#!/usr/bin/env python3
"""
Stage 8.2 (Step 9.3): Heatmap of mean graduation rate by selectivity band and Pell share band.

Task: viz-heatmap-selectivity-pell
Wave: 9, Step: 9.3, Stage: 8
Depends on: crosstab-selectivity-pell
Input: data/processed/2026-02-15_analysis.parquet
Output: output/figures/2026-02-15_heatmap_selectivity_pell.png
Checkpoint: CP4 (figure existence, data accuracy, labeling)
"""

import polars as pl
from pathlib import Path
from plotnine import (
    ggplot, aes, geom_tile, geom_text, labs,
    scale_fill_cmap, scale_x_discrete, scale_y_discrete,
    scale_color_identity,
    theme_minimal, theme, element_text, element_blank, element_rect,
    guides, guide_colorbar,
)

# --- Config ---
# Configuration constants for the selectivity-Pell heatmap visualization.
# Band ordering is critical: the Plan specifies exact category orders that
# match the crosstab analysis output (Step 9.1).
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_heatmap_selectivity_pell.png"

# REASONING: Category orders reflect the analytical structure from the Plan.
# Selectivity is ordered from most to least selective (top-to-bottom in the heatmap).
# Pell bands are ordered from lowest to highest Pell share (left-to-right).
# These must match the band definitions used in Stage 7 transformation.
SELECTIVITY_ORDER = [
    "Highly Selective",
    "Selective",
    "Moderately Selective",
    "Less Selective/Open",
]

PELL_ORDER = [
    "Low Pell (<20%)",
    "Moderate Pell (20-39%)",
    "High Pell (40-59%)",
    "Very High Pell (≥60%)",
]

# --- Load ---
# Load analysis dataset and verify shape before proceeding.
print("=" * 60)
print("Stage 8.2 (Step 9.3): Heatmap - Selectivity x Pell Share")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture current state before filtering. We need non-null values for all three
# variables: grad_rate_150pct, selectivity_band, and pell_band.
pre_rows = df.shape[0]
print(f"Pre-filter rows: {pre_rows:,}")

# INTENT: Check that the required columns exist before filtering.
# ASSUMES: These columns were created during Stage 7 transformation steps
# and are present in the analysis dataset.
required_cols = ["grad_rate_150pct", "selectivity_band", "pell_band"]
missing = [c for c in required_cols if c not in df.columns]
assert len(missing) == 0, f"STOP: Missing required columns: {missing}"
print(f"Required columns present: {required_cols}")

# --- Filter ---
# INTENT: Remove rows with null values in the three columns needed for the heatmap
# aggregation. Nulls would be excluded from group_by anyway but explicit filtering
# ensures we know the exact working dataset size.
#
# REASONING: Explicit filter rather than relying on implicit null exclusion in
# group_by because we want to report the exact N in each cell and the total
# working dataset size.
#
# ASSUMES: grad_rate_150pct is on 0-100 scale (percentage, not proportion).
# selectivity_band and pell_band are string categoricals with values matching
# the ORDER lists above.
df_filtered = df.filter(
    pl.col("grad_rate_150pct").is_not_null()
    & pl.col("selectivity_band").is_not_null()
    & pl.col("pell_band").is_not_null()
)
post_filter_rows = df_filtered.shape[0]
print(f"Post-filter rows: {post_filter_rows:,} (dropped {pre_rows - post_filter_rows:,} nulls)")

