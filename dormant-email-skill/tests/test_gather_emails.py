"""TDD tests for Phase 1 gather_emails.py — the simplegmail Facade.

All mocked: a fake Gmail client and fake Message/Label objects shaped like the
real `simplegmail` ones. No network, no credentials, no real addresses.

Contract (per generate_python_gather_emails.md): this phase is the Extract of
an ELT — exactly one CSV row per message, with the raw sender/recipient/cc/bcc
values carried as-is (no parsing, validation, normalization, or dedup) and
pipe-joined into the `emails` column, empty fields omitted. Dates are the one
exception: normalized to UTC YYYY-MM-DD, empty cell when unparseable.

Reference shapes (from simplegmail source):
- `Message.sender` / `Message.recipient` are strings (a header value, which may
  hold several comma-separated addresses — kept as one value).
- `Message.cc` / `Message.bcc` are `List[str]` (header split on ", ").
- `Message.date` is `str(dateutil.parse(header).astimezone())`, e.g.
  "2019-03-05 14:22:01-08:00".
- `Message.label_ids` is a list of `Label` objects (each with `.id` / `.name`).
"""

import csv
import logging
from types import SimpleNamespace

from scripts.gather_emails import (
    CSV_HEADER,
    MailboxSweepFacade,
    main,
    normalize_date,
    raw_values,
)


# --- fixtures modeled on the shape of real simplegmail objects ---------------

class FakeLabel:
    """Mimics simplegmail.label.Label (has .id and .name)."""

    def __init__(self, id, name=None):
        self.id = id
        self.name = name or id


def message(msg_id, thread_id, date, sender="", recipient="",
            cc=None, bcc=None, label_ids=None):
    """A stand-in exposing the attributes gather reads off a simplegmail Message."""
    return SimpleNamespace(
        id=msg_id, thread_id=thread_id, date=date,
        sender=sender, recipient=recipient,
        cc=list(cc or []), bcc=list(bcc or []),
        label_ids=list(label_ids or []),
    )


class FakeGmail:
    """Mimics simplegmail.Gmail: a get_messages() that returns Message-likes."""

    def __init__(self, messages):
        self._messages = messages
        self.calls = []

    def get_messages(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return list(self._messages)


# --- normalize_date ----------------------------------------------------------

def test_normalize_date_simplegmail_offset_format():
    # simplegmail emits str(datetime.astimezone()): space separator + tz offset
    assert normalize_date("2019-03-05 14:22:01-08:00") == "2019-03-05"


def test_normalize_date_converts_to_utc():
    # 23:30 at -08:00 is 07:30 the next day in UTC
    assert normalize_date("2019-03-05 23:30:00-08:00") == "2019-03-06"


def test_normalize_date_iso_z():
    assert normalize_date("2024-11-30T23:59:59Z") == "2024-11-30"


def test_normalize_date_rfc2822_fallback():
    assert normalize_date("Tue, 5 Mar 2019 14:22:01 +0000") == "2019-03-05"


def test_normalize_date_malformed_returns_empty():
    assert normalize_date("not a date") == ""
    assert normalize_date("") == ""
    assert normalize_date(None) == ""


# --- raw_values: as-is Extract, no transformations ---------------------------

def test_raw_string_field_kept_whole_and_untouched():
    # display names, case, and comma-separated multi-address strings survive
    # verbatim as ONE value — no parsing, no lowercasing, no splitting
    assert raw_values("Alice Example <ALICE@Example.COM>") == \
        ["Alice Example <ALICE@Example.COM>"]
    assert raw_values("a@x.com, B <b@x.com>") == ["a@x.com, B <b@x.com>"]


def test_raw_list_field_kept_elementwise():
    # cc / bcc arrive as List[str]; each element carried as-is
    assert raw_values(["Carol <carol@x.com>", "dave@x.com"]) == \
        ["Carol <carol@x.com>", "dave@x.com"]


def test_raw_empty_or_none_fields_are_omitted():
    assert raw_values(None) == []
    assert raw_values([]) == []
    assert raw_values("") == []
    assert raw_values(["", "eve@x.com"]) == ["eve@x.com"]  # empty elements too


def test_raw_values_are_not_validated():
    # 1:1 with the source: even a non-address header value passes through
    assert raw_values("undisclosed-recipients:;") == ["undisclosed-recipients:;"]


# --- sweep: schema, rows, streaming ------------------------------------------

def test_sweep_writes_header_and_one_row_per_message(tmp_path):
    m = message(
        "m1", "t1", "2019-03-05 14:22:01+00:00",
        sender="Alice <alice@example.com>",
        recipient="bob@example.com",
        cc=["Carol <carol@example.com>"],
        bcc=["dave@example.com"],
        label_ids=[FakeLabel("INBOX"), FakeLabel("STARRED")],
    )
    out = tmp_path / "occurrences.csv"
    n = MailboxSweepFacade(FakeGmail([m])).sweep(str(out))

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))

    assert rows[0] == CSV_HEADER
    assert n == 1
    row = rows[1]
    assert row[0] == "2019-03-05"  # date normalized to UTC YYYY-MM-DD
    assert row[1] == "t1"
    assert row[2] == "m1"
    # raw values as-is, sender/recipient/cc/bcc order, pipe-joined
    assert row[3] == ("Alice <alice@example.com>|bob@example.com|"
                      "Carol <carol@example.com>|dave@example.com")
    assert row[4] == "INBOX|STARRED"  # label_ids pipe-joined by id


