---
name: dormant-email-cleanup
description: >
  This skill is to architect, design, and program a skill and Python scripts that will do a single pass over an entire Gmail mailbox that records every email address seen in From / To / Cc / Bcc and tracks the EARLIEST and LATEST time each address appeared and write the results to a CSV file. Built for the Gmail MCP connector. Use this to audit or clean up a mailbox by recency: find threads where the emails used have not heard from in years (an address is "dormant" when its latest-seen date is older than your cutoff), build a first/last-seen contact list, or prepare a list of stale correspondents before optionally trashing their old mail. Triggers on "clean up old contacts", "find people I haven't emailed in years", "who have I lost touch with", "audit my mailbox", "delete emails from old senders", or building an address first/last-seen list — even without the word "dormant".

  Only generate code; do not execute code.
---

# Mailbox Address Sweep (Gmail MCP → one pass → first/last-seen CSV)
This skill was designed to run in claude's cowork. Only generate code; do not execute code. Follow the Test Driven Development standards for generating code (red->yellow->green). Tests should not use real emails addresses; it is okay to use the MCP server to create synthetic data. Follow pytest convention for testing.

The development of each script must follow a strict Test Driven Development (TDD) loop. Do not proceed to the next step until the current step's tests pass successfully.

# Steps:
The development of each script must follow a strict Test Driven Development (TDD) loop. Do not proceed to the next step until the current step's tests pass successfully.

For each script, you must perform the following cycle:
1. **Red**: Write a `pytest` file that defines the expected behavior and runs it (it must fail). Show the failure output.
2. **Yellow**: Write/Edit the minimum amount of code required to make that specific test pass.
3. **Green**: Run the tests again to verify success.

**Specific Constraints:**
- **Isolation**: One script/feature at a time. Do not combine multiple scripts into one response.
- **Mocking**: You must mock the `GmailMCPClient` and any network calls; do not attempt to connect to a live server.
- **Validation**: Every response that includes code must also include the output of a successful test run (or at least the command used to verify it).

**Order of Operations:**
1.  Execute TDD loop for `scripts/gather_emails.py`
2.  Execute TDD loop for `scripts/aggregate_emails.py`
3.  Execute TDD loop for `scripts/filter_emails.py`
4.  Review all three scripts and confirm they meet the requirements in their respective .md files.
5.  Verify any remaining edge cases (e.g., empty results, malformed dates).
6.  Update README.md document.
7. **Create or replace `SKILL.md`** — the operator's guide for running the
   pipeline. It must:
   - **Show how to run the three scripts in order** (`scripts/gather_emails.py`
     → `scripts/aggregate_emails.py` → `scripts/filter_emails.py`), with each
     command's inputs and outputs.
   - **Say nothing about the Gmail MCP connector** — no instructions for calling
     it, no explanation of how it works. The one and only thing to state is that
     `scripts/gather_emails.py` calls the connector itself.
   - **Present the sweep as a single command, not an agent procedure.** The
     mailbox is far too large for the agent to page through in-conversation — it
     would exhaust the token/context budget and memory and be far too slow — so
     `gather_emails.py` owns the entire sweep, and `SKILL.md` must not turn it
     into steps the agent performs.
