"""TDD tests for scripts/aggregate_emails.py — the Load and Transform (LT) of the ELT.

Written red-first from the user stories in generate_python_aggregate_emails.md.
All local: fixture CSVs on disk, no Gmail, no network.

Input contract (discovered at runtime by a sub agent from
generate_python_gather_emails.md, per that spec's "agent" story):
- columns: header_date, internal_date, thread_id, message_id, emails, label_ids
- `header_date` is the RAW simplegmail date string (ISO-8601 with tz offset,
  or the raw RFC 2822 header; empty when the message has no Date header) —
  this phase owns normalizing it to UTC YYYY-MM-DD
- `internal_date` is Gmail's internalDate (epoch-milliseconds string, present
  for every message) — the fallback when header_date is empty/unparseable
- `emails` is `|`-joined RAW header values (display names, mixed case, an
  element may hold several comma-separated addresses) — this phase owns
  splitting/normalizing them
- default input filename: gathered_results.csv
"""

import csv

from scripts.aggregate_emails import (
    CSV_HEADER,
    DEFAULT_IN,
    aggregate,
    main,
    normalize_date,
    split_emails,
)

INPUT_HEADER = ["header_date", "internal_date", "thread_id", "message_id",
                "emails", "label_ids"]


def write_input(path, rows):
    """Fixture CSV in exactly the discovered extract schema."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(INPUT_HEADER)
        w.writerows(rows)


def read_output(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


# --- normalize_date: the Transform of dates -----------------------------------

def test_normalize_date_iso_offset():
    # simplegmail's usual shape: str(datetime.astimezone())
    assert normalize_date("2019-03-05 14:22:01-08:00") == "2019-03-05"


def test_normalize_date_converts_to_utc():
    # 23:30 at -08:00 is 07:30 the NEXT day in UTC
    assert normalize_date("2019-03-05 23:30:00-08:00") == "2019-03-06"


def test_normalize_date_rfc2822_fallback():
    # the extract passes the raw RFC 2822 header through when simplegmail
    # could not parse it — this phase must still handle it
    assert normalize_date("Tue, 5 Mar 2019 14:22:01 -0800") == "2019-03-05"


def test_normalize_date_unparseable_returns_none():
    assert normalize_date("garbage") is None
    assert normalize_date("") is None
    assert normalize_date(None) is None


# --- split_emails: the Transform of addresses ----------------------------------

def test_split_pipe_joined_elements():
    assert split_emails("a@x.com|b@x.com") == ["a@x.com", "b@x.com"]


def test_split_commas_within_an_element():
    # one raw To header value can hold several comma-separated addresses
    assert split_emails("a@x.com|b@x.com, C <c@x.com>") == \
        ["a@x.com", "b@x.com", "c@x.com"]


def test_split_strips_display_names_and_lowercases():
    assert split_emails("Alice Example <ALICE@Example.COM>") == ["alice@example.com"]


def test_split_dedups_preserving_first_seen_order():
    assert split_emails("b@x.com|Alice <a@x.com>|B@X.COM|a@x.com") == \
        ["b@x.com", "a@x.com"]


def test_split_empty_cell():
    assert split_emails("") == []
    assert split_emails(None) == []


# --- aggregate: one pass, dict keyed by thread_id ------------------------------

def row(header_date, thread_id, message_id, emails, label_ids="", internal_date=""):
    return {"header_date": header_date, "internal_date": internal_date,
            "thread_id": thread_id, "message_id": message_id,
            "emails": emails, "label_ids": label_ids}


def test_aggregate_tracks_earliest_and_latest_per_thread():
    rows = [
        row("2019-03-05 14:00:00+00:00", "t1", "m1", "a@x.com"),
        row("2021-07-01 09:00:00+00:00", "t1", "m2", "b@x.com"),
        row("2020-01-01 00:00:00+00:00", "t1", "m3", "a@x.com"),
        row("2022-05-05 12:00:00+00:00", "t2", "m4", "c@x.com"),
    ]
    result = aggregate(iter(rows))
    assert result["t1"][0] == "2019-03-05"   # earliest (min)
    assert result["t1"][1] == "2021-07-01"   # latest (max)
    assert result["t2"][0] == result["t2"][1] == "2022-05-05"


def test_aggregate_collects_normalized_emails_and_message_ids():
    rows = [
        row("2020-01-01 00:00:00+00:00", "t1", "m1", "Alice <A@X.com>|b@x.com"),
        row("2020-01-02 00:00:00+00:00", "t1", "m2", "b@x.com, c@x.com"),
    ]
    result = aggregate(iter(rows))
    _earliest, _latest, emails, message_ids = result["t1"]
    assert emails == ["a@x.com", "b@x.com", "c@x.com"]  # deduped, first-seen order
    assert message_ids == ["m1", "m2"]


def test_aggregate_prefers_header_date_over_internal_date():
    rows = [row("2020-01-01 00:00:00+00:00", "t1", "m1", "a@x.com",
                internal_date="1713123673715")]
    assert aggregate(iter(rows))["t1"][0] == "2020-01-01"


def test_aggregate_falls_back_to_internal_date_when_header_empty():
    # e.g. a SENT message with no Date header: internalDate still dates it
    rows = [row("", "t1", "m1", "a@x.com", internal_date="1713123673715")]
    result = aggregate(iter(rows))
    assert result["t1"][0] == result["t1"][1] == "2024-04-14"
    assert result["t1"][2] == ["a@x.com"]  # row contributes, not skipped


def test_aggregate_falls_back_when_header_date_unparseable():
    rows = [row("garbage", "t1", "m1", "a@x.com", internal_date="1713123673715")]
    assert aggregate(iter(rows))["t1"][0] == "2024-04-14"


def test_aggregate_streams_from_a_lazy_iterator():
    # stream-read story: rows arrive one at a time; aggregate must iterate,
    # never len()/index the input
    def gen():
        yield row("2020-01-01 00:00:00+00:00", "t1", "m1", "a@x.com")
        yield row("2020-02-02 00:00:00+00:00", "t2", "m2", "b@x.com")

    result = aggregate(gen())
    assert set(result) == {"t1", "t2"}


# --- main: CSV in, CSV out, args + exit codes ----------------------------------

def test_default_input_is_the_extracts_default_output():
    # discovered at runtime from generate_python_gather_emails.md
    assert DEFAULT_IN == "gathered_results.csv"


def test_main_missing_input_exits_nonzero_naming_the_file(tmp_path, capsys):
    missing = tmp_path / "gathered_results.csv"
    rc = main(["--in", str(missing), "--out", str(tmp_path / "agg.csv")])
    assert rc == 2
    err = capsys.readouterr().err
    assert str(missing) in err
    assert not (tmp_path / "agg.csv").exists()


def test_main_end_to_end_writes_one_row_per_thread(tmp_path):
    src = tmp_path / "gathered_results.csv"
    write_input(src, [
        ["2019-03-05 14:22:01-08:00", "1551824521000", "t1", "m1",
         "Alice <A@X.com>|b@x.com", "INBOX"],
        ["Tue, 5 Mar 2019 23:30:00 -0800", "", "t1", "m2", "b@x.com, c@x.com", ""],
        ["", "1713123673715", "t2", "m3", "", "SENT"],  # no Date header at all
    ])
    out = tmp_path / "aggregated_results.csv"
    rc = main(["--in", str(src), "--out", str(out)])
    assert rc == 0

    rows = read_output(out)
    assert rows[0] == CSV_HEADER
    assert CSV_HEADER == ["thread_id", "earliest_date", "latest_date",
                          "emails", "message_ids"]
    assert len(rows) == 3                     # header + one row per thread
    t1, t2 = rows[1], rows[2]                 # first-seen thread order
    assert t1[0] == "t1"
    assert t1[1] == "2019-03-05"              # earliest, normalized to UTC
    assert t1[2] == "2019-03-06"              # -0800 23:30 rolls into next UTC day
    assert t1[3] == "a@x.com|b@x.com|c@x.com" # normalized, deduped, pipe-joined
    assert t1[4] == "m1|m2"
    assert t2[0] == "t2"
    assert t2[1] == t2[2] == "2024-04-14"     # dated via internal_date fallback
    assert t2[3] == ""                        # no addresses in the source row
    assert t2[4] == "m3"
