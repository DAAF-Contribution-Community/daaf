#!/usr/bin/env python3
"""
Stage 8.1: OLS Regression Models — Quantify how much student body composition
explains graduation rate variance beyond admissions selectivity alone.

Task: regression-models
Wave: 8, Step: 6, Stage: 8
Depends on: create-bands (Wave 7)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_regression_results.parquet
Checkpoint: CP4
"""

import numpy as np
from pathlib import Path

import polars as pl

# --- Config ---
# Configuration constants for regression analysis. Three nested OLS models
# progressively add student body composition and institutional characteristics
# to test whether selectivity alone explains graduation rate variation.
# This is SUPPLEMENTARY analysis — the narrative is driven by descriptive
# statistics and cross-tabulations from prior scripts.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_regression_results.parquet"

# Critical columns required for regression (all must be non-null for listwise deletion)
CRITICAL_COLS = [
    "grad_rate_150pct",
    "admission_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "inst_control",
]

# --- Load ---
# Load the analysis dataset produced by Stage 7. This contains 2,528 rows
# with institution-level data including graduation rates, admissions selectivity,
# and student body composition variables.
print("=" * 60)
print("Stage 8.1: OLS Regression Models")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture the full dataset state before applying listwise deletion.
# We track how many rows are dropped and their characteristics to understand
# potential selection bias from excluding institutions with missing data.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Report missingness in each critical column before filtering
print("\nMissingness in critical columns:")
for col in CRITICAL_COLS:
    null_ct = df[col].null_count()
    null_pct = null_ct / pre_rows * 100
    print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

# --- Prepare regression data ---
# INTENT: Apply listwise deletion — keep only rows where ALL critical regression
# variables are non-null. This ensures consistent sample size across all three
# models for valid R-squared comparison.
#
# REASONING: Listwise deletion (not pairwise or imputation) because:
#   - We need identical N across models to compare R-squared meaningfully
#   - Prior EDA found 14pp graduation rate gap between dropped/kept rows,
#     so results should be interpreted with this selection caveat
#   - Imputation would introduce additional assumptions for supplementary analysis
#
# ASSUMES:
#   - CRITICAL_COLS are all present in the dataframe (verified above)
#   - inst_control values include 1 (public) and 2 (private nonprofit)
#   - grad_rate_150pct is 0-100 scale (percentage)
#   - admission_rate is 0-1 scale (proportion)
#   - pell_share and urm_share are 0-1 scale (proportion)
print("\n" + "-" * 60)
print("Applying listwise deletion for regression sample")
print("-" * 60)

df_reg = df.drop_nulls(subset=CRITICAL_COLS)
n_complete = df_reg.shape[0]
n_dropped = pre_rows - n_complete
print(f"Complete cases: {n_complete:,} (dropped {n_dropped:,}, {n_dropped/pre_rows*100:.1f}%)")

# --- Create dummy variable ---
# INTENT: Create binary indicator for private nonprofit institutions.
# REASONING: inst_control is categorical (1=public, 2=private nonprofit).
# OLS requires numeric predictors. A single dummy (1=private, 0=public)
# captures the sector effect. This aligns with the Plan's specification.
# ASSUMES: inst_control has only values 1 and 2 in the regression sample.
inst_ctrl_values = df_reg["inst_control"].unique().sort().to_list()
print(f"\ninst_control values in regression sample: {inst_ctrl_values}")

df_reg = df_reg.with_columns(
    pl.when(pl.col("inst_control") == 2)
    .then(1)
    .otherwise(0)
    .cast(pl.Float64)
    .alias("sector_private")
)
print(f"sector_private created: mean = {df_reg['sector_private'].mean():.3f}")

