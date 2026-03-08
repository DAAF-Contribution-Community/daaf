#!/usr/bin/env python3
"""
Stage 8.1: Descriptive statistics by selectivity band.

Task: descriptive-by-selectivity
Wave: 7, Step: 1, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_descriptive_by_selectivity.parquet
Checkpoint: CP3 (analysis validation)
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for descriptive statistics by selectivity band.
# The analysis dataset was created in Stage 7 with selectivity_band derived
# from admission_rate quartile-based thresholds. We compute summary statistics
# for each band to establish the graduation rate gradient across selectivity levels.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_descriptive_by_selectivity.parquet"

# REASONING: The selectivity band ordering reflects the natural gradient from
# most to least selective. This ordering is used for display and validates
# Observable Truth: "Institutions with lower admission rates have significantly
# higher graduation rates."
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]

# Metric columns to summarize — these are the key institutional characteristics
# that vary across selectivity levels, providing context for the graduation rate story.
METRIC_COLS = [
    "grad_rate_150pct",
    "admission_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
]

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands step).
# Verify it contains selectivity_band and the required metric columns.
print("=" * 60)
print("Stage 8.1: Descriptive Statistics by Selectivity Band")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture dataset shape and verify required columns exist before aggregation.
# Also document the selectivity band distribution to confirm expected counts.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Verify required columns exist
required_cols = ["selectivity_band"] + METRIC_COLS
missing_cols = [c for c in required_cols if c not in df.columns]
assert len(missing_cols) == 0, f"STOP: Missing required columns: {missing_cols}"
print(f"All required columns present: {required_cols}")

# Document selectivity band distribution before aggregation
print("\nSelectivity band distribution:")
band_counts = df.group_by("selectivity_band").agg(pl.len().alias("n")).sort("n", descending=True)
for row in band_counts.iter_rows(named=True):
    print(f"  {row['selectivity_band']}: {row['n']:,}")

total_institutions = df.shape[0]
print(f"  Total: {total_institutions:,}")

# Count institutions with non-null grad rates (the denominator for n sum validation)
# REASONING: Some institutions may have null grad_rate_150pct (29% null per context).
# The n values in our summary should reflect institutions WITH graduation rate data,
# since that is the primary metric being described.
institutions_with_grad = df.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]
print(f"  With grad_rate_150pct: {institutions_with_grad:,}")

# --- Transform ---
# INTENT: Compute comprehensive descriptive statistics for each selectivity band.
# This table establishes the core gradient: as selectivity increases (admission rate
# decreases), graduation rates should increase — testing Observable Truth #1.
#
# REASONING: We compute both median and mean because:
#   - Median is robust to skew (graduation rates and admission rates can be skewed)
#   - Mean is useful for comparison with published statistics
#   - Standard deviation quantifies within-band variation
#   - Q1 and Q3 show the interquartile range for graduation rates specifically
#
# ASSUMES:
#   - selectivity_band is already categorized with exactly 4 levels (from Stage 7)
#   - Null values in metric columns are excluded from each statistic (Polars default)
#   - grad_rate_150pct is on 0-100 scale, admission_rate is on 0-1 scale

# Build aggregation expressions
agg_exprs = [
    # n: count of institutions in each band (total, regardless of nulls)
    pl.len().alias("n"),
]

for col in METRIC_COLS:
    if col == "grad_rate_150pct":
        # Full suite of statistics for the primary metric (graduation rate)
        agg_exprs.extend([
            pl.col(col).median().alias(f"{col}_median"),
            pl.col(col).mean().alias(f"{col}_mean"),
            pl.col(col).std().alias(f"{col}_std"),
            pl.col(col).quantile(0.25).alias(f"{col}_q1"),
            pl.col(col).quantile(0.75).alias(f"{col}_q3"),
            pl.col(col).count().alias(f"{col}_count"),  # Non-null count for this metric
        ])
    else:
        # Median and mean for context metrics
        agg_exprs.extend([
            pl.col(col).median().alias(f"{col}_median"),
            pl.col(col).mean().alias(f"{col}_mean"),
        ])

print("\nComputing descriptive statistics by selectivity band...")

result = (
    df
    .group_by("selectivity_band")
    .agg(agg_exprs)
)

# INTENT: Order bands from most to least selective for display and validation.
# REASONING: Using a manual sort via join with an ordering DataFrame, because
# Polars group_by does not guarantee output order. The ordering is conceptually
# important — the graduation rate gradient should be visible top to bottom.
order_df = pl.DataFrame({
    "selectivity_band": BAND_ORDER,
    "sort_order": list(range(len(BAND_ORDER))),
})

result = (
    result
    .join(order_df, on="selectivity_band", how="left")
    .sort("sort_order")
    .drop("sort_order")
)

print(f"Result: {result.shape[0]} rows x {result.shape[1]} cols")

# --- Display ---
# Print the full summary table for inspection and audit trail.
print("\n" + "=" * 60)
print("DESCRIPTIVE STATISTICS BY SELECTIVITY BAND")
print("=" * 60)

for row in result.iter_rows(named=True):
    band = row["selectivity_band"]
    n = row["n"]
    print(f"\n--- {band} (n={n:,}) ---")
    print(f"  Graduation Rate (150% time):")
    print(f"    Median: {row['grad_rate_150pct_median']:.1f}%")
    print(f"    Mean:   {row['grad_rate_150pct_mean']:.1f}%")
    print(f"    Std:    {row['grad_rate_150pct_std']:.1f}%")
    print(f"    Q1:     {row['grad_rate_150pct_q1']:.1f}%")
    print(f"    Q3:     {row['grad_rate_150pct_q3']:.1f}%")
    print(f"    Count:  {row['grad_rate_150pct_count']:,} (non-null)")
    print(f"  Admission Rate:")
    print(f"    Median: {row['admission_rate_median']:.3f}")
    print(f"    Mean:   {row['admission_rate_mean']:.3f}")
    print(f"  Pell Share:")
    print(f"    Median: {row['pell_share_median']:.3f}")
    print(f"    Mean:   {row['pell_share_mean']:.3f}")
    print(f"  URM Share:")
    print(f"    Median: {row['urm_share_median']:.3f}")
    print(f"    Mean:   {row['urm_share_mean']:.3f}")
    print(f"  Student-Faculty Ratio:")
    print(f"    Median: {row['student_faculty_ratio_median']:.1f}")
    print(f"    Mean:   {row['student_faculty_ratio_mean']:.1f}")
    print(f"  Retention Rate:")
    print(f"    Median: {row['retention_rate_median']:.1f}%")
    print(f"    Mean:   {row['retention_rate_mean']:.1f}%")

# --- Save ---
# Persist results in parquet format to output/analysis/ directory.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- Validate ---
# Checkpoint validation against task specification requirements.
# Each check corresponds to a specific verification criterion from the task.
print("\n" + "=" * 60)
print("CHECKPOINT VALIDATION")
print("=" * 60)

# V1: Exactly 4 rows (one per selectivity band)
has_4_rows = result.shape[0] == 4
print(f"  [{'PASS' if has_4_rows else 'FAIL'}] Exactly 4 rows: {result.shape[0]}")

# V2: All metric columns are non-null
# INTENT: Verify that every band has data for every metric. A null in any metric
# column would indicate a band with no non-null values for that metric.
null_metrics = []
for col in result.columns:
    if col == "selectivity_band" or col == "n":
        continue
    null_count = result[col].null_count()
    if null_count > 0:
        null_metrics.append(f"{col}: {null_count} nulls")

all_metrics_present = len(null_metrics) == 0
print(f"  [{'PASS' if all_metrics_present else 'FAIL'}] All metrics non-null: "
      f"{'OK' if all_metrics_present else '; '.join(null_metrics)}")

# V3: Graduation rate medians decrease from Highly Selective to Less Selective
# REASONING: This is the core Observable Truth test — the gradient should be
# monotonically decreasing (or at least generally decreasing) from the most
# selective band to the least selective band.
grad_medians = result.sort("selectivity_band").select("selectivity_band", "grad_rate_150pct_median")
# Re-extract in band order
ordered_medians = []
for band in BAND_ORDER:
    median_val = result.filter(pl.col("selectivity_band") == band)["grad_rate_150pct_median"][0]
    ordered_medians.append((band, median_val))
    print(f"    {band}: {median_val:.1f}%")

# Check monotonic decrease
is_decreasing = all(
    ordered_medians[i][1] >= ordered_medians[i + 1][1]
    for i in range(len(ordered_medians) - 1)
)
print(f"  [{'PASS' if is_decreasing else 'WARN'}] Grad rate medians decreasing: {is_decreasing}")

# V4: n values sum to total institution count
n_sum = result["n"].sum()
n_matches = n_sum == total_institutions
print(f"  [{'PASS' if n_matches else 'FAIL'}] n sum matches total: {n_sum:,} == {total_institutions:,}")

# V5: Band names match expected values
actual_bands = sorted(result["selectivity_band"].to_list())
expected_bands = sorted(BAND_ORDER)
bands_match = actual_bands == expected_bands
print(f"  [{'PASS' if bands_match else 'FAIL'}] Band names match: {actual_bands}")

# Overall status
all_passed = has_4_rows and all_metrics_present and n_matches and bands_match
# Note: is_decreasing is a WARN not FAIL — the gradient is expected but not strictly required
if not is_decreasing:
    print("\n  WARNING: Graduation rate medians are not strictly monotonically decreasing.")
    print("  This may reflect data characteristics rather than an error.")

print("\n" + "=" * 60)
if all_passed:
    print("CP VALIDATION: PASSED")
else:
    print("CP VALIDATION: FAILED")
print("=" * 60)

if not all_passed:
    raise SystemExit(1)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:49:28
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/01_descriptive-by-selectivity.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Descriptive Statistics by Selectivity Band
# ============================================================
# Loaded: 2,528 rows x 26 cols
# 
# Pre-state: 2,528 rows, 26 cols
# All required columns present: ['selectivity_band', 'grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
# 
# Selectivity band distribution:
#   Less Selective/Open: 1,695
#   Moderately Selective: 586
#   Selective: 174
#   Highly Selective: 73
#   Total: 2,528
#   With grad_rate_150pct: 1,796
# 
# Computing descriptive statistics by selectivity band...
# Result: 4 rows x 18 cols
# 
# ============================================================
# DESCRIPTIVE STATISTICS BY SELECTIVITY BAND
# ============================================================
# 
# --- Highly Selective (n=73) ---
#   Graduation Rate (150% time):
#     Median: 92.3%
#     Mean:   88.5%
#     Std:    13.6%
#     Q1:     89.3%
#     Q3:     94.1%
#     Count:  69 (non-null)
#   Admission Rate:
#     Median: 0.143
#     Mean:   0.144
#   Pell Share:
#     Median: 0.166
#     Mean:   0.201
#   URM Share:
#     Median: 0.184
#     Mean:   0.195
#   Student-Faculty Ratio:
#     Median: 8.0
#     Mean:   8.3
#   Retention Rate:
#     Median: 92.0%
#     Mean:   89.5%
# 
# --- Selective (n=174) ---
#   Graduation Rate (150% time):
#     Median: 63.6%
#     Mean:   62.7%
#     Std:    22.4%
#     Q1:     43.6%
#     Q3:     83.5%
#     Count:  159 (non-null)
#   Admission Rate:
#     Median: 0.401
#     Mean:   0.400
#   Pell Share:
#     Median: 0.353
#     Mean:   0.405
#   URM Share:
#     Median: 0.227
#     Mean:   0.332
#   Student-Faculty Ratio:
#     Median: 11.0
#     Mean:   12.7
#   Retention Rate:
#     Median: 81.5%
#     Mean:   76.7%
# 
# --- Moderately Selective (n=586) ---
#   Graduation Rate (150% time):
#     Median: 58.8%
#     Mean:   57.7%
#     Std:    17.3%
#     Q1:     46.7%
#     Q3:     70.6%
#     Count:  564 (non-null)
#   Admission Rate:
#     Median: 0.653
#     Mean:   0.644
#   Pell Share:
#     Median: 0.366
#     Mean:   0.389
#   URM Share:
#     Median: 0.201
#     Mean:   0.269
#   Student-Faculty Ratio:
#     Median: 13.0
#     Mean:   13.5
#   Retention Rate:
#     Median: 76.0%
#     Mean:   75.5%
# 
# --- Less Selective/Open (n=1,695) ---
#   Graduation Rate (150% time):
#     Median: 53.7%
#     Mean:   52.5%
#     Std:    18.5%
#     Q1:     39.7%
#     Q3:     65.0%
#     Count:  1,004 (non-null)
#   Admission Rate:
#     Median: 0.857
#     Mean:   0.865
#   Pell Share:
#     Median: 0.385
#     Mean:   0.420
#   URM Share:
#     Median: 0.218
#     Mean:   0.305
#   Student-Faculty Ratio:
#     Median: 14.0
#     Mean:   14.2
#   Retention Rate:
#     Median: 75.0%
#     Mean:   72.1%
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-02-15_descriptive_by_selectivity.parquet
# 
# ============================================================
# CHECKPOINT VALIDATION
# ============================================================
#   [PASS] Exactly 4 rows: 4
#   [PASS] All metrics non-null: OK
#     Highly Selective: 92.3%
#     Selective: 63.6%
#     Moderately Selective: 58.8%
#     Less Selective/Open: 53.7%
#   [PASS] Grad rate medians decreasing: True
#   [PASS] n sum matches total: 2,528 == 2,528
#   [PASS] Band names match: ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
# 
# ============================================================
# CP VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
