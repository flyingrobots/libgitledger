from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

from .ports import FilePort, LLMPort, Paths, ReporterPort, SleepPort


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


def default_paths(base: Path) -> Paths:
    base = base.resolve()
    return Paths(
        base=base,
        open=base / "open",
        blocked=base / "blocked",
        claimed=base / "claimed",
        closed=base / "closed",
        failed=base / "failed",
        dead=base / "dead",
        raw=base / "raw",
        admin=base / "admin",
        admin_closed=base / "admin" / "closed",
        edges_csv=base / "admin" / "edges.csv",
        failure_reasons=base.parent / "failures" / "reasons",
        attempts=base / "admin" / "attempts",
    )


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
    def __init__(self, worker_id: int, fs: FilePort, llm: LLMPort, paths: Paths):
        self.worker_id = worker_id
        self.fs = fs
        self.llm = llm
        self.p = paths
        self.current_issue: Optional[int] = None
        # ensure claimed dir exists
        self.fs.mkdirs(self.p.claimed / str(self.worker_id))

    def run_once(self) -> bool:
        # Try claim one task
        claimed_dir = self.p.claimed / str(self.worker_id)
        for f in list_sorted_txt(self.fs, self.p.open):
            dest = claimed_dir / f.name
            if self.fs.move_atomic(f, dest):
                self.current_issue = extract_issue_number(dest)
                # Execute
                prompt = self.fs.read_text(dest)
                rc, out, err = self.llm.exec(POLICY_GUARDRAILS + prompt)
                if rc != 0:
                    # Append failure diagnostics; tolerate append errors and still route to failed/
                    footer = ("\n\n## FAILURE:\n\n" f"STDOUT: {out}\n" f"STDERR: {err}\n")
                    try:
                        self.fs.append_text(dest, footer)
                    except Exception:
                        pass
                    self.fs.move_atomic(dest, self.p.failed / dest.name)
                else:
                    self.fs.move_atomic(dest, self.p.closed / dest.name)
                self.current_issue = None
                return True
        return False


class Watcher:
    def __init__(self, fs: FilePort, llm: LLMPort, reporter: ReporterPort, paths: Paths):
        self.fs = fs
        self.llm = llm
        self.reporter = reporter
        self.p = paths
        ensure_dirs(self.fs, self.p)
        self.closed_seen = {x.name for x in self.fs.list_files(self.p.closed)}
        self.failed_seen = {x.name for x in self.fs.list_files(self.p.failed)}
        self.edges = load_edges_map(self.fs, self.p.edges_csv)

    def print_report(self, workers: List[Worker]) -> None:
        lines: List[str] = []
        for w in workers:
            status = "busy" if w.current_issue is not None else "idle"
            extra = f" working on {w.current_issue}" if w.current_issue else ""
            lines.append(f"worker {w.worker_id} is {status}{extra}")
        failures = len(self.fs.list_files(self.p.failed))
        completed = len(self.fs.list_files(self.p.closed))
        blocked = len(self.fs.list_files(self.p.blocked))
        dead = len(self.fs.list_files(self.p.dead))
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

    def handle_closed(self, file: Path, workers: List[Worker]) -> None:
        issue = extract_issue_number(file)
        if issue is None:
            return
        self._write_closed_marker(issue)
        self.edges = load_edges_map(self.fs, self.p.edges_csv)
        downstream = sorted(self.edges.get(issue, set()))
        for dep in downstream:
            blockers = get_blockers_from_raw(self.fs, self.p, dep)
            if blockers and blockers_all_closed(self.fs, self.p, blockers):
                blocked_prompt = self.p.blocked / f"{dep}.txt"
                if self.fs.exists(blocked_prompt):
                    self.fs.move_atomic(blocked_prompt, self.p.open / blocked_prompt.name)
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
        self.llm.exec(remediation)
        self.print_report(workers)
