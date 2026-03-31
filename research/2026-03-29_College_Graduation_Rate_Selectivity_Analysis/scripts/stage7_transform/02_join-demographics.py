#!/usr/bin/env python3
"""
Stage 7.2: Join demographic variables (SFA Pell proxy, URM share) onto core dataset.

Task: join-demographics
Wave: 3, Step: 2, Stage: 7
Depends on: join-core (Stage 7.1), clean-sfa-grants (Stage 6.4), clean-enrollment-race (Stage 6.5)
Input: data/processed/2026-03-29_core.parquet,
       data/processed/2026-03-29_sfa_pell_clean.parquet,
       data/processed/2026-03-29_urm_share_clean.parquet
Output: data/processed/2026-03-29_core_demographics.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for joining demographic variables onto the core analysis dataset.
# Two LEFT joins preserve all 2,893 institutions from the core dataset.
# SFA provides grant recipient counts (Pell proxy); URM provides urm_share
# and total_ug_enrollment (used as pell_share denominator).
#
# The pell_share computation uses total_ug_enrollment from the URM/enrollment-race
# file rather than sfa_total_students from SFA because:
#   - Pell Grants are undergraduate-only, so the denominator should be UG enrollment
#   - total_ug_enrollment comes from IPEDS Fall Enrollment (race=99 total), which
#     is the standard headcount measure
#   - sfa_total_students comes from SFA survey and may differ in definition/timing
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_CORE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core.parquet"
INPUT_SFA = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfa_pell_clean.parquet"
INPUT_URM = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_urm_share_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_demographics.parquet"

JOIN_KEY = "unitid"
EXPECTED_CORE_ROWS = 2893

# --- Load ---
# Load all three input datasets and verify shapes before joining.
print("=" * 60)
print("Stage 7.2: Join Demographics onto Core")
print("=" * 60)

df_core = pl.read_parquet(INPUT_CORE)
df_sfa = pl.read_parquet(INPUT_SFA)
df_urm = pl.read_parquet(INPUT_URM)

print(f"Core:  {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"  Columns: {df_core.columns}")
print(f"SFA:   {df_sfa.shape[0]:,} rows x {df_sfa.shape[1]} cols")
print(f"  Columns: {df_sfa.columns}")
print(f"URM:   {df_urm.shape[0]:,} rows x {df_urm.shape[1]} cols")
print(f"  Columns: {df_urm.columns}")

# --- Pre-state ---
# INTENT: Capture join key overlap and uniqueness before joining. This establishes
# expected match rates and verifies 1:1 cardinality assumptions.
# REASONING: Pre-state capture allows us to distinguish between expected null
# introduction (institutions with no SFA/URM match) and unexpected data corruption.
pre_core_rows = df_core.shape[0]
pre_core_cols = df_core.columns.copy()

# Verify unitid uniqueness in all three datasets (required for 1:1 joins)
core_unitid_unique = df_core[JOIN_KEY].n_unique() == df_core.shape[0]
sfa_unitid_unique = df_sfa[JOIN_KEY].n_unique() == df_sfa.shape[0]
urm_unitid_unique = df_urm[JOIN_KEY].n_unique() == df_urm.shape[0]

print(f"\nUnitid uniqueness:")
print(f"  Core: {core_unitid_unique} ({df_core[JOIN_KEY].n_unique():,} unique / {df_core.shape[0]:,} rows)")
print(f"  SFA:  {sfa_unitid_unique} ({df_sfa[JOIN_KEY].n_unique():,} unique / {df_sfa.shape[0]:,} rows)")
print(f"  URM:  {urm_unitid_unique} ({df_urm[JOIN_KEY].n_unique():,} unique / {df_urm.shape[0]:,} rows)")

assert core_unitid_unique, "STOP: unitid not unique in core dataset"
assert sfa_unitid_unique, "STOP: unitid not unique in SFA dataset"
assert urm_unitid_unique, "STOP: unitid not unique in URM dataset"

# Key overlap analysis
core_keys = set(df_core[JOIN_KEY].to_list())
sfa_keys = set(df_sfa[JOIN_KEY].to_list())
urm_keys = set(df_urm[JOIN_KEY].to_list())

sfa_overlap = len(core_keys & sfa_keys)
urm_overlap = len(core_keys & urm_keys)
sfa_overlap_pct = sfa_overlap / len(core_keys) * 100
urm_overlap_pct = urm_overlap / len(core_keys) * 100

print(f"\nKey overlap with core:")
print(f"  SFA: {sfa_overlap:,} / {len(core_keys):,} ({sfa_overlap_pct:.1f}%)")
print(f"  URM: {urm_overlap:,} / {len(core_keys):,} ({urm_overlap_pct:.1f}%)")

# --- Join 1: Core LEFT JOIN SFA ---
# INTENT: Attach grant recipient counts (Pell proxy) to the core dataset.
# REASONING: Using LEFT join to retain all core institutions. Institutions not
# in SFA will get null for grant_recipients and sfa_total_students. This is
# expected -- not all institutions may be in the SFA survey for a given year.
#
# ASSUMES:
#   - unitid is unique in both datasets (verified above)
#   - SFA columns (grant_recipients, sfa_total_students) do not conflict with
#     existing core columns
#   - Expected cardinality is 1:1
result = df_core.join(df_sfa, on=JOIN_KEY, how="left")

print(f"\nAfter Join 1 (Core LEFT JOIN SFA):")
print(f"  Rows: {result.shape[0]:,} (core was {pre_core_rows:,})")
print(f"  Cols: {result.shape[1]} (was {df_core.shape[1]})")

# Join 1 validation: no fan-out
assert result.shape[0] == pre_core_rows, (
    f"STOP: Fan-out detected in SFA join: {result.shape[0]:,} rows vs {pre_core_rows:,} expected"
)

# --- Join 2: Result LEFT JOIN URM ---
# INTENT: Attach URM share and total UG enrollment to the dataset.
# REASONING: Using LEFT join to retain all core institutions. The URM file
# provides both urm_share (for demographic analysis) and total_ug_enrollment
# (used as denominator for pell_share computation).
#
# ASSUMES:
#   - unitid is unique in URM dataset (verified above)
#   - URM columns (urm_share, total_ug_enrollment) do not conflict with existing
#     columns in the intermediate result
#   - Expected cardinality is 1:1
result = result.join(df_urm, on=JOIN_KEY, how="left")

print(f"\nAfter Join 2 (Result LEFT JOIN URM):")
print(f"  Rows: {result.shape[0]:,} (core was {pre_core_rows:,})")
print(f"  Cols: {result.shape[1]}")

# Join 2 validation: no fan-out
assert result.shape[0] == pre_core_rows, (
    f"STOP: Fan-out detected in URM join: {result.shape[0]:,} rows vs {pre_core_rows:,} expected"
)

# --- Compute pell_share ---
# INTENT: Compute pell_share as the ratio of grant recipients to total UG enrollment.
# This represents the proportion of undergraduates receiving any federal/institutional
# grant aid, serving as a proxy for Pell Grant share.
#
# REASONING: Using total_ug_enrollment (from IPEDS Fall Enrollment) as denominator
# rather than sfa_total_students because:
#   - Pell Grants are limited to undergraduates, so UG enrollment is the appropriate base
#   - Fall enrollment headcount (IPEDS EF) is the standard enrollment measure
#   - sfa_total_students from SFA may use a different count methodology
# Only compute where both numerator and denominator are non-null and denominator > 0.
# Values > 1 indicate data quality issues (grant recipients exceeding enrollment count)
# and are flagged but not capped, per transparency principle.
#
# ASSUMES:
#   - grant_recipients and total_ug_enrollment are both non-negative where non-null
#   - Denominator of 0 or null produces null pell_share (not infinity)
#   - This is an all-grant proxy, not Pell-specific (~90% of federal grants are Pell)
result = result.with_columns(
    pl.when(
        pl.col("grant_recipients").is_not_null()
        & pl.col("total_ug_enrollment").is_not_null()
        & (pl.col("total_ug_enrollment") > 0)
    )
    .then(pl.col("grant_recipients") / pl.col("total_ug_enrollment"))
    .otherwise(None)
    .alias("pell_share")
)

# --- Post-state ---
# INTENT: Document the state of the joined dataset including new column statistics.
# REASONING: This validates that joins and computation produced reasonable results.
post_rows = result.shape[0]
post_cols = result.columns

print(f"\nPost-state: {post_rows:,} rows x {len(post_cols)} cols")
print(f"Row change: {post_rows - pre_core_rows:+,} ({(post_rows - pre_core_rows) / pre_core_rows * 100:+.1f}%)")
print(f"New columns: {[c for c in post_cols if c not in pre_core_cols]}")

# Null analysis for all columns
print("\nNull counts (all columns):")
for col in result.columns:
    null_ct = result[col].null_count()
    null_pct = null_ct / post_rows * 100 if post_rows > 0 else 0
    print(f"  {col}: {null_ct:,} ({null_pct:.1f}%)")

# grant_recipients statistics
gr = result["grant_recipients"].drop_nulls()
gr_null = result["grant_recipients"].null_count()
print(f"\ngrant_recipients: non-null={gr.len():,}, null={gr_null:,}")
if gr.len() > 0:
    print(f"  Min={gr.min():,}, Max={gr.max():,}, Median={gr.median():,.0f}, Mean={gr.mean():,.0f}")

# pell_share statistics
ps = result["pell_share"].drop_nulls()
ps_null = result["pell_share"].null_count()
print(f"\npell_share: non-null={ps.len():,}, null={ps_null:,}")
if ps.len() > 0:
    print(f"  Min={ps.min():.4f}, Max={ps.max():.4f}, Median={ps.median():.4f}, Mean={ps.mean():.4f}")
    ps_gt1 = ps.filter(ps > 1.0).len()
    print(f"  Values > 1.0: {ps_gt1:,} ({'WARN: data quality issue' if ps_gt1 > 0 else 'OK'})")
    ps_lt0 = ps.filter(ps < 0.0).len()
    print(f"  Values < 0.0: {ps_lt0:,} ({'FAIL' if ps_lt0 > 0 else 'OK'})")

# urm_share statistics
us = result["urm_share"].drop_nulls()
us_null = result["urm_share"].null_count()
print(f"\nurm_share: non-null={us.len():,}, null={us_null:,}")
if us.len() > 0:
    print(f"  Min={us.min():.4f}, Max={us.max():.4f}, Median={us.median():.4f}, Mean={us.mean():.4f}")

# total_ug_enrollment statistics
te = result["total_ug_enrollment"].drop_nulls()
te_null = result["total_ug_enrollment"].null_count()
print(f"\ntotal_ug_enrollment: non-null={te.len():,}, null={te_null:,}")
if te.len() > 0:
    print(f"  Min={te.min():,}, Max={te.max():,}, Median={te.median():,.0f}, Mean={te.mean():,.0f}")

# --- Save ---
# Persist results in parquet format. This becomes the input for subsequent
# transform steps (e.g., join-resources, create-bands).
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists on disk
assert OUTPUT_PATH.exists(), f"STOP: Output file not found: {OUTPUT_PATH}"
file_size_kb = OUTPUT_PATH.stat().st_size / 1024
print(f"File size: {file_size_kb:.1f} KB")

# --- CP3 Validation ---
# INTENT: Verify transformation preserved data integrity after both joins and
# the pell_share computation. This is the gating checkpoint for downstream tasks.
# ASSUMES: Pre-state variables (pre_core_rows, pre_core_cols) are still in scope.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

cp3_passed = True

# CP3.1: Row count preserved (LEFT joins should not change row count)
rows_match = result.shape[0] == EXPECTED_CORE_ROWS
print(f"  [{'PASS' if rows_match else 'FAIL'}] Row count preserved: {result.shape[0]:,} == {EXPECTED_CORE_ROWS:,}")
if not rows_match:
    cp3_passed = False

# CP3.2: No fan-out (result rows == core rows)
no_fanout = result.shape[0] == pre_core_rows
print(f"  [{'PASS' if no_fanout else 'FAIL'}] No fan-out: {result.shape[0]:,} rows")
if not no_fanout:
    cp3_passed = False

# CP3.3: unitid still unique
unitid_still_unique = result[JOIN_KEY].n_unique() == result.shape[0]
print(f"  [{'PASS' if unitid_still_unique else 'FAIL'}] unitid unique: {result[JOIN_KEY].n_unique():,} / {result.shape[0]:,}")
if not unitid_still_unique:
    cp3_passed = False

# CP3.4: No nulls in critical columns (unitid, inst_name, inst_control)
critical_cols = ["unitid", "inst_name", "inst_control"]
critical_nulls = {col: result[col].null_count() for col in critical_cols if col in result.columns}
no_critical_nulls = all(v == 0 for v in critical_nulls.values())
print(f"  [{'PASS' if no_critical_nulls else 'FAIL'}] Critical column nulls: {critical_nulls}")
if not no_critical_nulls:
    cp3_passed = False

# CP3.5: New columns present
expected_new_cols = ["grant_recipients", "sfa_total_students", "urm_share", "total_ug_enrollment", "pell_share"]
missing_new_cols = [c for c in expected_new_cols if c not in result.columns]
all_new_present = len(missing_new_cols) == 0
print(f"  [{'PASS' if all_new_present else 'FAIL'}] New columns present: {expected_new_cols}")
if not all_new_present:
    print(f"    Missing: {missing_new_cols}")
    cp3_passed = False

# CP3.6: pell_share range validation (where non-null)
ps_valid = result["pell_share"].drop_nulls()
if ps_valid.len() > 0:
    ps_min_ok = ps_valid.min() >= 0
    ps_gt1_count = ps_valid.filter(ps_valid > 1.0).len()
    ps_range_ok = ps_min_ok  # Values > 1 are WARN, not FAIL
    print(f"  [{'PASS' if ps_min_ok else 'FAIL'}] pell_share >= 0: min={ps_valid.min():.4f}")
    if ps_gt1_count > 0:
        print(f"  [WARN] pell_share > 1.0: {ps_gt1_count:,} institutions (data quality issue, not capped)")
    else:
        print(f"  [PASS] pell_share <= 1.0: all values in [0, 1]")
    if not ps_min_ok:
        cp3_passed = False
else:
    print(f"  [WARN] pell_share: all null ({result['pell_share'].null_count():,})")

# CP3.7: urm_share range validation (where non-null)
us_valid = result["urm_share"].drop_nulls()
if us_valid.len() > 0:
    us_range_ok = us_valid.min() >= 0 and us_valid.max() <= 1.0
    print(f"  [{'PASS' if us_range_ok else 'FAIL'}] urm_share in [0, 1]: min={us_valid.min():.4f}, max={us_valid.max():.4f}")
    if not us_range_ok:
        cp3_passed = False
else:
    print(f"  [WARN] urm_share: all null")

# CP3.8: Match rates (SFA and URM should match > 80% of core)
sfa_match_ok = sfa_overlap_pct > 80
urm_match_ok = urm_overlap_pct > 80
print(f"  [{'PASS' if sfa_match_ok else 'WARN'}] SFA match rate: {sfa_overlap_pct:.1f}% (threshold: >80%)")
print(f"  [{'PASS' if urm_match_ok else 'WARN'}] URM match rate: {urm_overlap_pct:.1f}% (threshold: >80%)")

# CP3.9: Preserved columns from core still present
preserved_cols = ["unitid", "inst_name", "fips", "inst_control", "admit_rate", "completion_rate_150pct"]
missing_preserved = [c for c in preserved_cols if c not in result.columns]
all_preserved = len(missing_preserved) == 0
print(f"  [{'PASS' if all_preserved else 'FAIL'}] Core columns preserved: {len(preserved_cols) - len(missing_preserved)}/{len(preserved_cols)}")
if not all_preserved:
    print(f"    Missing: {missing_preserved}")
    cp3_passed = False

assert cp3_passed, "STOP: CP3 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 00:20:54
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/02_join-demographics.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.2: Join Demographics onto Core
# ============================================================
# Core:  2,893 rows x 14 cols
#   Columns: ['unitid', 'inst_name', 'fips', 'inst_control', 'open_public', 'hbcu', 'tribal_college', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admit_rate', 'completion_rate_150pct', 'completers_150pct', 'cohort_adj_150pct']
# SFA:   5,320 rows x 3 cols
#   Columns: ['unitid', 'grant_recipients', 'sfa_total_students']
# URM:   5,837 rows x 3 cols
#   Columns: ['unitid', 'urm_share', 'total_ug_enrollment']
# 
# Unitid uniqueness:
#   Core: True (2,893 unique / 2,893 rows)
#   SFA:  True (5,320 unique / 5,320 rows)
#   URM:  True (5,837 unique / 5,837 rows)
# 
# Key overlap with core:
#   SFA: 2,224 / 2,893 (76.9%)
#   URM: 2,473 / 2,893 (85.5%)
# 
# After Join 1 (Core LEFT JOIN SFA):
#   Rows: 2,893 (core was 2,893)
#   Cols: 16 (was 14)
# 
# After Join 2 (Result LEFT JOIN URM):
#   Rows: 2,893 (core was 2,893)
#   Cols: 18
# 
# Post-state: 2,893 rows x 19 cols
# Row change: +0 (+0.0%)
# New columns: ['grant_recipients', 'sfa_total_students', 'urm_share', 'total_ug_enrollment', 'pell_share']
# 
# Null counts (all columns):
#   unitid: 0 (0.0%)
#   inst_name: 0 (0.0%)
#   fips: 0 (0.0%)
#   inst_control: 0 (0.0%)
#   open_public: 0 (0.0%)
#   hbcu: 0 (0.0%)
#   tribal_college: 0 (0.0%)
#   number_applied: 1,130 (39.1%)
#   number_admitted: 1,142 (39.5%)
#   number_enrolled_total: 1,144 (39.5%)
#   admit_rate: 1,142 (39.5%)
#   completion_rate_150pct: 947 (32.7%)
#   completers_150pct: 947 (32.7%)
#   cohort_adj_150pct: 888 (30.7%)
#   grant_recipients: 669 (23.1%)
#   sfa_total_students: 669 (23.1%)
#   urm_share: 423 (14.6%)
#   total_ug_enrollment: 420 (14.5%)
#   pell_share: 669 (23.1%)
# 
# grant_recipients: non-null=2,224, null=669
#   Min=0, Max=4,519, Median=207, Mean=380
# 
# pell_share: non-null=2,224, null=669
#   Min=0.0000, Max=1.1852, Median=0.1001, Mean=0.1131
#   Values > 1.0: 1 (WARN: data quality issue)
#   Values < 0.0: 0 (OK)
# 
# urm_share: non-null=2,470, null=423
#   Min=0.0000, Max=1.0000, Median=0.2681, Mean=0.3504
# 
# total_ug_enrollment: non-null=2,473, null=420
#   Min=2, Max=111,599, Median=1,562, Mean=4,508
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_core_demographics.parquet
# File size: 133.8 KB
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] Row count preserved: 2,893 == 2,893
#   [PASS] No fan-out: 2,893 rows
#   [PASS] unitid unique: 2,893 / 2,893
#   [PASS] Critical column nulls: {'unitid': 0, 'inst_name': 0, 'inst_control': 0}
#   [PASS] New columns present: ['grant_recipients', 'sfa_total_students', 'urm_share', 'total_ug_enrollment', 'pell_share']
#   [PASS] pell_share >= 0: min=0.0000
#   [WARN] pell_share > 1.0: 1 institutions (data quality issue, not capped)
#   [PASS] urm_share in [0, 1]: min=0.0000, max=1.0000
#   [WARN] SFA match rate: 76.9% (threshold: >80%)
#   [PASS] URM match rate: 85.5% (threshold: >80%)
#   [PASS] Core columns preserved: 6/6
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
