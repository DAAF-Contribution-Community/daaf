#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 07

Reviewed script: scripts/stage6_clean/07_clean-retention.py
Output files: data/processed/2026-03-29_retention_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations (unitid, retention_rate)
2. Row count within expected range (2,500-6,500)
3. No suspicious distributions
4. No coded missing values (-1, -2, -3) remain
5. No nulls in critical column (unitid)
6. [Counterfactual] Verify scale detection logic by checking raw data
7. [Semantic] Confirm rescaled values serve research purpose (0-100 like grad rates)
8. [Boundary] Check for retention_rate == 0.0 or == 100.0 edge cases
9. [Absence] Verify no ftpt != 1 rows leaked through
10. [Downstream] Confirm unitid type and uniqueness for Stage 7 join
11-15. Spot-checks: trace specific institutions, verify rescaling math, check filter complement
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_retention_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_retention.parquet"
EXPECTED_COLUMNS = ["unitid", "retention_rate"]
EXPECTED_MIN_ROWS = 2500
EXPECTED_MAX_ROWS = 6500
CRITICAL_COLUMNS = ["unitid"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 07 — clean-retention")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded clean output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load raw for cross-reference
df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw input: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

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
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
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
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ==========================================================================

# --- Check 6 [Counterfactual]: Scale detection cross-reference ---
# INTENT: Verify the scale detection was correct by independently checking raw FT data
# REASONING: If scale detection was wrong, all retention_rate values are off by 100x
print("\n--- Lens: Counterfactual (Scale Detection) ---")
raw_ft = df_raw.filter(pl.col("ftpt") == 1)
raw_ft_rates = raw_ft["retention_rate"].drop_nulls()
raw_max = raw_ft_rates.max()
raw_min = raw_ft_rates.min()
raw_mean = raw_ft_rates.mean()
print(f"Raw FT retention_rate: min={raw_min}, max={raw_max}, mean={raw_mean:.4f}")

clean_rates = df["retention_rate"].drop_nulls()
clean_mean = clean_rates.mean()
clean_max = clean_rates.max()
clean_min = clean_rates.min()
print(f"Clean retention_rate: min={clean_min:.1f}, max={clean_max:.1f}, mean={clean_mean:.1f}")

# If raw was 0-1 and clean is 0-100, clean_mean should be ~100x raw_mean
if raw_max <= 1.0:
    ratio = clean_mean / raw_mean if raw_mean > 0 else 0
    scale_ok = 99.0 < ratio < 101.0
    print(f"Scale ratio (clean_mean / raw_mean): {ratio:.2f}")
    print(f"[{'PASS' if scale_ok else 'FAIL'}] Rescaling verification: ratio ~ 100x as expected")
else:
    print("[INFO] Raw data was already 0-100 scale, no rescaling expected")
    scale_ok = True

# --- Check 7 [Semantic]: Values serve research purpose (0-100 like grad rates) ---
# INTENT: Confirm retention_rate is on the same scale as graduation rates for
# meaningful comparison in regressions and descriptive statistics
print("\n--- Lens: Semantic (Research Purpose Alignment) ---")
# Retention rate should be comparable to graduation rates (0-100)
# A mean around 60-80 is plausible for FT retention at 4-year institutions
semantic_ok = 40.0 < clean_mean < 90.0
print(f"Clean retention_rate mean: {clean_mean:.1f}")
print(f"[{'PASS' if semantic_ok else 'WARN'}] Mean in plausible range for FT retention (40-90): {semantic_ok}")

# Check that the standard deviation is reasonable (not collapsed)
clean_std = clean_rates.std()
print(f"Clean retention_rate std: {clean_std:.1f}")
std_ok = clean_std > 5.0
print(f"[{'PASS' if std_ok else 'WARN'}] Standard deviation > 5 (sufficient spread): {std_ok}")

# --- Check 8 [Boundary]: Edge cases at 0.0 and 100.0 ---
# INTENT: Identify institutions at exact boundaries -- these could be data artifacts
print("\n--- Lens: Boundary (Edge Cases) ---")
count_zero = (clean_rates == 0.0).sum()
count_hundred = (clean_rates == 100.0).sum()
null_count = df["retention_rate"].null_count()
null_pct = null_count / len(df) * 100
print(f"retention_rate == 0.0: {count_zero} institutions")
print(f"retention_rate == 100.0: {count_hundred} institutions")
print(f"retention_rate null: {null_count} ({null_pct:.1f}%)")
# A few zeros might be real (tiny schools), many would be suspicious
boundary_ok = count_zero < 50
print(f"[{'PASS' if boundary_ok else 'WARN'}] Zero retention count < 50: {boundary_ok}")

# --- Check 9 [Absence]: No ftpt != 1 rows leaked through ---
# INTENT: The output should contain only FT retention rows. Cross-reference
# that the count matches the raw FT count.
print("\n--- Lens: Absence (Filter Completeness) ---")
raw_ft_count = raw_ft.shape[0]
clean_count = df.shape[0]
filter_match = raw_ft_count == clean_count
print(f"Raw ftpt==1 count: {raw_ft_count:,}")
print(f"Clean output count: {clean_count:,}")
print(f"[{'PASS' if filter_match else 'FAIL'}] Output matches raw FT count exactly")

# Since output has no ftpt column, verify indirectly by checking all raw unitids
# with ftpt==1 are present in clean
raw_ft_unitids = set(raw_ft["unitid"].to_list())
clean_unitids = set(df["unitid"].to_list())
missing_from_clean = raw_ft_unitids - clean_unitids
extra_in_clean = clean_unitids - raw_ft_unitids
print(f"Missing unitids (in raw FT but not clean): {len(missing_from_clean)}")
print(f"Extra unitids (in clean but not raw FT): {len(extra_in_clean)}")
absence_ok = len(missing_from_clean) == 0 and len(extra_in_clean) == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] Unitid sets match between raw FT and clean")

