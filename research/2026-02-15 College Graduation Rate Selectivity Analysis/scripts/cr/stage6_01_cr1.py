#!/usr/bin/env python3
"""
QA INSPECTION: Stage 6 Step 3.1

Reviewed script: scripts/stage6_clean/01_clean-directory.py
Output files: data/processed/2026-02-15_directory_clean.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default):
1. Schema matches Plan expectations (adjusted for known missing columns)
2. Row count within expected range (2,000-3,000)
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns (unitid, inst_name, inst_control, hbcu)

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if coded values existed in columns NOT in NUMERIC_COLS_TO_CLEAN?
7. [Semantic] Does the cleaning serve the research question (selectivity vs quality)?
8. [Boundary] Check edge cases: null inst_control, single-value columns, locale nulls
9. [Absence] Verify no open_admissions or enrollment_undergrad silently present
10. [Downstream] Join readiness: unitid uniqueness, inst_control values for sector comparison

Spot-Checks:
11. Trace a specific institution through raw -> clean
12. Verify coded value replacement didn't alter non-coded values
13. Verify cc_basic_2021 was actually dropped (not just renamed)
14. Check that the 2 locale nulls are the former coded -1 values
15. Cross-check inst_control distribution against known IPEDS totals
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_directory_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_directory.parquet"

# Adjusted expected columns: Plan originally listed open_admissions and
# enrollment_undergrad but these are not in IPEDS directory (documented in
# Stage 5 _a.py revision). cc_basic_2021 is dropped by clean script (100% null).
EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "inst_control", "institution_level",
    "hbcu", "degree_granting", "urban_centric_locale", "state_abbr", "fips",
]
EXPECTED_MIN_ROWS = 2000
EXPECTED_MAX_ROWS = 3000
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control", "hbcu"]
CODED_MISSING = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 6 Step 3.1 — clean-directory")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded clean: {df.shape[0]:,} rows x {df.shape[1]} cols")

df_raw = pl.read_parquet(RAW_FILE)
print(f"Loaded raw: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# ============================================================
# DEFAULT CHECKS
# ============================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 - Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  [INFO] Extra columns: {extra_cols}")

# Verify cc_basic_2021 was dropped
cc_dropped = "cc_basic_2021" not in df.columns and "cc_basic_2021" in df_raw.columns
print(f"  [{'PASS' if cc_dropped else 'FAIL'}] cc_basic_2021 dropped from clean output")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Check 2 - Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# Row count preserved from raw
raw_match = len(df) == len(df_raw)
print(f"  [{'PASS' if raw_match else 'FAIL'}] Row count matches raw: {len(df_raw):,} -> {len(df):,}")

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
print(f"[{'PASS' if dist_ok else 'WARN'}] Check 3 - Distributions: ", end="")
if dist_ok:
    print("Look reasonable")
else:
    for issue in dist_issues:
        print(f"  {issue}")

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in CODED_MISSING:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Check 4 - Coded values: ", end="")
print("None remain in any integer column" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls ({null_count/len(df)*100:.1f}%)")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Check 5 - Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ============================================================

# --- Check 6: [Counterfactual] Coded values in columns NOT in NUMERIC_COLS_TO_CLEAN ---
# The script only cleaned: inst_control, institution_level, hbcu, degree_granting,
# urban_centric_locale, cc_basic_2021. What about unitid, year, fips?
# These SHOULDN'T have coded values, but let's verify.
print("\n[Counterfactual] Check 6 - Coded values in identifier/other columns:")
non_cleaned_int_cols = [c for c in ["unitid", "year", "fips"] if c in df.columns and df[c].dtype in [pl.Int64, pl.Int32, pl.Int16, pl.Int8]]
cf_issues = []
for col in non_cleaned_int_cols:
    for code in CODED_MISSING:
        count = (df[col] == code).sum()
        if count > 0:
            cf_issues.append(f"{col} == {code}: {count}")
cf_ok = len(cf_issues) == 0
print(f"  [{'PASS' if cf_ok else 'WARN'}] No coded values in {non_cleaned_int_cols}")

# --- Check 7: [Semantic] Does cleaning serve the research question? ---
# The research question is about selectivity vs quality. inst_control is needed
# for the Observable Truth: "Private nonprofit institutions have higher graduation
# rates than public institutions within the same selectivity band."
# inst_control must have values 1 (public) and 2 (private nonprofit) only.
print("\n[Semantic] Check 7 - inst_control serves sector comparison:")
ic_vals = sorted(df["inst_control"].drop_nulls().unique().to_list())
ic_ok = set(ic_vals) == {1, 2}
print(f"  [{'PASS' if ic_ok else 'FAIL'}] inst_control values: {ic_vals} (need exactly [1, 2])")
ic_null = df["inst_control"].null_count()
print(f"  [{'PASS' if ic_null == 0 else 'WARN'}] inst_control nulls: {ic_null} (must be 0 for sector comparison)")

# hbcu is needed for downstream characterization
hbcu_vals = sorted(df["hbcu"].drop_nulls().unique().to_list())
hbcu_null = df["hbcu"].null_count()
print(f"  [{'PASS' if hbcu_null == 0 else 'WARN'}] hbcu values: {hbcu_vals}, nulls: {hbcu_null}")

# --- Check 8: [Boundary] Edge cases ---
print("\n[Boundary] Check 8 - Edge cases:")
# Check for any single-row groups in inst_control
ic_counts = df["inst_control"].value_counts()
min_group = ic_counts["count"].min()
print(f"  [{'PASS' if min_group > 1 else 'WARN'}] Smallest inst_control group: {min_group}")

# Check locale null count matches expected (should be 2 from coded -1 replacement)
locale_null = df["urban_centric_locale"].null_count()
print(f"  [{'PASS' if locale_null == 2 else 'WARN'}] urban_centric_locale nulls: {locale_null} (expected 2 from coded -1 replacement)")

# Check institution_level is only 4
il_vals = sorted(df["institution_level"].drop_nulls().unique().to_list())
print(f"  [{'PASS' if il_vals == [4] else 'FAIL'}] institution_level values: {il_vals} (expected [4])")

# --- Check 9: [Absence] Columns that SHOULD NOT be present ---
print("\n[Absence] Check 9 - Verify missing columns status:")
# open_admissions and enrollment_undergrad should NOT be in clean data
# (not fetched — documented Stage 5 deviation)
oa_absent = "open_admissions" not in df.columns
eu_absent = "enrollment_undergrad" not in df.columns
print(f"  [INFO] open_admissions absent (as expected, not in directory endpoint): {oa_absent}")
print(f"  [INFO] enrollment_undergrad absent (as expected, not in directory endpoint): {eu_absent}")

# cc_basic_2021 should be dropped
cc_absent = "cc_basic_2021" not in df.columns
print(f"  [{'PASS' if cc_absent else 'FAIL'}] cc_basic_2021 properly dropped: {cc_absent}")

# Check that degree_granting==0 institutions exist (5 of them) — these are valid
# 4-year institutions that may not grant degrees (e.g., specialized institutions)
dg_zero = df.filter(pl.col("degree_granting") == 0).height
print(f"  [INFO] Non-degree-granting institutions present: {dg_zero} (5 expected per execution log)")

# --- Check 10: [Downstream] Join readiness ---
print("\n[Downstream] Check 10 - Join readiness for Wave 5 (join-core):")
# unitid must be unique (1:1 join key)
unitid_unique = df["unitid"].n_unique() == len(df)
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid unique: {df['unitid'].n_unique()}/{len(df)}")

# unitid must be non-null
unitid_nonnull = df["unitid"].null_count() == 0
print(f"  [{'PASS' if unitid_nonnull else 'FAIL'}] unitid non-null: {unitid_nonnull}")

# inst_control must be non-null for sector comparison
ic_nonnull = df["inst_control"].null_count() == 0
print(f"  [{'PASS' if ic_nonnull else 'FAIL'}] inst_control non-null (required for sector comparison): {ic_nonnull}")

# Check that year is consistently 2020
year_vals = df["year"].unique().to_list()
year_ok = year_vals == [2020]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year consistency: {year_vals} (expected [2020])")

# ============================================================
# SPOT-CHECKS
# ============================================================
print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Trace a specific institution through raw -> clean ---
# Pick Harvard (unitid likely 166027) or a well-known institution
sample_ids = df.sort("unitid").head(5)["unitid"].to_list()
target_id = sample_ids[0]  # Pick first institution alphabetically by ID
raw_row = df_raw.filter(pl.col("unitid") == target_id)
clean_row = df.filter(pl.col("unitid") == target_id)
print(f"\nSpot-check 11: Trace unitid={target_id}")
print(f"  Raw: {raw_row.shape[0]} row(s), cols={raw_row.columns}")
print(f"  Clean: {clean_row.shape[0]} row(s), cols={clean_row.columns}")
if raw_row.shape[0] == 1 and clean_row.shape[0] == 1:
    # Compare preserved values
    for col in ["unitid", "inst_name", "inst_control", "hbcu"]:
        raw_val = raw_row[col][0]
        clean_val = clean_row[col][0]
        match = raw_val == clean_val
        print(f"  [{'PASS' if match else 'FAIL'}] {col}: raw={raw_val} -> clean={clean_val}")

# --- Spot-check 12: Non-coded values preserved ---
# Verify that values like inst_control=1 and inst_control=2 weren't altered
print(f"\nSpot-check 12: Non-coded values preserved in inst_control:")
raw_ic_counts = df_raw["inst_control"].value_counts().sort("inst_control")
clean_ic_counts = df["inst_control"].value_counts().sort("inst_control")
# inst_control should have identical distributions (no coded values to replace there)
for row in raw_ic_counts.iter_rows(named=True):
    raw_count = row["count"]
    val = row["inst_control"]
    if val in CODED_MISSING:
        continue
    clean_match = clean_ic_counts.filter(pl.col("inst_control") == val)
    if clean_match.height > 0:
        clean_count = clean_match["count"][0]
        match = raw_count == clean_count
        print(f"  [{'PASS' if match else 'FAIL'}] inst_control={val}: raw={raw_count}, clean={clean_count}")

# --- Spot-check 13: cc_basic_2021 really dropped, not renamed ---
print(f"\nSpot-check 13: cc_basic_2021 truly dropped:")
# Verify column count is exactly 1 less than raw
col_diff = len(df_raw.columns) - len(df.columns)
print(f"  [{'PASS' if col_diff == 1 else 'WARN'}] Column count: raw={len(df_raw.columns)} -> clean={len(df.columns)} (diff={col_diff})")
# Verify no column has the same null pattern as cc_basic_2021 would
for col in df.columns:
    if df[col].null_count() == len(df):
        print(f"  [WARN] Column {col} is 100% null (suspicious rename?)")

# --- Spot-check 14: Locale nulls are from coded value replacement ---
print(f"\nSpot-check 14: Verify locale nulls came from coded -1:")
raw_locale_coded = df_raw.filter(pl.col("urban_centric_locale") == -1).height
clean_locale_null = df["urban_centric_locale"].null_count()
raw_locale_null = df_raw["urban_centric_locale"].null_count()
new_nulls = clean_locale_null - raw_locale_null
print(f"  Raw coded -1 count: {raw_locale_coded}")
print(f"  Raw null count: {raw_locale_null}")
print(f"  Clean null count: {clean_locale_null}")
print(f"  New nulls from replacement: {new_nulls}")
match = raw_locale_coded == new_nulls
print(f"  [{'PASS' if match else 'FAIL'}] New nulls ({new_nulls}) == raw coded -1 count ({raw_locale_coded})")

# --- Spot-check 15: inst_control distribution plausibility ---
print(f"\nSpot-check 15: inst_control distribution plausibility:")
public_count = df.filter(pl.col("inst_control") == 1).height
private_count = df.filter(pl.col("inst_control") == 2).height
public_pct = public_count / len(df) * 100
private_pct = private_count / len(df) * 100
print(f"  Public (1): {public_count} ({public_pct:.1f}%)")
print(f"  Private nonprofit (2): {private_count} ({private_pct:.1f}%)")
# In the US, there are roughly ~700 public 4-year and ~1,600 private nonprofit
# 4-year institutions. So roughly 30% public, 70% private is expected.
public_plausible = 20 < public_pct < 50
private_plausible = 50 < private_pct < 80
print(f"  [{'PASS' if public_plausible else 'WARN'}] Public share {public_pct:.1f}% (expected ~30%)")
print(f"  [{'PASS' if private_plausible else 'WARN'}] Private share {private_pct:.1f}% (expected ~65%)")

# ============================================================
# DATA PROFILING (for cr2+ decision)
# ============================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns and df[col].dtype in [pl.Int64, pl.Int32, pl.Utf8]:
        vc = df[col].value_counts().sort("count", descending=True).head(20)
        print(f"\n{col} (top 20):")
        print(vc)

print("\nFull schema with types:")
for col in df.columns:
    null_ct = df[col].null_count()
    null_pct = null_ct / len(df) * 100
    print(f"  {col}: {df[col].dtype}, nulls={null_ct} ({null_pct:.1f}%)")

# --- Summary ---
all_default_passed = all([schema_ok, rows_ok, coded_ok, nulls_ok, cc_dropped, raw_match])
all_lens_passed = all([cf_ok, ic_ok, unitid_unique, unitid_nonnull, cc_absent, year_ok])
all_spot_passed = all([match, col_diff == 1, public_plausible, private_plausible])

all_passed = all_default_passed and all_lens_passed and all_spot_passed
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "WARNING" if (all_default_passed and all_lens_passed) else "BLOCKER"
print(f"QA RESULT: {severity}")
if dist_issues:
    print(f"  Distribution notes: year is single value (expected for year=2020 filter)")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:46:12
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage6_01_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 6 Step 3.1 — clean-directory
# ============================================================
# Loaded clean: 2,528 rows x 10 cols
# Loaded raw: 2,528 rows x 11 cols
# 
# [PASS] Check 1 - Schema: All expected columns present
#   [PASS] cc_basic_2021 dropped from clean output
# [PASS] Check 2 - Row count: 2,528 (expected 2,000-3,000)
#   [PASS] Row count matches raw: 2,528 -> 2,528
# [WARN] Check 3 - Distributions:   year: all same value (2020)
#   institution_level: all same value (4)
# [PASS] Check 4 - Coded values: None remain in any integer column
# [PASS] Check 5 - Critical nulls: None
# 
# [Counterfactual] Check 6 - Coded values in identifier/other columns:
#   [PASS] No coded values in ['unitid', 'year', 'fips']
# 
# [Semantic] Check 7 - inst_control serves sector comparison:
#   [PASS] inst_control values: [1, 2] (need exactly [1, 2])
#   [PASS] inst_control nulls: 0 (must be 0 for sector comparison)
#   [PASS] hbcu values: [0, 1], nulls: 0
# 
# [Boundary] Check 8 - Edge cases:
#   [PASS] Smallest inst_control group: 852
#   [PASS] urban_centric_locale nulls: 2 (expected 2 from coded -1 replacement)
#   [PASS] institution_level values: [4] (expected [4])
# 
# [Absence] Check 9 - Verify missing columns status:
#   [INFO] open_admissions absent (as expected, not in directory endpoint): True
#   [INFO] enrollment_undergrad absent (as expected, not in directory endpoint): True
#   [PASS] cc_basic_2021 properly dropped: True
#   [INFO] Non-degree-granting institutions present: 5 (5 expected per execution log)
# 
# [Downstream] Check 10 - Join readiness for Wave 5 (join-core):
#   [PASS] unitid unique: 2528/2528
#   [PASS] unitid non-null: True
#   [PASS] inst_control non-null (required for sector comparison): True
#   [PASS] Year consistency: [2020] (expected [2020])
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-check 11: Trace unitid=100654
#   Raw: 1 row(s), cols=['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'cc_basic_2021', 'state_abbr', 'fips']
#   Clean: 1 row(s), cols=['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips']
#   [PASS] unitid: raw=100654 -> clean=100654
#   [PASS] inst_name: raw=Alabama A & M University -> clean=Alabama A & M University
#   [PASS] inst_control: raw=1 -> clean=1
#   [PASS] hbcu: raw=1 -> clean=1
# 
# Spot-check 12: Non-coded values preserved in inst_control:
#   [PASS] inst_control=1: raw=852, clean=852
#   [PASS] inst_control=2: raw=1676, clean=1676
# 
# Spot-check 13: cc_basic_2021 truly dropped:
#   [PASS] Column count: raw=11 -> clean=10 (diff=1)
# 
# Spot-check 14: Verify locale nulls came from coded -1:
#   Raw coded -1 count: 2
#   Raw null count: 0
#   Clean null count: 2
#   New nulls from replacement: 2
#   [PASS] New nulls (2) == raw coded -1 count (2)
# 
# Spot-check 15: inst_control distribution plausibility:
#   Public (1): 852 (33.7%)
#   Private nonprofit (2): 1676 (66.3%)
#   [PASS] Public share 33.7% (expected ~30%)
#   [PASS] Private share 66.3% (expected ~65%)
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 10)
# ┌────────┬──────┬──────────────┬──────────────┬───┬──────────────┬─────────────┬────────────┬──────┐
# │ unitid ┆ year ┆ inst_name    ┆ inst_control ┆ … ┆ degree_grant ┆ urban_centr ┆ state_abbr ┆ fips │
# │ ---    ┆ ---  ┆ ---          ┆ ---          ┆   ┆ ing          ┆ ic_locale   ┆ ---        ┆ ---  │
# │ i64    ┆ i64  ┆ str          ┆ i64          ┆   ┆ ---          ┆ ---         ┆ str        ┆ i64  │
# │        ┆      ┆              ┆              ┆   ┆ i64          ┆ i64         ┆            ┆      │
# ╞════════╪══════╪══════════════╪══════════════╪═══╪══════════════╪═════════════╪════════════╪══════╡
# │ 100654 ┆ 2020 ┆ Alabama A &  ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ M University ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100663 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ at Birmi…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100690 ┆ 2020 ┆ Amridge      ┆ 2            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100706 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ in Hunts…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100724 ┆ 2020 ┆ Alabama      ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ State        ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100733 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ System O…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100751 ┆ 2020 ┆ The          ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100812 ┆ 2020 ┆ Athens State ┆ 1            ┆ … ┆ 1            ┆ 31          ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100830 ┆ 2020 ┆ Auburn       ┆ 1            ┆ … ┆ 1            ┆ 12          ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ at           ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ Montgomer…   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100858 ┆ 2020 ┆ Auburn       ┆ 1            ┆ … ┆ 1            ┆ 13          ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# └────────┴──────┴──────────────┴──────────────┴───┴──────────────┴─────────────┴────────────┴──────┘
# 
# Descriptive statistics:
# shape: (9, 11)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ inst_name ┆ … ┆ degree_gr ┆ urban_cen ┆ state_abb ┆ fips      │
# │ ---        ┆ ---        ┆ ---    ┆ ---       ┆   ┆ anting    ┆ tric_loca ┆ r         ┆ ---       │
# │ str        ┆ f64        ┆ f64    ┆ str       ┆   ┆ ---       ┆ le        ┆ ---       ┆ f64       │
# │            ┆            ┆        ┆           ┆   ┆ f64       ┆ ---       ┆ str       ┆           │
# │            ┆            ┆        ┆           ┆   ┆           ┆ f64       ┆           ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 2528.0     ┆ 2528.0 ┆ 2528      ┆ … ┆ 2528.0    ┆ 2526.0    ┆ 2528      ┆ 2528.0    │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0         ┆ … ┆ 0.0       ┆ 2.0       ┆ 0         ┆ 0.0       │
# │ mean       ┆ 220569.164 ┆ 2020.0 ┆ null      ┆ … ┆ 0.998022  ┆ 19.64133  ┆ null      ┆ 30.374209 │
# │            ┆ 161        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ std        ┆ 103707.401 ┆ 0.0    ┆ null      ┆ … ┆ 0.044438  ┆ 9.631159  ┆ null      ┆ 16.613986 │
# │            ┆ 134        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ A T Still ┆ … ┆ 0.0       ┆ 11.0      ┆ AK        ┆ 1.0       │
# │            ┆            ┆        ┆ Universit ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ y of      ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ Health…   ┆   ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 155089.0   ┆ 2020.0 ┆ null      ┆ … ┆ 1.0       ┆ 11.0      ┆ null      ┆ 17.0      │
# │ 50%        ┆ 196121.0   ┆ 2020.0 ┆ null      ┆ … ┆ 1.0       ┆ 13.0      ┆ null      ┆ 33.0      │
# │ 75%        ┆ 230597.0   ┆ 2020.0 ┆ null      ┆ … ┆ 1.0       ┆ 23.0      ┆ null      ┆ 42.0      │
# │ max        ┆ 496070.0   ┆ 2020.0 ┆ Zaytuna   ┆ … ┆ 1.0       ┆ 43.0      ┆ WY        ┆ 78.0      │
# │            ┆            ┆        ┆ College   ┆   ┆           ┆           ┆           ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Key column value counts:
# 
# unitid (top 20):
# shape: (20, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ i64    ┆ u32   │
# ╞════════╪═══════╡
# │ 176600 ┆ 1     │
# │ 185129 ┆ 1     │
# │ 199102 ┆ 1     │
# │ 136774 ┆ 1     │
# │ 110316 ┆ 1     │
# │ …      ┆ …     │
# │ 172334 ┆ 1     │
# │ 190761 ┆ 1     │
# │ 207582 ┆ 1     │
# │ 125763 ┆ 1     │
# │ 475228 ┆ 1     │
# └────────┴───────┘
# 
# inst_name (top 20):
# shape: (20, 2)
# ┌─────────────────────────────────┬───────┐
# │ inst_name                       ┆ count │
# │ ---                             ┆ ---   │
# │ str                             ┆ u32   │
# ╞═════════════════════════════════╪═══════╡
# │ Stevens-Henager College         ┆ 6     │
# │ Lincoln University              ┆ 3     │
# │ Bethel University               ┆ 3     │
# │ Union College                   ┆ 3     │
# │ Westminster College             ┆ 3     │
# │ …                               ┆ …     │
# │ Columbia College                ┆ 2     │
# │ Sterling College                ┆ 2     │
# │ University of Puerto Rico-Ponc… ┆ 1     │
# │ Methodist University            ┆ 1     │
# │ Western New England University  ┆ 1     │
# └─────────────────────────────────┴───────┘
# 
# inst_control (top 20):
# shape: (2, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 2            ┆ 1676  │
# │ 1            ┆ 852   │
# └──────────────┴───────┘
# 
# hbcu (top 20):
# shape: (2, 2)
# ┌──────┬───────┐
# │ hbcu ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 0    ┆ 2437  │
# │ 1    ┆ 91    │
# └──────┴───────┘
# 
# Full schema with types:
#   unitid: Int64, nulls=0 (0.0%)
#   year: Int64, nulls=0 (0.0%)
#   inst_name: String, nulls=0 (0.0%)
#   inst_control: Int64, nulls=0 (0.0%)
#   institution_level: Int64, nulls=0 (0.0%)
#   hbcu: Int64, nulls=0 (0.0%)
#   degree_granting: Int64, nulls=0 (0.0%)
#   urban_centric_locale: Int64, nulls=2 (0.1%)
#   state_abbr: String, nulls=0 (0.0%)
#   fips: Int64, nulls=0 (0.0%)
# 
# ============================================================
# QA RESULT: PASSED
#   Distribution notes: year is single value (expected for year=2020 filter)
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
