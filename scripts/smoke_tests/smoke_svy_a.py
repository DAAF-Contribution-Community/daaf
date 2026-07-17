# scripts/smoke_tests/smoke_svy_a.py
# Functional smoke test for the Python `svy` complex-survey stack.
#
# REVISION _a: the original smoke_svy.py (immutable, log appended) was authored against the
# ONLINE 0.19.0 docs, which proved partly aspirational. This revision rewrites every API call
# against the OBSERVED installed API surface, discovered by introspection in
# scripts/scratch/diag_svy_api.py, diag_svy_api_a.py, diag_svy_api_b.py. Architecture, the
# hard/probe split, test-coverage intent, and the summary format are preserved from the
# original; IAT comments are updated wherever the API reality differed from the docs.
#
# Observed-vs-documented deltas encoded below (quoted introspection evidence in the diag logs):
#   - svy.Design has NO `fpc=` param. FPC is specified via `pop_size=` (a column name) or
#     svy.PopSize(psu=, ssu=). Observed sig:
#       Design(row_index, stratum, wgt, prob, hit, mos, psu, ssu, pop_size, wr, rep_wgts)
#   - Estimation result frames use columns ['est','se','lci','uci','cv'] -- NOT
#     'estimate'/'stderr'. GLM coef tables use ['term','estimate','std_err','conf_low',
#     'conf_high','statistic','p_value','df'].
#   - Batched estimation (y=[...]) returns a LIST of Estimate objects, not one stacked frame.
#   - where= requires a POLARS EXPRESSION; a string predicate raises TypeError.
#   - glm.fit REQUIRES string/categorical predictors wrapped in svy.Cat(); a raw string column
#     raises ValueError (strict_cast str->f64). All four families (gaussian/binomial/poisson/
#     gamma) fit and return a p_value column (issue #5 is about correctness-vs-R, not absence).
#   - margins() returns a list[GLMMargins] by default (AME).
#   - svy-io: svy.io.read_stata(path) returns a BARE polars.DataFrame (not a (df, meta) tuple);
#     svy.io.write_stata(sample, path) takes a SAMPLE object, not a DataFrame.
#   - create_bs_wgts()/create_jk_wgts() return a NEW Sample whose .data carries replicate-weight
#     columns named "{wgt_prefix}{1..n}" (default prefix = base weight col name); the count is
#     also exposed as sample.rep_wgts.n_reps.
#
# HARD vs PROBE sections (unchanged intent):
#   - HARD sections use bare assert -- a failure crashes the script. These encode claims the
#     skill will state as FACT.
#   - PROBE sections wrap uncertain claims in try/except, print observed structure on success or
#     the full exception on failure, and are counted separately. A probe failure is a finding,
#     not a defect.
# The closing summary distinguishes `HARD PASS n/n` from `PROBES: m succeeded, k failed`.
#
# Sequential inline script (DAAF style): no functions (except the tiny column-locator helper,
# which is a pure lookup, not a data-processing function), print + assert validation, polars
# for all data handling (never pandas), synthetic data seeded for reproducibility.

# --- Config ---
import os
import shutil
import sys
import traceback

import numpy as np
import polars as pl
import svy

# INTENT: echo every stack version so the appended execution log is version-visible.
# REASONING: a smoke result that does not name the build it tested cannot ground a skill
#   revision. svy-rs is internal and svy-io is a bundled dependency, so both are reported
#   best-effort via importlib.metadata rather than asserted.
print("=== svy (Python complex-survey) Smoke Test [revision _a] ===\n")
print(f"  svy version:    {svy.__version__}")
print(f"  polars version: {pl.__version__}")
print(f"  numpy version:  {np.__version__}")

try:
    import importlib.metadata as _md

    for _pkg in ("svy-rs", "svy-io", "polars"):
        try:
            print(f"  {_pkg} dist version: {_md.version(_pkg)}")
        except Exception as _e:  # noqa: BLE001 -- best-effort dist-version report only
            print(f"  {_pkg} dist version: unavailable ({_e!r})")
