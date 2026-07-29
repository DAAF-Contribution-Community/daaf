"""Regression tests for the 2026-07-28 dispatch-compliance heading normalization.

Covers Fix 1 (structural section-heading matching) and Fix 3 (shell-safe
sandbox slugs). No backend/model call; all scratch lives under benchmarks/.

Key properties asserted:
  * Strict widening: every label the LEGACY exact-match lists accepted still
    passes under the new structural matcher (task / context / instructions).
  * The archived-observed synonym "## Output format" (lowercase f) now passes.
  * Additional real-world synonyms pass (## Return format, ## Output
    requirements, ## Review expectations, ## Investigation requirements).
  * End-to-end: score_dispatch_compliance emits the three section criteria as
    PASS for a structurally-sound prompt and FAIL when the section is absent.
  * sandbox_slug renders shell-hostile display names safe.
"""

import json
import unittest
from pathlib import Path

from types import SimpleNamespace

from benchmarks.harness.artifacts import (
    assert_unique_sandbox_slugs,
    sandbox_slug,
)
from benchmarks.scorers.deterministic.dispatch_compliance import (
    CONTEXT_KEYWORDS,
    INSTRUCTION_KEYWORDS,
    TASK_KEYWORDS,
    extract_normalized_headings,
    match_section_heading,
    score_dispatch_compliance,
)

TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch_heading_norm")

# The exact-match label lists the scorer used BEFORE the fix. Every one of
# these must still pass under the new structural matcher (strict-widening
# property). Kept here verbatim as the frozen legacy contract.
LEGACY_TASK_LABEL = "## Task"
LEGACY_CONTEXT_HEADERS = [
    "## Context", "## Scope", "## Background", "## Specifications",
    "## Dataset Specifications", "## Known Symptoms", "## What to Search",
]
LEGACY_INSTRUCTION_HEADERS = [
    "## Instructions", "## What to Report", "## What to Look For",
    "## Where to Look", "## Validation Requirements", "## Output Format",
    "## Expected Output", "## Deliverables",
]


class HeadingExtractionTests(unittest.TestCase):
    def test_atx_headings_extracted_and_normalized(self):
        text = "# Task\nsome body\n### Context\n#### Deliverables\n"
        self.assertEqual(
            extract_normalized_headings(text),
            ["task", "context", "deliverables"],
        )

    def test_bold_label_headings_extracted(self):
        text = "**Task**\nbody\n**Context:**\n"
        self.assertEqual(
            extract_normalized_headings(text), ["task", "context:"]
        )

    def test_non_heading_lines_ignored(self):
        text = "regular prose mentioning Task and Context inline\nno headings\n"
        self.assertEqual(extract_normalized_headings(text), [])


class StrictWideningTests(unittest.TestCase):
    """Every legacy-accepted label must still pass under structural matching."""

    def test_legacy_task_label_still_passes(self):
        headings = extract_normalized_headings(LEGACY_TASK_LABEL + "\n")
        self.assertIsNotNone(
            match_section_heading(headings, TASK_KEYWORDS, word_boundary=True)
        )

    def test_all_legacy_context_headers_still_pass(self):
        for header in LEGACY_CONTEXT_HEADERS:
            headings = extract_normalized_headings(header + "\n")
            self.assertIsNotNone(
                match_section_heading(headings, CONTEXT_KEYWORDS),
                f"legacy context header regressed: {header!r}",
            )

    def test_all_legacy_instruction_headers_still_pass(self):
        for header in LEGACY_INSTRUCTION_HEADERS:
            headings = extract_normalized_headings(header + "\n")
            self.assertIsNotNone(
                match_section_heading(headings, INSTRUCTION_KEYWORDS),
                f"legacy instruction header regressed: {header!r}",
            )


class SynonymWideningTests(unittest.TestCase):
    """Archived-observed synonyms that FAILED under exact matching now pass."""

    def test_output_format_lowercase_f_now_passes(self):
        # The headline archived failure: "## Output format" (lowercase f) failed
        # the case-sensitive "## Output Format" check on 42/136 GPT prompts.
        headings = extract_normalized_headings("## Output format\n")
        self.assertIsNotNone(
            match_section_heading(headings, INSTRUCTION_KEYWORDS)
        )

    def test_additional_instruction_synonyms_pass(self):
        for header in [
            "## Output requirements", "## Return format",
            "## Investigation requirements", "## Review expectations",
        ]:
            headings = extract_normalized_headings(header + "\n")
            self.assertIsNotNone(
                match_section_heading(headings, INSTRUCTION_KEYWORDS),
                f"synonym should pass: {header!r}",
            )

    def test_task_variants_pass(self):
        for header in ["## Tasks", "## Task Description", "## Your task"]:
            headings = extract_normalized_headings(header + "\n")
            self.assertIsNotNone(
                match_section_heading(headings, TASK_KEYWORDS, word_boundary=True),
                f"task variant should pass: {header!r}",
            )


