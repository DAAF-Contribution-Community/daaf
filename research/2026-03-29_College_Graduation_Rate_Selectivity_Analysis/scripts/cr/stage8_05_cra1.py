#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 05 (QA4a -- Analysis)

Reviewed script: scripts/stage8_analysis/05_outperformers.py
Output files:
  - output/analysis/2026-03-29_selectivity_model.parquet
  - output/analysis/2026-03-29_outperformers.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
6-10. Script-specific checks (Five Lenses)
11-15. Concrete spot-checks
16. Data profiling
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

MODEL_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_selectivity_model.parquet"
OUTPERFORMERS_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_outperformers.parquet"
ANALYSIS_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

EXPECTED_MODEL_COLUMNS = ["unitid", "inst_name", "admit_rate", "completion_rate_150pct",
                          "predicted", "residual", "outperformer_flag"]
CRITICAL_COLUMNS_MODEL = ["unitid", "admit_rate", "completion_rate_150pct", "predicted", "residual", "outperformer_flag"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 05 -- Outperformers (QA4a)")
print("=" * 60)

df_model = pl.read_parquet(MODEL_FILE)
df_outperf = pl.read_parquet(OUTPERFORMERS_FILE)
df_analysis = pl.read_parquet(ANALYSIS_FILE)

print(f"Model file loaded: {df_model.shape[0]:,} rows x {df_model.shape[1]} cols")
print(f"Outperformers file loaded: {df_outperf.shape[0]:,} rows x {df_outperf.shape[1]} cols")
print(f"Analysis file loaded: {df_analysis.shape[0]:,} rows x {df_analysis.shape[1]} cols")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_MODEL_COLUMNS if c not in df_model.columns]
extra_cols = [c for c in df_model.columns if c not in EXPECTED_MODEL_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present in model file")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# --- Check 2: Row count ---
# Model file should contain institutions with non-null admit_rate AND completion_rate_150pct
# From execution log: 1,625 rows (1,946 - 321 dropped)
row_count = len(df_model)
rows_ok = 500 <= row_count <= 2500
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected 500-2,500)")

