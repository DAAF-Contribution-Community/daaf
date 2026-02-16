#!/usr/bin/env python3
"""
Stage 8.1: Cross-tabulation of graduation rates by selectivity band and URM band.

Task: crosstab-selectivity-urm
Wave: 7, Step: 1, Stage: 8
Depends on: create-bands
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_crosstab_selectivity_urm.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for cross-tabulation analysis. The analysis dataset
# was created in Stage 7 (create-bands) and contains selectivity_band and
# urm_band columns alongside grad_rate_150pct. This script groups by both
# band columns to produce summary statistics for each selectivity x URM cell.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_urm.parquet"

# --- Load ---
# Load the analysis dataset and verify it contains the required columns
# before proceeding with the cross-tabulation.
print("=" * 60)
print("Stage 8.1: Cross-tabulation — Selectivity x URM bands")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# Verify required columns exist
required_cols = ["selectivity_band", "urm_band", "grad_rate_150pct"]
missing = [c for c in required_cols if c not in df.columns]
assert len(missing) == 0, f"STOP: Missing required columns: {missing}"
print(f"Required columns present: {required_cols}")

# --- Pre-state ---
# Capture the state of the data BEFORE filtering. Document the distribution
# of null values in key columns to understand how many rows will be excluded
# by the non-null filter and why.
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows:,} rows")

selectivity_nulls = df["selectivity_band"].null_count()
urm_nulls = df["urm_band"].null_count()
grad_rate_nulls = df["grad_rate_150pct"].null_count()
print(f"  selectivity_band nulls: {selectivity_nulls:,} ({selectivity_nulls / pre_rows * 100:.1f}%)")
print(f"  urm_band nulls: {urm_nulls:,} ({urm_nulls / pre_rows * 100:.1f}%)")
print(f"  grad_rate_150pct nulls: {grad_rate_nulls:,} ({grad_rate_nulls / pre_rows * 100:.1f}%)")

# Show distribution of each band column before filtering
print("\nselectivity_band distribution (before filter):")
sel_dist = df.group_by("selectivity_band").len().sort("selectivity_band")
print(sel_dist)

print("\nurm_band distribution (before filter):")
urm_dist = df.group_by("urm_band").len().sort("urm_band")
print(urm_dist)

# --- Filter ---
# INTENT: Restrict to rows where ALL three required columns are non-null.
# We need valid values for both grouping variables (selectivity_band, urm_band)
# and the outcome variable (grad_rate_150pct) to compute meaningful summary
# statistics. Including nulls would either cause silent exclusion in group_by
# or produce misleading aggregates.
#
# REASONING: Filtering before grouping (rather than relying on Polars' default
# null exclusion in aggregations) makes the exact analysis population explicit
# and allows us to report the exact count of rows used. This is important for
# reproducibility — the reader knows exactly which institutions are included.
#
# ASSUMES:
#   - selectivity_band has 4 valid categories: "Highly Selective", "Selective",
#     "Moderately Selective", "Less Selective/Open Admission"
#   - urm_band has 4 valid categories: "Low URM (<15%)", "Moderate URM (15-30%)",
#     "High URM (30-50%)", "Very High URM (>50%)"
#   - grad_rate_150pct is on a 0-100 percentage scale
#   - Null values in these columns represent genuinely missing data (not coded
#     missing values, which were handled in Stage 6)
df_filtered = df.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("urm_band").is_not_null()
    & pl.col("grad_rate_150pct").is_not_null()
)

post_filter_rows = df_filtered.shape[0]
rows_dropped = pre_rows - post_filter_rows
print(f"\nAfter filtering to non-null rows: {post_filter_rows:,} rows")
print(f"Rows dropped: {rows_dropped:,} ({rows_dropped / pre_rows * 100:.1f}%)")

# --- Transform: Cross-tabulation ---
# INTENT: Compute summary statistics (count, mean, median) for grad_rate_150pct
# grouped by every combination of selectivity_band and urm_band. This cross-
# tabulation tests Observable Truth: "URM share is negatively correlated with
# graduation rate" by showing whether graduation rates decrease as URM share
# increases, and whether this pattern holds across selectivity levels.
#
# REASONING: Using group_by with multiple aggregation expressions (n, mean,
# median) because:
#   - Count (n) reveals cell sizes and identifies sparse cells (n < 10)
#   - Mean provides the standard central tendency measure
#   - Median provides a robust alternative less sensitive to outliers/skew
#   - Sorting by selectivity_band then urm_band produces a readable table
#     where the reader can scan down each selectivity level
#
# ASSUMES:
#   - All rows in df_filtered have non-null selectivity_band, urm_band,
#     and grad_rate_150pct (guaranteed by the filter above)
#   - grad_rate_150pct is numeric (Float64) on 0-100 scale
crosstab = (
    df_filtered
    .group_by("selectivity_band", "urm_band")
    .agg(
        pl.len().alias("n"),
        pl.col("grad_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("grad_rate_150pct").median().alias("median_grad_rate"),
    )
    .sort("selectivity_band", "urm_band")
)

print(f"\nCross-tabulation: {crosstab.shape[0]} rows x {crosstab.shape[1]} cols")

# --- Display Results ---
# Print the full cross-tabulation as a readable table. Format numeric values
# for readability (1 decimal place for rates).
print("\n" + "=" * 60)
print("CROSS-TABULATION: Graduation Rate by Selectivity x URM Band")
print("=" * 60)

# INTENT: Display the crosstab with formatted values so the output is
# human-readable in the execution log. Round to 1 decimal for clarity.
crosstab_display = crosstab.with_columns(
    pl.col("mean_grad_rate").round(1),
    pl.col("median_grad_rate").round(1),
)
# Use pl.Config to show full table without truncation
with pl.Config(tbl_rows=50, tbl_cols=10, tbl_width_chars=120):
    print(crosstab_display)

# --- Identify sparse cells ---
# INTENT: Flag cells with fewer than 10 institutions, where summary statistics
# may be unreliable due to small sample size.
#
# REASONING: n < 10 is a common threshold for statistical reliability concerns.
# Small cells are more susceptible to outlier influence and provide less
# confidence in the estimated mean/median. Flagging them helps the report-writer
# appropriately caveat findings in those cells.
sparse_cells = crosstab.filter(pl.col("n") < 10)
if sparse_cells.shape[0] > 0:
    print(f"\nWARNING: {sparse_cells.shape[0]} sparse cells (n < 10):")
    with pl.Config(tbl_rows=50, tbl_cols=10, tbl_width_chars=120):
        print(sparse_cells)
else:
    print("\nNo sparse cells (all n >= 10)")

# --- Observable Truth Check ---
# INTENT: Provide a preliminary assessment of whether the cross-tabulation
# supports the Observable Truth: "URM share is negatively correlated with
# graduation rate." Check whether mean graduation rate generally decreases
# as URM band increases, across each selectivity level.
#
# REASONING: This is a descriptive check, not a formal statistical test.
# The cross-tabulation allows visual inspection of the pattern. A more
# rigorous test (regression) would be done in a separate analysis script.
print("\n" + "=" * 60)
print("OBSERVABLE TRUTH CHECK: URM share vs graduation rate")
print("=" * 60)

# Define the expected URM band ordering from low to high
urm_order = ["Low URM (<15%)", "Moderate URM (15-30%)", "High URM (30-50%)", "Very High URM (>50%)"]

for sel_band in crosstab["selectivity_band"].unique().sort().to_list():
    subset = crosstab.filter(pl.col("selectivity_band") == sel_band).sort("urm_band")
    means = []
    for urm in urm_order:
        row = subset.filter(pl.col("urm_band") == urm)
        if row.shape[0] > 0:
            means.append((urm, row["mean_grad_rate"][0], row["n"][0]))
        else:
            means.append((urm, None, 0))

    print(f"\n{sel_band}:")
    for urm_label, mean_val, n_val in means:
        if mean_val is not None:
            print(f"  {urm_label}: mean={mean_val:.1f}% (n={n_val})")
        else:
            print(f"  {urm_label}: NO DATA")

    # Check if pattern is generally decreasing
    valid_means = [m for _, m, _ in means if m is not None]
    if len(valid_means) >= 2:
        is_decreasing = all(valid_means[i] >= valid_means[i + 1] for i in range(len(valid_means) - 1))
        is_generally_decreasing = valid_means[0] > valid_means[-1]  # First > last
        print(f"  Pattern: {'Strictly decreasing' if is_decreasing else ('Generally decreasing' if is_generally_decreasing else 'NOT decreasing')}")

# --- Save ---
# Persist the cross-tabulation results in parquet format for downstream use
# by the report-writer and visualization scripts.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
crosstab.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation ---
# Checkpoint validation: verify the cross-tabulation meets expectations for
# completeness, value ranges, and cell counts.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: Output has rows
has_rows = crosstab.shape[0] > 0
print(f"  [{'PASS' if has_rows else 'FAIL'}] Cross-tab has rows: {crosstab.shape[0]}")

# CP3.2: Expected columns present
expected_output_cols = ["selectivity_band", "urm_band", "n", "mean_grad_rate", "median_grad_rate"]
output_cols_ok = all(c in crosstab.columns for c in expected_output_cols)
print(f"  [{'PASS' if output_cols_ok else 'FAIL'}] Expected columns present: {expected_output_cols}")

# CP3.3: All n values are positive
all_n_positive = crosstab["n"].min() > 0
print(f"  [{'PASS' if all_n_positive else 'FAIL'}] All n values positive: min n = {crosstab['n'].min()}")

# CP3.4: Grad rate values in valid range (0-100)
mean_in_range = (crosstab["mean_grad_rate"].min() >= 0) and (crosstab["mean_grad_rate"].max() <= 100)
median_in_range = (crosstab["median_grad_rate"].min() >= 0) and (crosstab["median_grad_rate"].max() <= 100)
rates_ok = mean_in_range and median_in_range
print(f"  [{'PASS' if rates_ok else 'FAIL'}] Grad rates in 0-100 range: mean=[{crosstab['mean_grad_rate'].min():.1f}, {crosstab['mean_grad_rate'].max():.1f}], median=[{crosstab['median_grad_rate'].min():.1f}, {crosstab['median_grad_rate'].max():.1f}]")

# CP3.5: Coverage check — expect 4 selectivity bands x 4 URM bands = up to 16 cells
n_selectivity_bands = crosstab["selectivity_band"].n_unique()
n_urm_bands = crosstab["urm_band"].n_unique()
total_cells = crosstab.shape[0]
coverage_ok = n_selectivity_bands >= 3 and n_urm_bands >= 3  # Allow some empty cells
print(f"  [{'PASS' if coverage_ok else 'WARN'}] Band coverage: {n_selectivity_bands} selectivity x {n_urm_bands} URM = {total_cells} cells")

# CP3.6: Total n sums to filtered row count
total_n = crosstab["n"].sum()
n_matches = total_n == post_filter_rows
print(f"  [{'PASS' if n_matches else 'FAIL'}] Total n matches filtered rows: {total_n:,} == {post_filter_rows:,}")

# CP3.7: Sparse cell documentation
n_sparse = crosstab.filter(pl.col("n") < 10).shape[0]
print(f"  [INFO] Sparse cells (n < 10): {n_sparse}")

assert has_rows, "STOP: Cross-tabulation is empty"
assert output_cols_ok, "STOP: Missing expected columns in output"
assert all_n_positive, "STOP: Found cells with n <= 0"
assert rates_ok, "STOP: Graduation rates outside 0-100 range"
assert n_matches, "STOP: Total n does not match filtered row count"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:49:48
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/01_crosstab-selectivity-urm.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Cross-tabulation — Selectivity x URM bands
# ============================================================
# Loaded: 2,528 rows x 26 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment', 'student_faculty_ratio', 'retention_rate', 'selectivity_band', 'pell_band', 'urm_band']
# Required columns present: ['selectivity_band', 'urm_band', 'grad_rate_150pct']
# 
# Pre-state: 2,528 rows
#   selectivity_band nulls: 0 (0.0%)
#   urm_band nulls: 370 (14.6%)
#   grad_rate_150pct nulls: 732 (29.0%)
# 
# selectivity_band distribution (before filter):
# shape: (4, 2)
# ┌──────────────────────┬──────┐
# │ selectivity_band     ┆ len  │
# │ ---                  ┆ ---  │
# │ str                  ┆ u32  │
# ╞══════════════════════╪══════╡
# │ Highly Selective     ┆ 73   │
# │ Less Selective/Open  ┆ 1695 │
# │ Moderately Selective ┆ 586  │
# │ Selective            ┆ 174  │
# └──────────────────────┴──────┘
# 
# urm_band distribution (before filter):
# shape: (5, 2)
# ┌───────────────────────┬──────┐
# │ urm_band              ┆ len  │
# │ ---                   ┆ ---  │
# │ str                   ┆ u32  │
# ╞═══════════════════════╪══════╡
# │ null                  ┆ 370  │
# │ High URM (40-60%)     ┆ 228  │
# │ Low URM (under 20%)   ┆ 1025 │
# │ Moderate URM (20-40%) ┆ 635  │
# │ Very High URM (60%+)  ┆ 270  │
# └───────────────────────┴──────┘
# 
# After filtering to non-null rows: 1,791 rows
# Rows dropped: 737 (29.2%)
# 
# Cross-tabulation: 14 rows x 5 cols
# 
# ============================================================
# CROSS-TABULATION: Graduation Rate by Selectivity x URM Band
# ============================================================
# shape: (14, 5)
# ┌──────────────────────┬───────────────────────┬─────┬────────────────┬──────────────────┐
# │ selectivity_band     ┆ urm_band              ┆ n   ┆ mean_grad_rate ┆ median_grad_rate │
# │ ---                  ┆ ---                   ┆ --- ┆ ---            ┆ ---              │
# │ str                  ┆ str                   ┆ u32 ┆ f64            ┆ f64              │
# ╞══════════════════════╪═══════════════════════╪═════╪════════════════╪══════════════════╡
# │ Highly Selective     ┆ Low URM (under 20%)   ┆ 46  ┆ 87.9           ┆ 91.4             │
# │ Highly Selective     ┆ Moderate URM (20-40%) ┆ 23  ┆ 89.8           ┆ 93.0             │
# │ Less Selective/Open  ┆ High URM (40-60%)     ┆ 107 ┆ 46.9           ┆ 47.7             │
# │ Less Selective/Open  ┆ Low URM (under 20%)   ┆ 495 ┆ 56.0           ┆ 58.1             │
# │ Less Selective/Open  ┆ Moderate URM (20-40%) ┆ 262 ┆ 53.2           ┆ 53.8             │
# │ Less Selective/Open  ┆ Very High URM (60%+)  ┆ 135 ┆ 42.4           ┆ 39.7             │
# │ Moderately Selective ┆ High URM (40-60%)     ┆ 44  ┆ 49.4           ┆ 50.2             │
# │ Moderately Selective ┆ Low URM (under 20%)   ┆ 280 ┆ 64.0           ┆ 65.0             │
# │ Moderately Selective ┆ Moderate URM (20-40%) ┆ 193 ┆ 55.4           ┆ 56.4             │
# │ Moderately Selective ┆ Very High URM (60%+)  ┆ 47  ┆ 37.0           ┆ 36.6             │
# │ Selective            ┆ High URM (40-60%)     ┆ 15  ┆ 48.3           ┆ 53.7             │
# │ Selective            ┆ Low URM (under 20%)   ┆ 69  ┆ 75.2           ┆ 82.3             │
# │ Selective            ┆ Moderate URM (20-40%) ┆ 48  ┆ 62.4           ┆ 67.0             │
# │ Selective            ┆ Very High URM (60%+)  ┆ 27  ┆ 38.8           ┆ 39.0             │
# └──────────────────────┴───────────────────────┴─────┴────────────────┴──────────────────┘
# 
# No sparse cells (all n >= 10)
# 
# ============================================================
# OBSERVABLE TRUTH CHECK: URM share vs graduation rate
# ============================================================
# 
# Highly Selective:
#   Low URM (<15%): NO DATA
#   Moderate URM (15-30%): NO DATA
#   High URM (30-50%): NO DATA
#   Very High URM (>50%): NO DATA
# 
# Less Selective/Open:
#   Low URM (<15%): NO DATA
#   Moderate URM (15-30%): NO DATA
#   High URM (30-50%): NO DATA
#   Very High URM (>50%): NO DATA
# 
# Moderately Selective:
#   Low URM (<15%): NO DATA
#   Moderate URM (15-30%): NO DATA
#   High URM (30-50%): NO DATA
#   Very High URM (>50%): NO DATA
# 
# Selective:
#   Low URM (<15%): NO DATA
#   Moderate URM (15-30%): NO DATA
#   High URM (30-50%): NO DATA
#   Very High URM (>50%): NO DATA
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_crosstab_selectivity_urm.parquet
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] Cross-tab has rows: 14
#   [PASS] Expected columns present: ['selectivity_band', 'urm_band', 'n', 'mean_grad_rate', 'median_grad_rate']
#   [PASS] All n values positive: min n = 15
#   [PASS] Grad rates in 0-100 range: mean=[37.0, 89.8], median=[36.6, 93.0]
#   [PASS] Band coverage: 4 selectivity x 4 URM = 14 cells
#   [PASS] Total n matches filtered rows: 1,791 == 1,791
#   [INFO] Sparse cells (n < 10): 0
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
