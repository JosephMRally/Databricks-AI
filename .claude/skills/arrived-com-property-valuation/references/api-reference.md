# Arrived API reference (shared)

Shared reference behind the skill's METHOD SUMMARY: the authenticated Arrived API endpoints, the
auth/token capture, derived-field formulas, the dividend-consistency computation, the property-page
scrape, the SEC sourcing, and the **common SCD mechanics** used by the **five Arrived-API** `RAW_*` CSVs.
(The **four SEC forms** do **not** use SCD — they are **1:1 per filing**, `RAW_SEC_<form>/<filingDate>_<accession>.csv`,
one immutable CSV per filing; see each `RAW_SEC_*.md` and "SEC filing extraction" below.) Each raw source
has its own file (`RAW_<Sheet>.md`) that states its **source, grain, columns, load model, and sort
order**; this file holds everything cross-cutting. Endpoints/fields were **verified against a live
logged-in session** — treat as confirmed unless the app changes.

Per-source files: `RAW_Holdings.md`, `RAW_OfferingDetails.md`, `RAW_Dividends.md`,
`RAW_SharePriceHistory.md`, `RAW_PropertyHistory.md`, `RAW_SEC_1U.md`, `RAW_SEC_1K.md`,
`RAW_SEC_253G2.md`, `RAW_SEC_1SA.md`. Each lands to its own `RAW_<Sheet>.csv`.

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

| Endpoint | Returns | Feeds CSV |
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
the closed-position rows in Source 2). The **raw** `RAW_Holdings` CSV keeps the **full** unfiltered
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
  `/app/properties` browse page (verified 2026-07). Keep landing `properties[0].slug` in the raw CSVs as
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
  filing-URL CSV): scrape `a[href*="sec.gov/Archives/edgar"]` from the Documents section. The URL is
  identical for every property sharing a `dropId` — scrape one property per distinct `dropId` and map
  `dropId → URL`, then write it into column T for that drop's properties.

## Source 4 — SEC EDGAR: `https://www.sec.gov/Archives/edgar/data/{CIK}/{accession}/{file}.htm`

Public, no login. Reg A series LLCs — **no quarterly (10-Q) report**. Per-form **financial-content** raw
CSVs (`RAW_SEC_1U`, `RAW_SEC_1K`, `RAW_SEC_253G2`, `RAW_SEC_1SA`) — source doc, columns, grain, CIKs,
discovery, and doc resolution — are defined in their `RAW_SEC_*.md` files.

**Submissions API (shared):** `GET https://data.sec.gov/submissions/CIK{paddedCik}.json` — read
`filings.recent`'s **index-aligned parallel arrays** by the same index. If `filings.files[]` is non-empty,
fetch those overflow pages for older filings too. ⚠️ **Parse this JSON in the browser on a `data.sec.gov`
tab** — WebFetch mis-aligns the arrays.

**Mortgage / financing (computed tab):** Initial Mortgage = API `debtAmount` (`0` = all-cash). Current
Mortgage = arrived.com current financials, or the SEC `Loan payable, net` / `Mortgage payable` line, or an
amortization estimate (label estimates as estimates).

## Source 5 — Valuations methodology

