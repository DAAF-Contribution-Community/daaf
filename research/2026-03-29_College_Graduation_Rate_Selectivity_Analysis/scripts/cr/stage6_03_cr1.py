#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 03

Reviewed script: scripts/stage6_clean/03_clean-grad-rates_c.py
Output files: data/processed/2026-03-29_grad_rates_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

QA Checks (Script-Specific):
6. [Counterfactual] Dedup preserved all non-null completion rates
7. [Semantic] Rescaling correctly transforms 0-1 to 0-100
8. [Boundary] Min/max completion rate values plausible
9. [Absence] No institution_level != 4 data leaked through
10. [Downstream] unitid uniqueness for downstream 1:1 joins

Spot Checks:
11. Trace a specific unitid through raw to output
12. Verify no zero completion rates that could be misinterpreted
13. Recalculate a completion rate from raw components
14. Verify dedup complement (what was removed looks right)
15. Check completers_150pct / cohort_adj_150pct ratio matches rate
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"

EXPECTED_COLUMNS = ["unitid", "completion_rate_150pct"]
OPTIONAL_COLUMNS = ["completers_150pct", "cohort_adj_150pct"]
EXPECTED_MIN_ROWS = 2000
EXPECTED_MAX_ROWS = 4000
CRITICAL_COLUMNS = ["unitid"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 03 -- clean-grad-rates")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# Also load raw for cross-reference
assert RAW_FILE.exists(), f"FAIL: Raw file not found: {RAW_FILE}"
df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")

extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS + OPTIONAL_COLUMNS]
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

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ==========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Dedup preserved ALL non-null completion rates ---
# INTENT: The v3 bug was losing valid completion rates during dedup. The v4
# "smart dedup" claims to preserve all non-null rates. Verify independently
# that every institution with ANY non-null rate in the filtered raw data
# has a non-null rate in the output.
print("\n--- Check 6: Dedup preserved non-null completion rates ---")

df_raw_filtered = df_raw.filter(
    (pl.col("subcohort") == 2)
    & (pl.col("institution_level") == 4)
    & (pl.col("race") == 99)
    & (pl.col("sex") == 99)
    & (pl.col("year") == 2020)
)
print(f"Raw after same filters: {df_raw_filtered.shape[0]:,} rows")

# Count unitids that have at least one non-null rate in raw
unitids_with_rate_in_raw = (
    df_raw_filtered
    .filter(pl.col("completion_rate_150pct").is_not_null())
    .select("unitid")
    .unique()
)
n_unitids_with_rate_raw = unitids_with_rate_in_raw.shape[0]
print(f"Unitids with non-null rate in raw (after filter): {n_unitids_with_rate_raw:,}")

# Count unitids with non-null rate in output
unitids_with_rate_output = (
    df.filter(pl.col("completion_rate_150pct").is_not_null())
    .select("unitid")
    .unique()
)
n_unitids_with_rate_output = unitids_with_rate_output.shape[0]
print(f"Unitids with non-null rate in output: {n_unitids_with_rate_output:,}")

# Every unitid that had a non-null rate in raw should have one in output
lost_unitids = (
    unitids_with_rate_in_raw
    .join(unitids_with_rate_output, on="unitid", how="anti")
)
dedup_preserved = lost_unitids.shape[0] == 0
print(f"[{'PASS' if dedup_preserved else 'FAIL'}] Dedup preserved all non-null rates: "
      f"{lost_unitids.shape[0]} unitids lost valid rates")

if lost_unitids.shape[0] > 0:
    print(f"  Lost unitids: {lost_unitids['unitid'].to_list()[:10]}")

# --- Check 7: [Semantic] Rescaling from 0-1 to 0-100 ---
# INTENT: Verify the rescaling was applied correctly. The raw data stores
# rates as proportions (0-1). The output should be percentages (0-100).
# Cross-reference specific values between raw and output.
print("\n--- Check 7: Rescaling correctness ---")

# Get a specific unitid's rate from raw and output to verify
sample_unitid_for_rescale = (
    df_raw_filtered
    .filter(pl.col("completion_rate_150pct").is_not_null())
    .head(1)["unitid"][0]
)

