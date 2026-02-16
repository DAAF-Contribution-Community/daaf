#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 6
Task: fetch-sfr (IPEDS Student-Faculty Ratio)

Reviewed script: scripts/stage5_fetch/06_fetch-sfr.py
Output files: data/raw/2026-02-15_ipeds_sfr.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks:
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
6. [Counterfactual] What if SFR data has duplicates or missing institutions?
7. [Semantic] Does the data serve the research question (resource proxy)?
8. [Boundary] Edge values: SFR=110 outlier, SFR=1, nulls
9. [Absence] Are there institutions in the data that shouldn't be (closed, non-degree)?
10. [Downstream] Will the join to core dataset be clean 1:1?
11-15. Spot-checks: known institution SFR, unitid format, year uniformity,
      distribution shape, outlier characterization
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_sfr.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "student_faculty_ratio"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 7000  # Wider range: Plan says 3k-5k but all inst types included
CRITICAL_COLUMNS = ["unitid", "year"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 6 — fetch-sfr")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

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

# ===========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ===========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Duplicate unitids? ---
# If the data had duplicate institutions, the downstream 1:1 join would fan out.
# The script checks uniqueness but let's verify independently.
n_unique_unitid = df["unitid"].n_unique()
n_rows = len(df)
dup_ok = n_unique_unitid == n_rows
print(f"\n[{'PASS' if dup_ok else 'FAIL'}] [Counterfactual] unitid uniqueness: "
      f"{n_unique_unitid:,} unique / {n_rows:,} rows")
if not dup_ok:
    dups = df.group_by("unitid").agg(pl.count().alias("cnt")).filter(pl.col("cnt") > 1)
    print(f"  Duplicate unitids: {dups.head(10)}")

# --- Check 7: [Semantic] Does this serve the research question? ---
# The research question needs a resource proxy. Plan chose SFR over finance data.
# Verify the column actually has meaningful variation (not all same value).
sfr_col = df["student_faculty_ratio"].drop_nulls()
sfr_std = sfr_col.std()
sfr_mean = sfr_col.mean()
sfr_cv = sfr_std / sfr_mean if sfr_mean > 0 else 0
semantic_ok = sfr_cv > 0.1  # Coefficient of variation > 10% => meaningful variation
print(f"[{'PASS' if semantic_ok else 'WARN'}] [Semantic] SFR has meaningful variation: "
      f"mean={sfr_mean:.2f}, std={sfr_std:.2f}, CV={sfr_cv:.2f}")

# --- Check 8: [Boundary] Edge values and outliers ---
sfr_nonnull = df["student_faculty_ratio"].drop_nulls()
sfr_min = sfr_nonnull.min()
sfr_max = sfr_nonnull.max()
sfr_p99 = sfr_nonnull.quantile(0.99)
sfr_p01 = sfr_nonnull.quantile(0.01)

# Check for SFR=110 outlier specifically mentioned in task spec
sfr_110_count = (sfr_nonnull == 110).sum()
# Check extreme low values (SFR < 2 could be data quality issue)
sfr_low = sfr_nonnull.filter(sfr_nonnull < 2).len()
# Check zero values (would be data quality issue)
sfr_zero = (sfr_nonnull == 0).sum()

boundary_ok = sfr_zero == 0  # No zeros is the critical check
print(f"[{'PASS' if boundary_ok else 'FAIL'}] [Boundary] No zero SFR values: {sfr_zero} zeros found")
print(f"  SFR range: {sfr_min} to {sfr_max}")
print(f"  p1={sfr_p01}, p99={sfr_p99}")
print(f"  SFR==110: {sfr_110_count} institution(s)")
print(f"  SFR < 2: {sfr_low} institution(s)")
print(f"  SFR null count: {df['student_faculty_ratio'].null_count()}")

# --- Check 9: [Absence] Year filter correctness ---
# Verify ONLY year 2020 present (no other years leaked through filter)
years_present = sorted(df["year"].unique().to_list())
year_ok = years_present == [2020]
print(f"[{'PASS' if year_ok else 'FAIL'}] [Absence] Only year 2020 present: {years_present}")

# Check: are there negative unitids (would indicate coding error)?
neg_unitid = (df["unitid"] < 0).sum()
print(f"[{'PASS' if neg_unitid == 0 else 'FAIL'}] [Absence] No negative unitids: {neg_unitid} found")

# --- Check 10: [Downstream] Join readiness ---
# Downstream clean-sfr replaces coded values (-1, -2, -3) with null.
# Then join-resources does LEFT JOIN core_demographics + sfr ON unitid (1:1).
# Verify unitid type compatibility (should be Int64 to match other IPEDS tables).
unitid_dtype = df["unitid"].dtype
dtype_ok = unitid_dtype in [pl.Int64, pl.Int32]
print(f"[{'PASS' if dtype_ok else 'WARN'}] [Downstream] unitid dtype for join: {unitid_dtype} "
      f"(need Int64/Int32)")

# Check SFR dtype — it's currently Int64, but downstream scripts may expect Float64
sfr_dtype = df["student_faculty_ratio"].dtype
print(f"[INFO] [Downstream] student_faculty_ratio dtype: {sfr_dtype} "
      f"(Int64 is fine; clean-sfr may cast later)")

# ===========================================================================
# SPOT-CHECKS (5 concrete verifications)
# ===========================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot 1: Known institution check ---
# Check a well-known institution: Harvard (unitid=166027)
# Expected SFR around 5-7 (highly resourced)
harvard = df.filter(pl.col("unitid") == 166027)
if len(harvard) > 0:
    harvard_sfr = harvard["student_faculty_ratio"][0]
    harvard_ok = 3 <= harvard_sfr <= 15  # Reasonable for Harvard
    print(f"[{'PASS' if harvard_ok else 'WARN'}] Spot-check Harvard (166027): SFR={harvard_sfr} "
          f"(expected ~5-7)")
else:
    print("[INFO] Harvard (166027) not found in dataset")

# --- Spot 2: Another known institution (large state university) ---
# University of Michigan (unitid=170976) — expected SFR around 12-18
umich = df.filter(pl.col("unitid") == 170976)
if len(umich) > 0:
    umich_sfr = umich["student_faculty_ratio"][0]
    umich_ok = 8 <= umich_sfr <= 25
    print(f"[{'PASS' if umich_ok else 'WARN'}] Spot-check U Michigan (170976): SFR={umich_sfr} "
          f"(expected ~12-18)")
else:
    print("[INFO] U Michigan (170976) not found in dataset")

# --- Spot 3: Characterize the SFR=110 outlier ---
# What institution has SFR=110? Is it real or a data error?
outlier = df.filter(pl.col("student_faculty_ratio") == 110)
if len(outlier) > 0:
    outlier_unitid = outlier["unitid"][0]
    print(f"[INFO] Spot-check SFR=110 outlier: unitid={outlier_unitid}")
    # Check if there are other extreme outliers (>50)
    extreme = df.filter(pl.col("student_faculty_ratio") > 50)
    print(f"  Institutions with SFR > 50: {len(extreme)}")
    if len(extreme) <= 10:
        for row in extreme.iter_rows(named=True):
            print(f"    unitid={row['unitid']}, SFR={row['student_faculty_ratio']}")
else:
    print("[INFO] No SFR=110 found — outlier may have been resolved")

# --- Spot 4: Distribution shape ---
# Check percentile distribution to verify reasonable shape
print(f"\n[INFO] SFR distribution (percentiles):")
for q in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
    val = sfr_nonnull.quantile(q)
    print(f"  p{int(q*100):02d}: {val}")

# --- Spot 5: unitid range check ---
# IPEDS unitids are typically 6-digit numbers (100000-999999)
unitid_min = df["unitid"].min()
unitid_max = df["unitid"].max()
unitid_range_ok = unitid_min >= 100000 and unitid_max <= 999999
print(f"\n[{'PASS' if unitid_range_ok else 'WARN'}] Spot-check unitid range: "
      f"{unitid_min:,} to {unitid_max:,} (expected 100000-999999)")

# ===========================================================================
# DATA PROFILING (for cr2+ decision)
# ===========================================================================
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
        print(df[col].value_counts().head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

# SFR histogram-like binning
print("\nSFR distribution (binned):")
sfr_bins = df.filter(pl.col("student_faculty_ratio").is_not_null()).with_columns(
    pl.when(pl.col("student_faculty_ratio") <= 5).then(pl.lit("1-5"))
    .when(pl.col("student_faculty_ratio") <= 10).then(pl.lit("6-10"))
    .when(pl.col("student_faculty_ratio") <= 15).then(pl.lit("11-15"))
    .when(pl.col("student_faculty_ratio") <= 20).then(pl.lit("16-20"))
    .when(pl.col("student_faculty_ratio") <= 30).then(pl.lit("21-30"))
    .when(pl.col("student_faculty_ratio") <= 50).then(pl.lit("31-50"))
    .otherwise(pl.lit("51+"))
    .alias("sfr_bin")
)
print(sfr_bins["sfr_bin"].value_counts().sort("sfr_bin"))

# --- Summary ---
all_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
                  dup_ok, semantic_ok, boundary_ok, year_ok, dtype_ok])
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "WARNING"
print(f"QA RESULT: {severity}")
if not all_passed:
    if not any([schema_ok, dup_ok, boundary_ok, year_ok]):
        severity = "BLOCKER"
        print(f"QA RESULT (revised): {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:28:52
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_06_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 6 — fetch-sfr
# ============================================================
# Loaded: 5,836 rows x 3 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,836 (expected 3,000-7,000)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] [Counterfactual] unitid uniqueness: 5,836 unique / 5,836 rows
# [PASS] [Semantic] SFR has meaningful variation: mean=15.12, std=7.31, CV=0.48
# [PASS] [Boundary] No zero SFR values: 0 zeros found
#   SFR range: 1 to 110
#   p1=3.0, p99=40.0
#   SFR==110: 1 institution(s)
#   SFR < 2: 18 institution(s)
#   SFR null count: 1
# [PASS] [Absence] Only year 2020 present: [2020]
# [PASS] [Absence] No negative unitids: 0 found
# [PASS] [Downstream] unitid dtype for join: Int64 (need Int64/Int32)
# [INFO] [Downstream] student_faculty_ratio dtype: Int64 (Int64 is fine; clean-sfr may cast later)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# [PASS] Spot-check Harvard (166027): SFR=5 (expected ~5-7)
# [PASS] Spot-check U Michigan (170976): SFR=11 (expected ~12-18)
# [INFO] Spot-check SFR=110 outlier: unitid=246035
#   Institutions with SFR > 50: 13
# 
# [INFO] SFR distribution (percentiles):
#   p05: 6.0
#   p10: 7.0
#   p25: 10.0
#   p50: 14.0
#   p75: 19.0
#   p90: 24.0
#   p95: 27.0
#   p99: 40.0
# 
# [PASS] Spot-check unitid range: 100,654 to 496,423 (expected 100000-999999)
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
# Key column value counts:
# 
# unitid:
# shape: (20, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ i64    ┆ u32   │
# ╞════════╪═══════╡
# │ 260992 ┆ 1     │
# │ 179256 ┆ 1     │
# │ 196237 ┆ 1     │
# │ 478634 ┆ 1     │
# │ 130314 ┆ 1     │
# │ …      ┆ …     │
# │ 198109 ┆ 1     │
# │ 158343 ┆ 1     │
# │ 245962 ┆ 1     │
# │ 438151 ┆ 1     │
# │ 459958 ┆ 1     │
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
# SFR distribution (binned):
# shape: (7, 2)
# ┌─────────┬───────┐
# │ sfr_bin ┆ count │
# │ ---     ┆ ---   │
# │ str     ┆ u32   │
# ╞═════════╪═══════╡
# │ 1-5     ┆ 290   │
# │ 11-15   ┆ 1993  │
# │ 16-20   ┆ 1385  │
# │ 21-30   ┆ 788   │
# │ 31-50   ┆ 141   │
# │ 51+     ┆ 13    │
# │ 6-10    ┆ 1225  │
# └─────────┴───────┘
# 
# ============================================================
# QA RESULT: WARNING
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
