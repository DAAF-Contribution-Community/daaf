# scripts/smoke_tests/smoke_svy.py
# Functional smoke test for the Python `svy` complex-survey stack.
#
#   Expected versions (post-rebuild target):
#     svy    == 0.19.0   (pure-Python survey API: Design, Sample, estimation, glm, weighting)
#     svy-rs == 0.10.0   (compiled Rust kernels: Taylor variance, replicate wgts, GLM fit)
#     svy-io == 0.1.1     (ReadStat-backed SAS/SPSS/Stata I/O, returns Polars frames)
#   Effective polars floor: >= 1.39.1 (driven by svy-rs, stricter than svy's own >=1.33.1)
#
# What this validates (the 8 researched 0.19.0 priorities, in order):
#   1. Taylor mean/total on a stratified-clustered design (closed-form correctness anchor
#      + positive/finite SEs + deterministic-variance check across two runs)
#   2. Batched multi-variable prop()/ratio()/median() (new in 0.19.0)
#   3. Domain estimation: by= / where= / same-column-in-both (issue #9 fix)
#   4. Logistic GLM (family="binomial") -- coef-table structure, finite SEs, plausible sign
#      (p-values NOT asserted -- open upstream issue #5)
#   5. Poisson + Gamma GLM (documented, NO doc examples -> PROBE)
#   6. model.margins() (documented, no correctness claim vs R -> PROBE)
#   7. svy-io .dta round-trip (import path + writer/reader names discovered defensively -> PROBE)
#   8. Replicate weights: bootstrap + jackknife creation, replication-variance determinism
#   Bonus probe: polars 1.39.x replace_strict-on-Enum regression (issue #27060) -- informational
#
# WHY THIS SCRIPT EXISTS: the svy skill revision (Stage B) is grounded on the observed
# behavior recorded here, NOT on the library's online docs -- those docs are known to be
# partly aspirational ("Not all advanced features may be fully supported yet"). This script
# is the evidence-generating instrument. It will be read as an audit artifact when the skill
# cites it, so every non-obvious construction carries INTENT/REASONING/ASSUMES comments.
#
# Sequential inline script (DAAF code style): no functions, no classes, no type
# annotations, section separators, print + assert for validation. Polars for all data
# handling (never pandas). Synthetic data seeded for reproducibility.
#
# HARD vs PROBE sections:
#   - HARD sections use bare assert -- a failure crashes the script (exit nonzero). These
#     encode claims the skill will state as FACT.
#   - PROBE sections wrap uncertain 0.19.0 claims in try/except, print the observed result
#     structure on success or the full exception type+message on failure, and are counted
#     separately. A probe failure must NOT crash the script -- probes generate the evidence
#     that decides whether an uncertain claim gets encoded, hedged, or omitted from the skill.
# The closing summary distinguishes `HARD PASS n/n` from `PROBES: m succeeded, k failed`.
#
# DO NOT execute against svy 0.13.0 (the currently-installed version) -- the appended
# execution log would record failures against the wrong version and pollute this artifact.
# Execution happens post-rebuild against 0.19.0 in a later session.

# --- Config ---
import os
import shutil
import sys
import traceback

import numpy as np
import polars as pl
import svy

# INTENT: echo the version of every package in the stack so the appended execution log is
#   version-visible and auditable against the Dockerfile pins.
# REASONING: a smoke result that does not name the build it tested cannot ground a skill
#   revision. svy-rs is internal ("do not depend on this directly") and svy-io's import path
#   is not fully confirmed, so both are reported defensively rather than asserted here.
print("=== svy (Python complex-survey) Smoke Test ===\n")
print(f"  svy version:    {svy.__version__}")
print(f"  polars version: {pl.__version__}")
print(f"  numpy version:  {np.__version__}")

# svy-rs / svy-io versions: reported best-effort (internal / uncertain-import packages).
try:
    import importlib.metadata as _md

    for _pkg in ("svy-rs", "svy-io", "polars"):
        try:
            print(f"  {_pkg} dist version: {_md.version(_pkg)}")
        except Exception as _e:  # noqa: BLE001 -- best-effort dist-version report only
            print(f"  {_pkg} dist version: unavailable ({_e!r})")
except Exception as _e:  # noqa: BLE001
    print(f"  importlib.metadata unavailable: {_e!r}")