# --- Extract numpy arrays ---
# INTENT: Convert Polars columns to numpy arrays for OLS computation.
# REASONING: Using numpy/scipy for OLS (not sklearn) per task specification
# to keep dependencies light. Manual OLS via normal equations is straightforward
# and transparent for audit purposes.
y = df_reg["grad_rate_150pct"].to_numpy().astype(np.float64)
x_admission = df_reg["admission_rate"].to_numpy().astype(np.float64)
x_pell = df_reg["pell_share"].to_numpy().astype(np.float64)
x_urm = df_reg["urm_share"].to_numpy().astype(np.float64)
x_sfr = df_reg["student_faculty_ratio"].to_numpy().astype(np.float64)
x_private = df_reg["sector_private"].to_numpy().astype(np.float64)

N = len(y)
print(f"\nRegression sample N = {N}")


# --- OLS helper function ---
# INTENT: Implement OLS regression from scratch using the normal equations.
# REASONING: (X'X)^-1 X'y is the standard closed-form OLS estimator.
# Standard errors are derived from the residual variance and the
# (X'X)^-1 matrix diagonal. This avoids sklearn dependency and makes
# the computation fully transparent for audit.
# ASSUMES:
#   - X'X is invertible (checked via np.linalg.inv; will raise if singular)
#   - Errors are homoscedastic (standard OLS assumption; we check residuals later)
#   - No perfect multicollinearity (checked via VIF below)
def ols_regression(X_raw, y, predictor_names):
    """
    Run OLS regression: y = X @ beta + epsilon.

    Parameters:
        X_raw: numpy array of shape (N, k) — predictor columns (no intercept)
        y: numpy array of shape (N,) — dependent variable
        predictor_names: list of str — names corresponding to X_raw columns

    Returns:
        dict with keys: coefficients, std_errors, r_squared, adj_r_squared,
        residuals, predictor_names, N, k
    """
    n = len(y)
    # Add intercept column (column of ones)
    ones = np.ones((n, 1))
    X = np.hstack([ones, X_raw])  # Shape: (N, k+1) where k = number of predictors

    k = X.shape[1]  # Total parameters including intercept
    names = ["intercept"] + list(predictor_names)

    # Normal equations: beta = (X'X)^-1 X'y
    XtX = X.T @ X
    Xty = X.T @ y
    beta = np.linalg.solve(XtX, Xty)  # More numerically stable than inv()

    # Predicted values and residuals
    y_hat = X @ beta
    residuals = y - y_hat

    # R-squared: proportion of variance explained
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot)

    # Adjusted R-squared: penalizes for number of predictors
    # adj_R2 = 1 - (1 - R2) * (n - 1) / (n - k)
    adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k)

    # Standard errors of coefficients
    # Var(beta) = sigma^2 * (X'X)^-1 where sigma^2 = SS_res / (n - k)
    sigma_squared = ss_res / (n - k)
    XtX_inv = np.linalg.inv(XtX)
    se = np.sqrt(np.diag(XtX_inv) * sigma_squared)

    # t-statistics and p-values (two-sided)
    from scipy import stats
    t_stats = beta / se
    p_values = 2 * stats.t.sf(np.abs(t_stats), df=n - k)

    return {
        "coefficients": beta,
        "std_errors": se,
        "t_stats": t_stats,
        "p_values": p_values,
        "r_squared": r_squared,
        "adj_r_squared": adj_r_squared,
        "residuals": residuals,
        "y_hat": y_hat,
        "predictor_names": names,
        "N": n,
        "k": k,
    }


def print_model_results(result, model_name):
    """Print formatted regression results table."""
    print(f"\n{'=' * 70}")
    print(f"  {model_name}")
    print(f"  N = {result['N']:,}   |   R-squared = {result['r_squared']:.4f}   |   Adj. R-squared = {result['adj_r_squared']:.4f}")
    print(f"{'=' * 70}")
    print(f"  {'Variable':<25s} {'Coeff':>10s} {'Std.Err.':>10s} {'t-stat':>10s} {'p-value':>10s}")
    print(f"  {'-' * 65}")
    for i, name in enumerate(result["predictor_names"]):
        coef = result["coefficients"][i]
        se = result["std_errors"][i]
        t = result["t_stats"][i]
        p = result["p_values"][i]
        sig = ""
        if p < 0.001:
            sig = "***"
        elif p < 0.01:
            sig = "**"
        elif p < 0.05:
            sig = "*"
        print(f"  {name:<25s} {coef:>10.4f} {se:>10.4f} {t:>10.3f} {p:>10.4f} {sig}")
    print(f"  {'-' * 65}")
    print(f"  Significance: *** p<0.001, ** p<0.01, * p<0.05")


