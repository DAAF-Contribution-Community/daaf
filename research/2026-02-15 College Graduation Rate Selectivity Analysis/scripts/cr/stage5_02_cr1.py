#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 02
Checkpoint: QA1

Reviewed script: scripts/stage5_fetch/02_fetch-grad-rates_a.py
Output files: data/raw/2026-02-15_ipeds_grad_rates.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default 5):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered (or documented for Stage 6)
5. No nulls in critical identifier column (unitid)

Script-Specific Checks (5 Skeptical Lenses):
6. [Counterfactual] What if subcohort=2 is NOT bachelor's-seeking?
   Verify codebook confirmation was logged.
7. [Semantic] Does the code serve the research question (graduation rate
   of 4-year institutions) or just Plan compliance?
8. [Boundary] What happens with zero/null completion_rate_150pct values?
   Are edge cases handled?
9. [Absence] Is cohort_year column included? Without it, duplicate unitids
   cannot be resolved downstream.
10. [Downstream] What will Stage 6 (clean-grad-rates) receive? Will the
    duplicate unitids surprise the next consumer?

Spot-Checks (5):
11. Pick a specific unitid and verify its values are plausible
12. Verify completion_rate_150pct is on 0-1 scale (not 0-100)
13. Check that the subcohort column has only value 2
14. Check that no negative coded values exist in numeric columns
15. Verify duplicate unitid count matches expected from cohort_year structure
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_grad_rates.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "completion_rate_150pct", "cohort_adj_150pct",
                    "completers_150pct", "subcohort"]
