"""Rescore archived Phase 2/3 result sets after the 2026-06-10 criteria overhaul.

Covers two coordinated normalizations so the historical corpus stays comparable
with future runs (pure local recompute against archived transcripts — no API):

Phase 2 (benchmark == post_confirmation):
  Re-runs score_checkpoint() against each run's ARCHIVED transcript.jsonl with
  the CURRENT datasets/post_confirmation/cases.jsonl expectations, replicating
  run_post_confirmation.py's scoring path exactly (checkpoint line count from
  the manifest-pinned golden file, extract_new_tool_calls slicing). Effects:
  - pc-07's skill_skill_authoring retiers tier1 -> tier2 (skills_loaded_soft)
  - pc-07 gains a NEW tier2 criterion skill_agent_authoring, scored
    retroactively from the archived transcript
  Runs WITHOUT an archived transcript.jsonl (timeouts) skip all
  transcript-dependent scoring (no new criteria added), but still receive the
  transcript-INDEPENDENT pure relabel: archived skill_{name} entries for
  skills now in skills_loaded_soft go tier1 -> tier2 with the "(soft)" detail
  wording, pass/fail untouched.
  Determinism gate: every criterion present in BOTH archive and new scorer
  output must reproduce identical pass/fail (full dict equality, except the
  expected-retier criteria where tier1->tier2 plus the "(soft)" detail wording
  are the sanctioned deltas). Any other diff aborts the SET with no writes —
  all writes are staged in memory and flushed only after the whole set
  verifies (unlike rescore_skill_routing.py, which writes per-run as it goes).

Phase 3 (benchmark == dispatch_compliance):
  Main dispatch-level `criteria` are NOT recomputed and NOT modified.
  `subagent_criteria` are stripped of exactly four removed always-pass names
  (explicit DENYLIST below — NOT a blanket "drop anything the scorer no longer
  emits"): subagent_transcript_found, subagent_active,
  subagent_no_code_execution, subagent_tool_summary. Unlike
  rescore_skill_routing.py's retain-all merge, dropping these is the point:
  the v1 viewer counts every stored subagent criterion (info tier included)
  toward Phase 3b Perfect, so the noise must leave the stored results.
  Retained entries are cross-checked by re-running the BEHAVIOR_SPECS checks
  over the archived runs/*/subagents/agent-*.jsonl transcripts; mismatches are
  REPORTED but never overwritten (archived pass/fail is ground truth — the
  archive was scored at run time, while sandbox paths etc. may have aged).
  Runs with empty/absent subagent_criteria are left untouched; runs whose
  subagent transcripts were not archived get the denylist strip only and are
  reported as strip-only.

summary.json is regenerated per set, faithfully replicating each runner's own
archive_results() aggregation (run_post_confirmation.py for Phase 2;
run_dispatch_compliance.py for Phase 3, including the subagent_behavior block
that excludes info-tier names). wall_time_s is a run-time fact preserved from
the existing summary. Cosmetic caveat shared with rescore_skill_routing.py:
recomputed criterion_names ordering is first-appearance over runner-sorted
runs, which can differ from the original execution-order listing.

Viewer-Perfect accounting (printed per set + aggregate): Perfect is computed
the way the v1 viewer does — main: every entry in `criteria` passes
(non-empty); Phase 3b: every entry in `subagent_criteria` passes (non-empty,
info tier counted). Expected outcomes, verified empirically rather than
assumed: pc-07 runs that loaded only skill-authoring flip out of Perfect
(skill_agent_authoring fails); Phase 3b Perfect flips should be zero because
the removed criteria always passed wherever they were stored.

Usage:
    python3 benchmarks/scripts/rescore_criteria_overhaul.py 20260608_221438 --dry-run
    python3 benchmarks/scripts/rescore_criteria_overhaul.py --all
    python3 benchmarks/scripts/rescore_criteria_overhaul.py \
        benchmarks/results/20260609_003629 20260609_004353
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
    get_checkpoint_line_count,
    score_checkpoint,
)
from benchmarks.scorers.deterministic.subagent_behavior import (
    BEHAVIOR_SPECS,
    _run_check,
    extract_subagent_tool_calls,
)

BASE_DIR = Path("/daaf")
RESULTS_DIR = BASE_DIR / "benchmarks" / "results"
PC_CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "post_confirmation" / "cases.jsonl"

TARGET_BENCHMARKS = ("post_confirmation", "dispatch_compliance")

# The four Phase 3b criteria removed from subagent_behavior.py on 2026-06-10.
# Explicit denylist: anything else archived in subagent_criteria (including
# entries from runs whose subagent transcript is missing/corrupt) is retained.
SUBAGENT_DENYLIST = {
    "subagent_transcript_found",
    "subagent_active",
    "subagent_no_code_execution",
    "subagent_tool_summary",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rescore archived post_confirmation and dispatch_compliance "
                    "result sets under the 2026-06-10 criteria overhaul"
    )
    parser.add_argument(
        "set_dirs",
        nargs="*",
        help="Result-set dirs (timestamps like 20260608_221438, or full paths)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rescore every results/*/ set whose manifest.json benchmark is "
             "post_confirmation or dispatch_compliance",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes (including determinism check and sample "
             "per-run diffs) without writing any files",
    )
    return parser.parse_args()


def resolve_set_dirs(args) -> list[tuple[Path, str]]:
    """Resolve positional dirs and/or --all into (set_dir, benchmark) pairs."""
    candidates = []
    for raw in args.set_dirs:
        p = Path(raw)
        if not p.is_absolute():
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
        benchmark = manifest.get("benchmark")
        if benchmark not in TARGET_BENCHMARKS:
            if args.all:
                continue  # --all scan: silently skip other benchmarks
            print(f"ERROR: {p} is benchmark={benchmark!r}, not one of {TARGET_BENCHMARKS}")
            sys.exit(1)
        resolved.append((p, benchmark))
    return resolved


def load_current_pc_expected() -> dict[str, dict]:
    """Load CURRENT post_confirmation expectations keyed by case id.

    Expectations come from the live cases.jsonl (not the manifest's archived
    `expected`), because the whole point of the rescore is to apply the
    updated expectations retroactively. The golden checkpoint path, by
    contrast, stays manifest-pinned (it determines historical slicing).
    """
    expected_by_id = {}
    with open(PC_CASES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            expected_by_id[case["id"]] = case["expected"]
    return expected_by_id


def merge_criteria(old_criteria: list[dict], new_criteria: list[dict]) -> list[dict]:
    """Order-stable merge of old result.json criteria with new scorer output.

    Same semantics as rescore_skill_routing.py: entries the scorer still emits
    are replaced by the new versions (new criteria slot in at scorer order);
    legacy entries the scorer no longer emits are retained in place. For
    post_confirmation no legitimate drops exist, so retention is the safe
    default for anything unexpected (e.g., transcript_found placeholders on
    runs we never reach because they have no transcript).
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


