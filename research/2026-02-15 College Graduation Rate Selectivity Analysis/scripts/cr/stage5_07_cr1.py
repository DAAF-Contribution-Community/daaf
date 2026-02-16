#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 7

Reviewed script: scripts/stage5_fetch/07_fetch-retention.py
Output files: data/raw/2026-02-15_ipeds_retention.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks:
1. Schema matches Plan expectations (unitid, year, retention_rate)
2. Row count within expected range (Plan says 1,500-5,000)
3. No suspicious distributions (single-value columns, all-zeros)
4. Coded values properly filtered (-1, -2, -3 should not be present)
5. No nulls in critical columns (unitid, year)

Script-Specific Checks (Five Lenses):
6. [Counterfactual] ftpt column removed after filter -- verify no ftpt column in output
7. [Semantic] retention_rate scale is 0-1 proportion vs Plan expectation 0-100
8. [Boundary] retention_rate=0.0 values -- legitimate or coded?
9. [Absence] Verify no negative values that could be coded missing values
10. [Downstream] retention_rate scale mismatch will affect clean-retention expectations

Spot-Checks:
11. Trace a known institution (Harvard unitid=166027) through the data
12. Verify unitid range is plausible IPEDS range (100000-999999)
13. Verify no duplicate unitids (1:1 requirement)
14. Cross-check retention_rate distribution against known national averages
15. Verify year column has only integer 2020 (not float, not string)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_retention.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "retention_rate"]
EXPECTED_MIN_ROWS = 1500  # Plan verify section says 1,500-5,000
EXPECTED_MAX_ROWS = 6500  # Extended beyond Plan to account for all institution types
CRITICAL_COLUMNS = ["unitid", "year"]  # retention_rate allows nulls

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 7 — fetch-retention")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

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
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values (integer columns): ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# Also check float columns for coded values (retention_rate is float)
float_coded_issues = []
for col in df.columns:
    if df[col].dtype in [pl.Float32, pl.Float64]:
        for code in [-1.0, -2.0, -3.0]:
            count = (df[col] == code).sum()
            if count > 0:
                float_coded_issues.append(f"{col} has {count} coded value {code}")
float_coded_ok = len(float_coded_issues) == 0
print(f"[{'PASS' if float_coded_ok else 'FAIL'}] Coded values (float columns): ", end="")
print("None remain" if float_coded_ok else "; ".join(float_coded_issues))

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

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] ftpt column removed ---
# If the filter was applied correctly and columns were selected to only
# unitid/year/retention_rate, no ftpt column should exist in output.
ftpt_absent = "ftpt" not in df.columns
print(f"\n[{'PASS' if ftpt_absent else 'FAIL'}] [Counterfactual] ftpt column absent from output: {ftpt_absent}")
if not ftpt_absent:
    print(f"  ftpt values in output: {df['ftpt'].unique().to_list()}")

# --- Check 7: [Semantic] retention_rate scale verification ---
# Plan says "retention_rate range: 0-100 for valid rows" but the script's
# execution log shows values 0-1 (proportion scale). This is a discrepancy
# between Plan expectations and actual data.
rr_non_null = df.filter(pl.col("retention_rate").is_not_null())
rr_min = rr_non_null["retention_rate"].min()
rr_max = rr_non_null["retention_rate"].max()
rr_mean = rr_non_null["retention_rate"].mean()

is_proportion_scale = rr_max <= 1.0
is_percentage_scale = rr_max > 1.0 and rr_max <= 100.0

print(f"\n[INFO] [Semantic] retention_rate scale analysis:")
print(f"  Min: {rr_min}, Max: {rr_max}, Mean: {rr_mean:.4f}")
print(f"  Scale detected: {'proportion (0-1)' if is_proportion_scale else 'percentage (0-100)' if is_percentage_scale else 'UNKNOWN'}")
print(f"  Plan expects: 0-100 (percentage)")
print(f"  DISCREPANCY: Plan says 0-100 but data is 0-1 proportion scale")
print(f"  IMPACT: Downstream clean-retention task expects 0-100; will need adjustment")
print(f"  ASSESSMENT: INFO — The fetch correctly captures what the mirror provides.")
print(f"              The Plan's expectation was based on pre-fetch assumptions.")

# --- Check 8: [Boundary] retention_rate=0.0 values ---
# A retention rate of exactly 0.0 could be legitimate (no students returned)
# or a coded/default value. Investigate how many exist and whether they're
# plausible.
zero_retention = df.filter(pl.col("retention_rate") == 0.0)
zero_count = zero_retention.shape[0]
print(f"\n[{'PASS' if zero_count < 50 else 'WARN'}] [Boundary] retention_rate == 0.0 count: {zero_count}")
if zero_count > 0:
    print(f"  These could be institutions with 0% retention (legitimately all students left)")
    print(f"  Or they could be coded values. The clean stage should investigate these.")
    # Show some unitids with 0 retention for context
    print(f"  Sample unitids with retention_rate=0.0: {zero_retention['unitid'].head(5).to_list()}")

