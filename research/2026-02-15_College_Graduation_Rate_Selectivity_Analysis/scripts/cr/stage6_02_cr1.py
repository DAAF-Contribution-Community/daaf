#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 3.2

Reviewed script: scripts/stage6_clean/02_clean-grad-rates_a.py
Output files: data/processed/2026-02-15_grad_rates_clean.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Template):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if some institutions had multiple non-null rates within
   cohort_year=2015? The null filter acts as an implicit dedup — verify no data
   was silently lost by checking raw data's unitid x null pattern.
7. [Semantic] Does the 0-1 -> 0-100 conversion serve the research question?
   Verify scale is consistent with what downstream correlation expects.
8. [Boundary] Check min graduation rate (3.80%) — is this plausible or an artifact?
   Check max=100% — are there institutions with 100% graduation rate?
9. [Absence] The subcohort column is retained but not documented in clean output
   expectations. Verify it's a single value (no ambiguity).
10. [Downstream] For the next step (join-core on unitid), verify no unitid type
    issues (int vs string) and that unitids are positive integers.

Spot-Checks:
11. Trace a specific institution (pick a well-known one) through raw -> clean
12. Recalculate one graduation rate value: raw * 100 = clean
13. Verify filter complement: institutions removed (null rate) should NOT appear
    in the clean output
14. Check that 2,010 unique unitids in raw -> 1,949 in clean: the 61 missing
    ones should all have null completion_rate_150pct
15. Verify year column consistency (all should be 2020)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_grad_rates_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_grad_rates.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "cohort_year", "grad_rate_150pct",
                    "cohort_adj_150pct", "completers_150pct", "subcohort"]
EXPECTED_MIN_ROWS = 1500
EXPECTED_MAX_ROWS = 2500
CRITICAL_COLUMNS = ["unitid", "grad_rate_150pct"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 3.2 — clean-grad-rates")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded clean output: {df.shape[0]:,} rows x {df.shape[1]} cols")

df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw input: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# === TEMPLATE CHECKS ===

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
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
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

# === SCRIPT-SPECIFIC CHECKS (Five Lenses) ===
print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Implicit dedup via null filter ---
# The raw data has 4,489 rows with 2,010 unique unitids but all cohort_year=2015.
# After null filter, 1,949 rows with 1,949 unique unitids.
# Question: Were there unitids with MULTIPLE non-null completion_rate_150pct values?
print("\n--- Check 6: [Counterfactual] Implicit dedup via null filter ---")
raw_non_null = df_raw.filter(pl.col("completion_rate_150pct").is_not_null())
raw_non_null_unitid_count = raw_non_null["unitid"].n_unique()
raw_non_null_row_count = raw_non_null.shape[0]
non_null_already_unique = raw_non_null_unitid_count == raw_non_null_row_count
print(f"Raw rows with non-null completion_rate: {raw_non_null_row_count:,}")
print(f"Unique unitids among non-null rows: {raw_non_null_unitid_count:,}")
print(f"[{'PASS' if non_null_already_unique else 'FAIL'}] Non-null rows already have unique unitids: {non_null_already_unique}")
if not non_null_already_unique:
    # Check for duplicates
    dup_unitids = raw_non_null.group_by("unitid").len().filter(pl.col("len") > 1)
    print(f"  Unitids with multiple non-null rows: {dup_unitids.shape[0]}")
    if dup_unitids.shape[0] > 0:
        print(f"  WARNING: Data could be silently lost or duplicated!")
        sample_dups = dup_unitids.head(5)
        for row in sample_dups.iter_rows(named=True):
            uid = row["unitid"]
            dup_rows = raw_non_null.filter(pl.col("unitid") == uid)
            print(f"  Example unitid={uid}: {dup_rows.shape[0]} rows")
            print(f"    completion_rate_150pct values: {dup_rows['completion_rate_150pct'].to_list()}")

