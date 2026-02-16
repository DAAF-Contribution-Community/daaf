#!/usr/bin/env python3
"""
Stage 6.3: Clean IPEDS admissions data -- replace coded missing values, compute admission_rate.

Task: clean-admissions
Wave: 3, Step: 3, Stage: 6
Depends on: fetch-admissions (COMPLETE)
Input: data/raw/2026-02-15_ipeds_admissions.parquet
Output: data/processed/2026-02-15_admissions_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# This script cleans IPEDS admissions data for a single year (2020, sex=99/total).
# Coded missing values (-1, -2, -3) are standard across the Education Data Portal
# and must be replaced with null before computing derived metrics.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_admissions.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_admissions_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data rather than null. These must be mapped to null so they don't corrupt
# downstream computations (e.g., admission_rate calculation would be invalid
# if -1 values were used as denominators or numerators).
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}

# Columns where coded values need replacement per Risk Register
ADMISSIONS_NUMERIC_COLS = ["number_applied", "number_admitted", "number_enrolled_total"]

# --- Load ---
# Load input data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.3: Clean IPEDS admissions data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Also enumerate coded values present so we can verify they're all removed.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Check for coded values in admissions numeric columns
print("\nCoded values found in admissions columns:")
coded_counts = {}
for col in ADMISSIONS_NUMERIC_COLS:
    if col in df.columns:
        for code, meaning in CODED_MISSING.items():
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                coded_counts[(col, code)] = count
                print(f"  {col} = {code} ({meaning}): {count:,}")

if not coded_counts:
    print("  (none found)")

# Document open-admission nulls per Risk Register
# INTENT: Check how many institutions have null admissions data (open-admission schools)
# REASONING: Open-admission institutions don't have application/admission counts,
# so their admissions fields will naturally be null. This is expected, not an error.
print("\nNull counts in admissions columns (pre-clean):")
for col in ADMISSIONS_NUMERIC_COLS:
    if col in df.columns:
        null_ct = df[col].null_count()
        print(f"  {col}: {null_ct:,} nulls ({null_ct / pre_rows * 100:.1f}%)")

# Check open_admissions_policy column if present
if "open_admissions_policy" in df.columns:
    oa_counts = df["open_admissions_policy"].value_counts().sort("open_admissions_policy")
    print(f"\nOpen admissions policy distribution:")
    for row in oa_counts.iter_rows(named=True):
        print(f"  {row['open_admissions_policy']}: {row['count']:,}")

# Capture a reference snapshot: first 3 unitids for before/after comparison
sample_ids = df["unitid"].head(3).to_list()
print(f"\nSample unitids for tracking: {sample_ids}")
sample_before = df.filter(pl.col("unitid").is_in(sample_ids)).select(
    ["unitid"] + [c for c in ADMISSIONS_NUMERIC_COLS if c in df.columns]
)
print(f"Sample before:\n{sample_before}")

# --- Transform ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in all admissions
# numeric columns so downstream admission_rate computation is not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation -- these values were never observed. Zero would imply
# no applicants/admits which is different from "not reported." Using null also
# ensures Polars aggregation functions (mean, median) skip these values correctly.
#
# ASSUMES: All coded values in ADMISSIONS_NUMERIC_COLS are in the CODED_MISSING dict
# per IPEDS source documentation (education-data-context skill).
raw_df = df.clone()  # Keep copy for CP2 suppression check

for col in ADMISSIONS_NUMERIC_COLS:
    if col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(col).is_in(list(CODED_MISSING.keys())))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )

print("\nReplaced coded missing values with null in admissions columns")

# --- Derive admission_rate ---
# INTENT: Compute admission_rate = number_admitted / number_applied as our
# primary selectivity measure. This is the core metric for the research question
# about whether graduation rates reflect selectivity vs. institutional quality.
#
# REASONING: admission_rate computed as a proportion (0-1 scale) rather than
# percentage (0-100) to follow standard statistical convention. This makes it
# directly usable in regression models and correlation analyses.
#
# Set admission_rate to null where:
#   - number_applied is null (institution didn't report or is open-admission)
#   - number_applied is 0 (cannot divide by zero; shouldn't occur for reporting institutions)
#   - number_admitted is null (institution didn't report)
#
# ASSUMES:
#   - number_applied > 0 for all institutions that report admissions data
#   - number_admitted <= number_applied for valid institutions (admission_rate in [0, 1])
#   - Open-admission institutions will have null number_applied (documented in Risk Register)
df = df.with_columns(
    pl.when(
        pl.col("number_applied").is_not_null()
        & pl.col("number_admitted").is_not_null()
        & (pl.col("number_applied") > 0)
    )
    .then(pl.col("number_admitted") / pl.col("number_applied"))
    .otherwise(None)
    .alias("admission_rate")
)

print("\nComputed admission_rate = number_admitted / number_applied")

# --- Post-state ---
post_rows = df.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {len(df.columns)} cols")
print(f"Row change: {((post_rows - pre_rows) / pre_rows * 100):+.1f}%")

# Print admission_rate distribution
# INTENT: Report distribution statistics for the derived admission_rate to verify
# it falls within expected range [0, 1] and to document null rate.
admission_rate_valid = df.filter(pl.col("admission_rate").is_not_null())["admission_rate"]
admission_rate_null_count = df["admission_rate"].null_count()

print(f"\nAdmission rate distribution:")
print(f"  Non-null count: {len(admission_rate_valid):,}")
print(f"  Null count:     {admission_rate_null_count:,} ({admission_rate_null_count / post_rows * 100:.1f}%)")
if len(admission_rate_valid) > 0:
    print(f"  Min:    {admission_rate_valid.min():.4f}")
    print(f"  Max:    {admission_rate_valid.max():.4f}")
    print(f"  Mean:   {admission_rate_valid.mean():.4f}")
    print(f"  Median: {admission_rate_valid.median():.4f}")
    print(f"  Std:    {admission_rate_valid.std():.4f}")

# Verify admission_rate is between 0 and 1 for all non-null values
out_of_range = df.filter(
    pl.col("admission_rate").is_not_null()
    & ((pl.col("admission_rate") < 0) | (pl.col("admission_rate") > 1))
)
if out_of_range.height > 0:
    print(f"\n  [WARN] {out_of_range.height} institutions have admission_rate outside [0, 1]!")
    print(f"  Sample out-of-range:")
    print(out_of_range.select(["unitid", "number_applied", "number_admitted", "admission_rate"]).head(5))
else:
    print(f"  [PASS] All non-null admission_rate values are in [0, 1]")

# Show sample after transformation
sample_after = df.filter(pl.col("unitid").is_in(sample_ids)).select(
    ["unitid"] + [c for c in ADMISSIONS_NUMERIC_COLS if c in df.columns] + ["admission_rate"]
)
print(f"\nSample after:\n{sample_after}")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size:,} bytes")

# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning operations -- confirm coded values
# are removed, suppression rates are within tolerance, and row count is preserved.
# ASSUMES: raw_df is pre-cleaning state, df is post-cleaning state.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True
max_suppression = 0.5  # 50% threshold per CLAUDE.md STOP conditions

# CP2.1: Row count preserved (cleaning replaces values but should not drop rows)
rows_preserved = post_rows == pre_rows
print(f"\n  [{'PASS' if rows_preserved else 'FAIL'}] Rows preserved: {pre_rows:,} -> {post_rows:,}")
if not rows_preserved:
    cp2_passed = False

# CP2.2: No coded values remain in cleaned data
print(f"\nCoded Values Check (clean data):")
coded_remaining = 0
for col in ADMISSIONS_NUMERIC_COLS:
    if col in df.columns:
        for code in CODED_MISSING.keys():
            count = df.filter(pl.col(col) == code).height
            coded_remaining += count
            if count > 0:
                print(f"  [FAIL] {col} still has {count:,} coded value {code}")

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")
if not no_coded:
    cp2_passed = False

# CP2.3: Suppression rate check (on raw data)
# REASONING: The 50% threshold is from CLAUDE.md STOP conditions. Above 50%
# suppression, the remaining data is too sparse to support reliable analysis.
print(f"\nSuppression Rates (in raw data):")
for col in ADMISSIONS_NUMERIC_COLS:
    if col in raw_df.columns:
        suppressed = raw_df.filter(pl.col(col) == -3).height
        supp_rate = suppressed / pre_rows if pre_rows > 0 else 0
        status = "PASS" if supp_rate < max_suppression else "FAIL"
        if supp_rate > 0.2:
            status = "WARN" if supp_rate < max_suppression else "FAIL"
        print(f"  [{status}] {col}: {supp_rate:.1%} suppressed ({suppressed:,} of {pre_rows:,})")
        if supp_rate >= max_suppression:
            cp2_passed = False

# CP2.4: Null rate in key columns after cleaning (informational)
print(f"\nNull Rates (clean data):")
for col in ADMISSIONS_NUMERIC_COLS + ["admission_rate"]:
    if col in df.columns:
        null_ct = df[col].null_count()
        null_pct = null_ct / post_rows * 100
        print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

# CP2.5: admission_rate range validation
rate_in_range = out_of_range.height == 0
print(f"\n  [{'PASS' if rate_in_range else 'FAIL'}] admission_rate in [0, 1]: {out_of_range.height} out-of-range values")
if not rate_in_range:
    cp2_passed = False

# CP2.6: admission_rate null rate documented
print(f"  [PASS] admission_rate null rate documented: {admission_rate_null_count:,} ({admission_rate_null_count / post_rows * 100:.1f}%)")

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:38:34
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage6_clean/03_clean-admissions.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.3: Clean IPEDS admissions data
# ============================================================
# Loaded: 1,989 rows x 5 cols
# Columns: ['unitid', 'year', 'number_applied', 'number_admitted', 'number_enrolled_total']
# 
# Pre-state: 1,989 rows, 5 cols
# 
# Coded values found in admissions columns:
#   (none found)
# 
# Null counts in admissions columns (pre-clean):
#   number_applied: 0 nulls (0.0%)
#   number_admitted: 23 nulls (1.2%)
#   number_enrolled_total: 25 nulls (1.3%)
# 
# Sample unitids for tracking: [100654, 100663, 100706]
# Sample before:
# shape: (3, 4)
# ┌────────┬────────────────┬─────────────────┬───────────────────────┐
# │ unitid ┆ number_applied ┆ number_admitted ┆ number_enrolled_total │
# │ ---    ┆ ---            ┆ ---             ┆ ---                   │
# │ i64    ┆ i64            ┆ i64             ┆ i64                   │
# ╞════════╪════════════════╪═════════════════╪═══════════════════════╡
# │ 100654 ┆ 9855           ┆ 8835            ┆ 1664                  │
# │ 100663 ┆ 10391          ┆ 8375            ┆ 2154                  │
# │ 100706 ┆ 5793           ┆ 4467            ┆ 1345                  │
# └────────┴────────────────┴─────────────────┴───────────────────────┘
# 
# Replaced coded missing values with null in admissions columns
# 
# Computed admission_rate = number_admitted / number_applied
# 
# Post-state: 1,989 rows, 6 cols
# Row change: +0.0%
# 
# Admission rate distribution:
#   Non-null count: 1,966
#   Null count:     23 (1.2%)
#   Min:    0.0000
#   Max:    1.0000
#   Mean:   0.7122
#   Median: 0.7522
#   Std:    0.2133
#   [PASS] All non-null admission_rate values are in [0, 1]
# 
# Sample after:
# shape: (3, 5)
# ┌────────┬────────────────┬─────────────────┬───────────────────────┬────────────────┐
# │ unitid ┆ number_applied ┆ number_admitted ┆ number_enrolled_total ┆ admission_rate │
# │ ---    ┆ ---            ┆ ---             ┆ ---                   ┆ ---            │
# │ i64    ┆ i64            ┆ i64             ┆ i64                   ┆ f64            │
# ╞════════╪════════════════╪═════════════════╪═══════════════════════╪════════════════╡
# │ 100654 ┆ 9855           ┆ 8835            ┆ 1664                  ┆ 0.896499       │
# │ 100663 ┆ 10391          ┆ 8375            ┆ 2154                  ┆ 0.805986       │
# │ 100706 ┆ 5793           ┆ 4467            ┆ 1345                  ┆ 0.771103       │
# └────────┴────────────────┴─────────────────┴───────────────────────┴────────────────┘
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_admissions_clean.parquet
# File size: 32,524 bytes
# 
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
# 
#   [PASS] Rows preserved: 1,989 -> 1,989
# 
# Coded Values Check (clean data):
#   [PASS] No coded values remaining: 0
# 
# Suppression Rates (in raw data):
#   [PASS] number_applied: 0.0% suppressed (0 of 1,989)
#   [PASS] number_admitted: 0.0% suppressed (0 of 1,989)
#   [PASS] number_enrolled_total: 0.0% suppressed (0 of 1,989)
# 
# Null Rates (clean data):
#   number_applied: 0 nulls (0.0%)
#   number_admitted: 23 nulls (1.2%)
#   number_enrolled_total: 25 nulls (1.3%)
#   admission_rate: 23 nulls (1.2%)
# 
#   [PASS] admission_rate in [0, 1]: 0 out-of-range values
#   [PASS] admission_rate null rate documented: 23 (1.2%)
# 
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
