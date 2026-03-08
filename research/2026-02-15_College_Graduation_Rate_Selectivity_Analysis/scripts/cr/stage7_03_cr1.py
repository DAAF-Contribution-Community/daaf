#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 6.1 — join-resources

Reviewed script: scripts/stage7_transform/03_join-resources.py
Output files: data/processed/2026-02-15_pre_analysis.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical join-key columns

Script-Specific Checks (Five Lenses):
6. Counterfactual: Would the join produce different results with duplicate keys?
7. Semantic: Does the output actually serve the research question (resource proxies present and usable)?
8. Boundary: Check edge values for SFR (known outlier unitid 246035) and retention_rate range
9. Absence: Verify no duplicate year columns leaked from SFR/retention joins
10. Downstream: Verify the dataset is ready for create-bands (next step needs admission_rate, pell_share, urm_share)

Spot Checks:
11. Trace a specific institution end-to-end through the join
12. Verify null arithmetic: retention nulls = unmatched + pre-existing nulls in source
13. Verify SFR nulls = exactly unmatched count (SFR source should have no pre-existing nulls for matched)
14. Check that no rows were duplicated (unitid uniqueness in output)
15. Verify column count matches expectation (21 core + 2 new = 23)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_pre_analysis.parquet"
INPUT_CORE = PROJECT_DIR / "data" / "processed" / "2026-02-15_core_demographics.parquet"
INPUT_SFR = PROJECT_DIR / "data" / "processed" / "2026-02-15_sfr_clean.parquet"
INPUT_RETENTION = PROJECT_DIR / "data" / "processed" / "2026-02-15_retention_clean.parquet"

EXPECTED_ROWS = 2528
EXPECTED_COLS = 23  # 21 core + student_faculty_ratio + retention_rate

# Plan-specified required columns for the pre_analysis output
EXPECTED_COLUMNS = [
    "unitid", "inst_name", "grad_rate_150pct", "admission_rate",
    "pell_share", "urm_share", "student_faculty_ratio", "retention_rate",
    "inst_control", "hbcu", "enrollment_undergrad",
]
# Critical columns that must have zero nulls
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 6.1 — join-resources")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load inputs for cross-validation
df_core = pl.read_parquet(INPUT_CORE)
df_sfr = pl.read_parquet(INPUT_SFR)
df_retention = pl.read_parquet(INPUT_RETENTION)
print(f"Loaded core:      {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"Loaded SFR:       {df_sfr.shape[0]:,} rows x {df_sfr.shape[1]} cols")
print(f"Loaded retention: {df_retention.shape[0]:,} rows x {df_retention.shape[1]} cols")

qa_max_severity = "PASSED"

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All Plan-specified columns present")
else:
    print(f"Missing columns: {missing_cols}")
    qa_max_severity = "BLOCKER"

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROWS:,})")
if not rows_ok:
    qa_max_severity = "BLOCKER"

# --- Check 3: Distributions (numeric columns) ---
print("\n--- Distribution Check ---")
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
if not dist_ok:
    qa_max_severity = "WARNING"

# --- Check 4: Coded values ---
print("\n--- Coded Values Check ---")
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
if not coded_ok:
    qa_max_severity = "BLOCKER"

# --- Check 5: Critical nulls ---
print("\n--- Critical Nulls Check ---")
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))
if not nulls_ok:
    qa_max_severity = "BLOCKER"

# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ============================================================

# --- Check 6: COUNTERFACTUAL — What if keys were NOT unique in SFR/retention? ---
print("\n--- Counterfactual: Key Uniqueness in Source ---")
sfr_unique = df_sfr["unitid"].n_unique() == len(df_sfr)
ret_unique = df_retention["unitid"].n_unique() == len(df_retention)
print(f"[{'PASS' if sfr_unique else 'FAIL'}] SFR keys unique: {df_sfr['unitid'].n_unique()} unique out of {len(df_sfr)} rows")
print(f"[{'PASS' if ret_unique else 'FAIL'}] Retention keys unique: {df_retention['unitid'].n_unique()} unique out of {len(df_retention)} rows")
if not sfr_unique or not ret_unique:
    print("  BLOCKER: Non-unique keys would cause fan-out in LEFT join")
    qa_max_severity = "BLOCKER"

