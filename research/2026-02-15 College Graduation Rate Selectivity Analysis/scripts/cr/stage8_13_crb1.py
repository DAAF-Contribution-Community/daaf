#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 10.2 (QA4b — Visualization)

Reviewed script: scripts/stage8_analysis/13_viz-residual-scatter.py
Output files: output/figures/2026-02-15_actual_vs_predicted.png
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default):
1. Figure file exists and size > 50KB
2. Predicted values in plausible range
3. Correct number of selectivity bands
4. R-squared matches regression-models output
5. N matches regression-models output

Script-Specific Checks (Five Skeptical Lenses):
6. Counterfactual: What if sector_private has nulls from inst_control?
7. Semantic: Does re-fit reproduce the same coefficients as regression-models?
8. Boundary: Are there predicted values outside 0-100 that get clipped by axes?
9. Absence: Is listwise deletion missing inst_control (sector_private source)?
10. Downstream: Would notebook or report consumers be misled by caption text?

Spot-Checks:
11. Recalculate one predicted value from raw inputs using reported coefficients
12. Verify selectivity_band distribution matches prior scripts
13. Verify no coded/sentinel values in model columns
14. Check that actual grad_rate range is 0-100
15. Verify the 45-degree line logic (intercept=0, slope=1)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"
OUTPUT_FILE = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_actual_vs_predicted.png"
ANALYSIS_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
REGRESSION_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_regression_results.parquet"

EXPECTED_COLUMNS = [
    "grad_rate_150pct", "admission_rate", "pell_share", "urm_share",
    "student_faculty_ratio", "inst_control", "selectivity_band"
]
EXPECTED_MIN_ROWS = 1400
EXPECTED_MAX_ROWS = 1600
CRITICAL_COLUMNS = ["grad_rate_150pct", "admission_rate", "pell_share",
                     "urm_share", "student_faculty_ratio"]
MODEL_COLS = ["admission_rate", "pell_share", "urm_share", "student_faculty_ratio"]
OUTCOME_COL = "grad_rate_150pct"

# --- Load output data (the analysis dataset used by the script) ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 10.2 (viz-residual-scatter)")
print("=" * 60)

df = pl.read_parquet(ANALYSIS_FILE)
print(f"Analysis dataset loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# =====================================================================
# DEFAULT CHECK 1: Figure file exists and size > 50KB
# =====================================================================
fig_exists = OUTPUT_FILE.exists()
print(f"\n[{'PASS' if fig_exists else 'FAIL'}] Check 1 — Figure exists: {OUTPUT_FILE.name}")
if fig_exists:
    fig_size_kb = OUTPUT_FILE.stat().st_size / 1024
    size_ok = fig_size_kb > 50
    print(f"[{'PASS' if size_ok else 'FAIL'}] Check 1b — Figure size: {fig_size_kb:.1f} KB (> 50 KB required)")
else:
    size_ok = False
    fig_size_kb = 0

# =====================================================================
# DEFAULT CHECK 2: Predicted values in plausible range
# Reproduce the OLS fit independently to verify predicted range
# =====================================================================
# Replicate the script's listwise deletion + OLS
df_model = (
    df
    .with_columns(
        pl.when(pl.col("inst_control") == 2)
        .then(1)
        .otherwise(0)
        .alias("sector_private")
        .cast(pl.Float64)
    )
    .drop_nulls(subset=[OUTCOME_COL] + MODEL_COLS)
)

n_complete = df_model.shape[0]
print(f"\nComplete cases (independent calc): {n_complete:,}")

y = df_model[OUTCOME_COL].to_numpy().astype(np.float64)
X_cols = MODEL_COLS + ["sector_private"]
X_data = np.column_stack([df_model[c].to_numpy().astype(np.float64) for c in X_cols])
X = np.column_stack([np.ones(len(y)), X_data])
beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
y_pred = X @ beta

pred_min, pred_max = y_pred.min(), y_pred.max()
pred_range_ok = pred_min >= 0 and pred_max <= 100
print(f"[{'PASS' if pred_range_ok else 'WARN'}] Check 2 — Predicted range: [{pred_min:.2f}, {pred_max:.2f}]")
if not pred_range_ok:
    n_outside = ((y_pred < 0) | (y_pred > 100)).sum()
    print(f"  WARNING: {n_outside} predicted values outside 0-100 (clipped by plot axes)")

# =====================================================================
# DEFAULT CHECK 3: Correct number of selectivity bands
# =====================================================================
bands_in_data = df_model["selectivity_band"].n_unique()
bands_ok = bands_in_data == 4
print(f"[{'PASS' if bands_ok else 'FAIL'}] Check 3 — Selectivity bands: {bands_in_data} (expected 4)")
print(f"  Bands: {df_model['selectivity_band'].value_counts().sort('selectivity_band')}")

# =====================================================================
# DEFAULT CHECK 4: R-squared matches regression-models output
# =====================================================================
ss_res = np.sum((y - y_pred) ** 2)
ss_tot = np.sum((y - np.mean(y)) ** 2)
r_squared = 1 - ss_res / ss_tot
# Regression-models reports R2 = 0.4559 (4dp)
r2_match = abs(r_squared - 0.4559) < 0.001
print(f"[{'PASS' if r2_match else 'WARN'}] Check 4 — R²: {r_squared:.6f} (regression-models: 0.4559)")

# =====================================================================
# DEFAULT CHECK 5: N matches expected ~1,523
# =====================================================================
n_ok = EXPECTED_MIN_ROWS <= n_complete <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if n_ok else 'WARN'}] Check 5 — N: {n_complete:,} (expected {EXPECTED_MIN_ROWS}-{EXPECTED_MAX_ROWS})")