except Exception as _e:  # noqa: BLE001
    print(f"  importlib.metadata unavailable: {_e!r}")

# INTENT: gate on svy>=0.19 before running any 0.19-specific test.
# REASONING: parse major.minor as integers to avoid lexical string-compare pitfalls.
# ASSUMES: __version__ is a dotted numeric string.
_ver_parts = svy.__version__.split(".")
_major = int(_ver_parts[0])
_minor = int(_ver_parts[1]) if len(_ver_parts) > 1 else 0
assert (_major, _minor) >= (0, 19), (
    f"smoke_svy_a.py targets svy>=0.19.0 but found {svy.__version__}"
)
print(f"  version gate OK: svy {svy.__version__} >= 0.19\n")

rng = np.random.default_rng(42)

hard_pass = 0
hard_total = 0
probe_success = 0
probe_fail = 0

# INTENT: column-name locators for the OBSERVED result schemas.
# REASONING: estimation frames use 'est'/'se'; GLM coef tables use 'estimate'/'std_err'. Both
#   name families are listed so the locators work across estimation and regression outputs.
EST_NAMES = ("est", "estimate", "mean", "total", "value", "point_estimate")
SE_NAMES = ("se", "std_err", "stderr", "std_error", "standard_error")
COEF_NAMES = ("estimate", "coef", "coefficient", "beta")
TERM_NAMES = ("term", "variable", "name", "parameter", "predictor")
STAT_COLS = {"est", "se", "lci", "uci", "cv"}  # non-category columns in estimation frames


def find_col(frame, names):
    # INTENT: return the first column whose lowercased name is in `names`, else None.
    return next((c for c in frame.columns if c.lower() in names), None)


# --- Synthetic stratified-clustered survey dataset ---
# INTENT: stratified two-stage-clustered frame with continuous/binary/count outcomes, a
#   categorical, unequal weights, and an FPC-suitable population size per stratum.
# REASONING: mirrors smoke_survey_r.R so R/Python results are comparable. Sized 4x6x20=480 for
#   stable-but-fast estimates. Weights unequal so weighted != unweighted (the closed-form check
#   bites). Income carries a stratum-level shift so domain means differ.
# ASSUMES: Design accepts stratum/psu/wgt column-name refs plus pop_size for FPC (OBSERVED API).
n_strata = 4
n_psu_per_stratum = 6
n_obs_per_psu = 20
n = n_strata * n_psu_per_stratum * n_obs_per_psu  # 480

stratum = np.repeat(np.arange(1, n_strata + 1), n_psu_per_stratum * n_obs_per_psu)
# PSU ids unique across the whole frame (nested design: PSU implies stratum).
psu = np.repeat(np.arange(1, n_strata * n_psu_per_stratum + 1), n_obs_per_psu)
weight = rng.uniform(0.5, 5.0, size=n)
income = 30000.0 + 500.0 * stratum + rng.normal(0.0, 5000.0, size=n)
age = rng.integers(18, 81, size=n).astype(float)
gender = rng.choice(["Male", "Female"], size=n)
# Binary outcome with a KNOWN positive age relationship (the logistic section asserts sign).
_p_employed = 1.0 / (1.0 + np.exp(-(-1.0 + 0.02 * age + 0.5 * (gender == "Male"))))
employed = rng.binomial(1, _p_employed).astype(float)
visit_count = rng.poisson(np.exp(0.5 + 0.01 * age / 10.0)).astype(float)
# FPC population per stratum, larger than the realized sample so the correction is valid.
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

SCRATCH_DIR = "/daaf/scripts/scratch/smoke_svy_io"

# =============================================================================
# HARD SECTIONS -- claims the skill will state as fact; assert failures crash.
# =============================================================================