def perfect_main(result: dict) -> bool:
    """Viewer Perfect over main criteria: non-empty and every entry passed."""
    crits = result.get("criteria", [])
    return len(crits) > 0 and all(c["passed"] for c in crits)


def perfect_subagent(criteria: list[dict]):
    """Viewer Phase 3b Perfect: every stored entry (info included) passed.

    Returns None for an empty list — the run has no Phase 3b membership at
    all (the viewer's 3b group only counts runs with subagent_criteria).
    """
    if not criteria:
        return None
    return all(c["passed"] for c in criteria)


def build_summary(all_results: list[dict], manifest: dict, wall_time_s,
                  include_subagent: bool) -> dict:
    """Recompute summary.json, replicating the owning runner's archive_results().

    include_subagent=False replicates run_post_confirmation.py;
    include_subagent=True adds run_dispatch_compliance.py's subagent_behavior
    block (criterion names exclude info tier; by_model carries
    runs_with_subagent). Everything else is byte-for-byte the same aggregation
    in both runners.
    """
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

    summary = {
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

    if include_subagent:
        all_sub_criterion_names = []
        seen_sub = set()
        for r in all_results:
            for sc in r.get("subagent_criteria", []):
                if sc["tier"] == "info":
                    continue
                name = sc["name"]
                if name not in seen_sub:
                    all_sub_criterion_names.append(name)
                    seen_sub.add(name)

        subagent_by_model = {}
        for m in manifest["models"]:
            rows = [r for r in all_results
                    if r["model"] == m["name"] and r.get("subagent_criteria")]
            if not rows:
                continue
            rates = {}
            for crit_name in all_sub_criterion_names:
                passed = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name and c["passed"]
                           for c in r.get("subagent_criteria", []))
                )
                total = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name for c in r.get("subagent_criteria", []))
                )
                if total > 0:
                    rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
            subagent_by_model[m["name"]] = {"criteria": rates, "runs_with_subagent": len(rows)}

        summary["subagent_behavior"] = {
            "criterion_names": all_sub_criterion_names,
            "by_model": subagent_by_model,
        }

    return summary


