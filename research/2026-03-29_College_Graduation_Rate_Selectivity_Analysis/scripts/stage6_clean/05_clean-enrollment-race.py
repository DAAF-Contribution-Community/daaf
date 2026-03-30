#!/usr/bin/env python3
"""
Stage 6.5: Clean IPEDS Fall Enrollment Race data and compute URM share per institution.

Task: clean-enrollment-race
Wave: 2, Step: 5, Stage: 6
Depends on: fetch-enrollment-race (Stage 5)
Input: data/raw/2026-03-29_ipeds_enrollment_race.parquet
Output: data/processed/2026-03-29_urm_share_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for cleaning IPEDS Fall Enrollment Race data.
# The goal is to produce one row per institution (unitid) with urm_share and
# total_ug_enrollment. The raw data has 10 race codes per institution
# (5,837 institutions x 10 = 58,370 rows).
#
# Race code definitions (from Education Data Portal integer encoding):
#   1=White, 2=Black, 3=Hispanic, 4=Asian,
#   5=American Indian/Alaska Native (AIAN), 6=Native Hawaiian/Pacific Islander (NHPI),
#   7=Two or more races, 8=Nonresident alien, 9=Unknown, 99=Total
#
# URM definition per Plan: races 2 (Black), 3 (Hispanic), 5 (AIAN), 6 (NHPI)
# Domestic known-race denominator: races 1-7 (excludes 8=nonresident alien, 9=unknown, 99=total)
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_enrollment_race.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_urm_share_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data in numeric columns. These must be mapped to null so they don't corrupt
# enrollment sums. -1=missing, -2=not applicable, -3=suppressed.
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed"}

# URM race codes per Plan specification
URM_RACE_CODES = [2, 3, 5, 6]  # Black, Hispanic, AIAN, NHPI
DOMESTIC_KNOWN_RACE_CODES = [1, 2, 3, 4, 5, 6, 7]  # All domestic known-race categories
TOTAL_RACE_CODE = 99  # Total across all races

# Domain configuration for CP2
SUPPRESSION_CODE = -3
CODED_MISSING_VALUES = [-1, -2, -3]
SUPPRESSION_THRESHOLD = 0.5

# --- Load ---
# Load raw IPEDS Fall Enrollment Race data. This file was already filtered during
# fetch to sex==99 (total), ftpt==99 (total), level_of_study==1 (undergraduate),
# degree_seeking==99 (total), class_level==99 (total).
print("=" * 60)
print("Stage 6.5: Clean IPEDS Fall Enrollment Race")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# Capture state before any transformations for post-validation comparison.
# The raw data should have 58,370 rows (5,837 institutions x 10 race codes).
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Verify fetch-time filters are already applied
# INTENT: Confirm the data was pre-filtered during fetch so we don't need to
# re-apply demographic filters here. These filters collapse the data to one
# enrollment count per institution per race code.
# ASSUMES: sex, ftpt, level_of_study, degree_seeking, class_level columns exist
# and were filtered during Stage 5 fetch.
filter_cols = ["sex", "ftpt", "level_of_study"]
for col in filter_cols:
    if col in df.columns:
        unique_vals = sorted(df[col].unique().to_list())
        print(f"  {col} unique values: {unique_vals}")

# Check race code distribution
race_col = "race" if "race" in df.columns else None
if race_col:
    race_values = sorted(df[race_col].unique().to_list())
    print(f"  race unique values: {race_values}")
    n_institutions = df["unitid"].n_unique()
    print(f"  Unique institutions (unitid): {n_institutions:,}")
    print(f"  Rows per institution: {pre_rows / n_institutions:.1f}")

# Enumerate coded missing values in enrollment_fall before cleaning
# INTENT: Document the prevalence of coded missing values so we can verify
# they are all removed after cleaning.
enrollment_col = "enrollment_fall"
print(f"\nCoded values in {enrollment_col}:")
for code, meaning in CODED_MISSING.items():
    count = df.filter(pl.col(enrollment_col) == code).height
    print(f"  {code} ({meaning}): {count:,}")

# --- Clean ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in enrollment_fall.
# This prevents sentinel values from being included in enrollment sums, which would
# produce incorrect URM share calculations.
#
# REASONING: Using null (not zero) because these enrollment counts were never
# observed or were suppressed. Zero would imply the institution reported zero
# students of that race, which is a meaningful data point distinct from missing.
#
# ASSUMES: All coded missing values in enrollment_fall follow the Education Data
# Portal convention of -1/-2/-3.
raw_df = df.clone()  # Keep a reference for CP2 comparison

df = df.with_columns(
    pl.when(pl.col(enrollment_col).is_in(list(CODED_MISSING.keys())))
    .then(None)
    .otherwise(pl.col(enrollment_col))
    .alias(enrollment_col)
)
print(f"\nReplaced coded values with null in {enrollment_col}")

# Verify no coded values remain
for code in CODED_MISSING.keys():
    remaining = df.filter(pl.col(enrollment_col) == code).height
    assert remaining == 0, f"STOP: Coded value {code} still present ({remaining} rows)"
print("Verified: no coded values remain in enrollment_fall")

# --- Compute URM Share ---
# INTENT: Compute URM share per institution as:
#   urm_share = sum(enrollment for URM races) / sum(enrollment for domestic known races)
# This produces a proportion (0-1) representing the share of domestic known-race
# students who belong to underrepresented minority groups.
#
# REASONING: Using domestic known-race denominator (races 1-7) rather than total
# enrollment (race=99) because:
#   - Race=8 (nonresident alien) and race=9 (unknown) should not be in the denominator
#     when computing a share of domestic racial composition
#   - Race=99 (total) includes nonresident aliens and unknown, which would deflate
#     URM share at institutions with many international students
#   - This approach matches standard practice in higher education equity analysis
#
# ASSUMES:
#   - Each unitid has at most one row per race code (verified by balanced panel check)
#   - enrollment_fall with null has been handled (null excluded from sum by default in Polars)
#   - URM races: 2=Black, 3=Hispanic, 5=AIAN, 6=NHPI

# Step 1: Compute URM numerator per institution
# INTENT: Sum enrollment_fall for URM race codes (2, 3, 5, 6) per unitid.
urm_numerator = (
    df
    .filter(pl.col("race").is_in(URM_RACE_CODES))
    .group_by("unitid")
    .agg(pl.col(enrollment_col).sum().alias("urm_enrollment"))
)
print(f"\nURM numerator: {urm_numerator.shape[0]:,} institutions")

# Step 2: Compute domestic known-race denominator per institution
# INTENT: Sum enrollment_fall for all domestic known-race codes (1-7) per unitid.
domestic_denominator = (
    df
    .filter(pl.col("race").is_in(DOMESTIC_KNOWN_RACE_CODES))
    .group_by("unitid")
    .agg(pl.col(enrollment_col).sum().alias("domestic_known_enrollment"))
)
print(f"Domestic denominator: {domestic_denominator.shape[0]:,} institutions")

# Step 3: Extract total undergraduate enrollment per institution
# INTENT: Get the total enrollment (race=99) for each institution, which will be
# used downstream as the Pell share denominator.
# REASONING: race=99 represents the institution-reported total across all races
# including nonresident aliens and unknown. This is the correct base for Pell
# share because Pell Grants can be received by any enrolled student.
total_enrollment = (
    df
    .filter(pl.col("race") == TOTAL_RACE_CODE)
    .select(["unitid", pl.col(enrollment_col).alias("total_ug_enrollment")])
)
print(f"Total enrollment: {total_enrollment.shape[0]:,} institutions")

# Step 4: Join and compute URM share
# INTENT: Combine numerator, denominator, and total enrollment into a single
# row per institution, then compute urm_share as a proportion.
#
# REASONING: Using left join from total_enrollment as the base because every
# institution should have a race=99 row. URM and domestic enrollment may be
# null if all race-specific enrollment values were null/missing.
#
# ASSUMES: total_enrollment has one row per unitid (guaranteed by race==99 filter
# on a balanced panel where each institution has exactly one race=99 row).
result = (
    total_enrollment
    .join(urm_numerator, on="unitid", how="left")
    .join(domestic_denominator, on="unitid", how="left")
)

# INTENT: Compute urm_share as proportion, handling division by zero.
# REASONING: If domestic_known_enrollment is 0 or null, urm_share should be null
# rather than infinity or zero, because we genuinely don't know the URM composition.
result = result.with_columns(
    pl.when(pl.col("domestic_known_enrollment") > 0)
    .then(pl.col("urm_enrollment") / pl.col("domestic_known_enrollment"))
    .otherwise(None)
    .alias("urm_share")
)

# Keep only the columns needed downstream
result = result.select(["unitid", "urm_share", "total_ug_enrollment"])

print(f"\nResult: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Columns: {result.columns}")

# --- Post-state ---
# Capture post-transformation state for validation.
post_rows = result.shape[0]
print(f"\nPost-state: {post_rows:,} rows (one per institution)")

# URM share distribution
urm_non_null = result.filter(pl.col("urm_share").is_not_null())
urm_null_count = result.filter(pl.col("urm_share").is_null()).height
print(f"\nURM Share Distribution:")
print(f"  Non-null: {urm_non_null.height:,}")
print(f"  Null: {urm_null_count:,} ({urm_null_count / post_rows * 100:.1f}%)")
if urm_non_null.height > 0:
    print(f"  Mean:   {urm_non_null['urm_share'].mean():.4f}")
    print(f"  Median: {urm_non_null['urm_share'].median():.4f}")
    print(f"  Min:    {urm_non_null['urm_share'].min():.4f}")
    print(f"  Max:    {urm_non_null['urm_share'].max():.4f}")
    print(f"  Std:    {urm_non_null['urm_share'].std():.4f}")

# Total UG enrollment distribution
enrl_non_null = result.filter(pl.col("total_ug_enrollment").is_not_null())
enrl_null_count = result.filter(pl.col("total_ug_enrollment").is_null()).height
print(f"\nTotal UG Enrollment Distribution:")
print(f"  Non-null: {enrl_non_null.height:,}")
print(f"  Null: {enrl_null_count:,}")
if enrl_non_null.height > 0:
    print(f"  Mean:   {enrl_non_null['total_ug_enrollment'].mean():,.0f}")
    print(f"  Median: {enrl_non_null['total_ug_enrollment'].median():,.0f}")
    print(f"  Min:    {enrl_non_null['total_ug_enrollment'].min():,}")
    print(f"  Max:    {enrl_non_null['total_ug_enrollment'].max():,}")

# Verify unitid uniqueness
unitid_unique = result["unitid"].n_unique() == result.shape[0]
print(f"\nUnitid uniqueness: {unitid_unique} ({result['unitid'].n_unique():,} unique / {result.shape[0]:,} rows)")

# --- Save ---
# Persist results in parquet format. One row per institution with urm_share and
# total_ug_enrollment for downstream joins (Stage 7).
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists on disk
assert OUTPUT_PATH.exists(), f"STOP: Output file not found: {OUTPUT_PATH}"
file_size_kb = OUTPUT_PATH.stat().st_size / 1024
print(f"File size: {file_size_kb:.1f} KB")

# --- CP2 Validation ---
# Checkpoint validation: verify coded values removed, suppression rate acceptable,
# urm_share in valid range, unitid is unique, and row count is within expected bounds.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

cp2_passed = True

# CP2.1: No coded values remain in the cleaned intermediate data
# INTENT: Verify all coded missing values were replaced with null before aggregation.
coded_remaining = 0
for code in CODED_MISSING.keys():
    count = df.filter(pl.col(enrollment_col) == code).height
    coded_remaining += count

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")
if not no_coded:
    cp2_passed = False

# CP2.2: Suppression rate in raw data
# INTENT: Document the rate of suppressed values (-3) in the raw enrollment data.
# REASONING: High suppression means many institutions have missing race-specific
# enrollment, which could bias URM share calculations.
suppressed_count = raw_df.filter(pl.col(enrollment_col) == SUPPRESSION_CODE).height
suppression_rate = suppressed_count / len(raw_df)
suppression_ok = suppression_rate < SUPPRESSION_THRESHOLD
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate: {suppression_rate:.1%} (threshold: {SUPPRESSION_THRESHOLD:.0%})")
if not suppression_ok:
    cp2_passed = False

# CP2.3: Row count in expected range (3,000-7,000 institutions)
rows_ok = 3000 <= post_rows <= 7000
print(f"  [{'PASS' if rows_ok else 'FAIL'}] Row count: {post_rows:,} (expected 3,000-7,000)")
if not rows_ok:
    cp2_passed = False

# CP2.4: urm_share range validation (0-1 for non-null values)
if urm_non_null.height > 0:
    urm_min = urm_non_null["urm_share"].min()
    urm_max = urm_non_null["urm_share"].max()
    range_ok = urm_min >= 0.0 and urm_max <= 1.0
    print(f"  [{'PASS' if range_ok else 'FAIL'}] urm_share range: [{urm_min:.4f}, {urm_max:.4f}] (expected [0, 1])")
    if not range_ok:
        cp2_passed = False
else:
    print(f"  [FAIL] urm_share: all values null")
    cp2_passed = False

# CP2.5: unitid uniqueness
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid uniqueness: {unitid_unique}")
if not unitid_unique:
    cp2_passed = False

# CP2.6: total_ug_enrollment positive for non-null values
# INTENT: Verify that total enrollment makes sense (should be > 0 for active institutions).
if enrl_non_null.height > 0:
    enrl_positive = enrl_non_null.filter(pl.col("total_ug_enrollment") > 0).height
    enrl_zero_or_neg = enrl_non_null.height - enrl_positive
    enrl_ok = enrl_zero_or_neg == 0
    print(f"  [{'PASS' if enrl_ok else 'WARN'}] total_ug_enrollment > 0: {enrl_positive:,} / {enrl_non_null.height:,} ({enrl_zero_or_neg:,} non-positive)")

assert cp2_passed, "STOP: CP2 VALIDATION FAILED - see details above"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)

# --- Citation ---
# INTENT: Generate citation text for IPEDS Fall Enrollment Race data per
# ODC Attribution License requirements.
print("\n" + "=" * 60)
print("CITATION")
print("=" * 60)
print("""
IPEDS Fall Enrollment by Race/Ethnicity, Education Data Portal (Version 0.20.0),
Urban Institute, accessed March 29, 2026,
https://educationdata.urban.org/documentation/,
made available under the ODC Attribution License.
""".strip())


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:25:41
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.5: Clean IPEDS Fall Enrollment Race
# ============================================================
# Loaded: 58,370 rows x 10 cols
# Columns: ['unitid', 'year', 'fips', 'sex', 'race', 'ftpt', 'level_of_study', 'degree_seeking', 'class_level', 'enrollment_fall']
# Dtypes: [Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64]
# 
# Pre-state: 58,370 rows, 10 cols
#   sex unique values: [99]
#   ftpt unique values: [99]
#   level_of_study unique values: [1]
#   race unique values: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#   Unique institutions (unitid): 5,837
#   Rows per institution: 10.0
# 
# Coded values in enrollment_fall:
#   -1 (Missing/not reported): 0
#   -2 (Not applicable): 0
#   -3 (Suppressed): 0
# 
# Replaced coded values with null in enrollment_fall
# Verified: no coded values remain in enrollment_fall
# 
# URM numerator: 5,837 institutions
# Domestic denominator: 5,837 institutions
# Total enrollment: 5,837 institutions
# 
# Result: 5,837 rows x 3 cols
# Columns: ['unitid', 'urm_share', 'total_ug_enrollment']
# 
# Post-state: 5,837 rows (one per institution)
# 
# URM Share Distribution:
#   Non-null: 5,833
#   Null: 4 (0.1%)
#   Mean:   0.4115
#   Median: 0.3444
#   Min:    0.0000
#   Max:    1.0000
#   Std:    0.2881
# 
# Total UG Enrollment Distribution:
#   Non-null: 5,837
#   Null: 0
#   Mean:   2,817
#   Median: 519
#   Min:    1
#   Max:    111,599
# 
# Unitid uniqueness: True (5,837 unique / 5,837 rows)
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_urm_share_clean.parquet
# File size: 58.3 KB
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values remaining: 0
#   [PASS] Suppression rate: 0.0% (threshold: 50%)
#   [PASS] Row count: 5,837 (expected 3,000-7,000)
#   [PASS] urm_share range: [0.0000, 1.0000] (expected [0, 1])
#   [PASS] unitid uniqueness: True
#   [PASS] total_ug_enrollment > 0: 5,837 / 5,837 (0 non-positive)
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
# 
# ============================================================
# CITATION
# ============================================================
# IPEDS Fall Enrollment by Race/Ethnicity, Education Data Portal (Version 0.20.0),
# Urban Institute, accessed March 29, 2026,
# https://educationdata.urban.org/documentation/,
# made available under the ODC Attribution License.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
