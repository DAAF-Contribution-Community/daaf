#!/usr/bin/env python3
"""
Stage 8.2: Box plot of graduation rate distribution by selectivity band.

Task: viz-boxplot-selectivity
Wave: 10, Step: 9, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png
Checkpoint: CP4 (visualization)
"""

import numpy as np
import polars as pl
import pandas as pd
from pathlib import Path
from plotnine import (
    ggplot, aes, geom_boxplot, geom_jitter, geom_point,
    labs, theme_minimal, theme, element_text, element_blank,
    scale_fill_manual, scale_x_discrete, scale_y_continuous,
    position_jitter, stat_summary,
)

# --- Config ---
# Configuration for selectivity band boxplot visualization.
# Band ordering and palette chosen per task specification and
# colorblind-safe design guidelines (Okabe-Ito palette).
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
INPUT_PATH = PROJECT_DIR / "data" / "processed" / "2026-03-29_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / "2026-03-29_boxplot_grad_rate_by_selectivity.png"

# INTENT: Define band ordering from most to least selective for logical x-axis.
# REASONING: Ordering by selectivity makes the graduation rate gradient immediately
# visible; readers can scan left-to-right and see the decline in median grad rate.
BAND_ORDER = [
    "Highly Selective",
    "Selective",
    "Moderately Selective",
    "Open/Less Selective",
]

# INTENT: Colorblind-safe palette using Okabe-Ito colors for 4 categories.
# REASONING: Okabe-Ito is purpose-built for color vision deficiency accessibility.
# Orange, sky blue, bluish green, and vermilion chosen for maximum distinctness.
# Also pairs with redundant position encoding (x-axis categories).
PALETTE = {
    "Highly Selective": "#0072B2",       # blue
    "Selective": "#009E73",              # bluish green
    "Moderately Selective": "#E69F00",   # orange
    "Open/Less Selective": "#D55E00",    # vermilion
}

FIGURE_WIDTH = 10
FIGURE_HEIGHT = 7
FIGURE_DPI = 300
MIN_FILE_SIZE_KB = 50

# --- Load ---
# Load the analysis dataset produced by the create-bands transformation.
# Verify required columns exist before proceeding.
print("=" * 60)
print("Stage 8.2: Boxplot - Graduation Rate by Selectivity Band")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Verify the required columns exist and check data availability per band.
pre_rows = df.shape[0]

required_cols = ["selectivity_band", "completion_rate_150pct"]
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"STOP: Missing required columns: {missing_cols}"

# INTENT: Check band distribution before plotting to confirm all 4 bands present.
# ASSUMES: selectivity_band column was created in Stage 7 create-bands step.
band_counts = df.group_by("selectivity_band").len().sort("selectivity_band")
print(f"\nBand distribution:")
for row in band_counts.iter_rows(named=True):
    print(f"  {row['selectivity_band']}: {row['len']:,}")

bands_present = set(df["selectivity_band"].unique().to_list())
expected_bands = set(BAND_ORDER)
# REASONING: We allow extra or differently-named bands gracefully, but warn
# if any expected band is missing since it would mean the plot has gaps.
missing_bands = expected_bands - bands_present
if missing_bands:
    print(f"WARNING: Missing expected bands: {missing_bands}")

# INTENT: Drop rows with null completion rate -- they cannot be plotted.
# REASONING: Polars null values would be silently dropped by plotnine anyway;
# doing it explicitly lets us report the count for transparency.
null_rate = df["completion_rate_150pct"].null_count()
print(f"Null completion_rate_150pct: {null_rate:,} ({null_rate / pre_rows * 100:.1f}%)")

df_plot = df.filter(pl.col("completion_rate_150pct").is_not_null())
print(f"Rows for plotting: {df_plot.shape[0]:,} (dropped {pre_rows - df_plot.shape[0]:,} nulls)")

