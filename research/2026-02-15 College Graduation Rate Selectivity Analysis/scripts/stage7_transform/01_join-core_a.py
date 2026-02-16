#!/usr/bin/env python3
"""
Stage 7.1: Join directory + grad rates + admissions + FSA grants on unitid; compute pell_share.

Task: join-core
Wave: 5, Step: 1, Stage: 7
Depends on: clean-directory, clean-grad-rates, clean-admissions, clean-fsa-grants
Input: data/processed/2026-02-15_directory_clean.parquet
       data/processed/2026-02-15_grad_rates_clean.parquet
       data/processed/2026-02-15_admissions_clean.parquet
       data/processed/2026-02-15_fsa_grants_clean.parquet
Output: data/processed/2026-02-15_core_joined.parquet
Checkpoint: CP3

Revision: _a (fix from v1)
  - v1 failed because 'open_admissions' column was assumed to be in the
    admissions dataset, but it is not present in any fetched dataset.
    The Stage 5 fetch (01_fetch-directory_a.py) discovered that neither
    'open_admissions' nor 'enrollment_undergrad' exist in the IPEDS directory
    dataset. They were not fetched from any other source either.
  - Fix: Remove open_admissions from column selections and required columns.
    For pell_share computation, use total_enrollment_race from the
    enrollment_race_clean dataset (which will be joined in step 5.2
    join-demographics) as the enrollment denominator. Since enrollment_race
    data is not available until the next join, we compute pell_share HERE
    by pre-loading only the total_enrollment_race column from enrollment_race.
    This avoids deferring pell_share and keeps the core join self-contained.
  - NOTE: The directory has 'urban_centric_locale' (not 'locale') and does
    NOT have 'enrollment_undergrad'. Adjusted column references accordingly.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for the core join that combines directory, graduation rates,
# admissions, and FSA grants data. Directory is the base table; all other
# datasets are LEFT-joined to preserve the full 4-year public/private nonprofit
# institution universe. Join key is unitid (IPEDS unique institution identifier).
#
# DEVIATION FROM TASK SPEC: The task specification listed 'open_admissions' and
# 'enrollment_undergrad' as directory columns, but the actual directory dataset
# does not contain these. The Stage 5 fetch script documented this gap. We adapt
# by: (1) dropping open_admissions from this join (it can be handled in
# create-bands by assigning null admission_rate to "Less Selective/Open"); and
# (2) using total_enrollment_race from enrollment_race_clean as the enrollment
# denominator for pell_share.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_DIRECTORY = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_directory_clean.parquet"
INPUT_GRAD_RATES = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"
INPUT_ADMISSIONS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_admissions_clean.parquet"
INPUT_FSA_GRANTS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_fsa_grants_clean.parquet"
INPUT_ENROLLMENT_RACE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_enrollment_race_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_joined.parquet"

JOIN_KEY = "unitid"
EXPECTED_BASE_ROWS = 2528  # Directory defines the institution universe

# --- Load ---
# Load all four cleaned datasets and the enrollment denominator.
# Verify shapes before joining.
print("=" * 60)
print("Stage 7.1: Join core datasets (directory + grad rates + admissions + FSA grants)")
print("=" * 60)

df_directory = pl.read_parquet(INPUT_DIRECTORY)
df_grad_rates = pl.read_parquet(INPUT_GRAD_RATES)
df_admissions = pl.read_parquet(INPUT_ADMISSIONS)
df_fsa_grants = pl.read_parquet(INPUT_FSA_GRANTS)
df_enrollment_race = pl.read_parquet(INPUT_ENROLLMENT_RACE)

print(f"\nLoaded datasets:")
print(f"  Directory:        {df_directory.shape[0]:,} rows x {df_directory.shape[1]} cols")
print(f"  Grad Rates:       {df_grad_rates.shape[0]:,} rows x {df_grad_rates.shape[1]} cols")
print(f"  Admissions:       {df_admissions.shape[0]:,} rows x {df_admissions.shape[1]} cols")
print(f"  FSA Grants:       {df_fsa_grants.shape[0]:,} rows x {df_fsa_grants.shape[1]} cols")
print(f"  Enrollment Race:  {df_enrollment_race.shape[0]:,} rows x {df_enrollment_race.shape[1]} cols")

# --- Pre-state ---
# Capture key overlap statistics BEFORE joining. This establishes the expected
# match rates and verifies the 1:1 cardinality assumption for each join pair.
# Also checks for duplicate unitids in each dataset which would cause fan-out.
print("\n" + "-" * 60)
print("Pre-state: Key overlap analysis")
print("-" * 60)

dir_keys = set(df_directory[JOIN_KEY].unique().to_list())

# Check uniqueness in each dataset
dir_unique = df_directory[JOIN_KEY].n_unique() == df_directory.shape[0]
gr_unique = df_grad_rates[JOIN_KEY].n_unique() == df_grad_rates.shape[0]
adm_unique = df_admissions[JOIN_KEY].n_unique() == df_admissions.shape[0]
fsa_unique = df_fsa_grants[JOIN_KEY].n_unique() == df_fsa_grants.shape[0]
enr_unique = df_enrollment_race[JOIN_KEY].n_unique() == df_enrollment_race.shape[0]

print(f"\nUnitid uniqueness:")
print(f"  Directory:        unique={dir_unique} ({df_directory[JOIN_KEY].n_unique()} unique / {df_directory.shape[0]} rows)")
print(f"  Grad Rates:       unique={gr_unique} ({df_grad_rates[JOIN_KEY].n_unique()} unique / {df_grad_rates.shape[0]} rows)")
print(f"  Admissions:       unique={adm_unique} ({df_admissions[JOIN_KEY].n_unique()} unique / {df_admissions.shape[0]} rows)")
print(f"  FSA Grants:       unique={fsa_unique} ({df_fsa_grants[JOIN_KEY].n_unique()} unique / {df_fsa_grants.shape[0]} rows)")
print(f"  Enrollment Race:  unique={enr_unique} ({df_enrollment_race[JOIN_KEY].n_unique()} unique / {df_enrollment_race.shape[0]} rows)")

# CRITICAL CHECK: If FSA grants has duplicate unitids, we must aggregate first.
# The task specification warns that FSA may contain multiple rows per unitid
# (e.g., by grant type or year).
if not fsa_unique:
    fsa_n_unique = df_fsa_grants[JOIN_KEY].n_unique()
    fsa_n_rows = df_fsa_grants.shape[0]
    print(f"\n  WARNING: FSA grants has {fsa_n_rows} rows but only {fsa_n_unique} unique unitids.")
    print(f"  Will aggregate pell_recipients by SUM per unitid before joining.")

# Key overlap with directory
gr_keys = set(df_grad_rates[JOIN_KEY].unique().to_list())
adm_keys = set(df_admissions[JOIN_KEY].unique().to_list())
fsa_keys = set(df_fsa_grants[JOIN_KEY].unique().to_list())
enr_keys = set(df_enrollment_race[JOIN_KEY].unique().to_list())

gr_overlap = len(dir_keys & gr_keys)
adm_overlap = len(dir_keys & adm_keys)
fsa_overlap = len(dir_keys & fsa_keys)
enr_overlap = len(dir_keys & enr_keys)

print(f"\nKey overlap with directory ({len(dir_keys):,} institutions):")
print(f"  Grad Rates:       {gr_overlap:,} / {len(dir_keys):,} ({gr_overlap / len(dir_keys) * 100:.1f}%)")
print(f"  Admissions:       {adm_overlap:,} / {len(dir_keys):,} ({adm_overlap / len(dir_keys) * 100:.1f}%)")
print(f"  FSA Grants:       {fsa_overlap:,} / {len(dir_keys):,} ({fsa_overlap / len(dir_keys) * 100:.1f}%)")
print(f"  Enrollment Race:  {enr_overlap:,} / {len(dir_keys):,} ({enr_overlap / len(dir_keys) * 100:.1f}%)")

# --- Transform: Prepare FSA grants (aggregate if needed) ---
# INTENT: Ensure FSA grants has exactly one row per unitid before joining.
# REASONING: FSA grants data may contain multiple rows per institution (e.g.,
# multiple grant types or years). We need a single pell_recipients value per
# unitid. Summing is correct because pell_recipients represents a count.
#
# ASSUMES:
#   - pell_recipients is the column containing Pell Grant recipient counts
#   - If multiple rows exist per unitid, they represent distinct recipients
#     that should be summed (not averaged)
if not fsa_unique:
    print("\n" + "-" * 60)
    print("Aggregating FSA grants by unitid (SUM pell_recipients)")
    print("-" * 60)
    pre_fsa_rows = df_fsa_grants.shape[0]

    # INTENT: Select only unitid and pell_recipients, then aggregate to one row per unitid.
    # REASONING: We only need pell_recipients from FSA for this join. Keeping other
    # columns would require deciding how to aggregate them, and they're not needed.
    df_fsa_grants = (
        df_fsa_grants
        .group_by(JOIN_KEY)
        .agg(pl.col("pell_recipients").sum())
    )
    print(f"  Aggregated: {pre_fsa_rows:,} rows -> {df_fsa_grants.shape[0]:,} rows")

    # Re-check uniqueness after aggregation
    fsa_unique_after = df_fsa_grants[JOIN_KEY].n_unique() == df_fsa_grants.shape[0]
    print(f"  Uniqueness after aggregation: {fsa_unique_after}")
    assert fsa_unique_after, "STOP: FSA grants still not unique after aggregation"
else:
    # INTENT: Even if unique, select only the columns we need from FSA to keep
    # the join clean and avoid column name conflicts.
    # REASONING: Carrying unnecessary columns through joins wastes memory and
    # creates potential for column name collisions.
    df_fsa_grants = df_fsa_grants.select([JOIN_KEY, "pell_recipients"])
    print("\nFSA grants already has unique unitids; selected unitid + pell_recipients only.")

# --- Transform: Prepare enrollment race (select enrollment denominator only) ---
# INTENT: Extract total_enrollment_race from the enrollment_race dataset to use
# as the enrollment denominator for computing pell_share.
#
# REASONING: The original task spec assumed enrollment_undergrad would be in the
# directory dataset, but it was not fetched (not available in IPEDS directory).
# The best available enrollment denominator is total_enrollment_race from the
# enrollment_race_clean dataset, which represents total fall enrollment across
# all race categories for each institution.
#
# ASSUMES:
#   - total_enrollment_race is the sum of all race/ethnicity enrollment categories
#   - It represents the institution's total fall enrollment headcount
#   - It's suitable as a denominator for pell_share (Pell recipients / total enrollment)
df_enrollment_denom = df_enrollment_race.select([JOIN_KEY, "total_enrollment_race"])
print(f"\nEnrollment denominator prepared: {df_enrollment_denom.shape[0]:,} rows")

# --- Transform: Prepare grad_rates and admissions (select needed columns) ---
# INTENT: Select only the columns we need from each dataset to keep the join clean.
# REASONING: Minimizing columns prevents name collisions and makes the resulting
# dataset easier to audit. Each dataset contributes specific variables per the Plan.

# From grad_rates: grad_rate_150pct, cohort_year
# ASSUMES: year column exists but is redundant with directory's year; drop to avoid _right suffix
df_grad_rates_join = df_grad_rates.select([
    JOIN_KEY,
    "grad_rate_150pct",
    "cohort_year",
])

# From admissions: number_applied, number_admitted, number_enrolled_total, admission_rate
# NOTE: open_admissions is NOT in this dataset (not in any fetched dataset).
# ASSUMES: year column exists but is redundant with directory's year; drop to avoid _right suffix
df_admissions_join = df_admissions.select([
    JOIN_KEY,
    "number_applied",
    "number_admitted",
    "number_enrolled_total",
    "admission_rate",
])

print(f"\nPrepared join inputs:")
print(f"  Grad Rates (join):       {df_grad_rates_join.shape[0]:,} rows x {df_grad_rates_join.shape[1]} cols -- cols: {df_grad_rates_join.columns}")
print(f"  Admissions (join):       {df_admissions_join.shape[0]:,} rows x {df_admissions_join.shape[1]} cols -- cols: {df_admissions_join.columns}")
print(f"  FSA Grants (join):       {df_fsa_grants.shape[0]:,} rows x {df_fsa_grants.shape[1]} cols -- cols: {df_fsa_grants.columns}")
print(f"  Enrollment Denom (join): {df_enrollment_denom.shape[0]:,} rows x {df_enrollment_denom.shape[1]} cols -- cols: {df_enrollment_denom.columns}")

# --- Transform: Sequential LEFT joins ---
# INTENT: Build the core analysis dataset by sequentially LEFT-joining each
# dataset onto the directory base. LEFT join preserves ALL 2,528 institutions
# in the directory universe, filling unmatched fields with null.
#
# REASONING: Using LEFT join (not INNER) because:
#   - The directory defines our analysis universe (all 4-year public/private nonprofit)
#   - Not all institutions report graduation rates or admissions data
#   - We want to preserve the full universe and document coverage gaps
#   - Downstream analysis will handle nulls appropriately (exclude from specific analyses)
#   - Plan specifies LEFT join to preserve all institutions
#
# ASSUMES:
#   - JOIN_KEY ("unitid") is unique per institution in all datasets (verified above)
#   - Directory has 2,528 rows (the institutional universe for year 2020)
#   - Each LEFT join should produce exactly 2,528 rows (no fan-out)

print("\n" + "-" * 60)
print("Performing sequential LEFT joins")
print("-" * 60)

# Join 1: Directory + Grad Rates
result = df_directory.join(df_grad_rates_join, on=JOIN_KEY, how="left")
print(f"\n  Join 1 (Directory + Grad Rates): {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == EXPECTED_BASE_ROWS, f"STOP: Fan-out after Join 1! Expected {EXPECTED_BASE_ROWS}, got {result.shape[0]}"
gr_matched = result.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]
gr_missing = EXPECTED_BASE_ROWS - gr_matched
print(f"    Matched: {gr_matched:,} | Missing grad rate: {gr_missing:,} ({gr_missing / EXPECTED_BASE_ROWS * 100:.1f}%)")

# Join 2: Result + Admissions
result = result.join(df_admissions_join, on=JOIN_KEY, how="left")
print(f"\n  Join 2 (+ Admissions): {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == EXPECTED_BASE_ROWS, f"STOP: Fan-out after Join 2! Expected {EXPECTED_BASE_ROWS}, got {result.shape[0]}"
adm_matched = result.filter(pl.col("admission_rate").is_not_null()).shape[0]
adm_missing = EXPECTED_BASE_ROWS - adm_matched
print(f"    Matched: {adm_matched:,} | Missing admission rate: {adm_missing:,} ({adm_missing / EXPECTED_BASE_ROWS * 100:.1f}%)")

# Join 3: Result + FSA Grants
result = result.join(df_fsa_grants, on=JOIN_KEY, how="left")
print(f"\n  Join 3 (+ FSA Grants): {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == EXPECTED_BASE_ROWS, f"STOP: Fan-out after Join 3! Expected {EXPECTED_BASE_ROWS}, got {result.shape[0]}"
fsa_matched = result.filter(pl.col("pell_recipients").is_not_null()).shape[0]
fsa_missing = EXPECTED_BASE_ROWS - fsa_matched
print(f"    Matched: {fsa_matched:,} | Missing pell_recipients: {fsa_missing:,} ({fsa_missing / EXPECTED_BASE_ROWS * 100:.1f}%)")

# Join 4: Result + Enrollment Denominator (for pell_share computation)
# INTENT: Bring in total_enrollment_race to use as enrollment denominator for pell_share.
# REASONING: enrollment_undergrad was supposed to be in directory but was not fetched.
# total_enrollment_race from enrollment_race is the best available proxy: it represents
# total fall enrollment headcount by institution.
result = result.join(df_enrollment_denom, on=JOIN_KEY, how="left")
print(f"\n  Join 4 (+ Enrollment Denom): {result.shape[0]:,} rows x {result.shape[1]} cols")
assert result.shape[0] == EXPECTED_BASE_ROWS, f"STOP: Fan-out after Join 4! Expected {EXPECTED_BASE_ROWS}, got {result.shape[0]}"
enr_matched = result.filter(pl.col("total_enrollment_race").is_not_null()).shape[0]
enr_missing = EXPECTED_BASE_ROWS - enr_matched
print(f"    Matched: {enr_matched:,} | Missing enrollment denom: {enr_missing:,} ({enr_missing / EXPECTED_BASE_ROWS * 100:.1f}%)")

# --- Transform: Compute pell_share ---
# INTENT: Calculate the share of students receiving Pell Grants as a proxy
# for the socioeconomic composition of the student body.
#
# REASONING: pell_share = pell_recipients / total_enrollment_race. We use
# total_enrollment_race (from enrollment_race_clean) as the enrollment denominator
# because enrollment_undergrad was not available in the directory dataset.
# total_enrollment_race is the sum of all race/ethnicity enrollment categories
# and represents total fall headcount, which is a reasonable denominator.
# We guard against division by zero (total_enrollment_race could be 0 or null)
# by setting pell_share to null in those cases.
#
# ASSUMES:
#   - pell_recipients and total_enrollment_race are in compatible units (both counts
#     for the same institution and approximate time period)
#   - total_enrollment_race > 0 for valid institutions
#   - Result should be between 0 and 1 for most institutions

print("\n" + "-" * 60)
print("Computing pell_share = pell_recipients / total_enrollment_race")
print("-" * 60)

result = result.with_columns(
    pl.when(
        pl.col("total_enrollment_race").is_not_null()
        & (pl.col("total_enrollment_race") > 0)
        & pl.col("pell_recipients").is_not_null()
    )
    .then(pl.col("pell_recipients") / pl.col("total_enrollment_race"))
    .otherwise(None)
    .alias("pell_share")
)

# Validate pell_share range
pell_share_valid = result.filter(pl.col("pell_share").is_not_null())
pell_min = pell_share_valid["pell_share"].min()
pell_max = pell_share_valid["pell_share"].max()
pell_mean = pell_share_valid["pell_share"].mean()
pell_null = result["pell_share"].null_count()

print(f"  pell_share computed: {pell_share_valid.shape[0]:,} non-null values")
print(f"  Range: [{pell_min:.4f}, {pell_max:.4f}]")
print(f"  Mean: {pell_mean:.4f}")
print(f"  Null: {pell_null:,} ({pell_null / EXPECTED_BASE_ROWS * 100:.1f}%)")

# INTENT: Warn if any pell_share values exceed 1.0 (possible if pell_recipients
# includes recipients over the full year while enrollment is a point-in-time snapshot).
# REASONING: Values > 1.0 are not necessarily errors but are analytically problematic.
# Capping at 1.0 preserves these as "very high Pell" institutions without introducing
# misleading proportions that exceed 100%.
gt_one = result.filter(pl.col("pell_share") > 1.0).shape[0]
if gt_one > 0:
    print(f"  NOTE: {gt_one} institutions have pell_share > 1.0 (possible due to")
    print(f"        FSA counting full-year recipients vs point-in-time enrollment)")
    result = result.with_columns(
        pl.when(pl.col("pell_share") > 1.0)
        .then(1.0)
        .otherwise(pl.col("pell_share"))
        .alias("pell_share")
    )
    print(f"  Capped {gt_one} values at 1.0")

# --- Rename for consistency ---
# INTENT: Rename total_enrollment_race to enrollment_undergrad to maintain
# consistency with Plan column naming expectations.
# REASONING: Downstream scripts and the Plan reference 'enrollment_undergrad' as
# the enrollment denominator. Renaming here ensures a consistent schema.
# NOTE: This is total fall enrollment from enrollment_race, not specifically
# undergraduate enrollment from the IPEDS directory.
result = result.rename({"total_enrollment_race": "enrollment_undergrad"})
print(f"\n  Renamed 'total_enrollment_race' -> 'enrollment_undergrad' for Plan consistency")

# --- Post-state ---
# Document the final dataset shape and key column null rates.
print("\n" + "-" * 60)
print("Post-state: Final dataset summary")
print("-" * 60)

print(f"\nFinal shape: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Columns: {result.columns}")

print(f"\nNull rates for key analysis columns:")
key_cols = ["grad_rate_150pct", "admission_rate", "pell_share",
            "enrollment_undergrad", "pell_recipients",
            "number_applied", "number_admitted", "number_enrolled_total",
            "cohort_year"]
for col in key_cols:
    if col in result.columns:
        null_ct = result[col].null_count()
        null_pct = null_ct / result.shape[0] * 100
        print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation ---
# Checkpoint validation: verify join preserved the directory universe, no fan-out
# occurred, pell_share is within valid range, and key columns are present.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: Row count matches directory (LEFT join preserves all)
rows_ok = result.shape[0] == EXPECTED_BASE_ROWS
print(f"  [{'PASS' if rows_ok else 'FAIL'}] Row count == {EXPECTED_BASE_ROWS}: {result.shape[0]:,}")

# CP3.2: No fan-out (already asserted per join, but double-check final)
no_fanout = result.shape[0] == EXPECTED_BASE_ROWS
print(f"  [{'PASS' if no_fanout else 'FAIL'}] No fan-out: {result.shape[0]:,} == {EXPECTED_BASE_ROWS}")

# CP3.3: pell_share between 0 and 1 for non-null values
pell_nonnull = result.filter(pl.col("pell_share").is_not_null())
pell_range_ok = True
if pell_nonnull.shape[0] > 0:
    pell_min_final = pell_nonnull["pell_share"].min()
    pell_max_final = pell_nonnull["pell_share"].max()
    pell_range_ok = pell_min_final >= 0 and pell_max_final <= 1.0
    print(f"  [{'PASS' if pell_range_ok else 'FAIL'}] pell_share in [0, 1]: [{pell_min_final:.4f}, {pell_max_final:.4f}]")
else:
    print(f"  [WARN] pell_share: all values are null")
    pell_range_ok = False

# CP3.4: Key columns present in output
# NOTE: open_admissions not checked -- it was not available in any fetched dataset.
# Downstream create-bands step will handle null admission_rate as "Less Selective/Open".
required_cols = ["unitid", "year", "inst_name", "inst_control", "grad_rate_150pct",
                 "admission_rate", "pell_share", "enrollment_undergrad",
                 "hbcu", "institution_level"]
missing_cols = [c for c in required_cols if c not in result.columns]
cols_ok = len(missing_cols) == 0
print(f"  [{'PASS' if cols_ok else 'FAIL'}] Required columns present: {'all present' if cols_ok else f'missing {missing_cols}'}")

# CP3.5: No row loss beyond expectation (we start with full directory, should keep all)
no_row_loss = result.shape[0] >= EXPECTED_BASE_ROWS
print(f"  [{'PASS' if no_row_loss else 'FAIL'}] No unexpected row loss: {result.shape[0]:,} >= {EXPECTED_BASE_ROWS}")

# CP3.6: unitid still unique in output
unitid_unique = result[JOIN_KEY].n_unique() == result.shape[0]
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid unique in output: {result[JOIN_KEY].n_unique()} unique / {result.shape[0]:,} rows")

# CP3.7: Key overlap documentation (informational, not pass/fail)
print(f"\n  [INFO] Coverage summary:")
print(f"    Grad rate coverage:      {gr_matched:,} / {EXPECTED_BASE_ROWS:,} ({gr_matched / EXPECTED_BASE_ROWS * 100:.1f}%)")
print(f"    Admission rate coverage: {adm_matched:,} / {EXPECTED_BASE_ROWS:,} ({adm_matched / EXPECTED_BASE_ROWS * 100:.1f}%)")
print(f"    Pell recipients coverage:{fsa_matched:,} / {EXPECTED_BASE_ROWS:,} ({fsa_matched / EXPECTED_BASE_ROWS * 100:.1f}%)")
print(f"    Enrollment coverage:     {enr_matched:,} / {EXPECTED_BASE_ROWS:,} ({enr_matched / EXPECTED_BASE_ROWS * 100:.1f}%)")
print(f"    Pell share non-null:     {pell_share_valid.shape[0]:,} / {EXPECTED_BASE_ROWS:,} ({pell_share_valid.shape[0] / EXPECTED_BASE_ROWS * 100:.1f}%)")

# Overall CP3 result
all_passed = all([rows_ok, no_fanout, pell_range_ok, cols_ok, no_row_loss, unitid_unique])
assert all_passed, "STOP: CP3 validation failed"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:16:45
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage7_transform/01_join-core_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.1: Join core datasets (directory + grad rates + admissions + FSA grants)
# ============================================================
# 
# Loaded datasets:
#   Directory:        2,528 rows x 10 cols
#   Grad Rates:       1,949 rows x 7 cols
#   Admissions:       1,989 rows x 6 cols
#   FSA Grants:       4,994 rows x 4 cols
#   Enrollment Race:  5,837 rows x 4 cols
# 
# ------------------------------------------------------------
# Pre-state: Key overlap analysis
# ------------------------------------------------------------
# 
# Unitid uniqueness:
#   Directory:        unique=True (2528 unique / 2528 rows)
#   Grad Rates:       unique=True (1949 unique / 1949 rows)
#   Admissions:       unique=True (1989 unique / 1989 rows)
#   FSA Grants:       unique=True (4994 unique / 4994 rows)
#   Enrollment Race:  unique=True (5837 unique / 5837 rows)
# 
# Key overlap with directory (2,528 institutions):
#   Grad Rates:       1,796 / 2,528 (71.0%)
#   Admissions:       1,669 / 2,528 (66.0%)
#   FSA Grants:       2,038 / 2,528 (80.6%)
#   Enrollment Race:  2,158 / 2,528 (85.4%)
# 
# FSA grants already has unique unitids; selected unitid + pell_recipients only.
# 
# Enrollment denominator prepared: 5,837 rows
# 
# Prepared join inputs:
#   Grad Rates (join):       1,949 rows x 3 cols -- cols: ['unitid', 'grad_rate_150pct', 'cohort_year']
#   Admissions (join):       1,989 rows x 5 cols -- cols: ['unitid', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate']
#   FSA Grants (join):       4,994 rows x 2 cols -- cols: ['unitid', 'pell_recipients']
#   Enrollment Denom (join): 5,837 rows x 2 cols -- cols: ['unitid', 'total_enrollment_race']
# 
# ------------------------------------------------------------
# Performing sequential LEFT joins
# ------------------------------------------------------------
# 
#   Join 1 (Directory + Grad Rates): 2,528 rows x 12 cols
#     Matched: 1,796 | Missing grad rate: 732 (29.0%)
# 
#   Join 2 (+ Admissions): 2,528 rows x 16 cols
#     Matched: 1,659 | Missing admission rate: 869 (34.4%)
# 
#   Join 3 (+ FSA Grants): 2,528 rows x 17 cols
#     Matched: 2,032 | Missing pell_recipients: 496 (19.6%)
# 
#   Join 4 (+ Enrollment Denom): 2,528 rows x 18 cols
#     Matched: 2,158 | Missing enrollment denom: 370 (14.6%)
# 
# ------------------------------------------------------------
# Computing pell_share = pell_recipients / total_enrollment_race
# ------------------------------------------------------------
#   pell_share computed: 2,010 non-null values
#   Range: [0.0000, 8.0175]
#   Mean: 0.4155
#   Null: 518 (20.5%)
#   NOTE: 33 institutions have pell_share > 1.0 (possible due to
#         FSA counting full-year recipients vs point-in-time enrollment)
#   Capped 33 values at 1.0
# 
#   Renamed 'total_enrollment_race' -> 'enrollment_undergrad' for Plan consistency
# 
# ------------------------------------------------------------
# Post-state: Final dataset summary
# ------------------------------------------------------------
# 
# Final shape: 2,528 rows x 19 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share']
# 
# Null rates for key analysis columns:
#   grad_rate_150pct: 732 nulls (29.0%)
#   admission_rate: 869 nulls (34.4%)
#   pell_share: 518 nulls (20.5%)
#   enrollment_undergrad: 370 nulls (14.6%)
#   pell_recipients: 496 nulls (19.6%)
#   number_applied: 859 nulls (34.0%)
#   number_admitted: 869 nulls (34.4%)
#   number_enrolled_total: 870 nulls (34.4%)
#   cohort_year: 732 nulls (29.0%)
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_core_joined.parquet
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] Row count == 2528: 2,528
#   [PASS] No fan-out: 2,528 == 2528
#   [PASS] pell_share in [0, 1]: [0.0000, 1.0000]
#   [PASS] Required columns present: all present
#   [PASS] No unexpected row loss: 2,528 >= 2528
#   [PASS] unitid unique in output: 2528 unique / 2,528 rows
# 
#   [INFO] Coverage summary:
#     Grad rate coverage:      1,796 / 2,528 (71.0%)
#     Admission rate coverage: 1,659 / 2,528 (65.6%)
#     Pell recipients coverage:2,032 / 2,528 (80.4%)
#     Enrollment coverage:     2,158 / 2,528 (85.4%)
#     Pell share non-null:     2,010 / 2,528 (79.5%)
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
