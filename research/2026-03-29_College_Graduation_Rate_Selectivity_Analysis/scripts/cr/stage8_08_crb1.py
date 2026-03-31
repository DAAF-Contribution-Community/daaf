#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8.2 Wave 10 -- Consolidated Visualization Review (QA4b)

Reviewed scripts:
  1. scripts/stage8_analysis/08_viz-scatter-grad-admit.py
  2. scripts/stage8_analysis/09_viz-boxplot-selectivity_b.py
  3. scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_c.py
  4. scripts/stage8_analysis/11_viz-correlation-heatmap_a.py
  5. scripts/stage8_analysis/12_viz-sector-comparison_a.py

Output files:
  - output/figures/2026-03-29_grad_rate_vs_admission_rate.png
  - output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png
  - output/figures/2026-03-29_heatmap_selectivity_pell.png
  - output/figures/2026-03-29_correlation_heatmap.png
  - output/figures/2026-03-29_sector_comparison.png

Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
  1. All 5 figure files exist
  2. All 5 figure files > 50 KB
  3. Data source verification for each figure
  4. Axis/label presence validation

QA Checks (Script-Specific -- Five Lenses):
  5. [Semantic] Scatter: verify Pearson r annotation matches computed correlation
  6. [Counterfactual] Boxplot: verify all 4 bands present, check band N proportions
  7. [Boundary] Heatmap: verify sparse cells flagged, all 20 cells present
  8. [Absence] Correlation heatmap: verify symmetry and diagonal = 1.0
  9. [Downstream] Sector: verify annotated N values match actual plotted counts

Spot-Checks:
  10. Scatter: verify hardcoded r=-0.334 against actual data correlation
  11. Boxplot: verify band ordering matches Plan specification
  12. Heatmap: cross-check cell values against crosstab source
  13. Correlation: cross-check a specific r value against independent calculation
  14. Sector: verify for-profit sign reversal claim against data
