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
            m = re.search(r"subgraph\s+Phase(\d+)", line)
            if m:
                max_wave = max(max_wave, int(m.group(1)))
    return max_wave


def run_watcher(wave: int) -> int:
    logs = Path('.slaps/logs')
    logs.mkdir(parents=True, exist_ok=True)
    out_f = (logs / 'watcher.out').open('a', encoding='utf-8')
    err_f = (logs / 'watcher.err').open('a', encoding='utf-8')
    try:
        proc = subprocess.Popen([sys.executable, '-m', 'tools.tasks.watch_tasks', '--wave', str(wave)], stdout=out_f, stderr=err_f)
        rc = proc.wait()
        return rc
    finally:
        out_f.close(); err_f.close()


def count_dead(base: Path, wave: int) -> int:
    dead = base / str(wave) / 'dead'
    if not dead.exists():
        return 0
    return len([p for p in dead.iterdir() if p.is_file()])


def run_guardian(jsonl: JsonlLogger) -> int:
    prompt = (
        "Please read through the git repo and gain an understanding of the project. You are assigned the role of Lead QUALITY GUARDIAN — you're picking up after a swarm of LLMs just chewed through a bunch of tasks.\n"
        "They were all working together on top of each other in pure chaos. The dust has settled — now stabilize quality.\n\n"
        "POLICY:\n"
        "- TESTS MUST RUN IN DOCKER via Make targets: use 'make test-both' (and 'make lint' as needed).\n"
        "- DO NOT run tests directly on the host.\n"
        "- You may use git to commit changes locally; the coordinator will push afterwards.\n\n"
        "Workflow:\n"
        "1. Using git, examine the current working tree and staged changes (if any). Note the source files that changed.\n"
        "2. Examine the tests: ensure that tests comprehensively cover the changed code. If gaps exist, add tests.\n"
        "3. Run tests using 'make test-both' (Docker).\n"
        "4. If tests pass, git commit with a helpful message and EXIT 0.\n"
        "5. If tests fail: emit JSONL entries for each failure, implement minimal fixes, and go to step 3.\n\n"
        "ALL OUTPUT MUST BE IN JSONL FORMAT."
    )
    jsonl.emit('guardian_start')
    try:
        rc = subprocess.call(['codex', 'exec', prompt])
        jsonl.emit('guardian_finish', rc=rc)
        return rc
    except FileNotFoundError:
        jsonl.emit('guardian_finish', rc=127, error='codex not found')
        return 127


def push_changes(jsonl: JsonlLogger) -> int:
    try:
        rc = subprocess.call(['git', 'push'])
        jsonl.emit('push_finish', rc=rc)
        return rc
    except FileNotFoundError:
        jsonl.emit('push_finish', rc=127, error='git not found')
        return 127


def preflight(jsonl: JsonlLogger, no_commit: bool = False) -> int:
    jsonl.emit('preflight_start')
    # Docker available
    try:
        rc = subprocess.call(['docker', 'version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        jsonl.emit('preflight_check', name='docker', rc=rc)
        if rc != 0:
            print('[PREFLIGHT] Docker not available or not running', file=sys.stderr)
            return 1
    except FileNotFoundError:
        jsonl.emit('preflight_check', name='docker', rc=127)
        print('[PREFLIGHT] docker CLI not found', file=sys.stderr)
        return 1
    # Make targets present
    for tgt in ('test-both', 'lint'):
        rc = subprocess.call(['make', '-n', tgt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        jsonl.emit('preflight_check', name=f'make-{tgt}', rc=rc)
        if rc != 0:
            print(f'[PREFLIGHT] make target {tgt} unavailable', file=sys.stderr)
            return 1
    # Small commit and push (optional)
    if no_commit:
        jsonl.emit('preflight_skip_push', reason='no-commit flag set')
    else:
        pf = Path('docs/PREFLIGHT.md')
        pf.parent.mkdir(parents=True, exist_ok=True)
        with pf.open('a', encoding='utf-8') as f:
            f.write('Preflight OK\n')
        jsonl.emit('preflight_update_file', path=str(pf))
        rc = subprocess.call(['git', 'add', str(pf)])
        jsonl.emit('preflight_git_add', rc=rc)
        if rc != 0:
            print('[PREFLIGHT] git add failed', file=sys.stderr)
            return 1
        rc = subprocess.call(['git', 'commit', '-m', 'Preflight: validate push permissions'])
        jsonl.emit('preflight_git_commit', rc=rc)
        # If nothing to commit, still try push
        prc = push_changes(jsonl)
        if prc != 0:
            print('[PREFLIGHT] git push failed', file=sys.stderr)
            return 1
    jsonl.emit('preflight_finish', rc=0)
    return 0


def run_followups(wave: int, jsonl: JsonlLogger) -> int:
    jsonl.emit('followups_start', wave=wave)
    rc = subprocess.call([sys.executable, 'tools/tasks/process_followups.py', '--wave', str(wave)])
    jsonl.emit('followups_finish', wave=wave, rc=rc)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--waveStart', type=int, default=None)
    ap.add_argument('--no-commit-preflight', action='store_true', help='Skip git commit/push during preflight')
    args = ap.parse_args()

    wave_start = args.waveStart or int(os.environ.get('TASK_WAVE_START', '0') or 0)
    roadmap = Path('docs/ROADMAP-DAG.md')
    max_wave = parse_max_wave(roadmap)
    if wave_start <= 0 or max_wave <= 0:
        print('Invalid waveStart or roadmap not found', file=sys.stderr)
        return 2

    base = Path('.slaps/tasks')
    jsonl = JsonlLogger(path=base.parent / 'logs' / 'events.jsonl')
    # Preflight environment
    if preflight(jsonl, no_commit=args.no_commit_preflight) != 0:
        return 1

    for wave in range(wave_start, max_wave + 1):
        jsonl.emit('wave_start', wave=wave)
        print(f"[COORD] Running watcher for wave {wave}")
        rc = run_watcher(wave)
        jsonl.emit('watcher_finish', wave=wave, rc=rc)
        if rc != 0:
            print(f"[COORD] Watcher returned {rc}; aborting", file=sys.stderr)
            return 1

        # Process follow-ups and run a follow-up watcher pass if any were enqueued
        frc = run_followups(wave, jsonl)
        if frc == 0:
            # A follow-up prompt may have been enqueued; run a quick pass
            print(f"[COORD] Running follow-up watcher pass for wave {wave}")
            rc = run_watcher(wave)
            jsonl.emit('watcher_followup_finish', wave=wave, rc=rc)
            if rc != 0:
                print(f"[COORD] Follow-up watcher returned {rc}; aborting", file=sys.stderr)
                return 1

        dead_count = count_dead(base, wave)
        jsonl.emit('dead_count', wave=wave, count=dead_count)
        if dead_count > 0:
            print(f"[COORD] Dead queue has {dead_count} files (>0). Aborting.", file=sys.stderr)
            return 1

        print(f"[COORD] Running Quality Guardian LLM")
        rc = run_guardian(jsonl)
        if rc != 0:
            print(f"[COORD] Guardian returned {rc}; aborting", file=sys.stderr)
            return 1
        # Push changes after guardian success
        prc = push_changes(jsonl)
        if prc != 0:
            print(f"[COORD] git push failed with {prc}; aborting", file=sys.stderr)
            return 1
        jsonl.emit('wave_complete', wave=wave)

    print("[COORD] All waves complete")
    jsonl.emit('all_complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
