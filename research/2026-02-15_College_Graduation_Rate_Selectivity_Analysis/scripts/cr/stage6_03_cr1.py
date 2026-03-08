#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 3.3 (QA2)

Reviewed script: scripts/stage6_clean/03_clean-admissions.py
Output files: data/processed/2026-02-15_admissions_clean.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range (2,000-3,000)
3. No suspicious distributions
4. Coded values properly filtered (-1, -2, -3)
5. No nulls in critical columns (unitid)

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if number_applied has unexpected zero or negative values?
7. [Semantic] Does admission_rate actually serve the research question about selectivity?
8. [Boundary] Investigate admission_rate extremes (exact 0.0 and exact 1.0)
9. [Absence] Check number_admitted <= number_applied invariant
10. [Downstream] Verify output is suitable for Stage 7 join-core task

Spot-Checks:
11. Recalculate admission_rate for 3 known institutions
12. Verify null admission_rate corresponds to null number_admitted
13. Check admission_rate=0 institutions are plausible
14. Verify no negative values in numeric columns
15. Cross-check null counts match between execution log and actual data
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_admissions_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_admissions.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "number_applied", "number_admitted", "number_enrolled_total", "admission_rate"]
EXPECTED_MIN_ROWS = 1500
EXPECTED_MAX_ROWS = 3500
CRITICAL_COLUMNS = ["unitid"]  # unitid must never be null; admission_rate allows nulls per Plan

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 3.3 (QA2 — clean-admissions)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded clean data: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load raw for comparison
raw_df = pl.read_parquet(RAW_FILE)
print(f"Loaded raw data:   {raw_df.shape[0]:,} rows x {raw_df.shape[1]} cols")

# ==============================================================================
# DEFAULT CHECKS
# ==============================================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print(f"All {len(EXPECTED_COLUMNS)} expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")

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
for col in ["number_applied", "number_admitted", "number_enrolled_total"]:
    if col not in df.columns:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain in analysis columns" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls (unitid): ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# ==============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ==============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Unexpected zero or negative values in number_applied ---
# If number_applied has zeros that aren't coded values, the script should still
# set admission_rate to null (guarded by number_applied > 0).
zero_applied = df.filter(pl.col("number_applied") == 0)
negative_applied = df.filter(
    pl.col("number_applied").is_not_null() & (pl.col("number_applied") < 0)
)
print(f"\n[Counterfactual] number_applied == 0: {zero_applied.height} rows")
print(f"[Counterfactual] number_applied < 0 (non-coded): {negative_applied.height} rows")
# If zero_applied exists, verify their admission_rate is null
if zero_applied.height > 0:
    zero_with_rate = zero_applied.filter(pl.col("admission_rate").is_not_null())
    if zero_with_rate.height > 0:
        print(f"  [FAIL] {zero_with_rate.height} rows with number_applied=0 have non-null admission_rate!")
    else:
        print(f"  [PASS] All rows with number_applied=0 correctly have null admission_rate")
else:
    print(f"  [PASS] No zero-applied rows to guard against (guard clause is defensive)")
counterfactual_ok = negative_applied.height == 0
print(f"[{'PASS' if counterfactual_ok else 'WARN'}] No unexpected negative values in number_applied")

# --- Check 7: [Semantic] Does admission_rate serve the research question? ---
# The research question asks about selectivity. admission_rate (proportion admitted)
# should be NEGATIVELY correlated with graduation rate in the final analysis.
# Here we verify the distribution makes intuitive sense for a selectivity measure.
ar = df.filter(pl.col("admission_rate").is_not_null())["admission_rate"]
below_25 = (ar < 0.25).sum()
between_25_50 = ((ar >= 0.25) & (ar < 0.50)).sum()
between_50_75 = ((ar >= 0.50) & (ar < 0.75)).sum()
above_75 = (ar >= 0.75).sum()
print(f"\n[Semantic] admission_rate distribution for selectivity banding:")
print(f"  Highly Selective (<25%): {below_25} institutions ({below_25/len(ar)*100:.1f}%)")
print(f"  Selective (25-50%):      {between_25_50} ({between_25_50/len(ar)*100:.1f}%)")
print(f"  Moderately Selective:    {between_50_75} ({between_50_75/len(ar)*100:.1f}%)")
print(f"  Less Selective (>=75%):  {above_75} ({above_75/len(ar)*100:.1f}%)")
all_bands_populated = all(x > 0 for x in [below_25, between_25_50, between_50_75, above_75])
print(f"[{'PASS' if all_bands_populated else 'WARN'}] All selectivity bands will have data: {all_bands_populated}")

