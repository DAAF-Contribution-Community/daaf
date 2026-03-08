#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 4.2 (QA2)

Reviewed script: scripts/stage6_clean/07_clean-retention.py
Output files: data/processed/2026-02-15_retention_clean.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No unexpected nulls in critical ID columns

QA Checks (Script-Specific — Five Lenses):
6. [Counterfactual] Verify scale conversion math: raw * 100 == cleaned values
7. [Semantic] Retention rate semantically valid as quality proxy (mean ~70%, range 0-100)
8. [Boundary] Check edge cases: 0.00% and 100.00% retention institutions
9. [Absence] Verify no rows were dropped (zero row loss requirement)
10. [Downstream] Verify unitid uniqueness for 1:1 join in join-resources (Step 6.1)

Spot-Checks:
11. Trace 5 specific institutions through raw -> clean, verify values
12. Verify null count unchanged (654 pre = 654 post, no new nulls created)
13. Verify no negative values remain (would indicate coded value leak)
14. Check quartile structure for plausibility
15. Verify year column preserved correctly (all 2020)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_retention_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_retention.parquet"

EXPECTED_COLUMNS = ["unitid", "year", "retention_rate"]
EXPECTED_ROWS = 5836  # Exact from Stage 5 fetch
EXPECTED_MIN_ROWS = 5836
EXPECTED_MAX_ROWS = 5836  # Zero row change expected
CRITICAL_ID_COLUMNS = ["unitid", "year"]  # Must have no nulls
CRITICAL_ANALYSIS_COL = "retention_rate"

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 4.2 — clean-retention")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded cleaned: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Load raw for comparison
df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw:     {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

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
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROWS:,})")

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

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical ID column nulls ---
id_null_issues = []
for col in CRITICAL_ID_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            id_null_issues.append(f"{col}: {null_count} nulls")
id_nulls_ok = len(id_null_issues) == 0
print(f"[{'PASS' if id_nulls_ok else 'FAIL'}] Critical ID nulls: ", end="")
print("None" if id_nulls_ok else "; ".join(id_null_issues))

# === SCRIPT-SPECIFIC CHECKS (Five Lenses) ===
print("\n" + "-" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("-" * 60)

# --- Check 6: [Counterfactual] Scale conversion verification ---
# If scale conversion was done correctly, every non-null cleaned value should
# equal the corresponding raw value * 100.
print("\n[Counterfactual] Scale conversion verification:")
# Join raw and cleaned on unitid to compare
raw_with_clean = df_raw.select([
    pl.col("unitid"),
    pl.col("retention_rate").alias("raw_retention")
]).join(
    df.select([
        pl.col("unitid"),
        pl.col("retention_rate").alias("clean_retention")
    ]),
    on="unitid",
    how="inner"
)

# For non-null pairs, check raw * 100 == clean
both_non_null = raw_with_clean.filter(
    pl.col("raw_retention").is_not_null() & pl.col("clean_retention").is_not_null()
)
if both_non_null.height > 0:
    # Check if raw * 100 matches clean (within floating point tolerance)
    conversion_check = both_non_null.with_columns(
        (pl.col("raw_retention") * 100 - pl.col("clean_retention")).abs().alias("diff")
    )
    max_diff = conversion_check["diff"].max()
    mismatches = conversion_check.filter(pl.col("diff") > 0.001).height
    scale_ok = mismatches == 0
    print(f"  [{'PASS' if scale_ok else 'FAIL'}] raw * 100 == clean for all {both_non_null.height:,} non-null pairs")
    print(f"  Max abs difference: {max_diff}")
    if mismatches > 0:
        print(f"  Mismatches: {mismatches}")
        print(conversion_check.filter(pl.col("diff") > 0.001).head(5))
else:
    print("  [WARN] No non-null pairs found for conversion check")

# --- Check 7: [Semantic] Retention rate as quality proxy ---
print("\n[Semantic] Retention rate plausibility as quality proxy:")
non_null = df.filter(pl.col("retention_rate").is_not_null())
if non_null.height > 0:
    mean_val = non_null["retention_rate"].mean()
    median_val = non_null["retention_rate"].median()
    std_val = non_null["retention_rate"].std()
    # National average FTFT retention is ~70-80%. Mean should be in that range.
    mean_ok = 50 <= mean_val <= 90
    print(f"  Mean:   {mean_val:.2f} (expect 50-90)")
    print(f"  Median: {median_val:.2f}")
    print(f"  Std:    {std_val:.2f}")
    print(f"  [{'PASS' if mean_ok else 'FAIL'}] Mean in expected range: {mean_ok}")

# --- Check 8: [Boundary] Edge case institutions ---
print("\n[Boundary] Edge case analysis:")
zeros = df.filter(pl.col("retention_rate") == 0.0)
hundreds = df.filter(pl.col("retention_rate") == 100.0)
print(f"  Institutions with 0.00% retention: {zeros.height}")
print(f"  Institutions with 100.00% retention: {hundreds.height}")
# Check for values outside [0, 100] (should be impossible after correct conversion)
non_null_vals = df.filter(pl.col("retention_rate").is_not_null())
out_of_range = non_null_vals.filter(
    (pl.col("retention_rate") < 0) | (pl.col("retention_rate") > 100)
)
boundary_ok = out_of_range.height == 0
print(f"  Values outside [0, 100]: {out_of_range.height}")
print(f"  [{'PASS' if boundary_ok else 'FAIL'}] All values in valid range")
# INFO: Zero retention could be legitimate for very small institutions
if zeros.height > 0:
    print(f"  INFO: {zeros.height} institutions at 0% — legitimate for small/closing institutions")

# --- Check 9: [Absence] Zero row loss verification ---
print("\n[Absence] Zero row loss verification:")
raw_rows = df_raw.shape[0]
clean_rows = df.shape[0]
row_loss = raw_rows - clean_rows
absence_ok = row_loss == 0
print(f"  Raw rows:   {raw_rows:,}")
print(f"  Clean rows: {clean_rows:,}")
print(f"  Row delta:  {row_loss}")
print(f"  [{'PASS' if absence_ok else 'FAIL'}] No rows added or removed")

# --- Check 10: [Downstream] unitid uniqueness for join-resources ---
print("\n[Downstream] unitid uniqueness for join-resources (Step 6.1):")
unitid_unique = df["unitid"].n_unique()
unitid_total = df.shape[0]
unitid_ok = unitid_unique == unitid_total
print(f"  Unique unitids: {unitid_unique:,}")
print(f"  Total rows:     {unitid_total:,}")
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] unitid is unique (1:1 join safe)")
if not unitid_ok:
    dups = df.group_by("unitid").len().filter(pl.col("len") > 1).sort("len", descending=True).head(5)
    print(f"  Top duplicates:\n{dups}")

