"""Deterministic scorer for subagent behavior in dispatch compliance tests.

After the orchestrator dispatches a subagent via the Agent tool, this scorer
examines what the subagent actually DID by parsing its separate transcript file.
Behavioral expectations are derived from the agent type — no test case changes
needed.

Data sources:
  - Subagent transcripts: ~/.claude/projects/-daaf/{session_id}/subagents/agent-{id}.jsonl
  - Archived copies: _sandbox/transcripts/{session_id}/subagents/agent-{id}.jsonl

Scoring criteria per agent type (all deterministic): agent-specific criteria
(tier1/tier2) varying by subagent_type — see BEHAVIOR_SPECS.

Criteria hygiene (2026-06-10): structural always-pass criteria were removed
because they diluted Perfect and soft rates without discriminating behavior
(the viewer counts every non-info criterion toward Perfect):
  - subagent_transcript_found — when no subagent transcript exists, the scorer
    now emits NO subagent criteria (dispatch-level criteria such as
    agent_dispatched already capture dispatch failure)
  - subagent_active — every dispatched subagent makes tool calls
  - subagent_no_code_execution — never observed failing for read-only agents
  - subagent_tool_summary (info) — diagnostic distribution, not a criterion
"""

import json
import re
from pathlib import Path

from benchmarks.harness.models import CriterionResult


def find_subagent_transcripts(session_id: str) -> list[Path]:
    """Find all subagent transcript files for a given session.

    Checks archived location first, then live project directory.

    Returns:
        List of paths to subagent .jsonl transcript files.
    """
    locations = [
        Path(f"/daaf/benchmarks/_sandbox/transcripts/{session_id}/subagents"),
        Path.home() / ".claude" / "projects" / "-daaf" / session_id / "subagents",
    ]

    for loc in locations:
        if loc.exists():
            transcripts = sorted(loc.glob("agent-*.jsonl"))
            if transcripts:
                return transcripts

    return []


def extract_subagent_tool_calls(transcript_path: Path) -> list[dict]:
    """Extract all tool calls from a subagent transcript.

    Unlike parent transcripts, subagent transcripts don't have a golden
    checkpoint boundary — all tool calls from line 0 are from the subagent.

    Returns:
        List of dicts with keys: name, raw_input, tool_use_id, succeeded.
    """
    tool_calls = []
    tool_results = {}

    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
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
                        tool_results[tuid] = not is_error

    for tc in tool_calls:
        tuid = tc.get("tool_use_id", "")
        if tuid and tuid in tool_results:
            tc["succeeded"] = tool_results[tuid]

    return tool_calls


# --- Per-agent-type behavioral checks ---

def _check_uses_tool_type(tool_calls: list[dict], tool_types: list[str]) -> tuple[bool, str]:
    used = {tc["name"] for tc in tool_calls}
    found = used & set(tool_types)
    if found:
        return True, f"Used expected tool types: {sorted(found)}."
    return False, f"Expected one of {tool_types}, found: {sorted(used) or 'none'}."


def _check_reads_file(tool_calls: list[dict], pattern: str) -> tuple[bool, str]:
    read_calls = [
        tc for tc in tool_calls
        if tc["name"] == "Read" and tc.get("succeeded", True)
    ]
    for rc in read_calls:
        file_path = rc["raw_input"].get("file_path", "")
        if re.search(pattern, file_path):
            return True, f"Read file matching '{pattern}': {file_path}"
    paths = [rc["raw_input"].get("file_path", "?") for rc in read_calls[:5]]
    return False, f"No Read call matched '{pattern}'. Read files: {paths or 'none'}"


def _check_references_file(tool_calls: list[dict], pattern: str) -> tuple[bool, str]:
    """Check if any tool call references a file matching the pattern.

    Searches across Read file_path, Write file_path, Bash command, and
    Edit file_path. Catches cases where agents access data through scripts
    (Bash) rather than the Read tool directly.
    """
    path_fields = {
        "Read": "file_path",
        "Write": "file_path",
        "Edit": "file_path",
        "Bash": "command",
    }
    for tc in tool_calls:
        field = path_fields.get(tc["name"])
        if field:
            value = tc["raw_input"].get(field, "")
            if re.search(pattern, value):
                return True, f"{tc['name']} referenced file matching '{pattern}': {value[:120]}"
    tool_names = [tc["name"] for tc in tool_calls[:10]]
    return False, f"No tool call referenced '{pattern}'. Tools used: {tool_names or 'none'}"


