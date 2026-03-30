#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 09

Reviewed script: scripts/stage5_fetch/09_fetch-sfa-grants.py
Output files: data/raw/2026-03-29_ipeds_sfa_grants.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches expectations (15 columns including critical ones)
2. Row count within expected range (10,000 - 50,000)
3. No suspicious distributions (all-zero, all-same)
4. Coded missing values detection (-1, -2, -3)
5. No nulls in critical identifier columns (unitid, year, type_of_aid)

Script-Specific Checks (Five Skeptical Lenses):
6. COUNTERFACTUAL: What if type_of_aid=9 has multiple rows per unitid? Dimensional explosion risk.
7. SEMANTIC: Does type_of_aid=9 actually represent Pell/federal grant recipients (research need)?
8. BOUNDARY: Check for zero-value number_receiving_grants within type_of_aid=9 (boundary case).
9. ABSENCE: Are there unitids present in type_of_aid=3 but MISSING from type_of_aid=9 (data gaps)?
10. DOWNSTREAM: What columns are available for the cleaning script to use as Pell proxy?

Spot-Checks:
11. Trace a specific unitid through both type_of_aid values
12. Verify the 14.4% overall null rate comes entirely from type_of_aid=3
13. Check income_level distribution within type_of_aid=9 (key for aggregation strategy)
14. Verify uniqueness of (unitid, type_of_aid, income_level, ftpt, level_of_study, class_level, tuition_type)
15. Cross-reference: does number_receiving_grants <= number_of_students always hold?
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_sfa_grants.parquet"

EXPECTED_COLUMNS = [
    "unitid", "year", "fips", "ftpt", "level_of_study", "degree_seeking",
    "class_level", "tuition_type", "type_of_aid", "income_level",
    "average_grant", "number_of_students", "total_grant", "net_price",
    "number_receiving_grants"
]
EXPECTED_MIN_ROWS = 10000
EXPECTED_MAX_ROWS = 100000
CRITICAL_COLUMNS = ["unitid", "year", "type_of_aid", "number_receiving_grants"]
CODED_MISSING_VALUES = [-1, -2, -3]

# Dimensional columns that define the grain of the dataset
DIMENSION_COLS = ["ftpt", "level_of_study", "degree_seeking", "class_level",
                  "tuition_type", "type_of_aid", "income_level"]

# --- Load ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 09 (fetch-sfa-grants)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# =====================================================================
# DEFAULT CHECKS (1-5)
# =====================================================================

# --- Check 1: Schema ---
# INTENT: Verify all expected columns present in output.
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All 15 expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not expected): {extra_cols}")

# --- Check 2: Row count ---
# INTENT: Verify row count falls within expected range.
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
# INTENT: Detect degenerate distributions (all-zero, all-same) in numeric columns.
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        dist_issues.append(f"{col}: all null")
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all() and len(col_data) > 10:
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
# INTENT: Detect coded missing values (-1, -2, -3) in integer columns.
# NOTE: For Stage 5 (raw data), coded values are EXPECTED to be present.
# This check documents their presence; removal is Stage 6's job.
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in CODED_MISSING_VALUES:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'INFO'}] Coded values: ", end="")
if coded_ok:
    print("None detected (surprising for raw IPEDS data)")
else:
    print(f"Found: {'; '.join(coded_issues)}")

# --- Check 5: Critical nulls ---
# INTENT: Verify identifier columns have no nulls.
null_issues = []
for col in ["unitid", "year", "type_of_aid"]:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls (identifiers): ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =====================================================================
# SCRIPT-SPECIFIC CHECKS (6-10): Five Skeptical Lenses
# =====================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: COUNTERFACTUAL — How many rows per unitid within type_of_aid=9? ---
# INTENT: Determine whether type_of_aid=9 has ONE row per institution (simple)
# or MULTIPLE rows per institution (requires aggregation strategy).
# REASONING: If multiple rows exist, the cleaning script cannot simply filter to
# type_of_aid=9 and use number_receiving_grants directly -- it would need to
# aggregate, and the aggregation method matters for correctness.
toa9 = df.filter(pl.col("type_of_aid") == 9)
toa9_n_unitids = toa9["unitid"].n_unique()
toa9_rows = len(toa9)
rows_per_unitid_toa9 = toa9_rows / toa9_n_unitids if toa9_n_unitids > 0 else 0