# --- Check 10 [Downstream]: Unitid type and uniqueness for Stage 7 join ---
# INTENT: Stage 7 join-resources will join on unitid -- confirm type compatibility
# and uniqueness to prevent fan-out
print("\n--- Lens: Downstream (Join Readiness) ---")
unitid_dtype = df["unitid"].dtype
unitid_unique = df["unitid"].n_unique()
unitid_total = df.shape[0]
print(f"unitid dtype: {unitid_dtype}")
print(f"unitid uniqueness: {unitid_unique:,} unique / {unitid_total:,} total")
downstream_ok = unitid_unique == unitid_total and unitid_dtype == pl.Int64
print(f"[{'PASS' if downstream_ok else 'FAIL'}] unitid is Int64 and unique (1:1 join safe)")

# ==========================================================================
# SPOT-CHECKS
# ==========================================================================
print("\n--- Spot-Checks ---")

# Spot-Check 1: Trace 3 specific institutions through raw -> clean
# Pick the first 3 unitids from raw FT data and verify their rescaled values
print("\nSpot-Check 1: Trace specific institutions through transformation")
sample_unitids = raw_ft.head(3)["unitid"].to_list()
for uid in sample_unitids:
    raw_val = raw_ft.filter(pl.col("unitid") == uid)["retention_rate"].item()
    if raw_val is not None:
        clean_val = df.filter(pl.col("unitid") == uid)["retention_rate"].item()
        if clean_val is not None:
            expected_clean = raw_val * 100 if raw_max <= 1.0 else raw_val
            match = abs(clean_val - expected_clean) < 0.001
            print(f"  unitid={uid}: raw={raw_val}, clean={clean_val}, expected={expected_clean:.1f} -> {'MATCH' if match else 'MISMATCH'}")
        else:
            print(f"  unitid={uid}: raw={raw_val}, clean=null (null preserved correctly)")
    else:
        clean_val = df.filter(pl.col("unitid") == uid)["retention_rate"].item()
        null_preserved = clean_val is None
        print(f"  unitid={uid}: raw=null, clean={clean_val} -> {'null preserved' if null_preserved else 'ERROR: null became value'}")

