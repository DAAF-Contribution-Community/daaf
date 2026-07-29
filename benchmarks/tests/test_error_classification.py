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
    classify_tool_failure_class,
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


class ClassifyToolFailureClassTests(unittest.TestCase):
    """C4: additive finer-grained cause tagging for tool failures.

    Covers one case per returned class, the first-match-wins precedence order,
    and both branches of the ChatGPT/Codex lane-pattern rule.
    """

    def test_policy_hook(self):
        self.assertEqual(
            classify_tool_failure_class("BLOCKED by enforce-single-command hook"),
            "policy_hook",
        )

    def test_infra_transient_stream_closed(self):
        self.assertEqual(
            classify_tool_failure_class("API error: stream closed before completion"),
            "infra_transient",
        )

    def test_infra_transient_stalled_mid_stream(self):
        self.assertEqual(
            classify_tool_failure_class("the response stalled mid-stream"),
            "infra_transient",
        )

    def test_infra_transient_empty_200(self):
        self.assertEqual(
            classify_tool_failure_class("received an empty 200 from the backend"),
            "infra_transient",
        )

    def test_capacity_limit_prompt_too_long(self):
        self.assertEqual(
            classify_tool_failure_class("prompt is too long: 250000 tokens"),
            "capacity_limit",
        )

    def test_capacity_limit_quota_429(self):
        self.assertEqual(
            classify_tool_failure_class("HTTP 429 too many requests"),
            "capacity_limit",
        )

    def test_default_model_error(self):
        self.assertEqual(
            classify_tool_failure_class("some entirely novel model behavior"),
            "model_error",
        )

    def test_empty_is_model_error(self):
        self.assertEqual(classify_tool_failure_class(""), "model_error")

    # --- Lane-pattern rule: both branches -----------------------------------

    def test_lane_refusal_matching_id_is_infra_config(self):
        # Rejected id equals the configured child id → an infra/config problem.
        err = "gpt-5.6-sol is not available via the ChatGPT (Codex) lane"
        self.assertEqual(
            classify_tool_failure_class(err, configured_child_model_id="gpt-5.6-sol"),
            "infra_config",
        )

    def test_lane_refusal_mismatched_id_is_model_error(self):
        # A Terra run whose model authored a claude-fable-5 dispatch: the
        # rejected id differs from the configured child → the model mis-routed.
        err = "claude-fable-5 is not available via the ChatGPT (Codex) lane"
        self.assertEqual(
            classify_tool_failure_class(
                err, configured_child_model_id="gpt-5.6-terra"
            ),
            "model_error",
        )

    def test_lane_refusal_no_configured_id_falls_back_to_infra_config(self):
        err = "model-x is not available via the ChatGPT (Codex) lane"
        self.assertEqual(
            classify_tool_failure_class(err, configured_child_model_id=None),
            "infra_config",
        )

    # --- FIX-1 (2026-07-29): delimiter-aware lane id matching --------------
    # A bare substring match misclassified an id-with-extension as the same id.
    # An id counts as "named by the error" only when NOT glued to an
    # id-continuation character (letters/digits/``. _ - [ ]``), so ``[1m]``-style
    # extensions read as a DIFFERENT id → model_error.

    def test_lane_configured_base_vs_rejected_1m_is_model_error(self):
        # Configured bare id; the error rejects the [1m] extension of it. The
        # trailing "[" is an id-continuation char, so the bare id is NOT named →
        # a different id → the model mis-routed → model_error.
        err = "gpt-5.6-terra[1m] is not available via the ChatGPT (Codex) lane"
        self.assertEqual(
            classify_tool_failure_class(
                err, configured_child_model_id="gpt-5.6-terra"
            ),
            "model_error",
        )

    def test_lane_configured_1m_vs_rejected_base_is_model_error(self):
        # Symmetric: configured id carries the [1m] extension, the error rejects
        # the bare slug. The configured id string is not present verbatim → not
        # named → model_error.
        err = "gpt-5.6-terra is not available via the ChatGPT (Codex) lane"
        self.assertEqual(
            classify_tool_failure_class(
                err, configured_child_model_id="gpt-5.6-terra[1m]"
            ),
            "model_error",
        )

    def test_lane_exact_id_match_is_still_infra_config(self):
        # The exact-id case is unchanged: id named verbatim with clean
        # boundaries → the CONFIGURED child was rejected → infra_config.
        err = "gpt-5.6-terra is not available via the ChatGPT (Codex) lane"
        self.assertEqual(
            classify_tool_failure_class(
                err, configured_child_model_id="gpt-5.6-terra"
            ),
            "infra_config",
        )

    # --- FIX-2 (2026-07-29): anchored "429" --------------------------------
    # A bare "429" substring false-matched trace ids and token counts. Only a
    # standalone 429 (or an anchored HTTP-status phrasing) is a capacity signal.

    def test_trace_id_429_is_not_capacity(self):
        # "84290" contains the digits 4-2-9 but not a standalone 429.
        self.assertNotEqual(
            classify_tool_failure_class("request failed on trace-84290fae"),
            "capacity_limit",
        )

    def test_token_count_429_is_not_capacity(self):
        # "4293 tokens" — 429 is glued to a trailing digit, not standalone.
        self.assertNotEqual(
            classify_tool_failure_class("the call consumed 4293 tokens overall"),
            "capacity_limit",
        )

    def test_genuine_http_429_is_capacity(self):
        self.assertEqual(
            classify_tool_failure_class("HTTP 429 Too Many Requests"),
            "capacity_limit",
        )

    # --- FIX-6 (2026-07-29): transient wins over co-reported quota/429 ------

    def test_transient_precedes_co_reported_429(self):
        # A 429 rate-limit note co-occurring with a dropped stream classifies as
        # infra_transient — the transient rule (2) precedes the capacity rule (5),
        # and a stalled stream is the actionable, retryable cause.
        err = "HTTP 429 rate limit; stream closed"
        self.assertEqual(classify_tool_failure_class(err), "infra_transient")

    # --- Precedence (first match wins) --------------------------------------

    def test_policy_hook_precedes_transient(self):
        # A hook block that also mentions a stream-closed phrase still classifies
        # as policy_hook because hook signatures are checked first.
        err = "BLOCKED by bash-safety hook; stream closed"
        self.assertEqual(classify_tool_failure_class(err), "policy_hook")

    def test_transient_precedes_capacity(self):
        # infra_transient is checked before the prompt/quota capacity rules.
        err = "stream closed after prompt is too long warning"
        self.assertEqual(classify_tool_failure_class(err), "infra_transient")

    def test_prompt_capacity_precedes_lane(self):
        # prompt-too-long (rule 3) wins over the lane pattern (rule 4).
        err = (
            "prompt is too long and model is not available via the chatgpt lane"
        )
        self.assertEqual(
            classify_tool_failure_class(err, configured_child_model_id="m"),
            "capacity_limit",
        )

    def test_lane_precedes_quota(self):
        # The lane branch (rule 4) is evaluated before quota/429 (rule 5).
        err = "gpt-5.6-sol is not available via the chatgpt (codex) lane; quota"
        self.assertEqual(
            classify_tool_failure_class(err, configured_child_model_id="gpt-5.6-sol"),
            "infra_config",
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
