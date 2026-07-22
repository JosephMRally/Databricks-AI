---
name: arrived-com-property-valuation
description: "Arrived.com property valuation in a google spreadsheet"
---

# Arrived.com SFR Property Valuation → Google Sheet

## Goal

Iterate through the user's Single-Family Residential (SFR) holdings on arrived.com and, for
each property, determine whether it has positive or negative cash flow and — when cash flow is
positive — its Return on Investment (ROI) at the property's **current Arrived Valuation**. Also
capture a **dividend-payment track record** (how many of the trailing 12 eligible months the
property actually paid a distribution) and the property's **mortgage** (initial and current
balance). Record one row per property in a **worksheet tab named for the current month** (e.g. `July
2026`) inside the target Google Sheet, so each month's run is kept as its own tab. Cross-check
valuation changes against the SEC offering circular linked on each property page and the Arrived
Valuations help article.

- Reference help article: https://help.arrived.com/en/articles/6909386-how-do-we-calculate-arrived-valuations
- Target spreadsheet: https://docs.google.com/spreadsheets/d/185M_8BCE86vKdoTFpIrEy87nH5QyZqH5RWs5bQyZvGc/edit — each run writes to its own month-named tab (e.g. `July 2026`)

**Two layers, written every run.** (1) The **computed presentation layer** — the per-property month
tab below. (2) A **raw landing layer** — every value retrieved from Arrived and the SEC,
**untransformed**, written to **nine active per-source raw sheets** (five Arrived-API + four SEC-content; all **Slowly Changing Dimension (SCD)
Type 2**; the legacy `RAW_SECBalanceSheet` / `RAW_SECDividends` are **deprecated**, folded into `RAW_SEC_253G2` / `RAW_SEC_1U`) so each source record's history is preserved. The raw layer
never derives or reformats anything; it only adds SCD bookkeeping columns. **Each raw sheet has its own
reference file** — `references/RAW_<Sheet>.md` (source, **primary key**, columns, SCD type, sort order)
— and the shared auth / endpoints / SCD mechanics live in `references/api-reference.md`.

---

## Where the data comes from (summary)

Almost everything comes from the **authenticated Arrived API** (`https://abacus.arrivedhomes.com`):
the holdings list, each offering's record, and the distribution history behind the
dividend-consistency column. The per-property SEC offering-circular URL — and the property's initial
mortgage/financing — come from the SEC filing linked on the property page.

**The full API reference — endpoints, the bearer-token/cookie auth capture, field mappings,
derived-field formulas, the SEC sourcing, dividend consistency, and the shared SCD mechanics — lives in
[`references/api-reference.md`](references/api-reference.md); each raw sheet's schema, primary key, and
sort order live in its own `references/RAW_<Sheet>.md`. Read those before pulling any data; SKILL.md
keeps only the orientation below.**

Quick orientation (details in the reference file; column letters refer to the output layout further down):