# --- Test 1 (HARD): Taylor mean/total on the stratified-clustered design ---
# INTENT: confirm svy's Taylor point estimates match independently-computed weighted values
#   to floating tolerance, assert SEs are positive/finite, and verify variance determinism.
# REASONING: weighted mean = sum(w*y)/sum(w), total = sum(w*y) -- closed forms independent of
#   the variance machinery; strongest correctness anchor without a second survey library.
#   Determinism (run twice, bitwise-equal) tests the 0.19.0 deterministic-Taylor claim.
# ASSUMES (OBSERVED): Design(stratum=, wgt=, psu=, pop_size=) -- FPC via pop_size, NOT fpc=;
#   Sample(df, design=); estimation.mean/.total return an Estimate whose .to_polars() carries
#   'est' and 'se' columns.
hard_total += 1
print("Test 1 (HARD): Taylor mean/total on stratified-clustered design")

# OBSERVED DELTA: documented `fpc="fpc_pop"` does not exist -> use `pop_size="fpc_pop"`.
design = svy.Design(wgt="weight", stratum="stratum", psu="psu", pop_size="fpc_pop")
sample = svy.Sample(df, design=design)

_ref = df.select(
    (pl.col("weight") * pl.col("income")).sum().alias("wy"),
    pl.col("weight").sum().alias("w"),
)
ref_wy = _ref.item(0, "wy")
ref_w = _ref.item(0, "w")
ref_mean = ref_wy / ref_w
ref_total = ref_wy

mean_res = sample.estimation.mean("income")
total_res = sample.estimation.total("income")
mean_pl = mean_res.to_polars()
total_pl = total_res.to_polars()
print(f"  mean result columns:  {mean_pl.columns}")
print(f"  total result columns: {total_pl.columns}")

_mean_est_col = find_col(mean_pl, EST_NAMES)
_total_est_col = find_col(total_pl, EST_NAMES)
assert _mean_est_col is not None, f"no estimate column in mean result: {mean_pl.columns}"
assert _total_est_col is not None, f"no estimate column in total result: {total_pl.columns}"

svy_mean = float(mean_pl.item(0, _mean_est_col))
svy_total = float(total_pl.item(0, _total_est_col))

assert abs(svy_mean - ref_mean) < 1e-6, (
    f"Taylor mean {svy_mean} != closed-form weighted mean {ref_mean} "
    f"(diff {abs(svy_mean - ref_mean):.3e})"
)
assert abs(svy_total - ref_total) < 1e-3 * max(1.0, abs(ref_total)), (
    f"Taylor total {svy_total} != closed-form weighted total {ref_total}"
)
print(f"  mean: svy={svy_mean:.6f}  closed-form={ref_mean:.6f}  (match)")
print(f"  total: svy={svy_total:.2f}  closed-form={ref_total:.2f}")

_mean_se_col = find_col(mean_pl, SE_NAMES)
assert _mean_se_col is not None, f"no SE column in mean result: {mean_pl.columns}"
svy_mean_se = float(mean_pl.item(0, _mean_se_col))
assert np.isfinite(svy_mean_se) and svy_mean_se > 0, f"mean SE not positive/finite: {svy_mean_se}"
print(f"  mean SE: {svy_mean_se:.6f}  (positive, finite)")

# Determinism: recompute; require bitwise-equal point estimate AND SE.
mean_pl2 = svy.Sample(df, design=design).estimation.mean("income").to_polars()
svy_mean2 = float(mean_pl2.item(0, _mean_est_col))
svy_mean_se2 = float(mean_pl2.item(0, _mean_se_col))
assert svy_mean == svy_mean2, f"non-deterministic Taylor mean: {svy_mean} vs {svy_mean2}"
assert svy_mean_se == svy_mean_se2, f"non-deterministic Taylor mean SE: {svy_mean_se} vs {svy_mean_se2}"
print("  determinism: mean+SE bitwise-equal across two runs")
print("  PASS\n")
hard_pass += 1

# --- Test 2 (HARD): batched multi-variable prop()/ratio()/median() ---
# INTENT: verify the 0.19.0 batched extension -- pass several y variables in one call.
# REASONING: batching for ratio/prop/median is the headline 0.19.0 feature.
# ASSUMES (OBSERVED DELTA): batched calls return a LIST of Estimate objects (one per y), NOT a
#   single stacked frame with a 'variable' column. The structural claim is therefore
#   "len(list) == number of requested variables" plus per-element frame validity.
hard_total += 1
print("Test 2 (HARD): batched multi-variable prop()/ratio()/median()")

