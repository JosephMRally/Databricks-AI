# RAW_Dividends

**Sheet:** `RAW_Dividends` — the offering's dividend history from the Arrived API, verbatim.
**Source:** `GET /offerings/{cid}/dividends` → `data[]` (see `api-reference.md` Source 1).
**`source` tag:** `arrived:offerings/{cid}/dividends`
**SCD type:** **Type 2** (event/series — append-only; do **not** expire on absence).
**Primary key (`nk`):** **(`offeringCid`, `startDate`, `endDate`)** → `offeringCid|startDate|endDate`
**Sort order:** `offeringCid`, then `startDate` (both ascending; ISO dates sort as text).

## Columns (verbatim, in order)

| Column | Meaning |
|---|---|
| `offeringCid` | offering id (part of the key). |
| `startDate` | dividend period start, **`YYYY-MM-DD`** (part of the key). |
| `endDate` | dividend period end, **`YYYY-MM-DD`** (part of the key). |
| `dividendPerShare` | per-share distribution for the period. |
| `postedAt` | when the distribution was posted, **`YYYY-MM-DD`**. |

Then the **SCD2 bookkeeping columns** — see `api-reference.md` "SCD common".

## Notes
- Cadence shifts over time (early records quarterly, later monthly) — a period can cover 1 or 3 months.
- This is the authoritative **per-property dividend history** and the source for the computed tab's
  Dividend Consistency (TTM). Distinct from the SEC-sourced **`RAW_SEC_1U`** (per-series 1-U distributions; the old `RAW_SECDividends` is deprecated).