# === SPOT-CHECKS ===
print("\n" + "-" * 60)
print("SPOT-CHECKS")
print("-" * 60)

# --- Spot-Check 11: Trace 5 institutions raw -> clean ---
print("\n[Spot-Check 11] Trace 5 institutions through raw -> clean:")
sample_unitids = df_raw.filter(pl.col("retention_rate").is_not_null()).sample(5, seed=42)["unitid"].to_list()
trace_issues = 0
for uid in sample_unitids:
    raw_row = df_raw.filter(pl.col("unitid") == uid)
    clean_row = df.filter(pl.col("unitid") == uid)
    if raw_row.height == 0 or clean_row.height == 0:
        print(f"  unitid={uid}: MISSING in {'raw' if raw_row.height == 0 else 'clean'}")
        trace_issues += 1
        continue
    raw_val = raw_row["retention_rate"][0]
    clean_val = clean_row["retention_rate"][0]
    if raw_val is None:
        expected_clean = None
        match = clean_val is None
    else:
        expected_clean = raw_val * 100
        match = clean_val is not None and abs(clean_val - expected_clean) < 0.001
    status = "OK" if match else "MISMATCH"
    if not match:
        trace_issues += 1
    print(f"  unitid={uid}: raw={raw_val} -> expected={expected_clean} -> actual={clean_val} [{status}]")
trace_ok = trace_issues == 0
print(f"[{'PASS' if trace_ok else 'FAIL'}] All {len(sample_unitids)} traces match")

# --- Spot-Check 12: Null count preservation ---
print("\n[Spot-Check 12] Null count preservation:")
raw_nulls = df_raw["retention_rate"].null_count()
clean_nulls = df["retention_rate"].null_count()
null_preserved_ok = raw_nulls == clean_nulls
print(f"  Raw nulls:   {raw_nulls:,}")
print(f"  Clean nulls: {clean_nulls:,}")
print(f"  [{'PASS' if null_preserved_ok else 'FAIL'}] Null count preserved (no new nulls, no fills)")

# --- Spot-Check 13: No negative values ---
print("\n[Spot-Check 13] No negative values remain:")
negatives = df.filter(
    pl.col("retention_rate").is_not_null() & (pl.col("retention_rate") < 0)
)
neg_ok = negatives.height == 0
print(f"  Negative values: {negatives.height}")
print(f"  [{'PASS' if neg_ok else 'FAIL'}] No negative values in retention_rate")

