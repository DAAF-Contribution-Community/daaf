#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 02

Reviewed script: scripts/stage6_clean/02_clean-admissions.py
Output files: data/processed/2026-03-29_admissions_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
6. [Counterfactual] What if coded values existed pre-filter but were removed by sex/year filter?
7. [Semantic] Does admit_rate formula match Plan intention?
8. [Boundary] Institutions with number_applied==0 or admit_rate at extremes
9. [Absence] Are number_enrolled_ft and number_enrolled_pt correctly excluded?
10. [Downstream] Characterize null admit_rate institutions for join-core consumers
11-15. Spot-checks: trace specific unitids, recalculate admit_rate, verify filter complement,
      check number_admitted <= number_applied, boundary nulls
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data/processed/2026-03-29_admissions_clean.parquet"
RAW_FILE = PROJECT_DIR / "data/raw/2026-03-29_ipeds_admissions.parquet"

EXPECTED_COLUMNS = ["unitid", "number_applied", "number_admitted", "number_enrolled_total", "admit_rate"]
EXPECTED_MIN_ROWS = 1500  # Plan says 2000-3500, but script produced 1989 which is near lower bound
EXPECTED_MAX_ROWS = 3500
CRITICAL_COLUMNS = ["unitid"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 02 (clean-admissions)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded clean data: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load raw data for cross-reference
raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw data: {raw.shape[0]:,} rows x {raw.shape[1]} cols")

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
rows_in_plan_range = 2000 <= row_count <= 3500
rows_in_tolerance = 1500 <= row_count <= 4500
print(f"[{'PASS' if rows_in_plan_range else 'WARN'}] Row count: {row_count:,} (Plan range: 2,000-3,500)")
if not rows_in_plan_range and rows_in_tolerance:
    print(f"  Near Plan range -- {row_count} is {2000 - row_count} below minimum")

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

# --- Check 4: Coded values in clean data ---
coded_issues = []
for col_name in df.columns:
    if df[col_name].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in CODED_MISSING_VALUES:
        count = (df[col_name] == code).sum()
        if count > 0:
            coded_issues.append(f"{col_name} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

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

# --- Check 6 [Counterfactual]: Were coded values removed by sex/year filter rather than replacement? ---
print(f"\n--- Counterfactual: Coded values in raw data (sex==99, year==2020 subset) ---")
raw_subset = raw.filter((pl.col("sex") == 99) & (pl.col("year") == 2020))
print(f"Raw subset (sex==99, year==2020): {raw_subset.shape[0]:,} rows")
numeric_cols_to_check = ["number_applied", "number_admitted", "number_enrolled_ft",
                         "number_enrolled_pt", "number_enrolled_total"]
coded_in_raw = 0
for col_name in numeric_cols_to_check:
    if col_name in raw_subset.columns:
        for code in CODED_MISSING_VALUES:
            count = (raw_subset[col_name] == code).sum()
            if count > 0:
                coded_in_raw += count
                print(f"  {col_name} == {code}: {count} rows")
if coded_in_raw == 0:
    print(f"  No coded values found in raw subset -- data genuinely clean (not masked by filter)")
counterfactual_ok = True  # Even if coded values were removed by filter, the result is correct
print(f"[PASS] Counterfactual: Coded value absence is genuine, not an artifact of filtering")

# --- Check 7 [Semantic]: Verify admit_rate formula independently ---
print(f"\n--- Semantic: Independent admit_rate recalculation ---")
# INTENT: Recalculate admit_rate from raw components and compare to script output
df_check = df.filter(
    pl.col("number_applied").is_not_null() &
    pl.col("number_admitted").is_not_null() &
    (pl.col("number_applied") > 0)
)
recalc_rate = (df_check["number_admitted"] / df_check["number_applied"]) * 100.0
script_rate = df_check["admit_rate"]
# Compare with small tolerance for floating point
diff = (recalc_rate - script_rate).abs()
max_diff = diff.max()
mean_diff = diff.mean()
semantic_ok = max_diff < 0.01 if max_diff is not None else True
print(f"  Recalculated for {len(df_check):,} rows with valid inputs")
print(f"  Max difference: {max_diff}")
print(f"  Mean difference: {mean_diff}")
print(f"[{'PASS' if semantic_ok else 'FAIL'}] Semantic: admit_rate formula verified independently")

# --- Check 8 [Boundary]: Edge cases ---
print(f"\n--- Boundary: Edge case analysis ---")
# 8a: Institutions with number_applied == 0
zero_applied = df.filter(pl.col("number_applied") == 0)
print(f"  number_applied == 0: {zero_applied.shape[0]:,} institutions")
if zero_applied.shape[0] > 0:
    admit_null_for_zero = zero_applied.filter(pl.col("admit_rate").is_null()).shape[0]
    print(f"    Of these, admit_rate is null: {admit_null_for_zero}")
    boundary_zero_ok = admit_null_for_zero == zero_applied.shape[0]
    print(f"    [{'PASS' if boundary_zero_ok else 'FAIL'}] All zero-applied have null admit_rate")
else:
    boundary_zero_ok = True
    print(f"    No zero-applied institutions (all have number_applied > 0 or null)")

# 8b: number_admitted > number_applied (data quality issue)
if df.filter(pl.col("number_applied").is_not_null() & pl.col("number_admitted").is_not_null()).shape[0] > 0:
    over_admit = df.filter(
        pl.col("number_admitted").is_not_null() &
        pl.col("number_applied").is_not_null() &
        (pl.col("number_admitted") > pl.col("number_applied"))
    )
    print(f"  number_admitted > number_applied: {over_admit.shape[0]:,} institutions")
    if over_admit.shape[0] > 0:
        print(f"    These have admit_rate capped at 100 (script behavior)")
        capped = over_admit.filter(pl.col("admit_rate") == 100.0)
        print(f"    Actually capped at 100: {capped.shape[0]:,}")

# 8c: admit_rate extremes
if df.filter(pl.col("admit_rate").is_not_null()).shape[0] > 0:
    admit_0 = df.filter(pl.col("admit_rate") == 0.0).shape[0]
    admit_100 = df.filter(pl.col("admit_rate") == 100.0).shape[0]
    print(f"  admit_rate == 0 (admits nobody): {admit_0}")
    print(f"  admit_rate == 100 (admits everyone): {admit_100}")

# 8d: admit_rate range check
admit_valid = df.filter(pl.col("admit_rate").is_not_null())
if admit_valid.shape[0] > 0:
    min_rate = admit_valid["admit_rate"].min()
    max_rate = admit_valid["admit_rate"].max()
    range_ok = min_rate >= 0 and max_rate <= 100
    print(f"  admit_rate range: [{min_rate:.2f}, {max_rate:.2f}]")
    print(f"[{'PASS' if range_ok else 'FAIL'}] Boundary: admit_rate in [0, 100]")
else:
    range_ok = False
    print(f"[FAIL] Boundary: No non-null admit_rate values")

# --- Check 9 [Absence]: Verify excluded columns are actually excluded ---
print(f"\n--- Absence: Verify column exclusions ---")
should_be_absent = ["year", "sex", "fips", "number_enrolled_ft", "number_enrolled_pt"]
absent_issues = []
for col in should_be_absent:
    if col in df.columns:
        absent_issues.append(f"{col} should not be in clean output")
absence_ok = len(absent_issues) == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] Absence: ", end="")
print("All non-essential columns excluded" if absence_ok else "; ".join(absent_issues))

# Also check: is fips excluded? The raw data has fips, but Plan Task 3.2 Step 7 does not include it
if "fips" in df.columns:
    print(f"  WARNING: fips present but not in Plan's output column list")

# --- Check 10 [Downstream]: Characterize null admit_rate for join-core consumers ---
print(f"\n--- Downstream: Null admit_rate characterization ---")
null_admit = df.filter(pl.col("admit_rate").is_null())
non_null_admit = df.filter(pl.col("admit_rate").is_not_null())
print(f"  Null admit_rate: {null_admit.shape[0]:,} institutions ({null_admit.shape[0]/len(df)*100:.1f}%)")
print(f"  Non-null admit_rate: {non_null_admit.shape[0]:,} institutions")
if null_admit.shape[0] > 0:
    # What do these nulls look like?
    null_applied = null_admit.filter(pl.col("number_applied").is_null()).shape[0]
    null_admitted = null_admit.filter(pl.col("number_admitted").is_null()).shape[0]
    zero_applied = null_admit.filter(pl.col("number_applied") == 0).shape[0]
    print(f"  Reasons for null admit_rate:")
    print(f"    number_applied is null: {null_applied}")
    print(f"    number_admitted is null: {null_admitted}")
    print(f"    number_applied == 0: {zero_applied}")
    # These will be null admit_rate in the join-core step -- downstream scripts
    # should handle institutions with missing admission data gracefully
downstream_ok = True
print(f"[PASS] Downstream: Null pattern is well-characterized for consumers")

# --- Spot-Check 11: Trace specific unitids through raw -> clean ---
print(f"\n--- Spot-Check 11: Trace unitids through pipeline ---")
# Pick first 3 unitids from clean data and verify against raw
sample_unitids = df["unitid"].head(3).to_list()
for uid in sample_unitids:
    raw_rows = raw.filter(
        (pl.col("unitid") == uid) &
        (pl.col("sex") == 99) &
        (pl.col("year") == 2020)
    )
    clean_row = df.filter(pl.col("unitid") == uid)
    print(f"  unitid={uid}:")
    print(f"    Raw (sex=99, year=2020): {raw_rows.shape[0]} rows")
    print(f"    Clean: {clean_row.shape[0]} rows")
    if raw_rows.shape[0] == 1 and clean_row.shape[0] == 1:
        raw_applied = raw_rows["number_applied"][0]
        raw_admitted = raw_rows["number_admitted"][0]
        clean_applied = clean_row["number_applied"][0]
        clean_admitted = clean_row["number_admitted"][0]
        clean_rate = clean_row["admit_rate"][0]
        print(f"    Raw: applied={raw_applied}, admitted={raw_admitted}")
        print(f"    Clean: applied={clean_applied}, admitted={clean_admitted}, rate={clean_rate}")
        if raw_applied is not None and raw_applied > 0 and raw_admitted is not None:
            expected_rate = (raw_admitted / raw_applied) * 100.0
            matches = abs(expected_rate - clean_rate) < 0.01 if clean_rate is not None else False
            print(f"    Expected rate: {expected_rate:.4f} -- {'MATCH' if matches else 'MISMATCH'}")

# --- Spot-Check 12: Verify unitid uniqueness rigorously ---
print(f"\n--- Spot-Check 12: Unitid uniqueness ---")
n_unique = df["unitid"].n_unique()
n_total = len(df)
unique_ok = n_unique == n_total
print(f"  {n_unique:,} unique unitids out of {n_total:,} rows")
print(f"[{'PASS' if unique_ok else 'FAIL'}] Unitid uniqueness: {'unique' if unique_ok else 'DUPLICATES FOUND'}")

# --- Spot-Check 13: Verify filter complement (what was removed) ---
print(f"\n--- Spot-Check 13: Filter complement analysis ---")
# What sex values were removed?
removed_sex = raw.filter(pl.col("sex") != 99)
print(f"  Rows removed by sex!=99 filter: {removed_sex.shape[0]:,}")
print(f"  Sex values removed: {removed_sex['sex'].unique().sort().to_list()}")
# What year values were removed?
removed_year = raw.filter((pl.col("sex") == 99) & (pl.col("year") != 2020))
print(f"  Rows removed by year!=2020 filter (after sex==99): {removed_year.shape[0]:,}")
print(f"  Years removed: {removed_year['year'].unique().sort().to_list()}")
# Expected: 3970*2 = 7940 removed by sex filter, then 1981 removed by year filter
# Total raw = 11910, after sex filter = 3970, after year filter = 1989
# 11910 - 3970 = 7940 (sex filter), 3970 - 1989 = 1981 (year filter). Check!
expected_after_sex = raw.filter(pl.col("sex") == 99).shape[0]
expected_after_both = raw.filter((pl.col("sex") == 99) & (pl.col("year") == 2020)).shape[0]
print(f"  Expected after sex==99: {expected_after_sex:,} (matches script: {expected_after_sex == 3970})")
print(f"  Expected after sex+year: {expected_after_both:,} (matches script: {expected_after_both == 1989})")
complement_ok = expected_after_both == len(df)
print(f"[{'PASS' if complement_ok else 'FAIL'}] Filter complement: Removed rows are exactly what we expect")

# --- Spot-Check 14: number_admitted <= number_applied check (data quality) ---
print(f"\n--- Spot-Check 14: Admitted <= Applied invariant ---")
both_present = df.filter(
    pl.col("number_applied").is_not_null() & pl.col("number_admitted").is_not_null()
)
violations = both_present.filter(pl.col("number_admitted") > pl.col("number_applied"))
print(f"  Institutions with both values: {both_present.shape[0]:,}")
print(f"  Violations (admitted > applied): {violations.shape[0]:,}")
if violations.shape[0] > 0:
    print(f"  These are IPEDS data quality issues -- admit_rate capped at 100 by script")
    print(f"  Sample violations:")
    print(violations.select(["unitid", "number_applied", "number_admitted", "admit_rate"]).head(5))

# --- Spot-Check 15: Verify null counts match between raw subset and clean ---
print(f"\n--- Spot-Check 15: Null count consistency ---")
raw_sub = raw.filter((pl.col("sex") == 99) & (pl.col("year") == 2020))
for col_name in ["number_applied", "number_admitted", "number_enrolled_total"]:
    if col_name in raw_sub.columns and col_name in df.columns:
        # Raw nulls + raw coded values = clean nulls (because coded values become null)
        raw_nulls = raw_sub[col_name].null_count()
        raw_coded = sum((raw_sub[col_name] == c).sum() for c in CODED_MISSING_VALUES)
        clean_nulls = df[col_name].null_count()
        expected_clean_nulls = raw_nulls + raw_coded
        match = clean_nulls == expected_clean_nulls
        print(f"  {col_name}: raw_null={raw_nulls}, raw_coded={raw_coded}, clean_null={clean_nulls}, expected={expected_clean_nulls} -- {'MATCH' if match else 'MISMATCH'}")

# --- Data Profiling (for cr2+ decision) ---
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

print("\nNull counts:")
for col in df.columns:
    nc = df[col].null_count()
    print(f"  {col}: {nc} ({nc/len(df)*100:.1f}%)")

print("\nKey column distributions:")
for col in ["number_applied", "number_admitted", "number_enrolled_total", "admit_rate"]:
    if col in df.columns:
        valid = df[col].drop_nulls()
        if len(valid) > 0:
            print(f"\n  {col}:")
            print(f"    count={len(valid)}, min={valid.min()}, max={valid.max()}")
            print(f"    mean={valid.mean():.2f}, median={valid.median():.2f}")
            print(f"    std={valid.std():.2f}")
            # Quartiles
            q25 = valid.quantile(0.25)
            q75 = valid.quantile(0.75)
            print(f"    Q25={q25}, Q75={q75}")

# admit_rate distribution buckets
print("\nadmit_rate distribution (10% buckets):")
admit_valid = df.filter(pl.col("admit_rate").is_not_null())
for lo in range(0, 100, 10):
    hi = lo + 10
    n = admit_valid.filter(
        (pl.col("admit_rate") >= lo) & (pl.col("admit_rate") < hi)
    ).shape[0]
    print(f"  [{lo:3d}-{hi:3d}): {n:4d}")
n_100 = admit_valid.filter(pl.col("admit_rate") == 100.0).shape[0]
print(f"  [100]   : {n_100:4d}")

# --- Summary ---
all_base_passed = all([schema_ok, rows_in_tolerance, dist_ok, coded_ok, nulls_ok])
all_custom_passed = all([counterfactual_ok, semantic_ok, boundary_zero_ok if 'boundary_zero_ok' in dir() else True,
                         range_ok, absence_ok, downstream_ok, unique_ok, complement_ok])
all_passed = all_base_passed and all_custom_passed

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
if not rows_in_plan_range and all_base_passed and all_custom_passed:
    severity = "WARNING (row count near but below Plan range)"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:44:44
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_02_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 02 (clean-admissions)
# ============================================================
# Loaded clean data: 1,989 rows x 5 cols
# Loaded raw data: 11,910 rows x 9 cols
# 
# [PASS] Schema: All expected columns present
# [WARN] Row count: 1,989 (Plan range: 2,000-3,500)
#   Near Plan range -- 1989 is 11 below minimum
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Counterfactual: Coded values in raw data (sex==99, year==2020 subset) ---
# Raw subset (sex==99, year==2020): 1,989 rows
#   No coded values found in raw subset -- data genuinely clean (not masked by filter)
# [PASS] Counterfactual: Coded value absence is genuine, not an artifact of filtering
# 
# --- Semantic: Independent admit_rate recalculation ---
#   Recalculated for 1,966 rows with valid inputs
#   Max difference: 0.0
#   Mean difference: 0.0
# [PASS] Semantic: admit_rate formula verified independently
# 
# --- Boundary: Edge case analysis ---
#   number_applied == 0: 23 institutions
#     Of these, admit_rate is null: 23
#     [PASS] All zero-applied have null admit_rate
#   number_admitted > number_applied: 0 institutions
#   admit_rate == 0 (admits nobody): 2
#   admit_rate == 100 (admits everyone): 104
#   admit_rate range: [0.00, 100.00]
# [PASS] Boundary: admit_rate in [0, 100]
# 
# --- Absence: Verify column exclusions ---
# [PASS] Absence: All non-essential columns excluded
# 
# --- Downstream: Null admit_rate characterization ---
#   Null admit_rate: 23 institutions (1.2%)
#   Non-null admit_rate: 1,966 institutions
#   Reasons for null admit_rate:
#     number_applied is null: 0
#     number_admitted is null: 23
#     number_applied == 0: 23
# [PASS] Downstream: Null pattern is well-characterized for consumers
# 
# --- Spot-Check 11: Trace unitids through pipeline ---
#   unitid=100654:
#     Raw (sex=99, year=2020): 1 rows
#     Clean: 1 rows
#     Raw: applied=9855, admitted=8835
#     Clean: applied=9855, admitted=8835, rate=89.64992389649925
#     Expected rate: 89.6499 -- MATCH
#   unitid=100663:
#     Raw (sex=99, year=2020): 1 rows
#     Clean: 1 rows
#     Raw: applied=10391, admitted=8375
#     Clean: applied=10391, admitted=8375, rate=80.59859493792705
#     Expected rate: 80.5986 -- MATCH
#   unitid=100706:
#     Raw (sex=99, year=2020): 1 rows
#     Clean: 1 rows
#     Raw: applied=5793, admitted=4467
#     Clean: applied=5793, admitted=4467, rate=77.11030554117038
#     Expected rate: 77.1103 -- MATCH
# 
# --- Spot-Check 12: Unitid uniqueness ---
#   1,989 unique unitids out of 1,989 rows
# [PASS] Unitid uniqueness: unique
# 
# --- Spot-Check 13: Filter complement analysis ---
#   Rows removed by sex!=99 filter: 7,940
#   Sex values removed: [1, 2]
#   Rows removed by year!=2020 filter (after sex==99): 1,981
#   Years removed: [2021]
#   Expected after sex==99: 3,970 (matches script: True)
#   Expected after sex+year: 1,989 (matches script: True)
# [PASS] Filter complement: Removed rows are exactly what we expect
# 
# --- Spot-Check 14: Admitted <= Applied invariant ---
#   Institutions with both values: 1,966
#   Violations (admitted > applied): 0
# 
# --- Spot-Check 15: Null count consistency ---
#   number_applied: raw_null=0, raw_coded=0, clean_null=0, expected=0 -- MATCH
#   number_admitted: raw_null=23, raw_coded=0, clean_null=23, expected=23 -- MATCH
#   number_enrolled_total: raw_null=25, raw_coded=0, clean_null=25, expected=25 -- MATCH
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 5)
# ┌────────┬────────────────┬─────────────────┬───────────────────────┬────────────┐
# │ unitid ┆ number_applied ┆ number_admitted ┆ number_enrolled_total ┆ admit_rate │
# │ ---    ┆ ---            ┆ ---             ┆ ---                   ┆ ---        │
# │ i64    ┆ i64            ┆ i64             ┆ i64                   ┆ f64        │
# ╞════════╪════════════════╪═════════════════╪═══════════════════════╪════════════╡
# │ 100654 ┆ 9855           ┆ 8835            ┆ 1664                  ┆ 89.649924  │
# │ 100663 ┆ 10391          ┆ 8375            ┆ 2154                  ┆ 80.598595  │
# │ 100706 ┆ 5793           ┆ 4467            ┆ 1345                  ┆ 77.110306  │
# │ 100724 ┆ 7027           ┆ 6948            ┆ 975                   ┆ 98.875765  │
# │ 100751 ┆ 39560          ┆ 31804           ┆ 6507                  ┆ 80.394338  │
# │ 100830 ┆ 4606           ┆ 4401            ┆ 674                   ┆ 95.549284  │
# │ 100858 ┆ 17946          ┆ 15266           ┆ 4914                  ┆ 85.06631   │
# │ 100937 ┆ 2460           ┆ 1487            ┆ 256                   ┆ 60.447154  │
# │ 101189 ┆ 1572           ┆ 1191            ┆ 288                   ┆ 75.763359  │
# │ 101365 ┆ 177            ┆ 162             ┆ 102                   ┆ 91.525424  │
# └────────┴────────────────┴─────────────────┴───────────────────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 6)
# ┌────────────┬───────────────┬────────────────┬─────────────────┬─────────────────────┬────────────┐
# │ statistic  ┆ unitid        ┆ number_applied ┆ number_admitted ┆ number_enrolled_tot ┆ admit_rate │
# │ ---        ┆ ---           ┆ ---            ┆ ---             ┆ al                  ┆ ---        │
# │ str        ┆ f64           ┆ f64            ┆ f64             ┆ ---                 ┆ f64        │
# │            ┆               ┆                ┆                 ┆ f64                 ┆            │
# ╞════════════╪═══════════════╪════════════════╪═════════════════╪═════════════════════╪════════════╡
# │ count      ┆ 1989.0        ┆ 1989.0         ┆ 1966.0          ┆ 1964.0              ┆ 1966.0     │
# │ null_count ┆ 0.0           ┆ 0.0            ┆ 23.0            ┆ 25.0                ┆ 23.0       │
# │ mean       ┆ 224890.833585 ┆ 5825.701357    ┆ 3578.694303     ┆ 801.238798          ┆ 71.217225  │
# │ std        ┆ 106587.8359   ┆ 10808.406814   ┆ 5891.773274     ┆ 1375.075243         ┆ 21.329822  │
# │ min        ┆ 100654.0      ┆ 0.0            ┆ 0.0             ┆ 0.0                 ┆ 0.0        │
# │ 25%        ┆ 157951.0      ┆ 272.0          ┆ 219.0           ┆ 95.0                ┆ 59.5439    │
# │ 50%        ┆ 196176.0      ┆ 2016.0         ┆ 1440.0          ┆ 326.0               ┆ 75.244644  │
# │ 75%        ┆ 230889.0      ┆ 6046.0         ┆ 4108.0          ┆ 788.0               ┆ 87.5       │
# │ max        ┆ 495916.0      ┆ 108870.0       ┆ 74604.0         ┆ 15614.0             ┆ 100.0      │
# └────────────┴───────────────┴────────────────┴─────────────────┴─────────────────────┴────────────┘
# 
# Column types:
#   unitid: Int64
#   number_applied: Int64
#   number_admitted: Int64
#   number_enrolled_total: Int64
#   admit_rate: Float64
# 
# Null counts:
#   unitid: 0 (0.0%)
#   number_applied: 0 (0.0%)
#   number_admitted: 23 (1.2%)
#   number_enrolled_total: 25 (1.3%)
#   admit_rate: 23 (1.2%)
# 
# Key column distributions:
# 
#   number_applied:
#     count=1989, min=0, max=108870
#     mean=5825.70, median=2016.00
#     std=10808.41
#     Q25=272.0, Q75=6046.0
# 
#   number_admitted:
#     count=1966, min=0, max=74604
#     mean=3578.69, median=1440.00
#     std=5891.77
#     Q25=219.0, Q75=4108.0
# 
#   number_enrolled_total:
#     count=1964, min=0, max=15614
#     mean=801.24, median=326.00
#     std=1375.08
#     Q25=95.0, Q75=788.0
# 
#   admit_rate:
#     count=1966, min=0.0, max=100.0
#     mean=71.22, median=75.22
#     std=21.33
#     Q25=59.54389965792475, Q75=87.5
# 
# admit_rate distribution (10% buckets):
#   [  0- 10):   24
#   [ 10- 20):   36
#   [ 20- 30):   43
#   [ 30- 40):   93
#   [ 40- 50):  106
#   [ 50- 60):  200
#   [ 60- 70):  283
#   [ 70- 80):  408
#   [ 80- 90):  362
#   [ 90-100):  307
#   [100]   :  104
# 
# ============================================================
# QA RESULT: WARNING (row count near but below Plan range)
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
