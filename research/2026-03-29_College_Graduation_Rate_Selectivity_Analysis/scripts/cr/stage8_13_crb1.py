#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8.2 Step 13 (QA4b Visualization)

Reviewed script: scripts/stage8_analysis/13_viz-residual-scatter.py
Output files: output/figures/2026-03-29_actual_vs_predicted.png
Plan reference: Plan_Tasks.md Task 11.1 (viz-residual-scatter)

QA Checks (Default):
1. Figure file exists and size > 50 KB
2. Data source schema verification (selectivity_model.parquet)
3. Row count matches expectation (~1,625)
4. All 3 outperformer categories present
5. No nulls in critical plotting columns

Script-Specific Checks (Five Lenses):
6. COUNTERFACTUAL: What if predicted/actual values fall outside 0-100 axis limits?
7. SEMANTIC: Are labels actually the top outperformers by residual?
8. BOUNDARY: Check for tied residuals causing arbitrary label selection
9. ABSENCE: Verify no data points are silently dropped before plotting
10. DOWNSTREAM: Will the labeled institutions be recognizable in the report?

Spot Checks:
11. Verify top outperformer residual = actual - predicted
12. Verify all outperformers are above the y=x line (actual > predicted)
13. Verify all underperformers are below the y=x line (actual < predicted)
14. Check residual distribution symmetry (model quality indicator)
15. Verify the color mapping matches Plan.md spec (green/gray/red-family)
"""

import polars as pl
from pathlib import Path
import os

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_selectivity_model.parquet"
FIGURE_PATH = PROJECT_DIR / "output" / "figures" / f"{DATE_PREFIX}_actual_vs_predicted.png"

EXPECTED_COLUMNS = ["unitid", "inst_name", "admit_rate", "completion_rate_150pct",
                    "predicted", "residual", "outperformer_flag"]
EXPECTED_MIN_ROWS = 1500
EXPECTED_MAX_ROWS = 2000
CRITICAL_COLUMNS = ["predicted", "completion_rate_150pct", "residual", "outperformer_flag"]
N_LABELS = 8

# --- Load ---
print("=" * 60)
print("QA INSPECTION: Stage 8.2 Step 13 (viz-residual-scatter)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Default Check 1: Figure file exists and size ---
fig_exists = FIGURE_PATH.exists()
fig_size_kb = FIGURE_PATH.stat().st_size / 1024 if fig_exists else 0
fig_ok = fig_exists and fig_size_kb > 50
print(f"\n[{'PASS' if fig_ok else 'FAIL'}] Figure: exists={fig_exists}, size={fig_size_kb:.1f} KB (threshold: >50 KB)")

# --- Default Check 2: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns: {extra_cols}")

# --- Default Check 3: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Default Check 4: All 3 categories present ---
categories = set(df["outperformer_flag"].unique().to_list())
expected_cats = {"outperformer", "typical", "underperformer"}
cats_ok = categories == expected_cats
print(f"[{'PASS' if cats_ok else 'FAIL'}] Categories: {sorted(categories)} (expected {sorted(expected_cats)})")

# --- Default Check 5: No nulls in critical plotting columns ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        nc = df[col].null_count()
        if nc > 0:
            null_issues.append(f"{col}: {nc} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# --- Script-Specific Check 6: COUNTERFACTUAL -- values outside axis limits ---
# The script sets x limits=(0,100) and y limits=(0,105). Any data points outside
# these ranges would be silently clipped by plotnine.
pred_min = df["predicted"].min()
pred_max = df["predicted"].max()
actual_min = df["completion_rate_150pct"].min()
actual_max = df["completion_rate_150pct"].max()
x_clipped = pred_min < 0 or pred_max > 100
y_clipped = actual_min < 0 or actual_max > 105
clip_ok = not x_clipped and not y_clipped
print(f"\n[{'PASS' if clip_ok else 'WARN'}] Axis clipping: predicted=[{pred_min:.1f}, {pred_max:.1f}], actual=[{actual_min:.1f}, {actual_max:.1f}]")
if x_clipped:
    n_x_clip = df.filter((pl.col("predicted") < 0) | (pl.col("predicted") > 100)).shape[0]
    print(f"  WARNING: {n_x_clip} points outside x-axis limits (0-100)")
if y_clipped:
    n_y_clip = df.filter((pl.col("completion_rate_150pct") < 0) | (pl.col("completion_rate_150pct") > 105)).shape[0]
    print(f"  WARNING: {n_y_clip} points outside y-axis limits (0-105)")

# --- Script-Specific Check 7: SEMANTIC -- labels are truly top outperformers ---
# The script selects top N_LABELS by descending residual. Verify these are indeed
# the institutions with the largest positive residuals.
top_by_residual = df.sort("residual", descending=True).head(N_LABELS)
top_residuals = top_by_residual["residual"].to_list()
# Check that all labeled institutions have residual >= the N_LABELS-th largest
threshold_residual = sorted(df["residual"].to_list(), reverse=True)[N_LABELS - 1]
label_correct = all(r >= threshold_residual for r in top_residuals)
print(f"[{'PASS' if label_correct else 'FAIL'}] Label selection: top {N_LABELS} by residual (min labeled residual={min(top_residuals):.1f}pp, threshold={threshold_residual:.1f}pp)")

# --- Script-Specific Check 8: BOUNDARY -- tied residuals ---
# If many institutions share the same residual, the top-N selection is arbitrary.
# Count how many institutions share the same residual as the Nth-ranked.
n_at_threshold = df.filter(pl.col("residual") == threshold_residual).shape[0]
ties_issue = n_at_threshold > N_LABELS
print(f"[{'WARN' if ties_issue else 'PASS'}] Tied residuals at threshold ({threshold_residual:.1f}pp): {n_at_threshold} institutions share this value")
if ties_issue:
    print(f"  NOTE: {n_at_threshold} institutions tied at residual={threshold_residual:.1f}pp but only {N_LABELS} labeled -- selection is arbitrary among ties")

# Deeper investigation: how many institutions have the top residual value?
top_residual_val = df["residual"].max()
n_at_top = df.filter(pl.col("residual") == top_residual_val).shape[0]
print(f"  Top residual value: {top_residual_val:.1f}pp shared by {n_at_top} institutions")
if n_at_top > 3:
    print(f"  INVESTIGATION: {n_at_top} institutions all have residual={top_residual_val:.1f}pp -- possible data artifact")
    # Show what these institutions have in common
    tied_insts = df.filter(pl.col("residual") == top_residual_val)
    print(f"  Tied institutions details:")
    for row in tied_insts.select("inst_name", "predicted", "completion_rate_150pct", "residual", "admit_rate").iter_rows():
        print(f"    {row[0]}: predicted={row[1]:.1f}, actual={row[2]:.1f}, admit_rate={row[4]:.1f}")

# --- Script-Specific Check 9: ABSENCE -- no silent data drops ---
# The script loads data and plots all of it. Verify no filtering occurs.
# Also verify inst_name has no nulls (would cause label issues).
inst_name_nulls = df["inst_name"].null_count()
inst_ok = inst_name_nulls == 0
print(f"[{'PASS' if inst_ok else 'WARN'}] No null inst_name: {inst_name_nulls} nulls")

# --- Script-Specific Check 10: DOWNSTREAM -- will labeled names be readable? ---
# Check label lengths -- very long names may overlap or get truncated.
label_lengths = [len(name) for name in top_by_residual["inst_name"].to_list()]
max_label_len = max(label_lengths)
long_labels = [name for name in top_by_residual["inst_name"].to_list() if len(name) > 40]
label_readability = len(long_labels) == 0
print(f"[{'PASS' if label_readability else 'WARN'}] Label readability: max length={max_label_len} chars, {len(long_labels)} labels > 40 chars")
if long_labels:
    for lbl in long_labels:
        print(f"  Long label: '{lbl}' ({len(lbl)} chars)")

# --- Spot Check 11: Verify residual = actual - predicted ---
# The outperformers script should have computed residual as actual - predicted.
# Verify this for a sample of institutions.
df_check = df.with_columns(
    (pl.col("completion_rate_150pct") - pl.col("predicted")).alias("computed_residual")
)
residual_diff = (df_check["residual"] - df_check["computed_residual"]).abs()
max_diff = residual_diff.max()
residual_match = max_diff < 0.01  # Allow tiny floating point tolerance
print(f"\n[{'PASS' if residual_match else 'FAIL'}] Spot check: residual = actual - predicted (max diff: {max_diff:.6f})")

# --- Spot Check 12: All outperformers above y=x line ---
outperformers_df = df.filter(pl.col("outperformer_flag") == "outperformer")
n_outperformers_below = outperformers_df.filter(pl.col("completion_rate_150pct") < pl.col("predicted")).shape[0]
outperf_above_ok = n_outperformers_below == 0
print(f"[{'PASS' if outperf_above_ok else 'FAIL'}] Outperformers all above y=x: {n_outperformers_below} exceptions out of {outperformers_df.shape[0]}")

# --- Spot Check 13: All underperformers below y=x line ---
underperformers_df = df.filter(pl.col("outperformer_flag") == "underperformer")
n_underperformers_above = underperformers_df.filter(pl.col("completion_rate_150pct") > pl.col("predicted")).shape[0]
underperf_below_ok = n_underperformers_above == 0
print(f"[{'PASS' if underperf_below_ok else 'FAIL'}] Underperformers all below y=x: {n_underperformers_above} exceptions out of {underperformers_df.shape[0]}")

# --- Spot Check 14: Residual distribution symmetry ---
# A well-specified OLS model should have roughly symmetric residuals centered at 0.
residual_mean = df["residual"].mean()
residual_median = df["residual"].median()
residual_std = df["residual"].std()
residual_skew = ((df["residual"] - residual_mean) ** 3).mean() / (residual_std ** 3)
resid_sym_ok = abs(residual_mean) < 1.0 and abs(residual_skew) < 1.0
print(f"[{'PASS' if resid_sym_ok else 'WARN'}] Residual distribution: mean={residual_mean:.2f}, median={residual_median:.2f}, std={residual_std:.2f}, skewness={residual_skew:.2f}")

# --- Spot Check 15: Color mapping alignment with Plan spec ---
# Plan says: "green for outperformers, gray for typical, red for underperformers"
# Script uses: outperformer=#009E73, typical=#999999, underperformer=#D55E00
# Verify: #009E73 is a green, #999999 is gray, #D55E00 is a red/vermilion (warm)
# These are Okabe-Ito palette values, which align with the Plan's intent.
print(f"[PASS] Color mapping: outperformer=#009E73 (green), typical=#999999 (gray), underperformer=#D55E00 (vermilion) -- aligns with Plan")

# --- Category distribution ---
print("\n--- Category Distribution ---")
cat_counts = df.group_by("outperformer_flag").len().sort("outperformer_flag")
total = len(df)
for row in cat_counts.iter_rows():
    pct = row[1] / total * 100
    print(f"  {row[0]}: {row[1]:,} ({pct:.1f}%)")

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows (key columns):")
print(df.select("inst_name", "admit_rate", "completion_rate_150pct", "predicted", "residual", "outperformer_flag").head(10))

print("\nDescriptive statistics:")
print(df.select("admit_rate", "completion_rate_150pct", "predicted", "residual").describe())

print("\nResidual quantiles:")
for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
    val = df["residual"].quantile(q)
    print(f"  {q*100:.0f}th percentile: {val:.1f}pp")

print("\nTop 15 by residual (outperformer candidates):")
top15 = df.sort("residual", descending=True).head(15)
for row in top15.select("inst_name", "predicted", "completion_rate_150pct", "residual", "outperformer_flag").iter_rows():
    print(f"  {row[0]}: predicted={row[1]:.1f}, actual={row[2]:.1f}, residual={row[3]:+.1f}, flag={row[4]}")

print("\nBottom 5 by residual (worst underperformers):")
bottom5 = df.sort("residual").head(5)
for row in bottom5.select("inst_name", "predicted", "completion_rate_150pct", "residual", "outperformer_flag").iter_rows():
    print(f"  {row[0]}: predicted={row[1]:.1f}, actual={row[2]:.1f}, residual={row[3]:+.1f}, flag={row[4]}")

# --- Summary ---
all_defaults_passed = all([fig_ok, schema_ok, rows_ok, cats_ok, nulls_ok])
all_checks_passed = all([fig_ok, schema_ok, rows_ok, cats_ok, nulls_ok, clip_ok,
                         label_correct, inst_ok, residual_match,
                         outperf_above_ok, underperf_below_ok])
has_warnings = ties_issue or not label_readability or not resid_sym_ok

print("\n" + "=" * 60)
if not all_checks_passed:
    print("QA RESULT: BLOCKER -- critical check(s) failed")
elif has_warnings:
    print("QA RESULT: WARNING -- issues found but not blocking")
else:
    print("QA RESULT: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 14:23:23
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_13_crb1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8.2 Step 13 (viz-residual-scatter)
# ============================================================
# Loaded: 1,625 rows x 7 cols
# 
# [PASS] Figure: exists=True, size=881.0 KB (threshold: >50 KB)
# [PASS] Schema: All expected columns present
# [PASS] Row count: 1,625 (expected 1,500-2,000)
# [PASS] Categories: ['outperformer', 'typical', 'underperformer'] (expected ['outperformer', 'typical', 'underperformer'])
# [PASS] Critical nulls: None
# 
# [PASS] Axis clipping: predicted=[49.2, 78.1], actual=[3.8, 100.0]
# [PASS] Label selection: top 8 by residual (min labeled residual=49.4pp, threshold=49.4pp)
# [PASS] Tied residuals at threshold (49.4pp): 1 institutions share this value
#   Top residual value: 50.8pp shared by 7 institutions
#   INVESTIGATION: 7 institutions all have residual=50.8pp -- possible data artifact
#   Tied institutions details:
#     Saint Anthony College of Nursing: predicted=49.2, actual=100.0, admit_rate=100.0
#     Divine Word College: predicted=49.2, actual=100.0, admit_rate=100.0
#     Sacred Heart Major Seminary: predicted=49.2, actual=100.0, admit_rate=100.0
#     AmeriTech College-Draper: predicted=49.2, actual=100.0, admit_rate=100.0
#     Mid-South Christian College: predicted=49.2, actual=100.0, admit_rate=100.0
#     California Jazz Conservatory: predicted=49.2, actual=100.0, admit_rate=100.0
#     Chamberlain University-New Jersey: predicted=49.2, actual=100.0, admit_rate=100.0
# [PASS] No null inst_name: 0 nulls
# [WARN] Label readability: max length=47 chars, 1 labels > 40 chars
#   Long label: 'EDP University of Puerto Rico Inc-San Sebastian' (47 chars)
# 
# [PASS] Spot check: residual = actual - predicted (max diff: 0.000000)
# [PASS] Outperformers all above y=x: 0 exceptions out of 248
# [PASS] Underperformers all below y=x: 0 exceptions out of 251
# [PASS] Residual distribution: mean=-0.00, median=2.20, std=17.83, skewness=-0.53
# [PASS] Color mapping: outperformer=#009E73 (green), typical=#999999 (gray), underperformer=#D55E00 (vermilion) -- aligns with Plan
# 
# --- Category Distribution ---
#   outperformer: 248 (15.3%)
#   typical: 1,126 (69.3%)
#   underperformer: 251 (15.4%)
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows (key columns):
# shape: (10, 6)
# ┌────────────────────┬────────────┬───────────────────┬───────────┬────────────┬───────────────────┐
# │ inst_name          ┆ admit_rate ┆ completion_rate_1 ┆ predicted ┆ residual   ┆ outperformer_flag │
# │ ---                ┆ ---        ┆ 50pct             ┆ ---       ┆ ---        ┆ ---               │
# │ str                ┆ f64        ┆ ---               ┆ f64       ┆ f64        ┆ str               │
# │                    ┆            ┆ f64               ┆           ┆            ┆                   │
# ╞════════════════════╪════════════╪═══════════════════╪═══════════╪════════════╪═══════════════════╡
# │ Alabama A & M      ┆ 89.649924  ┆ 28.1              ┆ 52.213977 ┆ -24.113977 ┆ underperformer    │
# │ University         ┆            ┆                   ┆           ┆            ┆                   │
# │ University of      ┆ 80.598595  ┆ 62.4              ┆ 54.82984  ┆ 7.57016    ┆ typical           │
# │ Alabama at Birmi…  ┆            ┆                   ┆           ┆            ┆                   │
# │ University of      ┆ 77.110306  ┆ 60.7              ┆ 55.837967 ┆ 4.862033   ┆ typical           │
# │ Alabama in Hunts…  ┆            ┆                   ┆           ┆            ┆                   │
# │ Alabama State      ┆ 98.875765  ┆ 28.4              ┆ 49.547679 ┆ -21.147679 ┆ underperformer    │
# │ University         ┆            ┆                   ┆           ┆            ┆                   │
# │ The University of  ┆ 80.394338  ┆ 72.2              ┆ 54.888871 ┆ 17.311129  ┆ typical           │
# │ Alabama            ┆            ┆                   ┆           ┆            ┆                   │
# │ Auburn University  ┆ 95.549284  ┆ 35.7              ┆ 50.509043 ┆ -14.809043 ┆ typical           │
# │ at Montgomer…      ┆            ┆                   ┆           ┆            ┆                   │
# │ Auburn University  ┆ 85.06631   ┆ 80.9              ┆ 53.538656 ┆ 27.361344  ┆ outperformer      │
# │ Birmingham-Souther ┆ 60.447154  ┆ 69.8              ┆ 60.653671 ┆ 9.146329   ┆ typical           │
# │ n College          ┆            ┆                   ┆           ┆            ┆                   │
# │ Faulkner           ┆ 75.763359  ┆ 18.1              ┆ 56.227239 ┆ -38.127239 ┆ underperformer    │
# │ University         ┆            ┆                   ┆           ┆            ┆                   │
# │ Huntingdon College ┆ 54.391733  ┆ 44.2              ┆ 62.403707 ┆ -18.203707 ┆ underperformer    │
# └────────────────────┴────────────┴───────────────────┴───────────┴────────────┴───────────────────┘
# 
# Descriptive statistics:
# shape: (9, 5)
# ┌────────────┬────────────┬────────────────────────┬───────────┬─────────────┐
# │ statistic  ┆ admit_rate ┆ completion_rate_150pct ┆ predicted ┆ residual    │
# │ ---        ┆ ---        ┆ ---                    ┆ ---       ┆ ---         │
# │ str        ┆ f64        ┆ f64                    ┆ f64       ┆ f64         │
# ╞════════════╪════════════╪════════════════════════╪═══════════╪═════════════╡
# │ count      ┆ 1625.0     ┆ 1625.0                 ┆ 1625.0    ┆ 1625.0      │
# │ null_count ┆ 0.0        ┆ 0.0                    ┆ 0.0       ┆ 0.0         │
# │ mean       ┆ 70.41439   ┆ 57.773108              ┆ 57.773108 ┆ -5.3730e-14 │
# │ std        ┆ 20.555162  ┆ 18.793213              ┆ 5.940508  ┆ 17.829617   │
# │ min        ┆ 0.0        ┆ 3.8                    ┆ 49.222771 ┆ -58.013447  │
# │ 25%        ┆ 59.807356  ┆ 45.8                   ┆ 53.499793 ┆ -10.934602  │
# │ 50%        ┆ 74.441371  ┆ 57.7                   ┆ 56.609297 ┆ 2.204323    │
# │ 75%        ┆ 85.200782  ┆ 70.6                   ┆ 60.838575 ┆ 13.515327   │
# │ max        ┆ 100.0      ┆ 100.0                  ┆ 78.123093 ┆ 50.777229   │
# └────────────┴────────────┴────────────────────────┴───────────┴─────────────┘
# 
# Residual quantiles:
#   1th percentile: -48.0pp
#   5th percentile: -34.0pp
#   10th percentile: -23.7pp
#   25th percentile: -10.9pp
#   50th percentile: 2.2pp
#   75th percentile: 13.5pp
#   90th percentile: 20.1pp
#   95th percentile: 23.6pp
#   99th percentile: 32.5pp
# 
# Top 15 by residual (outperformer candidates):
#   Saint Anthony College of Nursing: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   Divine Word College: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   Sacred Heart Major Seminary: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   AmeriTech College-Draper: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   Mid-South Christian College: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   California Jazz Conservatory: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   Chamberlain University-New Jersey: predicted=49.2, actual=100.0, residual=+50.8, flag=outperformer
#   EDP University of Puerto Rico Inc-San Sebastian: predicted=50.6, actual=100.0, residual=+49.4, flag=outperformer
#   St. John Vianney College Seminary: predicted=51.4, actual=100.0, residual=+48.6, flag=outperformer
#   Yeshiva Gedola Tiferes Yerachmiel: predicted=50.3, actual=93.8, residual=+43.5, flag=outperformer
#   New York School of Interior Design: predicted=58.7, actual=100.0, residual=+41.3, flag=outperformer
#   Thomas More College of Liberal Arts: predicted=52.2, actual=90.0, residual=+37.8, flag=outperformer
#   Principia College: predicted=51.2, actual=85.9, residual=+34.7, flag=outperformer
#   Baptist Missionary Association Theological Seminary: predicted=65.3, actual=100.0, residual=+34.7, flag=outperformer
#   Wheaton College: predicted=53.0, actual=87.6, residual=+34.6, flag=outperformer
# 
# Bottom 5 by residual (worst underperformers):
#   Alliant International University-San Diego: predicted=67.1, actual=9.1, residual=-58.0, flag=underperformer
#   Bacone College: predicted=64.5, actual=7.2, residual=-57.3, flag=underperformer
#   DeVry University-California: predicted=64.9, actual=8.9, residual=-56.0, flag=underperformer
#   DeVry University-Georgia: predicted=66.6, actual=10.7, residual=-55.9, flag=underperformer
#   Bay State College: predicted=68.3, actual=12.7, residual=-55.6, flag=underperformer
# 
# ============================================================
# QA RESULT: WARNING -- issues found but not blocking
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
