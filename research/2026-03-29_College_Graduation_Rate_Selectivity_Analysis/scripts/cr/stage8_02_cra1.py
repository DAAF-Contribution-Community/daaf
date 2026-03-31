#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 2 (crosstab-selectivity-pell)

Reviewed script: scripts/stage8_analysis/02_crosstab-selectivity-pell_a.py
Output files: output/analysis/2026-03-29_crosstab_selectivity_pell.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations (6 columns: band, quintile, mean, median, N, pell_gap)
2. Row count = 20 (4 bands x 5 quintiles)
3. No suspicious distributions
4. Grad rates in [0, 100]
5. No nulls in critical columns (selectivity_band, pell_quintile, mean_grad_rate, N)
--- Script-Specific Checks (Five Lenses) ---
6. [Counterfactual] Cell N values sum to input filtered row count (1,887)
7. [Semantic] Pell gap direction matches expected Q1-Q5 definition
8. [Boundary] Sparse cell identification matches cells with N < 10
9. [Absence] Verify no band x quintile combination is missing
10. [Downstream] pell_gap column is consistent within each band (all 5 rows same value)
--- Spot-Checks ---
11. Recalculate Open/Less Selective x Q1 mean from source data
12. Verify HS band N=66 total across its 5 quintile cells
13. Cross-check that pell_gap for Open/Less Selective = Q1_mean - Q5_mean
14. Verify Moderately Selective median grad rate is within plausible range vs mean
15. Check that all BAND_ORDER bands are in the output and no extra bands exist
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_pell.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

EXPECTED_COLUMNS = ["selectivity_band", "pell_quintile", "mean_grad_rate", "median_grad_rate", "N", "pell_gap"]
EXPECTED_ROWS = 20  # 4 bands x 5 quintiles
CRITICAL_COLUMNS = ["selectivity_band", "pell_quintile", "mean_grad_rate", "N"]
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]
PELL_QUINTILE_ORDER = ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"]
SPARSE_THRESHOLD = 10

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 2 (crosstab-selectivity-pell)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load source data for cross-validation
df_source = pl.read_parquet(INPUT_FILE)
print(f"Loaded source: {df_source.shape[0]:,} rows x {df_source.shape[1]} cols")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count} (expected {EXPECTED_ROWS})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 5:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Grad rates in [0, 100] ---
min_mean = df["mean_grad_rate"].min()
max_mean = df["mean_grad_rate"].max()
min_median = df["median_grad_rate"].min()
max_median = df["median_grad_rate"].max()
range_ok = min_mean >= 0 and max_mean <= 100 and min_median >= 0 and max_median <= 100
print(f"[{'PASS' if range_ok else 'FAIL'}] Grad rates in [0, 100]: mean=[{min_mean:.1f}, {max_mean:.1f}], median=[{min_median:.1f}, {max_median:.1f}]")

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# --- Check 6: [Counterfactual] Cell N values sum to filtered input row count ---
# INTENT: The sum of all cell N values should equal the number of rows in source
# that have non-null selectivity_band, pell_quintile, and completion_rate_150pct.
total_n = df["N"].sum()
source_complete = df_source.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("pell_quintile").is_not_null()
    & pl.col("completion_rate_150pct").is_not_null()
).shape[0]
n_sum_ok = total_n == source_complete
print(f"[{'PASS' if n_sum_ok else 'FAIL'}] Cell N sum ({total_n}) == source filtered rows ({source_complete})")

# --- Check 7: [Semantic] Pell gap direction ---
# INTENT: Pell gap = Q1 mean - Q5 mean. For each band, verify this is actually computed
# correctly by re-deriving from the cross-tab values.
gap_issues = []
for band in BAND_ORDER:
    band_rows = df.filter(pl.col("selectivity_band") == band)
    q1_row = band_rows.filter(pl.col("pell_quintile") == "Q1 (Lowest)")
    q5_row = band_rows.filter(pl.col("pell_quintile") == "Q5 (Highest)")
    if q1_row.shape[0] > 0 and q5_row.shape[0] > 0:
        q1_mean = q1_row["mean_grad_rate"][0]
        q5_mean = q5_row["mean_grad_rate"][0]
        expected_gap = q1_mean - q5_mean
        actual_gap = band_rows["pell_gap"][0]
        if actual_gap is not None and abs(expected_gap - actual_gap) > 0.01:
            gap_issues.append(f"{band}: expected gap {expected_gap:.2f}, got {actual_gap:.2f}")