# --- Model 1: Selectivity Only ---
# INTENT: Establish baseline — how much of graduation rate variation does
# admissions selectivity (admission_rate) explain on its own?
# REASONING: This is the "selectivity-as-quality" hypothesis. If admission_rate
# alone explains most variance, it supports the view that selectivity = quality.
# A low R-squared here suggests other factors matter substantially.
# ASSUMES: admission_rate is 0-1 proportion where lower = more selective.
#   Coefficient should be NEGATIVE (lower admission rate -> higher grad rate).
print("\n" + "#" * 70)
print("# REGRESSION ANALYSIS: Three Nested OLS Models")
print("#" * 70)

X1 = x_admission.reshape(-1, 1)
m1 = ols_regression(X1, y, ["admission_rate"])
print_model_results(m1, "Model 1: grad_rate ~ admission_rate")

# --- Model 2: Selectivity + Student Body Composition ---
# INTENT: Add pell_share and urm_share to test whether student body composition
# explains ADDITIONAL variance beyond selectivity alone.
# REASONING: This is the KEY comparison. If R-squared increases substantially
# (>0.10 per Plan's Observable Truth), it demonstrates that graduation rates
# reflect who attends, not just institutional quality.
# ASSUMES:
#   - pell_share and urm_share are 0-1 proportions
#   - Known collinearity: pell_share x urm_share r=0.638 (from Stage 7 EDA)
#   - Collinearity inflates standard errors but does not bias coefficients
X2 = np.column_stack([x_admission, x_pell, x_urm])
m2 = ols_regression(X2, y, ["admission_rate", "pell_share", "urm_share"])
print_model_results(m2, "Model 2: grad_rate ~ admission_rate + pell_share + urm_share")

# --- Model 3: Full Model ---
# INTENT: Add institutional characteristics (student-faculty ratio, sector) to
# test whether resources and governance explain additional variance beyond
# selectivity and student composition.
# REASONING: If R-squared increases further, institutional resources matter
# independently. If the increase is small, most explanatory power comes from
# selectivity and composition — reinforcing the "inputs vs quality" narrative.
# ASSUMES:
#   - student_faculty_ratio is continuous (lower = more resources per student)
#   - sector_private is binary (0=public, 1=private nonprofit)
X3 = np.column_stack([x_admission, x_pell, x_urm, x_sfr, x_private])
m3 = ols_regression(X3, y, ["admission_rate", "pell_share", "urm_share",
                              "student_faculty_ratio", "sector_private"])
print_model_results(m3, "Model 3: grad_rate ~ admission_rate + pell_share + urm_share + student_faculty_ratio + sector_private")

# --- Model Comparison ---
# INTENT: Summarize R-squared progression across models to quantify the
# incremental explanatory power of each variable group.
# REASONING: The key finding is the R-squared INCREASE from Model 1 to Model 2.
# This directly tests the Observable Truth: "Adding student body composition
# to selectivity explains substantially more variance (R-squared increase > 0.10)."
print("\n" + "=" * 70)
print("  MODEL COMPARISON: R-squared Progression")
print("=" * 70)
r2_m1 = m1["r_squared"]
r2_m2 = m2["r_squared"]
r2_m3 = m3["r_squared"]

delta_1_to_2 = r2_m2 - r2_m1
delta_2_to_3 = r2_m3 - r2_m2

