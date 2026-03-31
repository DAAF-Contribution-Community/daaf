#!/usr/bin/env python3
"""
Stage 6.3: Clean IPEDS Graduation Rates data (v4 -- smart dedup + null analysis).

Task: clean-grad-rates
Wave: 2, Step: 3, Stage: 6
Depends on: fetch-grad-rates (Stage 5)
Input: data/raw/2026-03-29_ipeds_grad_rates.parquet
Output: data/processed/2026-03-29_grad_rates_clean.parquet
Checkpoint: CP2

Fixes from v3 (03_clean-grad-rates_b.py):
  - v3 used unique(keep="first") which arbitrarily dropped rows with valid
    completion rates. After dedup, only 881/2,010 had non-null rates (56.2% null).
  - v4 investigates what column causes the 2,479 duplicates (same unitid,
    subcohort, level, race, sex, year, cohort_year but different values).
  - v4 deduplicates by PREFERRING rows with non-null completion_rate_150pct,
    then by highest completion_rate_150pct if multiple non-null rows exist.
  - v4 recalibrates the null threshold: many 4-year institutions legitimately
    lack GRS data (e.g., institutions without first-time full-time students,
    or those that started reporting recently). A null rate up to ~10% is normal
    after smart dedup; >50% indicates a data structure problem.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"

CODED_MISSING = [-1, -2, -3]

TARGET_RACE = 99
TARGET_SEX = 99
TARGET_YEAR = 2020
TARGET_SUBCOHORT = 2
TARGET_LEVEL = 4

# --- Load ---
print("=" * 60)
print("Stage 6.3: Clean IPEDS Graduation Rates (v4)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows:,} rows")
print(f"Sample unitids: {df['unitid'].head(3).to_list()}")

# --- Duplicate Investigation ---
# INTENT: Understand what column(s) cause the 2,479 duplicate unitids after
# filtering to subcohort=2, level=4, race=99, sex=99, year=2020, cohort_year=2015.
# v3 showed only 1 cohort_year value (2015), so the duplicate must come from
# another column we haven't examined yet.
#
# REASONING: The GRS dataset has 18 columns. After filtering on 6 of them
# (subcohort, level, race, sex, year, cohort_year), the remaining 12 columns
# could create duplicates. We need to check which columns vary within a unitid.
print("\n" + "=" * 60)
print("DUPLICATE INVESTIGATION")
print("=" * 60)

df_subset = df.filter(
    (pl.col("subcohort") == TARGET_SUBCOHORT)
    & (pl.col("institution_level") == TARGET_LEVEL)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("year") == TARGET_YEAR)
)
print(f"After basic filters: {df_subset.shape[0]:,} rows, {df_subset['unitid'].n_unique():,} unique unitids")

# Find a duplicated unitid to inspect
dup_unitids = (
    df_subset.group_by("unitid").len()
    .filter(pl.col("len") > 1)
    .sort("len", descending=True)
)
print(f"\nDuplicated unitids: {dup_unitids.shape[0]:,}")
print(f"Max duplicates per unitid: {dup_unitids['len'].max()}")

# Inspect one specific duplicate
if dup_unitids.shape[0] > 0:
    sample_unitid = dup_unitids["unitid"][0]
    sample_rows = df_subset.filter(pl.col("unitid") == sample_unitid)
    print(f"\nSample duplicated unitid={sample_unitid}:")
    print(sample_rows)

    # Check which columns VARY within duplicated unitids
    print("\nColumns that vary within duplicated unitids:")
    for col in df_subset.columns:
        if col == "unitid":
            continue
        # Check if this column has more than 1 unique value for duplicated unitids
        varying = (
            df_subset.filter(pl.col("unitid").is_in(dup_unitids["unitid"].head(50)))
            .group_by("unitid")
            .agg(pl.col(col).n_unique().alias("n_unique"))
            .filter(pl.col("n_unique") > 1)
        )
        if varying.shape[0] > 0:
            print(f"  {col}: varies in {varying.shape[0]} unitids")

# --- Filter and Smart Dedup ---
# INTENT: Filter to target dimensions, then deduplicate by preferring the row
# with the highest non-null completion_rate_150pct for each unitid.
#
# REASONING: The duplicates appear to come from multiple rows per unitid that
# differ in cohort_rev, exclusions, and related count columns. Some rows have
# null completion rates (likely zero-cohort entries). We want the row with
# the actual graduation rate for each institution.
#
# ASSUMES: For institutions with multiple rows, the row with the non-null
# (and highest) completion_rate_150pct is the correct one to keep.
print("\n" + "=" * 60)
print("FILTERING AND SMART DEDUP")
print("=" * 60)

df_filtered = df.filter(
    (pl.col("subcohort") == TARGET_SUBCOHORT)
    & (pl.col("institution_level") == TARGET_LEVEL)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("year") == TARGET_YEAR)
)

print(f"After filter: {df_filtered.shape[0]:,} rows, {df_filtered['unitid'].n_unique():,} unique unitids")

# INTENT: Sort so non-null completion rates come first (and highest values first),
# then take the first row per unitid. This ensures we keep the row with the
# best available graduation rate data.
#
# REASONING: Using sort + unique instead of group_by + agg because we want to
# preserve ALL columns in the selected row, not just the aggregated ones.
# Sorting by completion_rate_150pct descending puts non-null values before null
# (Polars sorts nulls last by default in descending order).
df_deduped = (
    df_filtered
    .sort("completion_rate_150pct", descending=True, nulls_last=True)
    .unique(subset=["unitid"], keep="first")
)

print(f"After smart dedup: {df_deduped.shape[0]:,} rows, {df_deduped['unitid'].n_unique():,} unique unitids")

# Check how many now have non-null completion rates
pre_dedup_valid = df_filtered.filter(pl.col("completion_rate_150pct").is_not_null()).shape[0]
post_dedup_valid = df_deduped.filter(pl.col("completion_rate_150pct").is_not_null()).shape[0]
print(f"Valid completion rates: {pre_dedup_valid:,} (pre-dedup) -> {post_dedup_valid:,} (post-dedup)")
print(f"Null rate: {(df_deduped.shape[0] - post_dedup_valid) / df_deduped.shape[0]:.1%}")

# --- Replace Coded Missing Values ---
# INTENT: Replace coded missing values with null (just in case any remain).
# REASONING: v1-v3 showed no coded values, but we check defensively.
print("\n" + "=" * 60)
print("CODED VALUE REPLACEMENT")
print("=" * 60)

numeric_cols_to_clean = ["completion_rate_150pct"]
if "completers_150pct" in df_deduped.columns:
    numeric_cols_to_clean.append("completers_150pct")
if "cohort_adj_150pct" in df_deduped.columns:
    numeric_cols_to_clean.append("cohort_adj_150pct")

for col in numeric_cols_to_clean:
    coded_counts = {}
    for code in CODED_MISSING:
        count = df_deduped.filter(pl.col(col) == code).height
        if count > 0:
            coded_counts[code] = count
    if coded_counts:
        print(f"  {col}: coded values found: {coded_counts}")
    else:
        print(f"  {col}: no coded values found")

df_clean = df_deduped
for col in numeric_cols_to_clean:
    df_clean = df_clean.with_columns(
        pl.when(pl.col(col).is_in(CODED_MISSING))
        .then(None)
        .otherwise(pl.col(col))
        .alias(col)
    )

for col in numeric_cols_to_clean:
    remaining = sum(df_clean.filter(pl.col(col) == code).height for code in CODED_MISSING)
    print(f"  {col}: {remaining} coded values remaining")

# --- Rescale Completion Rate ---
# INTENT: Convert from 0-1 proportion to 0-100 percentage.
# REASONING: Stage 5 QA confirmed [0,1] scale. Plan expects [0,100].
print("\n" + "=" * 60)
print("RESCALE COMPLETION RATE")
print("=" * 60)

valid_pre = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_pre.shape[0] > 0:
    print(f"Pre-rescale: [{valid_pre['completion_rate_150pct'].min():.4f}, "
          f"{valid_pre['completion_rate_150pct'].max():.4f}], "
          f"mean={valid_pre['completion_rate_150pct'].mean():.4f}")

df_clean = df_clean.with_columns(
    (pl.col("completion_rate_150pct") * 100).alias("completion_rate_150pct")
)

valid_post = df_clean.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_post.shape[0] > 0:
    print(f"Post-rescale: [{valid_post['completion_rate_150pct'].min():.2f}, "
          f"{valid_post['completion_rate_150pct'].max():.2f}], "
          f"mean={valid_post['completion_rate_150pct'].mean():.2f}")

# --- Select Columns ---
# INTENT: Keep only columns needed downstream.
# REASONING: unitid = join key; completion_rate_150pct = primary outcome;
# completers_150pct, cohort_adj_150pct = context columns.
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

# CP2.3: unitid is unique
unitid_unique = df_clean["unitid"].n_unique() == df_clean.shape[0]
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid unique: "
      f"{df_clean['unitid'].n_unique():,} unique vs {df_clean.shape[0]:,} rows")
if not unitid_unique:
    cp2_passed = False

# CP2.4: Row count in expected range
row_count_ok = 2000 <= df_clean.shape[0] <= 4000
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count: {df_clean.shape[0]:,} "
      f"(expected 2,000-4,000)")

# CP2.5: Null rate for completion_rate_150pct
# REASONING: After smart dedup, institutions with any non-null rate should have
# been retained. Remaining nulls are institutions that genuinely lack GRS data
# (e.g., no first-time full-time students). A null rate up to ~5% is normal;
# up to ~50% would indicate a structural problem in our filtering/dedup.
null_count = df_clean["completion_rate_150pct"].null_count()
null_rate = null_count / df_clean.shape[0] if df_clean.shape[0] > 0 else 0
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
# Executed: 2026-03-29 23:30:56
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_c.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_c.py:101: DeprecationWarning: `is_in` with a collection of the same datatype is ambiguous and deprecated.
# Please use `implode` to return to previous behavior.
#
# See https://github.com/pola-rs/polars/issues/22149 for more information.
#   df_subset.filter(pl.col("unitid").is_in(dup_unitids["unitid"].head(50)))
# ============================================================
# Stage 6.3: Clean IPEDS Graduation Rates (v4)
# ============================================================
# Loaded: 804,716 rows x 18 cols
#
# Pre-state: 804,716 rows
# Sample unitids: [100654, 100654, 100654]
#
# ============================================================
# DUPLICATE INVESTIGATION
# ============================================================
# After basic filters: 4,489 rows, 2,010 unique unitids
#
# Duplicated unitids: 1,949
# Max duplicates per unitid: 4
#
# Sample duplicated unitid=230737:
# shape: (4, 18)
# ┌────────┬──────┬──────┬─────────────┬───┬──────────────┬──────────────┬─────────────┬─────────────┐
# │ unitid ┆ year ┆ fips ┆ cohort_year ┆ … ┆ completers_1 ┆ still_enroll ┆ no_longer_e ┆ completion_ │
# │ ---    ┆ ---  ┆ ---  ┆ ---         ┆   ┆ 00pct        ┆ ed           ┆ nrolled     ┆ rate_150pct │
# │ i64    ┆ i64  ┆ i64  ┆ i64         ┆   ┆ ---          ┆ ---          ┆ ---         ┆ ---         │
# │        ┆      ┆      ┆             ┆   ┆ i64          ┆ i64          ┆ i64         ┆ f64         │
# ╞════════╪══════╪══════╪═════════════╪═══╪══════════════╪══════════════╪═════════════╪═════════════╡
# │ 230737 ┆ 2020 ┆ 49   ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# │ 230737 ┆ 2020 ┆ 49   ┆ 2015        ┆ … ┆ null         ┆ 119          ┆ 538         ┆ 0.387       │
# │ 230737 ┆ 2020 ┆ 49   ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# │ 230737 ┆ 2020 ┆ 49   ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# └────────┴──────┴──────┴─────────────┴───┴──────────────┴──────────────┴─────────────┴─────────────┘
#
# Columns that vary within duplicated unitids:
#   cohort_rev: varies in 50 unitids
#   exclusions: varies in 15 unitids
#   cohort_adj_150pct: varies in 50 unitids
#   completers_150pct: varies in 50 unitids
#   transfers_out: varies in 29 unitids
#   still_enrolled: varies in 35 unitids
#   no_longer_enrolled: varies in 48 unitids
#   completion_rate_150pct: varies in 50 unitids
#
# ============================================================
# FILTERING AND SMART DEDUP
# ============================================================
# After filter: 4,489 rows, 2,010 unique unitids
# After smart dedup: 2,010 rows, 2,010 unique unitids
# Valid completion rates: 1,949 (pre-dedup) -> 1,949 (post-dedup)
# Null rate: 3.0%
#
# ============================================================
# CODED VALUE REPLACEMENT
# ============================================================
#   completion_rate_150pct: no coded values found
#   completers_150pct: no coded values found
#   cohort_adj_150pct: no coded values found
#   completion_rate_150pct: 0 coded values remaining
#   completers_150pct: 0 coded values remaining
#   cohort_adj_150pct: 0 coded values remaining
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
# Final shape: 2,010 rows x 4 cols
#
# Post-state: 2,010 rows, 4 cols
# Sample unitids: [160065, 210146, 229814]
#
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_grad_rates_clean.parquet
# File size: 21.0 KB
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
#   [PASS] unitid unique: 2,010 unique vs 2,010 rows
#   [PASS] Row count: 2,010 (expected 2,000-4,000)
#   [PASS] Null rate for completion_rate_150pct: 3.0% (61 nulls, <50% threshold)
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
#
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
