"""Runner module: orchestrates benchmark execution across the test matrix.

Iterates over test cases, models, and repetitions. Calls executor for each
run, collector to gather artifacts, and the appropriate scorer to evaluate.
Writes per-run results to a timestamped results directory.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from benchmarks.harness.models import (
    ModelConfig,
    RunConfig,
    RunResult,
    ScoredResult,
    TestCase,
)
from benchmarks.harness.executor import check_cli_available, check_hooks_active, execute_run
from benchmarks.harness.collector import (
    collect_audit_entries,
    collect_new_audit_entries,
    get_audit_log_position,
    now_iso,
)

# Scorer registry: maps category name to scoring function
SCORER_REGISTRY: dict = {}


def register_scorer(category: str):
    """Decorator to register a scoring function for a test category."""
    def wrapper(fn):
        SCORER_REGISTRY[category] = fn
        return fn
    return wrapper


def load_scorers():
    """Import scorer modules to trigger registration."""
    try:
        from benchmarks.scorers.deterministic.mode_classification import score_mode_classification
        SCORER_REGISTRY["mode_classification"] = score_mode_classification
    except ImportError as e:
        print(f"WARNING: Could not load mode_classification scorer: {e}", file=sys.stderr)


def load_models(config_path: Path) -> list[ModelConfig]:
    """Load model configurations from YAML."""
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return [ModelConfig.from_dict(m) for m in data.get("models", [])]


def load_budget(config_path: Path) -> dict:
    """Load cost budget configuration from YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_test_cases(dataset_dir: Path, category: str | None = None) -> list[TestCase]:
    """Load test cases from JSONL files in the datasets directory.

    If category is specified, only load from that subdirectory.
    Otherwise, load from all subdirectories.
    """
    cases = []
    if category:
        jsonl_path = dataset_dir / category / "cases.jsonl"
        if jsonl_path.exists():
            cases.extend(TestCase.load_from_jsonl(jsonl_path))
    else:
        for subdir in sorted(dataset_dir.iterdir()):
            if subdir.is_dir():
                jsonl_path = subdir / "cases.jsonl"
                if jsonl_path.exists():
                    cases.extend(TestCase.load_from_jsonl(jsonl_path))
    return cases


def run_single(
    config: RunConfig,
    pre_run_timestamp: str,
) -> ScoredResult:
    """Execute a single test case run and score the result."""
    # Execute
    run_result = execute_run(config)

    # Collect audit entries if we got a session_id
    if run_result.session_id:
        run_result.audit_entries = collect_audit_entries(
            session_id=run_result.session_id,
            after_timestamp=pre_run_timestamp,
        )
    elif not run_result.error:
        # No session_id but no error — collect by timestamp
        run_result.audit_entries = collect_new_audit_entries(
            after_timestamp=pre_run_timestamp,
        )

    # Score
    scorer = SCORER_REGISTRY.get(config.test_case.category)
    if scorer:
        criteria = scorer(run_result, config.test_case.expected)
        return ScoredResult(run=run_result, criteria=criteria)
    else:
        print(
            f"WARNING: No scorer for category '{config.test_case.category}'. "
            f"Returning unscored result.",
            file=sys.stderr,
        )
        return ScoredResult(run=run_result)


def print_result_summary(scored: ScoredResult, test_case: TestCase):
    """Print a concise summary of a single scored run."""
    status = "PASS" if scored.pass_rate == 1.0 else "FAIL" if scored.pass_rate == 0.0 else "PARTIAL"
    cost_str = f"${scored.run.total_cost_usd:.3f}" if scored.run.total_cost_usd else "n/a"
    error_str = f" ERROR: {scored.run.error}" if scored.run.error else ""

    print(
        f"  [{status}] {test_case.id} | "
        f"model={scored.run.model_name} | "
        f"rep={scored.run.run_index} | "
        f"pass={scored.pass_count}/{scored.total_count} | "
        f"cost={cost_str} | "
        f"turns={scored.run.total_turns} | "
        f"time={scored.run.duration_seconds:.1f}s"
        f"{error_str}"
    )

    # Print individual criteria
    for c in scored.criteria:
        mark = "+" if c.passed else "x"
        print(f"    [{mark}] {c.name}: {c.detail[:120]}")


def print_suite_summary(all_results: list[ScoredResult]):
    """Print an aggregate summary table across all results."""
    if not all_results:
        print("\nNo results to summarize.")
        return

    # Group by model
    by_model: dict[str, list[ScoredResult]] = {}
    for sr in all_results:
        model_name = sr.run.model_name
        by_model.setdefault(model_name, []).append(sr)

    # Collect all criterion names
    all_criteria = []
    seen = set()
    for sr in all_results:
        for c in sr.criteria:
            if c.name not in seen:
                all_criteria.append(c.name)
                seen.add(c.name)

    # Print table
    models = sorted(by_model.keys())
    header = f"{'Criterion':<35}" + "".join(f"| {m:<20}" for m in models)
    separator = "-" * len(header)

    print(f"\n{separator}")
    print("SUITE SUMMARY (pass@1 rates)")
    print(separator)
    print(header)
    print(separator)

    for criterion in all_criteria:
        row = f"{criterion:<35}"
        for model_name in models:
            results = by_model[model_name]
            passes = sum(
                1 for sr in results
                for c in sr.criteria
                if c.name == criterion and c.passed
            )
            total = sum(
                1 for sr in results
                for c in sr.criteria
                if c.name == criterion
            )
            rate = passes / total if total > 0 else 0.0
            row += f"| {rate:.2f} ({passes}/{total})       "
        print(row)

    print(separator)

    # Cost summary
    print("\nCOST SUMMARY")
    print(separator)
    for model_name in models:
        results = by_model[model_name]
        total_cost = sum(sr.run.total_cost_usd for sr in results)
        total_time = sum(sr.run.duration_seconds for sr in results)
        errors = sum(1 for sr in results if sr.run.error)
        print(
            f"  {model_name}: "
            f"runs={len(results)}, "
            f"cost=${total_cost:.2f}, "
            f"time={total_time:.0f}s, "
            f"errors={errors}"
        )
    print(separator)


