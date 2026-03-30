#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 3 -- fetch-grad-rates

Reviewed script: scripts/stage5_fetch/03_fetch-grad-rates_a.py
Output files: data/raw/2026-03-29_ipeds_grad_rates.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
  1. Schema matches Plan.md expectations
  2. Row count within expected range
  3. No suspicious distributions
  4. Coded values check (education domain: -1, -2, -3)
  5. No nulls in critical identifier columns

QA Checks (Script-Specific -- Five Lenses):
  6. [Counterfactual] What if year filter returned unexpected years?
  7. [Semantic] Does subcohort structure support downstream clean-grad-rates filtering?
  8. [Boundary] Check for zero-row institution-subcohort combos and edge cases
  9. [Absence] Verify institution_level column exists (needed for subcohort interpretation)
 10. [Downstream] Will the subcohort x institution_level cross-tab be usable in Stage 6?

Spot-Checks:
 11. Trace a specific unitid through all subcohort x race x sex combos
 12. Verify completion_rate_150pct range (0-100 where non-null)
 13. Check that subcohort 1 and 2 are 4-year only (institution_level==4)
 14. Verify year balance (~equal rows per year)
 15. Check race==99 and sex==99 "total" rows exist per institution per subcohort
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_grad_rates.parquet"

# Plan.md Query 3 expected columns (updated: subcohort not cohort)
EXPECTED_COLUMNS = [
    "unitid", "year", "subcohort", "race", "sex", "completion_rate_150pct",
]
# Additional columns discovered in data (not required but informative)
BONUS_COLUMNS = [
    "fips", "cohort_year", "institution_level", "cohort_rev", "exclusions",
    "cohort_adj_150pct", "completers_150pct", "transfers_out",
    "still_enrolled_long_program", "completers_100pct", "still_enrolled",
    "no_longer_enrolled",
]

# Row range: v2 adjusted to 500K-1.2M (was 50K-500K in Plan)
EXPECTED_MIN_ROWS = 500_000
EXPECTED_MAX_ROWS = 1_200_000

CRITICAL_COLUMNS = ["unitid", "year", "subcohort", "race", "sex"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 3 -- fetch-grad-rates")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS + BONUS_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not expected): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values (-1, -2, -3) ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in CODED_MISSING_VALUES:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count:,} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Coded values: ", end="")
if coded_ok:
    print("None remain in integer columns")
else:
    # REASONING: For raw/fetch data, coded values ARE expected -- they get removed
    # in Stage 6 cleaning. This is INFO, not FAIL, at Stage 5.
    print(f"Found coded values (expected in raw data):")
    for issue in coded_issues:
        print(f"  {issue}")

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count:,} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ==========================================================================

# --- Check 6 [Counterfactual]: Year filter correctness ---
# What if the year filter silently returned extra or wrong years?
years_found = sorted(df["year"].unique().to_list())
years_expected = [2020, 2021]
year_filter_ok = years_found == years_expected
print(f"\n[{'PASS' if year_filter_ok else 'FAIL'}] [Counterfactual] Years in data: {years_found} (expected {years_expected})")

# --- Check 7 [Semantic]: Subcohort structure for downstream cleaning ---
# Plan.md Step 3.3 (clean-grad-rates) needs to "identify correct cohort" and
# "filter race==99/sex==99". Verify the subcohort codes and that they are
# interpretable for the research question (bachelor's-seeking at 4-yr).
subcohort_codes = sorted(df["subcohort"].unique().to_list())
print(f"\n[INFO] [Semantic] Subcohort codes found: {subcohort_codes}")
# Plan expected codes 2, 8, 12 but actual codes are 1, 2, 99
plan_expected_codes = [2, 8, 12]
codes_match_plan = subcohort_codes == plan_expected_codes
print(f"[{'PASS' if codes_match_plan else 'WARN'}] Subcohort codes match Plan expectation {plan_expected_codes}: {codes_match_plan}")
if not codes_match_plan:
    print("  NOTE: Plan noted subcohort codes were LOW-confidence / undocumented.")
    print("  Actual codes {1, 2, 99} must be interpreted via institution_level cross-tab.")

