#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 01
QA Checkpoint: QA1 (Post-Fetch Quality Assessment)

Reviewed script: scripts/stage5_fetch/01_fetch-directory_a.py
Output files: data/raw/2026-02-15_ipeds_directory.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (5 Default):
1. Schema matches Plan expectations
2. Row count within expected range (2,000-3,000)
3. No suspicious distributions (single-value columns, all-zeros)
4. Coded values properly filtered (-1, -2, -3)
5. No nulls in critical columns (unitid, inst_name, inst_control)

Script-Specific Checks (5 Skeptical Lenses):
6. [Counterfactual] What if the year filter failed silently?
7. [Semantic] Does the filter logic serve the research question (exclude for-profit)?
8. [Boundary] Edge cases: zero-enrollment institutions, null institution_level
9. [Absence] What columns are MISSING that the Plan expected?
10. [Downstream] Will downstream joins find the expected unitid keys?

Spot-Checks (5):
11. Trace a known institution (Harvard) to verify its record
12. Verify filter complement: for-profit institutions excluded
13. Verify HBCU count is plausible (~90-100 4-year HBCUs exist)
14. Check state_abbr coverage: all 50 states + DC represented
15. Verify no duplicate unitids exist

Data Profiling section at end for cr2+ decision.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_directory.parquet"

# Plan expectations for Query 1 (IPEDS Directory)
EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "inst_control", "institution_level",
    "hbcu", "degree_granting", "urban_centric_locale", "cc_basic_2021",
    "state_abbr", "fips",
]
# Plan also expected open_admissions and enrollment_undergrad, but the _a.py
# revision documents these are NOT in the directory endpoint.
PLAN_ORIGINALLY_EXPECTED = [
    "unitid", "year", "inst_name", "inst_control", "institution_level",
    "hbcu", "degree_granting", "open_admissions", "urban_centric_locale",
    "cc_basic_2021", "enrollment_undergrad", "state_abbr", "fips",
]

EXPECTED_MIN_ROWS = 2000
EXPECTED_MAX_ROWS = 3000
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 01 (QA1)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# =============================================================================
# DEFAULT CHECKS (5)
# =============================================================================
print("\n" + "=" * 60)
print("DEFAULT CHECKS")
print("=" * 60)

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 - Schema: ", end="")
if schema_ok:
    print("All expected columns present (adjusted for _a.py revision)")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in expected list): {extra_cols}")

# Also note what the Plan originally expected but is absent
plan_missing = [c for c in PLAN_ORIGINALLY_EXPECTED if c not in df.columns]
if plan_missing:
    print(f"  [INFO] Columns in Plan but not in data (documented in _a.py): {plan_missing}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"\n[{'PASS' if rows_ok else 'FAIL'}] Check 2 - Row count: {row_count:,} "
      f"(expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        dist_issues.append(f"{col}: all null")
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"\n[{'PASS' if dist_ok else 'WARN'}] Check 3 - Distributions: ", end="")
if dist_ok:
    print("No single-value or all-zero numeric columns")
else:
    for issue in dist_issues:
        print(f"\n  {issue}")

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
print(f"\n[{'PASS' if coded_ok else 'WARN'}] Check 4 - Coded values: ", end="")
if coded_ok:
    print("No -1/-2/-3 coded values found")
else:
    for issue in coded_issues:
        print(f"\n  {issue}")

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        null_pct = null_count / row_count * 100 if row_count > 0 else 100
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls ({null_pct:.1f}%)")
nulls_ok = len(null_issues) == 0
print(f"\n[{'PASS' if nulls_ok else 'FAIL'}] Check 5 - Critical nulls: ", end="")
if nulls_ok:
    print("No nulls in critical columns (unitid, inst_name, inst_control)")
else:
    for issue in null_issues:
        print(f"\n  {issue}")

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# =============================================================================
print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS (Skeptical Lenses)")
print("=" * 60)

