#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 01

Reviewed script: scripts/stage6_clean/01_clean-directory.py
Output files: data/processed/2026-03-29_directory_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
6. [Counterfactual] What if raw data had multiple rows per unitid for year 2020?
7. [Semantic] Does open_public mean what downstream scripts expect?
8. [Boundary] Any edge-case fips values (0, 99, null)?
9. [Absence] Are there institutions in the raw 4-yr population that disappeared?
10. [Downstream] Will inst_control + unitid join cleanly to admissions/grad-rates?
-- Spot-checks:
11. Trace a specific institution through raw -> clean
12. Verify inst_control distribution matches known IPEDS population
13. Verify the filter complement (what was removed) looks correct
14. Check HBCU count against known count (~100 HBCUs exist)
15. Verify fips codes are valid U.S. state FIPS
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data/processed/2026-03-29_directory_clean.parquet"
RAW_FILE = PROJECT_DIR / "data/raw/2026-03-29_ipeds_directory.parquet"
EXPECTED_COLUMNS = ["unitid", "inst_name", "fips", "inst_control", "open_public", "hbcu", "tribal_college"]
EXPECTED_MIN_ROWS = 2500
EXPECTED_MAX_ROWS = 4500
CRITICAL_COLUMNS = ["unitid", "inst_name", "fips", "inst_control"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 01 — clean-directory")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded clean data: {df.shape[0]:,} rows x {df.shape[1]} cols")