# prop() on two columns at once -> list of 2 Estimate objects.
prop_batch = sample.estimation.prop(["employed", "gender"])
assert isinstance(prop_batch, list), f"batched prop expected list, got {type(prop_batch).__name__}"
assert len(prop_batch) == 2, f"batched prop expected 2 elements, got {len(prop_batch)}"
# Each element's non-stat columns name the variable (prop uses the varname as its category col).
_prop_vars = set()
for _est in prop_batch:
    _pf = _est.to_polars()
    _prop_vars |= {c for c in _pf.columns if c.lower() not in STAT_COLS}
print(f"  batched prop -> list len {len(prop_batch)}; category columns seen: {sorted(_prop_vars)}")
assert "employed" in _prop_vars, f"'employed' missing from batched prop category cols: {_prop_vars}"
assert "gender" in _prop_vars, f"'gender' missing from batched prop category cols: {_prop_vars}"
print("  batched prop references both requested variables")

# median() batched on two continuous columns -> list of 2.
median_batch = sample.estimation.median(["income", "age"])
assert isinstance(median_batch, list) and len(median_batch) == 2, (
    f"batched median expected list of 2, got {type(median_batch).__name__} "
    f"len {len(median_batch) if isinstance(median_batch, list) else 'n/a'}"
)
print(f"  batched median -> list len {len(median_batch)}; "
      f"elem[0] cols {median_batch[0].to_polars().columns}")

# ratio() batched: two numerators over one denominator -> list of 2.
ratio_batch = sample.estimation.ratio(["income", "visit_count"], "age")
assert isinstance(ratio_batch, list) and len(ratio_batch) == 2, (
    f"batched ratio expected list of 2, got {type(ratio_batch).__name__}"
)
print(f"  batched ratio -> list len {len(ratio_batch)}; "
      f"elem[0] cols {ratio_batch[0].to_polars().columns}")
print("  PASS\n")
hard_pass += 1

# --- Test 3 (HARD): domain estimation -- by= / where= / same-column-in-both ---
# INTENT: exercise grouped (by=), filtered (where=), and the issue-#9 same-column case.
# REASONING: domain estimation with by=/where= is core; the same-column case is the named
#   0.19.0 fix (issue #9). Income has a stratum-level shift so stratum-domain means differ.
# ASSUMES (OBSERVED): by= returns a single Estimate with one row per group (group col
#   prepended); where= requires a POLARS EXPRESSION (a string raises TypeError).
hard_total += 1
print("Test 3 (HARD): domain estimation (by= / where= / same-column-in-both)")

by_res = sample.estimation.mean("income", by="stratum")
by_pl = by_res.to_polars()
print(f"  by=stratum result: {by_pl.height} rows, columns {by_pl.columns}")
assert by_pl.height == n_strata, f"expected {n_strata} domain rows, got {by_pl.height}"
_by_est_col = find_col(by_pl, EST_NAMES)
assert _by_est_col is not None, f"no estimate column in by= result: {by_pl.columns}"
_by_vals = by_pl.get_column(_by_est_col).to_list()
assert max(_by_vals) - min(_by_vals) > 1.0, (
    f"domain means do not differ across strata (constructed to differ): {_by_vals}"
)
print(f"  stratum domain means range: {min(_by_vals):.1f} .. {max(_by_vals):.1f} (differ)")

# where= filtered mean -- polars expression (string form is rejected by the installed API).
where_res = sample.estimation.mean("income", where=pl.col("gender") == "Male")
where_pl = where_res.to_polars()
_where_est_col = find_col(where_pl, EST_NAMES)
assert _where_est_col is not None, f"no estimate column in where= result: {where_pl.columns}"
_where_est = float(where_pl.item(0, _where_est_col))
assert np.isfinite(_where_est) and _where_est > 0, f"where= estimate invalid: {_where_est}"
print(f"  where=(gender==Male) mean income: {_where_est:.1f}")

