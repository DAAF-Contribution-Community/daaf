#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 02
Reviewed script: scripts/stage7_transform/02_join-demographics.py
Output files: data/processed/2026-02-15_core_demographics.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns (that should never be null)
--- Script-specific checks (Five Lenses) ---
6. Counterfactual: What if enrollment_race had duplicates? Verify no fan-out residue
7. Semantic: Does urm_share actually enable answering the research question?
8. Boundary: Check urm_share=0 and urm_share=1 institutions — are they plausible?
9. Absence: Are there core columns missing that downstream expects?
10. Downstream: Will join-resources (next script) find what it needs?
--- Spot-checks ---
11. Trace a known HBCU — should have high urm_share
12. Verify urm_share null institutions are exactly the non-overlapping keys
13. Recalculate urm_share for one institution from raw enrollment data
14. Verify no duplicate unitids in output
15. Check urm_enrollment is consistent with urm_share (share = urm / total)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_core_demographics.parquet"
INPUT_CORE = PROJECT_DIR / "data" / "processed" / "2026-02-15_core_joined.parquet"
INPUT_ENROLLMENT = PROJECT_DIR / "data" / "processed" / "2026-02-15_enrollment_race_clean.parquet"

EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "inst_control", "institution_level",
    "hbcu", "degree_granting", "urban_centric_locale", "state_abbr", "fips",
    "grad_rate_150pct", "cohort_year", "number_applied", "number_admitted",
    "number_enrolled_total", "admission_rate", "pell_recipients",
    "enrollment_undergrad", "pell_share", "urm_share", "urm_enrollment"
]
EXPECTED_MIN_ROWS = 2528
EXPECTED_MAX_ROWS = 2528
# Critical columns for THIS join step — urm_share is allowed null (LEFT join);
# but unitid, grad_rate_150pct, pell_share must never be null.
CRITICAL_COLUMNS_NO_NULL = ["unitid", "grad_rate_150pct", "pell_share"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 02 — join-demographics")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

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
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls (columns that should NEVER be null) ---
null_issues = []
for col in CRITICAL_COLUMNS_NO_NULL:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =====================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# =====================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: Counterfactual — verify no fan-out residue ---
# If enrollment_race had duplicates, we'd see more rows than core.
# Also verify unitid uniqueness in output.
unitid_unique = df["unitid"].n_unique() == len(df)
print(f"\n[{'PASS' if unitid_unique else 'FAIL'}] Counterfactual (fan-out): unitid unique in output ({df['unitid'].n_unique():,} unique / {len(df):,} rows)")

# --- Check 7: Semantic — does urm_share enable the research question? ---
# Research question: "Are high graduation rates a signal of institutional quality,
# or primarily a reflection of admissions selectivity and student body demographics?"
# urm_share must have sufficient variance to test demographic effects.
urm_non_null = df.filter(pl.col("urm_share").is_not_null())
urm_std = urm_non_null["urm_share"].std() if len(urm_non_null) > 0 else 0
urm_has_variance = urm_std > 0.05  # need meaningful spread
print(f"[{'PASS' if urm_has_variance else 'FAIL'}] Semantic (variance): urm_share std={urm_std:.4f} (need >0.05 for meaningful analysis)")

# Check that urm_share is available for enough institutions to be useful
urm_coverage = len(urm_non_null) / len(df) if len(df) > 0 else 0
urm_coverage_ok = urm_coverage >= 0.70  # at least 70% coverage for robust analysis
print(f"[{'PASS' if urm_coverage_ok else 'WARN'}] Semantic (coverage): urm_share non-null for {len(urm_non_null):,}/{len(df):,} ({urm_coverage:.1%})")

# --- Check 8: Boundary — urm_share=0 and urm_share=1 ---
urm_zero = df.filter(pl.col("urm_share") == 0.0)
urm_one = df.filter(pl.col("urm_share") == 1.0)
print(f"\n[INFO] Boundary: urm_share=0.0 institutions: {len(urm_zero):,}")
if len(urm_zero) > 0:
    print(f"  Sample urm_share=0 institutions:")
    for row in urm_zero.head(3).iter_rows(named=True):
        print(f"    unitid={row['unitid']}, name={row['inst_name']}, enrollment_undergrad={row.get('enrollment_undergrad', 'N/A')}")

print(f"[INFO] Boundary: urm_share=1.0 institutions: {len(urm_one):,}")
if len(urm_one) > 0:
    print(f"  Sample urm_share=1 institutions:")
    for row in urm_one.head(3).iter_rows(named=True):
        print(f"    unitid={row['unitid']}, name={row['inst_name']}, hbcu={row.get('hbcu', 'N/A')}, urm_enrollment={row.get('urm_enrollment', 'N/A')}")

# Check: urm_share=1.0 means 100% URM — plausible for small institutions or HBCUs
boundary_plausible = True  # will assess from output
if len(urm_one) > 20:
    boundary_plausible = False  # suspicious if too many at exactly 1.0
    print(f"  [WARN] {len(urm_one)} institutions at urm_share=1.0 — seems high, investigate")
else:
    print(f"  [PASS] Boundary values plausible ({len(urm_one)} at 1.0)")

# --- Check 9: Absence — columns downstream expects ---
# join-resources (next script) needs: unitid + all current columns
# create-bands needs: urm_share for urm_band creation
downstream_needed = ["unitid", "grad_rate_150pct", "admission_rate", "pell_share", "urm_share",
                     "inst_control", "enrollment_undergrad", "inst_name"]
missing_downstream = [c for c in downstream_needed if c not in df.columns]
absence_ok = len(missing_downstream) == 0
print(f"\n[{'PASS' if absence_ok else 'FAIL'}] Absence: All downstream-needed columns present")
if missing_downstream:
    print(f"  Missing for downstream: {missing_downstream}")

# --- Check 10: Downstream — will join-resources find what it needs? ---
# join-resources joins on unitid with SFR and retention data.
# Verify unitid is well-formed (positive integer, no zeros).
unitid_positive = (df["unitid"] > 0).all()
print(f"[{'PASS' if unitid_positive else 'FAIL'}] Downstream: All unitids positive ({df['unitid'].min()} to {df['unitid'].max()})")

# =====================================================================
# SPOT-CHECKS
# =====================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: HBCUs should have high urm_share ---
hbcus = df.filter(pl.col("hbcu") == 1)
print(f"\n[INFO] HBCU spot-check: {len(hbcus):,} HBCUs in dataset")
if len(hbcus) > 0:
    hbcu_urm = hbcus.filter(pl.col("urm_share").is_not_null())
    if len(hbcu_urm) > 0:
        hbcu_mean_urm = hbcu_urm["urm_share"].mean()
        hbcu_check = hbcu_mean_urm > 0.50  # HBCUs should be majority URM
        print(f"  [{'PASS' if hbcu_check else 'FAIL'}] HBCU mean urm_share: {hbcu_mean_urm:.4f} (expect >0.50)")
        print(f"  HBCU urm_share range: {hbcu_urm['urm_share'].min():.4f} - {hbcu_urm['urm_share'].max():.4f}")
    else:
        print(f"  [WARN] All HBCUs have null urm_share")

# --- Spot-check 12: Null urm_share should be exactly the non-overlapping keys ---
df_core_raw = pl.read_parquet(INPUT_CORE)
df_enroll_raw = pl.read_parquet(INPUT_ENROLLMENT)
core_keys = set(df_core_raw["unitid"].to_list())
enroll_keys = set(df_enroll_raw["unitid"].to_list())
non_overlapping = core_keys - enroll_keys
urm_null_unitids = set(df.filter(pl.col("urm_share").is_null())["unitid"].to_list())

keys_match = non_overlapping == urm_null_unitids
print(f"\n[{'PASS' if keys_match else 'WARN'}] Null urm_share matches non-overlapping keys:")
print(f"  Non-overlapping core keys: {len(non_overlapping):,}")
print(f"  Null urm_share unitids: {len(urm_null_unitids):,}")
if not keys_match:
    extra_nulls = urm_null_unitids - non_overlapping
    missing_nulls = non_overlapping - urm_null_unitids
    if extra_nulls:
        print(f"  Extra nulls (in overlap but still null): {len(extra_nulls)}")
    if missing_nulls:
        print(f"  Missing nulls (not in overlap but not null): {len(missing_nulls)}")

# --- Spot-check 13: Recalculate urm_share for one institution ---
# Pick a known institution from enrollment_race and verify
sample_id = df_enroll_raw.head(1)["unitid"][0]
enroll_row = df_enroll_raw.filter(pl.col("unitid") == sample_id)
output_row = df.filter(pl.col("unitid") == sample_id)
print(f"\n[INFO] Recalculation spot-check for unitid={sample_id}:")
if len(enroll_row) > 0 and len(output_row) > 0:
    enroll_urm = enroll_row["urm_share"][0]
    output_urm = output_row["urm_share"][0]
    values_match = (enroll_urm is None and output_urm is None) or (enroll_urm is not None and output_urm is not None and abs(enroll_urm - output_urm) < 1e-10)
    print(f"  Enrollment source urm_share: {enroll_urm}")
    print(f"  Output urm_share: {output_urm}")
    print(f"  [{'PASS' if values_match else 'FAIL'}] Values match: {values_match}")
else:
    print(f"  [SKIP] Could not find unitid={sample_id} in both datasets")

# --- Spot-check 14: No duplicate unitids ---
dup_count = len(df) - df["unitid"].n_unique()
dup_ok = dup_count == 0
print(f"\n[{'PASS' if dup_ok else 'FAIL'}] No duplicate unitids: {dup_count} duplicates")

# --- Spot-check 15: urm_enrollment consistency with urm_share ---
# For non-null rows: urm_share should equal urm_enrollment / total_enrollment_race
# But total_enrollment_race was excluded from output. Check urm_enrollment is reasonable.
urm_enroll_non_null = df.filter(pl.col("urm_enrollment").is_not_null())
if len(urm_enroll_non_null) > 0:
    # urm_enrollment should be non-negative
    urm_enroll_nonneg = (urm_enroll_non_null["urm_enrollment"] >= 0).all()
    print(f"\n[{'PASS' if urm_enroll_nonneg else 'FAIL'}] urm_enrollment non-negative: {urm_enroll_nonneg}")
    # Cross-check: urm_enrollment where urm_share=0 should be 0
    zero_share = df.filter(pl.col("urm_share") == 0.0)
    if len(zero_share) > 0:
        zero_enroll_ok = (zero_share["urm_enrollment"] == 0).all()
        print(f"[{'PASS' if zero_enroll_ok else 'FAIL'}] urm_enrollment=0 where urm_share=0: {zero_enroll_ok}")
    # Cross-check: urm_enrollment > 0 where urm_share > 0
    pos_share = df.filter(pl.col("urm_share") > 0.0)
    if len(pos_share) > 0:
        pos_enroll_ok = (pos_share["urm_enrollment"] > 0).all()
        print(f"[{'PASS' if pos_enroll_ok else 'WARN'}] urm_enrollment>0 where urm_share>0: {pos_enroll_ok}")
else:
    print(f"\n[WARN] No non-null urm_enrollment values")

# =====================================================================
# DATA PROFILING (for cr2+ decision)
# =====================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows (key columns):")
print(df.select(["unitid", "inst_name", "grad_rate_150pct", "admission_rate",
                  "pell_share", "urm_share", "urm_enrollment", "hbcu"]).head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nurm_share distribution (deciles):")
urm_vals = df.filter(pl.col("urm_share").is_not_null())["urm_share"]
if len(urm_vals) > 0:
    for q in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        print(f"  {q:.0%}: {urm_vals.quantile(q):.4f}")

print("\nurm_share null rate by inst_control:")
print(df.group_by("inst_control").agg([
    pl.col("urm_share").null_count().alias("urm_null"),
    pl.len().alias("total"),
    (pl.col("urm_share").null_count() / pl.len()).alias("null_rate"),
]))

print(f"\nColumn null counts:")
for col in df.columns:
    nc = df[col].null_count()
    if nc > 0:
        print(f"  {col}: {nc:,} nulls ({nc/len(df):.1%})")

# --- Summary ---
all_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
                   unitid_unique, urm_has_variance, absence_ok, unitid_positive, dup_ok])
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:26:38
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_02_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 02 — join-demographics
# ============================================================
# Loaded: 2,528 rows x 21 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 2,528 (expected 2,528-2,528)
# [FAIL] Distributions: year: all same value (2020); institution_level: all same value (4); cohort_year: all same value (2015)
# [PASS] Coded values: None remain
# [FAIL] Critical nulls: grad_rate_150pct: 732 nulls; pell_share: 518 nulls
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] Counterfactual (fan-out): unitid unique in output (2,528 unique / 2,528 rows)
# [PASS] Semantic (variance): urm_share std=0.2512 (need >0.05 for meaningful analysis)
# [PASS] Semantic (coverage): urm_share non-null for 2,158/2,528 (85.4%)
# 
# [INFO] Boundary: urm_share=0.0 institutions: 105
#   Sample urm_share=0 institutions:
#     unitid=119058, name=Middlebury Institute of International Studies at Monterey, enrollment_undergrad=13
#     unitid=120166, name=Northwestern Polytechnic University, enrollment_undergrad=6
#     unitid=120838, name=Pacific States University, enrollment_undergrad=2
# [INFO] Boundary: urm_share=1.0 institutions: 41
#   Sample urm_share=1 institutions:
#     unitid=117283, name=Latin American Bible Institute, hbcu=0, urm_enrollment=60
#     unitid=155140, name=Haskell Indian Nations University, hbcu=0, urm_enrollment=731
#     unitid=199971, name=Carolina Christian College, hbcu=0, urm_enrollment=62
#   [WARN] 41 institutions at urm_share=1.0 — seems high, investigate
# 
# [PASS] Absence: All downstream-needed columns present
# [PASS] Downstream: All unitids positive (100654 to 496070)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [INFO] HBCU spot-check: 91 HBCUs in dataset
#   [PASS] HBCU mean urm_share: 0.8529 (expect >0.50)
#   HBCU urm_share range: 0.1074 - 1.0000
# 
# [PASS] Null urm_share matches non-overlapping keys:
#   Non-overlapping core keys: 370
#   Null urm_share unitids: 370
# 
# [INFO] Recalculation spot-check for unitid=110538:
#   Enrollment source urm_share: 0.3904870769035372
#   Output urm_share: 0.3904870769035372
#   [PASS] Values match: True
# 
# [PASS] No duplicate unitids: 0 duplicates
# 
# [PASS] urm_enrollment non-negative: True
# [PASS] urm_enrollment=0 where urm_share=0: True
# [PASS] urm_enrollment>0 where urm_share>0: True
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows (key columns):
# shape: (10, 8)
# ┌────────┬──────────────┬──────────────┬─────────────┬────────────┬───────────┬─────────────┬──────┐
# │ unitid ┆ inst_name    ┆ grad_rate_15 ┆ admission_r ┆ pell_share ┆ urm_share ┆ urm_enrollm ┆ hbcu │
# │ ---    ┆ ---          ┆ 0pct         ┆ ate         ┆ ---        ┆ ---       ┆ ent         ┆ ---  │
# │ i64    ┆ str          ┆ ---          ┆ ---         ┆ f64        ┆ f64       ┆ ---         ┆ i64  │
# │        ┆              ┆ f64          ┆ f64         ┆            ┆           ┆ i64         ┆      │
# ╞════════╪══════════════╪══════════════╪═════════════╪════════════╪═══════════╪═════════════╪══════╡
# │ 100654 ┆ Alabama A &  ┆ 28.1         ┆ 0.896499    ┆ 0.708227   ┆ 0.916552  ┆ 4668        ┆ 1    │
# │        ┆ M University ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100663 ┆ University   ┆ 62.4         ┆ 0.805986    ┆ 0.357833   ┆ 0.301845  ┆ 4189        ┆ 0    │
# │        ┆ of Alabama   ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ at Birmi…    ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100690 ┆ Amridge      ┆ 66.7         ┆ null        ┆ 0.90604    ┆ 0.718121  ┆ 214         ┆ 0    │
# │        ┆ University   ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100706 ┆ University   ┆ 60.7         ┆ 0.771103    ┆ 0.255139   ┆ 0.159836  ┆ 1283        ┆ 0    │
# │        ┆ of Alabama   ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ in Hunts…    ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100724 ┆ Alabama      ┆ 28.4         ┆ 0.988758    ┆ 0.68207    ┆ 0.941063  ┆ 3401        ┆ 1    │
# │        ┆ State        ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ University   ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100733 ┆ University   ┆ null         ┆ null        ┆ null       ┆ null      ┆ null        ┆ 0    │
# │        ┆ of Alabama   ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ System O…    ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100751 ┆ The          ┆ 72.2         ┆ 0.803943    ┆ 0.182033   ┆ 0.158952  ┆ 5034        ┆ 0    │
# │        ┆ University   ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ of Alabama   ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100812 ┆ Athens State ┆ null         ┆ null        ┆ 0.503348   ┆ 0.18006   ┆ 484         ┆ 0    │
# │        ┆ University   ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100830 ┆ Auburn       ┆ 35.7         ┆ 0.955493    ┆ 0.519314   ┆ 0.462629  ┆ 2024        ┆ 0    │
# │        ┆ University   ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ at           ┆              ┆             ┆            ┆           ┆             ┆      │
# │        ┆ Montgomer…   ┆              ┆             ┆            ┆           ┆             ┆      │
# │ 100858 ┆ Auburn       ┆ 80.9         ┆ 0.850663    ┆ 0.13736    ┆ 0.084636  ┆ 2074        ┆ 0    │
# │        ┆ University   ┆              ┆             ┆            ┆           ┆             ┆      │
# └────────┴──────────────┴──────────────┴─────────────┴────────────┴───────────┴─────────────┴──────┘
# 
# Descriptive statistics:
# shape: (9, 22)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ inst_name ┆ … ┆ enrollmen ┆ pell_shar ┆ urm_share ┆ urm_enrol │
# │ ---        ┆ ---        ┆ ---    ┆ ---       ┆   ┆ t_undergr ┆ e         ┆ ---       ┆ lment     │
# │ str        ┆ f64        ┆ f64    ┆ str       ┆   ┆ ad        ┆ ---       ┆ f64       ┆ ---       │
# │            ┆            ┆        ┆           ┆   ┆ ---       ┆ f64       ┆           ┆ f64       │
# │            ┆            ┆        ┆           ┆   ┆ f64       ┆           ┆           ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 2528.0     ┆ 2528.0 ┆ 2528      ┆ … ┆ 2158.0    ┆ 2010.0    ┆ 2158.0    ┆ 2158.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0         ┆ … ┆ 370.0     ┆ 518.0     ┆ 370.0     ┆ 370.0     │
# │ mean       ┆ 220569.164 ┆ 2020.0 ┆ null      ┆ … ┆ 4870.7854 ┆ 0.402658  ┆ 0.293667  ┆ 1471.0588 │
# │            ┆ 161        ┆        ┆           ┆   ┆ 49        ┆           ┆           ┆ 51        │
# │ std        ┆ 103707.401 ┆ 0.0    ┆ null      ┆ … ┆ 8536.2946 ┆ 0.197233  ┆ 0.25124   ┆ 3373.5912 │
# │            ┆ 134        ┆        ┆           ┆   ┆ 77        ┆           ┆           ┆ 06        │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ A T Still ┆ … ┆ 2.0       ┆ 0.0       ┆ 0.0       ┆ 0.0       │
# │            ┆            ┆        ┆ Universit ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ y of      ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ Health…   ┆   ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 155089.0   ┆ 2020.0 ┆ null      ┆ … ┆ 674.0     ┆ 0.262248  ┆ 0.128294  ┆ 133.0     │
# │ 50%        ┆ 196121.0   ┆ 2020.0 ┆ null      ┆ … ┆ 1783.0    ┆ 0.370848  ┆ 0.208903  ┆ 375.0     │
# │ 75%        ┆ 230597.0   ┆ 2020.0 ┆ null      ┆ … ┆ 5120.0    ┆ 0.5       ┆ 0.375284  ┆ 1311.0    │
# │ max        ┆ 496070.0   ┆ 2020.0 ┆ Zaytuna   ┆ … ┆ 111599.0  ┆ 1.0       ┆ 1.0       ┆ 51922.0   │
# │            ┆            ┆        ┆ College   ┆   ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# urm_share distribution (deciles):
#   0%: 0.0000
#   10%: 0.0688
#   20%: 0.1100
#   30%: 0.1420
#   40%: 0.1709
#   50%: 0.2089
#   60%: 0.2596
#   70%: 0.3299
#   80%: 0.4396
#   90%: 0.6943
#   100%: 1.0000
# 
# urm_share null rate by inst_control:
# shape: (2, 4)
# ┌──────────────┬──────────┬───────┬───────────┐
# │ inst_control ┆ urm_null ┆ total ┆ null_rate │
# │ ---          ┆ ---      ┆ ---   ┆ ---       │
# │ i64          ┆ u32      ┆ u32   ┆ f64       │
# ╞══════════════╪══════════╪═══════╪═══════════╡
# │ 1            ┆ 93       ┆ 852   ┆ 0.109155  │
# │ 2            ┆ 277      ┆ 1676  ┆ 0.165274  │
# └──────────────┴──────────┴───────┴───────────┘
# 
# Column null counts:
#   urban_centric_locale: 2 nulls (0.1%)
#   grad_rate_150pct: 732 nulls (29.0%)
#   cohort_year: 732 nulls (29.0%)
#   number_applied: 859 nulls (34.0%)
#   number_admitted: 869 nulls (34.4%)
#   number_enrolled_total: 870 nulls (34.4%)
#   admission_rate: 869 nulls (34.4%)
#   pell_recipients: 496 nulls (19.6%)
#   enrollment_undergrad: 370 nulls (14.6%)
#   pell_share: 518 nulls (20.5%)
#   urm_share: 370 nulls (14.6%)
#   urm_enrollment: 370 nulls (14.6%)
# 
# ============================================================
# QA RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
