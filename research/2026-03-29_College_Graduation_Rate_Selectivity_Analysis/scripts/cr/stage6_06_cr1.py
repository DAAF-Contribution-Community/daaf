#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 06

Reviewed script: scripts/stage6_clean/06_clean-sfr.py
Output files: data/processed/2026-03-29_sfr_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range (3,000-6,000)
3. No suspicious distributions
4. Coded values properly filtered (-1, -2, -3)
5. No nulls in critical columns (unitid, student_faculty_ratio)

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if raw data had multiple years? Year filter absence check
7. [Semantic] Does output serve downstream join-resources correctly?
8. [Boundary] SFR boundary values: min=1 edge, max outlier at 110
9. [Absence] Was year/fips column drop intentional and safe?
10. [Downstream] Would join-resources (Stage 7 Step 6.1) be surprised by anything?

Spot-Checks:
11. Trace outlier unitid=246035 (SFR=110) through output
12. Verify SFR distribution is plausible for US 4-year institutions
13. Verify raw->clean row difference matches execution log (1 row removed)
14. Check that no SFR values are exactly 0 (should have been filtered)
15. Cross-reference: clean unitid count vs raw unitid count
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

RAW_FILE = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_sfr.parquet"
CLEAN_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfr_clean.parquet"

EXPECTED_COLUMNS = ["unitid", "student_faculty_ratio"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 6000
CRITICAL_COLUMNS = ["unitid", "student_faculty_ratio"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output and raw data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 06 — clean-sfr")
print("=" * 60)

df = pl.read_parquet(CLEAN_FILE)
print(f"Clean file loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

raw_df = pl.read_parquet(RAW_FILE)
print(f"Raw file loaded: {raw_df.shape[0]:,} rows x {raw_df.shape[1]} cols")
print(f"Raw columns: {raw_df.columns}")

# === DEFAULT CHECKS ===

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

# --- Check 4: Coded values ---
coded_issues = []
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
if coded_ok:
    print("None remain in any numeric column")
else:
    print("; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# === SCRIPT-SPECIFIC CHECKS (Five Lenses) ===

# --- Check 6: [Counterfactual] Multiple years in raw data? ---
# INTENT: If the raw data has multiple years, the clean script MUST filter to a
# single year or else unitid won't be unique. The script does NOT filter by year --
# it only drops the column. This is safe IF the raw data already has one year.
print("\n--- Script-Specific Checks ---")

raw_years = raw_df["year"].unique().sort().to_list()
print(f"\n[COUNTERFACTUAL] Raw data years present: {raw_years}")
single_year = len(raw_years) == 1
if single_year:
    print(f"[PASS] Raw data already single-year ({raw_years[0]}), safe to drop year column")
else:
    print(f"[FAIL] Raw data has MULTIPLE years: {raw_years}. Script drops year without filtering!")
    print("  This would cause duplicate unitids in the clean output.")

# --- Check 7: [Semantic] Does output serve downstream join-resources? ---
# INTENT: Stage 7 join-resources expects unitid + student_faculty_ratio with
# 1:1 cardinality. Verify the output is ready for that join.
unitid_unique_clean = df["unitid"].n_unique() == df.shape[0]
sfr_dtype_ok = df["student_faculty_ratio"].dtype == pl.Float64
print(f"\n[SEMANTIC] Output serves join-resources (Stage 7 Step 6.1)?")
print(f"  unitid is unique: {unitid_unique_clean} ({df['unitid'].n_unique()} unique vs {df.shape[0]} rows)")
print(f"  SFR dtype is Float64: {sfr_dtype_ok} (actual: {df['student_faculty_ratio'].dtype})")
semantic_ok = unitid_unique_clean and sfr_dtype_ok
print(f"[{'PASS' if semantic_ok else 'FAIL'}] Semantic: Output ready for downstream 1:1 join")

# --- Check 8: [Boundary] SFR boundary values ---
# INTENT: Check edge values. SFR=1 is the minimum allowed; SFR=110 is the known
# outlier. Verify boundaries are correct and no fractional values exist (source is Int64).
sfr_min = df["student_faculty_ratio"].min()
sfr_max = df["student_faculty_ratio"].max()
sfr_below_1 = df.filter(pl.col("student_faculty_ratio") < 1).shape[0]
sfr_equal_1 = df.filter(pl.col("student_faculty_ratio") == 1).shape[0]
# REASONING: Source is Int64, so after Float64 cast all values should be whole numbers.
# If any fractional values exist, something unexpected happened.
fractional = df.filter(
    (pl.col("student_faculty_ratio") % 1 != 0)
    & pl.col("student_faculty_ratio").is_not_null()
).shape[0]
print(f"\n[BOUNDARY] SFR value boundaries:")
print(f"  Min value: {sfr_min} (expected >= 1)")
print(f"  Max value: {sfr_max} (known outlier at 110)")
print(f"  Rows with SFR < 1: {sfr_below_1}")
print(f"  Rows with SFR == 1: {sfr_equal_1}")
print(f"  Fractional values (unexpected from Int64 source): {fractional}")
boundary_ok = sfr_below_1 == 0 and sfr_min >= 1 and fractional == 0
print(f"[{'PASS' if boundary_ok else 'FAIL'}] Boundary: All SFR values are whole numbers >= 1")

# --- Check 9: [Absence] Year/fips columns dropped -- is this safe? ---
# INTENT: The script drops year and fips. Check that no downstream consumer would
# need these. Plan.md analysis dataset needs unitid+student_faculty_ratio only.
# Also verify that dropping year didn't silently hide a multi-year issue.
raw_has_year = "year" in raw_df.columns
raw_has_fips = "fips" in raw_df.columns
clean_has_year = "year" in df.columns
clean_has_fips = "fips" in df.columns
print(f"\n[ABSENCE] Column drop analysis:")
print(f"  Raw had 'year': {raw_has_year}, Clean has 'year': {clean_has_year}")
print(f"  Raw had 'fips': {raw_has_fips}, Clean has 'fips': {clean_has_fips}")
# REASONING: Plan.md Stage 6->7 interface specifies 'unitid + cleaned/computed variables'.
# SFR clean only needs unitid + student_faculty_ratio. Year is not needed for the join
# since the raw data is single-year. Fips is available from the directory dataset.
absence_ok = not clean_has_year and not clean_has_fips and single_year
print(f"[{'PASS' if absence_ok else 'WARN'}] Absence: Column drops are safe (year was single-valued, fips from directory)")

# --- Check 10: [Downstream] Surprises for join-resources? ---
# INTENT: Check if the output might surprise the next consumer. Look for:
# (a) unexpectedly low coverage vs directory, (b) SFR distribution anomalies,
# (c) unitid type mismatches.
unitid_dtype = df["unitid"].dtype
sfr_p10 = df["student_faculty_ratio"].quantile(0.10)
sfr_p90 = df["student_faculty_ratio"].quantile(0.90)
sfr_iqr = df["student_faculty_ratio"].quantile(0.75) - df["student_faculty_ratio"].quantile(0.25)
print(f"\n[DOWNSTREAM] Potential surprises for join-resources:")
print(f"  unitid dtype: {unitid_dtype} (should be Int64 for join compatibility)")
print(f"  SFR 10th percentile: {sfr_p10}")
print(f"  SFR 90th percentile: {sfr_p90}")
print(f"  SFR IQR: {sfr_iqr}")
print(f"  Total institutions: {df.shape[0]:,}")
# Plan expects ~4,000 rows for SFR (Query 6). We have 5,835 which is above that
# but within the 3,000-6,000 range. This is fine -- raw data may include more
# institutions than the 4-yr degree-granting target.
downstream_ok = unitid_dtype == pl.Int64
print(f"[{'PASS' if downstream_ok else 'FAIL'}] Downstream: unitid type compatible for joins")

# === SPOT-CHECKS ===

# --- Spot-Check 11: Trace outlier unitid=246035 ---
print("\n--- Spot-Checks ---")
outlier_raw = raw_df.filter(pl.col("unitid") == 246035)
outlier_clean = df.filter(pl.col("unitid") == 246035)
print(f"\n[SPOT] Outlier unitid=246035:")
print(f"  In raw:   {outlier_raw.shape[0]} rows, SFR={outlier_raw['student_faculty_ratio'].to_list()}")
print(f"  In clean: {outlier_clean.shape[0]} rows, SFR={outlier_clean['student_faculty_ratio'].to_list()}")
outlier_ok = outlier_clean.shape[0] == 1 and outlier_clean["student_faculty_ratio"][0] == 110.0
print(f"[{'PASS' if outlier_ok else 'FAIL'}] Outlier preserved correctly (SFR=110.0, flagged but retained)")

# --- Spot-Check 12: SFR distribution plausibility ---
# REASONING: US 4-year institutions typically have SFR between 8 and 25.
# Median around 14-16 is expected. Values < 5 or > 40 are unusual but possible.
sfr_median = df["student_faculty_ratio"].median()
sfr_mean = df["student_faculty_ratio"].mean()
pct_unusual_high = df.filter(pl.col("student_faculty_ratio") > 40).shape[0] / df.shape[0] * 100
pct_unusual_low = df.filter(pl.col("student_faculty_ratio") < 5).shape[0] / df.shape[0] * 100
print(f"\n[SPOT] SFR distribution plausibility:")
print(f"  Median: {sfr_median} (expected ~14-16)")
print(f"  Mean: {sfr_mean:.1f} (expected ~14-16)")
print(f"  % with SFR > 40: {pct_unusual_high:.1f}%")
print(f"  % with SFR < 5: {pct_unusual_low:.1f}%")
plausible = 10 <= sfr_median <= 20 and pct_unusual_high < 5 and pct_unusual_low < 10
print(f"[{'PASS' if plausible else 'WARN'}] SFR distribution plausible for US 4-year institutions")

# --- Spot-Check 13: Row difference matches execution log ---
raw_rows = raw_df.shape[0]
clean_rows = df.shape[0]
diff = raw_rows - clean_rows
print(f"\n[SPOT] Row difference: {raw_rows} raw - {clean_rows} clean = {diff} removed")
print(f"  Execution log claimed: 1 row removed (the null SFR row)")
diff_ok = diff == 1
print(f"[{'PASS' if diff_ok else 'FAIL'}] Row difference matches execution log")

# --- Spot-Check 14: No zero SFR values ---
zero_sfr = df.filter(pl.col("student_faculty_ratio") == 0).shape[0]
print(f"\n[SPOT] Zero SFR values in clean: {zero_sfr}")
print(f"[{'PASS' if zero_sfr == 0 else 'FAIL'}] No zero SFR values (filter working correctly)")

# --- Spot-Check 15: Clean unitid count vs raw unitid count ---
raw_unitid_unique = raw_df["unitid"].n_unique()
clean_unitid_unique = df["unitid"].n_unique()
print(f"\n[SPOT] Unitid counts: raw unique={raw_unitid_unique:,}, clean unique={clean_unitid_unique:,}")
print(f"  Difference: {raw_unitid_unique - clean_unitid_unique} (should = rows removed = {diff})")
unitid_diff_ok = (raw_unitid_unique - clean_unitid_unique) == diff
print(f"[{'PASS' if unitid_diff_ok else 'FAIL'}] Unitid difference matches row removal count")

# === SUMMARY ===

all_default = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific = all([single_year, semantic_ok, boundary_ok, absence_ok, downstream_ok])
all_spot = all([outlier_ok, plausible, diff_ok, zero_sfr == 0, unitid_diff_ok])
all_passed = all_default and all_specific and all_spot

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Default checks:        {'PASSED' if all_default else 'ISSUES'}")
print(f"  Script-specific checks: {'PASSED' if all_specific else 'ISSUES'}")
print(f"  Spot-checks:           {'PASSED' if all_spot else 'ISSUES'}")
severity = "PASSED" if all_passed else "BLOCKER"
print(f"\n  QA RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nSFR value counts (top 20 most common values):")
print(df["student_faculty_ratio"].value_counts().sort("count", descending=True).head(20))

print("\nSFR histogram (decile bins):")
for q in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    val = df["student_faculty_ratio"].quantile(q)
    print(f"  {q*100:5.0f}th percentile: {val}")

print(f"\nRaw data year distribution (for context):")
print(raw_df["year"].value_counts().sort("year"))

print(f"\nRaw data: rows with null SFR = {raw_df['student_faculty_ratio'].null_count()}")
print(f"Raw data: rows with SFR == 0  = {raw_df.filter(pl.col('student_faculty_ratio') == 0).shape[0]}")
print(f"Raw data: rows with coded values = ", end="")
coded_in_raw = 0
for code in CODED_MISSING_VALUES:
    c = raw_df.filter(pl.col("student_faculty_ratio") == code).shape[0]
    coded_in_raw += c
    if c > 0:
        print(f"[{code}]={c} ", end="")
if coded_in_raw == 0:
    print("None")
else:
    print(f"(total: {coded_in_raw})")

# Check the removed row
print(f"\nRemoved row(s) (in raw but not in clean):")
clean_unitids = set(df["unitid"].to_list())
raw_unitids = set(raw_df["unitid"].to_list())
removed_unitids = raw_unitids - clean_unitids
if removed_unitids:
    removed_rows = raw_df.filter(pl.col("unitid").is_in(list(removed_unitids)))
    print(removed_rows)
else:
    print("  None (unexpected -- execution log said 1 was removed)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:58:40
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_06_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 06 — clean-sfr
# ============================================================
# Clean file loaded: 5,835 rows x 2 cols
# Raw file loaded: 5,836 rows x 4 cols
# Raw columns: ['unitid', 'year', 'fips', 'student_faculty_ratio']
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,835 (expected 3,000-6,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in any numeric column
# [PASS] Critical nulls: None
# 
# --- Script-Specific Checks ---
# 
# [COUNTERFACTUAL] Raw data years present: [2020]
# [PASS] Raw data already single-year (2020), safe to drop year column
# 
# [SEMANTIC] Output serves join-resources (Stage 7 Step 6.1)?
#   unitid is unique: True (5835 unique vs 5835 rows)
#   SFR dtype is Float64: True (actual: Float64)
# [PASS] Semantic: Output ready for downstream 1:1 join
# 
# [BOUNDARY] SFR value boundaries:
#   Min value: 1.0 (expected >= 1)
#   Max value: 110.0 (known outlier at 110)
#   Rows with SFR < 1: 0
#   Rows with SFR == 1: 18
#   Fractional values (unexpected from Int64 source): 0
# [PASS] Boundary: All SFR values are whole numbers >= 1
# 
# [ABSENCE] Column drop analysis:
#   Raw had 'year': True, Clean has 'year': False
#   Raw had 'fips': True, Clean has 'fips': False
# [PASS] Absence: Column drops are safe (year was single-valued, fips from directory)
# 
# [DOWNSTREAM] Potential surprises for join-resources:
#   unitid dtype: Int64 (should be Int64 for join compatibility)
#   SFR 10th percentile: 7.0
#   SFR 90th percentile: 24.0
#   SFR IQR: 9.0
#   Total institutions: 5,835
# [PASS] Downstream: unitid type compatible for joins
# 
# --- Spot-Checks ---
# 
# [SPOT] Outlier unitid=246035:
#   In raw:   1 rows, SFR=[110]
#   In clean: 1 rows, SFR=[110.0]
# [PASS] Outlier preserved correctly (SFR=110.0, flagged but retained)
# 
# [SPOT] SFR distribution plausibility:
#   Median: 14.0 (expected ~14-16)
#   Mean: 15.1 (expected ~14-16)
#   % with SFR > 40: 0.9%
#   % with SFR < 5: 3.2%
# [PASS] SFR distribution plausible for US 4-year institutions
# 
# [SPOT] Row difference: 5836 raw - 5835 clean = 1 removed
#   Execution log claimed: 1 row removed (the null SFR row)
# [PASS] Row difference matches execution log
# 
# [SPOT] Zero SFR values in clean: 0
# [PASS] No zero SFR values (filter working correctly)
# 
# [SPOT] Unitid counts: raw unique=5,836, clean unique=5,835
#   Difference: 1 (should = rows removed = 1)
# [PASS] Unitid difference matches row removal count
# 
# ============================================================
# SUMMARY
# ============================================================
#   Default checks:        PASSED
#   Script-specific checks: PASSED
#   Spot-checks:           PASSED
# 
#   QA RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 2)
# ┌────────┬───────────────────────┐
# │ unitid ┆ student_faculty_ratio │
# │ ---    ┆ ---                   │
# │ i64    ┆ f64                   │
# ╞════════╪═══════════════════════╡
# │ 100654 ┆ 18.0                  │
# │ 100663 ┆ 20.0                  │
# │ 100690 ┆ 13.0                  │
# │ 100706 ┆ 19.0                  │
# │ 100724 ┆ 15.0                  │
# │ …      ┆ …                     │
# │ 101189 ┆ 13.0                  │
# │ 101240 ┆ 15.0                  │
# │ 101277 ┆ 22.0                  │
# │ 101286 ┆ 13.0                  │
# │ 101295 ┆ 17.0                  │
# └────────┴───────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 3)
# ┌────────────┬───────────────┬───────────────────────┐
# │ statistic  ┆ unitid        ┆ student_faculty_ratio │
# │ ---        ┆ ---           ┆ ---                   │
# │ str        ┆ f64           ┆ f64                   │
# ╞════════════╪═══════════════╪═══════════════════════╡
# │ count      ┆ 5835.0        ┆ 5835.0                │
# │ null_count ┆ 0.0           ┆ 0.0                   │
# │ mean       ┆ 283874.099914 ┆ 15.116881             │
# │ std        ┆ 137926.582897 ┆ 7.306764              │
# │ min        ┆ 100654.0      ┆ 1.0                   │
# │ 25%        ┆ 169761.0      ┆ 10.0                  │
# │ 50%        ┆ 219921.0      ┆ 14.0                  │
# │ 75%        ┆ 445300.0      ┆ 19.0                  │
# │ max        ┆ 496423.0      ┆ 110.0                 │
# └────────────┴───────────────┴───────────────────────┘
# 
# SFR value counts (top 20 most common values):
# shape: (20, 2)
# ┌───────────────────────┬───────┐
# │ student_faculty_ratio ┆ count │
# │ ---                   ┆ ---   │
# │ f64                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ 15.0                  ┆ 521   │
# │ 10.0                  ┆ 409   │
# │ 12.0                  ┆ 404   │
# │ 14.0                  ┆ 385   │
# │ 11.0                  ┆ 344   │
# │ …                     ┆ …     │
# │ 21.0                  ┆ 133   │
# │ 25.0                  ┆ 133   │
# │ 5.0                   ┆ 105   │
# │ 22.0                  ┆ 99    │
# │ 24.0                  ┆ 88    │
# └───────────────────────┴───────┘
# 
# SFR histogram (decile bins):
#       0th percentile: 1.0
#      10th percentile: 7.0
#      20th percentile: 10.0
#      30th percentile: 11.0
#      40th percentile: 13.0
#      50th percentile: 14.0
#      60th percentile: 15.0
#      70th percentile: 18.0
#      80th percentile: 20.0
#      90th percentile: 24.0
#     100th percentile: 110.0
# 
# Raw data year distribution (for context):
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 5836  │
# └──────┴───────┘
# 
# Raw data: rows with null SFR = 1
# Raw data: rows with SFR == 0  = 0
# Raw data: rows with coded values = None
# 
# Removed row(s) (in raw but not in clean):
# shape: (1, 4)
# ┌────────┬──────┬──────┬───────────────────────┐
# │ unitid ┆ year ┆ fips ┆ student_faculty_ratio │
# │ ---    ┆ ---  ┆ ---  ┆ ---                   │
# │ i64    ┆ i64  ┆ i64  ┆ i64                   │
# ╞════════╪══════╪══════╪═══════════════════════╡
# │ 121992 ┆ 2020 ┆ 6    ┆ null                  │
# └────────┴──────┴──────┴───────────────────────┘
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
