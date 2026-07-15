# scripts/scratch/xval_svy_r_02_tableintrospect.py
# INTENT: introspect the `Table` object returned by sample.categorical.tabulate() to find
#   where (if anywhere) a Rao-Scott chi-square / F statistic lives, for the two-way case.
# REASONING: the Categorical accessor has no separately-named chisq method; the design-based
#   independence test (if present) is most likely an attribute/method on the Table returned
#   by a two-way tabulate(). Blind attribute access would be noisy; dir() + targeted probing
#   maps it precisely.
# ASSUMES: synthetic frame identical to smoke_svy_a.py; tabulate(rowvar, colvar) yields the
#   two-way Table.

# --- Config ---
import inspect

import numpy as np
import polars as pl
import svy

print(f"svy {svy.__version__} | polars {pl.__version__}")
print("=" * 70)

# --- Synthetic frame (identical seeding) ---
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
cat_acc = sample.categorical


def dump_table(label, tbl):
    print(f"  {label}: type={type(tbl).__name__}")
    attrs = [a for a in dir(tbl) if not a.startswith("_")]
    print(f"    public attrs: {attrs}")
    if hasattr(tbl, "to_polars"):
        try:
            print(f"    to_polars() cols: {tbl.to_polars().columns}")
            print("    to_polars() head:")
            for line in str(tbl.to_polars().head(8)).splitlines():
                print(f"      {line}")
        except Exception as e:  # noqa: BLE001
            print(f"    to_polars FAILED {type(e).__name__}: {e}")
    # Probe each non-callable attr for chi-square-ish content
    for a in attrs:
        low = a.lower()
        if any(k in low for k in ("chi", "test", "stat", "wald", "rao", "f_", "pval", "p_val", "dof", "df")):
            try:
                v = getattr(tbl, a)
                if callable(v):
                    try:
                        print(f"    .{a} signature: {inspect.signature(v)}")
                    except Exception as e:  # noqa: BLE001
                        print(f"    .{a} callable (sig unavailable: {e})")
                else:
                    print(f"    .{a} = {repr(v)[:200]}")
            except Exception as e:  # noqa: BLE001
                print(f"    .{a} raised {type(e).__name__}: {e}")


# --- one-way tabulate ---
print("--- one-way tabulate(gender) ---")
t1 = cat_acc.tabulate("gender")
dump_table("tabulate(gender)", t1)
print()

print("--- one-way tabulate(gender, units='count') ---")
t1c = cat_acc.tabulate("gender", units="count")
dump_table("tabulate(gender, count)", t1c)
print()

# --- two-way tabulate ---
print("--- two-way tabulate(gender, employed) ---")
t2 = cat_acc.tabulate("gender", "employed")
dump_table("tabulate(gender, employed)", t2)
print()

# --- If a test method exists, call it and dump the result ---
print("--- probing two-way Table for a callable test/statistic ---")
for meth in ("test", "chisq", "chi2", "wald_test", "rao_scott", "independence"):
    fn = getattr(t2, meth, None)
    if callable(fn):
        try:
            res = fn()
            print(f"  t2.{meth}() OK -> type {type(res).__name__}; "
                  f"attrs {[a for a in dir(res) if not a.startswith('_')]}")
            if hasattr(res, "to_polars"):
                print(f"    to_polars cols {res.to_polars().columns}")
                for line in str(res.to_polars()).splitlines():
                    print(f"      {line}")
            else:
                print(f"    repr {repr(res)[:300]}")
        except Exception as e:  # noqa: BLE001
            print(f"  t2.{meth}() FAILED {type(e).__name__}: {e}")
    else:
        print(f"  t2.{meth}: not a callable attribute")
print()

# Also print full repr of the two-way Table (statistics often shown in __repr__/__str__)
print("--- str(two-way Table) ---")
print(str(t2))
print()