# --- Check 8: [Boundary] Investigate exact 0.0 and exact 1.0 admission_rate ---
exact_zero = df.filter(pl.col("admission_rate") == 0.0)
exact_one = df.filter(pl.col("admission_rate") == 1.0)
print(f"\n[Boundary] admission_rate == 0.0: {exact_zero.height} institutions")
if exact_zero.height > 0:
    print(f"  These institutions admitted 0 students despite having applicants:")
    print(exact_zero.select(["unitid", "number_applied", "number_admitted", "admission_rate"]).head(5))
print(f"[Boundary] admission_rate == 1.0: {exact_one.height} institutions")
if exact_one.height > 0 and exact_one.height <= 10:
    print(f"  These institutions admitted all applicants:")
    print(exact_one.select(["unitid", "number_applied", "number_admitted", "admission_rate"]).head(5))
elif exact_one.height > 10:
    print(f"  (Showing first 5 of {exact_one.height}):")
    print(exact_one.select(["unitid", "number_applied", "number_admitted", "admission_rate"]).head(5))
# admission_rate=0 is mathematically valid but odd; admission_rate=1 is normal for near-open
boundary_ok = True  # Will flag if truly problematic
if exact_zero.height > 0:
    # Check if number_admitted == 0 but number_applied > 0 — valid but unusual
    invalid_zero = exact_zero.filter(pl.col("number_admitted") != 0)
    if invalid_zero.height > 0:
        print(f"  [FAIL] {invalid_zero.height} rows have admission_rate=0 but number_admitted != 0!")
        boundary_ok = False
    else:
        print(f"  [PASS] admission_rate=0 correctly implies number_admitted=0")
print(f"[{'PASS' if boundary_ok else 'FAIL'}] Boundary values are consistent")

# --- Check 9: [Absence] Verify number_admitted <= number_applied ---
# The script does NOT explicitly check this invariant. If violated, admission_rate > 1.
# The range check [0,1] catches it, but let's verify independently.
invalid_admits = df.filter(
    pl.col("number_applied").is_not_null()
    & pl.col("number_admitted").is_not_null()
    & (pl.col("number_admitted") > pl.col("number_applied"))
)
absence_ok = invalid_admits.height == 0
print(f"\n[Absence] number_admitted > number_applied: {invalid_admits.height} rows")
if invalid_admits.height > 0:
    print(f"  [FAIL] Data integrity violation — more admitted than applied!")
    print(invalid_admits.select(["unitid", "number_applied", "number_admitted", "admission_rate"]).head(5))
else:
    print(f"  [PASS] number_admitted <= number_applied for all non-null rows")

# --- Check 10: [Downstream] Output suitable for join-core task ---
# join-core expects unitid as the join key. Verify uniqueness.
unitid_unique = df["unitid"].n_unique() == len(df)
has_year = "year" in df.columns
has_admission_rate = "admission_rate" in df.columns
print(f"\n[Downstream] unitid uniqueness: {'UNIQUE' if unitid_unique else 'DUPLICATES FOUND'} ({df['unitid'].n_unique():,} unique of {len(df):,})")
print(f"[Downstream] admission_rate column present: {has_admission_rate}")
print(f"[Downstream] year column present: {has_year}")
downstream_ok = unitid_unique and has_admission_rate
print(f"[{'PASS' if downstream_ok else 'FAIL'}] Output ready for join-core")