gap_ok = len(gap_issues) == 0
print(f"[{'PASS' if gap_ok else 'FAIL'}] Pell gap direction: ", end="")
print("All gaps match Q1-Q5 definition" if gap_ok else "; ".join(gap_issues))

# --- Check 8: [Boundary] Sparse cell identification ---
# INTENT: Verify which cells have N < 10. Cross-check against execution log claims.
sparse_cells = df.filter(pl.col("N") < SPARSE_THRESHOLD)
n_sparse = sparse_cells.shape[0]
print(f"[{'PASS' if n_sparse <= 5 else 'WARN'}] Sparse cells (N < {SPARSE_THRESHOLD}): {n_sparse}")
for row in sparse_cells.iter_rows(named=True):
    print(f"    {row['selectivity_band']} x {row['pell_quintile']}: N={row['N']}")

# --- Check 9: [Absence] Verify complete 4x5 grid ---
bands_in_output = sorted(df["selectivity_band"].unique().to_list())
quintiles_in_output = sorted(df["pell_quintile"].unique().to_list())
expected_bands = sorted(BAND_ORDER)
expected_quintiles = sorted(PELL_QUINTILE_ORDER)
bands_ok = bands_in_output == expected_bands
quintiles_ok = quintiles_in_output == expected_quintiles
no_extra_bands = len([b for b in bands_in_output if b not in BAND_ORDER]) == 0
print(f"[{'PASS' if bands_ok else 'FAIL'}] All 4 bands present: {bands_ok}")
print(f"[{'PASS' if quintiles_ok else 'FAIL'}] All 5 quintiles present: {quintiles_ok}")
print(f"[{'PASS' if no_extra_bands else 'FAIL'}] No extra bands: {no_extra_bands}")

# --- Check 10: [Downstream] pell_gap consistency within bands ---
# INTENT: The pell_gap column was joined on selectivity_band, so all 5 quintile
# rows within a band should have the same pell_gap value.
consistency_issues = []
for band in BAND_ORDER:
    band_gaps = df.filter(pl.col("selectivity_band") == band)["pell_gap"]
    unique_gaps = band_gaps.unique().drop_nulls()
    if unique_gaps.shape[0] > 1:
        consistency_issues.append(f"{band}: {unique_gaps.shape[0]} different gap values")
consistency_ok = len(consistency_issues) == 0
print(f"[{'PASS' if consistency_ok else 'FAIL'}] Pell gap consistent within bands: ", end="")
print("All consistent" if consistency_ok else "; ".join(consistency_issues))

# --- Check 11: [Spot-Check] Recalculate Open/Less Selective x Q1 mean from source ---
# INTENT: Independently compute the mean grad rate for Open/Less Selective x Q1 (Lowest)
# from the source data and compare to the cross-tab output.
ols_q1_source = df_source.filter(
    (pl.col("selectivity_band") == "Open/Less Selective")
    & (pl.col("pell_quintile") == "Q1 (Lowest)")
    & pl.col("completion_rate_150pct").is_not_null()
)
ols_q1_mean_source = ols_q1_source["completion_rate_150pct"].mean()
ols_q1_n_source = ols_q1_source.shape[0]
ols_q1_output = df.filter(
    (pl.col("selectivity_band") == "Open/Less Selective")
    & (pl.col("pell_quintile") == "Q1 (Lowest)")
)
ols_q1_mean_output = ols_q1_output["mean_grad_rate"][0]
ols_q1_n_output = ols_q1_output["N"][0]
spot1_ok = abs(ols_q1_mean_source - ols_q1_mean_output) < 0.01 and ols_q1_n_source == ols_q1_n_output
print(f"[{'PASS' if spot1_ok else 'FAIL'}] Spot-check OLS x Q1: source mean={ols_q1_mean_source:.2f} (N={ols_q1_n_source}), output mean={ols_q1_mean_output:.2f} (N={ols_q1_n_output})")

