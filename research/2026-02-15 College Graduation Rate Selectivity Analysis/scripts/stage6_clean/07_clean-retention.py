#!/usr/bin/env python3
"""
Stage 6.7: Clean IPEDS retention rate data — scale conversion, coded value removal.

Task: clean-retention
Wave: 4, Step: 7, Stage: 6
Depends on: fetch-retention (COMPLETE)
Input: data/raw/2026-02-15_ipeds_retention.parquet
Output: data/processed/2026-02-15_retention_clean.parquet
Checkpoint: CP2

Research Question: Are high college graduation rates a signal of institutional
quality, or primarily a reflection of admissions selectivity and student body
demographics?

Key Context from Stage 5 QA:
- retention_rate is on 0-1 PROPORTION scale (NOT 0-100 as Plan assumed)
- 654 nulls (11.2%) — within expected range
- COVID effects visible at selective institutions (e.g., Harvard 0.97->0.76)
  which are legitimate data, not errors
- All rows are ftpt==1, year==2020
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for IPEDS retention rate cleaning. The raw data
# was fetched filtered to ftpt==1 (first-time, full-time) and year==2020.
# The key cleaning operation is scale conversion: retention_rate arrives as
# a 0-1 proportion and must be converted to 0-100 percentage to match
# grad_rate_150pct scale used in downstream analysis (Stage 7 join).
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_retention.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_retention_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values (-1, -2, -3)
# for missing data in numeric columns. These must be replaced with null before
# any statistical computation, otherwise they corrupt means, medians, and
# distribution analyses. For retention_rate on a 0-1 scale, any negative value
# is definitively a coded missing value (not a legitimate proportion).
CODED_MISSING = [-1, -2, -3]

# Critical column for this cleaning task
RETENTION_COL = "retention_rate"

# --- Load ---
# Load raw retention data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.7: Clean IPEDS retention rate data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Document the raw scale, null counts, and coded value presence so we can
# verify all cleaning operations completed correctly.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Check for coded missing values in retention_rate
# INTENT: Enumerate how many coded values exist so we can verify complete removal.
# ASSUMES: retention_rate is numeric (Float64 or Int64) and coded values are
# negative integers per Education Data Portal convention.
coded_value_counts = {}
for code in CODED_MISSING:
    count = df.filter(pl.col(RETENTION_COL) == code).height
    if count > 0:
        coded_value_counts[code] = count
        print(f"  Coded value {code}: {count:,} occurrences")

if not coded_value_counts:
    print("  No coded missing values (-1, -2, -3) found in retention_rate")

# Document current null count before cleaning
pre_null_count = df[RETENTION_COL].null_count()
print(f"  Pre-existing nulls in {RETENTION_COL}: {pre_null_count:,}")

# Document current scale
# INTENT: Confirm the 0-1 proportion scale reported by Stage 5 QA before converting.
# This is the truth hierarchy in action: we trust the actual data over the Plan's
# assumption of 0-100 scale.
non_null_retention = df.filter(pl.col(RETENTION_COL).is_not_null())
if non_null_retention.height > 0:
    raw_min = non_null_retention[RETENTION_COL].min()
    raw_max = non_null_retention[RETENTION_COL].max()
    raw_mean = non_null_retention[RETENTION_COL].mean()
    raw_median = non_null_retention[RETENTION_COL].median()
    print(f"\n  Raw retention_rate scale check:")
    print(f"    Min: {raw_min}")
    print(f"    Max: {raw_max}")
    print(f"    Mean: {raw_mean:.4f}")
    print(f"    Median: {raw_median:.4f}")

    # REASONING: If max <= 1.0, the data is on a 0-1 proportion scale.
    # If max > 1.0, it may already be on a 0-100 percentage scale.
    # Stage 5 QA confirmed 0-1 scale, but we verify here independently.
    if raw_max <= 1.0:
        print("    Scale: CONFIRMED 0-1 proportion (will convert to 0-100)")
        scale_is_proportion = True
    elif raw_max <= 100.0:
        print("    Scale: Appears to be 0-100 already (no conversion needed)")
        scale_is_proportion = False
    else:
        print(f"    [WARN] Unexpected max value {raw_max} — investigate before proceeding")
        scale_is_proportion = False

# Keep a copy of raw data for CP2 suppression rate calculation
raw_df = df.clone()

# --- Transform: Step 1 — Replace coded missing values with null ---
# INTENT: Replace Education Data Portal coded missing values (-1, -2, -3)
# with proper null so they don't corrupt downstream statistical calculations.
#
# REASONING: Using null (not zero, not NaN) because null is semantically correct —
# these values were never observed or are suppressed. Zero would imply a measured
# 0% retention rate, and NaN would complicate Polars aggregations which handle
# null natively.
#
# ASSUMES: Coded values only appear in numeric measure columns. The retention_rate
# column is the only numeric measure we need to clean in this dataset.
print("\n--- Step 1: Replace coded missing values ---")

df = df.with_columns(
    pl.when(pl.col(RETENTION_COL).is_in(CODED_MISSING))
    .then(None)
    .otherwise(pl.col(RETENTION_COL))
    .alias(RETENTION_COL)
)

post_coded_null_count = df[RETENTION_COL].null_count()
coded_values_replaced = post_coded_null_count - pre_null_count
print(f"  Coded values replaced with null: {coded_values_replaced:,}")
print(f"  Total nulls after coded value removal: {post_coded_null_count:,}")

# --- Transform: Step 2 — Scale conversion (0-1 to 0-100) ---
# INTENT: Convert retention_rate from 0-1 proportion scale to 0-100 percentage
# scale for consistency with grad_rate_150pct which is on a 0-100 scale.
# This enables direct comparison and meaningful regression coefficients in
# downstream analysis (Stage 8).
#
# REASONING: The Plan assumed retention_rate would be on 0-100 scale, but Stage 5
# QA confirmed it is 0-1. Per the Truth Hierarchy, we trust the actual data.
# Converting to 0-100 rather than converting grad_rate to 0-1 because:
#   - Percentage scale (0-100) is more intuitive for stakeholder interpretation
#   - grad_rate_150pct is already on 0-100 and has been cleaned (Stage 6.2)
#   - Converting one column is simpler and lower-risk than re-processing
#
# ASSUMES: After Step 1, retention_rate values are either null or valid
# proportions in [0, 1]. Multiplying by 100 produces percentages in [0, 100].
print("\n--- Step 2: Scale conversion (0-1 -> 0-100) ---")

if scale_is_proportion:
    df = df.with_columns(
        (pl.col(RETENTION_COL) * 100).alias(RETENTION_COL)
    )
    print("  Multiplied retention_rate by 100 (proportion -> percentage)")
else:
    print("  No scale conversion needed (already 0-100)")

# --- Post-state ---
# Capture state AFTER transformation for validation comparison.
post_rows = df.shape[0]
post_null_count = df[RETENTION_COL].null_count()
non_null_post = df.filter(pl.col(RETENTION_COL).is_not_null())

print(f"\nPost-state: {post_rows:,} rows, {df.shape[1]} cols")
print(f"  Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

if non_null_post.height > 0:
    post_min = non_null_post[RETENTION_COL].min()
    post_max = non_null_post[RETENTION_COL].max()
    post_mean = non_null_post[RETENTION_COL].mean()
    post_median = non_null_post[RETENTION_COL].median()
    print(f"\n  retention_rate distribution (after conversion):")
    print(f"    Min:    {post_min:.2f}")
    print(f"    Max:    {post_max:.2f}")
    print(f"    Mean:   {post_mean:.2f}")
    print(f"    Median: {post_median:.2f}")
    print(f"    Nulls:  {post_null_count:,} ({post_null_count / post_rows * 100:.1f}%)")

# Print a sample of extreme values for manual inspection
# INTENT: Show COVID-affected institutions with low retention for context.
# Harvard's drop from 97% to 76% was noted in Stage 5 as legitimate COVID effect.
print(f"\n  Bottom 5 retention rates (non-null):")
bottom5 = non_null_post.sort(RETENTION_COL).head(5)
for row in bottom5.iter_rows(named=True):
    unitid = row.get("unitid", "N/A")
    rate = row[RETENTION_COL]
    print(f"    unitid={unitid}, retention_rate={rate:.2f}")

print(f"\n  Top 5 retention rates (non-null):")
top5 = non_null_post.sort(RETENTION_COL, descending=True).head(5)
for row in top5.iter_rows(named=True):
    unitid = row.get("unitid", "N/A")
    rate = row[RETENTION_COL]
    print(f"    unitid={unitid}, retention_rate={rate:.2f}")

# --- Save ---
# Persist results in parquet format to the processed data directory.
# Output path matches the Plan's file specification.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, suppression rate
# is within acceptable bounds, row count is preserved, and scale conversion
# produced values in the expected 0-100 range.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

cp2_passed = True

# CP2.1: No coded values remain in retention_rate
coded_remaining = 0
for code in CODED_MISSING:
    count = df.filter(pl.col(RETENTION_COL) == code).height
    coded_remaining += count

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")
if not no_coded:
    cp2_passed = False

# CP2.2: retention_rate range is 0-100 for non-null values (after conversion)
# REASONING: After multiplying 0-1 proportions by 100, all valid values should
# be in [0, 100]. Values outside this range indicate data corruption or
# incorrect conversion logic.
non_null_check = df.filter(pl.col(RETENTION_COL).is_not_null())
if non_null_check.height > 0:
    check_min = non_null_check[RETENTION_COL].min()
    check_max = non_null_check[RETENTION_COL].max()
    range_ok = check_min >= 0 and check_max <= 100
    print(f"  [{'PASS' if range_ok else 'FAIL'}] retention_rate range 0-100: min={check_min:.2f}, max={check_max:.2f}")
    if not range_ok:
        cp2_passed = False
else:
    print("  [FAIL] No non-null retention_rate values to validate range")
    cp2_passed = False

# CP2.3: Null rate less than 30% (expect ~11%)
# REASONING: Stage 5 found 654 nulls (11.2%) in 5,836 rows. After replacing
# coded values with null, the null rate may increase slightly but should stay
# well below 30%. A rate above 30% would indicate unexpected data loss.
null_rate = post_null_count / post_rows if post_rows > 0 else 0
null_ok = null_rate < 0.30
print(f"  [{'PASS' if null_ok else 'FAIL'}] Null rate < 30%: {null_rate:.1%} ({post_null_count:,} nulls)")
if not null_ok:
    cp2_passed = False

# CP2.4: Row count preserved (5,836 expected — cleaning replaces values, not rows)
# REASONING: This cleaning script only replaces coded values with null and
# converts scale. No rows should be added or removed.
rows_preserved = post_rows == pre_rows
expected_rows = 5836
rows_match_expected = post_rows == expected_rows
print(f"  [{'PASS' if rows_preserved else 'FAIL'}] Rows preserved: {pre_rows:,} -> {post_rows:,}")
if rows_match_expected:
    print(f"  [PASS] Row count matches expected: {post_rows:,} == {expected_rows:,}")
else:
    print(f"  [WARN] Row count differs from expected: {post_rows:,} vs {expected_rows:,}")
if not rows_preserved:
    cp2_passed = False

# CP2.5: Suppression rate check (overall null rate across key variable)
# REASONING: The 50% threshold is from CLAUDE.md STOP conditions. Above 50%
# suppression, the remaining data is too sparse to support reliable analysis.
suppression_rate = null_rate  # For single-variable cleaning, null rate IS suppression rate
suppression_ok = suppression_rate < 0.50
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: {suppression_rate:.1%}")
if not suppression_ok:
    cp2_passed = False

# CP2.6: Scale conversion sanity check — mean should be ~70-80 for IPEDS retention
# REASONING: National average first-time full-time retention rate is typically
# in the 70-80% range. A mean far outside this range after conversion would
# indicate a conversion error.
if non_null_check.height > 0:
    mean_val = non_null_check[RETENTION_COL].mean()
    mean_plausible = 30 <= mean_val <= 100  # Allow wide range for diverse institutions
    print(f"  [{'PASS' if mean_plausible else 'WARN'}] Mean retention plausible: {mean_val:.2f}%")

# Final CP2 status
print(f"\n{'=' * 60}")
print(f"CP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print(f"{'=' * 60}")

assert cp2_passed, "STOP: CP2 validation failed — see details above"

# --- Deviation Documentation ---
# DEVIATION (RULE 1 — Plan correction based on observed data):
# The Plan stated "verify retention_rate scale (0-100 expected)" but Stage 5 QA
# confirmed the data arrives on a 0-1 proportion scale. This script converts
# to 0-100 by multiplying by 100, per orchestrator instruction. This is a data
# reality correction, not a methodology change.
print("\nDeviation: Converted retention_rate from 0-1 to 0-100 scale (Plan assumed 0-100)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:50:17
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage6_clean/07_clean-retention.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.7: Clean IPEDS retention rate data
# ============================================================
# Loaded: 5,836 rows x 3 cols
# Columns: ['unitid', 'year', 'retention_rate']
# 
# Pre-state: 5,836 rows, 3 cols
#   No coded missing values (-1, -2, -3) found in retention_rate
#   Pre-existing nulls in retention_rate: 654
# 
#   Raw retention_rate scale check:
#     Min: 0.0
#     Max: 1.0
#     Mean: 0.7065
#     Median: 0.7300
#     Scale: CONFIRMED 0-1 proportion (will convert to 0-100)
# 
# --- Step 1: Replace coded missing values ---
#   Coded values replaced with null: 0
#   Total nulls after coded value removal: 654
# 
# --- Step 2: Scale conversion (0-1 -> 0-100) ---
#   Multiplied retention_rate by 100 (proportion -> percentage)
# 
# Post-state: 5,836 rows, 3 cols
#   Row change: +0 (+0.0%)
# 
#   retention_rate distribution (after conversion):
#     Min:    0.00
#     Max:    100.00
#     Mean:   70.65
#     Median: 73.00
#     Nulls:  654 (11.2%)
# 
#   Bottom 5 retention rates (non-null):
#     unitid=110918, retention_rate=0.00
#     unitid=118143, retention_rate=0.00
#     unitid=122454, retention_rate=0.00
#     unitid=143181, retention_rate=0.00
#     unitid=143552, retention_rate=0.00
# 
#   Top 5 retention rates (non-null):
#     unitid=101365, retention_rate=100.00
#     unitid=101453, retention_rate=100.00
#     unitid=103945, retention_rate=100.00
#     unitid=103954, retention_rate=100.00
#     unitid=111054, retention_rate=100.00
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_retention_clean.parquet
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values remaining: 0
#   [PASS] retention_rate range 0-100: min=0.00, max=100.00
#   [PASS] Null rate < 30%: 11.2% (654 nulls)
#   [PASS] Rows preserved: 5,836 -> 5,836
#   [PASS] Row count matches expected: 5,836 == 5,836
#   [PASS] Suppression rate < 50%: 11.2%
#   [PASS] Mean retention plausible: 70.65%
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
# 
# Deviation: Converted retention_rate from 0-1 to 0-100 scale (Plan assumed 0-100)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