print(f"\n[CHECK 6: COUNTERFACTUAL] type_of_aid=9 rows per unitid:")
print(f"  Total rows: {toa9_rows:,}")
print(f"  Unique unitids: {toa9_n_unitids:,}")
print(f"  Average rows per unitid: {rows_per_unitid_toa9:.1f}")

# Distribution of rows per unitid
rows_per_unit = toa9.group_by("unitid").agg(pl.len().alias("n_rows"))
row_dist = rows_per_unit["n_rows"].value_counts().sort("n_rows")
print(f"  Distribution of rows per unitid:")
for row in row_dist.iter_rows(named=True):
    print(f"    {row['n_rows']} rows: {row['count']:,} unitids")

counterfactual_ok = True
if rows_per_unitid_toa9 > 1.5:
    print(f"  [WARN] Multiple rows per unitid detected — aggregation strategy needed")
    counterfactual_ok = False
else:
    print(f"  [PASS] ~1 row per unitid — simple filter viable")

# --- Check 7: SEMANTIC — What does type_of_aid=9 represent? ---
# INTENT: Determine whether type_of_aid=9 represents Pell grants specifically,
# all federal grants, or something else entirely.
# REASONING: The research question requires Pell share specifically. Using a
# broader category introduces measurement error.
print(f"\n[CHECK 7: SEMANTIC] type_of_aid code meaning analysis:")

# Compare average_grant and number_receiving_grants across type_of_aid codes
for toa_code in sorted(df["type_of_aid"].unique().to_list()):
    subset = df.filter(pl.col("type_of_aid") == toa_code)
    avg_grant_mean = subset["average_grant"].drop_nulls().mean()
    avg_grant_median = subset["average_grant"].drop_nulls().median()
    n_recip_mean = subset["number_receiving_grants"].drop_nulls().mean()
    n_students_mean = subset["number_of_students"].drop_nulls().mean()
    print(f"  type_of_aid={toa_code}:")
    print(f"    Rows: {len(subset):,}")
    print(f"    avg_grant: mean={avg_grant_mean}, median={avg_grant_median}")
    print(f"    number_receiving_grants: mean={n_recip_mean}")
    print(f"    number_of_students: mean={n_students_mean}")

# Check if type_of_aid=9 grant amounts are consistent with Pell range (~$1,000-$7,000)
toa9_avg_grants = toa9["average_grant"].drop_nulls()
pell_range_count = toa9_avg_grants.filter(
    (toa9_avg_grants >= 500) & (toa9_avg_grants <= 10000)
).len()
pell_range_pct = pell_range_count / len(toa9_avg_grants) * 100 if len(toa9_avg_grants) > 0 else 0
print(f"  type_of_aid=9 avg_grant in Pell-plausible range ($500-$10000): {pell_range_pct:.1f}%")
print(f"  [INFO] Cannot definitively confirm type_of_aid=9 = Pell without codebook")
print(f"  [INFO] SFA data likely represents 'any grant/scholarship aid' not Pell-specific")

# --- Check 8: BOUNDARY — Zero-value number_receiving_grants within type_of_aid=9 ---
# INTENT: Check for institutions reporting 0 grant recipients (boundary case).
# REASONING: A zero value could mean "reported but none" vs. "error in reporting".
# Zeros in the denominator of a share calculation would cause division errors.
print(f"\n[CHECK 8: BOUNDARY] Zero and extreme values in type_of_aid=9:")

toa9_recip = toa9["number_receiving_grants"].drop_nulls()
zero_recip = (toa9_recip == 0).sum()
negative_recip = (toa9_recip < 0).sum()
very_large = (toa9_recip > 50000).sum()
print(f"  number_receiving_grants = 0: {zero_recip:,} rows")
print(f"  number_receiving_grants < 0: {negative_recip:,} rows")
print(f"  number_receiving_grants > 50,000: {very_large:,} rows")
print(f"  Min: {toa9_recip.min()}, Max: {toa9_recip.max()}")
print(f"  Median: {toa9_recip.median()}, Mean: {toa9_recip.mean():.1f}")

