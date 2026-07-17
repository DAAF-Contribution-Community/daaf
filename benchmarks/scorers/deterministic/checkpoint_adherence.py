"""Checkpoint adherence scorer: evaluates golden checkpoint test results.

Parses session transcripts (JSONL) — NOT audit.jsonl — to extract tool calls
made after the golden checkpoint boundary. Checks whether the model performed
the expected protocol steps.

Why transcripts over audit.jsonl:
  The audit-log.sh hook captures an empty `target` field for Skill tool calls,
  making it impossible to determine which skills were loaded. Session transcripts
  contain the full tool_use blocks with complete input parameters.
"""

import json
from pathlib import Path

from benchmarks.harness.models import CriterionResult


def extract_new_tool_calls(
    transcript_path: Path,
    checkpoint_line_count: int,
) -> list[dict]:
    """Extract tool calls from assistant messages added AFTER the golden checkpoint.

    Cross-references tool_use blocks (in assistant records) with tool_result
    blocks (in user records) to determine whether each call succeeded.

    Args:
        transcript_path: Path to the session transcript JSONL.
        checkpoint_line_count: Number of lines in the golden checkpoint file.
            Tool calls in lines after this are from the benchmark run.

    Returns:
        List of dicts with keys: name, skill, file_path, raw_input, tool_use_id, succeeded.
    """
    tool_calls = []
    tool_results = {}

    with open(transcript_path) as f:
        lines = f.readlines()

    for line in lines[checkpoint_line_count:]:
        try:
            record = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        rtype = record.get("type")

        if rtype == "assistant":
            for block in record.get("message", {}).get("content", []):
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue

                name = block.get("name", "")
                inp = block.get("input", {})
                tool_use_id = block.get("id", "")

                tool_calls.append({
                    "name": name,
                    "skill": inp.get("skill", "") if name == "Skill" else "",
                    # file_path must be populated for Write/Edit too — the
                    # state_md_updated criterion checks Write/Edit file_path
                    # and could never pass when this was Read-only.
                    # documents_read is unaffected: it filters name == "Read".
                    # NotebookEdit's parameter is notebook_path, not file_path.
                    "file_path": (inp.get("file_path") or inp.get("notebook_path", ""))
                    if name in ("Read", "Write", "Edit", "NotebookEdit")
                    else "",
                    "command": inp.get("command", "") if name == "Bash" else "",
                    "raw_input": inp,
                    "tool_use_id": tool_use_id,
                    "succeeded": True,
                })

        elif rtype == "user":
            for block in record.get("message", {}).get("content", []):
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                tuid = block.get("tool_use_id", "")
                is_error = block.get("is_error", False)
                if tuid:
                    error_content = ""
                    if is_error:
                        raw = block.get("content", "")
                        if isinstance(raw, str):
                            error_content = raw[:500]
                        elif isinstance(raw, list):
                            parts = [b.get("text", "") for b in raw if isinstance(b, dict)]
                            error_content = " ".join(parts)[:500]
                    tool_results[tuid] = {"succeeded": not is_error, "error_content": error_content}

    for tc in tool_calls:
        tuid = tc.get("tool_use_id", "")
        if tuid and tuid in tool_results:
            tc["succeeded"] = tool_results[tuid]["succeeded"]
            tc["error_content"] = tool_results[tuid]["error_content"]

    return tool_calls


def extract_new_assistant_text(
    transcript_path: Path,
    checkpoint_line_count: int,
) -> list[str]:
    """Extract user-visible assistant text added AFTER the golden checkpoint.

    Collects the `text` field of content blocks with type=="text" from
    assistant records past the checkpoint boundary. This inherently excludes
    thinking blocks (type=="thinking") and tool_use blocks — only prose the
    user actually sees is returned. Used by soft criteria that check whether
    the model *talked about* something (e.g., skill_routing's
    required_skills_engaged name-mention check).

    Args:
        transcript_path: Path to the session transcript JSONL.
        checkpoint_line_count: Number of lines in the golden checkpoint file.
            Text in lines after this is from the benchmark run.

    Returns:
        List of text-block strings in transcript order (one entry per block).
    """
    texts = []

    with open(transcript_path) as f:
        lines = f.readlines()

    for line in lines[checkpoint_line_count:]:
        try:
            record = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        if record.get("type") != "assistant":
            continue

        for block in record.get("message", {}).get("content", []):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            if text:
                texts.append(text)

    return texts


def get_checkpoint_line_count(golden_file: Path) -> int:
    """Count lines in a golden checkpoint file."""
    with open(golden_file) as f:
        return sum(1 for _ in f)


def find_benchmark_transcript(
    session_id: str,
    sessions_dir: Path = Path("/daaf/.claude/logs/sessions"),
    projects_dir: Path = Path.home() / ".claude" / "projects" / "-daaf",
) -> Path | None:
    """Find the session transcript for a benchmark run.

    Checks two locations:
    1. Session archives (.claude/logs/sessions/) — written by archive hook on clean exit
    2. Live session file (.claude/projects/-daaf/) — exists during and after runs,
       including timed-out runs where the archive hook never fired
    """
    if sessions_dir.exists():
        short = session_id[:8]
        for p in sessions_dir.glob(f"*_{short}_orchestrator.jsonl"):
            return p

    # Fallback: live session file (survives timeouts)
    live_file = projects_dir / f"{session_id}.jsonl"
    if live_file.exists():
        return live_file

    return None


