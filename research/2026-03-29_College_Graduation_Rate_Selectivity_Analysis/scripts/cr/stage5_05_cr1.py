#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 1.5

Reviewed script: scripts/stage5_fetch/05_fetch-enrollment-race.py
Output files: data/raw/2026-03-29_ipeds_enrollment_race.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range (30,000-70,000)
3. No suspicious distributions
4. Coded values properly filtered (enrollment_fall should NOT contain -1/-2/-3)
5. No nulls in critical columns (unitid, year, race)
6. Dimension filters verified: sex==99, ftpt==99, level_of_study==1, degree_seeking==99, class_level==99
7. Counterfactual: what if a dimension column is missing?
8. Semantic: does race coverage support downstream URM computation?
9. Boundary: zero enrollment values and extreme values
10. Absence: are any expected race codes missing for any institution?
11. Downstream: will the cleaning script (Task 3.5) receive what it expects?
Plus 5 concrete spot-checks.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_enrollment_race.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "fips", "sex", "race", "ftpt", "level_of_study", "degree_seeking", "class_level", "enrollment_fall"]
EXPECTED_MIN_ROWS = 30000
EXPECTED_MAX_ROWS = 70000
CRITICAL_COLUMNS = ["unitid", "year", "race", "enrollment_fall"]
CODED_MISSING_VALUES = [-1, -2, -3]

# Dimension filter values that should be constant across all rows
EXPECTED_DIMENSION_VALUES = {
    "sex": 99,
    "ftpt": 99,
    "level_of_study": 1,
    "degree_seeking": 99,
    "class_level": 99,
}

# Race codes per Plan.md
EXPECTED_RACE_CODES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# URM codes per Plan.md: Black(2), Hispanic(3), AIAN(5), NHPI(6)
URM_CODES = [2, 3, 5, 6]
# Domestic known-race codes per Plan.md (1-7)
DOMESTIC_KNOWN_RACE_CODES = [1, 2, 3, 4, 5, 6, 7]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 1.5 — fetch-enrollment-race")
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
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

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
print(f"[{'PASS' if dist_ok else 'WARN'}] Distributions: ", end="")
if dist_ok:
    print("Look reasonable")
else:
    for issue in dist_issues:
        print(f"  {issue}")

# --- Check 4: Coded values in enrollment_fall ---
coded_issues = []
if CODED_MISSING_VALUES:
    for col in ["enrollment_fall"]:
        if col in df.columns and df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            for code in CODED_MISSING_VALUES:
                count = (df[col] == code).sum()
                if count > 0:
                    coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values in enrollment_fall: ", end="")
if coded_ok:
    print("None remain (-1/-2/-3 absent)")
else:
    for issue in coded_issues:
        print(f"  {issue}")

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

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# ==========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: DIMENSION FILTER VERIFICATION (Critical) ---
# INTENT: Verify that ALL dimension filters were applied correctly. This is the
# most critical check for this script — wrong filters mean wrong URM shares
# downstream, corrupting the entire analysis.
print("\n--- Dimension Filter Verification ---")
dim_filter_ok = True
for col, expected_val in EXPECTED_DIMENSION_VALUES.items():
    if col not in df.columns:
        print(f"  [FAIL] Column '{col}' not in data — filter could not have been applied")
        dim_filter_ok = False
        continue
    unique_vals = sorted(df[col].unique().to_list())
    if unique_vals == [expected_val]:
        print(f"  [PASS] {col}: only value is {expected_val} (correct)")
    else:
        print(f"  [FAIL] {col}: values are {unique_vals} (expected only [{expected_val}])")
        dim_filter_ok = False

# --- Check 7: COUNTERFACTUAL — What if dimension columns had mixed values? ---
# INTENT: Verify the data is truly collapsed to the expected level. If multiple
# dimension values leak through, the same institution would appear multiple times
# per race, inflating enrollment counts.
print("\n--- Counterfactual: Cardinality per (unitid, race) ---")
if "unitid" in df.columns and "race" in df.columns:
    cardinality = df.group_by(["unitid", "race"]).len()
    max_card = cardinality["len"].max()
    multi_rows = (cardinality["len"] > 1).sum()
    card_ok = max_card == 1
    print(f"  [{'PASS' if card_ok else 'FAIL'}] Max rows per (unitid, race): {max_card}")
    if multi_rows > 0:
        print(f"  WARNING: {multi_rows} (unitid, race) pairs have >1 row — dimension filter leak!")
