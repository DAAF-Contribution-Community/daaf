#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 07

Reviewed script: scripts/stage5_fetch/07_fetch-retention.py
Output files: data/raw/2026-03-29_ipeds_retention.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range (accounting for ftpt multiplier)
3. No suspicious distributions
4. Coded values checked in integer columns
5. No nulls in critical identifier columns
--- Script-Specific Checks (Five Lenses) ---
6. Counterfactual: retention_rate dtype is Float64 (Risk Register item)
7. Semantic: ftpt values contain {1, 2} needed for downstream analysis
8. Boundary: retention_rate values are in [0, 1] range (proportions)
9. Absence: no rows with ftpt not in {1, 2, 99} -- no unexpected categories
10. Downstream: unitid x ftpt should give unique rows (no duplicates for Stage 6 filter)
--- Spot Checks ---
11. Row count divisibility: 17,508 should divide evenly by 3 (one per ftpt)
12. Trace specific unitid: verify it has exactly 3 rows (one per ftpt category)
13. Verify retention_rate null pattern: is nullness concentrated in certain ftpt categories?
14. Verify fips column has plausible state-level codes (1-78)
15. Cross-check: unique unitid count * 3 == total rows (balanced panel)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_retention.parquet"

# Plan.md expectations (adjusted for understanding that raw fetch includes all ftpt)
EXPECTED_COLUMNS = ["unitid", "year", "fips", "ftpt", "retention_rate"]
# Plan says 5,000-15,000 rows for the fetch, but that assumed ftpt==1 filter.
# Raw data has 3 ftpt categories, so expect 3x: 15,000-45,000 is plausible.
# Actual: 17,508 rows = 5,836 institutions * 3 ftpt values.
EXPECTED_MIN_ROWS = 5000   # Conservative lower bound
EXPECTED_MAX_ROWS = 25000  # Allow for 3x multiplier from ftpt
CRITICAL_COLUMNS = ["unitid", "year", "ftpt"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 07 (fetch-retention)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Check 1: Schema ---
# INTENT: Verify Plan-required columns exist. Extra columns are acceptable in raw data.
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (raw data): {extra_cols}")

# --- Check 2: Row count ---
# INTENT: Verify row count is reasonable. Plan expected 5,000-15,000 but that
# assumed ftpt==1 filter (applied in Stage 6). Raw data has 3 ftpt values.
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'WARN'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
# INTENT: Detect degenerate columns (all same value, all zeros).
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
# INTENT: Check for coded missing values in integer columns.
# Stage 5 (fetch) is NOT expected to clean these, but their presence should be documented.
coded_issues = []
for col_name in df.columns:
    dtype = df[col_name].dtype
    if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64):
        for code in CODED_MISSING_VALUES:
            count = (df[col_name] == code).sum()
            if count > 0:
                coded_issues.append(f"{col_name} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'INFO'}] Coded values: ", end="")
