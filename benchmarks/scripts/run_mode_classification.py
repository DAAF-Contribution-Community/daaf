"""Mode classification benchmark with multi-dimensional transcript scoring and run archival.

Tests whether models correctly: (1) load the orchestrator skill, (2) classify
the correct engagement mode, (3) present a confirmation gate, and (4) do NOT
proceed prematurely past the gate.

Each test case starts a fresh cold-start session (CHECKPOINT_LINES = 0 — no
golden checkpoint; the case prompt is passed directly to `claude -p`), then
scores the model's response by parsing the session transcript for tool_use
blocks and assistant text.

Results are archived to a self-contained results folder with per-run transcripts.

Usage:
    python3 benchmarks/scripts/run_mode_classification.py
    python3 benchmarks/scripts/run_mode_classification.py --reps 1 --models haiku,sonnet
    python3 benchmarks/scripts/run_mode_classification.py --test-id mc-01,mc-05 --sequential
"""

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.harness.models import TestCase, ModelConfig, RunConfig
from benchmarks.harness.executor import execute_run
from benchmarks.harness.model_loader import load_models, filter_models, add_model_args
from benchmarks.harness.cost_estimator import estimate_batch_cost, format_estimate
from benchmarks.harness.artifacts import (
    add_preflight_arg,
    attach_schema_version,
    build_error_artifact,
    build_run_artifact,
    console_billing_label,
    cost_summary,
    format_coverage,
    manifest_provenance,
    model_manifest_entry,
    nullable_mean,
    run_preflight,
)
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
    find_benchmark_transcript,
    get_checkpoint_line_count,
)

# --- Config ---

BASE_DIR = Path("/daaf")
CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "mode_classification" / "cases.jsonl"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

LAUNCH_DELAY_SECONDS = 2

