# scripts/scratch/xval_svy_r_01_catintrospect.py
# INTENT: introspect svy 0.19.0's `sample.categorical` accessor before exercising it,
#   mirroring the dir()+signature pattern from diag_svy_api_a.py. Gap 3 (categorical
#   analysis) is completely unverified, so we must discover the real surface first.
# REASONING: signatures + dir() reveal what tabulation / chi-square methods exist and
#   their call conventions; calling blindly would produce uninformative errors.
# ASSUMES: Design(stratum=, wgt=, psu=) + Sample(df, design=) build (confirmed in the
#   smoke test); synthetic frame identical to smoke_svy_a.py.

# --- Config ---
import inspect
import traceback

import numpy as np
import polars as pl
import svy

print(f"svy {svy.__version__} | polars {pl.__version__}")
print("=" * 70)

# --- Synthetic frame (mirrors smoke test exactly: seeded rng(42), 480 rows) ---
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
print("Design + Sample built OK\n")

# --- Introspect sample.categorical ---
print("--- sample.categorical accessor ---")
cat_acc = getattr(sample, "categorical", None)
print(f"  present: {cat_acc is not None}")
if cat_acc is not None:
    print(f"  type: {type(cat_acc).__name__}")
    pub = [a for a in dir(cat_acc) if not a.startswith("_")]
    print(f"  public methods/attrs: {pub}")
    for m in pub:
        try:
            member = getattr(cat_acc, m)
            if callable(member):
                print(f"    .{m}{inspect.signature(member)}")
        except (TypeError, ValueError) as e:
            print(f"    .{m}: signature unavailable ({e})")
        except Exception as e:  # noqa: BLE001
            print(f"    .{m}: raised {type(e).__name__}: {e}")
print()

# --- Try common tabulation / chi-square method names by calling them ---
print("--- exercising candidate categorical methods ---")
candidates = [
    ("tab(gender)", lambda: cat_acc.tab("gender")),
    ("tab(gender, employed)", lambda: cat_acc.tab("gender", "employed")),
    ("table(gender)", lambda: cat_acc.table("gender")),
    ("crosstab(gender, employed)", lambda: cat_acc.crosstab("gender", "employed")),
    ("chisq(gender, employed)", lambda: cat_acc.chisq("gender", "employed")),
    ("chi2(gender, employed)", lambda: cat_acc.chi2("gender", "employed")),
    ("test(gender, employed)", lambda: cat_acc.test("gender", "employed")),
    ("oneway(gender)", lambda: cat_acc.oneway("gender")),
    ("twoway(gender, employed)", lambda: cat_acc.twoway("gender", "employed")),
]
for label, call in candidates:
    if cat_acc is None:
        break
    try:
        r = call()
        rt = type(r).__name__
        info = ""
        if hasattr(r, "to_polars"):
            try:
                info = f" -> to_polars cols {r.to_polars().columns}"
            except Exception as e:  # noqa: BLE001
                info = f" -> to_polars FAILED {type(e).__name__}: {e}"
        elif hasattr(r, "columns"):
            info = f" cols {r.columns}"
        else:
            info = f" repr {repr(r)[:160]}"
        # also dump public attrs for objects to find nested chi-square stats
        attrs = [a for a in dir(r) if not a.startswith("_")]
        print(f"  {label}: OK type={rt}{info}")
        print(f"    public attrs: {attrs}")
    except AttributeError as e:
        print(f"  {label}: NO SUCH METHOD ({e})")
    except Exception as e:  # noqa: BLE001
        print(f"  {label}: FAILED {type(e).__name__}: {e}")
print()

print("=" * 70)
print("CATEGORICAL INTROSPECTION COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 11:51:01
# Command: python3 /daaf/scripts/scratch/xval_svy_r_01_catintrospect.py
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# svy 0.19.0 | polars 1.39.3
# ======================================================================
# Design + Sample built OK
# 
# --- sample.categorical accessor ---
#   present: True
#   type: Categorical
#   public methods/attrs: ['ranktest', 'tabulate', 'ttest']
#     .ranktest(y: 'str', *, group: 'str', method: "Literal['kruskal-wallis', 'vander-waerden', 'median'] | None" = None, score_fn: 'Callable[[np.ndarray, float], np.ndarray] | None' = None, by: 'str | None' = None, where: 'WhereArg' = None, alpha: 'float' = 0.05, alternative: "Literal['two-sided', 'less', 'greater']" = 'two-sided', drop_nulls: 'bool' = False) -> 'RankTestTwoSample | RankTestKSample | list[RankTestTwoSample] | list[RankTestKSample]'
#     .tabulate(rowvar: 'str', colvar: 'str | None' = None, *, units: "Literal['proportion', 'percent', 'count']" = 'proportion', count_total: 'float | int | None' = None, alpha: 'float' = 0.05, drop_nulls: 'bool' = False, use_labels: 'bool | None' = None) -> 'Table'
#     .ttest(y: 'str', *, mean_h0: 'Number' = 0, group: 'str | None' = None, y_pair: 'str | None' = None, by: 'str | None' = None, where: 'WhereArg' = None, alpha: 'float' = 0.05, alternative: "Literal['two-sided', 'less', 'greater']" = 'two-sided', drop_nulls: 'bool' = False) -> 'TTestOneGroup | TTestTwoGroups | TTestByResult'
# 
# --- exercising candidate categorical methods ---
#   tab(gender): NO SUCH METHOD ('Categorical' object has no attribute 'tab')
#   tab(gender, employed): NO SUCH METHOD ('Categorical' object has no attribute 'tab')
#   table(gender): NO SUCH METHOD ('Categorical' object has no attribute 'table')
#   crosstab(gender, employed): NO SUCH METHOD ('Categorical' object has no attribute 'crosstab')
#   chisq(gender, employed): NO SUCH METHOD ('Categorical' object has no attribute 'chisq')
#   chi2(gender, employed): NO SUCH METHOD ('Categorical' object has no attribute 'chi2')
#   test(gender, employed): NO SUCH METHOD ('Categorical' object has no attribute 'test')
#   oneway(gender): NO SUCH METHOD ('Categorical' object has no attribute 'oneway')
#   twoway(gender, employed): NO SUCH METHOD ('Categorical' object has no attribute 'twoway')
# 
# ======================================================================
# CATEGORICAL INTROSPECTION COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
