# Generate python script

## User Stories
Following agile conventions, we want our user stories to be in the following format: `As a <actor> I want <requirement> so that <description>` will be written in shorthand as `<actor>|<requirement>|<description>`. User stories form the basis of tests and code.

<actor>|<requirement>|<description>


## Function
Create a python script called `scripts/aggregate_emails.py` that will stream in a CSV file and aggregate the emails to track the **earliest** and **latest** date of every email address. A dict/map type would be the perfect data type to perform this logic; key=email and value=(`earliest_date`, `latest_date`). The result should be written to a single CSV file with one row per address: `email`, `earliest_date`, `latest_date`. 


## Input
The occurrences CSV produced by `scripts/gather_emails.py` (Phase 1 is a raw Extract):
name, type, format (optional)
`date`, date, `YYYY-MM-DD`
`thread_id`, str
`message_id`, str
`emails`, array<str> (joined with `|`) — raw header values as-is: elements may carry display names (`Alice <alice@example.com>`), mixed case, or several comma-separated addresses in one element; this phase owns splitting and normalizing them
`label_ids`, array<str> (joined with `|`)


## Output
name, type, format (optional)
`earliest_date`, date, `YYYY-MM-DD`
`latest_date`, date, `YYYY-MM-DD`
`emails`, array<str>
`thread_id`, str


# Tests
- confirm the schema output is as above


# Finally
Follow strict TDD (see `generate_SKILL.md` and `CLAUDE.md`): write the tests derived from the user stories first and run them to show they fail (red) **before** changing any implementation; then implement until green and report both runs. Every user story must map to at least one test that was observed failing first. Commit after green.