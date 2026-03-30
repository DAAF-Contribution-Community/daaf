#!/usr/bin/env python3
"""
Stage 8.2: Scatter plot of graduation rate vs. admission rate.

Task: viz-scatter-grad-admit
Wave: 10, Step: 8, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/figures/2026-03-29_grad_rate_vs_admission_rate.png
Checkpoint: CP4 (visualization)
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for the graduation rate vs. admission rate scatter plot.
# This visualization is the primary figure for H1: the relationship between
# institutional selectivity (measured by admission rate) and graduation rate.
# Prior analysis found Pearson r = -0.334 (moderate negative correlation).
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_grad_rate_vs_admission_rate.png"

# Pearson r from prior correlation analysis (Stage 8.1, Step 4)
PEARSON_R = -0.334

# REASONING: Okabe-Ito palette is purpose-built for color vision deficiency.
# Four colors needed for four selectivity bands. Ordered from most to least
# selective to create a visual gradient that reinforces the ordinal nature
# of the bands. Using the recommended order from visualization-execution.md.
BAND_COLORS = {
    "Highly Selective": "#0072B2",    # blue -- most selective, visually prominent
    "Selective": "#009E73",           # bluish green
    "Moderately Selective": "#E69F00", # orange
    "Open/Less Selective": "#CC79A7",  # reddish purple -- least selective
}

# REASONING: Order bands from most to least selective so the legend reads
# in a meaningful sequence that matches the x-axis direction (low admit rate
# = more selective on the left, high admit rate = less selective on the right).
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands).
print("=" * 60)
print("Stage 8.2: Scatter -- Graduation Rate vs. Admission Rate")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state before filtering. The scatter plot will only show institutions
# with non-null admit_rate values. Open-admissions institutions lack an
# admission rate and will be excluded from this visualization.
pre_rows = df.shape[0]
admit_nulls = df["admit_rate"].null_count()
grad_nulls = df["completion_rate_150pct"].null_count()
band_nulls = df["selectivity_band"].null_count()

print(f"\nPre-state: {pre_rows:,} rows")
print(f"  admit_rate nulls: {admit_nulls:,}")
print(f"  completion_rate_150pct nulls: {grad_nulls:,}")
print(f"  selectivity_band nulls: {band_nulls:,}")

# INTENT: Filter to institutions with non-null values for both axis variables
# and the color variable (selectivity_band). Institutions with null admit_rate
# are typically open-admissions and cannot be placed on the x-axis.
# REASONING: Using drop_nulls on the three plot-critical columns rather than
# filtering each individually, since all three are required for the scatter.
# ASSUMES: selectivity_band was created in Stage 7 create-bands step and
# contains exactly the four categories in BAND_ORDER for non-null admit_rate rows.
df_plot = df.drop_nulls(subset=["admit_rate", "completion_rate_150pct", "selectivity_band"])

print(f"After filtering nulls: {df_plot.shape[0]:,} rows")
print(f"  Dropped: {pre_rows - df_plot.shape[0]:,} rows ({(pre_rows - df_plot.shape[0]) / pre_rows * 100:.1f}%)")

# Verify band distribution in filtered data
band_counts = df_plot.group_by("selectivity_band").len().sort("len", descending=True)
print(f"\nBand distribution in plot data:")
for row in band_counts.iter_rows(named=True):
    print(f"  {row['selectivity_band']}: {row['len']:,}")

# --- Convert to pandas ---
# INTENT: Convert to pandas DataFrame for plotnine compatibility.
# REASONING: plotnine requires pandas DataFrames (not Polars). Convert only
# the filtered plot data to minimize memory usage.
# ASSUMES: The filtered dataset fits comfortably in memory (~1-2K rows).
import pandas as pd

df_pd = df_plot.select([
    "admit_rate", "completion_rate_150pct", "selectivity_band"
]).to_pandas()

# INTENT: Set selectivity_band as an ordered categorical so plotnine renders
# the legend in the correct order (most selective first).
# REASONING: Without explicit ordering, plotnine sorts categories alphabetically,
# which would produce a nonsensical legend order.
df_pd["selectivity_band"] = pd.Categorical(
    df_pd["selectivity_band"],
    categories=BAND_ORDER,
    ordered=True
)

# --- Plot ---
# INTENT: Create a scatter plot showing the relationship between admission rate
# (x-axis, selectivity proxy) and graduation rate (y-axis, outcome). Points are
# colored by selectivity band to show how the four band categories distribute
# across the bivariate space. An OLS trend line shows the overall linear
# association, and a Pearson r annotation quantifies the correlation.
#
# REASONING: Scatter plot is the gold standard for showing correlation between
# two continuous variables (both axes use position encoding, rank 1 in
# Cleveland & McGill hierarchy). Alpha=0.5 handles moderate overplotting
# (~1.6K points). The OLS trend line provides a visual summary of the linear
# relationship, complementing the Pearson r statistic.
#
# ASSUMES:
#   - admit_rate is on a 0-100 scale (percentage)
#   - completion_rate_150pct is on a 0-100 scale (percentage)
#   - selectivity_band contains exactly the four categories in BAND_ORDER
from plotnine import (
    ggplot, aes, geom_point, geom_smooth, annotate,
    labs, scale_color_manual, theme_minimal, theme,
    element_text, element_blank, element_line,
    scale_x_continuous, scale_y_continuous, guides, guide_legend,
)

p = (
    ggplot(df_pd, aes(x="admit_rate", y="completion_rate_150pct", color="selectivity_band"))
    + geom_point(alpha=0.5, size=1.8)
    # INTENT: Add OLS trend line across all points (ignoring band grouping)
    # to show the overall linear relationship.
    # REASONING: inherit_aes=False with explicit x/y ensures the smooth line
    # is fit to ALL data, not per-band. Gray color distinguishes it from the
    # data points. se=True shows the 95% CI band.
    + geom_smooth(
        aes(x="admit_rate", y="completion_rate_150pct"),
        method="lm",
        color="#555555",
        fill="#CCCCCC",
        alpha=0.3,
        inherit_aes=False,
        data=df_pd,
        se=True,
        linetype="solid",
        size=1.2,
    )
    # INTENT: Annotate the plot with the Pearson r statistic so the reader
    # can immediately see the strength of the linear association.
    # REASONING: Placed in the upper-right corner (high admit rate, high grad
    # rate region) where there is typically empty space in this distribution.
    # Using italic formatting per APA convention for statistics.
    + annotate(
        "text",
        x=85,
        y=95,
        label=f"Pearson r = {PEARSON_R:.3f}",
        size=10,
        color="#333333",
        ha="center",
    )
    + scale_color_manual(
        name="Selectivity Band",
        values=BAND_COLORS,
    )
    + scale_x_continuous(
        name="Admission Rate (%)",
        breaks=[0, 20, 40, 60, 80, 100],
        limits=(0, 105),
    )
    + scale_y_continuous(
        name="Graduation Rate (%)",
        breaks=[0, 20, 40, 60, 80, 100],
        limits=(0, 105),
    )
    + labs(
        title="Graduation Rate vs. Admission Rate at U.S. Four-Year Institutions",
        subtitle="Each point is one institution. Lower admission rate = more selective.",
        caption="Source: IPEDS 2020. Graduation rate = 150% time, first-time full-time students.",
    )
    + guides(color=guide_legend(override_aes={"size": 3, "alpha": 1}))
    + theme_minimal(base_size=11)
    + theme(
        figure_size=(10, 7),
        dpi=300,
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=11, color="#555555"),
        plot_caption=element_text(size=8, color="#777777", ha="left"),
        legend_position="bottom",
        legend_title=element_text(size=10, weight="bold"),
        legend_text=element_text(size=9),
        axis_title=element_text(size=11),
        axis_text=element_text(size=9),
        panel_grid_minor=element_blank(),
        panel_grid_major=element_line(color="#E0E0E0", size=0.4),
    )
)

# --- Save ---
# Persist the figure as PNG at 300 DPI, 10x7 inches.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
p.save(OUTPUT_PATH, dpi=300, width=10, height=7, verbose=False)
print(f"\nSaved figure: {OUTPUT_PATH}")

# --- CP4 Validation (Visualization) ---
# Checkpoint validation: verify figure was saved, file size is reasonable,
# and data source is correct.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

import os

# CP4.1: Figure file exists
file_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if file_exists else 'FAIL'}] Figure file exists: {file_exists}")

# CP4.2: File size > 50 KB (non-trivial figure)
if file_exists:
    file_size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    size_ok = file_size_kb > 50
    print(f"  [{'PASS' if size_ok else 'FAIL'}] File size: {file_size_kb:.1f} KB (>50 KB required)")
else:
    size_ok = False
    print(f"  [FAIL] File size: cannot check, file does not exist")

# CP4.3: Correct data source used (analysis.parquet from Stage 7)
source_ok = "analysis.parquet" in str(INPUT_PATH)
print(f"  [{'PASS' if source_ok else 'FAIL'}] Correct data source: {INPUT_PATH.name}")

# CP4.4: Point count matches filtered data
# REASONING: The number of points in the scatter should equal the number of
# rows after filtering nulls. We verify this by checking df_plot row count.
points_count = df_plot.shape[0]
points_ok = points_count > 100  # Expect ~1,600+ institutions with admit_rate
print(f"  [{'PASS' if points_ok else 'FAIL'}] Point count: {points_count:,} institutions plotted")

# CP4.5: All four selectivity bands represented
bands_in_data = set(df_plot["selectivity_band"].unique().to_list())
bands_expected = set(BAND_ORDER)
bands_ok = bands_in_data == bands_expected
print(f"  [{'PASS' if bands_ok else 'FAIL'}] All 4 bands present: {sorted(bands_in_data)}")

all_passed = all([file_exists, size_ok, source_ok, points_ok, bands_ok])
assert file_exists, "STOP: Figure file not created"
assert size_ok, "STOP: Figure file too small (< 50 KB)"

print(f"\n" + "=" * 60)
print(f"CP4 VALIDATION: {'PASSED' if all_passed else 'FAILED'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:40:28
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/08_viz-scatter-grad-admit.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.2: Scatter -- Graduation Rate vs. Admission Rate
# ============================================================
# Loaded: 1,946 rows x 25 cols
# 
# Pre-state: 1,946 rows
#   admit_rate nulls: 321
#   completion_rate_150pct nulls: 0
#   selectivity_band nulls: 0
# After filtering nulls: 1,625 rows
#   Dropped: 321 rows (16.5%)
# 
# Band distribution in plot data:
#   Open/Less Selective: 800
#   Moderately Selective: 577
#   Selective: 177
#   Highly Selective: 71
# 
# Saved figure: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION (Visualization)
# ============================================================
#   [PASS] Figure file exists: True
#   [PASS] File size: 1198.0 KB (>50 KB required)
#   [PASS] Correct data source: 2026-03-29_analysis.parquet
#   [PASS] Point count: 1,625 institutions plotted
#   [PASS] All 4 bands present: ['Highly Selective', 'Moderately Selective', 'Open/Less Selective', 'Selective']
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
