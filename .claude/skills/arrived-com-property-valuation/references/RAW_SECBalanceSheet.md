# RAW_SECBalanceSheet

> ⚠️ **DEPRECATED — do not use.** Superseded by the tidy SEC sheets: the offering-circular pro-forma balance
> sheet now lands in **`RAW_SEC_253G2`**, and the audited balance sheets in **`RAW_SEC_1K`** / **`RAW_SEC_1SA`**
> (tidy/long — `property` + `value` fields, `YYYY-MM-DD` dates, four parent CIKs `1821720`/`1962723`/`2015697`/`2032732`).
> Kept for historical reference only. See `RAW_SEC_253G2.md`, `RAW_SEC_1K.md`, `RAW_SEC_1SA.md`.

**Sheet:** `RAW_SECBalanceSheet` — per-series **assets & liabilities** (the housing data) from the offering circular's **UNAUDITED COMBINED PRO FORMA BALANCE SHEET**, long/tidy.
**Source:** the **1-A POS / offering circular** `.htm` (e.g. `https://www.sec.gov/Archives/edgar/data/1962723/000196272323000030/arrived3-1apos4.htm`), section **"UNAUDITED COMBINED PRO FORMA BALANCE SHEET"** — see `api-reference.md` Source 4. **No API.** The section is deep (page F-1+) and **past WebFetch's truncation**, so extract it via the browser: load the `.htm`, find `PRO FORMA BALANCE SHEET` in `document.body.innerText`, and slice the per-series columns.
**`source` tag:** `sec:pro-forma-balance-sheet`
**SCD type:** **Type 2** (periodic snapshot — append-only; do **not** expire on absence). A restated/re-filed balance sheet for the same `(series, as_of_date)` supersedes via a new version.
**Primary key (`nk`):** **(`cik`, `series_name`, `as_of_date`, `section`, `line_item`)** → `cik|series_name|as_of_date|section|line_item`
**Sort order:** `cik`, then `series_name`, then `as_of_date`, then `section`, then `line_item` (ascending).

## Columns (verbatim, long/tidy — one row per line item, in order)

| Column | Meaning |
|---|---|
| `parent_entity` | e.g. `Arrived Homes 3, LLC`. |
| `cik` | parent-LLC CIK (part of the key). |
| `accession` | offering-circular accession the balance sheet came from. |
| `as_of_date` | the balance-sheet date printed under the title (e.g. `January 10, 2023`; part of the key). |
| `series_name` | verbatim series label (e.g. `Sheezy`, `Cordero` — the column header in the schedule; part of the key). |
| `section` | `Assets` \| `Liabilities` \| `Equity` (part of the key). |
| `line_item` | verbatim label (part of the key) — see the verified list below. |
| `value` | the figure as reported (parentheses = negative). |
| `offeringCid` | join to the held offering by matching `series_name` → property `name`; blank if unmatched. |

Then the **SCD2 bookkeeping columns** — see `api-reference.md` "SCD common".

## Verified line items (Arrived Homes 3, arrived3-1apos4.htm, as of Jan 10 2023)

- **Assets** — `Cash and cash equivalents`, `Prepaid expenses`, `Deferred costs`, `Due from related
  party`, `Total current assets`, **`Property and equipment, net`** (the housing value), `Deposits`,
  `Total assets`.
- **Liabilities** — `Accrued expenses`, `Due to related party`, `Distribution payable`, `Total current
  liabilities`, `Tenant deposits`, **`Loan payable, net`** (the mortgage; `$-` = all-cash), `Total
  liabilities`.
- **Equity** — `Membership contributions`, `Retained earnings (accumulated deficit)`, `Total members'
  equity`, `Total liabilities and members' equity`.

Capture whatever labels the filing prints, verbatim — labels vary slightly by drop/vintage.

## Notes
- The schedule is **per series** (one column per series, many series per drop), as of the offering
  date — so one offering circular yields many series' balance sheets in one fetch.
- This is the "all the housing data (assets and liabilities)" capture — the balance-sheet layer of the SEC
  filings (per-series income-statement figures are not landed in any raw sheet).