# Issue-#9 case: SAME column (stratum) in both by= and where=.
same_col_res = sample.estimation.mean("income", by="stratum", where=pl.col("stratum") <= 3)
same_col_pl = same_col_res.to_polars()
print(f"  by=stratum + where=stratum<=3: {same_col_pl.height} rows")
assert same_col_pl.height == 3, (
    f"issue-#9 case: expected 3 domain rows (strata 1-3), got {same_col_pl.height}"
)
print("  same-column-in-both (issue #9) produced the expected 3 domains")
print("  PASS\n")
hard_pass += 1

# --- Test 4 (HARD): logistic GLM (family="binomial") ---
# INTENT: fit a survey-weighted logistic regression; assert coef-table structure, finite SEs,
#   and a plausible (positive) sign on age.
# REASONING: `employed` was built with a known positive age relationship. P-values are present
#   in the coef table but NOT asserted: open upstream issue #5 questions their agreement with R.
# ASSUMES (OBSERVED DELTA): string predictors MUST be wrapped in svy.Cat() -- a raw string
#   column raises ValueError (strict_cast str->f64). GLM.to_polars() carries
#   ['term','estimate','std_err',...]; the age term row has term == "age".
hard_total += 1
print("Test 4 (HARD): logistic GLM (family=binomial)")

# OBSERVED DELTA: x=["age","gender"] fails; gender must be svy.Cat("gender").
logit_model = sample.glm.fit(y="employed", x=["age", svy.Cat("gender")], family="binomial")
logit_pl = logit_model.to_polars()
print(f"  GLM coef table columns: {logit_pl.columns}  rows: {logit_pl.height}")
assert logit_pl.height >= 2, f"expected >=2 coefficient rows, got {logit_pl.height}"

_coef_col = find_col(logit_pl, COEF_NAMES)
_se_col = find_col(logit_pl, SE_NAMES)
_term_col = find_col(logit_pl, TERM_NAMES)
assert _coef_col is not None, f"no coefficient column in GLM result: {logit_pl.columns}"
assert _se_col is not None, f"no SE column in GLM result: {logit_pl.columns}"

_coefs = logit_pl.get_column(_coef_col).to_list()
_ses = logit_pl.get_column(_se_col).to_list()
assert all(np.isfinite(v) for v in _coefs), f"non-finite GLM coefficient(s): {_coefs}"
assert all(np.isfinite(s) and s > 0 for s in _ses), f"non-positive/finite GLM SE(s): {_ses}"

if _term_col is not None:
    _age_rows = logit_pl.filter(pl.col(_term_col).cast(pl.Utf8).str.contains("age"))
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
print("  p-values present in coef table but intentionally NOT asserted (open issue #5 vs R)")
print("  PASS\n")
hard_pass += 1

# =============================================================================
# PROBE SECTIONS -- uncertain claims; failures are recorded, not fatal.
# =============================================================================

# --- Test 5 (PROBE): Poisson and Gamma GLM ---
# INTENT: attempt Poisson and Gamma survey GLMs and record the observed result structure.
# REASONING: docs confirm these families but ship no working examples. Introspection showed all
#   four families fit; this probe records the coef-table structure per family as skill evidence.
# ASSUMES (OBSERVED): same glm.fit signature; string predictor wrapped in svy.Cat().
print("Test 5 (PROBE): Poisson and Gamma GLM")
for _family, _yvar in (("poisson", "visit_count"), ("gamma", "income")):
    try:
        _m = sample.glm.fit(y=_yvar, x=["age", svy.Cat("gender")], family=_family)
        _mpl = _m.to_polars()
        print(f"  [{_family}] OK -- coef table columns {_mpl.columns}, {_mpl.height} rows")
        probe_success += 1
    except Exception as _e:  # noqa: BLE001 -- probe: record, do not crash
        print(f"  [{_family}] FAILED -- {type(_e).__name__}: {_e}")
        probe_fail += 1
print()

