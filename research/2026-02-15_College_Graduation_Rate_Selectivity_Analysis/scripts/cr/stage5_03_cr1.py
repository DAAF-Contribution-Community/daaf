#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 03 (cr1)

Reviewed script: scripts/stage5_fetch/03_fetch-admissions.py
Output files: data/raw/2026-02-15_ipeds_admissions.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (5 Default):
  1. Schema matches Plan expectations (Query 3 columns)
  2. Row count within expected range (1,500-3,000)
  3. No suspicious distributions (constant columns, all-zeros)
  4. Coded values properly filtered (-1, -2, -3)
  5. No nulls in critical identifier column (unitid)

Script-Specific Checks (5 Skeptical Lenses):
  6. COUNTERFACTUAL: What if sex filter didn't work? Check no sex column remains
     and verify row count doesn't suggest unfiltered multi-sex data.
  7. SEMANTIC: Does the data actually serve the research question? Can we compute
     admission_rate = number_admitted / number_applied for most institutions?
  8. BOUNDARY: Check edge cases -- zeros in number_applied, nulls in number_admitted,
     extreme outlier institutions.
  9. ABSENCE: Verify year column is ONLY 2020 (no multi-year contamination) and
     that no extra filter columns (fips, sex) were accidentally retained.
 10. DOWNSTREAM: What will Stage 6 (clean-admissions) need? Verify that null
     pattern in number_admitted is consistent with open-admission school expectation.

Spot Checks (5 Concrete):
 11. Trace a known large university (e.g., unitid 110635 = UC Berkeley or similar)
     and verify its application count is plausible.
 12. Verify that number_admitted is never > number_applied for any row.
 13. Verify that number_enrolled_total <= number_admitted for valid rows.
 14. Check the 23 institutions with null number_admitted -- are they plausibly
     open-admission schools? (cross-check count against Plan expectation)
 15. Verify no duplicate unitids exist (1:1 row per institution).
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_admissions.parquet"

# Plan Query 3 expected columns
EXPECTED_COLUMNS = [
    "unitid",
    "year",
    "number_applied",
    "number_admitted",
    "number_enrolled_total",
]

