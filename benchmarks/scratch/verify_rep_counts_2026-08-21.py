# --- Config ---
# INTENT: verify EXACTLY 3 GRADEABLE reps per case per model, for the three
#         newly-onboarded OpenRouter models (qwen-38-27b / "Qwen 3.8 27B",
#         qwen-38-24t-a95b / "Qwen 3.8 2.4T A95B", glm-53 / "GLM 5.3"), across
#         the FULL four-battery case list (mc-01..15, pc-01..09, sr-01..15,
#         dc-01..12 = 51 cases), using the viewer's OWN loading pipeline
#         (discovery skips _quarantine*/probes/removed_runs; load_runs applies
#         the timed_out/stalled/instant-exit-stub "no gradeable signal"
#         chokepoint) so the check matches what the report actually counts as
#         gradeable.
# REASONING: re-deriving validity rules by hand risks divergence from the
#            generator; importing its loader guarantees the verification sees
#            exactly the same gradeable/non-gradeable split the report uses.
#            Pattern and import mechanism copied from the prior hygiene check
#            (scratch/verify_rep_counts_2026-08-12.py) for consistency.
# ASSUMES: generator module is importable from benchmarks/scripts; the corpus
#          convention is 3 gradeable reps per case per model; case coverage is
#          exactly the 51 cases across the four batteries (mc/pc/sr/dc) listed
#          above — any case missing from load_cases() would signal a dataset
#          drift, not a rep-count issue, and is asserted against explicitly.
import sys, collections, importlib.util

spec = importlib.util.spec_from_file_location(
    "gen", "/daaf/benchmarks/scripts/generate_results_viewer_v2.py")
gen = importlib.util.module_from_spec(spec)
sys.modules["gen"] = gen
spec.loader.exec_module(gen)

# --- Load ---
results_dir = "/daaf/benchmarks/results"
datasets_dir = "/daaf/benchmarks/datasets"
base_dir = "/daaf/benchmarks"

TARGET_MODELS = {
    "qwen-38-27b": "Qwen 3.8 27B",
    "qwen-38-24t-a95b": "Qwen 3.8 2.4T A95B",
    "glm-53": "GLM 5.3",
}
name_to_key = {v: k for k, v in TARGET_MODELS.items()}

excl = gen.load_display_exclusions(base_dir)
print("config retired_display_exclusions:", sorted(excl))
# INTENT: flag (not silently apply) any target model caught by the cosmetic
#         leaderboard-quarantine mechanism.
# REASONING: retired_display_exclusions is a report-rendering cosmetic filter
#            (drops a model from the leaderboard/cost/Key-Takeaways surfaces
#            to avoid distorting rankings) — it is a DIFFERENT chokepoint than
#            the "no gradeable signal" timed_out/stalled/instant-exit-stub
#            filter this audit cares about. A run dropped by display-exclusion
#            can still carry a real, gradeable score; treating it as "not
#            gradeable" would conflate two unrelated concepts and could hide
#            a rep-count deficit (or manufacture a fake one) behind a
#            leaderboard-cosmetics decision. This audit therefore computes
#            counts BOTH ways and reports any divergence explicitly rather
#            than picking one silently.
target_excluded = excl & set(TARGET_MODELS.values())
if target_excluded:
    print(f"NOTE: {sorted(target_excluded)} currently IN "
          f"retired_display_exclusions — computing gradeable counts both "
          f"WITH (report-exact) and WITHOUT (raw-gradeable) that cosmetic "
          f"filter applied, since it is orthogonal to rep-count gradeability.")

sets_ = gen.load_result_sets(results_dir)
cases = gen.load_cases(datasets_dir)

# ASSUMES: load_runs returns the 3-tuple (runs, anth_token_totals,
#          n_timed_out_excluded) per its docstring.
runs_report, _tok1, n_to1 = gen.load_runs(
    results_dir, sets_, cases, display_exclusions=excl)
runs_raw, _tok2, n_to2 = gen.load_runs(
    results_dir, sets_, cases, display_exclusions=set())
print("loaded runs (report-exact, display exclusions applied):", len(runs_report),
      "| timed-out/stalled/stub excluded:", n_to1)
print("loaded runs (raw-gradeable, display exclusions NOT applied):", len(runs_raw),
      "| timed-out/stalled/stub excluded:", n_to2)

# --- Profile ---
# INTENT: build the full expected case-id universe for the four batteries so
#         a case with ZERO gradeable runs for a model (not just a short count)
#         is caught, not only cells that already have >=1 run.
# REASONING: counting only (model, case) pairs observed in `runs` would miss a
#            case that never landed a single gradeable run for a model.
BATTERY_COUNTS = {
    "mode_classification": ("mc", 15),
    "post_confirmation": ("pc", 9),
    "skill_routing": ("sr", 15),
    "dispatch_compliance": ("dc", 12),
}
expected_cases = []
for _battery, (prefix, n) in BATTERY_COUNTS.items():
    for i in range(1, n + 1):
        expected_cases.append(f"{prefix}-{i:02d}")
