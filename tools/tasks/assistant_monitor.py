#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any


def count_dirs(path: Path) -> int:
    try:
        return len([p for p in path.iterdir() if p.is_file()])
    except FileNotFoundError:
        return 0


def scan_filesystem(base: Path) -> Dict[str, Any]:
    waves = []
    # Global queues
    g_open = count_dirs(base / 'open')
    g_blocked = count_dirs(base / 'blocked')
    g_closed = count_dirs(base / 'closed')
    g_failed = count_dirs(base / 'failed')
    g_dead = count_dirs(base / 'dead')
    # Per-wave queues (1..99)
    for w in range(1, 100):
        wpath = base / str(w)
        if not wpath.exists():
            continue
        waves.append({
            'wave': w,
            'open': count_dirs(wpath / 'open'),
            'blocked': count_dirs(wpath / 'blocked'),
            'closed': count_dirs(wpath / 'closed'),
            'failed': count_dirs(wpath / 'failed'),
            'dead': count_dirs(wpath / 'dead'),
        })
    return {
        'global': {'open': g_open, 'blocked': g_blocked, 'closed': g_closed, 'failed': g_failed, 'dead': g_dead},
        'waves': waves,
    }


def parse_events(path: Path, max_lines: int = 5000) -> Dict[str, Any]:
    stats = {
        'moves': 0,
        'claimed': 0,
        'closed': 0,
        'failed': 0,
        'retries': 0,
        'guardian_rc': None,
        'last_ts': None,
    }
    if not path.exists():
        return stats
    try:
        lines = path.read_text(encoding='utf-8').splitlines()[-max_lines:]
    except Exception:
        return stats
    for line in lines:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        stats['last_ts'] = ev.get('ts') or stats['last_ts']
        e = ev.get('event')
        if e == 'move':
            stats['moves'] += 1
            if ev.get('to_dir') == 'claimed':
                stats['claimed'] += 1
            if ev.get('to_dir') == 'closed':
                stats['closed'] += 1
            if ev.get('to_dir') == 'failed':
                stats['failed'] += 1
        elif e == 'retry':
            stats['retries'] += 1
        elif e == 'guardian_finish':
            stats['guardian_rc'] = ev.get('rc')
    return stats


def main() -> int:
    base = Path('.slaps/logs')
    viewer = base / 'viewer'
    viewer.mkdir(parents=True, exist_ok=True)
    out = (viewer / 'assistant.txt').open('a', encoding='utf-8')
    tasks_root = Path('.slaps/tasks')
    events = base / 'events.jsonl'
    try:
        while True:
            fs = scan_filesystem(tasks_root)
            ev = parse_events(events)
            line = {
                'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'global': fs['global'],
                'waves': fs['waves'],
                'events': ev,
            }
            s = json.dumps(line)
            # Write to file and stdout so the 'amon' window is useful by itself
            out.write(s + '\n')
            out.flush()
            print(s, flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
