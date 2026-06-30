---
name: dormant-email-cleanup
description: >
  Purpose of this skill is to create a python script that will do a one pass over an entire Gmail mailbox that records every email address seen in From / To / Cc / Bcc and tracks the EARLIEST and LATEST time each address appeared, written to a CSV. Built for the Gmail MCP connector. Use this to audit or clean up a mailbox by recency: find people or senders you have not heard from in years (an address is "dormant" when its latest-seen date is older than your cutoff), build a first/last-seen contact list, or prepare a list of stale correspondents before optionally trashing their old mail. Triggers on "clean up old contacts", "find people I haven't emailed in years", "who have I lost touch with", "audit my mailbox", "delete emails from old senders", or building an address first/last-seen list — even without the word "dormant".
---

# Mailbox Address Sweep (Gmail MCP → one pass → first/last-seen CSV)


## Phase 1
Create a python script that will do a single sweep over the whole mailbox. For **every message**, record each address in **From, To, Cc, and Bcc**, and date that address was ever seen. Communicate directly with the MCP server, page through `search_threads` over all mail and extract all requested info. The result should be streamed to a single CSV called `phase1.csv` — one row per email address per occurance: email, date


## Phase 2
Create a python script that will do a single sweep over the CSV file created in Phase 1. It should do an aggregate function to track the **earliest** and **latest** date of every email address. A dict/map type would be the perfect data type to perform this logic; for dates use `YYYY-MM-DD`. The result should be written to a single CSV called `phase2.csv` — one row per address: email, earliest_date, latest_date 


## Phase 3
Create a python script that will do a single sweep over the CSV file created in Phase 2.  First, prompt the user for email addresses that should be ignored; the account owners email should default. Second, prompt the user for email addresses that should be retained. Third, prompt the user for an integer to the cutoff (today − N years). Fourth, Everything downstream is a filter on that CSV: an address is **dormant** if its `latest_date` is older than your cutoff (today − N years); a **first/last-seen contact list** is the CSV itself; and an optional cleanup step trashes the old mail of the addresses you choose. There is no second pass and no recency re-scan — `latest_date` already answers "have I heard from them since?".  The result should be written to a single CSV called `phase3.csv` — one row per address per file: email, earliest_date, latest_date 


## Phase 4 trash a dormant address's old mail
Create a python script that will read CSV file created in Phase 3. It should do the following...
1. For each chosen address, `search_threads` `({from:X to:X cc:X bcc:X})` (no date filter — a date filter is thread-level and would skip revived threads that still hold old mail).
2. **Thread-level matching caveat:** Gmail returns a whole thread if ANY email matches — even a body-only or Bcc match, even one outside your window. Confirm that all emails associated with the thread are in `phase 3.csv` with the exception of the account owners email.
3. Before trashing, confirm the target is a **visible header party** of a dated message, then classify per message:
   trashable iff `date < cutoff` AND not `STARRED`.
   - Whole thread trashable → `label_thread(threadId, ["TRASH"])`.
   - Mixed → `label_message` only the trashable messages; leave recent/starred ones.
   - **Collateral guard:** if the thread is really an active contact's conversation and the
     dormant address was only cc'd, preserve it and tell the user.
4. Re-run the batch (Trash drops out of the default search) until it returns empty; retry transient errors.


## Phase 5
Prompt the user `that all python scripts have been created` and if they are ready to proceed in the execution of those python scripts. Only then execute the script(s) based on user's wishes.


