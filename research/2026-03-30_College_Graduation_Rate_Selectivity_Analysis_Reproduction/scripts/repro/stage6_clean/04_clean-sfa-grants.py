#!/usr/bin/env python3
"""
Stage 6.4: Clean IPEDS SFA Grants data as Pell proxy.

Task: clean-sfa-grants (MODIFIED Task 3.4 -- replaces original clean-fsa-grants)
Wave: 2, Step: 4, Stage: 6
Depends on: fetch-ipeds-sfa-grants (Stage 5, Task 2.4)
Input: data/raw/2026-03-29_ipeds_sfa_grants.parquet
Output: data/processed/2026-03-29_sfa_pell_clean.parquet
Checkpoint: CP2

Background: The original Plan used FSA Grants for Pell recipients, but
grant_recipients_unitid was 100% NULL for 2020-2021. This task cleans the
replacement IPEDS SFA Grants and Net Price data. Column number_receiving_grants
from type_of_aid=9 serves as "all grant/scholarship aid" proxy for Pell --
documented as acceptable proxy in Plan modification.

Provenance: IPEDS SFA Grants and Net Price via Urban Institute Education Data
Portal. The education-data-source-ipeds skill was consulted for context. Portal
uses integer encoding and -1/-2/-3 coded missing values for numeric fields.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# INTENT: Set paths and constants for cleaning IPEDS SFA Grants data.
# REASONING: All paths derive from PROJECT_DIR for portability. Date prefix
# ensures versioned output files. Coded missing values follow the Education
# Data Portal standard: -1 (missing), -2 (not applicable), -3 (suppressed).
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_sfa_grants.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfa_pell_clean.parquet"

# Education Data Portal coded missing values for numeric columns
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed"}

# Columns that need coded value replacement
NUMERIC_MEASURE_COLS = ["number_receiving_grants", "number_of_students"]

# Domain configuration (from Plan's Domain Configuration section)
SUPPRESSION_CODE = -3
CODED_MISSING_VALUES = [-1, -2, -3]
SUPPRESSION_THRESHOLD = 0.5  # 50% default for education data

# --- Load ---
# Load raw IPEDS SFA Grants data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.4: Clean IPEDS SFA Grants (Pell Proxy)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# INTENT: Capture raw data state before any transformations for post-validation
# comparison. Document the structure of the raw data to verify filtering logic.
# REASONING: We need to understand the type_of_aid and income_level distributions
# to confirm the filtering specification from Stage 5 QA findings.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Document type_of_aid distribution
print("\ntype_of_aid distribution:")
toa_dist = df.group_by("type_of_aid").agg(pl.len().alias("count"))
for row in toa_dist.sort("type_of_aid").iter_rows(named=True):
    print(f"  type_of_aid={row['type_of_aid']}: {row['count']:,} rows")

# Document income_level distribution within type_of_aid=9
# INTENT: Verify that income_level=99 (institution-level total) exists and
# is the correct filter for getting one row per institution.
toa9 = df.filter(pl.col("type_of_aid") == 9)
print(f"\nWithin type_of_aid=9 ({toa9.shape[0]:,} rows):")
il_dist = toa9.group_by("income_level").agg(pl.len().alias("count"))
for row in il_dist.sort("income_level").iter_rows(named=True):
    print(f"  income_level={row['income_level']}: {row['count']:,} rows")

# Document coded values in measure columns before cleaning
print("\nCoded values in raw data (type_of_aid=9, income_level=99 slice):")
raw_slice = df.filter(
    (pl.col("type_of_aid") == 9) & (pl.col("income_level") == 99)
)
for col in NUMERIC_MEASURE_COLS:
    if col in raw_slice.columns:
        for code, meaning in CODED_MISSING.items():
            count = raw_slice.filter(pl.col(col) == code).height
            if count > 0:
                print(f"  {col} = {code} ({meaning}): {count:,}")
        null_count = raw_slice[col].null_count()
        if null_count > 0:
            print(f"  {col} = null: {null_count:,}")

# --- Filter ---
# INTENT: Filter to usable grant recipient slice: type_of_aid=9 (all grant/
# scholarship aid from all sources) and income_level=99 (institution-level
# total across all income brackets).
#
# REASONING: type_of_aid=9 is the only type that has grant recipient counts
# (number_receiving_grants). type_of_aid=3 only has net price data and no
# recipient counts. income_level=99 gives institution-level totals, avoiding
# double-counting from income bracket breakdowns (levels 1-5). Stage 5 QA
# confirmed this yields ~5,320 rows with one row per institution.
#
# ASSUMES: type_of_aid and income_level columns exist and use integer encoding.
# income_level=99 is the "total" code (not a count), per EDP conventions.
df_filtered = df.filter(
    (pl.col("type_of_aid") == 9) & (pl.col("income_level") == 99)
)
print(f"\nAfter filtering (type_of_aid=9, income_level=99): {df_filtered.shape[0]:,} rows")
filter_removed = pre_rows - df_filtered.shape[0]
print(f"Rows removed by filter: {filter_removed:,} ({filter_removed / pre_rows * 100:.1f}%)")

# --- Clean Coded Values ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in numeric
# measure columns so downstream statistical operations are not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation -- these values were never observed or were suppressed.
# Zero would imply a measured value of zero (which has meaning: "the institution
# reported zero grant recipients"), and NaN would complicate Polars aggregations.
#
# ASSUMES: All coded values in NUMERIC_MEASURE_COLS are in the CODED_MISSING
# dict per Education Data Portal documentation.
for col in NUMERIC_MEASURE_COLS:
    if col in df_filtered.columns:
        df_filtered = df_filtered.with_columns(
            pl.when(pl.col(col).is_in(list(CODED_MISSING.keys())))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )
print("Replaced coded values (-1, -2, -3) with null in measure columns")

# --- Rename Columns ---
# INTENT: Rename columns for downstream compatibility with the analysis pipeline.
# REASONING: number_receiving_grants is renamed to grant_recipients because it
# serves as the Pell proxy variable in the analysis. number_of_students is
# renamed to sfa_total_students for clarity (it represents the SFA survey's
# student count, not fall enrollment).
#
# ASSUMES: These column names do not conflict with other datasets in the
# downstream join (Stage 7). The "grant_recipients" name clearly signals this
# is all-grant aid, not Pell-specific, per the Plan modification documentation.
df_clean = df_filtered.rename({
    "number_receiving_grants": "grant_recipients",
    "number_of_students": "sfa_total_students",
})
print("Renamed: number_receiving_grants -> grant_recipients")
print("Renamed: number_of_students -> sfa_total_students")

# --- Verify Uniqueness ---
# INTENT: Verify unitid uniqueness -- there should be exactly one row per
# institution after filtering to type_of_aid=9, income_level=99.
# REASONING: Duplicate unitids would indicate the filter did not produce
# the expected grain (one row per institution) and would cause fan-out
# in downstream joins.
n_unitids = df_clean["unitid"].n_unique()
n_rows = df_clean.shape[0]
unitid_unique = n_unitids == n_rows
print(f"\nUnitid uniqueness: {n_unitids:,} unique unitids, {n_rows:,} rows")
print(f"  Unique: {unitid_unique}")
assert unitid_unique, f"STOP: unitid is not unique: {n_unitids} unique vs {n_rows} rows"

# --- Select Columns ---
# INTENT: Select only the columns needed for downstream analysis.
# REASONING: Carrying all original columns would bloat the dataset and risk
# confusion about which variables to use. The downstream join (Stage 7)
# needs unitid (join key), grant_recipients (Pell proxy), and
# sfa_total_students (reference denominator).
df_clean = df_clean.select(["unitid", "grant_recipients", "sfa_total_students"])
print(f"\nSelected columns: {df_clean.columns}")
print(f"Final shape: {df_clean.shape[0]:,} rows x {df_clean.shape[1]} cols")

# --- Post-state ---
# INTENT: Document data quality of the final clean dataset.
post_rows = df_clean.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {df_clean.shape[1]} cols")

# Null counts
for col in df_clean.columns:
    null_ct = df_clean[col].null_count()
    null_pct = null_ct / post_rows * 100 if post_rows > 0 else 0
    print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

# Value range checks for grant_recipients
gr = df_clean["grant_recipients"].drop_nulls()
print(f"\ngrant_recipients (non-null): n={gr.len():,}, min={gr.min()}, max={gr.max()}, median={gr.median()}")

# Check for negative values (should not exist after coded value removal)
neg_count = gr.filter(gr < 0).len()
print(f"  Negative values: {neg_count:,}")
assert neg_count == 0, f"STOP: {neg_count} negative values in grant_recipients after cleaning"

# Check zero values (valid -- some institutions report zero recipients)
zero_count = gr.filter(gr == 0).len()
print(f"  Zero values: {zero_count:,} (valid -- institutions with zero grant recipients)")

# --- Save ---
# INTENT: Persist cleaned data as parquet for downstream Stage 7 join.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_clean.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists and is readable
saved_df = pl.read_parquet(OUTPUT_PATH)
print(f"Verified: {saved_df.shape[0]:,} rows x {saved_df.shape[1]} cols readable from disk")

# --- CP2 Validation ---
# INTENT: Verify data quality after cleaning operations -- confirm coded values
# are removed, suppression rates are within tolerance, and data loss is documented.
# REASONING: CP2 validates the cleaning stage output. The "raw" reference here
# is the filtered slice (type_of_aid=9, income_level=99) since that is the
# meaningful comparison population, not the full multi-type raw file.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True

# CP2.1: Data loss check (compared to filtered slice, not full raw file)
# REASONING: The filter from full raw to type_of_aid=9/income_level=99 is a
# design decision (not data loss). The relevant loss metric is how many
# institutions from the filtered slice were lost during coded value handling.
# Since we replace coded values with null rather than dropping rows, the
# row count should be preserved from the filtered slice.
filtered_rows = raw_slice.shape[0]
clean_rows = df_clean.shape[0]
rows_removed = filtered_rows - clean_rows
loss_rate = rows_removed / filtered_rows if filtered_rows > 0 else 0

print(f"\nData Loss:")
print(f"  Full raw rows:     {pre_rows:,}")
print(f"  Filtered slice:    {filtered_rows:,} (type_of_aid=9, income_level=99)")
print(f"  Clean rows:        {clean_rows:,}")
print(f"  Rows removed:      {rows_removed:,} ({loss_rate:.1%})")

if loss_rate > 0.9:
    print(f"[FAIL] Data loss rate {loss_rate:.1%} exceeds 90%")
    cp2_passed = False
elif loss_rate > 0.5:
    print(f"[WARN] High data loss rate: {loss_rate:.1%}")
else:
    print(f"[PASS] Data loss rate {loss_rate:.1%} within tolerance")

# CP2.2: Suppression rate check (on the filtered slice before cleaning)
print(f"\nSuppression Rates (in filtered raw slice):")
for var in NUMERIC_MEASURE_COLS:
    orig_var = var  # same name before rename
    if orig_var in raw_slice.columns:
        suppressed = (raw_slice[orig_var] == SUPPRESSION_CODE).sum()
        supp_rate = suppressed / filtered_rows if filtered_rows > 0 else 0
        if supp_rate > SUPPRESSION_THRESHOLD:
            print(f"[FAIL] {orig_var}: {supp_rate:.1%} suppressed (>{SUPPRESSION_THRESHOLD:.0%} threshold)")
            cp2_passed = False
        elif supp_rate > 0.2:
            print(f"[WARN] {orig_var}: {supp_rate:.1%} suppressed (notable)")
        else:
            print(f"[PASS] {orig_var}: {supp_rate:.1%} suppressed")

# CP2.3: No coded values remain in clean data
print(f"\nCoded Values Check (clean data):")
coded_found = False
for var in ["grant_recipients", "sfa_total_students"]:
    if var in df_clean.columns:
        for code in CODED_MISSING_VALUES:
            count = (df_clean[var] == code).sum()
            if count > 0:
                print(f"[FAIL] {var}: {count} coded value {code} remains")
                coded_found = True
                cp2_passed = False

if not coded_found:
    print("[PASS] No coded values remain in key variables")

# CP2.4: Row count within expected range (4,000-6,000 institutions)
rows_in_range = 4000 <= clean_rows <= 6000
if not rows_in_range:
    print(f"\n[WARN] Row count {clean_rows:,} outside expected range 4,000-6,000")
else:
    print(f"\n[PASS] Row count {clean_rows:,} within expected range 4,000-6,000")

# CP2.5: grant_recipients non-negative for all non-null values
gr_non_null = df_clean["grant_recipients"].drop_nulls()
all_non_neg = (gr_non_null >= 0).all()
if not all_non_neg:
    print(f"[FAIL] grant_recipients has negative values")
    cp2_passed = False
else:
    print(f"[PASS] grant_recipients >= 0 for all non-null values")

# CP2.6: unitid has no nulls (critical identifier)
unitid_nulls = df_clean["unitid"].null_count()
if unitid_nulls > 0:
    print(f"[FAIL] unitid has {unitid_nulls:,} nulls")
    cp2_passed = False
else:
    print(f"[PASS] unitid: 0 nulls (critical identifier)")

# CP2.7: Rows preserved (cleaning replaces values, doesn't drop rows)
rows_preserved = clean_rows == filtered_rows
if rows_preserved:
    print(f"[PASS] Rows preserved from filtered slice: {filtered_rows:,} -> {clean_rows:,}")
else:
    print(f"[WARN] Row count changed: {filtered_rows:,} -> {clean_rows:,}")

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")

# --- Citation ---
# INTENT: Generate citation for the data source used in this cleaning step.
# REASONING: ODC-By license requires attribution. The citation identifies the
# specific IPEDS survey component and access method.
print("\n" + "=" * 60)
print("DATA CITATION")
print("=" * 60)
print("""
IPEDS Student Financial Aid and Net Price (SFA), Education Data Portal
(Version 0.20.0), Urban Institute, accessed March 29, 2026,
https://educationdata.urban.org/documentation/,
made available under the ODC Attribution License.

