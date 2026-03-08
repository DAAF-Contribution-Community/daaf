#!/usr/bin/env python3
"""
Stage 6.5: Clean IPEDS enrollment by race — replace coded values, aggregate
across sub-dimensions, compute URM share.

Task: clean-enrollment-race
Wave: 3, Step: 5, Stage: 6
Depends on: fetch-enrollment-race (COMPLETE)
Input: data/raw/2026-02-15_ipeds_enrollment_race.parquet
Output: data/processed/2026-02-15_enrollment_race_clean.parquet
Checkpoint: CP2

Revision: _a.py (fix from v1 failure)
  - v1 assumed one row per unitid per race, but the raw data has multiple
    rows per unitid per race due to sub-dimensions (degree_seeking, class_level)
    that were not filtered during fetch (columns were selected out but rows
    remained). 352,410 rows / 10 races / 5,837 institutions = ~6 rows per
    institution per race. Fix: aggregate enrollment_fall by unitid+race first.
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
# corrupt downstream statistical calculations.
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}

# REASONING: Per Education Data Portal integer encoding system (education-data-context
# skill), race codes are:
#   1=White, 2=Black, 3=Hispanic, 4=Asian, 5=American Indian/Alaska Native,
#   6=Native Hawaiian/Pacific Islander, 7=Two or more races, 8=Nonresident alien,
#   9=Unknown, 99=Total
# URM = Black (2) + Hispanic (3) + AI/AN (5), per Portal encoding.
URM_CODES = [2, 3, 5]
RACE_TOTAL = 99

ENROLLMENT_COL = "enrollment_fall"

# --- Load ---
# Load raw enrollment by race data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.5: Clean IPEDS Enrollment by Race (v2 - _a.py)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
n_institutions = df["unitid"].n_unique()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Unique institutions: {n_institutions:,}")
print(f"Rows per institution: {pre_rows / n_institutions:.1f} (expect 10 races x ~6 sub-dims = ~60)")

# Inspect race codes present in the data
# INTENT: Verify the race codes match expected Portal encoding before using them.
print("\n--- Race Code Inspection ---")
race_col = "race"
assert race_col in df.columns, "STOP: 'race' column not found"

unique_races = sorted(df[race_col].unique().to_list())
print(f"Unique race codes: {unique_races}")
print(f"Expected Portal encoding: 1=White, 2=Black, 3=Hispanic, 4=Asian, 5=AI/AN, 6=NHPI, 7=Two+, 8=Nonresident, 9=Unknown, 99=Total")

# Verify all URM codes and total code exist
for code in URM_CODES + [RACE_TOTAL]:
    assert code in unique_races, f"STOP: Race code {code} not found in data. Present: {unique_races}"
print(f"URM codes {URM_CODES} and total code {RACE_TOTAL} all present.")

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
# INTENT: Replace coded missing values (-1, -2, -3) with null in enrollment_fall
# so downstream aggregation is not corrupted.
#
# REASONING: Using null (not zero) because null is semantically correct — these
# values were never observed. Zero would imply zero enrollment, which is different.
# Polars sum() skips nulls by default, so null URM race rows contribute 0 to
# the URM sum (correct behavior).
#
# ASSUMES: All coded values in ENROLLMENT_COL follow the standard Portal encoding.
print("\n--- Transform: Replace Coded Values ---")
df = df.with_columns(
    pl.when(pl.col(ENROLLMENT_COL).is_in(list(CODED_MISSING.keys())))
    .then(None)
    .otherwise(pl.col(ENROLLMENT_COL))
    .alias(ENROLLMENT_COL)
)
print("Replaced coded values with null in enrollment_fall")

remaining_coded = 0
for code in CODED_MISSING.keys():
    remaining_coded += df.filter(pl.col(ENROLLMENT_COL) == code).shape[0]
print(f"Coded values remaining: {remaining_coded}")
assert remaining_coded == 0, "STOP: Coded values still present after replacement"

# --- Transform: Aggregate sub-dimensions ---
# INTENT: Collapse the multiple rows per unitid+race (caused by degree_seeking
# and class_level sub-dimensions not filtered during fetch) into a single row
# per unitid+race by summing enrollment_fall.
#
# REASONING: The raw data has ~6 rows per unitid per race because the fetch
# script filtered on sex=99, level_of_study=1, ftpt=99 but did NOT filter on
# degree_seeking or class_level (those columns were dropped from the saved
# parquet but their distinct values still generated separate rows). Summing
# across these sub-dimensions gives us the total enrollment per unitid+race
# that matches the intended total-sex, undergraduate, total-ftpt aggregation.
#
# IMPORTANT: We aggregate by SUM rather than taking the race=99 sub-total
# because Stage 5 QA confirmed sub-categories are mutually exclusive
# (ratio=1.0 for all institutions). The sum of sub-dimension rows should
# equal the sub-total row if one exists. But since we don't know the exact
# coding of degree_seeking/class_level sub-totals, summing is safer.
#
# ASSUMES:
#   - The sub-dimension rows are NOT double-counting (they are disaggregated)
#   - Polars sum() treats null as 0 in aggregation context
print("\n--- Transform: Aggregate Sub-Dimensions ---")
pre_agg_rows = df.shape[0]

# First, let's understand the sub-dimension structure
rows_per_unitid_race = (
    df.group_by(["unitid", race_col])
    .len()
    .rename({"len": "n_rows"})
)
rows_dist = rows_per_unitid_race["n_rows"].value_counts().sort("n_rows")
print(f"Distribution of rows per unitid+race combination:")
print(rows_dist)

# INTENT: We need to determine whether the sub-dimension rows contain
# sub-totals that would cause double-counting. Let's check if any unitid+race
# combination has rows that sum to MORE than the enrollment in the row with
# the highest count (which would indicate a sub-total row is present).
#
# REASONING: Rather than trying to parse degree_seeking/class_level coding,
# we take a pragmatic approach: for each unitid+race, we check if the data
# contains exactly 1 row (no aggregation needed) vs. multiple rows. For
# multiple rows, we need to identify if one is a sub-total.
#
# SAFER APPROACH: Check if the raw data (pre-column-selection) had
# degree_seeking and class_level columns. Since the saved parquet only has
# ['unitid', 'year', 'enrollment_fall', 'race', 'sex', 'ftpt', 'level_of_study'],
# those columns were dropped. But the rows remain duplicated.
# Let's check: for a sample institution, look at the actual enrollment values
# across the duplicate rows for race=99.
sample_unitid = df["unitid"].unique().sort().head(1).item()
sample_rows = df.filter(
    (pl.col("unitid") == sample_unitid) & (pl.col(race_col) == RACE_TOTAL)
)
print(f"\nSample institution {sample_unitid}, race=99 rows:")
print(sample_rows)
print(f"Sum of enrollment_fall: {sample_rows[ENROLLMENT_COL].sum()}")

# REASONING: The Stage 5 fetch script fetched from the raw IPEDS fall-enrollment-race
# dataset, which contains degree_seeking and class_level dimensions. The fetch
# selected columns ['unitid', 'year', 'enrollment_fall', 'race', 'sex', 'ftpt',
# 'level_of_study'], dropping degree_seeking and class_level. This means we have
# duplicate rows where different degree_seeking/class_level values produced
# different enrollment counts for the same unitid+race.
#
# To correctly handle this, we should NOT simply sum all rows — some may be
# sub-totals. Instead, we should take the MAX row count per unitid+race
# (the sub-total row will have the highest enrollment), OR we should look for
# the specific degree_seeking/class_level combination that represents the total.
#
# However, since those columns were dropped, we take the MAXIMUM approach:
# for each unitid+race, take the maximum enrollment_fall value, which should
# correspond to the total/all sub-category row.
#
# VALIDATION: We will verify this gives sensible totals by checking that
# the race=99 total is >= sum of individual race enrollments for each institution.

# Actually, let's reconsider. Looking at the actual values more carefully:
# If the sub-rows are disaggregated (not overlapping), summing is correct.
# If they contain totals, taking max is correct.
# We need to check empirically.

# Check for a few institutions: does the sum of individual race enrollments
# (using the max per unitid+race) equal the total (race=99)?
print("\n--- Validation: Checking aggregation strategy ---")

# Strategy A: SUM all rows per unitid+race
df_sum = (
    df.group_by(["unitid", race_col])
    .agg(pl.col(ENROLLMENT_COL).sum().alias("enroll_sum"))
)

# Strategy B: MAX value per unitid+race (assumes one row is the total)
df_max = (
    df.group_by(["unitid", race_col])
    .agg(pl.col(ENROLLMENT_COL).max().alias("enroll_max"))
)

# For a few sample institutions, compare sum vs max vs race=99 total
sample_unitids = df["unitid"].unique().sort().head(5).to_list()
print(f"\nComparing strategies for {len(sample_unitids)} sample institutions:")

for uid in sample_unitids:
    total_sum = df_sum.filter(
        (pl.col("unitid") == uid) & (pl.col(race_col) == RACE_TOTAL)
    )["enroll_sum"].item()

    total_max = df_max.filter(
        (pl.col("unitid") == uid) & (pl.col(race_col) == RACE_TOTAL)
    )["enroll_max"].item()

    # Sum of individual races (using max strategy)
    indiv_max_sum = df_max.filter(
        (pl.col("unitid") == uid) &
        (pl.col(race_col) != RACE_TOTAL)
    )["enroll_max"].sum()

    # Sum of individual races (using sum strategy)
    indiv_sum_sum = df_sum.filter(
        (pl.col("unitid") == uid) &
        (pl.col(race_col) != RACE_TOTAL)
    )["enroll_sum"].sum()

    print(f"  unitid={uid}:")
    print(f"    race=99 total: SUM={total_sum}, MAX={total_max}")
    print(f"    sum of races (MAX strategy): {indiv_max_sum}")
    print(f"    sum of races (SUM strategy): {indiv_sum_sum}")
    # If MAX strategy total matches sum-of-individual-MAX, MAX is consistent
    # If SUM strategy total >> MAX total, SUM is double-counting
    if total_max is not None and total_max > 0:
        ratio_max = indiv_max_sum / total_max if total_max else 0
        ratio_sum = indiv_sum_sum / total_sum if total_sum else 0
        print(f"    ratio (indiv/total): MAX={ratio_max:.4f}, SUM={ratio_sum:.4f}")

# DECISION: Based on the empirical comparison above, choose the correct strategy.
# We proceed by printing the comparison and then using the appropriate method.
# The correct approach for IPEDS disaggregated data where sub-categories may
# contain sub-totals is typically MAX (the highest value is the aggregate row).

# INTENT: Aggregate to one row per unitid+race using the empirically validated
# strategy. We'll use SUM here because the QA from Stage 5 confirmed that
# sub-categories sum correctly to totals (ratio = 1.0000), meaning the rows
# are disaggregated, not overlapping with sub-totals.
#
# However, since the columns that distinguish sub-dimensions were dropped,
# and we may have sub-total rows mixed with detail rows, let's be conservative
# and check which strategy produces totals consistent with the QA finding.
#
# FINAL DECISION: After empirical check, we'll use whichever strategy produces
# race sub-group sums that match the race=99 total most closely (the Stage 5
# QA finding of ratio=1.0000 should be reproducible with the correct strategy).

# Let's do a broader check: across all institutions, which strategy makes
# the individual race sums match the race=99 total more closely?
print("\n--- Broader aggregation strategy validation ---")

# Strategy A (SUM): total for race=99, and sum of non-99 races
total_99_sum = df_sum.filter(pl.col(race_col) == RACE_TOTAL).rename({"enroll_sum": "total_99"})
indiv_sum = (
    df_sum.filter(pl.col(race_col) != RACE_TOTAL)
    .group_by("unitid")
    .agg(pl.col("enroll_sum").sum().alias("indiv_total"))
)
check_sum = total_99_sum.join(indiv_sum, on="unitid", how="inner")
check_sum = check_sum.with_columns(
    (pl.col("indiv_total") / pl.col("total_99")).alias("ratio")
)
sum_ratios = check_sum.filter(pl.col("total_99") > 0)
print(f"SUM strategy: mean ratio (indiv/total) = {sum_ratios['ratio'].mean():.4f}, "
      f"median = {sum_ratios['ratio'].median():.4f}")

# Strategy B (MAX)
total_99_max = df_max.filter(pl.col(race_col) == RACE_TOTAL).rename({"enroll_max": "total_99"})
indiv_max = (
    df_max.filter(pl.col(race_col) != RACE_TOTAL)
    .group_by("unitid")
    .agg(pl.col("enroll_max").sum().alias("indiv_total"))
)
check_max = total_99_max.join(indiv_max, on="unitid", how="inner")
check_max = check_max.with_columns(
    (pl.col("indiv_total") / pl.col("total_99")).alias("ratio")
)
max_ratios = check_max.filter(pl.col("total_99") > 0)
print(f"MAX strategy: mean ratio (indiv/total) = {max_ratios['ratio'].mean():.4f}, "
      f"median = {max_ratios['ratio'].median():.4f}")

# The strategy where the ratio is closest to 1.0 is correct.
# If both are close to 1.0, prefer MAX (more conservative, avoids double-counting).
sum_mean_ratio = sum_ratios['ratio'].mean()
max_mean_ratio = max_ratios['ratio'].mean()

if abs(max_mean_ratio - 1.0) <= abs(sum_mean_ratio - 1.0):
    use_strategy = "MAX"
    print(f"\nUsing MAX strategy (closer to ratio=1.0, max_ratio={max_mean_ratio:.4f})")
    df_agg = df_max.rename({"enroll_max": ENROLLMENT_COL})
else:
    use_strategy = "SUM"
    print(f"\nUsing SUM strategy (closer to ratio=1.0, sum_ratio={sum_mean_ratio:.4f})")
    df_agg = df_sum.rename({"enroll_sum": ENROLLMENT_COL})

print(f"\nAggregated: {df_agg.shape[0]:,} rows (from {pre_agg_rows:,})")
print(f"Unique unitid+race combinations: {df_agg.shape[0]:,}")

# Verify one row per unitid+race
unitid_race_unique = df_agg.select(["unitid", race_col]).n_unique() == df_agg.shape[0]
print(f"One row per unitid+race: {unitid_race_unique}")
assert unitid_race_unique, "STOP: Still multiple rows per unitid+race after aggregation"

# --- Transform: Compute URM aggregation per institution ---
# INTENT: For each institution (unitid), extract total enrollment (race=99)
# and sum URM enrollment (race in {2, 3, 5}), then compute urm_share.
#
# REASONING: We use the aggregated race=99 row as the total rather than
# summing sub-categories, because the race=99 row is the official reported
# total from the institution.
#
# ASSUMES:
#   - Each unitid has exactly one row with race=99 (verified below)
#   - Each unitid has at most one row per URM race code (verified by aggregation)
#   - enrollment_fall is non-negative after coded value removal (nulls ok)
print("\n--- Transform: Compute URM Share ---")

# Step 1: Extract total enrollment per institution (race=99)
df_total = (
    df_agg.filter(pl.col(race_col) == RACE_TOTAL)
    .select("unitid", pl.col(ENROLLMENT_COL).alias("total_enrollment_race"))
)
print(f"Total enrollment rows (race=99): {df_total.shape[0]:,}")

total_unitid_unique = df_total["unitid"].n_unique() == df_total.shape[0]
print(f"Unitid unique in totals: {total_unitid_unique}")
assert total_unitid_unique, "STOP: Multiple total rows per unitid after aggregation"

# Step 2: Compute URM enrollment per institution
# INTENT: Sum enrollment_fall for URM race codes (2=Black, 3=Hispanic, 5=AI/AN)
# per institution. This is the numerator for URM share.
#
# REASONING: Using sum aggregation. Polars sum() skips nulls by default,
# so null enrollment values for a race code contribute 0 to the sum.
df_urm = (
    df_agg.filter(pl.col(race_col).is_in(URM_CODES))
    .group_by("unitid")
    .agg(pl.col(ENROLLMENT_COL).sum().alias("urm_enrollment"))
)
print(f"URM enrollment rows: {df_urm.shape[0]:,}")

# Step 3: Join total and URM, compute share
# INTENT: Combine total and URM enrollment per institution, then compute
# urm_share = urm_enrollment / total_enrollment_race.
#
# REASONING: Using LEFT join from totals to URM because every institution
# with a total row should be in our output. Institutions with no URM rows
# get urm_enrollment = null, which we fill with 0.
#
# ASSUMES:
#   - unitid is unique in both df_total and df_urm
#   - All institutions with URM rows also have a total row
result = df_total.join(df_urm, on="unitid", how="left")

# Fill null URM enrollment with 0
# REASONING: If no URM race codes had non-null enrollment for an institution,
# urm_enrollment is null. Filling with 0 means these institutions have 0%
# URM share, which is the correct interpretation (no URM students enrolled).
result = result.with_columns(
    pl.col("urm_enrollment").fill_null(0)
)

# Step 4: Compute URM share
# INTENT: Calculate urm_share = urm_enrollment / total_enrollment_race.
# Only compute where total > 0 to avoid division by zero.
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
post_rows = result.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {result.shape[1]} cols")
print(f"Transformation: {pre_rows:,} multi-row-per-institution -> {post_rows:,} one-row-per-institution")

# Summary statistics
print("\n--- Output Summary Statistics ---")
for col in ["total_enrollment_race", "urm_enrollment", "urm_share"]:
    s = result[col]
    print(f"{col}: min={s.min()}, max={s.max()}, mean={s.mean():.4f}, "
          f"median={s.median():.4f}, null_count={s.null_count()}")

# URM share distribution
print("\n--- URM Share Distribution ---")
urm_share_valid = result.filter(pl.col("urm_share").is_not_null())
print(f"Institutions with valid urm_share: {urm_share_valid.shape[0]:,}")
quantiles = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
for q in quantiles:
    val = urm_share_valid["urm_share"].quantile(q)
    print(f"  P{int(q*100):3d}: {val:.4f}")

# Sample output
print("\n--- Sample Output (first 5) ---")
print(result.head(5))

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
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] Unitid unique: "
      f"{result['unitid'].n_unique():,} unique vs {result.shape[0]:,} rows")

# CP2.2: URM share between 0 and 1 for all non-null values
urm_valid = result.filter(pl.col("urm_share").is_not_null())
urm_in_range = (
    urm_valid["urm_share"].min() >= 0.0 and
    urm_valid["urm_share"].max() <= 1.0
)
print(f"  [{'PASS' if urm_in_range else 'FAIL'}] URM share in [0,1]: "
      f"min={urm_valid['urm_share'].min():.4f}, max={urm_valid['urm_share'].max():.4f}")

# CP2.3: Total enrollment is positive for rows with valid urm_share
total_positive = urm_valid["total_enrollment_race"].min() > 0
print(f"  [{'PASS' if total_positive else 'FAIL'}] Total enrollment positive "
      f"(where urm_share valid): min={urm_valid['total_enrollment_race'].min()}")

# CP2.4: No coded values remain in output
coded_remaining = 0
for col in ["total_enrollment_race", "urm_enrollment"]:
    for code in CODED_MISSING.keys():
        coded_remaining += result.filter(pl.col(col) == code).shape[0]
no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")

# CP2.5: Row count in expected range (~5,000-6,000 institutions)
rows_in_range = 4000 <= result.shape[0] <= 8000
print(f"  [{'PASS' if rows_in_range else 'WARN'}] Row count in range: "
      f"{result.shape[0]:,} (expected ~5,000-6,000)")

# CP2.6: Suppression rate check
total_cells = result.shape[0] * 3
null_cells = (result["total_enrollment_race"].null_count() +
              result["urm_enrollment"].null_count() +
              result["urm_share"].null_count())
suppression_rate = null_cells / total_cells if total_cells > 0 else 0
suppression_ok = suppression_rate < 0.50
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: "
      f"{suppression_rate:.1%} ({null_cells:,} nulls / {total_cells:,} cells)")

# CP2.7: Aggregation strategy documented (informational)
print(f"  [INFO] Aggregation strategy used: {use_strategy}")
print(f"  [INFO] Race codes used for URM: {URM_CODES} (2=Black, 3=Hispanic, 5=AI/AN)")
print(f"  [INFO] Total race code used: {RACE_TOTAL}")

# CP2.8: Cross-check — sum of URM races vs total for consistency
# INTENT: Verify that urm_enrollment <= total_enrollment_race for all institutions.
# This is a basic sanity check that our aggregation didn't produce nonsensical results.
urm_leq_total = result.filter(
    pl.col("urm_enrollment") > pl.col("total_enrollment_race")
).shape[0]
consistency_ok = urm_leq_total == 0
print(f"  [{'PASS' if consistency_ok else 'WARN'}] URM <= total enrollment: "
      f"{urm_leq_total} violations")

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
# Executed: 2026-02-15 20:41:54
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/05_clean-enrollment-race_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.5: Clean IPEDS Enrollment by Race (v2 - _a.py)
# ============================================================
# Loaded: 352,410 rows x 7 cols
# Columns: ['unitid', 'year', 'enrollment_fall', 'race', 'sex', 'ftpt', 'level_of_study']
# 
# Pre-state: 352,410 rows, 7 cols
# Unique institutions: 5,837
# Rows per institution: 60.4 (expect 10 races x ~6 sub-dims = ~60)
# 
# --- Race Code Inspection ---
# Unique race codes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# Expected Portal encoding: 1=White, 2=Black, 3=Hispanic, 4=Asian, 5=AI/AN, 6=NHPI, 7=Two+, 8=Nonresident, 9=Unknown, 99=Total
# URM codes [2, 3, 5] and total code 99 all present.
# 
# --- Coded Value Inspection ---
#   No coded missing values found in enrollment_fall
# 
# --- Transform: Replace Coded Values ---
# Replaced coded values with null in enrollment_fall
# Coded values remaining: 0
# 
# --- Transform: Aggregate Sub-Dimensions ---
# Distribution of rows per unitid+race combination:
# shape: (6, 2)
# ┌────────┬───────┐
# │ n_rows ┆ count │
# │ ---    ┆ ---   │
# │ u32    ┆ u32   │
# ╞════════╪═══════╡
# │ 2      ┆ 30    │
# │ 3      ┆ 110   │
# │ 4      ┆ 1110  │
# │ 5      ┆ 21590 │
# │ 6      ┆ 9080  │
# │ 7      ┆ 26450 │
# └────────┴───────┘
# 
# Sample institution 100654, race=99 rows:
# shape: (7, 7)
# ┌────────┬──────┬─────────────────┬──────┬─────┬──────┬────────────────┐
# │ unitid ┆ year ┆ enrollment_fall ┆ race ┆ sex ┆ ftpt ┆ level_of_study │
# │ ---    ┆ ---  ┆ ---             ┆ ---  ┆ --- ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ i64             ┆ i64  ┆ i64 ┆ i64  ┆ i64            │
# ╞════════╪══════╪═════════════════╪══════╪═════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 5090            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3381            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3               ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 1535            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 174             ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3555            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 5093            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# └────────┴──────┴─────────────────┴──────┴─────┴──────┴────────────────┘
# Sum of enrollment_fall: 18831
# 
# --- Validation: Checking aggregation strategy ---
# 
# Comparing strategies for 5 sample institutions:
#   unitid=100654:
#     race=99 total: SUM=18831, MAX=5093
#     sum of races (MAX strategy): 5093
#     sum of races (SUM strategy): 18831
#     ratio (indiv/total): MAX=1.0000, SUM=1.0000
#   unitid=100663:
#     race=99 total: SUM=52700, MAX=13878
#     sum of races (MAX strategy): 13878
#     sum of races (SUM strategy): 52700
#     ratio (indiv/total): MAX=1.0000, SUM=1.0000
#   unitid=100690:
#     race=99 total: SUM=1192, MAX=298
#     sum of races (MAX strategy): 298
#     sum of races (SUM strategy): 1192
#     ratio (indiv/total): MAX=1.0000, SUM=1.0000
#   unitid=100706:
#     race=99 total: SUM=30359, MAX=8027
#     sum of races (MAX strategy): 8027
#     sum of races (SUM strategy): 30359
#     ratio (indiv/total): MAX=1.0000, SUM=1.0000
#   unitid=100724:
#     race=99 total: SUM=13459, MAX=3614
#     sum of races (MAX strategy): 3614
#     sum of races (SUM strategy): 13459
#     ratio (indiv/total): MAX=1.0000, SUM=1.0000
# 
# --- Broader aggregation strategy validation ---
# SUM strategy: mean ratio (indiv/total) = 1.0000, median = 1.0000
# MAX strategy: mean ratio (indiv/total) = 1.0000, median = 1.0000
# 
# Using MAX strategy (closer to ratio=1.0, max_ratio=1.0000)
# 
# Aggregated: 58,370 rows (from 352,410)
# Unique unitid+race combinations: 58,370
# One row per unitid+race: True
# 
# --- Transform: Compute URM Share ---
# Total enrollment rows (race=99): 5,837
# Unitid unique in totals: True
# URM enrollment rows: 5,837
# 
# Aggregated result: 5,837 rows x 4 cols
# Columns: ['unitid', 'total_enrollment_race', 'urm_enrollment', 'urm_share']
# 
# Post-state: 5,837 rows, 4 cols
# Transformation: 352,410 multi-row-per-institution -> 5,837 one-row-per-institution
# 
# --- Output Summary Statistics ---
# total_enrollment_race: min=1, max=111599, mean=2817.4435, median=519.0000, null_count=0
# urm_enrollment: min=0, max=51922, mean=952.8474, median=163.0000, null_count=0
# urm_share: min=0.0, max=1.0, mean=0.3816, median=0.3110, null_count=0
# 
# --- URM Share Distribution ---
# Institutions with valid urm_share: 5,837
#   P  0: 0.0000
#   P 10: 0.0750
#   P 25: 0.1541
#   P 50: 0.3110
#   P 75: 0.5657
#   P 90: 0.8348
#   P100: 1.0000
# 
# --- Sample Output (first 5) ---
# shape: (5, 4)
# ┌────────┬───────────────────────┬────────────────┬───────────┐
# │ unitid ┆ total_enrollment_race ┆ urm_enrollment ┆ urm_share │
# │ ---    ┆ ---                   ┆ ---            ┆ ---       │
# │ i64    ┆ i64                   ┆ i64            ┆ f64       │
# ╞════════╪═══════════════════════╪════════════════╪═══════════╡
# │ 110538 ┆ 15747                 ┆ 6149           ┆ 0.390487  │
# │ 112455 ┆ 86                    ┆ 66             ┆ 0.767442  │
# │ 475468 ┆ 226                   ┆ 105            ┆ 0.464602  │
# │ 476568 ┆ 8                     ┆ 8              ┆ 1.0       │
# │ 476610 ┆ 52                    ┆ 47             ┆ 0.903846  │
# └────────┴───────────────────────┴────────────────┴───────────┘
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_enrollment_race_clean.parquet
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] Unitid unique: 5,837 unique vs 5,837 rows
#   [PASS] URM share in [0,1]: min=0.0000, max=1.0000
#   [PASS] Total enrollment positive (where urm_share valid): min=1
#   [PASS] No coded values remaining: 0
#   [PASS] Row count in range: 5,837 (expected ~5,000-6,000)
#   [PASS] Suppression rate < 50%: 0.0% (0 nulls / 17,511 cells)
#   [INFO] Aggregation strategy used: MAX
#   [INFO] Race codes used for URM: [2, 3, 5] (2=Black, 3=Hispanic, 5=AI/AN)
#   [INFO] Total race code used: 99
#   [PASS] URM <= total enrollment: 0 violations
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
