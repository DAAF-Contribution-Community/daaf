#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 07 — sector-comparison (QA4a)

Reviewed script: scripts/stage8_analysis/07_sector-comparison.py
Output files: output/analysis/2026-03-29_sector_comparison.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan_Tasks expectations (26 columns)
2. Row count = 3 (one per sector)
3. N sums to 1,946 (total input rows)
4. No suspicious distributions
5. Coded values properly handled
6. Critical columns non-null
--- Script-specific checks (Five Lenses) ---
7. COUNTERFACTUAL: Verify completion_rate and admit_rate scale consistency
8. SEMANTIC: Verify for-profit Pell share makes domain sense
9. BOUNDARY: Check for-profit N threshold logic at N=150 (>>30)
10. ABSENCE: Verify all 7 summary vars present with mean/median/SD
11. DOWNSTREAM: Verify viz-sector-comparison can consume this output
--- Spot-checks ---
12. Trace for-profit correlation manually via source data
13. Verify N per sector sums across band distribution
14. Check that band_distribution strings parse correctly
15. Verify sector labels are exactly the expected values
16. Cross-check public sector admit_rate mean against source data
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_sector_comparison.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

EXPECTED_COLUMNS_BASE = ["sector_label", "n"]
SUMMARY_VARS = [
    "completion_rate_150pct", "admit_rate", "pell_share", "urm_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte",
]
# Each summary var gets _mean, _median, _sd
EXPECTED_STATS_COLS = []
for var in SUMMARY_VARS:
    EXPECTED_STATS_COLS.extend([f"{var}_mean", f"{var}_median", f"{var}_sd"])
EXPECTED_COLUMNS = EXPECTED_COLUMNS_BASE + EXPECTED_STATS_COLS + ["pearson_r", "n_valid", "band_distribution"]

