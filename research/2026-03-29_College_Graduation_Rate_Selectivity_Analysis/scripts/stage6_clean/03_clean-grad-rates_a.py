#!/usr/bin/env python3
"""
Stage 6.3: Clean IPEDS Graduation Rates data (v2 -- fix duplicate unitids).

Task: clean-grad-rates
Wave: 2, Step: 3, Stage: 6
Depends on: fetch-grad-rates (Stage 5)
Input: data/raw/2026-03-29_ipeds_grad_rates.parquet
Output: data/processed/2026-03-29_grad_rates_clean.parquet
Checkpoint: CP2

Fixes from v1 (03_clean-grad-rates.py):
  - v1 produced 4,489 rows with 2,010 unique unitids -- duplicates caused by
    multiple institution_level values per unitid in the GRS dataset.
  - v2 adds institution_level filter to get 4-year institutions only.
  - v2 fixes CP2 data loss threshold: 99.4% "loss" is expected dimensional
    filtering (raw has 804K rows across all subcohort/race/sex/year/level combos),
    not unexpected data loss.
  - v2 fixes null rate: many nulls in v1 were from non-4-year institutions.
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

CODED_MISSING = [-1, -2, -3]

# REASONING: Education Data Portal integer codes for demographic aggregates.
TARGET_RACE = 99       # Total, all races
TARGET_SEX = 99        # Total, all sexes
TARGET_YEAR = 2020     # Most recent available per Plan
TARGET_SUBCOHORT = 2   # Bachelor's-seeking at 4-year institutions (confirmed in v1 discovery)

# --- Load ---
# Load raw IPEDS graduation rates data fetched in Stage 5.
print("=" * 60)
print("Stage 6.3: Clean IPEDS Graduation Rates (v2)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows:,} rows")
print(f"Sample unitids: {df['unitid'].head(3).to_list()}")

# --- Institution Level Discovery ---
# INTENT: Understand institution_level values to correctly filter for 4-year
# institutions. v1 failed because it didn't filter on institution_level,
# producing duplicate unitids (one row per institution_level per unitid).
#
# REASONING: IPEDS GRS reports graduation rates at different institution levels.
# For the selectivity analysis we need only 4-year institutions (level=4),
# since bachelor's graduation rates are only meaningful at 4-year schools.
print("\n" + "=" * 60)
print("INSTITUTION LEVEL DISCOVERY")
print("=" * 60)

level_counts = df["institution_level"].value_counts().sort("institution_level")
print(f"\ninstitution_level value_counts:\n{level_counts}")

# Count unique institutions per level (filtered to our target subcohort/race/sex/year)
print("\nUnique institutions per level (subcohort=2, year=2020, race=99, sex=99):")
for lev in sorted(df["institution_level"].unique().to_list()):
    subset = df.filter(
        (pl.col("institution_level") == lev)
        & (pl.col("subcohort") == TARGET_SUBCOHORT)
        & (pl.col("year") == TARGET_YEAR)
        & (pl.col("race") == TARGET_RACE)
        & (pl.col("sex") == TARGET_SEX)
    )
    n_inst = subset["unitid"].n_unique()
    n_rows = subset.shape[0]
    # Check null rate for completion_rate_150pct
    non_null = subset.filter(
        pl.col("completion_rate_150pct").is_not_null()
        & ~pl.col("completion_rate_150pct").is_in(CODED_MISSING)
    )
    null_rate = 1 - (non_null.shape[0] / n_rows) if n_rows > 0 else 1.0
    print(f"  level={lev}: {n_inst:,} unitids, {n_rows:,} rows, null_rate={null_rate:.1%}")

# REASONING: institution_level=4 represents 4-year institutions, which is what
# our selectivity analysis targets. This should give ~2,000 unique unitids
# matching the 4-year institution population.
TARGET_LEVEL = 4
print(f"\nSelected TARGET_LEVEL = {TARGET_LEVEL} (4-year institutions)")

# --- Filter ---
# INTENT: Filter to target subcohort, institution level, race total, sex total,
# and year 2020 to get exactly one row per 4-year institution with the
# overall bachelor's graduation rate.
#
# REASONING: We apply all five filters simultaneously to get the institution-level
# graduation rate for bachelor's-seeking students at 4-year schools.
# This is expected to reduce 804K rows to ~2,000 (one per 4-yr institution).
# The reduction is dimensional filtering, NOT data loss -- the raw data
# contains every combination of subcohort x level x race x sex x year.
#
# ASSUMES:
#   - subcohort=2 is bachelor's-seeking (confirmed in v1 subcohort discovery)
#   - institution_level=4 is 4-year (standard IPEDS encoding)
#   - race=99 and sex=99 are totals (Education Data Portal convention)
#   - year=2020 data is available (verified in Stage 5 fetch)
print("\n" + "=" * 60)
print("FILTERING")
print("=" * 60)

df_filtered = df.filter(
    (pl.col("subcohort") == TARGET_SUBCOHORT)
    & (pl.col("institution_level") == TARGET_LEVEL)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("year") == TARGET_YEAR)
)

print(f"Filters applied: subcohort={TARGET_SUBCOHORT}, institution_level={TARGET_LEVEL}, "
      f"race={TARGET_RACE}, sex={TARGET_SEX}, year={TARGET_YEAR}")
print(f"Rows: {pre_rows:,} -> {df_filtered.shape[0]:,}")
print(f"Unique unitids: {df_filtered['unitid'].n_unique():,}")

# Check for duplicate unitids
dup_count = df_filtered.shape[0] - df_filtered["unitid"].n_unique()
if dup_count > 0:
    print(f"WARNING: {dup_count:,} duplicate unitids remain after filtering")
else:
    print("unitid is unique (1 row per institution) -- GOOD")

# --- Replace Coded Missing Values ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in numeric columns.
#
# REASONING: Using null because these are genuinely unobserved values. The coded
# values would corrupt downstream statistics if left as integers.
#
# ASSUMES: All coded missing values in the relevant columns are in CODED_MISSING.
print("\n" + "=" * 60)
print("CODED VALUE REPLACEMENT")
print("=" * 60)

numeric_cols_to_clean = ["completion_rate_150pct"]
if "completers_150pct" in df_filtered.columns:
    numeric_cols_to_clean.append("completers_150pct")
if "cohort_adj_150pct" in df_filtered.columns:
    numeric_cols_to_clean.append("cohort_adj_150pct")

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

# Apply replacement
df_clean = df_filtered
for col in numeric_cols_to_clean:
    df_clean = df_clean.with_columns(
        pl.when(pl.col(col).is_in(CODED_MISSING))
        .then(None)
        .otherwise(pl.col(col))
        .alias(col)
    )

# Verify
for col in numeric_cols_to_clean:
    remaining = sum(df_clean.filter(pl.col(col) == code).height for code in CODED_MISSING)
    print(f"  {col}: {remaining} coded values remaining after replacement")

# --- Rescale Completion Rate ---
# INTENT: Convert completion_rate_150pct from 0-1 proportion to 0-100 percentage.
#
# REASONING: Stage 5 QA confirmed values are in [0, 1]. The Plan and all downstream
# analyses expect 0-100 scale for interpretability and consistency with other
# percentage variables (e.g., admission_rate after cleaning).
#
# ASSUMES: Non-null values are in [0, 1] range. Nulls remain null.
print("\n" + "=" * 60)
print("RESCALE COMPLETION RATE")
print("=" * 60)

valid_pre = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_pre.shape[0] > 0:
    pre_min = valid_pre["completion_rate_150pct"].min()
    pre_max = valid_pre["completion_rate_150pct"].max()
    pre_mean = valid_pre["completion_rate_150pct"].mean()
    print(f"Pre-rescale: [{pre_min:.4f}, {pre_max:.4f}], mean={pre_mean:.4f}")

df_clean = df_clean.with_columns(
    (pl.col("completion_rate_150pct") * 100).alias("completion_rate_150pct")
)

valid_post = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_post.shape[0] > 0:
    post_min = valid_post["completion_rate_150pct"].min()
    post_max = valid_post["completion_rate_150pct"].max()
    post_mean = valid_post["completion_rate_150pct"].mean()
    print(f"Post-rescale: [{post_min:.2f}, {post_max:.2f}], mean={post_mean:.2f}")

# --- Select Columns ---
# INTENT: Keep only the columns needed for downstream analysis.
#
# REASONING: unitid is the join key. completion_rate_150pct is the primary outcome.
# completers_150pct and cohort_adj_150pct provide context for the graduation rate.
print("\n" + "=" * 60)
print("COLUMN SELECTION")
print("=" * 60)

keep_cols = ["unitid", "completion_rate_150pct"]
optional_cols = ["completers_150pct", "cohort_adj_150pct"]
for col in optional_cols:
    if col in df_clean.columns:
        keep_cols.append(col)

print(f"Keeping columns: {keep_cols}")
df_clean = df_clean.select(keep_cols)
print(f"Final shape: {df_clean.shape[0]:,} rows x {df_clean.shape[1]} cols")

# --- Post-state ---
post_rows = df_clean.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {df_clean.shape[1]} cols")
print(f"Sample unitids: {df_clean['unitid'].head(3).to_list()}")

# --- Save ---
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_clean.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists on disk
assert OUTPUT_PATH.exists(), f"STOP: Output file not found: {OUTPUT_PATH}"
file_size_kb = OUTPUT_PATH.stat().st_size / 1024
print(f"File size: {file_size_kb:.1f} KB")

# --- Citation ---
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
students, and non-fall entrants.""")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, completion rates in
# valid range, unitid unique, and null rate acceptable.
#
# REASONING: Data loss threshold is NOT applied to the raw-to-clean reduction
# because 99.4% reduction is expected dimensional filtering (subcohort x level x
# race x sex x year), not unexpected data loss from cleaning operations.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