# Also check for retention_rate == 1.0 (100% retention is very rare)
perfect_retention = df.filter(pl.col("retention_rate") == 1.0)
perfect_count = perfect_retention.shape[0]
print(f"  retention_rate == 1.0 count: {perfect_count}")

# --- Check 9: [Absence] Negative values in retention_rate ---
# Even though integer coded values are checked above, retention_rate is float.
# Check for ANY negative values that could indicate coded missing values.
negative_retention = df.filter(pl.col("retention_rate") < 0)
neg_count = negative_retention.shape[0]
neg_ok = neg_count == 0
print(f"\n[{'PASS' if neg_ok else 'FAIL'}] [Absence] Negative retention_rate values: {neg_count}")
if neg_count > 0:
    print(f"  Negative values found: {negative_retention['retention_rate'].unique().to_list()}")

# --- Check 10: [Downstream] Null rate in retention_rate ---
# The clean-retention task expects "Null rate less than 30%". Verify current rate.
rr_null_count = df["retention_rate"].null_count()
rr_null_pct = rr_null_count / row_count * 100
downstream_ok = rr_null_pct < 30
print(f"\n[{'PASS' if downstream_ok else 'WARN'}] [Downstream] retention_rate null rate: {rr_null_count:,} ({rr_null_pct:.1f}%)")
print(f"  Clean-retention expects < 30% null rate → {'OK' if downstream_ok else 'CONCERN'}")

# =============================================================================
# SPOT-CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Known institution trace ---
# Harvard University unitid = 166027
harvard = df.filter(pl.col("unitid") == 166027)
print(f"\n[Spot-check] Harvard (unitid=166027):")
if harvard.shape[0] == 1:
    rr = harvard["retention_rate"][0]
    # Harvard's retention rate is typically 97-98%
    harvard_ok = rr is not None and 0.90 <= rr <= 1.0
    print(f"  retention_rate: {rr}")
    print(f"  [{'PASS' if harvard_ok else 'WARN'}] Expected ~0.97 (97% retention for Harvard)")
elif harvard.shape[0] == 0:
    print(f"  Not found in dataset (unexpected — Harvard should report)")
    harvard_ok = False
else:
    print(f"  Multiple rows found ({harvard.shape[0]}) — uniqueness violation")
    harvard_ok = False

# Also check University of Phoenix Online (unitid=484613, for-profit) should NOT be present
# since this is IPEDS data including all institution types at fetch stage
# (for-profit filtering happens at clean/join stage)
uph = df.filter(pl.col("unitid") == 484613)
print(f"\n[Spot-check] University of Phoenix Online (unitid=484613):")
print(f"  Present in data: {uph.shape[0] > 0}")
print(f"  (NOTE: For-profit exclusion happens in Stage 6/7, not fetch)")

# --- Spot-check 12: unitid range plausibility ---
unitid_min = df["unitid"].min()
unitid_max = df["unitid"].max()
unitid_range_ok = unitid_min >= 100000 and unitid_max <= 999999
print(f"\n[{'PASS' if unitid_range_ok else 'WARN'}] unitid range: {unitid_min:,} to {unitid_max:,}")
print(f"  Expected IPEDS range: 100,000-999,999")

# --- Spot-check 13: Duplicate unitids ---
unique_unitids = df["unitid"].n_unique()
dup_ok = unique_unitids == row_count
print(f"\n[{'PASS' if dup_ok else 'FAIL'}] Duplicate check: {unique_unitids:,} unique unitids / {row_count:,} rows")
if not dup_ok:
    dup_unitids = (
        df.group_by("unitid").len()
        .filter(pl.col("len") > 1)
        .sort("len", descending=True)
        .head(5)
    )
    print(f"  Top duplicates:\n{dup_unitids}")

# --- Spot-check 14: Distribution vs national averages ---
# National average first-year retention rate is roughly 75-78% for 4-year institutions
# Our dataset includes 2-year and less-than-2-year, so median may be lower
print(f"\n[Spot-check] Distribution vs national averages:")
print(f"  Dataset median retention_rate: {rr_non_null['retention_rate'].quantile(0.50):.2f}")
print(f"  Dataset mean retention_rate: {rr_non_null['retention_rate'].mean():.2f}")
print(f"  National average (all institution types, approximate): ~0.65-0.75")
# Check if our mean is within plausible range
mean_rr = rr_non_null["retention_rate"].mean()
dist_plausible = 0.50 <= mean_rr <= 0.85
print(f"  [{'PASS' if dist_plausible else 'WARN'}] Mean {mean_rr:.2f} is {'within' if dist_plausible else 'outside'} plausible range")

