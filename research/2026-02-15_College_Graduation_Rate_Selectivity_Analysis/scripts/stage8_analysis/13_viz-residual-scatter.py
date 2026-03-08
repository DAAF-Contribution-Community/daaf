#!/usr/bin/env python3
"""
Stage 8.2 (Step 10.2): Actual vs. Predicted Graduation Rate scatter plot.

Task: viz-residual-scatter
Wave: 10, Step: 10.2, Stage: 8.2
Depends on: regression-models (Step 8.1)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/figures/2026-02-15_actual_vs_predicted.png
Checkpoint: CP4 (figure existence, data source, labeling)
"""

import numpy as np
import polars as pl
from pathlib import Path
from plotnine import (
    ggplot, aes, geom_point, geom_abline, labs, theme_minimal,
    scale_color_manual, theme, element_text, element_rect,
    scale_x_continuous, scale_y_continuous, guides, guide_legend,
)

# --- Config ---
# Configuration for scatter plot of actual vs. predicted graduation rate.
# Model 3 is RE-FIT from the analysis data using numpy OLS (not parsed from
# saved coefficients) per plan-checker warning. This ensures predicted values
# come from the same OLS fit used to compute them.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_actual_vs_predicted.png"

# Model 3 specification: grad_rate_150pct ~ admission_rate + pell_share +
# urm_share + student_faculty_ratio + sector_private
# where sector_private = 1 if inst_control == 2, else 0.
MODEL_COLS = ["admission_rate", "pell_share", "urm_share", "student_faculty_ratio"]
OUTCOME_COL = "grad_rate_150pct"

# REASONING: Colorblind-safe palette using ColorBrewer qualitative scheme.
# Four distinct colors for four selectivity bands, chosen to be distinguishable
# by viewers with deuteranopia and protanopia.
SELECTIVITY_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
SELECTIVITY_COLORS = {
    "Highly Selective": "#d73027",
    "Selective": "#fc8d59",
    "Moderately Selective": "#91bfdb",
    "Less Selective/Open": "#4575b4",
}

# --- Load ---
# Load the analysis dataset and verify it contains all required columns.
print("=" * 60)
print("Stage 8.2 (Step 10.2): Actual vs. Predicted Graduation Rate")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

required_cols = [OUTCOME_COL] + MODEL_COLS + ["inst_control", "selectivity_band"]
missing = [c for c in required_cols if c not in df.columns]
assert not missing, f"STOP: Missing required columns: {missing}"

# --- Pre-state ---
# Capture current state before any filtering. We need listwise deletion on
# the 6 model columns (outcome + 4 predictors + inst_control for sector_private).
pre_rows = df.shape[0]
print(f"Pre-state: {pre_rows:,} rows")

for c in [OUTCOME_COL] + MODEL_COLS + ["inst_control"]:
    print(f"  {c}: {df[c].null_count()} nulls")

# --- Transform: Derive sector_private and apply listwise deletion ---
# INTENT: Create binary sector indicator and drop rows with any missing values
# in model variables so the OLS fit uses exactly the same sample as the original
# Model 3 regression (N ~ 1,523).
#
# REASONING: sector_private = 1 for private institutions (inst_control == 2),
# 0 otherwise. Listwise deletion on all 6 columns (outcome + 5 predictors)
# ensures the OLS fit matches the original regression's sample size exactly.
#
# ASSUMES:
#   - inst_control has values 1 (public) and 2 (private) with no nulls
#   - The same listwise deletion was used in the regression-models script
df_model = (
    df
    .with_columns(
        pl.when(pl.col("inst_control") == 2)
        .then(1)
        .otherwise(0)
        .alias("sector_private")
        .cast(pl.Float64)  # Float for OLS matrix
    )
    .drop_nulls(subset=[OUTCOME_COL] + MODEL_COLS)
)

complete_cases = df_model.shape[0]
print(f"\nComplete cases after listwise deletion: {complete_cases:,}")
print(f"Dropped: {pre_rows - complete_cases:,} rows ({(pre_rows - complete_cases) / pre_rows * 100:.1f}%)")

# --- RE-FIT Model 3 via numpy OLS ---
# INTENT: Re-fit Model 3 from scratch using the analysis data directly, rather
# than parsing saved coefficients. This ensures predicted values are computed
# from the exact same OLS fit.
#
# REASONING: Per plan-checker warning, re-fitting is mandatory. Using numpy
# lstsq (ordinary least squares via QR decomposition) because it's the standard
# approach for linear regression and avoids external dependencies like statsmodels.
# The formula is: grad_rate_150pct = b0 + b1*admission_rate + b2*pell_share +
# b3*urm_share + b4*student_faculty_ratio + b5*sector_private
#
# ASSUMES:
#   - No multicollinearity issues (VIFs checked in regression-models script, all < 2.0)
#   - Linear relationship is adequate for this visualization purpose
#   - Sample is the same N ~ 1,523 used in the original regression

