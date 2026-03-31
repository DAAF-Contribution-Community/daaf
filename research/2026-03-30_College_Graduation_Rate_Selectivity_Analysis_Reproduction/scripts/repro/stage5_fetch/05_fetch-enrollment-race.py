#!/usr/bin/env python3
"""
Stage 5.5: Fetch IPEDS fall enrollment by race data for 2020.

Task: fetch-enrollment-race
Wave: 1, Step: 5, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_enrollment_race.parquet
Checkpoint: CP1

Provenance: education-data-query skill. The skill's mirrors.yaml and
datasets-reference.md define the canonical path and mirror priority.
This is a YEARLY dataset (one file per year). The unfiltered file is
~3.5M rows; dimension filters reduce to ~50K rows.
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# Data is downloaded from mirrors. The fall-enrollment-race dataset is a yearly
# file containing enrollment counts disaggregated by race/ethnicity.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020]  # Per Plan query specification: single year 2020

# Dataset path template (from datasets-reference.md: yearly dataset)
# INTENT: Fetch IPEDS fall enrollment by race for 2020.
# REASONING: The path template uses {year} placeholder because this is a yearly
# dataset — one file per year. Year 2020 is the analysis year per Plan.
DATASET_PATH_TEMPLATE = "ipeds/colleges_ipeds_fall-enrollment-race_{year}"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_enrollment_race.parquet"

# Dimension filters to apply AFTER loading.
# INTENT: Reduce the ~3.5M-row file to only the rows needed for analysis.
# REASONING: The raw file contains all combinations of sex, ftpt, level_of_study,
# degree_seeking, class_level, and race. We want total enrollment by race only:
#   - sex == 99 (total across sexes)
#   - ftpt == 99 (total full-time + part-time)
#   - level_of_study == 1 (undergraduate)
#   - degree_seeking == 99 (total degree-seeking + non-degree-seeking)
#   - class_level == 99 (total across class levels)
# This collapses all demographic dimensions except race, giving one row per
# institution per race category.
# ASSUMES: These coded values (99 for totals, 1 for undergraduate) follow
# the standard Portal integer encoding documented in filters-reference.md.
DIMENSION_FILTERS = {
    "sex": 99,
    "ftpt": 99,
    "level_of_study": 1,
    "degree_seeking": 99,
    "class_level": 99,
}

# --- Mirror Configuration ---
# INTENT: Download dataset from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
# Format-specific read driven by each mirror's read_strategy field.
# ASSUMES: Mirror URLs are current and accessible.
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Rate Limiting ---
# INTENT: Prevent HTTP 429 (Too Many Requests) errors from mirrors.
# REASONING: Mirrors may rate-limit rapid successive requests.
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
                # REASONING: CSV files can be very large. Lazy loading streams
                # only matching rows into memory. For this ~3.5M row file, lazy
                # loading is essential to avoid excessive memory usage.
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
                print(f"  >> {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  >> {name}: {df.shape[0]:,} rows")

            # Apply filters for eagerly-loaded formats
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


def fetch_yearly_from_mirrors(
    path_template: str,
    years: list[int],
    year_placeholder: str = "{year}",
    filters: dict | None = None,
) -> pl.DataFrame:
    """Fetch yearly files and concatenate.

    For datasets split into per-year files, download each year separately
    and concatenate.

    Args:
        path_template: Canonical path string with a year placeholder.
        years: List of years to fetch.
        year_placeholder: String in path_template to replace with year.
        filters: Additional column filters.

    Returns:
        Concatenated, filtered Polars DataFrame.
    """
    frames = []

    for year in years:
        year_path = path_template.replace(year_placeholder, str(year))
        print(f"\n  Year {year}:")

        try:
            df = fetch_from_mirrors(
                year_path,
                filters=filters,
                years=[year],
            )
            frames.append(df)
            print(f"    -> {df.shape[0]:,} rows")
        except RuntimeError:
            print(f"    -> SKIP: Year {year} not available from any mirror")

    if not frames:
        raise RuntimeError(f"No data retrieved for any year in {years}")

    result = pl.concat(frames, how="diagonal_relaxed")
    print(f"\n  Combined: {result.shape[0]:,} rows x {result.shape[1]} cols")
    return result


# --- Execution ---
print("=" * 60)
print("Stage 5.5: Fetch IPEDS Fall Enrollment by Race (2020)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS fall enrollment by race for 2020 and apply dimension
# filters to reduce from ~3.5M rows to ~50K rows.
# REASONING: Yearly dataset (one file per year). Download the 2020 file, then
# apply dimension filters locally with Polars. We fetch the full file first
# (for parquet mirrors) or apply filters lazily (for CSV mirrors).
# ASSUMES: The file exists on at least one mirror for year 2020.
print("\nFetching IPEDS fall enrollment by race data...")
df_raw = fetch_yearly_from_mirrors(
    path_template=DATASET_PATH_TEMPLATE,
    years=YEARS,
)

# --- Pre-state (before dimension filtering) ---
pre_rows = df_raw.shape[0]
pre_cols = df_raw.columns.copy()
print(f"\nPre-filter state: {pre_rows:,} rows x {len(pre_cols)} cols")
print(f"Columns: {pre_cols}")

# --- Apply Dimension Filters ---
# INTENT: Filter to only the total enrollment rows by race, collapsing sex,
# ftpt, level_of_study, degree_seeking, and class_level dimensions.
# REASONING: The raw file has all cross-tabulations of these dimensions.
# We only want the undergraduate totals by race to compute racial composition
# metrics for each institution.
# ASSUMES: The dimension columns exist in the dataset and use the standard
# Portal integer encoding (99 = total, 1 = undergraduate for level_of_study).
print("\nApplying dimension filters...")
for col, val in DIMENSION_FILTERS.items():
    before = df_raw.shape[0]
    if col not in df_raw.columns:
        print(f"  WARNING: Column '{col}' not found in data. Skipping filter.")
        continue
    df_raw = df_raw.filter(pl.col(col) == val)
    after = df_raw.shape[0]
    print(f"  {col} == {val}: {before:,} -> {after:,} rows")

df = df_raw

# --- Post-state (after dimension filtering) ---
post_rows = df.shape[0]
print(f"\nPost-filter state: {post_rows:,} rows x {df.shape[1]} cols")
print(f"Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- Logging: Race codes and enrollment distribution ---
# INTENT: Document the race codes found and enrollment_fall distribution for
# downstream reference and QA inspection.
# REASONING: The task specification requires logging unique race codes and
# enrollment_fall distribution to confirm data completeness.
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

if "race" in df.columns:
    race_codes = sorted(df["race"].unique().to_list())
    print(f"\nUnique race codes found ({len(race_codes)}): {race_codes}")
    race_counts = df.group_by("race").len().sort("race")
    print(f"\nRows per race code:")
    for row in race_counts.iter_rows(named=True):
        print(f"  Race {row['race']}: {row['len']:,} rows")
else:
    print("WARNING: 'race' column not found in data")

if "enrollment_fall" in df.columns:
    enroll = df["enrollment_fall"].drop_nulls()
    print(f"\nenrollment_fall distribution:")
    print(f"  Count: {enroll.len():,}")
    print(f"  Nulls: {df['enrollment_fall'].null_count():,}")
    print(f"  Mean:  {enroll.mean():,.1f}")
    print(f"  Median: {enroll.median():,.1f}")
    print(f"  Min:   {enroll.min():,}")
    print(f"  Max:   {enroll.max():,}")
    print(f"  Zeros: {(enroll == 0).sum():,}")
else:
    print("WARNING: 'enrollment_fall' column not found in data")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# row counts, year coverage, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Year coverage
years_found = sorted(df["year"].unique().to_list())
all_years = all(y in years_found for y in YEARS)
print(f"  [{'PASS' if all_years else 'FAIL'}] Year coverage: {years_found} (expected {YEARS})")

# CP1.2: Row count in expected range (30,000-70,000 after filters)
row_count_ok = 30000 <= post_rows <= 70000
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count: {post_rows:,} (expected 30,000-70,000)")

# CP1.3: Required columns present
required_cols = ["unitid", "year", "race", "enrollment_fall"]
cols_present = all(c in df.columns for c in required_cols)
missing_cols = [c for c in required_cols if c not in df.columns]
print(f"  [{'PASS' if cols_present else 'FAIL'}] Required columns: {required_cols}")
if missing_cols:
    print(f"    Missing: {missing_cols}")

# CP1.4: Race codes include expected values
expected_race_codes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
if "race" in df.columns:
    actual_race_codes = sorted(df["race"].unique().to_list())
    # Check that at least the major race codes (1-7, 99) are present
    major_codes = [1, 2, 3, 4, 5, 6, 7, 99]
    major_present = all(c in actual_race_codes for c in major_codes)
    print(f"  [{'PASS' if major_present else 'WARN'}] Major race codes (1-7, 99) present: {major_present}")
    print(f"    Actual codes: {actual_race_codes}")
    print(f"    Expected: {expected_race_codes}")
else:
    major_present = False
    print(f"  [FAIL] Race column not found")

# CP1.5: Null rate < 5% for unitid
if "unitid" in df.columns:
    unitid_null_rate = df["unitid"].null_count() / len(df) * 100
    unitid_ok = unitid_null_rate < 5
    print(f"  [{'PASS' if unitid_ok else 'FAIL'}] unitid null rate: {unitid_null_rate:.2f}% (threshold: <5%)")
else:
    unitid_ok = False
    print(f"  [FAIL] unitid column not found")

# CP1.6: Data types check
print(f"\n  Column types:")
for col in required_cols:
    if col in df.columns:
        print(f"    {col}: {df[col].dtype}")

# Overall CP1 result
cp1_passed = all([all_years, cols_present, unitid_ok])
assert cp1_passed, f"STOP: CP1 FAILED - years={all_years}, cols={cols_present}, unitid_ok={unitid_ok}"

# Row count warning (non-blocking)
if not row_count_ok:
    print(f"\n  [WARNING] Row count {post_rows:,} outside expected range 30,000-70,000")
    print(f"  This may indicate different dimension filter results than anticipated.")

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:19:00
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage5_fetch/05_fetch-enrollment-race.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.5: Fetch IPEDS Fall Enrollment by Race (2020)
# ============================================================
# 
# Fetching IPEDS fall enrollment by race data...
# 
#   Year 2020:
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_fall-enrollment-race_2020.parquet
#   >> huggingface: 3,533,310 rows
#   After filters: 3,533,310 rows
#     -> 3,533,310 rows
# 
#   Combined: 3,533,310 rows x 10 cols
# 
# Pre-filter state: 3,533,310 rows x 10 cols
# Columns: ['unitid', 'year', 'fips', 'sex', 'race', 'ftpt', 'level_of_study', 'degree_seeking', 'class_level', 'enrollment_fall']
# 
# Applying dimension filters...
#   sex == 99: 3,533,310 -> 1,177,770 rows
#   ftpt == 99: 1,177,770 -> 434,120 rows
#   level_of_study == 1: 434,120 -> 352,410 rows
#   degree_seeking == 99: 352,410 -> 58,370 rows
#   class_level == 99: 58,370 -> 58,370 rows
# 
# Post-filter state: 58,370 rows x 10 cols
# Row change: -3,474,940 (-98.3%)
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/raw/2026-03-29_ipeds_enrollment_race.parquet
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Unique race codes found (10): [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# 
# Rows per race code:
#   Race 1: 5,837 rows
#   Race 2: 5,837 rows
#   Race 3: 5,837 rows
#   Race 4: 5,837 rows
#   Race 5: 5,837 rows
#   Race 6: 5,837 rows
#   Race 7: 5,837 rows
#   Race 8: 5,837 rows
#   Race 9: 5,837 rows
#   Race 99: 5,837 rows
# 
# enrollment_fall distribution:
#   Count: 58,370
#   Nulls: 0
#   Mean:  563.5
#   Median: 18.0
#   Min:   0
#   Max:   111,599
#   Zeros: 13,394
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year coverage: [2020] (expected [2020])
#   [PASS] Row count: 58,370 (expected 30,000-70,000)
#   [PASS] Required columns: ['unitid', 'year', 'race', 'enrollment_fall']
#   [PASS] Major race codes (1-7, 99) present: True
#     Actual codes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#     Expected: [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
#   [PASS] unitid null rate: 0.00% (threshold: <5%)
# 
#   Column types:
#     unitid: Int64
#     year: Int64
#     race: Int64
#     enrollment_fall: Int64
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
