#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 8.2 — sector-comparison (QA4a, Iteration 1)

Reviewed script: scripts/stage8_analysis/07_sector-comparison.py
Output files: output/analysis/2026-02-15_sector_comparison.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Standard):
1. Schema matches Plan expectations
2. Row count within expected range (8 rows)
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] Verify group_by doesn't silently drop nulls in grouping cols
7. [Semantic] Verify gap analysis direction matches Observable Truth interpretation
8. [Boundary] Check for sparse cells (n < 10) that could distort medians
9. [Absence] Verify no inst_control values other than 1, 2 exist in source data
10. [Downstream] Verify sector_label values match expected strings for viz-sector-comparison

Spot-Checks:
11. Recalculate median grad rate for one specific cell from raw data
12. Verify n_with_grad_rate + null count = n for each cell
13. Cross-check n sum against source dataset row count
14. Verify selectivity_band ordering in output is logical (not alphabetical)
15. Verify std_grad_rate is non-negative and plausible
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_sector_comparison.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
EXPECTED_COLUMNS = [
    "selectivity_band", "inst_control", "n", "n_with_grad_rate",
    "median_grad_rate", "mean_grad_rate", "std_grad_rate",
    "median_pell_share", "median_urm_share",
    "median_student_faculty_ratio", "median_retention_rate",
    "sector_label"
]
EXPECTED_MIN_ROWS = 8
EXPECTED_MAX_ROWS = 8
CRITICAL_COLUMNS = [
    "selectivity_band", "inst_control", "n", "median_grad_rate",
    "mean_grad_rate", "median_pell_share", "median_urm_share"
]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 8.2 — sector-comparison")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load the source analysis dataset for cross-validation
src = pl.read_parquet(INPUT_FILE)
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
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64, pl.Int32, pl.UInt32)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 1:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if col_data.dtype in [pl.Float64, pl.Float32]:
        if (col_data == 0).all():
            dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
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
print("None remain" if coded_ok else "; ".join(coded_issues))

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
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Do grouping columns have nulls in source? ---
# If source has null selectivity_band or inst_control, those rows would be
# silently dropped by group_by, making n sum incorrect.
src_null_band = src["selectivity_band"].null_count()
src_null_ctrl = src["inst_control"].null_count()
counterfactual_ok = (src_null_band == 0) and (src_null_ctrl == 0)
print(f"\n[{'PASS' if counterfactual_ok else 'WARN'}] Counterfactual: Null grouping cols in source")
print(f"  selectivity_band nulls in source: {src_null_band}")
print(f"  inst_control nulls in source: {src_null_ctrl}")
if not counterfactual_ok:
    # Check how many rows would be lost
    lost = src.filter(
        pl.col("selectivity_band").is_null() | pl.col("inst_control").is_null()
    ).shape[0]
    print(f"  Rows with null grouping cols: {lost} (would be dropped from aggregation)")

# --- Check 7: [Semantic] Verify gap direction matches Observable Truth ---
# Observable Truth: "Private nonprofit institutions have higher graduation rates
# than public institutions within the same selectivity band."
# The gap is computed as Private - Public. Positive = private higher = OT supported.
print(f"\n[INFO] Semantic: Observable Truth gap direction check")
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    ctrl = row["inst_control"]
    med_gr = row["median_grad_rate"]
    label = row["sector_label"]
    print(f"  {band} | {label} (ctrl={ctrl}): median_grad_rate={med_gr}")

# Compute gaps per band
bands_in_data = df["selectivity_band"].unique().to_list()
gap_results = []
for band in bands_in_data:
    band_data = df.filter(pl.col("selectivity_band") == band)
    pub = band_data.filter(pl.col("inst_control") == 1)["median_grad_rate"]
    priv = band_data.filter(pl.col("inst_control") == 2)["median_grad_rate"]
    if pub.len() > 0 and priv.len() > 0:
        pub_val = pub[0]
        priv_val = priv[0]
        if pub_val is not None and priv_val is not None:
            gap = priv_val - pub_val
            gap_results.append((band, gap))
            direction = "Private higher" if gap > 0 else "Public higher" if gap < 0 else "Equal"
            print(f"  GAP {band}: {gap:+.1f}pp ({direction})")

