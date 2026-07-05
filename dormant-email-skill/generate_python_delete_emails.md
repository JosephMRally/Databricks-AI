# Generate python script

## User Stories
Following agile conventions, we want our user stories to be in the following format: `As a <actor> I want <requirement> so that <description>` will be written in shorthand as `actor | requirement | description`. User stories form the basis of tests and code.

actor | requirement | description
agent | the input contract discovered at runtime — a sub agent reads `generate_python_filter_emails.md` and returns its output schema, default output filename, array delimiters, and known limitations — never hardcoded here | this spec cannot go stale when the filter's spec changes
human | a report of the threads deleted, by subject title and latest date | I can audit what was removed and see how stale each thread was
human | deletion to mean moving each thread to Gmail's Trash, never a permanent purge | anything removed by mistake stays recoverable
engineer | the input path to default to the filter's default output filename, overridable via `--in` | the pipeline runs with no args while tests point at fixtures
engineer | the same auth conventions as `scripts/gather_emails.py`: `~/gmail-token.json` / `~/client_secret.json` passed to the Gmail constructor, overridable via `--token` / `--client-secret`, with a clear error and non-zero exit code when neither exists | a saved token is reused and auth failures are understandable
agent | python args and exit codes are used | the LLM harness executing the code knows the status
engineer | tests to mock the `simplegmail` Gmail client, with fixtures using fake addresses — never a live mailbox | tests are deterministic and touch no real account


## Function
Create a python script called `scripts/delete_emails.py`; do not execute! It is the final **Delete phase of the ELT pipeline**: it moves the threads listed in the input CSV to Gmail's Trash (recoverable — never a permanent purge). It is only ever run explicitly by the user, never automatically. The user stories above define its behavior.


## Output Schema
name, type, format (optional)
`latest_date`, date, `YYYY-MM-DD`
`thread_ids`, str
`subject`, str


# Finally
Follow strict TDD (see `generate_SKILL.md` and `CLAUDE.md`): write the tests derived from the user stories first and run them to show they fail (red) **before** changing any implementation; then implement until green and report both runs. Every user story must map to at least one test that was observed failing first. Commit after green.