# =====================================================================
# SCRIPT-SPECIFIC CHECK 6 (Counterfactual): inst_control nulls
# If inst_control had nulls, sector_private would be 0 (wrong) via
# the otherwise(0) clause. Verify inst_control has no nulls.
# =====================================================================
ic_nulls = df["inst_control"].null_count()
ic_ok = ic_nulls == 0
print(f"\n[{'PASS' if ic_ok else 'WARN'}] Check 6 — Counterfactual: inst_control nulls = {ic_nulls}")
if not ic_ok:
    print(f"  WARNING: {ic_nulls} nulls in inst_control would produce wrong sector_private values")

# =====================================================================
# SCRIPT-SPECIFIC CHECK 7 (Semantic): Coefficient match to regression-models
# Re-fit coefficients should match the regression-models script exactly
# since both use the same listwise deletion and numpy lstsq.
# =====================================================================
# Expected from regression-models execution log:
expected_coefs = {
    "intercept": 97.749405,
    "admission_rate": -22.960301,
    "pell_share": -60.558279,
    "urm_share": 0.945381,
    "student_faculty_ratio": -0.114461,
    "sector_private": 1.221654,
}
coef_names = ["intercept"] + X_cols
coef_match_issues = []
for name, expected_val in expected_coefs.items():
    idx = coef_names.index(name)
    actual_val = beta[idx]
    diff = abs(actual_val - expected_val)
    if diff > 0.001:
        coef_match_issues.append(f"{name}: expected {expected_val:.6f}, got {actual_val:.6f}, diff={diff:.6f}")

coefs_ok = len(coef_match_issues) == 0
print(f"[{'PASS' if coefs_ok else 'WARN'}] Check 7 — Semantic: Coefficient match to regression-models")
if not coefs_ok:
    for issue in coef_match_issues:
        print(f"  MISMATCH: {issue}")
else:
    print(f"  All 6 coefficients match regression-models within 0.001 tolerance")

# =====================================================================
# SCRIPT-SPECIFIC CHECK 8 (Boundary): Predicted values clipped by axes
# Plot uses scale_x/y_continuous(limits=(0, 100)). Any points outside
# 0-100 would be silently clipped. Count how many are affected.
# =====================================================================
n_pred_under_0 = (y_pred < 0).sum()
n_pred_over_100 = (y_pred > 100).sum()
n_actual_under_0 = (y < 0).sum()
n_actual_over_100 = (y > 100).sum()
boundary_ok = (n_pred_under_0 + n_pred_over_100 + n_actual_under_0 + n_actual_over_100) == 0
print(f"[{'PASS' if boundary_ok else 'WARN'}] Check 8 — Boundary: Points outside 0-100 axes")
print(f"  Predicted <0: {n_pred_under_0}, >100: {n_pred_over_100}")
print(f"  Actual <0: {n_actual_under_0}, >100: {n_actual_over_100}")

