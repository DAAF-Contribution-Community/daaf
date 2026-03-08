#!/usr/bin/env python3
"""
Stage 5.6: Fetch IPEDS student-faculty ratio data for year 2020.

Task: fetch-sfr
Wave: 2, Step: 6, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_sfr.parquet
Checkpoint: CP1
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# We fetch the IPEDS student-faculty ratio for year 2020 — the analysis
# target year. Student-faculty ratio is a continuous measure of institutional
# resources that may relate to graduation rates and selectivity.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEAR = 2020  # Single target year per Plan specification

# Dataset path from education-data-query skill's datasets-reference.md.
# IPEDS Student-Faculty Ratio is a single-file dataset (all years in one file),
# covering 2009-2020.
DATASET_PATH = "ipeds/colleges_ipeds_student-faculty-ratio"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_sfr.parquet"

# Columns to select from the student-faculty ratio dataset.
# REASONING: We need unitid for joining to other IPEDS tables, year for
# filtering, and student_faculty_ratio as the key metric. Keeping the
# selection minimal since this is a single-variable supplement to the
# main analysis dataset.
SELECT_COLUMNS = [
    "unitid",
    "year",
    "student_faculty_ratio",
]

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
            Example: "ipeds/colleges_ipeds_student-faculty-ratio"
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


# =============================================================================
# EXECUTION
# =============================================================================

print("=" * 60)
print("Stage 5.6: Fetch IPEDS student-faculty ratio")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS student-faculty ratio and filter to year 2020.
# REASONING: Single-file dataset (all years in one file, 2009-2020). Download
# once, filter locally with Polars for year 2020 only.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
print("\nFetching IPEDS student-faculty ratio...")
df_raw = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)
print(f"After year filter: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# --- Pre-state ---
# Capture state BEFORE column selection so we can see what's available
# and track any filtering impact.
pre_rows = df_raw.shape[0]
print(f"\nPre-state (year={YEAR}): {pre_rows:,} rows")
print(f"Columns available: {len(df_raw.columns)}")
print(f"All column names: {df_raw.columns}")

# --- Select Columns ---
# INTENT: Reduce to only the columns needed for this analysis to minimize
# file size and clarify the analysis scope.
# REASONING: We only need unitid (join key), year (for verification), and
# student_faculty_ratio (the metric of interest). Other columns in this
# dataset are not needed for the graduation rate selectivity analysis.
# ASSUMES: All SELECT_COLUMNS exist in the dataset for year 2020.

# Verify all requested columns exist
available_cols = [c for c in SELECT_COLUMNS if c in df_raw.columns]
missing_cols = [c for c in SELECT_COLUMNS if c not in df_raw.columns]

if missing_cols:
    print(f"\nWARNING: Requested columns not found in data: {missing_cols}")

df_final = df_raw.select(available_cols)
print(f"\nSelected {len(available_cols)} columns: {available_cols}")

# --- Post-state ---
# Capture final state after column selection.
post_rows = df_final.shape[0]
print(f"\nPost-state: {post_rows:,} rows x {df_final.shape[1]} cols")

# Show sample of data
print(f"\nSample rows (first 5):")
print(df_final.head(5))

# Show distribution of student_faculty_ratio
# INTENT: Profile the key metric to verify reasonable values and detect
# anomalies before saving.
if "student_faculty_ratio" in df_final.columns:
    sfr = df_final["student_faculty_ratio"]
    sfr_nonnull = sfr.drop_nulls()
    print(f"\nstudent_faculty_ratio summary:")
    print(f"  Count (non-null): {sfr_nonnull.len():,}")
    print(f"  Null count: {sfr.null_count():,} ({sfr.null_count() / post_rows * 100:.1f}%)")
    print(f"  Min: {sfr_nonnull.min()}")
    print(f"  Max: {sfr_nonnull.max()}")
    print(f"  Mean: {sfr_nonnull.mean():.2f}")
    print(f"  Median: {sfr_nonnull.median():.2f}")
    print(f"  Std: {sfr_nonnull.std():.2f}")

    # Check for anomalous values (negative or extremely high)
    negative_count = sfr_nonnull.filter(sfr_nonnull < 0).len()
    very_high_count = sfr_nonnull.filter(sfr_nonnull > 100).len()
    print(f"  Negative values: {negative_count}")
    print(f"  Values > 100: {very_high_count}")

# Show null counts for all columns
print(f"\nNull counts per column:")
for col in df_final.columns:
    null_ct = df_final[col].null_count()
    null_pct = null_ct / post_rows * 100 if post_rows > 0 else 0
    print(f"  {col}: {null_ct:,} ({null_pct:.1f}%)")

# --- Save ---
# Persist results in parquet format.
# Output path matches the Plan's file specification.
df_final.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# row counts, year coverage, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Year coverage — should be exactly [2020]
years_found = sorted(df_final["year"].unique().to_list())
year_ok = years_found == [YEAR]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year coverage: {years_found} (expected [{YEAR}])")

# CP1.2: Row count within expected range (3,000 - 5,000 per task spec)
# REASONING: IPEDS covers ~6,400 institutions in the directory for 2020,
# but student-faculty ratio may not be reported by all institutions. The
# task expects 3,000-5,000 which is reasonable for degree-granting institutions.
# Note: this dataset includes ALL institution types (not just 4-year public/
# private nonprofit), so row count may be higher than the filtered directory.
row_count = df_final.shape[0]
rows_ok = 3000 <= row_count <= 5000
rows_warn = 2000 <= row_count <= 7000  # Wider acceptable range
print(f"  [{'PASS' if rows_ok else ('WARN' if rows_warn else 'FAIL')}] Row count: {row_count:,} "
      f"(expected 3,000-5,000)")

# CP1.3: Critical columns present
critical_cols = ["unitid", "year", "student_faculty_ratio"]
cols_present = all(c in df_final.columns for c in critical_cols)
missing_critical = [c for c in critical_cols if c not in df_final.columns]
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: "
      f"{'all present' if cols_present else f'missing {missing_critical}'}")

# CP1.4: No nulls in unitid (join key integrity)
unitid_null_count = df_final["unitid"].null_count()
unitid_nulls_ok = unitid_null_count == 0
print(f"  [{'PASS' if unitid_nulls_ok else 'FAIL'}] No nulls in unitid: "
      f"{unitid_null_count} nulls")

# CP1.5: unitid uniqueness (should be one row per institution for single year)
unitid_unique = df_final["unitid"].n_unique() == row_count
print(f"  [{'PASS' if unitid_unique else 'WARN'}] unitid uniqueness: "
      f"{df_final['unitid'].n_unique():,} unique / {row_count:,} rows")

# CP1.6: student_faculty_ratio has reasonable values (positive, typically 5-50)
# REASONING: SFR should be positive for all institutions. Values > 100 are
# extremely unusual. We check for positivity as a critical check, and
# flag the range as informational.
if "student_faculty_ratio" in df_final.columns:
    sfr_nonnull = df_final["student_faculty_ratio"].drop_nulls()
    sfr_min = sfr_nonnull.min()
    sfr_max = sfr_nonnull.max()
    sfr_positive = sfr_min is not None and sfr_min > 0
    sfr_null_rate = df_final["student_faculty_ratio"].null_count() / row_count
    sfr_nulls_ok = sfr_null_rate < 0.50  # Allow up to 50% nulls (some institutions don't report)
    print(f"  [{'PASS' if sfr_positive else 'WARN'}] SFR positive: min={sfr_min}")
    print(f"  [{'PASS' if sfr_nulls_ok else 'WARN'}] SFR null rate: {sfr_null_rate:.1%} "
          f"(threshold: <50%)")
    print(f"  [INFO] SFR range: {sfr_min} to {sfr_max}")

# --- Overall CP1 ---
# REASONING: Critical checks (year, columns, unitid nulls) must all pass.
# Row count outside range is a WARNING, not a failure, since the dataset
# includes all institution types. SFR distribution checks are informational.
critical_passed = all([year_ok, cols_present, unitid_nulls_ok])

if not rows_ok:
    if rows_warn:
        print(f"\n  [WARN] Row count {row_count:,} outside expected range 3,000-5,000 "
              f"but within acceptable range 2,000-7,000")
    else:
        print(f"\n  [WARN] Row count {row_count:,} outside acceptable range")

if not unitid_unique:
    print(f"\n  [WARN] unitid is not fully unique — potential duplicate rows")

assert critical_passed, (
    f"STOP: CP1 critical checks failed — "
    f"year_ok={year_ok}, cols_present={cols_present}, unitid_nulls_ok={unitid_nulls_ok}"
)

cp1_status = "PASSED" if (critical_passed and rows_ok and unitid_unique) else "PASSED (with WARNINGS)"
print(f"\n{'=' * 60}")
print(f"CP1 VALIDATION: {cp1_status}")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:25:00
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/06_fetch-sfr.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.6: Fetch IPEDS student-faculty ratio
# ============================================================
# 
# Fetching IPEDS student-faculty ratio...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_student-faculty-ratio.parquet
#   -> huggingface: 79,660 rows
#   After filters: 5,836 rows
# After year filter: 5,836 rows x 4 cols
# 
# Pre-state (year=2020): 5,836 rows
# Columns available: 4
# All column names: ['unitid', 'year', 'fips', 'student_faculty_ratio']
# 
# Selected 3 columns: ['unitid', 'year', 'student_faculty_ratio']
# 
# Post-state: 5,836 rows x 3 cols
# 
# Sample rows (first 5):
# shape: (5, 3)
# ┌────────┬──────┬───────────────────────┐
# │ unitid ┆ year ┆ student_faculty_ratio │
# │ ---    ┆ ---  ┆ ---                   │
# │ i64    ┆ i64  ┆ i64                   │
# ╞════════╪══════╪═══════════════════════╡
# │ 100654 ┆ 2020 ┆ 18                    │
# │ 100663 ┆ 2020 ┆ 20                    │
# │ 100690 ┆ 2020 ┆ 13                    │
# │ 100706 ┆ 2020 ┆ 19                    │
# │ 100724 ┆ 2020 ┆ 15                    │
# └────────┴──────┴───────────────────────┘
# 
# student_faculty_ratio summary:
#   Count (non-null): 5,835
#   Null count: 1 (0.0%)
#   Min: 1
#   Max: 110
#   Mean: 15.12
#   Median: 14.00
#   Std: 7.31
#   Negative values: 0
#   Values > 100: 1
# 
# Null counts per column:
#   unitid: 0 (0.0%)
#   year: 0 (0.0%)
#   student_faculty_ratio: 1 (0.0%)
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-02-15_ipeds_sfr.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year coverage: [2020] (expected [2020])
#   [WARN] Row count: 5,836 (expected 3,000-5,000)
#   [PASS] Critical columns present: all present
#   [PASS] No nulls in unitid: 0 nulls
#   [PASS] unitid uniqueness: 5,836 unique / 5,836 rows
#   [PASS] SFR positive: min=1
#   [PASS] SFR null rate: 0.0% (threshold: <50%)
#   [INFO] SFR range: 1 to 110
# 
#   [WARN] Row count 5,836 outside expected range 3,000-5,000 but within acceptable range 2,000-7,000
# 
# ============================================================
# CP1 VALIDATION: PASSED (with WARNINGS)
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
