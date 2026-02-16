#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 4.1 (clean-sfr)

Reviewed script: scripts/stage6_clean/06_clean-sfr.py
Output files: data/processed/2026-02-15_sfr_clean.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks:
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns (unitid, year)
--- Script-specific checks (5 Skeptical Lenses) ---
6. Counterfactual: What if coded values existed in non-SFR columns?
7. Semantic: Does the cleaning serve the research question (resource proxy)?
8. Boundary: Edge cases — zero SFR, SFR=1, SFR=110 outlier
9. Absence: Are there OTHER negative values or suspicious sentinels beyond -1,-2,-3?
10. Downstream: Will join-resources (Step 6.1) get what it expects?
--- Spot-checks (5) ---
11. Trace unitid 246035 (known SFR=110 outlier) — preserved?
12. Verify mean recalculation independently
13. Compare raw vs cleaned row-by-row for the null row
14. Check for duplicate unitid (should be 1:1 for year=2020)
15. Verify SFR dtype is suitable for downstream float operations
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_sfr_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_sfr.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "student_faculty_ratio"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 6000
CRITICAL_COLUMNS = ["unitid", "year"]  # These must have zero nulls
SFR_COLUMN = "student_faculty_ratio"

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 4.1 (clean-sfr)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded cleaned: {df.shape[0]:,} rows x {df.shape[1]} cols")

raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {raw.shape[0]:,} rows x {raw.shape[1]} cols")

# ==========================================
# DEFAULT CHECKS (5)
# ==========================================

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

# --- Check 5: Critical nulls (unitid, year must never be null) ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# ==========================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# ==========================================

# --- Check 6: Counterfactual Lens ---
# What if coded values existed in non-SFR columns (unitid, year)?
# The script only cleans SFR. If unitid/year had -1/-2/-3, they'd pass through.
# For identifiers this is correct — but let's verify no such values exist.
print("\n--- Counterfactual Lens ---")
non_sfr_coded = []
for col in ["unitid", "year"]:
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            non_sfr_coded.append(f"{col} has {count} value(s) of {code}")
counterfactual_ok = len(non_sfr_coded) == 0
print(f"[{'PASS' if counterfactual_ok else 'WARN'}] No coded values in identifier columns: ", end="")
print("Confirmed" if counterfactual_ok else "; ".join(non_sfr_coded))

# --- Check 7: Semantic Lens ---
# Does this serve the research question? SFR is a resource proxy for regression models.
# The cleaning should preserve real SFR values and only null out missing sentinels.
# Verify no real positive SFR values were converted to null.
print("\n--- Semantic Lens ---")
raw_non_null_positive = raw.filter(
    (pl.col(SFR_COLUMN).is_not_null()) & (pl.col(SFR_COLUMN) > 0)
).height
clean_non_null_positive = df.filter(
    (pl.col(SFR_COLUMN).is_not_null()) & (pl.col(SFR_COLUMN) > 0)
).height
semantic_ok = raw_non_null_positive == clean_non_null_positive
print(f"[{'PASS' if semantic_ok else 'FAIL'}] Positive SFR values preserved: raw={raw_non_null_positive:,}, clean={clean_non_null_positive:,}")

# --- Check 8: Boundary Lens ---
# Edge cases: SFR=1 (very low), SFR=110 (known outlier at unitid 246035), SFR=0 (impossible)
print("\n--- Boundary Lens ---")
sfr_valid = df.filter(pl.col(SFR_COLUMN).is_not_null())
sfr_min = sfr_valid[SFR_COLUMN].min()
sfr_max = sfr_valid[SFR_COLUMN].max()
zeros = df.filter(pl.col(SFR_COLUMN) == 0).height
boundary_min_ok = sfr_min >= 1  # SFR of 0 is impossible
boundary_zero_ok = zeros == 0
print(f"[{'PASS' if boundary_min_ok else 'FAIL'}] Min SFR >= 1: min={sfr_min}")
print(f"[{'PASS' if boundary_zero_ok else 'FAIL'}] No zero SFR values: count={zeros}")
print(f"[INFO] Max SFR = {sfr_max} (known outlier at unitid 246035)")

