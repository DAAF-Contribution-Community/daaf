#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 4

Reviewed script: scripts/stage6_clean/04_clean-fsa-grants.py
Output files: data/processed/2026-02-15_fsa_grants_clean.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

QA Checks (Script-Specific - Five Lenses):
6. [Counterfactual] Float-coded values: verify -1.0, -2.0, -3.0 also absent
7. [Semantic] pell_recipients serves research question: values reasonable for Pell share computation
8. [Boundary] Zero and max-value checks for pell_recipients and pell_disbursements
9. [Absence] Verify year==2020 only, unitid uniqueness for downstream 1:1 join
10. [Downstream] pell_recipients dtype compatible with division for pell_share computation

Spot-Checks:
11. Verify no fractional pell_recipients remain after rounding
12. Cross-check null alignment between pell_recipients and pell_disbursements
13. Verify pell_disbursements/pell_recipients ratio is reasonable (avg aid per student)
14. Sample specific unitids and verify values are plausible
15. Check for duplicate unitids (would break 1:1 join in join-core)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_fsa_grants_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_fsa_grants.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "pell_recipients", "pell_disbursements"]
EXPECTED_MIN_ROWS = 4000
EXPECTED_MAX_ROWS = 6000
CRITICAL_COLUMNS = ["unitid", "pell_recipients"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 4 — clean-fsa-grants")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Dtypes: {dict(zip(df.columns, [str(d) for d in df.dtypes]))}")

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

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
        continue
    for code in [-1, -2, -3, -1.0, -2.0, -3.0]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain (including float representation)" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
if nulls_ok:
    print("None in unitid or pell_recipients")
else:
    print("; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses of Skeptical Review)
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: [Counterfactual] Float-coded values ---
# The script checks for coded values [-1, -2, -3] as integers, but the data
# columns are Float64. Verify that Polars cross-type comparison worked and
# no -1.0, -2.0, -3.0 values remain.
print("\n--- Check 6: [Counterfactual] Float-typed coded values ---")
float_coded_count = 0
for col in ["pell_recipients", "pell_disbursements"]:
    if col in df.columns:
        for val in [-1.0, -2.0, -3.0]:
            cnt = df.filter(pl.col(col) == val).height
            float_coded_count += cnt
            if cnt > 0:
                print(f"  ISSUE: {col} has {cnt} values equal to {val}")
float_coded_ok = float_coded_count == 0
print(f"[{'PASS' if float_coded_ok else 'FAIL'}] No float-representation coded values remain: {float_coded_count} found")

# --- Check 7: [Semantic] Values reasonable for Pell share computation ---
# Downstream: pell_share = pell_recipients / enrollment_undergrad.
# pell_recipients should be non-negative and reasonably bounded.
# Largest universities have ~40-70K undergrads, so pell_recipients > 100K would be suspicious.
print("\n--- Check 7: [Semantic] Pell recipients reasonable for share computation ---")
pell = df["pell_recipients"].drop_nulls()
pell_max = pell.max()
pell_min = pell.min()
pell_zero_count = (pell == 0).sum()
semantic_ok = pell_min >= 0 and pell_max < 200000
print(f"  Min: {pell_min}, Max: {pell_max:,}")
print(f"  Zeros: {pell_zero_count} institutions with 0 Pell recipients")
print(f"  Mean: {pell.mean():,.1f}, Median: {pell.median():,.1f}")
print(f"[{'PASS' if semantic_ok else 'FAIL'}] Pell recipients in reasonable range for share computation")

# --- Check 8: [Boundary] Edge cases for zero, null, max ---
print("\n--- Check 8: [Boundary] Zero, null, and max value analysis ---")
# pell_recipients
pell_null = df["pell_recipients"].null_count()
pell_zero = df.filter(pl.col("pell_recipients") == 0).height
# pell_disbursements
disb_null = df["pell_disbursements"].null_count()
disb_zero = df.filter(pl.col("pell_disbursements") == 0).height
disb_max = df["pell_disbursements"].drop_nulls().max()
# Check if zeros in recipients also have zero disbursements (consistent)
zero_recip_nonzero_disb = df.filter(
    (pl.col("pell_recipients") == 0) & (pl.col("pell_disbursements") > 0)
).height
boundary_ok = True
print(f"  pell_recipients: {pell_null} nulls, {pell_zero} zeros")
print(f"  pell_disbursements: {disb_null} nulls, {disb_zero} zeros, max={disb_max:,.0f}")
print(f"  Institutions with 0 recipients but >0 disbursements: {zero_recip_nonzero_disb}")
if zero_recip_nonzero_disb > 0:
    print(f"  NOTE: {zero_recip_nonzero_disb} institutions have inconsistent zero recipients/nonzero disbursements")
    boundary_ok = False  # Mark as concern but not necessarily FAIL
print(f"[{'PASS' if boundary_ok else 'WARN'}] Boundary edge cases")

# --- Check 9: [Absence] Year==2020 only, unitid uniqueness ---
print("\n--- Check 9: [Absence] Year filter and unitid uniqueness ---")
years_present = df["year"].unique().sort().to_list()
year_ok = years_present == [2020]
print(f"  Years present: {years_present}")
print(f"[{'PASS' if year_ok else 'FAIL'}] Only year 2020 present")

unitid_count = df["unitid"].n_unique()
unitid_dupes = df.shape[0] - unitid_count
unitid_unique_ok = unitid_dupes == 0
print(f"  Unique unitids: {unitid_count:,}, Total rows: {df.shape[0]:,}, Duplicates: {unitid_dupes}")
print(f"[{'PASS' if unitid_unique_ok else 'FAIL'}] unitid is unique (required for 1:1 join in join-core)")

# --- Check 10: [Downstream] dtype compatibility for pell_share computation ---
print("\n--- Check 10: [Downstream] dtype compatibility for division ---")
pell_dtype = df["pell_recipients"].dtype
disb_dtype = df["pell_disbursements"].dtype
dtype_ok = pell_dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]
print(f"  pell_recipients dtype: {pell_dtype}")
print(f"  pell_disbursements dtype: {disb_dtype}")
print(f"[{'PASS' if dtype_ok else 'WARN'}] Numeric dtypes compatible with downstream division")