def test_sweep_empty_mailbox_writes_header_only(tmp_path):
    out = tmp_path / "occurrences.csv"
    n = MailboxSweepFacade(FakeGmail([])).sweep(str(out))
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert n == 0
    assert rows == [CSV_HEADER]


def test_sweep_emits_a_row_even_with_no_addresses_or_date(tmp_path):
    # 1:1 with the source: a message with empty address fields and a garbage
    # date still yields its row — empty `emails` and `date` cells, ids kept.
    m = message("m2", "t2", "garbage-date", sender="", recipient="", cc=[], bcc=[])
    out = tmp_path / "occurrences.csv"
    n = MailboxSweepFacade(FakeGmail([m])).sweep(str(out))
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert n == 1
    assert rows[1] == ["", "t2", "m2", "", ""]


def test_sweep_omits_empty_fields_from_emails_join(tmp_path):
    # spec: "in that order with empty fields omitted" — no empty elements like
    # "a@x.com||c@x.com" when recipient/bcc are empty
    m = message("m4", "t4", "2020-01-01T00:00:00Z",
                sender="a@x.com", recipient="", cc=["c@x.com"], bcc=[])
    out = tmp_path / "occurrences.csv"
    MailboxSweepFacade(FakeGmail([m])).sweep(str(out))
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[1][3] == "a@x.com|c@x.com"


def test_sweep_carries_multi_address_string_as_one_value(tmp_path):
    # a To header holding several comma-separated addresses stays ONE array
    # element — splitting it is the next phase's job
    m = message("m3", "t3", "2020-01-01T00:00:00Z",
                sender="a@x.com", recipient="b@x.com, C <c@x.com>")
    out = tmp_path / "occurrences.csv"
    MailboxSweepFacade(FakeGmail([m])).sweep(str(out))
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[1][3] == "a@x.com|b@x.com, C <c@x.com>"


def test_sweep_streams_from_a_lazy_generator(tmp_path):
    # get_messages may return a generator; the facade must iterate, not len()/index it
    def gen():
        yield message("m1", "t1", "2020-01-01T00:00:00Z", sender="a@x.com")
        yield message("m2", "t2", "2020-02-02T00:00:00Z", sender="b@x.com")

    client = SimpleNamespace(get_messages=lambda *a, **k: gen())
    out = tmp_path / "occurrences.csv"
    n = MailboxSweepFacade(client).sweep(str(out))
    assert n == 2