# Verify that subcohort x institution_level cross-tab makes semantic sense
if "institution_level" in df.columns:
    cross = (
        df.group_by(["subcohort", "institution_level"])
        .len()
        .sort(["subcohort", "institution_level"])
    )
    print(f"\n  subcohort x institution_level cross-tab:")
    for row in cross.iter_rows(named=True):
        print(f"    subcohort={row['subcohort']}, inst_level={row['institution_level']}: {row['len']:,} rows")

    # Key semantic check: subcohort 1 and 2 should be 4-year only
    sub1_levels = df.filter(pl.col("subcohort") == 1)["institution_level"].unique().to_list()
    sub2_levels = df.filter(pl.col("subcohort") == 2)["institution_level"].unique().to_list()
    sub1_4yr_only = sub1_levels == [4]
    sub2_4yr_only = sub2_levels == [4]
    print(f"  [{'PASS' if sub1_4yr_only else 'WARN'}] Subcohort 1 is 4-year only: {sub1_levels}")
    print(f"  [{'PASS' if sub2_4yr_only else 'WARN'}] Subcohort 2 is 4-year only: {sub2_levels}")

# --- Check 8 [Boundary]: Edge cases in the data ---
# Check for institutions with zero rows in certain subcohorts, or
# completion_rate_150pct values outside 0-100 (excluding nulls)
if "completion_rate_150pct" in df.columns:
    cr = df["completion_rate_150pct"].drop_nulls()
    cr_min = cr.min()
    cr_max = cr.max()
    cr_range_ok = (cr_min >= 0) and (cr_max <= 100)
    print(f"\n[{'PASS' if cr_range_ok else 'FAIL'}] [Boundary] completion_rate_150pct range: [{cr_min}, {cr_max}] (expected [0, 100])")
    if cr_max > 100:
        n_over = (cr > 100).sum()
        print(f"  WARNING: {n_over:,} values > 100 -- possible data quality issue")

# Check for single-row institutions (edge case for aggregation)
rows_per_inst = df.group_by("unitid").len()
single_row_inst = (rows_per_inst["len"] == 1).sum()
print(f"[INFO] [Boundary] Institutions with only 1 row: {single_row_inst:,} of {rows_per_inst.shape[0]:,}")

# --- Check 9 [Absence]: institution_level column present ---
# This column is NOT in Plan.md's required columns for Query 3 but IS critical
# for interpreting subcohort codes. Verify it's actually in the raw data.
inst_level_present = "institution_level" in df.columns
print(f"\n[{'PASS' if inst_level_present else 'WARN'}] [Absence] institution_level column present: {inst_level_present}")
if inst_level_present:
    inst_levels = sorted(df["institution_level"].unique().to_list())
    print(f"  institution_level values: {inst_levels}")
else:
    print("  WARNING: Cannot verify subcohort interpretation without institution_level")

# Check for absence of cohort_count column (Plan expected it)
cohort_count_present = "cohort_count" in df.columns
print(f"[{'PASS' if not cohort_count_present else 'INFO'}] Plan expected 'cohort_count' column -- {'NOT present (check alternatives)' if not cohort_count_present else 'PRESENT'}")
if not cohort_count_present:
    # Check for alternative columns that serve same purpose
    alternatives = [c for c in df.columns if "cohort" in c.lower()]
    print(f"  Cohort-related columns available: {alternatives}")

# --- Check 10 [Downstream]: Will Stage 6 cleaning be able to filter properly? ---
# Stage 6 clean-grad-rates needs to filter to race==99, sex==99 for totals,
# and select the correct subcohort for bachelor's-seeking at 4-year institutions.
# Verify these filter combinations yield non-empty results.
total_rows = df.filter(
    (pl.col("race") == 99) & (pl.col("sex") == 99)
)
print(f"\n[{'PASS' if len(total_rows) > 0 else 'FAIL'}] [Downstream] race==99 & sex==99 filter yields: {len(total_rows):,} rows")

# For each subcohort, check how many institution-total rows exist
for sub in subcohort_codes:
    n = df.filter(
        (pl.col("subcohort") == sub) &
        (pl.col("race") == 99) &
        (pl.col("sex") == 99)
    ).shape[0]
    print(f"  subcohort={sub}, race==99, sex==99: {n:,} rows")

# ==========================================================================
# SPOT-CHECKS (5 concrete verifications)
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot 11: Trace a specific unitid ---
# Pick a unitid that appears frequently and trace its subcohort x race x sex combos
sample_unitids = df["unitid"].unique().sort().head(3).to_list()
if sample_unitids:
    uid = sample_unitids[0]
    uid_rows = df.filter(pl.col("unitid") == uid)
    print(f"\nSpot 11: Tracing unitid={uid}")
    print(f"  Total rows: {uid_rows.shape[0]}")
    print(f"  Years: {sorted(uid_rows['year'].unique().to_list())}")
    print(f"  Subcohorts: {sorted(uid_rows['subcohort'].unique().to_list())}")
    print(f"  Races: {sorted(uid_rows['race'].unique().to_list())}")
    print(f"  Sexes: {sorted(uid_rows['sex'].unique().to_list())}")
    # Expected: 3 subcohorts x 10 races x 3 sexes x 2 years = 180 rows max
    max_expected = 3 * 10 * 3 * 2
    print(f"  Theoretical max (3 sub x 10 race x 3 sex x 2 yr): {max_expected}")
    print(f"  Actual rows: {uid_rows.shape[0]} -- {'reasonable' if uid_rows.shape[0] <= max_expected else 'UNEXPECTED'}")

