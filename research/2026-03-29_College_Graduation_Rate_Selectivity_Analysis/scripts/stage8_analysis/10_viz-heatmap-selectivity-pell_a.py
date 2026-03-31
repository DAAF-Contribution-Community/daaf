#!/usr/bin/env python3
"""
Stage 8.2: Heatmap of mean graduation rate by selectivity band and Pell quintile.

Task: viz-heatmap-selectivity-pell
Wave: 10, Step: 10, Stage: 8
Depends on: crosstab-selectivity-pell
Input: output/analysis/2026-03-29_crosstab_selectivity_pell.parquet
Output: output/figures/2026-03-29_heatmap_selectivity_pell.png
Checkpoint: CP4 (visualization)

Revision: _a -- Fix column name: crosstab uses uppercase "N", not lowercase "n".
"""

import polars as pl
import pandas as pd
from pathlib import Path

from plotnine import (
    ggplot, aes, geom_tile, geom_text,
    labs, theme_minimal, theme, element_text, element_blank, element_rect,
    scale_fill_cmap, scale_x_discrete, scale_y_discrete,
    guides, guide_colorbar,
)

# --- Config ---
# Configuration for the selectivity-Pell heatmap visualization. The cross-tab
# results from the prior analysis step contain 20 cells (4 bands x 5 quintiles)
# with mean graduation rates and cell counts.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_CROSSTAB = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_pell.parquet"
OUTPUT_FIGURE = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_heatmap_selectivity_pell.png"

# REASONING: Band order follows the convention established in the crosstab task:
# most selective at top, least selective at bottom. This matches the natural
# reading order (top = "best" selectivity outcomes) and is consistent with
# prior visualizations in this project.
BAND_ORDER = [
    "Highly Selective",
    "Selective",
    "Moderately Selective",
    "Open/Less Selective",
]

QUINTILE_ORDER = [
    "Q1 (Lowest)",
    "Q2",
    "Q3",
    "Q4",
    "Q5 (Highest)",
]

# Sparse cell threshold: cells with fewer than this many institutions are flagged
# with an asterisk to indicate unreliable estimates.
SPARSE_THRESHOLD = 10

# Column name for institution count in the crosstab output (uppercase "N").
COUNT_COL = "N"

# --- Load ---
# Load the cross-tab results produced by the crosstab-selectivity-pell script.
# Verify shape matches expected 20-cell grid (4 bands x 5 quintiles).
print("=" * 60)
print("Stage 8.2: Heatmap -- Selectivity x Pell Quintile")
print("=" * 60)

df = pl.read_parquet(INPUT_CROSSTAB)
print(f"Loaded crosstab: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture the cross-tab structure before building the visualization.
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows} cells in cross-tab")
print(f"Expected: 20 cells (4 bands x 5 quintiles)")

# Verify we have all expected columns for the heatmap
# ASSUMES: The crosstab output contains at minimum: selectivity_band,
# pell_quintile, mean_grad_rate, and N (count of institutions per cell).
# Note: Column is uppercase "N" per the crosstab script output.
required_cols = ["selectivity_band", "pell_quintile", "mean_grad_rate", COUNT_COL]
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"STOP: Missing required columns: {missing_cols}"

# Print summary of values
print(f"\nSelectivity bands present: {sorted(df['selectivity_band'].unique().to_list())}")
print(f"Pell quintiles present: {sorted(df['pell_quintile'].unique().to_list())}")
print(f"Grad rate range: {df['mean_grad_rate'].min():.1f}% - {df['mean_grad_rate'].max():.1f}%")
print(f"Cell N range: {df[COUNT_COL].min()} - {df[COUNT_COL].max()}")

# Identify sparse cells
# INTENT: Flag cells with N < 10 so viewers know these estimates are unreliable.
# REASONING: Small cell sizes produce unstable means with wide confidence intervals.
# The prior crosstab analysis identified 3 sparse cells in the Highly Selective band.
sparse_cells = df.filter(pl.col(COUNT_COL) < SPARSE_THRESHOLD)
print(f"Sparse cells (N < {SPARSE_THRESHOLD}): {sparse_cells.shape[0]}")
if sparse_cells.shape[0] > 0:
    for row in sparse_cells.iter_rows(named=True):
        print(f"  {row['selectivity_band']} x {row['pell_quintile']}: N={row[COUNT_COL]}")

