#!/usr/bin/env python3
"""
Stage 6.8: Clean Scorecard earnings data — drop 100% null columns, validate
earnings distributions, document coverage.

Task: clean-scorecard
Wave: 4, Step: 8, Stage: 6
Depends on: fetch-scorecard (COMPLETE)
Input: data/raw/2026-02-15_scorecard_earnings.parquet
Output: data/processed/2026-02-15_scorecard_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for Scorecard earnings cleaning. The Scorecard uses
# native null values (not -1/-2/-3 coded values like CCD/CRDC). Per the
# education-data-context skill, Scorecard data covers Title IV aid recipients
# only. At yae=10, many subgroup earnings columns are 100% null because the
# Scorecard only populates them at certain years-after-entry values.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_scorecard_earnings.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_scorecard_clean.parquet"

# REASONING: The Scorecard does not use Education Data Portal coded missing
# values (-1, -2, -3). Instead it uses native null for suppressed or
# unavailable data. However, some older Scorecard data may use the string
# "PrivacySuppressed" or numeric sentinel values in raw form. Since the data
# was fetched via the Education Data Portal (which normalizes to null), we
# only need to check for any unexpected negative sentinel values in numeric
# columns as a safety measure.
CODED_MISSING_SENTINELS = [-1, -2, -3, -999]

# REASONING: earnings_med is the key column for our analysis. The research
# question asks whether graduation rates reflect selectivity vs. quality,
# and post-graduation earnings (10 years after entry) is our primary outcome
# measure. We also keep earnings_pct25 and earnings_pct75 for distribution
# context, and count_working for sample size documentation.
KEY_ANALYSIS_COLUMNS = ["unitid", "year", "earnings_med"]

# REASONING: Earnings below $10,000 or above $300,000 for median institutional
# earnings 10 years after entry would be extreme outliers. The Scorecard
# documentation notes earnings are from IRS W-2 records for employed Title IV
# recipients, so values should be positive and reasonable for annual wages.
EARNINGS_RANGE_MIN = 10000
EARNINGS_RANGE_MAX = 300000

# --- Load ---
# Load the raw Scorecard earnings data fetched in Stage 5.
print("=" * 60)
print("Stage 6.8: Clean Scorecard earnings data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture current state BEFORE transformation. We document which columns are
# 100% null so we can verify they were correctly dropped. Also check for any
# coded sentinels that might have leaked through the Portal normalization.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
pre_col_count = len(pre_cols)
print(f"\nPre-state: {pre_rows:,} rows, {pre_col_count} cols")

# Identify 100% null columns
# INTENT: Identify columns that carry no data at yae=10. These columns are
# populated at other years_after_entry values but are entirely null for our
# filtered subset. Keeping them would add noise to schema and confuse downstream.
null_100_cols = []
for col in df.columns:
    if df[col].null_count() == df.shape[0]:
        null_100_cols.append(col)

print(f"\nColumns that are 100% null ({len(null_100_cols)}):")
for col in null_100_cols:
    print(f"  - {col}")

# Check for coded sentinel values in numeric columns
# INTENT: Safety check — the Scorecard *should* use native nulls (not coded
# values), but we verify this assumption to avoid corrupted downstream stats.
# ASSUMES: All numeric columns with negative sentinels would indicate data
# quality issues, since the Scorecard reports counts and dollar amounts which
# should be non-negative (after Portal normalization).
print("\nCoded sentinel check (safety):")
sentinel_found = False
for col in df.columns:
    if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        non_null = df[col].drop_nulls()
        if len(non_null) == 0:
            continue
        for sentinel in CODED_MISSING_SENTINELS:
            count = (non_null == sentinel).sum()
            if count > 0:
                print(f"  WARNING: {col} has {count} values == {sentinel}")
                sentinel_found = True
if not sentinel_found:
    print("  No coded sentinels found (as expected for Scorecard)")

# --- Transform ---
# INTENT: Drop columns that are 100% null at yae=10, as they carry no
# information for our analysis. This reduces the schema from 29 to ~14
# useful columns without losing any actual data values.
#
# REASONING: Keeping 100% null columns would:
#   1. Inflate null counts in downstream profiling, misleadingly
#   2. Complicate schema documentation
#   3. Add no analytical value (no non-null values to analyze)
# We drop rather than filter rows because these columns are structurally
# empty for yae=10 across ALL institutions, not just some.
#
# ASSUMES:
#   - 100% null columns at yae=10 are structurally absent (not suppressed)
#   - All useful data for our analysis is in the remaining non-null columns
#   - unitid, year, earnings_med, count_working are NOT 100% null
cols_to_keep = [c for c in df.columns if c not in null_100_cols]
df = df.select(cols_to_keep)
print(f"\nDropped {len(null_100_cols)} columns that were 100% null")
print(f"Remaining columns ({len(cols_to_keep)}): {cols_to_keep}")

# --- Post-state ---
post_rows = df.shape[0]
post_cols = df.columns.copy()
post_col_count = len(post_cols)
print(f"\nPost-state: {post_rows:,} rows, {post_col_count} cols")
print(f"Row change: {((post_rows - pre_rows) / pre_rows * 100):+.1f}%")
print(f"Column change: {pre_col_count} -> {post_col_count} ({pre_col_count - post_col_count} dropped)")

# --- Earnings Distribution ---
# INTENT: Document the distribution of earnings_med so the orchestrator and
# code-reviewer can verify the data is reasonable for 10-year post-entry
# institutional median earnings.
#
# REASONING: Printing distribution stats is a core data-scientist principle
# (Principle 1: Data Robustness First). We check min, max, mean, median,
# and percentiles to identify any outliers or anomalies.
print("\n" + "=" * 60)
print("EARNINGS DISTRIBUTION (earnings_med)")
print("=" * 60)

earnings = df["earnings_med"]
earnings_non_null = earnings.drop_nulls()
print(f"  Non-null count: {len(earnings_non_null):,} / {df.shape[0]:,} ({len(earnings_non_null)/df.shape[0]*100:.1f}%)")
print(f"  Min:    ${earnings_non_null.min():,}")
print(f"  P25:    ${earnings_non_null.quantile(0.25):,.0f}")
print(f"  Median: ${earnings_non_null.median():,.0f}")
print(f"  Mean:   ${earnings_non_null.mean():,.0f}")
print(f"  P75:    ${earnings_non_null.quantile(0.75):,.0f}")
print(f"  Max:    ${earnings_non_null.max():,}")

# Check for out-of-range earnings
# INTENT: Flag any earnings values outside the expected $10K-$300K range.
# Values outside this range for institutional medians 10 years after entry
# would warrant investigation.
out_of_range = df.filter(
    (pl.col("earnings_med") < EARNINGS_RANGE_MIN) | (pl.col("earnings_med") > EARNINGS_RANGE_MAX)
)
print(f"\n  Out of range (${EARNINGS_RANGE_MIN:,}-${EARNINGS_RANGE_MAX:,}): {out_of_range.shape[0]:,} institutions")
if out_of_range.shape[0] > 0:
    print(f"  Below ${EARNINGS_RANGE_MIN:,}: {df.filter(pl.col('earnings_med') < EARNINGS_RANGE_MIN).shape[0]:,}")
    print(f"  Above ${EARNINGS_RANGE_MAX:,}: {df.filter(pl.col('earnings_med') > EARNINGS_RANGE_MAX).shape[0]:,}")

# --- Coverage Summary ---
# INTENT: Document how many institutions have non-null values for each
# remaining column so the orchestrator can assess data completeness.
print("\n" + "=" * 60)
print("COVERAGE SUMMARY (non-null counts per column)")
print("=" * 60)

for col in df.columns:
    non_null = df.shape[0] - df[col].null_count()
    pct = non_null / df.shape[0] * 100
    print(f"  {col}: {non_null:,}/{df.shape[0]:,} ({pct:.1f}%)")

# --- count_working Distribution ---
# INTENT: Document sample sizes (count_working) since Scorecard suppresses
# earnings when fewer than 30 students have positive earnings. This helps
# assess reliability of the earnings_med values.
print("\n" + "=" * 60)
print("SAMPLE SIZE DISTRIBUTION (count_working)")
print("=" * 60)

cw = df["count_working"].drop_nulls()
print(f"  Non-null: {len(cw):,}/{df.shape[0]:,}")
print(f"  Min:    {cw.min():,}")
print(f"  P25:    {cw.quantile(0.25):,.0f}")
print(f"  Median: {cw.median():,.0f}")
print(f"  Mean:   {cw.mean():,.0f}")
print(f"  Max:    {cw.max():,}")

# Institutions with very small sample sizes (potential reliability concern)
small_n = df.filter(pl.col("count_working") < 30).shape[0]
print(f"\n  Institutions with count_working < 30: {small_n:,}")

# --- Save ---
# Persist cleaned results in parquet format. The output directory should
# already exist from prior Stage 6 scripts, but create if needed.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Final shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- CP2 Validation ---
# Checkpoint validation: verify cleaning preserved rows, no coded sentinels
# remain, suppression rate is within tolerance, and key analysis columns exist.
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

cp2_passed = True

# CP2.1: Row count preserved (cleaning should NOT drop rows for Scorecard;
# we only dropped columns, not rows)
rows_preserved = post_rows == pre_rows
status = "PASS" if rows_preserved else "WARN"
print(f"  [{status}] Rows preserved: {pre_rows:,} -> {post_rows:,}")
if not rows_preserved:
    loss_pct = (pre_rows - post_rows) / pre_rows * 100
    if loss_pct > 90:
        print(f"  [FAIL] Row loss > 90%: {loss_pct:.1f}%")
        cp2_passed = False

# CP2.2: Key analysis columns present
missing_key_cols = [c for c in KEY_ANALYSIS_COLUMNS if c not in df.columns]
key_cols_ok = len(missing_key_cols) == 0
status = "PASS" if key_cols_ok else "FAIL"
print(f"  [{status}] Key analysis columns present: {KEY_ANALYSIS_COLUMNS}")
if not key_cols_ok:
    print(f"    Missing: {missing_key_cols}")
    cp2_passed = False

# CP2.3: No coded sentinel values in remaining numeric columns
# REASONING: Even though Scorecard uses native nulls, we confirm no coded
# values slipped through to ensure clean downstream statistical operations.
coded_remaining = 0
for col in df.columns:
    if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        non_null = df[col].drop_nulls()
        if len(non_null) == 0:
            continue
        for sentinel in CODED_MISSING_SENTINELS:
            coded_remaining += (non_null == sentinel).sum()

no_coded = coded_remaining == 0
status = "PASS" if no_coded else "WARN"
print(f"  [{status}] No coded sentinel values remaining: {coded_remaining}")

# CP2.4: Suppression rate for key columns < 50%
# REASONING: The 50% threshold is from CLAUDE.md STOP conditions. For Scorecard,
# "suppression" manifests as native null values. We check earnings_med specifically
# as our primary outcome variable.
earnings_null_rate = df["earnings_med"].null_count() / df.shape[0]
suppression_ok = earnings_null_rate < 0.50
status = "PASS" if suppression_ok else "FAIL"
print(f"  [{status}] earnings_med null rate < 50%: {earnings_null_rate:.1%}")
if not suppression_ok:
    cp2_passed = False

# CP2.5: Earnings range validation
# REASONING: Institutional median earnings 10 years after entry should fall
# within a reasonable range. Values outside $10K-$300K would be extreme.
earnings_non_null_check = df.filter(pl.col("earnings_med").is_not_null())
in_range = earnings_non_null_check.filter(
    (pl.col("earnings_med") >= EARNINGS_RANGE_MIN) & (pl.col("earnings_med") <= EARNINGS_RANGE_MAX)
)
range_pct = in_range.shape[0] / earnings_non_null_check.shape[0] if earnings_non_null_check.shape[0] > 0 else 0
range_ok = range_pct >= 0.95  # Allow up to 5% outside range
status = "PASS" if range_ok else "WARN"
print(f"  [{status}] earnings_med in range ${EARNINGS_RANGE_MIN:,}-${EARNINGS_RANGE_MAX:,}: {range_pct:.1%}")

# CP2.6: No 100% null columns remain
remaining_all_null = [c for c in df.columns if df[c].null_count() == df.shape[0]]
no_all_null = len(remaining_all_null) == 0
status = "PASS" if no_all_null else "WARN"
print(f"  [{status}] No 100% null columns remain: {len(remaining_all_null)}")
if not no_all_null:
    print(f"    Still 100% null: {remaining_all_null}")

# CP2.7: unitid uniqueness (one row per institution expected at year=2018, yae=10)
unitid_unique = df["unitid"].n_unique() == df.shape[0]
status = "PASS" if unitid_unique else "WARN"
print(f"  [{status}] unitid unique (1 row per institution): {df['unitid'].n_unique():,} unique / {df.shape[0]:,} rows")

assert key_cols_ok, "STOP: Missing key analysis columns"
assert suppression_ok, "STOP: earnings_med suppression rate >= 50%"

print("\n" + "=" * 60)
if cp2_passed:
    print("CP2 VALIDATION: PASSED")
else:
    print("CP2 VALIDATION: FAILED")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:50:29
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage6_clean/08_clean-scorecard.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 6.8: Clean Scorecard earnings data
# ============================================================
# Loaded: 5,376 rows x 29 cols
# 
# Pre-state: 5,376 rows, 29 cols
# 
# Columns that are 100% null (15):
#   - earnings_mean
#   - earnings_sd
#   - earnings_greater_than_25k_pct
#   - earnings_pct10
#   - earnings_pct90
#   - earnings_lowinc_mean
#   - earnings_midinc_mean
#   - earnings_highinc_mean
#   - earnings_dep_lowinc_mean
#   - earnings_dep_mean
#   - earnings_ind_mean
#   - earnings_female_mean
#   - earnings_male_mean
#   - count_not_working
#   - count_working_dep_lowinc
# 
# Coded sentinel check (safety):
#   No coded sentinels found (as expected for Scorecard)
# 
# Dropped 15 columns that were 100% null
# Remaining columns (14): ['unitid', 'year', 'years_after_entry', 'earnings_med', 'earnings_pct25', 'earnings_pct75', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
# 
# Post-state: 5,376 rows, 14 cols
# Row change: +0.0%
# Column change: 29 -> 14 (15 dropped)
# 
# ============================================================
# EARNINGS DISTRIBUTION (earnings_med)
# ============================================================
#   Non-null count: 5,376 / 5,376 (100.0%)
#   Min:    $10,939
#   P25:    $28,327
#   Median: $36,778
#   Mean:   $39,092
#   P75:    $46,035
#   Max:    $132,969
# 
#   Out of range ($10,000-$300,000): 0 institutions
# 
# ============================================================
# COVERAGE SUMMARY (non-null counts per column)
# ============================================================
#   unitid: 5,376/5,376 (100.0%)
#   year: 5,376/5,376 (100.0%)
#   years_after_entry: 5,376/5,376 (100.0%)
#   earnings_med: 5,376/5,376 (100.0%)
#   earnings_pct25: 5,239/5,376 (97.5%)
#   earnings_pct75: 5,327/5,376 (99.1%)
#   count_working: 5,376/5,376 (100.0%)
#   count_working_lowinc: 5,188/5,376 (96.5%)
#   count_working_midinc: 4,606/5,376 (85.7%)
#   count_working_highinc: 3,548/5,376 (66.0%)
#   count_working_dep: 4,861/5,376 (90.4%)
#   count_working_ind: 4,902/5,376 (91.2%)
#   count_working_female: 5,140/5,376 (95.6%)
#   count_working_male: 4,422/5,376 (82.3%)
# 
# ============================================================
# SAMPLE SIZE DISTRIBUTION (count_working)
# ============================================================
#   Non-null: 5,376/5,376
#   Min:    16
#   P25:    167
#   Median: 626
#   Mean:   2,470
#   Max:    164,390
# 
#   Institutions with count_working < 30: 137
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_scorecard_clean.parquet
# Final shape: 5,376 rows x 14 cols
# 
# ============================================================
# CHECKPOINT 2 VALIDATION
# ============================================================
#   [PASS] Rows preserved: 5,376 -> 5,376
#   [PASS] Key analysis columns present: ['unitid', 'year', 'earnings_med']
#   [PASS] No coded sentinel values remaining: 0
#   [PASS] earnings_med null rate < 50%: 0.0%
#   [PASS] earnings_med in range $10,000-$300,000: 100.0%
#   [PASS] No 100% null columns remain: 0
#   [PASS] unitid unique (1 row per institution): 5,376 unique / 5,376 rows
# 
# ============================================================
# CP2 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