else:
    card_ok = False
    print("  [FAIL] Cannot check cardinality — missing unitid or race column")

# --- Check 8: SEMANTIC — Race codes support downstream URM computation ---
# INTENT: The downstream cleaning script (Task 3.5) needs race codes 2,3,5,6 for
# URM numerator and 1-7 for domestic denominator. Verify these are all present.
print("\n--- Semantic: Race codes for URM computation ---")
if "race" in df.columns:
    actual_race_codes = sorted(df["race"].unique().to_list())
    urm_present = all(c in actual_race_codes for c in URM_CODES)
    domestic_present = all(c in actual_race_codes for c in DOMESTIC_KNOWN_RACE_CODES)
    total_present = 99 in actual_race_codes
    print(f"  [{'PASS' if urm_present else 'FAIL'}] URM codes (2,3,5,6) all present: {urm_present}")
    print(f"  [{'PASS' if domestic_present else 'FAIL'}] Domestic known-race codes (1-7) all present: {domestic_present}")
    print(f"  [{'PASS' if total_present else 'FAIL'}] Total code (99) present: {total_present}")
    print(f"  Actual race codes: {actual_race_codes}")
else:
    urm_present = domestic_present = total_present = False
    print("  [FAIL] Race column not found")

# --- Check 9: BOUNDARY — Zeros, negatives, extreme enrollment values ---
# INTENT: Check for boundary conditions in enrollment_fall that could corrupt
# downstream URM share calculations. Zeros are OK (institutions may have zero
# enrollment in some race categories) but negatives would indicate coding errors.
print("\n--- Boundary: enrollment_fall extremes ---")
if "enrollment_fall" in df.columns:
    enroll = df["enrollment_fall"]
    neg_count = (enroll < 0).sum()
    zero_count = (enroll == 0).sum()
    very_large = (enroll > 100000).sum()
    pct_zero = zero_count / len(df) * 100

    neg_ok = neg_count == 0
    print(f"  [{'PASS' if neg_ok else 'FAIL'}] Negative enrollment values: {neg_count}")
    print(f"  [INFO] Zero enrollment values: {zero_count} ({pct_zero:.1f}% of rows)")
    print(f"  [INFO] Very large enrollment (>100K): {very_large}")
    print(f"  [INFO] Min={enroll.min()}, Max={enroll.max()}, Median={enroll.median()}")
else:
    neg_ok = False
    print("  [FAIL] enrollment_fall column not found")

# --- Check 10: ABSENCE — Are any institutions missing expected race categories? ---
# INTENT: If an institution has data for some races but not others, the URM share
# computation downstream may be biased. Check how many institutions have all 10
# race codes vs. fewer.
print("\n--- Absence: Institution coverage by race code ---")
if "unitid" in df.columns and "race" in df.columns:
    inst_race_count = df.group_by("unitid").agg(pl.col("race").n_unique().alias("n_race_codes"))
    n_institutions = inst_race_count.shape[0]
    full_coverage = (inst_race_count["n_race_codes"] == 10).sum()
    partial = (inst_race_count["n_race_codes"] < 10).sum()
    pct_full = full_coverage / n_institutions * 100

    print(f"  Total institutions: {n_institutions:,}")
    print(f"  [INFO] Full race coverage (all 10 codes): {full_coverage:,} ({pct_full:.1f}%)")
    print(f"  [INFO] Partial race coverage (<10 codes): {partial:,} ({100-pct_full:.1f}%)")

    if partial > 0:
        # Show the distribution of race code counts for partial institutions
        partial_dist = inst_race_count.filter(pl.col("n_race_codes") < 10)["n_race_codes"].value_counts().sort("n_race_codes")
        print(f"  Partial coverage distribution:")
        for row in partial_dist.iter_rows(named=True):
            print(f"    {row['n_race_codes']} race codes: {row['count']} institutions")
else:
    print("  [FAIL] Cannot check — missing unitid or race column")

