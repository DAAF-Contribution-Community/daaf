#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 4 — Correlation Matrix (QA4a)

Reviewed script: scripts/stage8_analysis/04_correlation-matrix_a.py
Output files: output/analysis/2026-03-29_correlation_matrix.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range (7 variables = 7 rows)
3. No suspicious distributions (degenerate columns)
4. Coded values properly filtered (N/A for correlation output)
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] Verify matrix properties hold even if data ordering changed
7. [Semantic] Verify H1 correlation matches what the research question needs
8. [Boundary] Check for extreme correlations (|r| > 0.99) or near-zero diagonals
9. [Absence] Verify Spearman results were computed (even though not saved)
10. [Downstream] Verify saved parquet is usable by viz-correlation-heatmap

Spot-Checks:
11. Recompute admit_rate x completion_rate_150pct Pearson from raw data
12. Verify matrix symmetry by comparing (i,j) vs (j,i) in saved file
13. Verify diagonal is exactly 1.0 in saved file
14. Check Fisher z CI calculation independently
15. Verify listwise N matches complete-case count from input data
"""

import numpy as np
from pathlib import Path
from scipy import stats as scipy_stats

import polars as pl

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

EXPECTED_COLUMNS = [
    "variable", "admit_rate", "completion_rate_150pct", "pell_share",
    "urm_share", "student_faculty_ratio", "retention_rate",
    "instr_expend_per_fte", "n_listwise", "method",
]

CORR_VARS = [
    "admit_rate", "completion_rate_150pct", "pell_share", "urm_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte",
]

EXPECTED_ROWS = 7  # One per variable
CRITICAL_COLUMNS = ["variable"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 4 — Correlation Matrix")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load source data for independent verification
df_src = pl.read_parquet(INPUT_FILE)
print(f"Loaded source: {df_src.shape[0]:,} rows x {df_src.shape[1]} cols")

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
    print(f"  Extra columns: {extra_cols}")

# --- Check 2: Row count ---
rows_ok = df.shape[0] == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {df.shape[0]} (expected {EXPECTED_ROWS})")

# --- Check 3: Distribution sanity ---
# INTENT: For a correlation matrix, check that values in the correlation columns
# are in valid range [-1, 1] and not all identical.
dist_issues = []
for col in CORR_VARS:
    if col in df.columns:
        col_data = df[col].drop_nulls()
        if col_data.min() < -1.0 or col_data.max() > 1.0:
            dist_issues.append(f"{col}: values outside [-1,1] range [{col_data.min():.4f}, {col_data.max():.4f}]")
        if col_data.n_unique() == 1 and len(col_data) > 1:
            dist_issues.append(f"{col}: all same value ({col_data[0]})")

dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
# N/A for correlation matrix output — these are computed correlations, not raw data.
print("[PASS] Coded values: N/A for correlation matrix output")
coded_ok = True

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")

# Also check correlation value columns for nulls
for col in CORR_VARS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls in correlation values")

nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Matrix properties independent of data order ---
# INTENT: Verify that the Pearson matrix from the saved file has correct
# mathematical properties — symmetry and PSD — which would be violated if
# the computation was somehow order-dependent or buggy.
pearson_values = df.select(CORR_VARS).to_numpy()

# Symmetry check
is_symmetric = np.allclose(pearson_values, pearson_values.T, atol=1e-10)
print(f"\n[{'PASS' if is_symmetric else 'FAIL'}] [Counterfactual] Saved matrix is symmetric: {is_symmetric}")

# PSD check
eigenvalues = np.linalg.eigvalsh(pearson_values)
is_psd = np.all(eigenvalues >= -1e-10)
print(f"[{'PASS' if is_psd else 'FAIL'}] [Counterfactual] Saved matrix is PSD: {is_psd} (min eigenvalue: {eigenvalues.min():.6f})")

# --- Check 7: [Semantic] H1 correlation serves the research question ---
# INTENT: Verify the admit_rate x completion_rate_150pct correlation is present
# and its sign is negative (as the research question expects: more selective =
# lower admit rate = higher graduation rate).
h1_row = df.filter(pl.col("variable") == "admit_rate")
h1_r = h1_row["completion_rate_150pct"][0] if len(h1_row) > 0 else None
h1_sign_correct = h1_r is not None and h1_r < 0
h1_magnitude_ok = h1_r is not None and abs(h1_r) > 0.1  # At least a non-trivial effect
print(f"[{'PASS' if h1_sign_correct else 'FAIL'}] [Semantic] H1 correlation is negative: r = {h1_r:.4f}")
print(f"[{'PASS' if h1_magnitude_ok else 'WARN'}] [Semantic] H1 correlation is non-trivial (|r| > 0.1): |r| = {abs(h1_r):.4f}")

# --- Check 8: [Boundary] Check for extreme or degenerate correlations ---
# INTENT: Detect near-perfect correlations (|r| > 0.99 off-diagonal) or
# diagonal values that aren't exactly 1.0, which would indicate data issues.
boundary_issues = []
for i in range(7):
    # Diagonal should be 1.0
    if not np.isclose(pearson_values[i, i], 1.0, atol=1e-10):
        boundary_issues.append(f"Diagonal [{i},{i}] = {pearson_values[i, i]:.6f} (expected 1.0)")
    # Off-diagonal should not be near-perfect
    for j in range(i + 1, 7):
        if abs(pearson_values[i, j]) > 0.99:
            boundary_issues.append(f"Near-perfect correlation: {CORR_VARS[i]} x {CORR_VARS[j]} = {pearson_values[i, j]:.4f}")

boundary_ok = len(boundary_issues) == 0
print(f"[{'PASS' if boundary_ok else 'WARN'}] [Boundary] No extreme correlations: ", end="")
print("OK" if boundary_ok else "; ".join(boundary_issues))

# --- Check 9: [Absence] Spearman comparison presence ---
# INTENT: The script computes both Pearson and Spearman but only saves Pearson.
# Verify the saved method column correctly reports "pearson" and note the
# Spearman absence as an observation.
method_values = df["method"].unique().to_list()
method_correct = method_values == ["pearson"]
print(f"[{'PASS' if method_correct else 'FAIL'}] [Absence] Method column correct: {method_values}")
print(f"[INFO] [Absence] Spearman matrix was computed but NOT saved to parquet.")
print(f"       Downstream viz-correlation-heatmap (Stage 10.4) will only have Pearson.")

# --- Check 10: [Downstream] Saved file is usable by viz-correlation-heatmap ---
# INTENT: The correlation heatmap script will need to pivot or reshape this data.
# Verify the 'variable' column matches the correlation column names for a proper
# matrix structure.
variable_names = df["variable"].to_list()
expected_var_names = CORR_VARS
downstream_ok = variable_names == expected_var_names
print(f"[{'PASS' if downstream_ok else 'FAIL'}] [Downstream] Variable column matches correlation columns: {downstream_ok}")

# Verify n_listwise metadata is present and reasonable
n_listwise = df["n_listwise"][0]
n_listwise_ok = 500 <= n_listwise <= 2000
print(f"[{'PASS' if n_listwise_ok else 'WARN'}] [Downstream] N_listwise metadata: {n_listwise} (expected 500-2000)")

# =============================================================================
# SPOT-CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recompute H1 Pearson from raw data ---
# INTENT: Independently compute the admit_rate x completion_rate_150pct Pearson
# correlation from the source data to verify the saved value.
df_complete = df_src.select(CORR_VARS).drop_nulls()
listwise_n_check = df_complete.shape[0]

x = df_complete["admit_rate"].to_numpy().astype(float)
y = df_complete["completion_rate_150pct"].to_numpy().astype(float)
r_independent = np.corrcoef(x, y)[0, 1]

saved_r = h1_r
match_ok = np.isclose(r_independent, saved_r, atol=1e-4)
print(f"\n[{'PASS' if match_ok else 'FAIL'}] Spot-check: Recomputed H1 Pearson r = {r_independent:.4f} vs saved = {saved_r:.4f}")

# --- Spot-Check 12: Verify (i,j) == (j,i) in saved file ---
# INTENT: Pick a specific off-diagonal pair and verify symmetry.
# Use pell_share x retention_rate as a non-obvious choice.
pell_row = df.filter(pl.col("variable") == "pell_share")
retention_row = df.filter(pl.col("variable") == "retention_rate")

pell_retention = pell_row["retention_rate"][0]
retention_pell = retention_row["pell_share"][0]
symm_match = np.isclose(pell_retention, retention_pell, atol=1e-10)
print(f"[{'PASS' if symm_match else 'FAIL'}] Spot-check: pell_share x retention_rate = {pell_retention:.4f}, retention_rate x pell_share = {retention_pell:.4f}")

# --- Spot-Check 13: Verify diagonal is exactly 1.0 ---
for i, var in enumerate(CORR_VARS):
    row = df.filter(pl.col("variable") == var)
    diag_val = row[var][0]
    if not np.isclose(diag_val, 1.0, atol=1e-10):
        print(f"[FAIL] Spot-check: Diagonal for {var} = {diag_val:.10f} (expected 1.0)")
        break
else:
    print(f"[PASS] Spot-check: All 7 diagonal values are exactly 1.0")

# --- Spot-Check 14: Independent Fisher z CI calculation ---
# INTENT: Recompute the 95% CI for the H1 correlation independently.
r_h1 = r_independent  # Use our independently computed r
n_ci = listwise_n_check
z_fisher = np.arctanh(r_h1)
se_fisher = 1.0 / np.sqrt(n_ci - 3)
z_lo_check = z_fisher - 1.96 * se_fisher
z_hi_check = z_fisher + 1.96 * se_fisher
r_lo_check = np.tanh(z_lo_check)
r_hi_check = np.tanh(z_hi_check)

# Compare to values from execution log: CI: [-0.3775, -0.2897]
ci_reasonable = r_lo_check < r_h1 < r_hi_check and r_lo_check < 0 and r_hi_check < 0
print(f"[{'PASS' if ci_reasonable else 'FAIL'}] Spot-check: Fisher z CI = [{r_lo_check:.4f}, {r_hi_check:.4f}] for r = {r_h1:.4f}")

# --- Spot-Check 15: Listwise N matches complete-case count ---
saved_n = int(df["n_listwise"][0])
computed_n = df_complete.shape[0]
n_match = saved_n == computed_n
print(f"[{'PASS' if n_match else 'FAIL'}] Spot-check: Saved N = {saved_n}, computed N = {computed_n}")

# =============================================================================
# ADDITIONAL DOMAIN-SPECIFIC CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("ADDITIONAL CHECKS")
print("=" * 60)

# --- Check: Pearson-Spearman divergence for instr_expend_per_fte ---
# INTENT: Risk register flagged that finance outliers inflate Pearson.
# Recompute both Pearson and Spearman for admit_rate x instr_expend_per_fte
# to verify the large divergence reported in the execution log (diff=0.2395).
x_admit = df_complete["admit_rate"].to_numpy().astype(float)
x_expend = df_complete["instr_expend_per_fte"].to_numpy().astype(float)

r_pearson_ae = np.corrcoef(x_admit, x_expend)[0, 1]
r_spearman_ae, _ = scipy_stats.spearmanr(x_admit, x_expend)
divergence = abs(r_pearson_ae - r_spearman_ae)

print(f"\n[INFO] admit_rate x instr_expend_per_fte:")
print(f"       Pearson = {r_pearson_ae:.4f}, Spearman = {r_spearman_ae:.4f}, diff = {divergence:.4f}")
if divergence > 0.20:
    print(f"[WARN] Large Pearson-Spearman divergence ({divergence:.4f} > 0.20) for finance variable.")
    print(f"       Risk register: 'Finance outliers inflate Pearson'. Confirmed.")
else:
    print(f"[PASS] Divergence within expected range")

# --- Check: Listwise deletion bias assessment ---
# INTENT: Verify that listwise N is above 50% of total, per QA tolerance.
listwise_pct = computed_n / df_src.shape[0] * 100
listwise_above_threshold = listwise_pct >= 50
print(f"\n[{'PASS' if listwise_above_threshold else 'WARN'}] Listwise N as % of total: {listwise_pct:.1f}% (threshold: >= 50%)")

# --- Check: Hardcoded comment accuracy ---
# INTENT: The script's inline comments say "~39.5% null admit_rate + ~28.1%
# null retention_rate" but the actual execution log shows 16.5% and 2.6%.
# Verify the actual missingness to flag the inaccurate comment.
actual_admit_null_pct = df_src["admit_rate"].null_count() / df_src.shape[0] * 100
actual_retention_null_pct = df_src["retention_rate"].null_count() / df_src.shape[0] * 100
print(f"\n[INFO] Actual missingness: admit_rate={actual_admit_null_pct:.1f}%, retention_rate={actual_retention_null_pct:.1f}%")
print(f"[WARN] Script comments claim '~39.5% null admit_rate + ~28.1% null retention_rate'")
print(f"       Actual values are {actual_admit_null_pct:.1f}% and {actual_retention_null_pct:.1f}%.")
print(f"       Comments appear to be from a different dataset or prior analysis version.")

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nSaved correlation matrix (full):")
print(df)

print("\nDescriptive statistics of correlation values:")
print(df.select(CORR_VARS).describe())

print("\nVariable column values:")
print(df["variable"].to_list())

print("\nMetadata columns:")
print(f"  n_listwise: {df['n_listwise'].unique().to_list()}")
print(f"  method: {df['method'].unique().to_list()}")

print("\nSource data summary for correlation variables:")
for var in CORR_VARS:
    if var in df_src.columns:
        null_pct = df_src[var].null_count() / df_src.shape[0] * 100
        non_null = df_src[var].drop_nulls()
        print(f"  {var}: nulls={null_pct:.1f}%, min={non_null.min():.4f}, max={non_null.max():.4f}, mean={non_null.mean():.4f}")

# --- Summary ---
all_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
                  is_symmetric, is_psd, h1_sign_correct, boundary_ok,
                  method_correct, downstream_ok, match_ok, symm_match,
                  n_match, listwise_above_threshold])

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if not all_passed:
    print("See individual check results above for details.")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:19:30
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_04_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 4 — Correlation Matrix
# ============================================================
# Loaded output: 7 rows x 10 cols
# Loaded source: 1,946 rows x 25 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 7 (expected 7)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: N/A for correlation matrix output
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] [Counterfactual] Saved matrix is symmetric: True
# [PASS] [Counterfactual] Saved matrix is PSD: True (min eigenvalue: 0.313511)
# [PASS] [Semantic] H1 correlation is negative: r = -0.3343
# [PASS] [Semantic] H1 correlation is non-trivial (|r| > 0.1): |r| = 0.3343
# [PASS] [Boundary] No extreme correlations: OK
# [PASS] [Absence] Method column correct: ['pearson']
# [INFO] [Absence] Spearman matrix was computed but NOT saved to parquet.
#        Downstream viz-correlation-heatmap (Stage 10.4) will only have Pearson.
# [PASS] [Downstream] Variable column matches correlation columns: True
# [PASS] [Downstream] N_listwise metadata: 1574 (expected 500-2000)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [PASS] Spot-check: Recomputed H1 Pearson r = -0.3343 vs saved = -0.3343
# [PASS] Spot-check: pell_share x retention_rate = -0.1572, retention_rate x pell_share = -0.1572
# [PASS] Spot-check: All 7 diagonal values are exactly 1.0
# [PASS] Spot-check: Fisher z CI = [-0.3775, -0.2897] for r = -0.3343
# [PASS] Spot-check: Saved N = 1574, computed N = 1574
# 
# ============================================================
# ADDITIONAL CHECKS
# ============================================================
# 
# [INFO] admit_rate x instr_expend_per_fte:
#        Pearson = -0.4354, Spearman = -0.1959, diff = 0.2395
# [WARN] Large Pearson-Spearman divergence (0.2395 > 0.20) for finance variable.
#        Risk register: 'Finance outliers inflate Pearson'. Confirmed.
# 
# [PASS] Listwise N as % of total: 80.9% (threshold: >= 50%)
# 
# [INFO] Actual missingness: admit_rate=16.5%, retention_rate=2.6%
# [WARN] Script comments claim '~39.5% null admit_rate + ~28.1% null retention_rate'
#        Actual values are 16.5% and 2.6%.
#        Comments appear to be from a different dataset or prior analysis version.
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Saved correlation matrix (full):
# shape: (7, 10)
# ┌────────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬─────────┐
# │ variable   ┆ admit_rat ┆ completio ┆ pell_shar ┆ … ┆ retention ┆ instr_exp ┆ n_listwis ┆ method  │
# │ ---        ┆ e         ┆ n_rate_15 ┆ e         ┆   ┆ _rate     ┆ end_per_f ┆ e         ┆ ---     │
# │ str        ┆ ---       ┆ 0pct      ┆ ---       ┆   ┆ ---       ┆ te        ┆ ---       ┆ str     │
# │            ┆ f64       ┆ ---       ┆ f64       ┆   ┆ f64       ┆ ---       ┆ i32       ┆         │
# │            ┆           ┆ f64       ┆           ┆   ┆           ┆ f64       ┆           ┆         │
# ╞════════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═════════╡
# │ admit_rate ┆ 1.0       ┆ -0.334322 ┆ 0.07176   ┆ … ┆ -0.204722 ┆ -0.435373 ┆ 1574      ┆ pearson │
# │ completion ┆ -0.334322 ┆ 1.0       ┆ -0.070188 ┆ … ┆ 0.630062  ┆ 0.450918  ┆ 1574      ┆ pearson │
# │ _rate_150p ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆         │
# │ ct         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆         │
# │ pell_share ┆ 0.07176   ┆ -0.070188 ┆ 1.0       ┆ … ┆ -0.15721  ┆ -0.122755 ┆ 1574      ┆ pearson │
# │ urm_share  ┆ -0.020784 ┆ -0.364894 ┆ 0.036626  ┆ … ┆ -0.271063 ┆ -0.128985 ┆ 1574      ┆ pearson │
# │ student_fa ┆ 0.213793  ┆ -0.222305 ┆ -0.171203 ┆ … ┆ 0.023287  ┆ -0.352811 ┆ 1574      ┆ pearson │
# │ culty_rati ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆         │
# │ o          ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆         │
# │ retention_ ┆ -0.204722 ┆ 0.630062  ┆ -0.15721  ┆ … ┆ 1.0       ┆ 0.307854  ┆ 1574      ┆ pearson │
# │ rate       ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆         │
# │ instr_expe ┆ -0.435373 ┆ 0.450918  ┆ -0.122755 ┆ … ┆ 0.307854  ┆ 1.0       ┆ 1574      ┆ pearson │
# │ nd_per_fte ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆         │
# └────────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴─────────┘
# 
# Descriptive statistics of correlation values:
# shape: (9, 8)
# ┌────────────┬────────────┬────────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ admit_rate ┆ completion ┆ pell_shar ┆ urm_share ┆ student_f ┆ retention ┆ instr_exp │
# │ ---        ┆ ---        ┆ _rate_150p ┆ e         ┆ ---       ┆ aculty_ra ┆ _rate     ┆ end_per_f │
# │ str        ┆ f64        ┆ ct         ┆ ---       ┆ f64       ┆ tio       ┆ ---       ┆ te        │
# │            ┆            ┆ ---        ┆ f64       ┆           ┆ ---       ┆ f64       ┆ ---       │
# │            ┆            ┆ f64        ┆           ┆           ┆ f64       ┆           ┆ f64       │
# ╞════════════╪════════════╪════════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 7.0        ┆ 7.0        ┆ 7.0       ┆ 7.0       ┆ 7.0       ┆ 7.0       ┆ 7.0       │
# │ null_count ┆ 0.0        ┆ 0.0        ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0       │
# │ mean       ┆ 0.041479   ┆ 0.15561    ┆ 0.083861  ┆ 0.061622  ┆ 0.095888  ┆ 0.189744  ┆ 0.102693  │
# │ std        ┆ 0.480013   ┆ 0.536977   ┆ 0.414585  ┆ 0.452956  ┆ 0.450492  ┆ 0.479648  ┆ 0.511535  │
# │ min        ┆ -0.435373  ┆ -0.364894  ┆ -0.171203 ┆ -0.364894 ┆ -0.352811 ┆ -0.271063 ┆ -0.435373 │
# │ 25%        ┆ -0.204722  ┆ -0.222305  ┆ -0.122755 ┆ -0.128985 ┆ -0.171203 ┆ -0.15721  ┆ -0.128985 │
# │ 50%        ┆ -0.020784  ┆ -0.070188  ┆ -0.070188 ┆ -0.020784 ┆ 0.023287  ┆ 0.023287  ┆ -0.122755 │
# │ 75%        ┆ 0.213793   ┆ 0.630062   ┆ 0.07176   ┆ 0.180456  ┆ 0.213793  ┆ 0.630062  ┆ 0.450918  │
# │ max        ┆ 1.0        ┆ 1.0        ┆ 1.0       ┆ 1.0       ┆ 1.0       ┆ 1.0       ┆ 1.0       │
# └────────────┴────────────┴────────────┴───────────┴───────────┴───────────┴───────────┴───────────┘
# 
# Variable column values:
# ['admit_rate', 'completion_rate_150pct', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate', 'instr_expend_per_fte']
# 
# Metadata columns:
#   n_listwise: [1574]
#   method: ['pearson']
# 
# Source data summary for correlation variables:
#   admit_rate: nulls=16.5%, min=0.0000, max=100.0000, mean=70.4144
#   completion_rate_150pct: nulls=0.0%, min=3.8000, max=100.0000, mean=55.5555
#   pell_share: nulls=3.0%, min=0.0000, max=1.1852, mean=0.1191
#   urm_share: nulls=0.4%, min=0.0000, max=1.0000, mean=0.3326
#   student_faculty_ratio: nulls=0.3%, min=2.0000, max=77.0000, mean=14.0484
#   retention_rate: nulls=2.6%, min=0.0000, max=100.0000, mean=74.0971
#   instr_expend_per_fte: nulls=2.3%, min=148.9469, max=161393.7672, mean=11042.5210
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
