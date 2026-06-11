"""Skill routing scorer: evaluates skill loading and reference routing test results.

Scores Phase 4 (skill_routing) runs: a model resumes from the Ad Hoc Collaboration
golden checkpoint, receives a brainstorming prompt, and is scored on whether it
loads exactly the skills (Skill tool calls) and reads exactly the skill reference
files (Read tool calls) that the DAAF skills' own routing directives prescribe.

All scoring is MAIN-TRANSCRIPT-ONLY: Phase 4 runs disallow the Agent tool, so no
subagent transcripts exist (see benchmarks/README.md § 2, Phase 4).

Matching rules (see benchmarks/README.md § 6, Phase 4 scoring):
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

Name-mention matching rules for required_skills_engaged (tier2):
- A required skill is "engaged" when it was EITHER successfully loaded via the
  Skill tool post-checkpoint OR name-mentioned in user-visible assistant text
  post-checkpoint (text blocks only — thinking and tool_use blocks excluded).
  Engagement is a strict superset of loading: engaged = loaded OR mentioned,
  so passing required_skills_loaded always implies passing this criterion.
  The engaged-vs-loaded gap quantifies "acknowledged the right skill but
  deferred the load" behavior.
- Matching is case-insensitive ("Plotly", "GeoPandas" count).
- Per-skill pattern: word-boundary match on the skill name with hyphens
  generalized to hyphen-or-whitespace, so "science-communication" matches
  "science communication" and "scikit-learn" matches "scikit learn".
- Alias map: "scikit-learn" additionally matches "sklearn" (the overwhelmingly
  common informal name; without it the criterion would under-count).
- Mentions inside backtick code spans and file paths COUNT as engagement
  (deliberate: regex \b treats "`" and "/" as non-word, so "`pyfixest`" and
  ".claude/skills/pyfixest/references/..." both match — a model narrating
  which skill's references to consult IS engaging with the skill).
- Known mild false positive: "science communication" is ordinary English, so
  sr-14 (exec-summary prompts) can register incidental generic mentions as
  engagement. Accepted for a soft tier2 criterion.
- Known mild limitation: assistant text blocks are joined with a newline
  separator before matching, and the hyphen-or-whitespace class in the
  mention pattern can match across it, so a skill name split across two
  adjacent text blocks (e.g., one block ending "scikit" and the next
  beginning "learn") could theoretically register as a mention. Exotic in
  practice; accepted for a soft tier2 criterion.

Reuses extract_new_tool_calls() and extract_new_assistant_text() from
checkpoint_adherence for post-checkpoint slicing, tool_result success
cross-referencing, and user-visible text extraction.
"""

import re
from pathlib import Path

from benchmarks.harness.models import CriterionResult
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_assistant_text,
    extract_new_tool_calls,
)

# Informal alternate names that count as a mention of the canonical skill name
# (see module docstring, name-mention matching rules).
SKILL_MENTION_ALIASES = {
    "scikit-learn": ["sklearn"],
}

def _basename(file_path: str) -> str:
    """Return the basename of a Read file_path (basename-only matching rule)."""
    return file_path.split("/")[-1]


def _skill_mention_pattern(skill_name: str) -> re.Pattern:
    """Compile the case-insensitive mention pattern for one skill name.

    Hyphens in the name (and its aliases) match hyphen-or-whitespace, per the
    module docstring's name-mention matching rules. Escaping is done per
    hyphen-separated part so behavior is independent of re.escape's treatment
    of "-" across Python versions.
    """
    variants = [skill_name] + SKILL_MENTION_ALIASES.get(skill_name, [])
    alternatives = [
        r"[-\s]".join(re.escape(part) for part in variant.split("-"))
        for variant in variants
    ]
    return re.compile(r"\b(?:" + "|".join(alternatives) + r")\b", re.IGNORECASE)


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
        List of CriterionResult — per section 3.1 of the plan, in emission
        order: required_skills_loaded (tier1), required_skills_engaged
        (tier2), required_refs_read (tier1), expected_refs_read (tier2,
        OMITTED when the case has no expected_refs — see inline comment),
        routing_order, no_forbidden_skills (both tier2).
        required_skills_engaged (loaded OR name-mentioned in user-visible
        text) is recorded in the plan (section 3.1 criteria table; section 9,
        decision 7); see the module docstring for its matching rules.
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

    # --- required_skills_engaged (tier2) ---
    # Soft superset of required_skills_loaded: a required skill counts as
    # engaged when it was successfully loaded OR name-mentioned in
    # user-visible assistant text (see module docstring for matching rules).
    # The engaged-vs-loaded gap is the headline diagnostic for "acknowledged
    # the right skill but deferred the load" behavior.
    assistant_text = "\n".join(
        extract_new_assistant_text(Path(transcript_path), checkpoint_line_count)
    )
    mentioned_skills = [
        s for s in required_skills
        if _skill_mention_pattern(s).search(assistant_text)
    ]
    missing_engaged = [
        s for s in required_skills
        if s not in loaded_skills and s not in mentioned_skills
    ]
    results.append(CriterionResult(
        name="required_skills_engaged",
        passed=not missing_engaged,
        tier="tier2",
        detail=(
            f"All required skills engaged: {required_skills} "
            f"(loaded: {loaded_skills or 'none'}, "
            f"mentioned: {mentioned_skills or 'none'})"
            if not missing_engaged
            else f"Skill(s) neither loaded nor mentioned: {missing_engaged} "
                 f"(loaded: {loaded_skills or 'none'}, "
                 f"mentioned: {mentioned_skills or 'none'})"
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

    # --- expected_refs_read (tier2, conditional) ---
    # Emitted ONLY when the case defines a non-empty expected_refs list. Cases
    # without secondary refs get NO criterion — omission, not an automatic
    # pass — because a criterion that can only ever pass for a case dilutes
    # Perfect/soft rates (2026-06-10; cf. the removed no_spurious_skill_reload,
    # plan section 9 decision 6). Aggregations (runner summary, rescore tool,
    # viewer) all key off per-run criteria sets, and rescore_skill_routing.py's
    # merge/determinism logic tolerates per-run omission, so no consumer
    # assumes this criterion exists.
    expected_refs = expected.get("expected_refs", [])
    if expected_refs:
        missing_expected = [r for r in expected_refs if r not in read_basenames]
        results.append(CriterionResult(
            name="expected_refs_read",
            passed=not missing_expected,
            tier="tier2",
            detail=(
                f"All expected refs read: {expected_refs}"
                if not missing_expected
                else f"Missing expected ref(s): {missing_expected}"
            ),
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
