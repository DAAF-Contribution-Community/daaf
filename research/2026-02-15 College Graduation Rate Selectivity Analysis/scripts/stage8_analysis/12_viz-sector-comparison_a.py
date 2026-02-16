#!/usr/bin/env python3
"""
Stage 8.2 (Step 9.5): Visualize sector comparison — grouped bar chart of
median graduation rate by selectivity band and sector.

Task: viz-sector-comparison
Wave: 9, Step: 9.5, Stage: 8
Depends on: sector-comparison (Step 9.4)
Input: output/analysis/2026-02-15_sector_comparison.parquet
Output: output/figures/2026-02-15_sector_comparison.png
Checkpoint: CP4

Revision _a: Fix sector_label case mismatch — data has "Private nonprofit"
(lowercase n), original script mapped "Private Nonprofit" (uppercase N),
causing plotnine to fall back to default gray fill for that sector.
"""

import polars as pl
from pathlib import Path
from plotnine import (
    ggplot, aes, geom_col, geom_text, labs, scale_fill_manual,
    scale_x_discrete, scale_y_continuous, position_dodge,
    theme_minimal, theme, element_text, element_blank,
)

# --- Config ---
# Configuration constants for the sector comparison visualization. The input
# is the pre-computed sector comparison parquet (8 rows: 4 selectivity bands
# x 2 sectors) produced by the sector-comparison analysis script. The output
# is a grouped bar chart saved as PNG at 300 DPI for publication quality.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_sector_comparison.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_sector_comparison.png"

# REASONING: Selectivity bands are ordered from most to least selective. This
# ordering matches the natural reading direction (best-to-worst) and aligns
# with how the research question frames selectivity as a gradient. The labels
# are derived from the analysis dataset's selectivity_band column.
BAND_ORDER = [
    "Highly Selective",
    "Selective",
    "Moderately Selective",
    "Less Selective/Open",
]

# REASONING: Using a colorblind-safe two-color palette. Blue (#4477AA) and
# coral/rose (#CC6677) are distinguishable under the three most common forms
# of color vision deficiency (deuteranopia, protanopia, tritanopia). These are
# drawn from the Tol qualitative palette, which is designed for accessibility.
#
# FIX (_a): Keys now match actual data values exactly — "Private nonprofit"
# (lowercase 'n') not "Private Nonprofit" (uppercase 'N'). The mismatch in v1
# caused plotnine to ignore the manual color and fall back to default gray.
SECTOR_COLORS = {
    "Public": "#4477AA",
    "Private nonprofit": "#CC6677",
}

# --- Load ---
# Load sector comparison results and verify schema before proceeding.
print("=" * 60)
print("Stage 8.2 (Step 9.5): Sector Comparison Visualization")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state of input data. This is a visualization task, so
# "pre-state" is the summary data that feeds the chart. We verify the expected
# shape (4 bands x 2 sectors = 8 rows) and the presence of required columns.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# ASSUMES:
#   - DataFrame has exactly 8 rows (4 selectivity bands x 2 sectors)
#   - Columns include: selectivity_band, sector_label, median_grad_rate
#   - median_grad_rate is a numeric percentage (0-100 scale)
#   - selectivity_band values match BAND_ORDER exactly
#   - sector_label values are "Public" and "Private nonprofit"
actual_sectors = sorted(df["sector_label"].unique().to_list())
print(f"Selectivity bands: {df['selectivity_band'].unique().to_list()}")
print(f"Sector labels: {actual_sectors}")
print(f"Median grad rate range: {df['median_grad_rate'].min():.1f} - {df['median_grad_rate'].max():.1f}")

# Verify sector labels match our color map keys exactly
for sector in actual_sectors:
    assert sector in SECTOR_COLORS, f"STOP: sector_label '{sector}' not in SECTOR_COLORS keys {list(SECTOR_COLORS.keys())}"
print("Sector labels match color map keys: OK")

# --- Transform ---
# INTENT: Convert Polars DataFrame to pandas for plotnine compatibility, and
# set the selectivity_band column as an ordered categorical so the x-axis
# displays bands in the correct order (most to least selective).
#
# REASONING: plotnine requires pandas DataFrames. The categorical ordering
# ensures x-axis labels appear in the logical order defined in BAND_ORDER
# rather than alphabetical order (which would be misleading).
df_pd = df.to_pandas()

import pandas as pd
df_pd["selectivity_band"] = pd.Categorical(
    df_pd["selectivity_band"],
    categories=BAND_ORDER,
    ordered=True,
)

print(f"\nConverted to pandas: {df_pd.shape[0]} rows x {df_pd.shape[1]} cols")
print(f"Band dtype: {df_pd['selectivity_band'].dtype}")

# --- Plot ---
# INTENT: Create a grouped (dodged) bar chart showing median graduation rate
# by selectivity band and sector (Public vs. Private Nonprofit). This directly
# visualizes Observable Truth #5: "Stakeholders can compare graduation rates
# between public and private institutions within selectivity tiers."
#
# REASONING: Grouped bar chart (not stacked) because:
#   - We want to compare Public vs. Private within each band visually
#   - Stacked bars would obscure the comparison — the height difference is
#     what matters, not cumulative totals
#   - Position dodge places bars side-by-side for direct comparison
#   - geom_col (not geom_bar) because we have pre-computed median values
#
# ASSUMES:
#   - median_grad_rate is on a 0-100 percentage scale
#   - Each selectivity band has exactly 2 rows (one Public, one Private)
#   - SECTOR_COLORS maps correctly to the sector_label values in the data
dodge_width = 0.8