# Build design matrix X (with intercept) and outcome vector y
y = df_model[OUTCOME_COL].to_numpy().astype(np.float64)
X_cols = MODEL_COLS + ["sector_private"]
X_data = np.column_stack([df_model[c].to_numpy().astype(np.float64) for c in X_cols])
X = np.column_stack([np.ones(len(y)), X_data])  # Prepend intercept column

print(f"\nOLS Design Matrix: {X.shape[0]} obs x {X.shape[1]} predictors (incl. intercept)")

# Solve via numpy least squares
beta, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)

# Report coefficients for verification against saved regression results
coef_names = ["intercept"] + X_cols
print("\nRe-fitted Model 3 coefficients:")
for name, b in zip(coef_names, beta):
    print(f"  {name}: {b:.6f}")

# Compute R-squared for verification
y_pred = X @ beta
ss_res = np.sum((y - y_pred) ** 2)
ss_tot = np.sum((y - np.mean(y)) ** 2)
r_squared = 1 - ss_res / ss_tot
print(f"\nR-squared: {r_squared:.6f}")
print(f"N: {len(y)}")

# --- Validation: Predicted values sanity ---
# INTENT: Verify predicted graduation rates are in a reasonable range before
# plotting. Extreme predicted values would indicate a model fitting error.
pred_min = y_pred.min()
pred_max = y_pred.max()
print(f"\nPredicted range: [{pred_min:.1f}, {pred_max:.1f}]")
assert pred_min > -20, f"STOP: Predicted min too low: {pred_min:.1f}"
assert pred_max < 120, f"STOP: Predicted max too high: {pred_max:.1f}"

# --- Add predicted values to DataFrame ---
# INTENT: Attach predicted graduation rates to the model data for plotting.
df_plot = df_model.with_columns(
    pl.Series("predicted_grad_rate", y_pred)
)

# INTENT: Convert selectivity_band to a categorical with specified order so
# the legend displays bands from most to least selective.
# REASONING: pandas Categorical is needed because plotnine inherits ggplot2's
# factor ordering. Polars does not natively enforce category order in plotnine.
df_plot_pd = df_plot.select([
    "predicted_grad_rate", OUTCOME_COL, "selectivity_band"
]).to_pandas()

import pandas as pd
df_plot_pd["selectivity_band"] = pd.Categorical(
    df_plot_pd["selectivity_band"],
    categories=SELECTIVITY_ORDER,
    ordered=True,
)

# --- Plot ---
# INTENT: Create scatter plot of actual vs. predicted graduation rate to
# visualize how well Model 3 explains variation in graduation rates and
# identify institutions that outperform or underperform their prediction.
# Points above the 45-degree line are outperformers; below are underperformers.
#
# REASONING: Scatter plot (not line or bar) because both variables are continuous.
# Alpha=0.5 handles overplotting (~1,523 points). The 45-degree reference line
# (intercept=0, slope=1) shows where actual == predicted. Coloring by selectivity
# band reveals whether model fit varies by institutional selectivity.
#
# ASSUMES:
#   - predicted_grad_rate and grad_rate_150pct are on the same scale (percentages)
#   - selectivity_band has four levels as defined in SELECTIVITY_ORDER
print("\nBuilding scatter plot...")

plot = (
    ggplot(df_plot_pd, aes(x="predicted_grad_rate", y=OUTCOME_COL, color="selectivity_band"))
    + geom_point(alpha=0.5, size=1.5)
    + geom_abline(intercept=0, slope=1, linetype="dashed", color="black", size=0.7)  # 45-degree line
    + scale_color_manual(
        values=SELECTIVITY_COLORS,
        name="Selectivity Band",
    )
    + scale_x_continuous(
        limits=(0, 100),
        breaks=list(range(0, 101, 20)),
    )
    + scale_y_continuous(
        limits=(0, 100),
        breaks=list(range(0, 101, 20)),
    )
    + labs(
        title="Actual vs. Predicted Graduation Rate",
        subtitle="Predicted from admission rate, Pell share, URM share, student-faculty ratio, and sector",
        x="Predicted Graduation Rate (%)",
        y="Actual Graduation Rate (%)",
        caption=f"Source: IPEDS 2020, FSA 2020. Model 3 OLS regression (R²={r_squared:.3f}, N={len(y):,}).",
    )
    + theme_minimal()
    + theme(
        figure_size=(10, 8),
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=10),
        plot_caption=element_text(size=8),
        legend_position="bottom",
        legend_title=element_text(size=10),
        panel_background=element_rect(fill="white"),
    )
    + guides(color=guide_legend(override_aes={"size": 4, "alpha": 1}))
)