boundary_ok = negative_recip == 0
if zero_recip > 0:
    print(f"  [WARN] {zero_recip} rows with zero recipients — downstream must handle")
if negative_recip > 0:
    print(f"  [FAIL] Negative recipient counts detected — data integrity issue")
else:
    print(f"  [PASS] No negative values in number_receiving_grants")

# --- Check 9: ABSENCE — Unitids in type_of_aid=3 but not in type_of_aid=9 ---
# INTENT: Check if institutions appear in one type_of_aid but not the other.
# REASONING: If institutions have type_of_aid=3 data but NO type_of_aid=9 data,
# they would be missing from any Pell proxy analysis.
print(f"\n[CHECK 9: ABSENCE] Coverage gaps between type_of_aid codes:")

toa3_unitids = set(df.filter(pl.col("type_of_aid") == 3)["unitid"].unique().to_list())
toa9_unitids = set(toa9["unitid"].unique().to_list())

in_3_not_9 = toa3_unitids - toa9_unitids
in_9_not_3 = toa9_unitids - toa3_unitids
in_both = toa3_unitids & toa9_unitids

print(f"  Unitids in type_of_aid=3 only: {len(in_3_not_9):,}")
print(f"  Unitids in type_of_aid=9 only: {len(in_9_not_3):,}")
print(f"  Unitids in both: {len(in_both):,}")

if len(in_3_not_9) > 0:
    print(f"  [WARN] {len(in_3_not_9)} institutions have net price data (toa=3) but NO grant recipient data (toa=9)")
else:
    print(f"  [PASS] All institutions with toa=3 also have toa=9 data")

# --- Check 10: DOWNSTREAM — What can the cleaning script use? ---
# INTENT: Assess which columns and structure the cleaning script will receive.
# REASONING: The downstream script needs to: (a) filter to the right type_of_aid,
# (b) aggregate if needed, and (c) produce a per-institution grant recipient count.
print(f"\n[CHECK 10: DOWNSTREAM] Data readiness for cleaning:")

# Check what the dimensional structure looks like for type_of_aid=9
print(f"  Dimensional values within type_of_aid=9:")
for dim_col in DIMENSION_COLS:
    if dim_col == "type_of_aid":
        continue
    unique_vals = sorted(toa9[dim_col].unique().to_list())
    print(f"    {dim_col}: {unique_vals}")

# Key question: is there a single row per unitid at any slice?
# Try income_level=0 (which might mean "total")
if 0 in toa9["income_level"].unique().to_list():
    toa9_il0 = toa9.filter(pl.col("income_level") == 0)
    toa9_il0_unique = toa9_il0["unitid"].n_unique()
    print(f"  income_level=0 slice: {len(toa9_il0):,} rows, {toa9_il0_unique:,} unique unitids")
    if toa9_il0_unique == len(toa9_il0):
        print(f"  [INFO] income_level=0 gives 1 row per unitid — likely the 'total' row")
    else:
        print(f"  [INFO] income_level=0 does NOT give 1 row per unitid — {len(toa9_il0)/toa9_il0_unique:.1f} avg")

# Check non-null rates for key columns within type_of_aid=9
print(f"\n  Non-null rates within type_of_aid=9:")
for col in ["number_receiving_grants", "average_grant", "number_of_students", "total_grant", "net_price"]:
    nonnull = toa9[col].drop_nulls().len()
    pct = nonnull / len(toa9) * 100
    print(f"    {col}: {nonnull:,}/{len(toa9):,} ({pct:.1f}%)")

# =====================================================================
# SPOT-CHECKS (11-15)
# =====================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Trace a specific unitid through both type_of_aid values ---
# INTENT: Pick a known institution and verify its data makes sense.
# REASONING: Tracing a single record exposes structural issues that aggregate
# statistics hide.
print(f"\n[SPOT-CHECK 11] Trace unitid through both type_of_aid codes:")

