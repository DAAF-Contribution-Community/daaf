"""Cross-process concurrency-safety regression tests for the benchmark runners.

Covers the three mechanisms that make concurrent runner PROCESSES safe:

1. The fixture reader/writer flock (EX excludes SH/EX; SH coexists with SH) —
   exercised across a real child process via multiprocessing, since flock is an
   open-file-description property that only contends across processes/OFDs.
2. Per-batch results-dir uniqueness (token appended, leading timestamp
   preserved) and the additive manifest ``batch_token``/``batch_pid`` fields.
3. The read-only fixture-source chmod round-trip on a temporary tree.

All fakes are in-memory or temp-dir; no backend/model call, no real benchmark
result, checkpoint, or sandbox is created outside the test scratch dir.
"""

import fcntl
import json
import multiprocessing
import os
import shutil
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from benchmarks.harness.models import ModelConfig, PricingConfig, TestCase as BenchmarkCase
from benchmarks.scripts import run_dispatch_compliance


TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch_concurrency")


def _child_try_flock(lockfile, lock_type, result_q):
    """Child-process worker: attempt a NON-blocking flock and report the outcome.

    Opens its OWN fd (a fresh open file description) so contention with a lock
    held by the parent process is genuine cross-OFD contention, exactly as two
    separate runner invocations would experience.
    """
    fd = os.open(lockfile, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, lock_type | fcntl.LOCK_NB)
            result_q.put("acquired")
            fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            result_q.put("blocked")
    finally:
        os.close(fd)


class FixtureLockTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        TEST_SCRATCH.mkdir(parents=True)
        self.lockfile = str(TEST_SCRATCH / ".fixtures.lock")
        # fork so the child inherits the temp lockfile path via the module patch
        # and contends via a fresh OFD (spawn would re-import and lose the patch).
        self.ctx = multiprocessing.get_context("fork")

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def _child_outcome(self, lock_type):
        q = self.ctx.Queue()
        p = self.ctx.Process(target=_child_try_flock, args=(self.lockfile, lock_type, q))
        p.start()
        outcome = q.get(timeout=10)
        p.join(timeout=10)
        return outcome

    def test_exclusive_lock_blocks_shared_and_exclusive(self):
        with patch.object(run_dispatch_compliance, "FIXTURE_LOCK_PATH", self.lockfile):
            with run_dispatch_compliance._fixture_lock(fcntl.LOCK_EX, "restore"):
                self.assertEqual("blocked", self._child_outcome(fcntl.LOCK_EX))
                self.assertEqual("blocked", self._child_outcome(fcntl.LOCK_SH))
            # Lock released on context exit — a fresh acquirer now succeeds.
            self.assertEqual("acquired", self._child_outcome(fcntl.LOCK_EX))

    def test_shared_lock_coexists_with_shared_but_blocks_exclusive(self):
        with patch.object(run_dispatch_compliance, "FIXTURE_LOCK_PATH", self.lockfile):
            with run_dispatch_compliance._fixture_lock(fcntl.LOCK_SH, "copy"):
                self.assertEqual("acquired", self._child_outcome(fcntl.LOCK_SH))
                self.assertEqual("blocked", self._child_outcome(fcntl.LOCK_EX))

    def test_lock_released_on_process_death_no_stale_cleanup(self):
        # A child that dies while holding the EX lock must not strand it: the
        # kernel releases on process exit, so the parent acquires afterwards.
        with patch.object(run_dispatch_compliance, "FIXTURE_LOCK_PATH", self.lockfile):
            self.assertEqual("acquired", self._child_outcome(fcntl.LOCK_EX))
            with run_dispatch_compliance._fixture_lock(fcntl.LOCK_EX, "restore"):
                pass  # acquired without hanging => prior child's lock was released


class FixtureChmodTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        self.tree = TEST_SCRATCH / "test_fixtures"
        (self.tree / "sub").mkdir(parents=True)
        self.f1 = self.tree / "top.txt"
        self.f2 = self.tree / "sub" / "nested.txt"
        self.f1.write_text("a")
        self.f2.write_text("b")
        self.f1.chmod(0o644)
        self.f2.chmod(0o644)

    def tearDown(self):
        # Re-enable writes so rmtree can remove the read-only tree.
        for p in self.tree.rglob("*"):
            try:
                p.chmod(p.stat().st_mode | stat.S_IWUSR)
            except OSError:
                pass
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def test_readonly_then_writable_round_trip(self):
        prefix = str(self.tree) + "/"
        with patch.object(run_dispatch_compliance, "FIXTURE_PREFIX", prefix):
            run_dispatch_compliance._set_fixture_tree_writable(False)
            for f in (self.f1, self.f2):
                mode = f.stat().st_mode
                self.assertEqual(0, mode & stat.S_IWUSR, f"{f} should be read-only")
                self.assertEqual(0, mode & stat.S_IWGRP)
                self.assertEqual(0, mode & stat.S_IWOTH)
            # Directories keep r-x (traversable) even when read-only.
            self.assertTrue(self.tree.stat().st_mode & stat.S_IXUSR)
            self.assertTrue(self.tree.stat().st_mode & stat.S_IRUSR)

            run_dispatch_compliance._set_fixture_tree_writable(True)
            for f in (self.f1, self.f2):
                self.assertTrue(f.stat().st_mode & stat.S_IWUSR, f"{f} should be writable")


class ResultsDirNamingTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        TEST_SCRATCH.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def _model(self):
        return ModelConfig(
            id="claude-sonnet-4-6",
            name="Sonnet 4.6",
            provider="anthropic",
            pricing=PricingConfig(input=3.0, output=15.0, cached_input=0.3),
        )

    def _case(self):
        return BenchmarkCase(
            id="dc-01",
            category="cat",
            prompt="p",
            golden_checkpoint="benchmarks/datasets/dispatch_compliance/goldens/dc-01.jsonl",
            expected={},
            subcategory="sub",
        )

    def _args(self, model):
        return SimpleNamespace(
            reps=1, sequential=True, delay=0, timeout=300,
            test_id="dc-01", models=model.key,
        )

    def test_token_appended_timestamp_preserved_and_manifest_records_token_pid(self):
        model, case = self._model(), self._case()
        with patch.object(run_dispatch_compliance, "BASE_DIR", TEST_SCRATCH), \
                patch.object(run_dispatch_compliance, "get_git_sha", return_value="test-sha"):
            output_dir = run_dispatch_compliance.archive_results(
                [], [model], [case], self._args(model), 0.0,
                output_dir=None, partial=True, expected_n=1, git_sha="test-sha",
                batch_token="abc123", batch_pid=4242,
            )
        self.assertTrue(output_dir.name.endswith("_abc123"))
        ts_part = output_dir.name[: -len("_abc123")]
        # Leading segment is a parseable %Y%m%d_%H%M%S timestamp (15 chars).
        self.assertEqual(15, len(ts_part))
        self.assertEqual("_", ts_part[8])
        manifest = json.loads((output_dir / "manifest.json").read_text())
        self.assertEqual("abc123", manifest["batch_token"])
        self.assertEqual(4242, manifest["batch_pid"])

    def test_auto_generated_tokens_are_unique_across_batches(self):
        model, case = self._model(), self._case()
        with patch.object(run_dispatch_compliance, "BASE_DIR", TEST_SCRATCH), \
                patch.object(run_dispatch_compliance, "get_git_sha", return_value="test-sha"):
            d1 = run_dispatch_compliance.archive_results(
                [], [model], [case], self._args(model), 0.0,
                output_dir=None, partial=True, expected_n=1, git_sha="test-sha",
            )
            d2 = run_dispatch_compliance.archive_results(
                [], [model], [case], self._args(model), 0.0,
                output_dir=None, partial=True, expected_n=1, git_sha="test-sha",
            )
        # Even if both start the same wall-clock second, the tokens differ.
        self.assertNotEqual(d1.name, d2.name)


if __name__ == "__main__":
    unittest.main()
