#!/usr/bin/env python3
"""
phase3.py — Phase 3 of the dormant-email pipeline.

Reduce Phase 2's per-address table to the DORMANT set the user cares about. Three
inputs — prompted interactively when --years is omitted, or passed as flags for
unattended/agent runs:
  * ignore   : addresses to DROP from the output entirely (e.g. your own address)
  * retain   : addresses to PROTECT — never list as dormant even if they qualify
               (e.g. personal / legal-government / financial contacts)
  * N (years): cutoff = today − N years. An address is "dormant" when its
               latest_date is older than the cutoff.

An address lands in the output iff:  dormant  AND  not ignored  AND  not retained.
ignore/retain matching is Gmail dot/plus-insensitive. Undated addresses are treated
as NOT dormant (we never act on an unknown date).

Input : phase2.csv  (email,earliest_date,latest_date)
Output: CSV `email,earliest_date,latest_date` on stdout (redirect into phase3.csv),
        most-recently-seen first.

Usage (interactive):  python3 scripts/phase3.py phase2.csv > phase3.csv
Usage (automation) :  python3 scripts/phase3.py phase2.csv --years 5 \
                          --ignore you@example.com --retain mom@example.com > phase3.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone

_GMAIL = {"gmail.com", "googlemail.com"}


def canonical(addr):
    """Lowercase; collapse Gmail dot/plus variants so ignore/retain match reliably."""
    addr = (addr or "").strip().lower()
    if "@" not in addr:
        return addr
    local, _, domain = addr.partition("@")
    local = local.split("+", 1)[0]
    if domain in _GMAIL:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def parse_iso(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def split_addrs(values):
    """Flatten repeatable, comma/space-separated address flags into a canonical set."""
    out = set()
    for chunk in values or []:
        for piece in chunk.replace(",", " ").split():
            c = canonical(piece)
            if c:
                out.add(c)
    return out


def cutoff_datetime(years, today):
    """today − N years, as a midnight-UTC datetime (Feb-29 guarded)."""
    try:
        d = today.replace(year=today.year - years)
    except ValueError:
        d = today.replace(year=today.year - years, day=28)  # Feb 29 -> Feb 28
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _prompt(msg):
    try:
        return input(msg)
    except EOFError:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 3: filter phase2.csv to the dormant set (ignore/retain/cutoff).")
    ap.add_argument("phase2_csv", help="CSV from Phase 2 (email,earliest_date,latest_date)")
    ap.add_argument("--years", type=int, default=None, help="cutoff N; if omitted, prompt interactively")
    ap.add_argument("--ignore", action="append", default=[], help="address(es) to drop entirely (repeatable/comma-sep)")
    ap.add_argument("--retain", action="append", default=[], help="address(es) to protect from the dormant list")
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD) for reproducible cutoffs")
    args = ap.parse_args(argv)

    if args.years is None:  # interactive mode
        ignore = split_addrs([_prompt("Addresses to IGNORE (drop entirely; comma-separated, blank = none): ")])
        retain = split_addrs([_prompt("Addresses to RETAIN (protect from dormant list; comma-separated, blank = none): ")])
        raw_years = _prompt("Cutoff N in whole years (dormant = no contact in N years): ").strip()
        try:
            years = int(raw_years)
        except ValueError:
            print(f"phase3: '{raw_years}' is not an integer", file=sys.stderr)
            return 2
    else:
        ignore = split_addrs(args.ignore)
        retain = split_addrs(args.retain)
        years = args.years

    today = parse_iso(args.today) or datetime.now(timezone.utc)
    cutoff = cutoff_datetime(years, today)

    with open(args.phase2_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    start = 1 if rows and rows[0] and rows[0][0].strip().lower() == "email" else 0

    kept = []
    for row in rows[start:]:
        if not row or not row[0].strip():
            continue
        email = row[0].strip().lower()
        canon = canonical(email)
        if canon in ignore:
            continue
        earliest = row[1] if len(row) > 1 else ""
        latest_s = row[2] if len(row) > 2 else ""
        latest = parse_iso(latest_s)
        dormant = latest is not None and latest < cutoff
        if not dormant or canon in retain:
            continue
        kept.append((email, earliest, latest_s, latest))

    kept.sort(key=lambda t: (0, -t[3].timestamp(), t[0]) if t[3] else (1, 0.0, t[0]))

    w = csv.writer(sys.stdout)
    w.writerow(["email", "earliest_date", "latest_date"])
    for email, earliest, latest_s, _ in kept:
        w.writerow([email, earliest, latest_s])
    print(f"[phase3] cutoff={cutoff.strftime('%Y-%m-%d')} (N={years}y) "
          f"ignored={len(ignore)} retained={len(retain)} dormant_out={len(kept)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