plot = (
    ggplot(df_pd, aes(x="selectivity_band", y="median_grad_rate", fill="sector_label"))
    + geom_col(
        stat="identity",
        position=position_dodge(width=dodge_width),
        width=0.7,
        alpha=0.9,
    )
    # INTENT: Add value labels on each bar so readers can see exact percentages
    # without having to estimate from the y-axis gridlines.
    # REASONING: In a comparison chart, precise values matter — the key finding
    # is a 12pp reversal in the Selective band, which requires exact numbers.
    + geom_text(
        aes(label="median_grad_rate"),
        position=position_dodge(width=dodge_width),
        format_string="{:.0f}%",
        va="bottom",
        size=8,
    )
    + scale_fill_manual(
        values=SECTOR_COLORS,
        name="Sector",
    )
    + scale_x_discrete(limits=BAND_ORDER)  # Enforce ordering
    + scale_y_continuous(
        limits=(0, 105),  # Ceiling above 100 so labels don't clip
        breaks=[0, 20, 40, 60, 80, 100],
        labels=lambda xs: [f"{x:.0f}%" for x in xs],
    )
    + labs(
        title="Median Graduation Rate by Selectivity Band and Sector",
        subtitle="Public vs. Private Nonprofit 4-Year Institutions, 2020",
        x="Selectivity Band",
        y="Median Graduation Rate (%)",
        caption="Source: IPEDS 2020.",
    )
    + theme_minimal()
    + theme(
        figure_size=(10, 6),
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=11, color="#555555"),
        plot_caption=element_text(size=9, color="#777777", ha="right"),
        axis_text_x=element_text(size=10, angle=15, ha="right"),
        axis_text_y=element_text(size=10),
        axis_title_x=element_text(size=11),
        axis_title_y=element_text(size=11),
        legend_position="top",
        legend_title=element_text(size=10, weight="bold"),
        legend_text=element_text(size=10),
        panel_grid_major_x=element_blank(),  # Remove vertical grid for bar charts
        panel_grid_minor=element_blank(),
    )
)

# --- Save ---
# Persist figure as PNG at 300 DPI for publication quality.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

plot.save(OUTPUT_PATH, dpi=300, width=10, height=6, verbose=False)
print(f"\nSaved figure: {OUTPUT_PATH}")

# --- Post-state ---
# Verify the output file exists and has a reasonable size. For a 10x6 inch
# figure at 300 DPI, we expect at least 50KB (a blank canvas would be ~20KB,
# so anything above 50KB indicates content was rendered).
import os

file_exists = OUTPUT_PATH.exists()
file_size = os.path.getsize(OUTPUT_PATH) if file_exists else 0
print(f"\nPost-state:")
print(f"  File exists: {file_exists}")
print(f"  File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

# --- CP4 Validation ---
# Checkpoint validation for visualization output. Verify figure file exists,
# is large enough to contain rendered content, and data coverage is complete.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

# CP4.1: Figure file exists
print(f"  [{'PASS' if file_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH}")

# CP4.2: Figure has reasonable file size (>50KB indicates rendered content)
size_ok = file_size > 50_000
print(f"  [{'PASS' if size_ok else 'FAIL'}] File size > 50KB: {file_size / 1024:.1f} KB")

# CP4.3: Input data had both sectors (2 bars per band)
# REASONING: If one sector is missing, the grouped bar chart would only show
# one bar per band, which misrepresents the comparison.
sector_count = df["sector_label"].n_unique()
sectors_ok = sector_count == 2
print(f"  [{'PASS' if sectors_ok else 'FAIL'}] Both sectors present: {sector_count} sectors")

# CP4.4: All 4 selectivity bands present
band_count = df["selectivity_band"].n_unique()
bands_ok = band_count == 4
print(f"  [{'PASS' if bands_ok else 'FAIL'}] All 4 selectivity bands present: {band_count} bands")

# CP4.5: Total bar count = 8 (4 bands x 2 sectors)
total_bars = len(df)
bars_ok = total_bars == 8
print(f"  [{'PASS' if bars_ok else 'FAIL'}] Expected 8 bars (4 bands x 2 sectors): {total_bars}")

assert file_exists, "STOP: Figure file not created"
assert size_ok, f"STOP: Figure file too small ({file_size} bytes)"
assert sectors_ok, f"STOP: Expected 2 sectors, found {sector_count}"
assert bands_ok, f"STOP: Expected 4 selectivity bands, found {band_count}"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:13:50
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/12_viz-sector-comparison_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.2 (Step 9.5): Sector Comparison Visualization
# ============================================================
# Loaded: 8 rows x 12 cols
# Columns: ['selectivity_band', 'inst_control', 'n', 'n_with_grad_rate', 'median_grad_rate', 'mean_grad_rate', 'std_grad_rate', 'median_pell_share', 'median_urm_share', 'median_student_faculty_ratio', 'median_retention_rate', 'sector_label']
# 
# Pre-state: 8 rows, 12 cols
# Selectivity bands: ['Highly Selective', 'Selective', 'Moderately Selective', 'Less Selective/Open']
# Sector labels: ['Private nonprofit', 'Public']
# Median grad rate range: 50.5 - 92.6
# Sector labels match color map keys: OK
# 
# Converted to pandas: 8 rows x 12 cols
# Band dtype: category
# 
# Saved figure: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_sector_comparison.png
# 
# Post-state:
#   File exists: True
#   File size: 238,085 bytes (232.5 KB)
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] Figure file exists: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_sector_comparison.png
#   [PASS] File size > 50KB: 232.5 KB
#   [PASS] Both sectors present: 2 sectors
#   [PASS] All 4 selectivity bands present: 4 bands
#   [PASS] Expected 8 bars (4 bands x 2 sectors): 8
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
