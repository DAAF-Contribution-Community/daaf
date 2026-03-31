#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 02

Reviewed script: scripts/stage7_transform/02_join-demographics.py
Output files: data/processed/2026-03-29_core_demographics.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
6. [Counterfactual] Verify pell_share computed correctly via manual recalculation
7. [Semantic] Verify pell_share denominator is UG enrollment (not SFA total)
8. [Boundary] Check edge cases: zero enrollment, null combos, pell_share extremes
9. [Absence] Verify no core rows lost -- all original unitids still present
10. [Downstream] Verify downstream columns needed by join-resources exist
11-15. Spot checks: trace specific institutions, recalculate values, check filter complement
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_demographics.parquet"
INPUT_CORE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core.parquet"
INPUT_SFA = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_sfa_pell_clean.parquet"
INPUT_URM = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_urm_share_clean.parquet"

EXPECTED_COLUMNS = [
    "unitid", "inst_name", "fips", "inst_control", "open_public", "hbcu",
    "tribal_college", "number_applied", "number_admitted", "number_enrolled_total",
    "admit_rate", "completion_rate_150pct", "completers_150pct", "cohort_adj_150pct",
    "grant_recipients", "sfa_total_students", "urm_share", "total_ug_enrollment",
    "pell_share"
]
EXPECTED_ROW_COUNT = 2893
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 02 (join-demographics)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Load inputs for cross-reference checks
df_core = pl.read_parquet(INPUT_CORE)
df_sfa = pl.read_parquet(INPUT_SFA)
df_urm = pl.read_parquet(INPUT_URM)
print(f"Loaded core: {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"Loaded SFA: {df_sfa.shape[0]:,} rows x {df_sfa.shape[1]} cols")
print(f"Loaded URM: {df_urm.shape[0]:,} rows x {df_urm.shape[1]} cols")

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
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROW_COUNT
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROW_COUNT:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64, pl.Int32, pl.Int16, pl.Int8)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all() and len(col_data) > 10:
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
coded_issues = []
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

# --- Check 6: [Counterfactual] Manual recalculation of pell_share ---
# INTENT: Independently recalculate pell_share and compare to stored value.
# If pell_share was computed incorrectly, the recalculation would differ.
print("\n--- Counterfactual: Manual pell_share recalculation ---")
df_recalc = df.with_columns(
    pl.when(
        pl.col("grant_recipients").is_not_null()
        & pl.col("total_ug_enrollment").is_not_null()
        & (pl.col("total_ug_enrollment") > 0)
    )
    .then(pl.col("grant_recipients") / pl.col("total_ug_enrollment"))
    .otherwise(None)
    .alias("pell_share_recalc")
)

# Compare recalculated vs stored
both_nonnull = df_recalc.filter(
    pl.col("pell_share").is_not_null() & pl.col("pell_share_recalc").is_not_null()
)
diff = (both_nonnull["pell_share"] - both_nonnull["pell_share_recalc"]).abs()
max_diff = diff.max() if diff.len() > 0 else 0
recalc_ok = max_diff < 1e-10
print(f"[{'PASS' if recalc_ok else 'FAIL'}] pell_share recalculation matches: max diff = {max_diff}")

# Check that null patterns match too
stored_null = df["pell_share"].null_count()
recalc_null = df_recalc["pell_share_recalc"].null_count()
null_pattern_match = stored_null == recalc_null
print(f"[{'PASS' if null_pattern_match else 'FAIL'}] Null pattern match: stored={stored_null}, recalc={recalc_null}")

# --- Check 7: [Semantic] Verify pell_share uses UG enrollment, not SFA total ---
# INTENT: Confirm the script used total_ug_enrollment (from URM/enrollment file)
# as denominator, not sfa_total_students (from SFA file). Plan.md Modeling Decisions
# specifies: "Pell share denominator: UG enrollment from IPEDS fall enrollment race."
print("\n--- Semantic: pell_share denominator source ---")
# If sfa_total_students was used as denominator, pell_share would equal
# grant_recipients / sfa_total_students, which differs from the stored value
df_wrong_denom = df.filter(
    pl.col("grant_recipients").is_not_null()
    & pl.col("sfa_total_students").is_not_null()
    & (pl.col("sfa_total_students") > 0)
    & pl.col("total_ug_enrollment").is_not_null()
    & (pl.col("total_ug_enrollment") > 0)
).with_columns(
    (pl.col("grant_recipients") / pl.col("sfa_total_students")).alias("wrong_pell_share")
)
if df_wrong_denom.height > 0:
    diffs_with_wrong = (df_wrong_denom["pell_share"] - df_wrong_denom["wrong_pell_share"]).abs()
    n_match_wrong = (diffs_with_wrong < 1e-10).sum()
    n_total = df_wrong_denom.height
    # If pell_share matches the wrong denominator, that's a problem
    semantic_ok = n_match_wrong < n_total * 0.01  # <1% should match by coincidence
    print(f"[{'PASS' if semantic_ok else 'FAIL'}] pell_share does NOT use sfa_total_students: {n_match_wrong}/{n_total} match wrong denominator")
