# Accounting Agent — Gap Analysis: Transaction Recording & Tax/Financial Reports

**Date**: 2026-04-10
**Status**: Largely resolved — HTKK XML, progressive PIT, VN GL store, and BCTC implemented as of Phase 9
**Last Updated**: 2026-04-10 (reflecting Phase 9 implementation)

---

## Design Requirement Summary

The [accounting_agent_architecture.html](../../docs/accounting_agent_architecture.html) specifies 5 core agent responsibilities:

| Responsibility | Design Requirement |
|---|---|
| **Transaction Recording** | Record transactions, build double-entry JEs, enforce DR=CR, post to GL |
| **Financial Reports** | P&L, Balance Sheet, Cash Flow, Trial Balance, AP/AR Aging, GL Detail — full statements |
| **Tax Reports** | VAT (01/GTGT), CIT (01/TNDN), PIT (05/KK-TNCN), BCTC — all as **HTKK XML** export |
| **Accounting Software Integration** | MISA/Fast/AMIS adapters, webhook-first, dual-ledger sync, PostgreSQL GL |
| **Knowledge Layer** | Qdrant VAS corpus, MOF circulars, regulation updater, meta-agent loop |

---

## Implementation Status — April 10, 2026

### ✅ Working — Core pipeline fully implemented

#### Tax Reports — HTKK XML (🔴 Critical Gap → ✅ Resolved)
- `step_tax_export.py`: 4 registered handlers — `htkk_xml_vat`, `htkk_xml_cit`, `htkk_xml_pit`, `package_htkk`
- Real XSD schemas from HTKK v5.6.5 installer (dated June 19, 2025, Thông tư 80/2021/TT-BTC):
  - `01_GTGT_TT80.xsd` — Form 01/GTGT VAT with `ct22-ct43` fields
  - `01_TNDN_TT80.xsd` — Form 01/TNDN CIT with income statement fields
  - `05_KK_TNCN_TT80.xsd` — Form 05/KK-TNCN PIT withholding with progressive bracket fields
  - `TKhaiThue.xsd` — base GDT schema with `HSoThue` root, `CTieuTKhaiChinh`
- lxml `XMLSchema` validation (non-blocking — `CKyDTu` digital signature excluded, user applies in HTKK)
- ZIP package with cover sheet + step-by-step instructions for HTKK signing
- Digital signature boundary enforced: agent produces unsigned XML, user signs in HTKK

#### Ledger Management — GL Store + Period Lock (🔴 Critical Gap → ✅ Resolved)
- `modules/gl_store.py` (826 lines): `AccountingGLStore` with `PeriodLockedError`, `UnbalancedEntryError`
  - `post_journal_entry`: append-only, DR=CR validation, refuses locked periods
  - `reverse_journal_entry`: creates reversing entry, marks original `is_reversed=True`
  - `get_trial_balance`: per-account debit/credit sums
  - `lock_period` / `is_period_locked`: period locking with `period_locks` table
  - `get_audit_trail`: immutable event log
- `modules/chart_of_accounts.py` (985 lines): `CHART_OF_ACCOUNTS_C200` + `CHART_OF_ACCOUNTS_C133`
  - VN-compliant 4-digit codes: 111 (Cash), 112 (Bank), 131 (AR), 133 (VAT input), 3331/3335/3336 (tax payable), 511 (Revenue), 632 (COGS), 8211 (CIT expense)
- `AccountingProcessingEngine.process()` wires `pg_pool` + `gl_store` into context (lines 283-290, 359-365)
- PostgreSQL schema: `chart_of_accounts`, `journal_entries`, `journal_lines`, `period_locks`, `audit_log`

#### Vietnam Tax Specificity (🟡 Partial Gap → ✅ Resolved)
- `VAT_RATES_VN` in `step_tax_compliance.py`: Circular 219/2013/TT-BTC Article 8 (10% standard, 5% reduced, 0% export)
- `CIT_RATES_VN`: Circular 78/2014/TT-BTC Article 11 (20% standard, 15%/17% incentive), Article 13
- `NON_DEDUCTIBLE_EXPENSES`: Circular 78/2014 Article 6-9 (traffic fines, entertainment, unverified expenses)
- Progressive PIT in `step_payroll.py` (277 lines): Circular 86/2016/TT-BTC Article 2
  - Brackets: 5% → 10% → 15% → 20% → 25% → 30% → 35%
  - SI caps: 35M VND/month (BHXH, BHYT, BHTN)
  - SI rates: employer 21.5%, employee 10.5%
  - Personal allowance: 11M VND/month resident, 4.4M VND/month per dependent
- Filing deadline references built into handlers

#### Financial Reports — BCTC (🟡 Partial Gap → ✅ Resolved)
- `step_financial_reporter.py`: `financial_reporter_bctc_c200` + `financial_reporter_bctc_c133`
  - B01-DN (Balance Sheet): row-by-row per Circular 200/2014
  - B02-DN (P&L): row-by-row with gross revenue → net profit before/after tax
  - Full row mapping: Total Assets = Total Liabilities + Equity enforced
- Circular 200/2014 and Circular 133/2016 SME charts available

