#!/usr/bin/env python3
"""
Stage 5.3: Fetch IPEDS admissions-enrollment data for 2020.

Task: fetch-admissions
Wave: 1, Step: 3, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_admissions.parquet
Checkpoint: CP1

Research Question: Are high college graduation rates a signal of
institutional quality, or primarily a reflection of admissions selectivity
and student body demographics?
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# Data is downloaded from mirrors (per mirrors.yaml priority order).
# We fetch year 2020 with sex==99 (total) to get institution-level
# admissions metrics for the selectivity analysis.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEAR = 2020  # Single year per Plan query specification
SEX_TOTAL = 99  # Portal integer encoding: 99 = total (both sexes combined)

# Dataset path from education-data-query skill's datasets-reference.md.
# IPEDS Admissions is a single-file dataset (all years in one file).
DATASET_PATH = "ipeds/colleges_ipeds_admissions-enrollment"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_admissions.parquet"

# Columns to retain from the full dataset. These are the minimum needed
# for computing admissions selectivity (admit rate = admitted / applied)
# and yield (enrolled / admitted).
KEEP_COLUMNS = [
    "unitid",
    "year",
    "number_applied",
    "number_admitted",
    "number_enrolled_total",
]

# Expected row count range per Plan: 1,500-4,000 institutions
# (Title IV degree-granting institutions that report admissions data).
EXPECTED_MIN_ROWS = 1_500
EXPECTED_MAX_ROWS = 4_000

# Critical columns that must be present and non-null for identifier integrity.
CRITICAL_COLUMNS = ["unitid", "number_applied", "number_admitted"]

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
            All mirrors use the same path -- only root_url and format differ.
            Example: "ipeds/colleges_ipeds_admissions-enrollment"
        filters: Dict of column->value(s) filters to apply locally.
        years: List of years to filter to (applied as pl.col("year").is_in(years)).

    Returns:
        Filtered Polars DataFrame.
    """
    _rate_limit()
    last_error = None

    for mirror in MIRRORS:
        name = mirror["name"]
        strategy = mirror["read_strategy"]

        # Build URL from template + canonical path
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
                # REASONING: CSV files can be very large. Lazy loading streams only
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
print("Stage 5.3: Fetch IPEDS admissions-enrollment data")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# INTENT: Download IPEDS admissions-enrollment data and filter to year 2020,
# sex==99 (total). This gives us institution-level application, admission,
# and enrollment counts needed to compute admissions selectivity (admit rate).
#
# REASONING: Using mirror-based download (not the REST API) because mirrors
# serve complete files that Polars can read natively via HTTP -- no pagination,
# no rate limiting, and parquet format preserves schema and compresses data.
#
# ASSUMES:
#   - At least one mirror is available and serves this dataset
#   - Dataset contains "year" and "sex" columns for filtering
#   - sex==99 represents the total (both sexes combined) per Portal encoding
#   - Year 2020 data is available (IPEDS admissions covers many years)
print("\nFetching IPEDS admissions-enrollment data...")
df_raw = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
    filters={"sex": SEX_TOTAL},
)

print(f"\nRaw data shape: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")
print(f"Columns available: {df_raw.columns}")

# --- Pre-state ---
# Capture current state BEFORE column selection for post-validation comparison.
pre_rows = df_raw.shape[0]
pre_cols = df_raw.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Sample unitids: {df_raw['unitid'].head(3).to_list()}")

# --- Column Selection ---
# INTENT: Select only the columns needed for the selectivity analysis to
# reduce file size and simplify downstream processing.
#
# REASONING: The full IPEDS admissions dataset has many columns (SAT scores,
# ACT scores, detailed enrollment breakdowns). We only need application,
# admission, and enrollment counts for computing admit rate. Additional
# columns can be fetched separately if needed later.
#
# ASSUMES: All KEEP_COLUMNS exist in the downloaded dataset.
available_keep = [c for c in KEEP_COLUMNS if c in df_raw.columns]
missing_cols = [c for c in KEEP_COLUMNS if c not in df_raw.columns]

if missing_cols:
    print(f"\nWARNING: Missing expected columns: {missing_cols}")
    print(f"Available columns: {df_raw.columns}")

df = df_raw.select(available_keep)

print(f"\nAfter column selection: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Retained columns: {df.columns}")

# --- Post-state ---
post_rows = df.shape[0]
print(f"\nPost-state: {post_rows:,} rows, {df.shape[1]} cols")
print(f"Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100 if pre_rows > 0 else 0:+.1f}%)")

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

# CP1.1: Only year 2020 present
years_found = df["year"].unique().to_list()
year_ok = years_found == [YEAR]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year filter: found {sorted(years_found)} (expected [{YEAR}])")

# CP1.2: Row count within expected range (1,500-4,000 institutions)
# REASONING: The expected range comes from the Plan estimate of Title IV
# degree-granting institutions that report admissions data. Too few rows
# would indicate a filtering error; too many would indicate duplicate
# institution entries.
row_count_ok = EXPECTED_MIN_ROWS <= post_rows <= EXPECTED_MAX_ROWS
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count: {post_rows:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# CP1.3: Critical columns present
# REASONING: unitid is the institution identifier; number_applied and
# number_admitted are needed to compute admit rate (selectivity measure).
cols_present = all(c in df.columns for c in CRITICAL_COLUMNS)
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: {CRITICAL_COLUMNS}")

# CP1.4: No nulls in unitid (institutional identifier)
unitid_nulls = df["unitid"].null_count()
unitid_ok = unitid_nulls == 0
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] No nulls in unitid: {unitid_nulls}")

