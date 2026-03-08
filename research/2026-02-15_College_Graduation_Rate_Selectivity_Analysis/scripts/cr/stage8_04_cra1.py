#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 7.4 (QA4a — Statistical Validity)

Reviewed script: scripts/stage8_analysis/03_correlation-matrix.py
Output files: output/analysis/2026-02-15_correlation_matrix.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Standard):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

Script-Specific Checks (Five Skeptical Lenses):
6. Counterfactual: What if column order in to_numpy() differs from CONTINUOUS_VARS?
7. Semantic: Does the correlation actually answer the research question?
8. Boundary: Check for constant columns, extreme values, near-degenerate matrix
9. Absence: Is listwise deletion documented; are dropped rows random or systematic?
10. Downstream: Will the viz-correlation-heatmap task get what it expects?

Spot-Checks:
11. Recompute one correlation cell independently (grad_rate vs admission_rate)
12. Verify matrix symmetry by reading output and comparing r[i,j] vs r[j,i]
13. Verify diagonal is exactly 1.0
14. Check that N (sample size) is documented and plausible
15. Verify Spearman by independent rank-based computation for one pair
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_correlation_matrix.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
SCRIPT_PATH = PROJECT_DIR / "scripts" / "stage8_analysis" / "03_correlation-matrix.py"

CONTINUOUS_VARS = [
    "grad_rate_150pct",
    "admission_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
]

EXPECTED_COLUMNS = ["method", "variable"] + CONTINUOUS_VARS
EXPECTED_MIN_ROWS = 12  # 6 Pearson + 6 Spearman
EXPECTED_MAX_ROWS = 12
CRITICAL_COLUMNS = ["method", "variable", "grad_rate_150pct", "admission_rate"]