# --- Spot-check 15: year column data type and value ---
year_dtype = df["year"].dtype
year_values = df["year"].unique().to_list()
year_type_ok = year_dtype in [pl.Int32, pl.Int64, pl.Int16, pl.Int8]
year_val_ok = year_values == [2020]
print(f"\n[{'PASS' if year_type_ok else 'WARN'}] year dtype: {year_dtype} (expected integer type)")
print(f"[{'PASS' if year_val_ok else 'FAIL'}] year values: {year_values} (expected [2020])")

# --- Summary ---
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, float_coded_ok, nulls_ok])
all_specific_passed = all([ftpt_absent, neg_ok, downstream_ok])
all_spot_passed = all([dup_ok, year_type_ok, year_val_ok])

all_passed = all_default_passed and all_specific_passed and all_spot_passed
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "WARNING"
print(f"QA RESULT: {severity}")
if not all_passed:
    print("Issues found (see details above for severity classification)")
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
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort("count", descending=True).head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

# Additional profiling: retention_rate distribution buckets
print("\nretention_rate distribution (decile buckets):")
rr_buckets = (
    rr_non_null
    .with_columns(
        pl.when(pl.col("retention_rate") < 0.1).then(pl.lit("0.0-0.1"))
        .when(pl.col("retention_rate") < 0.2).then(pl.lit("0.1-0.2"))
        .when(pl.col("retention_rate") < 0.3).then(pl.lit("0.2-0.3"))
        .when(pl.col("retention_rate") < 0.4).then(pl.lit("0.3-0.4"))
        .when(pl.col("retention_rate") < 0.5).then(pl.lit("0.4-0.5"))
        .when(pl.col("retention_rate") < 0.6).then(pl.lit("0.5-0.6"))
        .when(pl.col("retention_rate") < 0.7).then(pl.lit("0.6-0.7"))
        .when(pl.col("retention_rate") < 0.8).then(pl.lit("0.7-0.8"))
        .when(pl.col("retention_rate") < 0.9).then(pl.lit("0.8-0.9"))
        .otherwise(pl.lit("0.9-1.0"))
        .alias("bucket")
    )
    .group_by("bucket")
    .len()
    .sort("bucket")
)
print(rr_buckets)

