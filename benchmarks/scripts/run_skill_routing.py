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
import shutil
import subprocess
import sys
import time
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

# --- Config ---

BASE_DIR = Path("/daaf")
CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "skill_routing" / "cases.jsonl"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

LAUNCH_DELAY_SECONDS = 2


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
            sandbox_suffix: str, timeout_override=None):
    """Execute a single benchmark run with checkpoint scoring."""
    sandbox_dir = f"/daaf/benchmarks/_sandbox/run_{sandbox_suffix}"

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
            "transcript_path": archived_transcript or scored.get("transcript_path"),
            "tool_call_count": scored.get("tool_call_count", 0),
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
        "benchmark": "skill_routing",
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
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # --- Write per-run results and copy transcripts ---
    for r in all_results:
        run_name = f"{r['case_id']}_{r['model'].replace(' ', '_')}_{r['rep']}"
        run_dir = runs_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write every flat, phase-specific, and schema-v2 field. Transcript
        # content is copied separately below rather than embedded in result.json.
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
        "criterion_names": all_criterion_names,
        "by_model": model_summaries,
        "by_case": case_summaries,
    })
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
    parser.add_argument("--timeout", type=int, default=300,
                        help="Per-run timeout in seconds (Phase 4 default: 300; "
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
