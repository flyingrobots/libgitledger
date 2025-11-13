from __future__ import annotations

import json
import re
from dataclasses import dataclass
import time
from pathlib import Path
from typing import List, Optional, Set

from .ports import FilePort, LLMPort, Paths, ReporterPort, SleepPort
from .logjson import JsonlLogger


POLICY_GUARDRAILS = (
    "POLICY (READ CAREFULLY):\n"
    "- DO NOT PERFORM GIT OPERATIONS. Do not run git/gh, do not commit, branch, rebase, or push.\n"
    "- You are working in a shared branch alongside other LLMs. Expect transient conflicts; work around them, coordinate via code comments if needed, and avoid destructive actions.\n"
    "- Use only containerized build/test targets (make both/test-both/lint) and file edits.\n"
    "- Any git operation is forbidden.\n\n"
)


ISSUE_NUM_RE = re.compile(r"(\d+)")


def extract_issue_number(path: Path) -> Optional[int]:
    m = ISSUE_NUM_RE.search(path.name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def make_paths(base_root: Path, wave: Optional[int] = None) -> Paths:
    base_root = base_root.resolve()
    qbase = base_root / (str(wave) if wave is not None else '')
    qbase = qbase if wave is not None else base_root
    return Paths(
        base=qbase,
        open=qbase / "open",
        blocked=qbase / "blocked",
        claimed=qbase / "claimed",
        closed=qbase / "closed",
        failed=qbase / "failed",
        dead=qbase / "dead",
        raw=base_root / "raw",
        admin=base_root / "admin",
        admin_closed=(base_root / "admin" / "closed"),
        edges_csv=base_root / "admin" / "edges.csv",
        failure_reasons=(base_root.parent / "failures" / "reasons"),
        attempts=base_root / "admin" / "attempts",
    )


def default_paths(base: Path) -> Paths:
    return make_paths(base_root=base, wave=None)


def ensure_dirs(fs: FilePort, p: Paths) -> None:
    for d in [
        p.open,
        p.blocked,
        p.claimed,
        p.closed,
        p.failed,
        p.dead,
        p.raw,
        p.admin,
        p.admin_closed,
        p.failure_reasons,
        p.attempts,
    ]:
        fs.mkdirs(d)


def list_sorted_txt(fs: FilePort, d: Path) -> List[Path]:
    return [f for f in fs.list_files(d) if f.suffix == ".txt"]


def load_edges_map(fs: FilePort, edges_csv: Path) -> dict[int, set[int]]:
    import csv

    edges: dict[int, set[int]] = {}
    if not fs.exists(edges_csv):
        return edges
    with edges_csv.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header: Optional[list[str]] = None
        try:
            first = next(reader)
        except StopIteration:
            return edges
        if first and any(k.lower() in {"from", "to", "src", "dst", "blocker", "blocked"} for k in first):
            header = [c.strip().lower() for c in first]
        else:
            row = first
            if len(row) >= 2:
                try:
                    a = int(row[0])
                    b = int(row[1])
                    edges.setdefault(a, set()).add(b)
                except ValueError:
                    pass
        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            try:
                if header:
                    cols = {header[i]: row[i].strip() for i in range(min(len(header), len(row)))}
                    a_str = cols.get("from") or cols.get("src") or cols.get("blocker") or cols.get("prereq")
                    b_str = cols.get("to") or cols.get("dst") or cols.get("blocked") or cols.get("dependent")
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


def get_blockers_from_raw(fs: FilePort, p: Paths, issue: int) -> Set[int]:
    raw = p.raw / f"issue-{issue}.json"
    if not fs.exists(raw):
        return set()
    try:
        data = json.loads(raw.read_text(encoding="utf-8"))
        rel = data.get("relationships") or {}
        blocked_by = rel.get("blockedBy") or rel.get("blockedby") or []
        out: Set[int] = set()
        for v in blocked_by:
            try:
                out.add(int(v))
            except Exception:
                pass
        return out
    except Exception:
        return set()


def blockers_all_closed(fs: FilePort, p: Paths, blockers: Set[int]) -> bool:
    for b in blockers:
        marker_prefix = f"{b}"
        if not any(x.name.startswith(marker_prefix) for x in fs.list_files(p.admin_closed)):
            return False
    return True


class Worker:
    def __init__(self, worker_id: int, fs: FilePort, llm: LLMPort, paths: Paths, reporter: ReporterPort | None = None, allowed_issues: Optional[Set[int]] = None, logger: Optional[JsonlLogger] = None):
        self.worker_id = worker_id
        self.fs = fs
        self.llm = llm
        self.p = paths
        self.reporter = reporter
        self.logger = logger
        self.allowed_issues = allowed_issues
        self.current_issue: Optional[int] = None
        self.started_at: Optional[float] = None
        self.estimate_sec: Optional[int] = None
        self.timeout_sec: Optional[int] = None
        # ensure claimed dir exists
        self.fs.mkdirs(self.p.claimed / str(self.worker_id))

    def run_once(self) -> bool:
        # Enforce at most one claimed task per worker.
        claimed_dir = self.p.claimed / str(self.worker_id)
        claimed_files = list_sorted_txt(self.fs, claimed_dir)
        if len(claimed_files) > 1:
            # Corruption safety: move extras to failed with a diagnostic footer.
            keep = claimed_files[0]
            for extra in claimed_files[1:]:
                try:
                    self.fs.append_text(
                        extra,
                        "\n\n## CLAIM CORRUPTION:\n\nMultiple claimed tasks detected; moving this extra file to failed.\n",
                    )
                except Exception:
                    pass
                self.fs.move_atomic(extra, self.p.failed / extra.name)
                if self.reporter:
                    num = extract_issue_number(extra)
                    self.reporter.report(f"[SYSTEM] Moved task #{num} to failed")
                if getattr(self, 'logger', None):
                    self.logger.emit("move", task=extract_issue_number(extra), from_dir="claimed", to_dir="failed", worker=self.worker_id)
            claimed_files = [keep]

        # If a claimed file exists, process it before claiming new work.
        if claimed_files:
            dest = claimed_files[0]
            self.current_issue = extract_issue_number(dest)
            prompt = self.fs.read_text(dest)
            self.started_at = time.time()
            self._ensure_estimate_for(dest, prompt)
            rc, out, err = self.llm.exec(POLICY_GUARDRAILS + prompt, timeout=self.timeout_sec or None)
            if rc != 0:
                footer = ("\n\n## FAILURE:\n\n" f"STDOUT: {out}\n" f"STDERR: {err}\n")
                try:
                    self.fs.append_text(dest, footer)
                except Exception:
                    pass
                self.fs.move_atomic(dest, self.p.failed / dest.name)
                if self.reporter:
                    num = extract_issue_number(dest)
                    self.reporter.report(f"[WORKER:{self.worker_id:03d}] LLM error task #{num}: {err.strip()[:200]}; exit code {rc}")
                    self.reporter.report(f"[SYSTEM] Moved task #{num} to failed")
                if getattr(self, 'logger', None):
                    self.logger.emit("worker_result", outcome="error", task=extract_issue_number(dest), worker=self.worker_id, rc=rc)
                    self.logger.emit("move", task=extract_issue_number(dest), from_dir="claimed", to_dir="failed", worker=self.worker_id)
            else:
                self.fs.move_atomic(dest, self.p.closed / dest.name)
                if self.reporter:
                    num = extract_issue_number(dest)
                    self.reporter.report(f"[WORKER:{self.worker_id:03d}] LLM success task #{num}")
                    self.reporter.report(f"[SYSTEM] Moved task #{num} to closed")
                if getattr(self, 'logger', None):
                    self.logger.emit("worker_result", outcome="success", task=extract_issue_number(dest), worker=self.worker_id)
                    self.logger.emit("move", task=extract_issue_number(dest), from_dir="claimed", to_dir="closed", worker=self.worker_id)
            self.current_issue = None
            self.started_at = None
            self.estimate_sec = None
            self.timeout_sec = None
            return True

        # Otherwise, try to claim exactly one task from open.
        for f in list_sorted_txt(self.fs, self.p.open):
            # Respect wave/allowed filter
            f_issue = extract_issue_number(f)
            if self.allowed_issues is not None and (f_issue is None or f_issue not in self.allowed_issues):
                continue
            dest = claimed_dir / f.name
            if self.fs.move_atomic(f, dest):
                self.current_issue = extract_issue_number(dest)
                if self.reporter:
                    self.reporter.report(f"[SYSTEM] Moved task #{self.current_issue} to claimed")
                if getattr(self, 'logger', None):
                    self.logger.emit("move", task=self.current_issue, from_dir="open", to_dir="claimed", worker=self.worker_id)
                prompt = self.fs.read_text(dest)
                self.started_at = time.time()
                self._ensure_estimate_for(dest, prompt)
                rc, out, err = self.llm.exec(POLICY_GUARDRAILS + prompt, timeout=self.timeout_sec or None)
                if rc != 0:
                    footer = ("\n\n## FAILURE:\n\n" f"STDOUT: {out}\n" f"STDERR: {err}\n")
                    try:
                        self.fs.append_text(dest, footer)
                    except Exception:
                        pass
                    self.fs.move_atomic(dest, self.p.failed / dest.name)
                    if self.reporter:
                        num = extract_issue_number(dest)
                        self.reporter.report(f"[WORKER:{self.worker_id:03d}] LLM error task #{num}: {err.strip()[:200]}; exit code {rc}")
                        self.reporter.report(f"[SYSTEM] Moved task #{num} to failed")
                    if getattr(self, 'logger', None):
                        self.logger.emit("worker_result", outcome="error", task=extract_issue_number(dest), worker=self.worker_id, rc=rc)
                        self.logger.emit("move", task=extract_issue_number(dest), from_dir="claimed", to_dir="failed", worker=self.worker_id)
                else:
                    self.fs.move_atomic(dest, self.p.closed / dest.name)
                    if self.reporter:
                        num = extract_issue_number(dest)
                        self.reporter.report(f"[WORKER:{self.worker_id:03d}] LLM success task #{num}")
                        self.reporter.report(f"[SYSTEM] Moved task #{num} to closed")
                    if getattr(self, 'logger', None):
                        self.logger.emit("worker_result", outcome="success", task=extract_issue_number(dest), worker=self.worker_id)
                        self.logger.emit("move", task=extract_issue_number(dest), from_dir="claimed", to_dir="closed", worker=self.worker_id)
                self.current_issue = None
                self.started_at = None
                self.estimate_sec = None
                self.timeout_sec = None
                return True
        return False

    def _ensure_estimate_for(self, task_path: Path, prompt: str) -> None:
        if self.estimate_sec is not None and self.timeout_sec is not None:
            return
        issue = extract_issue_number(task_path) or 0
        est_dir = self.p.admin / "estimates"
        self.fs.mkdirs(est_dir)
        est_file = est_dir / f"{issue}.json"
        # Determine current attempt number (attempts file counts failures; current attempt = failures + 1)
        attempts_path = self.p.attempts / f"{issue}.count"
        current_attempt = 1
        if self.fs.exists(attempts_path):
            try:
                n = int(self.fs.read_text(attempts_path).strip() or "0")
                current_attempt = max(1, n + 1)
            except Exception:
                current_attempt = 1
        # Try cached
        if self.fs.exists(est_file):
            try:
                data = json.loads(self.fs.read_text(est_file))
                self.estimate_sec = int(data.get("estimate_sec", 0)) or None
                self.timeout_sec = int(data.get("timeout_sec", 0)) or None
                cached_attempt = int(data.get("attempt", 0)) if isinstance(data, dict) else 0
                if cached_attempt == current_attempt and self.estimate_sec and self.timeout_sec:
                    if self.reporter:
                        self.reporter.report(f"[SYSTEM] Estimated time for task #{issue}: {int(self.estimate_sec/60)}m; Timeout: {int(self.timeout_sec/60)}m (cached)")
                    return
            except Exception:
                pass
        # Ask LLM for a fast estimate (minutes), best-effort
        est_prompt = (
            POLICY_GUARDRAILS
            + "Estimate how long the following task will take in minutes. Output only a single integer (minutes). Task prompt follows:\n\n"
            + prompt
        )
        rc, out, _ = self.llm.exec(est_prompt, timeout=60)
        minutes = None
        if rc == 0:
            try:
                minutes = int("".join(ch for ch in out if ch.isdigit()) or "0")
            except Exception:
                minutes = None
        if not minutes or minutes <= 0:
            minutes = 20
        self.estimate_sec = int(minutes * 60)
        self.timeout_sec = max(600, min(self.estimate_sec * 2, 7200))
        if self.reporter:
            suffix = " (re-estimated)" if self.fs.exists(est_file) else ""
            self.reporter.report(f"[SYSTEM] Estimated time for task #{issue}: {minutes}m; Timeout: {int(self.timeout_sec/60)}m{suffix}")
        try:
            self.fs.write_text(est_file, json.dumps({
                "attempt": current_attempt,
                "estimate_sec": self.estimate_sec,
                "timeout_sec": self.timeout_sec
            }))
        except Exception:
            pass


class Watcher:
    def __init__(self, fs: FilePort, llm: LLMPort, reporter: ReporterPort, paths: Paths, allowed_issues: Optional[Set[int]] = None, logger: Optional[JsonlLogger] = None):
        self.fs = fs
        self.llm = llm
        self.reporter = reporter
        self.p = paths
        self.allowed_issues = allowed_issues
        self.logger = logger
        ensure_dirs(self.fs, self.p)
        self.closed_seen = {x.name for x in self.fs.list_files(self.p.closed)}
        self.failed_seen = {x.name for x in self.fs.list_files(self.p.failed)}
        self.edges = load_edges_map(self.fs, self.p.edges_csv)

    def print_report(self, workers: List[Worker]) -> None:
        lines: List[str] = []
        for w in workers:
            status = "busy" if w.current_issue is not None else "idle"
            extra = ""
            if w.current_issue:
                extra = f" working on {w.current_issue}"
                if getattr(w, "started_at", None):
                    now = time.time()
                    elapsed = int(now - (w.started_at or now))
                    est = getattr(w, "estimate_sec", None)
                    to_sec = getattr(w, "timeout_sec", None)
                    rem = None
                    if to_sec:
                        rem = max(0, int(to_sec - elapsed))
                    def fmt(s: Optional[int]) -> str:
                        if s is None:
                            return "?"
                        m, s2 = divmod(int(s), 60)
                        return f"{m}m{s2:02d}s"
                    extra += f" [elapsed {fmt(elapsed)}"
                    if est:
                        extra += f" / est {fmt(est)}"
                    if rem is not None:
                        extra += f" / timeout in {fmt(rem)}"
                    extra += "]"
            lines.append(f"worker {w.worker_id} is {status}{extra}")
        failures = len(self.fs.list_files(self.p.failed))
        completed = len(self.fs.list_files(self.p.closed))
        blocked = len(self.fs.list_files(self.p.blocked))
        dead = len(self.fs.list_files(self.p.dead))
        # Progress (based on raw issues; restrict to allowed_issues if provided)
        all_raw = [p for p in self.fs.list_files(self.p.raw) if p.name.startswith("issue-") and p.suffix == ".json"]
        if self.allowed_issues is not None:
            total = len([p for p in all_raw if extract_issue_number(p) in self.allowed_issues])
            progressed = len([p for p in self.fs.list_files(self.p.closed) if extract_issue_number(p) in self.allowed_issues]) \
                        + len([p for p in self.fs.list_files(self.p.dead) if extract_issue_number(p) in self.allowed_issues])
        else:
            total = len(all_raw)
            progressed = completed + dead
        pct = int((progressed / total) * 100) if total else 0
        bar_width = 60
        filled = int((pct / 100) * bar_width)
        bar = ("█" * filled) + ("░" * (bar_width - filled))
        ticks = "|     |     |     |     |     |     |     |     |     |     |"
        ruler = "0••••10••••20••••30••••40••••50••••60••••70••••80••••90•••100"
        lines += [
            "",
            f"PROGRESS: {pct}% [{progressed} of {total}]",
            bar,
            ticks,
            ruler,
            "",
        ]
        lines += [
            "FAILURES",
            f"{failures} failures",
            "COMPLETED TASKS",
            f"{completed} completed tasks",
            "BLOCKED TASKS",
            f"{blocked} blocked tasks",
            "DEAD LETTER QUEUE",
            f"{dead} dead tasks",
        ]
        self.reporter.report("\n".join(lines))

    def _write_closed_marker(self, issue: int) -> None:
        try:
            self.fs.mkdirs(self.p.admin_closed)
            marker = self.p.admin_closed / f"{issue}.closed"
            if not self.fs.exists(marker):
                self.fs.write_text(marker, "1")
        except Exception:
            pass

    def _unlock_downstream(self, issue: int) -> None:
        self.edges = load_edges_map(self.fs, self.p.edges_csv)
        downstream = sorted(self.edges.get(issue, set()))
        for dep in downstream:
            blockers = get_blockers_from_raw(self.fs, self.p, dep)
            if blockers and blockers_all_closed(self.fs, self.p, blockers):
                blocked_prompt = self.p.blocked / f"{dep}.txt"
                if self.fs.exists(blocked_prompt):
                    dest = self.p.open / blocked_prompt.name
                    # Avoid clobbering if a newer open prompt already exists (e.g., remediation created it).
                    if not self.fs.exists(dest):
                        if self.allowed_issues is not None and dep not in self.allowed_issues:
                            continue
                        self.fs.move_atomic(blocked_prompt, dest)
                        if self.reporter:
                            self.reporter.report(f"[SYSTEM] Moved task #{dep} to open")
                        if getattr(self, 'logger', None):
                            self.logger.emit("move", task=dep, from_dir="blocked", to_dir="open", worker=None)

    def handle_closed(self, file: Path, workers: List[Worker]) -> None:
        issue = extract_issue_number(file)
        if issue is None:
            return
        self._write_closed_marker(issue)
        self._unlock_downstream(issue)
        self.print_report(workers)

    def startup_sweep(self, workers: List[Worker]) -> None:
        """On startup, unlock any now-unblocked tasks based on existing closed files or markers."""
        # Collect issues from closed files and admin markers
        issues: set[int] = set()
        for f in self.fs.list_files(self.p.closed):
            num = extract_issue_number(f)
            if num is not None:
                issues.add(num)
        for m in self.fs.list_files(self.p.admin_closed):
            num = extract_issue_number(m)
            if num is not None:
                issues.add(num)
        for num in sorted(issues):
            # Ensure marker exists then unlock
            self._write_closed_marker(num)
            self._unlock_downstream(num)
        if issues:
            self.print_report(workers)

    def _attempt_path(self, issue: int) -> Path:
        return self.p.attempts / f"{issue}.count"

    def _inc_attempt(self, issue: int) -> int:
        self.fs.mkdirs(self.p.attempts)
        f = self._attempt_path(issue)
        n = 0
        if self.fs.exists(f):
            try:
                n = int(self.fs.read_text(f).strip() or "0")
            except Exception:
                n = 0
        n += 1
        self.fs.write_text(f, str(n))
        return n

    def handle_failed(self, file: Path, workers: List[Worker]) -> None:
        issue = extract_issue_number(file)
        if issue is None:
            return
        attempts = self._inc_attempt(issue)
        if attempts >= 3:
            # Append a terminal footer and then move to dead/
            try:
                self.fs.append_text(
                    file,
                    (
                        "\n\n## DEAD LETTER:\n\n"
                        f"Max attempts reached on attempt {attempts}.\n"
                        "Moving this task to the dead letter queue.\n"
                    ),
                )
            except Exception:
                pass
            self.fs.move_atomic(file, self.p.dead / file.name)
            reasons = self.p.failure_reasons / f"{issue}.txt"
            self.fs.append_text(
                reasons,
                (
                    f"\n\n## Attempt number {attempts}\n\n"
                    "Failed because exceeded max attempts.\n\n"
                    "Going to try no further; moving to dead.\n\n"
                ),
            )
            self.print_report(workers)
            return
        # remediation prompt
        next_attempt = attempts + 1
        remediation = (
            POLICY_GUARDRAILS
            + (
                "Another LLM was working on this issue {issue} and failed. "
                "Read the entire failed task file at: {filepath}. It contains the ORIGINAL PROMPT followed by \n"
                "'## FAILURE' with STDOUT/STDERR from the last attempt. Identify the approach the previous agent took.\n\n"
                "Write a concise analysis and APPEND it to .slaps/failures/reasons/{issue}.txt in this exact format:\n\n"
                "## Attempt number {attempt}\n\n"
                "Failed because <one-paragraph reason>.\n\n"
                "Previously tried: <one-sentence summary>.\n\n"
                "Going to try: <one-sentence new approach>.\n\n"
                "Now generate a NEW PROMPT for the next attempt and write it to .slaps/tasks/open/{issue}.txt.\n"
                "At the top of the prompt, include a line: 'Attempt {next_attempt}: Tried <X>, now trying <Y> because <why>'.\n"
                "Keep the rest of the prompt self-contained and compliant with repo rules and guardrails."
            ).format(issue=issue, filepath=str(file), attempt=attempts, next_attempt=next_attempt)
        )
        # Log retry with truncated prompt
        try:
            trunc = remediation.replace("\n", " ")[:50]
            self.reporter.report(f"[SYSTEM] Retry #{issue} with prompt: {trunc}")
            if getattr(self, 'logger', None):
                self.logger.emit("retry", task=issue, trunc_prompt=trunc)
        except Exception:
            pass
        self.llm.exec(remediation)
        self.print_report(workers)
