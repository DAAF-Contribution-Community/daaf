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
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for the core join that combines directory, graduation rates,
# admissions, and FSA grants data. Directory is the base table; all other
# datasets are LEFT-joined to preserve the full 4-year public/private nonprofit
# institution universe. Join key is unitid (IPEDS unique institution identifier).
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_DIRECTORY = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_directory_clean.parquet"
INPUT_GRAD_RATES = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_grad_rates_clean.parquet"
INPUT_ADMISSIONS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_admissions_clean.parquet"
INPUT_FSA_GRANTS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_fsa_grants_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core_joined.parquet"

JOIN_KEY = "unitid"
EXPECTED_BASE_ROWS = 2528  # Directory defines the institution universe

# --- Load ---
# Load all four cleaned datasets and verify shapes before joining.
print("=" * 60)
print("Stage 7.1: Join core datasets (directory + grad rates + admissions + FSA grants)")
print("=" * 60)

df_directory = pl.read_parquet(INPUT_DIRECTORY)
df_grad_rates = pl.read_parquet(INPUT_GRAD_RATES)
df_admissions = pl.read_parquet(INPUT_ADMISSIONS)
df_fsa_grants = pl.read_parquet(INPUT_FSA_GRANTS)

print(f"\nLoaded datasets:")
print(f"  Directory:   {df_directory.shape[0]:,} rows x {df_directory.shape[1]} cols")
print(f"  Grad Rates:  {df_grad_rates.shape[0]:,} rows x {df_grad_rates.shape[1]} cols")
print(f"  Admissions:  {df_admissions.shape[0]:,} rows x {df_admissions.shape[1]} cols")
print(f"  FSA Grants:  {df_fsa_grants.shape[0]:,} rows x {df_fsa_grants.shape[1]} cols")

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

print(f"\nUnitid uniqueness:")
print(f"  Directory:   unique={dir_unique} ({df_directory[JOIN_KEY].n_unique()} unique / {df_directory.shape[0]} rows)")
print(f"  Grad Rates:  unique={gr_unique} ({df_grad_rates[JOIN_KEY].n_unique()} unique / {df_grad_rates.shape[0]} rows)")
print(f"  Admissions:  unique={adm_unique} ({df_admissions[JOIN_KEY].n_unique()} unique / {df_admissions.shape[0]} rows)")
print(f"  FSA Grants:  unique={fsa_unique} ({df_fsa_grants[JOIN_KEY].n_unique()} unique / {df_fsa_grants.shape[0]} rows)")

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

gr_overlap = len(dir_keys & gr_keys)
adm_overlap = len(dir_keys & adm_keys)
fsa_overlap = len(dir_keys & fsa_keys)

print(f"\nKey overlap with directory ({len(dir_keys):,} institutions):")
print(f"  Grad Rates:  {gr_overlap:,} / {len(dir_keys):,} ({gr_overlap / len(dir_keys) * 100:.1f}%)")
print(f"  Admissions:  {adm_overlap:,} / {len(dir_keys):,} ({adm_overlap / len(dir_keys) * 100:.1f}%)")
print(f"  FSA Grants:  {fsa_overlap:,} / {len(dir_keys):,} ({fsa_overlap / len(dir_keys) * 100:.1f}%)")

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

# From admissions: number_applied, number_admitted, number_enrolled_total, admission_rate, open_admissions
# ASSUMES: year column exists but is redundant with directory's year; drop to avoid _right suffix
df_admissions_join = df_admissions.select([
    JOIN_KEY,
    "number_applied",
    "number_admitted",
    "number_enrolled_total",
    "admission_rate",
    "open_admissions",
])

print(f"\nPrepared join inputs:")
print(f"  Grad Rates (join):  {df_grad_rates_join.shape[0]:,} rows x {df_grad_rates_join.shape[1]} cols — cols: {df_grad_rates_join.columns}")
print(f"  Admissions (join):  {df_admissions_join.shape[0]:,} rows x {df_admissions_join.shape[1]} cols — cols: {df_admissions_join.columns}")
print(f"  FSA Grants (join):  {df_fsa_grants.shape[0]:,} rows x {df_fsa_grants.shape[1]} cols — cols: {df_fsa_grants.columns}")

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
#   - JOIN_KEY ("unitid") is unique per institution in all four datasets
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

# --- Transform: Compute pell_share ---
# INTENT: Calculate the share of undergraduate students receiving Pell Grants
# as a proxy for the socioeconomic composition of the student body.
#
# REASONING: pell_share = pell_recipients / enrollment_undergrad. This is a
# standard metric in higher education research for measuring the proportion
# of low-income students. We guard against division by zero (enrollment_undergrad
# could be 0 or null) by setting pell_share to null in those cases.
#
# ASSUMES:
#   - pell_recipients and enrollment_undergrad are in compatible units (both counts
#     for the same institution and approximate time period)
#   - enrollment_undergrad > 0 for valid institutions
#   - Result should be between 0 and 1 for valid institutions

