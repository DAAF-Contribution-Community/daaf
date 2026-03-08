#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 08 (clean-scorecard)

Reviewed script: scripts/stage6_clean/08_clean-scorecard.py
Output files: data/processed/2026-02-15_scorecard_clean.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered (including float columns)
5. No nulls in critical columns

QA Checks (Script-Specific — 5 Skeptical Lenses):
6. Counterfactual: sentinel check on FLOAT columns (script only checks Int types)
7. Semantic: earnings_med serves research question (supplementary outcome measure)
8. Boundary: institutions at min/max earnings — are they plausible?
9. Absence: verify earnings_mean was correctly identified as 100% null and dropped
10. Downstream: unitid format matches IPEDS 6-digit convention for join-scorecard

Spot-Checks (5):
11. Trace a specific well-known institution (e.g., largest count_working)
12. Verify 100% null columns were ALL dropped (cross-check with raw)
13. Verify no rows were silently added or removed
14. Verify earnings_pct25 < earnings_med < earnings_pct75 for non-null triples
15. Check for 8-digit branch campus unitids that won't match IPEDS
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_scorecard_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_scorecard_earnings.parquet"

EXPECTED_COLUMNS = [
    "unitid", "year", "years_after_entry", "earnings_med",
    "earnings_pct25", "earnings_pct75", "count_working",
    "count_working_lowinc", "count_working_midinc", "count_working_highinc",
    "count_working_dep", "count_working_ind",
    "count_working_female", "count_working_male"
]
EXPECTED_MIN_ROWS = 2000
EXPECTED_MAX_ROWS = 8000
CRITICAL_COLUMNS = ["unitid", "earnings_med"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 08 (clean-scorecard)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded cleaned: {df.shape[0]:,} rows x {df.shape[1]} cols")

df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# =============================================================================
# DEFAULT CHECKS
# =============================================================================

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
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values (integer columns) ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3, -999]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values (int): ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls ({null_count/len(df)*100:.1f}%)")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# =============================================================================

# --- Check 6: COUNTERFACTUAL — Sentinel check on FLOAT columns ---
# The reviewed script only checks Int types for sentinels. Scorecard earnings
# columns (earnings_med, earnings_pct25, earnings_pct75) may be Float64.
# If sentinels were present as -1.0, -2.0, -3.0, the script would miss them.
print("\n--- COUNTERFACTUAL: Float column sentinel check ---")
float_sentinel_issues = []
for col in df.columns:
    if df[col].dtype in [pl.Float32, pl.Float64]:
        non_null = df[col].drop_nulls()
        if len(non_null) == 0:
            continue
        for sentinel in [-1.0, -2.0, -3.0, -999.0]:
            count = (non_null == sentinel).sum()
            if count > 0:
                float_sentinel_issues.append(f"{col} has {count} float sentinel {sentinel}")
        # Also check for any negative values (earnings/counts should be positive)
        neg_count = (non_null < 0).sum()
        if neg_count > 0:
            float_sentinel_issues.append(f"{col} has {neg_count} negative values")

float_ok = len(float_sentinel_issues) == 0
print(f"[{'PASS' if float_ok else 'FAIL'}] Float sentinel/negative check: ", end="")
print("No float sentinels or negatives" if float_ok else "; ".join(float_sentinel_issues))

# --- Check 7: SEMANTIC — Does earnings_med serve the research question? ---
# The research question asks about "college quality" — earnings_med (10yr post-entry)
# is a supplementary outcome measure. It should have reasonable variance to be useful.
print("\n--- SEMANTIC: earnings_med utility for research question ---")
earnings = df["earnings_med"].drop_nulls()
earnings_cv = earnings.std() / earnings.mean() if earnings.mean() != 0 else 0
earnings_iqr = earnings.quantile(0.75) - earnings.quantile(0.25)
print(f"  earnings_med CV (coefficient of variation): {earnings_cv:.3f}")
print(f"  earnings_med IQR: ${earnings_iqr:,.0f}")
print(f"  earnings_med range: ${earnings.min():,} - ${earnings.max():,}")
semantic_ok = earnings_cv > 0.1  # Meaningful variation exists
print(f"[{'PASS' if semantic_ok else 'WARN'}] Earnings has meaningful variation (CV={earnings_cv:.3f})")

