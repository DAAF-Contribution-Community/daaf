#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 7.2 (QA4a — Statistical Validity)

Reviewed script: scripts/stage8_analysis/01_crosstab-selectivity-pell.py
Output files: output/analysis/2026-02-15_crosstab_selectivity_pell.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks:
1. Schema matches Plan expectations
2. Row count within expected range (16 cells for 4x4)
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns
--- Script-Specific Checks (Five Lenses) ---
6. [Counterfactual] What if filtering removed a biased subset? Check whether
   dropped rows systematically differ from kept rows on selectivity_band.
7. [Semantic] Does the code answer the research question — "Within selectivity
   bands, does Pell share explain meaningful graduation rate variation"?
8. [Boundary] The Highly Selective x Very High Pell cell has n=1. Does this
   single-institution cell distort the within-band spread calculation?
9. [Absence] Plan says "Filter to rows where selectivity_band and pell_band are
   non-null" but script also filters grad_rate_150pct non-null. Is this an
   unrequested additional filter that might change results?
10. [Downstream] The heatmap viz task (9.3) depends on this output. Does the
    output schema and format match what the viz task expects?
--- Spot-Checks ---
11. Verify n values sum to the filtered row count (1,704)
12. Recalculate one cell's mean grad rate independently from the source data
13. Verify selectivity band label consistency (the CP3 check flagged a mismatch)
14. Check whether the 62.5 pp spread for Highly Selective is meaningful given
    two sparse cells (n=3, n=1)
15. Verify grad rates are in 0-100 range in output AND source data
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_crosstab_selectivity_pell.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
EXPECTED_COLUMNS = ["selectivity_band", "pell_band", "n", "mean_grad_rate", "median_grad_rate"]
EXPECTED_MIN_ROWS = 10   # At least 10 of 16 possible cells should be populated
EXPECTED_MAX_ROWS = 20   # At most 16 (4x4) + small margin
CRITICAL_COLUMNS = ["selectivity_band", "pell_band", "n", "mean_grad_rate", "median_grad_rate"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 7.2 (QA4a)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load the source analysis dataset for cross-referencing
source = pl.read_parquet(INPUT_FILE)
print(f"Loaded source: {source.shape[0]:,} rows x {source.shape[1]} cols")

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
print(f"  Exactly 16 cells for 4x4 grid: {'YES' if row_count == 16 else 'NO'}")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64, pl.Int32, pl.UInt32)).columns:
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
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt32]:
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

# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses + 5 Spot-Checks)
# ============================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Filtering bias ---
# The script drops rows where any of selectivity_band, pell_band, or
# grad_rate_150pct are null. Check if the dropped rows are biased toward
# a particular selectivity band.
print("\n--- Check 6: [Counterfactual] Filtering bias ---")
all_sel = source.group_by("selectivity_band").len().sort("selectivity_band")
filtered_source = source.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("pell_band").is_not_null()
    & pl.col("grad_rate_150pct").is_not_null()
)
kept_sel = filtered_source.group_by("selectivity_band").len().sort("selectivity_band")

print("Selectivity band distribution: All vs Filtered")
print(f"  {'Band':<35} {'All':>6} {'Kept':>6} {'Kept%':>7}")
for a_row in all_sel.iter_rows(named=True):
    band = a_row["selectivity_band"]
    a_n = a_row["len"]
    k_rows = kept_sel.filter(pl.col("selectivity_band") == band)
    k_n = k_rows["len"][0] if len(k_rows) > 0 else 0
    pct = k_n / a_n * 100 if a_n > 0 else 0
    print(f"  {str(band):<35} {a_n:>6} {k_n:>6} {pct:>6.1f}%")

# Check if any band lost more than 50% of its rows
filter_bias_ok = True
for a_row in all_sel.iter_rows(named=True):
    band = a_row["selectivity_band"]
    if band is None:
        continue
    a_n = a_row["len"]
    k_rows = kept_sel.filter(pl.col("selectivity_band") == band)
    k_n = k_rows["len"][0] if len(k_rows) > 0 else 0
    if a_n > 0 and k_n / a_n < 0.50:
        print(f"  [WARNING] {band} retained only {k_n/a_n:.1%} of rows")
        filter_bias_ok = False

print(f"[{'PASS' if filter_bias_ok else 'WARN'}] Filtering bias: ", end="")
print("No band lost >50% of rows" if filter_bias_ok else "Some bands disproportionately affected")

