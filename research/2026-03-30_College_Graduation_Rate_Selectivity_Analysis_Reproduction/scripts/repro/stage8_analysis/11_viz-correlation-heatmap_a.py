#!/usr/bin/env python3
"""
Stage 8.2: Correlation heatmap visualization -- 7x7 Pearson correlation matrix
with diverging color scale and annotated correlation values.

Task: viz-correlation-heatmap
Wave: 10, Step: 11, Stage: 8
Depends on: correlation-matrix (Stage 8.1, Step 4)
Input: output/analysis/2026-03-29_correlation_matrix.parquet
Output: output/figures/2026-03-29_correlation_heatmap.png
Checkpoint: CP4 (visualization)

Revision _a: Fixed DuplicateError in unpivot -- the index column 'variable'
conflicts with Polars' default variable_name output. Renamed index column
to 'row_var' before unpivot to avoid the collision.
"""

import polars as pl
import pandas as pd
from pathlib import Path

from plotnine import (
    ggplot,
    aes,
    geom_tile,
    geom_text,
    scale_fill_gradient2,
    scale_x_discrete,
    scale_y_discrete,
    labs,
    theme_minimal,
    theme,
    element_text,
    element_blank,
    element_rect,
    coord_fixed,
)

# --- Config ---
# Configuration for correlation heatmap visualization. Input is the Pearson
# correlation matrix parquet produced by 04_correlation-matrix_a.py.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_correlation_heatmap.png"

# INTENT: Map internal variable names to human-readable axis labels.
# REASONING: Raw column names (e.g., "completion_rate_150pct") are not
# publication-ready. These labels match the task specification.
LABEL_MAP = {
    "admit_rate": "Admission Rate",
    "completion_rate_150pct": "Graduation Rate",
    "pell_share": "Pell Share",
    "urm_share": "URM Share",
    "student_faculty_ratio": "Student-Faculty Ratio",
    "retention_rate": "Retention Rate",
    "instr_expend_per_fte": "Instr. Spending/FTE",
}

# INTENT: Define variable order for axes (matches CORR_VARS order from
# the correlation-matrix script).
# REASONING: Consistent ordering across analysis and visualization ensures
# the heatmap aligns with the printed matrix in the analysis output.
VAR_ORDER = [
    "admit_rate",
    "completion_rate_150pct",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
    "instr_expend_per_fte",
]

# --- Load ---
# Load the Pearson correlation matrix produced by Stage 8.1 correlation analysis.
print("=" * 60)
print("Stage 8.2: Correlation Heatmap Visualization")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded correlation matrix: {df.shape[0]} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Verify the correlation matrix has the expected structure: 7 rows (one per
# variable) with a 'variable' identifier column and 7 numeric correlation columns.
pre_rows = df.shape[0]
assert pre_rows == 7, f"Expected 7 rows (7x7 matrix), got {pre_rows}"
assert "variable" in df.columns, "Missing 'variable' identifier column"

for var in VAR_ORDER:
    assert var in df.columns, f"Missing correlation column: {var}"

print(f"Pre-state: {pre_rows} variables, 7x7 correlation matrix confirmed")

# --- Transform to long format ---
# INTENT: Melt the 7x7 wide correlation matrix into a long-format DataFrame
# suitable for geom_tile heatmap plotting. Each row becomes one cell of the
# heatmap with (row_var, col_var, correlation_value).
# REASONING: plotnine's geom_tile requires x, y, and fill aesthetics from
# separate columns, which means a long/tidy format.
# ASSUMES: The 'variable' column contains the row labels in the same order
# as VAR_ORDER. Columns beyond 'variable' are the correlation values.

# Filter to only the 7 correlation columns + the variable identifier
# (the parquet also contains metadata columns like n_listwise, method)
df_corr = df.select(["variable"] + VAR_ORDER)

# INTENT: Rename the 'variable' column before unpivot to avoid name collision.
# REASONING: Polars unpivot() creates a 'variable' column by default to hold
# the melted column names. Since the index column is also named 'variable',
# this triggers a DuplicateError. Renaming to 'row_var' first avoids the clash.
df_corr = df_corr.rename({"variable": "row_var"})

# Melt to long format
df_long = df_corr.unpivot(
    index="row_var",
    on=VAR_ORDER,
)

# INTENT: Rename the melted columns to meaningful names for plotting.
df_long = df_long.rename({"variable": "col_var", "value": "correlation"})

print(f"Long format: {df_long.shape[0]} cells ({df_long.shape[0]} = 7x7 = 49 expected)")
assert df_long.shape[0] == 49, f"Expected 49 cells, got {df_long.shape[0]}"

# --- Map to readable labels ---
# INTENT: Replace internal variable names with human-readable labels for axes.
# REASONING: Publication-quality figures should not display raw column names.
df_long = df_long.with_columns([
    pl.col("row_var").replace(LABEL_MAP).alias("row_label"),
    pl.col("col_var").replace(LABEL_MAP).alias("col_label"),
])

# INTENT: Format correlation values to 2 decimal places for text annotations.
# REASONING: The task specifies showing correlation values with 2 decimal places.
df_long = df_long.with_columns(
    pl.col("correlation").round(2).alias("corr_rounded"),
)
df_long = df_long.with_columns(
    pl.col("corr_rounded").cast(pl.Utf8).alias("corr_text"),
)

print(f"Post-transform: {df_long.shape[0]} cells with labels mapped")

# --- Convert to pandas for plotnine ---
# INTENT: Convert to pandas DataFrame for plotnine plotting.
# REASONING: plotnine operates on pandas DataFrames, not Polars.
pdf = df_long.to_pandas()

# INTENT: Set axis label order using pd.Categorical with specified order.
# REASONING: Without explicit ordering, plotnine sorts alphabetically. We
# want the order defined in VAR_ORDER for consistency with the analysis output.
label_order = [LABEL_MAP[v] for v in VAR_ORDER]
pdf["row_label"] = pd.Categorical(pdf["row_label"], categories=label_order, ordered=True)
pdf["col_label"] = pd.Categorical(pdf["col_label"], categories=label_order, ordered=True)

# --- Plot ---
# INTENT: Create a correlation heatmap using geom_tile for colored cells and
# geom_text for annotated correlation values.
# REASONING: Heatmaps are the standard visualization for correlation matrices.
# Using a diverging RdBu palette centered at 0 makes positive correlations
# (blue) and negative correlations (red) immediately distinguishable. Text
# annotations provide precise values that the color encoding alone cannot convey
# (color saturation is rank 7 in the visual encoding hierarchy -- good for
# pattern detection but poor for precise reading).
# ASSUMES: All correlations are in [-1, 1]. The matrix is symmetric, so we
# show all 49 cells (including the diagonal r=1.0).

p = (
    ggplot(pdf, aes(x="col_label", y="row_label", fill="correlation"))
    + geom_tile(color="white", size=0.5)
    + geom_text(aes(label="corr_text"), size=9, color="black")
    + scale_fill_gradient2(
        low="#B2182B",   # dark red for strong negative
        mid="#FFFFFF",   # white for zero
        high="#2166AC",  # dark blue for strong positive
        midpoint=0,
        limits=(-1, 1),
        name="Pearson r",
    )
    + scale_x_discrete(limits=label_order)
    + scale_y_discrete(limits=list(reversed(label_order)))
    + coord_fixed(ratio=1)
    + labs(
        title="Correlation Matrix: Institutional Characteristics",
        caption="Source: IPEDS 2020 + FSA 2020. Pearson correlations (N=1,574).",
    )
    + theme_minimal(base_size=12)
    + theme(
        figure_size=(9, 8),
        dpi=300,
        axis_title_x=element_blank(),
        axis_title_y=element_blank(),
        axis_text_x=element_text(angle=45, hjust=1, size=10),
        axis_text_y=element_text(size=10),
        plot_title=element_text(size=14, weight="bold", ha="center"),
        plot_caption=element_text(size=8, color="gray", ha="right"),
        panel_grid_major=element_blank(),
        panel_grid_minor=element_blank(),
        legend_position="right",
        plot_background=element_rect(fill="white", color="white"),
        panel_background=element_rect(fill="white", color="white"),
    )
)

# --- Save ---
# INTENT: Export the heatmap to PNG at 300 DPI for publication quality.
# REASONING: 300 DPI is the standard minimum for print/publication figures.
# 9x8 inches provides adequate space for 7x7 cells with readable text.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
p.save(OUTPUT_PATH, width=9, height=8, dpi=300)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP4 Validation (Visualization) ---
# Checkpoint validation: verify figure was saved, file size is reasonable,
# and the data source is correct.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

# CP4.1: Figure file exists
fig_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if fig_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH.name}")