# Mode-specific reference files that should NOT be read before confirmation
MODE_REF_FILES = [
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

# Cold start: no golden checkpoint prefix to skip
CHECKPOINT_LINES = 0

# Keyword/pattern tables for the inline scoring below. Relocated here
# 2026-06-10 from scorers/deterministic/mode_classification.py when that
# module was deleted: its score_mode_classification() was dead code (this
# runner has always scored inline), and this runner was the only live
# consumer of these two tables.

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
    r"shall we (begin|start|get started)",
    r"shall I (begin|start|get started)",
    r"let'?s (begin|start|get started)",
    r"sound good",
    r"want me to",
    r"ready to (begin|start|proceed|get started)",
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


# --- Load config ---

def load_test_cases(path: Path) -> list[TestCase]:
    """Load test cases from cases.jsonl."""
    return TestCase.load_from_jsonl(path)


# --- Scoring ---

def extract_assistant_texts(transcript_path: Path, checkpoint_lines: int) -> list[str]:
    """Extract all assistant text blocks from transcript lines after the checkpoint."""
    texts = []
    with open(transcript_path) as f:
        lines = f.readlines()

    for line in lines[checkpoint_lines:]:
        try:
            record = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        if record.get("type") != "assistant":
            continue

        for block in record.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    texts.append(text)

    return texts


def score_orchestrator_skill_loaded(tool_calls: list[dict]) -> dict:
    """Criterion 1: Check that the daaf-orchestrator skill was loaded successfully."""
    for tc in tool_calls:
        if tc["name"] == "Skill" and tc.get("skill") == "daaf-orchestrator":
            if tc.get("succeeded", True):
                return {
                    "name": "orchestrator_skill_loaded",
                    "passed": True,
                    "detail": "daaf-orchestrator skill loaded successfully.",
                }
            else:
                return {
                    "name": "orchestrator_skill_loaded",
                    "passed": False,
                    "detail": "daaf-orchestrator skill call found but failed (is_error=true).",
                }

    return {
        "name": "orchestrator_skill_loaded",
        "passed": False,
        "detail": "No Skill tool call for daaf-orchestrator found in transcript.",
    }


def score_mode_correct(assistant_texts: list[str], expected_mode: str) -> dict:
    """Criterion 2: Check that the expected mode's keywords appear in assistant text.

    Also checks that no OTHER mode's keywords appear more prominently.
    """
    combined_text = " ".join(assistant_texts).lower()
    expected_keywords = MODE_KEYWORDS.get(expected_mode, [])

    # Count matches for expected mode
    expected_hits = sum(1 for kw in expected_keywords if kw.lower() in combined_text)
    mode_detected = expected_hits > 0

    # Check other modes for competing classifications
    other_modes_detected = []
    for mode_name, mode_kws in MODE_KEYWORDS.items():
        if mode_name == expected_mode:
            continue
        other_hits = sum(1 for kw in mode_kws if kw.lower() in combined_text)
        if other_hits > 0:
            other_modes_detected.append(f"{mode_name}({other_hits})")

    return {
        "name": "mode_correct",
        "passed": mode_detected,
        "detail": (
            f"Expected mode '{expected_mode}': "
            f"{'detected' if mode_detected else 'NOT detected'} "
            f"({expected_hits} keyword hits). "
            f"Other modes: {', '.join(other_modes_detected) or 'none'}."
        ),
    }


def score_confirmation_gate(assistant_texts: list[str], tool_calls: list[dict] = None) -> dict:
    """Criterion 3: Check that assistant text or AskUserQuestion tool contains a confirmation gate."""
    combined_text = " ".join(assistant_texts)
    matched_pattern = None

    for pattern in CONFIRMATION_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            matched_pattern = pattern
            break

    # Also check AskUserQuestion tool calls — some models present
    # confirmation gates via structured UI widgets instead of inline text.
    ask_user_gate = False
    if not matched_pattern and tool_calls:
        for tc in tool_calls:
            if tc.get("name") == "AskUserQuestion":
                raw = tc.get("raw_input", {})
                question_text = raw.get("question", "") + " " + str(raw.get("options", ""))
                for pattern in CONFIRMATION_PATTERNS:
                    if re.search(pattern, question_text, re.IGNORECASE):
                        matched_pattern = f"AskUserQuestion({pattern})"
                        ask_user_gate = True
                        break
                if not ask_user_gate:
                    ask_user_gate = True
                    matched_pattern = "AskUserQuestion(tool-based gate)"
                if ask_user_gate:
                    break

    return {
        "name": "confirmation_gate_present",
        "passed": matched_pattern is not None,
        "detail": (
            f"Confirmation gate found (matched: {matched_pattern})."
            if matched_pattern
            else "No confirmation gate pattern found in assistant text or AskUserQuestion tools."
        ),
    }


def score_no_premature_execution(tool_calls: list[dict]) -> dict:
    """Criterion 4: Check that no premature execution occurred.

    Premature execution means:
    - Reading mode-specific reference files (e.g., full-pipeline-mode.md)
    - Dispatching Agent tool calls (subagent launches)
    - Loading ANY skill other than daaf-orchestrator (e.g., data source skills)

    The daaf-orchestrator Skill load is EXPECTED and does NOT count as premature.
    """
    violations = []

    for tc in tool_calls:
        # Check for reading mode-specific reference files
        if tc["name"] == "Read" and tc.get("file_path"):
            filename = tc["file_path"].split("/")[-1]
            if filename in MODE_REF_FILES:
                violations.append(f"Read({filename})")

        # Check for Agent dispatches
        if tc["name"] == "Agent":
            agent_prompt = tc.get("raw_input", {}).get("prompt", "")[:80]
            violations.append(f"Agent({agent_prompt})")

        # Check for non-orchestrator Skill loads (e.g., data source skills)
        if tc["name"] == "Skill" and tc.get("skill"):
            skill_name = tc["skill"]
            if skill_name != "daaf-orchestrator":
                violations.append(f"Skill({skill_name})")

    return {
        "name": "no_premature_execution",
        "passed": len(violations) == 0,
        "detail": (
            "No premature tool calls detected."
            if not violations
            else f"Premature tool calls: {violations}"
        ),
    }


def score_run(session_id: str, expected_mode: str, checkpoint_lines: int) -> dict:
    """Score all 4 criteria for a single run by parsing the session transcript."""
    transcript_path = find_benchmark_transcript(session_id)
    if not transcript_path:
        return {
            "criteria": {
                "orchestrator_skill_loaded": {"name": "orchestrator_skill_loaded", "passed": False, "detail": "Transcript not found."},
                "mode_correct": {"name": "mode_correct", "passed": False, "detail": "Transcript not found."},
                "confirmation_gate_present": {"name": "confirmation_gate_present", "passed": False, "detail": "Transcript not found."},
                "no_premature_execution": {"name": "no_premature_execution", "passed": False, "detail": "Transcript not found."},
            },
            "transcript_path": None,
        }

    tool_calls = extract_new_tool_calls(transcript_path, checkpoint_lines)
    assistant_texts = extract_assistant_texts(transcript_path, checkpoint_lines)

    criteria = {
        "orchestrator_skill_loaded": score_orchestrator_skill_loaded(tool_calls),
        "mode_correct": score_mode_correct(assistant_texts, expected_mode),
        "confirmation_gate_present": score_confirmation_gate(assistant_texts, tool_calls),
        "no_premature_execution": score_no_premature_execution(tool_calls),
    }

    return {
        "criteria": criteria,
        "transcript_path": str(transcript_path),
    }


# --- Run + diagnose ---

def run_one(test_case: TestCase, model: ModelConfig, rep: int, sandbox_suffix: str, timeout_override=None):
    """Execute a single benchmark run with multi-dimensional scoring."""
    sandbox_dir = f"/daaf/benchmarks/_sandbox/run_{sandbox_suffix}"
    config = RunConfig(
        test_case=test_case,
        model=model,
        run_index=rep,
        sandbox_dir=sandbox_dir,
        timeout_override=timeout_override,
    )

    start = time.time()
    result = execute_run(config)
    elapsed = time.time() - start

    # Always attempt scoring if we have a session_id — even for timed-out runs
    if result.session_id:
        time.sleep(1)
        expected_mode = test_case.expected.get("mode", "")
        scored = score_run(result.session_id, expected_mode, CHECKPOINT_LINES)
    else:
        scored = {
            "criteria": {
                "orchestrator_skill_loaded": {"name": "orchestrator_skill_loaded", "passed": False, "detail": f"No session ID: {result.error}"},
                "mode_correct": {"name": "mode_correct", "passed": False, "detail": f"No session ID: {result.error}"},
                "confirmation_gate_present": {"name": "confirmation_gate_present", "passed": False, "detail": f"No session ID: {result.error}"},
                "no_premature_execution": {"name": "no_premature_execution", "passed": False, "detail": f"No session ID: {result.error}"},
            },
            "transcript_path": None,
        }

    return build_run_artifact(
        model,
        result,
        phase_fields={
            "case_id": test_case.id,
            "expected_mode": test_case.expected.get("mode", ""),
            "rep": rep,
            "criteria": scored["criteria"],
            "transcript_path": scored.get("transcript_path"),
        },
        duration_s=elapsed,
    )


def _error_result(test_case: TestCase, model: ModelConfig, rep: int, error_msg: str):
    """Build a safe result dict for a run that failed before returning data."""
    criteria = {
        "orchestrator_skill_loaded": {"name": "orchestrator_skill_loaded", "passed": False, "detail": f"Exception: {error_msg}"},
        "mode_correct": {"name": "mode_correct", "passed": False, "detail": f"Exception: {error_msg}"},
        "confirmation_gate_present": {"name": "confirmation_gate_present", "passed": False, "detail": f"Exception: {error_msg}"},
        "no_premature_execution": {"name": "no_premature_execution", "passed": False, "detail": f"Exception: {error_msg}"},
    }
    return build_error_artifact(
        model,
        test_case.id,
        rep,
        error_msg,
        phase_fields={
            "expected_mode": test_case.expected.get("mode", ""),
            "criteria": criteria,
            "transcript_path": None,
        },
    )


# --- Archival ---

def get_git_sha() -> str:
    """Get the current DAAF git commit SHA."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/daaf",
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def archive_results(all_results: list[dict], models: list[ModelConfig],
                    test_cases: list[TestCase], args, wall_time: float) -> Path:
    """Archive all run results, transcripts, and summary to a timestamped folder."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = BASE_DIR / "benchmarks" / "results" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    git_sha = get_git_sha()

    # --- Write manifest.json ---
    manifest = attach_schema_version({
        "benchmark": "mode_classification",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "daaf_git_sha": git_sha,
        **manifest_provenance(
            golden_checkpoints=[
                getattr(tc, "golden_checkpoint", None) for tc in test_cases
            ],
            run_records=all_results,
        ),
        "config": {
            "reps": args.reps,
            "parallel": not args.sequential,
            "launch_delay_s": args.delay,
            "timeout_override": args.timeout,
            "test_ids": args.test_id.split(",") if args.test_id else "all",
            "model_keys": args.models.split(",") if args.models else "all",
        },
        "models": [model_manifest_entry(m) for m in models],
        "cases": [
            {
                "id": tc.id,
                "subcategory": tc.subcategory,
                "expected_mode": tc.expected.get("mode", ""),
            }
            for tc in test_cases
        ],
    })
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # --- Write per-run results and copy transcripts ---
    for r in all_results:
        run_name = f"{r['case_id']}_{r['model'].replace(' ', '_')}_{r['rep']}"
        run_dir = runs_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write result.json for this run. The transcript is copied separately;
        # every other flat and schema-v2 field is preserved additively.
        result_data = {
            key: value for key, value in r.items()
            if key != "transcript_path"
        }
        with open(run_dir / "result.json", "w") as f:
            json.dump(result_data, f, indent=2)

        # Copy transcript if available
        transcript_src = r.get("transcript_path")
        if transcript_src and Path(transcript_src).exists():
            shutil.copy2(transcript_src, run_dir / "transcript.jsonl")

    # --- Write summary.json ---
    batch_cost = cost_summary(all_results)
    total_cost = batch_cost["total_cost_usd"]
    errored = sum(1 for r in all_results if r.get("error"))

    criterion_names = [
        "orchestrator_skill_loaded",
        "mode_correct",
        "confirmation_gate_present",
        "no_premature_execution",
    ]

    # Per-model pass rates
    model_summaries = {}
    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        rates = {}
        for crit in criterion_names:
            passed = sum(1 for r in rows if r["criteria"].get(crit, {}).get("passed", False))
            rates[crit] = {"passed": passed, "total": len(rows), "rate": passed / len(rows)}
        all_pass = sum(
            1 for r in rows
            if all(r["criteria"].get(c, {}).get("passed", False) for c in criterion_names)
        )
        rates["all_criteria"] = {"passed": all_pass, "total": len(rows), "rate": all_pass / len(rows)}
        model_cost = cost_summary(rows)
        model_summaries[model.name] = {
            "criteria": rates,
            "avg_cost_usd": model_cost["avg_cost_usd"],
            "accounting_coverage": model_cost["accounting_coverage"],
        }

    # Per-case pass rates
    case_summaries = {}
    for tc in test_cases:
        rows = [r for r in all_results if r["case_id"] == tc.id]
        if not rows:
            continue
        rates = {}
        for crit in criterion_names:
            passed = sum(1 for r in rows if r["criteria"].get(crit, {}).get("passed", False))
            rates[crit] = {"passed": passed, "total": len(rows), "rate": passed / len(rows)}
        case_summaries[tc.id] = {"expected_mode": tc.expected.get("mode", ""), "criteria": rates}

    # Tool failure summary
    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    runs_with_failures = sum(1 for r in all_results if r.get("tool_failures"))
    tool_failure_by_name = {}
    for r in all_results:
        for tf in r.get("tool_failures", []):
            name = tf.get("tool_name", "unknown")
            tool_failure_by_name[name] = tool_failure_by_name.get(name, 0) + 1

    summary = attach_schema_version({
        "total_runs": len(all_results),
        "total_cost_usd": total_cost,
        "accounting_coverage": batch_cost["accounting_coverage"],
        "wall_time_s": round(wall_time, 1),
        "errored_runs": errored,
        "tool_failures": {
            "total": total_tool_failures,
            "runs_affected": runs_with_failures,
            "by_tool": tool_failure_by_name,
        },
        "by_model": model_summaries,
        "by_case": case_summaries,
    })
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return output_dir


# --- Console output ---

def print_run_result(r: dict):
    """Print criterion results for a single run."""
    criteria = r.get("criteria", {})
    c1 = "PASS" if criteria.get("orchestrator_skill_loaded", {}).get("passed") else "FAIL"
    c2 = "PASS" if criteria.get("mode_correct", {}).get("passed") else "FAIL"
    c3 = "PASS" if criteria.get("confirmation_gate_present", {}).get("passed") else "FAIL"
    c4 = "PASS" if criteria.get("no_premature_execution", {}).get("passed") else "FAIL"

    print(f"\n--- {r['case_id']} | {r['model']} rep {r['rep']} ---")
    print(f"  Mode: {r['expected_mode']}")
    print(f"  orchestrator_skill={c1} | mode_correct={c2} | confirm_gate={c3} | no_premature={c4}")
    print(
        f"  Turns: {r['turns']} | Billing: {console_billing_label(r)} "
        f"| Duration: {r['duration_s']}s"
    )

    if r.get("error"):
        print(f"  ERROR: {r['error']}")

    # Print detail for any failures
    for crit_name in ["orchestrator_skill_loaded", "mode_correct", "confirmation_gate_present", "no_premature_execution"]:
        crit = criteria.get(crit_name, {})
        if not crit.get("passed", False):
            print(f"  [{crit_name}] {crit.get('detail', 'no detail')}")

    tool_failures = r.get("tool_failures", [])
    if tool_failures:
        print(f"  Tool failures ({len(tool_failures)}):")
        for tf in tool_failures[:5]:
            print(f"    {tf.get('tool_name', '?')}: {tf.get('content', '')[:120]}")


def print_summary(all_results: list[dict], models: list[ModelConfig],
                  test_cases: list[TestCase], wall_time: float):
    """Print the summary table to console."""
    criterion_names = [
        "orchestrator_skill_loaded",
        "mode_correct",
        "confirmation_gate_present",
        "no_premature_execution",
    ]
    short_names = ["orch_skill", "mode", "gate", "no_premature"]

    print(f"\n{'='*90}")
    print("SUMMARY BY MODEL")
    print(f"{'='*90}")
    header = f"{'Model':<20} | {'orch_skill':<11} | {'mode':<11} | {'gate':<11} | {'no_premature':<13} | {'all_4':<8} | {'avg$':<8}"
    print(header)
    print("-" * 95)

    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        n = len(rows)
        counts = []
        for crit in criterion_names:
            passed = sum(1 for r in rows if r["criteria"].get(crit, {}).get("passed", False))
            counts.append(passed)
        all_pass = sum(
            1 for r in rows
            if all(r["criteria"].get(c, {}).get("passed", False) for c in criterion_names)
        )
        avg_cost = nullable_mean(r["computed_cost_usd"] for r in rows)
        avg_label = (
            f"${avg_cost:.3f}"
            if avg_cost is not None
            else "included"
        )
        print(
            f"{model.name:<20} | "
            f"{counts[0]}/{n:<9} | "
            f"{counts[1]}/{n:<9} | "
            f"{counts[2]}/{n:<9} | "
            f"{counts[3]}/{n:<11} | "
            f"{all_pass}/{n:<6} | "
            f"{avg_label}"
        )

    # Summary by case (if multiple cases)
    if len(test_cases) > 1:
        print(f"\n{'='*90}")
        print("SUMMARY BY CASE")
        print(f"{'='*90}")
        header = f"{'Case':<10} | {'Mode':<28} | {'orch_skill':<11} | {'mode':<11} | {'gate':<11} | {'no_premature':<13}"
        print(header)
        print("-" * 95)

        for tc in test_cases:
            rows = [r for r in all_results if r["case_id"] == tc.id]
            if not rows:
                continue
            n = len(rows)
            counts = []
            for crit in criterion_names:
                passed = sum(1 for r in rows if r["criteria"].get(crit, {}).get("passed", False))
                counts.append(passed)
            expected_mode = tc.expected.get("mode", "")
            print(
                f"{tc.id:<10} | "
                f"{expected_mode:<28} | "
                f"{counts[0]}/{n:<9} | "
                f"{counts[1]}/{n:<9} | "
                f"{counts[2]}/{n:<9} | "
                f"{counts[3]}/{n:<11}"
            )

    batch_cost = cost_summary(all_results)
    total_cost = batch_cost["total_cost_usd"]
    total_label = f"${total_cost:.2f}" if total_cost is not None else "cost unavailable"
    errored = sum(1 for r in all_results if r.get("error"))
    error_note = f" ({errored} errored/timed-out)" if errored else ""
    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    tf_note = f" | {total_tool_failures} tool failures" if total_tool_failures else ""
    coverage = format_coverage(batch_cost["accounting_coverage"])
    print(
        f"\nTotal: {len(all_results)} runs{error_note} | {total_label} "
        f"| accounting: {coverage} | {wall_time:.0f}s wall time{tf_note}"
    )


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Mode classification benchmark runner")
    parser.add_argument("--reps", type=int, default=3,
                        help="Number of repetitions per case x model (default: 3)")
    add_model_args(parser)
    parser.add_argument("--test-id", type=str, default=None,
                        help="Comma-separated test case IDs to run (default: all)")
    parser.add_argument("--sequential", action="store_true",
                        help="Run sequentially instead of parallel")
    parser.add_argument("--delay", type=float, default=LAUNCH_DELAY_SECONDS,
                        help="Seconds between parallel launches (default: 2)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Per-run timeout in seconds (Phase 1 default: 120; "
                             "standardized 2026-07-10, replacing cost-tier defaults)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip cost confirmation prompt")
    add_preflight_arg(parser)
    args = parser.parse_args()

    # Load and filter models
    all_models = load_models(MODELS_FILE)
    model_keys = args.models.split(",") if args.models else None
    models = filter_models(all_models, model_keys=model_keys, provider=args.provider)
    if not models:
        print("ERROR: No valid models selected.")
        sys.exit(1)

    # Load test cases
    all_cases = load_test_cases(CASES_FILE)

    if args.test_id:
        test_ids = {t.strip() for t in args.test_id.split(",")}
        test_cases = [tc for tc in all_cases if tc.id in test_ids]
        if not test_cases:
            print(f"ERROR: No test cases matched IDs: {test_ids}")
            print(f"Available: {', '.join(tc.id for tc in all_cases)}")
            sys.exit(1)
    else:
        test_cases = all_cases

    # Batch route validation is the first action after model/case selection.
    # The preflight-only branch returns before estimates, run-list/sandbox
    # construction, executor calls, and result-directory creation.
    if run_preflight(models, preflight_only=args.preflight_only):
        return

    # Mode classification uses cold starts — no golden checkpoints.
    # Each run is a fresh `claude -p` session so we test the full bootstrap +
    # classification behavior. Golden checkpoints are reserved for post-confirmation
    # protocol tests (the legacy run_checkpoint_comparison.py has been retired).

    total_runs = len(test_cases) * len(models) * args.reps
    print(f"Mode Classification Benchmark")
    print(f"Cases: {len(test_cases)} | Models: {', '.join(m.name for m in models)}")
    print(f"Reps: {args.reps} | Total runs: {total_runs}")
    mode_str = "sequential" if args.sequential else f"parallel (delay={args.delay}s)"
    timeout_str = f" | timeout={args.timeout}s" if args.timeout else ""
    print(f"Mode: {mode_str}{timeout_str}")

    case_ids = [tc.id for tc in test_cases] if args.test_id else None
    est = estimate_batch_cost(models, "mode_classification", case_ids=case_ids, reps=args.reps)
    print(f"\n{format_estimate(est)}\n")

    if not args.yes and est["total"] > 0.50:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print(f"{'='*90}")
    sys.stdout.flush()

    # Build run list: case x model x rep
    runs = []
    for tc in test_cases:
        for model in models:
            for rep in range(args.reps):
                suffix = f"{tc.id}_{model.name.replace(' ', '_')}_{rep}"
                runs.append((tc, model, rep, suffix))

    all_results = []
    start_time = time.time()

    if args.sequential:
        for tc, model, rep, suffix in runs:
            try:
                r = run_one(tc, model, rep, suffix, timeout_override=args.timeout)
            except Exception as e:
                r = _error_result(tc, model, rep, f"{type(e).__name__}: {e}")
            all_results.append(r)
            print_run_result(r)
            sys.stdout.flush()
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runs)) as pool:
            futures = {}
            for i, (tc, model, rep, suffix) in enumerate(runs):
                future = pool.submit(run_one, tc, model, rep, suffix, timeout_override=args.timeout)
                futures[future] = (tc, model, rep)
                if i < len(runs) - 1:
                    time.sleep(args.delay)

            for future in concurrent.futures.as_completed(futures):
                tc, model, rep = futures[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = _error_result(tc, model, rep, f"{type(e).__name__}: {e}")
                all_results.append(r)
                print_run_result(r)
                sys.stdout.flush()

    wall_time = time.time() - start_time

    # Sort results by case order, then model order, then rep
    case_order = {tc.id: i for i, tc in enumerate(test_cases)}
    model_order = {m.name: i for i, m in enumerate(models)}
    all_results.sort(key=lambda r: (case_order.get(r["case_id"], 99), model_order.get(r["model"], 99), r["rep"]))

    # Print summary
    print_summary(all_results, models, test_cases, wall_time)

    # Archive results
    output_dir = archive_results(all_results, models, test_cases, args, wall_time)
    print(f"\nResults archived to: {output_dir}")


if __name__ == "__main__":
    main()
