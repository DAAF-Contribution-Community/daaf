"""build_rerun_queue.py — read-only scanner emitting the DAAFBench re-run queue.

Scans benchmarks/results/*/runs/*/result.json (excluding _quarantine* result
sets, the top-level probes/ dir, and removed_runs/ provenance sidecars), tallies
every timed-out run AND every permanently-stalled run (status == "stalled" — a
watchdog-killed hang that exhausted auto-relaunch; § 3), and emits an ordered
re-run queue: models sorted by descending timeout rate, with one ready-to-run
command per failing (model, battery, case). Each command's --reps is the number
of censored reps for that (model, battery, case) across the corpus — timed-out
plus stalled — i.e. the number of fresh completions needed to replace them. The
two failure classes are counted separately in the report and JSON output
(``timed_out``/``stalled`` per model, ``timed_out_reps``/``stalled_reps`` per
queue entry) so they stay distinguishable; recovery semantics are identical (both
produced no usable completion and are eligible for rerun).

Backburnered models (default: Gemma 4 31B, Gemma 4 26B, GPT-5.6 Luna
(ChatGPT Subscription)) are listed in a separate deferred section, not the
active queue.

No cases are excluded by default (maintainer decision 2026-08-12: the
data-ingest dispatch cases dc-11/dc-12 are VALID and retained — this
supersedes the 2026-07-18 static criteria audit's NEEDS REWORK ruling and
the G1R-era default exclusion). --exclude-cases remains available for ad hoc
scoping; excluded cases' timed-out reps still count in the corpus baseline
tally (the scan reports ground truth) and are omitted only from the emitted
commands, with an explicit exclusion line in the summary.

This tool is READ-ONLY: it opens result.json files and models.yaml and writes
nothing under benchmarks/results/. The only write path is the optional --out
JSON dump for downstream tooling.

Self-check: pre-campaign totals should be 401 timed-out across 3187 runs.
Per-model timeout counts should match the corpus-enumeration note
(Gemma 4 31B 70, Kimi K3 41, DeepSeek V4 Pro 41, Nemotron 3 Ultra 37, ...).

Usage:
    python3 benchmarks/scripts/build_rerun_queue.py
    python3 benchmarks/scripts/build_rerun_queue.py --out /daaf/.../scratch/queue.json
    python3 benchmarks/scripts/build_rerun_queue.py --backburner "Gemma 4 31B,Gemma 4 26B"
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

# --- Config ---
# INTENT: anchor all paths on the repo root two levels up from this script
#         (benchmarks/scripts/build_rerun_queue.py -> /daaf).
# ASSUMES: this file lives at {BASE_DIR}/benchmarks/scripts/.
BASE_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = BASE_DIR / "benchmarks" / "results"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

# Uniform logistical cap emitted in every re-run command (2026-07-21 walltime
# redesign). Kept in lockstep with the runners' argparse default and
# executor.DEFAULT_TIMEOUT_S.
RERUN_TIMEOUT_S = 900

# Case-id prefix -> (battery label, runner script). The prefix is the reliable
# battery discriminant and is present on every schema version (case_id is
# populated in 3187/3187 corpus runs; benchmark_key is not, so we do not rely
# on it).
BATTERY_BY_PREFIX = {
    "dc": ("dispatch_compliance", "run_dispatch_compliance.py"),
    "pc": ("post_confirmation", "run_post_confirmation.py"),
    "sr": ("skill_routing", "run_skill_routing.py"),
    "mc": ("mode_classification", "run_mode_classification.py"),
}

# Expected pre-campaign baseline (from the 2026-07-21 corpus-enumeration note).
EXPECTED_TOTAL_RUNS = 3187
EXPECTED_TIMED_OUT = 401

DEFAULT_BACKBURNER = "Gemma 4 31B,Gemma 4 26B,GPT-5.6 Luna (ChatGPT Subscription)"

# No default exclusions (maintainer decision 2026-08-12): dc-11/dc-12 are
# valid, retained cases — this supersedes the 2026-07-18 static audit's
# NEEDS REWORK ruling that previously excluded them here by default. Use
# --exclude-cases for ad hoc scoping only.
DEFAULT_EXCLUDED_CASES = ""

parser = argparse.ArgumentParser(
    description="Emit the DAAFBench timed-out re-run queue (read-only scanner). "
                "Pre-campaign baseline self-check: 401 timed-out / 3187 runs.")
parser.add_argument("--backburner", type=str, default=DEFAULT_BACKBURNER,
                    help="Comma-separated model DISPLAY names to defer to a "
                         "separate deferred section instead of the active queue "
                         f"(default: {DEFAULT_BACKBURNER!r}).")
parser.add_argument("--exclude-cases", type=str, default=DEFAULT_EXCLUDED_CASES,
                    help="Comma-separated case ids to EXCLUDE from the emitted "
                         "queue (still counted in the baseline tally). Default: "
                         "none — dc-11/dc-12 are valid, retained cases per the "
                         "2026-08-12 maintainer decision, superseding the "
                         "2026-07-18 audit's default exclusion.")
parser.add_argument("--out", type=str, default=None,
                    help="Optional path to write the queue as JSON for tooling. "
                         "This is the only write path; the scan is read-only.")
args = parser.parse_args()

backburner_names = [n.strip() for n in args.backburner.split(",") if n.strip()]
excluded_cases = {c.strip() for c in args.exclude_cases.split(",") if c.strip()}

# --- Load ---
# INTENT: build a model DISPLAY-name -> selectable runner key map and a registry
#         order index, mirroring model_loader.load_models():
#         key = entry.get("key") or name.lower().replace(" ","-").replace(".","")
# REASONING: 2952/3187 corpus result.json files predate schema_version 2 and
#            carry no benchmark_key, so the registry (models.yaml) is the only
#            corpus-wide source for the --models key.
with open(MODELS_FILE) as fh:
    _registry = yaml.safe_load(fh)

name_to_key = {}
name_to_registry_index = {}
for _idx, _entry in enumerate(_registry.get("models", [])):
    _name = _entry.get("name")
    if _name is None:
        continue
    _derived = _name.lower().replace(" ", "-").replace(".", "")
    name_to_key[_name] = _entry.get("key") or _derived
    # First occurrence wins for the ordering index (registry declaration order).
    if _name not in name_to_registry_index:
        name_to_registry_index[_name] = _idx

# INTENT: enumerate every corpus result.json under a result set's runs/ subtree.
# ASSUMES: removed_runs/ is a SIBLING of runs/ (not under it), probes/ is a
#          top-level results/ dir, and _quarantine* is a result-set-level dir —
#          so the */runs/* glob plus the explicit exclusions reproduce the
#          viewer's runs/-only scope (verified: 3187 files).
result_files = [
    p for p in RESULTS_DIR.glob("*/runs/*/result.json")
    if "_quarantine" not in str(p)
    and "/removed_runs/" not in str(p)
    and "/probes/" not in str(p)
]

# --- Scan ---
total_by_model = Counter()
timed_by_model = Counter()
# Permanently-stalled runs (status == "stalled") — the watchdog killed a hung run
# after exhausting auto-relaunch (§ 3). Recovery semantics are equivalent to a
# timeout (the run produced no usable completion and is eligible for rerun), so
# these are ALSO selected for the queue, but tracked in a SEPARATE counter so the
# two failure classes stay distinguishable in the report and JSON output.
stalled_by_model = Counter()
# (model_name, battery, runner, case_id) -> rep counts needed, split by failure
# class. reps_needed for a triple is the SUM (each censored run needs one fresh
# completion regardless of which class censored it).
timed_rerun_counts = defaultdict(int)
stalled_rerun_counts = defaultdict(int)
unknown_names = set()
skipped_unmapped_case = 0
# case_id -> reps (either class) omitted from the queue via --exclude-cases.
excluded_case_reps = Counter()

for path in result_files:
    with open(path) as fh:
        rec = json.load(fh)
    model_name = rec.get("model") or rec.get("model_name")
    case_id = rec.get("case_id") or rec.get("test_case_id")
    total_by_model[model_name] += 1
    is_timed_out = bool(rec.get("timed_out"))
    # status == "stalled" is mutually exclusive with the timed_out flag
    # (artifacts._run_status returns "stalled" before the timed_out branch).
    is_stalled = rec.get("status") == "stalled"
    if not (is_timed_out or is_stalled):
        continue
    if is_timed_out:
        timed_by_model[model_name] += 1
    if is_stalled:
        stalled_by_model[model_name] += 1
    # Map case-id prefix -> battery/runner.
    prefix = (case_id or "")[:2]
    battery_runner = BATTERY_BY_PREFIX.get(prefix)
    if battery_runner is None:
        skipped_unmapped_case += 1
        continue
    battery, runner = battery_runner
    # INTENT: keep --exclude-cases cases out of the emitted queue while the
    #         baseline tally above stays raw (scan reports ground truth).
    if case_id in excluded_cases:
        excluded_case_reps[case_id] += 1
        continue
    if is_timed_out:
        timed_rerun_counts[(model_name, battery, runner, case_id)] += 1
    if is_stalled:
        stalled_rerun_counts[(model_name, battery, runner, case_id)] += 1

# --- Build ordering ---
# INTENT: rank models with >=1 timeout by descending timeout RATE (per the
#         user's "descending timeout rate" campaign spec), breaking ties by
#         descending absolute timeout count, then registry declaration order
#         (which yields Kimi K3 before DeepSeek V4 Pro on their 41/41 tie).
# Any model with >=1 timeout OR >=1 stall needs rerun work. Stalled-only models
# (timeout rate 0) sort after timed-out models but still get emitted.
models_needing_rerun = [
    m for m in (set(timed_by_model) | set(stalled_by_model))
    if timed_by_model[m] > 0 or stalled_by_model[m] > 0
]


def _rate(m):
    total = total_by_model[m]
    return (timed_by_model[m] / total) if total else 0.0


def _sort_key(m):
    # Primary ordering stays timeout-rate descending (the campaign spec); stalled
    # count is a tertiary tiebreak so stalled-only models order deterministically.
    return (
        -_rate(m), -timed_by_model[m], -stalled_by_model[m],
        name_to_registry_index.get(m, 10_000), m,
    )


ranked = sorted(models_needing_rerun, key=_sort_key)
active_models = [m for m in ranked if m not in backburner_names]
deferred_models = [m for m in ranked if m in backburner_names]

# INTENT: assemble the per-model command lists once, reused for stdout + JSON.
queue = {}  # model_name -> list of entry dicts
for m in ranked:
    key = name_to_key.get(m)
    if key is None:
        unknown_names.add(m)
        key = m.lower().replace(" ", "-").replace(".", "")  # best-effort fallback
    entries = []
    # Case triples for this model (union of both failure classes), sorted by
    # battery then case_id for stable output. reps_needed = timed + stalled.
    triple_keys = {
        (b, r, c)
        for (mm, b, r, c) in set(timed_rerun_counts) | set(stalled_rerun_counts)
        if mm == m
    }
    triples = sorted(triple_keys, key=lambda t: (t[0], t[2]))
    for battery, runner, case_id in triples:
        timed_reps = timed_rerun_counts[(m, battery, runner, case_id)]
        stalled_reps = stalled_rerun_counts[(m, battery, runner, case_id)]
        reps = timed_reps + stalled_reps
        cmd = (f"python3 benchmarks/scripts/{runner} "
               f"--models {key} --test-id {case_id} --reps {reps} "
               f"--timeout {RERUN_TIMEOUT_S} --sequential")
        entries.append({
            "battery": battery,
            "case_id": case_id,
            "reps_needed": reps,
            "timed_out_reps": timed_reps,
            "stalled_reps": stalled_reps,
            "runner": runner,
            "command": cmd,
        })
    queue[m] = entries

# --- Summary (stdout) ---
grand_total_runs = sum(total_by_model.values())
grand_timed_out = sum(timed_by_model.values())
grand_stalled = sum(stalled_by_model.values())

print("=" * 78)
print("DAAFBench re-run queue (timed-out + permanently-stalled runs)")
print("=" * 78)
print(f"Corpus scanned : {RESULTS_DIR}")
print(f"Result files   : {grand_total_runs} runs "
      f"(runs/ scope; excludes _quarantine*, probes/, removed_runs/)")
print(f"Timed-out runs : {grand_timed_out}")
print(f"Stalled runs   : {grand_stalled} (status==\"stalled\"; watchdog-killed "
      f"hangs, distinct from timeouts — also queued for rerun)")
_baseline_match = (grand_total_runs == EXPECTED_TOTAL_RUNS
                   and grand_timed_out == EXPECTED_TIMED_OUT)
print(f"Self-check     : expected pre-campaign baseline "
      f"{EXPECTED_TIMED_OUT} timed-out / {EXPECTED_TOTAL_RUNS} runs -> "
      f"{'MATCH' if _baseline_match else 'DIFFERS (campaign in progress or scope drift)'}")
if excluded_case_reps:
    _excl_detail = ", ".join(f"{c} ({n})" for c, n in sorted(excluded_case_reps.items()))
    print(f"Excluded cases : {sum(excluded_case_reps.values())} timed-out rep(s) "
          f"omitted from the queue per --exclude-cases: {_excl_detail}")
if skipped_unmapped_case:
    print(f"WARNING        : {skipped_unmapped_case} timed-out run(s) had an "
          f"unmapped case-id prefix and were omitted from the queue")
if unknown_names:
    print(f"WARNING        : model name(s) not in models.yaml (fallback key "
          f"derived): {sorted(unknown_names)}")
print()

print("Per-model failure tally (all models needing rerun, descending timeout rate):")
print(f"  {'model':<40} {'timed':>6} {'stall':>6} {'total':>6} {'rate':>7}  section")
for m in ranked:
    section = "DEFERRED" if m in backburner_names else "active"
    print(f"  {m:<40} {timed_by_model[m]:>6} {stalled_by_model[m]:>6} "
          f"{total_by_model[m]:>6} {_rate(m) * 100:>6.1f}%  {section}")
print()

print("-" * 78)
print(f"ACTIVE QUEUE ({len(active_models)} models, "
      f"descending timeout rate; --timeout {RERUN_TIMEOUT_S})")
print("-" * 78)
for rank, m in enumerate(active_models, start=1):
    entries = queue[m]
    reps_sum = sum(e["reps_needed"] for e in entries)
    print(f"\n[{rank}] {m}  (key: {name_to_key.get(m, '?')}) — "
          f"{timed_by_model[m]} timed-out + {stalled_by_model[m]} stalled / "
          f"{total_by_model[m]} runs ({_rate(m) * 100:.1f}% timeout), "
          f"{len(entries)} case(s), {reps_sum} rep(s) to re-run")
    if not entries:
        print("    (all failed reps are excluded cases — nothing to re-run)")
    for e in entries:
        print(f"    {e['command']}")

print()
print("-" * 78)
print(f"DEFERRED (backburnered models — NOT in active queue): "
      f"{', '.join(backburner_names) if backburner_names else '(none)'}")
print("-" * 78)
for m in deferred_models:
    entries = queue[m]
    reps_sum = sum(e["reps_needed"] for e in entries)
    print(f"\n[deferred] {m}  (key: {name_to_key.get(m, '?')}) — "
          f"{timed_by_model[m]} timed-out + {stalled_by_model[m]} stalled / "
          f"{total_by_model[m]} runs ({_rate(m) * 100:.1f}% timeout), "
          f"{len(entries)} case(s), {reps_sum} rep(s) to re-run")
    if not entries:
        print("    (all failed reps are excluded cases — nothing to re-run)")
    for e in entries:
        print(f"    {e['command']}")

# --- Optional JSON out ---
if args.out:
    out_payload = {
        "corpus_dir": str(RESULTS_DIR),
        "total_runs": grand_total_runs,
        "timed_out": grand_timed_out,
        "stalled": grand_stalled,
        "baseline_expected": {"total_runs": EXPECTED_TOTAL_RUNS,
                              "timed_out": EXPECTED_TIMED_OUT},
        "baseline_match": _baseline_match,
        "rerun_timeout_s": RERUN_TIMEOUT_S,
        "backburner": backburner_names,
        "excluded_cases": sorted(excluded_cases),
        "excluded_case_reps": dict(sorted(excluded_case_reps.items())),
        "active_order": active_models,
        "deferred_order": deferred_models,
        "models": {
            m: {
                "timed_out": timed_by_model[m],
                "stalled": stalled_by_model[m],
                "total": total_by_model[m],
                "rate": _rate(m),
                "key": name_to_key.get(m),
                "section": "deferred" if m in backburner_names else "active",
                "entries": queue[m],
            }
            for m in ranked
        },
    }
    out_path = Path(args.out)
    with open(out_path, "w") as fh:
        json.dump(out_payload, fh, indent=2)
    print(f"\nWrote JSON queue to {out_path}")