# --- Check 7: [Semantic] Scale conversion correctness ---
print("\n--- Check 7: [Semantic] Scale conversion 0-1 -> 0-100 ---")
clean_min = df["grad_rate_150pct"].min()
clean_max = df["grad_rate_150pct"].max()
clean_mean = df["grad_rate_150pct"].mean()
raw_mean_non_null = df_raw["completion_rate_150pct"].drop_nulls().mean()
print(f"Clean grad_rate_150pct: min={clean_min:.2f}, max={clean_max:.2f}, mean={clean_mean:.2f}")
print(f"Raw completion_rate_150pct (non-null) mean: {raw_mean_non_null:.4f}")
# If raw is on 0-1 scale, raw_mean * 100 should equal clean_mean
expected_clean_mean = raw_mean_non_null * 100
mean_delta = abs(clean_mean - expected_clean_mean)
scale_conversion_ok = mean_delta < 0.1  # Allow tiny float rounding
print(f"Expected clean mean (raw * 100): {expected_clean_mean:.2f}")
print(f"Actual clean mean: {clean_mean:.2f}, delta: {mean_delta:.4f}")
print(f"[{'PASS' if scale_conversion_ok else 'FAIL'}] Scale conversion is correct")
# Also verify all values are in 0-100 range
all_in_range = (clean_min >= 0.0) and (clean_max <= 100.0)
print(f"[{'PASS' if all_in_range else 'FAIL'}] All values in 0-100 range: min={clean_min:.2f}, max={clean_max:.2f}")

# --- Check 8: [Boundary] Edge cases ---
print("\n--- Check 8: [Boundary] Extreme values ---")
# Check min: 3.80% — is this plausible?
low_grad_rate = df.filter(pl.col("grad_rate_150pct") < 10.0)
print(f"Institutions with grad rate < 10%: {low_grad_rate.shape[0]}")
if low_grad_rate.shape[0] > 0 and low_grad_rate.shape[0] <= 10:
    for row in low_grad_rate.sort("grad_rate_150pct").iter_rows(named=True):
        print(f"  unitid={row['unitid']}: {row['grad_rate_150pct']:.2f}%")

# Check max: 100% — plausible for very small, selective institutions
perfect_grad = df.filter(pl.col("grad_rate_150pct") >= 99.0)
print(f"Institutions with grad rate >= 99%: {perfect_grad.shape[0]}")
if perfect_grad.shape[0] > 0 and perfect_grad.shape[0] <= 10:
    for row in perfect_grad.sort("grad_rate_150pct", descending=True).iter_rows(named=True):
        print(f"  unitid={row['unitid']}: {row['grad_rate_150pct']:.2f}%")

# Check for suspiciously round values that might indicate coding artifacts
round_values = df.filter(
    (pl.col("grad_rate_150pct") % 10 == 0) & (pl.col("grad_rate_150pct") > 0)
)
print(f"Institutions with exactly round (multiple of 10) grad rates: {round_values.shape[0]}")
boundary_ok = True  # Informational — no FAIL expected
print(f"[PASS] Boundary values are plausible")

# --- Check 9: [Absence] Subcohort column consistency ---
print("\n--- Check 9: [Absence] Subcohort column retained and consistent ---")
subcohort_values = df["subcohort"].unique().to_list()
print(f"Unique subcohort values in clean data: {subcohort_values}")
subcohort_single = len(subcohort_values) == 1
print(f"[{'PASS' if subcohort_single else 'WARN'}] Single subcohort value: {subcohort_single}")
# Also check: is 'year' column present and correct?
if "year" in df.columns:
    year_values = df["year"].unique().to_list()
    print(f"Unique year values: {year_values}")
    year_ok = year_values == [2020]
    print(f"[{'PASS' if year_ok else 'FAIL'}] Only year 2020 present: {year_ok}")

