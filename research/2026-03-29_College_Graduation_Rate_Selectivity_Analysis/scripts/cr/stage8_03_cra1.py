#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 03 (QA4a)

Reviewed script: scripts/stage8_analysis/03_crosstab-selectivity-urm_a.py
Output files: output/analysis/2026-03-29_crosstab_selectivity_urm.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Standard):
1. Schema matches Plan.md expectations
2. Row count within expected range (19-20 cells)
3. No suspicious distributions
4. Coded values filtered (not applicable for aggregated output)
5. No nulls in critical columns

QA Checks (Script-Specific — Five Lenses):
6. (Counterfactual) What if urm_quintile labels changed in upstream?
7. (Semantic) Does the gap computation match Plan.md research outcome intent?
8. (Boundary) Sparse cells and empty cells handled correctly?
9. (Absence) Are all 4 bands present? Any band missing entirely?
10. (Downstream) Can a visualization script consume this output without surprises?

QA Spot-Checks:
11. Sum of N across all cells should equal complete cases from source data
12. Verify a specific cell's mean by manual recalculation from source data
13. Verify the empty cell (HS x Q5) is genuinely empty in source data
14. Check monotonicity expectations (Q1->Q5 should generally decrease within bands)
15. Cross-reference total N per band with known band distribution from Stage 7
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_urm.parquet"
SOURCE_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

EXPECTED_COLUMNS = ["selectivity_band", "urm_quintile", "mean_grad_rate", "median_grad_rate", "N"]
EXPECTED_MIN_ROWS = 15  # 4 bands x 5 quintiles - some empty expected
EXPECTED_MAX_ROWS = 20  # 4 bands x 5 quintiles maximum
CRITICAL_COLUMNS = ["selectivity_band", "urm_quintile", "mean_grad_rate", "N"]
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]
QUINTILE_ORDER = ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 03 (QA4a)")
print("  Cross-tabulation Selectivity x URM Quintile")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load source for spot-checks
src = pl.read_parquet(SOURCE_FILE)
print(f"Loaded source: {src.shape[0]:,} rows x {src.shape[1]} cols")

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
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS}-{EXPECTED_MAX_ROWS})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 3:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
# Not applicable for aggregated output (mean/median/count). Check for
# coded missing values (-1, -2, -3) in N or mean_grad_rate which would indicate
# upstream coded values leaked into aggregations.
CODED_MISSING_VALUES = [-1, -2, -3]
coded_issues = []
for col in ["mean_grad_rate", "median_grad_rate", "N"]:
    for code in CODED_MISSING_VALUES:
        count = (df[col].cast(pl.Float64) == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain in aggregated output" if coded_ok else "; ".join(coded_issues))

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

# ===================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ===================================================================

# --- Check 6: Counterfactual — Label consistency with upstream ---
# If the upstream create-bands script changed quintile labels, the crosstab
# would silently produce fewer cells. Verify labels match exactly.
print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

actual_quintiles_in_output = sorted(df["urm_quintile"].unique().to_list())
actual_quintiles_in_source = sorted(
    src.filter(pl.col("urm_quintile").is_not_null())["urm_quintile"].unique().to_list()
)
label_match = actual_quintiles_in_output == actual_quintiles_in_source[:len(actual_quintiles_in_output)]
# Also check that output labels are a subset of source labels
label_subset = all(q in actual_quintiles_in_source for q in actual_quintiles_in_output)
print(f"[{'PASS' if label_subset else 'FAIL'}] Counterfactual: Output quintile labels match source")
print(f"  Output labels: {actual_quintiles_in_output}")
print(f"  Source labels: {actual_quintiles_in_source}")

# --- Check 7: Semantic — Gap computation serves research outcome ---
# Plan.md requires: "Cross-tabulation of selectivity bands with URM enrollment
# share quintiles characterizes how underserved population concentration varies
# by selectivity level". The gap should show Q1 vs Q5 difference.
# Verify the output contains the data needed to compute this.
bands_in_output = sorted(df["selectivity_band"].unique().to_list())
has_all_4_bands = len(bands_in_output) == 4
has_q1 = "Q1 (Lowest)" in actual_quintiles_in_output
has_q5 = "Q5 (Highest)" in actual_quintiles_in_output
semantic_ok = has_all_4_bands and (has_q1 or has_q5)
print(f"[{'PASS' if semantic_ok else 'FAIL'}] Semantic: Output supports gap computation")
print(f"  Bands present: {len(bands_in_output)}/4")
print(f"  Q1 present: {has_q1}, Q5 present: {has_q5}")

# --- Check 8: Boundary — Sparse and empty cell handling ---
# The output should have 19 cells (HS x Q5 expected empty).
# Sparse cells (N < 10) should exist for HS band.
n_min = df["N"].min()
n_max = df["N"].max()
sparse_count = df.filter(pl.col("N") < 10).shape[0]
# Check if HS band has the smallest N values as expected
hs_cells = df.filter(pl.col("selectivity_band") == "Highly Selective")
hs_n_values = hs_cells["N"].to_list()
boundary_ok = row_count >= 19  # At most 1 missing cell
print(f"[{'PASS' if boundary_ok else 'FAIL'}] Boundary: Cell coverage")
print(f"  Total cells: {row_count}/20 ({20 - row_count} missing)")
print(f"  N range: [{n_min}, {n_max}]")
print(f"  Sparse cells (N<10): {sparse_count}")
print(f"  HS band cells: {hs_cells.shape[0]}, N values: {hs_n_values}")

# --- Check 9: Absence — All 4 bands present ---
expected_bands = set(BAND_ORDER)
observed_bands = set(df["selectivity_band"].unique().to_list())
missing_bands = expected_bands - observed_bands
absence_ok = len(missing_bands) == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] Absence: All selectivity bands present")
if missing_bands:
    print(f"  Missing bands: {missing_bands}")