def test_sweep_is_a_single_call_over_the_whole_mailbox(tmp_path):
    client = FakeGmail([])
    MailboxSweepFacade(client).sweep(str(tmp_path / "o.csv"))
    assert len(client.calls) == 1  # one sweep; the pagination fork pages internally


def test_sweep_requests_headers_only_and_passes_page_size(tmp_path):
    # The pagination fork's get_messages(page_size=...) pages lazily; the sweep
    # only reads headers, so attachments are ignored entirely.
    client = FakeGmail([])
    MailboxSweepFacade(client).sweep(str(tmp_path / "o.csv"), page_size=250)
    _args, kwargs = client.calls[0]
    assert kwargs["attachments"] == "ignore"
    assert kwargs["page_size"] == 250


def test_sweep_logs_each_message_when_enabled(tmp_path, caplog):
    # Story: a logging flag shows messages being processed (for testing).
    msgs = [
        message("m1", "t1", "2020-01-01T00:00:00Z", sender="a@x.com"),
        message("m2", "t2", "2020-02-02T00:00:00Z", sender="b@x.com"),
    ]
    with caplog.at_level(logging.INFO, logger="gather_emails"):
        MailboxSweepFacade(FakeGmail(msgs)).sweep(str(tmp_path / "o.csv"))
    assert len(caplog.records) == 2  # one progress line per message
    assert "m1" in caplog.records[0].getMessage()
    assert "m2" in caplog.records[1].getMessage()


def test_sweep_is_silent_by_default(tmp_path, caplog):
    m = message("m1", "t1", "2020-01-01T00:00:00Z", sender="a@x.com")
    with caplog.at_level(logging.WARNING, logger="gather_emails"):
        MailboxSweepFacade(FakeGmail([m])).sweep(str(tmp_path / "o.csv"))
    assert caplog.records == []  # progress is INFO, hidden without --verbose


# --- constructor: uses simplegmail to connect --------------------------------

def _inject_fake_simplegmail(monkeypatch, seen):
    """Put a fake `simplegmail` module in place and record how Gmail is built."""
    import sys
    import types

    class FakeGmailClient:
        def __init__(self, client_secret_file="client_secret.json",
                     creds_file="gmail_token.json"):
            seen["client_secret_file"] = client_secret_file
            seen["creds_file"] = creds_file

        def get_messages(self, *args, **kwargs):
            return []

    fake = types.ModuleType("simplegmail")
    fake.Gmail = FakeGmailClient
    monkeypatch.setitem(sys.modules, "simplegmail", fake)
    return FakeGmailClient


def test_from_simplegmail_uses_explicit_paths_as_given(monkeypatch):
    # Story: gather uses `simplegmail` to connect. Explicit paths pass straight
    # through — verified without the real package or credentials.
    seen = {}
    FakeGmailClient = _inject_fake_simplegmail(monkeypatch, seen)

    facade = MailboxSweepFacade.from_simplegmail("/tmp/cs.json", "/tmp/tok.json")

    assert seen["client_secret_file"] == "/tmp/cs.json"
    assert seen["creds_file"] == "/tmp/tok.json"
    assert isinstance(facade._client, FakeGmailClient)  # facade sweeps this client


def test_from_simplegmail_defaults_credentials_to_home(monkeypatch):
    # Per the spec's user story, the OAuth client and token live in the user's
    # HOME directory (~/client_secret.json, ~/gmail-token.json) — not the cwd
    # and not next to the script.
    import os

    seen = {}
    _inject_fake_simplegmail(monkeypatch, seen)

    MailboxSweepFacade.from_simplegmail()

    assert seen["client_secret_file"] == os.path.expanduser("~/client_secret.json")
    assert seen["creds_file"] == os.path.expanduser("~/gmail-token.json")


# --- main(): friendly message + exit codes (agent/harness facing) ------------

def test_main_friendly_error_and_nonzero_exit_when_credentials_missing(tmp_path, capsys):
    rc = main([
        "--out", str(tmp_path / "occ.csv"),
        "--client-secret", str(tmp_path / "nope.json"),
        "--token", str(tmp_path / "notoken.json"),
    ])
    assert rc == 2  # non-zero so an LLM harness sees the failure
    err = capsys.readouterr().err
    assert str(tmp_path / "nope.json") in err          # names the missing file
    assert "Google" in err and "Credentials" in err    # actionable guidance
    assert not (tmp_path / "occ.csv").exists()          # nothing swept


