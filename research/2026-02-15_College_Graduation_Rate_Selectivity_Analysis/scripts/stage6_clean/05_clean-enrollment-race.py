#!/usr/bin/env python3
"""
Stage 6.5: Clean IPEDS enrollment by race — replace coded values, compute URM share.

Task: clean-enrollment-race
Wave: 3, Step: 5, Stage: 6
Depends on: fetch-enrollment-race (COMPLETE)
Input: data/raw/2026-02-15_ipeds_enrollment_race.parquet
Output: data/processed/2026-02-15_enrollment_race_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# This script cleans IPEDS Fall Enrollment by Race data (fetched in Stage 5)
# and computes URM (Underrepresented Minority) share per institution.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_enrollment_race.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_enrollment_race_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data in numeric measure columns. These must be mapped to null so they don't
# corrupt downstream statistical calculations (e.g., mean enrollment would be
# dragged down by -1 values if left in place).
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}

# REASONING: Per Education Data Portal integer encoding system, race codes are:
#   1=White, 2=Black, 3=Hispanic, 4=Asian, 5=American Indian/Alaska Native,
#   6=Native Hawaiian/Pacific Islander, 7=Two or more races, 8=Nonresident alien,
#   9=Unknown, 99=Total
# However, the task specification from the orchestrator uses a DIFFERENT mapping
# from the IPEDS standard (which differs from CCD). The task specification states:
#   URM = Black (5) + Hispanic (2) + American Indian/Alaska Native (3)
# But per the Education Data Portal encoding in education-data-context skill:
#   2=Black, 3=Hispanic, 5=American Indian/Alaska Native
# We will VERIFY which encoding is actually present in the data before using it.
#
# IMPORTANT: The education-data-context skill documents Portal-wide race codes as:
#   1=White, 2=Black, 3=Hispanic, 4=Asian, 5=AI/AN, 6=NHPI, 7=Two+, 8=Nonresident,
#   9=Unknown, 99=Total
# The task spec referenced a DIFFERENT ordering. We MUST trust the data (Truth
# Hierarchy Priority 1: actual data file) and verify codes before computing URM.
RACE_TOTAL = 99

# The numeric column to clean coded values from
ENROLLMENT_COL = "enrollment_fall"

# --- Load ---
# Load raw enrollment by race data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.5: Clean IPEDS Enrollment by Race")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Types: {df.dtypes}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Also enumerate coded values and race codes present to inform URM definition.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Inspect race codes present in the data
# INTENT: Determine which integer codes the "race" column actually uses, so we
# can correctly define URM groups. We trust the data over documentation when
# they conflict (Truth Hierarchy Priority 1).
print("\n--- Race Code Inspection ---")
race_col = "race" if "race" in df.columns else None
if race_col is None:
    # Check for alternative names
    race_candidates = [c for c in df.columns if "race" in c.lower() or "ethnicity" in c.lower()]
    print(f"WARNING: 'race' column not found. Candidates: {race_candidates}")
    if race_candidates:
        race_col = race_candidates[0]
        print(f"Using: {race_col}")

assert race_col is not None, "STOP: No race column found in data"

race_counts = (
    df.group_by(race_col)
    .agg(
        pl.col(ENROLLMENT_COL).sum().alias("total_enrollment"),
        pl.len().alias("row_count"),
    )
    .sort(race_col)
)
print(f"\nRace code distribution:")
print(race_counts)

# Extract unique race values for verification
unique_races = sorted(df[race_col].unique().to_list())
print(f"\nUnique race codes: {unique_races}")

# INTENT: Determine URM race codes based on what's actually in the data.
# Per Education Data Portal encoding (education-data-context skill):
#   2=Black, 3=Hispanic, 5=American Indian/Alaska Native
# Per the orchestrator's task specification:
#   URM = Black (5) + Hispanic (2) + American Indian/Alaska Native (3)
# These conflict. We use the Portal standard from the skill (the authoritative
# source): 2=Black, 3=Hispanic, 5=AI/AN.
#
# REASONING: The education-data-context skill documents the Portal-wide encoding
# as the canonical reference. The task specification may have used IPEDS-native
# codes which differ. We verify by checking which codes exist in the data.
URM_CODES = [2, 3, 5]  # Portal encoding: 2=Black, 3=Hispanic, 5=AI/AN
print(f"\nURM definition: race codes {URM_CODES}")
print("  2 = Black/African American")
print("  3 = Hispanic/Latino")
print("  5 = American Indian/Alaska Native")

# Verify all URM codes exist in the data
for code in URM_CODES:
    present = code in unique_races
    count = df.filter(pl.col(race_col) == code).shape[0]
    print(f"  Code {code} present: {present} ({count:,} rows)")

assert all(code in unique_races for code in URM_CODES), \
    f"STOP: Not all URM codes {URM_CODES} found in data. Present: {unique_races}"

# Verify total code (99) exists
assert RACE_TOTAL in unique_races, \
    f"STOP: Total race code {RACE_TOTAL} not found in data. Present: {unique_races}"

# Check coded missing values in enrollment_fall
print("\n--- Coded Value Inspection ---")
coded_counts = {}
for code, meaning in CODED_MISSING.items():
    count = df.filter(pl.col(ENROLLMENT_COL) == code).shape[0]
    if count > 0:
        coded_counts[code] = count
        print(f"  {ENROLLMENT_COL} = {code} ({meaning}): {count:,}")

if not coded_counts:
    print("  No coded missing values found in enrollment_fall")

# --- Transform: Replace coded values ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in the enrollment_fall
# column so downstream aggregation is not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation — these values were never observed. Zero would imply
# a measured value of zero enrollment for that race group, and NaN would
# complicate Polars aggregations.
#
# ASSUMES: All coded values in ENROLLMENT_COL are in the CODED_MISSING dict
# per IPEDS source documentation.
print("\n--- Transform: Replace Coded Values ---")
df = df.with_columns(
    pl.when(pl.col(ENROLLMENT_COL).is_in(list(CODED_MISSING.keys())))
    .then(None)
    .otherwise(pl.col(ENROLLMENT_COL))
    .alias(ENROLLMENT_COL)
)
print("Replaced coded values with null in enrollment_fall")

# Verify no coded values remain
remaining_coded = 0
for code in CODED_MISSING.keys():
    remaining_coded += df.filter(pl.col(ENROLLMENT_COL) == code).shape[0]
print(f"Coded values remaining: {remaining_coded}")
assert remaining_coded == 0, "STOP: Coded values still present after replacement"

# --- Transform: Compute URM aggregation per institution ---
# INTENT: For each institution (unitid), extract total enrollment (race=99)
# and sum URM enrollment (race in {2, 3, 5}), then compute urm_share.
#
# REASONING: We compute totals from the race=99 row rather than summing sub-
# categories because:
#   - The total row is the official reported total from the institution
#   - Summing sub-categories could overcount if categories overlap
#   - Stage 5 QA confirmed sub-categories are mutually exclusive (ratio=1.0),
#     but the official total is still the authoritative figure
#   - QA confirmed SUM aggregation is safe for computing URM totals
#
# ASSUMES:
#   - Each unitid has exactly one row with race=99 (total)
#   - Each unitid has at most one row per URM race code
#   - enrollment_fall is non-negative after coded value removal (nulls ok)
print("\n--- Transform: Compute URM Share ---")

# Step 1: Extract total enrollment per institution (race=99)
# INTENT: Get the official total enrollment for each institution from the
# race=99 (Total) row. This is used as the denominator for URM share.
df_total = (
    df.filter(pl.col(race_col) == RACE_TOTAL)
    .select("unitid", pl.col(ENROLLMENT_COL).alias("total_enrollment_race"))
)
print(f"Total enrollment rows (race=99): {df_total.shape[0]:,}")

# Verify one row per unitid in totals
total_unitid_unique = df_total["unitid"].n_unique() == df_total.shape[0]
print(f"Unitid unique in totals: {total_unitid_unique}")
assert total_unitid_unique, "STOP: Multiple total rows per unitid"

# Step 2: Compute URM enrollment per institution
# INTENT: Sum enrollment_fall for URM race codes (2=Black, 3=Hispanic, 5=AI/AN)
# per institution. This is the numerator for URM share.
#
# REASONING: Using sum aggregation rather than any other method because Stage 5
# QA confirmed sub-categories are mutually exclusive. sum() correctly handles
# nulls in Polars by excluding them (treating as 0 in sum context).
df_urm = (
    df.filter(pl.col(race_col).is_in(URM_CODES))
    .group_by("unitid")
    .agg(pl.col(ENROLLMENT_COL).sum().alias("urm_enrollment"))
)
print(f"URM enrollment rows: {df_urm.shape[0]:,}")

# Step 3: Join total and URM, compute share
# INTENT: Combine total and URM enrollment per institution, then compute the
# URM share as a proportion.
#
# REASONING: Using LEFT join from totals to URM because every institution with
# a total row should be in our output, even if no URM rows exist (in which case
# urm_enrollment will be null, representing 0 URM students — we'll fill to 0).
#
# ASSUMES:
#   - unitid is unique in both df_total and df_urm
#   - All institutions with URM rows also have a total row
result = df_total.join(df_urm, on="unitid", how="left")

# Fill null URM enrollment with 0 (institutions with no URM race rows present)
# REASONING: If no URM race codes had rows for an institution, that means
# enrollment for those groups was 0 or unreported. Since we're looking at
# institutions that reported total enrollment, a missing URM row most likely
# indicates 0 URM students or data not broken out by race. Using 0 is
# conservative and prevents null propagation into urm_share.
result = result.with_columns(
    pl.col("urm_enrollment").fill_null(0)
)

# Step 4: Compute URM share
# INTENT: Calculate urm_share = urm_enrollment / total_enrollment_race.
# Only compute where total > 0 to avoid division by zero.
#
# REASONING: Using when/then/otherwise to guard against division by zero.
# Institutions with 0 total enrollment get null urm_share because the ratio
# is undefined (0/0 is not 0%).
#
# ASSUMES: total_enrollment_race >= 0 after coded value removal
result = result.with_columns(
    pl.when(pl.col("total_enrollment_race") > 0)
    .then(pl.col("urm_enrollment") / pl.col("total_enrollment_race"))
    .otherwise(None)
    .alias("urm_share")
)

print(f"\nAggregated result: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Columns: {result.columns}")

# --- Post-state ---
# Capture post-transformation state for validation.
post_rows = result.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {result.shape[1]} cols")
print(f"Row change from raw: {pre_rows:,} -> {post_rows:,} (aggregated from multi-row to one-per-institution)")

# Descriptive statistics of key columns
print("\n--- Output Summary Statistics ---")
print(f"total_enrollment_race: min={result['total_enrollment_race'].min()}, "
      f"max={result['total_enrollment_race'].max()}, "
      f"mean={result['total_enrollment_race'].mean():.1f}, "
      f"null_count={result['total_enrollment_race'].null_count()}")
print(f"urm_enrollment: min={result['urm_enrollment'].min()}, "
      f"max={result['urm_enrollment'].max()}, "
      f"mean={result['urm_enrollment'].mean():.1f}, "
      f"null_count={result['urm_enrollment'].null_count()}")
print(f"urm_share: min={result['urm_share'].min()}, "
      f"max={result['urm_share'].max()}, "
      f"mean={result['urm_share'].mean():.4f}, "
      f"null_count={result['urm_share'].null_count()}")

# Sample of results for sanity checking
print("\n--- Sample Output (first 5) ---")
print(result.head(5))

print("\n--- Sample Output (urm_share distribution) ---")
urm_share_valid = result.filter(pl.col("urm_share").is_not_null())
print(f"Institutions with valid urm_share: {urm_share_valid.shape[0]:,}")
quantiles = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
for q in quantiles:
    val = urm_share_valid["urm_share"].quantile(q)
    print(f"  P{int(q*100):3d}: {val:.4f}")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, URM share is valid,
# unitid is unique, and output meets Plan expectations.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

# CP2.1: Unitid is unique in output
unitid_unique = result["unitid"].n_unique() == result.shape[0]
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] Unitid unique: {result['unitid'].n_unique():,} unique vs {result.shape[0]:,} rows")

# CP2.2: URM share between 0 and 1 for all non-null values
urm_valid = result.filter(pl.col("urm_share").is_not_null())
urm_in_range = (
    urm_valid["urm_share"].min() >= 0.0 and
    urm_valid["urm_share"].max() <= 1.0
)
print(f"  [{'PASS' if urm_in_range else 'FAIL'}] URM share in [0,1]: min={urm_valid['urm_share'].min():.4f}, max={urm_valid['urm_share'].max():.4f}")

# CP2.3: Total enrollment is positive for all rows with valid urm_share
total_positive = urm_valid["total_enrollment_race"].min() > 0
print(f"  [{'PASS' if total_positive else 'FAIL'}] Total enrollment positive (where urm_share valid): min={urm_valid['total_enrollment_race'].min()}")

# CP2.4: No coded values remain in output
coded_remaining = 0
for col in ["total_enrollment_race", "urm_enrollment"]:
    for code in CODED_MISSING.keys():
        coded_remaining += result.filter(pl.col(col) == code).shape[0]
no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")

# CP2.5: Row count in expected range (5,000-6,000 institutions)
rows_in_range = 4000 <= result.shape[0] <= 8000
print(f"  [{'PASS' if rows_in_range else 'WARN'}] Row count in range: {result.shape[0]:,} (expected ~5,000-6,000)")

# CP2.6: Suppression rate check
total_cells = result.shape[0] * 3  # 3 numeric columns
null_cells = (result["total_enrollment_race"].null_count() +
              result["urm_enrollment"].null_count() +
              result["urm_share"].null_count())
suppression_rate = null_cells / total_cells if total_cells > 0 else 0
suppression_ok = suppression_rate < 0.50
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: {suppression_rate:.1%} ({null_cells:,} nulls / {total_cells:,} cells)")

# CP2.7: Race code mapping documented (informational)
print(f"  [INFO] Race codes used for URM: {URM_CODES} (2=Black, 3=Hispanic, 5=AI/AN)")
print(f"  [INFO] Total race code used: {RACE_TOTAL}")

assert unitid_unique, "STOP: Unitid not unique in output"
assert urm_in_range, "STOP: URM share outside [0,1]"
assert total_positive, "STOP: Total enrollment not positive"
assert no_coded, "STOP: Coded values still present"
assert suppression_ok, "STOP: Suppression rate >= 50%"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:39:21
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 6.5: Clean IPEDS Enrollment by Race
# ============================================================
# Loaded: 352,410 rows x 7 cols
# Columns: ['unitid', 'year', 'enrollment_fall', 'race', 'sex', 'ftpt', 'level_of_study']
# Types: [Int64, Int64, Int64, Int64, Int64, Int64, Int64]
# 
# Pre-state: 352,410 rows, 7 cols
# 
# --- Race Code Inspection ---
# 
# Race code distribution:
# shape: (10, 3)
# ┌──────┬──────────────────┬───────────┐
# │ race ┆ total_enrollment ┆ row_count │
# │ ---  ┆ ---              ┆ ---       │
# │ i64  ┆ i64              ┆ u32       │
# ╞══════╪══════════════════╪═══════════╡
# │ 1    ┆ 28360502         ┆ 35241     │
# │ 2    ┆ 7302057          ┆ 35241     │
# │ 3    ┆ 12544754         ┆ 35241     │
# │ 4    ┆ 3922940          ┆ 35241     │
# │ 5    ┆ 386234           ┆ 35241     │
# │ 6    ┆ 180719           ┆ 35241     │
# │ 7    ┆ 2369453          ┆ 35241     │
# │ 8    ┆ 1769370          ┆ 35241     │
# │ 9    ┆ 2403345          ┆ 35241     │
# │ 99   ┆ 59239374         ┆ 35241     │
# └──────┴──────────────────┴───────────┘
# 
# Unique race codes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# 
# URM definition: race codes [2, 3, 5]
#   2 = Black/African American
#   3 = Hispanic/Latino
#   5 = American Indian/Alaska Native
#   Code 2 present: True (35,241 rows)
#   Code 3 present: True (35,241 rows)
#   Code 5 present: True (35,241 rows)
# 
# --- Coded Value Inspection ---
#   No coded missing values found in enrollment_fall
# 
# --- Transform: Replace Coded Values ---
# Replaced coded values with null in enrollment_fall
# Coded values remaining: 0
# 
# --- Transform: Compute URM Share ---
# Total enrollment rows (race=99): 35,241
# Unitid unique in totals: False
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race.py", line 201, in <module>
#     assert total_unitid_unique, "STOP: Multiple total rows per unitid"
#            ^^^^^^^^^^^^^^^^^^^
# AssertionError: STOP: Multiple total rows per unitid
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
