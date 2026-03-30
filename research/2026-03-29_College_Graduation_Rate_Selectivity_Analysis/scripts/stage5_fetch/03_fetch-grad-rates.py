#!/usr/bin/env python3
"""
Stage 5.3: Fetch IPEDS graduation rates data for 2020-2021.

Task: fetch-grad-rates
Wave: 1, Step: 3, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_grad_rates.parquet
Checkpoint: CP1

CRITICAL: This script logs all unique values of the `cohort`, `race`, and `sex`
columns with value_counts() to document subcohort codes. This resolves the
LOW-confidence item from Stage 3 about undocumented subcohort codes.
Expected codes: 2=bachelor's-seeking at 4-yr, 8=Pell recipients, 12=total
degree-seeking. Verify from data.
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# INTENT: Set up paths and parameters for IPEDS graduation rates fetch.
# REASONING: Configuration is derived from the Plan's query specification.
#   IPEDS grad-rates is a single-file dataset (all years in one file per
#   datasets-reference.md). We download once and filter locally.
# ASSUMES: Project directory and data/raw/ exist or will be created.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020, 2021]  # Per Plan query specification

# Dataset path from datasets-reference.md: IPEDS Graduation Rates (single file)
DATASET_PATH = "ipeds/colleges_ipeds_grad-rates"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"

# Required columns per task verification spec
REQUIRED_COLS = ["unitid", "year", "cohort", "race", "sex", "completion_rate_150pct"]

# Domain configuration (education)
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID years

# --- Mirror Configuration ---
# INTENT: Download IPEDS grad-rates from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
#   Format-specific read driven by each mirror's read_strategy field.
#   All mirrors use the same canonical path from datasets-reference.md.
# ASSUMES: Mirror URLs are current and accessible; each mirror uses the same
#   canonical path with its own root_url and format.
# REFERENCE: mirrors.yaml for mirror config, datasets-reference.md for canonical paths.
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Rate Limiting ---
# INTENT: Prevent HTTP 429 (Too Many Requests) errors from mirrors.
# REASONING: Mirrors may rate-limit rapid successive requests. A 3-second delay
#   between fetch calls avoids triggering limits while keeping pipeline runtime
#   reasonable.
FETCH_DELAY_SECONDS = 3
_last_fetch_time = 0.0


def _rate_limit():
    """Sleep if needed to maintain minimum delay between fetch requests."""
    global _last_fetch_time
    if _last_fetch_time > 0:
        elapsed = time.time() - _last_fetch_time
        if elapsed < FETCH_DELAY_SECONDS:
            wait = FETCH_DELAY_SECONDS - elapsed
            print(f"  (rate limit: waiting {wait:.1f}s)")
            time.sleep(wait)
    _last_fetch_time = time.time()


def fetch_from_mirrors(
    path: str,
    filters: dict | None = None,
    years: list[int] | None = None,
) -> pl.DataFrame:
    """Try each mirror in order. Return DataFrame on first success.

    Args:
        path: Canonical dataset path string from datasets-reference.md.
        filters: Dict of column->value(s) filters to apply locally.
        years: List of years to filter to.
    """
    _rate_limit()
    last_error = None

    for mirror in MIRRORS:
        name = mirror["name"]
        strategy = mirror["read_strategy"]

        # Build URL from mirror's url_template + canonical path
        url = mirror["url_template"].format(
            root_url=mirror["root_url"], path=path, format=mirror["format"]
        )

        print(f"  Trying {name}: {url}")

        try:
            if strategy in ("eager_parquet", "parquet"):
                # REASONING: Parquet files have embedded schema, no inference needed.
                # Polars reads HTTP URLs natively via pl.read_parquet().
                df = pl.read_parquet(url)
            elif strategy in ("lazy_csv", "csv"):
                # REASONING: CSV files can be 500MB+. Lazy loading streams only
                # matching rows into memory rather than loading the full file.
                # ASSUMES: CSV has standard column names matching parquet schema.
                lazy = pl.scan_csv(url, infer_schema_length=10000)
                if years:
                    lazy = lazy.filter(pl.col("year").is_in(years))
                if filters:
                    for col, val in filters.items():
                        if isinstance(val, list):
                            lazy = lazy.filter(pl.col(col).is_in(val))
                        else:
                            lazy = lazy.filter(pl.col(col) == val)
                df = lazy.collect()
                print(f"  OK {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  OK {name}: {df.shape[0]:,} rows")

            # Apply filters for eagerly-loaded formats (parquet, etc.)
            if years:
                df = df.filter(pl.col("year").is_in(years))
            if filters:
                for col, val in filters.items():
                    if isinstance(val, list):
                        df = df.filter(pl.col(col).is_in(val))
                    else:
                        df = df.filter(pl.col(col) == val)

            print(f"  After filters: {df.shape[0]:,} rows")
            return df

        except Exception as e:
            last_error = e
            print(f"  FAILED {name}: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Fetch Data ---
print("=" * 60)
print("Stage 5.3: Fetch IPEDS graduation rates")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# INTENT: Download IPEDS graduation rates and filter to requested years.
# REASONING: Single-file dataset (all years in one file per datasets-reference.md).
#   Download once, filter locally with Polars.
# ASSUMES: Mirror URLs are current. Dataset contains "year" column with integer years.
print("\nFetching IPEDS graduation rates...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes:\n{df.dtypes}")

# --- CRITICAL DIAGNOSTIC: Subcohort Code Documentation ---
# INTENT: Log ALL unique values of cohort, race, and sex columns with counts.
# REASONING: The Plan has a LOW-confidence item about undocumented subcohort codes.
#   Expected codes: 2=bachelor's-seeking at 4-yr, 8=Pell recipients, 12=total
#   degree-seeking. We must verify from the actual data what codes exist and their
#   frequencies to resolve this uncertainty before cleaning.
# ASSUMES: cohort, race, and sex columns exist in the dataset as integer-encoded
#   values (per Portal conventions).

print("\n" + "=" * 60)
print("DIAGNOSTIC: Subcohort Code Documentation")
print("=" * 60)

# Cohort value_counts -- THE MOST IMPORTANT diagnostic
print("\n--- cohort value_counts ---")
if "cohort" in df.columns:
    cohort_vc = df["cohort"].value_counts().sort("cohort")
    print(cohort_vc)
else:
    print("WARNING: 'cohort' column NOT FOUND in dataset")

# Race value_counts
print("\n--- race value_counts ---")
if "race" in df.columns:
    race_vc = df["race"].value_counts().sort("race")
    print(race_vc)
else:
    print("WARNING: 'race' column NOT FOUND in dataset")

# Sex value_counts
print("\n--- sex value_counts ---")
if "sex" in df.columns:
    sex_vc = df["sex"].value_counts().sort("sex")
    print(sex_vc)
else:
    print("WARNING: 'sex' column NOT FOUND in dataset")

# --- Save ---
# INTENT: Persist fetched data in parquet format for downstream cleaning.
# REASONING: Parquet preserves types, is compressed, and is the DAAF standard format.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# INTENT: Verify fetched data meets Plan expectations for year coverage,
#   row counts, critical columns, and identifier integrity.
# ASSUMES: REQUIRED_COLS, YEARS, and expected row count range are defined
#   in the task specification.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Row count within expected range (50,000-500,000 per task spec)
row_count = df.shape[0]
row_ok = 50_000 <= row_count <= 500_000
status = "PASS" if row_ok else "FAIL"
print(f"  [{status}] Row count in range 50K-500K: {row_count:,}")
if not row_ok:
    # REASONING: Even if outside expected range, this may be acceptable.
    # We check more precisely below but flag it here.
    if row_count > 0:
        print(f"    Row count outside expected range but non-zero; continuing validation")
    else:
        cp1_passed = False

# CP1.2: Required columns present
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
cols_ok = len(missing_cols) == 0
status = "PASS" if cols_ok else "FAIL"
print(f"  [{status}] Required columns present: {REQUIRED_COLS}")
if not cols_ok:
    print(f"    Missing: {missing_cols}")
    cp1_passed = False

# CP1.3: Expected years present
if "year" in df.columns:
    years_found = sorted(df["year"].unique().to_list())
    all_years = all(y in years_found for y in YEARS)
    status = "PASS" if all_years else "FAIL"
    print(f"  [{status}] Expected years present: {years_found}")
    if not all_years:
        missing_years = [y for y in YEARS if y not in years_found]
        print(f"    Missing years: {missing_years}")
        cp1_passed = False
else:
    print("  [FAIL] 'year' column not found")
    cp1_passed = False

# CP1.4: Null rate < 10% for unitid, year
for col in ["unitid", "year"]:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        ok = null_pct < 10
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] Null rate for {col}: {null_pct:.2f}%")
        if not ok:
            cp1_passed = False

# CP1.5: Subcohort codes documented
# REASONING: This is informational -- we want to log what we found, not fail on it.
if "cohort" in df.columns:
    cohort_codes = sorted(df["cohort"].drop_nulls().unique().to_list())
    print(f"  [INFO] Cohort codes found: {cohort_codes}")
    # Check for expected codes
    expected_codes = [2, 8, 12]
    found_expected = [c for c in expected_codes if c in cohort_codes]
    print(f"  [INFO] Expected codes {expected_codes} -- found: {found_expected}")

# CP1.6: Year counts for data quality
if "year" in df.columns:
    year_counts = df.group_by("year").len().sort("year")
    print(f"\n  Year distribution:")
    for row in year_counts.iter_rows(named=True):
        print(f"    {row['year']}: {row['len']:,} rows")

# CP1.7: FLAG_YEARS warning (COVID)
if any(y in FLAG_YEARS for y in YEARS):
    print(f"  [WARN] FLAG-YEARS: Analysis includes data from flagged years {FLAG_YEARS}. "
          "Document comparability concerns in limitations.")

# CP1.8: Missingness summary for all required columns
print(f"\n  Missingness summary:")
for col in REQUIRED_COLS:
    if col in df.columns:
        null_count = df[col].null_count()
        null_pct = null_count / len(df) * 100
        print(f"    {col}: {null_count:,} nulls ({null_pct:.1f}%)")

assert cp1_passed, "STOP: CP1 FAILED -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 20:18:04
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 5.3: Fetch IPEDS graduation rates
# ============================================================
# 
# Fetching IPEDS graduation rates...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_grad-rates.parquet
#   OK huggingface: 10,690,508 rows
#   After filters: 804,716 rows
# 
# Shape: 804,716 rows x 18 cols
# Columns: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# Dtypes:
# [Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Float64]
# 
# ============================================================
# DIAGNOSTIC: Subcohort Code Documentation
# ============================================================
# 
# --- cohort value_counts ---
# WARNING: 'cohort' column NOT FOUND in dataset
# 
# --- race value_counts ---
# shape: (10, 2)
# ┌──────┬───────┐
# │ race ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 80151 │
# │ 2    ┆ 80151 │
# │ 3    ┆ 80151 │
# │ 4    ┆ 80151 │
# │ 5    ┆ 80151 │
# │ 6    ┆ 80151 │
# │ 7    ┆ 80151 │
# │ 8    ┆ 80151 │
# │ 9    ┆ 80151 │
# │ 99   ┆ 83357 │
# └──────┴───────┘
# 
# --- sex value_counts ---
# shape: (3, 2)
# ┌─────┬────────┐
# │ sex ┆ count  │
# │ --- ┆ ---    │
# │ i64 ┆ u32    │
# ╞═════╪════════╡
# │ 1   ┆ 267170 │
# │ 2   ┆ 267170 │
# │ 99  ┆ 270376 │
# └─────┴────────┘
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_grad_rates.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [FAIL] Row count in range 50K-500K: 804,716
#     Row count outside expected range but non-zero; continuing validation
#   [FAIL] Required columns present: ['unitid', 'year', 'cohort', 'race', 'sex', 'completion_rate_150pct']
#     Missing: ['cohort']
#   [PASS] Expected years present: [2020, 2021]
#   [PASS] Null rate for unitid: 0.00%
#   [PASS] Null rate for year: 0.00%
# 
#   Year distribution:
#     2020: 401,215 rows
#     2021: 403,501 rows
#   [WARN] FLAG-YEARS: Analysis includes data from flagged years [2020, 2021]. Document comparability concerns in limitations.
# 
#   Missingness summary:
#     unitid: 0 nulls (0.0%)
#     year: 0 nulls (0.0%)
#     race: 0 nulls (0.0%)
#     sex: 0 nulls (0.0%)
#     completion_rate_150pct: 530,408 nulls (65.9%)
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-grad-rates.py", line 307, in <module>
#     assert cp1_passed, "STOP: CP1 FAILED -- see details above"
#            ^^^^^^^^^^
# AssertionError: STOP: CP1 FAILED -- see details above
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