# Check: OT says private > public in each band. Report any exceptions.
ot_violations = [(b, g) for b, g in gap_results if g < 0]
semantic_ok = len(ot_violations) == 0
print(f"[{'PASS' if semantic_ok else 'WARN'}] Semantic: Observable Truth uniformly supported = {semantic_ok}")
if ot_violations:
    for b, g in ot_violations:
        print(f"  EXCEPTION: In '{b}', public has higher median grad rate by {abs(g):.1f}pp")
    print("  NOTE: This is a data finding, not a code error. The script correctly computes"
          " and reports the gap. The Observable Truth is not uniformly supported.")

# --- Check 8: [Boundary] Check for sparse cells (n < 10) ---
sparse_cells = []
for row in df.iter_rows(named=True):
    if row["n"] < 10:
        sparse_cells.append(f"{row['selectivity_band']} x {row['sector_label']}: n={row['n']}")
    if row["n_with_grad_rate"] < 10:
        sparse_cells.append(
            f"{row['selectivity_band']} x {row['sector_label']}: n_with_grad_rate={row['n_with_grad_rate']}"
        )
boundary_ok = len(sparse_cells) == 0
print(f"\n[{'PASS' if boundary_ok else 'WARN'}] Boundary: Sparse cells (n < 10)")
if sparse_cells:
    for s in sparse_cells:
        print(f"  SPARSE: {s}")

# --- Check 9: [Absence] Verify no inst_control values other than 1, 2 ---
# The script filters by SECTOR_LABELS = {1, 2}. If source has 3 (for-profit),
# those would still be included in the aggregation unless filtered upstream.
src_ctrl_values = sorted(src["inst_control"].drop_nulls().unique().to_list())
unexpected_ctrl = [v for v in src_ctrl_values if v not in [1, 2]]
absence_ok = len(unexpected_ctrl) == 0
print(f"\n[{'PASS' if absence_ok else 'FAIL'}] Absence: inst_control values in source = {src_ctrl_values}")
if unexpected_ctrl:
    for v in unexpected_ctrl:
        count = src.filter(pl.col("inst_control") == v).shape[0]
        print(f"  UNEXPECTED: inst_control={v} has {count} rows — these are included in group_by!")

# --- Check 10: [Downstream] sector_label values match expected ---
# viz-sector-comparison will use sector_label for legend/coloring
expected_labels = {"Public", "Private nonprofit"}
actual_labels = set(df["sector_label"].drop_nulls().to_list())
downstream_ok = actual_labels == expected_labels
print(f"\n[{'PASS' if downstream_ok else 'FAIL'}] Downstream: sector_label values = {actual_labels}")
if not downstream_ok:
    print(f"  Expected: {expected_labels}")

# =============================================================================
# SPOT-CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Recalculate median grad rate for one specific cell ---
# Pick "Moderately Selective" x "Public" (n=160, reasonable size)
spot_band = "Moderately Selective"
spot_ctrl = 1
spot_src = src.filter(
    (pl.col("selectivity_band") == spot_band) & (pl.col("inst_control") == spot_ctrl)
)
spot_output = df.filter(
    (pl.col("selectivity_band") == spot_band) & (pl.col("inst_control") == spot_ctrl)
)

recalc_median = spot_src["grad_rate_150pct"].median()
output_median = spot_output["median_grad_rate"][0]
median_match = (recalc_median is not None and output_median is not None and
                abs(recalc_median - output_median) < 0.01)
print(f"\n[{'PASS' if median_match else 'FAIL'}] Spot-check 11: Median grad rate for {spot_band} x Public")
print(f"  Recalculated from source: {recalc_median}")
print(f"  Output value:             {output_median}")

# --- Spot-Check 12: n_with_grad_rate + null count = n for each cell ---
print(f"\n  Spot-check 12: n_with_grad_rate consistency")
check12_ok = True
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    ctrl = row["inst_control"]
    n_total = row["n"]
    n_gr = row["n_with_grad_rate"]

    # Get source data for this cell and count nulls
    cell_src = src.filter(
        (pl.col("selectivity_band") == band) & (pl.col("inst_control") == ctrl)
    )
    actual_n = cell_src.shape[0]
    actual_n_gr = cell_src.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]

    n_match = (n_total == actual_n)
    ngr_match = (n_gr == actual_n_gr)
    if not (n_match and ngr_match):
        check12_ok = False
        label = row["sector_label"]
        print(f"  [FAIL] {band} x {label}: n={n_total} vs src={actual_n}, "
              f"n_gr={n_gr} vs src={actual_n_gr}")

