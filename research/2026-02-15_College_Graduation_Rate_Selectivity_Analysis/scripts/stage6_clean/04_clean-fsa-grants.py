#!/usr/bin/env python3
"""
Stage 6.4: Clean FSA grants data — replace coded missing values, round fractional
pell_recipients, validate data quality.

Task: clean-fsa-grants
Wave: 3, Step: 4, Stage: 6
Depends on: fetch-fsa-grants (COMPLETE)
Input: data/raw/2026-02-15_fsa_grants.parquet
Output: data/processed/2026-02-15_fsa_grants_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for FSA grants cleaning. The raw data contains
# year=2020, grant_type=4 (Pell Grant) records fetched in Stage 5.
# Coded missing values (-1, -2, -3) are standard across the Education Data
# Portal and must be replaced with null before any statistical computation.
# Additionally, 38 rows (~0.76%) have fractional pell_recipients from
# allocation splits — these are rounded to integer per QA1 guidance.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_fsa_grants.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_fsa_grants_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data rather than null. These must be mapped to null so they don't corrupt
# downstream statistical calculations (e.g., mean Pell recipients would be
# dragged down by -1 values if left in place).
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}

# INTENT: Target columns for coded value cleaning. These are the numeric measure
# columns in the FSA grants dataset that could contain coded missing values.
# Categorical/identifier columns (unitid, year, grant_type) do not use coded values.
NUMERIC_COLS = ["pell_recipients", "pell_disbursements"]

# --- Load ---
# Load raw FSA grants data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.4: Clean FSA grants data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Also enumerate coded values present so we can verify they're all removed,
# and count fractional pell_recipients for rounding verification.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Check for coded missing values in numeric columns
print("\nCoded values found in raw data:")
coded_counts = {}
for col in NUMERIC_COLS:
    if col in df.columns:
        for code, meaning in CODED_MISSING.items():
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                coded_counts[(col, code)] = count
                print(f"  {col} = {code} ({meaning}): {count:,}")

if not coded_counts:
    print("  None found")

# INTENT: Count fractional pell_recipients before rounding so we can verify
# the rounding operation affects the expected number of rows (38 per QA1).
# ASSUMES: pell_recipients is a numeric column. Fractional values arise from
# allocation splits where institutions share students.
fractional_count = 0
if "pell_recipients" in df.columns:
    # Check for non-integer values by comparing col to its rounded version
    fractional_mask = (
        pl.col("pell_recipients").is_not_null()
        & (pl.col("pell_recipients") != pl.col("pell_recipients").round(0))
    )
    fractional_count = df.filter(fractional_mask).height
    print(f"\nFractional pell_recipients: {fractional_count} rows")

# Print sample of first few rows for reference
print(f"\nSample (first 5 rows):")
print(df.head(5))

# --- Clean: Replace coded missing values ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in all numeric
# measure columns so downstream statistical operations are not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation — these values were never observed or are not applicable.
# Zero would imply a measured value of zero (a real institution with zero Pell
# recipients), and NaN would complicate Polars aggregations.
#
# ASSUMES: All coded values in NUMERIC_COLS are in the CODED_MISSING dict
# per Education Data Portal convention (education-data-context skill).
print("\n" + "-" * 60)
print("Cleaning Step 1: Replace coded missing values with null")
print("-" * 60)

coded_values_list = list(CODED_MISSING.keys())
for col in NUMERIC_COLS:
    if col in df.columns:
        # Count how many will be replaced for this column
        replace_count = df.filter(pl.col(col).is_in(coded_values_list)).height
        df = df.with_columns(
            pl.when(pl.col(col).is_in(coded_values_list))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )
        print(f"  {col}: replaced {replace_count} coded values with null")

# --- Clean: Round fractional pell_recipients ---
# INTENT: Round pell_recipients to integer to address fractional values from
# allocation splits (38 rows per Stage 5 QA1 finding).
#
# REASONING: Pell recipients are counts of people — fractional values arise
# from administrative allocation splits between institutions, not from actual
# fractional students. Rounding to nearest integer is the standard approach
# and was recommended by QA1 as a benign cleanup step. Using round(0) which
# rounds to nearest integer (banker's rounding in Polars).
#
# ASSUMES: Fractional values are from allocation splits only (confirmed by
# Stage 5 QA1 which found 38 fractional rows, 0.76% of total).
print("\n" + "-" * 60)
print("Cleaning Step 2: Round fractional pell_recipients to integer")
print("-" * 60)

if "pell_recipients" in df.columns:
    df = df.with_columns(
        pl.col("pell_recipients").round(0).alias("pell_recipients")
    )
    # Verify no fractional values remain
    post_fractional = df.filter(
        pl.col("pell_recipients").is_not_null()
        & (pl.col("pell_recipients") != pl.col("pell_recipients").round(0))
    ).height
    print(f"  Fractional before: {fractional_count}")
    print(f"  Fractional after:  {post_fractional}")

# --- Post-state ---
# Capture state AFTER transformation for comparison with pre-state.
post_rows = df.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {df.shape[1]} cols")
print(f"Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100 if pre_rows > 0 else 0:+.1f}%)")

# --- Distribution check for pell_recipients ---
# INTENT: Print distribution statistics for pell_recipients to verify
# the cleaned data has reasonable values (no coded values, no negatives,
# sensible range for Pell Grant recipient counts at institutions).
print("\n" + "-" * 60)
print("Distribution: pell_recipients (after cleaning)")
print("-" * 60)

if "pell_recipients" in df.columns:
    pell_col = df["pell_recipients"]
    pell_non_null = pell_col.drop_nulls()
    print(f"  Total rows:  {pell_col.len():,}")
    print(f"  Non-null:    {pell_non_null.len():,}")
    print(f"  Null count:  {pell_col.null_count():,}")
    print(f"  Null rate:   {pell_col.null_count() / pell_col.len() * 100:.2f}%")
    if pell_non_null.len() > 0:
        print(f"  Min:         {pell_non_null.min()}")
        print(f"  Max:         {pell_non_null.max():,}")
        print(f"  Mean:        {pell_non_null.mean():,.1f}")
        print(f"  Median:      {pell_non_null.median():,.1f}")
        print(f"  Std:         {pell_non_null.std():,.1f}")

# --- Distribution check for pell_disbursements ---
print("\n" + "-" * 60)
print("Distribution: pell_disbursements (after cleaning)")
print("-" * 60)

if "pell_disbursements" in df.columns:
    disb_col = df["pell_disbursements"]
    disb_non_null = disb_col.drop_nulls()
    print(f"  Total rows:  {disb_col.len():,}")
    print(f"  Non-null:    {disb_non_null.len():,}")
    print(f"  Null count:  {disb_col.null_count():,}")
    print(f"  Null rate:   {disb_col.null_count() / disb_col.len() * 100:.2f}%")
    if disb_non_null.len() > 0:
        print(f"  Min:         {disb_non_null.min()}")
        print(f"  Max:         {disb_non_null.max():,}")
        print(f"  Mean:        {disb_non_null.mean():,.1f}")
        print(f"  Median:      {disb_non_null.median():,.1f}")

# --- Save ---
# Persist results in parquet format.
# Output paths match the Plan's file specification.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, suppression rate
# is within acceptable bounds, row count is preserved (cleaning replaces
# values but should not drop rows), and pell_recipients are non-negative.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

cp2_passed = True

# CP2.1: No coded values remain in numeric columns
coded_remaining = 0
for col in NUMERIC_COLS:
    if col in df.columns:
        for code in CODED_MISSING.keys():
            coded_remaining += df.filter(pl.col(col) == code).height

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")
if not no_coded:
    cp2_passed = False

# CP2.2: pell_recipients >= 0 for all non-null values
# REASONING: Pell recipient counts must be non-negative. Any negative values
# would indicate coded values that weren't properly cleaned or data corruption.
if "pell_recipients" in df.columns:
    neg_count = df.filter(
        pl.col("pell_recipients").is_not_null() & (pl.col("pell_recipients") < 0)
    ).height
    non_neg_ok = neg_count == 0
    print(f"  [{'PASS' if non_neg_ok else 'FAIL'}] pell_recipients >= 0 (non-null): {neg_count} negative values")
    if not non_neg_ok:
        cp2_passed = False

# CP2.3: Null rate for pell_recipients < 30%
# REASONING: If more than 30% of institutions have null Pell recipient data,
# the dataset's usefulness for analyzing Pell participation patterns is limited.
# The 30% threshold is a practical cutoff — above it, selection bias becomes
# a major concern for any Pell-based analysis.
if "pell_recipients" in df.columns:
    pell_null_rate = df["pell_recipients"].null_count() / len(df)
    null_rate_ok = pell_null_rate < 0.30
    print(f"  [{'PASS' if null_rate_ok else 'FAIL'}] pell_recipients null rate < 30%: {pell_null_rate:.1%}")
    if not null_rate_ok:
        cp2_passed = False

# CP2.4: Row count preserved (cleaning should not drop rows)
# REASONING: This cleaning script replaces values and rounds, but should not
# remove any rows. Row count change would indicate an unintended filter operation.
rows_preserved = post_rows == pre_rows
print(f"  [{'PASS' if rows_preserved else 'WARN'}] Rows preserved: {pre_rows:,} -> {post_rows:,}")
if not rows_preserved:
    print(f"    WARNING: Row count changed during cleaning (expected 0 change)")

# CP2.5: Suppression rate < 50%
# REASONING: The 50% threshold is from CLAUDE.md STOP conditions. Above 50%
# suppression, the remaining data is too sparse to support reliable analysis.
total_cells = len(df) * len([c for c in NUMERIC_COLS if c in df.columns])
null_cells = sum(df[col].null_count() for col in NUMERIC_COLS if col in df.columns)
suppression_rate = null_cells / total_cells if total_cells > 0 else 0
suppression_ok = suppression_rate < 0.50
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: {suppression_rate:.1%}")
if not suppression_ok:
    cp2_passed = False

# CP2.6: Expected row count matches (4,994 from Stage 5)
expected_rows = 4994
row_count_ok = post_rows == expected_rows
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Expected row count ({expected_rows:,}): {post_rows:,}")

print(f"\n{'=' * 60}")
print(f"CP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print(f"{'=' * 60}")

assert no_coded, "STOP: Coded values still present after cleaning"
assert non_neg_ok, "STOP: Negative pell_recipients found after cleaning"
assert null_rate_ok, "STOP: pell_recipients null rate >= 30%"
assert suppression_ok, "STOP: Suppression rate >= 50%"


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:38:50
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/04_clean-fsa-grants.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.4: Clean FSA grants data
# ============================================================
# Loaded: 4,994 rows x 4 cols
# Columns: ['unitid', 'year', 'pell_recipients', 'pell_disbursements']
# Dtypes: [Int64, Int64, Float64, Float64]
# 
# Pre-state: 4,994 rows, 4 cols
# 
# Coded values found in raw data:
#   None found
# 
# Fractional pell_recipients: 38 rows
# 
# Sample (first 5 rows):
# shape: (5, 4)
# ┌────────┬──────┬─────────────────┬────────────────────┐
# │ unitid ┆ year ┆ pell_recipients ┆ pell_disbursements │
# │ ---    ┆ ---  ┆ ---             ┆ ---                │
# │ i64    ┆ i64  ┆ f64             ┆ f64                │
# ╞════════╪══════╪═════════════════╪════════════════════╡
# │ 100654 ┆ 2020 ┆ 3607.0          ┆ 1.8499612e7        │
# │ 100663 ┆ 2020 ┆ 4966.0          ┆ 2.3012828e7        │
# │ 100690 ┆ 2020 ┆ 270.0           ┆ 1.0310e6           │
# │ 100706 ┆ 2020 ┆ 2048.0          ┆ 8.986248e6         │
# │ 100724 ┆ 2020 ┆ 2465.0          ┆ 1.2532547e7        │
# └────────┴──────┴─────────────────┴────────────────────┘
# 
# ------------------------------------------------------------
# Cleaning Step 1: Replace coded missing values with null
# ------------------------------------------------------------
#   pell_recipients: replaced 0 coded values with null
#   pell_disbursements: replaced 0 coded values with null
# 
# ------------------------------------------------------------
# Cleaning Step 2: Round fractional pell_recipients to integer
# ------------------------------------------------------------
#   Fractional before: 38
#   Fractional after:  0
# 
# Post-state: 4,994 rows, 4 cols
# Row change: +0 (+0.0%)
# 
# ------------------------------------------------------------
# Distribution: pell_recipients (after cleaning)
# ------------------------------------------------------------
#   Total rows:  4,994
#   Non-null:    4,988
#   Null count:  6
#   Null rate:   0.12%
#   Min:         0.0
#   Max:         70,813.0
#   Mean:        1,269.1
#   Median:      362.0
#   Std:         2,970.5
# 
# ------------------------------------------------------------
# Distribution: pell_disbursements (after cleaning)
# ------------------------------------------------------------
#   Total rows:  4,994
#   Non-null:    4,988
#   Null count:  6
#   Null rate:   0.12%
#   Min:         0.0
#   Max:         224,762,800.0
#   Mean:        5,284,427.3
#   Median:      1,561,568.1
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_fsa_grants_clean.parquet
# File size: 39.0 KB
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values remaining: 0
#   [PASS] pell_recipients >= 0 (non-null): 0 negative values
#   [PASS] pell_recipients null rate < 30%: 0.1%
#   [PASS] Rows preserved: 4,994 -> 4,994
#   [PASS] Suppression rate < 50%: 0.1%
#   [PASS] Expected row count (4,994): 4,994
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
