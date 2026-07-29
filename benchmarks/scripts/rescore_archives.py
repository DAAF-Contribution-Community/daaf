#!/usr/bin/env python3
"""Re-score archived dispatch_compliance result sets under the CURRENT scorer.

Motivation
----------
DAAFBench archives are immutable as to their MEASUREMENT and PROVENANCE fields
(tokens, cost, timing, transcripts, route identity — see README § 8). They are
NOT frozen against correction of a scoring VERDICT that was produced by an
incorrect scorer. When a deterministic scoring bug is fixed, the archived
transcripts (which stay untouched) can be re-scored under the corrected
criteria. This is that sanctioned, provenance-stamped rescore path.

Concretely this addresses the 2026-07-28 heading-normalization fix in
``score_dispatch_compliance`` (criteria ``prompt_has_task_section`` /
``prompt_has_context_section`` / ``prompt_has_instructions``), which replaced
case-sensitive exact-label matching with structural concept matching. The number
of archived criterion FAILs this flips to PASS is archive-dependent — it varies
with how many stored dispatch prompts used synonym headings (e.g. GPT prompts
using ``## Output format``), and may be large or small for any given result set.

What it does
------------
For every ``results/*/`` set whose manifest identifies it as
``dispatch_compliance`` (or whose cases are ``dc-*``), for every
``runs/*/`` directory with a ``transcript.jsonl``:

  * Re-derive ``checkpoint_line_count`` and the case ``expected`` dict from the
    set's OWN golden checkpoint + manifest, exactly as the runner's
    ``score_run`` does, so rescored values are comparable to a fresh run.
  * Re-run the CURRENT ``score_dispatch_compliance`` (with the run dir's
    archived ``subagents/`` as recovery evidence) and, where a ``subagents/``
    directory exists, ``score_subagent_behavior_from_transcripts``.
  * Rewrite ONLY the ``criteria`` / ``subagent_criteria`` pass fields of
    ``result.json``, preserving every other field, and additively stamp
    ``rescored_at`` (ISO-8601 UTC) + ``rescore_reason``.
  * Recompute the criteria-derived rollups of ``summary.json`` (criterion
    names, per-model + per-case pass rates, subagent-behavior rollup),
    preserving cost / coverage / error_counts / tool_failures untouched, and
    stamp ``rescored_at``.

Transcripts are NEVER modified. Non-dispatch batteries are NEVER touched.

Usage
-----
  python3 benchmarks/scripts/rescore_archives.py            # dry-run (default)
  python3 benchmarks/scripts/rescore_archives.py --apply    # write changes

Import-light and function-structured (a benchmark utility, not a DAAF research
pipeline script): sequential-inline style does not apply here.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# --- Config ---
# Make the repo root importable so `benchmarks.*` resolves when this script is
# run directly (python3 benchmarks/scripts/rescore_archives.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.scorers.deterministic.checkpoint_adherence import (
    get_checkpoint_line_count,
)
from benchmarks.scorers.deterministic.dispatch_compliance import (
    score_dispatch_compliance,
)
from benchmarks.scorers.deterministic.subagent_behavior import (
    score_subagent_behavior_from_transcripts,
)
from benchmarks.harness.artifacts import is_scorable

BASE_DIR = Path("/daaf")
RESCORE_REASON = "heading-normalization-2026-07-28"


def load_json(path: Path):
    """Load a JSON file, returning None on any read/parse error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def atomic_write_json(path: Path, obj) -> None:
    """Write JSON to ``path`` atomically (temp file in the same dir + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def is_dispatch_set(manifest: dict) -> bool:
    """True when a result set is a dispatch_compliance battery.

    Primary signal: manifest ``benchmark`` == "dispatch_compliance". Fallback:
    any case id begins with "dc-" (covers older manifests lacking the field).
    """
    if not isinstance(manifest, dict):
        return False
    if manifest.get("benchmark") == "dispatch_compliance":
        return True
    for case in manifest.get("cases", []) or []:
        if isinstance(case, dict) and str(case.get("id", "")).startswith("dc-"):
            return True
    return False


def criteria_to_dicts(results) -> list:
    """Convert CriterionResult objects to the result.json dict shape."""
    return [
        {"name": cr.name, "passed": cr.passed, "tier": cr.tier, "detail": cr.detail}
        for cr in results
    ]


def case_index(manifest: dict) -> dict:
    """Map case id -> its manifest entry (carries golden_checkpoint + expected)."""
    idx = {}
    for case in manifest.get("cases", []) or []:
        if isinstance(case, dict) and "id" in case:
            idx[case["id"]] = case
    return idx


def rescore_run(run_dir: Path, case: dict) -> dict | None:
    """Rescore one run directory. Returns a dict describing the outcome or None.

    Replicates score_run's argument derivation: checkpoint line count from the
    case's OWN golden checkpoint, expected dict from the manifest case. Returns
    ``None`` when the run cannot be rescored (no transcript / no golden), so the
    caller can leave it untouched.
    """
    transcript = run_dir / "transcript.jsonl"
    if not transcript.exists():
        return None
    result = load_json(run_dir / "result.json")
    if result is None:
        return None

    golden_checkpoint = case.get("golden_checkpoint")
    if not golden_checkpoint:
        return None
    golden_path = BASE_DIR / golden_checkpoint
    if not golden_path.exists():
        return {"status": "skipped_no_golden", "golden": str(golden_path)}
    checkpoint_lines = get_checkpoint_line_count(golden_path)

    expected = case.get("expected", {}) or {}

    # Archived subagent transcripts (recovery evidence + Phase 3b behavior).
    sub_dir = run_dir / "subagents"
    subagent_transcripts = (
        sorted(sub_dir.rglob("*.jsonl")) if sub_dir.exists() else []
    )

    new_criteria = criteria_to_dicts(
        score_dispatch_compliance(
            str(transcript), checkpoint_lines, expected,
            subagent_transcripts=subagent_transcripts,
        )
    )

    # Subagent behavior: re-run only where subagent transcripts exist, matching
    # score_run's gate (agent_dispatched + expected type). Criteria semantics
    # are unchanged by this fix, but re-running keeps the archive internally
    # consistent with the current scorer.
    expected_type = expected.get("subagent_dispatched", "")
    agent_dispatched = any(
        c["name"] == "agent_dispatched" and c["passed"] for c in new_criteria
    )
    new_sub_criteria = None
    if agent_dispatched and expected_type and subagent_transcripts:
        new_sub_criteria = criteria_to_dicts(
            score_subagent_behavior_from_transcripts(
                subagent_transcripts, expected_type
            )
        )

    old_criteria = result.get("criteria", [])
    old_sub_criteria = result.get("subagent_criteria", [])

    criteria_changed = _criteria_pass_map(old_criteria) != _criteria_pass_map(
        new_criteria
    )
    sub_changed = new_sub_criteria is not None and (
        _criteria_pass_map(old_sub_criteria) != _criteria_pass_map(new_sub_criteria)
    )

    return {
        "status": "rescored",
        "result": result,
        "new_criteria": new_criteria,
        "new_sub_criteria": new_sub_criteria,
        "old_criteria": old_criteria,
        "changed": criteria_changed or sub_changed,
        "criteria_changed": criteria_changed,
        "sub_changed": sub_changed,
    }


def _criteria_pass_map(criteria) -> dict:
    """Map criterion name -> passed bool (order-independent change detection)."""
    return {c["name"]: bool(c["passed"]) for c in criteria or []}


def _rates_for_rows(scored_rows, criterion_names, key) -> dict:
    """Recompute the criteria-rate sub-dict for a group of rows.

    Faithful reimplementation of the runner's per-model / per-case aggregation
    (run_dispatch_compliance.py): per-criterion passed/total/rate over scorable
    rows, plus the ``all_criteria`` all-pass rate. ``key`` is the result field
    holding the criteria list ("criteria" or "subagent_criteria").
    """
    rates = {}
    for crit_name in criterion_names:
        passed = sum(
            1 for r in scored_rows
            if any(c["name"] == crit_name and c["passed"] for c in r.get(key, []))
        )
        total = sum(
            1 for r in scored_rows
            if any(c["name"] == crit_name for c in r.get(key, []))
        )
        if total > 0:
            rates[crit_name] = {
                "passed": passed, "total": total, "rate": passed / total,
            }
    return rates


def recompute_summary(summary: dict, rows: list, manifest: dict) -> dict:
    """Recompute ONLY the criteria-derived rollups of summary.json.

    Cost, coverage, error_counts, tool_failures, and all provenance fields are
    preserved verbatim — the rescore changes only criterion pass/fail, so those
    fields are unchanged by construction. Adds an additive ``rescored_at`` stamp.
    """
    # First-seen order of criterion names across all runs (matches runner).
    all_criterion_names = []
    seen = set()
    for r in rows:
        for crit in r.get("criteria", []):
            if crit["name"] not in seen:
                all_criterion_names.append(crit["name"])
                seen.add(crit["name"])
    summary["criterion_names"] = all_criterion_names

    # Per-model criteria rates (preserve every other by_model field).
    for model_name, model_entry in (summary.get("by_model") or {}).items():
        model_rows = [r for r in rows if r.get("model") == model_name]
        scored_rows = [r for r in model_rows if is_scorable(r)]
        rates = _rates_for_rows(scored_rows, all_criterion_names, "criteria")
        all_pass = sum(
            1 for r in scored_rows
            if r.get("criteria") and all(c["passed"] for c in r["criteria"])
        )
        scored_n = len(scored_rows)
        rates["all_criteria"] = {
            "passed": all_pass,
            "total": scored_n,
            "rate": all_pass / scored_n if scored_n else 0.0,
        }
        model_entry["criteria"] = rates

    # Per-case criteria rates (preserve every other by_case field).
    for case_id, case_entry in (summary.get("by_case") or {}).items():
        case_rows = [r for r in rows if r.get("case_id") == case_id]
        scored_rows = [r for r in case_rows if is_scorable(r)]
        rates = _rates_for_rows(scored_rows, all_criterion_names, "criteria")
        all_pass = sum(
            1 for r in scored_rows
            if r.get("criteria") and all(c["passed"] for c in r["criteria"])
        )
        scored_n = len(scored_rows)
        rates["all_criteria"] = {
            "passed": all_pass,
            "total": scored_n,
            "rate": all_pass / scored_n if scored_n else 0.0,
        }
        case_entry["criteria"] = rates

    # Subagent-behavior rollup (criteria only; skip info-tier, matching runner).
    sub_block = summary.get("subagent_behavior") or {}
    all_sub_names = []
    seen_sub = set()
    for r in rows:
        for sc in r.get("subagent_criteria", []):
            if sc.get("tier") == "info":
                continue
            if sc["name"] not in seen_sub:
                all_sub_names.append(sc["name"])
                seen_sub.add(sc["name"])
    sub_block["criterion_names"] = all_sub_names
    for model_name, sub_entry in (sub_block.get("by_model") or {}).items():
        model_rows = [
            r for r in rows
            if r.get("model") == model_name and r.get("subagent_criteria")
        ]
        sub_entry["criteria"] = _rates_for_rows(
            model_rows, all_sub_names, "subagent_criteria"
        )
        sub_entry["runs_with_subagent"] = len(model_rows)
    summary["subagent_behavior"] = sub_block

    summary["rescored_at"] = datetime.now(timezone.utc).isoformat()
    return summary


def process_set(set_dir: Path, apply: bool, reason: str = RESCORE_REASON) -> dict:
    """Rescore one result set. Returns a stats dict for reporting.

    ``reason`` is stamped into each rescored row's ``rescore_reason`` field;
    it defaults to the module constant so existing behavior is unchanged.
    """
    manifest = load_json(set_dir / "manifest.json")
    if not is_dispatch_set(manifest or {}):
        return {"set": set_dir.name, "skipped": "not_dispatch"}

    cases = case_index(manifest)
    runs_dir = set_dir / "runs"
    if not runs_dir.exists():
        return {"set": set_dir.name, "skipped": "no_runs"}

    stats = {
        "set": set_dir.name,
        "runs_seen": 0,
        "runs_rescored": 0,
        "runs_changed": 0,
        "criterion_flips": {},   # criterion name -> {"F->P": n, "P->F": n}
        "no_golden": 0,
    }
    updated_rows = []

    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        result = load_json(run_dir / "result.json")
        if result is None:
            continue
        stats["runs_seen"] += 1
        case_id = result.get("case_id", "")
        case = cases.get(case_id)
        if case is None:
            updated_rows.append(result)
            continue

        outcome = rescore_run(run_dir, case)
        if outcome is None:
            updated_rows.append(result)
            continue
        if outcome.get("status") == "skipped_no_golden":
            stats["no_golden"] += 1
            updated_rows.append(result)
            continue

        stats["runs_rescored"] += 1

        # Tally criterion flips for the report.
        old_map = _criteria_pass_map(outcome["old_criteria"])
        new_map = _criteria_pass_map(outcome["new_criteria"])
        for name, new_pass in new_map.items():
            old_pass = old_map.get(name)
            if old_pass is None or old_pass == new_pass:
                continue
            bucket = stats["criterion_flips"].setdefault(name, {"F->P": 0, "P->F": 0})
            bucket["F->P" if new_pass else "P->F"] += 1

        if outcome["changed"]:
            stats["runs_changed"] += 1

        # Build the updated result row (used for summary recompute + write).
        new_result = dict(result)
        new_result["criteria"] = outcome["new_criteria"]
        if outcome["new_sub_criteria"] is not None:
            new_result["subagent_criteria"] = outcome["new_sub_criteria"]
        new_result["rescored_at"] = datetime.now(timezone.utc).isoformat()
        new_result["rescore_reason"] = reason
        updated_rows.append(new_result)

        if apply:
            atomic_write_json(run_dir / "result.json", new_result)

    # Recompute + write summary.json from the updated rows.
    summary = load_json(set_dir / "summary.json")
    if summary is not None:
        new_summary = recompute_summary(summary, updated_rows, manifest)
        if apply:
            atomic_write_json(set_dir / "summary.json", new_summary)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-score archived dispatch_compliance result sets under the "
                    "current scorer (heading-normalization correction).",
    )
    parser.add_argument(
        "--results-root", default="benchmarks/results",
        help="Root directory of result sets (default: benchmarks/results).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Report would-change counts without writing (default).",
    )
    group.add_argument(
        "--apply", action="store_true",
        help="Write the rescored result.json / summary.json files.",
    )
    parser.add_argument(
        "--reason", default=RESCORE_REASON,
        help="Provenance reason stamped into each rescored row's "
             f"rescore_reason field (default: {RESCORE_REASON}).",
    )
    args = parser.parse_args()

    # A blank/whitespace-only reason would stamp an empty provenance marker into
    # every rescored row, defeating the auditability the stamp exists for.
    if not args.reason or not args.reason.strip():
        parser.error("--reason must not be blank or whitespace-only")

    apply = bool(args.apply)
    reason = args.reason
    root = Path(args.results_root)
    if not root.is_absolute():
        root = BASE_DIR / root
    if not root.exists():
        print(f"ERROR: results root not found: {root}", file=sys.stderr)
        return 2

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== rescore_archives.py [{mode}] root={root} reason={reason} ===")

    set_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    totals = {
        "sets_dispatch": 0, "sets_skipped": 0,
        "runs_rescored": 0, "runs_changed": 0, "no_golden": 0,
    }
    flip_totals = {}

    for set_dir in set_dirs:
        stats = process_set(set_dir, apply, reason=reason)
        if "skipped" in stats:
            totals["sets_skipped"] += 1
            continue
        totals["sets_dispatch"] += 1
        totals["runs_rescored"] += stats["runs_rescored"]
        totals["runs_changed"] += stats["runs_changed"]
        totals["no_golden"] += stats["no_golden"]
        for name, buckets in stats["criterion_flips"].items():
            agg = flip_totals.setdefault(name, {"F->P": 0, "P->F": 0})
            agg["F->P"] += buckets["F->P"]
            agg["P->F"] += buckets["P->F"]
        if stats["runs_changed"] or stats["no_golden"]:
            print(
                f"  {stats['set']}: rescored={stats['runs_rescored']} "
                f"changed={stats['runs_changed']} no_golden={stats['no_golden']}"
            )

    print("--- Totals ---")
    print(f"  dispatch sets: {totals['sets_dispatch']}  "
          f"(skipped non-dispatch: {totals['sets_skipped']})")
    print(f"  runs rescored: {totals['runs_rescored']}  "
          f"runs changed: {totals['runs_changed']}  "
          f"no-golden skips: {totals['no_golden']}")
    print("  criterion flips (would-change):" if not apply
          else "  criterion flips (applied):")
    for name in sorted(flip_totals):
        b = flip_totals[name]
        if b["F->P"] or b["P->F"]:
            print(f"    {name}: FAIL->PASS={b['F->P']}  PASS->FAIL={b['P->F']}")
    if not apply:
        print("  (dry-run; no files written — re-run with --apply to persist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
