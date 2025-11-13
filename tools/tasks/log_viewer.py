#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def main() -> int:
    base = Path('.slaps/logs')
    viewer_dir = base / 'viewer'
    viewer_dir.mkdir(parents=True, exist_ok=True)
    out = (viewer_dir / 'stdout.txt').open('a', encoding='utf-8')
    err = (viewer_dir / 'stderr.txt').open('a', encoding='utf-8')
    def log(msg: str):
        print(msg, file=out, flush=True)

    session = 'slaps-logs'
    log(f"Creating tmux session {session}")
    # Create session with events window
    run(['tmux', 'new-session', '-d', '-s', session, '-n', 'events', 'bash', '-lc', 'tail -F .slaps/logs/events.jsonl'])
    # coord window: out + err
    log('Adding coord window')
    run(['tmux', 'new-window', '-t', session, '-n', 'coord', 'bash', '-lc', 'tail -F .slaps/logs/coord.out'])
    run(['tmux', 'split-window', '-h', '-t', f'{session}:coord', 'bash', '-lc', 'tail -F .slaps/logs/coord.err'])
    # watcher window: out + err
    log('Adding watcher window')
    run(['tmux', 'new-window', '-t', session, '-n', 'watcher', 'bash', '-lc', 'tail -F .slaps/logs/watcher.out'])
    run(['tmux', 'split-window', '-h', '-t', f'{session}:watcher', 'bash', '-lc', 'tail -F .slaps/logs/watcher.err'])
    # worker LLM windows: per worker id (create first up to N)
    n = os.cpu_count() or 4
    n = min(n, 8)
    for i in range(1, n + 1):
        win = f'w{i:02d}'
        stdout_path = f'.slaps/logs/workers/{i:03d}/current-llm.stdout.txt'
        stderr_path = f'.slaps/logs/workers/{i:03d}/current-llm.stderr.txt'
        log(f'Adding worker window {win} for worker {i:03d}')
        run(['tmux', 'new-window', '-t', session, '-n', win, 'bash', '-lc', f'tail -F {stdout_path}'])
        run(['tmux', 'split-window', '-h', '-t', f'{session}:{win}', 'bash', '-lc', f'tail -F {stderr_path}'])

    log('Log viewer setup complete. Attach with: tmux attach -t slaps-logs')
    out.close(); err.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

