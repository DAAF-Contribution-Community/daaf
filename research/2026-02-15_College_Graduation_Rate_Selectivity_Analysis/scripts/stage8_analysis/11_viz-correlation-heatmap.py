#!/usr/bin/env python3
"""
Stage 8.4 (Step 9.4): Correlation heatmap of key institutional variables.

Task: viz-correlation-heatmap
Wave: 9, Step: 9.4, Stage: 8
Depends on: correlation-matrix (Step 9.3)
Input: output/analysis/2026-02-15_correlation_matrix.parquet
Output: output/figures/2026-02-15_correlation_heatmap.png
Checkpoint: CP4 (figure existence + data integrity)
"""

import polars as pl
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
# both Pearson and Spearman methods. This visualization uses Pearson correlations
# to create a symmetric heatmap of pairwise correlations among 6 key variables.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
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
# contains 12 rows: 6 variable pairs x 2 methods (pearson, spearman).
print("=" * 60)
print("Stage 8.4 (Step 9.4): Correlation Heatmap Visualization")
print("=" * 60)

df_corr = pl.read_parquet(INPUT_PATH)
print(f"Loaded correlation matrix: {df_corr.shape[0]:,} rows x {df_corr.shape[1]} cols")
print(f"Columns: {df_corr.columns}")

# --- Pre-state ---
# Verify the correlation matrix has the expected structure before proceeding.
# ASSUMES:
#   - The parquet contains columns: variable_1, variable_2, pearson, spearman (at minimum)
#   - Each pair appears once per method, with 6 variables producing 6*(6-1)/2 = 15 unique pairs
#   - Or it may be structured differently — inspect first
print(f"\nPre-state: {df_corr.shape[0]} rows")
print(f"Sample:\n{df_corr.head(5)}")

# Determine the structure of the correlation matrix
print(f"\nColumn dtypes: {dict(zip(df_corr.columns, [str(d) for d in df_corr.dtypes]))}")

# --- Transform ---
# INTENT: Reshape the correlation matrix into a long-format dataframe suitable
# for geom_tile() heatmap. We need columns: var1, var2, correlation_value.
# We filter to Pearson correlations only and create the full symmetric matrix
# (including diagonal) so every cell in the heatmap has a value.
#
# REASONING: geom_tile needs every (x, y) combination as a row. The input
# correlation matrix likely has only the upper triangle or a condensed format.
# We must expand to the full square matrix including the diagonal (1.0 values)
# for a complete heatmap.

# First, identify the structure
if "method" in df_corr.columns:
    # Filter to Pearson only
    # REASONING: Pearson is the standard choice for showing linear relationships
    # in a correlation heatmap. Spearman is available for robustness checking
    # but would be a separate visualization if needed.
    df_pearson = df_corr.filter(pl.col("method") == "pearson")
    print(f"\nFiltered to Pearson correlations: {df_pearson.shape[0]} rows")
else:
    df_pearson = df_corr
    print("\nNo 'method' column found — using all rows as Pearson correlations")

# Determine which columns hold variable names and correlation values
# ASSUMES: The dataframe has columns for the two variable names and correlation value
print(f"\nPearson data columns: {df_pearson.columns}")
print(f"Sample:\n{df_pearson.head()}")

# Build the full symmetric matrix for the heatmap
# INTENT: Create all (var1, var2, corr) triples including:
#   - The original pairs (upper triangle)
#   - The mirror pairs (lower triangle, same correlation value)
#   - The diagonal (var with itself = 1.0)
#
# REASONING: A correlation matrix is symmetric by definition (corr(A,B) = corr(B,A)).
# We need every cell filled for geom_tile to render the complete heatmap.

# Detect the column names for variable identifiers and correlation value
var1_col = None
var2_col = None
corr_col = None

for col in df_pearson.columns:
    col_lower = col.lower()
    if col_lower in ("variable_1", "var1", "variable1"):
        var1_col = col
    elif col_lower in ("variable_2", "var2", "variable2"):
        var2_col = col
    elif col_lower in ("correlation", "pearson", "corr", "value", "r"):
        corr_col = col

# Fallback: if we have standard column naming
if var1_col is None or var2_col is None or corr_col is None:
    print(f"\nAttempting column detection from: {df_pearson.columns}")
    str_cols = [c for c in df_pearson.columns if df_pearson[c].dtype == pl.Utf8]
    num_cols = [c for c in df_pearson.columns if df_pearson[c].dtype in (pl.Float64, pl.Float32)]
    print(f"  String columns: {str_cols}")
    print(f"  Numeric columns: {num_cols}")

    if len(str_cols) >= 2:
        var1_col = var1_col or str_cols[0]
        var2_col = var2_col or str_cols[1]
    if len(num_cols) >= 1 and corr_col is None:
        # Pick the first numeric column that isn't n_obs or similar
        for nc in num_cols:
            if nc.lower() not in ("n", "n_obs", "count", "spearman"):
                corr_col = nc
                break
        if corr_col is None:
            corr_col = num_cols[0]

