#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 01 (QA4a — Statistical Validity)

Reviewed script: scripts/stage8_analysis/01_descriptive-by-selectivity.py
Output files: output/analysis/2026-02-15_descriptive_by_selectivity.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range (exactly 4)
3. No suspicious distributions (all-same, all-zeros)
4. Coded values properly filtered (no -1, -2, -3)
5. No nulls in critical columns

QA Checks (Script-Specific — Five Lenses):
6. [Counterfactual] What if selectivity_band had a 5th category or missing values?
7. [Semantic] Does the aggregation answer the research question, not just match the Plan?
8. [Boundary] Check edge cases: bands with very few institutions, grad_rate near 0 or 100
9. [Absence] Are any expected metrics missing from the output?
10. [Downstream] Will downstream scripts (crosstab, outperformers, report) consume this correctly?

Spot-Checks:
11. Recalculate one band's median grad_rate from raw data
12. Verify n values by counting raw analysis data
13. Verify admission_rate ranges per band are plausible
14. Check that grad_rate_150pct_count + nulls = n for each band
15. Verify band ordering matches expected order
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_descriptive_by_selectivity.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
EXPECTED_COLUMNS = [
    "selectivity_band", "n",
    "grad_rate_150pct_median", "grad_rate_150pct_mean", "grad_rate_150pct_std",
    "grad_rate_150pct_q1", "grad_rate_150pct_q3", "grad_rate_150pct_count",
    "admission_rate_median", "admission_rate_mean",
    "pell_share_median", "pell_share_mean",
    "urm_share_median", "urm_share_mean",
    "student_faculty_ratio_median", "student_faculty_ratio_mean",
    "retention_rate_median", "retention_rate_mean",
]
EXPECTED_ROWS = 4
EXPECTED_BANDS = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
CRITICAL_COLUMNS = ["selectivity_band", "n", "grad_rate_150pct_median", "grad_rate_150pct_mean"]

# --- Load output data ---
print("=" * 60)
print("QA4a INSPECTION: Stage 8 Step 01 — descriptive-by-selectivity")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load input (source) data for independent verification
source_df = pl.read_parquet(INPUT_FILE)
print(f"Loaded source: {source_df.shape[0]:,} rows x {source_df.shape[1]} cols")