print(f"  Model 1 (selectivity only):           R2 = {r2_m1:.4f}")
print(f"  Model 2 (+composition):               R2 = {r2_m2:.4f}  (delta = +{delta_1_to_2:.4f})")
print(f"  Model 3 (+resources & sector):        R2 = {r2_m3:.4f}  (delta = +{delta_2_to_3:.4f})")
print(f"\n  KEY: Model 1 -> Model 2 R2 increase = {delta_1_to_2:.4f}")
observable_truth_met = delta_1_to_2 > 0.10
print(f"  Observable Truth (delta > 0.10): {'SATISFIED' if observable_truth_met else 'NOT SATISFIED'}")

# --- VIF Analysis (Plan-Checker Addition) ---
# INTENT: Compute Variance Inflation Factors for all Model 3 predictors to
# quantify multicollinearity severity. VIF > 5 indicates concerning collinearity;
# VIF > 10 indicates severe collinearity that destabilizes coefficient estimates.
# REASONING: pell_share and urm_share have known r=0.638 correlation from EDA.
# VIF quantifies how much this inflates their standard errors. High VIF doesn't
# bias coefficients but makes them less precise — important for interpretation.
# ASSUMES: VIF is calculated as 1/(1-R2) from regressing each predictor on all
# other predictors. This is the standard collinearity diagnostic.
print("\n" + "=" * 70)
print("  VIF ANALYSIS (Variance Inflation Factors) — Model 3 Predictors")
print("=" * 70)

predictor_names_m3 = ["admission_rate", "pell_share", "urm_share",
                       "student_faculty_ratio", "sector_private"]
X3_full = np.column_stack([x_admission, x_pell, x_urm, x_sfr, x_private])

vif_results = {}
for i, name in enumerate(predictor_names_m3):
    # Regress predictor i on all other predictors
    y_vif = X3_full[:, i]
    X_others = np.delete(X3_full, i, axis=1)  # All columns except column i

    # Add intercept
    ones = np.ones((len(y_vif), 1))
    X_vif = np.hstack([ones, X_others])

    # OLS for R-squared
    beta_vif = np.linalg.solve(X_vif.T @ X_vif, X_vif.T @ y_vif)
    y_hat_vif = X_vif @ beta_vif
    ss_res_vif = np.sum((y_vif - y_hat_vif) ** 2)
    ss_tot_vif = np.sum((y_vif - np.mean(y_vif)) ** 2)
    r2_vif = 1 - (ss_res_vif / ss_tot_vif)

    vif = 1 / (1 - r2_vif) if r2_vif < 1 else float("inf")
    vif_results[name] = vif

    flag = " *** CONCERNING" if vif > 5 else ""
    print(f"  {name:<25s}  VIF = {vif:.3f}{flag}")

any_vif_concerning = any(v > 5 for v in vif_results.values())
print(f"\n  Any VIF > 5: {any_vif_concerning}")
if any_vif_concerning:
    print("  NOTE: High VIF inflates standard errors but does NOT bias coefficients.")
    print("  Interpretation: coefficient MAGNITUDES are reliable; p-values may be conservative.")

# --- Residual Diagnostics (Plan-Checker Addition) ---
# INTENT: Check OLS assumptions for Model 3 residuals: mean ~0, normality
# approximation, and heteroscedasticity by predicted quartile.
# REASONING: Violated assumptions don't invalidate supplementary OLS for
# descriptive purposes, but we must document violations for the report.
# The Risk Register rates this as Medium likelihood / Low impact since
# regressions are supplementary to descriptive analysis.
# ASSUMES: Residuals from Model 3 are stored in m3["residuals"].
print("\n" + "=" * 70)
print("  RESIDUAL DIAGNOSTICS — Model 3")
print("=" * 70)

resid = m3["residuals"]
y_hat_m3 = m3["y_hat"]

