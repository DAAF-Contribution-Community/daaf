#!/usr/bin/env python3
"""
Stage 5.7: Fetch IPEDS Fall Retention data for 2020.

Task: fetch-retention
Wave: 2, Step: 7, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_retention.parquet
Checkpoint: CP1

Notes:
- Dataset: ipeds/colleges_ipeds_fall-retention (single file, all years 2003-2020)
- Filter: year == 2020 applied locally with Polars
- Risk: retention_rate may be String dtype (per Stage 3 findings) -- logged for Stage 6
- Coded missing values (-1, -2, -3) may be present -- reported but not cleaned here
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# Data is downloaded from mirrors and filtered locally.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020]  # Per Plan query specification: year 2020 only

# Dataset path (from education-data-query datasets-reference.md)
# INTENT: Fetch IPEDS Fall Retention rates -- single file containing all years 2003-2020.
# REASONING: Single-file dataset; download once and filter locally.
# ASSUMES: Dataset contains columns: unitid, year, ftpt, retention_rate.
DATASET_PATH = "ipeds/colleges_ipeds_fall-retention"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_retention.parquet"

# Domain configuration
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID years for education data
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Mirror Configuration ---
# INTENT: Download IPEDS Fall Retention from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
#   Format-specific read driven by each mirror's read_strategy field.
#   All mirrors use the same canonical path from datasets-reference.md.
# REFERENCE: mirrors.yaml for mirror config, datasets-reference.md for canonical paths.
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Rate Limiting ---
# INTENT: Prevent HTTP 429 (Too Many Requests) errors from mirrors.
# REASONING: Mirrors may rate-limit rapid successive requests. A 3-second delay
#   between fetch calls avoids triggering limits.
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
            All mirrors use the same path -- only root_url and format differ.
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
                df = pl.read_parquet(url)
            elif strategy in ("lazy_csv", "csv"):
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
                print(f"  -> {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  -> {name}: {df.shape[0]:,} rows")

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
            print(f"  X {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Load ---
print("=" * 60)
print("Stage 5.7: Fetch IPEDS Fall Retention")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS Fall Retention dataset and filter to year 2020.
# REASONING: Single-file dataset (all years 2003-2020 in one file). Download once,
#   filter locally with Polars. This is the most efficient approach for parquet.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
#   Portal uses integer encoding for coded values (-1, -2, -3).
print("\nFetching IPEDS Fall Retention data...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"\nShape after year filter: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Detailed Logging (Critical for Stage 6) ---
# INTENT: Log dtypes, unique values of ftpt, and retention_rate dtype.
# REASONING: The risk register flags retention_rate as potentially String type.
#   This logging captures the actual dtype so Stage 6 cleaning can handle it correctly.
#   Also logging ftpt values to confirm expected categories (1=FT, 2=PT) are present.
# ASSUMES: Columns unitid, year, ftpt, retention_rate exist in the dataset.

print("\n--- Column Dtypes ---")
for col_name in df.columns:
    print(f"  {col_name}: {df[col_name].dtype}")

print(f"\n--- CRITICAL: retention_rate dtype = {df['retention_rate'].dtype} ---")

print("\n--- ftpt Unique Values ---")
ftpt_values = df["ftpt"].value_counts().sort("ftpt")
print(ftpt_values)

print("\n--- retention_rate Sample Values ---")
print(df.select("retention_rate").head(10))

# INTENT: Check for coded missing values in numeric-like columns.
# REASONING: Portal uses -1, -2, -3 as coded missing values.
#   If retention_rate is String, coded values may appear as string "-1", "-2", "-3".
#   Report their presence for Stage 6 handling.
print("\n--- Coded Missing Value Check ---")
for code in CODED_MISSING_VALUES:
    # INTENT: Check both numeric and string representations of coded values.
    # REASONING: If retention_rate is String dtype, coded values will be strings.
    # ASSUMES: Other numeric columns use standard integer encoding.
    for col_name in df.columns:
        dtype = df[col_name].dtype
        if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64):
            count = (df[col_name] == code).sum()
            if count > 0:
                print(f"  {col_name} has {count} occurrences of coded value {code}")
        elif dtype == pl.Utf8:
            count = (df[col_name] == str(code)).sum()
            if count > 0:
                print(f"  {col_name} (String) has {count} occurrences of coded value '{code}'")

# --- Save ---
# INTENT: Persist fetched data in parquet format for Stage 6 cleaning.
# REASONING: Parquet preserves dtypes including String retention_rate if applicable.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")
print(f"File size: {OUTPUT_PARQUET.stat().st_size / 1024:.1f} KB")

# --- CP1 Validation ---
# INTENT: Verify fetched data meets Plan expectations for year coverage,
#   row counts, critical columns, and identifier integrity.
# ASSUMES: Expected row count range is 5,000-15,000 (multiple ftpt rows per institution).
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Expected year present
years_found = sorted(df["year"].unique().to_list())
all_years = all(y in years_found for y in YEARS)
print(f"  [{'PASS' if all_years else 'FAIL'}] Year 2020 present: {years_found}")
if not all_years:
    cp1_passed = False

# CP1.2: Row count in expected range (5,000-15,000)
expected_min = 5000
expected_max = 15000
row_count = df.shape[0]
rows_reasonable = expected_min <= row_count <= expected_max
if rows_reasonable:
    print(f"  [PASS] Row count {row_count:,} in expected range [{expected_min:,}, {expected_max:,}]")
elif row_count > 0:
    print(f"  [WARN] Row count {row_count:,} outside expected range [{expected_min:,}, {expected_max:,}]")
else:
    print(f"  [FAIL] Empty dataset")
    cp1_passed = False

# CP1.3: Critical columns present
required_cols = ["unitid", "year", "ftpt", "retention_rate"]
missing_cols = [c for c in required_cols if c not in df.columns]
cols_present = len(missing_cols) == 0
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: {required_cols}")
if missing_cols:
    print(f"    Missing: {missing_cols}")
    cp1_passed = False

# CP1.4: All available columns listed
print(f"  [INFO] All columns: {df.columns}")

# CP1.5: No nulls in identifier columns
unitid_nulls = df["unitid"].null_count()
year_nulls = df["year"].null_count()
no_id_nulls = unitid_nulls == 0 and year_nulls == 0
print(f"  [{'PASS' if no_id_nulls else 'FAIL'}] No nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")
if not no_id_nulls:
    cp1_passed = False

# CP1.6: Missingness by column
print("\n  Missing values by column:")
for col_name in df.columns:
    null_count = df[col_name].null_count()
    null_pct = null_count / len(df) * 100 if len(df) > 0 else 0
    status = "PASS" if null_pct < 5 else ("WARN" if null_pct < 50 else "FAIL")
    print(f"    [{status}] {col_name}: {null_count:,} nulls ({null_pct:.1f}%)")
    if null_pct > 90:
        cp1_passed = False

# CP1.7: COVID year flag
# INTENT: Flag that 2020 is a COVID-affected year for documentation purposes.
# REASONING: Education data for 2020 may have anomalous patterns due to COVID-19.
if any(y in FLAG_YEARS for y in YEARS):
    print(f"\n  [WARN] FLAG-YEARS: Analysis includes data from flagged years {FLAG_YEARS}.")
    print("    Document COVID-19 comparability concerns in limitations.")

# CP1.8: ftpt coverage check
# INTENT: Verify both full-time (1) and part-time (2) categories present.
# REASONING: Analysis requires both ftpt categories for complete retention picture.
ftpt_unique = sorted(df["ftpt"].unique().to_list())
both_ftpt = 1 in ftpt_unique and 2 in ftpt_unique
print(f"\n  [{'PASS' if both_ftpt else 'WARN'}] ftpt categories present: {ftpt_unique}")

assert cp1_passed, "STOP: CP1 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:16:08
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage5_fetch/07_fetch-retention.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.7: Fetch IPEDS Fall Retention
# ============================================================
# 
# Fetching IPEDS Fall Retention data...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_fall-retention.parquet
#   -> huggingface: 324,778 rows
#   After filters: 17,508 rows
# 
# Shape after year filter: 17,508 rows x 9 cols
# 
# --- Column Dtypes ---
#   unitid: Int64
#   year: Int64
#   fips: Int64
#   ftpt: Int64
#   retention_rate: Float64
#   returning_students: String
#   prev_cohort: String
#   prev_exclusions: String
#   prev_cohort_adj: String
# 
# --- CRITICAL: retention_rate dtype = Float64 ---
# 
# --- ftpt Unique Values ---
# shape: (3, 2)
# ┌──────┬───────┐
# │ ftpt ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 5836  │
# │ 2    ┆ 5836  │
# │ 99   ┆ 5836  │
# └──────┴───────┘
# 
# --- retention_rate Sample Values ---
# shape: (10, 1)
# ┌────────────────┐
# │ retention_rate │
# │ ---            │
# │ f64            │
# ╞════════════════╡
# │ 0.54           │
# │ 0.33           │
# │ 0.54           │
# │ 0.86           │
# │ 0.48           │
# │ 0.86           │
# │ 0.5            │
# │ null           │
# │ 0.5            │
# │ 0.82           │
# └────────────────┘
# 
# --- Coded Missing Value Check ---
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/raw/2026-03-29_ipeds_retention.parquet
# File size: 138.3 KB
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year 2020 present: [2020]
#   [WARN] Row count 17,508 outside expected range [5,000, 15,000]
#   [PASS] Critical columns present: ['unitid', 'year', 'ftpt', 'retention_rate']
#   [INFO] All columns: ['unitid', 'year', 'fips', 'ftpt', 'retention_rate', 'returning_students', 'prev_cohort', 'prev_exclusions', 'prev_cohort_adj']
#   [PASS] No nulls in ID columns: unitid=0, year=0
# 
#   Missing values by column:
#     [PASS] unitid: 0 nulls (0.0%)
#     [PASS] year: 0 nulls (0.0%)
#     [PASS] fips: 0 nulls (0.0%)
#     [PASS] ftpt: 0 nulls (0.0%)
#     [WARN] retention_rate: 4,096 nulls (23.4%)
#     [WARN] returning_students: 2,404 nulls (13.7%)
#     [WARN] prev_cohort: 2,404 nulls (13.7%)
#     [WARN] prev_exclusions: 2,404 nulls (13.7%)
#     [WARN] prev_cohort_adj: 2,404 nulls (13.7%)
# 
#   [WARN] FLAG-YEARS: Analysis includes data from flagged years [2020, 2021].
#     Document COVID-19 comparability concerns in limitations.
# 
#   [PASS] ftpt categories present: [1, 2, 99]
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
