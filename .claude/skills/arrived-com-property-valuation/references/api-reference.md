# Arrived API reference (shared)

Shared reference behind the skill's METHOD SUMMARY: the authenticated Arrived API endpoints, the
auth/token capture, derived-field formulas, the dividend-consistency computation, the property-page
scrape, the SEC sourcing, and the **common SCD mechanics** used by every `RAW_*` sheet. Each raw sheet
has its own file (`RAW_<Sheet>.md`) that states its **source, primary key, columns, SCD type, and sort
order**; this file holds everything cross-cutting. Endpoints/fields were **verified against a live
logged-in session** — treat as confirmed unless the app changes.

Per-sheet files: `RAW_Holdings.md`, `RAW_OfferingDetails.md`, `RAW_Dividends.md`,
`RAW_SharePriceHistory.md`, `RAW_PropertyHistory.md`, `RAW_SEC_1U.md`, `RAW_SEC_1K.md`,
`RAW_SEC_253G2.md`, `RAW_SEC_1SA.md` (plus **deprecated** `RAW_SECBalanceSheet.md` / `RAW_SECDividends.md`).

## Source 1 — Authenticated Arrived API: `https://abacus.arrivedhomes.com`

The arrived.com web app calls this JSON backend ("abacus") when logged in. Two auth modes:

- **Cookie/session auth** — most `GET /offerings/*` reads succeed with just the browser session
  (`fetch(url, { credentials: 'include' })`) from a logged-in arrived.com tab.
- **Bearer token** — account/portfolio endpoints (`/accounts/*`) return `401` without an
  `Authorization: Bearer …` header. The token is **in memory only** (not in local/sessionStorage).
  Capture it by monkey-patching `window.fetch` AND `XMLHttpRequest.prototype.setRequestHeader` on a
  logged-in tab and recording the `Authorization` value. **Never print or exfiltrate the token.**

**Getting the account id:** patching catches nothing until the app fires a request — navigate to
Portfolio, then click **POSITIONS / ACTIVITY**. The app calls e.g. `/sales?accountCid=bact_…`; read the
**`bact_…` account id** off the captured URL.

Key endpoints (verified):

| Endpoint | Returns | Feeds sheet |
|---|---|---|
| `GET /accounts/{bactId}/balance/offerings` | `data.offerings[]` — the investor's holdings | `RAW_Holdings` |
| `GET /offerings/{cid}` | `data` — full offering record | `RAW_OfferingDetails` |
| `GET /offerings/{cid}/dividends` | `data[]` — offering dividend history | `RAW_Dividends` |
| `GET /offerings/{cid}/share-prices/history` | `data[]` — valuation/share-price series | `RAW_SharePriceHistory` |
| `GET /offerings/{cid}/documents` | `data[]` | the `SERIES_FINANCIALS` `fileUrl` opens only an EDGAR **search** page — **not** the filing; get the direct doc by scraping the property page (Source 3/4) |

**Nested objects on the holding** (`balance/offerings`) — flatten to scalars, do **not** land the
sub-objects whole:
- `rentalIncome` is a **nested object, not a scalar**: `{ totalDividendsPaid, annualizedDividendPercent,
  latestDividend{…}, allDividends[] }`. The cumulative "Total Dividends Received" figure is
  **`rentalIncome.totalDividendsPaid`**; drop the `allDividends[]` array (it balloons the payload).
- `interest` is **also nested**: `{ interestAccrued, interestPaid, totalExpectedInterest,
  annualizedInterestPercent }` — cash-reserve / other income.
- `appreciation` is nested: `{ totalAppreciation, totalRealized, allTimeAppreciationPercent }`.

