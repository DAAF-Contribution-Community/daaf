#!/usr/bin/env python3
"""
Stage 5.6: Fetch IPEDS Student-Faculty Ratio data for year 2020.

Task: fetch-sfr
Wave: 2, Step: 6, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_sfr.parquet
Checkpoint: CP1
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification (Task 2.1).
# IPEDS Student-Faculty Ratio is a single-file dataset (all years 2009-2020 in one file).
# We download the full file and filter locally to year 2020.
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020]  # Per Plan query specification: year 2020 only
REQUIRED_COLS = ["unitid", "year", "fips", "student_faculty_ratio"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 7000

# Dataset path (from education-data-query datasets-reference.md)
# Type: Single (all years 2009-2020 in one file)
DATASET_PATH = "ipeds/colleges_ipeds_student-faculty-ratio"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_sfr.parquet"

# Domain configuration (from Plan's Domain Configuration section)
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID years for education data

# --- Mirror Configuration ---
# INTENT: Download IPEDS Student-Faculty Ratio from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
#   Format-specific read driven by each mirror's read_strategy field.
#   All mirrors use the same canonical path from datasets-reference.md.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
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
                # REASONING: Parquet files have embedded schema, no inference needed.
                # Polars reads HTTP URLs natively via pl.read_parquet().
                df = pl.read_parquet(url)
            elif strategy in ("lazy_csv", "csv"):
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
                print(f"  [OK] {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  [OK] {name}: {df.shape[0]:,} rows")

            # Apply filters for eagerly-loaded formats (parquet, etc.)
            if years:
                # INTENT: Filter to requested year(s) locally after full download.
                # REASONING: Single-file dataset contains all years; we only need 2020.
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
            print(f"  [FAIL] {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Load ---
print("=" * 60)
print("Stage 5.6: Fetch IPEDS Student-Faculty Ratio")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS SFR dataset and filter to year 2020.
# REASONING: Single-file dataset (all years 2009-2020 in one file). Download once,
#   filter locally with Polars. Mirror priority order handles failover automatically.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column
#   with integer year values. IPEDS SFR data covers 2009-2020 per datasets-reference.md.
print("\nFetching IPEDS Student-Faculty Ratio data...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)

print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Dtypes: {df.dtypes}")

# --- Pre-state ---
# INTENT: Capture state before any further processing for audit trail.
pre_rows = df.shape[0]
print(f"\nPre-state: {pre_rows:,} rows")

# Check for coded missing values (-1, -2, -3) that are standard in Portal data.
# INTENT: Report presence of coded values for downstream Stage 6 cleaning.
# REASONING: Portal uses integer sentinel values (-1 = missing/not reported,
#   -2 = not applicable, -3 = suppressed). These will be handled in Stage 6;
#   we just report their presence here for CP1 awareness.
# ASSUMES: Coded values only appear in numeric columns.
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed"}
print("\nCoded missing value scan:")
for col in df.columns:
    if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
        for code, meaning in CODED_MISSING.items():
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                print(f"  {col} = {code} ({meaning}): {count:,}")

# --- Save ---
# INTENT: Persist fetched data in parquet format for downstream cleaning.
# REASONING: Parquet preserves schema and types, is compressed, and supports
#   efficient column-level reads for downstream transformations.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# INTENT: Verify fetched data meets Plan expectations for year coverage,
#   row counts, critical columns, and identifier integrity.
# REASONING: CP1 catches fetch errors (wrong dataset, empty result, missing
#   columns) before they propagate to cleaning and transformation stages.
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

# CP1.2: Row count within expected range
if df.shape[0] > 0:
    in_range = EXPECTED_MIN_ROWS <= df.shape[0] <= EXPECTED_MAX_ROWS
    if in_range:
        print(f"[PASS] Row count {df.shape[0]:,} within expected range ({EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")
    else:
        print(f"[WARN] Row count {df.shape[0]:,} outside expected range ({EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# CP1.3: Required columns present
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    print(f"[FAIL] Missing required columns: {missing_cols}")
    cp1_passed = False
else:
    print(f"[PASS] All {len(REQUIRED_COLS)} required columns present: {REQUIRED_COLS}")

# CP1.4: Year coverage
if YEAR_COL in df.columns:
    years_found = sorted(df[YEAR_COL].unique().to_list())
    missing_years = [y for y in YEARS if y not in years_found]
    if missing_years:
        print(f"[FAIL] Missing expected years: {missing_years}")
        cp1_passed = False
    else:
        print(f"[PASS] All requested years present: {years_found}")

# CP1.5: Null rates for all columns
print("\nNull rates by column:")
for col in df.columns:
    null_count = df[col].null_count()
    null_pct = null_count / len(df) * 100 if len(df) > 0 else 0
    status = "PASS"
    if null_pct > 90:
        status = "FAIL"
        cp1_passed = False
    elif null_pct > 50:
        status = "WARN"
    elif null_pct > 5:
        status = "NOTE"
    print(f"  [{status}] {col}: {null_count:,} nulls ({null_pct:.1f}%)")

# CP1.6: No nulls in identifier columns
id_cols = ["unitid", "year"]
for col in id_cols:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            print(f"[FAIL] Nulls in identifier column {col}: {null_count:,}")
            cp1_passed = False
        else:
            print(f"[PASS] No nulls in identifier column: {col}")

# CP1.7: Flag years warning
if FLAG_YEARS and YEARS and any(y in FLAG_YEARS for y in YEARS):
    print(f"[WARN] FLAG-YEARS: Analysis includes data from flagged years {FLAG_YEARS}. "
          "Document comparability concerns in limitations.")

# CP1.8: Student-faculty ratio specific checks
if "student_faculty_ratio" in df.columns:
    sfr_col = df["student_faculty_ratio"].drop_nulls()
    if len(sfr_col) > 0:
        print(f"\nStudent-faculty ratio distribution:")
        print(f"  Min: {sfr_col.min()}")
        print(f"  Max: {sfr_col.max()}")
        print(f"  Mean: {sfr_col.mean():.1f}")
        print(f"  Median: {sfr_col.median():.1f}")
        # REASONING: SFR values typically range from 1 to 100. Values outside
        # this range suggest data issues or coded missing values.
        extreme_count = sfr_col.filter((sfr_col < 0) | (sfr_col > 200)).len()
        if extreme_count > 0:
            print(f"  [NOTE] {extreme_count:,} extreme values (< 0 or > 200) -- may include coded missing values")

assert cp1_passed, "STOP: CP1 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:46:20
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/06_fetch-sfr.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.6: Fetch IPEDS Student-Faculty Ratio
# ============================================================
#
# Fetching IPEDS Student-Faculty Ratio data...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_student-faculty-ratio.parquet
#   [OK] huggingface: 79,660 rows
#   After filters: 5,836 rows
#
# Shape: 5,836 rows x 4 cols
# Columns: ['unitid', 'year', 'fips', 'student_faculty_ratio']
# Dtypes: [Int64, Int64, Int64, Int64]
#
# Pre-state: 5,836 rows
#
# Coded missing value scan:
#
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_sfr.parquet
#
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#
# Shape: 5,836 rows x 4 cols
# [PASS] 5,836 rows loaded
# [PASS] Row count 5,836 within expected range (3,000-7,000)
# [PASS] All 4 required columns present: ['unitid', 'year', 'fips', 'student_faculty_ratio']
# [PASS] All requested years present: [2020]
#
# Null rates by column:
#   [PASS] unitid: 0 nulls (0.0%)
#   [PASS] year: 0 nulls (0.0%)
#   [PASS] fips: 0 nulls (0.0%)
#   [PASS] student_faculty_ratio: 1 nulls (0.0%)
# [PASS] No nulls in identifier column: unitid
# [PASS] No nulls in identifier column: year
# [WARN] FLAG-YEARS: Analysis includes data from flagged years [2020, 2021]. Document comparability concerns in limitations.
#
# Student-faculty ratio distribution:
#   Min: 1
#   Max: 110
#   Mean: 15.1
#   Median: 14.0
#
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
