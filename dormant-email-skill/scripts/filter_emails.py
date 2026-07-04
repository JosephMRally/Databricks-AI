"""Phase 3 / Filter — turn the aggregate CSV into a per-address delete list.

Reads the aggregate's per-thread CSV (thread_id, earliest_date, latest_date,
emails, message_ids — contract discovered from
generate_python_aggregate_emails.md) in a single streaming sweep, building
per-address state only: first seen = min of the threads' earliest_date, last
seen = max of their latest_date, with every thread_id and message_id the
address appears with. Everything after that one pass is a filter — no second
pass, no recency re-scan; `latest_date` already answers "have I heard from
them since?".

An address lands on the delete list only when its last-seen date is strictly
older than the cutoff (today − N years) and it is neither ignored nor
retained. Ignore/retain entries are exact addresses or bare domains (e.g.
``wm.com``, covering the domain and its subdomains), and every address and
entry is lowercased before comparison, whatever case the CSV or the user
supplies. The ignore prompt defaults to the inferred account owner — the
address appearing in the most threads, since the owner is on essentially
every thread of their own mailbox. Each prompt is skipped when the matching
CLI arg (--ignore / --retain / --years) is given, and --today pins the clock
so runs and tests are deterministic.

Alongside the CSV, the delete-list addresses are also written as ready-to-paste
Gmail search queries (" OR "-joined, 30 per line, each line standalone) to
`filtered_queries.txt` next to the CSV, overridable via --queries-out.

This script reads the input CSV and writes those two files, nothing else:
no Gmail access and no deletion. Deletion is a separate, deliberate step; the
`message_ids` column carries everything it needs.
"""

import argparse
import csv
import os
import sys
from datetime import date

CSV_HEADER = ["email", "earliest_date", "latest_date", "thread_ids", "message_ids"]
ARRAY_DELIMITER = "|"
# The pipeline contract: aggregate_emails.py writes this by default.
DEFAULT_IN = "aggregated_results.csv"
DEFAULT_OUT = "filtered_results.csv"
# Written alongside the delete-list CSV (same directory as --out).
DEFAULT_QUERIES_OUT = "filtered_queries.txt"
DEFAULT_YEARS = 5
# Gmail's search box has practical length limits, so queries are chunked.
ADDRESSES_PER_QUERY_LINE = 30


def build_address_state(rows):
    """One streaming pass over aggregate rows -> per-address state.

    Returns ``{email: [earliest, latest, thread_ids, message_ids]}`` where
    earliest/latest are min/max of the YYYY-MM-DD strings across every thread
    the address appears in, and thread_ids/message_ids collect those threads'
    ids in input order.
    """
    state = {}
    for r in rows:
        thread_id = r.get("thread_id", "") or ""
        earliest = r.get("earliest_date", "") or ""
        latest = r.get("latest_date", "") or ""
        message_ids = [m for m in (r.get("message_ids") or "").split(ARRAY_DELIMITER) if m]
        for email in (r.get("emails") or "").split(ARRAY_DELIMITER):
            if not email:
                continue
            # the aggregate emits lowercase, but don't trust a hand-edited
            # CSV: everything is compared lowercase
            email = email.lower()
            entry = state.setdefault(email, [earliest, latest, [], []])
            entry[0] = min(entry[0], earliest)
            entry[1] = max(entry[1], latest)
            entry[2].append(thread_id)
            entry[3].extend(message_ids)
    return state


def infer_owner(state):
    """The address appearing in the most threads; ``None`` for empty input.

    The owner is on essentially every thread of their own mailbox, so this
    needs no Gmail auth. First-seen order breaks ties.
    """
    owner, most = None, 0
    for email, entry in state.items():
        if len(entry[2]) > most:
            owner, most = email, len(entry[2])
    return owner


def years_before(day, n):
    """``day`` minus ``n`` calendar years; Feb 29 clamps to Feb 28."""
    try:
        return day.replace(year=day.year - n)
    except ValueError:
        return day.replace(year=day.year - n, day=28)


def _excluded(email, exclude):
    """True when ``email`` is covered by an exclude entry (all lowercase).

    An entry with an ``@`` is an exact address; a bare entry (e.g. ``wm.com``)
    is a domain and covers the address's domain and its subdomains — matched
    after the ``@`` only, never against a look-alike local part.
    """
    if email in exclude:
        return True
    domain = email.rsplit("@", 1)[-1]
    return any(
        "@" not in entry and (domain == entry or domain.endswith("." + entry))
        for entry in exclude
    )


