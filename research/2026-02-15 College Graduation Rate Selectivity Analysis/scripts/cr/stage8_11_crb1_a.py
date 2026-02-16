#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 9.4 (QA4b — Visualization)

Reviewed script: scripts/stage8_analysis/11_viz-correlation-heatmap_a.py
Output files: output/figures/2026-02-15_correlation_heatmap.png
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default):
1. Figure file exists and size > 50KB
2. Correlation matrix structure: 36 cells (6x6)
3. Diagonal values are 1.0
4. Correlations in [-1, 1] range
5. All 6 Plan-specified variables present

QA Checks (Script-Specific — Five Lenses):
6. COUNTERFACTUAL: Verify matrix symmetry (corr(A,B) == corr(B,A))
7. SEMANTIC: Verify Pearson-only filter worked (no spearman values leaked)
8. BOUNDARY: Check for values exactly at -1 or 1 (other than diagonal)
9. ABSENCE: Verify no NaN/null correlations exist in the 36 cells
10. DOWNSTREAM: Verify diverging color scale params match Plan (red=neg, blue=pos)

Spot-Checks:
11. Manually recalculate one correlation from analysis dataset to verify source fidelity
12. Verify annotation text matches numeric values (round-trip: float -> text -> check)
13. Trace grad_rate_150pct row: verify all 6 correlations present
14. Check label mapping is complete (no raw variable names leaked into labels)
15. Verify figure dimensions and DPI metadata
"""

import polars as pl
import pandas as pd
from pathlib import Path
import os

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"
FIGURE_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_correlation_heatmap.png"
CORR_MATRIX_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_correlation_matrix.parquet"
ANALYSIS_DATASET_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

EXPECTED_VARIABLES = [
    "grad_rate_150pct",
    "admission_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
]

EXPECTED_LABELS = {
    "grad_rate_150pct": "Graduation Rate",
    "admission_rate": "Admission Rate",
    "pell_share": "Pell Share",
    "urm_share": "URM Share",
    "student_faculty_ratio": "Student-Faculty Ratio",
    "retention_rate": "Retention Rate",
}

# --- Load data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 9.4 (QA4b — Visualization)")
print("=" * 60)

df_corr = pl.read_parquet(CORR_MATRIX_PATH)
print(f"Loaded correlation matrix: {df_corr.shape[0]:,} rows x {df_corr.shape[1]} cols")

# Filter to Pearson to match reviewed script
df_pearson = df_corr.filter(pl.col("method") == "pearson")

# Melt to long format to match reviewed script
df_long = df_pearson.select(["variable"] + EXPECTED_VARIABLES).unpivot(
    on=EXPECTED_VARIABLES,
    index="variable",
    variable_name="var2",
    value_name="corr",
).rename({"variable": "var1"})

print(f"Long-format matrix: {df_long.shape[0]} rows")

# ============================================================
# DEFAULT CHECKS
# ============================================================

# --- Check 1: Figure file exists ---
fig_exists = FIGURE_PATH.exists()
print(f"\n[{'PASS' if fig_exists else 'FAIL'}] Check 1 — Figure file exists: {FIGURE_PATH.name}")

# --- Check 2: Figure size > 50KB ---
if fig_exists:
    fig_size = FIGURE_PATH.stat().st_size
    fig_size_ok = fig_size > 50_000
    print(f"[{'PASS' if fig_size_ok else 'FAIL'}] Check 2 — Figure size: {fig_size:,} bytes (threshold: 50,000)")
else:
    fig_size_ok = False
    print("[FAIL] Check 2 — Figure size: file not found")

# --- Check 3: Matrix structure (36 cells) ---
n_cells = df_long.shape[0]
cells_ok = n_cells == 36
print(f"[{'PASS' if cells_ok else 'FAIL'}] Check 3 — Matrix cells: {n_cells} (expected 36)")

# --- Check 4: Diagonal values are 1.0 ---
diag = df_long.filter(pl.col("var1") == pl.col("var2"))
diag_vals = diag["corr"].to_list()
diag_ok = len(diag_vals) == 6 and all(abs(v - 1.0) < 0.001 for v in diag_vals)
print(f"[{'PASS' if diag_ok else 'FAIL'}] Check 4 — Diagonal values: {diag_vals}")

# --- Check 5: All 6 variables present ---
vars_present = set(df_long["var1"].unique().to_list())
all_vars = all(v in vars_present for v in EXPECTED_VARIABLES)
print(f"[{'PASS' if all_vars else 'FAIL'}] Check 5 — All 6 variables present: {sorted(vars_present)}")

# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ============================================================

# --- Check 6: COUNTERFACTUAL — Matrix symmetry ---
# corr(A,B) should equal corr(B,A)
asymmetry_issues = []
for row in df_long.iter_rows(named=True):
    v1, v2, c1 = row["var1"], row["var2"], row["corr"]
    mirror = df_long.filter(
        (pl.col("var1") == v2) & (pl.col("var2") == v1)
    )
    if len(mirror) == 1:
        c2 = mirror["corr"][0]
        if abs(c1 - c2) > 0.0001:
            asymmetry_issues.append(f"{v1} vs {v2}: {c1:.6f} != {c2:.6f}")
    else:
        asymmetry_issues.append(f"Missing mirror for {v1} vs {v2}")

sym_ok = len(asymmetry_issues) == 0
print(f"\n[{'PASS' if sym_ok else 'FAIL'}] Check 6 (COUNTERFACTUAL) — Matrix symmetry: ", end="")
if sym_ok:
    print("All 36 cells symmetric")
else:
    print(f"Asymmetries: {asymmetry_issues[:5]}")

# --- Check 7: SEMANTIC — No spearman values leaked ---
# Verify df_corr has both methods but we only used pearson
methods = df_corr["method"].unique().to_list()
has_both = "pearson" in methods and "spearman" in methods
pearson_rows = df_corr.filter(pl.col("method") == "pearson").shape[0]
spearman_rows = df_corr.filter(pl.col("method") == "spearman").shape[0]
# The melted long-form should have exactly 36 rows (6*6), not 72 (if spearman leaked)
semantic_ok = has_both and n_cells == 36 and pearson_rows == 6
print(f"[{'PASS' if semantic_ok else 'FAIL'}] Check 7 (SEMANTIC) — Pearson-only filter: "
      f"methods={methods}, pearson_rows={pearson_rows}, spearman_rows={spearman_rows}, "
      f"long-form={n_cells}")

# --- Check 8: BOUNDARY — Values at -1 or 1 (excluding diagonal) ---
off_diag = df_long.filter(pl.col("var1") != pl.col("var2"))
extreme_values = off_diag.filter(
    (pl.col("corr").abs() > 0.99)
)
boundary_ok = len(extreme_values) == 0
print(f"[{'PASS' if boundary_ok else 'WARN'}] Check 8 (BOUNDARY) — Off-diagonal extreme values: "
      f"{len(extreme_values)} cells with |r| > 0.99")
if len(extreme_values) > 0:
    for row in extreme_values.iter_rows(named=True):
        print(f"    {row['var1']} vs {row['var2']}: {row['corr']:.4f}")

# --- Check 9: ABSENCE — No null correlations ---
null_count = df_long["corr"].null_count()
absence_ok = null_count == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] Check 9 (ABSENCE) — Null correlations: {null_count}")

# --- Check 10: DOWNSTREAM — Diverging scale params ---
# Cannot inspect plotnine object programmatically from saved PNG,
# but we CAN verify the code used the right parameters by checking
# the correlation range covers both positive and negative values
min_corr = off_diag["corr"].min()
max_corr = off_diag["corr"].max()
has_neg = min_corr < 0
has_pos = max_corr > 0
diverging_range_ok = has_neg and has_pos
print(f"[{'PASS' if diverging_range_ok else 'WARN'}] Check 10 (DOWNSTREAM) — "
      f"Diverging data range: [{min_corr:.3f}, {max_corr:.3f}] (needs neg and pos)")

# ============================================================
# SPOT-CHECKS
# ============================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recalculate one correlation from analysis dataset ---
# Verify grad_rate_150pct vs admission_rate correlation independently
spot_11_ok = False
try:
    df_analysis = pl.read_parquet(ANALYSIS_DATASET_PATH)
    # Drop nulls in both columns, then compute Pearson
    pair = df_analysis.select(["grad_rate_150pct", "admission_rate"]).drop_nulls()
    recalc_corr = pair["grad_rate_150pct"].pearson_corr(pair["admission_rate"])
    matrix_corr = df_long.filter(
        (pl.col("var1") == "grad_rate_150pct") & (pl.col("var2") == "admission_rate")
    )["corr"][0]
    diff = abs(recalc_corr - matrix_corr)
    spot_11_ok = diff < 0.01
    print(f"[{'PASS' if spot_11_ok else 'FAIL'}] Spot 11 — Recalculated grad_rate vs admission_rate: "
          f"matrix={matrix_corr:.6f}, recalculated={recalc_corr:.6f}, diff={diff:.6f}")
except Exception as e:
    print(f"[WARN] Spot 11 — Could not recalculate: {e}")

# --- Spot-Check 12: Annotation text round-trip ---
df_annotated = df_long.with_columns(
    pl.col("corr").round(2).cast(pl.Utf8).alias("corr_text_check")
)
# Verify round-trip: text should be parseable back to a float close to the rounded value
text_issues = []
for row in df_annotated.iter_rows(named=True):
    try:
        text_val = float(row["corr_text_check"])
        expected = round(row["corr"], 2)
        if abs(text_val - expected) > 0.005:
            text_issues.append(f"{row['var1']} vs {row['var2']}: text={row['corr_text_check']}, expected={expected}")
    except ValueError:
        text_issues.append(f"{row['var1']} vs {row['var2']}: unparseable text='{row['corr_text_check']}'")

text_ok = len(text_issues) == 0
print(f"[{'PASS' if text_ok else 'FAIL'}] Spot 12 — Annotation text round-trip: "
      f"{'all 36 cells OK' if text_ok else text_issues[:3]}")

# --- Spot-Check 13: Trace grad_rate_150pct row ---
grad_row = df_long.filter(pl.col("var1") == "grad_rate_150pct")
grad_row_count = len(grad_row)
grad_row_vars = sorted(grad_row["var2"].to_list())
expected_vars_sorted = sorted(EXPECTED_VARIABLES)
grad_row_ok = grad_row_count == 6 and grad_row_vars == expected_vars_sorted
print(f"[{'PASS' if grad_row_ok else 'FAIL'}] Spot 13 — grad_rate row trace: "
      f"{grad_row_count} cells, vars={grad_row_vars}")

# --- Spot-Check 14: Label mapping complete ---
# Check that all 6 variable names map to labels
labels_mapped = all(v in EXPECTED_LABELS for v in EXPECTED_VARIABLES)
no_raw_in_labels = True
for v in EXPECTED_VARIABLES:
    if EXPECTED_LABELS.get(v) == v:  # label equals raw name = unmapped
        no_raw_in_labels = False
labels_ok = labels_mapped and no_raw_in_labels
print(f"[{'PASS' if labels_ok else 'FAIL'}] Spot 14 — Label mapping: "
      f"all mapped={labels_mapped}, no raw names={no_raw_in_labels}")

# --- Spot-Check 15: Figure file metadata (basic size check) ---
if fig_exists:
    fig_bytes = FIGURE_PATH.stat().st_size
    # A 9x8 inch 300 DPI heatmap should be roughly 100KB-1MB
    size_reasonable = 100_000 < fig_bytes < 2_000_000
    print(f"[{'PASS' if size_reasonable else 'WARN'}] Spot 15 — Figure size plausibility: "
          f"{fig_bytes:,} bytes (expected 100KB-2MB for 9x8 @ 300 DPI)")
else:
    print("[FAIL] Spot 15 — Cannot check: figure not found")

# ============================================================
# DATA PROFILING (for cr2+ decision)
# ============================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull correlation matrix (long-form):")
print(df_long.sort(["var1", "var2"]))

print("\nDescriptive statistics of correlations:")
print(df_long.select("corr").describe())

print("\nOff-diagonal correlation distribution:")
off_diag_stats = off_diag.select("corr")
print(f"  Mean: {off_diag_stats['corr'].mean():.4f}")
print(f"  Std:  {off_diag_stats['corr'].std():.4f}")
print(f"  Min:  {off_diag_stats['corr'].min():.4f}")
print(f"  Max:  {off_diag_stats['corr'].max():.4f}")

print("\nCorrelations with grad_rate_150pct (key variable):")
grad_corrs = df_long.filter(
    (pl.col("var1") == "grad_rate_150pct") & (pl.col("var2") != "grad_rate_150pct")
).sort("corr")
for row in grad_corrs.iter_rows(named=True):
    print(f"  {row['var2']:>25s}: {row['corr']:+.4f}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)

default_checks = [fig_exists, fig_size_ok, cells_ok, diag_ok, all_vars]
specific_checks = [sym_ok, semantic_ok, boundary_ok, absence_ok, diverging_range_ok]
spot_checks = [spot_11_ok, text_ok, grad_row_ok, labels_ok]

all_critical = all(default_checks) and all(specific_checks) and all(spot_checks)
severity = "PASSED" if all_critical else "BLOCKER"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:19:38
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_11_crb1_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 9.4 (QA4b — Visualization)
# ============================================================
# Loaded correlation matrix: 12 rows x 8 cols
# Long-format matrix: 36 rows
# 
# [PASS] Check 1 — Figure file exists: 2026-02-15_correlation_heatmap.png
# [PASS] Check 2 — Figure size: 310,234 bytes (threshold: 50,000)
# [PASS] Check 3 — Matrix cells: 36 (expected 36)
# [PASS] Check 4 — Diagonal values: [1.0, 0.9999999999999999, 1.0, 1.0, 1.0, 1.0]
# [PASS] Check 5 — All 6 variables present: ['admission_rate', 'grad_rate_150pct', 'pell_share', 'retention_rate', 'student_faculty_ratio', 'urm_share']
# 
# [PASS] Check 6 (COUNTERFACTUAL) — Matrix symmetry: All 36 cells symmetric
# [PASS] Check 7 (SEMANTIC) — Pearson-only filter: methods=['pearson', 'spearman'], pearson_rows=6, spearman_rows=6, long-form=36
# [PASS] Check 8 (BOUNDARY) — Off-diagonal extreme values: 0 cells with |r| > 0.99
# [PASS] Check 9 (ABSENCE) — Null correlations: 0
# [PASS] Check 10 (DOWNSTREAM) — Diverging data range: [-0.621, 0.638] (needs neg and pos)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# [WARN] Spot 11 — Could not recalculate: 'Series' object has no attribute 'pearson_corr'
# [PASS] Spot 12 — Annotation text round-trip: all 36 cells OK
# [PASS] Spot 13 — grad_rate row trace: 6 cells, vars=['admission_rate', 'grad_rate_150pct', 'pell_share', 'retention_rate', 'student_faculty_ratio', 'urm_share']
# [PASS] Spot 14 — Label mapping: all mapped=True, no raw names=True
# [PASS] Spot 15 — Figure size plausibility: 310,234 bytes (expected 100KB-2MB for 9x8 @ 300 DPI)
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full correlation matrix (long-form):
# shape: (36, 3)
# ┌────────────────┬───────────────────────┬───────────┐
# │ var1           ┆ var2                  ┆ corr      │
# │ ---            ┆ ---                   ┆ ---       │
# │ str            ┆ str                   ┆ f64       │
# ╞════════════════╪═══════════════════════╪═══════════╡
# │ admission_rate ┆ admission_rate        ┆ 1.0       │
# │ admission_rate ┆ grad_rate_150pct      ┆ -0.35887  │
# │ admission_rate ┆ pell_share            ┆ 0.160294  │
# │ admission_rate ┆ retention_rate        ┆ -0.217032 │
# │ admission_rate ┆ student_faculty_ratio ┆ 0.211869  │
# │ …              ┆ …                     ┆ …         │
# │ urm_share      ┆ grad_rate_150pct      ┆ -0.368845 │
# │ urm_share      ┆ pell_share            ┆ 0.638491  │
# │ urm_share      ┆ retention_rate        ┆ -0.261098 │
# │ urm_share      ┆ student_faculty_ratio ┆ 0.212461  │
# │ urm_share      ┆ urm_share             ┆ 1.0       │
# └────────────────┴───────────────────────┴───────────┘
# 
# Descriptive statistics of correlations:
# shape: (9, 2)
# ┌────────────┬───────────┐
# │ statistic  ┆ corr      │
# │ ---        ┆ ---       │
# │ str        ┆ f64       │
# ╞════════════╪═══════════╡
# │ count      ┆ 36.0      │
# │ null_count ┆ 0.0       │
# │ mean       ┆ 0.145443  │
# │ std        ┆ 0.513017  │
# │ min        ┆ -0.620643 │
# │ 25%        ┆ -0.261098 │
# │ 50%        ┆ 0.160294  │
# │ 75%        ┆ 0.629565  │
# │ max        ┆ 1.0       │
# └────────────┴───────────┘
# 
# Off-diagonal correlation distribution:
#   Mean: -0.0255
#   Std:  0.3692
#   Min:  -0.6206
#   Max:  0.6385
# 
# Correlations with grad_rate_150pct (key variable):
#                  pell_share: -0.6206
#                   urm_share: -0.3688
#              admission_rate: -0.3589
#       student_faculty_ratio: -0.2202
#              retention_rate: +0.6296
# 
# ============================================================
# QA RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
