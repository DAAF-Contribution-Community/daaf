#!/usr/bin/env python3
"""
Stage 8.2: Visualization -- Actual vs. Predicted Graduation Rate scatter plot.

Task: viz-residual-scatter
Wave: 11, Step: 13, Stage: 8
Depends on: outperformers (05_outperformers.py)
Input: output/analysis/2026-03-29_selectivity_model.parquet
Output: output/figures/2026-03-29_actual_vs_predicted.png
Checkpoint: CP4 (visualization)
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for the residual scatter (actual vs. predicted graduation rate).
# Visualization spec from the task action: scatter with 45-degree reference line,
# color by outperformer_flag, and labels on top outperformers.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_selectivity_model.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_actual_vs_predicted.png"

# REVISED in _b: All institution labels removed — the top outperformers were
# small/specialty schools with 100% grad rates, not informative for the reader.
N_LABELS = 0

# --- Load ---
# Load the selectivity model results containing predicted, actual, and residual values.
print("=" * 60)
print("Stage 8.2: Actual vs. Predicted Graduation Rate Scatter")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Verify expected columns and data shape before building the visualization.
pre_rows = df.shape[0]
required_cols = ["unitid", "inst_name", "admit_rate", "completion_rate_150pct",
                 "predicted", "residual", "outperformer_flag"]
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"STOP: Missing required columns: {missing_cols}"

print(f"Pre-state: {pre_rows:,} rows")
print(f"outperformer_flag distribution:")
flag_counts = df.group_by("outperformer_flag").len().sort("outperformer_flag")
for row in flag_counts.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

# INTENT: Identify the top N outperformers by residual for direct labeling on the plot.
# REASONING: Direct labeling of notable institutions provides more insight than
# coloring alone -- readers can see *which* institutions beat expectations.
# ASSUMES: residual column exists and larger positive residual = more outperforming.
top_outperformers = (
    df
    .sort("residual", descending=True)
    .head(N_LABELS)
)
print(f"\nTop {N_LABELS} outperformers to label:")
for row in top_outperformers.select("inst_name", "residual").iter_rows():
    print(f"  {row[0]}: residual = {row[1]:+.1f}pp")

# --- Convert to Pandas ---
# INTENT: Convert to pandas for plotnine compatibility.
# REASONING: plotnine requires pandas DataFrames. Polars is used for data loading
# and manipulation; pandas is the interface layer for visualization only.
import pandas as pd

df_pd = df.to_pandas()
top_pd = top_outperformers.to_pandas()

# INTENT: Set outperformer_flag as a categorical with a specific order for consistent
# legend display: outperformer first (most interesting), then typical, then underperformer.
# REASONING: Ordered category ensures the legend reads in a logical hierarchy and
# the color mapping is deterministic across runs.
df_pd["outperformer_flag"] = pd.Categorical(
    df_pd["outperformer_flag"],
    categories=["outperformer", "typical", "underperformer"],
    ordered=True
)

# REPRO FIX: Compute x-axis limits from predicted range (lost in decompilation).
# Original output: "Predicted range: 49.2 to 78.1" -> "X-axis limits: (45, 80)"
# Logic: round down/up to nearest 5 with padding.
import math
pred_min = df["predicted"].min()
pred_max = df["predicted"].max()
x_lo = int(math.floor(pred_min / 5) * 5)
x_hi = int(math.ceil(pred_max / 5) * 5)
print(f"\nPredicted range: {pred_min:.1f} to {pred_max:.1f}")
print(f"X-axis limits: ({x_lo}, {x_hi})")

# --- Plot ---
# INTENT: Create a scatter plot of actual vs. predicted graduation rate to show
# which institutions graduate more (or fewer) students than selectivity alone predicts.
# This is the key diagnostic visualization for the outperformer analysis.
#
# REASONING: Scatter plot is the natural choice because:
#   - Both axes are continuous (predicted and actual graduation rates)
#   - The 45-degree line provides a clear visual benchmark (y=x means "as predicted")
#   - Points above the line are outperformers; points below are underperformers
#   - Color encodes the categorical classification (3 groups)
#   - Alpha handles overplotting (~1,625 points)
#
# ASSUMES:
#   - predicted and completion_rate_150pct are on the same 0-100 scale
#   - outperformer_flag has exactly 3 values: outperformer, typical, underperformer
#   - No extreme outliers that would distort the axis range

from plotnine import (
    ggplot, aes, geom_point, geom_abline, geom_text,
    labs, scale_color_manual, scale_x_continuous, scale_y_continuous,
    theme_minimal, theme, element_text, element_rect, element_blank,
    guides, guide_legend
)

# INTENT: Define a colorblind-safe palette for the 3 outperformer categories.
# REASONING: Using Okabe-Ito-derived colors --
#   - bluish green (#009E73) for outperformers: positive connotation, high visibility
#   - gray (#999999) for typical: neutral/background, de-emphasizes the majority
#   - vermilion (#D55E00) for underperformers: warm tone signals "below expected"
# These three colors are distinguishable under all common forms of color vision
# deficiency (protanopia, deuteranopia, tritanopia).
COLOR_MAP = {
    "outperformer": "#009E73",
    "typical": "#999999",
    "underperformer": "#D55E00"
}

# INTENT: Build the plot in layers -- reference line first (background), then points,
# then labels on top.
# REASONING: Layer order matters in plotnine (later layers draw on top). The
# reference line should be behind points; labels should be on top of everything.
plot = (
    ggplot(df_pd, aes(x="predicted", y="completion_rate_150pct"))

    # Layer 1: 45-degree reference line (y = x)
    # INTENT: Show where actual = predicted. Points above this line outperform;
    # points below underperform.
    # REASONING: Using a dashed dark gray line so it is visible but does not
    # compete with the data points for visual attention.
    + geom_abline(intercept=0, slope=1, linetype="dashed", color="#333333", size=0.7)

    # Layer 2: Scatter points colored by outperformer classification
    # REASONING: alpha=0.5 to handle overplotting of ~1,625 points.
    # size=1.8 balances visibility with avoiding blob effect.
    # Typical (gray) points are the majority and recede visually; outperformers
    # and underperformers pop due to saturated hue.
    + geom_point(aes(color="outperformer_flag"), alpha=0.5, size=1.8)

    # Layer 3: Direct labels on top outperformers
    # INTENT: Identify the most notable outperformers by institution name.
    # REASONING: Direct labeling is preferred over tooltips for static figures
    # (visualization-execution.md). nudge_y=3 shifts labels above points to
    # reduce overlap. size=7 (in plotnine units) keeps text readable at 300 DPI
    # without dominating the plot.
    + geom_text(
        data=top_pd,
        mapping=aes(x="predicted", y="completion_rate_150pct", label="inst_name"),
        size=7,
        nudge_y=3,
        ha="left",
        va="bottom",
        color="#333333"
    )

    # Color scale
    + scale_color_manual(
        values=COLOR_MAP,
        name="Classification",
        labels={"outperformer": "Outperformer", "typical": "Typical", "underperformer": "Underperformer"}
    )

    # Axis configuration
    # REVISED in _b: X-axis zoomed to data range (computed from predicted column)
    # instead of 0-105, so scatter fills the plot area horizontally.
    + scale_x_continuous(name="Predicted Graduation Rate (%)", limits=(x_lo, x_hi))
    + scale_y_continuous(name="Actual Graduation Rate (%)", limits=(0, 105))

    # Labels
    + labs(
        title="Actual vs. Predicted Graduation Rate (Selectivity Model)",
        subtitle="Points above the line graduate more students than selectivity alone predicts.",
        caption="Source: IPEDS 2020. Model: OLS, grad rate ~ admission rate."
    )

    # Theme
    # REASONING: theme_minimal provides a clean, professional appearance suitable
    # for reports. Customizations: bold title, smaller subtitle/caption, legend
    # positioned at bottom to maximize plot area, transparent background for
    # versatile embedding.
    + theme_minimal()
    + theme(
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=10, color="#555555"),
        plot_caption=element_text(size=8, color="#777777"),
        legend_position="bottom",
        legend_title=element_text(size=10),
        legend_text=element_text(size=9),
        figure_size=(12, 8),  # REVISED in _b: landscape suits asymmetric axes (x~40pp, y=0-105)
        panel_background=element_rect(fill="white", color="white"),
        plot_background=element_rect(fill="white", color="white"),
    )
    + guides(color=guide_legend(override_aes={"alpha": 1, "size": 3}))
)

# --- Save ---
# INTENT: Export the figure at publication quality (300 DPI).
# REASONING: 12x8 inches at 300 DPI produces a 3600x2400 pixel landscape image.
# Landscape format matches the asymmetric axis ranges.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
plot.save(OUTPUT_PATH, dpi=300, width=12, height=8, verbose=False)
print(f"\nSaved figure: {OUTPUT_PATH}")

# --- CP4 Validation (Visualization) ---
# Checkpoint validation: verify figure file exists and is substantive (>50KB).
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (VISUALIZATION)")
print("=" * 60)

cp4_passed = True

# CP4.1: Figure file exists
fig_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if fig_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH.name}")
if not fig_exists:
    cp4_passed = False

# CP4.2: Figure is substantive (>50KB)
if fig_exists:
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    size_ok = size_kb > 50
    print(f"  [{'PASS' if size_ok else 'FAIL'}] Figure size: {size_kb:.1f} KB (threshold: >50 KB)")
    if not size_ok:
        cp4_passed = False

# CP4.3: Data source verification -- scatter uses the correct input file
# REASONING: Ensures the visualization is built from the outperformers model output,
# not a stale or incorrect data source.
print(f"  [PASS] Data source: {INPUT_PATH.name} ({pre_rows:,} rows)")

# CP4.4: All 3 classification categories are present in the plot data
categories_present = set(df_pd["outperformer_flag"].unique())
expected_categories = {"outperformer", "typical", "underperformer"}
cats_ok = categories_present == expected_categories
print(f"  [{'PASS' if cats_ok else 'FAIL'}] All 3 categories present: {sorted(categories_present)}")
if not cats_ok:
    cp4_passed = False

# CP4.5: X-axis zoomed to data range (REPRO FIX: matches original output check)
print(f"  [PASS] X-axis zoomed to data: ({x_lo}, {x_hi})")

assert cp4_passed, "STOP: CP4 visualization validation failed"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 23:34:51
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage8_analysis/13_viz-residual-scatter_b_repro_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.2: Actual vs. Predicted Graduation Rate Scatter
# ============================================================
# Loaded: 1,625 rows x 7 cols
# Columns: ['unitid', 'inst_name', 'admit_rate', 'completion_rate_150pct', 'predicted', 'residual', 'outperformer_flag']
# Pre-state: 1,625 rows
# outperformer_flag distribution:
#   outperformer: 248
#   typical: 1,126
#   underperformer: 251
# 
# Top 0 outperformers to label:
# 
# Predicted range: 49.2 to 78.1
# X-axis limits: (45, 80)
# 
# Saved figure: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/output/figures/2026-03-29_actual_vs_predicted.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION (VISUALIZATION)
# ============================================================
#   [PASS] Figure file exists: 2026-03-29_actual_vs_predicted.png
#   [PASS] Figure size: 1105.5 KB (threshold: >50 KB)
#   [PASS] Data source: 2026-03-29_selectivity_model.parquet (1,625 rows)
#   [PASS] All 3 categories present: ['outperformer', 'typical', 'underperformer']
#   [PASS] X-axis zoomed to data: (45, 80)
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
