#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 01

Reviewed script: scripts/stage7_transform/01_join-core.py
Output files: data/processed/2026-03-29_core.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] Verify LEFT join preserved all directory rows even if right sides had 0 overlap
7. [Semantic] Verify output serves research question - admit_rate and completion_rate_150pct both present and usable
8. [Boundary] Check for boundary values in admit_rate (0, 100) and completion_rate_150pct (0, 100)
9. [Absence] Verify no directory columns were lost during join (column clobbering)
10. [Downstream] Verify unitid uniqueness is preserved for downstream joins

Spot-Checks:
11. Trace specific institutions through the join
12. Verify null patterns match key overlap discrepancies
13. Cross-check inst_control distribution against expected sector composition
14. Verify open_public institutions have expected admit_rate patterns
15. Check that admit_rate values are consistent with number_applied/number_admitted
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core.parquet"
INPUT_DIRECTORY = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_directory_clean.parquet"
INPUT_ADMISSIONS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_admissions_clean.parquet"
INPUT_GRAD_RATES = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"

EXPECTED_COLUMNS = [
    "unitid", "inst_name", "fips", "inst_control", "open_public",
    "hbcu", "tribal_college", "number_applied", "number_admitted",
    "number_enrolled_total", "admit_rate", "completion_rate_150pct",
]
EXPECTED_MIN_ROWS = 2893
EXPECTED_MAX_ROWS = 2893
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 01 (join-core)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Load input files for cross-reference
df_dir = pl.read_parquet(INPUT_DIRECTORY)
df_adm = pl.read_parquet(INPUT_ADMISSIONS)
df_grad = pl.read_parquet(INPUT_GRAD_RATES)
print(f"Directory input: {df_dir.shape[0]:,} rows x {df_dir.shape[1]} cols")
print(f"Admissions input: {df_adm.shape[0]:,} rows x {df_adm.shape[1]} cols")
print(f"Grad rates input: {df_grad.shape[0]:,} rows x {df_grad.shape[1]} cols")

# === DEFAULT CHECKS ===

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
    print(f"  Extra columns (not in Plan_Tasks.md verify block): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_MIN_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64, pl.Int32, pl.Int16, pl.Int8)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if col_data.dtype in [pl.Float64, pl.Float32]:
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
    print("None remain")
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

# === SCRIPT-SPECIFIC CHECKS (Five Lenses) ===

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] LEFT join row preservation ---
# INTENT: Verify that every single unitid from the directory is present in the output.
# A LEFT join should preserve 100% of left-side rows. If any are missing, the join
# silently dropped data.
dir_unitids = set(df_dir["unitid"].to_list())
core_unitids = set(df["unitid"].to_list())
missing_from_core = dir_unitids - core_unitids
extra_in_core = core_unitids - dir_unitids
counterfactual_ok = len(missing_from_core) == 0 and len(extra_in_core) == 0
print(f"\n[{'PASS' if counterfactual_ok else 'FAIL'}] [Counterfactual] LEFT join row preservation:")
print(f"  Directory unitids missing from core: {len(missing_from_core)}")
print(f"  Core unitids not in directory: {len(extra_in_core)}")

# --- Check 7: [Semantic] Research question columns are usable ---
# INTENT: The research question asks about selectivity (admit_rate) vs graduation rate
# (completion_rate_150pct). Verify that both are present AND that at least some
# institutions have BOTH non-null, enabling the core analysis.
both_present = (
    df.filter(
        pl.col("admit_rate").is_not_null() & pl.col("completion_rate_150pct").is_not_null()
    ).shape[0]
)
semantic_ok = both_present > 500
print(f"\n[{'PASS' if semantic_ok else 'FAIL'}] [Semantic] Institutions with both admit_rate AND completion_rate:")
print(f"  Count: {both_present:,} (need >500 for meaningful analysis)")
print(f"  Percentage of total: {both_present / len(df) * 100:.1f}%")