# INTENT: assert the installed svy is at least 0.19 before running any 0.19-specific test.
# REASONING: this script targets the 0.19.0 API (batched prop/ratio/median, deterministic
#   Taylor variance, issue-#9 by=/where= overlap). Running it against 0.13.0 would produce
#   misleading failures. Parse major.minor as integers to avoid string-compare pitfalls
#   ("0.9" > "0.19" lexically). ASSUMES __version__ is a dotted numeric string.
_ver_parts = svy.__version__.split(".")
_major = int(_ver_parts[0])
_minor = int(_ver_parts[1]) if len(_ver_parts) > 1 else 0
assert (_major, _minor) >= (0, 19), (
    f"smoke_svy.py targets svy>=0.19.0 but found {svy.__version__}; "
    "run only after the container rebuild that installs svy 0.19.0"
)
print(f"  version gate OK: svy {svy.__version__} >= 0.19\n")

# Deterministic RNG for reproducible synthetic data.
rng = np.random.default_rng(42)

# Probe accounting: hard sections increment on PASS; probes track success/failure separately.
hard_pass = 0
hard_total = 0
probe_success = 0
probe_fail = 0

# --- Synthetic stratified-clustered survey dataset ---
# INTENT: build a stratified, two-stage-clustered survey frame in polars with a continuous,
#   binary, and count outcome, a categorical, unequal weights, and FPC-suitable structure.
# REASONING: mirrors smoke_survey_r.R's synthetic design so results are comparable across the
#   R/Python survey pair. Sized (~4 strata x 6 PSUs x 20 obs = 480 rows) so estimates are
#   stable but the script runs in seconds. Weights are unequal (drawn uniformly) so weighted
#   estimators differ from unweighted ones -- otherwise the correctness anchor is trivial.
# ASSUMES: svy.Design accepts stratum/psu/wgt/fpc column-name references (0.19.0 doc surface).
n_strata = 4
n_psu_per_stratum = 6
n_obs_per_psu = 20
n = n_strata * n_psu_per_stratum * n_obs_per_psu  # 480

stratum = np.repeat(np.arange(1, n_strata + 1), n_psu_per_stratum * n_obs_per_psu)
# PSU ids are unique across the whole frame (nested design: PSU implies stratum). This is the
# safe convention -- it avoids the "same PSU id in two strata" ambiguity that needs nest=TRUE
# in R's svydesign.
psu = np.repeat(np.arange(1, n_strata * n_psu_per_stratum + 1), n_obs_per_psu)

# Unequal weights in [0.5, 5.0]: makes weighted != unweighted so the closed-form check bites.
weight = rng.uniform(0.5, 5.0, size=n)

# Continuous outcome with a stratum-level shift so domain estimates differ across groups.
income = 30000.0 + 500.0 * stratum + rng.normal(0.0, 5000.0, size=n)

age = rng.integers(18, 81, size=n).astype(float)
gender = rng.choice(["Male", "Female"], size=n)

# Binary outcome with a KNOWN positive relationship to age: the logistic-GLM section asserts a
# positive sign on the age coefficient. logistic link on a linear predictor of age.
_p_employed = 1.0 / (1.0 + np.exp(-(-1.0 + 0.02 * age + 0.5 * (gender == "Male"))))
employed = rng.binomial(1, _p_employed).astype(float)

# Count outcome for the Poisson/Gamma GLM probes.
visit_count = rng.poisson(np.exp(0.5 + 0.01 * age / 10.0)).astype(float)

# FPC column: a plausible population size per stratum, constant within stratum, larger than the
# realized sample so the finite-population correction is a valid (0,1) factor.
fpc_pop = np.select(
    [stratum == 1, stratum == 2, stratum == 3, stratum == 4],
    [5000.0, 6000.0, 7000.0, 8000.0],
)

df = pl.DataFrame(
    {
        "stratum": stratum,
        "psu": psu,
        "weight": weight,
        "income": income,
        "age": age,
        "gender": gender,
        "employed": employed,
        "visit_count": visit_count,
        "fpc_pop": fpc_pop,
    }
)
assert df.height == n, f"expected {n} rows, built {df.height}"
print(f"Synthetic survey frame: {df.height} rows, {df.width} cols, "
      f"{n_strata} strata x {n_psu_per_stratum} PSUs x {n_obs_per_psu} obs\n")

# Working directory for the svy-io round-trip temp file: inside the repo per CLAUDE.md scratch
# conventions (NEVER /tmp -- outside the backup/audit boundary). Created here, deleted in the
# svy-io section's finally-arm.
SCRATCH_DIR = "/daaf/scripts/scratch/smoke_svy_io"

# =============================================================================
# HARD SECTIONS -- claims the skill will state as fact; assert failures crash.
# =============================================================================