# Spot-Check 2: Verify rescaling math on a known value
print("\nSpot-Check 2: Verify rescaling on institution with known value")
# Find an institution with a "round" raw value like 0.75
known_inst = raw_ft.filter(
    pl.col("retention_rate").is_not_null() & (pl.col("retention_rate") == 0.75)
).head(1)
if known_inst.shape[0] > 0:
    uid = known_inst["unitid"].item()
    clean_val = df.filter(pl.col("unitid") == uid)["retention_rate"].item()
    sc2_ok = abs(clean_val - 75.0) < 0.001
    print(f"  unitid={uid}: raw=0.75, clean={clean_val} -> [{'PASS' if sc2_ok else 'FAIL'}] Expected 75.0")
else:
    # Pick any institution
    known_inst = raw_ft.filter(pl.col("retention_rate").is_not_null()).head(1)
    uid = known_inst["unitid"].item()
    raw_v = known_inst["retention_rate"].item()
    clean_v = df.filter(pl.col("unitid") == uid)["retention_rate"].item()
    sc2_ok = abs(clean_v - raw_v * 100) < 0.001
    print(f"  unitid={uid}: raw={raw_v}, clean={clean_v}, expected={raw_v*100:.2f} -> [{'PASS' if sc2_ok else 'FAIL'}]")

# Spot-Check 3: Filter complement -- verify PT and Total rows were removed
print("\nSpot-Check 3: Filter complement (what was excluded)")
raw_non_ft = df_raw.filter(pl.col("ftpt") != 1)
non_ft_count = raw_non_ft.shape[0]
expected_removed = df_raw.shape[0] - raw_ft.shape[0]
sc3_ok = non_ft_count == expected_removed
print(f"  Non-FT rows in raw: {non_ft_count:,}")
print(f"  Expected removed (total - FT): {expected_removed:,}")
print(f"  [{'PASS' if sc3_ok else 'FAIL'}] Non-FT complement is as expected")
# Check that no non-FT unitids have different retention rates that might confuse things
non_ft_ftpt_vals = raw_non_ft["ftpt"].unique().sort().to_list()
print(f"  Non-FT ftpt values: {non_ft_ftpt_vals} (should be [2, 99])")

# Spot-Check 4: Null preservation -- institutions with null raw retention should stay null
print("\nSpot-Check 4: Null preservation")
raw_ft_nulls = raw_ft.filter(pl.col("retention_rate").is_null())
raw_null_unitids = raw_ft_nulls["unitid"].to_list()[:5]
null_preserved_count = 0
null_tested = 0
for uid in raw_null_unitids:
    clean_row = df.filter(pl.col("unitid") == uid)
    if clean_row.shape[0] == 1:
        null_tested += 1
        if clean_row["retention_rate"].item() is None:
            null_preserved_count += 1
sc4_ok = null_preserved_count == null_tested
print(f"  Tested {null_tested} institutions with null raw retention_rate")
print(f"  Preserved as null in clean: {null_preserved_count}")
print(f"  [{'PASS' if sc4_ok else 'FAIL'}] Null values preserved through transformation")

# Spot-Check 5: Boundary institution -- check institution closest to 0
print("\nSpot-Check 5: Boundary case -- lowest retention rate")
min_rate_row = df.filter(pl.col("retention_rate").is_not_null()).sort("retention_rate").head(1)
if min_rate_row.shape[0] > 0:
    min_uid = min_rate_row["unitid"].item()
    min_val = min_rate_row["retention_rate"].item()
    raw_min_val = raw_ft.filter(pl.col("unitid") == min_uid)["retention_rate"].item()
    sc5_ok = min_val >= 0.0
    print(f"  Lowest retention: unitid={min_uid}, clean={min_val:.1f}, raw={raw_min_val}")
    print(f"  [{'PASS' if sc5_ok else 'FAIL'}] Lowest value >= 0")

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

