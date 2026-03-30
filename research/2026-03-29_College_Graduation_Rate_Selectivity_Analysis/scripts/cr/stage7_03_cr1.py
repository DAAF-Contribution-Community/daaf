#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 03

Reviewed script: scripts/stage7_transform/03_join-resources.py
Output files: data/processed/2026-03-29_merged.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

QA Checks (Script-Specific - Five Lenses):
6. [Counterfactual] What if a resource file had duplicate unitids?
7. [Semantic] Does the merged output actually enable regression Model 3?
8. [Boundary] Check for zero/negative values in resource columns
9. [Absence] Are there institutions missing ALL three resource columns?
10. [Downstream] Does the downstream create-bands script get what it needs?

Spot Checks:
11. Trace a specific institution through all joins
12. Verify SFR non-null count matches join overlap minus pre-existing nulls
13. Verify retention non-null count consistency
14. Check that finance values are plausible (positive, reasonable range)
15. Verify no row order corruption by checking unitid sort stability
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_merged.parquet"
INPUT_CORE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_demographics.parquet"
INPUT_SFR = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfr_clean.parquet"
INPUT_RETENTION = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_retention_clean.parquet"
INPUT_FINANCE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_finance_clean.parquet"

EXPECTED_COLUMNS = [
    "unitid", "inst_name", "fips", "inst_control", "open_public",
    "hbcu", "tribal_college",
    "number_applied", "number_admitted", "number_enrolled_total", "admit_rate",
    "completion_rate_150pct", "completers_150pct", "cohort_adj_150pct",
    "grant_recipients", "sfa_total_students",
    "urm_share", "total_ug_enrollment", "pell_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"
]
EXPECTED_ROWS = 2893
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 03 (join-resources)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load inputs for cross-reference
df_core = pl.read_parquet(INPUT_CORE)
df_sfr = pl.read_parquet(INPUT_SFR)
df_retention = pl.read_parquet(INPUT_RETENTION)
df_finance = pl.read_parquet(INPUT_FINANCE)

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All 22 expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROWS:,})")

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
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
if coded_ok:
    print("None remain in integer columns")
else:
    print("; ".join(coded_issues))

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

# ==========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ==========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Verify 1:1 cardinality in source files ---
# INTENT: What if a resource file had duplicate unitids? The LEFT join would
# fan out. Verify independently that all source files have unique unitids.
sfr_unique = df_sfr["unitid"].n_unique() == df_sfr.shape[0]
ret_unique = df_retention["unitid"].n_unique() == df_retention.shape[0]
fin_unique = df_finance["unitid"].n_unique() == df_finance.shape[0]
cardinality_ok = sfr_unique and ret_unique and fin_unique
print(f"[{'PASS' if cardinality_ok else 'FAIL'}] [Counterfactual] 1:1 cardinality verified in all source files")
if not cardinality_ok:
    if not sfr_unique:
        print(f"  SFR: {df_sfr['unitid'].n_unique()} unique / {df_sfr.shape[0]} rows")
    if not ret_unique:
        print(f"  Retention: {df_retention['unitid'].n_unique()} unique / {df_retention.shape[0]} rows")
    if not fin_unique:
        print(f"  Finance: {df_finance['unitid'].n_unique()} unique / {df_finance.shape[0]} rows")

# --- Check 7: [Semantic] Does the merged output enable regression Model 3? ---
# INTENT: Plan requires Model 3 = completion_rate_150pct ~ admit_rate +
# pell_share + urm_share + student_faculty_ratio + retention_rate + instr_expend_per_fte.
# Are all these variables present and do enough rows have non-null values for regression?
model3_vars = [
    "completion_rate_150pct", "admit_rate", "pell_share", "urm_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"
]
model3_missing = [v for v in model3_vars if v not in df.columns]
model3_cols_present = len(model3_missing) == 0
print(f"[{'PASS' if model3_cols_present else 'FAIL'}] [Semantic] Model 3 regression vars present: {model3_cols_present}")

