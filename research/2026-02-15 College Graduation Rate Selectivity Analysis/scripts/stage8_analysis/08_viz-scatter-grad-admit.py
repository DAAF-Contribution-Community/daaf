#!/usr/bin/env python3
"""
Stage 8.2 (Step 9.1): Scatter plot of graduation rate vs. admission rate by sector.

Task: viz-scatter-grad-admit
Wave: 9, Step: 9.1, Stage: 8
Depends on: create-bands
Input: data/processed/2026-02-15_analysis.parquet
Output: output/figures/2026-02-15_grad_rate_vs_admission_rate.png
Checkpoint: CP4 (figure existence, data source accuracy, labeling)
"""

import polars as pl
from pathlib import Path
from plotnine import (
    ggplot, aes, geom_point, geom_smooth,
    labs, theme_minimal, theme, element_text,
    scale_color_manual, guides, guide_legend,
)

# --- Config ---
# Configuration constants for scatter plot visualization. The plot shows the
# relationship between admission rate (selectivity) and graduation rate,
# colored by institutional sector. This is a core visualization for the
# research question: whether high graduation rates reflect institutional
# quality or primarily admissions selectivity.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_DIR = PROJECT_DIR / "output" / "figures"
OUTPUT_PATH = OUTPUT_DIR / f"{DATE_PREFIX}_grad_rate_vs_admission_rate.png"

# REASONING: inst_control values are 1=Public, 2=Private Nonprofit per IPEDS.
# We map these to human-readable labels for the legend.
SECTOR_LABELS = {1: "Public", 2: "Private Nonprofit"}

# REASONING: Using colorblind-safe palette from ColorBrewer. "#1b9e77" (teal)
# and "#d95f02" (orange) are distinguishable under all common forms of color
# vision deficiency (protanopia, deuteranopia, tritanopia). These are from
# the "Dark2" qualitative palette.
SECTOR_COLORS = {"Public": "#1b9e77", "Private Nonprofit": "#d95f02"}

# --- Load ---
# Load analysis dataset and verify it contains the required columns.
print("=" * 60)
print("Stage 8.2 (Step 9.1): Scatter — Graduation Rate vs. Admission Rate")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state before filtering so we can report how many rows are used
# in the visualization vs. how many were excluded due to missing values.
pre_rows = df.shape[0]
print(f"Pre-state: {pre_rows:,} rows")

# Check required columns exist
required_cols = ["grad_rate_150pct", "admission_rate", "inst_control"]
missing = [c for c in required_cols if c not in df.columns]
assert len(missing) == 0, f"STOP: Missing required columns: {missing}"

# Report nulls in key columns before filtering
grad_nulls = df["grad_rate_150pct"].null_count()
admit_nulls = df["admission_rate"].null_count()
control_nulls = df["inst_control"].null_count()
print(f"Nulls — grad_rate_150pct: {grad_nulls:,} ({grad_nulls/pre_rows*100:.1f}%)")
print(f"Nulls — admission_rate: {admit_nulls:,} ({admit_nulls/pre_rows*100:.1f}%)")
print(f"Nulls — inst_control: {control_nulls:,} ({control_nulls/pre_rows*100:.1f}%)")

# --- Transform ---
# INTENT: Filter to rows where both graduation rate and admission rate are
# non-null, then create display-ready columns for the scatter plot.
#
# REASONING: We filter rather than impute because the visualization must
# show actual observed relationships. Imputed values would create artificial
# visual patterns. Admission rate is converted from 0-1 proportion to
# 0-100 percentage scale for interpretability on the x-axis.
#
# ASSUMES:
#   - grad_rate_150pct is already on a 0-100 percentage scale
#   - admission_rate is on a 0-1 proportion scale (per IPEDS convention)
#   - inst_control contains only values 1 and 2 after prior cleaning
df_plot = (
    df
    .filter(
        pl.col("grad_rate_150pct").is_not_null()
        & pl.col("admission_rate").is_not_null()
    )
    .with_columns([
        # Convert admission_rate from proportion (0-1) to percentage (0-100)
        (pl.col("admission_rate") * 100).alias("admit_rate_pct"),
        # Map integer sector codes to human-readable labels for legend
        pl.col("inst_control")
          .replace_strict(SECTOR_LABELS)
          .alias("sector"),
    ])
)

# --- Post-state ---
post_rows = df_plot.shape[0]
rows_dropped = pre_rows - post_rows
print(f"\nPost-filter: {post_rows:,} rows ({rows_dropped:,} dropped due to nulls, "
      f"{rows_dropped/pre_rows*100:.1f}%)")

# Verify both sectors are represented
sectors_present = df_plot["sector"].unique().to_list()
print(f"Sectors in plot data: {sorted(sectors_present)}")
assert len(sectors_present) == 2, f"STOP: Expected 2 sectors, found {len(sectors_present)}: {sectors_present}"

# Report axis ranges for verification
admit_min = df_plot["admit_rate_pct"].min()
admit_max = df_plot["admit_rate_pct"].max()
grad_min = df_plot["grad_rate_150pct"].min()
grad_max = df_plot["grad_rate_150pct"].max()
print(f"Admission rate range: {admit_min:.1f}% - {admit_max:.1f}%")
print(f"Graduation rate range: {grad_min:.1f}% - {grad_max:.1f}%")

# Report per-sector counts
sector_counts = df_plot.group_by("sector").len().sort("sector")
for row in sector_counts.iter_rows():
    print(f"  {row[0]}: {row[1]:,} institutions")