# --- Load output data ---
print("=" * 60)
print("QA4a INSPECTION: Stage 8 Step 7.4 (correlation-matrix)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load source data for independent verification
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
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distribution of correlation values ---
dist_issues = []
for col in CONTINUOUS_VARS:
    if col in df.columns:
        col_data = df[col].drop_nulls()
        if len(col_data) == 0:
            dist_issues.append(f"{col}: all null")
        elif col_data.n_unique() == 1 and len(col_data) > 2:
            dist_issues.append(f"{col}: all same value ({col_data[0]})")
        # Correlations should be between -1 and 1
        if col_data.min() < -1.0 or col_data.max() > 1.0:
            dist_issues.append(f"{col}: values outside [-1, 1] range (min={col_data.min()}, max={col_data.max()})")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("All correlation values in valid range" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values (N/A for correlation matrix — no integer codes expected) ---
print("[PASS] Coded values: N/A (output is correlation coefficients, not raw data)")
coded_ok = True

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

# ===================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ===================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6 (Counterfactual): Column order in to_numpy() ---
# CONCERN: If Polars reorders columns when converting to numpy, the
# correlation matrix labels would be wrong. Verify by computing one
# correlation independently.
print("\n--- Check 6: Counterfactual — Column order in to_numpy() ---")
df_complete = df_source.select(CONTINUOUS_VARS).drop_nulls()
np_data = df_complete.to_numpy()
# Verify column 0 is grad_rate_150pct by checking its stats against Polars
np_col0_mean = float(np.mean(np_data[:, 0]))
pl_grad_mean = float(df_complete["grad_rate_150pct"].mean())
col_order_ok = abs(np_col0_mean - pl_grad_mean) < 1e-10
print(f"  numpy col 0 mean: {np_col0_mean:.6f}")
print(f"  Polars grad_rate mean: {pl_grad_mean:.6f}")
print(f"  [{'PASS' if col_order_ok else 'FAIL'}] Column order preserved in to_numpy(): {col_order_ok}")

# --- Check 7 (Semantic): Does correlation answer the research question? ---
print("\n--- Check 7: Semantic — Research question alignment ---")
# The research question is about whether graduation rates reflect institutional
# quality or selectivity/demographics. The correlation matrix directly quantifies
# these relationships. Check that the key pairs are present.
pearson_rows = df.filter(pl.col("method") == "pearson")
spearman_rows = df.filter(pl.col("method") == "spearman")
has_both = len(pearson_rows) == 6 and len(spearman_rows) == 6
print(f"  Pearson rows: {len(pearson_rows)}, Spearman rows: {len(spearman_rows)}")
print(f"  [{'PASS' if has_both else 'FAIL'}] Both correlation methods present")

# Check key variable pair: grad_rate vs admission_rate present and non-null
grad_row = pearson_rows.filter(pl.col("variable") == "grad_rate_150pct")
if len(grad_row) == 1:
    grad_adm_corr = float(grad_row["admission_rate"][0])
    semantic_ok = not np.isnan(grad_adm_corr) and -1 <= grad_adm_corr <= 1
    print(f"  Key correlation (grad_rate vs admission_rate Pearson): {grad_adm_corr:.4f}")
    print(f"  [{'PASS' if semantic_ok else 'FAIL'}] Key correlation is a valid number")
else:
    semantic_ok = False
    print("  [FAIL] Could not extract grad_rate_150pct row from Pearson matrix")

# --- Check 8 (Boundary): Constant columns, degenerate matrix ---
print("\n--- Check 8: Boundary — Constant columns, near-degenerate matrix ---")
boundary_ok = True
for col in CONTINUOUS_VARS:
    col_data = df_complete[col]
    col_std = float(col_data.std())
    col_nunique = col_data.n_unique()
    if col_std < 1e-10:
        print(f"  [FAIL] {col}: standard deviation is ~0 (constant column)")
        boundary_ok = False
    elif col_nunique < 10:
        print(f"  [WARN] {col}: only {col_nunique} unique values (may affect correlation)")
    else:
        print(f"  [PASS] {col}: std={col_std:.4f}, {col_nunique} unique values")

# Check for NaN in correlation output
nan_count = 0
for col in CONTINUOUS_VARS:
    if col in df.columns:
        nan_count += df[col].is_nan().sum()
if nan_count > 0:
    print(f"  [FAIL] {nan_count} NaN values in correlation matrix output")
    boundary_ok = False
else:
    print(f"  [PASS] No NaN values in correlation matrix output")
print(f"  [{'PASS' if boundary_ok else 'FAIL'}] Boundary check overall")

# --- Check 9 (Absence): Is listwise deletion loss documented? Systematic missingness? ---
print("\n--- Check 9: Absence — Listwise deletion assessment ---")
n_complete = len(df_complete)
n_total = len(df_source)
drop_pct = (n_total - n_complete) / n_total * 100
print(f"  Total source rows: {n_total}")
print(f"  Complete cases: {n_complete}")
print(f"  Drop rate: {drop_pct:.1f}%")

# Check which variable contributes most to missingness
print("\n  Per-variable null rates (source data):")
max_null_pct = 0
for col in CONTINUOUS_VARS:
    if col in df_source.columns:
        null_ct = df_source[col].null_count()
        null_pct = null_ct / n_total * 100
        print(f"    {col}: {null_ct:,} nulls ({null_pct:.1f}%)")
        max_null_pct = max(max_null_pct, null_pct)

# WARNING threshold: >50% of data dropped
absence_warn = drop_pct > 50
if absence_warn:
    print(f"  [WARN] Listwise deletion dropped {drop_pct:.1f}% of data (>50% threshold)")
else:
    print(f"  [PASS] Listwise deletion dropped {drop_pct:.1f}% of data (within 50% threshold)")

# Check for systematic missingness: are institutions with null admission_rate
# open-admission? (admission_rate is the biggest contributor to missingness)
has_admission = df_source.filter(pl.col("admission_rate").is_not_null())
no_admission = df_source.filter(pl.col("admission_rate").is_null())
if "grad_rate_150pct" in df_source.columns:
    grad_with = has_admission["grad_rate_150pct"].drop_nulls()
    grad_without = no_admission["grad_rate_150pct"].drop_nulls()
    if len(grad_with) > 0 and len(grad_without) > 0:
        mean_with = float(grad_with.mean())
        mean_without = float(grad_without.mean())
        diff = mean_with - mean_without
        print(f"\n  Systematic missingness check (admission_rate):")
        print(f"    Mean grad_rate WHERE admission_rate NOT NULL: {mean_with:.1f}%")
        print(f"    Mean grad_rate WHERE admission_rate IS NULL:  {mean_without:.1f}%")
        print(f"    Difference: {diff:+.1f} percentage points")
        if abs(diff) > 10:
            print(f"    [WARN] Substantial difference — listwise deletion may create selection bias")
        else:
            print(f"    [PASS] Difference is moderate — selection bias concern is low")

# --- Check 10 (Downstream): Will viz-correlation-heatmap get what it expects? ---
print("\n--- Check 10: Downstream — Compatibility with viz-correlation-heatmap ---")
# The downstream task expects: Pearson correlations, variable names as labels,
# a method column to filter by
downstream_ok = True

# Can we filter to just Pearson?
pearson_only = df.filter(pl.col("method") == "pearson")
if len(pearson_only) != 6:
    print(f"  [FAIL] Expected 6 Pearson rows, got {len(pearson_only)}")
    downstream_ok = False
else:
    print(f"  [PASS] Can filter to 6 Pearson rows for heatmap")

# Are variable names interpretable (not numeric indices)?
var_values = pearson_only["variable"].to_list()
expected_vars = CONTINUOUS_VARS
if set(var_values) == set(expected_vars):
    print(f"  [PASS] Variable names match expected labels: {var_values}")
else:
    print(f"  [FAIL] Variable name mismatch: got {var_values}, expected {expected_vars}")
    downstream_ok = False

# Column types correct? Should be str for method/variable, f64 for correlations
method_type = str(df["method"].dtype)
variable_type = str(df["variable"].dtype)
type_ok = "Utf8" in method_type or "String" in method_type
type_ok = type_ok and ("Utf8" in variable_type or "String" in variable_type)
for col in CONTINUOUS_VARS:
    if str(df[col].dtype) not in ("Float64", "Float32"):
        type_ok = False
print(f"  [{'PASS' if type_ok else 'FAIL'}] Column types correct (str for labels, float for values)")

print(f"  [{'PASS' if downstream_ok else 'FAIL'}] Downstream compatibility overall")

# ===================================================================
# SPOT-CHECKS (5)
# ===================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recompute Pearson r for grad_rate vs admission_rate ---
print("\n--- Spot-Check 11: Independent Pearson r computation ---")
grad_vals = df_complete["grad_rate_150pct"].to_numpy()
adm_vals = df_complete["admission_rate"].to_numpy()
# Manual Pearson computation
n = len(grad_vals)
mean_g = np.mean(grad_vals)
mean_a = np.mean(adm_vals)
cov_ga = np.sum((grad_vals - mean_g) * (adm_vals - mean_a)) / (n - 1)
std_g = np.std(grad_vals, ddof=1)
std_a = np.std(adm_vals, ddof=1)
manual_pearson = cov_ga / (std_g * std_a)

# Compare to output
output_pearson = float(pearson_rows.filter(
    pl.col("variable") == "grad_rate_150pct"
)["admission_rate"][0])
diff_pearson = abs(manual_pearson - output_pearson)
pearson_match = diff_pearson < 1e-6
print(f"  Manual Pearson r(grad_rate, admission_rate) = {manual_pearson:.6f}")
print(f"  Output Pearson r(grad_rate, admission_rate) = {output_pearson:.6f}")
print(f"  Difference: {diff_pearson:.2e}")
print(f"  [{'PASS' if pearson_match else 'FAIL'}] Independent computation matches")

# --- Spot-Check 12: Matrix symmetry in output ---
print("\n--- Spot-Check 12: Output matrix symmetry ---")
symmetry_ok = True
for method in ["pearson", "spearman"]:
    method_df = df.filter(pl.col("method") == method)
    for i, var1 in enumerate(CONTINUOUS_VARS):
        for j, var2 in enumerate(CONTINUOUS_VARS):
            if i >= j:
                continue
            row_i = method_df.filter(pl.col("variable") == var1)
            row_j = method_df.filter(pl.col("variable") == var2)
            if len(row_i) == 1 and len(row_j) == 1:
                val_ij = float(row_i[var2][0])
                val_ji = float(row_j[var1][0])
                if abs(val_ij - val_ji) > 1e-10:
                    print(f"  [FAIL] {method} asymmetry: {var1}×{var2}={val_ij:.6f} vs {var2}×{var1}={val_ji:.6f}")
                    symmetry_ok = False
if symmetry_ok:
    print(f"  [PASS] All 30 off-diagonal pairs symmetric for both methods")

# --- Spot-Check 13: Diagonal values are exactly 1.0 ---
print("\n--- Spot-Check 13: Diagonal = 1.0 ---")
diag_ok = True
for method in ["pearson", "spearman"]:
    method_df = df.filter(pl.col("method") == method)
    for var in CONTINUOUS_VARS:
        row = method_df.filter(pl.col("variable") == var)
        if len(row) == 1:
            diag_val = float(row[var][0])
            if abs(diag_val - 1.0) > 1e-10:
                print(f"  [FAIL] {method} {var}: diagonal = {diag_val} (expected 1.0)")
                diag_ok = False
if diag_ok:
    print(f"  [PASS] All 12 diagonal values are 1.0")

# --- Spot-Check 14: Sample size is documented and plausible ---
print("\n--- Spot-Check 14: Sample size documentation ---")
# The execution log shows n=1,518. Verify independently.
independent_n = len(df_complete)
print(f"  Independent N (listwise complete cases): {independent_n:,}")
print(f"  Reported N (from execution log): 1,518")
n_match = independent_n == 1518
print(f"  [{'PASS' if n_match else 'FAIL'}] Sample size matches")

# Is N > 500 (Plan's threshold for regression, also reasonable for correlation)?
n_sufficient = independent_n > 500
print(f"  [{'PASS' if n_sufficient else 'FAIL'}] N > 500 threshold: {independent_n} > 500")

# --- Spot-Check 15: Independent Spearman for one pair ---
print("\n--- Spot-Check 15: Independent Spearman r computation ---")
from scipy.stats import spearmanr
sp_r, sp_p = spearmanr(grad_vals, adm_vals)

output_spearman = float(spearman_rows.filter(
    pl.col("variable") == "grad_rate_150pct"
)["admission_rate"][0])
diff_spearman = abs(sp_r - output_spearman)
spearman_match = diff_spearman < 1e-4  # slightly more tolerance for rank methods
print(f"  scipy.stats.spearmanr(grad_rate, admission_rate) = {sp_r:.6f}")
print(f"  Output Spearman r(grad_rate, admission_rate) = {output_spearman:.6f}")
print(f"  Difference: {diff_spearman:.2e}")
print(f"  [{'PASS' if spearman_match else 'FAIL'}] Independent Spearman computation matches")

# ===================================================================
# SUMMARY
# ===================================================================

all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,  # Standard
    col_order_ok, has_both and semantic_ok, boundary_ok,  # Script-specific
    not absence_warn, downstream_ok,  # Script-specific continued
    pearson_match, symmetry_ok, diag_ok, n_match and n_sufficient, spearman_match,  # Spot-checks
]

all_passed = all(all_checks)

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "WARNING" if not absence_warn else "BLOCKER"
# Override: if only absence_warn triggered (listwise deletion >50%), that's a WARNING not BLOCKER
# But we already checked it's <50% (40%), so no override needed
print(f"QA4a RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cra2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull output data:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nMethod distribution:")
print(df["method"].value_counts())

print("\nVariable values:")
print(df["variable"].value_counts())

print("\nPearson correlations with grad_rate_150pct:")
pearson_grad = pearson_rows.filter(pl.col("variable") == "grad_rate_150pct")
for col in CONTINUOUS_VARS:
    if col != "grad_rate_150pct" and col in pearson_grad.columns:
        val = float(pearson_grad[col][0])
        print(f"  {col}: {val:+.4f}")

print("\nSpearman correlations with grad_rate_150pct:")
spearman_grad = spearman_rows.filter(pl.col("variable") == "grad_rate_150pct")
for col in CONTINUOUS_VARS:
    if col != "grad_rate_150pct" and col in spearman_grad.columns:
        val = float(spearman_grad[col][0])
        print(f"  {col}: {val:+.4f}")

print(f"\nPearson-Spearman comparison (grad_rate row):")
for col in CONTINUOUS_VARS:
    if col != "grad_rate_150pct":
        p_val = float(pearson_grad[col][0])
        s_val = float(spearman_grad[col][0])
        print(f"  {col}: Pearson={p_val:+.4f}, Spearman={s_val:+.4f}, diff={abs(p_val-s_val):.4f}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:55:07
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_04_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA4a INSPECTION: Stage 8 Step 7.4 (correlation-matrix)
# ============================================================
# Loaded output: 12 rows x 8 cols
# Loaded source: 2,528 rows x 26 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 12 (expected 12-12)
# [PASS] Distributions: All correlation values in valid range
# [PASS] Coded values: N/A (output is correlation coefficients, not raw data)
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: Counterfactual — Column order in to_numpy() ---
#   numpy col 0 mean: 58.125955
#   Polars grad_rate mean: 58.125955
#   [PASS] Column order preserved in to_numpy(): True
# 
# --- Check 7: Semantic — Research question alignment ---
#   Pearson rows: 6, Spearman rows: 6
#   [PASS] Both correlation methods present
#   Key correlation (grad_rate vs admission_rate Pearson): -0.3589
#   [PASS] Key correlation is a valid number
# 
# --- Check 8: Boundary — Constant columns, near-degenerate matrix ---
#   [PASS] grad_rate_150pct: std=18.3690, 634 unique values
#   [PASS] admission_rate: std=0.2015, 1475 unique values
#   [PASS] pell_share: std=0.1763, 1503 unique values
#   [PASS] urm_share: std=0.2233, 1448 unique values
#   [PASS] student_faculty_ratio: std=4.6498, 33 unique values
#   [PASS] retention_rate: std=12.2375, 67 unique values
#   [PASS] No NaN values in correlation matrix output
#   [PASS] Boundary check overall
# 
# --- Check 9: Absence — Listwise deletion assessment ---
#   Total source rows: 2528
#   Complete cases: 1518
#   Drop rate: 40.0%
# 
#   Per-variable null rates (source data):
#     grad_rate_150pct: 732 nulls (29.0%)
#     admission_rate: 869 nulls (34.4%)
#     pell_share: 518 nulls (20.5%)
#     urm_share: 370 nulls (14.6%)
#     student_faculty_ratio: 370 nulls (14.6%)
#     retention_rate: 653 nulls (25.8%)
#   [PASS] Listwise deletion dropped 40.0% of data (within 50% threshold)
# 
#   Systematic missingness check (admission_rate):
#     Mean grad_rate WHERE admission_rate NOT NULL: 58.1%
#     Mean grad_rate WHERE admission_rate IS NULL:  44.2%
#     Difference: +13.9 percentage points
#     [WARN] Substantial difference — listwise deletion may create selection bias
# 
# --- Check 10: Downstream — Compatibility with viz-correlation-heatmap ---
#   [PASS] Can filter to 6 Pearson rows for heatmap
#   [PASS] Variable names match expected labels: ['grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
#   [PASS] Column types correct (str for labels, float for values)
#   [PASS] Downstream compatibility overall
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-Check 11: Independent Pearson r computation ---
#   Manual Pearson r(grad_rate, admission_rate) = -0.358870
#   Output Pearson r(grad_rate, admission_rate) = -0.358870
#   Difference: 1.11e-16
#   [PASS] Independent computation matches
# 
# --- Spot-Check 12: Output matrix symmetry ---
#   [PASS] All 30 off-diagonal pairs symmetric for both methods
# 
# --- Spot-Check 13: Diagonal = 1.0 ---
#   [PASS] All 12 diagonal values are 1.0
# 
# --- Spot-Check 14: Sample size documentation ---
#   Independent N (listwise complete cases): 1,518
#   Reported N (from execution log): 1,518
#   [PASS] Sample size matches
#   [PASS] N > 500 threshold: 1518 > 500
# 
# --- Spot-Check 15: Independent Spearman r computation ---
#   scipy.stats.spearmanr(grad_rate, admission_rate) = -0.270243
#   Output Spearman r(grad_rate, admission_rate) = -0.270243
#   Difference: 0.00e+00
#   [PASS] Independent Spearman computation matches
# 
# ============================================================
# QA4a RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full output data:
# shape: (12, 8)
# ┌──────────┬────────────┬────────────┬────────────┬────────────┬───────────┬───────────┬───────────┐
# │ method   ┆ variable   ┆ grad_rate_ ┆ admission_ ┆ pell_share ┆ urm_share ┆ student_f ┆ retention │
# │ ---      ┆ ---        ┆ 150pct     ┆ rate       ┆ ---        ┆ ---       ┆ aculty_ra ┆ _rate     │
# │ str      ┆ str        ┆ ---        ┆ ---        ┆ f64        ┆ f64       ┆ tio       ┆ ---       │
# │          ┆            ┆ f64        ┆ f64        ┆            ┆           ┆ ---       ┆ f64       │
# │          ┆            ┆            ┆            ┆            ┆           ┆ f64       ┆           │
# ╞══════════╪════════════╪════════════╪════════════╪════════════╪═══════════╪═══════════╪═══════════╡
# │ pearson  ┆ grad_rate_ ┆ 1.0        ┆ -0.35887   ┆ -0.620643  ┆ -0.368845 ┆ -0.22016  ┆ 0.629565  │
# │          ┆ 150pct     ┆            ┆            ┆            ┆           ┆           ┆           │
# │ pearson  ┆ admission_ ┆ -0.35887   ┆ 1.0        ┆ 0.160294   ┆ -0.003417 ┆ 0.211869  ┆ -0.217032 │
# │          ┆ rate       ┆            ┆            ┆            ┆           ┆           ┆           │
# │ pearson  ┆ pell_share ┆ -0.620643  ┆ 0.160294   ┆ 1.0        ┆ 0.638491  ┆ 0.221837  ┆ -0.449387 │
# │ pearson  ┆ urm_share  ┆ -0.368845  ┆ -0.003417  ┆ 0.638491   ┆ 1.0       ┆ 0.212461  ┆ -0.261098 │
# │ pearson  ┆ student_fa ┆ -0.22016   ┆ 0.211869   ┆ 0.221837   ┆ 0.212461  ┆ 1.0       ┆ 0.042914  │
# │          ┆ culty_rati ┆            ┆            ┆            ┆           ┆           ┆           │
# │          ┆ o          ┆            ┆            ┆            ┆           ┆           ┆           │
# │ …        ┆ …          ┆ …          ┆ …          ┆ …          ┆ …         ┆ …         ┆ …         │
# │ spearman ┆ admission_ ┆ -0.270243  ┆ 1.0        ┆ 0.151011   ┆ -0.045056 ┆ 0.193802  ┆ -0.192315 │
# │          ┆ rate       ┆            ┆            ┆            ┆           ┆           ┆           │
# │ spearman ┆ pell_share ┆ -0.667163  ┆ 0.151011   ┆ 1.0        ┆ 0.55777   ┆ 0.197758  ┆ -0.544693 │
# │ spearman ┆ urm_share  ┆ -0.346659  ┆ -0.045056  ┆ 0.55777    ┆ 1.0       ┆ 0.155622  ┆ -0.304175 │
# │ spearman ┆ student_fa ┆ -0.233481  ┆ 0.193802   ┆ 0.197758   ┆ 0.155622  ┆ 1.0       ┆ -0.020679 │
# │          ┆ culty_rati ┆            ┆            ┆            ┆           ┆           ┆           │
# │          ┆ o          ┆            ┆            ┆            ┆           ┆           ┆           │
# │ spearman ┆ retention_ ┆ 0.715988   ┆ -0.192315  ┆ -0.544693  ┆ -0.304175 ┆ -0.020679 ┆ 1.0       │
# │          ┆ rate       ┆            ┆            ┆            ┆           ┆           ┆           │
# └──────────┴────────────┴────────────┴────────────┴────────────┴───────────┴───────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 9)
# ┌───────────┬──────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic ┆ method   ┆ variable  ┆ grad_rate ┆ … ┆ pell_shar ┆ urm_share ┆ student_f ┆ retention │
# │ ---       ┆ ---      ┆ ---       ┆ _150pct   ┆   ┆ e         ┆ ---       ┆ aculty_ra ┆ _rate     │
# │ str       ┆ str      ┆ str       ┆ ---       ┆   ┆ ---       ┆ f64       ┆ tio       ┆ ---       │
# │           ┆          ┆           ┆ f64       ┆   ┆ f64       ┆           ┆ ---       ┆ f64       │
# │           ┆          ┆           ┆           ┆   ┆           ┆           ┆ f64       ┆           │
# ╞═══════════╪══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count     ┆ 12       ┆ 12        ┆ 12.0      ┆ … ┆ 12.0      ┆ 12.0      ┆ 12.0      ┆ 12.0      │
# │ null_coun ┆ 0        ┆ 0         ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0       │
# │ t         ┆          ┆           ┆           ┆   ┆           ┆           ┆           ┆           │
# │ mean      ┆ null     ┆ null      ┆ 0.021624  ┆ … ┆ 0.137106  ┆ 0.186258  ┆ 0.230162  ┆ 0.116591  │
# │ std       ┆ null     ┆ null      ┆ 0.624842  ┆ … ┆ 0.599921  ┆ 0.503694  ┆ 0.394241  ┆ 0.563396  │
# │ min       ┆ pearson  ┆ admission ┆ -0.667163 ┆ … ┆ -0.667163 ┆ -0.368845 ┆ -0.233481 ┆ -0.544693 │
# │           ┆          ┆ _rate     ┆           ┆   ┆           ┆           ┆           ┆           │
# │ 25%       ┆ null     ┆ null      ┆ -0.35887  ┆ … ┆ -0.449387 ┆ -0.261098 ┆ 0.042914  ┆ -0.261098 │
# │ 50%       ┆ null     ┆ null      ┆ -0.233481 ┆ … ┆ 0.197758  ┆ 0.155622  ┆ 0.197758  ┆ -0.020679 │
# │ 75%       ┆ null     ┆ null      ┆ 0.629565  ┆ … ┆ 0.55777   ┆ 0.55777   ┆ 0.212461  ┆ 0.629565  │
# │ max       ┆ spearman ┆ urm_share ┆ 1.0       ┆ … ┆ 1.0       ┆ 1.0       ┆ 1.0       ┆ 1.0       │
# └───────────┴──────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Method distribution:
# shape: (2, 2)
# ┌──────────┬───────┐
# │ method   ┆ count │
# │ ---      ┆ ---   │
# │ str      ┆ u32   │
# ╞══════════╪═══════╡
# │ spearman ┆ 6     │
# │ pearson  ┆ 6     │
# └──────────┴───────┘
# 
# Variable values:
# shape: (6, 2)
# ┌───────────────────────┬───────┐
# │ variable              ┆ count │
# │ ---                   ┆ ---   │
# │ str                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ admission_rate        ┆ 2     │
# │ grad_rate_150pct      ┆ 2     │
# │ retention_rate        ┆ 2     │
# │ pell_share            ┆ 2     │
# │ urm_share             ┆ 2     │
# │ student_faculty_ratio ┆ 2     │
# └───────────────────────┴───────┘
# 
# Pearson correlations with grad_rate_150pct:
#   admission_rate: -0.3589
#   pell_share: -0.6206
#   urm_share: -0.3688
#   student_faculty_ratio: -0.2202
#   retention_rate: +0.6296
# 
# Spearman correlations with grad_rate_150pct:
#   admission_rate: -0.2702
#   pell_share: -0.6672
#   urm_share: -0.3467
#   student_faculty_ratio: -0.2335
#   retention_rate: +0.7160
# 
# Pearson-Spearman comparison (grad_rate row):
#   admission_rate: Pearson=-0.3589, Spearman=-0.2702, diff=0.0886
#   pell_share: Pearson=-0.6206, Spearman=-0.6672, diff=0.0465
#   urm_share: Pearson=-0.3688, Spearman=-0.3467, diff=0.0222
#   student_faculty_ratio: Pearson=-0.2202, Spearman=-0.2335, diff=0.0133
#   retention_rate: Pearson=+0.6296, Spearman=+0.7160, diff=0.0864
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