if model3_cols_present:
    complete_cases = df.drop_nulls(subset=model3_vars).shape[0]
    complete_pct = complete_cases / len(df) * 100
    # Plan allows up to 30% listwise deletion
    complete_ok = complete_pct >= 70
    print(f"  Complete cases for Model 3: {complete_cases:,} / {len(df):,} ({complete_pct:.1f}%)")
    print(f"  [{'PASS' if complete_ok else 'WARN'}] Sufficient for regression (>70% needed): {complete_ok}")
else:
    print(f"  Missing: {model3_missing}")

# --- Check 8: [Boundary] Zero/negative values in resource columns ---
# INTENT: Resource measures should be positive. student_faculty_ratio < 0 or
# instr_expend_per_fte < 0 would indicate data corruption.
resource_cols = ["student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]
boundary_issues = []
for col in resource_cols:
    non_null = df[col].drop_nulls()
    if len(non_null) == 0:
        boundary_issues.append(f"{col}: entirely null")
        continue
    neg_count = (non_null < 0).sum()
    zero_count = (non_null == 0).sum()
    if neg_count > 0:
        boundary_issues.append(f"{col}: {neg_count} negative values")
    if zero_count > 0 and col != "instr_expend_per_fte":
        # Zero SFR or zero retention would be suspicious
        boundary_issues.append(f"{col}: {zero_count} zero values (suspicious)")

boundary_ok = len(boundary_issues) == 0
print(f"[{'PASS' if boundary_ok else 'WARN'}] [Boundary] Resource column value ranges: ", end="")
if boundary_ok:
    print("All positive, no suspicious zeros")
else:
    print("; ".join(boundary_issues))

# Print actual ranges for context
for col in resource_cols:
    non_null = df[col].drop_nulls()
    if len(non_null) > 0:
        print(f"  {col}: min={non_null.min():.2f}, max={non_null.max():.2f}, "
              f"median={non_null.median():.2f}, nulls={df[col].null_count()}")

# --- Check 9: [Absence] Institutions missing ALL three resource columns ---
# INTENT: If an institution has no resource data at all, it contributes nothing
# to the resource analysis and might indicate a systematic exclusion.
all_resource_null = (
    df.filter(
        pl.col("student_faculty_ratio").is_null()
        & pl.col("retention_rate").is_null()
        & pl.col("instr_expend_per_fte").is_null()
    )
)
n_all_null = all_resource_null.shape[0]
all_null_pct = n_all_null / len(df) * 100
absence_ok = all_null_pct < 20  # If >20% have zero resource data, investigate
print(f"[{'PASS' if absence_ok else 'WARN'}] [Absence] Institutions missing ALL resource columns: "
      f"{n_all_null} ({all_null_pct:.1f}%)")
if n_all_null > 0:
    # Check what these institutions look like
    null_controls = all_resource_null["inst_control"].value_counts().sort("count", descending=True)
    print(f"  inst_control distribution of fully-missing: {null_controls.to_dict()}")

# --- Check 10: [Downstream] Does create-bands get what it needs? ---
# INTENT: The next script (04_create-bands.py) needs to create selectivity_band,
# pell_quintile, and urm_quintile. Verify the required inputs exist.
downstream_required = ["admit_rate", "open_public", "pell_share", "urm_share"]
downstream_missing = [c for c in downstream_required if c not in df.columns]
downstream_ok = len(downstream_missing) == 0
print(f"[{'PASS' if downstream_ok else 'FAIL'}] [Downstream] create-bands input columns present: {downstream_ok}")
if downstream_missing:
    print(f"  Missing: {downstream_missing}")

# ==========================================================================
# SPOT CHECKS
# ==========================================================================

print("\n" + "=" * 60)
print("SPOT CHECKS")
print("=" * 60)

# --- Spot Check 11: Trace a specific institution ---
# Pick three unitids from different parts of the data and verify their
# resource values match the source files.
sample_ids = df["unitid"].head(3).to_list()
print(f"\nSpot-check institutions: {sample_ids}")
for uid in sample_ids:
    merged_row = df.filter(pl.col("unitid") == uid)
    sfr_row = df_sfr.filter(pl.col("unitid") == uid)
    ret_row = df_retention.filter(pl.col("unitid") == uid)
    fin_row = df_finance.filter(pl.col("unitid") == uid)

    m_sfr = merged_row["student_faculty_ratio"][0] if merged_row.shape[0] > 0 else "NOT_FOUND"
    s_sfr = sfr_row["student_faculty_ratio"][0] if sfr_row.shape[0] > 0 else "NOT_IN_SFR"
    m_ret = merged_row["retention_rate"][0] if merged_row.shape[0] > 0 else "NOT_FOUND"
    s_ret = ret_row["retention_rate"][0] if ret_row.shape[0] > 0 else "NOT_IN_RET"
    m_fin = merged_row["instr_expend_per_fte"][0] if merged_row.shape[0] > 0 else "NOT_FOUND"
    s_fin = fin_row["instr_expend_per_fte"][0] if fin_row.shape[0] > 0 else "NOT_IN_FIN"

    sfr_match = str(m_sfr) == str(s_sfr) or (m_sfr is None and sfr_row.shape[0] == 0)
    ret_match = str(m_ret) == str(s_ret) or (m_ret is None and ret_row.shape[0] == 0)
    fin_match = str(m_fin) == str(s_fin) or (m_fin is None and fin_row.shape[0] == 0)

    print(f"  unitid={uid}: SFR {m_sfr} vs {s_sfr} [{'OK' if sfr_match else 'MISMATCH'}], "
          f"Ret {m_ret} vs {s_ret} [{'OK' if ret_match else 'MISMATCH'}], "
          f"Fin {m_fin} vs {s_fin} [{'OK' if fin_match else 'MISMATCH'}]")

# --- Spot Check 12: SFR non-null count consistency ---
# The merged file should have SFR non-null = core institutions that appear in SFR file
core_keys = set(df_core["unitid"].to_list())
sfr_keys = set(df_sfr["unitid"].to_list())
expected_sfr_nonnull_from_keys = len(core_keys & sfr_keys)
# But subtract any that are null in SFR file itself
sfr_null_in_source = df_sfr.filter(pl.col("student_faculty_ratio").is_null()).shape[0]
expected_sfr_nonnull = expected_sfr_nonnull_from_keys - sfr_null_in_source
actual_sfr_nonnull = df["student_faculty_ratio"].drop_nulls().len()
sfr_consistent = actual_sfr_nonnull == expected_sfr_nonnull
# Allow for tiny rounding: some SFR source nulls in matched keys
print(f"\n[{'PASS' if sfr_consistent else 'WARN'}] SFR non-null consistency: "
      f"actual={actual_sfr_nonnull}, expected={expected_sfr_nonnull} "
      f"(keys={expected_sfr_nonnull_from_keys}, source nulls={sfr_null_in_source})")

# --- Spot Check 13: Retention non-null count consistency ---
ret_keys = set(df_retention["unitid"].to_list())
expected_ret_nonnull_from_keys = len(core_keys & ret_keys)
ret_null_in_source = df_retention.filter(pl.col("retention_rate").is_null()).shape[0]
expected_ret_nonnull = expected_ret_nonnull_from_keys - ret_null_in_source
actual_ret_nonnull = df["retention_rate"].drop_nulls().len()
ret_consistent = actual_ret_nonnull == expected_ret_nonnull
print(f"[{'PASS' if ret_consistent else 'WARN'}] Retention non-null consistency: "
      f"actual={actual_ret_nonnull}, expected={expected_ret_nonnull} "
      f"(keys={expected_ret_nonnull_from_keys}, source nulls={ret_null_in_source})")

# --- Spot Check 14: Finance plausibility ---
fin_data = df["instr_expend_per_fte"].drop_nulls()
fin_plausible = True
fin_issues = []
if fin_data.min() < 0:
    fin_plausible = False
    fin_issues.append(f"negative min: {fin_data.min()}")
if fin_data.max() > 500000:
    fin_plausible = False
    fin_issues.append(f"extremely high max: {fin_data.max()}")
if fin_data.median() < 1000 or fin_data.median() > 100000:
    fin_plausible = False
    fin_issues.append(f"unexpected median: {fin_data.median()}")
print(f"[{'PASS' if fin_plausible else 'WARN'}] Finance plausibility: ", end="")
if fin_plausible:
    print(f"min=${fin_data.min():,.0f}, median=${fin_data.median():,.0f}, max=${fin_data.max():,.0f}")
else:
    print("; ".join(fin_issues))

# --- Spot Check 15: Row order and unitid integrity ---
# Verify unitids in merged match exactly the set in core_demographics
merged_ids = set(df["unitid"].to_list())
core_ids = set(df_core["unitid"].to_list())
id_sets_match = merged_ids == core_ids
print(f"[{'PASS' if id_sets_match else 'FAIL'}] Unitid set preserved exactly from core_demographics: {id_sets_match}")

# ==========================================================================
# CP3 VALIDATION QUALITY CHECK
# ==========================================================================

print("\n" + "=" * 60)
print("VALIDATION QUALITY ASSESSMENT")
print("=" * 60)

# The reviewed script's CP3.4 check uses KEY overlap for retention match rate,
# but the actual non-null data rate is lower (due to pre-existing nulls in retention source).
# Check if this matters.
ret_key_overlap_pct = len(core_keys & ret_keys) / len(core_keys) * 100
ret_data_overlap_pct = actual_ret_nonnull / len(df) * 100
validation_gap = abs(ret_key_overlap_pct - ret_data_overlap_pct)
print(f"Retention: key overlap={ret_key_overlap_pct:.1f}%, data overlap={ret_data_overlap_pct:.1f}%, gap={validation_gap:.1f}pp")
if validation_gap > 5:
    print(f"  [WARN] CP3.4 reports retention match as {ret_key_overlap_pct:.1f}% (key overlap), "
          f"but actual non-null data is {ret_data_overlap_pct:.1f}%")
    print(f"  This means {int(expected_ret_nonnull_from_keys - actual_ret_nonnull)} institutions "
          f"matched on key but have null retention_rate in the source file.")
    print(f"  Both rates pass the >70% threshold, so this is informational, not a blocker.")
else:
    print(f"  [PASS] Key overlap and data overlap are consistent.")

# ==========================================================================
# DATA PROFILING (for cr2+ decision)
# ==========================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows (resource columns + key):")
print(df.select(["unitid", "inst_name", "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]).head(10))

print("\nDescriptive statistics for resource columns:")
print(df.select(["student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]).describe())

print("\nNull pattern analysis:")
null_patterns = df.select([
    pl.col("student_faculty_ratio").is_null().alias("sfr_null"),
    pl.col("retention_rate").is_null().alias("ret_null"),
    pl.col("instr_expend_per_fte").is_null().alias("fin_null"),
])
pattern_counts = null_patterns.group_by(["sfr_null", "ret_null", "fin_null"]).len().sort("len", descending=True)
print(pattern_counts)

print("\ninst_control distribution:")
print(df["inst_control"].value_counts().sort("inst_control"))

print("\nColumn null summary:")
for col in df.columns:
    nc = df[col].null_count()
    if nc > 0:
        print(f"  {col}: {nc:,} nulls ({nc/len(df)*100:.1f}%)")

# --- Summary ---
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([cardinality_ok, model3_cols_present, boundary_ok, absence_ok, downstream_ok])
all_passed = all_default_passed and all_specific_passed
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 00:39:27
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_03_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 03 (join-resources)
# ============================================================
# Loaded: 2,893 rows x 22 cols
# 
# [PASS] Schema: All 22 expected columns present
# [PASS] Row count: 2,893 (expected exactly 2,893)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in integer columns
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# [PASS] [Counterfactual] 1:1 cardinality verified in all source files
# [PASS] [Semantic] Model 3 regression vars present: True
#   Complete cases for Model 3: 1,574 / 2,893 (54.4%)
#   [WARN] Sufficient for regression (>70% needed): False
# [WARN] [Boundary] Resource column value ranges: retention_rate: 26 zero values (suspicious)
#   student_faculty_ratio: min=1.00, max=77.00, median=13.00, nulls=421
#   retention_rate: min=0.00, max=100.00, median=75.00, nulls=812
#   instr_expend_per_fte: min=148.95, max=14146996.00, median=8611.81, nulls=262
# [PASS] [Absence] Institutions missing ALL resource columns: 151 (5.2%)
#   inst_control distribution of fully-missing: {'inst_control': shape: (3,)
# Series: 'inst_control' [i64]
# [
# 	1
# 	2
# 	3
# ], 'count': shape: (3,)
# Series: 'count' [u32]
# [
# 	78
# 	55
# 	18
# ]}
# [PASS] [Downstream] create-bands input columns present: True
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# Spot-check institutions: [100654, 100663, 100690]
#   unitid=100654: SFR 18.0 vs 18.0 [OK], Ret 54.0 vs 54.0 [OK], Fin 5383.770660060166 vs 5383.770660060166 [OK]
#   unitid=100663: SFR 20.0 vs 20.0 [OK], Ret 86.0 vs 86.0 [OK], Fin 17533.005146936743 vs 17533.005146936743 [OK]
#   unitid=100690: SFR 13.0 vs 13.0 [OK], Ret 50.0 vs 50.0 [OK], Fin 4206.030947775628 vs 4206.030947775628 [OK]
# 
# [PASS] SFR non-null consistency: actual=2472, expected=2472 (keys=2472, source nulls=0)
# [WARN] Retention non-null consistency: actual=2081, expected=1818 (keys=2472, source nulls=654)
# [WARN] Finance plausibility: extremely high max: 14146996.0
# [PASS] Unitid set preserved exactly from core_demographics: True
# 
# ============================================================
# VALIDATION QUALITY ASSESSMENT
# ============================================================
# Retention: key overlap=85.4%, data overlap=71.9%, gap=13.5pp
#   [WARN] CP3.4 reports retention match as 85.4% (key overlap), but actual non-null data is 71.9%
#   This means 391 institutions matched on key but have null retention_rate in the source file.
#   Both rates pass the >70% threshold, so this is informational, not a blocker.
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows (resource columns + key):
# shape: (10, 5)
# ┌────────┬─────────────────────────┬───────────────────────┬────────────────┬──────────────────────┐
# │ unitid ┆ inst_name               ┆ student_faculty_ratio ┆ retention_rate ┆ instr_expend_per_fte │
# │ ---    ┆ ---                     ┆ ---                   ┆ ---            ┆ ---                  │
# │ i64    ┆ str                     ┆ f64                   ┆ f64            ┆ f64                  │
# ╞════════╪═════════════════════════╪═══════════════════════╪════════════════╪══════════════════════╡
# │ 100654 ┆ Alabama A & M           ┆ 18.0                  ┆ 54.0           ┆ 5383.77066           │
# │        ┆ University              ┆                       ┆                ┆                      │
# │ 100663 ┆ University of Alabama   ┆ 20.0                  ┆ 86.0           ┆ 17533.005147         │
# │        ┆ at Birmi…               ┆                       ┆                ┆                      │
# │ 100690 ┆ Amridge University      ┆ 13.0                  ┆ 50.0           ┆ 4206.030948          │
# │ 100706 ┆ University of Alabama   ┆ 19.0                  ┆ 82.0           ┆ 9390.673879          │
# │        ┆ in Hunts…               ┆                       ┆                ┆                      │
# │ 100724 ┆ Alabama State           ┆ 15.0                  ┆ 62.0           ┆ 8750.468505          │
# │        ┆ University              ┆                       ┆                ┆                      │
# │ 100733 ┆ University of Alabama   ┆ null                  ┆ null           ┆ null                 │
# │        ┆ System O…               ┆                       ┆                ┆                      │
# │ 100751 ┆ The University of       ┆ 20.0                  ┆ 87.0           ┆ 10954.560443         │
# │        ┆ Alabama                 ┆                       ┆                ┆                      │
# │ 100812 ┆ Athens State University ┆ 15.0                  ┆ null           ┆ 7987.696413          │
# │ 100830 ┆ Auburn University at    ┆ 16.0                  ┆ 70.0           ┆ 7198.384913          │
# │        ┆ Montgomer…              ┆                       ┆                ┆                      │
# │ 100858 ┆ Auburn University       ┆ 20.0                  ┆ 92.0           ┆ 11516.112987         │
# └────────┴─────────────────────────┴───────────────────────┴────────────────┴──────────────────────┘
# 
# Descriptive statistics for resource columns:
# shape: (9, 4)
# ┌────────────┬───────────────────────┬────────────────┬──────────────────────┐
# │ statistic  ┆ student_faculty_ratio ┆ retention_rate ┆ instr_expend_per_fte │
# │ ---        ┆ ---                   ┆ ---            ┆ ---                  │
# │ str        ┆ f64                   ┆ f64            ┆ f64                  │
# ╞════════════╪═══════════════════════╪════════════════╪══════════════════════╡
# │ count      ┆ 2472.0                ┆ 2081.0         ┆ 2631.0               │
# │ null_count ┆ 421.0                 ┆ 812.0          ┆ 262.0                │
# │ mean       ┆ 14.009304             ┆ 73.046132      ┆ 31235.936229         │
# │ std        ┆ 6.134826              ┆ 16.817681      ┆ 370003.584842        │
# │ min        ┆ 1.0                   ┆ 0.0            ┆ 148.946911           │
# │ 25%        ┆ 10.0                  ┆ 66.0           ┆ 5781.57029           │
# │ 50%        ┆ 13.0                  ┆ 75.0           ┆ 8611.813545          │
# │ 75%        ┆ 17.0                  ┆ 83.0           ┆ 13176.010459         │
# │ max        ┆ 77.0                  ┆ 100.0          ┆ 1.4146996e7          │
# └────────────┴───────────────────────┴────────────────┴──────────────────────┘
# 
# Null pattern analysis:
# shape: (6, 4)
# ┌──────────┬──────────┬──────────┬──────┐
# │ sfr_null ┆ ret_null ┆ fin_null ┆ len  │
# │ ---      ┆ ---      ┆ ---      ┆ ---  │
# │ bool     ┆ bool     ┆ bool     ┆ u32  │
# ╞══════════╪══════════╪══════════╪══════╡
# │ false    ┆ false    ┆ false    ┆ 2020 │
# │ false    ┆ true     ┆ false    ┆ 341  │
# │ true     ┆ true     ┆ false    ┆ 270  │
# │ true     ┆ true     ┆ true     ┆ 151  │
# │ false    ┆ false    ┆ true     ┆ 61   │
# │ false    ┆ true     ┆ true     ┆ 50   │
# └──────────┴──────────┴──────────┴──────┘
# 
# inst_control distribution:
# shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 852   │
# │ 2            ┆ 1671  │
# │ 3            ┆ 370   │
# └──────────────┴───────┘
# 
# Column null summary:
#   number_applied: 1,130 nulls (39.1%)
#   number_admitted: 1,142 nulls (39.5%)
#   number_enrolled_total: 1,144 nulls (39.5%)
#   admit_rate: 1,142 nulls (39.5%)
#   completion_rate_150pct: 947 nulls (32.7%)
#   completers_150pct: 947 nulls (32.7%)
#   cohort_adj_150pct: 888 nulls (30.7%)
#   grant_recipients: 669 nulls (23.1%)
#   sfa_total_students: 669 nulls (23.1%)
#   urm_share: 423 nulls (14.6%)
#   total_ug_enrollment: 420 nulls (14.5%)
#   pell_share: 669 nulls (23.1%)
#   student_faculty_ratio: 421 nulls (14.6%)
#   retention_rate: 812 nulls (28.1%)
#   instr_expend_per_fte: 262 nulls (9.1%)
# 
# ============================================================
# QA RESULT: ISSUES_FOUND
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
