"""Post-confirmation protocol benchmark with golden checkpoint scoring and run archival.

Tests whether models correctly execute the post-confirmation protocol after
the user confirms a classified engagement mode. Each test case resumes from
a golden checkpoint (a full session transcript from a Phase 1 mode classification
run where the model correctly classified and presented a confirmation message),
then scores whether the model loads the expected mode reference files and skills.

Scoring uses score_checkpoint() from checkpoint_adherence.py, which handles
documents_read, skills_loaded, subagent_dispatched, and no_tool_calls_of_type
criteria from the test case's expected dict.

Results are archived to a self-contained results folder with per-run transcripts.

Usage:
    python3 benchmarks/scripts/run_post_confirmation.py
    python3 benchmarks/scripts/run_post_confirmation.py --reps 1 --models haiku,sonnet
    python3 benchmarks/scripts/run_post_confirmation.py --test-id pc-01,pc-05 --sequential
"""

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.harness.models import TestCase, ModelConfig, RunConfig, CriterionResult
from benchmarks.harness.executor import execute_run
from benchmarks.harness.checkpoint_manager import cleanup_sandbox
from benchmarks.harness.model_loader import load_models, filter_models, add_model_args
from benchmarks.harness.cost_estimator import estimate_batch_cost, format_estimate, compute_cost
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
    find_benchmark_transcript,
    get_checkpoint_line_count,
    score_checkpoint,
)

# --- Config ---

BASE_DIR = Path("/daaf")
CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "post_confirmation" / "cases.jsonl"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

LAUNCH_DELAY_SECONDS = 2


# --- Load config ---

def load_test_cases(path: Path) -> list[TestCase]:
    """Load test cases from cases.jsonl."""
    return TestCase.load_from_jsonl(path)


# --- Scoring ---