def sort_runner_order(all_results: list[dict], manifest: dict):
    """Sort results to match runner ordering: case order, model order, rep."""
    case_order = {c["id"]: i for i, c in enumerate(manifest["cases"])}
    model_order = {m["name"]: i for i, m in enumerate(manifest["models"])}
    all_results.sort(
        key=lambda r: (case_order.get(r["case_id"], 99),
                       model_order.get(r["model"], 99), r["rep"])
    )


def print_criteria_diff(label: str, old: list[dict], new: list[dict]):
    """Print a full before/after listing of one run's criteria entries."""
    print(f"\n  Sample run diff: {label}")
    print(f"    BEFORE ({len(old)} entries):")
    for c in old:
        print(f"      {c['name']:<36} passed={c['passed']!s:<5} tier={c['tier']:<5} | {c['detail'][:90]}")
    print(f"    AFTER  ({len(new)} entries):")
    for c in new:
        print(f"      {c['name']:<36} passed={c['passed']!s:<5} tier={c['tier']:<5} | {c['detail'][:90]}")


def summary_delta_report(old_summary: dict, new_summary: dict):
    """Print per-model all_criteria before/after plus changed criterion rates."""
    print("  Per-model all_criteria (Perfect-equivalent in summary terms):")
    for model_name, new_m in new_summary["by_model"].items():
        old_m = old_summary.get("by_model", {}).get(model_name, {})
        old_c = old_m.get("criteria", {}).get("all_criteria")
        new_c = new_m.get("criteria", {}).get("all_criteria")
        old_str = f"{old_c['passed']}/{old_c['total']}" if old_c else "n/a"
        new_str = f"{new_c['passed']}/{new_c['total']}" if new_c else "n/a"
        marker = "  (CHANGED)" if old_str != new_str else ""
        print(f"    {model_name:<22} {old_str:>7} -> {new_str:<7}{marker}")


# ---------------------------------------------------------------------------
# Phase 2: post_confirmation rescore
# ---------------------------------------------------------------------------