print("=" * 70)
print("TABLE INTROSPECTION COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 11:51:44
# Command: python3 /daaf/scripts/scratch/xval_svy_r_02_tableintrospect.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# svy 0.19.0 | polars 1.39.3
# ======================================================================
# --- one-way tabulate(gender) ---
#   tabulate(gender): type=Table
#     public attrs: ['DECIMALS', 'PRINT_WIDTH', 'USE_LABELS', 'add_estimate', 'add_param', 'alpha', 'colvals', 'colvar', 'crosstab', 'decimals', 'estimates', 'extend_estimates', 'extend_params', 'fill_missing', 'is_crosstab', 'one_way', 'print_width', 'rowvals', 'rowvar', 'set_decimals', 'set_default_print_width', 'set_default_use_labels', 'set_levels', 'set_stats', 'show', 'stats', 'style', 'to_dataframe', 'to_dict', 'to_polars', 'to_records', 'two_way', 'type', 'update', 'use_labels']
#     to_polars() cols: ['gender', 'est', 'se', 'lci', 'uci', 'table_type', 'alpha']
#     to_polars() head:
#       shape: (2, 7)
#       ┌────────┬──────────┬──────────┬──────────┬──────────┬────────────┬───────┐
#       │ gender ┆ est      ┆ se       ┆ lci      ┆ uci      ┆ table_type ┆ alpha │
#       │ ---    ┆ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---        ┆ ---   │
#       │ str    ┆ f64      ┆ f64      ┆ f64      ┆ f64      ┆ str        ┆ f64   │
#       ╞════════╪══════════╪══════════╪══════════╪══════════╪════════════╪═══════╡
#       │ Female ┆ 0.507984 ┆ 0.019871 ┆ 0.466573 ┆ 0.549286 ┆ One-Way    ┆ 0.05  │
#       │ Male   ┆ 0.492016 ┆ 0.019871 ┆ 0.450714 ┆ 0.533427 ┆ One-Way    ┆ 0.05  │
#       └────────┴──────────┴──────────┴──────────┴──────────┴────────────┴───────┘
#     .set_stats signature: (stats: 'TableStats | None') -> 'Self'
#     .stats = None
# 
# --- one-way tabulate(gender, units='count') ---
#   tabulate(gender, count): type=Table
#     public attrs: ['DECIMALS', 'PRINT_WIDTH', 'USE_LABELS', 'add_estimate', 'add_param', 'alpha', 'colvals', 'colvar', 'crosstab', 'decimals', 'estimates', 'extend_estimates', 'extend_params', 'fill_missing', 'is_crosstab', 'one_way', 'print_width', 'rowvals', 'rowvar', 'set_decimals', 'set_default_print_width', 'set_default_use_labels', 'set_levels', 'set_stats', 'show', 'stats', 'style', 'to_dataframe', 'to_dict', 'to_polars', 'to_records', 'two_way', 'type', 'update', 'use_labels']
#     to_polars() cols: ['gender', 'est', 'se', 'lci', 'uci', 'table_type', 'alpha']
#     to_polars() head:
#       shape: (2, 7)
#       ┌────────┬────────────┬───────────┬────────────┬────────────┬────────────┬───────┐
#       │ gender ┆ est        ┆ se        ┆ lci        ┆ uci        ┆ table_type ┆ alpha │
#       │ ---    ┆ ---        ┆ ---       ┆ ---        ┆ ---        ┆ ---        ┆ ---   │
#       │ str    ┆ f64        ┆ f64       ┆ f64        ┆ f64        ┆ str        ┆ f64   │
#       ╞════════╪════════════╪═══════════╪════════════╪════════════╪════════════╪═══════╡
#       │ Female ┆ 666.951474 ┆ 31.493158 ┆ 605.226018 ┆ 728.676929 ┆ One-Way    ┆ 0.05  │
#       │ Male   ┆ 645.985746 ┆ 25.760401 ┆ 595.496287 ┆ 696.475204 ┆ One-Way    ┆ 0.05  │
#       └────────┴────────────┴───────────┴────────────┴────────────┴────────────┴───────┘
#     .set_stats signature: (stats: 'TableStats | None') -> 'Self'
#     .stats = None
# 
# --- two-way tabulate(gender, employed) ---
#   tabulate(gender, employed): type=Table
#     public attrs: ['DECIMALS', 'PRINT_WIDTH', 'USE_LABELS', 'add_estimate', 'add_param', 'alpha', 'colvals', 'colvar', 'crosstab', 'decimals', 'estimates', 'extend_estimates', 'extend_params', 'fill_missing', 'is_crosstab', 'one_way', 'print_width', 'rowvals', 'rowvar', 'set_decimals', 'set_default_print_width', 'set_default_use_labels', 'set_levels', 'set_stats', 'show', 'stats', 'style', 'to_dataframe', 'to_dict', 'to_polars', 'to_records', 'two_way', 'type', 'update', 'use_labels']
#     to_polars() cols: ['gender', 'employed', 'est', 'se', 'lci', 'uci', 'table_type', 'alpha']
#     to_polars() head:
#       shape: (4, 8)
#       ┌────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────────┬───────┐
#       │ gender ┆ employed ┆ est      ┆ se       ┆ lci      ┆ uci      ┆ table_type ┆ alpha │
#       │ ---    ┆ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---        ┆ ---   │
#       │ str    ┆ str      ┆ f64      ┆ f64      ┆ f64      ┆ f64      ┆ str        ┆ f64   │
#       ╞════════╪══════════╪══════════╪══════════╪══════════╪══════════╪════════════╪═══════╡
#       │ Female ┆ 0        ┆ 0.257386 ┆ 0.023113 ┆ 0.212178 ┆ 0.308454 ┆ Two-Way    ┆ 0.05  │
#       │ Female ┆ 1        ┆ 0.250599 ┆ 0.019614 ┆ 0.211938 ┆ 0.293684 ┆ Two-Way    ┆ 0.05  │
#       │ Male   ┆ 0        ┆ 0.174407 ┆ 0.013126 ┆ 0.148696 ┆ 0.203501 ┆ Two-Way    ┆ 0.05  │
#       │ Male   ┆ 1        ┆ 0.317609 ┆ 0.022696 ┆ 0.272253 ┆ 0.366713 ┆ Two-Way    ┆ 0.05  │
#       └────────┴──────────┴──────────┴──────────┴──────────┴──────────┴────────────┴───────┘
#     .set_stats signature: (stats: 'TableStats | None') -> 'Self'
#     .stats = TableStats(chisq=ChiSquare(df=1, value=11.327947321732701, p_value=0.0026899833581283117), f=FDist(df_num=1.0, df_den=20.0, value=9.006654687144357, p_value=0.007058257810822588))
# 
# --- probing two-way Table for a callable test/statistic ---
#   t2.test: not a callable attribute
#   t2.chisq: not a callable attribute
#   t2.chi2: not a callable attribute
#   t2.wald_test: not a callable attribute
#   t2.rao_scott: not a callable attribute
#   t2.independence: not a callable attribute
# 
# --- str(two-way Table) ---
# Table: gender × employed
# 
#   Row     Col  Estimate  Std Err       CV    Lower    Upper
#   ------  ---  --------  -------  -------  -------  -------
#   Female  0     0.25739  0.02311  0.08980  0.21218  0.30845
#   Female  1     0.25060  0.01961  0.07827  0.21194  0.29368
#   Male    0     0.17441  0.01313  0.07526  0.14870  0.20350
#   Male    1     0.31761  0.02270  0.07146  0.27225  0.36671
# 
# ======================================================================
# TABLE INTROSPECTION COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