# --- Check 7: SEMANTIC — Are SFR and retention actually usable for the research question? ---
print("\n--- Semantic: Resource Proxies Usable for Research ---")
sfr_non_null = df["student_faculty_ratio"].drop_nulls()
ret_non_null = df["retention_rate"].drop_nulls()
sfr_coverage = len(sfr_non_null) / len(df) * 100
ret_coverage = len(ret_non_null) / len(df) * 100
print(f"  student_faculty_ratio coverage: {sfr_coverage:.1f}% ({len(sfr_non_null):,} / {len(df):,})")
print(f"  retention_rate coverage:        {ret_coverage:.1f}% ({len(ret_non_null):,} / {len(df):,})")
sfr_mean = sfr_non_null.mean()
sfr_min = sfr_non_null.min()
sfr_max = sfr_non_null.max()
ret_mean = ret_non_null.mean()
ret_min = ret_non_null.min()
ret_max = ret_non_null.max()
print(f"  SFR range: [{sfr_min}, {sfr_max}], mean={sfr_mean:.1f}")
print(f"  Retention range: [{ret_min}, {ret_max}], mean={ret_mean:.1f}")
# SFR should be positive; retention should be 0-100
sfr_range_ok = sfr_min > 0 and sfr_max < 200
ret_range_ok = ret_min >= 0 and ret_max <= 100
print(f"[{'PASS' if sfr_range_ok else 'FAIL'}] SFR range plausible (positive, <200)")
print(f"[{'PASS' if ret_range_ok else 'FAIL'}] Retention range plausible (0-100)")
if not sfr_range_ok or not ret_range_ok:
    qa_max_severity = "BLOCKER"

# Check retention null rate against tolerance (<35%)
ret_null_pct = df["retention_rate"].null_count() / len(df) * 100
print(f"[{'PASS' if ret_null_pct < 35 else 'WARN'}] Retention null rate {ret_null_pct:.1f}% < 35% tolerance")
if ret_null_pct >= 35:
    qa_max_severity = "WARNING"

# --- Check 8: BOUNDARY — SFR outlier (unitid 246035) and edge values ---
print("\n--- Boundary: SFR Outlier and Edge Values ---")
outlier_check = df.filter(pl.col("unitid") == 246035)
if len(outlier_check) > 0:
    outlier_sfr = outlier_check["student_faculty_ratio"][0]
    print(f"[PASS] Outlier unitid=246035 present in output, SFR={outlier_sfr}")
    if outlier_sfr == 110:
        print(f"  Confirmed: SFR=110 outlier preserved as expected per Risk Register")
else:
    print(f"[INFO] unitid=246035 not in output (may not be in 4-yr public/nonprofit universe)")

# Check boundary: max SFR value
top_sfr = df.select("unitid", "student_faculty_ratio").sort("student_faculty_ratio", descending=True).head(5)
print(f"\nTop 5 SFR values:")
for row in top_sfr.iter_rows(named=True):
    print(f"  unitid={row['unitid']}, SFR={row['student_faculty_ratio']}")

# --- Check 9: ABSENCE — No duplicate year columns leaked ---
print("\n--- Absence: No Duplicate Columns from Joins ---")
year_cols = [c for c in df.columns if "year" in c.lower()]
print(f"  Year-related columns: {year_cols}")
has_year_right = any("year_right" in c for c in df.columns)
has_multiple_year = len(year_cols) > 1
print(f"[{'PASS' if not has_year_right else 'FAIL'}] No 'year_right' columns")
print(f"[{'PASS' if not has_multiple_year else 'FAIL'}] Only one year column")
if has_year_right or has_multiple_year:
    print("  BLOCKER: Duplicate year columns indicate join column leakage")
    qa_max_severity = "BLOCKER"

