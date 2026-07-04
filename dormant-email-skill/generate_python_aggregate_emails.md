# Generate python script

## User Stories
Following agile conventions, we want our user stories to be in the following format: `As a <actor> I want <requirement> so that <description>` will be written in shorthand as `<actor>|<requirement>|<description>`. User stories form the basis of tests and code.

<actor>|<requirement>|<description>
engineer | parse every raw `header_date` string from the extract (ISO-8601 with tz offset, or the raw RFC 2822 header) and normalize to UTC `YYYY-MM-DD` before any earliest/latest comparison | comparing mixed-format raw strings gives wrong earliest/latest — this phase owns the Transform of dates
engineer | when `header_date` is empty or unparseable, fall back to `internal_date` (epoch milliseconds -> UTC `YYYY-MM-DD`); skip the row and report it on stderr only when both are unusable | some messages have no `Date` header, but Gmail's `internalDate` always exists — every message can be dated
engineer | split each `|`-joined `emails` value into elements, split comma-separated addresses within an element, strip display names (`Alice <a@x.com>` -> `a@x.com`), lowercase, and dedup | the extract carries raw header values 1:1; this phase owns the Transform of addresses so downstream matching against user-entered addresses works
engineer | this script to be the Load and Transform (LT) of the ELT pipeline | the extract stays raw; this phase produces the typed, normalized data downstream phases consume
human | to know the earliest and latest date of every email thread | dormant threads can be identified in the next phase
agent | the input contract discovered at runtime — a sub agent reads `generate_python_gather_emails.md` and returns its output schema, default output filename, array delimiters, and known limitations — never hardcoded here | this spec cannot go stale when the extract's spec changes
engineer | stream-read the input CSV | the file could be larger than the amount of memory we have
engineer | the input path to default to the extract's default output filename, overridable via `--in` | the pipeline runs with no args while tests point at fixtures
engineer | aggregate with a dict/map: key=`thread_id`, value=tuple of [`earliest_date` (min function), `latest_date` (max function), `emails`, `message_ids`] | a single pass accumulates per-thread state
engineer | the result written to a single CSV file | the next phase consumes one file


## Function
Create a python script called `scripts/aggregate_emails.py`; do not execute! It is the **Load and Transform (LT) of the ELT pipeline** — the user stories above define its behavior.


## Output
name, type, format (optional)
`thread_id`, str
`earliest_date`, date, `YYYY-MM-DD`
`latest_date`, date, `YYYY-MM-DD`
`emails`, array<str>
`message_ids`, array<str>


# Finally
Follow strict TDD (see `generate_SKILL.md` and `CLAUDE.md`): write the tests derived from the user stories first and run them to show they fail (red) **before** changing any implementation; then implement until green and report both runs. Every user story must map to at least one test that was observed failing first. Commit after green.
