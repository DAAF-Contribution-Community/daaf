#!/usr/bin/env python3
"""
Stage 6.8: Clean IPEDS Finance data -- filter coded missing values, compute
instructional expenditure per FTE, validate range.

Task: clean-finance
Wave: 2, Step: 8, Stage: 6
Depends on: fetch-finance (Stage 5)
Input: data/raw/2026-03-29_ipeds_finance.parquet
Output: data/processed/2026-03-29_finance_clean.parquet
Checkpoint: CP2

Data year: 2017 (3-year lag from the 2020 base year accepted per Plan).
IPEDS Finance data uses fiscal year reporting. GASB/FASB accounting standard
differences exist across public/private sectors but do not affect the per-FTE
expenditure ratio computed here.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for IPEDS Finance cleaning.
# Column names are exact names from the Education Data Portal (EDP), confirmed
# during Stage 5 QA. The EDP uses lowercase, abbreviated variable names that
# differ from original IPEDS documentation.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_finance.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_finance_clean.parquet"

# REASONING: Column names confirmed by Stage 5 fetch QA inspection.
# exp_instruc_total = total instructional expenditures (abbreviated "instruc", not "instruction").
# est_fte = estimated full-time equivalent enrollment used as denominator.
EXPENDITURE_COL = "exp_instruc_total"
FTE_COL = "est_fte"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data. These must be replaced with null before any arithmetic to avoid corrupting
# the per-FTE ratio. For IPEDS finance data, -1 (missing), -2 (not applicable),
# -3 (suppressed) are the standard codes per education-data-context skill.
CODED_MISSING = [-1, -2, -3]

# Domain configuration from Plan
SUPPRESSION_CODE = -3
SUPPRESSION_THRESHOLD = 0.5  # 50% max suppression rate

# REASONING: Reasonable range for instructional expenditure per FTE based on
# higher education finance literature. Below $1,000 suggests a data error or
# non-degree-granting institution with minimal instruction. Above $200,000 is
# implausible even for elite research universities.
EXPEND_PER_FTE_MIN = 1000
EXPEND_PER_FTE_MAX = 200000

# --- Load ---
# Load raw IPEDS Finance data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.8: Clean IPEDS Finance data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Verify expected columns exist
assert "unitid" in df.columns, f"STOP: 'unitid' not found in columns: {df.columns[:10]}"
assert EXPENDITURE_COL in df.columns, f"STOP: '{EXPENDITURE_COL}' not found in columns"
assert FTE_COL in df.columns, f"STOP: '{FTE_COL}' not found in columns"

# Document data year
if "year" in df.columns:
    years_present = sorted(df["year"].unique().to_list())
    print(f"Years present: {years_present}")
else:
    print("No 'year' column -- single-year extract")
print("NOTE: Finance data year is 2017 (3-year lag from 2020 base year)")

# --- Pre-state ---
# Capture state BEFORE any transformations for post-validation comparison.
# Also enumerate coded values present so we can verify they are all removed.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# INTENT: Document coded values present in the two key numeric columns before cleaning.
# REASONING: We need to verify that all coded values are replaced with null after cleaning.
coded_counts = {}
for col in [EXPENDITURE_COL, FTE_COL]:
    for code in CODED_MISSING:
        count = df.filter(pl.col(col) == code).height
        if count > 0:
            coded_counts[(col, code)] = count

if coded_counts:
    print("Coded values found:")
    for (col, code), count in coded_counts.items():
        print(f"  {col} = {code}: {count:,}")
else:
    print("No coded missing values (-1, -2, -3) found in key columns")

# Document missingness in key columns before cleaning
for col in [EXPENDITURE_COL, FTE_COL]:
    null_count = df[col].null_count()
    null_pct = null_count / pre_rows * 100
    print(f"  {col} nulls: {null_count:,} ({null_pct:.1f}%)")

# --- Clean Step 1: Replace coded missing values with null ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in the two key
# numeric columns so downstream arithmetic is not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is semantically correct --
# these values were never observed. Zero would imply a measured value of zero
# expenditure or zero FTE, and NaN would complicate Polars aggregations.
#
# ASSUMES: All coded values in these columns follow the EDP convention (-1/-2/-3)
# per education-data-context skill. Stage 5 QA confirmed no coded missing values
# were detected in these columns, but we apply the replacement defensively.
for col in [EXPENDITURE_COL, FTE_COL]:
    df = df.with_columns(
        pl.when(pl.col(col).is_in(CODED_MISSING))
        .then(None)
        .otherwise(pl.col(col))
        .alias(col)
    )

print("\nReplaced coded values with null (defensive -- Stage 5 QA found none)")

# --- Clean Step 2: Filter est_fte > 0 and not null ---
# INTENT: Remove institutions with zero or null FTE before computing per-FTE ratio.
# Division by zero would produce infinity; null FTE means we cannot compute the ratio.
#
# REASONING: Stage 5 QA identified 39 institutions with est_fte=0 and 296 with
# est_fte null. Institutions with zero FTE are likely non-operational or have
# unusual reporting status (e.g., administrative-only entities).
#
# ASSUMES: Institutions with est_fte=0 or null are not meaningful for per-FTE
# expenditure analysis. This is a denominator validity filter, not a sample
# restriction -- these institutions cannot contribute to the ratio.
pre_fte_filter = df.shape[0]
df = df.filter(
    (pl.col(FTE_COL).is_not_null()) & (pl.col(FTE_COL) > 0)
)
post_fte_filter = df.shape[0]
fte_removed = pre_fte_filter - post_fte_filter
print(f"Filtered est_fte > 0: {pre_fte_filter:,} -> {post_fte_filter:,} (removed {fte_removed:,})")

# --- Clean Step 3: Compute instructional expenditure per FTE ---
# INTENT: Derive instr_expend_per_fte = exp_instruc_total / est_fte.
# Only compute where exp_instruc_total is not null; result is null otherwise.
#
# REASONING: This is the key derived metric for the analysis -- it normalizes
# instructional spending by institution size, enabling cross-institutional comparison.
# We preserve null when the numerator is null rather than imputing, because null
# expenditure means the institution did not report this figure.
#
# ASSUMES: est_fte > 0 guaranteed by the filter above (no division by zero).
# exp_instruc_total is in current dollars for fiscal year 2017.
df = df.with_columns(
    pl.when(pl.col(EXPENDITURE_COL).is_not_null())
    .then(pl.col(EXPENDITURE_COL) / pl.col(FTE_COL))
    .otherwise(None)
    .alias("instr_expend_per_fte")
)

non_null_ratio = df.filter(pl.col("instr_expend_per_fte").is_not_null()).height
print(f"Computed instr_expend_per_fte: {non_null_ratio:,} non-null values")

# --- Clean Step 4: Validate per-FTE range and flag outliers ---
# INTENT: Check that instr_expend_per_fte values fall within a reasonable range
# ($1,000-$200,000). Values outside this range are flagged but not removed --
# removal would be a methodological decision requiring Plan specification.
#
# REASONING: Range based on higher education finance norms. Very low values may
# indicate non-instructional institutions; very high values may indicate small
# specialized programs with few FTE students.
non_null_df = df.filter(pl.col("instr_expend_per_fte").is_not_null())
below_min = non_null_df.filter(pl.col("instr_expend_per_fte") < EXPEND_PER_FTE_MIN).height
above_max = non_null_df.filter(pl.col("instr_expend_per_fte") > EXPEND_PER_FTE_MAX).height
in_range = non_null_df.height - below_min - above_max

print(f"\nRange validation (non-null only, n={non_null_df.height:,}):")
print(f"  Below ${EXPEND_PER_FTE_MIN:,}: {below_min:,}")
print(f"  In range ${EXPEND_PER_FTE_MIN:,}-${EXPEND_PER_FTE_MAX:,}: {in_range:,}")
print(f"  Above ${EXPEND_PER_FTE_MAX:,}: {above_max:,}")

if non_null_df.height > 0:
    p5 = non_null_df["instr_expend_per_fte"].quantile(0.05)
    p25 = non_null_df["instr_expend_per_fte"].quantile(0.25)
    p50 = non_null_df["instr_expend_per_fte"].quantile(0.50)
    p75 = non_null_df["instr_expend_per_fte"].quantile(0.75)
    p95 = non_null_df["instr_expend_per_fte"].quantile(0.95)
    print(f"  Distribution: p5=${p5:,.0f}, p25=${p25:,.0f}, p50=${p50:,.0f}, p75=${p75:,.0f}, p95=${p95:,.0f}")

# --- Clean Step 5: Select output columns ---
# INTENT: Select only the columns needed for downstream joins and analysis.
# unitid is the join key; instr_expend_per_fte is the derived metric.
#
# REASONING: Downstream Stage 7 joins on unitid. Only the per-FTE metric is
# needed from IPEDS Finance -- the raw expenditure and FTE columns are
# intermediate and not required in the analysis dataset.
#
# ASSUMES: unitid is unique per institution in this single-year extract.
result = df.select(["unitid", "instr_expend_per_fte"])

# --- Post-state ---
post_rows = result.shape[0]
print(f"\nPost-state: {post_rows:,} rows x {result.shape[1]} cols")
print(f"Row change from raw: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")
print(f"Columns: {result.columns}")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP2 Validation: Post-Cleaning ---
# Checkpoint validation: verify all coded values removed, suppression rates
# within tolerance, data loss acceptable, derived column valid.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True

# CP2.1: Data loss check
loss_rate = (pre_rows - post_rows) / pre_rows if pre_rows > 0 else 0
print(f"\nData Loss:")
print(f"  Raw rows:     {pre_rows:,}")
print(f"  Clean rows:   {post_rows:,}")
print(f"  Rows removed: {pre_rows - post_rows:,} ({loss_rate:.1%})")

if loss_rate > 0.9:
    print(f"[FAIL] Data loss rate {loss_rate:.1%} exceeds 90%")
    cp2_passed = False
elif loss_rate > 0.5:
    print(f"[WARN] High data loss rate: {loss_rate:.1%}")
else:
    print(f"[PASS] Data loss rate {loss_rate:.1%} within tolerance")

# CP2.2: Row count in expected range (3,000-8,000 per task specification)
rows_in_range = 3000 <= post_rows <= 8000
if rows_in_range:
    print(f"[PASS] Row count {post_rows:,} in expected range [3,000-8,000]")
else:
    print(f"[WARN] Row count {post_rows:,} outside expected range [3,000-8,000]")

# CP2.3: No coded values remain in output
# INTENT: Verify coded missing values were fully replaced.
# Since output only has unitid and instr_expend_per_fte, check the derived column.
coded_remaining = 0
for code in CODED_MISSING:
    coded_remaining += result.filter(pl.col("instr_expend_per_fte") == code).height
no_coded = coded_remaining == 0
print(f"[{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")

# CP2.4: instr_expend_per_fte > 0 for all non-null rows
non_null_result = result.filter(pl.col("instr_expend_per_fte").is_not_null())
all_positive = non_null_result.filter(pl.col("instr_expend_per_fte") <= 0).height == 0
print(f"[{'PASS' if all_positive else 'FAIL'}] All non-null instr_expend_per_fte > 0")

# CP2.5: unitid is unique
unitid_unique = result["unitid"].n_unique() == result.shape[0]
print(f"[{'PASS' if unitid_unique else 'FAIL'}] unitid is unique: {result['unitid'].n_unique():,} unique / {result.shape[0]:,} rows")

# CP2.6: Null rate in derived column
null_in_derived = result["instr_expend_per_fte"].null_count()
null_rate_derived = null_in_derived / post_rows * 100 if post_rows > 0 else 0
print(f"[{'PASS' if null_rate_derived < 50 else 'WARN'}] instr_expend_per_fte null rate: {null_rate_derived:.1f}% ({null_in_derived:,} nulls)")

# CP2.7: unitid has no nulls (critical join key)
unitid_nulls = result["unitid"].null_count()
no_unitid_nulls = unitid_nulls == 0
print(f"[{'PASS' if no_unitid_nulls else 'FAIL'}] No nulls in unitid: {unitid_nulls}")

assert no_coded, "STOP: Coded values still present"
assert all_positive, "STOP: Non-positive instr_expend_per_fte values found"
assert unitid_unique, "STOP: unitid is not unique"
assert no_unitid_nulls, "STOP: Nulls in unitid (critical join key)"
assert loss_rate <= 0.9, "STOP: Data loss exceeds 90%"

if cp2_passed:
    print(f"\n{'=' * 60}")
    print("CP2 VALIDATION: PASSED")
    print(f"{'=' * 60}")
else:
    raise ValueError("CP2 FAILED - see details above")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:53:18
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/08_clean-finance.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.8: Clean IPEDS Finance data
# ============================================================
# Loaded: 6,857 rows x 141 cols
# Years present: [2017]
# NOTE: Finance data year is 2017 (3-year lag from 2020 base year)
#
# Pre-state: 6,857 rows, 141 cols
# No coded missing values (-1, -2, -3) found in key columns
#   exp_instruc_total nulls: 709 (10.3%)
#   est_fte nulls: 296 (4.3%)
#
# Replaced coded values with null (defensive -- Stage 5 QA found none)
# Filtered est_fte > 0: 6,857 -> 6,522 (removed 335)
# Computed instr_expend_per_fte: 6,076 non-null values
#
# Range validation (non-null only, n=6,076):
#   Below $1,000: 100
#   In range $1,000-$200,000: 5,942
#   Above $200,000: 34
#   Distribution: p5=$1,623, p25=$3,901, p50=$6,143, p75=$9,686, p95=$24,519
#
# Post-state: 6,522 rows x 2 cols
# Row change from raw: -335 (-4.9%)
# Columns: ['unitid', 'instr_expend_per_fte']
#
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_finance_clean.parquet
#
# ============================================================
# CP2 VALIDATION: POST-CLEANING
# ============================================================
#
# Data Loss:
#   Raw rows:     6,857
#   Clean rows:   6,522
#   Rows removed: 335 (4.9%)
# [PASS] Data loss rate 4.9% within tolerance
# [PASS] Row count 6,522 in expected range [3,000-8,000]
# [PASS] No coded values remaining: 0
# [PASS] All non-null instr_expend_per_fte > 0
# [PASS] unitid is unique: 6,522 unique / 6,522 rows
# [PASS] instr_expend_per_fte null rate: 6.8% (446 nulls)
# [PASS] No nulls in unitid: 0
#
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
