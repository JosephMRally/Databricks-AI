# RAW_OfferingDetails

**Output (CSV):** `RAW_OfferingDetails.csv` — the full offering record per offering, verbatim. Landed as a **CSV file** (not a Google-Sheet tab); still **SCD Type 2** — the CSV holds the full append-only history with the SCD bookkeeping columns (`api-reference.md` "SCD common": read the existing CSV → diff → expire → append).
**Source:** `GET /offerings/{cid}` → `data` (cookie/session auth usually suffices — see `api-reference.md` Source 1).
**`source` tag:** `arrived:offerings/{cid}`
**SCD type:** **Type 2** (dimension — expire on disappearance).
**Primary key (`nk`):** **`offeringCid`**
**Sort order:** `property_slug`, then `loaded_at` (both ascending).

## Columns (verbatim, flattened, in order)

| Column | Meaning |
|---|---|
| `offeringCid` | offering id — **the primary key**. |
| `market_title` | flattened from `market.title`. |
| `sharePrice` | current valuation/share (same current figure as `RAW_Holdings.offeringSharePrice`, different Arrived name). |
| `ipoDate` | offering IPO date, **`YYYY-MM-DD`** (drives dividend-consistency Y). |
| `targetRaiseAmount` | equity raised (= `totalShares × $10`). |
| `totalShares` | share count. |
| `dropId` | the "drop" this offering belongs to (properties sharing a drop share one SEC offering circular). |
| `projectedAnnualDividendYield` | pro-forma yield (feeds Current Expenses). |
| `debtAmount` | initial mortgage principal (`0` = all-cash). |
| `debtPercent`, `debtInterestPercent` | financing terms. |
| `property_slug` | flattened `properties[0].slug` (full address-based slug). |
| `property_rent` | monthly contract rent. |
| `property_leaseStatus` | current lease/occupancy enum (e.g. `OCCUPIED`, `VACANT`). **The authoritative source for the computed tab's Tenant Status (column U)** — Title-Cased (`OCCUPIED` → `Occupied`); it's what the Positions page shows as RENTAL STATUS. |
| `property_leaseStartAt`, `property_leaseEndAt`, `property_desiredLeaseLengthMonths` | lease term fields (supporting detail); the two date fields as **`YYYY-MM-DD`**. |

Then the **SCD2 bookkeeping columns** — see `api-reference.md` "SCD common".

## Notes
- `dropId` groups properties that share one SEC offering circular (one qualification per drop); its URL is scraped into the computed tab's column T.
- **`property_leaseStatus` feeds the computed tab's Tenant Status (column U)** — not the Property-History
  timeline. Map the enum to Title Case; every current holding presently reads `OCCUPIED` → `Occupied`.