print(f"  Residual mean:   {np.mean(resid):.6f}  (should be ~0)")
print(f"  Residual std:    {np.std(resid):.4f}")
print(f"  Residual min:    {np.min(resid):.4f}")
print(f"  Residual max:    {np.max(resid):.4f}")
print(f"  Residual median: {np.median(resid):.4f}")

# Heteroscedasticity check: residual spread by predicted value quartile
# INTENT: If residual variance increases with predicted values, OLS standard
# errors are biased — a common pattern with rate-bounded outcomes like grad rates.
# REASONING: Graduation rates are bounded 0-100, so variance naturally compresses
# at the extremes. Checking by quartile reveals this pattern.
print(f"\n  Heteroscedasticity check (residual stats by predicted quartile):")
quartiles = np.percentile(y_hat_m3, [25, 50, 75])
q_labels = [
    f"Q1 (predicted <= {quartiles[0]:.1f})",
    f"Q2 ({quartiles[0]:.1f} < predicted <= {quartiles[1]:.1f})",
    f"Q3 ({quartiles[1]:.1f} < predicted <= {quartiles[2]:.1f})",
    f"Q4 (predicted > {quartiles[2]:.1f})",
]
q_masks = [
    y_hat_m3 <= quartiles[0],
    (y_hat_m3 > quartiles[0]) & (y_hat_m3 <= quartiles[1]),
    (y_hat_m3 > quartiles[1]) & (y_hat_m3 <= quartiles[2]),
    y_hat_m3 > quartiles[2],
]

print(f"  {'Quartile':<50s} {'N':>6s} {'Mean Resid':>12s} {'Std Resid':>12s} {'Range':>14s}")
print(f"  {'-' * 94}")
resid_stds = []
for label, mask in zip(q_labels, q_masks):
    r_q = resid[mask]
    r_std = np.std(r_q)
    resid_stds.append(r_std)
    print(f"  {label:<50s} {len(r_q):>6d} {np.mean(r_q):>12.4f} {r_std:>12.4f} {np.max(r_q)-np.min(r_q):>14.4f}")

# Check if residual std varies substantially across quartiles (ratio > 2 is concerning)
max_std = max(resid_stds)
min_std = min(resid_stds)
std_ratio = max_std / min_std if min_std > 0 else float("inf")
print(f"\n  Max/Min residual std ratio: {std_ratio:.3f}")
if std_ratio > 2:
    print("  WARNING: Heteroscedasticity detected (ratio > 2). Standard errors may be biased.")
    print("  IMPACT: Low — regressions are supplementary; coefficient directions remain informative.")
else:
    print("  Residual variance appears roughly constant across predicted quartiles.")

# --- Post-state ---
print(f"\nPost-state: Regression sample = {N:,} rows (from {pre_rows:,} total)")
print(f"Row change from listwise deletion: {N - pre_rows:+,} ({(N - pre_rows) / pre_rows * 100:+.1f}%)")

# --- Save ---
# INTENT: Save regression results as a tidy parquet table for downstream
# report-writer and notebook-assembler consumption.
# REASONING: One row per coefficient per model allows easy filtering and
# tabulation. Model-level metrics (R-squared, N) are repeated per row for
# self-contained extraction.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

rows = []
for model_name, result in [("Model 1: Selectivity Only", m1),
                             ("Model 2: + Composition", m2),
                             ("Model 3: Full", m3)]:
    for i, pname in enumerate(result["predictor_names"]):
        rows.append({
            "model": model_name,
            "variable": pname,
            "coefficient": float(result["coefficients"][i]),
            "std_error": float(result["std_errors"][i]),
            "t_statistic": float(result["t_stats"][i]),
            "p_value": float(result["p_values"][i]),
            "r_squared": float(result["r_squared"]),
            "adj_r_squared": float(result["adj_r_squared"]),
            "n_obs": int(result["N"]),
        })

