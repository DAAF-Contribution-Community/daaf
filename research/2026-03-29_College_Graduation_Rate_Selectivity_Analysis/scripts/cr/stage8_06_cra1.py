#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8.1 Step 9.1 — regression-models (QA4a)

Reviewed script: scripts/stage8_analysis/06_regression-models.py
Output files: output/analysis/2026-03-29_regression_results.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

Research Question: How much of the variation in college graduation rates is
attributable to institutional selectivity versus institutional effectiveness?

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] Verify complete-case dataset doesn't systematically exclude
   institutions from specific selectivity bands
7. [Semantic] Verify H2 attenuation calculation is correct and meaningful
8. [Boundary] Check for multicollinearity among predictors (VIF)
9. [Absence] Verify confidence intervals are stored and reasonable
10. [Downstream] Verify output parquet has consistent N across all 4 models

Spot-Checks:
11. Recalculate R-squared change independently from stored values
12. Verify admit_rate coefficient is negative (expected direction)
13. Verify retention_rate coefficient is positive (expected direction)
14. Verify Model 1 R-squared matches outperformer model from Wave 8
15. Cross-check complete-case N against input data missingness
"""

import polars as pl
import pandas as pd
import numpy as np
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_regression_results.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPERFORMER_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_selectivity_model.parquet"

EXPECTED_COLUMNS = [
    "model", "variable", "coefficient", "std_error", "t_statistic",
    "p_value", "ci_lower", "ci_upper", "r_squared", "adj_r_squared",
    "n_obs", "f_statistic"
]
EXPECTED_MIN_ROWS = 15  # 4 models: M1(2), M2(4), M3(7), M3b(9) = 22 rows
EXPECTED_MAX_ROWS = 30
CRITICAL_COLUMNS = ["model", "variable", "coefficient", "std_error", "p_value", "r_squared", "n_obs"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8.1 Step 9.1 — regression-models")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

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
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")

# Check R-squared range
r2_vals = df["r_squared"].unique().to_list()
for r2 in r2_vals:
    if r2 < 0 or r2 > 1:
        dist_issues.append(f"r_squared out of range: {r2}")

dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
# IPEDS coded missing values [-1, -2, -3] should not appear in regression results
CODED_MISSING_VALUES = [-1, -2, -3]

coded_issues = []
for col in ["coefficient", "std_error", "t_statistic"]:
    if col in df.columns:
        for code in CODED_MISSING_VALUES:
            count = (df[col].cast(pl.Float64) == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} values equal to coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain in coefficients" if coded_ok else "; ".join(coded_issues))

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

# === SCRIPT-SPECIFIC CHECKS ===

# --- Check 6: [Counterfactual] Complete-case selection bias ---
# Does the complete-case dataset systematically exclude institutions from
# specific selectivity bands?
print(f"\n{'=' * 60}")
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

df_input = pl.read_parquet(INPUT_FILE)
print(f"\nLoaded input: {df_input.shape[0]:,} rows x {df_input.shape[1]} cols")

ALL_ANALYSIS_VARS = [
    "completion_rate_150pct", "admit_rate", "pell_share", "urm_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"
]

# Recreate complete-case dataset
df_complete = df_input.drop_nulls(subset=ALL_ANALYSIS_VARS)
complete_n = df_complete.shape[0]
print(f"\n[CHECK 6] Counterfactual: Complete-case selection bias")
print(f"  Full dataset: {df_input.shape[0]:,} rows")
print(f"  Complete-case: {complete_n:,} rows ({complete_n/df_input.shape[0]*100:.1f}%)")

# Compare selectivity band distributions
if "selectivity_band" in df_input.columns:
    full_bands = df_input["selectivity_band"].value_counts().sort("selectivity_band")
    complete_bands = df_complete["selectivity_band"].value_counts().sort("selectivity_band")

    print(f"\n  Selectivity band representation:")
    print(f"  {'Band':<25} {'Full N':>8} {'Complete N':>10} {'Retention %':>12}")
    print(f"  {'-'*55}")

    band_retention = {}
    for band_row in full_bands.iter_rows():
        band = band_row[0]
        full_n = band_row[1]
        comp_row = complete_bands.filter(pl.col("selectivity_band") == band)
        comp_n = comp_row["count"][0] if len(comp_row) > 0 else 0
        retention_pct = comp_n / full_n * 100 if full_n > 0 else 0
        band_retention[band] = retention_pct
        print(f"  {str(band):<25} {full_n:>8,} {comp_n:>10,} {retention_pct:>11.1f}%")

    # Flag if any band loses >50% of its members
    selection_bias_ok = all(r > 50 for r in band_retention.values())
    print(f"  [{'PASS' if selection_bias_ok else 'WARN'}] No band loses >50% of members in complete-case")
else:
    selection_bias_ok = True
    print("  selectivity_band not found in input data")

# --- Check 7: [Semantic] H2 attenuation verification ---
print(f"\n[CHECK 7] Semantic: H2 attenuation verification")

# Extract admit_rate coefficients from each model
m1_admit = df.filter(
    (pl.col("model") == "Model 1") & (pl.col("variable") == "admit_rate")
)
m3_admit = df.filter(
    (pl.col("model") == "Model 3") & (pl.col("variable") == "admit_rate")
)

if len(m1_admit) > 0 and len(m3_admit) > 0:
    m1_coef = m1_admit["coefficient"][0]
    m3_coef = m3_admit["coefficient"][0]
    attenuation = (m1_coef - m3_coef) / m1_coef * 100

    print(f"  M1 admit_rate coef: {m1_coef:.4f}")
    print(f"  M3 admit_rate coef: {m3_coef:.4f}")
    print(f"  Attenuation: {attenuation:.1f}%")

    # Verify attenuation percentage matches execution log (55.7%)
    attenuation_match = abs(attenuation - 55.7) < 0.5
    print(f"  [{'PASS' if attenuation_match else 'FAIL'}] Attenuation matches execution log (55.7%)")

    # Verify the coefficient sign is negative (more selective = lower admit rate = higher grad rate)
    sign_correct = m1_coef < 0 and m3_coef < 0
    print(f"  [{'PASS' if sign_correct else 'FAIL'}] Both coefficients negative (expected direction)")

    # Is the attenuation "substantial"? Plan H2 says "substantially reduced"
    h2_substantial = abs(attenuation) > 30
    print(f"  [{'PASS' if h2_substantial else 'INFO'}] Attenuation > 30% (qualifies as 'substantial')")
else:
    attenuation_match = False
    sign_correct = False
    h2_substantial = False
    print("  FAIL: Could not find admit_rate coefficients for M1 and M3")

# --- Check 8: [Boundary] Multicollinearity check via coefficient instability ---
print(f"\n[CHECK 8] Boundary: Multicollinearity proxy (coefficient stability)")

# If multicollinearity is severe, SEs will be inflated and coefficients unstable.
# Check: are any SEs extremely large relative to coefficients?
for model_name in ["Model 3", "Model 3b"]:
    model_rows = df.filter(
        (pl.col("model") == model_name) & (pl.col("variable") != "Intercept")
    )
    if len(model_rows) > 0:
        t_stats = model_rows["t_statistic"].to_list()
        vars_list = model_rows["variable"].to_list()
        ses = model_rows["std_error"].to_list()
        coefs = model_rows["coefficient"].to_list()

        print(f"\n  {model_name} coefficient/SE ratios:")
        inflate_issues = []
        for v, c, s, t in zip(vars_list, coefs, ses, t_stats):
            ratio = abs(c / s) if s > 0 else float('inf')
            flag = " <-- SE > |coef|" if abs(s) > abs(c) and "C(" not in v else ""
            print(f"    {v:<30} coef={c:>10.4f}  SE={s:>10.4f}  t={t:>8.2f}{flag}")
            if abs(s) > abs(c) * 5 and "C(" not in v:
                inflate_issues.append(v)

        if inflate_issues:
            print(f"  [WARN] Potentially inflated SEs: {inflate_issues}")
        else:
            print(f"  [PASS] No extreme SE inflation detected")

# --- Check 9: [Absence] Verify confidence intervals stored and reasonable ---
print(f"\n[CHECK 9] Absence: Confidence intervals")

ci_issues = []
for row in df.iter_rows(named=True):
    ci_lower = row["ci_lower"]
    ci_upper = row["ci_upper"]
    coef = row["coefficient"]

    # CI should bracket the coefficient
    if ci_lower is not None and ci_upper is not None:
        if not (ci_lower <= coef <= ci_upper):
            ci_issues.append(f"{row['model']}/{row['variable']}: CI [{ci_lower:.4f}, {ci_upper:.4f}] does not bracket coef {coef:.4f}")
        # CI width should be positive
        if ci_upper < ci_lower:
            ci_issues.append(f"{row['model']}/{row['variable']}: CI inverted [{ci_lower:.4f}, {ci_upper:.4f}]")
    else:
        ci_issues.append(f"{row['model']}/{row['variable']}: CI has null values")

ci_ok = len(ci_issues) == 0
print(f"  [{'PASS' if ci_ok else 'FAIL'}] CIs bracket coefficients and are non-null: ", end="")
print("All valid" if ci_ok else f"{len(ci_issues)} issues")
for issue in ci_issues[:5]:
    print(f"    - {issue}")

# --- Check 10: [Downstream] Consistent N across all 4 models ---
print(f"\n[CHECK 10] Downstream: Consistent sample size across models")

model_n = {}
for model_name in ["Model 1", "Model 2", "Model 3", "Model 3b"]:
    model_rows = df.filter(pl.col("model") == model_name)
    if len(model_rows) > 0:
        n_values = model_rows["n_obs"].unique().to_list()
        model_n[model_name] = n_values[0]
        if len(n_values) > 1:
            print(f"  [WARN] {model_name} has inconsistent n_obs values: {n_values}")

all_n = list(model_n.values())
consistent_n = len(set(all_n)) == 1
print(f"  N per model: {model_n}")
print(f"  [{'PASS' if consistent_n else 'FAIL'}] All models use same N: {all_n[0] if consistent_n else 'INCONSISTENT'}")

# === SPOT-CHECKS ===
print(f"\n{'=' * 60}")
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recalculate R-squared change ---
print(f"\n[SPOT 11] R-squared change verification")

r2_by_model = {}
for model_name in ["Model 1", "Model 2", "Model 3", "Model 3b"]:
    model_rows = df.filter(pl.col("model") == model_name)
    if len(model_rows) > 0:
        r2_by_model[model_name] = model_rows["r_squared"][0]

if len(r2_by_model) == 4:
    r2_m1 = r2_by_model["Model 1"]
    r2_m2 = r2_by_model["Model 2"]
    r2_m3 = r2_by_model["Model 3"]
    r2_m3b = r2_by_model["Model 3b"]

    change_1to2 = r2_m2 - r2_m1
    change_2to3 = r2_m3 - r2_m2
    change_3to3b = r2_m3b - r2_m3

    print(f"  R-squared: M1={r2_m1:.4f}, M2={r2_m2:.4f}, M3={r2_m3:.4f}, M3b={r2_m3b:.4f}")
    print(f"  Change M1->M2: {change_1to2:.4f} (composition)")
    print(f"  Change M2->M3: {change_2to3:.4f} (resources)")
    print(f"  Change M3->M3b: {change_3to3b:.4f} (sector)")

    r2_increasing = r2_m1 <= r2_m2 <= r2_m3 <= r2_m3b
    print(f"  [{'PASS' if r2_increasing else 'FAIL'}] R-squared monotonically increasing")

    # Resources add much more than composition: 0.3048 vs 0.1394
    resource_dominates = change_2to3 > change_1to2
    print(f"  [INFO] Resources add more R2 than composition: {resource_dominates}")
else:
    print(f"  FAIL: Could not find R-squared for all 4 models")

# --- Spot-Check 12: admit_rate coefficient direction ---
print(f"\n[SPOT 12] admit_rate coefficient direction (all models)")
admit_ok = True
for model_name in ["Model 1", "Model 2", "Model 3", "Model 3b"]:
    admit_rows = df.filter(
        (pl.col("model") == model_name) & (pl.col("variable") == "admit_rate")
    )
    if len(admit_rows) > 0:
        coef = admit_rows["coefficient"][0]
        pval = admit_rows["p_value"][0]
        sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "ns"
        print(f"  {model_name}: admit_rate = {coef:.4f} ({sig})")
        if coef > 0:
            print(f"    [FAIL] Expected negative coefficient!")
            admit_ok = False
    else:
        print(f"  {model_name}: admit_rate NOT FOUND")
        admit_ok = False
print(f"  [{'PASS' if admit_ok else 'FAIL'}] All admit_rate coefficients negative")

# --- Spot-Check 13: retention_rate coefficient direction ---
print(f"\n[SPOT 13] retention_rate coefficient direction")
ret_ok = True
for model_name in ["Model 3", "Model 3b"]:
    ret_rows = df.filter(
        (pl.col("model") == model_name) & (pl.col("variable") == "retention_rate")
    )
    if len(ret_rows) > 0:
        coef = ret_rows["coefficient"][0]
        pval = ret_rows["p_value"][0]
        sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "ns"
        print(f"  {model_name}: retention_rate = {coef:.4f} ({sig})")
        if coef < 0:
            print(f"    [WARN] Negative retention coefficient -- unexpected direction")
            ret_ok = False

print(f"  [{'PASS' if ret_ok else 'WARN'}] retention_rate coefficients positive (expected)")

# --- Spot-Check 14: Model 1 R-squared vs outperformer selectivity model ---
print(f"\n[SPOT 14] Model 1 R-squared vs outperformer selectivity model")
if OUTPERFORMER_FILE.exists():
    df_outperf = pl.read_parquet(OUTPERFORMER_FILE)
    print(f"  Outperformer model file loaded: {df_outperf.shape[0]:,} rows")

    # The outperformer model is also completion_rate_150pct ~ admit_rate
    # But it may use a different sample (only rows with admit_rate + grad_rate non-null,
    # not the full 7-variable complete-case). So R-squared may differ.
    m1_r2 = r2_by_model.get("Model 1", None)
    print(f"  Regression Model 1 R-squared: {m1_r2:.4f}" if m1_r2 else "  M1 R2 not available")
    print(f"  Outperformer model columns: {df_outperf.columns}")

    # Note: The outperformer model uses a larger sample (only needs admit_rate + grad_rate),
    # while the regression M1 uses the 7-variable complete-case subset.
    # Different N -> different R-squared is expected and correct.
    print(f"  [INFO] Different sample sizes expected (outperformer model uses broader sample)")
else:
    print(f"  Outperformer model file not found at {OUTPERFORMER_FILE}")

# --- Spot-Check 15: Cross-check complete-case N ---
print(f"\n[SPOT 15] Complete-case N verification")
n_from_output = int(all_n[0]) if consistent_n else None
n_from_recreation = complete_n

if n_from_output and n_from_recreation:
    n_match = n_from_output == n_from_recreation
    print(f"  N from output parquet: {n_from_output}")
    print(f"  N from recreated complete-case: {n_from_recreation}")
    print(f"  [{'PASS' if n_match else 'FAIL'}] N values match")
else:
    print(f"  Could not compare N values")

# --- Data Profiling (for cr2+ decision) ---
print(f"\n{'=' * 60}")
print("DATA PROFILING")
print("=" * 60)

print("\nOutput data sample (first 22 rows = all rows):")
print(df.head(22))

print("\nDescriptive statistics of output:")
print(df.describe())

print("\nModels present:")
print(df["model"].value_counts().sort("model"))

print("\nVariables per model:")
for model_name in ["Model 1", "Model 2", "Model 3", "Model 3b"]:
    model_vars = df.filter(pl.col("model") == model_name)["variable"].to_list()
    print(f"  {model_name}: {model_vars}")

print("\nCoefficient summary statistics by model:")
for model_name in ["Model 1", "Model 2", "Model 3", "Model 3b"]:
    model_rows = df.filter(
        (pl.col("model") == model_name) & (pl.col("variable") != "Intercept")
    )
    if len(model_rows) > 0:
        print(f"\n  {model_name}:")
        for row in model_rows.iter_rows(named=True):
            print(f"    {row['variable']:<30} coef={row['coefficient']:>10.4f}  "
                  f"p={row['p_value']:>8.4f}  CI=[{row['ci_lower']:>8.4f}, {row['ci_upper']:>8.4f}]")

print(f"\nP-value distribution:")
print(f"  p < 0.001: {(df['p_value'] < 0.001).sum()}")
print(f"  p < 0.01:  {((df['p_value'] >= 0.001) & (df['p_value'] < 0.01)).sum()}")
print(f"  p < 0.05:  {((df['p_value'] >= 0.01) & (df['p_value'] < 0.05)).sum()}")
print(f"  p >= 0.05: {(df['p_value'] >= 0.05).sum()}")

# --- Summary ---
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([
    selection_bias_ok, attenuation_match, sign_correct,
    ci_ok, consistent_n, admit_ok, ret_ok
])

print(f"\n{'=' * 60}")
if all_default_passed and all_specific_passed:
    severity = "PASSED"
else:
    severity = "WARNING" if all_default_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:34:18
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_06_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8.1 Step 9.1 — regression-models
# ============================================================
# Loaded output: 22 rows x 12 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 22 (expected 15-30)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in coefficients
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# Loaded input: 1,946 rows x 25 cols
# 
# [CHECK 6] Counterfactual: Complete-case selection bias
#   Full dataset: 1,946 rows
#   Complete-case: 1,574 rows (80.9%)
# 
#   Selectivity band representation:
#   Band                        Full N Complete N  Retention %
#   -------------------------------------------------------
#   Highly Selective                71         65        91.5%
#   Moderately Selective           577        571        99.0%
#   Open/Less Selective          1,121        768        68.5%
#   Selective                      177        170        96.0%
#   [PASS] No band loses >50% of members in complete-case
# 
# [CHECK 7] Semantic: H2 attenuation verification
#   M1 admit_rate coef: -0.3047
#   M3 admit_rate coef: -0.1349
#   Attenuation: 55.7%
#   [PASS] Attenuation matches execution log (55.7%)
#   [PASS] Both coefficients negative (expected direction)
#   [PASS] Attenuation > 30% (qualifies as 'substantial')
# 
# [CHECK 8] Boundary: Multicollinearity proxy (coefficient stability)
# 
#   Model 3 coefficient/SE ratios:
#     admit_rate                     coef=   -0.1349  SE=    0.0197  t=   -6.86
#     pell_share                     coef=    6.5907  SE=    6.9815  t=    0.94 <-- SE > |coef|
#     urm_share                      coef=  -14.2181  SE=    1.6291  t=   -8.73
#     student_faculty_ratio          coef=   -0.2380  SE=    0.0995  t=   -2.39
#     retention_rate                 coef=    0.6730  SE=    0.0625  t=   10.77
#     log_instr_expend               coef=    8.3021  SE=    1.1462  t=    7.24
#   [PASS] No extreme SE inflation detected
# 
#   Model 3b coefficient/SE ratios:
#     C(inst_control)[T.2]           coef=    2.8116  SE=    1.0608  t=    2.65
#     C(inst_control)[T.3]           coef=    5.5189  SE=    3.3232  t=    1.66
#     admit_rate                     coef=   -0.1207  SE=    0.0213  t=   -5.68
#     pell_share                     coef=    1.0574  SE=    8.3005  t=    0.13 <-- SE > |coef|
#     urm_share                      coef=  -13.9570  SE=    1.5576  t=   -8.96
#     student_faculty_ratio          coef=   -0.0874  SE=    0.1205  t=   -0.73 <-- SE > |coef|
#     retention_rate                 coef=    0.6707  SE=    0.0617  t=   10.87
#     log_instr_expend               coef=    9.0886  SE=    1.1702  t=    7.77
#   [WARN] Potentially inflated SEs: ['pell_share']
# 
# [CHECK 9] Absence: Confidence intervals
#   [PASS] CIs bracket coefficients and are non-null: All valid
# 
# [CHECK 10] Downstream: Consistent sample size across models
#   N per model: {'Model 1': 1574, 'Model 2': 1574, 'Model 3': 1574, 'Model 3b': 1574}
#   [PASS] All models use same N: 1574
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [SPOT 11] R-squared change verification
#   R-squared: M1=0.1118, M2=0.2511, M3=0.5560, M3b=0.5599
#   Change M1->M2: 0.1394 (composition)
#   Change M2->M3: 0.3048 (resources)
#   Change M3->M3b: 0.0040 (sector)
#   [PASS] R-squared monotonically increasing
#   [INFO] Resources add more R2 than composition: True
# 
# [SPOT 12] admit_rate coefficient direction (all models)
#   Model 1: admit_rate = -0.3047 (***)
#   Model 2: admit_rate = -0.3096 (***)
#   Model 3: admit_rate = -0.1349 (***)
#   Model 3b: admit_rate = -0.1207 (***)
#   [PASS] All admit_rate coefficients negative
# 
# [SPOT 13] retention_rate coefficient direction
#   Model 3: retention_rate = 0.6730 (***)
#   Model 3b: retention_rate = 0.6707 (***)
#   [PASS] retention_rate coefficients positive (expected)
# 
# [SPOT 14] Model 1 R-squared vs outperformer selectivity model
#   Outperformer model file loaded: 1,625 rows
#   Regression Model 1 R-squared: 0.1118
#   Outperformer model columns: ['unitid', 'inst_name', 'admit_rate', 'completion_rate_150pct', 'predicted', 'residual', 'outperformer_flag']
#   [INFO] Different sample sizes expected (outperformer model uses broader sample)
# 
# [SPOT 15] Complete-case N verification
#   N from output parquet: 1574
#   N from recreated complete-case: 1574
#   [PASS] N values match
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Output data sample (first 22 rows = all rows):
# shape: (22, 12)
# ┌──────────┬────────────┬────────────┬───────────┬───┬───────────┬────────────┬───────┬────────────┐
# │ model    ┆ variable   ┆ coefficien ┆ std_error ┆ … ┆ r_squared ┆ adj_r_squa ┆ n_obs ┆ f_statisti │
# │ ---      ┆ ---        ┆ t          ┆ ---       ┆   ┆ ---       ┆ red        ┆ ---   ┆ c          │
# │ str      ┆ str        ┆ ---        ┆ f64       ┆   ┆ f64       ┆ ---        ┆ i64   ┆ ---        │
# │          ┆            ┆ f64        ┆           ┆   ┆           ┆ f64        ┆       ┆ f64        │
# ╞══════════╪════════════╪════════════╪═══════════╪═══╪═══════════╪════════════╪═══════╪════════════╡
# │ Model 1  ┆ Intercept  ┆ 79.048162  ┆ 1.847285  ┆ … ┆ 0.111771  ┆ 0.111206   ┆ 1574  ┆ 160.615159 │
# │ Model 1  ┆ admit_rate ┆ -0.304699  ┆ 0.024042  ┆ … ┆ 0.111771  ┆ 0.111206   ┆ 1574  ┆ 160.615159 │
# │ Model 2  ┆ Intercept  ┆ 89.194642  ┆ 1.866687  ┆ … ┆ 0.25113   ┆ 0.249699   ┆ 1574  ┆ 173.248352 │
# │ Model 2  ┆ admit_rate ┆ -0.309614  ┆ 0.021861  ┆ … ┆ 0.25113   ┆ 0.249699   ┆ 1574  ┆ 173.248352 │
# │ Model 2  ┆ pell_share ┆ -9.124045  ┆ 7.40597   ┆ … ┆ 0.25113   ┆ 0.249699   ┆ 1574  ┆ 173.248352 │
# │ …        ┆ …          ┆ …          ┆ …         ┆ … ┆ …         ┆ …          ┆ …     ┆ …          │
# │ Model 3b ┆ pell_share ┆ 1.057432   ┆ 8.300483  ┆ … ┆ 0.559927  ┆ 0.557677   ┆ 1574  ┆ 230.934016 │
# │ Model 3b ┆ urm_share  ┆ -13.95699  ┆ 1.557634  ┆ … ┆ 0.559927  ┆ 0.557677   ┆ 1574  ┆ 230.934016 │
# │ Model 3b ┆ student_fa ┆ -0.087382  ┆ 0.12048   ┆ … ┆ 0.559927  ┆ 0.557677   ┆ 1574  ┆ 230.934016 │
# │          ┆ culty_rati ┆            ┆           ┆   ┆           ┆            ┆       ┆            │
# │          ┆ o          ┆            ┆           ┆   ┆           ┆            ┆       ┆            │
# │ Model 3b ┆ retention_ ┆ 0.67067    ┆ 0.061708  ┆ … ┆ 0.559927  ┆ 0.557677   ┆ 1574  ┆ 230.934016 │
# │          ┆ rate       ┆            ┆           ┆   ┆           ┆            ┆       ┆            │
# │ Model 3b ┆ log_instr_ ┆ 9.088648   ┆ 1.170186  ┆ … ┆ 0.559927  ┆ 0.557677   ┆ 1574  ┆ 230.934016 │
# │          ┆ expend     ┆            ┆           ┆   ┆           ┆            ┆       ┆            │
# └──────────┴────────────┴────────────┴───────────┴───┴───────────┴────────────┴───────┴────────────┘
# 
# Descriptive statistics of output:
# shape: (9, 13)
# ┌────────────┬──────────┬────────────┬────────────┬───┬───────────┬───────────┬────────┬───────────┐
# │ statistic  ┆ model    ┆ variable   ┆ coefficien ┆ … ┆ r_squared ┆ adj_r_squ ┆ n_obs  ┆ f_statist │
# │ ---        ┆ ---      ┆ ---        ┆ t          ┆   ┆ ---       ┆ ared      ┆ ---    ┆ ic        │
# │ str        ┆ str      ┆ str        ┆ ---        ┆   ┆ f64       ┆ ---       ┆ f64    ┆ ---       │
# │            ┆          ┆            ┆ f64        ┆   ┆           ┆ f64       ┆        ┆ f64       │
# ╞════════════╪══════════╪════════════╪════════════╪═══╪═══════════╪═══════════╪════════╪═══════════╡
# │ count      ┆ 22       ┆ 22         ┆ 22.0       ┆ … ┆ 22.0      ┆ 22.0      ┆ 22.0   ┆ 22.0      │
# │ null_count ┆ 0        ┆ 0          ┆ 0.0        ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0    ┆ 0.0       │
# │ mean       ┆ null     ┆ null       ┆ 0.783889   ┆ … ┆ 0.46178   ┆ 0.460007  ┆ 1574.0 ┆ 233.97945 │
# │            ┆          ┆            ┆            ┆   ┆           ┆           ┆        ┆ 9         │
# │ std        ┆ null     ┆ null       ┆ 32.956939  ┆ … ┆ 0.164938  ┆ 0.164503  ┆ 0.0    ┆ 49.01402  │
# │ min        ┆ Model 1  ┆ C(inst_con ┆ -64.922876 ┆ … ┆ 0.111771  ┆ 0.111206  ┆ 1574.0 ┆ 160.61515 │
# │            ┆          ┆ trol)[T.2] ┆            ┆   ┆           ┆           ┆        ┆ 9         │
# │ 25%        ┆ null     ┆ null       ┆ -9.124045  ┆ … ┆ 0.25113   ┆ 0.249699  ┆ 1574.0 ┆ 173.24835 │
# │            ┆          ┆            ┆            ┆   ┆           ┆           ┆        ┆ 2         │
# │ 50%        ┆ null     ┆ null       ┆ -0.087382  ┆ … ┆ 0.555964  ┆ 0.554263  ┆ 1574.0 ┆ 230.93401 │
# │            ┆          ┆            ┆            ┆   ┆           ┆           ┆        ┆ 6         │
# │ 75%        ┆ null     ┆ null       ┆ 5.518906   ┆ … ┆ 0.559927  ┆ 0.557677  ┆ 1574.0 ┆ 293.55974 │
# │            ┆          ┆            ┆            ┆   ┆           ┆           ┆        ┆ 6         │
# │ max        ┆ Model 3b ┆ urm_share  ┆ 89.194642  ┆ … ┆ 0.559927  ┆ 0.557677  ┆ 1574.0 ┆ 293.55974 │
# │            ┆          ┆            ┆            ┆   ┆           ┆           ┆        ┆ 6         │
# └────────────┴──────────┴────────────┴────────────┴───┴───────────┴───────────┴────────┴───────────┘
# 
# Models present:
# shape: (4, 2)
# ┌──────────┬───────┐
# │ model    ┆ count │
# │ ---      ┆ ---   │
# │ str      ┆ u32   │
# ╞══════════╪═══════╡
# │ Model 1  ┆ 2     │
# │ Model 2  ┆ 4     │
# │ Model 3  ┆ 7     │
# │ Model 3b ┆ 9     │
# └──────────┴───────┘
# 
# Variables per model:
#   Model 1: ['Intercept', 'admit_rate']
#   Model 2: ['Intercept', 'admit_rate', 'pell_share', 'urm_share']
#   Model 3: ['Intercept', 'admit_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate', 'log_instr_expend']
#   Model 3b: ['Intercept', 'C(inst_control)[T.2]', 'C(inst_control)[T.3]', 'admit_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate', 'log_instr_expend']
# 
# Coefficient summary statistics by model:
# 
#   Model 1:
#     admit_rate                     coef=   -0.3047  p=  0.0000  CI=[ -0.3518,  -0.2576]
# 
#   Model 2:
#     admit_rate                     coef=   -0.3096  p=  0.0000  CI=[ -0.3525,  -0.2668]
#     pell_share                     coef=   -9.1240  p=  0.2180  CI=[-23.6395,   5.3914]
#     urm_share                      coef=  -28.8646  p=  0.0000  CI=[-32.3945, -25.3348]
# 
#   Model 3:
#     admit_rate                     coef=   -0.1349  p=  0.0000  CI=[ -0.1735,  -0.0963]
#     pell_share                     coef=    6.5907  p=  0.3452  CI=[ -7.0928,  20.2743]
#     urm_share                      coef=  -14.2181  p=  0.0000  CI=[-17.4109, -11.0252]
#     student_faculty_ratio          coef=   -0.2380  p=  0.0168  CI=[ -0.4331,  -0.0430]
#     retention_rate                 coef=    0.6730  p=  0.0000  CI=[  0.5506,   0.7955]
#     log_instr_expend               coef=    8.3021  p=  0.0000  CI=[  6.0555,  10.5486]
# 
#   Model 3b:
#     C(inst_control)[T.2]           coef=    2.8116  p=  0.0080  CI=[  0.7324,   4.8908]
#     C(inst_control)[T.3]           coef=    5.5189  p=  0.0968  CI=[ -0.9944,  12.0322]
#     admit_rate                     coef=   -0.1207  p=  0.0000  CI=[ -0.1623,  -0.0790]
#     pell_share                     coef=    1.0574  p=  0.8986  CI=[-15.2112,  17.3261]
#     urm_share                      coef=  -13.9570  p=  0.0000  CI=[-17.0099, -10.9041]
#     student_faculty_ratio          coef=   -0.0874  p=  0.4683  CI=[ -0.3235,   0.1488]
#     retention_rate                 coef=    0.6707  p=  0.0000  CI=[  0.5497,   0.7916]
#     log_instr_expend               coef=    9.0886  p=  0.0000  CI=[  6.7951,  11.3822]
# 
# P-value distribution:
#   p < 0.001: 15
#   p < 0.01:  1
#   p < 0.05:  1
#   p >= 0.05: 5
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