else:
    print("[INFO] Cannot test wrong-denominator -- insufficient overlap between sfa_total_students and total_ug_enrollment")
    semantic_ok = True

# --- Check 8: [Boundary] Edge cases ---
print("\n--- Boundary: Edge cases ---")
# Zero enrollment check
zero_enroll = df.filter(
    (pl.col("total_ug_enrollment") == 0) & pl.col("total_ug_enrollment").is_not_null()
)
zero_enroll_pell_null = zero_enroll["pell_share"].null_count() == zero_enroll.height
print(f"[{'PASS' if zero_enroll.height == 0 or zero_enroll_pell_null else 'FAIL'}] "
      f"Zero enrollment -> null pell_share: {zero_enroll.height} institutions with zero enrollment")

# pell_share > 1 cases
ps_gt1 = df.filter(pl.col("pell_share") > 1.0)
print(f"[WARN] pell_share > 1.0: {ps_gt1.height} institutions")
if ps_gt1.height > 0:
    for row in ps_gt1.select("unitid", "inst_name", "grant_recipients", "total_ug_enrollment", "pell_share").iter_rows(named=True):
        print(f"  unitid={row['unitid']}: grant_recip={row['grant_recipients']}, ug_enroll={row['total_ug_enrollment']}, pell_share={row['pell_share']:.4f}")

# Single-row group boundary: institutions with only SFA match, only URM match, both, or neither
sfa_only = df.filter(
    pl.col("grant_recipients").is_not_null() & pl.col("urm_share").is_null()
).height
urm_only = df.filter(
    pl.col("grant_recipients").is_null() & pl.col("urm_share").is_not_null()
).height
both_match = df.filter(
    pl.col("grant_recipients").is_not_null() & pl.col("urm_share").is_not_null()
).height
neither = df.filter(
    pl.col("grant_recipients").is_null() & pl.col("urm_share").is_null()
).height
print(f"[INFO] Match pattern distribution:")
print(f"  Both SFA + URM: {both_match:,}")
print(f"  SFA only: {sfa_only:,}")
print(f"  URM only: {urm_only:,}")
print(f"  Neither: {neither:,}")
print(f"  Total: {sfa_only + urm_only + both_match + neither:,}")
boundary_total_ok = (sfa_only + urm_only + both_match + neither) == EXPECTED_ROW_COUNT
print(f"[{'PASS' if boundary_total_ok else 'FAIL'}] Match pattern covers all rows: {boundary_total_ok}")

# --- Check 9: [Absence] No core rows lost ---
print("\n--- Absence: Core row preservation ---")
core_unitids = set(df_core["unitid"].to_list())
output_unitids = set(df["unitid"].to_list())
lost_unitids = core_unitids - output_unitids
gained_unitids = output_unitids - core_unitids
absence_ok = len(lost_unitids) == 0 and len(gained_unitids) == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] Core row preservation: lost={len(lost_unitids)}, gained={len(gained_unitids)}")
if lost_unitids:
    print(f"  Lost unitids (sample): {list(lost_unitids)[:10]}")

# --- Check 10: [Downstream] Columns needed by join-resources ---
print("\n--- Downstream: Columns for next step (join-resources, create-bands) ---")
# join-resources needs the full demographics output as input
# create-bands needs: pell_share (for pell_quintile), urm_share (for urm_quintile), open_public, admit_rate
downstream_cols = ["unitid", "pell_share", "urm_share", "open_public", "admit_rate",
                   "completion_rate_150pct", "inst_control", "inst_name"]
missing_downstream = [c for c in downstream_cols if c not in df.columns]
downstream_ok = len(missing_downstream) == 0
print(f"[{'PASS' if downstream_ok else 'FAIL'}] Downstream columns present: {len(downstream_cols) - len(missing_downstream)}/{len(downstream_cols)}")
if missing_downstream:
    print(f"  Missing: {missing_downstream}")

