# RAW_SEC_1SA

**Output (CSV):** **one CSV per filing** — `RAW_SEC_1SA/<filingDate>_<accession>.csv` (**1:1** with each extracted 1-SA; **never a combined file**). The **financial-table content** of every **Form 1-SA** (semiannual report) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form (one row per table cell). Same structure and extraction as `RAW_SEC_1K`, but **unaudited** and **semiannual** (periods end **June 30**, with an **as-of Dec 31** comparative on the balance sheet).
**Source:** the 1-SA's report `.htm` (name contains `1sa`, e.g. `ea0257633-1sa_arrived3.htm`) — this **is** the primary document for 1-SAs (unlike 1-Ks). See `api-reference.md` → **"SEC filing extraction"**.
**`source` tag:** `sec:1-sa-html-tables`
**Load model:** **one immutable CSV per SEC filing (1:1).** Filings never change once filed, so there is **no SCD history and no bookkeeping columns**. Incremental: a re-run **skips any accession whose `RAW_SEC_1SA/<filingDate>_<accession>.csv` already exists** and only fetches + writes new filings. Do **not** combine filings into one CSV — the 1:1 mapping is what keeps loads incremental and fast.
**Within-file grain:** one row per (`statement`, `period`, `section`, `line_item`, `property`). `filingDate` / `accession` are constant within a file (kept as columns so each CSV is self-describing and concatenable).
**Sort order (within file):** `statement`, `period`, `section`, `line_item`, `property` (ascending; ISO dates sort as text).

## What tables to capture

Same consolidating statements and per-series note schedules as the 1-K (see `RAW_SEC_1K.md`), detected the same way. The comprehensive-income statement may appear as `... STATEMENT OF OPERATIONS`; the engine's title detection handles both. `period_basis` for the semiannual flows is `period_ended` (six months ended June 30).

## Columns (tidy/long — identical schema to RAW_SEC_1K)

| Column | Meaning |
|---|---|
| `filingDate` | EDGAR filing date `YYYY-MM-DD` (**part of the grain**). |
| `accession` | EDGAR accession `NNNNNNNNNN-NN-NNNNNN` (**part of the grain**). |
| `statement` | the table name, verbatim (e.g. `CONSOLIDATED AND CONSOLIDATING BALANCE SHEET`, `RELATED PARTY TRANSACTIONS`). |
| `period_basis` | `as_of` (balance sheet, P&E) \| `period_ended` (semiannual flows — six months ended June 30) \| `period` (offerings/related-party) \| `stub_period`. |
| `period` | the reporting date/period the value covers — **`YYYY-MM-DD`** when it's a date (e.g. `2025-06-30`). The balance sheet carries the interim (June 30) and the prior year-end (Dec 31) comparative; each fragment's period is the `BALANCE SHEET AS OF <date>` it falls under. |
| `section` | balance-sheet section — `ASSETS` \| `LIABILITIES` \| `EQUITY` — disambiguates a label that repeats across sections. |
| `line_item` | the row label (e.g. `Total assets`, `Rental income`, `Net income (loss)`, `Building`, `Sourcing fees`). |
| `property` | **the series/property name** (e.g. `Adams`, `Hedgecrest`). Join to holdings by matching `property` → offering `name`. **Roll-up/aggregate columns (`Consolidated`) are excluded** — only individual series are landed. |
| `value` | the cell value, cleaned: digits only, negatives as `-N` (from `( )`), `-`/blank → `0`. |

**Do NOT pivot on `property`.** Each property × line-item is its own row, with `property` and `value` as fields (the file must not have one column per series).

> **Coverage note (as built):** same as `RAW_SEC_1K` — the **consolidating balance sheet** is landed and reconciled per series; the flow statements and per-series note schedules are not yet extracted. Balance sheets that don't self-balance in the source filing are landed verbatim (a handful of AH4 series in the 2024 1-SA are imbalanced in Arrived's own numbers).

## Notes
- Shared extraction engine + cross-checks: `api-reference.md`.
- 1-SA balance sheets **may or may not** carry a `Consolidated` total column — it's **entity-dependent** (AH3's June-30 interim omits it; AH `1821720` includes one). When absent, per-series values are still fully captured, only the roll-up column is blank — don't treat a missing `Consolidated` as a parse error.
- Series count grows over time (e.g. AH3: 2023 ≈ 59, 2024 ≈ 86, 2025 ≈ 97); absent series → omitted rows.
- All date fields (`filingDate`, and `period` when it's a date) are emitted **`YYYY-MM-DD`** (e.g. `2025-06-30`).
- Four parent LLCs: `1821720` (Arrived Homes), `1962723` (Arrived Homes 3), `2015697` (Arrived Homes 4), `2032732` (Arrived Homes 5).
