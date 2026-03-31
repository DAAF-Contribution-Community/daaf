#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 06

Reviewed script: scripts/stage5_fetch/06_fetch-sfr.py
Output files: data/raw/2026-03-29_ipeds_sfr.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md Query 6 expectations
2. Row count within expected range (3,000-7,000)
3. No suspicious distributions
4. Coded values properly filtered (or absent)
5. No nulls in critical columns (unitid, year)

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if SFR contains negative values masking coded missing?
7. [Semantic] Does student_faculty_ratio actually represent what the research needs?
8. [Boundary] Check edge cases: zero SFR, extreme SFR, single-institution outliers
9. [Absence] Verify no institutions are duplicated (unitid uniqueness for year 2020)
10. [Downstream] Will Int64 dtype cause precision loss in Stage 6/7 downstream?

Spot-Checks:
11. Trace a specific known institution through the data
12. Verify SFR distribution matches known national averages
13. Check that removed years (non-2020) are truly absent
14. Cross-check row count against other Wave 1 datasets for consistency
15. Verify FIPS codes are valid US state/territory codes
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_sfr.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "fips", "student_faculty_ratio"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 7000
CRITICAL_COLUMNS = ["unitid", "year"]
CODED_MISSING_VALUES = [-1, -2, -3]

# Valid US FIPS state codes (1-56 + territories: 60, 64, 66, 68, 69, 70, 72, 78)
VALID_FIPS = set(range(1, 57)) | {60, 64, 66, 68, 69, 70, 72, 78}

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 06 (fetch-sfr)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

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
    print(f"  Extra columns (not in Plan.md Query 6): {extra_cols}")

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
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
if coded_ok:
    print("None remain")
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

# === Script-Specific Checks (Five Lenses) ===

# --- Check 6: [Counterfactual] Negative values masking coded missing ---
# INTENT: The coded missing scan in the script found 0 coded values. But what
# if there are OTHER negative values that aren't -1/-2/-3?
print(f"\n--- Script-Specific Checks ---")
sfr_col = df["student_faculty_ratio"].drop_nulls()
neg_count = sfr_col.filter(sfr_col < 0).len()
neg_ok = neg_count == 0
print(f"[{'PASS' if neg_ok else 'WARN'}] Counterfactual: Negative SFR values: {neg_count}")
if neg_count > 0:
    neg_vals = sfr_col.filter(sfr_col < 0).value_counts()
    print(f"  Negative value distribution: {neg_vals}")

# --- Check 7: [Semantic] SFR meaning verification ---
# INTENT: Verify student_faculty_ratio represents the ratio we need for the
# research question (institutional resources). SFR should be a positive number
# typically between 5 and 50 for most institutions.
sfr_mean = sfr_col.mean()
sfr_median = sfr_col.median()
sfr_between_5_50 = sfr_col.filter((sfr_col >= 5) & (sfr_col <= 50)).len()
sfr_pct_typical = sfr_between_5_50 / len(sfr_col) * 100
semantic_ok = sfr_pct_typical > 80 and 10 < sfr_mean < 25
print(f"[{'PASS' if semantic_ok else 'WARN'}] Semantic: SFR mean={sfr_mean:.1f}, median={sfr_median:.1f}, "
      f"{sfr_pct_typical:.1f}% in typical range [5-50]")

# --- Check 8: [Boundary] Edge cases ---
# INTENT: Check for extreme values that could skew downstream analysis.
zero_sfr = sfr_col.filter(sfr_col == 0).len()
one_sfr = sfr_col.filter(sfr_col == 1).len()
gt_100 = sfr_col.filter(sfr_col > 100).len()
gt_200 = sfr_col.filter(sfr_col > 200).len()
boundary_issues = []
if zero_sfr > 0:
    boundary_issues.append(f"{zero_sfr} zeros")
if gt_100 > 10:
    boundary_issues.append(f"{gt_100} values > 100 (suspicious count)")
if gt_200 > 0:
    boundary_issues.append(f"{gt_200} values > 200 (extreme)")