def score_run(session_id: str, test_case: TestCase) -> dict:
    """Score a single run by extracting tool calls from the transcript and
    delegating to score_checkpoint().

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

    # Extract tool calls made after the checkpoint boundary
    tool_calls = extract_new_tool_calls(transcript_path, checkpoint_lines)

    # Score using the generic checkpoint scorer
    criterion_results = score_checkpoint(tool_calls, test_case.expected)

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

    return {
        "criteria": criteria_dicts,
        "transcript_path": str(transcript_path),
        "tool_call_count": len(tool_calls),
    }


# --- Run + diagnose ---

def run_one(test_case: TestCase, model: ModelConfig, rep: int,
            sandbox_suffix: str, timeout_override=None):
    """Execute a single benchmark run with checkpoint scoring."""
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

    # Clean up checkpoint sandbox AFTER scoring (transcript may live there)
    if test_case.golden_checkpoint:
        cleanup_sandbox(result.session_id)

    actual_cost = compute_cost(model, result)

    return {
        "case_id": test_case.id,
        "subcategory": test_case.subcategory,
        "model": model.name,
        "model_id": model.id,
        "provider": model.provider,
        "effort_level": model.effort_level or "default",
        "rep": rep,
        "session_id": result.session_id,
        "turns": result.total_turns,
        "computed_cost_usd": actual_cost,
        "reasoning_cost_multiplier": model.reasoning_cost_multiplier,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cache_read_tokens": result.cache_read_tokens,
        "cache_creation_tokens": result.cache_creation_tokens,
        "duration_s": round(elapsed, 1),
        "error": result.error,
        "timed_out": bool(result.error and "Timed out" in result.error),
        "criteria": scored["criteria"],
        "transcript_path": scored.get("transcript_path"),
        "tool_call_count": scored.get("tool_call_count", 0),
        "tool_failures": result.tool_failures,
    }


def _error_result(test_case: TestCase, model: ModelConfig, rep: int, error_msg: str):
    """Build a safe result dict for a run that failed before returning data."""
    return {
        "case_id": test_case.id,
        "subcategory": test_case.subcategory,
        "model": model.name,
        "model_id": model.id,
        "provider": model.provider,
        "effort_level": model.effort_level or "default",
        "rep": rep,
        "session_id": "",
        "turns": 0,
        "computed_cost_usd": 0.0,
        "reasoning_cost_multiplier": model.reasoning_cost_multiplier,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "duration_s": 0.0,
        "error": error_msg,
        "timed_out": False,
        "criteria": [
            {
                "name": "run_completed",
                "passed": False,
                "tier": "tier1",
                "detail": f"Exception: {error_msg}",
            }
        ],
        "transcript_path": None,
        "tool_call_count": 0,
        "tool_failures": [],
    }


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
    manifest = {
        "benchmark": "post_confirmation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "daaf_git_sha": git_sha,
        "config": {
            "reps": args.reps,
            "parallel": not args.sequential,
            "launch_delay_s": args.delay,
            "timeout_override": args.timeout,
            "test_ids": args.test_id.split(",") if args.test_id else "all",
            "model_keys": args.models.split(",") if args.models else "all",
        },
        "models": [
            {
                "name": m.name,
                "id": m.id,
                "provider": m.provider,
                "effort_level": m.effort_level or "default",
            }
            for m in models
        ],
        "cases": [
            {
                "id": tc.id,
                "subcategory": tc.subcategory,
                "golden_checkpoint": tc.golden_checkpoint,
                "expected": tc.expected,
            }
            for tc in test_cases
        ],
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # --- Write per-run results and copy transcripts ---
    for r in all_results:
        run_name = f"{r['case_id']}_{r['model'].replace(' ', '_')}_{r['rep']}"
        run_dir = runs_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write result.json for this run
        result_data = {
            "case_id": r["case_id"],
            "subcategory": r["subcategory"],
            "model": r["model"],
            "model_id": r["model_id"],
            "provider": r.get("provider", "anthropic"),
            "effort_level": r["effort_level"],
            "rep": r["rep"],
            "session_id": r["session_id"],
            "turns": r["turns"],
            "computed_cost_usd": r["computed_cost_usd"],
            "input_tokens": r.get("input_tokens", 0),
            "output_tokens": r.get("output_tokens", 0),
            "cache_read_tokens": r.get("cache_read_tokens", 0),
            "cache_creation_tokens": r.get("cache_creation_tokens", 0),
            "duration_s": r["duration_s"],
            "error": r["error"],
            "timed_out": r.get("timed_out", False),
            "criteria": r["criteria"],
            "tool_call_count": r["tool_call_count"],
            "tool_failures": r.get("tool_failures", []),
        }
        with open(run_dir / "result.json", "w") as f:
            json.dump(result_data, f, indent=2)

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
    total_cost = sum(r["computed_cost_usd"] for r in all_results)
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
        avg_cost = sum(r["computed_cost_usd"] for r in rows) / len(rows)
        model_summaries[model.name] = {"criteria": rates, "avg_cost_usd": avg_cost}

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

    summary = {
        "total_runs": len(all_results),
        "total_cost_usd": total_cost,
        "wall_time_s": round(wall_time, 1),
        "errored_runs": errored,
        "tool_failures": {
            "total": total_tool_failures,
            "runs_affected": runs_with_failures,
            "by_tool": tool_failure_by_name,
        },
        "criterion_names": all_criterion_names,
        "by_model": model_summaries,
        "by_case": case_summaries,
    }
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

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

    print(f"  Turns: {r['turns']} | Cost: ${r['computed_cost_usd']:.3f} | Duration: {r['duration_s']}s | Tool calls: {r['tool_call_count']}")

    if r.get("error"):
        print(f"  ERROR: {r['error']}")

    # Print detail for any failures
    for crit in criteria:
        if not crit.get("passed", False):
            print(f"  [{crit['name']}] {crit.get('detail', 'no detail')}")

    tool_failures = r.get("tool_failures", [])
    if tool_failures:
        print(f"  Tool failures ({len(tool_failures)}):")
        for tf in tool_failures[:5]:
            print(f"    {tf.get('tool_name', '?')}: {tf.get('content', '')[:120]}")


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
        avg_cost = sum(r["computed_cost_usd"] for r in rows) / n
        line += f" | {all_pass}/{n:<6} | ${avg_cost:.3f}"
        print(line)

    # --- Summary by case (mode) ---
    if len(test_cases) > 1:
        print(f"\n{'='*100}")
        print("SUMMARY BY MODE")
        print(f"{'='*100}")

        header = f"{'Case':<8} | {'Mode':<30}"
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

    total_cost = sum(r["computed_cost_usd"] for r in all_results)
    errored = sum(1 for r in all_results if r.get("error"))
    error_note = f" ({errored} errored/timed-out)" if errored else ""
    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    tf_note = f" | {total_tool_failures} tool failures" if total_tool_failures else ""
    print(f"\nTotal: {len(all_results)} runs{error_note} | ${total_cost:.2f} | {wall_time:.0f}s wall time{tf_note}")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Post-confirmation protocol benchmark runner")
    parser.add_argument("--reps", type=int, default=3,
                        help="Number of repetitions per case x model (default: 3)")
    add_model_args(parser)
    parser.add_argument("--test-id", type=str, default=None,
                        help="Comma-separated test case IDs to run (default: all)")
    parser.add_argument("--sequential", action="store_true",
                        help="Run sequentially instead of parallel")
    parser.add_argument("--delay", type=float, default=LAUNCH_DELAY_SECONDS,
                        help="Seconds between parallel launches (default: 2)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Override per-run timeout in seconds (default: cost-tier based)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip cost confirmation prompt")
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
    print(f"Post-Confirmation Protocol Benchmark")
    print(f"Cases: {len(test_cases)} | Models: {', '.join(m.name for m in models)}")
    print(f"Reps: {args.reps} | Total runs: {total_runs}")
    mode_str = "sequential" if args.sequential else f"parallel (delay={args.delay}s)"
    timeout_str = f" | timeout={args.timeout}s" if args.timeout else ""
    print(f"Mode: {mode_str}{timeout_str}")

    # Print checkpoint info
    print(f"\nGolden checkpoints:")
    for tc in test_cases:
        golden_path = BASE_DIR / tc.golden_checkpoint
        line_count = get_checkpoint_line_count(golden_path)
        expected_docs = tc.expected.get("documents_read", [])
        expected_skills = tc.expected.get("skills_loaded", [])
        print(f"  {tc.id} ({tc.subcategory}): {line_count} lines | "
              f"expect docs={expected_docs} skills={expected_skills}")

    case_ids = [tc.id for tc in test_cases] if args.test_id else None
    est = estimate_batch_cost(models, "post_confirmation", case_ids=case_ids, reps=args.reps)
    print(f"\n{format_estimate(est)}\n")

    if not args.yes and est["total"] > 0.50:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print(f"{'='*100}")
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