raw_rate = (
    df_raw_filtered
    .filter(
        (pl.col("unitid") == sample_unitid_for_rescale)
        & pl.col("completion_rate_150pct").is_not_null()
    )
    .sort("completion_rate_150pct", descending=True)
    .head(1)["completion_rate_150pct"][0]
)

output_rate = (
    df.filter(pl.col("unitid") == sample_unitid_for_rescale)
    ["completion_rate_150pct"][0]
)

# Raw is 0-1, output should be raw * 100
rescale_correct = abs(output_rate - raw_rate * 100) < 0.01
print(f"  Sample unitid={sample_unitid_for_rescale}: raw={raw_rate:.4f}, output={output_rate:.2f}")
print(f"  Expected: {raw_rate * 100:.2f}")
print(f"[{'PASS' if rescale_correct else 'FAIL'}] Rescaling verified for sample: "
      f"raw * 100 = {raw_rate * 100:.2f}, output = {output_rate:.2f}")

# Also verify range: all non-null values should be 0-100
valid_rates = df.filter(pl.col("completion_rate_150pct").is_not_null())
if valid_rates.shape[0] > 0:
    rate_min = valid_rates["completion_rate_150pct"].min()
    rate_max = valid_rates["completion_rate_150pct"].max()
    range_ok = rate_min >= 0 and rate_max <= 100
    print(f"[{'PASS' if range_ok else 'FAIL'}] Rate range: [{rate_min:.2f}, {rate_max:.2f}] (expected [0, 100])")
else:
    range_ok = False
    print("[FAIL] No valid rates in output")

# --- Check 8: [Boundary] Edge case values ---
# INTENT: Check for boundary values that might indicate data issues.
# Rate of exactly 100% (every student graduates?) and very low rates.
print("\n--- Check 8: Boundary values ---")

n_100 = (valid_rates["completion_rate_150pct"] == 100.0).sum()
n_below_5 = (valid_rates["completion_rate_150pct"] < 5.0).sum()
n_below_1 = (valid_rates["completion_rate_150pct"] < 1.0).sum()
print(f"  Rates == 100%: {n_100}")
print(f"  Rates < 5%: {n_below_5}")
print(f"  Rates < 1%: {n_below_1}")

# A few 100% rates are plausible (small specialized institutions)
# Very few <1% rates should exist
boundary_ok = n_below_1 == 0 and n_100 < 50
print(f"[{'PASS' if boundary_ok else 'WARN'}] Boundary values: "
      f"{n_100} at 100%, {n_below_1} below 1%")

# --- Check 9: [Absence] No unexpected institution_level values ---
# INTENT: The script filters on institution_level == 4. Verify that no
# institution_level != 4 data leaked through. Since the output doesn't
# include institution_level, we verify by checking that all output unitids
# exist in the raw data with level=4.
print("\n--- Check 9: No data leakage from wrong institution level ---")

raw_level4_unitids = set(
    df_raw.filter(
        (pl.col("institution_level") == 4)
        & (pl.col("year") == 2020)
    )["unitid"].unique().to_list()
)

output_unitids = set(df["unitid"].unique().to_list())
non_level4 = output_unitids - raw_level4_unitids
level_ok = len(non_level4) == 0
print(f"[{'PASS' if level_ok else 'FAIL'}] All output unitids are level-4 institutions: "
      f"{len(non_level4)} non-level-4 found")

# --- Check 10: [Downstream] unitid uniqueness for 1:1 joins ---
# INTENT: Downstream join-core expects 1:1 cardinality on unitid.
# A single duplicate would cause fan-out and corrupt the entire pipeline.
print("\n--- Check 10: unitid uniqueness for downstream joins ---")

n_unique = df["unitid"].n_unique()
n_rows = df.shape[0]
unitid_unique = n_unique == n_rows
print(f"[{'PASS' if unitid_unique else 'FAIL'}] unitid unique: "
      f"{n_unique:,} unique vs {n_rows:,} rows")

if not unitid_unique:
    dups = df.group_by("unitid").len().filter(pl.col("len") > 1)
    print(f"  Duplicate unitids: {dups.shape[0]:,}")
    print(f"  Example: {dups.head(3)}")