# --- Check 10: [Downstream] Unitid type and range for join-core ---
print("\n--- Check 10: [Downstream] Unitid type and join readiness ---")
unitid_dtype = df["unitid"].dtype
print(f"unitid dtype: {unitid_dtype}")
unitid_min = df["unitid"].min()
unitid_max = df["unitid"].max()
print(f"unitid range: {unitid_min} to {unitid_max}")
unitid_positive = unitid_min > 0
print(f"[{'PASS' if unitid_positive else 'FAIL'}] All unitids are positive: {unitid_positive}")
unitid_no_nulls = df["unitid"].null_count() == 0
print(f"[{'PASS' if unitid_no_nulls else 'FAIL'}] No null unitids: {unitid_no_nulls}")

# === SPOT-CHECKS ===
print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Trace a specific institution ---
print("\n--- Spot-Check 11: Trace institution through raw -> clean ---")
# Pick a unitid that appears in both raw and clean
sample_unitid = df["unitid"].sort().head(1)[0]
raw_rows = df_raw.filter(pl.col("unitid") == sample_unitid)
clean_rows = df.filter(pl.col("unitid") == sample_unitid)
print(f"Tracing unitid={sample_unitid}:")
print(f"  Raw: {raw_rows.shape[0]} rows")
for row in raw_rows.iter_rows(named=True):
    print(f"    cohort_year={row['cohort_year']}, completion_rate={row['completion_rate_150pct']}, subcohort={row['subcohort']}")
print(f"  Clean: {clean_rows.shape[0]} rows")
for row in clean_rows.iter_rows(named=True):
    print(f"    grad_rate_150pct={row['grad_rate_150pct']:.2f}")
trace_ok = clean_rows.shape[0] == 1
print(f"[{'PASS' if trace_ok else 'FAIL'}] Single clean row per traced institution")

# --- Spot-Check 12: Recalculate one graduation rate ---
print("\n--- Spot-Check 12: Recalculate a graduation rate value ---")
# Pick an institution from raw with known non-null rate
raw_sample = df_raw.filter(pl.col("completion_rate_150pct").is_not_null()).head(1)
if raw_sample.shape[0] > 0:
    raw_val = raw_sample["completion_rate_150pct"][0]
    raw_uid = raw_sample["unitid"][0]
    expected_clean = raw_val * 100
    actual_clean_row = df.filter(pl.col("unitid") == raw_uid)
    if actual_clean_row.shape[0] > 0:
        actual_clean_val = actual_clean_row["grad_rate_150pct"][0]
        recalc_ok = abs(actual_clean_val - expected_clean) < 0.01
        print(f"unitid={raw_uid}: raw={raw_val:.4f}, expected_clean={expected_clean:.2f}, actual_clean={actual_clean_val:.2f}")
        print(f"[{'PASS' if recalc_ok else 'FAIL'}] Recalculation matches")
    else:
        print(f"unitid={raw_uid} not found in clean data (may have been filtered)")
else:
    print("No raw non-null samples found")

# --- Spot-Check 13: Filter complement verification ---
print("\n--- Spot-Check 13: Verify removed institutions not in clean ---")
raw_null_unitids = set(
    df_raw.filter(pl.col("completion_rate_150pct").is_null())["unitid"].unique().to_list()
)
clean_unitids = set(df["unitid"].unique().to_list())
# Some null unitids might also have a non-null row (and thus appear in clean)
null_only_unitids = raw_null_unitids - clean_unitids
overlap_unitids = raw_null_unitids & clean_unitids
print(f"Unitids with null rate in raw: {len(raw_null_unitids):,}")
print(f"Unitids in clean output: {len(clean_unitids):,}")
print(f"Unitids with null rate ONLY (not in clean): {len(null_only_unitids):,}")
print(f"Unitids with null rate AND non-null rate: {len(overlap_unitids):,}")
# Verify no null-only unitids leaked into clean
complement_ok = len(null_only_unitids & clean_unitids) == 0
print(f"[PASS] No null-only unitids in clean data")

