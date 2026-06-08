"""Post-hoc subagent behavior rescoring for existing dispatch compliance results.

Reads an existing results directory, finds subagent transcripts, scores them,
and writes updated result.json files with subagent_criteria added.

Usage:
    python3 benchmarks/scripts/rescore_subagent_behavior.py results/20260608_115024
    python3 benchmarks/scripts/rescore_subagent_behavior.py results/20260608_115024 --print-only
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.scorers.deterministic.subagent_behavior import score_subagent_behavior

CASES_FILE = Path("/daaf/benchmarks/datasets/dispatch_compliance/cases.jsonl")


def load_expected_agents() -> dict[str, str]:
    """Load case_id -> expected subagent_type mapping from cases.jsonl."""
    mapping = {}
    with open(CASES_FILE) as f:
        for line in f:
            case = json.loads(line.strip())
            mapping[case["id"]] = case["expected"]["subagent_dispatched"]
    return mapping


def main():
    parser = argparse.ArgumentParser(description="Rescore subagent behavior post-hoc")
    parser.add_argument("results_dir", help="Path to results directory (e.g., results/20260608_115024)")
    parser.add_argument("--print-only", action="store_true", help="Print scores without updating files")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        results_dir = Path("/daaf/benchmarks") / results_dir

    runs_dir = results_dir / "runs"
    if not runs_dir.exists():
        print(f"ERROR: {runs_dir} not found")
        sys.exit(1)

    expected_agents = load_expected_agents()

    scored_count = 0
    skipped_count = 0

    for run_dir in sorted(runs_dir.iterdir()):
        result_file = run_dir / "result.json"
        if not result_file.exists():
            continue

        r = json.loads(result_file.read_text())
        case_id = r["case_id"]
        model = r["model"]
        session_id = r.get("session_id", "")

        agent_dispatched = any(
            c["name"] == "agent_dispatched" and c["passed"]
            for c in r.get("criteria", [])
        )

        if not agent_dispatched or not session_id:
            skipped_count += 1
            if not args.print_only:
                r["subagent_criteria"] = []
                with open(result_file, "w") as f:
                    json.dump(r, f, indent=2)
            continue

        expected_type = expected_agents.get(case_id, "")
        if not expected_type:
            skipped_count += 1
            continue

        results = score_subagent_behavior(session_id, expected_type)
        criteria_dicts = [
            {
                "name": cr.name,
                "passed": cr.passed,
                "tier": cr.tier,
                "detail": cr.detail,
            }
            for cr in results
        ]

        print(f"\n--- {case_id} | {model} | {expected_type} ---")
        for cr in results:
            status = "PASS" if cr.passed else "FAIL"
            if cr.tier == "info":
                print(f"  [{cr.tier}] {cr.detail}")
            else:
                print(f"  {cr.name} [{cr.tier}]: {status}")
                if not cr.passed:
                    print(f"    {cr.detail}")

        if not args.print_only:
            r["subagent_criteria"] = criteria_dicts
            with open(result_file, "w") as f:
                json.dump(r, f, indent=2)

        scored_count += 1

    print(f"\n{'='*60}")
    print(f"Scored: {scored_count} | Skipped (no dispatch): {skipped_count}")
    if not args.print_only:
        print(f"Updated result.json files in {runs_dir}")
    else:
        print("(print-only mode — no files modified)")


if __name__ == "__main__":
    main()