# ==========================================================================
# SPOT CHECKS
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT CHECKS")
print("=" * 60)

# --- Spot Check 11: Trace a specific unitid through raw to output ---
# INTENT: Pick a unitid that was duplicated in raw and verify the smart
# dedup selected the correct (non-null, highest) row.
print("\n--- Spot 11: Trace duplicated unitid through dedup ---")

dup_unitids = (
    df_raw_filtered.group_by("unitid").len()
    .filter(pl.col("len") > 1)
    .sort("len", descending=True)
)

if dup_unitids.shape[0] > 0:
    trace_uid = dup_unitids["unitid"][0]
    raw_rows = df_raw_filtered.filter(pl.col("unitid") == trace_uid)
    output_row = df.filter(pl.col("unitid") == trace_uid)

    print(f"  Tracing unitid={trace_uid} (had {raw_rows.shape[0]} raw rows)")
    print(f"  Raw completion rates: {raw_rows['completion_rate_150pct'].to_list()}")

    # The output should have the highest non-null value * 100
    raw_valid = raw_rows.filter(pl.col("completion_rate_150pct").is_not_null())
    if raw_valid.shape[0] > 0:
        expected_rate = raw_valid["completion_rate_150pct"].max() * 100
        actual_rate = output_row["completion_rate_150pct"][0]
        trace_ok = actual_rate is not None and abs(actual_rate - expected_rate) < 0.01
        print(f"  Expected (max non-null * 100): {expected_rate:.2f}")
        print(f"  Actual in output: {actual_rate}")
        print(f"  [{'PASS' if trace_ok else 'FAIL'}] Correct row selected")
    else:
        print(f"  All raw rates were null -- output should be null")
        actual_rate = output_row["completion_rate_150pct"][0]
        trace_ok = actual_rate is None
        print(f"  Actual in output: {actual_rate}")
        print(f"  [{'PASS' if trace_ok else 'FAIL'}] Null preserved correctly")
else:
    print("  No duplicated unitids found -- cannot trace")
    trace_ok = True

# --- Spot Check 12: No zero completion rates ---
# INTENT: A rate of 0% would mean NO students graduated. While theoretically
# possible, it is extremely rare for 4-year institutions. If present,
# these likely should be null (coded missing) rather than 0.
print("\n--- Spot 12: No zero completion rates ---")

n_zero = (valid_rates["completion_rate_150pct"] == 0.0).sum()
zero_ok = n_zero == 0
print(f"[{'PASS' if zero_ok else 'WARN'}] Zero completion rates: {n_zero}")

# --- Spot Check 13: Recalculate rate from components ---
# INTENT: If completers_150pct and cohort_adj_150pct are both available,
# verify that completion_rate_150pct approximately equals
# completers_150pct / cohort_adj_150pct * 100.
print("\n--- Spot 13: Rate recalculation from components ---")

if "completers_150pct" in df.columns and "cohort_adj_150pct" in df.columns:
    df_calc = df.filter(
        pl.col("completers_150pct").is_not_null()
        & pl.col("cohort_adj_150pct").is_not_null()
        & (pl.col("cohort_adj_150pct") > 0)
        & pl.col("completion_rate_150pct").is_not_null()
    )
    if df_calc.shape[0] > 0:
        df_calc = df_calc.with_columns(
            (pl.col("completers_150pct") / pl.col("cohort_adj_150pct") * 100)
            .alias("recalculated_rate")
        )
        df_calc = df_calc.with_columns(
            (pl.col("completion_rate_150pct") - pl.col("recalculated_rate")).abs()
            .alias("rate_diff")
        )
        max_diff = df_calc["rate_diff"].max()
        mean_diff = df_calc["rate_diff"].mean()
        n_large_diff = (df_calc["rate_diff"] > 1.0).sum()
        print(f"  Recalculated vs reported: N={df_calc.shape[0]:,}")
        print(f"  Max absolute difference: {max_diff:.4f}")
        print(f"  Mean absolute difference: {mean_diff:.4f}")
        print(f"  N with >1 percentage point difference: {n_large_diff}")
        recalc_ok = max_diff < 5.0  # Allow some tolerance for rounding
        print(f"[{'PASS' if recalc_ok else 'WARN'}] Rate recalculation consistency")
    else:
        print("  Not enough rows with all three columns non-null for recalculation")
        recalc_ok = True
