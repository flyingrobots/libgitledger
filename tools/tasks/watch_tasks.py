#!/usr/bin/env python3
"""CLI runner for task watcher using hexagonal architecture ports/adapters."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path

from .taskwatch.adapters import CodexLLM, LocalFS, RealSleeper, StdoutReporter
from .taskwatch.domain import Watcher, Worker, default_paths, ensure_dirs, make_paths
from .taskwatch.logjson import JsonlLogger
import re


def _parse_wave_issues(wave: int) -> set[int]:
    path = Path('docs/ROADMAP-DAG.md')
    if not path.exists():
        return set()
    issues: set[int] = set()
    current: int | None = None
    node_re = re.compile(r"\bN(\d+)\[")
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            m = re.search(r"subgraph\\s+Phase(\\d+)", line)
            if m:
                current = int(m.group(1))
                continue
            if line.strip() == 'end':
                current = None
                continue
            if current is not None and current == wave:
                nm = node_re.search(line)
                if nm:
                    try:
                        issues.add(int(nm.group(1)))
                    except Exception:
                        pass
    return issues


def _parse_wave_map() -> dict[int, int]:
    path = Path('docs/ROADMAP-DAG.md')
    mapping: dict[int, int] = {}
    if not path.exists():
        return mapping
    current: int | None = None
    node_re = re.compile(r"\bN(\d+)\[")
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            m = re.search(r"subgraph\\s+Phase(\\d+)", line)
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


def _bucket_prompts_to_wave(fs: LocalFS, base_root: Path, mapping: dict[int, int], wave: int) -> None:
    # Move global blocked/open prompts into wave-specific dirs if their issue maps to this wave
    global_blocked = base_root / 'blocked'
    global_open = base_root / 'open'
    dst_paths = make_paths(base_root, wave)
    ensure_dirs(fs, dst_paths)
    for src_dir, dst_dir in [(global_blocked, dst_paths.blocked), (global_open, dst_paths.open)]:
        for p in fs.list_files(src_dir):
            m = re.search(r"(\d+)", p.name)
            if not m:
                continue
            issue = int(m.group(1))
            if mapping.get(issue) == wave:
                fs.move_atomic(p, dst_dir / p.name)


def run() -> int:
    base = Path('.slaps/tasks')
    fs = LocalFS()
    llm = CodexLLM()
    reporter = StdoutReporter()
    sleeper = RealSleeper()
    # Determine wave selection
    wave = None
    args = sys.argv[1:]
    for i in range(len(args)):
        if args[i] == '--wave' and i + 1 < len(args):
            try:
                wave = int(args[i + 1])
            except Exception:
                wave = None
            break
    if wave is None:
        try:
            wave = int(os.environ.get('TASK_WAVE', ''))
        except Exception:
            wave = None

    # Bucket prompts into wave dirs if wave specified
    if wave:
        wave_map = _parse_wave_map()
        reporter.report(f"[SYSTEM] Wave filter active: Phase {wave}")
        _bucket_prompts_to_wave(fs, base, wave_map, wave)

    # Use wave-specific queue directories if wave provided
    paths = make_paths(base_root=base, wave=wave)
    # JSONL logger
    jsonl = JsonlLogger(path=base.parent / 'logs' / 'events.jsonl')

    # Parse optional wave selection from argv/env
    wave = None
    args = sys.argv[1:]
    for i in range(len(args)):
        if args[i] == '--wave' and i + 1 < len(args):
            try:
                wave = int(args[i + 1])
            except Exception:
                wave = None
            break
    if wave is None:
        try:
            wave = int(os.environ.get('TASK_WAVE', ''))
        except Exception:
            wave = None
    allowed_issues = _parse_wave_issues(wave) if wave else None
    if allowed_issues:
        reporter.report(f"[SYSTEM] Wave filter active: Phase {wave} with {len(allowed_issues)} tasks")

    # Ensure directories exist before device checks
    ensure_dirs(fs, paths)

    # Sanity: verify all task directories reside on the same filesystem device so
    # atomic os.replace acts as our mutex. If not, abort loudly.
    try:
        devs = set()
        for d in [paths.open, paths.blocked, paths.claimed, paths.closed, paths.failed, paths.dead, paths.admin, paths.raw]:
            devs.add((d.stat().st_dev, d))
        if len({dev for dev, _ in devs}) != 1:
            reporter.report("ERROR: .slaps/tasks subdirectories are on different filesystems; atomic rename cannot be guaranteed. Please place them on the same device.")
            return 2
    except Exception as e:
        reporter.report(f"WARNING: device check failed: {e}")

    watcher = Watcher(fs=fs, llm=llm, reporter=reporter, paths=paths, logger=jsonl)

    stop_event = threading.Event()
    workers: list[Worker] = []

    def worker_thread(w: Worker) -> None:
        while not stop_event.is_set():
            worked = w.run_once()
            if not worked:
                # Add jitter to avoid thundering herd: 20-30s
                import random
                sleeper.sleep(20 + random.random() * 10)

    # Start workers
    n = os.cpu_count() or 1
    for i in range(1, n + 1):
        w = Worker(worker_id=i, fs=fs, llm=llm, paths=paths, reporter=reporter, logger=jsonl)
        workers.append(w)
        t = threading.Thread(target=worker_thread, name=f"worker-{i}", args=(w,), daemon=True)
        t.start()

    def _sigint(signum, frame):
        reporter.report("received signal, shutting down...")
        stop_event.set()
        time.sleep(0.5)
        watcher.print_report(workers)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    reporter.report("watcher started; monitoring .slaps/tasks/")
    # Perform a cold-start sweep to unlock any tasks based on existing closed files/markers.
    watcher.startup_sweep(workers)
    while True:
        # detect closed
        closed_now = {p.name for p in fs.list_files(paths.closed)}
        new_closed = [paths.closed / n for n in sorted(closed_now - watcher.closed_seen)]
        watcher.closed_seen = closed_now
        for p in new_closed:
            watcher.handle_closed(p, workers)

        # detect failed
        failed_now = {p.name for p in fs.list_files(paths.failed)}
        new_failed = [paths.failed / n for n in sorted(failed_now - watcher.failed_seen)]
        watcher.failed_seen = failed_now
        for p in new_failed:
            watcher.handle_failed(p, workers)

        # periodic sweep to catch unlocks from externally added markers
        watcher.startup_sweep(workers)

        # finish condition
        if not fs.list_files(paths.open) and not fs.list_files(paths.blocked) and all(w.current_issue is None for w in workers):
            reporter.report("All work complete. Final report:")
            watcher.print_report(workers)
            return 0
        time.sleep(2)


def main() -> int:
    try:
        return run()
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
