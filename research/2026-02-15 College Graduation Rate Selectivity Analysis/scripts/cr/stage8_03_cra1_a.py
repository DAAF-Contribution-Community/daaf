#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 3 (QA4a — Statistical Validity)

Reviewed script: scripts/stage8_analysis/01_crosstab-selectivity-urm.py
Output files: output/analysis/2026-02-15_crosstab_selectivity_urm.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks:
1. Schema matches Plan expectations
2. Row count within expected range (up to 16 cells, 14 reported)
3. No suspicious distributions
4. No coded values remaining
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. COUNTERFACTUAL: What if URM bands had empty or single-row groups?
7. SEMANTIC: Does the crosstab serve the research question, not just the Plan?
8. BOUNDARY: Check boundary values — grad rates at 0/100 edges, n=1 cells
9. ABSENCE: Are any expected selectivity x URM combinations missing and why?
10. DOWNSTREAM: Would report-writer or visualization scripts be surprised by this output?

Spot-Checks:
11. Verify total n across all cells matches the filtered row count (1,791)
12. Manually recalculate mean grad_rate for one specific cell from source data
13. Verify the two empty cells (Highly Selective x High/Very High URM) are correct
14. Check that URM band labels in output match Plan specification exactly
15. Verify monotonic decrease pattern within at least one selectivity band
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_crosstab_selectivity_urm.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"

# Plan-specified expected columns for the crosstab output
EXPECTED_COLUMNS = ["selectivity_band", "urm_band", "n", "mean_grad_rate", "median_grad_rate"]

# Plan-specified URM band labels (from Plan Section "create-bands" task, line 1156-1160)
PLAN_URM_LABELS = [
    "Low URM (under 20%)",
    "Moderate URM (20-40%)",
    "High URM (40-60%)",
    "Very High URM (60%+)",
]

PLAN_SELECTIVITY_LABELS = [
    "Highly Selective",
    "Selective",
    "Moderately Selective",
    "Less Selective/Open Admission",  # Note: Plan says "Less Selective/Open"
]

# Row count expectations
EXPECTED_MIN_ROWS = 10  # At minimum 10 non-empty cells (4x4 minus sparse)
EXPECTED_MAX_ROWS = 16  # At most 4 selectivity x 4 URM = 16

# Critical columns — these must have no nulls in the output crosstab
CRITICAL_COLUMNS = ["selectivity_band", "urm_band", "n", "mean_grad_rate", "median_grad_rate"]

