import unittest
from pathlib import Path

from tools.tasks.taskwatch.domain_gh import GHWatcher, GHWorker
from tools.tasks.taskwatch.adapters import LocalFS
from tools.tasks.tests.test_taskwatch_gh import FakeGH


class DummyReporter:
    def __init__(self):
        self.lines = []

    def report(self, text: str) -> None:
        self.lines.append(text)


class CoordinatorGHUnitTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fs = LocalFS()
        self.raw = self.root / ".slaps" / "tasks" / "raw"
        self.lock = self.root / ".slaps" / "tasks" / "lock"
        self.raw.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _watcher(self, gh):
        rep = DummyReporter()
        w = GHWatcher(gh=gh, fs=self.fs, reporter=rep, logger=None,
                      raw_dir=self.raw, lock_dir=self.lock, project_title="SLAPS-repo")
        w.leader_ttl_sec = -1
        return w

    def test_counts_and_abort_logic_from_project(self):
        from tools.tasks.coordinator_gh import CoordinatorGH
        gh = FakeGH()
        watcher = self._watcher(gh)
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        project = watcher.state.project
        fields = watcher.state.fields
        # Set states: one open (42), one dead (55)
        items = {it["content"]["number"]: it for it in gh.list_items(project)}
        gh.set_item_single_select(project, items[42]["id"], fields["slaps-state"], "open")
        gh.set_item_single_select(project, items[55]["id"], fields["slaps-state"], "dead")
        coord = CoordinatorGH(gh)
        counts = coord.compute_counts(project, wave=1)
        self.assertEqual(1, counts["open"])  # one open
        self.assertEqual(1, counts["dead"])  # one dead
        self.assertTrue(coord.should_abort(counts))

    def test_wave_status_issue_created_and_added(self):
        from tools.tasks.coordinator_gh import CoordinatorGH
        gh = FakeGH()
        watcher = self._watcher(gh)
        watcher.preflight(wave=1)
        project = watcher.state.project
        coord = CoordinatorGH(gh)
        num = coord.create_wave_status_issue(project, wave=1)
        self.assertIsInstance(num, int)
        # ensure exists and is added to project
        item_id = gh.find_item_by_issue(project, num)
        self.assertIsNotNone(item_id)

    def test_mini_flow_no_dead_does_not_abort(self):
        from tools.tasks.coordinator_gh import CoordinatorGH
        gh = FakeGH()
        watcher = self._watcher(gh)
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        project = watcher.state.project
        fields = watcher.state.fields
        # Open roots and close blocker 42
        watcher.unlock_sweep(wave=1)
        # Simulate worker closing 42
        items = {it["content"]["number"]: it for it in gh.list_items(project)}
        gh.set_item_single_select(project, items[42]["id"], fields["slaps-state"], "closed")
        # Unlock dependent 55 now
        watcher.unlock_sweep(wave=1)
        coord = CoordinatorGH(gh)
        counts = coord.compute_counts(project, wave=1)
        self.assertEqual(1, counts.get("open", 0))  # 55 open
        self.assertEqual(1, counts.get("closed", 0))  # 42 closed
        self.assertFalse(coord.should_abort(counts))

    def test_progress_comment_content(self):
        from tools.tasks.coordinator_gh import CoordinatorGH
        gh = FakeGH()
        watcher = self._watcher(gh)
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        project = watcher.state.project
        fields = watcher.state.fields
        # Prepare states: 42 closed; 55 open; 56 blocked by 55
        items = {it["content"]["number"]: it for it in gh.list_items(project)}
        gh.set_item_single_select(project, items[42]["id"], fields["slaps-state"], "closed")
        gh.set_item_single_select(project, items[55]["id"], fields["slaps-state"], "open")
        gh.blockers[56] = [55]
        gh.set_item_single_select(project, items[56]["id"], fields["slaps-state"], "blocked")
        coord = CoordinatorGH(gh)
        md = coord.compose_progress_md(project, wave=1)
        self.assertIn("SLAPS Progress Update", md)
        self.assertIn("OPEN ISSUES", md)
        self.assertIn("#55", md)
        # Post comment and verify stored
        coord.post_progress_comment(project, wave_issue=1001, wave=1)
        self.assertTrue(any(c[0] == 1001 and 'SLAPS Progress Update' in c[1] for c in gh.comments))

    def test_progress_comment_throttle(self):
        from tools.tasks.coordinator_gh import CoordinatorGH
        gh = FakeGH()
        watcher = self._watcher(gh)
        watcher.preflight(wave=1)
        watcher.initialize_items(wave=1)
        project = watcher.state.project
        coord = CoordinatorGH(gh)
        coord.debounce_sec = 9999
        coord.post_progress_comment(project, wave_issue=1002, wave=1)
        coord.post_progress_comment(project, wave_issue=1002, wave=1)
        # Only one comment due to throttle
        comments = [c for c in gh.comments if c[0] == 1002]
        self.assertEqual(1, len(comments))


if __name__ == "__main__":
    unittest.main()