# =============================================================================
# SPOT-CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: No fractional pell_recipients after rounding ---
print("\n--- Spot-Check 11: No fractional pell_recipients remain ---")
fractional_remaining = df.filter(
    pl.col("pell_recipients").is_not_null()
    & (pl.col("pell_recipients") != pl.col("pell_recipients").round(0))
).height
frac_ok = fractional_remaining == 0
print(f"  Fractional pell_recipients remaining: {fractional_remaining}")
print(f"[{'PASS' if frac_ok else 'FAIL'}] All pell_recipients are integers (post-rounding)")

# --- Spot-Check 12: Null alignment between pell_recipients and pell_disbursements ---
print("\n--- Spot-Check 12: Null alignment between columns ---")
both_null = df.filter(
    pl.col("pell_recipients").is_null() & pl.col("pell_disbursements").is_null()
).height
recip_null_only = df.filter(
    pl.col("pell_recipients").is_null() & pl.col("pell_disbursements").is_not_null()
).height
disb_null_only = df.filter(
    pl.col("pell_recipients").is_not_null() & pl.col("pell_disbursements").is_null()
).height
print(f"  Both null: {both_null}")
print(f"  Only pell_recipients null: {recip_null_only}")
print(f"  Only pell_disbursements null: {disb_null_only}")
null_align_ok = recip_null_only == 0 and disb_null_only == 0
print(f"[{'PASS' if null_align_ok else 'WARN'}] Null patterns aligned between columns")

# --- Spot-Check 13: Average aid per student sanity check ---
print("\n--- Spot-Check 13: Pell aid per recipient sanity ---")
# In 2020, max Pell Grant was $6,345. Average should be somewhat below that.
valid_ratio = df.filter(
    pl.col("pell_recipients").is_not_null()
    & pl.col("pell_disbursements").is_not_null()
    & (pl.col("pell_recipients") > 0)
).with_columns(
    (pl.col("pell_disbursements") / pl.col("pell_recipients")).alias("avg_aid")
)
if valid_ratio.height > 0:
    avg_aid_stats = valid_ratio["avg_aid"]
    avg_aid_mean = avg_aid_stats.mean()
    avg_aid_min = avg_aid_stats.min()
    avg_aid_max = avg_aid_stats.max()
    avg_aid_median = avg_aid_stats.median()
    # In 2020, max Pell was $6,345. Average aid per student should be ~$3,000-$6,500.
    # Institutional average should not exceed ~$7,000 (slight overshoot OK due to partial-year enrollment)
    aid_ok = avg_aid_mean > 1000 and avg_aid_mean < 10000
    print(f"  Institutions with valid ratio: {valid_ratio.height:,}")
    print(f"  Avg aid per student: mean={avg_aid_mean:,.0f}, median={avg_aid_median:,.0f}")
    print(f"  Range: min={avg_aid_min:,.0f}, max={avg_aid_max:,.0f}")
    print(f"[{'PASS' if aid_ok else 'WARN'}] Average aid per recipient in expected range (~$3K-$6.5K max Pell)")