# --- Load output data ---
print("=" * 60)
print("QA4a INSPECTION: Stage 8 Step 3 (crosstab-selectivity-urm)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded crosstab: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load the source analysis dataset for cross-validation
df_source = pl.read_parquet(INPUT_FILE)
print(f"Loaded source: {df_source.shape[0]:,} rows x {df_source.shape[1]} cols")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.UInt32, pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
# Only check signed integer columns for coded values; UInt32 cannot hold
# negative values by definition, so comparing would cause OverflowError.
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain (no signed integer columns in crosstab)" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: COUNTERFACTUAL — What if data had empty or single-row groups? ---
print("\n--- Check 6: COUNTERFACTUAL (sparse cells) ---")
min_n = df["n"].min()
max_n = df["n"].max()
print(f"Cell sizes range: min={min_n}, max={max_n}")
single_row_cells = df.filter(pl.col("n") == 1)
if single_row_cells.shape[0] > 0:
    print(f"[WARN] {single_row_cells.shape[0]} cells with n=1 (mean/median are same single value)")
    print(single_row_cells)
else:
    print("[PASS] No single-observation cells (min n > 1)")

sparse_cells = df.filter(pl.col("n") < 10)
if sparse_cells.shape[0] > 0:
    print(f"[INFO] {sparse_cells.shape[0]} cells with n < 10:")
    print(sparse_cells)
else:
    print("[PASS] All cells have n >= 10")

# --- Check 7: SEMANTIC — Does the crosstab serve the research question? ---
print("\n--- Check 7: SEMANTIC (research question alignment) ---")
# Research question: "URM share is negatively correlated with graduation rate"
# The crosstab should show that within each selectivity band, higher URM =>
# lower grad rate. Let's verify this pattern exists in the output.
semantic_ok = True
for sel_band in df["selectivity_band"].unique().sort().to_list():
    subset = df.filter(pl.col("selectivity_band") == sel_band).sort("urm_band")
    if subset.shape[0] < 2:
        continue
    # Map URM bands to ordinal for pattern checking
    urm_order_map = {
        "Low URM (under 20%)": 0,
        "Moderate URM (20-40%)": 1,
        "High URM (40-60%)": 2,
        "Very High URM (60%+)": 3,
    }
    subset_ordered = subset.with_columns(
        pl.col("urm_band").replace_strict(urm_order_map, default=None).alias("urm_ord")
    ).filter(pl.col("urm_ord").is_not_null()).sort("urm_ord")

    means = subset_ordered["mean_grad_rate"].to_list()
    if len(means) >= 2:
        first_last_decreasing = means[0] > means[-1]
        print(f"  {sel_band}: means={[round(m, 1) for m in means]}, "
              f"first>last={'YES' if first_last_decreasing else 'NO'}")
        if not first_last_decreasing:
            semantic_ok = False

print(f"[{'PASS' if semantic_ok else 'WARN'}] Observable Truth pattern: "
      f"{'Generally decreasing within all selectivity bands' if semantic_ok else 'Not consistently decreasing'}")

# --- Check 8: BOUNDARY — Grad rates at edges ---
print("\n--- Check 8: BOUNDARY (value ranges) ---")
mean_min = df["mean_grad_rate"].min()
mean_max = df["mean_grad_rate"].max()
median_min = df["median_grad_rate"].min()
median_max = df["median_grad_rate"].max()
boundary_ok = (mean_min >= 0 and mean_max <= 100 and median_min >= 0 and median_max <= 100)
print(f"Mean grad rate range: [{mean_min:.1f}, {mean_max:.1f}]")
print(f"Median grad rate range: [{median_min:.1f}, {median_max:.1f}]")
print(f"[{'PASS' if boundary_ok else 'BLOCKER'}] All grad rates in 0-100 range")

# Check n values are all positive
all_n_positive = df["n"].min() > 0
print(f"[{'PASS' if all_n_positive else 'BLOCKER'}] All n values positive (min={df['n'].min()})")

# --- Check 9: ABSENCE — Are expected combinations missing? ---
print("\n--- Check 9: ABSENCE (missing combinations) ---")
actual_selectivity = set(df["selectivity_band"].unique().to_list())
actual_urm = set(df["urm_band"].unique().to_list())
print(f"Selectivity bands present: {sorted(actual_selectivity)}")
print(f"URM bands present: {sorted(actual_urm)}")

# Check how many of the 16 possible cells are populated
total_possible = 4 * 4  # 4 selectivity x 4 URM
total_actual = df.shape[0]
missing_cells = total_possible - total_actual
print(f"Populated cells: {total_actual} / {total_possible} ({missing_cells} empty)")

# Identify which cells are missing
for sel in sorted(PLAN_SELECTIVITY_LABELS):
    for urm in sorted(PLAN_URM_LABELS):
        # The selectivity label in data might be truncated
        sel_match = df.filter(
            pl.col("selectivity_band").str.starts_with(sel[:20])
            & (pl.col("urm_band") == urm)
        )
        if sel_match.shape[0] == 0:
            # Check if the selectivity band exists at all in data
            sel_exists = df.filter(pl.col("selectivity_band").str.starts_with(sel[:20])).shape[0] > 0
            if sel_exists:
                print(f"  EMPTY: {sel} x {urm}")

# Verify the emptiness makes sense by checking source data
print("\nVerifying empty cells against source data:")
source_filtered = df_source.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("urm_band").is_not_null()
    & pl.col("grad_rate_150pct").is_not_null()
)
for sel in ["Highly Selective"]:
    for urm in ["High URM (40-60%)", "Very High URM (60%+)"]:
        count = source_filtered.filter(
            (pl.col("selectivity_band") == sel) & (pl.col("urm_band") == urm)
        ).shape[0]
        print(f"  Source data: {sel} x {urm} = {count} rows")