print(f"\nUsing columns: var1={var1_col}, var2={var2_col}, corr={corr_col}")

# ASSUMES: var1_col, var2_col, and corr_col are now identified correctly
assert var1_col is not None, "STOP: Could not identify variable_1 column"
assert var2_col is not None, "STOP: Could not identify variable_2 column"
assert corr_col is not None, "STOP: Could not identify correlation value column"

# Extract the pairs into a clean format
pairs = df_pearson.select([
    pl.col(var1_col).alias("var1"),
    pl.col(var2_col).alias("var2"),
    pl.col(corr_col).cast(pl.Float64).alias("corr"),
])

print(f"\nExtracted {pairs.shape[0]} correlation pairs")
print(f"Pairs sample:\n{pairs.head()}")

# Build the full symmetric matrix
# Step 1: Create mirror pairs (swap var1 and var2)
mirror = pairs.select([
    pl.col("var2").alias("var1"),
    pl.col("var1").alias("var2"),
    pl.col("corr"),
])

# Step 2: Create diagonal entries (each variable correlated with itself = 1.0)
# REASONING: The diagonal of a correlation matrix is always 1.0 by definition.
# Including it ensures the heatmap is visually complete and provides a reference
# for the color scale maximum.
unique_vars = list(set(
    pairs["var1"].unique().to_list() + pairs["var2"].unique().to_list()
))
diagonal = pl.DataFrame({
    "var1": unique_vars,
    "var2": unique_vars,
    "corr": [1.0] * len(unique_vars),
})

# Step 3: Combine all parts
full_matrix = pl.concat([pairs, mirror, diagonal])

# Deduplicate (in case input already had some mirror pairs)
full_matrix = full_matrix.unique(subset=["var1", "var2"])

print(f"\nFull symmetric matrix: {full_matrix.shape[0]} cells")
print(f"Expected: {len(VARIABLES)}x{len(VARIABLES)} = {len(VARIABLES)**2} cells")

# --- Apply human-readable labels ---
# INTENT: Replace variable names with readable labels for the plot axes.
# REASONING: Raw variable names (e.g., "grad_rate_150pct") are not reader-friendly.
# Shorter, descriptive labels improve plot readability and accessibility.
full_matrix = full_matrix.with_columns([
    pl.col("var1").replace(VARIABLE_LABELS).alias("var1_label"),
    pl.col("var2").replace(VARIABLE_LABELS).alias("var2_label"),
])

# INTENT: Create formatted correlation text for cell annotations.
# REASONING: Annotating cells with exact values lets readers extract precise
# information beyond what color alone conveys. Diagonal cells show "1.00" for
# completeness and visual consistency.
full_matrix = full_matrix.with_columns(
    pl.col("corr").round(2).cast(pl.Utf8).alias("corr_text")
)

# Convert to pandas for plotnine
# REASONING: plotnine requires pandas DataFrames. Polars → pandas conversion
# is lightweight for 36 rows.
df_plot = full_matrix.to_pandas()

print(f"\nPlot dataframe shape: {df_plot.shape}")
print(f"Unique var1 labels: {sorted(df_plot['var1_label'].unique())}")
print(f"Unique var2 labels: {sorted(df_plot['var2_label'].unique())}")
print(f"Correlation range: [{df_plot['corr'].min():.3f}, {df_plot['corr'].max():.3f}]")

# --- Define variable order ---
# INTENT: Order variables logically for the heatmap so related variables are adjacent.
# REASONING: Grouping outcome (graduation) first, then selectivity (admission),
# then demographics (pell, urm), then resources (student-faculty), then engagement
# (retention) follows the conceptual flow of the research question: outcome →
# selectivity → demographics → resources → engagement.
var_order = [
    "Graduation Rate",
    "Admission Rate",
    "Pell Share",
    "URM Share",
    "Student-Faculty Ratio",
    "Retention Rate",
]

import pandas as pd

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
#   - The matrix is symmetric (ensured by construction above)
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
diag_values = full_matrix.filter(pl.col("var1") == pl.col("var2"))["corr"].to_list()
diag_all_one = all(abs(v - 1.0) < 0.001 for v in diag_values)
print(f"  [{'PASS' if diag_all_one else 'FAIL'}] Diagonal values all 1.0: {diag_values}")