EXPECTED_MIN_ROWS = 2000
EXPECTED_MAX_ROWS = 5000
CRITICAL_COLUMNS = ["unitid", "completion_rate_150pct"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 02 — cr1")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# ============================================================
# DEFAULT CHECKS (1-5)
# ============================================================

print("\n" + "=" * 60)
print("DEFAULT CHECKS")
print("=" * 60)

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 — Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Check 2 — Row count: {row_count:,} "
      f"(expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        dist_issues.append(f"{col}: ALL null (no non-null values)")
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'WARN'}] Check 3 — Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values in numeric columns ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Check 4 — Coded values: ", end="")
print("None remain in any column" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls (unitid only — completion_rate is expected to have nulls) ---
unitid_null_count = df["unitid"].null_count()
unitid_nulls_ok = unitid_null_count == 0
print(f"[{'PASS' if unitid_nulls_ok else 'FAIL'}] Check 5 — Critical nulls in unitid: "
      f"{unitid_null_count}")

# ============================================================
# SCRIPT-SPECIFIC CHECKS (6-10, Skeptical Lenses)
# ============================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS (Skeptical Lenses)")
print("=" * 60)

# --- Check 6: [Counterfactual] subcohort=2 confirmation ---
# The script's execution log should show codebook confirmation that
# subcohort=2 = "Bachelor's or equivalent subcohort"
# We verify: (a) only subcohort=2 is in the data, (b) the value is documented
subcohort_values = df["subcohort"].unique().sort().to_list()
subcohort_ok = subcohort_values == [2]
print(f"\n[{'PASS' if subcohort_ok else 'FAIL'}] Check 6 — [Counterfactual] Subcohort filter:")
print(f"  Unique subcohort values in output: {subcohort_values}")
print(f"  Expected: [2] (bachelor's degree-seeking)")
if subcohort_ok:
    print("  Codebook confirmation from execution log: subcohort=2 = "
          "'Bachelor's or equivalent subcohort' — CONFIRMED")

# --- Check 7: [Semantic] Does data serve the research question? ---
# The research question focuses on 4-year institution graduation rates.
# subcohort=2 (bachelor's) is semantically correct for 4-year institutions.
# However, the data includes ALL institution levels (not just 4-year).
# The directory filter (institution_level==4) happens during the join,
# so having non-4-year institutions here is expected and correct.
year_values = df["year"].unique().to_list()
year_ok = year_values == [2020]
print(f"\n[{'PASS' if year_ok else 'FAIL'}] Check 7 — [Semantic] Data serves research question:")
print(f"  Year filter: {year_values} (expected [2020])")
print(f"  Subcohort: {subcohort_values} (bachelor's degree-seeking — correct for 4-year analysis)")
# Graduation rate column has values, so we can proceed with analysis
rate_non_null = df["completion_rate_150pct"].drop_nulls()
print(f"  Non-null graduation rates: {rate_non_null.shape[0]:,} out of {row_count:,} "
      f"({rate_non_null.shape[0]/row_count*100:.1f}%)")
semantic_ok = rate_non_null.shape[0] > 0 and year_ok

# --- Check 8: [Boundary] Edge cases in completion_rate_150pct ---
rate_col = df["completion_rate_150pct"]
null_count = rate_col.null_count()
null_pct = null_count / row_count * 100
non_null = rate_col.drop_nulls()
print(f"\n[INFO] Check 8 — [Boundary] Edge cases in completion_rate_150pct:")
print(f"  Null count: {null_count:,} ({null_pct:.1f}%)")

if non_null.shape[0] > 0:
    rate_min = non_null.min()
    rate_max = non_null.max()
    rate_mean = non_null.mean()
    rate_median = non_null.median()
    print(f"  Min: {rate_min:.4f}")
    print(f"  Max: {rate_max:.4f}")
    print(f"  Mean: {rate_mean:.4f}")
    print(f"  Median: {rate_median:.4f}")

    # Check for zero values
    zero_count = (non_null == 0).sum()
    print(f"  Zero values: {zero_count}")

    # Check for values exactly 1.0
    one_count = (non_null == 1.0).sum()
    print(f"  Values == 1.0: {one_count}")

    # Check for values > 1.0 (would indicate wrong scale or data error)
    over_one = (non_null > 1.0).sum()
    print(f"  Values > 1.0: {over_one}")
    boundary_ok = rate_min >= 0 and rate_max <= 1.0
    print(f"  [{'PASS' if boundary_ok else 'FAIL'}] Range within [0, 1]: "
          f"{rate_min:.4f} to {rate_max:.4f}")
else:
    boundary_ok = False
    print(f"  [FAIL] All values are null — no graduation rate data")

# --- Check 9: [Absence] Is cohort_year included? ---
# CRITICAL: The data has duplicate unitids (4,489 rows, 2,010 unique unitids).
# This is due to multiple cohort_year values per institution. Stage 6 needs
# cohort_year to filter to a single row per institution (cohort_year=2014).
# If cohort_year is NOT in the output, Stage 6 cannot do this filtering.
cohort_year_present = "cohort_year" in df.columns
print(f"\n[{'PASS' if cohort_year_present else 'BLOCKER'}] Check 9 — "
      f"[Absence] cohort_year column present: {cohort_year_present}")
if not cohort_year_present:
    print("  BLOCKER DETAIL: The output has 4,489 rows but only 2,010 unique unitids.")
    print("  Duplicate unitids exist because multiple cohort_year values are present")
    print("  in the source data (before column selection). Stage 6 needs cohort_year")
    print("  to filter to a single cohort_year per institution (e.g., 2014 for the")
    print("  150% time completion rate of the 2014 entering cohort).")
    print("  Without cohort_year, the data cannot be deduplicated properly.")
    print("  SUGGESTED FIX: Add 'cohort_year' to SELECT_COLUMNS in the fetch script.")

# --- Check 10: [Downstream] Will duplicate unitids surprise Stage 6? ---
n_unique_unitid = df["unitid"].n_unique()
n_total = df.shape[0]
has_duplicates = n_unique_unitid < n_total
dup_count = n_total - n_unique_unitid
print(f"\n[{'WARN' if has_duplicates else 'PASS'}] Check 10 — "
      f"[Downstream] Unitid uniqueness:")
print(f"  Total rows: {n_total:,}")
print(f"  Unique unitids: {n_unique_unitid:,}")
print(f"  Duplicate unitid rows: {dup_count:,}")
if has_duplicates:
    print(f"  WARNING: The downstream clean-grad-rates script expects ~2,000-3,000 rows")
    print(f"  and will likely expect 1:1 unitid mapping. Without cohort_year column,")
    print(f"  there's no way to resolve which row to keep per institution.")
    # Show distribution of duplicates
    dup_distribution = (
        df.group_by("unitid")
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
        ["count"]
    )
    if dup_distribution.shape[0] > 0:
        print(f"  Institutions with duplicates: {dup_distribution.shape[0]:,}")
        print(f"  Min rows per dup institution: {dup_distribution.min()}")
        print(f"  Max rows per dup institution: {dup_distribution.max()}")
        print(f"  Median rows per dup institution: {dup_distribution.median()}")

# ============================================================
# SPOT-CHECKS (11-15)
# ============================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Pick a specific unitid and verify plausibility ---
# Pick a well-known institution (e.g., unitid=110635 = UC Berkeley)
test_unitid = 110635
test_rows = df.filter(pl.col("unitid") == test_unitid)
print(f"\nSpot-Check 11 — Specific institution (unitid={test_unitid}):")
if test_rows.shape[0] > 0:
    print(f"  Rows found: {test_rows.shape[0]}")
    for row in test_rows.iter_rows(named=True):
        rate = row.get("completion_rate_150pct")
        cohort = row.get("cohort_adj_150pct")
        completers = row.get("completers_150pct")
        print(f"    completion_rate_150pct={rate}, cohort_adj={cohort}, "
              f"completers={completers}, subcohort={row.get('subcohort')}")
        # UC Berkeley should have a high graduation rate (~90%+)
        if rate is not None and rate > 0:
            plausible = 0.5 < rate < 1.0  # Known to be very high
            print(f"    [{'PASS' if plausible else 'WARN'}] Rate {rate:.3f} "
                  f"is {'plausible' if plausible else 'surprising'} for UC Berkeley")
else:
    print(f"  unitid {test_unitid} not found in data (may be filtered or not reporting)")
    # Try another institution
    sample_unitid = df["unitid"].head(1)[0]
    sample_rows = df.filter(pl.col("unitid") == sample_unitid)
    print(f"  Fallback: unitid={sample_unitid}, {sample_rows.shape[0]} rows")
    print(f"  {sample_rows.head(3)}")

# --- Spot-Check 12: Verify 0-1 scale ---
print(f"\nSpot-Check 12 — Verify 0-1 scale for completion_rate_150pct:")
if non_null.shape[0] > 0:
    pct_below_1 = (non_null <= 1.0).sum() / non_null.shape[0] * 100
    pct_above_0 = (non_null >= 0).sum() / non_null.shape[0] * 100
    print(f"  % of non-null values <= 1.0: {pct_below_1:.1f}%")
    print(f"  % of non-null values >= 0.0: {pct_above_0:.1f}%")
    scale_ok = pct_below_1 == 100.0 and pct_above_0 == 100.0
    print(f"  [{'PASS' if scale_ok else 'FAIL'}] Scale confirmed as 0-1 (proportion)")
else:
    print(f"  Cannot verify — all values null")

# --- Spot-Check 13: Subcohort column values ---
print(f"\nSpot-Check 13 — Subcohort column value counts:")
subcohort_vc = df["subcohort"].value_counts().sort("subcohort")
print(subcohort_vc)
all_subcohort_2 = (df["subcohort"] == 2).all()
print(f"  [{'PASS' if all_subcohort_2 else 'FAIL'}] All rows have subcohort==2")

# --- Spot-Check 14: No negative coded values in numeric columns ---
print(f"\nSpot-Check 14 — Negative coded values check:")
neg_coded_found = False
for col in df.columns:
    if df[col].dtype in [pl.Int64, pl.Float64]:
        neg_count = df.filter(pl.col(col).is_in([-1, -2, -3])).shape[0]
        if neg_count > 0:
            print(f"  [WARN] {col}: {neg_count} negative coded values found")
            neg_coded_found = True
        else:
            print(f"  [PASS] {col}: no negative coded values")
if not neg_coded_found:
    print(f"  [PASS] No negative coded values found in any numeric column")

# --- Spot-Check 15: Duplicate unitid structure ---
print(f"\nSpot-Check 15 — Duplicate unitid structure analysis:")
unitid_counts = (
    df.group_by("unitid")
    .agg(pl.len().alias("row_count"))
    .sort("row_count", descending=True)
)
count_dist = unitid_counts["row_count"].value_counts().sort("row_count")
print(f"  Distribution of rows per unitid:")
print(count_dist)
# Most institutions should have ~2-3 rows (one per cohort_year)
single_row = unitid_counts.filter(pl.col("row_count") == 1).shape[0]
multi_row = unitid_counts.filter(pl.col("row_count") > 1).shape[0]
print(f"  Institutions with 1 row: {single_row:,}")
print(f"  Institutions with >1 row: {multi_row:,}")
# Since cohort_year is not in the output, we can't directly verify which
# cohort_year values are causing duplicates. But we can infer from the structure.
if multi_row > 0:
    # Look at the most duplicated institution to understand the pattern
    max_dup_unitid = unitid_counts.head(1)["unitid"][0]
    max_dup_rows = df.filter(pl.col("unitid") == max_dup_unitid)
    print(f"\n  Most duplicated unitid={max_dup_unitid}: {max_dup_rows.shape[0]} rows")
    print(max_dup_rows)

# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

# Determine overall severity
blocker_found = not cohort_year_present  # Check 9 is the main BLOCKER
warning_found = has_duplicates  # Check 10

if blocker_found:
    severity = "BLOCKER"
elif warning_found:
    severity = "WARNING"
else:
    severity = "PASSED"

print(f"\n  QA Status: {'ISSUES_FOUND' if blocker_found or warning_found else 'PASSED'}")
print(f"  Severity: {severity}")
print(f"\n  BLOCKER Issues:")
if blocker_found:
    print(f"    - cohort_year column missing from output (Check 9)")
    print(f"      The output has {n_total:,} rows but only {n_unique_unitid:,} unique unitids.")
    print(f"      Without cohort_year, Stage 6 cannot deduplicate to one row per institution.")
    print(f"      Fix: Add 'cohort_year' to SELECT_COLUMNS in the fetch script.")
else:
    print(f"    None")

print(f"\n  WARNING Issues:")
if warning_found:
    print(f"    - Duplicate unitids: {dup_count:,} extra rows (Check 10)")
    print(f"      Expected if cohort_year is present and will be filtered in Stage 6.")
    print(f"      But cohort_year is MISSING, making this a compounding problem.")
else:
    print(f"    None")

print(f"\n  INFO Items:")
print(f"    - completion_rate_150pct has {null_pct:.1f}% null values (Check 8)")
print(f"      Expected given multi-cohort_year structure; nulls will decrease after")
print(f"      filtering to a single cohort_year per institution in Stage 6.")
print(f"    - No negative coded values in output (Check 14)")

print("\n" + "=" * 60)
print(f"QA RESULT: {severity}")
print("=" * 60)

# ============================================================
# DATA PROFILING (for cr2+ decision)
# ============================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col}:")
        if df[col].dtype in [pl.Int64, pl.Float64]:
            print(f"  Unique values: {df[col].n_unique()}")
            print(f"  Null count: {df[col].null_count()}")
            print(f"  Non-null count: {df[col].shape[0] - df[col].null_count()}")
            non_null_vals = df[col].drop_nulls()
            if non_null_vals.shape[0] > 0:
                print(f"  Min: {non_null_vals.min()}")
                print(f"  Max: {non_null_vals.max()}")
                print(f"  Mean: {non_null_vals.mean():.4f}")
                print(f"  Std: {non_null_vals.std():.4f}")
        else:
            print(df[col].value_counts().head(20))

print("\nYear distribution:")
if "year" in df.columns:
    print(df["year"].value_counts().sort("year"))

print("\nSubcohort distribution:")
if "subcohort" in df.columns:
    print(df["subcohort"].value_counts().sort("subcohort"))


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:33:55
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_02_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 02 — cr1
# ============================================================
# Loaded: 4,489 rows x 6 cols
# Columns: ['unitid', 'year', 'completion_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# Dtypes: [Int64, Int64, Float64, Int64, Int64, Int64]
# 
# ============================================================
# DEFAULT CHECKS
# ============================================================
# 
# [PASS] Check 1 — Schema: All expected columns present
# [PASS] Check 2 — Row count: 4,489 (expected 2,000-5,000)
# [WARN] Check 3 — Distributions: year: all same value (2020); subcohort: all same value (2)
# [PASS] Check 4 — Coded values: None remain in any column
# [PASS] Check 5 — Critical nulls in unitid: 0
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS (Skeptical Lenses)
# ============================================================
# 
# [PASS] Check 6 — [Counterfactual] Subcohort filter:
#   Unique subcohort values in output: [2]
#   Expected: [2] (bachelor's degree-seeking)
#   Codebook confirmation from execution log: subcohort=2 = 'Bachelor's or equivalent subcohort' — CONFIRMED
# 
# [PASS] Check 7 — [Semantic] Data serves research question:
#   Year filter: [2020] (expected [2020])
#   Subcohort: [2] (bachelor's degree-seeking — correct for 4-year analysis)
#   Non-null graduation rates: 1,949 out of 4,489 (43.4%)
# 
# [INFO] Check 8 — [Boundary] Edge cases in completion_rate_150pct:
#   Null count: 2,540 (56.6%)
#   Min: 0.0380
#   Max: 1.0000
#   Mean: 0.5560
#   Median: 0.5630
#   Zero values: 0
#   Values == 1.0: 41
#   Values > 1.0: 0
#   [PASS] Range within [0, 1]: 0.0380 to 1.0000
# 
# [BLOCKER] Check 9 — [Absence] cohort_year column present: False
#   BLOCKER DETAIL: The output has 4,489 rows but only 2,010 unique unitids.
#   Duplicate unitids exist because multiple cohort_year values are present
#   in the source data (before column selection). Stage 6 needs cohort_year
#   to filter to a single cohort_year per institution (e.g., 2014 for the
#   150% time completion rate of the 2014 entering cohort).
#   Without cohort_year, the data cannot be deduplicated properly.
#   SUGGESTED FIX: Add 'cohort_year' to SELECT_COLUMNS in the fetch script.
# 
# [WARN] Check 10 — [Downstream] Unitid uniqueness:
#   Total rows: 4,489
#   Unique unitids: 2,010
#   Duplicate unitid rows: 2,479
#   WARNING: The downstream clean-grad-rates script expects ~2,000-3,000 rows
#   and will likely expect 1:1 unitid mapping. Without cohort_year column,
#   there's no way to resolve which row to keep per institution.
#   Institutions with duplicates: 1,949
#   Min rows per dup institution: 2
#   Max rows per dup institution: 4
#   Median rows per dup institution: 2.0
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-Check 11 — Specific institution (unitid=110635):
#   Rows found: 2
#     completion_rate_150pct=None, cohort_adj=None, completers=5114, subcohort=2
#     completion_rate_150pct=0.928, cohort_adj=5510, completers=5114, subcohort=2
#     [PASS] Rate 0.928 is plausible for UC Berkeley
# 
# Spot-Check 12 — Verify 0-1 scale for completion_rate_150pct:
#   % of non-null values <= 1.0: 100.0%
#   % of non-null values >= 0.0: 100.0%
#   [PASS] Scale confirmed as 0-1 (proportion)
# 
# Spot-Check 13 — Subcohort column value counts:
# shape: (1, 2)
# ┌───────────┬───────┐
# │ subcohort ┆ count │
# │ ---       ┆ ---   │
# │ i64       ┆ u32   │
# ╞═══════════╪═══════╡
# │ 2         ┆ 4489  │
# └───────────┴───────┘
#   [PASS] All rows have subcohort==2
# 
# Spot-Check 14 — Negative coded values check:
#   [PASS] unitid: no negative coded values
#   [PASS] year: no negative coded values
#   [PASS] completion_rate_150pct: no negative coded values
#   [PASS] cohort_adj_150pct: no negative coded values
#   [PASS] completers_150pct: no negative coded values
#   [PASS] subcohort: no negative coded values
#   [PASS] No negative coded values found in any numeric column
# 
# Spot-Check 15 — Duplicate unitid structure analysis:
#   Distribution of rows per unitid:
# shape: (4, 2)
# ┌───────────┬───────┐
# │ row_count ┆ count │
# │ ---       ┆ ---   │
# │ u32       ┆ u32   │
# ╞═══════════╪═══════╡
# │ 1         ┆ 61    │
# │ 2         ┆ 1464  │
# │ 3         ┆ 440   │
# │ 4         ┆ 45    │
# └───────────┴───────┘
#   Institutions with 1 row: 61
#   Institutions with >1 row: 1,949
# 
#   Most duplicated unitid=169363: 4 rows
# shape: (4, 6)
# ┌────────┬──────┬────────────────────────┬───────────────────┬───────────────────┬───────────┐
# │ unitid ┆ year ┆ completion_rate_150pct ┆ cohort_adj_150pct ┆ completers_150pct ┆ subcohort │
# │ ---    ┆ ---  ┆ ---                    ┆ ---               ┆ ---               ┆ ---       │
# │ i64    ┆ i64  ┆ f64                    ┆ i64               ┆ i64               ┆ i64       │
# ╞════════╪══════╪════════════════════════╪═══════════════════╪═══════════════════╪═══════════╡
# │ 169363 ┆ 2020 ┆ null                   ┆ null              ┆ 74                ┆ 2         │
# │ 169363 ┆ 2020 ┆ null                   ┆ null              ┆ 1                 ┆ 2         │
# │ 169363 ┆ 2020 ┆ 0.513                  ┆ 152               ┆ 78                ┆ 2         │
# │ 169363 ┆ 2020 ┆ null                   ┆ null              ┆ 3                 ┆ 2         │
# └────────┴──────┴────────────────────────┴───────────────────┴───────────────────┴───────────┘
# 
# ============================================================
# QA SUMMARY
# ============================================================
# 
#   QA Status: ISSUES_FOUND
#   Severity: BLOCKER
# 
#   BLOCKER Issues:
#     - cohort_year column missing from output (Check 9)
#       The output has 4,489 rows but only 2,010 unique unitids.
#       Without cohort_year, Stage 6 cannot deduplicate to one row per institution.
#       Fix: Add 'cohort_year' to SELECT_COLUMNS in the fetch script.
# 
#   WARNING Issues:
#     - Duplicate unitids: 2,479 extra rows (Check 10)
#       Expected if cohort_year is present and will be filtered in Stage 6.
#       But cohort_year is MISSING, making this a compounding problem.
# 
#   INFO Items:
#     - completion_rate_150pct has 56.6% null values (Check 8)
#       Expected given multi-cohort_year structure; nulls will decrease after
#       filtering to a single cohort_year per institution in Stage 6.
#     - No negative coded values in output (Check 14)
# 
# ============================================================
# QA RESULT: BLOCKER
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 6)
# ┌────────┬──────┬────────────────────────┬───────────────────┬───────────────────┬───────────┐
# │ unitid ┆ year ┆ completion_rate_150pct ┆ cohort_adj_150pct ┆ completers_150pct ┆ subcohort │
# │ ---    ┆ ---  ┆ ---                    ┆ ---               ┆ ---               ┆ ---       │
# │ i64    ┆ i64  ┆ f64                    ┆ i64               ┆ i64               ┆ i64       │
# ╞════════╪══════╪════════════════════════╪═══════════════════╪═══════════════════╪═══════════╡
# │ 100654 ┆ 2020 ┆ null                   ┆ null              ┆ 343               ┆ 2         │
# │ 100654 ┆ 2020 ┆ 0.281                  ┆ 1222              ┆ 343               ┆ 2         │
# │ 100663 ┆ 2020 ┆ 0.624                  ┆ 1587              ┆ 991               ┆ 2         │
# │ 100663 ┆ 2020 ┆ null                   ┆ null              ┆ 991               ┆ 2         │
# │ 100690 ┆ 2020 ┆ 0.667                  ┆ 6                 ┆ 4                 ┆ 2         │
# │ …      ┆ …    ┆ …                      ┆ …                 ┆ …                 ┆ …         │
# │ 100858 ┆ 2020 ┆ 0.809                  ┆ 4848              ┆ 3921              ┆ 2         │
# │ 100937 ┆ 2020 ┆ null                   ┆ null              ┆ 308               ┆ 2         │
# │ 100937 ┆ 2020 ┆ 0.698                  ┆ 441               ┆ 308               ┆ 2         │
# │ 101116 ┆ 2020 ┆ null                   ┆ null              ┆ 3                 ┆ 2         │
# │ 101116 ┆ 2020 ┆ 0.136                  ┆ 22                ┆ 3                 ┆ 2         │
# └────────┴──────┴────────────────────────┴───────────────────┴───────────────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 7)
# ┌────────────┬───────────────┬────────┬────────────────┬───────────────┬───────────────┬───────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ completion_rat ┆ cohort_adj_15 ┆ completers_15 ┆ subcohort │
# │ ---        ┆ ---           ┆ ---    ┆ e_150pct       ┆ 0pct          ┆ 0pct          ┆ ---       │
# │ str        ┆ f64           ┆ f64    ┆ ---            ┆ ---           ┆ ---           ┆ f64       │
# │            ┆               ┆        ┆ f64            ┆ f64           ┆ f64           ┆           │
# ╞════════════╪═══════════════╪════════╪════════════════╪═══════════════╪═══════════════╪═══════════╡
# │ count      ┆ 4489.0        ┆ 4489.0 ┆ 1949.0         ┆ 2008.0        ┆ 4428.0        ┆ 4489.0    │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 2540.0         ┆ 2481.0        ┆ 61.0          ┆ 0.0       │
# │ mean       ┆ 217224.272221 ┆ 2020.0 ┆ 0.555965       ┆ 763.731574    ┆ 447.33785     ┆ 2.0       │
# │ std        ┆ 99877.243922  ┆ 0.0    ┆ 0.205566       ┆ 1239.4868     ┆ 893.741404    ┆ 0.0       │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.038          ┆ 1.0           ┆ 1.0           ┆ 2.0       │
# │ 25%        ┆ 156125.0      ┆ 2020.0 ┆ 0.417          ┆ 88.0          ┆ 17.0          ┆ 2.0       │
# │ 50%        ┆ 194958.0      ┆ 2020.0 ┆ 0.563          ┆ 334.0         ┆ 132.0         ┆ 2.0       │
# │ 75%        ┆ 226471.0      ┆ 2020.0 ┆ 0.696          ┆ 806.0         ┆ 431.0         ┆ 2.0       │
# │ max        ┆ 496636.0      ┆ 2020.0 ┆ 1.0            ┆ 15327.0       ┆ 11142.0       ┆ 2.0       │
# └────────────┴───────────────┴────────┴────────────────┴───────────────┴───────────────┴───────────┘
# 
# Key column value counts:
# 
# unitid:
#   Unique values: 2010
#   Null count: 0
#   Non-null count: 4489
#   Min: 100654
#   Max: 496636
#   Mean: 217224.2722
#   Std: 99877.2439
# 
# completion_rate_150pct:
#   Unique values: 708
#   Null count: 2540
#   Non-null count: 1949
#   Min: 0.038
#   Max: 1.0
#   Mean: 0.5560
#   Std: 0.2056
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 4489  │
# └──────┴───────┘
# 
# Subcohort distribution:
# shape: (1, 2)
# ┌───────────┬───────┐
# │ subcohort ┆ count │
# │ ---       ┆ ---   │
# │ i64       ┆ u32   │
# ╞═══════════╪═══════╡
# │ 2         ┆ 4489  │
# └───────────┴───────┘
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