print("None found in integer columns" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
# INTENT: Identifier columns (unitid, year, ftpt) must have zero nulls.
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# --- Check 6 (Counterfactual): retention_rate dtype ---
# INTENT: Risk Register flags retention_rate as potentially String type.
# Verify it is Float64 so Stage 6 doesn't need String-to-Float casting.
retention_dtype = df["retention_rate"].dtype
dtype_ok = retention_dtype in (pl.Float32, pl.Float64)
print(f"[{'PASS' if dtype_ok else 'WARN'}] retention_rate dtype: {retention_dtype} (expected Float64)")
if not dtype_ok:
    print("  WARNING: Retention rate is NOT numeric. Stage 6 must cast to Float.")

# --- Check 7 (Semantic): ftpt values contain {1, 2} ---
# INTENT: Plan requires ftpt==1 (FT) for analysis. Check both FT and PT exist.
ftpt_values = sorted(df["ftpt"].unique().to_list())
has_ft = 1 in ftpt_values
has_pt = 2 in ftpt_values
semantic_ok = has_ft and has_pt
print(f"[{'PASS' if semantic_ok else 'FAIL'}] ftpt contains 1 (FT) and 2 (PT): {ftpt_values}")

# --- Check 8 (Boundary): retention_rate range ---
# INTENT: Retention rates should be proportions in [0, 1]. Values outside
# this range indicate data quality issues or misinterpretation.
rr_nonnull = df["retention_rate"].drop_nulls()
if len(rr_nonnull) > 0:
    rr_min = rr_nonnull.min()
    rr_max = rr_nonnull.max()
    range_ok = rr_min >= 0.0 and rr_max <= 1.0
    print(f"[{'PASS' if range_ok else 'FAIL'}] retention_rate range: [{rr_min}, {rr_max}] (expected [0, 1])")
    if not range_ok:
        out_of_range = df.filter(
            (pl.col("retention_rate") < 0) | (pl.col("retention_rate") > 1)
        ).shape[0]
        print(f"  {out_of_range} rows outside [0, 1]")
else:
    print("[FAIL] retention_rate: ALL values are null")
    range_ok = False

# --- Check 9 (Absence): No unexpected ftpt categories ---
# INTENT: Verify only expected ftpt values exist (1=FT, 2=PT, 99=Total).
expected_ftpt = {1, 2, 99}
actual_ftpt = set(ftpt_values)
unexpected_ftpt = actual_ftpt - expected_ftpt
absence_ok = len(unexpected_ftpt) == 0
print(f"[{'PASS' if absence_ok else 'WARN'}] No unexpected ftpt values: ", end="")
print("All in {1, 2, 99}" if absence_ok else f"Unexpected: {unexpected_ftpt}")

# --- Check 10 (Downstream): unitid x ftpt uniqueness ---
# INTENT: Stage 6 will filter to ftpt==1. If unitid x ftpt is not unique,
# the filter could produce duplicates that corrupt downstream joins.
unique_combos = df.select("unitid", "ftpt").n_unique()
downstream_ok = unique_combos == len(df)
print(f"[{'PASS' if downstream_ok else 'FAIL'}] unitid x ftpt uniqueness: {unique_combos:,} combos vs {len(df):,} rows")
if not downstream_ok:
    dupes = len(df) - unique_combos
    print(f"  WARNING: {dupes} duplicate unitid x ftpt combinations")

# --- Spot Check 11: Row count divisibility ---
# INTENT: If data is balanced (every institution has all 3 ftpt values),
# row count should be divisible by 3.
n_ftpt = len(ftpt_values)
divisible = row_count % n_ftpt == 0
institutions = row_count // n_ftpt if divisible else "N/A"
print(f"[{'PASS' if divisible else 'INFO'}] Row divisibility: {row_count} / {n_ftpt} ftpt values = {institutions} institutions")

# --- Spot Check 12: Trace specific unitid ---
# INTENT: Pick a known institution and verify it has exactly 3 rows.
sample_unitid = df["unitid"].head(1).item()
unitid_rows = df.filter(pl.col("unitid") == sample_unitid)
trace_ok = len(unitid_rows) == n_ftpt
print(f"[{'PASS' if trace_ok else 'WARN'}] Trace unitid {sample_unitid}: {len(unitid_rows)} rows (expected {n_ftpt})")
print(f"  ftpt values for this unitid: {sorted(unitid_rows['ftpt'].to_list())}")
print(f"  retention_rate values: {unitid_rows['retention_rate'].to_list()}")

# --- Spot Check 13: Null pattern by ftpt ---
# INTENT: Check if retention_rate nullness varies by ftpt category.
# PT retention rates may have higher missingness than FT.
print("\n--- Null pattern by ftpt ---")
for ftpt_val in sorted(ftpt_values):
    subset = df.filter(pl.col("ftpt") == ftpt_val)
    null_count = subset["retention_rate"].null_count()
    null_pct = null_count / len(subset) * 100
    print(f"  ftpt={ftpt_val}: {null_count:,} nulls ({null_pct:.1f}%) of {len(subset):,} rows")

# --- Spot Check 14: FIPS codes plausibility ---
# INTENT: FIPS state codes should be 1-78 (US states and territories).
fips_values = df["fips"].unique().sort()
fips_min = fips_values.min()
fips_max = fips_values.max()
n_fips = fips_values.len()
fips_ok = fips_min >= 1 and fips_max <= 78
print(f"[{'PASS' if fips_ok else 'WARN'}] FIPS codes: {n_fips} unique, range [{fips_min}, {fips_max}] (expected 1-78)")

# --- Spot Check 15: Balanced panel check ---
# INTENT: Verify unique unitids * n_ftpt == total rows (perfectly balanced).
unique_unitids = df["unitid"].n_unique()
expected_total = unique_unitids * n_ftpt
balanced = expected_total == row_count
print(f"[{'PASS' if balanced else 'WARN'}] Balanced panel: {unique_unitids:,} unitids x {n_ftpt} ftpt = {expected_total:,} (actual: {row_count:,})")

# --- Summary ---
all_base_passed = all([schema_ok, rows_ok, dist_ok, nulls_ok])
all_specific_passed = all([dtype_ok, semantic_ok, range_ok, absence_ok, downstream_ok])
all_spot_passed = all([divisible, trace_ok, fips_ok, balanced])
all_passed = all_base_passed and all_specific_passed and all_spot_passed

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES FOUND"
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

print("\nColumn dtypes:")
for col_name in df.columns:
    print(f"  {col_name}: {df[col_name].dtype}")

print("\nretention_rate by ftpt (for understanding distribution):")
for ftpt_val in sorted(ftpt_values):
    subset = df.filter(pl.col("ftpt") == ftpt_val)["retention_rate"].drop_nulls()
    if len(subset) > 0:
        print(f"\n  ftpt={ftpt_val}: n={len(subset):,}, mean={subset.mean():.3f}, "
              f"median={subset.median():.3f}, min={subset.min():.3f}, max={subset.max():.3f}")

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\nftpt distribution:")
print(df["ftpt"].value_counts().sort("ftpt"))

print("\nString columns sample values:")
for col_name in df.columns:
    if df[col_name].dtype == pl.Utf8:
        non_null = df[col_name].drop_nulls()
        null_pct = df[col_name].null_count() / len(df) * 100
        print(f"\n  {col_name}: {non_null.n_unique()} unique, {null_pct:.1f}% null")
        print(f"    Sample: {non_null.head(5).to_list()}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:51:23
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_07_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 07 (fetch-retention)
# ============================================================
# Loaded: 17,508 rows x 9 cols
# 
# [PASS] Schema: All expected columns present
#   Extra columns (raw data): ['returning_students', 'prev_cohort', 'prev_exclusions', 'prev_cohort_adj']
# [PASS] Row count: 17,508 (expected 5,000-25,000)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None found in integer columns
# [PASS] Critical nulls: None
# [PASS] retention_rate dtype: Float64 (expected Float64)
# [PASS] ftpt contains 1 (FT) and 2 (PT): [1, 2, 99]
# [PASS] retention_rate range: [0.0, 1.0] (expected [0, 1])
# [PASS] No unexpected ftpt values: All in {1, 2, 99}
# [PASS] unitid x ftpt uniqueness: 17,508 combos vs 17,508 rows
# [PASS] Row divisibility: 17508 / 3 ftpt values = 5836 institutions
# [PASS] Trace unitid 100654: 3 rows (expected 3)
#   ftpt values for this unitid: [1, 2, 99]
#   retention_rate values: [0.54, 0.33, 0.54]
# 
# --- Null pattern by ftpt ---
#   ftpt=1: 654 nulls (11.2%) of 5,836 rows
#   ftpt=2: 2,846 nulls (48.8%) of 5,836 rows
#   ftpt=99: 596 nulls (10.2%) of 5,836 rows
# [PASS] FIPS codes: 59 unique, range [1, 78] (expected 1-78)
# [PASS] Balanced panel: 5,836 unitids x 3 ftpt = 17,508 (actual: 17,508)
# 
# ============================================================
# QA RESULT: ISSUES FOUND
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 9)
# ┌────────┬──────┬──────┬──────┬───┬────────────────┬─────────────┬────────────────┬────────────────┐
# │ unitid ┆ year ┆ fips ┆ ftpt ┆ … ┆ returning_stud ┆ prev_cohort ┆ prev_exclusion ┆ prev_cohort_ad │
# │ ---    ┆ ---  ┆ ---  ┆ ---  ┆   ┆ ents           ┆ ---         ┆ s              ┆ j              │
# │ i64    ┆ i64  ┆ i64  ┆ i64  ┆   ┆ ---            ┆ str         ┆ ---            ┆ ---            │
# │        ┆      ┆      ┆      ┆   ┆ str            ┆             ┆ str            ┆ str            │
# ╞════════╪══════╪══════╪══════╪═══╪════════════════╪═════════════╪════════════════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 911            ┆ 1688        ┆ 2              ┆ 1686           │
# │ 100654 ┆ 2020 ┆ 1    ┆ 2    ┆ … ┆ 2              ┆ 6           ┆ 0              ┆ 6              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99   ┆ … ┆ 913            ┆ 1694        ┆ 2              ┆ 1692           │
# │ 100663 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 1982           ┆ 2294        ┆ 0              ┆ 2294           │
# │ 100663 ┆ 2020 ┆ 1    ┆ 2    ┆ … ┆ 20             ┆ 42          ┆ 0              ┆ 42             │
# │ 100663 ┆ 2020 ┆ 1    ┆ 99   ┆ … ┆ 2002           ┆ 2336        ┆ 0              ┆ 2336           │
# │ 100690 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 1              ┆ 2           ┆ 0              ┆ 2              │
# │ 100690 ┆ 2020 ┆ 1    ┆ 2    ┆ … ┆ null           ┆ null        ┆ null           ┆ null           │
# │ 100690 ┆ 2020 ┆ 1    ┆ 99   ┆ … ┆ 1              ┆ 2           ┆ 0              ┆ 2              │
# │ 100706 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 1218           ┆ 1489        ┆ 0              ┆ 1489           │
# └────────┴──────┴──────┴──────┴───┴────────────────┴─────────────┴────────────────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 10)
# ┌────────────┬────────────┬─────────┬──────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year    ┆ fips     ┆ … ┆ returning ┆ prev_coho ┆ prev_excl ┆ prev_coho │
# │ ---        ┆ ---        ┆ ---     ┆ ---      ┆   ┆ _students ┆ rt        ┆ usions    ┆ rt_adj    │
# │ str        ┆ f64        ┆ f64     ┆ f64      ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---       │
# │            ┆            ┆         ┆          ┆   ┆ str       ┆ str       ┆ str       ┆ str       │
# ╞════════════╪════════════╪═════════╪══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 17508.0    ┆ 17508.0 ┆ 17508.0  ┆ … ┆ 15104     ┆ 15104     ┆ 15104     ┆ 15104     │
# │ null_count ┆ 0.0        ┆ 0.0     ┆ 0.0      ┆ … ┆ 2404      ┆ 2404      ┆ 2404      ┆ 2404      │
# │ mean       ┆ 283846.361 ┆ 2020.0  ┆ 29.32865 ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │            ┆ 378        ┆         ┆          ┆   ┆           ┆           ┆           ┆           │
# │ std        ┆ 137923.163 ┆ 0.0     ┆ 16.82904 ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │            ┆ 202        ┆         ┆          ┆   ┆           ┆           ┆           ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0  ┆ 1.0      ┆ … ┆ 0         ┆ 0         ┆ 0         ┆ 0         │
# │ 25%        ┆ 169734.0   ┆ 2020.0  ┆ 13.0     ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │ 50%        ┆ 219921.0   ┆ 2020.0  ┆ 30.0     ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │ 75%        ┆ 445267.0   ┆ 2020.0  ┆ 42.0     ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │ max        ┆ 496423.0   ┆ 2020.0  ┆ 78.0     ┆ … ┆ 999       ┆ 999       ┆ 96        ┆ 999       │
# └────────────┴────────────┴─────────┴──────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Column dtypes:
#   unitid: Int64
#   year: Int64
#   fips: Int64
#   ftpt: Int64
#   retention_rate: Float64
#   returning_students: String
#   prev_cohort: String
#   prev_exclusions: String
#   prev_cohort_adj: String
# 
# retention_rate by ftpt (for understanding distribution):
# 
#   ftpt=1: n=5,182, mean=0.707, median=0.730, min=0.000, max=1.000
# 
#   ftpt=2: n=2,990, mean=0.510, median=0.480, min=0.000, max=1.000
# 
#   ftpt=99: n=5,240, mean=0.689, median=0.710, min=0.000, max=1.000
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 17508 │
# └──────┴───────┘
# 
# ftpt distribution:
# shape: (3, 2)
# ┌──────┬───────┐
# │ ftpt ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 5836  │
# │ 2    ┆ 5836  │
# │ 99   ┆ 5836  │
# └──────┴───────┘
# 
# String columns sample values:
# 
#   returning_students: 1619 unique, 13.7% null
#     Sample: ['911', '2', '913', '1982', '20']
# 
#   prev_cohort: 1971 unique, 13.7% null
#     Sample: ['1688', '6', '1694', '2294', '42']
# 
#   prev_exclusions: 70 unique, 13.7% null
#     Sample: ['2', '0', '2', '0', '0']
# 
#   prev_cohort_adj: 1987 unique, 13.7% null
#     Sample: ['1686', '6', '1692', '2294', '42']
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
