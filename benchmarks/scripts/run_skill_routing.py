"""Skill routing benchmark (Phase 4) with golden checkpoint scoring and run archival.

Tests whether models load exactly the skills (Skill tool) and read exactly the
skill reference files (Read tool) that the DAAF skills' own routing directives
prescribe. Each test case resumes from the Phase 3 Ad Hoc Collaboration golden
checkpoint (daaf-orchestrator loaded, ad-hoc-collaboration-mode.md read,
data-scientist skill loaded) and poses one brainstorming question constructed so
the routing text in the skills makes one specific set of Skill loads and
reference Reads objectively correct.

The Agent tool is DISALLOWED for all Phase 4 runs (disallowed_tools=["Agent"]),
so no subagent transcripts exist and all scoring is main-transcript-only. See
benchmarks/README.md § 2 (Phase 4) and § 6.

Scoring uses score_skill_routing() from skill_routing.py, which checks
required_skills_loaded, required_refs_read, expected_refs_read, routing_order,
and no_forbidden_skills criteria.

Phase 4 has NO fixtures: prompts are pure brainstorming text with no file
references, so the fixture staging/restore machinery of run_dispatch_compliance.py
is intentionally absent here.

Results are archived to a self-contained results folder with per-run transcripts.

Usage:
    python3 benchmarks/scripts/run_skill_routing.py
    python3 benchmarks/scripts/run_skill_routing.py --reps 1 --models haiku,sonnet
    python3 benchmarks/scripts/run_skill_routing.py --test-id sr-01,sr-09 --sequential
"""

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.harness.models import TestCase, ModelConfig, RunConfig
from benchmarks.harness.executor import execute_run
from benchmarks.harness.checkpoint_manager import cleanup_sandbox
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
from benchmarks.scorers.deterministic.skill_routing import (
    score_skill_routing,
)
from benchmarks.scorers.deterministic.error_classification import compute_error_counts

# --- Config ---

BASE_DIR = Path("/daaf")
CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "skill_routing" / "cases.jsonl"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

LAUNCH_DELAY_SECONDS = 2
# Cap on simultaneously in-flight runs. Per-run state (sandbox dir, uuid4 session
# ids, transcript dirs) is fully isolated, so the cap is purely a resource-
# pressure guard, not a correctness one. --delay staggers submits independently.
MAX_CONCURRENT_RUNS = 5

# Serializes the progressive rollup (per-run archive write + summary/manifest
# rewrite). In the parallel path the as_completed loop already collects results
# on the main thread one at a time, but the lock makes the invariant explicit and
# keeps the finalizer safe against any future concurrent caller.
_ARCHIVE_LOCK = threading.Lock()


# --- Load config ---

def load_test_cases(path: Path) -> list[TestCase]:
    """Load test cases from cases.jsonl."""
    return TestCase.load_from_jsonl(path)


# --- Scoring ---

def score_run(session_id: str, test_case: TestCase) -> dict:
    """Score a single run by extracting tool calls from the transcript and
    delegating to score_skill_routing().

    Returns dict with 'criteria' (list of CriterionResult dicts) and
    'transcript_path'.
    """
    transcript_path = find_benchmark_transcript(session_id)
    if not transcript_path:
        return {
            "criteria": [
                {
                    "name": "transcript_found",
                    "passed": False,
                    "tier": "tier1",
                    "detail": "Transcript not found for session.",
                }
            ],
            "transcript_path": None,
        }

    # Get checkpoint line count from this test case's golden file
    golden_path = BASE_DIR / test_case.golden_checkpoint
    checkpoint_lines = get_checkpoint_line_count(golden_path)

    # Score using the skill routing scorer (main transcript only — Agent
    # tool is disallowed, so no subagent transcripts exist)
    criterion_results = score_skill_routing(
        str(transcript_path), checkpoint_lines, test_case.expected
    )

    # Convert CriterionResult objects to dicts for JSON serialization
    criteria_dicts = [
        {
            "name": cr.name,
            "passed": cr.passed,
            "tier": cr.tier,
            "detail": cr.detail,
        }
        for cr in criterion_results
    ]

    # Real post-checkpoint tool-call count (all tool names, including failed
    # calls). Re-parses the transcript — acceptable for this harness; the
    # scorer's API is kept transcript-path-based on purpose.
    tool_call_count = len(
        extract_new_tool_calls(Path(transcript_path), checkpoint_lines)
    )

    return {
        "criteria": criteria_dicts,
        "transcript_path": str(transcript_path),
        "tool_call_count": tool_call_count,
    }


