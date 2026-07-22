# RAW_SEC_1U

**Sheet:** `RAW_SEC_1U` — the **per-series distribution (dividend) declarations** from every **Form 1-U** (current report) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form. This is the SEC-sourced dividend record (complements the API dividend history and the computed tab's dividend-consistency column).
**Source:** each 1-U's report `.htm` (`current_report.htm`, sometimes `arrivedhomes3_1u.htm`). A distribution 1-U contains **one small table** with header `Series of {LLC} | Dividend Amount per Share`, one row per series. Non-distribution 1-Us (other current-report events) have no such table → skip them.
**`source` tag:** `sec:1-u-distributions`
**SCD type:** **Type 2** (append-only). **`filingDate` + `accession` in the grain**; keep every distribution 1-U; skip accessions already present. `reportDate` = the distribution/event date.

## Extraction (fast — bulk same-origin fetch, no per-doc navigation)

1-U docs are small and same-origin (`www.sec.gov`). From **one** `www.sec.gov` browser tab you can `fetch()` the submissions JSON (`https://data.sec.gov/submissions/CIK{paddedCik}.json` — CORS-open) to list all `1-U`/`1-U/A` filings, then `fetch()` **every** filing's `.htm` in the same JS pass, `DOMParser` each, and pull the `Series | Dividend Amount per Share` table. (Validated: AH3 = 40 filings, 32 with distribution tables, 2,438 rows, in one call.) See `api-reference.md` → "SEC filing extraction — bulk fetch".

## Columns (tidy/long — already property/value shaped)

| Column | Meaning |
|---|---|
| `form` | `1-U` (or `1-U/A`). |
| `filingDate` | EDGAR filing date `YYYY-MM-DD` (**grain**). |
| `entityName` | e.g. `Arrived Homes 3, LLC`. |
| `accession` | EDGAR accession (**grain**). |
| `reportDate` | the distribution/event date from the filing, as **`YYYY-MM-DD`**. |
| `property` | the series/property name (verbatim; join to holdings by `name`). |
| `dividend_amount_per_share` | the per-share distribution, `$`/spaces stripped (e.g. `0.051`). |

**One row per property per filing** — `property` and `value` (`dividend_amount_per_share`) are their own fields; do not pivot.

## Notes
- Enumerate parent LLCs `1821720` (Arrived Homes) / `1962723` (Arrived Homes 3) / `2015697` (Arrived Homes 4) / `2032732` (Arrived Homes 5); each has its own 1-U stream (roughly monthly).
- The 8/40 AH3 filings without a distribution table are non-distribution current reports — legitimately skipped (log the count).
- Doc resolution: a 1-U's `primaryDocument` **is** the report `.htm` (`current_report.htm`) — no `index.json` lookup needed (that's only for 1-K). All date fields are `YYYY-MM-DD`.