expected_cases = sorted(expected_cases)
print(f"\nexpected case universe: {len(expected_cases)} cases "
      f"(mc:15 + pc:9 + sr:15 + dc:12 = 51)")

# ASSUMES: load_cases() key set matches this expected universe exactly; any
#          mismatch is a dataset-drift signal worth surfacing, not silence.
cases_loaded = sorted(cases.keys())
missing_from_loader = sorted(set(expected_cases) - set(cases_loaded))
extra_in_loader = sorted(set(cases_loaded) - set(expected_cases))
if missing_from_loader:
    print(f"WARNING: cases expected but NOT in load_cases(): {missing_from_loader}")
if extra_in_loader:
    print(f"NOTE: load_cases() has cases outside the expected 51-case battery "
          f"list (other batteries in the corpus, expected): "
          f"{len(extra_in_loader)} extra")


def count_by_case(runs, target_names):
    # INTENT: tally gradeable reps per (model, case) restricted to the three
    #         target models.
    # REASONING: mirrors the prior script's Counter approach; scoped down to
    #            target_names so output stays readable.
    counts = collections.Counter()
    for r in runs:
        model = r.get("model") if isinstance(r, dict) else getattr(r, "model", None)
        if model not in target_names:
            continue
        case = r.get("case_id") if isinstance(r, dict) else getattr(r, "case_id", None)
        counts[(model, case)] += 1
    return counts


target_names = set(TARGET_MODELS.values())
counts_report = count_by_case(runs_report, target_names)
counts_raw = count_by_case(runs_raw, target_names)

# --- Validate ---
# INTENT: for each target model x expected case, report gradeable count,
#         deficit (3 - n, floored at 0), and surplus flag (n > 3) — using the
#         RAW (display-exclusion-agnostic) counts as the authoritative
#         "gradeable" signal per the REASONING above, with the report-exact
#         counts shown alongside for transparency where they diverge.
print()
print("=" * 100)
print("PER-MODEL, PER-CASE GRADEABLE REP COUNTS (raw-gradeable = authoritative; "
      "report-exact shown when it diverges)")
print("=" * 100)

all_deviations = {}  # model_key -> list of (case, raw_n, deficit, surplus, report_n_if_diff)
for model_key, model_name in TARGET_MODELS.items():
    print(f"\n--- {model_key}  (\"{model_name}\") ---")
    deviations = []
    for case in expected_cases:
        n_raw = counts_raw.get((model_name, case), 0)
        n_report = counts_report.get((model_name, case), 0)
        deficit = max(0, 3 - n_raw)
        surplus = n_raw > 3
        if n_raw != 3:
            diverge_note = ""
            if n_report != n_raw:
                diverge_note = f"  [report-exact count differs: {n_report}]"
            deviations.append((case, n_raw, deficit, surplus, n_report))
            flag = "SURPLUS" if surplus else "DEFICIT"
            print(f"  {case:6s} gradeable={n_raw}  deficit={deficit}  "
                  f"{'surplus' if surplus else '      '}{diverge_note}")
    if not deviations:
        print("  (none — every case == 3 gradeable reps)")
    all_deviations[model_key] = deviations

# --- Summary ---
print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"models checked: {len(TARGET_MODELS)} | cases per model: {len(expected_cases)} "
      f"| total cells: {len(TARGET_MODELS) * len(expected_cases)}")

any_deviation = any(all_deviations[k] for k in all_deviations)
if not any_deviation:
    print("VERIFIED: exactly 3 gradeable reps for every case, every target model.")
else:
    print("DEVIATIONS FOUND (see per-model lists above). Exact re-run list:")
    for model_key, deviations in all_deviations.items():
        for case, n_raw, deficit, surplus, n_report in deviations:
            if deficit > 0:
                print(f"  RE-RUN: model={model_key}  case={case}  reps_needed={deficit}")
            if surplus:
                print(f"  SURPLUS (no action / maintainer adjudication): "
                      f"model={model_key}  case={case}  gradeable_n={n_raw}")

# Explicit confirmation of exhaustiveness: every non-listed cell is exactly 3.
print()
non_deviating_cells = (len(TARGET_MODELS) * len(expected_cases)) - sum(
    len(v) for v in all_deviations.values())
print(f"non-deviating cells (== 3 gradeable reps): {non_deviating_cells} / "
      f"{len(TARGET_MODELS) * len(expected_cases)}")
print("Deviation list above is EXHAUSTIVE over the full 51-case x 3-model grid "
      "(every cell was checked against the expected battery case universe, "
      "not just cells with >=1 observed run).")
