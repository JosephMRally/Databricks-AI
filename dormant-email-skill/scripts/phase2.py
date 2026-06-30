#!/usr/bin/env python3
"""
phase2.py — Phase 2 of the dormant-email pipeline.

Read Phase 1's occurrence log and aggregate it with a dict: for each address, the
EARLIEST and LATEST date it was seen. One row per address out.

Input : phase1.csv  (columns: email,date)
Output: CSV `email,earliest_date,latest_date` on stdout (redirect into phase2.csv),
        sorted most-recently-seen first (undated addresses sink to the bottom).

Pure stdlib.

Usage:
  python3 scripts/phase2.py phase1.csv > phase2.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone


def parse_iso(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def aggregate(path):
    """Return {email: [earliest, latest]} over phase1.csv rows."""
    spans = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    start = 1 if rows and rows[0] and rows[0][0].strip().lower() == "email" else 0
    for row in rows[start:]:
        if not row or not row[0].strip():
            continue
        email = row[0].strip().lower()
        dt = parse_iso(row[1]) if len(row) > 1 else None
        span = spans.setdefault(email, [None, None])  # [earliest, latest]
        if dt is None:
            continue
        if span[0] is None or dt < span[0]:
            span[0] = dt
        if span[1] is None or dt > span[1]:
            span[1] = dt
    return spans


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 2: aggregate phase1.csv into earliest/latest per address.")
    ap.add_argument("phase1_csv", help="CSV from Phase 1 (email,date)")
    args = ap.parse_args(argv)

    spans = aggregate(args.phase1_csv)
    out = [(email, e, l) for email, (e, l) in spans.items()]
    # most-recently-seen first; undated (no latest) sink to bottom; tie-break by email
    out.sort(key=lambda t: (0, -t[2].timestamp(), t[0]) if t[2] else (1, 0.0, t[0]))

    w = csv.writer(sys.stdout)
    w.writerow(["email", "earliest_date", "latest_date"])
    for email, e, l in out:
        w.writerow([email, iso(e), iso(l)])
    print(f"[phase2] addresses: {len(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