# --- Check 7: [Semantic] Does the code answer the research question? ---
print("\n--- Check 7: [Semantic] Research question alignment ---")
# The observable truth: "Within selectivity bands, Pell share still explains
# meaningful graduation rate variation."
# The script groups by selectivity x pell, computes mean/median grad rate, and
# calculates within-band spreads. This directly addresses the truth.
# Verify the interpretation logic: all 4 bands with >5pp spread = SUPPORTED.
bands_in_output = df["selectivity_band"].unique().to_list()
pell_bands_in_output = df["pell_band"].unique().to_list()
print(f"Selectivity bands in output: {sorted(str(b) for b in bands_in_output)}")
print(f"Pell bands in output: {sorted(str(b) for b in pell_bands_in_output)}")
has_4_sel = len(bands_in_output) == 4
has_4_pell = len(pell_bands_in_output) == 4
print(f"[{'PASS' if has_4_sel else 'WARN'}] 4 selectivity bands present: {has_4_sel}")
print(f"[{'PASS' if has_4_pell else 'WARN'}] 4 Pell bands present: {has_4_pell}")

# Verify within-band spread calculation for one band
sel_example = "Moderately Selective"
band_data = df.filter(pl.col("selectivity_band") == sel_example)
if len(band_data) > 0:
    spread = band_data["mean_grad_rate"].max() - band_data["mean_grad_rate"].min()
    print(f"  Verified spread for '{sel_example}': {spread:.1f} pp (expect ~42.9 pp from log)")
    semantic_ok = abs(spread - 42.9) < 1.0
    print(f"  [{'PASS' if semantic_ok else 'FAIL'}] Spread matches execution log")
else:
    print(f"  [FAIL] No data for '{sel_example}' band")
    semantic_ok = False

# --- Check 8: [Boundary] Sparse cell impact on Highly Selective spread ---
print("\n--- Check 8: [Boundary] Sparse cell impact ---")
hs_data = df.filter(pl.col("selectivity_band") == "Highly Selective")
print(f"Highly Selective cells:")
for row in hs_data.sort("pell_band").iter_rows(named=True):
    sparse_flag = " [SPARSE]" if row["n"] < 10 else ""
    print(f"  {row['pell_band']:<25} n={row['n']:>4}  mean={row['mean_grad_rate']:.1f}%{sparse_flag}")

hs_full_spread = hs_data["mean_grad_rate"].max() - hs_data["mean_grad_rate"].min()
# Compute spread excluding sparse cells (n < 10)
hs_robust = hs_data.filter(pl.col("n") >= 10)
if len(hs_robust) >= 2:
    hs_robust_spread = hs_robust["mean_grad_rate"].max() - hs_robust["mean_grad_rate"].min()
    print(f"\n  Full spread (all 4 cells): {hs_full_spread:.1f} pp")
    print(f"  Robust spread (n>=10 only): {hs_robust_spread:.1f} pp")
    print(f"  Sparse cells inflate spread by: {hs_full_spread - hs_robust_spread:.1f} pp")
    # Even robust spread should show meaningful variation
    boundary_ok = True  # The sparse cells are flagged in the script; this is a WARNING, not BLOCKER
    if hs_robust_spread < 5:
        print(f"  [WARN] Robust spread for Highly Selective is only {hs_robust_spread:.1f} pp")
        boundary_ok = False
    else:
        print(f"  [PASS] Even robust spread shows meaningful variation")
else:
    print(f"  [WARN] Only {len(hs_robust)} non-sparse cells in Highly Selective; cannot compute robust spread")
    boundary_ok = False

# --- Check 9: [Absence] Extra grad_rate filter ---
print("\n--- Check 9: [Absence] Extra grad_rate_150pct filter ---")
# Plan says filter to non-null selectivity_band and pell_band.
# Script also filters grad_rate_150pct non-null.
# This is sensible (can't compute mean without values) but does it change n?
without_grad_filter = source.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("pell_band").is_not_null()
)
with_grad_filter = source.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("pell_band").is_not_null()
    & pl.col("grad_rate_150pct").is_not_null()
)
diff_n = len(without_grad_filter) - len(with_grad_filter)
print(f"  Without grad_rate filter: {len(without_grad_filter):,} rows")
print(f"  With grad_rate filter: {len(with_grad_filter):,} rows")
print(f"  Additional rows dropped by grad filter: {diff_n}")
if diff_n > 0:
    # This means some institutions have selectivity + pell bands but no grad rate
    pct_extra_drop = diff_n / len(without_grad_filter) * 100
    print(f"  Extra drop rate: {pct_extra_drop:.1f}%")
    absence_ok = pct_extra_drop < 20  # Under 20% is reasonable
    print(f"  [{'PASS' if absence_ok else 'WARN'}] Extra filter drops {'<20%' if absence_ok else '>=20%'} additional rows")
else:
    print(f"  [PASS] No additional rows dropped by grad_rate filter")
    absence_ok = True