else:
    print("  No valid rows for ratio computation")
    aid_ok = False

# --- Spot-Check 14: Specific unitid plausibility ---
print("\n--- Spot-Check 14: Specific institution spot-check ---")
# Check a few well-known institutions by unitid if present
# 166027 = MIT, 243780 = Stanford, 110635 = UC Berkeley
known_unitids = {166027: "MIT", 243780: "Stanford", 110635: "UC Berkeley"}
for uid, name in known_unitids.items():
    row = df.filter(pl.col("unitid") == uid)
    if row.height > 0:
        pell_val = row["pell_recipients"][0]
        disb_val = row["pell_disbursements"][0]
        print(f"  {name} (unitid={uid}): pell_recipients={pell_val}, pell_disbursements={disb_val:,.0f}" if disb_val is not None else f"  {name} (unitid={uid}): pell_recipients={pell_val}, pell_disbursements=null")
    else:
        print(f"  {name} (unitid={uid}): not in dataset")
print("[INFO] Spot-check complete — values should be plausible for well-known institutions")

# --- Spot-Check 15: Duplicate unitid check (critical for join-core) ---
print("\n--- Spot-Check 15: Duplicate unitid check ---")
dupe_unitids = df.group_by("unitid").agg(pl.len().alias("cnt")).filter(pl.col("cnt") > 1)
dupe_ok = dupe_unitids.height == 0
if not dupe_ok:
    print(f"  ISSUE: {dupe_unitids.height} unitids with multiple rows!")
    print(dupe_unitids.head(10))
else:
    print(f"  No duplicate unitids found ({unitid_count:,} unique across {df.shape[0]:,} rows)")
print(f"[{'PASS' if dupe_ok else 'FAIL'}] No duplicate unitids")

# =============================================================================
# COMPARE WITH RAW DATA
# =============================================================================

print("\n" + "=" * 60)
print("RAW vs CLEAN COMPARISON")
print("=" * 60)

if RAW_FILE.exists():
    df_raw = pl.read_parquet(RAW_FILE)
    print(f"Raw: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")
    print(f"Clean: {df.shape[0]:,} rows x {df.shape[1]} cols")
    print(f"Row change: {df.shape[0] - df_raw.shape[0]:+,}")
    # Verify same unitids
    raw_unitids = set(df_raw["unitid"].to_list())
    clean_unitids = set(df["unitid"].to_list())
    lost_unitids = raw_unitids - clean_unitids
    gained_unitids = clean_unitids - raw_unitids
    print(f"  Lost unitids: {len(lost_unitids)}")
    print(f"  Gained unitids: {len(gained_unitids)}")
    raw_clean_match = len(lost_unitids) == 0 and len(gained_unitids) == 0
    print(f"[{'PASS' if raw_clean_match else 'FAIL'}] Same unitid set in raw and clean")