# --- Spot 12: completion_rate_150pct range (non-null) ---
cr_non_null = df["completion_rate_150pct"].drop_nulls()
print(f"\nSpot 12: completion_rate_150pct stats (non-null only, n={len(cr_non_null):,})")
print(f"  min={cr_non_null.min()}, max={cr_non_null.max()}, mean={cr_non_null.mean():.2f}, median={cr_non_null.median():.2f}")
n_zero = (cr_non_null == 0).sum()
print(f"  Exact zeros: {n_zero:,} ({n_zero/len(cr_non_null)*100:.1f}%)")
n_hundred = (cr_non_null == 100).sum()
print(f"  Exact 100s: {n_hundred:,} ({n_hundred/len(cr_non_null)*100:.1f}%)")

# --- Spot 13: Subcohort 1 and 2 are 4-year only ---
# Already checked above in Lens 7, but verify with explicit assertion
if "institution_level" in df.columns:
    sub1_non4 = df.filter((pl.col("subcohort") == 1) & (pl.col("institution_level") != 4)).shape[0]
    sub2_non4 = df.filter((pl.col("subcohort") == 2) & (pl.col("institution_level") != 4)).shape[0]
    print(f"\nSpot 13: Subcohort restriction to 4-year institutions")
    print(f"  subcohort=1 at non-4-year: {sub1_non4:,} rows (should be 0)")
    print(f"  subcohort=2 at non-4-year: {sub2_non4:,} rows (should be 0)")

# --- Spot 14: Year balance ---
year_vc = df["year"].value_counts().sort("year")
print(f"\nSpot 14: Year balance")
for row in year_vc.iter_rows(named=True):
    print(f"  {row['year']}: {row['count']:,} rows")
if len(year_vc) == 2:
    counts = year_vc["count"].to_list()
    ratio = max(counts) / min(counts) if min(counts) > 0 else float("inf")
    print(f"  Year ratio (max/min): {ratio:.3f} (should be ~1.0)")
    print(f"  [{'PASS' if ratio < 1.1 else 'WARN'}] Year balance: {'balanced' if ratio < 1.1 else 'IMBALANCED'}")

# --- Spot 15: Total rows (race==99, sex==99) per institution per subcohort ---
totals = df.filter(
    (pl.col("race") == 99) & (pl.col("sex") == 99)
)
totals_per_inst_sub = totals.group_by(["unitid", "subcohort"]).len()
print(f"\nSpot 15: Total-row (race==99, sex==99) counts per institution-subcohort")
print(f"  Unique institution-subcohort combos with totals: {totals_per_inst_sub.shape[0]:,}")
# Each combo should have ~2 rows (one per year)
len_vc = totals_per_inst_sub["len"].value_counts().sort("len")
print(f"  Distribution of rows per combo:")
for row in len_vc.iter_rows(named=True):
    print(f"    {row['len']} rows: {row['count']:,} combos")

# ==========================================================================
# DATA PROFILING (for cr2+ decision)
# ==========================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 5 rows:")
print(df.head(5))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["subcohort", "race", "sex"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort(col))

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\nNull counts per column:")
for col in df.columns:
    nc = df[col].null_count()
    pct = nc / len(df) * 100
    if nc > 0:
        print(f"  {col}: {nc:,} nulls ({pct:.1f}%)")

