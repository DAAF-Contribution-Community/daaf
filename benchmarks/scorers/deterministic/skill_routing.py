"""Skill routing scorer: evaluates skill loading and reference routing test results.

Scores Phase 4 (skill_routing) runs: a model resumes from the Ad Hoc Collaboration
golden checkpoint, receives a brainstorming prompt, and is scored on whether it
loads exactly the skills (Skill tool calls) and reads exactly the skill reference
files (Read tool calls) that the DAAF skills' own routing directives prescribe.

All scoring is MAIN-TRANSCRIPT-ONLY: Phase 4 runs disallow the Agent tool, so no
subagent transcripts exist (see PHASE4_SKILL_ROUTING_PLAN.md section 2.2).

Matching rules (see plan sections 2.3 and 3.2):
- Read matching is by BASENAME only: sandbox checkpoint replay string-rewrites
  /daaf inside replayed file_path values, so full-path matching is unreliable.
  Basenames in the case set are unique within their skill, and skill membership
  is enforced by the paired Skill-load criterion, so basename matching does not
  create cross-skill false positives.
- Success-only: failed tool calls (missing file, denied tool, etc.) never satisfy
  a requirement. Caveat (shared-extractor property, matches Phase 3 behavior):
  extract_new_tool_calls() defaults succeeded=True when a tool_use has no
  matching tool_result, so a trailing call in a timeout-truncated transcript
  counts as successful.

Reuses extract_new_tool_calls() from checkpoint_adherence for post-checkpoint
slicing and tool_result success cross-referencing.
"""

from pathlib import Path

from benchmarks.harness.models import CriterionResult
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
)

def _basename(file_path: str) -> str:
    """Return the basename of a Read file_path (basename-only matching rule)."""
    return file_path.split("/")[-1]


def score_skill_routing(
    transcript_path: str,
    checkpoint_line_count: int,
    expected: dict,
) -> list[CriterionResult]:
    """Score a skill_routing test case from the main session transcript.

    Args:
        transcript_path: Path to the session transcript JSONL.
        checkpoint_line_count: Number of lines in the golden checkpoint file;
            tool calls in lines after this are from the benchmark run.
        expected: The test case's expected dict with keys: required_skills,
            required_refs, expected_refs, forbidden_skills, and optionally
            order (omitted when no directive prescribes a sequence).

    Returns:
        List of CriterionResult — one per criterion in section 3.1 of the plan:
        required_skills_loaded (tier1), required_refs_read (tier1),
        expected_refs_read, routing_order, no_forbidden_skills (all tier2).
    """
    tool_calls = extract_new_tool_calls(Path(transcript_path), checkpoint_line_count)

    # Successful Skill loads and Read basenames (success-only rule)
    loaded_skills = [
        tc["skill"]
        for tc in tool_calls
        if tc["name"] == "Skill" and tc["skill"] and tc.get("succeeded", True)
    ]
    read_basenames = [
        _basename(tc["file_path"])
        for tc in tool_calls
        if tc["name"] == "Read" and tc["file_path"] and tc.get("succeeded", True)
    ]
    results = []

    # --- required_skills_loaded (tier1) ---
    required_skills = expected.get("required_skills", [])
    missing_skills = [s for s in required_skills if s not in loaded_skills]
    results.append(CriterionResult(
        name="required_skills_loaded",
        passed=not missing_skills,
        tier="tier1",
        detail=(
            f"All required skills loaded: {required_skills}"
            if not missing_skills
            else f"Missing required skill(s): {missing_skills} "
                 f"(loaded: {loaded_skills or 'none'})"
        ),
    ))

    # --- required_refs_read (tier1) ---
    required_refs = expected.get("required_refs", [])
    missing_refs = [r for r in required_refs if r not in read_basenames]
    results.append(CriterionResult(
        name="required_refs_read",
        passed=not missing_refs,
        tier="tier1",
        detail=(
            f"All required refs read: {required_refs}"
            if not missing_refs
            else f"Missing required ref(s): {missing_refs} "
                 f"(read: {sorted(set(read_basenames)) or 'none'})"
        ),
    ))

    # --- expected_refs_read (tier2) ---
    expected_refs = expected.get("expected_refs", [])
    missing_expected = [r for r in expected_refs if r not in read_basenames]
    if not expected_refs:
        detail = "No secondary expected refs for this case."
    elif not missing_expected:
        detail = f"All expected refs read: {expected_refs}"
    else:
        detail = f"Missing expected ref(s): {missing_expected}"
    results.append(CriterionResult(
        name="expected_refs_read",
        passed=not missing_expected,
        tier="tier2",
        detail=detail,
    ))

    # --- routing_order (tier2) ---
    # Ordered-subsequence check over the post-checkpoint stream of SUCCESSFUL
    # Skill/Read events. Passes automatically when the case omits "order" (no
    # directive prescribes a sequence, e.g., sr-15's two independent branches).
    if "order" in expected and expected["order"]:
        order_steps = [tuple(step) for step in expected["order"]]
        events = []
        for tc in tool_calls:
            if tc["name"] == "Skill" and tc["skill"] and tc.get("succeeded", True):
                events.append(("skill", tc["skill"]))
            elif tc["name"] == "Read" and tc["file_path"] and tc.get("succeeded", True):
                events.append(("read", _basename(tc["file_path"])))

        idx = 0
        failed_step = None
        for step in order_steps:
            while idx < len(events) and events[idx] != step:
                idx += 1
            if idx >= len(events):
                failed_step = step
                break
            idx += 1

        order_str = " -> ".join(f"{k}:{v}" for k, v in order_steps)
        if failed_step is None:
            detail = f"Order satisfied as subsequence: {order_str}"
        else:
            detail = (
                f"Order broken at {failed_step[0]}:{failed_step[1]} "
                f"(expected subsequence: {order_str}; "
                f"observed events: {events or 'none'})"
            )
        results.append(CriterionResult(
            name="routing_order",
            passed=failed_step is None,
            tier="tier2",
            detail=detail,
        ))
    else:
        results.append(CriterionResult(
            name="routing_order",
            passed=True,
            tier="tier2",
            detail="No order specified for this case — passes automatically.",
        ))

    # --- no_forbidden_skills (tier2) ---
    # Only SUCCESSFUL loads count: a failed/denied load of a forbidden skill
    # never injected its content, so no routing harm occurred.
    forbidden = expected.get("forbidden_skills", [])
    violations = [s for s in loaded_skills if s in forbidden]
    if not forbidden:
        detail = "No forbidden skills for this case."
    elif not violations:
        detail = f"No forbidden skill loaded (forbidden: {forbidden})."
    else:
        detail = f"Forbidden skill(s) loaded: {violations}"
    results.append(CriterionResult(
        name="no_forbidden_skills",
        passed=not violations,
        tier="tier2",
        detail=detail,
    ))

    return results
