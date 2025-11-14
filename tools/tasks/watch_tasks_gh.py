#!/usr/bin/env python3
"""CLI runner for GH-backed task watcher and workers.

States and attempt counts live in GitHub Project fields. Local FS is used only
for lock files during claim.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

from .taskwatch.adapters import CodexLLM, LocalFS, StdoutReporter
from .taskwatch.ghcli import GHCLI
from .taskwatch.domain_gh import GHWatcher, GHWorker, STATE_VALUES
from .taskwatch.logjson import JsonlLogger
from .taskwatch.domain import ensure_dirs, make_paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--wave', type=int, required=True)
    ap.add_argument('--project', type=str, default=None, help='Project title (default: SLAPS Run <date>)')
    args = ap.parse_args()

    wave = args.wave
    gh = GHCLI()
    # Default project name: SLAPS-{repo}
    if args.project:
        proj_title = args.project
    else:
        try:
            repo_name = gh.repo_name()
        except Exception:
            repo_name = "repo"
        proj_title = f"SLAPS-{repo_name}"

    base = Path('.slaps/tasks')
    fs = LocalFS()
    reporter = StdoutReporter()
    jsonl = JsonlLogger(path=base.parent / 'logs' / 'events.jsonl')
    watcher = GHWatcher(gh=gh, fs=fs, reporter=reporter, logger=jsonl,
                        raw_dir=base / 'raw', lock_dir=base / 'lock', project_title=proj_title)

    # Preflight and initialization
    watcher.preflight(wave)
    watcher.initialize_items(wave)
    watcher.unlock_sweep(wave)

    # Build state and workers
    assert watcher.state is not None
    project = watcher.state.project
    fields = watcher.state.fields
    llm = CodexLLM()

    stop = threading.Event()
    workers: list[threading.Thread] = []

    wave_issue = None
    try:
        # If coordinator created a wave status issue, its number may be passed via env
        wave_issue_env = os.environ.get('WAVE_STATUS_ISSUE')
        if wave_issue_env:
            wave_issue = int(wave_issue_env)
    except Exception:
        wave_issue = None

    def worker_loop(wid: int) -> None:
        w = GHWorker(worker_id=wid, gh=gh, fs=fs, reporter=reporter, logger=jsonl,
                     locks=base / 'lock', project=project, fields=fields, wave=wave, wave_issue=wave_issue)
        while not stop.is_set():
            # Pick an open issue
            open_issues = w._list_open_issues(wave)
            if not open_issues:
                reporter.report(f"[WORKER:{wid:03d}] Open issues: 0; sleeping")
                time.sleep(10)
                continue
            reporter.report(f"[WORKER:{wid:03d}] Open issues: {len(open_issues)}")
            claimed = False
            for issue in open_issues:
                if w.claim_and_verify(issue):
                    claimed = True
                    w.work_issue(issue, llm)
                    break
            if not claimed:
                time.sleep(5)

    def watcher_loop() -> None:
        while not stop.is_set():
            watcher.watch_locks()
            watcher.unlock_sweep(wave)
            time.sleep(2)

    # Spawn workers (allow override to reduce GH pressure)
    n = int(os.environ.get('SLAPS_WORKERS', str(os.cpu_count() or 1)))
    for i in range(1, n + 1):
        t = threading.Thread(target=worker_loop, name=f"gh-worker-{i}", args=(i,), daemon=True)
        workers.append(t)
        t.start()

    wt = threading.Thread(target=watcher_loop, name="gh-watcher", daemon=True)
    wt.start()

    def _sigint(signum, frame):
        reporter.report("received signal, shutting down...")
        stop.set()
        time.sleep(0.5)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    # Finish condition: all wave issues are in {closed, dead}
    wave_issues = watcher._list_wave_issues_from_raw(wave)
    while True:
        done = 0
        items = gh.list_items(project)
        for it in items:
            content = it.get("content") or {}
            num = content.get("number")
            if num not in wave_issues:
                continue
            fields = { (f.get("name") or f.get("field", {}).get("name") or "").strip(): f.get("value") for f in (it.get("fields") or []) }
            st = fields.get("slaps-state")
            st = st.get("name") if isinstance(st, dict) else st
            if st in ("closed", "dead"):
                done += 1
        reporter.report(f"[SYSTEM] Wave {wave} progress: {done}/{len(wave_issues)}")
        if done >= len(wave_issues):
            stop.set()
            break
        time.sleep(5)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