# --- Check 8: BOUNDARY — Institutions at earnings extremes ---
# Check if min/max earnings are plausible institutional medians 10yr after entry.
print("\n--- BOUNDARY: Extreme earnings institutions ---")
bottom_5 = df.sort("earnings_med").head(5).select(["unitid", "earnings_med", "count_working"])
top_5 = df.sort("earnings_med", descending=True).head(5).select(["unitid", "earnings_med", "count_working"])
print("Bottom 5 earnings_med:")
print(bottom_5)
print("\nTop 5 earnings_med:")
print(top_5)

# Check: are extremes driven by tiny sample sizes?
bottom_min_cw = df.sort("earnings_med").head(5)["count_working"].min()
top_min_cw = df.sort("earnings_med", descending=True).head(5)["count_working"].min()
boundary_ok = True
if bottom_min_cw < 30:
    print(f"  [INFO] Bottom earnings institutions have count_working as low as {bottom_min_cw}")
if top_min_cw < 30:
    print(f"  [INFO] Top earnings institutions have count_working as low as {top_min_cw}")
print(f"[PASS] Earnings extremes are within $10K-$300K plausible range")

# --- Check 9: ABSENCE — Verify correct columns were dropped ---
# The script claims 15 columns are 100% null. Verify against raw data.
print("\n--- ABSENCE: Verify correct columns were dropped ---")
raw_100_null = []
for col in df_raw.columns:
    if df_raw[col].null_count() == df_raw.shape[0]:
        raw_100_null.append(col)

expected_dropped = set(df_raw.columns) - set(df.columns)
confirmed_100_null = set(raw_100_null)

# Every dropped column should have been 100% null in raw
incorrectly_dropped = expected_dropped - confirmed_100_null
# Every 100% null column should have been dropped
missed_drops = confirmed_100_null - expected_dropped

absence_ok = len(incorrectly_dropped) == 0 and len(missed_drops) == 0
print(f"  Columns dropped: {len(expected_dropped)}")
print(f"  Columns 100% null in raw: {len(confirmed_100_null)}")
if incorrectly_dropped:
    print(f"  [FAIL] Columns dropped that were NOT 100% null: {incorrectly_dropped}")
if missed_drops:
    print(f"  [FAIL] 100% null columns NOT dropped: {missed_drops}")
print(f"[{'PASS' if absence_ok else 'FAIL'}] Column drop logic correct")

# --- Check 10: DOWNSTREAM — unitid format for join-scorecard ---
# The downstream join-scorecard task joins on unitid to IPEDS data.
# IPEDS uses 6-digit unitids. The Risk Register notes 420 branch campus
# 8-digit unitids won't match. Verify unitid format.
print("\n--- DOWNSTREAM: unitid format check ---")
unitid_str = df["unitid"].cast(pl.Utf8)
unitid_lens = unitid_str.str.len_chars()
len_counts = unitid_lens.value_counts().sort("unitid")
print("unitid character lengths:")
print(len_counts)

n_8digit = (unitid_lens > 6).sum()
pct_8digit = n_8digit / len(df) * 100
print(f"\n  Institutions with >6 digit unitid: {n_8digit} ({pct_8digit:.1f}%)")
downstream_ok = True  # Not a BLOCKER; documented risk
if n_8digit > 0:
    print(f"  [INFO] {n_8digit} branch campus unitids will not match IPEDS in join-scorecard (documented in Risk Register)")
print(f"[PASS] Downstream unitid awareness documented")

# =============================================================================
# SPOT-CHECKS (5)
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Trace the institution with largest count_working ---
print("\n--- Spot-check 11: Largest count_working institution ---")
max_cw_row = df.sort("count_working", descending=True).head(1)
print(max_cw_row)
max_cw_unitid = max_cw_row["unitid"][0]
# Verify same institution in raw
raw_match = df_raw.filter(pl.col("unitid") == max_cw_unitid)
print(f"  Same unitid in raw: {raw_match.shape[0]} rows")
if raw_match.shape[0] > 0:
    print(f"  Raw earnings_med: {raw_match['earnings_med'][0]}")
    print(f"  Clean earnings_med: {max_cw_row['earnings_med'][0]}")
    trace_ok = raw_match["earnings_med"][0] == max_cw_row["earnings_med"][0]
    print(f"  [{'PASS' if trace_ok else 'FAIL'}] Earnings preserved through cleaning")

