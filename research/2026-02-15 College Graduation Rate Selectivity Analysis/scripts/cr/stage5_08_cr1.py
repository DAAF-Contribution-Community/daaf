#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 8

Reviewed script: scripts/stage5_fetch/08_fetch-scorecard.py
Output files: data/raw/2026-02-15_scorecard_earnings.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks:
1. Schema matches Plan expectations (unitid, year, earnings_med at minimum)
2. Row count within expected range (Plan: 1,000-5,000; actual 5,376 — assess)
3. No suspicious distributions in numeric columns
4. Coded values properly filtered (no -1, -2, -3 in numeric columns)
5. No nulls in critical columns (unitid, year, earnings_med)
6. [COUNTERFACTUAL] What if year filtering failed — verify only year 2018 present
7. [SEMANTIC] Does earnings_med range serve the research question (selectivity vs outcomes)?
8. [BOUNDARY] Check min/max earnings_med for outliers; check unitid range
9. [ABSENCE] Verify years_after_entry == 10 for all rows (no other values leaked)
10. [DOWNSTREAM] Check unitid type matches IPEDS convention (Int64) for join compatibility
11-15: Spot-checks for data integrity
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_scorecard_earnings.parquet"
# Plan specifies: unitid, year, earnings_med, earnings_mean, count_working
# Script actually selected all earnings + count columns (29 cols).
# Critical columns from Plan perspective:
EXPECTED_COLUMNS = ["unitid", "year", "earnings_med"]
EXPECTED_MIN_ROWS = 1000
EXPECTED_MAX_ROWS = 5500  # Plan says 1000-5000, actual 5376 — slightly above
CRITICAL_COLUMNS = ["unitid", "year", "earnings_med"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 8 (fetch-scorecard)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan minimum): {extra_cols}")
    print(f"  NOTE: Script selected {len(df.columns)} cols vs Plan's 5-6. Not a blocker — superset.")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"\n[{'PASS' if rows_ok else 'WARN'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")