# --- Check 8: [Boundary] Value ranges for key analysis variables ---
# INTENT: admit_rate should be 0-100, completion_rate_150pct should be 0-100.
# Values outside these ranges indicate cleaning failures or join corruption.
boundary_issues = []
if "admit_rate" in df.columns:
    ar = df["admit_rate"].drop_nulls()
    if len(ar) > 0:
        ar_min = ar.min()
        ar_max = ar.max()
        if ar_min < 0 or ar_max > 100:
            boundary_issues.append(f"admit_rate out of [0,100]: [{ar_min}, {ar_max}]")
        # Check for exact 0 and exact 100
        n_zero = (ar == 0).sum()
        n_hundred = (ar == 100).sum()
        print(f"\n  admit_rate range: [{ar_min:.2f}, {ar_max:.2f}], zeros={n_zero}, hundreds={n_hundred}")

if "completion_rate_150pct" in df.columns:
    cr = df["completion_rate_150pct"].drop_nulls()
    if len(cr) > 0:
        cr_min = cr.min()
        cr_max = cr.max()
        if cr_min < 0 or cr_max > 100:
            boundary_issues.append(f"completion_rate_150pct out of [0,100]: [{cr_min}, {cr_max}]")
        n_zero_cr = (cr == 0).sum()
        n_hundred_cr = (cr == 100).sum()
        print(f"  completion_rate_150pct range: [{cr_min:.2f}, {cr_max:.2f}], zeros={n_zero_cr}, hundreds={n_hundred_cr}")

boundary_ok = len(boundary_issues) == 0
print(f"[{'PASS' if boundary_ok else 'FAIL'}] [Boundary] Value ranges: ", end="")
print("All within expected bounds" if boundary_ok else "; ".join(boundary_issues))

# --- Check 9: [Absence] Directory columns preserved through join ---
# INTENT: LEFT join can silently drop columns if there are name collisions between
# left and right datasets. Verify all directory-sourced columns survived.
dir_cols = df_dir.columns
dir_cols_in_core = [c for c in dir_cols if c in df.columns]
dir_cols_missing = [c for c in dir_cols if c not in df.columns]
absence_ok = len(dir_cols_missing) == 0
print(f"\n[{'PASS' if absence_ok else 'FAIL'}] [Absence] Directory columns preserved:")
print(f"  Present: {dir_cols_in_core}")
if dir_cols_missing:
    print(f"  MISSING: {dir_cols_missing}")

# --- Check 10: [Downstream] unitid uniqueness preserved ---
# INTENT: Downstream scripts (join-demographics, join-resources) will join on unitid.
# If unitid is not unique here, those joins will produce fan-out.
n_unique = df["unitid"].n_unique()
downstream_ok = n_unique == len(df)
print(f"\n[{'PASS' if downstream_ok else 'FAIL'}] [Downstream] unitid uniqueness: {n_unique:,} unique / {len(df):,} rows")

# === SPOT-CHECKS ===

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Trace specific institutions ---
# INTENT: Pick known institutions and verify their data survived the join correctly.
# Using first 3 unitids from directory to trace through.
sample_ids = df_dir["unitid"].head(3).to_list()
print(f"\nSpot-check: Tracing unitids {sample_ids} through join")
for uid in sample_ids:
    dir_row = df_dir.filter(pl.col("unitid") == uid)
    core_row = df.filter(pl.col("unitid") == uid)
    adm_row = df_adm.filter(pl.col("unitid") == uid)
    grad_row = df_grad.filter(pl.col("unitid") == uid)

    dir_name = dir_row["inst_name"][0] if len(dir_row) > 0 else "NOT FOUND"
    core_name = core_row["inst_name"][0] if len(core_row) > 0 else "NOT FOUND"
    has_adm = len(adm_row) > 0
    has_grad = len(grad_row) > 0
    core_adm_null = core_row["admit_rate"].is_null()[0] if len(core_row) > 0 else None
    core_grad_null = core_row["completion_rate_150pct"].is_null()[0] if len(core_row) > 0 else None

    name_match = dir_name == core_name
    adm_consistent = (has_adm and not core_adm_null) or (not has_adm and core_adm_null)
    grad_consistent = (has_grad and not core_grad_null) or (not has_grad and core_grad_null)

    print(f"  unitid={uid}: name_match={name_match}, adm_in_source={has_adm}, "
          f"adm_null_in_core={core_adm_null}, grad_in_source={has_grad}, "
          f"grad_null_in_core={core_grad_null}")