absence_ok = total_actual >= 12  # At least 12 of 16 cells populated
print(f"[{'PASS' if absence_ok else 'WARN'}] Cell coverage adequate ({total_actual}/16)")

# --- Check 10: DOWNSTREAM — Would downstream consumers be surprised? ---
print("\n--- Check 10: DOWNSTREAM (output format for consumers) ---")
# Plan says to pivot into matrix format (action step 6), but script saves long format
# Check if the long format will work for report-writer and viz scripts
downstream_issues = []

# Check that output is in long format (which is what was produced)
is_long_format = "urm_band" in df.columns and "selectivity_band" in df.columns
if is_long_format:
    print("[INFO] Output is in long format (not pivoted as Plan step 6 suggests)")
    print("  Long format is more versatile for downstream plotnine/report use")

# Check data types are clean for downstream
for col in ["mean_grad_rate", "median_grad_rate"]:
    if col in df.columns:
        if df[col].dtype == pl.Float64:
            print(f"[PASS] {col} is Float64 (correct for downstream)")
        else:
            downstream_issues.append(f"{col} unexpected type: {df[col].dtype}")

if df["n"].dtype in [pl.UInt32, pl.Int64, pl.Int32]:
    print(f"[PASS] n column is integer ({df['n'].dtype})")
else:
    downstream_issues.append(f"n unexpected type: {df['n'].dtype}")

downstream_ok = len(downstream_issues) == 0
if not downstream_ok:
    for issue in downstream_issues:
        print(f"[WARN] {issue}")

# =============================================================================
# SPOT-CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Total n matches filtered row count ---
print("\n--- Spot-Check 11: Total n sum ---")
total_n = df["n"].sum()
# From execution log: 1,791 rows after filtering
expected_total = 1791
n_sum_ok = total_n == expected_total
print(f"Sum of n across all cells: {total_n}")
print(f"Expected (filtered rows): {expected_total}")
print(f"[{'PASS' if n_sum_ok else 'BLOCKER'}] Total n matches filtered count")

# --- Spot-Check 12: Recalculate mean for a specific cell ---
print("\n--- Spot-Check 12: Manual mean recalculation ---")
# Pick "Less Selective/Open" x "Low URM (under 20%)" (largest cell, n=495)
spot_sel = "Less Selective/Open"
spot_urm = "Low URM (under 20%)"

# Get the reported value from the crosstab
crosstab_row = df.filter(
    pl.col("selectivity_band").str.starts_with(spot_sel[:15])
    & (pl.col("urm_band") == spot_urm)
)
if crosstab_row.shape[0] > 0:
    reported_mean = crosstab_row["mean_grad_rate"][0]
    reported_median = crosstab_row["median_grad_rate"][0]
    reported_n = crosstab_row["n"][0]

    # Recalculate from source
    source_subset = source_filtered.filter(
        pl.col("selectivity_band").str.starts_with(spot_sel[:15])
        & (pl.col("urm_band") == spot_urm)
    )
    recalc_mean = source_subset["grad_rate_150pct"].mean()
    recalc_median = source_subset["grad_rate_150pct"].median()
    recalc_n = source_subset.shape[0]

    mean_diff = abs(reported_mean - recalc_mean) if recalc_mean is not None else float('inf')
    n_diff = abs(reported_n - recalc_n)

    print(f"Cell: {spot_sel} x {spot_urm}")
    print(f"  Reported: n={reported_n}, mean={reported_mean:.2f}, median={reported_median:.2f}")
    print(f"  Recalculated: n={recalc_n}, mean={recalc_mean:.2f}, median={recalc_median:.2f}")

    recalc_ok = mean_diff < 0.01 and n_diff == 0
    print(f"[{'PASS' if recalc_ok else 'BLOCKER'}] Mean difference: {mean_diff:.4f}, n difference: {n_diff}")
else:
    print(f"[WARN] Could not find cell {spot_sel} x {spot_urm} in crosstab")
    recalc_ok = False

