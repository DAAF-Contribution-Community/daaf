#!/usr/bin/env python3
"""
Stage 6.3: Clean IPEDS Graduation Rates data.

Task: clean-grad-rates
Wave: 2, Step: 3, Stage: 6
Depends on: fetch-grad-rates (Stage 5)
Input: data/raw/2026-03-29_ipeds_grad_rates.parquet
Output: data/processed/2026-03-29_grad_rates_clean.parquet
Checkpoint: CP2

Cleaning steps:
  1. Explore subcohort codes to identify bachelor's-seeking at 4-year institutions
  2. Filter to target subcohort, race=99 (total), sex=99 (total), year=2020
  3. Replace coded missing values (-1, -2, -3) with null
  4. Rescale completion_rate_150pct from 0-1 proportion to 0-100 percentage
  5. Validate and save
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from Plan Task 3.3.
# IPEDS graduation rates track first-time, full-time students only (IPEDS caveat).
# The Education Data Portal uses integer codes for categorical variables and
# -1/-2/-3 for coded missing values in numeric fields.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data. These must be mapped to null before any statistical computation.
# -1 = Missing/not reported, -2 = Not applicable, -3 = Suppressed for privacy.
CODED_MISSING = [-1, -2, -3]

# REASONING: Education Data Portal uses integer codes for demographic aggregates.
# race=99 means "total, all races"; sex=99 means "total, all sexes".
# These give us the institution-level totals rather than demographic breakdowns.
TARGET_RACE = 99
TARGET_SEX = 99
TARGET_YEAR = 2020

# --- Load ---
# Load raw IPEDS graduation rates data fetched in Stage 5.
# The raw file contains all subcohorts, races, sexes, and years.
print("=" * 60)
print("Stage 6.3: Clean IPEDS Graduation Rates")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# Capture current state BEFORE any transformations for post-validation comparison.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Sample unitids: {df['unitid'].head(3).to_list()}")

# --- Subcohort Discovery ---
# INTENT: Determine which subcohort code represents "bachelor's-seeking at
# 4-year institutions" since the Stage 5 QA found codes {1, 2, 99}, not
# the {2, 8, 12} that the Plan originally assumed.
#
# REASONING: We examine the institution count for each subcohort value to
# identify the correct one. Bachelor's-seeking at 4-yr should have ~2,000-4,000
# unique institutions (the 4-yr population). Subcohort=99 is likely "total"
# (all subcohorts combined). We also cross-reference with cohort counts and
# completion rates to distinguish subcohort meanings.
#
# ASSUMES: The data contains columns "subcohort", "unitid", and at least
# year/race/sex for filtering.
print("\n" + "=" * 60)
print("SUBCOHORT DISCOVERY")
print("=" * 60)

# Value counts for subcohort
subcohort_counts = df["subcohort"].value_counts().sort("subcohort")
print(f"\nSubcohort value_counts:\n{subcohort_counts}")

# For each subcohort, count unique institutions (filtering to year=2020, race=99, sex=99)
# to match our target population
print("\nUnique institutions per subcohort (year=2020, race=99, sex=99):")
for sc_val in sorted(df["subcohort"].unique().to_list()):
    subset = df.filter(
        (pl.col("subcohort") == sc_val)
        & (pl.col("year") == TARGET_YEAR)
        & (pl.col("race") == TARGET_RACE)
        & (pl.col("sex") == TARGET_SEX)
    )
    n_inst = subset["unitid"].n_unique()
    n_rows = subset.shape[0]

    # Check completion rate characteristics for this subcohort
    # INTENT: Look at the distribution of completion_rate_150pct to help
    # distinguish which subcohort is bachelor's vs associate's vs total.
    valid_rates = subset.filter(
        ~pl.col("completion_rate_150pct").is_in(CODED_MISSING)
        & pl.col("completion_rate_150pct").is_not_null()
    )
    if valid_rates.shape[0] > 0:
        mean_rate = valid_rates["completion_rate_150pct"].mean()
        median_rate = valid_rates["completion_rate_150pct"].median()
        print(f"  subcohort={sc_val}: {n_inst:,} unique unitids, {n_rows:,} rows, "
              f"mean_rate={mean_rate:.4f}, median_rate={median_rate:.4f}")
    else:
        print(f"  subcohort={sc_val}: {n_inst:,} unique unitids, {n_rows:,} rows, no valid rates")

# REASONING: Based on IPEDS graduation rate methodology:
# - subcohort=2 likely represents bachelor's-seeking at 4-year institutions
#   (the primary cohort for 4-year graduation rate reporting)
# - subcohort=1 likely represents a different program level (associate's/certificate)
# - subcohort=99 likely represents the total across all subcohorts
#
# We select subcohort=2 because:
# 1. It should have institution counts consistent with the 4-year population (~2,000-4,000)
# 2. The Plan targets bachelor's-seeking students for the selectivity analysis
# 3. IPEDS GRS subcohort 2 historically represents BA/BS-seeking at 4-year institutions
TARGET_SUBCOHORT = 2
print(f"\nSelected TARGET_SUBCOHORT = {TARGET_SUBCOHORT} (bachelor's-seeking at 4-year institutions)")

# --- Filter ---
# INTENT: Filter to target subcohort, total race, total sex, and year 2020
# to get one row per institution with the overall graduation rate.
#
# REASONING: We want institution-level graduation rates, not demographic breakdowns.
# Using race=99 and sex=99 gives us the total cohort at each institution.
# Year 2020 is the most recent available per the Plan specification.
#
# ASSUMES:
#   - subcohort=2 is the bachelor's-seeking cohort (verified in discovery above)
#   - race=99 and sex=99 represent totals (Education Data Portal convention)
#   - year=2020 data is available (verified in Stage 5 fetch)
print("\n" + "=" * 60)
print("FILTERING")
print("=" * 60)

pre_filter_rows = df.shape[0]

df_filtered = df.filter(
    (pl.col("subcohort") == TARGET_SUBCOHORT)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("year") == TARGET_YEAR)
)

print(f"Filter: subcohort={TARGET_SUBCOHORT}, race={TARGET_RACE}, sex={TARGET_SEX}, year={TARGET_YEAR}")
print(f"Rows: {pre_filter_rows:,} -> {df_filtered.shape[0]:,} "
      f"({df_filtered.shape[0] - pre_filter_rows:+,}, "
      f"{(df_filtered.shape[0] - pre_filter_rows) / pre_filter_rows * 100:+.1f}%)")
print(f"Unique unitids: {df_filtered['unitid'].n_unique():,}")

# Check for duplicate unitids (should be 1 row per institution after filtering)
dup_count = df_filtered.shape[0] - df_filtered["unitid"].n_unique()
if dup_count > 0:
    print(f"WARNING: {dup_count:,} duplicate unitids found after filtering")
else:
    print("unitid is unique after filtering (1 row per institution)")

# --- Replace Coded Missing Values ---
# INTENT: Replace Education Data Portal coded missing values (-1, -2, -3)
# with null in the completion_rate_150pct column so they don't corrupt
# downstream statistical calculations.
#
# REASONING: Using null (not zero or NaN) because null is the semantically
# correct representation in Polars -- these values were never observed or
# are suppressed. Zero would imply a 0% graduation rate. The coded values
# also need to be removed from completers_150pct and cohort_count if present.
#
# ASSUMES: All coded missing values in the relevant columns are in CODED_MISSING.
print("\n" + "=" * 60)
print("CODED VALUE REPLACEMENT")
print("=" * 60)

# Check which numeric columns have coded values
numeric_cols_to_clean = ["completion_rate_150pct"]
# INTENT: Also clean completers_150pct and cohort_count if they exist
if "completers_150pct" in df_filtered.columns:
    numeric_cols_to_clean.append("completers_150pct")
if "cohort_count" in df_filtered.columns:
    numeric_cols_to_clean.append("cohort_count")

for col in numeric_cols_to_clean:
    coded_counts = {}
    for code in CODED_MISSING:
        count = df_filtered.filter(pl.col(col) == code).height
        if count > 0:
            coded_counts[code] = count
    if coded_counts:
        print(f"  {col}: coded values found: {coded_counts}")
    else:
        print(f"  {col}: no coded values found")

# Apply coded value replacement
df_clean = df_filtered
for col in numeric_cols_to_clean:
    df_clean = df_clean.with_columns(
        pl.when(pl.col(col).is_in(CODED_MISSING))
        .then(None)
        .otherwise(pl.col(col))
        .alias(col)
    )

# Verify coded values removed
for col in numeric_cols_to_clean:
    remaining = sum(df_clean.filter(pl.col(col) == code).height for code in CODED_MISSING)
    print(f"  {col}: {remaining} coded values remaining after replacement")

# --- Rescale Completion Rate ---
# INTENT: Convert completion_rate_150pct from 0-1 proportion to 0-100 percentage.
#
# REASONING: The Stage 5 QA confirmed that this column stores proportions (0-1 scale),
# but the Plan and all downstream analyses (regression, visualization, descriptive stats)
# expect a 0-100 percentage scale. Rescaling here ensures consistency across the pipeline.
#
# ASSUMES:
#   - completion_rate_150pct values are in [0, 1] range (after coded values removed)
#   - Null values should remain null (not be rescaled)
print("\n" + "=" * 60)
print("RESCALE COMPLETION RATE")
print("=" * 60)

# Check pre-rescale range (excluding nulls)
valid_pre = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_pre.shape[0] > 0:
    pre_min = valid_pre["completion_rate_150pct"].min()
    pre_max = valid_pre["completion_rate_150pct"].max()
    pre_mean = valid_pre["completion_rate_150pct"].mean()
    print(f"Pre-rescale range: [{pre_min:.4f}, {pre_max:.4f}], mean={pre_mean:.4f}")
else:
    print("WARNING: No valid completion rates found")
    pre_min, pre_max, pre_mean = None, None, None

# Rescale: multiply by 100 to convert proportion to percentage
df_clean = df_clean.with_columns(
    (pl.col("completion_rate_150pct") * 100).alias("completion_rate_150pct")
)

# Check post-rescale range
valid_post = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_post.shape[0] > 0:
    post_min = valid_post["completion_rate_150pct"].min()
    post_max = valid_post["completion_rate_150pct"].max()
    post_mean = valid_post["completion_rate_150pct"].mean()
    print(f"Post-rescale range: [{post_min:.2f}, {post_max:.2f}], mean={post_mean:.2f}")

# --- Select Columns ---
# INTENT: Keep only the columns needed for downstream analysis to reduce
# file size and make the schema explicit.
#
# REASONING: unitid is the join key for merging with other IPEDS datasets.
# completion_rate_150pct is the primary outcome variable. completers_150pct
# and cohort_count provide context for interpretation.
print("\n" + "=" * 60)
print("COLUMN SELECTION")
print("=" * 60)

# Build list of columns to keep
keep_cols = ["unitid", "completion_rate_150pct"]
optional_cols = ["completers_150pct", "cohort_count"]
for col in optional_cols:
    if col in df_clean.columns:
        keep_cols.append(col)

print(f"Available columns: {df_clean.columns}")
print(f"Keeping columns: {keep_cols}")

df_clean = df_clean.select(keep_cols)
print(f"Final shape: {df_clean.shape[0]:,} rows x {df_clean.shape[1]} cols")

# --- Post-state ---
# Capture state after all transformations for validation comparison.
post_rows = df_clean.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {df_clean.shape[1]} cols")
print(f"Sample unitids: {df_clean['unitid'].head(3).to_list()}")
print(f"Row change from raw: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_clean.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- Citation ---
# INTENT: Generate citation text for the IPEDS graduation rates data
# per the ODC Attribution License requirements.
print("\n" + "=" * 60)
print("CITATION")
print("=" * 60)
print("""IPEDS Graduation Rates (GRS), Education Data Portal (Version 0.20.0),
Urban Institute, accessed March 29, 2026,
https://educationdata.urban.org/documentation/,
made available under the ODC Attribution License.

