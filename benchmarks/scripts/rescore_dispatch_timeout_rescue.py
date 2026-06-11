"""Rescue-rescore archived dispatch_compliance runs whose Agent dispatch was
lost to a timeout SIGKILL (2026-06-11).

The harness runs ``claude -p`` under ``subprocess.run(timeout=...)``, which
SIGKILLs on timeout. Claude Code's main-session transcript writes are
async/buffered, so timed-out runs lose an unflushed tail — sometimes including
the assistant record carrying the ``Agent`` tool_use. Such runs scored
``agent_dispatched: False`` even though the dispatched subagent's own
transcript was archived beside them in the run dir's ``subagents/`` folder
(worst case: a main transcript frozen at exactly the 47-line golden checkpoint
next to a 71KB subagent transcript). Subagent dirs are keyed by per-run fresh
session UUIDs, so their presence proves THAT run dispatched.

What this script does, per dispatch_compliance result set:

1. Sweeps every ``runs/*/result.json`` whose ``criteria`` contain a FAILED
   ``agent_dispatched`` entry (runs without that criterion — error results,
   transcript-not-found placeholders — and runs where dispatch passed are
   left untouched).
2. Re-scores the 10 dispatch criteria via score_dispatch_compliance() with the
   run dir's archived ``subagents/agent-*.jsonl`` files passed as recovery
   evidence (the 2026-06-11 evidence-gated fallback: type from meta.json
   ``agentType``, prompt from the subagent transcript's first user record;
   every recovered criterion detail carries a "(recovered from subagent
   transcript)" provenance suffix). Checkpoint line counts come from each
   case's golden file and expectations from the live
   ``datasets/dispatch_compliance/cases.jsonl`` — replicating
   run_dispatch_compliance.score_run().
3. For runs where recovery does not fire — no archived subagent evidence, OR
   evidence present but yielding no recovered calls (recovery-inert) — the
   recomputed criteria must reproduce the archived entries EXACTLY (the
   fallback's recovery-not-fired path is byte-identical to the pre-fallback
   scorer). Any diff means scorer or golden drift — the whole set is aborted
   with no writes (overhaul-style staging: all writes are flushed only after
   the set verifies).
4. For rescued runs (recovery fired -> agent_dispatched now passes), Phase 3b
   subagent behavior is scored from the ARCHIVED subagent transcripts via
   score_subagent_behavior_from_transcripts() — the live scorer's session_id
   lookup cannot resolve historical runs — and stored in
   ``subagent_criteria`` (previously empty for these runs).
5. ``tool_call_count`` is recomputed from the archived main transcript for
   every swept (failed-dispatch) run — the dispatch runner hardcoded 0 until
   2026-06-11. Rescued runs whose main transcript froze at the checkpoint
   legitimately keep 0. All other result.json fields are run-time facts and
   are preserved unchanged.
6. ``summary.json`` is regenerated per touched set, faithfully replicating
   run_dispatch_compliance.archive_results() aggregation (including the
   subagent_behavior block that excludes info-tier names). wall_time_s is a
   run-time fact preserved from the existing summary. Shared caveats with the
   other rescore tools: recomputed criterion_names ordering is
   first-appearance over runner-sorted runs, and sets whose run dirs were
   pruned after archival get a loud NOTICE (regenerated totals reflect disk).

Unlike rescore_criteria_overhaul.py's Phase 3 pass (which never touched main
``criteria``), changing dispatch-level criteria is the point here, so there is
no main-summary identity gate — the per-set and aggregate before/after tables
make every delta visible instead. The no-evidence determinism gate (3) is the
fidelity certificate.

Usage:
    python3 benchmarks/scripts/rescore_dispatch_timeout_rescue.py --all --dry-run
    python3 benchmarks/scripts/rescore_dispatch_timeout_rescue.py --all
    python3 benchmarks/scripts/rescore_dispatch_timeout_rescue.py 20260609_005920
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
    get_checkpoint_line_count,
)
from benchmarks.scorers.deterministic.dispatch_compliance import (
    score_dispatch_compliance,
)
from benchmarks.scorers.deterministic.subagent_behavior import (
    score_subagent_behavior_from_transcripts,
)

BASE_DIR = Path("/daaf")
RESULTS_DIR = BASE_DIR / "benchmarks" / "results"
DC_CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "dispatch_compliance" / "cases.jsonl"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rescue-rescore dispatch_compliance runs whose Agent "
                    "dispatch record was lost to a timeout SIGKILL, using "
                    "archived subagent transcripts as evidence"
    )
    parser.add_argument(
        "set_dirs",
        nargs="*",
        help="Result-set dirs (timestamps like 20260609_005920, or full paths)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rescore every results/*/ set whose manifest.json benchmark is "
             "dispatch_compliance",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes (candidate list, per-run before/after, "
             "determinism check) without writing any files",
    )
    return parser.parse_args()


def resolve_set_dirs(args) -> list[Path]:
    """Resolve positional dirs and/or --all into dispatch_compliance set dirs."""
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
        if manifest.get("benchmark") != "dispatch_compliance":
            if args.all:
                continue  # --all scan: silently skip other benchmarks
            print(f"ERROR: {p} is benchmark={manifest.get('benchmark')!r}, "
                  f"not dispatch_compliance")
            sys.exit(1)
        resolved.append(p)
    return resolved


def load_current_cases() -> dict[str, dict]:
    """Load CURRENT dispatch_compliance cases keyed by id.

    Expectations and golden paths come from the live cases.jsonl, replicating
    run_dispatch_compliance.score_run() (which scores from TestCase objects
    loaded from the same file). All 12 cases share one golden checkpoint;
    line counts are cached per golden path regardless.
    """
    cases = {}
    with open(DC_CASES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            cases[case["id"]] = case
    return cases


def perfect_main(result: dict) -> bool:
    """Viewer Perfect over main criteria: non-empty and every entry passed."""
    crits = result.get("criteria", [])
    return len(crits) > 0 and all(c["passed"] for c in crits)


def build_summary(all_results: list[dict], manifest: dict, wall_time_s) -> dict:
    """Recompute summary.json, replicating run_dispatch_compliance.archive_results()
    (same aggregation as rescore_criteria_overhaul.build_summary with
    include_subagent=True)."""
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
        "subagent_behavior": {
            "criterion_names": all_sub_criterion_names,
            "by_model": subagent_by_model,
        },
    }


def sort_runner_order(all_results: list[dict], manifest: dict):
    """Sort results to match runner ordering: case order, model order, rep."""
    case_order = {c["id"]: i for i, c in enumerate(manifest["cases"])}
    model_order = {m["name"]: i for i, m in enumerate(manifest["models"])}
    all_results.sort(
        key=lambda r: (case_order.get(r["case_id"], 99),
                       model_order.get(r["model"], 99), r["rep"])
    )


def rescore_set(set_dir: Path, current_cases: dict, dry_run: bool,
                totals: dict) -> bool:
    """Rescue-rescore one dispatch_compliance set. Returns False on
    determinism failure (in which case NOTHING is written for this set)."""
    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Rescuing: {set_dir.name}")
    print(f"{'='*80}")

    with open(set_dir / "manifest.json") as f:
        manifest = json.load(f)
    summary_path = set_dir / "summary.json"
    if not summary_path.exists():
        print(f"  ERROR: no summary.json in {set_dir} — skipping this set")
        return True
    with open(summary_path) as f:
        old_summary = json.load(f)

    line_count_cache = {}
    run_dirs = sorted(d for d in (set_dir / "runs").iterdir() if d.is_dir())
    all_results = []
    staged_writes = []  # (path, result) — flushed only after the set verifies
    determinism_diffs = []
    rescued = []        # (run_name, before_pass_count, after_pass_count, n_sub, n_sub_passed, old_tcc, new_tcc)
    tcc_only = []       # (run_name, old_tcc, new_tcc) — no evidence, count fix only
    no_transcript = []
    evidence_no_recovery = []
    perfect_flips = []
    crit_newly_passing = {}  # criterion name -> count newly passing via rescue

    for run_dir in run_dirs:
        result_path = run_dir / "result.json"
        if not result_path.exists():
            print(f"  WARNING: no result.json in {run_dir.name} — skipping")
            continue
        with open(result_path) as f:
            result = json.load(f)
        all_results.append(result)

        # Candidates: criteria contain a FAILED agent_dispatched entry
        old_criteria = result.get("criteria", [])
        ad = next((c for c in old_criteria if c["name"] == "agent_dispatched"), None)
        if ad is None or ad["passed"]:
            continue

        transcript = run_dir / "transcript.jsonl"
        if not transcript.exists():
            # Without the archived main transcript neither rescoring nor the
            # tool_call_count recompute is possible.
            no_transcript.append(run_dir.name)
            continue

        case = current_cases.get(result["case_id"])
        if case is None:
            print(f"  WARNING: case {result['case_id']} not in current "
                  f"cases.jsonl — preserving {run_dir.name}")
            continue

        golden = case["golden_checkpoint"]
        if golden not in line_count_cache:
            line_count_cache[golden] = get_checkpoint_line_count(BASE_DIR / golden)
        checkpoint_lines = line_count_cache[golden]

        # tool_call_count recompute (dispatch runner hardcoded 0 pre-2026-06-11)
        tool_calls = extract_new_tool_calls(transcript, checkpoint_lines)
        old_tcc = result.get("tool_call_count", 0)
        new_tcc = len(tool_calls)

        # Archived subagent evidence for this run (per-run session UUIDs:
        # presence proves THIS run dispatched)
        evidence = sorted((run_dir / "subagents").glob("agent-*.jsonl"))

        criterion_results = score_dispatch_compliance(
            str(transcript), checkpoint_lines, case["expected"],
            subagent_transcripts=evidence or None,
        )
        new_criteria = [
            {"name": cr.name, "passed": cr.passed, "tier": cr.tier, "detail": cr.detail}
            for cr in criterion_results
        ]
        recovery_fired = any(
            c["name"] == "agent_dispatched" and c["passed"] for c in new_criteria
        )

        if not evidence or not recovery_fired:
            # Determinism gate: with no usable evidence the fallback path is
            # inert, so the recompute must reproduce the archive EXACTLY.
            if new_criteria != old_criteria:
                for oc, nc in zip(old_criteria, new_criteria):
                    if oc != nc:
                        determinism_diffs.append((run_dir.name, oc, nc))
                if len(old_criteria) != len(new_criteria):
                    determinism_diffs.append((
                        run_dir.name,
                        {"name": "<criteria length>", "passed": len(old_criteria),
                         "tier": "-", "detail": "archived entry count"},
                        {"name": "<criteria length>", "passed": len(new_criteria),
                         "tier": "-", "detail": "recomputed entry count"},
                    ))
            if evidence and not recovery_fired:
                evidence_no_recovery.append(run_dir.name)
            if new_tcc != old_tcc:
                result["tool_call_count"] = new_tcc
                tcc_only.append((run_dir.name, old_tcc, new_tcc))
                staged_writes.append((result_path, result))
            continue

        # --- Rescue: recovery fired ---
        before_pass = sum(1 for c in old_criteria if c["passed"])
        after_pass = sum(1 for c in new_criteria if c["passed"])
        old_by_name = {c["name"]: c for c in old_criteria}
        for nc in new_criteria:
            oc = old_by_name.get(nc["name"])
            if nc["passed"] and (oc is None or not oc["passed"]):
                crit_newly_passing[nc["name"]] = crit_newly_passing.get(nc["name"], 0) + 1

        before_perfect = perfect_main(result)
        result["criteria"] = new_criteria
        result["tool_call_count"] = new_tcc

        # Phase 3b: dispatch now passes, so subagent behavior IS scorable —
        # from the ARCHIVED transcripts (live session_id lookup can't resolve
        # historical runs). Mirrors score_run()'s gating.
        expected_type = case["expected"].get("subagent_dispatched", "")
        sub_results = score_subagent_behavior_from_transcripts(evidence, expected_type)
        result["subagent_criteria"] = [
            {"name": cr.name, "passed": cr.passed, "tier": cr.tier, "detail": cr.detail}
            for cr in sub_results
        ]
        n_sub = len(result["subagent_criteria"])
        n_sub_passed = sum(1 for c in result["subagent_criteria"] if c["passed"])

        after_perfect = perfect_main(result)
        if before_perfect != after_perfect:
            perfect_flips.append((run_dir.name, before_perfect, after_perfect))

        rescued.append((run_dir.name, before_pass, after_pass,
                        n_sub, n_sub_passed, old_tcc, new_tcc))
        staged_writes.append((result_path, result))

    if determinism_diffs:
        print(f"\n  DETERMINISM CHECK FAILED: {len(determinism_diffs)} criterion "
              f"diff(s) on no-evidence runs — NO files written for this set:")
        for run_name, oc, nc in determinism_diffs[:10]:
            print(f"    {run_name} [{oc['name']}]")
            print(f"      old: passed={oc['passed']} tier={oc['tier']} detail={str(oc['detail'])[:120]}")
            print(f"      new: passed={nc['passed']} tier={nc['tier']} detail={str(nc['detail'])[:120]}")
        if len(determinism_diffs) > 10:
            print(f"    ... and {len(determinism_diffs) - 10} more")
        return False
    print("  Determinism check: PASSED (all no-evidence recomputes reproduced "
          "the archive exactly)")

    sort_runner_order(all_results, manifest)
    if len(all_results) != old_summary.get("total_runs"):
        print(f"  NOTICE: archived summary counted {old_summary.get('total_runs')} "
              f"runs but {len(all_results)} result.json files exist on disk (run "
              f"dirs deleted after archival — pre-existing condition); the "
              f"regenerated summary reflects the current archive.")
        totals["count_mismatch_sets"].append(set_dir.name)
    new_summary = build_summary(all_results, manifest, old_summary.get("wall_time_s"))

    if not dry_run:
        for path, result in staged_writes:
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
        if new_summary != old_summary:
            with open(summary_path, "w") as f:
                json.dump(new_summary, f, indent=2)

    print(f"  Runs in set: {len(all_results)} | result.json rewritten: "
          f"{len(staged_writes)} | rescued: {len(rescued)} | tool_call_count-only: "
          f"{len(tcc_only)}")
    if rescued:
        print(f"  Rescued runs (criteria passed before -> after | Phase 3b | tcc):")
        for name, b, a, ns, nsp, ot, nt in rescued:
            print(f"    {name:<34} {b}/10 -> {a}/10 | 3b: {nsp}/{ns} passed | "
                  f"tcc {ot} -> {nt}")
    if tcc_only:
        print(f"  tool_call_count-only fixes (genuine non-dispatches):")
        for name, ot, nt in tcc_only:
            print(f"    {name:<34} tcc {ot} -> {nt}")
    if no_transcript:
        print(f"  SKIPPED (failed dispatch, no archived main transcript): {no_transcript}")
    if evidence_no_recovery:
        print(f"  WARNING: evidence present but recovery yielded nothing "
              f"(unparseable?): {evidence_no_recovery}")
    if perfect_flips:
        print(f"  Viewer-Perfect flips (main criteria): {len(perfect_flips)}")
        for name, b, a in perfect_flips:
            print(f"    {name}: {b} -> {a}")
    print("  Per-model agent_dispatched / all_criteria (before -> after):")
    for model_name, new_m in new_summary["by_model"].items():
        old_m = old_summary.get("by_model", {}).get(model_name, {})
        deltas = []
        for crit in ("agent_dispatched", "all_criteria"):
            old_c = old_m.get("criteria", {}).get(crit)
            new_c = new_m.get("criteria", {}).get(crit)
            old_str = f"{old_c['passed']}/{old_c['total']}" if old_c else "n/a"
            new_str = f"{new_c['passed']}/{new_c['total']}" if new_c else "n/a"
            marker = " (CHANGED)" if old_str != new_str else ""
            deltas.append(f"{crit}: {old_str} -> {new_str}{marker}")
        print(f"    {model_name:<22} {' | '.join(deltas)}")
    if dry_run:
        print("  [DRY RUN] No files written.")

    totals["sets"] += 1
    totals["rescued"] += len(rescued)
    totals["tcc_only"] += len(tcc_only)
    totals["rewritten"] += len(staged_writes)
    totals["no_transcript"] += len(no_transcript)
    totals["perfect_flips"] += len(perfect_flips)
    totals["sub_criteria_added"] += sum(ns for _, _, _, ns, _, _, _ in rescued)
    for name, n in crit_newly_passing.items():
        totals["crit_newly_passing"][name] = totals["crit_newly_passing"].get(name, 0) + n
    return True


def main():
    args = parse_args()
    set_dirs = resolve_set_dirs(args)
    if not set_dirs:
        print("ERROR: no result sets specified (pass dirs and/or --all)")
        sys.exit(1)

    print(f"dispatch_compliance result sets to sweep: {len(set_dirs)}")
    for d in set_dirs:
        print(f"  {d.name}")

    current_cases = load_current_cases()

    totals = {
        "sets": 0, "rescued": 0, "tcc_only": 0, "rewritten": 0,
        "no_transcript": 0, "perfect_flips": 0, "sub_criteria_added": 0,
        "crit_newly_passing": {}, "count_mismatch_sets": [],
    }

    ok = True
    for d in set_dirs:
        ok = rescore_set(d, current_cases, args.dry_run, totals) and ok

    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}AGGREGATE REPORT")
    print(f"{'='*80}")
    print(f"Sets swept: {totals['sets']} | runs rescued: {totals['rescued']} | "
          f"tool_call_count-only fixes: {totals['tcc_only']} | "
          f"result.json rewritten: {totals['rewritten']}")
    print(f"Failed-dispatch runs skipped (no archived main transcript): "
          f"{totals['no_transcript']}")
    print(f"Viewer-Perfect flips: {totals['perfect_flips']} | Phase 3b criteria "
          f"entries added: {totals['sub_criteria_added']}")
    if totals["crit_newly_passing"]:
        print("Criteria newly passing via rescue:")
        for name, n in sorted(totals["crit_newly_passing"].items()):
            print(f"  {name}: +{n}")
    if totals["count_mismatch_sets"]:
        print(f"Sets with pre-existing run-dir deletions (summary totals now "
              f"reflect current disk state): {totals['count_mismatch_sets']}")

    if not ok:
        print("\nOne or more sets FAILED the determinism check — those sets were "
              "NOT written. Investigate before re-running.")
        sys.exit(1)


if __name__ == "__main__":
    main()