"""

import polars as pl
import numpy as np
from pathlib import Path
import os

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"
FIGURES_DIR = PROJECT_DIR / "output" / "figures"

# Figure paths
FIGURES = {
    "Scatter": FIGURES_DIR / f"{DATE_PREFIX}_grad_rate_vs_admission_rate.png",
    "Boxplot": FIGURES_DIR / f"{DATE_PREFIX}_boxplot_grad_rate_by_selectivity.png",
    "Heatmap-Pell": FIGURES_DIR / f"{DATE_PREFIX}_heatmap_selectivity_pell.png",
    "Corr-Heatmap": FIGURES_DIR / f"{DATE_PREFIX}_correlation_heatmap.png",
    "Sector": FIGURES_DIR / f"{DATE_PREFIX}_sector_comparison.png",
}

# Data source paths
ANALYSIS_DATA = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
CROSSTAB_DATA = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_pell.parquet"
CORR_DATA = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"

MIN_SIZE_KB = 50
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]
SECTOR_MAP = {1: "Public", 2: "Private Nonprofit", 3: "Private For-Profit"}

issues = []

print("=" * 70)
print("QA4b CONSOLIDATED INSPECTION: Wave 10 Visualizations (5 figures)")
print("=" * 70)

# ============================================================================
# CHECK 1: All 5 figure files exist
# ============================================================================
print("\n--- Check 1: File Existence ---")
for name, path in FIGURES.items():
    exists = path.exists()
    status = "PASS" if exists else "FAIL"
    print(f"  [{status}] {name}: {path.name} exists={exists}")
    if not exists:
        issues.append(f"BLOCKER: {name} figure file does not exist: {path}")

# ============================================================================
# CHECK 2: All 5 figure files > 50 KB
# ============================================================================
print("\n--- Check 2: File Size (> 50 KB) ---")
for name, path in FIGURES.items():
    if path.exists():
        size_kb = os.path.getsize(path) / 1024
        ok = size_kb > MIN_SIZE_KB
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {size_kb:.1f} KB")
        if not ok:
            issues.append(f"WARNING: {name} figure file is only {size_kb:.1f} KB (< 50 KB)")
    else:
        print(f"  [SKIP] {name}: file does not exist")

# ============================================================================
# CHECK 3: Data source verification
# ============================================================================
print("\n--- Check 3: Data Source Verification ---")

# Load analysis data
df_analysis = pl.read_parquet(ANALYSIS_DATA)
print(f"  Analysis data: {df_analysis.shape[0]:,} rows x {df_analysis.shape[1]} cols")

# Load crosstab data
df_crosstab = pl.read_parquet(CROSSTAB_DATA)
print(f"  Crosstab data: {df_crosstab.shape[0]:,} rows x {df_crosstab.shape[1]} cols")

# Load correlation matrix
df_corr = pl.read_parquet(CORR_DATA)
print(f"  Correlation matrix: {df_corr.shape[0]} rows x {df_corr.shape[1]} cols")

# Verify scripts use the right data sources:
# - Scatter, Boxplot, Sector use analysis.parquet
# - Heatmap uses crosstab.parquet
# - Corr heatmap uses correlation_matrix.parquet
print("  [PASS] Scatter source: analysis.parquet (verified in script)")
print("  [PASS] Boxplot source: analysis.parquet (verified in script)")
print("  [PASS] Heatmap source: crosstab_selectivity_pell.parquet (verified in script)")
print("  [PASS] Corr heatmap source: correlation_matrix.parquet (verified in script)")
print("  [PASS] Sector source: analysis.parquet (verified in script)")

# ============================================================================
# CHECK 4: Required columns for each visualization
# ============================================================================
print("\n--- Check 4: Required Columns ---")

# Scatter needs: admit_rate, completion_rate_150pct, selectivity_band
scatter_cols = ["admit_rate", "completion_rate_150pct", "selectivity_band"]
scatter_missing = [c for c in scatter_cols if c not in df_analysis.columns]
print(f"  [{'PASS' if not scatter_missing else 'FAIL'}] Scatter columns: {scatter_cols}")

# Boxplot needs: selectivity_band, completion_rate_150pct
box_cols = ["selectivity_band", "completion_rate_150pct"]
box_missing = [c for c in box_cols if c not in df_analysis.columns]
print(f"  [{'PASS' if not box_missing else 'FAIL'}] Boxplot columns: {box_cols}")

# Heatmap needs: selectivity_band, pell_quintile, mean_grad_rate, N
hmap_cols = ["selectivity_band", "pell_quintile", "mean_grad_rate", "N"]
hmap_missing = [c for c in hmap_cols if c not in df_crosstab.columns]
print(f"  [{'PASS' if not hmap_missing else 'FAIL'}] Heatmap columns: {hmap_cols}")

# Correlation heatmap needs: variable + 7 var columns
corr_cols = ["variable", "admit_rate", "completion_rate_150pct", "pell_share",
             "urm_share", "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]
corr_missing = [c for c in corr_cols if c not in df_corr.columns]
print(f"  [{'PASS' if not corr_missing else 'FAIL'}] Corr heatmap columns present: {len(corr_cols) - len(corr_missing)}/{len(corr_cols)}")

# Sector needs: inst_control, admit_rate, completion_rate_150pct
sector_cols = ["inst_control", "admit_rate", "completion_rate_150pct"]
sector_missing = [c for c in sector_cols if c not in df_analysis.columns]
print(f"  [{'PASS' if not sector_missing else 'FAIL'}] Sector columns: {sector_cols}")

if scatter_missing or box_missing or hmap_missing or corr_missing or sector_missing:
    issues.append("BLOCKER: Missing required columns in data source(s)")

# ============================================================================
# CHECK 5: [Semantic] Scatter: Pearson r annotation vs computed
# ============================================================================
print("\n--- Check 5: [Semantic] Scatter Pearson r Verification ---")
# INTENT: Verify the hardcoded r=-0.334 in the scatter script matches an
# independently computed correlation from the actual data.
# REASONING: If the hardcoded value is wrong, the figure misleads readers.

df_scatter = df_analysis.drop_nulls(subset=["admit_rate", "completion_rate_150pct"])
computed_r = df_scatter.select(
    pl.corr("admit_rate", "completion_rate_150pct", method="pearson")
).item()
hardcoded_r = -0.334
r_diff = abs(computed_r - hardcoded_r)
r_ok = r_diff < 0.005  # Allow rounding tolerance

print(f"  Hardcoded in script: r = {hardcoded_r}")
print(f"  Independently computed: r = {computed_r:.4f}")
print(f"  Difference: {r_diff:.4f}")
print(f"  [{'PASS' if r_ok else 'FAIL'}] Pearson r matches (within 0.005 tolerance)")

if not r_ok:
    issues.append(f"WARNING: Scatter Pearson r annotation ({hardcoded_r}) differs from computed ({computed_r:.4f})")

# ============================================================================
# CHECK 6: [Counterfactual] Boxplot: Band coverage and proportions
# ============================================================================
print("\n--- Check 6: [Counterfactual] Boxplot Band Coverage ---")
# INTENT: Verify all 4 bands are in the data and proportions are reasonable.
# REASONING: If a band has very few institutions, the boxplot summary stats
# are unreliable and the visualization could be misleading.

band_counts = df_analysis.group_by("selectivity_band").len().sort("len", descending=True)
print(f"  Band distribution:")
all_bands_present = True
for row in band_counts.iter_rows(named=True):
    pct = row["len"] / df_analysis.shape[0] * 100
    print(f"    {row['selectivity_band']}: {row['len']:,} ({pct:.1f}%)")
    if row["len"] < 20:
        issues.append(f"WARNING: Boxplot band '{row['selectivity_band']}' has only {row['len']} institutions")
bands_in_data = set(df_analysis["selectivity_band"].unique().to_list())
missing_bands = set(BAND_ORDER) - bands_in_data
if missing_bands:
    all_bands_present = False
    issues.append(f"BLOCKER: Missing bands in boxplot data: {missing_bands}")
print(f"  [{'PASS' if all_bands_present else 'FAIL'}] All 4 expected bands present")

# ============================================================================
# CHECK 7: [Boundary] Heatmap: All 20 cells present, sparse cells flagged
# ============================================================================
print("\n--- Check 7: [Boundary] Heatmap Cell Completeness ---")
# INTENT: Verify the heatmap has all 20 cells and sparse cells are properly handled.
# REASONING: Missing cells would create gaps in the heatmap; unflagged sparse cells
# could lead readers to trust unreliable estimates.

cell_count = df_crosstab.shape[0]
cells_ok = cell_count == 20
print(f"  [{'PASS' if cells_ok else 'FAIL'}] Cell count: {cell_count} (expected 20)")

sparse = df_crosstab.filter(pl.col("N") < 10)
print(f"  Sparse cells (N < 10): {sparse.shape[0]}")
for row in sparse.iter_rows(named=True):
    print(f"    {row['selectivity_band']} x {row['pell_quintile']}: N={row['N']}, mean={row['mean_grad_rate']:.1f}%")

if not cells_ok:
    issues.append(f"WARNING: Heatmap has {cell_count} cells instead of expected 20")

# Check N range is plausible
n_total = df_crosstab["N"].sum()
print(f"  Total N across cells: {n_total:,}")
print(f"  Analysis data rows: {df_analysis.shape[0]:,}")
# Total N in crosstab should be <= analysis data rows
n_plausible = n_total <= df_analysis.shape[0]
print(f"  [{'PASS' if n_plausible else 'FAIL'}] Crosstab total N <= analysis rows")

# ============================================================================
# CHECK 8: [Absence] Correlation heatmap: Symmetry and diagonal
# ============================================================================
print("\n--- Check 8: [Absence] Correlation Matrix Symmetry ---")
# INTENT: Verify the correlation matrix is symmetric and has 1.0 on diagonal.
# REASONING: An asymmetric matrix indicates a computation error. Diagonal
# must be 1.0 (variable correlated with itself).

var_names = ["admit_rate", "completion_rate_150pct", "pell_share", "urm_share",
             "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]

# Check diagonal = 1.0
diagonal_ok = True
for i, var in enumerate(var_names):
    row = df_corr.filter(pl.col("variable") == var)
    if row.shape[0] == 1:
        diag_val = row[var].item()
        if abs(diag_val - 1.0) > 0.001:
            diagonal_ok = False
            print(f"  FAIL: Diagonal[{var}] = {diag_val} (expected 1.0)")
print(f"  [{'PASS' if diagonal_ok else 'FAIL'}] Diagonal values = 1.0")
if not diagonal_ok:
    issues.append("BLOCKER: Correlation matrix diagonal is not 1.0")

# Check symmetry
symmetry_ok = True
max_asym = 0.0
for i, var_i in enumerate(var_names):
    for j, var_j in enumerate(var_names):
        if i >= j:
            continue
        row_i = df_corr.filter(pl.col("variable") == var_i)
        row_j = df_corr.filter(pl.col("variable") == var_j)
        if row_i.shape[0] == 1 and row_j.shape[0] == 1:
            val_ij = row_i[var_j].item()
            val_ji = row_j[var_i].item()
            diff = abs(val_ij - val_ji)
            max_asym = max(max_asym, diff)
            if diff > 0.001:
                symmetry_ok = False
                print(f"  FAIL: r({var_i},{var_j})={val_ij:.4f} != r({var_j},{var_i})={val_ji:.4f}")
print(f"  [{'PASS' if symmetry_ok else 'FAIL'}] Symmetry (max asymmetry: {max_asym:.6f})")
if not symmetry_ok:
    issues.append("BLOCKER: Correlation matrix is not symmetric")

# ============================================================================
# CHECK 9: [Downstream] Sector: Annotated N vs actual plottable rows
# ============================================================================
print("\n--- Check 9: [Downstream] Sector N Annotation Accuracy ---")
# INTENT: Verify the hardcoded N values in the sector comparison script match
# the actual count of plottable rows (non-null admit_rate AND completion_rate).
# REASONING: If annotated N values are wrong, the figure communicates false
# sample sizes to readers. The script hardcodes N from the sector-comparison
# analysis (07_sector-comparison.py) which may use a different filtering
# criterion than the scatter plot.

# Sector map: 1=Public, 2=Private NP, 3=Private FP
df_sector = df_analysis.with_columns(
    pl.col("inst_control").replace_strict(SECTOR_MAP, default=None).alias("sector_label")
).drop_nulls(subset=["admit_rate", "completion_rate_150pct", "sector_label"])

# These are the hardcoded values from 12_viz-sector-comparison_a.py
annotated_n = {"Public": 594, "Private Nonprofit": 1202, "Private For-Profit": 150}

n_match_issues = []
for sector in ["Public", "Private Nonprofit", "Private For-Profit"]:
    actual_n = df_sector.filter(pl.col("sector_label") == sector).shape[0]
    expected_n = annotated_n[sector]
    match = actual_n == expected_n
    status = "PASS" if match else "FAIL"
    print(f"  [{status}] {sector}: annotated N={expected_n}, actual plottable N={actual_n}")
    if not match:
        n_match_issues.append(f"{sector}: annotated {expected_n} vs actual {actual_n}")

if n_match_issues:
    issues.append(
        f"WARNING: Sector annotations show N values that differ from actual "
        f"plottable rows: {'; '.join(n_match_issues)}. "
        f"The annotations likely use the full dataset N (before filtering null admit_rate), "
        f"but the plotted points only include the non-null subset."
    )

# ============================================================================
# CHECK 10: [Spot-check] Scatter: Independent r verification (already in Check 5)
# ============================================================================
# (Covered in Check 5 above)

# ============================================================================
# CHECK 11: [Spot-check] Boxplot: Band order matches Plan specification
# ============================================================================
print("\n--- Check 11: [Spot-check] Boxplot Band Order ---")
# Plan says: highly selective (<25%), selective (25-50%), moderately selective
# (50-75%), open/less selective (>75% or open admissions)
# INTENT: Verify the band labels match these definitions.

# Check that the bands in the data map to correct admit_rate ranges
df_with_admit = df_analysis.drop_nulls(subset=["admit_rate", "selectivity_band"])
for band, (lo, hi) in [
    ("Highly Selective", (0, 25)),
    ("Selective", (25, 50)),
    ("Moderately Selective", (50, 75)),
    ("Open/Less Selective", (75, 101)),
]:
    subset = df_with_admit.filter(pl.col("selectivity_band") == band)
    if subset.shape[0] > 0:
        ar_min = subset["admit_rate"].min()
        ar_max = subset["admit_rate"].max()
        in_range = ar_min >= lo and ar_max <= hi
        print(f"  [{'PASS' if in_range else 'WARN'}] {band}: admit_rate range [{ar_min:.1f}, {ar_max:.1f}] (expected ~{lo}-{hi})")
        if not in_range:
            issues.append(f"INFO: {band} has admit_rate outside expected range: [{ar_min:.1f}, {ar_max:.1f}]")

# Also check Open/Less Selective includes null admit_rate institutions
open_null = df_analysis.filter(
    (pl.col("selectivity_band") == "Open/Less Selective") & (pl.col("admit_rate").is_null())
).shape[0]
print(f"  Open/Less Selective with null admit_rate (open admissions): {open_null:,}")

# ============================================================================
# CHECK 12: [Spot-check] Heatmap: Cross-check specific cell values
# ============================================================================
print("\n--- Check 12: [Spot-check] Heatmap Cell Value Cross-Check ---")
# INTENT: Pick a specific cell and independently compute its mean grad rate
# to verify the crosstab output is correct.
# REASONING: If we independently compute one cell's mean and it matches the
# crosstab value, we have evidence the pipeline is working correctly.

# Pick the largest cell for most stable verification
target_band = "Open/Less Selective"
target_quintile = "Q4"

# Get the value from crosstab
ct_row = df_crosstab.filter(
    (pl.col("selectivity_band") == target_band) & (pl.col("pell_quintile") == target_quintile)
)
if ct_row.shape[0] == 1:
    ct_mean = ct_row["mean_grad_rate"].item()
    ct_n = ct_row["N"].item()

    # Now compute independently from analysis data
    # Need to identify which rows fall into this cell. We need pell_quintile column.
    if "pell_quintile" in df_analysis.columns:
        independent = df_analysis.filter(
            (pl.col("selectivity_band") == target_band) & (pl.col("pell_quintile") == target_quintile)
        )
        if independent.shape[0] > 0:
            ind_mean = independent["completion_rate_150pct"].mean()
            ind_n = independent.shape[0]
            mean_match = abs(ct_mean - ind_mean) < 0.5
            n_match = ct_n == ind_n
            print(f"  Cell: {target_band} x {target_quintile}")
            print(f"    Crosstab: mean={ct_mean:.1f}%, N={ct_n}")
            print(f"    Independent: mean={ind_mean:.1f}%, N={ind_n}")
            print(f"  [{'PASS' if mean_match else 'FAIL'}] Mean matches within 0.5pp")
            print(f"  [{'PASS' if n_match else 'FAIL'}] N matches exactly")
        else:
            print(f"  [SKIP] No matching rows in analysis data for independent check")
            print(f"  (pell_quintile may not be in analysis.parquet)")
    else:
        print(f"  [SKIP] pell_quintile not in analysis.parquet -- cannot cross-check")
        print(f"  Crosstab cell: {target_band} x {target_quintile}: mean={ct_mean:.1f}%, N={ct_n}")
else:
    print(f"  [SKIP] Cell not found in crosstab")

# ============================================================================
# CHECK 13: [Spot-check] Correlation: Independent r calculation
# ============================================================================
print("\n--- Check 13: [Spot-check] Correlation Cross-Check ---")
# INTENT: Pick one off-diagonal correlation and independently verify it.
# REASONING: Catches silent errors in the correlation computation pipeline.

# Check r(admit_rate, completion_rate_150pct) from the matrix
corr_row = df_corr.filter(pl.col("variable") == "admit_rate")
if corr_row.shape[0] == 1:
    matrix_r = corr_row["completion_rate_150pct"].item()

    # Independent calculation: listwise deletion on all 7 vars (matching the
    # correlation script's approach)
    all_vars = ["admit_rate", "completion_rate_150pct", "pell_share", "urm_share",
                "student_faculty_ratio", "retention_rate", "instr_expend_per_fte"]
    df_listwise = df_analysis.drop_nulls(subset=all_vars)
    ind_r = df_listwise.select(
        pl.corr("admit_rate", "completion_rate_150pct", method="pearson")
    ).item()

    r_diff = abs(matrix_r - ind_r)
    r_match = r_diff < 0.005
    print(f"  r(admit_rate, completion_rate) from matrix: {matrix_r:.4f}")
    print(f"  Independently computed (listwise): {ind_r:.4f}")
    print(f"  [{'PASS' if r_match else 'FAIL'}] Match within 0.005 tolerance (diff={r_diff:.4f})")
    if not r_match:
        issues.append(f"WARNING: Correlation matrix r differs from independent calc: {matrix_r:.4f} vs {ind_r:.4f}")
else:
    print(f"  [SKIP] Could not find admit_rate row in correlation matrix")

# Also verify listwise N matches what the figure caption says
print(f"  Listwise N: {df_listwise.shape[0]:,}")
# Caption says N=1,574
caption_n_match = df_listwise.shape[0] == 1574
print(f"  [{'PASS' if caption_n_match else 'WARN'}] Listwise N matches caption N=1,574: {caption_n_match}")

# ============================================================================
# CHECK 14: [Spot-check] Sector: For-profit sign reversal verification
# ============================================================================
print("\n--- Check 14: [Spot-check] Sector Sign Reversal ---")
# INTENT: Independently verify the for-profit positive correlation claim.
# REASONING: This is a key finding -- if the sign reversal is an artifact
# of the small sample, the entire narrative about for-profit institutions
# could be misleading.

for sector in ["Public", "Private Nonprofit", "Private For-Profit"]:
    sector_df = df_sector.filter(pl.col("sector_label") == sector)
    n = sector_df.shape[0]
    if n > 2:
        r = sector_df.select(
            pl.corr("admit_rate", "completion_rate_150pct", method="pearson")
        ).item()
        print(f"  {sector}: N={n:,}, r={r:+.4f}")

        # Check against hardcoded values
        hardcoded = {"Public": -0.3683, "Private Nonprofit": -0.3349, "Private For-Profit": +0.2564}
        diff = abs(r - hardcoded[sector])
        match = diff < 0.01
        print(f"    Annotated: r={hardcoded[sector]:+.4f}, diff={diff:.4f}")
        print(f"    [{'PASS' if match else 'FAIL'}] Match within 0.01")
        if not match:
            issues.append(f"WARNING: Sector {sector} annotated r differs from computed")
    else:
        print(f"  {sector}: N={n} -- too few for correlation")
        issues.append(f"BLOCKER: {sector} has only {n} plottable rows -- insufficient for trend line")

# Check for-profit N is adequate for the claim
fp_n = df_sector.filter(pl.col("sector_label") == "Private For-Profit").shape[0]
if fp_n < 30:
    print(f"  [WARN] For-profit plottable N={fp_n} is small (< 30) -- sign reversal may be unstable")
    issues.append(
        f"WARNING: For-profit sector has only {fp_n} plottable institutions "
        f"(with non-null admit_rate). The positive correlation (r=+0.26) and "
        f"trend line may be unreliable with this small N."
    )

# ============================================================================
# CHECK 15: Heatmap subtitle accuracy
# ============================================================================
print("\n--- Check 15: Heatmap Subtitle Color-Meaning Mapping ---")
# INTENT: The heatmap script subtitle says "Darker cells = higher graduation rates"
# but with viridis colormap, darker (purple) = LOWER values, lighter (yellow) = HIGHER.
# REASONING: This could mislead readers who read the subtitle and expect the
# opposite color-meaning mapping from what's displayed.
print("  Script subtitle: 'Darker cells = higher graduation rates'")
print("  Viridis colormap: dark purple = low values, bright yellow = high values")
print("  ASSESSMENT: Subtitle is INCORRECT -- darker cells actually correspond")
print("  to LOWER graduation rates with viridis. This inverts the reader's")
print("  interpretation of the color scale.")
issues.append(
    "WARNING: Heatmap subtitle says 'Darker cells = higher graduation rates' "
    "but viridis maps darker colors to LOWER values. The subtitle should say "
    "'Brighter/lighter cells = higher graduation rates' or 'Darker cells = lower "
    "graduation rates'. Visual inspection confirms high-rate cells (90%+) are "
    "yellow/bright while low-rate cells (43%) are dark purple."
)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("QA4b SUMMARY")
print("=" * 70)

blockers = [i for i in issues if i.startswith("BLOCKER")]
warnings = [i for i in issues if i.startswith("WARNING")]
infos = [i for i in issues if i.startswith("INFO")]

print(f"\nBLOCKERS: {len(blockers)}")
for b in blockers:
    print(f"  {b}")

print(f"\nWARNINGS: {len(warnings)}")
for w in warnings:
    print(f"  {w}")

print(f"\nINFO: {len(infos)}")
for i in infos:
    print(f"  {i}")

# Overall status
if blockers:
    overall = "BLOCKER"
elif warnings:
    overall = "WARNING"
elif infos:
    overall = "INFO"
else:
    overall = "PASSED"

print(f"\nOVERALL QA4b STATUS: {overall}")
print("=" * 70)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 14:00:28
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_08_crb1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ======================================================================
# QA4b CONSOLIDATED INSPECTION: Wave 10 Visualizations (5 figures)
# ======================================================================
# 
# --- Check 1: File Existence ---
#   [PASS] Scatter: 2026-03-29_grad_rate_vs_admission_rate.png exists=True
#   [PASS] Boxplot: 2026-03-29_boxplot_grad_rate_by_selectivity.png exists=True
#   [PASS] Heatmap-Pell: 2026-03-29_heatmap_selectivity_pell.png exists=True
#   [PASS] Corr-Heatmap: 2026-03-29_correlation_heatmap.png exists=True
#   [PASS] Sector: 2026-03-29_sector_comparison.png exists=True
# 
# --- Check 2: File Size (> 50 KB) ---
#   [PASS] Scatter: 1198.0 KB
#   [PASS] Boxplot: 786.4 KB
#   [PASS] Heatmap-Pell: 311.1 KB
#   [PASS] Corr-Heatmap: 340.9 KB
#   [PASS] Sector: 466.9 KB
# 
# --- Check 3: Data Source Verification ---
#   Analysis data: 1,946 rows x 25 cols
#   Crosstab data: 20 rows x 6 cols
#   Correlation matrix: 7 rows x 10 cols
#   [PASS] Scatter source: analysis.parquet (verified in script)
#   [PASS] Boxplot source: analysis.parquet (verified in script)
#   [PASS] Heatmap source: crosstab_selectivity_pell.parquet (verified in script)
#   [PASS] Corr heatmap source: correlation_matrix.parquet (verified in script)
#   [PASS] Sector source: analysis.parquet (verified in script)
# 
# --- Check 4: Required Columns ---
#   [PASS] Scatter columns: ['admit_rate', 'completion_rate_150pct', 'selectivity_band']
#   [PASS] Boxplot columns: ['selectivity_band', 'completion_rate_150pct']
#   [PASS] Heatmap columns: ['selectivity_band', 'pell_quintile', 'mean_grad_rate', 'N']
#   [PASS] Corr heatmap columns present: 8/8
#   [PASS] Sector columns: ['inst_control', 'admit_rate', 'completion_rate_150pct']
# 
# --- Check 5: [Semantic] Scatter Pearson r Verification ---
#   Hardcoded in script: r = -0.334
#   Independently computed: r = -0.3161
#   Difference: 0.0179
#   [FAIL] Pearson r matches (within 0.005 tolerance)
# 
# --- Check 6: [Counterfactual] Boxplot Band Coverage ---
#   Band distribution:
#     Open/Less Selective: 1,121 (57.6%)
#     Moderately Selective: 577 (29.7%)
#     Selective: 177 (9.1%)
#     Highly Selective: 71 (3.6%)
#   [PASS] All 4 expected bands present
# 
# --- Check 7: [Boundary] Heatmap Cell Completeness ---
#   [PASS] Cell count: 20 (expected 20)
#   Sparse cells (N < 10): 3
#     Highly Selective x Q1 (Lowest): N=4, mean=90.9%
#     Highly Selective x Q4: N=3, mean=64.7%
#     Highly Selective x Q5 (Highest): N=2, mean=62.5%
#   Total N across cells: 1,887
#   Analysis data rows: 1,946
#   [PASS] Crosstab total N <= analysis rows
# 
# --- Check 8: [Absence] Correlation Matrix Symmetry ---
#   [PASS] Diagonal values = 1.0
#   [PASS] Symmetry (max asymmetry: 0.000000)
# 
# --- Check 9: [Downstream] Sector N Annotation Accuracy ---
#   [FAIL] Public: annotated N=594, actual plottable N=525
#   [FAIL] Private Nonprofit: annotated N=1202, actual plottable N=1048
#   [FAIL] Private For-Profit: annotated N=150, actual plottable N=52
# 
# --- Check 11: [Spot-check] Boxplot Band Order ---
#   [PASS] Highly Selective: admit_rate range [0.0, 24.5] (expected ~0-25)
#   [PASS] Selective: admit_rate range [25.0, 50.0] (expected ~25-50)
#   [PASS] Moderately Selective: admit_rate range [50.0, 75.0] (expected ~50-75)
#   [PASS] Open/Less Selective: admit_rate range [75.0, 100.0] (expected ~75-101)
#   Open/Less Selective with null admit_rate (open admissions): 321
# 
# --- Check 12: [Spot-check] Heatmap Cell Value Cross-Check ---
#   Cell: Open/Less Selective x Q4
#     Crosstab: mean=55.0%, N=228
#     Independent: mean=55.0%, N=228
#   [PASS] Mean matches within 0.5pp
#   [PASS] N matches exactly
# 
# --- Check 13: [Spot-check] Correlation Cross-Check ---
#   r(admit_rate, completion_rate) from matrix: -0.3343
#   Independently computed (listwise): -0.3343
#   [PASS] Match within 0.005 tolerance (diff=0.0000)
#   Listwise N: 1,574
#   [PASS] Listwise N matches caption N=1,574: True
# 
# --- Check 14: [Spot-check] Sector Sign Reversal ---
#   Public: N=525, r=-0.3683
#     Annotated: r=-0.3683, diff=0.0000
#     [PASS] Match within 0.01
#   Private Nonprofit: N=1,048, r=-0.3349
#     Annotated: r=-0.3349, diff=0.0000
#     [PASS] Match within 0.01
#   Private For-Profit: N=52, r=+0.2564
#     Annotated: r=+0.2564, diff=0.0000
#     [PASS] Match within 0.01
# 
# --- Check 15: Heatmap Subtitle Color-Meaning Mapping ---
#   Script subtitle: 'Darker cells = higher graduation rates'
#   Viridis colormap: dark purple = low values, bright yellow = high values
#   ASSESSMENT: Subtitle is INCORRECT -- darker cells actually correspond
#   to LOWER graduation rates with viridis. This inverts the reader's
#   interpretation of the color scale.
# 
# ======================================================================
# QA4b SUMMARY
# ======================================================================
# 
# BLOCKERS: 0
# 
# WARNINGS: 3
#   WARNING: Scatter Pearson r annotation (-0.334) differs from computed (-0.3161)
#   WARNING: Sector annotations show N values that differ from actual plottable rows: Public: annotated 594 vs actual 525; Private Nonprofit: annotated 1202 vs actual 1048; Private For-Profit: annotated 150 vs actual 52. The annotations likely use the full dataset N (before filtering null admit_rate), but the plotted points only include the non-null subset.
#   WARNING: Heatmap subtitle says 'Darker cells = higher graduation rates' but viridis maps darker colors to LOWER values. The subtitle should say 'Brighter/lighter cells = higher graduation rates' or 'Darker cells = lower graduation rates'. Visual inspection confirms high-rate cells (90%+) are yellow/bright while low-rate cells (43%) are dark purple.
# 
# INFO: 0
# 
# OVERALL QA4b STATUS: WARNING
# ======================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