# Count institutions at extreme boundaries
sfr_eq_1 = df.filter(pl.col(SFR_COLUMN) == 1).height
sfr_gt_50 = df.filter(pl.col(SFR_COLUMN) > 50).height
print(f"[INFO] SFR == 1 (minimum): {sfr_eq_1} institutions")
print(f"[INFO] SFR > 50 (high): {sfr_gt_50} institutions")

# --- Check 9: Absence Lens ---
# Are there OTHER suspicious sentinel values beyond -1,-2,-3?
# Check for -4, -5, -9, 0, 999, etc. that might be alternative coding.
print("\n--- Absence Lens ---")
suspicious_sentinels = [0, -4, -5, -9, -99, 999, 9999]
absence_issues = []
for val in suspicious_sentinels:
    count = df.filter(pl.col(SFR_COLUMN) == val).height
    if count > 0:
        absence_issues.append(f"SFR={val}: {count} occurrences")
absence_ok = len(absence_issues) == 0
print(f"[{'PASS' if absence_ok else 'WARN'}] No alternative sentinel values: ", end="")
print("None found" if absence_ok else "; ".join(absence_issues))

# Also check: are there any negative SFR values remaining (beyond -1,-2,-3)?
neg_sfr = df.filter(pl.col(SFR_COLUMN) < 0).height
print(f"[{'PASS' if neg_sfr == 0 else 'FAIL'}] No negative SFR remaining: count={neg_sfr}")

# --- Check 10: Downstream Lens ---
# join-resources (Step 6.1) will LEFT JOIN on unitid. Verify:
# - unitid is suitable as a join key (non-null, consistent type)
# - year=2020 is present (analysis year)
# - SFR null rate is reasonable for analysis (not too many nulls)
print("\n--- Downstream Lens ---")
unitid_unique = df["unitid"].n_unique()
unitid_total = df.height
unitid_duplicate = unitid_total - unitid_unique
downstream_unique_ok = unitid_duplicate == 0
print(f"[{'PASS' if downstream_unique_ok else 'WARN'}] unitid uniqueness: {unitid_unique:,} unique / {unitid_total:,} total ({unitid_duplicate} duplicates)")

year_vals = df["year"].unique().to_list()
year_2020_present = 2020 in year_vals
print(f"[{'PASS' if year_2020_present else 'FAIL'}] Year 2020 present: {sorted(year_vals)}")

sfr_null_rate = df[SFR_COLUMN].null_count() / df.height
downstream_null_ok = sfr_null_rate < 0.30
print(f"[{'PASS' if downstream_null_ok else 'WARN'}] SFR null rate for join: {sfr_null_rate:.4%}")

# ==========================================
# SPOT-CHECKS (5)
# ==========================================

# --- Spot-check 11: Trace unitid 246035 (known SFR=110 outlier) ---
print("\n--- Spot-checks ---")
outlier_raw = raw.filter(pl.col("unitid") == 246035)
outlier_clean = df.filter(pl.col("unitid") == 246035)
if outlier_raw.height > 0 and outlier_clean.height > 0:
    raw_sfr = outlier_raw[SFR_COLUMN][0]
    clean_sfr = outlier_clean[SFR_COLUMN][0]
    outlier_preserved = raw_sfr == clean_sfr and clean_sfr == 110
    print(f"[{'PASS' if outlier_preserved else 'FAIL'}] unitid 246035 outlier: raw_SFR={raw_sfr}, clean_SFR={clean_sfr} (expected 110)")
elif outlier_raw.height == 0:
    print(f"[INFO] unitid 246035 not found in raw data — may not be in year=2020 subset")
else:
    print(f"[FAIL] unitid 246035 present in raw but not in cleaned data")

# --- Spot-check 12: Independently recalculate mean SFR ---
sfr_non_null = df.filter(pl.col(SFR_COLUMN).is_not_null())
manual_mean = sfr_non_null[SFR_COLUMN].sum() / sfr_non_null.height
polars_mean = sfr_non_null[SFR_COLUMN].mean()
mean_match = abs(manual_mean - polars_mean) < 0.01
print(f"[{'PASS' if mean_match else 'FAIL'}] Mean recalculation: manual={manual_mean:.4f}, polars={polars_mean:.4f}")