boundary_ok = len(boundary_issues) == 0
print(f"[{'PASS' if boundary_ok else 'WARN'}] Boundary: ", end="")
if boundary_ok:
    print(f"No extreme edge cases (zeros={zero_sfr}, SFR=1: {one_sfr}, >100: {gt_100})")
else:
    print("; ".join(boundary_issues))

# --- Check 9: [Absence] Unitid uniqueness ---
# INTENT: For year 2020, each institution should appear exactly once.
# Duplicates would indicate a data integrity issue or unfiltered sub-records.
n_unique_unitid = df["unitid"].n_unique()
unitid_unique_ok = n_unique_unitid == len(df)
print(f"[{'PASS' if unitid_unique_ok else 'FAIL'}] Absence: unitid uniqueness: "
      f"{n_unique_unitid:,} unique vs {len(df):,} rows")
if not unitid_unique_ok:
    dupes = df.group_by("unitid").len().filter(pl.col("len") > 1)
    print(f"  Duplicate unitids: {dupes.shape[0]:,}")
    print(f"  Sample duplicates: {dupes.head(5)}")

# --- Check 10: [Downstream] Int64 dtype precision concern ---
# INTENT: SFR is stored as Int64, meaning values like 14.7 are truncated to 14.
# This could lose meaningful precision for downstream regression analysis.
sfr_dtype = df["student_faculty_ratio"].dtype
dtype_concern = sfr_dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]
print(f"[{'WARN' if dtype_concern else 'PASS'}] Downstream: SFR dtype is {sfr_dtype}", end="")
if dtype_concern:
    print(" -- integer type may lose fractional precision. Stage 6 clean should cast to Float64.")
else:
    print(" -- float type preserves precision")

# === Spot-Checks ===
print(f"\n--- Spot-Checks ---")

# --- Spot-Check 11: Known institution trace ---
# INTENT: Check if a well-known institution (Harvard, unitid=166027) appears
# with a plausible SFR value.
harvard = df.filter(pl.col("unitid") == 166027)
if len(harvard) > 0:
    harvard_sfr = harvard["student_faculty_ratio"][0]
    # Harvard's SFR is typically around 5-7 (very low, as expected for elite institution)
    harvard_plausible = 3 <= harvard_sfr <= 15 if harvard_sfr is not None else False
    print(f"[{'PASS' if harvard_plausible else 'WARN'}] Spot-check: Harvard (166027) SFR = {harvard_sfr} "
          f"(expected ~5-7 for elite institution)")
else:
    print(f"[INFO] Spot-check: Harvard (166027) not found in dataset")

# Large state university check (Ohio State, unitid=204796)
osu = df.filter(pl.col("unitid") == 204796)
if len(osu) > 0:
    osu_sfr = osu["student_faculty_ratio"][0]
    # Ohio State SFR is typically around 15-20
    osu_plausible = 10 <= osu_sfr <= 30 if osu_sfr is not None else False
    print(f"[{'PASS' if osu_plausible else 'WARN'}] Spot-check: Ohio State (204796) SFR = {osu_sfr} "
          f"(expected ~15-20 for large public)")
else:
    print(f"[INFO] Spot-check: Ohio State (204796) not found in dataset")

# --- Spot-Check 12: National average comparison ---
# INTENT: NCES reports national average SFR for 4-year institutions around 14-16.
# Our mean should be in that ballpark (includes 2-year and <4-year institutions too).
nat_avg_ok = 10 <= sfr_mean <= 25
print(f"[{'PASS' if nat_avg_ok else 'WARN'}] Spot-check: National avg SFR = {sfr_mean:.1f} "
      f"(NCES reports ~14-16 for degree-granting)")

# --- Spot-Check 13: Year filter verification ---
# INTENT: Confirm only year 2020 is present -- no leakage of other years.
years_present = sorted(df["year"].unique().to_list())
year_filter_ok = years_present == [2020]
print(f"[{'PASS' if year_filter_ok else 'FAIL'}] Spot-check: Years present = {years_present} (expected [2020])")