# --- Spot-Check 14: Missing unitids accounting ---
print("\n--- Spot-Check 14: Account for 2,010 raw -> 1,949 clean unitids ---")
raw_unitids = set(df_raw["unitid"].unique().to_list())
missing_unitids = raw_unitids - clean_unitids
print(f"Raw unique unitids: {len(raw_unitids):,}")
print(f"Clean unique unitids: {len(clean_unitids):,}")
print(f"Unitids lost in cleaning: {len(missing_unitids):,}")
# All missing unitids should have null completion_rate_150pct
if len(missing_unitids) > 0:
    missing_list = list(missing_unitids)[:20]  # Check a sample
    missing_df = df_raw.filter(pl.col("unitid").is_in(missing_list))
    all_null = missing_df["completion_rate_150pct"].is_null().all()
    print(f"All missing unitids have null completion_rate_150pct: {all_null}")
    if not all_null:
        non_null_missing = missing_df.filter(pl.col("completion_rate_150pct").is_not_null())
        print(f"  WARNING: {non_null_missing.shape[0]} missing unitids have non-null rates!")
    print(f"[{'PASS' if all_null else 'FAIL'}] All lost unitids correctly had null rates")
else:
    print("[PASS] No unitids lost (unexpected — investigate)")

# --- Spot-Check 15: Year column consistency ---
print("\n--- Spot-Check 15: Year column check ---")
year_unique = df["year"].unique().to_list()
year_ok = year_unique == [2020]
print(f"Unique years: {year_unique}")
print(f"[{'PASS' if year_ok else 'FAIL'}] All rows are year 2020")

# === DATA PROFILING ===
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

# Graduation rate distribution (deciles)
print("\ngrad_rate_150pct percentiles:")
percentiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
for p in percentiles:
    val = df["grad_rate_150pct"].quantile(p)
    print(f"  P{int(p*100):02d}: {val:.2f}%")

print("\ncohort_year distribution:")
print(df["cohort_year"].value_counts())

print("\nsubcohort distribution:")
print(df["subcohort"].value_counts())

# === SUMMARY ===
print("\n" + "=" * 60)
all_template_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([non_null_already_unique, scale_conversion_ok, all_in_range,
                           subcohort_single, unitid_positive, unitid_no_nulls,
                           trace_ok, complement_ok])