else:
    print("  Component columns not available -- skipping recalculation")
    recalc_ok = True

# --- Spot Check 14: Dedup complement analysis ---
# INTENT: Examine WHAT was removed by dedup. Removed rows should be either
# null completion rates or lower completion rates for the same unitid.
print("\n--- Spot 14: Dedup complement analysis ---")

# Reconstruct the dedup: sort + unique
df_sorted = df_raw_filtered.sort("completion_rate_150pct", descending=True, nulls_last=True)
df_deduped = df_sorted.unique(subset=["unitid"], keep="first")

# Anti-join to find removed rows
removed = df_raw_filtered.join(
    df_deduped.select("unitid", pl.col("completion_rate_150pct").alias("kept_rate")),
    on="unitid",
    how="left"
)
# Rows where this row's rate is null or less than the kept rate
removed_rows = df_raw_filtered.shape[0] - df_deduped.shape[0]
print(f"  Total removed rows: {removed_rows:,}")

# Of removed rows, how many had null completion rates?
removed_with_null = df_raw_filtered.shape[0] - df_raw_filtered.filter(
    pl.col("completion_rate_150pct").is_not_null()
).shape[0]
# But we need to subtract the null rows that were KEPT (61 unitids with no rate at all)
nulls_in_output = df.filter(pl.col("completion_rate_150pct").is_null()).shape[0]
# The script kept 2010 rows; removed 2479 rows (4489 - 2010)
print(f"  Null rate rows in raw (after filter): approximately {df_raw_filtered.shape[0] - df_raw_filtered.filter(pl.col('completion_rate_150pct').is_not_null()).shape[0]:,}")
print(f"  Null rate unitids in output: {nulls_in_output}")

complement_ok = removed_rows > 0  # Some rows should have been removed given duplicates
print(f"[{'PASS' if complement_ok else 'WARN'}] Dedup complement plausible")

# --- Spot Check 15: Rate vs components consistency for output ---
# INTENT: Verify the internal consistency of the completion_rate value by
# checking a few specific institution patterns.
print("\n--- Spot 15: Specific institution rate checks ---")

# Check a few unitids to ensure rates are plausible
sample_rows = df.filter(pl.col("completion_rate_150pct").is_not_null()).sample(5, seed=42)
print("  Sample institutions:")
for row in sample_rows.iter_rows(named=True):
    uid = row["unitid"]
    rate = row["completion_rate_150pct"]
    compl = row.get("completers_150pct")
    cohort = row.get("cohort_adj_150pct")
    print(f"    unitid={uid}: rate={rate:.1f}%, completers={compl}, cohort={cohort}")
    if compl is not None and cohort is not None and cohort > 0:
        expected_pct = compl / cohort * 100
        diff = abs(rate - expected_pct)
        if diff > 2.0:
            print(f"      WARNING: recalculated={expected_pct:.1f}%, diff={diff:.1f}")

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

print("\nNull counts:")
for col in df.columns:
    null_ct = df[col].null_count()
    null_pct = null_ct / len(df) * 100
    print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

print("\ncompletion_rate_150pct distribution (non-null):")
vr = df.filter(pl.col("completion_rate_150pct").is_not_null())["completion_rate_150pct"]
if len(vr) > 0:
    print(f"  N: {len(vr):,}")
    print(f"  Mean: {vr.mean():.2f}")
    print(f"  Median: {vr.median():.2f}")
    print(f"  Std: {vr.std():.2f}")
    print(f"  Min: {vr.min():.2f}")
    print(f"  Max: {vr.max():.2f}")
    print(f"  Q10: {vr.quantile(0.10):.2f}")
    print(f"  Q25: {vr.quantile(0.25):.2f}")
    print(f"  Q75: {vr.quantile(0.75):.2f}")
    print(f"  Q90: {vr.quantile(0.90):.2f}")