class RequestKeywordTests(unittest.TestCase):
    """Fix 3 (2026-07-28): '## User Request' must satisfy the TASK concept.

    The GPT diagnostic cited '## User Request' as a near-miss that failed the
    task check under the 'task'-only keyword set. The other cited near-misses
    are pinned here too as named cases documenting current semantics.
    """

    def test_user_request_heading_passes_task(self):
        headings = extract_normalized_headings("## User Request\n")
        self.assertIsNotNone(
            match_section_heading(headings, TASK_KEYWORDS, word_boundary=True),
            "'## User Request' should satisfy the TASK concept",
        )

    def test_request_variants_pass_task(self):
        for header in ["## Request", "## Requests", "## User request"]:
            headings = extract_normalized_headings(header + "\n")
            self.assertIsNotNone(
                match_section_heading(headings, TASK_KEYWORDS, word_boundary=True),
                f"request variant should pass task: {header!r}",
            )

    def test_required_scope_passes_context(self):
        # '## Required scope' matches CONTEXT via the 'scope' substring keyword.
        headings = extract_normalized_headings("## Required scope\n")
        self.assertIsNotNone(
            match_section_heading(headings, CONTEXT_KEYWORDS),
            "'## Required scope' should satisfy the CONTEXT concept",
        )

    def test_evidence_and_output_format_passes_instructions(self):
        # '## Evidence and Output Format' matches INSTRUCTIONS via 'output'.
        headings = extract_normalized_headings("## Evidence and Output Format\n")
        self.assertIsNotNone(
            match_section_heading(headings, INSTRUCTION_KEYWORDS),
            "'## Evidence and Output Format' should satisfy the INSTRUCTIONS concept",
        )

    def test_prose_requirements_colon_is_not_a_heading(self):
        # Documents current semantics (NOT a change): a bare prose line
        # 'Requirements:' is neither an ATX (#) nor a bold (**) heading, so
        # extract_normalized_headings ignores it and it does not, on its own,
        # satisfy the INSTRUCTIONS concept. The 'requirement' keyword only helps
        # when it appears in an actual heading (e.g. '## Validation Requirements').
        headings = extract_normalized_headings("Requirements:\nsome prose\n")
        self.assertEqual(headings, [])
        self.assertIsNone(
            match_section_heading(headings, INSTRUCTION_KEYWORDS)
        )