- **Which holdings count as SFR properties:** `offeringInvestmentProductType === 'SINGLE_FAMILY_RESIDENTIAL_IPO'`, **both open (`currentSharesCount > 0`) and closed / fully-exited (`currentSharesCount === 0`)** positions — these are the arrived.com Portfolio **Positions** page's **OPEN POSITIONS** and **CLOSED POSITIONS** tabs. Exclude only the SFR *Fund*, vacation rentals (`VACATION_RENTAL_IPO`), and private credit. **Open positions render on top, sorted by `ROI ($)` descending; closed positions are grouped after them, also sorted by `ROI ($)` descending** — mirroring how Arrived separates the two tabs. The **raw** `RAW_Holdings` sheet keeps the full unfiltered response (all product types) as always.
- **`buy` and `sell` (columns A & B) are human-entered boolean checkboxes that persist across refreshes** — your own flags at the **left of everything**. Each run reads the prior tab's values by **Property** and restores them (default `FALSE` for a newly-seen property); it never blanks your entries. **`buy` appears on every row. `sell` appears ONLY on rows whose `raw_holdings.currentSharesCount > 0` (open positions)** — a closed/exited position (0 shares) gets **no `sell` checkbox** (you can't sell what you no longer hold), so its column-B cell is left blank with no checkbox.
- **Your cost basis (Avg Cost / Share)** = your average price paid per share = **`currentInvestment ÷ currentSharesCount`** — *not* the $10 issue price. **ROI is shown three ways** (there is **no separate `Value` column** — the total-value figure is inlined into ROI ($)): **ROI ($)** = (Total Dividends Received + Current Arrived Valuation / Share × currentSharesCount) − (Avg Cost / Share × currentSharesCount) = your **net dollar gain** (can be negative); **Dividend ROI (%)** = Total Dividends Received ÷ cost basis (**dividends-only** return); **ROI (%)** = ROI ($) ÷ cost basis (**total** return).
- **Closed / exited positions (`currentSharesCount === 0`)** can't use the per-share formulas (they would divide by zero: `currentInvestment ÷ 0` and cost basis `= 0`). Handle them as a **realized** record instead, using **`initialInvestment`** (the original pre-sale amount) as the cost basis: **ROI ($)** = Total Dividends Received **+ `appreciation.totalRealized`** (the realized gain/loss booked at sale) — your realized net dollar result; **Dividend ROI (%)** = Total Dividends Received ÷ `initialInvestment`; **ROI (%)** = ROI ($) ÷ `initialInvestment`. Leave the **current-holding / current-operating** columns blank for a closed position — **Avg Cost / Share (R)** (0 shares), **ROI at Current Valuation (G)**, **Current Rent (M)**, **Current Expenses (N)**, **Initial/Current Mortgage (O/P)**, **Annual Cash Flow (Q)**, **Equity Raised (S)**, and **SEC Filing (T)** — since you no longer own the property; still show identity, Purchase Date, Dividend Consistency, Total Dividends, Current Arrived Valuation / Share, and Tenant Status.
- **Current Arrived Valuation** = arrived.com's official current per-share valuation (the quarterly comparable-sales figure). It exists **only on arrived.com** — prefer the valuation source over a raw holdings field. The **SEC offering circular** is authoritative only for the **$10 issue price** (the ROI/valuation-change baseline) and the offering size.
- **Mortgage** = the property's debt. **Initial** principal = API `debtAmount` (`0` for all-cash); **current** balance from arrived.com (or Arrived's 1-K/1-SA, or amortized from the initial loan).
- **SEC financial CONTENT — one tidy sheet per form.** The **actual financial tables** out of every **1-U, 1-K, 253G2, and 1-SA** filed by the portfolio's Arrived parent series-LLCs are extracted into their own **SCD2, tidy/long** sheets — **`RAW_SEC_1U`** (per-series dividend/share), **`RAW_SEC_1K`** & **`RAW_SEC_1SA`** (consolidating balance sheet / comprehensive income / members' equity / cash flows + per-series note schedules), **`RAW_SEC_253G2`** (unaudited pro-forma balance sheet). Grain includes **`filingDate` + `accession`** (full history, append-only). **Tidy shape: one row per (filing, statement, period, line_item, property)=value — `property` and `value` are their own fields; never pivot on property.** Extraction method: `references/api-reference.md` → "SEC filing extraction"; per-sheet schema: `references/RAW_SEC_1U.md`, `RAW_SEC_1K.md`, `RAW_SEC_253G2.md`, `RAW_SEC_1SA.md`. There is **no quarterly (10-Q)** report (Reg A exempt); the pro-forma balance sheet lives in the 253G2 offering circular. (The computed tab's **SEC Filing (column T)** still carries the offering-circular URL scraped from the property page. The older `RAW_SECBalanceSheet` / `RAW_SECDividends` content sheets are superseded by `RAW_SEC_253G2` / `RAW_SEC_1U`.)
- **Dividend consistency** = distinct calendar months with a paid distribution in the trailing `Y = min(12, months since ipoDate)` window, written as the text `"X / Y"`. Pull the distribution history from `/offerings/{cid}/dividends` (see the reference file).

---

## COMPUTED OUTPUT TAB — 21-column layout (A–U)

Each run writes a **21-column, A–U** layout (header row + one row per property) into a fresh
**month tab**. **Open positions come first, sorted by `ROI ($)` (column J) descending** — best dollar gain
first — then **closed / exited positions grouped below, also sorted by `ROI ($)` descending**. Row 1 =
headers; data from row 2. **Columns A (`buy`) and B (`sell`) are human-entered boolean checkboxes that
PERSIST across refreshes** — before rewriting the tab, read the existing `buy`/`sell` per **Property** and
restore each property's values after the paste (see the "buy/sell persistence" note under *Writing into the
sheet*); never blank them. **`buy` renders on every row; `sell` renders only on open rows
(`currentSharesCount > 0`)** — closed rows get no `sell` checkbox. Formula columns are computed by the
sheet, not hard-coded. Number formats: **checkbox** on **A** (all rows) and **B** (open rows only);
**Date** on **E** (Purchase Date); percent (2 dp) on **G, K, L**; currency on **H, I, J, M, N, O, P, Q, R,
S**; leave **F** (the `"X / Y"` count), **T** (the SEC URL), and **U** (Tenant Status text) as plain text.
**Finally, autosize every column to its contents — Format → Resize columns → "Fit to data" (a.k.a.
double-click a column-border to auto-fit) across A:U** so nothing is clipped.

