#!/usr/bin/env python3
"""
Stage 6.5: Clean MEPS poverty data — verify no coded values, validate ranges,
summarize by year.

Task: clean-meps
Wave: 3, Step: 5, Stage: 6
Depends on: fetch-meps
Input: data/raw/2026-02-14_meps.parquet
Output: data/processed/2026-02-14_meps_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for MEPS cleaning. Unlike CCD which uses coded
# missing values (-1, -2, -3), MEPS uses native null for missing data.
# However, we still verify no coded values are present as a defensive check.
# The poverty measure (meps_poverty_pct) represents the estimated percentage
# of students at 100% Federal Poverty Level — the preferred cross-state
# poverty measure because it avoids CEP contamination of FRPL post-2014.
PROJECT_DIR = Path("/daaf/research/2026-02-14 School Law Enforcement Demographics")
DATE_PREFIX = "2026-02-14"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_meps.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_meps_clean.parquet"

EXPECTED_YEARS = [2015, 2017, 2020, 2021]
EXPECTED_MIN_ROWS = 300_000
EXPECTED_MAX_ROWS = 500_000

# --- Load ---
# Load raw MEPS data fetched in Stage 5 and verify shape before proceeding.
print("=" * 60)
print("Stage 6.5: Clean MEPS poverty data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# Capture current state BEFORE any transformation for post-validation comparison.
# MEPS cleaning is primarily a validation pass — we expect no rows to be dropped
# and no values to change, because MEPS uses native null (not coded values).
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Sample (first 5 rows):")
print(df.head(5))

# --- Validation Step 1: Check for coded values ---
# INTENT: Verify that no Education Data Portal coded missing values (-1, -2, -3)
# are present in meps_poverty_pct. Per the MEPS source documentation, MEPS uses
# native null rather than coded values. This check is defensive — if coded values
# ARE found, it indicates an unexpected data format change.
#
# REASONING: Even though MEPS documentation says it uses native null, we verify
# this assumption explicitly because:
#   1. Data format can change across years without warning
#   2. The fetch script may have introduced coded values via type casting
#   3. Downstream analysis would be corrupted if -1/-2/-3 values are treated as
#      real poverty percentages (e.g., mean would be dragged down)
#
# ASSUMES: meps_poverty_pct column exists and is Float64
print("\n" + "-" * 40)
print("Validation Step 1: Check for coded values in meps_poverty_pct")
print("-" * 40)
coded_count = df.filter(pl.col("meps_poverty_pct").is_in([-1.0, -2.0, -3.0])).height
print(f"  Coded values (-1, -2, -3) found: {coded_count}")
assert coded_count == 0, f"STOP: Unexpected coded values in MEPS: {coded_count} found"
print("  [PASS] No coded values present")

# Also check meps_pct_aa and meps_pct_hisp if present
# INTENT: Apply the same defensive check to other MEPS percentage columns.
# REASONING: These columns follow the same MEPS data specification and should
# also use native null, but we verify to be safe.
for col in ["meps_pct_aa", "meps_pct_hisp"]:
    if col in df.columns:
        col_coded = df.filter(pl.col(col).is_in([-1.0, -2.0, -3.0])).height
        print(f"  Coded values in {col}: {col_coded}")
        assert col_coded == 0, f"STOP: Unexpected coded values in {col}: {col_coded}"
        print(f"  [PASS] No coded values in {col}")

# --- Validation Step 2: Verify ncessch format ---
# INTENT: Confirm that ncessch (NCES school identifier) is a 12-character String.
# This is critical for downstream joins with CCD data.
#
# REASONING: The fetch script cast ncessch from Int64 to String and zero-padded
# to 12 characters. We verify this transformation was successful because a join
# on mismatched key formats (e.g., "10000000001" vs "010000000001") would silently
# produce zero matches.
#
# ASSUMES: ncessch column exists
print("\n" + "-" * 40)
print("Validation Step 2: Verify ncessch format")
print("-" * 40)
ncessch_dtype = df["ncessch"].dtype
print(f"  ncessch dtype: {ncessch_dtype}")
assert ncessch_dtype == pl.Utf8 or ncessch_dtype == pl.String, \
    f"STOP: ncessch should be String, got {ncessch_dtype}"
print(f"  [PASS] ncessch is String type")

# Check all values are exactly 12 characters
# INTENT: Verify zero-padding consistency — all NCES IDs must be exactly 12 chars.
# REASONING: NCES school IDs are always 12 digits. Values shorter than 12 indicate
# the zero-padding in the fetch script failed for some records. Values longer than
# 12 would indicate data corruption.
ncessch_lengths = df["ncessch"].str.len_chars().value_counts().sort("ncessch")
print(f"  ncessch length distribution:")
print(ncessch_lengths)

all_12_chars = (df["ncessch"].str.len_chars() == 12).all()
print(f"  All ncessch values are 12 chars: {all_12_chars}")
assert all_12_chars, "STOP: Not all ncessch values are 12 characters"
print("  [PASS] All ncessch values are 12 characters")

# Check for null ncessch
ncessch_nulls = df["ncessch"].null_count()
print(f"  ncessch null count: {ncessch_nulls}")
assert ncessch_nulls == 0, f"STOP: {ncessch_nulls} null ncessch values"
print("  [PASS] No null ncessch values")

# --- Validation Step 3: Verify meps_poverty_pct range ---
# INTENT: Confirm poverty percentage falls within expected bounds (0 to ~65).
# Values outside this range would indicate data corruption or misinterpretation.
#
# REASONING: At 100% FPL, school-level poverty estimates typically range from
# near 0% (affluent areas) to ~60.5% (high-poverty areas). We use a slightly
# generous upper bound of 100 for the assertion (theoretical maximum), but
# report the actual range for human review.
#
# ASSUMES: meps_poverty_pct represents percentage (0-100 scale), not proportion (0-1)
print("\n" + "-" * 40)
print("Validation Step 3: Verify meps_poverty_pct range")
print("-" * 40)

# Drop nulls before computing range to avoid null contamination
poverty_non_null = df["meps_poverty_pct"].drop_nulls()
min_val = poverty_non_null.min()
max_val = poverty_non_null.max()
mean_val = poverty_non_null.mean()
median_val = poverty_non_null.median()
print(f"  meps_poverty_pct range: [{min_val:.4f}, {max_val:.4f}]")
print(f"  meps_poverty_pct mean: {mean_val:.4f}")
print(f"  meps_poverty_pct median: {median_val:.4f}")

assert min_val >= 0, f"STOP: meps_poverty_pct has negative values (min={min_val})"
assert max_val <= 100, f"STOP: meps_poverty_pct exceeds 100 (max={max_val})"
print("  [PASS] meps_poverty_pct in valid range [0, 100]")

# Check for negative values explicitly (extra safety)
negative_count = df.filter(pl.col("meps_poverty_pct") < 0).height
print(f"  Negative meps_poverty_pct values: {negative_count}")
assert negative_count == 0, f"STOP: {negative_count} negative poverty values"

# --- Summary by year ---
# INTENT: Print descriptive statistics by year for human review. This helps
# identify year-specific anomalies (e.g., COVID-19 effects on 2020/2021 data,
# coverage changes across years).
#
# REASONING: Aggregating by year because MEPS coverage and poverty rates may
# vary across CRDC collection years. Year-level summaries make anomalies visible
# without requiring the reviewer to examine individual records.
print("\n" + "-" * 40)
print("Summary by year")
print("-" * 40)
year_summary = df.group_by("year").agg([
    pl.len().alias("school_count"),
    pl.col("meps_poverty_pct").mean().alias("mean_poverty"),
    pl.col("meps_poverty_pct").median().alias("median_poverty"),
    pl.col("meps_poverty_pct").null_count().alias("null_count"),
    (pl.col("meps_poverty_pct").null_count() / pl.len() * 100).alias("null_rate_pct"),
]).sort("year")
print(year_summary)

# --- Null rate assessment ---
# INTENT: Calculate and report the overall null rate for meps_poverty_pct.
# REASONING: The CP2 threshold is 50% — above that, the data is too sparse
# for reliable analysis. We expect ~2.1% based on Stage 5 findings.
print("\n" + "-" * 40)
print("Null rate assessment")
print("-" * 40)
total_nulls = df["meps_poverty_pct"].null_count()
null_rate = total_nulls / pre_rows * 100
print(f"  meps_poverty_pct null count: {total_nulls:,}")
print(f"  meps_poverty_pct null rate: {null_rate:.2f}%")

# Also check other columns
for col in df.columns:
    col_nulls = df[col].null_count()
    col_rate = col_nulls / pre_rows * 100
    print(f"  {col} null count: {col_nulls:,} ({col_rate:.2f}%)")

# --- Save ---
# Persist the validated MEPS data. Since MEPS uses native null (not coded values),
# the data passes through largely unchanged — this script is primarily a validation
# and documentation step rather than a transformation step.
#
# REASONING: We save the data as-is (without dropping null rows) because:
#   1. Downstream joins will naturally exclude unmatched records
#   2. Dropping nulls here would lose schools that have valid data in other columns
#   3. The null rate (~2.1%) is well within acceptable bounds
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Output shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Post-state ---
# Capture state after processing for comparison with pre-state.
post_rows = df.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {len(df.columns)} cols")
print(f"Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100 if pre_rows > 0 else 0:+.1f}%)")

# --- CP2 Validation ---
# Checkpoint validation: verify all expected years present, row count within
# bounds, poverty range valid, null rate acceptable, and key format correct.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

# CP2.1: All 4 expected years present
years_found = sorted(df["year"].unique().to_list())
all_years_present = all(y in years_found for y in EXPECTED_YEARS)
print(f"  [{'PASS' if all_years_present else 'FAIL'}] All 4 years present: {years_found}")
print(f"    Expected: {EXPECTED_YEARS}")

# CP2.2: Row count within expected range
row_count_ok = EXPECTED_MIN_ROWS <= pre_rows <= EXPECTED_MAX_ROWS
print(f"  [{'PASS' if row_count_ok else 'FAIL'}] Row count: {pre_rows:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# CP2.3: meps_poverty_pct in valid range (no negative coded values)
range_ok = min_val >= 0 and max_val <= 100
print(f"  [{'PASS' if range_ok else 'FAIL'}] Poverty range valid: [{min_val:.4f}, {max_val:.4f}]")

# CP2.4: Null rate < 50%
null_rate_ok = null_rate < 50
print(f"  [{'PASS' if null_rate_ok else 'FAIL'}] Null rate < 50%: {null_rate:.2f}%")

# CP2.5: ncessch is 12-char String
ncessch_ok = all_12_chars and (ncessch_dtype == pl.Utf8 or ncessch_dtype == pl.String)
print(f"  [{'PASS' if ncessch_ok else 'FAIL'}] ncessch is 12-char String: dtype={ncessch_dtype}, all_12={all_12_chars}")

# CP2.6: No coded values remain (already verified above, but restate for CP2)
no_coded_values = coded_count == 0
print(f"  [{'PASS' if no_coded_values else 'FAIL'}] No coded values (-1/-2/-3): {coded_count} found")

# CP2.7: Row count preserved (cleaning should not drop rows for MEPS)
rows_preserved = post_rows == pre_rows
print(f"  [{'PASS' if rows_preserved else 'WARN'}] Rows preserved: {pre_rows:,} -> {post_rows:,}")

# Aggregate CP2 result
all_checks = [all_years_present, row_count_ok, range_ok, null_rate_ok, ncessch_ok, no_coded_values]
cp2_passed = all(all_checks)

assert all_years_present, f"STOP: Missing years. Found {years_found}, expected {EXPECTED_YEARS}"
assert row_count_ok, f"STOP: Row count {pre_rows:,} outside expected range {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,}"
assert range_ok, f"STOP: Poverty range [{min_val}, {max_val}] outside expected [0, 100]"
assert null_rate_ok, f"STOP: Null rate {null_rate:.2f}% exceeds 50% threshold"
assert ncessch_ok, f"STOP: ncessch format invalid"
assert no_coded_values, f"STOP: Coded values still present"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 00:31:32
# Command: python /daaf/research/2026-02-14 School Law Enforcement Demographics/scripts/stage6_clean/05_clean-meps_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.5: Clean MEPS poverty data
# ============================================================
# Loaded: 381,147 rows x 5 cols
# Columns: ['ncessch', 'year', 'meps_poverty_pct', 'meps_poverty_se', 'meps_poverty_ptl']
# Dtypes: [String, Int64, Float64, Float64, Int64]
# 
# Pre-state: 381,147 rows, 5 cols
# Sample (first 5 rows):
# shape: (5, 5)
# ┌──────────────┬──────┬──────────────────┬─────────────────┬──────────────────┐
# │ ncessch      ┆ year ┆ meps_poverty_pct ┆ meps_poverty_se ┆ meps_poverty_ptl │
# │ ---          ┆ ---  ┆ ---              ┆ ---             ┆ ---              │
# │ str          ┆ i64  ┆ f64              ┆ f64             ┆ i64              │
# ╞══════════════╪══════╪══════════════════╪═════════════════╪══════════════════╡
# │ 010000200277 ┆ 2015 ┆ null             ┆ null            ┆ null             │
# │ 010000201667 ┆ 2015 ┆ null             ┆ null            ┆ null             │
# │ 010000201670 ┆ 2015 ┆ null             ┆ null            ┆ null             │
# │ 010000201705 ┆ 2015 ┆ null             ┆ null            ┆ null             │
# │ 010000201706 ┆ 2015 ┆ null             ┆ null            ┆ null             │
# └──────────────┴──────┴──────────────────┴─────────────────┴──────────────────┘
# 
# ----------------------------------------
# Validation Step 1: Check for coded values in meps_poverty_pct
# ----------------------------------------
#   Coded values (-1, -2, -3) found: 0
#   [PASS] No coded values present
# 
# ----------------------------------------
# Validation Step 2: Verify ncessch format
# ----------------------------------------
#   ncessch dtype: String
#   [PASS] ncessch is String type
#   ncessch length distribution:
# shape: (1, 2)
# ┌─────────┬────────┐
# │ ncessch ┆ count  │
# │ ---     ┆ ---    │
# │ u32     ┆ u32    │
# ╞═════════╪════════╡
# │ 12      ┆ 381147 │
# └─────────┴────────┘
#   All ncessch values are 12 chars: True
#   [PASS] All ncessch values are 12 characters
#   ncessch null count: 0
#   [PASS] No null ncessch values
# 
# ----------------------------------------
# Validation Step 3: Verify meps_poverty_pct range
# ----------------------------------------
#   meps_poverty_pct range: [0.0000, 60.5347]
#   meps_poverty_pct mean: 17.7911
#   meps_poverty_pct median: 16.9188
#   [PASS] meps_poverty_pct in valid range [0, 100]
#   Negative meps_poverty_pct values: 0
# 
# ----------------------------------------
# Summary by year
# ----------------------------------------
# shape: (4, 6)
# ┌──────┬──────────────┬──────────────┬────────────────┬────────────┬───────────────┐
# │ year ┆ school_count ┆ mean_poverty ┆ median_poverty ┆ null_count ┆ null_rate_pct │
# │ ---  ┆ ---          ┆ ---          ┆ ---            ┆ ---        ┆ ---           │
# │ i64  ┆ u32          ┆ f64          ┆ f64            ┆ u32        ┆ f64           │
# ╞══════╪══════════════╪══════════════╪════════════════╪════════════╪═══════════════╡
# │ 2015 ┆ 96661        ┆ 19.885056    ┆ 18.983351      ┆ 1897       ┆ 1.962529      │
# │ 2017 ┆ 94915        ┆ 18.281753    ┆ 17.701937      ┆ 1402       ┆ 1.477111      │
# │ 2020 ┆ 94590        ┆ 15.682763    ┆ 14.911288      ┆ 2339       ┆ 2.472777      │
# │ 2021 ┆ 94981        ┆ 17.253676    ┆ 16.411106      ┆ 2260       ┆ 2.379423      │
# └──────┴──────────────┴──────────────┴────────────────┴────────────┴───────────────┘
# 
# ----------------------------------------
# Null rate assessment
# ----------------------------------------
#   meps_poverty_pct null count: 7,898
#   meps_poverty_pct null rate: 2.07%
#   ncessch null count: 0 (0.00%)
#   year null count: 0 (0.00%)
#   meps_poverty_pct null count: 7,898 (2.07%)
#   meps_poverty_se null count: 5,661 (1.49%)
#   meps_poverty_ptl null count: 7,898 (2.07%)
# 
# Saved: /daaf/research/2026-02-14 School Law Enforcement Demographics/data/processed/2026-02-14_meps_clean.parquet
# Output shape: 381,147 rows x 5 cols
# 
# Post-state: 381,147 rows, 5 cols
# Row change: +0 (+0.0%)
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] All 4 years present: [2015, 2017, 2020, 2021]
#     Expected: [2015, 2017, 2020, 2021]
#   [PASS] Row count: 381,147 (expected 300,000-500,000)
#   [PASS] Poverty range valid: [0.0000, 60.5347]
#   [PASS] Null rate < 50%: 2.07%
#   [PASS] ncessch is 12-char String: dtype=String, all_12=True
#   [PASS] No coded values (-1/-2/-3): 0 found
#   [PASS] Rows preserved: 381,147 -> 381,147
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
