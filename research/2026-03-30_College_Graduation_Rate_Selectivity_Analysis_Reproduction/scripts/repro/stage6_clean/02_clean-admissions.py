#!/usr/bin/env python3
"""
Stage 6.2: Clean IPEDS Admissions Data.

Task: clean-admissions
Wave: 1, Step: 2, Stage: 6
Depends on: scripts/stage5_fetch/02_fetch-admissions.py
Input: data/raw/2026-03-29_ipeds_admissions.parquet
Output: data/processed/2026-03-29_admissions_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for this script. Paths are relative to the project
# root. Constants are derived from the Plan's query specification.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
INPUT_PATH = PROJECT_DIR / "data/raw/2026-03-29_ipeds_admissions.parquet"
OUTPUT_PATH = PROJECT_DIR / "data/processed/2026-03-29_admissions_clean.parquet"

# Domain configuration (education data, Urban Institute Portal)
# REASONING: The Portal uses -1 (missing/not reported), -2 (not applicable),
# -3 (suppressed for privacy) as coded missing values in numeric columns.
CODED_MISSING_VALUES = [-1, -2, -3]
SUPPRESSION_CODE = -3
SUPPRESSION_THRESHOLD = 0.5  # 50% max suppression before STOP

# Columns that need coded value replacement
# REASONING: These are the numeric measure columns from IPEDS admissions that
# may contain coded missing values. Categorical columns (sex, year) use integer
# encoding and do NOT get coded value replacement.
NUMERIC_COLS_TO_CLEAN = [
    "number_applied",
    "number_admitted",
    "number_enrolled_ft",
    "number_enrolled_pt",
    "number_enrolled_total",
]

# Key variables for CP2 validation
KEY_VARIABLES = ["number_applied", "number_admitted", "number_enrolled_total", "admit_rate"]

# --- Load ---
# Load raw admissions data from Stage 5 fetch output. Verify shape and schema
# match expectations before proceeding.
print("=" * 60)
print("Stage 6.2: Clean IPEDS Admissions Data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# Capture the current state of the data BEFORE transformation. These values
# are compared against post-state to validate the transformation worked
# correctly and didn't introduce unexpected changes.
raw_df = df.clone()
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Sample unitids: {df['unitid'].head(3).to_list()}")

# Check sex values present
# INTENT: Understand the structure of the raw data before filtering.
# The raw data contains rows for sex=1 (male), sex=2 (female), sex=99 (total).
# We need sex=99 for institution-level totals.
print(f"\nSex value distribution:")
sex_counts = df.group_by("sex").len().sort("sex")
print(sex_counts)

# Check year values present
print(f"\nYear value distribution:")
year_counts = df.group_by("year").len().sort("year")
print(year_counts)

# --- Transform ---
# This is the core operation of this script: filter to institution-level totals
# (sex==99, year==2020), replace coded missing values with null, and compute
# admission rate.

# Step 1: Filter to institution-level totals
# INTENT: Keep only the sex==99 (total) rows to get institution-level aggregates.
# Without this filter, each institution appears ~3x (male, female, total).
# REASONING: The analysis requires one row per institution. Sex==99 provides
# the pre-aggregated institutional totals reported by IPEDS.
# ASSUMES: sex column contains value 99 for institutional totals.
print("\n--- Step 1: Filter to sex==99 (institution totals) ---")
pre_filter_rows = df.shape[0]
df = df.filter(pl.col("sex") == 99)
print(f"  Rows: {pre_filter_rows:,} -> {df.shape[0]:,} (removed {pre_filter_rows - df.shape[0]:,})")

# Step 2: Filter to year 2020
# INTENT: Keep only year==2020 to match the analysis time period.
# REASONING: The Plan specifies year 2020 for the cross-sectional analysis.
# ASSUMES: year column contains integer values.
print("\n--- Step 2: Filter to year==2020 ---")
pre_year_rows = df.shape[0]
df = df.filter(pl.col("year") == 2020)
print(f"  Rows: {pre_year_rows:,} -> {df.shape[0]:,} (removed {pre_year_rows - df.shape[0]:,})")

# Step 3: Replace coded missing values with null
# INTENT: Convert Portal coded missing values (-1, -2, -3) to proper nulls
# so they are correctly excluded from statistical calculations.
# REASONING: The Portal uses integer codes for missing/not-applicable/suppressed.
# If left as integers, they would corrupt means, sums, and ratios.
# ASSUMES: Coded values only appear in numeric measure columns, not in
# categorical columns like unitid, sex, or year.
print("\n--- Step 3: Replace coded missing values (-1, -2, -3) -> null ---")
for col_name in NUMERIC_COLS_TO_CLEAN:
    if col_name in df.columns:
        coded_count = df.filter(pl.col(col_name).is_in(CODED_MISSING_VALUES)).shape[0]
        print(f"  {col_name}: {coded_count} coded values replaced with null")
        df = df.with_columns(
            pl.when(pl.col(col_name).is_in(CODED_MISSING_VALUES))
            .then(None)
            .otherwise(pl.col(col_name))
            .alias(col_name)
        )

# Step 4: Compute admission rate
# INTENT: Calculate admit_rate = (number_admitted / number_applied) * 100.
# REASONING: Admission rate is a key measure of institutional selectivity,
# which is the central variable in this analysis.
# ASSUMES: number_applied > 0 for a valid ratio. Where number_applied is 0
# or null, admit_rate is set to null to avoid division by zero or meaningless values.
print("\n--- Step 4: Compute admission rate ---")
df = df.with_columns(
    pl.when(
        (pl.col("number_applied") > 0) &
        pl.col("number_applied").is_not_null() &
        pl.col("number_admitted").is_not_null()
    )
    .then((pl.col("number_admitted") / pl.col("number_applied")) * 100.0)
    .otherwise(None)
    .alias("admit_rate")
)

non_null_admit = df.filter(pl.col("admit_rate").is_not_null()).shape[0]
null_admit = df.filter(pl.col("admit_rate").is_null()).shape[0]
print(f"  admit_rate computed: {non_null_admit:,} non-null, {null_admit:,} null")

# Step 5: Validate admit_rate range
# INTENT: Confirm all non-null admit_rate values are in [0, 100].
# REASONING: Admission rate is a percentage; values outside this range indicate
# data errors or incorrect computation.
# ASSUMES: number_admitted <= number_applied for valid institutions.
print("\n--- Step 5: Validate admit_rate range ---")
out_of_range = df.filter(
    pl.col("admit_rate").is_not_null() &
    ((pl.col("admit_rate") < 0) | (pl.col("admit_rate") > 100))
)
print(f"  admit_rate values outside [0, 100]: {out_of_range.shape[0]}")
if out_of_range.shape[0] > 0:
    print(f"  WARNING: {out_of_range.shape[0]} institutions have admit_rate > 100 or < 0")
    print(f"  These may be data entry errors in IPEDS.")
    # REASONING: Some institutions report more admitted than applied (data quality issue).
    # Cap at 100 rather than dropping, to preserve institutions in the dataset.
    # This is a known IPEDS data quality issue.
    df = df.with_columns(
        pl.when(pl.col("admit_rate") > 100)
        .then(100.0)
        .otherwise(pl.col("admit_rate"))
        .alias("admit_rate")
    )
    print(f"  Capped {out_of_range.shape[0]} values at 100.")

# Step 6: Select final columns
# INTENT: Keep only the columns needed for downstream analysis to reduce
# memory footprint and clarify the data contract.
# REASONING: Plan specifies unitid, number_applied, number_admitted,
# number_enrolled_total, and admit_rate as the output columns.
print("\n--- Step 6: Select final columns ---")
clean_df = df.select([
    "unitid",
    "number_applied",
    "number_admitted",
    "number_enrolled_total",
    "admit_rate",
])
print(f"  Selected columns: {clean_df.columns}")
print(f"  Shape: {clean_df.shape[0]:,} rows x {clean_df.shape[1]} cols")

# --- Post-state ---
# Capture post-transformation state for comparison and reporting.
post_rows = clean_df.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {clean_df.shape[1]} cols")
print(f"Sample unitids: {clean_df['unitid'].head(3).to_list()}")
print(f"Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# Null counts per column
print(f"\nNull counts in clean data:")
for col_name in clean_df.columns:
    null_ct = clean_df[col_name].null_count()
    print(f"  {col_name}: {null_ct} nulls ({null_ct / post_rows * 100:.1f}%)")

# Uniqueness check
# INTENT: Verify unitid is unique in the cleaned data (one row per institution).
# ASSUMES: After filtering to sex==99 and year==2020, each unitid appears once.
n_unique = clean_df["unitid"].n_unique()
print(f"\nUnitid uniqueness: {n_unique:,} unique out of {post_rows:,} rows")
assert n_unique == post_rows, f"STOP: unitid not unique! {n_unique} unique vs {post_rows} rows"

# Descriptive stats for key variables
print(f"\nDescriptive statistics:")
print(clean_df.describe())

# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning operations -- confirm coded values
# are removed, suppression rates are within tolerance, and data loss is acceptable.
# ASSUMES: raw_df is pre-cleaning state, clean_df is post-cleaning state,
# KEY_VARIABLES lists the columns to validate.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True
max_suppression = SUPPRESSION_THRESHOLD
max_data_loss = 0.9  # 90% threshold

# Data loss check
raw_rows = len(raw_df)
clean_rows = len(clean_df)
rows_removed = raw_rows - clean_rows
loss_rate = rows_removed / raw_rows if raw_rows > 0 else 0

print(f"\nData Loss:")
print(f"  Raw rows:     {raw_rows:,}")
print(f"  Clean rows:   {clean_rows:,}")
print(f"  Rows removed: {rows_removed:,} ({loss_rate:.1%})")

if loss_rate > max_data_loss:
    print(f"[FAIL] Data loss rate {loss_rate:.1%} exceeds {max_data_loss:.0%}")
    cp2_passed = False
elif loss_rate > 0.5:
    # REASONING: We expect ~67% loss from sex filter (keeping 1 of 3 sex categories)
    # plus potential year filtering. This is expected, not a quality concern.
    print(f"[PASS] Data loss rate {loss_rate:.1%} -- expected due to sex/year filter (keeping 1 of ~3 sex categories for 1 year)")
else:
    print(f"[PASS] Data loss rate {loss_rate:.1%} within tolerance")

# Suppression rate check (on raw data, for sex==99 and year==2020 subset)
# REASONING: We check suppression on the filtered subset (sex==99, year==2020)
# since that is the relevant population for the analysis.
raw_filtered = raw_df.filter((pl.col("sex") == 99) & (pl.col("year") == 2020))
raw_filtered_rows = len(raw_filtered)
print(f"\nSuppression Rates (in raw data, sex==99 & year==2020 subset, n={raw_filtered_rows:,}):")
for var in KEY_VARIABLES:
    if var in raw_filtered.columns:
        suppressed = raw_filtered.filter(pl.col(var) == SUPPRESSION_CODE).shape[0]
        supp_rate = suppressed / raw_filtered_rows if raw_filtered_rows > 0 else 0
        if supp_rate > max_suppression:
            print(f"[FAIL] {var}: {supp_rate:.1%} suppressed (>{max_suppression:.0%} threshold)")
            cp2_passed = False
        elif supp_rate > 0.2:
            print(f"[WARN] {var}: {supp_rate:.1%} suppressed (notable)")
        else:
            print(f"[PASS] {var}: {supp_rate:.1%} suppressed")
    else:
        print(f"[SKIP] {var}: not in raw data (derived column)")

# Coded values remaining in clean data
print(f"\nCoded Values Check (clean data):")
coded_found = False
for var in KEY_VARIABLES:
    if var in clean_df.columns:
        dtype = clean_df[var].dtype
        if dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            coded = sum(clean_df.filter(pl.col(var) == c).shape[0] for c in CODED_MISSING_VALUES)
            if coded > 0:
                print(f"[WARN] {var}: {coded} coded values remain")
                coded_found = True
if not coded_found:
    print("[PASS] No coded values remain in key variables")

# Admit rate range check
print(f"\nAdmit Rate Range Check:")
admit_non_null = clean_df.filter(pl.col("admit_rate").is_not_null())
if admit_non_null.shape[0] > 0:
    min_rate = admit_non_null["admit_rate"].min()
    max_rate = admit_non_null["admit_rate"].max()
    print(f"  Range: {min_rate:.1f} to {max_rate:.1f}")
    if min_rate >= 0 and max_rate <= 100:
        print(f"[PASS] All admit_rate values in [0, 100]")
    else:
        print(f"[FAIL] admit_rate values outside [0, 100]")
        cp2_passed = False
else:
    print(f"[WARN] No non-null admit_rate values")

# Row count range check (Plan expects 2,000-3,500)
print(f"\nRow Count Range Check:")
if 2000 <= clean_rows <= 3500:
    print(f"[PASS] {clean_rows:,} rows within expected range [2,000-3,500]")
elif 1500 <= clean_rows <= 4500:
    print(f"[WARN] {clean_rows:,} rows near expected range [2,000-3,500]")
else:
    print(f"[FAIL] {clean_rows:,} rows outside expected range [2,000-3,500]")
    cp2_passed = False

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")

# --- Citation ---
# INTENT: Generate data citation for the IPEDS admissions data per ODC-By license.
print("\n--- Citation ---")
print("IPEDS Admissions and Enrollment, Education Data Portal (Version 0.20.0),")
print("Urban Institute, accessed March 29, 2026,")
print("https://educationdata.urban.org/documentation/,")
print("made available under the ODC Attribution License.")

# --- Save ---
# Persist results in parquet format.
# Output paths match the Plan's file specification.
clean_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Final shape: {clean_df.shape[0]:,} rows x {clean_df.shape[1]} cols")
print(f"\nDONE: Stage 6.2 Clean IPEDS Admissions complete.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:25:11
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage6_clean/02_clean-admissions.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.2: Clean IPEDS Admissions Data
# ============================================================
# Loaded: 11,910 rows x 9 cols
# Columns: ['unitid', 'year', 'fips', 'sex', 'number_applied', 'number_admitted', 'number_enrolled_ft', 'number_enrolled_pt', 'number_enrolled_total']
# Dtypes: [Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64]
# 
# Pre-state: 11,910 rows, 9 cols
# Sample unitids: [100654, 100654, 100654]
# 
# Sex value distribution:
# shape: (3, 2)
# ┌─────┬──────┐
# │ sex ┆ len  │
# │ --- ┆ ---  │
# │ i64 ┆ u32  │
# ╞═════╪══════╡
# │ 1   ┆ 3970 │
# │ 2   ┆ 3970 │
# │ 99  ┆ 3970 │
# └─────┴──────┘
# 
# Year value distribution:
# shape: (2, 2)
# ┌──────┬──────┐
# │ year ┆ len  │
# │ ---  ┆ ---  │
# │ i64  ┆ u32  │
# ╞══════╪══════╡
# │ 2020 ┆ 5967 │
# │ 2021 ┆ 5943 │
# └──────┴──────┘
# 
# --- Step 1: Filter to sex==99 (institution totals) ---
#   Rows: 11,910 -> 3,970 (removed 7,940)
# 
# --- Step 2: Filter to year==2020 ---
#   Rows: 3,970 -> 1,989 (removed 1,981)
# 
# --- Step 3: Replace coded missing values (-1, -2, -3) -> null ---
#   number_applied: 0 coded values replaced with null
#   number_admitted: 0 coded values replaced with null
#   number_enrolled_ft: 0 coded values replaced with null
#   number_enrolled_pt: 0 coded values replaced with null
#   number_enrolled_total: 0 coded values replaced with null
# 
# --- Step 4: Compute admission rate ---
#   admit_rate computed: 1,966 non-null, 23 null
# 
# --- Step 5: Validate admit_rate range ---
#   admit_rate values outside [0, 100]: 0
# 
# --- Step 6: Select final columns ---
#   Selected columns: ['unitid', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admit_rate']
#   Shape: 1,989 rows x 5 cols
# 
# Post-state: 1,989 rows, 5 cols
# Sample unitids: [100654, 100663, 100706]
# Row change: -9,921 (-83.3%)
# 
# Null counts in clean data:
#   unitid: 0 nulls (0.0%)
#   number_applied: 0 nulls (0.0%)
#   number_admitted: 23 nulls (1.2%)
#   number_enrolled_total: 25 nulls (1.3%)
#   admit_rate: 23 nulls (1.2%)
# 
# Unitid uniqueness: 1,989 unique out of 1,989 rows
# 
# Descriptive statistics:
# shape: (9, 6)
# ┌────────────┬───────────────┬────────────────┬─────────────────┬─────────────────────┬────────────┐
# │ statistic  ┆ unitid        ┆ number_applied ┆ number_admitted ┆ number_enrolled_tot ┆ admit_rate │
# │ ---        ┆ ---           ┆ ---            ┆ ---             ┆ al                  ┆ ---        │
# │ str        ┆ f64           ┆ f64            ┆ f64             ┆ ---                 ┆ f64        │
# │            ┆               ┆                ┆                 ┆ f64                 ┆            │
# ╞════════════╪═══════════════╪════════════════╪═════════════════╪═════════════════════╪════════════╡
# │ count      ┆ 1989.0        ┆ 1989.0         ┆ 1966.0          ┆ 1964.0              ┆ 1966.0     │
# │ null_count ┆ 0.0           ┆ 0.0            ┆ 23.0            ┆ 25.0                ┆ 23.0       │
# │ mean       ┆ 224890.833585 ┆ 5825.701357    ┆ 3578.694303     ┆ 801.238798          ┆ 71.217225  │
# │ std        ┆ 106587.8359   ┆ 10808.406814   ┆ 5891.773274     ┆ 1375.075243         ┆ 21.329822  │
# │ min        ┆ 100654.0      ┆ 0.0            ┆ 0.0             ┆ 0.0                 ┆ 0.0        │
# │ 25%        ┆ 157951.0      ┆ 272.0          ┆ 219.0           ┆ 95.0                ┆ 59.5439    │
# │ 50%        ┆ 196176.0      ┆ 2016.0         ┆ 1440.0          ┆ 326.0               ┆ 75.244644  │
# │ 75%        ┆ 230889.0      ┆ 6046.0         ┆ 4108.0          ┆ 788.0               ┆ 87.5       │
# │ max        ┆ 495916.0      ┆ 108870.0       ┆ 74604.0         ┆ 15614.0             ┆ 100.0      │
# └────────────┴───────────────┴────────────────┴─────────────────┴─────────────────────┴────────────┘
# 
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
# 
# Data Loss:
#   Raw rows:     11,910
#   Clean rows:   1,989
#   Rows removed: 9,921 (83.3%)
# [PASS] Data loss rate 83.3% -- expected due to sex/year filter (keeping 1 of ~3 sex categories for 1 year)
# 
# Suppression Rates (in raw data, sex==99 & year==2020 subset, n=1,989):
# [PASS] number_applied: 0.0% suppressed
# [PASS] number_admitted: 0.0% suppressed
# [PASS] number_enrolled_total: 0.0% suppressed
# [SKIP] admit_rate: not in raw data (derived column)
# 
# Coded Values Check (clean data):
# [PASS] No coded values remain in key variables
# 
# Admit Rate Range Check:
#   Range: 0.0 to 100.0
# [PASS] All admit_rate values in [0, 100]
# 
# Row Count Range Check:
# [WARN] 1,989 rows near expected range [2,000-3,500]
# 
# CP2 VALIDATION: PASSED
# ============================================================
# 
# --- Citation ---
# IPEDS Admissions and Enrollment, Education Data Portal (Version 0.20.0),
# Urban Institute, accessed March 29, 2026,
# https://educationdata.urban.org/documentation/,
# made available under the ODC Attribution License.
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/processed/2026-03-29_admissions_clean.parquet
# Final shape: 1,989 rows x 5 cols
# 
# DONE: Stage 6.2 Clean IPEDS Admissions complete.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