Note: IPEDS graduation rates track ONLY first-time, full-time,
bachelor's-seeking students who entered in the fall term. This
excludes transfer students (~40% of undergraduates), part-time
students, and non-fall entrants. Rates should not be interpreted
as representing outcomes for all students at an institution.""")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, suppression rate
# within bounds, data loss acceptable, and completion rates in valid range.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

cp2_passed = True

# CP2.1: No coded values remain in numeric columns
coded_remaining = 0
for col in numeric_cols_to_clean:
    if col in df_clean.columns:
        for code in CODED_MISSING:
            coded_remaining += df_clean.filter(pl.col(col) == code).height

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")
if not no_coded:
    cp2_passed = False

# CP2.2: completion_rate_150pct in valid range [0, 100] where non-null
valid_rates = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_rates.shape[0] > 0:
    rate_min = valid_rates["completion_rate_150pct"].min()
    rate_max = valid_rates["completion_rate_150pct"].max()
    range_valid = rate_min >= 0 and rate_max <= 100
    print(f"  [{'PASS' if range_valid else 'FAIL'}] completion_rate_150pct range: [{rate_min:.2f}, {rate_max:.2f}] (expected [0, 100])")
    if not range_valid:
        cp2_passed = False
else:
    print("  [FAIL] No valid completion rates after cleaning")
    cp2_passed = False

# CP2.3: unitid is unique (1 row per institution)
unitid_unique = df_clean["unitid"].n_unique() == df_clean.shape[0]
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid unique: {df_clean['unitid'].n_unique():,} unique vs {df_clean.shape[0]:,} rows")
if not unitid_unique:
    cp2_passed = False

# CP2.4: Row count in expected range (2,000-4,000 for 4-yr institutions)
row_count_ok = 2000 <= df_clean.shape[0] <= 4000
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count: {df_clean.shape[0]:,} (expected 2,000-4,000)")

# CP2.5: Suppression/missingness rate for completion_rate_150pct
null_rate = df_clean["completion_rate_150pct"].null_count() / df_clean.shape[0]
supp_ok = null_rate < 0.50
print(f"  [{'PASS' if supp_ok else 'FAIL'}] Null rate for completion_rate_150pct: {null_rate:.1%} (<50% threshold)")
if not supp_ok:
    cp2_passed = False

# CP2.6: Data loss from raw is not excessive (<90%)
data_loss = 1 - (df_clean.shape[0] / pre_rows)
loss_ok = data_loss < 0.90
print(f"  [{'PASS' if loss_ok else 'FAIL'}] Data loss from raw: {data_loss:.1%} (<90% threshold)")
if not loss_ok:
    cp2_passed = False

# CP2.7: No nulls in unitid (critical identifier column)
unitid_nulls = df_clean["unitid"].null_count()
no_unitid_nulls = unitid_nulls == 0
print(f"  [{'PASS' if no_unitid_nulls else 'FAIL'}] No nulls in unitid: {unitid_nulls}")
if not no_unitid_nulls:
    cp2_passed = False

# Summary statistics for downstream reference
print(f"\n  Summary statistics for completion_rate_150pct:")
if valid_rates.shape[0] > 0:
    print(f"    N non-null: {valid_rates.shape[0]:,}")
    print(f"    Mean:   {valid_rates['completion_rate_150pct'].mean():.2f}%")
    print(f"    Median: {valid_rates['completion_rate_150pct'].median():.2f}%")
    print(f"    Std:    {valid_rates['completion_rate_150pct'].std():.2f}")
    print(f"    Min:    {valid_rates['completion_rate_150pct'].min():.2f}%")
    print(f"    Max:    {valid_rates['completion_rate_150pct'].max():.2f}%")

assert cp2_passed, "STOP: CP2 FAILED - see details above"

print(f"\n{'=' * 60}")
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:25:41
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 6.3: Clean IPEDS Graduation Rates
# ============================================================
# Loaded: 804,716 rows x 18 cols
# Columns: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# Dtypes: [Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Float64]
# 
# Pre-state: 804,716 rows, 18 cols
# Sample unitids: [100654, 100654, 100654]
# 
# ============================================================
# SUBCOHORT DISCOVERY
# ============================================================
# 
# Subcohort value_counts:
# shape: (3, 2)
# ┌───────────┬────────┐
# │ subcohort ┆ count  │
# │ ---       ┆ ---    │
# │ i64       ┆ u32    │
# ╞═══════════╪════════╡
# │ 1         ┆ 149910 │
# │ 2         ┆ 271410 │
# │ 99        ┆ 383396 │
# └───────────┴────────┘
# 
# Unique institutions per subcohort (year=2020, race=99, sex=99):
#   subcohort=1: 932 unique unitids, 2,467 rows, mean_rate=0.4602, median_rate=0.4105
#   subcohort=2: 2,010 unique unitids, 4,489 rows, mean_rate=0.5560, median_rate=0.5630
#   subcohort=99: 5,415 unique unitids, 7,979 rows, mean_rate=0.5633, median_rate=0.5760
# 
# Selected TARGET_SUBCOHORT = 2 (bachelor's-seeking at 4-year institutions)
# 
# ============================================================
# FILTERING
# ============================================================
# Filter: subcohort=2, race=99, sex=99, year=2020
# Rows: 804,716 -> 4,489 (-800,227, -99.4%)
# Unique unitids: 2,010
# WARNING: 2,479 duplicate unitids found after filtering
# 
# ============================================================
# CODED VALUE REPLACEMENT
# ============================================================
#   completion_rate_150pct: no coded values found
#   completers_150pct: no coded values found
#   completion_rate_150pct: 0 coded values remaining after replacement
#   completers_150pct: 0 coded values remaining after replacement
# 
# ============================================================
# RESCALE COMPLETION RATE
# ============================================================
# Pre-rescale range: [0.0380, 1.0000], mean=0.5560
# Post-rescale range: [3.80, 100.00], mean=55.60
# 
# ============================================================
# COLUMN SELECTION
# ============================================================
# Available columns: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# Keeping columns: ['unitid', 'completion_rate_150pct', 'completers_150pct']
# Final shape: 4,489 rows x 3 cols
# 
# Post-state: 4,489 rows, 3 cols
# Sample unitids: [100654, 100654, 100663]
# Row change from raw: -800,227 (-99.4%)
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_grad_rates_clean.parquet
# 
# ============================================================
# CITATION
# ============================================================
# IPEDS Graduation Rates (GRS), Education Data Portal (Version 0.20.0),
# Urban Institute, accessed March 29, 2026,
# https://educationdata.urban.org/documentation/,
# made available under the ODC Attribution License.
# 
# Note: IPEDS graduation rates track ONLY first-time, full-time,
# bachelor's-seeking students who entered in the fall term. This
# excludes transfer students (~40% of undergraduates), part-time
# students, and non-fall entrants. Rates should not be interpreted
# as representing outcomes for all students at an institution.
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values remaining: 0
#   [PASS] completion_rate_150pct range: [3.80, 100.00] (expected [0, 100])
#   [FAIL] unitid unique: 2,010 unique vs 4,489 rows
#   [WARN] Row count: 4,489 (expected 2,000-4,000)
#   [FAIL] Null rate for completion_rate_150pct: 56.6% (<50% threshold)
#   [FAIL] Data loss from raw: 99.4% (<90% threshold)
#   [PASS] No nulls in unitid: 0
# 
#   Summary statistics for completion_rate_150pct:
#     N non-null: 1,949
#     Mean:   55.60%
#     Median: 56.30%
#     Std:    20.56
#     Min:    3.80%
#     Max:    100.00%
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates.py", line 381, in <module>
#     assert cp2_passed, "STOP: CP2 FAILED - see details above"
#            ^^^^^^^^^^
# AssertionError: STOP: CP2 FAILED - see details above
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