# --- Test 1 (HARD): Taylor mean/total on the stratified-clustered design ---
# INTENT: confirm svy's Taylor point estimates match independently-computed weighted values
#   to floating tolerance, assert SEs are positive/finite, and verify variance determinism.
# REASONING: the weighted mean and total have closed forms -- sum(w*y)/sum(w) and sum(w*y) --
#   independent of the variance machinery. This is the strongest correctness anchor available
#   without a second survey library. Determinism (run twice, bitwise-equal) tests the 0.19.0
#   claim that Taylor variance was made deterministic (PSU sort + std HashSet dropped in svy-rs).
# ASSUMES: svy.Sample(df, design=) with .estimation.mean/.total; results expose .to_polars();
#   the estimate column can be located by name or position in that frame.
hard_total += 1
print("Test 1 (HARD): Taylor mean/total on stratified-clustered design")

design = svy.Design(wgt="weight", stratum="stratum", psu="psu", fpc="fpc_pop")
sample = svy.Sample(df, design=design)

# Independently-computed weighted reference values via polars.
_ref = df.select(
    (pl.col("weight") * pl.col("income")).sum().alias("wy"),
    pl.col("weight").sum().alias("w"),
)
ref_wy = _ref.item(0, "wy")
ref_w = _ref.item(0, "w")
ref_mean = ref_wy / ref_w
ref_total = ref_wy

mean_res = sample.estimation.mean(y="income")
total_res = sample.estimation.total(y="income")
mean_pl = mean_res.to_polars()
total_pl = total_res.to_polars()
print(f"  mean result columns:  {mean_pl.columns}")
print(f"  total result columns: {total_pl.columns}")

# INTENT: locate the point-estimate and SE columns robustly across possible column namings.
# REASONING: the exact result-frame schema for 0.19.0 is not fully confirmed from docs. Prefer
#   named columns ("estimate"/"mean"/"total", "se"/"stderr") but fall back to positional so a
#   naming difference degrades to a clear assertion message rather than a KeyError.
# ASSUMES: the estimate lives in the first numeric-looking column if not found by name.
def_est_names = ("estimate", "mean", "total", "value", "point_estimate")
def_se_names = ("se", "stderr", "std_error", "standard_error")

_mean_est_col = next((c for c in mean_pl.columns if c.lower() in def_est_names), None)
_total_est_col = next((c for c in total_pl.columns if c.lower() in def_est_names), None)
assert _mean_est_col is not None, f"no estimate column found in mean result: {mean_pl.columns}"
assert _total_est_col is not None, f"no estimate column found in total result: {total_pl.columns}"

svy_mean = float(mean_pl.item(0, _mean_est_col))
svy_total = float(total_pl.item(0, _total_est_col))

# Closed-form correctness: svy's estimate must equal the polars-computed weighted value.
assert abs(svy_mean - ref_mean) < 1e-9, (
    f"Taylor mean {svy_mean} != closed-form weighted mean {ref_mean} "
    f"(diff {abs(svy_mean - ref_mean):.3e})"
)
assert abs(svy_total - ref_total) < 1e-3 * max(1.0, abs(ref_total)), (
    f"Taylor total {svy_total} != closed-form weighted total {ref_total}"
)
print(f"  mean: svy={svy_mean:.6f}  closed-form={ref_mean:.6f}  (match < 1e-9)")
print(f"  total: svy={svy_total:.2f}  closed-form={ref_total:.2f}")

# SEs must be present, positive, and finite.
_mean_se_col = next((c for c in mean_pl.columns if c.lower() in def_se_names), None)
assert _mean_se_col is not None, f"no SE column found in mean result: {mean_pl.columns}"
svy_mean_se = float(mean_pl.item(0, _mean_se_col))
assert np.isfinite(svy_mean_se) and svy_mean_se > 0, f"mean SE not positive/finite: {svy_mean_se}"
print(f"  mean SE: {svy_mean_se:.6f}  (positive, finite)")

# Determinism: recompute the same estimation and require bitwise-equal point estimate AND SE.
# ASSUMES: 0.19.0's deterministic-Taylor claim covers both the estimate and its variance.
mean_res2 = svy.Sample(df, design=design).estimation.mean(y="income")
mean_pl2 = mean_res2.to_polars()
svy_mean2 = float(mean_pl2.item(0, _mean_est_col))
svy_mean_se2 = float(mean_pl2.item(0, _mean_se_col))
assert svy_mean == svy_mean2, f"non-deterministic Taylor mean: {svy_mean} vs {svy_mean2}"
assert svy_mean_se == svy_mean_se2, (
    f"non-deterministic Taylor mean SE: {svy_mean_se} vs {svy_mean_se2}"
)
print(f"  determinism: mean+SE bitwise-equal across two runs")
print("  PASS\n")
hard_pass += 1

