#!/usr/bin/env python3
"""
Stage 5.8: Fetch Scorecard earnings data (supplementary).

Task: fetch-scorecard
Wave: 2, Step: 8, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_scorecard_earnings.parquet
Checkpoint: CP1

Notes:
  - Scorecard data is SUPPLEMENTARY — Title IV coverage bias means 30-50%
    coverage at elite institutions. Lower row counts are acceptable.
  - Column names in Scorecard may differ from IPEDS conventions.
  - years_after_entry filtering applied if column exists.
  - Most recent year with data is selected dynamically.
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants for Scorecard earnings fetch. The Scorecard
# (College Scorecard) provides post-college earnings data for Title IV
# participants. This is supplementary data — not all institutions are
# covered, especially elite schools with lower Title IV participation.
# Analysis year is 2020, but Scorecard may have different year availability;
# we select the most recent year with data.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

# Dataset path from education-data-query skill's datasets-reference.md.
# Scorecard Earnings is a single-file dataset (all years in one file).
DATASET_PATH = "scorecard/colleges_scorecard_earnings"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_scorecard_earnings.parquet"

# Target analysis year — we prefer 2020 but will use most recent available.
# REASONING: The rest of the analysis uses 2020 data. We try to match, but
# Scorecard earnings may lag or have different year coverage. We select the
# most recent year available and document which year was used.
TARGET_YEAR = 2020

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
            Example: "scorecard/colleges_scorecard_earnings"
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
print("Stage 5.8: Fetch Scorecard earnings (supplementary)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download Scorecard earnings dataset (all years) and inspect
# available columns and years before filtering.
# REASONING: Single-file dataset. Download once, inspect schema, then
# filter locally. We don't filter by year during fetch because we need
# to discover which years are available first.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains
# "year" and "unitid" columns at minimum.
print("\nFetching Scorecard earnings...")
df_raw = fetch_from_mirrors(path=DATASET_PATH)
print(f"Full dataset: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# --- Inspect Available Columns ---
# INTENT: Document all columns in the Scorecard earnings dataset so we
# can identify the correct column names for earnings and counts.
# REASONING: Scorecard may use different column names than IPEDS.
# The task spec asks for earnings_med and count_working, but the actual
# column names may differ. We inspect and adapt.
print(f"\nAll columns ({len(df_raw.columns)}):")
for col in sorted(df_raw.columns):
    print(f"  {col} ({df_raw[col].dtype})")

# --- Inspect Available Years ---
# INTENT: Determine which years have data and select the most recent.
# REASONING: We prefer 2020 to match other datasets but Scorecard may
# have different year availability. Select most recent for maximum
# relevance.
print(f"\nYear distribution:")
year_counts = df_raw.group_by("year").len().sort("year")
print(year_counts)

available_years = sorted(df_raw["year"].unique().to_list())
print(f"\nAvailable years: {available_years}")

# Select the target year if available; otherwise most recent
# REASONING: Using TARGET_YEAR (2020) if available ensures consistency
# with the rest of the analysis. If not available, the most recent year
# provides the most current earnings data.
if TARGET_YEAR in available_years:
    selected_year = TARGET_YEAR
    print(f"\nTarget year {TARGET_YEAR} is available -- using it.")
else:
    selected_year = max(available_years)
    print(f"\nTarget year {TARGET_YEAR} NOT available. Using most recent: {selected_year}")

# --- Filter to Selected Year ---
# INTENT: Restrict to the single selected year for the analysis.
df_year = df_raw.filter(pl.col("year") == selected_year)
print(f"\nAfter year filter ({selected_year}): {df_year.shape[0]:,} rows")

# --- Inspect years_after_entry if present ---
# INTENT: Check for a years_after_entry column to filter to 10-year
# post-entry earnings (the standard Scorecard metric for long-term
# outcomes).
# REASONING: If present, filtering to years_after_entry == 10 gives
# the most commonly cited earnings metric. If not present, document
# this deviation.
if "years_after_entry" in df_year.columns:
    yae_values = sorted(df_year["years_after_entry"].drop_nulls().unique().to_list())
    print(f"\nyears_after_entry values: {yae_values}")
    yae_counts = df_year.group_by("years_after_entry").len().sort("years_after_entry")
    print(yae_counts)

    if 10 in yae_values:
        df_year = df_year.filter(pl.col("years_after_entry") == 10)
        print(f"Filtered to years_after_entry == 10: {df_year.shape[0]:,} rows")
    else:
        print(f"WARNING: years_after_entry == 10 not available. Using all values.")
else:
    print("\nyears_after_entry column NOT present in dataset. Proceeding without filter.")

# --- Pre-state ---
# Capture state after year/yae filters but before column selection.
pre_rows = df_year.shape[0]
print(f"\nPre-state (after year/yae filters): {pre_rows:,} rows")
print(f"Columns available: {len(df_year.columns)}")

# --- Identify and Select Columns ---
# INTENT: Select the columns needed for the analysis. The task spec asks
# for: unitid, year, earnings_med, count_working. We adapt to actual
# column names found in the data.
#
# REASONING: Scorecard column names may not match exactly. We search for
# columns containing "earn" or "count" or "working" to find the right ones.
# We also keep any years_after_entry column for documentation.
#
# ASSUMES: unitid and year exist (standard Portal columns).

# Find earnings-related columns
earnings_cols = [c for c in df_year.columns if "earn" in c.lower()]
count_cols = [c for c in df_year.columns if "count" in c.lower() or "working" in c.lower()]
print(f"\nEarnings-related columns: {earnings_cols}")
print(f"Count-related columns: {count_cols}")

# Build selection list based on what actually exists
# REASONING: We prioritize the exact column names from the task spec
# (earnings_med, count_working) but fall back to alternatives if not found.
select_cols = ["unitid", "year"]

# Add years_after_entry if it exists
if "years_after_entry" in df_year.columns:
    select_cols.append("years_after_entry")

# Add earnings columns -- prefer earnings_med, but include all earnings cols
# for inspection. We'll narrow down after seeing the data.
for col in earnings_cols:
    if col not in select_cols:
        select_cols.append(col)

# Add count columns
for col in count_cols:
    if col not in select_cols:
        select_cols.append(col)

# Verify all selected columns exist
available_select = [c for c in select_cols if c in df_year.columns]
missing_select = [c for c in select_cols if c not in df_year.columns]
if missing_select:
    print(f"\nWARNING: These columns not found: {missing_select}")

df_final = df_year.select(available_select)
print(f"\nSelected {len(available_select)} columns: {available_select}")

# --- Post-state ---
# Capture final state after all filters and column selection.
post_rows = df_final.shape[0]
print(f"\nPost-state: {post_rows:,} rows x {df_final.shape[1]} cols")
print(f"Row change from pre-state: {post_rows - pre_rows:+,}")

# Show sample of data
print(f"\nSample rows (first 5):")
print(df_final.head(5))

# Show null counts for all columns
print(f"\nNull counts per column:")
for col in df_final.columns:
    null_ct = df_final[col].null_count()
    null_pct = null_ct / post_rows * 100 if post_rows > 0 else 0
    print(f"  {col}: {null_ct:,} ({null_pct:.1f}%)")

# Show summary stats for earnings columns
print(f"\nSummary statistics for earnings/count columns:")
numeric_cols = [c for c in df_final.columns if c not in ["unitid", "year", "years_after_entry"]]
for col in numeric_cols:
    col_data = df_final[col].drop_nulls()
    if len(col_data) > 0 and col_data.dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]:
        print(f"\n  {col}:")
        print(f"    count: {len(col_data):,}")
        print(f"    mean:  {col_data.mean():,.0f}")
        print(f"    std:   {col_data.std():,.0f}")
        print(f"    min:   {col_data.min():,}")
        print(f"    25%:   {col_data.quantile(0.25):,}")
        print(f"    50%:   {col_data.quantile(0.50):,}")
        print(f"    75%:   {col_data.quantile(0.75):,}")
        print(f"    max:   {col_data.max():,}")

# --- Save ---
# Persist results in parquet format.
# Output paths match the Plan's file specification.
df_final.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets expectations for
# row counts, critical columns, and identifier integrity.
#
# NOTE: This is SUPPLEMENTARY data with Title IV coverage bias.
# Row count expectations are lower (2,000-4,000) compared to IPEDS
# datasets because not all institutions participate in Title IV programs,
# and elite institutions in particular may have lower coverage (30-50%).
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Year documented
print(f"  [INFO] Year used: {selected_year} (target was {TARGET_YEAR})")
year_match = selected_year == TARGET_YEAR
print(f"  [{'PASS' if year_match else 'WARN'}] Year matches target: {year_match}")

# CP1.2: Row count within expected range (2,000-4,000 -- supplementary, lower acceptable)
row_count = df_final.shape[0]
rows_ok = 2000 <= row_count <= 4000
rows_nonzero = row_count > 0
print(f"  [{'PASS' if rows_ok else 'WARN'}] Row count: {row_count:,} "
      f"(expected 2,000-4,000 for supplementary data)")

# CP1.3: Critical columns present (unitid required, earnings preferred)
critical_cols = ["unitid"]
cols_present = all(c in df_final.columns for c in critical_cols)
missing_critical = [c for c in critical_cols if c not in df_final.columns]
has_earnings = any("earn" in c.lower() for c in df_final.columns)
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns (unitid): "
      f"{'present' if cols_present else f'missing {missing_critical}'}")
print(f"  [{'PASS' if has_earnings else 'FAIL'}] Earnings column present: {has_earnings}")

# CP1.4: No nulls in unitid
unitid_null_rate = df_final["unitid"].null_count() / row_count if row_count > 0 else 1
unitid_ok = unitid_null_rate == 0
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] No nulls in unitid: "
      f"null rate = {unitid_null_rate:.1%}")

# CP1.5: unitid uniqueness (should be one row per institution if filtered
# to single year and years_after_entry)
unitid_unique_count = df_final["unitid"].n_unique()
unitid_unique = unitid_unique_count == row_count
print(f"  [{'PASS' if unitid_unique else 'WARN'}] unitid uniqueness: "
      f"{unitid_unique_count:,} unique / {row_count:,} rows")

# CP1.6: Earnings values in reasonable range (positive, typically $20k-$150k)
# REASONING: Median earnings 10 years post-entry for college graduates
# should be positive and generally fall in the $20,000-$150,000 range.
# Values outside this range may indicate data quality issues.
if has_earnings:
    earn_col = [c for c in df_final.columns if "earn" in c.lower()][0]
    earn_data = df_final[earn_col].drop_nulls()
    if len(earn_data) > 0 and earn_data.dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]:
        earn_min = earn_data.min()
        earn_max = earn_data.max()
        earn_positive = earn_min > 0 if earn_min is not None else False
        earn_reasonable = earn_max < 500000 if earn_max is not None else False
        print(f"  [{'PASS' if earn_positive else 'WARN'}] Earnings positive: "
              f"min = {earn_min:,}")
        print(f"  [{'PASS' if earn_reasonable else 'WARN'}] Earnings reasonable: "
              f"max = {earn_max:,}")
    else:
        print(f"  [WARN] Earnings column '{earn_col}' has no numeric data to validate")

# CP1.7: Title IV coverage bias noted
print(f"\n  [INFO] COVERAGE NOTE: Scorecard data covers Title IV recipients only.")
print(f"  [INFO] Elite institutions may have 30-50% coverage bias.")
print(f"  [INFO] This data is supplementary and should be used with caveats.")

# --- Overall CP1 ---
# REASONING: Critical checks (unitid present, no unitid nulls, has earnings,
# nonzero rows) must all pass. Row count outside range and year mismatch
# are WARNINGs, not failures, since this is supplementary data with known
# coverage limitations. unitid uniqueness is also a warning.
critical_passed = all([cols_present, unitid_ok, has_earnings, rows_nonzero])

if not rows_ok:
    print(f"\n  [WARN] Row count {row_count:,} outside expected range 2,000-4,000")
if not year_match:
    print(f"\n  [WARN] Using year {selected_year} instead of target {TARGET_YEAR}")
if not unitid_unique:
    print(f"\n  [WARN] unitid is not fully unique -- potential duplicate rows "
          f"(may indicate multiple years_after_entry values)")

assert critical_passed, (
    f"STOP: CP1 critical checks failed -- "
    f"cols_present={cols_present}, unitid_ok={unitid_ok}, "
    f"has_earnings={has_earnings}, rows_nonzero={rows_nonzero}"
)

cp1_status = "PASSED" if (critical_passed and rows_ok and unitid_unique) else "PASSED (with WARNINGS)"
print(f"\n{'=' * 60}")
print(f"CP1 VALIDATION: {cp1_status}")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:25:49
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/08_fetch-scorecard.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.8: Fetch Scorecard earnings (supplementary)
# ============================================================
# 
# Fetching Scorecard earnings...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/scorecard/colleges_scorecard_earnings.parquet
#   -> huggingface: 203,066 rows
#   After filters: 203,066 rows
# Full dataset: 203,066 rows x 33 cols
# 
# All columns (33):
#   cohort_year (Int64)
#   count_not_working (Int64)
#   count_working (Int64)
#   count_working_dep (Int64)
#   count_working_dep_lowinc (Int64)
#   count_working_female (Int64)
#   count_working_highinc (Int64)
#   count_working_ind (Int64)
#   count_working_lowinc (Int64)
#   count_working_male (Int64)
#   count_working_midinc (Int64)
#   earnings_dep_lowinc_mean (Int64)
#   earnings_dep_mean (Int64)
#   earnings_female_mean (Int64)
#   earnings_greater_than_25k_pct (Float64)
#   earnings_highinc_mean (Int64)
#   earnings_ind_mean (Int64)
#   earnings_lowinc_mean (Int64)
#   earnings_male_mean (Int64)
#   earnings_mean (Int64)
#   earnings_med (Int64)
#   earnings_midinc_mean (Int64)
#   earnings_pct10 (Int64)
#   earnings_pct25 (Int64)
#   earnings_pct75 (Int64)
#   earnings_pct90 (Int64)
#   earnings_sd (Int64)
#   fips (Int64)
#   opeid (String)
#   opeid6 (Int64)
#   unitid (Int64)
#   year (Int64)
#   years_after_entry (Int64)
# 
# Year distribution:
# shape: (13, 2)
# ┌──────┬───────┐
# │ year ┆ len   │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2003 ┆ 6189  │
# │ 2004 ┆ 6193  │
# │ 2005 ┆ 12635 │
# │ 2006 ┆ 12610 │
# │ 2007 ┆ 19070 │
# │ …    ┆ …     │
# │ 2011 ┆ 20751 │
# │ 2012 ┆ 21015 │
# │ 2013 ┆ 21075 │
# │ 2014 ┆ 20853 │
# │ 2018 ┆ 16761 │
# └──────┴───────┘
# 
# Available years: [2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2018]
# 
# Target year 2020 NOT available. Using most recent: 2018
# 
# After year filter (2018): 16,761 rows
# 
# years_after_entry values: [6, 8, 10]
# shape: (3, 2)
# ┌───────────────────┬──────┐
# │ years_after_entry ┆ len  │
# │ ---               ┆ ---  │
# │ i64               ┆ u32  │
# ╞═══════════════════╪══════╡
# │ 6                 ┆ 5792 │
# │ 8                 ┆ 5593 │
# │ 10                ┆ 5376 │
# └───────────────────┴──────┘
# Filtered to years_after_entry == 10: 5,376 rows
# 
# Pre-state (after year/yae filters): 5,376 rows
# Columns available: 33
# 
# Earnings-related columns: ['earnings_mean', 'earnings_sd', 'earnings_greater_than_25k_pct', 'earnings_med', 'earnings_pct10', 'earnings_pct25', 'earnings_pct75', 'earnings_pct90', 'earnings_lowinc_mean', 'earnings_midinc_mean', 'earnings_highinc_mean', 'earnings_dep_lowinc_mean', 'earnings_dep_mean', 'earnings_ind_mean', 'earnings_female_mean', 'earnings_male_mean']
# Count-related columns: ['count_not_working', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep_lowinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
# 
# Selected 29 columns: ['unitid', 'year', 'years_after_entry', 'earnings_mean', 'earnings_sd', 'earnings_greater_than_25k_pct', 'earnings_med', 'earnings_pct10', 'earnings_pct25', 'earnings_pct75', 'earnings_pct90', 'earnings_lowinc_mean', 'earnings_midinc_mean', 'earnings_highinc_mean', 'earnings_dep_lowinc_mean', 'earnings_dep_mean', 'earnings_ind_mean', 'earnings_female_mean', 'earnings_male_mean', 'count_not_working', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep_lowinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
# 
# Post-state: 5,376 rows x 29 cols
# Row change from pre-state: +0
# 
# Sample rows (first 5):
# shape: (5, 29)
# ┌────────┬──────┬─────────────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ year ┆ years_after ┆ earnings_m ┆ … ┆ count_work ┆ count_work ┆ count_work ┆ count_work │
# │ ---    ┆ ---  ┆ _entry      ┆ ean        ┆   ┆ ing_dep    ┆ ing_ind    ┆ ing_female ┆ ing_male   │
# │ i64    ┆ i64  ┆ ---         ┆ ---        ┆   ┆ ---        ┆ ---        ┆ ---        ┆ ---        │
# │        ┆      ┆ i64         ┆ i64        ┆   ┆ i64        ┆ i64        ┆ i64        ┆ i64        │
# ╞════════╪══════╪═════════════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 867        ┆ 96         ┆ 481        ┆ 483        │
# │ 100663 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1990       ┆ 875        ┆ 1773       ┆ 1091       │
# │ 100690 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ null       ┆ 131        ┆ 78         ┆ 63         │
# │ 100706 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1042       ┆ 473        ┆ 736        ┆ 779        │
# │ 100724 ┆ 2018 ┆ 10          ┆ null       ┆ … ┆ 1911       ┆ 305        ┆ 1182       ┆ 1034       │
# └────────┴──────┴─────────────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘
# 
# Null counts per column:
#   unitid: 0 (0.0%)
#   year: 0 (0.0%)
#   years_after_entry: 0 (0.0%)
#   earnings_mean: 5,376 (100.0%)
#   earnings_sd: 5,376 (100.0%)
#   earnings_greater_than_25k_pct: 5,376 (100.0%)
#   earnings_med: 0 (0.0%)
#   earnings_pct10: 5,376 (100.0%)
#   earnings_pct25: 137 (2.5%)
#   earnings_pct75: 49 (0.9%)
#   earnings_pct90: 5,376 (100.0%)
#   earnings_lowinc_mean: 5,376 (100.0%)
#   earnings_midinc_mean: 5,376 (100.0%)
#   earnings_highinc_mean: 5,376 (100.0%)
#   earnings_dep_lowinc_mean: 5,376 (100.0%)
#   earnings_dep_mean: 5,376 (100.0%)
#   earnings_ind_mean: 5,376 (100.0%)
#   earnings_female_mean: 5,376 (100.0%)
#   earnings_male_mean: 5,376 (100.0%)
#   count_not_working: 5,376 (100.0%)
#   count_working: 0 (0.0%)
#   count_working_lowinc: 188 (3.5%)
#   count_working_midinc: 770 (14.3%)
#   count_working_highinc: 1,828 (34.0%)
#   count_working_dep_lowinc: 5,376 (100.0%)
#   count_working_dep: 515 (9.6%)
#   count_working_ind: 474 (8.8%)
#   count_working_female: 236 (4.4%)
#   count_working_male: 954 (17.7%)
# 
# Summary statistics for earnings/count columns:
# 
#   earnings_med:
#     count: 5,376
#     mean:  39,092
#     std:   14,741
#     min:   10,939
#     25%:   28,327.0
#     50%:   36,781.0
#     75%:   46,035.0
#     max:   132,969
# 
#   earnings_pct25:
#     count: 5,239
#     mean:  23,821
#     std:   10,850
#     min:   2,474
#     25%:   15,795.0
#     50%:   21,565.0
#     75%:   29,654.0
#     max:   88,530
# 
#   earnings_pct75:
#     count: 5,327
#     mean:  57,782
#     std:   20,424
#     min:   17,200
#     25%:   42,914.0
#     50%:   54,752.0
#     75%:   67,971.0
#     max:   175,675
# 
#   count_working:
#     count: 5,376
#     mean:  2,470
#     std:   10,382
#     min:   16
#     25%:   167.0
#     50%:   626.0
#     75%:   1,741.0
#     max:   164,390
# 
#   count_working_lowinc:
#     count: 5,188
#     mean:  1,428
#     std:   6,131
#     min:   16
#     25%:   97.0
#     50%:   327.0
#     75%:   1,086.0
#     max:   95,499
# 
#   count_working_midinc:
#     count: 4,606
#     mean:  850
#     std:   3,557
#     min:   16
#     25%:   82.0
#     50%:   221.0
#     75%:   590.0
#     max:   52,661
# 
#   count_working_highinc:
#     count: 3,548
#     mean:  546
#     std:   1,504
#     min:   16
#     25%:   59.0
#     50%:   154.0
#     75%:   428.0
#     max:   16,229
# 
#   count_working_dep:
#     count: 4,861
#     mean:  1,103
#     std:   2,242
#     min:   16
#     25%:   121.0
#     50%:   405.0
#     75%:   1,081.0
#     max:   19,608
# 
#   count_working_ind:
#     count: 4,902
#     mean:  1,613
#     std:   9,683
#     min:   16
#     25%:   84.0
#     50%:   282.0
#     75%:   798.0
#     max:   151,296
# 
#   count_working_female:
#     count: 5,140
#     mean:  1,591
#     std:   6,994
#     min:   16
#     25%:   127.0
#     50%:   404.0
#     75%:   1,167.0
#     max:   110,003
# 
#   count_working_male:
#     count: 4,422
#     mean:  1,151
#     std:   4,011
#     min:   16
#     25%:   109.0
#     50%:   315.0
#     75%:   884.0
#     max:   54,388
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-02-15_scorecard_earnings.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [INFO] Year used: 2018 (target was 2020)
#   [WARN] Year matches target: False
#   [WARN] Row count: 5,376 (expected 2,000-4,000 for supplementary data)
#   [PASS] Critical columns (unitid): present
#   [PASS] Earnings column present: True
#   [PASS] No nulls in unitid: null rate = 0.0%
#   [PASS] unitid uniqueness: 5,376 unique / 5,376 rows
#   [WARN] Earnings column 'earnings_mean' has no numeric data to validate
# 
#   [INFO] COVERAGE NOTE: Scorecard data covers Title IV recipients only.
#   [INFO] Elite institutions may have 30-50% coverage bias.
#   [INFO] This data is supplementary and should be used with caveats.
# 
#   [WARN] Row count 5,376 outside expected range 2,000-4,000
# 
#   [WARN] Using year 2018 instead of target 2020
# 
# ============================================================
# CP1 VALIDATION: PASSED (with WARNINGS)
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
