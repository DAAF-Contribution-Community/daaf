"""Tests for the error-bearing tool-result classifier and its runner wiring.

Covers:
  * Fix 4 / I2 (2026-07-28) compute_error_counts single-count property: with an
    empty ``tool_failures`` list, a parent transcript is scanned exactly once —
    no double-counting against the legacy tool_failures-derived path.
  * I3 truncation-reclassification: the transcript scan sees FULL, untruncated
    content, so a failure signature living past char 500 (which the legacy
    500-char-truncated result.tool_failures path would have missed) is now
    classified into its named bucket instead of ``unclassified``.
  * W1 (2026-07-28) parent_skip_lines: the parent scan skips the prepended
    golden-checkpoint prefix, mirroring extract_new_tool_calls's slice.
  * Fix 1 fallback invariant: every golden checkpoint under benchmarks/golden/
    carries ZERO is_error tool_results, so the checkpoint prefix can never
    contribute spurious error counts (the safety net for the runners that do
    not thread the boundary line count).

No backend/model call. All scratch lives under benchmarks/.
"""

import json
import shutil
import unittest
from pathlib import Path

from benchmarks.scorers.deterministic.error_classification import (
    classify_error_content,
    compute_error_counts,
)

TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch_error_classification")
GOLDEN_ROOT = Path("/daaf/benchmarks/golden")


def _error_line(tool_use_id: str, content: str) -> str:
    """One JSONL user record carrying a single is_error tool_result."""
    return json.dumps({
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "is_error": True,
                    "content": content,
                }
            ]
        },
    })


def _plain_line(text: str) -> str:
    """A non-tool-result record (no is_error), for prefix/padding lines."""
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}
    ]}})


class ClassifyContentTests(unittest.TestCase):
    def test_hook_block_wins_over_failure(self):
        # A blocked call reports as an error but is the framework acting as
        # designed; hook signatures are checked first.
        self.assertEqual(
            classify_error_content("BLOCKED by enforce-single-command hook"),
            "hook_block",
        )

    def test_genuine_failure_signature(self):
        self.assertEqual(
            classify_error_content("Error: no such file or directory"),
            "tool_failure",
        )

    def test_unrecognized_is_unclassified(self):
        self.assertEqual(
            classify_error_content("something totally novel"),
            "tool_failure_unclassified",
        )


class SingleCountPropertyTests(unittest.TestCase):
    def setUp(self):
        TEST_SCRATCH.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if TEST_SCRATCH.exists():
            shutil.rmtree(TEST_SCRATCH)

    def test_parent_scanned_once_with_empty_tool_failures(self):
        tpath = TEST_SCRATCH / "transcript.jsonl"
        with open(tpath, "w") as f:
            f.write(_error_line("tu1", "no such file or directory") + "\n")
            f.write(_error_line("tu2", "BLOCKED by bash-safety hook") + "\n")
        counts = compute_error_counts([], parent_transcript=str(tpath))
        # Exactly two errors, counted once each — no double count.
        self.assertEqual(counts["tool_failures"], 1)
        self.assertEqual(counts["hook_blocks"], 1)
        self.assertEqual(counts["tool_failures_unclassified"], 0)

    def test_empty_everything_is_all_zero(self):
        counts = compute_error_counts([])
        self.assertEqual(
            counts,
            {"hook_blocks": 0, "tool_failures": 0, "tool_failures_unclassified": 0},
        )


class TruncationReclassificationTests(unittest.TestCase):
    def setUp(self):
        TEST_SCRATCH.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if TEST_SCRATCH.exists():
            shutil.rmtree(TEST_SCRATCH)

    def test_signature_past_char_500_now_classified(self):
        # Legacy result.tool_failures truncated content to 500 chars; a
        # signature living beyond that boundary was invisible and the error
        # landed in 'unclassified'. The transcript scan sees the full string.
        content = ("x" * 600) + " no such file or directory"
        # Demonstrate the legacy-vs-full divergence directly on the classifier.
        self.assertEqual(
            classify_error_content(content[:500]), "tool_failure_unclassified"
        )
        self.assertEqual(classify_error_content(content), "tool_failure")
        # And through the full transcript scan the run is a tool_failure.
        tpath = TEST_SCRATCH / "transcript.jsonl"
        with open(tpath, "w") as f:
            f.write(_error_line("tu1", content) + "\n")
        counts = compute_error_counts([], parent_transcript=str(tpath))
        self.assertEqual(counts["tool_failures"], 1)
        self.assertEqual(counts["tool_failures_unclassified"], 0)


class ParentSkipLinesTests(unittest.TestCase):
    def setUp(self):
        TEST_SCRATCH.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if TEST_SCRATCH.exists():
            shutil.rmtree(TEST_SCRATCH)

    def test_checkpoint_prefix_errors_are_skipped(self):
        tpath = TEST_SCRATCH / "transcript.jsonl"
        with open(tpath, "w") as f:
            # 3-line golden prefix, one of which (defensively) carries an error.
            f.write(_plain_line("golden line 1") + "\n")
            f.write(_error_line("tu0", "no such file or directory") + "\n")
            f.write(_plain_line("golden line 3") + "\n")
            # Post-checkpoint benchmark run.
            f.write(_error_line("tu1", "BLOCKED by bash-safety hook") + "\n")
        # Skipping the 3-line prefix drops the prefix error; only the
        # post-checkpoint hook_block remains.
        counts = compute_error_counts(
            [], parent_transcript=str(tpath), parent_skip_lines=3
        )
        self.assertEqual(counts["hook_blocks"], 1)
        self.assertEqual(counts["tool_failures"], 0)
        # With skip=0 the prefix error is (wrongly, absent the boundary) counted.
        counts0 = compute_error_counts([], parent_transcript=str(tpath))
        self.assertEqual(counts0["tool_failures"], 1)


class GoldensErrorFreeInvariantTests(unittest.TestCase):
    """Fix 1 fallback: goldens must contain zero is_error tool_results.

    This is the safety net for the runners that do NOT thread the checkpoint
    boundary into the error scan (post_confirmation, mode_classification): if
    every golden prefix is error-free, scanning it contributes nothing to the
    counts regardless of parent_skip_lines.
    """

    def test_all_goldens_have_zero_error_tool_results(self):
        goldens = sorted(GOLDEN_ROOT.rglob("*.jsonl"))
        self.assertTrue(goldens, f"no golden .jsonl files found under {GOLDEN_ROOT}")
        offenders = []
        for g in goldens:
            counts = compute_error_counts([], parent_transcript=str(g))
            total = (
                counts["hook_blocks"]
                + counts["tool_failures"]
                + counts["tool_failures_unclassified"]
            )
            if total:
                offenders.append((str(g), total))
        self.assertEqual(
            offenders, [],
            f"golden checkpoints with is_error tool_results: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
