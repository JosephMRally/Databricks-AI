"""TDD tests for Phase 3 filter_emails.py — the delete list, one row per
dormant address per deletable thread.

Contract (per generate_python_filter_emails.md): a single streaming sweep over the
aggregate's per-thread CSV builds per-address state (first seen = min
earliest_date, last seen = max latest_date, thread_ids/message_ids collected),
then everything is a filter: an address lands on the delete list only when its
last-seen date is older than the cutoff (today − N years) and it is neither
ignored (default: the inferred owner) nor retained. The script reads the input
CSV and writes the delete-list CSV, nothing else — no Gmail access.

Input contract discovered from generate_python_aggregate_emails.md: columns
thread_id, earliest_date, latest_date, emails, message_ids; dates YYYY-MM-DD;
arrays `|`-joined; addresses already normalized (lowercase, bare). All
fixtures use fake addresses; prompts are driven via CLI args or stdin.
"""

import csv
import io
import sys
from datetime import date

from scripts.filter_emails import (
    CSV_HEADER,
    DEFAULT_IN,
    DEFAULT_OUT,
    DEFAULT_QUERIES_OUT,
    build_address_state,
    infer_owner,
    main,
    select_dormant,
    years_before,
)


# --- fixtures: rows shaped like the aggregate's output CSV -------------------

def arow(thread_id, earliest, latest, emails, message_ids):
    return {"thread_id": thread_id, "earliest_date": earliest,
            "latest_date": latest, "emails": emails, "message_ids": message_ids}


def write_input(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["thread_id", "earliest_date", "latest_date",
                            "emails", "message_ids"])
        writer.writeheader()
        writer.writerows(rows)


def write_entries(path, *entries):
    # --ignore/--retain files: one address or bare domain per line
    path.write_text("".join(e + "\n" for e in entries), encoding="utf-8")
    return str(path)


# A small mailbox: owner@x.com is on every thread (the owner); old@x.com was
# last heard from in 2015; fresh@x.com is recent.
def sample_rows():
    return [
        arow("t1", "2014-01-01", "2015-06-01", "owner@x.com|old@x.com", "m1|m2"),
        arow("t2", "2020-01-01", "2026-01-01", "owner@x.com|fresh@x.com", "m3"),
        arow("t3", "2019-05-05", "2019-05-05", "owner@x.com", "m4"),
    ]


# --- per-address state: aggregated across every thread -----------------------

def test_build_state_aggregates_per_address_across_threads():
    rows = [
        arow("t1", "2019-01-01", "2020-01-01", "a@x.com|b@x.com", "m1|m2"),
        arow("t2", "2018-06-01", "2024-03-03", "a@x.com", "m3"),
    ]
    state = build_address_state(iter(rows))
    earliest, latest, thread_ids, message_ids = state["a@x.com"]
    assert earliest == "2018-06-01"          # min across threads
    assert latest == "2024-03-03"            # max across threads
    assert thread_ids == ["t1", "t2"]
    # message ids grouped per thread (aligned with thread_ids), so retain
    # can drop a protected thread's messages without losing the others'
    assert message_ids == [["m1", "m2"], ["m3"]]
    assert state["b@x.com"][2] == ["t1"]      # only where the address appears


def test_build_state_streams_from_a_lazy_iterator():
    # single streaming sweep: rows arrive one at a time; never len()/index
    def gen():
        yield arow("t1", "2020-01-01", "2020-01-01", "a@x.com", "m1")
        yield arow("t2", "2021-01-01", "2021-01-01", "b@x.com", "m2")

    state = build_address_state(gen())
    assert set(state) == {"a@x.com", "b@x.com"}


# --- owner inference: the address on the most threads -------------------------

def test_infer_owner_is_address_on_most_threads():
    state = build_address_state(iter(sample_rows()))
    assert infer_owner(state) == "owner@x.com"  # on 3 threads, others on 1


def test_infer_owner_none_when_no_addresses():
    assert infer_owner({}) is None


# --- cutoff arithmetic: today − N years ---------------------------------------

def test_years_before_subtracts_years():
    assert years_before(date(2026, 7, 4), 5) == date(2021, 7, 4)


def test_years_before_clamps_feb_29():
    assert years_before(date(2024, 2, 29), 1) == date(2023, 2, 28)


# --- the filters: dormant, ignored, retained ----------------------------------

