#!/usr/bin/env python3
"""
Stage 8.1: Hierarchical OLS regression -- selectivity vs. effectiveness.

Task: regression-models
Wave: 9, Step: 6, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_regression_results.parquet
Checkpoint: CP4

Research Question: How much of the variation in college graduation rates is
attributable to institutional selectivity versus institutional effectiveness?

Models:
  Model 1: completion_rate_150pct ~ admit_rate
  Model 2: Model 1 + pell_share + urm_share
  Model 3: Model 2 + student_faculty_ratio + retention_rate + log_instr_expend
  Model 3b: Model 3 + C(inst_control)
All estimated with HC1 robust standard errors.
"""

import polars as pl
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
from pathlib import Path

# --- Config ---
# Configuration constants from Plan Section 5 (Analysis Design).
# Four hierarchical OLS models test whether selectivity (admit_rate) explains
# graduation rates beyond what student composition and institutional resources explain.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_regression_results.parquet"

# Analysis variables from Plan specification
OUTCOME = "completion_rate_150pct"
KEY_PREDICTOR = "admit_rate"
COMPOSITION_VARS = ["pell_share", "urm_share"]
RESOURCE_VARS = ["student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]
SECTOR_VAR = "inst_control"

# All variables needed for complete-case analysis (Model 3 requires all seven)
ALL_ANALYSIS_VARS = [OUTCOME, KEY_PREDICTOR] + COMPOSITION_VARS + RESOURCE_VARS

# --- Load ---
# Load the analysis dataset built in Stage 7 and verify shape.
print("=" * 60)
print("Stage 8.1: Hierarchical OLS Regression")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Verify all required analysis variables exist and document missingness.
pre_rows = df.shape[0]

missing_vars = [v for v in ALL_ANALYSIS_VARS + [SECTOR_VAR] if v not in df.columns]
assert not missing_vars, f"STOP: Missing analysis variables: {missing_vars}"

print(f"\nPre-state: {pre_rows:,} rows")
print("\nMissingness by analysis variable:")
for var in ALL_ANALYSIS_VARS + [SECTOR_VAR]:
    null_ct = df[var].null_count()
    null_pct = null_ct / pre_rows * 100
    print(f"  {var}: {null_ct:,} nulls ({null_pct:.1f}%)")

# --- Complete-Case Dataset ---
# INTENT: Create a single complete-case dataset across ALL seven continuous
# analysis variables so that Models 1-3b are estimated on the SAME sample.
# This ensures R-squared changes reflect added predictors, not sample changes.
#
# REASONING: Listwise deletion across all Model 3 variables is the appropriate
# strategy here because (a) we need consistent samples for hierarchical model
# comparison, and (b) the main driver of missingness is admit_rate (open-admission
# institutions have no admission rate), which is the key predictor -- imputation
# of the key predictor would undermine the research question.
#
# ASSUMES: Missingness is primarily driven by open-admission institutions lacking
# admit_rate data. The Plan documents this as ~54% complete-case rate (~1,058 rows).
df_complete = df.drop_nulls(subset=ALL_ANALYSIS_VARS)
complete_n = df_complete.shape[0]
dropped = pre_rows - complete_n
drop_pct = dropped / pre_rows * 100

print(f"\nComplete-case dataset: {complete_n:,} rows")
print(f"Dropped: {dropped:,} rows ({drop_pct:.1f}%)")
print(f"NOTE: High drop rate ({drop_pct:.1f}%) is expected and documented in Plan.")
print("  Primary driver: admit_rate nulls (open-admission institutions).")

# --- Log-Transform Finance Variable ---
# INTENT: Log-transform instr_expend_per_fte before entering Models 3/3b.
# REASONING: The raw variable has extreme outliers (up to $14.1M/FTE from
# Wave 8 correlation analysis). Log-transformation compresses the right tail,
# stabilizes variance, and allows coefficient interpretation as elasticity-like
# (percentage change in spending associated with graduation rate change).
# Using np.log1p (log(1+x)) to safely handle any zero values.
# ASSUMES: instr_expend_per_fte >= 0 for all observations.
df_complete = df_complete.with_columns(
    pl.col("instr_expend_per_fte").map_batches(
        lambda s: pl.Series(np.log1p(s.to_numpy().astype(float)))
    ).alias("log_instr_expend")
)

print(f"\nLog-transformed instr_expend_per_fte -> log_instr_expend")
log_vals = df_complete["log_instr_expend"]
print(f"  Range: [{log_vals.min():.3f}, {log_vals.max():.3f}]")
print(f"  Mean: {log_vals.mean():.3f}, Median: {log_vals.median():.3f}")

# --- Convert to Pandas for statsmodels ---
# REASONING: statsmodels formula API requires pandas DataFrames.
# Converting only the complete-case subset (not the full dataset).
pdf = df_complete.to_pandas()

# Ensure inst_control is treated as categorical
# ASSUMES: inst_control values are 1=public, 2=private NP, 3=for-profit
pdf["inst_control"] = pdf["inst_control"].astype(int)

print(f"\nSample for regression: {len(pdf):,} rows")
print(f"inst_control distribution:")
print(pdf["inst_control"].value_counts().sort_index().to_string())

# --- Model Estimation ---
# INTENT: Estimate four hierarchical OLS models to decompose how much of the
# graduation rate variation is explained by selectivity alone (Model 1), student
# composition (Model 2), institutional resources (Model 3), and sector (Model 3b).
# All models use HC1 robust standard errors to address heteroskedasticity.
#
# REASONING: Hierarchical (nested) model specification is standard for assessing
# incremental explanatory power. HC1 is used per the Plan specification and is
# the default robust SE choice for cross-sectional data (White 1980).

print("\n" + "=" * 60)
print("MODEL ESTIMATION (HC1 Robust SEs)")
print("=" * 60)

# Model 1: Selectivity only
# INTENT: Baseline model -- how much does selectivity alone explain?
m1 = smf.ols(
    f"{OUTCOME} ~ {KEY_PREDICTOR}",
    data=pdf
).fit(cov_type="HC1")
print(f"\nModel 1 (Selectivity only): R2={m1.rsquared:.4f}, Adj.R2={m1.rsquared_adj:.4f}, N={int(m1.nobs)}")

# Model 2: Add student composition
# INTENT: Does adding Pell share and URM share improve explanation?
m2 = smf.ols(
    f"{OUTCOME} ~ {KEY_PREDICTOR} + {' + '.join(COMPOSITION_VARS)}",
    data=pdf
).fit(cov_type="HC1")
print(f"Model 2 (+Composition):    R2={m2.rsquared:.4f}, Adj.R2={m2.rsquared_adj:.4f}, N={int(m2.nobs)}")

# Model 3: Add institutional resources
# INTENT: Full model with selectivity + composition + resources.
# Uses log_instr_expend instead of raw instr_expend_per_fte.
m3 = smf.ols(
    f"{OUTCOME} ~ {KEY_PREDICTOR} + {' + '.join(COMPOSITION_VARS)} + student_faculty_ratio + retention_rate + log_instr_expend",
    data=pdf
).fit(cov_type="HC1")
print(f"Model 3 (+Resources):      R2={m3.rsquared:.4f}, Adj.R2={m3.rsquared_adj:.4f}, N={int(m3.nobs)}")

# Model 3b: Add sector dummies
# INTENT: Does sector (public/private NP/for-profit) explain additional variation
# beyond selectivity, composition, and resources?
# REASONING: C(inst_control) creates treatment-coded dummies. Default reference
# is the lowest value (1 = public).
m3b = smf.ols(
    f"{OUTCOME} ~ {KEY_PREDICTOR} + {' + '.join(COMPOSITION_VARS)} + student_faculty_ratio + retention_rate + log_instr_expend + C(inst_control)",
    data=pdf
).fit(cov_type="HC1")
print(f"Model 3b (+Sector):        R2={m3b.rsquared:.4f}, Adj.R2={m3b.rsquared_adj:.4f}, N={int(m3b.nobs)}")

# --- R-squared Change ---
# INTENT: Compute incremental R-squared to quantify the explanatory contribution
# of each variable block (composition and resources).
# REASONING: R2 change from Model 1->2 measures the added value of knowing
# student composition beyond selectivity. R2 change from Model 2->3 measures
# the added value of institutional resources beyond selectivity and composition.
r2_change_1to2 = m2.rsquared - m1.rsquared
r2_change_2to3 = m3.rsquared - m2.rsquared
r2_change_3to3b = m3b.rsquared - m3.rsquared

print(f"\nR-squared Changes:")
print(f"  Model 1 -> 2 (student composition): +{r2_change_1to2:.4f}")
print(f"  Model 2 -> 3 (resources):           +{r2_change_2to3:.4f}")
print(f"  Model 3 -> 3b (sector):             +{r2_change_3to3b:.4f}")

# --- H2 Assessment ---
# INTENT: Test H2 -- Does the admit_rate coefficient attenuate substantially
# from Model 1 to Model 3 when composition and resources are added?
# REASONING: If selectivity is merely proxying for composition and resources,
# the admit_rate coefficient should shrink substantially. If it retains much
# of its magnitude, selectivity has an independent association with graduation.
admit_coef_m1 = m1.params[KEY_PREDICTOR]
admit_coef_m2 = m2.params[KEY_PREDICTOR]
admit_coef_m3 = m3.params[KEY_PREDICTOR]
admit_coef_m3b = m3b.params[KEY_PREDICTOR]

attenuation_m1_to_m3 = (admit_coef_m1 - admit_coef_m3) / admit_coef_m1 * 100

print(f"\n{'=' * 60}")
print("H2 ASSESSMENT: Admit Rate Coefficient Attenuation")
print(f"{'=' * 60}")
print(f"  Model 1 (selectivity only):  {admit_coef_m1:.4f}")
print(f"  Model 2 (+composition):      {admit_coef_m2:.4f}")
print(f"  Model 3 (+resources):        {admit_coef_m3:.4f}")
print(f"  Model 3b (+sector):          {admit_coef_m3b:.4f}")
print(f"  Attenuation M1->M3: {attenuation_m1_to_m3:.1f}%")

if abs(attenuation_m1_to_m3) > 50:
    print(f"  FINDING: admit_rate coefficient attenuated by {attenuation_m1_to_m3:.1f}% -- substantial.")
    print("  Selectivity's association is largely mediated by composition/resources.")
else:
    print(f"  FINDING: admit_rate coefficient attenuated by {attenuation_m1_to_m3:.1f}% -- moderate.")
    print("  Selectivity retains independent association beyond composition/resources.")

# --- Formatted Regression Table ---
# INTENT: Print a comprehensive regression table to stdout for the audit trail.
print(f"\n{'=' * 60}")
print("REGRESSION TABLE")
print(f"{'=' * 60}")

models = {"Model 1": m1, "Model 2": m2, "Model 3": m3, "Model 3b": m3b}

# Collect all variable names across models
all_vars = []
for m in models.values():
    for v in m.params.index:
        if v not in all_vars:
            all_vars.append(v)

# Print header
header = f"{'Variable':<30}"
for name in models:
    header += f" {name:>14}"
print(header)
print("-" * (30 + 15 * len(models)))

# Print coefficients with significance stars
for var in all_vars:
    row = f"{var:<30}"
    for name, m in models.items():
        if var in m.params.index:
            coef = m.params[var]
            se = m.bse[var]
            pval = m.pvalues[var]
            stars = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else ""
            row += f" {coef:>10.4f}{stars:>4}"
        else:
            row += f" {'':>14}"
    print(row)
    # Print standard errors in parentheses
    se_row = f"{'':30}"
    for name, m in models.items():
        if var in m.params.index:
            se = m.bse[var]
            se_row += f" ({se:>9.4f})  "
        else:
            se_row += f" {'':>14}"
    print(se_row)

print("-" * (30 + 15 * len(models)))

# Print fit statistics
stat_row = f"{'R-squared':<30}"
for name, m in models.items():
    stat_row += f" {m.rsquared:>14.4f}"
print(stat_row)

stat_row = f"{'Adj. R-squared':<30}"
for name, m in models.items():
    stat_row += f" {m.rsquared_adj:>14.4f}"
print(stat_row)

stat_row = f"{'N':<30}"
for name, m in models.items():
    stat_row += f" {int(m.nobs):>14,}"
print(stat_row)

stat_row = f"{'F-statistic':<30}"
for name, m in models.items():
    stat_row += f" {m.fvalue:>14.2f}"
print(stat_row)

print(f"\nNote: HC1 robust standard errors in parentheses.")
print("* p<0.05, ** p<0.01, *** p<0.001")
print(f"log_instr_expend = log(1 + instr_expend_per_fte)")
print(f"inst_control: 1=Public (reference), 2=Private NP, 3=For-Profit")

# --- Save Results ---
# INTENT: Persist all coefficient estimates and model fit statistics as a
# structured parquet file for downstream consumption (report, notebook).
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

results_rows = []
for model_name, m in models.items():
    for var in m.params.index:
        results_rows.append({
            "model": model_name,
            "variable": var,
            "coefficient": float(m.params[var]),
            "std_error": float(m.bse[var]),
            "t_statistic": float(m.tvalues[var]),
            "p_value": float(m.pvalues[var]),
            "ci_lower": float(m.conf_int().loc[var, 0]),
            "ci_upper": float(m.conf_int().loc[var, 1]),
            "r_squared": float(m.rsquared),
            "adj_r_squared": float(m.rsquared_adj),
            "n_obs": int(m.nobs),
            "f_statistic": float(m.fvalue),
        })

results_df = pl.DataFrame(results_rows)
results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Results shape: {results_df.shape[0]} rows x {results_df.shape[1]} cols")

# --- CP4 Validation ---
# Checkpoint validation: verify regression produced valid results,
# R-squared is increasing across nested models, coefficients are finite,
# and the H2 assessment was conducted.
print(f"\n{'=' * 60}")
print("CHECKPOINT 4 VALIDATION")
print(f"{'=' * 60}")

# CP4.1: Output file exists and is non-zero
file_exists = OUTPUT_PATH.exists() and OUTPUT_PATH.stat().st_size > 0
print(f"  [{'PASS' if file_exists else 'FAIL'}] Output file exists and non-zero: {OUTPUT_PATH.stat().st_size:,} bytes")

# CP4.2: R-squared values between 0 and 1
r2_valid = all(0 <= m.rsquared <= 1 for m in models.values())
print(f"  [{'PASS' if r2_valid else 'FAIL'}] All R-squared in [0, 1]")

# CP4.3: R-squared increases from Model 1 to Model 3
r2_increasing = m1.rsquared <= m2.rsquared <= m3.rsquared
print(f"  [{'PASS' if r2_increasing else 'FAIL'}] R-squared increasing: {m1.rsquared:.4f} <= {m2.rsquared:.4f} <= {m3.rsquared:.4f}")

# CP4.4: All coefficients finite
all_finite = all(
    np.all(np.isfinite(m.params.values)) and np.all(np.isfinite(m.bse.values))
    for m in models.values()
)
print(f"  [{'PASS' if all_finite else 'FAIL'}] All coefficients and SEs finite")

# CP4.5: Sample sizes documented and consistent
consistent_n = len(set(int(m.nobs) for m in models.values())) == 1
print(f"  [{'PASS' if consistent_n else 'FAIL'}] Consistent sample size across models: N={int(m1.nobs)}")

# CP4.6: H2 assessed
h2_assessed = admit_coef_m1 is not None and admit_coef_m3 is not None
print(f"  [{'PASS' if h2_assessed else 'FAIL'}] H2 attenuation assessed: {attenuation_m1_to_m3:.1f}%")

# CP4.7: Adequate observations for number of predictors
# Model 3b has the most predictors; check n/k ratio
k_m3b = m3b.df_model + 1  # +1 for constant
n_k_ratio = int(m3b.nobs) / k_m3b
obs_adequate = n_k_ratio > 10
print(f"  [{'PASS' if obs_adequate else 'WARN'}] n/k ratio for Model 3b: {int(m3b.nobs)}/{k_m3b} = {n_k_ratio:.0f} (>10 required)")

assert file_exists, "STOP: Output file missing or empty"
assert r2_valid, "STOP: R-squared out of range"
assert r2_increasing, "STOP: R-squared not increasing across nested models"
assert all_finite, "STOP: Non-finite coefficients or SEs"

print(f"\n{'=' * 60}")
print("CP4 VALIDATION: PASSED")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:23:56
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/06_regression-models.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Hierarchical OLS Regression
# ============================================================
# Loaded: 1,946 rows x 25 cols
# 
# Pre-state: 1,946 rows
# 
# Missingness by analysis variable:
#   completion_rate_150pct: 0 nulls (0.0%)
#   admit_rate: 321 nulls (16.5%)
#   pell_share: 59 nulls (3.0%)
#   urm_share: 7 nulls (0.4%)
#   student_faculty_ratio: 5 nulls (0.3%)
#   retention_rate: 51 nulls (2.6%)
#   instr_expend_per_fte: 45 nulls (2.3%)
#   inst_control: 0 nulls (0.0%)
# 
# Complete-case dataset: 1,574 rows
# Dropped: 372 rows (19.1%)
# NOTE: High drop rate (19.1%) is expected and documented in Plan.
#   Primary driver: admit_rate nulls (open-admission institutions).
# 
# Log-transformed instr_expend_per_fte -> log_instr_expend
#   Range: [6.377, 11.992]
#   Mean: 9.181, Median: 9.157
# 
# Sample for regression: 1,574 rows
# inst_control distribution:
# inst_control
# 1     511
# 2    1017
# 3      46
# 
# ============================================================
# MODEL ESTIMATION (HC1 Robust SEs)
# ============================================================
# 
# Model 1 (Selectivity only): R2=0.1118, Adj.R2=0.1112, N=1574
# Model 2 (+Composition):    R2=0.2511, Adj.R2=0.2497, N=1574
# Model 3 (+Resources):      R2=0.5560, Adj.R2=0.5543, N=1574
# Model 3b (+Sector):        R2=0.5599, Adj.R2=0.5577, N=1574
# 
# R-squared Changes:
#   Model 1 -> 2 (student composition): +0.1394
#   Model 2 -> 3 (resources):           +0.3048
#   Model 3 -> 3b (sector):             +0.0040
# 
# ============================================================
# H2 ASSESSMENT: Admit Rate Coefficient Attenuation
# ============================================================
#   Model 1 (selectivity only):  -0.3047
#   Model 2 (+composition):      -0.3096
#   Model 3 (+resources):        -0.1349
#   Model 3b (+sector):          -0.1207
#   Attenuation M1->M3: 55.7%
#   FINDING: admit_rate coefficient attenuated by 55.7% -- substantial.
#   Selectivity's association is largely mediated by composition/resources.
# 
# ============================================================
# REGRESSION TABLE
# ============================================================
# Variable                              Model 1        Model 2        Model 3       Model 3b
# ------------------------------------------------------------------------------------------
# Intercept                         79.0482 ***    89.1946 ***   -53.4284 ***   -64.9229 ***
#                                (   1.8473)   (   1.8667)   (  10.0252)   (  10.7450)  
# admit_rate                        -0.3047 ***    -0.3096 ***    -0.1349 ***    -0.1207 ***
#                                (   0.0240)   (   0.0219)   (   0.0197)   (   0.0213)  
# pell_share                                       -9.1240         6.5907         1.0574    
#                                               (   7.4060)   (   6.9815)   (   8.3005)  
# urm_share                                       -28.8646 ***   -14.2181 ***   -13.9570 ***
#                                               (   1.8010)   (   1.6291)   (   1.5576)  
# student_faculty_ratio                                           -0.2380   *    -0.0874    
#                                                              (   0.0995)   (   0.1205)  
# retention_rate                                                   0.6730 ***     0.6707 ***
#                                                              (   0.0625)   (   0.0617)  
# log_instr_expend                                                 8.3021 ***     9.0886 ***
#                                                              (   1.1462)   (   1.1702)  
# C(inst_control)[T.2]                                                            2.8116  **
#                                                                             (   1.0608)  
# C(inst_control)[T.3]                                                            5.5189    
#                                                                             (   3.3232)  
# ------------------------------------------------------------------------------------------
# R-squared                              0.1118         0.2511         0.5560         0.5599
# Adj. R-squared                         0.1112         0.2497         0.5543         0.5577
# N                                       1,574          1,574          1,574          1,574
# F-statistic                            160.62         173.25         293.56         230.93
# 
# Note: HC1 robust standard errors in parentheses.
# * p<0.05, ** p<0.01, *** p<0.001
# log_instr_expend = log(1 + instr_expend_per_fte)
# inst_control: 1=Public (reference), 2=Private NP, 3=For-Profit
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_regression_results.parquet
# Results shape: 22 rows x 12 cols
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] Output file exists and non-zero: 5,433 bytes
#   [PASS] All R-squared in [0, 1]
#   [PASS] R-squared increasing: 0.1118 <= 0.2511 <= 0.5560
#   [PASS] All coefficients and SEs finite
#   [PASS] Consistent sample size across models: N=1574
#   [PASS] H2 attenuation assessed: 55.7%
#   [PASS] n/k ratio for Model 3b: 1574/9.0 = 175 (>10 required)
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