def _write_transcript(path: Path, prompt: str, subagent_type: str) -> None:
    """Write a minimal 2-line transcript: an Agent tool_use + a success result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    assistant = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu1",
                    "name": "Agent",
                    "input": {
                        "subagent_type": subagent_type,
                        "prompt": prompt,
                        "description": "d",
                    },
                }
            ]
        },
    }
    user = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "tu1", "is_error": False}
            ]
        },
    }
    with open(path, "w") as f:
        f.write(json.dumps(assistant) + "\n")
        f.write(json.dumps(user) + "\n")


class EndToEndScorerTests(unittest.TestCase):
    def setUp(self):
        TEST_SCRATCH.mkdir(parents=True, exist_ok=True)
        self.expected = {
            "subagent_dispatched": "research-executor",
            "prompt_contains": [],
            "prompt_contains_any": [],
        }

    def tearDown(self):
        import shutil
        if TEST_SCRATCH.exists():
            shutil.rmtree(TEST_SCRATCH)

    def _section_passes(self, prompt: str) -> dict:
        tpath = TEST_SCRATCH / "transcript.jsonl"
        _write_transcript(tpath, prompt, "research-executor")
        results = score_dispatch_compliance(str(tpath), 0, self.expected)
        return {c.name: c.passed for c in results}

    def test_synonym_prompt_passes_all_three_section_criteria(self):
        # A GPT-style prompt that FAILED the old exact-label matcher.
        prompt = (
            "## Your task\nDo the thing.\n\n"
            "## Scope\nThe boundaries.\n\n"
            "## Output format\nReturn a table.\n"
        )
        passes = self._section_passes(prompt)
        self.assertTrue(passes["prompt_has_task_section"])
        self.assertTrue(passes["prompt_has_context_section"])
        self.assertTrue(passes["prompt_has_instructions"])

    def test_canonical_prompt_still_passes(self):
        prompt = (
            "## Task\nDo it.\n\n## Context\nHere.\n\n## Instructions\nSteps.\n"
        )
        passes = self._section_passes(prompt)
        self.assertTrue(passes["prompt_has_task_section"])
        self.assertTrue(passes["prompt_has_context_section"])
        self.assertTrue(passes["prompt_has_instructions"])

    def test_missing_sections_fail(self):
        prompt = "just some prose with no markdown headings at all\n"
        passes = self._section_passes(prompt)
        self.assertFalse(passes["prompt_has_task_section"])
        self.assertFalse(passes["prompt_has_context_section"])
        self.assertFalse(passes["prompt_has_instructions"])

    def test_legacy_label_not_at_heading_position_still_passes(self):
        # Strict-widening guarantee: the old matcher used substring-anywhere,
        # so a legacy label appearing NOT as a line-start heading (e.g. inside
        # an indented block) passed. The new matcher ORs in the legacy
        # substring check so such prompts never regress P->F.
        prompt = (
            "## Task\ndo it\n"
            "## Context\nhere\n"
            "        ## Instructions (deeply indented, not a heading line)\n"
        )
        passes = self._section_passes(prompt)
        self.assertTrue(passes["prompt_has_task_section"])
        self.assertTrue(passes["prompt_has_context_section"])
        self.assertTrue(passes["prompt_has_instructions"])


def _write_no_dispatch_transcript(path: Path) -> None:
    """Write a transcript with tool activity but NO Agent tool_use (zero dispatch).

    Uses a non-Agent tool (Read) so extract_new_tool_calls yields a non-empty
    tool_calls list while extract_agent_calls yields none — the exact shape of a
    run that did work but never dispatched a subagent.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    assistant = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Looking now."},
                {
                    "type": "tool_use",
                    "id": "tu1",
                    "name": "Read",
                    "input": {"file_path": "/daaf/x"},
                },
            ]
        },
    }
    user = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "tu1", "is_error": False}
            ]
        },
    }
    with open(path, "w") as f:
        f.write(json.dumps(assistant) + "\n")
        f.write(json.dumps(user) + "\n")


