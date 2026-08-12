# --- Config ---
# INTENT: verify EXACTLY 3 complete (graded) reps per case per model across
#         the entire display corpus, using the viewer's OWN loading pipeline
#         (discovery skips _quarantine*/probes/removed_runs; load_runs applies
#         validity + model-level display exclusions) so the check matches what
#         the report actually aggregates.
# REASONING: re-deriving validity rules by hand risks divergence; importing
#            the generator's loader guarantees the verification sees exactly
#            what the report sees.
# ASSUMES: generator module is importable from benchmarks/scripts; the corpus
#          convention is 3 reps per case per model for every ACTIVE display
#          model.
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
excl = gen.load_display_exclusions(base_dir)
print("display exclusions:", sorted(excl))
sets_ = gen.load_result_sets(results_dir)
cases = gen.load_cases(datasets_dir)
# ASSUMES: load_runs returns the 3-tuple (runs, anth_token_totals,
#          n_timed_out_excluded) per its docstring (verified at line 1410).
runs, _tok, n_to = gen.load_runs(results_dir, sets_, cases, display_exclusions=excl)
print("loaded runs:", len(runs), "| timed-out excluded:", n_to)

# --- Profile ---
counts = collections.Counter()
for r in runs:
    model = r.get("model") if isinstance(r, dict) else getattr(r, "model", None)
    case = r.get("case_id") if isinstance(r, dict) else getattr(r, "case_id", None)
    counts[(model, case)] += 1

models = sorted({m for m, _ in counts})
cases_seen = sorted({c for _, c in counts})

# --- Validate ---
deviations = []
for m in models:
    for c in cases_seen:
        n = counts.get((m, c), 0)
        if n != 3:
            deviations.append((m, c, n))

# INTENT: distinguish "case not run for model" (structural, e.g. a case
#         retired before a model was onboarded) from over/under-rep counts.
# REASONING: a 0 count for every model of a case would mean the case is not
#            part of the corpus contract; report all deviations verbatim and
#            let the maintainer adjudicate.
print()
print(f"models: {len(models)} | cases: {len(cases_seen)} | cells: {len(models)*len(cases_seen)}")
print(f"deviating cells (n != 3): {len(deviations)}")
for m, c, n in sorted(deviations):
    print(f"  {m:40s} {c:8s} n={n}")

# --- Summary ---
if not deviations:
    print()
    print("VERIFIED: exactly 3 complete reps for every case on every model.")
else:
    print()
    print("DEVIATIONS FOUND — see list above.")
