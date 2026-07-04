"""Phase 2 / Load + Transform (LT) — collapse the extract to per-thread first/last-seen.

Stream-reads the extract CSV (one raw row per message) and writes one row per
thread:

    thread_id, earliest_date(YYYY-MM-DD), latest_date(YYYY-MM-DD),
    emails(pipe-joined), message_ids(pipe-joined)

The extract (see generate_python_gather_emails.md, whose output contract this
script consumes — discovered at generation time, not duplicated here) is 1:1
raw, so this phase owns both Transforms:

- dates: the raw `header_date` string (ISO-8601 with tz offset, or the raw
  RFC 2822 header) is normalized to UTC YYYY-MM-DD before any min/max
  comparison; when it is empty or unparseable the row falls back to
  `internal_date` (Gmail's internalDate, epoch milliseconds — present for
  every message), so every row always has an email date.
- addresses: each `|`-joined `emails` value is split into elements, elements
  are split on commas, display names are stripped (Alice <a@x.com> -> a@x.com),
  lowercased, and deduped.

Aggregation state is a dict keyed by thread_id -> (earliest, latest, emails,
message_ids); the input is consumed row-by-row, so only per-thread state — not
the file — is ever in memory.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime

CSV_HEADER = ["thread_id", "earliest_date", "latest_date", "emails", "message_ids"]
ARRAY_DELIMITER = "|"
# The extract's default output filename (its story: "so that the next step
# knows what it needs to load").
DEFAULT_IN = "gathered_results.csv"
DEFAULT_OUT = "aggregated_results.csv"


def normalize_date(value):
    """Raw ``header_date`` string -> UTC ``YYYY-MM-DD``; ``None`` if unparseable.

    Handles both shapes the extract carries as-is: simplegmail's usual
    ``str(datetime.astimezone())`` (ISO-8601, space separator, tz offset) and
    the raw RFC 2822 ``Date`` header it falls back to.
    """
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def epoch_ms_to_date(value):
    """Gmail ``internalDate`` (epoch-milliseconds string) -> UTC ``YYYY-MM-DD``.

    Returns ``None`` when the cell is empty or not a number (e.g. the extract
    ran against a fork build that does not expose internal_date yet).
    """
    if not value:
        return None
    try:
        ms = int(str(value).strip())
    except ValueError:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _row_date(r):
    """UTC ``YYYY-MM-DD`` for an extract row: header_date, else internal_date."""
    return normalize_date(r.get("header_date")) or epoch_ms_to_date(r.get("internal_date"))


def split_emails(cell):
    """A raw ``|``-joined `emails` cell -> normalized, deduped address list.

    Each element is a raw header value: possibly ``Display Name <addr>``,
    mixed case, or several comma-separated addresses. ``getaddresses`` does
    the display-name stripping and comma splitting; dedup preserves
    first-seen order.
    """
    if not cell:
        return []
    out = []
    for element in cell.split(ARRAY_DELIMITER):
        for _name, addr in getaddresses([element]):
            if "@" not in addr:
                continue
            addr = addr.lower()
            if addr not in out:
                out.append(addr)
    return out


def aggregate(rows):
    """One streaming pass: dict keyed by thread_id.

    ``rows`` is an iterator of dicts with the extract's columns. Returns
    ``{thread_id: (earliest, latest, emails, message_ids)}``. Every row is
    dated: header_date, else internal_date (per the extract's contract,
    internalDate exists for every message).
    """
    threads = {}
    for r in rows:
        date = _row_date(r)
        thread_id = r.get("thread_id", "") or ""
        entry = threads.setdefault(thread_id, [date, date, [], []])
        entry[0] = min(entry[0], date)
        entry[1] = max(entry[1], date)
        for email in split_emails(r.get("emails")):
            if email not in entry[2]:
                entry[2].append(email)
        message_id = r.get("message_id", "") or ""
        if message_id:
            entry[3].append(message_id)
    return {tid: tuple(entry) for tid, entry in threads.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aggregate the extract CSV to per-thread earliest/latest "
                    "dates with normalized addresses (the LT of the ELT)."
    )
    parser.add_argument("--in", dest="in_path", default=DEFAULT_IN,
                        help=f"input CSV from gather_emails.py (default: {DEFAULT_IN})")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help=f"output CSV path (default: {DEFAULT_OUT})")
    args = parser.parse_args(argv)

    if not os.path.exists(args.in_path):
        print(
            f"error: input CSV not found: {args.in_path}\n"
            f"Run scripts/gather_emails.py first (it writes {DEFAULT_IN}), "
            "or pass --in PATH.",
            file=sys.stderr,
        )
        return 2

    with open(args.in_path, newline="", encoding="utf-8") as fh:
        threads = aggregate(csv.DictReader(fh))

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for thread_id, (earliest, latest, emails, message_ids) in threads.items():
            writer.writerow([
                thread_id, earliest, latest,
                ARRAY_DELIMITER.join(emails),
                ARRAY_DELIMITER.join(message_ids),
            ])

    print(f"wrote {len(threads)} thread rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
