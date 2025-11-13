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
from .taskwatch.domain import Watcher, Worker, default_paths


def run() -> int:
    base = Path('.slaps/tasks')
    fs = LocalFS()
    llm = CodexLLM()
    reporter = StdoutReporter()
    sleeper = RealSleeper()
    paths = default_paths(base)

    watcher = Watcher(fs=fs, llm=llm, reporter=reporter, paths=paths)

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
        w = Worker(worker_id=i, fs=fs, llm=llm, paths=paths)
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