# --- Check 12: [Spot-Check] Verify HS band total N = 66 ---
hs_total_n = df.filter(pl.col("selectivity_band") == "Highly Selective")["N"].sum()
hs_ok = hs_total_n == 66  # From execution log
print(f"[{'PASS' if hs_ok else 'FAIL'}] HS band total N: {hs_total_n} (expected 66 from log)")

# --- Check 13: [Spot-Check] Cross-check Open/Less Selective pell_gap ---
ols_rows = df.filter(pl.col("selectivity_band") == "Open/Less Selective")
ols_q1 = ols_rows.filter(pl.col("pell_quintile") == "Q1 (Lowest)")["mean_grad_rate"][0]
ols_q5 = ols_rows.filter(pl.col("pell_quintile") == "Q5 (Highest)")["mean_grad_rate"][0]
expected_ols_gap = ols_q1 - ols_q5
actual_ols_gap = ols_rows["pell_gap"][0]
spot3_ok = abs(expected_ols_gap - actual_ols_gap) < 0.01
print(f"[{'PASS' if spot3_ok else 'FAIL'}] OLS pell_gap: Q1={ols_q1:.1f} - Q5={ols_q5:.1f} = {expected_ols_gap:.1f}, stored={actual_ols_gap:.1f}")

# --- Check 14: [Spot-Check] Moderately Selective median vs mean plausibility ---
# INTENT: Median should generally be close to mean for large-N cells. If median is
# far from mean it suggests skew, which is fine but worth documenting.
ms_rows = df.filter(pl.col("selectivity_band") == "Moderately Selective")
ms_mean_range = (ms_rows["mean_grad_rate"].min(), ms_rows["mean_grad_rate"].max())
ms_median_range = (ms_rows["median_grad_rate"].min(), ms_rows["median_grad_rate"].max())
# Check that medians are within +-15pp of means (generous tolerance for skewed data)
ms_diffs = []
for row in ms_rows.iter_rows(named=True):
    diff = abs(row["mean_grad_rate"] - row["median_grad_rate"])
    if diff > 15:
        ms_diffs.append(f"{row['pell_quintile']}: mean={row['mean_grad_rate']:.1f}, median={row['median_grad_rate']:.1f}")
spot4_ok = len(ms_diffs) == 0
print(f"[{'PASS' if spot4_ok else 'WARN'}] Moderately Selective mean-median consistency: ", end="")
print("All within 15pp" if spot4_ok else "; ".join(ms_diffs))

# --- Check 15: [Spot-Check] Band completeness - no extra bands, exactly 4 ---
actual_bands = df["selectivity_band"].unique().to_list()
expected_band_set = set(BAND_ORDER)
actual_band_set = set(actual_bands)
spot5_ok = actual_band_set == expected_band_set
print(f"[{'PASS' if spot5_ok else 'FAIL'}] Band set exactly matches expected: {spot5_ok}")
if not spot5_ok:
    print(f"  Missing: {expected_band_set - actual_band_set}")
    print(f"  Extra: {actual_band_set - expected_band_set}")

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull output data:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nN per band:")
for band in BAND_ORDER:
    band_n = df.filter(pl.col("selectivity_band") == band)["N"].sum()
    print(f"  {band}: {band_n}")

print("\nPell gap per band:")
for band in BAND_ORDER:
    band_rows = df.filter(pl.col("selectivity_band") == band)
    gap = band_rows["pell_gap"][0]
    print(f"  {band}: {gap:+.1f} pp")