SFR valuations use a **comparable-sales** method, updated **quarterly, starting 12 months after IPO**
(so recently-IPO'd properties sit at $10.00 / 0%). Share price = the Arrived Valuation per share.
Help article: https://help.arrived.com/en/articles/6909386-how-do-we-calculate-arrived-valuations

---

# SCD common mechanics (the five Arrived-API `RAW_*` CSVs)

This section applies to the **five Arrived-API sources** (`RAW_Holdings`, `RAW_OfferingDetails`,
`RAW_Dividends`, `RAW_SharePriceHistory`, `RAW_PropertyHistory`). The **four SEC forms are exempt** —
they are **1:1 per filing** (`RAW_SEC_<form>/<filingDate>_<accession>.csv`, immutable, no SCD, no bookkeeping columns;
re-runs skip accessions already on disk). Each Arrived-API source lands to its **own CSV file**
(`RAW_<Sheet>.csv`), not a Google-Sheet tab. The
raw layer lands **every value exactly as returned** — no ROI, no `rent × 12`, no currency
reformatting; the only added columns are the SCD bookkeeping columns. **Flatten** nested JSON paths
into columns (`market.title` → `market_title`). Write **RFC 4180** CSV: comma-separated, a header line
of column names, and any field containing a comma, double-quote, or newline wrapped in double-quotes
(embedded quotes doubled). Values are stored **literally** — no leading `'` text-guard is needed (that
was a Sheets-coercion workaround); keep date/ratio strings exactly as emitted (`YYYY-MM-DD`, etc.).

**SCD Type 2** is used by every active source — full row history. A changed value **expires** the old
current row (`valid_to`, `is_current=FALSE`) and **appends** a new version row. One `is_current=TRUE`
row per key.

**SCD2 bookkeeping columns** (appended after the raw columns, in this order):

| Column | Meaning |
|---|---|
| `nk` | **natural key** (the source's primary key spelled out with `\|` between parts). Row identity = (`nk`, `valid_from`); no synthetic surrogate. |
| `source` | lineage tag, constant per source (each `RAW_*.md` gives its value). |
| `row_hash` | djb2 hash of the raw columns only (bookkeeping excluded). Stored as text. |
| `loaded_at` | run timestamp (`new Date().toISOString()`), taken **once** per run and reused. |
| `valid_from` | effective-from = the `loaded_at` that first observed this version. |
| `valid_to` | effective-to = the `loaded_at` that superseded it; blank while current. |
| `is_current` | `TRUE` for the live version, `FALSE` once superseded. |

`row_hash` (djb2):
```js
const rowHash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(16); };
const h = rowHash(RAW_COLS.map(c => rec[c] ?? '').join('|'));   // RAW_COLS in the CSV's fixed order
```

**Load algorithm — per CSV, every run — read → diff → expire → append → sort:**
1. **Read** the existing `RAW_<Sheet>.csv`. Missing → first load: write the header line, then every fresh
   record as an initial version (`is_current=TRUE`, `valid_from=loaded_at`).
2. Parse the CSV and build `currentByKey` from `is_current=TRUE` rows: `nk → { row_hash, row_index }`.
3. Per fresh record: **new key** → append; **unchanged `row_hash`** → no-op; **changed** → expire old
   (`valid_to=loaded_at`, `is_current=FALSE`) + append new version.
4. **Disappeared keys:** on **dimension** sources (`RAW_Holdings`, `RAW_OfferingDetails`)
   expire. On **event/series** sources (`RAW_Dividends`, `RAW_SharePriceHistory`,
   `RAW_PropertyHistory`) do **not** expire on absence — append-only in practice. (The SEC forms are
   not in this algorithm at all — they are 1:1 per filing, see "SEC filing extraction".)
5. **Write:** apply the appends and the in-place `valid_to`/`is_current` edits to the parsed rows, then
   **rewrite the whole CSV** (header line + all data rows). A CSV has no cell-level edit — regenerate the
   file each run.
6. **Header:** the CSV's first line is the column names (raw columns then the SCD bookkeeping columns).
7. **Sort (final step):** before writing, sort the data rows by the source's **sort order** (each
   `RAW_*.md` gives it). `loaded_at` / `startDate` / `postedAt` / `eventDate` are all **`YYYY-MM-DD`**
   (or ISO timestamps) and sort correctly as text.

**Idempotency:** because change detection is by `row_hash`, a re-run with no upstream change stages zero
appends and zero expirations.

---

## SEC filing extraction — shared parsing engine

Per-form discovery, doc resolution, bulk fetch, columns, and verification live in
`RAW_SEC_1U.md`, `RAW_SEC_1K.md`, `RAW_SEC_253G2.md`, `RAW_SEC_1SA.md`. This section covers the **shared
HTML table engine** (1-K / 1-SA / 253G2) and the **landing path**.

**Output model — 1:1 per filing (no SCD).** Each SEC filing is extracted to its **own** CSV,
`RAW_SEC_<form>/<filingDate>_<accession>.csv` — never a combined per-form file. Filings are immutable, so there is
**no SCD history and no bookkeeping columns**; each CSV holds only the tidy rows for that one filing
(`filingDate`/`accession` — and `as_of_date` for 253G2 — are constant within the file, kept as columns so
each CSV is self-describing and concatenable). **Incremental + fast:** before fetching a filing's `.htm`,
check whether `RAW_SEC_<form>/<filingDate>_<accession>.csv` already exists and **skip it if so** — only new accessions
are fetched and written. Within a file, sort by the per-form order in its `RAW_SEC_*.md`.

**Parse the tables (order-token coalescing).** SEC HTML splits each figure across cells
(`$` | number | `)`) and the **header row uses a different cell count than the data rows**, so
cell-index alignment fails. Map by **ORDER**: the *Nth numeric token in a row → the Nth series*.
Negatives from a leading `(` or a trailing `)` cell; `-`/blank → `0`; strip `$` and commas. Detect tables
content-driven by title (`balance sheet`, `comprehensive`/`operations`, `changes in member`, `cash flow`)
and by per-series note-schedule headers/title-rows; a page's final `Consolidated` column is the roll-up.
**Use `textContent`, not `innerText`, when reading cells/titles from a `DOMParser` doc** — `innerText`
needs layout and returns empty on a detached document; `norm()` already collapses whitespace so the two are
equivalent for token parsing. (`innerText` is only needed if you run the engine against the *live*
`document` after navigating to the doc.)

**Known cross-entity engine gaps (harden in the standalone extractor).** The heuristic engine was tuned on
AH3 (`1962723`) and reconciles to the dollar there, but testing on the larger AH (`1821720`, ~249 series)
exposed three: (1) picking series columns by a **text filter** drops legitimate headers like `Unallocated
members' capital` and desyncs the order-token mapping — map columns by **position** (cell index / colspan)
instead; (2) **continuation pages** of a 30+-page statement that don't repeat the title get skipped (~0.6%
of series dropped) — classify a continuation by the presence of known series columns, not title proximity;
(3) **entity-specific titles** vary (`OPERATIONAL EXPENSES` vs `Operating Expenses`, the misspelled `CASH &
CASH EQUIVILENTS`, `RECENT OPERATIONAL EXPENSES` for the stub) — match schedules fuzzily. Lock it down with
the per-`(filingDate, period)` reconciliation as a **golden test across all four CIKs**, not just AH3.

**Landing path (browser download → device bridge — no clipboard).** The cloud sandbox's egress
allowlist blocks `*.sec.gov`, and `device_bash`/the Mac VM have no network, so **only the connected Chrome
extension can reach the filings.** Clipboard writes are unreliable (need Chrome frontmost + active tab) and
multi-MB writes hang the renderer — **do not depend on clipboard.** Instead: after the in-page `fetch`+parse,
build the tidy CSV string in the page and trigger a **Blob download** (`a.download`; needs no focus, no
size-limited tool return) to `~/Downloads`. Then grant Downloads (`device_request_folder_access`) and pull
it into the cloud. **The device bridge times out on ~13 MB files — `gzip` on the Mac first** (CSV compresses
~20:1 → a few hundred KB), `device_stage_files` the `.gz`, `gunzip` + validate in the cloud, then
`SendUserFile` the clean CSVs to the user — these `RAW_SEC_<form>/<filingDate>_<accession>.csv` files **are** the output.
Write **one CSV per filing** (1:1), never a combined per-form file — this keeps each download small and lets
a re-run skip accessions already on disk.
