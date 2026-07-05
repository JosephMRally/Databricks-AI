"""Phase 3 / Filter — turn the aggregate CSV into a delete list, one row per
dormant address per deletable thread.

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
supplies. Non-interactively they come from files (--ignore FILE /
--retain FILE, one entry per line, blank lines skipped; an empty argument
means no entries); the prompts accept comma-separated entries directly. The two exclusions differ in strength: ignore is address-level
(the owner is on every thread, so their presence protects nothing), while
retain is thread-level — every thread a retained contact appears in is
protected, its thread/message ids never reach the output through anyone,
and dormancy/dates still reflect the whole history (see ``select_dormant``). The ignore prompt defaults to the inferred account owner — the
address appearing in the most threads, since the owner is on essentially
every thread of their own mailbox. Each prompt is skipped when the matching
CLI arg (--ignore / --retain / --years) is given, and --today pins the clock
so runs and tests are deterministic.

Alongside the CSV, the delete-list addresses are also written as a plain
list, one address per line, to `filtered_queries.txt` next to the CSV,
overridable via --queries-out.

This script reads the input CSV and writes those two files, nothing else:
no Gmail access and no deletion. Deletion is a separate, deliberate step; the
`thread_ids` and `message_ids` columns carry everything it needs.
"""

import argparse
import csv
import os
import sys
from datetime import date

CSV_HEADER = ["earliest_date", "latest_date", "thread_ids", "message_ids", "emails"]
ARRAY_DELIMITER = "|"
# The pipeline contract: aggregate_emails.py writes this by default.
DEFAULT_IN = "aggregated_results.csv"
DEFAULT_OUT = "filtered_results.csv"
# Written alongside the delete-list CSV (same directory as --out).
DEFAULT_QUERIES_OUT = "filtered_queries.txt"
DEFAULT_YEARS = 5