# --- Test 6 (PROBE): model.margins() ---
# INTENT: call margins() on the fitted logistic model and record the output structure.
# REASONING: margins() carries no correctness claim vs R -- pure discovery.
# ASSUMES (OBSERVED): margins() returns a list[GLMMargins] (AME) by default; each element may
#   expose .to_polars(). signature: margins(at=None, variables=None, alpha=0.05).
print("Test 6 (PROBE): model.margins()")
try:
    _marg = logit_model.margins()
    if isinstance(_marg, list):
        print(f"  margins() OK -- list[{type(_marg[0]).__name__}] len {len(_marg)}")
        _first = _marg[0]
        if hasattr(_first, "to_polars"):
            print(f"    elem[0].to_polars() columns: {_first.to_polars().columns}")
        else:
            print(f"    elem[0] repr: {repr(_first)[:200]}")
    else:
        _mpl = _marg.to_polars() if hasattr(_marg, "to_polars") else _marg
        print(f"  margins() OK -- type {type(_marg).__name__}; "
              f"{'columns ' + str(_mpl.columns) if hasattr(_mpl, 'columns') else repr(_mpl)[:200]}")
    probe_success += 1
except Exception as _e:  # noqa: BLE001 -- probe
    print(f"  margins() FAILED -- {type(_e).__name__}: {_e}")
    probe_fail += 1
print()

# --- Test 7 (PROBE): svy-io .dta round-trip ---
# INTENT: write the synthetic frame to Stata .dta via svy-io, read it back, and assert the
#   round-trip preserves shape and a checksum column.
# REASONING: svy-io's stable API is recent (0.1.x). Introspection resolved the real surface:
#   svy.io.write_stata(sample, path) takes a SAMPLE, and svy.io.read_stata(path) returns a BARE
#   polars.DataFrame (NOT the documented (df, metadata) tuple). This probe exercises that exact
#   pair; a failure is a discovery finding for the skill, not a defect that should abort.
# ASSUMES (OBSERVED): svy.io submodule present; writer accepts a Sample built from the frame
#   (design optional on Sample); reader returns a DataFrame.
print("Test 7 (PROBE): svy-io .dta round-trip")
os.makedirs(SCRATCH_DIR, exist_ok=True)
_dta_path = os.path.join(SCRATCH_DIR, "smoke_svy_roundtrip.dta")
try:
    _io = getattr(svy, "io", None)
    if _io is None:
        raise ImportError("svy.io submodule not present")
    print(f"  I/O module: svy.io ({getattr(_io, '__name__', '?')})")
    _write_fn = getattr(_io, "write_stata", None)
    _read_fn = getattr(_io, "read_stata", None)
    if not callable(_write_fn) or not callable(_read_fn):
        raise AttributeError("svy.io.write_stata / read_stata not both callable")

    # A checksum column to verify content survives the round-trip exactly.
    _rt = df.with_columns(
        (pl.col("income") + pl.col("age") + pl.col("weight")).alias("checksum")
    )
    # OBSERVED DELTA: writer takes a Sample, not a DataFrame. Sample's design is optional, so a
    # design-less Sample is a valid I/O container for the round-trip.
    _rt_sample = svy.Sample(_rt)
    _write_fn(_rt_sample, _dta_path)
    if not os.path.exists(_dta_path):
        raise RuntimeError(f"write_stata did not produce {_dta_path}")
    print(f"  wrote .dta via svy.io.write_stata(sample, path)")

    _back = _read_fn(_dta_path)
    # OBSERVED DELTA: returns a bare polars.DataFrame (docs claimed a (df, metadata) tuple).
    print(f"  read via svy.io.read_stata(path) -> {type(_back).__name__}")
    assert isinstance(_back, pl.DataFrame), f"read_stata returned {type(_back).__name__}, expected DataFrame"
    assert _back.shape[0] == _rt.shape[0], f"round-trip row count {_back.shape[0]} != {_rt.shape[0]}"
    assert "checksum" in _back.columns, f"checksum column lost in round-trip: {_back.columns}"
    _orig_sum = float(_rt.get_column("checksum").sum())
    _back_sum = float(_back.get_column("checksum").sum())
    assert abs(_orig_sum - _back_sum) < 1e-3 * max(1.0, abs(_orig_sum)), (
        f"checksum differs after round-trip: {_orig_sum} vs {_back_sum}"
    )
    print(f"  round-trip OK: shape {_back.shape}, checksum preserved")
    probe_success += 1
