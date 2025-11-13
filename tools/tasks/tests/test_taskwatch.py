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
    make_paths,
)
from tools.tasks.taskwatch.adapters import LocalFS
from tools.tasks.taskwatch.ports import FilePort, LLMPort, ReporterPort


class FakeLLM(LLMPort):
    def __init__(self, rc: int = 0, capture: list[str] | None = None):
        self.rc = rc
        self.capture = capture if capture is not None else []
        self.last_timeout: float | None = None

    def exec(self, prompt: str, timeout: float | None = None):
        # capture the prompt for assertions
        self.capture.append(prompt)
        self.last_timeout = timeout
        if self.rc == 0:
            return 0, "ok", ""
        return self.rc, "oops", "bad"

class FakeLLMWriter(LLMPort):
    """LLM that writes a new prompt to open/{issue}.txt when invoked by handle_failed."""
    def __init__(self, fs: FilePort, paths):
        self.fs = fs
        self.paths = paths
        self.capture: list[str] = []

    def exec(self, prompt: str, timeout: float | None = None):
        self.capture.append(prompt)
        # Try to extract the issue number from the prompt by looking for '/open/{issue}.txt'
        import re

        m = re.search(r"\.slaps/tasks/open/(\d+)\.txt", prompt)
        if m:
            issue = m.group(1)
            out = self.paths.open / f"{issue}.txt"
            body = f"Attempt 2: Tried X, now trying Y because reasons.\nNew plan here.\n"
            self.fs.write_text(out, body)
        return 0, "ok", ""

    
