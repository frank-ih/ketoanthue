"""Batch article publisher for ketoanthue.ai.vn — generates SEO articles and publishes as static HTML.

Uses direct LLM calls (1 per article) for reliable batch generation,
then publishes each article via the blog.publish module.

Usage:
    python scripts/publish_blog_articles.py [--limit N] [--start N] [--dry-run] [--skip-gen]

    --limit N      Generate/publish N articles (default: 30)
    --start N      Start at article index N in the plan
    --dry-run      Run pipeline but don't write files
    --skip-gen     Skip LLM generation, just generate OG images + sitemap

Requires: .env with ANTHROPIC_API_KEY or GLM_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Ensure src/ on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load .env
_ENV_PATH = Path(__file__).parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _v_clean = _v.strip().strip('"').strip("'")
            if _v_clean:
                os.environ[_k.strip()] = _v_clean

# Ketoanthue config
SITE_NAME = "Kế Toán Thuế AI"
BASE_URL = "https://ketoanthue.ai.vn"
PLAN_PATH = Path(__file__).parent.parent / "agents" / "seo_writer" / "blog_articles_plan.json"

from agentclan.modules.blog.publish import publish_article, regenerate_listing, regenerate_sitemap


# ---------------------------------------------------------------------------
# Direct LLM generation — 1 call per article
# ---------------------------------------------------------------------------

_ARTICLE_SYSTEM_PROMPT = """Bạn là chuyên gia SEO content writing cho thị trường kế toán-thuế Việt Nam.
Viết bài blog chuẩn SEO cho website ketoanthue.ai.vn — nền tảng AI kế toán cho doanh nghiệp SME Việt Nam.

Yêu cầu:
- Bài viết TIẾNG VIỆT, chuyên nghiệp, dễ hiểu cho chủ doanh nghiệp SME
- Độ dài 2000-3000 từ
- Cấu trúc rõ ràng: H1 → H2 → H3, có bảng, checklist, FAQ
- Tối ưu SEO: từ khóa chính xuất hiện tự nhiên, heading chứa từ khóa
- Có ví dụ thực tế, con số cụ thể, trích dẫn quy định pháp luật
- Mỗi mục có nội dung thực chất, KHÔNG lấp đầy bằng từ ngữ sáo rỗng
- Có phần FAQ (5-8 câu hỏi) ở cuối bài
- Có call-to-action giới thiệu giải pháp AI kế toán tự nhiên, không spam
- Nêu rõ nguồn luật: Luật số, Nghị định số, Thông tư số khi relevant"""

_ARTICLE_USER_TEMPLATE = """Viết bài blog SEO hoàn chỉnh về chủ đề: "{title}"

Thông tin bài viết:
- Từ khóa chính: {primary_keyword}
- Từ khóa phụ: {secondary_keywords}
- Danh mục: {category_label}
- Đối tượng: {target_audience}
- Loại bài: {article_type}
- Năm tham chiếu: 2026

QUAN TRỌNG: Phải tuân thủ đúng format JSON bên dưới, KHÔNG thêm text nào khác.

Trả về ĐÚNG MỘT JSON object với cấu trúc sau (không markdown fence):
{{
  "meta_title": "Tiêu đề SEO dưới 60 ký tự, chứa từ khóa chính",
  "meta_description": "Mô tả SEO dưới 155 ký tự, hấp dẫn, chứa từ khóa",
  "content": "Nội dung bài viết đầy đủ bằng markdown (2000-3000 từ). Dùng ## cho H2, ### cho H3. Bao gồm bảng, checklist, FAQ.",
  "primary_keyword": "{primary_keyword}",
  "secondary_keywords": [{secondary_keywords_json}],
  "word_count": 0
}}"""


def _build_category_label(category: str) -> str:
    """Map category slug to Vietnamese label."""
    labels = {
        "thue-doanh-nghiep": "Thuế Doanh Nghiệp",
        "ke-toan": "Kế Toán",
        "hoa-don-dien-tu": "Hóa Đơn Điện Tử",
        "ai-ke-toan": "AI Kế Toán",
        "thue-ca-nhan": "Thuế Cá Nhân",
        "khoi-nghiep": "Khởi Nghiệp & Tuân Thủ",
        "huong-dan": "Hướng Dẫn",
    }
    return labels.get(category, category)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Parse LLM response into article dict."""
    # Try to extract JSON from response
    text = raw.strip()

    # Remove markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    # Try direct JSON parse
    try:
        data = json.loads(text)
        return _validate_article(data)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            data = json.loads(text[brace_start:brace_end + 1])
            return _validate_article(data)
        except json.JSONDecodeError:
            pass

    # Fallback: treat entire response as content
    return {
        "meta_title": "",
        "meta_description": "",
        "content": text,
        "primary_keyword": "",
        "secondary_keywords": [],
        "word_count": len(text.split()),
    }