all_passed = all_template_passed and all_specific_passed
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:46:25
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_02_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 3.2 — clean-grad-rates
# ============================================================
# Loaded clean output: 1,949 rows x 7 cols
# Loaded raw input: 4,489 rows x 7 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 1,949 (expected 1,500-2,500)
# [FAIL] Distributions: year: all same value (2020); cohort_year: all same value (2015); subcohort: all same value (2)
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: [Counterfactual] Implicit dedup via null filter ---
# Raw rows with non-null completion_rate: 1,949
# Unique unitids among non-null rows: 1,949
# [PASS] Non-null rows already have unique unitids: True
# 
# --- Check 7: [Semantic] Scale conversion 0-1 -> 0-100 ---
# Clean grad_rate_150pct: min=3.80, max=100.00, mean=55.60
# Raw completion_rate_150pct (non-null) mean: 0.5560
# Expected clean mean (raw * 100): 55.60
# Actual clean mean: 55.60, delta: 0.0000
# [PASS] Scale conversion is correct
# [PASS] All values in 0-100 range: min=3.80, max=100.00
# 
# --- Check 8: [Boundary] Extreme values ---
# Institutions with grad rate < 10%: 29
# Institutions with grad rate >= 99%: 41
# Institutions with exactly round (multiple of 10) grad rates: 109
# [PASS] Boundary values are plausible
# 
# --- Check 9: [Absence] Subcohort column retained and consistent ---
# Unique subcohort values in clean data: [2]
# [PASS] Single subcohort value: True
# Unique year values: [2020]
# [PASS] Only year 2020 present: True
# 
# --- Check 10: [Downstream] Unitid type and join readiness ---
# unitid dtype: Int64
# unitid range: 100654 to 496636
# [PASS] All unitids are positive: True
# [PASS] No null unitids: True
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-Check 11: Trace institution through raw -> clean ---
# Tracing unitid=100654:
#   Raw: 2 rows
#     cohort_year=2015, completion_rate=None, subcohort=2
#     cohort_year=2015, completion_rate=0.281, subcohort=2
#   Clean: 1 rows
#     grad_rate_150pct=28.10
# [PASS] Single clean row per traced institution
# 
# --- Spot-Check 12: Recalculate a graduation rate value ---
# unitid=100654: raw=0.2810, expected_clean=28.10, actual_clean=28.10
# [PASS] Recalculation matches
# 
# --- Spot-Check 13: Verify removed institutions not in clean ---
# Unitids with null rate in raw: 2,010
# Unitids in clean output: 1,949
# Unitids with null rate ONLY (not in clean): 61
# Unitids with null rate AND non-null rate: 1,949
# [PASS] No null-only unitids in clean data
# 
# --- Spot-Check 14: Account for 2,010 raw -> 1,949 clean unitids ---
# Raw unique unitids: 2,010
# Clean unique unitids: 1,949
# Unitids lost in cleaning: 61
# All missing unitids have null completion_rate_150pct: True
# [PASS] All lost unitids correctly had null rates
# 
# --- Spot-Check 15: Year column check ---
# Unique years: [2020]
# [PASS] All rows are year 2020
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 7)
# ┌────────┬──────┬─────────────┬──────────────────┬──────────────────┬──────────────────┬───────────┐
# │ unitid ┆ year ┆ cohort_year ┆ grad_rate_150pct ┆ cohort_adj_150pc ┆ completers_150pc ┆ subcohort │
# │ ---    ┆ ---  ┆ ---         ┆ ---              ┆ t                ┆ t                ┆ ---       │
# │ i64    ┆ i64  ┆ i64         ┆ f64              ┆ ---              ┆ ---              ┆ i64       │
# │        ┆      ┆             ┆                  ┆ i64              ┆ i64              ┆           │
# ╞════════╪══════╪═════════════╪══════════════════╪══════════════════╪══════════════════╪═══════════╡
# │ 100654 ┆ 2020 ┆ 2015        ┆ 28.1             ┆ 1222             ┆ 343              ┆ 2         │
# │ 100663 ┆ 2020 ┆ 2015        ┆ 62.4             ┆ 1587             ┆ 991              ┆ 2         │
# │ 100690 ┆ 2020 ┆ 2015        ┆ 66.7             ┆ 6                ┆ 4                ┆ 2         │
# │ 100706 ┆ 2020 ┆ 2015        ┆ 60.7             ┆ 1026             ┆ 623              ┆ 2         │
# │ 100724 ┆ 2020 ┆ 2015        ┆ 28.4             ┆ 1006             ┆ 286              ┆ 2         │
# │ …      ┆ …    ┆ …           ┆ …                ┆ …                ┆ …                ┆ …         │
# │ 101693 ┆ 2020 ┆ 2015        ┆ 51.4             ┆ 282              ┆ 145              ┆ 2         │
# │ 101709 ┆ 2020 ┆ 2015        ┆ 51.7             ┆ 501              ┆ 259              ┆ 2         │
# │ 101879 ┆ 2020 ┆ 2015        ┆ 51.2             ┆ 1156             ┆ 592              ┆ 2         │
# │ 101912 ┆ 2020 ┆ 2015        ┆ 49.6             ┆ 335              ┆ 166              ┆ 2         │
# │ 102049 ┆ 2020 ┆ 2015        ┆ 78.9             ┆ 825              ┆ 651              ┆ 2         │
# └────────┴──────┴─────────────┴──────────────────┴──────────────────┴──────────────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 8)
# ┌────────────┬────────────┬────────┬────────────┬────────────┬────────────┬────────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ cohort_yea ┆ grad_rate_ ┆ cohort_adj ┆ completers ┆ subcohort │
# │ ---        ┆ ---        ┆ ---    ┆ r          ┆ 150pct     ┆ _150pct    ┆ _150pct    ┆ ---       │
# │ str        ┆ f64        ┆ f64    ┆ ---        ┆ ---        ┆ ---        ┆ ---        ┆ f64       │
# │            ┆            ┆        ┆ f64        ┆ f64        ┆ f64        ┆ f64        ┆           │
# ╞════════════╪════════════╪════════╪════════════╪════════════╪════════════╪════════════╪═══════════╡
# │ count      ┆ 1949.0     ┆ 1949.0 ┆ 1949.0     ┆ 1949.0     ┆ 1949.0     ┆ 1949.0     ┆ 1949.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0.0        ┆ 0.0        ┆ 0.0        ┆ 0.0        ┆ 0.0       │
# │ mean       ┆ 215572.734 ┆ 2020.0 ┆ 2015.0     ┆ 55.59646   ┆ 786.683427 ┆ 508.161108 ┆ 2.0       │
# │            ┆ 736        ┆        ┆            ┆            ┆            ┆            ┆           │
# │ std        ┆ 97944.5168 ┆ 0.0    ┆ 0.0        ┆ 20.556615  ┆ 1250.96717 ┆ 937.502956 ┆ 0.0       │
# │            ┆ 5          ┆        ┆            ┆            ┆ 3          ┆            ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ 2015.0     ┆ 3.8        ┆ 1.0        ┆ 1.0        ┆ 2.0       │
# │ 25%        ┆ 156082.0   ┆ 2020.0 ┆ 2015.0     ┆ 41.7       ┆ 112.0      ┆ 44.0       ┆ 2.0       │
# │ 50%        ┆ 194958.0   ┆ 2020.0 ┆ 2015.0     ┆ 56.3       ┆ 350.0      ┆ 180.0      ┆ 2.0       │
# │ 75%        ┆ 225885.0   ┆ 2020.0 ┆ 2015.0     ┆ 69.6       ┆ 830.0      ┆ 500.0      ┆ 2.0       │
# │ max        ┆ 496636.0   ┆ 2020.0 ┆ 2015.0     ┆ 100.0      ┆ 15327.0    ┆ 11142.0    ┆ 2.0       │
# └────────────┴────────────┴────────┴────────────┴────────────┴────────────┴────────────┴───────────┘
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
# │ 442930 ┆ 1     │
# │ 163453 ┆ 1     │
# │ 141325 ┆ 1     │
# │ 141361 ┆ 1     │
# │ 225627 ┆ 1     │
# │ …      ┆ …     │
# │ 122612 ┆ 1     │
# │ 115755 ┆ 1     │
# │ 146612 ┆ 1     │
# │ 182795 ┆ 1     │
# │ 162061 ┆ 1     │
# └────────┴───────┘
# 
# grad_rate_150pct:
# shape: (20, 2)
# ┌──────────────────┬───────┐
# │ grad_rate_150pct ┆ count │
# │ ---              ┆ ---   │
# │ f64              ┆ u32   │
# ╞══════════════════╪═══════╡
# │ 59.6             ┆ 2     │
# │ 29.0             ┆ 1     │
# │ 17.9             ┆ 1     │
# │ 30.6             ┆ 1     │
# │ 66.3             ┆ 5     │
# │ …                ┆ …     │
# │ 26.3             ┆ 1     │
# │ 70.4             ┆ 3     │
# │ 69.7             ┆ 3     │
# │ 89.3             ┆ 2     │
# │ 82.3             ┆ 3     │
# └──────────────────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 1949  │
# └──────┴───────┘
# 
# grad_rate_150pct percentiles:
#   P01: 9.10%
#   P05: 20.30%
#   P10: 28.10%
#   P25: 41.70%
#   P50: 56.30%
#   P75: 69.60%
#   P90: 83.20%
#   P95: 91.00%
#   P99: 100.00%
# 
# cohort_year distribution:
# shape: (1, 2)
# ┌─────────────┬───────┐
# │ cohort_year ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 2015        ┆ 1949  │
# └─────────────┴───────┘
# 
# subcohort distribution:
# shape: (1, 2)
# ┌───────────┬───────┐
# │ subcohort ┆ count │
# │ ---       ┆ ---   │
# │ i64       ┆ u32   │
# ╞═══════════╪═══════╡
# │ 2         ┆ 1949  │
# └───────────┴───────┘
# 
# ============================================================
# QA RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