# --- Check 3: Distributions ---
dist_issues = []
for col in df_model.select(pl.col(pl.Float64, pl.Int64)).columns:
    col_data = df_model[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if col in ["admit_rate", "completion_rate_150pct", "predicted"]:
        if col_data.min() < 0 or col_data.max() > 100:
            dist_issues.append(f"{col}: values outside 0-100 range ({col_data.min():.1f} to {col_data.max():.1f})")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
coded_issues = []
for col in df_model.columns:
    if df_model[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in CODED_MISSING_VALUES:
        count = (df_model[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS_MODEL:
    if col in df_model.columns:
        null_count = df_model[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ==========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6 (Counterfactual): What if residuals are not approximately normal? ---
# The 1 SD threshold assumes roughly ~15-20% at each tail. If residuals are
# heavily skewed, the percentage would differ materially.
residuals = df_model["residual"]
skewness = residuals.skew()
kurtosis = float(np.mean(((residuals.to_numpy() - residuals.mean()) / residuals.std()) ** 4))
n_out = (df_model["outperformer_flag"] == "outperformer").sum()
n_under = (df_model["outperformer_flag"] == "underperformer").sum()
n_total = len(df_model)
out_pct = n_out / n_total * 100
under_pct = n_under / n_total * 100

# For normal distribution, ~15.87% should be beyond 1 SD on each side
normal_expected_pct = 15.87
deviation_from_normal_out = abs(out_pct - normal_expected_pct)
deviation_from_normal_under = abs(under_pct - normal_expected_pct)

resid_norm_ok = deviation_from_normal_out < 5 and deviation_from_normal_under < 5
print(f"\n[{'PASS' if resid_norm_ok else 'WARN'}] Counterfactual: Residual normality")
print(f"  Skewness: {skewness:.3f}, Excess kurtosis: {kurtosis - 3:.3f}")
print(f"  Outperformer %: {out_pct:.1f}% (normal expectation: ~15.9%)")
print(f"  Underperformer %: {under_pct:.1f}% (normal expectation: ~15.9%)")

# --- Check 7 (Semantic): Does the model serve the RESEARCH QUESTION? ---
# The research question asks about variance attributable to selectivity vs
# effectiveness. R-squared from this model directly quantifies selectivity's
# share. Verify R-squared is computed correctly from the output data.
ss_res = (residuals ** 2).sum()
ss_tot = ((df_model["completion_rate_150pct"] - df_model["completion_rate_150pct"].mean()) ** 2).sum()
r_squared_recalc = 1 - (ss_res / ss_tot)
print(f"\n[INFO] Semantic: R-squared recalculated from output data = {r_squared_recalc:.4f}")
# From execution log: R-squared = 0.0999
r2_match = abs(r_squared_recalc - 0.0999) < 0.005
print(f"[{'PASS' if r2_match else 'FAIL'}] R-squared matches execution log: recalc={r_squared_recalc:.4f} vs logged=0.0999")
print(f"  Interpretation: Selectivity alone explains ~{r_squared_recalc*100:.1f}% of graduation rate variance")

# --- Check 8 (Boundary): Edge cases -- zero admit rate, 100% grad rate ---
zero_admit = df_model.filter(pl.col("admit_rate") == 0)
max_grad = df_model.filter(pl.col("completion_rate_150pct") == 100)
min_grad = df_model.filter(pl.col("completion_rate_150pct") == 0)
print(f"\n[INFO] Boundary: Edge cases in model data")
print(f"  admit_rate == 0: {zero_admit.shape[0]} institutions")
if zero_admit.shape[0] > 0:
    print(f"    DeVry check: {zero_admit.filter(pl.col('unitid') == 482538).shape[0]} is DeVry (unitid 482538)")
    for row in zero_admit.iter_rows(named=True):
        print(f"    unitid={row['unitid']}, name={row['inst_name']}, grad_rate={row['completion_rate_150pct']:.1f}%, predicted={row['predicted']:.1f}%, flag={row['outperformer_flag']}")
print(f"  completion_rate_150pct == 100: {max_grad.shape[0]} institutions")
print(f"  completion_rate_150pct == 0: {min_grad.shape[0]} institutions")

boundary_ok = True  # Informational check
print(f"[{'PASS' if boundary_ok else 'WARN'}] Boundary: Edge cases documented")

# --- Check 9 (Absence): What's NOT checked? ---
# The script does not verify that residuals sum to approximately zero (OLS property).
# It prints mean residual but doesn't assert it. Let's verify.
resid_mean = residuals.mean()
resid_sum_ok = abs(resid_mean) < 0.01
print(f"\n[{'PASS' if resid_sum_ok else 'FAIL'}] Absence: Residual mean ~0 (OLS property)")
print(f"  Residual mean: {resid_mean:.6f}")

# Also check: Does the profile include all Plan.md-specified variables?
plan_profile_vars = ["pell_share", "urm_share", "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]
profile_vars_in_output = [v for v in df_outperf["variable"].to_list() if not v.startswith("sector_")]
missing_profile = [v for v in plan_profile_vars if v not in profile_vars_in_output]
profile_complete = len(missing_profile) == 0
print(f"[{'PASS' if profile_complete else 'FAIL'}] Absence: All Plan.md profile variables present in outperformers.parquet")
if missing_profile:
    print(f"  Missing: {missing_profile}")

# --- Check 10 (Downstream): What would viz-residual-scatter (Task 11.1) need? ---
# The downstream viz script needs predicted, actual, and outperformer_flag from
# selectivity_model.parquet. Verify the flag values are exactly the expected strings.
flag_values = sorted(df_model["outperformer_flag"].unique().to_list())
expected_flags = ["outperformer", "typical", "underperformer"]
flags_ok = flag_values == expected_flags
print(f"\n[{'PASS' if flags_ok else 'FAIL'}] Downstream: outperformer_flag values are {flag_values}")
if not flags_ok:
    print(f"  Expected: {expected_flags}")

# Verify predicted values are in reasonable range for scatter plot
pred_range_ok = df_model["predicted"].min() >= 0 and df_model["predicted"].max() <= 100
print(f"[{'PASS' if pred_range_ok else 'FAIL'}] Downstream: Predicted values in 0-100 range ({df_model['predicted'].min():.1f} to {df_model['predicted'].max():.1f})")

# ==========================================================================
# CONCRETE SPOT-CHECKS
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Recalculate predicted value for a specific institution ---
# Pick the first outperformer and manually verify its predicted = intercept + slope * admit_rate
# From execution log: const=78.1231, admit_rate coef=-0.2890
INTERCEPT = 78.1231
SLOPE = -0.2890

sample_out = df_model.filter(pl.col("outperformer_flag") == "outperformer").head(3)
print(f"\nSpot-check: Manual predicted value recalculation (const={INTERCEPT}, slope={SLOPE})")
recalc_ok = True
for row in sample_out.iter_rows(named=True):
    manual_pred = INTERCEPT + SLOPE * row["admit_rate"]
    actual_pred = row["predicted"]
    diff = abs(manual_pred - actual_pred)
    ok = diff < 0.01
    if not ok:
        recalc_ok = False
    print(f"  {row['inst_name'][:40]}: admit_rate={row['admit_rate']:.1f}%, "
          f"manual_pred={manual_pred:.2f}, stored_pred={actual_pred:.2f}, diff={diff:.4f} [{'OK' if ok else 'FAIL'}]")
print(f"[{'PASS' if recalc_ok else 'FAIL'}] Spot-check: Manual prediction recalculation matches stored values")

# --- Spot-check 12: Verify residual = actual - predicted ---
resid_check_ok = True
for row in sample_out.iter_rows(named=True):
    expected_resid = row["completion_rate_150pct"] - row["predicted"]
    actual_resid = row["residual"]
    diff = abs(expected_resid - actual_resid)
    ok = diff < 0.001
    if not ok:
        resid_check_ok = False
    print(f"  Residual check: actual={row['completion_rate_150pct']:.2f} - pred={row['predicted']:.2f} = {expected_resid:.2f}, stored={actual_resid:.2f} [{'OK' if ok else 'FAIL'}]")
print(f"[{'PASS' if resid_check_ok else 'FAIL'}] Spot-check: Residual = actual - predicted")

# --- Spot-check 13: Verify outperformer threshold classification ---
resid_sd = residuals.std()  # This is sample SD (ddof=1 in polars default)
resid_sd_pop = float(np.std(residuals.to_numpy(), ddof=0))  # Population SD as used in script
threshold = resid_sd_pop * 1.0

print(f"\n  Residual SD (population, ddof=0): {resid_sd_pop:.4f}")
print(f"  Residual SD (sample, ddof=1): {resid_sd:.4f}")
print(f"  Threshold used (1 * SD_pop): {threshold:.4f}")

# Verify: all outperformers have residual > threshold
misclassified_out = df_model.filter(
    (pl.col("outperformer_flag") == "outperformer") & (pl.col("residual") <= threshold)
)
misclassified_under = df_model.filter(
    (pl.col("outperformer_flag") == "underperformer") & (pl.col("residual") >= -threshold)
)
misclassified_typical_high = df_model.filter(
    (pl.col("outperformer_flag") == "typical") & (pl.col("residual") > threshold)
)
misclassified_typical_low = df_model.filter(
    (pl.col("outperformer_flag") == "typical") & (pl.col("residual") < -threshold)
)
total_misclassified = (misclassified_out.shape[0] + misclassified_under.shape[0] +
                       misclassified_typical_high.shape[0] + misclassified_typical_low.shape[0])
classify_ok = total_misclassified == 0
print(f"[{'PASS' if classify_ok else 'FAIL'}] Spot-check: Classification threshold consistency")
print(f"  Misclassified outperformers (resid <= threshold): {misclassified_out.shape[0]}")
print(f"  Misclassified underperformers (resid >= -threshold): {misclassified_under.shape[0]}")
print(f"  Misclassified typical (resid > threshold): {misclassified_typical_high.shape[0]}")
print(f"  Misclassified typical (resid < -threshold): {misclassified_typical_low.shape[0]}")

# --- Spot-check 14: Cross-reference model N vs analysis complete-case N ---
# The model should contain exactly the rows from analysis where both admit_rate and
# completion_rate_150pct are non-null
analysis_complete = df_analysis.drop_nulls(subset=["admit_rate", "completion_rate_150pct"])
n_match = len(analysis_complete) == len(df_model)
print(f"\n[{'PASS' if n_match else 'FAIL'}] Spot-check: Model N matches analysis complete-case N")
print(f"  Analysis complete cases: {len(analysis_complete):,}")
print(f"  Model rows: {len(df_model):,}")

# --- Spot-check 15: Verify outperformer % is within QA tolerance (5-30%) ---
out_pct_tolerance = 5 <= out_pct <= 30
print(f"\n[{'PASS' if out_pct_tolerance else 'FAIL'}] Spot-check: Outperformer % within QA tolerance")
print(f"  Outperformer %: {out_pct:.1f}% (tolerance: 5-30%)")
print(f"  Outperformers: {n_out:,}, Underperformers: {n_under:,}, Typical: {n_total - n_out - n_under:,}")

# ==========================================================================
# DATA PROFILING
# ==========================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nModel file -- first 10 rows:")
print(df_model.head(10))

print("\nModel file -- descriptive statistics:")
print(df_model.describe())

print("\nOutperformer flag distribution:")
print(df_model["outperformer_flag"].value_counts().sort("outperformer_flag"))

print("\nOutperformers profile file contents:")
print(df_outperf)

print("\nResidual distribution (selected percentiles):")
residuals_np = residuals.to_numpy()
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    print(f"  P{p}: {np.percentile(residuals_np, p):.2f}")

print("\nAdmit rate distribution in model data:")
print(f"  Min: {df_model['admit_rate'].min():.1f}%")
print(f"  P25: {df_model['admit_rate'].quantile(0.25):.1f}%")
print(f"  Median: {df_model['admit_rate'].median():.1f}%")
print(f"  P75: {df_model['admit_rate'].quantile(0.75):.1f}%")
print(f"  Max: {df_model['admit_rate'].max():.1f}%")

print("\nCompletion rate distribution in model data:")
print(f"  Min: {df_model['completion_rate_150pct'].min():.1f}%")
print(f"  P25: {df_model['completion_rate_150pct'].quantile(0.25):.1f}%")
print(f"  Median: {df_model['completion_rate_150pct'].median():.1f}%")
print(f"  P75: {df_model['completion_rate_150pct'].quantile(0.75):.1f}%")
print(f"  Max: {df_model['completion_rate_150pct'].max():.1f}%")

# Check predicted value range
print(f"\nPredicted value range: {df_model['predicted'].min():.2f} to {df_model['predicted'].max():.2f}")
print(f"  (Linear model: as admit_rate increases, predicted grad rate should decrease)")
# Verify negative slope: highest admit_rate should have lowest predicted
max_admit = df_model.filter(pl.col("admit_rate") == df_model["admit_rate"].max())
min_admit = df_model.filter(pl.col("admit_rate") == df_model["admit_rate"].min())
print(f"  At min admit_rate ({min_admit['admit_rate'][0]:.1f}%): predicted={min_admit['predicted'][0]:.2f}%")
print(f"  At max admit_rate ({max_admit['admit_rate'][0]:.1f}%): predicted={max_admit['predicted'][0]:.2f}%")
slope_negative = min_admit['predicted'][0] > max_admit['predicted'][0]
print(f"  Slope direction correct (negative): {slope_negative}")

# --- Summary ---
all_checks = [schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
              resid_norm_ok, r2_match, resid_sum_ok, profile_complete,
              flags_ok, pred_range_ok, recalc_ok, resid_check_ok,
              classify_ok, n_match, out_pct_tolerance, slope_negative]
all_passed = all(all_checks)

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
failed = [i for i, v in enumerate(all_checks) if not v]
if failed:
    print(f"  Failed check indices: {failed}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:19:22
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_05_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 05 -- Outperformers (QA4a)
# ============================================================
# Model file loaded: 1,625 rows x 7 cols
# Outperformers file loaded: 11 rows x 5 cols
# Analysis file loaded: 1,946 rows x 25 cols
# 
# [PASS] Schema: All expected columns present in model file
# [PASS] Row count: 1,625 (expected 500-2,500)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] Counterfactual: Residual normality
#   Skewness: -0.531, Excess kurtosis: 0.238
#   Outperformer %: 15.3% (normal expectation: ~15.9%)
#   Underperformer %: 15.4% (normal expectation: ~15.9%)
# 
# [INFO] Semantic: R-squared recalculated from output data = 0.0999
# [PASS] R-squared matches execution log: recalc=0.0999 vs logged=0.0999
#   Interpretation: Selectivity alone explains ~10.0% of graduation rate variance
# 
# [INFO] Boundary: Edge cases in model data
#   admit_rate == 0: 1 institutions
#     DeVry check: 1 is DeVry (unitid 482538)
#     unitid=482538, name=DeVry University-Missouri, grad_rate=66.7%, predicted=78.1%, flag=typical
#   completion_rate_150pct == 100: 13 institutions
#   completion_rate_150pct == 0: 0 institutions
# [PASS] Boundary: Edge cases documented
# 
# [PASS] Absence: Residual mean ~0 (OLS property)
#   Residual mean: -0.000000
# [PASS] Absence: All Plan.md profile variables present in outperformers.parquet
# 
# [PASS] Downstream: outperformer_flag values are ['outperformer', 'typical', 'underperformer']
# [PASS] Downstream: Predicted values in 0-100 range (49.2 to 78.1)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-check: Manual predicted value recalculation (const=78.1231, slope=-0.289)
#   Auburn University: admit_rate=85.1%, manual_pred=53.54, stored_pred=53.54, diff=0.0003 [OK]
#   Samford University: admit_rate=84.0%, manual_pred=53.85, stored_pred=53.85, diff=0.0003 [OK]
#   Art Center College of Design: admit_rate=76.1%, manual_pred=56.13, stored_pred=56.13, diff=0.0003 [OK]
# [PASS] Spot-check: Manual prediction recalculation matches stored values
#   Residual check: actual=80.90 - pred=53.54 = 27.36, stored=27.36 [OK]
#   Residual check: actual=78.90 - pred=53.85 = 25.05, stored=25.05 [OK]
#   Residual check: actual=75.90 - pred=56.13 = 19.77, stored=19.77 [OK]
# [PASS] Spot-check: Residual = actual - predicted
# 
#   Residual SD (population, ddof=0): 17.8241
#   Residual SD (sample, ddof=1): 17.8296
#   Threshold used (1 * SD_pop): 17.8241
# [PASS] Spot-check: Classification threshold consistency
#   Misclassified outperformers (resid <= threshold): 0
#   Misclassified underperformers (resid >= -threshold): 0
#   Misclassified typical (resid > threshold): 0
#   Misclassified typical (resid < -threshold): 0
# 
# [PASS] Spot-check: Model N matches analysis complete-case N
#   Analysis complete cases: 1,625
#   Model rows: 1,625
# 
# [PASS] Spot-check: Outperformer % within QA tolerance
#   Outperformer %: 15.3% (tolerance: 5-30%)
#   Outperformers: 248, Underperformers: 251, Typical: 1,126
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Model file -- first 10 rows:
# shape: (10, 7)
# ┌────────┬─────────────────┬────────────┬────────────────┬───────────┬────────────┬────────────────┐
# │ unitid ┆ inst_name       ┆ admit_rate ┆ completion_rat ┆ predicted ┆ residual   ┆ outperformer_f │
# │ ---    ┆ ---             ┆ ---        ┆ e_150pct       ┆ ---       ┆ ---        ┆ lag            │
# │ i64    ┆ str             ┆ f64        ┆ ---            ┆ f64       ┆ f64        ┆ ---            │
# │        ┆                 ┆            ┆ f64            ┆           ┆            ┆ str            │
# ╞════════╪═════════════════╪════════════╪════════════════╪═══════════╪════════════╪════════════════╡
# │ 100654 ┆ Alabama A & M   ┆ 89.649924  ┆ 28.1           ┆ 52.213977 ┆ -24.113977 ┆ underperformer │
# │        ┆ University      ┆            ┆                ┆           ┆            ┆                │
# │ 100663 ┆ University of   ┆ 80.598595  ┆ 62.4           ┆ 54.82984  ┆ 7.57016    ┆ typical        │
# │        ┆ Alabama at      ┆            ┆                ┆           ┆            ┆                │
# │        ┆ Birmi…          ┆            ┆                ┆           ┆            ┆                │
# │ 100706 ┆ University of   ┆ 77.110306  ┆ 60.7           ┆ 55.837967 ┆ 4.862033   ┆ typical        │
# │        ┆ Alabama in      ┆            ┆                ┆           ┆            ┆                │
# │        ┆ Hunts…          ┆            ┆                ┆           ┆            ┆                │
# │ 100724 ┆ Alabama State   ┆ 98.875765  ┆ 28.4           ┆ 49.547679 ┆ -21.147679 ┆ underperformer │
# │        ┆ University      ┆            ┆                ┆           ┆            ┆                │
# │ 100751 ┆ The University  ┆ 80.394338  ┆ 72.2           ┆ 54.888871 ┆ 17.311129  ┆ typical        │
# │        ┆ of Alabama      ┆            ┆                ┆           ┆            ┆                │
# │ 100830 ┆ Auburn          ┆ 95.549284  ┆ 35.7           ┆ 50.509043 ┆ -14.809043 ┆ typical        │
# │        ┆ University at   ┆            ┆                ┆           ┆            ┆                │
# │        ┆ Montgomer…      ┆            ┆                ┆           ┆            ┆                │
# │ 100858 ┆ Auburn          ┆ 85.06631   ┆ 80.9           ┆ 53.538656 ┆ 27.361344  ┆ outperformer   │
# │        ┆ University      ┆            ┆                ┆           ┆            ┆                │
# │ 100937 ┆ Birmingham-Sout ┆ 60.447154  ┆ 69.8           ┆ 60.653671 ┆ 9.146329   ┆ typical        │
# │        ┆ hern College    ┆            ┆                ┆           ┆            ┆                │
# │ 101189 ┆ Faulkner        ┆ 75.763359  ┆ 18.1           ┆ 56.227239 ┆ -38.127239 ┆ underperformer │
# │        ┆ University      ┆            ┆                ┆           ┆            ┆                │
# │ 101435 ┆ Huntingdon      ┆ 54.391733  ┆ 44.2           ┆ 62.403707 ┆ -18.203707 ┆ underperformer │
# │        ┆ College         ┆            ┆                ┆           ┆            ┆                │
# └────────┴─────────────────┴────────────┴────────────────┴───────────┴────────────┴────────────────┘
# 
# Model file -- descriptive statistics:
# shape: (9, 8)
# ┌────────────┬────────────┬────────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ inst_name  ┆ admit_rat ┆ completio ┆ predicted ┆ residual  ┆ outperfor │
# │ ---        ┆ ---        ┆ ---        ┆ e         ┆ n_rate_15 ┆ ---       ┆ ---       ┆ mer_flag  │
# │ str        ┆ f64        ┆ str        ┆ ---       ┆ 0pct      ┆ f64       ┆ f64       ┆ ---       │
# │            ┆            ┆            ┆ f64       ┆ ---       ┆           ┆           ┆ str       │
# │            ┆            ┆            ┆           ┆ f64       ┆           ┆           ┆           │
# ╞════════════╪════════════╪════════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 1625.0     ┆ 1625       ┆ 1625.0    ┆ 1625.0    ┆ 1625.0    ┆ 1625.0    ┆ 1625      │
# │ null_count ┆ 0.0        ┆ 0          ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0         │
# │ mean       ┆ 202765.124 ┆ null       ┆ 70.41439  ┆ 57.773108 ┆ 57.773108 ┆ -5.3730e- ┆ null      │
# │            ┆ 923        ┆            ┆           ┆           ┆           ┆ 14        ┆           │
# │ std        ┆ 83317.3426 ┆ null       ┆ 20.555162 ┆ 18.793213 ┆ 5.940508  ┆ 17.829617 ┆ null      │
# │            ┆ 42         ┆            ┆           ┆           ┆           ┆           ┆           │
# │ min        ┆ 100654.0   ┆ Abilene    ┆ 0.0       ┆ 3.8       ┆ 49.222771 ┆ -58.01344 ┆ outperfor │
# │            ┆            ┆ Christian  ┆           ┆           ┆           ┆ 7         ┆ mer       │
# │            ┆            ┆ University ┆           ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 154712.0   ┆ null       ┆ 59.807356 ┆ 45.8      ┆ 53.499793 ┆ -10.93460 ┆ null      │
# │            ┆            ┆            ┆           ┆           ┆           ┆ 2         ┆           │
# │ 50%        ┆ 190761.0   ┆ null       ┆ 74.441371 ┆ 57.7      ┆ 56.609297 ┆ 2.204323  ┆ null      │
# │ 75%        ┆ 218654.0   ┆ null       ┆ 85.200782 ┆ 70.6      ┆ 60.838575 ┆ 13.515327 ┆ null      │
# │ max        ┆ 495767.0   ┆ Youngstown ┆ 100.0     ┆ 100.0     ┆ 78.123093 ┆ 50.777229 ┆ underperf │
# │            ┆            ┆ State      ┆           ┆           ┆           ┆           ┆ ormer     │
# │            ┆            ┆ University ┆           ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────────┴───────────┴───────────┴───────────┴───────────┴───────────┘
# 
# Outperformer flag distribution:
# shape: (3, 2)
# ┌───────────────────┬───────┐
# │ outperformer_flag ┆ count │
# │ ---               ┆ ---   │
# │ str               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ outperformer      ┆ 248   │
# │ typical           ┆ 1126  │
# │ underperformer    ┆ 251   │
# └───────────────────┴───────┘
# 
# Outperformers profile file contents:
# shape: (11, 5)
# ┌───────────────────┬───────────────────┬───────────────────┬───────────────────┬──────────────────┐
# │ variable          ┆ outperformer_mean ┆ outperformer_medi ┆ underperformer_me ┆ underperformer_m │
# │ ---               ┆ ---               ┆ an                ┆ an                ┆ edian            │
# │ str               ┆ f64               ┆ ---               ┆ ---               ┆ ---              │
# │                   ┆                   ┆ f64               ┆ f64               ┆ f64              │
# ╞═══════════════════╪═══════════════════╪═══════════════════╪═══════════════════╪══════════════════╡
# │ pell_share        ┆ 0.105786          ┆ 0.098559          ┆ 0.126922          ┆ 0.120482         │
# │ urm_share         ┆ 0.186062          ┆ 0.168427          ┆ 0.462726          ┆ 0.388326         │
# │ student_faculty_r ┆ 11.762097         ┆ 11.0              ┆ 14.494024         ┆ 14.0             │
# │ atio              ┆                   ┆                   ┆                   ┆                  │
# │ retention_rate    ┆ 87.310204         ┆ 89.0              ┆ 62.691057         ┆ 63.0             │
# │ instr_expend_per_ ┆ 21116.211585      ┆ 16653.337505      ┆ 7739.778942       ┆ 6143.222546      │
# │ fte               ┆                   ┆                   ┆                   ┆                  │
# │ …                 ┆ …                 ┆ …                 ┆ …                 ┆ …                │
# │ sector_private_np ┆ 75.403226         ┆ null              ┆ null              ┆ null             │
# │ _outperformer…    ┆                   ┆                   ┆                   ┆                  │
# │ sector_forprofit_ ┆ 2.419355          ┆ null              ┆ null              ┆ null             │
# │ outperformers     ┆                   ┆                   ┆                   ┆                  │
# │ sector_public_und ┆ null              ┆ null              ┆ 26.294821         ┆ null             │
# │ erperformers      ┆                   ┆                   ┆                   ┆                  │
# │ sector_private_np ┆ null              ┆ null              ┆ 64.940239         ┆ null             │
# │ _underperform…    ┆                   ┆                   ┆                   ┆                  │
# │ sector_forprofit_ ┆ null              ┆ null              ┆ 8.76494           ┆ null             │
# │ underperforme…    ┆                   ┆                   ┆                   ┆                  │
# └───────────────────┴───────────────────┴───────────────────┴───────────────────┴──────────────────┘
# 
# Residual distribution (selected percentiles):
#   P1: -48.00
#   P5: -34.03
#   P10: -23.67
#   P25: -10.93
#   P50: 2.20
#   P75: 13.52
#   P90: 20.05
#   P95: 23.58
#   P99: 32.42
# 
# Admit rate distribution in model data:
#   Min: 0.0%
#   P25: 59.8%
#   Median: 74.4%
#   P75: 85.2%
#   Max: 100.0%
# 
# Completion rate distribution in model data:
#   Min: 3.8%
#   P25: 45.8%
#   Median: 57.7%
#   P75: 70.6%
#   Max: 100.0%
# 
# Predicted value range: 49.22 to 78.12
#   (Linear model: as admit_rate increases, predicted grad rate should decrease)
#   At min admit_rate (0.0%): predicted=78.12%
#   At max admit_rate (100.0%): predicted=49.22%
#   Slope direction correct (negative): True
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