# Pick the first unitid that appears in both type_of_aid codes
if len(in_both) > 0:
    sample_unitid = sorted(list(in_both))[0]
    print(f"  Sample unitid: {sample_unitid}")
    sample_rows = df.filter(pl.col("unitid") == sample_unitid).sort("type_of_aid", "income_level")
    print(f"  Total rows for this unitid: {len(sample_rows)}")
    print(f"  By type_of_aid:")
    for toa in sorted(sample_rows["type_of_aid"].unique().to_list()):
        toa_subset = sample_rows.filter(pl.col("type_of_aid") == toa)
        print(f"    toa={toa}: {len(toa_subset)} rows")
        for row in toa_subset.iter_rows(named=True):
            print(f"      income_level={row['income_level']}, "
                  f"n_students={row['number_of_students']}, "
                  f"n_receiving={row['number_receiving_grants']}, "
                  f"avg_grant={row['average_grant']}, "
                  f"ftpt={row['ftpt']}, "
                  f"level={row['level_of_study']}")

# --- Spot-Check 12: Verify 14.4% overall null rate comes from type_of_aid=3 ---
# INTENT: Confirm that number_receiving_grants is 100% null for toa=3 and 0% null for toa=9.
# REASONING: The execution log reported 14.4% overall null. This should be entirely
# from toa=3 (5,372 rows / 37,292 total = 14.4%).
print(f"\n[SPOT-CHECK 12] Null attribution for number_receiving_grants:")
toa3_nulls = df.filter(pl.col("type_of_aid") == 3)["number_receiving_grants"].null_count()
toa9_nulls = toa9["number_receiving_grants"].null_count()
total_nulls = df["number_receiving_grants"].null_count()
print(f"  type_of_aid=3: {toa3_nulls:,} nulls out of {len(df.filter(pl.col('type_of_aid') == 3)):,} rows ({toa3_nulls/len(df.filter(pl.col('type_of_aid') == 3))*100:.1f}%)")
print(f"  type_of_aid=9: {toa9_nulls:,} nulls out of {len(toa9):,} rows ({toa9_nulls/len(toa9)*100:.1f}%)")
print(f"  Total: {total_nulls:,} nulls out of {len(df):,} rows ({total_nulls/len(df)*100:.1f}%)")

null_attribution_ok = toa3_nulls == total_nulls and toa9_nulls == 0
if null_attribution_ok:
    print(f"  [PASS] All nulls come from type_of_aid=3; type_of_aid=9 is 100% populated")
else:
    print(f"  [FAIL] Null attribution unexpected — toa=9 has {toa9_nulls} nulls")

# --- Spot-Check 13: Income_level distribution within type_of_aid=9 ---
# INTENT: Understand the income_level dimension -- is there a 'total' row?
# REASONING: IPEDS SFA data typically breaks down by income level. If there are
# 5+ income levels per institution, we need the total (or sum) for Pell proxy.
print(f"\n[SPOT-CHECK 13] income_level distribution within type_of_aid=9:")
il_dist = (
    toa9.group_by("income_level")
    .agg([
        pl.len().alias("count"),
        pl.col("number_receiving_grants").mean().alias("mean_recipients"),
        pl.col("number_receiving_grants").sum().alias("sum_recipients"),
        pl.col("number_of_students").mean().alias("mean_students"),
    ])
    .sort("income_level")
)
print(f"  {'IL':>4} {'Count':>8} {'Mean Recip':>12} {'Sum Recip':>14} {'Mean Students':>14}")
for row in il_dist.iter_rows(named=True):
    print(f"  {row['income_level']:>4} {row['count']:>8,} "
          f"{row['mean_recipients']:>12.1f} {row['sum_recipients']:>14,} "
          f"{row['mean_students']:>14.1f}")

# Check if income_level=0 is a "total" row
il_values = sorted(toa9["income_level"].unique().to_list())
print(f"  Unique income_level values: {il_values}")
if 0 in il_values:
    # Compare il=0 recipients to sum of other income levels for a sample unitid
    if len(in_both) > 0:
        test_uid = sorted(list(in_both))[0]
        uid_toa9 = toa9.filter(pl.col("unitid") == test_uid)
        il0_recip = uid_toa9.filter(pl.col("income_level") == 0)["number_receiving_grants"].sum()
        other_recip = uid_toa9.filter(pl.col("income_level") != 0)["number_receiving_grants"].sum()
        print(f"  For unitid={test_uid}: income_level=0 recipients={il0_recip}, sum of others={other_recip}")
        if il0_recip is not None and other_recip is not None:
            if il0_recip >= other_recip * 0.9:
                print(f"  [INFO] income_level=0 appears to be a total/aggregate row")
            else:
                print(f"  [INFO] income_level=0 does NOT appear to be a sum of others")