# --- Check 6: [Counterfactual] Year filter verification ---
# What if the year filter failed silently and we got multiple years?
years_in_data = sorted(df["year"].unique().to_list())
year_ok = years_in_data == [2020]
print(f"\n[{'PASS' if year_ok else 'FAIL'}] Check 6 [Counterfactual] - Year filter: ", end="")
if year_ok:
    print(f"Only year 2020 present: {years_in_data}")
else:
    print(f"UNEXPECTED years present: {years_in_data}")

# --- Check 7: [Semantic] Filter logic serves research question ---
# The research question focuses on 4-year public and private nonprofit.
# Verify inst_control has ONLY 1 (public) and 2 (private nonprofit).
# Verify institution_level has ONLY 4 (four-year).
inst_control_vals = sorted(df["inst_control"].drop_nulls().unique().to_list())
inst_level_vals = sorted(df["institution_level"].drop_nulls().unique().to_list())
semantic_ok = (set(inst_control_vals) == {1, 2}) and (inst_level_vals == [4])
print(f"\n[{'PASS' if semantic_ok else 'FAIL'}] Check 7 [Semantic] - Filter logic: ", end="")
if semantic_ok:
    print(f"inst_control={inst_control_vals} (public+nonprofit), "
          f"institution_level={inst_level_vals} (4-year)")
else:
    print(f"inst_control={inst_control_vals}, institution_level={inst_level_vals}")
    if 3 in inst_control_vals:
        print("  BLOCKER: For-profit institutions (3) are present!")

# --- Check 8: [Boundary] Edge cases ---
# Are there institutions with null institution_level or inst_control that slipped through?
null_level = df.filter(pl.col("institution_level").is_null()).shape[0]
null_control = df.filter(pl.col("inst_control").is_null()).shape[0]
boundary_ok = null_level == 0 and null_control == 0
print(f"\n[{'PASS' if boundary_ok else 'WARN'}] Check 8 [Boundary] - Null filter columns: ", end="")
if boundary_ok:
    print("No null values in institution_level or inst_control")
else:
    print(f"null institution_level: {null_level}, null inst_control: {null_control}")

# Check degree_granting: are there non-degree-granting institutions?
dg_values = df["degree_granting"].value_counts().sort("degree_granting")
print(f"  [INFO] degree_granting distribution: {dg_values.to_dict()}")

# --- Check 9: [Absence] What's MISSING that the Plan expected? ---
# Plan Query 1 expected: open_admissions, enrollment_undergrad
# These are documented as missing in the _a.py revision.
# Verify cc_basic_2021 null rate (execution log showed 100% null).
cc_null_count = df["cc_basic_2021"].null_count()
cc_null_pct = cc_null_count / row_count * 100 if row_count > 0 else 0
absence_issues = []
if "open_admissions" not in df.columns:
    absence_issues.append("open_admissions not in dataset (documented in _a.py)")
if "enrollment_undergrad" not in df.columns:
    absence_issues.append("enrollment_undergrad not in dataset (documented in _a.py)")
if cc_null_pct > 50:
    absence_issues.append(f"cc_basic_2021 is {cc_null_pct:.0f}% null (effectively missing)")

# This is expected per the _a.py revision notes, so WARNING not BLOCKER
print(f"\n[{'PASS' if not absence_issues else 'WARN'}] Check 9 [Absence] - Missing Plan columns: ")
for issue in absence_issues:
    print(f"  - {issue}")
if not absence_issues:
    print("  All Plan-expected columns present")

# --- Check 10: [Downstream] Will downstream joins work? ---
# Directory is the BASE table that everything joins TO.
# unitid must be unique (one row per institution for 2020).
# unitid must be non-null.
unitid_unique_count = df["unitid"].n_unique()
unitid_is_unique = unitid_unique_count == row_count
unitid_null_count = df["unitid"].null_count()
downstream_ok = unitid_is_unique and unitid_null_count == 0
print(f"\n[{'PASS' if downstream_ok else 'FAIL'}] Check 10 [Downstream] - Join readiness: ", end="")
if downstream_ok:
    print(f"unitid unique ({unitid_unique_count:,}/{row_count:,}) and non-null")
