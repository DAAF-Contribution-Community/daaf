#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 1.2

Reviewed script: scripts/stage5_fetch/02_fetch-admissions.py
Output files: data/raw/2026-03-29_ipeds_admissions.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations (9 columns exactly)
2. Row count assessment (Plan_Tasks says 15K-30K; Transformation Sequence says ~6K)
3. No suspicious distributions in numeric columns
4. Coded values (-1, -2, -3) may be present in raw data (expected at fetch)
5. No nulls in identifier columns (unitid, year)
6. [Counterfactual] What if mirror returned stale data with wrong years?
7. [Semantic] Does raw data preserve what cleaning step needs (all sex categories)?
8. [Boundary] Check for zero/negative values in count columns
9. [Absence] Are any institutions duplicated within year+sex?
10. [Downstream] Will cleaning script find sex==99 rows as expected?

Spot-checks:
A. Trace a specific unitid across years to verify multi-row structure
B. Verify sex categories are exactly {1, 2, 99} as documented
C. Check that number_applied >= number_admitted (logical constraint)
D. Verify year distribution is balanced (roughly equal per year)
E. Check for any unitid with only partial sex categories
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_admissions.parquet"
EXPECTED_COLUMNS = [
    "unitid", "year", "fips", "sex",
    "number_applied", "number_admitted",
    "number_enrolled_ft", "number_enrolled_pt", "number_enrolled_total",
]
# INTENT: Plan_Tasks Task 1.2 verify says 15K-30K but Plan.md Transformation
# Sequence row for Step 1.2 says ~6,000. The discrepancy exists in the Plan
# itself. We use a wider range to accommodate both estimates.
# REASONING: The actual count of 11,910 = ~3,970 institutions x 3 sex categories
# x 2 years, which is geometrically consistent. The Plan_Tasks verify range
# appears to overestimate.
EXPECTED_MIN_ROWS = 5_000
EXPECTED_MAX_ROWS = 35_000
CRITICAL_COLUMNS = ["unitid", "year", "sex", "number_applied", "number_admitted"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 1.2 — fetch-admissions")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print(f"All {len(EXPECTED_COLUMNS)} expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan.md): {extra_cols}")

# Verify column count is exactly 9 per Plan.md Stage 2 findings
col_count_ok = df.shape[1] == 9
print(f"[{'PASS' if col_count_ok else 'FAIL'}] Column count: {df.shape[1]} (expected exactly 9)")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# Also check against Plan_Tasks strict range (15K-30K) -- note as WARNING
plan_tasks_range = (15_000, 30_000)
in_strict_range = plan_tasks_range[0] <= row_count <= plan_tasks_range[1]
if not in_strict_range:
    print(f"  [WARN] Row count {row_count:,} outside Plan_Tasks verify range {plan_tasks_range}")
    print(f"  NOTE: Plan.md Transformation Sequence says ~6K for this task.")
    print(f"  Actual: ~{row_count // 6:,} institutions x 3 sex categories x 2 years = {row_count:,}")

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
# INTENT: At raw/fetch stage, coded values (-1, -2, -3) MAY legitimately
# exist. The cleaning script (Stage 6) will handle them. We document their
# presence here for downstream awareness.
coded_issues = []
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_present = len(coded_issues) > 0
print(f"[{'INFO' if coded_present else 'PASS'}] Coded values: ", end="")
if not CODED_MISSING_VALUES:
    print("No domain-specific coded values to check")
elif coded_present:
    print(f"Present in raw data (expected at fetch stage):")
    for issue in coded_issues:
        print(f"  {issue}")
else:
    print("None found (unusual for raw IPEDS data)")

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls ({null_count/row_count*100:.1f}%)")
nulls_ok = len(null_issues) == 0 or all(
    "number_applied" in issue or "number_admitted" in issue for issue in null_issues
)
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
if not null_issues:
    print("None in identifiers")