def select_dormant(state, cutoff, exclude):
    """The delete list: state filtered to dormant, non-excluded addresses.

    Dormant is strict: last seen older than ``cutoff`` (a ``date``); an
    address last seen on the cutoff day itself is kept off the list.
    ``exclude`` holds exact addresses and/or bare domains (see ``_excluded``).

    The result is ordered by last seen DESC with ties broken by email A->Z,
    so both output files (CSV and Gmail queries) inherit the order: the most
    recently seen — borderline — contacts come first.
    """
    result = {}
    for email, entry in state.items():
        if _excluded(email, exclude):
            continue
        if date.fromisoformat(entry[1]) < cutoff:
            result[email] = entry
    ordered = sorted(result.items(), key=lambda kv: kv[0])
    ordered.sort(key=lambda kv: kv[1][1], reverse=True)  # stable: email ASC kept
    return dict(ordered)


def format_queries(emails, per_line=ADDRESSES_PER_QUERY_LINE):
    """Delete-list addresses -> standalone Gmail search queries.

    Each returned line is ``per_line`` addresses joined by ``" OR "``, ready
    to paste into Gmail's search UI; the last line holds the remainder.
    """
    return [" OR ".join(emails[i:i + per_line])
            for i in range(0, len(emails), per_line)]


def _parse_addresses(text):
    """Comma-separated addresses or bare domains -> stripped, lowercased,
    empties dropped."""
    return [a.strip().lower() for a in (text or "").split(",") if a.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Filter the aggregate CSV down to a per-address delete "
                    "list of dormant contacts (the Filter of the ELT)."
    )
    parser.add_argument("--in", dest="in_path", default=DEFAULT_IN,
                        help=f"input CSV from aggregate_emails.py (default: {DEFAULT_IN})")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help=f"output delete-list CSV (default: {DEFAULT_OUT})")
    parser.add_argument("--queries-out", default=None,
                        help="output Gmail-search text file (default: "
                             f"{DEFAULT_QUERIES_OUT} alongside the CSV)")
    parser.add_argument("--ignore", default=None,
                        help="comma-separated addresses or bare domains to "
                             "ignore; skips the prompt (prompt default: the "
                             "inferred owner)")
    parser.add_argument("--retain", default=None,
                        help="comma-separated addresses or bare domains to "
                             "retain; skips the prompt")
    parser.add_argument("--years", type=int, default=None,
                        help=f"dormancy cutoff in years; skips the prompt "
                             f"(default: {DEFAULT_YEARS})")
    parser.add_argument("--today", default=None,
                        help="YYYY-MM-DD to compute the cutoff from "
                             "(default: the current date); pins dormancy for tests")
    args = parser.parse_args(argv)

    if not os.path.exists(args.in_path):
        print(
            f"error: input CSV not found: {args.in_path}\n"
            f"Run scripts/aggregate_emails.py first (it writes {DEFAULT_IN}), "
            "or pass --in PATH.",
            file=sys.stderr,
        )
        return 2

    with open(args.in_path, newline="", encoding="utf-8") as fh:
        state = build_address_state(csv.DictReader(fh))

    if args.ignore is not None:
        ignore = _parse_addresses(args.ignore)
    else:
        owner = infer_owner(state)
        resp = input(f"Addresses to ignore, comma-separated "
                     f"[default: {owner or 'none'}]: ").strip()
        ignore = _parse_addresses(resp) if resp else ([owner] if owner else [])

    if args.retain is not None:
        retain = _parse_addresses(args.retain)
    else:
        retain = _parse_addresses(
            input("Addresses to retain, comma-separated [default: none]: "))

    if args.years is not None:
        years = args.years
    else:
        resp = input(f"Dormancy cutoff in years [default: {DEFAULT_YEARS}]: ").strip()
        years = int(resp) if resp else DEFAULT_YEARS

    today = date.fromisoformat(args.today) if args.today else date.today()
    cutoff = years_before(today, years)
    selected = select_dormant(state, cutoff, set(ignore) | set(retain))

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for email, (earliest, latest, thread_ids, message_ids) in selected.items():
            writer.writerow([
                email, earliest, latest,
                ARRAY_DELIMITER.join(thread_ids),
                ARRAY_DELIMITER.join(message_ids),
            ])

    queries_out = args.queries_out or os.path.join(
        os.path.dirname(args.out) or ".", DEFAULT_QUERIES_OUT)
    lines = format_queries(list(selected))
    with open(queries_out, "w", encoding="utf-8") as fh:
        fh.writelines(line + "\n" for line in lines)

    print(f"wrote {len(selected)} address rows to {args.out} "
          f"and {len(lines)} Gmail search queries to {queries_out} "
          f"(dormant before {cutoff.isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
