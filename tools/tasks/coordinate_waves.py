#!/usr/bin/env python3
"""Wave coordinator: runs watcher per-wave, halts on dead queue overflow, and invokes Quality Guardian LLM to heal and test.

Usage:
  python3 tools/tasks/coordinate_waves.py --waveStart 1

Environment:
  TASK_WAVE_START may be used instead of argv.

Exit codes:
  0 -> all waves completed successfully
  1 -> dead queue overflow or guardian failure
  2 -> configuration error
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from .taskwatch.logjson import JsonlLogger


def parse_max_wave(roadmap: Path) -> int:
    if not roadmap.exists():
        return 0
    max_wave = 0
    with roadmap.open('r', encoding='utf-8') as f:
        for line in f:
            m = re.search(r"subgraph\\s+Phase(\\d+)", line)
            if m:
                max_wave = max(max_wave, int(m.group(1)))
    return max_wave


def run_watcher(wave: int) -> int:
    return subprocess.call([sys.executable, 'tools/tasks/watch_tasks.py', '--wave', str(wave)])


def count_dead(base: Path, wave: int) -> int:
    dead = base / str(wave) / 'dead'
    if not dead.exists():
        return 0
    return len([p for p in dead.iterdir() if p.is_file()])


def run_guardian(jsonl: JsonlLogger) -> int:
    prompt = (
        "Please read through the git repo and gain an understanding of the project. You are assigned the role of Lead QUALITY GUARDIAN - you're picking up after a swarm of LLMs just chewed through a bunch of tasks. They were all working together on top of each other in pure chaos. The dust has settled, but that's when you come in. Please git commit to the current branch (try to write a helpful commit message). Then:\n\n"
        "1. Using git, examine what you just committed. Note the source files that changed.\n"
        "2. Examine the tests: ensure that the tests that were written were comprehensive and cover the code that was committed. If you find gaps, cover them with new tests.\n"
        "3. Run the tests.\n"
        "4. If they pass, git commit, indicate success and exit 0.\n"
        "5. Else for each failure: indicate test case failed via output, then iterate on the affected code. After fixing the code, go to 3.\n\n"
        "ALL OUTPUT SHOULD BE IN JSONL FORMAT."
    )
    jsonl.emit('guardian_start')
    try:
        rc = subprocess.call(['codex', 'exec', prompt])
        jsonl.emit('guardian_finish', rc=rc)
        return rc
    except FileNotFoundError:
        jsonl.emit('guardian_finish', rc=127, error='codex not found')
        return 127


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--waveStart', type=int, default=None)
    args = ap.parse_args()

    wave_start = args.waveStart or int(os.environ.get('TASK_WAVE_START', '0') or 0)
    roadmap = Path('docs/ROADMAP-DAG.md')
    max_wave = parse_max_wave(roadmap)
    if wave_start <= 0 or max_wave <= 0:
        print('Invalid waveStart or roadmap not found', file=sys.stderr)
        return 2

    base = Path('.slaps/tasks')
    jsonl = JsonlLogger(path=base.parent / 'logs' / 'events.jsonl')

    for wave in range(wave_start, max_wave + 1):
        jsonl.emit('wave_start', wave=wave)
        print(f"[COORD] Running watcher for wave {wave}")
        rc = run_watcher(wave)
        jsonl.emit('watcher_finish', wave=wave, rc=rc)
        if rc != 0:
            print(f"[COORD] Watcher returned {rc}; aborting", file=sys.stderr)
            return 1

        dead_count = count_dead(base, wave)
        jsonl.emit('dead_count', wave=wave, count=dead_count)
        if dead_count > 1:
            print(f"[COORD] Dead queue has {dead_count} files (>1). Aborting.", file=sys.stderr)
            return 1

        print(f"[COORD] Running Quality Guardian LLM")
        rc = run_guardian(jsonl)
        if rc != 0:
            print(f"[COORD] Guardian returned {rc}; aborting", file=sys.stderr)
            return 1
        jsonl.emit('wave_complete', wave=wave)

    print("[COORD] All waves complete")
    jsonl.emit('all_complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

