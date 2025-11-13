import json
import tempfile
from pathlib import Path

import unittest

from tools.tasks.taskwatch.ports import GHPort, GHProject, GHField
from tools.tasks.taskwatch.adapters import LocalFS
from tools.tasks.taskwatch.domain_gh import GHWatcher, GHWorker, STATE_VALUES


class FakeGH(GHPort):
    def __init__(self):
        self._owner = "me"
        self.projects = {}
        self.labels = set()
        self.items = {}  # project_id -> list of {id, content:{number}, fields:[{name,value}]}
        self.issue_id = {}  # number -> node id
        self.comments = []
        self.wave_map = {42: 1, 55: 1, 56: 1}
        self.blockers = {55: [42], 56: [55]}
        
    def repo_owner(self) -> str:
        return self._owner

    def ensure_project(self, title: str) -> GHProject:
        if title in self.projects:
            return self.projects[title]
        prj = GHProject(owner=self._owner, number=len(self.projects) + 1, id=f"PRJ{len(self.projects)+1}", title=title)
        self.projects[title] = prj
        self.items[prj.id] = []
        return prj

    def ensure_labels(self, labels):
        self.labels |= set(labels)

    def ensure_fields(self, project, single_select_state_values):
        return {
            "slaps-state": GHField(id="F_STATE", name="slaps-state", data_type="SINGLE_SELECT", options={n: f"OPT_{n}" for n in single_select_state_values}),
            "slaps-worker": GHField(id="F_WORK", name="slaps-worker", data_type="NUMBER"),
            "slaps-attempt-count": GHField(id="F_ATTEMPT", name="slaps-attempt-count", data_type="NUMBER"),
            "slaps-wave": GHField(id="F_WAVE", name="slaps-wave", data_type="NUMBER"),
        }

    def issue_node_id(self, issue_number: int) -> str:
        nid = self.issue_id.get(issue_number)
        if not nid:
            nid = f"ISSUE{issue_number}"
            self.issue_id[issue_number] = nid
        return nid

    def ensure_issue_in_project(self, project, issue_number: int) -> str:
        for it in self.items[project.id]:
            if it["content"]["number"] == issue_number:
                return it["id"]
        item = {"id": f"ITEM{issue_number}", "content": {"number": issue_number}, "fields": []}
        self.items[project.id].append(item)
        return item["id"]

    def list_items(self, project):
        arr = []
        for it in self.items[project.id]:
            # deep copy minimal
            arr.append({"id": it["id"], "content": dict(it["content"]), "fields": [dict(f) for f in it["fields"]]})
        return arr

    def list_issues_for_wave(self, wave: int):
        return [n for n, w in self.wave_map.items() if w == wave]

    def get_blockers(self, issue_number: int):
        return list(self.blockers.get(issue_number, []))

    def get_issue_wave_by_label(self, issue_number: int):
        return self.wave_map.get(issue_number)

    def _set_field(self, project, item_id: str, name: str, value):
        it = next(i for i in self.items[project.id] if i["id"] == item_id)
        # replace or add
        for f in it["fields"]:
            if (f.get("name") or f.get("field", {}).get("name")) == name:
                f["value"] = value
                return
        it["fields"].append({"name": name, "value": value})

    def set_item_number_field(self, project, item_id, field, value: float):
        self._set_field(project, item_id, field.name, value)

    def set_item_text_field(self, project, item_id, field, value: str):
        self._set_field(project, item_id, field.name, value)

    def set_item_single_select(self, project, item_id, field, option_value: str):
        self._set_field(project, item_id, field.name, {"id": field.options.get(option_value) if field.options else None, "name": option_value})

    def get_item_fields(self, project, item_id):
        it = next(i for i in self.items[project.id] if i["id"] == item_id)
        out = {}
        for f in it["fields"]:
            nm = (f.get("name") or f.get("field", {}).get("name"))
            val = f.get("value")
            out[nm] = val.get("name") if isinstance(val, dict) else (str(val) if val is not None else None)
        return out

    def find_item_by_issue(self, project, issue_number: int):
        for it in self.items[project.id]:
            if it["content"]["number"] == issue_number:
                return it["id"]
        return None

    def add_label(self, issue_number: int, label: str):
        self.labels.add(label)

    def remove_label(self, issue_number: int, label: str):
        pass

    def add_comment(self, issue_number: int, body_markdown: str):
        self.comments.append((issue_number, body_markdown))

    def list_issue_comments(self, issue_number: int):
        # Return comments as list of dicts in insertion order
        out = []
        idx = 0
        for n, body in self.comments:
            if n == issue_number:
                idx += 1
                out.append({"createdAt": f"2024-01-01T00:{idx:03d}:00Z", "body": body})
        return out

    def fetch_issue_json(self, issue_number: int) -> dict:
        state = 'OPEN'
        return {"number": issue_number, "state": state, "labels": [{"name": f"milestone::M{self.wave_map.get(issue_number, 1)}"}]}

    def project_item_create_draft(self, project, title: str, body: str) -> str:
        # ignore
        return "DRAFT1"

    def repo_name(self) -> str:
        return "repo"

    def create_issue(self, title: str, body: str) -> int:
        # create a new synthetic issue number (max existing + 1)
        new_num = 1
        if self.issue_id:
            new_num = max(self.issue_id.keys()) + 1
        self.issue_id[new_num] = f"ISSUE{new_num}"
        # In this FakeGH we don't persist titles/bodies beyond ID allocation
        return new_num


class TestGHFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw = self.root / ".slaps" / "tasks" / "raw"
        self.lock = self.root / ".slaps" / "tasks" / "lock"
        self.raw.mkdir(parents=True)
        # create raw issues with wave label
        def j(num, wave, blocked_by=None):
            blocked_by = blocked_by or []
            labels = [{"name": f"milestone::M{wave}"}]
            data = {"number": num, "title": f"Issue {num}", "body": "Body\n\n## Acceptance Criteria\n- AC1", "labels": labels, "relationships": {"blockedBy": blocked_by}}
            (self.raw / f"issue-{num}.json").write_text(json.dumps(data), encoding="utf-8")
        j(42, 1, [])
        j(55, 1, [42])
        j(56, 1, [55])

        self.fs = LocalFS()
        self.gh = FakeGH()

    def tearDown(self):
        self.tmp.cleanup()

    def test_preflight_unlock_and_claim_flow(self):
        # Arrange
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        # Make this watcher leader immediately and with a long TTL
        watcher.leader_ttl_sec = -1  # force leader
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        watcher.unlock_sweep(wave=1)

        # 42 should be open now; 55 remains blocked until 42 closes; 56 blocked
        prj = watcher.state.project
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        def state(num):
            it = items[num]
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertEqual("open", state(42))
        self.assertIn("blocked", {state(55), state(56)})

        # Worker 1 creates a lock; watcher processes it -> sets claimed + worker id
        worker = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                          locks=self.lock, project=prj, fields=watcher.state.fields)
        self.assertTrue(worker._atomic_lock_create(42))
        watcher.watch_locks()

        # Close 42 by simulating worker success without running LLM
        item_id = self.gh.find_item_by_issue(prj, 42)
        self.gh.set_item_single_select(prj, item_id, watcher.state.fields["slaps-state"], "closed")

        # Unlock sweep should open 55 now
        watcher.unlock_sweep(wave=1)
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        self.assertEqual("open", state(55))

    def test_initialize_items_idempotent(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        first = self.gh.list_items(prj)
        watcher.initialize_items(wave=1)
        second = self.gh.list_items(prj)
        self.assertEqual(len(first), len(second))

    def test_deps_change_runtime_unlocks(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        # Initially blocked: 55 blocked by 42
        watcher.unlock_sweep(wave=1)
        prj = watcher.state.project
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        def state(num):
            it = items.get(num)
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertIn(state(55), ("blocked", None))
        # Change blockers: remove 42 so 55 has none
        self.gh.blockers[55] = []
        watcher.unlock_sweep(wave=1)
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        self.assertEqual("open", state(55))

    def test_stale_lock_cleanup(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.lock_ttl_sec = 0  # immediately stale
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        # Create a stale lock
        lf = self.lock / "42.lock.txt"
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text('{"worker_id": 9, "started_at": 1}', encoding='utf-8')
        watcher.watch_locks()
        self.assertFalse(lf.exists())

    def test_non_leader_stands_down(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        # Write fresh leader heartbeat (another watcher)
        watcher.leader_ttl_sec = 60
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        hb = watcher.leader_heartbeat
        hb.write_text('{"pid":1,"host":"x","ts": 999999999999}', encoding='utf-8')
        # Create a lock, but watch_locks should do nothing since not leader
        lf = self.lock / "42.lock.txt"
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text('{"worker_id": 1, "started_at": 999999999999}', encoding='utf-8')
        watcher.watch_locks()
        # No claimed since not leader
        prj = watcher.state.project
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        def state(num):
            it = items.get(num)
            if not it:
                return None
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertNotEqual("claimed", state(42))

    def test_leader_handoff_on_stale_heartbeat(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        # watcher1 writes an old heartbeat
        watcher1 = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                             raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher1.preflight(wave=1)
        watcher1.initialize_items(wave=1)
        hb = watcher1.leader_heartbeat
        hb.parent.mkdir(parents=True, exist_ok=True)
        hb.write_text('{"pid":1,"host":"x","ts": 0}', encoding='utf-8')
        # create a lock
        lf = self.lock / "42.lock.txt"
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text('{"worker_id": 7, "started_at": 999999999999}', encoding='utf-8')
        # watcher2 should take leadership and claim
        watcher2 = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                             raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher2.preflight(wave=1)
        watcher2.initialize_items(wave=1)
        watcher2.watch_locks()
        prj = watcher1.state.project
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        def state(num):
            it = items.get(num)
            if not it:
                return None
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertEqual("claimed", state(42))

    def test_claim_posts_progress_comment_when_wave_issue_set(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        # Set env wave issue and create a lock
        import os
        os.environ['WAVE_STATUS_ISSUE'] = '999'
        lf = self.lock / "42.lock.txt"
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text('{"worker_id": 7, "started_at": 999999999999}', encoding='utf-8')
        # Create another lock in same pass to verify coalescing
        lf2 = self.lock / "55.lock.txt"
        lf2.write_text('{"worker_id": 7, "started_at": 999999999999}', encoding='utf-8')
        watcher.progress_debounce_sec = 9999
        watcher.watch_locks()
        # Verify a single coalesced comment was posted to the wave issue
        progress = [c for c in self.gh.comments if c[0] == 999 and 'SLAPS Progress Update' in c[1]]
        self.assertEqual(1, len(progress))
        # Clean env
        import os
        del os.environ['WAVE_STATUS_ISSUE']

    def test_watcher_progress_debounce(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.progress_debounce_sec = 9999
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        # Env wave issue
        import os
        os.environ['WAVE_STATUS_ISSUE'] = '1000'
        # First pass: create 42 lock and process
        import time
        now = int(time.time())
        (self.lock / '42.lock.txt').write_text('{"worker_id":1,"started_at":%d}' % now, encoding='utf-8')
        watcher.watch_locks()
        # Second pass quickly: create 55 lock and process; debounce suppresses comment
        (self.lock / '55.lock.txt').write_text('{"worker_id":1,"started_at":%d}' % now, encoding='utf-8')
        watcher.watch_locks()
        comments = [c for c in self.gh.comments if c[0] == 1000]
        self.assertEqual(1, len(comments))
        del os.environ['WAVE_STATUS_ISSUE']

    def test_blocker_not_in_project_prior_wave_opens_dependent(self):
        # 60 (wave 0) blocks 61 (wave 1), 60 not added to project items
        self.gh.wave_map[60] = 0
        self.gh.blockers[61] = [60]
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        # Only initialize items for wave 1 (61)
        # FakeGH.list_issues_for_wave returns those in wave_map == 1; ensure 61 added
        self.gh.wave_map[61] = 1
        watcher.initialize_items(wave=1)
        watcher.unlock_sweep(wave=1)
        prj = watcher.state.project
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        def state(num):
            it = items[num]
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertEqual("open", state(61))

    def test_attempt_increment_invariants_worker_failure_and_unlock(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        # Prepare issue 42 open with attempt=1
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        id42 = items[42]["id"]
        self.gh.set_item_number_field(prj, id42, fields["slaps-attempt-count"], 1)
        self.gh.set_item_single_select(prj, id42, fields["slaps-state"], "open")
        # Worker fails → remediation + reopen attempt=2
        class FailLLM:
            def exec(self, prompt, timeout=None, out_path=None, err_path=None):
                return 2, "", "err"
        w = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        w.work_issue(42, FailLLM())
        # Read fields
        f = self.gh.get_item_fields(prj, id42)
        self.assertEqual('open', f.get('slaps-state'))
        self.assertEqual('2', f.get('slaps-attempt-count'))
        # Unlock sweep increments from failure as well (setup):
        # Close blocker 42 so 55 can open
        self.gh.set_item_single_select(prj, id42, fields["slaps-state"], "closed")
        # Set 55 failure attempt=1
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        id55 = items[55]["id"]
        self.gh.set_item_number_field(prj, id55, fields["slaps-attempt-count"], 1)
        self.gh.set_item_single_select(prj, id55, fields["slaps-state"], "failure")
        watcher.unlock_sweep(wave=1)
        f2 = self.gh.get_item_fields(prj, id55)
        self.assertEqual('open', f2.get('slaps-state'))
        self.assertEqual('2', f2.get('slaps-attempt-count'))

    def test_latest_tasks_comment_with_pagination(self):
        # Add two TASKS comments; second is later and should be used
        self.gh.comments = [
            (42, "## TASKS\n\n## Prompt\n\n```text\nold\n```"),
            (42, "## TASKS\n\n## Prompt\n\n```text\nnew\n```"),
        ]
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        w = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        p = w._compose_prompt(42)
        self.assertEqual("new", p)

    def test_tasks_without_prompt_block_falls_back_to_issue_body_ac(self):
        # Add a TASKS comment without a fenced block; worker should use issue body+AC fallback
        self.gh.comments = [
            (42, "## TASKS\n\n(no prompt block here)")
        ]
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        w = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        prompt = w._compose_prompt(42)
        self.assertIn('Acceptance Criteria', prompt)

    def test_prompt_fenced_any_language_accepted(self):
        # Add a TASKS comment with ```md fenced block
        self.gh.comments = [
            (42, "## TASKS\n\n## Prompt\n\n```md\nhello world\n```")
        ]
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        w = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        prompt = w._compose_prompt(42)
        self.assertEqual('hello world', prompt)

    def test_unlock_sweep_does_not_open_failure_attempt3(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        id55 = items[55]["id"]
        # Satisfy blockers (close 42) and set 55 to failure attempt=3
        gh = self.gh
        gh.set_item_single_select(prj, items[42]["id"], fields["slaps-state"], "closed")
        gh.set_item_number_field(prj, id55, fields["slaps-attempt-count"], 3)
        gh.set_item_single_select(prj, id55, fields["slaps-state"], "failure")
        watcher.unlock_sweep(wave=1)
        f = gh.get_item_fields(prj, id55)
        self.assertEqual('failure', f.get('slaps-state'))

    def test_worker_claim_timeout_releases_lock(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        # Have 42 open
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        self.gh.set_item_single_select(prj, items[42]["id"], fields["slaps-state"], "open")
        # Worker creates lock but watcher won't claim; verify timeout returns False and lock removed
        w = GHWorker(worker_id=9, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        # create lock and immediately call claim_and_verify with tiny timeout; since watcher isn't run, verify fails and lock is deleted
        ok = w.claim_and_verify(42, timeout=0.01)
        self.assertFalse(ok)
        self.assertFalse((self.lock / '42.lock.txt').exists())
        fvals = self.gh.get_item_fields(prj, items[42]['id'])
        self.assertNotEqual('9', fvals.get('slaps-worker'))

    def test_remediation_comment_and_next_prompt(self):
        # Failure <3 should post New Approach with Prompt used next time
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        id42 = items[42]['id']
        # Set attempt=1 open
        self.gh.set_item_number_field(prj, id42, fields['slaps-attempt-count'], 1)
        self.gh.set_item_single_select(prj, id42, fields['slaps-state'], 'open')
        class PlanLLM:
            def exec(self, prompt, timeout=None, out_path=None, err_path=None):
                # Return a New Approach comment with a Prompt block "NEXTPROMPT"
                return 0, "## TASKS New Approach\n\n## Prompt\n\n```text\nNEXTPROMPT\n```\n", ""
        w = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        # Fail path: simulate rc!=0 by directly calling work_issue with a fake LLM that returns rc==0 for remediation
        class FailThenPlan:
            def __init__(self):
                self.called = 0
            def exec(self, prompt, timeout=None, out_path=None, err_path=None):
                if self.called == 0:
                    self.called += 1
                    return 2, '', 'bad'
                # second call is remediation prompt
                return PlanLLM().exec(prompt, timeout, out_path, err_path)
        w.work_issue(42, FailThenPlan())
        # Verify New Approach comment present and next prompt picks it
        self.assertTrue(any('TASKS New Approach' in c[1] for c in self.gh.comments))
        nprompt = w._compose_prompt(42)
        self.assertEqual('NEXTPROMPT', nprompt)

    def test_latest_tasks_comment_over_100(self):
        # 120 comments; latest should win
        self.gh.comments = []
        for i in range(1, 121):
            body = f"## TASKS\n\n## Prompt\n\n```text\nplan-{i}\n```"
            self.gh.comments.append((42, body))
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        w = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                     locks=self.lock, project=prj, fields=fields)
        p = w._compose_prompt(42)
        self.assertEqual("plan-120", p)

    def test_reconcile_gh_closed_sets_slaps_closed(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        watcher.leader_ttl_sec = -1
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        # Force an item into non-closed state, but mark GH issue as CLOSED
        prj = watcher.state.project
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        id42 = items[42]["id"]
        fields = watcher.state.fields
        self.gh.set_item_single_select(prj, id42, fields["slaps-state"], "open")
        # Override GH fetch to CLOSED for issue 42
        def closed_fetch(num):
            return {"number": num, "state": "CLOSED", "labels": [{"name": "milestone::M1"}]}
        self.gh.fetch_issue_json = closed_fetch
        watcher.unlock_sweep(wave=1)
        items = {it["content"]["number"]: it for it in self.gh.list_items(prj)}
        def state(num):
            it = items[num]
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertEqual("closed", state(42))

    def test_preflight_missing_slaps_state_option_raises(self):
        # Fake GH that returns fields missing 'dead' option
        class FakeGHMissing(FakeGH):
            def ensure_fields(self, project, single_select_state_values):
                f = super().ensure_fields(project, single_select_state_values)
                # strip 'dead'
                f["slaps-state"].options.pop("dead", None)
                return f
        gh2 = FakeGHMissing()
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=gh2, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P")
        with self.assertRaises(RuntimeError):
            watcher.preflight(wave=1)

    def test_failure_to_dead_after_three_attempts(self):
        reporter = type("R", (), {"report": lambda self, s: None})()
        watcher = GHWatcher(gh=self.gh, fs=self.fs, reporter=reporter, logger=None,
                            raw_dir=self.raw, lock_dir=self.lock, project_title="P2")
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        prj = watcher.state.project
        fields = watcher.state.fields
        # Prepare issue 42 as failure with attempt=3 (about to dead-letter)
        id42 = self.gh.find_item_by_issue(prj, 42)
        self.gh.set_item_number_field(prj, id42, fields["slaps-attempt-count"], 3)
        self.gh.set_item_single_select(prj, id42, fields["slaps-state"], "failure")
        # Worker fails again -> should mark dead immediately
        class FailLLM:
            def exec(self, prompt, timeout=None, out_path=None, err_path=None):
                return 2, "", "boom"
        worker = GHWorker(worker_id=1, gh=self.gh, fs=self.fs, reporter=type("R", (), {"report": lambda s, t: None})(), logger=None,
                          locks=self.lock, project=prj, fields=fields)
        # Simulate a claim lock (worker workflow)
        worker._atomic_lock_create(42)
        worker.work_issue(42, FailLLM())
        it = next(i for i in self.gh.list_items(prj) if i["content"]["number"] == 42)
        def st():
            for f in it["fields"]:
                if (f.get("name") or f.get("field", {}).get("name")) == "slaps-state":
                    v = f.get("value")
                    return v.get("name") if isinstance(v, dict) else v
            return None
        self.assertEqual("dead", st())


if __name__ == "__main__":
    unittest.main()
