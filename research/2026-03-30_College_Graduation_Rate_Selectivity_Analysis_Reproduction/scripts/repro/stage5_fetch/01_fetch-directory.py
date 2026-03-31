#!/usr/bin/env python3
"""
Stage 5.1: Fetch IPEDS institution directory data for 2020-2021.

Task: fetch-directory
Wave: 1, Step: 1, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_directory.parquet
Checkpoint: CP1
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# Data is downloaded from mirrors (per mirrors.yaml priority order).
# We fetch 2 years (2020-2021) to match the Plan's year range for this
# college graduation rate / selectivity analysis.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020, 2021]  # Per Plan query specification

# Dataset path from education-data-query skill's datasets-reference.md.
# IPEDS Directory is a single-file dataset (all years in one file).
DATASET_PATH = "ipeds/colleges_ipeds_directory"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_directory.parquet"

# Required columns per task specification
REQUIRED_COLS = [
    "unitid", "year", "inst_name", "fips", "inst_control",
    "institution_level", "degree_granting", "open_public",
]

# Expected row count range: 6,000-15,000 (2 years x 3,000-7,500 institutions)
EXPECTED_MIN_ROWS = 6_000
EXPECTED_MAX_ROWS = 15_000

# Domain configuration (education)
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID-impacted years

# --- Mirror Configuration ---
# INTENT: Load mirror configuration so fetch_from_mirrors() knows which
# mirrors to try and in what order. mirrors.yaml is the single source of
# truth for mirror URLs, formats, and read strategies.
#
# REASONING: Loading from YAML file (rather than hardcoding URLs) because
# mirrors can change independently of analysis scripts. The YAML also
# encodes the read_strategy (eager_parquet vs lazy_csv) so the fetch
# function adapts to each mirror's format automatically.
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
            Example: "ipeds/colleges_ipeds_directory"
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
            if strategy == "eager_parquet":
                # REASONING: Parquet files have embedded schema, no inference needed.
                # Polars reads HTTP URLs natively via pl.read_parquet().
                df = pl.read_parquet(url)
            elif strategy == "lazy_csv":
                # REASONING: CSV files can be large. Lazy loading streams only
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
                print(f"  {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  {name}: {df.shape[0]:,} rows (full file)")

            # Apply filters for eagerly-loaded formats (parquet)
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
            print(f"  {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Fetch ---
# INTENT: Download IPEDS institution directory and filter to years 2020-2021.
# REASONING: Single-file dataset (all years in one file). Download once,
# filter locally with Polars. No additional filters at fetch stage --
# population filters (4-year, degree-granting, etc.) will be applied
# during cleaning (Stage 6) per the task specification.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
# ASSUMES: Dataset path "ipeds/colleges_ipeds_directory" is correct per
# datasets-reference.md.
print("=" * 60)
print("Stage 5.1: Fetch IPEDS institution directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

print("\nFetching IPEDS directory...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"\nFetched shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state for the record. Since this is a fetch (not transform),
# we capture the fetched data profile directly.
pre_rows = df.shape[0]
print(f"\nPre-state (fetched data): {pre_rows:,} rows, {df.shape[1]} cols")

# Sample identifiers for audit trail
if "unitid" in df.columns:
    sample_ids = df["unitid"].head(3).to_list()
    print(f"Sample unitid values: {sample_ids}")

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# year coverage, row counts, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Shape check
print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} cols")
if df.shape[0] == 0:
    print("[FAIL] Empty dataset returned from mirror")
    cp1_passed = False
else:
    print(f"[PASS] {df.shape[0]:,} rows loaded")

# CP1.2: Row count reasonableness
if EXPECTED_MIN_ROWS <= df.shape[0] <= EXPECTED_MAX_ROWS:
    print(f"[PASS] Row count {df.shape[0]:,} within expected range [{EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,}]")
elif df.shape[0] > EXPECTED_MAX_ROWS:
    # REASONING: Row count above max is acceptable -- the range is conservative.
    # IPEDS directory includes all institution types (not just 4-year), so higher
    # counts are expected before population filtering in Stage 6.
    print(f"[WARN] Row count {df.shape[0]:,} above expected max {EXPECTED_MAX_ROWS:,} (includes all institution types)")
else:
    print(f"[WARN] Row count {df.shape[0]:,} below expected min {EXPECTED_MIN_ROWS:,}")

# CP1.3: All expected years present
years_found = sorted(df[YEAR_COL].unique().to_list())
missing_years = [y for y in YEARS if y not in years_found]
if missing_years:
    print(f"[FAIL] Missing expected years: {missing_years}")
    cp1_passed = False
else:
    print(f"[PASS] All {len(YEARS)} expected years present: {years_found}")

# CP1.4: Year-level row counts
year_counts = df.group_by("year").len().sort("year")
print("\nRow counts by year:")
for row in year_counts.iter_rows(named=True):
    print(f"  {row['year']}: {row['len']:,}")

# CP1.5: Required columns present
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    print(f"[FAIL] Missing required columns: {missing_cols}")
    cp1_passed = False
else:
    print(f"[PASS] All {len(REQUIRED_COLS)} required columns present: {REQUIRED_COLS}")

# CP1.6: No nulls in identifier columns (unitid, year)
unitid_nulls = df["unitid"].null_count()
year_nulls = df["year"].null_count()
if unitid_nulls > 0 or year_nulls > 0:
    print(f"[FAIL] Nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")
    cp1_passed = False
else:
    print(f"[PASS] No nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")

# CP1.7: Null rates for required columns (< 10% threshold for unitid, year)
print("\nNull rates for required columns:")
for col in REQUIRED_COLS:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        status = "PASS" if null_pct < 10 else ("WARN" if null_pct < 50 else "FAIL")
        print(f"  [{status}] {col}: {null_pct:.1f}% null ({df[col].null_count():,} / {len(df):,})")
        if null_pct >= 90:
            cp1_passed = False

# CP1.8: Data types for key columns
print("\nData types for required columns:")
for col in REQUIRED_COLS:
    if col in df.columns:
        print(f"  {col}: {df[col].dtype}")

# CP1.9: Flag years warning (COVID)
# REASONING: 2020 and 2021 are COVID-impacted years for postsecondary data.
# Institutions may have different reporting patterns (e.g., enrollment drops,
# temporary closures). This is documented as a data quality caveat.
if any(y in FLAG_YEARS for y in YEARS):
    print(f"\n[WARN] FLAG-YEARS: Analysis includes COVID-impacted years {FLAG_YEARS}. "
          "Document comparability concerns in limitations.")

# --- CP1 Result ---
assert cp1_passed, "STOP: CP1 FAILED - see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:16:04
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage5_fetch/01_fetch-directory.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.1: Fetch IPEDS institution directory
# ============================================================
# 
# Fetching IPEDS directory...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_directory.parquet
#   huggingface: 336,982 rows (full file)
#   After filters: 12,729 rows
# 
# Fetched shape: 12,729 rows x 89 cols
# Columns: ['unitid', 'year', 'opeid', 'inst_name', 'inst_alias', 'address', 'state_abbr', 'fips', 'zip', 'phone_number', 'city', 'county_name', 'county_fips', 'region', 'urban_centric_locale', 'cbsa', 'cbsa_type', 'csa', 'necta', 'longitude', 'latitude', 'congress_district_id', 'ein', 'ueis', 'chief_admin_name', 'chief_admin_title', 'inst_status', 'currently_active_ipeds', 'degree_granting', 'open_public', 'title_iv_indicator', 'postsec_public_active', 'postsec_public_active_title_iv', 'date_closed', 'newid', 'year_deleted', 'inst_control', 'institution_level', 'inst_category', 'inst_size', 'sector', 'primarily_postsecondary', 'hbcu', 'hospital', 'medical_degree', 'tribal_college', 'land_grant', 'offering_highest_degree', 'offering_highest_level', 'offering_undergrad', 'offering_grad', 'url_school', 'url_fin_aid', 'url_application', 'url_netprice', 'url_veterans', 'url_athletes', 'url_disability_services', 'cc_basic_2010', 'cc_instruc_undergrad_2010', 'cc_instruc_grad_2010', 'cc_undergrad_2010', 'cc_enroll_2010', 'cc_size_setting_2010', 'cc_basic_2000', 'cc_basic_2015', 'cc_instruc_undergrad_2015', 'cc_instruc_grad_2015', 'cc_undergrad_2015', 'cc_enroll_2015', 'cc_size_setting_2015', 'cc_basic_2018', 'cc_instruc_undergrad_2018', 'cc_instruc_grad_2018', 'cc_undergrad_2018', 'cc_enroll_2018', 'cc_size_setting_2018', 'comparison_group', 'comparison_group_custom', 'inst_system_flag', 'inst_system_name', 'reporting_method', 'duns', 'cc_basic_2021', 'cc_instruc_undergrad_2021', 'cc_instruc_grad_2021', 'cc_undergrad_2021', 'cc_enroll_2021', 'cc_size_setting_2021']
# 
# Pre-state (fetched data): 12,729 rows, 89 cols
# Sample unitid values: [100654, 100654, 100663]
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/raw/2026-03-29_ipeds_directory.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
# 
# Shape: 12,729 rows x 89 cols
# [PASS] 12,729 rows loaded
# [PASS] Row count 12,729 within expected range [6,000-15,000]
# [PASS] All 2 expected years present: [2020, 2021]
# 
# Row counts by year:
#   2020: 6,440
#   2021: 6,289
# [PASS] All 8 required columns present: ['unitid', 'year', 'inst_name', 'fips', 'inst_control', 'institution_level', 'degree_granting', 'open_public']
# [PASS] No nulls in ID columns: unitid=0, year=0
# 
# Null rates for required columns:
#   [PASS] unitid: 0.0% null (0 / 12,729)
#   [PASS] year: 0.0% null (0 / 12,729)
#   [PASS] inst_name: 0.0% null (0 / 12,729)
#   [PASS] fips: 0.0% null (0 / 12,729)
#   [PASS] inst_control: 0.0% null (0 / 12,729)
#   [PASS] institution_level: 0.0% null (0 / 12,729)
#   [PASS] degree_granting: 0.0% null (0 / 12,729)
#   [PASS] open_public: 0.0% null (0 / 12,729)
# 
# Data types for required columns:
#   unitid: Int64
#   year: Int64
#   inst_name: String
#   fips: Int64
#   inst_control: Int64
#   institution_level: Int64
#   degree_granting: Int64
#   open_public: Int64
# 
# [WARN] FLAG-YEARS: Analysis includes COVID-impacted years [2020, 2021]. Document comparability concerns in limitations.
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
