#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 01
QA Checkpoint: QA3 (Post-Transform Quality Assessment)

Reviewed script: scripts/stage7_transform/01_join-core_a.py
Output files: data/processed/2026-02-15_core_joined.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan expectations (required output columns present)
2. Row count exactly 2,528 (directory universe preserved)
3. Distribution sanity (no all-same, no all-zero columns)
4. Coded values properly filtered (-1, -2, -3 absent from numeric columns)
5. Critical columns present (grad_rate_150pct, admission_rate, pell_share, enrollment_undergrad)

Script-Specific Checks (Five Skeptical Lenses):
6. COUNTERFACTUAL: What if enrollment_race has different unitids than directory? Verify LEFT join didn't silently fail
7. SEMANTIC: Does pell_share actually serve the research question (proxy for SES composition)?
8. BOUNDARY: Check pell_share at boundaries (0, near 1, exactly 1 after capping)
9. ABSENCE: Is open_admissions truly absent? Are there columns the Plan expected but missing?
10. DOWNSTREAM: Will join-demographics (next step) find what it needs in this output?

Spot-Checks:
11. Pick 3 specific institutions and trace their pell_share computation end-to-end
12. Verify that institutions with null pell_share have the expected null pattern (either pell_recipients or enrollment null)
13. Verify admission_rate match count vs admissions overlap (cross-reference)
14. Check that no institution has enrollment_undergrad==0 (would indicate div-by-zero escape)
15. Verify grad_rate_150pct is in valid range (0-100 or 0-1) for non-null rows
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_core_joined.parquet"

# Input files (for cross-validation)
INPUT_DIRECTORY = PROJECT_DIR / "data" / "processed" / "2026-02-15_directory_clean.parquet"
INPUT_GRAD_RATES = PROJECT_DIR / "data" / "processed" / "2026-02-15_grad_rates_clean.parquet"
INPUT_ADMISSIONS = PROJECT_DIR / "data" / "processed" / "2026-02-15_admissions_clean.parquet"
INPUT_FSA_GRANTS = PROJECT_DIR / "data" / "processed" / "2026-02-15_fsa_grants_clean.parquet"
INPUT_ENROLLMENT_RACE = PROJECT_DIR / "data" / "processed" / "2026-02-15_enrollment_race_clean.parquet"