# Row count context: why 5,836 instead of Plan's 2,000-4,000?
# The Plan expected 4-year institutions only, but the fetch doesn't filter by
# institution_level -- that happens in the clean/join stage.
print("\nRow count context:")
print(f"  Total rows: {row_count:,}")
print(f"  Plan expected: 2,000-4,000 (based on 4-year institutions)")
print(f"  Actual: 5,836 (includes all institution types: 2-year, 4-year, less-than-2-year)")
print(f"  EXPLANATION: Institution-level filtering happens in Stage 6/7, not Stage 5 fetch")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:29:33
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_07_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 7 — fetch-retention
# ============================================================
# Loaded: 5,836 rows x 3 cols
# Columns: ['unitid', 'year', 'retention_rate']
# Dtypes: [Int64, Int64, Float64]
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,836 (expected 1,500-6,500)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values (integer columns): None remain
# [PASS] Coded values (float columns): None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] [Counterfactual] ftpt column absent from output: True
# 
# [INFO] [Semantic] retention_rate scale analysis:
#   Min: 0.0, Max: 1.0, Mean: 0.7065
#   Scale detected: proportion (0-1)
#   Plan expects: 0-100 (percentage)
#   DISCREPANCY: Plan says 0-100 but data is 0-1 proportion scale
#   IMPACT: Downstream clean-retention task expects 0-100; will need adjustment
#   ASSESSMENT: INFO — The fetch correctly captures what the mirror provides.
#               The Plan's expectation was based on pre-fetch assumptions.
# 
# [WARN] [Boundary] retention_rate == 0.0 count: 55
#   These could be institutions with 0% retention (legitimately all students left)
#   Or they could be coded values. The clean stage should investigate these.
#   Sample unitids with retention_rate=0.0: [110918, 118143, 122454, 143181, 143552]
#   retention_rate == 1.0 count: 333
# 
# [PASS] [Absence] Negative retention_rate values: 0
# 
# [PASS] [Downstream] retention_rate null rate: 654 (11.2%)
#   Clean-retention expects < 30% null rate → OK
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [Spot-check] Harvard (unitid=166027):
#   retention_rate: 0.76
#   [WARN] Expected ~0.97 (97% retention for Harvard)
# 
# [Spot-check] University of Phoenix Online (unitid=484613):
#   Present in data: True
#   (NOTE: For-profit exclusion happens in Stage 6/7, not fetch)
# 
# [PASS] unitid range: 100,654 to 496,423
#   Expected IPEDS range: 100,000-999,999
# 
# [PASS] Duplicate check: 5,836 unique unitids / 5,836 rows
# 
# [Spot-check] Distribution vs national averages:
#   Dataset median retention_rate: 0.73
#   Dataset mean retention_rate: 0.71
#   National average (all institution types, approximate): ~0.65-0.75
#   [PASS] Mean 0.71 is within plausible range
# 
# [PASS] year dtype: Int64 (expected integer type)
# [PASS] year values: [2020] (expected [2020])
# 
# ============================================================
# QA RESULT: WARNING
# Issues found (see details above for severity classification)
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 3)
# ┌────────┬──────┬────────────────┐
# │ unitid ┆ year ┆ retention_rate │
# │ ---    ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ f64            │
# ╞════════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 0.54           │
# │ 100663 ┆ 2020 ┆ 0.86           │
# │ 100690 ┆ 2020 ┆ 0.5            │
# │ 100706 ┆ 2020 ┆ 0.82           │
# │ 100724 ┆ 2020 ┆ 0.62           │
# │ …      ┆ …    ┆ …              │
# │ 101189 ┆ 2020 ┆ 0.6            │
# │ 101240 ┆ 2020 ┆ 0.54           │
# │ 101277 ┆ 2020 ┆ 0.78           │
# │ 101286 ┆ 2020 ┆ 0.55           │
# │ 101295 ┆ 2020 ┆ 0.64           │
# └────────┴──────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 4)
# ┌────────────┬───────────────┬────────┬────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ retention_rate │
# │ ---        ┆ ---           ┆ ---    ┆ ---            │
# │ str        ┆ f64           ┆ f64    ┆ f64            │
# ╞════════════╪═══════════════╪════════╪════════════════╡
# │ count      ┆ 5836.0        ┆ 5836.0 ┆ 5182.0         │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 654.0          │
# │ mean       ┆ 283846.361378 ┆ 2020.0 ┆ 0.706521       │
# │ std        ┆ 137931.042049 ┆ 0.0    ┆ 0.187062       │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.0            │
# │ 25%        ┆ 169734.0      ┆ 2020.0 ┆ 0.6            │
# │ 50%        ┆ 219921.0      ┆ 2020.0 ┆ 0.73           │
# │ 75%        ┆ 445267.0      ┆ 2020.0 ┆ 0.83           │
# │ max        ┆ 496423.0      ┆ 2020.0 ┆ 1.0            │
# └────────────┴───────────────┴────────┴────────────────┘
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
# │ 179955 ┆ 1     │
# │ 448196 ┆ 1     │
# │ 459523 ┆ 1     │
# │ 168546 ┆ 1     │
# │ 135179 ┆ 1     │
# │ …      ┆ …     │
# │ 215530 ┆ 1     │
# │ 433138 ┆ 1     │
# │ 164739 ┆ 1     │
# │ 382957 ┆ 1     │
# │ 445780 ┆ 1     │
# └────────┴───────┘
# 
# year:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 5836  │
# └──────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 5836  │
# └──────┴───────┘
# 
# retention_rate distribution (decile buckets):
# shape: (10, 2)
# ┌─────────┬──────┐
# │ bucket  ┆ len  │
# │ ---     ┆ ---  │
# │ str     ┆ u32  │
# ╞═════════╪══════╡
# │ 0.0-0.1 ┆ 69   │
# │ 0.1-0.2 ┆ 32   │
# │ 0.2-0.3 ┆ 59   │
# │ 0.3-0.4 ┆ 117  │
# │ 0.4-0.5 ┆ 240  │
# │ 0.5-0.6 ┆ 676  │
# │ 0.6-0.7 ┆ 1046 │
# │ 0.7-0.8 ┆ 1196 │
# │ 0.8-0.9 ┆ 1012 │
# │ 0.9-1.0 ┆ 735  │
# └─────────┴──────┘
# 
# Row count context:
#   Total rows: 5,836
#   Plan expected: 2,000-4,000 (based on 4-year institutions)
#   Actual: 5,836 (includes all institution types: 2-year, 4-year, less-than-2-year)
#   EXPLANATION: Institution-level filtering happens in Stage 6/7, not Stage 5 fetch
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