except Exception as _e:  # noqa: BLE001 -- probe: record full context, do not crash
    print(f"  svy-io round-trip FAILED -- {type(_e).__name__}: {_e}")
    traceback.print_exc()
    probe_fail += 1
finally:
    shutil.rmtree(SCRATCH_DIR, ignore_errors=True)
print()

# --- Test 8 (PROBE): replicate weights -- bootstrap + jackknife + determinism ---
# INTENT: create bootstrap and jackknife replicate weight sets, assert the expected replicate
#   count, then run a replication-variance mean twice with the same rstate and assert determinism.
# REASONING: replicate creation + replication variance claim determinism in 0.19.0.
# ASSUMES (OBSERVED): create_bs_wgts(n_reps=, rstate=) returns a NEW Sample whose .data carries
#   replicate columns "{prefix}{1..n}" (default prefix = base weight col name), and whose
#   .rep_wgts.n_reps reports the count; create_jk_wgts() likewise returns a Sample; the returned
#   Sample exposes .estimation.mean(method="replication").
print("Test 8 (PROBE): replicate weights (bootstrap + jackknife + determinism)")
try:
    n_reps = 20
    bs = sample.weighting.create_bs_wgts(n_reps=n_reps, rstate=42)
    print(f"  create_bs_wgts returned type: {type(bs).__name__}")

    # Count replicate columns: prefer the RepWeights.n_reps metadata; also count added columns.
    _rep_meta = getattr(bs, "rep_wgts", None)
    _meta_n = getattr(_rep_meta, "n_reps", None)
    _base_cols = set(df.columns)
    _new_cols = [c for c in bs.data.columns if c not in _base_cols] if hasattr(bs, "data") else []
    print(f"  rep_wgts metadata: {repr(_rep_meta)[:120]}")
    print(f"  new columns added to .data: {len(_new_cols)} (e.g. {_new_cols[:4]})")
    assert _meta_n == n_reps, f"expected rep_wgts.n_reps == {n_reps}, got {_meta_n}"
    print(f"  bootstrap replicate count confirmed via rep_wgts.n_reps = {_meta_n}")

    jk = sample.weighting.create_jk_wgts()
    print(f"  create_jk_wgts returned type: {type(jk).__name__}")

    # Determinism: two runs, same rstate, bitwise-equal replication-variance mean.
    bs_a = sample.weighting.create_bs_wgts(n_reps=n_reps, rstate=7)
    bs_b = sample.weighting.create_bs_wgts(n_reps=n_reps, rstate=7)
    m_a = bs_a.estimation.mean("income", method="replication").to_polars()
    m_b = bs_b.estimation.mean("income", method="replication").to_polars()
    _ecol = find_col(m_a, EST_NAMES) or m_a.columns[0]
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
# INTENT: document the known-carried polars regression for the record.
# REASONING: polars 1.39.3 is the installed floor. Either outcome (raise or succeed) is a PASS
#   here -- informational, capturing the environment's behavior for the skill.
# ASSUMES: pl.Enum exists and replace_strict is available at this version.
print("Bonus (PROBE): polars replace_strict-on-Enum regression (issue #27060)")
try:
    _enum_dtype = pl.Enum(["a", "b", "c"])
    _enum_series = pl.Series("cat", ["a", "b", "c", "a"], dtype=_enum_dtype)
    try:
        _out = _enum_series.replace_strict(
            pl.Series(["a", "b", "c"], dtype=_enum_dtype),
            pl.Series(["A", "B", "C"]),
        )
        print(f"  replace_strict on Enum SUCCEEDED (regression not present): "
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
print("=== smoke_svy_a.py summary ===")
print(f"  HARD PASS {hard_pass}/{hard_total}")
print(f"  PROBES: {probe_success} succeeded, {probe_fail} failed (see output above)")
print(f"  Tested against: svy {svy.__version__}, polars {pl.__version__}")

assert hard_pass == hard_total, (
    f"internal accounting error: hard_pass {hard_pass} != hard_total {hard_total}"
)
print("=== All HARD smoke tests PASSED ===")
sys.exit(0)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 02:34:03
# Command: python3 /daaf/scripts/smoke_tests/smoke_svy_a.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# === svy (Python complex-survey) Smoke Test [revision _a] ===
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
#   mean result columns:  ['est', 'se', 'lci', 'uci', 'cv']
#   total result columns: ['est', 'se', 'lci', 'uci', 'cv']
#   mean: svy=31157.013319  closed-form=31157.013319  (match)
#   total: svy=40907202.43  closed-form=40907202.43
#   mean SE: 260.920051  (positive, finite)
#   determinism: mean+SE bitwise-equal across two runs
#   PASS
# 
# Test 2 (HARD): batched multi-variable prop()/ratio()/median()
#   batched prop -> list len 2; category columns seen: ['employed', 'gender']
#   batched prop references both requested variables
#   batched median -> list len 2; elem[0] cols ['est', 'se', 'lci', 'uci', 'cv']
#   batched ratio -> list len 2; elem[0] cols ['est', 'se', 'lci', 'uci', 'cv']
#   PASS
# 
# Test 3 (HARD): domain estimation (by= / where= / same-column-in-both)
#   by=stratum result: 4 rows, columns ['stratum', 'est', 'se', 'lci', 'uci', 'cv']
#   stratum domain means range: 30470.3 .. 32287.9 (differ)
#   where=(gender==Male) mean income: 30910.0
#   by=stratum + where=stratum<=3: 3 rows
#   same-column-in-both (issue #9) produced the expected 3 domains
#   PASS
# 
# Test 4 (HARD): logistic GLM (family=binomial)
#   GLM coef table columns: ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']  rows: 3
#   age coefficient: +0.0107 (constructed positive)
#   p-values present in coef table but intentionally NOT asserted (open issue #5 vs R)
#   PASS
# 
# Test 5 (PROBE): Poisson and Gamma GLM
#   [poisson] OK -- coef table columns ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df'], 3 rows
#   [gamma] OK -- coef table columns ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df'], 3 rows
# 
# Test 6 (PROBE): model.margins()
#   margins() OK -- list[GLMMargins] len 1
#     elem[0].to_polars() columns: ['term', 'margin', 'se', 'lci', 'uci']
# 
# Test 7 (PROBE): svy-io .dta round-trip
#   I/O module: svy.io (svy.io)
#   wrote .dta via svy.io.write_stata(sample, path)
#   read via svy.io.read_stata(path) -> DataFrame
#   round-trip OK: shape (480, 11), checksum preserved
# 
# Test 8 (PROBE): replicate weights (bootstrap + jackknife + determinism)
#   create_bs_wgts returned type: Sample
#   rep_wgts metadata: RepWeights(method=Bootstrap, prefix='weight', n_reps=20, df=19.0)
#   new columns added to .data: 21 (e.g. ['svy_row_index', 'weight1', 'weight2', 'weight3'])
#   bootstrap replicate count confirmed via rep_wgts.n_reps = 20
#   create_jk_wgts returned type: Sample
#   replication-variance mean deterministic across same rstate: 31157.013319
# 
# Bonus (PROBE): polars replace_strict-on-Enum regression (issue #27060)
#   replace_strict on Enum SUCCEEDED (regression not present): result head ['A', 'B', 'C', 'A']
#   informational PASS (either outcome documents the carried regression)
# 
# === smoke_svy_a.py summary ===
#   HARD PASS 4/4
#   PROBES: 6 succeeded, 0 failed (see output above)
#   Tested against: svy 0.19.0, polars 1.39.3
# === All HARD smoke tests PASSED ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
