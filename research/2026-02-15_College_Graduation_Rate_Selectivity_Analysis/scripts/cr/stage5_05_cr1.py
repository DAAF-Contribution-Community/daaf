#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 05
QA Checkpoint: QA1

Reviewed script: scripts/stage5_fetch/05_fetch-enrollment-race.py
Output files: data/raw/2026-02-15_ipeds_enrollment_race.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
DEFAULT:
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered (or expected for raw data)
5. No nulls in critical columns

SCRIPT-SPECIFIC (Five Skeptical Lenses):
6. [Counterfactual] What if degree_seeking/class_level create double-counting risk?
7. [Semantic] Does filtering to sex==99, level_of_study==1, ftpt==99 correctly isolate
   undergraduate total enrollment by race, per the research question?
8. [Boundary] Check for zero-enrollment institutions and extreme enrollment values
9. [Absence] Verify all 10 standard IPEDS race codes are present; check for missing institutions
10. [Downstream] Will Stage 6 be able to aggregate to institution-level URM shares without ambiguity?

SPOT-CHECKS:
11. Trace a specific institution (unitid 100654) through the data
12. Verify race code 99 (total) enrollment equals sum of individual race codes per institution
13. Check that no negative/coded values remain in enrollment_fall
14. Verify year column is exclusively 2020
15. Check uniqueness of (unitid, race, degree_seeking, class_level) combinations
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_enrollment_race.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "enrollment_fall", "race", "sex", "ftpt", "level_of_study"]
EXPECTED_MIN_ROWS = 20000
EXPECTED_MAX_ROWS = 400000
CRITICAL_COLUMNS = ["unitid", "enrollment_fall", "race"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 05 — Enrollment Race Fetch")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# =============================================================================
# DEFAULT CHECKS (1-5)
# =============================================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 — Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Check 2 — Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

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
print(f"[{'PASS' if dist_ok else 'FAIL'}] Check 3 — Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count:,} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Check 4 — Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count:,} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Check 5 — Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (6-10) — Five Skeptical Lenses
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Degree-seeking/class-level sub-category analysis ---
# The script filtered sex==99, level_of_study==1, ftpt==99 but degree_seeking
# and class_level columns were dropped. How many sub-rows per institution-race exist?
n_institutions = df["unitid"].n_unique()
n_race_codes = df["race"].n_unique()
expected_minimal_rows = n_institutions * n_race_codes
row_ratio = row_count / expected_minimal_rows if expected_minimal_rows > 0 else 0

print(f"\n[INFO] Check 6 — Counterfactual (sub-category granularity):")
print(f"  Unique institutions: {n_institutions:,}")
print(f"  Unique race codes: {n_race_codes}")
print(f"  Expected minimal rows (inst x race): {expected_minimal_rows:,}")
print(f"  Actual rows: {row_count:,}")
print(f"  Row ratio (actual/minimal): {row_ratio:.2f}")
print(f"  This means ~{row_ratio:.1f} sub-rows per institution-race combination")

# Check if rows per institution are consistent
rows_per_inst = df.group_by("unitid").len().rename({"len": "n_rows"})
rows_per_inst_stats = rows_per_inst["n_rows"].describe()
print(f"  Rows-per-institution distribution:")
min_rows_per_inst = rows_per_inst["n_rows"].min()
max_rows_per_inst = rows_per_inst["n_rows"].max()
mean_rows_per_inst = rows_per_inst["n_rows"].mean()
median_rows_per_inst = rows_per_inst["n_rows"].median()
print(f"    Min: {min_rows_per_inst}, Max: {max_rows_per_inst}, Mean: {mean_rows_per_inst:.1f}, Median: {median_rows_per_inst:.1f}")

# Check if sub-rows could cause double-counting when summed by race
# Group by unitid + race and count rows — multiple rows means sub-categories exist
dup_check = df.group_by(["unitid", "race"]).len().rename({"len": "n_rows"})
multi_row_count = dup_check.filter(pl.col("n_rows") > 1).shape[0]
all_unitid_race = dup_check.shape[0]
dup_pct = multi_row_count / all_unitid_race * 100 if all_unitid_race > 0 else 0
print(f"\n  Double-counting risk assessment:")
print(f"    (unitid, race) combinations with >1 row: {multi_row_count:,} / {all_unitid_race:,} ({dup_pct:.1f}%)")
if multi_row_count > 0:
    print(f"    [WARN] Multiple rows per (unitid, race) — Stage 6 MUST aggregate to avoid double-counting")
    sample_dup = dup_check.filter(pl.col("n_rows") > 1).head(5)
    print(f"    Sample (unitid, race) with multiple rows:\n{sample_dup}")
    # Show the actual rows for one example
    sample_uid = sample_dup["unitid"][0]
    sample_race = sample_dup["race"][0]
    sample_rows = df.filter((pl.col("unitid") == sample_uid) & (pl.col("race") == sample_race))
    print(f"    Example rows for unitid={sample_uid}, race={sample_race}:\n{sample_rows}")
else:
    print(f"    [PASS] No double-counting risk — each (unitid, race) pair is unique")

check6_ok = True  # Informational — not a BLOCKER since Stage 6 will handle this

# --- Check 7: [Semantic] Filter correctness for research question ---
# The research question needs total undergraduate enrollment by race per institution.
# Verify that sex==99, level_of_study==1, ftpt==99 are the correct filter values.
print(f"\n[INFO] Check 7 — Semantic (filter correctness for research question):")
sex_vals = sorted(df["sex"].unique().to_list())
level_vals = sorted(df["level_of_study"].unique().to_list())
ftpt_vals = sorted(df["ftpt"].unique().to_list())
print(f"  sex values in output: {sex_vals} (expected: [99] for total)")
print(f"  level_of_study values in output: {level_vals} (expected: [1] for undergraduate)")
print(f"  ftpt values in output: {ftpt_vals} (expected: [99] for total FT+PT)")
sex_correct = sex_vals == [99]
level_correct = level_vals == [1]
ftpt_correct = ftpt_vals == [99]
all_filters_correct = sex_correct and level_correct and ftpt_correct
print(f"  [{'PASS' if all_filters_correct else 'FAIL'}] All demographic filters applied correctly: "
      f"sex={'OK' if sex_correct else 'WRONG'}, level={'OK' if level_correct else 'WRONG'}, ftpt={'OK' if ftpt_correct else 'WRONG'}")

# --- Check 8: [Boundary] Zero-enrollment and extreme values ---
print(f"\n[INFO] Check 8 — Boundary (zero enrollment and extremes):")
zero_enroll = df.filter(pl.col("enrollment_fall") == 0).shape[0]
neg_enroll = df.filter(pl.col("enrollment_fall") < 0).shape[0]
zero_pct = zero_enroll / row_count * 100
print(f"  Zero enrollment rows: {zero_enroll:,} ({zero_pct:.1f}% of total)")
print(f"  Negative enrollment rows: {neg_enroll:,}")

# Enrollment distribution by percentiles
enroll_stats = df["enrollment_fall"].drop_nulls()
p = [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]
percentiles = [enroll_stats.quantile(q) for q in p]
print(f"  enrollment_fall percentiles:")
for q, v in zip(p, percentiles):
    print(f"    P{int(q*100):02d}: {v:,.0f}")

# Top 5 enrollment values
top5 = df.sort("enrollment_fall", descending=True).head(5).select(["unitid", "race", "enrollment_fall"])
print(f"  Top 5 enrollment_fall values:\n{top5}")

check8_ok = neg_enroll == 0
print(f"  [{'PASS' if check8_ok else 'FAIL'}] No negative enrollment values")

# --- Check 9: [Absence] Verify all expected race codes present ---
print(f"\n[INFO] Check 9 — Absence (race code completeness):")
# Standard IPEDS race codes: 1-9, 99
expected_race_codes = {1, 2, 3, 4, 5, 6, 7, 8, 9, 99}
actual_race_codes = set(df["race"].unique().to_list())
missing_race_codes = expected_race_codes - actual_race_codes
extra_race_codes = actual_race_codes - expected_race_codes
print(f"  Expected race codes: {sorted(expected_race_codes)}")
print(f"  Actual race codes: {sorted(actual_race_codes)}")
print(f"  Missing race codes: {sorted(missing_race_codes) if missing_race_codes else 'None'}")
print(f"  Extra race codes: {sorted(extra_race_codes) if extra_race_codes else 'None'}")
race_complete = len(missing_race_codes) == 0
print(f"  [{'PASS' if race_complete else 'WARN'}] Race code completeness")

# Check rows per race code — should be roughly equal
race_dist = df.group_by("race").len().sort("race")
print(f"  Race code distribution:\n{race_dist}")

# Check if any institution is missing a race code
inst_race_count = df.group_by("unitid").agg(pl.col("race").n_unique().alias("n_races"))
incomplete_insts = inst_race_count.filter(pl.col("n_races") < n_race_codes).shape[0]
print(f"  Institutions missing some race codes: {incomplete_insts:,} / {n_institutions:,}")

# --- Check 10: [Downstream] Stage 6 aggregation feasibility ---
print(f"\n[INFO] Check 10 — Downstream (Stage 6 aggregation feasibility):")
# Stage 6 needs to compute URM share: sum race-specific enrollment / total enrollment per institution
# This requires:
#   a) race==99 (total) row for each institution -> denominator
#   b) specific race codes (e.g., 2=Black, 3=Hispanic, etc.) -> numerator
# Check if every institution has a race==99 row
race99_insts = df.filter(pl.col("race") == 99)["unitid"].n_unique()
all_have_total = race99_insts == n_institutions
print(f"  Institutions with race==99 (total) row: {race99_insts:,} / {n_institutions:,}")
print(f"  [{'PASS' if all_have_total else 'WARN'}] All institutions have total enrollment row")

# Check if race-specific rows exist for URM calculation
# URM typically = race codes 2 (Black), 3 (Hispanic), 5 (Native American), 6 (Pacific Islander)
urm_codes = [2, 3, 5, 6]
for code in urm_codes:
    code_insts = df.filter(pl.col("race") == code)["unitid"].n_unique()
    print(f"  Institutions with race=={code}: {code_insts:,} / {n_institutions:,}")

# Check columns available for Stage 6 — degree_seeking and class_level were dropped
print(f"\n  Columns in output: {df.columns}")
print(f"  Note: degree_seeking and class_level were dropped during column selection")
print(f"  Stage 6 will need to handle sub-category aggregation using SUM on enrollment_fall")

# =============================================================================
# SPOT-CHECKS (11-15)
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Trace unitid 100654 ---
print(f"\nSpot-Check 11 — Trace unitid 100654:")
inst_data = df.filter(pl.col("unitid") == 100654)
print(f"  Rows for unitid 100654: {inst_data.shape[0]}")
print(f"  Race codes present: {sorted(inst_data['race'].unique().to_list())}")
print(f"  Full data:\n{inst_data}")
# Check if race 99 total matches sum of individual races
race99_enroll = inst_data.filter(pl.col("race") == 99)["enrollment_fall"].sum()
other_races_enroll = inst_data.filter(pl.col("race") != 99)["enrollment_fall"].sum()
print(f"  Race 99 (total) enrollment sum: {race99_enroll:,}")
print(f"  Sum of individual race codes enrollment: {other_races_enroll:,}")
if race99_enroll > 0:
    ratio = other_races_enroll / race99_enroll
    print(f"  Ratio (individual sum / total): {ratio:.4f}")
    if abs(ratio - 1.0) < 0.1:
        print(f"  [PASS] Individual race enrollments approximately sum to total")
    else:
        print(f"  [WARN] Individual race enrollments do NOT match total — ratio: {ratio:.4f}")

# --- Spot-Check 12: Race 99 total vs sum of individual race codes (sample of 20 institutions) ---
print(f"\nSpot-Check 12 — Race 99 total vs sum of individual codes (20 institutions):")
# For each sampled institution, sum enrollment_fall for race != 99, compare to race == 99
sample_uids = df["unitid"].unique().sort().head(20).to_list()
mismatch_count = 0
for uid in sample_uids:
    uid_data = df.filter(pl.col("unitid") == uid)
    total_row = uid_data.filter(pl.col("race") == 99)["enrollment_fall"].sum()
    indiv_sum = uid_data.filter(pl.col("race") != 99)["enrollment_fall"].sum()
    if total_row > 0 and abs(indiv_sum / total_row - 1.0) > 0.05:
        mismatch_count += 1
        print(f"  unitid {uid}: total={total_row:,}, individual sum={indiv_sum:,}, ratio={indiv_sum/total_row:.4f}")
if mismatch_count == 0:
    print(f"  [PASS] All 20 sampled institutions: individual race sums match race==99 total (within 5%)")
else:
    print(f"  [WARN] {mismatch_count} of 20 institutions have individual-race sums not matching total")

# --- Spot-Check 13: No negative or coded values in enrollment_fall ---
print(f"\nSpot-Check 13 — No negative/coded values in enrollment_fall:")
neg_values = df.filter(pl.col("enrollment_fall") < 0)
print(f"  Negative values: {neg_values.shape[0]}")
if neg_values.shape[0] > 0:
    neg_unique = sorted(neg_values["enrollment_fall"].unique().to_list())
    print(f"  [FAIL] Negative values found: {neg_unique}")
else:
    print(f"  [PASS] No negative values in enrollment_fall")

null_enroll = df["enrollment_fall"].null_count()
print(f"  Null enrollment_fall: {null_enroll:,}")
print(f"  [{'PASS' if null_enroll == 0 else 'WARN'}] enrollment_fall nulls: {null_enroll}")

# --- Spot-Check 14: Year column exclusively 2020 ---
print(f"\nSpot-Check 14 — Year column exclusively 2020:")
unique_years = sorted(df["year"].unique().to_list())
year_ok = unique_years == [2020]
print(f"  Unique years: {unique_years}")
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year is exclusively 2020")

# --- Spot-Check 15: Uniqueness of row identifiers (after dropping degree_seeking/class_level) ---
print(f"\nSpot-Check 15 — Row identifier uniqueness:")
# Since degree_seeking and class_level were dropped, check if (unitid, race) is unique
# If not, that confirms sub-category rows that Stage 6 must aggregate
dedup_check = df.group_by(["unitid", "race"]).len().rename({"len": "n_rows"})
unique_combos = dedup_check.shape[0]
multi_combos = dedup_check.filter(pl.col("n_rows") > 1).shape[0]
print(f"  Total (unitid, race) combinations: {unique_combos:,}")
print(f"  Combinations with >1 row: {multi_combos:,}")
print(f"  [INFO] {multi_combos:,} of {unique_combos:,} (unitid, race) combinations have multiple rows")
print(f"  This is expected — sub-categories (degree_seeking, class_level) create multiple rows")
print(f"  Stage 6 must SUM enrollment_fall by (unitid, race) to get institution-level totals")

# Show distribution of rows-per-combo
combo_dist = dedup_check["n_rows"].value_counts().sort("n_rows")
print(f"  Distribution of rows per (unitid, race) combination:\n{combo_dist}")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print("DEFAULT CHECK SUMMARY")
print("=" * 60)
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
print(f"  Schema: {'PASS' if schema_ok else 'FAIL'}")
print(f"  Row count: {'PASS' if rows_ok else 'FAIL'}")
print(f"  Distributions: {'PASS' if dist_ok else 'FAIL'}")
print(f"  Coded values: {'PASS' if coded_ok else 'WARN'}")
print(f"  Critical nulls: {'PASS' if nulls_ok else 'FAIL'}")
print(f"  Filters correct: {'PASS' if all_filters_correct else 'FAIL'}")
print(f"  No negatives: {'PASS' if check8_ok else 'FAIL'}")
print(f"  Year check: {'PASS' if year_ok else 'FAIL'}")

severity = "PASSED"
if not all([schema_ok, rows_ok, all_filters_correct, check8_ok, year_ok, nulls_ok]):
    severity = "BLOCKER"
elif not coded_ok or multi_row_count > 0:
    severity = "WARNING"

print(f"\n{'=' * 60}")
print(f"QA RESULT: {severity}")
if severity == "WARNING":
    print("  Note: WARNING is for multi-row (unitid, race) combinations requiring Stage 6 aggregation")
    print("  This is expected behavior per the orchestrator's context note, not an error")
print("=" * 60)

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================
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
        vc = df[col].value_counts().sort("count", descending=True).head(20)
        print(vc)

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\nDtype summary:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:33:52
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_05_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 05 — Enrollment Race Fetch
# ============================================================
# Loaded: 352,410 rows x 7 cols
# 
# [PASS] Check 1 — Schema: All expected columns present
# [PASS] Check 2 — Row count: 352,410 (expected 20,000-400,000)
# [FAIL] Check 3 — Distributions: year: all same value (2020); sex: all same value (99); ftpt: all same value (99); level_of_study: all same value (1)
# [PASS] Check 4 — Coded values: None remain
# [PASS] Check 5 — Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [INFO] Check 6 — Counterfactual (sub-category granularity):
#   Unique institutions: 5,837
#   Unique race codes: 10
#   Expected minimal rows (inst x race): 58,370
#   Actual rows: 352,410
#   Row ratio (actual/minimal): 6.04
#   This means ~6.0 sub-rows per institution-race combination
#   Rows-per-institution distribution:
#     Min: 20, Max: 70, Mean: 60.4, Median: 60.0
# 
#   Double-counting risk assessment:
#     (unitid, race) combinations with >1 row: 58,370 / 58,370 (100.0%)
#     [WARN] Multiple rows per (unitid, race) — Stage 6 MUST aggregate to avoid double-counting
#     Sample (unitid, race) with multiple rows:
# shape: (5, 3)
# ┌────────┬──────┬────────┐
# │ unitid ┆ race ┆ n_rows │
# │ ---    ┆ ---  ┆ ---    │
# │ i64    ┆ i64  ┆ u32    │
# ╞════════╪══════╪════════╡
# │ 106306 ┆ 6    ┆ 6      │
# │ 106397 ┆ 3    ┆ 7      │
# │ 106449 ┆ 8    ┆ 7      │
# │ 107877 ┆ 9    ┆ 7      │
# │ 109785 ┆ 2    ┆ 6      │
# └────────┴──────┴────────┘
#     Example rows for unitid=106306, race=6:
# shape: (6, 7)
# ┌────────┬──────┬─────────────────┬──────┬─────┬──────┬────────────────┐
# │ unitid ┆ year ┆ enrollment_fall ┆ race ┆ sex ┆ ftpt ┆ level_of_study │
# │ ---    ┆ ---  ┆ ---             ┆ ---  ┆ --- ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ i64             ┆ i64  ┆ i64 ┆ i64  ┆ i64            │
# ╞════════╪══════╪═════════════════╪══════╪═════╪══════╪════════════════╡
# │ 106306 ┆ 2020 ┆ 17              ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# │ 106306 ┆ 2020 ┆ 3               ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# │ 106306 ┆ 2020 ┆ 2               ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# │ 106306 ┆ 2020 ┆ 5               ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# │ 106306 ┆ 2020 ┆ 17              ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# │ 106306 ┆ 2020 ┆ 12              ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# └────────┴──────┴─────────────────┴──────┴─────┴──────┴────────────────┘
# 
# [INFO] Check 7 — Semantic (filter correctness for research question):
#   sex values in output: [99] (expected: [99] for total)
#   level_of_study values in output: [1] (expected: [1] for undergraduate)
#   ftpt values in output: [99] (expected: [99] for total FT+PT)
#   [PASS] All demographic filters applied correctly: sex=OK, level=OK, ftpt=OK
# 
# [INFO] Check 8 — Boundary (zero enrollment and extremes):
#   Zero enrollment rows: 95,864 (27.2% of total)
#   Negative enrollment rows: 0
#   enrollment_fall percentiles:
#     P01: 0
#     P05: 0
#     P25: 0
#     P50: 8
#     P75: 80
#     P95: 1,369
#     P99: 6,547
#   Top 5 enrollment_fall values:
# shape: (5, 3)
# ┌────────┬──────┬─────────────────┐
# │ unitid ┆ race ┆ enrollment_fall │
# │ ---    ┆ ---  ┆ ---             │
# │ i64    ┆ i64  ┆ i64             │
# ╞════════╪══════╪═════════════════╡
# │ 183026 ┆ 99   ┆ 111599          │
# │ 183026 ┆ 99   ┆ 109233          │
# │ 433387 ┆ 99   ┆ 104919          │
# │ 433387 ┆ 99   ┆ 104919          │
# │ 433387 ┆ 99   ┆ 104819          │
# └────────┴──────┴─────────────────┘
#   [PASS] No negative enrollment values
# 
# [INFO] Check 9 — Absence (race code completeness):
#   Expected race codes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#   Actual race codes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#   Missing race codes: None
#   Extra race codes: None
#   [PASS] Race code completeness
#   Race code distribution:
# shape: (10, 2)
# ┌──────┬───────┐
# │ race ┆ len   │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 35241 │
# │ 2    ┆ 35241 │
# │ 3    ┆ 35241 │
# │ 4    ┆ 35241 │
# │ 5    ┆ 35241 │
# │ 6    ┆ 35241 │
# │ 7    ┆ 35241 │
# │ 8    ┆ 35241 │
# │ 9    ┆ 35241 │
# │ 99   ┆ 35241 │
# └──────┴───────┘
#   Institutions missing some race codes: 0 / 5,837
# 
# [INFO] Check 10 — Downstream (Stage 6 aggregation feasibility):
#   Institutions with race==99 (total) row: 5,837 / 5,837
#   [PASS] All institutions have total enrollment row
#   Institutions with race==2: 5,837 / 5,837
#   Institutions with race==3: 5,837 / 5,837
#   Institutions with race==5: 5,837 / 5,837
#   Institutions with race==6: 5,837 / 5,837
# 
#   Columns in output: ['unitid', 'year', 'enrollment_fall', 'race', 'sex', 'ftpt', 'level_of_study']
#   Note: degree_seeking and class_level were dropped during column selection
#   Stage 6 will need to handle sub-category aggregation using SUM on enrollment_fall
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-Check 11 — Trace unitid 100654:
#   Rows for unitid 100654: 70
#   Race codes present: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#   Full data:
# shape: (70, 7)
# ┌────────┬──────┬─────────────────┬──────┬─────┬──────┬────────────────┐
# │ unitid ┆ year ┆ enrollment_fall ┆ race ┆ sex ┆ ftpt ┆ level_of_study │
# │ ---    ┆ ---  ┆ ---             ┆ ---  ┆ --- ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ i64             ┆ i64  ┆ i64 ┆ i64  ┆ i64            │
# ╞════════╪══════╪═════════════════╪══════╪═════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 1               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 6               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 1    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 31              ┆ 7    ┆ 99  ┆ 99   ┆ 1              │
# │ …      ┆ …    ┆ …               ┆ …    ┆ …   ┆ …    ┆ …              │
# │ 100654 ┆ 2020 ┆ 19              ┆ 1    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3               ┆ 2    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 5               ┆ 5    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 5               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 5093            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# └────────┴──────┴─────────────────┴──────┴─────┴──────┴────────────────┘
#   Race 99 (total) enrollment sum: 18,831
#   Sum of individual race codes enrollment: 18,831
#   Ratio (individual sum / total): 1.0000
#   [PASS] Individual race enrollments approximately sum to total
# 
# Spot-Check 12 — Race 99 total vs sum of individual codes (20 institutions):
#   [PASS] All 20 sampled institutions: individual race sums match race==99 total (within 5%)
# 
# Spot-Check 13 — No negative/coded values in enrollment_fall:
#   Negative values: 0
#   [PASS] No negative values in enrollment_fall
#   Null enrollment_fall: 0
#   [PASS] enrollment_fall nulls: 0
# 
# Spot-Check 14 — Year column exclusively 2020:
#   Unique years: [2020]
#   [PASS] Year is exclusively 2020
# 
# Spot-Check 15 — Row identifier uniqueness:
#   Total (unitid, race) combinations: 58,370
#   Combinations with >1 row: 58,370
#   [INFO] 58,370 of 58,370 (unitid, race) combinations have multiple rows
#   This is expected — sub-categories (degree_seeking, class_level) create multiple rows
#   Stage 6 must SUM enrollment_fall by (unitid, race) to get institution-level totals
#   Distribution of rows per (unitid, race) combination:
# shape: (6, 2)
# ┌────────┬───────┐
# │ n_rows ┆ count │
# │ ---    ┆ ---   │
# │ u32    ┆ u32   │
# ╞════════╪═══════╡
# │ 2      ┆ 30    │
# │ 3      ┆ 110   │
# │ 4      ┆ 1110  │
# │ 5      ┆ 21590 │
# │ 6      ┆ 9080  │
# │ 7      ┆ 26450 │
# └────────┴───────┘
# 
# ============================================================
# DEFAULT CHECK SUMMARY
# ============================================================
#   Schema: PASS
#   Row count: PASS
#   Distributions: FAIL
#   Coded values: PASS
#   Critical nulls: PASS
#   Filters correct: PASS
#   No negatives: PASS
#   Year check: PASS
# 
# ============================================================
# QA RESULT: WARNING
#   Note: WARNING is for multi-row (unitid, race) combinations requiring Stage 6 aggregation
#   This is expected behavior per the orchestrator's context note, not an error
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 7)
# ┌────────┬──────┬─────────────────┬──────┬─────┬──────┬────────────────┐
# │ unitid ┆ year ┆ enrollment_fall ┆ race ┆ sex ┆ ftpt ┆ level_of_study │
# │ ---    ┆ ---  ┆ ---             ┆ ---  ┆ --- ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ i64             ┆ i64  ┆ i64 ┆ i64  ┆ i64            │
# ╞════════╪══════╪═════════════════╪══════╪═════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 1               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 6               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 1    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 31              ┆ 7    ┆ 99  ┆ 99   ┆ 1              │
# │ …      ┆ …    ┆ …               ┆ …    ┆ …   ┆ …    ┆ …              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 6    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3381            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 41              ┆ 7    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3042            ┆ 2    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3               ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# └────────┴──────┴─────────────────┴──────┴─────┴──────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 8)
# ┌────────────┬─────────────┬──────────┬─────────────┬───────────┬──────────┬──────────┬────────────┐
# │ statistic  ┆ unitid      ┆ year     ┆ enrollment_ ┆ race      ┆ sex      ┆ ftpt     ┆ level_of_s │
# │ ---        ┆ ---         ┆ ---      ┆ fall        ┆ ---       ┆ ---      ┆ ---      ┆ tudy       │
# │ str        ┆ f64         ┆ f64      ┆ ---         ┆ f64       ┆ f64      ┆ f64      ┆ ---        │
# │            ┆             ┆          ┆ f64         ┆           ┆          ┆          ┆ f64        │
# ╞════════════╪═════════════╪══════════╪═════════════╪═══════════╪══════════╪══════════╪════════════╡
# │ count      ┆ 352410.0    ┆ 352410.0 ┆ 352410.0    ┆ 352410.0  ┆ 352410.0 ┆ 352410.0 ┆ 352410.0   │
# │ null_count ┆ 0.0         ┆ 0.0      ┆ 0.0         ┆ 0.0       ┆ 0.0      ┆ 0.0      ┆ 0.0        │
# │ mean       ┆ 272286.7706 ┆ 2020.0   ┆ 336.195761  ┆ 14.4      ┆ 99.0     ┆ 99.0     ┆ 1.0        │
# │            ┆ 93          ┆          ┆             ┆           ┆          ┆          ┆            │
# │ std        ┆ 134743.9737 ┆ 0.0      ┆ 1780.596838 ┆ 28.306223 ┆ 0.0      ┆ 0.0      ┆ 0.0        │
# │            ┆ 06          ┆          ┆             ┆           ┆          ┆          ┆            │
# │ min        ┆ 100654.0    ┆ 2020.0   ┆ 0.0         ┆ 1.0       ┆ 99.0     ┆ 99.0     ┆ 1.0        │
# │ 25%        ┆ 165820.0    ┆ 2020.0   ┆ 0.0         ┆ 3.0       ┆ 99.0     ┆ 99.0     ┆ 1.0        │
# │ 50%        ┆ 214582.0    ┆ 2020.0   ┆ 8.0         ┆ 6.0       ┆ 99.0     ┆ 99.0     ┆ 1.0        │
# │ 75%        ┆ 439367.0    ┆ 2020.0   ┆ 80.0        ┆ 8.0       ┆ 99.0     ┆ 99.0     ┆ 1.0        │
# │ max        ┆ 496423.0    ┆ 2020.0   ┆ 111599.0    ┆ 99.0      ┆ 99.0     ┆ 99.0     ┆ 1.0        │
# └────────────┴─────────────┴──────────┴─────────────┴───────────┴──────────┴──────────┴────────────┘
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
# │ 150668 ┆ 70    │
# │ 173300 ┆ 70    │
# │ 122791 ┆ 70    │
# │ 366395 ┆ 70    │
# │ 213774 ┆ 70    │
# │ …      ┆ …     │
# │ 171137 ┆ 70    │
# │ 217776 ┆ 70    │
# │ 202046 ┆ 70    │
# │ 241191 ┆ 70    │
# │ 181543 ┆ 70    │
# └────────┴───────┘
# 
# enrollment_fall:
# shape: (20, 2)
# ┌─────────────────┬───────┐
# │ enrollment_fall ┆ count │
# │ ---             ┆ ---   │
# │ i64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 0               ┆ 95864 │
# │ 1               ┆ 23886 │
# │ 2               ┆ 15244 │
# │ 3               ┆ 10917 │
# │ 4               ┆ 8667  │
# │ …               ┆ …     │
# │ 15              ┆ 2593  │
# │ 16              ┆ 2490  │
# │ 17              ┆ 2229  │
# │ 18              ┆ 2101  │
# │ 19              ┆ 2053  │
# └─────────────────┴───────┘
# 
# race:
# shape: (10, 2)
# ┌──────┬───────┐
# │ race ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 35241 │
# │ 99   ┆ 35241 │
# │ 7    ┆ 35241 │
# │ 9    ┆ 35241 │
# │ 2    ┆ 35241 │
# │ 5    ┆ 35241 │
# │ 6    ┆ 35241 │
# │ 4    ┆ 35241 │
# │ 8    ┆ 35241 │
# │ 3    ┆ 35241 │
# └──────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬────────┐
# │ year ┆ count  │
# │ ---  ┆ ---    │
# │ i64  ┆ u32    │
# ╞══════╪════════╡
# │ 2020 ┆ 352410 │
# └──────┴────────┘
# 
# Dtype summary:
#   unitid: Int64
#   year: Int64
#   enrollment_fall: Int64
#   race: Int64
#   sex: Int64
#   ftpt: Int64
#   level_of_study: Int64
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