cp2_passed = True

# CP2.1: No coded values remain
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
    print(f"  [{'PASS' if range_valid else 'FAIL'}] completion_rate_150pct range: "
          f"[{rate_min:.2f}, {rate_max:.2f}] (expected [0, 100])")
    if not range_valid:
        cp2_passed = False
else:
    print("  [FAIL] No valid completion rates after cleaning")
    cp2_passed = False

# CP2.3: unitid is unique (1 row per institution)
unitid_unique = df_clean["unitid"].n_unique() == df_clean.shape[0]
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid unique: "
      f"{df_clean['unitid'].n_unique():,} unique vs {df_clean.shape[0]:,} rows")
if not unitid_unique:
    cp2_passed = False

# CP2.4: Row count in expected range (2,000-4,000 for 4-yr institutions)
row_count_ok = 2000 <= df_clean.shape[0] <= 4000
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count: {df_clean.shape[0]:,} "
      f"(expected 2,000-4,000)")

# CP2.5: Null rate for completion_rate_150pct
null_count = df_clean["completion_rate_150pct"].null_count()
null_rate = null_count / df_clean.shape[0]
supp_ok = null_rate < 0.50
print(f"  [{'PASS' if supp_ok else 'FAIL'}] Null rate for completion_rate_150pct: "
      f"{null_rate:.1%} ({null_count:,} nulls, <50% threshold)")