# --- Spot-Check 14: Uniqueness of composite key ---
# INTENT: Check if the full dimensional key is unique (no true duplicates).
# REASONING: Duplicate rows for the same dimensional combination would indicate
# data quality issues from the source.
print(f"\n[SPOT-CHECK 14] Composite key uniqueness:")
key_cols = ["unitid", "type_of_aid", "income_level", "ftpt", "level_of_study",
            "degree_seeking", "class_level", "tuition_type"]
n_total = len(df)
n_unique = df.select(key_cols).n_unique()
key_unique = n_total == n_unique
print(f"  Total rows: {n_total:,}")
print(f"  Unique combinations of {key_cols}: {n_unique:,}")
if key_unique:
    print(f"  [PASS] Full dimensional key is unique — no duplicate rows")
else:
    print(f"  [WARN] {n_total - n_unique:,} duplicate rows detected on full key")

# --- Spot-Check 15: number_receiving_grants <= number_of_students ---
# INTENT: Verify logical consistency — recipients should not exceed total students.
# REASONING: If recipients > students, it indicates data quality issues or
# misunderstanding of what the columns represent.
print(f"\n[SPOT-CHECK 15] Logical consistency: recipients <= students:")
toa9_both_nonnull = toa9.filter(
    pl.col("number_receiving_grants").is_not_null() &
    pl.col("number_of_students").is_not_null()
)
violations = toa9_both_nonnull.filter(
    pl.col("number_receiving_grants") > pl.col("number_of_students")
)
print(f"  Rows with both columns non-null: {len(toa9_both_nonnull):,}")
print(f"  Rows where recipients > students: {len(violations):,}")
if len(violations) > 0:
    violation_pct = len(violations) / len(toa9_both_nonnull) * 100
    print(f"  Violation rate: {violation_pct:.1f}%")
    # Show some examples
    print(f"  Examples:")
    for row in violations.head(5).iter_rows(named=True):
        print(f"    unitid={row['unitid']}: recipients={row['number_receiving_grants']}, students={row['number_of_students']}")
    if violation_pct > 5:
        print(f"  [WARN] Significant violation rate — columns may measure different populations")
    else:
        print(f"  [INFO] Minor violations — likely rounding or reporting artifacts")
else:
    print(f"  [PASS] All rows satisfy recipients <= students")

# =====================================================================
# SUMMARY
# =====================================================================

print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

all_default_passed = all([schema_ok, rows_ok, dist_ok, nulls_ok])
print(f"Default checks: {'ALL PASSED' if all_default_passed else 'ISSUES FOUND'}")
print(f"Counterfactual (rows per unitid): {'OK' if counterfactual_ok else 'NEEDS INVESTIGATION'}")
print(f"Boundary (negative values): {'OK' if boundary_ok else 'FAIL'}")
print(f"Null attribution: {'OK' if null_attribution_ok else 'FAIL'}")
print(f"Key uniqueness: {'OK' if key_unique else 'NEEDS INVESTIGATION'}")

severity = "PASSED"
if not all([all_default_passed, boundary_ok, null_attribution_ok]):
    severity = "BLOCKER"
elif not all([counterfactual_ok, key_unique]):
    severity = "WARNING"

print(f"\nQA RESULT: {severity}")
print("=" * 60)

# =====================================================================
# DATA PROFILING (for cr2+ decision)
# =====================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\ntype_of_aid distribution:")
print(df["type_of_aid"].value_counts().sort("type_of_aid"))

print("\nColumn dtypes:")
for col, dtype in zip(df.columns, df.dtypes):
    print(f"  {col}: {dtype}")

print("\nKey column value counts (income_level):")
print(df["income_level"].value_counts().sort("income_level"))

