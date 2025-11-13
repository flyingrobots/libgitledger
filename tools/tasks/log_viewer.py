#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def has_session(session: str) -> bool:
    return subprocess.call(['tmux', 'has-session', '-t', session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def list_windows(session: str) -> set[str]:
    try:
        out = subprocess.check_output(['tmux', 'list-windows', '-t', session, '-F', '#{window_name}'], text=True)
        return set(line.strip() for line in out.splitlines() if line.strip())
    except subprocess.CalledProcessError:
        return set()


def ensure_window(session: str, name: str, cmd: str) -> None:
    wins = list_windows(session)
    if name in wins:
        return
    run(['tmux', 'new-window', '-t', session, '-n', name, 'bash', '-lc', cmd])


def ensure_split(session: str, target: str, cmd: str) -> None:
    run(['tmux', 'split-window', '-h', '-t', f'{session}:{target}', 'bash', '-lc', cmd])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--iterm', action='store_true', help='Attach using tmux -CC for iTerm2 native integration')
    ap.add_argument('--reuse', action='store_true', help='Reuse existing session; add missing panes/windows')
    ap.add_argument('--follow', action='store_true', help='Follow worker dirs and add windows dynamically')
    args = ap.parse_args()

    base = Path('.slaps/logs')
    viewer_dir = base / 'viewer'
    viewer_dir.mkdir(parents=True, exist_ok=True)
    out = (viewer_dir / 'stdout.txt').open('a', encoding='utf-8')
    err = (viewer_dir / 'stderr.txt').open('a', encoding='utf-8')

    def log(msg: str):
        print(msg, file=out, flush=True)

    session = 'slaps-logs'
    log(f'Preparing tmux session {session}')
    exists = has_session(session)
    if exists and not args.reuse:
        log(f'Session {session} exists; killing and recreating')
        run(['tmux', 'kill-session', '-t', session])
        exists = False

    # Create session if needed
    if not exists:
        run(['tmux', 'new-session', '-d', '-s', session, '-n', 'events', 'bash', '-lc', 'tail -F .slaps/logs/events.jsonl'])
    else:
        # Ensure events window exists
        ensure_window(session, 'events', 'tail -F .slaps/logs/events.jsonl')

    # coord window: out + err
    ensure_window(session, 'coord', 'tail -F .slaps/logs/coord.out')
    ensure_split(session, 'coord', 'tail -F .slaps/logs/coord.err')
    # watcher window: out + err
    ensure_window(session, 'watcher', 'tail -F .slaps/logs/watcher.out')
    ensure_split(session, 'watcher', 'tail -F .slaps/logs/watcher.err')

    # assistant monitor (aggregated summary)
    ensure_window(session, 'amon', 'python3 tools/tasks/assistant_monitor.py')

    # workers windows
    def seed_workers(max_workers: int = 8):
        n = os.cpu_count() or 4
        n = min(n, max_workers)
        for i in range(1, n + 1):
            win = f'w{i:02d}'
            stdout_path = f'.slaps/logs/workers/{i:03d}/current-llm.stdout.txt'
            stderr_path = f'.slaps/logs/workers/{i:03d}/current-llm.stderr.txt'
            ensure_window(session, win, f'tail -F {stdout_path}')
            ensure_split(session, win, f'tail -F {stderr_path}')

    seed_workers()

    # Follow mode: dynamically add worker windows as dirs appear
    if args.follow:
        log('Entering follow mode (polling .slaps/logs/workers)')
        base_workers = Path('.slaps/logs/workers')
        seen: set[str] = set(list_windows(session))
        try:
            while True:
                if base_workers.exists():
                    for d in sorted(base_workers.iterdir()):
                        if not d.is_dir():
                            continue
                        try:
                            wid = int(d.name)
                        except ValueError:
                            continue
                        win = f'w{wid:02d}'
                        if win not in list_windows(session):
                            stdout_path = f'.slaps/logs/workers/{wid:03d}/current-llm.stdout.txt'
                            stderr_path = f'.slaps/logs/workers/{wid:03d}/current-llm.stderr.txt'
                            log(f'Adding dynamic worker window {win}')
                            ensure_window(session, win, f'tail -F {stdout_path}')
                            ensure_split(session, win, f'tail -F {stderr_path}')
                time.sleep(5)
        except KeyboardInterrupt:
            log('Follow mode interrupted')
            out.close(); err.close()
            return 0

    # Attach or exit
    if args.iterm and not args.follow:
        log('Attaching with tmux -CC (iTerm2 native integration)')
        out.close(); err.close()
        return subprocess.call(['tmux', '-CC', 'attach', '-t', session])
    else:
        log('Log viewer setup complete. Attach with: tmux attach -t slaps-logs')
        out.close(); err.close()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