# Also check for any _right suffixed columns
right_cols = [c for c in df.columns if c.endswith("_right")]
print(f"[{'PASS' if len(right_cols) == 0 else 'FAIL'}] No '_right' suffix columns: {right_cols if right_cols else 'none'}")
if right_cols:
    qa_max_severity = "BLOCKER"

# --- Check 10: DOWNSTREAM — Ready for create-bands? ---
print("\n--- Downstream: Ready for create-bands (Step 6.2)? ---")
# create-bands needs: admission_rate, pell_share, urm_share for banding
downstream_cols = ["admission_rate", "pell_share", "urm_share", "grad_rate_150pct"]
for col in downstream_cols:
    if col in df.columns:
        non_null = df[col].drop_nulls()
        print(f"  {col}: {len(non_null):,} non-null ({len(non_null)/len(df)*100:.1f}%)")
    else:
        print(f"  {col}: MISSING!")
        qa_max_severity = "BLOCKER"

# ============================================================
# SPOT CHECKS
# ============================================================

# --- Spot Check 11: Trace a specific institution ---
print("\n--- Spot Check: Trace University of Michigan (unitid ~170976) ---")
trace_id = 170976  # University of Michigan Ann Arbor
core_row = df_core.filter(pl.col("unitid") == trace_id)
sfr_row = df_sfr.filter(pl.col("unitid") == trace_id)
ret_row = df_retention.filter(pl.col("unitid") == trace_id)
output_row = df.filter(pl.col("unitid") == trace_id)

if len(core_row) > 0:
    print(f"  Core:      Found, grad_rate={core_row['grad_rate_150pct'][0]}, pell_share={core_row['pell_share'][0]}")
if len(sfr_row) > 0:
    print(f"  SFR src:   Found, SFR={sfr_row['student_faculty_ratio'][0]}")
if len(ret_row) > 0:
    print(f"  Ret src:   Found, retention={ret_row['retention_rate'][0]}")
if len(output_row) > 0:
    out_sfr = output_row["student_faculty_ratio"][0]
    out_ret = output_row["retention_rate"][0]
    print(f"  Output:    Found, SFR={out_sfr}, retention={out_ret}")
    # Cross-validate
    if len(sfr_row) > 0:
        match_sfr = out_sfr == sfr_row["student_faculty_ratio"][0]
        print(f"  [{'PASS' if match_sfr else 'FAIL'}] SFR matches source")
        if not match_sfr:
            qa_max_severity = "BLOCKER"
    if len(ret_row) > 0:
        match_ret = out_ret == ret_row["retention_rate"][0]
        print(f"  [{'PASS' if match_ret else 'FAIL'}] Retention matches source")
        if not match_ret:
            qa_max_severity = "BLOCKER"
else:
    print(f"  unitid {trace_id} not in output — trying alternative")
    # Try first institution in core
    alt_id = df_core["unitid"][0]
    print(f"  Using unitid={alt_id} instead")
    core_row = df_core.filter(pl.col("unitid") == alt_id)
    output_row = df.filter(pl.col("unitid") == alt_id)
    if len(output_row) > 0:
        print(f"  [PASS] Institution found in output")

# --- Spot Check 12: Null arithmetic for retention ---
print("\n--- Spot Check: Retention Null Arithmetic ---")
core_keys = set(df_core["unitid"].to_list())
ret_keys = set(df_retention["unitid"].to_list())
unmatched_count = len(core_keys - ret_keys)
# Count pre-existing nulls in retention source for matched keys
matched_keys = core_keys & ret_keys
matched_ret = df_retention.filter(pl.col("unitid").is_in(list(matched_keys)))
pre_existing_nulls = matched_ret["retention_rate"].null_count()
expected_total_nulls = unmatched_count + pre_existing_nulls
actual_nulls = df["retention_rate"].null_count()
null_math_ok = expected_total_nulls == actual_nulls
print(f"  Unmatched institutions:   {unmatched_count}")
print(f"  Pre-existing source nulls: {pre_existing_nulls}")
print(f"  Expected total nulls:     {expected_total_nulls}")
print(f"  Actual output nulls:      {actual_nulls}")
print(f"[{'PASS' if null_math_ok else 'FAIL'}] Null arithmetic: {expected_total_nulls} expected == {actual_nulls} actual")
if not null_math_ok:
    print(f"  Difference: {actual_nulls - expected_total_nulls}")
    qa_max_severity = "WARNING"