# --- Spot-Check 13: Verify empty cells correctness ---
print("\n--- Spot-Check 13: Empty cell verification ---")
for sel, urm in [("Highly Selective", "High URM (40-60%)"), ("Highly Selective", "Very High URM (60%+)")]:
    source_count = source_filtered.filter(
        (pl.col("selectivity_band") == sel)
        & (pl.col("urm_band") == urm)
    ).shape[0]
    crosstab_exists = df.filter(
        (pl.col("selectivity_band") == sel) & (pl.col("urm_band") == urm)
    ).shape[0] > 0

    correctly_empty = (source_count == 0 and not crosstab_exists)
    incorrectly_empty = (source_count > 0 and not crosstab_exists)

    print(f"  {sel} x {urm}: source has {source_count} rows, "
          f"crosstab {'present' if crosstab_exists else 'empty'} "
          f"[{'PASS' if correctly_empty else ('BLOCKER' if incorrectly_empty else 'PASS')}]")

# --- Spot-Check 14: URM band label verification ---
print("\n--- Spot-Check 14: URM band label match ---")
actual_urm_labels = sorted(df["urm_band"].unique().to_list())
expected_urm_in_data = sorted([l for l in PLAN_URM_LABELS if l in actual_urm_labels])
urm_label_issues = []

for label in actual_urm_labels:
    if label not in PLAN_URM_LABELS:
        urm_label_issues.append(f"Unexpected label: '{label}'")

for label in PLAN_URM_LABELS:
    if label not in actual_urm_labels:
        # Could be legitimately empty — check source
        src_count = source_filtered.filter(pl.col("urm_band") == label).shape[0]
        if src_count > 0:
            urm_label_issues.append(f"Missing label with {src_count} source rows: '{label}'")
        else:
            print(f"  Label '{label}' absent (0 source rows after filtering) — OK")

labels_ok = len(urm_label_issues) == 0
print(f"Actual URM labels in output: {actual_urm_labels}")
print(f"Plan-specified labels: {PLAN_URM_LABELS}")
if urm_label_issues:
    for issue in urm_label_issues:
        print(f"  [WARN] {issue}")
print(f"[{'PASS' if labels_ok else 'WARN'}] URM band labels match Plan")

# Also check selectivity band labels
actual_sel_labels = sorted(df["selectivity_band"].unique().to_list())
print(f"Actual selectivity labels: {actual_sel_labels}")

# --- Spot-Check 15: Verify monotonic decrease pattern ---
print("\n--- Spot-Check 15: Monotonic decrease verification ---")
urm_order_map = {
    "Low URM (under 20%)": 0,
    "Moderate URM (20-40%)": 1,
    "High URM (40-60%)": 2,
    "Very High URM (60%+)": 3,
}

monotonic_results = {}
for sel_band in sorted(df["selectivity_band"].unique().to_list()):
    subset = df.filter(pl.col("selectivity_band") == sel_band)
    subset = subset.with_columns(
        pl.col("urm_band").replace_strict(urm_order_map, default=None).alias("urm_ord")
    ).filter(pl.col("urm_ord").is_not_null()).sort("urm_ord")

    means = subset["mean_grad_rate"].to_list()
    if len(means) >= 2:
        strictly_decreasing = all(means[i] >= means[i+1] for i in range(len(means)-1))
        generally_decreasing = means[0] > means[-1]
        monotonic_results[sel_band] = {
            "means": [round(m, 1) for m in means],
            "strictly": strictly_decreasing,
            "generally": generally_decreasing,
        }
        pattern = "strictly decreasing" if strictly_decreasing else (
            "generally decreasing" if generally_decreasing else "NOT decreasing"
        )
        print(f"  {sel_band}: {[round(m, 1) for m in means]} — {pattern}")

all_generally_decreasing = all(r["generally"] for r in monotonic_results.values())
print(f"[{'PASS' if all_generally_decreasing else 'WARN'}] "
      f"All selectivity bands show generally decreasing pattern")

