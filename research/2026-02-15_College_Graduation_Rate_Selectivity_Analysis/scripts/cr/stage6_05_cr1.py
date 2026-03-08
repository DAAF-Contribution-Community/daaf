#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 5

Reviewed script: scripts/stage6_clean/05_clean-enrollment-race_a.py
Output files: data/processed/2026-02-15_enrollment_race_clean.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
6. [Counterfactual] Verify MAX aggregation correctness via independent SUM-of-MAX-per-race vs race=99 MAX
7. [Semantic] Verify URM share actually serves the research question (correct race codes)
8. [Boundary] Check edge cases: urm_share=0, urm_share=1, very small institutions
9. [Absence] Check for missing NHPI (code 6) in URM definition and verify no institutions lost
10. [Downstream] Verify unitid alignment with raw data and output readiness for join-demographics
11-15. Concrete spot-checks
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_enrollment_race_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_enrollment_race.parquet"
EXPECTED_COLUMNS = ["unitid", "total_enrollment_race", "urm_enrollment", "urm_share"]
EXPECTED_MIN_ROWS = 2000
EXPECTED_MAX_ROWS = 8000
CRITICAL_COLUMNS = ["unitid", "urm_share", "total_enrollment_race", "urm_enrollment"]
URM_CODES = [2, 3, 5]  # Portal encoding: 2=Black, 3=Hispanic, 5=AI/AN
RACE_TOTAL = 99

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 5 (clean-enrollment-race)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load raw data for cross-reference
df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

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
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
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

# --- Check 6: [Counterfactual] Verify MAX aggregation independently ---
# The script chose MAX aggregation. Let's verify it by independently computing
# URM share using a completely different approach: take MAX per unitid+race,
# then compare individual race sums to race=99.
print(f"\n--- Counterfactual: Independent MAX aggregation validation ---")
df_raw_agg = (
    df_raw.group_by(["unitid", "race"])
    .agg(pl.col("enrollment_fall").max().alias("enrollment_max"))
)

# For each institution: sum of individual race MAXes vs race=99 MAX
race99 = df_raw_agg.filter(pl.col("race") == RACE_TOTAL).select("unitid", pl.col("enrollment_max").alias("total_99"))
indiv_races = (
    df_raw_agg.filter(pl.col("race") != RACE_TOTAL)
    .group_by("unitid")
    .agg(pl.col("enrollment_max").sum().alias("sum_races"))
)
check = race99.join(indiv_races, on="unitid", how="inner").filter(pl.col("total_99") > 0)
check = check.with_columns((pl.col("sum_races") / pl.col("total_99")).alias("ratio"))

ratio_min = check["ratio"].min()
ratio_max = check["ratio"].max()
ratio_mean = check["ratio"].mean()
counterfactual_ok = abs(ratio_mean - 1.0) < 0.01  # within 1%
print(f"[{'PASS' if counterfactual_ok else 'WARN'}] Independent MAX ratio check: "
      f"mean={ratio_mean:.6f}, min={ratio_min:.6f}, max={ratio_max:.6f}")

# Also check: does the output total_enrollment_race match our independent MAX for race=99?
independent_total = race99.rename({"total_99": "independent_total"})
compare_total = df.select("unitid", "total_enrollment_race").join(independent_total, on="unitid", how="inner")
total_mismatch = compare_total.filter(
    pl.col("total_enrollment_race") != pl.col("independent_total")
).shape[0]
total_match_ok = total_mismatch == 0
print(f"[{'PASS' if total_match_ok else 'FAIL'}] Output total_enrollment matches independent MAX: "
      f"{total_mismatch} mismatches out of {compare_total.shape[0]:,}")

# --- Check 7: [Semantic] URM race code verification ---
# Verify the right codes were used for URM by independently computing urm_enrollment
print(f"\n--- Semantic: URM code verification ---")
urm_raw = (
    df_raw_agg.filter(pl.col("race").is_in(URM_CODES))
    .group_by("unitid")
    .agg(pl.col("enrollment_max").sum().alias("independent_urm"))
)
compare_urm = df.select("unitid", "urm_enrollment").join(urm_raw, on="unitid", how="left")
compare_urm = compare_urm.with_columns(pl.col("independent_urm").fill_null(0))
urm_mismatch = compare_urm.filter(
    pl.col("urm_enrollment") != pl.col("independent_urm")
).shape[0]
urm_match_ok = urm_mismatch == 0
print(f"[{'PASS' if urm_match_ok else 'FAIL'}] URM enrollment matches independent calculation: "
      f"{urm_mismatch} mismatches")

