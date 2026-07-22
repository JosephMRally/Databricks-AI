# RAW_SECDividends

> ⚠️ **DEPRECATED — do not use.** Superseded by **`RAW_SEC_1U`** (per-series 1-U distributions, tidy/long,
> SCD2, `YYYY-MM-DD` dates, four parent CIKs `1821720`/`1962723`/`2015697`/`2032732`). Kept for historical
> reference only. See `RAW_SEC_1U.md`.

**Sheet:** `RAW_SECDividends` — per-series **dividend/distribution declarations** from the SEC **Form 1-U current report**, tracked **SCD Type 3** (current + previous in-row).
**Source:** the parent series-LLC's **1-U** `current_report.htm` (e.g. `https://www.sec.gov/Archives/edgar/data/1962723/000196272326000015/current_report.htm`) — see `api-reference.md` Source 4. WebFetch extracts the full per-series table cleanly. **No API for the SEC copy** (the API dividend history is the separate `RAW_Dividends` sheet).
**`source` tag:** `sec:1-u-dividends`
**SCD type:** **Type 3** — one row per series holding the **current** declaration and the **previous** one in adjacent columns; on a new 1-U, shift `current_* → previous_*` and write the new `current_*` (the row is updated in place, never multiplied).
**Primary key (`nk`):** **(`cik`, `series_name`)** → `cik|series_name`
**Sort order:** `cik`, then `series_name` (ascending).

## Columns (in order)

| Column | Meaning |
|---|---|
| `parent_entity` | e.g. `Arrived Homes 3, LLC`. |
| `cik` | parent-LLC CIK (part of the key). |
| `series_name` | verbatim series label from the 1-U (e.g. `Cordero`; part of the key). |
| `offeringCid` | join to the held offering by matching `series_name` → property `name`; blank if unmatched. |
| `current_amount` | latest declared distribution **per membership interest / share** (e.g. `$0.026`). |
| `current_declaration_date` | latest declaration date (e.g. `June 23, 2026`). |
| `current_record_date` | latest record date. |
| `current_payment_date` | latest payment date. |
| `current_accession` | the 1-U accession the current values came from. |
| `previous_amount` | the prior declaration's per-share amount (blank until a second 1-U is seen). |
| `previous_declaration_date`, `previous_record_date`, `previous_payment_date` | the prior declaration's dates. |
| `previous_accession` | the 1-U accession the previous values came from. |

Then the **SCD3 bookkeeping columns** (`nk`, `source`, `effective_date` = when `current_*` took effect, `previous_effective_date`, `loaded_at`) — see `api-reference.md` "SCD common".

## SCD Type 3 update rule
On each run, for each series in the newest 1-U: if `current_declaration_date` differs from what's stored,
copy the stored `current_*` into `previous_*` (and `effective_date` → `previous_effective_date`), then
write the new declaration into `current_*` with `effective_date = loaded_at`. If unchanged → no-op.
(Type 3 keeps only current + previous by design; the **full** dividend history is `RAW_Dividends`.)

## Verified shape (Arrived Homes 3 1-U, accession 0001213900-26-000015)
Declaration June 23 2026 / record June 24 2026 / payment June 24 2026; per-series per-share amounts for
~88 series (e.g. `Cordero $0.026`, `Ethan $0.035`, `Bean $0.040`, `Hancock $0.123`). One 1-U = one
declaration date covering many series.
