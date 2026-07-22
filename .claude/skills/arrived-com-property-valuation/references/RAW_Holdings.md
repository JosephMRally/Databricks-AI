# RAW_Holdings

**Sheet:** `RAW_Holdings` — the investor's holdings, verbatim (all product types, including sold-out and non-SFR).
**Source:** `GET /accounts/{bactId}/balance/offerings` → `data.offerings[]` (bearer-token auth — see `api-reference.md` Source 1).
**`source` tag:** `arrived:balance/offerings`
**SCD type:** **Type 2** (dimension — expire on disappearance).
**Primary key (`nk`):** **`offeringCid`**
**Sort order:** `name`, then `loaded_at` (both ascending).

## Columns (verbatim, flattened, in order)

| Column | Meaning |
|---|---|
| `name` | property/offering name (e.g. `The Cordero`). |
| `marketName` | market string (e.g. `Albuquerque, NM`). |
| `offeringCid` | offering id `offr_…` — **the primary key**. |
| `offeringInvestmentProductType` | `SINGLE_FAMILY_RESIDENTIAL_IPO` \| `VACATION_RENTAL_IPO` \| `SINGLE_FAMILY_RESIDENTIAL_FUND` \| `PRIVATE_CREDIT_FUND`. |
| `offeringSharePrice` | **current** per-share valuation despite the `offering-` prefix (e.g. `10.17`) — Arrived's verbatim name, kept as-is. |
| `currentSharesCount` | shares held now (`0` = sold out). |
| `currentInvestment` | your cost basis. |
| `initialInvestment` | original amount, pre-sale. |
| `ownershipStartDate` | date your ownership began, emitted **`YYYY-MM-DD`** (date-only, from the API ISO timestamp) → the computed tab's Purchase Date. |
| `rentalIncome_totalDividendsPaid` | flattened from the **nested** `rentalIncome` object (not a bare scalar). |
| `rentalIncome_annualizedDividendPercent` | flattened from `rentalIncome`. |
| `interest_interestPaid`, `interest_annualizedInterestPercent` | flattened from the **nested** `interest` object (land other `interest_*` scalars too if present). |
| `appreciation_allTimeAppreciationPercent` | flattened from `appreciation` (+ any other `appreciation.*` as `appreciation_<k>`). |

Then the **SCD2 bookkeeping columns** (`nk`, `source`, `row_hash`, `loaded_at`, `valid_from`, `valid_to`, `is_current`) — see `api-reference.md` "SCD common".

## Notes
- Join key to every other sheet is `offeringCid`.
- `rentalIncome` / `interest` / `appreciation` are nested objects — flatten to the scalars above; never land the whole object or the `allDividends[]` array.
- **The computed tab now includes both open (`currentSharesCount > 0`) and closed / fully-exited
  (`currentSharesCount === 0`) SFR positions.** `currentSharesCount` gates the computed tab's `sell`
  checkbox (open rows only) and picks the ROI regime: open rows use `currentInvestment`-based per-share
  formulas; closed rows use `initialInvestment` (cost basis) with `appreciation_totalRealized` (realized
  gain/loss) for a realized ROI. Both `initialInvestment` and `appreciation_totalRealized` are already
  landed here, so closed positions need no extra source.