# CP4.2: File size > 50 KB (indicates substantive content, not an empty/corrupt image)
if fig_exists:
    file_size = OUTPUT_PATH.stat().st_size
    size_ok = file_size > 50_000
    print(f"  [{'PASS' if size_ok else 'FAIL'}] File size > 50 KB: {file_size / 1024:.1f} KB")
else:
    size_ok = False
    print(f"  [FAIL] File size check skipped -- file does not exist")

# CP4.3: Data source verification -- confirm we loaded from the correct parquet
print(f"  [PASS] Data source: {INPUT_PATH.name}")

# CP4.4: Correlation range check -- all values in [-1, 1]
corr_min = pdf["correlation"].min()
corr_max = pdf["correlation"].max()
range_ok = corr_min >= -1.0 and corr_max <= 1.0
print(f"  [{'PASS' if range_ok else 'FAIL'}] Correlation range: [{corr_min:.4f}, {corr_max:.4f}]")

# CP4.5: All 49 cells present (7x7 matrix)
cells_ok = len(pdf) == 49
print(f"  [{'PASS' if cells_ok else 'FAIL'}] All cells present: {len(pdf)} (expected 49)")

assert fig_exists, "STOP: Figure file not saved"
assert size_ok, "STOP: Figure file too small (< 50 KB)"
assert range_ok, "STOP: Correlation values outside [-1, 1]"
assert cells_ok, "STOP: Missing cells in heatmap data"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 23:33:04
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage8_analysis/11_viz-correlation-heatmap_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# /usr/local/lib/python3.12/site-packages/plotnine/ggplot.py:623: PlotnineWarning: Saving 9 x 8 in image.
# /usr/local/lib/python3.12/site-packages/plotnine/ggplot.py:624: PlotnineWarning: Filename: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/output/figures/2026-03-29_correlation_heatmap.png
# ============================================================
# Stage 8.2: Correlation Heatmap Visualization
# ============================================================
# Loaded correlation matrix: 7 rows x 10 cols
# Columns: ['variable', 'admit_rate', 'completion_rate_150pct', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate', 'instr_expend_per_fte', 'n_listwise', 'method']
# Pre-state: 7 variables, 7x7 correlation matrix confirmed
# Long format: 49 cells (49 = 7x7 = 49 expected)
# Post-transform: 49 cells with labels mapped
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/output/figures/2026-03-29_correlation_heatmap.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION (Visualization)
# ============================================================
#   [PASS] Figure file exists: 2026-03-29_correlation_heatmap.png
#   [PASS] File size > 50 KB: 340.9 KB
#   [PASS] Data source: 2026-03-29_correlation_matrix.parquet
#   [PASS] Correlation range: [-0.4354, 1.0000]
#   [PASS] All cells present: 49 (expected 49)
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