def _check_writes_file(tool_calls: list[dict], pattern: str) -> tuple[bool, str]:
    write_calls = [
        tc for tc in tool_calls
        if tc["name"] == "Write" and tc.get("succeeded", True)
    ]
    for wc in write_calls:
        file_path = wc["raw_input"].get("file_path", "")
        if re.search(pattern, file_path):
            return True, f"Wrote file matching '{pattern}': {file_path}"
    paths = [wc["raw_input"].get("file_path", "?") for wc in write_calls[:5]]
    return False, f"No Write call matched '{pattern}'. Written files: {paths or 'none'}"


def _check_bash_contains(tool_calls: list[dict], pattern: str) -> tuple[bool, str]:
    bash_calls = [tc for tc in tool_calls if tc["name"] == "Bash"]
    for bc in bash_calls:
        command = bc["raw_input"].get("command", "")
        if re.search(pattern, command):
            return True, f"Bash command matched '{pattern}'."
    return False, f"No Bash command matched '{pattern}' ({len(bash_calls)} Bash calls found)."


def _check_loads_skill(tool_calls: list[dict], pattern: str) -> tuple[bool, str]:
    skill_calls = [
        tc for tc in tool_calls
        if tc["name"] == "Skill" and tc.get("succeeded", True)
    ]
    for sc in skill_calls:
        skill_name = sc["raw_input"].get("skill", "")
        if re.search(pattern, skill_name):
            return True, f"Loaded skill matching '{pattern}': {skill_name}"
    loaded = [sc["raw_input"].get("skill", "?") for sc in skill_calls]
    return False, f"No Skill call matched '{pattern}'. Loaded: {loaded or 'none'}"


def _check_min_tool_calls(tool_calls: list[dict], min_count: int) -> tuple[bool, str]:
    n = len(tool_calls)
    if n >= min_count:
        return True, f"Made {n} tool calls (minimum {min_count})."
    return False, f"Made {n} tool calls, expected at least {min_count}."


def _check_writes_to_dir(tool_calls: list[dict], pattern: str) -> tuple[bool, str]:
    """Check that at least one successful Write targets a path matching the pattern."""
    write_calls = [
        tc for tc in tool_calls
        if tc["name"] == "Write" and tc.get("succeeded", True)
    ]
    for wc in write_calls:
        file_path = wc["raw_input"].get("file_path", "")
        if re.search(pattern, file_path):
            return True, f"Wrote to path matching '{pattern}': {file_path}"
    paths = [wc["raw_input"].get("file_path", "?") for wc in write_calls[:5]]
    return False, f"No Write matched '{pattern}'. Written: {paths or 'none'}"


def _check_reads_min_matching(tool_calls: list[dict], pattern: str, min_count: int) -> tuple[bool, str]:
    """Check that at least N successful Read calls target paths matching the pattern."""
    matching = [
        tc for tc in tool_calls
        if tc["name"] == "Read" and tc.get("succeeded", True)
        and re.search(pattern, tc["raw_input"].get("file_path", ""))
    ]
    n = len(matching)
    if n >= min_count:
        paths = [m["raw_input"].get("file_path", "?").split("/")[-1] for m in matching[:5]]
        return True, f"Read {n} files matching '{pattern}' (min {min_count}): {paths}"
    paths = [m["raw_input"].get("file_path", "?").split("/")[-1] for m in matching]
    return False, f"Read {n} files matching '{pattern}', expected {min_count}. Found: {paths or 'none'}"


# --- Agent type behavior specifications ---

