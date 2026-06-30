#!/usr/bin/env python3
"""
test_pipeline.py — chain Phase 1 → 2 → 3 over a schema-faithful mock of the Gmail
MCP `search_threads` responses (tests/mock_mcp/page_*.json) and assert each stage.

Run:  python3 tests/test_pipeline.py     (exits non-zero on first failure)

All addresses here are synthetic and use IANA-reserved example domains
(example.com/.net/.org); no real mailbox is referenced.

Covers:
  - Phase 1 emits one (email,date) row per address per message, across From/To/Cc/Bcc,
    including STARRED and TRASH messages, with the message-id hex fallback for undated mail.
  - Phase 2 aggregates to earliest/latest per address (dict), sorted most-recent first.
  - Phase 3 filters to the dormant set, honoring ignore (drop), retain (protect), and
    the today−N cutoff; active and undated addresses are excluded; ignore normalizes
    case/plus (and Gmail dots, covered at unit level); interactive and flag modes agree.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
MOCK = os.path.join(HERE, "mock_mcp")
sys.path.insert(0, SCRIPTS)

import phase1 as p1mod   # noqa: E402
import phase3 as p3mod   # noqa: E402

PAGES = [os.path.join(MOCK, "page_001.json"), os.path.join(MOCK, "page_002.json")]
SELF = "owner@example.com"
TODAY = "2026-06-29"

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"FAIL: {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  ok: {name}")


def run(args, stdin=None):
    res = subprocess.run([sys.executable, *args], capture_output=True, text=True, input=stdin)
    if res.returncode != 0:
        print(res.stderr)
        raise SystemExit(f"{args} exited {res.returncode}")
    return res.stdout


def read_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


def test_units():
    print("[unit] helpers")
    check("extract_email display-name", p1mod.extract_email("Grace Hopper <grace@example.org>") == "grace@example.org")
    check("extract_email undisclosed -> None", p1mod.extract_email("undisclosed-recipients:;") is None)
    hexdt = p1mod.parse_date({"id": "17a40037b8d2f87c"})
    check("hex date fallback ~2021", hexdt is not None and hexdt.year == 2021)
    check("canonical gmail dot/plus", p3mod.canonical("a.b.c+x@googlemail.com") == "abc@gmail.com")
    cut = p3mod.cutoff_datetime(6, datetime(2026, 6, 29, tzinfo=timezone.utc))
    check("cutoff today-6y", (cut.year, cut.month, cut.day) == (2020, 6, 29))


def test_phase1(tmp):
    print("[phase1] occurrence log")
    out = run([os.path.join(SCRIPTS, "phase1.py"), *PAGES])
    header, rows = read_csv(out)
    check("phase1 header email,date", header == ["email", "date"])
    check("phase1 row count = 25 occurrences", len(rows) == 25)
    bob = [r[1] for r in rows if r[0] == "bob@example.com"]
    check("bob seen on 3 messages (cc/from/bcc)", len(bob) == 3)
    check("bob dates include 2014/2017/2020",
          {d[:4] for d in bob} == {"2014", "2017", "2020"})
    check("starred sender eve present", any(r[0] == "eve@example.net" for r in rows))
    check("trash sender frank present", any(r[0] == "frank@example.net" for r in rows))
    check("undated hexguy present", any(r[0] == "hexguy@example.net" for r in rows))
    p1 = os.path.join(tmp, "phase1.csv")
    with open(p1, "w") as fh:
        fh.write(out)
    return p1


def test_phase2(tmp, p1):
    print("[phase2] aggregate")
    out = run([os.path.join(SCRIPTS, "phase2.py"), p1])
    header, rows = read_csv(out)
    by = {r[0]: r for r in rows}
    check("phase2 header", header == ["email", "earliest_date", "latest_date"])
    check("10 addresses", len(rows) == 10)
    check("alice earliest 2016-02-02", by["alice@example.com"][1] == "2016-02-02T11:11:11Z")
    check("alice latest 2019-07-15", by["alice@example.com"][2] == "2019-07-15T22:58:53Z")
    check("bob earliest 2014 (bcc)", by["bob@example.com"][1] == "2014-04-04T04:04:04Z")
    check("bob latest 2020 (from)", by["bob@example.com"][2] == "2020-11-20T08:30:00Z")
    check("self earliest 2013 (trash)", by[SELF][1] == "2013-03-03T03:03:03Z")
    check("self latest 2021 (hex)", by[SELF][2].startswith("2021"))
    check("sorted most-recent first (row0 latest is 2021)", rows[0][2].startswith("2021"))
    p2 = os.path.join(tmp, "phase2.csv")
    with open(p2, "w") as fh:
        fh.write(out)
    return p2


def test_phase3(p2):
    print("[phase3] dormant filter")
    expected = ["someone@example.net", "grace@example.org", "carol@example.net",
                "dave@example.net", "eve@example.net", "frank@example.net"]

    # flag mode: ignore self, retain alice, N=6 -> cutoff 2020-06-29
    out = run([os.path.join(SCRIPTS, "phase3.py"), p2, "--years", "6", "--today", TODAY,
               "--ignore", SELF, "--retain", "alice@example.com"])
    header, rows = read_csv(out)
    emails = [r[0] for r in rows]
    check("phase3 header", header == ["email", "earliest_date", "latest_date"])
    check("dormant set exact + ordered", emails == expected)
    check("active hexguy excluded (recent)", "hexguy@example.net" not in emails)
    check("active bob excluded (recent)", "bob@example.com" not in emails)
    check("retained alice excluded", "alice@example.com" not in emails)
    check("ignored self excluded", SELF not in emails)
    check("dormant rows keep earliest+latest",
          rows[0] == ["someone@example.net", "2014-04-04T04:04:04Z", "2017-01-10T12:00:00Z"])

    # ignore normalizes case + plus-tag (Gmail dot collapse covered in test_units)
    out2 = run([os.path.join(SCRIPTS, "phase3.py"), p2, "--years", "6", "--today", TODAY,
                "--ignore", "  OWNER+promo@Example.Com ", "--retain", "alice@example.com"])
    check("ignore normalization (case/plus) drops self", SELF not in [r[0] for r in read_csv(out2)[1]])

    # interactive mode (stdin) agrees with flag mode
    out3 = run([os.path.join(SCRIPTS, "phase3.py"), p2, "--today", TODAY],
               stdin=f"{SELF}\nalice@example.com\n6\n")
    check("interactive mode matches flag mode", [r[0] for r in read_csv(out3)[1]] == expected)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="dormant_pipeline_")
    test_units()
    p1 = test_phase1(tmp)
    p2 = test_phase2(tmp, p1)
    test_phase3(p2)
    print(f"\nALL PASSED ({passed} checks)")
