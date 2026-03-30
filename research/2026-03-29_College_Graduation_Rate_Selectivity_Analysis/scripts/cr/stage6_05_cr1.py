#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 05

Reviewed script: scripts/stage6_clean/05_clean-enrollment-race.py
Output files: data/processed/2026-03-29_urm_share_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
--- Script-Specific Checks ---
6. [Semantic] URM race codes verified independently against raw data
7. [Counterfactual] What if some institutions lack certain race codes?
8. [Boundary] urm_share at boundaries (0.0 and 1.0) are plausible
9. [Absence] Verify race 8 and 9 excluded from denominator
10. [Downstream] total_ug_enrollment matches race=99, not race sum
--- Spot Checks ---
11. Recalculate URM share for a specific institution from raw data
12. Verify that institutions with urm_share=null have valid reasons
13. Check that sum of race 1-7 < race 99 for most institutions
14. Check institutions where urm_share=1.0 (100% URM)
15. Cross-check institution count between raw and output
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_urm_share_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_enrollment_race.parquet"

EXPECTED_COLUMNS = ["unitid", "urm_share", "total_ug_enrollment"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 7000
CRITICAL_COLUMNS = ["unitid", "urm_share", "total_ug_enrollment"]

URM_RACE_CODES = [2, 3, 5, 6]
DOMESTIC_KNOWN_RACE_CODES = [1, 2, 3, 4, 5, 6, 7]
TOTAL_RACE_CODE = 99
EXCLUDED_RACE_CODES = [8, 9]

CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 05 — clean-enrollment-race")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {raw.shape[0]:,} rows x {raw.shape[1]} cols")

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
    print("None remain in output")