def test_main_success_returns_zero(tmp_path, monkeypatch):
    # credential pre-check passes; stub the live constructor so no simplegmail /
    # network / browser is involved.
    cs = tmp_path / "credentials.json"
    cs.write_text("{}")

    class FakeFacade:
        def sweep(self, out_csv, page_size=None):
            with open(out_csv, "w", encoding="utf-8") as fh:
                fh.write(",".join(CSV_HEADER) + "\n")
            return 0

    monkeypatch.setattr(
        MailboxSweepFacade, "from_simplegmail",
        classmethod(lambda cls, client_secret=None, token=None: FakeFacade()),
    )

    rc = main(["--out", str(tmp_path / "occ.csv"), "--client-secret", str(cs)])
    assert rc == 0
    assert (tmp_path / "occ.csv").exists()


def test_main_passes_page_size_to_sweep(tmp_path, monkeypatch):
    # Story: python args are used — --page-size reaches the fork's get_messages.
    cs = tmp_path / "credentials.json"
    cs.write_text("{}")
    seen = {}

    class FakeFacade:
        def sweep(self, out_csv, page_size=None):
            seen["page_size"] = page_size
            with open(out_csv, "w", encoding="utf-8") as fh:
                fh.write(",".join(CSV_HEADER) + "\n")
            return 0

    monkeypatch.setattr(
        MailboxSweepFacade, "from_simplegmail",
        classmethod(lambda cls, client_secret=None, token=None: FakeFacade()),
    )

    rc = main(["--out", str(tmp_path / "occ.csv"), "--client-secret", str(cs),
               "--page-size", "42"])
    assert rc == 0
    assert seen["page_size"] == 42


def test_main_verbose_flag_sets_info_level(tmp_path, monkeypatch):
    # Story: "include a flag for logging" — the -v FLAG itself must enable the
    # INFO progress lines, even when main() has been invoked before (a plain
    # run followed by a -v run must not leave logging stuck at WARNING).
    cs = tmp_path / "credentials.json"
    cs.write_text("{}")

    class FakeFacade:
        def sweep(self, out_csv, page_size=None):
            with open(out_csv, "w", encoding="utf-8") as fh:
                fh.write(",".join(CSV_HEADER) + "\n")
            return 0

    monkeypatch.setattr(
        MailboxSweepFacade, "from_simplegmail",
        classmethod(lambda cls, client_secret=None, token=None: FakeFacade()),
    )

    main(["--out", str(tmp_path / "a.csv"), "--client-secret", str(cs)])
    main(["--out", str(tmp_path / "b.csv"), "--client-secret", str(cs), "-v"])
    assert logging.getLogger("gather_emails").getEffectiveLevel() == logging.INFO


def test_main_reuses_saved_token_without_client_secret(tmp_path, monkeypatch):
    # Story #22: when the saved token exists, no client_secret / sign-in is
    # required — the run proceeds even though the OAuth client is absent.
    token = tmp_path / "gmail-token.json"
    token.write_text("{}")                       # token present
    missing_cs = tmp_path / "client_secret.json"  # deliberately absent

    class FakeFacade:
        def sweep(self, out_csv, page_size=None):
            with open(out_csv, "w", encoding="utf-8") as fh:
                fh.write(",".join(CSV_HEADER) + "\n")
            return 0

    monkeypatch.setattr(
        MailboxSweepFacade, "from_simplegmail",
        classmethod(lambda cls, client_secret=None, token=None: FakeFacade()),
    )

    rc = main(["--out", str(tmp_path / "occ.csv"),
               "--client-secret", str(missing_cs),
               "--token", str(token)])
    assert rc == 0                                # proceeded on the token alone
    assert (tmp_path / "occ.csv").exists()