def _validate_article(data: dict) -> dict:
    """Validate and clean parsed article data."""
    content = data.get("content", "")
    word_count = data.get("word_count") or len(content.split())
    return {
        "meta_title": data.get("meta_title", "")[:65],
        "meta_description": data.get("meta_description", "")[:160],
        "content": content,
        "primary_keyword": data.get("primary_keyword", ""),
        "secondary_keywords": data.get("secondary_keywords", []),
        "word_count": word_count,
    }


async def _call_llm(messages: list[dict], model: str, api_key: str, api_base: str | None = None) -> str:
    """Make a single LLM call with retry logic."""
    import litellm

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": 8192,
                "temperature": 0.7,
                "api_key": api_key,
            }
            if api_base:
                kwargs["api_base"] = api_base

            response = await litellm.acompletion(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            is_rate = "rate" in str(exc).lower() or "429" in str(exc)
            if is_rate and attempt < max_retries:
                wait = min(10 * (2 ** attempt), 120)
                print(f"    [rate-limit] retry {attempt}/{max_retries} in {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise


async def generate_article(article: dict, model: str, api_key: str, api_base: str | None = None) -> dict[str, Any]:
    """Generate a single article via direct LLM call."""
    title = article["title"]
    category = article["category"]
    primary_kw = article.get("primary_keyword", title)
    secondary_kws = article.get("secondary_keywords", [primary_kw])

    sec_kw_json = json.dumps(secondary_kws, ensure_ascii=False)
    user_prompt = _ARTICLE_USER_TEMPLATE.format(
        title=title,
        primary_keyword=primary_kw,
        secondary_keywords=", ".join(secondary_kws),
        secondary_keywords_json=sec_kw_json,
        category_label=_build_category_label(category),
        target_audience=article.get("target_audience", "Chủ doanh nghiệp SME"),
        article_type=article.get("article_type", "standard"),
    )

    messages = [
        {"role": "system", "content": _ARTICLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = await _call_llm(messages, model, api_key, api_base)
    parsed = _parse_llm_response(raw)

    # Fallback title from plan if LLM didn't provide one
    if not parsed["meta_title"]:
        parsed["meta_title"] = title

    return parsed


def load_plan(limit: int = 30, start: int = 0) -> list[dict]:
    """Load article plan from JSON."""
    if not PLAN_PATH.exists():
        print(f"ERROR: Plan not found at {PLAN_PATH}")
        sys.exit(1)
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    return plan[start: start + limit]


async def generate_and_publish(
    articles: list[dict],
    model: str,
    api_key: str,
    api_base: str | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """Generate articles via direct LLM calls and publish to disk."""
    from generate_og_image import generate_og_svg
    from agentclan.modules.blog.publish import slugify as _slugify

    results: list[dict] = []

    for i, article in enumerate(articles, start=1):
        title = article["title"]
        category = article["category"]
        promoted = article.get("promoted_to_root", False)

        print(f"\n[{i}/{len(articles)}] {title[:60]}...")
        t0 = time.monotonic()

        try:
            # Retry article generation up to 3 times
            parsed = None
            for attempt in range(1, 4):
                parsed = await generate_article(article, model, api_key, api_base)
                if parsed.get("word_count", 0) >= 500:
                    break
                if attempt < 3:
                    print(f"  Low word count ({parsed.get('word_count', 0)}), retry {attempt}/3...")
                    await asyncio.sleep(15)

            elapsed = time.monotonic() - t0
            word_count = parsed.get("word_count", 0)
            print(f"  words={word_count}  time={elapsed:.1f}s")

            if word_count < 100:
                print(f"  SKIPPED (too short: {word_count} words)")
                results.append({
                    "title": title, "category": category,
                    "word_count": word_count, "success": False,
                    "time_s": round(elapsed, 1),
                })
                continue

            if not dry_run:
                slug = _slugify(parsed.get("meta_title", title))

                # Generate OG image
                og_path = generate_og_svg(title, category, slug)
                og_url = f"{BASE_URL}/blog/{category}/{slug}-og.svg"

                # Build result dict for publish_article
                pub_result = {
                    "meta_title": parsed["meta_title"],
                    "meta_description": parsed["meta_description"],
                    "content": parsed["content"],
                    "secondary_keywords": parsed.get("secondary_keywords", []),
                    "og_image": og_url,
                    "topic": title,
                }

                pub = await publish_article(
                    pub_result,
                    category=category,
                    promoted_to_root=promoted,
                    site_name=SITE_NAME,
                    base_url=BASE_URL,
                )
                print(f"  Published: {pub['url']}")

                results.append({
                    "slug": pub["slug"],
                    "title": title,
                    "category": category,
                    "word_count": word_count,
                    "success": True,
                    "time_s": round(elapsed, 1),
                    "url": pub["url"],
                })
            else:
                print(f"  [DRY RUN] Would publish: {title[:50]}")
                results.append({
                    "title": title, "category": category,
                    "word_count": word_count, "success": True,
                    "time_s": round(elapsed, 1),
                })

        except Exception as e:
            elapsed = time.monotonic() - t0
            print(f"  ERROR: {e}")
            results.append({
                "title": title, "category": category,
                "success": False, "error": str(e),
                "time_s": round(elapsed, 1),
            })

        # Rate limit spacing between articles
        if i < len(articles):
            await asyncio.sleep(10)

    return results


async def publish_from_plan(
    limit: int = 30,
    start: int = 0,
    dry_run: bool = False,
    skip_gen: bool = False,
) -> list[dict]:
    """Main entry: load plan, generate, publish."""
    articles = load_plan(limit, start)
    print(f"Loaded {len(articles)} articles from plan (start={start}, limit={limit})")

    if skip_gen:
        from generate_og_image import generate_from_plan
        print("Skipping LLM generation. Generating OG images...")
        generate_from_plan(str(PLAN_PATH))
        regenerate_listing(site_name=SITE_NAME, base_url=BASE_URL)
        regenerate_sitemap(base_url=BASE_URL)
        print("Done (skip-gen mode).")
        return []

    # Determine LLM config
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    glm_key = os.environ.get("GLM_API_KEY", "")

    if anthropic_key:
        model = os.environ.get("ANTHROPIC_MODEL", "anthropic/claude-sonnet-4-6")
        api_key = anthropic_key
        api_base = None
        print(f"Using Anthropic model: {model}")
    elif glm_key:
        model = os.environ.get("GLM_MODEL", "openai/GLM-5")
        api_key = glm_key
        api_base = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/paas/v4/")
        print(f"Using GLM model: {model} (base: {api_base})")
    else:
        print("ERROR: No API key found. Set ANTHROPIC_API_KEY or GLM_API_KEY in .env")
        sys.exit(1)

    results = await generate_and_publish(articles, model, api_key, api_base, dry_run)

    # Regenerate listing + sitemap
    if not dry_run:
        regenerate_listing(site_name=SITE_NAME, base_url=BASE_URL)
        regenerate_sitemap(base_url=BASE_URL)
        print("\nRegenerated blog listing and sitemap.")

    # Summary
    print("\n" + "=" * 70)
    print("BATCH SUMMARY")
    print("=" * 70)
    succeeded = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    total_words = sum(r.get("word_count", 0) for r in succeeded)
    total_time = sum(r.get("time_s", 0) for r in results)
    print(f"Total: {len(results)} | Published: {len(succeeded)} | Failed: {len(failed)}")
    print(f"Total words: {total_words:,} | Total time: {total_time:.1f}s")

    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        wc = r.get("word_count", 0)
        t = r.get("time_s", 0)
        slug = r.get("slug", r.get("title", "")[:30])
        print(f"  [{status}] {slug[:50]:50s} {wc:>5d}w  {t:>5.1f}s")

    return results


def main():
    parser = argparse.ArgumentParser(description="Batch publish ketoanthue.ai.vn blog articles")
    parser.add_argument("--limit", type=int, default=30, help="Number of articles (default: 30)")
    parser.add_argument("--start", type=int, default=0, help="Start index (default: 0)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    parser.add_argument("--skip-gen", action="store_true", help="Skip LLM, just OG images + sitemap")
    args = parser.parse_args()

    asyncio.run(publish_from_plan(
        limit=args.limit, start=args.start,
        dry_run=args.dry_run, skip_gen=args.skip_gen,
    ))


if __name__ == "__main__":
    main()