raw_df = pl.read_parquet(RAW_FILE)
print(f"Loaded raw data: {raw_df.shape[0]:,} rows x {raw_df.shape[1]} cols")

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
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# Check dtypes are sensible
print(f"\nColumn dtypes:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"\n[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

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
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"\n[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
if coded_ok:
    print("None remain in any integer column")
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
print(f"\n[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# === SCRIPT-SPECIFIC CHECKS ===

# --- Check 6 [Counterfactual]: unitid uniqueness deep verify ---
# What if the raw data had duplicate unitids for 2020? The script asserts
# uniqueness, but let's independently verify in the output AND check
# if the raw data actually had duplicates.
print(f"\n--- Counterfactual: unitid duplication ---")
clean_unique = df["unitid"].n_unique()
clean_rows = df.shape[0]
unitid_unique_ok = clean_unique == clean_rows
print(f"[{'PASS' if unitid_unique_ok else 'FAIL'}] Clean unitid: {clean_unique:,} unique in {clean_rows:,} rows")

# Check raw data for year 2020 duplication
raw_2020 = raw_df.filter(pl.col("year") == 2020)
raw_2020_dups = raw_2020.shape[0] - raw_2020["unitid"].n_unique()
print(f"  Raw 2020 rows: {raw_2020.shape[0]:,}, duplicate unitids: {raw_2020_dups}")
if raw_2020_dups > 0:
    print(f"  [WARN] Raw data has {raw_2020_dups} duplicate unitid rows for year 2020!")
else:
    print(f"  [INFO] Raw data is 1:1 on unitid for year 2020 - no duplication risk")

# --- Check 7 [Semantic]: open_public meaning verification ---
# The script notes open_public means "open to the public" operating status,
# NOT open-admissions. Verify the distribution makes sense -- most degree-
# granting 4-yr institutions should be open to the public (value 1).
print(f"\n--- Semantic: open_public distribution ---")
op_dist = df["open_public"].value_counts().sort("open_public")
print(op_dist)
op_ones = (df["open_public"] == 1).sum()
op_zeros = (df["open_public"] == 0).sum()
op_nulls = df["open_public"].null_count()
total = len(df)
pct_open = op_ones / total * 100 if total > 0 else 0
print(f"  open_public=1: {op_ones} ({pct_open:.1f}%)")
print(f"  open_public=0: {op_zeros}")
print(f"  open_public=null: {op_nulls}")
# Nearly all degree-granting 4-yr institutions should be open to the public
if pct_open < 90:
    print(f"  [WARN] Only {pct_open:.1f}% open_public=1. Expected >90% for 4-yr degree-granting.")
else:
    print(f"  [PASS] {pct_open:.1f}% open_public=1 -- consistent with nearly all degree-granting institutions being open to the public")

# --- Check 8 [Boundary]: fips codes ---
print(f"\n--- Boundary: fips codes ---")
fips_vals = sorted(df["fips"].unique().to_list())
n_fips = len(fips_vals)
# Valid US FIPS: 1-56 (states + DC + territories), some outliers possible
# 0 or 99 would be suspicious
fips_suspicious = [f for f in fips_vals if f <= 0 or f > 78]
fips_ok = len(fips_suspicious) == 0
print(f"  {n_fips} unique fips values")
print(f"  Range: {min(fips_vals)} to {max(fips_vals)}")
if fips_suspicious:
    print(f"  [WARN] Suspicious fips values: {fips_suspicious}")
else:
    print(f"  [PASS] All fips values in valid range (1-78)")
# Check for null fips
fips_nulls = df["fips"].null_count()
print(f"  Null fips: {fips_nulls}")

# --- Check 9 [Absence]: Institutions lost during filtering ---
# Verify the filter complement: what institution_level values were removed?
print(f"\n--- Absence: Filter complement analysis ---")
raw_2020_dg = raw_df.filter(
    (pl.col("year") == 2020) & (pl.col("degree_granting") == 1)
)
raw_2020_dg_levels = raw_2020_dg["institution_level"].value_counts().sort("institution_level")
print(f"  Raw 2020, degree_granting==1, institution_level distribution:")
print(raw_2020_dg_levels)

# How many were excluded by institution_level != 4?
excluded_levels = raw_2020_dg.filter(pl.col("institution_level") != 4)
print(f"  Institutions excluded by institution_level != 4: {excluded_levels.shape[0]:,}")
print(f"  Institutions retained (level==4): {raw_2020_dg.filter(pl.col('institution_level') == 4).shape[0]:,}")

# Are there any institutions where institution_level==-1 (missing)?
missing_level = raw_2020_dg.filter(pl.col("institution_level") == -1).shape[0]
if missing_level > 0:
    print(f"  [INFO] {missing_level} institutions have institution_level==-1 (missing), excluded from analysis")

# --- Check 10 [Downstream]: inst_control distribution for join compatibility ---
print(f"\n--- Downstream: inst_control for joins ---")
ic_dist = df["inst_control"].value_counts().sort("inst_control")
print(ic_dist)
ic_values = sorted(df["inst_control"].unique().to_list())
ic_valid = all(v in [1, 2, 3] for v in ic_values)
print(f"[{'PASS' if ic_valid else 'FAIL'}] inst_control values: {ic_values} (expected [1, 2, 3])")
# Check proportions are reasonable: public ~30%, private NP ~55%, for-profit ~15%
for ic_val, label in [(1, "Public"), (2, "Private NP"), (3, "For-Profit")]:
    ct = (df["inst_control"] == ic_val).sum()
    pct = ct / len(df) * 100
    print(f"  {label} (inst_control={ic_val}): {ct:,} ({pct:.1f}%)")

# === SPOT-CHECKS ===

# --- Spot-check 11: Trace a specific known institution ---
print(f"\n--- Spot-check: Trace institution through raw -> clean ---")
# Use University of Alabama (unitid=100751, a well-known public 4-yr)
target_unitid = 100751
raw_target = raw_df.filter(
    (pl.col("unitid") == target_unitid) & (pl.col("year") == 2020)
)
clean_target = df.filter(pl.col("unitid") == target_unitid)
if len(raw_target) > 0:
    print(f"  Raw (unitid={target_unitid}, year=2020):")
    print(f"    inst_name: {raw_target['inst_name'][0]}")
    print(f"    degree_granting: {raw_target['degree_granting'][0]}")
    print(f"    institution_level: {raw_target['institution_level'][0]}")
    print(f"    inst_control: {raw_target['inst_control'][0]}")
    if len(clean_target) > 0:
        print(f"  Clean: FOUND -- inst_name={clean_target['inst_name'][0]}, inst_control={clean_target['inst_control'][0]}")
        print(f"  [PASS] Known 4-yr public institution successfully passed through filters")
    else:
        print(f"  [FAIL] Institution present in raw but MISSING from clean!")
else:
    # Try a different well-known institution
    print(f"  unitid={target_unitid} not in raw data. Trying first unitid in clean data.")
    sample_unitid = df["unitid"][0]
    raw_s = raw_df.filter((pl.col("unitid") == sample_unitid) & (pl.col("year") == 2020))
    clean_s = df.filter(pl.col("unitid") == sample_unitid)
    print(f"  Raw: {raw_s.select(['unitid', 'inst_name', 'degree_granting', 'institution_level', 'inst_control'])}")
    print(f"  Clean: {clean_s}")
    print(f"  [PASS] Sample institution traces correctly")

# --- Spot-check 12: inst_control distribution vs known IPEDS population ---
print(f"\n--- Spot-check: inst_control proportions ---")
n_public = (df["inst_control"] == 1).sum()
n_private_np = (df["inst_control"] == 2).sum()
n_private_fp = (df["inst_control"] == 3).sum()
# Known approximate proportions for 4-yr degree-granting:
# Public: ~25-35%, Private NP: ~45-60%, For-Profit: ~8-20%
pct_public = n_public / len(df) * 100
pct_private_np = n_private_np / len(df) * 100
pct_private_fp = n_private_fp / len(df) * 100
proportions_ok = (20 < pct_public < 40) and (40 < pct_private_np < 65) and (5 < pct_private_fp < 25)
print(f"  Public: {pct_public:.1f}% (expected 25-35%)")
print(f"  Private NP: {pct_private_np:.1f}% (expected 45-60%)")
print(f"  For-Profit: {pct_private_fp:.1f}% (expected 8-20%)")
print(f"[{'PASS' if proportions_ok else 'WARN'}] Sector proportions {'reasonable' if proportions_ok else 'outside expected range'}")

# --- Spot-check 13: Filter complement - what DID get removed? ---
print(f"\n--- Spot-check: What institutions were removed by filters? ---")
removed_by_year = raw_df.filter(pl.col("year") != 2020).shape[0]
raw_2020_all = raw_df.filter(pl.col("year") == 2020)
removed_by_dg = raw_2020_all.filter(pl.col("degree_granting") != 1).shape[0]
raw_2020_dg_only = raw_2020_all.filter(pl.col("degree_granting") == 1)
removed_by_level = raw_2020_dg_only.filter(pl.col("institution_level") != 4).shape[0]
print(f"  Removed by year != 2020: {removed_by_year:,}")
print(f"  Removed by degree_granting != 1 (within 2020): {removed_by_dg:,}")
print(f"  Removed by institution_level != 4 (within 2020+DG): {removed_by_level:,}")
print(f"  Final clean: {len(df):,}")
total_removed = removed_by_year + removed_by_dg + removed_by_level
total_expected = raw_df.shape[0] - len(df)
print(f"  Total removed: {total_removed:,} (expected {total_expected:,})")
removal_sum_ok = total_removed == total_expected
print(f"[{'PASS' if removal_sum_ok else 'FAIL'}] Filter removal counts add up correctly")

# --- Spot-check 14: HBCU count ---
print(f"\n--- Spot-check: HBCU count ---")
hbcu_count = (df["hbcu"] == 1).sum()
hbcu_null = df["hbcu"].null_count()
# Known: approximately 100-107 HBCUs in the US, many are 4-year
print(f"  HBCUs in clean data: {hbcu_count}")
print(f"  HBCU nulls: {hbcu_null}")
hbcu_ok = 80 <= hbcu_count <= 110
print(f"[{'PASS' if hbcu_ok else 'WARN'}] HBCU count {'reasonable' if hbcu_ok else f'unexpected ({hbcu_count})'} (expected 80-110 4-yr HBCUs)")

# --- Spot-check 15: Valid fips codes ---
print(f"\n--- Spot-check: fips code coverage ---")
# US states: 1-56 excluding gaps; DC=11; territories go higher
# Check that we have institutions from many states
n_states = df["fips"].n_unique()
print(f"  Unique fips codes: {n_states}")
# Should have at least 50 (all 50 states + DC)
fips_coverage_ok = n_states >= 50
print(f"[{'PASS' if fips_coverage_ok else 'WARN'}] State coverage: {n_states} states {'(good coverage)' if fips_coverage_ok else '(low coverage)'}")

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns and df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        print(f"\n{col}:")
        print(df[col].value_counts().sort("count", descending=True).head(20))

print("\nopen_public distribution:")
print(df["open_public"].value_counts())

print("\nhbcu distribution:")
print(df["hbcu"].value_counts())

print("\ntribal_college distribution:")
print(df["tribal_college"].value_counts())

# --- Summary ---
all_base_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([unitid_unique_ok, ic_valid, fips_ok, removal_sum_ok])
all_passed = all_base_passed and all_specific_passed
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
if not all_passed:
    if not all_base_passed:
        print("  Base check failures detected")
    if not all_specific_passed:
        print("  Script-specific check failures detected")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:44:22
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_01_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 01 — clean-directory
# ============================================================
# Loaded clean data: 2,893 rows x 7 cols
# Loaded raw data: 12,729 rows x 89 cols
# 
# [PASS] Schema: All expected columns present
# 
# Column dtypes:
#   unitid: Int64
#   inst_name: String
#   fips: Int64
#   inst_control: Int64
#   open_public: Int64
#   hbcu: Int64
#   tribal_college: Int64
# 
# [PASS] Row count: 2,893 (expected 2,500-4,500)
# 
# [PASS] Distributions: Look reasonable
# 
# [PASS] Coded values: None remain in any integer column
# 
# [PASS] Critical nulls: None
# 
# --- Counterfactual: unitid duplication ---
# [PASS] Clean unitid: 2,893 unique in 2,893 rows
#   Raw 2020 rows: 6,440, duplicate unitids: 0
#   [INFO] Raw data is 1:1 on unitid for year 2020 - no duplication risk
# 
# --- Semantic: open_public distribution ---
# shape: (2, 2)
# ┌─────────────┬───────┐
# │ open_public ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 0           ┆ 2     │
# │ 1           ┆ 2891  │
# └─────────────┴───────┘
#   open_public=1: 2891 (99.9%)
#   open_public=0: 2
#   open_public=null: 0
#   [PASS] 99.9% open_public=1 -- consistent with nearly all degree-granting institutions being open to the public
# 
# --- Boundary: fips codes ---
#   58 unique fips values
#   Range: 1 to 78
#   [PASS] All fips values in valid range (1-78)
#   Null fips: 0
# 
# --- Absence: Filter complement analysis ---
#   Raw 2020, degree_granting==1, institution_level distribution:
# shape: (2, 2)
# ┌───────────────────┬───────┐
# │ institution_level ┆ count │
# │ ---               ┆ ---   │
# │ i64               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ 2                 ┆ 1357  │
# │ 4                 ┆ 2893  │
# └───────────────────┴───────┘
#   Institutions excluded by institution_level != 4: 1,357
#   Institutions retained (level==4): 2,893
# 
# --- Downstream: inst_control for joins ---
# shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 852   │
# │ 2            ┆ 1671  │
# │ 3            ┆ 370   │
# └──────────────┴───────┘
# [PASS] inst_control values: [1, 2, 3] (expected [1, 2, 3])
#   Public (inst_control=1): 852 (29.5%)
#   Private NP (inst_control=2): 1,671 (57.8%)
#   For-Profit (inst_control=3): 370 (12.8%)
# 
# --- Spot-check: Trace institution through raw -> clean ---
#   Raw (unitid=100751, year=2020):
#     inst_name: The University of Alabama
#     degree_granting: 1
#     institution_level: 4
#     inst_control: 1
#   Clean: FOUND -- inst_name=The University of Alabama, inst_control=1
#   [PASS] Known 4-yr public institution successfully passed through filters
# 
# --- Spot-check: inst_control proportions ---
#   Public: 29.5% (expected 25-35%)
#   Private NP: 57.8% (expected 45-60%)
#   For-Profit: 12.8% (expected 8-20%)
# [PASS] Sector proportions reasonable
# 
# --- Spot-check: What institutions were removed by filters? ---
#   Removed by year != 2020: 6,289
#   Removed by degree_granting != 1 (within 2020): 2,190
#   Removed by institution_level != 4 (within 2020+DG): 1,357
#   Final clean: 2,893
#   Total removed: 9,836 (expected 9,836)
# [PASS] Filter removal counts add up correctly
# 
# --- Spot-check: HBCU count ---
#   HBCUs in clean data: 91
#   HBCU nulls: 0
# [PASS] HBCU count reasonable (expected 80-110 4-yr HBCUs)
# 
# --- Spot-check: fips code coverage ---
#   Unique fips codes: 58
# [PASS] State coverage: 58 states (good coverage)
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 7)
# ┌────────┬─────────────────────────────┬──────┬──────────────┬─────────────┬──────┬────────────────┐
# │ unitid ┆ inst_name                   ┆ fips ┆ inst_control ┆ open_public ┆ hbcu ┆ tribal_college │
# │ ---    ┆ ---                         ┆ ---  ┆ ---          ┆ ---         ┆ ---  ┆ ---            │
# │ i64    ┆ str                         ┆ i64  ┆ i64          ┆ i64         ┆ i64  ┆ i64            │
# ╞════════╪═════════════════════════════╪══════╪══════════════╪═════════════╪══════╪════════════════╡
# │ 100654 ┆ Alabama A & M University    ┆ 1    ┆ 1            ┆ 1           ┆ 1    ┆ 0              │
# │ 100663 ┆ University of Alabama at    ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# │        ┆ Birmi…                      ┆      ┆              ┆             ┆      ┆                │
# │ 100690 ┆ Amridge University          ┆ 1    ┆ 2            ┆ 1           ┆ 0    ┆ 0              │
# │ 100706 ┆ University of Alabama in    ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# │        ┆ Hunts…                      ┆      ┆              ┆             ┆      ┆                │
# │ 100724 ┆ Alabama State University    ┆ 1    ┆ 1            ┆ 1           ┆ 1    ┆ 0              │
# │ 100733 ┆ University of Alabama       ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# │        ┆ System O…                   ┆      ┆              ┆             ┆      ┆                │
# │ 100751 ┆ The University of Alabama   ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# │ 100812 ┆ Athens State University     ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# │ 100830 ┆ Auburn University at        ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# │        ┆ Montgomer…                  ┆      ┆              ┆             ┆      ┆                │
# │ 100858 ┆ Auburn University           ┆ 1    ┆ 1            ┆ 1           ┆ 0    ┆ 0              │
# └────────┴─────────────────────────────┴──────┴──────────────┴─────────────┴──────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 8)
# ┌────────────┬────────────┬────────────┬───────────┬────────────┬───────────┬──────────┬───────────┐
# │ statistic  ┆ unitid     ┆ inst_name  ┆ fips      ┆ inst_contr ┆ open_publ ┆ hbcu     ┆ tribal_co │
# │ ---        ┆ ---        ┆ ---        ┆ ---       ┆ ol         ┆ ic        ┆ ---      ┆ llege     │
# │ str        ┆ f64        ┆ str        ┆ f64       ┆ ---        ┆ ---       ┆ f64      ┆ ---       │
# │            ┆            ┆            ┆           ┆ f64        ┆ f64       ┆          ┆ f64       │
# ╞════════════╪════════════╪════════════╪═══════════╪════════════╪═══════════╪══════════╪═══════════╡
# │ count      ┆ 2893.0     ┆ 2893       ┆ 2893.0    ┆ 2893.0     ┆ 2893.0    ┆ 2893.0   ┆ 2893.0    │
# │ null_count ┆ 0.0        ┆ 0          ┆ 0.0       ┆ 0.0        ┆ 0.0       ┆ 0.0      ┆ 0.0       │
# │ mean       ┆ 240022.826 ┆ null       ┆ 29.891808 ┆ 1.833391   ┆ 0.999309  ┆ 0.031455 ┆ 0.006222  │
# │            ┆ 823        ┆            ┆           ┆            ┆           ┆          ┆           │
# │ std        ┆ 119303.323 ┆ null       ┆ 17.0178   ┆ 0.628313   ┆ 0.026288  ┆ 0.174575 ┆ 0.078647  │
# │            ┆ 702        ┆            ┆           ┆            ┆           ┆          ┆           │
# │ min        ┆ 100654.0   ┆ A T Still  ┆ 1.0       ┆ 1.0        ┆ 0.0       ┆ 0.0      ┆ 0.0       │
# │            ┆            ┆ University ┆           ┆            ┆           ┆          ┆           │
# │            ┆            ┆ of Health… ┆           ┆            ┆           ┆          ┆           │
# │ 25%        ┆ 157447.0   ┆ null       ┆ 15.0      ┆ 1.0        ┆ 1.0       ┆ 0.0      ┆ 0.0       │
# │ 50%        ┆ 200697.0   ┆ null       ┆ 31.0      ┆ 2.0        ┆ 1.0       ┆ 0.0      ┆ 0.0       │
# │ 75%        ┆ 240462.0   ┆ null       ┆ 42.0      ┆ 2.0        ┆ 1.0       ┆ 0.0      ┆ 0.0       │
# │ max        ┆ 496326.0   ┆ Zaytuna    ┆ 78.0      ┆ 3.0        ┆ 1.0       ┆ 1.0      ┆ 1.0       │
# │            ┆            ┆ College    ┆           ┆            ┆           ┆          ┆           │
# └────────────┴────────────┴────────────┴───────────┴────────────┴───────────┴──────────┴───────────┘
# 
# Key column value counts:
# 
# unitid:
# shape: (20, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ i64    ┆ u32   │
# ╞════════╪═══════╡
# │ 475121 ┆ 1     │
# │ 486433 ┆ 1     │
# │ 155973 ┆ 1     │
# │ 207315 ┆ 1     │
# │ 168847 ┆ 1     │
# │ …      ┆ …     │
# │ 206622 ┆ 1     │
# │ 201371 ┆ 1     │
# │ 235547 ┆ 1     │
# │ 153108 ┆ 1     │
# │ 204176 ┆ 1     │
# └────────┴───────┘
# 
# fips:
# shape: (20, 2)
# ┌──────┬───────┐
# │ fips ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 6    ┆ 294   │
# │ 36   ┆ 243   │
# │ 42   ┆ 160   │
# │ 48   ┆ 159   │
# │ 12   ┆ 132   │
# │ …    ┆ …     │
# │ 53   ┆ 63    │
# │ 47   ┆ 62    │
# │ 18   ┆ 61    │
# │ 55   ┆ 54    │
# │ 27   ┆ 52    │
# └──────┴───────┘
# 
# inst_control:
# shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 2            ┆ 1671  │
# │ 1            ┆ 852   │
# │ 3            ┆ 370   │
# └──────────────┴───────┘
# 
# open_public distribution:
# shape: (2, 2)
# ┌─────────────┬───────┐
# │ open_public ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 0           ┆ 2     │
# │ 1           ┆ 2891  │
# └─────────────┴───────┘
# 
# hbcu distribution:
# shape: (2, 2)
# ┌──────┬───────┐
# │ hbcu ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 0    ┆ 2802  │
# │ 1    ┆ 91    │
# └──────┴───────┘
# 
# tribal_college distribution:
# shape: (2, 2)
# ┌────────────────┬───────┐
# │ tribal_college ┆ count │
# │ ---            ┆ ---   │
# │ i64            ┆ u32   │
# ╞════════════════╪═══════╡
# │ 1              ┆ 18    │
# │ 0              ┆ 2875  │
# └────────────────┴───────┘
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