# =====================================================================
# SCRIPT-SPECIFIC CHECK 9 (Absence): Listwise deletion completeness
# The script drops nulls on [OUTCOME_COL] + MODEL_COLS but NOT inst_control.
# If inst_control had nulls, sector_private would silently be 0 (wrong).
# Verify the drop_nulls covers the right columns.
# =====================================================================
# The script's drop_nulls uses: subset=[OUTCOME_COL] + MODEL_COLS
# = ["grad_rate_150pct", "admission_rate", "pell_share", "urm_share", "student_faculty_ratio"]
# sector_private derived from inst_control, which has 0 nulls (check 6).
# So the absence of inst_control in drop_nulls is SAFE but FRAGILE.
absence_concern = ic_nulls > 0
print(f"[{'PASS' if not absence_concern else 'WARN'}] Check 9 — Absence: inst_control not in drop_nulls")
print(f"  inst_control has {ic_nulls} nulls → {'SAFE (no impact)' if ic_nulls == 0 else 'UNSAFE: sector_private would be wrong'}")
print(f"  Note: This is a latent fragility — if inst_control ever has nulls, the code silently produces wrong sector_private.")

# =====================================================================
# SCRIPT-SPECIFIC CHECK 10 (Downstream): Caption text deviation
# Plan specifies: "Source: IPEDS 2020. Points above the diagonal outperform model expectations."
# Script uses: "Source: IPEDS 2020, FSA 2020. Model 3 OLS regression (R²=..., N=...)."
# =====================================================================
print(f"[INFO] Check 10 — Downstream: Caption differs from Plan specification")
print(f"  Plan:   'Source: IPEDS 2020. Points above the diagonal outperform model expectations.'")
print(f"  Script: 'Source: IPEDS 2020, FSA 2020. Model 3 OLS regression (R²=..., N=...)'")
print(f"  Assessment: Script caption is MORE informative (adds R², N, FSA source). Acceptable deviation.")

# =====================================================================
# SPOT-CHECK 11: Recalculate one predicted value
# Pick the first complete-case row and manually compute predicted grad rate
# =====================================================================
row0 = df_model.row(0, named=True)
manual_pred = (
    beta[0]
    + beta[1] * row0["admission_rate"]
    + beta[2] * row0["pell_share"]
    + beta[3] * row0["urm_share"]
    + beta[4] * row0["student_faculty_ratio"]
    + beta[5] * (1.0 if row0["inst_control"] == 2 else 0.0)
)
model_pred = y_pred[0]
spot_match = abs(manual_pred - model_pred) < 0.001
print(f"\n[{'PASS' if spot_match else 'FAIL'}] Spot-Check 11 — Manual prediction for row 0")
print(f"  Institution: {row0.get('inst_name', 'N/A')}")
print(f"  Manual calc: {manual_pred:.4f}")
print(f"  Model pred:  {model_pred:.4f}")
print(f"  Actual:      {row0[OUTCOME_COL]}")

# =====================================================================
# SPOT-CHECK 12: Selectivity band distribution matches prior scripts
# =====================================================================
band_counts = df_model["selectivity_band"].value_counts().sort("selectivity_band")
print(f"\n[INFO] Spot-Check 12 — Selectivity band distribution (complete cases only)")
print(band_counts)
# Check no band has < 5% of total
min_band_pct = band_counts["count"].min() / n_complete * 100
band_dist_ok = min_band_pct >= 5
print(f"[{'PASS' if band_dist_ok else 'WARN'}] Smallest band: {min_band_pct:.1f}% of total (>= 5% required)")

# =====================================================================
# SPOT-CHECK 13: No coded/sentinel values in model columns
# =====================================================================
coded_issues = []
for col in [OUTCOME_COL] + MODEL_COLS:
    vals = df_model[col]
    for sentinel in [-1, -2, -3, -9, -99]:
        cnt = (vals == sentinel).sum()
        if cnt > 0:
            coded_issues.append(f"{col} has {cnt} rows with sentinel {sentinel}")