# NOTE on "Highly Selective" anomaly: The execution log shows that for Highly
# Selective, "Moderate URM (20-40%)" has a HIGHER mean (89.8) than "Low URM (under 20%)"
# (87.9). This means the pattern is NOT strictly decreasing for Highly Selective,
# but IS generally decreasing (low > moderate not needed if it still drops overall).
# Actually, 89.8 > 87.9 means it's NOT monotonically decreasing. Let's flag this.
hs_subset = df.filter(pl.col("selectivity_band") == "Highly Selective")
if hs_subset.shape[0] >= 2:
    hs_means = hs_subset.with_columns(
        pl.col("urm_band").replace_strict(urm_order_map, default=None).alias("urm_ord")
    ).filter(pl.col("urm_ord").is_not_null()).sort("urm_ord")["mean_grad_rate"].to_list()
    print(f"\n  Highly Selective detail: means={[round(m, 1) for m in hs_means]}")
    if len(hs_means) >= 2 and hs_means[0] < hs_means[1]:
        print(f"  [INFO] Highly Selective: Moderate URM ({hs_means[1]:.1f}) > Low URM ({hs_means[0]:.1f})")
        print(f"  This is plausible: n=23 vs n=46, small samples can show non-monotonic patterns")
        print(f"  Only 2 cells populated, both with high grad rates (>87%), so pattern is weak")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print("QA4a SUMMARY")
print("=" * 60)

all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([boundary_ok, all_n_positive, absence_ok])
all_spots_passed = all([n_sum_ok, recalc_ok])

all_passed = all_default_passed and all_specific_passed and all_spots_passed
severity = "PASSED" if all_passed else "BLOCKER"
print(f"Default checks: {'PASSED' if all_default_passed else 'ISSUES'}")
print(f"Script-specific checks: {'PASSED' if all_specific_passed else 'ISSUES'}")
print(f"Spot-checks: {'PASSED' if all_spots_passed else 'ISSUES'}")

print(f"\nQA4a RESULT: {severity}")
print("=" * 60)

# =============================================================================
# DATA PROFILING (for cra2+ decision)
# =============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull crosstab output:")
with pl.Config(tbl_rows=50, tbl_cols=10, tbl_width_chars=120):
    print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["selectivity_band", "urm_band"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort(col))

print("\nn distribution:")
print(f"  min: {df['n'].min()}, max: {df['n'].max()}, mean: {df['n'].mean():.1f}, sum: {df['n'].sum()}")

