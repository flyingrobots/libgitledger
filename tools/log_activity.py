#!/usr/bin/env python3
"""Append an activity entry to ACTIVITY.log.jsonl.

Example:
    tools/log_activity.py \
        --who AGENT \
        --what "Ran lint" \
        --where README.md --where tools/ \
        --why "Need clean docs" \
        --how "Updated prose and scripts" \
        --protip "Docs drift fast" --when now

If --when is omitted or set to "now", the current UTC timestamp is used.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

LOG_PATH = Path("ACTIVITY.log.jsonl")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--who", required=True)
    parser.add_argument("--what", required=True)
    parser.add_argument("--where", action="append", default=[], help="Repeat for each file path")
    parser.add_argument("--why", required=True)
    parser.add_argument("--how", required=True)
    parser.add_argument("--protip", required=True)
    parser.add_argument(
        "--when",
        default="now",
        help="RFC 3339 timestamp, or 'now' (default) for the current UTC time",
    )
    return parser.parse_args()


def _render_timestamp(raw: str) -> str:
    if raw.lower() == "now":
        return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        parsed = _dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - user input
        raise SystemExit(f"invalid --when value '{raw}': {exc}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    args = _parse_args()
    entry = {
        "who": args.who,
        "what": args.what,
        "where": args.where,
        "when": _render_timestamp(args.when),
        "why": args.why,
        "how": args.how,
        "protip": args.protip,
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":  # pragma: no cover - CLI entry
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - interactive interrupt
        sys.exit(130)
