"""TDD tests for scripts/filter_emails.py — Phase 3 / Filter.

An address is dormant when its latest_date is older than today - N years.
Threads are emitted when they contain >=1 dormant address and no retained
address. All dates are injected so tests are deterministic; no MCP, no
network, no real addresses.
"""

import csv
from datetime import date

from scripts.filter_emails import (
    compute_cutoff,
    dormant_addresses,
    main,
    resolve_dormant_threads,
)

TODAY = date(2026, 7, 1)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def write_aggregate(path, rows):
    write_csv(path, ["email", "earliest_date", "latest_date"], rows)


def write_occurrences(path, rows):
    write_csv(path, ["date", "thread_id", "message_id", "email", "labelIds"], rows)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


# ---------------------------------------------------------------------------
# Cutoff arithmetic
# ---------------------------------------------------------------------------

def test_compute_cutoff_default_five_years():
    assert compute_cutoff(TODAY, 5) == date(2021, 7, 1)


def test_compute_cutoff_handles_leap_day():
    # Feb 29 minus N years lands on a non-leap year -> clamp to Feb 28
    assert compute_cutoff(date(2024, 2, 29), 5) == date(2019, 2, 28)


# ---------------------------------------------------------------------------
# Dormancy sweep over the aggregate CSV
# ---------------------------------------------------------------------------

def test_dormant_is_latest_date_older_than_cutoff(tmp_path):
    agg = tmp_path / "contacts.csv"
    write_aggregate(str(agg), [
        ["stale@example.com", "2010-01-01", "2019-06-30"],   # dormant
        ["edge@example.com", "2010-01-01", "2021-07-01"],    # exactly cutoff: NOT dormant
        ["fresh@example.com", "2010-01-01", "2026-06-01"],   # active
    ])
    result = dormant_addresses(str(agg), compute_cutoff(TODAY, 5),
                               ignore=set(), retain=set())
    assert result == {"stale@example.com"}


def test_ignored_and_retained_addresses_are_never_dormant(tmp_path):
    agg = tmp_path / "contacts.csv"
    write_aggregate(str(agg), [
        ["owner@example.com", "2000-01-01", "2001-01-01"],
        ["keep@example.com", "2000-01-01", "2001-01-01"],
        ["stale@example.com", "2000-01-01", "2001-01-01"],
    ])
    result = dormant_addresses(str(agg), compute_cutoff(TODAY, 5),
                               ignore={"owner@example.com"},
                               retain={"keep@example.com"})
    assert result == {"stale@example.com"}


def test_malformed_latest_date_is_not_dormant(tmp_path):
    agg = tmp_path / "contacts.csv"
    write_aggregate(str(agg), [
        ["weird@example.com", "2000-01-01", "not-a-date"],
        ["blank@example.com", "2000-01-01", ""],
    ])
    result = dormant_addresses(str(agg), compute_cutoff(TODAY, 5),
                               ignore=set(), retain=set())
    assert result == set()


# ---------------------------------------------------------------------------
# Thread resolution over the occurrences CSV
# ---------------------------------------------------------------------------

def test_thread_emitted_when_it_has_a_dormant_address(tmp_path):
    occ = tmp_path / "occurrences.csv"
    write_occurrences(str(occ), [
        ["2001-01-01", "t-old", "m1", "stale@example.com", ""],
        ["2026-01-01", "t-new", "m2", "fresh@example.com", ""],
    ])
    threads = resolve_dormant_threads(str(occ), {"stale@example.com"}, retain=set())
    assert threads == ["t-old"]


def test_retained_address_protects_whole_thread(tmp_path):
    occ = tmp_path / "occurrences.csv"
    write_occurrences(str(occ), [
        ["2001-01-01", "t-mixed", "m1", "stale@example.com", ""],
        ["2001-01-01", "t-mixed", "m1", "keep@example.com", ""],
        ["2001-01-01", "t-old", "m2", "stale@example.com", ""],
    ])
    threads = resolve_dormant_threads(str(occ), {"stale@example.com"},
                                      retain={"keep@example.com"})
    assert threads == ["t-old"]


def test_no_dormant_addresses_yields_no_threads(tmp_path):
    occ = tmp_path / "occurrences.csv"
    write_occurrences(str(occ), [
        ["2026-01-01", "t1", "m1", "fresh@example.com", ""],
    ])
    assert resolve_dormant_threads(str(occ), set(), retain=set()) == []


# ---------------------------------------------------------------------------
# CLI: prompts (owner defaults into ignore, 5-year default) and output file
# ---------------------------------------------------------------------------

def run_main(tmp_path, argv, inputs):
    """Run main() with scripted stdin answers; returns output CSV rows."""
    answers = iter(inputs)
    out = tmp_path / "dormant_threads.csv"
    main(argv + ["--out", str(out)], input_fn=lambda _prompt: next(answers),
         today=TODAY)
    return read_csv(str(out))


def make_pipeline_files(tmp_path):
    agg = tmp_path / "contacts.csv"
    occ = tmp_path / "occurrences.csv"
    write_aggregate(str(agg), [
        ["owner@example.com", "2001-01-01", "2001-06-01"],   # owner: old but ignored
        ["stale@example.com", "2001-01-01", "2001-06-01"],
        ["keep@example.com", "2001-01-01", "2001-06-01"],
        ["fresh@example.com", "2020-01-01", "2026-06-01"],
    ])
    write_occurrences(str(occ), [
        ["2001-06-01", "t-owner-only", "m0", "owner@example.com", ""],
        ["2001-06-01", "t-stale", "m1", "stale@example.com", ""],
        ["2001-06-01", "t-protected", "m2", "stale@example.com", ""],
        ["2001-06-01", "t-protected", "m2", "keep@example.com", ""],
        ["2026-06-01", "t-fresh", "m3", "fresh@example.com", ""],
    ])
    return str(agg), str(occ)


def test_main_interactive_defaults(tmp_path):
    agg, occ = make_pipeline_files(tmp_path)
    rows = run_main(
        tmp_path,
        ["--aggregate", agg, "--occurrences", occ, "--owner", "owner@example.com"],
        inputs=["", "keep@example.com", ""],  # accept owner ignore, retain one, default 5y
    )
    assert rows[0] == ["thread_id"]
    # owner ignored -> t-owner-only not emitted; keep protects t-protected
    assert [r[0] for r in rows[1:]] == ["t-stale"]


def test_main_non_interactive_flags_skip_prompts(tmp_path):
    agg, occ = make_pipeline_files(tmp_path)
    out = tmp_path / "dormant_threads.csv"

    def no_input(_prompt):
        raise AssertionError("must not prompt when flags are given")

    main(["--aggregate", agg, "--occurrences", occ,
          "--owner", "owner@example.com",
          "--years", "5", "--ignore", "owner@example.com",
          "--retain", "keep@example.com", "--out", str(out)],
         input_fn=no_input, today=TODAY)
    assert [r[0] for r in read_csv(str(out))[1:]] == ["t-stale"]


def test_main_empty_aggregate_writes_header_only(tmp_path):
    agg = tmp_path / "contacts.csv"
    occ = tmp_path / "occurrences.csv"
    write_aggregate(str(agg), [])
    write_occurrences(str(occ), [])
    out = tmp_path / "dormant_threads.csv"
    main(["--aggregate", str(agg), "--occurrences", str(occ),
          "--owner", "owner@example.com", "--years", "5",
          "--ignore", "", "--retain", "", "--out", str(out)],
         input_fn=lambda _p: "", today=TODAY)
    assert read_csv(str(out)) == [["thread_id"]]