# Add model comparison summary rows
rows.append({
    "model": "Comparison",
    "variable": "R2_model1",
    "coefficient": float(r2_m1),
    "std_error": 0.0,
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": float(r2_m1),
    "adj_r_squared": float(m1["adj_r_squared"]),
    "n_obs": int(N),
})
rows.append({
    "model": "Comparison",
    "variable": "R2_model2",
    "coefficient": float(r2_m2),
    "std_error": 0.0,
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": float(r2_m2),
    "adj_r_squared": float(m2["adj_r_squared"]),
    "n_obs": int(N),
})
rows.append({
    "model": "Comparison",
    "variable": "R2_model3",
    "coefficient": float(r2_m3),
    "std_error": 0.0,
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": float(r2_m3),
    "adj_r_squared": float(m3["adj_r_squared"]),
    "n_obs": int(N),
})
rows.append({
    "model": "Comparison",
    "variable": "R2_delta_M1_to_M2",
    "coefficient": float(delta_1_to_2),
    "std_error": 0.0,
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": 0.0,
    "adj_r_squared": 0.0,
    "n_obs": int(N),
})
rows.append({
    "model": "Comparison",
    "variable": "R2_delta_M2_to_M3",
    "coefficient": float(delta_2_to_3),
    "std_error": 0.0,
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": 0.0,
    "adj_r_squared": 0.0,
    "n_obs": int(N),
})

# Add VIF results
for vif_name, vif_val in vif_results.items():
    rows.append({
        "model": "Diagnostics",
        "variable": f"VIF_{vif_name}",
        "coefficient": float(vif_val),
        "std_error": 0.0,
        "t_statistic": 0.0,
        "p_value": 0.0,
        "r_squared": 0.0,
        "adj_r_squared": 0.0,
        "n_obs": int(N),
    })

# Add residual diagnostics
rows.append({
    "model": "Diagnostics",
    "variable": "resid_mean",
    "coefficient": float(np.mean(resid)),
    "std_error": float(np.std(resid)),
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": 0.0,
    "adj_r_squared": 0.0,
    "n_obs": int(N),
})
rows.append({
    "model": "Diagnostics",
    "variable": "resid_std_ratio",
    "coefficient": float(std_ratio),
    "std_error": 0.0,
    "t_statistic": 0.0,
    "p_value": 0.0,
    "r_squared": 0.0,
    "adj_r_squared": 0.0,
    "n_obs": int(N),
})

df_results = pl.DataFrame(rows)
df_results.write_parquet(OUTPUT_PATH)
print(f"\nSaved regression results: {OUTPUT_PATH}")
print(f"Results table: {df_results.shape[0]} rows x {df_results.shape[1]} cols")

# --- CP4 Validation ---
# Checkpoint validation: verify all three models produced valid results,
# R-squared values are reasonable, and key directional expectations are met.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

# CP4.1: All three models have valid R-squared (0 <= R2 <= 1)
r2_valid = all(0 <= r <= 1 for r in [r2_m1, r2_m2, r2_m3])
print(f"  [{'PASS' if r2_valid else 'FAIL'}] All R-squared values in [0, 1]: M1={r2_m1:.4f}, M2={r2_m2:.4f}, M3={r2_m3:.4f}")

# CP4.2: R-squared increases monotonically from M1 to M3
# (Adding variables to OLS cannot decrease R-squared by construction)
r2_monotonic = r2_m1 <= r2_m2 <= r2_m3
print(f"  [{'PASS' if r2_monotonic else 'FAIL'}] R-squared monotonically increasing: {r2_m1:.4f} <= {r2_m2:.4f} <= {r2_m3:.4f}")

# CP4.3: admission_rate coefficient is negative (higher admission = lower grad rate)
adm_coef_m1 = m1["coefficients"][1]  # Index 1 = admission_rate (index 0 = intercept)
adm_negative = adm_coef_m1 < 0
print(f"  [{'PASS' if adm_negative else 'FAIL'}] admission_rate coefficient negative: {adm_coef_m1:.4f}")