# --- Spot-Check 12: Null pattern verification ---
# INTENT: The execution log showed key overlap of 1,763 for admissions but only
# 1,751 non-null admit_rate values. This 12-institution discrepancy could indicate
# that some admissions records had null admit_rate BEFORE the join. Verify.
adm_null_in_source = df_adm.filter(pl.col("admit_rate").is_null()).shape[0]
grad_null_in_source = df_grad.filter(pl.col("completion_rate_150pct").is_null()).shape[0]
print(f"\nNull pattern verification:")
print(f"  Admissions records with null admit_rate in source: {adm_null_in_source}")
print(f"  Grad rate records with null completion_rate_150pct in source: {grad_null_in_source}")

# Expected null count in core:
# = (directory rows - key overlap) + (source records with null in the variable)
dir_keys = set(df_dir["unitid"].to_list())
adm_keys = set(df_adm["unitid"].to_list())
grad_keys = set(df_grad["unitid"].to_list())
key_overlap_adm = len(dir_keys & adm_keys)
key_overlap_grad = len(dir_keys & grad_keys)

# Null admit_rate in admissions source that matched directory
adm_matched_null = df_adm.filter(
    pl.col("unitid").is_in(list(dir_keys)) & pl.col("admit_rate").is_null()
).shape[0]
grad_matched_null = df_grad.filter(
    pl.col("unitid").is_in(list(dir_keys)) & pl.col("completion_rate_150pct").is_null()
).shape[0]

expected_core_adm_null = (len(df) - key_overlap_adm) + adm_matched_null
expected_core_grad_null = (len(df) - key_overlap_grad) + grad_matched_null
actual_core_adm_null = df["admit_rate"].null_count()
actual_core_grad_null = df["completion_rate_150pct"].null_count()

print(f"  Expected admit_rate nulls in core: {expected_core_adm_null} (unmatched: {len(df) - key_overlap_adm}, source null: {adm_matched_null})")
print(f"  Actual admit_rate nulls in core: {actual_core_adm_null}")
print(f"  Match: {expected_core_adm_null == actual_core_adm_null}")
print(f"  Expected completion_rate_150pct nulls in core: {expected_core_grad_null} (unmatched: {len(df) - key_overlap_grad}, source null: {grad_matched_null})")
print(f"  Actual completion_rate_150pct nulls in core: {actual_core_grad_null}")
print(f"  Match: {expected_core_grad_null == actual_core_grad_null}")

# --- Spot-Check 13: inst_control distribution ---
# INTENT: Verify sector composition is plausible for 4-year institutions.
# Expected: majority public and private nonprofit, few for-profit.
print(f"\ninst_control distribution:")
ic_dist = df["inst_control"].value_counts().sort("inst_control")
for row in ic_dist.iter_rows():
    val, count = row[0], row[1]
    label = {1: "Public", 2: "Private nonprofit", 3: "Private for-profit"}.get(val, f"Unknown({val})")
    pct = count / len(df) * 100
    print(f"  {val} ({label}): {count:,} ({pct:.1f}%)")

# --- Spot-Check 14: open_public and admit_rate consistency ---
# INTENT: Open admissions institutions (open_public=1) may or may not report
# admit_rate data. Check the pattern.
open_inst = df.filter(pl.col("open_public") == 1)
open_with_ar = open_inst.filter(pl.col("admit_rate").is_not_null()).shape[0]
open_without_ar = open_inst.filter(pl.col("admit_rate").is_null()).shape[0]
print(f"\nOpen admissions (open_public=1): {len(open_inst):,} institutions")
print(f"  With admit_rate: {open_with_ar}")
print(f"  Without admit_rate (null): {open_without_ar}")
if open_with_ar > 0:
    open_ar_mean = open_inst.filter(pl.col("admit_rate").is_not_null())["admit_rate"].mean()
    print(f"  Mean admit_rate among those reporting: {open_ar_mean:.1f}%")

