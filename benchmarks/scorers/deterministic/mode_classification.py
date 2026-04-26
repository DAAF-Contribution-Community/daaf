"""Deterministic scorer for mode classification test cases.

Checks whether the model correctly classified the engagement mode
and produced a confirmation gate in its response. All checks are
Tier 1 (pure deterministic, no LLM involvement).
"""

import re

from benchmarks.harness.models import CriterionResult, RunResult


# Keywords that indicate a specific mode classification.
# Multiple variants per mode to handle natural language variation.
MODE_KEYWORDS: dict[str, list[str]] = {
    "data_onboarding": [
        "data onboarding",
        "onboarding mode",
        "profile your data",
        "profile the data",
        "profiling phases",
        "onboard",
    ],
    "data_lookup": [
        "data lookup",
        "lookup mode",
        "look that up",
        "focused answer",
        "direct answer",
    ],
    "data_discovery": [
        "data discovery",
        "discovery mode",
        "read-only exploration",
        "no code, no downloads",
        "explore what",
    ],
    "ad_hoc_collaboration": [
        "ad hoc",
        "ad-hoc",
        "collaboration mode",
        "thought partner",
        "flexible",
        "working session",
    ],
    "full_pipeline": [
        "full pipeline",
        "complete pipeline",
        "comprehensive mode",
        "most comprehensive",
        "5 phases",
        "five phases",
        "4 checkpoints",
        "four checkpoints",
        "research pipeline",
    ],
    "revision_and_extension": [
        "revision",
        "extension mode",
        "revise",
        "existing analysis",
        "new version",
        "original untouched",
    ],
    "reproducibility_verification": [
        "reproducibility",
        "verification mode",
        "reproduce",
        "re-run",
        "rerun",
        "reproduction report",
    ],
    "framework_development": [
        "framework development",
        "framework mode",
        "modify daaf",
        "framework components",
        "skills, agents",
        "create a skill",
    ],
    "user_support": [
        "user support",
        "support mode",
        "answer your questions",
        "how it works",
        "troubleshooting",
    ],
}

# Patterns indicating a confirmation gate (must end with a question)
CONFIRMATION_PATTERNS = [
    r"shall I proceed",
    r"shall we proceed",
    r"sound good",
    r"want me to",
    r"ready to",
    r"go ahead\??",
    r"proceed\?",
    r"confirm",
    r"does this .* look right",
    r"any adjustments",
    r"approach .* differently",
    r"shall I",
    r"want to (try|proceed|start|begin)",
    r"proceed with",
    r"do you want",
    r"would you like",
    r"should I",
]


def score_mode_classification(
    run_result: RunResult,
    expected: dict,
) -> list[CriterionResult]:
    """Score a mode classification test case.

    Args:
        run_result: The raw result from executing the test case.
        expected: The expected outcomes dict from the test case.

    Returns:
        List of CriterionResult for each scoring criterion.
    """
    results = []
    response = run_result.response_text
    response_lower = response.lower()

    # --- Criterion 1: mode_correct ---
    expected_mode = expected.get("mode", "")
    keywords = MODE_KEYWORDS.get(expected_mode, [])

    mode_detected = any(kw.lower() in response_lower for kw in keywords)

    # Also check if any OTHER mode was more prominently classified
    other_modes_detected = []
    for mode_name, mode_kws in MODE_KEYWORDS.items():
        if mode_name == expected_mode:
            continue
        if any(kw.lower() in response_lower for kw in mode_kws):
            other_modes_detected.append(mode_name)

    results.append(CriterionResult(
        name="mode_correct",
        passed=mode_detected,
        tier="tier1",
        detail=(
            f"Expected mode '{expected_mode}'. "
            f"{'Detected' if mode_detected else 'NOT detected'} in response. "
            f"Other modes detected: {other_modes_detected or 'none'}"
        ),
    ))

    # --- Criterion 2: confirmation_gate_present ---
    gate_found = any(
        re.search(pattern, response, re.IGNORECASE)
        for pattern in CONFIRMATION_PATTERNS
    )

    results.append(CriterionResult(
        name="confirmation_gate_present",
        passed=gate_found,
        tier="tier1",
        detail=(
            "Confirmation gate "
            f"{'found' if gate_found else 'NOT found'} in response."
        ),
    ))

    # --- Criterion 3: no_premature_execution ---
    # Check audit entries for tool calls that should not happen before confirmation.
    # In mode classification, the model should NOT read mode-specific reference files
    # or dispatch subagents in the same turn as the classification.
    premature_tools = []
    mode_ref_files = [
        "full-pipeline-mode.md",
        "data-onboarding-mode.md",
        "data-lookup-mode.md",
        "data-discovery-mode.md",
        "ad-hoc-collaboration-mode.md",
        "revision-and-extension-mode.md",
        "reproducibility-verification-mode.md",
        "framework-development-mode.md",
        "user-support-mode.md",
    ]

    for entry in run_result.audit_entries:
        tool = entry.get("tool", "")
        target = entry.get("target", "")

        # Check for reading mode-specific reference files
        if tool == "Read" and any(ref in target for ref in mode_ref_files):
            premature_tools.append(f"Read({target})")

        # Check for Agent dispatches (subagent launches)
        if tool == "Agent":
            premature_tools.append(f"Agent({target[:80]})")

    results.append(CriterionResult(
        name="no_premature_execution",
        passed=len(premature_tools) == 0,
        tier="tier1",
        detail=(
            "No premature tool calls."
            if not premature_tools
            else f"Premature tool calls: {premature_tools}"
        ),
    ))

    # --- Criterion 4: reasoning_present (soft) ---
    # Check that the response includes some reasoning for the classification,
    # not just a bare mode name.
    reasoning_indicators = [
        "because",
        "since",
        "this is",
        "classification",
        "sounds like",
        "this falls under",
        "i'd classify",
        "this request",
        "you're asking",
        "you want to",
        "your request",
    ]
    reasoning_found = any(ind in response_lower for ind in reasoning_indicators)

    results.append(CriterionResult(
        name="reasoning_present",
        passed=reasoning_found,
        tier="tier1",
        detail=(
            "Classification reasoning "
            f"{'found' if reasoning_found else 'NOT found'} in response."
        ),
    ))

    return results