# --- Check 11: DOWNSTREAM — Will Task 3.5 cleaning script get what it expects? ---
# INTENT: Task 3.5 needs to compute urm_share = sum(enrollment_fall for race in
# 2,3,5,6) / sum(enrollment_fall for race in 1-7). It also needs race==99 for
# total_ug_enrollment. Verify the data structure supports this.
print("\n--- Downstream: Readiness for Task 3.5 (clean-enrollment-race) ---")
downstream_ok = True

# Check 1: rows with race==99 exist per institution (for total_ug_enrollment)
if "race" in df.columns and "unitid" in df.columns:
    race99_count = df.filter(pl.col("race") == 99).shape[0]
    n_inst_with_99 = df.filter(pl.col("race") == 99)["unitid"].n_unique()
    all_inst = df["unitid"].n_unique()
    pct_with_99 = n_inst_with_99 / all_inst * 100
    has_99_ok = pct_with_99 > 95
    print(f"  [{'PASS' if has_99_ok else 'WARN'}] Institutions with race==99: {n_inst_with_99:,}/{all_inst:,} ({pct_with_99:.1f}%)")
    if not has_99_ok:
        downstream_ok = False
else:
    print("  [FAIL] Cannot check race==99 coverage")
    downstream_ok = False

# Check 2: year should be exclusively 2020
if "year" in df.columns:
    years = sorted(df["year"].unique().to_list())
    year_ok = years == [2020]
    print(f"  [{'PASS' if year_ok else 'FAIL'}] Year is exclusively [2020]: {years}")
    if not year_ok:
        downstream_ok = False
else:
    print("  [FAIL] Year column not found")
    downstream_ok = False

# ==========================================================================
# SPOT CHECKS (5 concrete validations)
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT CHECKS")
print("=" * 60)

# Spot-Check 1: Verify rows-per-race-code are balanced
# If filters are correct, each race code should have the same number of rows
# (one per institution).
print("\n--- Spot-Check 1: Rows per race code (should be balanced) ---")
if "race" in df.columns:
    race_counts = df.group_by("race").len().sort("race")
    race_lens = race_counts["len"].to_list()
    balanced = len(set(race_lens)) == 1
    print(f"  [{'PASS' if balanced else 'WARN'}] All race codes have same row count: {balanced}")
    for row in race_counts.iter_rows(named=True):
        print(f"    Race {row['race']}: {row['len']:,} rows")

# Spot-Check 2: Pick a specific known large institution (e.g., unitid for a major
# university) and verify its enrollment looks reasonable
print("\n--- Spot-Check 2: Trace a known institution ---")
# Use race==99 (total) to find a large institution
if "enrollment_fall" in df.columns and "unitid" in df.columns and "race" in df.columns:
    large_inst = df.filter(pl.col("race") == 99).sort("enrollment_fall", descending=True).head(5)
    print(f"  Top 5 institutions by total enrollment (race==99):")
    for row in large_inst.iter_rows(named=True):
        print(f"    unitid={row['unitid']}: enrollment_fall={row['enrollment_fall']:,}")

    # Pick the largest and verify its race breakdown sums to total
    top_unitid = large_inst["unitid"][0]
    top_total = large_inst["enrollment_fall"][0]
    top_inst_races = df.filter(
        (pl.col("unitid") == top_unitid) & (pl.col("race") != 99)
    )
    race_sum = top_inst_races["enrollment_fall"].sum()
    total_match = abs(race_sum - top_total) <= 1  # Allow rounding
    print(f"\n  Verification for top institution (unitid={top_unitid}):")
    print(f"    Total (race==99): {top_total:,}")
    print(f"    Sum of race codes 1-9: {race_sum:,}")
    print(f"    [{'PASS' if total_match else 'WARN'}] Sum matches total: {total_match}")

# Spot-Check 3: Verify that filter complement was applied — check that the
# dimension columns ONLY contain the expected filter values
print("\n--- Spot-Check 3: Filter complement (only expected values remain) ---")
for col, expected_val in EXPECTED_DIMENSION_VALUES.items():
    if col in df.columns:
        other_vals = df.filter(pl.col(col) != expected_val).shape[0]
        print(f"  [{'PASS' if other_vals == 0 else 'FAIL'}] {col}: {other_vals} rows with value != {expected_val}")