# --- Spot-check 13: Compare raw vs cleaned for the null row ---
# The execution log showed 1 null in raw, 1 null in cleaned. Verify it's the same row.
raw_null_rows = raw.filter(pl.col(SFR_COLUMN).is_null())
clean_null_rows = df.filter(pl.col(SFR_COLUMN).is_null())
print(f"[INFO] Raw null SFR rows: {raw_null_rows.height}, unitids: {raw_null_rows['unitid'].to_list()}")
print(f"[INFO] Clean null SFR rows: {clean_null_rows.height}, unitids: {clean_null_rows['unitid'].to_list()}")
null_same = (raw_null_rows.height == clean_null_rows.height and
             set(raw_null_rows["unitid"].to_list()) == set(clean_null_rows["unitid"].to_list()))
print(f"[{'PASS' if null_same else 'FAIL'}] Null rows identical between raw and cleaned")

# --- Spot-check 14: Duplicate unitid check (should be 1 row per institution for year=2020) ---
dup_unitids = df.group_by("unitid").len().filter(pl.col("len") > 1)
dup_ok = dup_unitids.height == 0
print(f"[{'PASS' if dup_ok else 'WARN'}] No duplicate unitids: {dup_unitids.height} duplicated")
if not dup_ok:
    print(f"  Duplicate unitids: {dup_unitids.head(5)}")

# --- Spot-check 15: SFR dtype check for downstream float operations ---
sfr_dtype = df[SFR_COLUMN].dtype
# Int64 is fine — Polars will handle it in downstream mean/regression
# But let's verify the non-null values are all positive integers or floats
all_positive = sfr_non_null[SFR_COLUMN].min() >= 1
print(f"[INFO] SFR dtype: {sfr_dtype} (Int64 is acceptable for downstream operations)")
print(f"[{'PASS' if all_positive else 'FAIL'}] All non-null SFR values >= 1: min={sfr_non_null[SFR_COLUMN].min()}")

# ==========================================
# SUMMARY
# ==========================================
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
    counterfactual_ok, semantic_ok, boundary_min_ok, boundary_zero_ok,
    absence_ok, neg_sfr == 0,
    downstream_unique_ok, year_2020_present, downstream_null_ok,
    mean_match, null_same, dup_ok, all_positive
]
# outlier_preserved may not be available if unitid 246035 not in data
all_passed = all(all_checks)
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)

# ==========================================
# DATA PROFILING (for cr2+ decision)
# ==========================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nSFR distribution percentiles:")
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    val = df[SFR_COLUMN].drop_nulls().quantile(p / 100)
    print(f"  P{p}: {val}")

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\nSFR value counts (top 20):")
print(df[SFR_COLUMN].value_counts().sort("count", descending=True).head(20))