else:
    if not unitid_is_unique:
        print(f"BLOCKER: unitid not unique ({unitid_unique_count:,} unique / {row_count:,} rows)")
    if unitid_null_count > 0:
        print(f"BLOCKER: unitid has {unitid_null_count} null values")

# =============================================================================
# SPOT-CHECKS (5)
# =============================================================================
print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Trace Harvard University ---
# Harvard (unitid=166027) should be a 4-year private nonprofit (inst_control=2)
harvard = df.filter(pl.col("unitid") == 166027)
harvard_found = harvard.shape[0] == 1
print(f"\n[{'PASS' if harvard_found else 'WARN'}] Spot-Check 11 - Harvard (unitid=166027): ", end="")
if harvard_found:
    h = harvard.row(0, named=True)
    checks = []
    if h["inst_control"] == 2:
        checks.append("inst_control=2 (private nonprofit) CORRECT")
    else:
        checks.append(f"inst_control={h['inst_control']} WRONG (expected 2)")
    if h["institution_level"] == 4:
        checks.append("institution_level=4 (four-year) CORRECT")
    else:
        checks.append(f"institution_level={h['institution_level']} WRONG")
    if h["hbcu"] == 0:
        checks.append("hbcu=0 CORRECT")
    if h["state_abbr"] == "MA":
        checks.append("state_abbr=MA CORRECT")
    else:
        checks.append(f"state_abbr={h['state_abbr']} WRONG (expected MA)")
    print("; ".join(checks))
else:
    print("Harvard NOT FOUND in data — surprising for a 4-year private nonprofit")

# --- Spot-Check 12: Verify filter complement (for-profit excluded) ---
# If inst_control==3 exists, the filter failed. Already checked, but let's
# explicitly verify there are NO for-profit institutions.
forprofit_count = df.filter(pl.col("inst_control") == 3).shape[0]
print(f"\n[{'PASS' if forprofit_count == 0 else 'FAIL'}] Spot-Check 12 - For-profit exclusion: ", end="")
if forprofit_count == 0:
    print("Zero for-profit (inst_control=3) institutions in data")
else:
    print(f"BLOCKER: {forprofit_count} for-profit institutions found!")

# --- Spot-Check 13: HBCU count plausibility ---
# There are approximately 100 4-year HBCUs in the US (both public and private).
hbcu_count = df.filter(pl.col("hbcu") == 1).shape[0]
hbcu_plausible = 70 <= hbcu_count <= 120
print(f"\n[{'PASS' if hbcu_plausible else 'WARN'}] Spot-Check 13 - HBCU count: ", end="")
print(f"{hbcu_count} HBCUs found (expected ~70-120 for 4-year public+private nonprofit)")

# --- Spot-Check 14: State coverage ---
# Expect all 50 states + DC + possibly territories (Guam, PR, VI, AS, MP, MH, FM, PW)
# The IPEDS directory includes US territories. state_abbr should have >= 51.
state_count = df["state_abbr"].n_unique()
has_dc = "DC" in df["state_abbr"].unique().to_list()
print(f"\n[{'PASS' if state_count >= 51 else 'WARN'}] Spot-Check 14 - State coverage: ", end="")
print(f"{state_count} unique state/territory codes. DC present: {has_dc}")
if state_count < 50:
    print("  CONCERN: Fewer than 50 states — possible geography filtering issue")

# --- Spot-Check 15: Duplicate unitid check ---
# Reconfirm no duplicates with explicit duplicate listing
duplicates = df.group_by("unitid").len().filter(pl.col("len") > 1)
dup_count = duplicates.shape[0]
print(f"\n[{'PASS' if dup_count == 0 else 'FAIL'}] Spot-Check 15 - Duplicate unitids: ", end="")
if dup_count == 0:
    print("No duplicate unitids found")