# --- Spot Check 13: SFR null arithmetic ---
print("\n--- Spot Check: SFR Null Arithmetic ---")
sfr_keys = set(df_sfr["unitid"].to_list())
sfr_unmatched = len(core_keys - sfr_keys)
matched_sfr_keys = core_keys & sfr_keys
matched_sfr = df_sfr.filter(pl.col("unitid").is_in(list(matched_sfr_keys)))
sfr_pre_nulls = matched_sfr["student_faculty_ratio"].null_count()
sfr_expected_nulls = sfr_unmatched + sfr_pre_nulls
sfr_actual_nulls = df["student_faculty_ratio"].null_count()
sfr_null_ok = sfr_expected_nulls == sfr_actual_nulls
print(f"  Unmatched institutions:   {sfr_unmatched}")
print(f"  Pre-existing source nulls: {sfr_pre_nulls}")
print(f"  Expected total nulls:     {sfr_expected_nulls}")
print(f"  Actual output nulls:      {sfr_actual_nulls}")
print(f"[{'PASS' if sfr_null_ok else 'FAIL'}] SFR null arithmetic: {sfr_expected_nulls} expected == {sfr_actual_nulls} actual")
if not sfr_null_ok:
    qa_max_severity = "WARNING"

# --- Spot Check 14: unitid uniqueness in output (no duplication) ---
print("\n--- Spot Check: Output unitid Uniqueness ---")
output_unique = df["unitid"].n_unique() == len(df)
print(f"[{'PASS' if output_unique else 'FAIL'}] unitid unique: {df['unitid'].n_unique()} unique out of {len(df)} rows")
if not output_unique:
    qa_max_severity = "BLOCKER"

# --- Spot Check 15: Column count ---
print("\n--- Spot Check: Column Count ---")
col_count_ok = df.shape[1] == EXPECTED_COLS
print(f"[{'PASS' if col_count_ok else 'WARN'}] Column count: {df.shape[1]} (expected {EXPECTED_COLS})")
print(f"  Columns: {df.columns}")
if not col_count_ok:
    print(f"  Note: {df.shape[1]} - {EXPECTED_COLS} = {df.shape[1] - EXPECTED_COLS} extra columns")

# ============================================================
# DATA PROFILING (for cr2+ decision)
# ============================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nNull rates per column:")
for col in df.columns:
    nc = df[col].null_count()
    print(f"  {col:<30s} nulls: {nc:>5,} ({nc/len(df)*100:>5.1f}%)")

print(f"\nstudent_faculty_ratio value counts (top 20):")
print(df["student_faculty_ratio"].value_counts().sort("count", descending=True).head(20))

print(f"\nretention_rate sample values (top 20 by frequency):")
print(df["retention_rate"].value_counts().sort("count", descending=True).head(20))

