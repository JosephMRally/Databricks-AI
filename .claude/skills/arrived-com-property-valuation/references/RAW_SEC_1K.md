# RAW_SEC_1K

**Sheet:** `RAW_SEC_1K` — the **financial-table content** of every **Form 1-K** (annual report) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form (one row per table cell). NOT a filing index — the actual numbers out of the statements.
**Source:** the 1-K's main annual-report `.htm` (the large document whose name contains `1k`, e.g. `ea0288058-1k_arrived3.htm`) — **not** the XBRL cover `primary_doc.xml`. Find filings via the EDGAR submissions API and open each filing's report `.htm`. See `api-reference.md` → **"SEC filing extraction"** for the shared discovery + bulk-fetch + parsing engine.
**`source` tag:** `sec:1-k-html-tables`
**SCD type:** **Type 2** (append-only; filings are immutable). **`filingDate` (and `accession`) are part of the grain** — keep the full history of every 1-K. A re-run skips any `accession` already present.

## What tables to capture (all named financial tables in the 1-K)

Arrived 1-Ks present a **consolidating** view where **each property is a "series"**. Capture every named financial table:

- **Consolidating statements** (series are **columns**, ~8 per physical page, one statement split across ~12 tables; a final page adds a **`Consolidated`** total column): `CONSOLIDATED AND CONSOLIDATING BALANCE SHEET`, `... STATEMENT OF COMPREHENSIVE INCOME (LOSS)` (older filings: `... STATEMENT OF OPERATIONS`), `CONSOLIDATED STATEMENT OF CHANGES IN MEMBERS' EQUITY (DEFICIT)`, `... STATEMENT OF CASH FLOWS` — each for **both** the current and prior year.
- **Per-series note schedules** (series are **rows**): `Rental Income`, `Operating Expenses`, `Other Expenses (Income)`, `Cash & Cash Equivalents`, `PROPERTY AND EQUIPMENT`, `MEMBERS' EQUITY (OFFERINGS BY SERIES)`, `DISTRIBUTIONS BY SERIES`, `RELATED PARTY TRANSACTIONS` — audited annual and (where present) the interim stub period.

## Columns (tidy/long — one row per property × line-item; `property` and `value` are their own fields)

| Column | Meaning |
|---|---|
| `form` | `1-K` (or `1-K/A`). |
| `filingDate` | EDGAR filing date `YYYY-MM-DD` (**part of the grain**). |
| `entityName` | e.g. `Arrived Homes 3, LLC`. |
| `accession` | EDGAR accession `NNNNNNNNNN-NN-NNNNNN` (**part of the grain**). |
| `statement` | the table name, verbatim (e.g. `CONSOLIDATED AND CONSOLIDATING BALANCE SHEET`, `RELATED PARTY TRANSACTIONS`). |
| `period_basis` | `as_of` (balance sheet, P&E) \| `year_ended` (flows) \| `period` (offerings/related-party) \| `stub_period`. |
| `period` | the reporting date/period the value covers — **`YYYY-MM-DD`** when it's a date (e.g. `2025-12-31`). |
| `line_item` | the row label (e.g. `Total assets`, `Rental income`, `Net income (loss)`, `Building`, `Sourcing fees`). |
| `property` | **the series/property name** (e.g. `Adams`, `Hedgecrest`), or `Consolidated` for the roll-up column. Join to holdings by matching `property` → offering `name`. |
| `value` | the cell value, cleaned: digits only, negatives as `-N` (from `( )`), `-`/blank → `0`. |

**Do NOT pivot on `property`.** Each property × line-item is its own row, with `property` and `value` as fields (the sheet must not have one column per series).

## Notes
- Extraction engine (order-token coalescing, content-driven table detection, cross-checks) is shared across 1-K/1-SA — see `api-reference.md`.
- **Comparative years:** later filings carry both the current and prior year in one statement; the engine tags each with its own `period`, so `period` is part of the effective grain. Never collapse a filing to one period.
- **Drop blank-statement rows:** rows with an empty `statement` (and empty `line_item`) come from an unclassifiable / interim "Recent Developments" table — filter them out before landing (they partly duplicate named statements).
- Verify: **Consolidated = sum of the series grouped by `(filingDate, period)`** (ties to the dollar, ±$1–2 rounding); **`Property and equipment, net` = balance-sheet figure**; the **same period matches across filings** (e.g. `Dec 31, 2024` P&E net = 25,742,292 in the 2025 & 2026 1-K and the 2025 1-SA). AH3 reference counts: 1-K = 40,057 tidy rows across the 3 filings (2024/2025/2026), 1-SA = 32,640.
- Full history across the parent LLCs (`1821720` Arrived Homes, `1962723` Arrived Homes 3, `2015697` Arrived Homes 4, `2032732` Arrived Homes 5); older filings have fewer series (properties added over time) — absent series are simply omitted rows, not blanks.