def test_select_dormant_keeps_only_addresses_older_than_cutoff():
    state = build_address_state(iter(sample_rows()))
    result = select_dormant(state, cutoff=date(2021, 1, 1),
                            ignore=set(), retain=set())
    assert "old@x.com" in result       # last seen 2015 < cutoff
    assert "fresh@x.com" not in result  # last seen 2026 >= cutoff


def test_select_dormant_last_seen_is_max_across_threads():
    # dormant in one thread but active in another -> NOT dormant
    rows = [
        arow("t1", "2010-01-01", "2011-01-01", "a@x.com", "m1"),
        arow("t2", "2025-01-01", "2025-06-01", "a@x.com", "m2"),
    ]
    state = build_address_state(iter(rows))
    assert select_dormant(state, cutoff=date(2021, 1, 1),
                          ignore=set(), retain=set()) == {}


def test_select_dormant_boundary_equal_to_cutoff_is_not_dormant():
    # "older than the cutoff" is strict
    rows = [arow("t1", "2021-01-01", "2021-01-01", "a@x.com", "m1")]
    state = build_address_state(iter(rows))
    assert select_dormant(state, cutoff=date(2021, 1, 1),
                          ignore=set(), retain=set()) == {}


def test_select_dormant_excludes_ignored_and_retained():
    state = build_address_state(iter(sample_rows()))
    result = select_dormant(
        state, cutoff=date(2026, 7, 1),          # everyone is old enough...
        ignore={"owner@x.com"}, retain={"old@x.com"},  # ...but neither appears
    )
    assert "owner@x.com" not in result
    assert "old@x.com" not in result


# --- retain protects whole threads; ignore does not ----------------------------

def test_retain_excludes_the_entire_thread():
    rows = [
        arow("t1", "2010-01-01", "2012-05-05", "keep@y.com|old@x.com", "m1|m2"),
        arow("t2", "2009-01-01", "2010-02-02", "old@x.com", "m3"),
    ]
    state = build_address_state(iter(rows))
    result = select_dormant(state, cutoff=date(2021, 1, 1),
                            ignore=set(), retain={"keep@y.com"})
    assert "keep@y.com" not in result
    earliest, latest, thread_ids, message_ids = result["old@x.com"]
    assert thread_ids == ["t2"]        # t1 is protected by keep@y.com
    # message ids stay grouped per thread so each output row can carry a
    # single thread_id with that thread's own message_ids
    assert message_ids == [["m3"]]     # none of t1's messages are deletable
    # dates still describe the whole contact, including the protected thread
    assert (earliest, latest) == ("2009-01-01", "2012-05-05")


def test_retain_drops_address_with_no_unprotected_threads():
    rows = [arow("t1", "2010-01-01", "2011-01-01", "keep@y.com|old@x.com", "m1")]
    state = build_address_state(iter(rows))
    assert select_dormant(state, cutoff=date(2021, 1, 1),
                          ignore=set(), retain={"keep@y.com"}) == {}


def test_retain_domain_protects_threads_of_subdomain_addresses():
    rows = [
        arow("t1", "2010-01-01", "2011-01-01", "alerts@notify.wm.com|old@x.com", "m1"),
        arow("t2", "2009-01-01", "2010-01-01", "old@x.com", "m2"),
    ]
    state = build_address_state(iter(rows))
    result = select_dormant(state, cutoff=date(2021, 1, 1),
                            ignore=set(), retain={"wm.com"})
    assert result["old@x.com"][2] == ["t2"]


def test_ignore_is_address_level_threads_stay_eligible():
    # the owner is on every thread; ignoring them must not protect threads
    state = build_address_state(iter(sample_rows()))
    result = select_dormant(state, cutoff=date(2021, 7, 4),
                            ignore={"owner@x.com"}, retain=set())
    assert result["old@x.com"][2] == ["t1"]  # t1 deletable though owner is in it


# --- main: CSV in, delete-list CSV out, args + prompts + exit codes -----------

def test_main_writes_delete_list_csv(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, sample_rows())
    out = tmp_path / "filtered.csv"

    rc = main(["--in", str(inp), "--out", str(out),
               "--ignore", write_entries(tmp_path / "ign.txt", "owner@x.com"),
               "--retain", "", "--years", "5",
               "--today", "2026-07-04"])

    assert rc == 0
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert CSV_HEADER == ["earliest_date", "latest_date",
                          "thread_ids", "message_ids", "emails"]
    assert rows[0] == CSV_HEADER
    # cutoff 2021-07-04: old@x.com (2015) is dormant; fresh@x.com and
    # owner@x.com were both heard from in 2026, and owner is ignored anyway.
    assert rows[1:] == [["2014-01-01", "2015-06-01", "t1", "m1|m2", "old@x.com"]]


