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
        for n, body in self.comments:
            if n == issue_number:
                out.append({"createdAt": "2024-01-01T00:00:00Z", "body": body})
        return out


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