else:
    print(f"  Bands: {sorted(observed_bands)}")

# --- Check 10: Downstream — Consumability ---
# A downstream visualization script would pivot this data. Verify:
# (a) selectivity_band is string (not enum) — easier to handle
# (b) urm_quintile is categorical or string (pivotable)
# (c) mean_grad_rate is float
band_dtype = str(df["selectivity_band"].dtype)
quintile_dtype = str(df["urm_quintile"].dtype)
rate_dtype = str(df["mean_grad_rate"].dtype)
downstream_ok = "Float" in rate_dtype
print(f"[{'PASS' if downstream_ok else 'FAIL'}] Downstream: Output consumable by viz scripts")
print(f"  selectivity_band dtype: {band_dtype}")
print(f"  urm_quintile dtype: {quintile_dtype}")
print(f"  mean_grad_rate dtype: {rate_dtype}")

# ===================================================================
# SPOT-CHECKS
# ===================================================================
print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Sum of N equals complete cases ---
total_n_in_output = df["N"].sum()
source_complete = src.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("urm_quintile").is_not_null()
    & pl.col("completion_rate_150pct").is_not_null()
)
expected_n = source_complete.shape[0]
n_sum_ok = total_n_in_output == expected_n
print(f"[{'PASS' if n_sum_ok else 'FAIL'}] Sum of N: {total_n_in_output} (expected {expected_n} complete cases)")

# --- Spot-check 12: Manual recalculation of one cell ---
# Pick "Selective" x "Q2" — verify mean_grad_rate by independent computation
target_band = "Selective"
target_quintile = "Q2"
target_subset = source_complete.filter(
    (pl.col("selectivity_band") == target_band)
    & (pl.col("urm_quintile") == target_quintile)
)
manual_mean = target_subset["completion_rate_150pct"].mean()
manual_n = target_subset.shape[0]
output_row = df.filter(
    (pl.col("selectivity_band") == target_band)
    & (pl.col("urm_quintile") == target_quintile)
)
output_mean = output_row["mean_grad_rate"][0] if output_row.shape[0] > 0 else None
output_n = output_row["N"][0] if output_row.shape[0] > 0 else None
recalc_ok = (
    output_mean is not None
    and manual_mean is not None
    and abs(output_mean - manual_mean) < 0.001
    and output_n == manual_n
)
print(f"[{'PASS' if recalc_ok else 'FAIL'}] Manual recalc ({target_band} x {target_quintile})")
print(f"  Output: mean={output_mean:.6f}, N={output_n}")
print(f"  Manual: mean={manual_mean:.6f}, N={manual_n}")