# Verify Portal encoding: check that the race codes in raw data match expected set
raw_race_codes = sorted(df_raw["race"].unique().to_list())
expected_codes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
race_codes_ok = raw_race_codes == expected_codes
print(f"[{'PASS' if race_codes_ok else 'WARN'}] Raw race codes match Portal standard: "
      f"{raw_race_codes}")

# --- Check 8: [Boundary] Edge case analysis ---
print(f"\n--- Boundary: Edge cases ---")
# urm_share = 0 (institutions with zero URM enrollment)
urm_zero = df.filter(pl.col("urm_share") == 0.0).shape[0]
# urm_share = 1 (institutions that are 100% URM)
urm_one = df.filter(pl.col("urm_share") == 1.0).shape[0]
# Very small institutions (total enrollment < 10)
small_inst = df.filter(pl.col("total_enrollment_race") < 10).shape[0]
# Total enrollment = 1 (minimum)
min_total = df["total_enrollment_race"].min()

print(f"  urm_share == 0: {urm_zero} institutions")
print(f"  urm_share == 1: {urm_one} institutions")
print(f"  total_enrollment < 10: {small_inst} institutions")
print(f"  Minimum total_enrollment: {min_total}")
print(f"  Maximum total_enrollment: {df['total_enrollment_race'].max():,}")

# Check urm_share boundary validity
boundary_violations = df.filter(
    (pl.col("urm_share") < 0.0) | (pl.col("urm_share") > 1.0)
).shape[0]
boundary_ok = boundary_violations == 0
print(f"[{'PASS' if boundary_ok else 'FAIL'}] urm_share in [0,1]: {boundary_violations} violations")

# Check urm_enrollment <= total_enrollment for all
consistency_violations = df.filter(
    pl.col("urm_enrollment") > pl.col("total_enrollment_race")
).shape[0]
consistency_ok = consistency_violations == 0
print(f"[{'PASS' if consistency_ok else 'FAIL'}] urm_enrollment <= total: {consistency_violations} violations")

# --- Check 9: [Absence] What's missing? ---
print(f"\n--- Absence: Missing checks ---")
# Are there raw data unitids NOT in the output?
raw_unitids = df_raw["unitid"].unique()
output_unitids = df["unitid"].unique()
missing_from_output = raw_unitids.filter(~raw_unitids.is_in(output_unitids)).len()
extra_in_output = output_unitids.filter(~output_unitids.is_in(raw_unitids)).len()
absence_ok = missing_from_output == 0 and extra_in_output == 0
print(f"[{'PASS' if missing_from_output == 0 else 'WARN'}] Raw unitids in output: "
      f"{missing_from_output} missing (raw has {raw_unitids.len():,}, output has {output_unitids.len():,})")
print(f"[{'PASS' if extra_in_output == 0 else 'FAIL'}] No phantom unitids: {extra_in_output} extra")

# NHPI (code 6) not included in URM -- Plan says URM = Black + Hispanic + AI/AN
# This is standard. Log as INFO.
nhpi_total = (
    df_raw_agg.filter(pl.col("race") == 6)
    .select(pl.col("enrollment_max").sum())
    .item()
)
total_enrollment_all = (
    df_raw_agg.filter(pl.col("race") == RACE_TOTAL)
    .select(pl.col("enrollment_max").sum())
    .item()
)
nhpi_share = nhpi_total / total_enrollment_all if total_enrollment_all > 0 else 0
print(f"[INFO] NHPI (code 6) excluded from URM: {nhpi_total:,} enrollment ({nhpi_share:.2%} of total)")
print(f"  This matches Plan definition. Standard URM = Black + Hispanic + AI/AN.")

# --- Check 10: [Downstream] Readiness for join-demographics ---
print(f"\n--- Downstream: Readiness for join-demographics ---")
# join-demographics expects 1:1 join on unitid
unitid_unique = df["unitid"].n_unique() == df.shape[0]
print(f"[{'PASS' if unitid_unique else 'FAIL'}] Unitid is unique (ready for 1:1 join): "
      f"{df['unitid'].n_unique():,} unique vs {df.shape[0]:,} rows")

# Check data types are appropriate for downstream
dtypes_info = {col: str(df[col].dtype) for col in df.columns}
print(f"  Column types: {dtypes_info}")
type_ok = (str(df["unitid"].dtype) in ["Int64", "i64"] and
           str(df["urm_share"].dtype) in ["Float64", "f64"])
