# RAW_SEC_1U

**Output (CSV):** **one CSV per filing** — `RAW_SEC_1U/<filingDate>_<accession>.csv` (**1:1** with each extracted distribution 1-U; **never a combined file**). The **per-series distribution (dividend) declarations** from every **Form 1-U** (current report) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form. Complements the API dividend history and the computed tab's dividend-consistency column.
**Source:** each 1-U's report `.htm` (`current_report.htm`, sometimes `arrivedhomes3_1u.htm`). A distribution 1-U contains **one small table** with header `Series of {LLC} | Dividend Amount per Share`, one row per series. Non-distribution 1-Us (other current-report events) have no such table → they produce **no file**.
**`source` tag:** `sec:1-u-distributions`
**Load model:** **one immutable CSV per SEC filing (1:1).** Filings never change once filed, so there is **no SCD history and no bookkeeping columns**. Incremental: a re-run **skips any accession whose `RAW_SEC_1U/<filingDate>_<accession>.csv` already exists** and only fetches + writes new filings. Do **not** combine filings into one CSV — the 1:1 mapping is what keeps loads incremental and fast. `reportDate` = the distribution/event date.
**Within-file grain:** one row per `property` (series). `filingDate` / `accession` / `reportDate` are constant within a file (kept as columns so each CSV is self-describing and concatenable).
**Sort order (within file):** `property` (ascending).

## Extraction (fast — bulk same-origin fetch, no per-doc navigation)

1-U docs are small and same-origin (`www.sec.gov`). From **one** `www.sec.gov` browser tab you can `fetch()` the submissions JSON (`https://data.sec.gov/submissions/CIK{paddedCik}.json` — CORS-open) to list all `1-U`/`1-U/A` filings, then `fetch()` **every** filing's `.htm` in the same JS pass, `DOMParser` each, and pull the `Series | Dividend Amount per Share` table. (Verified 2026-07 across all four CIKs: **149 total 1-U filings, 119 with distribution tables → 119 CSVs, 11,091 rows** — AH3 alone = 41 filings, 33 with distribution tables. Only distribution 1-Us produce a CSV; each such filing → its own `RAW_SEC_1U/<filingDate>_<accession>.csv`.) See `api-reference.md` → "SEC filing extraction".

## Columns (tidy/long — already property/value shaped)

| Column | Meaning |
|---|---|
| `filingDate` | EDGAR filing date `YYYY-MM-DD` (**grain**). |
| `accession` | EDGAR accession (**grain**). |
| `reportDate` | the distribution/event date from the filing, as **`YYYY-MM-DD`**. |
| `property` | the series/property name (verbatim; join to holdings by `name`). |
| `dividend_amount_per_share` | the per-share distribution, `$`/spaces stripped (e.g. `0.051`). |

**One row per property per filing** — `property` and `value` (`dividend_amount_per_share`) are their own fields; do not pivot.

## Notes
- Enumerate parent LLCs `1821720` (Arrived Homes) / `1962723` (Arrived Homes 3) / `2015697` (Arrived Homes 4) / `2032732` (Arrived Homes 5); each has its own 1-U stream (roughly monthly).
- The 8 of 41 AH3 filings without a distribution table are non-distribution current reports — they produce no CSV (log the count).
- Doc resolution: a 1-U's `primaryDocument` **is** the report `.htm` (`current_report.htm`) — no `index.json` lookup needed (that's only for 1-K). All date fields are `YYYY-MM-DD`.
