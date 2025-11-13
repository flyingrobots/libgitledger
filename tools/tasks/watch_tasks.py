#!/usr/bin/env python3
"""
Task watcher and worker pool for .slaps/tasks/

Responsibilities
- Maintain a pool of workers (size = CPU core count).
- Workers claim prompts from .slaps/tasks/open/, run `codex exec "{prompt}"`,
  capture stdout/stderr and route files to closed/failed accordingly.
- Append FAILURE diagnostics to failed prompt files.
- Watch .slaps/tasks/closed/ to unlock downstream tasks: when a task closes,
  consult .slaps/tasks/admin/edges.csv and each downstream issue's raw JSON
  relationships.blockedBy list; if all blockers are present under
  .slaps/tasks/admin/closed/, move the downstream prompt from blocked/ → open/.
- Watch .slaps/tasks/failed/ to trigger a remediation LLM prompt and enforce a
  maximum of 3 failures per task; on the 3rd failure, move to .slaps/tasks/dead/.
- Print a status report after taking actions and a final report when no open or
  blocked prompts remain and all workers are idle.

No external dependencies; uses polling.

Usage
  python3 tools/tasks/watch_tasks.py

Environment
  CODex CLI must be available on PATH as `codex`.
"""

from __future__ import annotations

import csv
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


BASE = Path('.slaps/tasks').resolve()
DIR_OPEN = BASE / 'open'
DIR_BLOCKED = BASE / 'blocked'
DIR_CLAIMED = BASE / 'claimed'
DIR_CLOSED = BASE / 'closed'
DIR_FAILED = BASE / 'failed'
DIR_DEAD = BASE / 'dead'
DIR_RAW = BASE / 'raw'
DIR_ADMIN = BASE / 'admin'
DIR_ADMIN_CLOSED = DIR_ADMIN / 'closed'
FILE_EDGES = DIR_ADMIN / 'edges.csv'
DIR_FAILURE_REASONS = BASE.parent / 'failures' / 'reasons'
DIR_ATTEMPTS = DIR_ADMIN / 'attempts'


ISSUE_NUM_RE = re.compile(r'(\d+)')