# --- Test 2 (HARD): batched multi-variable prop()/ratio()/median() ---
# INTENT: verify the 0.19.0 batched-call extension -- pass several y variables in one call and
#   confirm every requested variable appears in the result.
# REASONING: batching for ratio/prop/median is the headline 0.19.0 estimation feature. The
#   hard claim is structural (all requested variables returned), not numeric, so exact values
#   are printed but not asserted.
# ASSUMES: prop()/median() accept a list y=[...]; ratio() takes list y=[...] plus a denominator
#   x=. If the batched signature differs, the structural assert surfaces it clearly.
hard_total += 1
print("Test 2 (HARD): batched multi-variable prop()/ratio()/median()")

# prop() on two binary/categorical-codeable columns at once.
prop_batch = sample.estimation.prop(y=["employed", "gender"])
prop_pl = prop_batch.to_polars()
print(f"  prop batch columns: {prop_pl.columns}  rows: {prop_pl.height}")
# The batched result must reference both requested variables somewhere (column values or a
# 'variable' key). Search the frame's string cells + column names for both names.
_flat = set(prop_pl.columns)
for c in prop_pl.columns:
    if prop_pl.schema[c] == pl.Utf8:
        _flat |= set(prop_pl.get_column(c).to_list())
assert "employed" in _flat, f"'employed' missing from batched prop result: {prop_pl}"
assert "gender" in _flat, f"'gender' missing from batched prop result: {prop_pl}"
print("  batched prop references both requested variables")

# median() batched on two continuous columns.
median_batch = sample.estimation.median(y=["income", "age"])
median_pl = median_batch.to_polars()
print(f"  median batch columns: {median_pl.columns}  rows: {median_pl.height}")
assert median_pl.height >= 2, f"expected >=2 median rows for 2 vars, got {median_pl.height}"

# ratio() batched: two numerators over one denominator.
ratio_batch = sample.estimation.ratio(y=["income", "visit_count"], x="age")
ratio_pl = ratio_batch.to_polars()
print(f"  ratio batch columns: {ratio_pl.columns}  rows: {ratio_pl.height}")
assert ratio_pl.height >= 2, f"expected >=2 ratio rows for 2 numerators, got {ratio_pl.height}"
print("  PASS\n")
hard_pass += 1

# --- Test 3 (HARD): domain estimation -- by= / where= / same-column-in-both ---
# INTENT: exercise grouped estimation (by=), filtered estimation (where=), and the issue-#9
#   case where the SAME column drives both by= and where=. Assert group counts and that domain
#   estimates actually differ across groups.
# REASONING: domain estimation with by=/where= is core survey functionality, and the same-
#   column-in-both case is a named 0.19.0 fix (issue #9) -- worth a dedicated hard assertion.
#   Income was constructed with a stratum-level shift, so stratum-domain means should differ.
# ASSUMES: by= accepts a grouping column name; where= accepts a polars-style predicate or an
#   expression on the frame's columns. The exact where= grammar is one of the researched
#   uncertainties (issue #2, where= vs filter_records), so the predicate is kept simple.
hard_total += 1
print("Test 3 (HARD): domain estimation (by= / where= / same-column-in-both)")

# by= grouped means over stratum: expect one row per stratum, differing estimates.
by_res = sample.estimation.mean(y="income", by="stratum")
by_pl = by_res.to_polars()
print(f"  by=stratum result: {by_pl.height} rows, columns {by_pl.columns}")
assert by_pl.height == n_strata, f"expected {n_strata} domain rows, got {by_pl.height}"
_by_est_col = next((c for c in by_pl.columns if c.lower() in def_est_names), None)
assert _by_est_col is not None, f"no estimate column in by= result: {by_pl.columns}"
_by_vals = by_pl.get_column(_by_est_col).to_list()
assert max(_by_vals) - min(_by_vals) > 1.0, (
    f"domain means do not differ across strata (constructed to differ): {_by_vals}"
)
print(f"  stratum domain means range: {min(_by_vals):.1f} .. {max(_by_vals):.1f} (differ)")

# where= filtered mean: restrict to a subgroup, expect a valid single estimate.
where_res = sample.estimation.mean(y="income", where=pl.col("gender") == "Male")
where_pl = where_res.to_polars()
_where_est_col = next((c for c in where_pl.columns if c.lower() in def_est_names), None)
assert _where_est_col is not None, f"no estimate column in where= result: {where_pl.columns}"
_where_est = float(where_pl.item(0, _where_est_col))
assert np.isfinite(_where_est) and _where_est > 0, f"where= estimate invalid: {_where_est}"
print(f"  where=(gender==Male) mean income: {_where_est:.1f}")

