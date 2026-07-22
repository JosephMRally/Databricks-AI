---
name: dormant-email-cleanup
description: >
  This skill is to architect, design, and program a skill and Python scripts that will do a single pass over an entire Gmail mailbox that records every email address seen in From / To / Cc / Bcc and tracks the EARLIEST and LATEST time each address appeared and write the results to a CSV file. Built on the `simplegmail` library (the JosephMRally `pagination` fork), which wraps the Gmail API. Use this to audit or clean up a mailbox by recency: find threads where the emails used have not heard from in years (an address is "dormant" when its latest-seen date is older than your cutoff), build a first/last-seen contact list, or prepare a list of stale correspondents and — as an optional, deliberate final step — trash their old mail with `scripts/delete_emails.py` (only ever run explicitly by the user, never automatically). Triggers on "clean up old contacts", "find people I haven't emailed in years", "who have I lost touch with", "audit my mailbox", "delete emails from old senders", or building an address first/last-seen list — even without the word "dormant".

  Only generate code; never run the pipeline scripts against the live mailbox. Running pytest is always fine.
---

# Mailbox Address Sweep (simplegmail → one pass → first/last-seen CSV → optional delete)
This skill was designed to run in Claude's Cowork. Only generate code; never run the pipeline scripts against the live mailbox — "do not execute" means live runs, and running pytest is always fine. Follow the Test Driven Development standards for generating code (red->green->refactor). Tests must not use real email addresses; use synthetic fixture data modeled on the shape of real `simplegmail` `Message` objects. Follow pytest convention for testing.

# Steps:
The development of each script must follow a strict Test Driven Development (TDD) loop. Do not proceed to the next step until the current step's tests pass successfully.

For each script, you must perform the following cycle:
1. **Red**: Translate the user stories into a `pytest` file only (no edits under `scripts/`), run it (it must fail), and show the failure output.
2. **Green**: Write/Edit the minimum amount of code required to make those specific tests pass; change nothing the tests don't force.
3. **Refactor**: Clean up on green, keeping tests passing.
4. **Commit**: Commit after each green so the next cycle has a baseline to demonstrate red against.

Never edit implementation and tests in the same step.

**Specific Constraints:**
- **Isolation**: One script/feature at a time. Do not combine multiple scripts into one response.
- **Mocking**: You must mock the `simplegmail` `Gmail` client and any network calls; do not attempt to connect to a live server.
- **Validation**: Every response that includes code must also include the output of a successful test run (or at least the command used to verify it).

**Order of Operations:**
1.  Execute TDD loop for `scripts/gather_emails.py`
2.  Execute TDD loop for `scripts/aggregate_emails.py`
3.  Execute TDD loop for `scripts/filter_emails.py`
4.  Execute TDD loop for `scripts/delete_emails.py`
5.  Review all four scripts and confirm they meet the requirements in their respective .md files.
6.  Verify any remaining edge cases (e.g., empty results, malformed dates).
7.  Update README.md document.
8. **Create or replace `SKILL.md`** — the operator's guide for running the
   pipeline. It must:
   - **Show how to run the four scripts in order** (`scripts/gather_emails.py`
     → `scripts/aggregate_emails.py` → `scripts/filter_emails.py`
     → `scripts/delete_emails.py`), with each command's inputs and outputs.
   - **Present the delete step as optional and destructive**: a separate,
     deliberate command the user runs themselves after reviewing the filter
     output — never automatic, never a side effect of the earlier phases.
   - **Say nothing about how Gmail is reached** — no `simplegmail` or Gmail API
     instructions, no explanation of how the connection works. The one and only
     thing to state is that `scripts/gather_emails.py` and
     `scripts/delete_emails.py` talk to Gmail themselves.
   - **Present the sweep as a single command, not an agent procedure.** The
     mailbox is far too large for the agent to page through in-conversation — it
     would exhaust the token/context budget and memory and be far too slow — so
     `gather_emails.py` owns the entire sweep, and `SKILL.md` must not turn it
     into steps the agent performs.