def rescore_post_confirmation(set_dir: Path, current_expected: dict,
                              dry_run: bool, totals: dict) -> bool:
    """Rescore one post_confirmation set. Returns False on determinism failure
    (in which case NOTHING is written for this set)."""
    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Rescoring post_confirmation: {set_dir.name}")
    print(f"{'='*80}")

    with open(set_dir / "manifest.json") as f:
        manifest = json.load(f)
    summary_path = set_dir / "summary.json"
    if not summary_path.exists():
        print(f"  ERROR: no summary.json in {set_dir} — skipping this set")
        return True
    with open(summary_path) as f:
        old_summary = json.load(f)

    cases_by_id = {c["id"]: c for c in manifest["cases"]}
    line_count_cache = {}

    run_dirs = sorted(d for d in (set_dir / "runs").iterdir() if d.is_dir())
    all_results = []
    staged_writes = []  # (path, result) — flushed only after the set verifies
    skipped = []
    determinism_diffs = []
    retier_count = 0
    new_crit_counts = {}  # name -> [passed, total]
    perfect_flips = []  # (run_name, before, after)
    sample_printed = False

    for run_dir in run_dirs:
        result_path = run_dir / "result.json"
        if not result_path.exists():
            print(f"  WARNING: no result.json in {run_dir.name} — skipping")
            continue
        with open(result_path) as f:
            result = json.load(f)

        transcript = run_dir / "transcript.jsonl"
        if not transcript.exists():
            # Timeout / no-session run: transcript-DEPENDENT scoring (new
            # criteria such as pc-07's skill_agent_authoring) is impossible and
            # is skipped. But the skills_loaded -> skills_loaded_soft retier is
            # a pure relabel — tier1 -> tier2 plus the "(soft)" detail wording,
            # pass/fail untouched — that depends only on the CURRENT
            # expectations, so apply it here too (2026-06-10 follow-up: the
            # original bundling of the relabel with transcript-dependent
            # scoring left timed-out runs carrying stale tier1 entries).
            cur_exp = current_expected.get(result["case_id"]) or {}
            relabelled = 0
            for s in cur_exp.get("skills_loaded_soft", []):
                cname = "skill_" + s.replace("-", "_")
                for c in result["criteria"]:
                    if c["name"] == cname and c["tier"] == "tier1":
                        c["tier"] = "tier2"
                        c["detail"] = f"{'Loaded' if c['passed'] else 'Missing'} (soft): {s}"
                        relabelled += 1
            if relabelled:
                retier_count += relabelled
                staged_writes.append((result_path, result))
            skipped.append(run_dir.name)
            all_results.append(result)
            continue

        case = cases_by_id.get(result["case_id"])
        if case is None:
            print(f"  WARNING: case {result['case_id']} not in manifest — preserving {run_dir.name}")
            all_results.append(result)
            continue
        cur_exp = current_expected.get(result["case_id"])
        if cur_exp is None:
            print(f"  ERROR: case {result['case_id']} missing from current cases.jsonl — aborting set")
            return False

        # Checkpoint slicing from the manifest-pinned golden path. Goldens were
        # content-refreshed in place with unchanged record counts; if that
        # assumption is wrong the determinism gate below trips on every
        # criterion of the affected case.
        golden = case["golden_checkpoint"]
        if golden not in line_count_cache:
            line_count_cache[golden] = get_checkpoint_line_count(BASE_DIR / golden)
        checkpoint_lines = line_count_cache[golden]

        tool_calls = extract_new_tool_calls(transcript, checkpoint_lines)
        criterion_results = score_checkpoint(tool_calls, cur_exp)
        new_criteria = [
            {"name": cr.name, "passed": cr.passed, "tier": cr.tier, "detail": cr.detail}
            for cr in criterion_results
        ]

        # Expected retiers: skill_{name} criteria for skills now listed in
        # skills_loaded_soft (formerly skills_loaded). Sanctioned delta is
        # tier1 -> tier2 with a "(soft)" detail rewording; pass/fail must hold.
        allowed_retier = {
            "skill_" + s.replace("-", "_")
            for s in cur_exp.get("skills_loaded_soft", [])
        }

        old_by_name = {c["name"]: c for c in result["criteria"]}
        run_new_names = {nc["name"] for nc in new_criteria} - set(old_by_name)
        for nc in new_criteria:
            oc = old_by_name.get(nc["name"])
            if oc is None:
                counts = new_crit_counts.setdefault(nc["name"], [0, 0])
                counts[1] += 1
                if nc["passed"]:
                    counts[0] += 1
                continue
            if nc["name"] in allowed_retier:
                if oc["passed"] != nc["passed"] or nc["tier"] != "tier2":
                    determinism_diffs.append((run_dir.name, oc, nc))
                elif oc["tier"] != nc["tier"]:
                    retier_count += 1
            elif oc != nc:
                determinism_diffs.append((run_dir.name, oc, nc))

        old_criteria = result["criteria"]
        merged = merge_criteria(old_criteria, new_criteria)

        before_perfect = perfect_main(result)
        result["criteria"] = merged
        after_perfect = perfect_main(result)
        if before_perfect != after_perfect:
            perfect_flips.append((run_dir.name, before_perfect, after_perfect))

        all_results.append(result)
        if merged != old_criteria:
            staged_writes.append((result_path, result))
            if dry_run and not sample_printed and result["case_id"] == "pc-07":
                print_criteria_diff(run_dir.name, old_criteria, merged)
                sample_printed = True

    if determinism_diffs:
        print(f"\n  DETERMINISM CHECK FAILED: {len(determinism_diffs)} criterion diff(s) — "
              f"NO files written for this set:")
        for run_name, oc, nc in determinism_diffs[:10]:
            print(f"    {run_name} [{oc['name']}]")
            print(f"      old: passed={oc['passed']} tier={oc['tier']} detail={oc['detail'][:120]}")
            print(f"      new: passed={nc['passed']} tier={nc['tier']} detail={nc['detail'][:120]}")
        if len(determinism_diffs) > 10:
            print(f"    ... and {len(determinism_diffs) - 10} more")
        return False
    print("  Determinism check: PASSED (all reproduced criteria identical; "
          f"{retier_count} sanctioned tier1->tier2 retier(s))")

    sort_runner_order(all_results, manifest)
    if len(all_results) != old_summary.get("total_runs"):
        # Pre-existing archive inconsistency (run dirs deleted after the
        # original archive): the regenerated summary reflects what is on disk
        # NOW. Surface loudly — totals/costs shift beyond the criteria change.
        print(f"  NOTICE: archived summary counted {old_summary.get('total_runs')} runs "
              f"but only {len(all_results)} result.json files exist on disk — "
              f"regenerated summary reflects the current archive (totals/costs shift).")
        totals["pc_count_mismatch_sets"].append(set_dir.name)
    new_summary = build_summary(all_results, manifest,
                                old_summary.get("wall_time_s"),
                                include_subagent=False)

    if not dry_run:
        for path, result in staged_writes:
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
        if new_summary != old_summary:
            with open(summary_path, "w") as f:
                json.dump(new_summary, f, indent=2)

    print(f"  Runs in set: {len(all_results)} | result.json rewritten: {len(staged_writes)} "
          f"| skipped (no transcript): {len(skipped)}")
    for name, (passed, total) in sorted(new_crit_counts.items()):
        print(f"  NEW criterion {name}: {passed}/{total} passed across rescored runs")
    if perfect_flips:
        print(f"  Viewer-Perfect flips: {len(perfect_flips)}")
        for name, b, a in perfect_flips:
            print(f"    {name}: {b} -> {a}")
    else:
        print("  Viewer-Perfect flips: 0")
    summary_delta_report(old_summary, new_summary)
    if dry_run:
        print("  [DRY RUN] No files written.")

    totals["pc_sets"] += 1
    totals["pc_runs_touched"] += len(staged_writes)
    totals["pc_retier"] += retier_count
    totals["pc_perfect_flips"] += len(perfect_flips)
    for name, (passed, total) in new_crit_counts.items():
        agg = totals["pc_new_crit"].setdefault(name, [0, 0])
        agg[0] += passed
        agg[1] += total
    return True