# Spot-Check 4: Cross-reference institution count with expected population
# Plan.md expects ~4,000-7,000 institutions for enrollment race data
print("\n--- Spot-Check 4: Institution count vs Plan expectation ---")
if "unitid" in df.columns:
    n_inst = df["unitid"].n_unique()
    inst_range_ok = 4000 <= n_inst <= 7000
    print(f"  [{'PASS' if inst_range_ok else 'WARN'}] Unique institutions: {n_inst:,} (expected 4,000-7,000)")

# Spot-Check 5: Check that no institution has unreasonable total enrollment
# A single institution should not have >200,000 UG enrollment
print("\n--- Spot-Check 5: Extreme enrollment sanity check ---")
if "enrollment_fall" in df.columns and "race" in df.columns and "unitid" in df.columns:
    totals = df.filter(pl.col("race") == 99)
    extreme = totals.filter(pl.col("enrollment_fall") > 200000)
    extreme_ok = extreme.shape[0] == 0
    print(f"  [{'PASS' if extreme_ok else 'WARN'}] Institutions with enrollment > 200,000: {extreme.shape[0]}")
    if not extreme_ok:
        for row in extreme.iter_rows(named=True):
            print(f"    unitid={row['unitid']}: {row['enrollment_fall']:,}")

# ==========================================================================
# DATA PROFILING (for cr2+ decision)
# ==========================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nColumn types:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort("count", descending=True).head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

if "enrollment_fall" in df.columns:
    print("\nEnrollment percentiles:")
    for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
        val = df["enrollment_fall"].quantile(q)
        print(f"  {q*100:.0f}th percentile: {val:,.0f}")

# ==========================================================================
# SUMMARY
# ==========================================================================

print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

all_critical = all([schema_ok, rows_ok, coded_ok, nulls_ok, dim_filter_ok, card_ok, neg_ok])
has_warnings = not all([dist_ok, downstream_ok])

if all_critical:
    severity = "PASSED"
elif not all_critical:
    severity = "BLOCKER"
else:
    severity = "WARNING"