| Col | Header | Source / formula (row 2 shown) |
|---|---|---|
| A | buy | **human-entered boolean** (checkbox) that **persists across refreshes**. Your own buy flag — the run reads the prior value for this **Property** and restores it (default `FALSE` for a newly-seen property); it **never blanks** your entry. Not derived from any source. |
| B | sell | **human-entered boolean** (checkbox), **persisted across refreshes** exactly like `buy`. Not derived. **Rendered ONLY on rows whose `raw_holdings.currentSharesCount > 0` (open positions).** A closed/exited position (0 shares) gets **no checkbox** here — leave B blank and do **not** insert a checkbox on it (you can't sell what you don't hold). |
| C | Property | formula `=HYPERLINK("https://arrived.com/app/properties/"&nameSlug, name)`. `nameSlug` = the offering **`name`** lowercased with spaces → hyphens (`The Hedgecrest` → `the-hedgecrest`, `The McGregor` → `the-mcgregor`) — this is the **live logged-in app route**. ⚠️ Do **NOT** use the old public `https://arrived.com/properties/{properties[0].slug}` (address-based) pattern — Arrived retired those pages and every one now **redirects to the `/app/properties` browse page** (verified for open, closed, and camel-cased names). Written per row as a literal. (`properties[0].slug`, the address slug, is still landed in the raw sheets; it's just no longer used to build this link.) |
| D | Market | API `market.title` |
| E | Purchase Date | the date **you** first began owning this property — API **`ownershipStartDate`** on the holding, rendered `YYYY-MM-DD`. **Sits immediately right of Market.** Pasted value; format as a **Date**. Do **not** confuse it with `startAt` (the *offering's* open date). |
| F | Dividend Consistency (TTM) | text `"X / Y"` — X = distinct months in the trailing Y months with a paid distribution; Y = `min(12, whole months since ipoDate)`. Pasted computed value (not a live formula). Definition: `references/api-reference.md` (Source 2b). |
| G | ROI at Current Valuation | formula `=IF(Q2>0, Q2/(S2*(1+(I2-10)/10)), "")` — annual cash flow (Q) ÷ the property's *current* total valuation (`S2` = Equity Raised). `(I2-10)/10` is the property-level Arrived Valuation change from the $10 issue price. Blank unless cash flow (Q) > 0. **Closed positions: leave blank** (exited — no current holding to measure). |
| H | Total Dividends Received | API **`rentalIncome.totalDividendsPaid`** on the holding — **`rentalIncome` is a nested object, NOT a scalar** (it also carries `annualizedDividendPercent`, `latestDividend{…}`, and an `allDividends[]` array — take the `.totalDividendsPaid` scalar, drop the array). Cumulative rent dividends you've been paid. Pasted value. |
| I | Current Arrived Valuation / Share | arrived.com's **official current per-share valuation** — the latest `/offerings/{cid}/share-prices/history` entry (≈ `offeringSharePrice`). Pasted value. |
| J | ROI ($) | **Open:** formula `=H2+(I2*<shares>)-(R2*<shares>)` — **net dollar gain**, with the old **Value** formula inlined: (**Total Dividends Received** (H) **+** **Current Arrived Valuation / Share** (I) **× shares**) **−** (**Avg Cost / Share** (R) **× shares**). `<shares>` = the holding's **`currentSharesCount`**, a literal per row (e.g. a 10-share row = `=H2+(I2*10)-(R2*10)`). `Avg Cost / Share × currentSharesCount = currentInvestment` (your cost basis). **Closed (0 shares):** formula `=H<r>+(<totalRealized>)` — realized net = **Total Dividends Received + `appreciation.totalRealized`** (the `totalRealized` literal, e.g. `=H37+(-0.83)`). Can be negative. **Open positions are sorted by this column descending, then closed positions below them sorted the same way.** Format as currency. (There is **no separate `Value` column** — it was merged in here.) |
| K | Dividend ROI (%) | **Open:** formula `=H2/(R2*<shares>)` — **dividends-only ROI** = **Total Dividends Received** (H) ÷ your cost basis (**Avg Cost / Share** (R) × `currentSharesCount`, the same literal). **Closed:** formula `=H<r>/<initialInvestment>` — Total Dividends Received ÷ **`initialInvestment`** (the original pre-sale cost basis, a literal, e.g. `=H37/250`). The return earned from rent distributions **alone**, as a percent of what you paid. Format as percent (2 dp). |
| L | ROI (%) | **Open:** formula `=J2/(R2*<shares>)` — **ROI ($)** (J) ÷ your cost basis (**Avg Cost / Share** (R) × `currentSharesCount`, the same literal). **Closed:** formula `=J<r>/<initialInvestment>` — realized **ROI ($)** (J) ÷ **`initialInvestment`** (same literal as K, e.g. `=J37/250`). Total net gain as a percent of cost. Format as percent (2 dp). |
| M | Current Rent | current annual rent = `properties[0].rent × 12` (the latest/current contract rent). Pasted value. |
| N | Current Expenses | current annual expenses = `M2 − projectedAnnualDividendYield × S2` (pasted computed value; `S2` = Equity Raised). |
| O | Initial Mortgage | original mortgage principal at acquisition (`0` if all-cash) — API `debtAmount`. Pasted value. |
| P | Current Mortgage | current outstanding loan balance (`0` if all-cash). From arrived.com's current financials, else the SEC `Loan payable, net` / 1-K/1-SA figure, else an amortization estimate (label estimates as such). Pasted value. |
| Q | Annual Cash Flow | formula `=M2-N2` (Current Rent − Current Expenses) |
| R | Avg Cost / Share | your average price paid per share = **`currentInvestment ÷ currentSharesCount`** (held positions only). Not the $10 issue price. Pasted value. **Closed positions: leave blank** (0 shares — no current per-share cost; the closed ROI %s use `initialInvestment` instead). |
| S | Equity Raised | API `targetRaiseAmount` |
| T | SEC Filing (Offering Circular) | the **direct** filing-document URL — `https://www.sec.gov/Archives/edgar/data/{CIK}/{accession}/{file}.htm`. Scrape from the property page's Documents section (`a[href*="sec.gov/Archives/edgar"]`), one property per `dropId`. **Not** the documents-endpoint `fileUrl` (an EDGAR search page). |
| U | Tenant Status | the property's **current lease/occupancy state**, taken **directly from `properties[0].leaseStatus`** on `GET /offerings/{cid}` (landed in `RAW_OfferingDetails.property_leaseStatus`) — this is the field the arrived.com Positions page renders as its **RENTAL STATUS** column. Map the raw enum to Title Case: **`OCCUPIED` → `Occupied`** (Arrived's UI shows "Rented"), **`VACANT` → `Vacant`**, any other value → Title-Case the token (underscores → spaces). Pasted value. **Do NOT derive this from the Property-History timeline** (the old `new`/`renewed`/`current` buckets measured lease *age*, not occupancy, and were wrong — every current holding read `OCCUPIED`). The timeline still lands verbatim in `RAW_PropertyHistory`, it just no longer feeds this column. |

**Live formulas** go in **C** (HYPERLINK), **G** (ROI at Current Valuation, open rows only), **J** (ROI $),
**K** (Dividend ROI %), **L** (ROI %), and **Q** (Annual Cash Flow, open rows only); the `"X / Y"` text in
**F** is a computed value; **A/B** (`buy`/`sell`) are human checkboxes; every other column is a pasted
value. On **closed rows**, G and Q are blank and J/K/L use the closed-position formulas (realized net;
`initialInvestment` basis).

**Writing into the sheet (no Sheets API tool available):** build the TSV — **21 columns, A–U** in the
order above. **Open positions first, sorted by `ROI ($)` descending** (compute `ROI ($) = (TotalDividends +
CurrentValuation×shares) − AvgCost×shares` per open property), **then closed positions, sorted by `ROI ($)`
descending** (compute their `ROI ($) = TotalDividends + totalRealized`); then number the per-row formulas
by their final sorted position. Per-row formulas in C/G/J/K/L/Q — the open **ROI ($)** (J), **Dividend ROI
(%)** (K) and **ROI (%)** (L) formulas each have that row's `currentSharesCount` baked in as a literal;
the closed J/K/L bake in `totalRealized` / `initialInvestment` literals. The `"X / Y"` text goes in **F**.

**`buy`/`sell` persistence (required):** these are the only human-owned columns — do not lose them on a
refresh. **Before clearing the tab**, read the current tab's `buy`/`sell` values keyed by **Property**
(via the Drive API). Build A/B of each sorted output row from that map (default `FALSE` for a property
not previously present). When creating a **brand-new** month tab, seed `buy`/`sell` from the **most
recent existing** month tab so the flags carry forward. Then open the target spreadsheet in a browser
tab. **After pasting, insert checkboxes: `buy` on `A2:A<last>` (every data row), and `sell` on `B2:B<last
open row>` only** (the open block is contiguous at the top because closed positions are grouped below, so
one range covers it — Insert → Checkbox). **Do not insert a `sell` checkbox on any closed row.** TRUE
values from the restore map stay checked.

**Write each run to its own month tab.** Name it for the **current month** — `{MonthName} {year}`, e.g.
`July 2026`, computed at runtime, **never hardcoded**. Add a sheet with the **+** button (bottom-left),
rename it, make it active. If a tab for this month already exists, write into that one.

Paste: set the clipboard (real Cmd/Ctrl+C on a selected off-screen `<textarea>` holding the TSV is the
reliable path — the Clipboard API is often blocked), select A1 via the Name Box, press Cmd/Ctrl+V.
Apply number formats via Name-Box range select + Ctrl+Shift+5 (percent, **G, K, L**) / Ctrl+Shift+4
(currency, **H, I, J, M, N, O, P, Q, R, S**); leave **F**, **T**, **U** unformatted, format **E**
(Purchase Date) as a Date, and add **checkboxes** on **A2:A<last>** (all rows) and **B2:B<last open row>**
(open rows only) via Insert → Checkbox for `buy`/`sell`.

**Autosize all columns last (required — "Fit to Data").** After formats and checkboxes, select all columns
**A:U** (click the column-A header, Shift-click the column-U header — or Ctrl/Cmd+A) and **Format → Resize
columns → "Fit to data"** (equivalently, double-click any selected column border). Every column then hugs
its widest cell so nothing is clipped. Do this after the number formats so the fitted widths account for
the formatted (currency/percent/date) text.

Force the `"X / Y"` cells to text (prefix each with a `'` in the TSV) so Sheets doesn't read `5 / 12`
as a date or division.

**Freeze, bold, and wrap the header row (required).** After the paste, select the header via the Name
Box (`A1:U1`): Cmd/Ctrl+B to bold; **Format → Wrapping → Wrap** to text-wrap; then **View → Freeze → 1
row** to freeze. Confirm the freeze took — row 1 should stay pinned when you scroll.

Verify the result with the Google Drive API (`read_file_content`) since Google Sheets is
canvas-rendered and screenshots/DOM reads of cells don't work.

---

## METHOD SUMMARY

Endpoint / auth / field detail is in [`references/api-reference.md`](references/api-reference.md); each
raw sheet's schema + primary key + sort order is in its own `references/RAW_<Sheet>.md`.

1. Open a logged-in arrived.com tab; patch `fetch`/`XHR`, navigate to Portfolio, then click into
   **POSITIONS / ACTIVITY** so the app fires an authenticated request — capture the bearer token and
   the account (`bact_…`) id.
2. `GET /accounts/{bactId}/balance/offerings`; keep **all `SINGLE_FAMILY_RESIDENTIAL_IPO` holdings — both
   open (`currentSharesCount > 0`) and closed / fully-exited (`currentSharesCount === 0`)** (the Positions
   page's OPEN and CLOSED tabs). Record shares, **`currentInvestment`** (cost basis → column **R**, Avg Cost
   / Share; `0` on closed), **`initialInvestment`** (original pre-sale cost basis → the **closed**-position
   ROI-% denominator), **`rentalIncome.totalDividendsPaid`** (the scalar inside the **nested** `rentalIncome`
   object → column **H**, Total Dividends Received), **`appreciation.totalRealized`** (realized gain/loss →
   the **closed**-position **ROI ($)**), and **`ownershipStartDate`** (your purchase date → column **E**,
   right after Market). The **raw** `RAW_Holdings` sheet lands the full, unfiltered response — its
   **`currentSharesCount`** feeds the open **ROI ($) / Dividend ROI (%) / ROI (%)** formulas (baked into each
   row as a literal) and gates the **`sell` checkbox** (open rows only). **Also read the prior tab's
   `buy`/`sell` by Property here** so they can be restored (persistence).
3. For each holding, `GET /offerings/{cid}`; grab `ipoDate` (dividend-consistency Y), `debtAmount`
   (mortgage), the **current Arrived Valuation** → column **I** (latest `/share-prices/history`), and
   **`properties[0].leaseStatus`** → **Tenant Status (column U)**, Title-Cased (`OCCUPIED` → `Occupied`).
   This is the direct, authoritative source (what the Positions page shows as RENTAL STATUS); do **not**
   derive Tenant Status from the Property-History timeline. Also land `leaseStartAt`/`leaseEndAt` in
   `RAW_OfferingDetails`.
4. `GET /offerings/{cid}/dividends`; count the distinct trailing-12-month months a distribution covered
   → column **F** `"X / Y"`.
5. Group by `dropId`; scrape one property page per drop for the **direct** Offering Circular link →
   column **T** (**not** the documents-endpoint `fileUrl`) — for **open** positions (a closed/exited row
   leaves T blank). Read initial mortgage (column **O**) from `debtAmount`. **Per property**, read the
   **Property History** timeline into **`RAW_PropertyHistory`** (raw landing only) — it **no longer feeds
   Tenant Status** (column **U** now comes from `properties[0].leaseStatus`, step 3).
6. **SEC filings — financial CONTENT per form, 4 tidy sheets (not a filing index).** For each parent
   series-LLC CIK (`1821720` Arrived Homes, `1962723` Arrived Homes 3, `2015697` Arrived Homes 4, `2032732` Arrived Homes 5), discover
   filings via the **submissions API** `https://data.sec.gov/submissions/CIK{paddedCik}.json`, then extract
   the **financial tables** out of each filing's report `.htm` into its own **tidy/long** sheet — **1-U →
   `RAW_SEC_1U`** (per-series dividend/share), **1-K → `RAW_SEC_1K`** & **1-SA → `RAW_SEC_1SA`**
   (consolidating balance sheet / comprehensive income / members' equity / cash flows + the per-series note
   schedules), **253G2 → `RAW_SEC_253G2`** (unaudited pro-forma balance sheet). Each is **SCD2, append-only**,
   with **`filingDate` + `accession` in the grain**; a re-run skips accessions already present.
   **Tidy shape (required): one row per (filing, statement, period, line_item, property)=value — `property`
   (the series/property name) and `value` are their own fields; NEVER pivot on property (no column-per-series
   layout).** The full method — EDGAR discovery, the **bulk same-origin `fetch()`** trick (fetch the
   submissions JSON + all filing `.htm`s from one `www.sec.gov` tab, no per-doc navigation), the
   **order-token coalescing** parser (SEC splits `$`/number/`)` across cells and header vs data rows have
   different cell counts, so map the *Nth numeric token → Nth series*), the cross-checks, and the
   **ISO-date rule** (all dates `YYYY-MM-DD`), the 1-K **doc resolution via `index.json`** (its `primaryDocument` is only the XBRL cover), and the **download → device-bridge landing** for the large SEC data (gzipped CSVs, not clipboard-paste) — is in
   `references/api-reference.md` → **"SEC filing extraction"**; each sheet's columns are in its
   `references/RAW_SEC_<form>.md`. (This supersedes the old filing-index sheets and the separate
   `RAW_SECBalanceSheet` / `RAW_SECDividends` content sheets, now folded into `RAW_SEC_253G2` / `RAW_SEC_1U`.)
7. Set the **current mortgage** (column **P**) — `0` for all-cash; else arrived.com's current balance /
   the SEC `Loan payable, net` / an amortization estimate (label estimates).
8. **Land the raw sheets** — upsert all **eleven** per-source sheets **exactly per their
   `references/RAW_<Sheet>.md`** files (source, primary key, columns, SCD type, sort order) and the shared
   `api-reference.md` "SCD common" (read → diff → expire → append → **sort**). Values land **verbatim**;
   an unchanged re-run writes nothing. Each sheet is kept **sorted** by its documented order (e.g.
   `RAW_Holdings` by `name`, `loaded_at`; `RAW_PropertyHistory` by `property_slug`, `eventDate` — sorted
   **as a date**). Independent of the computed tab.
9. Write the **computed** month tab — 21 columns **A–U** — into a `{MonthName} {year}` tab. **Open
   positions first, sorted by `ROI ($)` (column J) descending; closed / exited positions grouped below,
   also sorted by `ROI ($)` descending.** **A/B (`buy`/`sell`) restored from the prior tab by Property
   (persistence): `buy` checkbox on every row, `sell` checkbox on open rows only** (contiguous top block —
   closed rows get no `sell` checkbox). Live formulas in **C** (HYPERLINK), **G** (ROI at Current
   Valuation, open only), **J** (ROI $ — the old Value formula is inlined; closed = dividends + realized),
   **K** (Dividend ROI %), **L** (ROI %) — open rows bake in `currentSharesCount`, closed rows bake in
   `totalRealized`/`initialInvestment` — and **Q** (Annual Cash Flow, open only); `"X / Y"` computed text
   in **F**; pasted values elsewhere; closed rows leave G/M/N/O/P/Q/R/S/T blank. **No separate `Value`
   column.** Then bold, **wrap**, **and freeze** the header row (`A1:U1`), and **autosize every column
   A:U to "Fit to Data"** as the final formatting step.
10. Verify (via the Drive API): **computed tab** — **open positions on top sorted by `ROI ($)` (column J)
    descending, then closed positions grouped below, also `ROI ($)`-descending**; open rows: ROI at Current
    Valuation only-when-positive, `ROI ($) = (H + I × currentSharesCount) − (R × currentSharesCount)`,
    `Dividend ROI (%) = H ÷ (R × currentSharesCount)`, `ROI (%) = ROI ($) ÷ (R × currentSharesCount)`;
    closed rows: `ROI ($) = H + totalRealized`, `Dividend ROI (%) = H ÷ initialInvestment`, `ROI (%) = ROI
    ($) ÷ initialInvestment`, and G/M/N/O/P/Q/R/S/T blank; **Purchase Date (E) right after Market**, **no
    `Value` column and no `Status` column**, column **R** (Avg Cost / Share) vs. your actual cost (not $10),
    column **H** (Total Dividends Received) vs. `rentalIncome.totalDividendsPaid`, **Tenant Status (U) =
    Title-Cased `properties[0].leaseStatus`** (e.g. `Occupied`) — never the old `new`/`renewed`/`current`;
    **`buy` checkbox on every row and `sell` checkbox on open rows only, matching the prior tab**; header
    frozen; **all columns A:U autosized ("Fit to Data")**; **raw sheets** — an unchanged re-run added zero
    rows, a changed value produced one new live row + one expired old row, and each natural key has exactly
    one `is_current = TRUE` version.

## Notes / gotchas

- `javascript_tool` output is auto-blocked if it contains cookie/query-string data — strip query
  strings (`url.split('?')[0]`) and never echo tokens. SEC `fileUrl`s carry query strings, so store
  them straight into the TSV/clipboard rather than returning them to yourself.
- The `/offerings/{numericId}/documents` endpoint can hang; prefer `/offerings/{cid}/documents`.
- Persist the pulled dataset to disk (or a `window.__*` global) early — browser tabs can be recreated
  and lose in-memory state.
- **Paginated lists → set "Items per page" to 100.** Whenever a page you're reading (arrived.com or
  SEC EDGAR) exposes an **"Items per page"** / page-size selector on a list, set it to **100** (the
  largest option offered) before reading, so the whole list loads in as few pages as possible and you
  minimize pagination clicks. Applies anywhere a list is paginated — holdings/activity, dividend or
  transaction history, EDGAR filing lists, etc.