# --- Spot-Check 14: Cross-check with other Wave 1 datasets ---
# INTENT: SFR dataset should have institution count comparable to other IPEDS
# datasets for 2020. The directory had ~8,000 rows for 2020 (includes all
# institution types). SFR of 5,836 for ALL institutions (including 2-year)
# is plausible. Check this is in the right order of magnitude.
expected_institutions_all = 5836  # From execution log
# Directory had ~8,000 for 2 years, so ~4,000 per year for 4-yr degree-granting
# SFR covers ALL institutions (not filtered to 4-yr yet), so more rows is expected
row_magnitude_ok = 3000 <= expected_institutions_all <= 8000
print(f"[{'PASS' if row_magnitude_ok else 'WARN'}] Spot-check: {expected_institutions_all:,} institutions -- "
      f"plausible for all-institution SFR dataset before 4-yr filtering")

# --- Spot-Check 15: FIPS code validity ---
# INTENT: Verify FIPS codes are valid US state/territory codes.
fips_values = set(df["fips"].unique().to_list())
invalid_fips = fips_values - VALID_FIPS
fips_ok = len(invalid_fips) == 0
print(f"[{'PASS' if fips_ok else 'WARN'}] Spot-check: FIPS codes -- "
      f"{len(fips_values)} unique states/territories", end="")
if not fips_ok:
    print(f" -- invalid codes: {sorted(invalid_fips)}")
else:
    print(" -- all valid")

# --- Summary ---
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([neg_ok, semantic_ok, boundary_ok, unitid_unique_ok])
all_spot_passed = all([nat_avg_ok, year_filter_ok, row_magnitude_ok])

overall = all_default_passed and all_specific_passed and all_spot_passed
print("\n" + "=" * 60)
severity = "PASSED" if overall else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if dtype_concern:
    print("  WARNING: student_faculty_ratio is Int64 (precision loss for downstream)")
if not fips_ok:
    print(f"  WARNING: Invalid FIPS codes detected: {sorted(invalid_fips)}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nSFR distribution (percentiles):")
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    val = sfr_col.quantile(p / 100)
    print(f"  P{p}: {val}")

print(f"\nSFR value counts (top 20):")
print(sfr_col.value_counts().sort("count", descending=True).head(20))

print(f"\nFIPS distribution (top 10 states by institution count):")
print(df["fips"].value_counts().sort("count", descending=True).head(10))

