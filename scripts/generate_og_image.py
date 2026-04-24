"""Generate branded SVG OG images for ketoanthue.ai.vn blog articles.

Creates 1200x630 SVG files with article title, category badge, and brand.
Output: web/static/blog/{category}/{slug}-og.svg

Usage:
    python scripts/generate_og_image.py --title "Tiêu đề bài viết" --category "ai-ke-toan" --slug "tieu-de-bai-viet"
    python scripts/generate_og_image.py --plan agents/seo_writer/blog_articles_plan.json
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
import unicodedata
from pathlib import Path

# Brand constants
_ORANGE = "#e05c20"
_DARK = "#19110a"
_WHITE = "#ffffff"
_LIGHT_BG = "#faf8f5"
_MUTED = "rgba(25,17,10,0.52)"

_BLOG_DIR = Path(__file__).parent.parent / "web" / "public" / "blog"

# Category colors for badge
_CAT_COLORS: dict[str, str] = {
    "thue-doanh-nghiep": "#e05c20",
    "ke-toan": "#2d7dd2",
    "hoa-don-dien-tu": "#6c5ce7",
    "ai-ke-toan": "#00b894",
    "thue-ca-nhan": "#fdcb6e",
    "khoi-nghiep": "#e17055",
    "huong-dan": "#74b9ff",
    "general": "#636e72",
}

_CAT_LABELS: dict[str, str] = {
    "thue-doanh-nghiep": "Thuế Doanh Nghiệp",
    "ke-toan": "Kế Toán",
    "hoa-don-dien-tu": "Hóa Đơn Điện Tử",
    "ai-ke-toan": "AI Kế Toán",
    "thue-ca-nhan": "Thuế Cá Nhân",
    "khoi-nghiep": "Khởi Nghiệp",
    "huong-dan": "Hướng Dẫn",
    "general": "Chung",
}


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _wrap_text(text: str, max_chars_per_line: int = 32) -> list[str]:
    """Wrap text into lines for SVG rendering."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) <= max_chars_per_line:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    # Cap at 4 lines
    return lines[:4]


def generate_og_svg(
    title: str,
    category: str,
    slug: str,
    blog_dir: Path | None = None,
) -> Path:
    """Generate an OG image SVG for a blog article."""
    blog_dir = blog_dir or _BLOG_DIR

    cat_color = _CAT_COLORS.get(category, _ORANGE)
    cat_label = _CAT_LABELS.get(category, category)

    # Wrap title into lines
    lines = _wrap_text(title, max_chars_per_line=28)
    if not lines:
        lines = ["Untitled"]

    # Build title text blocks
    title_blocks = ""
    line_height = 52
    start_y = 260
    font_size = 42

    # Reduce font size if many lines
    if len(lines) > 3:
        font_size = 34
        line_height = 44
    elif len(lines) > 2:
        font_size = 38
        line_height = 48

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        title_blocks += f'<text x="80" y="{y}" font-family="Be Vietnam Pro, Arial, sans-serif" font-size="{font_size}" font-weight="700" fill="{_DARK}">{_escape_xml(line)}</text>\n'

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{_LIGHT_BG}"/>
      <stop offset="100%" stop-color="#f4efe6"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>

  <!-- Top bar -->
  <rect width="1200" height="8" fill="{cat_color}"/>

  <!-- Category badge -->
  <rect x="80" y="170" rx="16" ry="16" width="{len(cat_label) * 12 + 32}" height="36" fill="{cat_color}" opacity="0.12"/>
  <rect x="80" y="170" rx="16" ry="16" width="{len(cat_label) * 12 + 32}" height="36" fill="none" stroke="{cat_color}" stroke-width="1.5"/>
  <text x="96" y="194" font-family="Be Vietnam Pro, Arial, sans-serif" font-size="14" font-weight="600" fill="{cat_color}">{_escape_xml(cat_label)}</text>

  <!-- Title -->
  {title_blocks}

  <!-- Bottom bar -->
  <rect x="80" y="530" width="40" height="40" rx="8" fill="{cat_color}"/>
  <text x="94" y="558" font-family="Arial" font-size="20" fill="{_WHITE}">&#9889;</text>
  <text x="132" y="558" font-family="Be Vietnam Pro, Arial, sans-serif" font-size="18" font-weight="600" fill="{_DARK}">Kế Toán Thuế AI</text>
  <text x="132" y="578" font-family="Be Vietnam Pro, Arial, sans-serif" font-size="13" fill="{_MUTED}">ketoanthue.ai.vn</text>

  <!-- Decorative elements -->
  <circle cx="1050" cy="100" r="180" fill="{cat_color}" opacity="0.04"/>
  <circle cx="1100" cy="530" r="120" fill="{cat_color}" opacity="0.03"/>
</svg>"""

    # Write to file
    cat_dir = blog_dir / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    output_path = cat_dir / f"{slug}-og.svg"
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def generate_from_plan(plan_path: str, blog_dir: Path | None = None) -> list[Path]:
    """Generate OG images for all articles in a plan JSON file."""
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    results: list[Path] = []

    for article in plan:
        title = article["title"]
        category = article["category"]
        # Generate slug from title
        slug = _slugify(title)
        path = generate_og_svg(title, category, slug, blog_dir)
        results.append(path)
        print(f"  OG: {path.name}")

    return results


def _slugify(text: str) -> str:
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:100] if text else "untitled"


def main():
    parser = argparse.ArgumentParser(description="Generate OG SVG images for ketoanthue.ai.vn blog")
    parser.add_argument("--title", help="Article title")
    parser.add_argument("--category", default="general", help="Category slug")
    parser.add_argument("--slug", help="URL slug (auto-generated from title if omitted)")
    parser.add_argument("--plan", help="Path to blog_articles_plan.json to batch generate")
    args = parser.parse_args()

    if args.plan:
        print(f"Generating OG images from plan: {args.plan}")
        paths = generate_from_plan(args.plan)
        print(f"Generated {len(paths)} OG images")
    elif args.title:
        slug = args.slug or _slugify(args.title)
        path = generate_og_svg(args.title, args.category, slug)
        print(f"Generated: {path}")
    else:
        parser.error("Provide --title or --plan")


if __name__ == "__main__":
    main()