- **SEC financial content lives in four tidy sheets** — `RAW_SEC_1K`, `RAW_SEC_1SA`, `RAW_SEC_253G2`
  (balance sheet / statements) and `RAW_SEC_1U` (per-series distributions), all **tidy/long, SCD2**, keyed
  by `filingDate` + `accession`. Extract across **all four parent LLCs** (`1821720`, `1962723`, `2015697`,
  `2032732`). The legacy `RAW_SECBalanceSheet` / `RAW_SECDividends` are **deprecated** (folded into
  `RAW_SEC_253G2` / `RAW_SEC_1U`). The offering-circular **URL** still lives only in the computed tab's
  **column T** (scraped from the property page). Reg A has **no quarterly (10-Q) report**. The API dividend
  history stays in `RAW_Dividends`. See each `references/RAW_SEC_*.md`.
- **All date fields are `YYYY-MM-DD` (Date type).** Every date on every sheet — SEC `filingDate` /
  `reportDate` / `as_of_date` / `period` (when it's a date), and the Arrived-API `ownershipStartDate` /
  `eventDate` / share-price & dividend dates / `leaseStartAt`-`leaseEndAt` — is emitted `YYYY-MM-DD` so the
  columns import as true Date type (for SEC values, parse the printed `Month D, YYYY` → ISO).