# --- Run + diagnose ---

def run_one(test_case: TestCase, model: ModelConfig, rep: int,
            sandbox_suffix: str, timeout_override=None, watchdog_poll=60,
            stall_threshold=330, stall_retries=1):
    """Execute a single benchmark run with checkpoint scoring.

    Run-lifecycle watchdog (Dispatch B): STALL DETECTION ONLY — no score-complete
    early stop. This phase's ``no_forbidden_skills`` criterion is a monotone-FAIL
    negative (it starts PASS and can only flip to FAIL when the model later loads
    a forbidden skill). Early-stopping the moment all criteria pass would lock in
    that not-yet-violated negative and mask a later forbidden-skill load, so
    early stop is deliberately NOT wired here. Stall detection is safe and
    enabled; a stalled run is relaunched from a fresh sandbox up to
    ``stall_retries`` times.
    """
    sandbox_dir = f"/daaf/benchmarks/_sandbox/run_{sandbox_suffix}"

    attempt = 0
    # Accumulate each stalled attempt's diagnostics so a run that stalled once
    # then passed is legible from the archive alone (previously console-only).
    # Carried onto the FINAL result.json as an additive stall_attempts field.
    stall_attempts = []
    while True:
        # Disallow the Agent tool entirely (replaces the default git Bash-pattern
        # deny list): Phase 4 scoring is main-transcript-only, and brainstorming
        # questions are direct-answer territory per ad-hoc-collaboration-mode.md.
        # Whole-tool disallow by exact name works reliably (unlike Bash sub-pattern
        # deny rules — see benchmarks/README.md section 11, Limitation 1).
        config = RunConfig(
            test_case=test_case,
            model=model,
            run_index=rep,
            sandbox_dir=sandbox_dir,
            disallowed_tools=["Agent"],
            timeout_override=timeout_override,
            stall_detection=True,
            watchdog_poll_seconds=watchdog_poll,
            stall_threshold_seconds=stall_threshold,
        )

        start = time.time()
        result = execute_run(config)
        elapsed = time.time() - start

        if getattr(result, "stalled", False):
            stall_attempts.append({
                "attempt": attempt,
                "stall_diagnostics": dict(result.stall_diagnostics or {}),
            })
        if getattr(result, "stalled", False) and attempt < stall_retries:
            print(
                f"STALL [{test_case.id} | {model.name} | rep {rep}] attempt "
                f"{attempt + 1}: {result.stall_diagnostics}; relaunching from a "
                f"fresh sandbox (retry {attempt + 1}/{stall_retries})."
            )
            if test_case.golden_checkpoint and result.session_id:
                cleanup_sandbox(result.session_id)
            attempt += 1
            continue
        break

    stall_relaunch_count = attempt

    # Always attempt scoring if we have a session_id — even for timed-out runs,
    # the live session file may contain partial but scorable transcript data.
    if result.session_id:
        time.sleep(1)
        scored = score_run(result.session_id, test_case)
    else:
        scored = {
            "criteria": [
                {
                    "name": "run_completed",
                    "passed": False,
                    "tier": "tier1",
                    "detail": f"No session ID: {result.error}",
                }
            ],
            "transcript_path": None,
            "tool_call_count": 0,
        }

    # Archive transcript BEFORE cleanup deletes it. The subagents copy is a
    # harmless no-op safeguard: with Agent disallowed no subagent dir should
    # exist, but if the disallow ever failed, the evidence is preserved.
    archived_transcript = None
    if result.session_id:
        transcript_src = scored.get("transcript_path")
        if transcript_src and Path(transcript_src).exists():
            archive_dir = Path(f"/daaf/benchmarks/_sandbox/transcripts/{result.session_id}")
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(transcript_src, archive_dir / "transcript.jsonl")
            archived_transcript = str(archive_dir / "transcript.jsonl")
            subagent_dir = Path.home() / ".claude" / "projects" / "-daaf" / result.session_id / "subagents"
            if subagent_dir.exists():
                shutil.copytree(subagent_dir, archive_dir / "subagents", dirs_exist_ok=True)

    # Classify error-bearing tool results (parent + any archived subagent
    # transcripts) into hook-block vs genuine-failure buckets before cleanup
    # removes the live transcripts. Additive diagnostic only.
    subagent_transcripts = []
    if archived_transcript:
        sub_dir = Path(archived_transcript).parent / "subagents"
        if sub_dir.exists():
            subagent_transcripts = list(sub_dir.rglob("*.jsonl"))
    error_counts = compute_error_counts(
        result.tool_failures, subagent_transcripts=subagent_transcripts
    )

    # Clean up checkpoint sandbox AFTER archiving
    if test_case.golden_checkpoint:
        cleanup_sandbox(result.session_id)

    return build_run_artifact(
        model,
        result,
        phase_fields={
            "case_id": test_case.id,
            "subcategory": test_case.subcategory,
            "rep": rep,
            "criteria": scored["criteria"],
            "error_counts": error_counts,
            "transcript_path": archived_transcript or scored.get("transcript_path"),
            "tool_call_count": scored.get("tool_call_count", 0),
            "stall_relaunch_count": stall_relaunch_count,
            "stall_attempts": stall_attempts,
        },
        duration_s=elapsed,
    )