if check12_ok:
    print(f"[PASS] Spot-check 12: All n and n_with_grad_rate match source")
else:
    print(f"[FAIL] Spot-check 12: n / n_with_grad_rate mismatch detected")

# --- Spot-Check 13: n sum against source row count ---
n_sum = df["n"].sum()
src_rows = src.shape[0]
sum_ok = n_sum == src_rows
print(f"\n[{'PASS' if sum_ok else 'FAIL'}] Spot-check 13: n sum = {n_sum}, source rows = {src_rows}")

# --- Spot-Check 14: Selectivity band ordering ---
# Output should be ordered: Highly Selective, Selective, Moderately Selective, Less Selective/Open
expected_order = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
actual_bands_ordered = []
seen = set()
for row in df.iter_rows(named=True):
    band = row["selectivity_band"]
    if band not in seen:
        actual_bands_ordered.append(band)
        seen.add(band)
order_ok = actual_bands_ordered == expected_order
print(f"\n[{'PASS' if order_ok else 'FAIL'}] Spot-check 14: Selectivity band ordering")
print(f"  Expected: {expected_order}")
print(f"  Actual:   {actual_bands_ordered}")

# --- Spot-Check 15: std_grad_rate is non-negative and plausible ---
std_vals = df["std_grad_rate"].drop_nulls()
std_ok = True
if std_vals.len() > 0:
    if std_vals.min() < 0:
        std_ok = False
        print(f"[FAIL] Spot-check 15: Negative std_grad_rate found: min={std_vals.min()}")
    elif std_vals.max() > 50:
        # Grad rate is 0-100, so std > 50 would be extreme
        std_ok = False
        print(f"[FAIL] Spot-check 15: Implausibly high std_grad_rate: max={std_vals.max()}")
    else:
        print(f"\n[PASS] Spot-check 15: std_grad_rate range [{std_vals.min():.1f}, {std_vals.max():.1f}] is plausible")
else:
    print(f"\n[WARN] Spot-check 15: No non-null std_grad_rate values")
    std_ok = False

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull output dataset:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["selectivity_band", "inst_control", "sector_label"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts())

print("\nGrad rate columns detail:")
for col in ["median_grad_rate", "mean_grad_rate", "std_grad_rate"]:
    if col in df.columns:
        vals = df[col].drop_nulls()
        print(f"\n{col}: min={vals.min()}, max={vals.max()}, mean={vals.mean():.2f}")

# --- Summary ---
all_standard_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_ok = counterfactual_ok and absence_ok and downstream_ok
all_spots_ok = median_match and check12_ok and sum_ok and order_ok and std_ok

all_passed = all_standard_passed and all_specific_ok and all_spots_ok
# Semantic check (Observable Truth) is a data finding, not a code error
has_warnings = not semantic_ok or not boundary_ok

print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)
print(f"Standard checks:       {'PASSED' if all_standard_passed else 'ISSUES'}")
print(f"Script-specific checks: {'PASSED' if all_specific_ok else 'ISSUES'}")
print(f"  (Semantic OT check:   {'Uniformly supported' if semantic_ok else 'EXCEPTIONS found (WARNING, not BLOCKER)'})")
print(f"  (Boundary sparse:     {'No sparse cells' if boundary_ok else 'SPARSE CELLS found (WARNING)'})")
print(f"Spot-checks:           {'PASSED' if all_spots_ok else 'ISSUES'}")

if all_passed and not has_warnings:
    severity = "PASSED"
elif all_passed:
    severity = "PASSED with WARNINGs"
else:
    severity = "BLOCKER"