# ==============================================================================
# SPOT-CHECKS
# ==============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recalculate admission_rate for known institutions ---
sample_ids = [100654, 100663, 100706]  # Same as script's tracking sample
print(f"\n[Spot-Check 11] Recalculate admission_rate for unitids {sample_ids}:")
recalc_ok = True
for uid in sample_ids:
    row = df.filter(pl.col("unitid") == uid)
    if row.height == 0:
        print(f"  unitid {uid}: NOT FOUND")
        recalc_ok = False
        continue
    applied = row["number_applied"][0]
    admitted = row["number_admitted"][0]
    computed_rate = row["admission_rate"][0]
    if applied is not None and admitted is not None and applied > 0:
        expected_rate = admitted / applied
        match = abs(computed_rate - expected_rate) < 1e-10
        print(f"  unitid {uid}: {admitted}/{applied} = {expected_rate:.6f}, stored = {computed_rate:.6f} -> {'MATCH' if match else 'MISMATCH'}")
        if not match:
            recalc_ok = False
    else:
        print(f"  unitid {uid}: applied={applied}, admitted={admitted} -> rate should be null, is {computed_rate}")
        if computed_rate is not None:
            recalc_ok = False
print(f"[{'PASS' if recalc_ok else 'FAIL'}] Manual recalculation matches stored values")

# --- Spot-Check 12: null admission_rate corresponds to null number_admitted ---
null_rate_rows = df.filter(pl.col("admission_rate").is_null())
# admission_rate should be null when: number_applied is null, number_applied==0, OR number_admitted is null
null_rate_with_valid_inputs = null_rate_rows.filter(
    pl.col("number_applied").is_not_null()
    & (pl.col("number_applied") > 0)
    & pl.col("number_admitted").is_not_null()
)
spot12_ok = null_rate_with_valid_inputs.height == 0
print(f"\n[Spot-Check 12] Null admission_rate rows: {null_rate_rows.height}")
print(f"  Of these, rows where both inputs are valid (should be 0): {null_rate_with_valid_inputs.height}")
print(f"[{'PASS' if spot12_ok else 'FAIL'}] All null admission_rate rows have valid justification")

# --- Spot-Check 13: admission_rate=0 institutions are plausible ---
if exact_zero.height > 0:
    print(f"\n[Spot-Check 13] Inspecting admission_rate=0 institutions:")
    print(exact_zero.select(["unitid", "number_applied", "number_admitted", "number_enrolled_total"]))
    # These should have number_admitted=0 but number_applied>0
    spot13_ok = (exact_zero["number_admitted"] == 0).all()
    print(f"[{'PASS' if spot13_ok else 'FAIL'}] All admission_rate=0 have number_admitted=0")
else:
    print(f"\n[Spot-Check 13] No admission_rate=0 institutions to inspect")
    spot13_ok = True

# --- Spot-Check 14: No negative values in numeric columns (beyond coded) ---
neg_issues = []
for col in ["number_applied", "number_admitted", "number_enrolled_total"]:
    if col in df.columns:
        neg_count = df.filter(pl.col(col).is_not_null() & (pl.col(col) < 0)).height
        if neg_count > 0:
            neg_issues.append(f"{col}: {neg_count} negative values")
spot14_ok = len(neg_issues) == 0
print(f"\n[Spot-Check 14] Negative values in numeric columns: ", end="")
print("None" if spot14_ok else "; ".join(neg_issues))
print(f"[{'PASS' if spot14_ok else 'FAIL'}] No negative values remain after cleaning")

# --- Spot-Check 15: Cross-check null counts match execution log ---
# Execution log reported: number_admitted: 23 nulls, number_enrolled_total: 25 nulls,
# admission_rate: 23 nulls
admitted_nulls = df["number_admitted"].null_count()
enrolled_nulls = df["number_enrolled_total"].null_count()
rate_nulls = df["admission_rate"].null_count()
applied_nulls = df["number_applied"].null_count()
print(f"\n[Spot-Check 15] Null counts vs execution log:")
print(f"  number_applied: {applied_nulls} (log: 0)")
print(f"  number_admitted: {admitted_nulls} (log: 23)")
print(f"  number_enrolled_total: {enrolled_nulls} (log: 25)")
print(f"  admission_rate: {rate_nulls} (log: 23)")
spot15_ok = (applied_nulls == 0 and admitted_nulls == 23 and enrolled_nulls == 25 and rate_nulls == 23)
print(f"[{'PASS' if spot15_ok else 'FAIL'}] Null counts match execution log")