def _ensure_dirs() -> None:
    for d in [
        DIR_OPEN,
        DIR_BLOCKED,
        DIR_CLAIMED,
        DIR_CLOSED,
        DIR_FAILED,
        DIR_DEAD,
        DIR_RAW,
        DIR_ADMIN,
        DIR_ADMIN_CLOSED,
        DIR_FAILURE_REASONS,
        DIR_ATTEMPTS,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def extract_issue_number(path: Path) -> Optional[int]:
    m = ISSUE_NUM_RE.search(path.name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def append_text(path: Path, text: str) -> None:
    with path.open('a', encoding='utf-8') as f:
        f.write(text)


def safe_move(src: Path, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(str(src), str(dst))
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def list_sorted_files(d: Path) -> List[Path]:
    try:
        return sorted([p for p in d.iterdir() if p.is_file()])
    except FileNotFoundError:
        return []


def load_edges_map(csv_path: Path) -> Dict[int, Set[int]]:
    """
    Returns mapping: blocker_issue -> set(dependent_issue)
    Accepts a header row if present; otherwise treats first two columns as src,dst.
    """
    edges: Dict[int, Set[int]] = {}
    if not csv_path.exists():
        return edges
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header: Optional[List[str]] = None
        first_row: Optional[List[str]] = None
        try:
            first_row = next(reader)
        except StopIteration:
            return edges
        if first_row and any(k.lower() in {'from', 'to', 'src', 'dst', 'blocker', 'blocked'} for k in first_row):
            header = [c.strip().lower() for c in first_row]
        else:
            # treat as data row
            row = first_row
            if len(row) >= 2:
                try:
                    a = int(row[0])
                    b = int(row[1])
                    edges.setdefault(a, set()).add(b)
                except ValueError:
                    pass
        # process remaining rows
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            if row[0].lstrip().startswith('#'):
                continue
            try:
                if header:
                    cols = {header[i]: row[i].strip() for i in range(min(len(header), len(row)))}
                    # heuristics
                    a_str = cols.get('from') or cols.get('src') or cols.get('blocker') or cols.get('prereq')
                    b_str = cols.get('to') or cols.get('dst') or cols.get('blocked') or cols.get('dependent')
                    if a_str is None or b_str is None:
                        continue
                    a = int(a_str)
                    b = int(b_str)
                else:
                    a = int(row[0])
                    b = int(row[1])
                edges.setdefault(a, set()).add(b)
            except Exception:
                continue
    return edges


def get_blockers_from_raw(issue_num: int) -> Set[int]:
    raw = DIR_RAW / f'issue-{issue_num}.json'
    if not raw.exists():
        return set()
    try:
        import json

        data = json.loads(raw.read_text(encoding='utf-8'))
        rel = data.get('relationships') or {}
        blocked_by = rel.get('blockedBy') or rel.get('blockedby') or []
        out: Set[int] = set()
        for v in blocked_by:
            try:
                out.add(int(v))
            except Exception:
                pass
        return out
    except Exception:
        return set()


def blockers_all_closed(blockers: Set[int]) -> bool:
    # Closed markers are files under admin/closed named like "<issue>.*" or "<issue>"
    for b in blockers:
        # accept any file starting with the issue number
        pattern = f"{b}"
        found = any(p.name.startswith(pattern) for p in list_sorted_files(DIR_ADMIN_CLOSED))
        if not found:
            return False
    return True


def print_report(workers: List['Worker']) -> None:
    # Worker reports
    for w in workers:
        status = 'busy' if w.is_busy() else 'idle'
        extra = f" working on {w.current_issue}" if w.is_busy() and w.current_issue else ''
        print(f"worker {w.worker_id} is {status}{extra}")
    # Counts
    failures = len(list_sorted_files(DIR_FAILED))
    completed = len(list_sorted_files(DIR_CLOSED))
    blocked = len(list_sorted_files(DIR_BLOCKED))
    dead = len(list_sorted_files(DIR_DEAD))
    print("FAILURES")
    print(f"{failures} failures")
    print("COMPLETED TASKS")
    print(f"{completed} completed tasks")
    print("BLOCKED TASKS")
    print(f"{blocked} blocked tasks")
    print("DEAD LETTER QUEUE")
    print(f"{dead} dead tasks")
    sys.stdout.flush()


def final_report_and_exit(workers: List['Worker']) -> None:
    print("All work complete. Final report:")
    print_report(workers)
    sys.stdout.flush()
    os._exit(0)


def increment_attempt(issue_num: int) -> int:
    DIR_ATTEMPTS.mkdir(parents=True, exist_ok=True)
    f = DIR_ATTEMPTS / f"{issue_num}.count"
    n = 0
    if f.exists():
        try:
            n = int(f.read_text().strip() or '0')
        except Exception:
            n = 0
    n += 1
    f.write_text(str(n))
    return n


def invoke_codex_exec(prompt: str) -> Tuple[int, str, str]:
    # Runs: codex exec "{prompt}"
    # Use argv form to avoid shell quoting issues.
    try:
        proc = subprocess.run(
            ["codex", "exec", prompt],
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as e:
        return 127, "", f"codex not found: {e}"
    except Exception as e:
        return 1, "", f"exception invoking codex: {e}"


@dataclass
class Worker:
    worker_id: int
    stop_event: threading.Event
    lock: threading.Lock = field(default_factory=threading.Lock)
    current_issue: Optional[int] = None
    thread: Optional[threading.Thread] = None

    def is_busy(self) -> bool:
        return self.current_issue is not None

    def run(self) -> None:
        # Ensure per-worker claimed directory exists
        claimed_dir = DIR_CLAIMED / str(self.worker_id)
        claimed_dir.mkdir(parents=True, exist_ok=True)
        while not self.stop_event.is_set():
            # Step 1: look for a file in open/, claim it via atomic rename
            # Only consider .txt prompts.
            open_files = [p for p in list_sorted_files(DIR_OPEN) if p.suffix == '.txt']
            claimed_file: Optional[Path] = None
            issue_num: Optional[int] = None
            for f in open_files:
                dest = claimed_dir / f.name
                if safe_move(f, dest):
                    claimed_file = dest
                    issue_num = extract_issue_number(dest)
                    break
            if not claimed_file:
                # no work; sleep 25s
                time.sleep(25)
                continue
            # Step 2: invoke LLM
            with self.lock:
                self.current_issue = issue_num
            try:
                # Prepend hard guardrails to the prompt so workers are warned.
                guardrails = (
                    "POLICY (READ CAREFULLY):\n"
                    "- DO NOT PERFORM GIT OPERATIONS. Do not run git/gh, do not commit, branch, rebase, or push.\n"
                    "- You are working in a shared branch alongside other LLMs. Expect transient conflicts; work around them, coordinate via code comments if needed, and avoid destructive actions.\n"
                    "- Use only containerized build/test targets (make both/test-both/lint) and file edits.\n"
                    "- Any git operation is forbidden.\n\n"
                )
                prompt = read_text(claimed_file)
                effective_prompt = guardrails + prompt
                rc, out, err = invoke_codex_exec(effective_prompt)
                if rc != 0:
                    # append failure diagnostics, then move to failed/
                    failure_footer = (
                        "\n\n## FAILURE:\n\n"
                        f"STDOUT: {out}\n"
                        f"STDERR: {err}\n"
                    )
                    append_text(claimed_file, failure_footer)
                    failed_path = DIR_FAILED / claimed_file.name
                    safe_move(claimed_file, failed_path)
                else:
                    closed_path = DIR_CLOSED / claimed_file.name
                    safe_move(claimed_file, closed_path)
            finally:
                with self.lock:
                    self.current_issue = None


class Watcher:
    def __init__(self) -> None:
        _ensure_dirs()
        self.stop_event = threading.Event()
        self.workers: List[Worker] = []
        self.closed_seen: Set[str] = set(p.name for p in list_sorted_files(DIR_CLOSED))
        self.failed_seen: Set[str] = set(p.name for p in list_sorted_files(DIR_FAILED))
        self.edges_map = load_edges_map(FILE_EDGES)
        self.lock = threading.Lock()

    def start_workers(self) -> None:
        n = os.cpu_count() or 1
        for i in range(1, n + 1):
            w = Worker(worker_id=i, stop_event=self.stop_event)
            t = threading.Thread(target=w.run, name=f"worker-{i}", daemon=True)
            w.thread = t
            self.workers.append(w)
            t.start()

    def all_idle(self) -> bool:
        return all(not w.is_busy() for w in self.workers)

    def _handle_closed_file(self, path: Path) -> None:
        # Called when a new file appears in closed/
        issue_num = extract_issue_number(path)
        if issue_num is None:
            return
        # Write a closed marker under admin/closed for dependency checks
        try:
            DIR_ADMIN_CLOSED.mkdir(parents=True, exist_ok=True)
            marker = DIR_ADMIN_CLOSED / f"{issue_num}.closed"
            if not marker.exists():
                marker.write_text(str(int(time.time())), encoding='utf-8')
        except Exception:
            pass
        # Refresh edges map in case it changed
        self.edges_map = load_edges_map(FILE_EDGES)
        downstream = self.edges_map.get(issue_num, set())
        actions = 0
        for dep in sorted(downstream):
            blockers = get_blockers_from_raw(dep)
            if blockers and blockers_all_closed(blockers):
                blocked_prompt = DIR_BLOCKED / f"{dep}.txt"
                if blocked_prompt.exists():
                    dest = DIR_OPEN / blocked_prompt.name
                    if safe_move(blocked_prompt, dest):
                        actions += 1
        # Print a report whenever we took any action (marker/unlocks)
        print_report(self.workers)

    def _handle_failed_file(self, path: Path) -> None:
        issue_num = extract_issue_number(path)
        if issue_num is None:
            return
        # Increment attempts and dead-letter if >= 3
        attempts = increment_attempt(issue_num)
        if attempts >= 3:
            dead_path = DIR_DEAD / path.name
            safe_move(path, dead_path)
            # Optionally append a note in reasons file
            reasons = DIR_FAILURE_REASONS / f"{issue_num}.txt"
            append_text(
                reasons,
                f"\n\n## Attempt number {attempts}\n\nFailed because exceeded max attempts.\n\nGoing to try no further; moving to dead.\n\n",
            )
            print_report(self.workers)
            return
        # Otherwise, invoke remediation LLM
        guardrails = (
            "POLICY (READ CAREFULLY):\n"
            "- DO NOT PERFORM GIT OPERATIONS. Do not run git/gh, do not commit, branch, rebase, or push.\n"
            "- You are working in a shared branch alongside other LLMs. Expect transient conflicts; work around them, coordinate via code comments if needed, and avoid destructive actions.\n"
            "- Use only containerized build/test targets (make both/test-both/lint) and file edits.\n"
            "- Any git operation is forbidden.\n\n"
        )
        remediation_prompt = guardrails + (
            "Another LLM was working on this issue {issue} and failed. "
            "Please read the original prompt used and the stdout/stderr from the previous LLM's attempt "
            "by reading this file {filepath}. Next, examine the state of the repository and determine what went "
            "wrong and what could have been done differently. Are the instructions incorrect? Is there some other issue? "
            "Either way, reason it out, then APPEND your rational to log to .slaps/failures/reasons/{issue}.txt like so:\n\n"
            "## Attempt number {attempt}\n\nFailed because {{reason}}\n\nGoing to try {{new approach}}\n\n"
            "Then, write a new prompt for the task and put it in the .slaps/tasks/open/ directory."
        ).format(issue=issue_num, filepath=str(path), attempt=attempts)
        rc, out, err = invoke_codex_exec(remediation_prompt)
        # We do not enforce output; the remediation agent is expected to append and enqueue a new prompt.
        print_report(self.workers)

    def maybe_finish(self) -> None:
        if not list_sorted_files(DIR_OPEN) and not list_sorted_files(DIR_BLOCKED) and self.all_idle():
            final_report_and_exit(self.workers)

    def run(self) -> None:
        self.start_workers()
        print("watcher started; monitoring .slaps/tasks/")
        sys.stdout.flush()

        def _sigint(signum, frame):
            print("received signal, shutting down...")
            self.stop_event.set()
            time.sleep(0.5)
            final_report_and_exit(self.workers)

        signal.signal(signal.SIGINT, _sigint)
        signal.signal(signal.SIGTERM, _sigint)

        while True:
            # detect new closed files
            closed_now = set(p.name for p in list_sorted_files(DIR_CLOSED))
            new_closed = [DIR_CLOSED / n for n in sorted(closed_now - self.closed_seen)]
            self.closed_seen = closed_now
            for p in new_closed:
                self._handle_closed_file(p)

            # detect new failed files
            failed_now = set(p.name for p in list_sorted_files(DIR_FAILED))
            new_failed = [DIR_FAILED / n for n in sorted(failed_now - self.failed_seen)]
            self.failed_seen = failed_now
            for p in new_failed:
                self._handle_failed_file(p)

            self.maybe_finish()
            time.sleep(2)


def main() -> int:
    try:
        Watcher().run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
