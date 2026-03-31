#!/usr/bin/env python3
"""
Stage 6.6: Clean IPEDS Student-Faculty Ratio data.

Task: clean-sfr
Wave: 2, Step: 6, Stage: 6
Depends on: fetch-sfr (Stage 5)
Input: data/raw/2026-03-29_ipeds_sfr.parquet
Output: data/processed/2026-03-29_sfr_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# INTENT: Configure paths and cleaning parameters for IPEDS SFR data.
# REASONING: IPEDS numeric fields use coded missing values (-1, -2, -3) per
# Education Data Portal conventions. These must be replaced with null before
# any statistical computation. student_faculty_ratio is stored as Int64 in the
# raw data (integer truncation from source); we cast to Float64 for downstream
# analysis compatibility.
# ASSUMES: Raw data exists from Stage 5 fetch at the specified path.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_sfr.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfr_clean.parquet"

# REASONING: Education Data Portal uses integer sentinel values for missing data.
# -1 = Missing/not reported, -2 = Not applicable, -3 = Suppressed for privacy.
# Stage 5 QA found no coded values in this dataset, but we still check defensively.
CODED_MISSING = [-1, -2, -3]

# REASONING: SFR values must be positive and non-zero to be meaningful.
# Values > 100 are flagged as WARN per Plan Task 4.1 specification (one outlier
# at 110 was noted in Stage 5 QA).
SFR_VALID_MIN = 1
SFR_VALID_MAX = 100  # Flag threshold, not hard filter

# --- Load ---
print("=" * 60)
print("Stage 6.6: Clean IPEDS Student-Faculty Ratio")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Types: {df.dtypes}")

# --- Pre-state ---
# INTENT: Capture state before any cleaning for validation comparison.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_sfr_nulls = df["student_faculty_ratio"].null_count()
pre_sfr_dtype = df["student_faculty_ratio"].dtype
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"  student_faculty_ratio dtype: {pre_sfr_dtype}")
print(f"  student_faculty_ratio nulls: {pre_sfr_nulls}")
print(f"  unitid nulls: {df['unitid'].null_count()}")
print(f"  unitid unique: {df['unitid'].n_unique()}")

# Check for coded missing values before replacement
coded_counts = {}
for code in CODED_MISSING:
    count = df.filter(pl.col("student_faculty_ratio") == code).height
    if count > 0:
        coded_counts[code] = count
if coded_counts:
    print(f"  Coded values found: {coded_counts}")
else:
    print("  No coded missing values (-1, -2, -3) found in student_faculty_ratio")

# Check for zeros
zero_count = df.filter(pl.col("student_faculty_ratio") == 0).height
print(f"  Zeros in student_faculty_ratio: {zero_count}")

# Check for negative values (other than coded)
neg_count = df.filter(
    (pl.col("student_faculty_ratio") < 0)
    & (~pl.col("student_faculty_ratio").is_in(CODED_MISSING))
).height
print(f"  Other negative values: {neg_count}")

# --- Clean Step 1: Replace coded missing values with null ---
# INTENT: Replace IPEDS coded missing values (-1, -2, -3) with null in
# student_faculty_ratio so they don't corrupt downstream statistics.
# REASONING: Even though Stage 5 QA found no coded values, this is a defensive
# measure. The cost of checking is negligible; the cost of missing one is not.
# ASSUMES: Coded values are exactly -1, -2, -3 per Education Data Portal docs.
raw_df = df.clone()

df = df.with_columns(
    pl.when(pl.col("student_faculty_ratio").is_in(CODED_MISSING))
    .then(None)
    .otherwise(pl.col("student_faculty_ratio"))
    .alias("student_faculty_ratio")
)
print("\nStep 1: Replaced coded missing values with null")

# --- Clean Step 2: Cast student_faculty_ratio to Float64 ---
# INTENT: Cast from Int64 to Float64 for downstream analysis compatibility.
# REASONING: Source stores SFR as Int64 (integer truncation). Float64 is needed
# for regression and correlation analysis in Stage 8. The integer truncation
# means precision is limited to whole numbers regardless of cast.
# ASSUMES: All non-null values are valid integers that can be safely cast.
df = df.with_columns(
    pl.col("student_faculty_ratio").cast(pl.Float64)
)
print(f"Step 2: Cast student_faculty_ratio to Float64 (was {pre_sfr_dtype})")

# --- Clean Step 3: Filter to positive, non-null SFR ---
# INTENT: Remove rows where student_faculty_ratio is zero, negative, or null.
# REASONING: Zero SFR is not meaningful (would imply no students or no faculty
# reported). Null values (including those from coded value replacement) cannot
# contribute to analysis. Positive values only are retained.
# ASSUMES: A ratio of 0 is a data quality issue, not a real measurement.
pre_filter_rows = df.shape[0]

df = df.filter(
    pl.col("student_faculty_ratio").is_not_null()
    & (pl.col("student_faculty_ratio") > 0)
)
filtered_out = pre_filter_rows - df.shape[0]
print(f"Step 3: Filtered to SFR > 0 and not null (removed {filtered_out} rows)")

# --- Clean Step 4: Validate range and flag outliers ---
# INTENT: Flag any SFR > 100 as a warning per Plan specification.
# REASONING: SFR values typically range 1-30. Values > 100 are unusual and may
# indicate data quality issues. Stage 5 QA noted one outlier at 110. We flag
# but do not remove these outliers per Plan Task 4.1.
# ASSUMES: The 100 threshold is a reasonable boundary for flagging.
outliers_above_100 = df.filter(pl.col("student_faculty_ratio") > SFR_VALID_MAX)
if outliers_above_100.height > 0:
    print(f"\n[WARN] {outliers_above_100.height} rows with SFR > {SFR_VALID_MAX}:")
    for row in outliers_above_100.iter_rows(named=True):
        print(f"  unitid={row['unitid']}, SFR={row['student_faculty_ratio']}")
else:
    print(f"\nNo outliers above {SFR_VALID_MAX}")

below_min = df.filter(pl.col("student_faculty_ratio") < SFR_VALID_MIN)
if below_min.height > 0:
    print(f"[WARN] {below_min.height} rows with SFR < {SFR_VALID_MIN}")

# --- Clean Step 5: Select final columns ---
# INTENT: Select only unitid and student_faculty_ratio for the clean output.
# REASONING: Downstream joins will merge on unitid. Only the SFR variable is
# needed from this dataset; other columns (year, etc.) are not required per Plan.
# ASSUMES: unitid is present and will serve as the join key in Stage 7.
df = df.select(["unitid", "student_faculty_ratio"])
print(f"\nStep 5: Selected columns: {df.columns}")

# --- Post-state ---
post_rows = df.shape[0]
post_cols = df.columns.copy()
post_sfr_dtype = df["student_faculty_ratio"].dtype
post_sfr_nulls = df["student_faculty_ratio"].null_count()
post_unitid_nulls = df["unitid"].null_count()
post_unitid_unique = df["unitid"].n_unique()

print(f"\nPost-state: {post_rows:,} rows, {len(post_cols)} cols")
print(f"  student_faculty_ratio dtype: {post_sfr_dtype}")
print(f"  student_faculty_ratio nulls: {post_sfr_nulls}")
print(f"  unitid nulls: {post_unitid_nulls}")
print(f"  unitid unique: {post_unitid_unique}")
print(f"  Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# SFR distribution summary
print(f"\n  SFR distribution:")
print(f"    min:    {df['student_faculty_ratio'].min()}")
print(f"    p25:    {df['student_faculty_ratio'].quantile(0.25)}")
print(f"    median: {df['student_faculty_ratio'].quantile(0.50)}")
print(f"    p75:    {df['student_faculty_ratio'].quantile(0.75)}")
print(f"    max:    {df['student_faculty_ratio'].max()}")
print(f"    mean:   {df['student_faculty_ratio'].mean():.1f}")

# --- Save ---
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning -- confirm coded values removed,
# suppression rates within tolerance, data loss acceptable, and output valid.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True

# CP2.1: Data loss check
loss_rate = (pre_rows - post_rows) / pre_rows if pre_rows > 0 else 0
print(f"\nData Loss:")
print(f"  Raw rows:     {pre_rows:,}")
print(f"  Clean rows:   {post_rows:,}")
print(f"  Rows removed: {pre_rows - post_rows:,} ({loss_rate:.1%})")

if loss_rate > 0.9:
    print(f"[FAIL] Data loss rate {loss_rate:.1%} exceeds 90%")
    cp2_passed = False
elif loss_rate > 0.5:
    print(f"[WARN] High data loss rate: {loss_rate:.1%}")
else:
    print(f"[PASS] Data loss rate {loss_rate:.1%} within tolerance")

# CP2.2: No coded values remain
coded_remaining = 0
for code in CODED_MISSING:
    count = df.filter(pl.col("student_faculty_ratio") == code).height
    coded_remaining += count

no_coded = coded_remaining == 0
print(f"\n[{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")

if not no_coded:
    cp2_passed = False

# CP2.3: Row count in expected range (3,000-6,000 per Plan)
row_count_ok = 3000 <= post_rows <= 6000
print(f"[{'PASS' if row_count_ok else 'FAIL'}] Row count in range [3000, 6000]: {post_rows:,}")

if not row_count_ok:
    cp2_passed = False

# CP2.4: All SFR values > 0
all_positive = df.filter(pl.col("student_faculty_ratio") <= 0).height == 0
print(f"[{'PASS' if all_positive else 'FAIL'}] All SFR values > 0")

if not all_positive:
    cp2_passed = False

# CP2.5: No nulls in student_faculty_ratio (after filter)
no_sfr_nulls = post_sfr_nulls == 0
print(f"[{'PASS' if no_sfr_nulls else 'FAIL'}] No nulls in student_faculty_ratio: {post_sfr_nulls}")

if not no_sfr_nulls:
    cp2_passed = False

# CP2.6: No nulls in unitid
no_unitid_nulls = post_unitid_nulls == 0
print(f"[{'PASS' if no_unitid_nulls else 'FAIL'}] No nulls in unitid: {post_unitid_nulls}")

if not no_unitid_nulls:
    cp2_passed = False

# CP2.7: unitid is unique (one row per institution)
unitid_unique = post_unitid_unique == post_rows
print(f"[{'PASS' if unitid_unique else 'FAIL'}] unitid is unique: {post_unitid_unique:,} unique vs {post_rows:,} rows")

if not unitid_unique:
    cp2_passed = False

# CP2.8: dtype is Float64
dtype_ok = post_sfr_dtype == pl.Float64
print(f"[{'PASS' if dtype_ok else 'FAIL'}] student_faculty_ratio dtype is Float64: {post_sfr_dtype}")

if not dtype_ok:
    cp2_passed = False

# CP2.9: Output file exists on disk
output_exists = OUTPUT_PATH.exists()
output_size = OUTPUT_PATH.stat().st_size if output_exists else 0
print(f"[{'PASS' if output_exists else 'FAIL'}] Output file exists: {OUTPUT_PATH} ({output_size:,} bytes)")

if not output_exists:
    cp2_passed = False

print(f"\n{'=' * 60}")
print(f"CP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print(f"{'=' * 60}")

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")



# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:22:17
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage6_clean/06_clean-sfr.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.6: Clean IPEDS Student-Faculty Ratio
# ============================================================
# Loaded: 5,836 rows x 4 cols
# Columns: ['unitid', 'year', 'fips', 'student_faculty_ratio']
# Types: [Int64, Int64, Int64, Int64]
# 
# Pre-state: 5,836 rows, 4 cols
#   student_faculty_ratio dtype: Int64
#   student_faculty_ratio nulls: 1
#   unitid nulls: 0
#   unitid unique: 5836
#   No coded missing values (-1, -2, -3) found in student_faculty_ratio
#   Zeros in student_faculty_ratio: 0
#   Other negative values: 0
# 
# Step 1: Replaced coded missing values with null
# Step 2: Cast student_faculty_ratio to Float64 (was Int64)
# Step 3: Filtered to SFR > 0 and not null (removed 1 rows)
# 
# [WARN] 1 rows with SFR > 100:
#   unitid=246035, SFR=110.0
# 
# Step 5: Selected columns: ['unitid', 'student_faculty_ratio']
# 
# Post-state: 5,835 rows, 2 cols
#   student_faculty_ratio dtype: Float64
#   student_faculty_ratio nulls: 0
#   unitid nulls: 0
#   unitid unique: 5835
#   Row change: -1 (-0.0%)
# 
#   SFR distribution:
#     min:    1.0
#     p25:    10.0
#     median: 14.0
#     p75:    19.0
#     max:    110.0
#     mean:   15.1
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_sfr_clean.parquet
# 
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
# 
# Data Loss:
#   Raw rows:     5,836
#   Clean rows:   5,835
#   Rows removed: 1 (0.0%)
# [PASS] Data loss rate 0.0% within tolerance
# 
# [PASS] No coded values remaining: 0
# [PASS] Row count in range [3000, 6000]: 5,835
# [PASS] All SFR values > 0
# [PASS] No nulls in student_faculty_ratio: 0
# [PASS] No nulls in unitid: 0
# [PASS] unitid is unique: 5,835 unique vs 5,835 rows
# [PASS] student_faculty_ratio dtype is Float64: Float64
# [PASS] Output file exists: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_sfr_clean.parquet (13,148 bytes)
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
