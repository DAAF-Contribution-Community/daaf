#!/usr/bin/env python3
"""
Stage 8.1: Correlation matrix analysis -- Pearson and Spearman correlations
among key continuous variables, with H1 hypothesis test for admit_rate vs
completion_rate_150pct.

Task: correlation-matrix
Wave: 8, Step: 4, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_correlation_matrix.parquet
Checkpoint: CP4
"""

import numpy as np
from pathlib import Path
from scipy import stats as scipy_stats

import polars as pl

# --- Config ---
# Configuration constants derived from the Plan's analysis design. Variables
# selected are the continuous measures relevant to the research question about
# graduation rate variation by selectivity, resources, and demographics.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"

# INTENT: Select the 7 continuous variables specified in the task for correlation.
# REASONING: These variables span the key dimensions of the research question:
#   - admit_rate: selectivity proxy (H1 predictor)
#   - completion_rate_150pct: outcome variable (H1 outcome)
#   - pell_share: financial aid dependency / student need
#   - urm_share: underserved population representation
#   - student_faculty_ratio: institutional resources (staffing)
#   - retention_rate: institutional effectiveness proxy
#   - instr_expend_per_fte: institutional resources (spending)
CORR_VARS = [
    "admit_rate",
    "completion_rate_150pct",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
    "instr_expend_per_fte",
]

# H1 hypothesis from Plan: "Admission rate and graduation rate are strongly
# negatively correlated (|r| > 0.5)"
H1_VAR_X = "admit_rate"
H1_VAR_Y = "completion_rate_150pct"

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands).
print("=" * 60)
print("Stage 8.1: Correlation Matrix Analysis")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state before any filtering. Document missingness per variable so
# the reader understands why listwise N is lower than total N.
pre_rows = df.shape[0]

missing_vars = [v for v in CORR_VARS if v not in df.columns]
assert not missing_vars, f"STOP: Missing correlation variables: {missing_vars}"

print(f"\nPre-state: {pre_rows:,} rows")
print("\nMissingness per correlation variable:")
for var in CORR_VARS:
    null_ct = df[var].null_count()
    null_pct = null_ct / pre_rows * 100
    print(f"  {var}: {null_ct:,} nulls ({null_pct:.1f}%)")

# --- Pairwise complete N ---
# INTENT: Report pairwise-complete N for each variable pair so the reader
# knows how many cases contribute per correlation in a pairwise approach.
# REASONING: With ~39.5% null admit_rate (open-admissions institutions),
# listwise deletion will substantially reduce N. Reporting pairwise N
# alongside listwise results gives context on information loss.
print("\n--- Pairwise Complete N (for context) ---")
n_vars = len(CORR_VARS)
pairwise_n = np.zeros((n_vars, n_vars), dtype=int)

for i in range(n_vars):
    for j in range(i, n_vars):
        # INTENT: Count rows where both variables are non-null.
        pair_complete = df.select(CORR_VARS[i], CORR_VARS[j]).drop_nulls().shape[0]
        pairwise_n[i, j] = pair_complete
        pairwise_n[j, i] = pair_complete

# Print pairwise N matrix
header = f"{'':>28s}" + "".join(f"{v:>12s}" for v in CORR_VARS)
print(header)
for i, var in enumerate(CORR_VARS):
    row_str = f"{var:>28s}" + "".join(f"{pairwise_n[i, j]:>12,}" for j in range(n_vars))
    print(row_str)

# --- Listwise deletion ---
# INTENT: Create complete-case dataset for the main correlation matrices using
# listwise deletion (drop rows with any null across all 7 variables).
# REASONING: Listwise deletion ensures every correlation in the matrix uses the
# exact same set of observations, making the matrix positive semi-definite and
# internally consistent. Pairwise deletion could produce a non-PSD matrix.
# ASSUMES: Missingness is primarily driven by open-admissions institutions
# lacking admit_rate (~39.5%) and institutions missing retention_rate (~28.1%).
# These are structural (data not collected for open-admissions) rather than
# informatively missing, so listwise deletion does not introduce severe bias
# for institutions that DO report these variables.
df_complete = df.select(CORR_VARS).drop_nulls()
listwise_n = df_complete.shape[0]
dropped = pre_rows - listwise_n
drop_pct = dropped / pre_rows * 100