else:
    print("Raw file not found — skipping comparison")

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
        print(df[col].value_counts().sort("count", descending=True).head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

# Quantile distribution for pell_recipients
print("\nPell recipients quantiles:")
pell_non_null = df["pell_recipients"].drop_nulls()
for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
    print(f"  {q*100:.0f}th percentile: {pell_non_null.quantile(q):,.0f}")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
all_checks = [
    ("Schema", schema_ok),
    ("Row count", rows_ok),
    ("Distributions", dist_ok),
    ("Coded values", coded_ok),
    ("Critical nulls", nulls_ok),
    ("Float-coded values", float_coded_ok),
    ("Semantic range", semantic_ok),
    ("Boundary cases", boundary_ok),
    ("Year/uniqueness", year_ok and unitid_unique_ok),
    ("Dtype compatibility", dtype_ok),
    ("No fractional values", frac_ok),
    ("Null alignment", null_align_ok),
    ("Aid per recipient", aid_ok),
    ("No duplicate unitids", dupe_ok),
]

blockers = [name for name, ok in all_checks if not ok and name in ["Schema", "Row count", "Coded values", "Float-coded values", "No fractional values", "No duplicate unitids", "Year/uniqueness"]]
warnings = [name for name, ok in all_checks if not ok and name not in ["Schema", "Row count", "Coded values", "Float-coded values", "No fractional values", "No duplicate unitids", "Year/uniqueness"]]

if blockers:
    severity = "BLOCKER"
elif warnings:
    severity = "WARNING"
else:
    severity = "PASSED"

print(f"QA RESULT: {severity}")
if blockers:
    print(f"BLOCKERS: {blockers}")
if warnings:
    print(f"WARNINGS: {warnings}")
print(f"Checks passed: {sum(1 for _, ok in all_checks if ok)}/{len(all_checks)}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:46:19
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 4 — clean-fsa-grants
# ============================================================
# Loaded: 4,994 rows x 4 cols
# Dtypes: {'unitid': 'Int64', 'year': 'Int64', 'pell_recipients': 'Float64', 'pell_disbursements': 'Float64'}
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 4,994 (expected 4,000-6,000)
# [FAIL] Distributions: year: all same value (2020)
# [PASS] Coded values: None remain (including float representation)
# [FAIL] Critical nulls: pell_recipients: 6 nulls
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: [Counterfactual] Float-typed coded values ---
# [PASS] No float-representation coded values remain: 0 found
# 
# --- Check 7: [Semantic] Pell recipients reasonable for share computation ---
#   Min: 0.0, Max: 70,813.0
#   Zeros: 83 institutions with 0 Pell recipients
#   Mean: 1,269.1, Median: 362.0
# [PASS] Pell recipients in reasonable range for share computation
# 
# --- Check 8: [Boundary] Zero, null, and max value analysis ---
#   pell_recipients: 6 nulls, 83 zeros
#   pell_disbursements: 6 nulls, 83 zeros, max=224,762,800
#   Institutions with 0 recipients but >0 disbursements: 0
# [PASS] Boundary edge cases
# 
# --- Check 9: [Absence] Year filter and unitid uniqueness ---
#   Years present: [2020]
# [PASS] Only year 2020 present
#   Unique unitids: 4,994, Total rows: 4,994, Duplicates: 0
# [PASS] unitid is unique (required for 1:1 join in join-core)
# 
# --- Check 10: [Downstream] dtype compatibility for division ---
#   pell_recipients dtype: Float64
#   pell_disbursements dtype: Float64
# [PASS] Numeric dtypes compatible with downstream division
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-Check 11: No fractional pell_recipients remain ---
#   Fractional pell_recipients remaining: 0
# [PASS] All pell_recipients are integers (post-rounding)
# 
# --- Spot-Check 12: Null alignment between columns ---
#   Both null: 6
#   Only pell_recipients null: 0
#   Only pell_disbursements null: 0
# [PASS] Null patterns aligned between columns
# 
# --- Spot-Check 13: Pell aid per recipient sanity ---
#   Institutions with valid ratio: 4,905
#   Avg aid per student: mean=4,218, median=4,209
#   Range: min=705, max=9,517
# [PASS] Average aid per recipient in expected range (~$3K-$6.5K max Pell)
# 
# --- Spot-Check 14: Specific institution spot-check ---
#   MIT (unitid=166027): pell_recipients=1281.0, pell_disbursements=6,185,841
#   Stanford (unitid=243780): pell_recipients=5356.0, pell_disbursements=25,554,348
#   UC Berkeley (unitid=110635): pell_recipients=9049.0, pell_disbursements=46,521,624
# [INFO] Spot-check complete — values should be plausible for well-known institutions
# 
# --- Spot-Check 15: Duplicate unitid check ---
#   No duplicate unitids found (4,994 unique across 4,994 rows)
# [PASS] No duplicate unitids
# 
# ============================================================
# RAW vs CLEAN COMPARISON
# ============================================================
# Raw: 4,994 rows x 4 cols
# Clean: 4,994 rows x 4 cols
# Row change: +0
#   Lost unitids: 0
#   Gained unitids: 0
# [PASS] Same unitid set in raw and clean
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 4)
# ┌────────┬──────┬─────────────────┬────────────────────┐
# │ unitid ┆ year ┆ pell_recipients ┆ pell_disbursements │
# │ ---    ┆ ---  ┆ ---             ┆ ---                │
# │ i64    ┆ i64  ┆ f64             ┆ f64                │
# ╞════════╪══════╪═════════════════╪════════════════════╡
# │ 100654 ┆ 2020 ┆ 3607.0          ┆ 1.8499612e7        │
# │ 100663 ┆ 2020 ┆ 4966.0          ┆ 2.3012828e7        │
# │ 100690 ┆ 2020 ┆ 270.0           ┆ 1.0310e6           │
# │ 100706 ┆ 2020 ┆ 2048.0          ┆ 8.986248e6         │
# │ 100724 ┆ 2020 ┆ 2465.0          ┆ 1.2532547e7        │
# │ 100751 ┆ 2020 ┆ 5765.0          ┆ 2.6869592e7        │
# │ 100760 ┆ 2020 ┆ 572.0           ┆ 2.2938e6           │
# │ 100812 ┆ 2020 ┆ 1353.0          ┆ 5.312207e6         │
# │ 100830 ┆ 2020 ┆ 2272.0          ┆ 1.0718279e7        │
# │ 100858 ┆ 2020 ┆ 3366.0          ┆ 1.5990988e7        │
# └────────┴──────┴─────────────────┴────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 5)
# ┌────────────┬───────────────┬────────┬─────────────────┬────────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ pell_recipients ┆ pell_disbursements │
# │ ---        ┆ ---           ┆ ---    ┆ ---             ┆ ---                │
# │ str        ┆ f64           ┆ f64    ┆ f64             ┆ f64                │
# ╞════════════╪═══════════════╪════════╪═════════════════╪════════════════════╡
# │ count      ┆ 4994.0        ┆ 4994.0 ┆ 4988.0          ┆ 4988.0             │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 6.0             ┆ 6.0                │
# │ mean       ┆ 264892.57509  ┆ 2020.0 ┆ 1269.113071     ┆ 5.2844e6           │
# │ std        ┆ 131963.729845 ┆ 0.0    ┆ 2970.47238      ┆ 1.2168e7           │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.0             ┆ 0.0                │
# │ 25%        ┆ 162706.0      ┆ 2020.0 ┆ 82.0            ┆ 334101.0           │
# │ 50%        ┆ 211343.0      ┆ 2020.0 ┆ 362.0           ┆ 1.5640e6           │
# │ 75%        ┆ 420398.0      ┆ 2020.0 ┆ 1211.0          ┆ 4946663.5          │
# │ max        ┆ 497037.0      ┆ 2020.0 ┆ 70813.0         ┆ 2.247628e8         │
# └────────────┴───────────────┴────────┴─────────────────┴────────────────────┘
# 
# Key column value counts:
# 
# unitid:
# shape: (20, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ i64    ┆ u32   │
# ╞════════╪═══════╡
# │ 459347 ┆ 1     │
# │ 122117 ┆ 1     │
# │ 158325 ┆ 1     │
# │ 187134 ┆ 1     │
# │ 177117 ┆ 1     │
# │ …      ┆ …     │
# │ 116350 ┆ 1     │
# │ 155335 ┆ 1     │
# │ 161688 ┆ 1     │
# │ 163912 ┆ 1     │
# │ 226107 ┆ 1     │
# └────────┴───────┘
# 
# pell_recipients:
# shape: (20, 2)
# ┌─────────────────┬───────┐
# │ pell_recipients ┆ count │
# │ ---             ┆ ---   │
# │ f64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 0.0             ┆ 83    │
# │ 15.0            ┆ 29    │
# │ 19.0            ┆ 25    │
# │ 27.0            ┆ 22    │
# │ 39.0            ┆ 21    │
# │ …               ┆ …     │
# │ 47.0            ┆ 19    │
# │ 51.0            ┆ 18    │
# │ 18.0            ┆ 18    │
# │ 14.0            ┆ 18    │
# │ 34.0            ┆ 18    │
# └─────────────────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 4994  │
# └──────┴───────┘
# 
# Pell recipients quantiles:
#   1th percentile: 0
#   5th percentile: 13
#   10th percentile: 26
#   25th percentile: 82
#   50th percentile: 362
#   75th percentile: 1,211
#   90th percentile: 3,247
#   95th percentile: 5,306
#   99th percentile: 13,014
# 
# ============================================================
# QA RESULT: WARNING
# WARNINGS: ['Distributions', 'Critical nulls']
# Checks passed: 12/14
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