print("\nKey column value counts (ftpt):")
print(df["ftpt"].value_counts().sort("ftpt"))

print("\nKey column value counts (level_of_study):")
print(df["level_of_study"].value_counts().sort("level_of_study"))


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:13:50
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_09_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 09 (fetch-sfa-grants)
# ============================================================
# Loaded: 37,292 rows x 15 cols
# 
# [PASS] Schema: All 15 expected columns present
# [PASS] Row count: 37,292 (expected 10,000-100,000)
# [FAIL] Distributions: year: all same value (2020); ftpt: all same value (1); level_of_study: all same value (1); degree_seeking: all same value (1); class_level: all same value (1)
# [PASS] Coded values: None detected (surprising for raw IPEDS data)
# [PASS] Critical nulls (identifiers): None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [CHECK 6: COUNTERFACTUAL] type_of_aid=9 rows per unitid:
#   Total rows: 31,920
#   Unique unitids: 5,320
#   Average rows per unitid: 6.0
#   Distribution of rows per unitid:
#     6 rows: 5,320 unitids
#   [WARN] Multiple rows per unitid detected — aggregation strategy needed
# 
# [CHECK 7: SEMANTIC] type_of_aid code meaning analysis:
#   type_of_aid=3:
#     Rows: 5,372
#     avg_grant: mean=9219.62751303053, median=5912.5
#     number_receiving_grants: mean=None
#     number_of_students: mean=309.0625465376024
#   type_of_aid=9:
#     Rows: 31,920
#     avg_grant: mean=9846.035696541181, median=5835.0
#     number_receiving_grants: mean=74.21666666666667
#     number_of_students: mean=80.37462406015038
#   type_of_aid=9 avg_grant in Pell-plausible range ($500-$10000): 66.7%
#   [INFO] Cannot definitively confirm type_of_aid=9 = Pell without codebook
#   [INFO] SFA data likely represents 'any grant/scholarship aid' not Pell-specific
# 
# [CHECK 8: BOUNDARY] Zero and extreme values in type_of_aid=9:
#   number_receiving_grants = 0: 7,015 rows
#   number_receiving_grants < 0: 0 rows
#   number_receiving_grants > 50,000: 0 rows
#   Min: 0, Max: 4519
#   Median: 14.0, Mean: 74.2
#   [WARN] 7015 rows with zero recipients — downstream must handle
#   [PASS] No negative values in number_receiving_grants
# 
# [CHECK 9: ABSENCE] Coverage gaps between type_of_aid codes:
#   Unitids in type_of_aid=3 only: 61
#   Unitids in type_of_aid=9 only: 9
#   Unitids in both: 5,311
#   [WARN] 61 institutions have net price data (toa=3) but NO grant recipient data (toa=9)
# 
# [CHECK 10: DOWNSTREAM] Data readiness for cleaning:
#   Dimensional values within type_of_aid=9:
#     ftpt: [1]
#     level_of_study: [1]
#     degree_seeking: [1]
#     class_level: [1]
#     tuition_type: [1, 99]
#     income_level: [1, 2, 3, 4, 5, 99]
# 
#   Non-null rates within type_of_aid=9:
#     number_receiving_grants: 31,920/31,920 (100.0%)
#     average_grant: 26,165/31,920 (82.0%)
#     number_of_students: 31,920/31,920 (100.0%)
#     total_grant: 31,920/31,920 (100.0%)
#     net_price: 20,840/31,920 (65.3%)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [SPOT-CHECK 11] Trace unitid through both type_of_aid codes:
#   Sample unitid: 100654
#   Total rows for this unitid: 7
#   By type_of_aid:
#     toa=3: 1 rows
#       income_level=99, n_students=693, n_receiving=None, avg_grant=9006, ftpt=1, level=1
#     toa=9: 6 rows
#       income_level=1, n_students=381, n_receiving=380, avg_grant=9747, ftpt=1, level=1
#       income_level=2, n_students=141, n_receiving=141, avg_grant=9624, ftpt=1, level=1
#       income_level=3, n_students=76, n_receiving=73, avg_grant=6416, ftpt=1, level=1
#       income_level=4, n_students=40, n_receiving=34, avg_grant=5217, ftpt=1, level=1
#       income_level=5, n_students=19, n_receiving=14, avg_grant=3067, ftpt=1, level=1
#       income_level=99, n_students=657, n_receiving=642, avg_grant=8867, ftpt=1, level=1
# 
# [SPOT-CHECK 12] Null attribution for number_receiving_grants:
#   type_of_aid=3: 5,372 nulls out of 5,372 rows (100.0%)
#   type_of_aid=9: 0 nulls out of 31,920 rows (0.0%)
#   Total: 5,372 nulls out of 37,292 rows (14.4%)
#   [PASS] All nulls come from type_of_aid=3; type_of_aid=9 is 100% populated
# 
# [SPOT-CHECK 13] income_level distribution within type_of_aid=9:
#     IL    Count   Mean Recip      Sum Recip  Mean Students
#      1    5,320         95.3        507,218           96.9
#      2    5,320         39.3        209,132           40.0
#      3    5,320         33.5        178,440           35.1
#      4    5,320         21.6        114,718           25.7
#      5    5,320         32.9        174,990           43.5
#     99    5,320        222.7      1,184,498          241.1
#   Unique income_level values: [1, 2, 3, 4, 5, 99]
# 
# [SPOT-CHECK 14] Composite key uniqueness:
#   Total rows: 37,292
#   Unique combinations of ['unitid', 'type_of_aid', 'income_level', 'ftpt', 'level_of_study', 'degree_seeking', 'class_level', 'tuition_type']: 37,292
#   [PASS] Full dimensional key is unique — no duplicate rows
# 
# [SPOT-CHECK 15] Logical consistency: recipients <= students:
#   Rows with both columns non-null: 31,920
#   Rows where recipients > students: 0
#   [PASS] All rows satisfy recipients <= students
# 
# ============================================================
# QA SUMMARY
# ============================================================
# Default checks: ISSUES FOUND
# Counterfactual (rows per unitid): NEEDS INVESTIGATION
# Boundary (negative values): OK
# Null attribution: OK
# Key uniqueness: OK
# 
# QA RESULT: BLOCKER
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 15)
# ┌────────┬──────┬──────┬──────┬───┬───────────────────┬─────────────┬───────────┬──────────────────┐
# │ unitid ┆ year ┆ fips ┆ ftpt ┆ … ┆ number_of_student ┆ total_grant ┆ net_price ┆ number_receiving │
# │ ---    ┆ ---  ┆ ---  ┆ ---  ┆   ┆ s                 ┆ ---         ┆ ---       ┆ _grants          │
# │ i64    ┆ i64  ┆ i64  ┆ i64  ┆   ┆ ---               ┆ i64         ┆ i64       ┆ ---              │
# │        ┆      ┆      ┆      ┆   ┆ i64               ┆             ┆           ┆ i64              │
# ╞════════╪══════╪══════╪══════╪═══╪═══════════════════╪═════════════╪═══════════╪══════════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 657               ┆ 5825299     ┆ null      ┆ 642              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 76                ┆ 487604      ┆ 15508     ┆ 73               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 381               ┆ 3713735     ┆ 12177     ┆ 380              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 19                ┆ 58270       ┆ 18857     ┆ 14               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 141               ┆ 1357002     ┆ 12300     ┆ 141              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 40                ┆ 208688      ┆ 16707     ┆ 34               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 693               ┆ 6240985     ┆ 12921     ┆ null             │
# │ 100663 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 249               ┆ 1542360     ┆ 20054     ┆ 209              │
# │ 100663 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 161               ┆ 1513529     ┆ 16847     ┆ 155              │
# │ 100663 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 1585              ┆ 15046376    ┆ 16990     ┆ null             │
# └────────┴──────┴──────┴──────┴───┴───────────────────┴─────────────┴───────────┴──────────────────┘
# 
# Descriptive statistics:
# shape: (9, 16)
# ┌────────────┬───────────┬─────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid    ┆ year    ┆ fips      ┆ … ┆ number_of ┆ total_gra ┆ net_price ┆ number_re │
# │ ---        ┆ ---       ┆ ---     ┆ ---       ┆   ┆ _students ┆ nt        ┆ ---       ┆ ceiving_g │
# │ str        ┆ f64       ┆ f64     ┆ f64       ┆   ┆ ---       ┆ ---       ┆ f64       ┆ rants     │
# │            ┆           ┆         ┆           ┆   ┆ f64       ┆ f64       ┆           ┆ ---       │
# │            ┆           ┆         ┆           ┆   ┆           ┆           ┆           ┆ f64       │
# ╞════════════╪═══════════╪═════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 37292.0   ┆ 37292.0 ┆ 37292.0   ┆ … ┆ 37292.0   ┆ 37292.0   ┆ 26211.0   ┆ 31920.0   │
# │ null_count ┆ 0.0       ┆ 0.0     ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 11081.0   ┆ 5372.0    │
# │ mean       ┆ 278713.85 ┆ 2020.0  ┆ 29.389547 ┆ … ┆ 113.31765 ┆ 1.3774e6  ┆ 17147.332 ┆ 74.216667 │
# │            ┆ 029       ┆         ┆           ┆   ┆ 5         ┆           ┆ 494       ┆           │
# │ std        ┆ 136506.69 ┆ 0.0     ┆ 16.82669  ┆ … ┆ 310.99466 ┆ 4.4072e6  ┆ 8970.9525 ┆ 198.54634 │
# │            ┆ 4738      ┆         ┆           ┆   ┆ 2         ┆           ┆ 26        ┆ 6         │
# │ min        ┆ 100654.0  ┆ 2020.0  ┆ 1.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ -8846.0   ┆ 0.0       │
# │ 25%        ┆ 167987.0  ┆ 2020.0  ┆ 13.0      ┆ … ┆ 3.0       ┆ 6500.0    ┆ 10462.0   ┆ 1.0       │
# │ 50%        ┆ 217907.0  ┆ 2020.0  ┆ 30.0      ┆ … ┆ 21.0      ┆ 108745.0  ┆ 16347.0   ┆ 14.0      │
# │ 75%        ┆ 443225.0  ┆ 2020.0  ┆ 42.0      ┆ … ┆ 85.0      ┆ 846587.0  ┆ 22489.0   ┆ 61.0      │
# │ max        ┆ 497329.0  ┆ 2020.0  ┆ 78.0      ┆ … ┆ 7477.0    ┆ 1.2430761 ┆ 115511.0  ┆ 4519.0    │
# │            ┆           ┆         ┆           ┆   ┆           ┆ 1e8       ┆           ┆           │
# └────────────┴───────────┴─────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 37292 │
# └──────┴───────┘
# 
# type_of_aid distribution:
# shape: (2, 2)
# ┌─────────────┬───────┐
# │ type_of_aid ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 3           ┆ 5372  │
# │ 9           ┆ 31920 │
# └─────────────┴───────┘
# 
# Column dtypes:
#   unitid: Int64
#   year: Int64
#   fips: Int64
#   ftpt: Int64
#   level_of_study: Int64
#   degree_seeking: Int64
#   class_level: Int64
#   tuition_type: Int64
#   type_of_aid: Int64
#   income_level: Int64
#   average_grant: Int64
#   number_of_students: Int64
#   total_grant: Int64
#   net_price: Int64
#   number_receiving_grants: Int64
# 
# Key column value counts (income_level):
# shape: (6, 2)
# ┌──────────────┬───────┐
# │ income_level ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 5320  │
# │ 2            ┆ 5320  │
# │ 3            ┆ 5320  │
# │ 4            ┆ 5320  │
# │ 5            ┆ 5320  │
# │ 99           ┆ 10692 │
# └──────────────┴───────┘
# 
# Key column value counts (ftpt):
# shape: (1, 2)
# ┌──────┬───────┐
# │ ftpt ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 37292 │
# └──────┴───────┘
# 
# Key column value counts (level_of_study):
# shape: (1, 2)
# ┌────────────────┬───────┐
# │ level_of_study ┆ count │
# │ ---            ┆ ---   │
# │ i64            ┆ u32   │
# ╞════════════════╪═══════╡
# │ 1              ┆ 37292 │
# └────────────────┴───────┘
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
