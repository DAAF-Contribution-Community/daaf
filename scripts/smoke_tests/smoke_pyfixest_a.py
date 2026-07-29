# scripts/smoke_tests/smoke_pyfixest.py
# Functional smoke test for pyfixest after the 0.40.0 -> 0.60.0 Dockerfile pin bump.
#
#   Expected versions (post-rebuild target):
#     pyfixest == 0.60.0  (Dockerfile core data-science block)
#
# Background: the pyfixest 0.40.0 wheel declared ZERO runtime dependencies
# (packaging bug — no Requires-Dist in METADATA), so the old pin only worked
# because numba/formulaic/etc. arrived transitively via umap-learn, wildboottest,
# and linearmodels. 0.60.0 declares correct metadata and swaps the etable
# rendering backend from great-tables to maketables; numba is now an optional
# extra (default demeaning reportedly uses a compiled extension in the wheel).
# See research/2026-07-23_FrameworkDev_Pyfixest-Pin-Bump/SESSION_NOTES.md.
#
# What this validates:
#   1. HARD: version == 0.60.0 and non-empty declared dependency metadata
#      (the metadata-sanity check that would have caught the 0.40.0 bug)
#   2. HARD: feols() fit with fixed effects — finite coefficient, finite SE,
#      tidy() returns a well-formed frame
#   3. HARD: fepois() fit runs and returns finite coefficients
#   4. PROBE: etable() render — records the observed output type under the new
#      maketables backend (evidence for the pyfixest skill refresh; API details
#      across 0.41-0.60 not assumed)
#   5. PROBE: ritest() randomization inference — numba is now an optional extra;
#      it is still present transitively (umap-learn/wildboottest), so this
#      records whether the numba-accelerated path works in this image
#
# WHY THIS SCRIPT EXISTS: it is the evidence-generating instrument for the
# pyfixest skill refresh (0.40.0 -> 0.60.0) — the skill cites observed behavior
# recorded here, not online docs alone. HARD sections use bare assert (failure
# crashes the script, exit nonzero) for claims the skill states as fact. PROBE
# sections wrap uncertain 0.60.0 claims in try/except and print the observed
# structure or the full exception; a probe failure must NOT crash the script.
#
# Sequential inline script (DAAF code style): no functions, no classes, no type
# annotations, section separators, print + assert. Seeded synthetic data comes
# from pf.get_data() (deterministic default seed).

# --- Config ---
import importlib.metadata as im
import traceback

import numpy as np
import pyfixest as pf

# INTENT: echo versions of pyfixest and its formerly-shadow dependencies so the
#   appended execution log is auditable against the Dockerfile pins.
# REASONING: the 0.40.0 failure mode was invisible at install time and only
#   detectable via metadata/import — recording the full stack here makes any
#   future drift diagnosable from the log alone.
print("pyfixest :", pf.__version__)
for _pkg in ("numpy", "pandas", "scipy", "formulaic", "narwhals", "joblib",
             "tabulate", "seaborn", "tqdm", "maketables", "numba"):
    try:
        print(f"{_pkg:10s}:", im.version(_pkg))
    except im.PackageNotFoundError:
        print(f"{_pkg:10s}: NOT INSTALLED")

hard_pass = 0
probe_ok = 0
probe_fail = 0

# --- Validate: version and dependency metadata (HARD) ---
# INTENT: pin-assert the exact version and require non-empty declared deps.
# REASONING: requires() returning None/empty is exactly the 0.40.0 packaging bug
#   this bump fixed — asserting non-empty metadata here catches any future
#   broken-metadata wheel at rebuild-validation time.
# ASSUMES: the Dockerfile pin is the single source of the installed version.
assert pf.__version__ == "0.60.0", f"expected 0.60.0, got {pf.__version__}"
_reqs = im.requires("pyfixest")
assert _reqs, "pyfixest declares NO runtime dependencies (0.40.0-style metadata bug)"
_req_names = [r.split(" ")[0].split(">=")[0].split("==")[0] for r in _reqs]
assert any("maketables" in r for r in _req_names), \
    f"maketables missing from declared deps: {_req_names}"
print(f"HARD PASS: version 0.60.0, {len(_reqs)} declared dependency specs (incl. maketables)")
hard_pass += 1

