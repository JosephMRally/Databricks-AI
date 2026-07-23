# RAW_SEC_253G2

**Output (CSV):** **one CSV per filing** — `RAW_SEC_253G2/<filingDate>_<accession>.csv` (**1:1** with each extracted 253G2; **never a combined file**). The **per-series financial content** from every **Form 253G2** (offering circular) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form. Primarily the per-series **balance sheet** (assets & liabilities — the housing values and mortgages as of the offering/estimate date).
**Source:** the 253G2 offering-circular `.htm` (large, ~1–2 MB; the balance sheet is deep in the document, past WebFetch's truncation — parse via the browser/`DOMParser`, same engine as the 1-K balance sheet). See `api-reference.md` → **"SEC filing extraction"**.
**`source` tag:** `sec:253g2-html-tables`
**Load model:** **one immutable CSV per SEC filing (1:1).** Filings never change once filed, so there is **no SCD history and no bookkeeping columns**. Incremental: a re-run **skips any accession whose `RAW_SEC_253G2/<filingDate>_<accession>.csv` already exists** and only fetches + writes new filings. Do **not** combine filings into one CSV — the 1:1 mapping is what keeps loads incremental and fast.
**Within-file grain:** one row per (`statement`, `section`, `line_item`, `property`). `filingDate` / `accession` / `as_of_date` are constant within a file (kept as columns so each CSV is self-describing and concatenable).
**Sort order (within file):** `statement`, `section`, `line_item`, `property` (ascending).

## What tables to capture

- **The per-series balance sheet** — captured under its **verbatim title**, which varies by filing vintage: newer filings print **`BALANCE SHEET (UNAUDITED)`**, older ones **`UNAUDITED COMBINED PRO FORMA BALANCE SHEET`** or **`CONSOLIDATED BALANCE SHEET`**. Per-series **Assets** / **Liabilities** / **Equity** line items (`Property and equipment, net` = the housing value; the mortgage line is filed **verbatim** — e.g. `Mortgage payables` on recent filings — with `-`/`$-` = all-cash → `0`). Layout is the same series-oriented consolidating shape the 1-K engine handles: series names are the **first row** of each fragment table; each line-item row maps its numeric tokens in order to those series.
- Any other named per-series financial schedules present in the circular.

## Columns (tidy/long — one row per property × line-item; `property` and `value` are their own fields)

| Column | Meaning |
|---|---|
| `filingDate` | EDGAR filing date `YYYY-MM-DD` (**part of the grain**). |
| `accession` | EDGAR accession number (**part of the grain**). |
| `as_of_date` | the balance-sheet date printed under/beside the title (e.g. footnote "Estimated Balance Sheet as of March 31, 2026"), as `YYYY-MM-DD`. |
| `statement` | the schedule's **verbatim** title (e.g. `BALANCE SHEET (UNAUDITED)`, or older `UNAUDITED COMBINED PRO FORMA BALANCE SHEET` / `CONSOLIDATED BALANCE SHEET`). |
| `section` | the balance-sheet section — `ASSETS` \| `LIABILITIES` \| `EQUITY` — needed because a label (e.g. `Due to (from) related parties`) can appear in more than one section. |
| `line_item` | verbatim line item (e.g. `Property and equipment, net`, `Mortgage payables`, `Total assets`). |
| `property` | the series/property name. Join to holdings by matching `property` → offering `name`. **Roll-up/aggregate columns (`Consolidated`, `Pro Forma Combined`) are excluded** — only individual property series are landed. |
| `value` | the cell value, cleaned: digits only, negatives as `-N` (from `( )`), `-`/blank → `0`. |

**Do NOT pivot on `property`.** Each property × line-item is its own row, with `property` and `value` as fields (the file must not have one column per series).

## Notes
- **Verified 2026-07:** 26 filings → 26 CSVs, 54,857 rows, **every individual-property balance sheet reconciles** (`Total assets = Total liabilities + equity`). Roll-up columns are excluded; the two oldest small "sticker" 253G2s carry no balance sheet (0 rows).
- Same content-driven extraction engine as 1-K/1-SA (`api-reference.md`); built as `tools/sec-extractor/`.
- Reg A has **no quarterly (10-Q)** report; the offering circular (253G2 / 1-A POS) carries the per-series balance sheet (older filings label it "pro forma", newer ones "estimated"). Match `property` → held offering by `name`.
- Enumerate the same four parent LLCs as the other SEC forms: `1821720`, `1962723`, `2015697`, `2032732`. The 253G2 `primaryDocument` **is** the report `.htm`. All date fields are `YYYY-MM-DD`.
