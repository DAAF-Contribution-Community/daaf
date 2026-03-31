#!/usr/bin/env python3
"""
Stage 6 - Step 01: Clean IPEDS Directory Data
==============================================
Task:     3.1 - Clean IPEDS Institutional Directory
Input:    data/raw/2026-03-29_ipeds_directory.parquet (12,729 rows)
Output:   data/processed/2026-03-29_directory_clean.parquet
Plan:     2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

Filters raw IPEDS directory to 4-year degree-granting institutions for
year 2020. Replaces coded missing values (-1, -2, -3) with null in
numeric indicator columns. Selects analysis columns and validates
unitid uniqueness.

Provenance: Data accessed via Urban Institute Education Data Portal.
"""

import polars as pl
import os
from datetime import datetime

# --- Config ---
# Configuration constants derived from the Plan's query specification and
# the orchestrator task prompt. Paths are absolute per DAAF convention.
PROJECT_DIR = "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis"
INPUT_PATH = os.path.join(PROJECT_DIR, "data/raw/2026-03-29_ipeds_directory.parquet")
OUTPUT_PATH = os.path.join(PROJECT_DIR, "data/processed/2026-03-29_directory_clean.parquet")

# Population filters from Plan Task 3.1
TARGET_YEAR = 2020
# REASONING: degree_granting == 1 restricts to institutions that confer degrees
# (excludes non-degree-granting certificate-only institutions)
DEGREE_GRANTING_CODE = 1
# REASONING: institution_level == 4 restricts to 4-year institutions
# (excludes 2-year, less-than-2-year). This is the universe for graduation
# rate analysis of bachelor's-degree-granting institutions.
INSTITUTION_LEVEL_4YEAR = 4

# Coded missing values per Education Data Portal convention
# REASONING: The Portal encodes -1 (missing/not reported), -2 (not applicable),
# -3 (suppressed for privacy) in numeric columns. These must be replaced with
# null before any analysis to prevent them from corrupting calculations.
CODED_MISSING_VALUES = [-1, -2, -3]

# Columns where coded values should be replaced with null
# INTENT: These are binary indicator columns (0/1) where -1/-2/-3 are coded missingness
# ASSUMES: inst_control uses integer codes 1/2/3 and should NOT have coded missing values
#   after filtering to degree-granting 4-year institutions
CODED_VALUE_COLUMNS = ["open_public", "hbcu", "tribal_college"]

# Final columns to retain for downstream analysis
# REASONING: unitid is the primary key; inst_name for identification; fips for
# state grouping; inst_control for public/private/for-profit sector analysis;
# open_public retained for reference (NOTE: means "open to the public" operating
# status, NOT open-admissions policy per Stage 5 QA finding); hbcu and
# tribal_college for institutional characteristic controls.
SELECT_COLUMNS = ["unitid", "inst_name", "fips", "inst_control", "open_public", "hbcu", "tribal_college"]

# Validation thresholds
EXPECTED_ROW_RANGE = (2500, 4500)  # from orchestrator specification
SUPPRESSION_CODE = -3
SUPPRESSION_THRESHOLD = 0.5  # 50% BLOCKER threshold from Plan domain config

# Domain configuration
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID-impacted years in education data

# --- Load ---
# Load raw IPEDS directory data from Stage 5 fetch output.
# Verify the file exists and inspect schema before proceeding.
print("=" * 60)
print("STAGE 6.1: CLEAN IPEDS DIRECTORY")
print("=" * 60)

assert os.path.exists(INPUT_PATH), f"Input file not found: {INPUT_PATH}"
raw_df = pl.read_parquet(INPUT_PATH)
print(f"\nLoaded raw data: {raw_df.shape[0]:,} rows x {raw_df.shape[1]} cols")
print(f"Columns: {raw_df.columns}")
print(f"Dtypes:\n{raw_df.dtypes}")

# --- Pre-state ---
# Capture the current state of the data BEFORE transformation. These values
# are compared against post-state to validate the transformation worked
# correctly and didn't introduce unexpected changes.
pre_rows = raw_df.shape[0]
pre_cols = raw_df.shape[1]
pre_unitids = sorted(raw_df["unitid"].head(3).to_list())
print(f"\nPre-state:")
print(f"  Rows: {pre_rows:,}")
print(f"  Shape: {pre_rows} x {pre_cols}")
print(f"  Sample unitids: {pre_unitids}")
print(f"  Year values: {sorted(raw_df['year'].unique().to_list())}")

