"""TDD tests for scripts/aggregate_emails.py — Phase 2 / Transform.

Streams the occurrences CSV and collapses it to earliest/latest date per
address. Pure local CSV pass; no MCP, no network.
"""

import csv

from scripts.aggregate_emails import aggregate

EXPECTED_HEADER = ["email", "earliest_date", "latest_date"]


def write_occurrences(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "thread_id", "message_id", "email", "labelIds"])
        writer.writerows(rows)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def test_output_schema(tmp_path):
    src = tmp_path / "occurrences.csv"
    out = tmp_path / "contacts.csv"
    write_occurrences(str(src), [
        ["2020-01-01", "t1", "m1", "a@example.com", "INBOX"],
    ])
    aggregate(str(src), str(out))
    rows = read_csv(str(out))
    assert rows[0] == EXPECTED_HEADER
    assert rows[1] == ["a@example.com", "2020-01-01", "2020-01-01"]


def test_tracks_earliest_and_latest_per_address(tmp_path):
    src = tmp_path / "occurrences.csv"
    out = tmp_path / "contacts.csv"
    write_occurrences(str(src), [
        ["2019-05-05", "t1", "m1", "a@example.com", ""],
        ["2015-01-01", "t2", "m2", "a@example.com", ""],
        ["2023-12-31", "t3", "m3", "a@example.com", ""],
        ["2021-07-07", "t1", "m1", "b@example.com", ""],
    ])
    count = aggregate(str(src), str(out))
    assert count == 2

    body = {r[0]: (r[1], r[2]) for r in read_csv(str(out))[1:]}
    assert body["a@example.com"] == ("2015-01-01", "2023-12-31")
    assert body["b@example.com"] == ("2021-07-07", "2021-07-07")


def test_output_sorted_by_email_for_determinism(tmp_path):
    src = tmp_path / "occurrences.csv"
    out = tmp_path / "contacts.csv"
    write_occurrences(str(src), [
        ["2020-01-01", "t1", "m1", "zed@example.com", ""],
        ["2020-01-01", "t1", "m1", "amy@example.com", ""],
    ])
    aggregate(str(src), str(out))
    emails = [r[0] for r in read_csv(str(out))[1:]]
    assert emails == sorted(emails)


def test_empty_input_writes_header_only(tmp_path):
    src = tmp_path / "occurrences.csv"
    out = tmp_path / "contacts.csv"
    write_occurrences(str(src), [])
    count = aggregate(str(src), str(out))
    assert count == 0
    assert read_csv(str(out)) == [EXPECTED_HEADER]


def test_rows_with_blank_or_malformed_dates_are_skipped(tmp_path):
    src = tmp_path / "occurrences.csv"
    out = tmp_path / "contacts.csv"
    write_occurrences(str(src), [
        ["", "t1", "m1", "a@example.com", ""],          # Phase 1 bad-date row
        ["not-a-date", "t2", "m2", "a@example.com", ""],
        ["2022-02-02", "t3", "m3", "a@example.com", ""],
    ])
    aggregate(str(src), str(out))
    assert read_csv(str(out))[1:] == [["a@example.com", "2022-02-02", "2022-02-02"]]