BEHAVIOR_SPECS: dict[str, list[dict]] = {
    "research-executor": [
        {"name": "subagent_writes_script", "tier": "tier1",
         "check": "writes_file", "pattern": r"\.py$"},
        {"name": "subagent_writes_to_adhoc", "tier": "tier2",
         "check": "writes_to_dir", "pattern": r"scripts/adhoc/"},
        {"name": "subagent_uses_run_with_capture", "tier": "tier2",
         "check": "bash_contains", "pattern": r"run_with_capture"},
    ],
    "source-researcher": [
        {"name": "subagent_loads_data_skill", "tier": "tier1",
         "check": "loads_skill", "pattern": r"education-data-source-"},
        {"name": "subagent_reads_skill_refs", "tier": "tier2",
         "check": "reads_min_matching", "pattern": r"/references/", "min_count": 2},
    ],
    "search-agent": [
        {"name": "subagent_searches", "tier": "tier1",
         "check": "uses_tool_type", "tool_types": ["Grep", "Glob", "Read", "WebSearch"]},
        {"name": "subagent_reads_skill_files", "tier": "tier2",
         "check": "reads_min_matching", "pattern": r"\.claude/skills/", "min_count": 3},
    ],
    "debugger": [
        {"name": "subagent_reads_problem_script", "tier": "tier1",
         "check": "reads_file", "pattern": r"test_fixtures/debugger/"},
        {"name": "subagent_writes_diagnostic", "tier": "tier2",
         "check": "writes_to_dir", "pattern": r"debug/|diag"},
        {"name": "subagent_uses_run_with_capture", "tier": "tier2",
         "check": "bash_contains", "pattern": r"run_with_capture"},
    ],
    "code-reviewer": [
        {"name": "subagent_reads_target_script", "tier": "tier1",
         "check": "reads_file", "pattern": r"test_fixtures/code_reviewer/"},
        {"name": "subagent_writes_cr_script", "tier": "tier2",
         "check": "writes_to_dir", "pattern": r"scripts/cr/|_cr\d"},
        {"name": "subagent_uses_run_with_capture", "tier": "tier2",
         "check": "bash_contains", "pattern": r"run_with_capture"},
    ],
    "data-ingest": [
        {"name": "subagent_reads_data_file", "tier": "tier1",
         "check": "references_file", "pattern": r"test_fixtures/data_ingest/"},
        {"name": "subagent_writes_profiling_script", "tier": "tier2",
         "check": "writes_file", "pattern": r"\.py$"},
        {"name": "subagent_uses_run_with_capture", "tier": "tier2",
         "check": "bash_contains", "pattern": r"run_with_capture"},
    ],
}


def _run_check(spec: dict, tool_calls: list[dict]) -> tuple[bool, str]:
    """Dispatch a behavioral check based on its spec."""
    check_type = spec["check"]

    if check_type == "uses_tool_type":
        return _check_uses_tool_type(tool_calls, spec["tool_types"])
    elif check_type == "reads_file":
        return _check_reads_file(tool_calls, spec["pattern"])
    elif check_type == "references_file":
        return _check_references_file(tool_calls, spec["pattern"])
    elif check_type == "writes_file":
        return _check_writes_file(tool_calls, spec["pattern"])
    elif check_type == "writes_to_dir":
        return _check_writes_to_dir(tool_calls, spec["pattern"])
    elif check_type == "bash_contains":
        return _check_bash_contains(tool_calls, spec["pattern"])
    elif check_type == "loads_skill":
        return _check_loads_skill(tool_calls, spec["pattern"])
    elif check_type == "min_tool_calls":
        return _check_min_tool_calls(tool_calls, spec["min_count"])
    elif check_type == "reads_min_matching":
        return _check_reads_min_matching(tool_calls, spec["pattern"], spec["min_count"])
    else:
        return False, f"Unknown check type: {check_type}"


def score_subagent_behavior(
    session_id: str,
    expected_agent_type: str,
) -> list[CriterionResult]:
    """Score subagent behavior from its transcript.

    Finds the subagent transcript for the given session, extracts tool calls,
    and evaluates agent-type-specific behavioral criteria.

    Args:
        session_id: The parent session ID (subagent transcripts are nested under it).
        expected_agent_type: The expected subagent_type (e.g., "research-executor").

    Returns:
        List of CriterionResult objects for subagent behavior criteria.
        Returns an EMPTY list when no subagent transcript is found: dispatch
        failure is already captured by the dispatch-level criteria
        (agent_dispatched etc.), and emitting a structural transcript-found
        criterion here only noised Perfect/soft rates (removed 2026-06-10).
    """
    results = []

    transcripts = find_subagent_transcripts(session_id)

    if not transcripts:
        return results

    all_tool_calls = []
    for t in transcripts:
        all_tool_calls.extend(extract_subagent_tool_calls(t))

    # subagent_behavior_defined is a deliberate tripwire, NOT always-pass noise:
    # it fires (always as a FAILURE) only when a case expects an agent type
    # that BEHAVIOR_SPECS does not cover — i.e., a scoring gap that would
    # otherwise silently produce zero subagent criteria for a real dispatch.
    specs = BEHAVIOR_SPECS.get(expected_agent_type, [])
    if not specs:
        results.append(CriterionResult(
            name="subagent_behavior_defined",
            passed=False,
            tier="tier2",
            detail=f"No behavior specs defined for agent type '{expected_agent_type}'.",
        ))
        return results

    for spec in specs:
        passed, detail = _run_check(spec, all_tool_calls)
        results.append(CriterionResult(
            name=spec["name"],
            passed=passed,
            tier=spec["tier"],
            detail=detail,
        ))

    return results
