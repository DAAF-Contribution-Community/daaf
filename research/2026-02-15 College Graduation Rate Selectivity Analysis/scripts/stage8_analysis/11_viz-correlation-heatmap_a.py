#!/usr/bin/env python3
"""
Stage 8.4 (Step 9.4): Correlation heatmap of key institutional variables.
REVISION _a: Fixed data reshaping — input is wide-format (each variable is a column),
not long-format. Now melts the wide matrix to long-format for geom_tile.

Task: viz-correlation-heatmap
Wave: 9, Step: 9.4, Stage: 8
Depends on: correlation-matrix (Step 9.3)
Input: output/analysis/2026-02-15_correlation_matrix.parquet
Output: output/figures/2026-02-15_correlation_heatmap.png
Checkpoint: CP4 (figure existence + data integrity)
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
    labs,
    theme_minimal,
    theme,
    element_text,
    element_blank,
    coord_fixed,
)

# --- Config ---
# Configuration constants for the correlation heatmap visualization.
# The correlation matrix was computed in Step 9.3 (correlation-matrix) using
# both Pearson and Spearman methods. The parquet is in WIDE format:
# columns = [method, variable, grad_rate_150pct, admission_rate, pell_share,
#            urm_share, student_faculty_ratio, retention_rate]
# Each row is one variable's correlations with all others, with 6 rows per method.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_correlation_heatmap.png"

# REASONING: These are the 6 key variables from the analysis dataset that capture
# the core dimensions of the research question: graduation outcomes (grad_rate_150pct),
# selectivity proxies (admission_rate), student body demographics (pell_share, urm_share),
# institutional resources (student_faculty_ratio), and student engagement (retention_rate).
VARIABLES = [
    "grad_rate_150pct",
    "admission_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
]

# REASONING: Human-readable labels for the heatmap axes. Short enough to fit
# without overlap, descriptive enough to communicate meaning without a legend.
VARIABLE_LABELS = {
    "grad_rate_150pct": "Graduation Rate",
    "admission_rate": "Admission Rate",
    "pell_share": "Pell Share",
    "urm_share": "URM Share",
    "student_faculty_ratio": "Student-Faculty Ratio",
    "retention_rate": "Retention Rate",
}

# --- Load ---
# Load the correlation matrix from the analysis output. This parquet file
# contains 12 rows: 6 variable rows x 2 methods (pearson, spearman).
# Structure: wide format where each numeric column IS a variable's correlation values.
print("=" * 60)
print("Stage 8.4 (Step 9.4): Correlation Heatmap Visualization")
print("=" * 60)

df_corr = pl.read_parquet(INPUT_PATH)
print(f"Loaded correlation matrix: {df_corr.shape[0]:,} rows x {df_corr.shape[1]} cols")
print(f"Columns: {df_corr.columns}")

# --- Pre-state ---
# Verify the correlation matrix has the expected wide-format structure.
# ASSUMES:
#   - Column "method" identifies pearson vs spearman
#   - Column "variable" identifies which row-variable this is
#   - Remaining 6 columns are the correlation values with each variable
print(f"\nPre-state: {df_corr.shape[0]} rows")
print(f"Methods present: {df_corr['method'].unique().to_list()}")
print(f"Variables present: {df_corr['variable'].unique().to_list()}")

# --- Transform ---
# INTENT: Filter to Pearson correlations and melt the wide-format matrix into
# long format suitable for geom_tile(). The wide format has each variable as
# a column; we need (var1, var2, corr) triples.
#
# REASONING: The correlation matrix parquet stores data in a matrix-like wide
# format where the "variable" column identifies the row variable and the remaining
# numeric columns hold correlation values with each column variable. We need to
# melt (unpivot) this into long format for plotnine's geom_tile, which requires
# explicit x, y, and fill columns.

# Filter to Pearson only
# REASONING: Pearson is the standard choice for showing linear relationships
# in a correlation heatmap. Spearman is available for robustness checking
# but would be a separate visualization if needed.
df_pearson = df_corr.filter(pl.col("method") == "pearson")
print(f"\nFiltered to Pearson correlations: {df_pearson.shape[0]} rows")

# Melt from wide to long format
# INTENT: Convert from wide format (1 row per variable, 6 numeric columns)
# to long format (1 row per variable PAIR, with var1, var2, corr columns).
# This produces 6 * 6 = 36 rows for the full symmetric matrix.
#
# ASSUMES: The "variable" column contains the row-variable name, and each of
# the 6 numeric columns contains the correlation of that row-variable with the
# column-variable.
df_long = df_pearson.select(["variable"] + VARIABLES).unpivot(
    on=VARIABLES,
    index="variable",
    variable_name="var2",
    value_name="corr",
).rename({"variable": "var1"})

print(f"\nMelted to long format: {df_long.shape[0]} rows (expected 36)")
print(f"Sample:\n{df_long.head(6)}")

# Verify the full matrix is present
n_cells = df_long.shape[0]
expected_cells = len(VARIABLES) ** 2
print(f"\nMatrix cells: {n_cells} (expected {expected_cells})")

# --- Apply human-readable labels ---
# INTENT: Replace variable names with readable labels for the plot axes.
# REASONING: Raw variable names (e.g., "grad_rate_150pct") are not reader-friendly.
# Shorter, descriptive labels improve plot readability and accessibility.
df_long = df_long.with_columns([
    pl.col("var1").replace(VARIABLE_LABELS).alias("var1_label"),
    pl.col("var2").replace(VARIABLE_LABELS).alias("var2_label"),
])

# INTENT: Create formatted correlation text for cell annotations.
# REASONING: Annotating cells with exact values lets readers extract precise
# information beyond what color alone conveys. Two decimal places provide
# sufficient precision for correlation interpretation.
df_long = df_long.with_columns(
    pl.col("corr").round(2).cast(pl.Utf8).alias("corr_text")
)

# Convert to pandas for plotnine
# REASONING: plotnine requires pandas DataFrames. Polars -> pandas conversion
# is lightweight for 36 rows.
df_plot = df_long.to_pandas()

print(f"\nPlot dataframe shape: {df_plot.shape}")
print(f"Unique var1 labels: {sorted(df_plot['var1_label'].unique())}")
print(f"Unique var2 labels: {sorted(df_plot['var2_label'].unique())}")
print(f"Correlation range: [{df_plot['corr'].min():.3f}, {df_plot['corr'].max():.3f}]")

# --- Define variable order ---
# INTENT: Order variables logically for the heatmap so related variables are adjacent.
# REASONING: Grouping outcome (graduation) first, then selectivity (admission),
# then demographics (pell, urm), then resources (student-faculty), then engagement
# (retention) follows the conceptual flow of the research question: outcome ->
# selectivity -> demographics -> resources -> engagement.
var_order = [
    "Graduation Rate",
    "Admission Rate",
    "Pell Share",
    "URM Share",
    "Student-Faculty Ratio",
    "Retention Rate",
]

df_plot["var1_label"] = pd.Categorical(df_plot["var1_label"], categories=var_order, ordered=True)
df_plot["var2_label"] = pd.Categorical(df_plot["var2_label"], categories=var_order, ordered=True)

# --- Plot ---
# INTENT: Create a correlation heatmap showing pairwise Pearson correlations
# among 6 key institutional variables. This visualization supports the research
# question by revealing which variables are most strongly associated with
# graduation rates, and whether selectivity proxies and demographic factors
# share substantial covariance.
#
# REASONING: geom_tile + diverging color scale is the standard visualization
# for correlation matrices. The diverging palette (blue=positive, red=negative,
# white=zero) immediately communicates direction and strength of association.
# Cell annotations provide exact values for precise reading.
#
# ASSUMES:
#   - All correlation values fall in [-1, 1]
#   - The matrix is symmetric (guaranteed by the correlation function)
#   - 6x6 grid is small enough for all annotations to be legible

p = (
    ggplot(df_plot, aes(x="var1_label", y="var2_label", fill="corr"))
    + geom_tile(color="white", size=0.5)  # White borders between cells for visual separation
    + geom_text(
        aes(label="corr_text"),
        size=9,
        color="black",
    )
    + scale_fill_gradient2(
        low="#d73027",      # Strong red for negative correlations
        mid="white",        # White for zero correlation
        high="#4575b4",     # Strong blue for positive correlations
        midpoint=0,         # Center the diverging scale at zero
        limits=(-1, 1),     # Full correlation range
        name="Pearson r",
    )
    + coord_fixed()  # Square tiles (1:1 aspect ratio)
    + labs(
        title="Correlation Matrix of Key Institutional Variables",
        x="",
        y="",
        caption="Source: IPEDS 2020, FSA 2020. Pearson correlations. N=1,518 institutions with complete data.",
    )
    + theme_minimal()
    + theme(
        plot_title=element_text(size=14, weight="bold", ha="center"),
        axis_text_x=element_text(angle=45, ha="right", size=10),
        axis_text_y=element_text(size=10),
        legend_position="right",
        figure_size=(9, 8),
        plot_caption=element_text(size=8, ha="right", style="italic"),
        panel_grid_major=element_blank(),  # Remove grid lines (tiles ARE the grid)
        panel_grid_minor=element_blank(),
    )
)

# --- Save ---
# Persist the figure as PNG at 300 DPI for publication quality.
# Output path matches the Plan's visualization specification.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
p.save(OUTPUT_PATH, dpi=300, width=9, height=8, verbose=False)
print(f"\nSaved figure: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify figure was saved correctly, has reasonable
# file size, and the underlying data is consistent with expectations.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

# CP4.1: Figure file exists
fig_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if fig_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH}")

# CP4.2: Figure file size > 50KB (reasonable for a 300 DPI heatmap)
# REASONING: A 300 DPI 9x8 inch PNG should be at least 50KB. Smaller files
# suggest the plot rendered empty or with minimal content.
if fig_exists:
    fig_size = OUTPUT_PATH.stat().st_size
    fig_size_ok = fig_size > 50_000
    print(f"  [{'PASS' if fig_size_ok else 'WARN'}] Figure size: {fig_size:,} bytes (threshold: 50,000)")
else:
    fig_size_ok = False
    print(f"  [FAIL] Figure size: file not found")

# CP4.3: Diagonal values are 1.0
diag_values = df_long.filter(pl.col("var1") == pl.col("var2"))["corr"].to_list()
diag_all_one = all(abs(v - 1.0) < 0.001 for v in diag_values)
print(f"  [{'PASS' if diag_all_one else 'FAIL'}] Diagonal values all 1.0: {diag_values}")

# CP4.4: Correlation values in [-1, 1] range
min_corr = df_long["corr"].min()
max_corr = df_long["corr"].max()
range_ok = min_corr >= -1.001 and max_corr <= 1.001
print(f"  [{'PASS' if range_ok else 'FAIL'}] Correlation range valid: [{min_corr:.3f}, {max_corr:.3f}]")

# CP4.5: Full matrix completeness (6x6 = 36 cells)
cells_ok = n_cells == expected_cells
print(f"  [{'PASS' if cells_ok else 'WARN'}] Matrix completeness: {n_cells} cells (expected {expected_cells})")

# CP4.6: All 6 variables represented
vars_in_matrix = set(df_long["var1"].unique().to_list())
all_vars_present = all(v in vars_in_matrix for v in VARIABLES)
print(f"  [{'PASS' if all_vars_present else 'FAIL'}] All variables present: {sorted(vars_in_matrix)}")

# CP4.7: No spurious variables (e.g., "pearson" should NOT appear as a variable)
spurious_vars = vars_in_matrix - set(VARIABLES)
no_spurious = len(spurious_vars) == 0
print(f"  [{'PASS' if no_spurious else 'FAIL'}] No spurious variables: {spurious_vars if spurious_vars else 'none'}")

all_passed = all([fig_exists, fig_size_ok, diag_all_one, range_ok, cells_ok, all_vars_present, no_spurious])
assert fig_exists, "STOP: Figure file not saved"
assert diag_all_one, "STOP: Diagonal values are not 1.0"
assert range_ok, "STOP: Correlation values outside [-1, 1]"
assert all_vars_present, "STOP: Missing expected variables"
assert no_spurious, "STOP: Spurious variables in matrix"

print("\n" + "=" * 60)
print(f"CP4 VALIDATION: {'PASSED' if all_passed else 'PASSED WITH WARNINGS'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:14:49
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.4 (Step 9.4): Correlation Heatmap Visualization
# ============================================================
# Loaded correlation matrix: 12 rows x 8 cols
# Columns: ['method', 'variable', 'grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
# 
# Pre-state: 12 rows
# Methods present: ['spearman', 'pearson']
# Variables present: ['urm_share', 'admission_rate', 'retention_rate', 'student_faculty_ratio', 'pell_share', 'grad_rate_150pct']
# 
# Filtered to Pearson correlations: 6 rows
# 
# Melted to long format: 36 rows (expected 36)
# Sample:
# shape: (6, 3)
# ┌───────────────────────┬──────────────────┬───────────┐
# │ var1                  ┆ var2             ┆ corr      │
# │ ---                   ┆ ---              ┆ ---       │
# │ str                   ┆ str              ┆ f64       │
# ╞═══════════════════════╪══════════════════╪═══════════╡
# │ grad_rate_150pct      ┆ grad_rate_150pct ┆ 1.0       │
# │ admission_rate        ┆ grad_rate_150pct ┆ -0.35887  │
# │ pell_share            ┆ grad_rate_150pct ┆ -0.620643 │
# │ urm_share             ┆ grad_rate_150pct ┆ -0.368845 │
# │ student_faculty_ratio ┆ grad_rate_150pct ┆ -0.22016  │
# │ retention_rate        ┆ grad_rate_150pct ┆ 0.629565  │
# └───────────────────────┴──────────────────┴───────────┘
# 
# Matrix cells: 36 (expected 36)
# 
# Plot dataframe shape: (36, 6)
# Unique var1 labels: ['Admission Rate', 'Graduation Rate', 'Pell Share', 'Retention Rate', 'Student-Faculty Ratio', 'URM Share']
# Unique var2 labels: ['Admission Rate', 'Graduation Rate', 'Pell Share', 'Retention Rate', 'Student-Faculty Ratio', 'URM Share']
# Correlation range: [-0.621, 1.000]
# 
# Saved figure: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_correlation_heatmap.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION (Visualization)
# ============================================================
#   [PASS] Figure file exists: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_correlation_heatmap.png
#   [PASS] Figure size: 310,234 bytes (threshold: 50,000)
#   [PASS] Diagonal values all 1.0: [1.0, 0.9999999999999999, 1.0, 1.0, 1.0, 1.0]
#   [PASS] Correlation range valid: [-0.621, 1.000]
#   [PASS] Matrix completeness: 36 cells (expected 36)
#   [PASS] All variables present: ['admission_rate', 'grad_rate_150pct', 'pell_share', 'retention_rate', 'student_faculty_ratio', 'urm_share']
#   [PASS] No spurious variables: none
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