## Tools (Gmail MCP)
- `search_threads` — the read that produces Phase 1's input. Returns THREADS, each with
  its messages' `date / id / labelIds / sender / toRecipients / ccRecipients /
  bccRecipients`, max `pageSize` 50. Use `view=THREAD_VIEW_METADATA_ONLY` (headers + date
  + labels, no bodies).
- `label_thread` / `label_message` — only for the OPTIONAL trash step *after Phase 3*; add
  the system label `TRASH` (recoverable 30 days; there is no permanent-delete and no
  Contacts API through this connector).
- **`resultCountEstimate` is unreliable** — it can be a stuck placeholder (e.g. "201")
  that never moves. The only signal that pagination is finished is a **missing
  `nextPageToken`**.
- **Retry transient failures** ("service is currently unavailable"; a first write may
  say "requires additional permissions") — just resend the one call.

## Fetching the mail (Phase 1's input)
Phase 1 works over the mailbox as local JSON pages. In Cowork the OAuth connector is
callable only by the agent, so the agent pages `search_threads` and saves each page; then
`phase1.py` reads those files. (If you instead run this where the Gmail MCP is exposed to
Python — e.g. a local stdio MCP server with your own credentials — `phase1.py` can page
`search_threads` itself. As built, it reads the saved pages.)

1. `search_threads` with `view=THREAD_VIEW_METADATA_ONLY`, `pageSize=50`. For **all mail**
   leave the query empty (the default already excludes Spam and Trash); to literally
   include **every** email — Spam and Trash too — use `query="in:anywhere"`.
2. **Save each page's raw JSON verbatim** to `pages/page_001.json`, `page_002.json`, … as
   it arrives. Do not reshape it. Paginate with `pageToken` **until there is no
   `nextPageToken`**.

### Scale (read before fetching a big mailbox)
A whole-mailbox fetch can be many dozens — sometimes 100+ — pages of 50 threads.
- **Stream each page straight to a file, not back into the conversation.** The scripts
  read the files; the model never has to hold the raw pages.
- **Only Phase 1's fetch touches the network; Phases 2–3 are local CSV passes.** The fetch
  is a single ordered walk — `pageToken` is opaque, so it cannot be parallelized or sharded.
- **Delegate the fetch to a worker** when it is large: spawn a subagent whose only job is
  to page through `search_threads` and save the JSON files, returning just the page count
  and the final `pageToken`; resume with another worker from that token if needed.
- **Checkpoint with the user** if it runs very long — exhaustive vs. a recent slice.

## Execution
Run the three scripts in order; each reads the previous one's CSV:
```
# 0. Agent has saved the mailbox to pages/*.json (see "Fetching the mail")
python3 scripts/phase1.py pages/*.json   > phase1.csv   # email,date  (one row per occurrence)
python3 scripts/phase2.py phase1.csv     > phase2.csv   # email,earliest_date,latest_date
python3 scripts/phase3.py phase2.csv     > phase3.csv   # dormant subset
```
- **Phase 1** records every address in From/To/Cc/Bcc of every message — STARRED and TRASH
  included — and falls back to the message-id hex timestamp when a `date` header is
  missing. `--exclude ADDR` optionally skips an address up front.
- **Phase 2** aggregates with a dict to earliest/latest per address, sorted
  most-recently-seen first.
- **Phase 3** prompts for **ignore** (drop entirely — e.g. your own address), **retain**
  (protect — never list as dormant), and **N** (cutoff = today − N years), then writes the
  dormant set (`latest_date` < cutoff, minus ignored/retained). For unattended/agent runs
  pass `--years N --ignore … --retain …` (and `--today YYYY-MM-DD` to pin the cutoff); with
  no `--years` it prompts. ignore/retain matching is Gmail dot/plus-insensitive.

## Reading the outputs
- `phase2.csv` is your **first/last-seen contact list** (every address, earliest + latest).
- `phase3.csv` is the **dormant set** Phase 3 selected.
- Put **personal, legal/government, and financial** addresses on the Phase 3 **retain**
  list — keep them out of the dormant set by default even when technically dormant.

## Gotchas
- **Phase 1 is robust to thread-level matching** — it records exact per-message headers and
  dates, so a thread that rode along on a body match contributes only the real header
  parties of each dated message. Thread-matching only needs care in the optional trash step.
- `resultCountEstimate` is unreliable; only a missing `nextPageToken` ends pagination.
- **Drop your own address(es)** via the Phase 3 *ignore* list (or a Phase 1 `--exclude`),
  or you top your own list.
- Phase 1 records `email,date` only — it does **not** keep the role, so you cannot later
  tell a Bcc-only contact from a primary one. Add a role column to Phase 1 if you need that.
- No permanent delete and no Contacts API here; Trash is recoverable for 30 days. Offer to
  hand `phase2.csv`/`phase3.csv` to the user for manual Google Contacts pruning.
- Address typos/variants in old mail (`…@hotmail.con`) are distinct strings — treated
  literally.
- `tests/test_pipeline.py` (30 checks over a schema-faithful mock) must print `ALL PASSED`
  after any change to the scripts.