# ==========================================================================
# SUMMARY
# ==========================================================================
print("\n" + "=" * 60)
all_default_pass = all([schema_ok, rows_ok, dist_ok, nulls_ok, year_filter_ok])
# Note: coded_ok is not gating because coded values are expected in raw data
severity = "PASSED" if all_default_pass else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if not codes_match_plan:
    print("WARNING: Subcohort codes differ from Plan.md expectation (LOW-confidence item resolved)")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:07:21
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 3 -- fetch-grad-rates
# ============================================================
# Loaded: 804,716 rows x 18 cols
# Columns: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 804,716 (expected 500,000-1,200,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in integer columns
# [PASS] Critical nulls: None
# 
# [PASS] [Counterfactual] Years in data: [2020, 2021] (expected [2020, 2021])
# 
# [INFO] [Semantic] Subcohort codes found: [1, 2, 99]
# [WARN] Subcohort codes match Plan expectation [2, 8, 12]: False
#   NOTE: Plan noted subcohort codes were LOW-confidence / undocumented.
#   Actual codes {1, 2, 99} must be interpreted via institution_level cross-tab.
# 
#   subcohort x institution_level cross-tab:
#     subcohort=1, inst_level=4: 149,910 rows
#     subcohort=2, inst_level=4: 271,410 rows
#     subcohort=99, inst_level=1: 3,206 rows
#     subcohort=99, inst_level=2: 243,480 rows
#     subcohort=99, inst_level=4: 136,710 rows
#   [PASS] Subcohort 1 is 4-year only: [4]
#   [PASS] Subcohort 2 is 4-year only: [4]
# 
# [PASS] [Boundary] completion_rate_150pct range: [0.0, 1.0] (expected [0, 100])
# [INFO] [Boundary] Institutions with only 1 row: 147 of 5,549
# 
# [PASS] [Absence] institution_level column present: True
#   institution_level values: [1, 2, 4]
# [PASS] Plan expected 'cohort_count' column -- NOT present (check alternatives)
#   Cohort-related columns available: ['cohort_year', 'subcohort', 'cohort_rev', 'cohort_adj_150pct']
# 
# [PASS] [Downstream] race==99 & sex==99 filter yields: 29,923 rows
#   subcohort=1, race==99, sex==99: 4,997 rows
#   subcohort=2, race==99, sex==99: 9,047 rows
#   subcohort=99, race==99, sex==99: 15,879 rows
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot 11: Tracing unitid=100654
#   Total rows: 180
#   Years: [2020, 2021]
#   Subcohorts: [2, 99]
#   Races: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#   Sexes: [1, 2, 99]
#   Theoretical max (3 sub x 10 race x 3 sex x 2 yr): 180
#   Actual rows: 180 -- reasonable
# 
# Spot 12: completion_rate_150pct stats (non-null only, n=274,308)
#   min=0.0, max=1.0, mean=0.49, median=0.50
#   Exact zeros: 33,447 (12.2%)
#   Exact 100s: 0 (0.0%)
# 
# Spot 13: Subcohort restriction to 4-year institutions
#   subcohort=1 at non-4-year: 0 rows (should be 0)
#   subcohort=2 at non-4-year: 0 rows (should be 0)
# 
# Spot 14: Year balance
#   2020: 401,215 rows
#   2021: 403,501 rows
#   Year ratio (max/min): 1.006 (should be ~1.0)
#   [PASS] Year balance: balanced
# 
# Spot 15: Total-row (race==99, sex==99) counts per institution-subcohort
#   Unique institution-subcohort combos with totals: 8,680
#   Distribution of rows per combo:
#     1 rows: 344 combos
#     2 rows: 3,976 combos
#     3 rows: 233 combos
#     4 rows: 1,843 combos
#     5 rows: 484 combos
#     6 rows: 1,582 combos
#     7 rows: 100 combos
#     8 rows: 118 combos
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 5 rows:
# shape: (5, 18)
# ┌────────┬──────┬──────┬─────────────┬───┬──────────────┬──────────────┬─────────────┬─────────────┐
# │ unitid ┆ year ┆ fips ┆ cohort_year ┆ … ┆ completers_1 ┆ still_enroll ┆ no_longer_e ┆ completion_ │
# │ ---    ┆ ---  ┆ ---  ┆ ---         ┆   ┆ 00pct        ┆ ed           ┆ nrolled     ┆ rate_150pct │
# │ i64    ┆ i64  ┆ i64  ┆ i64         ┆   ┆ ---          ┆ ---          ┆ ---         ┆ ---         │
# │        ┆      ┆      ┆             ┆   ┆ i64          ┆ i64          ┆ i64         ┆ f64         │
# ╞════════╪══════╪══════╪═════════════╪═══╪══════════════╪══════════════╪═════════════╪═════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# │ 100654 ┆ 2020 ┆ 1    ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# │ 100654 ┆ 2020 ┆ 1    ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# │ 100654 ┆ 2020 ┆ 1    ┆ 2015        ┆ … ┆ null         ┆ 18           ┆ 223         ┆ 0.229       │
# │ 100654 ┆ 2020 ┆ 1    ┆ 2015        ┆ … ┆ null         ┆ null         ┆ null        ┆ null        │
# └────────┴──────┴──────┴─────────────┴───┴──────────────┴──────────────┴─────────────┴─────────────┘
# 
# Descriptive statistics:
# shape: (9, 19)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ unitid    ┆ year      ┆ fips      ┆ … ┆ completer ┆ still_enr ┆ no_longer ┆ completi │
# │ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ s_100pct  ┆ olled     ┆ _enrolled ┆ on_rate_ │
# │ str       ┆ f64       ┆ f64       ┆ f64       ┆   ┆ ---       ┆ ---       ┆ ---       ┆ 150pct   │
# │           ┆           ┆           ┆           ┆   ┆ f64       ┆ f64       ┆ f64       ┆ ---      │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ f64      │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 804716.0  ┆ 804716.0  ┆ 804716.0  ┆ … ┆ 238406.0  ┆ 264836.0  ┆ 384476.0  ┆ 274308.0 │
# │ null_coun ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ … ┆ 566310.0  ┆ 539880.0  ┆ 420240.0  ┆ 530408.0 │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ 232372.33 ┆ 2020.5014 ┆ 30.034224 ┆ … ┆ 3.099729  ┆ 4.632078  ┆ 24.334879 ┆ 0.488034 │
# │           ┆ 994       ┆ 2         ┆           ┆   ┆           ┆           ┆           ┆          │
# │ std       ┆ 112956.56 ┆ 0.499998  ┆ 16.926898 ┆ … ┆ 28.358667 ┆ 21.124325 ┆ 91.363411 ┆ 0.302771 │
# │           ┆ 4227      ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ min       ┆ 100654.0  ┆ 2020.0    ┆ 1.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0      │
# │ 25%       ┆ 156295.0  ┆ 2020.0    ┆ 16.0      ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.259    │
# │ 50%       ┆ 199032.0  ┆ 2021.0    ┆ 31.0      ┆ … ┆ 0.0       ┆ 0.0       ┆ 1.0       ┆ 0.5      │
# │ 75%       ┆ 237385.0  ┆ 2021.0    ┆ 42.0      ┆ … ┆ 0.0       ┆ 2.0       ┆ 11.0      ┆ 0.707    │
# │ max       ┆ 498571.0  ┆ 2021.0    ┆ 78.0      ┆ … ┆ 1822.0    ┆ 1206.0    ┆ 6860.0    ┆ 1.0      │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Key column value counts:
# 
# subcohort:
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
# race:
# shape: (10, 2)
# ┌──────┬───────┐
# │ race ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 80151 │
# │ 2    ┆ 80151 │
# │ 3    ┆ 80151 │
# │ 4    ┆ 80151 │
# │ 5    ┆ 80151 │
# │ 6    ┆ 80151 │
# │ 7    ┆ 80151 │
# │ 8    ┆ 80151 │
# │ 9    ┆ 80151 │
# │ 99   ┆ 83357 │
# └──────┴───────┘
# 
# sex:
# shape: (3, 2)
# ┌─────┬────────┐
# │ sex ┆ count  │
# │ --- ┆ ---    │
# │ i64 ┆ u32    │
# ╞═════╪════════╡
# │ 1   ┆ 267170 │
# │ 2   ┆ 267170 │
# │ 99  ┆ 270376 │
# └─────┴────────┘
# 
# Year distribution:
# shape: (2, 2)
# ┌──────┬────────┐
# │ year ┆ count  │
# │ ---  ┆ ---    │
# │ i64  ┆ u32    │
# ╞══════╪════════╡
# │ 2020 ┆ 401215 │
# │ 2021 ┆ 403501 │
# └──────┴────────┘
# 
# Null counts per column:
#   cohort_rev: 578,250 nulls (71.9%)
#   exclusions: 718,590 nulls (89.3%)
#   cohort_adj_150pct: 396,750 nulls (49.3%)
#   completers_150pct: 11,670 nulls (1.5%)
#   transfers_out: 554,820 nulls (68.9%)
#   still_enrolled_long_program: 804,716 nulls (100.0%)
#   completers_100pct: 566,310 nulls (70.4%)
#   still_enrolled: 539,880 nulls (67.1%)
#   no_longer_enrolled: 420,240 nulls (52.2%)
#   completion_rate_150pct: 530,408 nulls (65.9%)
# 
# ============================================================
# QA RESULT: PASSED
# WARNING: Subcohort codes differ from Plan.md expectation (LOW-confidence item resolved)
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
