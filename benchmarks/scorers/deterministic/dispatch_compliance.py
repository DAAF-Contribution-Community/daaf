"""Deterministic scorer for dispatch compliance test cases (Phase 3).

Evaluates whether a DAAF orchestrator correctly dispatches subagents via the
Agent tool when a user requests specific tasks in Ad Hoc Collaboration mode.

Operates on session transcripts (JSONL) rather than audit.jsonl because audit
logs record an empty ``target`` field for Agent calls, losing the subagent_type
and prompt content needed for scoring.

Scoring criteria (all deterministic, no LLM involvement):
  - agent_dispatched (tier1): At least one Agent tool call exists and succeeds
  - correct_subagent_type (tier1): Agent call matches expected subagent_type
  - prompt_has_base_dir (tier2): Agent prompt contains "BASE_DIR"
  - prompt_has_mode_marker (tier2): Agent prompt contains "Ad Hoc" (case-insensitive)
  - prompt_has_project_dir (tier2): Agent prompt contains "PROJECT_DIR"
  - prompt_has_task_section (tier2): Agent prompt contains "## Task"
  - prompt_has_context_section (tier2): Agent prompt contains "## Context"
  - prompt_has_instructions (tier2): Agent prompt contains "## Instructions"
  - prompt_contains_required (tier2): All expected strings appear in Agent prompt
  - prompt_contains_any (tier2): At least one of the optional strings appears
"""

from benchmarks.harness.models import CriterionResult
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
)


def extract_agent_calls(tool_calls: list[dict]) -> list[dict]:
    """Extract Agent tool calls and parse their input fields.

    Filters the tool_calls list (as returned by ``extract_new_tool_calls``)
    to only Agent invocations, and surfaces the key input fields for
    convenient downstream access.

    Args:
        tool_calls: List of tool call dicts from extract_new_tool_calls().

    Returns:
        List of dicts, each with keys:
            - subagent_type: str
            - prompt: str
            - description: str
            - model: str (may be empty)
            - raw_input: dict (full input payload)
            - succeeded: bool
    """
    agent_calls = []
    for tc in tool_calls:
        if tc.get("name") != "Agent":
            continue
        raw = tc.get("raw_input", {})
        agent_calls.append({
            "subagent_type": raw.get("subagent_type", ""),
            "prompt": raw.get("prompt", ""),
            "description": raw.get("description", ""),
            "model": raw.get("model", ""),
            "raw_input": raw,
            "succeeded": tc.get("succeeded", True),
        })
    return agent_calls