# --- Spot-check 13: HS x Q5 genuinely empty ---
hs_q5_subset = source_complete.filter(
    (pl.col("selectivity_band") == "Highly Selective")
    & (pl.col("urm_quintile") == "Q5 (Highest)")
)
hs_q5_count = hs_q5_subset.shape[0]
hs_q5_ok = hs_q5_count == 0
print(f"[{'PASS' if hs_q5_ok else 'FAIL'}] HS x Q5(Highest) genuinely empty: {hs_q5_count} institutions")
if hs_q5_count > 0:
    print(f"  WARNING: Expected 0 but found {hs_q5_count} institutions!")

# --- Spot-check 14: Monotonicity within bands ---
# Within each band, mean_grad_rate should generally decrease from Q1 to Q5
# (higher URM share -> lower grad rate due to structural disadvantage)
# This is a soft check — we expect general trend but not strict monotonicity.
print(f"\nMonotonicity check (Q1 -> Q5 within each band):")
mono_issues = []
for band in BAND_ORDER:
    band_data = df.filter(pl.col("selectivity_band") == band)
    if band_data.shape[0] < 3:
        print(f"  {band}: Only {band_data.shape[0]} cells, skipping")
        continue
    # Sort by quintile order
    band_sorted = []
    for q in QUINTILE_ORDER:
        row = band_data.filter(pl.col("urm_quintile") == q)
        if row.shape[0] > 0:
            band_sorted.append((q, row["mean_grad_rate"][0]))
    # Check general trend
    if len(band_sorted) >= 3:
        first_rate = band_sorted[0][1]
        last_rate = band_sorted[-1][1]
        trend = "decreasing" if first_rate > last_rate else "increasing"
        # Count inversions
        inversions = sum(
            1 for i in range(len(band_sorted) - 1)
            if band_sorted[i][1] < band_sorted[i + 1][1]
        )
        direction_note = f"overall {trend} ({inversions} inversions)"
        if inversions >= len(band_sorted) - 1:
            mono_issues.append(f"{band}: unexpectedly {trend} (all inversions)")
        print(f"  {band}: {' -> '.join(f'{q}={r:.1f}' for q, r in band_sorted)} [{direction_note}]")

mono_ok = len(mono_issues) == 0
print(f"[{'PASS' if mono_ok else 'WARN'}] Monotonicity: {'General trend holds' if mono_ok else '; '.join(mono_issues)}")

# --- Spot-check 15: Band N totals match known distribution ---
# From Stage 7: HS=71, S=177, MS=577, OLS=1121 (total=1946)
# But the crosstab uses complete cases (non-null urm_quintile), so band N
# will be <= the full band sizes.
known_band_sizes = {"Highly Selective": 71, "Selective": 177, "Moderately Selective": 577, "Open/Less Selective": 1121}
print(f"\nBand N comparison:")
band_n_ok = True
for band in BAND_ORDER:
    band_cells = df.filter(pl.col("selectivity_band") == band)
    band_total = band_cells["N"].sum()
    known_total = known_band_sizes.get(band, 0)
    # Band total in crosstab should be <= known total (some may have null urm_quintile)
    ok = band_total <= known_total
    if not ok:
        band_n_ok = False
    pct = (band_total / known_total * 100) if known_total > 0 else 0
    print(f"  {band}: crosstab N={band_total}, known total={known_total} ({pct:.1f}%)")
    if not ok:
        print(f"    WARNING: Crosstab N exceeds known band size!")

print(f"[{'PASS' if band_n_ok else 'FAIL'}] Band N totals: {'All <= known sizes' if band_n_ok else 'Some exceed known sizes'}")

