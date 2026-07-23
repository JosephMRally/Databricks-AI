# RAW_PropertyHistory

**Output (CSV):** `RAW_PropertyHistory.csv` — the per-property event timeline, verbatim. Landed as a **CSV file** (not a Google-Sheet tab); still **SCD Type 2** — the CSV holds the full append-only history with the SCD bookkeeping columns (`api-reference.md` "SCD common": read the existing CSV → diff → expire → append).
**Source:** scraped per property from the **"View Full Property Timeline"** modal (Performance tab) — see `api-reference.md` Source 3. **No API exists.**
**`source` tag:** `arrived:property-timeline`
**SCD type:** **Type 2** (event — append-only; do **not** expire on absence).
**Primary key (`nk`):** **(`offeringCid`, `eventDate`, `eventType`)** → `offeringCid|eventDate|eventType`
**Sort order:** `property_slug`, then `eventDate` (ascending). `eventDate` is emitted **`YYYY-MM-DD`** (convert from the source `MM/DD/YYYY`) so it is true Date type and sorts chronologically as text — each property's timeline is time-ordered.

## Columns (verbatim, in order)

| Column | Meaning |
|---|---|
| `offeringCid` | offering id (part of the key). |
| `property_slug` | the property slug (primary sort key). |
| `eventType` | one of: `Initial Public Offering`, `Market Preparation`, `Marketed for Rent`, `Approved Application`, `Lease Started`, `Lease Renewed`, `Lease Completed`, `Marketing Rent Changed`, `Arrived Valuation Updated`, `Dividends Paid`, `Dividends Paused` (part of the key). |
| `eventDate` | **`YYYY-MM-DD`** (converted from the source `MM/DD/YYYY`; part of the key). |
| `detail` | the value line(s) shown (e.g. `$1,820`; `3.06% Annualized Dividend Yield`; `$10.17`). |

Then the **SCD2 bookkeeping columns** — see `api-reference.md` "SCD common".

## Notes
- **Raw landing only — this sheet no longer feeds the computed tab's Tenant Status.** Tenant Status
  (column **U**) now comes directly from `properties[0].leaseStatus` (`RAW_OfferingDetails`), Title-Cased
  (`OCCUPIED` → `Occupied`). The old timeline derivation (`Lease Renewed` → `renewed`; recent `Lease
  Started` → `new`, else `current`) tracked lease *age* rather than occupancy and mislabeled current
  holdings, so it was dropped. The timeline is still captured here verbatim for history.
- The modal is fully rendered (not virtualized) — one `innerText` read captures every event; parse in a
  short synchronous call (anchor on the `MM/DD/YYYY` lines).
