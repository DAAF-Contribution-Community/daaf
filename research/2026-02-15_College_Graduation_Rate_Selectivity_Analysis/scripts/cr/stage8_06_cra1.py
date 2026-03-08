#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 06 — QA4a (Statistical Validity)

Reviewed script: scripts/stage8_analysis/06_regression-models.py
Output files: output/analysis/2026-02-15_regression_results.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default 5):
1. Schema matches Plan expectations
2. Row count within expected range (24 rows)
3. No suspicious distributions in coefficients
4. R-squared values in valid range
5. No nulls in critical columns

Script-Specific Checks (5 Skeptical Lenses):
6. [Counterfactual] Would results change if listwise deletion dropped different rows?
7. [Semantic] Does the R-squared decomposition actually answer the research question?
8. [Boundary] Are coefficient magnitudes plausible given variable scales?
9. [Absence] Is VIF correctly computed — does the output include all 5 predictors?
10. [Downstream] Will the residual-scatter task (Wave 10) get what it needs?

Spot-Checks (5 Concrete):
11. Recalculate R-squared from coefficients and raw data
12. Verify admission_rate coefficient sign consistency across all 3 models
13. Verify N=1523 matches the listwise deletion count
14. Verify VIF for pell_share by independent calculation
15. Verify Model 2 R-squared delta from comparison rows matches model rows
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_regression_results.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
EXPECTED_COLUMNS = ["model", "variable", "coefficient", "std_error", "t_statistic", "p_value", "r_squared", "adj_r_squared", "n_obs"]
EXPECTED_MIN_ROWS = 20
EXPECTED_MAX_ROWS = 30
CRITICAL_COLUMNS = ["model", "variable", "coefficient", "std_error", "t_statistic", "p_value", "r_squared"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 06 — QA4a (Regression Models)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded results: {df.shape[0]:,} rows x {df.shape[1]} cols")

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
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# Verify 24 rows per orchestrator expectation
print(f"  Exact row count = {row_count} (expected 24)")

# --- Check 3: Distributions of coefficients ---
# Coefficients should not all be zero or all same value
coeff_rows = df.filter(pl.col("model") != "Diagnostics").filter(pl.col("model") != "Comparison")
coeff_vals = coeff_rows["coefficient"].drop_nulls()
dist_ok = coeff_vals.n_unique() > 1 and not (coeff_vals == 0).all()
print(f"[{'PASS' if dist_ok else 'FAIL'}] Coefficient distribution: {coeff_vals.n_unique()} unique values, range [{coeff_vals.min():.4f}, {coeff_vals.max():.4f}]")

# --- Check 4: R-squared values in [0, 1] ---
r2_vals = df.filter(pl.col("model") != "Diagnostics")["r_squared"].drop_nulls()
r2_ok = (r2_vals >= 0).all() and (r2_vals <= 1).all()
print(f"[{'PASS' if r2_ok else 'FAIL'}] R-squared in [0,1]: min={r2_vals.min():.4f}, max={r2_vals.max():.4f}")

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

# ============================================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# ============================================================
print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# Load source data for independent verification
df_src = pl.read_parquet(INPUT_FILE)
print(f"\nLoaded source data: {df_src.shape[0]:,} rows x {df_src.shape[1]} cols")

# --- Check 6: [Counterfactual] Characterize listwise deletion bias ---
# If dropped rows are systematically different, results may not generalize
CRITICAL_COLS = ["grad_rate_150pct", "admission_rate", "pell_share", "urm_share",
                 "student_faculty_ratio", "inst_control"]
complete_mask = df_src.select(
    pl.all_horizontal([pl.col(c).is_not_null() for c in CRITICAL_COLS]).alias("complete")
)["complete"]
df_complete = df_src.filter(complete_mask)
df_dropped = df_src.filter(~complete_mask)

print(f"\n[CHECK 6] Counterfactual — Listwise deletion bias:")
print(f"  Complete cases: {len(df_complete):,}")
print(f"  Dropped cases: {len(df_dropped):,}")
# Compare grad_rate_150pct between kept and dropped (where available)
kept_gr = df_complete["grad_rate_150pct"].drop_nulls()
dropped_gr = df_dropped["grad_rate_150pct"].drop_nulls()
if len(dropped_gr) > 0:
    gap = kept_gr.mean() - dropped_gr.mean()
    print(f"  Kept mean grad_rate: {kept_gr.mean():.2f}")
    print(f"  Dropped mean grad_rate: {dropped_gr.mean():.2f}")
    print(f"  Gap: {gap:.2f} pp (prior EDA found ~14pp gap)")
    counterfactual_ok = True  # INFO-level, not a BLOCKER
    if abs(gap) > 20:
        print(f"  [WARN] Large gap >20pp — selection bias may affect interpretation")
    else:
        print(f"  [INFO] Gap consistent with prior EDA findings")
else:
    print(f"  [INFO] No grad_rate data for dropped cases — cannot compare")
    counterfactual_ok = True

# --- Check 7: [Semantic] Does R-squared decomposition answer the research question? ---
# The key claim is M1->M2 delta > 0.10. Verify the structure supports this claim.
m1_r2_row = df.filter((pl.col("model") == "Comparison") & (pl.col("variable") == "R2_model1"))
m2_r2_row = df.filter((pl.col("model") == "Comparison") & (pl.col("variable") == "R2_model2"))
delta_row = df.filter((pl.col("model") == "Comparison") & (pl.col("variable") == "R2_delta_M1_to_M2"))

semantic_ok = True
print(f"\n[CHECK 7] Semantic — R-squared decomposition structure:")
if len(m1_r2_row) == 1 and len(m2_r2_row) == 1 and len(delta_row) == 1:
    m1_r2 = m1_r2_row["coefficient"][0]
    m2_r2 = m2_r2_row["coefficient"][0]
    stored_delta = delta_row["coefficient"][0]
    computed_delta = m2_r2 - m1_r2
    print(f"  M1 R2 = {m1_r2:.4f}")
    print(f"  M2 R2 = {m2_r2:.4f}")
    print(f"  Stored delta = {stored_delta:.4f}")
    print(f"  Computed delta = {computed_delta:.4f}")
    delta_match = abs(stored_delta - computed_delta) < 1e-10
    print(f"  [{'PASS' if delta_match else 'FAIL'}] Delta consistency: stored matches computed")
    if not delta_match:
        semantic_ok = False
    # Observable Truth check
    obs_truth_met = stored_delta > 0.10
    print(f"  [{'PASS' if obs_truth_met else 'FAIL'}] Observable Truth (delta > 0.10): {stored_delta:.4f}")
    if not obs_truth_met:
        semantic_ok = False
        print(f"  [BLOCKER] Observable Truth NOT satisfied")
else:
    print(f"  [FAIL] Missing comparison rows: M1={len(m1_r2_row)}, M2={len(m2_r2_row)}, delta={len(delta_row)}")
    semantic_ok = False

# --- Check 8: [Boundary] Coefficient magnitudes given variable scales ---
# admission_rate is 0-1 proportion. A coefficient of -32.55 means going from
# 0% admission (perfectly selective) to 100% admission rate reduces grad_rate
# by ~32.5 percentage points. Is this plausible?
print(f"\n[CHECK 8] Boundary — Coefficient scale plausibility:")
m1_coefs = df.filter(pl.col("model") == "Model 1: Selectivity Only")
adm_coef_m1 = m1_coefs.filter(pl.col("variable") == "admission_rate")["coefficient"][0]
intercept_m1 = m1_coefs.filter(pl.col("variable") == "intercept")["coefficient"][0]
# Predicted grad rate at admission_rate=0: intercept ~ 81
# Predicted grad rate at admission_rate=1: intercept + coef ~ 81 - 33 = 48
pred_at_0 = intercept_m1
pred_at_1 = intercept_m1 + adm_coef_m1
boundary_ok = (0 < pred_at_0 < 100) and (0 < pred_at_1 < 100)
print(f"  M1 intercept: {intercept_m1:.2f} (predicted grad rate at admission_rate=0)")
print(f"  M1 admission_rate coef: {adm_coef_m1:.2f}")
print(f"  Predicted grad rate at adm_rate=0: {pred_at_0:.2f}%")
print(f"  Predicted grad rate at adm_rate=1: {pred_at_1:.2f}%")
print(f"  [{'PASS' if boundary_ok else 'WARN'}] Predictions in reasonable range [0, 100]")

# Check Model 3 — pell_share coefficient
m3_coefs = df.filter(pl.col("model") == "Model 3: Full")
pell_coef_m3 = m3_coefs.filter(pl.col("variable") == "pell_share")["coefficient"][0]
# pell_share is 0-1 proportion. Coef of -60.6 means going from 0% Pell to
# 100% Pell reduces grad rate by ~60.6pp. That's a huge effect — plausible?
print(f"  M3 pell_share coef: {pell_coef_m3:.2f} (full range effect: {pell_coef_m3:.1f}pp)")
# With other variables held constant, this is plausible since pell_share and
# selectivity are correlated — holding selectivity constant isolates Pell effect
pell_boundary_ok = -100 < pell_coef_m3 < 0
print(f"  [{'PASS' if pell_boundary_ok else 'WARN'}] pell_share coefficient sign and magnitude plausible")

# --- Check 9: [Absence] VIF completeness and correctness ---
print(f"\n[CHECK 9] Absence — VIF analysis completeness:")
vif_rows = df.filter((pl.col("model") == "Diagnostics") & (pl.col("variable").str.starts_with("VIF_")))
expected_vif_vars = ["VIF_admission_rate", "VIF_pell_share", "VIF_urm_share",
                     "VIF_student_faculty_ratio", "VIF_sector_private"]
actual_vif_vars = vif_rows["variable"].to_list()
vif_complete = set(expected_vif_vars) == set(actual_vif_vars)
print(f"  Expected VIF variables: {expected_vif_vars}")
print(f"  Actual VIF variables: {actual_vif_vars}")
print(f"  [{'PASS' if vif_complete else 'FAIL'}] All 5 VIF values present")

# Check all VIF > 1 (mathematical property: VIF is always >= 1)
vif_values = vif_rows["coefficient"].to_list()
all_vif_above_1 = all(v >= 1.0 for v in vif_values)
print(f"  VIF values: {[f'{v:.3f}' for v in vif_values]}")
print(f"  [{'PASS' if all_vif_above_1 else 'FAIL'}] All VIF >= 1.0 (mathematical property)")

# Check for concerning VIF > 5 (from risk register)
any_concerning = any(v > 5 for v in vif_values)
print(f"  [{'PASS' if not any_concerning else 'WARN'}] No VIF > 5 (collinearity threshold)")

# --- Check 10: [Downstream] Does output support viz-residual-scatter (Wave 10)? ---
# That task needs: predicted grad_rate from Model 3, i.e., model coefficients to
# recompute predictions. Check that Model 3 has all needed coefficients saved.
print(f"\n[CHECK 10] Downstream — viz-residual-scatter compatibility:")
m3_vars = df.filter(pl.col("model") == "Model 3: Full")["variable"].to_list()
needed_vars = ["intercept", "admission_rate", "pell_share", "urm_share",
               "student_faculty_ratio", "sector_private"]
missing_for_downstream = [v for v in needed_vars if v not in m3_vars]
downstream_ok = len(missing_for_downstream) == 0
print(f"  M3 variables saved: {m3_vars}")
print(f"  Needed for downstream: {needed_vars}")
print(f"  [{'PASS' if downstream_ok else 'FAIL'}] All coefficients available for prediction reconstruction")

# Also check n_obs is stored (needed for downstream interpretation)
m3_n = df.filter(pl.col("model") == "Model 3: Full")["n_obs"].unique().to_list()
print(f"  n_obs in M3 rows: {m3_n}")

# ============================================================
# SPOT-CHECKS (5 Concrete)
# ============================================================
print("\n" + "=" * 60)
print("CONCRETE SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Independent R-squared recalculation ---
print(f"\n[SPOT-CHECK 11] Independent R-squared recalculation for Model 1:")
# Reproduce Model 1 from source data
reg_cols = ["grad_rate_150pct", "admission_rate", "pell_share", "urm_share",
            "student_faculty_ratio", "inst_control"]
df_reg = df_src.drop_nulls(subset=reg_cols)
y = df_reg["grad_rate_150pct"].to_numpy().astype(np.float64)
x_adm = df_reg["admission_rate"].to_numpy().astype(np.float64)

N_check = len(y)
ones = np.ones((N_check, 1))
X = np.hstack([ones, x_adm.reshape(-1, 1)])
beta = np.linalg.solve(X.T @ X, X.T @ y)
y_hat = X @ beta
ss_res = np.sum((y - y_hat)**2)
ss_tot = np.sum((y - np.mean(y))**2)
r2_check = 1 - ss_res / ss_tot

stored_r2_m1 = df.filter((pl.col("model") == "Model 1: Selectivity Only") &
                          (pl.col("variable") == "intercept"))["r_squared"][0]
r2_match = abs(r2_check - stored_r2_m1) < 1e-8
print(f"  Independent R2 = {r2_check:.6f}")
print(f"  Stored R2 = {stored_r2_m1:.6f}")
print(f"  [{'PASS' if r2_match else 'FAIL'}] R-squared matches independent calculation")

# --- Spot-Check 12: admission_rate sign consistency across models ---
print(f"\n[SPOT-CHECK 12] admission_rate coefficient sign across all 3 models:")
adm_coefs = {}
for model_name in ["Model 1: Selectivity Only", "Model 2: + Composition", "Model 3: Full"]:
    row = df.filter((pl.col("model") == model_name) & (pl.col("variable") == "admission_rate"))
    if len(row) == 1:
        adm_coefs[model_name] = row["coefficient"][0]
        print(f"  {model_name}: {adm_coefs[model_name]:.4f}")
all_negative = all(v < 0 for v in adm_coefs.values())
print(f"  [{'PASS' if all_negative else 'FAIL'}] All admission_rate coefficients are negative")

# --- Spot-Check 13: N matches listwise deletion ---
print(f"\n[SPOT-CHECK 13] Sample size verification:")
n_from_output = df.filter(pl.col("model") == "Model 1: Selectivity Only")["n_obs"][0]
n_from_source = len(df_reg)
n_match = n_from_output == n_from_source
print(f"  N from output parquet: {n_from_output}")
print(f"  N from independent listwise deletion: {n_from_source}")
print(f"  [{'PASS' if n_match else 'FAIL'}] Sample sizes match")

# --- Spot-Check 14: Independent VIF for pell_share ---
print(f"\n[SPOT-CHECK 14] Independent VIF calculation for pell_share:")
x_pell = df_reg["pell_share"].to_numpy().astype(np.float64)
x_urm = df_reg["urm_share"].to_numpy().astype(np.float64)
x_sfr = df_reg["student_faculty_ratio"].to_numpy().astype(np.float64)
x_private = (df_reg["inst_control"].to_numpy() == 2).astype(np.float64)

# Regress pell_share on other predictors (admission_rate, urm_share, sfr, sector_private)
X_others = np.column_stack([ones, x_adm.reshape(-1, 1), x_urm.reshape(-1, 1),
                             x_sfr.reshape(-1, 1), x_private.reshape(-1, 1)])
beta_vif = np.linalg.solve(X_others.T @ X_others, X_others.T @ x_pell)
y_hat_vif = X_others @ beta_vif
ss_res_vif = np.sum((x_pell - y_hat_vif)**2)
ss_tot_vif = np.sum((x_pell - np.mean(x_pell))**2)
r2_vif = 1 - ss_res_vif / ss_tot_vif
vif_independent = 1 / (1 - r2_vif)

stored_vif_pell = df.filter((pl.col("model") == "Diagnostics") &
                             (pl.col("variable") == "VIF_pell_share"))["coefficient"][0]
vif_match = abs(vif_independent - stored_vif_pell) < 0.01
print(f"  Independent VIF = {vif_independent:.4f}")
print(f"  Stored VIF = {stored_vif_pell:.4f}")
print(f"  [{'PASS' if vif_match else 'FAIL'}] VIF matches independent calculation")

# --- Spot-Check 15: Delta M1->M2 consistency ---
print(f"\n[SPOT-CHECK 15] R-squared delta consistency:")
# Get R-squared from Model 1 and Model 2 coefficient rows
m1_r2_from_coef = df.filter((pl.col("model") == "Model 1: Selectivity Only") &
                              (pl.col("variable") == "intercept"))["r_squared"][0]
m2_r2_from_coef = df.filter((pl.col("model") == "Model 2: + Composition") &
                              (pl.col("variable") == "intercept"))["r_squared"][0]
delta_from_coef_rows = m2_r2_from_coef - m1_r2_from_coef

delta_from_comparison = df.filter((pl.col("model") == "Comparison") &
                                   (pl.col("variable") == "R2_delta_M1_to_M2"))["coefficient"][0]

delta_consistent = abs(delta_from_coef_rows - delta_from_comparison) < 1e-10
print(f"  Delta from coefficient rows: {delta_from_coef_rows:.6f}")
print(f"  Delta from comparison rows: {delta_from_comparison:.6f}")
print(f"  [{'PASS' if delta_consistent else 'FAIL'}] Deltas are consistent")

# ============================================================
# DATA PROFILING (for cra2+ decision)
# ============================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nAll 24 rows:")
with pl.Config(tbl_rows=30, tbl_cols=12, fmt_str_lengths=40):
    print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nModel distribution:")
print(df["model"].value_counts().sort("model"))

print("\nVariable distribution:")
print(df["variable"].value_counts().sort("variable"))

# Key: urm_share is NOT significant in any model (p=0.965 in M2, 0.650 in M3)
# This is a notable finding for the research question
print("\n" + "-" * 60)
print("NOTABLE FINDING: urm_share coefficient")
print("-" * 60)
for model_name in ["Model 2: + Composition", "Model 3: Full"]:
    urm_row = df.filter((pl.col("model") == model_name) & (pl.col("variable") == "urm_share"))
    if len(urm_row) == 1:
        coef = urm_row["coefficient"][0]
        p = urm_row["p_value"][0]
        print(f"  {model_name}: coef={coef:.4f}, p={p:.4f}")
print("  urm_share is NOT significant in either model after controlling for")
print("  admission_rate and pell_share. Pell_share absorbs the URM effect.")
print("  This is consistent with prior EDA collinearity finding (r=0.638)")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)

all_default_passed = all([schema_ok, rows_ok, dist_ok, r2_ok, nulls_ok])
all_specific_passed = all([counterfactual_ok, semantic_ok, boundary_ok, vif_complete,
                           all_vif_above_1, downstream_ok])
all_spot_passed = all([r2_match, all_negative, n_match, vif_match, delta_consistent])
all_passed = all_default_passed and all_specific_passed and all_spot_passed

severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA4a RESULT: {severity}")
print(f"  Default checks: {'PASSED' if all_default_passed else 'ISSUES'}")
print(f"  Script-specific checks: {'PASSED' if all_specific_passed else 'ISSUES'}")
print(f"  Spot-checks: {'PASSED' if all_spot_passed else 'ISSUES'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:08:57
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_06_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 06 — QA4a (Regression Models)
# ============================================================
# Loaded results: 24 rows x 9 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 24 (expected 20-30)
#   Exact row count = 24 (expected 24)
# [PASS] Coefficient distribution: 12 unique values, range [-60.5583, 97.9710]
# [PASS] R-squared in [0,1]: min=0.0000, max=0.4559
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# Loaded source data: 2,528 rows x 26 cols
# 
# [CHECK 6] Counterfactual — Listwise deletion bias:
#   Complete cases: 1,523
#   Dropped cases: 1,005
#   Kept mean grad_rate: 58.16
#   Dropped mean grad_rate: 46.50
#   Gap: 11.67 pp (prior EDA found ~14pp gap)
#   [INFO] Gap consistent with prior EDA findings
# 
# [CHECK 7] Semantic — R-squared decomposition structure:
#   M1 R2 = 0.1273
#   M2 R2 = 0.4534
#   Stored delta = 0.3261
#   Computed delta = 0.3261
#   [PASS] Delta consistency: stored matches computed
#   [PASS] Observable Truth (delta > 0.10): 0.3261
# 
# [CHECK 8] Boundary — Coefficient scale plausibility:
#   M1 intercept: 81.10 (predicted grad rate at admission_rate=0)
#   M1 admission_rate coef: -32.55
#   Predicted grad rate at adm_rate=0: 81.10%
#   Predicted grad rate at adm_rate=1: 48.55%
#   [PASS] Predictions in reasonable range [0, 100]
#   M3 pell_share coef: -60.56 (full range effect: -60.6pp)
#   [PASS] pell_share coefficient sign and magnitude plausible
# 
# [CHECK 9] Absence — VIF analysis completeness:
#   Expected VIF variables: ['VIF_admission_rate', 'VIF_pell_share', 'VIF_urm_share', 'VIF_student_faculty_ratio', 'VIF_sector_private']
#   Actual VIF variables: ['VIF_admission_rate', 'VIF_pell_share', 'VIF_urm_share', 'VIF_student_faculty_ratio', 'VIF_sector_private']
#   [PASS] All 5 VIF values present
#   VIF values: ['1.107', '1.816', '1.781', '1.451', '1.412']
#   [PASS] All VIF >= 1.0 (mathematical property)
#   [PASS] No VIF > 5 (collinearity threshold)
# 
# [CHECK 10] Downstream — viz-residual-scatter compatibility:
#   M3 variables saved: ['intercept', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'sector_private']
#   Needed for downstream: ['intercept', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'sector_private']
#   [PASS] All coefficients available for prediction reconstruction
#   n_obs in M3 rows: [1523]
# 
# ============================================================
# CONCRETE SPOT-CHECKS
# ============================================================
# 
# [SPOT-CHECK 11] Independent R-squared recalculation for Model 1:
#   Independent R2 = 0.127323
#   Stored R2 = 0.127323
#   [PASS] R-squared matches independent calculation
# 
# [SPOT-CHECK 12] admission_rate coefficient sign across all 3 models:
#   Model 1: Selectivity Only: -32.5497
#   Model 2: + Composition: -24.0574
#   Model 3: Full: -22.9603
#   [PASS] All admission_rate coefficients are negative
# 
# [SPOT-CHECK 13] Sample size verification:
#   N from output parquet: 1523
#   N from independent listwise deletion: 1523
#   [PASS] Sample sizes match
# 
# [SPOT-CHECK 14] Independent VIF calculation for pell_share:
#   Independent VIF = 1.8158
#   Stored VIF = 1.8158
#   [PASS] VIF matches independent calculation
# 
# [SPOT-CHECK 15] R-squared delta consistency:
#   Delta from coefficient rows: 0.326102
#   Delta from comparison rows: 0.326102
#   [PASS] Deltas are consistent
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# All 24 rows:
# shape: (24, 9)
# ┌───────────┬───────────┬───────────┬──────────┬──────────┬──────────┬──────────┬──────────┬───────┐
# │ model     ┆ variable  ┆ coefficie ┆ std_erro ┆ t_statis ┆ p_value  ┆ r_square ┆ adj_r_sq ┆ n_obs │
# │ ---       ┆ ---       ┆ nt        ┆ r        ┆ tic      ┆ ---      ┆ d        ┆ uared    ┆ ---   │
# │ str       ┆ str       ┆ ---       ┆ ---      ┆ ---      ┆ f64      ┆ ---      ┆ ---      ┆ i64   │
# │           ┆           ┆ f64       ┆ f64      ┆ f64      ┆          ┆ f64      ┆ f64      ┆       │
# ╞═══════════╪═══════════╪═══════════╪══════════╪══════════╪══════════╪══════════╪══════════╪═══════╡
# │ Model 1:  ┆ intercept ┆ 81.095104 ┆ 1.601566 ┆ 50.63488 ┆ 0.0      ┆ 0.127323 ┆ 0.126749 ┆ 1523  │
# │ Selectivi ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ ty Only   ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 1:  ┆ admission ┆ -32.54974 ┆ 2.185023 ┆ -14.8967 ┆ 5.9629e- ┆ 0.127323 ┆ 0.126749 ┆ 1523  │
# │ Selectivi ┆ _rate     ┆ 7         ┆          ┆ 54       ┆ 47       ┆          ┆          ┆       │
# │ ty Only   ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 2:  ┆ intercept ┆ 97.97096  ┆ 1.38919  ┆ 70.52379 ┆ 0.0      ┆ 0.453425 ┆ 0.452346 ┆ 1523  │
# │ + Composi ┆           ┆           ┆          ┆ 2        ┆          ┆          ┆          ┆       │
# │ tion      ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 2:  ┆ admission ┆ -24.05741 ┆ 1.771282 ┆ -13.5819 ┆ 9.6907e- ┆ 0.453425 ┆ 0.452346 ┆ 1523  │
# │ + Composi ┆ _rate     ┆           ┆          ┆ 18       ┆ 40       ┆          ┆          ┆       │
# │ tion      ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 2:  ┆ pell_shar ┆ -60.35225 ┆ 2.623204 ┆ -23.0070 ┆ 9.7654e- ┆ 0.453425 ┆ 0.452346 ┆ 1523  │
# │ + Composi ┆ e         ┆ 4         ┆          ┆ 79       ┆ 101      ┆          ┆          ┆       │
# │ tion      ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 2:  ┆ urm_share ┆ -0.089984 ┆ 2.045626 ┆ -0.04398 ┆ 0.964919 ┆ 0.453425 ┆ 0.452346 ┆ 1523  │
# │ + Composi ┆           ┆           ┆          ┆ 8        ┆          ┆          ┆          ┆       │
# │ tion      ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 3:  ┆ intercept ┆ 97.749405 ┆ 1.996572 ┆ 48.95862 ┆ 0.0      ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ Full      ┆           ┆           ┆          ┆ 7        ┆          ┆          ┆          ┆       │
# │ Model 3:  ┆ admission ┆ -22.96030 ┆ 1.817313 ┆ -12.6342 ┆ 7.2887e- ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ Full      ┆ _rate     ┆ 1         ┆          ┆ 03       ┆ 35       ┆          ┆          ┆       │
# │ Model 3:  ┆ pell_shar ┆ -60.55827 ┆ 2.665152 ┆ -22.7222 ┆ 1.3025e- ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ Full      ┆ e         ┆ 9         ┆          ┆ 6        ┆ 98       ┆          ┆          ┆       │
# │ Model 3:  ┆ urm_share ┆ 0.945381  ┆ 2.085696 ┆ 0.453269 ┆ 0.65042  ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ Full      ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 3:  ┆ student_f ┆ -0.114461 ┆ 0.090198 ┆ -1.26899 ┆ 0.204637 ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ Full      ┆ aculty_ra ┆           ┆          ┆ 6        ┆          ┆          ┆          ┆       │
# │           ┆ tio       ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Model 3:  ┆ sector_pr ┆ 1.221654  ┆ 0.88272  ┆ 1.383964 ┆ 0.166573 ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ Full      ┆ ivate     ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Compariso ┆ R2_model1 ┆ 0.127323  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.127323 ┆ 0.126749 ┆ 1523  │
# │ n         ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Compariso ┆ R2_model2 ┆ 0.453425  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.453425 ┆ 0.452346 ┆ 1523  │
# │ n         ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Compariso ┆ R2_model3 ┆ 0.455891  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.455891 ┆ 0.454098 ┆ 1523  │
# │ n         ┆           ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Compariso ┆ R2_delta_ ┆ 0.326102  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ n         ┆ M1_to_M2  ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Compariso ┆ R2_delta_ ┆ 0.002466  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ n         ┆ M2_to_M3  ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ VIF_admis ┆ 1.106551  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ sion_rate ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ VIF_pell_ ┆ 1.815776  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ share     ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ VIF_urm_s ┆ 1.781263  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ hare      ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ VIF_stude ┆ 1.451308  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ nt_facult ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │           ┆ y_ratio   ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ VIF_secto ┆ 1.411505  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ r_private ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ resid_mea ┆ 3.7323e-1 ┆ 13.58931 ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ n         ┆ 5         ┆ 9        ┆          ┆          ┆          ┆          ┆       │
# │ Diagnosti ┆ resid_std ┆ 1.252688  ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 0.0      ┆ 1523  │
# │ cs        ┆ _ratio    ┆           ┆          ┆          ┆          ┆          ┆          ┆       │
# └───────────┴───────────┴───────────┴──────────┴──────────┴──────────┴──────────┴──────────┴───────┘
# 
# Descriptive statistics:
# shape: (9, 10)
# ┌────────────┬────────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬────────┐
# │ statistic  ┆ model      ┆ variable  ┆ coefficie ┆ … ┆ p_value   ┆ r_squared ┆ adj_r_squ ┆ n_obs  │
# │ ---        ┆ ---        ┆ ---       ┆ nt        ┆   ┆ ---       ┆ ---       ┆ ared      ┆ ---    │
# │ str        ┆ str        ┆ str       ┆ ---       ┆   ┆ f64       ┆ f64       ┆ ---       ┆ f64    │
# │            ┆            ┆           ┆ f64       ┆   ┆           ┆           ┆ f64       ┆        │
# ╞════════════╪════════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪════════╡
# │ count      ┆ 24         ┆ 24        ┆ 24.0      ┆ … ┆ 24.0      ┆ 24.0      ┆ 24.0      ┆ 24.0   │
# │ null_count ┆ 0          ┆ 0         ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0    │
# │ mean       ┆ null       ┆ null      ┆ 3.686849  ┆ … ┆ 0.082773  ┆ 0.243347  ┆ 0.242528  ┆ 1523.0 │
# │ std        ┆ null       ┆ null      ┆ 38.950843 ┆ … ┆ 0.233992  ┆ 0.219707  ┆ 0.218994  ┆ 0.0    │
# │ min        ┆ Comparison ┆ R2_delta_ ┆ -60.55827 ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 1523.0 │
# │            ┆            ┆ M1_to_M2  ┆ 9         ┆   ┆           ┆           ┆           ┆        │
# │ 25%        ┆ null       ┆ null      ┆ -0.089984 ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 1523.0 │
# │ 50%        ┆ null       ┆ null      ┆ 0.455891  ┆ … ┆ 0.0       ┆ 0.453425  ┆ 0.452346  ┆ 1523.0 │
# │ 75%        ┆ null       ┆ null      ┆ 1.411505  ┆ … ┆ 5.9629e-4 ┆ 0.455891  ┆ 0.454098  ┆ 1523.0 │
# │            ┆            ┆           ┆           ┆   ┆ 7         ┆           ┆           ┆        │
# │ max        ┆ Model 3:   ┆ urm_share ┆ 97.97096  ┆ … ┆ 0.964919  ┆ 0.455891  ┆ 0.454098  ┆ 1523.0 │
# │            ┆ Full       ┆           ┆           ┆   ┆           ┆           ┆           ┆        │
# └────────────┴────────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴────────┘
# 
# Model distribution:
# shape: (5, 2)
# ┌───────────────────────────┬───────┐
# │ model                     ┆ count │
# │ ---                       ┆ ---   │
# │ str                       ┆ u32   │
# ╞═══════════════════════════╪═══════╡
# │ Comparison                ┆ 5     │
# │ Diagnostics               ┆ 7     │
# │ Model 1: Selectivity Only ┆ 2     │
# │ Model 2: + Composition    ┆ 4     │
# │ Model 3: Full             ┆ 6     │
# └───────────────────────────┴───────┘
# 
# Variable distribution:
# shape: (18, 2)
# ┌───────────────────────┬───────┐
# │ variable              ┆ count │
# │ ---                   ┆ ---   │
# │ str                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ R2_delta_M1_to_M2     ┆ 1     │
# │ R2_delta_M2_to_M3     ┆ 1     │
# │ R2_model1             ┆ 1     │
# │ R2_model2             ┆ 1     │
# │ R2_model3             ┆ 1     │
# │ …                     ┆ …     │
# │ resid_mean            ┆ 1     │
# │ resid_std_ratio       ┆ 1     │
# │ sector_private        ┆ 1     │
# │ student_faculty_ratio ┆ 1     │
# │ urm_share             ┆ 2     │
# └───────────────────────┴───────┘
# 
# ------------------------------------------------------------
# NOTABLE FINDING: urm_share coefficient
# ------------------------------------------------------------
#   Model 2: + Composition: coef=-0.0900, p=0.9649
#   Model 3: Full: coef=0.9454, p=0.6504
#   urm_share is NOT significant in either model after controlling for
#   admission_rate and pell_share. Pell_share absorbs the URM effect.
#   This is consistent with prior EDA collinearity finding (r=0.638)
# 
# ============================================================
# QA4a RESULT: PASSED
#   Default checks: PASSED
#   Script-specific checks: PASSED
#   Spot-checks: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