# --- Check 10: [Downstream] Output format for heatmap viz ---
print("\n--- Check 10: [Downstream] Output format for viz-heatmap task ---")
# The viz-heatmap-selectivity-pell task (9.3) will load this parquet and
# create a heatmap. It needs: selectivity_band, pell_band, and a grad rate value.
# The long format (not pivoted) is actually what plotnine geom_tile expects.
has_sel = "selectivity_band" in df.columns
has_pell = "pell_band" in df.columns
has_mean = "mean_grad_rate" in df.columns
has_n = "n" in df.columns
downstream_ok = has_sel and has_pell and has_mean and has_n
print(f"  selectivity_band present: {has_sel}")
print(f"  pell_band present: {has_pell}")
print(f"  mean_grad_rate present: {has_mean}")
print(f"  n present (for cell annotations): {has_n}")
print(f"  [{'PASS' if downstream_ok else 'FAIL'}] Output suitable for downstream heatmap task")

# Note: Plan says "Pivot into matrix format" but long format is actually
# better for plotnine's geom_tile. This is a deviation from Plan letter
# but aligned with Plan intent (produce data the heatmap can consume).
print(f"  [INFO] Script saves long format, not pivoted matrix. This is a deviation from")
print(f"         Plan action step 6 ('Pivot into matrix format') but long format is what")
print(f"         plotnine geom_tile expects. Acceptable deviation.")

# --- Spot-Check 11: N values sum to filtered count ---
print("\n--- Spot-Check 11: N sum validation ---")
total_n = df["n"].sum()
expected_total = 1704  # From execution log
n_sum_ok = total_n == expected_total
print(f"  Sum of n across all cells: {total_n}")
print(f"  Expected (filtered row count): {expected_total}")
print(f"  [{'PASS' if n_sum_ok else 'FAIL'}] N values sum correctly: {n_sum_ok}")

# --- Spot-Check 12: Recalculate one cell's mean independently ---
print("\n--- Spot-Check 12: Independent recalculation ---")
# Pick Moderately Selective x Moderate Pell (a non-sparse, mid-size cell)
check_sel = "Moderately Selective"
check_pell = "Moderate Pell (20-40%)"
independent_data = filtered_source.filter(
    (pl.col("selectivity_band") == check_sel)
    & (pl.col("pell_band") == check_pell)
)
independent_mean = independent_data["grad_rate_150pct"].mean()
independent_median = independent_data["grad_rate_150pct"].median()
independent_n = len(independent_data)

output_row = df.filter(
    (pl.col("selectivity_band") == check_sel)
    & (pl.col("pell_band") == check_pell)
)
if len(output_row) > 0:
    output_mean = output_row["mean_grad_rate"][0]
    output_median = output_row["median_grad_rate"][0]
    output_n = output_row["n"][0]

    mean_match = abs(independent_mean - output_mean) < 0.1
    median_match = abs(independent_median - output_median) < 0.1
    n_match = independent_n == output_n

    print(f"  Cell: {check_sel} x {check_pell}")
    print(f"  Independent:  n={independent_n}, mean={independent_mean:.2f}, median={independent_median:.2f}")
    print(f"  Output:       n={output_n}, mean={output_mean:.2f}, median={output_median:.2f}")
    print(f"  [{'PASS' if mean_match else 'FAIL'}] Mean matches: {mean_match}")
    print(f"  [{'PASS' if median_match else 'FAIL'}] Median matches: {median_match}")
    print(f"  [{'PASS' if n_match else 'FAIL'}] N matches: {n_match}")
    recalc_ok = mean_match and median_match and n_match
else:
    print(f"  [FAIL] Cell not found in output")
    recalc_ok = False

# --- Spot-Check 13: Selectivity band label consistency ---
print("\n--- Spot-Check 13: Band label consistency ---")
# The CP3 check found "Less Selective/Open" in data but expected
# "Less Selective/Open Admission". Check what the create-bands script produced.
source_sel_bands = set(source["selectivity_band"].drop_nulls().unique().to_list())
output_sel_bands = set(df["selectivity_band"].unique().to_list())
print(f"  Source data bands: {sorted(source_sel_bands)}")
print(f"  Output bands: {sorted(output_sel_bands)}")

# Check if "Less Selective/Open Admission" was expected by Plan
expected_plan_bands = {"Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open Admission"}
actual_bands = source_sel_bands
plan_mismatch = expected_plan_bands.symmetric_difference(actual_bands)
if plan_mismatch:
    print(f"  Plan expected: {sorted(expected_plan_bands)}")
    print(f"  Actual bands: {sorted(actual_bands)}")
    print(f"  Mismatch: {plan_mismatch}")
    # This is a cosmetic issue — the create-bands script used "Less Selective/Open"
    # instead of "Less Selective/Open Admission". The cross-tab script correctly
    # works with whatever bands exist. Not a correctness issue.
    print(f"  [INFO] Band label 'Less Selective/Open' differs from Plan's 'Less Selective/Open Admission'.")
    print(f"         This is a Stage 7 (create-bands) decision, not a cross-tab error.")
    label_ok = True  # Not a BLOCKER for this script