# Check what institution_level values exist
print(f"\n  institution_level distribution:")
print(raw_df["institution_level"].value_counts().sort("institution_level"))

# Check degree_granting distribution
print(f"\n  degree_granting distribution:")
print(raw_df["degree_granting"].value_counts().sort("degree_granting"))

# --- Transform ---
# Apply sequential filters per Plan Task 3.1 specification. Each filter is
# applied and validated independently to track row loss at each step.

validation_log = {}

# Step 1: Filter to target year (2020)
# INTENT: Restrict to single cross-sectional year for the analysis.
# REASONING: The research question examines graduation rates at a point in time,
# not trends. Year 2020 aligns with the most recent available graduation rate data.
rows_before = raw_df.shape[0]
df = raw_df.filter(pl.col("year") == TARGET_YEAR)
rows_after = df.shape[0]
validation_log["Filter year == 2020"] = {
    "pre_rows": rows_before,
    "post_rows": rows_after,
    "removed": rows_before - rows_after,
    "pct_removed": (rows_before - rows_after) / rows_before * 100 if rows_before > 0 else 0,
}
print(f"\nFilter year == {TARGET_YEAR}: {rows_before:,} -> {rows_after:,} (removed {rows_before - rows_after:,})")

# Step 2: Filter to degree-granting institutions
# INTENT: Exclude non-degree-granting institutions (e.g., certificate-only programs)
# ASSUMES: degree_granting column uses 1 = yes, 0 or 2 = no
rows_before = df.shape[0]
df = df.filter(pl.col("degree_granting") == DEGREE_GRANTING_CODE)
rows_after = df.shape[0]
validation_log["Filter degree_granting == 1"] = {
    "pre_rows": rows_before,
    "post_rows": rows_after,
    "removed": rows_before - rows_after,
    "pct_removed": (rows_before - rows_after) / rows_before * 100 if rows_before > 0 else 0,
}
print(f"Filter degree_granting == {DEGREE_GRANTING_CODE}: {rows_before:,} -> {rows_after:,} (removed {rows_before - rows_after:,})")

# Step 3: Filter to 4-year institutions
# INTENT: Restrict to bachelor's-degree-granting institutions for graduation rate analysis.
# REASONING: institution_level == 4 is the Portal code for "Four-year or above".
# This excludes 2-year (community colleges) and less-than-2-year institutions
# whose graduation dynamics differ fundamentally from 4-year bachelor's programs.
rows_before = df.shape[0]
df = df.filter(pl.col("institution_level") == INSTITUTION_LEVEL_4YEAR)
rows_after = df.shape[0]
validation_log["Filter institution_level == 4"] = {
    "pre_rows": rows_before,
    "post_rows": rows_after,
    "removed": rows_before - rows_after,
    "pct_removed": (rows_before - rows_after) / rows_before * 100 if rows_before > 0 else 0,
}
print(f"Filter institution_level == {INSTITUTION_LEVEL_4YEAR}: {rows_before:,} -> {rows_after:,} (removed {rows_before - rows_after:,})")

# Step 4: Replace coded missing values with null in indicator columns
# INTENT: Convert Portal coded values (-1/-2/-3) to proper nulls so they are
# excluded from downstream calculations automatically by Polars.
# REASONING: Leaving -1/-2/-3 in place would corrupt means, counts, and
# distributional statistics. Replacing with null makes missingness explicit
# and handled correctly by Polars aggregation functions.
for col_name in CODED_VALUE_COLUMNS:
    if col_name in df.columns:
        coded_count = sum((df[col_name] == c).sum() for c in CODED_MISSING_VALUES)
        print(f"\n  {col_name}: {coded_count} coded values found -> replacing with null")
        # ASSUMES: These columns contain integer-coded indicators where
        # -1/-2/-3 are the only non-valid values needing replacement
        df = df.with_columns(
            pl.when(pl.col(col_name).is_in(CODED_MISSING_VALUES))
            .then(None)
            .otherwise(pl.col(col_name))
            .alias(col_name)
        )