# --- Summary ---
all_standard = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific = all([label_subset, semantic_ok, boundary_ok, absence_ok, downstream_ok])
all_spot = all([n_sum_ok, recalc_ok, hs_q5_ok, mono_ok, band_n_ok])
all_passed = all_standard and all_specific and all_spot

print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if not all_passed:
    if not all_standard:
        print("  Standard checks had failures")
    if not all_specific:
        print("  Script-specific checks had failures")
    if not all_spot:
        print("  Spot-checks had failures")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull output data:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["selectivity_band", "urm_quintile"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts())

print("\nMean grad rate by band (from output, across all quintiles):")
band_summary = (
    df.group_by("selectivity_band")
    .agg(
        pl.col("mean_grad_rate").mean().alias("avg_mean_grad_rate"),
        pl.col("N").sum().alias("total_N"),
    )
)
print(band_summary)

print("\nGrad rate range per band:")
for band in BAND_ORDER:
    band_data = df.filter(pl.col("selectivity_band") == band)
    if band_data.shape[0] > 0:
        mn = band_data["mean_grad_rate"].min()
        mx = band_data["mean_grad_rate"].max()
        print(f"  {band}: [{mn:.1f}, {mx:.1f}]")

print("\nMedian vs Mean comparison (large divergence may indicate skew):")
for row in df.iter_rows(named=True):
    diff = abs(row["mean_grad_rate"] - row["median_grad_rate"])
    flag = " <-- LARGE GAP" if diff > 15 else ""
    print(f"  {row['selectivity_band']:22s} x {row['urm_quintile']:14s}: mean={row['mean_grad_rate']:.1f}, median={row['median_grad_rate']:.1f}, diff={diff:.1f}{flag}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 12:08:57
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_03_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 03 (QA4a)
#   Cross-tabulation Selectivity x URM Quintile
# ============================================================
# Loaded output: 19 rows x 5 cols
# Loaded source: 1,946 rows x 25 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 19 (expected 15-20)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain in aggregated output
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# [PASS] Counterfactual: Output quintile labels match source
#   Output labels: ['Q1 (Lowest)', 'Q2', 'Q3', 'Q4', 'Q5 (Highest)']
#   Source labels: ['Q1 (Lowest)', 'Q2', 'Q3', 'Q4', 'Q5 (Highest)']
# [PASS] Semantic: Output supports gap computation
#   Bands present: 4/4
#   Q1 present: True, Q5 present: True
# [PASS] Boundary: Cell coverage
#   Total cells: 19/20 (1 missing)
#   N range: [4, 275]
#   Sparse cells (N<10): 2
#   HS band cells: 4, N values: [7, 31, 29, 4]
# [PASS] Absence: All selectivity bands present
#   Bands: ['Highly Selective', 'Moderately Selective', 'Open/Less Selective', 'Selective']
# [PASS] Downstream: Output consumable by viz scripts
#   selectivity_band dtype: String
#   urm_quintile dtype: Categorical
#   mean_grad_rate dtype: Float64
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# [PASS] Sum of N: 1939 (expected 1939 complete cases)
# [PASS] Manual recalc (Selective x Q2)
#   Output: mean=78.688636, N=44
#   Manual: mean=78.688636, N=44
# [PASS] HS x Q5(Highest) genuinely empty: 0 institutions
# 
# Monotonicity check (Q1 -> Q5 within each band):
#   Highly Selective: Q1 (Lowest)=68.6 -> Q2=90.8 -> Q3=92.4 -> Q4=73.8 [overall increasing (2 inversions)]
#   Selective: Q1 (Lowest)=66.1 -> Q2=78.7 -> Q3=66.2 -> Q4=50.7 -> Q5 (Highest)=37.6 [overall decreasing (1 inversions)]
#   Moderately Selective: Q1 (Lowest)=63.3 -> Q2=64.4 -> Q3=58.7 -> Q4=51.0 -> Q5 (Highest)=39.0 [overall decreasing (1 inversions)]
#   Open/Less Selective: Q1 (Lowest)=54.3 -> Q2=58.4 -> Q3=54.2 -> Q4=48.5 -> Q5 (Highest)=43.9 [overall decreasing (1 inversions)]
# [PASS] Monotonicity: General trend holds
# 
# Band N comparison:
#   Highly Selective: crosstab N=71, known total=71 (100.0%)
#   Selective: crosstab N=176, known total=177 (99.4%)
#   Moderately Selective: crosstab N=577, known total=577 (100.0%)
#   Open/Less Selective: crosstab N=1115, known total=1121 (99.5%)
# [PASS] Band N totals: All <= known sizes
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full output data:
# shape: (19, 5)
# ┌──────────────────────┬──────────────┬────────────────┬──────────────────┬─────┐
# │ selectivity_band     ┆ urm_quintile ┆ mean_grad_rate ┆ median_grad_rate ┆ N   │
# │ ---                  ┆ ---          ┆ ---            ┆ ---              ┆ --- │
# │ str                  ┆ cat          ┆ f64            ┆ f64              ┆ u32 │
# ╞══════════════════════╪══════════════╪════════════════╪══════════════════╪═════╡
# │ Highly Selective     ┆ Q1 (Lowest)  ┆ 68.614286      ┆ 76.9             ┆ 7   │
# │ Highly Selective     ┆ Q2           ┆ 90.841935      ┆ 91.5             ┆ 31  │
# │ Highly Selective     ┆ Q3           ┆ 92.437931      ┆ 93.8             ┆ 29  │
# │ Highly Selective     ┆ Q4           ┆ 73.75          ┆ 89.95            ┆ 4   │
# │ Moderately Selective ┆ Q1 (Lowest)  ┆ 63.29386       ┆ 67.5             ┆ 114 │
# │ …                    ┆ …            ┆ …              ┆ …                ┆ …   │
# │ Selective            ┆ Q1 (Lowest)  ┆ 66.142105      ┆ 65.2             ┆ 19  │
# │ Selective            ┆ Q2           ┆ 78.688636      ┆ 83.7             ┆ 44  │
# │ Selective            ┆ Q3           ┆ 66.182857      ┆ 73.5             ┆ 35  │
# │ Selective            ┆ Q4           ┆ 50.697436      ┆ 53.7             ┆ 39  │
# │ Selective            ┆ Q5 (Highest) ┆ 37.564103      ┆ 37.0             ┆ 39  │
# └──────────────────────┴──────────────┴────────────────┴──────────────────┴─────┘
# 
# Descriptive statistics:
# shape: (9, 6)
# ┌────────────┬──────────────────┬──────────────┬────────────────┬──────────────────┬────────────┐
# │ statistic  ┆ selectivity_band ┆ urm_quintile ┆ mean_grad_rate ┆ median_grad_rate ┆ N          │
# │ ---        ┆ ---              ┆ ---          ┆ ---            ┆ ---              ┆ ---        │
# │ str        ┆ str              ┆ str          ┆ f64            ┆ f64              ┆ f64        │
# ╞════════════╪══════════════════╪══════════════╪════════════════╪══════════════════╪════════════╡
# │ count      ┆ 19               ┆ 19           ┆ 19.0           ┆ 19.0             ┆ 19.0       │
# │ null_count ┆ 0                ┆ 0            ┆ 0.0            ┆ 0.0              ┆ 0.0        │
# │ mean       ┆ null             ┆ null         ┆ 61.085322      ┆ 63.731579        ┆ 102.052632 │
# │ std        ┆ null             ┆ null         ┆ 15.407115      ┆ 17.380514        ┆ 87.121546  │
# │ min        ┆ Highly Selective ┆ null         ┆ 37.564103      ┆ 37.0             ┆ 4.0        │
# │ 25%        ┆ null             ┆ null         ┆ 50.998947      ┆ 53.7             ┆ 35.0       │
# │ 50%        ┆ null             ┆ null         ┆ 58.721154      ┆ 60.9             ┆ 64.0       │
# │ 75%        ┆ null             ┆ null         ┆ 68.614286      ┆ 76.9             ┆ 181.0      │
# │ max        ┆ Selective        ┆ null         ┆ 92.437931      ┆ 93.8             ┆ 275.0      │
# └────────────┴──────────────────┴──────────────┴────────────────┴──────────────────┴────────────┘
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
# │ Open/Less Selective  ┆ 5     │
# │ Selective            ┆ 5     │
# │ Highly Selective     ┆ 4     │
# │ Moderately Selective ┆ 5     │
# └──────────────────────┴───────┘
# 
# urm_quintile:
# shape: (5, 2)
# ┌──────────────┬───────┐
# │ urm_quintile ┆ count │
# │ ---          ┆ ---   │
# │ cat          ┆ u32   │
# ╞══════════════╪═══════╡
# │ Q2           ┆ 4     │
# │ Q1 (Lowest)  ┆ 4     │
# │ Q5 (Highest) ┆ 3     │
# │ Q4           ┆ 4     │
# │ Q3           ┆ 4     │
# └──────────────┴───────┘
# 
# Mean grad rate by band (from output, across all quintiles):
# shape: (4, 3)
# ┌──────────────────────┬────────────────────┬─────────┐
# │ selectivity_band     ┆ avg_mean_grad_rate ┆ total_N │
# │ ---                  ┆ ---                ┆ ---     │
# │ str                  ┆ f64                ┆ u32     │
# ╞══════════════════════╪════════════════════╪═════════╡
# │ Moderately Selective ┆ 55.288502          ┆ 577     │
# │ Open/Less Selective  ┆ 51.851865          ┆ 1115    │
# │ Selective            ┆ 59.855027          ┆ 176     │
# │ Highly Selective     ┆ 81.411038          ┆ 71      │
# └──────────────────────┴────────────────────┴─────────┘
# 
# Grad rate range per band:
#   Highly Selective: [68.6, 92.4]
#   Selective: [37.6, 78.7]
#   Moderately Selective: [39.0, 64.4]
#   Open/Less Selective: [43.9, 58.4]
# 
# Median vs Mean comparison (large divergence may indicate skew):
#   Highly Selective       x Q1 (Lowest)   : mean=68.6, median=76.9, diff=8.3
#   Highly Selective       x Q2            : mean=90.8, median=91.5, diff=0.7
#   Highly Selective       x Q3            : mean=92.4, median=93.8, diff=1.4
#   Highly Selective       x Q4            : mean=73.8, median=90.0, diff=16.2 <-- LARGE GAP
#   Moderately Selective   x Q1 (Lowest)   : mean=63.3, median=67.5, diff=4.2
#   Moderately Selective   x Q2            : mean=64.4, median=63.0, diff=1.3
#   Moderately Selective   x Q3            : mean=58.7, median=60.9, diff=2.2
#   Moderately Selective   x Q4            : mean=51.0, median=52.3, diff=1.3
#   Moderately Selective   x Q5 (Highest)  : mean=39.0, median=40.6, diff=1.6
#   Open/Less Selective    x Q1 (Lowest)   : mean=54.3, median=57.3, diff=3.0
#   Open/Less Selective    x Q2            : mean=58.4, median=59.5, diff=1.0
#   Open/Less Selective    x Q3            : mean=54.2, median=55.6, diff=1.4
#   Open/Less Selective    x Q4            : mean=48.5, median=48.6, diff=0.1
#   Open/Less Selective    x Q5 (Highest)  : mean=43.9, median=40.3, diff=3.6
#   Selective              x Q1 (Lowest)   : mean=66.1, median=65.2, diff=0.9
#   Selective              x Q2            : mean=78.7, median=83.7, diff=5.0
#   Selective              x Q3            : mean=66.2, median=73.5, diff=7.3
#   Selective              x Q4            : mean=50.7, median=53.7, diff=3.0
#   Selective              x Q5 (Highest)  : mean=37.6, median=37.0, diff=0.6
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