print("\nretention_rate distribution (non-null):")
rates = df["retention_rate"].drop_nulls()
print(f"  Count: {rates.len():,}")
print(f"  Mean:  {rates.mean():.2f}")
print(f"  Std:   {rates.std():.2f}")
print(f"  Min:   {rates.min():.2f}")
print(f"  25%:   {rates.quantile(0.25):.2f}")
print(f"  50%:   {rates.quantile(0.50):.2f}")
print(f"  75%:   {rates.quantile(0.75):.2f}")
print(f"  Max:   {rates.max():.2f}")

print(f"\nNull rate in retention_rate: {df['retention_rate'].null_count()} / {len(df)} ({df['retention_rate'].null_count() / len(df) * 100:.1f}%)")

# Histogram buckets for retention_rate
print("\nRetention rate distribution (10-point buckets):")
non_null = df.filter(pl.col("retention_rate").is_not_null())
for low in range(0, 100, 10):
    high = low + 10
    bucket = non_null.filter(
        (pl.col("retention_rate") >= low) & (pl.col("retention_rate") < high)
    ).shape[0]
    print(f"  [{low:3d}, {high:3d}): {bucket:,}")
# Count exactly 100
exactly_100 = non_null.filter(pl.col("retention_rate") == 100.0).shape[0]
print(f"  [100, 100]: {exactly_100:,}")

print("\nunitid dtype:", df["unitid"].dtype)
print("unitid range:", df["unitid"].min(), "-", df["unitid"].max())

# --- Summary ---
all_checks = [schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
              scale_ok, semantic_ok, std_ok, boundary_ok, filter_match,
              absence_ok, downstream_ok]