#### Knowledge Layer — Meta-Agent + Eval Infrastructure (🟡 Partial → ✅ Resolved)
- `meta_agent.py` (260 lines): `AccountingMetaAgent` — eval-driven prompt optimization loop
  - `run_eval_cycle`: golden set evaluation against current prompts
  - `run_optimization_cycle`: detect regressions, propose/apply fixes, rollback on regression
  - Threshold tracking per category: vat/cit/pit/bctc/htkk/journal/period/escalation/oos/gl
- `golden_set.json` in `agents/accounting/eval/` (33 Q&A pairs, 16 intent tags)
- `metadata.yaml` in `agents/accounting/knowledge/`: circular IDs, effective dates, supersession chains, alert rules
- Knowledge crawlers: 14-source system built, 49 tests, batch embedding with L2 normalization + zero-vector elimination
- Circulars ingested: VAT 219/2013 (4 chunks), CIT 78/2014 (3 chunks), PIT 86/2016 (3 chunks)

---

## Remaining Gaps

### 🔴 Accounting Software Integration — In Progress

| Gap | Detail |
|---|---|
| **No MISA/Fast/AMIS adapters** | No adapter layer; no `read_account`, `post_journal_entry`, `get_trial_balance`, `list_invoices` |
| **No dual-ledger sync** | No sync back to accounting software |
| **No webhook listeners** | No event-driven push from external software |
| **No file import fallback** | For Fast Accounting (no API) — no CSV/Excel import processing |

**Status**: MISA AMIS partnership inquiry in progress. API reference: `https://www.misa.vn/155017/tai-lieu-open-api-tich-hop-misa-crm/`
- MISA AMIS: Partner API exists — "mọi nhà phát triển có thể linh hoạt kết nối qua API"
- Developer portal: `developers.misa.com.vn` — API key requires business partnership
- Recommended first integration: meInvoice (e-invoice API) — natural fit since agent already produces HTKK XML

**Impact**: Agent operates entirely in-memory or with its own GL. No integration with actual VN accounting software (MISA, Fast, AMIS). The "Adapter Layer" described in Diagram ③ does not exist.

### 🟡 Knowledge Layer — Partially Complete

| Gap | Detail |
|---|---|
| **No regulation updater** | RSS polling + alert pipeline for MOF gazette new circulars not implemented |
| **Qdrant production population** | Collection exists and circulars ingested; production population confirmed via tests |
| **BCTC chunks pending** | `bctc_200_2014` and `bctc_133_2016` have `chunk_count: 0` (pending ingestion) |

---

## Proposed Solutions (Updated)

### Solution 1: Accounting Software Adapter Layer *(🔴 Highest Priority — Still Open)*

```
modules/adapters/
├── __init__.py
├── base.py          # AccountingSoftwareAdapter ABC
├── misa.py          # MISA SME REST API
├── fast.py          # Fast Accounting (file-based)
└── Amis.py          # AMIS.vn / Base.vn OpenAPI
```

```python
class AccountingSoftwareAdapter(ABC):
    @abstractmethod
    async def read_account(self, code: str) -> Account: ...
    @abstractmethod
    async def post_journal_entry(self, je: JournalEntry) -> str: ...
    @abstractmethod
    async def get_trial_balance(self, period: str) -> TrialBalance: ...
    @abstractmethod
    async def list_invoices(self, filters: dict) -> list[Invoice]: ...
    @abstractmethod
    async def reconcile_bank(self, statement: BankStatement) -> ReconciliationReport: ...
    @abstractmethod
    async def export_report(self, report_type: str, period: str) -> bytes: ...
```

`DualLedgerSync` reconciles agent GL vs. software GL on demand, flags discrepancies without silently overwriting.

---

### Solution 2: Knowledge Regulation Updater *(🟡 Medium Priority — Still Open)*

Implement RSS polling + alert pipeline:

```python
class RegulationUpdater:
    SOURCES = [
        "https://mof.gov.vn/rss/van-ban",
        "https://gdt.gov.vn/rss/circulars",
    ]
    async def check_for_updates(self) -> list[RegulationUpdate]: ...
    async def alert_and_queue(self, update: RegulationUpdate): ...
```

---

## Recommended Priority Order (Updated)

1. **Solution 1 (Adapters)** — Only remaining 🔴 critical gap. MISA adapter first (most popular VN SME software).
2. **Solution 2 (Regulation Updater)** — RSS polling to alert when new circulars are published.

---

## Files Implemented

```
agents/accounting/
├── schemas/
│   ├── 01_GTGT_TT80.xsd          ✅ (from HTKK v5.6.5, June 2025)
│   ├── 01_TNDN_TT80.xsd           ✅
│   ├── 05_KK_TNCN_TT80.xsd        ✅
│   └── TKhaiThue.xsd              ✅
└── src/agentclan/agents/accounting/
    ├── handlers/
    │   └── step_tax_export.py     ✅ (4 handlers)
    └── modules/
        ├── gl_store.py            ✅ (826 lines)
        └── chart_of_accounts.py   ✅ (985 lines)
```

## Files to Create

```
agents/accounting/src/agentclan/agents/accounting/
modules/adapters/
├── __init__.py
├── base.py          # AccountingSoftwareAdapter ABC
├── misa.py          # MISA SME REST API
├── fast.py          # Fast Accounting (file-based)
└── amis.py          # AMIS.vn / Base.vn OpenAPI
```