class EstimatingLLM(LLMPort):
    """LLM that returns an integer minutes for estimate prompts and OK for task exec.
    Records last timeout used for the task exec.
    """
    def __init__(self, minutes: int):
        self.minutes = minutes
        self.capture: list[str] = []
        self.last_timeout: float | None = None

    def exec(self, prompt: str, timeout: float | None = None):
        self.capture.append(prompt)
        if "Estimate how long the following task" in prompt:
            return 0, str(self.minutes), ""
        self.last_timeout = timeout
        return 0, "ok", ""


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
        w = Worker(worker_id=1, fs=self.fs, llm=llm, paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)

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
        w = Worker(worker_id=1, fs=self.fs, llm=llm, paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)

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
        # Third attempt -> dead, and file should include DEAD LETTER footer
        self.fs.write_text(self.paths.failed / "13.txt", "failed body")
        watcher.handle_failed(self.paths.failed / "13.txt", workers=[])
        dead_f = self.paths.dead / "13.txt"
        self.assertTrue(dead_f.exists())
        txt = dead_f.read_text(encoding="utf-8")
        self.assertIn("## DEAD LETTER:", txt)

    def test_watcher_failed_generates_remediation_prompt_with_history(self):
        reporter = CaptureReporter()
        capture_llm = FakeLLM()
        watcher = Watcher(fs=self.fs, llm=capture_llm, reporter=reporter, paths=self.paths)
        f = self.paths.failed / "14.txt"
        self.fs.write_text(f, "original prompt body\n\n## FAILURE:\n\nSTDOUT: x\nSTDERR: y\n")
        watcher.handle_failed(f, workers=[])
        # A remediation prompt should be sent with explicit guidance
        self.assertGreater(len(capture_llm.capture), 0)
        prompt = capture_llm.capture[-1]
        self.assertIn(str(self.paths.failed / "14.txt"), prompt)
        self.assertIn("Previously tried:", prompt)
        self.assertIn("write it to .slaps/tasks/open/14.txt", prompt)
        self.assertIn(GUARD, prompt)

    def test_handle_failed_writes_new_open_prompt_via_llm(self):
        reporter = CaptureReporter()
        writer_llm = FakeLLMWriter(fs=self.fs, paths=self.paths)
        watcher = Watcher(fs=self.fs, llm=writer_llm, reporter=reporter, paths=self.paths)
        f = self.paths.failed / "15.txt"
        self.fs.write_text(f, "original body\n\n## FAILURE:\n\nSTDOUT: s\nSTDERR: e\n")
        watcher.handle_failed(f, workers=[])
        # New open prompt created by the LLM writer
        new_open = self.paths.open / "15.txt"
        self.assertTrue(new_open.exists())
        self.assertIn("Attempt 2:", new_open.read_text(encoding="utf-8"))

    def test_worker_ignores_non_txt(self):
        self.fs.write_text(self.paths.open / "17.md", "ignored")
        w = Worker(worker_id=1, fs=self.fs, llm=FakeLLM(rc=0), paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)
        worked = w.run_once()
        self.assertFalse(worked)
        self.assertTrue((self.paths.open / "17.md").exists())

    def test_two_workers_only_one_claims(self):
        # Arrange: one open task
        self.fs.write_text(self.paths.open / "16.txt", "task")
        w1 = Worker(worker_id=1, fs=self.fs, llm=FakeLLM(rc=0), paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)
        w2 = Worker(worker_id=2, fs=self.fs, llm=FakeLLM(rc=0), paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)
        # Act
        r1 = w1.run_once()
        r2 = w2.run_once()
        # Assert: first worked, second found nothing to claim
        self.assertTrue(r1)
        self.assertFalse(r2)
        self.assertEqual(1, len(self.fs.list_files(self.paths.closed)))

    def test_edges_alt_header_src_dst(self):
        self.fs.write_text(self.paths.edges_csv, "src,dst\n31,32\n")
        self.fs.write_text(self.paths.raw / "issue-32.json", json.dumps({"relationships": {"blockedBy": [31]}}))
        self.fs.write_text(self.paths.blocked / "32.txt", "prompt 32")
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "31.txt"
        self.fs.write_text(c, "done 31")
        watcher.handle_closed(c, workers=[])
        self.assertEqual([self.paths.open / "32.txt"], self.fs.list_files(self.paths.open))

    def test_unblocks_only_after_all_blockers_closed(self):
        # edges: 1->3 and 2->3, so 3 is blocked by [1,2]
        self.fs.write_text(self.paths.edges_csv, "1,3\n2,3\n")
        self.fs.write_text(self.paths.raw / "issue-3.json", json.dumps({"relationships": {"blockedBy": [1, 2]}}))
        self.fs.write_text(self.paths.blocked / "3.txt", "prompt for 3")

        reporter = CaptureReporter()
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=reporter, paths=self.paths)

        # Close 1: should NOT unblock 3 yet
        closed1 = self.paths.closed / "1.txt"
        self.fs.write_text(closed1, "done 1")
        watcher.handle_closed(closed1, workers=[])
        self.assertTrue((self.paths.blocked / "3.txt").exists())
        self.assertEqual([], self.fs.list_files(self.paths.open))

        # Close 2: now all blockers closed, 3 should move to open
        closed2 = self.paths.closed / "2.txt"
        self.fs.write_text(closed2, "done 2")
        watcher.handle_closed(closed2, workers=[])
        self.assertFalse((self.paths.blocked / "3.txt").exists())
        self.assertEqual([self.paths.open / "3.txt"], self.fs.list_files(self.paths.open))

    def test_unblocks_multiple_dependents_from_one_blocker(self):
        # edges: 10->12 and 10->13; both blockedBy [10]
        self.fs.write_text(self.paths.edges_csv, "10,12\n10,13\n")
        self.fs.write_text(self.paths.raw / "issue-12.json", json.dumps({"relationships": {"blockedBy": [10]}}))
        self.fs.write_text(self.paths.raw / "issue-13.json", json.dumps({"relationships": {"blockedBy": [10]}}))
        self.fs.write_text(self.paths.blocked / "12.txt", "prompt 12")
        self.fs.write_text(self.paths.blocked / "13.txt", "prompt 13")

        reporter = CaptureReporter()
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=reporter, paths=self.paths)

        closed10 = self.paths.closed / "10.txt"
        self.fs.write_text(closed10, "done 10")
        watcher.handle_closed(closed10, workers=[])

        opens = sorted(self.fs.list_files(self.paths.open))
        self.assertEqual([self.paths.open / "12.txt", self.paths.open / "13.txt"], opens)

    def test_edges_header_parsing_unlocks(self):
        # edges with header
        self.fs.write_text(self.paths.edges_csv, "from,to\n21,22\n")
        self.fs.write_text(self.paths.raw / "issue-22.json", json.dumps({"relationships": {"blockedBy": [21]}}))
        self.fs.write_text(self.paths.blocked / "22.txt", "prompt 22")

        reporter = CaptureReporter()
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=reporter, paths=self.paths)

        closed21 = self.paths.closed / "21.txt"
        self.fs.write_text(closed21, "done 21")
        watcher.handle_closed(closed21, workers=[])

        self.assertEqual([self.paths.open / "22.txt"], self.fs.list_files(self.paths.open))

    def test_startup_sweep_uses_closed_markers_and_files(self):
        # Setup: 91 blocks 92; 92 blockedBy [91]
        self.fs.write_text(self.paths.edges_csv, "91,92\n")
        self.fs.write_text(self.paths.raw / "issue-92.json", json.dumps({"relationships": {"blockedBy": [91]}}))
        self.fs.write_text(self.paths.blocked / "92.txt", "prompt 92")
        # Create only marker, no closed file
        self.fs.write_text(self.paths.admin_closed / "91.closed", "1")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        # Cold-start sweep should unlock 92
        w.startup_sweep(workers=[])
        self.assertEqual([self.paths.open / "92.txt"], self.fs.list_files(self.paths.open))

        # Now simulate a second dependent 93 blocked by 91 as well; blocked prompt present
        self.fs.append_text(self.paths.edges_csv, "91,93\n")
        self.fs.write_text(self.paths.raw / "issue-93.json", json.dumps({"relationships": {"blockedBy": [91]}}))
        self.fs.write_text(self.paths.blocked / "93.txt", "prompt 93")
        # Also create a closed file for 91 and sweep again (should unlock 93)
        self.fs.write_text(self.paths.closed / "91.txt", "done")
        w.startup_sweep(workers=[])
        opens = sorted(self.fs.list_files(self.paths.open))
        self.assertIn(self.paths.open / "93.txt", opens)

    def test_edges_respects_comments_and_whitespace(self):
        content = """
        # comment line
        \t  101 ,   102  \n
        101,102
        """
        self.fs.write_text(self.paths.edges_csv, content)
        self.fs.write_text(self.paths.raw / "issue-102.json", json.dumps({"relationships": {"blockedBy": [101]}}))
        self.fs.write_text(self.paths.blocked / "102.txt", "prompt 102")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "101.txt"
        self.fs.write_text(c, "done 101")
        w.handle_closed(c, workers=[])
        self.assertEqual([self.paths.open / "102.txt"], self.fs.list_files(self.paths.open))

    def test_cross_wave_blocker_from_prior_wave_unlocks(self):
        # Use wave 2 queue dirs
        wave_paths = make_paths(self.root, wave=2)
        ensure_dirs(self.fs, wave_paths)
        # edges: 99 -> 100 ; 100 is in wave 2; 99 is prior wave and already closed (marker exists)
        self.fs.write_text(wave_paths.edges_csv, "99,100\n")
        self.fs.write_text(wave_paths.raw / "issue-100.json", json.dumps({"relationships": {"blockedBy": [99]}}))
        self.fs.write_text(wave_paths.blocked / "100.txt", "prompt 100")
        # Create admin-wide closed marker for 99 (from previous wave)
        self.fs.write_text(wave_paths.admin_closed / "99.closed", "1")
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=wave_paths)
        # Cold-start sweep should consider admin markers and unlock 100 in this wave
        watcher.startup_sweep(workers=[])
        self.assertEqual([wave_paths.open / "100.txt"], self.fs.list_files(wave_paths.open))

    def test_cross_wave_blocker_not_closed_keeps_blocked(self):
        # Use wave 2 queue dirs
        wave_paths = make_paths(self.root, wave=2)
        ensure_dirs(self.fs, wave_paths)
        # edges: 101 -> 100 ; no marker for 101 so it should remain blocked
        self.fs.write_text(wave_paths.edges_csv, "101,100\n")
        self.fs.write_text(wave_paths.raw / "issue-100.json", json.dumps({"relationships": {"blockedBy": [101]}}))
        self.fs.write_text(wave_paths.blocked / "100.txt", "prompt 100")
        watcher = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=wave_paths)
        watcher.startup_sweep(workers=[])
        self.assertEqual([wave_paths.blocked / "100.txt"], self.fs.list_files(wave_paths.blocked))

    def test_worker_claims_lexicographic_order(self):
        self.fs.write_text(self.paths.open / "100.txt", "x")
        self.fs.write_text(self.paths.open / "2.txt", "x")
        self.fs.write_text(self.paths.open / "10.txt", "x")
        w = Worker(worker_id=1, fs=self.fs, llm=FakeLLM(rc=0), paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)
        # First claim should pick 10.txt (lexicographic: 10 < 100 < 2)
        self.assertTrue(w.run_once())
        closed_names = [p.name for p in self.fs.list_files(self.paths.closed)]
        self.assertEqual(["10.txt"], closed_names)
        # Second claim picks 100.txt
        self.assertTrue(w.run_once())
        closed_names = sorted([p.name for p in self.fs.list_files(self.paths.closed)])
        self.assertIn("100.txt", closed_names)

    def test_move_atomic_failure_on_claim_does_not_crash(self):
        class FailClaimFS(LocalFS):
            def move_atomic(self, src: Path, dst: Path) -> bool:
                # Fail only when moving into claimed dir
                if "claimed" in str(dst):
                    return False
                return super().move_atomic(src, dst)

        fs = FailClaimFS()
        paths = default_paths(self.root)
        ensure_dirs(fs, paths)
        fs.write_text(paths.open / "201.txt", "task")
        w = Worker(worker_id=1, fs=fs, llm=FakeLLM(rc=0), paths=paths, reporter=CaptureReporter(), allowed_issues=None)
        self.assertFalse(w.run_once())  # no claim -> returns False
        # File remains in open/
        self.assertEqual([paths.open / "201.txt"], fs.list_files(paths.open))

    def test_move_atomic_failure_on_route_does_not_crash(self):
        class FailRouteFS(LocalFS):
            def move_atomic(self, src: Path, dst: Path) -> bool:
                # Allow claim from open->claimed, but fail claimed->closed/failed
                if "claimed" in str(src) and ("closed" in str(dst) or "failed" in str(dst)):
                    return False
                return super().move_atomic(src, dst)

        fs = FailRouteFS()
        paths = default_paths(self.root)
        ensure_dirs(fs, paths)
        fs.write_text(paths.open / "202.txt", "task")
        w = Worker(worker_id=1, fs=fs, llm=FakeLLM(rc=0), paths=paths, reporter=CaptureReporter(), allowed_issues=None)
        self.assertTrue(w.run_once())  # claimed and executed
        # File should still exist in claimed since routing failed
        claimed_dir = paths.claimed / "1"
        remaining = fs.list_files(claimed_dir)
        self.assertEqual([claimed_dir / "202.txt"], remaining)

    def test_worker_does_not_claim_when_claimed_has_file(self):
        # Existing claimed file for worker 1
        claimed = self.paths.claimed / "1"
        (claimed).mkdir(parents=True, exist_ok=True)
        self.fs.write_text(claimed / "300.txt", "stuck task")
        # Also an open task present
        self.fs.write_text(self.paths.open / "301.txt", "new task")
        # LLM returns failure so file routes to failed
        w = Worker(worker_id=1, fs=self.fs, llm=FakeLLM(rc=2), paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)
        # First run processes claimed file; should not claim new yet
        self.assertTrue(w.run_once())
        # Claimed directory should now be empty (moved to failed)
        self.assertEqual([], self.fs.list_files(claimed))
        # Open still has the new task because it wasn't claimed yet
        self.assertEqual([self.paths.open / "301.txt"], self.fs.list_files(self.paths.open))
        # Second run now claims the open task
        self.assertTrue(w.run_once())
        self.assertEqual([], self.fs.list_files(self.paths.open))

    def test_reestimate_on_new_attempt_adjusts_timeout(self):
        # Prepare cached estimate for attempt 1
        issue = 501
        est_dir = self.paths.admin / "estimates"
        self.fs.mkdirs(est_dir)
        self.fs.write_text(est_dir / f"{issue}.json", json.dumps({
            "attempt": 1,
            "estimate_sec": 1200,
            "timeout_sec": 2400
        }))
        # One failure already
        attempts = self.paths.admin / "attempts" / f"{issue}.count"
        self.fs.mkdirs(attempts.parent)
        self.fs.write_text(attempts, "1")
        # Open task present
        self.fs.write_text(self.paths.open / f"{issue}.txt", "do work")
        llm = EstimatingLLM(minutes=7)
        w = Worker(worker_id=1, fs=self.fs, llm=llm, paths=self.paths, reporter=CaptureReporter(), allowed_issues=None)
        self.assertTrue(w.run_once())
        # New timeout should be 2x 7m = 14m = 840s (>= min 600)
        self.assertEqual(840, int(llm.last_timeout))
        # Estimate file should be updated to attempt 2
        data = json.loads((self.paths.admin / "estimates" / f"{issue}.json").read_text())
        self.assertEqual(2, data.get("attempt"))
        self.assertEqual(7 * 60, data.get("estimate_sec"))

    def test_case_insensitive_blockedby_key(self):
        self.fs.write_text(self.paths.edges_csv, "301,302\n")
        # use lowercase 'blockedby'
        self.fs.write_text(self.paths.raw / "issue-302.json", json.dumps({"relationships": {"blockedby": [301]}}))
        self.fs.write_text(self.paths.blocked / "302.txt", "prompt 302")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "301.txt"
        self.fs.write_text(c, "done 301")
        w.handle_closed(c, workers=[])
        self.assertEqual([self.paths.open / "302.txt"], self.fs.list_files(self.paths.open))

    def test_unlock_skips_when_open_already_has_prompt(self):
        # edges: 401->402
        self.fs.write_text(self.paths.edges_csv, "401,402\n")
        self.fs.write_text(self.paths.raw / "issue-402.json", json.dumps({"relationships": {"blockedBy": [401]}}))
        # open already has a regenerated prompt; blocked has an older one
        self.fs.write_text(self.paths.open / "402.txt", "newer prompt")
        self.fs.write_text(self.paths.blocked / "402.txt", "older prompt")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "401.txt"
        self.fs.write_text(c, "done 401")
        w.handle_closed(c, workers=[])
        # Ensure we did not clobber the open prompt and the blocked remains (conservative)
        self.assertEqual("newer prompt", (self.paths.open / "402.txt").read_text(encoding="utf-8"))
        self.assertTrue((self.paths.blocked / "402.txt").exists())

    def test_malformed_edges_prevents_unlock_and_does_not_crash(self):
        # Malformed edges: header unrelated and non-integer values
        self.fs.write_text(self.paths.edges_csv, "alpha,beta\nfoo,bar\n")
        # Even if raw says blockedBy, without a usable edges relation nothing should unlock
        self.fs.write_text(self.paths.raw / "issue-41.json", json.dumps({"relationships": {"blockedBy": [40]}}))
        self.fs.write_text(self.paths.blocked / "41.txt", "prompt 41")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "40.txt"
        self.fs.write_text(c, "done 40")
        # Should not crash and should not move 41
        w.handle_closed(c, workers=[])
        self.assertTrue((self.paths.blocked / "41.txt").exists())
        self.assertEqual([], self.fs.list_files(self.paths.open))

    def test_missing_blockedby_in_raw_does_not_unlock(self):
        # edges exist but raw has no blockedBy list
        self.fs.write_text(self.paths.edges_csv, "50,51\n")
        self.fs.write_text(self.paths.raw / "issue-51.json", json.dumps({}))
        self.fs.write_text(self.paths.blocked / "51.txt", "prompt 51")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "50.txt"
        self.fs.write_text(c, "done 50")
        w.handle_closed(c, workers=[])
        self.assertTrue((self.paths.blocked / "51.txt").exists())
        self.assertEqual([], self.fs.list_files(self.paths.open))

    def test_double_close_event_is_idempotent(self):
        self.fs.write_text(self.paths.edges_csv, "60,61\n")
        self.fs.write_text(self.paths.raw / "issue-61.json", json.dumps({"relationships": {"blockedBy": [60]}}))
        self.fs.write_text(self.paths.blocked / "61.txt", "prompt 61")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "60.txt"
        self.fs.write_text(c, "done 60")
        w.handle_closed(c, workers=[])
        # second call should not duplicate or crash
        w.handle_closed(c, workers=[])
        opens = self.fs.list_files(self.paths.open)
        self.assertEqual([self.paths.open / "61.txt"], opens)

    def test_preexisting_closed_marker_still_unlocks(self):
        self.fs.write_text(self.paths.edges_csv, "70,71\n")
        self.fs.write_text(self.paths.raw / "issue-71.json", json.dumps({"relationships": {"blockedBy": [70]}}))
        self.fs.write_text(self.paths.blocked / "71.txt", "prompt 71")
        # Pre-create closed marker for 70
        marker = self.paths.admin_closed / "70.closed"
        self.fs.write_text(marker, "1")
        w = Watcher(fs=self.fs, llm=FakeLLM(), reporter=CaptureReporter(), paths=self.paths)
        c = self.paths.closed / "70.txt"
        self.fs.write_text(c, "done 70")
        w.handle_closed(c, workers=[])
        self.assertEqual([self.paths.open / "71.txt"], self.fs.list_files(self.paths.open))

    def test_missing_codex_treated_as_failure(self):
        # rc=127 simulates missing binary
        self.fs.write_text(self.paths.open / "81.txt", "task body")
        w = Worker(worker_id=1, fs=self.fs, llm=FakeLLM(rc=127), paths=self.paths)
        self.assertTrue(w.run_once())
        failed = self.fs.list_files(self.paths.failed)
        self.assertEqual(1, len(failed))
        txt = failed[0].read_text(encoding="utf-8")
        self.assertIn("## FAILURE:", txt)

    def test_append_failure_does_not_crash_and_still_routes_to_failed(self):
        class AppendFailFS(LocalFS):
            def append_text(self, p: Path, text: str) -> None:
                raise IOError("simulated append failure")

        fs = AppendFailFS()
        paths = default_paths(self.root)
        ensure_dirs(fs, paths)
        fs.write_text(paths.open / "82.txt", "task body")
        w = Worker(worker_id=1, fs=fs, llm=FakeLLM(rc=2), paths=paths)
        # Should not raise
        self.assertTrue(w.run_once())
        self.assertEqual([paths.failed / "82.txt"], fs.list_files(paths.failed))


if __name__ == "__main__":
    unittest.main()
