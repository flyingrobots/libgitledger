import json
import tempfile
from pathlib import Path

import unittest

from tools.tasks.taskwatch.domain import (
    POLICY_GUARDRAILS as GUARD,
    Watcher,
    Worker,
    default_paths,
    ensure_dirs,
)
from tools.tasks.taskwatch.adapters import LocalFS
from tools.tasks.taskwatch.ports import FilePort, LLMPort, ReporterPort


class FakeLLM(LLMPort):
    def __init__(self, rc: int = 0, capture: list[str] | None = None):
        self.rc = rc
        self.capture = capture if capture is not None else []

    def exec(self, prompt: str):
        # capture the prompt for assertions
        self.capture.append(prompt)
        if self.rc == 0:
            return 0, "ok", ""
        return self.rc, "oops", "bad"


class CaptureReporter(ReporterPort):
    def __init__(self):
        self.lines: list[str] = []

    def report(self, text: str) -> None:
        self.lines.append(text)


class TaskwatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".slaps" / "tasks"
        self.fs: FilePort = LocalFS()
        self.paths = default_paths(self.root)
        ensure_dirs(self.fs, self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def test_worker_success_moves_to_closed_and_prepends_guardrails(self):
        # Arrange
        open_f = self.paths.open / "10.txt"
        self.fs.write_text(open_f, "do the thing")
        llm = FakeLLM(rc=0)
        w = Worker(worker_id=1, fs=self.fs, llm=llm, paths=self.paths)

        # Act
        worked = w.run_once()

        # Assert
        self.assertTrue(worked)
        self.assertEqual([], self.fs.list_files(self.paths.open))
        closed = self.fs.list_files(self.paths.closed)
        self.assertEqual(1, len(closed))
        self.assertEqual("10.txt", closed[0].name)
        # guardrails enforced
        self.assertTrue(any(GUARD in p for p in llm.capture))

    def test_worker_failure_moves_to_failed_and_appends_footer(self):
        # Arrange
        open_f = self.paths.open / "11.txt"
        self.fs.write_text(open_f, "do the thing (fail)")
        llm = FakeLLM(rc=2)
        w = Worker(worker_id=1, fs=self.fs, llm=llm, paths=self.paths)

        # Act
        worked = w.run_once()

        # Assert
        self.assertTrue(worked)
        failed = self.fs.list_files(self.paths.failed)
        self.assertEqual(1, len(failed))
        txt = failed[0].read_text(encoding="utf-8")
        self.assertIn("## FAILURE:", txt)
        self.assertIn("STDOUT:", txt)
        self.assertIn("STDERR:", txt)

    def test_watcher_unlocks_blocked_when_all_blockers_closed(self):
        # Arrange: edges 10 -> 12; 12 blockedBy [10]
        edges = self.paths.edges_csv
        self.fs.write_text(edges, "10,12\n")
        raw12 = self.paths.raw / "issue-12.json"
        self.fs.write_text(raw12, json.dumps({"relationships": {"blockedBy": [10]}}))
        self.fs.write_text(self.paths.blocked / "12.txt", "prompt for 12")

        reporter = CaptureReporter()
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=reporter, paths=self.paths)

        # Simulate close of 10
        closed10 = self.paths.closed / "10.txt"
        self.fs.write_text(closed10, "done")

        # Act
        watcher.handle_closed(closed10, workers=[])  # no workers in this test

        # Assert: marker written and 12 moved to open
        markers = self.fs.list_files(self.paths.admin_closed)
        self.assertTrue(any(m.name.startswith("10") for m in markers))
        open_files = self.fs.list_files(self.paths.open)
        self.assertEqual([self.paths.open / "12.txt"], open_files)

    def test_watcher_failed_three_attempts_moves_to_dead(self):
        reporter = CaptureReporter()
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=reporter, paths=self.paths)
        f = self.paths.failed / "13.txt"
        self.fs.write_text(f, "failed body")

        # Attempt 1
        watcher.handle_failed(f, workers=[])
        self.assertFalse((self.paths.dead / "13.txt").exists())
        # Recreate failed file for next attempt
        self.fs.write_text(self.paths.failed / "13.txt", "failed body")
        watcher.handle_failed(self.paths.failed / "13.txt", workers=[])
        self.assertFalse((self.paths.dead / "13.txt").exists())
        # Third attempt -> dead
        self.fs.write_text(self.paths.failed / "13.txt", "failed body")
        watcher.handle_failed(self.paths.failed / "13.txt", workers=[])
        self.assertTrue((self.paths.dead / "13.txt").exists())


if __name__ == "__main__":
    unittest.main()