print(f"QA RESULT: {severity}")
print(f"  Schema:             {'PASS' if schema_ok else 'FAIL'}")
print(f"  Row count:          {'PASS' if rows_ok else 'FAIL'}")
print(f"  Coded values:       {'PASS' if coded_ok else 'FAIL'}")
print(f"  Critical nulls:     {'PASS' if nulls_ok else 'FAIL'}")
print(f"  Dimension filters:  {'PASS' if dim_filter_ok else 'FAIL'}")
print(f"  Cardinality (1:1):  {'PASS' if card_ok else 'FAIL'}")
print(f"  No negatives:       {'PASS' if neg_ok else 'FAIL'}")
print(f"  Race codes for URM: {'PASS' if urm_present else 'FAIL'}")
print(f"  Distribution:       {'PASS' if dist_ok else 'WARN'}")
print(f"  Downstream ready:   {'PASS' if downstream_ok else 'WARN'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:07:52
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_05_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 1.5 — fetch-enrollment-race
# ============================================================
# Loaded: 58,370 rows x 10 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 58,370 (expected 30,000-70,000)
# [WARN] Distributions:   year: all same value (2020)
#   sex: all same value (99)
#   ftpt: all same value (99)
#   level_of_study: all same value (1)
#   degree_seeking: all same value (99)
#   class_level: all same value (99)
# [PASS] Coded values in enrollment_fall: None remain (-1/-2/-3 absent)
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Dimension Filter Verification ---
#   [PASS] sex: only value is 99 (correct)
#   [PASS] ftpt: only value is 99 (correct)
#   [PASS] level_of_study: only value is 1 (correct)
#   [PASS] degree_seeking: only value is 99 (correct)
#   [PASS] class_level: only value is 99 (correct)
# 
# --- Counterfactual: Cardinality per (unitid, race) ---
#   [PASS] Max rows per (unitid, race): 1
# 
# --- Semantic: Race codes for URM computation ---
#   [PASS] URM codes (2,3,5,6) all present: True
#   [PASS] Domestic known-race codes (1-7) all present: True
#   [PASS] Total code (99) present: True
#   Actual race codes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# 
# --- Boundary: enrollment_fall extremes ---
#   [PASS] Negative enrollment values: 0
#   [INFO] Zero enrollment values: 13394 (22.9% of rows)
#   [INFO] Very large enrollment (>100K): 2
#   [INFO] Min=0, Max=111599, Median=18.0
# 
# --- Absence: Institution coverage by race code ---
#   Total institutions: 5,837
#   [INFO] Full race coverage (all 10 codes): 5,837 (100.0%)
#   [INFO] Partial race coverage (<10 codes): 0 (0.0%)
# 
# --- Downstream: Readiness for Task 3.5 (clean-enrollment-race) ---
#   [PASS] Institutions with race==99: 5,837/5,837 (100.0%)
#   [PASS] Year is exclusively [2020]: [2020]
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# --- Spot-Check 1: Rows per race code (should be balanced) ---
#   [PASS] All race codes have same row count: True
#     Race 1: 5,837 rows
#     Race 2: 5,837 rows
#     Race 3: 5,837 rows
#     Race 4: 5,837 rows
#     Race 5: 5,837 rows
#     Race 6: 5,837 rows
#     Race 7: 5,837 rows
#     Race 8: 5,837 rows
#     Race 9: 5,837 rows
#     Race 99: 5,837 rows
# 
# --- Spot-Check 2: Trace a known institution ---
#   Top 5 institutions by total enrollment (race==99):
#     unitid=183026: enrollment_fall=111,599
#     unitid=433387: enrollment_fall=104,919
#     unitid=224615: enrollment_fall=74,781
#     unitid=495767: enrollment_fall=74,446
#     unitid=227182: enrollment_fall=70,109
# 
#   Verification for top institution (unitid=183026):
#     Total (race==99): 111,599
#     Sum of race codes 1-9: 111,599
#     [PASS] Sum matches total: True
# 
# --- Spot-Check 3: Filter complement (only expected values remain) ---
#   [PASS] sex: 0 rows with value != 99
#   [PASS] ftpt: 0 rows with value != 99
#   [PASS] level_of_study: 0 rows with value != 1
#   [PASS] degree_seeking: 0 rows with value != 99
#   [PASS] class_level: 0 rows with value != 99
# 
# --- Spot-Check 4: Institution count vs Plan expectation ---
#   [PASS] Unique institutions: 5,837 (expected 4,000-7,000)
# 
# --- Spot-Check 5: Extreme enrollment sanity check ---
#   [PASS] Institutions with enrollment > 200,000: 0
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 10)
# ┌────────┬──────┬──────┬─────┬───┬────────────────┬────────────────┬─────────────┬─────────────────┐
# │ unitid ┆ year ┆ fips ┆ sex ┆ … ┆ level_of_study ┆ degree_seeking ┆ class_level ┆ enrollment_fall │
# │ ---    ┆ ---  ┆ ---  ┆ --- ┆   ┆ ---            ┆ ---            ┆ ---         ┆ ---             │
# │ i64    ┆ i64  ┆ i64  ┆ i64 ┆   ┆ i64            ┆ i64            ┆ i64         ┆ i64             │
# ╞════════╪══════╪══════╪═════╪═══╪════════════════╪════════════════╪═════════════╪═════════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 4               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 73              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 81              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 6               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 37              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 14              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 224             │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 59              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 4595            │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 1              ┆ 99             ┆ 99          ┆ 5093            │
# └────────┴──────┴──────┴─────┴───┴────────────────┴────────────────┴─────────────┴─────────────────┘
# 
# Descriptive statistics:
# shape: (9, 11)
# ┌────────────┬───────────┬─────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid    ┆ year    ┆ fips      ┆ … ┆ level_of_ ┆ degree_se ┆ class_lev ┆ enrollmen │
# │ ---        ┆ ---       ┆ ---     ┆ ---       ┆   ┆ study     ┆ eking     ┆ el        ┆ t_fall    │
# │ str        ┆ f64       ┆ f64     ┆ f64       ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---       │
# │            ┆           ┆         ┆           ┆   ┆ f64       ┆ f64       ┆ f64       ┆ f64       │
# ╞════════════╪═══════════╪═════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 58370.0   ┆ 58370.0 ┆ 58370.0   ┆ … ┆ 58370.0   ┆ 58370.0   ┆ 58370.0   ┆ 58370.0   │
# │ null_count ┆ 0.0       ┆ 0.0     ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0       │
# │ mean       ┆ 283873.48 ┆ 2020.0  ┆ 29.326538 ┆ … ┆ 1.0       ┆ 99.0      ┆ 99.0      ┆ 563.48871 │
# │            ┆ 3981      ┆         ┆           ┆   ┆           ┆           ┆           ┆           │
# │ std        ┆ 137924.15 ┆ 0.0     ┆ 16.828036 ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 2530.8495 │
# │            ┆ 5554      ┆         ┆           ┆   ┆           ┆           ┆           ┆ 87        │
# │ min        ┆ 100654.0  ┆ 2020.0  ┆ 1.0       ┆ … ┆ 1.0       ┆ 99.0      ┆ 99.0      ┆ 0.0       │
# │ 25%        ┆ 169734.0  ┆ 2020.0  ┆ 13.0      ┆ … ┆ 1.0       ┆ 99.0      ┆ 99.0      ┆ 1.0       │
# │ 50%        ┆ 219921.0  ┆ 2020.0  ┆ 30.0      ┆ … ┆ 1.0       ┆ 99.0      ┆ 99.0      ┆ 18.0      │
# │ 75%        ┆ 445267.0  ┆ 2020.0  ┆ 42.0      ┆ … ┆ 1.0       ┆ 99.0      ┆ 99.0      ┆ 150.0     │
# │ max        ┆ 496423.0  ┆ 2020.0  ┆ 78.0      ┆ … ┆ 1.0       ┆ 99.0      ┆ 99.0      ┆ 111599.0  │
# └────────────┴───────────┴─────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Column types:
#   unitid: Int64
#   year: Int64
#   fips: Int64
#   sex: Int64
#   race: Int64
#   ftpt: Int64
#   level_of_study: Int64
#   degree_seeking: Int64
#   class_level: Int64
#   enrollment_fall: Int64
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
# │ 430795 ┆ 10    │
# │ 234137 ┆ 10    │
# │ 494834 ┆ 10    │
# │ 365374 ┆ 10    │
# │ 449083 ┆ 10    │
# │ …      ┆ …     │
# │ 428055 ┆ 10    │
# │ 203748 ┆ 10    │
# │ 495299 ┆ 10    │
# │ 458210 ┆ 10    │
# │ 183655 ┆ 10    │
# └────────┴───────┘
# 
# year:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 58370 │
# └──────┴───────┘
# 
# race:
# shape: (10, 2)
# ┌──────┬───────┐
# │ race ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 4    ┆ 5837  │
# │ 99   ┆ 5837  │
# │ 2    ┆ 5837  │
# │ 3    ┆ 5837  │
# │ 5    ┆ 5837  │
# │ 8    ┆ 5837  │
# │ 1    ┆ 5837  │
# │ 9    ┆ 5837  │
# │ 6    ┆ 5837  │
# │ 7    ┆ 5837  │
# └──────┴───────┘
# 
# enrollment_fall:
# shape: (20, 2)
# ┌─────────────────┬───────┐
# │ enrollment_fall ┆ count │
# │ ---             ┆ ---   │
# │ i64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 0               ┆ 13394 │
# │ 1               ┆ 3151  │
# │ 2               ┆ 2093  │
# │ 3               ┆ 1555  │
# │ 4               ┆ 1279  │
# │ …               ┆ …     │
# │ 16              ┆ 398   │
# │ 15              ┆ 394   │
# │ 17              ┆ 350   │
# │ 18              ┆ 339   │
# │ 20              ┆ 304   │
# └─────────────────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 58370 │
# └──────┴───────┘
# 
# Enrollment percentiles:
#   1th percentile: 0
#   5th percentile: 0
#   10th percentile: 0
#   25th percentile: 1
#   50th percentile: 18
#   75th percentile: 150
#   90th percentile: 999
#   95th percentile: 2,583
#   99th percentile: 10,705
# 
# ============================================================
# QA SUMMARY
# ============================================================
# QA RESULT: PASSED
#   Schema:             PASS
#   Row count:          PASS
#   Coded values:       PASS
#   Critical nulls:     PASS
#   Dimension filters:  PASS
#   Cardinality (1:1):  PASS
#   No negatives:       PASS
#   Race codes for URM: PASS
#   Distribution:       WARN
#   Downstream ready:   PASS
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