# ---------------------------------------------------------------------------
# Phase 3: dispatch_compliance subagent-criteria normalization
# ---------------------------------------------------------------------------

def recompute_subagent_criteria(run_dir: Path, expected_agent_type: str):
    """Re-run the CURRENT subagent scorer logic over ARCHIVED subagent
    transcripts (runs/*/subagents/agent-*.jsonl).

    Mirrors score_subagent_behavior() but reads the archived copies directly —
    the live scorer resolves transcripts via session_id from _sandbox/ or
    ~/.claude/projects/, which no longer exist for historical runs.

    Returns a list of criterion dicts, or None when no archived subagent
    transcripts exist (cross-check impossible).
    """
    subagents_dir = run_dir / "subagents"
    if not subagents_dir.exists():
        return None
    transcripts = sorted(subagents_dir.glob("agent-*.jsonl"))
    if not transcripts:
        return None

    all_tool_calls = []
    for t in transcripts:
        all_tool_calls.extend(extract_subagent_tool_calls(t))

    specs = BEHAVIOR_SPECS.get(expected_agent_type, [])
    if not specs:
        # Replicates the scorer's subagent_behavior_defined tripwire
        return [{
            "name": "subagent_behavior_defined",
            "passed": False,
            "tier": "tier2",
            "detail": f"No behavior specs defined for agent type '{expected_agent_type}'.",
        }]

    results = []
    for spec in specs:
        passed, detail = _run_check(spec, all_tool_calls)
        results.append({
            "name": spec["name"],
            "passed": passed,
            "tier": spec["tier"],
            "detail": detail,
        })
    return results


