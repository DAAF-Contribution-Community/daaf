# scripts/scratch/diag_svy_api_b.py
# Third-pass introspection (revision _b). diag_a revealed glm.fit rejects raw string
# predictors (strict_cast str->f64 on 'gender'); categorical predictors must be wrapped
# in svy.Cat(). This pass captures the three surfaces diag_a could not reach because of
# that failure.
#
# INTENT: capture (1) glm.fit(...) coef-table column names + return structure using
#   svy.Cat() for the string predictor; (2) margins() output columns; (3) the actual
#   column naming of create_bs_wgts()'s returned Sample so the smoke test's replicate-weight
#   probe can count replicate columns correctly.
# REASONING: these three are the last unknowns needed to author smoke_svy_a.py against
#   observed reality. Everything wrapped so one failure never aborts the map.
# ASSUMES: svy.Cat("gender") is the correct categorical wrapper (confirmed present in
#   dir(svy); Cat.__init__(name, ref=None)).

import inspect
import numpy as np
import polars as pl
import svy

print(f"svy {svy.__version__} | polars {pl.__version__}")

rng = np.random.default_rng(42)
n_strata, n_psu, n_obs = 4, 6, 20
n = n_strata * n_psu * n_obs
stratum = np.repeat(np.arange(1, n_strata + 1), n_psu * n_obs)
psu = np.repeat(np.arange(1, n_strata * n_psu + 1), n_obs)
weight = rng.uniform(0.5, 5.0, size=n)
income = 30000.0 + 500.0 * stratum + rng.normal(0.0, 5000.0, size=n)
age = rng.integers(18, 81, size=n).astype(float)
gender = rng.choice(["Male", "Female"], size=n)
_p = 1.0 / (1.0 + np.exp(-(-1.0 + 0.02 * age + 0.5 * (gender == "Male"))))
employed = rng.binomial(1, _p).astype(float)
visit_count = rng.poisson(np.exp(0.5 + 0.01 * age / 10.0)).astype(float)
df = pl.DataFrame({
    "stratum": stratum, "psu": psu, "weight": weight, "income": income, "age": age,
    "gender": gender, "employed": employed, "visit_count": visit_count,
})
design = svy.Design(stratum="stratum", wgt="weight", psu="psu")
sample = svy.Sample(df, design=design)

# --- (1) glm.fit with svy.Cat for the string predictor ---
print("\n--- (1) glm.fit(y=employed, x=[age, Cat(gender)], family=binomial) ---")
logit = None
try:
    logit = sample.glm.fit(y="employed", x=["age", svy.Cat("gender")], family="binomial")
    print(f"  OK -> return type {type(logit).__name__}")
    lp = logit.to_polars()
    print(f"  to_polars() columns: {lp.columns}")
    print(f"  to_polars() rows: {lp.height}")
    for line in str(lp).splitlines():
        print(f"    {line}")
except Exception as e:  # noqa: BLE001
    print(f"  FAILED: {type(e).__name__}: {e}")

# --- (1b) family coverage with Cat ---
print("\n--- (1b) family coverage (x=[age, Cat(gender)]) ---")
for _fam, _y in (("gaussian", "income"), ("binomial", "employed"),
                 ("poisson", "visit_count"), ("gamma", "income")):
    try:
        _m = sample.glm.fit(y=_y, x=["age", svy.Cat("gender")], family=_fam)
        print(f"  family={_fam!r}: OK cols={_m.to_polars().columns} rows={_m.to_polars().height}")
    except Exception as e:  # noqa: BLE001
        print(f"  family={_fam!r}: FAILED {type(e).__name__}: {e}")

# --- (1c) does plain all-numeric x work without Cat? ---
print("\n--- (1c) glm.fit with all-numeric x (no Cat needed) ---")
try:
    _m = sample.glm.fit(y="employed", x=["age"], family="binomial")
    print(f"  x=[age] only: OK cols={_m.to_polars().columns}")
except Exception as e:  # noqa: BLE001
    print(f"  x=[age] only: FAILED {type(e).__name__}: {e}")

# --- (2) margins() ---
print("\n--- (2) margins() on the logistic model ---")
if logit is not None:
    try:
        print(f"  margins signature: {inspect.signature(logit.margins)}")
    except Exception as e:  # noqa: BLE001
        print(f"  sig unavailable: {e}")
    try:
        mg = logit.margins()
        print(f"  margins() return type: {type(mg).__name__}")
        if hasattr(mg, "to_polars"):
            mp = mg.to_polars()
            print(f"  margins to_polars columns: {mp.columns} rows={mp.height}")
            for line in str(mp).splitlines():
                print(f"    {line}")
        else:
            print(f"  repr: {repr(mg)[:300]}")
    except Exception as e:  # noqa: BLE001
        print(f"  margins() FAILED: {type(e).__name__}: {e}")