Note: grant_recipients column represents all grant/scholarship aid recipients
(type_of_aid=9), not Pell-specific recipients. Used as Pell proxy per Plan
modification (original FSA grant_recipients_unitid was 100% NULL for 2020-2021).
""")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:26:58
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage6_clean/04_clean-sfa-grants.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.4: Clean IPEDS SFA Grants (Pell Proxy)
# ============================================================
# Loaded: 37,292 rows x 15 cols
# Columns: ['unitid', 'year', 'fips', 'ftpt', 'level_of_study', 'degree_seeking', 'class_level', 'tuition_type', 'type_of_aid', 'income_level', 'average_grant', 'number_of_students', 'total_grant', 'net_price', 'number_receiving_grants']
# 
# Pre-state: 37,292 rows, 15 cols
# 
# type_of_aid distribution:
#   type_of_aid=3: 5,372 rows
#   type_of_aid=9: 31,920 rows
# 
# Within type_of_aid=9 (31,920 rows):
#   income_level=1: 5,320 rows
#   income_level=2: 5,320 rows
#   income_level=3: 5,320 rows
#   income_level=4: 5,320 rows
#   income_level=5: 5,320 rows
#   income_level=99: 5,320 rows
# 
# Coded values in raw data (type_of_aid=9, income_level=99 slice):
# 
# After filtering (type_of_aid=9, income_level=99): 5,320 rows
# Rows removed by filter: 31,972 (85.7%)
# Replaced coded values (-1, -2, -3) with null in measure columns
# Renamed: number_receiving_grants -> grant_recipients
# Renamed: number_of_students -> sfa_total_students
# 
# Unitid uniqueness: 5,320 unique unitids, 5,320 rows
#   Unique: True
# 
# Selected columns: ['unitid', 'grant_recipients', 'sfa_total_students']
# Final shape: 5,320 rows x 3 cols
# 
# Post-state: 5,320 rows, 3 cols
#   unitid: 0 nulls (0.0%)
#   grant_recipients: 0 nulls (0.0%)
#   sfa_total_students: 0 nulls (0.0%)
# 
# grant_recipients (non-null): n=5,320, min=0, max=4519, median=77.0
#   Negative values: 0
#   Zero values: 11 (valid -- institutions with zero grant recipients)
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_sfa_pell_clean.parquet
# Verified: 5,320 rows x 3 cols readable from disk
# 
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
# 
# Data Loss:
#   Full raw rows:     37,292
#   Filtered slice:    5,320 (type_of_aid=9, income_level=99)
#   Clean rows:        5,320
#   Rows removed:      0 (0.0%)
# [PASS] Data loss rate 0.0% within tolerance
# 
# Suppression Rates (in filtered raw slice):
# [PASS] number_receiving_grants: 0.0% suppressed
# [PASS] number_of_students: 0.0% suppressed
# 
# Coded Values Check (clean data):
# [PASS] No coded values remain in key variables
# 
# [PASS] Row count 5,320 within expected range 4,000-6,000
# [PASS] grant_recipients >= 0 for all non-null values
# [PASS] unitid: 0 nulls (critical identifier)
# [PASS] Rows preserved from filtered slice: 5,320 -> 5,320
# 
# CP2 VALIDATION: PASSED
# ============================================================
# 
# ============================================================
# DATA CITATION
# ============================================================
# 
# IPEDS Student Financial Aid and Net Price (SFA), Education Data Portal
# (Version 0.20.0), Urban Institute, accessed March 29, 2026,
# https://educationdata.urban.org/documentation/,
# made available under the ODC Attribution License.
# 
# Note: grant_recipients column represents all grant/scholarship aid recipients
# (type_of_aid=9), not Pell-specific recipients. Used as Pell proxy per Plan
# modification (original FSA grant_recipients_unitid was 100% NULL for 2020-2021).
# 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