# --- Spot Check 11: Trace specific institution through transformation ---
print("\n--- Spot Check: Trace a specific institution ---")
# Pick the first institution that has both SFA and URM match
sample_unitids = df.filter(
    pl.col("grant_recipients").is_not_null() & pl.col("urm_share").is_not_null()
).head(3)["unitid"].to_list()

for uid in sample_unitids:
    out_row = df.filter(pl.col("unitid") == uid)
    core_row = df_core.filter(pl.col("unitid") == uid)
    sfa_row = df_sfa.filter(pl.col("unitid") == uid)
    urm_row = df_urm.filter(pl.col("unitid") == uid)

    print(f"\n  unitid={uid}:")
    if core_row.height > 0:
        print(f"    Core: inst_name={core_row['inst_name'][0]}, inst_control={core_row['inst_control'][0]}")
    if sfa_row.height > 0:
        print(f"    SFA: grant_recipients={sfa_row['grant_recipients'][0]}, sfa_total={sfa_row['sfa_total_students'][0]}")
    if urm_row.height > 0:
        print(f"    URM: urm_share={urm_row['urm_share'][0]:.4f}, total_ug={urm_row['total_ug_enrollment'][0]}")
    if out_row.height > 0:
        print(f"    Output: pell_share={out_row['pell_share'][0]:.4f if out_row['pell_share'][0] is not None else 'null'}, "
              f"urm_share={out_row['urm_share'][0]:.4f if out_row['urm_share'][0] is not None else 'null'}")
        # Manual recalculation for this specific institution
        if sfa_row.height > 0 and urm_row.height > 0:
            manual_pell = sfa_row['grant_recipients'][0] / urm_row['total_ug_enrollment'][0]
            stored_pell = out_row['pell_share'][0]
            match = abs(manual_pell - stored_pell) < 1e-10
            print(f"    Manual recalc: {sfa_row['grant_recipients'][0]} / {urm_row['total_ug_enrollment'][0]} = {manual_pell:.4f} -> match={match}")

# --- Spot Check 12: Verify filter complement (non-matching keys) ---
print("\n--- Spot Check: Non-matching SFA keys ---")
sfa_keys = set(df_sfa["unitid"].to_list())
core_keys = set(df_core["unitid"].to_list())
sfa_not_in_core = sfa_keys - core_keys
core_not_in_sfa = core_keys - sfa_keys
print(f"  SFA institutions not in core: {len(sfa_not_in_core):,} (likely 2-year or non-degree-granting)")
print(f"  Core institutions not in SFA: {len(core_not_in_sfa):,} (no SFA data)")
# Verify grant_recipients is null exactly for core-not-in-sfa
null_grant = df.filter(pl.col("grant_recipients").is_null())["unitid"].to_list()
null_grant_set = set(null_grant)
fc_ok = null_grant_set == core_not_in_sfa
# There could also be nulls from within-SFA nulls (grant_recipients was null in SFA itself)
# So let's check a weaker condition: core_not_in_sfa should be a SUBSET of null_grant_set
fc_ok_weak = core_not_in_sfa.issubset(null_grant_set)
print(f"[{'PASS' if fc_ok_weak else 'FAIL'}] Core non-SFA unitids all have null grant_recipients: {fc_ok_weak}")
extra_nulls = null_grant_set - core_not_in_sfa
if extra_nulls:
    print(f"  Additional nulls from SFA-internal nulls: {len(extra_nulls):,}")

# --- Spot Check 13: Join key cardinality verification ---
print("\n--- Spot Check: Join key cardinality ---")
unitid_unique_out = df["unitid"].n_unique() == df.height
print(f"[{'PASS' if unitid_unique_out else 'FAIL'}] unitid unique in output: {df['unitid'].n_unique():,} unique / {df.height:,} rows")

# --- Spot Check 14: pell_share null pattern correctness ---
print("\n--- Spot Check: pell_share null pattern ---")
# pell_share should be null when: grant_recipients is null OR total_ug_enrollment is null OR total_ug_enrollment == 0
expected_null_cond = (
    pl.col("grant_recipients").is_null()
    | pl.col("total_ug_enrollment").is_null()
    | (pl.col("total_ug_enrollment") == 0)
)
expected_null_count = df.filter(expected_null_cond).height
actual_null_count = df["pell_share"].null_count()
null_pattern_ok = expected_null_count == actual_null_count
print(f"[{'PASS' if null_pattern_ok else 'FAIL'}] pell_share null count matches expected: actual={actual_null_count}, expected_from_conditions={expected_null_count}")