# Step 5: Verify inst_control has no coded missing values
# INTENT: inst_control (1=public, 2=private nonprofit, 3=private for-profit)
# is critical for sector analysis. Verify no coded values remain.
# ASSUMES: All degree-granting 4-year institutions should have a valid
# inst_control value (1, 2, or 3).
inst_control_coded = sum((df["inst_control"] == c).sum() for c in CODED_MISSING_VALUES)
inst_control_values = sorted(df["inst_control"].unique().to_list())
print(f"\n  inst_control coded values remaining: {inst_control_coded}")
print(f"  inst_control unique values: {inst_control_values}")
assert inst_control_coded == 0, f"inst_control still has {inst_control_coded} coded values"
assert all(v in [1, 2, 3] for v in inst_control_values), (
    f"inst_control has unexpected values: {inst_control_values}"
)

# Step 6: Verify unitid uniqueness
# INTENT: Each institution should appear exactly once after filtering to a single year.
# ASSUMES: The raw data has one row per unitid per year.
n_unitids = df["unitid"].n_unique()
n_rows = df.shape[0]
print(f"\n  unitid uniqueness: {n_unitids:,} unique unitids in {n_rows:,} rows")
assert n_unitids == n_rows, (
    f"unitid is not unique: {n_unitids} unique values vs {n_rows} rows"
)

# Step 7: Select final columns
# INTENT: Retain only the columns needed for downstream analysis to reduce
# file size and prevent accidental use of unvalidated columns.
missing_select = [c for c in SELECT_COLUMNS if c not in df.columns]
assert not missing_select, f"Missing columns for selection: {missing_select}"
clean_df = df.select(SELECT_COLUMNS)

print(f"\nSelected {len(SELECT_COLUMNS)} columns: {SELECT_COLUMNS}")

# --- Validate ---
# CP2 Validation: Post-Cleaning checkpoint verifying data quality,
# suppression rates, coded value removal, and data loss thresholds.

print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True

# Data loss check
raw_rows = pre_rows
clean_rows = clean_df.shape[0]
rows_removed = raw_rows - clean_rows
loss_rate = rows_removed / raw_rows if raw_rows > 0 else 0

print(f"\nData Loss:")
print(f"  Raw rows:     {raw_rows:,}")
print(f"  Clean rows:   {clean_rows:,}")
print(f"  Rows removed: {rows_removed:,} ({loss_rate:.1%})")

if loss_rate > 0.9:
    print(f"[FAIL] Data loss rate {loss_rate:.1%} exceeds 90%")
    cp2_passed = False
elif loss_rate > 0.5:
    print(f"[WARN] High data loss rate: {loss_rate:.1%}")
else:
    print(f"[PASS] Data loss rate {loss_rate:.1%} within tolerance")

# Row count range check
if EXPECTED_ROW_RANGE[0] <= clean_rows <= EXPECTED_ROW_RANGE[1]:
    print(f"[PASS] Row count {clean_rows:,} within expected range {EXPECTED_ROW_RANGE}")
else:
    print(f"[WARN] Row count {clean_rows:,} outside expected range {EXPECTED_ROW_RANGE}")

# Suppression rate check (on raw data, within target population)
# INTENT: Measure how much data is suppressed (-3) in the columns we care about.
# REASONING: High suppression rates indicate privacy-driven data loss that
# could bias results, especially for small institutions.
print(f"\nSuppression Rates (in raw year-filtered data):")
raw_year_df = raw_df.filter(pl.col("year") == TARGET_YEAR)
for var in CODED_VALUE_COLUMNS:
    if var in raw_year_df.columns:
        suppressed = (raw_year_df[var] == SUPPRESSION_CODE).sum()
        total = raw_year_df.shape[0]
        supp_rate = suppressed / total if total > 0 else 0
        if supp_rate > SUPPRESSION_THRESHOLD:
            print(f"[FAIL] {var}: {supp_rate:.1%} suppressed (>{SUPPRESSION_THRESHOLD:.0%} threshold)")
            cp2_passed = False
        elif supp_rate > 0.1:
            print(f"[WARN] {var}: {supp_rate:.1%} suppressed (notable)")
        else:
            print(f"[PASS] {var}: {supp_rate:.1%} suppressed")

# Coded values remaining in clean data
print(f"\nCoded Values Check (clean data):")
coded_found = False
for var in CODED_VALUE_COLUMNS + ["inst_control"]:
    if var in clean_df.columns:
        dtype = clean_df[var].dtype
        if dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            coded = sum((clean_df[var] == c).sum() for c in CODED_MISSING_VALUES)
            if coded > 0:
                print(f"[WARN] {var}: {coded} coded values remain")
                coded_found = True
if not coded_found:
    print("[PASS] No coded values remain in key variables")