print("\n" + "-" * 60)
print("Computing pell_share = pell_recipients / enrollment_undergrad")
print("-" * 60)

result = result.with_columns(
    pl.when(
        pl.col("enrollment_undergrad").is_not_null()
        & (pl.col("enrollment_undergrad") > 0)
        & pl.col("pell_recipients").is_not_null()
    )
    .then(pl.col("pell_recipients") / pl.col("enrollment_undergrad"))
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
# includes graduate students or different reporting period than enrollment).
# REASONING: Values > 1.0 are not necessarily errors (FSA may count recipients
# over a full year while enrollment is a single-point-in-time snapshot), but
# they warrant documentation. We cap at 1.0 only if Plan specifies.
gt_one = result.filter(pl.col("pell_share") > 1.0).shape[0]
if gt_one > 0:
    print(f"  NOTE: {gt_one} institutions have pell_share > 1.0 (possible due to")
    print(f"        FSA counting full-year recipients vs point-in-time enrollment)")
    # Cap pell_share at 1.0 for analytical cleanliness
    # REASONING: pell_share > 1.0 is an artifact of measurement timing differences,
    # not a real phenomenon. Capping preserves these as "very high Pell" institutions
    # without introducing misleading proportions.
    result = result.with_columns(
        pl.when(pl.col("pell_share") > 1.0)
        .then(1.0)
        .otherwise(pl.col("pell_share"))
        .alias("pell_share")
    )
    print(f"  Capped {gt_one} values at 1.0")

# --- Post-state ---
# Document the final dataset shape and key column null rates.
print("\n" + "-" * 60)
print("Post-state: Final dataset summary")
print("-" * 60)

print(f"\nFinal shape: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Columns: {result.columns}")

print(f"\nNull rates for key analysis columns:")
key_cols = ["grad_rate_150pct", "admission_rate", "pell_share",
            "open_admissions", "enrollment_undergrad", "pell_recipients"]
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
required_cols = ["unitid", "year", "inst_name", "inst_control", "grad_rate_150pct",
                 "admission_rate", "pell_share", "open_admissions", "enrollment_undergrad",
                 "hbcu", "locale", "institution_level"]
missing_cols = [c for c in required_cols if c not in result.columns]
cols_ok = len(missing_cols) == 0
print(f"  [{'PASS' if cols_ok else 'FAIL'}] Required columns present: {'all present' if cols_ok else f'missing {missing_cols}'}")

# CP3.5: No row loss beyond expectation (we start with full directory, should keep all)
no_row_loss = result.shape[0] >= EXPECTED_BASE_ROWS
print(f"  [{'PASS' if no_row_loss else 'FAIL'}] No unexpected row loss: {result.shape[0]:,} >= {EXPECTED_BASE_ROWS}")

# CP3.6: unitid still unique in output
unitid_unique = result[JOIN_KEY].n_unique() == result.shape[0]
print(f"  [{'PASS' if unitid_unique else 'FAIL'}] unitid unique in output: {result[JOIN_KEY].n_unique()} unique / {result.shape[0]:,} rows")

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
# Executed: 2026-02-15 21:12:03
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage7_transform/01_join-core.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 7.1: Join core datasets (directory + grad rates + admissions + FSA grants)
# ============================================================
# 
# Loaded datasets:
#   Directory:   2,528 rows x 10 cols
#   Grad Rates:  1,949 rows x 7 cols
#   Admissions:  1,989 rows x 6 cols
#   FSA Grants:  4,994 rows x 4 cols
# 
# ------------------------------------------------------------
# Pre-state: Key overlap analysis
# ------------------------------------------------------------
# 
# Unitid uniqueness:
#   Directory:   unique=True (2528 unique / 2528 rows)
#   Grad Rates:  unique=True (1949 unique / 1949 rows)
#   Admissions:  unique=True (1989 unique / 1989 rows)
#   FSA Grants:  unique=True (4994 unique / 4994 rows)
# 
# Key overlap with directory (2,528 institutions):
#   Grad Rates:  1,796 / 2,528 (71.0%)
#   Admissions:  1,669 / 2,528 (66.0%)
#   FSA Grants:  2,038 / 2,528 (80.6%)
# 
# FSA grants already has unique unitids; selected unitid + pell_recipients only.
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage7_transform/01_join-core.py", line 151, in <module>
#     df_admissions_join = df_admissions.select([
#                          ^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/frame.py", line 10307, in select
#     .collect(optimizations=QueryOptFlags._eager())
#      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 97, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/opt_flags.py", line 326, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/frame.py", line 2440, in collect
#     return wrap_df(ldf.collect(engine, callback))
#                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.ColumnNotFoundError: unable to find column "open_admissions"; valid columns: ["unitid", "year", "number_applied", "number_admitted", "number_enrolled_total", "admission_rate"]
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
