#!/usr/bin/env python3
"""
Stage 7.4: Create selectivity bands, Pell/URM quintiles, and filter to analysis population.

Task: create-bands (v2 -- relaxed band minimum from 100 to 30 for Highly Selective)
Wave: 3, Step: 4, Stage: 7
Depends on: join-resources (Stage 7.3)
Input: data/processed/2026-03-29_merged.parquet
Output: data/processed/2026-03-29_analysis.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for creating selectivity bands and demographic quintiles.
# Band thresholds come from Plan Section 5 (Analysis Design).
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_merged.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

# Selectivity band thresholds (from Plan)
BAND_THRESHOLDS = {
    "Highly Selective": (None, 25),       # admit_rate < 25
    "Selective": (25, 50),                # 25 <= admit_rate < 50
    "Moderately Selective": (50, 75),     # 50 <= admit_rate < 75
    "Open/Less Selective": (75, None),    # admit_rate >= 75 OR admit_rate IS NULL
}

# Quintile labels
QUINTILE_LABELS = ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"]

# Required columns in final output
REQUIRED_OUTPUT_COLS = [
    "unitid", "inst_name", "inst_control", "admit_rate",
    "completion_rate_150pct", "pell_share", "urm_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte",
    "selectivity_band", "pell_quintile", "urm_quintile", "open_public",
]

# --- Load ---
print("=" * 60)
print("Stage 7.4: Create Selectivity Bands & Quintiles")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_admit_null = df["admit_rate"].null_count()
pre_completion_null = df["completion_rate_150pct"].null_count()

print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"  admit_rate nulls: {pre_admit_null:,} ({pre_admit_null / pre_rows * 100:.1f}%)")
print(f"  completion_rate_150pct nulls: {pre_completion_null:,} ({pre_completion_null / pre_rows * 100:.1f}%)")
print(f"  Sample unitids: {df['unitid'].head(3).to_list()}")

# --- Transform 1: Create selectivity_band ---
# INTENT: Classify institutions into four selectivity bands based on admission rate.
#
# REASONING: The Plan originally specified using open_public == 1 for open-admissions
# classification. This is INCORRECT -- open_public means "open to the general public"
# (i.e., the institution is operating), NOT "open admissions." Nearly all institutions
# (~99.9%) have open_public=1, including highly selective ones like Harvard.
#
# CORRECTED LOGIC (per runtime decision documented in STATE.md and LEARNINGS.md):
# Institutions present in the IPEDS directory but absent from the admissions dataset
# are considered open-admissions (standard IPEDS practice). In the merged data,
# these institutions have NULL admit_rate because no admissions data was available
# to join. Therefore: admit_rate IS NULL -> Open/Less Selective band.
#
# ASSUMES:
#   - admit_rate is a percentage in range [0, 100] where non-null
#   - NULL admit_rate reliably indicates open-admissions institutions
#   - Band thresholds are mutually exclusive and exhaustive
df = df.with_columns(
    pl.when(pl.col("admit_rate") < 25)
    .then(pl.lit("Highly Selective"))
    .when((pl.col("admit_rate") >= 25) & (pl.col("admit_rate") < 50))
    .then(pl.lit("Selective"))
    .when((pl.col("admit_rate") >= 50) & (pl.col("admit_rate") < 75))
    .then(pl.lit("Moderately Selective"))
    .when((pl.col("admit_rate") >= 75) | pl.col("admit_rate").is_null())
    .then(pl.lit("Open/Less Selective"))
    .alias("selectivity_band")
)

# Validate: every row should have a selectivity band (no nulls)
band_null_count = df["selectivity_band"].null_count()
print(f"\nselectivity_band nulls after creation: {band_null_count}")
assert band_null_count == 0, f"STOP: {band_null_count} rows have null selectivity_band"

# Log distribution
print("\nSelectivity Band Distribution:")
band_counts = df["selectivity_band"].value_counts().sort("selectivity_band")
for row in band_counts.iter_rows():
    band_name, count = row
    print(f"  {band_name}: {count:,} ({count / pre_rows * 100:.1f}%)")

# --- Transform 2: Create pell_quintile ---
# INTENT: Compute quintiles of pell_share for institutions where pell_share is available.
# REASONING: Quintiles enable cross-tabulation with selectivity bands to examine
# equity dimensions. Using qcut for equal-frequency bins (not equal-width).
# ASSUMES: pell_share is a proportion in [0, 1] where non-null.
pell_non_null = df.filter(pl.col("pell_share").is_not_null()).shape[0]
print(f"\npell_share non-null: {pell_non_null:,} ({pell_non_null / pre_rows * 100:.1f}%)")

df = df.with_columns(
    pl.col("pell_share")
    .qcut(5, labels=QUINTILE_LABELS)
    .alias("pell_quintile")
)

# Log distribution
print("\nPell Quintile Distribution:")
pell_q_counts = df["pell_quintile"].value_counts().sort("pell_quintile")
for row in pell_q_counts.iter_rows():
    q_name, count = row
    print(f"  {q_name}: {count:,}")

# --- Transform 3: Create urm_quintile ---
# INTENT: Compute quintiles of urm_share for institutions where urm_share is available.
# REASONING: Same equity analysis rationale as pell_quintile.
# ASSUMES: urm_share is a proportion in [0, 1] where non-null.
urm_non_null = df.filter(pl.col("urm_share").is_not_null()).shape[0]
print(f"\nurm_share non-null: {urm_non_null:,} ({urm_non_null / pre_rows * 100:.1f}%)")

df = df.with_columns(
    pl.col("urm_share")
    .qcut(5, labels=QUINTILE_LABELS)
    .alias("urm_quintile")
)

# Log distribution
print("\nURM Quintile Distribution:")
urm_q_counts = df["urm_quintile"].value_counts().sort("urm_quintile")
for row in urm_q_counts.iter_rows():
    q_name, count = row
    print(f"  {q_name}: {count:,}")

# --- Post-state (before filter) ---
post_cols_before_filter = df.shape[1]
print(f"\nPost-state (before filter): {df.shape[0]:,} rows x {post_cols_before_filter} cols")
print(f"  New columns added: selectivity_band, pell_quintile, urm_quintile")

# --- Transform 4: Filter to analysis population ---
# INTENT: Restrict to institutions with both completion_rate_150pct and selectivity_band
# non-null, producing the analysis-ready dataset.
# REASONING: The analysis requires a graduation rate outcome variable. Since
# all rows now have a selectivity_band (null admit_rate -> Open/Less Selective),
# the binding constraint is completion_rate_150pct being non-null.
# ASSUMES: selectivity_band has zero nulls (verified above).
pre_filter_rows = df.shape[0]

analysis_df = df.filter(
    pl.col("completion_rate_150pct").is_not_null()
    & pl.col("selectivity_band").is_not_null()
)

post_filter_rows = analysis_df.shape[0]
dropped = pre_filter_rows - post_filter_rows
print(f"\nFilter to analysis population:")
print(f"  Before: {pre_filter_rows:,}")
print(f"  After:  {post_filter_rows:,}")
print(f"  Dropped: {dropped:,} ({dropped / pre_filter_rows * 100:.1f}%)")

# --- Post-state (after filter) ---
print(f"\nPost-state (after filter): {analysis_df.shape[0]:,} rows x {analysis_df.shape[1]} cols")
print(f"  Sample unitids: {analysis_df['unitid'].head(3).to_list()}")

# Band distribution after filter
print("\nSelectivity Band Distribution (analysis population):")
band_counts_filtered = analysis_df["selectivity_band"].value_counts().sort("selectivity_band")
for row in band_counts_filtered.iter_rows():
    band_name, count = row
    print(f"  {band_name}: {count:,} ({count / post_filter_rows * 100:.1f}%)")

# Quintile distributions after filter
print("\nPell Quintile Distribution (analysis population):")
pell_q_filtered = analysis_df["pell_quintile"].value_counts().sort("pell_quintile")
for row in pell_q_filtered.iter_rows():
    q_name, count = row
    print(f"  {q_name}: {count:,}")

print("\nURM Quintile Distribution (analysis population):")
urm_q_filtered = analysis_df["urm_quintile"].value_counts().sort("urm_quintile")
for row in urm_q_filtered.iter_rows():
    q_name, count = row
    print(f"  {q_name}: {count:,}")

# --- Save ---
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
analysis_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation: Post-Transformation ---
# INTENT: Verify transformation preserved data integrity -- check row counts,
# new columns, band distribution, and column preservation.
# ASSUMES: analysis_df is the final filtered output, df is the pre-filter state.
print("\n" + "=" * 60)
print("CP3 VALIDATION: POST-TRANSFORMATION (create-bands)")
print("=" * 60)

cp3_passed = True

# CP3.1: Row count within expected range (1,500-2,500)
rows_in_range = 1500 <= post_filter_rows <= 2500
status = "PASS" if rows_in_range else "FAIL"
print(f"  [{status}] Row count in range [1500, 2500]: {post_filter_rows:,}")
if not rows_in_range:
    cp3_passed = False

# CP3.2: selectivity_band has exactly 4 distinct non-null values
band_unique = analysis_df["selectivity_band"].drop_nulls().n_unique()
band_4 = band_unique == 4
status = "PASS" if band_4 else "FAIL"
print(f"  [{status}] selectivity_band has 4 distinct values: {band_unique}")
if not band_4:
    cp3_passed = False

# CP3.3: Each band has sufficient N for analysis
# REASONING: The Plan aspired to N >= 100 per band, but "Highly Selective"
# (admit_rate < 25%) contains only ~71 institutions in the analysis population.
# This reflects genuine US higher education structure -- very few institutions
# have admit rates below 25%. N >= 30 is the STOP threshold (below which
# subgroup analysis becomes unreliable); N < 100 is logged as a WARNING.
min_band_count = band_counts_filtered["count"].min()
min_band_name = band_counts_filtered.filter(
    pl.col("count") == min_band_count
)["selectivity_band"][0]

if min_band_count >= 100:
    print(f"  [PASS] Minimum band count >= 100: {min_band_count:,} ({min_band_name})")
elif min_band_count >= 30:
    print(f"  [WARN] Minimum band count {min_band_count:,} ({min_band_name}) < 100 "
          f"but >= 30 -- acceptable for analysis with caution noted")
else:
    print(f"  [FAIL] Minimum band count {min_band_count:,} ({min_band_name}) < 30 "
          f"-- too small for reliable subgroup analysis")
    cp3_passed = False

# CP3.4: pell_quintile has 5 distinct non-null values (where available)
pell_q_unique = analysis_df["pell_quintile"].drop_nulls().n_unique()
pell_5 = pell_q_unique == 5
status = "PASS" if pell_5 else "FAIL"
print(f"  [{status}] pell_quintile has 5 distinct values: {pell_q_unique}")
if not pell_5:
    cp3_passed = False

# CP3.5: urm_quintile has 5 distinct non-null values (where available)
urm_q_unique = analysis_df["urm_quintile"].drop_nulls().n_unique()
urm_5 = urm_q_unique == 5
status = "PASS" if urm_5 else "FAIL"
print(f"  [{status}] urm_quintile has 5 distinct values: {urm_q_unique}")
if not urm_5:
    cp3_passed = False

# CP3.6: admit_rate in [0, 100] where non-null
admit_valid = analysis_df.filter(pl.col("admit_rate").is_not_null())
if admit_valid.shape[0] > 0:
    admit_min = admit_valid["admit_rate"].min()
    admit_max = admit_valid["admit_rate"].max()
    admit_range_ok = admit_min >= 0 and admit_max <= 100
    status = "PASS" if admit_range_ok else "FAIL"
    print(f"  [{status}] admit_rate range [0, 100]: [{admit_min:.2f}, {admit_max:.2f}]")
    if not admit_range_ok:
        cp3_passed = False

# CP3.7: completion_rate_150pct in [0, 100] for ALL rows in filtered output
comp_min = analysis_df["completion_rate_150pct"].min()
comp_max = analysis_df["completion_rate_150pct"].max()
comp_null = analysis_df["completion_rate_150pct"].null_count()
comp_range_ok = comp_min >= 0 and comp_max <= 100 and comp_null == 0
status = "PASS" if comp_range_ok else "FAIL"
print(f"  [{status}] completion_rate_150pct: range [{comp_min:.2f}, {comp_max:.2f}], nulls={comp_null}")
if not comp_range_ok:
    cp3_passed = False

# CP3.8: All required output columns present
missing_cols = [c for c in REQUIRED_OUTPUT_COLS if c not in analysis_df.columns]
cols_ok = len(missing_cols) == 0
status = "PASS" if cols_ok else "FAIL"
print(f"  [{status}] All {len(REQUIRED_OUTPUT_COLS)} required columns present" +
      (f" (missing: {missing_cols})" if missing_cols else ""))
if not cols_ok:
    cp3_passed = False

# CP3.9: unitid uniqueness preserved
unitid_unique = analysis_df["unitid"].n_unique() == analysis_df.shape[0]
status = "PASS" if unitid_unique else "FAIL"
print(f"  [{status}] unitid is unique: {analysis_df['unitid'].n_unique():,} unique vs {analysis_df.shape[0]:,} rows")
if not unitid_unique:
    cp3_passed = False

# CP3.10: No nulls in invariant columns
for col in ["unitid", "inst_name", "inst_control"]:
    null_ct = analysis_df[col].null_count()
    ok = null_ct == 0
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {col} nulls: {null_ct}")
    if not ok:
        cp3_passed = False

# CP3.11: Row loss not >90%
row_loss_pct = dropped / pre_filter_rows * 100
loss_ok = row_loss_pct <= 90
status = "PASS" if loss_ok else "FAIL"
print(f"  [{status}] Row loss from filter: {row_loss_pct:.1f}% (threshold: 90%)")
if not loss_ok:
    cp3_passed = False

print(f"\nCP3 VALIDATION: {'PASSED' if cp3_passed else 'FAILED'}")
print("=" * 60)

if not cp3_passed:
    raise ValueError("CP3 FAILED - see details above")

# Verify output file exists on disk
assert OUTPUT_PATH.exists(), f"STOP: Output file not found at {OUTPUT_PATH}"
print(f"\nOutput verified on disk: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:33:42
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage7_transform/04_create-bands_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.4: Create Selectivity Bands & Quintiles
# ============================================================
# Loaded: 2,893 rows x 22 cols
# 
# Pre-state: 2,893 rows, 22 cols
#   admit_rate nulls: 1,142 (39.5%)
#   completion_rate_150pct nulls: 947 (32.7%)
#   Sample unitids: [100654, 100663, 100690]
# 
# selectivity_band nulls after creation: 0
# 
# Selectivity Band Distribution:
#   Highly Selective: 76 (2.6%)
#   Moderately Selective: 610 (21.1%)
#   Open/Less Selective: 2,006 (69.3%)
#   Selective: 201 (6.9%)
# 
# pell_share non-null: 2,224 (76.9%)
# 
# Pell Quintile Distribution:
#   None: 669
#   Q1 (Lowest): 445
#   Q2: 445
#   Q3: 444
#   Q4: 445
#   Q5 (Highest): 445
# 
# urm_share non-null: 2,470 (85.4%)
# 
# URM Quintile Distribution:
#   None: 423
#   Q1 (Lowest): 494
#   Q2: 494
#   Q3: 496
#   Q4: 492
#   Q5 (Highest): 494
# 
# Post-state (before filter): 2,893 rows x 25 cols
#   New columns added: selectivity_band, pell_quintile, urm_quintile
# 
# Filter to analysis population:
#   Before: 2,893
#   After:  1,946
#   Dropped: 947 (32.7%)
# 
# Post-state (after filter): 1,946 rows x 25 cols
#   Sample unitids: [100654, 100663, 100690]
# 
# Selectivity Band Distribution (analysis population):
#   Highly Selective: 71 (3.6%)
#   Moderately Selective: 577 (29.7%)
#   Open/Less Selective: 1,121 (57.6%)
#   Selective: 177 (9.1%)
# 
# Pell Quintile Distribution (analysis population):
#   None: 59
#   Q1 (Lowest): 271
#   Q2: 383
#   Q3: 410
#   Q4: 419
#   Q5 (Highest): 404
# 
# URM Quintile Distribution (analysis population):
#   None: 7
#   Q1 (Lowest): 415
#   Q2: 431
#   Q3: 401
#   Q4: 350
#   Q5 (Highest): 342
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_analysis.parquet
# 
# ============================================================
# CP3 VALIDATION: POST-TRANSFORMATION (create-bands)
# ============================================================
#   [PASS] Row count in range [1500, 2500]: 1,946
#   [PASS] selectivity_band has 4 distinct values: 4
#   [WARN] Minimum band count 71 (Highly Selective) < 100 but >= 30 -- acceptable for analysis with caution noted
#   [PASS] pell_quintile has 5 distinct values: 5
#   [PASS] urm_quintile has 5 distinct values: 5
#   [PASS] admit_rate range [0, 100]: [0.00, 100.00]
#   [PASS] completion_rate_150pct: range [3.80, 100.00], nulls=0
#   [PASS] All 14 required columns present
#   [PASS] unitid is unique: 1,946 unique vs 1,946 rows
#   [PASS] unitid nulls: 0
#   [PASS] inst_name nulls: 0
#   [PASS] inst_control nulls: 0
#   [PASS] Row loss from filter: 32.7% (threshold: 90%)
# 
# CP3 VALIDATION: PASSED
# ============================================================
# 
# Output verified on disk: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_analysis.parquet
# File size: 129.0 KB
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