EXPECTED_ROWS = 3  # 3 sectors (FP N=150 >= 30)
EXPECTED_TOTAL_N = 1946
CRITICAL_COLUMNS = ["sector_label", "n", "completion_rate_150pct_mean", "admit_rate_mean", "pearson_r"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output + source data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 07 — sector-comparison")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

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
    print(f"  Extra columns (not expected): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count} (expected {EXPECTED_ROWS})")

# --- Check 3: N sums to total ---
n_sum = df["n"].sum()
n_ok = n_sum == EXPECTED_TOTAL_N
print(f"[{'PASS' if n_ok else 'FAIL'}] N sums to total: {n_sum:,} (expected {EXPECTED_TOTAL_N:,})")

# --- Check 4: Distribution sanity ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 1:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'WARN'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 5: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in CODED_MISSING_VALUES:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 6: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# ===========================================================================
# Script-specific checks (Five Skeptical Lenses)
# ===========================================================================

# --- Check 7: COUNTERFACTUAL — Scale consistency ---
# The script's CP4 check used a 0-1.5 range for completion_rate and admit_rate
# means, but the execution log showed values ~45-75, suggesting percentage (0-100)
# scale. Verify the actual scale of these variables in the source data.
print(f"\n--- COUNTERFACTUAL: Scale consistency ---")
cr_vals = src["completion_rate_150pct"].drop_nulls()
ar_vals = src["admit_rate"].drop_nulls()
print(f"Source completion_rate_150pct: min={cr_vals.min():.2f}, max={cr_vals.max():.2f}, mean={cr_vals.mean():.2f}")
print(f"Source admit_rate: min={ar_vals.min():.4f}, max={ar_vals.max():.4f}, mean={ar_vals.mean():.4f}")

# Check if output means match the source scale
out_cr_means = df["completion_rate_150pct_mean"].to_list()
out_ar_means = df["admit_rate_mean"].to_list()
scale_issue = False
for v in out_cr_means:
    if v is not None and v > 1.5:
        # percentage scale, not proportion
        scale_issue = True
        break
for v in out_ar_means:
    if v is not None and v > 1.5:
        scale_issue = True
        break

if scale_issue:
    # This means the CP4 range check in the script was miscalibrated — it warned
    # on percentage-scale data that is actually correct
    print(f"[INFO] Data is in PERCENTAGE scale (0-100), not proportion (0-1).")
    print(f"  Script's CP4 range check (0, 1.5) flagged all sectors spuriously.")
    print(f"  This is NOT a data error — the CP4 check was miscalibrated.")
    # Verify means are in 0-100 range
    for i, row in enumerate(df.iter_rows(named=True)):
        cr = row["completion_rate_150pct_mean"]
        ar = row["admit_rate_mean"]
        if cr is not None and (cr < 0 or cr > 100):
            print(f"  [FAIL] {row['sector_label']}: completion_rate mean {cr:.2f} outside 0-100")
        if ar is not None and (ar < 0 or ar > 100):
            print(f"  [FAIL] {row['sector_label']}: admit_rate mean {ar:.2f} outside 0-100")
    print(f"  [PASS] All means within valid 0-100 percentage range")
else:
    print(f"[PASS] Scale consistency: data in proportion scale (0-1)")

# --- Check 8: SEMANTIC — For-profit Pell share ---
# For-profit institutions are well-known for having high Pell shares (often 60-80%).
# The script output shows pell_share mean = 0.0817 for for-profit. This seems
# extremely low. Investigate whether pell_share is computed correctly.
print(f"\n--- SEMANTIC: For-profit Pell share domain plausibility ---")
fp_row = df.filter(pl.col("sector_label") == "Private For-Profit")
fp_pell = fp_row["pell_share_mean"].item()
print(f"For-profit pell_share mean: {fp_pell:.4f}")
# Check actual source data
fp_src = src.filter(pl.col("inst_control") == 3)
print(f"For-profit institutions in source: {fp_src.shape[0]}")
fp_pell_src = fp_src["pell_share"].drop_nulls()
print(f"For-profit pell_share from source: min={fp_pell_src.min():.4f}, max={fp_pell_src.max():.4f}, "
      f"mean={fp_pell_src.mean():.4f}, median={fp_pell_src.median():.4f}")
print(f"For-profit pell_share distribution:")
print(f"  < 0.10: {(fp_pell_src < 0.10).sum()}")
print(f"  0.10-0.50: {((fp_pell_src >= 0.10) & (fp_pell_src < 0.50)).sum()}")
print(f"  0.50-0.80: {((fp_pell_src >= 0.50) & (fp_pell_src < 0.80)).sum()}")
print(f"  >= 0.80: {(fp_pell_src >= 0.80).sum()}")
print(f"  null: {fp_src['pell_share'].null_count()}")
# Also check what pell_share values look like across all sectors
for ctrl, label in [(1, "Public"), (2, "Private NP"), (3, "Private FP")]:
    sector_src = src.filter(pl.col("inst_control") == ctrl)
    ps = sector_src["pell_share"].drop_nulls()
    print(f"  {label}: N={len(ps)}, mean={ps.mean():.4f}, median={ps.median():.4f}")

# Flag if for-profit pell_share is unreasonably low
if fp_pell < 0.30:
    print(f"[WARN] For-profit pell_share mean ({fp_pell:.4f}) is much lower than typical (~0.60-0.80)")
    print(f"  This may indicate pell_share was computed differently than expected, OR")
    print(f"  the 4-year degree-granting filter excludes most high-Pell FP institutions")
else:
    print(f"[PASS] For-profit pell_share ({fp_pell:.4f}) within expected domain range")

# --- Check 9: BOUNDARY — For-profit N threshold ---
# Risk register: collapse if N < 30. Here N=150. Check edge case reasoning.
print(f"\n--- BOUNDARY: For-profit N threshold ---")
fp_n = fp_row["n"].item()
print(f"For-profit N = {fp_n}")
print(f"Threshold = 30")
print(f"Collapse triggered: {fp_n < 30}")
# Also check: how many FP institutions have valid admit_rate AND completion_rate?
fp_valid_n = fp_row["n_valid"].item()
print(f"For-profit N with valid correlation data: {fp_valid_n}")
# With only 52 valid, the correlation is based on just 1/3 of FP institutions
if fp_valid_n < fp_n * 0.5:
    print(f"[WARN] Only {fp_valid_n}/{fp_n} ({fp_valid_n/fp_n*100:.0f}%) FP institutions "
          f"have valid admit_rate + completion_rate for correlation")
    print(f"  Correlation r=+0.2564 based on subset — may not represent full FP sector")
else:
    print(f"[PASS] Sufficient valid observations for FP correlation")

# --- Check 10: ABSENCE — All 7 summary vars with mean/median/SD ---
print(f"\n--- ABSENCE: Summary variable completeness ---")
missing_stats = []
for var in SUMMARY_VARS:
    for stat in ["mean", "median", "sd"]:
        col_name = f"{var}_{stat}"
        if col_name not in df.columns:
            missing_stats.append(col_name)
        else:
            # Check if any sector has null for this stat
            null_ct = df[col_name].null_count()
            if null_ct > 0:
                missing_stats.append(f"{col_name} has {null_ct} null(s)")
if not missing_stats:
    print(f"[PASS] All 7 vars x 3 stats = 21 statistics present and non-null")
else:
    print(f"[WARN] Missing or null statistics: {missing_stats}")

# --- Check 11: DOWNSTREAM — viz-sector-comparison consumability ---
# Task 10.5 viz-sector-comparison depends on this output. It needs sector_label
# and the analysis dataset. Check output is self-consistent.
print(f"\n--- DOWNSTREAM: Output consumability ---")
downstream_ok = True
# Sector labels must be valid strings
sector_labels = df["sector_label"].to_list()
print(f"Sector labels in output: {sector_labels}")
expected_labels = ["Private For-Profit", "Private Nonprofit", "Public"]
if sorted(sector_labels) != sorted(expected_labels):
    print(f"[WARN] Sector labels don't match expected: {expected_labels}")
    downstream_ok = False
# band_distribution must be parseable
for row in df.iter_rows(named=True):
    bd = row["band_distribution"]
    if bd is None or len(bd) == 0:
        print(f"[FAIL] {row['sector_label']}: band_distribution is empty/null")
        downstream_ok = False
    else:
        # Parse "Band:XX.X%; Band:XX.X%"
        parts = bd.split("; ")
        if len(parts) < 2:
            print(f"[WARN] {row['sector_label']}: band_distribution has only {len(parts)} band(s)")
if downstream_ok:
    print(f"[PASS] Output consumable by downstream viz task")

# ===========================================================================
# Spot-checks
# ===========================================================================

# --- Spot-check 12: Manually verify FP correlation ---
print(f"\n--- SPOT-CHECK: For-profit correlation manual verification ---")
fp_source = src.filter(pl.col("inst_control") == 3).drop_nulls(subset=["admit_rate", "completion_rate_150pct"])
print(f"For-profit valid rows from source: {fp_source.shape[0]}")
if fp_source.shape[0] >= 10:
    x = fp_source["admit_rate"].to_numpy().astype(float)
    y = fp_source["completion_rate_150pct"].to_numpy().astype(float)
    r_manual = float(np.corrcoef(x, y)[0, 1])
    r_output = df.filter(pl.col("sector_label") == "Private For-Profit")["pearson_r"].item()
    print(f"Manual r = {r_manual:.6f}, Output r = {r_output:.6f}")
    diff = abs(r_manual - r_output)
    print(f"[{'PASS' if diff < 0.0001 else 'FAIL'}] Correlation difference: {diff:.8f}")

# --- Spot-check 13: Band distribution N sums within sector ---
print(f"\n--- SPOT-CHECK: Band distribution N consistency ---")
for row in df.iter_rows(named=True):
    bd = row["band_distribution"]
    sector = row["sector_label"]
    n_sector = row["n"]
    # Parse percentages from "Band:XX.X%"
    parts = bd.split("; ")
    pct_sum = 0
    for part in parts:
        pct_str = part.split(":")[1].replace("%", "")
        pct_sum += float(pct_str)
    pct_ok = abs(pct_sum - 100.0) < 1.0  # Allow rounding
    print(f"  {sector}: band pct sum = {pct_sum:.1f}% [{'PASS' if pct_ok else 'FAIL'}]")

# --- Spot-check 14: Verify public sector mean completion_rate independently ---
print(f"\n--- SPOT-CHECK: Public sector completion_rate mean ---")
pub_src = src.filter(pl.col("inst_control") == 1)
pub_cr_mean = pub_src["completion_rate_150pct"].mean()
pub_cr_out = df.filter(pl.col("sector_label") == "Public")["completion_rate_150pct_mean"].item()
diff = abs(pub_cr_mean - pub_cr_out)
print(f"Source mean: {pub_cr_mean:.4f}, Output mean: {pub_cr_out:.4f}, Diff: {diff:.6f}")
print(f"[{'PASS' if diff < 0.001 else 'FAIL'}] Public completion_rate mean matches source")

# --- Spot-check 15: Verify sector N matches source inst_control ---
print(f"\n--- SPOT-CHECK: Sector N matches source inst_control counts ---")
for ctrl, label in [(1, "Public"), (2, "Private Nonprofit"), (3, "Private For-Profit")]:
    src_n = src.filter(pl.col("inst_control") == ctrl).shape[0]
    out_n = df.filter(pl.col("sector_label") == label)["n"].item()
    match = src_n == out_n
    print(f"  {label}: source={src_n}, output={out_n} [{'PASS' if match else 'FAIL'}]")

# --- Spot-check 16: Verify std() calculation is sample SD (ddof=1) ---
print(f"\n--- SPOT-CHECK: SD uses sample standard deviation (ddof=1) ---")
pub_cr_vals = pub_src["completion_rate_150pct"].drop_nulls().to_numpy().astype(float)
np_sd_ddof1 = float(np.std(pub_cr_vals, ddof=1))
np_sd_ddof0 = float(np.std(pub_cr_vals, ddof=0))
polars_sd = df.filter(pl.col("sector_label") == "Public")["completion_rate_150pct_sd"].item()
print(f"  numpy ddof=1: {np_sd_ddof1:.4f}")
print(f"  numpy ddof=0: {np_sd_ddof0:.4f}")
print(f"  polars .std(): {polars_sd:.4f}")
ddof1_match = abs(np_sd_ddof1 - polars_sd) < 0.01
ddof0_match = abs(np_sd_ddof0 - polars_sd) < 0.01
if ddof1_match:
    print(f"[PASS] Polars .std() uses ddof=1 (sample SD) as expected")
elif ddof0_match:
    print(f"[INFO] Polars .std() uses ddof=0 (population SD)")
else:
    print(f"[WARN] SD doesn't match either ddof=0 or ddof=1")

# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 60)
print("QA RESULT SUMMARY")
print("=" * 60)

all_base_passed = all([schema_ok, rows_ok, n_ok, dist_ok, coded_ok, nulls_ok])
print(f"Base checks: {'PASSED' if all_base_passed else 'ISSUES FOUND'}")
print(f"Note: CP4 range check was miscalibrated (0-1.5 for percentage-scale data)")
print(f"Note: For-profit pell_share and correlation validity require domain review")

# ===========================================================================
# Data Profiling
# ===========================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull output DataFrame:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nSector labels:")
print(df["sector_label"].value_counts())

print("\nCorrelation results:")
for row in df.iter_rows(named=True):
    print(f"  {row['sector_label']}: r={row['pearson_r']}, n_valid={row['n_valid']}")

print("\nBand distributions:")
for row in df.iter_rows(named=True):
    print(f"  {row['sector_label']}: {row['band_distribution']}")

# Cross-check: completion_rate means in context
print("\nCompletion rate means across sectors (for reasonableness):")
for row in df.iter_rows(named=True):
    print(f"  {row['sector_label']}: mean={row['completion_rate_150pct_mean']:.1f}, "
          f"median={row['completion_rate_150pct_median']:.1f}, SD={row['completion_rate_150pct_sd']:.1f}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:34:19
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_07_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 07 — sector-comparison
# ============================================================
# Loaded output: 3 rows x 26 cols
# Loaded source: 1,946 rows x 25 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 3 (expected 3)
# [PASS] N sums to total: 1,946 (expected 1,946)
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- COUNTERFACTUAL: Scale consistency ---
# Source completion_rate_150pct: min=3.80, max=100.00, mean=55.56
# Source admit_rate: min=0.0000, max=100.0000, mean=70.4144
# [INFO] Data is in PERCENTAGE scale (0-100), not proportion (0-1).
#   Script's CP4 range check (0, 1.5) flagged all sectors spuriously.
#   This is NOT a data error — the CP4 check was miscalibrated.
#   [PASS] All means within valid 0-100 percentage range
# 
# --- SEMANTIC: For-profit Pell share domain plausibility ---
# For-profit pell_share mean: 0.0817
# For-profit institutions in source: 150
# For-profit pell_share from source: min=0.0001, max=0.5381, mean=0.0817, median=0.0497
# For-profit pell_share distribution:
#   < 0.10: 102
#   0.10-0.50: 34
#   0.50-0.80: 2
#   >= 0.80: 0
#   null: 12
#   Public: N=589, mean=0.0843, median=0.0791
#   Private NP: N=1160, mean=0.1412, median=0.1376
#   Private FP: N=138, mean=0.0817, median=0.0497
# [WARN] For-profit pell_share mean (0.0817) is much lower than typical (~0.60-0.80)
#   This may indicate pell_share was computed differently than expected, OR
#   the 4-year degree-granting filter excludes most high-Pell FP institutions
# 
# --- BOUNDARY: For-profit N threshold ---
# For-profit N = 150
# Threshold = 30
# Collapse triggered: False
# For-profit N with valid correlation data: 52
# [WARN] Only 52/150 (35%) FP institutions have valid admit_rate + completion_rate for correlation
#   Correlation r=+0.2564 based on subset — may not represent full FP sector
# 
# --- ABSENCE: Summary variable completeness ---
# [PASS] All 7 vars x 3 stats = 21 statistics present and non-null
# 
# --- DOWNSTREAM: Output consumability ---
# Sector labels in output: ['Private For-Profit', 'Private Nonprofit', 'Public']
# [PASS] Output consumable by downstream viz task
# 
# --- SPOT-CHECK: For-profit correlation manual verification ---
# For-profit valid rows from source: 52
# Manual r = 0.256359, Output r = 0.256359
# [PASS] Correlation difference: 0.00000000
# 
# --- SPOT-CHECK: Band distribution N consistency ---
#   Private For-Profit: band pct sum = 100.0% [PASS]
#   Private Nonprofit: band pct sum = 100.0% [PASS]
#   Public: band pct sum = 99.9% [PASS]
# 
# --- SPOT-CHECK: Public sector completion_rate mean ---
# Source mean: 52.7754, Output mean: 52.7754, Diff: 0.000000
# [PASS] Public completion_rate mean matches source
# 
# --- SPOT-CHECK: Sector N matches source inst_control counts ---
#   Public: source=594, output=594 [PASS]
#   Private Nonprofit: source=1202, output=1202 [PASS]
#   Private For-Profit: source=150, output=150 [PASS]
# 
# --- SPOT-CHECK: SD uses sample standard deviation (ddof=1) ---
#   numpy ddof=1: 17.4714
#   numpy ddof=0: 17.4567
#   polars .std(): 17.4714
# [PASS] Polars .std() uses ddof=1 (sample SD) as expected
# 
# ============================================================
# QA RESULT SUMMARY
# ============================================================
# Base checks: PASSED
# Note: CP4 range check was miscalibrated (0-1.5 for percentage-scale data)
# Note: For-profit pell_share and correlation validity require domain review
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full output DataFrame:
# shape: (3, 26)
# ┌─────────────┬──────┬────────────┬────────────┬───┬────────────┬───────────┬─────────┬────────────┐
# │ sector_labe ┆ n    ┆ completion ┆ completion ┆ … ┆ instr_expe ┆ pearson_r ┆ n_valid ┆ band_distr │
# │ l           ┆ ---  ┆ _rate_150p ┆ _rate_150p ┆   ┆ nd_per_fte ┆ ---       ┆ ---     ┆ ibution    │
# │ ---         ┆ u32  ┆ ct_mean    ┆ ct_median  ┆   ┆ _sd        ┆ f64       ┆ i64     ┆ ---        │
# │ str         ┆      ┆ ---        ┆ ---        ┆   ┆ ---        ┆           ┆         ┆ str        │
# │             ┆      ┆ f64        ┆ f64        ┆   ┆ f64        ┆           ┆         ┆            │
# ╞═════════════╪══════╪════════════╪════════════╪═══╪════════════╪═══════════╪═════════╪════════════╡
# │ Private     ┆ 150  ┆ 45.596     ┆ 40.0       ┆ … ┆ 4785.52906 ┆ 0.256359  ┆ 52      ┆ Highly Sel │
# │ For-Profit  ┆      ┆            ┆            ┆   ┆ 1          ┆           ┆         ┆ ective:1.3 │
# │             ┆      ┆            ┆            ┆   ┆            ┆           ┆         ┆ %;         │
# │             ┆      ┆            ┆            ┆   ┆            ┆           ┆         ┆ Moderat…   │
# │ Private     ┆ 1202 ┆ 58.172213  ┆ 59.7       ┆ … ┆ 12086.0786 ┆ -0.334851 ┆ 1048    ┆ Highly Sel │
# │ Nonprofit   ┆      ┆            ┆            ┆   ┆ 88         ┆           ┆         ┆ ective:5.0 │
# │             ┆      ┆            ┆            ┆   ┆            ┆           ┆         ┆ %;         │
# │             ┆      ┆            ┆            ┆   ┆            ┆           ┆         ┆ Moderat…   │
# │ Public      ┆ 594  ┆ 52.775421  ┆ 52.1       ┆ … ┆ 5304.93538 ┆ -0.368273 ┆ 525     ┆ Highly Sel │
# │             ┆      ┆            ┆            ┆   ┆ 8          ┆           ┆         ┆ ective:1.5 │
# │             ┆      ┆            ┆            ┆   ┆            ┆           ┆         ┆ %;         │
# │             ┆      ┆            ┆            ┆   ┆            ┆           ┆         ┆ Moderat…   │
# └─────────────┴──────┴────────────┴────────────┴───┴────────────┴───────────┴─────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 27)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ sector_la ┆ n         ┆ completio ┆ … ┆ instr_exp ┆ pearson_r ┆ n_valid   ┆ band_dis │
# │ ---       ┆ bel       ┆ ---       ┆ n_rate_15 ┆   ┆ end_per_f ┆ ---       ┆ ---       ┆ tributio │
# │ str       ┆ ---       ┆ f64       ┆ 0pct_mean ┆   ┆ te_sd     ┆ f64       ┆ f64       ┆ n        │
# │           ┆ str       ┆           ┆ ---       ┆   ┆ ---       ┆           ┆           ┆ ---      │
# │           ┆           ┆           ┆ f64       ┆   ┆ f64       ┆           ┆           ┆ str      │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 3         ┆ 3.0       ┆ 3.0       ┆ … ┆ 3.0       ┆ 3.0       ┆ 3.0       ┆ 3        │
# │ null_coun ┆ 0         ┆ 0.0       ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0        │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ null      ┆ 648.66666 ┆ 52.181211 ┆ … ┆ 7392.1810 ┆ -0.148922 ┆ 541.66666 ┆ null     │
# │           ┆           ┆ 7         ┆           ┆   ┆ 46        ┆           ┆ 7         ┆          │
# │ std       ┆ null      ┆ 528.12624 ┆ 6.309128  ┆ … ┆ 4073.3219 ┆ 0.351381  ┆ 498.20912 ┆ null     │
# │           ┆           ┆ 8         ┆           ┆   ┆ 91        ┆           ┆ 6         ┆          │
# │ min       ┆ Private   ┆ 150.0     ┆ 45.596    ┆ … ┆ 4785.5290 ┆ -0.368273 ┆ 52.0      ┆ Highly   │
# │           ┆ For-Profi ┆           ┆           ┆   ┆ 61        ┆           ┆           ┆ Selectiv │
# │           ┆ t         ┆           ┆           ┆   ┆           ┆           ┆           ┆ e:1.3%;  │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ Moderat… │
# │ 25%       ┆ null      ┆ 594.0     ┆ 52.775421 ┆ … ┆ 5304.9353 ┆ -0.334851 ┆ 525.0     ┆ null     │
# │           ┆           ┆           ┆           ┆   ┆ 88        ┆           ┆           ┆          │
# │ 50%       ┆ null      ┆ 594.0     ┆ 52.775421 ┆ … ┆ 5304.9353 ┆ -0.334851 ┆ 525.0     ┆ null     │
# │           ┆           ┆           ┆           ┆   ┆ 88        ┆           ┆           ┆          │
# │ 75%       ┆ null      ┆ 1202.0    ┆ 58.172213 ┆ … ┆ 12086.078 ┆ 0.256359  ┆ 1048.0    ┆ null     │
# │           ┆           ┆           ┆           ┆   ┆ 688       ┆           ┆           ┆          │
# │ max       ┆ Public    ┆ 1202.0    ┆ 58.172213 ┆ … ┆ 12086.078 ┆ 0.256359  ┆ 1048.0    ┆ Highly   │
# │           ┆           ┆           ┆           ┆   ┆ 688       ┆           ┆           ┆ Selectiv │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ e:5.0%;  │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ Moderat… │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Sector labels:
# shape: (3, 2)
# ┌────────────────────┬───────┐
# │ sector_label       ┆ count │
# │ ---                ┆ ---   │
# │ str                ┆ u32   │
# ╞════════════════════╪═══════╡
# │ Public             ┆ 1     │
# │ Private For-Profit ┆ 1     │
# │ Private Nonprofit  ┆ 1     │
# └────────────────────┴───────┘
# 
# Correlation results:
#   Private For-Profit: r=0.25635876479630865, n_valid=52
#   Private Nonprofit: r=-0.3348514791058042, n_valid=1048
#   Public: r=-0.36827342787210837, n_valid=525
# 
# Band distributions:
#   Private For-Profit: Highly Selective:1.3%; Moderately Selective:8.7%; Open/Less Selective:78.0%; Selective:12.0%
#   Private Nonprofit: Highly Selective:5.0%; Moderately Selective:33.9%; Open/Less Selective:51.0%; Selective:10.1%
#   Public: Highly Selective:1.5%; Moderately Selective:26.4%; Open/Less Selective:65.8%; Selective:6.2%
# 
# Completion rate means across sectors (for reasonableness):
#   Private For-Profit: mean=45.6, median=40.0, SD=26.9
#   Private Nonprofit: mean=58.2, median=59.7, SD=20.5
#   Public: mean=52.8, median=52.1, SD=17.5
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
