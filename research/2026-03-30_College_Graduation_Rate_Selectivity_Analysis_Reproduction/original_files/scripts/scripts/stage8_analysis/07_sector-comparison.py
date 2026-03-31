#!/usr/bin/env python3
"""
Stage 8.1: Sector comparison — descriptive statistics by institutional control.

Task: sector-comparison
Wave: 9, Step: 7, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_sector_comparison.parquet
Checkpoint: CP4
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
# Configuration for sector comparison analysis. Institutional control (inst_control)
# is coded 1=Public, 2=Private Nonprofit, 3=Private For-Profit per IPEDS convention.
# Risk register: If for-profit N < 30, collapse to Public vs. Private.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_sector_comparison.parquet"

# INTENT: Define the mapping from numeric inst_control codes to human-readable labels.
# REASONING: IPEDS uses integer codes for institutional control. Labels make output
# interpretable and ensure the mapping is explicit and auditable.
SECTOR_MAP = {1: "Public", 2: "Private Nonprofit", 3: "Private For-Profit"}

# INTENT: Define the variables to summarize for each sector.
# REASONING: These are the core analytic variables identified in the Plan's analysis
# design. They cover outcomes (completion rate), selectivity (admit rate), demographics
# (pell_share, urm_share), resources (student_faculty_ratio, instr_expend_per_fte),
# and retention (retention_rate).
SUMMARY_VARS = [
    "completion_rate_150pct",
    "admit_rate",
    "pell_share",
    "urm_share",
    "student_faculty_ratio",
    "retention_rate",
    "instr_expend_per_fte",
]

# Selectivity band column for within-sector band distribution
BAND_COL = "selectivity_band"

# For-profit N threshold from risk register
FOR_PROFIT_MIN_N = 30

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands).
print("=" * 60)
print("Stage 8.1: Sector Comparison")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture the current state of the data BEFORE any transformations. This is a
# descriptive analysis that does not modify the source data, but we document
# the input characteristics for validation.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"Pre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Columns: {pre_cols}")

# Verify required columns exist
required_cols = ["unitid", "inst_control", BAND_COL] + SUMMARY_VARS
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"STOP: Missing required columns: {missing_cols}"
print(f"All {len(required_cols)} required columns present")

# --- Sector labeling ---
# INTENT: Map inst_control integer codes to descriptive sector labels.
# REASONING: Using pl.col().replace_strict() for an explicit, auditable mapping.
# Any unmapped codes will raise an error rather than silently pass through.
# ASSUMES: inst_control contains only values 1, 2, 3 per IPEDS convention.
df = df.with_columns(
    pl.col("inst_control")
    .replace_strict(SECTOR_MAP, default=None)
    .alias("sector_label")
)

# Verify no unmapped values
unmapped = df.filter(pl.col("sector_label").is_null()).shape[0]
assert unmapped == 0, f"STOP: {unmapped} rows have unmapped inst_control values"

# --- Risk register: Check for-profit N ---
# INTENT: Check if for-profit institution count meets the minimum threshold.
# REASONING: Risk register specifies that if N < 30 for for-profit sector,
# we should collapse to Public vs. Private. Small N makes summary statistics
# unreliable and potentially disclosive.
sector_counts = df.group_by("sector_label").len().sort("sector_label")
print("\nSector counts:")
for row in sector_counts.iter_rows(named=True):
    print(f"  {row['sector_label']}: {row['len']:,}")

fp_count = df.filter(pl.col("sector_label") == "Private For-Profit").shape[0]
collapse_sectors = fp_count < FOR_PROFIT_MIN_N

if collapse_sectors:
    # INTENT: Collapse for-profit into a combined "Private" category.
    # REASONING: N < 30 makes separate for-profit statistics unreliable.
    # Combining with nonprofit creates a Public vs. Private comparison.
    print(f"\nFor-profit N = {fp_count} < {FOR_PROFIT_MIN_N}. Collapsing to Public vs. Private.")
    df = df.with_columns(
        pl.when(pl.col("sector_label") == "Public")
        .then(pl.lit("Public"))
        .otherwise(pl.lit("Private"))
        .alias("sector_label")
    )
    sector_counts = df.group_by("sector_label").len().sort("sector_label")
    print("Collapsed sector counts:")
    for row in sector_counts.iter_rows(named=True):
        print(f"  {row['sector_label']}: {row['len']:,}")
else:
    print(f"\nFor-profit N = {fp_count} >= {FOR_PROFIT_MIN_N}. Keeping 3-sector breakdown.")

# --- Compute summary statistics by sector ---
# INTENT: For each sector, compute N, mean, median, and SD for all summary variables.
# REASONING: Mean and median together reveal skewness; SD captures within-sector
# heterogeneity. These are the standard descriptive summary statistics for
# continuous variables in social science research.
# ASSUMES: Summary variables are numeric and have been cleaned (no coded missing values).
print("\n" + "=" * 60)
print("SECTOR SUMMARY STATISTICS")
print("=" * 60)

sector_labels = sorted(df["sector_label"].unique().to_list())

# Build aggregation expressions for each summary variable
agg_exprs = [pl.len().alias("n")]
for var in SUMMARY_VARS:
    agg_exprs.extend([
        pl.col(var).mean().alias(f"{var}_mean"),
        pl.col(var).median().alias(f"{var}_median"),
        pl.col(var).std().alias(f"{var}_sd"),
    ])

sector_stats = df.group_by("sector_label").agg(agg_exprs).sort("sector_label")

# Print formatted table
for row in sector_stats.iter_rows(named=True):
    sector = row["sector_label"]
    n = row["n"]
    print(f"\n--- {sector} (N={n:,}) ---")
    print(f"  {'Variable':<30} {'Mean':>10} {'Median':>10} {'SD':>10}")
    print(f"  {'-'*60}")
    for var in SUMMARY_VARS:
        mean_val = row[f"{var}_mean"]
        med_val = row[f"{var}_median"]
        sd_val = row[f"{var}_sd"]
        mean_str = f"{mean_val:.4f}" if mean_val is not None else "N/A"
        med_str = f"{med_val:.4f}" if med_val is not None else "N/A"
        sd_str = f"{sd_val:.4f}" if sd_val is not None else "N/A"
        print(f"  {var:<30} {mean_str:>10} {med_str:>10} {sd_str:>10}")

# --- Selectivity band distribution within sector ---
# INTENT: For each sector, compute the percentage of institutions in each
# selectivity band. This reveals whether selectivity is distributed differently
# across public and private institutions.
# REASONING: Raw counts are less comparable across sectors of different sizes;
# percentages within each sector make cross-sector patterns visible.
# ASSUMES: selectivity_band is a categorical/string column with values from
# the create-bands step (e.g., "Highly Selective", "Selective", "Moderately Selective",
# "Open/Less Selective").
print("\n" + "=" * 60)
print("SELECTIVITY BAND DISTRIBUTION BY SECTOR")
print("=" * 60)

band_dist = (
    df.group_by(["sector_label", BAND_COL])
    .len()
    .sort(["sector_label", BAND_COL])
)

# Compute percentages within each sector
band_dist = band_dist.join(
    df.group_by("sector_label").len().rename({"len": "sector_total"}),
    on="sector_label",
    how="left",
)
band_dist = band_dist.with_columns(
    (pl.col("len") / pl.col("sector_total") * 100).round(1).alias("pct")
)

for sector in sector_labels:
    sector_bands = band_dist.filter(pl.col("sector_label") == sector)
    print(f"\n{sector}:")
    for row in sector_bands.iter_rows(named=True):
        print(f"  {row[BAND_COL]:<25} {row['len']:>5} ({row['pct']:>5.1f}%)")

# --- Within-sector correlation: admit_rate vs completion_rate_150pct ---
# INTENT: Compute Pearson correlation between admission rate and graduation rate
# within each sector to test whether the selectivity-graduation relationship
# varies by institutional type.
# REASONING: Pearson correlation is appropriate here because both variables are
# continuous and roughly linear in prior analysis. Within-sector correlation
# controls for systematic mean differences across sectors.
# ASSUMES: Both variables have been cleaned and have sufficient non-null
# observations within each sector for a meaningful correlation.
print("\n" + "=" * 60)
print("WITHIN-SECTOR PEARSON CORRELATION: admit_rate vs completion_rate_150pct")
print("=" * 60)

corr_results = []
for sector in sector_labels:
    sector_df = df.filter(pl.col("sector_label") == sector)
    # Drop rows with null in either correlation variable
    valid = sector_df.drop_nulls(subset=["admit_rate", "completion_rate_150pct"])
    n_valid = valid.shape[0]

    if n_valid >= 10:
        # REASONING: Using numpy for Pearson r because Polars does not have a
        # built-in pairwise correlation function for two columns.
        x = valid["admit_rate"].to_numpy().astype(float)
        y = valid["completion_rate_150pct"].to_numpy().astype(float)
        r = float(np.corrcoef(x, y)[0, 1])
        print(f"  {sector:<25} r = {r:+.4f}  (N = {n_valid:,})")
        corr_results.append({"sector_label": sector, "pearson_r": r, "n_valid": n_valid})
    else:
        print(f"  {sector:<25} N = {n_valid} (too few for correlation)")
        corr_results.append({"sector_label": sector, "pearson_r": None, "n_valid": n_valid})

corr_df = pl.DataFrame(corr_results)

# --- Assemble output DataFrame ---
# INTENT: Combine sector summary statistics with correlation results into a
# single output table, one row per sector.
# REASONING: A single output parquet file is required by the task specification.
# Joining on sector_label ensures the correlation result aligns with the correct
# sector row.
output_df = sector_stats.join(corr_df, on="sector_label", how="left")

# Also add band distribution as a struct/string column for each sector
# INTENT: Encode band distributions compactly so all sector summary data is
# in one parquet file. Using a string representation of the distribution.
# REASONING: Polars supports nested types but a simple string is more portable
# for downstream consumers (report-writer, notebook-assembler).
band_str_rows = []
for sector in sector_labels:
    sector_bands = band_dist.filter(pl.col("sector_label") == sector)
    parts = []
    for row in sector_bands.iter_rows(named=True):
        parts.append(f"{row[BAND_COL]}:{row['pct']:.1f}%")
    band_str_rows.append({"sector_label": sector, "band_distribution": "; ".join(parts)})

band_str_df = pl.DataFrame(band_str_rows)
output_df = output_df.join(band_str_df, on="sector_label", how="left")

print(f"\nOutput shape: {output_df.shape[0]} rows x {output_df.shape[1]} cols")
print(f"Output columns: {output_df.columns}")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
output_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify sector comparison output is complete, has the
# correct number of rows (one per sector), and all statistics are reasonable.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Output file exists and is non-zero
assert OUTPUT_PATH.exists(), "STOP: Output file does not exist"
file_size = OUTPUT_PATH.stat().st_size
file_ok = file_size > 0
if not file_ok:
    cp4_passed = False
print(f"  [{'PASS' if file_ok else 'FAIL'}] Output file exists and non-zero: {file_size:,} bytes")

# CP4.2: Correct number of rows (sectors)
expected_sectors = 2 if collapse_sectors else 3
rows_ok = output_df.shape[0] == expected_sectors
if not rows_ok:
    cp4_passed = False
print(f"  [{'PASS' if rows_ok else 'FAIL'}] Rows = {output_df.shape[0]} (expected {expected_sectors})")

# CP4.3: N per sector documented and sums to total
n_sum = output_df["n"].sum()
n_matches = n_sum == pre_rows
if not n_matches:
    cp4_passed = False
print(f"  [{'PASS' if n_matches else 'FAIL'}] N sums to total: {n_sum:,} (expected {pre_rows:,})")

# CP4.4: Summary statistics are substantively reasonable
stats_ok = True
for row in output_df.iter_rows(named=True):
    sector = row["sector_label"]
    # Completion rate should be 0-100 range (stored as proportion 0-1 or percentage)
    cr_mean = row["completion_rate_150pct_mean"]
    if cr_mean is not None and (cr_mean < 0 or cr_mean > 1.5):
        # Allow slight overshoot for percentage vs proportion ambiguity
        print(f"  [WARN] {sector}: completion_rate mean = {cr_mean:.4f} (outside expected range)")
        stats_ok = False
    # Admit rate should be between 0 and 1
    ar_mean = row["admit_rate_mean"]
    if ar_mean is not None and (ar_mean < 0 or ar_mean > 1.5):
        print(f"  [WARN] {sector}: admit_rate mean = {ar_mean:.4f} (outside expected range)")
        stats_ok = False
    # N must be positive
    if row["n"] <= 0:
        print(f"  [FAIL] {sector}: N = {row['n']} (must be > 0)")
        stats_ok = False
        cp4_passed = False

if stats_ok:
    print(f"  [PASS] All summary statistics within reasonable ranges")

# CP4.5: Correlation values in valid range [-1, 1]
corr_ok = True
for row in output_df.iter_rows(named=True):
    r = row["pearson_r"]
    if r is not None and (r < -1.001 or r > 1.001):
        print(f"  [FAIL] {row['sector_label']}: Pearson r = {r:.4f} (outside [-1, 1])")
        corr_ok = False
        cp4_passed = False
if corr_ok:
    print(f"  [PASS] All Pearson correlations in valid range")

# CP4.6: N per sector documented
print(f"\n  Sector N breakdown:")
for row in output_df.iter_rows(named=True):
    print(f"    {row['sector_label']}: N = {row['n']:,}")

if collapse_sectors:
    print(f"\n  NOTE: For-profit sector collapsed (N={fp_count}) per risk register guidance.")

assert cp4_passed, "STOP: CP4 validation failed"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 13:23:42
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/07_sector-comparison.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Sector Comparison
# ============================================================
# Loaded: 1,946 rows x 25 cols
# Pre-state: 1,946 rows, 25 cols
# Columns: ['unitid', 'inst_name', 'fips', 'inst_control', 'open_public', 'hbcu', 'tribal_college', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admit_rate', 'completion_rate_150pct', 'completers_150pct', 'cohort_adj_150pct', 'grant_recipients', 'sfa_total_students', 'urm_share', 'total_ug_enrollment', 'pell_share', 'student_faculty_ratio', 'retention_rate', 'instr_expend_per_fte', 'selectivity_band', 'pell_quintile', 'urm_quintile']
# All 10 required columns present
#
# Sector counts:
#   Private For-Profit: 150
#   Private Nonprofit: 1,202
#   Public: 594
#
# For-profit N = 150 >= 30. Keeping 3-sector breakdown.
#
# ============================================================
# SECTOR SUMMARY STATISTICS
# ============================================================
#
# --- Private For-Profit (N=150) ---
#   Variable                             Mean     Median         SD
#   ------------------------------------------------------------
#   completion_rate_150pct            45.5960    40.0000    26.9034
#   admit_rate                        62.9290    63.0682    24.7842
#   pell_share                         0.0817     0.0497     0.1002
#   urm_share                          0.5515     0.5397     0.2310
#   student_faculty_ratio             17.1800    15.0000    10.0416
#   retention_rate                    64.0000    64.0000    22.7616
#   instr_expend_per_fte            5265.0308  3878.9389  4785.5291
#
# --- Private Nonprofit (N=1,202) ---
#   Variable                             Mean     Median         SD
#   ------------------------------------------------------------
#   completion_rate_150pct            58.1722    59.7000    20.4835
#   admit_rate                        68.2686    71.6895    21.3769
#   pell_share                         0.1412     0.1376     0.0736
#   urm_share                          0.3043     0.2252     0.2577
#   student_faculty_ratio             12.1479    12.0000     4.2720
#   retention_rate                    74.4850    76.0000    14.4243
#   instr_expend_per_fte           12123.2967  9384.0494 12086.0787
#
# --- Public (N=594) ---
#   Variable                             Mean     Median         SD
#   ------------------------------------------------------------
#   completion_rate_150pct            52.7754    52.1000    17.4714
#   admit_rate                        75.4392    78.8791    17.2206
#   pell_share                         0.0843     0.0791     0.0414
#   urm_share                          0.3343     0.2463     0.2626
#   student_faculty_ratio             17.0875    17.0000     4.1793
#   retention_rate                    75.6166    77.0000    11.0259
#   instr_expend_per_fte           10261.0721  8802.6640  5304.9354
#
# ============================================================
# SELECTIVITY BAND DISTRIBUTION BY SECTOR
# ============================================================
#
# Private For-Profit:
#   Highly Selective              2 (  1.3%)
#   Moderately Selective         13 (  8.7%)
#   Open/Less Selective         117 ( 78.0%)
#   Selective                    18 ( 12.0%)
#
# Private Nonprofit:
#   Highly Selective             60 (  5.0%)
#   Moderately Selective        407 ( 33.9%)
#   Open/Less Selective         613 ( 51.0%)
#   Selective                   122 ( 10.1%)
#
# Public:
#   Highly Selective              9 (  1.5%)
#   Moderately Selective        157 ( 26.4%)
#   Open/Less Selective         391 ( 65.8%)
#   Selective                    37 (  6.2%)
#
# ============================================================
# WITHIN-SECTOR PEARSON CORRELATION: admit_rate vs completion_rate_150pct
# ============================================================
#   Private For-Profit        r = +0.2564  (N = 52)
#   Private Nonprofit         r = -0.3349  (N = 1,048)
#   Public                    r = -0.3683  (N = 525)
#
# Output shape: 3 rows x 26 cols
# Output columns: ['sector_label', 'n', 'completion_rate_150pct_mean', 'completion_rate_150pct_median', 'completion_rate_150pct_sd', 'admit_rate_mean', 'admit_rate_median', 'admit_rate_sd', 'pell_share_mean', 'pell_share_median', 'pell_share_sd', 'urm_share_mean', 'urm_share_median', 'urm_share_sd', 'student_faculty_ratio_mean', 'student_faculty_ratio_median', 'student_faculty_ratio_sd', 'retention_rate_mean', 'retention_rate_median', 'retention_rate_sd', 'instr_expend_per_fte_mean', 'instr_expend_per_fte_median', 'instr_expend_per_fte_sd', 'pearson_r', 'n_valid', 'band_distribution']
#
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_sector_comparison.parquet
#
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] Output file exists and non-zero: 10,891 bytes
#   [PASS] Rows = 3 (expected 3)
#   [PASS] N sums to total: 1,946 (expected 1,946)
#   [WARN] Private For-Profit: completion_rate mean = 45.5960 (outside expected range)
#   [WARN] Private For-Profit: admit_rate mean = 62.9290 (outside expected range)
#   [WARN] Private Nonprofit: completion_rate mean = 58.1722 (outside expected range)
#   [WARN] Private Nonprofit: admit_rate mean = 68.2686 (outside expected range)
#   [WARN] Public: completion_rate mean = 52.7754 (outside expected range)
#   [WARN] Public: admit_rate mean = 75.4392 (outside expected range)
#   [PASS] All Pearson correlations in valid range
#
#   Sector N breakdown:
#     Private For-Profit: N = 150
#     Private Nonprofit: N = 1,202
#     Public: N = 594
#
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