# Issue-#9 case: SAME column (stratum) in both by= and where=.
# INTENT: group by stratum while also filtering on stratum -- the exact pattern 0.19.0 fixed.
# ASSUMES: filtering to strata {1,2,3} then grouping by stratum yields exactly 3 domain rows.
same_col_res = sample.estimation.mean(
    y="income", by="stratum", where=pl.col("stratum") <= 3
)
same_col_pl = same_col_res.to_polars()
print(f"  by=stratum + where=stratum<=3: {same_col_pl.height} rows")
assert same_col_pl.height == 3, (
    f"issue-#9 case: expected 3 domain rows (strata 1-3), got {same_col_pl.height}"
)
print("  same-column-in-both (issue #9) produced the expected 3 domains")
print("  PASS\n")
hard_pass += 1

# --- Test 4 (HARD): logistic GLM (family="binomial") ---
# INTENT: fit a survey-weighted logistic regression and assert the coefficient table has the
#   expected structure, finite SEs, and a plausible (positive) sign on age.
# REASONING: `employed` was built with a known positive age relationship, so the age
#   coefficient should be positive -- a weak but real correctness signal. P-values are NOT
#   asserted: open upstream issue #5 questions their agreement with R, so encoding a p-value
#   claim would be premature. This is a HARD section because coefficient-table *structure* and
#   *finite SEs* are claims the skill will state; only the numeric p-value claim is withheld.
# ASSUMES: sample.glm.fit(y=, x=[...], family="binomial") returns a model exposing .to_polars()
#   with a per-term coefficient table containing coefficient and SE columns.
hard_total += 1
print("Test 4 (HARD): logistic GLM (family=binomial)")

logit_model = sample.glm.fit(y="employed", x=["age", "gender"], family="binomial")
logit_pl = logit_model.to_polars()
print(f"  GLM coef table columns: {logit_pl.columns}  rows: {logit_pl.height}")
assert logit_pl.height >= 2, f"expected >=2 coefficient rows (intercept+terms), got {logit_pl.height}"

# Locate coefficient and SE columns; locate the term/label column to find the age row.
_coef_names = ("coef", "coefficient", "estimate", "beta")
_term_names = ("term", "variable", "name", "parameter", "predictor")
_coef_col = next((c for c in logit_pl.columns if c.lower() in _coef_names), None)
_se_col = next((c for c in logit_pl.columns if c.lower() in def_se_names), None)
_term_col = next((c for c in logit_pl.columns if c.lower() in _term_names), None)
assert _coef_col is not None, f"no coefficient column in GLM result: {logit_pl.columns}"
assert _se_col is not None, f"no SE column in GLM result: {logit_pl.columns}"

# All coefficients finite; all SEs positive and finite.
_coefs = logit_pl.get_column(_coef_col).to_list()
_ses = logit_pl.get_column(_se_col).to_list()
assert all(np.isfinite(v) for v in _coefs), f"non-finite GLM coefficient(s): {_coefs}"
assert all(np.isfinite(s) and s > 0 for s in _ses), f"non-positive/finite GLM SE(s): {_ses}"

# Plausible sign on age (constructed positive). Locate the age row if a term column exists.
if _term_col is not None:
    _age_rows = logit_pl.filter(
        pl.col(_term_col).cast(pl.Utf8).str.contains("age")
    )
    if _age_rows.height >= 1:
        _age_coef = float(_age_rows.item(0, _coef_col))
        print(f"  age coefficient: {_age_coef:+.4f} (constructed positive)")
        assert _age_coef > 0, (
            f"age coefficient sign {_age_coef} contradicts the constructed positive relationship"
        )
    else:
        print("  age term not locatable by name; sign check skipped (structure still asserted)")
else:
    print("  no term-label column; sign check skipped (structure + finite SEs still asserted)")
print("  p-values intentionally NOT asserted (open upstream issue #5 vs R)")
print("  PASS\n")
hard_pass += 1

# =============================================================================
# PROBE SECTIONS -- uncertain 0.19.0 claims; failures are recorded, not fatal.
# =============================================================================

# --- Test 5 (PROBE): Poisson and Gamma GLM ---
# INTENT: attempt Poisson and Gamma survey GLMs and record the observed result structure.
# REASONING: docs confirm these families are *supported* but ship NO working code examples, so
#   their behavior is uncertain. A probe generates the evidence that decides whether the skill
#   encodes, hedges, or omits these families. Each family is its own probe count.
# ASSUMES: same glm.fit signature as the logistic case, with family="poisson"/"gamma".
print("Test 5 (PROBE): Poisson and Gamma GLM")
for _family, _yvar in (("poisson", "visit_count"), ("gamma", "income")):
    try:
        _m = sample.glm.fit(y=_yvar, x=["age", "gender"], family=_family)
        _mpl = _m.to_polars()
        print(f"  [{_family}] OK -- coef table columns {_mpl.columns}, {_mpl.height} rows")
        probe_success += 1
    except Exception as _e:  # noqa: BLE001 -- probe: record, do not crash
        print(f"  [{_family}] FAILED -- {type(_e).__name__}: {_e}")
        probe_fail += 1