# --- Spot-Check 15: admit_rate consistency with components ---
# INTENT: Verify that admit_rate = number_admitted / number_applied * 100.
# If these columns are present, recalculate and compare.
if all(c in df.columns for c in ["admit_rate", "number_applied", "number_admitted"]):
    check_df = df.filter(
        pl.col("admit_rate").is_not_null()
        & pl.col("number_applied").is_not_null()
        & pl.col("number_admitted").is_not_null()
        & (pl.col("number_applied") > 0)
    )
    if len(check_df) > 0:
        recalc = check_df.with_columns(
            (pl.col("number_admitted") / pl.col("number_applied") * 100).alias("recalc_ar")
        )
        diff = (recalc["admit_rate"] - recalc["recalc_ar"]).abs()
        max_diff = diff.max()
        mean_diff = diff.mean()
        n_exact = (diff < 0.01).sum()
        print(f"\nadmit_rate recalculation check ({len(check_df):,} institutions):")
        print(f"  Max absolute difference: {max_diff:.4f}")
        print(f"  Mean absolute difference: {mean_diff:.4f}")
        print(f"  Exact matches (within 0.01): {n_exact:,} / {len(check_df):,}")

# === SUMMARY ===
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([counterfactual_ok, semantic_ok, boundary_ok, absence_ok, downstream_ok])
all_passed = all_default_passed and all_specific_passed

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nNull counts per column:")
for col in df.columns:
    nc = df[col].null_count()
    pct = nc / len(df) * 100
    print(f"  {col}: {nc:,} ({pct:.1f}%)")

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col} (first 20):")
        print(df[col].value_counts().head(20))