# --- Spot Check 15: pell_share among institutions with grad rate data ---
print("\n--- Spot Check: pell_share coverage for institutions with grad rates ---")
has_grad = df.filter(pl.col("completion_rate_150pct").is_not_null())
pell_with_grad = has_grad.filter(pl.col("pell_share").is_not_null()).height
grad_total = has_grad.height
pell_coverage_pct = pell_with_grad / grad_total * 100 if grad_total > 0 else 0
# BLOCKER if: pell_share has >50% nulls among institutions with grad rate data
pell_coverage_ok = pell_coverage_pct >= 50
print(f"[{'PASS' if pell_coverage_ok else 'BLOCKER'}] pell_share non-null among grad-rate institutions: "
      f"{pell_with_grad:,}/{grad_total:,} ({pell_coverage_pct:.1f}%)")
# Research Outcome contribution: "pell_share and urm_share are non-null for >60% of institutions with grad rate data"
urm_with_grad = has_grad.filter(pl.col("urm_share").is_not_null()).height
urm_coverage_pct = urm_with_grad / grad_total * 100 if grad_total > 0 else 0
print(f"[{'PASS' if urm_coverage_pct >= 60 else 'WARN'}] urm_share non-null among grad-rate institutions: "
      f"{urm_with_grad:,}/{grad_total:,} ({urm_coverage_pct:.1f}%)")

# --- Summary ---
all_critical = all([schema_ok, rows_ok, recalc_ok, null_pattern_match, absence_ok,
                     unitid_unique_out, null_pattern_ok, pell_coverage_ok,
                     boundary_total_ok, downstream_ok, nulls_ok])
print("\n" + "=" * 60)
severity = "PASSED" if all_critical else "BLOCKER"
print(f"QA RESULT: {severity}")
if not all_critical:
    print("Failed checks above require investigation")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey demographic column distributions:")
for col in ["pell_share", "urm_share", "grant_recipients", "total_ug_enrollment"]:
    if col in df.columns:
        nonnull = df[col].drop_nulls()
        if nonnull.len() > 0:
            print(f"\n{col}: n={nonnull.len():,}, null={df[col].null_count():,}")
            print(f"  min={nonnull.min()}, p10={nonnull.quantile(0.1)}, median={nonnull.median()}, "
                  f"p90={nonnull.quantile(0.9)}, max={nonnull.max()}, mean={nonnull.mean():.4f}")

print("\ninst_control distribution:")
print(df["inst_control"].value_counts().sort("inst_control"))

print("\nNull rate summary:")
for col in df.columns:
    null_ct = df[col].null_count()
    if null_ct > 0:
        print(f"  {col}: {null_ct:,} ({null_ct / df.height * 100:.1f}%)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 00:29:08
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_02_cr1.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 02 (join-demographics)
# ============================================================
# Loaded output: 2,893 rows x 19 cols
# Loaded core: 2,893 rows x 14 cols
# Loaded SFA: 5,320 rows x 3 cols
# Loaded URM: 5,837 rows x 3 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 2,893 (expected exactly 2,893)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in integer columns
# [PASS] Critical nulls: None
# 
# --- Counterfactual: Manual pell_share recalculation ---
# [PASS] pell_share recalculation matches: max diff = 0.0
# [PASS] Null pattern match: stored=669, recalc=669
# 
# --- Semantic: pell_share denominator source ---
# [PASS] pell_share does NOT use sfa_total_students: 3/2224 match wrong denominator
# 
# --- Boundary: Edge cases ---
# [PASS] Zero enrollment -> null pell_share: 0 institutions with zero enrollment
# [WARN] pell_share > 1.0: 1 institutions
#   unitid=376385: grant_recip=128, ug_enroll=108, pell_share=1.1852
# [INFO] Match pattern distribution:
#   Both SFA + URM: 2,223
#   SFA only: 1
#   URM only: 247
#   Neither: 422
#   Total: 2,893
# [PASS] Match pattern covers all rows: True
# 
# --- Absence: Core row preservation ---
# [PASS] Core row preservation: lost=0, gained=0
# 
# --- Downstream: Columns for next step (join-resources, create-bands) ---
# [PASS] Downstream columns present: 8/8
# 
# --- Spot Check: Trace a specific institution ---
# 
#   unitid=100654:
#     Core: inst_name=Alabama A & M University, inst_control=1
#     SFA: grant_recipients=642, sfa_total=657
#     URM: urm_share=0.9669, total_ug=5093
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_02_cr1.py", line 260, in <module>
#     print(f"    Output: pell_share={out_row['pell_share'][0]:.4f if out_row['pell_share'][0] is not None else 'null'}, "
#                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# ValueError: Invalid format specifier '.4f if out_row['pell_share'][0] is not None else 'null'' for object of type 'float'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