# --- Aggregate ---
# INTENT: Compute mean graduation rate and count of institutions for each
# selectivity-Pell cell. These become the fill color and annotation text.
#
# REASONING: Mean (not median) is used to align with the crosstab analysis
# (Step 9.1) and to show the central tendency across institutions. The count
# provides context for interpreting cell means — small-n cells are less reliable.
#
# ASSUMES: Each institution appears once per cell (no duplicates in analysis data).
heatmap_data = (
    df_filtered
    .group_by(["selectivity_band", "pell_band"])
    .agg([
        pl.col("grad_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("grad_rate_150pct").len().alias("n"),
    ])
)
print(f"\nHeatmap cells: {heatmap_data.shape[0]:,} (expected 16 = 4x4)")
print(f"Heatmap data:\n{heatmap_data.sort(['selectivity_band', 'pell_band'])}")

# INTENT: Create a formatted label column for cell annotations showing both
# the mean graduation rate and the number of institutions.
# REASONING: Combining rate + n in a single label lets readers immediately see
# both the value and the sample size without needing a second reference.
heatmap_data = heatmap_data.with_columns(
    (
        pl.col("mean_grad_rate").round(1).cast(pl.Utf8)
        + pl.lit("%\n(n=")
        + pl.col("n").cast(pl.Utf8)
        + pl.lit(")")
    ).alias("cell_label")
)

# INTENT: Convert to pandas for plotnine, applying categorical ordering.
# REASONING: plotnine requires pandas DataFrames. We use pd.Categorical
# to enforce the exact band ordering on axes — without this, plotnine would
# sort alphabetically, which misrepresents the ordinal structure.
import pandas as pd

heatmap_pdf = heatmap_data.to_pandas()
heatmap_pdf["selectivity_band"] = pd.Categorical(
    heatmap_pdf["selectivity_band"],
    categories=SELECTIVITY_ORDER,
    ordered=True,
)
heatmap_pdf["pell_band"] = pd.Categorical(
    heatmap_pdf["pell_band"],
    categories=PELL_ORDER,
    ordered=True,
)

# --- Plot ---
# INTENT: Create a heatmap (geom_tile) showing mean graduation rate by
# selectivity band (Y) and Pell share band (X). This is the primary
# visualization for the research question: do institutions with similar
# selectivity but different Pell shares have different graduation rates?
#
# REASONING: Heatmap (geom_tile) is the natural choice for a 2D categorical
# cross-tabulation with a continuous fill variable. It allows simultaneous
# comparison along both dimensions — readers can scan across a row (same
# selectivity, varying Pell) or down a column (same Pell, varying selectivity).
# The viridis colormap is used because it is:
#   - Perceptually uniform (equal changes in data = equal visual changes)
#   - Colorblind-safe (readable for all common color vision deficiencies)
#   - Prints well in grayscale
#
# ASSUMES:
#   - All 16 cells (4x4) have data; if any are missing, geom_tile will show gaps
#   - mean_grad_rate is on 0-100 scale, making percentage annotations intuitive
#   - The viridis scale direction (dark=low, bright=high) is intuitive for rates

# REASONING: Use dark text for light tiles and light text for dark tiles to
# ensure readability. The threshold of 50% is chosen because viridis transitions
# from dark to bright around the midpoint, so text contrast needs to flip there.
heatmap_pdf["text_color"] = heatmap_pdf["mean_grad_rate"].apply(
    lambda x: "white" if x < 45 else "black"
)

plot = (
    ggplot(heatmap_pdf, aes(x="pell_band", y="selectivity_band", fill="mean_grad_rate"))
    + geom_tile(color="white", size=0.5)  # White borders between cells for visual separation
    + geom_text(
        aes(label="cell_label", color="text_color"),
        size=8,
        show_legend=False,
    )
    + scale_fill_cmap(
        cmap_name="viridis",
        name="Mean Graduation\nRate (%)",
        limits=(0, 100),
    )
    + scale_color_identity()  # Use literal color values from text_color column
    + scale_x_discrete(limits=PELL_ORDER)
    + scale_y_discrete(limits=list(reversed(SELECTIVITY_ORDER)))  # Reversed so Highly Selective is at top
    + labs(
        title="Mean Graduation Rate by Selectivity and Pell Share",
        subtitle="Do institutions with similar selectivity but different Pell shares\nhave different graduation rates?",
        x="Pell Grant Recipient Share",
        y="Selectivity Band",
        caption="Source: IPEDS 2020, FSA 2020. Cell values show mean graduation rate (n institutions).",
    )
    + theme_minimal(base_size=11)
    + theme(
        figure_size=(10, 6),
        dpi=300,
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=10, color="#555555"),
        plot_caption=element_text(size=8, color="#888888"),
        axis_text_x=element_text(size=9, angle=0, ha="center"),
        axis_text_y=element_text(size=9),
        axis_title=element_text(size=11),
        panel_grid_major=element_blank(),
        panel_grid_minor=element_blank(),
        legend_position="right",
    )
    + guides(fill=guide_colorbar(barwidth=8, barheight=80))
)