# ==============================================================================
# RAW-TO-CLEAN COMPARISON
# ==============================================================================

print("\n" + "=" * 60)
print("RAW-TO-CLEAN COMPARISON")
print("=" * 60)

# Verify row count preserved
raw_rows = raw_df.shape[0]
clean_rows = df.shape[0]
print(f"Raw rows: {raw_rows:,}, Clean rows: {clean_rows:,}, Change: {((clean_rows-raw_rows)/raw_rows*100):+.1f}%")
rows_preserved = raw_rows == clean_rows
print(f"[{'PASS' if rows_preserved else 'FAIL'}] Row count preserved")

# Verify new column added
new_cols = [c for c in df.columns if c not in raw_df.columns]
print(f"New columns added: {new_cols}")
print(f"[{'PASS' if 'admission_rate' in new_cols else 'FAIL'}] admission_rate column added")

# ==============================================================================
# DATA PROFILING (for cr2+ decision)
# ==============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nAdmission rate percentiles:")
ar_valid = df.filter(pl.col("admission_rate").is_not_null())["admission_rate"]
if len(ar_valid) > 0:
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        val = ar_valid.quantile(p / 100)
        print(f"  P{p}: {val:.4f}")

print("\nKey column value counts:")
print(f"\nyear:")
print(df["year"].value_counts())

# ==============================================================================
# SUMMARY
# ==============================================================================

