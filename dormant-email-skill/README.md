# Dormant-email cleanup — ELT pipeline

A three-stage **ELT** that does a single pass over a Gmail mailbox, records the
**first/last-seen** date of every address in From/To/Cc/Bcc, and produces the
thread ids whose old mail you could trash. Built for the Gmail MCP connector.

The pipeline **decides** what to delete. It does **not** delete anything itself —
the optional trash step is a separate, deliberate action you run against the
emitted thread ids.

```
search_threads pages ──▶ Phase 1 ──▶ occurrences.csv ──▶ Phase 2 ──▶ contacts_first_last_seen.csv
   (Gmail MCP)            gather                            aggregate
                                                                        │
                                       dormant_threads.csv ◀── Phase 3 ◀┘ (+ occurrences.csv)
                                                               filter
```

## Files

| File | Role |
|------|------|
| `scripts/gather_emails.py`    | **Phase 1 / Extract.** Facade over the Gmail MCP. One sweep → one row per (message, address) occurrence. |
| `scripts/aggregate_emails.py` | **Phase 2 / Transform.** Collapse occurrences to earliest/latest date per address. |
| `scripts/filter_emails.py`    | **Phase 3 / Filter.** Pick a cutoff, flag dormant addresses, resolve them to thread ids. |
| `tests/`                      | pytest suite (TDD, mocked MCP only) incl. synthetic real-format `search_threads` pages. |

## Schemas

**Phase 1 → `occurrences.csv`** — `date(YYYY-MM-DD), thread_id, message_id, email, labelIds(pipe-joined)` (STARRED, if set, stays inside `labelIds`)
**Phase 2 → `contacts_first_last_seen.csv`** — `email, earliest_date, latest_date`
**Phase 3 → `dormant_threads.csv`** — `thread_id`

Arrays (`labelIds`) are joined with the `|` delimiter. All output is streamed
row-by-row, so the mailbox can be larger than memory.

## Running it

### Phase 1 — fetch + extract
In Cowork the OAuth connector is callable only by the agent, so the **agent**
pages `search_threads` and saves each raw page verbatim, then the script reads
those files:

1. Agent calls `search_threads` with `view=THREAD_VIEW_METADATA_ONLY`,
   `pageSize=50`. Empty query = all mail (excludes Spam/Trash); `query="in:anywhere"`
   to include everything.
2. Save each page to `pages/page_001.json`, `page_002.json`, … **verbatim**.
   Paginate on `pageToken` **until there is no `nextPageToken`**
   (`resultCountEstimate` is an unreliable, often-stuck placeholder). Retry
   transient failures by resending the one call.
3. Run the extract:
   ```
   python3 scripts/gather_emails.py --pages-dir pages --out occurrences.csv
   ```

> A whole mailbox can be 100+ pages. Stream each page straight to a file; the
> model never holds raw pages. The fetch is one ordered walk (`pageToken` is
> opaque — not parallelizable); delegate it to a worker subagent for big
> mailboxes. Only Phase 1 touches the network; Phases 2–3 are local CSV passes.

*(Live mode: where the Gmail MCP is exposed to Python,
`MailboxSweepFacade.from_mcp(client)` pages `search_threads` itself — calling
only that command, retrying each transient failure once.)*

### Phase 2 — aggregate
```
python3 scripts/aggregate_emails.py --in occurrences.csv --out contacts_first_last_seen.csv
```

### Phase 3 — filter
Interactive (prompts for ignore list [owner defaults in], retain list, cutoff years [default 5]):
```
python3 scripts/filter_emails.py \
  --aggregate contacts_first_last_seen.csv \
  --occurrences occurrences.csv \
  --owner you@gmail.com
```
Non-interactive overrides: `--years N --ignore "a@x.com,b@x.com" --retain "keep@x.com"`.

An address is **dormant** when its `latest_date` is older than `today − N years`.
A thread is emitted when it contains ≥1 dormant address and **no** retained
address (retained addresses protect the whole thread).

### Optional cleanup (manual, after Phase 3)
For each `thread_id` in `dormant_threads.csv`, the agent adds the system label
`TRASH` via `label_thread` (recoverable for 30 days; this connector has no
permanent delete). Review the list first.

## Tests

```
python3 -m pytest -q        # or: uv run --with pytest python -m pytest -q
```

28 tests, written red→green (TDD). They cover date/address normalization, the
synthetic real-format page fixtures, output schemas, streaming/empty-input/
malformed-date edge cases, the min/max aggregation, the dormancy cutoff (incl.
leap-day), thread resolution with retain-protection, pagination stopping only
on a missing `nextPageToken`, transient-failure retry, and a mock asserting
Phase 1 calls **all and only** `search_threads`. No test touches the network
or a real address.