def _error_result(test_case: TestCase, model: ModelConfig, rep: int, error_msg: str):
    """Build a safe result dict for a run that failed before returning data."""
    criteria = [
        {
            "name": "run_completed",
            "passed": False,
            "tier": "tier1",
            "detail": f"Exception: {error_msg}",
        }
    ]
    return build_error_artifact(
        model,
        test_case.id,
        rep,
        error_msg,
        phase_fields={
            "subcategory": test_case.subcategory,
            "criteria": criteria,
            "error_counts": {
                "hook_blocks": 0,
                "tool_failures": 0,
                "tool_failures_unclassified": 0,
            },
            "transcript_path": None,
            "tool_call_count": 0,
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


def _write_json_atomic(path: Path, obj) -> None:
    """Write JSON to a sibling .tmp then os.replace() over the target.

    Atomicity matters for the progressive rollup: a reader (or a kill) never sees
    a half-written summary.json/manifest.json — the file either holds the prior
    complete rollup or the new complete one.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def archive_results(all_results: list[dict], models: list[ModelConfig],
                    test_cases: list[TestCase], args, wall_time: float,
                    output_dir: Path = None, partial: bool = False,
                    expected_n: int = None, git_sha: str = None,
                    batch_token: str = None, batch_pid: int = None) -> Path:
    """Archive run results, transcripts, and rollups to a timestamped folder.

    Progressive by design (2026-07 redesign): called once before the pool with
    ``all_results=[]`` to create the folder and seed manifest.json + an initial
    ``partial`` summary.json, then re-invoked after every completed run over the
    completed-so-far set, and finally once more with ``partial=False`` when all
    runs finished. Per-run artifact writes are existence-guarded so re-invocation
    is cheap (each run's files are written exactly once); manifest/summary are
    recomputed and atomically rewritten each call. The whole body runs under
    ``_ARCHIVE_LOCK`` so concurrent callers cannot interleave writes.
    """
    with _ARCHIVE_LOCK:
        return _archive_results_locked(
            all_results, models, test_cases, args, wall_time,
            output_dir, partial, expected_n, git_sha, batch_token, batch_pid,
        )


def _archive_results_locked(all_results, models, test_cases, args, wall_time,
                            output_dir, partial, expected_n, git_sha,
                            batch_token=None, batch_pid=None) -> Path:
    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        # Cross-process uniqueness: two batches starting the same wall-clock
        # second would otherwise collide on results/{timestamp} and cross-write
        # each other's manifest/summary. The short token disambiguates while the
        # LEADING timestamp stays intact so viewer/rerun-queue lexicographic
        # ordering and glob discovery are unaffected.
        tok = batch_token or uuid.uuid4().hex[:6]
        output_dir = BASE_DIR / "benchmarks" / "results" / f"{timestamp}_{tok}"
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    if git_sha is None:
        git_sha = get_git_sha()

    # --- Write manifest.json ---
    manifest = attach_schema_version({
        "benchmark": "skill_routing",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "daaf_git_sha": git_sha,
        # Cross-batch forensics: the per-batch uniqueness token (also the results
        # dir-name suffix and sandbox-suffix tail) and the launching process PID.
        "batch_token": batch_token or output_dir.name.rsplit("_", 1)[-1],
        "batch_pid": batch_pid if batch_pid is not None else os.getpid(),
        **manifest_provenance(
            golden_checkpoints=[tc.golden_checkpoint for tc in test_cases],
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
                "golden_checkpoint": tc.golden_checkpoint,
                "expected": tc.expected,
            }
            for tc in test_cases
        ],
    })
    _write_json_atomic(output_dir / "manifest.json", manifest)

    # --- Write per-run results and copy transcripts (existence-guarded) ---
    # Each run's artifacts are immutable once written, so re-invocation across
    # progressive rollups writes each run exactly once (the result.json guard).
    for r in all_results:
        run_name = f"{r['case_id']}_{r['model'].replace(' ', '_')}_{r['rep']}"
        run_dir = runs_dir / run_name
        if (run_dir / "result.json").exists():
            continue
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write every flat, phase-specific, and schema-v2 field. Transcript
        # content is copied separately below rather than embedded in result.json.
        result_data = {
            key: value for key, value in r.items()
            if key != "transcript_path"
        }
        _write_json_atomic(run_dir / "result.json", result_data)

        # Copy transcript if available
        transcript_src = r.get("transcript_path")
        if transcript_src and Path(transcript_src).exists():
            shutil.copy2(transcript_src, run_dir / "transcript.jsonl")

    # --- Collect all unique criterion names across all runs ---
    all_criterion_names = []
    seen_criteria = set()
    for r in all_results:
        for crit in r.get("criteria", []):
            name = crit["name"]
            if name not in seen_criteria:
                all_criterion_names.append(name)
                seen_criteria.add(name)

    # --- Write summary.json ---
    batch_cost = cost_summary(all_results)
    total_cost = batch_cost["total_cost_usd"]
    errored = sum(1 for r in all_results if r.get("error"))

    # Per-model pass rates
    model_summaries = {}
    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        rates = {}
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            total = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        # All criteria pass rate
        all_pass = sum(
            1 for r in rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
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
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            total = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        all_pass = sum(
            1 for r in rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        rates["all_criteria"] = {"passed": all_pass, "total": len(rows), "rate": all_pass / len(rows)}
        case_summaries[tc.id] = {
            "subcategory": tc.subcategory,
            "criteria": rates,
        }

    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    runs_with_failures = sum(1 for r in all_results if r.get("tool_failures"))
    tool_failure_by_name = {}
    for r in all_results:
        for tf in r.get("tool_failures", []):
            name = tf.get("tool_name", "unknown")
            tool_failure_by_name[name] = tool_failure_by_name.get(name, 0) + 1

    # Aggregate the per-run hook-block vs tool-failure diagnostic counters.
    error_counts_total = {
        "hook_blocks": 0,
        "tool_failures": 0,
        "tool_failures_unclassified": 0,
    }
    for r in all_results:
        ec = r.get("error_counts") or {}
        for key in error_counts_total:
            error_counts_total[key] += ec.get(key, 0)

    runs_completed = len(all_results)
    summary = attach_schema_version({
        "total_runs": runs_completed,
        # Additive self-description so a crashed/partial pass is legible without
        # re-deriving from the runs/ directory.
        "partial": partial,
        "runs_expected": expected_n if expected_n is not None else runs_completed,
        "runs_completed": runs_completed,
        "total_cost_usd": total_cost,
        "accounting_coverage": batch_cost["accounting_coverage"],
        "wall_time_s": round(wall_time, 1),
        "errored_runs": errored,
        "tool_failures": {
            "total": total_tool_failures,
            "runs_affected": runs_with_failures,
            "by_tool": tool_failure_by_name,
        },
        "error_counts": error_counts_total,
        "criterion_names": all_criterion_names,
        "by_model": model_summaries,
        "by_case": case_summaries,
    })
    _write_json_atomic(output_dir / "summary.json", summary)

    return output_dir


# --- Console output ---

def print_run_result(r: dict):
    """Print criterion results for a single run."""
    criteria = r.get("criteria", [])

    print(f"\n--- {r['case_id']} | {r['subcategory']} | {r['model']} rep {r['rep']} ---")

    # Print each criterion inline
    crit_strs = []
    for crit in criteria:
        status = "PASS" if crit["passed"] else "FAIL"
        crit_strs.append(f"{crit['name']}={status}")
    if crit_strs:
        print(f"  {' | '.join(crit_strs)}")

    print(
        f"  Turns: {r['turns']} | Billing: {console_billing_label(r)} "
        f"| Duration: {r['duration_s']}s | Tool calls: {r['tool_call_count']}"
    )

    if r.get("error"):
        print(f"  ERROR: {r['error']}")

    tool_failures = r.get("tool_failures", [])
    if tool_failures:
        print(f"  Tool failures ({len(tool_failures)}):")
        for tf in tool_failures[:5]:
            print(f"    {tf.get('tool_name', '?')}: {tf.get('content', '')[:120]}")

    # Print detail for any failures
    for crit in criteria:
        if not crit.get("passed", False):
            print(f"  [{crit['name']}] {crit.get('detail', 'no detail')}")


def print_summary(all_results: list[dict], models: list[ModelConfig],
                  test_cases: list[TestCase], wall_time: float):
    """Print summary tables to console."""

    # Collect all unique criterion names in order of first appearance
    all_criterion_names = []
    seen = set()
    for r in all_results:
        for crit in r.get("criteria", []):
            name = crit["name"]
            if name not in seen:
                all_criterion_names.append(name)
                seen.add(name)

    # --- Summary by model ---
    print(f"\n{'='*100}")
    print("SUMMARY BY MODEL")
    print(f"{'='*100}")

    # Build header dynamically from criterion names
    # Truncate criterion names to 14 chars for column display
    short_names = [n[:14] for n in all_criterion_names]
    header = f"{'Model':<20}"
    for sn in short_names:
        header += f" | {sn:<14}"
    header += f" | {'all':<8} | {'avg$':<8}"
    print(header)
    print("-" * len(header))

    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        n = len(rows)
        line = f"{model.name:<20}"
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            applicable = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if applicable > 0:
                line += f" | {passed}/{applicable:<12}"
            else:
                line += f" | {'n/a':<14}"
        all_pass = sum(
            1 for r in rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        avg_cost = nullable_mean(r["computed_cost_usd"] for r in rows)
        avg_label = f"${avg_cost:.3f}" if avg_cost is not None else "included"
        line += f" | {all_pass}/{n:<6} | {avg_label}"
        print(line)

    # --- Summary by case ---
    if len(test_cases) > 1:
        print(f"\n{'='*100}")
        print("SUMMARY BY CASE")
        print(f"{'='*100}")

        header = f"{'Case':<8} | {'Subcategory':<30}"
        for sn in short_names:
            header += f" | {sn:<14}"
        header += f" | {'all':<8}"
        print(header)
        print("-" * len(header))

        for tc in test_cases:
            rows = [r for r in all_results if r["case_id"] == tc.id]
            if not rows:
                continue
            n = len(rows)
            line = f"{tc.id:<8} | {tc.subcategory:<30}"
            for crit_name in all_criterion_names:
                passed = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
                )
                applicable = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name for c in r.get("criteria", []))
                )
                if applicable > 0:
                    line += f" | {passed}/{applicable:<12}"
                else:
                    line += f" | {'n/a':<14}"
            all_pass = sum(
                1 for r in rows
                if all(c["passed"] for c in r.get("criteria", []))
                and len(r.get("criteria", [])) > 0
            )
            line += f" | {all_pass}/{n:<6}"
            print(line)

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
    parser = argparse.ArgumentParser(description="Skill routing benchmark runner (Phase 4)")
    parser.add_argument("--reps", type=int, default=3,
                        help="Number of repetitions per case x model (default: 3)")
    add_model_args(parser)
    parser.add_argument("--test-id", type=str, default=None,
                        help="Comma-separated test case IDs to run (default: all)")
    parser.add_argument("--sequential", action="store_true",
                        help="Run sequentially instead of parallel")
    parser.add_argument("--delay", type=float, default=LAUNCH_DELAY_SECONDS,
                        help="Seconds between parallel launches (default: 2)")
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT_RUNS,
                        help=f"Max simultaneously in-flight runs "
                             f"(default: {MAX_CONCURRENT_RUNS}). Caps the thread "
                             f"pool; --delay still staggers submits")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Per-run timeout in seconds. Uniform 900s logistical "
                             "cap (2026-07-21 walltime redesign; formerly "
                             "120/180/300/300 per-phase). High cap so runs complete "
                             "rather than censor; duration is now the measured axis")
    parser.add_argument("--watchdog-poll", type=int, default=60,
                        help="Watchdog poll interval in seconds (default: 60)")
    parser.add_argument("--stall-threshold", type=int, default=330,
                        help="Staleness cutoff in seconds for one stalled read "
                             "(default: 330; K3-validated). Two consecutive "
                             "stalled reads trigger a stall kill")
    parser.add_argument("--stall-retries", type=int, default=1,
                        help="Times to relaunch a stalled rep from a fresh "
                             "sandbox (default: 1)")
    parser.add_argument("--no-early-stop", action="store_true",
                        help="Accepted for CLI uniformity but INERT for this "
                             "phase: score-complete early stop is intentionally "
                             "not wired here (the no_forbidden_skills negative "
                             "criterion makes it unfair). Stall detection always "
                             "runs")
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
    # The preflight-only branch returns before checkpoint inspection or setup,
    # estimates, run-list/sandbox construction, executor calls, and archives.
    if run_preflight(models, preflight_only=args.preflight_only):
        return

    # Validate golden checkpoints exist for all selected cases
    missing_checkpoints = []
    for tc in test_cases:
        if not tc.golden_checkpoint:
            missing_checkpoints.append(f"{tc.id}: no golden_checkpoint field")
        else:
            golden_path = BASE_DIR / tc.golden_checkpoint
            if not golden_path.exists():
                missing_checkpoints.append(f"{tc.id}: {golden_path} not found")
    if missing_checkpoints:
        print("ERROR: Missing golden checkpoints:")
        for msg in missing_checkpoints:
            print(f"  {msg}")
        sys.exit(1)

    total_runs = len(test_cases) * len(models) * args.reps
    print(f"Skill Routing Benchmark (Phase 4)")
    print(f"Cases: {len(test_cases)} | Models: {', '.join(m.name for m in models)}")
    print(f"Reps: {args.reps} | Total runs: {total_runs}")
    mode_str = "sequential" if args.sequential else f"parallel (delay={args.delay}s)"
    timeout_str = f" | timeout={args.timeout}s" if args.timeout else ""
    print(f"Mode: {mode_str}{timeout_str}")
    print("Agent tool: DISALLOWED (main-transcript-only scoring)")

    # Print checkpoint info (all cases share the Phase 3 Ad Hoc golden)
    print(f"\nGolden checkpoint:")
    golden_path = BASE_DIR / test_cases[0].golden_checkpoint
    line_count = get_checkpoint_line_count(golden_path)
    print(f"  {test_cases[0].golden_checkpoint}: {line_count} lines")
    print(f"\nExpected routing:")
    for tc in test_cases:
        req_skills = tc.expected.get("required_skills", [])
        req_refs = tc.expected.get("required_refs", [])
        print(f"  {tc.id} ({tc.subcategory}): skills={req_skills} refs={req_refs}")

    case_ids = [tc.id for tc in test_cases] if args.test_id else None
    est = estimate_batch_cost(models, "skill_routing", case_ids=case_ids, reps=args.reps)
    print(f"\n{format_estimate(est)}\n")

    if not args.yes and est["total"] > 0.50:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print(f"{'='*100}")
    sys.stdout.flush()

    # Per-batch uniqueness token (cross-process safety): one short token per
    # runner invocation, reused for BOTH the results dir-name suffix and every
    # sandbox suffix so concurrent batches never collide on results/ dirs or
    # _sandbox/run_ dirs, even when running the same model at the same second.
    batch_token = uuid.uuid4().hex[:6]
    batch_pid = os.getpid()

    # Build run list: case x model x rep
    runs = []
    for tc in test_cases:
        for model in models:
            for rep in range(args.reps):
                suffix = f"{tc.id}_{model.name.replace(' ', '_')}_{rep}_{batch_token}"
                runs.append((tc, model, rep, suffix))

    all_results = []
    expected_n = len(runs)
    git_sha = get_git_sha()
    start_time = time.time()

    # Create the results folder and seed manifest.json + an initial partial
    # summary.json BEFORE any run launches, so a killed pass still leaves a
    # self-describing (partial) archive.
    output_dir = archive_results(
        [], models, test_cases, args, 0.0,
        output_dir=None, partial=True, expected_n=expected_n, git_sha=git_sha,
        batch_token=batch_token, batch_pid=batch_pid,
    )
    print(f"Progressive archive: {output_dir}")
    sys.stdout.flush()

    try:
        if args.sequential:
            for tc, model, rep, suffix in runs:
                try:
                    r = run_one(
                        tc, model, rep, suffix, timeout_override=args.timeout,
                        watchdog_poll=args.watchdog_poll,
                        stall_threshold=args.stall_threshold,
                        stall_retries=args.stall_retries,
                    )
                except Exception as e:
                    r = _error_result(tc, model, rep, f"{type(e).__name__}: {e}")
                all_results.append(r)
                print_run_result(r)
                # Progressive per-run archive + incremental rollup.
                archive_results(
                    all_results, models, test_cases, args,
                    time.time() - start_time, output_dir=output_dir,
                    partial=True, expected_n=expected_n, git_sha=git_sha,
                    batch_token=batch_token, batch_pid=batch_pid,
                )
                sys.stdout.flush()
        else:
            max_workers = min(len(runs), args.max_concurrent)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for i, (tc, model, rep, suffix) in enumerate(runs):
                    future = pool.submit(
                        run_one, tc, model, rep, suffix,
                        timeout_override=args.timeout,
                        watchdog_poll=args.watchdog_poll,
                        stall_threshold=args.stall_threshold,
                        stall_retries=args.stall_retries,
                    )
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
                    # Progressive per-run archive + incremental rollup.
                    archive_results(
                        all_results, models, test_cases, args,
                        time.time() - start_time, output_dir=output_dir,
                        partial=True, expected_n=expected_n, git_sha=git_sha,
                        batch_token=batch_token, batch_pid=batch_pid,
                    )
                    sys.stdout.flush()
    finally:
        # Final rollup runs even on KeyboardInterrupt/exception: partial=False
        # only when every expected run completed.
        wall_time = time.time() - start_time
        all_done = len(all_results) == expected_n
        archive_results(
            all_results, models, test_cases, args, wall_time,
            output_dir=output_dir, partial=not all_done,
            expected_n=expected_n, git_sha=git_sha,
            batch_token=batch_token, batch_pid=batch_pid,
        )

    # Sort results by case order, then model order, then rep
    case_order = {tc.id: i for i, tc in enumerate(test_cases)}
    model_order = {m.name: i for i, m in enumerate(models)}
    all_results.sort(key=lambda r: (case_order.get(r["case_id"], 99), model_order.get(r["model"], 99), r["rep"]))

    # Print summary
    print_summary(all_results, models, test_cases, wall_time)

    print(f"\nResults archived to: {output_dir}")


if __name__ == "__main__":
    main()