else:
    print(f"BLOCKER: {dup_count} unitids have multiple rows!")
    print(duplicates.head(10))

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("CHECK SUMMARY")
print("=" * 60)

all_checks = {
    "Check 1 - Schema": schema_ok,
    "Check 2 - Row count": rows_ok,
    "Check 3 - Distributions": dist_ok,
    "Check 4 - Coded values": coded_ok,
    "Check 5 - Critical nulls": nulls_ok,
    "Check 6 - Year filter": year_ok,
    "Check 7 - Semantic filter": semantic_ok,
    "Check 8 - Boundary (nulls)": boundary_ok,
    "Check 9 - Absence": len(absence_issues) == 0,
    "Check 10 - Downstream (unitid)": downstream_ok,
    "Spot 11 - Harvard trace": harvard_found,
    "Spot 12 - For-profit exclusion": forprofit_count == 0,
    "Spot 13 - HBCU plausibility": hbcu_plausible,
    "Spot 14 - State coverage": state_count >= 51,
    "Spot 15 - Duplicate unitids": dup_count == 0,
}

passed = sum(v for v in all_checks.values())
total = len(all_checks)
print(f"\nResults: {passed}/{total} passed")
for name, status in all_checks.items():
    print(f"  [{'PASS' if status else 'WARN/FAIL'}] {name}")

# Determine overall severity
has_blocker = (
    not downstream_ok  # unitid issues are blockers
    or not semantic_ok  # wrong filter values are blockers
    or forprofit_count > 0  # for-profit inclusion is blocker
    or not year_ok  # wrong year is blocker
    or dup_count > 0  # duplicates are blocker
)
has_warning = (
    not dist_ok  # distribution issues
    or not coded_ok  # coded values remaining
    or not boundary_ok  # null filter columns
    or len(absence_issues) > 0  # missing Plan columns
)

if has_blocker:
    severity = "BLOCKER"
elif has_warning:
    severity = "WARNING"
else:
    severity = "PASSED"

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
for col in CRITICAL_COLUMNS + ["institution_level", "hbcu", "degree_granting"]:
    if col in df.columns:
        print(f"\n{col}:")
        vc = df[col].value_counts().sort("count", descending=True)
        print(vc.head(20))

print("\nNull count summary per column:")
for col in df.columns:
    nc = df[col].null_count()
    pct = nc / row_count * 100 if row_count > 0 else 0
    flag = " *** HIGH" if pct > 10 else ""
    print(f"  {col}: {nc:,} nulls ({pct:.1f}%){flag}")

print("\nInst_control breakdown:")
print(df.group_by("inst_control").len().sort("inst_control"))

print("\nState_abbr sample (first 20 unique):")
states = sorted(df["state_abbr"].unique().to_list())
print(f"  Total unique: {len(states)}")
print(f"  States: {states}")

print("\nUrban_centric_locale distribution:")
print(df["urban_centric_locale"].value_counts().sort("urban_centric_locale"))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

