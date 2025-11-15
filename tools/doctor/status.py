#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def parse_events(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def main() -> int:
    events_p = Path('.slaps/logs/events.jsonl')
    rows = parse_events(events_p)
    if not rows:
        print('status: no events found')
        return 1
    c = Counter(r.get('event') for r in rows)
    last = rows[-1]
    # summarize
    print('STATUS SUMMARY')
    print('---------------')
    print(f"Total events: {len(rows)}")
    for k in ('doctor_pass','doctor_fail','degraded','ok','claimed','success','failure_reopen','dead','unlock_open'):
        if c.get(k):
            print(f"{k}: {c[k]}")
    print(f"Last event: {last.get('event')} @ {last.get('ts')}")
    # alarm
    if c.get('doctor_fail', 0) > 0 or c.get('degraded', 0) > 0:
        print('status: ALARM (doctor_fail/degraded present)')
        return 1
    print('status: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

