#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 01

Reviewed script: scripts/stage5_fetch/01_fetch-directory.py
Output files: data/raw/2026-03-29_ipeds_directory.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values check (education domain: -1, -2, -3)
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] Verify data survives schema assumptions even with unexpected columns
7. [Semantic] Verify this is truly IPEDS directory data and not a different dataset
8. [Boundary] Check for duplicate (unitid, year) pairs -- composite key integrity
9. [Absence] Verify that hbcu and tribal_college columns exist (Plan.md Query 1 lists them)
10. [Downstream] Verify unitid is Integer type suitable for joins in Stage 6-7

Spot-Checks:
11. Trace a specific known institution (unitid) across years
12. Verify inst_control values are valid codes (1, 2, 3)
13. Verify institution_level contains code 4 (needed for Stage 6 filtering)
14. Verify degree_granting contains code 1 (needed for Stage 6 filtering)
15. Check that open_public is present and has expected values (0/1)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_directory.parquet"
EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "fips", "inst_control",
    "institution_level", "degree_granting", "open_public",
]
EXPECTED_MIN_ROWS = 6_000
EXPECTED_MAX_ROWS = 15_000
CRITICAL_COLUMNS = ["unitid", "year", "inst_control", "institution_level", "degree_granting"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 01 (fetch-directory)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

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
    print(f"  Extra columns (not in minimum required set): {len(extra_cols)} extra cols present (expected for raw fetch)")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns[:15]:
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

# --- Check 4: Coded values in critical columns ---
coded_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns and df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Coded values in critical cols: ", end="")
if coded_ok:
    print("None in critical columns")
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

# ==========================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ==========================================================

# --- Check 6: [Counterfactual] Schema robustness ---
# INTENT: Verify the data has the expected schema type even though we loaded raw
print(f"\n--- Script-Specific Checks ---")
unitid_dtype = df["unitid"].dtype
year_dtype = df["year"].dtype
dtype_ok = unitid_dtype in [pl.Int32, pl.Int64] and year_dtype in [pl.Int32, pl.Int64]
print(f"[{'PASS' if dtype_ok else 'FAIL'}] [Counterfactual] Key column dtypes: unitid={unitid_dtype}, year={year_dtype}")

# --- Check 7: [Semantic] Verify this is IPEDS directory data ---
# INTENT: Confirm this isn't a different dataset by checking for directory-specific columns
directory_signature_cols = ["inst_name", "fips", "inst_control", "institution_level",
                            "degree_granting", "open_public", "sector", "hbcu"]
found_signature = [c for c in directory_signature_cols if c in df.columns]
semantic_ok = len(found_signature) >= 6
print(f"[{'PASS' if semantic_ok else 'FAIL'}] [Semantic] IPEDS directory signature: {len(found_signature)}/{len(directory_signature_cols)} signature cols found")

# --- Check 8: [Boundary] Duplicate (unitid, year) pairs ---
# INTENT: Verify each institution appears at most once per year in the directory
total_rows = len(df)
unique_pairs = df.select("unitid", "year").n_unique()
dups_ok = total_rows == unique_pairs
print(f"[{'PASS' if dups_ok else 'FAIL'}] [Boundary] Composite key (unitid, year) uniqueness: {total_rows:,} rows, {unique_pairs:,} unique pairs", end="")
if not dups_ok:
    dup_count = total_rows - unique_pairs
    print(f" -- {dup_count:,} DUPLICATE PAIRS FOUND")
else:
    print("")

# --- Check 9: [Absence] Verify hbcu and tribal_college columns ---
# INTENT: Plan.md Query 1 lists hbcu and tribal_college in Variables. Verify they're present.
plan_extra_cols = ["hbcu", "tribal_college"]
absent_cols = [c for c in plan_extra_cols if c not in df.columns]
absence_ok = len(absent_cols) == 0
print(f"[{'PASS' if absence_ok else 'WARN'}] [Absence] Plan.md extra columns (hbcu, tribal_college): ", end="")
if absence_ok:
    print("Both present")
else:
    print(f"Missing: {absent_cols}")

# --- Check 10: [Downstream] unitid type suitable for joins ---
# INTENT: Stage 6-7 will join on unitid. Verify it's an integer type without string artifacts.
unitid_min = df["unitid"].min()
unitid_max = df["unitid"].max()
unitid_range_ok = unitid_min > 0 and unitid_max < 999_999_999
print(f"[{'PASS' if unitid_range_ok else 'WARN'}] [Downstream] unitid range: [{unitid_min:,}, {unitid_max:,}] (6-digit IDs expected)")

# ==========================================================
# SPOT-CHECKS
# ==========================================================
print(f"\n--- Spot-Checks ---")

# --- Spot-Check 11: Trace a known institution across years ---
# INTENT: Pick a well-known institution and verify it appears in both years
# Using unitid 110635 (UC Berkeley) or 166027 (MIT) as known large institutions
trace_ids = [110635, 166027, 243780]  # UC Berkeley, MIT, Yale
for uid in trace_ids:
    matches = df.filter(pl.col("unitid") == uid)
    if len(matches) > 0:
        years = sorted(matches["year"].to_list())
        name = matches["inst_name"][0]
        print(f"[PASS] Spot-check unitid {uid} ({name}): found in years {years}")
        break
else:
    # Try any unitid that appears in both years
    both_years = (
        df.group_by("unitid")
        .agg(pl.col("year").n_unique().alias("n_years"))
        .filter(pl.col("n_years") == 2)
    )
    if len(both_years) > 0:
        sample_uid = both_years["unitid"][0]
        sample_rows = df.filter(pl.col("unitid") == sample_uid)
        print(f"[PASS] Spot-check unitid {sample_uid} ({sample_rows['inst_name'][0]}): found in both years")
    else:
        print(f"[WARN] Could not find any institution in both years")

# --- Spot-Check 12: inst_control values are valid (1, 2, 3) ---
ic_values = sorted(df["inst_control"].drop_nulls().unique().to_list())
ic_valid = set(ic_values).issubset({1, 2, 3})
print(f"[{'PASS' if ic_valid else 'FAIL'}] inst_control values: {ic_values} (expected subset of [1, 2, 3])")

# --- Spot-Check 13: institution_level contains code 4 ---
il_values = sorted(df["institution_level"].drop_nulls().unique().to_list())
il_has_4 = 4 in il_values
print(f"[{'PASS' if il_has_4 else 'FAIL'}] institution_level contains 4: values found = {il_values}")
if il_has_4:
    n_level4 = (df["institution_level"] == 4).sum()
    print(f"  Count with institution_level==4: {n_level4:,} ({n_level4/len(df)*100:.1f}%)")

# --- Spot-Check 14: degree_granting contains code 1 ---
dg_values = sorted(df["degree_granting"].drop_nulls().unique().to_list())
dg_has_1 = 1 in dg_values
print(f"[{'PASS' if dg_has_1 else 'FAIL'}] degree_granting contains 1: values found = {dg_values}")
if dg_has_1:
    n_dg1 = (df["degree_granting"] == 1).sum()
    print(f"  Count with degree_granting==1: {n_dg1:,} ({n_dg1/len(df)*100:.1f}%)")

# --- Spot-Check 15: open_public values ---
op_values = sorted(df["open_public"].drop_nulls().unique().to_list())
op_valid = set(op_values).issubset({0, 1, -1, -2, -3})
op_null_count = df["open_public"].null_count()
print(f"[{'PASS' if op_valid else 'WARN'}] open_public values: {op_values}, nulls: {op_null_count}")
for v in op_values:
    ct = (df["open_public"] == v).sum()
    print(f"  open_public=={v}: {ct:,}")

# ==========================================================
# DATA PROFILING (for cr2+ decision)
# ==========================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 5 rows (selected columns):")
print(df.select(EXPECTED_COLUMNS).head(5))

print("\nDescriptive statistics (selected columns):")
print(df.select(EXPECTED_COLUMNS).describe())

print("\nKey column value counts:")
for col in ["year", "inst_control", "institution_level", "degree_granting", "open_public"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort(col))

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\nYear x institution_level cross-tab:")
cross = df.group_by("year", "institution_level").len().sort("year", "institution_level")
print(cross)

# --- Summary ---
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
    dtype_ok, semantic_ok, dups_ok, absence_ok, unitid_range_ok,
    ic_valid, il_has_4, dg_has_1,
]
all_passed = all(all_checks)
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if not all_passed:
    print("Failed checks: see details above")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:07:10
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_01_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 01 (fetch-directory)
# ============================================================
# Loaded: 12,729 rows x 89 cols
# 
# [PASS] Schema: All expected columns present
#   Extra columns (not in minimum required set): 81 extra cols present (expected for raw fetch)
# [PASS] Row count: 12,729 (expected 6,000-15,000)
# [PASS] Distributions: Look reasonable
# [WARN] Coded values in critical cols: inst_control has 68 coded value -1; institution_level has 68 coded value -1; degree_granting has 68 coded value -1
# [PASS] Critical nulls: None
# 
# --- Script-Specific Checks ---
# [PASS] [Counterfactual] Key column dtypes: unitid=Int64, year=Int64
# [PASS] [Semantic] IPEDS directory signature: 8/8 signature cols found
# [PASS] [Boundary] Composite key (unitid, year) uniqueness: 12,729 rows, 12,729 unique pairs
# [PASS] [Absence] Plan.md extra columns (hbcu, tribal_college): Both present
# [PASS] [Downstream] unitid range: [100,654, 497,347] (6-digit IDs expected)
# 
# --- Spot-Checks ---
# [PASS] Spot-check unitid 110635 (University of California-Berkeley): found in years [2020, 2021]
# [FAIL] inst_control values: [-1, 1, 2, 3] (expected subset of [1, 2, 3])
# [PASS] institution_level contains 4: values found = [-1, 1, 2, 4]
#   Count with institution_level==4: 5,743 (45.1%)
# [PASS] degree_granting contains 1: values found = [-1, 0, 1]
#   Count with degree_granting==1: 8,427 (66.2%)
# [PASS] open_public values: [0, 1], nulls: 0
#   open_public==0: 4
#   open_public==1: 12,725
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 5 rows (selected columns):
# shape: (5, 8)
# ┌────────┬──────┬───────────────┬──────┬──────────────┬───────────────┬──────────────┬─────────────┐
# │ unitid ┆ year ┆ inst_name     ┆ fips ┆ inst_control ┆ institution_l ┆ degree_grant ┆ open_public │
# │ ---    ┆ ---  ┆ ---           ┆ ---  ┆ ---          ┆ evel          ┆ ing          ┆ ---         │
# │ i64    ┆ i64  ┆ str           ┆ i64  ┆ i64          ┆ ---           ┆ ---          ┆ i64         │
# │        ┆      ┆               ┆      ┆              ┆ i64           ┆ i64          ┆             │
# ╞════════╪══════╪═══════════════╪══════╪══════════════╪═══════════════╪══════════════╪═════════════╡
# │ 100654 ┆ 2020 ┆ Alabama A & M ┆ 1    ┆ 1            ┆ 4             ┆ 1            ┆ 1           │
# │        ┆      ┆ University    ┆      ┆              ┆               ┆              ┆             │
# │ 100654 ┆ 2021 ┆ Alabama A & M ┆ 1    ┆ 1            ┆ 4             ┆ 1            ┆ 1           │
# │        ┆      ┆ University    ┆      ┆              ┆               ┆              ┆             │
# │ 100663 ┆ 2020 ┆ University of ┆ 1    ┆ 1            ┆ 4             ┆ 1            ┆ 1           │
# │        ┆      ┆ Alabama at    ┆      ┆              ┆               ┆              ┆             │
# │        ┆      ┆ Birmi…        ┆      ┆              ┆               ┆              ┆             │
# │ 100663 ┆ 2021 ┆ University of ┆ 1    ┆ 1            ┆ 4             ┆ 1            ┆ 1           │
# │        ┆      ┆ Alabama at    ┆      ┆              ┆               ┆              ┆             │
# │        ┆      ┆ Birmi…        ┆      ┆              ┆               ┆              ┆             │
# │ 100690 ┆ 2020 ┆ Amridge       ┆ 1    ┆ 2            ┆ 4             ┆ 1            ┆ 1           │
# │        ┆      ┆ University    ┆      ┆              ┆               ┆              ┆             │
# └────────┴──────┴───────────────┴──────┴──────────────┴───────────────┴──────────────┴─────────────┘
# 
# Descriptive statistics (selected columns):
# shape: (9, 9)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ unitid    ┆ year      ┆ inst_name ┆ … ┆ inst_cont ┆ instituti ┆ degree_gr ┆ open_pub │
# │ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ rol       ┆ on_level  ┆ anting    ┆ lic      │
# │ str       ┆ f64       ┆ f64       ┆ str       ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---      │
# │           ┆           ┆           ┆           ┆   ┆ f64       ┆ f64       ┆ f64       ┆ f64      │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 12729.0   ┆ 12729.0   ┆ 12729     ┆ … ┆ 12729.0   ┆ 12729.0   ┆ 12729.0   ┆ 12729.0  │
# │ null_coun ┆ 0.0       ┆ 0.0       ┆ 0         ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0      │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ 286128.34 ┆ 2020.4940 ┆ null      ┆ … ┆ 2.050279  ┆ 2.603975  ┆ 0.656689  ┆ 0.999686 │
# │           ┆ 0954      ┆ 69        ┆           ┆   ┆           ┆           ┆           ┆          │
# │ std       ┆ 139086.58 ┆ 0.499984  ┆ null      ┆ … ┆ 0.8632    ┆ 1.330593  ┆ 0.485954  ┆ 0.017725 │
# │           ┆ 5322      ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ min       ┆ 100654.0  ┆ 2020.0    ┆ A Better  ┆ … ┆ -1.0      ┆ -1.0      ┆ -1.0      ┆ 0.0      │
# │           ┆           ┆           ┆ U Beauty  ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆           ┆ Barber    ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆           ┆ Acade…    ┆   ┆           ┆           ┆           ┆          │
# │ 25%       ┆ 169798.0  ┆ 2020.0    ┆ null      ┆ … ┆ 1.0       ┆ 1.0       ┆ 0.0       ┆ 1.0      │
# │ 50%       ┆ 220996.0  ┆ 2020.0    ┆ null      ┆ … ┆ 2.0       ┆ 2.0       ┆ 1.0       ┆ 1.0      │
# │ 75%       ┆ 446516.0  ┆ 2021.0    ┆ null      ┆ … ┆ 3.0       ┆ 4.0       ┆ 1.0       ┆ 1.0      │
# │ max       ┆ 497347.0  ┆ 2021.0    ┆ eClips    ┆ … ┆ 3.0       ┆ 4.0       ┆ 1.0       ┆ 1.0      │
# │           ┆           ┆           ┆ School of ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆           ┆ Cosmetolo ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆           ┆ gy a…     ┆   ┆           ┆           ┆           ┆          │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Key column value counts:
# 
# year:
# shape: (2, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 6440  │
# │ 2021 ┆ 6289  │
# └──────┴───────┘
# 
# inst_control:
# shape: (4, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ -1           ┆ 68    │
# │ 1            ┆ 4030  │
# │ 2            ┆ 3757  │
# │ 3            ┆ 4874  │
# └──────────────┴───────┘
# 
# institution_level:
# shape: (4, 2)
# ┌───────────────────┬───────┐
# │ institution_level ┆ count │
# │ ---               ┆ ---   │
# │ i64               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ -1                ┆ 68    │
# │ 1                 ┆ 3594  │
# │ 2                 ┆ 3324  │
# │ 4                 ┆ 5743  │
# └───────────────────┴───────┘
# 
# degree_granting:
# shape: (3, 2)
# ┌─────────────────┬───────┐
# │ degree_granting ┆ count │
# │ ---             ┆ ---   │
# │ i64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ -1              ┆ 68    │
# │ 0               ┆ 4234  │
# │ 1               ┆ 8427  │
# └─────────────────┴───────┘
# 
# open_public:
# shape: (2, 2)
# ┌─────────────┬───────┐
# │ open_public ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 0           ┆ 4     │
# │ 1           ┆ 12725 │
# └─────────────┴───────┘
# 
# Year distribution:
# shape: (2, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 6440  │
# │ 2021 ┆ 6289  │
# └──────┴───────┘
# 
# Year x institution_level cross-tab:
# shape: (8, 3)
# ┌──────┬───────────────────┬──────┐
# │ year ┆ institution_level ┆ len  │
# │ ---  ┆ ---               ┆ ---  │
# │ i64  ┆ i64               ┆ u32  │
# ╞══════╪═══════════════════╪══════╡
# │ 2020 ┆ -1                ┆ 52   │
# │ 2020 ┆ 1                 ┆ 1805 │
# │ 2020 ┆ 2                 ┆ 1685 │
# │ 2020 ┆ 4                 ┆ 2898 │
# │ 2021 ┆ -1                ┆ 16   │
# │ 2021 ┆ 1                 ┆ 1789 │
# │ 2021 ┆ 2                 ┆ 1639 │
# │ 2021 ┆ 4                 ┆ 2845 │
# └──────┴───────────────────┴──────┘
# 
# ============================================================
# QA RESULT: ISSUES_FOUND
# Failed checks: see details above
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
