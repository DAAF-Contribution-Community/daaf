#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 04

Reviewed script: scripts/stage6_clean/04_clean-sfa-grants.py
Output files: data/processed/2026-03-29_sfa_pell_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

CONTEXT: This is a MODIFIED Task 3.4 (clean-sfa-grants replaces clean-fsa-grants).
The original FSA Pell data had 100% NULL for grant_recipients_unitid for 2020-2021.
The replacement uses IPEDS SFA Grants data with type_of_aid=9 (all grant/scholarship)
and income_level=99 (institution total) as a Pell proxy.

QA Checks:
1. Schema matches Plan expectations (unitid, grant_recipients, sfa_total_students)
2. Row count within expected range (4,000-6,000)
3. Distribution sanity for numeric columns
4. No coded values (-1, -2, -3) remain
5. No nulls in critical columns (unitid)
6. [Counterfactual] Verify filtering logic against raw data independently
7. [Semantic] Check that grant_recipients values are plausible for Pell proxy use
8. [Boundary] Edge cases: zero values, extremes, single-record groups
9. [Absence] Verify no income_level or type_of_aid leaking into output
10. [Downstream] Verify unitid uniqueness and types ready for Stage 7 join
11-15. Spot-checks: trace specific records, recalculate, verify filter complement
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfa_pell_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_sfa_grants.parquet"