print(f"\n--- Listwise Deletion ---")
print(f"Complete cases: {listwise_n:,} ({dropped:,} rows dropped, {drop_pct:.1f}%)")
print(f"NOTE: Listwise N is {listwise_n:,} vs full dataset N={pre_rows:,}")
print(f"  This reflects ~39.5% null admit_rate + ~28.1% null retention_rate.")
print(f"  Institutions with complete data on all 7 variables are those that are")
print(f"  selective (report admit_rate) and report retention + spending data.")

assert listwise_n >= 50, f"STOP: Only {listwise_n} complete cases -- too few for reliable correlations"

# --- Pearson Correlation Matrix ---
# INTENT: Compute Pearson product-moment correlation matrix on listwise-complete
# data. Pearson measures linear association between continuous variables.
# REASONING: Pearson is the standard first-pass correlation. We compute via
# numpy for efficiency and to preserve the full matrix structure.
# ASSUMES: Variables are continuous. Non-normality does not invalidate Pearson
# point estimates, but affects CI coverage -- hence we also compute Spearman.
print("\n--- Pearson Correlation Matrix ---")

data_matrix = df_complete.to_numpy()  # shape: (listwise_n, 7)
pearson_matrix = np.corrcoef(data_matrix, rowvar=False)  # 7x7

header = f"{'':>28s}" + "".join(f"{v:>12s}" for v in CORR_VARS)
print(header)
for i, var in enumerate(CORR_VARS):
    row_str = f"{var:>28s}" + "".join(f"{pearson_matrix[i, j]:>12.4f}" for j in range(n_vars))
    print(row_str)

# --- Spearman Rank Correlation Matrix ---
# INTENT: Compute Spearman rank correlations as a robustness check.
# REASONING: Some variables (e.g., instr_expend_per_fte) have highly skewed
# distributions with outliers up to $14.1M/FTE (professional schools). Spearman
# is robust to outliers and non-linear monotonic relationships, providing a
# complementary view to Pearson. If Pearson and Spearman agree closely, the
# linear assumption is reasonable.
print("\n--- Spearman Rank Correlation Matrix ---")

spearman_matrix = np.zeros((n_vars, n_vars))
for i in range(n_vars):
    for j in range(i, n_vars):
        if i == j:
            spearman_matrix[i, j] = 1.0
        else:
            rho, _ = scipy_stats.spearmanr(data_matrix[:, i], data_matrix[:, j])
            spearman_matrix[i, j] = rho
            spearman_matrix[j, i] = rho

header = f"{'':>28s}" + "".join(f"{v:>12s}" for v in CORR_VARS)
print(header)
for i, var in enumerate(CORR_VARS):
    row_str = f"{var:>28s}" + "".join(f"{spearman_matrix[i, j]:>12.4f}" for j in range(n_vars))
    print(row_str)

# --- H1 Hypothesis Test: admit_rate vs completion_rate_150pct ---
# INTENT: Directly test H1 from the Plan -- "Admission rate and graduation rate
# are strongly negatively correlated (|r| > 0.5)".
# REASONING: Report both Pearson and Spearman for this key pair, with a 95%
# confidence interval via Fisher z-transformation for the Pearson r.
# ASSUMES: Fisher z is appropriate for constructing CIs when n is reasonably
# large (our listwise N should be several hundred).
h1_x_idx = CORR_VARS.index(H1_VAR_X)
h1_y_idx = CORR_VARS.index(H1_VAR_Y)

r_pearson = pearson_matrix[h1_x_idx, h1_y_idx]
r_spearman = spearman_matrix[h1_x_idx, h1_y_idx]