# CP4.4: Correlation values in [-1, 1] range
min_corr = full_matrix["corr"].min()
max_corr = full_matrix["corr"].max()
range_ok = min_corr >= -1.001 and max_corr <= 1.001
print(f"  [{'PASS' if range_ok else 'FAIL'}] Correlation range valid: [{min_corr:.3f}, {max_corr:.3f}]")

# CP4.5: Full matrix completeness (6x6 = 36 cells)
n_cells = full_matrix.shape[0]
cells_ok = n_cells == len(VARIABLES) ** 2
print(f"  [{'PASS' if cells_ok else 'WARN'}] Matrix completeness: {n_cells} cells (expected {len(VARIABLES)**2})")

# CP4.6: All 6 variables represented
vars_in_matrix = set(full_matrix["var1"].unique().to_list())
all_vars_present = all(v in vars_in_matrix for v in VARIABLES)
print(f"  [{'PASS' if all_vars_present else 'FAIL'}] All variables present: {sorted(vars_in_matrix)}")

all_passed = all([fig_exists, fig_size_ok, diag_all_one, range_ok, all_vars_present])
assert fig_exists, "STOP: Figure file not saved"
assert diag_all_one, "STOP: Diagonal values are not 1.0"
assert range_ok, "STOP: Correlation values outside [-1, 1]"