**Selecting SFR rows (computed tab):** `offeringInvestmentProductType === 'SINGLE_FAMILY_RESIDENTIAL_IPO'`,
**both open (`currentSharesCount > 0`) and closed / fully-exited (`currentSharesCount === 0`)** — the
Portfolio Positions page's **OPEN POSITIONS** and **CLOSED POSITIONS** tabs. Exclude only the SFR *Fund*,
vacation rentals (`VACATION_RENTAL_IPO`), and private credit. **Open rows sort first by `ROI ($)` desc;
closed rows group below, also `ROI ($)` desc.** The `sell` checkbox renders **only on open rows** (0-share
rows can't be sold). A closed position can't use the per-share formulas (`currentInvestment / 0` divides by
zero and its current cost basis is `0`), so it uses a **realized** regime keyed on `initialInvestment` (see
the closed-position rows in Source 2). The **raw** `RAW_Holdings` sheet keeps the **full** unfiltered
response (all product types, open and closed).

⚠️ **Two different "change" numbers — keep separate:** property-level Arrived Valuation change =
`(sharePrice − 10) / 10` (from the fixed **$10 issue price**, used inside `ROI at Current Valuation`);
your personal cost basis = `currentInvestment ÷ currentSharesCount` (never a hardcoded 10 —
secondary-market / DRIP / staggered buys differ).

## Source 2 — Derived / computed fields (feed the computed month tab; see SKILL.md for the column map)

| Field | Formula | Notes |
|---|---|---|
| IPO (issue) Price/Share | `targetRaiseAmount / totalShares` | = **$10.00** for every SFR offering — the ROI baseline, not your cost. |
| Current Arrived Valuation / Share | latest `/offerings/{cid}/share-prices/history` (≈ `offeringSharePrice`) | current share price = Arrived Valuation/share; lives only on arrived.com. |
| Avg Cost / Share | `currentInvestment / currentSharesCount` | your blended purchase price per share (held positions only). |
| Property Valuation Change % | `(sharePrice − 10) / 10` | property-level, from the $10 issue price; used inside `ROI at Current Valuation`. |
| Current Rent | `properties[0].rent × 12` | current monthly contract rent × 12 (the latest/current figure). |
| Current Expenses | `CurrentRent − (projectedAnnualDividendYield × EquityRaised)` | reproduces the property page's FINANCIALS "Expenses" (The Cove: 20,940 − 0.044×246,930 = **$10,075**). |
| Annual Cash Flow | `CurrentRent − CurrentExpenses` | sheet formula. |
| Equity Raised | `targetRaiseAmount` | = `totalShares × $10`. |
| **ROI ($)** — open | `(TotalDividendsReceived + CurrentArrivedValuationPerShare × currentSharesCount) − (AvgCostPerShare × currentSharesCount)` | **net dollar gain** — total value (dividends + current share value) minus your cost basis (`AvgCostPerShare × currentSharesCount = currentInvestment`); **can be negative**. The old standalone **`Value`** column was removed and its formula **inlined here**. `currentSharesCount` baked into each row's formula as a literal. |
| **Dividend ROI (%)** — open | `TotalDividendsReceived ÷ (AvgCostPerShare × currentSharesCount)` | **dividends-only** return as a fraction of cost basis; percent (2 dp). |
| **ROI (%)** — open | `ROI ($) ÷ (AvgCostPerShare × currentSharesCount)` | the **total** net gain as a fraction of your cost basis; percent (2 dp). |
| **ROI ($)** — closed | `TotalDividendsReceived + appreciation.totalRealized` | **realized** net dollar result for a fully-exited (0-share) position: cumulative dividends plus the realized gain/loss booked at sale. Baked per row as `=H<r>+(<totalRealized>)`. |
| **Dividend ROI (%)** — closed | `TotalDividendsReceived ÷ initialInvestment` | closed positions have no current cost basis, so use **`initialInvestment`** (original pre-sale amount); percent (2 dp). |
| **ROI (%)** — closed | `ROI ($) ÷ initialInvestment` | realized total return over the original amount invested; percent (2 dp). |
| **buy / sell** | — (human-entered) | two **boolean checkbox** columns (sheet columns **A** & **B**, left of everything) filled in by hand. **They persist across refreshes:** the run reads the prior tab's values by Property and restores them (default `FALSE` for a newly-seen property); never blanked. Not derived from any source. **`buy` on every row; `sell` on open rows only** (`currentSharesCount > 0`) — closed rows get no `sell` checkbox. |

## Source 2b — Dividend-payment consistency (trailing 12 months) — computed column F

Track-record metric: of the months a property *could* have paid, how many did it. **Data:**
`/offerings/{cid}/dividends` (also landed raw in `RAW_Dividends`).
- **Y = `min(12, whole calendar months since ipoDate)`** (`ipoDate` from `/offerings/{cid}`).
- **X = distinct calendar months, within the most recent Y complete months, covered by a dividend
  period (`startDate`→`endDate`) with `dividendPerShare > 0`.** A quarterly period covers its 3 months;
  count each once. Never paid → 0.
- Output text `"X / Y"`, forced to text (leading `'`) so `5 / 12` isn't read as a date/division.
- Caveat: it counts *months covered*; a healthy quarterly payer still reads near `12/12`.

## Source 3 — Property page + scraping

- Property detail page (**logged-in app route**) `https://arrived.com/app/properties/{nameSlug}` —
  `nameSlug` = the offering **`name`** lowercased with spaces → hyphens (`The Hedgecrest` →
  `the-hedgecrest`). This is what the computed tab's **Property** HYPERLINK (column C) must use, and the
  page to open for the property-page scrapes below. ⚠️ The **old** public `https://arrived.com/properties/{address-slug}`
  (built from `properties[0].slug`) is **dead** — Arrived retired those pages and they now redirect to the
  `/app/properties` browse page (verified 2026-07). Keep landing `properties[0].slug` in the raw sheets as
  data, but never build a live link from it.
- **Tenant Status** (computed column **U**) comes from **`properties[0].leaseStatus`** on
  `GET /offerings/{cid}` (landed in `RAW_OfferingDetails.property_leaseStatus`) — the field the Positions
  page renders as **RENTAL STATUS**. Title-case the enum: `OCCUPIED` → `Occupied`, `VACANT` → `Vacant`,
  else Title-Case the token. It is **not** derived from the Property-History timeline any more (the old
  `new`/`renewed`/`current` buckets tracked lease *age*, not occupancy, and mislabeled current holdings).
- **Property History timeline** (feeds `RAW_PropertyHistory` — raw landing only; **no longer** Tenant
  Status): Performance tab → **"View Full Property Timeline"** opens a fully-rendered modal (not
  virtualized) — one `innerText` read captures every event. No history API exists. Event types: `Initial Public Offering`, `Market
  Preparation`, `Marketed for Rent`, `Approved Application`, `Lease Started`, `Lease Renewed`, `Lease
  Completed`, `Marketing Rent Changed`, `Arrived Valuation Updated`, `Dividends Paid`, `Dividends
  Paused`. Each = `eventType` + `MM/DD/YYYY` + a `detail` line. Click with a real click, then read in a
  short synchronous call — long async loops freeze the renderer.
- **SEC offering-circular link** (feeds the computed tab's **column T** only — there is **no** raw
  filing-URL sheet): scrape `a[href*="sec.gov/Archives/edgar"]` from the Documents section. The URL is
  identical for every property sharing a `dropId` — scrape one property per distinct `dropId` and map
  `dropId → URL`, then write it into column T for that drop's properties.

## Source 4 — SEC EDGAR: `https://www.sec.gov/Archives/edgar/data/{CIK}/{accession}/{file}.htm`

Public, no login. Reg A series LLCs — **no quarterly (10-Q) report**. Filing types that matter:
- **1-A POS / offering circular** (e.g. `arrived3-1apos4.htm`) — the offering doc. Confirms the $10
  issue price, and **deep inside (page F-1+)** carries the **UNAUDITED COMBINED PRO FORMA BALANCE
  SHEET** per series → feeds `RAW_SEC_253G2`. The balance sheet is past WebFetch's truncation, so
  extract it via the browser: load the `.htm`, find `PRO FORMA BALANCE SHEET` in `document.body.innerText`,
  slice the section.
- **Annual 1-K** (audited) / **semiannual 1-SA** (unaudited) — per-series financial reports. Kept only as
  a **fallback source for the current mortgage** (column P): the `Loan payable, net` balance-sheet line
  (Item 3, page F-1+, usually past WebFetch truncation). The 1-SA is a single fetchable `.htm`; the 1-K is
  one ~14 MB `.htm` — fetch in sections. (Income statements are **no longer landed** as a raw sheet.)
- **1-U current report** (e.g. `current_report.htm`) — event-driven; carries per-series **dividend
  declarations** with declaration / record / payment dates → feeds `RAW_SEC_1U`.

Verified parent series-LLCs / CIKs (the four in scope): `1821720` = **Arrived Homes, LLC**, `1962723` =
**Arrived Homes 3, LLC**, `2015697` = **Arrived Homes 4, LLC**, `2032732` = **Arrived Homes 5, LLC**.
Example latest-1-SA accessions: `1821720` → `0001213900-25-092406`; `1962723` → `0001213900-25-091696`;
`2032732` → `0001213900-25-092122`.

**Filing INDEX via the submissions API (feeds `RAW_SEC_1U` / `RAW_SEC_1K` / `RAW_SEC_253G2` /
`RAW_SEC_1SA` — the full filing history):** `GET https://data.sec.gov/submissions/CIK{paddedCik}.json`
(CIK zero-padded to 10 digits, e.g. `CIK0001962723`). `filings.recent` holds **index-aligned parallel
arrays** — `form[]`, `filingDate[]`, `reportDate[]`, `accessionNumber[]`, `primaryDocument[]`,
`primaryDocDescription[]` — read them by the **same index** so fields stay aligned. Bucket every filing
whose **base** form (strip any `/A`) is `1-U` / `1-K` / `253G2` / `1-SA` into that form's sheet, keeping
the exact `form` string (amendments included). Build the direct doc URL as
`https://www.sec.gov/Archives/edgar/data/{cikNoPad}/{accessionNoDashes}/{primaryDocument}`. If
`filings.files[]` is non-empty it lists overflow pages of **older** filings to fetch too (currently empty
for these CIKs → `recent` is the complete history). Enumerate the CIKs to pull from the holdings' offering
circulars, so the index covers **every parent LLC the portfolio touches**. ⚠️ **Read this JSON in the
browser on a `data.sec.gov` tab and parse the arrays exactly — WebFetch mis-aligns and under-counts them
(observed 54 vs the true 40 on one form).** Each sheet is SCD2 append-only, `nk = cik|filingDate|accession`
(see `references/RAW_SEC_*.md`).

**Mortgage / financing:** Initial Mortgage = API `debtAmount` (`0` = all-cash). Current Mortgage =
arrived.com current financials, or the SEC `Loan payable, net` / `Mortgage payable` line, or an
amortization estimate (label estimates as estimates).

## Source 5 — Valuations methodology

SFR valuations use a **comparable-sales** method, updated **quarterly, starting 12 months after IPO**
(so recently-IPO'd properties sit at $10.00 / 0%). Share price = the Arrived Valuation per share.
Help article: https://help.arrived.com/en/articles/6909386-how-do-we-calculate-arrived-valuations

---

# SCD common mechanics (used by every `RAW_*` sheet)

The raw layer lands **every value exactly as returned** — no ROI, no `rent × 12`, no currency
reformatting; the only added columns are the SCD bookkeeping columns. **Flatten** nested JSON paths
into columns (`market.title` → `market_title`), and **force text** (leading `'`) on date-like/ratio-like
strings so Sheets doesn't coerce them.

**Two SCD flavours are used** (each sheet states which):
- **SCD Type 2** (most sheets) — full row history. A changed value **expires** the old current row
  (`valid_to`, `is_current=FALSE`) and **appends** a new version row. One `is_current=TRUE` row per key.
- **SCD Type 3** (legacy — only the now-**deprecated** `RAW_SECDividends` used it; **no active sheet does**):
  limited history in-row — keep the **current** value plus the **previous** in adjacent columns, with an
  effective date. On change, shift current → previous and write the new current.

**SCD2 bookkeeping columns** (appended after the raw columns, in this order):

| Column | Meaning |
|---|---|
| `nk` | **natural key** (the sheet's primary key spelled out with `\|` between parts). Row identity = (`nk`, `valid_from`); no synthetic surrogate. |
| `source` | lineage tag, constant per sheet (each `RAW_*.md` gives its value). |
| `row_hash` | djb2 hash of the raw columns only (bookkeeping excluded). Stored as text. |
| `loaded_at` | run timestamp (`new Date().toISOString()`), taken **once** per run and reused. |
| `valid_from` | effective-from = the `loaded_at` that first observed this version. |
| `valid_to` | effective-to = the `loaded_at` that superseded it; blank while current. |
| `is_current` | `TRUE` for the live version, `FALSE` once superseded. |

**SCD3 bookkeeping columns** (legacy `RAW_SECDividends` only — **deprecated**): the raw columns are split into `current_*` /
`previous_*` pairs, plus `nk`, `source`, `effective_date` (when `current_*` took effect),
`previous_effective_date`, `loaded_at`.

`row_hash` (djb2):
```js
const rowHash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(16); };
const h = rowHash(RAW_COLS.map(c => rec[c] ?? '').join('|'));   // RAW_COLS in the sheet's fixed order
```

**Load algorithm — per sheet, every run — read → diff → expire → append → sort:**
1. **Read** the existing tab via the Drive API (`read_file_content`). Missing → first load: create tab,
   header row, then every fresh record as an initial version (`is_current=TRUE`, `valid_from=loaded_at`).
2. Build `currentByKey` from `is_current=TRUE` rows: `nk → { row_hash, sheet_row_index }`.
3. Per fresh record: **new key** → append; **unchanged `row_hash`** → no-op; **changed** → expire old
   (`valid_to=loaded_at`, `is_current=FALSE`) + append new version.
4. **Disappeared keys:** on **dimension** sheets (`RAW_Holdings`, `RAW_OfferingDetails`)
   expire. On **event/series/periodic** sheets (`RAW_Dividends`, `RAW_SharePriceHistory`,
   `RAW_PropertyHistory`, `RAW_SEC_1U`, `RAW_SEC_1K`, `RAW_SEC_253G2`,
   `RAW_SEC_1SA`) do **not** expire on absence — append-only in practice.
5. **Write:** appends → paste at first empty row; expirations → edit `valid_to` + `is_current` in place.
6. **Header:** on first creation, bold, wrap, freeze row 1.
7. **Sort (final step):** sort the data rows (below the frozen header) by the sheet's **sort order**
   (each `RAW_*.md` gives it). Re-sorting each run is safe because step 1 re-reads positions.
   `loaded_at` / `startDate` / `postedAt` / `eventDate` are all **`YYYY-MM-DD`** (or ISO timestamps) and
   sort correctly as text.

**Idempotency:** because change detection is by `row_hash`, a re-run with no upstream change stages zero
appends and zero expirations.

---

## SEC filing extraction (Source 4 — the four `RAW_SEC_*` content sheets)

The `RAW_SEC_1U / 1K / 253G2 / 1SA` sheets hold the **financial-table CONTENT** of Arrived's Reg A
filings in **tidy/long** form — one row per table cell, with **`property`** (series name) and **`value`**
as their own fields. **Never pivot on property** (no one-column-per-series layout). Each sheet's exact
columns are in its `RAW_SEC_<form>.md`.

**1. Discover filings.** For each parent series-LLC CIK (`1821720` Arrived Homes, `1962723` Arrived
Homes 3, `2015697` Arrived Homes 4, `2032732` Arrived Homes 5), read the **submissions API**
`https://data.sec.gov/submissions/CIK{paddedCik}.json` → `filings.recent`, and bucket by base form
(`1-U`, `1-K`, `253G2`, `1-SA`; include `/A`). The browse UI `https://www.sec.gov/edgar/browse/?CIK={cik}`
is the human entry point. **Skip any `accession` (or `filingDate`) already in the target sheet** —
incremental, full history.

**2. Get each filing's report `.htm`.** 1-SA / 1-U / 253G2: `primaryDocument` **is** the report `.htm`
(e.g. `ea…-1sa_arrived.htm`, `current_report.htm`, `…_253g2.htm`) — build `…/{accNoDashes}/{primaryDocument}`.
**1-K: `primaryDocument` is only the XBRL cover** (`xsl1-K_X01/primary_doc.xml`, `isXBRL:0`), NOT the report.
Resolve the real doc from the accession index JSON: fetch
`https://www.sec.gov/Archives/edgar/data/{cikInt}/{accNoDashes}/index.json` → `directory.item[]`
(each has `name`,`size`; ignore `type` — it's just an icon label) and take the **largest `.htm`** (its name
contains `1k`; the cover/index stubs are ~0–1.6 KB). **WebFetch truncates these multi-MB docs — use the browser
or a raw `fetch()`** (they're static HTML; no headless browser needed).

**3. Bulk same-origin fetch (fast path — no per-doc navigation).** From ONE `www.sec.gov` tab you can
`fetch()` the submissions JSON (data.sec.gov is CORS-open) **and** every filing `.htm` (same origin) in a
single JS pass, `DOMParser` each, and extract. Validated on 1-U: 40 docs → 2,438 rows in one call. For the
huge 1-K/1-SA docs, fetch/parse a few at a time to avoid freezing the tab (large in-page state + long
loops freeze the renderer).

**4. Parse the tables (the coalescing engine).** SEC HTML splits each figure across cells
(`$` | number | `)`) and the **header row uses a different cell count than the data rows**, so
cell-index alignment fails. Map by **ORDER**: the *Nth numeric token in a row → the Nth series*.
Negatives from a leading `(` or a trailing `)` cell; `-`/blank → `0`; strip `$` and commas. Detect tables
content-driven by title (`balance sheet`, `comprehensive`/`operations`, `changes in member`, `cash flow`)
and by per-series note-schedule headers/title-rows; a page's final `Consolidated` column is the roll-up.
1-U is trivial: the `Series | Dividend Amount per Share` table, one row per series.
**Use `textContent`, not `innerText`, when reading cells/titles from a `DOMParser` doc** — `innerText`
needs layout and returns empty on a detached document; `norm()` already collapses whitespace so the two are
equivalent for token parsing. (`innerText` is only needed if you run the engine against the *live*
`document` after navigating to the doc.)

**Comparative (multi-year) statements.** Later 1-K/1-SA filings print the current period **and** a
comparative prior period side by side (e.g. a 2025 1-K balance sheet carries both `DECEMBER 31, 2024` and
`DECEMBER 31, 2023` series blocks). The engine tags each block with its own `period`, so **the grain must
include `period`** — never collapse a filing to one period. 1-SA interim balance sheets legitimately print
the current interim period (e.g. `JUNE 30, 2025`) **without** a `Consolidated` column; only the comparative
year-end block has one. Do not treat a missing `Consolidated` column as a parse failure.

**5. Land tidy.** Emit one row per (filing, statement, period, line_item, property)=value. SCD2,
append-only, `filingDate`+`accession` in the grain (`RAW_SEC_*.md` gives each schema).
**All date fields — `filingDate`, `reportDate`, and `period` whenever it holds a date — must be emitted as
`YYYY-MM-DD`** (parse the printed `MONTH D, YYYY` → ISO, e.g. `DECEMBER 31, 2025` → `2025-12-31`) so the
sheet columns land as true Date type.

**Known cross-entity engine gaps (harden in the standalone extractor).** The heuristic engine was tuned on
AH3 (`1962723`) and reconciles to the dollar there, but testing on the larger AH (`1821720`, ~249 series)
exposed three: (1) picking series columns by a **text filter** drops legitimate headers like `Unallocated
members' capital` and desyncs the order-token mapping — map columns by **position** (cell index / colspan)
instead; (2) **continuation pages** of a 30+-page statement that don't repeat the title get skipped (~0.6%
of series dropped) — classify a continuation by the presence of known series columns, not title proximity;
(3) **entity-specific titles** vary (`OPERATIONAL EXPENSES` vs `Operating Expenses`, the misspelled `CASH &
CASH EQUIVILENTS`, `RECENT OPERATIONAL EXPENSES` for the stub) — match schedules fuzzily. Lock it down with
the per-`(filingDate, period)` reconciliation as a **golden test across all four CIKs**, not just AH3.
**Drop unclassifiable rows:** a row-schedule table the engine can't name yields rows with a **blank
`statement` AND blank `line_item`** (period polluted with stray labels like `Depreciation`). These are
garbage (they partly duplicate named statements, partly are unlabeled interim "Recent Developments"
figures) — **filter out every row whose `statement` is empty** before landing.

**6. Verify.** Per data row, numeric-token-count == series-count (0 mismatches = clean). Cross-check
`Consolidated == sum(series)` **grouped by `(filingDate, period)`** — every period that has a `Consolidated`
column must tie to the dollar (±$1–2 rounding). Also confirm the **same period's figure matches across
independent filings** (e.g. `Dec 31, 2024` P&E net = 25,742,292 appears identically in the 2025 & 2026 1-K
and the 2025 1-SA) — strong cross-filing consistency. Confirm 0 empty `property`/`value` and 0 non-numeric
`value`.

**✅ Landing path that works: browser download → device bridge (no clipboard).** The cloud sandbox's egress
allowlist blocks `*.sec.gov`, and `device_bash`/the Mac VM have no network, so **only the connected Chrome
extension can reach the filings.** Clipboard writes are unreliable (need Chrome frontmost + active tab) and
multi-MB writes hang the renderer — **do not depend on clipboard.** Instead: after the in-page `fetch`+parse,
build the tidy CSV string in the page and trigger a **Blob download** (`a.download`; needs no focus, no
size-limited tool return) to `~/Downloads`. Then grant Downloads (`device_request_folder_access`) and pull
it into the cloud. **The device bridge times out on ~13 MB files — `gzip` on the Mac first** (CSV compresses
~20:1 → a few hundred KB), `device_stage_files` the `.gz`, `gunzip` + validate in the cloud, then
`SendUserFile` clean CSVs for the user to import (File → Import → Replace current sheet). One combined
download split by the `form` column in the cloud avoids Chrome's multi-file prompt.