# CP4.4: Sample size documented and within expected range (1200-1518)
n_in_range = 1200 <= N <= 1518
print(f"  [{'PASS' if n_in_range else 'WARN'}] Sample size in expected range: N={N} (expected 1200-1518)")

# CP4.5: Model comparison documented (R-squared differences)
delta_documented = delta_1_to_2 > 0 and delta_2_to_3 >= 0
print(f"  [{'PASS' if delta_documented else 'FAIL'}] R-squared deltas documented: M1->M2={delta_1_to_2:.4f}, M2->M3={delta_2_to_3:.4f}")

# CP4.6: VIF computed for all Model 3 predictors
vif_complete = len(vif_results) == 5
print(f"  [{'PASS' if vif_complete else 'FAIL'}] VIF computed for all 5 predictors: {vif_complete}")

# CP4.7: Residual diagnostics reported
resid_checked = abs(np.mean(resid)) < 0.01  # Residual mean should be ~0
print(f"  [{'PASS' if resid_checked else 'WARN'}] Residual mean near zero: {np.mean(resid):.6f}")

# CP4.8: Output file exists and is readable
output_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if output_exists else 'FAIL'}] Output file exists: {output_exists}")

all_passed = all([r2_valid, r2_monotonic, adm_negative, n_in_range,
                   delta_documented, vif_complete, resid_checked, output_exists])

assert r2_valid, "STOP: Invalid R-squared values"
assert r2_monotonic, "STOP: R-squared not monotonically increasing"
assert adm_negative, "STOP: admission_rate coefficient should be negative"
assert output_exists, "STOP: Output file not saved"

print("\n" + "=" * 60)
if all_passed:
    print("CP4 VALIDATION: PASSED")
