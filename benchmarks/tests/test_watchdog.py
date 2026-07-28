"""Deterministic unit tests for the Dispatch B run-lifecycle watchdog.

Exercises the executor's watchdog decision logic WITHOUT launching claude:
each test drives ``_watchdog_wait`` against a real but trivial subprocess
(``python -c "sleep"``) plus injected transcript-lookup functions and an
injected clock (``now_fn``). Decoupling the decision clock (``now_fn``) from the
real poll interval keeps the tests fast: the real ``proc.wait(timeout=poll)``
uses a tiny 0.05s poll while ``now_fn`` fast-forwards elapsed time to cross the
90s / 330s thresholds instantly.

Covers:
  - early-stop confirmation-poll path (requires two consecutive True readings)
  - early-stop scorer-exception catch path (raise -> "not done", never kills)
  - early-stop score_complete_seconds recording (first-hit elapsed, not confirm)
  - stall consecutive-reads path (>330s staleness, two reads)
  - first-activity path (no transcript at all past 90s)
  - transcript-lookup-exception counting (regression != model stall)
  - natural-completion path (process exits on its own -> reason None + stdout)
  - wall-clock timeout backstop
  - no-new-params backward-compat (RunConfig defaults leave the watchdog off)

All scratch lives under benchmarks/tests/ (no /tmp writes).
"""

import subprocess
import sys
import time
import unittest
from pathlib import Path

from benchmarks.harness import executor
from benchmarks.harness.executor import _watchdog_wait, _transcript_recency
from benchmarks.harness.models import RunConfig, TestCase, ModelConfig


SCRATCH = Path(__file__).parent / "_watchdog_scratch"


def _cfg(**overrides):
    """Build a RunConfig with a throwaway test_case/model and watchdog fields."""
    tc = TestCase(id="wd-01", category="x", prompt="p", expected={})
    model = ModelConfig(id="m", name="m")
    base = dict(
        test_case=tc,
        model=model,
        run_index=0,
        watchdog_poll_seconds=0.05,
    )
    base.update(overrides)
    return RunConfig(**base)


def _sleep_proc(seconds=30, prelude=""):
    """Launch a long-running child with piped stdout/stderr.

    ``prelude`` is python printed before the sleep so tests can assert the
    reader threads captured stdout even after the process is killed.
    """
    code = f"{prelude}import time; time.sleep({seconds})"
    return subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class _Clock:
    """Deterministic monotone clock: each call advances by ``step`` seconds."""

    def __init__(self, start, step):
        self.t = start
        self.step = step

    def __call__(self):
        self.t += self.step
        return self.t


class WatchdogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SCRATCH.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        # Track every spawned child so tearDown can close its pipes and reap it,
        # silencing ResourceWarnings from GC-time pipe finalization.
        self._procs = []

    def _spawn(self, *args, **kwargs):
        proc = _sleep_proc(*args, **kwargs)
        self._procs.append(proc)
        return proc

    def tearDown(self):
        for proc in self._procs:
            if proc.poll() is None:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe is not None:
                        pipe.close()
                except OSError:
                    pass
        for p in SCRATCH.glob("*"):
            try:
                p.unlink()
            except OSError:
                pass

    # --- Early stop: confirmation poll required ---

    def test_early_stop_requires_confirmation_poll(self):
        calls = {"n": 0}

        def check(_session_id):
            calls["n"] += 1
            return True  # done from the very first poll

        proc = self._spawn(30, prelude="print('HELLO', flush=True)\n")
        start = 1000.0
        cfg = _cfg(
            early_stop_check=check,
            stall_detection=False,
        )
        # now_fn stays well below the 900s deadline.
        clock = _Clock(start, step=1.0)
        stdout, stderr, reason, diag = _watchdog_wait(
            proc, cfg, "sess", start, timeout=900, now_fn=clock,
        )
        self.assertEqual(reason, "early_stop")
        # Two polls: first sets pending, second confirms.
        self.assertGreaterEqual(calls["n"], 2)
        # Reader thread captured stdout even though the proc was killed.
        self.assertIn("HELLO", stdout)
        self.assertIsNotNone(proc.poll())  # process was terminated

    def test_early_stop_resets_on_intermittent_false(self):
        # True, False, True, True -> must NOT stop until two consecutive Trues.
        seq = iter([True, False, True, True, True, True])

        def check(_s):
            try:
                return next(seq)
            except StopIteration:
                return True

        proc = self._spawn(30)
        start = 0.0
        cfg = _cfg(early_stop_check=check, stall_detection=False)
        clock = _Clock(start, step=1.0)
        _, _, reason, _ = _watchdog_wait(
            proc, cfg, "s", start, timeout=900, now_fn=clock,
        )
        self.assertEqual(reason, "early_stop")

    # --- Stall: consecutive reads over the 330s threshold ---

    def test_stall_consecutive_reads(self):
        # A parent transcript exists but its mtime is far in the past relative to
        # the injected clock, so every poll is a stalled read.
        parent = SCRATCH / "parent.jsonl"
        parent.write_text('{"type":"assistant"}\n')
        old_mtime = 500.0
        import os
        os.utime(parent, (old_mtime, old_mtime))

        def find_parent(_s):
            return parent

        def find_subs(_s):
            return []

        proc = self._spawn(30)
        start = 500.0
        cfg = _cfg(
            stall_detection=True,
            stall_threshold_seconds=330,
            stall_consecutive_reads=2,
            early_stop_check=None,
        )
        # Clock jumps to 500+400=900 on first read (staleness 400 > 330), etc.
        clock = _Clock(start, step=400.0)
        _, _, reason, diag = _watchdog_wait(
            proc, cfg, "s", start, timeout=100000,
            find_parent=find_parent, find_subs=find_subs, now_fn=clock,
        )
        self.assertEqual(reason, "stalled")
        self.assertGreaterEqual(diag["stall_reads"], 2)
        self.assertIsNotNone(proc.poll())

    def test_stall_does_not_fire_on_single_read(self):
        # First read stale, second read fresh -> counter resets, no stall; the
        # process is then reaped by the wall-clock timeout instead.
        parent = SCRATCH / "parent2.jsonl"
        parent.write_text("{}\n")
        import os

        state = {"poll": 0}

        def find_parent(_s):
            # Make the file "fresh" on the 2nd poll by stamping mtime to ~now.
            state["poll"] += 1
            if state["poll"] == 1:
                os.utime(parent, (100.0, 100.0))  # very stale
            else:
                os.utime(parent, (10_000.0, 10_000.0))  # fresh vs clock below
            return parent

        proc = self._spawn(30)
        start = 100.0
        cfg = _cfg(
            stall_detection=True,
            stall_threshold_seconds=330,
            stall_consecutive_reads=2,
        )
        # Clock: poll1 ->  ~600 (staleness 500, stale); poll2 -> ~1100
        # (staleness vs 10000 mtime is negative -> fresh); poll3 crosses deadline.
        clock = _Clock(start, step=500.0)
        _, _, reason, diag = _watchdog_wait(
            proc, cfg, "s", start, timeout=1200,
            find_parent=find_parent, find_subs=lambda _s: [], now_fn=clock,
        )
        self.assertEqual(reason, "timeout")
        self.assertLess(diag["stall_reads"], 2)
        self.assertIsNotNone(proc.poll())

    # --- First-activity: no transcript at all past 90s ---

    def test_first_activity_stall(self):
        proc = self._spawn(30)
        start = 0.0
        cfg = _cfg(
            stall_detection=True,
            stall_first_activity_seconds=90,
            stall_consecutive_reads=2,
        )
        # No transcript ever appears; clock jumps 100s each poll (>90 first-act).
        clock = _Clock(start, step=100.0)
        _, _, reason, diag = _watchdog_wait(
            proc, cfg, "s", start, timeout=100000,
            find_parent=lambda _s: None, find_subs=lambda _s: [], now_fn=clock,
        )
        self.assertEqual(reason, "stalled")
        self.assertGreaterEqual(diag["stall_reads"], 2)

    # --- Natural completion: process exits before any watchdog action ---

    def test_natural_completion_returns_none(self):
        proc = self._spawn(0.15, prelude="print('DONE', flush=True)\n")
        start = time.time()
        cfg = _cfg(stall_detection=True, early_stop_check=None)
        # Fresh transcript so no stall; real clock is fine here.
        parent = SCRATCH / "fresh.jsonl"
        parent.write_text("{}\n")
        stdout, _, reason, _ = _watchdog_wait(
            proc, cfg, "s", start, timeout=900,
            find_parent=lambda _s: parent, find_subs=lambda _s: [],
        )
        self.assertIsNone(reason)
        self.assertIn("DONE", stdout)
        self.assertEqual(proc.poll(), 0)

    # --- Wall-clock timeout backstop ---

    def test_wall_clock_timeout(self):
        proc = self._spawn(30)
        start = 0.0
        cfg = _cfg(stall_detection=False, early_stop_check=None)
        # No stop conditions; clock jumps past the deadline immediately.
        clock = _Clock(start, step=1000.0)
        _, _, reason, _ = _watchdog_wait(
            proc, cfg, "s", start, timeout=900, now_fn=clock,
        )
        self.assertEqual(reason, "timeout")
        self.assertIsNotNone(proc.poll())

    # --- Backward compatibility: defaults leave the watchdog off ---

    def test_defaults_disable_watchdog(self):
        cfg = _cfg()
        self.assertFalse(cfg.stall_detection)
        self.assertIsNone(cfg.early_stop_check)
        # execute_run gates the watchdog on exactly this predicate.
        watchdog_active = cfg.stall_detection or cfg.early_stop_check is not None
        self.assertFalse(watchdog_active)

    # --- Recency helper aggregates parent + subagent mtimes ---

    def test_transcript_recency_aggregates_max(self):
        import os
        parent = SCRATCH / "p.jsonl"
        sub = SCRATCH / "s.jsonl"
        parent.write_text("{}\n")
        sub.write_text("{}\n")
        os.utime(parent, (100.0, 100.0))
        os.utime(sub, (9000.0, 9000.0))  # subagent more recent
        latest, parent_exists, lookup_errors = _transcript_recency(
            "sess", lambda _s: parent, lambda _s: [sub]
        )
        self.assertTrue(parent_exists)
        self.assertEqual(latest, 9000.0)
        self.assertEqual(lookup_errors, 0)

    def test_transcript_recency_counts_lookup_exceptions(self):
        # A lookup FUNCTION raising (not a merely-absent transcript) is a
        # monitoring regression: it must be counted, not silently treated as a
        # model stall. Both the parent and subagent lookups raise here.
        def boom_parent(_s):
            raise RuntimeError("parent lookup exploded")

        def boom_subs(_s):
            raise RuntimeError("subagent lookup exploded")

        latest, parent_exists, lookup_errors = _transcript_recency(
            "sess", boom_parent, boom_subs
        )
        self.assertIsNone(latest)
        self.assertFalse(parent_exists)
        self.assertEqual(lookup_errors, 2)

    # --- Early stop: scorer exception is caught, run is not killed ---

    def test_early_stop_check_exception_is_caught(self):
        # early_stop_check raising must be swallowed as "not done" (never kills
        # the run); the process is then reaped by the wall-clock backstop.
        def boom(_s):
            raise RuntimeError("scorer exploded")

        proc = self._spawn(30)
        start = 0.0
        cfg = _cfg(early_stop_check=boom, stall_detection=False)
        # Clock crosses the deadline after a couple of (exception-swallowing) polls.
        clock = _Clock(start, step=500.0)
        _, _, reason, diag = _watchdog_wait(
            proc, cfg, "s", start, timeout=900, now_fn=clock,
        )
        self.assertEqual(reason, "timeout")
        self.assertIsNone(diag["score_complete_seconds"])
        self.assertIsNotNone(proc.poll())

    # --- Early stop: score_complete_seconds is recorded on the early-stop path ---

    def test_early_stop_records_score_complete_seconds(self):
        # early_stop_check returns True from the first poll; score_complete_seconds
        # must capture the elapsed time at that FIRST hit (not the confirmation
        # poll). With start=1000 and a step=1.0 clock, the first now_fn() call is
        # 1001.0, so the recorded value is 1.0.
        def check(_s):
            return True

        proc = self._spawn(30)
        start = 1000.0
        cfg = _cfg(early_stop_check=check, stall_detection=False)
        clock = _Clock(start, step=1.0)
        _, _, reason, diag = _watchdog_wait(
            proc, cfg, "s", start, timeout=900, now_fn=clock,
        )
        self.assertEqual(reason, "early_stop")
        self.assertEqual(diag["score_complete_seconds"], 1.0)


if __name__ == "__main__":
    unittest.main()
