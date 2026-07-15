# scripts/scratch/diag_svy_api_a.py
# Follow-up introspection (revision _a). The original diag crashed when dir() on the
# glm namespace hit unfitted-model properties (coefs/predict/stats) that raise ModelError.
#
# INTENT: resolve the REMAINING unknowns the first diag could not reach, so smoke_svy_a.py
#   is written against observed reality: (1) glm.fit signature + what it returns + its
#   to_polars() column names; (2) margins() output structure; (3) svy-io module + function
#   names; (4) actual .to_polars() column names on estimation results (mean/total/by/prop/
#   median/ratio); (5) whether where= accepts a polars expr and rstate= accepts an int;
#   (6) how FPC is specified now that Design has no fpc= (pop_size=?).
# REASONING: signatures alone do not reveal result-frame column names or return types --
#   those require actually calling the methods and inspecting outputs. Everything is wrapped
#   so one failure never aborts the full map.
# ASSUMES: Design(stratum=, wgt=, psu=) + Sample(df, design=) both work (confirmed in the
#   first diag). Synthetic frame identical to the smoke test.

# --- Config ---
import inspect
import importlib
import traceback

import numpy as np
import polars as pl
import svy

print(f"svy {svy.__version__} | polars {pl.__version__}")
print("=" * 70)

# --- Synthetic frame (mirrors smoke test) ---
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
fpc_pop = np.select([stratum == 1, stratum == 2, stratum == 3, stratum == 4],
                    [5000.0, 6000.0, 7000.0, 8000.0])
df = pl.DataFrame({
    "stratum": stratum, "psu": psu, "weight": weight, "income": income, "age": age,
    "gender": gender, "employed": employed, "visit_count": visit_count, "fpc_pop": fpc_pop,
})

design = svy.Design(stratum="stratum", wgt="weight", psu="psu")
sample = svy.Sample(df, design=design)
print("Design(stratum=, wgt=, psu=) + Sample(df, design=) built OK\n")


def dump(label, obj, n_rows=3):
    # Print type; if it has to_polars(), print columns + head; else repr.
    print(f"  {label}: type={type(obj).__name__}")
    if hasattr(obj, "to_polars"):
        try:
            _p = obj.to_polars()
            print(f"    .to_polars() columns: {_p.columns}")
            print(f"    .to_polars() head({n_rows}):")
            for line in str(_p.head(n_rows)).splitlines():
                print(f"      {line}")
        except Exception as e:  # noqa: BLE001
            print(f"    .to_polars() FAILED: {type(e).__name__}: {e}")
    else:
        print(f"    repr: {repr(obj)[:300]}")


# --- (4) Estimation result column names ---
print("--- (4) estimation result frames ---")
for _label, _call in (
    ("mean(income)", lambda: sample.estimation.mean("income")),
    ("total(income)", lambda: sample.estimation.total("income")),
    ("mean batched [income,age]", lambda: sample.estimation.mean(["income", "age"])),
    ("prop batched [employed,gender]", lambda: sample.estimation.prop(["employed", "gender"])),
    ("median batched [income,age]", lambda: sample.estimation.median(["income", "age"])),
    ("ratio batched [income,visit]/age", lambda: sample.estimation.ratio(["income", "visit_count"], "age")),
    ("mean by=stratum", lambda: sample.estimation.mean("income", by="stratum")),
):
    try:
        _r = _call()
        # batched returns a list[Estimate]; single returns Estimate
        if isinstance(_r, list):
            print(f"  {_label}: returns list[{type(_r[0]).__name__}] len={len(_r)}")
            dump(f"{_label}[0]", _r[0])
        else:
            dump(_label, _r)
    except Exception as e:  # noqa: BLE001
        print(f"  {_label} FAILED: {type(e).__name__}: {e}")
print()

