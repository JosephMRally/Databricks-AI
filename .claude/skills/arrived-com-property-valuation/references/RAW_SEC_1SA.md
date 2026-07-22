# RAW_SEC_1SA

**Sheet:** `RAW_SEC_1SA` — the **financial-table content** of every **Form 1-SA** (semiannual report) filed by the portfolio's Arrived parent series-LLCs, in **tidy/long** form (one row per table cell). Same structure and extraction as `RAW_SEC_1K`, but **unaudited** and **semiannual** (periods end **June 30**, with an **as-of Dec 31** comparative on the balance sheet).
**Source:** the 1-SA's report `.htm` (name contains `1sa`, e.g. `ea0257633-1sa_arrived3.htm`) — this **is** the primary document for 1-SAs (unlike 1-Ks). See `api-reference.md` → **"SEC filing extraction"**.
**`source` tag:** `sec:1-sa-html-tables`
**SCD type:** **Type 2** (append-only). **`filingDate` + `accession` in the grain**; keep every 1-SA; skip accessions already present.

## What tables to capture

Same consolidating statements and per-series note schedules as the 1-K (see `RAW_SEC_1K.md`), detected the same way. The comprehensive-income statement may appear as `... STATEMENT OF OPERATIONS`; the engine's title detection handles both. `period_basis` for the semiannual flows is `period_ended` (six months ended June 30).

## Columns (tidy/long — identical schema to RAW_SEC_1K)

`form` (`1-SA`/`1-SA/A`), `filingDate`, `entityName`, `accession`, `statement`, `period_basis`, `period`, `line_item`, `property`, `value`.

**Do NOT pivot on `property`** — one row per property × line-item; `property` and `value` are their own fields.

## Notes
- Shared extraction engine + cross-checks: `api-reference.md`.
- 1-SA balance sheets **may or may not** carry a `Consolidated` total column — it's **entity-dependent** (AH3's June-30 interim omits it; AH `1821720` includes one). When absent, per-series values are still fully captured, only the roll-up column is blank — don't treat a missing `Consolidated` as a parse error.
- Series count grows over time (e.g. AH3: 2023 ≈ 59, 2024 ≈ 86, 2025 ≈ 97); absent series → omitted rows.
- All date fields (`filingDate`, and `period` when it's a date) are emitted **`YYYY-MM-DD`** (e.g. `2025-06-30`).
- Four parent LLCs: `1821720` (Arrived Homes), `1962723` (Arrived Homes 3), `2015697` (Arrived Homes 4), `2032732` (Arrived Homes 5).