# --- Transform to pandas ---
# INTENT: Convert to pandas DataFrame for plotnine compatibility.
# REASONING: plotnine requires pandas DataFrames. We also need to create the
# display label column and set categorical ordering for the axes.
# ASSUMES: The Polars DataFrame has no null values in the required columns.
pdf = df.to_pandas()

# INTENT: Create formatted cell labels showing mean graduation rate and N count.
# For sparse cells (N < 10), append an asterisk to flag unreliability.
# REASONING: Direct labeling on heatmap cells eliminates the need for a separate
# legend lookup and communicates both the value and its reliability in one glance.
pdf["label"] = pdf.apply(
    lambda row: (
        f"{row['mean_grad_rate']:.1f}%\n(N={int(row[COUNT_COL])})*"
        if row[COUNT_COL] < SPARSE_THRESHOLD
        else f"{row['mean_grad_rate']:.1f}%\n(N={int(row[COUNT_COL])})"
    ),
    axis=1,
)

# INTENT: Set categorical column ordering so axes display in the correct sequence.
# REASONING: Without explicit ordering, plotnine would sort alphabetically, placing
# "Highly Selective" before "Moderately Selective" (correct for Y) but "Q1" before
# "Q5" on X (correct but need explicit label mapping). We use pd.Categorical for
# both to ensure consistent display regardless of data order.
pdf["selectivity_band"] = pd.Categorical(
    pdf["selectivity_band"],
    categories=BAND_ORDER,
    ordered=True,
)
pdf["pell_quintile"] = pd.Categorical(
    pdf["pell_quintile"],
    categories=QUINTILE_ORDER,
    ordered=True,
)

# INTENT: Determine optimal text color (black vs white) for each cell based on
# the graduation rate value, ensuring readability against the fill color.
# REASONING: Dark fill colors require white text; light fill colors require black
# text. Using a threshold at the midpoint of the graduation rate range provides
# good contrast with a viridis-family palette.
grad_rate_mid = (pdf["mean_grad_rate"].min() + pdf["mean_grad_rate"].max()) / 2
pdf["text_color"] = pdf["mean_grad_rate"].apply(
    lambda v: "white" if v > grad_rate_mid else "black"
)

print(f"\nPandas DataFrame ready: {pdf.shape[0]} rows")
print(f"Label column sample: {pdf['label'].iloc[0]}")

# --- Plot ---
# INTENT: Create a heatmap (geom_tile + geom_text) showing mean graduation rate
# across the 4x5 grid of selectivity bands and Pell quintiles. This is the
# primary visualization for examining the interaction between institutional
# selectivity and student financial need (Pell share).
#
# REASONING: Heatmap chosen because:
#   - Two categorical axes (selectivity band, Pell quintile) with a continuous
#     fill (graduation rate) -- this is the canonical heatmap use case
#   - geom_tile provides color-encoded pattern detection (visual encoding rank 7)
#   - geom_text overlays provide precise values (compensating for color imprecision)
#   - Direct cell labeling with N counts embeds data quality information
#
# ASSUMES:
#   - mean_grad_rate is on 0-100 scale (percentage)
#   - All 20 cells are populated (no structural missingness in the cross-tab)
#   - Sparse cells are flagged with asterisk per task specification