else:
    print(f"  [PASS] Band labels match Plan expectations")
    label_ok = True

# --- Spot-Check 14: Robust spread for Highly Selective ---
print("\n--- Spot-Check 14: Highly Selective spread robustness ---")
# The 62.5 pp spread for Highly Selective is driven by sparse cells.
# What would a user conclude if they saw only the non-sparse cells?
hs_nonsparse = hs_data.filter(pl.col("n") >= 10)
if len(hs_nonsparse) >= 2:
    min_mean = hs_nonsparse["mean_grad_rate"].min()
    max_mean = hs_nonsparse["mean_grad_rate"].max()
    robust_spread = max_mean - min_mean
    print(f"  Non-sparse Highly Selective cells:")
    for row in hs_nonsparse.sort("pell_band").iter_rows(named=True):
        print(f"    {row['pell_band']}: n={row['n']}, mean={row['mean_grad_rate']:.1f}%")
    print(f"  Robust spread: {robust_spread:.1f} pp")
    print(f"  Full spread (incl. sparse): {hs_full_spread:.1f} pp")
    if robust_spread > 5:
        print(f"  [PASS] Even excluding sparse cells, meaningful variation exists")
    else:
        print(f"  [INFO] Robust spread is small; 62.5 pp headline is driven by sparse cells")
else:
    print(f"  [INFO] Insufficient non-sparse cells to compute robust spread")

# --- Spot-Check 15: Grad rate range in output AND source ---
print("\n--- Spot-Check 15: Grad rate range validation ---")
out_min_mean = df["mean_grad_rate"].min()
out_max_mean = df["mean_grad_rate"].max()
out_min_med = df["median_grad_rate"].min()
out_max_med = df["median_grad_rate"].max()
src_min = filtered_source["grad_rate_150pct"].min()
src_max = filtered_source["grad_rate_150pct"].max()

print(f"  Output mean_grad_rate range: [{out_min_mean:.1f}, {out_max_mean:.1f}]")
print(f"  Output median_grad_rate range: [{out_min_med:.1f}, {out_max_med:.1f}]")
print(f"  Source grad_rate_150pct range: [{src_min:.1f}, {src_max:.1f}]")

range_ok = (
    out_min_mean >= 0 and out_max_mean <= 100
    and out_min_med >= 0 and out_max_med <= 100
    and src_min >= 0 and src_max <= 100
)
print(f"  [{'PASS' if range_ok else 'FAIL'}] All grad rates in 0-100 range")

# Sanity: cell means should be within the source range
means_in_src_range = out_min_mean >= src_min and out_max_mean <= src_max
print(f"  [{'PASS' if means_in_src_range else 'WARN'}] Cell means within source data range")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

all_checks = {
    "Schema": schema_ok,
    "Row count": rows_ok,
    "Distributions": dist_ok,
    "Coded values": coded_ok,
    "Critical nulls": nulls_ok,
    "Filter bias [Counterfactual]": filter_bias_ok,
    "Research question [Semantic]": semantic_ok,
    "Downstream format": downstream_ok,
    "N sum": n_sum_ok,
    "Recalculation": recalc_ok,
    "Grad rate range": range_ok,
}

all_passed = all(all_checks.values())
for check_name, status in all_checks.items():
    print(f"  [{'PASS' if status else 'FAIL'}] {check_name}")

print(f"\n{'=' * 60}")
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
print(f"{'=' * 60}")

# --- Data Profiling (for cra2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull cross-tabulation output (all 16 rows):")
print(df.sort("selectivity_band", "pell_band"))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["selectivity_band", "pell_band"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort(col))

print("\nN distribution across cells:")
print(f"  Min n: {df['n'].min()}")
print(f"  Max n: {df['n'].max()}")
print(f"  Mean n: {df['n'].mean():.1f}")
print(f"  Median n: {df['n'].median()}")
print(f"  Cells with n < 10: {df.filter(pl.col('n') < 10).shape[0]}")
print(f"  Cells with n < 30: {df.filter(pl.col('n') < 30).shape[0]}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:55:08
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_02_cra1.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 7.2 (QA4a)
# ============================================================
# Loaded output: 16 rows x 5 cols
# Loaded source: 2,528 rows x 26 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 16 (expected 10-20)
#   Exactly 16 cells for 4x4 grid: YES
# [PASS] Distributions: Look reasonable
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_02_cra1.py", line 98, in <module>
#     count = (df[col] == code).sum()
#              ^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/series/series.py", line 952, in __eq__
#     return self._comp(other, "eq")
#            ^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/series/series.py", line 940, in _comp
#     return self._from_pyseries(f(other))
#                                ^^^^^^^^
# OverflowError: out of range integral type conversion attempted
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
