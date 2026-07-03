# Generate python script

## Function
Create a python script called `scripts/filter_emails.py` that will:
1. Prompt the user for email addresses that should be ignored; the account owners email should default. 
2. Prompt the user for email addresses that should be retained. 
3. Prompt the user for an integer to the cutoff (today − N years); default to 5 years.
4. Do a single sweep over the CSV file.  
5. Everything downstream is a filter on that CSV: an address is **dormant** if its `latest_date` is older than your cutoff (today − N years); a **first/last-seen contact list** is the CSV itself; and an optional cleanup step trashes the old mail of the addresses you choose. There is no second pass and no recency re-scan — `latest_date` already answers "have I heard from them since?"


## Input
name, type, format (optional)
`email`, str
`thread_id`, str
`message_id`, str
`earliest_date`, date, `YYYY-MM-DD`
`latest_date`, date, `YYYY-MM-DD`


## Output
`thread_id`, str


# Tests


# Finally
Follow strict TDD (see `generate_SKILL.md` and `CLAUDE.md`): write the tests derived from the user stories first and run them to show they fail (red) **before** changing any implementation; then implement until green and report both runs. Every user story must map to at least one test that was observed failing first. Commit after green.