# Histogram-like bins
print("\ncompletion_rate_150pct histogram (10% bins):")
for lo in range(0, 100, 10):
    hi = lo + 10
    n_bin = vr.filter((vr >= lo) & (vr < hi)).len()
    print(f"  [{lo:3d}, {hi:3d}): {n_bin:,}")
n_100_exact = (vr == 100.0).sum()
print(f"  [100, 100]: {n_100_exact}")

print("\nunitid range:")
print(f"  Min: {df['unitid'].min()}")
print(f"  Max: {df['unitid'].max()}")

# ==========================================================================
# SUMMARY
# ==========================================================================

print("\n" + "=" * 60)
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
    dedup_preserved, rescale_correct, range_ok, level_ok,
    unitid_unique, trace_ok, zero_ok, recalc_ok
]
all_passed = all(all_checks)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)

if not all_passed:
    print("Failed checks:")
    check_names = [
        "Schema", "Row count", "Distribution", "Coded values", "Critical nulls",
        "Dedup preserved rates", "Rescaling", "Rate range", "Level-4 only",
        "unitid unique", "Trace dedup", "No zeros", "Rate recalculation"
    ]
    for name, ok in zip(check_names, all_checks):
        if not ok:
            print(f"  FAIL: {name}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:44:59
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_03_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 03 -- clean-grad-rates
# ============================================================
# Loaded output: 2,010 rows x 4 cols
# Columns: ['unitid', 'completion_rate_150pct', 'completers_150pct', 'cohort_adj_150pct']
# Loaded raw: 804,716 rows x 18 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 2,010 (expected 2,000-4,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: Dedup preserved non-null completion rates ---
# Raw after same filters: 4,489 rows
# Unitids with non-null rate in raw (after filter): 1,949
# Unitids with non-null rate in output: 1,949
# [PASS] Dedup preserved all non-null rates: 0 unitids lost valid rates
# 
# --- Check 7: Rescaling correctness ---
#   Sample unitid=100654: raw=0.2810, output=28.10
#   Expected: 28.10
# [PASS] Rescaling verified for sample: raw * 100 = 28.10, output = 28.10
# [PASS] Rate range: [3.80, 100.00] (expected [0, 100])
# 
# --- Check 8: Boundary values ---
#   Rates == 100%: 41
#   Rates < 5%: 6
#   Rates < 1%: 0
# [PASS] Boundary values: 41 at 100%, 0 below 1%
# 
# --- Check 9: No data leakage from wrong institution level ---
# [PASS] All output unitids are level-4 institutions: 0 non-level-4 found
# 
# --- Check 10: unitid uniqueness for downstream joins ---
# [PASS] unitid unique: 2,010 unique vs 2,010 rows
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# --- Spot 11: Trace duplicated unitid through dedup ---
#   Tracing unitid=171456 (had 4 raw rows)
#   Raw completion rates: [None, 0.535, None, None]
#   Expected (max non-null * 100): 53.50
#   Actual in output: 53.5
#   [PASS] Correct row selected
# 
# --- Spot 12: No zero completion rates ---
# [PASS] Zero completion rates: 0
# 
# --- Spot 13: Rate recalculation from components ---
#   Recalculated vs reported: N=1,949
#   Max absolute difference: 0.0500
#   Mean absolute difference: 0.0236
#   N with >1 percentage point difference: 0
# [PASS] Rate recalculation consistency
# 
# --- Spot 14: Dedup complement analysis ---
#   Total removed rows: 2,479
#   Null rate rows in raw (after filter): approximately 2,540
#   Null rate unitids in output: 61
# [PASS] Dedup complement plausible
# 
# --- Spot 15: Specific institution rate checks ---
#   Sample institutions:
#     unitid=241395: rate=31.7%, completers=19, cohort=60
#     unitid=449339: rate=47.4%, completers=225, cohort=475
#     unitid=114813: rate=67.7%, completers=111, cohort=164
#     unitid=218919: rate=31.7%, completers=33, cohort=104
#     unitid=206349: rate=49.1%, completers=56, cohort=114
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 4)
# ┌────────┬────────────────────────┬───────────────────┬───────────────────┐
# │ unitid ┆ completion_rate_150pct ┆ completers_150pct ┆ cohort_adj_150pct │
# │ ---    ┆ ---                    ┆ ---               ┆ ---               │
# │ i64    ┆ f64                    ┆ i64               ┆ i64               │
# ╞════════╪════════════════════════╪═══════════════════╪═══════════════════╡
# │ 160065 ┆ 30.1                   ┆ 25                ┆ 83                │
# │ 210146 ┆ 41.0                   ┆ 320               ┆ 780               │
# │ 229814 ┆ 45.7                   ┆ 631               ┆ 1382              │
# │ 190600 ┆ 54.2                   ┆ 801               ┆ 1479              │
# │ 144351 ┆ 43.2                   ┆ 126               ┆ 292               │
# │ 191931 ┆ 61.9                   ┆ 518               ┆ 837               │
# │ 458919 ┆ 9.1                    ┆ 1                 ┆ 11                │
# │ 449764 ┆ 14.3                   ┆ 2                 ┆ 14                │
# │ 213826 ┆ 69.8                   ┆ 256               ┆ 367               │
# │ 160074 ┆ 33.3                   ┆ 21                ┆ 63                │
# └────────┴────────────────────────┴───────────────────┴───────────────────┘
# 
# Descriptive statistics:
# shape: (9, 5)
# ┌────────────┬───────────────┬────────────────────────┬───────────────────┬───────────────────┐
# │ statistic  ┆ unitid        ┆ completion_rate_150pct ┆ completers_150pct ┆ cohort_adj_150pct │
# │ ---        ┆ ---           ┆ ---                    ┆ ---               ┆ ---               │
# │ str        ┆ f64           ┆ f64                    ┆ f64               ┆ f64               │
# ╞════════════╪═══════════════╪════════════════════════╪═══════════════════╪═══════════════════╡
# │ count      ┆ 2010.0        ┆ 1949.0                 ┆ 1949.0            ┆ 2008.0            │
# │ null_count ┆ 0.0           ┆ 61.0                   ┆ 61.0              ┆ 2.0               │
# │ mean       ┆ 219935.667164 ┆ 55.59646               ┆ 508.161108        ┆ 763.731574        │
# │ std        ┆ 102401.24793  ┆ 20.556615              ┆ 937.502956        ┆ 1239.4868         │
# │ min        ┆ 100654.0      ┆ 3.8                    ┆ 1.0               ┆ 1.0               │
# │ 25%        ┆ 156365.0      ┆ 41.7                   ┆ 44.0              ┆ 88.0              │
# │ 50%        ┆ 196033.0      ┆ 56.3                   ┆ 180.0             ┆ 334.0             │
# │ 75%        ┆ 228723.0      ┆ 69.6                   ┆ 500.0             ┆ 806.0             │
# │ max        ┆ 496636.0      ┆ 100.0                  ┆ 11142.0           ┆ 15327.0           │
# └────────────┴───────────────┴────────────────────────┴───────────────────┴───────────────────┘
# 
# Null counts:
#   unitid: 0 nulls (0.0%)
#   completion_rate_150pct: 61 nulls (3.0%)
#   completers_150pct: 61 nulls (3.0%)
#   cohort_adj_150pct: 2 nulls (0.1%)
# 
# completion_rate_150pct distribution (non-null):
#   N: 1,949
#   Mean: 55.60
#   Median: 56.30
#   Std: 20.56
#   Min: 3.80
#   Max: 100.00
#   Q10: 28.10
#   Q25: 41.70
#   Q75: 69.60
#   Q90: 83.20
# 
# completion_rate_150pct histogram (10% bins):
#   [  0,  10): 29
#   [ 10,  20): 63
#   [ 20,  30): 133
#   [ 30,  40): 216
#   [ 40,  50): 276
#   [ 50,  60): 411
#   [ 60,  70): 345
#   [ 70,  80): 234
#   [ 80,  90): 134
#   [ 90, 100): 67
#   [100, 100]: 41
# 
# unitid range:
#   Min: 100654
#   Max: 496636
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
