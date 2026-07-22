# RAW_SharePriceHistory

**Sheet:** `RAW_SharePriceHistory` — the Arrived Valuation / share-price series per offering, verbatim.
**Source:** `GET /offerings/{cid}/share-prices/history` → `data[]` (see `api-reference.md` Source 1).
**`source` tag:** `arrived:offerings/{cid}/share-prices/history`
**SCD type:** **Type 2** (series — append-only; do **not** expire on absence).
**Primary key (`nk`):** **(`offeringCid`, `postedAt`)** → `offeringCid|postedAt`
**Sort order:** `offeringCid`, then `postedAt` (both ascending; ISO timestamps sort as text).

## Columns (verbatim, in order)

| Column | Meaning |
|---|---|
| `uuid` | the record's id as returned. |
| `offeringCid` | offering id (part of the key). |
| `postedAt` | observation timestamp (part of the key). |
| `status` | invariably `SHARE_PRICE_UPDATED` — this endpoint is a **pure valuation series**, one record per Arrived Valuation update, **not** an event log. |
| `sharePrice` | the Arrived Valuation / share at that observation (the latest = current valuation). |
| `sharePriceEstimatedMin`, `sharePriceEstimatedMax` | the valuation range as returned. |

Then the **SCD2 bookkeeping columns** — see `api-reference.md` "SCD common".

## Notes
- A column showing only `SHARE_PRICE_UPDATED` is **correct and complete, not missing rows**. Timeline
  events (new tenant → `Lease Started`, re-signed → `Lease Renewed`, `Dividends Paused`, …) are **not**
  in this endpoint — they live in `RAW_PropertyHistory`.
- The latest `sharePrice` here is the authoritative "Current Arrived Valuation / Share" for the computed tab.