EXPECTED_MIN_ROWS = 1_500
EXPECTED_MAX_ROWS = 3_000
CRITICAL_COLUMNS = ["unitid", "number_applied"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 03 — fetch-admissions (cr1)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {dict(zip(df.columns, [str(d) for d in df.dtypes]))}")

# =============================================================================
# DEFAULT CHECKS (5)
# =============================================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 - Schema: ", end="")
if schema_ok:
    print(f"All {len(EXPECTED_COLUMNS)} expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Check 2 - Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

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
print(f"[{'PASS' if dist_ok else 'FAIL'}] Check 3 - Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values (-1, -2, -3) ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Check 4 - Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls (unitid) ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Check 5 - Critical nulls: ", end="")
print("None in unitid/number_applied" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (5 Skeptical Lenses)
# =============================================================================

# --- Check 6: COUNTERFACTUAL — sex filter verification ---
# If the sex filter didn't apply, we'd expect ~3x more rows (one for each
# sex value: male, female, total). The raw fetch was 196,186 rows across all
# years, so ~196186/20 years * 3 sex values would mean ~3,273 per year-sex.
# Getting 1,989 for a single year+sex is consistent with proper filtering.
sex_in_data = "sex" in df.columns
print(f"\n[{'PASS' if not sex_in_data else 'WARN'}] Check 6 - COUNTERFACTUAL (sex filter): ", end="")
if not sex_in_data:
    print("'sex' column correctly excluded from output (filter applied pre-column-selection)")
else:
    sex_vals = df["sex"].unique().to_list()
    print(f"'sex' column present with values: {sex_vals}")

# Additional: check if row count suggests unfiltered data
# Without sex filter, we'd expect ~3x more rows
if row_count > 5_000:
    print(f"  [WARN] Row count {row_count:,} is suspiciously high — may include multiple sex values")

# --- Check 7: SEMANTIC — can we compute admission_rate? ---
# The research question needs admission_rate = number_admitted / number_applied.
# This check verifies both columns are present and computable for most rows.
both_present = (
    df.filter(
        pl.col("number_applied").is_not_null()
        & pl.col("number_admitted").is_not_null()
        & (pl.col("number_applied") > 0)
    ).shape[0]
)
compute_pct = both_present / row_count * 100 if row_count > 0 else 0
semantic_ok = compute_pct > 90
print(f"[{'PASS' if semantic_ok else 'WARN'}] Check 7 - SEMANTIC (admission_rate computable): {both_present:,}/{row_count:,} rows ({compute_pct:.1f}%)")

# Compute actual admission rates for the computable rows
computable = df.filter(
    pl.col("number_applied").is_not_null()
    & pl.col("number_admitted").is_not_null()
    & (pl.col("number_applied") > 0)
).with_columns(
    (pl.col("number_admitted") / pl.col("number_applied")).alias("admission_rate")
)
print(f"  Admission rate range: min={computable['admission_rate'].min():.4f}, "
      f"median={computable['admission_rate'].median():.4f}, "
      f"max={computable['admission_rate'].max():.4f}")
# Admission rates should typically be 0.0 to 1.0 (or slightly above 1.0 in rare cases)
rate_over_1 = computable.filter(pl.col("admission_rate") > 1.0).shape[0]
if rate_over_1 > 0:
    print(f"  [WARN] {rate_over_1} institutions have admission_rate > 1.0 (admitted > applied)")
else:
    print(f"  [PASS] All admission rates <= 1.0")

# --- Check 8: BOUNDARY — edge cases ---
# Check for zeros in number_applied (can't compute admission rate)
applied_zero = df.filter(
    pl.col("number_applied").is_not_null() & (pl.col("number_applied") == 0)
).shape[0]
print(f"\n[{'PASS' if applied_zero < 50 else 'WARN'}] Check 8a - BOUNDARY (number_applied == 0): {applied_zero} institutions")
if applied_zero > 0:
    print(f"  These institutions have 0 applications — likely open-admission or reporting anomaly")

# Check for extreme outliers in number_applied
applied_stats = df["number_applied"].drop_nulls()
if len(applied_stats) > 0:
    p99 = applied_stats.quantile(0.99)
    p01 = applied_stats.quantile(0.01)
    print(f"  number_applied: p01={p01:,.0f}, p99={p99:,.0f}")
    # Verify max isn't implausible
    max_applied = applied_stats.max()
    print(f"  Max applications: {max_applied:,} — ", end="")
    if max_applied > 200_000:
        print("Suspiciously high, verify against known data")
    elif max_applied > 50_000:
        print("Plausible for large state universities (e.g., UCLA ~109K)")
    else:
        print("Within expected range")

# Check for nulls in number_admitted (expected for open-admission schools)
admitted_nulls = df["number_admitted"].null_count()
print(f"  number_admitted nulls: {admitted_nulls} (expected ~23 per script log)")
enrolled_nulls = df["number_enrolled_total"].null_count()
print(f"  number_enrolled_total nulls: {enrolled_nulls}")

# --- Check 9: ABSENCE — verify no multi-year contamination ---
years_present = df["year"].unique().to_list()
year_clean = len(years_present) == 1 and years_present[0] == 2020
print(f"\n[{'PASS' if year_clean else 'FAIL'}] Check 9a - ABSENCE (year filter): years present = {sorted(years_present)}")

# Verify no extra columns leaked through that shouldn't be there
expected_absent = ["sex", "fips", "number_enrolled_ft", "number_enrolled_pt"]
leaked_cols = [c for c in expected_absent if c in df.columns]
leak_ok = len(leaked_cols) == 0
print(f"[{'PASS' if leak_ok else 'WARN'}] Check 9b - ABSENCE (no leaked columns): ", end="")
if leak_ok:
    print(f"None of {expected_absent} present in output")
else:
    print(f"Leaked columns: {leaked_cols}")

# --- Check 10: DOWNSTREAM — null pattern for Stage 6 ---
# Stage 6 will compute admission_rate = number_admitted / number_applied.
# Open-admission schools with null number_admitted should be assigned to
# "Less Selective/Open" band in Stage 7. Verify the count is reasonable.
admitted_null_count = df.filter(pl.col("number_admitted").is_null()).shape[0]
downstream_ok = admitted_null_count < 100  # should be small, expected ~23
print(f"\n[{'PASS' if downstream_ok else 'WARN'}] Check 10 - DOWNSTREAM (null number_admitted for Stage 6): {admitted_null_count} institutions")
print(f"  These will be assigned to 'Less Selective/Open' band in Stage 7")

# Verify that institutions with null admitted also have 0 or null applied (expected pattern)
null_admitted_with_nonzero_applied = df.filter(
    pl.col("number_admitted").is_null()
    & pl.col("number_applied").is_not_null()
    & (pl.col("number_applied") > 0)
).shape[0]
print(f"  Of those, {null_admitted_with_nonzero_applied} have non-zero applications")
print(f"  (These are institutions that received applications but don't report admits — likely open-admission)")

# =============================================================================
# SPOT CHECKS (5 Concrete)
# =============================================================================
print("\n" + "=" * 60)
print("SPOT CHECKS")
print("=" * 60)

# --- Spot Check 11: Trace a known large university ---
# Look for well-known institutions to verify plausible values
known_ids = {
    110635: "University of California-Berkeley",
    166027: "Harvard University",
    243744: "University of Wisconsin-Madison",
    228778: "University of Texas at Austin",
    186131: "Princeton University",
}
print("\nSpot Check 11 - Known institution lookup:")
for uid, name in known_ids.items():
    match = df.filter(pl.col("unitid") == uid)
    if match.shape[0] > 0:
        row = match.row(0, named=True)
        applied = row.get("number_applied", "N/A")
        admitted = row.get("number_admitted", "N/A")
        enrolled = row.get("number_enrolled_total", "N/A")
        print(f"  {name} ({uid}): applied={applied:,}, admitted={admitted:,}, enrolled={enrolled:,}")
    else:
        print(f"  {name} ({uid}): NOT FOUND in dataset")

# --- Spot Check 12: admitted <= applied for ALL rows ---
valid_rows = df.filter(
    pl.col("number_applied").is_not_null()
    & pl.col("number_admitted").is_not_null()
    & (pl.col("number_applied") > 0)
    & (pl.col("number_admitted") > 0)
)
violations = valid_rows.filter(
    pl.col("number_admitted") > pl.col("number_applied")
)
print(f"\nSpot Check 12 - admitted <= applied: {violations.shape[0]} violations out of {valid_rows.shape[0]:,} valid rows")
if violations.shape[0] > 0:
    print(f"  Violations:")
    print(violations.head(5))

# --- Spot Check 13: enrolled <= admitted for valid rows ---
# This should generally hold but might have exceptions if enrollment includes
# other cohorts. Still a useful sanity check.
enrolled_check = valid_rows.filter(
    pl.col("number_enrolled_total").is_not_null()
    & (pl.col("number_enrolled_total") > 0)
)
yield_violations = enrolled_check.filter(
    pl.col("number_enrolled_total") > pl.col("number_admitted")
)
print(f"\nSpot Check 13 - enrolled <= admitted: {yield_violations.shape[0]} exceptions out of {enrolled_check.shape[0]:,} valid rows")
if yield_violations.shape[0] > 0 and yield_violations.shape[0] <= 10:
    print(f"  Exceptions (may include transfer students or special programs):")
    print(yield_violations.select(["unitid", "number_applied", "number_admitted", "number_enrolled_total"]))
elif yield_violations.shape[0] > 10:
    print(f"  First 5 exceptions:")
    print(yield_violations.select(["unitid", "number_applied", "number_admitted", "number_enrolled_total"]).head(5))

# --- Spot Check 14: Null number_admitted institutions ---
null_admitted = df.filter(pl.col("number_admitted").is_null())
print(f"\nSpot Check 14 - Institutions with null number_admitted: {null_admitted.shape[0]}")
# Check if they have 0 applied or null applied
null_admitted_applied_zero = null_admitted.filter(
    pl.col("number_applied").is_not_null() & (pl.col("number_applied") == 0)
).shape[0]
null_admitted_applied_null = null_admitted.filter(
    pl.col("number_applied").is_null()
).shape[0]
null_admitted_applied_positive = null_admitted.filter(
    pl.col("number_applied").is_not_null() & (pl.col("number_applied") > 0)
).shape[0]
print(f"  With applied=0: {null_admitted_applied_zero}")
print(f"  With applied=null: {null_admitted_applied_null}")
print(f"  With applied>0: {null_admitted_applied_positive}")
if null_admitted_applied_positive > 0:
    print(f"  Sample institutions with applications but null admits:")
    sample = null_admitted.filter(
        pl.col("number_applied").is_not_null() & (pl.col("number_applied") > 0)
    ).select(["unitid", "number_applied", "number_admitted", "number_enrolled_total"]).head(5)
    print(sample)

# --- Spot Check 15: Duplicate unitids ---
dup_check = df.group_by("unitid").len().filter(pl.col("len") > 1)
dup_ok = dup_check.shape[0] == 0
print(f"\nSpot Check 15 - Duplicate unitids: {'None' if dup_ok else f'{dup_check.shape[0]} duplicates found'}")
if not dup_ok:
    print(f"  Duplicates:")
    print(dup_check.head(10))

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["unitid"]:
    if col in df.columns:
        print(f"\n{col} — unique count: {df[col].n_unique()}")
        print(f"  min: {df[col].min()}, max: {df[col].max()}")

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

# Null counts across all columns
print("\nNull counts per column:")
for col in df.columns:
    nc = df[col].null_count()
    pct = nc / len(df) * 100 if len(df) > 0 else 0
    print(f"  {col}: {nc} ({pct:.1f}%)")

# Distribution of number_applied (quantiles)
print("\nnumber_applied quantiles:")
for q in [0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 1.0]:
    val = df["number_applied"].drop_nulls().quantile(q)
    print(f"  p{int(q*100):02d}: {val:,.0f}")

# Distribution of number_admitted (quantiles, excluding nulls)
print("\nnumber_admitted quantiles (excluding nulls):")
for q in [0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 1.0]:
    val = df["number_admitted"].drop_nulls().quantile(q)
    print(f"  p{int(q*100):02d}: {val:,.0f}")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_lens_passed = all([not sex_in_data, semantic_ok, year_clean, leak_ok, downstream_ok])
all_spot_passed = all([dup_ok, violations.shape[0] == 0])

overall_passed = all_default_passed and all_lens_passed and all_spot_passed

print(f"Default checks: {'ALL PASSED' if all_default_passed else 'ISSUES FOUND'}")
print(f"Skeptical lens checks: {'ALL PASSED' if all_lens_passed else 'ISSUES FOUND'}")
print(f"Spot checks: {'ALL PASSED' if all_spot_passed else 'ISSUES FOUND'}")

severity = "PASSED" if overall_passed else "BLOCKER"
print(f"\nQA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:33:11
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 03 — fetch-admissions (cr1)
# ============================================================
# Loaded: 1,989 rows x 5 cols
# Columns: ['unitid', 'year', 'number_applied', 'number_admitted', 'number_enrolled_total']
# Dtypes: {'unitid': 'Int64', 'year': 'Int64', 'number_applied': 'Int64', 'number_admitted': 'Int64', 'number_enrolled_total': 'Int64'}
# 
# [PASS] Check 1 - Schema: All 5 expected columns present
# [PASS] Check 2 - Row count: 1,989 (expected 1,500-3,000)
# [FAIL] Check 3 - Distributions: year: all same value (2020)
# [PASS] Check 4 - Coded values: None remain
# [PASS] Check 5 - Critical nulls: None in unitid/number_applied
# 
# [PASS] Check 6 - COUNTERFACTUAL (sex filter): 'sex' column correctly excluded from output (filter applied pre-column-selection)
# [PASS] Check 7 - SEMANTIC (admission_rate computable): 1,966/1,989 rows (98.8%)
#   Admission rate range: min=0.0000, median=0.7522, max=1.0000
#   [PASS] All admission rates <= 1.0
# 
# [PASS] Check 8a - BOUNDARY (number_applied == 0): 23 institutions
#   These institutions have 0 applications — likely open-admission or reporting anomaly
#   number_applied: p01=0, p99=52,371
#   Max applications: 108,870 — Plausible for large state universities (e.g., UCLA ~109K)
#   number_admitted nulls: 23 (expected ~23 per script log)
#   number_enrolled_total nulls: 25
# 
# [PASS] Check 9a - ABSENCE (year filter): years present = [2020]
# [PASS] Check 9b - ABSENCE (no leaked columns): None of ['sex', 'fips', 'number_enrolled_ft', 'number_enrolled_pt'] present in output
# 
# [PASS] Check 10 - DOWNSTREAM (null number_admitted for Stage 6): 23 institutions
#   These will be assigned to 'Less Selective/Open' band in Stage 7
#   Of those, 0 have non-zero applications
#   (These are institutions that received applications but don't report admits — likely open-admission)
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# Spot Check 11 - Known institution lookup:
#   University of California-Berkeley (110635): applied=88,062, admitted=15,390, enrolled=6,117
#   Harvard University (166027): applied=40,248, admitted=2,015, enrolled=1,407
#   University of Wisconsin-Madison (243744): applied=45,227, admitted=2,349, enrolled=1,606
#   University of Texas at Austin (228778): applied=57,241, admitted=18,290, enrolled=8,459
#   Princeton University (186131): applied=32,835, admitted=1,848, enrolled=1,154
# 
# Spot Check 12 - admitted <= applied: 0 violations out of 1,964 valid rows
# 
# Spot Check 13 - enrolled <= admitted: 0 exceptions out of 1,953 valid rows
# 
# Spot Check 14 - Institutions with null number_admitted: 23
#   With applied=0: 23
#   With applied=null: 0
#   With applied>0: 0
# 
# Spot Check 15 - Duplicate unitids: None
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 5)
# ┌────────┬──────┬────────────────┬─────────────────┬───────────────────────┐
# │ unitid ┆ year ┆ number_applied ┆ number_admitted ┆ number_enrolled_total │
# │ ---    ┆ ---  ┆ ---            ┆ ---             ┆ ---                   │
# │ i64    ┆ i64  ┆ i64            ┆ i64             ┆ i64                   │
# ╞════════╪══════╪════════════════╪═════════════════╪═══════════════════════╡
# │ 100654 ┆ 2020 ┆ 9855           ┆ 8835            ┆ 1664                  │
# │ 100663 ┆ 2020 ┆ 10391          ┆ 8375            ┆ 2154                  │
# │ 100706 ┆ 2020 ┆ 5793           ┆ 4467            ┆ 1345                  │
# │ 100724 ┆ 2020 ┆ 7027           ┆ 6948            ┆ 975                   │
# │ 100751 ┆ 2020 ┆ 39560          ┆ 31804           ┆ 6507                  │
# │ …      ┆ …    ┆ …              ┆ …               ┆ …                     │
# │ 101648 ┆ 2020 ┆ 1000           ┆ 575             ┆ 255                   │
# │ 101693 ┆ 2020 ┆ 2037           ┆ 1356            ┆ 250                   │
# │ 101709 ┆ 2020 ┆ 4954           ┆ 2998            ┆ 471                   │
# │ 101879 ┆ 2020 ┆ 2739           ┆ 2264            ┆ 924                   │
# │ 101912 ┆ 2020 ┆ 1135           ┆ 1008            ┆ 303                   │
# └────────┴──────┴────────────────┴─────────────────┴───────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 6)
# ┌────────────┬───────────────┬────────┬────────────────┬─────────────────┬───────────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ number_applied ┆ number_admitted ┆ number_enrolled_total │
# │ ---        ┆ ---           ┆ ---    ┆ ---            ┆ ---             ┆ ---                   │
# │ str        ┆ f64           ┆ f64    ┆ f64            ┆ f64             ┆ f64                   │
# ╞════════════╪═══════════════╪════════╪════════════════╪═════════════════╪═══════════════════════╡
# │ count      ┆ 1989.0        ┆ 1989.0 ┆ 1989.0         ┆ 1966.0          ┆ 1964.0                │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 0.0            ┆ 23.0            ┆ 25.0                  │
# │ mean       ┆ 224890.833585 ┆ 2020.0 ┆ 5825.701357    ┆ 3578.694303     ┆ 801.238798            │
# │ std        ┆ 106587.8359   ┆ 0.0    ┆ 10808.406814   ┆ 5891.773274     ┆ 1375.075243           │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.0            ┆ 0.0             ┆ 0.0                   │
# │ 25%        ┆ 157951.0      ┆ 2020.0 ┆ 272.0          ┆ 219.0           ┆ 95.0                  │
# │ 50%        ┆ 196176.0      ┆ 2020.0 ┆ 2016.0         ┆ 1440.0          ┆ 326.0                 │
# │ 75%        ┆ 230889.0      ┆ 2020.0 ┆ 6046.0         ┆ 4108.0          ┆ 788.0                 │
# │ max        ┆ 495916.0      ┆ 2020.0 ┆ 108870.0       ┆ 74604.0         ┆ 15614.0               │
# └────────────┴───────────────┴────────┴────────────────┴─────────────────┴───────────────────────┘
# 
# Key column value counts:
# 
# unitid — unique count: 1989
#   min: 100654, max: 495916
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 1989  │
# └──────┴───────┘
# 
# Null counts per column:
#   unitid: 0 (0.0%)
#   year: 0 (0.0%)
#   number_applied: 0 (0.0%)
#   number_admitted: 23 (1.2%)
#   number_enrolled_total: 25 (1.3%)
# 
# number_applied quantiles:
#   p00: 0
#   p05: 8
#   p10: 22
#   p25: 272
#   p50: 2,016
#   p75: 6,046
#   p90: 15,324
#   p95: 26,127
#   p100: 108,870
# 
# number_admitted quantiles (excluding nulls):
#   p00: 0
#   p05: 7
#   p10: 18
#   p25: 219
#   p50: 1,440
#   p75: 4,108
#   p90: 9,767
#   p95: 15,602
#   p100: 74,604
# 
# ============================================================
# QA SUMMARY
# ============================================================
# Default checks: ISSUES FOUND
# Skeptical lens checks: ALL PASSED
# Spot checks: ALL PASSED
# 
# QA RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