def test_main_one_row_per_deletable_thread(tmp_path):
    # story: one output row per dormant address per deletable thread — each
    # row carries a single thread_id and that thread's message_ids, while the
    # first/last-seen dates describe the whole contact on every row
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "owner@x.com|old@x.com", "m1|m2"),
        arow("t2", "2009-05-05", "2010-02-02", "owner@x.com|old@x.com", "m3"),
        arow("t3", "2020-01-01", "2026-01-01", "owner@x.com", "m4"),
    ])
    out = tmp_path / "filtered.csv"

    rc = main(["--in", str(inp), "--out", str(out),
               "--ignore", write_entries(tmp_path / "ign.txt", "owner@x.com"),
               "--retain", "", "--years", "5", "--today", "2026-07-04"])

    assert rc == 0
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[1:] == [
        ["2009-05-05", "2011-01-01", "t1", "m1|m2", "old@x.com"],
        ["2009-05-05", "2011-01-01", "t2", "m3", "old@x.com"],
    ]
    # the queries file still lists the address once, not once per thread row
    queries = (tmp_path / "filtered_queries.txt").read_text(encoding="utf-8")
    assert queries == "old@x.com\n"


def test_main_retain_keeps_address_off_the_list(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, sample_rows())
    out = tmp_path / "filtered.csv"

    main(["--in", str(inp), "--out", str(out),
          "--ignore", write_entries(tmp_path / "ign.txt", "owner@x.com"),
          "--retain", write_entries(tmp_path / "ret.txt", "old@x.com"),
          "--years", "5", "--today", "2026-07-04"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows == [CSV_HEADER]  # the only dormant address was retained


def test_main_today_flag_pins_dormancy(tmp_path):
    # the same data flips dormant/active purely on the injected today
    inp = tmp_path / "agg.csv"
    write_input(inp, sample_rows())
    out = tmp_path / "filtered.csv"

    main(["--in", str(inp), "--out", str(out),
          "--ignore", write_entries(tmp_path / "ign.txt", "owner@x.com"),
          "--retain", "", "--years", "5", "--today", "2020-01-01"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows == [CSV_HEADER]  # cutoff 2015-01-01: old@x.com (2015-06) not yet dormant


def test_main_prompts_with_owner_default_when_args_absent(tmp_path, monkeypatch, capsys):
    # empty responses accept the defaults: ignore=[owner], retain=none, N=5
    inp = tmp_path / "agg.csv"
    write_input(inp, sample_rows())
    out = tmp_path / "filtered.csv"
    monkeypatch.setattr("sys.stdin", io.StringIO("\n\n\n"))

    rc = main(["--in", str(inp), "--out", str(out), "--today", "2026-07-04"])

    assert rc == 0
    assert "owner@x.com" in capsys.readouterr().out  # default shown in prompt
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert [r[4] for r in rows[1:]] == ["old@x.com"]  # owner ignored by default


def test_main_args_skip_prompts(tmp_path, monkeypatch):
    # agent story: with all args given the run never touches stdin
    inp = tmp_path / "agg.csv"
    write_input(inp, sample_rows())
    monkeypatch.setattr(
        "builtins.input",
        lambda *a: (_ for _ in ()).throw(AssertionError("prompted despite args")),
    )

    rc = main(["--in", str(inp), "--out", str(tmp_path / "f.csv"),
               "--ignore", write_entries(tmp_path / "ign.txt", "owner@x.com"),
               "--retain", "", "--years", "5",
               "--today", "2026-07-04"])
    assert rc == 0


def test_main_missing_input_friendly_error_and_exit_2(tmp_path, capsys):
    rc = main(["--in", str(tmp_path / "nope.csv"),
               "--out", str(tmp_path / "f.csv"),
               "--ignore", "", "--retain", "", "--years", "5",
               "--today", "2026-07-04"])
    assert rc == 2
    err = capsys.readouterr().err
    assert str(tmp_path / "nope.csv") in err
    assert "aggregate" in err.lower()  # points at the phase that produces it


def test_defaults_follow_the_pipeline_contract():
    assert DEFAULT_IN == "aggregated_results.csv"   # the aggregate's default output
    assert DEFAULT_OUT == "filtered_results.csv"


def test_main_writes_default_out_filename(tmp_path, monkeypatch):
    inp = tmp_path / "agg.csv"
    write_input(inp, sample_rows())
    monkeypatch.chdir(tmp_path)

    rc = main(["--in", str(inp),
               "--ignore", write_entries(tmp_path / "ign.txt", "owner@x.com"),
               "--retain", "", "--years", "5", "--today", "2026-07-04"])
    assert rc == 0
    assert (tmp_path / "filtered_results.csv").exists()


def test_module_never_touches_gmail():
    # story: no Gmail access, no deletion — computing the list has no side
    # effects, so the module must not even import the Gmail wrapper
    assert "simplegmail" not in sys.modules


# --- domains: a bare entry covers the whole domain and its subdomains ----------

def test_select_dormant_excludes_whole_domain_including_subdomains():
    rows = [
        arow("t1", "2010-01-01", "2011-01-01", "billing@wm.com", "m1"),
        arow("t2", "2010-01-01", "2011-02-01", "alerts@notify.wm.com", "m2"),
        arow("t3", "2010-01-01", "2011-03-01", "wm.com@gmail.com", "m3"),
    ]
    state = build_address_state(iter(rows))
    result = select_dormant(state, cutoff=date(2021, 1, 1),
                            ignore={"wm.com"}, retain=set())
    # the bare domain matches after the @ only: the exact domain and its
    # subdomains, never a local part that happens to look like it
    assert set(result) == {"wm.com@gmail.com"}


def test_main_ignore_accepts_bare_domains(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "billing@wm.com|old@x.com", "m1"),
        arow("t2", "2010-01-01", "2011-01-01", "alerts@notify.wm.com", "m2"),
    ])
    out = tmp_path / "filtered.csv"

    main(["--in", str(inp), "--out", str(out),
          "--ignore", write_entries(tmp_path / "ign.txt", "wm.com"),
          "--retain", "", "--years", "5", "--today", "2026-07-04"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert [r[4] for r in rows[1:]] == ["old@x.com"]  # all of wm.com ignored


def test_main_retain_accepts_bare_domains(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "billing@wm.com|old@x.com", "m1"),
    ])
    out = tmp_path / "filtered.csv"

    main(["--in", str(inp), "--out", str(out), "--ignore", "",
          "--retain", write_entries(tmp_path / "ret.txt", "wm.com"),
          "--years", "5", "--today", "2026-07-04"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    # retain protects the whole thread: old@x.com's only thread contains a
    # wm.com address, so old@x.com has nothing deletable and drops off too
    assert rows[1:] == []


# --- case-insensitivity: everything lowercased before comparison ---------------

def test_build_state_lowercases_and_merges_csv_addresses():
    # the CSV may not honor the aggregate's lowercase contract (hand-edited,
    # third-party); the filter lowercases on read so the same sender merges
    rows = [
        arow("t1", "2019-01-01", "2020-01-01", "Alice@X.com", "m1"),
        arow("t2", "2018-01-01", "2021-01-01", "alice@x.com", "m2"),
    ]
    state = build_address_state(iter(rows))
    assert set(state) == {"alice@x.com"}
    assert state["alice@x.com"][0] == "2018-01-01"
    assert state["alice@x.com"][2] == ["t1", "t2"]


# --- ordering: domain, then subdomain, then username, ascending, both files ----

def test_main_outputs_ordered_by_domain_subdomain_then_username(tmp_path):
    # input arrives in neither order: same-domain addresses group together
    # (username A->Z), a domain's subdomains come right after it, and the
    # dates play no part in the order
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "c@wm.com", "m1"),
        arow("t2", "2010-01-01", "2012-01-01", "alerts@notify.wm.com", "m2"),
        arow("t3", "2010-01-01", "2013-01-01", "a@x.com", "m3"),
        arow("t4", "2010-01-01", "2010-06-06", "b@wm.com", "m4"),
    ])
    out = tmp_path / "filtered.csv"

    main(["--in", str(inp), "--out", str(out),
          "--ignore", "", "--retain", "", "--years", "5",
          "--today", "2026-07-04"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    expected = ["b@wm.com", "c@wm.com", "alerts@notify.wm.com", "a@x.com"]
    assert [r[4] for r in rows[1:]] == expected
    queries = (tmp_path / "filtered_queries.txt").read_text(encoding="utf-8")
    assert queries == "".join(e + "\n" for e in expected)


# --- addresses text file: one address per line ---------------------------------

def test_main_writes_queries_file_alongside_the_csv(tmp_path):
    # default: filtered_queries.txt in the same directory as the --out CSV
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "old@x.com|older@y.com", "m1"),
    ])

    rc = main(["--in", str(inp), "--out", str(tmp_path / "filtered.csv"),
               "--ignore", "", "--retain", "", "--years", "5",
               "--today", "2026-07-04"])

    assert rc == 0
    assert DEFAULT_QUERIES_OUT == "filtered_queries.txt"
    text = (tmp_path / "filtered_queries.txt").read_text(encoding="utf-8")
    assert text == "old@x.com\nolder@y.com\n"  # one address per line, list order


