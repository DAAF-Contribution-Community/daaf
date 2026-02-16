#!/usr/bin/env python3
"""
Stage 5.7: Fetch IPEDS fall retention rates for year 2020.

Task: fetch-retention
Wave: 2, Step: 7, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_retention.parquet
Checkpoint: CP1

Fetches the IPEDS fall-retention dataset and filters to:
  - year == 2020
  - ftpt == 1 (full-time students only)
  - Selects: unitid, year, retention_rate
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# We fetch IPEDS fall retention rates for year 2020, filtering to full-time
# students (ftpt==1) to align with the graduation rate cohort definition
# (first-time, full-time students). Retention rate is a key predictor variable
# for the selectivity analysis.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEAR = 2020  # Single target year per Plan specification

# Dataset path from education-data-query skill's datasets-reference.md.
# IPEDS Fall Retention is a single-file dataset (years 2003-2020 in one file).
DATASET_PATH = "ipeds/colleges_ipeds_fall-retention"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_retention.parquet"

# Columns to select after filtering.
# REASONING: We only need unitid (join key), year (for verification), and
# retention_rate (the analysis variable). Keeping the selection minimal
# avoids carrying unnecessary columns through downstream joins.
SELECT_COLUMNS = ["unitid", "year", "retention_rate"]

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
print("Stage 5.7: Fetch IPEDS fall retention rates")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS fall-retention dataset and filter to year 2020.
# REASONING: Single-file dataset (all years in one file, 2003-2020). Download
# once, filter locally with Polars for year 2020 only.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
print("\nFetching IPEDS fall retention...")
df_raw = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)
print(f"After year filter: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# --- Pre-state ---
# Capture state BEFORE applying local filters so we can track how many
# institutions are removed by each filter condition.
pre_rows = df_raw.shape[0]
print(f"\nPre-state (year={YEAR}, before ftpt filter): {pre_rows:,} rows")
print(f"Columns available: {len(df_raw.columns)}")
print(f"All column names: {df_raw.columns}")

# --- Explore ftpt values ---
# INTENT: Understand the ftpt column distribution before filtering, so we can
# verify that ftpt==1 correctly selects full-time students.
# REASONING: Portal uses integer encoding. We need to confirm ftpt==1 means
# full-time before filtering. Also check if the column exists.
if "ftpt" in df_raw.columns:
    print(f"\nftpt distribution:")
    print(df_raw.group_by("ftpt").len().sort("ftpt"))
else:
    print("\nWARNING: 'ftpt' column not found in dataset!")
    print("Available columns that might be relevant:")
    for c in df_raw.columns:
        if "ft" in c.lower() or "pt" in c.lower() or "time" in c.lower():
            print(f"  {c}")

# --- Filter ---
# INTENT: Filter to full-time students only (ftpt==1) per Plan specification.
# REASONING: The graduation rate cohort is defined as first-time, full-time
# students. Using full-time retention rate ensures consistency with the GRS
# cohort definition used elsewhere in this analysis.
# ASSUMES: ftpt==1 represents full-time students in the IPEDS fall-retention
# dataset (integer encoding per Portal conventions).
if "ftpt" in df_raw.columns:
    df_filtered = df_raw.filter(pl.col("ftpt") == 1)
    print(f"\nAfter ftpt == 1 (full-time only): {df_filtered.shape[0]:,} rows "
          f"(removed {pre_rows - df_filtered.shape[0]:,})")
else:
    # If ftpt column doesn't exist, proceed with all rows and log warning
    print("\nWARNING: No ftpt column found. Proceeding with all rows.")
    df_filtered = df_raw

# --- Select Columns ---
# INTENT: Reduce to only unitid, year, and retention_rate to minimize file
# size and clarify the analysis scope.
# REASONING: Only retention_rate is needed from this dataset. unitid is the
# join key, year is for verification.
# ASSUMES: All SELECT_COLUMNS exist in the dataset.

# Verify all requested columns exist
available_cols = [c for c in SELECT_COLUMNS if c in df_filtered.columns]
missing_cols = [c for c in SELECT_COLUMNS if c not in df_filtered.columns]

if missing_cols:
    print(f"\nWARNING: Requested columns not found in data: {missing_cols}")
    # Show all columns to help diagnose
    print(f"Available columns: {df_filtered.columns}")

df_final = df_filtered.select(available_cols)
print(f"\nSelected {len(available_cols)} columns: {available_cols}")

# --- Post-state ---
# Capture final state after all filters and column selection.
post_rows = df_final.shape[0]
print(f"\nPost-state: {post_rows:,} rows x {df_final.shape[1]} cols")
print(f"Row change from pre-state: {post_rows - pre_rows:+,} "
      f"({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# Show sample of data
print(f"\nSample rows (first 5):")
print(df_final.head(5))

# Show retention_rate summary statistics
print(f"\nretention_rate summary statistics:")
if "retention_rate" in df_final.columns:
    desc = df_final["retention_rate"].describe()
    print(desc)
    # Also show key percentiles for more detail
    non_null = df_final.filter(pl.col("retention_rate").is_not_null())
    if non_null.shape[0] > 0:
        print(f"\nretention_rate distribution (non-null only):")
        print(f"  Count (non-null): {non_null.shape[0]:,}")
        print(f"  Min:    {non_null['retention_rate'].min()}")
        print(f"  P25:    {non_null['retention_rate'].quantile(0.25)}")
        print(f"  Median: {non_null['retention_rate'].quantile(0.50)}")
        print(f"  P75:    {non_null['retention_rate'].quantile(0.75)}")
        print(f"  Max:    {non_null['retention_rate'].max()}")
        print(f"  Mean:   {non_null['retention_rate'].mean():.2f}")
        print(f"  Std:    {non_null['retention_rate'].std():.2f}")

# Show null counts for all columns
print(f"\nNull counts per column:")
for col in df_final.columns:
    null_ct = df_final[col].null_count()
    null_pct = null_ct / post_rows * 100 if post_rows > 0 else 0
    print(f"  {col}: {null_ct:,} ({null_pct:.1f}%)")

# Check unitid uniqueness (should be 1:1 after ftpt filter)
unitid_unique_ct = df_final["unitid"].n_unique()
print(f"\nunitid uniqueness: {unitid_unique_ct:,} unique / {post_rows:,} rows")
if unitid_unique_ct != post_rows:
    print("WARNING: unitid is not unique - potential duplicate rows per institution")
    # Show examples of duplicates
    dup_unitids = (
        df_final.group_by("unitid").len()
        .filter(pl.col("len") > 1)
        .sort("len", descending=True)
        .head(5)
    )
    print(f"Top duplicate unitids:")
    print(dup_unitids)

# --- Save ---
# Persist results in parquet format.
# Output paths match the Plan's file specification.
df_final.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# Verify file on disk
import os
file_size = os.path.getsize(OUTPUT_PARQUET)
print(f"File size: {file_size:,} bytes")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# row counts, year coverage, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Year coverage -- should be exactly [2020]
years_found = sorted(df_final["year"].unique().to_list())
year_ok = years_found == [YEAR]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year coverage: {years_found} (expected [{YEAR}])")

# CP1.2: Row count within expected range (2,000 - 4,000 per task spec)
row_count = df_final.shape[0]
rows_ok = 2000 <= row_count <= 4000
print(f"  [{'PASS' if rows_ok else 'WARN'}] Row count: {row_count:,} "
      f"(expected 2,000-4,000)")

# CP1.3: Critical columns present
critical_cols = ["unitid", "year", "retention_rate"]
cols_present = all(c in df_final.columns for c in critical_cols)
missing_critical = [c for c in critical_cols if c not in df_final.columns]
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: "
      f"{'all present' if cols_present else f'missing {missing_critical}'}")

# CP1.4: No nulls in unitid
unitid_null_ct = df_final["unitid"].null_count()
unitid_ok = unitid_null_ct == 0
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] unitid nulls: {unitid_null_ct:,} "
      f"(expected 0)")

# CP1.5: retention_rate range check
# REASONING: Retention rate should be a proportion (0-1) or percentage (0-100).
# We check which scale is used and verify values are in a reasonable range.
if "retention_rate" in df_final.columns:
    rr_non_null = df_final.filter(pl.col("retention_rate").is_not_null())
    if rr_non_null.shape[0] > 0:
        rr_min = rr_non_null["retention_rate"].min()
        rr_max = rr_non_null["retention_rate"].max()
        # Determine scale: if max > 1, it's likely percentage (0-100)
        if rr_max > 1:
            rr_range_ok = 0 <= rr_min and rr_max <= 100
            scale = "percentage (0-100)"
        else:
            rr_range_ok = 0 <= rr_min and rr_max <= 1
            scale = "proportion (0-1)"
        print(f"  [{'PASS' if rr_range_ok else 'WARN'}] retention_rate range: "
              f"{rr_min} to {rr_max} ({scale})")
    else:
        rr_range_ok = False
        print(f"  [FAIL] retention_rate: all values are null")
else:
    rr_range_ok = False
    print(f"  [FAIL] retention_rate column not found")

# CP1.6: retention_rate null rate
rr_null_ct = df_final["retention_rate"].null_count() if "retention_rate" in df_final.columns else post_rows
rr_null_pct = rr_null_ct / post_rows * 100 if post_rows > 0 else 100
rr_nulls_ok = rr_null_pct < 50  # Allow some nulls but flag if > 50%
print(f"  [{'PASS' if rr_nulls_ok else 'WARN'}] retention_rate null rate: "
      f"{rr_null_ct:,} ({rr_null_pct:.1f}%)")

# CP1.7: unitid uniqueness (should be 1:1 mapping after ftpt filter)
unitid_unique = df_final["unitid"].n_unique() == row_count
print(f"  [{'PASS' if unitid_unique else 'WARN'}] unitid uniqueness: "
      f"{df_final['unitid'].n_unique():,} unique / {row_count:,} rows")

# --- Overall CP1 ---
# REASONING: Critical checks (year, columns, unitid nulls) must all pass.
# Row count outside range, retention_rate nulls, and unitid uniqueness
# are warnings, not failures, since they may reflect legitimate data patterns.
critical_passed = all([year_ok, cols_present, unitid_ok])

if not rows_ok:
    print(f"\n  [WARN] Row count {row_count:,} outside expected range 2,000-4,000")
if not unitid_unique:
    print(f"\n  [WARN] unitid is not fully unique -- potential duplicate rows")
if not rr_nulls_ok:
    print(f"\n  [WARN] retention_rate null rate is high ({rr_null_pct:.1f}%)")

assert critical_passed, (
    f"STOP: CP1 critical checks failed -- "
    f"year_ok={year_ok}, cols_present={cols_present}, unitid_ok={unitid_ok}"
)

cp1_status = "PASSED" if (critical_passed and rows_ok and unitid_unique and rr_nulls_ok) else "PASSED (with WARNINGS)"
print(f"\n{'=' * 60}")
print(f"CP1 VALIDATION: {cp1_status}")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:25:30
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage5_fetch/07_fetch-retention.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.7: Fetch IPEDS fall retention rates
# ============================================================
# 
# Fetching IPEDS fall retention...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_fall-retention.parquet
#   -> huggingface: 324,778 rows
#   After filters: 17,508 rows
# After year filter: 17,508 rows x 9 cols
# 
# Pre-state (year=2020, before ftpt filter): 17,508 rows
# Columns available: 9
# All column names: ['unitid', 'year', 'fips', 'ftpt', 'retention_rate', 'returning_students', 'prev_cohort', 'prev_exclusions', 'prev_cohort_adj']
# 
# ftpt distribution:
# shape: (3, 2)
# ┌──────┬──────┐
# │ ftpt ┆ len  │
# │ ---  ┆ ---  │
# │ i64  ┆ u32  │
# ╞══════╪══════╡
# │ 1    ┆ 5836 │
# │ 2    ┆ 5836 │
# │ 99   ┆ 5836 │
# └──────┴──────┘
# 
# After ftpt == 1 (full-time only): 5,836 rows (removed 11,672)
# 
# Selected 3 columns: ['unitid', 'year', 'retention_rate']
# 
# Post-state: 5,836 rows x 3 cols
# Row change from pre-state: -11,672 (-66.7%)
# 
# Sample rows (first 5):
# shape: (5, 3)
# ┌────────┬──────┬────────────────┐
# │ unitid ┆ year ┆ retention_rate │
# │ ---    ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ f64            │
# ╞════════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 0.54           │
# │ 100663 ┆ 2020 ┆ 0.86           │
# │ 100690 ┆ 2020 ┆ 0.5            │
# │ 100706 ┆ 2020 ┆ 0.82           │
# │ 100724 ┆ 2020 ┆ 0.62           │
# └────────┴──────┴────────────────┘
# 
# retention_rate summary statistics:
# shape: (9, 2)
# ┌────────────┬──────────┐
# │ statistic  ┆ value    │
# │ ---        ┆ ---      │
# │ str        ┆ f64      │
# ╞════════════╪══════════╡
# │ count      ┆ 5182.0   │
# │ null_count ┆ 654.0    │
# │ mean       ┆ 0.706521 │
# │ std        ┆ 0.187062 │
# │ min        ┆ 0.0      │
# │ 25%        ┆ 0.6      │
# │ 50%        ┆ 0.73     │
# │ 75%        ┆ 0.83     │
# │ max        ┆ 1.0      │
# └────────────┴──────────┘
# 
# retention_rate distribution (non-null only):
#   Count (non-null): 5,182
#   Min:    0.0
#   P25:    0.6
#   Median: 0.73
#   P75:    0.83
#   Max:    1.0
#   Mean:   0.71
#   Std:    0.19
# 
# Null counts per column:
#   unitid: 0 (0.0%)
#   year: 0 (0.0%)
#   retention_rate: 654 (11.2%)
# 
# unitid uniqueness: 5,836 unique / 5,836 rows
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/2026-02-15_ipeds_retention.parquet
# File size: 17,462 bytes
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year coverage: [2020] (expected [2020])
#   [WARN] Row count: 5,836 (expected 2,000-4,000)
#   [PASS] Critical columns present: all present
#   [PASS] unitid nulls: 0 (expected 0)
#   [PASS] retention_rate range: 0.0 to 1.0 (proportion (0-1))
#   [PASS] retention_rate null rate: 654 (11.2%)
#   [PASS] unitid uniqueness: 5,836 unique / 5,836 rows
# 
#   [WARN] Row count 5,836 outside expected range 2,000-4,000
# 
# ============================================================
# CP1 VALIDATION: PASSED (with WARNINGS)
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
