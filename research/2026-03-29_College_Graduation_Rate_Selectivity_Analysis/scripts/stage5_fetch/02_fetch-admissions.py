#!/usr/bin/env python3
"""
Stage 5.2: Fetch IPEDS admissions-enrollment data for 2020-2021.

Task: fetch-admissions
Wave: 1, Step: 2, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_admissions.parquet
Checkpoint: CP1
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# IPEDS admissions-enrollment is a single-file dataset containing all years.
# We download the full file and filter locally to 2020-2021.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020, 2021]  # Per Plan query specification

# Dataset path from education-data-query skill's datasets-reference.md.
# IPEDS Admissions is a single-file dataset (all years in one file).
DATASET_PATH = "ipeds/colleges_ipeds_admissions-enrollment"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_admissions.parquet"

# Expected columns per task specification (dataset has only 9 columns)
EXPECTED_COLUMNS = [
    "unitid", "year", "fips", "sex",
    "number_applied", "number_admitted",
    "number_enrolled_ft", "number_enrolled_pt", "number_enrolled_total",
]

# Domain configuration
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID years -- document comparability concerns
EXPECTED_ROW_RANGE = (15_000, 30_000)

# --- Mirror Configuration ---
# INTENT: Load mirror configuration so fetch_from_mirrors() knows which
# mirrors to try and in what order. mirrors.yaml is the single source of
# truth for mirror URLs, formats, and read strategies.
# REASONING: Loading from YAML file (rather than hardcoding URLs) because
# mirrors can change independently of analysis scripts.
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
            print(f"  x {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Fetch ---
# INTENT: Download IPEDS admissions-enrollment data and filter to 2020-2021.
# REASONING: Single-file dataset (all years in one file). Download once,
# filter locally with Polars to the requested years.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains a "year"
# column. Dataset has multiple rows per institution per year (one per sex
# category: total, male, female).
print("=" * 60)
print("Stage 5.2: Fetch IPEDS admissions-enrollment data")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

print("\nFetching IPEDS admissions-enrollment...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"\nFetched shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Column Inventory ---
# INTENT: Log all column names found in the dataset, as requested by task spec.
# REASONING: The task specification notes the dataset has only 9 columns and
# requests explicit logging to confirm the schema.
print(f"\nAll columns found ({df.shape[1]}):")
for i, col in enumerate(df.columns):
    dtype = df[col].dtype
    null_ct = df[col].null_count()
    null_pct = null_ct / df.shape[0] * 100 if df.shape[0] > 0 else 0
    print(f"  {i+1:2d}. {col:<30s} dtype={dtype!s:<12s} nulls={null_ct:,} ({null_pct:.1f}%)")

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

# CP1.1: Row count within expected range
row_count = df.shape[0]
rows_in_range = EXPECTED_ROW_RANGE[0] <= row_count <= EXPECTED_ROW_RANGE[1]
if row_count == 0:
    print(f"[FAIL] Empty dataset returned from mirror")
    cp1_passed = False
elif rows_in_range:
    print(f"[PASS] Row count {row_count:,} within expected range {EXPECTED_ROW_RANGE}")
else:
    print(f"[WARN] Row count {row_count:,} outside expected range {EXPECTED_ROW_RANGE}")

# CP1.2: All expected years present
years_found = sorted(df[YEAR_COL].unique().to_list())
missing_years = [y for y in YEARS if y not in years_found]
if missing_years:
    print(f"[FAIL] Missing expected years: {missing_years}")
    cp1_passed = False
else:
    print(f"[PASS] All expected years present: {years_found}")

# CP1.3: Year-level row counts
year_counts = df.group_by(YEAR_COL).len().sort(YEAR_COL)
print(f"\nRows per year:")
for row in year_counts.iter_rows(named=True):
    print(f"  {row[YEAR_COL]}: {row['len']:,}")

# CP1.4: Required columns present
# INTENT: Check both expected columns and the required columns from task spec.
required_cols = ["unitid", "year", "sex", "number_applied", "number_admitted"]
missing_required = [c for c in required_cols if c not in df.columns]
if missing_required:
    print(f"[FAIL] Missing required columns: {missing_required}")
    cp1_passed = False
else:
    print(f"[PASS] All required columns present: {required_cols}")

# Also check full expected column set
missing_expected = [c for c in EXPECTED_COLUMNS if c not in df.columns]
if missing_expected:
    print(f"[WARN] Missing expected columns (non-critical): {missing_expected}")
else:
    print(f"[PASS] All {len(EXPECTED_COLUMNS)} expected columns present")

# CP1.5: No nulls in identifier columns (unitid, year)
unitid_nulls = df["unitid"].null_count()
year_nulls = df[YEAR_COL].null_count()
unitid_null_pct = unitid_nulls / row_count * 100 if row_count > 0 else 0
year_null_pct = year_nulls / row_count * 100 if row_count > 0 else 0

if unitid_null_pct > 10:
    print(f"[FAIL] unitid null rate {unitid_null_pct:.1f}% exceeds 10%")
    cp1_passed = False
elif unitid_nulls > 0:
    print(f"[WARN] unitid has {unitid_nulls:,} nulls ({unitid_null_pct:.1f}%)")
else:
    print(f"[PASS] unitid: 0 nulls")

if year_null_pct > 10:
    print(f"[FAIL] year null rate {year_null_pct:.1f}% exceeds 10%")
    cp1_passed = False
elif year_nulls > 0:
    print(f"[WARN] year has {year_nulls:,} nulls ({year_null_pct:.1f}%)")
else:
    print(f"[PASS] year: 0 nulls")

# CP1.6: Sex categories present (multiple rows per institution per year)
# REASONING: IPEDS admissions data has sex=1 (Male), sex=2 (Female), sex=99 (Total).
# Multiple sex categories per institution-year explain the 15K-30K row count
# (roughly ~6,000 institutions x 2 years x 2-3 sex categories).
if "sex" in df.columns:
    sex_values = sorted(df["sex"].unique().to_list())
    print(f"[INFO] Sex categories found: {sex_values}")

# CP1.7: Flag years warning
# INTENT: Warn that COVID-era data may have comparability issues.
flagged = [y for y in YEARS if y in FLAG_YEARS]
if flagged:
    print(f"[WARN] FLAG-YEARS: Analysis includes COVID-era years {flagged}. "
          "Document comparability concerns in limitations.")

# CP1.8: Missingness summary for all columns
print(f"\nMissingness summary:")
for col in df.columns:
    null_ct = df[col].null_count()
    null_pct = null_ct / row_count * 100 if row_count > 0 else 0
    if null_pct > 50:
        print(f"  [WARN] {col}: {null_pct:.1f}% null (high)")
    elif null_pct > 5:
        print(f"  [NOTE] {col}: {null_pct:.1f}% null")

assert cp1_passed, "STOP: CP1 FAILED -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 20:17:36
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-admissions.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.2: Fetch IPEDS admissions-enrollment data
# ============================================================
# 
# Fetching IPEDS admissions-enrollment...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_admissions-enrollment.parquet
#   -> huggingface: 196,186 rows
#   After filters: 11,910 rows
# 
# Fetched shape: 11,910 rows x 9 cols
# 
# All columns found (9):
#    1. unitid                         dtype=Int64        nulls=0 (0.0%)
#    2. year                           dtype=Int64        nulls=0 (0.0%)
#    3. fips                           dtype=Int64        nulls=0 (0.0%)
#    4. sex                            dtype=Int64        nulls=0 (0.0%)
#    5. number_applied                 dtype=Int64        nulls=3 (0.0%)
#    6. number_admitted                dtype=Int64        nulls=438 (3.7%)
#    7. number_enrolled_ft             dtype=Int64        nulls=608 (5.1%)
#    8. number_enrolled_pt             dtype=Int64        nulls=2,950 (24.8%)
#    9. number_enrolled_total          dtype=Int64        nulls=495 (4.2%)
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_admissions.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
# [WARN] Row count 11,910 outside expected range (15000, 30000)
# [PASS] All expected years present: [2020, 2021]
# 
# Rows per year:
#   2020: 5,967
#   2021: 5,943
# [PASS] All required columns present: ['unitid', 'year', 'sex', 'number_applied', 'number_admitted']
# [PASS] All 9 expected columns present
# [PASS] unitid: 0 nulls
# [PASS] year: 0 nulls
# [INFO] Sex categories found: [1, 2, 99]
# [WARN] FLAG-YEARS: Analysis includes COVID-era years [2020, 2021]. Document comparability concerns in limitations.
# 
# Missingness summary:
#   [NOTE] number_enrolled_ft: 5.1% null
#   [NOTE] number_enrolled_pt: 24.8% null
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
