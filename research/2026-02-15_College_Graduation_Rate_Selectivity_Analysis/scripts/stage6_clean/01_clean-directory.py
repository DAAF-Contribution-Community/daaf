#!/usr/bin/env python3
"""
Stage 6.3: Clean IPEDS directory data — replace coded missing values with null,
verify pre-applied filters, drop entirely-null column, report value distributions.

Task: clean-directory
Wave: 3, Step: 3, Stage: 6
Depends on: fetch-directory (COMPLETE)
Input: data/raw/2026-02-15_ipeds_directory.parquet
Output: data/processed/2026-02-15_directory_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for IPEDS directory cleaning. The raw data was
# fetched in Stage 5 with filters: inst_control in [1,2], institution_level == 4,
# year == 2020. This script cleans coded missing values and verifies the filters
# are intact. The cc_basic_2021 column is 100% null (not populated for year=2020)
# and will be dropped as it provides no analytical value.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_directory.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_directory_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data in numeric columns. These must be mapped to null to avoid corrupting
# downstream statistical calculations. For IPEDS data, -1 means missing/not
# reported, -2 means not applicable, -3 means suppressed for privacy.
CODED_MISSING = [-1, -2, -3]

# Numeric columns to scan for coded values. We check ALL numeric columns
# (excluding identifiers like unitid, year, fips which should never have
# coded values) to ensure thorough cleaning.
NUMERIC_COLS_TO_CLEAN = [
    "inst_control", "institution_level", "hbcu", "degree_granting",
    "urban_centric_locale", "cc_basic_2021",
]

# --- Load ---
# Load raw IPEDS directory data and verify shape matches Stage 5 output.
print("=" * 60)
print("Stage 6.3: Clean IPEDS directory data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE any cleaning for post-validation comparison.
# Also enumerate coded values present so we can verify they're all removed.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_shape = df.shape
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Enumerate coded values in numeric columns before cleaning
print("\nCoded values found in raw data:")
coded_counts = {}
for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        for code in CODED_MISSING:
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                coded_counts[(col, code)] = count
                print(f"  {col} == {code}: {count:,} rows")

if not coded_counts:
    print("  (none found)")

# Check for null column: cc_basic_2021
# REASONING: Stage 5 confirmed cc_basic_2021 is 100% null for year=2020.
# This column provides Carnegie Classification which is not populated for
# this data year, so it carries no analytical value and should be dropped
# to keep the dataset clean.
cc_null_count = df["cc_basic_2021"].null_count()
cc_null_pct = cc_null_count / len(df) * 100
print(f"\ncc_basic_2021 null rate: {cc_null_pct:.1f}% ({cc_null_count:,} / {len(df):,})")

# --- Transform: Replace coded missing values ---
# INTENT: Replace Education Data Portal coded missing values (-1, -2, -3)
# with null in all numeric columns so downstream statistical operations
# are not corrupted by sentinel values being treated as real data.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation — these values were never observed. Polars natively
# excludes nulls from aggregations (mean, sum, etc.), which is the correct
# behavior for missing data.
#
# ASSUMES:
#   - Coded values only appear in NUMERIC_COLS_TO_CLEAN (not in unitid, year, fips)
#   - Stage 5 findings confirmed only urban_centric_locale has coded values (-1)
#   - cc_basic_2021 is 100% null (no coded values to replace, but we scan it anyway)
print("\n--- Replacing coded values with null ---")
for col in NUMERIC_COLS_TO_CLEAN:
    if col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(col).is_in(CODED_MISSING))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )
print("Coded value replacement complete.")

# --- Transform: Drop cc_basic_2021 (100% null) ---
# INTENT: Remove the entirely-null column that provides no analytical value.
# REASONING: Keeping a 100% null column would be misleading — it might suggest
# the analysis intended to use Carnegie Classifications but failed to populate
# them. Dropping it makes the dataset schema reflect only usable variables.
df = df.drop("cc_basic_2021")
print(f"Dropped cc_basic_2021 (was 100% null)")

# --- Post-state ---
# Capture state AFTER cleaning for comparison and CP2 validation.
post_rows = df.shape[0]
post_cols = df.columns.copy()
print(f"\nPost-state: {post_rows:,} rows, {len(post_cols)} cols")
print(f"Row change: {((post_rows - pre_rows) / pre_rows * 100):+.1f}%")
print(f"Column change: {len(pre_cols)} -> {len(post_cols)} (dropped cc_basic_2021)")
print(f"Columns: {post_cols}")

# --- Verify pre-applied filters ---
# INTENT: Confirm that the filters applied during Stage 5 fetch are still intact.
# The raw data should already contain only: inst_control in [1,2] (public and
# private nonprofit), institution_level == 4 (4-year institutions), year == 2020.
#
# REASONING: This is a defensive check — if the raw data somehow includes
# for-profit institutions (inst_control == 3) or non-4-year institutions,
# the analysis would be compromised. We verify rather than re-filter to
# preserve audit trail transparency.
print("\n--- Verifying pre-applied filters ---")

# Check inst_control: should be only 1 (public) and 2 (private nonprofit)
inst_control_vals = sorted(df["inst_control"].drop_nulls().unique().to_list())
inst_control_ok = set(inst_control_vals) <= {1, 2}
print(f"inst_control values: {inst_control_vals} -> {'PASS' if inst_control_ok else 'FAIL'}")

# Check no for-profit (inst_control == 3) present
forprofit_count = df.filter(pl.col("inst_control") == 3).height
no_forprofit = forprofit_count == 0
print(f"For-profit institutions (inst_control==3): {forprofit_count} -> {'PASS' if no_forprofit else 'FAIL'}")

# Check institution_level: should be only 4 (4-year or above)
inst_level_vals = sorted(df["institution_level"].unique().to_list())
inst_level_ok = inst_level_vals == [4]
print(f"institution_level values: {inst_level_vals} -> {'PASS' if inst_level_ok else 'FAIL'}")

# --- Value distributions for key columns ---
# INTENT: Report value distributions for key categorical columns to provide
# context for downstream analysis and enable QA review.
print("\n--- Value distributions ---")

print(f"\ninst_control (1=Public, 2=Private nonprofit):")
print(df["inst_control"].value_counts().sort("inst_control"))

print(f"\nhbcu (0=No, 1=Yes):")
print(df["hbcu"].value_counts().sort("hbcu"))

print(f"\ndegree_granting (0=No, 1=Yes):")
print(df["degree_granting"].value_counts().sort("degree_granting"))

print(f"\nurban_centric_locale (after coded value replacement):")
locale_vc = df["urban_centric_locale"].value_counts().sort("urban_centric_locale")
print(locale_vc)
locale_null = df["urban_centric_locale"].null_count()
print(f"  null count: {locale_null}")

# --- Save ---
# Persist cleaned results in parquet format.
# REASONING: Parquet preserves schema, compresses well, and is the mandatory
# format per DAAF conventions.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning operations — confirm coded values
# are removed, suppression rates are within tolerance, and data loss is acceptable.
# ASSUMES: raw data was the pre-cleaning state, df is the post-cleaning state.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True

# CP2.1: No coded values remain in numeric columns
# REASONING: After replacement, no numeric column should contain -1, -2, or -3.
# We check all remaining numeric columns (cc_basic_2021 was dropped).
print("\nCP2.1: Coded values check")
coded_remaining = 0
numeric_cols_remaining = [c for c in NUMERIC_COLS_TO_CLEAN if c in df.columns]
for col in numeric_cols_remaining:
    for code in CODED_MISSING:
        count = df.filter(pl.col(col) == code).height
        coded_remaining += count
        if count > 0:
            print(f"  [FAIL] {col} == {code}: {count:,} rows still present")

# Also check unitid, year, fips just to be thorough
for col in ["unitid", "year", "fips"]:
    if col in df.columns:
        for code in CODED_MISSING:
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                print(f"  [WARN] {col} == {code}: {count:,} (unexpected in identifier)")

no_coded = coded_remaining == 0
if no_coded:
    print(f"  [PASS] No coded values (-1, -2, -3) remain in cleaned numeric columns")
else:
    print(f"  [FAIL] {coded_remaining} coded values still present")
    cp2_passed = False

# CP2.2: Suppression rate check
# REASONING: The task specification asks to calculate suppression rate for
# enrollment_undergrad. However, enrollment_undergrad is NOT in the directory
# dataset — it comes from a separate IPEDS admissions/enrollment fetch.
# For the directory dataset, we calculate suppression across all numeric columns
# as a general quality metric. The 50% threshold is from CLAUDE.md STOP conditions.
print("\nCP2.2: Suppression rate check")
total_cells = 0
null_cells = 0
for col in numeric_cols_remaining:
    col_total = len(df)
    col_null = df[col].null_count()
    total_cells += col_total
    null_cells += col_null
    null_pct = col_null / col_total * 100 if col_total > 0 else 0
    if null_pct > 0:
        print(f"  {col}: {col_null:,} nulls ({null_pct:.1f}%)")

overall_suppression = null_cells / total_cells if total_cells > 0 else 0
suppression_ok = overall_suppression < 0.50
print(f"  Overall suppression rate: {overall_suppression:.1%} ({null_cells:,} / {total_cells:,})")
if suppression_ok:
    print(f"  [PASS] Suppression rate {overall_suppression:.1%} < 50%")
else:
    print(f"  [FAIL] Suppression rate {overall_suppression:.1%} >= 50%")
    cp2_passed = False

# CP2.3: Row count preserved
# REASONING: Cleaning replaces coded values with null and drops one column,
# but should NOT drop any rows. Row count must be unchanged.
print("\nCP2.3: Row count preservation")
rows_preserved = post_rows == pre_rows
if rows_preserved:
    print(f"  [PASS] Rows preserved: {pre_rows:,} -> {post_rows:,}")
else:
    print(f"  [WARN] Row count changed: {pre_rows:,} -> {post_rows:,}")

# CP2.4: Filter integrity
# REASONING: Verify the pre-applied filters from Stage 5 are still intact
# after cleaning operations.
print("\nCP2.4: Filter integrity")
if inst_control_ok:
    print(f"  [PASS] inst_control only 1 or 2")
else:
    print(f"  [FAIL] inst_control has unexpected values: {inst_control_vals}")
    cp2_passed = False

if no_forprofit:
    print(f"  [PASS] No for-profit institutions")
else:
    print(f"  [FAIL] {forprofit_count} for-profit institutions found")
    cp2_passed = False

if inst_level_ok:
    print(f"  [PASS] institution_level only 4")
else:
    print(f"  [FAIL] institution_level has unexpected values: {inst_level_vals}")
    cp2_passed = False

# CP2.5: Output file verification
print("\nCP2.5: Output file verification")
if OUTPUT_PATH.exists():
    file_size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"  [PASS] Output file exists: {OUTPUT_PATH} ({file_size_kb:.1f} KB)")

    # Verify readable
    verify_df = pl.read_parquet(OUTPUT_PATH)
    readback_ok = verify_df.shape == df.shape
    if readback_ok:
        print(f"  [PASS] File readable, shape matches: {verify_df.shape}")
    else:
        print(f"  [FAIL] Shape mismatch: written={df.shape}, read={verify_df.shape}")
        cp2_passed = False
else:
    print(f"  [FAIL] Output file not found: {OUTPUT_PATH}")
    cp2_passed = False

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:38:24
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/01_clean-directory.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.3: Clean IPEDS directory data
# ============================================================
# Loaded: 2,528 rows x 11 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'cc_basic_2021', 'state_abbr', 'fips']
# 
# Pre-state: 2,528 rows, 11 cols
# 
# Coded values found in raw data:
#   urban_centric_locale == -1: 2 rows
# 
# cc_basic_2021 null rate: 100.0% (2,528 / 2,528)
# 
# --- Replacing coded values with null ---
# Coded value replacement complete.
# Dropped cc_basic_2021 (was 100% null)
# 
# Post-state: 2,528 rows, 10 cols
# Row change: +0.0%
# Column change: 11 -> 10 (dropped cc_basic_2021)
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips']
# 
# --- Verifying pre-applied filters ---
# inst_control values: [1, 2] -> PASS
# For-profit institutions (inst_control==3): 0 -> PASS
# institution_level values: [4] -> PASS
# 
# --- Value distributions ---
# 
# inst_control (1=Public, 2=Private nonprofit):
# shape: (2, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 852   │
# │ 2            ┆ 1676  │
# └──────────────┴───────┘
# 
# hbcu (0=No, 1=Yes):
# shape: (2, 2)
# ┌──────┬───────┐
# │ hbcu ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 0    ┆ 2437  │
# │ 1    ┆ 91    │
# └──────┴───────┘
# 
# degree_granting (0=No, 1=Yes):
# shape: (2, 2)
# ┌─────────────────┬───────┐
# │ degree_granting ┆ count │
# │ ---             ┆ ---   │
# │ i64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 0               ┆ 5     │
# │ 1               ┆ 2523  │
# └─────────────────┴───────┘
# 
# urban_centric_locale (after coded value replacement):
# shape: (13, 2)
# ┌──────────────────────┬───────┐
# │ urban_centric_locale ┆ count │
# │ ---                  ┆ ---   │
# │ i64                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ null                 ┆ 2     │
# │ 11                   ┆ 645   │
# │ 12                   ┆ 305   │
# │ 13                   ┆ 344   │
# │ 21                   ┆ 511   │
# │ …                    ┆ …     │
# │ 32                   ┆ 218   │
# │ 33                   ┆ 135   │
# │ 41                   ┆ 101   │
# │ 42                   ┆ 43    │
# │ 43                   ┆ 31    │
# └──────────────────────┴───────┘
#   null count: 2
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_directory_clean.parquet
# 
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
# 
# CP2.1: Coded values check
#   [PASS] No coded values (-1, -2, -3) remain in cleaned numeric columns
# 
# CP2.2: Suppression rate check
#   urban_centric_locale: 2 nulls (0.1%)
#   Overall suppression rate: 0.0% (2 / 12,640)
#   [PASS] Suppression rate 0.0% < 50%
# 
# CP2.3: Row count preservation
#   [PASS] Rows preserved: 2,528 -> 2,528
# 
# CP2.4: Filter integrity
#   [PASS] inst_control only 1 or 2
#   [PASS] No for-profit institutions
#   [PASS] institution_level only 4
# 
# CP2.5: Output file verification
#   [PASS] Output file exists: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_directory_clean.parquet (34.1 KB)
#   [PASS] File readable, shape matches: (2528, 10)
# 
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