# ========================================================================
# DEFAULT CHECKS
# ========================================================================

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
    print(f"  Extra columns (not in expected): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count} (expected exactly {EXPECTED_ROWS})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64, pl.Int32, pl.UInt32)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 1:
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

# ========================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ========================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] What if selectivity_band had unexpected values? ---
print("\n--- Check 6: [Counterfactual] Band completeness ---")
actual_bands = sorted(df["selectivity_band"].to_list())
expected_bands_sorted = sorted(EXPECTED_BANDS)
bands_match = actual_bands == expected_bands_sorted
print(f"[{'PASS' if bands_match else 'FAIL'}] Bands match expected: {actual_bands}")

# Check: are there any null selectivity_band values in SOURCE data?
source_null_bands = source_df.filter(pl.col("selectivity_band").is_null()).shape[0]
print(f"  Source data: {source_null_bands} rows with null selectivity_band")
if source_null_bands > 0:
    print(f"  [WARNING] {source_null_bands} institutions have null selectivity_band — they are excluded from the group_by")
    # These would be silently dropped by group_by
    bands_counterfactual_ok = False
else:
    print(f"  [PASS] No null selectivity_band in source — group_by covers all rows")
    bands_counterfactual_ok = True

# --- Check 7: [Semantic] Does this answer the research question? ---
print("\n--- Check 7: [Semantic] Research question alignment ---")
# Research question: "Are high graduation rates a signal of quality or selectivity?"
# This table should show that grad rates track selectivity closely.
# Check: is the spread between top and bottom band large enough to be "significant"?
top_band = df.filter(pl.col("selectivity_band") == "Highly Selective")
bottom_band = df.filter(pl.col("selectivity_band") == "Less Selective/Open")

if len(top_band) > 0 and len(bottom_band) > 0:
    top_median = top_band["grad_rate_150pct_median"][0]
    bottom_median = bottom_band["grad_rate_150pct_median"][0]
    spread = top_median - bottom_median
    print(f"  Top band median: {top_median:.1f}%, Bottom band median: {bottom_median:.1f}%")
    print(f"  Spread: {spread:.1f} percentage points")
    semantic_ok = spread > 10  # Should be substantial gap
    print(f"  [{'PASS' if semantic_ok else 'WARN'}] Gradient is {'substantial' if semantic_ok else 'unexpectedly small'} ({spread:.1f}pp)")
else:
    semantic_ok = False
    print("  [FAIL] Could not find top and bottom bands")

# --- Check 8: [Boundary] Edge cases ---
print("\n--- Check 8: [Boundary] Small bands and extreme values ---")
boundary_ok = True

# Check for bands with very few institutions
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    n = row["n"]
    if n < 10:
        print(f"  [WARNING] Band '{band}' has only {n} institutions (< 10)")
        boundary_ok = False
    elif n < 30:
        print(f"  [INFO] Band '{band}' has {n} institutions (small but acceptable)")
    else:
        print(f"  [PASS] Band '{band}' has {n} institutions")

# Check grad rate values are in plausible range (0-100)
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    median_gr = row["grad_rate_150pct_median"]
    mean_gr = row["grad_rate_150pct_mean"]
    if median_gr < 0 or median_gr > 100:
        print(f"  [FAIL] {band}: median grad rate {median_gr} outside 0-100")
        boundary_ok = False
    if mean_gr < 0 or mean_gr > 100:
        print(f"  [FAIL] {band}: mean grad rate {mean_gr} outside 0-100")
        boundary_ok = False

if boundary_ok:
    print(f"  [PASS] All grad rate values in plausible range")

# Check admission_rate values are in 0-1 range
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    adm_median = row["admission_rate_median"]
    if adm_median < 0 or adm_median > 1:
        print(f"  [FAIL] {band}: admission_rate_median {adm_median} outside 0-1")
        boundary_ok = False

# --- Check 9: [Absence] Are expected metrics missing? ---
print("\n--- Check 9: [Absence] Metric completeness ---")
# Check ALL metric columns (not just critical) for nulls across all rows
absence_issues = []
for col in EXPECTED_COLUMNS:
    if col in df.columns:
        nc = df[col].null_count()
        if nc > 0:
            absence_issues.append(f"{col}: {nc} nulls")
absence_ok = len(absence_issues) == 0
print(f"[{'PASS' if absence_ok else 'WARN'}] All metrics present: ", end="")
print("Yes" if absence_ok else f"Missing: {'; '.join(absence_issues)}")

# Check: does the Plan specify IQR (Q1/Q3) for grad_rate? Verify those columns exist.
has_iqr = "grad_rate_150pct_q1" in df.columns and "grad_rate_150pct_q3" in df.columns
print(f"[{'PASS' if has_iqr else 'FAIL'}] IQR columns (Q1/Q3) for grad_rate present: {has_iqr}")

# Check: does the Plan specify std for grad_rate?
has_std = "grad_rate_150pct_std" in df.columns
print(f"[{'PASS' if has_std else 'FAIL'}] Std column for grad_rate present: {has_std}")

# Check: is grad_rate_150pct_count present (non-null count)?
has_count = "grad_rate_150pct_count" in df.columns
print(f"[{'PASS' if has_count else 'INFO'}] Non-null count for grad_rate present: {has_count}")

# --- Check 10: [Downstream] Will downstream consumers be surprised? ---
print("\n--- Check 10: [Downstream] Downstream compatibility ---")
# Downstream scripts: crosstab, outperformers, report-writer, viz-boxplot
# They need to know band names and basic structure
# Check: are band names strings (not categorical with codes)?
band_type = str(df["selectivity_band"].dtype)
downstream_ok = "Utf8" in band_type or "String" in band_type
print(f"[{'PASS' if downstream_ok else 'WARN'}] selectivity_band dtype is string: {band_type}")

# Check: is the ordering correct in the output (most selective first)?
band_order_in_output = df["selectivity_band"].to_list()
expected_order = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
order_correct = band_order_in_output == expected_order
print(f"[{'PASS' if order_correct else 'WARN'}] Band ordering in output: {band_order_in_output}")
if not order_correct:
    print(f"  Expected: {expected_order}")

# ========================================================================
# SPOT-CHECKS (5 concrete verifications)
# ========================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recalculate one band's median grad_rate from source ---
print("\n--- Spot-Check 11: Recalculate 'Selective' band median grad_rate ---")
selective_source = source_df.filter(pl.col("selectivity_band") == "Selective")
recalc_median = selective_source["grad_rate_150pct"].median()
reported_median = df.filter(pl.col("selectivity_band") == "Selective")["grad_rate_150pct_median"][0]
median_match = abs(recalc_median - reported_median) < 0.01
print(f"  Recalculated from source: {recalc_median:.4f}")
print(f"  Reported in output:       {reported_median:.4f}")
print(f"  [{'PASS' if median_match else 'FAIL'}] Match: difference = {abs(recalc_median - reported_median):.6f}")

# --- Spot-Check 12: Verify n values match source counts ---
print("\n--- Spot-Check 12: Verify n values against source data ---")
n_sum = df["n"].sum()
source_total = source_df.shape[0]
n_sum_ok = n_sum == source_total
print(f"  Sum of n values: {n_sum}")
print(f"  Source total rows: {source_total}")
print(f"  [{'PASS' if n_sum_ok else 'FAIL'}] n sum == source total: {n_sum_ok}")

# Verify each band count individually
for band in EXPECTED_BANDS:
    source_count = source_df.filter(pl.col("selectivity_band") == band).shape[0]
    output_n = df.filter(pl.col("selectivity_band") == band)["n"][0]
    match = source_count == output_n
    print(f"  [{'PASS' if match else 'FAIL'}] {band}: source={source_count}, output_n={output_n}")

# --- Spot-Check 13: Verify admission_rate ranges by band ---
print("\n--- Spot-Check 13: Verify admission_rate consistency per band ---")
for band in EXPECTED_BANDS:
    band_source = source_df.filter(pl.col("selectivity_band") == band)
    source_adm_median = band_source["admission_rate"].median()
    output_adm_median = df.filter(pl.col("selectivity_band") == band)["admission_rate_median"][0]
    match = abs(source_adm_median - output_adm_median) < 0.001 if source_adm_median is not None and output_adm_median is not None else False
    print(f"  {band}: source_median={source_adm_median:.4f}, output={output_adm_median:.4f}, [{'PASS' if match else 'FAIL'}]")

# --- Spot-Check 14: Verify grad_rate_150pct_count + nulls = n ---
print("\n--- Spot-Check 14: Verify non-null count + nulls = n ---")
for band in EXPECTED_BANDS:
    band_source = source_df.filter(pl.col("selectivity_band") == band)
    total_n = band_source.shape[0]
    non_null = band_source.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]
    null_count = total_n - non_null
    output_count = int(df.filter(pl.col("selectivity_band") == band)["grad_rate_150pct_count"][0])
    output_n = int(df.filter(pl.col("selectivity_band") == band)["n"][0])
    match = output_count + null_count == output_n and output_count == non_null
    print(f"  {band}: n={output_n}, count={output_count}, nulls_in_source={null_count}, "
          f"count+nulls={output_count + null_count}, [{'PASS' if match else 'FAIL'}]")

