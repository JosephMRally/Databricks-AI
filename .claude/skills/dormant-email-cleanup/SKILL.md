---
name: dormant-email-cleanup
description: >-
  Audit or clean up a Gmail mailbox by recency. Runs one pass over the whole
  mailbox, records every address seen in From/To/Cc/Bcc, tracks the earliest and
  latest date each appeared, then flags "dormant" addresses (latest-seen older
  than your cutoff, default 5 years) and resolves them to a list of stale thread
  ids. Use it to find people you haven't heard from in years, build a
  first/last-seen contact list, or produce a review list of old threads. It
  produces a list only — it never deletes anything. Make sure to use this skill
  whenever the user wants to "clean up old contacts", "find people I haven't
  emailed in years", "who have I lost touch with", "audit my mailbox", "delete
  emails from old senders", or build an address first/last-seen list — even
  without the word "dormant".
---

# Dormant-email cleanup

Run three scripts in order to turn a Gmail mailbox into a reviewed list of stale
thread ids:

```
gather_emails.py ─▶ occurrences.csv ─▶ aggregate_emails.py ─▶ contacts_first_last_seen.csv
                                                                        │
                            dormant_threads.csv ◀── filter_emails.py ◀──┘  (+ occurrences.csv)
```

`scripts/gather_emails.py` calls the Gmail MCP connector itself. The other two
scripts are local CSV passes. Requires `python3`.

## How to run

Run the scripts in this order.

### 1. Gather — sweep the mailbox

```
python3 scripts/gather_emails.py --out occurrences.csv
```

- **Input:** none — the script sweeps the entire mailbox on its own.
- **Output:** `occurrences.csv` — one row per (message, address) occurrence:
  `date, thread_id, message_id, email, labelIds`.

### 2. Aggregate — first/last-seen per address

```
python3 scripts/aggregate_emails.py --in occurrences.csv --out contacts_first_last_seen.csv
```

- **Input:** `occurrences.csv` (from step 1).
- **Output:** `contacts_first_last_seen.csv` — one row per address:
  `email, earliest_date, latest_date`. This is the first/last-seen contact list.

### 3. Filter — flag dormant, resolve to threads

Interactive — prompts for addresses to ignore (the owner defaults in), addresses
to retain, and the cutoff in whole years (default 5):

```
python3 scripts/filter_emails.py \
  --aggregate contacts_first_last_seen.csv \
  --occurrences occurrences.csv \
  --owner you@gmail.com
```

Non-interactive — pre-answer the prompts (empty string = "none"):

```
python3 scripts/filter_emails.py \
  --aggregate contacts_first_last_seen.csv \
  --occurrences occurrences.csv \
  --owner you@gmail.com \
  --years 5 --ignore "" --retain "keep@x.com"
```

- **Input:** `contacts_first_last_seen.csv` and `occurrences.csv`.
- **Output:** `dormant_threads.csv` — one `thread_id` per row, for you to review.

An address is **dormant** when its `latest_date` is older than `today − N years`.
A thread is written when it contains **≥1 dormant address** and **no retained
address** — one retained address protects the whole thread. Ignored addresses
(the owner defaults in via `--owner`; its `+` aliases are worth adding too) are
never dormant.

## Output schemas

| Step | File | Columns |
|------|------|---------|
| 1 | `occurrences.csv` | `date`(YYYY-MM-DD), `thread_id`, `message_id`, `email`, `labelIds` |
| 2 | `contacts_first_last_seen.csv` | `email`, `earliest_date`, `latest_date` |
| 3 | `dormant_threads.csv` | `thread_id` |

`labelIds` is a `|`-joined array. Rows with a blank/malformed date or no real
address are dropped.

## Safety

The pipeline only *decides*: its final output is `dormant_threads.csv`, a list of
thread ids for you to review. It never deletes, trashes, or modifies any mail.

## Tests

```
python3 -m pytest -q
```

28 tests, TDD (red→green), fully mocked — no test touches the network or a real
address.
