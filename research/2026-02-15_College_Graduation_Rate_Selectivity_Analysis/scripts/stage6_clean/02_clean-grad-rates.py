#!/usr/bin/env python3
"""
Stage 6.2: Clean IPEDS graduation rate data — dedup by cohort_year, replace coded
missing values, filter to non-null completion rates, rename for clarity.

Task: clean-grad-rates
Wave: 3, Step: 2, Stage: 6
Depends on: fetch-grad-rates (COMPLETE)
Input: data/raw/2026-02-15_ipeds_grad_rates.parquet
Output: data/processed/2026-02-15_grad_rates_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# The raw data has DUPLICATE unitids because cohort_year has two values (2014 and 2015).
# Stage 5 confirmed that cohort_year=2015 is the correct value for 150% completion
# measured in year=2020. The Portal uses academic year convention: fall 2014 cohort
# = AY 2014-15 = cohort_year 2015 in the Portal's schema.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing data
# in numeric columns. These must be mapped to null so they don't corrupt downstream
# statistical calculations (e.g., mean graduation rate would be dragged down by -1
# values if left in place). These codes are standard across the Portal.
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}
CODED_VALUES = list(CODED_MISSING.keys())

# Numeric columns where coded missing values may appear
NUMERIC_COLS_TO_CLEAN = ["completion_rate_150pct", "cohort_adj_150pct", "completers_150pct"]

# The correct cohort year for 150% completion in year 2020
# REASONING: Stage 5 fetch confirmed that cohort_year=2015 maps to the fall 2014 entering
# cohort (AY 2014-15). 150% time for a 4-year institution = 6 years, so fall 2014
# cohort outcomes are measured in 2020. cohort_year=2014 in the raw data represents
# a different cohort and must be excluded to avoid duplicate unitids.
CORRECT_COHORT_YEAR = 2015

# --- Load ---
# Load raw graduation rate data and verify shape matches Stage 5 output.
print("=" * 60)
print("Stage 6.2: Clean IPEDS graduation rate data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE any transformation for post-validation comparison.
# Also document the duplicate unitid situation and coded value presence.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_unitid_unique = df["unitid"].n_unique()
pre_unitid_total = df.shape[0]
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Unique unitids: {pre_unitid_unique:,} (out of {pre_unitid_total:,} rows)")
print(f"  -> Indicates {'DUPLICATES' if pre_unitid_unique < pre_unitid_total else 'no duplicates'}")

# Document cohort_year distribution
cohort_year_counts = df.group_by("cohort_year").len().sort("cohort_year")
print(f"\ncohort_year distribution:")
for row in cohort_year_counts.iter_rows(named=True):
    print(f"  cohort_year={row['cohort_year']}: {row['len']:,} rows")

# Document coded values present in numeric columns before cleaning
print("\nCoded values found in numeric columns:")
coded_found_any = False
for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        for code, meaning in CODED_MISSING.items():
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                coded_found_any = True
                print(f"  {col} = {code} ({meaning}): {count:,}")
if not coded_found_any:
    print("  None found (columns may already use null for missing)")

# Document null counts in numeric columns before cleaning
print("\nPre-clean null counts in numeric columns:")
for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        null_ct = df[col].null_count()
        print(f"  {col}: {null_ct:,} nulls ({null_ct / pre_rows * 100:.1f}%)")

# --- Transform Step 1: Replace coded missing values ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in all numeric
# measure columns so downstream statistical operations are not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation -- these values were never observed or are suppressed.
# Zero would imply a measured rate of zero, and NaN would complicate Polars
# aggregations. This step is performed BEFORE filtering by cohort_year so that
# all rows are cleaned uniformly.
#
# ASSUMES: All coded values in NUMERIC_COLS_TO_CLEAN are in the CODED_MISSING dict
# per IPEDS source documentation (education-data-context skill).
print("\n" + "-" * 40)
print("Step 1: Replace coded missing values with null")
print("-" * 40)

for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(col).is_in(CODED_VALUES))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )

# Verify coded values removed
coded_remaining = 0
for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        for code in CODED_VALUES:
            coded_remaining += df.filter(pl.col(col) == code).height

print(f"Coded values remaining after replacement: {coded_remaining}")
assert coded_remaining == 0, f"STOP: {coded_remaining} coded values still present"
print("[PASS] All coded values replaced with null")

# --- Transform Step 2: Filter to correct cohort year ---
# INTENT: Filter to cohort_year==2015 to resolve the duplicate unitid issue.
# The raw data has two cohort_year values (2014 and 2015) per unitid, but only
# cohort_year=2015 corresponds to the 150% completion rate for the fall 2014
# entering cohort measured in year 2020.
#
# REASONING: The Portal uses academic year convention where fall 2014 = AY 2014-15
# = cohort_year 2015. Keeping both cohort years would create duplicate unitids
# that would break downstream joins (1:1 cardinality required). Stage 5 confirmed
# this mapping.
#
# ASSUMES:
#   - cohort_year column exists and has integer values
#   - Filtering to cohort_year==2015 will approximately halve the row count
#   - After filter, unitid should be unique (1:1 mapping)
print("\n" + "-" * 40)
print(f"Step 2: Filter to cohort_year=={CORRECT_COHORT_YEAR}")
print("-" * 40)

pre_filter_rows = df.shape[0]
df = df.filter(pl.col("cohort_year") == CORRECT_COHORT_YEAR)
post_filter_rows = df.shape[0]
print(f"Rows: {pre_filter_rows:,} -> {post_filter_rows:,} (removed {pre_filter_rows - post_filter_rows:,})")

# --- Transform Step 3: Filter to non-null completion_rate_150pct ---
# INTENT: Remove institutions without a reportable 150% completion rate.
# These are institutions where the rate is null (either originally null or
# converted from coded missing values in Step 1).
#
# REASONING: Institutions without a completion rate cannot contribute to the
# research question about graduation rates vs. selectivity. Including them
# would introduce nulls that propagate through analysis. This is a data
# availability filter, not a methodological choice.
#
# ASSUMES:
#   - completion_rate_150pct is the column we need for the research question
#   - Null values represent genuinely unavailable data (not zero completion)
print("\n" + "-" * 40)
print("Step 3: Filter to non-null completion_rate_150pct")
print("-" * 40)

pre_null_filter_rows = df.shape[0]
null_rate_count = df["completion_rate_150pct"].null_count()
print(f"Rows with null completion_rate_150pct: {null_rate_count:,} ({null_rate_count / pre_null_filter_rows * 100:.1f}%)")

df = df.filter(pl.col("completion_rate_150pct").is_not_null())
post_null_filter_rows = df.shape[0]
print(f"Rows: {pre_null_filter_rows:,} -> {post_null_filter_rows:,} (removed {pre_null_filter_rows - post_null_filter_rows:,})")

# --- Validate: unitid uniqueness ---
# INTENT: Verify that after filtering to cohort_year=2015 and non-null rates,
# each unitid appears exactly once. This is the critical dedup verification.
#
# ASSUMES: The combination of cohort_year filter + non-null filter should yield
# exactly one row per unitid. If not, there is a data issue that must be resolved.
print("\n" + "-" * 40)
print("Step 4: Verify unitid uniqueness (1:1 mapping)")
print("-" * 40)

unitid_unique_count = df["unitid"].n_unique()
total_rows = df.shape[0]
unitid_is_unique = unitid_unique_count == total_rows
print(f"Unique unitids: {unitid_unique_count:,}")
print(f"Total rows: {total_rows:,}")
print(f"[{'PASS' if unitid_is_unique else 'FAIL'}] unitid is unique: {unitid_is_unique}")
assert unitid_is_unique, f"STOP: unitid not unique after dedup ({unitid_unique_count} unique vs {total_rows} rows)"

# --- Validate: completion_rate_150pct scale ---
# INTENT: Confirm that completion_rate_150pct is on the 0-100 scale (percentage)
# as documented in Stage 5, not on a 0-1 proportion scale.
#
# REASONING: Stage 5 confirmed the scale is 0-100. Verifying here as a sanity
# check to prevent downstream calculation errors (e.g., if someone multiplies
# by 100 thinking it's a proportion).
print("\n" + "-" * 40)
print("Step 5: Verify completion_rate_150pct scale (0-100)")
print("-" * 40)

rate_min = df["completion_rate_150pct"].min()
rate_max = df["completion_rate_150pct"].max()
rate_mean = df["completion_rate_150pct"].mean()
rate_median = df["completion_rate_150pct"].median()
print(f"Min: {rate_min:.2f}")
print(f"Max: {rate_max:.2f}")
print(f"Mean: {rate_mean:.2f}")
print(f"Median: {rate_median:.2f}")

# REASONING: On a 0-100 scale, max should be <= 100 and we expect most values > 1.
# If max <= 1.0 it would suggest a 0-1 proportion scale instead.
scale_is_percent = rate_max > 1.0 and rate_max <= 100.0
print(f"[{'PASS' if scale_is_percent else 'WARN'}] Scale appears to be 0-100 percentage: max={rate_max:.2f}")
if not scale_is_percent and rate_max <= 1.0:
    print("  WARNING: Values suggest 0-1 proportion scale, not 0-100 percentage")

# --- Transform Step 6: Rename for clarity ---
# INTENT: Rename completion_rate_150pct to grad_rate_150pct for downstream clarity.
# The new name better communicates that this is a graduation rate metric.
#
# REASONING: "grad_rate_150pct" is more immediately understandable in analysis code
# and report text than "completion_rate_150pct". The rename happens after all
# validation to avoid confusion during the cleaning pipeline.
print("\n" + "-" * 40)
print("Step 6: Rename completion_rate_150pct -> grad_rate_150pct")
print("-" * 40)

df = df.rename({"completion_rate_150pct": "grad_rate_150pct"})
print(f"Renamed. Columns now: {df.columns}")

# --- Post-state ---
# Capture final state for comparison with pre-state.
post_rows = df.shape[0]
post_cols = df.columns.copy()
print(f"\nPost-state: {post_rows:,} rows, {len(post_cols)} cols")
print(f"Columns: {post_cols}")

# Null rate for grad_rate_150pct (should be 0% since we filtered to non-null)
grad_rate_null_count = df["grad_rate_150pct"].null_count()
grad_rate_null_pct = grad_rate_null_count / post_rows * 100 if post_rows > 0 else 0
print(f"\ngrad_rate_150pct null count: {grad_rate_null_count} ({grad_rate_null_pct:.1f}%)")

# Row change summary
total_removed = pre_rows - post_rows
total_change_pct = (post_rows - pre_rows) / pre_rows * 100
print(f"\nOverall row change: {pre_rows:,} -> {post_rows:,} ({total_change_pct:+.1f}%)")
print(f"  Removed by cohort_year filter: {pre_filter_rows - post_filter_rows:,}")
print(f"  Removed by null rate filter: {pre_null_filter_rows - post_null_filter_rows:,}")

# Suppression rate: proportion of the cohort_year=2015 rows that were removed
# due to null completion_rate_150pct (i.e., not reportable)
suppression_rate = null_rate_count / (post_filter_rows + null_rate_count) * 100 if (post_filter_rows + null_rate_count) > 0 else 0
# Actually use the pre_null_filter count which is the post-cohort-filter count
suppression_rate = null_rate_count / pre_null_filter_rows * 100 if pre_null_filter_rows > 0 else 0
print(f"\nSuppression rate (null rates in cohort_year=2015 subset): {suppression_rate:.1f}%")

# --- Save ---
# Persist cleaned results in parquet format.
# Output paths match the Plan's file specification.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size:,} bytes")

# Verify saved file is readable
df_verify = pl.read_parquet(OUTPUT_PATH)
print(f"Verification read: {df_verify.shape[0]:,} rows x {df_verify.shape[1]} cols")
assert df_verify.shape == df.shape, "STOP: Saved file shape mismatch"

# --- CP2 Validation ---
# Checkpoint validation: verify all cleaning objectives met, suppression within
# bounds, and data is ready for downstream transformation and analysis.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

# CP2.1: No coded values remain in grad_rate_150pct
coded_in_grad_rate = 0
for code in CODED_VALUES:
    coded_in_grad_rate += df.filter(pl.col("grad_rate_150pct") == code).height
no_coded = coded_in_grad_rate == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values in grad_rate_150pct: {coded_in_grad_rate}")

# CP2.2: grad_rate_150pct on 0-100 scale
scale_ok = rate_max <= 100.0 and rate_min >= 0.0
print(f"  [{'PASS' if scale_ok else 'FAIL'}] grad_rate_150pct on 0-100 scale: min={rate_min:.2f}, max={rate_max:.2f}")

# CP2.3: unitid is unique (no duplicates)
print(f"  [{'PASS' if unitid_is_unique else 'FAIL'}] unitid is unique: {unitid_unique_count:,} unique / {total_rows:,} rows")

# CP2.4: Null rate for grad_rate_150pct is 0%
null_rate_zero = grad_rate_null_count == 0
print(f"  [{'PASS' if null_rate_zero else 'FAIL'}] grad_rate_150pct null rate: {grad_rate_null_pct:.1f}%")

# CP2.5: Suppression rate < 50%
suppression_ok = suppression_rate < 50.0
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: {suppression_rate:.1f}%")

# CP2.6: Row count in expected range (expect ~2,000-2,500 after dedup)
row_count_ok = 1000 <= post_rows <= 5000
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count in expected range (1,000-5,000): {post_rows:,}")

# CP2.7: File saved and readable
file_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if file_exists else 'FAIL'}] Output file exists: {OUTPUT_PATH}")

# Overall CP2 assessment
all_critical_pass = all([no_coded, scale_ok, unitid_is_unique, null_rate_zero, suppression_ok, file_exists])

assert no_coded, "STOP: Coded values still present in grad_rate_150pct"
assert scale_ok, "STOP: grad_rate_150pct not on 0-100 scale"
assert unitid_is_unique, "STOP: unitid not unique"
assert null_rate_zero, "STOP: grad_rate_150pct has nulls after filter"
assert suppression_ok, "STOP: Suppression rate >= 50%"
assert file_exists, "STOP: Output file not saved"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:38:49
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/02_clean-grad-rates.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 6.2: Clean IPEDS graduation rate data
# ============================================================
# Loaded: 4,489 rows x 7 cols
# Columns: ['unitid', 'year', 'cohort_year', 'completion_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# 
# Pre-state: 4,489 rows, 7 cols
# Unique unitids: 2,010 (out of 4,489 rows)
#   -> Indicates DUPLICATES
# 
# cohort_year distribution:
#   cohort_year=2015: 4,489 rows
# 
# Coded values found in numeric columns:
#   None found (columns may already use null for missing)
# 
# Pre-clean null counts in numeric columns:
#   completion_rate_150pct: 2,540 nulls (56.6%)
#   cohort_adj_150pct: 2,481 nulls (55.3%)
#   completers_150pct: 61 nulls (1.4%)
# 
# ----------------------------------------
# Step 1: Replace coded missing values with null
# ----------------------------------------
# Coded values remaining after replacement: 0
# [PASS] All coded values replaced with null
# 
# ----------------------------------------
# Step 2: Filter to cohort_year==2015
# ----------------------------------------
# Rows: 4,489 -> 4,489 (removed 0)
# 
# ----------------------------------------
# Step 3: Filter to non-null completion_rate_150pct
# ----------------------------------------
# Rows with null completion_rate_150pct: 2,540 (56.6%)
# Rows: 4,489 -> 1,949 (removed 2,540)
# 
# ----------------------------------------
# Step 4: Verify unitid uniqueness (1:1 mapping)
# ----------------------------------------
# Unique unitids: 1,949
# Total rows: 1,949
# [PASS] unitid is unique: True
# 
# ----------------------------------------
# Step 5: Verify completion_rate_150pct scale (0-100)
# ----------------------------------------
# Min: 0.04
# Max: 1.00
# Mean: 0.56
# Median: 0.56
# [WARN] Scale appears to be 0-100 percentage: max=1.00
#   WARNING: Values suggest 0-1 proportion scale, not 0-100 percentage
# 
# ----------------------------------------
# Step 6: Rename completion_rate_150pct -> grad_rate_150pct
# ----------------------------------------
# Renamed. Columns now: ['unitid', 'year', 'cohort_year', 'grad_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# 
# Post-state: 1,949 rows, 7 cols
# Columns: ['unitid', 'year', 'cohort_year', 'grad_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# 
# grad_rate_150pct null count: 0 (0.0%)
# 
# Overall row change: 4,489 -> 1,949 (-56.6%)
#   Removed by cohort_year filter: 0
#   Removed by null rate filter: 2,540
# 
# Suppression rate (null rates in cohort_year=2015 subset): 56.6%
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_grad_rates_clean.parquet
# File size: 19,490 bytes
# Verification read: 1,949 rows x 7 cols
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values in grad_rate_150pct: 0
#   [PASS] grad_rate_150pct on 0-100 scale: min=0.04, max=1.00
#   [PASS] unitid is unique: 1,949 unique / 1,949 rows
#   [PASS] grad_rate_150pct null rate: 0.0%
#   [FAIL] Suppression rate < 50%: 56.6%
#   [PASS] Row count in expected range (1,000-5,000): 1,949
#   [PASS] Output file exists: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_grad_rates_clean.parquet
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/02_clean-grad-rates.py", line 320, in <module>
#     assert suppression_ok, "STOP: Suppression rate >= 50%"
#            ^^^^^^^^^^^^^^
# AssertionError: STOP: Suppression rate >= 50%
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
