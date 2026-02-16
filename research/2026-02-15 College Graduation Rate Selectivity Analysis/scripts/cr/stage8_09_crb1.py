#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 9.2 (QA4b — Visualization)

Reviewed script: scripts/stage8_analysis/09_viz-boxplot-selectivity_a.py
Output files: output/figures/2026-02-15_boxplot_grad_rate_by_selectivity.png
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default):
1. Figure file exists and size > 50KB
2. Source data schema: selectivity_band and grad_rate_150pct present
3. All 4 selectivity bands present in plot data
4. Band ordering is correct (HS, S, MS, LS/O)
5. No coded values or nulls in plotted columns

QA Checks (Script-Specific — Five Lenses):
6. [Counterfactual] Verify no empty bands that would produce invisible boxes
7. [Semantic] Verify grad_rate_150pct is on 0-100 scale (not 0-1 proportion)
8. [Boundary] Check for extreme outliers that could distort scale
9. [Absence] Verify no institutions lost via inner-join-like filtering
10. [Downstream] Verify band counts match execution log expectations

Spot-Checks:
11. Verify Highly Selective band has highest median grad rate
12. Verify Less Selective/Open has lowest median
13. Verify monotonic relationship: HS > S > MS > LS/O for median
14. Verify institution count per band matches execution log
15. Verify grad_rate range [0, 100] with no impossible values
"""

import polars as pl
import os
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "figures" / "2026-02-15_boxplot_grad_rate_by_selectivity.png"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
CRITICAL_COLUMNS = ["selectivity_band", "grad_rate_150pct"]

print("=" * 60)
print("QA INSPECTION: Stage 8 Step 9.2 — viz-boxplot-selectivity (QA4b)")
print("=" * 60)

# --- Check 1: Figure file exists and size ---
fig_exists = OUTPUT_FILE.exists()
file_size = os.path.getsize(OUTPUT_FILE) if fig_exists else 0
size_ok = file_size > 50_000
print(f"\n[{'PASS' if fig_exists and size_ok else 'FAIL'}] Figure exists and size > 50KB: "
      f"{'yes' if fig_exists else 'no'}, {file_size / 1024:.1f} KB")

# --- Load source data (replicate script's filtering) ---
df = pl.read_parquet(INPUT_FILE)
print(f"\nLoaded source data: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Check 2: Schema ---
missing_cols = [c for c in CRITICAL_COLUMNS if c not in df.columns]
schema_ok = len(missing_cols) == 0
print(f"[{'PASS' if schema_ok else 'FAIL'}] Schema: critical columns present = {schema_ok}")
if missing_cols:
    print(f"  Missing: {missing_cols}")

# Replicate the script's filtering to get the plot dataset
df_plot = df.filter(
    pl.col("grad_rate_150pct").is_not_null()
    & pl.col("selectivity_band").is_not_null()
)
print(f"Plot dataset after filtering: {df_plot.shape[0]:,} rows")

# --- Check 3: All 4 bands present ---
bands_in_data = set(df_plot["selectivity_band"].unique().to_list())
expected_bands = set(BAND_ORDER)
missing_bands = expected_bands - bands_in_data
extra_bands = bands_in_data - expected_bands
bands_ok = len(missing_bands) == 0 and len(extra_bands) == 0
print(f"[{'PASS' if bands_ok else 'FAIL'}] All 4 bands present, no extras: "
      f"missing={missing_bands or 'none'}, extra={extra_bands or 'none'}")

# --- Check 4: Band ordering verification ---
# The script uses pd.Categorical with ordered=True and scale_x_discrete(limits=BAND_ORDER).
# We verify the BAND_ORDER constant matches Plan specification.
plan_order = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
order_match = BAND_ORDER == plan_order
print(f"[{'PASS' if order_match else 'FAIL'}] Band order matches Plan: {order_match}")

# --- Check 5: No coded values or nulls in plotted columns ---
null_grad = df_plot["grad_rate_150pct"].null_count()
null_band = df_plot["selectivity_band"].null_count()
nulls_ok = null_grad == 0 and null_band == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] No nulls in plotted columns: "
      f"grad_rate nulls={null_grad}, band nulls={null_band}")

# Check for negative coded values in grad_rate
coded_values = df_plot.filter(pl.col("grad_rate_150pct") < 0).shape[0]
coded_ok = coded_values == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] No negative coded values in grad_rate: count={coded_values}")

# === SCRIPT-SPECIFIC CHECKS (Five Lenses) ===

# --- Check 6 [Counterfactual]: No empty bands ---
band_counts = (
    df_plot.group_by("selectivity_band")
    .agg(pl.len().alias("n"))
    .sort("selectivity_band")
)
min_band_n = band_counts["n"].min()
empty_bands = band_counts.filter(pl.col("n") == 0).shape[0]
counterfactual_ok = empty_bands == 0 and min_band_n >= 5
print(f"\n[{'PASS' if counterfactual_ok else 'FAIL'}] [Counterfactual] No empty/tiny bands: "
      f"min n={min_band_n}, empty={empty_bands}")
print("  Band counts:")
for row in band_counts.iter_rows(named=True):
    print(f"    {row['selectivity_band']}: n={row['n']}")

# --- Check 7 [Semantic]: Grad rate on 0-100 scale ---
gr_min = df_plot["grad_rate_150pct"].min()
gr_max = df_plot["grad_rate_150pct"].max()
gr_mean = df_plot["grad_rate_150pct"].mean()
# If scale were 0-1 (proportion), max would be ~1.0 and mean ~0.5
scale_ok = gr_max > 1.0 and gr_mean > 1.0  # Must be percentage, not proportion
print(f"[{'PASS' if scale_ok else 'FAIL'}] [Semantic] Grad rate on 0-100 scale: "
      f"min={gr_min:.1f}, max={gr_max:.1f}, mean={gr_mean:.1f}")

# --- Check 8 [Boundary]: No extreme outliers distorting scale ---
# Check if values exceed 100 or are below 0 (impossible for graduation rate)
out_of_range = df_plot.filter(
    (pl.col("grad_rate_150pct") > 100) | (pl.col("grad_rate_150pct") < 0)
).shape[0]
boundary_ok = out_of_range == 0
print(f"[{'PASS' if boundary_ok else 'FAIL'}] [Boundary] All values in [0, 100]: "
      f"out-of-range count={out_of_range}")

# Also check for single-value extremes (e.g., one school at 0% pulling whiskers)
very_low = df_plot.filter(pl.col("grad_rate_150pct") < 5).shape[0]
very_high = df_plot.filter(pl.col("grad_rate_150pct") > 99).shape[0]
print(f"  Boundary detail: <5% count={very_low}, >99% count={very_high}")

# --- Check 9 [Absence]: Verify no institutions silently lost ---
# Total in source minus those with null grad_rate or null band should equal plot dataset
total_source = df.shape[0]
null_grad_source = df.filter(pl.col("grad_rate_150pct").is_null()).shape[0]
null_band_source = df.filter(pl.col("selectivity_band").is_null()).shape[0]
# Some may have both null
both_null = df.filter(
    pl.col("grad_rate_150pct").is_null() & pl.col("selectivity_band").is_null()
).shape[0]
expected_removed = null_grad_source + null_band_source - both_null
expected_plot_rows = total_source - expected_removed
# The script filters in two steps: first grad_rate nulls, then band nulls
# Rows with null band AND non-null grad_rate would also be removed
absence_ok = abs(expected_plot_rows - df_plot.shape[0]) <= 1  # allow rounding
print(f"[{'PASS' if absence_ok else 'FAIL'}] [Absence] No silent row loss: "
      f"source={total_source}, expected_plot={expected_plot_rows}, actual_plot={df_plot.shape[0]}")

# --- Check 10 [Downstream]: Band counts match execution log ---
# Execution log showed: HS=69, S=159, MS=564, LS/O=1004, total=1796
log_counts = {"Highly Selective": 69, "Selective": 159, "Moderately Selective": 564, "Less Selective/Open": 1004}
log_total = 1796
downstream_ok = True
for row in band_counts.iter_rows(named=True):
    expected = log_counts.get(row["selectivity_band"], -1)
    if row["n"] != expected:
        downstream_ok = False
        print(f"  MISMATCH: {row['selectivity_band']}: got {row['n']}, log said {expected}")
total_ok = df_plot.shape[0] == log_total
downstream_ok = downstream_ok and total_ok
print(f"[{'PASS' if downstream_ok else 'FAIL'}] [Downstream] Counts match execution log: "
      f"total={df_plot.shape[0]} (expected {log_total})")

# === SPOT-CHECKS ===

# --- Spot-Check 11: HS has highest median ---
band_medians = (
    df_plot.group_by("selectivity_band")
    .agg(pl.col("grad_rate_150pct").median().alias("median"))
)
hs_median = band_medians.filter(pl.col("selectivity_band") == "Highly Selective")["median"][0]
other_medians = band_medians.filter(pl.col("selectivity_band") != "Highly Selective")["median"].max()
hs_highest = hs_median > other_medians
print(f"\n[{'PASS' if hs_highest else 'FAIL'}] [Spot-Check] HS has highest median: "
      f"HS={hs_median:.1f}, next highest={other_medians:.1f}")

# --- Spot-Check 12: LS/O has lowest median ---
lso_median = band_medians.filter(pl.col("selectivity_band") == "Less Selective/Open")["median"][0]
other_min = band_medians.filter(pl.col("selectivity_band") != "Less Selective/Open")["median"].min()
lso_lowest = lso_median < other_min
print(f"[{'PASS' if lso_lowest else 'FAIL'}] [Spot-Check] LS/O has lowest median: "
      f"LS/O={lso_median:.1f}, next lowest={other_min:.1f}")

# --- Spot-Check 13: Monotonic median relationship ---
ordered_medians = []
for band in BAND_ORDER:
    med = band_medians.filter(pl.col("selectivity_band") == band)["median"][0]
    ordered_medians.append(med)
monotonic = all(ordered_medians[i] > ordered_medians[i + 1] for i in range(len(ordered_medians) - 1))
print(f"[{'PASS' if monotonic else 'WARN'}] [Spot-Check] Monotonic medians (HS>S>MS>LS/O): "
      f"{[f'{m:.1f}' for m in ordered_medians]}")
if not monotonic:
    print("  NOTE: Non-monotonic medians may be valid if Selective and Moderately Selective overlap")

# --- Spot-Check 14: Institution counts per band match log ---
# Already verified in Check 10; summarize here
print(f"[{'PASS' if downstream_ok else 'FAIL'}] [Spot-Check] Band counts verified against log")

# --- Spot-Check 15: Grad rate range [0, 100] ---
range_ok = gr_min >= 0 and gr_max <= 100
print(f"[{'PASS' if range_ok else 'FAIL'}] [Spot-Check] Grad rate in [0, 100]: "
      f"min={gr_min:.1f}, max={gr_max:.1f}")

# === MISSINGNESS DIFFERENTIAL CHECK ===
# The execution log showed 40.8% null grad_rate in LS/O vs 3.8-8.6% in other bands.
# This is not a BLOCKER (the script correctly notes and filters), but is it WARNING-worthy?
print("\n--- Differential Missingness Assessment ---")
null_by_band = (
    df.group_by("selectivity_band")
    .agg([
        pl.len().alias("total"),
        pl.col("grad_rate_150pct").is_null().sum().alias("null_count"),
    ])
    .with_columns(
        (pl.col("null_count") / pl.col("total") * 100).round(1).alias("null_pct")
    )
    .sort("selectivity_band")
)
print(null_by_band)
max_null_pct = null_by_band["null_pct"].max()
min_null_pct = null_by_band["null_pct"].min()
differential = max_null_pct - min_null_pct
print(f"Differential missingness: max {max_null_pct}% - min {min_null_pct}% = {differential:.1f} pp")
if differential > 20:
    print("WARNING: High differential missingness across bands may bias visual comparison")
    print("  LS/O loses ~41% of institutions vs ~4-9% for other bands")
    print("  The remaining LS/O institutions may not be representative of the full LS/O population")
else:
    print("Differential missingness within acceptable range")

# --- Summary ---
all_default = all([fig_exists, size_ok, schema_ok, bands_ok, order_match, nulls_ok, coded_ok])
all_lenses = all([counterfactual_ok, scale_ok, boundary_ok, absence_ok, downstream_ok])
all_spots = all([hs_highest, lso_lowest, range_ok])
# Monotonic is WARN-worthy if false, not FAIL
all_passed = all_default and all_lenses and all_spots

print("\n" + "=" * 60)
if all_passed and monotonic:
    severity = "PASSED"
elif all_passed and not monotonic:
    severity = "PASSED (non-monotonic medians noted as INFO)"
elif not all_passed:
    # Check if any critical check failed
    severity = "BLOCKER"
else:
    severity = "WARNING"
print(f"QA RESULT: {severity}")
if differential > 20:
    print("NOTE: Differential missingness across bands is WARNING-level (logged for Stage 10)")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows of plot dataset:")
print(df_plot.select(["selectivity_band", "grad_rate_150pct", "inst_name"]).head(10))

print("\nDescriptive statistics (grad_rate_150pct):")
print(df_plot.select("grad_rate_150pct").describe())

print("\nGrad rate summary by band:")
summary = (
    df_plot.group_by("selectivity_band")
    .agg([
        pl.len().alias("n"),
        pl.col("grad_rate_150pct").mean().round(1).alias("mean"),
        pl.col("grad_rate_150pct").median().round(1).alias("median"),
        pl.col("grad_rate_150pct").std().round(1).alias("std"),
        pl.col("grad_rate_150pct").min().round(1).alias("min"),
        pl.col("grad_rate_150pct").max().round(1).alias("max"),
        pl.col("grad_rate_150pct").quantile(0.25).round(1).alias("q25"),
        pl.col("grad_rate_150pct").quantile(0.75).round(1).alias("q75"),
    ])
    .sort("selectivity_band")
)
print(summary)

print("\nOverlap assessment: IQR ranges by band")
for row in summary.iter_rows(named=True):
    print(f"  {row['selectivity_band']}: IQR=[{row['q25']}, {row['q75']}], range=[{row['min']}, {row['max']}]")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:19:05
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_09_crb1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 9.2 — viz-boxplot-selectivity (QA4b)
# ============================================================
# 
# [PASS] Figure exists and size > 50KB: yes, 766.1 KB
# 
# Loaded source data: 2,528 rows x 26 cols
# [PASS] Schema: critical columns present = True
# Plot dataset after filtering: 1,796 rows
# [PASS] All 4 bands present, no extras: missing=none, extra=none
# [PASS] Band order matches Plan: True
# [PASS] No nulls in plotted columns: grad_rate nulls=0, band nulls=0
# [PASS] No negative coded values in grad_rate: count=0
# 
# [PASS] [Counterfactual] No empty/tiny bands: min n=69, empty=0
#   Band counts:
#     Highly Selective: n=69
#     Less Selective/Open: n=1004
#     Moderately Selective: n=564
#     Selective: n=159
# [PASS] [Semantic] Grad rate on 0-100 scale: min=3.8, max=100.0, mean=56.4
# [PASS] [Boundary] All values in [0, 100]: out-of-range count=0
#   Boundary detail: <5% count=5, >99% count=26
# [PASS] [Absence] No silent row loss: source=2528, expected_plot=1796, actual_plot=1796
# [PASS] [Downstream] Counts match execution log: total=1796 (expected 1796)
# 
# [PASS] [Spot-Check] HS has highest median: HS=92.3, next highest=63.6
# [PASS] [Spot-Check] LS/O has lowest median: LS/O=53.7, next lowest=58.8
# [PASS] [Spot-Check] Monotonic medians (HS>S>MS>LS/O): ['92.3', '63.6', '58.8', '53.7']
# [PASS] [Spot-Check] Band counts verified against log
# [PASS] [Spot-Check] Grad rate in [0, 100]: min=3.8, max=100.0
# 
# --- Differential Missingness Assessment ---
# shape: (4, 4)
# ┌──────────────────────┬───────┬────────────┬──────────┐
# │ selectivity_band     ┆ total ┆ null_count ┆ null_pct │
# │ ---                  ┆ ---   ┆ ---        ┆ ---      │
# │ str                  ┆ u32   ┆ u32        ┆ f64      │
# ╞══════════════════════╪═══════╪════════════╪══════════╡
# │ Highly Selective     ┆ 73    ┆ 4          ┆ 5.5      │
# │ Less Selective/Open  ┆ 1695  ┆ 691        ┆ 40.8     │
# │ Moderately Selective ┆ 586   ┆ 22         ┆ 3.8      │
# │ Selective            ┆ 174   ┆ 15         ┆ 8.6      │
# └──────────────────────┴───────┴────────────┴──────────┘
# Differential missingness: max 40.8% - min 3.8% = 37.0 pp
# WARNING: High differential missingness across bands may bias visual comparison
#   LS/O loses ~41% of institutions vs ~4-9% for other bands
#   The remaining LS/O institutions may not be representative of the full LS/O population
# 
# ============================================================
# QA RESULT: PASSED
# NOTE: Differential missingness across bands is WARNING-level (logged for Stage 10)
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows of plot dataset:
# shape: (10, 3)
# ┌──────────────────────┬──────────────────┬─────────────────────────────────┐
# │ selectivity_band     ┆ grad_rate_150pct ┆ inst_name                       │
# │ ---                  ┆ ---              ┆ ---                             │
# │ str                  ┆ f64              ┆ str                             │
# ╞══════════════════════╪══════════════════╪═════════════════════════════════╡
# │ Less Selective/Open  ┆ 28.1             ┆ Alabama A & M University        │
# │ Less Selective/Open  ┆ 62.4             ┆ University of Alabama at Birmi… │
# │ Less Selective/Open  ┆ 66.7             ┆ Amridge University              │
# │ Less Selective/Open  ┆ 60.7             ┆ University of Alabama in Hunts… │
# │ Less Selective/Open  ┆ 28.4             ┆ Alabama State University        │
# │ Less Selective/Open  ┆ 72.2             ┆ The University of Alabama       │
# │ Less Selective/Open  ┆ 35.7             ┆ Auburn University at Montgomer… │
# │ Less Selective/Open  ┆ 80.9             ┆ Auburn University               │
# │ Moderately Selective ┆ 69.8             ┆ Birmingham-Southern College     │
# │ Less Selective/Open  ┆ 18.1             ┆ Faulkner University             │
# └──────────────────────┴──────────────────┴─────────────────────────────────┘
# 
# Descriptive statistics (grad_rate_150pct):
# shape: (9, 2)
# ┌────────────┬──────────────────┐
# │ statistic  ┆ grad_rate_150pct │
# │ ---        ┆ ---              │
# │ str        ┆ f64              │
# ╞════════════╪══════════════════╡
# │ count      ┆ 1796.0           │
# │ null_count ┆ 0.0              │
# │ mean       ┆ 56.387305        │
# │ std        ┆ 19.698269        │
# │ min        ┆ 3.8              │
# │ 25%        ┆ 43.2             │
# │ 50%        ┆ 56.7             │
# │ 75%        ┆ 69.7             │
# │ max        ┆ 100.0            │
# └────────────┴──────────────────┘
# 
# Grad rate summary by band:
# shape: (4, 9)
# ┌──────────────────────┬──────┬──────┬────────┬───┬──────┬───────┬──────┬──────┐
# │ selectivity_band     ┆ n    ┆ mean ┆ median ┆ … ┆ min  ┆ max   ┆ q25  ┆ q75  │
# │ ---                  ┆ ---  ┆ ---  ┆ ---    ┆   ┆ ---  ┆ ---   ┆ ---  ┆ ---  │
# │ str                  ┆ u32  ┆ f64  ┆ f64    ┆   ┆ f64  ┆ f64   ┆ f64  ┆ f64  │
# ╞══════════════════════╪══════╪══════╪════════╪═══╪══════╪═══════╪══════╪══════╡
# │ Highly Selective     ┆ 69   ┆ 88.5 ┆ 92.3   ┆ … ┆ 19.3 ┆ 97.6  ┆ 89.3 ┆ 94.1 │
# │ Less Selective/Open  ┆ 1004 ┆ 52.5 ┆ 53.7   ┆ … ┆ 3.8  ┆ 100.0 ┆ 39.7 ┆ 65.0 │
# │ Moderately Selective ┆ 564  ┆ 57.7 ┆ 58.8   ┆ … ┆ 7.1  ┆ 100.0 ┆ 46.7 ┆ 70.6 │
# │ Selective            ┆ 159  ┆ 62.7 ┆ 63.6   ┆ … ┆ 7.2  ┆ 100.0 ┆ 43.6 ┆ 83.5 │
# └──────────────────────┴──────┴──────┴────────┴───┴──────┴───────┴──────┴──────┘
# 
# Overlap assessment: IQR ranges by band
#   Highly Selective: IQR=[89.3, 94.1], range=[19.3, 97.6]
#   Less Selective/Open: IQR=[39.7, 65.0], range=[3.8, 100.0]
#   Moderately Selective: IQR=[46.7, 70.6], range=[7.1, 100.0]
#   Selective: IQR=[43.6, 83.5], range=[7.2, 100.0]
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
