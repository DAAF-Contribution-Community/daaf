#!/usr/bin/env python3
"""
Stage 6.4: Clean CCD directory data — filter to regular open schools,
replace coded missing values, select key columns.

Task: clean-ccd-directory
Wave: 3, Step: 4, Stage: 6
Depends on: fetch-ccd-directory
Input: data/raw/2026-02-14_ccd_directory.parquet
Output: data/processed/2026-02-14_ccd_directory_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# The CCD directory provides school-level characteristics (locale, charter status,
# FRPL counts) needed to characterize schools that do/don't have SROs.
# Coded missing values (-1, -2, -3, -9) must be replaced with null before
# downstream analysis to avoid corrupting statistical calculations.
PROJECT_DIR = Path("/daaf/research/2026-02-14 School Law Enforcement Demographics")
DATE_PREFIX = "2026-02-14"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ccd_directory.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_ccd_directory_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data in numeric fields. Values -1, -2, -3 are standard across the Portal.
# We also include -9, which appears in some CCD variables as an additional
# "not reported" code. These must be mapped to null so they don't corrupt
# downstream statistical calculations (e.g., mean FRPL would be dragged
# down by negative sentinel values if left in place).
CODED_MISSING = [-1, -2, -3, -9]

# Columns where coded missing values need to be replaced with null.
# These are the analysis-relevant numeric/categorical columns from the CCD
# directory that may contain sentinel values.
COLUMNS_TO_CLEAN = ["free_or_reduced_price_lunch", "urban_centric_locale", "charter"]

# Key columns to retain for downstream analysis (joining with CRDC).
# REASONING: We select only columns needed for the research question to keep
# the dataset lean. ncessch is the join key; year for temporal alignment;
# school_name for human-readable labeling; fips for state identification
# (state_name is not available in this dataset); urban_centric_locale for
# locale classification; charter for charter status; free_or_reduced_price_lunch
# as the primary poverty proxy; lowest/highest_grade_offered for grade span.
KEY_COLUMNS = [
    "ncessch",
    "year",
    "school_name",
    "fips",
    "urban_centric_locale",
    "charter",
    "free_or_reduced_price_lunch",
    "lowest_grade_offered",
    "highest_grade_offered",
]

# Expected years from the Plan's query specification.
EXPECTED_YEARS = [2015, 2017, 2020, 2021]

# --- Load ---
# Load raw CCD directory data from Stage 5 output and verify shape before proceeding.
print("=" * 60)
print("Stage 6.4: Clean CCD Directory Data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE any transformations for post-validation comparison.
# Document initial row count, school_type and school_status value distributions,
# coded value presence, and FRPL null rate.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Document school_type distribution to understand filtering impact
print("\nSchool type distribution (pre-filter):")
school_type_counts = df.group_by("school_type").len().sort("school_type")
for row in school_type_counts.iter_rows():
    print(f"  school_type={row[0]}: {row[1]:,} rows")

# Document school_status distribution to understand filtering impact
print("\nSchool status distribution (pre-filter):")
school_status_counts = df.group_by("school_status").len().sort("school_status")
for row in school_status_counts.iter_rows():
    print(f"  school_status={row[0]}: {row[1]:,} rows")

# Document coded values present in analysis columns BEFORE cleaning
print("\nCoded values in analysis columns (pre-clean):")
for col in COLUMNS_TO_CLEAN:
    if col in df.columns:
        for code in CODED_MISSING:
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                print(f"  {col} == {code}: {count:,}")

# Document initial FRPL null rate (separate from coded values)
frpl_null_count = df["free_or_reduced_price_lunch"].null_count()
frpl_null_pct = frpl_null_count / pre_rows * 100
print(f"\nFRPL initial null rate: {frpl_null_count:,} ({frpl_null_pct:.1f}%)")

# --- Transform Step 1: Filter to regular, open schools ---
# INTENT: Retain only regular, currently operating public schools. Non-regular
# schools (special education, vocational, alternative) and non-open schools
# (closed, inactive, future) have different characteristics that would
# confound the analysis of SRO presence by demographics.
#
# REASONING: school_type == 1 means "Regular school" in CCD. school_status == 1
# means "Currently operational." Filtering on both ensures we analyze only
# the standard public school population that is relevant to the research question
# about law enforcement in schools.
#
# ASSUMES:
#   - school_type uses CCD integer encoding: 1=Regular, 2=Special Ed, 3=Vocational, 4=Alternative/Other
#   - school_status uses CCD integer encoding: 1=Open, 2=Closed, 3=New, etc.
#   - Both columns are present and populated (verified in pre-state check)
pre_filter_rows = df.shape[0]
df = df.filter(
    (pl.col("school_type") == 1) & (pl.col("school_status") == 1)
)
post_filter_rows = df.shape[0]
rows_removed_by_filter = pre_filter_rows - post_filter_rows
pct_removed = rows_removed_by_filter / pre_filter_rows * 100
print(f"\nFilter to regular open schools: {pre_filter_rows:,} -> {post_filter_rows:,}")
print(f"Rows removed by school_type/status filter: {rows_removed_by_filter:,} ({pct_removed:.1f}%)")

# --- Transform Step 2: Replace coded missing values with null ---
# INTENT: Replace Education Data Portal coded missing values (-1, -2, -3, -9)
# with null in analysis columns so downstream statistical operations are not
# corrupted by sentinel values being treated as real data.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation — these values were never observed or were suppressed.
# Zero would imply a measured value of zero (e.g., zero FRPL students), and NaN
# would complicate Polars aggregations. Polars handles null correctly in
# aggregations like mean(), sum(), etc., by excluding nulls.
#
# ASSUMES: All coded values in COLUMNS_TO_CLEAN are sentinel values per CCD
# source documentation (education-data-source-ccd skill). Values -1 (Missing),
# -2 (Not applicable), -3 (Suppressed), -9 (Not reported) should all be null.
for col in COLUMNS_TO_CLEAN:
    if col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(col).is_in(CODED_MISSING))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )
print("Replaced coded missing values (-1, -2, -3, -9) with null in analysis columns")

# --- Transform Step 3: Verify ncessch format ---
# INTENT: Ensure ncessch is a 12-character String, which is the canonical NCES
# school identifier format. This is critical for downstream joins with CRDC data.
#
# REASONING: ncessch must be exactly 12 characters to correctly represent the
# [State FIPS: 2][LEAID suffix: 5][School: 5] structure. If stored as integer,
# leading zeros would be stripped, breaking joins with datasets that store it
# as string.
#
# ASSUMES: ncessch is already String type from Stage 5 fetch (confirmed in
# Stage 5 findings: "ncessch is already 12-char String").
ncessch_dtype = df["ncessch"].dtype
print(f"\nncessch dtype: {ncessch_dtype}")

ncessch_lengths = df["ncessch"].str.len_chars().value_counts().sort("ncessch")
print(f"ncessch string lengths distribution:")
for row in ncessch_lengths.iter_rows():
    print(f"  length={row[0]}: {row[1]:,}")

# Verify all are 12 characters
all_12_char = df["ncessch"].str.len_chars().eq(12).all()
print(f"All ncessch are 12 chars: {all_12_char}")

if not all_12_char:
    # If any are not 12 chars, zero-pad them
    # REASONING: Some sources may store ncessch without leading zeros. Zero-padding
    # ensures consistent format for downstream joins.
    df = df.with_columns(
        pl.col("ncessch").str.zfill(12).alias("ncessch")
    )
    print("Applied zero-padding to ncessch to ensure 12-char format")

# --- Transform Step 4: Select key columns ---
# INTENT: Retain only columns needed for downstream analysis to keep the dataset
# lean and focused on the research question.
#
# REASONING: The full CCD directory has 11 columns. We retain 9 that are needed:
# ncessch (join key), year (temporal), school_name (label), fips (state),
# urban_centric_locale (urbanicity), charter (school type), free_or_reduced_price_lunch
# (poverty proxy), lowest/highest_grade_offered (grade span for filtering to
# schools that serve relevant grade levels).
#
# ASSUMES: All KEY_COLUMNS exist in the dataset (verified in fetch stage).
missing_cols = [c for c in KEY_COLUMNS if c not in df.columns]
if missing_cols:
    print(f"WARNING: Missing columns: {missing_cols}")
else:
    df = df.select(KEY_COLUMNS)
    print(f"\nSelected {len(KEY_COLUMNS)} key columns: {KEY_COLUMNS}")

# --- Post-state ---
# Capture state AFTER all transformations for validation comparison.
post_rows = df.shape[0]
post_cols = df.columns
print(f"\nPost-state: {post_rows:,} rows, {len(post_cols)} cols")
print(f"Row change from pre-state: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# Summary: row count per year
print("\nRow count per year:")
year_counts = df.group_by("year").len().sort("year")
for row in year_counts.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

# Summary: FRPL null rate after cleaning
frpl_null_post = df["free_or_reduced_price_lunch"].null_count()
frpl_null_pct_post = frpl_null_post / post_rows * 100
print(f"\nFRPL null rate after cleaning: {frpl_null_post:,} ({frpl_null_pct_post:.1f}%)")

# Summary: locale null rate after cleaning
locale_null = df["urban_centric_locale"].null_count()
locale_null_pct = locale_null / post_rows * 100
print(f"Locale null rate after cleaning: {locale_null:,} ({locale_null_pct:.1f}%)")

# Summary: charter null rate after cleaning
charter_null = df["charter"].null_count()
charter_null_pct = charter_null / post_rows * 100
print(f"Charter null rate after cleaning: {charter_null:,} ({charter_null_pct:.1f}%)")

# --- Save ---
# Persist results in parquet format to the processed data directory.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation ---
# Checkpoint validation: verify cleaning was correct and data meets Plan expectations.
# Each check corresponds to a specific requirement from the task specification.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

validation_log = {}

# CP2.1: All 4 expected years present
years_found = sorted(df["year"].unique().to_list())
all_years = all(y in years_found for y in EXPECTED_YEARS)
validation_log["All 4 years present"] = {"status": "PASS" if all_years else "FAIL", "detail": str(years_found)}
print(f"  [{'PASS' if all_years else 'FAIL'}] All 4 years present: {years_found}")

# CP2.2: Row count in expected range (250,000-450,000)
# REASONING: With 4 years of data and ~100K regular open schools per year,
# we expect 250K-450K total rows. Counts outside this range would indicate
# a filtering error or data issue.
row_count_ok = 250_000 <= post_rows <= 450_000
validation_log["Row count in range"] = {"status": "PASS" if row_count_ok else "FAIL", "detail": f"{post_rows:,}"}
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count 250K-450K: {post_rows:,}")

# CP2.3: No school_type != 1 or school_status != 1 remain
# REASONING: This is a hard constraint — the filter should have removed ALL
# non-regular and non-open schools. If any remain, the filter logic is wrong.
# Note: school_type and school_status are no longer in the selected columns,
# so we verify indirectly by checking that all rows passed the filter.
# The fact that we applied the filter and then selected columns means this
# is guaranteed, but we confirm the row count is reasonable.
filter_validation = post_rows < pre_rows  # Should have removed some rows
validation_log["Filter applied"] = {"status": "PASS" if filter_validation else "WARN", "detail": f"Removed {pre_rows - post_rows:,} rows"}
print(f"  [{'PASS' if filter_validation else 'WARN'}] Filter applied: removed {pre_rows - post_rows:,} non-regular/non-open schools")

# CP2.4: No coded values remain in analysis columns
# INTENT: Verify that ALL coded missing values have been successfully replaced
# with null. Their presence would corrupt downstream statistical calculations.
coded_remaining = 0
coded_detail = []
for col in COLUMNS_TO_CLEAN:
    if col in df.columns:
        for code in CODED_MISSING:
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                coded_remaining += count
                coded_detail.append(f"{col}={code}: {count}")

no_coded = coded_remaining == 0
validation_log["No coded values"] = {"status": "PASS" if no_coded else "FAIL", "detail": str(coded_detail) if coded_detail else "None remaining"}
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining} {'(' + ', '.join(coded_detail) + ')' if coded_detail else ''}")

# CP2.5: ncessch is 12-char String
ncessch_is_string = df["ncessch"].dtype == pl.String or df["ncessch"].dtype == pl.Utf8
ncessch_all_12 = df["ncessch"].str.len_chars().eq(12).all()
ncessch_ok = ncessch_is_string and ncessch_all_12
validation_log["ncessch format"] = {"status": "PASS" if ncessch_ok else "FAIL", "detail": f"dtype={df['ncessch'].dtype}, all_12_char={ncessch_all_12}"}
print(f"  [{'PASS' if ncessch_ok else 'FAIL'}] ncessch is 12-char String: dtype={df['ncessch'].dtype}, all 12-char={ncessch_all_12}")

# CP2.6: Suppression rate < 50% for FRPL (primary analysis variable)
# REASONING: The 50% threshold is from CLAUDE.md STOP conditions. Above 50%
# suppression, the remaining data is too sparse to support reliable analysis.
suppression_rate = frpl_null_pct_post / 100
suppression_ok = suppression_rate < 0.50
validation_log["FRPL suppression rate"] = {"status": "PASS" if suppression_ok else "FAIL", "detail": f"{suppression_rate:.1%}"}
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] FRPL suppression rate < 50%: {suppression_rate:.1%}")

# CP2.7: No nulls in identifier columns (ncessch, year)
ncessch_nulls = df["ncessch"].null_count()
year_nulls = df["year"].null_count()
no_id_nulls = ncessch_nulls == 0 and year_nulls == 0
validation_log["No ID nulls"] = {"status": "PASS" if no_id_nulls else "FAIL", "detail": f"ncessch={ncessch_nulls}, year={year_nulls}"}
print(f"  [{'PASS' if no_id_nulls else 'FAIL'}] No nulls in ID columns: ncessch={ncessch_nulls}, year={year_nulls}")

# CP2.8: Required columns present
required = KEY_COLUMNS
cols_present = all(c in df.columns for c in required)
validation_log["Required columns"] = {"status": "PASS" if cols_present else "FAIL", "detail": str(df.columns)}
print(f"  [{'PASS' if cols_present else 'FAIL'}] Required columns present: {cols_present}")

# --- Validation Summary ---
all_passed = all(v["status"] == "PASS" for v in validation_log.values())
print("\nValidation Summary:")
for check, info in validation_log.items():
    print(f"  [{info['status']}] {check}: {info['detail']}")

assert all_years, "STOP: Missing expected years"
assert no_coded, "STOP: Coded values still present in analysis columns"
assert ncessch_ok, "STOP: ncessch is not 12-char String"
assert suppression_ok, "STOP: FRPL suppression rate >= 50%"
assert no_id_nulls, "STOP: Nulls in identifier columns"
assert cols_present, "STOP: Missing required columns"

# Verify output file exists on disk
assert OUTPUT_PATH.exists(), f"STOP: Output file not found at {OUTPUT_PATH}"
verify_df = pl.read_parquet(OUTPUT_PATH)
assert verify_df.shape[0] == post_rows, f"STOP: Written file has {verify_df.shape[0]} rows, expected {post_rows}"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 00:30:36
# Command: python /daaf/research/2026-02-14 School Law Enforcement Demographics/scripts/stage6_clean/04_clean-ccd-directory.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.4: Clean CCD Directory Data
# ============================================================
# Loaded: 408,653 rows x 11 cols
# Columns: ['ncessch', 'year', 'school_type', 'school_status', 'urban_centric_locale', 'charter', 'free_or_reduced_price_lunch', 'lowest_grade_offered', 'highest_grade_offered', 'school_name', 'fips']
# 
# Pre-state: 408,653 rows, 11 cols
# 
# School type distribution (pre-filter):
#   school_type=None: 123 rows
#   school_type=1: 370,858 rows
#   school_type=2: 8,215 rows
#   school_type=3: 6,221 rows
#   school_type=4: 23,236 rows
# 
# School status distribution (pre-filter):
#   school_status=None: 123 rows
#   school_status=1: 395,081 rows
#   school_status=2: 4,619 rows
#   school_status=3: 4,431 rows
#   school_status=4: 353 rows
#   school_status=5: 325 rows
#   school_status=6: 2,031 rows
#   school_status=7: 1,561 rows
#   school_status=8: 129 rows
# 
# Coded values in analysis columns (pre-clean):
#   free_or_reduced_price_lunch == -1: 4,471
#   free_or_reduced_price_lunch == -2: 1,213
#   free_or_reduced_price_lunch == -3: 296
#   urban_centric_locale == -2: 118
#   charter == -2: 21,747
# 
# FRPL initial null rate: 61,580 (15.1%)
# 
# Filter to regular open schools: 408,653 -> 360,937
# Rows removed by school_type/status filter: 47,716 (11.7%)
# Replaced coded missing values (-1, -2, -3, -9) with null in analysis columns
# 
# ncessch dtype: String
# ncessch string lengths distribution:
#   length=12: 360,937
# All ncessch are 12 chars: True
# 
# Selected 9 key columns: ['ncessch', 'year', 'school_name', 'fips', 'urban_centric_locale', 'charter', 'free_or_reduced_price_lunch', 'lowest_grade_offered', 'highest_grade_offered']
# 
# Post-state: 360,937 rows, 9 cols
# Row change from pre-state: -47,716 (-11.7%)
# 
# Row count per year:
#   2015: 90,264
#   2017: 90,136
#   2020: 90,167
#   2021: 90,370
# 
# FRPL null rate after cleaning: 43,603 (12.1%)
# Locale null rate after cleaning: 141 (0.0%)
# Charter null rate after cleaning: 19,429 (5.4%)
# 
# Saved: /daaf/research/2026-02-14 School Law Enforcement Demographics/data/processed/2026-02-14_ccd_directory_clean.parquet
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] All 4 years present: [2015, 2017, 2020, 2021]
#   [PASS] Row count 250K-450K: 360,937
#   [PASS] Filter applied: removed 47,716 non-regular/non-open schools
#   [PASS] No coded values remaining: 0 
#   [PASS] ncessch is 12-char String: dtype=String, all 12-char=True
#   [PASS] FRPL suppression rate < 50%: 12.1%
#   [PASS] No nulls in ID columns: ncessch=0, year=0
#   [PASS] Required columns present: True
# 
# Validation Summary:
#   [PASS] All 4 years present: [2015, 2017, 2020, 2021]
#   [PASS] Row count in range: 360,937
#   [PASS] Filter applied: Removed 47,716 rows
#   [PASS] No coded values: None remaining
#   [PASS] ncessch format: dtype=String, all_12_char=True
#   [PASS] FRPL suppression rate: 12.1%
#   [PASS] No ID nulls: ncessch=0, year=0
#   [PASS] Required columns: ['ncessch', 'year', 'school_name', 'fips', 'urban_centric_locale', 'charter', 'free_or_reduced_price_lunch', 'lowest_grade_offered', 'highest_grade_offered']
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
