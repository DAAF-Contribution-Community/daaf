#!/usr/bin/env python3
"""
Stage 8.1: Descriptive statistics by selectivity band.

Task: descriptive-by-selectivity
Wave: 7, Step: 1, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_descriptive_by_selectivity.parquet
Checkpoint: CP4
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's analysis design.
# Selectivity bands were created in Stage 7 (create-bands) and are ordered
# from most to least selective. Summary statistics are computed per band
# for all key continuous variables plus sector composition.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_descriptive_by_selectivity.parquet"

# REASONING: Band ordering follows the logical gradient from most to least
# selective. This order is used for display and for ensuring the output
# rows are in a meaningful sequence (not alphabetical).
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]

# INTENT: These are the continuous variables for which we compute descriptive
# statistics (mean, median, SD) within each selectivity band. They correspond
# to the key outcome, predictor, and control variables in the research design.
SUMMARY_VARS = [
    "completion_rate_150pct",
    "admit_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
    "instr_expend_per_fte",
]

# --- Load ---
# Load the analysis dataset and verify shape before proceeding.
print("=" * 60)
print("Stage 8.1: Descriptive Statistics by Selectivity Band")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture current state before computing descriptives. This is a read-only
# analysis (no row filtering), so we expect the same row count throughout.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"Pre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Columns available: {pre_cols}")

# Verify all required columns exist
required_cols = ["selectivity_band", "inst_control"] + SUMMARY_VARS
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"STOP: Missing required columns: {missing_cols}"
print(f"All {len(required_cols)} required columns present")

# --- Descriptive Statistics ---
# INTENT: Compute mean, median, and standard deviation for each continuous
# variable within each selectivity band. This table is the primary descriptive
# output characterizing how institutions differ across selectivity levels.
#
# REASONING: Computing all three measures (mean, median, SD) because:
#   - Mean provides the central tendency for symmetric variables
#   - Median provides robustness for skewed variables (e.g., instr_expend_per_fte)
#   - SD characterizes within-band heterogeneity, which matters for
#     interpreting whether selectivity bands are meaningfully distinct
#
# ASSUMES:
#   - selectivity_band column has exactly 4 categories matching BAND_ORDER
#   - completion_rate_150pct is on 0-100 scale (percentage)
#   - pell_share and urm_share are on 0-1 scale (proportions)
#   - No coded missing values remain (Stage 6 cleaned these)

# Build aggregation expressions for all summary variables
agg_exprs = [pl.len().alias("n_institutions")]

for var in SUMMARY_VARS:
    agg_exprs.extend([
        pl.col(var).mean().alias(f"{var}_mean"),
        pl.col(var).median().alias(f"{var}_median"),
        pl.col(var).std().alias(f"{var}_sd"),
    ])

# INTENT: Compute sector composition within each band (count and percentage
# of public, private non-profit, and for-profit institutions).
# REASONING: inst_control uses IPEDS coding: 1=public, 2=private NP, 3=for-profit.
# Sector mix is a key contextual variable — highly selective bands may be
# dominated by private NP institutions, while open bands may include more
# public and for-profit institutions.
# ASSUMES: inst_control values are integers 1, 2, or 3 per IPEDS convention.
agg_exprs.extend([
    (pl.col("inst_control") == 1).sum().alias("n_public"),
    (pl.col("inst_control") == 2).sum().alias("n_private_np"),
    (pl.col("inst_control") == 3).sum().alias("n_for_profit"),
])

descriptive = (
    df
    .group_by("selectivity_band")
    .agg(agg_exprs)
)

# INTENT: Compute sector percentages as derived columns from counts.
# REASONING: Percentages are more interpretable than raw counts for cross-band
# comparison because band sizes differ substantially (HS=71 vs Open=1121).
descriptive = descriptive.with_columns([
    (pl.col("n_public") / pl.col("n_institutions") * 100).round(1).alias("pct_public"),
    (pl.col("n_private_np") / pl.col("n_institutions") * 100).round(1).alias("pct_private_np"),
    (pl.col("n_for_profit") / pl.col("n_institutions") * 100).round(1).alias("pct_for_profit"),
])

# INTENT: Sort by the predefined band order (most to least selective).
# REASONING: Categorical ordering ensures consistent presentation.
# Using a mapping column to sort because Polars does not natively preserve
# ordered categoricals from a group_by.
band_order_map = {band: i for i, band in enumerate(BAND_ORDER)}
descriptive = (
    descriptive
    .with_columns(
        pl.col("selectivity_band")
        .replace_strict(band_order_map, return_dtype=pl.Int32)
        .alias("_sort_order")
    )
    .sort("_sort_order")
    .drop("_sort_order")
)

# --- Display ---
# INTENT: Print a formatted summary table for the execution log so the
# results are captured in the audit trail and can be reviewed without
# re-running the script.
print("\n" + "=" * 60)
print("DESCRIPTIVE STATISTICS BY SELECTIVITY BAND")
print("=" * 60)

for row in descriptive.iter_rows(named=True):
    band = row["selectivity_band"]
    n = row["n_institutions"]
    print(f"\n--- {band} (N={n:,}) ---")

    if n < 100:
        print(f"  ** WARNING: N={n} is below 100; interpret with caution **")

    print(f"  Completion Rate (150%): mean={row['completion_rate_150pct_mean']:.1f}, "
          f"median={row['completion_rate_150pct_median']:.1f}, "
          f"SD={row['completion_rate_150pct_sd']:.1f}")
    print(f"  Admission Rate:         mean={row['admit_rate_mean']:.3f}, "
          f"median={row['admit_rate_median']:.3f}, "
          f"SD={row['admit_rate_sd']:.3f}")
    print(f"  Pell Share:             mean={row['pell_share_mean']:.3f}, "
          f"median={row['pell_share_median']:.3f}, "
          f"SD={row['pell_share_sd']:.3f}")
    print(f"  URM Share:              mean={row['urm_share_mean']:.3f}, "
          f"median={row['urm_share_median']:.3f}, "
          f"SD={row['urm_share_sd']:.3f}")
    print(f"  Student-Faculty Ratio:  mean={row['student_faculty_ratio_mean']:.1f}, "
          f"median={row['student_faculty_ratio_median']:.1f}, "
          f"SD={row['student_faculty_ratio_sd']:.1f}")
    print(f"  Retention Rate:         mean={row['retention_rate_mean']:.1f}, "
          f"median={row['retention_rate_median']:.1f}, "
          f"SD={row['retention_rate_sd']:.1f}")
    print(f"  Instr Expend/FTE:       mean={row['instr_expend_per_fte_mean']:,.0f}, "
          f"median={row['instr_expend_per_fte_median']:,.0f}, "
          f"SD={row['instr_expend_per_fte_sd']:,.0f}")
    print(f"  Sector: Public={row['n_public']} ({row['pct_public']:.1f}%), "
          f"Private NP={row['n_private_np']} ({row['pct_private_np']:.1f}%), "
          f"For-Profit={row['n_for_profit']} ({row['pct_for_profit']:.1f}%)")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
descriptive.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify output exists, has expected structure,
# and values are substantively reasonable.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Output file exists and is non-zero
output_exists = OUTPUT_PATH.exists() and OUTPUT_PATH.stat().st_size > 0
print(f"  [{'PASS' if output_exists else 'FAIL'}] Output exists and non-zero: {OUTPUT_PATH.stat().st_size:,} bytes")
if not output_exists:
    cp4_passed = False

# CP4.2: Exactly 4 rows (one per selectivity band)
n_bands = descriptive.shape[0]
bands_ok = n_bands == 4
print(f"  [{'PASS' if bands_ok else 'FAIL'}] Row count: {n_bands} (expected 4)")
if not bands_ok:
    cp4_passed = False

# CP4.3: All expected bands present
bands_present = set(descriptive["selectivity_band"].to_list())
bands_expected = set(BAND_ORDER)
bands_match = bands_present == bands_expected
print(f"  [{'PASS' if bands_match else 'FAIL'}] All bands present: {sorted(bands_present)}")
if not bands_match:
    cp4_passed = False

# CP4.4: Summary statistics are substantively reasonable
# REASONING: These ranges are based on domain knowledge of U.S. higher education.
# completion_rate_150pct should be 0-100 (percentage scale)
# admit_rate should be 0-1 (proportion)
# pell_share should be 0-1 (proportion)
# urm_share should be 0-1 (proportion)
mean_grad = descriptive["completion_rate_150pct_mean"].to_list()
grad_reasonable = all(0 <= v <= 100 for v in mean_grad if v is not None)
print(f"  [{'PASS' if grad_reasonable else 'FAIL'}] Mean grad rates in 0-100 range: {[round(v, 1) for v in mean_grad]}")
if not grad_reasonable:
    cp4_passed = False

mean_pell = descriptive["pell_share_mean"].to_list()
pell_reasonable = all(0 <= v <= 1 for v in mean_pell if v is not None)
print(f"  [{'PASS' if pell_reasonable else 'FAIL'}] Mean pell_share in 0-1 range: {[round(v, 3) for v in mean_pell]}")
if not pell_reasonable:
    cp4_passed = False

mean_urm = descriptive["urm_share_mean"].to_list()
urm_reasonable = all(0 <= v <= 1 for v in mean_urm if v is not None)
print(f"  [{'PASS' if urm_reasonable else 'FAIL'}] Mean urm_share in 0-1 range: {[round(v, 3) for v in mean_urm]}")
if not urm_reasonable:
    cp4_passed = False

# CP4.5: N per band check (warn if any band < 100)
n_values = descriptive["n_institutions"].to_list()
band_names = descriptive["selectivity_band"].to_list()
all_above_100 = all(n >= 100 for n in n_values)
for band_name, n_val in zip(band_names, n_values):
    if n_val < 100:
        print(f"  [WARN] {band_name}: N={n_val} is below 100 aspiration threshold")
    else:
        print(f"  [PASS] {band_name}: N={n_val}")

# CP4.6: Total N across bands should equal input dataset
total_n = sum(n_values)
total_ok = total_n == pre_rows
print(f"  [{'PASS' if total_ok else 'FAIL'}] Total N across bands: {total_n:,} (expected {pre_rows:,})")
if not total_ok:
    cp4_passed = False

# CP4.7: Grad rate should generally decrease from HS to Open (monotonic tendency)
# REASONING: This is an expected pattern — more selective institutions tend to
# have higher graduation rates. Not a hard requirement but a sanity check.
hs_grad = descriptive.filter(pl.col("selectivity_band") == "Highly Selective")["completion_rate_150pct_mean"][0]
open_grad = descriptive.filter(pl.col("selectivity_band") == "Open/Less Selective")["completion_rate_150pct_mean"][0]
grad_gradient = hs_grad > open_grad
print(f"  [{'PASS' if grad_gradient else 'NOTE'}] Grad rate gradient: HS={hs_grad:.1f} > Open={open_grad:.1f}: {grad_gradient}")

assert cp4_passed, "STOP: CP4 validation failed — see details above"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)



# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:51:08
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage8_analysis/01_descriptive-by-selectivity.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Descriptive Statistics by Selectivity Band
# ============================================================
# Loaded: 1,946 rows x 25 cols
# Pre-state: 1,946 rows, 25 cols
# Columns available: ['unitid', 'inst_name', 'fips', 'inst_control', 'open_public', 'hbcu', 'tribal_college', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admit_rate', 'completion_rate_150pct', 'completers_150pct', 'cohort_adj_150pct', 'grant_recipients', 'sfa_total_students', 'urm_share', 'total_ug_enrollment', 'pell_share', 'student_faculty_ratio', 'retention_rate', 'instr_expend_per_fte', 'selectivity_band', 'pell_quintile', 'urm_quintile']
# All 9 required columns present
# 
# ============================================================
# DESCRIPTIVE STATISTICS BY SELECTIVITY BAND
# ============================================================
# 
# --- Highly Selective (N=71) ---
#   ** WARNING: N=71 is below 100; interpret with caution **
#   Completion Rate (150%): mean=88.3, median=92.3, SD=13.6
#   Admission Rate:         mean=14.535, median=15.119, SD=6.053
#   Pell Share:             mean=0.084, median=0.075, SD=0.043
#   URM Share:              mean=0.213, median=0.214, SD=0.080
#   Student-Faculty Ratio:  mean=8.4, median=8.0, SD=3.8
#   Retention Rate:         mean=89.9, median=92.5, SD=10.2
#   Instr Expend/FTE:       mean=40,020, median=32,046, SD=29,248
#   Sector: Public=9 (12.7%), Private NP=60 (84.5%), For-Profit=2 (2.8%)
# 
# --- Selective (N=177) ---
#   Completion Rate (150%): mean=59.7, median=61.0, SD=24.0
#   Admission Rate:         mean=40.444, median=40.478, SD=6.664
#   Pell Share:             mean=0.109, median=0.099, SD=0.066
#   URM Share:              mean=0.390, median=0.291, SD=0.285
#   Student-Faculty Ratio:  mean=13.1, median=12.0, SD=5.9
#   Retention Rate:         mean=76.7, median=81.0, SD=16.6
#   Instr Expend/FTE:       mean=12,264, median=9,648, SD=8,492
#   Sector: Public=37 (20.9%), Private NP=122 (68.9%), For-Profit=18 (10.2%)
# 
# --- Moderately Selective (N=577) ---
#   Completion Rate (150%): mean=57.6, median=58.9, SD=17.3
#   Admission Rate:         mean=64.423, median=65.301, SD=6.902
#   Pell Share:             mean=0.134, median=0.128, SD=0.068
#   URM Share:              mean=0.296, median=0.227, SD=0.229
#   Student-Faculty Ratio:  mean=13.6, median=13.0, SD=4.2
#   Retention Rate:         mean=75.2, median=76.0, SD=12.0
#   Instr Expend/FTE:       mean=10,832, median=9,688, SD=6,352
#   Sector: Public=157 (27.2%), Private NP=407 (70.5%), For-Profit=13 (2.3%)
# 
# --- Open/Less Selective (N=1,121) ---
#   Completion Rate (150%): mean=51.8, median=52.9, SD=19.7
#   Admission Rate:         mean=86.326, median=85.440, SD=7.455
#   Pell Share:             mean=0.115, median=0.102, SD=0.077
#   URM Share:              mean=0.350, median=0.259, SD=0.282
#   Student-Faculty Ratio:  mean=14.8, median=14.0, SD=5.8
#   Retention Rate:         mean=72.1, median=75.0, SD=14.9
#   Instr Expend/FTE:       mean=9,055, median=8,209, SD=5,929
#   Sector: Public=391 (34.9%), Private NP=613 (54.7%), For-Profit=117 (10.4%)
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/output/analysis/2026-03-29_descriptive_by_selectivity.parquet
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] Output exists and non-zero: 11,362 bytes
#   [PASS] Row count: 4 (expected 4)
#   [PASS] All bands present: ['Highly Selective', 'Moderately Selective', 'Open/Less Selective', 'Selective']
#   [PASS] Mean grad rates in 0-100 range: [88.3, 59.7, 57.6, 51.8]
#   [PASS] Mean pell_share in 0-1 range: [0.084, 0.109, 0.134, 0.115]
#   [PASS] Mean urm_share in 0-1 range: [0.213, 0.39, 0.296, 0.35]
#   [WARN] Highly Selective: N=71 is below 100 aspiration threshold
#   [PASS] Selective: N=177
#   [PASS] Moderately Selective: N=577
#   [PASS] Open/Less Selective: N=1121
#   [PASS] Total N across bands: 1,946 (expected 1,946)
#   [PASS] Grad rate gradient: HS=88.3 > Open=51.8: True
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