print("\nColumn dtypes:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 00:15:49
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 01 (join-core)
# ============================================================
# Loaded output: 2,893 rows x 14 cols
# Directory input: 2,893 rows x 7 cols
# Admissions input: 1,989 rows x 5 cols
# Grad rates input: 2,010 rows x 4 cols
# 
# [PASS] Schema: All expected columns present
#   Extra columns (not in Plan_Tasks.md verify block): ['completers_150pct', 'cohort_adj_150pct']
# [PASS] Row count: 2,893 (expected exactly 2,893)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] [Counterfactual] LEFT join row preservation:
#   Directory unitids missing from core: 0
#   Core unitids not in directory: 0
# 
# [PASS] [Semantic] Institutions with both admit_rate AND completion_rate:
#   Count: 1,625 (need >500 for meaningful analysis)
#   Percentage of total: 56.2%
# 
#   admit_rate range: [0.00, 100.00], zeros=2, hundreds=54
#   completion_rate_150pct range: [3.80, 100.00], zeros=0, hundreds=40
# [PASS] [Boundary] Value ranges: All within expected bounds
# 
# [PASS] [Absence] Directory columns preserved:
#   Present: ['unitid', 'inst_name', 'fips', 'inst_control', 'open_public', 'hbcu', 'tribal_college']
# 
# [PASS] [Downstream] unitid uniqueness: 2,893 unique / 2,893 rows
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-check: Tracing unitids [100654, 100663, 100690] through join
#   unitid=100654: name_match=True, adm_in_source=True, adm_null_in_core=False, grad_in_source=True, grad_null_in_core=False
#   unitid=100663: name_match=True, adm_in_source=True, adm_null_in_core=False, grad_in_source=True, grad_null_in_core=False
#   unitid=100690: name_match=True, adm_in_source=False, adm_null_in_core=True, grad_in_source=True, grad_null_in_core=False
# 
# Null pattern verification:
#   Admissions records with null admit_rate in source: 23
#   Grad rate records with null completion_rate_150pct in source: 61
#   Expected admit_rate nulls in core: 1142 (unmatched: 1130, source null: 12)
#   Actual admit_rate nulls in core: 1142
#   Match: True
#   Expected completion_rate_150pct nulls in core: 947 (unmatched: 886, source null: 61)
#   Actual completion_rate_150pct nulls in core: 947
#   Match: True
# 
# inst_control distribution:
#   1 (Public): 852 (29.5%)
#   2 (Private nonprofit): 1,671 (57.8%)
#   3 (Private for-profit): 370 (12.8%)
# 
# Open admissions (open_public=1): 2,891 institutions
#   With admit_rate: 1751
#   Without admit_rate (null): 1140
#   Mean admit_rate among those reporting: 70.4%
# 
# admit_rate recalculation check (1,751 institutions):
#   Max absolute difference: 0.0000
#   Mean absolute difference: 0.0000
#   Exact matches (within 0.01): 1,751 / 1,751
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 14)
# ┌────────┬─────────────┬──────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ inst_name   ┆ fips ┆ inst_contr ┆ … ┆ admit_rate ┆ completion ┆ completers ┆ cohort_adj │
# │ ---    ┆ ---         ┆ ---  ┆ ol         ┆   ┆ ---        ┆ _rate_150p ┆ _150pct    ┆ _150pct    │
# │ i64    ┆ str         ┆ i64  ┆ ---        ┆   ┆ f64        ┆ ct         ┆ ---        ┆ ---        │
# │        ┆             ┆      ┆ i64        ┆   ┆            ┆ ---        ┆ i64        ┆ i64        │
# │        ┆             ┆      ┆            ┆   ┆            ┆ f64        ┆            ┆            │
# ╞════════╪═════════════╪══════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ Alabama A & ┆ 1    ┆ 1          ┆ … ┆ 89.649924  ┆ 28.1       ┆ 343        ┆ 1222       │
# │        ┆ M           ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100663 ┆ University  ┆ 1    ┆ 1          ┆ … ┆ 80.598595  ┆ 62.4       ┆ 991        ┆ 1587       │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ at Birmi…   ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100690 ┆ Amridge     ┆ 1    ┆ 2          ┆ … ┆ null       ┆ 66.7       ┆ 4          ┆ 6          │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100706 ┆ University  ┆ 1    ┆ 1          ┆ … ┆ 77.110306  ┆ 60.7       ┆ 623        ┆ 1026       │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ in Hunts…   ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100724 ┆ Alabama     ┆ 1    ┆ 1          ┆ … ┆ 98.875765  ┆ 28.4       ┆ 286        ┆ 1006       │
# │        ┆ State       ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100733 ┆ University  ┆ 1    ┆ 1          ┆ … ┆ null       ┆ null       ┆ null       ┆ null       │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ System O…   ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100751 ┆ The         ┆ 1    ┆ 1          ┆ … ┆ 80.394338  ┆ 72.2       ┆ 5178       ┆ 7169       │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100812 ┆ Athens      ┆ 1    ┆ 1          ┆ … ┆ null       ┆ null       ┆ null       ┆ null       │
# │        ┆ State       ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100830 ┆ Auburn      ┆ 1    ┆ 1          ┆ … ┆ 95.549284  ┆ 35.7       ┆ 202        ┆ 566        │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ at          ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ Montgomer…  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100858 ┆ Auburn      ┆ 1    ┆ 1          ┆ … ┆ 85.06631   ┆ 80.9       ┆ 3921       ┆ 4848       │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# └────────┴─────────────┴──────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 15)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ unitid    ┆ inst_name ┆ fips      ┆ … ┆ admit_rat ┆ completio ┆ completer ┆ cohort_a │
# │ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ e         ┆ n_rate_15 ┆ s_150pct  ┆ dj_150pc │
# │ str       ┆ f64       ┆ str       ┆ f64       ┆   ┆ ---       ┆ 0pct      ┆ ---       ┆ t        │
# │           ┆           ┆           ┆           ┆   ┆ f64       ┆ ---       ┆ f64       ┆ ---      │
# │           ┆           ┆           ┆           ┆   ┆           ┆ f64       ┆           ┆ f64      │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 2893.0    ┆ 2893      ┆ 2893.0    ┆ … ┆ 1751.0    ┆ 1946.0    ┆ 1946.0    ┆ 2005.0   │
# │ null_coun ┆ 0.0       ┆ 0         ┆ 0.0       ┆ … ┆ 1142.0    ┆ 947.0     ┆ 947.0     ┆ 888.0    │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ 240022.82 ┆ null      ┆ 29.891808 ┆ … ┆ 70.401689 ┆ 55.555498 ┆ 508.86844 ┆ 764.7725 │
# │           ┆ 6823      ┆           ┆           ┆   ┆           ┆           ┆ 8         ┆ 69       │
# │ std       ┆ 119303.32 ┆ null      ┆ 17.0178   ┆ … ┆ 21.040067 ┆ 20.53858  ┆ 938.05143 ┆ 1240.120 │
# │           ┆ 3702      ┆           ┆           ┆   ┆           ┆           ┆ 5         ┆ 273      │
# │ min       ┆ 100654.0  ┆ A T Still ┆ 1.0       ┆ … ┆ 0.0       ┆ 3.8       ┆ 1.0       ┆ 1.0      │
# │           ┆           ┆ Universit ┆           ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆ y of      ┆           ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆ Health…   ┆           ┆   ┆           ┆           ┆           ┆          │
# │ 25%       ┆ 157447.0  ┆ null      ┆ 15.0      ┆ … ┆ 59.245057 ┆ 41.6      ┆ 44.0      ┆ 89.0     │
# │ 50%       ┆ 200697.0  ┆ null      ┆ 31.0      ┆ … ┆ 74.577453 ┆ 56.2      ┆ 182.0     ┆ 334.0    │
# │ 75%       ┆ 240462.0  ┆ null      ┆ 42.0      ┆ … ┆ 85.93577  ┆ 69.5      ┆ 506.0     ┆ 808.0    │
# │ max       ┆ 496326.0  ┆ Zaytuna   ┆ 78.0      ┆ … ┆ 100.0     ┆ 100.0     ┆ 11142.0   ┆ 15327.0  │
# │           ┆           ┆ College   ┆           ┆   ┆           ┆           ┆           ┆          │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Null counts per column:
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
# 
# Key column value counts:
# 
# unitid (first 20):
# shape: (20, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ i64    ┆ u32   │
# ╞════════╪═══════╡
# │ 446048 ┆ 1     │
# │ 217633 ┆ 1     │
# │ 166683 ┆ 1     │
# │ 178244 ┆ 1     │
# │ 212106 ┆ 1     │
# │ …      ┆ …     │
# │ 102298 ┆ 1     │
# │ 494010 ┆ 1     │
# │ 236072 ┆ 1     │
# │ 216010 ┆ 1     │
# │ 251312 ┆ 1     │
# └────────┴───────┘
# 
# inst_name (first 20):
# shape: (20, 2)
# ┌────────────────────────────────┬───────┐
# │ inst_name                      ┆ count │
# │ ---                            ┆ ---   │
# │ str                            ┆ u32   │
# ╞════════════════════════════════╪═══════╡
# │ Lincoln College                ┆ 1     │
# │ Los Angeles Pacific University ┆ 1     │
# │ Claremont Lincoln University   ┆ 1     │
# │ Friends University             ┆ 1     │
# │ Hesston College                ┆ 1     │
# │ …                              ┆ …     │
# │ Rutgers University-Newark      ┆ 1     │
# │ Greensboro College             ┆ 1     │
# │ Southern Methodist University  ┆ 1     │
# │ DePauw University              ┆ 1     │
# │ Illinois College               ┆ 1     │
# └────────────────────────────────┴───────┘
# 
# inst_control (first 20):
# shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 3            ┆ 370   │
# │ 2            ┆ 1671  │
# │ 1            ┆ 852   │
# └──────────────┴───────┘
# 
# Column dtypes:
#   unitid: Int64
#   inst_name: String
#   fips: Int64
#   inst_control: Int64
#   open_public: Int64
#   hbcu: Int64
#   tribal_college: Int64
#   number_applied: Int64
#   number_admitted: Int64
#   number_enrolled_total: Int64
#   admit_rate: Float64
#   completion_rate_150pct: Float64
#   completers_150pct: Int64
#   cohort_adj_150pct: Int64
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