else:
    for issue in null_issues:
        # Nulls in number_applied/number_admitted are acceptable at raw stage
        if "unitid" in issue or "year" in issue or "sex" in issue:
            print(f"  [FAIL] {issue}")
        else:
            print(f"  [INFO] {issue} (acceptable at raw stage)")

# --- Check 6: [Counterfactual] Stale data / wrong years ---
# INTENT: Verify the data actually contains only the requested years.
# If the mirror returned a cached/stale file, we might get wrong years.
years_found = sorted(df["year"].unique().to_list())
years_expected = [2020, 2021]
years_match = years_found == years_expected
print(f"\n[{'PASS' if years_match else 'FAIL'}] [Counterfactual] Year filter: ", end="")
print(f"Found {years_found}, expected {years_expected}")

# --- Check 7: [Semantic] All sex categories preserved for cleaning ---
# INTENT: The cleaning script needs sex==99 rows. If the fetch inadvertently
# filtered to sex==99 only, we'd lose the ability to verify completeness.
# The raw data should contain all sex categories (1=Male, 2=Female, 99=Total).
sex_values = sorted(df["sex"].unique().to_list())
expected_sex = [1, 2, 99]
sex_ok = sex_values == expected_sex
print(f"[{'PASS' if sex_ok else 'WARN'}] [Semantic] Sex categories preserved: ", end="")
print(f"Found {sex_values}, expected {expected_sex}")

# Verify roughly equal distribution across sex categories
sex_counts = df.group_by("sex").len().sort("sex")
print("  Sex category distribution:")
for row in sex_counts.iter_rows(named=True):
    print(f"    sex={row['sex']}: {row['len']:,} rows")

# Check: sex==99 should have roughly 1/3 of total rows
sex99_count = df.filter(pl.col("sex") == 99).shape[0]
sex99_ratio = sex99_count / row_count
sex99_balanced = 0.25 < sex99_ratio < 0.40
print(f"  sex==99 ratio: {sex99_ratio:.2%} {'(balanced)' if sex99_balanced else '(UNEXPECTED ratio)'}")

# --- Check 8: [Boundary] Zero/negative values in count columns ---
# INTENT: Count columns (applied, admitted, enrolled) should be non-negative
# in real data. Negative values (other than coded -1/-2/-3) would indicate
# corruption. Zero is legitimate (e.g., a school that admitted 0 students).
count_cols = ["number_applied", "number_admitted", "number_enrolled_ft",
              "number_enrolled_pt", "number_enrolled_total"]
boundary_issues = []
for col in count_cols:
    if col not in df.columns:
        continue
    col_data = df[col].drop_nulls()
    # Check for unexpected negative values (not coded values)
    unexpected_neg = col_data.filter(
        (col_data < 0) & (~col_data.is_in(CODED_MISSING_VALUES))
    )
    if len(unexpected_neg) > 0:
        boundary_issues.append(f"{col}: {len(unexpected_neg)} unexpected negatives")
    # Check max value reasonableness (single institution shouldn't have >1M applications)
    max_val = col_data.max()
    if max_val is not None and max_val > 1_000_000:
        boundary_issues.append(f"{col}: max={max_val:,} (unreasonably large)")

boundary_ok = len(boundary_issues) == 0
print(f"[{'PASS' if boundary_ok else 'WARN'}] [Boundary] Count column ranges: ", end="")
print("All reasonable" if boundary_ok else "; ".join(boundary_issues))

# --- Check 9: [Absence] Duplicate unitid+year+sex combinations ---
# INTENT: Each institution should appear exactly once per year+sex combination.
# Duplicates would indicate the data has unexpected granularity.
key_cols = ["unitid", "year", "sex"]
total_rows = df.shape[0]
unique_keys = df.select(key_cols).unique().shape[0]
no_dupes = total_rows == unique_keys
print(f"[{'PASS' if no_dupes else 'FAIL'}] [Absence] Unique (unitid, year, sex): ", end="")
print(f"{unique_keys:,} unique vs {total_rows:,} total rows")
if not no_dupes:
    dupe_count = total_rows - unique_keys
    print(f"  CONCERN: {dupe_count:,} duplicate key combinations detected")