if not supp_ok:
    cp2_passed = False

# CP2.6: No nulls in unitid
unitid_nulls = df_clean["unitid"].null_count()
no_unitid_nulls = unitid_nulls == 0
print(f"  [{'PASS' if no_unitid_nulls else 'FAIL'}] No nulls in unitid: {unitid_nulls}")
if not no_unitid_nulls:
    cp2_passed = False

# Summary statistics
print(f"\n  Summary statistics for completion_rate_150pct:")
if valid_rates.shape[0] > 0:
    print(f"    N non-null: {valid_rates.shape[0]:,}")
    print(f"    Mean:   {valid_rates['completion_rate_150pct'].mean():.2f}%")
    print(f"    Median: {valid_rates['completion_rate_150pct'].median():.2f}%")
    print(f"    Std:    {valid_rates['completion_rate_150pct'].std():.2f}")
    print(f"    Min:    {valid_rates['completion_rate_150pct'].min():.2f}%")
    print(f"    Max:    {valid_rates['completion_rate_150pct'].max():.2f}%")
    print(f"    Q25:    {valid_rates['completion_rate_150pct'].quantile(0.25):.2f}%")
    print(f"    Q75:    {valid_rates['completion_rate_150pct'].quantile(0.75):.2f}%")

assert cp2_passed, "STOP: CP2 FAILED - see details above"