# --- (3) create_bs_wgts return Sample column naming ---
print("\n--- (3) create_bs_wgts column naming ---")
try:
    base_cols = set(df.columns)
    bs = sample.weighting.create_bs_wgts(n_reps=20, rstate=42)
    bs_data = bs.data
    new_cols = [c for c in bs_data.columns if c not in base_cols]
    print(f"  bs return type: {type(bs).__name__}")
    print(f"  base cols: {len(base_cols)}; bs.data cols: {bs_data.width}; new cols: {len(new_cols)}")
    print(f"  new column names (first 25): {new_cols[:25]}")
    # bs.rep_wgts attribute?
    rw = getattr(bs, "rep_wgts", None)
    print(f"  bs.rep_wgts type: {type(rw).__name__}; repr: {repr(rw)[:200]}")
    # n_reps discoverable?
    for _attr in ("n_reps", "n_replicates", "reps"):
        if rw is not None and hasattr(rw, _attr):
            print(f"    rep_wgts.{_attr} = {getattr(rw, _attr)}")
except Exception as e:  # noqa: BLE001
    import traceback
    print(f"  FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\nCOMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 02:30:41
# Command: python3 /daaf/scripts/scratch/diag_svy_api_b.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# svy 0.19.0 | polars 1.39.3
# 
# --- (1) glm.fit(y=employed, x=[age, Cat(gender)], family=binomial) ---
#   OK -> return type GLM
#   to_polars() columns: ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']
#   to_polars() rows: 3
#     shape: (3, 8)
#     ┌─────────────┬───────────┬──────────┬───────────┬───────────┬───────────┬──────────┬─────┐
#     │ term        ┆ estimate  ┆ std_err  ┆ conf_low  ┆ conf_high ┆ statistic ┆ p_value  ┆ df  │
#     │ ---         ┆ ---       ┆ ---      ┆ ---       ┆ ---       ┆ ---       ┆ ---      ┆ --- │
#     │ str         ┆ f64       ┆ f64      ┆ f64       ┆ f64       ┆ f64       ┆ f64      ┆ i64 │
#     ╞═════════════╪═══════════╪══════════╪═══════════╪═══════════╪═══════════╪══════════╪═════╡
#     │ _intercept_ ┆ -0.551967 ┆ 0.248351 ┆ -1.073733 ┆ -0.030201 ┆ -2.222527 ┆ 0.039301 ┆ 18  │
#     │ age         ┆ 0.010673  ┆ 0.003952 ┆ 0.00237   ┆ 0.018975  ┆ 2.700641  ┆ 0.014632 ┆ 18  │
#     │ gender_Male ┆ 0.6325    ┆ 0.211176 ┆ 0.188836  ┆ 1.076163  ┆ 2.995137  ┆ 0.007767 ┆ 18  │
#     └─────────────┴───────────┴──────────┴───────────┴───────────┴───────────┴──────────┴─────┘
# 
# --- (1b) family coverage (x=[age, Cat(gender)]) ---
#   family='gaussian': OK cols=['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df'] rows=3
#   family='binomial': OK cols=['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df'] rows=3
#   family='poisson': OK cols=['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df'] rows=3
#   family='gamma': OK cols=['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df'] rows=3
# 
# --- (1c) glm.fit with all-numeric x (no Cat needed) ---
#   x=[age] only: OK cols=['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']
# 
# --- (2) margins() on the logistic model ---
#   margins signature: (at: 'dict[str, list] | None' = None, variables: 'list[str] | None' = None, alpha: 'float' = 0.05) -> "'GLMMargins | list[GLMMargins]'"
#   margins() return type: list
#   repr: [GLMMargins(term='age', 95% CI, type=ame)]
# 
# --- (3) create_bs_wgts column naming ---
#   bs return type: Sample
#   base cols: 8; bs.data cols: 29; new cols: 21
#   new column names (first 25): ['svy_row_index', 'weight1', 'weight2', 'weight3', 'weight4', 'weight5', 'weight6', 'weight7', 'weight8', 'weight9', 'weight10', 'weight11', 'weight12', 'weight13', 'weight14', 'weight15', 'weight16', 'weight17', 'weight18', 'weight19', 'weight20']
#   bs.rep_wgts type: RepWeights; repr: RepWeights(method=Bootstrap, prefix='weight', n_reps=20, df=19.0)
#     rep_wgts.n_reps = 20
# 
# COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