print("\nSFR histogram bins:")
bins = [0, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150]
for i in range(len(bins) - 1):
    count = df.filter(
        (pl.col(SFR_COLUMN) >= bins[i]) & (pl.col(SFR_COLUMN) < bins[i + 1])
    ).height
    print(f"  [{bins[i]:3d}, {bins[i+1]:3d}): {count:,}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:57:33
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage6_06_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 4.1 (clean-sfr)
# ============================================================
# Loaded cleaned: 5,836 rows x 3 cols
# Loaded raw: 5,836 rows x 3 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,836 (expected 3,000-6,000)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Counterfactual Lens ---
# [PASS] No coded values in identifier columns: Confirmed
# 
# --- Semantic Lens ---
# [PASS] Positive SFR values preserved: raw=5,835, clean=5,835
# 
# --- Boundary Lens ---
# [PASS] Min SFR >= 1: min=1
# [PASS] No zero SFR values: count=0
# [INFO] Max SFR = 110 (known outlier at unitid 246035)
# [INFO] SFR == 1 (minimum): 18 institutions
# [INFO] SFR > 50 (high): 13 institutions
# 
# --- Absence Lens ---
# [PASS] No alternative sentinel values: None found
# [PASS] No negative SFR remaining: count=0
# 
# --- Downstream Lens ---
# [PASS] unitid uniqueness: 5,836 unique / 5,836 total (0 duplicates)
# [PASS] Year 2020 present: [2020]
# [PASS] SFR null rate for join: 0.0171%
# 
# --- Spot-checks ---
# [PASS] unitid 246035 outlier: raw_SFR=110, clean_SFR=110 (expected 110)
# [PASS] Mean recalculation: manual=15.1169, polars=15.1169
# [INFO] Raw null SFR rows: 1, unitids: [121992]
# [INFO] Clean null SFR rows: 1, unitids: [121992]
# [PASS] Null rows identical between raw and cleaned
# [PASS] No duplicate unitids: 0 duplicated
# [INFO] SFR dtype: Int64 (Int64 is acceptable for downstream operations)
# [PASS] All non-null SFR values >= 1: min=1
# 
# ============================================================
# QA RESULT: BLOCKER
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 3)
# ┌────────┬──────┬───────────────────────┐
# │ unitid ┆ year ┆ student_faculty_ratio │
# │ ---    ┆ ---  ┆ ---                   │
# │ i64    ┆ i64  ┆ i64                   │
# ╞════════╪══════╪═══════════════════════╡
# │ 100654 ┆ 2020 ┆ 18                    │
# │ 100663 ┆ 2020 ┆ 20                    │
# │ 100690 ┆ 2020 ┆ 13                    │
# │ 100706 ┆ 2020 ┆ 19                    │
# │ 100724 ┆ 2020 ┆ 15                    │
# │ …      ┆ …    ┆ …                     │
# │ 101189 ┆ 2020 ┆ 13                    │
# │ 101240 ┆ 2020 ┆ 15                    │
# │ 101277 ┆ 2020 ┆ 22                    │
# │ 101286 ┆ 2020 ┆ 13                    │
# │ 101295 ┆ 2020 ┆ 17                    │
# └────────┴──────┴───────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 4)
# ┌────────────┬───────────────┬────────┬───────────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ student_faculty_ratio │
# │ ---        ┆ ---           ┆ ---    ┆ ---                   │
# │ str        ┆ f64           ┆ f64    ┆ f64                   │
# ╞════════════╪═══════════════╪════════╪═══════════════════════╡
# │ count      ┆ 5836.0        ┆ 5836.0 ┆ 5835.0                │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 1.0                   │
# │ mean       ┆ 283846.361378 ┆ 2020.0 ┆ 15.116881             │
# │ std        ┆ 137931.042049 ┆ 0.0    ┆ 7.306764              │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 1.0                   │
# │ 25%        ┆ 169734.0      ┆ 2020.0 ┆ 10.0                  │
# │ 50%        ┆ 219921.0      ┆ 2020.0 ┆ 14.0                  │
# │ 75%        ┆ 445267.0      ┆ 2020.0 ┆ 19.0                  │
# │ max        ┆ 496423.0      ┆ 2020.0 ┆ 110.0                 │
# └────────────┴───────────────┴────────┴───────────────────────┘
# 
# SFR distribution percentiles:
#   P1: 3.0
#   P5: 6.0
#   P10: 7.0
#   P25: 10.0
#   P50: 14.0
#   P75: 19.0
#   P90: 24.0
#   P95: 27.0
#   P99: 40.0
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
# SFR value counts (top 20):
# shape: (20, 2)
# ┌───────────────────────┬───────┐
# │ student_faculty_ratio ┆ count │
# │ ---                   ┆ ---   │
# │ i64                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ 15                    ┆ 521   │
# │ 10                    ┆ 409   │
# │ 12                    ┆ 404   │
# │ 14                    ┆ 385   │
# │ 11                    ┆ 344   │
# │ …                     ┆ …     │
# │ 25                    ┆ 133   │
# │ 21                    ┆ 133   │
# │ 5                     ┆ 105   │
# │ 22                    ┆ 99    │
# │ 24                    ┆ 88    │
# └───────────────────────┴───────┘
# 
# SFR histogram bins:
#   [  0,   5): 185
#   [  5,  10): 921
#   [ 10,  15): 1,881
#   [ 15,  20): 1,569
#   [ 20,  25): 744
#   [ 25,  30): 327
#   [ 30,  40): 145
#   [ 40,  50): 46
#   [ 50,  75): 14
#   [ 75, 100): 2
#   [100, 150): 1
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