def rescore_dispatch_compliance(set_dir: Path, dry_run: bool, totals: dict) -> bool:
    """Normalize one dispatch_compliance set (denylist strip + cross-check)."""
    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Rescoring dispatch_compliance: {set_dir.name}")
    print(f"{'='*80}")

    with open(set_dir / "manifest.json") as f:
        manifest = json.load(f)
    summary_path = set_dir / "summary.json"
    if not summary_path.exists():
        print(f"  ERROR: no summary.json in {set_dir} — skipping this set")
        return True
    with open(summary_path) as f:
        old_summary = json.load(f)

    cases_by_id = {c["id"]: c for c in manifest["cases"]}

    run_dirs = sorted(d for d in (set_dir / "runs").iterdir() if d.is_dir())
    all_results = []
    staged_writes = []
    removed_by_name = {}
    runs_stripped = 0
    runs_crosschecked = 0
    strip_only_runs = []
    crosscheck_mismatches = []  # (run_name, name, archived, recomputed)
    perfect_flips_3b = []  # (run_name, before, after)
    runs_left_3b = []  # stripped to empty -> exits the viewer's 3b group
    sample_printed = False

    for run_dir in run_dirs:
        result_path = run_dir / "result.json"
        if not result_path.exists():
            print(f"  WARNING: no result.json in {run_dir.name} — skipping")
            continue
        with open(result_path) as f:
            result = json.load(f)

        sub = result.get("subagent_criteria", [])
        if not sub:
            all_results.append(result)
            continue

        stripped = [c for c in sub if c["name"] not in SUBAGENT_DENYLIST]
        for c in sub:
            if c["name"] in SUBAGENT_DENYLIST:
                removed_by_name[c["name"]] = removed_by_name.get(c["name"], 0) + 1

        # Cross-check retained entries against a re-run of the current scorer
        # over the ARCHIVED subagent transcripts. Mismatches are reported only;
        # archived pass/fail stays (ground truth at scoring time).
        case = cases_by_id.get(result["case_id"])
        expected_type = (case or {}).get("expected", {}).get("subagent_dispatched", "")
        recomputed = recompute_subagent_criteria(run_dir, expected_type)
        if recomputed is None:
            strip_only_runs.append(run_dir.name)
        else:
            runs_crosschecked += 1
            rec_by_name = {c["name"]: c for c in recomputed}
            ret_by_name = {c["name"]: c for c in stripped}
            for name in set(rec_by_name) | set(ret_by_name):
                if rec_by_name.get(name) != ret_by_name.get(name):
                    crosscheck_mismatches.append(
                        (run_dir.name, name, ret_by_name.get(name), rec_by_name.get(name))
                    )

        before_p = perfect_subagent(sub)
        after_p = perfect_subagent(stripped)
        if not stripped:
            runs_left_3b.append((run_dir.name, before_p))
        elif before_p != after_p:
            perfect_flips_3b.append((run_dir.name, before_p, after_p))

        if stripped != sub:
            runs_stripped += 1
            if dry_run and not sample_printed:
                print_criteria_diff(f"{run_dir.name} (subagent_criteria)", sub, stripped)
                sample_printed = True
            result["subagent_criteria"] = stripped
            staged_writes.append((result_path, result))
        all_results.append(result)

    sort_runner_order(all_results, manifest)
    new_summary = build_summary(all_results, manifest,
                                old_summary.get("wall_time_s"),
                                include_subagent=True)

    # Consistency check: main criteria were not touched, so when every
    # archived run still exists on disk the dispatch-level summary blocks must
    # reproduce the archive exactly — any diff means the reconstruction is
    # wrong, so abort writes for this set. Exception: some historical sets had
    # run dirs deleted AFTER archival (pre-existing condition, e.g. pruned
    # timed-out runs), making exact reproduction impossible; for those the
    # regenerated summary legitimately reflects the current disk state (the
    # viewer reads result.json files directly, never the archived totals), so
    # proceed with a loud NOTICE instead. The strict path passing on the
    # count-reconciling sets is what certifies the builder's fidelity.
    if len(all_results) != old_summary.get("total_runs"):
        print(f"  NOTICE: archived summary counted {old_summary.get('total_runs')} runs "
              f"but {len(all_results)} result.json files exist on disk (run dirs "
              f"deleted after archival — pre-existing condition). Strict "
              f"main-summary comparison impossible; regenerated summary reflects "
              f"the current archive (totals/costs shift beyond the criteria change).")
        totals["dc_count_mismatch_sets"].append(set_dir.name)
    else:
        main_consistent = all(
            new_summary.get(k) == old_summary.get(k)
            for k in ("total_runs", "criterion_names", "by_model", "by_case")
        )
        if not main_consistent:
            print("  ERROR: regenerated dispatch-level summary blocks do not match the "
                  "archived summary (main criteria are untouched, so they must) — "
                  "NO files written for this set.")
            for k in ("total_runs", "criterion_names", "by_model", "by_case"):
                if new_summary.get(k) != old_summary.get(k):
                    print(f"    mismatching block: {k}")
            return False
        print("  Main-summary consistency check: PASSED (dispatch-level blocks identical)")

    if not dry_run:
        for path, result in staged_writes:
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
        if new_summary != old_summary:
            with open(summary_path, "w") as f:
                json.dump(new_summary, f, indent=2)

    print(f"  Runs in set: {len(all_results)} | result.json rewritten: {len(staged_writes)}")
    print(f"  Denylist entries removed: "
          f"{ {k: v for k, v in sorted(removed_by_name.items())} or 'none'}")
    print(f"  Cross-checked against archived subagent transcripts: {runs_crosschecked} run(s)")
    if strip_only_runs:
        print(f"  STRIP-ONLY (no archived subagent transcript; retained entries kept "
              f"unverified): {strip_only_runs}")
    if crosscheck_mismatches:
        print(f"  CROSS-CHECK MISMATCHES (archived kept as ground truth): "
              f"{len(crosscheck_mismatches)}")
        for run_name, name, archived, recomputed in crosscheck_mismatches[:10]:
            print(f"    {run_name} [{name}]")
            print(f"      archived:   {archived}")
            print(f"      recomputed: {recomputed}")
        if len(crosscheck_mismatches) > 10:
            print(f"    ... and {len(crosscheck_mismatches) - 10} more")
    else:
        print("  Cross-check: all retained entries reproduced exactly")
    if perfect_flips_3b:
        print(f"  Phase 3b viewer-Perfect flips: {len(perfect_flips_3b)}")
        for name, b, a in perfect_flips_3b:
            print(f"    {name}: {b} -> {a}")
    else:
        print("  Phase 3b viewer-Perfect flips: 0")
    if runs_left_3b:
        print(f"  Runs leaving Phase 3b entirely (subagent_criteria now empty): {runs_left_3b}")
    if dry_run:
        print("  [DRY RUN] No files written.")

    totals["dc_sets"] += 1
    totals["dc_runs_stripped"] += runs_stripped
    totals["dc_crosschecked"] += runs_crosschecked
    totals["dc_strip_only"] += len(strip_only_runs)
    totals["dc_mismatches"] += len(crosscheck_mismatches)
    totals["dc_perfect_flips"] += len(perfect_flips_3b)
    totals["dc_left_3b"] += len(runs_left_3b)
    for name, n in removed_by_name.items():
        totals["dc_removed_by_name"][name] = totals["dc_removed_by_name"].get(name, 0) + n
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    set_dirs = resolve_set_dirs(args)
    if not set_dirs:
        print("ERROR: no result sets specified (pass dirs and/or --all)")
        sys.exit(1)

    pc_sets = [(p, b) for p, b in set_dirs if b == "post_confirmation"]
    dc_sets = [(p, b) for p, b in set_dirs if b == "dispatch_compliance"]
    print(f"Result sets to rescore: {len(set_dirs)} "
          f"(post_confirmation: {len(pc_sets)}, dispatch_compliance: {len(dc_sets)})")
    for p, b in set_dirs:
        print(f"  {p.name}  [{b}]")

    current_expected = load_current_pc_expected()

    totals = {
        "pc_sets": 0, "pc_runs_touched": 0, "pc_retier": 0,
        "pc_perfect_flips": 0, "pc_new_crit": {}, "pc_count_mismatch_sets": [],
        "dc_sets": 0, "dc_runs_stripped": 0, "dc_crosschecked": 0,
        "dc_strip_only": 0, "dc_mismatches": 0, "dc_perfect_flips": 0,
        "dc_left_3b": 0, "dc_removed_by_name": {}, "dc_count_mismatch_sets": [],
    }

    ok = True
    for p, benchmark in set_dirs:
        if benchmark == "post_confirmation":
            ok = rescore_post_confirmation(p, current_expected, args.dry_run, totals) and ok
        else:
            ok = rescore_dispatch_compliance(p, args.dry_run, totals) and ok

    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}AGGREGATE REPORT")
    print(f"{'='*80}")
    print(f"post_confirmation: {totals['pc_sets']} set(s) | "
          f"{totals['pc_runs_touched']} result.json rewritten | "
          f"{totals['pc_retier']} tier1->tier2 retiers | "
          f"{totals['pc_perfect_flips']} viewer-Perfect flips")
    for name, (passed, total) in sorted(totals["pc_new_crit"].items()):
        print(f"  NEW criterion {name}: {passed}/{total} passed "
              f"({total - passed} run(s) now fail it)")
    print(f"dispatch_compliance: {totals['dc_sets']} set(s) | "
          f"{totals['dc_runs_stripped']} result.json rewritten | "
          f"{totals['dc_crosschecked']} cross-checked | "
          f"{totals['dc_strip_only']} strip-only | "
          f"{totals['dc_mismatches']} cross-check mismatch(es) | "
          f"{totals['dc_perfect_flips']} Phase 3b Perfect flips | "
          f"{totals['dc_left_3b']} run(s) left Phase 3b")
    for name, n in sorted(totals["dc_removed_by_name"].items()):
        print(f"  removed {name}: {n} entr{'y' if n == 1 else 'ies'}")
    mismatch_sets = totals["pc_count_mismatch_sets"] + totals["dc_count_mismatch_sets"]
    if mismatch_sets:
        print(f"Sets with pre-existing run-dir deletions (summary totals now reflect "
              f"current disk state): {mismatch_sets}")

    if not ok:
        print("\nOne or more sets FAILED verification — those sets were NOT written. "
              "Investigate before re-running.")
        sys.exit(1)


if __name__ == "__main__":
    main()
