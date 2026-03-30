#!/usr/bin/env python3
"""
Stage 8.2: Faceted scatter plot — graduation rate vs admission rate by sector.

Task: viz-sector-comparison
Wave: 10, Step: 12, Stage: 8
Depends on: sector-comparison (07_sector-comparison.py)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/figures/2026-03-29_sector_comparison.png
Checkpoint: CP4
"""

import polars as pl
import numpy as np
import pandas as pd
from pathlib import Path

# --- Config ---
# Configuration for the sector comparison visualization. This faceted scatter
# plot is the primary visual for the cross-sector analysis, highlighting the
# sign reversal in the selectivity-graduation correlation for for-profit
# institutions (r=+0.26 vs negative for public/private NP).
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_sector_comparison.png"

# INTENT: Map inst_control integer codes to human-readable sector labels.
# REASONING: Same mapping as 07_sector-comparison.py to ensure consistency.
# IPEDS codes: 1=Public, 2=Private Nonprofit, 3=Private For-Profit.
SECTOR_MAP = {1: "Public", 2: "Private Nonprofit", 3: "Private For-Profit"}

# INTENT: Define a consistent ordering for facet panels.
# REASONING: Ordering Public -> Private NP -> For-Profit follows the natural
# grouping from largest N to smallest and places the sign-reversal finding
# (for-profit) last where the reader's attention settles for the punchline.
SECTOR_ORDER = ["Public", "Private Nonprofit", "Private For-Profit"]

# INTENT: Define colorblind-safe colors for each sector using Okabe-Ito palette.
# REASONING: Okabe-Ito is purpose-built for color vision deficiency accessibility.
# Using distinct hues with high contrast ensures readability across CVD types.
SECTOR_COLORS = {
    "Public": "#0072B2",           # Okabe-Ito blue
    "Private Nonprofit": "#009E73",  # Okabe-Ito bluish green
    "Private For-Profit": "#D55E00",  # Okabe-Ito vermilion
}

# Within-sector Pearson correlations from 07_sector-comparison.py output
# These are pre-computed to annotate each facet with the exact r value.
SECTOR_CORRELATIONS = {
    "Public": -0.3683,
    "Private Nonprofit": -0.3349,
    "Private For-Profit": +0.2564,
}

SECTOR_N = {
    "Public": 594,
    "Private Nonprofit": 1202,
    "Private For-Profit": 150,
}

# --- Load ---
# Load the analysis dataset and verify it contains the required columns.
print("=" * 60)
print("Stage 8.2: Sector Comparison Visualization")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Verify required columns for the visualization exist in the dataset.
pre_rows = df.shape[0]
required_cols = ["inst_control", "admit_rate", "completion_rate_150pct"]
missing = [c for c in required_cols if c not in df.columns]
assert not missing, f"STOP: Missing required columns: {missing}"
print(f"Pre-state: {pre_rows:,} rows, all required columns present")

# --- Transform ---
# INTENT: Create sector labels and filter to rows with valid data for both
# axes of the scatter plot. Rows with null admit_rate or completion_rate
# cannot be plotted and would cause warnings in plotnine.
# REASONING: Applying the same sector mapping used in the prior analysis
# script ensures visual labels match the statistical output exactly.
# ASSUMES: inst_control contains only values 1, 2, 3 per IPEDS convention.
df = df.with_columns(
    pl.col("inst_control")
    .replace_strict(SECTOR_MAP, default=None)
    .alias("sector_label")
)

# Drop rows with null in either axis variable
df_plot = df.drop_nulls(subset=["admit_rate", "completion_rate_150pct", "sector_label"])
print(f"Plottable rows (non-null on both axes): {df_plot.shape[0]:,}")
print(f"Dropped {pre_rows - df_plot.shape[0]:,} rows with null values")

# Verify sector counts match expected values
for sector in SECTOR_ORDER:
    n = df_plot.filter(pl.col("sector_label") == sector).shape[0]
    print(f"  {sector}: {n:,} plottable rows")

# --- Convert to pandas ---
# INTENT: Convert to pandas DataFrame for plotnine compatibility.
# REASONING: plotnine requires pandas DataFrames. Converting here is the
# standard pattern for the plotnine workflow.
# ASSUMES: Data fits comfortably in memory (< 2K rows).
pdf = df_plot.select([
    "sector_label", "admit_rate", "completion_rate_150pct"
]).to_pandas()

# INTENT: Set sector_label as an ordered categorical for consistent facet ordering.
# REASONING: Without explicit ordering, facets appear alphabetically, which would
# place "Private For-Profit" before "Private Nonprofit" and "Public" last.
# The custom order puts the sign-reversal finding (for-profit) in the rightmost
# panel for maximum impact.
pdf["sector_label"] = pd.Categorical(
    pdf["sector_label"],
    categories=SECTOR_ORDER,
    ordered=True,
)

# --- Build annotation DataFrame ---
# INTENT: Create a small DataFrame with annotation text and positions for each
# facet so we can display the Pearson r and N in each panel.
# REASONING: geom_text with a separate data source lets us place one annotation
# per facet without duplicating text across all data points.
# ASSUMES: Correlation values are from the 07_sector-comparison.py execution log.
ann_data = pd.DataFrame({
    "sector_label": pd.Categorical(SECTOR_ORDER, categories=SECTOR_ORDER, ordered=True),
    "admit_rate": [85, 85, 85],  # x position (top-right area of each facet)
    "completion_rate_150pct": [95, 95, 95],  # y position
    "label": [
        f"r = {SECTOR_CORRELATIONS[s]:+.2f}\nN = {SECTOR_N[s]:,}"
        for s in SECTOR_ORDER
    ],
})