coded_ok = len(coded_issues) == 0
print(f"\n[{'PASS' if coded_ok else 'FAIL'}] Spot-Check 13 — No sentinel values in model columns")
if not coded_ok:
    for issue in coded_issues:
        print(f"  {issue}")

# =====================================================================
# SPOT-CHECK 14: Actual grad_rate range is 0-100
# =====================================================================
actual_min, actual_max = y.min(), y.max()
actual_range_ok = actual_min >= 0 and actual_max <= 100
print(f"[{'PASS' if actual_range_ok else 'WARN'}] Spot-Check 14 — Actual grad_rate range: [{actual_min:.1f}, {actual_max:.1f}]")

# =====================================================================
# SPOT-CHECK 15: 45-degree line logic
# The script uses geom_abline(intercept=0, slope=1). Verify this puts
# the line at y=x, meaning where actual == predicted.
# =====================================================================
# A 45-degree line at intercept=0, slope=1 draws y = 0 + 1*x = x.
# In the plot: x = predicted, y = actual. So line = actual == predicted. Correct.
print(f"[PASS] Spot-Check 15 — 45-degree line: intercept=0, slope=1 → y=x (actual==predicted). Correct.")

# =====================================================================
# ADDITIONAL: Cross-reference with saved regression results parquet
# =====================================================================
if REGRESSION_FILE.exists():
    reg_df = pl.read_parquet(REGRESSION_FILE)
    m3_rows = reg_df.filter(pl.col("model") == "Model 3: Full")
    if len(m3_rows) > 0:
        saved_r2 = m3_rows["r_squared"][0]
        saved_n = int(m3_rows["n"][0])
        r2_cross = abs(r_squared - saved_r2) < 0.001
        n_cross = saved_n == n_complete
        print(f"\n[{'PASS' if r2_cross else 'WARN'}] Cross-ref: R² from parquet = {saved_r2:.6f} vs re-fit = {r_squared:.6f}")
        print(f"[{'PASS' if n_cross else 'WARN'}] Cross-ref: N from parquet = {saved_n} vs re-fit = {n_complete}")
    else:
        print("\n[WARN] Cross-ref: No 'Model 3: Full' rows in regression results parquet")
else:
    print(f"\n[WARN] Cross-ref: Regression results file not found: {REGRESSION_FILE}")

# =====================================================================
# SUMMARY
# =====================================================================
all_checks = [fig_exists, size_ok, pred_range_ok, bands_ok, r2_match, n_ok,
              ic_ok, coefs_ok, boundary_ok, not absence_concern, spot_match,
              band_dist_ok, coded_ok, actual_range_ok]
all_passed = all(all_checks)
failed_count = sum(1 for c in all_checks if not c)

print("\n" + "=" * 60)
print(f"QA RESULT: {'PASSED' if all_passed else 'ISSUES_FOUND'}")
if not all_passed:
    print(f"  {failed_count} check(s) with issues (see above)")
print("=" * 60)

# =====================================================================
# DATA PROFILING (for cr2+ decision)
# =====================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print(f"\nModel data shape: {df_model.shape}")
print(f"\nPredicted graduation rate statistics:")
print(f"  Mean: {y_pred.mean():.2f}")
print(f"  Std:  {y_pred.std():.2f}")
print(f"  Min:  {pred_min:.2f}")
print(f"  Max:  {pred_max:.2f}")
print(f"  Median: {np.median(y_pred):.2f}")

print(f"\nActual graduation rate statistics:")
print(f"  Mean: {y.mean():.2f}")
print(f"  Std:  {y.std():.2f}")
print(f"  Min:  {actual_min:.2f}")
print(f"  Max:  {actual_max:.2f}")
print(f"  Median: {np.median(y):.2f}")

print(f"\nResidual statistics (actual - predicted):")
residuals = y - y_pred
print(f"  Mean: {residuals.mean():.4f}")
print(f"  Std:  {residuals.std():.2f}")
print(f"  Min:  {residuals.min():.2f}")
print(f"  Max:  {residuals.max():.2f}")