print(f"[{'PASS' if type_ok else 'WARN'}] Types appropriate for downstream joins")

# --- Spot-checks (11-15) ---
print(f"\n--- Spot-checks ---")

# Spot-check 11: Pick a specific institution and trace through
# Use institution 100654 from the execution log
sample_uid = 100654
raw_sample = df_raw.filter(pl.col("unitid") == sample_uid)
output_sample = df.filter(pl.col("unitid") == sample_uid)

if output_sample.shape[0] > 0:
    # Get MAX enrollment for race=99
    raw_total_max = raw_sample.filter(pl.col("race") == RACE_TOTAL)["enrollment_fall"].max()
    # Get MAX for each URM race and sum
    raw_urm_sum = 0
    for rc in URM_CODES:
        race_max = raw_sample.filter(pl.col("race") == rc)["enrollment_fall"].max()
        if race_max is not None:
            raw_urm_sum += race_max

    output_total = output_sample["total_enrollment_race"].item()
    output_urm = output_sample["urm_enrollment"].item()
    output_share = output_sample["urm_share"].item()

    trace_total_ok = raw_total_max == output_total
    trace_urm_ok = raw_urm_sum == output_urm
    expected_share = raw_urm_sum / raw_total_max if raw_total_max and raw_total_max > 0 else None
    trace_share_ok = abs(output_share - expected_share) < 1e-6 if expected_share is not None else False

    print(f"[{'PASS' if trace_total_ok and trace_urm_ok and trace_share_ok else 'FAIL'}] "
          f"Spot-check unitid={sample_uid}: "
          f"total={output_total} (raw MAX={raw_total_max}), "
          f"urm={output_urm} (raw SUM-of-MAX={raw_urm_sum}), "
          f"share={output_share:.4f} (expected={expected_share:.4f})")
else:
    print(f"[SKIP] unitid={sample_uid} not in output")

# Spot-check 12: Verify a high-URM institution (urm_share > 0.9)
high_urm = df.filter(pl.col("urm_share") > 0.9).head(1)
if high_urm.shape[0] > 0:
    uid = high_urm["unitid"].item()
    raw_high = df_raw.filter(pl.col("unitid") == uid)
    raw_urm_total = sum(
        raw_high.filter(pl.col("race") == rc)["enrollment_fall"].max() or 0
        for rc in URM_CODES
    )
    raw_race99_max = raw_high.filter(pl.col("race") == RACE_TOTAL)["enrollment_fall"].max()
    expected = raw_urm_total / raw_race99_max if raw_race99_max and raw_race99_max > 0 else 0
    actual = high_urm["urm_share"].item()
    spot12_ok = abs(actual - expected) < 1e-6
    print(f"[{'PASS' if spot12_ok else 'FAIL'}] Spot-check high-URM unitid={uid}: "
          f"share={actual:.4f} (expected={expected:.4f})")

# Spot-check 13: Verify a low-URM institution (urm_share < 0.05)
low_urm = df.filter(pl.col("urm_share") < 0.05).filter(pl.col("urm_share") > 0).head(1)
if low_urm.shape[0] > 0:
    uid = low_urm["unitid"].item()
    raw_low = df_raw.filter(pl.col("unitid") == uid)
    raw_urm_total = sum(
        raw_low.filter(pl.col("race") == rc)["enrollment_fall"].max() or 0
        for rc in URM_CODES
    )
    raw_race99_max = raw_low.filter(pl.col("race") == RACE_TOTAL)["enrollment_fall"].max()
    expected = raw_urm_total / raw_race99_max if raw_race99_max and raw_race99_max > 0 else 0
    actual = low_urm["urm_share"].item()
    spot13_ok = abs(actual - expected) < 1e-6
    print(f"[{'PASS' if spot13_ok else 'FAIL'}] Spot-check low-URM unitid={uid}: "
          f"share={actual:.4f} (expected={expected:.4f})")