print("\nGrad rate range per band:")
for band in BAND_ORDER:
    band_rows = df.filter(pl.col("selectivity_band") == band)
    min_r = band_rows["mean_grad_rate"].min()
    max_r = band_rows["mean_grad_rate"].max()
    spread = max_r - min_r
    print(f"  {band}: [{min_r:.1f}, {max_r:.1f}] (spread={spread:.1f}pp)")

print("\nSparse cell detail:")
for row in df.filter(pl.col("N") < SPARSE_THRESHOLD).iter_rows(named=True):
    print(f"  {row['selectivity_band']} x {row['pell_quintile']}: N={row['N']}, mean={row['mean_grad_rate']:.1f}, median={row['median_grad_rate']:.1f}")

# --- Summary ---
all_checks = [schema_ok, rows_ok, dist_ok, range_ok, nulls_ok, n_sum_ok, gap_ok,
              n_sparse <= 5, bands_ok, quintiles_ok, no_extra_bands, consistency_ok,
              spot1_ok, hs_ok, spot3_ok, spot4_ok, spot5_ok]
all_passed = all(all_checks)

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
if not all_passed:
    failed = sum(1 for c in all_checks if not c)
    print(f"  {failed} check(s) did not pass")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 12:08:48
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_02_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 2 (crosstab-selectivity-pell)
# ============================================================
# Loaded output: 20 rows x 6 cols
# Loaded source: 1,946 rows x 25 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 20 (expected 20)
# [PASS] Distributions: Look reasonable
# [PASS] Grad rates in [0, 100]: mean=[43.8, 91.4], median=[43.1, 93.0]
# [PASS] Critical nulls: None
# [PASS] Cell N sum (1887) == source filtered rows (1887)
# [PASS] Pell gap direction: All gaps match Q1-Q5 definition
# [PASS] Sparse cells (N < 10): 3
#     Highly Selective x Q1 (Lowest): N=4
#     Highly Selective x Q4: N=3
#     Highly Selective x Q5 (Highest): N=2
# [PASS] All 4 bands present: True
# [PASS] All 5 quintiles present: True
# [PASS] No extra bands: True
# [PASS] Pell gap consistent within bands: All consistent
# [PASS] Spot-check OLS x Q1: source mean=43.76 (N=182), output mean=43.76 (N=182)
# [PASS] HS band total N: 66 (expected 66 from log)
# [PASS] OLS pell_gap: Q1=43.8 - Q5=54.1 = -10.3, stored=-10.3
# [PASS] Moderately Selective mean-median consistency: All within 15pp
# [PASS] Band set exactly matches expected: True
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full output data:
# shape: (20, 6)
# ┌──────────────────┬───────────────┬────────────────┬──────────────────┬─────┬──────────┐
# │ selectivity_band ┆ pell_quintile ┆ mean_grad_rate ┆ median_grad_rate ┆ N   ┆ pell_gap │
# │ ---              ┆ ---           ┆ ---            ┆ ---              ┆ --- ┆ ---      │
# │ str              ┆ cat           ┆ f64            ┆ f64              ┆ u32 ┆ f64      │
# ╞══════════════════╪═══════════════╪════════════════╪══════════════════╪═════╪══════════╡
# │ Highly Selective ┆ Q1 (Lowest)   ┆ 90.875         ┆ 92.8             ┆ 4   ┆ 28.325   │
# │ Highly Selective ┆ Q2            ┆ 91.405263      ┆ 92.95            ┆ 38  ┆ 28.325   │
# │ Highly Selective ┆ Q3            ┆ 89.278947      ┆ 91.5             ┆ 19  ┆ 28.325   │
# │ Highly Selective ┆ Q4            ┆ 64.7           ┆ 83.4             ┆ 3   ┆ 28.325   │
# │ Highly Selective ┆ Q5 (Highest)  ┆ 62.55          ┆ 62.55            ┆ 2   ┆ 28.325   │
# │ …                ┆ …             ┆ …              ┆ …                ┆ …   ┆ …        │
# │ Selective        ┆ Q1 (Lowest)   ┆ 48.003448      ┆ 44.3             ┆ 29  ┆ 0.824282 │
# │ Selective        ┆ Q2            ┆ 67.662162      ┆ 75.5             ┆ 37  ┆ 0.824282 │
# │ Selective        ┆ Q3            ┆ 73.236585      ┆ 79.9             ┆ 41  ┆ 0.824282 │
# │ Selective        ┆ Q4            ┆ 55.882927      ┆ 57.6             ┆ 41  ┆ 0.824282 │
# │ Selective        ┆ Q5 (Highest)  ┆ 47.179167      ┆ 44.9             ┆ 24  ┆ 0.824282 │
# └──────────────────┴───────────────┴────────────────┴──────────────────┴─────┴──────────┘
# 
# Descriptive statistics:
# shape: (9, 7)
# ┌────────────┬───────────────┬──────────────┬──────────────┬──────────────┬───────────┬────────────┐
# │ statistic  ┆ selectivity_b ┆ pell_quintil ┆ mean_grad_ra ┆ median_grad_ ┆ N         ┆ pell_gap   │
# │ ---        ┆ and           ┆ e            ┆ te           ┆ rate         ┆ ---       ┆ ---        │
# │ str        ┆ ---           ┆ ---          ┆ ---          ┆ ---          ┆ f64       ┆ f64        │
# │            ┆ str           ┆ str          ┆ f64          ┆ f64          ┆           ┆            │
# ╞════════════╪═══════════════╪══════════════╪══════════════╪══════════════╪═══════════╪════════════╡
# │ count      ┆ 20            ┆ 20           ┆ 20.0         ┆ 20.0         ┆ 20.0      ┆ 20.0       │
# │ null_count ┆ 0             ┆ 0            ┆ 0.0          ┆ 0.0          ┆ 0.0       ┆ 0.0        │
# │ mean       ┆ null          ┆ null         ┆ 61.69579     ┆ 64.0025      ┆ 94.35     ┆ 4.935077   │
# │ std        ┆ null          ┆ null         ┆ 14.276804    ┆ 16.233157    ┆ 84.636234 ┆ 14.630816  │
# │ min        ┆ Highly        ┆ null         ┆ 43.757692    ┆ 43.1         ┆ 2.0       ┆ -10.343697 │
# │            ┆ Selective     ┆              ┆              ┆              ┆           ┆            │
# │ 25%        ┆ null          ┆ null         ┆ 54.101389    ┆ 55.4         ┆ 29.0      ┆ 0.824282   │
# │ 50%        ┆ null          ┆ null         ┆ 57.748235    ┆ 57.6         ┆ 56.0      ┆ 0.934722   │
# │ 75%        ┆ null          ┆ null         ┆ 64.7         ┆ 75.5         ┆ 162.0     ┆ 0.934722   │
# │ max        ┆ Selective     ┆ null         ┆ 91.405263    ┆ 92.95        ┆ 228.0     ┆ 28.325     │
# └────────────┴───────────────┴──────────────┴──────────────┴──────────────┴───────────┴────────────┘
# 
# N per band:
#   Highly Selective: 66
#   Selective: 172
#   Moderately Selective: 574
#   Open/Less Selective: 1075
# 
# Pell gap per band:
#   Highly Selective: +28.3 pp
#   Selective: +0.8 pp
#   Moderately Selective: +0.9 pp
#   Open/Less Selective: -10.3 pp
# 
# Grad rate range per band:
#   Highly Selective: [62.5, 91.4] (spread=28.9pp)
#   Selective: [47.2, 73.2] (spread=26.1pp)
#   Moderately Selective: [54.3, 61.4] (spread=7.2pp)
#   Open/Less Selective: [43.8, 55.0] (spread=11.3pp)
# 
# Sparse cell detail:
#   Highly Selective x Q1 (Lowest): N=4, mean=90.9, median=92.8
#   Highly Selective x Q4: N=3, mean=64.7, median=83.4
#   Highly Selective x Q5 (Highest): N=2, mean=62.5, median=62.5
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