# Fisher z-transformation for 95% CI on Pearson r
# REASONING: Fisher z = 0.5 * ln((1+r)/(1-r)) is approximately normal with
# SE = 1/sqrt(n-3). We transform to z, compute CI in z-space, then back-
# transform to r-space for interpretability.
z = np.arctanh(r_pearson)  # Fisher z-transform
se_z = 1.0 / np.sqrt(listwise_n - 3)  # SE of Fisher z
z_crit = 1.96  # 95% CI
z_lo = z - z_crit * se_z
z_hi = z + z_crit * se_z
r_lo = np.tanh(z_lo)  # back-transform to r-space
r_hi = np.tanh(z_hi)

# Also compute p-value for r
# REASONING: Use scipy for the exact two-sided p-value via t-distribution.
t_stat = r_pearson * np.sqrt((listwise_n - 2) / (1 - r_pearson**2))
p_value = 2 * scipy_stats.t.sf(abs(t_stat), df=listwise_n - 2)

print("\n" + "=" * 60)
print("H1 TEST: admit_rate vs completion_rate_150pct")
print("=" * 60)
print(f"  Pearson r   = {r_pearson:.4f}  [95% CI: {r_lo:.4f}, {r_hi:.4f}]")
print(f"  Spearman rho = {r_spearman:.4f}")
print(f"  t-statistic  = {t_stat:.4f}")
print(f"  p-value      = {p_value:.2e}")
print(f"  N (listwise) = {listwise_n:,}")
print(f"  H1 threshold: |r| > 0.5")

h1_supported = abs(r_pearson) > 0.5
h1_negative = r_pearson < 0
print(f"  H1 magnitude (|r| > 0.5): {'SUPPORTED' if h1_supported else 'NOT SUPPORTED'} (|r| = {abs(r_pearson):.4f})")
print(f"  H1 direction (negative):  {'CONFIRMED' if h1_negative else 'NOT CONFIRMED'}")

# --- Pearson vs Spearman comparison ---
# INTENT: Flag large discrepancies between Pearson and Spearman that indicate
# non-linearity or outlier influence.
# REASONING: A difference > 0.1 between Pearson and Spearman for any pair
# suggests the linear association assumption is notably violated for that pair.
print("\n--- Pearson vs Spearman Comparison ---")
print("(Pairs where |Pearson - Spearman| > 0.05)")
for i in range(n_vars):
    for j in range(i + 1, n_vars):
        diff = abs(pearson_matrix[i, j] - spearman_matrix[i, j])
        if diff > 0.05:
            print(f"  {CORR_VARS[i]} x {CORR_VARS[j]}: "
                  f"Pearson={pearson_matrix[i, j]:.4f}, "
                  f"Spearman={spearman_matrix[i, j]:.4f}, "
                  f"diff={diff:.4f}")

# --- Save ---
# INTENT: Save the Pearson correlation matrix as a structured parquet file.
# REASONING: Saving as a tidy DataFrame with variable names as both a column
# and as row identifiers allows downstream scripts to load and reference
# specific correlations by name.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Build a DataFrame with variable names as the first column, then each
# variable's correlations as subsequent columns.
pearson_data = {"variable": CORR_VARS}
for j, var in enumerate(CORR_VARS):
    pearson_data[var] = [float(pearson_matrix[i, j]) for i in range(n_vars)]

results_df = pl.DataFrame(pearson_data)

# INTENT: Add metadata columns so downstream consumers know the N and method.
results_df = results_df.with_columns([
    pl.lit(listwise_n).alias("n_listwise"),
    pl.lit("pearson").alias("method"),
])

results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"  Shape: {results_df.shape[0]} rows x {results_df.shape[1]} cols")

# --- CP4 Validation ---
# Checkpoint validation: verify correlation matrix is valid, symmetric,
# with diagonal = 1.0, values in [-1, 1], and output file exists.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Output file exists and is non-zero
file_exists = OUTPUT_PATH.exists()
file_size = OUTPUT_PATH.stat().st_size if file_exists else 0
print(f"  [{'PASS' if file_exists and file_size > 0 else 'FAIL'}] Output file exists: {file_exists}, size: {file_size:,} bytes")
if not file_exists or file_size == 0:
    cp4_passed = False