def build_address_state(rows):
    """One streaming pass over aggregate rows -> per-address state.

    Returns ``{email: [earliest, latest, thread_ids, message_id_groups]}``
    where earliest/latest are min/max of the YYYY-MM-DD strings across every
    thread the address appears in, ``thread_ids`` collects those threads' ids
    in input order, and ``message_id_groups`` holds each thread's message ids
    as its own list, aligned with ``thread_ids`` — so retain can drop a
    protected thread's messages without losing the other threads'.
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
            entry[3].append(list(message_ids))
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


def select_dormant(state, cutoff, ignore, retain):
    """The delete list: state filtered to dormant, non-excluded addresses.

    Dormant is strict: last seen older than ``cutoff`` (a ``date``); an
    address last seen on the cutoff day itself is kept off the list. Both
    ``ignore`` and ``retain`` hold exact addresses and/or bare domains (see
    ``_excluded``), but they exclude at different levels:

    - ignore is address-level only: the address never appears as a row, but
      threads containing it stay eligible (the owner is on every thread).
    - retain is thread-level: the address never appears AND every thread it
      appears in is protected — its thread/message ids vanish from all rows,
      and an address left with no unprotected threads is dropped. Deleting a
      dormant contact's copy of a shared thread would delete the retained
      contact's mail too.

    Dormancy and the first/last-seen dates still reflect ALL of an address's
    threads, protected ones included: they describe the contact, not just the
    deletable subset.

    The result values are ``[earliest, latest, thread_ids, message_id_groups]``
    with message ids still grouped per thread (aligned with ``thread_ids``, so
    the writer can emit one row per deletable thread), ordered by domain, then
    subdomain, then username, all ascending (see ``_sort_key``), so both
    output files inherit the order: same-organization addresses sit together,
    a domain's subdomains right after it.
    """
    protected = set()
    for email, entry in state.items():
        if _excluded(email, retain):
            protected.update(entry[2])

    result = {}
    for email, entry in state.items():
        if _excluded(email, ignore) or _excluded(email, retain):
            continue
        if date.fromisoformat(entry[1]) >= cutoff:
            continue
        kept = [(tid, msgs) for tid, msgs in zip(entry[2], entry[3])
                if tid not in protected]
        if not kept:
            continue
        result[email] = [
            entry[0], entry[1],
            [tid for tid, _ in kept],
            [msgs for _, msgs in kept],
        ]
    return dict(sorted(result.items(), key=lambda kv: _sort_key(kv[0])))


def _sort_key(email):
    """Domain, then subdomain, then username, ascending.

    The domain labels are reversed (``alerts@notify.wm.com`` -> ``("com",
    "wm", "notify")``) so a domain sorts before its subdomains and same-
    organization addresses group together; the local part breaks ties.
    """
    local, _, domain = email.rpartition("@")
    return tuple(reversed(domain.split("."))), local


def _parse_addresses(text):
    """Comma-separated addresses or bare domains -> stripped, lowercased,
    empties dropped."""
    return [a.strip().lower() for a in (text or "").split(",") if a.strip()]


def _read_entries(path):
    """An --ignore/--retain file -> its entries, one address or bare domain
    per line, blank lines skipped, lowercased. Raises FileNotFoundError."""
    with open(path, encoding="utf-8") as fh:
        return [line.strip().lower() for line in fh if line.strip()]


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
                        help="output text file, one delete-list address per "
                             f"line (default: {DEFAULT_QUERIES_OUT} alongside "
                             "the CSV)")
    parser.add_argument("--ignore", default=None, metavar="FILE",
                        help="file of addresses/bare domains to ignore, one "
                             "per line; skips the prompt (empty string: no "
                             "entries; prompt default: the inferred owner)")
    parser.add_argument("--retain", default=None, metavar="FILE",
                        help="file of addresses/bare domains to retain, one "
                             "per line; skips the prompt (empty string: no "
                             "entries)")
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

    # --ignore/--retain are filenames (one entry per line); an empty argument
    # means "no entries" so non-interactive runs can decline without a file.
    try:
        if args.ignore is not None:
            ignore = _read_entries(args.ignore) if args.ignore else []
        else:
            owner = infer_owner(state)
            resp = input(f"Addresses to ignore, comma-separated "
                         f"[default: {owner or 'none'}]: ").strip()
            ignore = _parse_addresses(resp) if resp else ([owner] if owner else [])

        if args.retain is not None:
            retain = _read_entries(args.retain) if args.retain else []
        else:
            retain = _parse_addresses(
                input("Addresses to retain, comma-separated [default: none]: "))
    except FileNotFoundError as exc:
        print(f"error: ignore/retain file not found: {exc.filename}",
              file=sys.stderr)
        return 2

    if args.years is not None:
        years = args.years
    else:
        resp = input(f"Dormancy cutoff in years [default: {DEFAULT_YEARS}]: ").strip()
        years = int(resp) if resp else DEFAULT_YEARS

    today = date.fromisoformat(args.today) if args.today else date.today()
    cutoff = years_before(today, years)
    selected = select_dormant(state, cutoff, set(ignore), set(retain))

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for email, (earliest, latest, thread_ids, groups) in selected.items():
            # one row per deletable thread; the dates describe the whole
            # contact, so they repeat on each of the address's rows
            for thread_id, message_ids in zip(thread_ids, groups):
                writer.writerow([
                    earliest, latest, thread_id,
                    ARRAY_DELIMITER.join(message_ids), email,
                ])

    queries_out = args.queries_out or os.path.join(
        os.path.dirname(args.out) or ".", DEFAULT_QUERIES_OUT)
    with open(queries_out, "w", encoding="utf-8") as fh:
        fh.writelines(email + "\n" for email in selected)

    row_count = sum(len(entry[2]) for entry in selected.values())
    print(f"wrote {row_count} thread rows for {len(selected)} addresses to "
          f"{args.out} and the addresses, one per line, to {queries_out} "
          f"(dormant before {cutoff.isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