def test_main_queries_out_flag_overrides_path(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "old@x.com", "m1"),
    ])
    queries = tmp_path / "custom" / "q.txt"
    queries.parent.mkdir()

    main(["--in", str(inp), "--out", str(tmp_path / "filtered.csv"),
          "--queries-out", str(queries),
          "--ignore", "", "--retain", "", "--years", "5",
          "--today", "2026-07-04"])

    assert queries.read_text(encoding="utf-8") == "old@x.com\n"
    assert not (tmp_path / "filtered_queries.txt").exists()


def test_main_queries_file_empty_when_delete_list_is_empty(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "old@x.com", "m1"),
    ])

    main(["--in", str(inp), "--out", str(tmp_path / "filtered.csv"),
          "--ignore", "",
          "--retain", write_entries(tmp_path / "ret.txt", "old@x.com"),
          "--years", "5", "--today", "2026-07-04"])

    assert (tmp_path / "filtered_queries.txt").read_text(encoding="utf-8") == ""


def test_ignore_file_reads_one_entry_per_line_skipping_blanks(tmp_path):
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01",
             "old@x.com|billing@wm.com|OWNER@Y.COM", "m1"),
    ])
    out = tmp_path / "filtered.csv"
    ignore = tmp_path / "ign.txt"
    ignore.write_text("wm.com\n\nOWNER@y.com\n", encoding="utf-8")

    main(["--in", str(inp), "--out", str(out), "--ignore", str(ignore),
          "--retain", "", "--years", "5", "--today", "2026-07-04"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert [r[4] for r in rows[1:]] == ["old@x.com"]  # both entries applied


def test_main_missing_ignore_file_friendly_error_and_exit_2(tmp_path, capsys):
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "old@x.com", "m1"),
    ])

    rc = main(["--in", str(inp), "--out", str(tmp_path / "f.csv"),
               "--ignore", str(tmp_path / "nope.txt"),
               "--retain", "", "--years", "5", "--today", "2026-07-04"])

    assert rc == 2
    assert str(tmp_path / "nope.txt") in capsys.readouterr().err


