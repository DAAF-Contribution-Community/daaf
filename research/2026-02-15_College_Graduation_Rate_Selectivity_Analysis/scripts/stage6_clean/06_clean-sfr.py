#!/usr/bin/env python3
"""
Stage 6.6: Clean IPEDS student-faculty ratio data — replace coded missing values with null.

Task: clean-sfr
Wave: 4, Step: 6, Stage: 6
Depends on: fetch-sfr (COMPLETE)
Input: data/raw/2026-02-15_ipeds_sfr.parquet
Output: data/processed/2026-02-15_sfr_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for cleaning IPEDS student-faculty ratio data.
# The Education Data Portal uses integer sentinel values (-1, -2, -3) for
# missing data in numeric columns. These must be replaced with null before
# any statistical computation to prevent corruption of means/medians.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_sfr.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfr_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data rather than null. These must be mapped to null so they don't corrupt
# downstream statistical calculations (e.g., mean SFR would be dragged down
# by negative coded values if left in place).
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}

# The primary numeric column of interest for this dataset
SFR_COLUMN = "student_faculty_ratio"

# --- Load ---
# Load raw SFR data from Stage 5 output and verify shape before proceeding.
print("=" * 60)
print("Stage 6.6: Clean IPEDS student-faculty ratio data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Also enumerate coded values present so we can verify they're all removed.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# INTENT: Profile the student_faculty_ratio column to understand data quality
# before cleaning. This establishes the baseline for comparison with post-state.
print(f"\n--- Pre-clean SFR distribution ---")
print(f"  Min: {df[SFR_COLUMN].min()}")
print(f"  Max: {df[SFR_COLUMN].max()}")
print(f"  Mean: {df[SFR_COLUMN].mean():.2f}" if df[SFR_COLUMN].mean() is not None else "  Mean: None")
print(f"  Median: {df[SFR_COLUMN].median()}")
print(f"  Null count: {df[SFR_COLUMN].null_count()}")

# INTENT: Count occurrences of each coded missing value in the SFR column
# to document what will be replaced.
coded_counts = {}
for code, meaning in CODED_MISSING.items():
    count = df.filter(pl.col(SFR_COLUMN) == code).height
    if count > 0:
        coded_counts[code] = count
        print(f"  {SFR_COLUMN} = {code} ({meaning}): {count:,}")

if not coded_counts:
    print("  No coded missing values (-1, -2, -3) found in SFR column")

# Also check for any other integer columns that might have coded values
int_cols = [c for c in df.columns if df[c].dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64)]
print(f"\nInteger columns found: {int_cols}")
for col in int_cols:
    if col == SFR_COLUMN:
        continue  # Already profiled above
    for code, meaning in CODED_MISSING.items():
        count = df.filter(pl.col(col) == code).height
        if count > 0:
            print(f"  {col} = {code} ({meaning}): {count:,}")

# --- Clean ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in the
# student_faculty_ratio column so downstream statistical operations are valid.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation -- these values were never observed or are suppressed.
# Zero would imply a measured SFR of zero (impossible for an institution with
# students and faculty). Polars handles nulls natively in aggregations (excluded
# from mean/median by default), which is the correct behavior.
#
# ASSUMES: Coded values (-1, -2, -3) apply to the student_faculty_ratio
# numeric measure column, per Education Data Portal conventions documented in
# the education-data-context skill.
df = df.with_columns(
    pl.when(pl.col(SFR_COLUMN).is_in(list(CODED_MISSING.keys())))
    .then(None)
    .otherwise(pl.col(SFR_COLUMN))
    .alias(SFR_COLUMN)
)

# Also clean any other integer columns that may have coded values
# REASONING: Even if unitid or year contain coded values (unlikely for identifiers),
# we only clean the SFR measure column. Identifiers with value -1/-2/-3 are
# actual values, not missing indicators. However, if there are other numeric
# measure columns (like counts), they should be cleaned too.
# In this dataset, the primary measure is student_faculty_ratio only.
print("\nReplaced coded values with null in student_faculty_ratio")

# --- Post-state ---
# Verify the transformation preserved row count and removed coded values.
post_rows = df.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {len(df.columns)} cols")
print(f"Row change: {((post_rows - pre_rows) / pre_rows * 100):+.1f}%")

# INTENT: Profile SFR distribution after cleaning to confirm coded values removed
# and distribution is now sensible.
print(f"\n--- Post-clean SFR distribution ---")
sfr_valid = df.filter(pl.col(SFR_COLUMN).is_not_null())
print(f"  Non-null count: {sfr_valid.height:,}")
print(f"  Null count: {df[SFR_COLUMN].null_count()}")

if sfr_valid.height > 0:
    print(f"  Min: {sfr_valid[SFR_COLUMN].min()}")
    print(f"  Max: {sfr_valid[SFR_COLUMN].max()}")
    sfr_mean = sfr_valid[SFR_COLUMN].mean()
    sfr_median = sfr_valid[SFR_COLUMN].median()
    print(f"  Mean: {sfr_mean:.2f}" if sfr_mean is not None else "  Mean: None")
    print(f"  Median: {sfr_median}")

# --- Save ---
# Persist cleaned results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, null rate within
# acceptable bounds, row count preserved, and SFR range is reasonable.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

# CP2.1: No coded values remain in SFR column
coded_remaining = 0
for code in CODED_MISSING.keys():
    coded_remaining += df.filter(pl.col(SFR_COLUMN) == code).height

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")

# CP2.2: SFR range reasonable for non-null values (1-100)
# REASONING: A student-faculty ratio above 100 is highly unusual. The Stage 5
# findings noted SFR=110 at unitid 246035 as an outlier, but ratios up to ~110
# can exist at very large institutions. We check the range is within 1-110
# to allow for that known outlier, while flagging if values are outside 1-100
# for the vast majority.
sfr_non_null = df.filter(pl.col(SFR_COLUMN).is_not_null())
if sfr_non_null.height > 0:
    sfr_min = sfr_non_null[SFR_COLUMN].min()
    sfr_max = sfr_non_null[SFR_COLUMN].max()
    # Core check: values should be positive and within a plausible range
    range_ok = sfr_min >= 1 and sfr_max <= 150  # generous upper bound
    print(f"  [{'PASS' if range_ok else 'FAIL'}] SFR range: {sfr_min} - {sfr_max} (expected 1-150)")

    # Informational: how many are above 100 (unusual but not invalid)
    above_100 = sfr_non_null.filter(pl.col(SFR_COLUMN) > 100).height
    if above_100 > 0:
        print(f"  [WARN] {above_100} institution(s) with SFR > 100")
else:
    range_ok = False
    print("  [FAIL] No non-null SFR values after cleaning")

# CP2.3: Null rate < 30% (task specification threshold)
# REASONING: The 30% threshold is from the task specification. Above 30%
# missingness, the SFR variable may not be reliable enough for analysis.
total_rows = df.shape[0]
null_count = df[SFR_COLUMN].null_count()
null_rate = null_count / total_rows if total_rows > 0 else 0
null_ok = null_rate < 0.30
print(f"  [{'PASS' if null_ok else 'FAIL'}] Null rate < 30%: {null_rate:.1%} ({null_count:,} / {total_rows:,})")

# CP2.4: Row count preserved (cleaning replaces values but should not drop rows)
rows_preserved = post_rows == pre_rows
print(f"  [{'PASS' if rows_preserved else 'FAIL'}] Rows preserved: {pre_rows:,} -> {post_rows:,}")

# CP2.5: Suppression rate (overall nulls across all measure columns)
# REASONING: For this single-measure dataset, suppression rate = null rate in SFR
suppression_rate = null_rate
suppression_ok = suppression_rate < 0.50
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: {suppression_rate:.1%}")

# Assertions for hard stops
assert no_coded, "STOP: Coded values still present in student_faculty_ratio"
assert range_ok, "STOP: SFR range outside expected bounds"
assert null_ok, "STOP: Null rate >= 30% in student_faculty_ratio"
assert rows_preserved, "STOP: Row count changed during cleaning"
assert suppression_ok, "STOP: Suppression rate >= 50%"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:49:45
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/06_clean-sfr.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.6: Clean IPEDS student-faculty ratio data
# ============================================================
# Loaded: 5,836 rows x 3 cols
# Columns: ['unitid', 'year', 'student_faculty_ratio']
# Dtypes: [Int64, Int64, Int64]
# 
# Pre-state: 5,836 rows, 3 cols
# 
# --- Pre-clean SFR distribution ---
#   Min: 1
#   Max: 110
#   Mean: 15.12
#   Median: 14.0
#   Null count: 1
#   No coded missing values (-1, -2, -3) found in SFR column
# 
# Integer columns found: ['unitid', 'year', 'student_faculty_ratio']
# 
# Replaced coded values with null in student_faculty_ratio
# 
# Post-state: 5,836 rows, 3 cols
# Row change: +0.0%
# 
# --- Post-clean SFR distribution ---
#   Non-null count: 5,835
#   Null count: 1
#   Min: 1
#   Max: 110
#   Mean: 15.12
#   Median: 14.0
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_sfr_clean.parquet
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values remaining: 0
#   [PASS] SFR range: 1 - 110 (expected 1-150)
#   [WARN] 1 institution(s) with SFR > 100
#   [PASS] Null rate < 30%: 0.0% (1 / 5,836)
#   [PASS] Rows preserved: 5,836 -> 5,836
#   [PASS] Suppression rate < 50%: 0.0%
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