print()

# --- Test 6 (PROBE): model.margins() ---
# INTENT: call margins() on the fitted logistic model and print whatever structure comes back.
# REASONING: margins() is documented but carries no correctness claim vs R. Pure discovery: we
#   want the output shape recorded so the skill can describe (or omit) it accurately.
# ASSUMES: logit_model from Test 4 exposes .margins(); signature (with/without at=) unknown, so
#   the bare call is tried first, then margins(at=...) as a secondary attempt.
print("Test 6 (PROBE): model.margins()")
try:
    _marg = logit_model.margins()
    _mpl = _marg.to_polars() if hasattr(_marg, "to_polars") else _marg
    print(f"  margins() OK -- type {type(_marg).__name__}; "
          f"{'columns ' + str(_mpl.columns) if hasattr(_mpl, 'columns') else repr(_mpl)[:200]}")
    probe_success += 1
except Exception as _e:  # noqa: BLE001 -- probe
    print(f"  margins() FAILED -- {type(_e).__name__}: {_e}")
    print("  retrying with margins(at=...) ...")
    try:
        _marg = logit_model.margins(at={"age": 40})
        print(f"  margins(at=) OK -- type {type(_marg).__name__}")
        probe_success += 1
    except Exception as _e2:  # noqa: BLE001 -- probe
        print(f"  margins(at=) FAILED -- {type(_e2).__name__}: {_e2}")
        probe_fail += 1
print()

# --- Test 7 (PROBE): svy-io .dta round-trip ---
# INTENT: write the synthetic frame to Stata .dta via svy-io, read it back, and assert the
#   round-trip preserves shape and a checksum column -- discovering the import path and the
#   writer/reader function names defensively.
# REASONING: whether I/O is `svy.io.read_stata` (dotted submodule) or a separate `import svy_io`
#   is NOT confirmed at 0.19; svy-io only reached a stable 0.1.0 in April 2026. Both the import
#   path and the exact write/read function names are discovered inside the probe. This is a
#   probe (not hard) because a failure here is a discovery finding for the skill, not a defect
#   that should abort the other evidence.
# ASSUMES: some accessible read/write pair exists among the documented candidate names; the
#   writer accepts a polars frame + path; the reader returns a polars frame or a (frame, meta)
#   tuple (docs say svy-io returns (DataFrame, metadata_dict)).
print("Test 7 (PROBE): svy-io .dta round-trip")
os.makedirs(SCRATCH_DIR, exist_ok=True)
_dta_path = os.path.join(SCRATCH_DIR, "smoke_svy_roundtrip.dta")
try:
    # Resolve the I/O module: try the dotted submodule first, then a separate package.
    _io = None
    _io_source = None
    for _attempt in ("svy.io", "svy_io", "svyio"):
        try:
            if _attempt == "svy.io":
                _io = getattr(svy, "io", None)
                if _io is not None:
                    _io_source = "svy.io (submodule)"
                    break
            else:
                import importlib

                _io = importlib.import_module(_attempt)
                _io_source = f"{_attempt} (separate package)"
                break
        except Exception:  # noqa: BLE001 -- keep trying candidate import paths
            continue
    if _io is None:
        raise ImportError("no svy-io accessible via svy.io / svy_io / svyio")
    print(f"  I/O module resolved via: {_io_source}")
    print(f"  I/O module attributes (sample): "
          f"{[a for a in dir(_io) if not a.startswith('_')][:20]}")

    # Discover a Stata writer among documented candidate names.
    _write_fn = None
    _write_name = None
    for _cand in ("write_stata", "write_dta", "to_stata", "write"):
        _fn = getattr(_io, _cand, None)
        if callable(_fn):
            _write_fn, _write_name = _fn, _cand
            break
    if _write_fn is None:
        raise AttributeError(f"no Stata writer found on {_io_source}")

    # A checksum column to verify content survives the round-trip exactly.
    _rt = df.with_columns(
        (pl.col("income") + pl.col("age") + pl.col("weight")).alias("checksum")
    )
    # Writer arg convention unknown: try (df, path) then (path, df) then keyword forms.
    _written = False
    for _call in ("df_path", "path_df", "kw_data", "kw_frame"):
        try:
            if _call == "df_path":
                _write_fn(_rt, _dta_path)
            elif _call == "path_df":
                _write_fn(_dta_path, _rt)
            elif _call == "kw_data":
                _write_fn(data=_rt, path=_dta_path)
            else:
                _write_fn(frame=_rt, path=_dta_path)
            _written = True
            print(f"  wrote .dta via {_write_name}() (arg style: {_call})")
            break
        except Exception:  # noqa: BLE001 -- try the next calling convention
            continue
    if not _written or not os.path.exists(_dta_path):
        raise RuntimeError(f"{_write_name}() did not produce {_dta_path} under any arg style")

    # Discover a Stata reader.
    _read_fn = None
    _read_name = None
    for _cand in ("read_stata", "read_dta", "read"):
        _fn = getattr(_io, _cand, None)
        if callable(_fn):
            _read_fn, _read_name = _fn, _cand
            break
    if _read_fn is None:
        raise AttributeError(f"no Stata reader found on {_io_source}")

    _read_out = _read_fn(_dta_path)
    # svy-io docs: returns (polars.DataFrame, metadata_dict). Accept a bare frame too.
    if isinstance(_read_out, tuple):
        _back = _read_out[0]
        print(f"  read_*() returned a {len(_read_out)}-tuple (frame + metadata)")
    else:
        _back = _read_out
        print(f"  read_*() returned a bare {type(_back).__name__}")

    assert _back.shape[0] == _rt.shape[0], (
        f"round-trip row count {_back.shape[0]} != {_rt.shape[0]}"
    )
    assert "checksum" in _back.columns, f"checksum column lost in round-trip: {_back.columns}"
    # Checksum values must match to Stata's float precision (double); use a loose tolerance.
    _orig_sum = float(_rt.get_column("checksum").sum())
    _back_sum = float(_back.get_column("checksum").sum())
    assert abs(_orig_sum - _back_sum) < 1e-3 * max(1.0, abs(_orig_sum)), (
        f"checksum column differs after round-trip: {_orig_sum} vs {_back_sum}"
    )
    print(f"  round-trip OK via {_read_name}(): shape {_back.shape}, checksum preserved")
    probe_success += 1
