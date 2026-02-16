#!/usr/bin/env python3
"""
Stage 8.2 | Step 9.2 | viz-boxplot-selectivity
===============================================
Research Question: Are high college graduation rates a signal of institutional
quality, or primarily a reflection of admissions selectivity and student body
demographics?

Task: Create a box plot of graduation rate distributions by selectivity band,
with jittered individual institution points overlaid, to visualize the spread
and central tendency of graduation rates across selectivity categories.

Input:  data/processed/2026-02-15_analysis.parquet
Output: output/figures/2026-02-15_boxplot_grad_rate_by_selectivity.png

Observable Truth Contribution: Stakeholders can visually compare graduation
rate distributions across selectivity tiers and see the extent to which
selectivity explains variation in graduation outcomes.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan. The analysis dataset was
# produced in Stage 7 (create-bands) and contains the selectivity_band
# column used for grouping.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATA_PROCESSED = PROJECT_DIR / "data" / "processed"
OUTPUT_FIGURES = PROJECT_DIR / "output" / "figures"
DATE_PREFIX = "2026-02-15"

INPUT_PARQUET = DATA_PROCESSED / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = OUTPUT_FIGURES / f"{DATE_PREFIX}_boxplot_grad_rate_by_selectivity.png"

# Selectivity band ordering from most to least selective.
# REASONING: Ordering bands in descending selectivity puts the "quality"
# narrative gradient on the x-axis, making the visual argument clearer.
# The audience expects to see Highly Selective on the left.
BAND_ORDER = [
    "Highly Selective",
    "Selective",
    "Moderately Selective",
    "Less Selective/Open",
]

# Colorblind-safe palette — 4 distinct colors chosen to be distinguishable
# under deuteranopia and protanopia (most common color vision deficiencies).
# REASONING: Using a blue-orange-green-purple scheme avoids the red-green
# confusion axis. Colors sourced from the ColorBrewer "Set2" qualitative
# palette which is certified colorblind-safe for 4 categories.
FILL_COLORS = {
    "Highly Selective": "#66c2a5",     # teal
    "Selective": "#fc8d62",            # orange
    "Moderately Selective": "#8da0cb", # periwinkle
    "Less Selective/Open": "#e78ac3",  # pink
}

# --- Load ---
# Load the analysis dataset produced by Stage 7. We need grad_rate_150pct
# and selectivity_band columns. Filter to non-null graduation rates since
# box plots cannot meaningfully represent missing values.
print("=" * 60)
print("Stage 8.2 | Step 9.2: Boxplot — Graduation Rate by Selectivity Band")
print("=" * 60)

df = pl.read_parquet(INPUT_PARQUET)
print(f"\nLoaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state before filtering to quantify how many institutions
# are excluded due to missing graduation rate data.
pre_rows = df.shape[0]
null_grad_rate = df.filter(pl.col("grad_rate_150pct").is_null()).shape[0]
null_pct = null_grad_rate / pre_rows * 100 if pre_rows > 0 else 0
print(f"Pre-filter: {pre_rows:,} total rows")
print(f"Null grad_rate_150pct: {null_grad_rate:,} ({null_pct:.1f}%)")

# Show null rates per selectivity band so we can assess whether missingness
# is differential across bands (which would bias the visualization).
print("\nNull grad_rate_150pct by selectivity_band:")
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

# --- Transform ---
# INTENT: Filter to rows with non-null graduation rates so the box plot
# has valid data for every institution plotted.
# REASONING: Box plots compute quartiles from observed values; nulls would
# be silently dropped by plotnine anyway, but explicit filtering lets us
# report the exact N per band in the console output.
# ASSUMES: selectivity_band is non-null for all rows (created in Stage 7
# from admission_rate which was used to define bands).
df_plot = df.filter(pl.col("grad_rate_150pct").is_not_null())

post_rows = df_plot.shape[0]
row_change_pct = ((post_rows - pre_rows) / pre_rows * 100) if pre_rows > 0 else 0
print(f"\nPost-filter: {post_rows:,} rows (change: {row_change_pct:+.1f}%)")

# Also filter out any rows where selectivity_band is null (institutions
# without admission rate data cannot be banded).
pre_band_filter = df_plot.shape[0]
df_plot = df_plot.filter(pl.col("selectivity_band").is_not_null())
post_band_filter = df_plot.shape[0]
if pre_band_filter != post_band_filter:
    print(f"Removed {pre_band_filter - post_band_filter} rows with null selectivity_band")
print(f"Final plot dataset: {df_plot.shape[0]:,} rows")

# Report counts per band for the figure
print("\nInstitutions per selectivity band (in plot):")
band_counts = (
    df_plot.group_by("selectivity_band")
    .agg(pl.len().alias("n"))
    .sort("selectivity_band")
)
print(band_counts)

# Summary statistics per band for validation
print("\nGraduation rate summary by selectivity band:")
band_stats = (
    df_plot.group_by("selectivity_band")
    .agg([
        pl.col("grad_rate_150pct").mean().round(1).alias("mean"),
        pl.col("grad_rate_150pct").median().round(1).alias("median"),
        pl.col("grad_rate_150pct").std().round(1).alias("std"),
        pl.col("grad_rate_150pct").min().alias("min"),
        pl.col("grad_rate_150pct").max().alias("max"),
    ])
    .sort("selectivity_band")
)
print(band_stats)

# --- Plot ---
# INTENT: Create a box plot showing the distribution of 150%-time graduation
# rates for each selectivity band, overlaid with jittered individual points.
# This visualization directly addresses the research question by showing
# whether graduation rates are tightly clustered within bands (suggesting
# selectivity is a strong predictor) or widely dispersed (suggesting other
# factors matter).
#
# REASONING: Box plot + jitter combination because:
#   - Box plot shows quartiles, median, and outliers (summary statistics)
#   - Jittered points show the actual data distribution and density
#   - Together they reveal both central tendency AND the full spread
#   - This is more informative than box plot alone (which hides bimodality)
#     or violin plot (which can over-smooth with small n in Highly Selective)
#   - Alpha=0.25 on points prevents overplotting while showing density
#
# ASSUMES:
#   - grad_rate_150pct is on 0-100 scale (percentage, not proportion)
#   - selectivity_band is categorical with exactly 4 values matching BAND_ORDER
#   - No extreme outliers that would distort the scale (verified in EDA)

# Convert to pandas for plotnine (plotnine requires pandas DataFrames)
df_pd = df_plot.select(["selectivity_band", "grad_rate_150pct"]).to_pandas()

# INTENT: Convert selectivity_band to ordered categorical so the x-axis
# displays bands in the intended order (most to least selective).
# REASONING: Without explicit ordering, pandas/plotnine would use
# alphabetical order which puts "Highly Selective" after "Less Selective/Open".
import pandas as pd
df_pd["selectivity_band"] = pd.Categorical(
    df_pd["selectivity_band"],
    categories=BAND_ORDER,
    ordered=True,
)

from plotnine import (
    ggplot, aes, geom_boxplot, geom_jitter,
    labs, theme_minimal, theme, element_text,
    scale_fill_manual, scale_x_discrete,
    position_jitter,
)

plot = (
    ggplot(df_pd, aes(x="selectivity_band", y="grad_rate_150pct", fill="selectivity_band"))
    # Box plot layer: shows quartiles, median line, and whiskers.
    # outlier_shape="" suppresses the default outlier points since the jitter
    # layer already shows all individual data points.
    + geom_boxplot(
        outlier_shape="",   # suppress outlier dots (jitter shows all points)
        width=0.6,          # narrower boxes leave room for jitter
        alpha=0.7,          # slight transparency so jitter points show through
    )
    # Jittered points layer: shows every individual institution.
    # REASONING: width=0.15 keeps points within box boundaries;
    # alpha=0.25 handles overplotting (especially in Less Selective/Open, n~1000);
    # size=0.8 keeps points small enough not to obscure the boxes.
    + geom_jitter(
        width=0.15,
        alpha=0.25,
        size=0.8,
        color="black",  # fixed color for all points for clarity against fill
    )
    # Colorblind-safe fill palette
    + scale_fill_manual(values=FILL_COLORS, guide=False)  # guide=False removes redundant legend
    # X-axis ordering enforced via the Categorical, but explicit limits ensure
    # correct rendering even if plotnine ignores the ordered flag.
    + scale_x_discrete(limits=BAND_ORDER)
    + labs(
        title="Graduation Rate Distribution by Selectivity Band",
        subtitle="4-Year Public and Private Nonprofit Institutions, 2020",
        x="Selectivity Band",
        y="Graduation Rate (150% time, %)",
        caption="Source: IPEDS 2020.",
    )
    # REASONING: theme_minimal removes chart junk (Tufte principle) while
    # retaining grid lines for reading values. Base size 11 is readable at
    # 300 DPI on standard report page width. Rotating x labels slightly
    # prevents overlap for the longer band names.
    + theme_minimal(base_size=11)
    + theme(
        figure_size=(10, 7),
        dpi=300,
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=11),
        axis_text_x=element_text(size=10),
        axis_title=element_text(size=11),
        plot_caption=element_text(size=8, color="gray"),
    )
)

# --- Save ---
# Persist the figure to the output/figures directory.
# Output path matches the Plan's file specification.
OUTPUT_FIGURES.mkdir(parents=True, exist_ok=True)
plot.save(OUTPUT_PATH, width=10, height=7, dpi=300, verbose=False)
print(f"\nFigure saved: {OUTPUT_PATH}")

# --- Validate (CP4) ---
# Verify the output file exists and has reasonable size (>50KB indicates
# a real plot was rendered, not a blank or error image).
import os
if OUTPUT_PATH.exists():
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    if file_size > 50_000:
        print("CP4: PASSED — Figure exists and size > 50KB")
    else:
        print(f"CP4: WARNING — Figure exists but only {file_size / 1024:.1f} KB (expected >50KB)")
else:
    print("CP4: FAILED — Output file does not exist")

# Validate that all 4 bands are represented in the plot data
bands_in_data = set(df_pd["selectivity_band"].dropna().unique())
expected_bands = set(BAND_ORDER)
missing_bands = expected_bands - bands_in_data
if missing_bands:
    print(f"CP4: WARNING — Missing bands in plot data: {missing_bands}")
else:
    print(f"CP4: PASSED — All 4 selectivity bands present in plot data")

print(f"\nRow change from full dataset: {row_change_pct:+.1f}%")
print("Done.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:12:27
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 8.2 | Step 9.2: Boxplot — Graduation Rate by Selectivity Band
# ============================================================
# 
# Loaded: 2,528 rows x 26 cols
# Pre-filter: 2,528 total rows
# Null grad_rate_150pct: 732 (29.0%)
# 
# Null grad_rate_150pct by selectivity_band:
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
# 
# Post-filter: 1,796 rows (change: -29.0%)
# Final plot dataset: 1,796 rows
# 
# Institutions per selectivity band (in plot):
# shape: (4, 2)
# ┌──────────────────────┬──────┐
# │ selectivity_band     ┆ n    │
# │ ---                  ┆ ---  │
# │ str                  ┆ u32  │
# ╞══════════════════════╪══════╡
# │ Highly Selective     ┆ 69   │
# │ Less Selective/Open  ┆ 1004 │
# │ Moderately Selective ┆ 564  │
# │ Selective            ┆ 159  │
# └──────────────────────┴──────┘
# 
# Graduation rate summary by selectivity band:
# shape: (4, 6)
# ┌──────────────────────┬──────┬────────┬──────┬──────┬───────┐
# │ selectivity_band     ┆ mean ┆ median ┆ std  ┆ min  ┆ max   │
# │ ---                  ┆ ---  ┆ ---    ┆ ---  ┆ ---  ┆ ---   │
# │ str                  ┆ f64  ┆ f64    ┆ f64  ┆ f64  ┆ f64   │
# ╞══════════════════════╪══════╪════════╪══════╪══════╪═══════╡
# │ Highly Selective     ┆ 88.5 ┆ 92.3   ┆ 13.6 ┆ 19.3 ┆ 97.6  │
# │ Less Selective/Open  ┆ 52.5 ┆ 53.7   ┆ 18.5 ┆ 3.8  ┆ 100.0 │
# │ Moderately Selective ┆ 57.7 ┆ 58.8   ┆ 17.3 ┆ 7.1  ┆ 100.0 │
# │ Selective            ┆ 62.7 ┆ 63.6   ┆ 22.4 ┆ 7.2  ┆ 100.0 │
# └──────────────────────┴──────┴────────┴──────┴──────┴───────┘
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/09_viz-boxplot-selectivity.py", line 236, in <module>
#     plot.save(OUTPUT_PATH, width=10, height=7, dpi=300, verbose=False)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 681, in save
#     sv = self.save_helper(
#          ^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 629, in save_helper
#     figure = self.draw(show=False)
#              ^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/plotnine/ggplot.py", line 310, in draw
#     self.guides._setup(self)
#   File "/usr/local/lib/python3.12/site-packages/plotnine/guides/guides.py", line 174, in _setup
#     raise PlotnineError(f"Unknown guide: {g}")
# plotnine.exceptions.PlotnineError: 'Unknown guide: False'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