# --- Spot-Check 15: Verify Q1 < median < Q3 for grad_rate (sanity) ---
print("\n--- Spot-Check 15: Verify Q1 <= median <= Q3 for grad_rate ---")
quartile_ok = True
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    q1 = row["grad_rate_150pct_q1"]
    median = row["grad_rate_150pct_median"]
    q3 = row["grad_rate_150pct_q3"]
    ok = q1 <= median <= q3
    if not ok:
        print(f"  [FAIL] {band}: Q1={q1:.1f}, Median={median:.1f}, Q3={q3:.1f}")
        quartile_ok = False
    else:
        print(f"  [PASS] {band}: Q1={q1:.1f} <= Median={median:.1f} <= Q3={q3:.1f}")

# ========================================================================
# DATA PROFILING (for cra2+ decision)
# ========================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull output data:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nSource data selectivity_band value counts:")
print(source_df["selectivity_band"].value_counts().sort("selectivity_band"))

print("\nSource data grad_rate_150pct null rate by band:")
for band in EXPECTED_BANDS:
    band_data = source_df.filter(pl.col("selectivity_band") == band)
    total = band_data.shape[0]
    non_null = band_data.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]
    null_rate = (total - non_null) / total * 100 if total > 0 else 0
    print(f"  {band}: {total} total, {non_null} non-null, {null_rate:.1f}% null")