# --- Spot-Check 14: Quartile plausibility ---
print("\n[Spot-Check 14] Quartile structure plausibility:")
if non_null.height > 0:
    q25 = non_null["retention_rate"].quantile(0.25)
    q50 = non_null["retention_rate"].quantile(0.50)
    q75 = non_null["retention_rate"].quantile(0.75)
    print(f"  Q25: {q25:.2f}")
    print(f"  Q50: {q50:.2f}")
    print(f"  Q75: {q75:.2f}")
    # Quartiles should be monotonically increasing and between 0-100
    quartile_ok = 0 <= q25 <= q50 <= q75 <= 100
    # Additionally, for retention rates, Q25 should be > 30 and Q75 < 100
    quartile_plausible = q25 > 20 and q75 < 100
    print(f"  [{'PASS' if quartile_ok and quartile_plausible else 'WARN'}] Quartile structure: {'plausible' if quartile_ok and quartile_plausible else 'unexpected'}")

# --- Spot-Check 15: Year column preserved ---
print("\n[Spot-Check 15] Year column preserved correctly:")
if "year" in df.columns:
    unique_years = df["year"].unique().to_list()
    year_ok = unique_years == [2020] or set(unique_years) == {2020}
    print(f"  Unique years: {unique_years}")
    print(f"  [{'PASS' if year_ok else 'FAIL'}] Only year 2020 present")
else:
    print("  [FAIL] Year column not found")

# --- Summary ---
all_checks = [
    schema_ok, rows_ok, dist_ok, coded_ok, id_nulls_ok,
    scale_ok, mean_ok, boundary_ok, absence_ok, unitid_ok,
    trace_ok, null_preserved_ok, neg_ok
]
all_passed = all(all_checks)
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA RESULT: {severity}")
if not all_passed:
    failed = [name for name, ok in zip([
        "Schema", "RowCount", "Distribution", "CodedValues", "IDNulls",
        "ScaleConversion", "MeanPlausibility", "BoundaryRange", "ZeroRowLoss",
        "UnitidUniqueness", "TraceVerification", "NullPreservation", "NoNegatives"
    ], all_checks) if not ok]
    print(f"Failed checks: {failed}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nretention_rate distribution (non-null):")
if non_null.height > 0:
    print(f"  Count: {non_null.height:,}")
    print(f"  Min:    {non_null['retention_rate'].min():.2f}")
    print(f"  P5:     {non_null['retention_rate'].quantile(0.05):.2f}")
    print(f"  P10:    {non_null['retention_rate'].quantile(0.10):.2f}")
    print(f"  Q25:    {non_null['retention_rate'].quantile(0.25):.2f}")
    print(f"  Median: {non_null['retention_rate'].quantile(0.50):.2f}")
    print(f"  Q75:    {non_null['retention_rate'].quantile(0.75):.2f}")
    print(f"  P90:    {non_null['retention_rate'].quantile(0.90):.2f}")
    print(f"  P95:    {non_null['retention_rate'].quantile(0.95):.2f}")
    print(f"  Max:    {non_null['retention_rate'].max():.2f}")

print("\nretention_rate value counts (top 20):")
print(df["retention_rate"].value_counts().sort("count", descending=True).head(20))

print("\nNull summary:")
for col in df.columns:
    nc = df[col].null_count()
    print(f"  {col}: {nc:,} nulls ({nc/len(df)*100:.1f}%)")