print("\nunitid range:")
print(f"  min: {df['unitid'].min()}, max: {df['unitid'].max()}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:32:42
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_01_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 01 (QA1)
# ============================================================
# Loaded: 2,528 rows x 11 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'cc_basic_2021', 'state_abbr', 'fips']
# Dtypes: [Int64, Int64, String, Int64, Int64, Int64, Int64, Int64, Int64, String, Int64]
# 
# ============================================================
# DEFAULT CHECKS
# ============================================================
# 
# [PASS] Check 1 - Schema: All expected columns present (adjusted for _a.py revision)
#   [INFO] Columns in Plan but not in data (documented in _a.py): ['open_admissions', 'enrollment_undergrad']
# 
# [PASS] Check 2 - Row count: 2,528 (expected 2,000-3,000)
# 
# [WARN] Check 3 - Distributions: 
#   year: all same value (2020)
# 
#   institution_level: all same value (4)
# 
#   cc_basic_2021: all null
# 
# [WARN] Check 4 - Coded values: 
#   urban_centric_locale has 2 coded value -1
# 
# [PASS] Check 5 - Critical nulls: No nulls in critical columns (unitid, inst_name, inst_control)
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS (Skeptical Lenses)
# ============================================================
# 
# [PASS] Check 6 [Counterfactual] - Year filter: Only year 2020 present: [2020]
# 
# [PASS] Check 7 [Semantic] - Filter logic: inst_control=[1, 2] (public+nonprofit), institution_level=[4] (4-year)
# 
# [PASS] Check 8 [Boundary] - Null filter columns: No null values in institution_level or inst_control
#   [INFO] degree_granting distribution: {'degree_granting': shape: (2,)
# Series: 'degree_granting' [i64]
# [
# 	0
# 	1
# ], 'count': shape: (2,)
# Series: 'count' [u32]
# [
# 	5
# 	2523
# ]}
# 
# [WARN] Check 9 [Absence] - Missing Plan columns: 
#   - open_admissions not in dataset (documented in _a.py)
#   - enrollment_undergrad not in dataset (documented in _a.py)
#   - cc_basic_2021 is 100% null (effectively missing)
# 
# [PASS] Check 10 [Downstream] - Join readiness: unitid unique (2,528/2,528) and non-null
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [PASS] Spot-Check 11 - Harvard (unitid=166027): inst_control=2 (private nonprofit) CORRECT; institution_level=4 (four-year) CORRECT; hbcu=0 CORRECT; state_abbr=MA CORRECT
# 
# [PASS] Spot-Check 12 - For-profit exclusion: Zero for-profit (inst_control=3) institutions in data
# 
# [PASS] Spot-Check 13 - HBCU count: 91 HBCUs found (expected ~70-120 for 4-year public+private nonprofit)
# 
# [PASS] Spot-Check 14 - State coverage: 58 unique state/territory codes. DC present: True
# 
# [PASS] Spot-Check 15 - Duplicate unitids: No duplicate unitids found
# 
# ============================================================
# CHECK SUMMARY
# ============================================================
# 
# Results: 12/15 passed
#   [PASS] Check 1 - Schema
#   [PASS] Check 2 - Row count
#   [WARN/FAIL] Check 3 - Distributions
#   [WARN/FAIL] Check 4 - Coded values
#   [PASS] Check 5 - Critical nulls
#   [PASS] Check 6 - Year filter
#   [PASS] Check 7 - Semantic filter
#   [PASS] Check 8 - Boundary (nulls)
#   [WARN/FAIL] Check 9 - Absence
#   [PASS] Check 10 - Downstream (unitid)
#   [PASS] Spot 11 - Harvard trace
#   [PASS] Spot 12 - For-profit exclusion
#   [PASS] Spot 13 - HBCU plausibility
#   [PASS] Spot 14 - State coverage
#   [PASS] Spot 15 - Duplicate unitids
# 
# QA RESULT: WARNING
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 11)
# ┌────────┬──────┬──────────────┬──────────────┬───┬──────────────┬─────────────┬────────────┬──────┐
# │ unitid ┆ year ┆ inst_name    ┆ inst_control ┆ … ┆ urban_centri ┆ cc_basic_20 ┆ state_abbr ┆ fips │
# │ ---    ┆ ---  ┆ ---          ┆ ---          ┆   ┆ c_locale     ┆ 21          ┆ ---        ┆ ---  │
# │ i64    ┆ i64  ┆ str          ┆ i64          ┆   ┆ ---          ┆ ---         ┆ str        ┆ i64  │
# │        ┆      ┆              ┆              ┆   ┆ i64          ┆ i64         ┆            ┆      │
# ╞════════╪══════╪══════════════╪══════════════╪═══╪══════════════╪═════════════╪════════════╪══════╡
# │ 100654 ┆ 2020 ┆ Alabama A &  ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ M University ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100663 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ at Birmi…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100690 ┆ 2020 ┆ Amridge      ┆ 2            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100706 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ in Hunts…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100724 ┆ 2020 ┆ Alabama      ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ State        ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ …      ┆ …    ┆ …            ┆ …            ┆ … ┆ …            ┆ …           ┆ …          ┆ …    │
# │ 101480 ┆ 2020 ┆ Jacksonville ┆ 1            ┆ … ┆ 23           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ State        ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 101541 ┆ 2020 ┆ Judson       ┆ 2            ┆ … ┆ 43           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ College      ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 101587 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 43           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ of West      ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ Alabama      ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 101675 ┆ 2020 ┆ Miles        ┆ 2            ┆ … ┆ 21           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ College      ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 101693 ┆ 2020 ┆ University   ┆ 2            ┆ … ┆ 41           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ of Mobile    ┆              ┆   ┆              ┆             ┆            ┆      │
# └────────┴──────┴──────────────┴──────────────┴───┴──────────────┴─────────────┴────────────┴──────┘
# 
# Descriptive statistics:
# shape: (9, 12)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ inst_name ┆ … ┆ urban_cen ┆ cc_basic_ ┆ state_abb ┆ fips      │
# │ ---        ┆ ---        ┆ ---    ┆ ---       ┆   ┆ tric_loca ┆ 2021      ┆ r         ┆ ---       │
# │ str        ┆ f64        ┆ f64    ┆ str       ┆   ┆ le        ┆ ---       ┆ ---       ┆ f64       │
# │            ┆            ┆        ┆           ┆   ┆ ---       ┆ f64       ┆ str       ┆           │
# │            ┆            ┆        ┆           ┆   ┆ f64       ┆           ┆           ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 2528.0     ┆ 2528.0 ┆ 2528      ┆ … ┆ 2528.0    ┆ 0.0       ┆ 2528      ┆ 2528.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0         ┆ … ┆ 0.0       ┆ 2528.0    ┆ 0         ┆ 0.0       │
# │ mean       ┆ 220569.164 ┆ 2020.0 ┆ null      ┆ … ┆ 19.625    ┆ null      ┆ null      ┆ 30.374209 │
# │            ┆ 161        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ std        ┆ 103707.401 ┆ 0.0    ┆ null      ┆ … ┆ 9.64483   ┆ null      ┆ null      ┆ 16.613986 │
# │            ┆ 134        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ A T Still ┆ … ┆ -1.0      ┆ null      ┆ AK        ┆ 1.0       │
# │            ┆            ┆        ┆ Universit ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ y of      ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ Health…   ┆   ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 155089.0   ┆ 2020.0 ┆ null      ┆ … ┆ 11.0      ┆ null      ┆ null      ┆ 17.0      │
# │ 50%        ┆ 196121.0   ┆ 2020.0 ┆ null      ┆ … ┆ 13.0      ┆ null      ┆ null      ┆ 33.0      │
# │ 75%        ┆ 230597.0   ┆ 2020.0 ┆ null      ┆ … ┆ 23.0      ┆ null      ┆ null      ┆ 42.0      │
# │ max        ┆ 496070.0   ┆ 2020.0 ┆ Zaytuna   ┆ … ┆ 43.0      ┆ null      ┆ WY        ┆ 78.0      │
# │            ┆            ┆        ┆ College   ┆   ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
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
# │ 234915 ┆ 1     │
# │ 115214 ┆ 1     │
# │ 168254 ┆ 1     │
# │ 153250 ┆ 1     │
# │ 204705 ┆ 1     │
# │ …      ┆ …     │
# │ 239105 ┆ 1     │
# │ 441131 ┆ 1     │
# │ 192323 ┆ 1     │
# │ 192712 ┆ 1     │
# │ 484905 ┆ 1     │
# └────────┴───────┘
# 
# inst_name:
# shape: (20, 2)
# ┌─────────────────────────────────┬───────┐
# │ inst_name                       ┆ count │
# │ ---                             ┆ ---   │
# │ str                             ┆ u32   │
# ╞═════════════════════════════════╪═══════╡
# │ Stevens-Henager College         ┆ 6     │
# │ Union College                   ┆ 3     │
# │ Bethel University               ┆ 3     │
# │ Westminster College             ┆ 3     │
# │ Lincoln University              ┆ 3     │
# │ …                               ┆ …     │
# │ Anderson University             ┆ 2     │
# │ Marian University               ┆ 2     │
# │ California State University-Do… ┆ 1     │
# │ National Louis University       ┆ 1     │
# │ The University of West Florida  ┆ 1     │
# └─────────────────────────────────┴───────┘
# 
# inst_control:
# shape: (2, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 2            ┆ 1676  │
# │ 1            ┆ 852   │
# └──────────────┴───────┘
# 
# institution_level:
# shape: (1, 2)
# ┌───────────────────┬───────┐
# │ institution_level ┆ count │
# │ ---               ┆ ---   │
# │ i64               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ 4                 ┆ 2528  │
# └───────────────────┴───────┘
# 
# hbcu:
# shape: (2, 2)
# ┌──────┬───────┐
# │ hbcu ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 0    ┆ 2437  │
# │ 1    ┆ 91    │
# └──────┴───────┘
# 
# degree_granting:
# shape: (2, 2)
# ┌─────────────────┬───────┐
# │ degree_granting ┆ count │
# │ ---             ┆ ---   │
# │ i64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 1               ┆ 2523  │
# │ 0               ┆ 5     │
# └─────────────────┴───────┘
# 
# Null count summary per column:
#   unitid: 0 nulls (0.0%)
#   year: 0 nulls (0.0%)
#   inst_name: 0 nulls (0.0%)
#   inst_control: 0 nulls (0.0%)
#   institution_level: 0 nulls (0.0%)
#   hbcu: 0 nulls (0.0%)
#   degree_granting: 0 nulls (0.0%)
#   urban_centric_locale: 0 nulls (0.0%)
#   cc_basic_2021: 2,528 nulls (100.0%) *** HIGH
#   state_abbr: 0 nulls (0.0%)
#   fips: 0 nulls (0.0%)
# 
# Inst_control breakdown:
# shape: (2, 2)
# ┌──────────────┬──────┐
# │ inst_control ┆ len  │
# │ ---          ┆ ---  │
# │ i64          ┆ u32  │
# ╞══════════════╪══════╡
# │ 1            ┆ 852  │
# │ 2            ┆ 1676 │
# └──────────────┴──────┘
# 
# State_abbr sample (first 20 unique):
#   Total unique: 58
#   States: ['AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'FM', 'GA', 'GU', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MH', 'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VI', 'VT', 'WA', 'WI', 'WV', 'WY']
# 
# Urban_centric_locale distribution:
# shape: (13, 2)
# ┌──────────────────────┬───────┐
# │ urban_centric_locale ┆ count │
# │ ---                  ┆ ---   │
# │ i64                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ -1                   ┆ 2     │
# │ 11                   ┆ 645   │
# │ 12                   ┆ 305   │
# │ 13                   ┆ 344   │
# │ 21                   ┆ 511   │
# │ …                    ┆ …     │
# │ 32                   ┆ 218   │
# │ 33                   ┆ 135   │
# │ 41                   ┆ 101   │
# │ 42                   ┆ 43    │
# │ 43                   ┆ 31    │
# └──────────────────────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 2528  │
# └──────┴───────┘
# 
# unitid range:
#   min: 100654, max: 496070
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