# --- (5a) where= with a polars expression ---
print("--- (5a) where= argument forms ---")
for _label, _call in (
    ("where=pl.expr", lambda: sample.estimation.mean("income", where=pl.col("gender") == "Male")),
    ("where=str", lambda: sample.estimation.mean("income", where="gender == 'Male'")),
    ("by+where same col", lambda: sample.estimation.mean("income", by="stratum", where=pl.col("stratum") <= 3)),
):
    try:
        _r = _call()
        _rr = _r[0] if isinstance(_r, list) else _r
        _pp = _rr.to_polars()
        print(f"  {_label}: OK rows={_pp.height} cols={_pp.columns}")
    except Exception as e:  # noqa: BLE001
        print(f"  {_label} FAILED: {type(e).__name__}: {e}")
print()

# --- (6) FPC via pop_size ---
print("--- (6) FPC specification (Design has no fpc=; try pop_size=) ---")
for _label, _kw in (
    ("pop_size=col", {"stratum": "stratum", "wgt": "weight", "psu": "psu", "pop_size": "fpc_pop"}),
):
    try:
        _d = svy.Design(**_kw)
        _s = svy.Sample(df, design=_d)
        _m = _s.estimation.mean("income")
        _mp = (_m[0] if isinstance(_m, list) else _m).to_polars()
        print(f"  {_label}: OK Design built + mean computed; cols={_mp.columns}")
    except Exception as e:  # noqa: BLE001
        print(f"  {_label} FAILED: {type(e).__name__}: {e}")
# Also show what PopSize is
print(f"  svy.PopSize signature: ", end="")
try:
    print(inspect.signature(svy.PopSize))
except Exception as e:  # noqa: BLE001
    print(f"<{e}>")
print()

# --- (1) glm.fit signature + return structure ---
print("--- (1) glm.fit ---")
print(f"  glm.fit signature: {inspect.signature(sample.glm.fit)}")
logit = None
try:
    logit = sample.glm.fit(y="employed", x=["age", "gender"], family="binomial")
    print(f"  fit() returned type: {type(logit).__name__}")
    print(f"  return public attrs: {[a for a in dir(logit) if not a.startswith('_')]}")
    dump("logit.to_polars()", logit, n_rows=6)
    # Inspect coefs property if present
    if hasattr(logit, "coefs"):
        try:
            print(f"  logit.coefs type: {type(logit.coefs).__name__}")
        except Exception as e:  # noqa: BLE001
            print(f"  logit.coefs raised: {type(e).__name__}: {e}")