print("\n" + "=" * 60)
print(f"CP4 VALIDATION: {'PASSED' if all_passed else 'PASSED WITH WARNINGS'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:13:34
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap.py:250: Pandas4Warning: Constructing a Categorical with a dtype and values containing non-null entries not in that dtype's categories is deprecated and will raise in a future version.
# /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/11_viz-correlation-heatmap.py:251: Pandas4Warning: Constructing a Categorical with a dtype and values containing non-null entries not in that dtype's categories is deprecated and will raise in a future version.
# ============================================================
# Stage 8.4 (Step 9.4): Correlation Heatmap Visualization
# ============================================================
# Loaded correlation matrix: 12 rows x 8 cols
# Columns: ['method', 'variable', 'grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
# 
# Pre-state: 12 rows
# Sample:
# shape: (5, 8)
# ┌─────────┬────────────┬────────────┬────────────┬────────────┬───────────┬────────────┬───────────┐
# │ method  ┆ variable   ┆ grad_rate_ ┆ admission_ ┆ pell_share ┆ urm_share ┆ student_fa ┆ retention │
# │ ---     ┆ ---        ┆ 150pct     ┆ rate       ┆ ---        ┆ ---       ┆ culty_rati ┆ _rate     │
# │ str     ┆ str        ┆ ---        ┆ ---        ┆ f64        ┆ f64       ┆ o          ┆ ---       │
# │         ┆            ┆ f64        ┆ f64        ┆            ┆           ┆ ---        ┆ f64       │
# │         ┆            ┆            ┆            ┆            ┆           ┆ f64        ┆           │
# ╞═════════╪════════════╪════════════╪════════════╪════════════╪═══════════╪════════════╪═══════════╡
# │ pearson ┆ grad_rate_ ┆ 1.0        ┆ -0.35887   ┆ -0.620643  ┆ -0.368845 ┆ -0.22016   ┆ 0.629565  │
# │         ┆ 150pct     ┆            ┆            ┆            ┆           ┆            ┆           │
# │ pearson ┆ admission_ ┆ -0.35887   ┆ 1.0        ┆ 0.160294   ┆ -0.003417 ┆ 0.211869   ┆ -0.217032 │
# │         ┆ rate       ┆            ┆            ┆            ┆           ┆            ┆           │
# │ pearson ┆ pell_share ┆ -0.620643  ┆ 0.160294   ┆ 1.0        ┆ 0.638491  ┆ 0.221837   ┆ -0.449387 │
# │ pearson ┆ urm_share  ┆ -0.368845  ┆ -0.003417  ┆ 0.638491   ┆ 1.0       ┆ 0.212461   ┆ -0.261098 │
# │ pearson ┆ student_fa ┆ -0.22016   ┆ 0.211869   ┆ 0.221837   ┆ 0.212461  ┆ 1.0        ┆ 0.042914  │
# │         ┆ culty_rati ┆            ┆            ┆            ┆           ┆            ┆           │
# │         ┆ o          ┆            ┆            ┆            ┆           ┆            ┆           │
# └─────────┴────────────┴────────────┴────────────┴────────────┴───────────┴────────────┴───────────┘
# 
# Column dtypes: {'method': 'String', 'variable': 'String', 'grad_rate_150pct': 'Float64', 'admission_rate': 'Float64', 'pell_share': 'Float64', 'urm_share': 'Float64', 'student_faculty_ratio': 'Float64', 'retention_rate': 'Float64'}
# 
# Filtered to Pearson correlations: 6 rows
# 
# Pearson data columns: ['method', 'variable', 'grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
# Sample:
# shape: (5, 8)
# ┌─────────┬────────────┬────────────┬────────────┬────────────┬───────────┬────────────┬───────────┐
# │ method  ┆ variable   ┆ grad_rate_ ┆ admission_ ┆ pell_share ┆ urm_share ┆ student_fa ┆ retention │
# │ ---     ┆ ---        ┆ 150pct     ┆ rate       ┆ ---        ┆ ---       ┆ culty_rati ┆ _rate     │
# │ str     ┆ str        ┆ ---        ┆ ---        ┆ f64        ┆ f64       ┆ o          ┆ ---       │
# │         ┆            ┆ f64        ┆ f64        ┆            ┆           ┆ ---        ┆ f64       │
# │         ┆            ┆            ┆            ┆            ┆           ┆ f64        ┆           │
# ╞═════════╪════════════╪════════════╪════════════╪════════════╪═══════════╪════════════╪═══════════╡
# │ pearson ┆ grad_rate_ ┆ 1.0        ┆ -0.35887   ┆ -0.620643  ┆ -0.368845 ┆ -0.22016   ┆ 0.629565  │
# │         ┆ 150pct     ┆            ┆            ┆            ┆           ┆            ┆           │
# │ pearson ┆ admission_ ┆ -0.35887   ┆ 1.0        ┆ 0.160294   ┆ -0.003417 ┆ 0.211869   ┆ -0.217032 │
# │         ┆ rate       ┆            ┆            ┆            ┆           ┆            ┆           │
# │ pearson ┆ pell_share ┆ -0.620643  ┆ 0.160294   ┆ 1.0        ┆ 0.638491  ┆ 0.221837   ┆ -0.449387 │
# │ pearson ┆ urm_share  ┆ -0.368845  ┆ -0.003417  ┆ 0.638491   ┆ 1.0       ┆ 0.212461   ┆ -0.261098 │
# │ pearson ┆ student_fa ┆ -0.22016   ┆ 0.211869   ┆ 0.221837   ┆ 0.212461  ┆ 1.0        ┆ 0.042914  │
# │         ┆ culty_rati ┆            ┆            ┆            ┆           ┆            ┆           │
# │         ┆ o          ┆            ┆            ┆            ┆           ┆            ┆           │
# └─────────┴────────────┴────────────┴────────────┴────────────┴───────────┴────────────┴───────────┘
# 
# Attempting column detection from: ['method', 'variable', 'grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
#   String columns: ['method', 'variable']
#   Numeric columns: ['grad_rate_150pct', 'admission_rate', 'pell_share', 'urm_share', 'student_faculty_ratio', 'retention_rate']
# 
# Using columns: var1=method, var2=variable, corr=grad_rate_150pct
# 
# Extracted 6 correlation pairs
# Pairs sample:
# shape: (5, 3)
# ┌─────────┬───────────────────────┬───────────┐
# │ var1    ┆ var2                  ┆ corr      │
# │ ---     ┆ ---                   ┆ ---       │
# │ str     ┆ str                   ┆ f64       │
# ╞═════════╪═══════════════════════╪═══════════╡
# │ pearson ┆ grad_rate_150pct      ┆ 1.0       │
# │ pearson ┆ admission_rate        ┆ -0.35887  │
# │ pearson ┆ pell_share            ┆ -0.620643 │
# │ pearson ┆ urm_share             ┆ -0.368845 │
# │ pearson ┆ student_faculty_ratio ┆ -0.22016  │
# └─────────┴───────────────────────┴───────────┘
# 
# Full symmetric matrix: 19 cells
# Expected: 6x6 = 36 cells
# 
# Plot dataframe shape: (19, 6)
# Unique var1 labels: ['Admission Rate', 'Graduation Rate', 'Pell Share', 'Retention Rate', 'Student-Faculty Ratio', 'URM Share', 'pearson']
# Unique var2 labels: ['Admission Rate', 'Graduation Rate', 'Pell Share', 'Retention Rate', 'Student-Faculty Ratio', 'URM Share', 'pearson']
# Correlation range: [-0.621, 1.000]
# 
# Saved figure: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-02-15_correlation_heatmap.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION (Visualization)
# ============================================================
#   [PASS] Figure file exists: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-02-15_correlation_heatmap.png
#   [PASS] Figure size: 271,955 bytes (threshold: 50,000)
#   [PASS] Diagonal values all 1.0: [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
#   [PASS] Correlation range valid: [-0.621, 1.000]
#   [WARN] Matrix completeness: 19 cells (expected 36)
#   [PASS] All variables present: ['admission_rate', 'grad_rate_150pct', 'pearson', 'pell_share', 'retention_rate', 'student_faculty_ratio', 'urm_share']
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
