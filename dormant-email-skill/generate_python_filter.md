# Generate python script

## User Stories
Following agile conventions, we want our user stories to be in the following format: `As a <actor> I want <requirement> so that <description>` will be written in shorthand as `actor | requirement | description`. User stories form the basis of tests and code.

actor | requirement | description
human | a **delete list**: the addresses I have not heard from since the cutoff, with every address that should not be deleted filtered out | the separate cleanup step that follows only ever sees mail that is safe to remove
agent | the input contract discovered at runtime — a sub agent reads `generate_python_aggregate_emails.md` and returns its output schema, default output filename, array delimiters, and known limitations — never hardcoded here | this spec cannot go stale when the aggregate's spec changes
engineer | one output row per dormant **address**, aggregated across every thread it appears in: first seen = min of the threads' `earliest_date`, last seen = max of their `latest_date`, with all of its `thread_id`s and `message_id`s collected | an address still active in any thread is not dormant, and the cleanup step gets the message ids it needs
human | an address on the delete list only when its last-seen date is older than the cutoff (today − N years) | contacts I have not heard from since the cutoff are identified
human | to be prompted for email addresses to ignore, defaulting to the account owner's address | my own address is in every thread and must never appear on the delete list
engineer | the owner default inferred from the input data: the address that appears in the most threads in the input CSV | the owner is on essentially every thread of their own mailbox, so no Gmail auth is needed to identify them
human | to be prompted for email addresses to retain | contacts I choose are never on the delete list, whatever their dates say
human | to be prompted for an integer N for the cutoff (today − N years), defaulting to 5 | I control what counts as dormant without editing code
agent | every prompt also settable via CLI args (`--ignore`, `--retain`, `--years`), which skip that prompt; python args and exit codes are used | the LLM harness can run the script non-interactively and knows the status
engineer | "today" injectable via `--today YYYY-MM-DD`, defaulting to the current date | dormancy depends on the clock, so tests must be able to pin it
engineer | a single streaming sweep over the aggregate's output CSV, holding per-address state only — no second pass, no recency re-scan | `latest_date` already answers "have I heard from them since?", and the file could be larger than memory
engineer | this script reads the input CSV and writes the delete-list CSV and its companion Gmail-search text file, nothing else — no Gmail access, no deletion | deletion is a separate, deliberate action, never a side effect of computing the list; the `message_ids` column gives that step everything it needs
human | first-seen and last-seen dates on every delete-list row | I can review how stale each contact is before anything is deleted
engineer | the output written to a single CSV defaulting to `filtered_results.csv` (overridable via `--out`), with the input path defaulting to the aggregate's default output filename (overridable via `--in`) | the pipeline runs with no args while tests point at fixtures
engineer | the array columns (`thread_ids`, `message_ids`) in the output CSV to be `|`-delimited | consistent with the rest of the pipeline
engineer | test fixtures use fake addresses, and prompts are driven through CLI args or fed stdin in tests | tests are deterministic and touch no real account or terminal
human | to enter a bare domain (e.g. wm.com) in the ignore or retain inputs, matching every address at that domain or its subdomains | so I do not have to enter every address from that domain one by one
engineer | all email addresses and domains handled case-insensitively: every address or domain — from the input CSV or the ignore/retain inputs — is converted to lower case before any comparison | `Billing@WM.com` and `billing@wm.com` are the same sender, so matching never misses on capitalization
human | alongside the CSV, a text file of the delete-list addresses joined by " OR ", 30 addresses per line, each line a standalone Gmail search query, defaulting to `filtered_queries.txt` (overridable via `--queries-out`) | so I can paste a line into Gmail's search UI and review many dormant senders' mail at once
human | both output files ordered by `latest_date` DESC, ties broken by `email` A→Z | the most recently seen dormant contacts — the borderline calls — are at the top, and the order is deterministic


## Function
Create a python script called `scripts/filter_emails.py`; do not execute! It is the final **Filter phase of the ELT pipeline**: it turns the aggregate's per-thread CSV into a per-address **delete list**, filtering out every address that should not be deleted — the owner, ignored and retained addresses, and anyone heard from since the cutoff. The user stories above define its behavior.


## Output Schema
name, type, format (optional)
`email`, str, normalized (lowercase, bare address, as produced by the aggregate)
`earliest_date`, date, `YYYY-MM-DD`; first seen across all the address's threads
`latest_date`, date, `YYYY-MM-DD`; last seen across all the address's threads
`thread_ids`, array<str>, `|`-joined
`message_ids`, array<str>, `|`-joined


# Finally
Follow strict TDD (see `generate_SKILL.md` and `CLAUDE.md`): write the tests derived from the user stories first and run them to show they fail (red) **before** changing any implementation; then implement until green and report both runs. Every user story must map to at least one test that was observed failing first. Commit after green.