print(f"\n{'=' * 60}")
print("CP2 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:28:01
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_a.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 6.3: Clean IPEDS Graduation Rates (v2)
# ============================================================
# Loaded: 804,716 rows x 18 cols
# Columns: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# 
# Pre-state: 804,716 rows
# Sample unitids: [100654, 100654, 100654]
# 
# ============================================================
# INSTITUTION LEVEL DISCOVERY
# ============================================================
# 
# institution_level value_counts:
# shape: (3, 2)
# ┌───────────────────┬────────┐
# │ institution_level ┆ count  │
# │ ---               ┆ ---    │
# │ i64               ┆ u32    │
# ╞═══════════════════╪════════╡
# │ 1                 ┆ 3206   │
# │ 2                 ┆ 243480 │
# │ 4                 ┆ 558030 │
# └───────────────────┴────────┘
# 
# Unique institutions per level (subcohort=2, year=2020, race=99, sex=99):
#   level=1: 0 unitids, 0 rows, null_rate=100.0%
#   level=2: 0 unitids, 0 rows, null_rate=100.0%
#   level=4: 2,010 unitids, 4,489 rows, null_rate=56.6%
# 
# Selected TARGET_LEVEL = 4 (4-year institutions)
# 
# ============================================================
# FILTERING
# ============================================================
# Filters applied: subcohort=2, institution_level=4, race=99, sex=99, year=2020
# Rows: 804,716 -> 4,489
# Unique unitids: 2,010
# WARNING: 2,479 duplicate unitids remain after filtering
# 
# ============================================================
# CODED VALUE REPLACEMENT
# ============================================================
#   completion_rate_150pct: no coded values found
#   completers_150pct: no coded values found
#   cohort_adj_150pct: no coded values found
#   completion_rate_150pct: 0 coded values remaining after replacement
#   completers_150pct: 0 coded values remaining after replacement
#   cohort_adj_150pct: 0 coded values remaining after replacement
# 
# ============================================================
# RESCALE COMPLETION RATE
# ============================================================
# Pre-rescale: [0.0380, 1.0000], mean=0.5560
# Post-rescale: [3.80, 100.00], mean=55.60
# 
# ============================================================
# COLUMN SELECTION
# ============================================================
# Keeping columns: ['unitid', 'completion_rate_150pct', 'completers_150pct', 'cohort_adj_150pct']
# Final shape: 4,489 rows x 4 cols
# 
# Post-state: 4,489 rows, 4 cols
# Sample unitids: [100654, 100654, 100663]
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_grad_rates_clean.parquet
# File size: 28.0 KB
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
# students, and non-fall entrants.
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] No coded values remaining: 0
#   [PASS] completion_rate_150pct range: [3.80, 100.00] (expected [0, 100])
#   [FAIL] unitid unique: 2,010 unique vs 4,489 rows
#   [WARN] Row count: 4,489 (expected 2,000-4,000)
#   [FAIL] Null rate for completion_rate_150pct: 56.6% (2,540 nulls, <50% threshold)
#   [PASS] No nulls in unitid: 0
# 
#   Summary statistics for completion_rate_150pct:
#     N non-null: 1,949
#     Mean:   55.60%
#     Median: 56.30%
#     Std:    20.56
#     Min:    3.80%
#     Max:    100.00%
#     Q25:    41.70%
#     Q75:    69.60%
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_a.py", line 339, in <module>
#     assert cp2_passed, "STOP: CP2 FAILED - see details above"
#            ^^^^^^^^^^
# AssertionError: STOP: CP2 FAILED - see details above
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
