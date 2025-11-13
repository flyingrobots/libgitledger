from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from .ports import FilePort, ReporterPort, GHPort, GHProject, GHField
from .adapters import LocalFS
from .logjson import JsonlLogger
from .domain import extract_issue_number, get_blockers_from_raw


STATE_VALUES = ["open", "closed", "claimed", "failure", "dead", "blocked"]


class GHState:
    def __init__(self, project: GHProject, fields: Dict[str, GHField]):
        self.project = project
        self.fields = fields

    def field(self, name: str) -> GHField:
        return self.fields[name]


class GHWatcher:
    """Watcher that uses GitHub project fields for state and local FS locks for claims."""

    def __init__(self, gh: GHPort, fs: FilePort, reporter: ReporterPort, logger: Optional[JsonlLogger], raw_dir: Path, lock_dir: Path, project_title: str):
        self.gh = gh
        self.fs = fs
        self.r = reporter
        self.log = logger
        self.raw_dir = raw_dir
        self.lock_dir = lock_dir
        self.project_title = project_title
        self.state: Optional[GHState] = None

    def _emit(self, event: str, **kw) -> None:
        if self.log:
            self.log.emit(event, **kw)

    def preflight(self, wave: int) -> None:
        project = self.gh.ensure_project(self.project_title)
        fields = self.gh.ensure_fields(project, STATE_VALUES)
        self.state = GHState(project, fields)
        # Ensure labels
        self.gh.ensure_labels(["slaps-wip", "slaps-did-it", "slaps-failed"])
        # Ensure lock dir exists
        self.fs.mkdirs(self.lock_dir)
        self.r.report(f"[SYSTEM] GH project ready: {project.title} (#{project.number})")
        self._emit("gh_preflight", project=project.title, number=project.number)

    def ensure_cached_issue(self, issue: int, evict: bool = False) -> None:
        raw_file = self.raw_dir / f"issue-{issue}.json"
        if evict and raw_file.exists():
            try:
                raw_file.unlink()
            except Exception:
                pass
        if raw_file.exists():
            return
        try:
            data = self.gh.fetch_issue_json(issue)
            # Write as a minimal cache; relationships may already exist from prior import
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            raw_file.write_text(json.dumps(data), encoding='utf-8')
        except Exception:
            pass

    def _list_wave_issues_from_gh(self, wave: int) -> Set[int]:
        try:
            nums = self.gh.list_issues_for_wave(wave)
            return set(int(n) for n in nums)
        except Exception:
            return set()

    def initialize_items(self, wave: int) -> None:
        assert self.state is not None
        project = self.state.project
        f_state = self.state.field("slaps-state")
        f_wave = self.state.field("slaps-wave")
        f_attempt = self.state.field("slaps-attempt-count")

        for issue in sorted(self._list_wave_issues_from_gh(wave)):
            item_id = self.gh.ensure_issue_in_project(project, issue)
            # Set initial fields: wave, attempt=0, state=blocked
            self.gh.set_item_number_field(project, item_id, f_wave, wave)
            self.gh.set_item_number_field(project, item_id, f_attempt, 0)
            self.gh.set_item_single_select(project, item_id, f_state, "blocked")
            self._emit("init_item", issue=issue, item_id=item_id, wave=wave)
        self.r.report(f"[SYSTEM] Initialized wave {wave} issues in project")

    def _get_field_value(self, fields_map: Dict[str, str], name: str) -> Optional[str]:
        return fields_map.get(name)

    def _blockers_satisfied(self, wave: int, issue: int) -> bool:
        assert self.state is not None
        project = self.state.project
        # Lookup blockers from GH dependencies
        try:
            blockers = set(self.gh.get_blockers(issue))
        except Exception:
            blockers = set()
        if not blockers:
            return True
        items = {it.get("content", {}).get("number"): it for it in self.gh.list_items(project)}
        for b in blockers:
            it = items.get(b)
            if not it:
                # If blocker not in project, fall back to label wave check
                bwave = self.gh.get_issue_wave_by_label(b)
                if bwave is not None and bwave < wave:
                    continue
                # Unknown blocker status -> treat as blocking
                return False
            fields = {}
            for f in it.get("fields") or []:
                nm = (f.get("name") or f.get("field", {}).get("name") or "").strip()
                val = f.get("value")
                fields[nm] = val.get("name") if isinstance(val, dict) else (str(val) if val is not None else None)
            st = self._get_field_value(fields, "slaps-state")
            bwave = self._get_field_value(fields, "slaps-wave")
            try:
                bwave = int(bwave) if bwave is not None else None
            except Exception:
                bwave = None
            if st == "closed":
                continue
            if bwave is not None and bwave < wave:
                continue
            return False
        return True

    def unlock_sweep(self, wave: int) -> None:
        assert self.state is not None
        prj = self.state.project
        f_state = self.state.field("slaps-state")
        opened = 0
        items = self.gh.list_items(prj)
        wave_issues = self._list_wave_issues_from_gh(wave)
        for it in items:
            issue = (it.get("content") or {}).get("number")
            if issue not in wave_issues:
                continue
            fields = {}
            for f in it.get("fields") or []:
                nm = (f.get("name") or f.get("field", {}).get("name") or "").strip()
                val = f.get("value")
                fields[nm] = val.get("name") if isinstance(val, dict) else (str(val) if val is not None else None)
            st = self._get_field_value(fields, "slaps-state")
            if st in ("blocked", "failure"):
                if self._blockers_satisfied(wave, issue):
                    # Only open if attempt count < 3. Dead-letter is handled at worker time.
                    f_attempt = self.state.field("slaps-attempt-count")
                    try:
                        cur = int(self._get_field_value(fields, "slaps-attempt-count") or "0")
                    except Exception:
                        cur = 0
                    if cur < 3:
                        self.gh.set_item_number_field(prj, it["id"], f_attempt, cur + 1)
                        self.gh.set_item_single_select(prj, it["id"], f_state, "open")
                        opened += 1
                        self._emit("unlock_open", issue=issue)
        if opened:
            self.r.report(f"[SYSTEM] Opened {opened} issues in wave {wave}")

    def watch_locks(self) -> None:
        """Process new lock files by marking issues as claimed and recording the worker id in GH fields.

        Format of lock filename: {issue}.lock.txt ; file content should contain worker id as integer.
        """
        assert self.state is not None
        prj = self.state.project
        f_state = self.state.field("slaps-state")
        f_worker = self.state.field("slaps-worker")
        for lock in sorted(self.lock_dir.glob("*.lock.txt")):
            issue = extract_issue_number(lock)
            if issue is None:
                continue
            try:
                wid = int(lock.read_text(encoding="utf-8").strip().splitlines()[0])
            except Exception:
                continue
            item_id = self.gh.ensure_issue_in_project(prj, issue)
            self.gh.set_item_number_field(prj, item_id, f_worker, wid)
            self.gh.set_item_single_select(prj, item_id, f_state, "claimed")
            self.gh.add_label(issue, "slaps-wip")
            self._emit("claimed", issue=issue, worker=wid)
            self.r.report(f"[SYSTEM] Claimed issue #{issue} for worker {wid}")


