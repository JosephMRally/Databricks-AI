# RAW_SEC_253G2

**Sheet:** `RAW_SEC_253G2` — the **per-series pro-forma financial content** from every **Form 253G2** (offering circular) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form. Primarily the **`UNAUDITED COMBINED PRO FORMA BALANCE SHEET`** (per-series assets & liabilities — the housing values and mortgages as of the offering date). This is the offering-circular balance-sheet content the skill previously tracked as `RAW_SECBalanceSheet`.
**Source:** the 253G2 offering-circular `.htm` (large, ~1–2 MB; the pro-forma balance sheet is deep in the document, past WebFetch's truncation — parse via the browser/`DOMParser`, same engine as the 1-K balance sheet). See `api-reference.md` → **"SEC filing extraction"**.
**`source` tag:** `sec:253g2-html-tables`
**SCD type:** **Type 2** (append-only). **`filingDate` + `accession` in the grain**; keep every 253G2; skip accessions already present.

## What tables to capture

- **`UNAUDITED COMBINED PRO FORMA BALANCE SHEET`** — per-series **Assets** / **Liabilities** / **Equity** line items (`Property and equipment, net` = the housing value; `Loan payable, net` = the mortgage, `$-` = all-cash). Layout is the same series-oriented consolidating shape the 1-K engine already handles (series as columns or the schedule's per-series rows).
- Any other named per-series financial schedules present in the circular.

## Columns (tidy/long)

`form` (`253G2`), `filingDate`, `entityName`, `accession`, `as_of_date` (the balance-sheet date printed under the title, as **`YYYY-MM-DD`**), `statement`, `line_item` (verbatim, e.g. `Property and equipment, net`, `Loan payable, net`, `Total assets`), `property` (series name), `value`.

**One row per property × line-item** — `property` and `value` are their own fields; do not pivot.

## Notes
- Same content-driven extraction engine as 1-K/1-SA (`api-reference.md`).
- Reg A has **no quarterly (10-Q)** report; the offering circular (253G2 / 1-A POS) is the pro-forma source. Match `property` → held offering by `name`.
- Enumerate the same four parent LLCs as the other SEC sheets: `1821720`, `1962723`, `2015697`, `2032732`. The 253G2 `primaryDocument` **is** the report `.htm`. All date fields are `YYYY-MM-DD`.