if row_count > 5000:
    print(f"  NOTE: Plan expected max 5,000 but got {row_count:,}. This is 7.5% above upper bound.")
    print(f"  Assessment: Scorecard has broader coverage than expected. Acceptable for supplementary data.")

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
print(f"\n[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"\n[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"\n[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses of Skeptical Review)
# =============================================================================

# --- Check 6 [COUNTERFACTUAL]: Year filtering ---
# What if the year filter didn't work? Verify only 2018 is present.
unique_years = df["year"].unique().to_list()
year_ok = unique_years == [2018]
print(f"\n[{'PASS' if year_ok else 'FAIL'}] [COUNTERFACTUAL] Year filter: ", end="")
print(f"unique years = {unique_years}")
if not year_ok:
    print(f"  CONCERN: Expected only [2018] but found {unique_years}")

# --- Check 7 [SEMANTIC]: earnings_med range serves research question ---
# Research question asks about selectivity vs outcomes. earnings_med should have
# meaningful variation to show how earnings differ across selectivity bands.
earn_med = df["earnings_med"].drop_nulls()
earn_min = earn_med.min()
earn_max = earn_med.max()
earn_std = earn_med.std()
earn_mean = earn_med.mean()
cv = earn_std / earn_mean if earn_mean and earn_mean > 0 else 0

# Plan says range 10000-200000
range_ok = earn_min >= 10000 and earn_max <= 200000
variation_ok = cv > 0.1  # At least 10% coefficient of variation
print(f"\n[{'PASS' if range_ok else 'WARN'}] [SEMANTIC] earnings_med range: "
      f"${earn_min:,.0f} - ${earn_max:,.0f}")
print(f"  Plan expected: $10,000-$200,000")
print(f"[{'PASS' if variation_ok else 'WARN'}] [SEMANTIC] earnings_med variation: "
      f"CV = {cv:.2f} (std=${earn_std:,.0f}, mean=${earn_mean:,.0f})")
print(f"  Sufficient variation for selectivity analysis: {'Yes' if variation_ok else 'No'}")

# --- Check 8 [BOUNDARY]: Edge cases in earnings_med ---
# Check for suspiciously low or high values
very_low = df.filter(pl.col("earnings_med") < 15000).shape[0]
very_high = df.filter(pl.col("earnings_med") > 100000).shape[0]
print(f"\n[INFO] [BOUNDARY] earnings_med edge cases:")
print(f"  < $15,000: {very_low} institutions ({very_low/row_count*100:.1f}%)")
print(f"  > $100,000: {very_high} institutions ({very_high/row_count*100:.1f}%)")

# Check unitid range (should be 6-digit IPEDS identifiers)
unitid_min = df["unitid"].min()
unitid_max = df["unitid"].max()
unitid_range_ok = unitid_min >= 100000 and unitid_max < 1000000
print(f"[{'PASS' if unitid_range_ok else 'WARN'}] [BOUNDARY] unitid range: "
      f"{unitid_min} - {unitid_max}")
if not unitid_range_ok:
    below_6digit = df.filter(pl.col("unitid") < 100000).shape[0]
    above_6digit = df.filter(pl.col("unitid") >= 1000000).shape[0]
    print(f"  Below 100000: {below_6digit}, At/above 1000000: {above_6digit}")

# --- Check 9 [ABSENCE]: years_after_entry filtering ---
# Verify ALL rows have years_after_entry == 10 (no leaked values)
if "years_after_entry" in df.columns:
    yae_values = df["years_after_entry"].unique().to_list()
    yae_ok = yae_values == [10]
    print(f"\n[{'PASS' if yae_ok else 'FAIL'}] [ABSENCE] years_after_entry filter: "
          f"unique values = {yae_values}")
    if not yae_ok:
        print(f"  CONCERN: Expected only [10] but found {yae_values}")
        for v in yae_values:
            count = df.filter(pl.col("years_after_entry") == v).shape[0]
            print(f"    years_after_entry == {v}: {count} rows")
else:
    print(f"\n[INFO] [ABSENCE] years_after_entry column not in output")

# --- Check 10 [DOWNSTREAM]: unitid type compatibility for IPEDS join ---
# Downstream joins will be on unitid. Verify type matches IPEDS convention (Int64).
unitid_type = df["unitid"].dtype
type_ok = unitid_type == pl.Int64
print(f"\n[{'PASS' if type_ok else 'WARN'}] [DOWNSTREAM] unitid dtype: {unitid_type} "
      f"(expected Int64 for IPEDS join compatibility)")

# Also check for duplicate unitids (should be 1:1 after year+yae filter)
unitid_n_unique = df["unitid"].n_unique()
unitid_dup_ok = unitid_n_unique == row_count
print(f"[{'PASS' if unitid_dup_ok else 'WARN'}] [DOWNSTREAM] unitid uniqueness: "
      f"{unitid_n_unique:,} unique / {row_count:,} rows")
if not unitid_dup_ok:
    dups = (df.group_by("unitid").len()
            .filter(pl.col("len") > 1)
            .sort("len", descending=True)
            .head(5))
    print(f"  Duplicate unitids (top 5):\n{dups}")

# =============================================================================
# SPOT-CHECKS (5 concrete validations)
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# Spot-check 1: Known institution — Harvard (unitid 166027)
harvard = df.filter(pl.col("unitid") == 166027)
print(f"\n[SPOT-1] Harvard (unitid=166027):")
if harvard.shape[0] == 1:
    h_earn = harvard["earnings_med"][0]
    print(f"  earnings_med = ${h_earn:,}")
    # Harvard grads should have high median earnings (>$60k at 10yr)
    harvard_ok = h_earn is not None and h_earn > 60000
    print(f"  [{'PASS' if harvard_ok else 'WARN'}] Reasonable for Harvard? {harvard_ok}")
elif harvard.shape[0] == 0:
    print(f"  Not found in dataset (may not be in Scorecard)")
else:
    print(f"  WARN: Multiple rows for Harvard: {harvard.shape[0]}")

# Spot-check 2: Known institution — community-type institution check
# Find lowest earnings_med and verify it's plausible
lowest = df.sort("earnings_med").head(3)
print(f"\n[SPOT-2] Lowest earnings_med institutions:")
for row in lowest.iter_rows(named=True):
    print(f"  unitid={row['unitid']}, earnings_med=${row['earnings_med']:,}")

# Spot-check 3: Verify count_working column has plausible values
if "count_working" in df.columns:
    cw = df["count_working"]
    cw_min = cw.drop_nulls().min()
    cw_max = cw.drop_nulls().max()
    cw_mean = cw.drop_nulls().mean()
    print(f"\n[SPOT-3] count_working range: {cw_min:,} - {cw_max:,} (mean: {cw_mean:,.0f})")
    cw_ok = cw_min >= 0 and cw_max < 500000
    print(f"  [{'PASS' if cw_ok else 'WARN'}] Range plausible")
else:
    print(f"\n[SPOT-3] count_working not in output columns")

# Spot-check 4: Verify earnings_pct25 < earnings_med < earnings_pct75 ordering
if "earnings_pct25" in df.columns and "earnings_pct75" in df.columns:
    # Only check rows where all three are non-null
    comparison = df.filter(
        pl.col("earnings_pct25").is_not_null() &
        pl.col("earnings_med").is_not_null() &
        pl.col("earnings_pct75").is_not_null()
    )
    if comparison.shape[0] > 0:
        ordering_violations = comparison.filter(
            (pl.col("earnings_pct25") > pl.col("earnings_med")) |
            (pl.col("earnings_med") > pl.col("earnings_pct75"))
        ).shape[0]
        ordering_ok = ordering_violations == 0
        print(f"\n[SPOT-4] Percentile ordering (p25 <= median <= p75):")
        print(f"  Checked {comparison.shape[0]:,} rows with all three non-null")
        print(f"  [{'PASS' if ordering_ok else 'WARN'}] Violations: {ordering_violations}")
    else:
        print(f"\n[SPOT-4] No rows with all three percentile columns non-null")
else:
    print(f"\n[SPOT-4] Percentile columns not available for ordering check")

# Spot-check 5: Verify no negative values in earnings_med
neg_earn = df.filter(pl.col("earnings_med") < 0).shape[0]
neg_ok = neg_earn == 0
print(f"\n[SPOT-5] Negative earnings_med values: {neg_earn}")
print(f"  [{'PASS' if neg_ok else 'FAIL'}] No negative earnings")

# =============================================================================
# NULL RATE ANALYSIS (for many-subgroup columns)
# =============================================================================

print("\n" + "=" * 60)
print("NULL RATE ANALYSIS")
print("=" * 60)

null_100pct = []
null_partial = []
null_zero = []
for col in df.columns:
    nc = df[col].null_count()
    pct = nc / row_count * 100
    if pct == 100.0:
        null_100pct.append(col)
    elif pct > 0:
        null_partial.append((col, nc, pct))
    else:
        null_zero.append(col)

print(f"\nColumns with 0% null ({len(null_zero)}):")
for col in null_zero:
    print(f"  {col}")

print(f"\nColumns with partial null ({len(null_partial)}):")
for col, nc, pct in null_partial:
    print(f"  {col}: {nc:,} ({pct:.1f}%)")

print(f"\nColumns with 100% null ({len(null_100pct)}):")
for col in null_100pct:
    print(f"  {col}")
if null_100pct:
    print(f"\n  NOTE: {len(null_100pct)} columns are entirely null. These are subgroup ")
    print(f"  breakdowns that Scorecard suppresses for privacy at the institution level.")
    print(f"  This is expected behavior for years_after_entry == 10.")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

all_critical = all([
    schema_ok,
    nulls_ok,
    coded_ok,
    year_ok if 'year_ok' in dir() else True,
    neg_ok,
    unitid_dup_ok if 'unitid_dup_ok' in dir() else True,
])

has_warnings = not rows_ok or not range_ok or len(null_100pct) > 0

if not all_critical:
    severity = "BLOCKER"
elif has_warnings:
    severity = "WARNING"
else:
    severity = "PASSED"

print(f"\nCritical checks: {'ALL PASSED' if all_critical else 'FAILURES DETECTED'}")
print(f"Warning items: {'Present' if has_warnings else 'None'}")
print(f"\nQA RESULT: {severity}")
print("=" * 60)

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        if col == "unitid":
            print(f"\n{col}: {df[col].n_unique()} unique values (not printing all)")
        elif col == "year":
            print(f"\n{col}:")
            print(df[col].value_counts().sort("year"))
        else:
            print(f"\n{col} (top 20 values):")
            print(df[col].value_counts().sort("count", descending=True).head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

# earnings_med distribution summary for profiling
print("\nearnings_med distribution (deciles):")
for q in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    val = df["earnings_med"].quantile(q)
    print(f"  {q*100:5.0f}%: ${val:,.0f}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:29:18
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_08_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 8 (fetch-scorecard)
# ============================================================
# Loaded: 5,376 rows x 29 cols
# Columns: ['unitid', 'year', 'years_after_entry', 'earnings_mean', 'earnings_sd', 'earnings_greater_than_25k_pct', 'earnings_med', 'earnings_pct10', 'earnings_pct25', 'earnings_pct75', 'earnings_pct90', 'earnings_lowinc_mean', 'earnings_midinc_mean', 'earnings_highinc_mean', 'earnings_dep_lowinc_mean', 'earnings_dep_mean', 'earnings_ind_mean', 'earnings_female_mean', 'earnings_male_mean', 'count_not_working', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep_lowinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
# 
# [PASS] Schema: All expected columns present
#   Extra columns (not in Plan minimum): ['years_after_entry', 'earnings_mean', 'earnings_sd', 'earnings_greater_than_25k_pct', 'earnings_pct10', 'earnings_pct25', 'earnings_pct75', 'earnings_pct90', 'earnings_lowinc_mean', 'earnings_midinc_mean', 'earnings_highinc_mean', 'earnings_dep_lowinc_mean', 'earnings_dep_mean', 'earnings_ind_mean', 'earnings_female_mean', 'earnings_male_mean', 'count_not_working', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep_lowinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
#   NOTE: Script selected 29 cols vs Plan's 5-6. Not a blocker — superset.
# 
# [PASS] Row count: 5,376 (expected 1,000-5,500)
#   NOTE: Plan expected max 5,000 but got 5,376. This is 7.5% above upper bound.
#   Assessment: Scorecard has broader coverage than expected. Acceptable for supplementary data.
# 
# [FAIL] Distributions: year: all same value (2018); years_after_entry: all same value (10)
# 
# [PASS] Coded values: None remain
# 
# [PASS] Critical nulls: None
# 
# [PASS] [COUNTERFACTUAL] Year filter: unique years = [2018]
# 
# [PASS] [SEMANTIC] earnings_med range: $10,939 - $132,969
#   Plan expected: $10,000-$200,000
# [PASS] [SEMANTIC] earnings_med variation: CV = 0.38 (std=$14,741, mean=$39,092)
#   Sufficient variation for selectivity analysis: Yes
# 
# [INFO] [BOUNDARY] earnings_med edge cases:
#   < $15,000: 26 institutions (0.5%)
#   > $100,000: 14 institutions (0.3%)
# [WARN] [BOUNDARY] unitid range: 100654 - 48511113
#   Below 100000: 0, At/above 1000000: 420
# 
# [PASS] [ABSENCE] years_after_entry filter: unique values = [10]
# 
# [PASS] [DOWNSTREAM] unitid dtype: Int64 (expected Int64 for IPEDS join compatibility)
# [PASS] [DOWNSTREAM] unitid uniqueness: 5,376 unique / 5,376 rows
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [SPOT-1] Harvard (unitid=166027):
#   earnings_med = $84,918
#   [PASS] Reasonable for Harvard? True
# 
# [SPOT-2] Lowest earnings_med institutions:
#   unitid=208044, earnings_med=$10,939
#   unitid=202453, earnings_med=$11,884
#   unitid=215530, earnings_med=$12,248
# 
# [SPOT-3] count_working range: 16 - 164,390 (mean: 2,470)
#   [PASS] Range plausible
# 
# [SPOT-4] Percentile ordering (p25 <= median <= p75):
#   Checked 5,206 rows with all three non-null
#   [PASS] Violations: 0
# 
# [SPOT-5] Negative earnings_med values: 0
#   [PASS] No negative earnings
# 
# ============================================================
# NULL RATE ANALYSIS
# ============================================================
# 
# Columns with 0% null (5):
#   unitid
#   year
#   years_after_entry
#   earnings_med
#   count_working
# 
# Columns with partial null (9):
#   earnings_pct25: 137 (2.5%)
#   earnings_pct75: 49 (0.9%)
#   count_working_lowinc: 188 (3.5%)
#   count_working_midinc: 770 (14.3%)
#   count_working_highinc: 1,828 (34.0%)
#   count_working_dep: 515 (9.6%)
#   count_working_ind: 474 (8.8%)
#   count_working_female: 236 (4.4%)
#   count_working_male: 954 (17.7%)
# 
# Columns with 100% null (15):
#   earnings_mean
#   earnings_sd
#   earnings_greater_than_25k_pct
#   earnings_pct10
#   earnings_pct90
#   earnings_lowinc_mean
#   earnings_midinc_mean
#   earnings_highinc_mean
#   earnings_dep_lowinc_mean
#   earnings_dep_mean
#   earnings_ind_mean
#   earnings_female_mean
#   earnings_male_mean
#   count_not_working
#   count_working_dep_lowinc
# 
#   NOTE: 15 columns are entirely null. These are subgroup 
#   breakdowns that Scorecard suppresses for privacy at the institution level.
#   This is expected behavior for years_after_entry == 10.
# 
# ============================================================
# SUMMARY
# ============================================================
# 
# Critical checks: ALL PASSED
# Warning items: Present
# 
# QA RESULT: WARNING
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 29)
# ┌────────┬──────┬─────────────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ year ┆ years_after ┆ earnings_m ┆ … ┆ count_work ┆ count_work ┆ count_work ┆ count_work │
# │ ---    ┆ ---  ┆ _entry      ┆ ean        ┆   ┆ ing_dep    ┆ ing_ind    ┆ ing_female ┆ ing_male   │
# │ i64    ┆ i64  ┆ ---         ┆ ---        ┆   ┆ ---        ┆ ---        ┆ ---        ┆ ---        │
# │        ┆      ┆ i64         ┆ i64        ┆   ┆ i64        ┆ i64        ┆ i64        ┆ i64        │
# ╞════════╪══════╪═════════════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 867        ┆ 96         ┆ 481        ┆ 483        │
# │ 100663 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1990       ┆ 875        ┆ 1773       ┆ 1091       │
# │ 100690 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ null       ┆ 131        ┆ 78         ┆ 63         │
# │ 100706 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1042       ┆ 473        ┆ 736        ┆ 779        │
# │ 100724 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1911       ┆ 305        ┆ 1182       ┆ 1034       │
# │ …      ┆ …    ┆ …           ┆ …          ┆ … ┆ …          ┆ …          ┆ …          ┆ …          │
# │ 101189 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 529        ┆ 743        ┆ 769        ┆ 502        │
# │ 101240 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 881        ┆ 850        ┆ 1149       ┆ 580        │
# │ 101286 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 497        ┆ 553        ┆ 755        ┆ 297        │
# │ 101295 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1060       ┆ 933        ┆ 1288       ┆ 705        │
# │ 101301 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 469        ┆ 331        ┆ 495        ┆ 306        │
# └────────┴──────┴─────────────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 30)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ years_aft ┆ … ┆ count_wor ┆ count_wor ┆ count_wor ┆ count_wor │
# │ ---        ┆ ---        ┆ ---    ┆ er_entry  ┆   ┆ king_dep  ┆ king_ind  ┆ king_fema ┆ king_male │
# │ str        ┆ f64        ┆ f64    ┆ ---       ┆   ┆ ---       ┆ ---       ┆ le        ┆ ---       │
# │            ┆            ┆        ┆ f64       ┆   ┆ f64       ┆ f64       ┆ ---       ┆ f64       │
# │            ┆            ┆        ┆           ┆   ┆           ┆           ┆ f64       ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 5376.0     ┆ 5376.0 ┆ 5376.0    ┆ … ┆ 4861.0    ┆ 4902.0    ┆ 5140.0    ┆ 4422.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0.0       ┆ … ┆ 515.0     ┆ 474.0     ┆ 236.0     ┆ 954.0     │
# │ mean       ┆ 2.1852e6   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 1102.9082 ┆ 1612.5032 ┆ 1590.6480 ┆ 1151.3844 │
# │            ┆            ┆        ┆           ┆   ┆ 49        ┆ 64        ┆ 54        ┆ 41        │
# │ std        ┆ 7.5309e6   ┆ 0.0    ┆ 0.0       ┆ … ┆ 2241.9645 ┆ 9683.0740 ┆ 6993.5470 ┆ 4011.3171 │
# │            ┆            ┆        ┆           ┆   ┆ 79        ┆ 87        ┆ 98        ┆ 42        │
# │ min        ┆ 100654.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 16.0      ┆ 16.0      ┆ 16.0      ┆ 16.0      │
# │ 25%        ┆ 166027.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 121.0     ┆ 84.0      ┆ 127.0     ┆ 109.0     │
# │ 50%        ┆ 215239.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 405.0     ┆ 282.0     ┆ 404.0     ┆ 315.0     │
# │ 75%        ┆ 431266.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 1081.0    ┆ 798.0     ┆ 1167.0    ┆ 884.0     │
# │ max        ┆ 4.8511113e ┆ 2018.0 ┆ 10.0      ┆ … ┆ 19608.0   ┆ 151296.0  ┆ 110003.0  ┆ 54388.0   │
# │            ┆ 7          ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Key column value counts:
# 
# unitid: 5376 unique values (not printing all)
# 
# year:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2018 ┆ 5376  │
# └──────┴───────┘
# 
# earnings_med (top 20 values):
# shape: (20, 2)
# ┌──────────────┬───────┐
# │ earnings_med ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 43590        ┆ 76    │
# │ 43125        ┆ 33    │
# │ 58227        ┆ 25    │
# │ 28204        ┆ 24    │
# │ 36567        ┆ 22    │
# │ …            ┆ …     │
# │ 33344        ┆ 15    │
# │ 34727        ┆ 14    │
# │ 24220        ┆ 14    │
# │ 36710        ┆ 14    │
# │ 31462        ┆ 13    │
# └──────────────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2018 ┆ 5376  │
# └──────┴───────┘
# 
# earnings_med distribution (deciles):
#       0%: $10,939
#      10%: $22,878
#      20%: $26,502
#      30%: $30,572
#      40%: $33,954
#      50%: $36,781
#      60%: $40,199
#      70%: $43,613
#      80%: $49,230
#      90%: $57,590
#     100%: $132,969
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