def test_main_prompt_entries_lowercased_before_matching(tmp_path, monkeypatch):
    # story: every source — including the PROMPTS, not just CLI args — is
    # lower-cased before any processing
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "billing@wm.com|old@x.com", "m1"),
    ])
    out = tmp_path / "filtered.csv"
    # ignore prompt answered "WM.COM"; retain and years accept defaults
    monkeypatch.setattr("sys.stdin", io.StringIO("WM.COM\n\n\n"))

    rc = main(["--in", str(inp), "--out", str(out), "--today", "2026-07-04"])

    assert rc == 0
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert [r[4] for r in rows[1:]] == ["old@x.com"]


def test_main_inputs_match_case_insensitively(tmp_path):
    # mixed-case CSV addresses and mixed-case ignore entries still match
    inp = tmp_path / "agg.csv"
    write_input(inp, [
        arow("t1", "2010-01-01", "2011-01-01", "Billing@WM.com|old@x.com", "m1"),
    ])
    out = tmp_path / "filtered.csv"

    main(["--in", str(inp), "--out", str(out),
          "--ignore", write_entries(tmp_path / "ign.txt", "wm.COM"),
          "--retain", "", "--years", "5", "--today", "2026-07-04"])

    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert [r[4] for r in rows[1:]] == ["old@x.com"]