def score_dispatch_compliance(
    transcript_path: str,
    checkpoint_line_count: int,
    expected: dict,
) -> list[CriterionResult]:
    """Score dispatch compliance from a session transcript.

    Extracts tool calls made after the golden checkpoint boundary, then
    checks whether the model dispatched the correct subagent with a
    properly structured prompt.

    Args:
        transcript_path: Path to session JSONL transcript.
        checkpoint_line_count: Number of lines in the golden checkpoint
            (boundary marker). Tool calls on lines after this index are
            from the benchmark run.
        expected: Dict with scoring parameters:
            - subagent_dispatched (str): expected subagent_type value
            - prompt_contains (list[str]): strings that must ALL appear
              in the Agent prompt
            - prompt_contains_any (list[str], optional): at least one
              must appear in the Agent prompt

    Returns:
        List of CriterionResult objects, one per criterion.
    """
    results = []

    # --- Extract tool calls after the golden checkpoint boundary ---
    tool_calls = extract_new_tool_calls(transcript_path, checkpoint_line_count)
    agent_calls = extract_agent_calls(tool_calls)

    expected_type = expected.get("subagent_dispatched", "")
    prompt_contains = expected.get("prompt_contains", [])
    prompt_contains_any = expected.get("prompt_contains_any", [])

    # --- Criterion 1: agent_dispatched (tier1) ---
    # At least one Agent tool call must exist AND succeed.
    # A failed dispatch (is_error=true) means the system rejected the launch.
    succeeded_calls = [ac for ac in agent_calls if ac.get("succeeded", True)]
    failed_calls = [ac for ac in agent_calls if not ac.get("succeeded", True)]
    dispatched = len(succeeded_calls) > 0

    detail_parts = []
    if succeeded_calls:
        detail_parts.append(f"{len(succeeded_calls)} successful Agent call(s)")
    if failed_calls:
        detail_parts.append(f"{len(failed_calls)} failed")
    if not agent_calls:
        detail_parts.append("No Agent tool calls found after checkpoint boundary")

    results.append(CriterionResult(
        name="agent_dispatched",
        passed=dispatched,
        tier="tier1",
        detail=". ".join(detail_parts) + ".",
    ))

    # --- Criterion 2: correct_subagent_type (tier1) ---
    # At least one SUCCESSFUL Agent call must have the expected subagent_type.
    matching_calls = [
        ac for ac in succeeded_calls
        if ac["subagent_type"] == expected_type
    ]
    type_correct = len(matching_calls) > 0
    actual_types = [ac["subagent_type"] for ac in succeeded_calls] if succeeded_calls else []

    type_detail = (
        f"Found Agent({expected_type})."
        if type_correct
        else f"Expected Agent({expected_type}), found: {actual_types or 'no successful Agent calls'}."
    )
    # Note failed attempts of the right type for diagnostics
    failed_right_type = [ac for ac in failed_calls if ac["subagent_type"] == expected_type]
    if failed_right_type and not type_correct:
        type_detail += f" ({len(failed_right_type)} attempt(s) of correct type failed.)"

    results.append(CriterionResult(
        name="correct_subagent_type",
        passed=type_correct,
        tier="tier1",
        detail=type_detail,
    ))

    # For prompt-level criteria, examine prompts from SUCCESSFUL Agent calls
    # that match the expected subagent_type. If none match, fall back to all
    # successful calls so we still report what was found.
    prompt_source = matching_calls if matching_calls else succeeded_calls
    all_prompts = [ac["prompt"] for ac in prompt_source]

    # --- Criterion 3: prompt_has_base_dir (tier2) ---
    # The Agent prompt must contain "BASE_DIR" (case-sensitive).
    has_base_dir = any("BASE_DIR" in p for p in all_prompts)
    results.append(CriterionResult(
        name="prompt_has_base_dir",
        passed=has_base_dir,
        tier="tier2",
        detail=(
            "Found 'BASE_DIR' in agent prompt."
            if has_base_dir
            else "Missing 'BASE_DIR' in agent prompt."
        ),
    ))

    # --- Criterion 4: prompt_has_mode_marker (tier2) ---
    # The Agent prompt must contain "Ad Hoc" (case-insensitive).
    has_mode_marker = any("ad hoc" in p.lower() for p in all_prompts)
    results.append(CriterionResult(
        name="prompt_has_mode_marker",
        passed=has_mode_marker,
        tier="tier2",
        detail=(
            "Found 'Ad Hoc' in agent prompt."
            if has_mode_marker
            else "Missing 'Ad Hoc' (case-insensitive) in agent prompt."
        ),
    ))

    # --- Criterion 5: prompt_has_project_dir (tier2) ---
    # The Agent prompt must contain "PROJECT_DIR" (case-sensitive).
    has_project_dir = any("PROJECT_DIR" in p for p in all_prompts)
    results.append(CriterionResult(
        name="prompt_has_project_dir",
        passed=has_project_dir,
        tier="tier2",
        detail=(
            "Found 'PROJECT_DIR' in agent prompt."
            if has_project_dir
            else "Missing 'PROJECT_DIR' in agent prompt."
        ),
    ))

    # --- Criterion 6: prompt_has_task_section (tier2) ---
    has_task = any("## Task" in p for p in all_prompts)
    results.append(CriterionResult(
        name="prompt_has_task_section",
        passed=has_task,
        tier="tier2",
        detail=(
            "Found '## Task' section in agent prompt."
            if has_task
            else "Missing '## Task' section in agent prompt."
        ),
    ))

    # --- Criterion 7: prompt_has_context_section (tier2) ---
    has_context = any("## Context" in p for p in all_prompts)
    results.append(CriterionResult(
        name="prompt_has_context_section",
        passed=has_context,
        tier="tier2",
        detail=(
            "Found '## Context' section in agent prompt."
            if has_context
            else "Missing '## Context' section in agent prompt."
        ),
    ))

    # --- Criterion 8: prompt_has_instructions (tier2) ---
    has_instructions = any("## Instructions" in p for p in all_prompts)
    results.append(CriterionResult(
        name="prompt_has_instructions",
        passed=has_instructions,
        tier="tier2",
        detail=(
            "Found '## Instructions' section in agent prompt."
            if has_instructions
            else "Missing '## Instructions' section in agent prompt."
        ),
    ))

    # --- Criterion 9: prompt_contains_required (tier2) ---
    # Every string in expected["prompt_contains"] must appear in the prompt.
    missing = []
    for required_str in prompt_contains:
        found = any(required_str in p for p in all_prompts)
        if not found:
            missing.append(required_str)

    all_required_present = len(missing) == 0
    results.append(CriterionResult(
        name="prompt_contains_required",
        passed=all_required_present,
        tier="tier2",
        detail=(
            f"All {len(prompt_contains)} required string(s) found in agent prompt."
            if all_required_present
            else f"Missing required string(s) in agent prompt: {missing}"
        ),
    ))

    # --- Criterion 6: prompt_contains_any (tier2) ---
    # If expected["prompt_contains_any"] is provided, at least one string
    # must appear. If not provided, this criterion auto-passes.
    if prompt_contains_any:
        found_any = any(
            candidate in p
            for p in all_prompts
            for candidate in prompt_contains_any
        )
        results.append(CriterionResult(
            name="prompt_contains_any",
            passed=found_any,
            tier="tier2",
            detail=(
                f"Found at least one of {prompt_contains_any} in agent prompt."
                if found_any
                else f"None of {prompt_contains_any} found in agent prompt."
            ),
        ))
    else:
        results.append(CriterionResult(
            name="prompt_contains_any",
            passed=True,
            tier="tier2",
            detail="No prompt_contains_any specified; auto-pass.",
        ))

    return results
