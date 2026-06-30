#!/usr/bin/env python3
"""
phase1.py — Phase 1 of the dormant-email pipeline.

A single sweep over the saved Gmail `search_threads` JSON pages. For EVERY message,
emit one CSV row for each address found in From / To / Cc / Bcc, paired with the
message date. This is the raw occurrence log — one row per (address, message) — which
Phase 2 aggregates. Output is streamed row-by-row, so memory stays flat even on a
huge mailbox.

Input : `search_threads` response page files (the agent fetched + saved them).
        Each file is one response object, or a JSON array of them.
Output: CSV `email,date` on stdout (redirect into phase1.csv).

Every message is counted — STARRED and TRASH included; missing `date` headers fall
back to the message-id hex timestamp. Pure stdlib.

Usage:
  python3 scripts/phase1.py pages/*.json > phase1.csv
  python3 scripts/phase1.py --exclude you@example.com pages/*.json > phase1.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone

HEADER_FIELDS = ["sender", "toRecipients", "ccRecipients", "bccRecipients"]  # From/To/Cc/Bcc
_ANGLE = re.compile(r"<([^<>]+)>")
_BARE = re.compile(r"[^\s<>,;\"']+@[^\s<>,;\"']+")
_NON_CONTACT = {"undisclosed-recipients:;", "undisclosed-recipients:", ""}


def extract_email(raw):
    """Bare lowercase address from a header token; None for non-addresses."""
    if not raw:
        return None
    token = raw.strip()
    if not token or token.lower() in _NON_CONTACT:
        return None
    m = _ANGLE.search(token)
    cand = m.group(1).strip() if m else token
    m2 = _BARE.search(cand)
    return m2.group(0).strip().lower() if m2 else None


def parse_date(msg):
    """UTC datetime from the ISO `date` header, else the message-id hex fallback."""
    raw = msg.get("date")
    if raw:
        try:
            dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    mid = msg.get("id")
    if mid:
        try:
            return datetime.fromtimestamp((int(mid, 16) >> 20) / 1000.0, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def iter_messages(paths):
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        for page in (data if isinstance(data, list) else [data]):
            for thread in page.get("threads", []) or []:
                for msg in thread.get("messages", []) or []:
                    yield msg


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 1: stream every (address, date) occurrence from search_threads pages.")
    ap.add_argument("pages", nargs="+", help="search_threads response JSON file(s)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="address to skip entirely (optional; repeatable)")
    args = ap.parse_args(argv)

    exclude = {a.strip().lower() for a in args.exclude if a.strip()}
    w = csv.writer(sys.stdout)
    w.writerow(["email", "date"])
    rows = 0
    for msg in iter_messages(args.pages):
        date = iso(parse_date(msg))
        seen = set()  # one row per address per message, even if it holds two roles
        for field in HEADER_FIELDS:
            value = msg.get(field)
            if not value:
                continue
            for tok in ([value] if isinstance(value, str) else value):
                email = extract_email(tok)
                if not email or email in exclude or email in seen:
                    continue
                seen.add(email)
                w.writerow([email, date])
                rows += 1
    print(f"[phase1] occurrence rows written: {rows}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
