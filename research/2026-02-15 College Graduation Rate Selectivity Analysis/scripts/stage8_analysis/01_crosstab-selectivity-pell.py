#!/usr/bin/env python3
"""
Stage 8.1: Cross-tabulation of graduation rates by selectivity band and Pell band.

Task: crosstab-selectivity-pell
Wave: 7, Step: 1, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_crosstab_selectivity_pell.parquet
Checkpoint: CP3 (analysis validation)
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's analysis specification.
# This script computes a cross-tabulation of mean/median graduation rates
# grouped by selectivity_band x pell_band to test the Observable Truth:
# "Within selectivity bands, Pell share still explains meaningful graduation
# rate variation."
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_pell.parquet"

# --- Load ---
# Load the analysis dataset produced by Stage 7 (band creation). Verify shape
# and confirm key columns exist before proceeding.
print("=" * 60)
print("Stage 8.1: Cross-tabulation — Selectivity x Pell x Grad Rate")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# Verify required columns
REQUIRED_COLS = ["selectivity_band", "pell_band", "grad_rate_150pct"]
missing = [c for c in REQUIRED_COLS if c not in df.columns]
assert len(missing) == 0, f"STOP: Missing required columns: {missing}"
print(f"Required columns present: {REQUIRED_COLS}")

# --- Pre-state ---
# Capture the current state BEFORE filtering. Document how many rows have
# non-null values in each of the three key columns, and how many rows remain
# after requiring all three to be non-null. This establishes the effective
# analysis sample size.
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows:,} total rows")

selectivity_non_null = df.filter(pl.col("selectivity_band").is_not_null()).shape[0]
pell_non_null = df.filter(pl.col("pell_band").is_not_null()).shape[0]
grad_rate_non_null = df.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]

print(f"  selectivity_band non-null: {selectivity_non_null:,} ({selectivity_non_null/pre_rows*100:.1f}%)")
print(f"  pell_band non-null: {pell_non_null:,} ({pell_non_null/pre_rows*100:.1f}%)")
print(f"  grad_rate_150pct non-null: {grad_rate_non_null:,} ({grad_rate_non_null/pre_rows*100:.1f}%)")

# --- Filter ---
# INTENT: Restrict to rows where ALL three key columns are non-null. This is
# the effective analysis sample for the cross-tabulation. Rows missing any of
# these cannot contribute to a selectivity x Pell breakdown of grad rates.
#
# REASONING: Filtering rather than imputing because:
#   - selectivity_band and pell_band are categorical grouping variables —
#     imputation would create artificial groups
#   - grad_rate_150pct is the outcome — imputing it would bias the analysis
#   - The Plan acknowledges ~29% null grad rates and ~20% null pell_band
#     as acceptable missingness given sufficient remaining sample
#
# ASSUMES:
#   - selectivity_band has 4 levels: Highly Selective, Selective,
#     Moderately Selective, Less Selective/Open Admission
#   - pell_band has 4 levels: Low Pell, Moderate Pell, High Pell, Very High Pell
#   - grad_rate_150pct is on 0-100 percentage scale
df_filtered = df.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("pell_band").is_not_null()
    & pl.col("grad_rate_150pct").is_not_null()
)

post_filter_rows = df_filtered.shape[0]
rows_dropped = pre_rows - post_filter_rows
print(f"\nAfter filtering to all-non-null: {post_filter_rows:,} rows")
print(f"Rows dropped: {rows_dropped:,} ({rows_dropped/pre_rows*100:.1f}%)")

assert post_filter_rows > 0, "STOP: No rows remain after filtering"

# --- Profile filtered data ---
# Quick profile of the filtered dataset to confirm distributions before grouping.
print(f"\nFiltered data profile:")
print(f"  selectivity_band distribution:")
sel_counts = df_filtered.group_by("selectivity_band").len().sort("len", descending=True)
for row in sel_counts.iter_rows(named=True):
    print(f"    {row['selectivity_band']}: {row['len']:,}")

print(f"  pell_band distribution:")
pell_counts = df_filtered.group_by("pell_band").len().sort("len", descending=True)
for row in pell_counts.iter_rows(named=True):
    print(f"    {row['pell_band']}: {row['len']:,}")

print(f"  grad_rate_150pct summary:")
grad_stats = df_filtered.select(
    pl.col("grad_rate_150pct").mean().alias("mean"),
    pl.col("grad_rate_150pct").median().alias("median"),
    pl.col("grad_rate_150pct").min().alias("min"),
    pl.col("grad_rate_150pct").max().alias("max"),
    pl.col("grad_rate_150pct").std().alias("std"),
)
for row in grad_stats.iter_rows(named=True):
    print(f"    Mean: {row['mean']:.1f}, Median: {row['median']:.1f}, "
          f"Min: {row['min']:.1f}, Max: {row['max']:.1f}, Std: {row['std']:.1f}")

# --- Cross-tabulation ---
# INTENT: Group by selectivity_band x pell_band and compute summary statistics
# for grad_rate_150pct (n, mean, median) to test whether Pell share explains
# meaningful graduation rate variation within selectivity bands.
#
# REASONING: Mean and median together help detect skewness within cells.
# If mean differs substantially from median, the distribution within that cell
# is skewed (common for grad rates near 0 or 100). n is reported so the user
# can assess statistical reliability of each cell (small n = less reliable).
#
# ASSUMES:
#   - grad_rate_150pct is on 0-100 scale (verified above)
#   - Each selectivity x pell combination should have at least some observations,
#     though some cells (e.g., Highly Selective x Very High Pell) may be sparse
crosstab = (
    df_filtered
    .group_by("selectivity_band", "pell_band")
    .agg(
        pl.len().alias("n"),
        pl.col("grad_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("grad_rate_150pct").median().alias("median_grad_rate"),
    )
    .sort("selectivity_band", "pell_band")
)

print(f"\n{'=' * 80}")
print("CROSS-TABULATION: Graduation Rate by Selectivity Band x Pell Band")
print(f"{'=' * 80}")

# Print as a readable table
print(f"\n{'Selectivity Band':<35} {'Pell Band':<20} {'N':>6} {'Mean Grad Rate':>15} {'Median Grad Rate':>17}")
print("-" * 95)

for row in crosstab.iter_rows(named=True):
    sparse_flag = " *" if row["n"] < 10 else ""
    print(f"{row['selectivity_band']:<35} {row['pell_band']:<20} {row['n']:>6} "
          f"{row['mean_grad_rate']:>14.1f}% {row['median_grad_rate']:>16.1f}%{sparse_flag}")

print("\n* = sparse cell (n < 10), interpret with caution")

# --- Interpretation ---
# INTENT: Assess whether, WITHIN each selectivity band, graduation rates vary
# meaningfully by Pell share. This directly tests the Observable Truth.
#
# REASONING: We compute the within-band spread (max mean - min mean across Pell
# bands) for each selectivity band. A spread of >5 percentage points is
# considered "meaningful" variation, following common education research thresholds.
print(f"\n{'=' * 80}")
print("INTERPRETATION: Within-Band Variation by Pell Share")
print(f"{'=' * 80}")

# INTENT: For each selectivity band, compute the range of mean grad rates across
# Pell bands to quantify the magnitude of Pell-related variation.
selectivity_bands = crosstab["selectivity_band"].unique().sort().to_list()

for band in selectivity_bands:
    band_data = crosstab.filter(pl.col("selectivity_band") == band)
    mean_rates = band_data["mean_grad_rate"]
    n_values = band_data["n"]

    spread = mean_rates.max() - mean_rates.min()
    total_n = n_values.sum()
    min_cell_n = n_values.min()

    print(f"\n  {band}:")
    print(f"    Pell bands represented: {band_data.shape[0]}")
    print(f"    Total institutions: {total_n}")
    print(f"    Smallest cell: n={min_cell_n}")
    print(f"    Mean grad rate range: {mean_rates.min():.1f}% to {mean_rates.max():.1f}%")
    print(f"    Spread (max - min): {spread:.1f} percentage points")

    if spread > 5:
        print(f"    --> MEANINGFUL variation ({spread:.1f} pp > 5 pp threshold)")
    else:
        print(f"    --> MODEST variation ({spread:.1f} pp <= 5 pp threshold)")

    if min_cell_n < 10:
        print(f"    --> CAUTION: At least one cell has n < 10; results may not be reliable")

# --- Overall assessment ---
all_spreads = []
for band in selectivity_bands:
    band_data = crosstab.filter(pl.col("selectivity_band") == band)
    spread = band_data["mean_grad_rate"].max() - band_data["mean_grad_rate"].min()
    all_spreads.append({"band": band, "spread": spread})

bands_with_meaningful = [s for s in all_spreads if s["spread"] > 5]

print(f"\n{'=' * 80}")
print("OVERALL ASSESSMENT")
print(f"{'=' * 80}")
print(f"Selectivity bands with meaningful Pell variation (>5 pp): "
      f"{len(bands_with_meaningful)} of {len(selectivity_bands)}")

for s in all_spreads:
    label = "MEANINGFUL" if s["spread"] > 5 else "MODEST"
    print(f"  {s['band']}: {s['spread']:.1f} pp [{label}]")

if len(bands_with_meaningful) >= len(selectivity_bands) // 2 + 1:
    print(f"\nOBSERVABLE TRUTH SUPPORTED: In a majority of selectivity bands, "
          f"Pell share explains meaningful graduation rate variation.")
else:
    print(f"\nOBSERVABLE TRUTH PARTIALLY SUPPORTED: Only {len(bands_with_meaningful)} of "
          f"{len(selectivity_bands)} bands show meaningful Pell variation.")

# --- Save ---
# Persist the cross-tabulation results in parquet format for downstream use
# (visualization, report generation).
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
crosstab.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation ---
# Checkpoint validation: verify the cross-tabulation output meets expectations.
print(f"\n{'=' * 60}")
print("CHECKPOINT VALIDATION")
print(f"{'=' * 60}")

# CP3.1: Output has rows
has_rows = crosstab.shape[0] > 0
print(f"  [{'PASS' if has_rows else 'FAIL'}] Output has rows: {crosstab.shape[0]}")

# CP3.2: All selectivity bands represented
sel_bands_in_output = set(crosstab["selectivity_band"].unique().to_list())
expected_sel_bands = {"Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open Admission"}
sel_coverage = sel_bands_in_output & expected_sel_bands
sel_ok = len(sel_coverage) >= 3  # Allow for possible missing combinations
print(f"  [{'PASS' if sel_ok else 'WARN'}] Selectivity bands covered: {len(sel_coverage)} of {len(expected_sel_bands)}")
if sel_bands_in_output - expected_sel_bands:
    print(f"    Unexpected bands: {sel_bands_in_output - expected_sel_bands}")
if expected_sel_bands - sel_bands_in_output:
    print(f"    Missing bands: {expected_sel_bands - sel_bands_in_output}")

# CP3.3: All n values positive
all_n_positive = (crosstab["n"] > 0).all()
print(f"  [{'PASS' if all_n_positive else 'FAIL'}] All n values positive: {all_n_positive}")

# CP3.4: Grad rates in valid range (0-100)
mean_in_range = (crosstab["mean_grad_rate"] >= 0).all() and (crosstab["mean_grad_rate"] <= 100).all()
median_in_range = (crosstab["median_grad_rate"] >= 0).all() and (crosstab["median_grad_rate"] <= 100).all()
range_ok = mean_in_range and median_in_range
print(f"  [{'PASS' if range_ok else 'FAIL'}] Grad rates in 0-100 range: mean={mean_in_range}, median={median_in_range}")

# CP3.5: Flag sparse cells (n < 10)
sparse_cells = crosstab.filter(pl.col("n") < 10)
if sparse_cells.shape[0] > 0:
    print(f"  [WARN] Sparse cells (n < 10): {sparse_cells.shape[0]} cells")
    for row in sparse_cells.iter_rows(named=True):
        print(f"    {row['selectivity_band']} x {row['pell_band']}: n={row['n']}")
else:
    print(f"  [PASS] No sparse cells (all n >= 10)")

# CP3.6: Total n sums to filtered dataset size
total_n = crosstab["n"].sum()
n_matches = total_n == post_filter_rows
print(f"  [{'PASS' if n_matches else 'FAIL'}] Total n matches filtered rows: {total_n:,} vs {post_filter_rows:,}")

assert has_rows, "STOP: Empty cross-tabulation output"
assert all_n_positive, "STOP: Zero or negative n values found"
assert range_ok, "STOP: Grad rates outside 0-100 range"

print(f"\n{'=' * 60}")
print("CP3 VALIDATION: PASSED")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:49:44
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/01_crosstab-selectivity-pell.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Cross-tabulation — Selectivity x Pell x Grad Rate
# ============================================================
# Loaded: 2,528 rows x 26 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment', 'student_faculty_ratio', 'retention_rate', 'selectivity_band', 'pell_band', 'urm_band']
# Required columns present: ['selectivity_band', 'pell_band', 'grad_rate_150pct']
# 
# Pre-state: 2,528 total rows
#   selectivity_band non-null: 2,528 (100.0%)
#   pell_band non-null: 2,010 (79.5%)
#   grad_rate_150pct non-null: 1,796 (71.0%)
# 
# After filtering to all-non-null: 1,704 rows
# Rows dropped: 824 (32.6%)
# 
# Filtered data profile:
#   selectivity_band distribution:
#     Less Selective/Open: 927
#     Moderately Selective: 556
#     Selective: 156
#     Highly Selective: 65
#   pell_band distribution:
#     Moderate Pell (20-40%): 760
#     High Pell (40-60%): 488
#     Very High Pell (60%+): 234
#     Low Pell (under 20%): 222
#   grad_rate_150pct summary:
#     Mean: 56.8, Median: 57.0, Min: 3.8, Max: 100.0, Std: 19.4
# 
# ================================================================================
# CROSS-TABULATION: Graduation Rate by Selectivity Band x Pell Band
# ================================================================================
# 
# Selectivity Band                    Pell Band                 N  Mean Grad Rate  Median Grad Rate
# -----------------------------------------------------------------------------------------------
# Highly Selective                    High Pell (40-60%)        3           53.4%             62.5% *
# Highly Selective                    Low Pell (under 20%)     44           91.8%             92.8%
# Highly Selective                    Moderate Pell (20-40%)     17           89.9%             92.5%
# Highly Selective                    Very High Pell (60%+)      1           29.3%             29.3% *
# Less Selective/Open                 High Pell (40-60%)      280           46.3%             47.2%
# Less Selective/Open                 Low Pell (under 20%)     73           64.6%             70.2%
# Less Selective/Open                 Moderate Pell (20-40%)    429           58.6%             60.3%
# Less Selective/Open                 Very High Pell (60%+)    145           42.6%             39.7%
# Moderately Selective                High Pell (40-60%)      170           49.5%             50.8%
# Moderately Selective                Low Pell (under 20%)     64           78.5%             81.6%
# Moderately Selective                Moderate Pell (20-40%)    265           62.9%             64.3%
# Moderately Selective                Very High Pell (60%+)     57           35.5%             33.8%
# Selective                           High Pell (40-60%)       35           49.1%             49.6%
# Selective                           Low Pell (under 20%)     41           83.8%             84.4%
# Selective                           Moderate Pell (20-40%)     49           69.3%             71.9%
# Selective                           Very High Pell (60%+)     31           40.9%             40.8%
# 
# * = sparse cell (n < 10), interpret with caution
# 
# ================================================================================
# INTERPRETATION: Within-Band Variation by Pell Share
# ================================================================================
# 
#   Highly Selective:
#     Pell bands represented: 4
#     Total institutions: 65
#     Smallest cell: n=1
#     Mean grad rate range: 29.3% to 91.8%
#     Spread (max - min): 62.5 percentage points
#     --> MEANINGFUL variation (62.5 pp > 5 pp threshold)
#     --> CAUTION: At least one cell has n < 10; results may not be reliable
# 
#   Less Selective/Open:
#     Pell bands represented: 4
#     Total institutions: 927
#     Smallest cell: n=73
#     Mean grad rate range: 42.6% to 64.6%
#     Spread (max - min): 21.9 percentage points
#     --> MEANINGFUL variation (21.9 pp > 5 pp threshold)
# 
#   Moderately Selective:
#     Pell bands represented: 4
#     Total institutions: 556
#     Smallest cell: n=57
#     Mean grad rate range: 35.5% to 78.5%
#     Spread (max - min): 42.9 percentage points
#     --> MEANINGFUL variation (42.9 pp > 5 pp threshold)
# 
#   Selective:
#     Pell bands represented: 4
#     Total institutions: 156
#     Smallest cell: n=31
#     Mean grad rate range: 40.9% to 83.8%
#     Spread (max - min): 42.9 percentage points
#     --> MEANINGFUL variation (42.9 pp > 5 pp threshold)
# 
# ================================================================================
# OVERALL ASSESSMENT
# ================================================================================
# Selectivity bands with meaningful Pell variation (>5 pp): 4 of 4
#   Highly Selective: 62.5 pp [MEANINGFUL]
#   Less Selective/Open: 21.9 pp [MEANINGFUL]
#   Moderately Selective: 42.9 pp [MEANINGFUL]
#   Selective: 42.9 pp [MEANINGFUL]
# 
# OBSERVABLE TRUTH SUPPORTED: In a majority of selectivity bands, Pell share explains meaningful graduation rate variation.
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_crosstab_selectivity_pell.parquet
# 
# ============================================================
# CHECKPOINT VALIDATION
# ============================================================
#   [PASS] Output has rows: 16
#   [PASS] Selectivity bands covered: 3 of 4
#     Unexpected bands: {'Less Selective/Open'}
#     Missing bands: {'Less Selective/Open Admission'}
#   [PASS] All n values positive: True
#   [PASS] Grad rates in 0-100 range: mean=True, median=True
#   [WARN] Sparse cells (n < 10): 2 cells
#     Highly Selective x High Pell (40-60%): n=3
#     Highly Selective x Very High Pell (60%+): n=1
#   [PASS] Total n matches filtered rows: 1,704 vs 1,704
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
