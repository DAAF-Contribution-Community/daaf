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

Dispatch-recovery fallback (2026-06-11): the harness runs ``claude -p`` under
``subprocess.run(timeout=...)``, which SIGKILLs on timeout. Claude Code's
main-session transcript writes are async/buffered, so a timed-out run can lose
an unflushed tail — sometimes including the assistant record carrying the
``Agent`` tool_use. The dispatched subagent's own transcript
(``subagents/agent-{id}.jsonl`` + ``agent-{id}.meta.json``) survives because it
is a separate file, and its presence proves the dispatch happened (subagent
dirs are keyed by per-run fresh session UUIDs). When the main transcript yields
NO Agent tool_use record at all post-checkpoint (not even a failed one) AND
the caller supplies subagent transcript paths, the scorer recovers the
dispatch from that evidence: the subagent_type comes from meta.json
``agentType`` and the full dispatched prompt from the first user record of the
subagent transcript. A RECORDED failed Agent call (``is_error=true``)
suppresses recovery — it is evidence the system processed and
rejected/aborted the dispatch, which must keep failing per the original
criterion semantics; the fallback exists only to reconstruct records LOST to
the timeout-kill race. The fallback is evidence-gated, NOT timeout-gated. Every criterion emitted from a recovered
scoring pass carries a " (recovered from subagent transcript)" provenance
suffix in its detail. With no evidence supplied (or none parseable), behavior
is identical to the pre-fallback scorer.
"""

import json
from pathlib import Path

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


def recover_agent_calls_from_subagent_transcripts(
    subagent_transcripts: list,
) -> list[dict]:
    """Synthesize Agent-call entries from archived subagent transcript evidence.

    Used by the dispatch-recovery fallback (module docstring) when the main
    transcript lost its Agent tool_use record to a timeout SIGKILL. For each
    subagent transcript ``agent-{id}.jsonl``:
      - subagent_type comes from the sibling ``agent-{id}.meta.json``
        (``{"agentType": ..., "description": ...}``)
      - the dispatched prompt comes from the transcript's FIRST record, which
        is type "user" with ``message.content`` as a plain string containing
        the complete prompt the orchestrator dispatched

    Args:
        subagent_transcripts: Paths (str or Path) to subagent .jsonl files.
            Works for both live locations (~/.claude/projects/-daaf/{sid}/
            subagents/) and archived run dirs (results/*/runs/*/subagents/).

    Returns:
        List of dicts shaped like extract_agent_calls() entries, each with
        ``succeeded: True`` and an extra ``recovered: True`` flag. Transcripts
        whose first record cannot be parsed — or whose record, ``message``, or
        ``content`` is not the expected shape (dict / dict / plain string) —
        are skipped: an unparseable or malformed file is not dispatch
        evidence. Fail-soft is deliberate: this runs inside the live scorer,
        where a crash would convert a completed, paid run into a zeroed error
        result.
    """
    recovered = []
    for t in subagent_transcripts:
        t = Path(t)

        # --- Prompt: first record of the subagent transcript ---
        prompt = ""
        first_record = None
        try:
            with open(t) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    first_record = json.loads(line)
                    break
        except (OSError, json.JSONDecodeError):
            continue
        # Malformed-evidence guards: treat unexpected shapes as not-evidence
        # (skip the transcript) rather than crashing — an AttributeError here
        # in the live runner would zero out a completed, paid run.
        if not isinstance(first_record, dict):
            # Empty file (None) or non-dict JSON (bare list/string/number).
            continue
        if first_record.get("type") == "user":
            message = first_record.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content", "")
            if not isinstance(content, str):
                # The dispatched prompt is written as the first user record's
                # content as a PLAIN STRING; a list-of-blocks or other shape
                # is not the dispatch-evidence format -> skip.
                continue
            prompt = content
        else:
            # A dict first record that is not a user record (e.g., a summary
            # or queue-operation line) is not the dispatch-evidence format
            # either — skip, consistent with the transcript-shape contract
            # above (transcript problems skip; only meta problems degrade).
            continue

        # --- Type + description: sibling meta.json ---
        agent_type = ""
        description = ""
        meta_path = t.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                # Guard non-dict meta JSON the same way as unparseable meta
                # (adjacent except): degrade to empty fields, don't crash.
                if isinstance(meta, dict):
                    agent_type = meta.get("agentType", "")
                    description = meta.get("description", "")
            except (OSError, json.JSONDecodeError):
                pass

        recovered.append({
            "subagent_type": agent_type,
            "prompt": prompt,
            "description": description,
            "model": "",
            "raw_input": {},
            "succeeded": True,
            "recovered": True,
        })
    return recovered


def score_dispatch_compliance(
    transcript_path: str,
    checkpoint_line_count: int,
    expected: dict,
    subagent_transcripts: list | None = None,
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
        subagent_transcripts: Optional list of subagent .jsonl paths used as
            dispatch-recovery evidence (module docstring). Consulted ONLY when
            the main transcript yields no Agent tool_use record at all — a
            recorded failed call suppresses recovery. Callers:
            the live runner passes find_subagent_transcripts(session_id); the
            archived rescore passes the run dir's subagents/ globs. When None
            or empty, behavior is identical to the pre-fallback scorer.

    Returns:
        List of CriterionResult objects, one per criterion. When recovery
        fired, every detail carries the "(recovered from subagent transcript)"
        provenance suffix.
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

    # --- Dispatch-recovery fallback (evidence-gated, NOT timeout-gated) ---
    # NO Agent tool_use record at all in the main transcript + subagent
    # transcript evidence supplied by the caller -> the dispatch demonstrably
    # happened (subagent dirs are keyed by per-run fresh session UUIDs) but
    # its tool_use record was lost to the timeout SIGKILL before the async
    # transcript writer flushed it. Synthesize the calls from the evidence.
    # The gate is `not agent_calls`, deliberately NOT `not succeeded_calls`:
    # the fallback exists only to reconstruct records LOST to the
    # timeout-kill race. A RECORDED failed call (is_error=true) is evidence
    # the system processed and rejected/aborted the dispatch, and must keep
    # failing per the original criterion semantics above — recovery never
    # overturns a recorded failure.
    recovered_calls = []
    if not agent_calls and subagent_transcripts:
        recovered_calls = recover_agent_calls_from_subagent_transcripts(
            subagent_transcripts
        )
        if recovered_calls:
            succeeded_calls = recovered_calls

    dispatched = len(succeeded_calls) > 0

    detail_parts = []
    if recovered_calls:
        detail_parts.append(
            f"No successful Agent calls in main transcript; "
            f"{len(recovered_calls)} dispatch(es) evidenced by archived "
            f"subagent transcript(s)"
        )
    elif succeeded_calls:
        detail_parts.append(f"{len(succeeded_calls)} successful Agent call(s)")
    if failed_calls:
        detail_parts.append(f"{len(failed_calls)} failed")
    if not agent_calls and not recovered_calls:
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
    # Required for write-capable agents; informational for read-only agents.
    READ_ONLY_AGENTS = {"search-agent", "source-researcher", "plan-checker"}
    has_project_dir = any("PROJECT_DIR" in p for p in all_prompts)
    is_read_only = expected_type in READ_ONLY_AGENTS

    if is_read_only:
        results.append(CriterionResult(
            name="prompt_has_project_dir",
            passed=True,
            tier="tier2",
            detail=(
                f"Read-only agent ({expected_type}): PROJECT_DIR not required. "
                f"{'Present anyway.' if has_project_dir else 'Not present (expected).'}"
            ),
        ))
    else:
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
    # Accept semantically equivalent headers for context information.
    CONTEXT_HEADERS = [
        "## Context", "## Scope", "## Background", "## Specifications",
        "## Dataset Specifications", "## Known Symptoms", "## What to Search",
    ]
    matched_context = None
    for p in all_prompts:
        for header in CONTEXT_HEADERS:
            if header in p:
                matched_context = header
                break
        if matched_context:
            break

    results.append(CriterionResult(
        name="prompt_has_context_section",
        passed=matched_context is not None,
        tier="tier2",
        detail=(
            f"Found '{matched_context}' section in agent prompt."
            if matched_context
            else f"Missing context section in agent prompt. Accepted: {CONTEXT_HEADERS}"
        ),
    ))

    # --- Criterion 8: prompt_has_instructions (tier2) ---
    # Accept semantically equivalent headers for instruction content.
    INSTRUCTION_HEADERS = [
        "## Instructions", "## What to Report", "## What to Look For",
        "## Where to Look", "## Validation Requirements", "## Output Format",
        "## Expected Output", "## Deliverables",
    ]
    matched_instructions = None
    for p in all_prompts:
        for header in INSTRUCTION_HEADERS:
            if header in p:
                matched_instructions = header
                break
        if matched_instructions:
            break

    results.append(CriterionResult(
        name="prompt_has_instructions",
        passed=matched_instructions is not None,
        tier="tier2",
        detail=(
            f"Found '{matched_instructions}' section in agent prompt."
            if matched_instructions
            else f"Missing instructions section in agent prompt. Accepted: {INSTRUCTION_HEADERS}"
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

    # --- Criterion 10: prompt_contains_any (tier2) ---
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

    # --- Provenance stamp for recovered scoring passes ---
    # When recovery fired, EVERY criterion above was computed from the
    # synthesized evidence (type from meta.json, prompt from the subagent
    # transcript's first user record), so all details are stamped uniformly —
    # downstream consumers and greps can identify recovered runs from any
    # single criterion.
    if recovered_calls:
        for cr in results:
            cr.detail += " (recovered from subagent transcript)"

    return results