# --- Summary ---
print("\n" + "=" * 60)
print(f"QA3 RESULT: {qa_max_severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:32:54
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_03_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 6.1 — join-resources
# ============================================================
# Loaded output: 2,528 rows x 23 cols
# Loaded core:      2,528 rows x 21 cols
# Loaded SFR:       5,836 rows x 3 cols
# Loaded retention: 5,836 rows x 3 cols
# 
# [PASS] Schema: All Plan-specified columns present
# [PASS] Row count: 2,528 (expected exactly 2,528)
# 
# --- Distribution Check ---
# [FAIL] Distributions: year: all same value (2020); institution_level: all same value (4); cohort_year: all same value (2015)
# 
# --- Coded Values Check ---
# [PASS] Coded values: None remain
# 
# --- Critical Nulls Check ---
# [PASS] Critical nulls: None
# 
# --- Counterfactual: Key Uniqueness in Source ---
# [PASS] SFR keys unique: 5836 unique out of 5836 rows
# [PASS] Retention keys unique: 5836 unique out of 5836 rows
# 
# --- Semantic: Resource Proxies Usable for Research ---
#   student_faculty_ratio coverage: 85.4% (2,158 / 2,528)
#   retention_rate coverage:        74.2% (1,875 / 2,528)
#   SFR range: [1, 60], mean=13.7
#   Retention range: [0.0, 100.0], mean=74.2
# [PASS] SFR range plausible (positive, <200)
# [PASS] Retention range plausible (0-100)
# [PASS] Retention null rate 25.8% < 35% tolerance
# 
# --- Boundary: SFR Outlier and Edge Values ---
# [INFO] unitid=246035 not in output (may not be in 4-yr public/nonprofit universe)
# 
# Top 5 SFR values:
#   unitid=100733, SFR=None
#   unitid=102058, SFR=None
#   unitid=103529, SFR=None
#   unitid=104188, SFR=None
#   unitid=104665, SFR=None
# 
# --- Absence: No Duplicate Columns from Joins ---
#   Year-related columns: ['year', 'cohort_year']
# [PASS] No 'year_right' columns
# [FAIL] Only one year column
#   BLOCKER: Duplicate year columns indicate join column leakage
# [PASS] No '_right' suffix columns: none
# 
# --- Downstream: Ready for create-bands (Step 6.2)? ---
#   admission_rate: 1,659 non-null (65.6%)
#   pell_share: 2,010 non-null (79.5%)
#   urm_share: 2,158 non-null (85.4%)
#   grad_rate_150pct: 1,796 non-null (71.0%)
# 
# --- Spot Check: Trace University of Michigan (unitid ~170976) ---
#   Core:      Found, grad_rate=93.7, pell_share=0.19534616489514509
#   SFR src:   Found, SFR=11
#   Ret src:   Found, retention=96.0
#   Output:    Found, SFR=11, retention=96.0
#   [PASS] SFR matches source
#   [PASS] Retention matches source
# 
# --- Spot Check: Retention Null Arithmetic ---
#   Unmatched institutions:   370
#   Pre-existing source nulls: 283
#   Expected total nulls:     653
#   Actual output nulls:      653
# [PASS] Null arithmetic: 653 expected == 653 actual
# 
# --- Spot Check: SFR Null Arithmetic ---
#   Unmatched institutions:   370
#   Pre-existing source nulls: 0
#   Expected total nulls:     370
#   Actual output nulls:      370
# [PASS] SFR null arithmetic: 370 expected == 370 actual
# 
# --- Spot Check: Output unitid Uniqueness ---
# [PASS] unitid unique: 2528 unique out of 2528 rows
# 
# --- Spot Check: Column Count ---
# [PASS] Column count: 23 (expected 23)
#   Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment', 'student_faculty_ratio', 'retention_rate']
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 23)
# ┌────────┬──────┬─────────────┬─────────────┬───┬───────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ year ┆ inst_name   ┆ inst_contro ┆ … ┆ urm_share ┆ urm_enroll ┆ student_fa ┆ retention_ │
# │ ---    ┆ ---  ┆ ---         ┆ l           ┆   ┆ ---       ┆ ment       ┆ culty_rati ┆ rate       │
# │ i64    ┆ i64  ┆ str         ┆ ---         ┆   ┆ f64       ┆ ---        ┆ o          ┆ ---        │
# │        ┆      ┆             ┆ i64         ┆   ┆           ┆ i64        ┆ ---        ┆ f64        │
# │        ┆      ┆             ┆             ┆   ┆           ┆            ┆ i64        ┆            │
# ╞════════╪══════╪═════════════╪═════════════╪═══╪═══════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ 2020 ┆ Alabama A & ┆ 1           ┆ … ┆ 0.916552  ┆ 4668       ┆ 18         ┆ 54.0       │
# │        ┆      ┆ M           ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100663 ┆ 2020 ┆ University  ┆ 1           ┆ … ┆ 0.301845  ┆ 4189       ┆ 20         ┆ 86.0       │
# │        ┆      ┆ of Alabama  ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ at Birmi…   ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100690 ┆ 2020 ┆ Amridge     ┆ 2           ┆ … ┆ 0.718121  ┆ 214        ┆ 13         ┆ 50.0       │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100706 ┆ 2020 ┆ University  ┆ 1           ┆ … ┆ 0.159836  ┆ 1283       ┆ 19         ┆ 82.0       │
# │        ┆      ┆ of Alabama  ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ in Hunts…   ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100724 ┆ 2020 ┆ Alabama     ┆ 1           ┆ … ┆ 0.941063  ┆ 3401       ┆ 15         ┆ 62.0       │
# │        ┆      ┆ State       ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100733 ┆ 2020 ┆ University  ┆ 1           ┆ … ┆ null      ┆ null       ┆ null       ┆ null       │
# │        ┆      ┆ of Alabama  ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ System O…   ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100751 ┆ 2020 ┆ The         ┆ 1           ┆ … ┆ 0.158952  ┆ 5034       ┆ 20         ┆ 87.0       │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ of Alabama  ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100812 ┆ 2020 ┆ Athens      ┆ 1           ┆ … ┆ 0.18006   ┆ 484        ┆ 15         ┆ null       │
# │        ┆      ┆ State       ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100830 ┆ 2020 ┆ Auburn      ┆ 1           ┆ … ┆ 0.462629  ┆ 2024       ┆ 16         ┆ 70.0       │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ at          ┆             ┆   ┆           ┆            ┆            ┆            │
# │        ┆      ┆ Montgomer…  ┆             ┆   ┆           ┆            ┆            ┆            │
# │ 100858 ┆ 2020 ┆ Auburn      ┆ 1           ┆ … ┆ 0.084636  ┆ 2074       ┆ 20         ┆ 92.0       │
# │        ┆      ┆ University  ┆             ┆   ┆           ┆            ┆            ┆            │
# └────────┴──────┴─────────────┴─────────────┴───┴───────────┴────────────┴────────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 24)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ inst_name ┆ … ┆ urm_share ┆ urm_enrol ┆ student_f ┆ retention │
# │ ---        ┆ ---        ┆ ---    ┆ ---       ┆   ┆ ---       ┆ lment     ┆ aculty_ra ┆ _rate     │
# │ str        ┆ f64        ┆ f64    ┆ str       ┆   ┆ f64       ┆ ---       ┆ tio       ┆ ---       │
# │            ┆            ┆        ┆           ┆   ┆           ┆ f64       ┆ ---       ┆ f64       │
# │            ┆            ┆        ┆           ┆   ┆           ┆           ┆ f64       ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 2528.0     ┆ 2528.0 ┆ 2528      ┆ … ┆ 2158.0    ┆ 2158.0    ┆ 2158.0    ┆ 1875.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0         ┆ … ┆ 370.0     ┆ 370.0     ┆ 370.0     ┆ 653.0     │
# │ mean       ┆ 220569.164 ┆ 2020.0 ┆ null      ┆ … ┆ 0.293667  ┆ 1471.0588 ┆ 13.688601 ┆ 74.213333 │
# │            ┆ 161        ┆        ┆           ┆   ┆           ┆ 51        ┆           ┆           │
# │ std        ┆ 103707.401 ┆ 0.0    ┆ null      ┆ … ┆ 0.25124   ┆ 3373.5912 ┆ 5.367044  ┆ 14.751312 │
# │            ┆ 134        ┆        ┆           ┆   ┆           ┆ 06        ┆           ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ A T Still ┆ … ┆ 0.0       ┆ 0.0       ┆ 1.0       ┆ 0.0       │
# │            ┆            ┆        ┆ Universit ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ y of      ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ Health…   ┆   ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 155089.0   ┆ 2020.0 ┆ null      ┆ … ┆ 0.128294  ┆ 133.0     ┆ 10.0      ┆ 67.0      │
# │ 50%        ┆ 196121.0   ┆ 2020.0 ┆ null      ┆ … ┆ 0.208903  ┆ 375.0     ┆ 13.0      ┆ 76.0      │
# │ 75%        ┆ 230597.0   ┆ 2020.0 ┆ null      ┆ … ┆ 0.375284  ┆ 1311.0    ┆ 17.0      ┆ 84.0      │
# │ max        ┆ 496070.0   ┆ 2020.0 ┆ Zaytuna   ┆ … ┆ 1.0       ┆ 51922.0   ┆ 60.0      ┆ 100.0     │
# │            ┆            ┆        ┆ College   ┆   ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Null rates per column:
#   unitid                         nulls:     0 (  0.0%)
#   year                           nulls:     0 (  0.0%)
#   inst_name                      nulls:     0 (  0.0%)
#   inst_control                   nulls:     0 (  0.0%)
#   institution_level              nulls:     0 (  0.0%)
#   hbcu                           nulls:     0 (  0.0%)
#   degree_granting                nulls:     0 (  0.0%)
#   urban_centric_locale           nulls:     2 (  0.1%)
#   state_abbr                     nulls:     0 (  0.0%)
#   fips                           nulls:     0 (  0.0%)
#   grad_rate_150pct               nulls:   732 ( 29.0%)
#   cohort_year                    nulls:   732 ( 29.0%)
#   number_applied                 nulls:   859 ( 34.0%)
#   number_admitted                nulls:   869 ( 34.4%)
#   number_enrolled_total          nulls:   870 ( 34.4%)
#   admission_rate                 nulls:   869 ( 34.4%)
#   pell_recipients                nulls:   496 ( 19.6%)
#   enrollment_undergrad           nulls:   370 ( 14.6%)
#   pell_share                     nulls:   518 ( 20.5%)
#   urm_share                      nulls:   370 ( 14.6%)
#   urm_enrollment                 nulls:   370 ( 14.6%)
#   student_faculty_ratio          nulls:   370 ( 14.6%)
#   retention_rate                 nulls:   653 ( 25.8%)
# 
# student_faculty_ratio value counts (top 20):
# shape: (20, 2)
# ┌───────────────────────┬───────┐
# │ student_faculty_ratio ┆ count │
# │ ---                   ┆ ---   │
# │ i64                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ null                  ┆ 370   │
# │ 12                    ┆ 201   │
# │ 14                    ┆ 182   │
# │ 11                    ┆ 176   │
# │ 13                    ┆ 175   │
# │ …                     ┆ …     │
# │ 7                     ┆ 60    │
# │ 21                    ┆ 43    │
# │ 5                     ┆ 37    │
# │ 22                    ┆ 32    │
# │ 23                    ┆ 29    │
# └───────────────────────┴───────┘
# 
# retention_rate sample values (top 20 by frequency):
# shape: (20, 2)
# ┌────────────────┬───────┐
# │ retention_rate ┆ count │
# │ ---            ┆ ---   │
# │ f64            ┆ u32   │
# ╞════════════════╪═══════╡
# │ null           ┆ 653   │
# │ 75.0           ┆ 81    │
# │ 77.0           ┆ 70    │
# │ 79.0           ┆ 67    │
# │ 82.0           ┆ 61    │
# │ …              ┆ …     │
# │ 87.0           ┆ 51    │
# │ 85.0           ┆ 51    │
# │ 86.0           ┆ 49    │
# │ 84.0           ┆ 47    │
# │ 100.0          ┆ 47    │
# └────────────────┴───────┘
# 
# ============================================================
# QA3 RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
