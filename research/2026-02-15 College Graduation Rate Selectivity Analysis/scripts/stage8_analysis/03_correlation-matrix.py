#!/usr/bin/env python3
"""
Stage 8.1.3: Compute Pearson and Spearman correlation matrices for continuous variables.

Task: correlation-matrix
Wave: 7, Step: 3, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_correlation_matrix.parquet
Checkpoint: CP3 (analysis validation)
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's analysis specification.
# We compute both Pearson (linear) and Spearman (monotonic/rank-based) correlation
# matrices on six continuous variables. Listwise deletion is used so that all
# pairwise correlations are computed on the same sample of observations.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"

# REASONING: These six variables are the continuous measures identified in the Plan
# for correlation analysis. They span outcome (grad_rate_150pct, retention_rate),
# selectivity (admission_rate), and demographic composition (pell_share, urm_share,
# student_faculty_ratio). Together they test the three Observable Truths about the
# relationship between selectivity and graduation rates.
CONTINUOUS_VARS = [
    "grad_rate_150pct",
    "admission_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
]

# --- Load ---
# Load the analysis dataset produced in Stage 7 and verify it has the expected
# shape and columns before proceeding.
print("=" * 60)
print("Stage 8.1.3: Correlation Matrix (Pearson + Spearman)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Verify all continuous variables exist
missing_cols = [c for c in CONTINUOUS_VARS if c not in df.columns]
assert len(missing_cols) == 0, f"STOP: Missing columns: {missing_cols}"
print(f"All {len(CONTINUOUS_VARS)} continuous variables present")

# --- Pre-state ---
# Document null rates per variable BEFORE listwise deletion to show how much
# data is lost and which variables contribute most to the reduction.
print("\n--- Pre-state: Null rates per variable ---")
pre_rows = df.shape[0]

for col in CONTINUOUS_VARS:
    null_ct = df[col].null_count()
    null_pct = null_ct / pre_rows * 100
    print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

# --- Listwise Deletion ---
# INTENT: Drop any row that has a null in ANY of the six continuous variables.
# This ensures all pairwise correlations are computed on the identical set of
# observations, making the correlation matrix internally consistent.
#
# REASONING: Listwise deletion (rather than pairwise deletion) is chosen because:
#   - Pairwise deletion can produce non-positive-definite correlation matrices
#     (each cell computed on a different subset of rows)
#   - With overlapping nulls across variables, we expect ~1,000-1,500 complete cases
#     from 2,528 total, which is still a substantial sample
#   - The correlation matrix is a single coherent summary statistic; it should
#     reflect a single coherent sample
#
# ASSUMES:
#   - Missingness is primarily due to non-reporting (not systematic bias), though
#     institutions that don't report admission_rate may be open-admission schools
#     (a known selection effect we document below)
#   - The remaining sample after deletion is still large enough for reliable
#     correlation estimates (n > 100 is typical minimum; we expect ~1,000+)
df_complete = df.select(CONTINUOUS_VARS).drop_nulls()

post_rows = df_complete.shape[0]
rows_dropped = pre_rows - post_rows
drop_pct = rows_dropped / pre_rows * 100
print(f"\n--- Listwise deletion ---")
print(f"  Rows before: {pre_rows:,}")
print(f"  Rows after:  {post_rows:,}")
print(f"  Rows dropped: {rows_dropped:,} ({drop_pct:.1f}%)")

# REASONING: We assert at least 100 rows remain for correlation to be meaningful.
# With n < 100, individual outliers can dominate and confidence intervals become
# too wide for reliable inference.
assert post_rows >= 100, f"STOP: Only {post_rows} rows after listwise deletion — too few for correlation"

# --- Compute Pearson Correlation ---
# INTENT: Compute the Pearson product-moment correlation matrix to measure
# linear relationships between all pairs of continuous variables.
#
# REASONING: Using numpy's corrcoef on the Polars DataFrame converted to numpy
# because Polars does not have a built-in full correlation matrix method.
# np.corrcoef expects variables in rows (rowvar=True) or columns (rowvar=False).
#
# ASSUMES:
#   - No nulls remain after listwise deletion (verified above)
#   - Variables are at least approximately interval-scaled
print("\n--- Pearson Correlation Matrix ---")

# Convert to numpy for correlation computation
np_data = df_complete.to_numpy()  # shape: (n_obs, n_vars)
pearson_matrix = np.corrcoef(np_data, rowvar=False)  # rowvar=False means each column is a variable

# Format as Polars DataFrame for display and saving
pearson_df = pl.DataFrame(
    {CONTINUOUS_VARS[i]: pearson_matrix[:, i].tolist() for i in range(len(CONTINUOUS_VARS))}
).with_columns(pl.Series("variable", CONTINUOUS_VARS)).select(["variable"] + CONTINUOUS_VARS)

print(pearson_df)

# --- Compute Spearman Rank Correlation ---
# INTENT: Compute the Spearman rank correlation matrix to measure monotonic
# (not necessarily linear) relationships. Spearman is more robust to outliers
# and non-normal distributions than Pearson.
#
# REASONING: Spearman correlation is computed by ranking each variable and then
# computing Pearson on the ranks. This is mathematically equivalent to the
# Spearman rho formula and works correctly for tied values (numpy ranking).
# We use scipy.stats.rankdata for correct tie handling (average method).
#
# ASSUMES:
#   - Same complete-case dataset as Pearson (no nulls)
#   - Ranking uses "average" method for ties (standard for Spearman)
print("\n--- Spearman Rank Correlation Matrix ---")

from scipy.stats import rankdata

# Rank each column independently, handling ties with average method
ranked_data = np.column_stack([
    rankdata(np_data[:, i], method="average") for i in range(np_data.shape[1])
])

spearman_matrix = np.corrcoef(ranked_data, rowvar=False)

spearman_df = pl.DataFrame(
    {CONTINUOUS_VARS[i]: spearman_matrix[:, i].tolist() for i in range(len(CONTINUOUS_VARS))}
).with_columns(pl.Series("variable", CONTINUOUS_VARS)).select(["variable"] + CONTINUOUS_VARS)

print(spearman_df)

# --- Key Correlations Highlighted ---
# INTENT: Extract and interpret the specific correlations that test the three
# Observable Truths from the Plan.
print("\n" + "=" * 60)
print("KEY CORRELATIONS — Observable Truth Tests")
print("=" * 60)

def get_corr(matrix, var1, var2, var_names):
    """Extract correlation between two named variables from a matrix."""
    i = var_names.index(var1)
    j = var_names.index(var2)
    return matrix[i, j]

# Observable Truth 1: "Institutions with lower admission rates have significantly
# higher graduation rates (expect r > 0.5)"
# REASONING: Lower admission_rate = more selective = higher grad_rate, so we
# expect a NEGATIVE Pearson r (low admission correlates with high graduation).
# The Observable Truth states "r > 0.5" which in this context means |r| > 0.5
# with a negative sign.
pearson_grad_adm = get_corr(pearson_matrix, "grad_rate_150pct", "admission_rate", CONTINUOUS_VARS)
spearman_grad_adm = get_corr(spearman_matrix, "grad_rate_150pct", "admission_rate", CONTINUOUS_VARS)
print(f"\n1. grad_rate_150pct vs admission_rate")
print(f"   Pearson r  = {pearson_grad_adm:+.4f}")
print(f"   Spearman r = {spearman_grad_adm:+.4f}")
print(f"   Expected: Strong negative (Observable Truth expects |r| > 0.5)")
if abs(pearson_grad_adm) > 0.5:
    print(f"   Interpretation: SUPPORTED — magnitude {abs(pearson_grad_adm):.3f} exceeds 0.5 threshold")
else:
    print(f"   Interpretation: NOT SUPPORTED — magnitude {abs(pearson_grad_adm):.3f} below 0.5 threshold")

# Observable Truth 2: "Pell share is negatively correlated with graduation rate
# (expect r < -0.3)"
pearson_grad_pell = get_corr(pearson_matrix, "grad_rate_150pct", "pell_share", CONTINUOUS_VARS)
spearman_grad_pell = get_corr(spearman_matrix, "grad_rate_150pct", "pell_share", CONTINUOUS_VARS)
print(f"\n2. grad_rate_150pct vs pell_share")
print(f"   Pearson r  = {pearson_grad_pell:+.4f}")
print(f"   Spearman r = {spearman_grad_pell:+.4f}")
print(f"   Expected: Negative (Observable Truth expects r < -0.3)")
if pearson_grad_pell < -0.3:
    print(f"   Interpretation: SUPPORTED — r = {pearson_grad_pell:.3f} is below -0.3 threshold")
else:
    print(f"   Interpretation: NOT SUPPORTED — r = {pearson_grad_pell:.3f} does not reach -0.3 threshold")

# Observable Truth 3: "URM share is negatively correlated with graduation rate"
pearson_grad_urm = get_corr(pearson_matrix, "grad_rate_150pct", "urm_share", CONTINUOUS_VARS)
spearman_grad_urm = get_corr(spearman_matrix, "grad_rate_150pct", "urm_share", CONTINUOUS_VARS)
print(f"\n3. grad_rate_150pct vs urm_share")
print(f"   Pearson r  = {pearson_grad_urm:+.4f}")
print(f"   Spearman r = {spearman_grad_urm:+.4f}")
print(f"   Expected: Negative")
if pearson_grad_urm < 0:
    print(f"   Interpretation: SUPPORTED — negative correlation observed")
else:
    print(f"   Interpretation: NOT SUPPORTED — positive correlation observed")

# Additional notable correlations
pearson_grad_ret = get_corr(pearson_matrix, "grad_rate_150pct", "retention_rate", CONTINUOUS_VARS)
spearman_grad_ret = get_corr(spearman_matrix, "grad_rate_150pct", "retention_rate", CONTINUOUS_VARS)
print(f"\n4. grad_rate_150pct vs retention_rate (supplementary)")
print(f"   Pearson r  = {pearson_grad_ret:+.4f}")
print(f"   Spearman r = {spearman_grad_ret:+.4f}")
print(f"   Expected: Strong positive (retention is a leading indicator of graduation)")

pearson_adm_pell = get_corr(pearson_matrix, "admission_rate", "pell_share", CONTINUOUS_VARS)
spearman_adm_pell = get_corr(spearman_matrix, "admission_rate", "pell_share", CONTINUOUS_VARS)
print(f"\n5. admission_rate vs pell_share (supplementary)")
print(f"   Pearson r  = {pearson_adm_pell:+.4f}")
print(f"   Spearman r = {spearman_adm_pell:+.4f}")
print(f"   Expected: Positive (less selective schools tend to serve more Pell students)")

pearson_adm_urm = get_corr(pearson_matrix, "admission_rate", "urm_share", CONTINUOUS_VARS)
spearman_adm_urm = get_corr(spearman_matrix, "admission_rate", "urm_share", CONTINUOUS_VARS)
print(f"\n6. admission_rate vs urm_share (supplementary)")
print(f"   Pearson r  = {pearson_adm_urm:+.4f}")
print(f"   Spearman r = {spearman_adm_urm:+.4f}")
print(f"   Expected: Positive (less selective schools tend to have higher URM share)")

# --- Save ---
# INTENT: Save both correlation matrices stacked into a single parquet file
# with a 'method' column distinguishing Pearson from Spearman rows.
#
# REASONING: Stacking with a method column is cleaner than side-by-side because
# each row in the output is a single correlation vector, and downstream consumers
# can filter by method. The parquet file preserves the full precision of float values.
print("\n" + "=" * 60)
print("Saving correlation matrices")
print("=" * 60)

pearson_out = pearson_df.with_columns(pl.lit("pearson").alias("method"))
spearman_out = spearman_df.with_columns(pl.lit("spearman").alias("method"))

combined = pl.concat([pearson_out, spearman_out])

# Reorder columns: method, variable, then correlation values
combined = combined.select(["method", "variable"] + CONTINUOUS_VARS)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
combined.write_parquet(OUTPUT_PATH)
print(f"Saved: {OUTPUT_PATH}")
print(f"Output shape: {combined.shape[0]} rows x {combined.shape[1]} cols")
print(f"  (6 Pearson rows + 6 Spearman rows = 12 total, 8 columns)")

# --- Validate ---
# Checkpoint validation: verify both matrices are symmetric with unit diagonal,
# all values are in [-1, 1], and the output file was saved correctly.
print("\n" + "=" * 60)
print("CP3 VALIDATION (Analysis)")
print("=" * 60)

# CP3.1: Matrices are symmetric (check Pearson; Spearman follows same logic)
is_symmetric = np.allclose(pearson_matrix, pearson_matrix.T, atol=1e-10)
print(f"  [{'PASS' if is_symmetric else 'FAIL'}] Pearson matrix symmetric: {is_symmetric}")

is_symmetric_sp = np.allclose(spearman_matrix, spearman_matrix.T, atol=1e-10)
print(f"  [{'PASS' if is_symmetric_sp else 'FAIL'}] Spearman matrix symmetric: {is_symmetric_sp}")

# CP3.2: Diagonal elements are 1.0 (variable correlated with itself)
diag_pearson = np.diag(pearson_matrix)
diag_ok = np.allclose(diag_pearson, 1.0, atol=1e-10)
print(f"  [{'PASS' if diag_ok else 'FAIL'}] Pearson diagonal = 1.0: {diag_ok}")

diag_spearman = np.diag(spearman_matrix)
diag_ok_sp = np.allclose(diag_spearman, 1.0, atol=1e-10)
print(f"  [{'PASS' if diag_ok_sp else 'FAIL'}] Spearman diagonal = 1.0: {diag_ok_sp}")

# CP3.3: All values in [-1, 1]
all_in_range = np.all((pearson_matrix >= -1.0) & (pearson_matrix <= 1.0))
print(f"  [{'PASS' if all_in_range else 'FAIL'}] Pearson values in [-1, 1]: {all_in_range}")

all_in_range_sp = np.all((spearman_matrix >= -1.0) & (spearman_matrix <= 1.0))
print(f"  [{'PASS' if all_in_range_sp else 'FAIL'}] Spearman values in [-1, 1]: {all_in_range_sp}")

# CP3.4: Sample size documented
print(f"  [PASS] Sample size: n = {post_rows:,} (after listwise deletion from {pre_rows:,})")

# CP3.5: Output file exists and has correct shape
output_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if output_exists else 'FAIL'}] Output file exists: {output_exists}")

if output_exists:
    verify_df = pl.read_parquet(OUTPUT_PATH)
    shape_ok = verify_df.shape == (12, 8)
    print(f"  [{'PASS' if shape_ok else 'FAIL'}] Output shape: {verify_df.shape} (expected (12, 8))")

all_passed = all([
    is_symmetric, is_symmetric_sp,
    diag_ok, diag_ok_sp,
    all_in_range, all_in_range_sp,
    post_rows >= 100,
    output_exists,
])

assert all_passed, "STOP: Validation checks failed"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)

print(f"\nSummary:")
print(f"  Complete cases: n = {post_rows:,} / {pre_rows:,} ({post_rows/pre_rows*100:.1f}%)")
print(f"  Method: Listwise deletion, Pearson + Spearman")
print(f"  Key finding: grad_rate vs admission_rate Pearson r = {pearson_grad_adm:+.4f}")
print(f"  Output: {OUTPUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:51:12
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/03_correlation-matrix.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1.3: Correlation Matrix (Pearson + Spearman)
# ============================================================
# Loaded: 2,528 rows x 26 cols
# All 6 continuous variables present
# 
# --- Pre-state: Null rates per variable ---
#   grad_rate_150pct: 732 nulls (29.0%)
#   admission_rate: 869 nulls (34.4%)
#   pell_share: 518 nulls (20.5%)
#   urm_share: 370 nulls (14.6%)
#   student_faculty_ratio: 370 nulls (14.6%)
#   retention_rate: 653 nulls (25.8%)
# 
# --- Listwise deletion ---
#   Rows before: 2,528
#   Rows after:  1,518
#   Rows dropped: 1,010 (40.0%)
# 
# --- Pearson Correlation Matrix ---
# shape: (6, 7)
# ┌──────────────┬──────────────┬──────────────┬────────────┬───────────┬──────────────┬─────────────┐
# │ variable     ┆ grad_rate_15 ┆ admission_ra ┆ pell_share ┆ urm_share ┆ student_facu ┆ retention_r │
# │ ---          ┆ 0pct         ┆ te           ┆ ---        ┆ ---       ┆ lty_ratio    ┆ ate         │
# │ str          ┆ ---          ┆ ---          ┆ f64        ┆ f64       ┆ ---          ┆ ---         │
# │              ┆ f64          ┆ f64          ┆            ┆           ┆ f64          ┆ f64         │
# ╞══════════════╪══════════════╪══════════════╪════════════╪═══════════╪══════════════╪═════════════╡
# │ grad_rate_15 ┆ 1.0          ┆ -0.35887     ┆ -0.620643  ┆ -0.368845 ┆ -0.22016     ┆ 0.629565    │
# │ 0pct         ┆              ┆              ┆            ┆           ┆              ┆             │
# │ admission_ra ┆ -0.35887     ┆ 1.0          ┆ 0.160294   ┆ -0.003417 ┆ 0.211869     ┆ -0.217032   │
# │ te           ┆              ┆              ┆            ┆           ┆              ┆             │
# │ pell_share   ┆ -0.620643    ┆ 0.160294     ┆ 1.0        ┆ 0.638491  ┆ 0.221837     ┆ -0.449387   │
# │ urm_share    ┆ -0.368845    ┆ -0.003417    ┆ 0.638491   ┆ 1.0       ┆ 0.212461     ┆ -0.261098   │
# │ student_facu ┆ -0.22016     ┆ 0.211869     ┆ 0.221837   ┆ 0.212461  ┆ 1.0          ┆ 0.042914    │
# │ lty_ratio    ┆              ┆              ┆            ┆           ┆              ┆             │
# │ retention_ra ┆ 0.629565     ┆ -0.217032    ┆ -0.449387  ┆ -0.261098 ┆ 0.042914     ┆ 1.0         │
# │ te           ┆              ┆              ┆            ┆           ┆              ┆             │
# └──────────────┴──────────────┴──────────────┴────────────┴───────────┴──────────────┴─────────────┘
# 
# --- Spearman Rank Correlation Matrix ---
# shape: (6, 7)
# ┌──────────────┬──────────────┬──────────────┬────────────┬───────────┬──────────────┬─────────────┐
# │ variable     ┆ grad_rate_15 ┆ admission_ra ┆ pell_share ┆ urm_share ┆ student_facu ┆ retention_r │
# │ ---          ┆ 0pct         ┆ te           ┆ ---        ┆ ---       ┆ lty_ratio    ┆ ate         │
# │ str          ┆ ---          ┆ ---          ┆ f64        ┆ f64       ┆ ---          ┆ ---         │
# │              ┆ f64          ┆ f64          ┆            ┆           ┆ f64          ┆ f64         │
# ╞══════════════╪══════════════╪══════════════╪════════════╪═══════════╪══════════════╪═════════════╡
# │ grad_rate_15 ┆ 1.0          ┆ -0.270243    ┆ -0.667163  ┆ -0.346659 ┆ -0.233481    ┆ 0.715988    │
# │ 0pct         ┆              ┆              ┆            ┆           ┆              ┆             │
# │ admission_ra ┆ -0.270243    ┆ 1.0          ┆ 0.151011   ┆ -0.045056 ┆ 0.193802     ┆ -0.192315   │
# │ te           ┆              ┆              ┆            ┆           ┆              ┆             │
# │ pell_share   ┆ -0.667163    ┆ 0.151011     ┆ 1.0        ┆ 0.55777   ┆ 0.197758     ┆ -0.544693   │
# │ urm_share    ┆ -0.346659    ┆ -0.045056    ┆ 0.55777    ┆ 1.0       ┆ 0.155622     ┆ -0.304175   │
# │ student_facu ┆ -0.233481    ┆ 0.193802     ┆ 0.197758   ┆ 0.155622  ┆ 1.0          ┆ -0.020679   │
# │ lty_ratio    ┆              ┆              ┆            ┆           ┆              ┆             │
# │ retention_ra ┆ 0.715988     ┆ -0.192315    ┆ -0.544693  ┆ -0.304175 ┆ -0.020679    ┆ 1.0         │
# │ te           ┆              ┆              ┆            ┆           ┆              ┆             │
# └──────────────┴──────────────┴──────────────┴────────────┴───────────┴──────────────┴─────────────┘
# 
# ============================================================
# KEY CORRELATIONS — Observable Truth Tests
# ============================================================
# 
# 1. grad_rate_150pct vs admission_rate
#    Pearson r  = -0.3589
#    Spearman r = -0.2702
#    Expected: Strong negative (Observable Truth expects |r| > 0.5)
#    Interpretation: NOT SUPPORTED — magnitude 0.359 below 0.5 threshold
# 
# 2. grad_rate_150pct vs pell_share
#    Pearson r  = -0.6206
#    Spearman r = -0.6672
#    Expected: Negative (Observable Truth expects r < -0.3)
#    Interpretation: SUPPORTED — r = -0.621 is below -0.3 threshold
# 
# 3. grad_rate_150pct vs urm_share
#    Pearson r  = -0.3688
#    Spearman r = -0.3467
#    Expected: Negative
#    Interpretation: SUPPORTED — negative correlation observed
# 
# 4. grad_rate_150pct vs retention_rate (supplementary)
#    Pearson r  = +0.6296
#    Spearman r = +0.7160
#    Expected: Strong positive (retention is a leading indicator of graduation)
# 
# 5. admission_rate vs pell_share (supplementary)
#    Pearson r  = +0.1603
#    Spearman r = +0.1510
#    Expected: Positive (less selective schools tend to serve more Pell students)
# 
# 6. admission_rate vs urm_share (supplementary)
#    Pearson r  = -0.0034
#    Spearman r = -0.0451
#    Expected: Positive (less selective schools tend to have higher URM share)
# 
# ============================================================
# Saving correlation matrices
# ============================================================
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_correlation_matrix.parquet
# Output shape: 12 rows x 8 cols
#   (6 Pearson rows + 6 Spearman rows = 12 total, 8 columns)
# 
# ============================================================
# CP3 VALIDATION (Analysis)
# ============================================================
#   [PASS] Pearson matrix symmetric: True
#   [PASS] Spearman matrix symmetric: True
#   [PASS] Pearson diagonal = 1.0: True
#   [PASS] Spearman diagonal = 1.0: True
#   [PASS] Pearson values in [-1, 1]: True
#   [PASS] Spearman values in [-1, 1]: True
#   [PASS] Sample size: n = 1,518 (after listwise deletion from 2,528)
#   [PASS] Output file exists: True
#   [PASS] Output shape: (12, 8) (expected (12, 8))
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
# 
# Summary:
#   Complete cases: n = 1,518 / 2,528 (60.0%)
#   Method: Listwise deletion, Pearson + Spearman
#   Key finding: grad_rate vs admission_rate Pearson r = -0.3589
#   Output: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_correlation_matrix.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