# CP1.5: unitid uniqueness (one row per institution for year 2020, sex=total)
unitid_unique = df["unitid"].n_unique()
unitid_is_unique = unitid_unique == post_rows
print(f"  [{'PASS' if unitid_is_unique else 'WARN'}] unitid uniqueness: {unitid_unique:,} unique vs {post_rows:,} rows")

# CP1.6: number_applied > 0 for most rows (open-admission may have 0 or null)
# REASONING: Most institutions that report admissions data should have
# non-zero application counts. A high rate of zero/null would suggest
# data quality issues. Some open-admission institutions may legitimately
# have missing data here -- these are handled in Stage 6 cleaning.
applied_positive = df.filter(
    pl.col("number_applied").is_not_null() & (pl.col("number_applied") > 0)
).shape[0]
applied_pct = applied_positive / post_rows * 100 if post_rows > 0 else 0
applied_ok = applied_pct > 50  # At least 50% should have application data
print(f"  [{'PASS' if applied_ok else 'WARN'}] number_applied > 0: {applied_positive:,}/{post_rows:,} ({applied_pct:.1f}%)")

# CP1.7: number_admitted <= number_applied for all valid rows
# REASONING: An institution cannot admit more students than applied --
# this would indicate data corruption or misaligned variables.
valid_admit = df.filter(
    pl.col("number_applied").is_not_null()
    & pl.col("number_admitted").is_not_null()
    & (pl.col("number_applied") > 0)
    & (pl.col("number_admitted") > 0)
)
if valid_admit.shape[0] > 0:
    violations = valid_admit.filter(
        pl.col("number_admitted") > pl.col("number_applied")
    ).shape[0]
    admit_leq_applied = violations == 0
    print(f"  [{'PASS' if admit_leq_applied else 'WARN'}] admitted <= applied: {violations} violations out of {valid_admit.shape[0]:,} valid rows")
else:
    admit_leq_applied = True
    print(f"  [WARN] admitted <= applied: no valid rows to check")

# CP1.8: Data type verification
print(f"\n  Data types:")
for col in df.columns:
    print(f"    {col}: {df[col].dtype}")

# CP1.9: Quick distribution summary for admissions variables
print(f"\n  Distribution summary:")
for col in ["number_applied", "number_admitted", "number_enrolled_total"]:
    if col in df.columns:
        non_null = df[col].drop_nulls()
        if len(non_null) > 0:
            print(f"    {col}: min={non_null.min()}, median={non_null.median()}, max={non_null.max()}, null={df[col].null_count()}")
        else:
            print(f"    {col}: all null")

# --- CP1 Overall Status ---
# REASONING: Core checks (year, columns, unitid) must pass. Row count and
# admissions ratio checks are warnings because some institutions may have
# legitimate data gaps (open-admission schools, etc.).
cp1_passed = all([year_ok, cols_present, unitid_ok])
cp1_status = "PASSED" if cp1_passed else "FAILED"

if not row_count_ok:
    cp1_status = "PASSED" if cp1_passed else "FAILED"
    print(f"\n  NOTE: Row count outside expected range but core checks passed.")

print("\n" + "=" * 60)
print(f"CP1 VALIDATION: {cp1_status}")
print("=" * 60)

assert year_ok, f"STOP: Unexpected years found: {years_found}"
assert cols_present, f"STOP: Missing critical columns"
assert unitid_ok, f"STOP: Nulls in unitid"


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:09:05
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-admissions.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.3: Fetch IPEDS admissions-enrollment data
# ============================================================
# 
# Fetching IPEDS admissions-enrollment data...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_admissions-enrollment.parquet
#   OK huggingface: 196,186 rows
#   After filters: 1,989 rows
# 
# Raw data shape: 1,989 rows x 9 cols
# Columns available: ['unitid', 'year', 'fips', 'sex', 'number_applied', 'number_admitted', 'number_enrolled_ft', 'number_enrolled_pt', 'number_enrolled_total']
# 
# Pre-state: 1,989 rows, 9 cols
# Sample unitids: [100654, 100663, 100706]
# 
# After column selection: 1,989 rows x 5 cols
# Retained columns: ['unitid', 'year', 'number_applied', 'number_admitted', 'number_enrolled_total']
# 
# Post-state: 1,989 rows, 5 cols
# Row change: +0 (+0.0%)
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-02-15_ipeds_admissions.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year filter: found [2020] (expected [2020])
#   [PASS] Row count: 1,989 (expected 1,500-4,000)
#   [PASS] Critical columns present: ['unitid', 'number_applied', 'number_admitted']
#   [PASS] No nulls in unitid: 0
#   [PASS] unitid uniqueness: 1,989 unique vs 1,989 rows
#   [PASS] number_applied > 0: 1,966/1,989 (98.8%)
#   [PASS] admitted <= applied: 0 violations out of 1,964 valid rows
# 
#   Data types:
#     unitid: Int64
#     year: Int64
#     number_applied: Int64
#     number_admitted: Int64
#     number_enrolled_total: Int64
# 
#   Distribution summary:
#     number_applied: min=0, median=2016.0, max=108870, null=0
#     number_admitted: min=0, median=1440.0, max=74604, null=23
#     number_enrolled_total: min=0, median=326.0, max=15614, null=25
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