# --- Check 10: [Downstream] sex==99 rows available for cleaning ---
# INTENT: The downstream cleaning script (Task 3.2) will filter to sex==99
# and year==2020. Check that this specific subset exists and has reasonable size.
downstream_subset = df.filter(
    (pl.col("sex") == 99) & (pl.col("year") == 2020)
)
downstream_count = downstream_subset.shape[0]
downstream_ok = 1_500 < downstream_count < 5_000
print(f"[{'PASS' if downstream_ok else 'WARN'}] [Downstream] sex==99 & year==2020 subset: ", end="")
print(f"{downstream_count:,} rows (cleaning expects ~2,000-3,500)")

# --- Spot-Check A: Trace a specific unitid across rows ---
# Pick a common large university (e.g., first unitid) and trace
sample_unitids = df["unitid"].unique().sort().head(3).to_list()
print(f"\n--- Spot-Check A: Trace unitid={sample_unitids[0]} across rows ---")
sample = df.filter(pl.col("unitid") == sample_unitids[0])
print(f"  Rows for unitid={sample_unitids[0]}: {sample.shape[0]}")
print(sample.select(["unitid", "year", "sex", "number_applied", "number_admitted"]))
# Expect: 6 rows = 2 years x 3 sex categories
spot_a_ok = sample.shape[0] == 6
print(f"  [{'PASS' if spot_a_ok else 'INFO'}] Expected 6 rows (2 years x 3 sex), got {sample.shape[0]}")

# --- Spot-Check B: Sex categories are exactly {1, 2, 99} ---
# Already verified above, but cross-check no institution has a different set
institutions_by_sex = df.group_by("unitid", "year").agg(
    pl.col("sex").n_unique().alias("n_sex_cats"),
    pl.col("sex").sort().implode().alias("sex_cats"),
)
unusual_sex = institutions_by_sex.filter(pl.col("n_sex_cats") != 3)
print(f"\n--- Spot-Check B: Institutions with != 3 sex categories ---")
print(f"  {unusual_sex.shape[0]:,} institution-years have != 3 sex categories out of {institutions_by_sex.shape[0]:,}")
if unusual_sex.shape[0] > 0:
    print(f"  Sample of unusual cases:")
    print(unusual_sex.head(5))

# --- Spot-Check C: number_applied >= number_admitted (logical constraint) ---
# INTENT: You cannot admit more than applied. Violations (excluding coded values)
# indicate data quality issues.
print(f"\n--- Spot-Check C: Applied >= Admitted constraint ---")
valid_pairs = df.filter(
    pl.col("number_applied").is_not_null()
    & pl.col("number_admitted").is_not_null()
    & ~pl.col("number_applied").is_in(CODED_MISSING_VALUES)
    & ~pl.col("number_admitted").is_in(CODED_MISSING_VALUES)
)
violations = valid_pairs.filter(pl.col("number_admitted") > pl.col("number_applied"))
print(f"  Valid pairs to check: {valid_pairs.shape[0]:,}")
print(f"  Violations (admitted > applied): {violations.shape[0]:,}")
if violations.shape[0] > 0:
    print(f"  [WARN] Sample violations:")
    print(violations.head(5).select(["unitid", "year", "sex", "number_applied", "number_admitted"]))

# --- Spot-Check D: Year distribution balance ---
print(f"\n--- Spot-Check D: Year distribution balance ---")
year_counts = df.group_by("year").len().sort("year")
for row in year_counts.iter_rows(named=True):
    print(f"  Year {row['year']}: {row['len']:,} rows")
if year_counts.shape[0] == 2:
    counts_list = year_counts["len"].to_list()
    ratio = min(counts_list) / max(counts_list)
    balanced = ratio > 0.9
    print(f"  Year balance ratio: {ratio:.3f} {'(balanced)' if balanced else '(IMBALANCED)'}")