except Exception as _e:  # noqa: BLE001 -- probe: record full context, do not crash
    print(f"  svy-io round-trip FAILED -- {type(_e).__name__}: {_e}")
    traceback.print_exc()
    probe_fail += 1
finally:
    shutil.rmtree(SCRATCH_DIR, ignore_errors=True)
print()

# --- Test 8 (PROBE): replicate weights -- bootstrap + jackknife + determinism ---
# INTENT: create bootstrap and jackknife replicate weight sets, assert the expected replicate-
#   column counts, then run a replication-variance mean twice with the same rstate and assert
#   determinism.
# REASONING: replicate weight creation and replication variance were unstable pre-0.17.1;
#   0.19.0 claims determinism. The column-count assertion is structural; the determinism check
#   is the substantive one. Kept as a PROBE because the weighting-namespace method names and
#   signatures (create_bs_wgts / create_jk_wgts, rstate=, n_reps=, rep_prefix=) are documented
#   but unconfirmed by execution.
# ASSUMES: sample.weighting.create_bs_wgts(n_reps=, rstate=) and .create_jk_wgts(); the result
#   exposes the replicate-augmented frame (or a new Sample) whose replicate columns are
#   countable; a subsequent estimation.mean(method="replication") is deterministic given rstate.
print("Test 8 (PROBE): replicate weights (bootstrap + jackknife + determinism)")
try:
    n_reps = 20
    # Bootstrap replicate weights.
    bs = sample.weighting.create_bs_wgts(n_reps=n_reps, rstate=42)
    print(f"  create_bs_wgts returned type: {type(bs).__name__}")

    # Locate the replicate-augmented frame to count replicate columns. The return may be a new
    # Sample, a frame, or an object exposing one; probe common access points.
    _bs_frame = None
    for _accessor in ("to_polars", "df", "data", "frame"):
        _obj = getattr(bs, _accessor, None)
        if callable(_obj):
            try:
                _bs_frame = _obj()
                break
            except Exception:  # noqa: BLE001
                continue
        elif _obj is not None:
            _bs_frame = _obj
            break
    if isinstance(_bs_frame, pl.DataFrame):
        _rep_cols = [c for c in _bs_frame.columns if "rep" in c.lower()]
        print(f"  bootstrap replicate-like columns detected: {len(_rep_cols)}")
        # Expect roughly n_reps replicate columns (allow the frame to also carry base columns).
        assert len(_rep_cols) >= n_reps, (
            f"expected >= {n_reps} replicate columns, found {len(_rep_cols)}"
        )
    else:
        print(f"  bootstrap frame not directly countable (return type {type(bs).__name__})")

    # Jackknife replicate weights (paired=False -> JKn per docs).
    jk = sample.weighting.create_jk_wgts()
    print(f"  create_jk_wgts returned type: {type(jk).__name__}")

    # Determinism of replication-variance mean: two runs, same rstate, bitwise-equal.
    bs_a = sample.weighting.create_bs_wgts(n_reps=n_reps, rstate=7)
    bs_b = sample.weighting.create_bs_wgts(n_reps=n_reps, rstate=7)
    m_a = bs_a.estimation.mean(y="income", method="replication").to_polars()
    m_b = bs_b.estimation.mean(y="income", method="replication").to_polars()
    _ecol = next((c for c in m_a.columns if c.lower() in def_est_names), m_a.columns[0])
    _va = float(m_a.item(0, _ecol))
    _vb = float(m_b.item(0, _ecol))
    assert _va == _vb, f"replication mean not deterministic across same-rstate runs: {_va} vs {_vb}"
    print(f"  replication-variance mean deterministic across same rstate: {_va:.6f}")
    probe_success += 1