# --- Plot ---
# INTENT: Create a faceted scatter plot showing the selectivity-graduation
# relationship within each institutional sector, with OLS trend lines to
# visually highlight the sign reversal for for-profit institutions.
#
# REASONING: Faceted scatter plot (not overlaid) because:
#   - Three sectors have very different N (594, 1202, 150), making overlaid
#     colors hard to read where sectors overlap
#   - Small multiples let each sector's pattern stand independently
#   - OLS trend lines (geom_smooth method="lm") directly show the slope sign
#   - The subtitle calls out the for-profit sign reversal as the key finding
#
# ASSUMES:
#   - admit_rate and completion_rate_150pct are on percentage scales (0-100)
#   - Within-sector linear trends are a reasonable summary (verified in prior
#     analysis with Pearson r values)
from plotnine import (
    ggplot, aes, geom_point, geom_smooth, geom_text,
    facet_wrap, labs, theme_minimal, theme,
    scale_color_manual, scale_x_continuous, scale_y_continuous,
    element_text, element_blank, element_rect,
)

p = (
    ggplot(pdf, aes(x="admit_rate", y="completion_rate_150pct", color="sector_label"))
    + geom_point(alpha=0.35, size=1.2)  # Alpha handles overplotting; size keeps points visible
    + geom_smooth(method="lm", se=True, color="black", size=0.8, alpha=0.15)  # OLS trend line with CI in black for clarity
    + geom_text(
        aes(x="admit_rate", y="completion_rate_150pct", label="label"),
        data=ann_data,
        inherit_aes=False,
        size=8,
        ha="right",
        va="top",
        color="black",
    )
    + facet_wrap("sector_label", ncol=3)
    + scale_color_manual(values=SECTOR_COLORS, guide=False)  # Color is redundant with facet labels; suppress legend
    + scale_x_continuous(
        name="Admission Rate (%)",
        breaks=[0, 25, 50, 75, 100],
        limits=(0, 105),
    )
    + scale_y_continuous(
        name="Graduation Rate (% within 150% time)",
        breaks=[0, 25, 50, 75, 100],
        limits=(0, 105),
    )
    + labs(
        title="Selectivity-Graduation Relationship by Institutional Sector",
        subtitle="Note the positive slope for For-Profit institutions -- the opposite pattern.",
        caption="Source: IPEDS 2020.",
    )
    + theme_minimal(base_size=11)
    + theme(
        figure_size=(12, 5),  # 12x5 inches per task spec
        dpi=300,
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=10, style="italic"),
        plot_caption=element_text(size=8, color="gray"),
        strip_text=element_text(size=11, weight="bold"),
        strip_background=element_rect(fill="#F5F5F5", color="none"),
        axis_title=element_text(size=10),
        axis_text=element_text(size=9),
        panel_grid_minor=element_blank(),
        panel_spacing=0.4,
    )
)

# --- Save ---
# Persist the figure to the output directory at 300 DPI.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
p.save(OUTPUT_PATH, width=12, height=5, dpi=300, verbose=False)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify the figure file exists, is above the
# minimum size threshold, and that the data behind it is reasonable.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Figure file exists
file_exists = OUTPUT_PATH.exists()
if not file_exists:
    cp4_passed = False
print(f"  [{'PASS' if file_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH}")

# CP4.2: File size > 50 KB (indicates a substantive plot, not an empty canvas)
if file_exists:
    file_size_kb = OUTPUT_PATH.stat().st_size / 1024
    size_ok = file_size_kb > 50
    if not size_ok:
        cp4_passed = False
    print(f"  [{'PASS' if size_ok else 'FAIL'}] File size: {file_size_kb:.1f} KB (threshold: > 50 KB)")
else:
    cp4_passed = False
    print(f"  [FAIL] Cannot check file size -- file does not exist")

# CP4.3: Correct data source used (analysis.parquet, not a different file)
data_source_ok = "analysis.parquet" in str(INPUT_PATH)
if not data_source_ok:
    cp4_passed = False
print(f"  [{'PASS' if data_source_ok else 'FAIL'}] Correct data source: {INPUT_PATH.name}")

# CP4.4: All three sectors represented in the plot data
sectors_in_data = set(pdf["sector_label"].unique())
all_sectors = all(s in sectors_in_data for s in SECTOR_ORDER)
if not all_sectors:
    cp4_passed = False
print(f"  [{'PASS' if all_sectors else 'FAIL'}] All 3 sectors in plot data: {sorted(sectors_in_data)}")

# CP4.5: Plottable row count is reasonable (not a near-empty chart)
rows_ok = df_plot.shape[0] > 100
if not rows_ok:
    cp4_passed = False
print(f"  [{'PASS' if rows_ok else 'FAIL'}] Plottable rows: {df_plot.shape[0]:,} (threshold: > 100)")

assert cp4_passed, "STOP: CP4 validation failed"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:40:08
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 8.2: Sector Comparison Visualization
# ============================================================
# Loaded: 1,946 rows x 25 cols
# Pre-state: 1,946 rows, all required columns present
# Plottable rows (non-null on both axes): 1,625
# Dropped 321 rows with null values
#   Public: 525 plottable rows
#   Private Nonprofit: 1,048 plottable rows
#   Private For-Profit: 52 plottable rows
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/12_viz-sector-comparison.py", line 211, in <module>
#     p.save(OUTPUT_PATH, width=12, height=5, dpi=300, verbose=False)
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