def score_checkpoint(
    tool_calls: list[dict],
    expected: dict,
) -> list[CriterionResult]:
    """Score a golden checkpoint test case from extracted tool calls.

    Args:
        tool_calls: Tool calls extracted via extract_new_tool_calls().
        expected: The test case's expected dict with scoring criteria.

    Returns:
        List of CriterionResult for each criterion checked.
    """
    results = []

    # Check documents_read: expected file names that should appear in SUCCESSFUL Read calls
    if "documents_read" in expected:
        read_files = [
            tc["file_path"].split("/")[-1]
            for tc in tool_calls
            if tc["name"] == "Read" and tc["file_path"] and tc.get("succeeded", True)
        ]
        for doc in expected["documents_read"]:
            passed = doc in read_files
            results.append(CriterionResult(
                name=f"read_{doc.replace('.md', '').replace('-', '_')}",
                passed=passed,
                tier="tier1",
                detail=f"{'Found' if passed else 'Missing'}: {doc}",
            ))

    # Collision guard: a skill must appear in skills_loaded OR skills_loaded_soft,
    # never both. Both blocks emit the same dynamically named skill_{name}
    # criterion (only the stamped tier differs), so a collision would produce
    # duplicate same-named criteria entries that corrupt downstream dict-keyed
    # merging (rescore tools and summary rollups key criteria by name). Fail
    # loudly rather than emit corrupt output.
    skill_overlap = set(expected.get("skills_loaded", [])) & set(
        expected.get("skills_loaded_soft", [])
    )
    if skill_overlap:
        raise ValueError(
            f"skills_loaded and skills_loaded_soft overlap: {sorted(skill_overlap)}. "
            f"A skill must be listed in exactly one of the two — both emit the same "
            f"skill_{{name}} criterion name, so duplicates would corrupt dict-keyed "
            f"criteria merging downstream. Fix the case's expected dict."
        )

    # Check skills_loaded: expected skill names from SUCCESSFUL Skill tool calls
    if "skills_loaded" in expected:
        loaded_skills = [
            tc["skill"]
            for tc in tool_calls
            if tc["name"] == "Skill" and tc["skill"] and tc.get("succeeded", True)
        ]
        for skill in expected["skills_loaded"]:
            passed = skill in loaded_skills
            results.append(CriterionResult(
                name=f"skill_{skill.replace('-', '_')}",
                passed=passed,
                tier="tier1",
                detail=f"{'Loaded' if passed else 'Missing'}: {skill}",
            ))

    # Check skills_loaded_soft: same dynamically named skill_{name} criteria as
    # skills_loaded, but emitted at tier2. For mode-doc-directed loads where
    # deferral is a protocol detail rather than a structural failure (e.g.,
    # pc-07's two authoring skills, which framework-development-mode.md directs
    # loading at mode start). A given skill belongs in skills_loaded OR
    # skills_loaded_soft, never both — the criterion name is identical either
    # way, only the stamped tier differs.
    if "skills_loaded_soft" in expected:
        loaded_skills = [
            tc["skill"]
            for tc in tool_calls
            if tc["name"] == "Skill" and tc["skill"] and tc.get("succeeded", True)
        ]
        for skill in expected["skills_loaded_soft"]:
            passed = skill in loaded_skills
            results.append(CriterionResult(
                name=f"skill_{skill.replace('-', '_')}",
                passed=passed,
                tier="tier2",
                detail=f"{'Loaded' if passed else 'Missing'} (soft): {skill}",
            ))

    # Check subagent_dispatched: expected SUCCESSFUL Agent tool calls
    if "subagent_dispatched" in expected:
        spec = expected["subagent_dispatched"]
        agent_calls = [tc for tc in tool_calls if tc["name"] == "Agent" and tc.get("succeeded", True)]

        if isinstance(spec, dict):
            expected_type = spec.get("type", "")
            prompt_contains = spec.get("prompt_contains", [])

            type_match = any(
                tc["raw_input"].get("subagent_type") == expected_type
                for tc in agent_calls
            )
            results.append(CriterionResult(
                name=f"agent_type_{expected_type}",
                passed=type_match,
                tier="tier1",
                detail=f"{'Found' if type_match else 'Missing'}: Agent({expected_type})",
            ))

            for keyword in prompt_contains:
                found = any(
                    keyword in tc["raw_input"].get("prompt", "")
                    for tc in agent_calls
                )
                results.append(CriterionResult(
                    name=f"agent_prompt_contains_{keyword[:30]}",
                    passed=found,
                    tier="tier2",
                    detail=f"{'Found' if found else 'Missing'} in agent prompt: {keyword}",
                ))

    # Check no_tool_calls_of_type: tools that should NOT appear (blocking gates)
    if "no_tool_calls_of_type" in expected:
        for forbidden_tool in expected["no_tool_calls_of_type"]:
            found = any(tc["name"] == forbidden_tool for tc in tool_calls)
            results.append(CriterionResult(
                name=f"no_{forbidden_tool.lower()}",
                passed=not found,
                tier="tier1",
                detail=f"{'VIOLATION: found' if found else 'Correctly absent'}: {forbidden_tool}",
            ))

    # Check response_contains: patterns in response text (not tool calls)
    # This would need the response text passed separately — skip for now

    # Check state_md_updated: whether STATE.md was written/edited
    if expected.get("state_md_updated"):
        state_writes = any(
            tc["name"] in ("Write", "Edit") and "STATE.md" in tc.get("file_path", "")
            for tc in tool_calls
        )
        results.append(CriterionResult(
            name="state_md_updated",
            passed=state_writes,
            tier="tier1",
            detail=f"STATE.md {'updated' if state_writes else 'not updated'}",
        ))

    return results