print(f"\nQA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:08:49
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_07_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 8.2 — sector-comparison
# ============================================================
# Loaded output: 8 rows x 12 cols
# Loaded source: 2,528 rows x 26 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 8 (expected 8-8)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] Counterfactual: Null grouping cols in source
#   selectivity_band nulls in source: 0
#   inst_control nulls in source: 0
# 
# [INFO] Semantic: Observable Truth gap direction check
#   Highly Selective | Public (ctrl=1): median_grad_rate=91.9
#   Highly Selective | Private nonprofit (ctrl=2): median_grad_rate=92.6
#   Selective | Public (ctrl=1): median_grad_rate=74.6
#   Selective | Private nonprofit (ctrl=2): median_grad_rate=62.6
#   Moderately Selective | Public (ctrl=1): median_grad_rate=54.2
#   Moderately Selective | Private nonprofit (ctrl=2): median_grad_rate=60.3
#   Less Selective/Open | Public (ctrl=1): median_grad_rate=50.5
#   Less Selective/Open | Private nonprofit (ctrl=2): median_grad_rate=56.99999999999999
#   GAP Highly Selective: +0.7pp (Private higher)
#   GAP Selective: -12.0pp (Public higher)
#   GAP Moderately Selective: +6.1pp (Private higher)
#   GAP Less Selective/Open: +6.5pp (Private higher)
# [WARN] Semantic: Observable Truth uniformly supported = False
#   EXCEPTION: In 'Selective', public has higher median grad rate by 12.0pp
#   NOTE: This is a data finding, not a code error. The script correctly computes and reports the gap. The Observable Truth is not uniformly supported.
# 
# [WARN] Boundary: Sparse cells (n < 10)
#   SPARSE: Highly Selective x Public: n=9
#   SPARSE: Highly Selective x Public: n_with_grad_rate=9
# 
# [PASS] Absence: inst_control values in source = [1, 2]
# 
# [PASS] Downstream: sector_label values = {'Private nonprofit', 'Public'}
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# [PASS] Spot-check 11: Median grad rate for Moderately Selective x Public
#   Recalculated from source: 54.2
#   Output value:             54.2
# 
#   Spot-check 12: n_with_grad_rate consistency
# [PASS] Spot-check 12: All n and n_with_grad_rate match source
# 
# [PASS] Spot-check 13: n sum = 2528, source rows = 2528
# 
# [PASS] Spot-check 14: Selectivity band ordering
#   Expected: ['Highly Selective', 'Selective', 'Moderately Selective', 'Less Selective/Open']
#   Actual:   ['Highly Selective', 'Selective', 'Moderately Selective', 'Less Selective/Open']
# 
# [PASS] Spot-check 15: std_grad_rate range [4.6, 23.0] is plausible
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full output dataset:
# shape: (8, 12)
# ┌────────────┬────────────┬──────┬────────────┬───┬────────────┬───────────┬───────────┬───────────┐
# │ selectivit ┆ inst_contr ┆ n    ┆ n_with_gra ┆ … ┆ median_urm ┆ median_st ┆ median_re ┆ sector_la │
# │ y_band     ┆ ol         ┆ ---  ┆ d_rate     ┆   ┆ _share     ┆ udent_fac ┆ tention_r ┆ bel       │
# │ ---        ┆ ---        ┆ u32  ┆ ---        ┆   ┆ ---        ┆ ulty_rati ┆ ate       ┆ ---       │
# │ cat        ┆ i64        ┆      ┆ u32        ┆   ┆ f64        ┆ o         ┆ ---       ┆ str       │
# │            ┆            ┆      ┆            ┆   ┆            ┆ ---       ┆ f64       ┆           │
# │            ┆            ┆      ┆            ┆   ┆            ┆ f64       ┆           ┆           │
# ╞════════════╪════════════╪══════╪════════════╪═══╪════════════╪═══════════╪═══════════╪═══════════╡
# │ Highly     ┆ 1          ┆ 9    ┆ 9          ┆ … ┆ 0.182029   ┆ 13.0      ┆ 97.0      ┆ Public    │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Highly     ┆ 2          ┆ 64   ┆ 60         ┆ … ┆ 0.18551    ┆ 8.0       ┆ 92.0      ┆ Private   │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# │ Selective  ┆ 1          ┆ 38   ┆ 37         ┆ … ┆ 0.310883   ┆ 17.0      ┆ 89.0      ┆ Public    │
# │ Selective  ┆ 2          ┆ 136  ┆ 122        ┆ … ┆ 0.196464   ┆ 10.0      ┆ 79.0      ┆ Private   │
# │            ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# │ Moderately ┆ 1          ┆ 160  ┆ 157        ┆ … ┆ 0.257936   ┆ 16.0      ┆ 78.0      ┆ Public    │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Moderately ┆ 2          ┆ 426  ┆ 407        ┆ … ┆ 0.186251   ┆ 12.0      ┆ 75.5      ┆ Private   │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# │ Less Selec ┆ 1          ┆ 645  ┆ 391        ┆ … ┆ 0.230444   ┆ 17.0      ┆ 75.0      ┆ Public    │
# │ tive/Open  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Less Selec ┆ 2          ┆ 1050 ┆ 613        ┆ … ┆ 0.207363   ┆ 12.0      ┆ 75.0      ┆ Private   │
# │ tive/Open  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# └────────────┴────────────┴──────┴────────────┴───┴────────────┴───────────┴───────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 13)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ selectivi ┆ inst_cont ┆ n         ┆ … ┆ median_ur ┆ median_st ┆ median_re ┆ sector_l │
# │ ---       ┆ ty_band   ┆ rol       ┆ ---       ┆   ┆ m_share   ┆ udent_fac ┆ tention_r ┆ abel     │
# │ str       ┆ ---       ┆ ---       ┆ f64       ┆   ┆ ---       ┆ ulty_rati ┆ ate       ┆ ---      │
# │           ┆ str       ┆ f64       ┆           ┆   ┆ f64       ┆ o         ┆ ---       ┆ str      │
# │           ┆           ┆           ┆           ┆   ┆           ┆ ---       ┆ f64       ┆          │
# │           ┆           ┆           ┆           ┆   ┆           ┆ f64       ┆           ┆          │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 8         ┆ 8.0       ┆ 8.0       ┆ … ┆ 8.0       ┆ 8.0       ┆ 8.0       ┆ 8        │
# │ null_coun ┆ 0         ┆ 0.0       ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0        │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ null      ┆ 1.5       ┆ 316.0     ┆ … ┆ 0.21961   ┆ 13.125    ┆ 82.5625   ┆ null     │
# │ std       ┆ null      ┆ 0.534522  ┆ 368.56284 ┆ … ┆ 0.045183  ┆ 3.313932  ┆ 8.756375  ┆ null     │
# │           ┆           ┆           ┆ 6         ┆   ┆           ┆           ┆           ┆          │
# │ min       ┆ null      ┆ 1.0       ┆ 9.0       ┆ … ┆ 0.182029  ┆ 8.0       ┆ 75.0      ┆ Private  │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ nonprofi │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ t        │
# │ 25%       ┆ null      ┆ 1.0       ┆ 64.0      ┆ … ┆ 0.186251  ┆ 12.0      ┆ 75.5      ┆ null     │
# │ 50%       ┆ null      ┆ 2.0       ┆ 160.0     ┆ … ┆ 0.207363  ┆ 13.0      ┆ 79.0      ┆ null     │
# │ 75%       ┆ null      ┆ 2.0       ┆ 426.0     ┆ … ┆ 0.230444  ┆ 16.0      ┆ 89.0      ┆ null     │
# │ max       ┆ null      ┆ 2.0       ┆ 1050.0    ┆ … ┆ 0.310883  ┆ 17.0      ┆ 97.0      ┆ Public   │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Key column value counts:
# 
# selectivity_band:
# shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ cat                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Less Selective/Open  ┆ 2     │
# │ Highly Selective     ┆ 2     │
# │ Selective            ┆ 2     │
# │ Moderately Selective ┆ 2     │
# └──────────────────────┴───────┘
# 
# inst_control:
# shape: (2, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 2            ┆ 4     │
# │ 1            ┆ 4     │
# └──────────────┴───────┘
# 
# sector_label:
# shape: (2, 2)
# ┌───────────────────┬───────┐
# │ sector_label      ┆ count │
# │ ---               ┆ ---   │
# │ str               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ Public            ┆ 4     │
# │ Private nonprofit ┆ 4     │
# └───────────────────┴───────┘
# 
# Grad rate columns detail:
# 
# median_grad_rate: min=50.5, max=92.6, mean=67.96
# 
# mean_grad_rate: min=49.31023017902813, max=89.41111111111111, mean=65.44
# 
# std_grad_rate: min=4.551495480730607, max=22.990898447242362, mean=16.74
# 
# ============================================================
# QA SUMMARY
# ============================================================
# Standard checks:       PASSED
# Script-specific checks: PASSED
#   (Semantic OT check:   EXCEPTIONS found (WARNING, not BLOCKER))
#   (Boundary sparse:     SPARSE CELLS found (WARNING))
# Spot-checks:           PASSED
# 
# QA RESULT: PASSED with WARNINGs
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
