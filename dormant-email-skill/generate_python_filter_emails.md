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
human | to be prompted for email addresses to retain | mail involving contacts I choose must never be deleted, whatever their dates say
engineer | **retain excludes at thread level**: an address matching a retain entry (exact address, or domain/subdomain) is removed from the output AND every thread it appears in is protected — those `thread_id`s and `message_id`s never appear in any output row, and an address left with no unprotected threads is dropped from the list | deleting a dormant contact's copy of a shared thread would delete the retained contact's mail too, so protected threads are untouchable through anyone
engineer | first/last-seen dates and dormancy still computed across ALL of an address's threads, including protected ones | a contact heard from recently in a protected thread is not dormant, and the dates describe the contact, not just the deletable subset
engineer | **ignore excludes at address level only**: an ignored address never appears as an output row, but threads containing it stay eligible | the owner is on essentially every thread — thread-level exclusion for ignore would empty the delete list
human | to be prompted for an integer N for the cutoff (today − N years), defaulting to 5 | I control what counts as dormant without editing code
agent | every prompt also settable via CLI args (`--ignore FILE`, `--retain FILE`, `--years N`), which skip that prompt; python args and exit codes are used | the LLM harness can run the script non-interactively and knows the status
engineer | `--ignore` and `--retain` take a filename read as one address or bare domain per line (blank lines skipped, entries lowercased); an empty argument means no entries; a missing file is a clear error with a non-zero exit code | long ignore/retain lists live in versionable files instead of shell one-liners, and the prompts stay for quick interactive use
engineer | "today" injectable via `--today YYYY-MM-DD`, defaulting to the current date | dormancy depends on the clock, so tests must be able to pin it
engineer | a single streaming sweep over the aggregate's output CSV, holding per-address state only — no second pass, no recency re-scan | `latest_date` already answers "have I heard from them since?", and the file could be larger than memory
engineer | this script reads the input CSV and writes the delete-list CSV and its companion Gmail-search text file, nothing else — no Gmail access, no deletion | deletion is a separate, deliberate action, never a side effect of computing the list; the `message_ids` column gives that step everything it needs
human | first-seen and last-seen dates on every delete-list row | I can review how stale each contact is before anything is deleted
engineer | the output written to a single CSV defaulting to `filtered_results.csv` (overridable via `--out`), with the input path defaulting to the aggregate's default output filename (overridable via `--in`) | the pipeline runs with no args while tests point at fixtures
engineer | the array columns (`thread_ids`, `message_ids`) in the output CSV to be `|`-delimited | consistent with the rest of the pipeline
engineer | test fixtures use fake addresses, and prompts are driven through CLI args or fed stdin in tests | tests are deterministic and touch no real account or terminal
human | to enter a bare domain (e.g. wm.com) in the ignore or retain inputs, matching every address at that domain or its subdomains | so I do not have to enter every address from that domain one by one
engineer | every email address and domain from every source — the input CSV, the ignore/retain prompts, and the CLI args — converted to lower case before any processing (state building, owner inference, matching, output) | `Billing@WM.com` and `billing@wm.com` are the same sender, so no source's capitalization can ever cause a missed match or a duplicate row
human | alongside the CSV, a text file of the delete-list addresses, one address per line, defaulting to `filtered_queries.txt` (overridable via `--queries-out`) | a plain list is easy to copy-paste and easy for other tools to consume line by line
human | both output files ordered by domain, then subdomain, then username, all ascending — sort key: the reversed domain labels (`com`, `wm`, `notify`), then the local part | addresses from the same organization sit together, a domain's subdomains right after it, so I can review and prune sender by sender


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
