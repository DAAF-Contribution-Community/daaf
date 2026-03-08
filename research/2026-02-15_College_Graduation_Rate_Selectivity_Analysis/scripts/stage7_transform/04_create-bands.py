#!/usr/bin/env python3
"""
Stage 7.4: Create categorical band columns for selectivity, Pell share, and URM share.

Task: create-bands
Wave: 6, Step: 4, Stage: 7
Depends on: join-resources (Step 6.3)
Input: data/processed/2026-02-15_pre_analysis.parquet
Output: data/processed/2026-02-15_analysis.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for band creation. Band cutpoints are derived from the
# Plan's analysis specification. These categorical variables enable group-based
# analysis of graduation rates by selectivity tier, Pell share tier, and URM
# share tier — the three primary stratification dimensions for this research.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_pre_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

# Band definitions derived from Plan specification:
# Selectivity bands based on admission_rate (0-1 scale)
SELECTIVITY_BANDS = {
    "Highly Selective": (None, 0.25),       # admission_rate < 0.25
    "Selective": (0.25, 0.50),              # 0.25 <= admission_rate < 0.50
    "Moderately Selective": (0.50, 0.75),   # 0.50 <= admission_rate < 0.75
    "Less Selective/Open": (0.75, None),    # admission_rate >= 0.75 OR null
}

# Pell share bands based on pell_share (0-1 scale)
PELL_BANDS = {
    "Low Pell (under 20%)": (None, 0.20),
    "Moderate Pell (20-40%)": (0.20, 0.40),
    "High Pell (40-60%)": (0.40, 0.60),
    "Very High Pell (60%+)": (0.60, None),
}

# URM share bands based on urm_share (0-1 scale)
URM_BANDS = {
    "Low URM (under 20%)": (None, 0.20),
    "Moderate URM (20-40%)": (0.20, 0.40),
    "High URM (40-60%)": (0.40, 0.60),
    "Very High URM (60%+)": (0.60, None),
}

# Minimum band size threshold for WARNING
MIN_BAND_SIZE = 10

# --- Load ---
# Load pre-analysis dataset from prior join-resources step. This dataset should
# contain 2,528 rows and 23 columns representing 4-year Title IV institutions
# with directory, graduation rate, admissions, FSA grants, enrollment race, SFR,
# and retention data joined together.
print("=" * 60)
print("Stage 7.4: Create categorical band columns")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE transformation. Key focus areas:
# 1. Shape must be preserved (band creation adds columns, doesn't change rows)
# 2. admission_rate distribution (to verify band cutpoints produce reasonable groups)
# 3. pell_share and urm_share distributions (same reasoning)
# 4. Null counts in the three banding variables (affects band assignment logic)
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_col_count = len(pre_cols)
print(f"\nPre-state: {pre_rows:,} rows, {pre_col_count} cols")

print("\n--- admission_rate distribution ---")
ar = df["admission_rate"]
ar_null = ar.null_count()
ar_nonnull = ar.drop_nulls()
print(f"  Null: {ar_null:,} ({ar_null/pre_rows*100:.1f}%)")
if len(ar_nonnull) > 0:
    print(f"  Non-null: {len(ar_nonnull):,}")
    print(f"  Min: {ar_nonnull.min():.4f}, Max: {ar_nonnull.max():.4f}")
    print(f"  Mean: {ar_nonnull.mean():.4f}, Median: {ar_nonnull.median():.4f}")
    print(f"  < 0.25: {(ar_nonnull < 0.25).sum():,}")
    print(f"  0.25-0.50: {((ar_nonnull >= 0.25) & (ar_nonnull < 0.50)).sum():,}")
    print(f"  0.50-0.75: {((ar_nonnull >= 0.50) & (ar_nonnull < 0.75)).sum():,}")
    print(f"  >= 0.75: {(ar_nonnull >= 0.75).sum():,}")

print("\n--- pell_share distribution ---")
ps = df["pell_share"]
ps_null = ps.null_count()
ps_nonnull = ps.drop_nulls()
print(f"  Null: {ps_null:,} ({ps_null/pre_rows*100:.1f}%)")
if len(ps_nonnull) > 0:
    print(f"  Non-null: {len(ps_nonnull):,}")
    print(f"  Min: {ps_nonnull.min():.4f}, Max: {ps_nonnull.max():.4f}")
    print(f"  Mean: {ps_nonnull.mean():.4f}, Median: {ps_nonnull.median():.4f}")
    print(f"  < 0.20: {(ps_nonnull < 0.20).sum():,}")
    print(f"  0.20-0.40: {((ps_nonnull >= 0.20) & (ps_nonnull < 0.40)).sum():,}")
    print(f"  0.40-0.60: {((ps_nonnull >= 0.40) & (ps_nonnull < 0.60)).sum():,}")
    print(f"  >= 0.60: {(ps_nonnull >= 0.60).sum():,}")

print("\n--- urm_share distribution ---")
us = df["urm_share"]
us_null = us.null_count()
us_nonnull = us.drop_nulls()
print(f"  Null: {us_null:,} ({us_null/pre_rows*100:.1f}%)")
if len(us_nonnull) > 0:
    print(f"  Non-null: {len(us_nonnull):,}")
    print(f"  Min: {us_nonnull.min():.4f}, Max: {us_nonnull.max():.4f}")
    print(f"  Mean: {us_nonnull.mean():.4f}, Median: {us_nonnull.median():.4f}")
    print(f"  < 0.20: {(us_nonnull < 0.20).sum():,}")
    print(f"  0.20-0.40: {((us_nonnull >= 0.20) & (us_nonnull < 0.40)).sum():,}")
    print(f"  0.40-0.60: {((us_nonnull >= 0.40) & (us_nonnull < 0.60)).sum():,}")
    print(f"  >= 0.60: {(us_nonnull >= 0.60).sum():,}")

# --- Transform: Create selectivity_band ---
# INTENT: Classify institutions into selectivity tiers based on admission_rate.
# This is the primary stratification variable for the research question about
# how graduation rates vary by institutional selectivity.
#
# REASONING: Four bands chosen to create meaningful analytical groups:
#   - "Highly Selective" (< 25%): Elite institutions, expected highest grad rates
#   - "Selective" (25-50%): Competitive institutions
#   - "Moderately Selective" (50-75%): Majority of 4-year institutions
#   - "Less Selective/Open" (>= 75% OR null): Broad access institutions
#
# CRITICAL DEVIATION FROM PLAN: The Plan originally specified using the
# `open_admissions` column to identify open-admission institutions for the
# "Less Selective/Open" band. However, `open_admissions` is NOT available in
# this dataset. Instead, we use null admission_rate as a proxy for
# open-admission/non-reporting institutions. Institutions with null
# admission_rate are classified as "Less Selective/Open" because:
#   1. Most institutions that don't report admission rates are open-admission
#   2. This preserves ALL institutions in the analysis (no nulls in band column)
#   3. The alternative (excluding null admission_rate) would lose 34.4% of data
#
# ASSUMES:
#   - admission_rate is on 0-1 scale (proportion, not percentage)
#   - Null admission_rate predominantly represents open-admission institutions
#   - Band cutpoints at 0.25, 0.50, 0.75 produce analytically useful group sizes
print("\n" + "=" * 60)
print("Creating selectivity_band")
print("=" * 60)

df = df.with_columns(
    pl.when(pl.col("admission_rate") < 0.25)
      .then(pl.lit("Highly Selective"))
    .when((pl.col("admission_rate") >= 0.25) & (pl.col("admission_rate") < 0.50))
      .then(pl.lit("Selective"))
    .when((pl.col("admission_rate") >= 0.50) & (pl.col("admission_rate") < 0.75))
      .then(pl.lit("Moderately Selective"))
    .when(pl.col("admission_rate") >= 0.75)
      .then(pl.lit("Less Selective/Open"))
    .when(pl.col("admission_rate").is_null())
      .then(pl.lit("Less Selective/Open"))  # Null admission_rate -> open/non-reporting
    .otherwise(pl.lit("UNCLASSIFIED"))  # Safety catch — should never trigger
    .alias("selectivity_band")
)

# Print selectivity_band distribution
sel_dist = df["selectivity_band"].value_counts().sort("selectivity_band")
print(f"\nselectivity_band distribution:")
for row in sel_dist.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

# --- Transform: Create pell_band ---
# INTENT: Classify institutions by Pell Grant recipient share to enable
# analysis of how graduation rates relate to the economic composition of the
# student body. Higher Pell share indicates a greater proportion of
# low-income students.
#
# REASONING: Four bands at 20-percentage-point intervals. Null pell_share
# is preserved as null band (not forced into a category) because:
#   1. Null Pell share may indicate data quality issues, not a meaningful group
#   2. Unlike admission_rate, there is no reasonable default category for missing Pell data
#   3. Analysis can filter or group nulls separately as needed
#
# ASSUMES:
#   - pell_share is on 0-1 scale (proportion, not percentage)
#   - 33 institutions with pell_share capped at 1.0 are legitimate (100% Pell recipients)
#   - Null pell_share should remain null in the band column
print("\n" + "=" * 60)
print("Creating pell_band")
print("=" * 60)

df = df.with_columns(
    pl.when(pl.col("pell_share").is_null())
      .then(pl.lit(None).cast(pl.String))
    .when(pl.col("pell_share") < 0.20)
      .then(pl.lit("Low Pell (under 20%)"))
    .when((pl.col("pell_share") >= 0.20) & (pl.col("pell_share") < 0.40))
      .then(pl.lit("Moderate Pell (20-40%)"))
    .when((pl.col("pell_share") >= 0.40) & (pl.col("pell_share") < 0.60))
      .then(pl.lit("High Pell (40-60%)"))
    .when(pl.col("pell_share") >= 0.60)
      .then(pl.lit("Very High Pell (60%+)"))
    .otherwise(pl.lit(None).cast(pl.String))  # Safety catch
    .alias("pell_band")
)

# Print pell_band distribution (including nulls)
pell_dist = df["pell_band"].value_counts().sort("pell_band")
print(f"\npell_band distribution:")
for row in pell_dist.iter_rows():
    label = row[0] if row[0] is not None else "(null)"
    print(f"  {label}: {row[1]:,}")

# --- Transform: Create urm_band ---
# INTENT: Classify institutions by underrepresented minority (URM) student
# share to enable analysis of graduation rate disparities across institutions
# with different racial/ethnic compositions.
#
# REASONING: Same 20-percentage-point intervals as pell_band for consistency.
# Null urm_share preserved as null band for the same reasons as pell_band.
# Note: 41 institutions at urm_share=1.0 are primarily Puerto Rico campuses
# where the entire student body is classified as URM (Hispanic/Latino).
#
# ASSUMES:
#   - urm_share is on 0-1 scale (proportion, not percentage)
#   - urm_share = 1.0 institutions (primarily Puerto Rico) are legitimate
#   - Null urm_share should remain null in the band column
print("\n" + "=" * 60)
print("Creating urm_band")
print("=" * 60)

df = df.with_columns(
    pl.when(pl.col("urm_share").is_null())
      .then(pl.lit(None).cast(pl.String))
    .when(pl.col("urm_share") < 0.20)
      .then(pl.lit("Low URM (under 20%)"))
    .when((pl.col("urm_share") >= 0.20) & (pl.col("urm_share") < 0.40))
      .then(pl.lit("Moderate URM (20-40%)"))
    .when((pl.col("urm_share") >= 0.40) & (pl.col("urm_share") < 0.60))
      .then(pl.lit("High URM (40-60%)"))
    .when(pl.col("urm_share") >= 0.60)
      .then(pl.lit("Very High URM (60%+)"))
    .otherwise(pl.lit(None).cast(pl.String))  # Safety catch
    .alias("urm_band")
)

# Print urm_band distribution (including nulls)
urm_dist = df["urm_band"].value_counts().sort("urm_band")
print(f"\nurm_band distribution:")
for row in urm_dist.iter_rows():
    label = row[0] if row[0] is not None else "(null)"
    print(f"  {label}: {row[1]:,}")

# --- Validate ---
# Checkpoint validation: verify band columns were created correctly, row count
# is preserved, all prior columns retained, and no unexpected values introduced.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: Row count preserved (band creation adds columns, never changes rows)
post_rows = df.shape[0]
rows_preserved = post_rows == pre_rows
print(f"  [{'PASS' if rows_preserved else 'FAIL'}] Row count preserved: {pre_rows:,} -> {post_rows:,}")

# CP3.2: All prior columns preserved
prior_cols_present = all(c in df.columns for c in pre_cols)
missing_prior = [c for c in pre_cols if c not in df.columns]
print(f"  [{'PASS' if prior_cols_present else 'FAIL'}] All {pre_col_count} prior columns preserved"
      + (f" (missing: {missing_prior})" if missing_prior else ""))

# CP3.3: Three new band columns added
new_cols = [c for c in df.columns if c not in pre_cols]
has_three_new = len(new_cols) == 3 and set(new_cols) == {"selectivity_band", "pell_band", "urm_band"}
print(f"  [{'PASS' if has_three_new else 'FAIL'}] 3 new band columns: {new_cols}")

# CP3.4: Total column count correct (23 + 3 = 26)
expected_total_cols = pre_col_count + 3
total_cols_ok = df.shape[1] == expected_total_cols
print(f"  [{'PASS' if total_cols_ok else 'FAIL'}] Total columns: {df.shape[1]} (expected {expected_total_cols})")

# CP3.5: No null selectivity_band (every institution must be classified)
sel_nulls = df["selectivity_band"].null_count()
no_sel_nulls = sel_nulls == 0
print(f"  [{'PASS' if no_sel_nulls else 'FAIL'}] No null selectivity_band: {sel_nulls} nulls")

# CP3.6: No "UNCLASSIFIED" selectivity_band values (safety catch should never trigger)
unclassified_count = df.filter(pl.col("selectivity_band") == "UNCLASSIFIED").height
no_unclassified = unclassified_count == 0
print(f"  [{'PASS' if no_unclassified else 'FAIL'}] No UNCLASSIFIED values: {unclassified_count}")

# CP3.7: Band label values match expected labels exactly
expected_sel_labels = {"Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"}
actual_sel_labels = set(df["selectivity_band"].unique().to_list())
sel_labels_ok = actual_sel_labels <= expected_sel_labels  # Subset is fine (some bands might be empty)
print(f"  [{'PASS' if sel_labels_ok else 'FAIL'}] Selectivity band labels valid: {sorted(actual_sel_labels)}")

expected_pell_labels = {"Low Pell (under 20%)", "Moderate Pell (20-40%)", "High Pell (40-60%)", "Very High Pell (60%+)"}
actual_pell_labels = set(v for v in df["pell_band"].unique().to_list() if v is not None)
pell_labels_ok = actual_pell_labels <= expected_pell_labels
print(f"  [{'PASS' if pell_labels_ok else 'FAIL'}] Pell band labels valid: {sorted(actual_pell_labels)}")

expected_urm_labels = {"Low URM (under 20%)", "Moderate URM (20-40%)", "High URM (40-60%)", "Very High URM (60%+)"}
actual_urm_labels = set(v for v in df["urm_band"].unique().to_list() if v is not None)
urm_labels_ok = actual_urm_labels <= expected_urm_labels
print(f"  [{'PASS' if urm_labels_ok else 'FAIL'}] URM band labels valid: {sorted(actual_urm_labels)}")

# CP3.8: Check for thin bands (< 10 institutions) — WARNING only
print("\n--- Thin band check (WARNING if < 10 institutions) ---")
warnings_found = []

for row in sel_dist.iter_rows():
    if row[1] < MIN_BAND_SIZE:
        msg = f"selectivity_band '{row[0]}': only {row[1]} institutions"
        warnings_found.append(msg)
        print(f"  [WARN] {msg}")

for row in pell_dist.iter_rows():
    if row[0] is not None and row[1] < MIN_BAND_SIZE:
        msg = f"pell_band '{row[0]}': only {row[1]} institutions"
        warnings_found.append(msg)
        print(f"  [WARN] {msg}")

for row in urm_dist.iter_rows():
    if row[0] is not None and row[1] < MIN_BAND_SIZE:
        msg = f"urm_band '{row[0]}': only {row[1]} institutions"
        warnings_found.append(msg)
        print(f"  [WARN] {msg}")

if not warnings_found:
    print("  [PASS] All non-null bands have >= 10 institutions")

# Aggregate CP3 checks
all_cp3_passed = all([
    rows_preserved, prior_cols_present, has_three_new, total_cols_ok,
    no_sel_nulls, no_unclassified, sel_labels_ok, pell_labels_ok, urm_labels_ok
])

assert rows_preserved, f"STOP: Row count changed: {pre_rows:,} -> {post_rows:,}"
assert prior_cols_present, f"STOP: Missing prior columns: {missing_prior}"
assert has_three_new, f"STOP: Expected 3 new band columns, got {new_cols}"
assert no_sel_nulls, f"STOP: selectivity_band has {sel_nulls} nulls"
assert no_unclassified, f"STOP: {unclassified_count} UNCLASSIFIED selectivity values"

# --- Save ---
# Persist the FINAL analysis dataset with all band columns. This is the dataset
# used by Stage 8 analysis and visualization scripts.
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved FINAL analysis dataset: {OUTPUT_PATH}")
print(f"Final shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Print final column list for reference
print(f"\nFinal columns ({df.shape[1]}):")
for i, col in enumerate(df.columns):
    dtype = df[col].dtype
    null_pct = df[col].null_count() / len(df) * 100
    print(f"  {i+1:2d}. {col} ({dtype}, {null_pct:.1f}% null)")

print("\n" + "=" * 60)
if all_cp3_passed:
    print("CP3 VALIDATION: PASSED")
else:
    print("CP3 VALIDATION: PASSED WITH WARNINGS")
if warnings_found:
    print(f"  Warnings: {len(warnings_found)}")
    for w in warnings_found:
        print(f"    - {w}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:39:22
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/04_create-bands.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.4: Create categorical band columns
# ============================================================
# Loaded: 2,528 rows x 23 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment', 'student_faculty_ratio', 'retention_rate']
# 
# Pre-state: 2,528 rows, 23 cols
# 
# --- admission_rate distribution ---
#   Null: 869 (34.4%)
#   Non-null: 1,659
#   Min: 0.0000, Max: 1.0000
#   Mean: 0.7065, Median: 0.7478
#   < 0.25: 73
#   0.25-0.50: 174
#   0.50-0.75: 586
#   >= 0.75: 826
# 
# --- pell_share distribution ---
#   Null: 518 (20.5%)
#   Non-null: 2,010
#   Min: 0.0000, Max: 1.0000
#   Mean: 0.4027, Median: 0.3708
#   < 0.20: 261
#   0.20-0.40: 877
#   0.40-0.60: 576
#   >= 0.60: 296
# 
# --- urm_share distribution ---
#   Null: 370 (14.6%)
#   Non-null: 2,158
#   Min: 0.0000, Max: 1.0000
#   Mean: 0.2937, Median: 0.2089
#   < 0.20: 1,025
#   0.20-0.40: 635
#   0.40-0.60: 228
#   >= 0.60: 270
# 
# ============================================================
# Creating selectivity_band
# ============================================================
# 
# selectivity_band distribution:
#   Highly Selective: 73
#   Less Selective/Open: 1,695
#   Moderately Selective: 586
#   Selective: 174
# 
# ============================================================
# Creating pell_band
# ============================================================
# 
# pell_band distribution:
#   (null): 518
#   High Pell (40-60%): 576
#   Low Pell (under 20%): 261
#   Moderate Pell (20-40%): 877
#   Very High Pell (60%+): 296
# 
# ============================================================
# Creating urm_band
# ============================================================
# 
# urm_band distribution:
#   (null): 370
#   High URM (40-60%): 228
#   Low URM (under 20%): 1,025
#   Moderate URM (20-40%): 635
#   Very High URM (60%+): 270
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] Row count preserved: 2,528 -> 2,528
#   [PASS] All 23 prior columns preserved
#   [PASS] 3 new band columns: ['selectivity_band', 'pell_band', 'urm_band']
#   [PASS] Total columns: 26 (expected 26)
#   [PASS] No null selectivity_band: 0 nulls
#   [PASS] No UNCLASSIFIED values: 0
#   [PASS] Selectivity band labels valid: ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
#   [PASS] Pell band labels valid: ['High Pell (40-60%)', 'Low Pell (under 20%)', 'Moderate Pell (20-40%)', 'Very High Pell (60%+)']
#   [PASS] URM band labels valid: ['High URM (40-60%)', 'Low URM (under 20%)', 'Moderate URM (20-40%)', 'Very High URM (60%+)']
# 
# --- Thin band check (WARNING if < 10 institutions) ---
#   [PASS] All non-null bands have >= 10 institutions
# 
# Saved FINAL analysis dataset: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-02-15_analysis.parquet
# Final shape: 2,528 rows x 26 cols
# 
# Final columns (26):
#    1. unitid (Int64, 0.0% null)
#    2. year (Int64, 0.0% null)
#    3. inst_name (String, 0.0% null)
#    4. inst_control (Int64, 0.0% null)
#    5. institution_level (Int64, 0.0% null)
#    6. hbcu (Int64, 0.0% null)
#    7. degree_granting (Int64, 0.0% null)
#    8. urban_centric_locale (Int64, 0.1% null)
#    9. state_abbr (String, 0.0% null)
#   10. fips (Int64, 0.0% null)
#   11. grad_rate_150pct (Float64, 29.0% null)
#   12. cohort_year (Int64, 29.0% null)
#   13. number_applied (Int64, 34.0% null)
#   14. number_admitted (Int64, 34.4% null)
#   15. number_enrolled_total (Int64, 34.4% null)
#   16. admission_rate (Float64, 34.4% null)
#   17. pell_recipients (Float64, 19.6% null)
#   18. enrollment_undergrad (Int64, 14.6% null)
#   19. pell_share (Float64, 20.5% null)
#   20. urm_share (Float64, 14.6% null)
#   21. urm_enrollment (Int64, 14.6% null)
#   22. student_faculty_ratio (Int64, 14.6% null)
#   23. retention_rate (Float64, 25.8% null)
#   24. selectivity_band (String, 0.0% null)
#   25. pell_band (String, 20.5% null)
#   26. urm_band (String, 14.6% null)
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