# Spot-check 14: Verify URM share by recalculating from raw data for 10 random institutions
import random
random.seed(42)
sample_uids = random.sample(df["unitid"].to_list(), min(10, len(df)))
recalc_mismatches = 0
for uid in sample_uids:
    raw_inst = df_raw.filter(pl.col("unitid") == uid)
    raw_total = raw_inst.filter(pl.col("race") == RACE_TOTAL)["enrollment_fall"].max()
    raw_urm = sum(
        raw_inst.filter(pl.col("race") == rc)["enrollment_fall"].max() or 0
        for rc in URM_CODES
    )
    expected_share = raw_urm / raw_total if raw_total and raw_total > 0 else 0
    actual_share = df.filter(pl.col("unitid") == uid)["urm_share"].item()
    if abs(actual_share - expected_share) > 1e-6:
        recalc_mismatches += 1
        print(f"  MISMATCH unitid={uid}: expected={expected_share:.6f}, actual={actual_share:.6f}")

spot14_ok = recalc_mismatches == 0
print(f"[{'PASS' if spot14_ok else 'FAIL'}] Spot-check 10 random institutions: {recalc_mismatches} mismatches")

# Spot-check 15: Verify sum of URM enrollment across all institutions is reasonable
total_urm_all = df["urm_enrollment"].sum()
total_enrollment_all_output = df["total_enrollment_race"].sum()
overall_urm_share = total_urm_all / total_enrollment_all_output if total_enrollment_all_output > 0 else 0
# US URM share of higher ed is roughly 30-45% as of 2020
spot15_ok = 0.15 <= overall_urm_share <= 0.60
print(f"[{'PASS' if spot15_ok else 'WARN'}] Overall URM share across all institutions: "
      f"{overall_urm_share:.2%} (expected ~30-40% national avg)")

# --- Summary ---
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
    counterfactual_ok, total_match_ok, urm_match_ok, race_codes_ok,
    boundary_ok, consistency_ok, unitid_unique, type_ok,
    spot14_ok, spot15_ok
]
all_passed = all(all_checks)
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["unitid"]:
    if col in df.columns:
        print(f"\n{col} n_unique: {df[col].n_unique()}")

print("\nurm_share quintile distribution:")
for q in [0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0]:
    val = df["urm_share"].quantile(q)
    print(f"  P{int(q*100):3d}: {val:.4f}")

