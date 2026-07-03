# dormant-email-skill

An ELT pipeline of three Python scripts (`gather` → `aggregate` → `filter`) generated from spec files: `generate_SKILL.md` defines the overall process, and each `generate_python_*.md` is the spec for one script. User stories in the specs are the source of truth for tests and code.

## TDD is mandatory

When executing or re-executing any `generate_*.md` spec — including small schema changes to already-working code — follow the strict loop from `generate_SKILL.md`:

1. **Red**: translate the changed user stories into tests only (no edits under `scripts/`), run pytest, and show the failing output.
2. **Green**: write the minimum implementation to make those tests pass; change nothing the tests don't force.
3. **Refactor** on green, keeping tests passing.
4. Commit after each green so the next cycle has a baseline to demonstrate red against.

Never edit implementation and tests in the same step.

## Running tests

```
.venv/bin/python -m pytest tests/test_gather_emails.py -q
```

Use `.venv/bin/python` — pytest is installed in the project venv, not globally. `tests/test_aggregate_emails.py` and `tests/test_filter_emails.py` predate their scripts (not yet regenerated) and fail at import; scope test runs until those phases are executed.

## Other rules

- Do not run the pipeline scripts against the live mailbox unless explicitly asked — "do not execute" in the specs refers to live runs; running pytest is always fine.
- Tests must mock `simplegmail` (the installed package is the JosephMRally `pagination` fork); no real addresses or credentials in fixtures.
