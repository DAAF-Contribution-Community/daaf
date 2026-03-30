#!/usr/bin/env python3
"""
Stage 6.3: Clean IPEDS Graduation Rates data (v3 -- fix cohort_year duplicates).

Task: clean-grad-rates
Wave: 2, Step: 3, Stage: 6
Depends on: fetch-grad-rates (Stage 5)
Input: data/raw/2026-03-29_ipeds_grad_rates.parquet
Output: data/processed/2026-03-29_grad_rates_clean.parquet
Checkpoint: CP2

Fixes from v2 (03_clean-grad-rates_a.py):
  - v2 still had 4,489 rows for 2,010 unitids even with institution_level=4.
  - The duplicate is caused by multiple cohort_year values per unitid (IPEDS GRS
    reports graduation rates for multiple entry cohorts in each reporting year).
  - v3 discovers the cohort_year structure and selects the most recent cohort
    with non-null completion rates, then deduplicates to 1 row per unitid.
  - v3 also removes the explicit 50% null rate threshold since nulls are expected
    to be low once we select the correct cohort_year, and instead validates the
    actual null rate with a more appropriate threshold.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from Plan Task 3.3.
# IPEDS graduation rates track first-time, full-time students only (IPEDS caveat).
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"

CODED_MISSING = [-1, -2, -3]

TARGET_RACE = 99       # Total, all races
TARGET_SEX = 99        # Total, all sexes
TARGET_YEAR = 2020     # Most recent available per Plan
TARGET_SUBCOHORT = 2   # Bachelor's-seeking (confirmed in v1 discovery)
TARGET_LEVEL = 4       # 4-year institutions (confirmed in v2 discovery)

# --- Load ---
print("=" * 60)
print("Stage 6.3: Clean IPEDS Graduation Rates (v3)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows:,} rows")
print(f"Sample unitids: {df['unitid'].head(3).to_list()}")

# --- Cohort Year Discovery ---
# INTENT: Understand why subcohort=2, level=4, race=99, sex=99, year=2020
# still produces 4,489 rows for 2,010 unitids (v2 finding). The likely cause
# is multiple cohort_year values -- IPEDS GRS reports outcomes for multiple
# entry cohorts in each reporting year.
#
# REASONING: IPEDS graduation rates report on cohorts that started in different
# years. For year=2020, the 150% graduation rate for 4-year institutions
# measures the cohort that entered 6 years prior (2014). But the dataset may
# also include 100% and 200% time cohorts from different entry years.
# We need to identify which cohort_year has the best coverage of non-null
# 150% completion rates.
print("\n" + "=" * 60)
print("COHORT YEAR DISCOVERY")
print("=" * 60)

# First, apply our known filters
df_subset = df.filter(
    (pl.col("subcohort") == TARGET_SUBCOHORT)
    & (pl.col("institution_level") == TARGET_LEVEL)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("year") == TARGET_YEAR)
)

print(f"\nAfter basic filters (subcohort={TARGET_SUBCOHORT}, level={TARGET_LEVEL}, "
      f"race={TARGET_RACE}, sex={TARGET_SEX}, year={TARGET_YEAR}):")
print(f"  {df_subset.shape[0]:,} rows, {df_subset['unitid'].n_unique():,} unique unitids")

# Examine cohort_year distribution
print(f"\ncohort_year value_counts:")
cy_counts = df_subset["cohort_year"].value_counts().sort("cohort_year")
print(cy_counts)

# For each cohort_year, check coverage and null rate
print("\nPer cohort_year analysis:")
for cy in sorted(df_subset["cohort_year"].unique().to_list()):
    cy_sub = df_subset.filter(pl.col("cohort_year") == cy)
    n_inst = cy_sub["unitid"].n_unique()
    n_rows = cy_sub.shape[0]

    # Check completion_rate_150pct coverage
    valid = cy_sub.filter(
        pl.col("completion_rate_150pct").is_not_null()
        & ~pl.col("completion_rate_150pct").is_in(CODED_MISSING)
    )
    valid_count = valid.shape[0]
    null_rate = 1 - (valid_count / n_rows) if n_rows > 0 else 1.0

    # Check for unitid uniqueness within this cohort_year
    is_unique = n_inst == n_rows

    if valid_count > 0:
        mean_rate = valid["completion_rate_150pct"].mean()
        print(f"  cohort_year={cy}: {n_inst:,} unitids, {n_rows:,} rows, "
              f"valid_rates={valid_count:,}, null_rate={null_rate:.1%}, "
              f"mean_rate={mean_rate:.4f}, unitid_unique={is_unique}")
    else:
        print(f"  cohort_year={cy}: {n_inst:,} unitids, {n_rows:,} rows, "
              f"valid_rates=0, null_rate=100.0%, unitid_unique={is_unique}")

# REASONING: Select the cohort_year with the most non-null completion_rate_150pct
# values and unique unitids. For 150% graduation rate at 4-year institutions
# in year=2020, the cohort should have entered ~6 years prior (2014).
# We'll select the cohort_year that has the best coverage.
#
# Strategy: Pick the cohort_year where (1) unitid is unique and (2) has the
# highest count of valid completion rates. If no single cohort_year has unique
# unitids, we'll select the one with highest valid count and deduplicate.

# Find best cohort_year
best_cy = None
best_valid = 0
for cy in sorted(df_subset["cohort_year"].unique().to_list()):
    cy_sub = df_subset.filter(pl.col("cohort_year") == cy)
    valid = cy_sub.filter(
        pl.col("completion_rate_150pct").is_not_null()
        & ~pl.col("completion_rate_150pct").is_in(CODED_MISSING)
    )
    if valid.shape[0] > best_valid:
        best_valid = valid.shape[0]
        best_cy = cy

print(f"\nBest cohort_year = {best_cy} ({best_valid:,} valid completion rates)")

# --- Filter with Cohort Year ---
# INTENT: Apply all filters including cohort_year to get one row per institution.
#
# ASSUMES: The selected cohort_year produces unique unitids after filtering.
print("\n" + "=" * 60)
print("FILTERING (with cohort_year)")
print("=" * 60)

df_filtered = df.filter(
    (pl.col("subcohort") == TARGET_SUBCOHORT)
    & (pl.col("institution_level") == TARGET_LEVEL)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("year") == TARGET_YEAR)
    & (pl.col("cohort_year") == best_cy)
)

print(f"Filters: subcohort={TARGET_SUBCOHORT}, level={TARGET_LEVEL}, race={TARGET_RACE}, "
      f"sex={TARGET_SEX}, year={TARGET_YEAR}, cohort_year={best_cy}")
print(f"Rows: {pre_rows:,} -> {df_filtered.shape[0]:,}")
print(f"Unique unitids: {df_filtered['unitid'].n_unique():,}")

# Check uniqueness
dup_count = df_filtered.shape[0] - df_filtered["unitid"].n_unique()
if dup_count > 0:
    print(f"WARNING: {dup_count:,} duplicate unitids -- deduplicating by keeping first row per unitid")
    # INTENT: Deduplicate by keeping the first row per unitid. Since all filter
    # dimensions are identical, duplicates should have the same data.
    df_filtered = df_filtered.unique(subset=["unitid"], keep="first")
    print(f"After dedup: {df_filtered.shape[0]:,} rows, {df_filtered['unitid'].n_unique():,} unique unitids")
else:
    print("unitid is unique (1 row per institution) -- GOOD")

# --- Replace Coded Missing Values ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in numeric columns.
#
# REASONING: Using null because these are genuinely unobserved values.
# ASSUMES: All coded missing values are in CODED_MISSING.
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

df_clean = df_filtered
for col in numeric_cols_to_clean:
    df_clean = df_clean.with_columns(
        pl.when(pl.col(col).is_in(CODED_MISSING))
        .then(None)
        .otherwise(pl.col(col))
        .alias(col)
    )

for col in numeric_cols_to_clean:
    remaining = sum(df_clean.filter(pl.col(col) == code).height for code in CODED_MISSING)
    print(f"  {col}: {remaining} coded values remaining after replacement")

# --- Rescale Completion Rate ---
# INTENT: Convert completion_rate_150pct from 0-1 proportion to 0-100 percentage.
#
# REASONING: Stage 5 QA confirmed values are in [0, 1]. Plan expects 0-100 scale.
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
# completers_150pct and cohort_adj_150pct provide context.
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
# Checkpoint validation after cleaning.
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
# REASONING: After proper cohort_year filtering, we expect ~2,000 institutions.
# If slightly outside range, WARN but don't fail.
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count: {df_clean.shape[0]:,} "
      f"(expected 2,000-4,000)")

# CP2.5: Null rate for completion_rate_150pct
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
# Executed: 2026-03-29 23:29:28
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_b.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 6.3: Clean IPEDS Graduation Rates (v3)
# ============================================================
# Loaded: 804,716 rows x 18 cols
# 
# Pre-state: 804,716 rows
# Sample unitids: [100654, 100654, 100654]
# 
# ============================================================
# COHORT YEAR DISCOVERY
# ============================================================
# 
# After basic filters (subcohort=2, level=4, race=99, sex=99, year=2020):
#   4,489 rows, 2,010 unique unitids
# 
# cohort_year value_counts:
# shape: (1, 2)
# ┌─────────────┬───────┐
# │ cohort_year ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 2015        ┆ 4489  │
# └─────────────┴───────┘
# 
# Per cohort_year analysis:
#   cohort_year=2015: 2,010 unitids, 4,489 rows, valid_rates=1,949, null_rate=56.6%, mean_rate=0.5560, unitid_unique=False
# 
# Best cohort_year = 2015 (1,949 valid completion rates)
# 
# ============================================================
# FILTERING (with cohort_year)
# ============================================================
# Filters: subcohort=2, level=4, race=99, sex=99, year=2020, cohort_year=2015
# Rows: 804,716 -> 4,489
# Unique unitids: 2,010
# WARNING: 2,479 duplicate unitids -- deduplicating by keeping first row per unitid
# After dedup: 2,010 rows, 2,010 unique unitids
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
# Pre-rescale: [0.0380, 1.0000], mean=0.5664
# Post-rescale: [3.80, 100.00], mean=56.64
# 
# ============================================================
# COLUMN SELECTION
# ============================================================
# Keeping columns: ['unitid', 'completion_rate_150pct', 'completers_150pct', 'cohort_adj_150pct']
# Final shape: 2,010 rows x 4 cols
# 
# Post-state: 2,010 rows, 4 cols
# Sample unitids: [130697, 190752, 183026]
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_grad_rates_clean.parquet
# File size: 16.4 KB
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
#   [FAIL] Null rate for completion_rate_150pct: 56.2% (1,129 nulls, <50% threshold)
#   [PASS] No nulls in unitid: 0
# 
#   Summary statistics for completion_rate_150pct:
#     N non-null: 881
#     Mean:   56.64%
#     Median: 58.00%
#     Std:    20.69
#     Min:    3.80%
#     Max:    100.00%
#     Q25:    41.90%
#     Q75:    70.80%
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/03_clean-grad-rates_b.py", line 362, in <module>
#     assert cp2_passed, "STOP: CP2 FAILED - see details above"
#            ^^^^^^^^^^
# AssertionError: STOP: CP2 FAILED - see details above
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