def main():
    parser = argparse.ArgumentParser(
        description="DAAF Framework Adherence Benchmark Runner"
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Run only test cases from this category (e.g., 'mode_classification')",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Run only this model ID (e.g., 'claude-haiku-4-5-20251001')",
    )
    parser.add_argument(
        "--test-id",
        type=str,
        default=None,
        help="Run only this specific test case ID (e.g., 'mc-01')",
    )
    parser.add_argument(
        "--reps",
        type=int,
        default=None,
        help="Override number of repetitions per test case",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the test matrix without executing",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="/daaf",
        help="DAAF base directory (default: /daaf)",
    )

    args = parser.parse_args()

    base = Path(args.base_dir)
    bench = base / "benchmarks"

    # Load configuration
    models = load_models(bench / "config" / "models.yaml")
    budget = load_budget(bench / "config" / "cost_budget.yaml")
    test_cases = load_test_cases(bench / "datasets", args.category)
    load_scorers()

    if not test_cases:
        print("ERROR: No test cases found.", file=sys.stderr)
        sys.exit(1)

    # Filter by model if specified
    if args.model:
        models = [m for m in models if m.id == args.model or m.name == args.model]
        if not models:
            print(f"ERROR: Model '{args.model}' not found in config.", file=sys.stderr)
            sys.exit(1)

    # Filter by test ID if specified
    if args.test_id:
        test_cases = [tc for tc in test_cases if tc.id == args.test_id]
        if not test_cases:
            print(f"ERROR: Test case '{args.test_id}' not found.", file=sys.stderr)
            sys.exit(1)

    # Determine repetitions
    default_reps = args.reps or budget.get("default_repetitions", 3)
    reps_by_tier = budget.get("repetitions_by_tier", {})

    # Build test matrix
    matrix = []
    for model in models:
        for tc in test_cases:
            reps = args.reps or reps_by_tier.get(tc.cost_tier, default_reps)
            for rep in range(reps):
                matrix.append((model, tc, rep))

    print(f"DAAF Framework Adherence Benchmark")
    print(f"===================================")
    print(f"Models:     {len(models)} ({', '.join(m.name for m in models)})")
    print(f"Test cases: {len(test_cases)}")
    print(f"Total runs: {len(matrix)}")
    print(f"Categories: {sorted(set(tc.category for tc in test_cases))}")
    print(f"Scorers:    {sorted(SCORER_REGISTRY.keys())}")
    print()

    if args.dry_run:
        print("DRY RUN — test matrix:")
        for model, tc, rep in matrix:
            print(f"  {model.name} | {tc.id} | rep={rep}")
        return

    # Pre-flight checks
    if not check_cli_available():
        print("ERROR: 'claude' CLI not found or not responsive.", file=sys.stderr)
        sys.exit(1)

    hooks_status = check_hooks_active(str(base))
    print("Hook status:")
    for hook, active in hooks_status.items():
        print(f"  {hook}: {'active' if active else 'NOT FOUND'}")
    print()

    # Create results directory
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_dir = bench / "results" / run_timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    # Execute
    all_results: list[ScoredResult] = []
    total_cost = 0.0

    for i, (model, tc, rep) in enumerate(matrix):
        print(f"\n--- Run {i + 1}/{len(matrix)} ---")

        # Check budget
        if total_cost >= budget.get("max_cost_per_suite", float("inf")):
            print(f"BUDGET EXCEEDED: ${total_cost:.2f} >= suite limit. Stopping.")
            break

        # Snapshot audit log position
        pre_run_ts = now_iso()
        time.sleep(0.1)  # Ensure timestamp separation

        config = RunConfig(
            test_case=tc,
            model=model,
            run_index=rep,
            working_dir=str(base),
        )

        scored = run_single(config, pre_run_ts)
        all_results.append(scored)
        total_cost += scored.run.total_cost_usd

        print_result_summary(scored, tc)

        # Write individual result
        result_file = results_dir / f"{tc.id}_{model.id}_{rep}.json"
        with open(result_file, "w") as f:
            json.dump(scored.to_dict(), f, indent=2)

        # Check per-run cost
        if scored.run.total_cost_usd > budget.get("max_cost_per_run", float("inf")):
            print(
                f"WARNING: Run cost ${scored.run.total_cost_usd:.2f} "
                f"exceeds per-run limit."
            )

    # Write aggregate results
    aggregate_file = results_dir / "aggregate.json"
    with open(aggregate_file, "w") as f:
        json.dump(
            {
                "timestamp": run_timestamp,
                "models": [m.id for m in models],
                "test_cases": [tc.id for tc in test_cases],
                "total_runs": len(all_results),
                "total_cost_usd": total_cost,
                "results": [sr.to_dict() for sr in all_results],
            },
            f,
            indent=2,
        )

    # Print summary
    print_suite_summary(all_results)
    print(f"\nResults written to: {results_dir}")


if __name__ == "__main__":
    main()