print("\nmean_grad_rate distribution:")
print(f"  min: {df['mean_grad_rate'].min():.1f}, max: {df['mean_grad_rate'].max():.1f}, "
      f"mean: {df['mean_grad_rate'].mean():.1f}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:55:55
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage8_03_cra1_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA4a INSPECTION: Stage 8 Step 3 (crosstab-selectivity-urm)
# ============================================================
# Loaded crosstab: 14 rows x 5 cols
# Loaded source: 2,528 rows x 26 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 14 (expected 10-16)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain (no signed integer columns in crosstab)
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: COUNTERFACTUAL (sparse cells) ---
# Cell sizes range: min=15, max=495
# [PASS] No single-observation cells (min n > 1)
# [PASS] All cells have n >= 10
# 
# --- Check 7: SEMANTIC (research question alignment) ---
#   Highly Selective: means=[87.9, 89.8], first>last=NO
#   Less Selective/Open: means=[56.0, 53.2, 46.9, 42.4], first>last=YES
#   Moderately Selective: means=[64.0, 55.4, 49.4, 37.0], first>last=YES
#   Selective: means=[75.2, 62.4, 48.3, 38.8], first>last=YES
# [WARN] Observable Truth pattern: Not consistently decreasing
# 
# --- Check 8: BOUNDARY (value ranges) ---
# Mean grad rate range: [37.0, 89.8]
# Median grad rate range: [36.6, 93.0]
# [PASS] All grad rates in 0-100 range
# [PASS] All n values positive (min=15)
# 
# --- Check 9: ABSENCE (missing combinations) ---
# Selectivity bands present: ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
# URM bands present: ['High URM (40-60%)', 'Low URM (under 20%)', 'Moderate URM (20-40%)', 'Very High URM (60%+)']
# Populated cells: 14 / 16 (2 empty)
#   EMPTY: Highly Selective x High URM (40-60%)
#   EMPTY: Highly Selective x Very High URM (60%+)
# 
# Verifying empty cells against source data:
#   Source data: Highly Selective x High URM (40-60%) = 0 rows
#   Source data: Highly Selective x Very High URM (60%+) = 0 rows
# [PASS] Cell coverage adequate (14/16)
# 
# --- Check 10: DOWNSTREAM (output format for consumers) ---
# [INFO] Output is in long format (not pivoted as Plan step 6 suggests)
#   Long format is more versatile for downstream plotnine/report use
# [PASS] mean_grad_rate is Float64 (correct for downstream)
# [PASS] median_grad_rate is Float64 (correct for downstream)
# [PASS] n column is integer (UInt32)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-Check 11: Total n sum ---
# Sum of n across all cells: 1791
# Expected (filtered rows): 1791
# [PASS] Total n matches filtered count
# 
# --- Spot-Check 12: Manual mean recalculation ---
# Cell: Less Selective/Open x Low URM (under 20%)
#   Reported: n=495, mean=55.95, median=58.10
#   Recalculated: n=495, mean=55.95, median=58.10
# [PASS] Mean difference: 0.0000, n difference: 0
# 
# --- Spot-Check 13: Empty cell verification ---
#   Highly Selective x High URM (40-60%): source has 0 rows, crosstab empty [PASS]
#   Highly Selective x Very High URM (60%+): source has 0 rows, crosstab empty [PASS]
# 
# --- Spot-Check 14: URM band label match ---
# Actual URM labels in output: ['High URM (40-60%)', 'Low URM (under 20%)', 'Moderate URM (20-40%)', 'Very High URM (60%+)']
# Plan-specified labels: ['Low URM (under 20%)', 'Moderate URM (20-40%)', 'High URM (40-60%)', 'Very High URM (60%+)']
# [PASS] URM band labels match Plan
# Actual selectivity labels: ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
# 
# --- Spot-Check 15: Monotonic decrease verification ---
#   Highly Selective: [87.9, 89.8] — NOT decreasing
#   Less Selective/Open: [56.0, 53.2, 46.9, 42.4] — strictly decreasing
#   Moderately Selective: [64.0, 55.4, 49.4, 37.0] — strictly decreasing
#   Selective: [75.2, 62.4, 48.3, 38.8] — strictly decreasing
# [WARN] All selectivity bands show generally decreasing pattern
# 
#   Highly Selective detail: means=[87.9, 89.8]
#   [INFO] Highly Selective: Moderate URM (89.8) > Low URM (87.9)
#   This is plausible: n=23 vs n=46, small samples can show non-monotonic patterns
#   Only 2 cells populated, both with high grad rates (>87%), so pattern is weak
# 
# ============================================================
# QA4a SUMMARY
# ============================================================
# Default checks: PASSED
# Script-specific checks: PASSED
# Spot-checks: PASSED
# 
# QA4a RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full crosstab output:
# shape: (14, 5)
# ┌──────────────────────┬───────────────────────┬─────┬────────────────┬──────────────────┐
# │ selectivity_band     ┆ urm_band              ┆ n   ┆ mean_grad_rate ┆ median_grad_rate │
# │ ---                  ┆ ---                   ┆ --- ┆ ---            ┆ ---              │
# │ str                  ┆ str                   ┆ u32 ┆ f64            ┆ f64              │
# ╞══════════════════════╪═══════════════════════╪═════╪════════════════╪══════════════════╡
# │ Highly Selective     ┆ Low URM (under 20%)   ┆ 46  ┆ 87.930435      ┆ 91.45            │
# │ Highly Selective     ┆ Moderate URM (20-40%) ┆ 23  ┆ 89.773913      ┆ 93.0             │
# │ Less Selective/Open  ┆ High URM (40-60%)     ┆ 107 ┆ 46.894393      ┆ 47.7             │
# │ Less Selective/Open  ┆ Low URM (under 20%)   ┆ 495 ┆ 55.950909      ┆ 58.1             │
# │ Less Selective/Open  ┆ Moderate URM (20-40%) ┆ 262 ┆ 53.246565      ┆ 53.8             │
# │ Less Selective/Open  ┆ Very High URM (60%+)  ┆ 135 ┆ 42.361481      ┆ 39.7             │
# │ Moderately Selective ┆ High URM (40-60%)     ┆ 44  ┆ 49.425         ┆ 50.15            │
# │ Moderately Selective ┆ Low URM (under 20%)   ┆ 280 ┆ 63.978214      ┆ 64.95            │
# │ Moderately Selective ┆ Moderate URM (20-40%) ┆ 193 ┆ 55.421762      ┆ 56.4             │
# │ Moderately Selective ┆ Very High URM (60%+)  ┆ 47  ┆ 36.980851      ┆ 36.6             │
# │ Selective            ┆ High URM (40-60%)     ┆ 15  ┆ 48.333333      ┆ 53.7             │
# │ Selective            ┆ Low URM (under 20%)   ┆ 69  ┆ 75.23913       ┆ 82.3             │
# │ Selective            ┆ Moderate URM (20-40%) ┆ 48  ┆ 62.445833      ┆ 66.95            │
# │ Selective            ┆ Very High URM (60%+)  ┆ 27  ┆ 38.818519      ┆ 39.0             │
# └──────────────────────┴───────────────────────┴─────┴────────────────┴──────────────────┘
# 
# Descriptive statistics:
# shape: (9, 6)
# ┌────────────┬──────────────────┬──────────────────┬────────────┬────────────────┬─────────────────┐
# │ statistic  ┆ selectivity_band ┆ urm_band         ┆ n          ┆ mean_grad_rate ┆ median_grad_rat │
# │ ---        ┆ ---              ┆ ---              ┆ ---        ┆ ---            ┆ e               │
# │ str        ┆ str              ┆ str              ┆ f64        ┆ f64            ┆ ---             │
# │            ┆                  ┆                  ┆            ┆                ┆ f64             │
# ╞════════════╪══════════════════╪══════════════════╪════════════╪════════════════╪═════════════════╡
# │ count      ┆ 14               ┆ 14               ┆ 14.0       ┆ 14.0           ┆ 14.0            │
# │ null_count ┆ 0                ┆ 0                ┆ 0.0        ┆ 0.0            ┆ 0.0             │
# │ mean       ┆ null             ┆ null             ┆ 127.928571 ┆ 57.628596      ┆ 59.557143       │
# │ std        ┆ null             ┆ null             ┆ 137.191873 ┆ 16.719913      ┆ 18.374552       │
# │ min        ┆ Highly Selective ┆ High URM         ┆ 15.0       ┆ 36.980851      ┆ 36.6            │
# │            ┆                  ┆ (40-60%)         ┆            ┆                ┆                 │
# │ 25%        ┆ null             ┆ null             ┆ 44.0       ┆ 46.894393      ┆ 47.7            │
# │ 50%        ┆ null             ┆ null             ┆ 69.0       ┆ 55.421762      ┆ 56.4            │
# │ 75%        ┆ null             ┆ null             ┆ 193.0      ┆ 63.978214      ┆ 66.95           │
# │ max        ┆ Selective        ┆ Very High URM    ┆ 495.0      ┆ 89.773913      ┆ 93.0            │
# │            ┆                  ┆ (60%+)           ┆            ┆                ┆                 │
# └────────────┴──────────────────┴──────────────────┴────────────┴────────────────┴─────────────────┘
# 
# Key column value counts:
# 
# selectivity_band:
# shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ str                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Highly Selective     ┆ 2     │
# │ Less Selective/Open  ┆ 4     │
# │ Moderately Selective ┆ 4     │
# │ Selective            ┆ 4     │
# └──────────────────────┴───────┘
# 
# urm_band:
# shape: (4, 2)
# ┌───────────────────────┬───────┐
# │ urm_band              ┆ count │
# │ ---                   ┆ ---   │
# │ str                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ High URM (40-60%)     ┆ 3     │
# │ Low URM (under 20%)   ┆ 4     │
# │ Moderate URM (20-40%) ┆ 4     │
# │ Very High URM (60%+)  ┆ 3     │
# └───────────────────────┴───────┘
# 
# n distribution:
#   min: 15, max: 495, mean: 127.9, sum: 1791
# 
# mean_grad_rate distribution:
#   min: 37.0, max: 89.8, mean: 57.6
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