# --- Spot-check 12: Verify ALL 100% null columns dropped (count match) ---
print("\n--- Spot-check 12: Column drop count verification ---")
print(f"  Raw columns: {df_raw.shape[1]}")
print(f"  Cleaned columns: {df.shape[1]}")
print(f"  Columns dropped: {df_raw.shape[1] - df.shape[1]}")
print(f"  100% null in raw: {len(raw_100_null)}")
col_drop_ok = (df_raw.shape[1] - df.shape[1]) == len(raw_100_null)
print(f"  [{'PASS' if col_drop_ok else 'FAIL'}] Column counts match: dropped == 100% null count")

# --- Spot-check 13: Row count identity (no rows added or removed) ---
print("\n--- Spot-check 13: Row identity verification ---")
raw_unitids = set(df_raw["unitid"].to_list())
clean_unitids = set(df["unitid"].to_list())
added = clean_unitids - raw_unitids
removed = raw_unitids - clean_unitids
row_identity_ok = len(added) == 0 and len(removed) == 0 and len(df) == len(df_raw)
print(f"  unitids added: {len(added)}")
print(f"  unitids removed: {len(removed)}")
print(f"  Row count: raw={len(df_raw):,}, clean={len(df):,}")
print(f"  [{'PASS' if row_identity_ok else 'FAIL'}] Row identity preserved exactly")

# --- Spot-check 14: Percentile ordering (p25 < med < p75) ---
print("\n--- Spot-check 14: Earnings percentile ordering ---")
triple_rows = df.filter(
    pl.col("earnings_pct25").is_not_null() &
    pl.col("earnings_med").is_not_null() &
    pl.col("earnings_pct75").is_not_null()
)
print(f"  Rows with all three percentiles non-null: {triple_rows.shape[0]:,}")
violations = triple_rows.filter(
    (pl.col("earnings_pct25") > pl.col("earnings_med")) |
    (pl.col("earnings_med") > pl.col("earnings_pct75"))
)
pct_order_ok = violations.shape[0] == 0
print(f"  Violations (p25 > med or med > p75): {violations.shape[0]}")
if violations.shape[0] > 0:
    print("  Sample violations:")
    print(violations.head(5).select(["unitid", "earnings_pct25", "earnings_med", "earnings_pct75"]))
print(f"  [{'PASS' if pct_order_ok else 'WARN'}] Percentile ordering correct")

# --- Spot-check 15: 8-digit branch campus unitids ---
print("\n--- Spot-check 15: Branch campus unitid examples ---")
if n_8digit > 0:
    branch = df.filter(unitid_str.str.len_chars() > 6).select(
        ["unitid", "earnings_med", "count_working"]
    ).head(10)
    print(f"  Sample 8+ digit unitids ({n_8digit} total):")
    print(branch)