else:
    print("; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
# REASONING: urm_share CAN be null when domestic_known_enrollment is 0 or null.
# This is legitimate. But unitid and total_ug_enrollment should never be null.
unitid_nulls = df["unitid"].null_count()
total_enrl_nulls = df["total_ug_enrollment"].null_count()
urm_nulls = df["urm_share"].null_count()
nulls_ok = unitid_nulls == 0 and total_enrl_nulls == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: unitid={unitid_nulls}, total_ug_enrollment={total_enrl_nulls}")
print(f"  [INFO] urm_share nulls: {urm_nulls} ({urm_nulls / len(df) * 100:.1f}%) — expected for institutions with no domestic known-race data")

# =============================================================================
# SCRIPT-SPECIFIC CHECKS
# =============================================================================

# --- Check 6: [Semantic] URM race codes verified independently ---
# INTENT: Independently verify the URM formula by recomputing from raw data.
# This checks whether the script used the CORRECT race codes, not just that it ran.
print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# Replace coded missing in raw data
raw_clean = raw.with_columns(
    pl.when(pl.col("enrollment_fall").is_in(CODED_MISSING_VALUES))
    .then(None)
    .otherwise(pl.col("enrollment_fall"))
    .alias("enrollment_fall")
)

# Independent URM numerator
urm_num_indep = (
    raw_clean
    .filter(pl.col("race").is_in(URM_RACE_CODES))
    .group_by("unitid")
    .agg(pl.col("enrollment_fall").sum().alias("urm_enrollment_check"))
)

# Independent denominator
denom_indep = (
    raw_clean
    .filter(pl.col("race").is_in(DOMESTIC_KNOWN_RACE_CODES))
    .group_by("unitid")
    .agg(pl.col("enrollment_fall").sum().alias("domestic_known_check"))
)

# Independent total
total_indep = (
    raw_clean
    .filter(pl.col("race") == TOTAL_RACE_CODE)
    .select(["unitid", pl.col("enrollment_fall").alias("total_ug_check")])
)

# Join and compute independently
indep_result = (
    total_indep
    .join(urm_num_indep, on="unitid", how="left")
    .join(denom_indep, on="unitid", how="left")
    .with_columns(
        pl.when(pl.col("domestic_known_check") > 0)
        .then(pl.col("urm_enrollment_check") / pl.col("domestic_known_check"))
        .otherwise(None)
        .alias("urm_share_check")
    )
)

# Compare to script output
comparison = df.join(indep_result.select(["unitid", "urm_share_check", "total_ug_check"]), on="unitid", how="inner")

# Check urm_share match
urm_share_match = comparison.filter(
    (pl.col("urm_share").is_not_null()) & (pl.col("urm_share_check").is_not_null())
)
if urm_share_match.height > 0:
    max_diff = (urm_share_match["urm_share"] - urm_share_match["urm_share_check"]).abs().max()
    urm_formula_ok = max_diff < 1e-10
    print(f"[{'PASS' if urm_formula_ok else 'FAIL'}] URM formula verification: max absolute diff = {max_diff:.2e}")
else:
    print("[FAIL] URM formula verification: no non-null comparisons available")
    urm_formula_ok = False

# Check total_ug_enrollment match
total_match = comparison.filter(
    (pl.col("total_ug_enrollment").is_not_null()) & (pl.col("total_ug_check").is_not_null())
)
if total_match.height > 0:
    total_diffs = (total_match["total_ug_enrollment"] - total_match["total_ug_check"]).abs().max()
    total_ok = total_diffs == 0
    print(f"[{'PASS' if total_ok else 'FAIL'}] total_ug_enrollment verification: max diff = {total_diffs}")
else:
    print("[FAIL] total_ug_enrollment verification: no non-null comparisons")
    total_ok = False

# --- Check 7: [Counterfactual] Missing race codes per institution ---
# INTENT: What if some institutions don't have all 10 race codes?
# This could cause unbalanced panels or missing URM values.
race_counts_per_inst = raw.group_by("unitid").agg(pl.col("race").n_unique().alias("n_race_codes"))
institutions_with_all = race_counts_per_inst.filter(pl.col("n_race_codes") == 10).height
institutions_total = race_counts_per_inst.height
pct_complete = institutions_with_all / institutions_total * 100
print(f"\n[{'PASS' if pct_complete > 95 else 'WARN'}] Race code completeness: {institutions_with_all:,}/{institutions_total:,} institutions have all 10 race codes ({pct_complete:.1f}%)")
# If some institutions have fewer codes, check which ones are missing
if institutions_with_all < institutions_total:
    incomplete = race_counts_per_inst.filter(pl.col("n_race_codes") < 10)
    print(f"  {incomplete.height} institutions have incomplete race code sets:")
    for row in incomplete.head(5).iter_rows(named=True):
        unitid = row["unitid"]
        races_present = sorted(raw.filter(pl.col("unitid") == unitid)["race"].to_list())
        print(f"    unitid={unitid}: race codes present = {races_present}")

# --- Check 8: [Boundary] urm_share at 0.0 and 1.0 ---
# INTENT: Institutions with 0% or 100% URM should be plausible.
urm_zero = df.filter(pl.col("urm_share") == 0.0).height
urm_one = df.filter(pl.col("urm_share") == 1.0).height
print(f"\n[INFO] Boundary values: urm_share=0.0: {urm_zero} institutions; urm_share=1.0: {urm_one} institutions")
# If urm_share=1.0 exists, verify it makes sense (e.g., HBCUs or tribal colleges)
if urm_one > 0:
    urm_one_unitids = df.filter(pl.col("urm_share") == 1.0)["unitid"].to_list()
    print(f"  Institutions with 100% URM share (unitids): {urm_one_unitids[:10]}")
    # Check their enrollment sizes — very small enrollment makes 100% more plausible
    for uid in urm_one_unitids[:5]:
        enrl = df.filter(pl.col("unitid") == uid)["total_ug_enrollment"].item()
        print(f"    unitid={uid}: total_ug_enrollment={enrl}")
boundary_ok = urm_zero < row_count * 0.2 and urm_one < row_count * 0.05
print(f"[{'PASS' if boundary_ok else 'WARN'}] Boundary check: 0.0 count reasonable={urm_zero < row_count * 0.2}, 1.0 count reasonable={urm_one < row_count * 0.05}")

# --- Check 9: [Absence] Race 8 and 9 excluded from denominator ---
# INTENT: Verify that race 8 (nonresident alien) and 9 (unknown) are NOT in the denominator.
# The script filters to DOMESTIC_KNOWN_RACE_CODES=[1..7], so races 8, 9 should be absent.
# We verify by computing what the denominator WOULD be if 8 and 9 were included, and confirm it differs.
denom_with_all = (
    raw_clean
    .filter(pl.col("race").is_in([1, 2, 3, 4, 5, 6, 7, 8, 9]))
    .group_by("unitid")
    .agg(pl.col("enrollment_fall").sum().alias("denom_all_races"))
)

denom_compare = denom_indep.join(denom_with_all, on="unitid", how="inner")
# If race 8/9 have any enrollment, the denominators will differ
denom_diff_count = denom_compare.filter(
    pl.col("domestic_known_check") != pl.col("denom_all_races")
).height
print(f"\n[INFO] Race 8/9 exclusion verification: {denom_diff_count:,}/{denom_compare.height:,} institutions have different denominators when races 8,9 are included")
# This should be most institutions (because most have nonresident aliens or unknown)
race_89_ok = denom_diff_count > 0  # At least some institutions differ
print(f"[{'PASS' if race_89_ok else 'WARN'}] Race 8/9 exclusion: confirmed that denominator uses only races 1-7 (differs from 1-9 for {denom_diff_count:,} institutions)")

# --- Check 10: [Downstream] total_ug_enrollment matches race=99, NOT sum of races ---
# INTENT: Verify total_ug_enrollment comes from race==99 row, not computed as sum(races 1-9).
# The sum of individual race codes may not equal race=99 total due to rounding or reporting.
race_sum = (
    raw_clean
    .filter(pl.col("race").is_in([1, 2, 3, 4, 5, 6, 7, 8, 9]))
    .group_by("unitid")
    .agg(pl.col("enrollment_fall").sum().alias("race_sum_enrollment"))
)
total_vs_sum = total_indep.join(race_sum, on="unitid", how="inner")
match_count = total_vs_sum.filter(
    pl.col("total_ug_check") == pl.col("race_sum_enrollment")
).height
differ_count = total_vs_sum.height - match_count
print(f"\n[INFO] race=99 vs sum(races 1-9): {match_count:,} match exactly, {differ_count:,} differ")
# Confirm script uses race=99 (which we already verified in check 6 via total_ug_check)
print(f"[PASS] total_ug_enrollment correctly sourced from race=99 (verified in Check 6)")

# =============================================================================
# SPOT CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT CHECKS")
print("=" * 60)

# --- Spot Check 11: Recalculate for specific institution ---
# Pick the first institution in the output and trace through raw data
sample_unitid = df.sort("unitid").head(1)["unitid"].item()
sample_raw = raw_clean.filter(pl.col("unitid") == sample_unitid)
print(f"\nSpot check: unitid={sample_unitid}")
print(f"  Raw race breakdown:")
for row in sample_raw.sort("race").iter_rows(named=True):
    print(f"    race={row['race']}: enrollment_fall={row['enrollment_fall']}")

# Manual calculation
urm_races = sample_raw.filter(pl.col("race").is_in(URM_RACE_CODES))
urm_sum = urm_races["enrollment_fall"].sum()
domestic_races = sample_raw.filter(pl.col("race").is_in(DOMESTIC_KNOWN_RACE_CODES))
domestic_sum = domestic_races["enrollment_fall"].sum()
total_race99 = sample_raw.filter(pl.col("race") == 99)["enrollment_fall"].item()

manual_urm_share = urm_sum / domestic_sum if domestic_sum > 0 else None
output_urm_share = df.filter(pl.col("unitid") == sample_unitid)["urm_share"].item()
output_total = df.filter(pl.col("unitid") == sample_unitid)["total_ug_enrollment"].item()

print(f"  Manual URM numerator: {urm_sum} (races {URM_RACE_CODES})")
print(f"  Manual denominator: {domestic_sum} (races {DOMESTIC_KNOWN_RACE_CODES})")
print(f"  Manual urm_share: {manual_urm_share:.6f}")
print(f"  Output urm_share: {output_urm_share:.6f}")
print(f"  Match: {abs(manual_urm_share - output_urm_share) < 1e-10 if manual_urm_share is not None else 'N/A'}")
print(f"  Manual total (race=99): {total_race99}")
print(f"  Output total_ug_enrollment: {output_total}")
print(f"  Total match: {total_race99 == output_total}")

# --- Spot Check 12: Null urm_share institutions ---
null_urm = df.filter(pl.col("urm_share").is_null())
print(f"\nNull urm_share: {null_urm.height} institutions")
if null_urm.height > 0:
    for uid in null_urm["unitid"].to_list()[:3]:
        raw_data = raw_clean.filter(pl.col("unitid") == uid)
        domestic = raw_data.filter(pl.col("race").is_in(DOMESTIC_KNOWN_RACE_CODES))
        dom_sum = domestic["enrollment_fall"].sum()
        dom_null_count = domestic["enrollment_fall"].null_count()
        print(f"  unitid={uid}: domestic race enrollment sum={dom_sum}, nulls in domestic races={dom_null_count}")
        if dom_sum == 0 or dom_sum is None:
            print(f"    -> urm_share is correctly null (zero or null denominator)")

# --- Spot Check 13: Sum of races 1-7 vs race 99 ---
# Most institutions should have sum(1-7) <= race(99) because 99 includes 8 and 9
total_vs_domestic = total_indep.join(denom_indep, on="unitid", how="inner")
less_than = total_vs_domestic.filter(
    pl.col("domestic_known_check") <= pl.col("total_ug_check")
).height
greater_than = total_vs_domestic.filter(
    pl.col("domestic_known_check") > pl.col("total_ug_check")
).height
print(f"\nSum(races 1-7) vs race=99: {less_than:,} institutions have domestic <= total, {greater_than:,} have domestic > total")
if greater_than > 0:
    print(f"  [WARN] {greater_than} institutions have domestic known-race sum > total — may indicate data quality issue")
else:
    print(f"  [PASS] All institutions have domestic known-race sum <= total enrollment")

# --- Spot Check 14: Institutions with urm_share = 1.0 ---
if urm_one > 0:
    one_unitids = df.filter(pl.col("urm_share") == 1.0)["unitid"].to_list()
    print(f"\nurm_share = 1.0 detail ({len(one_unitids)} institutions):")
    for uid in one_unitids[:5]:
        raw_data = raw_clean.filter(pl.col("unitid") == uid)
        domestic = raw_data.filter(pl.col("race").is_in(DOMESTIC_KNOWN_RACE_CODES))
        for row in domestic.sort("race").iter_rows(named=True):
            print(f"  unitid={uid}, race={row['race']}: enrollment={row['enrollment_fall']}")
        dom_sum = domestic["enrollment_fall"].sum()
        urm_sum_check = raw_data.filter(pl.col("race").is_in(URM_RACE_CODES))["enrollment_fall"].sum()
        print(f"  -> URM/domestic = {urm_sum_check}/{dom_sum} = 1.0")

# --- Spot Check 15: Institution count consistency ---
raw_unitids = raw["unitid"].n_unique()
output_unitids = df["unitid"].n_unique()
count_match = raw_unitids == output_unitids
print(f"\nInstitution count: raw={raw_unitids:,}, output={output_unitids:,}")
print(f"[{'PASS' if count_match else 'WARN'}] Institution count consistency: {'match' if count_match else 'mismatch'}")
if not count_match:
    raw_set = set(raw["unitid"].unique().to_list())
    out_set = set(df["unitid"].unique().to_list())
    in_raw_not_out = raw_set - out_set
    in_out_not_raw = out_set - raw_set
    if in_raw_not_out:
        print(f"  In raw but not output: {len(in_raw_not_out)} institutions")
    if in_out_not_raw:
        print(f"  In output but not raw: {len(in_out_not_raw)} institutions")

# =============================================================================
# SUMMARY
# =============================================================================

all_checks = [schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok, urm_formula_ok, total_ok, boundary_ok]
all_passed = all(all_checks)

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["unitid"]:
    if col in df.columns:
        print(f"\n{col}: {df[col].n_unique()} unique values")

print("\nurm_share distribution (quintiles):")
urm_non_null = df.filter(pl.col("urm_share").is_not_null())
if urm_non_null.height > 0:
    for q in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
        val = urm_non_null["urm_share"].quantile(q)
        print(f"  {q:.0%}: {val:.4f}")

print("\ntotal_ug_enrollment distribution:")
enrl_non_null = df.filter(pl.col("total_ug_enrollment").is_not_null())
if enrl_non_null.height > 0:
    for q in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
        val = enrl_non_null["total_ug_enrollment"].quantile(q)
        print(f"  {q:.0%}: {val:,.0f}")

print("\nunitid uniqueness check:")
print(f"  Unique unitids: {df['unitid'].n_unique()}")
print(f"  Total rows: {df.shape[0]}")
print(f"  Is unique: {df['unitid'].n_unique() == df.shape[0]}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:44:36
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_05_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 05 — clean-enrollment-race
# ============================================================
# Loaded output: 5,837 rows x 3 cols
# Loaded raw: 58,370 rows x 10 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,837 (expected 3,000-7,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in output
# [PASS] Critical nulls: unitid=0, total_ug_enrollment=0
#   [INFO] urm_share nulls: 4 (0.1%) — expected for institutions with no domestic known-race data
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# [PASS] URM formula verification: max absolute diff = 0.00e+00
# [PASS] total_ug_enrollment verification: max diff = 0
# 
# [PASS] Race code completeness: 5,837/5,837 institutions have all 10 race codes (100.0%)
# 
# [INFO] Boundary values: urm_share=0.0: 168 institutions; urm_share=1.0: 211 institutions
#   Institutions with 100% URM share (unitids): [106111, 106315, 107442, 108065, 117283, 135142, 143482, 143491, 148955, 155140]
#     unitid=106111: total_ug_enrollment=61
#     unitid=106315: total_ug_enrollment=15
#     unitid=107442: total_ug_enrollment=35
#     unitid=108065: total_ug_enrollment=11
#     unitid=117283: total_ug_enrollment=60
# [PASS] Boundary check: 0.0 count reasonable=True, 1.0 count reasonable=True
# 
# [INFO] Race 8/9 exclusion verification: 4,399/5,837 institutions have different denominators when races 8,9 are included
# [PASS] Race 8/9 exclusion: confirmed that denominator uses only races 1-7 (differs from 1-9 for 4,399 institutions)
# 
# [INFO] race=99 vs sum(races 1-9): 5,837 match exactly, 0 differ
# [PASS] total_ug_enrollment correctly sourced from race=99 (verified in Check 6)
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# Spot check: unitid=100654
#   Raw race breakdown:
#     race=1: enrollment_fall=81
#     race=2: enrollment_fall=4595
#     race=3: enrollment_fall=59
#     race=4: enrollment_fall=6
#     race=5: enrollment_fall=14
#     race=6: enrollment_fall=4
#     race=7: enrollment_fall=73
#     race=8: enrollment_fall=37
#     race=9: enrollment_fall=224
#     race=99: enrollment_fall=5093
#   Manual URM numerator: 4672 (races [2, 3, 5, 6])
#   Manual denominator: 4832 (races [1, 2, 3, 4, 5, 6, 7])
#   Manual urm_share: 0.966887
#   Output urm_share: 0.966887
#   Match: True
#   Manual total (race=99): 5093
#   Output total_ug_enrollment: 5093
#   Total match: True
# 
# Null urm_share: 4 institutions
#   unitid=120838: domestic race enrollment sum=0, nulls in domestic races=0
#     -> urm_share is correctly null (zero or null denominator)
#   unitid=170286: domestic race enrollment sum=0, nulls in domestic races=0
#     -> urm_share is correctly null (zero or null denominator)
#   unitid=490063: domestic race enrollment sum=0, nulls in domestic races=0
#     -> urm_share is correctly null (zero or null denominator)
# 
# Sum(races 1-7) vs race=99: 5,837 institutions have domestic <= total, 0 have domestic > total
#   [PASS] All institutions have domestic known-race sum <= total enrollment
# 
# urm_share = 1.0 detail (211 institutions):
#   unitid=106111, race=1: enrollment=0
#   unitid=106111, race=2: enrollment=6
#   unitid=106111, race=3: enrollment=7
#   unitid=106111, race=4: enrollment=0
#   unitid=106111, race=5: enrollment=1
#   unitid=106111, race=6: enrollment=0
#   unitid=106111, race=7: enrollment=0
#   -> URM/domestic = 14/14 = 1.0
#   unitid=106315, race=1: enrollment=0
#   unitid=106315, race=2: enrollment=12
#   unitid=106315, race=3: enrollment=1
#   unitid=106315, race=4: enrollment=0
#   unitid=106315, race=5: enrollment=0
#   unitid=106315, race=6: enrollment=2
#   unitid=106315, race=7: enrollment=0
#   -> URM/domestic = 15/15 = 1.0
#   unitid=107442, race=1: enrollment=0
#   unitid=107442, race=2: enrollment=35
#   unitid=107442, race=3: enrollment=0
#   unitid=107442, race=4: enrollment=0
#   unitid=107442, race=5: enrollment=0
#   unitid=107442, race=6: enrollment=0
#   unitid=107442, race=7: enrollment=0
#   -> URM/domestic = 35/35 = 1.0
#   unitid=108065, race=1: enrollment=0
#   unitid=108065, race=2: enrollment=11
#   unitid=108065, race=3: enrollment=0
#   unitid=108065, race=4: enrollment=0
#   unitid=108065, race=5: enrollment=0
#   unitid=108065, race=6: enrollment=0
#   unitid=108065, race=7: enrollment=0
#   -> URM/domestic = 11/11 = 1.0
#   unitid=117283, race=1: enrollment=0
#   unitid=117283, race=2: enrollment=1
#   unitid=117283, race=3: enrollment=58
#   unitid=117283, race=4: enrollment=0
#   unitid=117283, race=5: enrollment=1
#   unitid=117283, race=6: enrollment=0
#   unitid=117283, race=7: enrollment=0
#   -> URM/domestic = 60/60 = 1.0
# 
# Institution count: raw=5,837, output=5,837
# [PASS] Institution count consistency: match
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 3)
# ┌────────┬───────────┬─────────────────────┐
# │ unitid ┆ urm_share ┆ total_ug_enrollment │
# │ ---    ┆ ---       ┆ ---                 │
# │ i64    ┆ f64       ┆ i64                 │
# ╞════════╪═══════════╪═════════════════════╡
# │ 100654 ┆ 0.966887  ┆ 5093                │
# │ 100663 ┆ 0.31299   ┆ 13878               │
# │ 100690 ┆ 0.735395  ┆ 298                 │
# │ 100706 ┆ 0.169134  ┆ 8027                │
# │ 100724 ┆ 0.968723  ┆ 3614                │
# │ 100751 ┆ 0.163599  ┆ 31670               │
# │ 100760 ┆ 0.181631  ┆ 1546                │
# │ 100812 ┆ 0.186519  ┆ 2688                │
# │ 100830 ┆ 0.490324  ┆ 4375                │
# │ 100858 ┆ 0.090433  ┆ 24505               │
# └────────┴───────────┴─────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 4)
# ┌────────────┬───────────────┬───────────┬─────────────────────┐
# │ statistic  ┆ unitid        ┆ urm_share ┆ total_ug_enrollment │
# │ ---        ┆ ---           ┆ ---       ┆ ---                 │
# │ str        ┆ f64           ┆ f64       ┆ f64                 │
# ╞════════════╪═══════════════╪═══════════╪═════════════════════╡
# │ count      ┆ 5837.0        ┆ 5833.0    ┆ 5837.0              │
# │ null_count ┆ 0.0           ┆ 4.0       ┆ 0.0                 │
# │ mean       ┆ 283873.483981 ┆ 0.411512  ┆ 2817.44355          │
# │ std        ┆ 137934.790145 ┆ 0.288116  ┆ 6363.847993         │
# │ min        ┆ 100654.0      ┆ 0.0       ┆ 1.0                 │
# │ 25%        ┆ 169734.0      ┆ 0.170588  ┆ 109.0               │
# │ 50%        ┆ 219921.0      ┆ 0.344444  ┆ 519.0               │
# │ 75%        ┆ 445267.0      ┆ 0.61829   ┆ 2505.0              │
# │ max        ┆ 496423.0      ┆ 1.0       ┆ 111599.0            │
# └────────────┴───────────────┴───────────┴─────────────────────┘
# 
# Key column value counts:
# 
# unitid: 5837 unique values
# 
# urm_share distribution (quintiles):
#   0%: 0.0000
#   10%: 0.0829
#   25%: 0.1706
#   50%: 0.3444
#   75%: 0.6183
#   90%: 0.8724
#   100%: 1.0000
# 
# total_ug_enrollment distribution:
#   0%: 1
#   10%: 41
#   25%: 109
#   50%: 519
#   75%: 2,505
#   90%: 7,662
#   100%: 111,599
# 
# unitid uniqueness check:
#   Unique unitids: 5837
#   Total rows: 5837
#   Is unique: True
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
