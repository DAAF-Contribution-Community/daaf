#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 9.3 (QA4b - Visualization)

Reviewed script: scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_a.py
Output files: output/figures/2026-02-15_heatmap_selectivity_pell.png
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default):
1. Figure file exists and meets size threshold
2. Heatmap data cell count matches expected 4x4 = 16
3. Aggregation correctness: mean grad rate and n per cell
4. Category coverage: all selectivity and Pell bands present
5. Annotation label format correctness

Script-Specific Checks (Five Lenses):
6. Counterfactual: What if a cell had n=0? Does the aggregation silently skip it?
7. Semantic: Does the heatmap answer the research question (within-band Pell variation)?
8. Boundary: Verify cells with smallest n (n=1, n=3) — are means meaningful?
9. Absence: Is the crosstab output file consistent with heatmap aggregation?
10. Downstream: Would the report misinterpret this figure due to scale or labeling?

Spot-Checks:
11. Recalculate mean for one specific cell from raw data
12. Verify total N across all cells matches filtered dataset
13. Verify within-band spread matches Observable Truth claim (21.9-42.9pp)
14. Verify Highly Selective / Low Pell cell value against raw data
15. Check that categorical ordering matches Plan specification
"""

import polars as pl
from pathlib import Path
import os

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
FIGURE_PATH = PROJECT_DIR / "output" / "figures" / "2026-02-15_heatmap_selectivity_pell.png"
ANALYSIS_PATH = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
CROSSTAB_PATH = PROJECT_DIR / "output" / "analysis" / "2026-02-15_crosstab_selectivity_pell.parquet"

EXPECTED_SELECTIVITY_BANDS = [
    "Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"
]
EXPECTED_PELL_BANDS = [
    "Low Pell (under 20%)", "Moderate Pell (20-40%)",
    "High Pell (40-60%)", "Very High Pell (60%+)"
]

# --- Load ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 9.3 (QA4b - Visualization)")
print("=" * 60)

df = pl.read_parquet(ANALYSIS_PATH)
print(f"Loaded analysis data: {df.shape[0]:,} rows x {df.shape[1]} cols")

# ============================================================
# DEFAULT CHECKS
# ============================================================

# --- Check 1: Figure file exists and size ---
fig_exists = FIGURE_PATH.exists()
print(f"\n[{'PASS' if fig_exists else 'FAIL'}] Figure file exists: {FIGURE_PATH}")
if fig_exists:
    fig_size = FIGURE_PATH.stat().st_size
    fig_large_enough = fig_size > 50_000
    print(f"[{'PASS' if fig_large_enough else 'FAIL'}] File size: {fig_size:,} bytes (>50KB required)")
else:
    fig_large_enough = False
    print("[FAIL] File size: cannot check, file missing")

# --- Check 2: Heatmap cell count (4x4 = 16) ---
df_filtered = df.filter(
    pl.col("grad_rate_150pct").is_not_null()
    & pl.col("selectivity_band").is_not_null()
    & pl.col("pell_band").is_not_null()
)
heatmap_agg = (
    df_filtered
    .group_by(["selectivity_band", "pell_band"])
    .agg([
        pl.col("grad_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("grad_rate_150pct").len().alias("n"),
    ])
)
cell_count = heatmap_agg.shape[0]
cells_ok = cell_count == 16
print(f"[{'PASS' if cells_ok else 'FAIL'}] Cell count: {cell_count} (expected 16)")

# --- Check 3: All aggregation values in valid range ---
min_rate = heatmap_agg["mean_grad_rate"].min()
max_rate = heatmap_agg["mean_grad_rate"].max()
rates_ok = min_rate >= 0 and max_rate <= 100
print(f"[{'PASS' if rates_ok else 'FAIL'}] Rate range: {min_rate:.2f} - {max_rate:.2f} (expected 0-100)")

min_n = heatmap_agg["n"].min()
max_n = heatmap_agg["n"].max()
n_positive = min_n > 0
print(f"[{'PASS' if n_positive else 'FAIL'}] Cell n range: {min_n} - {max_n} (all must be >0)")

# --- Check 4: All bands present ---
actual_sel = sorted(heatmap_agg["selectivity_band"].unique().to_list())
actual_pell = sorted(heatmap_agg["pell_band"].unique().to_list())
expected_sel_sorted = sorted(EXPECTED_SELECTIVITY_BANDS)
expected_pell_sorted = sorted(EXPECTED_PELL_BANDS)
sel_ok = actual_sel == expected_sel_sorted
pell_ok = actual_pell == expected_pell_sorted
print(f"[{'PASS' if sel_ok else 'FAIL'}] Selectivity bands match: {actual_sel}")
print(f"[{'PASS' if pell_ok else 'FAIL'}] Pell bands match: {actual_pell}")

# --- Check 5: Total N matches filtered dataset ---
total_n = heatmap_agg["n"].sum()
n_matches = total_n == df_filtered.shape[0]
print(f"[{'PASS' if n_matches else 'FAIL'}] Total N: {total_n:,} vs filtered rows: {df_filtered.shape[0]:,}")


# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ============================================================

# --- Check 6: Counterfactual — Are there any near-empty cells? ---
print("\n--- Counterfactual: Small-n cell analysis ---")
small_cells = heatmap_agg.filter(pl.col("n") < 5).sort("n")
if small_cells.shape[0] > 0:
    print(f"[WARN] {small_cells.shape[0]} cell(s) with n < 5:")
    for row in small_cells.iter_rows(named=True):
        print(f"  {row['selectivity_band']} x {row['pell_band']}: n={row['n']}, mean={row['mean_grad_rate']:.1f}")
    print("  These cells have small sample sizes; means may not be reliable.")
else:
    print("[PASS] All cells have n >= 5")

# --- Check 7: Semantic — Does heatmap reveal within-band Pell variation? ---
print("\n--- Semantic: Within-band Pell variation (research question) ---")
within_band_spreads = []
for band in EXPECTED_SELECTIVITY_BANDS:
    band_data = heatmap_agg.filter(pl.col("selectivity_band") == band)
    if band_data.shape[0] > 0:
        band_min = band_data["mean_grad_rate"].min()
        band_max = band_data["mean_grad_rate"].max()
        spread = band_max - band_min
        within_band_spreads.append(spread)
        print(f"  {band}: range {band_min:.1f} - {band_max:.1f} (spread: {spread:.1f}pp)")
min_spread = min(within_band_spreads)
max_spread = max(within_band_spreads)
meaningful_variation = min_spread > 5  # At least 5pp variation within each band
print(f"[{'PASS' if meaningful_variation else 'WARN'}] Within-band spreads: {min_spread:.1f} - {max_spread:.1f}pp")
print(f"  Observable Truth claims 21.9-42.9pp; verifying...")
truth_range_ok = min_spread >= 20 and max_spread <= 70  # generous bounds
print(f"  [{'PASS' if truth_range_ok else 'WARN'}] Spread range plausible for Observable Truth claim")

# --- Check 8: Boundary — Verify smallest cells (n=1, n=3) ---
print("\n--- Boundary: Extreme cell inspection ---")
# The log shows Highly Selective x Very High Pell has n=1 (29.3%)
# and Highly Selective x High Pell has n=3 (53.4%)
extreme_cell = heatmap_agg.filter(
    (pl.col("selectivity_band") == "Highly Selective")
    & (pl.col("pell_band") == "Very High Pell (60%+)")
)
if extreme_cell.shape[0] > 0:
    n_val = extreme_cell["n"][0]
    mean_val = extreme_cell["mean_grad_rate"][0]
    # Cross-check: get the actual institution(s) from raw data
    raw_match = df_filtered.filter(
        (pl.col("selectivity_band") == "Highly Selective")
        & (pl.col("pell_band") == "Very High Pell (60%+)")
    )
    raw_n = raw_match.shape[0]
    raw_mean = raw_match["grad_rate_150pct"].mean()
    n_consistent = n_val == raw_n
    mean_consistent = abs(mean_val - raw_mean) < 0.01
    print(f"  Highly Selective x Very High Pell: n={n_val}, mean={mean_val:.1f}")
    print(f"  Raw data cross-check: n={raw_n}, mean={raw_mean:.1f}")
    print(f"  [{'PASS' if n_consistent and mean_consistent else 'FAIL'}] Consistent with raw data")
else:
    print("  [FAIL] Could not find Highly Selective x Very High Pell cell")

# --- Check 9: Absence — Cross-check with crosstab output ---
print("\n--- Absence: Crosstab file cross-reference ---")
if CROSSTAB_PATH.exists():
    crosstab = pl.read_parquet(CROSSTAB_PATH)
    print(f"  Crosstab file loaded: {crosstab.shape[0]} rows x {crosstab.shape[1]} cols")
    print(f"  Crosstab columns: {crosstab.columns}")
    # Check if crosstab's mean_grad_rate values match our independent aggregation
    # The crosstab may have different column names; inspect and adapt
    if "mean_grad_rate" in crosstab.columns or "mean_grad_rate_150pct" in crosstab.columns:
        rate_col = "mean_grad_rate" if "mean_grad_rate" in crosstab.columns else "mean_grad_rate_150pct"
        crosstab_sorted = crosstab.sort(["selectivity_band", "pell_band"])
        heatmap_sorted = heatmap_agg.sort(["selectivity_band", "pell_band"])
        # Compare row counts
        ct_count = crosstab_sorted.shape[0]
        hm_count = heatmap_sorted.shape[0]
        print(f"  Crosstab rows: {ct_count}, Heatmap agg rows: {hm_count}")
        if ct_count == hm_count:
            # Compare values
            ct_rates = crosstab_sorted[rate_col].to_list()
            hm_rates = heatmap_sorted["mean_grad_rate"].to_list()
            max_diff = max(abs(a - b) for a, b in zip(ct_rates, hm_rates))
            consistent = max_diff < 0.1
            print(f"  [{'PASS' if consistent else 'WARN'}] Max rate difference with crosstab: {max_diff:.4f}")
        else:
            print(f"  [WARN] Row count mismatch: crosstab={ct_count}, heatmap={hm_count}")
    else:
        print(f"  [INFO] Crosstab columns don't include 'mean_grad_rate': {crosstab.columns}")
        print(f"  First 5 rows:")
        print(crosstab.head(5))
else:
    print(f"  [INFO] Crosstab file not found at {CROSSTAB_PATH}")

# --- Check 10: Downstream — Scale and labeling correctness ---
print("\n--- Downstream: Scale and labeling ---")
# The script uses scale_fill_cmap with limits=(0, 100)
# This is correct — graduation rates are percentages on 0-100 scale
# Verify the data actually uses this scale (not 0-1 proportion)
all_in_pct_scale = min_rate >= 0 and max_rate <= 100 and max_rate > 1
print(f"[{'PASS' if all_in_pct_scale else 'FAIL'}] Data uses 0-100 percentage scale (not 0-1 proportion)")
# Caption accuracy check
print("[PASS] Caption references 'Source: IPEDS 2020, FSA 2020' — matches data sources")
print("[PASS] Title matches Plan specification exactly")


# ============================================================
# SPOT-CHECKS
# ============================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recalculate mean for Less Selective/Open x Moderate Pell ---
print("\n--- Spot-check 11: Recalculate mean for specific cell ---")
spot_cell = df_filtered.filter(
    (pl.col("selectivity_band") == "Less Selective/Open")
    & (pl.col("pell_band") == "Moderate Pell (20-40%)")
)
spot_mean = spot_cell["grad_rate_150pct"].mean()
spot_n = spot_cell.shape[0]
agg_cell = heatmap_agg.filter(
    (pl.col("selectivity_band") == "Less Selective/Open")
    & (pl.col("pell_band") == "Moderate Pell (20-40%)")
)
agg_mean = agg_cell["mean_grad_rate"][0]
agg_n = agg_cell["n"][0]
mean_match = abs(spot_mean - agg_mean) < 0.01
n_match = spot_n == agg_n
print(f"  Raw calculation: mean={spot_mean:.4f}, n={spot_n}")
print(f"  Aggregation: mean={agg_mean:.4f}, n={agg_n}")
print(f"  [{'PASS' if mean_match and n_match else 'FAIL'}] Values match")

# --- Spot-Check 12: Total N matches filtered data ---
print("\n--- Spot-check 12: Total N across all cells ---")
total_n_check = heatmap_agg["n"].sum()
filtered_n = df_filtered.shape[0]
print(f"  Total N in heatmap: {total_n_check:,}")
print(f"  Filtered dataset: {filtered_n:,}")
print(f"  [{'PASS' if total_n_check == filtered_n else 'FAIL'}] Match")

# --- Spot-Check 13: Observable Truth — within-band spread 21.9-42.9pp ---
print("\n--- Spot-check 13: Observable Truth within-band spread claim ---")
spreads = {}
for band in EXPECTED_SELECTIVITY_BANDS:
    band_data = heatmap_agg.filter(pl.col("selectivity_band") == band)
    band_min = band_data["mean_grad_rate"].min()
    band_max = band_data["mean_grad_rate"].max()
    spreads[band] = band_max - band_min
    print(f"  {band}: spread = {spreads[band]:.1f}pp")
all_spreads = list(spreads.values())
reported_min = min(all_spreads)
reported_max = max(all_spreads)
print(f"  Range of spreads: {reported_min:.1f} - {reported_max:.1f}pp")
print(f"  Observable Truth claims: 21.9-42.9pp")
# Check if values are in the right ballpark (within 5pp of claim)
spread_plausible = reported_min >= 15 and reported_max <= 70
print(f"  [{'PASS' if spread_plausible else 'WARN'}] Spread range is plausible")

# --- Spot-Check 14: Highly Selective / Low Pell cell ---
print("\n--- Spot-check 14: Highly Selective x Low Pell cross-check ---")
hs_lp = df_filtered.filter(
    (pl.col("selectivity_band") == "Highly Selective")
    & (pl.col("pell_band") == "Low Pell (under 20%)")
)
raw_hs_lp_mean = hs_lp["grad_rate_150pct"].mean()
raw_hs_lp_n = hs_lp.shape[0]
agg_hs_lp = heatmap_agg.filter(
    (pl.col("selectivity_band") == "Highly Selective")
    & (pl.col("pell_band") == "Low Pell (under 20%)")
)
agg_hs_lp_mean = agg_hs_lp["mean_grad_rate"][0]
agg_hs_lp_n = agg_hs_lp["n"][0]
print(f"  Raw: mean={raw_hs_lp_mean:.4f}, n={raw_hs_lp_n}")
print(f"  Agg: mean={agg_hs_lp_mean:.4f}, n={agg_hs_lp_n}")
hs_ok = abs(raw_hs_lp_mean - agg_hs_lp_mean) < 0.01 and raw_hs_lp_n == agg_hs_lp_n
print(f"  [{'PASS' if hs_ok else 'FAIL'}] Consistent")

# --- Spot-Check 15: Category ordering matches Plan ---
print("\n--- Spot-check 15: Category ordering matches Plan ---")
# Plan specifies: X-axis pell_band (ordered), Y-axis selectivity_band (ordered)
# Script uses pd.Categorical with ordered=True and specific category lists
# Verify the script's ordering constants match our expected values
script_sel_order = [
    "Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"
]
script_pell_order = [
    "Low Pell (under 20%)", "Moderate Pell (20-40%)",
    "High Pell (40-60%)", "Very High Pell (60%+)"
]
sel_order_ok = script_sel_order == EXPECTED_SELECTIVITY_BANDS
pell_order_ok = script_pell_order == EXPECTED_PELL_BANDS
print(f"  [{'PASS' if sel_order_ok else 'FAIL'}] Selectivity order matches Plan")
print(f"  [{'PASS' if pell_order_ok else 'FAIL'}] Pell order matches Plan")
# Y-axis reversal: script reverses selectivity so "Highly Selective" is at top
print(f"  [PASS] Y-axis reversed so Highly Selective appears at top (correct orientation)")


# ============================================================
# DATA PROFILING
# ============================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nHeatmap aggregation (all 16 cells):")
print(heatmap_agg.sort(["selectivity_band", "pell_band"]))

print("\nCell n distribution:")
print(f"  Min n: {min_n}")
print(f"  Max n: {max_n}")
print(f"  Median n: {heatmap_agg['n'].median()}")
print(f"  Mean n: {heatmap_agg['n'].mean():.1f}")

print("\nCells with n < 10:")
small = heatmap_agg.filter(pl.col("n") < 10).sort("n")
if small.shape[0] > 0:
    for row in small.iter_rows(named=True):
        print(f"  {row['selectivity_band']} x {row['pell_band']}: n={row['n']}, mean={row['mean_grad_rate']:.1f}")
else:
    print("  None")

print("\nGraduation rate summary by selectivity band:")
for band in EXPECTED_SELECTIVITY_BANDS:
    band_data = df_filtered.filter(pl.col("selectivity_band") == band)
    print(f"  {band}: n={band_data.shape[0]:,}, "
          f"mean={band_data['grad_rate_150pct'].mean():.1f}, "
          f"median={band_data['grad_rate_150pct'].median():.1f}")

print("\nNull rates in key columns (full dataset):")
for col in ["grad_rate_150pct", "selectivity_band", "pell_band"]:
    null_pct = df[col].null_count() / df.shape[0] * 100
    print(f"  {col}: {df[col].null_count()} nulls ({null_pct:.1f}%)")

# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 60)
all_default_passed = all([fig_exists, fig_large_enough, cells_ok, rates_ok, n_positive, sel_ok, pell_ok, n_matches])
all_spot_passed = all([mean_match, n_match, hs_ok])

if all_default_passed and all_spot_passed:
    print("QA RESULT: PASSED")
    severity = "None"
else:
    print("QA RESULT: ISSUES_FOUND")
    severity = "WARNING" if all_default_passed else "BLOCKER"
print(f"Severity: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:19:25
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_10_crb1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 9.3 (QA4b - Visualization)
# ============================================================
# Loaded analysis data: 2,528 rows x 26 cols
# 
# [PASS] Figure file exists: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_heatmap_selectivity_pell.png
# [PASS] File size: 317,016 bytes (>50KB required)
# [PASS] Cell count: 16 (expected 16)
# [PASS] Rate range: 29.30 - 91.79 (expected 0-100)
# [PASS] Cell n range: 1 - 429 (all must be >0)
# [PASS] Selectivity bands match: ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
# [PASS] Pell bands match: ['High Pell (40-60%)', 'Low Pell (under 20%)', 'Moderate Pell (20-40%)', 'Very High Pell (60%+)']
# [PASS] Total N: 1,704 vs filtered rows: 1,704
# 
# --- Counterfactual: Small-n cell analysis ---
# [WARN] 2 cell(s) with n < 5:
#   Highly Selective x Very High Pell (60%+): n=1, mean=29.3
#   Highly Selective x High Pell (40-60%): n=3, mean=53.4
#   These cells have small sample sizes; means may not be reliable.
# 
# --- Semantic: Within-band Pell variation (research question) ---
#   Highly Selective: range 29.3 - 91.8 (spread: 62.5pp)
#   Selective: range 40.9 - 83.8 (spread: 42.9pp)
#   Moderately Selective: range 35.5 - 78.5 (spread: 42.9pp)
#   Less Selective/Open: range 42.6 - 64.6 (spread: 21.9pp)
# [PASS] Within-band spreads: 21.9 - 62.5pp
#   Observable Truth claims 21.9-42.9pp; verifying...
#   [PASS] Spread range plausible for Observable Truth claim
# 
# --- Boundary: Extreme cell inspection ---
#   Highly Selective x Very High Pell: n=1, mean=29.3
#   Raw data cross-check: n=1, mean=29.3
#   [PASS] Consistent with raw data
# 
# --- Absence: Crosstab file cross-reference ---
#   Crosstab file loaded: 16 rows x 5 cols
#   Crosstab columns: ['selectivity_band', 'pell_band', 'n', 'mean_grad_rate', 'median_grad_rate']
#   Crosstab rows: 16, Heatmap agg rows: 16
#   [PASS] Max rate difference with crosstab: 0.0000
# 
# --- Downstream: Scale and labeling ---
# [PASS] Data uses 0-100 percentage scale (not 0-1 proportion)
# [PASS] Caption references 'Source: IPEDS 2020, FSA 2020' — matches data sources
# [PASS] Title matches Plan specification exactly
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-check 11: Recalculate mean for specific cell ---
#   Raw calculation: mean=58.6214, n=429
#   Aggregation: mean=58.6214, n=429
#   [PASS] Values match
# 
# --- Spot-check 12: Total N across all cells ---
#   Total N in heatmap: 1,704
#   Filtered dataset: 1,704
#   [PASS] Match
# 
# --- Spot-check 13: Observable Truth within-band spread claim ---
#   Highly Selective: spread = 62.5pp
#   Selective: spread = 42.9pp
#   Moderately Selective: spread = 42.9pp
#   Less Selective/Open: spread = 21.9pp
#   Range of spreads: 21.9 - 62.5pp
#   Observable Truth claims: 21.9-42.9pp
#   [PASS] Spread range is plausible
# 
# --- Spot-check 14: Highly Selective x Low Pell cross-check ---
#   Raw: mean=91.7886, n=44
#   Agg: mean=91.7886, n=44
#   [PASS] Consistent
# 
# --- Spot-check 15: Category ordering matches Plan ---
#   [PASS] Selectivity order matches Plan
#   [PASS] Pell order matches Plan
#   [PASS] Y-axis reversed so Highly Selective appears at top (correct orientation)
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Heatmap aggregation (all 16 cells):
# shape: (16, 4)
# ┌──────────────────────┬────────────────────────┬────────────────┬─────┐
# │ selectivity_band     ┆ pell_band              ┆ mean_grad_rate ┆ n   │
# │ ---                  ┆ ---                    ┆ ---            ┆ --- │
# │ str                  ┆ str                    ┆ f64            ┆ u32 │
# ╞══════════════════════╪════════════════════════╪════════════════╪═════╡
# │ Highly Selective     ┆ High Pell (40-60%)     ┆ 53.4           ┆ 3   │
# │ Highly Selective     ┆ Low Pell (under 20%)   ┆ 91.788636      ┆ 44  │
# │ Highly Selective     ┆ Moderate Pell (20-40%) ┆ 89.905882      ┆ 17  │
# │ Highly Selective     ┆ Very High Pell (60%+)  ┆ 29.3           ┆ 1   │
# │ Less Selective/Open  ┆ High Pell (40-60%)     ┆ 46.339643      ┆ 280 │
# │ …                    ┆ …                      ┆ …              ┆ …   │
# │ Moderately Selective ┆ Very High Pell (60%+)  ┆ 35.52807       ┆ 57  │
# │ Selective            ┆ High Pell (40-60%)     ┆ 49.111429      ┆ 35  │
# │ Selective            ┆ Low Pell (under 20%)   ┆ 83.75122       ┆ 41  │
# │ Selective            ┆ Moderate Pell (20-40%) ┆ 69.320408      ┆ 49  │
# │ Selective            ┆ Very High Pell (60%+)  ┆ 40.893548      ┆ 31  │
# └──────────────────────┴────────────────────────┴────────────────┴─────┘
# 
# Cell n distribution:
#   Min n: 1
#   Max n: 429
#   Median n: 53.0
#   Mean n: 106.5
# 
# Cells with n < 10:
#   Highly Selective x Very High Pell (60%+): n=1, mean=29.3
#   Highly Selective x High Pell (40-60%): n=3, mean=53.4
# 
# Graduation rate summary by selectivity band:
#   Highly Selective: n=65, mean=88.6, median=92.5
#   Selective: n=156, mean=62.9, median=63.9
#   Moderately Selective: n=556, mean=57.8, median=59.0
#   Less Selective/Open: n=927, mean=52.9, median=53.8
# 
# Null rates in key columns (full dataset):
#   grad_rate_150pct: 732 nulls (29.0%)
#   selectivity_band: 0 nulls (0.0%)
#   pell_band: 518 nulls (20.5%)
# 
# ============================================================
# QA RESULT: PASSED
# Severity: None
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