# REASONING: Using viridis colormap because it is perceptually uniform,
# colorblind-safe, and prints well in grayscale. Sequential palette is correct
# here because graduation rate is a unidirectional measure (higher = better).
# "Darker = higher" aligns with the subtitle guidance.
plot = (
    ggplot(pdf, aes(x="pell_quintile", y="selectivity_band", fill="mean_grad_rate"))
    + geom_tile(color="white", size=1.5)  # White borders between cells for visual separation
    + geom_text(
        aes(label="label"),
        size=8,
        color=pdf["text_color"].tolist(),
    )
    + scale_fill_cmap(
        cmap_name="viridis",
        name="Mean Graduation\nRate (%)",
        guide=guide_colorbar(barwidth=12, barheight=1),
    )
    + scale_x_discrete(limits=QUINTILE_ORDER)
    + scale_y_discrete(limits=list(reversed(BAND_ORDER)))  # Top = most selective
    + labs(
        title="Mean Graduation Rate by Selectivity and Pell Grant Share",
        subtitle="Darker cells = higher graduation rates. * = fewer than 10 institutions.",
        x="Pell Grant Quintile",
        y="Selectivity Band",
        caption="Source: IPEDS 2020 + FSA 2020.",
    )
    + theme_minimal(base_size=12)
    + theme(
        figure_size=(10, 8),
        dpi=300,
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=10, style="italic"),
        plot_caption=element_text(size=8, color="gray"),
        axis_title_x=element_text(size=11),
        axis_title_y=element_text(size=11),
        axis_text_x=element_text(size=10),
        axis_text_y=element_text(size=10),
        legend_position="bottom",
        panel_grid_major=element_blank(),
        panel_grid_minor=element_blank(),
        panel_background=element_rect(fill="white"),
        plot_background=element_rect(fill="white"),
    )
)

# --- Save ---
# Persist the figure at 300 DPI for publication quality.
OUTPUT_FIGURE.parent.mkdir(parents=True, exist_ok=True)
plot.save(OUTPUT_FIGURE, dpi=300, width=10, height=8, verbose=False)
print(f"\nSaved figure: {OUTPUT_FIGURE}")

# --- CP4 Validation (Visualization) ---
# Checkpoint validation: verify figure file exists and meets size threshold.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

# CP4.1: Figure file exists
figure_exists = OUTPUT_FIGURE.exists()
print(f"  [{'PASS' if figure_exists else 'FAIL'}] Figure file exists: {OUTPUT_FIGURE}")

# CP4.2: File size > 50KB (non-trivial figure with content)
if figure_exists:
    file_size_kb = OUTPUT_FIGURE.stat().st_size / 1024
    size_ok = file_size_kb > 50
    print(f"  [{'PASS' if size_ok else 'FAIL'}] File size: {file_size_kb:.1f} KB (threshold: > 50 KB)")
else:
    size_ok = False
    print(f"  [FAIL] Cannot check file size -- file does not exist")

# CP4.3: All 20 cells represented in the data
cells_complete = pre_rows == 20
print(f"  [{'PASS' if cells_complete else 'WARN'}] All cells present: {pre_rows} / 20")

# CP4.4: Correct data source (crosstab parquet, not raw analysis data)
correct_source = "crosstab" in str(INPUT_CROSSTAB)
print(f"  [{'PASS' if correct_source else 'FAIL'}] Correct data source: {INPUT_CROSSTAB.name}")

assert figure_exists, "STOP: Figure file was not created"
assert size_ok, f"STOP: Figure file too small ({file_size_kb:.1f} KB)"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:41:49
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_a.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 8.2: Heatmap -- Selectivity x Pell Quintile
# ============================================================
# Loaded crosstab: 20 rows x 6 cols
# Columns: ['selectivity_band', 'pell_quintile', 'mean_grad_rate', 'median_grad_rate', 'N', 'pell_gap']
# 
# Pre-state: 20 cells in cross-tab
# Expected: 20 cells (4 bands x 5 quintiles)
# 
# Selectivity bands present: ['Highly Selective', 'Moderately Selective', 'Open/Less Selective', 'Selective']
# Pell quintiles present: ['Q1 (Lowest)', 'Q2', 'Q3', 'Q4', 'Q5 (Highest)']
# Grad rate range: 43.8% - 91.4%
# Cell N range: 2 - 228
# Sparse cells (N < 10): 3
#   Highly Selective x Q1 (Lowest): N=4
#   Highly Selective x Q4: N=3
#   Highly Selective x Q5 (Highest): N=2
# 
# Pandas DataFrame ready: 20 rows
# Label column sample: 90.9%
# (N=4)*
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_a.py", line 185, in <module>
#     guide=guide_colorbar(barwidth=12, barheight=1),
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# TypeError: guide_colorbar.__init__() got an unexpected keyword argument 'barwidth'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