print("\nSource data: admission_rate summary by band:")
for band in EXPECTED_BANDS:
    band_data = source_df.filter(pl.col("selectivity_band") == band)
    adm = band_data["admission_rate"].drop_nulls()
    if len(adm) > 0:
        print(f"  {band}: min={adm.min():.3f}, max={adm.max():.3f}, "
              f"median={adm.median():.3f}, mean={adm.mean():.3f}, n_non_null={len(adm)}")
    else:
        print(f"  {band}: no non-null admission_rate values")

# ========================================================================
# SUMMARY
# ========================================================================

print("\n" + "=" * 60)
all_default = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific = all([bands_match, bands_counterfactual_ok, semantic_ok, boundary_ok, absence_ok, downstream_ok])
all_spot = all([median_match, n_sum_ok, quartile_ok])

all_passed = all_default and all_specific and all_spot
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA4a RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:54:25
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_01_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA4a INSPECTION: Stage 8 Step 01 — descriptive-by-selectivity
# ============================================================
# Loaded output: 4 rows x 18 cols
# Loaded source: 2,528 rows x 26 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 4 (expected exactly 4)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: [Counterfactual] Band completeness ---
# [PASS] Bands match expected: ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
#   Source data: 0 rows with null selectivity_band
#   [PASS] No null selectivity_band in source — group_by covers all rows
# 
# --- Check 7: [Semantic] Research question alignment ---
#   Top band median: 92.3%, Bottom band median: 53.7%
#   Spread: 38.6 percentage points
#   [PASS] Gradient is substantial (38.6pp)
# 
# --- Check 8: [Boundary] Small bands and extreme values ---
#   [PASS] Band 'Highly Selective' has 73 institutions
#   [PASS] Band 'Selective' has 174 institutions
#   [PASS] Band 'Moderately Selective' has 586 institutions
#   [PASS] Band 'Less Selective/Open' has 1695 institutions
#   [PASS] All grad rate values in plausible range
# 
# --- Check 9: [Absence] Metric completeness ---
# [PASS] All metrics present: Yes
# [PASS] IQR columns (Q1/Q3) for grad_rate present: True
# [PASS] Std column for grad_rate present: True
# [PASS] Non-null count for grad_rate present: True
# 
# --- Check 10: [Downstream] Downstream compatibility ---
# [PASS] selectivity_band dtype is string: String
# [PASS] Band ordering in output: ['Highly Selective', 'Selective', 'Moderately Selective', 'Less Selective/Open']
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-Check 11: Recalculate 'Selective' band median grad_rate ---
#   Recalculated from source: 63.6000
#   Reported in output:       63.6000
#   [PASS] Match: difference = 0.000000
# 
# --- Spot-Check 12: Verify n values against source data ---
#   Sum of n values: 2528
#   Source total rows: 2528
#   [PASS] n sum == source total: True
#   [PASS] Highly Selective: source=73, output_n=73
#   [PASS] Selective: source=174, output_n=174
#   [PASS] Moderately Selective: source=586, output_n=586
#   [PASS] Less Selective/Open: source=1695, output_n=1695
# 
# --- Spot-Check 13: Verify admission_rate consistency per band ---
#   Highly Selective: source_median=0.1433, output=0.1433, [PASS]
#   Selective: source_median=0.4010, output=0.4010, [PASS]
#   Moderately Selective: source_median=0.6530, output=0.6530, [PASS]
#   Less Selective/Open: source_median=0.8572, output=0.8572, [PASS]
# 
# --- Spot-Check 14: Verify non-null count + nulls = n ---
#   Highly Selective: n=73, count=69, nulls_in_source=4, count+nulls=73, [PASS]
#   Selective: n=174, count=159, nulls_in_source=15, count+nulls=174, [PASS]
#   Moderately Selective: n=586, count=564, nulls_in_source=22, count+nulls=586, [PASS]
#   Less Selective/Open: n=1695, count=1004, nulls_in_source=691, count+nulls=1695, [PASS]
# 
# --- Spot-Check 15: Verify Q1 <= median <= Q3 for grad_rate ---
#   [PASS] Highly Selective: Q1=89.3 <= Median=92.3 <= Q3=94.1
#   [PASS] Selective: Q1=43.6 <= Median=63.6 <= Q3=83.5
#   [PASS] Moderately Selective: Q1=46.7 <= Median=58.8 <= Q3=70.6
#   [PASS] Less Selective/Open: Q1=39.7 <= Median=53.7 <= Q3=65.0
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full output data:
# shape: (4, 18)
# ┌────────────┬──────┬────────────┬────────────┬───┬────────────┬───────────┬───────────┬───────────┐
# │ selectivit ┆ n    ┆ grad_rate_ ┆ grad_rate_ ┆ … ┆ student_fa ┆ student_f ┆ retention ┆ retention │
# │ y_band     ┆ ---  ┆ 150pct_med ┆ 150pct_mea ┆   ┆ culty_rati ┆ aculty_ra ┆ _rate_med ┆ _rate_mea │
# │ ---        ┆ u32  ┆ ian        ┆ n          ┆   ┆ o_median   ┆ tio_mean  ┆ ian       ┆ n         │
# │ str        ┆      ┆ ---        ┆ ---        ┆   ┆ ---        ┆ ---       ┆ ---       ┆ ---       │
# │            ┆      ┆ f64        ┆ f64        ┆   ┆ f64        ┆ f64       ┆ f64       ┆ f64       │
# ╞════════════╪══════╪════════════╪════════════╪═══╪════════════╪═══════════╪═══════════╪═══════════╡
# │ Highly     ┆ 73   ┆ 92.3       ┆ 88.544928  ┆ … ┆ 8.0        ┆ 8.315068  ┆ 92.0      ┆ 89.542857 │
# │ Selective  ┆      ┆            ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Selective  ┆ 174  ┆ 63.6       ┆ 62.654088  ┆ … ┆ 11.0       ┆ 12.695402 ┆ 81.5      ┆ 76.67284  │
# │ Moderately ┆ 586  ┆ 58.85      ┆ 57.665071  ┆ … ┆ 13.0       ┆ 13.539249 ┆ 76.0      ┆ 75.487889 │
# │ Selective  ┆      ┆            ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Less Selec ┆ 1695 ┆ 53.7       ┆ 52.467032  ┆ … ┆ 14.0       ┆ 14.181132 ┆ 75.0      ┆ 72.139906 │
# │ tive/Open  ┆      ┆            ┆            ┆   ┆            ┆           ┆           ┆           │
# └────────────┴──────┴────────────┴────────────┴───┴────────────┴───────────┴───────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 19)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ selectivi ┆ n         ┆ grad_rate ┆ … ┆ student_f ┆ student_f ┆ retention ┆ retentio │
# │ ---       ┆ ty_band   ┆ ---       ┆ _150pct_m ┆   ┆ aculty_ra ┆ aculty_ra ┆ _rate_med ┆ n_rate_m │
# │ str       ┆ ---       ┆ f64       ┆ edian     ┆   ┆ tio_media ┆ tio_mean  ┆ ian       ┆ ean      │
# │           ┆ str       ┆           ┆ ---       ┆   ┆ n         ┆ ---       ┆ ---       ┆ ---      │
# │           ┆           ┆           ┆ f64       ┆   ┆ ---       ┆ f64       ┆ f64       ┆ f64      │
# │           ┆           ┆           ┆           ┆   ┆ f64       ┆           ┆           ┆          │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 4         ┆ 4.0       ┆ 4.0       ┆ … ┆ 4.0       ┆ 4.0       ┆ 4.0       ┆ 4.0      │
# │ null_coun ┆ 0         ┆ 0.0       ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0      │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ null      ┆ 632.0     ┆ 67.1125   ┆ … ┆ 11.5      ┆ 12.182713 ┆ 81.125    ┆ 78.46087 │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ 3        │
# │ std       ┆ null      ┆ 742.59230 ┆ 17.271478 ┆ … ┆ 2.645751  ┆ 2.649238  ┆ 7.792892  ┆ 7.633276 │
# │           ┆           ┆ 6         ┆           ┆   ┆           ┆           ┆           ┆          │
# │ min       ┆ Highly    ┆ 73.0      ┆ 53.7      ┆ … ┆ 8.0       ┆ 8.315068  ┆ 75.0      ┆ 72.13990 │
# │           ┆ Selective ┆           ┆           ┆   ┆           ┆           ┆           ┆ 6        │
# │ 25%       ┆ null      ┆ 174.0     ┆ 58.85     ┆ … ┆ 11.0      ┆ 12.695402 ┆ 76.0      ┆ 75.48788 │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ 9        │
# │ 50%       ┆ null      ┆ 586.0     ┆ 63.6      ┆ … ┆ 13.0      ┆ 13.539249 ┆ 81.5      ┆ 76.67284 │
# │ 75%       ┆ null      ┆ 586.0     ┆ 63.6      ┆ … ┆ 13.0      ┆ 13.539249 ┆ 81.5      ┆ 76.67284 │
# │ max       ┆ Selective ┆ 1695.0    ┆ 92.3      ┆ … ┆ 14.0      ┆ 14.181132 ┆ 92.0      ┆ 89.54285 │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ 7        │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Source data selectivity_band value counts:
# shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ str                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Highly Selective     ┆ 73    │
# │ Less Selective/Open  ┆ 1695  │
# │ Moderately Selective ┆ 586   │
# │ Selective            ┆ 174   │
# └──────────────────────┴───────┘
# 
# Source data grad_rate_150pct null rate by band:
#   Highly Selective: 73 total, 69 non-null, 5.5% null
#   Selective: 174 total, 159 non-null, 8.6% null
#   Moderately Selective: 586 total, 564 non-null, 3.8% null
#   Less Selective/Open: 1695 total, 1004 non-null, 40.8% null
# 
# Source data: admission_rate summary by band:
#   Highly Selective: min=0.000, max=0.245, median=0.143, mean=0.144, n_non_null=73
#   Selective: min=0.250, max=0.500, median=0.401, mean=0.400, n_non_null=174
#   Moderately Selective: min=0.500, max=0.750, median=0.653, mean=0.644, n_non_null=586
#   Less Selective/Open: min=0.750, max=1.000, median=0.857, mean=0.865, n_non_null=826
# 
# ============================================================
# QA4a RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
