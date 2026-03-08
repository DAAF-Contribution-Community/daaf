#!/usr/bin/env python3
"""
Stage 7.2: Join core analysis dataset with enrollment race/ethnicity demographics.

Task: join-demographics
Wave: 5, Step: 2, Stage: 7
Depends on: join-core (COMPLETE - 2,528 rows), clean-enrollment-race (COMPLETE - 5,837 rows)
Input: data/processed/2026-02-15_core_joined.parquet, data/processed/2026-02-15_enrollment_race_clean.parquet
Output: data/processed/2026-02-15_core_demographics.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for joining the core analysis dataset (graduation rates, admissions,
# financial aid) with enrollment race/ethnicity demographics (URM share).
# The core dataset contains 2,528 4-year public/private nonprofit institutions.
# The enrollment_race dataset contains 5,837 institutions (all types). The LEFT join
# will match only the ~2,528 in our analysis universe; unmatched enrollment_race
# rows are expected and harmless.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_CORE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_joined.parquet"
INPUT_ENROLLMENT = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_enrollment_race_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_demographics.parquet"

# REASONING: unitid is the IPEDS unique institution identifier. Both datasets use
# Int64 type for unitid (verified in schema inspection). unitid is unique per
# institution in both datasets — core_joined has 2,528 unique unitids (1 per row)
# and enrollment_race_clean has 5,837 unique unitids (1 per row).
JOIN_KEY = "unitid"
EXPECTED_CARDINALITY = "1:1"
EXPECTED_CORE_ROWS = 2528

# --- Load ---
# Load both datasets and verify shapes match expectations from prior stages.
print("=" * 60)
print("Stage 7.2: Join Core + Enrollment Race Demographics")
print("=" * 60)

df_core = pl.read_parquet(INPUT_CORE)
df_enroll = pl.read_parquet(INPUT_ENROLLMENT)
print(f"Core:       {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"Enrollment: {df_enroll.shape[0]:,} rows x {df_enroll.shape[1]} cols")

# --- Pre-state ---
# Capture current state BEFORE join for post-validation comparison.
# Also verify join key properties required for a correct 1:1 LEFT join.
pre_core_rows = df_core.shape[0]
pre_core_cols = df_core.columns.copy()
pre_enroll_rows = df_enroll.shape[0]

print(f"\nPre-state:")
print(f"  Core rows: {pre_core_rows:,}")
print(f"  Core columns ({len(pre_core_cols)}): {pre_core_cols}")
print(f"  Enrollment rows: {pre_enroll_rows:,}")
print(f"  Enrollment columns: {df_enroll.columns}")

# Verify join key uniqueness in both datasets
# ASSUMES: Both datasets have 1 row per unitid (no year dimension in these
# aggregated/filtered datasets). If unitid is not unique, the join would fan out.
core_key_unique = df_core[JOIN_KEY].n_unique() == len(df_core)
enroll_key_unique = df_enroll[JOIN_KEY].n_unique() == len(df_enroll)
print(f"\n  Core unitid unique: {core_key_unique} ({df_core[JOIN_KEY].n_unique():,} unique / {len(df_core):,} rows)")
print(f"  Enrollment unitid unique: {enroll_key_unique} ({df_enroll[JOIN_KEY].n_unique():,} unique / {len(df_enroll):,} rows)")

# Check key overlap between the two datasets
core_keys = set(df_core[JOIN_KEY].to_list())
enroll_keys = set(df_enroll[JOIN_KEY].to_list())
key_overlap = len(core_keys & enroll_keys)
overlap_pct = key_overlap / len(core_keys) if core_keys else 0
print(f"  Key overlap: {key_overlap:,} / {len(core_keys):,} core institutions ({overlap_pct:.1%})")

# --- Join ---
# INTENT: Add URM (underrepresented minority) enrollment share to the core
# analysis dataset. This demographic variable is needed to test whether
# graduation rates primarily reflect student body demographics rather than
# institutional quality.
#
# REASONING: Using LEFT join (not INNER) because:
#   - The core dataset defines our analysis universe (2,528 4-yr pub/priv nonprofit)
#   - We want to PRESERVE all core institutions even if some lack race/ethnicity data
#   - Missing urm_share will be null (handled in analysis with appropriate caveats)
#   - enrollment_race has 5,837 rows (all institution types) — the ~3,300 that
#     don't match are community colleges, for-profits, etc. outside our universe
#   - Plan specifies LEFT join with 1:1 cardinality
#
# ASSUMES:
#   - unitid is unique per institution in both datasets (verified above)
#   - Both unitid columns are Int64 type (verified in schema inspection)
#   - Key overlap is high (~95%+) since both come from IPEDS for same year
#   - enrollment_race columns (total_enrollment_race, urm_enrollment, urm_share)
#     do not conflict with any core column names
result = df_core.join(
    df_enroll,
    on=JOIN_KEY,
    how="left",
)
print(f"\nJoin complete: {result.shape[0]:,} rows x {result.shape[1]} cols")

# --- Post-state Column Selection ---
# INTENT: Select only the columns needed for analysis, avoiding any redundant
# or unnecessary columns from the enrollment dataset. Keep urm_share as the
# primary demographic variable. Also keep urm_enrollment for documentation/
# transparency (allows users to verify the share computation).
#
# REASONING: total_enrollment_race is excluded because we already have
# enrollment_undergrad from the core dataset. Keeping both would create
# confusion about which enrollment figure to use (they may differ due to
# different reporting categories).
keep_cols = pre_core_cols + ["urm_share", "urm_enrollment"]

# Verify all expected columns exist before selecting
missing_cols = [c for c in keep_cols if c not in result.columns]
if missing_cols:
    print(f"WARNING: Missing expected columns: {missing_cols}")
    # Fall back to keeping only columns that exist
    keep_cols = [c for c in keep_cols if c in result.columns]

result = result.select(keep_cols)
print(f"After column selection: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Final columns: {result.columns}")

# --- Validate ---
# Checkpoint validation against Plan expectations.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: No fan-out — result rows must equal core rows (LEFT join preserves base)
no_fanout = result.shape[0] == pre_core_rows
print(f"  [{'PASS' if no_fanout else 'FAIL'}] No fan-out: {result.shape[0]:,} rows == {pre_core_rows:,} core rows")

# CP3.2: Result row count matches expected
rows_match_expected = result.shape[0] == EXPECTED_CORE_ROWS
print(f"  [{'PASS' if rows_match_expected else 'FAIL'}] Expected row count: {result.shape[0]:,} == {EXPECTED_CORE_ROWS:,}")

# CP3.3: urm_share values between 0 and 1 for non-null values
# REASONING: urm_share is a proportion (0.0 to 1.0), not a percentage.
# Values outside this range indicate a computation error upstream.
urm_non_null = result.filter(pl.col("urm_share").is_not_null())
if len(urm_non_null) > 0:
    urm_min = urm_non_null["urm_share"].min()
    urm_max = urm_non_null["urm_share"].max()
    urm_in_range = (urm_min >= 0.0) and (urm_max <= 1.0)
    print(f"  [{'PASS' if urm_in_range else 'FAIL'}] urm_share in [0, 1]: min={urm_min:.4f}, max={urm_max:.4f}")
else:
    urm_in_range = False
    print(f"  [FAIL] urm_share: ALL values are null")

# CP3.4: Document urm_share null rate
urm_null_count = result["urm_share"].null_count()
urm_null_rate = urm_null_count / len(result) if len(result) > 0 else 0
# REASONING: Some null is expected — institutions that don't appear in enrollment_race
# (due to being filtered out at a different stage or missing race data at source).
# A null rate above 20% would be concerning for analysis robustness.
urm_null_acceptable = urm_null_rate < 0.20
print(f"  [{'PASS' if urm_null_acceptable else 'WARN'}] urm_share null rate: {urm_null_count:,} / {len(result):,} ({urm_null_rate:.1%})")

# CP3.5: No unexpected row loss (row change should be 0% for LEFT join)
row_change_pct = ((result.shape[0] - pre_core_rows) / pre_core_rows * 100)
no_row_loss = row_change_pct == 0.0
print(f"  [{'PASS' if no_row_loss else 'FAIL'}] Row preservation: {row_change_pct:+.1f}% change")

# CP3.6: Core columns preserved (no columns lost from original core dataset)
core_cols_preserved = all(c in result.columns for c in pre_core_cols)
print(f"  [{'PASS' if core_cols_preserved else 'FAIL'}] Core columns preserved: {core_cols_preserved}")

# CP3.7: urm_share descriptive statistics for documentation
print(f"\n  urm_share summary (non-null):")
if len(urm_non_null) > 0:
    print(f"    Count: {len(urm_non_null):,}")
    print(f"    Mean:   {urm_non_null['urm_share'].mean():.4f}")
    print(f"    Median: {urm_non_null['urm_share'].median():.4f}")
    print(f"    Std:    {urm_non_null['urm_share'].std():.4f}")
    print(f"    Min:    {urm_non_null['urm_share'].min():.4f}")
    print(f"    Max:    {urm_non_null['urm_share'].max():.4f}")
    # Show quartiles
    q25 = urm_non_null["urm_share"].quantile(0.25)
    q75 = urm_non_null["urm_share"].quantile(0.75)
    print(f"    Q25:    {q25:.4f}")
    print(f"    Q75:    {q75:.4f}")

# Assert critical checks
assert no_fanout, f"STOP: Fan-out detected — {result.shape[0]:,} rows != {pre_core_rows:,} core rows"
assert rows_match_expected, f"STOP: Unexpected row count — {result.shape[0]:,} != {EXPECTED_CORE_ROWS:,}"
assert urm_in_range, "STOP: urm_share values outside [0, 1] range"
assert core_cols_preserved, "STOP: Core columns lost during join"

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size:,} bytes")

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:24:17
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/02_join-demographics.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.2: Join Core + Enrollment Race Demographics
# ============================================================
# Core:       2,528 rows x 19 cols
# Enrollment: 5,837 rows x 4 cols
# 
# Pre-state:
#   Core rows: 2,528
#   Core columns (19): ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share']
#   Enrollment rows: 5,837
#   Enrollment columns: ['unitid', 'total_enrollment_race', 'urm_enrollment', 'urm_share']
# 
#   Core unitid unique: True (2,528 unique / 2,528 rows)
#   Enrollment unitid unique: True (5,837 unique / 5,837 rows)
#   Key overlap: 2,158 / 2,528 core institutions (85.4%)
# 
# Join complete: 2,528 rows x 22 cols
# After column selection: 2,528 rows x 21 cols
# Final columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment']
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] No fan-out: 2,528 rows == 2,528 core rows
#   [PASS] Expected row count: 2,528 == 2,528
#   [PASS] urm_share in [0, 1]: min=0.0000, max=1.0000
#   [PASS] urm_share null rate: 370 / 2,528 (14.6%)
#   [PASS] Row preservation: +0.0% change
#   [PASS] Core columns preserved: True
# 
#   urm_share summary (non-null):
#     Count: 2,158
#     Mean:   0.2937
#     Median: 0.2089
#     Std:    0.2512
#     Min:    0.0000
#     Max:    1.0000
#     Q25:    0.1283
#     Q75:    0.3753
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_core_demographics.parquet
# File size: 121,506 bytes
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