except Exception as _e:  # noqa: BLE001 -- probe
    print(f"  replicate-weights probe FAILED -- {type(_e).__name__}: {_e}")
    traceback.print_exc()
    probe_fail += 1
print()

# --- Bonus (PROBE): polars 1.39.x replace_strict-on-Enum regression (issue #27060) ---
# INTENT: document the known-carried polars regression for the record. Build a tiny Enum-dtype
#   column and attempt replace_strict to strings, reporting whether it raises or succeeds.
# REASONING: polars 1.39.1 is the effective floor (driven by svy-rs). Issue #27060 reports
#   replace_strict raising InvalidOperationError on Enum dtype at 1.39.x. Either outcome is a
#   PASS here -- this is informational, capturing the environment's behavior so the skill can
#   warn (or not) accurately. Counted as a probe success regardless of raise/succeed; only an
#   unexpected error type would be notable.
# ASSUMES: pl.Enum exists and replace_strict is available on the Series/Expr at this version.
print("Bonus (PROBE): polars replace_strict-on-Enum regression (issue #27060)")
try:
    _enum_dtype = pl.Enum(["a", "b", "c"])
    _enum_series = pl.Series("cat", ["a", "b", "c", "a"], dtype=_enum_dtype)
    try:
        _out = _enum_series.replace_strict(
            pl.Series(["a", "b", "c"], dtype=_enum_dtype),
            pl.Series(["A", "B", "C"]),
        )
        print(f"  replace_strict on Enum SUCCEEDED (regression not present at this polars): "
              f"result head {_out.head(4).to_list()}")
    except pl.exceptions.InvalidOperationError as _e:
        print(f"  replace_strict on Enum raised InvalidOperationError (expected at 1.39.x): {_e}")
    print("  informational PASS (either outcome documents the carried regression)")
    probe_success += 1
except Exception as _e:  # noqa: BLE001 -- unexpected setup error is still non-fatal
    print(f"  Enum-regression probe setup FAILED -- {type(_e).__name__}: {_e}")
    probe_fail += 1
print()

# --- Summary ---
# INTENT: report hard-section and probe outcomes separately so the skill author can tell which
#   claims are proven fact (hard) versus which uncertain claims the evidence supports, hedges,
#   or refutes (probes).
print("=== smoke_svy.py summary ===")
print(f"  HARD PASS {hard_pass}/{hard_total}")
print(f"  PROBES: {probe_success} succeeded, {probe_fail} failed (see output above)")
print(f"  Tested against: svy {svy.__version__}, polars {pl.__version__}")

# A hard-section failure would already have crashed the script via assert. Reaching here means
# all hard sections passed; exit success. Probe failures are informational and do NOT set a
# nonzero exit code -- they are evidence for the skill revision, not defects in this test.
assert hard_pass == hard_total, (
    f"internal accounting error: hard_pass {hard_pass} != hard_total {hard_total}"
)
print("=== All HARD smoke tests PASSED ===")
sys.exit(0)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 02:24:06
# Command: python3 /daaf/scripts/smoke_tests/smoke_svy.py
# Duration: 2s
# Exit code: 1
#
# --- STDOUT ---
# === svy (Python complex-survey) Smoke Test ===
# 
#   svy version:    0.19.0
#   polars version: 1.39.3
#   numpy version:  2.4.2
#   svy-rs dist version: 0.10.0
#   svy-io dist version: 0.1.1
#   polars dist version: 1.39.3
#   version gate OK: svy 0.19.0 >= 0.19
# 
# Synthetic survey frame: 480 rows, 9 cols, 4 strata x 6 PSUs x 20 obs
# 
# Test 1 (HARD): Taylor mean/total on stratified-clustered design
# Traceback (most recent call last):
#   File "/daaf/scripts/smoke_tests/smoke_svy.py", line 182, in <module>
#     design = svy.Design(wgt="weight", stratum="stratum", psu="psu", fpc="fpc_pop")
#              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# TypeError: Design.__init__() got an unexpected keyword argument 'fpc'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
