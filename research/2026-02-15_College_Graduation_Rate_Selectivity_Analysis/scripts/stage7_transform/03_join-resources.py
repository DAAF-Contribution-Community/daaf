#!/usr/bin/env python3
"""
Stage 7.3: Join resource datasets (SFR, retention) to core demographics.

Task: join-resources
Wave: 6, Step: 3, Stage: 7
Depends on: join-demographics (COMPLETE), clean-sfr (COMPLETE), clean-retention (COMPLETE)
Input: data/processed/2026-02-15_core_demographics.parquet (2,528 rows x 21 cols)
       data/processed/2026-02-15_sfr_clean.parquet (5,836 rows)
       data/processed/2026-02-15_retention_clean.parquet (5,836 rows)
Output: data/processed/2026-02-15_pre_analysis.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for joining resource datasets onto the core demographics
# dataset. Both SFR and retention contain all institution types (~5,836 rows), but
# core_demographics is already filtered to 4-year public/private nonprofit (~2,528 rows).
# LEFT JOIN ensures we keep all core institutions even if resource data is missing.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_CORE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_demographics.parquet"
INPUT_SFR = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfr_clean.parquet"
INPUT_RETENTION = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_retention_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_pre_analysis.parquet"

JOIN_KEY = "unitid"
EXPECTED_ROWS = 2528

# Key columns that must be present in the final dataset for analysis
REQUIRED_COLUMNS = [
    "unitid", "inst_name", "grad_rate_150pct", "admission_rate",
    "pell_share", "urm_share", "student_faculty_ratio", "retention_rate",
    "inst_control",
]

# --- Load ---
# Load all three input datasets and verify shapes match expectations before joining.
print("=" * 60)
print("Stage 7.3: Join Resources (SFR + Retention) to Core Demographics")
print("=" * 60)

df_core = pl.read_parquet(INPUT_CORE)
df_sfr = pl.read_parquet(INPUT_SFR)
df_retention = pl.read_parquet(INPUT_RETENTION)

print(f"Core demographics: {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"SFR:               {df_sfr.shape[0]:,} rows x {df_sfr.shape[1]} cols")
print(f"Retention:         {df_retention.shape[0]:,} rows x {df_retention.shape[1]} cols")

print(f"\nCore columns: {df_core.columns}")
print(f"SFR columns: {df_sfr.columns}")
print(f"Retention columns: {df_retention.columns}")

# --- Pre-state ---
# Capture key overlap statistics BEFORE joining. Both resource datasets have ~5,836
# rows covering all institution types, but only ~2,528 will match our 4-year
# public/private nonprofit universe in core_demographics. This is expected behavior.
pre_core_rows = df_core.shape[0]
pre_core_cols = df_core.columns.copy()

core_keys = set(df_core[JOIN_KEY].unique().to_list())
sfr_keys = set(df_sfr[JOIN_KEY].unique().to_list())
retention_keys = set(df_retention[JOIN_KEY].unique().to_list())

sfr_overlap = len(core_keys & sfr_keys)
retention_overlap = len(core_keys & retention_keys)
sfr_overlap_pct = sfr_overlap / len(core_keys) if core_keys else 0
retention_overlap_pct = retention_overlap / len(core_keys) if core_keys else 0

print(f"\nPre-state: {pre_core_rows:,} rows, {len(pre_core_cols)} cols in core")
print(f"SFR key overlap with core:       {sfr_overlap:,} / {len(core_keys):,} ({sfr_overlap_pct:.1%})")
print(f"Retention key overlap with core:  {retention_overlap:,} / {len(core_keys):,} ({retention_overlap_pct:.1%})")

# Verify uniqueness of join keys — required for 1:1 cardinality
core_key_unique = df_core[JOIN_KEY].n_unique() == len(df_core)
sfr_key_unique = df_sfr[JOIN_KEY].n_unique() == len(df_sfr)
retention_key_unique = df_retention[JOIN_KEY].n_unique() == len(df_retention)
print(f"\nCore keys unique:      {core_key_unique}")
print(f"SFR keys unique:       {sfr_key_unique}")
print(f"Retention keys unique: {retention_key_unique}")

# --- Join 1: Core + SFR ---
# INTENT: Add student-faculty ratio to the core demographics dataset. SFR is an
# institutional resource metric that may independently predict graduation rates
# beyond selectivity and demographics.
#
# REASONING: Using LEFT join (not INNER) because:
#   - We want to preserve all 2,528 core institutions even if SFR is missing
#   - SFR has 5,836 rows (all institution types) but only ~2,528 match our universe
#   - Non-matching SFR rows are simply institutions outside our scope (2-year, for-profit)
#   - Missing SFR values will be null, which is acceptable for downstream analysis
#
# ASSUMES:
#   - unitid is unique in both datasets (verified in pre-state above)
#   - SFR dataset may contain a 'year' column that needs to be excluded to avoid
#     duplicate column names (core already has 'year' if applicable)
#   - 1:1 cardinality — each core institution matches at most one SFR row
print("\n" + "-" * 40)
print("Join 1: Core + SFR")
print("-" * 40)

# INTENT: Select only the columns we need from SFR to avoid bringing in duplicate
# columns (e.g., 'year') that already exist in the core dataset.
# REASONING: SFR dataset has columns [unitid, year, student_faculty_ratio]. We only
# need unitid (for join) and student_faculty_ratio (the metric). Excluding 'year'
# prevents a column name collision and keeps the dataset clean.
sfr_join_cols = [JOIN_KEY, "student_faculty_ratio"]
df_sfr_slim = df_sfr.select(sfr_join_cols)

df_joined = df_core.join(df_sfr_slim, on=JOIN_KEY, how="left")
print(f"After SFR join: {df_joined.shape[0]:,} rows x {df_joined.shape[1]} cols")

sfr_nulls_after = df_joined["student_faculty_ratio"].null_count()
print(f"SFR nulls after join: {sfr_nulls_after:,} / {df_joined.shape[0]:,} ({sfr_nulls_after / df_joined.shape[0] * 100:.1f}%)")

# Fan-out check: row count must remain unchanged after 1:1 join
assert df_joined.shape[0] == pre_core_rows, (
    f"STOP: Fan-out detected in SFR join! Expected {pre_core_rows:,} rows, got {df_joined.shape[0]:,}"
)

# --- Join 2: Result + Retention ---
# INTENT: Add retention rate to the growing dataset. Retention rate measures the
# percentage of first-time full-time freshmen who return for their second year,
# which is a key indicator of institutional quality and student experience.
#
# REASONING: Using LEFT join for the same reasons as the SFR join — preserve all
# core institutions even if retention data is missing. The retention dataset has
# the same structure (5,836 rows covering all institution types).
#
# ASSUMES:
#   - unitid is unique in retention dataset (verified above)
#   - Retention dataset may contain a 'year' column that must be excluded
#   - 1:1 cardinality — each institution matches at most one retention row
#   - retention_rate is on 0-100 scale (percentage, not proportion) per clean script
#   - 654 nulls (11.2%) in retention_rate are expected per upstream documentation
print("\n" + "-" * 40)
print("Join 2: Result + Retention")
print("-" * 40)

# INTENT: Select only needed columns from retention to avoid column collisions.
retention_join_cols = [JOIN_KEY, "retention_rate"]
df_retention_slim = df_retention.select(retention_join_cols)

df_result = df_joined.join(df_retention_slim, on=JOIN_KEY, how="left")
print(f"After retention join: {df_result.shape[0]:,} rows x {df_result.shape[1]} cols")

retention_nulls_after = df_result["retention_rate"].null_count()
print(f"Retention nulls after join: {retention_nulls_after:,} / {df_result.shape[0]:,} ({retention_nulls_after / df_result.shape[0] * 100:.1f}%)")

# Fan-out check: row count must still match original core
assert df_result.shape[0] == pre_core_rows, (
    f"STOP: Fan-out detected in retention join! Expected {pre_core_rows:,} rows, got {df_result.shape[0]:,}"
)

# --- Post-state: Full Dataset Summary ---
# Comprehensive summary of the final pre-analysis dataset showing shape,
# all columns with data types, and null rates for every column.
print("\n" + "=" * 60)
print("POST-STATE: Full Dataset Summary")
print("=" * 60)

print(f"\nFinal shape: {df_result.shape[0]:,} rows x {df_result.shape[1]} cols")
print(f"Row change from core: {df_result.shape[0] - pre_core_rows:+,} ({(df_result.shape[0] - pre_core_rows) / pre_core_rows * 100:+.1f}%)")

print(f"\nAll columns ({df_result.shape[1]}):")
for col in df_result.columns:
    dtype = df_result[col].dtype
    null_ct = df_result[col].null_count()
    null_pct = null_ct / df_result.shape[0] * 100
    print(f"  {col:<30s} {str(dtype):<15s} nulls: {null_ct:>5,} ({null_pct:>5.1f}%)")

# --- Save ---
# Persist results in parquet format. Output path matches Plan specification.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation ---
# Checkpoint validation: verify join produced expected row count, no fan-out
# occurred, required columns are present, and null rates are documented.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: Row count matches expected (no fan-out, no data loss)
rows_match = df_result.shape[0] == EXPECTED_ROWS
print(f"  [{'PASS' if rows_match else 'FAIL'}] Row count: {df_result.shape[0]:,} (expected {EXPECTED_ROWS:,})")

# CP3.2: No fan-out from either join
no_fanout = df_result.shape[0] == pre_core_rows
print(f"  [{'PASS' if no_fanout else 'FAIL'}] No fan-out: {df_result.shape[0]:,} == {pre_core_rows:,} (core rows)")

# CP3.3: All required columns present
missing_cols = [c for c in REQUIRED_COLUMNS if c not in df_result.columns]
cols_present = len(missing_cols) == 0
print(f"  [{'PASS' if cols_present else 'FAIL'}] Required columns: {'all present' if cols_present else f'missing {missing_cols}'}")

# CP3.4: unitid has no nulls (join key integrity)
unitid_nulls = df_result["unitid"].null_count()
unitid_ok = unitid_nulls == 0
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] unitid no nulls: {unitid_nulls}")

# CP3.5: Document null rates for new columns (informational, not blocking)
sfr_null_pct = df_result["student_faculty_ratio"].null_count() / df_result.shape[0] * 100
retention_null_pct = df_result["retention_rate"].null_count() / df_result.shape[0] * 100
print(f"  [INFO] student_faculty_ratio null rate: {sfr_null_pct:.1f}%")
print(f"  [INFO] retention_rate null rate: {retention_null_pct:.1f}%")

# CP3.6: No unexpected row loss (>90% loss is suspicious)
row_change_pct = (df_result.shape[0] - pre_core_rows) / pre_core_rows * 100
acceptable_change = abs(row_change_pct) < 90
print(f"  [{'PASS' if acceptable_change else 'FAIL'}] Acceptable row change: {row_change_pct:+.1f}%")

# Assert critical checks
assert rows_match, f"STOP: Row count {df_result.shape[0]:,} != expected {EXPECTED_ROWS:,}"
assert no_fanout, f"STOP: Fan-out detected — rows changed from {pre_core_rows:,} to {df_result.shape[0]:,}"
assert cols_present, f"STOP: Missing required columns: {missing_cols}"
assert unitid_ok, f"STOP: unitid has {unitid_nulls} nulls"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:30:14
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/03_join-resources.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.3: Join Resources (SFR + Retention) to Core Demographics
# ============================================================
# Core demographics: 2,528 rows x 21 cols
# SFR:               5,836 rows x 3 cols
# Retention:         5,836 rows x 3 cols
# 
# Core columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment']
# SFR columns: ['unitid', 'year', 'student_faculty_ratio']
# Retention columns: ['unitid', 'year', 'retention_rate']
# 
# Pre-state: 2,528 rows, 21 cols in core
# SFR key overlap with core:       2,158 / 2,528 (85.4%)
# Retention key overlap with core:  2,158 / 2,528 (85.4%)
# 
# Core keys unique:      True
# SFR keys unique:       True
# Retention keys unique: True
# 
# ----------------------------------------
# Join 1: Core + SFR
# ----------------------------------------
# After SFR join: 2,528 rows x 22 cols
# SFR nulls after join: 370 / 2,528 (14.6%)
# 
# ----------------------------------------
# Join 2: Result + Retention
# ----------------------------------------
# After retention join: 2,528 rows x 23 cols
# Retention nulls after join: 653 / 2,528 (25.8%)
# 
# ============================================================
# POST-STATE: Full Dataset Summary
# ============================================================
# 
# Final shape: 2,528 rows x 23 cols
# Row change from core: +0 (+0.0%)
# 
# All columns (23):
#   unitid                         Int64           nulls:     0 (  0.0%)
#   year                           Int64           nulls:     0 (  0.0%)
#   inst_name                      String          nulls:     0 (  0.0%)
#   inst_control                   Int64           nulls:     0 (  0.0%)
#   institution_level              Int64           nulls:     0 (  0.0%)
#   hbcu                           Int64           nulls:     0 (  0.0%)
#   degree_granting                Int64           nulls:     0 (  0.0%)
#   urban_centric_locale           Int64           nulls:     2 (  0.1%)
#   state_abbr                     String          nulls:     0 (  0.0%)
#   fips                           Int64           nulls:     0 (  0.0%)
#   grad_rate_150pct               Float64         nulls:   732 ( 29.0%)
#   cohort_year                    Int64           nulls:   732 ( 29.0%)
#   number_applied                 Int64           nulls:   859 ( 34.0%)
#   number_admitted                Int64           nulls:   869 ( 34.4%)
#   number_enrolled_total          Int64           nulls:   870 ( 34.4%)
#   admission_rate                 Float64         nulls:   869 ( 34.4%)
#   pell_recipients                Float64         nulls:   496 ( 19.6%)
#   enrollment_undergrad           Int64           nulls:   370 ( 14.6%)
#   pell_share                     Float64         nulls:   518 ( 20.5%)
#   urm_share                      Float64         nulls:   370 ( 14.6%)
#   urm_enrollment                 Int64           nulls:   370 ( 14.6%)
#   student_faculty_ratio          Int64           nulls:   370 ( 14.6%)
#   retention_rate                 Float64         nulls:   653 ( 25.8%)
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_pre_analysis.parquet
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] Row count: 2,528 (expected 2,528)
#   [PASS] No fan-out: 2,528 == 2,528 (core rows)
#   [PASS] Required columns: all present
#   [PASS] unitid no nulls: 0
#   [INFO] student_faculty_ratio null rate: 14.6%
#   [INFO] retention_rate null rate: 25.8%
#   [PASS] Acceptable row change: +0.0%
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