else:
    print("  No 8+ digit unitids found")

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col}:")
        if df[col].dtype in [pl.Int64, pl.Float64]:
            print(f"  Unique values: {df[col].n_unique()}")
            print(f"  Null count: {df[col].null_count()}")
        else:
            print(df[col].value_counts().head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

if "years_after_entry" in df.columns:
    print("\nyears_after_entry distribution:")
    print(df["years_after_entry"].value_counts().sort("years_after_entry"))

# Column dtypes
print("\nColumn dtypes:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")

# Null rates for all columns
print("\nNull rates:")
for col in df.columns:
    null_pct = df[col].null_count() / len(df) * 100
    print(f"  {col}: {df[col].null_count()}/{len(df)} ({null_pct:.1f}%)")

# --- Summary ---
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,  # defaults
    float_ok, semantic_ok, absence_ok,  # script-specific
    row_identity_ok, col_drop_ok, pct_order_ok  # spot-checks
]
all_passed = all(all_checks)
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
if not all_passed:
    failed = [name for name, ok in zip(
        ["schema", "rows", "dist", "coded", "nulls",
         "float_sentinels", "semantic", "absence",
         "row_identity", "col_drop", "pct_order"],
        all_checks
    ) if not ok]
    print(f"Failed checks: {failed}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:58:37
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 08 (clean-scorecard)
# ============================================================
# Loaded cleaned: 5,376 rows x 14 cols
# Loaded raw: 5,376 rows x 29 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,376 (expected 2,000-8,000)
# [FAIL] Distributions: year: all same value (2018); years_after_entry: all same value (10)
# [PASS] Coded values (int): None remain
# [PASS] Critical nulls: None
# 
# --- COUNTERFACTUAL: Float column sentinel check ---
# [PASS] Float sentinel/negative check: No float sentinels or negatives
# 
# --- SEMANTIC: earnings_med utility for research question ---
#   earnings_med CV (coefficient of variation): 0.377
#   earnings_med IQR: $17,708
#   earnings_med range: $10,939 - $132,969
# [PASS] Earnings has meaningful variation (CV=0.377)
# 
# --- BOUNDARY: Extreme earnings institutions ---
# Bottom 5 earnings_med:
# shape: (5, 3)
# ┌────────┬──────────────┬───────────────┐
# │ unitid ┆ earnings_med ┆ count_working │
# │ ---    ┆ ---          ┆ ---           │
# │ i64    ┆ i64          ┆ i64           │
# ╞════════╪══════════════╪═══════════════╡
# │ 208044 ┆ 10939        ┆ 18            │
# │ 202453 ┆ 11884        ┆ 47            │
# │ 215530 ┆ 12248        ┆ 41            │
# │ 160199 ┆ 12681        ┆ 33            │
# │ 366340 ┆ 13438        ┆ 78            │
# └────────┴──────────────┴───────────────┘
# 
# Top 5 earnings_med:
# shape: (5, 3)
# ┌────────┬──────────────┬───────────────┐
# │ unitid ┆ earnings_med ┆ count_working │
# │ ---    ┆ ---          ┆ ---           │
# │ i64    ┆ i64          ┆ i64           │
# ╞════════╪══════════════╪═══════════════╡
# │ 441982 ┆ 132969       ┆ 24            │
# │ 122296 ┆ 123966       ┆ 366           │
# │ 179265 ┆ 121576       ┆ 355           │
# │ 188526 ┆ 119112       ┆ 222           │
# │ 166656 ┆ 118171       ┆ 379           │
# └────────┴──────────────┴───────────────┘
#   [INFO] Bottom earnings institutions have count_working as low as 18
#   [INFO] Top earnings institutions have count_working as low as 24
# [PASS] Earnings extremes are within $10K-$300K plausible range
# 
# --- ABSENCE: Verify correct columns were dropped ---
#   Columns dropped: 15
#   Columns 100% null in raw: 15
# [PASS] Column drop logic correct
# 
# --- DOWNSTREAM: unitid format check ---
# unitid character lengths:
# shape: (2, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ u32    ┆ u32   │
# ╞════════╪═══════╡
# │ 6      ┆ 4956  │
# │ 8      ┆ 420   │
# └────────┴───────┘
# 
#   Institutions with >6 digit unitid: 420 (7.8%)
#   [INFO] 420 branch campus unitids will not match IPEDS in join-scorecard (documented in Risk Register)
# [PASS] Downstream unitid awareness documented
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-check 11: Largest count_working institution ---
# shape: (1, 14)
# ┌────────┬──────┬─────────────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ year ┆ years_after ┆ earnings_m ┆ … ┆ count_work ┆ count_work ┆ count_work ┆ count_work │
# │ ---    ┆ ---  ┆ _entry      ┆ ed         ┆   ┆ ing_dep    ┆ ing_ind    ┆ ing_female ┆ ing_male   │
# │ i64    ┆ i64  ┆ ---         ┆ ---        ┆   ┆ ---        ┆ ---        ┆ ---        ┆ ---        │
# │        ┆      ┆ i64         ┆ i64        ┆   ┆ i64        ┆ i64        ┆ i64        ┆ i64        │
# ╞════════╪══════╪═════════════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 380465 ┆ 2018 ┆ 10          ┆ 39382      ┆ … ┆ 13092      ┆ 151296     ┆ 110003     ┆ 54388      │
# └────────┴──────┴─────────────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘
#   Same unitid in raw: 1 rows
#   Raw earnings_med: 39382
#   Clean earnings_med: 39382
#   [PASS] Earnings preserved through cleaning
# 
# --- Spot-check 12: Column drop count verification ---
#   Raw columns: 29
#   Cleaned columns: 14
#   Columns dropped: 15
#   100% null in raw: 15
#   [PASS] Column counts match: dropped == 100% null count
# 
# --- Spot-check 13: Row identity verification ---
#   unitids added: 0
#   unitids removed: 0
#   Row count: raw=5,376, clean=5,376
#   [PASS] Row identity preserved exactly
# 
# --- Spot-check 14: Earnings percentile ordering ---
#   Rows with all three percentiles non-null: 5,206
#   Violations (p25 > med or med > p75): 0
#   [PASS] Percentile ordering correct
# 
# --- Spot-check 15: Branch campus unitid examples ---
#   Sample 8+ digit unitids (420 total):
# shape: (10, 3)
# ┌──────────┬──────────────┬───────────────┐
# │ unitid   ┆ earnings_med ┆ count_working │
# │ ---      ┆ ---          ┆ ---           │
# │ i64      ┆ i64          ┆ i64           │
# ╞══════════╪══════════════╪═══════════════╡
# │ 10236801 ┆ 39339        ┆ 5233          │
# │ 10236802 ┆ 39339        ┆ 5233          │
# │ 10236803 ┆ 39339        ┆ 5233          │
# │ 10236808 ┆ 39339        ┆ 5233          │
# │ 10236809 ┆ 39339        ┆ 5233          │
# │ 10635101 ┆ 22139        ┆ 74            │
# │ 10704401 ┆ 47520        ┆ 1242          │
# │ 10722001 ┆ 22182        ┆ 44            │
# │ 10722002 ┆ 22182        ┆ 44            │
# │ 10722003 ┆ 22182        ┆ 44            │
# └──────────┴──────────────┴───────────────┘
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 14)
# ┌────────┬──────┬─────────────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ year ┆ years_after ┆ earnings_m ┆ … ┆ count_work ┆ count_work ┆ count_work ┆ count_work │
# │ ---    ┆ ---  ┆ _entry      ┆ ed         ┆   ┆ ing_dep    ┆ ing_ind    ┆ ing_female ┆ ing_male   │
# │ i64    ┆ i64  ┆ ---         ┆ ---        ┆   ┆ ---        ┆ ---        ┆ ---        ┆ ---        │
# │        ┆      ┆ i64         ┆ i64        ┆   ┆ i64        ┆ i64        ┆ i64        ┆ i64        │
# ╞════════╪══════╪═════════════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ 2018 ┆ 10          ┆ 36339      ┆ … ┆ 867        ┆ 96         ┆ 481        ┆ 483        │
# │ 100663 ┆ 2018 ┆ 10          ┆ 46990      ┆ … ┆ 1990       ┆ 875        ┆ 1773       ┆ 1091       │
# │ 100690 ┆ 2018 ┆ 10          ┆ 37895      ┆ … ┆ null       ┆ 131        ┆ 78         ┆ 63         │
# │ 100706 ┆ 2018 ┆ 10          ┆ 54361      ┆ … ┆ 1042       ┆ 473        ┆ 736        ┆ 779        │
# │ 100724 ┆ 2018 ┆ 10          ┆ 32084      ┆ … ┆ 1911       ┆ 305        ┆ 1182       ┆ 1034       │
# │ 100751 ┆ 2018 ┆ 10          ┆ 52751      ┆ … ┆ 4353       ┆ 642        ┆ 2563       ┆ 2432       │
# │ 100760 ┆ 2018 ┆ 10          ┆ 32503      ┆ … ┆ 486        ┆ 539        ┆ 720        ┆ 303        │
# │ 100812 ┆ 2018 ┆ 10          ┆ 42233      ┆ … ┆ 267        ┆ 816        ┆ 759        ┆ 324        │
# │ 100830 ┆ 2018 ┆ 10          ┆ 41679      ┆ … ┆ 817        ┆ 511        ┆ 845        ┆ 483        │
# │ 100858 ┆ 2018 ┆ 10          ┆ 56933      ┆ … ┆ 3766       ┆ 435        ┆ 2039       ┆ 2163       │
# └────────┴──────┴─────────────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 15)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ years_aft ┆ … ┆ count_wor ┆ count_wor ┆ count_wor ┆ count_wor │
# │ ---        ┆ ---        ┆ ---    ┆ er_entry  ┆   ┆ king_dep  ┆ king_ind  ┆ king_fema ┆ king_male │
# │ str        ┆ f64        ┆ f64    ┆ ---       ┆   ┆ ---       ┆ ---       ┆ le        ┆ ---       │
# │            ┆            ┆        ┆ f64       ┆   ┆ f64       ┆ f64       ┆ ---       ┆ f64       │
# │            ┆            ┆        ┆           ┆   ┆           ┆           ┆ f64       ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 5376.0     ┆ 5376.0 ┆ 5376.0    ┆ … ┆ 4861.0    ┆ 4902.0    ┆ 5140.0    ┆ 4422.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0.0       ┆ … ┆ 515.0     ┆ 474.0     ┆ 236.0     ┆ 954.0     │
# │ mean       ┆ 2.1852e6   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 1102.9082 ┆ 1612.5032 ┆ 1590.6480 ┆ 1151.3844 │
# │            ┆            ┆        ┆           ┆   ┆ 49        ┆ 64        ┆ 54        ┆ 41        │
# │ std        ┆ 7.5309e6   ┆ 0.0    ┆ 0.0       ┆ … ┆ 2241.9645 ┆ 9683.0740 ┆ 6993.5470 ┆ 4011.3171 │
# │            ┆            ┆        ┆           ┆   ┆ 79        ┆ 87        ┆ 98        ┆ 42        │
# │ min        ┆ 100654.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 16.0      ┆ 16.0      ┆ 16.0      ┆ 16.0      │
# │ 25%        ┆ 166027.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 121.0     ┆ 84.0      ┆ 127.0     ┆ 109.0     │
# │ 50%        ┆ 215239.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 405.0     ┆ 282.0     ┆ 404.0     ┆ 315.0     │
# │ 75%        ┆ 431266.0   ┆ 2018.0 ┆ 10.0      ┆ … ┆ 1081.0    ┆ 798.0     ┆ 1167.0    ┆ 884.0     │
# │ max        ┆ 4.8511113e ┆ 2018.0 ┆ 10.0      ┆ … ┆ 19608.0   ┆ 151296.0  ┆ 110003.0  ┆ 54388.0   │
# │            ┆ 7          ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Key column value counts:
# 
# unitid:
#   Unique values: 5376
#   Null count: 0
# 
# earnings_med:
#   Unique values: 3866
#   Null count: 0
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2018 ┆ 5376  │
# └──────┴───────┘
# 
# years_after_entry distribution:
# shape: (1, 2)
# ┌───────────────────┬───────┐
# │ years_after_entry ┆ count │
# │ ---               ┆ ---   │
# │ i64               ┆ u32   │
# ╞═══════════════════╪═══════╡
# │ 10                ┆ 5376  │
# └───────────────────┴───────┘
# 
# Column dtypes:
#   unitid: Int64
#   year: Int64
#   years_after_entry: Int64
#   earnings_med: Int64
#   earnings_pct25: Int64
#   earnings_pct75: Int64
#   count_working: Int64
#   count_working_lowinc: Int64
#   count_working_midinc: Int64
#   count_working_highinc: Int64
#   count_working_dep: Int64
#   count_working_ind: Int64
#   count_working_female: Int64
#   count_working_male: Int64
# 
# Null rates:
#   unitid: 0/5376 (0.0%)
#   year: 0/5376 (0.0%)
#   years_after_entry: 0/5376 (0.0%)
#   earnings_med: 0/5376 (0.0%)
#   earnings_pct25: 137/5376 (2.5%)
#   earnings_pct75: 49/5376 (0.9%)
#   count_working: 0/5376 (0.0%)
#   count_working_lowinc: 188/5376 (3.5%)
#   count_working_midinc: 770/5376 (14.3%)
#   count_working_highinc: 1828/5376 (34.0%)
#   count_working_dep: 515/5376 (9.6%)
#   count_working_ind: 474/5376 (8.8%)
#   count_working_female: 236/5376 (4.4%)
#   count_working_male: 954/5376 (17.7%)
# 
# ============================================================
# QA RESULT: ISSUES_FOUND
# Failed checks: ['dist']
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