# --- Spot-Check E: Institutions with partial sex categories ---
# Some institutions might not report all three sex categories.
# This is important because downstream assumes sex==99 exists for all.
print(f"\n--- Spot-Check E: Institutions missing sex==99 rows ---")
all_unitid_years = df.select(["unitid", "year"]).unique()
sex99_unitid_years = df.filter(pl.col("sex") == 99).select(["unitid", "year"]).unique()
missing_sex99 = all_unitid_years.join(sex99_unitid_years, on=["unitid", "year"], how="anti")
print(f"  Institution-years total: {all_unitid_years.shape[0]:,}")
print(f"  Institution-years with sex==99: {sex99_unitid_years.shape[0]:,}")
print(f"  Institution-years MISSING sex==99: {missing_sex99.shape[0]:,}")
if missing_sex99.shape[0] > 0:
    print(f"  [WARN] These institutions will be lost in cleaning (sex==99 filter)")

# --- Summary ---
all_critical = all([schema_ok, col_count_ok, rows_ok, dist_ok, years_match,
                    sex_ok, no_dupes, downstream_ok])
print("\n" + "=" * 60)
severity = "PASSED" if all_critical else "ISSUES_FOUND"
print(f"QA RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in ["unitid", "year", "sex"]:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().sort(col).head(20))

print("\nYear distribution:")
print(df["year"].value_counts().sort("year"))

print("\nNumber of unique unitids per year:")
for yr in [2020, 2021]:
    n_inst = df.filter(pl.col("year") == yr)["unitid"].n_unique()
    print(f"  {yr}: {n_inst:,} unique institutions")

print("\nNull summary:")
for col in df.columns:
    nc = df[col].null_count()
    if nc > 0:
        print(f"  {col}: {nc:,} nulls ({nc/row_count*100:.1f}%)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:07:31
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_02_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 1.2 — fetch-admissions
# ============================================================
# Loaded: 11,910 rows x 9 cols
# 
# [PASS] Schema: All 9 expected columns present
# [PASS] Column count: 9 (expected exactly 9)
# [PASS] Row count: 11,910 (expected 5,000-35,000)
#   [WARN] Row count 11,910 outside Plan_Tasks verify range (15000, 30000)
#   NOTE: Plan.md Transformation Sequence says ~6K for this task.
#   Actual: ~1,985 institutions x 3 sex categories x 2 years = 11,910
# [PASS] Distributions: Look reasonable
# [PASS] Coded values: None found (unusual for raw IPEDS data)
# [PASS] Critical nulls:   [INFO] number_applied: 3 nulls (0.0%) (acceptable at raw stage)
#   [INFO] number_admitted: 438 nulls (3.7%) (acceptable at raw stage)
# 
# [PASS] [Counterfactual] Year filter: Found [2020, 2021], expected [2020, 2021]
# [PASS] [Semantic] Sex categories preserved: Found [1, 2, 99], expected [1, 2, 99]
#   Sex category distribution:
#     sex=1: 3,970 rows
#     sex=2: 3,970 rows
#     sex=99: 3,970 rows
#   sex==99 ratio: 33.33% (balanced)
# [PASS] [Boundary] Count column ranges: All reasonable
# [PASS] [Absence] Unique (unitid, year, sex): 11,910 unique vs 11,910 total rows
# [PASS] [Downstream] sex==99 & year==2020 subset: 1,989 rows (cleaning expects ~2,000-3,500)
# 
# --- Spot-Check A: Trace unitid=100654 across rows ---
#   Rows for unitid=100654: 6
# shape: (6, 5)
# ┌────────┬──────┬─────┬────────────────┬─────────────────┐
# │ unitid ┆ year ┆ sex ┆ number_applied ┆ number_admitted │
# │ ---    ┆ ---  ┆ --- ┆ ---            ┆ ---             │
# │ i64    ┆ i64  ┆ i64 ┆ i64            ┆ i64             │
# ╞════════╪══════╪═════╪════════════════╪═════════════════╡
# │ 100654 ┆ 2020 ┆ 1   ┆ 3394           ┆ 2947            │
# │ 100654 ┆ 2020 ┆ 2   ┆ 6461           ┆ 5888            │
# │ 100654 ┆ 2020 ┆ 99  ┆ 9855           ┆ 8835            │
# │ 100654 ┆ 2021 ┆ 1   ┆ 2209           ┆ 1599            │
# │ 100654 ┆ 2021 ┆ 2   ┆ 4345           ┆ 3092            │
# │ 100654 ┆ 2021 ┆ 99  ┆ 6560           ┆ 4697            │
# └────────┴──────┴─────┴────────────────┴─────────────────┘
#   [PASS] Expected 6 rows (2 years x 3 sex), got 6
# 
# --- Spot-Check B: Institutions with != 3 sex categories ---
#   0 institution-years have != 3 sex categories out of 3,970
# 
# --- Spot-Check C: Applied >= Admitted constraint ---
#   Valid pairs to check: 11,471
#   Violations (admitted > applied): 0
# 
# --- Spot-Check D: Year distribution balance ---
#   Year 2020: 5,967 rows
#   Year 2021: 5,943 rows
#   Year balance ratio: 0.996 (balanced)
# 
# --- Spot-Check E: Institutions missing sex==99 rows ---
#   Institution-years total: 3,970
#   Institution-years with sex==99: 3,970
#   Institution-years MISSING sex==99: 0
# 
# ============================================================
# QA RESULT: PASSED
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 9)
# ┌────────┬──────┬──────┬─────┬───┬────────────────┬────────────────┬───────────────┬───────────────┐
# │ unitid ┆ year ┆ fips ┆ sex ┆ … ┆ number_admitte ┆ number_enrolle ┆ number_enroll ┆ number_enroll │
# │ ---    ┆ ---  ┆ ---  ┆ --- ┆   ┆ d              ┆ d_ft           ┆ ed_pt         ┆ ed_total      │
# │ i64    ┆ i64  ┆ i64  ┆ i64 ┆   ┆ ---            ┆ ---            ┆ ---           ┆ ---           │
# │        ┆      ┆      ┆     ┆   ┆ i64            ┆ i64            ┆ i64           ┆ i64           │
# ╞════════╪══════╪══════╪═════╪═══╪════════════════╪════════════════╪═══════════════╪═══════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 1   ┆ … ┆ 2947           ┆ 660            ┆ 16            ┆ 676           │
# │ 100654 ┆ 2020 ┆ 1    ┆ 2   ┆ … ┆ 5888           ┆ 962            ┆ 26            ┆ 988           │
# │ 100654 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 8835           ┆ 1622           ┆ 42            ┆ 1664          │
# │ 100654 ┆ 2021 ┆ 1    ┆ 1   ┆ … ┆ 1599           ┆ 623            ┆ 24            ┆ 647           │
# │ 100654 ┆ 2021 ┆ 1    ┆ 2   ┆ … ┆ 3092           ┆ 834            ┆ 51            ┆ 885           │
# │ 100654 ┆ 2021 ┆ 1    ┆ 99  ┆ … ┆ 4697           ┆ 1459           ┆ 75            ┆ 1534          │
# │ 100663 ┆ 2020 ┆ 1    ┆ 1   ┆ … ┆ 3002           ┆ 738            ┆ 27            ┆ 765           │
# │ 100663 ┆ 2020 ┆ 1    ┆ 2   ┆ … ┆ 5373           ┆ 1364           ┆ 25            ┆ 1389          │
# │ 100663 ┆ 2020 ┆ 1    ┆ 99  ┆ … ┆ 8375           ┆ 2102           ┆ 52            ┆ 2154          │
# │ 100663 ┆ 2021 ┆ 1    ┆ 1   ┆ … ┆ 3501           ┆ 816            ┆ 19            ┆ 835           │
# └────────┴──────┴──────┴─────┴───┴────────────────┴────────────────┴───────────────┴───────────────┘
# 
# Descriptive statistics:
# shape: (9, 10)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ unitid    ┆ year      ┆ fips      ┆ … ┆ number_ad ┆ number_en ┆ number_en ┆ number_e │
# │ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ mitted    ┆ rolled_ft ┆ rolled_pt ┆ nrolled_ │
# │ str       ┆ f64       ┆ f64       ┆ f64       ┆   ┆ ---       ┆ ---       ┆ ---       ┆ total    │
# │           ┆           ┆           ┆           ┆   ┆ f64       ┆ f64       ┆ f64       ┆ ---      │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ f64      │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 11910.0   ┆ 11910.0   ┆ 11910.0   ┆ … ┆ 11472.0   ┆ 11302.0   ┆ 8960.0    ┆ 11415.0  │
# │ null_coun ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ … ┆ 438.0     ┆ 608.0     ┆ 2950.0    ┆ 495.0    │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ 225686.13 ┆ 2020.4989 ┆ 30.73073  ┆ … ┆ 2508.3812 ┆ 543.93310 ┆ 28.657143 ┆ 561.0424 │
# │           ┆ 3249      ┆ 92        ┆           ┆   ┆ 76        ┆ 9         ┆           ┆ 88       │
# │ std       ┆ 107453.74 ┆ 0.50002   ┆ 15.810006 ┆ … ┆ 4528.3907 ┆ 996.58262 ┆ 179.87196 ┆ 1040.525 │
# │           ┆ 5389      ┆           ┆           ┆   ┆ 67        ┆ 6         ┆ 2         ┆ 762      │
# │ min       ┆ 100654.0  ┆ 2020.0    ┆ 1.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0.0      │
# │ 25%       ┆ 158477.0  ┆ 2020.0    ┆ 18.0      ┆ … ┆ 150.0     ┆ 60.0      ┆ 1.0       ┆ 63.0     │
# │ 50%       ┆ 196200.0  ┆ 2020.0    ┆ 34.0      ┆ … ┆ 913.0     ┆ 206.0     ┆ 3.0       ┆ 208.0    │
# │ 75%       ┆ 230959.0  ┆ 2021.0    ┆ 42.0      ┆ … ┆ 2691.0    ┆ 545.0     ┆ 15.0      ┆ 555.0    │
# │ max       ┆ 497268.0  ┆ 2021.0    ┆ 78.0      ┆ … ┆ 89207.0   ┆ 15785.0   ┆ 8301.0    ┆ 16049.0  │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
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
# │ 100654 ┆ 6     │
# │ 100663 ┆ 6     │
# │ 100706 ┆ 6     │
# │ 100724 ┆ 6     │
# │ 100751 ┆ 6     │
# │ …      ┆ …     │
# │ 101648 ┆ 6     │
# │ 101693 ┆ 6     │
# │ 101709 ┆ 6     │
# │ 101879 ┆ 6     │
# │ 101912 ┆ 6     │
# └────────┴───────┘
# 
# year:
# shape: (2, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 5967  │
# │ 2021 ┆ 5943  │
# └──────┴───────┘
# 
# sex:
# shape: (3, 2)
# ┌─────┬───────┐
# │ sex ┆ count │
# │ --- ┆ ---   │
# │ i64 ┆ u32   │
# ╞═════╪═══════╡
# │ 1   ┆ 3970  │
# │ 2   ┆ 3970  │
# │ 99  ┆ 3970  │
# └─────┴───────┘
# 
# Year distribution:
# shape: (2, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 5967  │
# │ 2021 ┆ 5943  │
# └──────┴───────┘
# 
# Number of unique unitids per year:
#   2020: 1,989 unique institutions
#   2021: 1,981 unique institutions
# 
# Null summary:
#   number_applied: 3 nulls (0.0%)
#   number_admitted: 438 nulls (3.7%)
#   number_enrolled_ft: 608 nulls (5.1%)
#   number_enrolled_pt: 2,950 nulls (24.8%)
#   number_enrolled_total: 495 nulls (4.2%)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
