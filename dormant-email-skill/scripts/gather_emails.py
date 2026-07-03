"""Phase 1 / Extract — Facade over ``simplegmail`` for a one-pass mailbox sweep.

Running this script once sweeps the whole mailbox and streams exactly one CSV
row per message, 1:1 with the source:

    date(YYYY-MM-DD), thread_id, message_id, emails(pipe-joined), label_ids(pipe-joined)

This phase is the Extract of an ELT: the raw ``sender`` / ``recipient`` /
``cc`` / ``bcc`` values are carried as-is — no parsing, validation,
normalization, or dedup (splitting and normalizing addresses is the next
phase's job). ``emails`` holds those values in that order with empty fields
omitted; position does not identify which field a value came from. Dates are
the one sanctioned transformation: normalized to UTC ``YYYY-MM-DD``, with an
empty cell when the source date is unparseable.

The Facade hides the Gmail API behind a single ``sweep()`` call. Its core logic
depends only on the *shape* of a ``simplegmail`` ``Message`` — ``.sender`` and
``.recipient`` (strings), ``.cc`` / ``.bcc`` (``List[str]``), ``.date``
(a ``str(datetime.astimezone())``), ``.id``, ``.thread_id``, and ``.label_ids``
(``Label`` objects) — so tests inject a fake client and need no credentials or
network.

Only the convenience constructor ``from_simplegmail()`` builds a real
``simplegmail.Gmail`` (imported lazily, so importing this module and running the
mocked tests never require the package or an OAuth token). A live run needs a
``client_secret.json`` and, on first use, a browser to authorize — see
``generate_python_gather_emails.md``.

The installed ``simplegmail`` is the JosephMRally/simplegmail ``pagination``
fork, whose ``get_messages()`` returns a lazy ``Iterator[Message]`` that pages
through the mailbox internally (``page_size`` per API page). Combined with the
row-at-a-time CSV writes, neither the mailbox nor the output ever needs to fit
in memory.
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger("gather_emails")

CSV_HEADER = ["date", "thread_id", "message_id", "emails", "label_ids"]
ARRAY_DELIMITER = "|"
# simplegmail Message attributes for From / To / Cc / Bcc, in output order.
ADDRESS_FIELDS = ("sender", "recipient", "cc", "bcc")
# Messages fetched per Gmail API page (the pagination fork allows 1-500; the
# maximum keeps a whole-mailbox sweep to the fewest requests).
DEFAULT_PAGE_SIZE = 500


def normalize_date(value):
    """A ``simplegmail`` ``Message.date`` -> ``YYYY-MM-DD`` (UTC); "" if unparseable.

    ``simplegmail`` sets ``date`` to ``str(dateutil.parse(header).astimezone())``
    — an ISO-8601 string with a space separator and a tz offset, e.g.
    ``"2019-03-05 14:22:01-08:00"`` — but falls back to the raw RFC 2822 ``Date``
    header if that parse failed. Handle both, and express the day in UTC.
    """
    if not value or not isinstance(value, str):
        return ""
    text = value.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)  # RFC 2822 fallback
        except (TypeError, ValueError, IndexError):
            return ""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def raw_values(field):
    """A ``simplegmail`` address field -> list of its raw non-empty values, as-is.

    ``sender`` / ``recipient`` are strings (a header value that may itself hold
    several comma-separated addresses — kept as one value); ``cc`` / ``bcc`` are
    ``List[str]``. Any of them may be empty or ``None``. Per the spec, this
    phase does no parsing, validation, normalization, or dedup — empty fields
    are simply omitted.
    """
    if not field:
        return []
    if isinstance(field, str):
        return [field]
    return [x for x in field if isinstance(x, str) and x]


def _label_ids(message):
    """``label_ids`` joined with ``|`` for the CSV.

    Real ``simplegmail`` exposes ``Label`` objects (use ``.id``); tolerate bare
    strings too, so fixtures and future callers can pass either.
    """
    labels = getattr(message, "label_ids", None) or []
    return ARRAY_DELIMITER.join(getattr(lbl, "id", None) or str(lbl) for lbl in labels)


def _message_row(message):
    """One CSV row for a single message (emitted even with no addresses).

    ``emails`` pipe-joins the raw sender/recipient/cc/bcc values in that order,
    empty fields omitted.
    """
    emails = []
    for field_name in ADDRESS_FIELDS:
        emails.extend(raw_values(getattr(message, field_name, None)))
    return [
        normalize_date(getattr(message, "date", "")),
        getattr(message, "thread_id", "") or "",
        getattr(message, "id", "") or "",
        ARRAY_DELIMITER.join(emails),
        _label_ids(message),
    ]


# Google OAuth files live in the user's HOME directory (per the spec's user
# story), independent of where the script is launched from. ``client_secret.json``
# is the OAuth client downloaded from the Google Cloud Console; ``gmail-token.json``
# is the token simplegmail writes on first authorization and reuses thereafter.
DEFAULT_CLIENT_SECRET = os.path.expanduser("~/client_secret.json")
DEFAULT_TOKEN = os.path.expanduser("~/gmail-token.json")


class MailboxSweepFacade:
    """Facade Design Pattern: one ``sweep()`` hides simplegmail, address parsing,
    and CSV IO behind a single call."""

    def __init__(self, client):
        self._client = client

    @classmethod
    def from_simplegmail(cls, client_secret_file=None, creds_file=None):
        """Build a facade over a live ``simplegmail.Gmail`` client.

        The OAuth client and saved token default to ``~/client_secret.json`` and
        ``~/gmail-token.json`` in the user's home directory (per the spec), so
        the sweep finds them no matter where it is launched from. Pass explicit
        paths to override.

        ``simplegmail`` is imported lazily so this module and the mocked tests
        need neither the package nor credentials. Constructing ``Gmail`` triggers
        Google OAuth (a browser on first run, unless a valid token already
        exists).
        """
        from simplegmail import Gmail

        return cls(Gmail(
            client_secret_file=client_secret_file or DEFAULT_CLIENT_SECRET,
            creds_file=creds_file or DEFAULT_TOKEN,
        ))

    def sweep(self, out_csv, page_size=DEFAULT_PAGE_SIZE):
        """Stream one row per message to ``out_csv``, 1:1 with the mailbox.

        Returns the number of message rows written. The pagination fork's
        ``get_messages()`` yields messages lazily one API page at a time
        (``attachments='ignore'`` — the sweep only reads headers), and each row
        is written as its message is consumed, so neither the mailbox nor the
        output file is ever held in memory.
        """
        count = 0
        with open(out_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(CSV_HEADER)
            messages = self._client.get_messages(
                query="", attachments="ignore", page_size=page_size
            ) or []
            for message in messages:
                writer.writerow(_message_row(message))
                count += 1
                logger.info(
                    "message %d (id=%s) written",
                    count, getattr(message, "id", "") or "?",
                )
        return count


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sweep the whole Gmail mailbox (via simplegmail) into an occurrences CSV."
    )
    parser.add_argument("--out", default="occurrences.csv",
                        help="output CSV path (streamed)")
    parser.add_argument("--client-secret", default=None,
                        help="OAuth client JSON (default: ~/client_secret.json)")
    parser.add_argument("--token", default=None,
                        help="saved OAuth token JSON (default: ~/gmail-token.json)")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE,
                        help="messages fetched per Gmail API page, 1-500 "
                             f"(default: {DEFAULT_PAGE_SIZE})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="log each message to stderr as it is processed")
    args = parser.parse_args(argv)

    # Story: a logging flag shows messages being processed (for testing).
    # Logs go to stderr so stdout stays reserved for the final status line.
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    client_secret = args.client_secret or DEFAULT_CLIENT_SECRET
    token = args.token or DEFAULT_TOKEN

    # Story #22: prefer a previously-saved token so we do not sign in twice. Only
    # when there is no token do we need the OAuth client (which does the browser
    # sign-in and writes the token). simplegmail reuses a valid token and only
    # touches client_secret when the token is absent/invalid. If neither is
    # available, fail clearly with a friendly message and a non-zero exit code
    # (stories #20/#21).
    token_exists = os.path.exists(token)
    if not token_exists and not os.path.exists(client_secret):
        print(
            f"error: no saved token at {token} and no Google OAuth client at "
            f"{client_secret}.\nCreate an OAuth client ID in the Google Cloud "
            "Console (APIs & Services -> Credentials), download the JSON, and "
            f"save it as {client_secret} (or pass --client-secret PATH).",
            file=sys.stderr,
        )
        return 2

    try:
        count = MailboxSweepFacade.from_simplegmail(client_secret, token).sweep(
            args.out, page_size=args.page_size
        )
    except (FileNotFoundError, ValueError) as exc:
        # ValueError: get_messages rejects a page size outside 1-500.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {count} message rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
