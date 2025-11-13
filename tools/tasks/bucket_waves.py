#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_wave_map(roadmap: Path) -> dict[int, int]:
    mapping: dict[int, int] = {}
    if not roadmap.exists():
        return mapping
    current: int | None = None
    node_re = re.compile(r"\bN(\d+)\[")
    with roadmap.open('r', encoding='utf-8') as f:
        for line in f:
            m = re.search(r"subgraph\s+Phase(\d+)", line)
            if m:
                current = int(m.group(1))
                continue
            if line.strip() == 'end':
                current = None
                continue
            if current is not None:
                nm = node_re.search(line)
                if nm:
                    try:
                        mapping[int(nm.group(1))] = current
                    except Exception:
                        pass
    return mapping


def ensure_dirs(base: Path, wave: int) -> None:
    w = base / str(wave)
    for name in ("open", "blocked", "claimed", "closed", "failed", "dead"):
        (w / name).mkdir(parents=True, exist_ok=True)


def bucket(base: Path, mapping: dict[int, int]) -> dict[str, int]:
    stats = {"open_moved": 0, "blocked_moved": 0, "open_skipped": 0, "blocked_skipped": 0}
    global_open = base / 'open'
    global_blocked = base / 'blocked'
    # Move blocked first, then open
    for src_dir, key_moved, key_skipped in (
        (global_blocked, "blocked_moved", "blocked_skipped"),
        (global_open, "open_moved", "open_skipped"),
    ):
        if not src_dir.exists():
            continue
        for p in sorted([x for x in src_dir.iterdir() if x.is_file()]):
            m = re.search(r"(\d+)", p.name)
            if not m:
                stats[key_skipped] += 1
                continue
            issue = int(m.group(1))
            wave = mapping.get(issue)
            if not wave:
                stats[key_skipped] += 1
                continue
            ensure_dirs(base, wave)
            dst = base / str(wave) / src_dir.name / p.name
            try:
                p.replace(dst)
                stats[key_moved] += 1
            except Exception:
                stats[key_skipped] += 1
    return stats


def main() -> int:
    root = Path('.slaps/tasks')
    roadmap = Path('docs/ROADMAP-DAG.md')
    mapping = parse_wave_map(roadmap)
    if not mapping:
        print("No wave mapping found; aborting.", file=sys.stderr)
        return 2
    stats = bucket(root, mapping)
    print(f"Bucketed: open_moved={stats['open_moved']} blocked_moved={stats['blocked_moved']} (skipped open={stats['open_skipped']} blocked={stats['blocked_skipped']})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

