# RAW_SEC_1K

**Output (CSV):** **one CSV per filing** — `RAW_SEC_1K/<filingDate>_<accession>.csv` (**1:1** with each extracted 1-K; **never a combined file**). The **financial-table content** of every **Form 1-K** (annual report) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form (one row per table cell). NOT a filing index — the actual numbers out of the statements.
**Source:** the 1-K's main annual-report `.htm` (the large document whose name contains `1k`, e.g. `ea0288058-1k_arrived3.htm`) — **not** the XBRL cover `primary_doc.xml`. Find filings via the EDGAR submissions API and open each filing's report `.htm`. See `api-reference.md` → **"SEC filing extraction"** for the shared discovery + bulk-fetch + parsing engine.
**`source` tag:** `sec:1-k-html-tables`
**Load model:** **one immutable CSV per SEC filing (1:1).** Filings never change once filed, so there is **no SCD history and no bookkeeping columns**. Incremental: a re-run **skips any accession whose `RAW_SEC_1K/<filingDate>_<accession>.csv` already exists** and only fetches + writes new filings. Do **not** combine filings into one CSV — the 1:1 mapping is what keeps loads incremental and fast.
**Within-file grain:** one row per (`statement`, `period`, `section`, `line_item`, `property`). `filingDate` / `accession` are constant within a file (kept as columns so each CSV is self-describing and concatenable).
**Sort order (within file):** `statement`, `period`, `section`, `line_item`, `property` (ascending; ISO dates sort as text).

> **Coverage note (as built, verified 2026-07):** 11 filings → 11 CSVs, 43,647 rows, the **consolidating balance sheet** (series-as-columns) reconciling **2393/2393** per series (`Total assets = Total liabilities + equity`). Both comparative years are captured where the filing renders them as separate statement blocks; a first-year filing has one. The other consolidating statements (comprehensive income, cash flows, members' equity) and the per-series **note schedules** (series-as-rows) are **not yet extracted**. Two legacy AH filings (`0001213900-22-023267`, `0001213900-21-032674`) use a one-table-per-series layout the engine skips (0 rows, never garbage); a couple of AH4 filings land only the current year (side-by-side 2-column comparative not yet split). Built as `tools/sec-extractor/`.

## What tables to capture (all named financial tables in the 1-K)

Arrived 1-Ks present a **consolidating** view where **each property is a "series"**. Capture every named financial table:

- **Consolidating statements** (series are **columns**, ~8 per physical page, one statement split across ~12 tables; a final page adds a **`Consolidated`** total column): `CONSOLIDATED AND CONSOLIDATING BALANCE SHEET`, `... STATEMENT OF COMPREHENSIVE INCOME (LOSS)` (older filings: `... STATEMENT OF OPERATIONS`), `CONSOLIDATED STATEMENT OF CHANGES IN MEMBERS' EQUITY (DEFICIT)`, `... STATEMENT OF CASH FLOWS` — each for **both** the current and prior year.
- **Per-series note schedules** (series are **rows**): `Rental Income`, `Operating Expenses`, `Other Expenses (Income)`, `Cash & Cash Equivalents`, `PROPERTY AND EQUIPMENT`, `MEMBERS' EQUITY (OFFERINGS BY SERIES)`, `DISTRIBUTIONS BY SERIES`, `RELATED PARTY TRANSACTIONS` — audited annual and (where present) the interim stub period.

## Columns (tidy/long — one row per property × line-item; `property` and `value` are their own fields)

| Column | Meaning |
|---|---|
| `filingDate` | EDGAR filing date `YYYY-MM-DD` (**part of the grain**). |
| `accession` | EDGAR accession `NNNNNNNNNN-NN-NNNNNN` (**part of the grain**). |
| `statement` | the table name, verbatim (e.g. `CONSOLIDATED AND CONSOLIDATING BALANCE SHEET`, `RELATED PARTY TRANSACTIONS`). |
| `period_basis` | `as_of` (balance sheet, P&E) \| `year_ended` (flows) \| `period` (offerings/related-party) \| `stub_period`. |
| `period` | the reporting date/period the value covers — **`YYYY-MM-DD`** when it's a date (e.g. `2025-12-31`). A 1-K carries two balance-sheet years; each fragment's period is the `BALANCE SHEET AS OF <date>` it falls under. |
| `section` | balance-sheet section — `ASSETS` \| `LIABILITIES` \| `EQUITY` — disambiguates a label that repeats across sections (e.g. `Due to (from) related parties`). |
| `line_item` | the row label (e.g. `Total assets`, `Rental income`, `Net income (loss)`, `Building`, `Sourcing fees`). |
| `property` | **the series/property name** (e.g. `Adams`, `Hedgecrest`). Join to holdings by matching `property` → offering `name`. **Roll-up/aggregate columns (`Consolidated`) are excluded** — only individual series are landed. |
| `value` | the cell value, cleaned: digits only, negatives as `-N` (from `( )`), `-`/blank → `0`. |

**Do NOT pivot on `property`.** Each property × line-item is its own row, with `property` and `value` as fields (the file must not have one column per series).

## Notes
- Extraction engine (order-token coalescing, content-driven table detection, cross-checks) is shared across 1-K/1-SA — see `api-reference.md`.
- **Comparative years:** later filings carry both the current and prior year in one statement; the engine tags each with its own `period`, so `period` is part of the effective grain. Never collapse a filing to one period.
- **Drop blank-statement rows:** rows with an empty `statement` (and empty `line_item`) come from an unclassifiable / interim "Recent Developments" table — filter them out before landing (they partly duplicate named statements).
- Verify: **Consolidated = sum of the series grouped by `(filingDate, period)`** (ties to the dollar, ±$1–2 rounding); **`Property and equipment, net` = balance-sheet figure**; the **same period matches across filings** (e.g. `Dec 31, 2024` P&E net = 25,742,292 in the 2025 & 2026 1-K and the 2025 1-SA). AH3 reference counts: 1-K = 40,057 tidy rows across the 3 filings (2024/2025/2026), 1-SA = 32,640.
- Full history across the parent LLCs (`1821720` Arrived Homes, `1962723` Arrived Homes 3, `2015697` Arrived Homes 4, `2032732` Arrived Homes 5); older filings have fewer series (properties added over time) — absent series are simply omitted rows, not blanks.