# --- Save ---
# Persist figure to output directory at 300 DPI for publication quality.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
plot.save(OUTPUT_PATH, dpi=300, width=10, height=6, verbose=False)
print(f"\nSaved figure: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify figure was created, has reasonable file size,
# and the underlying data is consistent with expectations.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

# CP4.1: Figure file exists
fig_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if fig_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH}")

# CP4.2: Figure file size > 50KB (non-trivial image)
if fig_exists:
    fig_size = OUTPUT_PATH.stat().st_size
    fig_large_enough = fig_size > 50_000
    print(f"  [{'PASS' if fig_large_enough else 'FAIL'}] File size: {fig_size:,} bytes (>50KB required)")
else:
    fig_large_enough = False
    print(f"  [FAIL] File size check skipped (file missing)")

# CP4.3: All expected cells present (4x4 = 16)
cell_count = heatmap_data.shape[0]
all_cells_present = cell_count == 16
print(f"  [{'PASS' if all_cells_present else 'WARN'}] Cell count: {cell_count} (expected 16)")

# CP4.4: Mean graduation rates are in valid range (0-100)
min_rate = heatmap_data["mean_grad_rate"].min()
max_rate = heatmap_data["mean_grad_rate"].max()
rates_valid = min_rate >= 0 and max_rate <= 100
print(f"  [{'PASS' if rates_valid else 'FAIL'}] Rate range: {min_rate:.1f} - {max_rate:.1f} (expected 0-100)")

# CP4.5: All annotations present (cell_label column has no nulls)
labels_complete = heatmap_data["cell_label"].null_count() == 0
print(f"  [{'PASS' if labels_complete else 'FAIL'}] All cells have annotations: {labels_complete}")

# CP4.6: Total N across cells matches filtered dataset
total_n = heatmap_data["n"].sum()
n_matches = total_n == post_filter_rows
print(f"  [{'PASS' if n_matches else 'WARN'}] Total N: {total_n:,} (filtered dataset: {post_filter_rows:,})")

all_passed = all([fig_exists, fig_large_enough, all_cells_present, rates_valid, labels_complete])

assert fig_exists, "STOP: Figure file not created"
assert fig_large_enough, "STOP: Figure file too small"

print("\n" + "=" * 60)
print(f"CP4 VALIDATION: {'PASSED' if all_passed else 'WARNING'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:13:13
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py:139: Pandas4Warning: Constructing a Categorical with a dtype and values containing non-null entries not in that dtype's categories is deprecated and will raise in a future version.
# ============================================================
# Stage 8.2 (Step 9.3): Heatmap - Selectivity x Pell Share
# ============================================================
# Loaded: 2,528 rows x 26 cols
# Pre-filter rows: 2,528
# Required columns present: ['grad_rate_150pct', 'selectivity_band', 'pell_band']
# Post-filter rows: 1,704 (dropped 824 nulls)
# 
# Heatmap cells: 16 (expected 16 = 4x4)
# Heatmap data:
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
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py", line 209, in <module>
#     + guides(fill=guide_colorbar(barwidth=8, barheight=80))
#                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# TypeError: guide_colorbar.__init__() got an unexpected keyword argument 'barwidth'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