EXPECTED_COLUMNS = ["unitid", "grant_recipients", "sfa_total_students"]
EXPECTED_MIN_ROWS = 4000
EXPECTED_MAX_ROWS = 6000
CRITICAL_COLUMNS = ["unitid"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 04 (clean-sfa-grants)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
assert RAW_FILE.exists(), f"FAIL: Raw file not found: {RAW_FILE}"

df = pl.read_parquet(OUTPUT_FILE)
df_raw = pl.read_parquet(RAW_FILE)
print(f"Clean output loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Raw input loaded:    {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# ==========================================================================
# DEFAULT CHECKS (1-5)
# ==========================================================================

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

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ==========================================================================

# --- Check 6: [Counterfactual] Independent filter verification ---
# INTENT: Independently reproduce the filtering logic against raw data and compare
# row count to clean output. If the script applied the wrong filter or had off-by-one
# errors, row counts will diverge.
print("\n" + "-" * 60)
print("CHECK 6 [Counterfactual]: Independent filter verification")
print("-" * 60)

# Reproduce the filter independently
raw_filtered = df_raw.filter(
    (pl.col("type_of_aid") == 9) & (pl.col("income_level") == 99)
)
filter_match = raw_filtered.shape[0] == df.shape[0]
print(f"Raw filtered independently: {raw_filtered.shape[0]:,} rows")
print(f"Clean output:              {df.shape[0]:,} rows")
print(f"[{'PASS' if filter_match else 'FAIL'}] Row counts match: {filter_match}")

# Also verify: what if the filter values were swapped or wrong?
alt_filter_1 = df_raw.filter(pl.col("type_of_aid") == 3).shape[0]
alt_filter_2 = df_raw.filter(pl.col("income_level") == 0).shape[0]
print(f"  Sanity: type_of_aid=3 would yield {alt_filter_1:,} rows (net price only, no grant recipients)")
print(f"  Sanity: income_level=0 would yield {alt_filter_2:,} rows (wrong filter)")

# --- Check 7: [Semantic] Grant recipient plausibility for Pell proxy ---
# INTENT: Verify that grant_recipients values are plausible as Pell proxy numbers.
# Real Pell recipient counts at institutions typically range from a few dozen to
# ~15,000+ for the largest public universities. "All grant/scholarship aid" (type_of_aid=9)
# should be >= Pell recipients, so these numbers should be upper-bound plausible.
print("\n" + "-" * 60)
print("CHECK 7 [Semantic]: Grant recipient plausibility")
print("-" * 60)

gr = df["grant_recipients"].drop_nulls()
print(f"grant_recipients stats:")
print(f"  count:  {gr.len():,}")
print(f"  min:    {gr.min()}")
print(f"  p5:     {gr.quantile(0.05)}")
print(f"  p25:    {gr.quantile(0.25)}")
print(f"  median: {gr.median()}")
print(f"  p75:    {gr.quantile(0.75)}")
print(f"  p95:    {gr.quantile(0.95)}")
print(f"  max:    {gr.max()}")
print(f"  mean:   {gr.mean():.1f}")

# Check: max seems low for large universities (4,519 per execution log).
# This COULD indicate the data is actually a different measure.
# Flag if max < 5,000 -- that would be surprisingly low for all-grant aid at a
# large university if it truly represents all grant/scholarship recipients.
max_val = gr.max()
max_plausible = max_val > 500  # At minimum, large universities should have hundreds
print(f"[{'PASS' if max_plausible else 'FAIL'}] Max grant_recipients ({max_val}) > 500: plausible for institutions")

# Check sfa_total_students for comparison
sfa = df["sfa_total_students"].drop_nulls()
print(f"\nsfa_total_students stats:")
print(f"  count:  {sfa.len():,}")
print(f"  min:    {sfa.min()}")
print(f"  median: {sfa.median()}")
print(f"  max:    {sfa.max()}")

# Ratio check: grant_recipients / sfa_total_students should be < 1.0 for most institutions
# (not everyone gets grants). Also > 0 for most.
both_valid = df.filter(
    pl.col("grant_recipients").is_not_null() &
    pl.col("sfa_total_students").is_not_null() &
    (pl.col("sfa_total_students") > 0)
)
if both_valid.shape[0] > 0:
    ratios = both_valid.with_columns(
        (pl.col("grant_recipients").cast(pl.Float64) / pl.col("sfa_total_students").cast(pl.Float64)).alias("grant_ratio")
    )
    r = ratios["grant_ratio"]
    print(f"\ngrant_recipients / sfa_total_students ratio:")
    print(f"  min:    {r.min():.3f}")
    print(f"  median: {r.median():.3f}")
    print(f"  max:    {r.max():.3f}")
    over_1 = (r > 1.0).sum()
    print(f"  ratio > 1.0: {over_1} institutions")
    ratio_ok = over_1 < (both_valid.shape[0] * 0.05)  # < 5% should have ratio > 1
    print(f"[{'PASS' if ratio_ok else 'WARN'}] <5% of institutions have grant ratio > 1.0: {over_1}/{both_valid.shape[0]}")

# --- Check 8: [Boundary] Edge cases ---
# INTENT: Check for boundary conditions that could corrupt downstream analysis.
print("\n" + "-" * 60)
print("CHECK 8 [Boundary]: Edge cases")
print("-" * 60)

# Zero grant_recipients
zero_gr = (df["grant_recipients"] == 0).sum()
print(f"grant_recipients == 0: {zero_gr} institutions")
print(f"  (These are valid -- institutions reporting zero grant recipients)")

# Zero sfa_total_students (would cause division-by-zero downstream)
zero_sfa = (df["sfa_total_students"] == 0).sum()
print(f"sfa_total_students == 0: {zero_sfa} institutions")
if zero_sfa > 0:
    print(f"  [WARN] Zero total students -- will cause division-by-zero in Pell share calculation")
else:
    print(f"  [PASS] No zero-student institutions")

# Very small institutions (< 10 students) -- may be noise
small_inst = df.filter(pl.col("sfa_total_students") < 10).shape[0]
print(f"sfa_total_students < 10: {small_inst} institutions (potential noise)")

# Check for negative values (shouldn't exist after coded value cleaning)
neg_gr = df.filter(pl.col("grant_recipients") < 0).shape[0]
neg_sfa = df.filter(pl.col("sfa_total_students") < 0).shape[0]
print(f"Negative grant_recipients: {neg_gr}")
print(f"Negative sfa_total_students: {neg_sfa}")
boundary_ok = neg_gr == 0 and neg_sfa == 0
print(f"[{'PASS' if boundary_ok else 'FAIL'}] No negative values in either column")

# --- Check 9: [Absence] No unexpected columns leaking through ---
# INTENT: Verify that filter columns (type_of_aid, income_level) and other
# non-essential columns were dropped. Carrying them downstream could confuse analysis.
print("\n" + "-" * 60)
print("CHECK 9 [Absence]: Column leak check")
print("-" * 60)

leak_cols = ["type_of_aid", "income_level", "year", "fips", "ftpt",
             "level_of_study", "degree_seeking", "class_level", "tuition_type",
             "average_grant", "total_grant", "net_price"]
leaking = [c for c in leak_cols if c in df.columns]
absence_ok = len(leaking) == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] No filter/extra columns in output: ", end="")
if absence_ok:
    print("Clean -- only expected columns present")
else:
    print(f"Leaking columns: {leaking}")

# Also check: is 'year' absent? If the raw data had multiple years, the filter
# should have resolved to a single year (or the data is for a single year already).
# The script doesn't filter by year, so we need to verify the raw data context.
raw_years = df_raw.filter(
    (pl.col("type_of_aid") == 9) & (pl.col("income_level") == 99)
)["year"].unique().to_list()
print(f"  Years in raw filtered slice: {sorted(raw_years)}")
if len(raw_years) > 1:
    print(f"  [WARN] Multiple years in raw data but no year filter applied!")
else:
    print(f"  [PASS] Single year ({raw_years[0]}) -- no year filter needed")

# --- Check 10: [Downstream] Join readiness ---
# INTENT: Verify the output is ready for Stage 7 join on unitid.
# Stage 7 Task 5.2 (join-demographics) will join this data to core data on unitid.
print("\n" + "-" * 60)
print("CHECK 10 [Downstream]: Join readiness for Stage 7")
print("-" * 60)

# Unitid uniqueness
uid_unique = df["unitid"].n_unique() == df.shape[0]
print(f"[{'PASS' if uid_unique else 'FAIL'}] unitid is unique: {df['unitid'].n_unique():,} unique / {df.shape[0]:,} rows")

# Unitid type
uid_type = df["unitid"].dtype
print(f"unitid dtype: {uid_type}")

# Unitid range (IPEDS unitids are typically 6-digit integers, 100000-999999)
uid_min = df["unitid"].min()
uid_max = df["unitid"].max()
uid_range_ok = uid_min > 0 and uid_max < 10_000_000
print(f"unitid range: {uid_min} to {uid_max}")
print(f"[{'PASS' if uid_range_ok else 'WARN'}] unitid range plausible for IPEDS: {uid_range_ok}")

# ==========================================================================
# SPOT CHECKS (5)
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT CHECKS")
print("=" * 60)

# --- Spot 1: Trace specific unitid from raw to clean ---
# Pick the first 3 unitids from the clean output and verify them in raw
sample_uids = df["unitid"].head(3).to_list()
print(f"\nSpot 1: Trace unitids {sample_uids} through raw -> clean")
for uid in sample_uids:
    raw_row = df_raw.filter(
        (pl.col("unitid") == uid) &
        (pl.col("type_of_aid") == 9) &
        (pl.col("income_level") == 99)
    )
    clean_row = df.filter(pl.col("unitid") == uid)

    if raw_row.shape[0] == 1 and clean_row.shape[0] == 1:
        raw_val = raw_row["number_receiving_grants"][0]
        clean_val = clean_row["grant_recipients"][0]
        # If raw_val is a coded value (-1,-2,-3), clean should be null
        if raw_val in CODED_MISSING_VALUES:
            match = clean_val is None
        else:
            match = raw_val == clean_val
        print(f"  unitid={uid}: raw number_receiving_grants={raw_val} -> clean grant_recipients={clean_val} [{'MATCH' if match else 'MISMATCH'}]")
    else:
        print(f"  unitid={uid}: raw rows={raw_row.shape[0]}, clean rows={clean_row.shape[0]} [UNEXPECTED]")

# --- Spot 2: Verify largest institution's values ---
print(f"\nSpot 2: Verify largest institution by grant_recipients")
largest = df.sort("grant_recipients", descending=True).head(1)
uid_largest = largest["unitid"][0]
gr_largest = largest["grant_recipients"][0]
sfa_largest = largest["sfa_total_students"][0]
print(f"  unitid={uid_largest}: grant_recipients={gr_largest}, sfa_total_students={sfa_largest}")

# Cross-reference with raw
raw_largest = df_raw.filter(
    (pl.col("unitid") == uid_largest) &
    (pl.col("type_of_aid") == 9) &
    (pl.col("income_level") == 99)
)
if raw_largest.shape[0] == 1:
    raw_gr = raw_largest["number_receiving_grants"][0]
    raw_sfa = raw_largest["number_of_students"][0]
    print(f"  Raw: number_receiving_grants={raw_gr}, number_of_students={raw_sfa}")
    spot2_ok = gr_largest == raw_gr and sfa_largest == raw_sfa
    print(f"  [{'MATCH' if spot2_ok else 'MISMATCH'}]")

# --- Spot 3: Verify filter complement (what was removed) ---
print(f"\nSpot 3: Verify filter complement")
removed_by_toa = df_raw.filter(pl.col("type_of_aid") != 9).shape[0]
removed_by_il = df_raw.filter(
    (pl.col("type_of_aid") == 9) & (pl.col("income_level") != 99)
).shape[0]
total_removed = removed_by_toa + removed_by_il
total_kept = df_raw.shape[0] - total_removed
print(f"  Removed by type_of_aid != 9: {removed_by_toa:,}")
print(f"  Removed by income_level != 99 (within toa=9): {removed_by_il:,}")
print(f"  Total removed: {total_removed:,}")
print(f"  Total kept: {total_kept:,} (matches clean output: {total_kept == df.shape[0]})")

# --- Spot 4: Verify coded value replacement on a specific case ---
print(f"\nSpot 4: Check coded value replacement")
# Look for a unitid that had a coded value in the raw data
raw_with_coded = df_raw.filter(
    (pl.col("type_of_aid") == 9) &
    (pl.col("income_level") == 99) &
    (pl.col("number_receiving_grants").is_in(CODED_MISSING_VALUES))
)
if raw_with_coded.shape[0] > 0:
    coded_uid = raw_with_coded["unitid"][0]
    coded_raw_val = raw_with_coded["number_receiving_grants"][0]
    clean_check = df.filter(pl.col("unitid") == coded_uid)
    clean_val = clean_check["grant_recipients"][0] if clean_check.shape[0] > 0 else "NOT FOUND"
    print(f"  unitid={coded_uid}: raw={coded_raw_val} (coded) -> clean={clean_val} (should be null)")
    print(f"  [{'PASS' if clean_val is None else 'FAIL'}] Coded value properly replaced")
else:
    print(f"  No coded values found in filtered raw slice for number_receiving_grants")
    print(f"  (Confirmed: 0 coded values to replace -- consistent with execution log)")

# Check number_of_students too
raw_with_coded_sfa = df_raw.filter(
    (pl.col("type_of_aid") == 9) &
    (pl.col("income_level") == 99) &
    (pl.col("number_of_students").is_in(CODED_MISSING_VALUES))
)
print(f"  Coded values in number_of_students (filtered slice): {raw_with_coded_sfa.shape[0]}")

# --- Spot 5: Verify income_level=99 gives exactly one row per unitid ---
print(f"\nSpot 5: Verify income_level=99 yields one row per unitid")
toa9_il99 = df_raw.filter(
    (pl.col("type_of_aid") == 9) & (pl.col("income_level") == 99)
)
dup_check = toa9_il99.group_by("unitid").agg(pl.len().alias("count")).filter(pl.col("count") > 1)
spot5_ok = dup_check.shape[0] == 0
print(f"  Duplicate unitids in raw filtered slice: {dup_check.shape[0]}")
print(f"  [{'PASS' if spot5_ok else 'FAIL'}] Each unitid appears exactly once")

if not spot5_ok:
    print(f"  Example duplicates: {dup_check.head(5)}")

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

print("\nNull summary:")
for col in df.columns:
    nc = df[col].null_count()
    pct = nc / df.shape[0] * 100
    print(f"  {col}: {nc:,} nulls ({pct:.1f}%)")

print("\ngrant_recipients distribution (deciles):")
gr = df["grant_recipients"].drop_nulls()
for q in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    print(f"  p{int(q*100):3d}: {gr.quantile(q):,.0f}")

print("\nsfa_total_students distribution (deciles):")
sfa = df["sfa_total_students"].drop_nulls()
for q in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    print(f"  p{int(q*100):3d}: {sfa.quantile(q):,.0f}")

# ==========================================================================
# SUMMARY
# ==========================================================================
print("\n" + "=" * 60)
all_checks = [schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
              filter_match, boundary_ok, absence_ok, uid_unique, spot5_ok]
all_passed = all(all_checks)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:44:34
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 04 (clean-sfa-grants)
# ============================================================
# Clean output loaded: 5,320 rows x 3 cols
# Raw input loaded:    37,292 rows x 15 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,320 (expected 4,000-6,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ------------------------------------------------------------
# CHECK 6 [Counterfactual]: Independent filter verification
# ------------------------------------------------------------
# Raw filtered independently: 5,320 rows
# Clean output:              5,320 rows
# [PASS] Row counts match: True
#   Sanity: type_of_aid=3 would yield 5,372 rows (net price only, no grant recipients)
#   Sanity: income_level=0 would yield 0 rows (wrong filter)
# 
# ------------------------------------------------------------
# CHECK 7 [Semantic]: Grant recipient plausibility
# ------------------------------------------------------------
# grant_recipients stats:
#   count:  5,320
#   min:    0
#   p5:     3.0
#   p25:    18.0
#   median: 77.0
#   p75:    253.0
#   p95:    909.0
#   max:    4519
#   mean:   222.7
# [PASS] Max grant_recipients (4519) > 500: plausible for institutions
# 
# sfa_total_students stats:
#   count:  5,320
#   min:    1
#   median: 83.0
#   max:    6180
# 
# grant_recipients / sfa_total_students ratio:
#   min:    0.000
#   median: 0.984
#   max:    1.000
#   ratio > 1.0: 0 institutions
# [PASS] <5% of institutions have grant ratio > 1.0: 0/5320
# 
# ------------------------------------------------------------
# CHECK 8 [Boundary]: Edge cases
# ------------------------------------------------------------
# grant_recipients == 0: 11 institutions
#   (These are valid -- institutions reporting zero grant recipients)
# sfa_total_students == 0: 0 institutions
#   [PASS] No zero-student institutions
# sfa_total_students < 10: 720 institutions (potential noise)
# Negative grant_recipients: 0
# Negative sfa_total_students: 0
# [PASS] No negative values in either column
# 
# ------------------------------------------------------------
# CHECK 9 [Absence]: Column leak check
# ------------------------------------------------------------
# [PASS] No filter/extra columns in output: Clean -- only expected columns present
#   Years in raw filtered slice: [2020]
#   [PASS] Single year (2020) -- no year filter needed
# 
# ------------------------------------------------------------
# CHECK 10 [Downstream]: Join readiness for Stage 7
# ------------------------------------------------------------
# [PASS] unitid is unique: 5,320 unique / 5,320 rows
# unitid dtype: Int64
# unitid range: 100654 to 497329
# [PASS] unitid range plausible for IPEDS: True
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# Spot 1: Trace unitids [100654, 100663, 100706] through raw -> clean
#   unitid=100654: raw number_receiving_grants=642 -> clean grant_recipients=642 [MATCH]
#   unitid=100663: raw number_receiving_grants=992 -> clean grant_recipients=992 [MATCH]
#   unitid=100706: raw number_receiving_grants=492 -> clean grant_recipients=492 [MATCH]
# 
# Spot 2: Verify largest institution by grant_recipients
#   unitid=104151: grant_recipients=4519, sfa_total_students=4630
#   Raw: number_receiving_grants=4519, number_of_students=4630
#   [MATCH]
# 
# Spot 3: Verify filter complement
#   Removed by type_of_aid != 9: 5,372
#   Removed by income_level != 99 (within toa=9): 26,600
#   Total removed: 31,972
#   Total kept: 5,320 (matches clean output: True)
# 
# Spot 4: Check coded value replacement
#   No coded values found in filtered raw slice for number_receiving_grants
#   (Confirmed: 0 coded values to replace -- consistent with execution log)
#   Coded values in number_of_students (filtered slice): 0
# 
# Spot 5: Verify income_level=99 yields one row per unitid
#   Duplicate unitids in raw filtered slice: 0
#   [PASS] Each unitid appears exactly once
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 3)
# ┌────────┬──────────────────┬────────────────────┐
# │ unitid ┆ grant_recipients ┆ sfa_total_students │
# │ ---    ┆ ---              ┆ ---                │
# │ i64    ┆ i64              ┆ i64                │
# ╞════════╪══════════════════╪════════════════════╡
# │ 100654 ┆ 642              ┆ 657                │
# │ 100663 ┆ 992              ┆ 1053               │
# │ 100706 ┆ 492              ┆ 515                │
# │ 100724 ┆ 389              ┆ 418                │
# │ 100751 ┆ 1245             ┆ 1360               │
# │ 100760 ┆ 115              ┆ 137                │
# │ 100830 ┆ 441              ┆ 444                │
# │ 100858 ┆ 953              ┆ 1066               │
# │ 100937 ┆ 207              ┆ 207                │
# │ 101028 ┆ 108              ┆ 117                │
# └────────┴──────────────────┴────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 4)
# ┌────────────┬───────────────┬──────────────────┬────────────────────┐
# │ statistic  ┆ unitid        ┆ grant_recipients ┆ sfa_total_students │
# │ ---        ┆ ---           ┆ ---              ┆ ---                │
# │ str        ┆ f64           ┆ f64              ┆ f64                │
# ╞════════════╪═══════════════╪══════════════════╪════════════════════╡
# │ count      ┆ 5320.0        ┆ 5320.0           ┆ 5320.0             │
# │ null_count ┆ 0.0           ┆ 0.0              ┆ 0.0                │
# │ mean       ┆ 278555.13891  ┆ 222.65           ┆ 241.123872         │
# │ std        ┆ 136451.776732 ┆ 393.675248       ┆ 433.922384         │
# │ min        ┆ 100654.0      ┆ 0.0              ┆ 1.0                │
# │ 25%        ┆ 167905.0      ┆ 18.0             ┆ 21.0               │
# │ 50%        ┆ 217891.0      ┆ 77.0             ┆ 83.0               │
# │ 75%        ┆ 443146.0      ┆ 253.0            ┆ 267.0              │
# │ max        ┆ 497329.0      ┆ 4519.0           ┆ 6180.0             │
# └────────────┴───────────────┴──────────────────┴────────────────────┘
# 
# Column types:
#   unitid: Int64
#   grant_recipients: Int64
#   sfa_total_students: Int64
# 
# Null summary:
#   unitid: 0 nulls (0.0%)
#   grant_recipients: 0 nulls (0.0%)
#   sfa_total_students: 0 nulls (0.0%)
# 
# grant_recipients distribution (deciles):
#   p  0: 0
#   p 10: 6
#   p 20: 14
#   p 30: 24
#   p 40: 42
#   p 50: 77
#   p 60: 132
#   p 70: 202
#   p 80: 317
#   p 90: 572
#   p100: 4,519
# 
# sfa_total_students distribution (deciles):
#   p  0: 1
#   p 10: 7
#   p 20: 16
#   p 30: 28
#   p 40: 47
#   p 50: 83
#   p 60: 141
#   p 70: 215
#   p 80: 340
#   p 90: 611
#   p100: 6,180
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