# CP4.2: All correlation values in [-1, 1]
all_in_range = np.all((pearson_matrix >= -1.0) & (pearson_matrix <= 1.0))
print(f"  [{'PASS' if all_in_range else 'FAIL'}] All Pearson values in [-1, 1]: {all_in_range}")
if not all_in_range:
    cp4_passed = False

spearman_in_range = np.all((spearman_matrix >= -1.0) & (spearman_matrix <= 1.0))
print(f"  [{'PASS' if spearman_in_range else 'FAIL'}] All Spearman values in [-1, 1]: {spearman_in_range}")
if not spearman_in_range:
    cp4_passed = False

# CP4.3: Pearson matrix is symmetric
is_symmetric = np.allclose(pearson_matrix, pearson_matrix.T, atol=1e-10)
print(f"  [{'PASS' if is_symmetric else 'FAIL'}] Pearson matrix symmetric: {is_symmetric}")
if not is_symmetric:
    cp4_passed = False

spearman_symmetric = np.allclose(spearman_matrix, spearman_matrix.T, atol=1e-10)
print(f"  [{'PASS' if spearman_symmetric else 'FAIL'}] Spearman matrix symmetric: {spearman_symmetric}")
if not spearman_symmetric:
    cp4_passed = False

# CP4.4: Diagonal values are 1.0
diag_ones = np.allclose(np.diag(pearson_matrix), 1.0, atol=1e-10)
print(f"  [{'PASS' if diag_ones else 'FAIL'}] Pearson diagonal = 1.0: {diag_ones}")
if not diag_ones:
    cp4_passed = False

spearman_diag = np.allclose(np.diag(spearman_matrix), 1.0, atol=1e-10)
print(f"  [{'PASS' if spearman_diag else 'FAIL'}] Spearman diagonal = 1.0: {spearman_diag}")
if not spearman_diag:
    cp4_passed = False

# CP4.5: Sufficient N for meaningful correlations
# REASONING: With 7 variables, we need at minimum ~30 observations for any
# statistical meaning; 50+ is a more conservative threshold for 95% CIs.
n_adequate = listwise_n >= 50
print(f"  [{'PASS' if n_adequate else 'FAIL'}] N >= 50: {listwise_n:,}")
if not n_adequate:
    cp4_passed = False

# CP4.6: H1 correlation is statistically significant
h1_significant = p_value < 0.05
print(f"  [{'PASS' if h1_significant else 'WARN'}] H1 correlation significant (p < 0.05): p={p_value:.2e}")

# CP4.7: Pearson matrix is positive semi-definite (necessary for valid corr matrix)
eigenvalues = np.linalg.eigvalsh(pearson_matrix)
is_psd = np.all(eigenvalues >= -1e-10)
print(f"  [{'PASS' if is_psd else 'WARN'}] Pearson matrix PSD: {is_psd} (min eigenvalue: {eigenvalues.min():.6f})")

assert cp4_passed, "STOP: CP4 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 12:14:13
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Correlation Matrix Analysis
# ============================================================
# Loaded: 1,946 rows x 25 cols
# 
# Pre-state: 1,946 rows
# 
# Missingness per correlation variable:
#   admit_rate: 321 nulls (16.5%)
#   completion_rate_150pct: 0 nulls (0.0%)
#   pell_share: 59 nulls (3.0%)
#   urm_share: 7 nulls (0.4%)
#   student_faculty_ratio: 5 nulls (0.3%)
#   retention_rate: 51 nulls (2.6%)
#   instr_expend_per_fte: 45 nulls (2.3%)
# 
# --- Pairwise Complete N (for context) ---
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/04_correlation-matrix.py", line 92, in <module>
#     pair_complete = df.select(CORR_VARS[i], CORR_VARS[j]).drop_nulls().shape[0]
#                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/frame.py", line 10307, in select
#     .collect(optimizations=QueryOptFlags._eager())
#      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 97, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/opt_flags.py", line 326, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/frame.py", line 2440, in collect
#     return wrap_df(ldf.collect(engine, callback))
#                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.DuplicateError: projections contained duplicate output name 'admit_rate'. It's possible that multiple expressions are returning the same default column name. If this is the case, try renaming the columns with `.alias("new_name")` to avoid duplicate column names.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