# --- Validate: feols with fixed effects (HARD) ---
# INTENT: fit the canonical single-FE regression on the bundled example data and
#   assert the estimate and SE are finite.
# REASONING: this exercises the demeaning backend (the component that moved off
#   numba), formulaic parsing, and the inference stack in one call.
# ASSUMES: pf.get_data() default seed is deterministic, so the coefficient is
#   stable across runs on the same version.
data = pf.get_data()
fit = pf.feols("Y ~ X1 | f1", data=data)
coef = fit.coef()
se = fit.se()
assert len(coef) == 1 and np.isfinite(coef.iloc[0]), f"bad coef: {coef}"
assert np.isfinite(se.iloc[0]) and se.iloc[0] > 0, f"bad se: {se}"
tidy = fit.tidy()
assert len(tidy) >= 1, "tidy() returned empty frame"
print(f"HARD PASS: feols Y ~ X1 | f1 -> coef={coef.iloc[0]:.6f}, se={se.iloc[0]:.6f}")
hard_pass += 1

# --- Validate: fepois (HARD) ---
# INTENT: confirm the Poisson FE estimator also runs on 0.60.0.
# REASONING: fepois shares the backend but exercises the IRLS path; a bump that
#   silently broke non-OLS estimators would pass the feols check alone.
# ASSUMES: pf.get_data(model="Fepois") provides count-valued Y (NaN-bearing
#   float Y from the default OLS data cannot be cast to int under pandas 3.0
#   strict casting — cause of the v1 script failure).
data_pois = pf.get_data(model="Fepois")
fit_pois = pf.fepois("Y ~ X1 | f1", data=data_pois)
assert np.isfinite(fit_pois.coef().iloc[0]), "fepois coef not finite"
print(f"HARD PASS: fepois -> coef={fit_pois.coef().iloc[0]:.6f}")
hard_pass += 1

# --- Probe: etable under the maketables backend (PROBE) ---
# INTENT: record what etable() returns in 0.60.0 without asserting API details.
# REASONING: the rendering backend changed great-tables -> maketables somewhere
#   in 0.41-0.60; the skill refresh needs the observed output type and a smoke
#   signal that default rendering does not raise.
try:
    tbl = pf.etable([fit])
    print(f"PROBE OK: etable([fit]) -> type={type(tbl).__module__}.{type(tbl).__name__}")
    probe_ok += 1
except Exception:
    print("PROBE FAIL: etable([fit]) raised:")
    traceback.print_exc()
    probe_fail += 1

# --- Probe: ritest randomization inference (PROBE) ---
# INTENT: exercise the path that formerly hard-required numba.
# REASONING: numba is now an optional extra but remains installed transitively
#   (umap-learn, wildboottest) — this records whether ritest works in this image
#   and what it returns, so the skill can state it accurately.
# ASSUMES: small reps keeps runtime trivial; statistical output is not asserted.
try:
    ri = fit.ritest(resampvar="X1", reps=100)
    print(f"PROBE OK: ritest(reps=100) -> type={type(ri).__name__}, repr head: {str(ri)[:200]}")
    probe_ok += 1
except Exception:
    print("PROBE FAIL: ritest raised:")
    traceback.print_exc()
    probe_fail += 1

# --- Summary ---
print("=" * 60)
print(f"HARD PASS {hard_pass}/3 | PROBES: {probe_ok} succeeded, {probe_fail} failed")
print("smoke_pyfixest: COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-23 21:44:45
# Command: python3 /daaf/scripts/smoke_tests/smoke_pyfixest_a.py
# Duration: 11s
# Exit code: 0
#
# --- STDOUT ---
# /usr/local/lib/python3.12/dist-packages/pyfixest/estimation/formula/model_matrix.py:151: UserWarning: 1 singleton fixed effect(s) dropped from the model.
#   warnings.warn(
# pyfixest : 0.60.0
# numpy     : 2.4.2
# pandas    : 3.0.0
# scipy     : 1.17.0
# formulaic : 1.2.2
# narwhals  : 2.24.0
# joblib    : 1.5.3
# tabulate  : 0.10.0
# seaborn   : 0.13.2
# tqdm      : 4.69.0
# maketables: 0.1.8
# numba     : 0.66.0
# HARD PASS: version 0.60.0, 17 declared dependency specs (incl. maketables)
# HARD PASS: feols Y ~ X1 | f1 -> coef=-0.949441, se=0.069627
# HARD PASS: fepois -> coef=0.002262
# PROBE OK: etable([fit]) -> type=great_tables.gt.GT
# PROBE OK: ritest(reps=100) -> type=Series, repr head: H0                                      X1=0
# ri-type                      randomization-c
# Estimate                 -0.9494410591286256
# Pr(>|t|)                                 0.0
# Std. Error (Pr(>|t|)
# ============================================================
# HARD PASS 3/3 | PROBES: 2 succeeded, 0 failed
# smoke_pyfixest: COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