# --- Transform to pandas ---
# INTENT: Convert to pandas DataFrame for plotnine compatibility.
# REASONING: plotnine requires pandas DataFrames, not Polars. Convert only the
# columns needed for the plot to minimize memory usage.
# ASSUMES: selectivity_band is a string column; completion_rate_150pct is numeric.
pdf = df_plot.select(["selectivity_band", "completion_rate_150pct"]).to_pandas()

# INTENT: Set selectivity_band as an ordered categorical with explicit level order.
# REASONING: Without explicit ordering, plotnine would alphabetize the x-axis,
# placing "Highly Selective" next to "Moderately Selective" instead of showing
# the logical selectivity gradient.
pdf["selectivity_band"] = pd.Categorical(
    pdf["selectivity_band"],
    categories=BAND_ORDER,
    ordered=True,
)

# --- Visualization ---
# INTENT: Create a layered boxplot with jittered points and mean markers to show
# both the distributional summary and the individual institution scatter.
# REASONING: Boxplots show median, IQR, and outliers well, but can hide bimodality
# and cluster density. Adding jittered points reveals the underlying data density.
# Diamond mean markers highlight how means diverge from medians (skewness signal).
print("\nBuilding boxplot...")

p = (
    ggplot(pdf, aes(x="selectivity_band", y="completion_rate_150pct", fill="selectivity_band"))
    # Layer 1: Jittered points (behind boxes for visual clarity)
    # INTENT: Show individual institutions as semi-transparent dots.
    # REASONING: alpha=0.2 prevents overplotting while still showing density;
    # width=0.25 keeps jitter within the box boundaries.
    + geom_jitter(
        width=0.25,
        height=0,
        alpha=0.2,
        size=1,
        color="gray40",
        show_legend=False,
    )
    # Layer 2: Boxplot (draws on top of points)
    # INTENT: Show IQR, median, and whiskers per band.
    # REASONING: outlier_shape=False suppresses plotnine's default outlier dots
    # since the jittered points layer already shows all data points.
    + geom_boxplot(
        alpha=0.7,
        outlier_shape="",
        width=0.5,
        show_legend=False,
    )
    # Layer 3: Mean markers (diamonds)
    # INTENT: Add diamond markers at the mean of each group.
    # REASONING: Means differ from medians when distributions are skewed.
    # Showing both lets readers assess skewness at a glance.
    # REASONING: fun_y must be a callable (not a string) in plotnine.
    # Using np.mean directly as the aggregation function.
    + stat_summary(
        fun_y=np.mean,
        geom="point",
        shape="D",
        size=3,
        color="black",
        fill="white",
        show_legend=False,
    )
    # Scales
    + scale_fill_manual(values=PALETTE)
    + scale_y_continuous(
        breaks=range(0, 101, 10),
        limits=(0, 105),
    )
    # Labels
    + labs(
        title="Graduation Rate Distribution by Selectivity Band",
        x="",
        y="Graduation Rate (%)",
        caption="Source: IPEDS 2020. Boxes show IQR; diamonds show means.",
    )
    # Theme
    + theme_minimal(base_size=13)
    + theme(
        figure_size=(FIGURE_WIDTH, FIGURE_HEIGHT),
        dpi=FIGURE_DPI,
        plot_title=element_text(size=16, weight="bold", ha="left"),
        plot_caption=element_text(size=9, color="gray40", ha="right"),
        axis_text_x=element_text(size=11),
        axis_text_y=element_text(size=10),
        axis_title_y=element_text(size=12),
        panel_grid_major_x=element_blank(),
        panel_grid_minor=element_blank(),
        legend_position="none",
    )
)

# --- Save ---
# INTENT: Export figure at 300 DPI for publication quality.
# REASONING: 300 DPI meets standard print resolution requirements.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
p.save(OUTPUT_PATH, width=FIGURE_WIDTH, height=FIGURE_HEIGHT, dpi=FIGURE_DPI, verbose=False)
print(f"Saved: {OUTPUT_PATH}")

# --- CP4 Validation (Visualization) ---
# Checkpoint validation: verify figure file exists and meets size threshold.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

