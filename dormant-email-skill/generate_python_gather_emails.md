# Generate python script
## Function
Create a python script called `scripts/gather_emails.py`; do not execute! The script should be a Facade over the `simplegmail` library that hides the Gmail API behind one simple call. This script is the **Extract (E) of an ELT pipeline**: running it once does a single sweep over the whole mailbox and, for every message, records the raw From, To, Cc, and Bcc values and both raw dates (the `header_date` aka Date-header-derived string and Gmail's `internalDate`), all as-is — no transformations of any kind; parsing and normalization belong to later phases. The script owns the entire sweep, so the agent never pages the mailbox or holds raw messages in context.


## User Stories
Following agile conventions, we want our user stories to be in the following format: `As a <actor> I want <requirement> so that <description>` will be written in shorthand as `<actor>|<requirement>|<description>`. User stories form the basis of tests and code.

actor | requirement | description
engineer | tests to mock the `simplegmail` Gmail client | all tests are deterministic and reproducible
engineer | test fixtures modeled on the shape of real `simplegmail` `Message` objects, using fake addresses | tests are realistic yet deterministic and touch no real account
human | to know all email address values per message per thread | a full summary of an email thread's start and end can be understood
engineer | this script to be the Extract (E) of an ELT pipeline: no transformation of any source value | downstream phases own all parsing, normalization, and typing
human | both dates carried as-is with no parsing or conversion: `header_date` (the raw `simplegmail` date string, derived from the message's `Date` header) and Gmail's `internalDate` (epoch-milliseconds string, the server receive time) | this phase is Extract-only; date normalization happens in a later phase
engineer | read the header date off each `simplegmail` `Message` from the fork's `Message.headerDate` (a `str`; the fork renamed upstream's `Message.date`, which no longer exists; also accept a `header_date` attribute; emit an empty cell when neither is present or the value is empty/None) | the raw `Date`-header string actually lands in the `header_date` column instead of a silently empty cell
engineer | read Gmail's `internalDate` off each `simplegmail` `Message` (the fork exposes `Message.internalDate`, an `Optional[int]` of epoch milliseconds; also accept an `internal_date` attribute; emit an empty cell when neither is present or the value is None) | some messages have no `Date` header at all, but `internalDate` always exists — a later phase can date every message
human | read `sender`, `recipient`, `cc`, and `bcc` off each `simplegmail` `Message` | every From/To/Cc/Bcc value is captured
engineer | the output to be streamed to a single CSV file | the file itself could be larger than the amount of memory we have
engineer | the output filename should default to `gathered_results.csv` (overridable via `--out` for tests and ad-hoc runs) | so that the next step knows what it needs to load
engineer | the array columns (`emails`, `label_ids`) in the output CSV to be `|`-delimited | arrays of strings can be split apart in the next phase
engineer | use [`simplegmail`](https://github.com/JosephMRally/simplegmail/tree/pagination) (it is already installed) to connect to Gmail | it wraps the Gmail API and speeds up development
human | a clear error message and non-zero exit code when neither the saved token (`~/gmail-token.json`) nor the OAuth client (`~/client_secret.json`) exists | so that the user understands why authentication cannot proceed and how to fix it
agent | python args and exit codes are used | so that LLM harness executing the code knows the status
engineer | pass both `~/gmail-token.json` (creds_file) and `~/client_secret.json` (client_secret_file) to the Gmail constructor; a valid saved token is reused | so that signing in isnt necessary a second time
engineer | include a flag for logging | so that i can see messages are being processed for testing
human | treat `sender` as strings and `cc`/`bcc`/`recipient` as lists of strings (any may be empty/None), carrying every value as-is — no parsing, validation, normalization, or dedup | the output stays 1:1 with the source and all transformations happen in later phases
engineer | exactly one row per message, even when all address fields are empty | every source message is represented 1:1 in the extract

## Input
Phase 1 reads the mailbox through the `simplegmail` library, which wraps the Gmail API — there is no MCP connector involved. Authentication is Google OAuth: use the `~/client_secret.json` (an OAuth client from the Google Cloud Console) in the constructor.  The first run opens a browser to authorize and writes `~/gmail-token.json` for reuse, and IMAP must be enabled on the account. Because the first run needs a browser, provision `~/gmail-token.json` in an environment that has one — the script cannot authenticate headless on a cold start.

When running the sweep, pass `--verbose` to watch messages being processed (logging is off by default).


## Output Schema
The output should be streamed to a single CSV — exactly one row per message, 1:1 with the source (a message with no addresses still yields a row with an empty `emails` cell):
name, type, format (optional)
`header_date`, str, ISO-8601 with tz offset or raw RFC 2822; empty when the message has no `Date` header
`internal_date`, str, epoch milliseconds; present for every message
`thread_id`, str
`message_id`, str
`emails`, array<str>, `|`-joined; `sender`, `recipient`, `cc`, `bcc` order with empty fields omitted (position does not identify the source field)
`label_ids`, array<str>, `|`-joined

Known limitation: `|` is technically legal inside an RFC 5322 address local part and would corrupt the `|`-join, but Gmail addresses cannot contain `|` — accepted for this tool.

# Finally
Follow strict TDD (see `generate_SKILL.md` and `CLAUDE.md`): write the tests derived from the user stories first and run them to show they fail (red) **before** changing any implementation; then implement until green and report both runs. Every user story must map to at least one test that was observed failing first. Commit after green.