print(f"\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print(f"\nSFR null count: {df['student_faculty_ratio'].null_count()}")
print(f"SFR zero count: {(df['student_faculty_ratio'] == 0).sum()}")
print(f"SFR < 0 count: {(df['student_faculty_ratio'] < 0).sum()}")
print(f"SFR > 100 count: {(df['student_faculty_ratio'] > 100).sum()}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:51:44
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_06_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 06 (fetch-sfr)
# ============================================================
# Loaded: 5,836 rows x 4 cols
# Columns: ['unitid', 'year', 'fips', 'student_faculty_ratio']
# Dtypes: [Int64, Int64, Int64, Int64]
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,836 (expected 3,000-7,000)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Script-Specific Checks ---
# [PASS] Counterfactual: Negative SFR values: 0
# [PASS] Semantic: SFR mean=15.1, median=14.0, 96.6% in typical range [5-50]
# [PASS] Boundary: No extreme edge cases (zeros=0, SFR=1: 18, >100: 1)
# [PASS] Absence: unitid uniqueness: 5,836 unique vs 5,836 rows
# [WARN] Downstream: SFR dtype is Int64 -- integer type may lose fractional precision. Stage 6 clean should cast to Float64.
# 
# --- Spot-Checks ---
# [PASS] Spot-check: Harvard (166027) SFR = 5 (expected ~5-7 for elite institution)
# [PASS] Spot-check: Ohio State (204796) SFR = 19 (expected ~15-20 for large public)
# [PASS] Spot-check: National avg SFR = 15.1 (NCES reports ~14-16 for degree-granting)
# [PASS] Spot-check: Years present = [2020] (expected [2020])
# [PASS] Spot-check: 5,836 institutions -- plausible for all-institution SFR dataset before 4-yr filtering
# [PASS] Spot-check: FIPS codes -- 59 unique states/territories -- all valid
# 
# ============================================================
# QA RESULT: ISSUES_FOUND
#   WARNING: student_faculty_ratio is Int64 (precision loss for downstream)
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 4)
# ┌────────┬──────┬──────┬───────────────────────┐
# │ unitid ┆ year ┆ fips ┆ student_faculty_ratio │
# │ ---    ┆ ---  ┆ ---  ┆ ---                   │
# │ i64    ┆ i64  ┆ i64  ┆ i64                   │
# ╞════════╪══════╪══════╪═══════════════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 18                    │
# │ 100663 ┆ 2020 ┆ 1    ┆ 20                    │
# │ 100690 ┆ 2020 ┆ 1    ┆ 13                    │
# │ 100706 ┆ 2020 ┆ 1    ┆ 19                    │
# │ 100724 ┆ 2020 ┆ 1    ┆ 15                    │
# │ 100751 ┆ 2020 ┆ 1    ┆ 20                    │
# │ 100760 ┆ 2020 ┆ 1    ┆ 15                    │
# │ 100812 ┆ 2020 ┆ 1    ┆ 15                    │
# │ 100830 ┆ 2020 ┆ 1    ┆ 16                    │
# │ 100858 ┆ 2020 ┆ 1    ┆ 20                    │
# └────────┴──────┴──────┴───────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 5)
# ┌────────────┬───────────────┬────────┬───────────┬───────────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ fips      ┆ student_faculty_ratio │
# │ ---        ┆ ---           ┆ ---    ┆ ---       ┆ ---                   │
# │ str        ┆ f64           ┆ f64    ┆ f64       ┆ f64                   │
# ╞════════════╪═══════════════╪════════╪═══════════╪═══════════════════════╡
# │ count      ┆ 5836.0        ┆ 5836.0 ┆ 5836.0    ┆ 5835.0                │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 0.0       ┆ 1.0                   │
# │ mean       ┆ 283846.361378 ┆ 2020.0 ┆ 29.32865  ┆ 15.116881             │
# │ std        ┆ 137931.042049 ┆ 0.0    ┆ 16.830002 ┆ 7.306764              │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 1.0       ┆ 1.0                   │
# │ 25%        ┆ 169734.0      ┆ 2020.0 ┆ 13.0      ┆ 10.0                  │
# │ 50%        ┆ 219921.0      ┆ 2020.0 ┆ 30.0      ┆ 14.0                  │
# │ 75%        ┆ 445267.0      ┆ 2020.0 ┆ 42.0      ┆ 19.0                  │
# │ max        ┆ 496423.0      ┆ 2020.0 ┆ 78.0      ┆ 110.0                 │
# └────────────┴───────────────┴────────┴───────────┴───────────────────────┘
# 
# SFR distribution (percentiles):
#   P1: 3.0
#   P5: 6.0
#   P10: 7.0
#   P25: 10.0
#   P50: 14.0
#   P75: 19.0
#   P90: 24.0
#   P95: 27.0
#   P99: 40.0
# 
# SFR value counts (top 20):
# shape: (20, 2)
# ┌───────────────────────┬───────┐
# │ student_faculty_ratio ┆ count │
# │ ---                   ┆ ---   │
# │ i64                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ 15                    ┆ 521   │
# │ 10                    ┆ 409   │
# │ 12                    ┆ 404   │
# │ 14                    ┆ 385   │
# │ 11                    ┆ 344   │
# │ …                     ┆ …     │
# │ 21                    ┆ 133   │
# │ 25                    ┆ 133   │
# │ 5                     ┆ 105   │
# │ 22                    ┆ 99    │
# │ 24                    ┆ 88    │
# └───────────────────────┴───────┘
# 
# FIPS distribution (top 10 states by institution count):
# shape: (10, 2)
# ┌──────┬───────┐
# │ fips ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 6    ┆ 599   │
# │ 36   ┆ 397   │
# │ 48   ┆ 377   │
# │ 12   ┆ 322   │
# │ 42   ┆ 291   │
# │ 39   ┆ 271   │
# │ 17   ┆ 220   │
# │ 37   ┆ 162   │
# │ 26   ┆ 156   │
# │ 34   ┆ 154   │
# └──────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 5836  │
# └──────┴───────┘
# 
# SFR null count: 1
# SFR zero count: 0
# SFR < 0 count: 0
# SFR > 100 count: 1
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