print("\ntotal_enrollment_race quintile distribution:")
for q in [0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0]:
    val = df["total_enrollment_race"].quantile(q)
    print(f"  P{int(q*100):3d}: {val}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:46:30
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_05_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_05_cr1.py:201: DeprecationWarning: `is_in` with a collection of the same datatype is ambiguous and deprecated.
# Please use `implode` to return to previous behavior.
# 
# See https://github.com/pola-rs/polars/issues/22149 for more information.
#   missing_from_output = raw_unitids.filter(~raw_unitids.is_in(output_unitids)).len()
# /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_05_cr1.py:202: DeprecationWarning: `is_in` with a collection of the same datatype is ambiguous and deprecated.
# Please use `implode` to return to previous behavior.
# 
# See https://github.com/pola-rs/polars/issues/22149 for more information.
#   extra_in_output = output_unitids.filter(~output_unitids.is_in(raw_unitids)).len()
# ============================================================
# QA INSPECTION: Stage 6 Step 5 (clean-enrollment-race)
# ============================================================
# Loaded output: 5,837 rows x 4 cols
# Loaded raw: 352,410 rows x 7 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,837 (expected 2,000-8,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Counterfactual: Independent MAX aggregation validation ---
# [PASS] Independent MAX ratio check: mean=1.000000, min=1.000000, max=1.000000
# [PASS] Output total_enrollment matches independent MAX: 0 mismatches out of 5,837
# 
# --- Semantic: URM code verification ---
# [PASS] URM enrollment matches independent calculation: 0 mismatches
# [PASS] Raw race codes match Portal standard: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# 
# --- Boundary: Edge cases ---
#   urm_share == 0: 175 institutions
#   urm_share == 1: 188 institutions
#   total_enrollment < 10: 61 institutions
#   Minimum total_enrollment: 1
#   Maximum total_enrollment: 111,599
# [PASS] urm_share in [0,1]: 0 violations
# [PASS] urm_enrollment <= total: 0 violations
# 
# --- Absence: Missing checks ---
# [PASS] Raw unitids in output: 0 missing (raw has 5,837, output has 5,837)
# [PASS] No phantom unitids: 0 extra
# [INFO] NHPI (code 6) excluded from URM: 49,600 enrollment (0.30% of total)
#   This matches Plan definition. Standard URM = Black + Hispanic + AI/AN.
# 
# --- Downstream: Readiness for join-demographics ---
# [PASS] Unitid is unique (ready for 1:1 join): 5,837 unique vs 5,837 rows
#   Column types: {'unitid': 'Int64', 'total_enrollment_race': 'Int64', 'urm_enrollment': 'Int64', 'urm_share': 'Float64'}
# [PASS] Types appropriate for downstream joins
# 
# --- Spot-checks ---
# [PASS] Spot-check unitid=100654: total=5093 (raw MAX=5093), urm=4668 (raw SUM-of-MAX=4668), share=0.9166 (expected=0.9166)
# [PASS] Spot-check high-URM unitid=476568: share=1.0000 (expected=1.0000)
# [PASS] Spot-check low-URM unitid=201140: share=0.0455 (expected=0.0455)
# [PASS] Spot-check 10 random institutions: 0 mismatches
# [PASS] Overall URM share across all institutions: 33.82% (expected ~30-40% national avg)
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 4)
# ┌────────┬───────────────────────┬────────────────┬───────────┐
# │ unitid ┆ total_enrollment_race ┆ urm_enrollment ┆ urm_share │
# │ ---    ┆ ---                   ┆ ---            ┆ ---       │
# │ i64    ┆ i64                   ┆ i64            ┆ f64       │
# ╞════════╪═══════════════════════╪════════════════╪═══════════╡
# │ 110538 ┆ 15747                 ┆ 6149           ┆ 0.390487  │
# │ 112455 ┆ 86                    ┆ 66             ┆ 0.767442  │
# │ 475468 ┆ 226                   ┆ 105            ┆ 0.464602  │
# │ 476568 ┆ 8                     ┆ 8              ┆ 1.0       │
# │ 476610 ┆ 52                    ┆ 47             ┆ 0.903846  │
# │ …      ┆ …                     ┆ …              ┆ …         │
# │ 482149 ┆ 5674                  ┆ 1961           ┆ 0.345612  │
# │ 482422 ┆ 178                   ┆ 77             ┆ 0.432584  │
# │ 482431 ┆ 1619                  ┆ 778            ┆ 0.480544  │
# │ 483018 ┆ 116                   ┆ 51             ┆ 0.439655  │
# │ 483647 ┆ 34                    ┆ 19             ┆ 0.558824  │
# └────────┴───────────────────────┴────────────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 5)
# ┌────────────┬───────────────┬───────────────────────┬────────────────┬───────────┐
# │ statistic  ┆ unitid        ┆ total_enrollment_race ┆ urm_enrollment ┆ urm_share │
# │ ---        ┆ ---           ┆ ---                   ┆ ---            ┆ ---       │
# │ str        ┆ f64           ┆ f64                   ┆ f64            ┆ f64       │
# ╞════════════╪═══════════════╪═══════════════════════╪════════════════╪═══════════╡
# │ count      ┆ 5837.0        ┆ 5837.0                ┆ 5837.0         ┆ 5837.0    │
# │ null_count ┆ 0.0           ┆ 0.0                   ┆ 0.0            ┆ 0.0       │
# │ mean       ┆ 283873.483981 ┆ 2817.44355            ┆ 952.847353     ┆ 0.381563  │
# │ std        ┆ 137934.790145 ┆ 6363.847993           ┆ 2595.537695    ┆ 0.279133  │
# │ min        ┆ 100654.0      ┆ 1.0                   ┆ 0.0            ┆ 0.0       │
# │ 25%        ┆ 169734.0      ┆ 109.0                 ┆ 35.0           ┆ 0.154067  │
# │ 50%        ┆ 219921.0      ┆ 519.0                 ┆ 163.0          ┆ 0.310976  │
# │ 75%        ┆ 445267.0      ┆ 2505.0                ┆ 625.0          ┆ 0.565657  │
# │ max        ┆ 496423.0      ┆ 111599.0              ┆ 51922.0        ┆ 1.0       │
# └────────────┴───────────────┴───────────────────────┴────────────────┴───────────┘
# 
# Key column value counts:
# 
# unitid n_unique: 5837
# 
# urm_share quintile distribution:
#   P  0: 0.0000
#   P  5: 0.0385
#   P 10: 0.0750
#   P 25: 0.1541
#   P 50: 0.3110
#   P 75: 0.5657
#   P 90: 0.8348
#   P 95: 0.9525
#   P100: 1.0000
# 
# total_enrollment_race quintile distribution:
#   P  0: 1.0
#   P  5: 25.0
#   P 10: 41.0
#   P 25: 109.0
#   P 50: 519.0
#   P 75: 2505.0
#   P 90: 7662.0
#   P 95: 13408.0
#   P100: 111599.0
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