# --- Save ---
# Persist the figure to output/figures/ at 300 DPI for publication quality.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
plot.save(OUTPUT_PATH, dpi=300, width=10, height=8, verbose=False)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify figure was saved, has reasonable size,
# and predicted values are in expected range.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

# CP4.1: Figure file exists
fig_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if fig_exists else 'FAIL'}] Figure file exists: {OUTPUT_PATH.name}")

# CP4.2: Figure file size > 50KB (not a blank/corrupt image)
if fig_exists:
    fig_size_kb = OUTPUT_PATH.stat().st_size / 1024
    size_ok = fig_size_kb > 50
    print(f"  [{'PASS' if size_ok else 'FAIL'}] Figure size: {fig_size_kb:.1f} KB (> 50 KB required)")
else:
    size_ok = False
    print("  [FAIL] Cannot check size - file missing")

# CP4.3: Predicted values in reasonable range (0-100)
pred_range_ok = pred_min >= -10 and pred_max <= 110
print(f"  [{'PASS' if pred_range_ok else 'WARN'}] Predicted range: [{pred_min:.1f}, {pred_max:.1f}]")

# CP4.4: N matches expected ~1,523
n_ok = 1400 <= len(y) <= 1600
print(f"  [{'PASS' if n_ok else 'WARN'}] Sample size: {len(y):,} (expected ~1,523)")

# CP4.5: R² matches expected ~0.456
r2_ok = abs(r_squared - 0.456) < 0.01
print(f"  [{'PASS' if r2_ok else 'WARN'}] R²: {r_squared:.6f} (expected ~0.456)")

# CP4.6: 45-degree reference line present (by construction — geom_abline in plot)
print("  [PASS] 45-degree reference line: present (geom_abline intercept=0, slope=1)")

# CP4.7: Points colored by selectivity band (verified 4 bands in data)
bands_present = df_plot_pd["selectivity_band"].nunique()
bands_ok = bands_present == 4
print(f"  [{'PASS' if bands_ok else 'FAIL'}] Selectivity bands: {bands_present} (expected 4)")

all_passed = all([fig_exists, size_ok, pred_range_ok, n_ok, r2_ok, bands_ok])

assert fig_exists, "STOP: Figure file not saved"
assert size_ok, "STOP: Figure file too small (corrupt?)"

print("\n" + "=" * 60)
print(f"CP4 VALIDATION: {'PASSED' if all_passed else 'PASSED WITH WARNINGS'}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:23:55
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/13_viz-residual-scatter.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.2 (Step 10.2): Actual vs. Predicted Graduation Rate
# ============================================================
# Loaded: 2,528 rows x 26 cols
# Pre-state: 2,528 rows
#   grad_rate_150pct: 732 nulls
#   admission_rate: 869 nulls
#   pell_share: 518 nulls
#   urm_share: 370 nulls
#   student_faculty_ratio: 370 nulls
#   inst_control: 0 nulls
# 
# Complete cases after listwise deletion: 1,523
# Dropped: 1,005 rows (39.8%)
# 
# OLS Design Matrix: 1523 obs x 6 predictors (incl. intercept)
# 
# Re-fitted Model 3 coefficients:
#   intercept: 97.749405
#   admission_rate: -22.960301
#   pell_share: -60.558279
#   urm_share: 0.945381
#   student_faculty_ratio: -0.114461
#   sector_private: 1.221654
# 
# R-squared: 0.455891
# N: 1523
# 
# Predicted range: [15.7, 94.5]
# 
# Building scatter plot...
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-02-15_actual_vs_predicted.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] Figure file exists: 2026-02-15_actual_vs_predicted.png
#   [PASS] Figure size: 1009.8 KB (> 50 KB required)
#   [PASS] Predicted range: [15.7, 94.5]
#   [PASS] Sample size: 1,523 (expected ~1,523)
#   [PASS] R²: 0.455891 (expected ~0.456)
#   [PASS] 45-degree reference line: present (geom_abline intercept=0, slope=1)
#   [PASS] Selectivity bands: 4 (expected 4)
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
