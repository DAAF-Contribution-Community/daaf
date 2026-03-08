#!/usr/bin/env python3
"""
Stage 5.5: Fetch IPEDS fall enrollment by race data for 2020.

Task: fetch-enrollment-race
Wave: 1, Step: 5, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_enrollment_race.parquet
Checkpoint: CP1
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# This dataset provides fall enrollment counts broken down by race/ethnicity
# at each IPEDS institution, needed to calculate URM enrollment shares for
# the college graduation rate selectivity analysis.
#
# The IPEDS fall-enrollment-race dataset is a YEARLY file (one file per year),
# so we use fetch_yearly_from_mirrors() with a single year (2020).
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEARS = [2020]  # 2020 only, per Plan query specification

# Dataset path template from education-data-query skill's datasets-reference.md.
# IPEDS Fall Enrollment (Race) is a YEARLY dataset: one file per year.
DATASET_PATH_TEMPLATE = "ipeds/colleges_ipeds_fall-enrollment-race_{year}"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_enrollment_race.parquet"

# Critical columns that must be present in the output per Plan specification
CRITICAL_COLUMNS = ["unitid", "enrollment_fall", "race"]

# --- Mirror Configuration ---
# INTENT: Download IPEDS fall enrollment by race from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
# Format-specific read driven by each mirror's read_strategy field.
# All mirrors use the same canonical path from datasets-reference.md.
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
        filters: Dict of column->value(s) filters to apply locally.
        years: List of years to filter to.
    """
    _rate_limit()
    last_error = None

    for mirror in MIRRORS:
        name = mirror["name"]
        strategy = mirror["read_strategy"]

        url = mirror["url_template"].format(
            root_url=mirror["root_url"], path=path, format=mirror["format"]
        )

        print(f"  Trying {name}: {url}")

        try:
            if strategy == "eager_parquet":
                df = pl.read_parquet(url)
            elif strategy == "lazy_csv":
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

    Args:
        path_template: Canonical path string with a year placeholder.
        years: List of years to fetch.
        year_placeholder: String in path_template to replace with year.
        filters: Additional column filters.
    """
    frames = []

    for year in years:
        year_path = path_template.replace(year_placeholder, str(year))
        print(f"\n  Year {year}:")

        try:
            df = fetch_from_mirrors(year_path, filters=filters, years=[year])
            frames.append(df)
            print(f"    -> {df.shape[0]:,} rows")
        except RuntimeError:
            print(f"    -> SKIP: Year {year} not available from any mirror")

    if not frames:
        raise RuntimeError(f"No data retrieved for any year in {years}")

    result = pl.concat(frames, how="diagonal_relaxed")
    print(f"\n  Combined: {result.shape[0]:,} rows x {result.shape[1]} cols")
    return result


# =============================================================================
# MAIN EXECUTION
# =============================================================================
print("=" * 60)
print("Stage 5.5: Fetch IPEDS fall enrollment by race (2020)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS fall enrollment by race for 2020.
# REASONING: Yearly dataset (one file per year), so we use fetch_yearly_from_mirrors
#   with the path template containing {year}. Only fetching 2020 to match the
#   Plan's year specification for this analysis.
# ASSUMES:
#   - At least one mirror is available and serves this dataset
#   - Dataset has columns: unitid, year, enrollment_fall, race, sex, ftpt, level_of_study
#   - Multiple rows per institution (one per race code) — unitid is NOT unique
#   - Portal uses integer encoding for race (1-7, 99), sex (1, 2, 99), etc.
print("\nFetching IPEDS fall enrollment by race...")
df_raw = fetch_yearly_from_mirrors(
    path_template=DATASET_PATH_TEMPLATE,
    years=YEARS,
)
print(f"\nRaw shape: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# --- Pre-state ---
# Capture current state BEFORE any filtering for post-validation comparison.
pre_rows = df_raw.shape[0]
pre_cols = df_raw.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Columns: {pre_cols}")

# --- Explore coded values ---
# INTENT: Print unique values of demographic variables to understand the coding
#   scheme before applying filters. This is critical for correctly identifying
#   "total" codes for sex and undergraduate codes for level_of_study.
# REASONING: The Portal uses integer codes, not string labels. We must inspect
#   the actual data to confirm which codes represent totals vs. subgroups,
#   since documentation may not match the data exactly (Truth Hierarchy: data first).
print("\n" + "=" * 60)
print("CODED VALUE EXPLORATION")
print("=" * 60)

# Race codes
if "race" in df_raw.columns:
    race_values = sorted(df_raw["race"].unique().to_list())
    print(f"\nrace unique values ({len(race_values)}): {race_values}")
    race_counts = df_raw.group_by("race").len().sort("race")
    print(f"race value counts:\n{race_counts}")

# Sex codes
if "sex" in df_raw.columns:
    sex_values = sorted(df_raw["sex"].unique().to_list())
    print(f"\nsex unique values ({len(sex_values)}): {sex_values}")
    sex_counts = df_raw.group_by("sex").len().sort("sex")
    print(f"sex value counts:\n{sex_counts}")

# FTPT codes (full-time / part-time)
if "ftpt" in df_raw.columns:
    ftpt_values = sorted(df_raw["ftpt"].unique().to_list())
    print(f"\nftpt unique values ({len(ftpt_values)}): {ftpt_values}")
    ftpt_counts = df_raw.group_by("ftpt").len().sort("ftpt")
    print(f"ftpt value counts:\n{ftpt_counts}")

# Level of study codes
if "level_of_study" in df_raw.columns:
    level_values = sorted(df_raw["level_of_study"].unique().to_list())
    print(f"\nlevel_of_study unique values ({len(level_values)}): {level_values}")
    level_counts = df_raw.group_by("level_of_study").len().sort("level_of_study")
    print(f"level_of_study value counts:\n{level_counts}")

# --- Filter ---
# INTENT: Filter to total sex (sex == 99) and undergraduate level of study
#   to get one set of enrollment-by-race rows per institution that represents
#   total undergraduate enrollment by race (not split by male/female or grad/undergrad).
#
# REASONING: We filter sex == 99 (total, not split by gender) because the research
#   question is about overall demographic composition, not gender breakdowns.
#   For level_of_study, we need to inspect the actual codes to determine which
#   value(s) represent undergraduates. Common IPEDS codes:
#     1 = Undergraduate total, 2 = Graduate, 99 = Total all levels
#   We will filter based on what the data actually contains.
#
# ASSUMES:
#   - sex == 99 represents total (both sexes combined)
#   - level_of_study values will be inspectable from the coded value exploration above
#   - All race codes should be kept (aggregation happens in Stage 6/7)

print("\n" + "=" * 60)
print("APPLYING FILTERS")
print("=" * 60)

# INTENT: Filter to sex == 99 (total) to avoid double-counting male+female.
# REASONING: If sex == 99 is not present, we may need to use a different approach.
#   The coded value exploration above will show what's available.
if 99 in df_raw["sex"].unique().to_list():
    df_filtered = df_raw.filter(pl.col("sex") == 99)
    print(f"\nAfter sex == 99 (total) filter: {df_filtered.shape[0]:,} rows")
else:
    # REASONING: If sex == 99 is not available, check if the data already
    # represents totals or needs manual aggregation. Log this for investigation.
    print("\nWARNING: sex == 99 not found in data. Available values:")
    print(f"  {sorted(df_raw['sex'].unique().to_list())}")
    print("  Proceeding without sex filter — may need to aggregate in Stage 6")
    df_filtered = df_raw

# INTENT: Filter to undergraduate level of study.
# REASONING: The research question focuses on undergraduate graduation rates,
#   so we need undergraduate enrollment for demographic composition analysis.
#   Common IPEDS level_of_study codes: 1 = Undergraduate, 2 = Graduate, 99 = All.
#   We prefer undergraduate-specific (1) if available.
if "level_of_study" in df_filtered.columns:
    available_levels = sorted(df_filtered["level_of_study"].unique().to_list())
    print(f"\nAvailable level_of_study values after sex filter: {available_levels}")

    if 1 in available_levels:
        # REASONING: level_of_study == 1 is the undergraduate total.
        df_filtered = df_filtered.filter(pl.col("level_of_study") == 1)
        print(f"After level_of_study == 1 (undergraduate) filter: {df_filtered.shape[0]:,} rows")
    elif 99 in available_levels:
        # REASONING: If no undergraduate-specific code, use total (99) as fallback.
        # This will include graduate students, which is suboptimal but usable.
        print("WARNING: level_of_study == 1 not found, using 99 (total) as fallback")
        df_filtered = df_filtered.filter(pl.col("level_of_study") == 99)
        print(f"After level_of_study == 99 (total) filter: {df_filtered.shape[0]:,} rows")
    else:
        print(f"WARNING: Neither level_of_study 1 nor 99 found. Available: {available_levels}")
        print("  Proceeding without level_of_study filter")

# INTENT: Filter to total full-time/part-time if available, to avoid double-counting.
# REASONING: Similar logic to sex — we want the combined FT+PT total (99) if available,
#   otherwise we proceed without this filter and handle in Stage 6.
if "ftpt" in df_filtered.columns:
    available_ftpt = sorted(df_filtered["ftpt"].unique().to_list())
    print(f"\nAvailable ftpt values after prior filters: {available_ftpt}")

    if 99 in available_ftpt:
        df_filtered = df_filtered.filter(pl.col("ftpt") == 99)
        print(f"After ftpt == 99 (total) filter: {df_filtered.shape[0]:,} rows")
    else:
        print(f"WARNING: ftpt == 99 not found. Available: {available_ftpt}")
        print("  Proceeding without ftpt filter — may need aggregation in Stage 6")

# --- Post-state ---
post_rows = df_filtered.shape[0]
print(f"\nPost-state: {post_rows:,} rows x {df_filtered.shape[1]} cols")
row_change_pct = ((post_rows - pre_rows) / pre_rows * 100) if pre_rows > 0 else 0
print(f"Row change from raw: {row_change_pct:+.1f}%")

# --- Column Selection ---
# INTENT: Select only the columns needed for downstream analysis to reduce file size
#   and clarify what data is carried forward.
# REASONING: We keep all identifying and measurement columns but drop any extraneous
#   metadata columns that aren't needed for the graduation rate analysis.
available_cols = df_filtered.columns
select_cols = [c for c in ["unitid", "year", "enrollment_fall", "race", "sex",
                            "ftpt", "level_of_study"] if c in available_cols]
print(f"\nSelecting columns: {select_cols}")
df_final = df_filtered.select(select_cols)
print(f"Final shape: {df_final.shape[0]:,} rows x {df_final.shape[1]} cols")

# --- Data Preview ---
# INTENT: Show sample data and race distribution for human verification.
print("\n" + "=" * 60)
print("DATA PREVIEW")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df_final.head(10)}")
print(f"\nSchema:\n{df_final.schema}")

# Unique institutions
n_institutions = df_final["unitid"].n_unique()
print(f"\nUnique institutions (unitid): {n_institutions:,}")

# Race distribution
race_dist = df_final.group_by("race").agg(
    pl.len().alias("n_rows"),
    pl.col("enrollment_fall").sum().alias("total_enrollment"),
).sort("race")
print(f"\nRace distribution:\n{race_dist}")

# Sample unitid values
sample_unitids = df_final["unitid"].unique().sort().head(5).to_list()
print(f"\nSample unitid values: {sample_unitids}")

# Check for negative/coded values in enrollment_fall
if "enrollment_fall" in df_final.columns:
    neg_count = df_final.filter(pl.col("enrollment_fall") < 0).shape[0]
    null_count = df_final["enrollment_fall"].null_count()
    print(f"\nenrollment_fall: {neg_count:,} negative values, {null_count:,} nulls")
    if neg_count > 0:
        neg_values = df_final.filter(pl.col("enrollment_fall") < 0)["enrollment_fall"].unique().sort().to_list()
        print(f"  Negative values found: {neg_values}")
        print(f"  (These are likely coded missing: -1=Missing, -2=Not applicable, -3=Suppressed)")

# --- Save ---
# Persist results in parquet format.
# REASONING: Parquet preserves schema and types, compresses efficiently, and
#   is the mandatory output format per DAAF protocol.
OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
df_final.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# row counts, critical columns, race code diversity, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Year present
years_found = df_final["year"].unique().to_list()
year_ok = 2020 in years_found
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year 2020 present: {sorted(years_found)}")

# CP1.2: Row count within expected range (10,000-60,000 per Plan)
row_count = df_final.shape[0]
rows_ok = 10000 <= row_count <= 60000
print(f"  [{'PASS' if rows_ok else 'WARN'}] Row count in range 10K-60K: {row_count:,}")

# CP1.3: Critical columns present
cols_present = all(c in df_final.columns for c in CRITICAL_COLUMNS)
missing_cols = [c for c in CRITICAL_COLUMNS if c not in df_final.columns]
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: {CRITICAL_COLUMNS}")
if missing_cols:
    print(f"    Missing: {missing_cols}")

# CP1.4: Multiple race code values present (data should have multiple race groups)
n_race_codes = df_final["race"].n_unique()
race_diverse = n_race_codes >= 2
print(f"  [{'PASS' if race_diverse else 'FAIL'}] Multiple race codes present: {n_race_codes} unique values")

# CP1.5: unitid is NOT unique (expected: multiple rows per institution, one per race)
unitid_unique_count = df_final["unitid"].n_unique()
unitid_not_unique = row_count > unitid_unique_count
print(f"  [{'PASS' if unitid_not_unique else 'WARN'}] unitid NOT unique (multiple rows per institution): "
      f"{unitid_unique_count:,} unique unitids vs {row_count:,} rows")

# CP1.6: No nulls in identifier columns
unitid_nulls = df_final["unitid"].null_count()
year_nulls = df_final["year"].null_count()
race_nulls = df_final["race"].null_count()
no_id_nulls = unitid_nulls == 0 and year_nulls == 0 and race_nulls == 0
print(f"  [{'PASS' if no_id_nulls else 'FAIL'}] No nulls in ID columns: "
      f"unitid={unitid_nulls}, year={year_nulls}, race={race_nulls}")

# CP1.7: enrollment_fall present and mostly non-null
if "enrollment_fall" in df_final.columns:
    enroll_null_rate = df_final["enrollment_fall"].null_count() / row_count
    enroll_ok = enroll_null_rate < 0.90
    print(f"  [{'PASS' if enroll_ok else 'FAIL'}] enrollment_fall null rate < 90%: {enroll_null_rate:.1%}")
else:
    enroll_ok = False
    print(f"  [FAIL] enrollment_fall column not present")

# Overall CP1 status
all_critical = year_ok and cols_present and race_diverse and no_id_nulls and enroll_ok
print(f"\n{'=' * 60}")
if all_critical:
    print("CP1 VALIDATION: PASSED")
else:
    print("CP1 VALIDATION: FAILED")
print("=" * 60)

assert year_ok, "STOP: Year 2020 not present in data"
assert cols_present, f"STOP: Missing critical columns: {missing_cols}"
assert race_diverse, "STOP: Only one race code found — data may be pre-aggregated"
assert no_id_nulls, "STOP: Nulls in identifier columns"
assert enroll_ok, "STOP: enrollment_fall >90% null or missing"


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:09:45
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/05_fetch-enrollment-race.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.5: Fetch IPEDS fall enrollment by race (2020)
# ============================================================
# 
# Fetching IPEDS fall enrollment by race...
# 
#   Year 2020:
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_fall-enrollment-race_2020.parquet
#   OK huggingface: 3,533,310 rows
#   After filters: 3,533,310 rows
#     -> 3,533,310 rows
# 
#   Combined: 3,533,310 rows x 10 cols
# 
# Raw shape: 3,533,310 rows x 10 cols
# 
# Pre-state: 3,533,310 rows, 10 cols
# Columns: ['unitid', 'year', 'fips', 'sex', 'race', 'ftpt', 'level_of_study', 'degree_seeking', 'class_level', 'enrollment_fall']
# 
# ============================================================
# CODED VALUE EXPLORATION
# ============================================================
# 
# race unique values (10): [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# race value counts:
# shape: (10, 2)
# ┌──────┬────────┐
# │ race ┆ len    │
# │ ---  ┆ ---    │
# │ i64  ┆ u32    │
# ╞══════╪════════╡
# │ 1    ┆ 353331 │
# │ 2    ┆ 353331 │
# │ 3    ┆ 353331 │
# │ 4    ┆ 353331 │
# │ 5    ┆ 353331 │
# │ 6    ┆ 353331 │
# │ 7    ┆ 353331 │
# │ 8    ┆ 353331 │
# │ 9    ┆ 353331 │
# │ 99   ┆ 353331 │
# └──────┴────────┘
# 
# sex unique values (3): [1, 2, 99]
# sex value counts:
# shape: (3, 2)
# ┌─────┬─────────┐
# │ sex ┆ len     │
# │ --- ┆ ---     │
# │ i64 ┆ u32     │
# ╞═════╪═════════╡
# │ 1   ┆ 1177770 │
# │ 2   ┆ 1177770 │
# │ 99  ┆ 1177770 │
# └─────┴─────────┘
# 
# ftpt unique values (3): [1, 2, 99]
# ftpt value counts:
# shape: (3, 2)
# ┌──────┬─────────┐
# │ ftpt ┆ len     │
# │ ---  ┆ ---     │
# │ i64  ┆ u32     │
# ╞══════╪═════════╡
# │ 1    ┆ 1268220 │
# │ 2    ┆ 962730  │
# │ 99   ┆ 1302360 │
# └──────┴─────────┘
# 
# level_of_study unique values (3): [1, 2, 99]
# level_of_study value counts:
# shape: (3, 2)
# ┌────────────────┬─────────┐
# │ level_of_study ┆ len     │
# │ ---            ┆ ---     │
# │ i64            ┆ u32     │
# ╞════════════════╪═════════╡
# │ 1              ┆ 2854740 │
# │ 2              ┆ 177840  │
# │ 99             ┆ 500730  │
# └────────────────┴─────────┘
# 
# ============================================================
# APPLYING FILTERS
# ============================================================
# 
# After sex == 99 (total) filter: 1,177,770 rows
# 
# Available level_of_study values after sex filter: [1, 2, 99]
# After level_of_study == 1 (undergraduate) filter: 951,580 rows
# 
# Available ftpt values after prior filters: [1, 2, 99]
# After ftpt == 99 (total) filter: 352,410 rows
# 
# Post-state: 352,410 rows x 10 cols
# Row change from raw: -90.0%
# 
# Selecting columns: ['unitid', 'year', 'enrollment_fall', 'race', 'sex', 'ftpt', 'level_of_study']
# Final shape: 352,410 rows x 7 cols
# 
# ============================================================
# DATA PREVIEW
# ============================================================
# 
# First 10 rows:
# shape: (10, 7)
# ┌────────┬──────┬─────────────────┬──────┬─────┬──────┬────────────────┐
# │ unitid ┆ year ┆ enrollment_fall ┆ race ┆ sex ┆ ftpt ┆ level_of_study │
# │ ---    ┆ ---  ┆ ---             ┆ ---  ┆ --- ┆ ---  ┆ ---            │
# │ i64    ┆ i64  ┆ i64             ┆ i64  ┆ i64 ┆ i64  ┆ i64            │
# ╞════════╪══════╪═════════════════╪══════╪═════╪══════╪════════════════╡
# │ 100654 ┆ 2020 ┆ 1               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 6               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 4    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 1    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 31              ┆ 7    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 3               ┆ 8    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 5090            ┆ 99   ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 169             ┆ 9    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 0               ┆ 7    ┆ 99  ┆ 99   ┆ 1              │
# │ 100654 ┆ 2020 ┆ 1               ┆ 7    ┆ 99  ┆ 99   ┆ 1              │
# └────────┴──────┴─────────────────┴──────┴─────┴──────┴────────────────┘
# 
# Schema:
# Schema({'unitid': Int64, 'year': Int64, 'enrollment_fall': Int64, 'race': Int64, 'sex': Int64, 'ftpt': Int64, 'level_of_study': Int64})
# 
# Unique institutions (unitid): 5,837
# 
# Race distribution:
# shape: (10, 3)
# ┌──────┬────────┬──────────────────┐
# │ race ┆ n_rows ┆ total_enrollment │
# │ ---  ┆ ---    ┆ ---              │
# │ i64  ┆ u32    ┆ i64              │
# ╞══════╪════════╪══════════════════╡
# │ 1    ┆ 35241  ┆ 28360502         │
# │ 2    ┆ 35241  ┆ 7302057          │
# │ 3    ┆ 35241  ┆ 12544754         │
# │ 4    ┆ 35241  ┆ 3922940          │
# │ 5    ┆ 35241  ┆ 386234           │
# │ 6    ┆ 35241  ┆ 180719           │
# │ 7    ┆ 35241  ┆ 2369453          │
# │ 8    ┆ 35241  ┆ 1769370          │
# │ 9    ┆ 35241  ┆ 2403345          │
# │ 99   ┆ 35241  ┆ 59239374         │
# └──────┴────────┴──────────────────┘
# 
# Sample unitid values: [100654, 100663, 100690, 100706, 100724]
# 
# enrollment_fall: 0 negative values, 0 nulls
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-02-15_ipeds_enrollment_race.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year 2020 present: [2020]
#   [WARN] Row count in range 10K-60K: 352,410
#   [PASS] Critical columns present: ['unitid', 'enrollment_fall', 'race']
#   [PASS] Multiple race codes present: 10 unique values
#   [PASS] unitid NOT unique (multiple rows per institution): 5,837 unique unitids vs 352,410 rows
#   [PASS] No nulls in ID columns: unitid=0, year=0, race=0
#   [PASS] enrollment_fall null rate < 90%: 0.0%
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