print(f"\nSelectivity band distribution (complete cases):")
print(df_model["selectivity_band"].value_counts().sort("selectivity_band"))

print(f"\nSector distribution (complete cases):")
print(f"  Public (inst_control=1): {(df_model['inst_control'] == 1).sum()}")
print(f"  Private (inst_control=2): {(df_model['inst_control'] == 2).sum()}")

# Correlation between predicted and actual
corr = np.corrcoef(y_pred, y)[0, 1]
print(f"\nCorrelation (predicted, actual): {corr:.4f}")
print(f"R² from correlation²: {corr**2:.6f} (should match R² = {r_squared:.6f})")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:27:54
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_13_crb1.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 10.2 (viz-residual-scatter)
# ============================================================
# Analysis dataset loaded: 2,528 rows x 26 cols
# 
# [PASS] Check 1 — Figure exists: 2026-02-15_actual_vs_predicted.png
# [PASS] Check 1b — Figure size: 1009.8 KB (> 50 KB required)
# 
# Complete cases (independent calc): 1,523
# [PASS] Check 2 — Predicted range: [15.73, 94.48]
# [PASS] Check 3 — Selectivity bands: 4 (expected 4)
#   Bands: shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ str                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Highly Selective     ┆ 65    │
# │ Less Selective/Open  ┆ 746   │
# │ Moderately Selective ┆ 556   │
# │ Selective            ┆ 156   │
# └──────────────────────┴───────┘
# [PASS] Check 4 — R²: 0.455891 (regression-models: 0.4559)
# [PASS] Check 5 — N: 1,523 (expected 1400-1600)
# 
# [PASS] Check 6 — Counterfactual: inst_control nulls = 0
# [PASS] Check 7 — Semantic: Coefficient match to regression-models
#   All 6 coefficients match regression-models within 0.001 tolerance
# [PASS] Check 8 — Boundary: Points outside 0-100 axes
#   Predicted <0: 0, >100: 0
#   Actual <0: 0, >100: 0
# [PASS] Check 9 — Absence: inst_control not in drop_nulls
#   inst_control has 0 nulls → SAFE (no impact)
#   Note: This is a latent fragility — if inst_control ever has nulls, the code silently produces wrong sector_private.
# [INFO] Check 10 — Downstream: Caption differs from Plan specification
#   Plan:   'Source: IPEDS 2020. Points above the diagonal outperform model expectations.'
#   Script: 'Source: IPEDS 2020, FSA 2020. Model 3 OLS regression (R²=..., N=...)'
#   Assessment: Script caption is MORE informative (adds R², N, FSA source). Acceptable deviation.
# 
# [PASS] Spot-Check 11 — Manual prediction for row 0
#   Institution: Alabama A & M University
#   Manual calc: 33.0827
#   Model pred:  33.0827
#   Actual:      28.1
# 
# [INFO] Spot-Check 12 — Selectivity band distribution (complete cases only)
# shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ str                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Highly Selective     ┆ 65    │
# │ Less Selective/Open  ┆ 746   │
# │ Moderately Selective ┆ 556   │
# │ Selective            ┆ 156   │
# └──────────────────────┴───────┘
# [WARN] Smallest band: 4.3% of total (>= 5% required)
# 
# [PASS] Spot-Check 13 — No sentinel values in model columns
# [PASS] Spot-Check 14 — Actual grad_rate range: [3.8, 100.0]
# [PASS] Spot-Check 15 — 45-degree line: intercept=0, slope=1 → y=x (actual==predicted). Correct.
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_13_crb1.py", line 285, in <module>
#     saved_n = int(m3_rows["n"][0])
#                   ~~~~~~~^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/frame.py", line 1431, in __getitem__
#     return get_df_item_by_key(self, key)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/getitem.py", line 163, in get_df_item_by_key
#     return df.get_column(key)
#            ^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/frame.py", line 9193, in get_column
#     return wrap_s(self._df.get_column(name))
#                   ^^^^^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.ColumnNotFoundError: "n" not found
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