all_passed = all(all_checks)
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if not all_passed:
    failed = [name for name, ok in zip(
        ["schema", "rows", "dist", "coded", "nulls", "scale", "semantic",
         "std", "boundary", "filter_match", "absence", "downstream"],
        all_checks
    ) if not ok]
    print(f"Failed checks: {failed}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:58:28
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 07 — clean-retention
# ============================================================
# Loaded clean output: 5,836 rows x 2 cols
# Loaded raw input: 17,508 rows x 9 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,836 (expected 2,500-6,500)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Lens: Counterfactual (Scale Detection) ---
# Raw FT retention_rate: min=0.0, max=1.0, mean=0.7065
# Clean retention_rate: min=0.0, max=100.0, mean=70.7
# Scale ratio (clean_mean / raw_mean): 100.00
# [PASS] Rescaling verification: ratio ~ 100x as expected
# 
# --- Lens: Semantic (Research Purpose Alignment) ---
# Clean retention_rate mean: 70.7
# [PASS] Mean in plausible range for FT retention (40-90): True
# Clean retention_rate std: 18.7
# [PASS] Standard deviation > 5 (sufficient spread): True
# 
# --- Lens: Boundary (Edge Cases) ---
# retention_rate == 0.0: 55 institutions
# retention_rate == 100.0: 333 institutions
# retention_rate null: 654 (11.2%)
# [WARN] Zero retention count < 50: False
# 
# --- Lens: Absence (Filter Completeness) ---
# Raw ftpt==1 count: 5,836
# Clean output count: 5,836
# [PASS] Output matches raw FT count exactly
# Missing unitids (in raw FT but not clean): 0
# Extra unitids (in clean but not raw FT): 0
# [PASS] Unitid sets match between raw FT and clean
# 
# --- Lens: Downstream (Join Readiness) ---
# unitid dtype: Int64
# unitid uniqueness: 5,836 unique / 5,836 total
# [PASS] unitid is Int64 and unique (1:1 join safe)
# 
# --- Spot-Checks ---
# 
# Spot-Check 1: Trace specific institutions through transformation
#   unitid=100654: raw=0.54, clean=54.0, expected=54.0 -> MATCH
#   unitid=100663: raw=0.86, clean=86.0, expected=86.0 -> MATCH
#   unitid=100690: raw=0.5, clean=50.0, expected=50.0 -> MATCH
# 
# Spot-Check 2: Verify rescaling on institution with known value
#   unitid=105543: raw=0.75, clean=75.0 -> [PASS] Expected 75.0
# 
# Spot-Check 3: Filter complement (what was excluded)
#   Non-FT rows in raw: 11,672
#   Expected removed (total - FT): 11,672
#   [PASS] Non-FT complement is as expected
#   Non-FT ftpt values: [2, 99] (should be [2, 99])
# 
# Spot-Check 4: Null preservation
#   Tested 5 institutions with null raw retention_rate
#   Preserved as null in clean: 5
#   [PASS] Null values preserved through transformation
# 
# Spot-Check 5: Boundary case -- lowest retention rate
#   Lowest retention: unitid=110918, clean=0.0, raw=0.0
#   [PASS] Lowest value >= 0
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 2)
# ┌────────┬────────────────┐
# │ unitid ┆ retention_rate │
# │ ---    ┆ ---            │
# │ i64    ┆ f64            │
# ╞════════╪════════════════╡
# │ 100654 ┆ 54.0           │
# │ 100663 ┆ 86.0           │
# │ 100690 ┆ 50.0           │
# │ 100706 ┆ 82.0           │
# │ 100724 ┆ 62.0           │
# │ 100751 ┆ 87.0           │
# │ 100760 ┆ 59.0           │
# │ 100812 ┆ null           │
# │ 100830 ┆ 70.0           │
# │ 100858 ┆ 92.0           │
# └────────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 3)
# ┌────────────┬───────────────┬────────────────┐
# │ statistic  ┆ unitid        ┆ retention_rate │
# │ ---        ┆ ---           ┆ ---            │
# │ str        ┆ f64           ┆ f64            │
# ╞════════════╪═══════════════╪════════════════╡
# │ count      ┆ 5836.0        ┆ 5182.0         │
# │ null_count ┆ 0.0           ┆ 654.0          │
# │ mean       ┆ 283846.361378 ┆ 70.652065      │
# │ std        ┆ 137931.042049 ┆ 18.70617       │
# │ min        ┆ 100654.0      ┆ 0.0            │
# │ 25%        ┆ 169734.0      ┆ 60.0           │
# │ 50%        ┆ 219921.0      ┆ 73.0           │
# │ 75%        ┆ 445267.0      ┆ 83.0           │
# │ max        ┆ 496423.0      ┆ 100.0          │
# └────────────┴───────────────┴────────────────┘
# 
# retention_rate distribution (non-null):
#   Count: 5,182
#   Mean:  70.65
#   Std:   18.71
#   Min:   0.00
#   25%:   60.00
#   50%:   73.00
#   75%:   83.00
#   Max:   100.00
# 
# Null rate in retention_rate: 654 / 5836 (11.2%)
# 
# Retention rate distribution (10-point buckets):
#   [  0,  10): 69
#   [ 10,  20): 32
#   [ 20,  30): 59
#   [ 30,  40): 117
#   [ 40,  50): 240
#   [ 50,  60): 676
#   [ 60,  70): 1,046
#   [ 70,  80): 1,196
#   [ 80,  90): 1,012
#   [ 90, 100): 402
#   [100, 100]: 333
# 
# unitid dtype: Int64
# unitid range: 100654 - 496423
# 
# ============================================================
# QA RESULT: ISSUES_FOUND
# Failed checks: ['boundary']
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