# Null summary for clean data
print(f"\nNull Summary (clean data):")
for col in clean_df.columns:
    null_ct = clean_df[col].null_count()
    null_pct = null_ct / clean_rows * 100 if clean_rows > 0 else 0
    if null_ct > 0:
        print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")
    else:
        print(f"  {col}: 0 nulls")

# COVID year flag
if TARGET_YEAR in FLAG_YEARS:
    print(f"\n[INFO] Target year {TARGET_YEAR} is a COVID-impacted year. "
          "Directory data (institutional characteristics) is less affected than "
          "enrollment/outcome data, but document in limitations.")

# Validation log summary
print(f"\nTransformation Summary:")
for step, info in validation_log.items():
    print(f"  {step}: {info['pre_rows']:,} -> {info['post_rows']:,} "
          f"(removed {info['removed']:,}, {info['pct_removed']:.1f}%)")

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")

# --- Post-state ---
# Capture final state for comparison with pre-state.
post_rows = clean_df.shape[0]
post_cols = clean_df.shape[1]
post_unitids = sorted(clean_df["unitid"].head(3).to_list())
print(f"\nPost-state:")
print(f"  Rows: {post_rows:,}")
print(f"  Shape: {post_rows} x {post_cols}")
print(f"  Sample unitids: {post_unitids}")
print(f"  Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# inst_control distribution
print(f"\n  inst_control distribution (1=public, 2=private nonprofit, 3=private for-profit):")
print(clean_df["inst_control"].value_counts().sort("inst_control"))

# --- Save ---
# Persist cleaned data as parquet. Output path matches Plan specification.
clean_df.write_parquet(OUTPUT_PATH)
assert os.path.exists(OUTPUT_PATH), f"Output file not created: {OUTPUT_PATH}"
file_size = os.path.getsize(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

# --- Citation ---
# INTENT: Generate citation text per ODC-By license requirements.
# The Education Data Portal requires attribution for all published work.
print(f"\n--- Citation ---")
print(f"IPEDS Institutional Characteristics, Education Data Portal (Version 0.20.0),")
print(f"Urban Institute, accessed March 29, 2026,")
print(f"https://educationdata.urban.org/documentation/,")
print(f"made available under the ODC Attribution License.")

print(f"\n{'=' * 60}")
print("STAGE 6.1 COMPLETE")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:25:50
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/01_clean-directory.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# STAGE 6.1: CLEAN IPEDS DIRECTORY
# ============================================================
# 
# Loaded raw data: 12,729 rows x 89 cols
# Columns: ['unitid', 'year', 'opeid', 'inst_name', 'inst_alias', 'address', 'state_abbr', 'fips', 'zip', 'phone_number', 'city', 'county_name', 'county_fips', 'region', 'urban_centric_locale', 'cbsa', 'cbsa_type', 'csa', 'necta', 'longitude', 'latitude', 'congress_district_id', 'ein', 'ueis', 'chief_admin_name', 'chief_admin_title', 'inst_status', 'currently_active_ipeds', 'degree_granting', 'open_public', 'title_iv_indicator', 'postsec_public_active', 'postsec_public_active_title_iv', 'date_closed', 'newid', 'year_deleted', 'inst_control', 'institution_level', 'inst_category', 'inst_size', 'sector', 'primarily_postsecondary', 'hbcu', 'hospital', 'medical_degree', 'tribal_college', 'land_grant', 'offering_highest_degree', 'offering_highest_level', 'offering_undergrad', 'offering_grad', 'url_school', 'url_fin_aid', 'url_application', 'url_netprice', 'url_veterans', 'url_athletes', 'url_disability_services', 'cc_basic_2010', 'cc_instruc_undergrad_2010', 'cc_instruc_grad_2010', 'cc_undergrad_2010', 'cc_enroll_2010', 'cc_size_setting_2010', 'cc_basic_2000', 'cc_basic_2015', 'cc_instruc_undergrad_2015', 'cc_instruc_grad_2015', 'cc_undergrad_2015', 'cc_enroll_2015', 'cc_size_setting_2015', 'cc_basic_2018', 'cc_instruc_undergrad_2018', 'cc_instruc_grad_2018', 'cc_undergrad_2018', 'cc_enroll_2018', 'cc_size_setting_2018', 'comparison_group', 'comparison_group_custom', 'inst_system_flag', 'inst_system_name', 'reporting_method', 'duns', 'cc_basic_2021', 'cc_instruc_undergrad_2021', 'cc_instruc_grad_2021', 'cc_undergrad_2021', 'cc_enroll_2021', 'cc_size_setting_2021']
# Dtypes:
# [Int64, Int64, String, String, String, String, String, Int64, String, String, String, String, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Float64, Float64, Int64, String, String, String, String, Int64, Int64, Int64, Int64, Int64, Int64, Int64, String, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, String, String, String, String, String, String, String, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, String, Int64, String, Int64, Int64, Int64, Int64, Int64, Int64]
# 
# Pre-state:
#   Rows: 12,729
#   Shape: 12729 x 89
#   Sample unitids: [100654, 100654, 100663]
#   Year values: [2020, 2021]
# 
#   institution_level distribution:
# shape: (4, 2)
# ┌───────────────────┬───────┐
# │ institution_level ┆ count │
# │ ---               ┆ ---   │
# │ i64               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ -1                ┆ 68    │
# │ 1                 ┆ 3594  │
# │ 2                 ┆ 3324  │
# │ 4                 ┆ 5743  │
# └───────────────────┴───────┘
# 
#   degree_granting distribution:
# shape: (3, 2)
# ┌─────────────────┬───────┐
# │ degree_granting ┆ count │
# │ ---             ┆ ---   │
# │ i64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ -1              ┆ 68    │
# │ 0               ┆ 4234  │
# │ 1               ┆ 8427  │
# └─────────────────┴───────┘
# 
# Filter year == 2020: 12,729 -> 6,440 (removed 6,289)
# Filter degree_granting == 1: 6,440 -> 4,250 (removed 2,190)
# Filter institution_level == 4: 4,250 -> 2,893 (removed 1,357)
# 
#   open_public: 0 coded values found -> replacing with null
# 
#   hbcu: 0 coded values found -> replacing with null
# 
#   tribal_college: 0 coded values found -> replacing with null
# 
#   inst_control coded values remaining: 0
#   inst_control unique values: [1, 2, 3]
# 
#   unitid uniqueness: 2,893 unique unitids in 2,893 rows
# 
# Selected 7 columns: ['unitid', 'inst_name', 'fips', 'inst_control', 'open_public', 'hbcu', 'tribal_college']
# 
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
# 
# Data Loss:
#   Raw rows:     12,729
#   Clean rows:   2,893
#   Rows removed: 9,836 (77.3%)
# [WARN] High data loss rate: 77.3%
# [PASS] Row count 2,893 within expected range (2500, 4500)
# 
# Suppression Rates (in raw year-filtered data):
# [PASS] open_public: 0.0% suppressed
# [PASS] hbcu: 0.0% suppressed
# [PASS] tribal_college: 0.0% suppressed
# 
# Coded Values Check (clean data):
# [PASS] No coded values remain in key variables
# 
# Null Summary (clean data):
#   unitid: 0 nulls
#   inst_name: 0 nulls
#   fips: 0 nulls
#   inst_control: 0 nulls
#   open_public: 0 nulls
#   hbcu: 0 nulls
#   tribal_college: 0 nulls
# 
# [INFO] Target year 2020 is a COVID-impacted year. Directory data (institutional characteristics) is less affected than enrollment/outcome data, but document in limitations.
# 
# Transformation Summary:
#   Filter year == 2020: 12,729 -> 6,440 (removed 6,289, 49.4%)
#   Filter degree_granting == 1: 6,440 -> 4,250 (removed 2,190, 34.0%)
#   Filter institution_level == 4: 4,250 -> 2,893 (removed 1,357, 31.9%)
# 
# CP2 VALIDATION: PASSED
# ============================================================
# 
# Post-state:
#   Rows: 2,893
#   Shape: 2893 x 7
#   Sample unitids: [100654, 100663, 100690]
#   Row change: -9,836 (-77.3%)
# 
#   inst_control distribution (1=public, 2=private nonprofit, 3=private for-profit):
# shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 852   │
# │ 2            ┆ 1671  │
# │ 3            ┆ 370   │
# └──────────────┴───────┘
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_directory_clean.parquet
# File size: 36,377 bytes (35.5 KB)
# 
# --- Citation ---
# IPEDS Institutional Characteristics, Education Data Portal (Version 0.20.0),
# Urban Institute, accessed March 29, 2026,
# https://educationdata.urban.org/documentation/,
# made available under the ODC Attribution License.
# 
# ============================================================
# STAGE 6.1 COMPLETE
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
