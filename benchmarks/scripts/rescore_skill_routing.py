"""Rescore archived Phase 4 (skill_routing) result sets with the current scorer.

Re-runs score_skill_routing() against each run's ARCHIVED transcript.jsonl and
rewrites result.json criteria plus the set-level summary.json. Built so newly
added criteria (e.g., required_skills_engaged) can be applied retroactively to
historical result sets without re-running the (expensive) benchmark itself.

Merge semantics for result.json criteria:
- New scorer output REPLACES/updates same-named entries.
- Old criteria entries whose names the current scorer no longer emits are
  RETAINED in place (preserves historical criteria such as dry-run-2's
  no_spurious_skill_reload — see PHASE4 plan section 9, decision 6).
- Genuinely new criteria slot in at the scorer's emission position.
- All other result.json fields (costs, tokens, turns, tool_call_count, etc.)
  are run-time facts and are left untouched.

Runs without an archived transcript.jsonl (timeout / no-session failures) are
SKIPPED and their existing criteria preserved unchanged.

summary.json is recomputed from the rewritten result.json files, faithfully
replicating the aggregation in run_skill_routing.py archive_results()
(criterion_names by first appearance, by_model / by_case rollups, the
synthetic all_criteria rate, tool_failures block). wall_time_s is a run-time
fact preserved from the existing summary. Retained-legacy criteria flow into
criterion_names and the rollups exactly as the original summary listed them.
Note (cosmetic): recomputed criterion_names ordering is first-appearance over
runs sorted in runner order, which may differ from the original summary's
execution-order listing when errored runs (with no/partial criteria) happened
to complete first in the original run — rollup contents are unaffected.

Determinism check: every criterion present in BOTH the archived result.json
and the new scorer output must match exactly. Criteria the scorer emits that
are absent from the archive are treated as NEW for that set (computed per
run, not hardcoded) — so re-rescoring an already-rescored set verifies all
criteria, and the next criterion addition needs no code edit here.

CAUTION: adding a criterion shifts all_criteria retroactively — a run that
previously passed everything can flip to failing all_criteria. The before/after
table printed per set makes this delta visible.

Checkpoint-drift caveat: checkpoint_line_count is recomputed from the CURRENT
golden checkpoint file referenced in the manifest. If the golden file has
changed since the original run, historical slicing breaks (the manifest's
daaf_git_sha allows verification).

Usage:
    python3 benchmarks/scripts/rescore_skill_routing.py 20260610_153005
    python3 benchmarks/scripts/rescore_skill_routing.py --all --dry-run
    python3 benchmarks/scripts/rescore_skill_routing.py \
        benchmarks/results/20260610_153005 20260610_153417
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.scorers.deterministic.checkpoint_adherence import (
    get_checkpoint_line_count,
)
from benchmarks.scorers.deterministic.skill_routing import score_skill_routing

BASE_DIR = Path("/daaf")
RESULTS_DIR = BASE_DIR / "benchmarks" / "results"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rescore archived skill_routing result sets with the current scorer"
    )
    parser.add_argument(
        "set_dirs",
        nargs="*",
        help="Result-set dirs (timestamps like 20260610_153005, or full paths)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rescore every results/*/ set whose manifest.json has benchmark == skill_routing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes (including determinism check) without writing any files",
    )
    return parser.parse_args()


def resolve_set_dirs(args) -> list[Path]:
    """Resolve positional dirs and/or --all into verified skill_routing set dirs."""
    candidates = []
    for raw in args.set_dirs:
        p = Path(raw)
        if not p.is_absolute():
            # Accept bare timestamps and repo-relative paths
            p = RESULTS_DIR / raw if "/" not in raw else BASE_DIR / raw
        candidates.append(p)

    if args.all:
        for manifest_path in sorted(RESULTS_DIR.glob("*/manifest.json")):
            candidates.append(manifest_path.parent)

    resolved = []
    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        manifest_path = p / "manifest.json"
        if not manifest_path.exists():
            print(f"ERROR: no manifest.json in {p}")
            sys.exit(1)
        with open(manifest_path) as f:
            manifest = json.load(f)
        if manifest.get("benchmark") != "skill_routing":
            if args.all:
                continue  # --all scan: silently skip other benchmarks
            print(f"ERROR: {p} is benchmark={manifest.get('benchmark')!r}, not skill_routing")
            sys.exit(1)
        resolved.append(p)
    return resolved


def merge_criteria(old_criteria: list[dict], new_criteria: list[dict]) -> list[dict]:
    """Order-stable merge of old result.json criteria with new scorer output.

    Walks the old list: entries whose names the scorer still emits are replaced
    by the new versions (pulling in any not-yet-emitted new criteria that
    precede them in scorer order, so genuinely new criteria slot in at their
    scorer position); legacy entries the scorer no longer emits are retained
    in place. Any trailing new criteria are appended.
    """
    new_names = {c["name"] for c in new_criteria}
    merged = []
    new_idx = 0
    for old in old_criteria:
        if old["name"] in new_names:
            while new_idx < len(new_criteria):
                entry = new_criteria[new_idx]
                new_idx += 1
                merged.append(entry)
                if entry["name"] == old["name"]:
                    break
        else:
            merged.append(old)
    merged.extend(new_criteria[new_idx:])
    return merged


def build_summary(all_results: list[dict], manifest: dict, wall_time_s) -> dict:
    """Recompute summary.json, replicating run_skill_routing.archive_results()."""
    # Criterion names in order of first appearance across sorted results
    all_criterion_names = []
    seen_criteria = set()
    for r in all_results:
        for crit in r.get("criteria", []):
            name = crit["name"]
            if name not in seen_criteria:
                all_criterion_names.append(name)
                seen_criteria.add(name)

    total_cost = sum(r["computed_cost_usd"] for r in all_results)
    errored = sum(1 for r in all_results if r.get("error"))

    def rates_for(rows: list[dict]) -> dict:
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
        return rates

    model_summaries = {}
    for m in manifest["models"]:
        rows = [r for r in all_results if r["model"] == m["name"]]
        if not rows:
            continue
        rates = rates_for(rows)
        avg_cost = sum(r["computed_cost_usd"] for r in rows) / len(rows)
        model_summaries[m["name"]] = {"criteria": rates, "avg_cost_usd": avg_cost}

    case_summaries = {}
    for case in manifest["cases"]:
        rows = [r for r in all_results if r["case_id"] == case["id"]]
        if not rows:
            continue
        case_summaries[case["id"]] = {
            "subcategory": case["subcategory"],
            "criteria": rates_for(rows),
        }

    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    runs_with_failures = sum(1 for r in all_results if r.get("tool_failures"))
    tool_failure_by_name = {}
    for r in all_results:
        for tf in r.get("tool_failures", []):
            name = tf.get("tool_name", "unknown")
            tool_failure_by_name[name] = tool_failure_by_name.get(name, 0) + 1

    return {
        "total_runs": len(all_results),
        "total_cost_usd": total_cost,
        "wall_time_s": wall_time_s,
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


def print_before_after(
    set_dir: Path, old_summary: dict, new_summary: dict, new_criterion_names: set
):
    """Print a per-model before/after table of per-criterion pass counts."""
    print(f"\n  Before/after (per model, passed/total):")
    crit_names = list(new_summary["criterion_names"])
    for name in old_summary.get("criterion_names", []):
        if name not in crit_names:
            crit_names.append(name)  # criteria dropped by rescore (shouldn't happen)
    crit_names.append("all_criteria")

    width = max(len(n) for n in crit_names) + 2
    for model_name, new_m in new_summary["by_model"].items():
        old_m = old_summary.get("by_model", {}).get(model_name, {})
        print(f"  Model: {model_name}")
        for crit in crit_names:
            old_c = old_m.get("criteria", {}).get(crit)
            new_c = new_m.get("criteria", {}).get(crit)
            old_str = f"{old_c['passed']}/{old_c['total']}" if old_c else "n/a"
            new_str = f"{new_c['passed']}/{new_c['total']}" if new_c else "n/a"
            marker = ""
            if crit in new_criterion_names:
                marker = "  <-- NEW"
            elif old_str != new_str:
                marker = "  (CHANGED)"
            print(f"    {crit:<{width}} {old_str:>7} -> {new_str:<7}{marker}")


def rescore_set(set_dir: Path, dry_run: bool) -> bool:
    """Rescore one result set. Returns True if the determinism check passed."""
    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Rescoring: {set_dir}")
    print(f"{'='*80}")

    with open(set_dir / "manifest.json") as f:
        manifest = json.load(f)

    summary_path = set_dir / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: no summary.json in {set_dir} — skipping this set")
        return True
    with open(summary_path) as f:
        old_summary = json.load(f)

    cases_by_id = {c["id"]: c for c in manifest["cases"]}
    line_count_cache = {}

    run_dirs = sorted(d for d in (set_dir / "runs").iterdir() if d.is_dir())
    all_results = []
    skipped = []
    determinism_diffs = []
    new_criterion_names = set()  # scorer-emitted criteria absent from the archive
    new_criterion_counts = {}  # name -> [passed, total] across rescored runs

    for run_dir in run_dirs:
        result_path = run_dir / "result.json"
        if not result_path.exists():
            print(f"  WARNING: no result.json in {run_dir.name} — skipping")
            continue
        with open(result_path) as f:
            result = json.load(f)

        transcript = run_dir / "transcript.jsonl"
        if not transcript.exists():
            # Timeout / no-session run: preserve existing criteria unchanged
            skipped.append(run_dir.name)
            all_results.append(result)
            continue

        case = cases_by_id.get(result["case_id"])
        if case is None:
            print(f"  WARNING: case {result['case_id']} not in manifest — skipping {run_dir.name}")
            all_results.append(result)
            continue

        golden = case["golden_checkpoint"]
        if golden not in line_count_cache:
            line_count_cache[golden] = get_checkpoint_line_count(BASE_DIR / golden)
        checkpoint_lines = line_count_cache[golden]

        criterion_results = score_skill_routing(
            str(transcript), checkpoint_lines, case["expected"]
        )
        new_criteria = [
            {"name": cr.name, "passed": cr.passed, "tier": cr.tier, "detail": cr.detail}
            for cr in criterion_results
        ]

        # Determinism check: every criterion present in BOTH the archive and
        # the new scorer output must reproduce the archived values exactly
        # (name, passed, tier, detail). Any diff means either scorer drift or
        # golden-checkpoint drift — investigate. Criteria the scorer emits
        # that are absent from the archive are NEW for this run (computed per
        # run, not hardcoded), so re-rescoring an already-rescored set
        # determinism-checks every criterion.
        old_by_name = {c["name"]: c for c in result["criteria"]}
        run_new_names = {nc["name"] for nc in new_criteria} - set(old_by_name)
        new_criterion_names |= run_new_names
        for nc in new_criteria:
            oc = old_by_name.get(nc["name"])
            if oc is not None and oc != nc:
                determinism_diffs.append((run_dir.name, oc, nc))

        for nc in new_criteria:
            if nc["name"] in run_new_names:
                counts = new_criterion_counts.setdefault(nc["name"], [0, 0])
                counts[1] += 1
                if nc["passed"]:
                    counts[0] += 1

        result["criteria"] = merge_criteria(result["criteria"], new_criteria)
        all_results.append(result)

        if not dry_run:
            with open(result_path, "w") as f:
                json.dump(result, f, indent=2)

    # Sort to match runner ordering: case order, then model order, then rep
    case_order = {c["id"]: i for i, c in enumerate(manifest["cases"])}
    model_order = {m["name"]: i for i, m in enumerate(manifest["models"])}
    all_results.sort(
        key=lambda r: (case_order.get(r["case_id"], 99), model_order.get(r["model"], 99), r["rep"])
    )

    new_summary = build_summary(all_results, manifest, old_summary.get("wall_time_s"))
    if not dry_run:
        with open(set_dir / "summary.json", "w") as f:
            json.dump(new_summary, f, indent=2)

    print(f"  Runs rescored: {len(all_results) - len(skipped)} | skipped (no transcript): {len(skipped)}")
    if skipped:
        for name in skipped:
            print(f"    skipped: {name}")
    if new_criterion_counts:
        for name in sorted(new_criterion_counts):
            passed, total = new_criterion_counts[name]
            print(f"  NEW criterion {name}: {passed}/{total} passed across rescored runs")
    else:
        print("  No new criteria — all scorer-emitted criteria already present in archive")

    if determinism_diffs:
        print(f"\n  DETERMINISM CHECK FAILED: {len(determinism_diffs)} criterion diff(s):")
        for run_name, oc, nc in determinism_diffs[:10]:
            print(f"    {run_name} [{oc['name']}]")
            print(f"      old: passed={oc['passed']} tier={oc['tier']} detail={oc['detail'][:120]}")
            print(f"      new: passed={nc['passed']} tier={nc['tier']} detail={nc['detail'][:120]}")
        if len(determinism_diffs) > 10:
            print(f"    ... and {len(determinism_diffs) - 10} more")
    else:
        print(f"  Determinism check: PASSED (every criterion present in both archive and scorer output is identical)")

    print_before_after(set_dir, old_summary, new_summary, new_criterion_names)

    if dry_run:
        print(f"\n  [DRY RUN] No files written.")

    return not determinism_diffs


def main():
    args = parse_args()
    set_dirs = resolve_set_dirs(args)
    if not set_dirs:
        print("ERROR: no result sets specified (pass dirs and/or --all)")
        sys.exit(1)

    print(f"Result sets to rescore: {len(set_dirs)}")
    for d in set_dirs:
        print(f"  {d}")

    ok = True
    for d in set_dirs:
        ok = rescore_set(d, args.dry_run) and ok

    if not ok:
        print("\nOne or more sets FAILED the determinism check — investigate before trusting rescored output.")
        sys.exit(1)


if __name__ == "__main__":
    main()