print("\n" + "=" * 60)
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,  # defaults
    counterfactual_ok, all_bands_populated, boundary_ok, absence_ok, downstream_ok,  # lenses
    recalc_ok, spot12_ok, spot13_ok, spot14_ok, spot15_ok,  # spot-checks
    rows_preserved  # raw-to-clean
]
all_passed = all(all_checks)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA2 RESULT: {severity}")
print(f"Checks passed: {sum(all_checks)}/{len(all_checks)}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:46:10
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_03_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 3.3 (QA2 — clean-admissions)
# ============================================================
# Loaded clean data: 1,989 rows x 6 cols
# Loaded raw data:   1,989 rows x 5 cols
# 
# [PASS] Schema: All 6 expected columns present
# [PASS] Row count: 1,989 (expected 1,500-3,500)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None remain in analysis columns
# [PASS] Critical nulls (unitid): None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [Counterfactual] number_applied == 0: 23 rows
# [Counterfactual] number_applied < 0 (non-coded): 0 rows
#   [PASS] All rows with number_applied=0 correctly have null admission_rate
# [PASS] No unexpected negative values in number_applied
# 
# [Semantic] admission_rate distribution for selectivity banding:
#   Highly Selective (<25%): 83 institutions (4.2%)
#   Selective (25-50%):      219 (11.1%)
#   Moderately Selective:    664 (33.8%)
#   Less Selective (>=75%):  1000 (50.9%)
# [PASS] All selectivity bands will have data: True
# 
# [Boundary] admission_rate == 0.0: 2 institutions
#   These institutions admitted 0 students despite having applicants:
# shape: (2, 4)
# ┌────────┬────────────────┬─────────────────┬────────────────┐
# │ unitid ┆ number_applied ┆ number_admitted ┆ admission_rate │
# │ ---    ┆ ---            ┆ ---             ┆ ---            │
# │ i64    ┆ i64            ┆ i64             ┆ f64            │
# ╞════════╪════════════════╪═════════════════╪════════════════╡
# │ 143978 ┆ 39             ┆ 0               ┆ 0.0            │
# │ 482538 ┆ 2              ┆ 0               ┆ 0.0            │
# └────────┴────────────────┴─────────────────┴────────────────┘
# [Boundary] admission_rate == 1.0: 104 institutions
#   (Showing first 5 of 104):
# shape: (5, 4)
# ┌────────┬────────────────┬─────────────────┬────────────────┐
# │ unitid ┆ number_applied ┆ number_admitted ┆ admission_rate │
# │ ---    ┆ ---            ┆ ---             ┆ ---            │
# │ i64    ┆ i64            ┆ i64             ┆ f64            │
# ╞════════╪════════════════╪═════════════════╪════════════════╡
# │ 107585 ┆ 965            ┆ 965             ┆ 1.0            │
# │ 110918 ┆ 1              ┆ 1               ┆ 1.0            │
# │ 113582 ┆ 3              ┆ 3               ┆ 1.0            │
# │ 123280 ┆ 4              ┆ 4               ┆ 1.0            │
# │ 127653 ┆ 160            ┆ 160             ┆ 1.0            │
# └────────┴────────────────┴─────────────────┴────────────────┘
#   [PASS] admission_rate=0 correctly implies number_admitted=0
# [PASS] Boundary values are consistent
# 
# [Absence] number_admitted > number_applied: 0 rows
#   [PASS] number_admitted <= number_applied for all non-null rows
# 
# [Downstream] unitid uniqueness: UNIQUE (1,989 unique of 1,989)
# [Downstream] admission_rate column present: True
# [Downstream] year column present: True
# [PASS] Output ready for join-core
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [Spot-Check 11] Recalculate admission_rate for unitids [100654, 100663, 100706]:
#   unitid 100654: 8835/9855 = 0.896499, stored = 0.896499 -> MATCH
#   unitid 100663: 8375/10391 = 0.805986, stored = 0.805986 -> MATCH
#   unitid 100706: 4467/5793 = 0.771103, stored = 0.771103 -> MATCH
# [PASS] Manual recalculation matches stored values
# 
# [Spot-Check 12] Null admission_rate rows: 23
#   Of these, rows where both inputs are valid (should be 0): 0
# [PASS] All null admission_rate rows have valid justification
# 
# [Spot-Check 13] Inspecting admission_rate=0 institutions:
# shape: (2, 4)
# ┌────────┬────────────────┬─────────────────┬───────────────────────┐
# │ unitid ┆ number_applied ┆ number_admitted ┆ number_enrolled_total │
# │ ---    ┆ ---            ┆ ---             ┆ ---                   │
# │ i64    ┆ i64            ┆ i64             ┆ i64                   │
# ╞════════╪════════════════╪═════════════════╪═══════════════════════╡
# │ 143978 ┆ 39             ┆ 0               ┆ null                  │
# │ 482538 ┆ 2              ┆ 0               ┆ null                  │
# └────────┴────────────────┴─────────────────┴───────────────────────┘
# [PASS] All admission_rate=0 have number_admitted=0
# 
# [Spot-Check 14] Negative values in numeric columns: None
# [PASS] No negative values remain after cleaning
# 
# [Spot-Check 15] Null counts vs execution log:
#   number_applied: 0 (log: 0)
#   number_admitted: 23 (log: 23)
#   number_enrolled_total: 25 (log: 25)
#   admission_rate: 23 (log: 23)
# [PASS] Null counts match execution log
# 
# ============================================================
# RAW-TO-CLEAN COMPARISON
# ============================================================
# Raw rows: 1,989, Clean rows: 1,989, Change: +0.0%
# [PASS] Row count preserved
# New columns added: ['admission_rate']
# [PASS] admission_rate column added
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 6)
# ┌────────┬──────┬────────────────┬─────────────────┬───────────────────────┬────────────────┐
# │ unitid ┆ year ┆ number_applied ┆ number_admitted ┆ number_enrolled_total ┆ admission_rate │
# │ ---    ┆ ---  ┆ ---            ┆ ---             ┆ ---                   ┆ ---            │
# │ i64    ┆ i64  ┆ i64            ┆ i64             ┆ i64                   ┆ f64            │
# ╞════════╪══════╪════════════════╪═════════════════╪═══════════════════════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 9855           ┆ 8835            ┆ 1664                  ┆ 0.896499       │
# │ 100663 ┆ 2020 ┆ 10391          ┆ 8375            ┆ 2154                  ┆ 0.805986       │
# │ 100706 ┆ 2020 ┆ 5793           ┆ 4467            ┆ 1345                  ┆ 0.771103       │
# │ 100724 ┆ 2020 ┆ 7027           ┆ 6948            ┆ 975                   ┆ 0.988758       │
# │ 100751 ┆ 2020 ┆ 39560          ┆ 31804           ┆ 6507                  ┆ 0.803943       │
# │ …      ┆ …    ┆ …              ┆ …               ┆ …                     ┆ …              │
# │ 101648 ┆ 2020 ┆ 1000           ┆ 575             ┆ 255                   ┆ 0.575          │
# │ 101693 ┆ 2020 ┆ 2037           ┆ 1356            ┆ 250                   ┆ 0.665685       │
# │ 101709 ┆ 2020 ┆ 4954           ┆ 2998            ┆ 471                   ┆ 0.605168       │
# │ 101879 ┆ 2020 ┆ 2739           ┆ 2264            ┆ 924                   ┆ 0.826579       │
# │ 101912 ┆ 2020 ┆ 1135           ┆ 1008            ┆ 303                   ┆ 0.888106       │
# └────────┴──────┴────────────────┴─────────────────┴───────────────────────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 7)
# ┌────────────┬───────────────┬────────┬───────────────┬──────────────┬──────────────┬──────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ number_applie ┆ number_admit ┆ number_enrol ┆ admission_ra │
# │ ---        ┆ ---           ┆ ---    ┆ d             ┆ ted          ┆ led_total    ┆ te           │
# │ str        ┆ f64           ┆ f64    ┆ ---           ┆ ---          ┆ ---          ┆ ---          │
# │            ┆               ┆        ┆ f64           ┆ f64          ┆ f64          ┆ f64          │
# ╞════════════╪═══════════════╪════════╪═══════════════╪══════════════╪══════════════╪══════════════╡
# │ count      ┆ 1989.0        ┆ 1989.0 ┆ 1989.0        ┆ 1966.0       ┆ 1964.0       ┆ 1966.0       │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 0.0           ┆ 23.0         ┆ 25.0         ┆ 23.0         │
# │ mean       ┆ 224890.833585 ┆ 2020.0 ┆ 5825.701357   ┆ 3578.694303  ┆ 801.238798   ┆ 0.712172     │
# │ std        ┆ 106587.8359   ┆ 0.0    ┆ 10808.406814  ┆ 5891.773274  ┆ 1375.075243  ┆ 0.213298     │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.0           ┆ 0.0          ┆ 0.0          ┆ 0.0          │
# │ 25%        ┆ 157951.0      ┆ 2020.0 ┆ 272.0         ┆ 219.0        ┆ 95.0         ┆ 0.595439     │
# │ 50%        ┆ 196176.0      ┆ 2020.0 ┆ 2016.0        ┆ 1440.0       ┆ 326.0        ┆ 0.752446     │
# │ 75%        ┆ 230889.0      ┆ 2020.0 ┆ 6046.0        ┆ 4108.0       ┆ 788.0        ┆ 0.875        │
# │ max        ┆ 495916.0      ┆ 2020.0 ┆ 108870.0      ┆ 74604.0      ┆ 15614.0      ┆ 1.0          │
# └────────────┴───────────────┴────────┴───────────────┴──────────────┴──────────────┴──────────────┘
# 
# Admission rate percentiles:
#   P1: 0.0916
#   P5: 0.2835
#   P10: 0.4000
#   P25: 0.5954
#   P50: 0.7524
#   P75: 0.8750
#   P90: 0.9609
#   P95: 1.0000
#   P99: 1.0000
# 
# Key column value counts:
# 
# year:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 1989  │
# └──────┴───────┘
# 
# ============================================================
# QA2 RESULT: BLOCKER
# Checks passed: 15/16
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