except Exception as e:  # noqa: BLE001
    print(f"  glm.fit(binomial) FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
print()

# --- (1b) GLM family coverage ---
print("--- (1b) glm family coverage ---")
for _fam, _y in (("gaussian", "income"), ("binomial", "employed"),
                 ("poisson", "visit_count"), ("gamma", "income")):
    try:
        _m = sample.glm.fit(y=_y, x=["age", "gender"], family=_fam)
        _cols = _m.to_polars().columns if hasattr(_m, "to_polars") else "<none>"
        print(f"  family={_fam!r}: OK cols={_cols}")
    except Exception as e:  # noqa: BLE001
        print(f"  family={_fam!r}: FAILED {type(e).__name__}: {e}")
print()

# --- (2) margins() ---
print("--- (2) margins() ---")
if logit is not None:
    try:
        print(f"  margins signature: {inspect.signature(logit.margins)}")
    except Exception as e:  # noqa: BLE001
        print(f"  margins signature unavailable: {e}")
    try:
        _mg = logit.margins()
        dump("margins()", _mg, n_rows=6)
    except Exception as e:  # noqa: BLE001
        print(f"  margins() FAILED: {type(e).__name__}: {e}")
print()

# --- (3) svy-io module + functions ---
print("--- (3) svy-io ---")
_io = getattr(svy, "io", None)
print(f"  svy.io present: {_io is not None}")
if _io is not None:
    print(f"  svy.io.__name__: {getattr(_io, '__name__', '?')}")
    _iopub = [a for a in dir(_io) if not a.startswith("_")]
    print(f"  dir(svy.io) public: {_iopub}")
    for _fn in ("read_stata", "write_stata", "read_dta", "write_dta"):
        _f = getattr(_io, _fn, None)
        if callable(_f):
            try:
                print(f"    svy.io.{_fn}{inspect.signature(_f)}")
            except Exception as e:  # noqa: BLE001
                print(f"    svy.io.{_fn}: sig unavailable ({e})")
# Top-level convenience functions (seen in dir(svy))
print("  top-level svy.* I/O functions:")
for _fn in ("read_stata", "write_stata", "read_dta", "write_dta",
            "read_sas", "read_spss", "create_from_dta"):
    _f = getattr(svy, _fn, None)
    if callable(_f):
        try:
            print(f"    svy.{_fn}{inspect.signature(_f)}")
        except Exception as e:  # noqa: BLE001
            print(f"    svy.{_fn}: sig unavailable ({e})")
# Separate svy_io package?
try:
    _sep = importlib.import_module("svy_io")
    print(f"  separate svy_io importable: {getattr(_sep, '__file__', '?')}")
    print(f"    dir(svy_io) public: {[a for a in dir(_sep) if not a.startswith('_')]}")
except Exception as e:  # noqa: BLE001
    print(f"  separate 'svy_io' import: {type(e).__name__}: {e}")
print()

# --- (5b) replicate weights return structure + rstate=int ---
print("--- (5b) replicate weights ---")
try:
    bs = sample.weighting.create_bs_wgts(n_reps=20, rstate=42)
    print(f"  create_bs_wgts(n_reps=20, rstate=42): OK -> type {type(bs).__name__}")
    print(f"    public attrs: {[a for a in dir(bs) if not a.startswith('_')][:30]}")
    # Try to find replicate columns
    for _acc in ("data", "to_polars"):
        _o = getattr(bs, _acc, None)
        if _o is None:
            continue
        _frame = _o() if callable(_o) else _o
        if isinstance(_frame, pl.DataFrame):
            _reps = [c for c in _frame.columns if "rep" in c.lower()]
            print(f"    via .{_acc}: {_frame.width} cols; replicate-like cols: {len(_reps)} "
                  f"(sample {_reps[:5]})")
            break
    # Does the bs object expose estimation for replication variance?
    if hasattr(bs, "estimation"):
        try:
            _rm = bs.estimation.mean("income", method="replication")
            _rmp = (_rm[0] if isinstance(_rm, list) else _rm).to_polars()
            print(f"    bs.estimation.mean(method='replication'): OK cols={_rmp.columns}")
        except Exception as e:  # noqa: BLE001
            print(f"    bs.estimation.mean(replication) FAILED: {type(e).__name__}: {e}")
except Exception as e:  # noqa: BLE001
    print(f"  create_bs_wgts FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
try:
    jk = sample.weighting.create_jk_wgts()
    print(f"  create_jk_wgts(): OK -> type {type(jk).__name__}")
except Exception as e:  # noqa: BLE001
    print(f"  create_jk_wgts FAILED: {type(e).__name__}: {e}")
print()

print("=" * 70)
print("FOLLOW-UP INTROSPECTION COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 02:29:27
# Command: python3 /daaf/scripts/scratch/diag_svy_api_a.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# svy 0.19.0 | polars 1.39.3
# ======================================================================
# Design(stratum=, wgt=, psu=) + Sample(df, design=) built OK
# 
# --- (4) estimation result frames ---
#   mean(income): type=Estimate
#     .to_polars() columns: ['est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (1, 5)
#       ┌──────────────┬───────────┬──────────────┬──────────────┬──────────┐
#       │ est          ┆ se        ┆ lci          ┆ uci          ┆ cv       │
#       │ ---          ┆ ---       ┆ ---          ┆ ---          ┆ ---      │
#       │ f64          ┆ f64       ┆ f64          ┆ f64          ┆ f64      │
#       ╞══════════════╪═══════════╪══════════════╪══════════════╪══════════╡
#       │ 31157.013319 ┆ 261.03341 ┆ 30612.507167 ┆ 31701.519471 ┆ 0.008378 │
#       └──────────────┴───────────┴──────────────┴──────────────┴──────────┘
#   total(income): type=Estimate
#     .to_polars() columns: ['est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (1, 5)
#       ┌──────────┬───────────────┬──────────┬──────────┬──────────┐
#       │ est      ┆ se            ┆ lci      ┆ uci      ┆ cv       │
#       │ ---      ┆ ---           ┆ ---      ┆ ---      ┆ ---      │
#       │ f64      ┆ f64           ┆ f64      ┆ f64      ┆ f64      │
#       ╞══════════╪═══════════════╪══════════╪══════════╪══════════╡
#       │ 4.0907e7 ┆ 838795.599162 ┆ 3.9158e7 ┆ 4.2657e7 ┆ 0.020505 │
#       └──────────┴───────────────┴──────────┴──────────┴──────────┘
#   mean batched [income,age]: returns list[Estimate] len=2
#   mean batched [income,age][0]: type=Estimate
#     .to_polars() columns: ['est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (1, 5)
#       ┌──────────────┬───────────┬──────────────┬──────────────┬──────────┐
#       │ est          ┆ se        ┆ lci          ┆ uci          ┆ cv       │
#       │ ---          ┆ ---       ┆ ---          ┆ ---          ┆ ---      │
#       │ f64          ┆ f64       ┆ f64          ┆ f64          ┆ f64      │
#       ╞══════════════╪═══════════╪══════════════╪══════════════╪══════════╡
#       │ 31157.013319 ┆ 261.03341 ┆ 30612.507167 ┆ 31701.519471 ┆ 0.008378 │
#       └──────────────┴───────────┴──────────────┴──────────────┴──────────┘
#   prop batched [employed,gender]: returns list[Estimate] len=2
#   prop batched [employed,gender][0]: type=Estimate
#     .to_polars() columns: ['employed', 'est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (2, 6)
#       ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
#       │ employed ┆ est      ┆ se       ┆ lci      ┆ uci      ┆ cv       │
#       │ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---      │
#       │ str      ┆ f64      ┆ f64      ┆ f64      ┆ f64      ┆ f64      │
#       ╞══════════╪══════════╪══════════╪══════════╪══════════╪══════════╡
#       │ 0        ┆ 0.431792 ┆ 0.023447 ┆ 0.383696 ┆ 0.48121  ┆ 0.054302 │
#       │ 1        ┆ 0.568208 ┆ 0.023447 ┆ 0.51879  ┆ 0.616304 ┆ 0.041265 │
#       └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
#   median batched [income,age]: returns list[Estimate] len=2
#   median batched [income,age][0]: type=Estimate
#     .to_polars() columns: ['est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (1, 5)
#       ┌──────────────┬────────────┬──────────────┬──────────────┬──────────┐
#       │ est          ┆ se         ┆ lci          ┆ uci          ┆ cv       │
#       │ ---          ┆ ---        ┆ ---          ┆ ---          ┆ ---      │
#       │ f64          ┆ f64        ┆ f64          ┆ f64          ┆ f64      │
#       ╞══════════════╪════════════╪══════════════╪══════════════╪══════════╡
#       │ 31439.576746 ┆ 330.450926 ┆ 30620.232749 ┆ 31998.849854 ┆ 0.010511 │
#       └──────────────┴────────────┴──────────────┴──────────────┴──────────┘
#   ratio batched [income,visit]/age: returns list[Estimate] len=2
#   ratio batched [income,visit]/age[0]: type=Estimate
#     .to_polars() columns: ['est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (1, 5)
#       ┌────────────┬───────────┬────────────┬────────────┬──────────┐
#       │ est        ┆ se        ┆ lci        ┆ uci        ┆ cv       │
#       │ ---        ┆ ---       ┆ ---        ┆ ---        ┆ ---      │
#       │ f64        ┆ f64       ┆ f64        ┆ f64        ┆ f64      │
#       ╞════════════╪═══════════╪════════════╪════════════╪══════════╡
#       │ 633.699439 ┆ 10.778582 ┆ 611.215711 ┆ 656.183168 ┆ 0.017009 │
#       └────────────┴───────────┴────────────┴────────────┴──────────┘
#   mean by=stratum: type=Estimate
#     .to_polars() columns: ['stratum', 'est', 'se', 'lci', 'uci', 'cv']
#     .to_polars() head(3):
#       shape: (3, 6)
#       ┌─────────┬──────────────┬────────────┬──────────────┬──────────────┬──────────┐
#       │ stratum ┆ est          ┆ se         ┆ lci          ┆ uci          ┆ cv       │
#       │ ---     ┆ ---          ┆ ---        ┆ ---          ┆ ---          ┆ ---      │
#       │ str     ┆ f64          ┆ f64        ┆ f64          ┆ f64          ┆ f64      │
#       ╞═════════╪══════════════╪════════════╪══════════════╪══════════════╪══════════╡
#       │ 1       ┆ 30470.313914 ┆ 236.289583 ┆ 29977.42248  ┆ 30963.205348 ┆ 0.007755 │Traceback (most recent call last):
#   File "/usr/local/lib/python3.12/dist-packages/svy/regression/base.py", line 388, in fit
#     eng_df: pl.DataFrame = df.select(final_selects)
#                            ^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/polars/dataframe/frame.py", line 10341, in select
#     .collect(optimizations=QueryOptFlags._eager())
#      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/polars/_utils/deprecation.py", line 97, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/polars/lazyframe/opt_flags.py", line 326, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/polars/lazyframe/frame.py", line 2464, in collect
#     return wrap_df(ldf.collect(engine, callback))
#                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.InvalidOperationError: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
# 
# During handling of the above exception, another exception occurred:
# 
# Traceback (most recent call last):
#   File "/daaf/scripts/scratch/diag_svy_api_a.py", line 135, in <module>
#     logit = sample.glm.fit(y="employed", x=["age", "gender"], family="binomial")
#             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/svy/regression/base.py", line 390, in fit
#     raise ValueError(f"Failed to prepare data: {e}")
# ValueError: Failed to prepare data: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
# 
#       │ 2       ┆ 30510.226338 ┆ 565.325303 ┆ 29330.978421 ┆ 31689.474255 ┆ 0.018529 │
#       │ 3       ┆ 31336.966138 ┆ 513.058388 ┆ 30266.745093 ┆ 32407.187183 ┆ 0.016372 │
#       └─────────┴──────────────┴────────────┴──────────────┴──────────────┴──────────┘
# 
# --- (5a) where= argument forms ---
#   where=pl.expr: OK rows=1 cols=['est', 'se', 'lci', 'uci', 'cv']
#   where=str FAILED: TypeError: Unsupported expression type: 'str'
#   by+where same col: OK rows=3 cols=['stratum', 'est', 'se', 'lci', 'uci', 'cv']
# 
# --- (6) FPC specification (Design has no fpc=; try pop_size=) ---
#   pop_size=col: OK Design built + mean computed; cols=['est', 'se', 'lci', 'uci', 'cv']
#   svy.PopSize signature: (psu: ForwardRef('str'), ssu: ForwardRef('str | None') = None)
# 
# --- (1) glm.fit ---
#   glm.fit signature: (y: 'str', *, x: 'Sequence[Feature] | None' = None, intercept: 'bool' = True, family: "Literal['gaussian', 'binomial', 'poisson', 'gamma']" = 'gaussian', link: "Literal['identity', 'logit', 'log', 'inverse', 'inverse_squared'] | None" = None, where: 'WhereArg' = None, drop_nulls: 'bool' = True, tol: 'float' = 1e-08, max_iter: 'int' = 100, alpha: 'float' = 0.05) -> 'GLM'
#   glm.fit(binomial) FAILED: ValueError: Failed to prepare data: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
# 
# --- (1b) glm family coverage ---
#   family='gaussian': FAILED ValueError: Failed to prepare data: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
#   family='binomial': FAILED ValueError: Failed to prepare data: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
#   family='poisson': FAILED ValueError: Failed to prepare data: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
#   family='gamma': FAILED ValueError: Failed to prepare data: conversion from `str` to `f64` failed in column 'gender' for 480 out of 480 values: ["Female", "Male", … "Female"]
# 
# Did not show all failed cases as there were too many.
# 
# This error occurred in the following expression:
# 	col("gender").strict_cast(Float64)
# 
# 
# --- (2) margins() ---
# 
# --- (3) svy-io ---
#   svy.io present: True
#   svy.io.__name__: svy.io
#   dir(svy.io) public: ['base', 'create_from_csv', 'create_from_dta', 'create_from_parquet', 'create_from_sas', 'create_from_sav', 'create_from_spss', 'create_from_stata', 'read_csv', 'read_dta', 'read_dta_with_labels', 'read_parquet', 'read_sas', 'read_sas_with_labels', 'read_sav', 'read_sav_with_labels', 'read_spss', 'read_spss_with_labels', 'read_stata', 'read_stata_with_labels', 'scan_csv', 'scan_parquet', 'write_csv', 'write_dta', 'write_parquet', 'write_sas', 'write_sav', 'write_spss', 'write_stata']
#     svy.io.read_stata(path: 'str | Path', *, columns: 'ColumnsArg' = None, **kwargs) -> 'pl.DataFrame'
#     svy.io.write_stata(sample: 'Sample', path: 'str | Path', **kwargs) -> 'None'
#     svy.io.read_dta(path: 'str | Path', *, columns: 'ColumnsArg' = None, **kwargs) -> 'pl.DataFrame'
#     svy.io.write_dta(sample: 'Sample', path: 'str | Path', **kwargs) -> 'None'
#   top-level svy.* I/O functions:
#     svy.read_stata(path: 'str | Path', *, columns: 'ColumnsArg' = None, **kwargs) -> 'pl.DataFrame'
#     svy.write_stata(sample: 'Sample', path: 'str | Path', **kwargs) -> 'None'
#     svy.read_dta(path: 'str | Path', *, columns: 'ColumnsArg' = None, **kwargs) -> 'pl.DataFrame'
#     svy.write_dta(sample: 'Sample', path: 'str | Path', **kwargs) -> 'None'
#     svy.read_sas(path: 'str | Path', *, columns: 'ColumnsArg' = None, **kwargs) -> 'pl.DataFrame'
#     svy.read_spss(path: 'str | Path', *, columns: 'ColumnsArg' = None, **kwargs) -> 'pl.DataFrame'
#     svy.create_from_dta(path: 'str | Path', name: 'str | None' = None, **kwargs) -> 'Sample'
#   separate svy_io importable: /usr/local/lib/python3.12/dist-packages/svy_io/__init__.py
#     dir(svy_io) public: ['Labelled', 'LabelledSPSS', 'MissingRule', 'SvyMetadata', 'TaggedNA', 'ValueLabels', 'VarMeta', 'apply_value_labels', 'as_factor', 'factor', 'format_tagged_na', 'get_column_labels', 'get_user_missing_for_column', 'get_value_labels_for_column', 'helpers', 'is_labelled', 'is_labelled_spss', 'is_tagged_na', 'labelled', 'labelled_spss', 'metadata', 'na_tag', 'print_tagged_na', 'read_dta', 'read_por', 'read_sas', 'read_sas_arrow', 'read_sav', 'read_spss', 'read_stata', 'read_xpt', 'sas', 'spss', 'stata', 'svyreadstat_rs', 'tagged_na', 'write_dta', 'write_sav', 'write_stata', 'write_xpt', 'zap', 'zap_empty', 'zap_label', 'zap_labels', 'zap_missing', 'zap_widths']
# 
# --- (5b) replicate weights ---
#   create_bs_wgts(n_reps=20, rstate=42): OK -> type Sample
#     public attrs: ['PRINT_WIDTH', 'categorical', 'clone', 'data', 'deff_w', 'describe', 'design', 'dtypes', 'estimation', 'fpc', 'glm', 'labels', 'meta', 'n_columns', 'n_psus', 'n_records', 'n_strata', 'psus', 'rep_wgts', 'resolve_labels', 'sampling', 'set_categories', 'set_data', 'set_default_print_width', 'set_design', 'set_missing', 'set_na_as_level', 'set_print_width', 'set_type', 'set_value_labels']
#     via .data: 30 cols; replicate-like cols: 0 (sample [])
#     bs.estimation.mean(method='replication'): OK cols=['est', 'se', 'lci', 'uci', 'cv']
#   create_jk_wgts(): OK -> type Sample
# 
# ======================================================================
# FOLLOW-UP INTROSPECTION COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