def _write_failed_dispatch_transcript(path: Path, prompt: str, subagent_type: str) -> None:
    """Write an Agent tool_use whose tool_result is_error=True (recorded failure)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    assistant = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu1",
                    "name": "Agent",
                    "input": {
                        "subagent_type": subagent_type,
                        "prompt": prompt,
                        "description": "d",
                    },
                }
            ]
        },
    }
    user = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "tu1", "is_error": True}
            ]
        },
    }
    with open(path, "w") as f:
        f.write(json.dumps(assistant) + "\n")
        f.write(json.dumps(user) + "\n")


class DispatchAttemptGateTests(unittest.TestCase):
    """2026-07-29: the prompt_* family requires a dispatch ATTEMPT.

    A zero-dispatch run must FAIL all eight prompt criteria rather than banking
    the three that historically auto-passed on vacuous truth (prompt_has_project_dir
    for read-only agents, the 0-required prompt_contains_required, and the
    unspecified prompt_contains_any). Observed: 2 GPT-5.6 Sol dc-06 runs scored
    3/10 with zero Agent calls.
    """

    PROMPT_CRITERIA = (
        "prompt_has_base_dir", "prompt_has_mode_marker", "prompt_has_project_dir",
        "prompt_has_task_section", "prompt_has_context_section",
        "prompt_has_instructions", "prompt_contains_required",
        "prompt_contains_any",
    )
    GATE_DETAIL = "No Agent dispatch attempt; prompt criteria not evaluable."

    def setUp(self):
        TEST_SCRATCH.mkdir(parents=True, exist_ok=True)
        # dc-06-shaped expected: a read-only agent + zero required strings — the
        # exact shape whose three prompt criteria previously auto-passed.
        self.expected = {
            "subagent_dispatched": "search-agent",
            "prompt_contains": [],
            "prompt_contains_any": [],
        }

    def tearDown(self):
        import shutil
        if TEST_SCRATCH.exists():
            shutil.rmtree(TEST_SCRATCH)

    def test_no_dispatch_fails_all_prompt_criteria(self):
        tpath = TEST_SCRATCH / "transcript.jsonl"
        _write_no_dispatch_transcript(tpath)
        results = score_dispatch_compliance(str(tpath), 0, self.expected)
        by_name = {c.name: c for c in results}
        # tier1 unaffected: no successful dispatch.
        self.assertFalse(by_name["agent_dispatched"].passed)
        self.assertFalse(by_name["correct_subagent_type"].passed)
        # Every prompt_* criterion FAILS with the gate detail (previously 3
        # auto-passed on vacuous truth).
        for name in self.PROMPT_CRITERIA:
            self.assertIn(name, by_name)
            self.assertFalse(
                by_name[name].passed, f"{name} must fail with no dispatch attempt"
            )
            self.assertEqual(by_name[name].detail, self.GATE_DETAIL)
        # Full criterion set preserved (2 tier1 + 8 tier2), names + order intact.
        self.assertEqual([c.name for c in results][2:], list(self.PROMPT_CRITERIA))
        self.assertEqual(len(results), 10)

    def test_dispatched_run_behavior_unchanged(self):
        # A well-formed dispatched prompt still scores its prompt_* criteria under
        # normal semantics — the gate does not fire when a dispatch exists.
        tpath = TEST_SCRATCH / "transcript.jsonl"
        prompt = (
            "BASE_DIR context. Ad Hoc mode. PROJECT_DIR set.\n"
            "## Task\nDo it.\n## Context\nHere.\n## Instructions\nSteps.\n"
        )
        _write_transcript(tpath, prompt, "search-agent")
        results = score_dispatch_compliance(str(tpath), 0, self.expected)
        passes = {c.name: c.passed for c in results}
        self.assertTrue(passes["agent_dispatched"])
        self.assertTrue(passes["correct_subagent_type"])
        self.assertTrue(passes["prompt_has_base_dir"])
        self.assertTrue(passes["prompt_has_mode_marker"])
        self.assertTrue(passes["prompt_has_task_section"])
        self.assertTrue(passes["prompt_has_context_section"])
        self.assertTrue(passes["prompt_has_instructions"])
        # read-only agent: project_dir auto-passes under its OWN semantics; the
        # 0-required / unspecified checks pass under theirs. All unchanged.
        self.assertTrue(passes["prompt_has_project_dir"])
        self.assertTrue(passes["prompt_contains_required"])
        self.assertTrue(passes["prompt_contains_any"])

    def test_failed_only_dispatch_is_an_attempt(self):
        # A RECORDED failed Agent call is an attempt: prompt criteria are
        # evaluated under normal semantics (gate does NOT fire), even though
        # agent_dispatched fails because no call succeeded.
        tpath = TEST_SCRATCH / "transcript.jsonl"
        _write_failed_dispatch_transcript(tpath, "## Task\nx\n", "search-agent")
        results = score_dispatch_compliance(str(tpath), 0, self.expected)
        by_name = {c.name: c for c in results}
        self.assertFalse(by_name["agent_dispatched"].passed)
        for name in self.PROMPT_CRITERIA:
            self.assertNotEqual(
                by_name[name].detail, self.GATE_DETAIL,
                f"{name} should be evaluated (failed dispatch is an attempt)",
            )


def _write_subagent_recovery_fixture(sub_path: Path, prompt: str, agent_type: str) -> None:
    """Write a subagent transcript + sibling meta.json shaped like real recovery
    evidence (see dispatch_compliance.recover_agent_calls_from_subagent_transcripts).

    The transcript's FIRST record is a type "user" record whose
    ``message.content`` is a PLAIN STRING carrying the dispatched prompt; the
    sibling ``agent-{id}.meta.json`` supplies ``agentType``.
    """
    sub_path.parent.mkdir(parents=True, exist_ok=True)
    first_user = {"type": "user", "message": {"content": prompt}}
    with open(sub_path, "w") as f:
        f.write(json.dumps(first_user) + "\n")
    meta_path = sub_path.with_suffix(".meta.json")
    with open(meta_path, "w") as f:
        f.write(json.dumps({"agentType": agent_type, "description": "d"}))


class RecoveredOnlyGateTests(unittest.TestCase):
    """FIX-3 (2026-07-29): a recovered dispatch is an ATTEMPT, so the
    zero-dispatch gate must NOT fire when the main transcript has zero Agent
    tool_use calls but subagent recovery evidence exists.

    Mirrors the scorer's recovery derivation: main transcript yields no Agent
    call, ``subagent_transcripts`` supplies the evidence, and the reconstructed
    prompt is scored under normal semantics (with the recovered-provenance
    suffix), never with the gate detail.
    """

    PROMPT_CRITERIA = (
        "prompt_has_base_dir", "prompt_has_mode_marker", "prompt_has_project_dir",
        "prompt_has_task_section", "prompt_has_context_section",
        "prompt_has_instructions", "prompt_contains_required",
        "prompt_contains_any",
    )
    GATE_DETAIL = "No Agent dispatch attempt; prompt criteria not evaluable."
    RECOVERED_SUFFIX = " (recovered from subagent transcript)"

    def setUp(self):
        TEST_SCRATCH.mkdir(parents=True, exist_ok=True)
        self.expected = {
            "subagent_dispatched": "search-agent",
            "prompt_contains": [],
            "prompt_contains_any": [],
        }

    def tearDown(self):
        import shutil
        if TEST_SCRATCH.exists():
            shutil.rmtree(TEST_SCRATCH)

    def test_recovered_dispatch_does_not_trip_the_gate(self):
        # Main transcript: tool activity but NO Agent call.
        main = TEST_SCRATCH / "transcript.jsonl"
        _write_no_dispatch_transcript(main)
        # Recovery evidence: a well-formed dispatched prompt off a subagent
        # transcript keyed by a fresh session UUID.
        sub = TEST_SCRATCH / "subagents" / "agent-abc123.jsonl"
        prompt = (
            "BASE_DIR context. Ad Hoc mode. PROJECT_DIR set.\n"
            "## Task\nDo it.\n## Context\nHere.\n## Instructions\nSteps.\n"
        )
        _write_subagent_recovery_fixture(sub, prompt, "search-agent")

        results = score_dispatch_compliance(
            str(main), 0, self.expected, subagent_transcripts=[str(sub)]
        )
        by_name = {c.name: c for c in results}

        # The gate did NOT fire: no prompt criterion carries the gate detail.
        for name in self.PROMPT_CRITERIA:
            self.assertIn(name, by_name)
            self.assertNotIn(
                self.GATE_DETAIL, by_name[name].detail,
                f"{name} must be evaluated normally, not gated, for a "
                f"recovered dispatch",
            )
        # The recovered dispatch is treated as a successful attempt: tier1 passes
        # and every criterion carries the recovered-provenance suffix.
        self.assertTrue(by_name["agent_dispatched"].passed)
        self.assertTrue(by_name["correct_subagent_type"].passed)
        for cr in results:
            self.assertTrue(cr.detail.endswith(self.RECOVERED_SUFFIX))
        # The reconstructed prompt scores under normal semantics.
        self.assertTrue(by_name["prompt_has_task_section"].passed)
        self.assertTrue(by_name["prompt_has_context_section"].passed)
        self.assertTrue(by_name["prompt_has_instructions"].passed)


class SandboxSlugTests(unittest.TestCase):
    def test_parentheses_and_spaces_collapsed(self):
        self.assertEqual(
            sandbox_slug("GPT-5.6 Luna (ChatGPT Subscription)"),
            "GPT-5.6_Luna_ChatGPT_Subscription",
        )

    def test_safe_chars_preserved(self):
        self.assertEqual(sandbox_slug("Opus_4.8-preview"), "Opus_4.8-preview")

    def test_no_shell_metacharacters_survive(self):
        slug = sandbox_slug("weird (name) & $stuff; rm -rf")
        for ch in "()&$; ":
            self.assertNotIn(ch, slug)


class SlugCollisionGuardTests(unittest.TestCase):
    """W2 (2026-07-28): assert_unique_sandbox_slugs fails fast on collisions."""

    def test_distinct_slugs_pass(self):
        models = [
            SimpleNamespace(name="Opus 4.8"),
            SimpleNamespace(name="GPT-5.6 Sol"),
        ]
        # Should not raise.
        assert_unique_sandbox_slugs(models)

    def test_colliding_slugs_raise_with_names(self):
        # "GPT-5.6 (A)" and "GPT-5.6 [A]" both slug to "GPT-5.6_A".
        models = [
            SimpleNamespace(name="GPT-5.6 (A)"),
            SimpleNamespace(name="GPT-5.6 [A]"),
        ]
        self.assertEqual(
            sandbox_slug("GPT-5.6 (A)"), sandbox_slug("GPT-5.6 [A]")
        )
        with self.assertRaises(SystemExit) as ctx:
            assert_unique_sandbox_slugs(models)
        msg = str(ctx.exception)
        self.assertIn("GPT-5.6 (A)", msg)
        self.assertIn("GPT-5.6 [A]", msg)


if __name__ == "__main__":
    unittest.main()