print("\nDtype summary:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:57:45
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 4.2 — clean-retention
# ============================================================
# Loaded cleaned: 5,836 rows x 3 cols
# Loaded raw:     5,836 rows x 3 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 5,836 (expected exactly 5,836)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None remain
# [PASS] Critical ID nulls: None
# 
# ------------------------------------------------------------
# SCRIPT-SPECIFIC CHECKS
# ------------------------------------------------------------
# 
# [Counterfactual] Scale conversion verification:
#   [PASS] raw * 100 == clean for all 5,182 non-null pairs
#   Max abs difference: 0.0
# 
# [Semantic] Retention rate plausibility as quality proxy:
#   Mean:   70.65 (expect 50-90)
#   Median: 73.00
#   Std:    18.71
#   [PASS] Mean in expected range: True
# 
# [Boundary] Edge case analysis:
#   Institutions with 0.00% retention: 55
#   Institutions with 100.00% retention: 333
#   Values outside [0, 100]: 0
#   [PASS] All values in valid range
#   INFO: 55 institutions at 0% — legitimate for small/closing institutions
# 
# [Absence] Zero row loss verification:
#   Raw rows:   5,836
#   Clean rows: 5,836
#   Row delta:  0
#   [PASS] No rows added or removed
# 
# [Downstream] unitid uniqueness for join-resources (Step 6.1):
#   Unique unitids: 5,836
#   Total rows:     5,836
#   [PASS] unitid is unique (1:1 join safe)
# 
# ------------------------------------------------------------
# SPOT-CHECKS
# ------------------------------------------------------------
# 
# [Spot-Check 11] Trace 5 institutions through raw -> clean:
#   unitid=455220: raw=0.38 -> expected=38.0 -> actual=38.0 [OK]
#   unitid=182892: raw=0.83 -> expected=83.0 -> actual=83.0 [OK]
#   unitid=493521: raw=0.8 -> expected=80.0 -> actual=80.0 [OK]
#   unitid=418409: raw=0.92 -> expected=92.0 -> actual=92.0 [OK]
#   unitid=450641: raw=0.75 -> expected=75.0 -> actual=75.0 [OK]
# [PASS] All 5 traces match
# 
# [Spot-Check 12] Null count preservation:
#   Raw nulls:   654
#   Clean nulls: 654
#   [PASS] Null count preserved (no new nulls, no fills)
# 
# [Spot-Check 13] No negative values remain:
#   Negative values: 0
#   [PASS] No negative values in retention_rate
# 
# [Spot-Check 14] Quartile structure plausibility:
#   Q25: 60.00
#   Q50: 73.00
#   Q75: 83.00
#   [PASS] Quartile structure: plausible
# 
# [Spot-Check 15] Year column preserved correctly:
#   Unique years: [2020]
#   [PASS] Only year 2020 present
# 
# ============================================================
# QA RESULT: BLOCKER
# Failed checks: ['Distribution']
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 3)
# ┌────────┬──────┬────────────────┐
# │ unitid ┆ year ┆ retention_rate │
# │ ---    ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ f64            │
# ╞════════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 54.0           │
# │ 100663 ┆ 2020 ┆ 86.0           │
# │ 100690 ┆ 2020 ┆ 50.0           │
# │ 100706 ┆ 2020 ┆ 82.0           │
# │ 100724 ┆ 2020 ┆ 62.0           │
# │ …      ┆ …    ┆ …              │
# │ 101189 ┆ 2020 ┆ 60.0           │
# │ 101240 ┆ 2020 ┆ 54.0           │
# │ 101277 ┆ 2020 ┆ 78.0           │
# │ 101286 ┆ 2020 ┆ 55.0           │
# │ 101295 ┆ 2020 ┆ 64.0           │
# └────────┴──────┴────────────────┘
# 
# Descriptive statistics:
# shape: (9, 4)
# ┌────────────┬───────────────┬────────┬────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ retention_rate │
# │ ---        ┆ ---           ┆ ---    ┆ ---            │
# │ str        ┆ f64           ┆ f64    ┆ f64            │
# ╞════════════╪═══════════════╪════════╪════════════════╡
# │ count      ┆ 5836.0        ┆ 5836.0 ┆ 5182.0         │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 654.0          │
# │ mean       ┆ 283846.361378 ┆ 2020.0 ┆ 70.652065      │
# │ std        ┆ 137931.042049 ┆ 0.0    ┆ 18.70617       │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.0            │
# │ 25%        ┆ 169734.0      ┆ 2020.0 ┆ 60.0           │
# │ 50%        ┆ 219921.0      ┆ 2020.0 ┆ 73.0           │
# │ 75%        ┆ 445267.0      ┆ 2020.0 ┆ 83.0           │
# │ max        ┆ 496423.0      ┆ 2020.0 ┆ 100.0          │
# └────────────┴───────────────┴────────┴────────────────┘
# 
# retention_rate distribution (non-null):
#   Count: 5,182
#   Min:    0.00
#   P5:     38.00
#   P10:    50.00
#   Q25:    60.00
#   Median: 73.00
#   Q75:    83.00
#   P90:    93.00
#   P95:    100.00
#   Max:    100.00
# 
# retention_rate value counts (top 20):
# shape: (20, 2)
# ┌────────────────┬───────┐
# │ retention_rate ┆ count │
# │ ---            ┆ ---   │
# │ f64            ┆ u32   │
# ╞════════════════╪═══════╡
# │ null           ┆ 654   │
# │ 100.0          ┆ 333   │
# │ 67.0           ┆ 160   │
# │ 75.0           ┆ 158   │
# │ 83.0           ┆ 135   │
# │ …              ┆ …     │
# │ 76.0           ┆ 110   │
# │ 60.0           ┆ 110   │
# │ 50.0           ┆ 109   │
# │ 81.0           ┆ 104   │
# │ 79.0           ┆ 103   │
# └────────────────┴───────┘
# 
# Null summary:
#   unitid: 0 nulls (0.0%)
#   year: 0 nulls (0.0%)
#   retention_rate: 654 nulls (11.2%)
# 
# Dtype summary:
#   unitid: Int64
#   year: Int64
#   retention_rate: Float64
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
