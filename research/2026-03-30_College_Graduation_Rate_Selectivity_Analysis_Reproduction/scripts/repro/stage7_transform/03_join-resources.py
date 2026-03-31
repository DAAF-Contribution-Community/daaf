#!/usr/bin/env python3
"""
Stage 7.3: Join resource datasets (SFR, Retention, Finance) onto core demographics.

Task: join-resources
Wave: 3, Step: 3, Stage: 7
Depends on: join-demographics (Stage 7.2), clean-sfr, clean-retention, clean-finance
Input:
  - data/processed/2026-03-29_core_demographics.parquet (2,893 rows, left side)
  - data/processed/2026-03-29_sfr_clean.parquet (student-faculty ratio)
  - data/processed/2026-03-29_retention_clean.parquet (retention rate)
  - data/processed/2026-03-29_finance_clean.parquet (instructional expenditure per FTE)
Output: data/processed/2026-03-29_merged.parquet
Checkpoint: CP3

Notes:
  - All three joins are LEFT JOIN on unitid with expected 1:1 cardinality.
  - Finance data is from ~2017 while other data is from 2020. This cross-year
    join is intentional per Plan: instructional spending is slow-moving.
  - Resource files have no overlapping columns (aside from unitid join key):
    SFR = [unitid, student_faculty_ratio]
    Retention = [unitid, retention_rate]
    Finance = [unitid, instr_expend_per_fte]
  - Resource files cover more IPEDS institutions than the 2,893 in our analysis
    dataset, so match rates will be <100%.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for joining resource datasets onto core demographics.
# The left side (core demographics) was produced by Stage 7.2 and contains
# directory, admissions, graduation rates, SFA grants, and enrollment-race data.
# This script adds three resource variables: SFR, retention, and finance.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_CORE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_demographics.parquet"
INPUT_SFR = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfr_clean.parquet"
INPUT_RETENTION = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_retention_clean.parquet"
INPUT_FINANCE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_finance_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_merged.parquet"

# REASONING: unitid is the IPEDS institution identifier, unique per institution
# in both the core demographics dataset and each resource file. All Stage 6
# cleaning scripts selected only [unitid, <metric>], ensuring no column overlaps.
JOIN_KEY = "unitid"
EXPECTED_CARDINALITY = "1:1"

# Invariants from prior stages (documented in task specification)
EXPECTED_ROWS = 2893
CRITICAL_COLS = ["unitid", "inst_name", "inst_control"]

# --- Load ---
# Load all four input datasets and verify shapes before joining.
print("=" * 60)
print("Stage 7.3: Join Resource Datasets (SFR, Retention, Finance)")
print("=" * 60)

df_core = pl.read_parquet(INPUT_CORE)
df_sfr = pl.read_parquet(INPUT_SFR)
df_retention = pl.read_parquet(INPUT_RETENTION)
df_finance = pl.read_parquet(INPUT_FINANCE)

print(f"Core Demographics: {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"SFR:               {df_sfr.shape[0]:,} rows x {df_sfr.shape[1]} cols  {df_sfr.columns}")
print(f"Retention:         {df_retention.shape[0]:,} rows x {df_retention.shape[1]} cols  {df_retention.columns}")
print(f"Finance:           {df_finance.shape[0]:,} rows x {df_finance.shape[1]} cols  {df_finance.columns}")

# --- Pre-state ---
# Capture state BEFORE any joins for post-validation comparison.
# Record unitid overlap between core and each resource file to establish
# expected match rates. Also verify 1:1 cardinality assumption (unitid unique
# in each resource file).
pre_rows = df_core.shape[0]
pre_cols = df_core.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"  First 3 unitids: {df_core['unitid'].head(3).to_list()}")

# INTENT: Check unitid uniqueness in all datasets to verify 1:1 cardinality assumption.
# REASONING: If any resource file has duplicate unitids, the left join would fan out,
# violating the invariant that result row count must equal core row count (2,893).
core_unique = df_core[JOIN_KEY].n_unique() == df_core.shape[0]
sfr_unique = df_sfr[JOIN_KEY].n_unique() == df_sfr.shape[0]
ret_unique = df_retention[JOIN_KEY].n_unique() == df_retention.shape[0]
fin_unique = df_finance[JOIN_KEY].n_unique() == df_finance.shape[0]

print(f"\nUnitid uniqueness:")
print(f"  Core:      {core_unique} ({df_core[JOIN_KEY].n_unique():,} unique / {df_core.shape[0]:,} rows)")
print(f"  SFR:       {sfr_unique} ({df_sfr[JOIN_KEY].n_unique():,} unique / {df_sfr.shape[0]:,} rows)")
print(f"  Retention: {ret_unique} ({df_retention[JOIN_KEY].n_unique():,} unique / {df_retention.shape[0]:,} rows)")
print(f"  Finance:   {fin_unique} ({df_finance[JOIN_KEY].n_unique():,} unique / {df_finance.shape[0]:,} rows)")

assert core_unique, "STOP: Core demographics has duplicate unitids"
assert sfr_unique, "STOP: SFR has duplicate unitids -- cannot do 1:1 join"
assert ret_unique, "STOP: Retention has duplicate unitids -- cannot do 1:1 join"
assert fin_unique, "STOP: Finance has duplicate unitids -- cannot do 1:1 join"

# INTENT: Compute unitid overlap between core and each resource file.
# REASONING: LEFT join preserves all core rows; overlap determines how many
# rows get non-null values for each resource variable. Overlap rates below
# expectations (SFR >70%, Retention >70%, Finance >60%) would warrant investigation.
core_keys = set(df_core[JOIN_KEY].to_list())

sfr_keys = set(df_sfr[JOIN_KEY].to_list())
sfr_overlap = len(core_keys & sfr_keys)
sfr_match_pct = sfr_overlap / len(core_keys) * 100

ret_keys = set(df_retention[JOIN_KEY].to_list())
ret_overlap = len(core_keys & ret_keys)
ret_match_pct = ret_overlap / len(core_keys) * 100

fin_keys = set(df_finance[JOIN_KEY].to_list())
fin_overlap = len(core_keys & fin_keys)
fin_match_pct = fin_overlap / len(core_keys) * 100

print(f"\nKey overlap (core vs resource):")
print(f"  SFR:       {sfr_overlap:,} / {len(core_keys):,} ({sfr_match_pct:.1f}%)")
print(f"  Retention: {ret_overlap:,} / {len(core_keys):,} ({ret_match_pct:.1f}%)")
print(f"  Finance:   {fin_overlap:,} / {len(core_keys):,} ({fin_match_pct:.1f}%)")

# --- Join 1: Core LEFT JOIN SFR ---
# INTENT: Add student-faculty ratio to the core demographics dataset.
# REASONING: LEFT join preserves all 2,893 core rows. Institutions without
# SFR data will have null in student_faculty_ratio. SFR is a continuous
# measure of institutional resources (lower = more resources per student).
# ASSUMES: unitid is unique in both datasets (verified above). SFR file
# contains only [unitid, student_faculty_ratio], so no column collisions.
print("\n--- Join 1: Core LEFT JOIN SFR ---")
result = df_core.join(df_sfr, on=JOIN_KEY, how="left")
print(f"After SFR join: {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == pre_rows, (
    f"STOP: Fan-out after SFR join: {result.shape[0]:,} rows (expected {pre_rows:,})"
)
sfr_matched = result["student_faculty_ratio"].drop_nulls().len()
print(f"  SFR matched: {sfr_matched:,} / {pre_rows:,} ({sfr_matched / pre_rows * 100:.1f}%)")

# --- Join 2: Result LEFT JOIN Retention ---
# INTENT: Add full-time retention rate to the growing merged dataset.
# REASONING: LEFT join preserves all core rows. Retention rate measures the
# percentage of first-time full-time students who return for the second year.
# This is a key institutional quality indicator for graduation rate analysis.
# ASSUMES: unitid is unique in retention file (verified above). Retention file
# contains only [unitid, retention_rate], so no column collisions.
print("\n--- Join 2: Result LEFT JOIN Retention ---")
result = result.join(df_retention, on=JOIN_KEY, how="left")
print(f"After Retention join: {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == pre_rows, (
    f"STOP: Fan-out after Retention join: {result.shape[0]:,} rows (expected {pre_rows:,})"
)
ret_matched = result["retention_rate"].drop_nulls().len()
print(f"  Retention matched: {ret_matched:,} / {pre_rows:,} ({ret_matched / pre_rows * 100:.1f}%)")

# --- Join 3: Result LEFT JOIN Finance ---
# INTENT: Add instructional expenditure per FTE to complete the merged dataset.
# REASONING: LEFT join preserves all core rows. Finance data is from ~2017 while
# other data is from 2020. This cross-year join is intentional per Plan because
# instructional spending is slow-moving (institutional budgets change incrementally).
# The 3-year lag is documented in the Plan and accepted as reasonable.
# ASSUMES: unitid is unique in finance file (verified above). Finance file
# contains only [unitid, instr_expend_per_fte], so no column collisions.
print("\n--- Join 3: Result LEFT JOIN Finance ---")
result = result.join(df_finance, on=JOIN_KEY, how="left")
print(f"After Finance join: {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == pre_rows, (
    f"STOP: Fan-out after Finance join: {result.shape[0]:,} rows (expected {pre_rows:,})"
)
fin_matched = result["instr_expend_per_fte"].drop_nulls().len()
print(f"  Finance matched: {fin_matched:,} / {pre_rows:,} ({fin_matched / pre_rows * 100:.1f}%)")

# --- Post-state ---
# Capture state AFTER all joins for validation comparison.
post_rows = result.shape[0]
post_cols = result.columns.copy()
new_cols = [c for c in post_cols if c not in pre_cols]
print(f"\nPost-state: {post_rows:,} rows, {len(post_cols)} cols")
print(f"  First 3 unitids: {result['unitid'].head(3).to_list()}")
print(f"  New columns added: {new_cols}")
print(f"  Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# INTENT: Document null counts for all columns in the merged result, focusing on
# the three new resource columns to quantify match rates precisely.
print(f"\nNull counts for new columns:")
for col in new_cols:
    null_ct = result[col].null_count()
    null_pct = null_ct / post_rows * 100
    print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

print(f"\nNull counts for critical columns:")
for col in CRITICAL_COLS:
    null_ct = result[col].null_count()
    print(f"  {col}: {null_ct:,} nulls")

# Full column listing with types
print(f"\nFull schema ({len(post_cols)} columns):")
for col in post_cols:
    print(f"  {col}: {result[col].dtype} (nulls: {result[col].null_count():,})")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file was written successfully
assert OUTPUT_PATH.exists(), f"STOP: Output file not found: {OUTPUT_PATH}"
file_size_kb = OUTPUT_PATH.stat().st_size / 1024
print(f"File size: {file_size_kb:.1f} KB")

# --- CP3 Validation: Post-Transformation ---
# INTENT: Validate that the three sequential LEFT JOINs preserved data integrity,
# produced expected row counts, and introduced no unexpected issues.
# ASSUMES: Expected row count is 2,893 (from core demographics), cardinality is
# 1:1 for all joins, and critical columns must have zero nulls.
print("\n" + "=" * 60)
print("CP3 VALIDATION: POST-TRANSFORMATION (join-resources)")
print("=" * 60)

cp3_passed = True

# CP3.1: Row count preserved (LEFT JOIN on unique keys should not change row count)
rows_ok = post_rows == EXPECTED_ROWS
print(f"  [{'PASS' if rows_ok else 'FAIL'}] Row count preserved: {post_rows:,} (expected {EXPECTED_ROWS:,})")
if not rows_ok:
    cp3_passed = False

# CP3.2: No fan-out from any join (already asserted inline, but confirm final)
no_fanout = post_rows <= pre_rows
print(f"  [{'PASS' if no_fanout else 'FAIL'}] No fan-out: {post_rows:,} <= {pre_rows:,}")
if not no_fanout:
    cp3_passed = False

# CP3.3: New resource columns present
expected_new_cols = ["student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]
missing_new = [c for c in expected_new_cols if c not in result.columns]
cols_present = len(missing_new) == 0
print(f"  [{'PASS' if cols_present else 'FAIL'}] New columns present: {expected_new_cols}")
if not cols_present:
    print(f"    Missing: {missing_new}")
    cp3_passed = False

# CP3.4: Match rates within expected bounds
# REASONING: Match rates depend on how many IPEDS institutions overlap with our
# analysis population. SFR/Retention cover most 4-year Title IV institutions.
# Finance data (from 2017) may have slightly lower coverage due to cross-year lag.
sfr_match_ok = sfr_match_pct > 70
ret_match_ok = ret_match_pct > 70
fin_match_ok = fin_match_pct > 60
print(f"  [{'PASS' if sfr_match_ok else 'WARN'}] SFR match rate: {sfr_match_pct:.1f}% (threshold >70%)")
print(f"  [{'PASS' if ret_match_ok else 'WARN'}] Retention match rate: {ret_match_pct:.1f}% (threshold >70%)")
print(f"  [{'PASS' if fin_match_ok else 'WARN'}] Finance match rate: {fin_match_pct:.1f}% (threshold >60%)")

# CP3.5: No nulls in critical columns (invariant from prior stages)
critical_nulls = 0
for col in CRITICAL_COLS:
    null_ct = result[col].null_count()
    if null_ct > 0:
        print(f"  [FAIL] Critical column {col} has {null_ct:,} nulls")
        critical_nulls += null_ct
        cp3_passed = False
if critical_nulls == 0:
    print(f"  [PASS] No nulls in critical columns: {CRITICAL_COLS}")

# CP3.6: No duplicate column names (sanity check after multiple joins)
has_dupes = len(result.columns) != len(set(result.columns))
print(f"  [{'FAIL' if has_dupes else 'PASS'}] No duplicate column names")
if has_dupes:
    cp3_passed = False

# CP3.7: Unitid still unique in result
result_unique = result[JOIN_KEY].n_unique() == result.shape[0]
print(f"  [{'PASS' if result_unique else 'FAIL'}] Unitid unique in result: {result[JOIN_KEY].n_unique():,} / {result.shape[0]:,}")
if not result_unique:
    cp3_passed = False

# CP3.8: No completely null new columns
for col in expected_new_cols:
    all_null = result[col].null_count() == result.shape[0]
    if all_null:
        print(f"  [FAIL] {col} is entirely null -- join produced no matches")
        cp3_passed = False

print(f"\nCP3 VALIDATION: {'PASSED' if cp3_passed else 'FAILED'}")
print("=" * 60)

if not cp3_passed:
    raise ValueError("CP3 FAILED - see details above")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:32:57
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage7_transform/03_join-resources.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.3: Join Resource Datasets (SFR, Retention, Finance)
# ============================================================
# Core Demographics: 2,893 rows x 19 cols
# SFR:               5,835 rows x 2 cols  ['unitid', 'student_faculty_ratio']
# Retention:         5,836 rows x 2 cols  ['unitid', 'retention_rate']
# Finance:           6,522 rows x 2 cols  ['unitid', 'instr_expend_per_fte']
# 
# Pre-state: 2,893 rows, 19 cols
#   First 3 unitids: [100654, 100663, 100690]
# 
# Unitid uniqueness:
#   Core:      True (2,893 unique / 2,893 rows)
#   SFR:       True (5,835 unique / 5,835 rows)
#   Retention: True (5,836 unique / 5,836 rows)
#   Finance:   True (6,522 unique / 6,522 rows)
# 
# Key overlap (core vs resource):
#   SFR:       2,472 / 2,893 (85.4%)
#   Retention: 2,472 / 2,893 (85.4%)
#   Finance:   2,748 / 2,893 (95.0%)
# 
# --- Join 1: Core LEFT JOIN SFR ---
# After SFR join: 2,893 rows x 20 cols
#   SFR matched: 2,472 / 2,893 (85.4%)
# 
# --- Join 2: Result LEFT JOIN Retention ---
# After Retention join: 2,893 rows x 21 cols
#   Retention matched: 2,081 / 2,893 (71.9%)
# 
# --- Join 3: Result LEFT JOIN Finance ---
# After Finance join: 2,893 rows x 22 cols
#   Finance matched: 2,631 / 2,893 (90.9%)
# 
# Post-state: 2,893 rows, 22 cols
#   First 3 unitids: [100654, 100663, 100690]
#   New columns added: ['student_faculty_ratio', 'retention_rate', 'instr_expend_per_fte']
#   Row change: +0 (+0.0%)
# 
# Null counts for new columns:
#   student_faculty_ratio: 421 nulls (14.6%)
#   retention_rate: 812 nulls (28.1%)
#   instr_expend_per_fte: 262 nulls (9.1%)
# 
# Null counts for critical columns:
#   unitid: 0 nulls
#   inst_name: 0 nulls
#   inst_control: 0 nulls
# 
# Full schema (22 columns):
#   unitid: Int64 (nulls: 0)
#   inst_name: String (nulls: 0)
#   fips: Int64 (nulls: 0)
#   inst_control: Int64 (nulls: 0)
#   open_public: Int64 (nulls: 0)
#   hbcu: Int64 (nulls: 0)
#   tribal_college: Int64 (nulls: 0)
#   number_applied: Int64 (nulls: 1,130)
#   number_admitted: Int64 (nulls: 1,142)
#   number_enrolled_total: Int64 (nulls: 1,144)
#   admit_rate: Float64 (nulls: 1,142)
#   completion_rate_150pct: Float64 (nulls: 947)
#   completers_150pct: Int64 (nulls: 947)
#   cohort_adj_150pct: Int64 (nulls: 888)
#   grant_recipients: Int64 (nulls: 669)
#   sfa_total_students: Int64 (nulls: 669)
#   urm_share: Float64 (nulls: 423)
#   total_ug_enrollment: Int64 (nulls: 420)
#   pell_share: Float64 (nulls: 669)
#   student_faculty_ratio: Float64 (nulls: 421)
#   retention_rate: Float64 (nulls: 812)
#   instr_expend_per_fte: Float64 (nulls: 262)
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_merged.parquet
# File size: 160.3 KB
# 
# ============================================================
# CP3 VALIDATION: POST-TRANSFORMATION (join-resources)
# ============================================================
#   [PASS] Row count preserved: 2,893 (expected 2,893)
#   [PASS] No fan-out: 2,893 <= 2,893
#   [PASS] New columns present: ['student_faculty_ratio', 'retention_rate', 'instr_expend_per_fte']
#   [PASS] SFR match rate: 85.4% (threshold >70%)
#   [PASS] Retention match rate: 85.4% (threshold >70%)
#   [PASS] Finance match rate: 95.0% (threshold >60%)
#   [PASS] No nulls in critical columns: ['unitid', 'inst_name', 'inst_control']
#   [PASS] No duplicate column names
#   [PASS] Unitid unique in result: 2,893 / 2,893
# 
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