else:
    print("CP4 VALIDATION: PASSED WITH WARNINGS")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:04:23
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/06_regression-models.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: OLS Regression Models
# ============================================================
# Loaded: 2,528 rows x 26 cols
# 
# Pre-state: 2,528 rows, 26 cols
# 
# Missingness in critical columns:
#   grad_rate_150pct: 732 nulls (29.0%)
#   admission_rate: 869 nulls (34.4%)
#   pell_share: 518 nulls (20.5%)
#   urm_share: 370 nulls (14.6%)
#   student_faculty_ratio: 370 nulls (14.6%)
#   inst_control: 0 nulls (0.0%)
# 
# ------------------------------------------------------------
# Applying listwise deletion for regression sample
# ------------------------------------------------------------
# Complete cases: 1,523 (dropped 1,005, 39.8%)
# 
# inst_control values in regression sample: [1, 2]
# sector_private created: mean = 0.672
# 
# Regression sample N = 1523
# 
# ######################################################################
# # REGRESSION ANALYSIS: Three Nested OLS Models
# ######################################################################
# 
# ======================================================================
#   Model 1: grad_rate ~ admission_rate
#   N = 1,523   |   R-squared = 0.1273   |   Adj. R-squared = 0.1267
# ======================================================================
#   Variable                       Coeff   Std.Err.     t-stat    p-value
#   -----------------------------------------------------------------
#   intercept                    81.0951     1.6016     50.635     0.0000 ***
#   admission_rate              -32.5497     2.1850    -14.897     0.0000 ***
#   -----------------------------------------------------------------
#   Significance: *** p<0.001, ** p<0.01, * p<0.05
# 
# ======================================================================
#   Model 2: grad_rate ~ admission_rate + pell_share + urm_share
#   N = 1,523   |   R-squared = 0.4534   |   Adj. R-squared = 0.4523
# ======================================================================
#   Variable                       Coeff   Std.Err.     t-stat    p-value
#   -----------------------------------------------------------------
#   intercept                    97.9710     1.3892     70.524     0.0000 ***
#   admission_rate              -24.0574     1.7713    -13.582     0.0000 ***
#   pell_share                  -60.3523     2.6232    -23.007     0.0000 ***
#   urm_share                    -0.0900     2.0456     -0.044     0.9649 
#   -----------------------------------------------------------------
#   Significance: *** p<0.001, ** p<0.01, * p<0.05
# 
# ======================================================================
#   Model 3: grad_rate ~ admission_rate + pell_share + urm_share + student_faculty_ratio + sector_private
#   N = 1,523   |   R-squared = 0.4559   |   Adj. R-squared = 0.4541
# ======================================================================
#   Variable                       Coeff   Std.Err.     t-stat    p-value
#   -----------------------------------------------------------------
#   intercept                    97.7494     1.9966     48.959     0.0000 ***
#   admission_rate              -22.9603     1.8173    -12.634     0.0000 ***
#   pell_share                  -60.5583     2.6652    -22.722     0.0000 ***
#   urm_share                     0.9454     2.0857      0.453     0.6504 
#   student_faculty_ratio        -0.1145     0.0902     -1.269     0.2046 
#   sector_private                1.2217     0.8827      1.384     0.1666 
#   -----------------------------------------------------------------
#   Significance: *** p<0.001, ** p<0.01, * p<0.05
# 
# ======================================================================
#   MODEL COMPARISON: R-squared Progression
# ======================================================================
#   Model 1 (selectivity only):           R2 = 0.1273
#   Model 2 (+composition):               R2 = 0.4534  (delta = +0.3261)
#   Model 3 (+resources & sector):        R2 = 0.4559  (delta = +0.0025)
# 
#   KEY: Model 1 -> Model 2 R2 increase = 0.3261
#   Observable Truth (delta > 0.10): SATISFIED
# 
# ======================================================================
#   VIF ANALYSIS (Variance Inflation Factors) — Model 3 Predictors
# ======================================================================
#   admission_rate             VIF = 1.107
#   pell_share                 VIF = 1.816
#   urm_share                  VIF = 1.781
#   student_faculty_ratio      VIF = 1.451
#   sector_private             VIF = 1.412
# 
#   Any VIF > 5: False
# 
# ======================================================================
#   RESIDUAL DIAGNOSTICS — Model 3
# ======================================================================
#   Residual mean:   0.000000  (should be ~0)
#   Residual std:    13.5893
#   Residual min:    -63.8248
#   Residual max:    55.1961
#   Residual median: 1.4714
# 
#   Heteroscedasticity check (residual stats by predicted quartile):
#   Quartile                                                N   Mean Resid    Std Resid          Range
#   ----------------------------------------------------------------------------------------------
#   Q1 (predicted <= 51.2)                                381       0.8854      15.4478        98.4836
#   Q2 (51.2 < predicted <= 58.5)                         381      -2.1575      12.3317        89.4406
#   Q3 (58.5 < predicted <= 65.3)                         380      -0.8399      13.2048        95.6808
#   Q4 (predicted > 65.3)                                 381       2.1098      12.7666        95.9306
# 
#   Max/Min residual std ratio: 1.253
#   Residual variance appears roughly constant across predicted quartiles.
# 
# Post-state: Regression sample = 1,523 rows (from 2,528 total)
# Row change from listwise deletion: -1,005 (-39.8%)
# 
# Saved regression results: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_regression_results.parquet
# Results table: 24 rows x 9 cols
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] All R-squared values in [0, 1]: M1=0.1273, M2=0.4534, M3=0.4559
#   [PASS] R-squared monotonically increasing: 0.1273 <= 0.4534 <= 0.4559
#   [PASS] admission_rate coefficient negative: -32.5497
#   [WARN] Sample size in expected range: N=1523 (expected 1200-1518)
#   [PASS] R-squared deltas documented: M1->M2=0.3261, M2->M3=0.0025
#   [PASS] VIF computed for all 5 predictors: True
#   [PASS] Residual mean near zero: 0.000000
#   [PASS] Output file exists: True
# 
# ============================================================
# CP4 VALIDATION: PASSED WITH WARNINGS
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
