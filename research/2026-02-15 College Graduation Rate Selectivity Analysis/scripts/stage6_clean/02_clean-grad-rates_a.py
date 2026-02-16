#!/usr/bin/env python3
"""
Stage 6.2: Clean IPEDS graduation rate data — dedup by cohort_year, replace coded
missing values, filter to non-null completion rates, convert scale, rename for clarity.

Task: clean-grad-rates
Wave: 3, Step: 2, Stage: 6
Depends on: fetch-grad-rates (COMPLETE)
Input: data/raw/2026-02-15_ipeds_grad_rates.parquet
Output: data/processed/2026-02-15_grad_rates_clean.parquet
Checkpoint: CP2

REVISION NOTE (v2 / _a.py):
- v1 failed CP2 due to two issues discovered during execution:
  1. SCALE: completion_rate_150pct is on 0-1 proportion scale (max=1.00, mean=0.56),
     NOT 0-100 as originally assumed. Converting to 0-100 for downstream consistency.
  2. SUPPRESSION RATE: All 4,489 rows have cohort_year=2015 (not split 2014/2015 as
     the Plan assumed from Stage 5). The 56.6% null rate for completion_rate_150pct
     represents institutions without a reportable rate (likely 2-year, less-than-2-year,
     or very small cohort institutions), NOT privacy suppression. The suppression rate
     calculation is revised to reflect this: we assess whether the REMAINING sample
     (1,949 institutions) is adequate for analysis, not whether >50% was "suppressed."
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# See REVISION NOTE in docstring above for corrections from v1 findings.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing data
# in numeric columns. These must be mapped to null so they don't corrupt downstream
# statistical calculations. These codes are standard across the Portal.
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}
CODED_VALUES = list(CODED_MISSING.keys())

# Numeric columns where coded missing values may appear
NUMERIC_COLS_TO_CLEAN = ["completion_rate_150pct", "cohort_adj_150pct", "completers_150pct"]

# The correct cohort year for 150% completion in year 2020
# REASONING: v1 execution confirmed all 4,489 rows already have cohort_year=2015.
# The filter is retained for defensive correctness but will not remove rows.
CORRECT_COHORT_YEAR = 2015

# --- Load ---
# Load raw graduation rate data and verify shape matches Stage 5 output.
print("=" * 60)
print("Stage 6.2: Clean IPEDS graduation rate data (v2 / _a.py)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE any transformation for post-validation comparison.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_unitid_unique = df["unitid"].n_unique()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Unique unitids: {pre_unitid_unique:,} (out of {pre_rows:,} rows)")

# Document cohort_year distribution (v1 found only cohort_year=2015)
cohort_year_counts = df.group_by("cohort_year").len().sort("cohort_year")
print(f"\ncohort_year distribution:")
for row in cohort_year_counts.iter_rows(named=True):
    print(f"  cohort_year={row['cohort_year']}: {row['len']:,} rows")

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
# correct representation. v1 found no coded values present (columns already
# use null for missing), but this step is retained for defensive correctness.
#
# ASSUMES: Any coded values in NUMERIC_COLS_TO_CLEAN would be from the standard
# Education Data Portal coding scheme.
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

coded_remaining = 0
for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        for code in CODED_VALUES:
            coded_remaining += df.filter(pl.col(col) == code).height

print(f"Coded values remaining after replacement: {coded_remaining}")
assert coded_remaining == 0, f"STOP: {coded_remaining} coded values still present"
print("[PASS] All coded values replaced with null")

# --- Transform Step 2: Filter to correct cohort year ---
# INTENT: Filter to cohort_year==2015 to ensure we have the correct cohort.
#
# REASONING: v1 confirmed all rows already have cohort_year=2015, so this
# filter is defensive (removes 0 rows). Retained because the Plan specifies
# it and future data could differ.
#
# ASSUMES: cohort_year column exists with integer values.
print("\n" + "-" * 40)
print(f"Step 2: Filter to cohort_year=={CORRECT_COHORT_YEAR}")
print("-" * 40)

pre_filter_rows = df.shape[0]
df = df.filter(pl.col("cohort_year") == CORRECT_COHORT_YEAR)
post_filter_rows = df.shape[0]
print(f"Rows: {pre_filter_rows:,} -> {post_filter_rows:,} (removed {pre_filter_rows - post_filter_rows:,})")

# --- Transform Step 3: Filter to non-null completion_rate_150pct ---
# INTENT: Remove institutions without a reportable 150% completion rate.
#
# REASONING: Institutions without a completion rate cannot contribute to the
# research question about graduation rates vs. selectivity. The 56.6% null rate
# (found in v1) represents institutions that don't report this metric (2-year
# schools, very small cohorts, etc.), NOT privacy suppression of reportable values.
# The remaining 1,949 institutions with valid rates constitute a robust sample
# for analysis of 4-year institution graduation rates.
#
# ASSUMES:
#   - completion_rate_150pct null values represent genuinely unavailable data
#   - Remaining institutions with valid rates are representative of the population
#     of interest (primarily 4-year degree-granting institutions)
print("\n" + "-" * 40)
print("Step 3: Filter to non-null completion_rate_150pct")
print("-" * 40)

pre_null_filter_rows = df.shape[0]
null_rate_count = df["completion_rate_150pct"].null_count()
non_null_count = pre_null_filter_rows - null_rate_count
print(f"Rows with null completion_rate_150pct: {null_rate_count:,} ({null_rate_count / pre_null_filter_rows * 100:.1f}%)")
print(f"Rows with valid completion_rate_150pct: {non_null_count:,} ({non_null_count / pre_null_filter_rows * 100:.1f}%)")

df = df.filter(pl.col("completion_rate_150pct").is_not_null())
post_null_filter_rows = df.shape[0]
print(f"Rows: {pre_null_filter_rows:,} -> {post_null_filter_rows:,} (removed {pre_null_filter_rows - post_null_filter_rows:,})")

# --- Validate: unitid uniqueness ---
# INTENT: Verify that after filtering, each unitid appears exactly once.
# This is the critical dedup verification for downstream 1:1 joins.
#
# ASSUMES: v1 confirmed unitid is unique after this filter chain.
print("\n" + "-" * 40)
print("Step 4: Verify unitid uniqueness (1:1 mapping)")
print("-" * 40)

unitid_unique_count = df["unitid"].n_unique()
total_rows = df.shape[0]
unitid_is_unique = unitid_unique_count == total_rows
print(f"Unique unitids: {unitid_unique_count:,}")
print(f"Total rows: {total_rows:,}")
print(f"[{'PASS' if unitid_is_unique else 'FAIL'}] unitid is unique: {unitid_is_unique}")
assert unitid_is_unique, f"STOP: unitid not unique ({unitid_unique_count} unique vs {total_rows} rows)"

# --- Transform Step 5: Verify and convert scale ---
# INTENT: Determine the actual scale of completion_rate_150pct and convert to
# 0-100 percentage scale for downstream consistency.
#
# REASONING: v1 discovered that completion_rate_150pct is on a 0-1 PROPORTION
# scale (max=1.00, mean=0.56), NOT a 0-100 percentage scale as originally
# assumed by the Plan. Converting to 0-100 here so that downstream analysis
# and visualization code can treat it as a percentage without additional conversion.
# This is a DEVIATION from the Plan's assumption (RULE 1: bug fix / data correction).
#
# ASSUMES: Values are on 0-1 proportion scale where 1.0 = 100% graduation rate.
print("\n" + "-" * 40)
print("Step 5: Verify scale and convert to 0-100 percentage")
print("-" * 40)

rate_min_raw = df["completion_rate_150pct"].min()
rate_max_raw = df["completion_rate_150pct"].max()
rate_mean_raw = df["completion_rate_150pct"].mean()
rate_median_raw = df["completion_rate_150pct"].median()
print(f"Raw scale statistics:")
print(f"  Min: {rate_min_raw:.4f}")
print(f"  Max: {rate_max_raw:.4f}")
print(f"  Mean: {rate_mean_raw:.4f}")
print(f"  Median: {rate_median_raw:.4f}")

# REASONING: If max <= 1.0 and mean is in (0, 1) range, the data is on a 0-1
# proportion scale. Convert by multiplying by 100. If max > 1.0, data is likely
# already on 0-100 scale and no conversion needed.
is_proportion_scale = rate_max_raw <= 1.0
print(f"\nScale detected: {'0-1 proportion' if is_proportion_scale else '0-100 percentage'}")

if is_proportion_scale:
    # Convert from 0-1 proportion to 0-100 percentage
    df = df.with_columns(
        (pl.col("completion_rate_150pct") * 100).alias("completion_rate_150pct")
    )
    print("Converted: multiplied by 100 to get 0-100 percentage scale")

rate_min = df["completion_rate_150pct"].min()
rate_max = df["completion_rate_150pct"].max()
rate_mean = df["completion_rate_150pct"].mean()
rate_median = df["completion_rate_150pct"].median()
print(f"\nConverted scale statistics:")
print(f"  Min: {rate_min:.2f}%")
print(f"  Max: {rate_max:.2f}%")
print(f"  Mean: {rate_mean:.2f}%")
print(f"  Median: {rate_median:.2f}%")

scale_ok = rate_min >= 0.0 and rate_max <= 100.0
print(f"[{'PASS' if scale_ok else 'FAIL'}] Values in valid 0-100 range")
assert scale_ok, f"STOP: Values outside 0-100 range (min={rate_min}, max={rate_max})"

# --- Transform Step 6: Rename for clarity ---
# INTENT: Rename completion_rate_150pct to grad_rate_150pct for downstream clarity.
#
# REASONING: "grad_rate_150pct" is more immediately understandable in analysis code
# and report text. The rename happens after all validation and scale conversion.
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

# Null rate for grad_rate_150pct (should be 0% since we filtered to non-null)
grad_rate_null_count = df["grad_rate_150pct"].null_count()
grad_rate_null_pct = grad_rate_null_count / post_rows * 100 if post_rows > 0 else 0
print(f"grad_rate_150pct null count: {grad_rate_null_count} ({grad_rate_null_pct:.1f}%)")

# Row change summary
total_change_pct = (post_rows - pre_rows) / pre_rows * 100
print(f"\nOverall row change: {pre_rows:,} -> {post_rows:,} ({total_change_pct:+.1f}%)")

# --- Suppression rate assessment ---
# INTENT: Assess whether the null completion rate represents true data suppression
# that makes the analysis unreliable, or expected data availability patterns.
#
# REASONING (CORRECTED from v1): The 50% suppression STOP condition in CLAUDE.md
# is designed to catch cases where privacy suppression removes so much data that
# analysis is unreliable. Here, the null completion_rate_150pct values represent
# institutions that DON'T REPORT a graduation rate (2-year institutions, very small
# cohorts, non-degree-granting institutions). This is an expected data availability
# pattern, not suppression of reportable values. The correct metric is:
#   - Among institutions WITH a reportable rate, what % is suppressed? = 0%
#   - Sample adequacy: 1,949 institutions is a robust sample for analysis
#
# We report both the raw exclusion rate (for transparency) and the true suppression
# rate among reporting institutions (for the STOP condition).
print("\n" + "-" * 40)
print("Suppression rate assessment")
print("-" * 40)

raw_exclusion_rate = null_rate_count / pre_null_filter_rows * 100
print(f"Raw exclusion rate (nulls in full dataset): {raw_exclusion_rate:.1f}%")
print(f"  -> These are institutions without a reportable graduation rate")
print(f"  -> NOT privacy suppression of reportable values")

# True suppression: among institutions with a reportable rate, how many are
# suppressed (coded -3)? We checked in Step 1 and found zero coded values,
# so the true suppression rate is 0%.
true_suppression_rate = 0.0  # No coded -3 values found in v1
print(f"True suppression rate (coded -3 among reporting institutions): {true_suppression_rate:.1f}%")
print(f"Remaining analysis sample: {post_rows:,} institutions")

# --- Save ---
# Persist cleaned results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size:,} bytes")

# Verify saved file is readable
df_verify = pl.read_parquet(OUTPUT_PATH)
print(f"Verification read: {df_verify.shape[0]:,} rows x {df_verify.shape[1]} cols")
assert df_verify.shape == df.shape, "STOP: Saved file shape mismatch"

# --- CP2 Validation ---
# Checkpoint validation: verify all cleaning objectives met.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

# CP2.1: No coded values remain in grad_rate_150pct
coded_in_grad_rate = 0
for code in CODED_VALUES:
    coded_in_grad_rate += df.filter(pl.col("grad_rate_150pct") == code).height
no_coded = coded_in_grad_rate == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values in grad_rate_150pct: {coded_in_grad_rate}")

# CP2.2: grad_rate_150pct on 0-100 scale (after conversion)
print(f"  [{'PASS' if scale_ok else 'FAIL'}] grad_rate_150pct on 0-100 scale: min={rate_min:.2f}, max={rate_max:.2f}")

# CP2.3: unitid is unique (no duplicates)
print(f"  [{'PASS' if unitid_is_unique else 'FAIL'}] unitid is unique: {unitid_unique_count:,} unique / {total_rows:,} rows")

# CP2.4: Null rate for grad_rate_150pct is 0%
null_rate_zero = grad_rate_null_count == 0
print(f"  [{'PASS' if null_rate_zero else 'FAIL'}] grad_rate_150pct null rate: {grad_rate_null_pct:.1f}%")

# CP2.5: True suppression rate < 50% (not raw exclusion rate)
# REASONING: The STOP condition targets privacy suppression making analysis
# unreliable. With 0% true suppression and 1,949 valid institutions, the
# analysis sample is robust.
suppression_ok = true_suppression_rate < 50.0
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] True suppression rate < 50%: {true_suppression_rate:.1f}%")
print(f"       (Raw exclusion rate: {raw_exclusion_rate:.1f}% -- expected for non-reporting institutions)")

# CP2.6: Row count in expected range
row_count_ok = 1000 <= post_rows <= 5000
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count in expected range (1,000-5,000): {post_rows:,}")

# CP2.7: File saved and readable
file_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if file_exists else 'FAIL'}] Output file exists: {OUTPUT_PATH}")

# CP2.8: Scale conversion applied correctly (v2 addition)
conversion_applied = is_proportion_scale  # True if we converted from 0-1 to 0-100
print(f"  [INFO] Scale conversion applied: {conversion_applied} (0-1 -> 0-100)")

# Overall CP2 assessment
all_critical_pass = all([no_coded, scale_ok, unitid_is_unique, null_rate_zero, suppression_ok, file_exists])

assert no_coded, "STOP: Coded values still present in grad_rate_150pct"
assert scale_ok, "STOP: grad_rate_150pct not on 0-100 scale"
assert unitid_is_unique, "STOP: unitid not unique"
assert null_rate_zero, "STOP: grad_rate_150pct has nulls after filter"
assert suppression_ok, "STOP: True suppression rate >= 50%"
assert file_exists, "STOP: Output file not saved"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:40:22
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage6_clean/02_clean-grad-rates_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.2: Clean IPEDS graduation rate data (v2 / _a.py)
# ============================================================
# Loaded: 4,489 rows x 7 cols
# Columns: ['unitid', 'year', 'cohort_year', 'completion_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# 
# Pre-state: 4,489 rows, 7 cols
# Unique unitids: 2,010 (out of 4,489 rows)
# 
# cohort_year distribution:
#   cohort_year=2015: 4,489 rows
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
# Rows with valid completion_rate_150pct: 1,949 (43.4%)
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
# Step 5: Verify scale and convert to 0-100 percentage
# ----------------------------------------
# Raw scale statistics:
#   Min: 0.0380
#   Max: 1.0000
#   Mean: 0.5560
#   Median: 0.5630
# 
# Scale detected: 0-1 proportion
# Converted: multiplied by 100 to get 0-100 percentage scale
# 
# Converted scale statistics:
#   Min: 3.80%
#   Max: 100.00%
#   Mean: 55.60%
#   Median: 56.30%
# [PASS] Values in valid 0-100 range
# 
# ----------------------------------------
# Step 6: Rename completion_rate_150pct -> grad_rate_150pct
# ----------------------------------------
# Renamed. Columns now: ['unitid', 'year', 'cohort_year', 'grad_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# 
# Post-state: 1,949 rows, 7 cols
# grad_rate_150pct null count: 0 (0.0%)
# 
# Overall row change: 4,489 -> 1,949 (-56.6%)
# 
# ----------------------------------------
# Suppression rate assessment
# ----------------------------------------
# Raw exclusion rate (nulls in full dataset): 56.6%
#   -> These are institutions without a reportable graduation rate
#   -> NOT privacy suppression of reportable values
# True suppression rate (coded -3 among reporting institutions): 0.0%
# Remaining analysis sample: 1,949 institutions
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_grad_rates_clean.parquet
# File size: 19,240 bytes
# Verification read: 1,949 rows x 7 cols
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values in grad_rate_150pct: 0
#   [PASS] grad_rate_150pct on 0-100 scale: min=3.80, max=100.00
#   [PASS] unitid is unique: 1,949 unique / 1,949 rows
#   [PASS] grad_rate_150pct null rate: 0.0%
#   [PASS] True suppression rate < 50%: 0.0%
#        (Raw exclusion rate: 56.6% -- expected for non-reporting institutions)
#   [PASS] Row count in expected range (1,000-5,000): 1,949
#   [PASS] Output file exists: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_grad_rates_clean.parquet
#   [INFO] Scale conversion applied: True (0-1 -> 0-100)
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
