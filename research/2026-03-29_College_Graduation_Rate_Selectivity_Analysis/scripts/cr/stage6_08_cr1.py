#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 08

Reviewed script: scripts/stage6_clean/08_clean-finance.py
Output files: data/processed/2026-03-29_finance_clean.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range
3. Distribution sanity
4. Coded values properly filtered
5. Critical nulls absent

Script-Specific Checks (5 Lenses):
6. [Counterfactual] Negative expenditure values in raw -> per-FTE result
7. [Semantic] Per-FTE calculation independence verification
8. [Boundary] est_fte edge cases: verify no zero/negative FTE in output
9. [Absence] Check no year column leak or extra columns
10. [Downstream] Null profile compatible with downstream LEFT join

Spot-Checks:
11. Manual recalculation of instr_expend_per_fte for sampled records
12. Verify filter complement (removed rows) makes sense
13. Trace a specific unitid through raw -> clean
14. Cross-reference output row count with raw FTE > 0 count
15. Check unitid uniqueness holds at both file and value level
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-03-29_finance_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_finance.parquet"

EXPECTED_COLUMNS = ["unitid", "instr_expend_per_fte"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 8000
CRITICAL_COLUMNS = ["unitid"]
CODED_MISSING_VALUES = [-1, -2, -3]

EXPENDITURE_COL = "exp_instruc_total"
FTE_COL = "est_fte"

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 08 (clean-finance)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load raw for cross-reference checks
assert RAW_FILE.exists(), f"FAIL: Raw file not found: {RAW_FILE}"
df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# =========================================================================
# DEFAULT CHECKS
# =========================================================================

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
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

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

# =========================================================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# =========================================================================

# --- Check 6: [Counterfactual] Negative expenditure -> per-FTE ---
# What if raw exp_instruc_total had legitimate negative values (accounting adjustments)?
# Those would produce negative per-FTE values, which the script flags but does not remove.
print("\n--- Check 6: [Counterfactual] Negative per-FTE values ---")
negative_per_fte = df.filter(
    (pl.col("instr_expend_per_fte").is_not_null())
    & (pl.col("instr_expend_per_fte") < 0)
).height
print(f"  Negative instr_expend_per_fte values: {negative_per_fte}")
# Also check raw data for negative expenditures
raw_neg_expend = df_raw.filter(
    (pl.col(EXPENDITURE_COL).is_not_null())
    & (~pl.col(EXPENDITURE_COL).is_in(CODED_MISSING_VALUES))
    & (pl.col(EXPENDITURE_COL) < 0)
).height
print(f"  Raw negative {EXPENDITURE_COL}: {raw_neg_expend}")
neg_ok = negative_per_fte == 0
print(f"  [{'PASS' if neg_ok else 'WARN'}] No negative per-FTE values")

# --- Check 7: [Semantic] Independent per-FTE recalculation ---
# Verify that the script correctly computed exp_instruc_total / est_fte
print("\n--- Check 7: [Semantic] Per-FTE calculation independence ---")
# Reconstruct the computation from raw data
raw_with_calc = df_raw.filter(
    (pl.col(FTE_COL).is_not_null())
    & (pl.col(FTE_COL) > 0)
    & (~pl.col(FTE_COL).is_in(CODED_MISSING_VALUES))
    & (pl.col(EXPENDITURE_COL).is_not_null())
    & (~pl.col(EXPENDITURE_COL).is_in(CODED_MISSING_VALUES))
).with_columns(
    (pl.col(EXPENDITURE_COL).cast(pl.Float64) / pl.col(FTE_COL).cast(pl.Float64))
    .alias("recalc_per_fte")
).select(["unitid", "recalc_per_fte"])

# Join to output and compare
joined = df.filter(pl.col("instr_expend_per_fte").is_not_null()).join(
    raw_with_calc, on="unitid", how="inner"
)
if joined.height > 0:
    diff = (joined["instr_expend_per_fte"] - joined["recalc_per_fte"]).abs()
    max_diff = diff.max()
    mean_diff = diff.mean()
    n_exact_match = (diff < 0.01).sum()
    print(f"  Compared {joined.height:,} records")
    print(f"  Max absolute difference: {max_diff:.6f}")
    print(f"  Mean absolute difference: {mean_diff:.6f}")
    print(f"  Exact matches (diff < 0.01): {n_exact_match:,} / {joined.height:,}")
    calc_ok = max_diff < 0.01
    print(f"  [{'PASS' if calc_ok else 'FAIL'}] Independent recalculation matches")
else:
    print("  WARNING: No matching records for recalculation check")
    calc_ok = False

# --- Check 8: [Boundary] No zero or negative FTE in output ---
# The script filters est_fte > 0 before division. Verify the output has no
# evidence of division by zero (inf values) or negative denominators.
print("\n--- Check 8: [Boundary] FTE edge cases ---")
# Check for infinity values
inf_count = df.filter(
    pl.col("instr_expend_per_fte").is_infinite()
).height if "instr_expend_per_fte" in df.columns else 0
print(f"  Infinite values: {inf_count}")
# Check for NaN values
nan_count = df.filter(
    pl.col("instr_expend_per_fte").is_nan()
).height if "instr_expend_per_fte" in df.columns else 0
print(f"  NaN values: {nan_count}")
boundary_ok = inf_count == 0 and nan_count == 0
print(f"  [{'PASS' if boundary_ok else 'FAIL'}] No infinity/NaN in output")

# --- Check 9: [Absence] No extra columns leaked ---
# The script selects only unitid and instr_expend_per_fte. Verify nothing else.
print("\n--- Check 9: [Absence] Column leak check ---")
expected_cols_set = set(EXPECTED_COLUMNS)
actual_cols_set = set(df.columns)
leaked = actual_cols_set - expected_cols_set
absence_ok = len(leaked) == 0
print(f"  Expected columns: {sorted(expected_cols_set)}")
print(f"  Actual columns: {sorted(actual_cols_set)}")
print(f"  [{'PASS' if absence_ok else 'WARN'}] No extra columns: {leaked if leaked else 'clean'}")

# --- Check 10: [Downstream] Null profile for LEFT join compatibility ---
# Downstream join-resources (Stage 7 Step 6.1) uses LEFT join on unitid.
# Rows with null instr_expend_per_fte will propagate. Check null rate.
print("\n--- Check 10: [Downstream] Null profile ---")
null_count_derived = df["instr_expend_per_fte"].null_count()
null_rate = null_count_derived / len(df) * 100
print(f"  Nulls in instr_expend_per_fte: {null_count_derived:,} ({null_rate:.1f}%)")
downstream_ok = null_rate < 20  # Per QA tolerance
print(f"  [{'PASS' if downstream_ok else 'WARN'}] Null rate < 20%: {null_rate:.1f}%")

# =========================================================================
# SPOT-CHECKS
# =========================================================================

# --- Spot-Check 11: Manual recalculation for 5 specific records ---
print("\n--- Spot-Check 11: Trace 5 records through raw -> clean ---")
sample_unitids = df.filter(pl.col("instr_expend_per_fte").is_not_null()).sample(5, seed=42)["unitid"].to_list()
for uid in sample_unitids:
    raw_row = df_raw.filter(pl.col("unitid") == uid)
    clean_row = df.filter(pl.col("unitid") == uid)
    if raw_row.height == 1 and clean_row.height == 1:
        raw_exp = raw_row[EXPENDITURE_COL][0]
        raw_fte = raw_row[FTE_COL][0]
        clean_val = clean_row["instr_expend_per_fte"][0]
        expected_val = raw_exp / raw_fte if raw_fte and raw_fte > 0 else None
        match = abs(clean_val - expected_val) < 0.01 if clean_val is not None and expected_val is not None else False
        print(f"  unitid={uid}: raw_exp={raw_exp}, raw_fte={raw_fte}, "
              f"expected={expected_val:.2f}, actual={clean_val:.2f}, match={match}")

# --- Spot-Check 12: Filter complement analysis ---
print("\n--- Spot-Check 12: Filter complement (removed records) ---")
output_unitids = set(df["unitid"].to_list())
raw_unitids = set(df_raw["unitid"].to_list())
removed_unitids = raw_unitids - output_unitids
print(f"  Institutions in raw: {len(raw_unitids):,}")
print(f"  Institutions in output: {len(output_unitids):,}")
print(f"  Institutions removed: {len(removed_unitids):,}")
# Check why they were removed -- should be est_fte null or <= 0
removed_df = df_raw.filter(pl.col("unitid").is_in(list(removed_unitids)))
removed_fte_null = removed_df.filter(pl.col(FTE_COL).is_null()).height
removed_fte_zero = removed_df.filter(pl.col(FTE_COL) == 0).height
removed_fte_coded = removed_df.filter(pl.col(FTE_COL).is_in(CODED_MISSING_VALUES)).height
print(f"  Removed because est_fte null: {removed_fte_null}")
print(f"  Removed because est_fte == 0: {removed_fte_zero}")
print(f"  Removed because est_fte coded missing: {removed_fte_coded}")
total_explained = removed_fte_null + removed_fte_zero + removed_fte_coded
print(f"  Total explained: {total_explained} / {len(removed_unitids)}")
complement_ok = total_explained == len(removed_unitids)
print(f"  [{'PASS' if complement_ok else 'WARN'}] All removals explained by FTE filter")

# --- Spot-Check 13: Trace a high and low per-FTE institution ---
print("\n--- Spot-Check 13: Extreme value trace ---")
non_null_df = df.filter(pl.col("instr_expend_per_fte").is_not_null())
if non_null_df.height > 0:
    max_row = non_null_df.sort("instr_expend_per_fte", descending=True).head(1)
    min_row = non_null_df.sort("instr_expend_per_fte").head(1)
    print(f"  Highest per-FTE: unitid={max_row['unitid'][0]}, "
          f"value=${max_row['instr_expend_per_fte'][0]:,.0f}")
    print(f"  Lowest per-FTE: unitid={min_row['unitid'][0]}, "
          f"value=${min_row['instr_expend_per_fte'][0]:,.0f}")
    # Cross-reference highest with raw
    max_uid = max_row["unitid"][0]
    max_raw = df_raw.filter(pl.col("unitid") == max_uid)
    if max_raw.height > 0:
        print(f"  Raw for highest: exp={max_raw[EXPENDITURE_COL][0]:,}, "
              f"fte={max_raw[FTE_COL][0]:,}")

# --- Spot-Check 14: Cross-reference row count ---
print("\n--- Spot-Check 14: Row count cross-reference ---")
# Independently count how many raw rows have est_fte > 0 and not null and not coded
raw_valid_fte = df_raw.filter(
    (pl.col(FTE_COL).is_not_null())
    & (pl.col(FTE_COL) > 0)
    & (~pl.col(FTE_COL).is_in(CODED_MISSING_VALUES))
).height
print(f"  Raw rows with valid est_fte (>0, not null, not coded): {raw_valid_fte:,}")
print(f"  Output rows: {len(df):,}")
count_match = raw_valid_fte == len(df)
print(f"  [{'PASS' if count_match else 'WARN'}] Counts match: {count_match}")

# --- Spot-Check 15: Unitid uniqueness at value level ---
print("\n--- Spot-Check 15: Unitid uniqueness deep check ---")
n_unique = df["unitid"].n_unique()
n_total = len(df)
unique_ok = n_unique == n_total
print(f"  Unique unitids: {n_unique:,} / {n_total:,} rows")
# Also check for any unitid == 0 or negative (suspicious)
bad_unitids = df.filter((pl.col("unitid") <= 0) | (pl.col("unitid").is_null())).height
print(f"  Bad unitids (<=0 or null): {bad_unitids}")
unitid_deep_ok = unique_ok and bad_unitids == 0
print(f"  [{'PASS' if unitid_deep_ok else 'FAIL'}] Unitid integrity verified")

# =========================================================================
# DATA PROFILING (for cr2+ decision)
# =========================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
print(f"\nunitid sample (first 10): {df['unitid'].head(10).to_list()}")

print(f"\ninstr_expend_per_fte quantiles:")
non_null_vals = df.filter(pl.col("instr_expend_per_fte").is_not_null())["instr_expend_per_fte"]
if len(non_null_vals) > 0:
    for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
        val = non_null_vals.quantile(q)
        print(f"  p{int(q*100):02d}: ${val:,.0f}")

print(f"\nOutlier counts:")
below_1k = non_null_vals.filter(non_null_vals < 1000).len()
above_200k = non_null_vals.filter(non_null_vals > 200000).len()
print(f"  Below $1,000: {below_1k}")
print(f"  Above $200,000: {above_200k}")
outlier_rate = (below_1k + above_200k) / len(non_null_vals) * 100
print(f"  Outlier rate: {outlier_rate:.1f}%")

# =========================================================================
# SUMMARY
# =========================================================================
all_default = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific = all([neg_ok, calc_ok, boundary_ok, absence_ok, downstream_ok])
all_spot = all([complement_ok, unitid_deep_ok])

all_passed = all_default and all_specific and all_spot

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
if not all_passed:
    if not all_default:
        print("  Default checks have failures")
    if not all_specific:
        print("  Script-specific checks have failures")
    if not all_spot:
        print("  Spot-checks have failures")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:58:26
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 08 (clean-finance)
# ============================================================
# Loaded output: 6,522 rows x 2 cols
# Loaded raw: 6,857 rows x 141 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 6,522 (expected 3,000-8,000)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Check 6: [Counterfactual] Negative per-FTE values ---
#   Negative instr_expend_per_fte values: 0
#   Raw negative exp_instruc_total: 0
#   [PASS] No negative per-FTE values
# 
# --- Check 7: [Semantic] Per-FTE calculation independence ---
#   Compared 6,076 records
#   Max absolute difference: 0.000000
#   Mean absolute difference: 0.000000
#   Exact matches (diff < 0.01): 6,076 / 6,076
#   [PASS] Independent recalculation matches
# 
# --- Check 8: [Boundary] FTE edge cases ---
#   Infinite values: 0
#   NaN values: 0
#   [PASS] No infinity/NaN in output
# 
# --- Check 9: [Absence] Column leak check ---
#   Expected columns: ['instr_expend_per_fte', 'unitid']
#   Actual columns: ['instr_expend_per_fte', 'unitid']
#   [PASS] No extra columns: clean
# 
# --- Check 10: [Downstream] Null profile ---
#   Nulls in instr_expend_per_fte: 446 (6.8%)
#   [PASS] Null rate < 20%: 6.8%
# 
# --- Spot-Check 11: Trace 5 records through raw -> clean ---
#   unitid=454306: raw_exp=886817.0, raw_fte=105, expected=8445.88, actual=8445.88, match=True
#   unitid=182306: raw_exp=14243846.0, raw_fte=1929, expected=7384.06, actual=7384.06, match=True
#   unitid=490674: raw_exp=30000.0, raw_fte=13, expected=2307.69, actual=2307.69, match=True
#   unitid=418205: raw_exp=2547894.0, raw_fte=252, expected=10110.69, actual=10110.69, match=True
#   unitid=449524: raw_exp=1012752.0, raw_fte=244, expected=4150.62, actual=4150.62, match=True
# 
# --- Spot-Check 12: Filter complement (removed records) ---
#   Institutions in raw: 6,857
#   Institutions in output: 6,522
#   Institutions removed: 335
#   Removed because est_fte null: 296
#   Removed because est_fte == 0: 39
#   Removed because est_fte coded missing: 0
#   Total explained: 335 / 335
#   [PASS] All removals explained by FTE filter
# 
# --- Spot-Check 13: Extreme value trace ---
#   Highest per-FTE: unitid=480790, value=$14,146,996
#   Lowest per-FTE: unitid=391546, value=$120
#   Raw for highest: exp=14,146,996.0, fte=1
# 
# --- Spot-Check 14: Row count cross-reference ---
#   Raw rows with valid est_fte (>0, not null, not coded): 6,522
#   Output rows: 6,522
#   [PASS] Counts match: True
# 
# --- Spot-Check 15: Unitid uniqueness deep check ---
#   Unique unitids: 6,522 / 6,522 rows
#   Bad unitids (<=0 or null): 0
#   [PASS] Unitid integrity verified
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 2)
# ┌────────┬──────────────────────┐
# │ unitid ┆ instr_expend_per_fte │
# │ ---    ┆ ---                  │
# │ i64    ┆ f64                  │
# ╞════════╪══════════════════════╡
# │ 100654 ┆ 5383.77066           │
# │ 100663 ┆ 17533.005147         │
# │ 100690 ┆ 4206.030948          │
# │ 100706 ┆ 9390.673879          │
# │ 100724 ┆ 8750.468505          │
# │ 100751 ┆ 10954.560443         │
# │ 100760 ┆ 6801.392385          │
# │ 100812 ┆ 7987.696413          │
# │ 100830 ┆ 7198.384913          │
# │ 100858 ┆ 11516.112987         │
# └────────┴──────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 3)
# ┌────────────┬───────────────┬──────────────────────┐
# │ statistic  ┆ unitid        ┆ instr_expend_per_fte │
# │ ---        ┆ ---           ┆ ---                  │
# │ str        ┆ f64           ┆ f64                  │
# ╞════════════╪═══════════════╪══════════════════════╡
# │ count      ┆ 6522.0        ┆ 6076.0               │
# │ null_count ┆ 0.0           ┆ 446.0                │
# │ mean       ┆ 284278.380251 ┆ 17132.156406         │
# │ std        ┆ 136670.607734 ┆ 243994.90992         │
# │ min        ┆ 100654.0      ┆ 119.807692           │
# │ 25%        ┆ 170091.0      ┆ 3900.508557          │
# │ 50%        ┆ 220701.0      ┆ 6143.295826          │
# │ 75%        ┆ 444440.0      ┆ 9686.161546          │
# │ max        ┆ 493451.0      ┆ 1.4146996e7          │
# └────────────┴───────────────┴──────────────────────┘
# 
# Key column value counts:
# 
# unitid sample (first 10): [100654, 100663, 100690, 100706, 100724, 100751, 100760, 100812, 100830, 100858]
# 
# instr_expend_per_fte quantiles:
#   p01: $805
#   p05: $1,623
#   p10: $2,299
#   p25: $3,901
#   p50: $6,143
#   p75: $9,686
#   p90: $16,133
#   p95: $24,519
#   p99: $98,953
# 
# Outlier counts:
#   Below $1,000: 100
#   Above $200,000: 34
#   Outlier rate: 2.2%
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