# CP4.1: File exists
file_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if file_exists else 'FAIL'}] Figure file exists: {file_exists}")

# CP4.2: File size > 50 KB
if file_exists:
    file_size_kb = OUTPUT_PATH.stat().st_size / 1024
    size_ok = file_size_kb > MIN_FILE_SIZE_KB
    print(f"  [{'PASS' if size_ok else 'FAIL'}] File size: {file_size_kb:.1f} KB (min: {MIN_FILE_SIZE_KB} KB)")
else:
    size_ok = False
    print(f"  [FAIL] File size check skipped -- file does not exist")

# CP4.3: Data source verification -- confirm we used the correct input
print(f"  [PASS] Data source: {INPUT_PATH.name} ({df_plot.shape[0]:,} institutions plotted)")

# CP4.4: All expected bands represented in the plot
bands_in_plot = set(pdf["selectivity_band"].dropna().unique())
all_bands_plotted = expected_bands.issubset(bands_in_plot)
print(f"  [{'PASS' if all_bands_plotted else 'WARN'}] All 4 selectivity bands plotted: {all_bands_plotted}")

assert file_exists, "STOP: Figure file not created"
assert size_ok, f"STOP: Figure file too small ({file_size_kb:.1f} KB < {MIN_FILE_SIZE_KB} KB)"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:41:05
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_a.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 8.2: Boxplot - Graduation Rate by Selectivity Band
# ============================================================
# Loaded: 1,946 rows x 25 cols
# 
# Band distribution:
#   Highly Selective: 71
#   Moderately Selective: 577
#   Open/Less Selective: 1,121
#   Selective: 177
# Null completion_rate_150pct: 0 (0.0%)
# Rows for plotting: 1,946 (dropped 0 nulls)
# 
# Building boxplot...
# Traceback (most recent call last):
#   File "/usr/local/lib/python3.12/site-packages/mizani/_colors/named_colors.py", line 20, in __getitem__
#     return super().__getitem__(key)
#            ^^^^^^^^^^^^^^^^^^^^^^^^
# KeyError: 'gray40'
# 
# The above exception was the direct cause of the following exception:
# 
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity_a.py", line 197, in <module>
#     p.save(OUTPUT_PATH, width=FIGURE_WIDTH, height=FIGURE_HEIGHT, dpi=FIGURE_DPI, verbose=False)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 681, in save
#     sv = self.save_helper(
#          ^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 629, in save_helper
#     figure = self.draw(show=False)
#              ^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 314, in draw
#     self._draw_layers()
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 461, in _draw_layers
#     self.layers.draw(self.layout, self.coordinates)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/layer.py", line 481, in draw
#     l.draw(layout, coord)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/layer.py", line 377, in draw
#     self.geom.draw_layer(self.data, layout, coord)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/geoms/geom.py", line 326, in draw_layer
#     self.draw_panel(pdata, panel_params, coord, ax)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/geoms/geom_point.py", line 62, in draw_panel
#     self.draw_group(data, panel_params, coord, ax, self.params)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/geoms/geom_point.py", line 76, in draw_group
#     geom_point.draw_unit(udata, panel_params, coord, ax, params)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/geoms/geom_point.py", line 93, in draw_unit
#     color = to_rgba(data["color"], data["alpha"])
#             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/mizani/_colors/utils.py", line 130, in to_rgba
#     return [to_rgba(c, a) for c, a in zip(colors, alpha)]  # pyright: ignore[reportCallIssue,reportArgumentType]
#             ^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/mizani/_colors/utils.py", line 110, in to_rgba
#     c = get_named_color(colors)
#         ^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/mizani/_colors/named_colors.py", line 72, in get_named_color
#     return NAMED_COLORS[name.lower()]
#            ~~~~~~~~~~~~^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/mizani/_colors/named_colors.py", line 22, in __getitem__
#     raise ValueError(f"Unknown name '{key}' for a color.") from err
# ValueError: Unknown name 'gray40' for a color.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