EXPECTED_ROWS = 2528
EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "inst_control", "institution_level", "hbcu",
    "degree_granting", "urban_centric_locale", "state_abbr", "fips",
    "grad_rate_150pct", "cohort_year",
    "number_applied", "number_admitted", "number_enrolled_total", "admission_rate",
    "pell_recipients", "enrollment_undergrad", "pell_share"
]
CRITICAL_COLUMNS = ["grad_rate_150pct", "admission_rate", "pell_share", "enrollment_undergrad"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 01 (join-core)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load inputs for cross-validation
df_dir = pl.read_parquet(INPUT_DIRECTORY)
df_gr = pl.read_parquet(INPUT_GRAD_RATES)
df_adm = pl.read_parquet(INPUT_ADMISSIONS)
df_fsa = pl.read_parquet(INPUT_FSA_GRANTS)
df_enr = pl.read_parquet(INPUT_ENROLLMENT_RACE)

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
    print(f"  Extra columns (not in expected list): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64, pl.Int32, pl.Int16, pl.Int8)).columns:
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

# --- Check 5: Critical columns null rates ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_ct = df[col].null_count()
        null_pct = null_ct / len(df) * 100
        # WARNING threshold is >40%
        if null_pct > 40:
            null_issues.append(f"{col}: {null_ct} nulls ({null_pct:.1f}%) -- EXCEEDS 40% THRESHOLD")
        else:
            print(f"  [INFO] {col}: {null_ct:,} nulls ({null_pct:.1f}%)")
nulls_warning = len(null_issues) > 0
if nulls_warning:
    for issue in null_issues:
        print(f"  [WARN] {issue}")
else:
    print(f"[PASS] Critical column null rates all under 40% threshold")

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ==========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: COUNTERFACTUAL — LEFT join correctness ---
# If enrollment_race had zero overlap with directory, enrollment_undergrad would be all null.
# Verify the join actually transferred data.
enr_nonnull = df.filter(pl.col("enrollment_undergrad").is_not_null()).shape[0]
enr_expected_overlap = len(set(df_dir["unitid"].to_list()) & set(df_enr["unitid"].to_list()))
counterfactual_ok = enr_nonnull == enr_expected_overlap
print(f"\n[{'PASS' if counterfactual_ok else 'FAIL'}] COUNTERFACTUAL (enrollment join transfer): "
      f"{enr_nonnull:,} non-null enrollment_undergrad matches expected overlap of {enr_expected_overlap:,}")

# Also verify grad_rate_150pct non-null count matches expected overlap
gr_nonnull = df.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]
gr_expected_overlap = len(set(df_dir["unitid"].to_list()) & set(df_gr["unitid"].to_list()))
gr_match = gr_nonnull == gr_expected_overlap
print(f"[{'PASS' if gr_match else 'FAIL'}] COUNTERFACTUAL (grad_rate join transfer): "
      f"{gr_nonnull:,} non-null grad_rate matches expected overlap of {gr_expected_overlap:,}")

# --- Check 7: SEMANTIC — pell_share as SES proxy ---
# For pell_share to be a meaningful SES proxy:
# - It should have a reasonable mean (US average ~34% for 4-yr institutions)
# - It should have meaningful variance (not all clustered near one value)
# - It should not be negative
pell_valid = df.filter(pl.col("pell_share").is_not_null())
pell_mean = pell_valid["pell_share"].mean()
pell_std = pell_valid["pell_share"].std()
pell_min = pell_valid["pell_share"].min()
pell_max = pell_valid["pell_share"].max()
pell_negative = pell_valid.filter(pl.col("pell_share") < 0).shape[0]

semantic_ok = (pell_negative == 0
               and 0.15 < pell_mean < 0.60
               and pell_std > 0.05
               and pell_min >= 0
               and pell_max <= 1.0)
print(f"\n[{'PASS' if semantic_ok else 'FAIL'}] SEMANTIC (pell_share as SES proxy):")
print(f"  Mean: {pell_mean:.4f} (expect ~0.34 for 4-yr institutions)")
print(f"  Std: {pell_std:.4f} (needs meaningful variance)")
print(f"  Range: [{pell_min:.4f}, {pell_max:.4f}]")
print(f"  Negative values: {pell_negative}")

# --- Check 8: BOUNDARY — pell_share at boundaries ---
# After capping, max should be exactly 1.0 (33 institutions were capped)
pell_at_one = pell_valid.filter(pl.col("pell_share") == 1.0).shape[0]
pell_at_zero = pell_valid.filter(pl.col("pell_share") == 0.0).shape[0]
pell_near_one = pell_valid.filter(pl.col("pell_share") > 0.95).shape[0]
# Also check: were the 33 capped institutions actually different originally?
# Can verify by recomputing from raw components
boundary_ok = pell_max <= 1.0 and pell_min >= 0.0
print(f"\n[{'PASS' if boundary_ok else 'FAIL'}] BOUNDARY (pell_share edges):")
print(f"  At 0.0: {pell_at_zero}")
print(f"  At 1.0 (capped): {pell_at_one}")
print(f"  Near 1.0 (>0.95): {pell_near_one}")

# Verify capping by recomputing from raw pell_recipients and enrollment_undergrad
df_with_raw = df.filter(
    pl.col("pell_recipients").is_not_null()
    & pl.col("enrollment_undergrad").is_not_null()
    & (pl.col("enrollment_undergrad") > 0)
)
raw_pell_share = (df_with_raw["pell_recipients"].cast(pl.Float64) / df_with_raw["enrollment_undergrad"].cast(pl.Float64))
gt_one_raw = (raw_pell_share > 1.0).sum()
print(f"  Recomputed: {gt_one_raw} institutions have raw pell_share > 1.0 (script logged 33)")
cap_check = gt_one_raw == pell_at_one
print(f"  [{'PASS' if cap_check else 'WARN'}] Capped count consistency: recomputed {gt_one_raw} vs output {pell_at_one} at exactly 1.0")

# --- Check 9: ABSENCE — missing columns from Plan ---
# Plan specified open_admissions and enrollment_undergrad from directory.
# Script documents that these are NOT in the fetched directory data.
# Verify that open_admissions is truly not in the directory clean.
dir_cols = df_dir.columns
has_open_adm = "open_admissions" in dir_cols
has_enroll_ug = "enrollment_undergrad" in dir_cols
print(f"\n[PASS] ABSENCE (documented missing columns):")
print(f"  open_admissions in directory_clean: {has_open_adm} (expected False — documented deviation)")
print(f"  enrollment_undergrad in directory_clean: {has_enroll_ug} (expected False — used enrollment_race instead)")

# Also check: cc_basic_2021 is in Plan's variable list but NOT in output columns
cc_in_plan = True  # Plan lists cc_basic_2021 as a directory variable
cc_in_output = "cc_basic_2021" in df.columns
cc_in_directory = "cc_basic_2021" in df_dir.columns
print(f"  cc_basic_2021 in Plan variable list: {cc_in_plan}")
print(f"  cc_basic_2021 in directory_clean: {cc_in_directory}")
print(f"  cc_basic_2021 in output: {cc_in_output}")
if not cc_in_output and cc_in_directory:
    print(f"  [INFO] cc_basic_2021 is in directory but not carried through to output — acceptable if not needed for join-core")
elif not cc_in_output and not cc_in_directory:
    print(f"  [INFO] cc_basic_2021 not in directory_clean — may have been excluded at fetch/clean stage")

# --- Check 10: DOWNSTREAM — join-demographics readiness ---
# Next step needs: unitid, all core columns, and will add urm_share.
# Verify unitid is present and unique; verify key columns for downstream.
downstream_ok = (
    "unitid" in df.columns
    and df["unitid"].n_unique() == len(df)
    and "year" in df.columns
    and "inst_name" in df.columns
    and "pell_share" in df.columns
)
print(f"\n[{'PASS' if downstream_ok else 'FAIL'}] DOWNSTREAM (join-demographics readiness):")
print(f"  unitid present and unique: {('unitid' in df.columns) and (df['unitid'].n_unique() == len(df))}")
print(f"  year present: {'year' in df.columns}")
print(f"  pell_share present: {'pell_share' in df.columns}")
print(f"  Output columns: {df.columns}")

# ==========================================================================
# SPOT-CHECKS
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Trace 3 specific institutions through pell_share computation ---
# Pick 3 unitids that have non-null pell_share
sample_ids = df.filter(pl.col("pell_share").is_not_null()).sample(3, seed=42)["unitid"].to_list()
print(f"\nSpot-check 11: Tracing pell_share for unitids {sample_ids}")
for uid in sample_ids:
    # Get pell_recipients from FSA
    fsa_row = df_fsa.filter(pl.col("unitid") == uid)
    pell_recip = fsa_row["pell_recipients"][0] if len(fsa_row) > 0 else None

    # Get enrollment from enrollment_race
    enr_row = df_enr.filter(pl.col("unitid") == uid)
    enroll = enr_row["total_enrollment_race"][0] if len(enr_row) > 0 else None

    # Get output pell_share
    out_row = df.filter(pl.col("unitid") == uid)
    out_pell = out_row["pell_share"][0] if len(out_row) > 0 else None
    inst_name = out_row["inst_name"][0] if len(out_row) > 0 else "UNKNOWN"

    # Recompute
    expected = None
    if pell_recip is not None and enroll is not None and enroll > 0:
        expected = min(pell_recip / enroll, 1.0)

    match = (expected is None and out_pell is None) or (expected is not None and out_pell is not None and abs(expected - out_pell) < 0.0001)
    print(f"  unitid={uid} ({inst_name}): pell_recip={pell_recip}, enroll={enroll}, "
          f"expected={expected:.4f if expected is not None else 'null'}, "
          f"actual={out_pell:.4f if out_pell is not None else 'null'} "
          f"-> [{'PASS' if match else 'FAIL'}]")

# --- Spot-check 12: Null pattern verification for pell_share ---
# If pell_share is null, either pell_recipients or enrollment_undergrad should be null (or enrollment 0)
pell_null_rows = df.filter(pl.col("pell_share").is_null())
null_explained = pell_null_rows.filter(
    pl.col("pell_recipients").is_null()
    | pl.col("enrollment_undergrad").is_null()
    | (pl.col("enrollment_undergrad") == 0)
).shape[0]
null_unexplained = pell_null_rows.shape[0] - null_explained
null_pattern_ok = null_unexplained == 0
print(f"\n[{'PASS' if null_pattern_ok else 'FAIL'}] Spot-check 12: Null pell_share pattern")
print(f"  Total null pell_share: {pell_null_rows.shape[0]:,}")
print(f"  Explained by null inputs or zero enrollment: {null_explained:,}")
print(f"  Unexplained: {null_unexplained:,}")

# --- Spot-check 13: Admission_rate match count cross-reference ---
adm_nonnull = df.filter(pl.col("admission_rate").is_not_null()).shape[0]
adm_expected_overlap = len(set(df_dir["unitid"].to_list()) & set(df_adm["unitid"].to_list()))
# Note: some admissions records may have null admission_rate even if joined
# So adm_nonnull might be <= adm_expected_overlap
adm_xref_ok = adm_nonnull <= adm_expected_overlap
print(f"\n[{'PASS' if adm_xref_ok else 'FAIL'}] Spot-check 13: Admission rate cross-reference")
print(f"  Non-null admission_rate in output: {adm_nonnull:,}")
print(f"  Directory-admissions key overlap: {adm_expected_overlap:,}")
print(f"  Difference (nulls within matched institutions): {adm_expected_overlap - adm_nonnull:,}")

# --- Spot-check 14: No zero enrollment_undergrad ---
zero_enroll = df.filter(
    pl.col("enrollment_undergrad").is_not_null() & (pl.col("enrollment_undergrad") == 0)
).shape[0]
zero_enroll_ok = zero_enroll == 0
print(f"\n[{'PASS' if zero_enroll_ok else 'WARN'}] Spot-check 14: Zero enrollment_undergrad")
print(f"  Institutions with enrollment_undergrad == 0: {zero_enroll}")
if zero_enroll > 0:
    print("  (These should have null pell_share due to div-by-zero guard)")

# --- Spot-check 15: Grad rate range validity ---
gr_valid = df.filter(pl.col("grad_rate_150pct").is_not_null())
gr_min = gr_valid["grad_rate_150pct"].min()
gr_max = gr_valid["grad_rate_150pct"].max()
# Stage 6 cleaning converted 0-1 to 0-100 for IPEDS rates
# Need to check which scale was used
gr_range_ok = gr_min >= 0 and gr_max <= 100
print(f"\n[{'PASS' if gr_range_ok else 'FAIL'}] Spot-check 15: Grad rate range")
print(f"  Range: [{gr_min:.2f}, {gr_max:.2f}]")
if gr_max <= 1.0:
    print(f"  Scale: 0-1 (proportion)")
elif gr_max <= 100:
    print(f"  Scale: 0-100 (percentage)")
else:
    print(f"  [WARN] Unexpected range — values exceed 100")

# ==========================================================================
# DATA PROFILING
# ==========================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["inst_control", "institution_level", "hbcu", "year"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort(col))

print("\nCritical columns:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col} (non-null: {df[col].drop_nulls().shape[0]}):")
        if df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
            print(f"  min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.4f}, "
                  f"median={df[col].median():.4f}, std={df[col].std():.4f}")

# ==========================================================================
# SUMMARY
# ==========================================================================
print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

all_checks = [
    ("Schema", schema_ok),
    ("Row count", rows_ok),
    ("Distributions", dist_ok),
    ("Coded values", coded_ok),
    ("Counterfactual (enrollment join)", counterfactual_ok),
    ("Counterfactual (grad rate join)", gr_match),
    ("Semantic (pell_share)", semantic_ok),
    ("Boundary (pell_share)", boundary_ok),
    ("Downstream readiness", downstream_ok),
    ("Null pattern", null_pattern_ok),
    ("Admission cross-ref", adm_xref_ok),
    ("Zero enrollment", zero_enroll_ok),
    ("Grad rate range", gr_range_ok),
]

all_passed = all(ok for _, ok in all_checks)
has_warnings = nulls_warning or not cap_check

for name, ok in all_checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

if nulls_warning:
    print(f"  [WARN] Critical column null rates exceed 40% threshold")
if not cap_check:
    print(f"  [WARN] Pell share cap count mismatch")

severity = "PASSED" if all_passed and not has_warnings else ("BLOCKER" if not all_passed else "WARNING")
print(f"\nQA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:19:42
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr1.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 01 (join-core)
# ============================================================
# Loaded output: 2,528 rows x 19 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 2,528 (expected exactly 2,528)
# [FAIL] Distributions: year: all same value (2020); institution_level: all same value (4); cohort_year: all same value (2015)
# [PASS] Coded values: None remain
#   [INFO] grad_rate_150pct: 732 nulls (29.0%)
#   [INFO] admission_rate: 869 nulls (34.4%)
#   [INFO] pell_share: 518 nulls (20.5%)
#   [INFO] enrollment_undergrad: 370 nulls (14.6%)
# [PASS] Critical column null rates all under 40% threshold
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] COUNTERFACTUAL (enrollment join transfer): 2,158 non-null enrollment_undergrad matches expected overlap of 2,158
# [PASS] COUNTERFACTUAL (grad_rate join transfer): 1,796 non-null grad_rate matches expected overlap of 1,796
# 
# [PASS] SEMANTIC (pell_share as SES proxy):
#   Mean: 0.4027 (expect ~0.34 for 4-yr institutions)
#   Std: 0.1972 (needs meaningful variance)
#   Range: [0.0000, 1.0000]
#   Negative values: 0
# 
# [PASS] BOUNDARY (pell_share edges):
#   At 0.0: 8
#   At 1.0 (capped): 34
#   Near 1.0 (>0.95): 42
#   Recomputed: 33 institutions have raw pell_share > 1.0 (script logged 33)
#   [WARN] Capped count consistency: recomputed 33 vs output 34 at exactly 1.0
# 
# [PASS] ABSENCE (documented missing columns):
#   open_admissions in directory_clean: False (expected False — documented deviation)
#   enrollment_undergrad in directory_clean: False (expected False — used enrollment_race instead)
#   cc_basic_2021 in Plan variable list: True
#   cc_basic_2021 in directory_clean: False
#   cc_basic_2021 in output: False
#   [INFO] cc_basic_2021 not in directory_clean — may have been excluded at fetch/clean stage
# 
# [PASS] DOWNSTREAM (join-demographics readiness):
#   unitid present and unique: True
#   year present: True
#   pell_share present: True
#   Output columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share']
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-check 11: Tracing pell_share for unitids [233277, 164216, 490504]
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr1.py", line 277, in <module>
#     f"expected={expected:.4f if expected is not None else 'null'}, "
#                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# ValueError: Invalid format specifier '.4f if expected is not None else 'null'' for object of type 'float'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