class GHWorker:
    def __init__(self, worker_id: int, gh: GHPort, fs: FilePort, reporter: ReporterPort, logger: Optional[JsonlLogger], locks: Path, project: GHProject, fields: Dict[str, GHField]):
        self.worker_id = worker_id
        self.gh = gh
        self.fs = fs
        self.r = reporter
        self.log = logger
        self.locks = locks
        self.project = project
        self.fields = fields

    def _emit(self, event: str, **kw) -> None:
        if self.log:
            self.log.emit(event, worker=self.worker_id, **kw)

    def _atomic_lock_create(self, issue: int) -> bool:
        self.fs.mkdirs(self.locks)
        p = self.locks / f"{issue}.lock.txt"
        try:
            # atomic create
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(self.worker_id))
            return True
        except FileExistsError:
            return False

    def _remove_lock(self, issue: int) -> None:
        try:
            (self.locks / f"{issue}.lock.txt").unlink(missing_ok=True)
        except Exception:
            pass

    def _list_open_issues(self, wave: int) -> List[int]:
        items = self.gh.list_items(self.project)
        out: List[int] = []
        for it in items:
            content = it.get("content") or {}
            num = content.get("number")
            fields = { (f.get("name") or f.get("field", {}).get("name") or "").strip(): f.get("value") for f in (it.get("fields") or []) }
            st = fields.get("slaps-state")
            st = st.get("name") if isinstance(st, dict) else st
            wv = fields.get("slaps-wave")
            try:
                wv = int(wv) if not isinstance(wv, dict) else None
            except Exception:
                wv = None
            if num and st == "open" and wv == wave:
                out.append(num)
        return sorted(out)

    def claim_and_verify(self, issue: int, timeout: float = 60.0) -> bool:
        if not self._atomic_lock_create(issue):
            self.r.report(f"[WORKER:{self.worker_id:03d}] Lock exists for #{issue}; skipping")
            return False
        self._emit("lock_create", issue=issue)
        # Wait for watcher to set GH fields
        f_worker = self.fields["slaps-worker"]
        start = time.time()
        item_id = self.gh.ensure_issue_in_project(self.project, issue)
        while time.time() - start < timeout:
            fields = self.gh.get_item_fields(self.project, item_id)
            try:
                wid = int(fields.get("slaps-worker") or "0")
            except Exception:
                wid = 0
            if wid == self.worker_id:
                self.r.report(f"[WORKER:{self.worker_id:03d}] Verified claim on #{issue}")
                return True
            time.sleep(2)
        # Timed out; relinquish
        self._remove_lock(issue)
        self._emit("claim_timeout", issue=issue)
        self.r.report(f"[WORKER:{self.worker_id:03d}] Claim timeout #{issue}; releasing lock")
        return False

    def _extract_ac(self, body: str) -> Optional[str]:
        lines = body.splitlines()
        start = None
        for i, ln in enumerate(lines):
            if ln.strip().lower().startswith("## acceptance criteria"):
                start = i
                break
        if start is None:
            return None
        out = []
        for j in range(start, len(lines)):
            if j > start and lines[j].strip().startswith("## "):
                break
            out.append(lines[j])
        return "\n".join(out).strip()

    def _latest_tasks_comment(self, issue: int) -> Optional[str]:
        try:
            comments = self.gh.list_issue_comments(issue)
        except Exception:
            comments = []
        latest = None
        latest_ts = None
        for c in comments:
            body = c.get("body") or ""
            if body.strip().startswith("## TASKS"):
                ts = c.get("createdAt") or ""
                if latest is None or ts > (latest_ts or ""):
                    latest = body
                    latest_ts = ts
        return latest

    def _extract_prompt_block(self, text: str) -> Optional[str]:
        # Try to extract a ```text``` fenced block under a heading "Prompt"
        import re
        m = re.search(r"```(?:text)?\n([\s\S]*?)\n```", text)
        if m:
            return m.group(1).strip()
        return None

    def _compose_prompt(self, issue: int) -> str:
        raw = Path('.slaps/tasks/raw') / f"issue-{issue}.json"
        title = f"Issue #{issue}"
        body = ""
        if raw.exists():
            try:
                data = json.loads(raw.read_text(encoding='utf-8'))
                title = data.get('title') or title
                body = data.get('body') or ''
            except Exception:
                pass
        ac = self._extract_ac(body) or "## Acceptance Criteria\n- Execute the task as described."
        plan = self._latest_tasks_comment(issue)
        plan_prompt = self._extract_prompt_block(plan) if plan else None
        if plan_prompt:
            return plan_prompt
        # Fall back to constructing a prompt from issue body + AC if no plan found
        return (
            "You are an autonomous repo assistant. Follow all repository rules.\n\n"
            f"Task: {title}\n\n"
            f"Details (from issue body):\n\n{body}\n\n"
            f"{ac}\n\n"
            "Important:\n- DO NOT perform git operations.\n- Write failing tests first, then implementation.\n- Do not run tests directly; rely on repository tooling.\n"
        )

    def _comment_wip(self, issue: int, attempt: int, prompt: str) -> None:
        md = (
            f"# SLAPS: Worker WIP\n\n"
            f"Worker {self.worker_id} has claimed this issue and is about to begin attempt number {attempt} using the following LLM prompt:\n\n"
            f"## Prompt\n\n````text\n{prompt}\n````\n\n"
            "(NOTE: this message was automatically generated by a SLAPS worker swarm 🦾 beep-boop)\n"
        )
        try:
            self.gh.add_comment(issue, md)
        except Exception:
            pass

    def _comment_failure(self, issue: int, stdout_text: str, stderr_text: str, state: str) -> None:
        md = (
            f"## SLAPS Worker Attempt FAILED\n\n"
            f"🚨 Worker #{self.worker_id} failed to resolve this issue. The following are the `stdout` and `stderr` streams from the LLM that made the attempt.\n\n"
            f"<details>\n<summary>STDOUT</summary>\n\n```text\n{stdout_text}\n```\n</details>\n\n"
            f"<details>\n<summary>STDERR</summary>\n\n```text\n{stderr_text}\n```\n</details>\n\n"
            f"The issue is now marked as: {state}\n\n"
            "(NOTE: This message was automatically generated by a SLAPS worker swarm 🦾 beep-boop)\n"
        )
        try:
            self.gh.add_comment(issue, md)
        except Exception:
            pass

    def _comment_success(self, issue: int) -> None:
        md = (
            f"## SLAPS Worker Did It\n\n"
            f"✌️ Worker #{self.worker_id} successfully resolved this issue.\n\n"
            "(NOTE: This message was automatically generated by a SLAPS worker swarm 🦾 beep-boop)\n"
        )
        try:
            self.gh.add_comment(issue, md)
        except Exception:
            pass

    def work_issue(self, issue: int, llm) -> bool:
        # Compose prompt and post WIP comment
        item_id = self.gh.ensure_issue_in_project(self.project, issue)
        fields = self.gh.get_item_fields(self.project, item_id)
        try:
            attempt = int(fields.get("slaps-attempt-count") or "1")
        except Exception:
            attempt = 1
        prompt = self._compose_prompt(issue)
        self._comment_wip(issue, attempt, prompt)

        # Execute
        logs_dir = Path('.slaps/logs/workers') / f"{self.worker_id:03d}"
        self.fs.mkdirs(logs_dir)
        out_path = logs_dir / f"{issue}-llm.stdout.txt"
        err_path = logs_dir / f"{issue}-llm.stderr.txt"
        # truncate live
        (logs_dir / 'current-llm.stdout.txt').write_text('', encoding='utf-8')
        (logs_dir / 'current-llm.stderr.txt').write_text('', encoding='utf-8')
        rc, out, err = llm.exec(prompt, out_path=logs_dir / 'current-llm.stdout.txt', err_path=logs_dir / 'current-llm.stderr.txt')
        # archive
        (out_path).write_text(out, encoding='utf-8')
        (err_path).write_text(err, encoding='utf-8')

        f_state = self.fields["slaps-state"]
        if rc == 0:
            self.gh.set_item_single_select(self.project, item_id, f_state, "closed")
            self.gh.add_label(issue, "slaps-did-it")
            self._comment_success(issue)
            self._remove_lock(issue)
            self.r.report(f"[WORKER:{self.worker_id:03d}] LLM success task #{issue}")
            self._emit("success", issue=issue)
            return True
        else:
            # Read current attempt count to decide dead vs remediation
            fields_now = self.gh.get_item_fields(self.project, item_id)
            try:
                cur_attempt = int(fields_now.get("slaps-attempt-count") or "1")
            except Exception:
                cur_attempt = 1
            if cur_attempt >= 3:
                # Dead letter immediately
                self.gh.set_item_single_select(self.project, item_id, f_state, "dead")
                self.gh.add_label(issue, "slaps-failed")
                self._comment_failure(issue, out, err, state="dead")
                self._remove_lock(issue)
                self.r.report(f"[WORKER:{self.worker_id:03d}] LLM error task #{issue}: exit code {rc}; marked dead")
                self._emit("dead", issue=issue, rc=rc)
                return True
            # mark failure, post details, then generate remediation plan and reopen with attempt+1
            self.gh.set_item_single_select(self.project, item_id, f_state, "failure")
            self._comment_failure(issue, out, err, state="failure")
            # Build remediation plan (## TASKS New Approach) with a new prompt block
            rem_prompt = (
                "You are a senior engineer triaging a failed automated attempt.\n"
                "Read the following artifacts and write a concise remediation plan as a Markdown comment that starts with the heading '## TASKS New Approach'.\n"
                "Include a table with: What Went Wrong, New Plan, Why This Should Work, Confidence Index (0-1).\n"
                "Then include a 'Prompt' section with a fenced ```text block containing the exact prompt the next worker should run.\n\n"
                f"Issue #{issue} prior prompt:\n\n```text\n{prompt}\n```\n\n"
                f"LLM STDOUT (truncated):\n\n```text\n{out[:4000]}\n```\n\n"
                f"LLM STDERR (truncated):\n\n```text\n{err[:4000]}\n```\n\n"
                "Important constraints:\n- DO NOT perform git operations.\n- Plan must be specific and executable in this repository.\n- Keep the prompt self-contained.\n"
            )
            rc2, plan_md, _ = llm.exec(rem_prompt, timeout=120)
            if rc2 == 0 and plan_md.strip():
                try:
                    self.gh.add_comment(issue, plan_md)
                except Exception:
                    pass
            # Reopen for next attempt and increment attempt count now
            f_attempt = self.fields["slaps-attempt-count"]
            self.gh.set_item_number_field(self.project, item_id, f_attempt, cur_attempt + 1)
            self.gh.set_item_single_select(self.project, item_id, f_state, "open")
            self._remove_lock(issue)
            self.r.report(f"[WORKER:{self.worker_id:03d}] LLM error task #{issue}: exit code {rc}; posted remediation and reopened")
            self._emit("failure_reopen", issue=issue, rc=rc, next_attempt=cur_attempt + 1)
            return True