# --- Plot ---
# INTENT: Create a scatter plot showing the relationship between admission
# rate (selectivity) and graduation rate, colored by institutional sector,
# with linear trend lines to highlight the sector-specific gradients. This
# is the primary visualization for the research question about whether
# graduation rates are driven by selectivity.
#
# REASONING: Scatter plot is appropriate because both variables are continuous,
# and we want to show the full distribution of institutions, not just averages.
# Alpha=0.5 and size=1.5 handle the ~1,500+ points without complete occlusion.
# Linear trend lines (method="lm") show the average relationship per sector,
# making it easy to compare slopes (i.e., how strongly selectivity predicts
# graduation rates in each sector).
#
# ASSUMES:
#   - admit_rate_pct is 0-100 scale (converted above)
#   - grad_rate_150pct is 0-100 scale (from source)
#   - sector column contains "Public" and "Private Nonprofit" strings
print("\nGenerating scatter plot...")

# Convert to pandas for plotnine (plotnine requires pandas DataFrames)
df_pd = df_plot.select(["admit_rate_pct", "grad_rate_150pct", "sector"]).to_pandas()

plot = (
    ggplot(df_pd, aes(x="admit_rate_pct", y="grad_rate_150pct", color="sector"))
    + geom_point(alpha=0.5, size=1.5)
    + geom_smooth(method="lm", se=True, size=1)  # Linear trend with confidence band
    + scale_color_manual(
        name="Sector",
        values=SECTOR_COLORS,
    )
    + labs(
        title="College Graduation Rate vs. Admission Rate",
        subtitle="4-Year Public and Private Nonprofit Institutions, 2020",
        x="Admission Rate (%)",
        y="Graduation Rate (150% time, %)",
        caption="Source: IPEDS 2020. Graduation rate is for first-time, full-time bachelor-seeking students.",
    )
    + theme_minimal(base_size=11)
    + theme(
        figure_size=(10, 7),
        dpi=300,
        plot_title=element_text(size=14, weight="bold"),
        plot_subtitle=element_text(size=11),
        plot_caption=element_text(size=8, color="gray"),
        legend_position="bottom",
    )
    + guides(color=guide_legend(override_aes={"size": 3, "alpha": 1}))
)

# --- Save ---
# Persist figure to output/figures/ directory in PNG format at 300 DPI.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
plot.save(OUTPUT_PATH, width=10, height=7, dpi=300, verbose=False)
print(f"Saved: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify figure was saved, file size indicates a
# real plot (not empty), and data source is correct.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION (Visualization)")
print("=" * 60)

# CP4.1: Figure file exists
fig_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if fig_exists else 'FAIL'}] Figure exists: {OUTPUT_PATH}")

# CP4.2: File size > 50KB (indicates actual plot content, not empty/corrupt)
fig_size = OUTPUT_PATH.stat().st_size if fig_exists else 0
fig_size_ok = fig_size > 50_000
print(f"  [{'PASS' if fig_size_ok else 'FAIL'}] File size: {fig_size:,} bytes (>50KB required)")

# CP4.3: Both sectors visible in data (ensures legend and color coding work)
both_sectors = len(sectors_present) == 2
print(f"  [{'PASS' if both_sectors else 'FAIL'}] Both sectors in data: {sorted(sectors_present)}")

# CP4.4: Data point count is reasonable (not degenerate)
point_count_ok = post_rows >= 100
print(f"  [{'PASS' if point_count_ok else 'FAIL'}] Data points: {post_rows:,} (>=100 required)")

# CP4.5: Axis ranges are plausible
axes_ok = (0 <= admit_min <= admit_max <= 100) and (0 <= grad_min <= grad_max <= 100)
print(f"  [{'PASS' if axes_ok else 'FAIL'}] Axis ranges plausible: "
      f"x=[{admit_min:.1f}, {admit_max:.1f}], y=[{grad_min:.1f}, {grad_max:.1f}]")

all_passed = all([fig_exists, fig_size_ok, both_sectors, point_count_ok, axes_ok])
assert all_passed, "STOP: CP4 validation failed"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:12:07
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/08_viz-scatter-grad-admit.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.2 (Step 9.1): Scatter — Graduation Rate vs. Admission Rate
# ============================================================
# Loaded: 2,528 rows x 26 cols
# Pre-state: 2,528 rows
# Nulls — grad_rate_150pct: 732 (29.0%)
# Nulls — admission_rate: 869 (34.4%)
# Nulls — inst_control: 0 (0.0%)
# 
# Post-filter: 1,573 rows (955 dropped due to nulls, 37.8%)
# Sectors in plot data: ['Private Nonprofit', 'Public']
# Admission rate range: 2.4% - 100.0%
# Graduation rate range: 3.8% - 100.0%
#   Private Nonprofit: 1,048 institutions
#   Public: 525 institutions
# 
# Generating scatter plot...
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_grad_rate_vs_admission_rate.png
# 
# ============================================================
# CHECKPOINT 4 VALIDATION (Visualization)
# ============================================================
#   [PASS] Figure exists: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_grad_rate_vs_admission_rate.png
#   [PASS] File size: 1,193,478 bytes (>50KB required)
#   [PASS] Both sectors in data: ['Private Nonprofit', 'Public']
#   [PASS] Data points: 1,573 (>=100 required)
#   [PASS] Axis ranges plausible: x=[2.4, 100.0], y=[3.8, 100.0]
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
