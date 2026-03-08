#!/usr/bin/env python3
"""
Stage 5.1: Fetch IPEDS college directory data for year 2020.

Task: fetch-directory
Wave: 1, Step: 1, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_directory.parquet
Checkpoint: CP1
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# We fetch the IPEDS directory for 4-year, public and private nonprofit
# institutions in year 2020 — the analysis target year chosen because it has
# the most complete data (student-faculty ratio, retention, GR reflecting
# 2014 pre-COVID entering cohort, and mostly pre-COVID admissions apps).
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEAR = 2020  # Single target year per Plan specification

# Dataset path from education-data-query skill's datasets-reference.md.
# IPEDS Directory is a single-file dataset (all years in one file).
DATASET_PATH = "ipeds/colleges_ipeds_directory"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_directory.parquet"

# Columns to select from the directory dataset.
# REASONING: These columns provide institutional characteristics needed for
# the analysis: identification (unitid, inst_name), classification (inst_control,
# institution_level, hbcu, degree_granting, open_admissions), geography
# (state_abbr, fips, urban_centric_locale), Carnegie classification
# (cc_basic_2021), and enrollment (enrollment_undergrad).
SELECT_COLUMNS = [
    "unitid",
    "year",
    "inst_name",
    "inst_control",
    "institution_level",
    "hbcu",
    "degree_granting",
    "open_admissions",
    "urban_centric_locale",
    "cc_basic_2021",
    "enrollment_undergrad",
    "state_abbr",
    "fips",
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
print("Stage 5.1: Fetch IPEDS college directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download IPEDS directory and filter to year 2020.
# REASONING: Single-file dataset (all years in one file). Download once,
# filter locally with Polars for year 2020 only.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
print("\nFetching IPEDS directory...")
df_raw = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)
print(f"After year filter: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")

# --- Pre-state ---
# Capture state BEFORE applying local filters so we can track how many
# institutions are removed by each filter condition.
pre_rows = df_raw.shape[0]
print(f"\nPre-state (year={YEAR}, before institutional filters): {pre_rows:,} rows")
print(f"Columns available: {len(df_raw.columns)}")

# --- Filter ---
# INTENT: Apply local filters to restrict to 4-year, public/private nonprofit
# institutions per Plan specification. These filters narrow the dataset to the
# analysis population.
#
# REASONING: institution_level == 4 selects 4-year institutions (the analysis
# focuses on bachelor's-granting colleges/universities). inst_control in [1, 2]
# selects public (1) and private nonprofit (2), excluding for-profit (3) per
# user clarification that for-profit institutions should be excluded.
#
# ASSUMES: institution_level and inst_control columns use integer codes per
# IPEDS/Portal conventions. Value 4 = 4-year, value 1 = public, 2 = private
# nonprofit, 3 = private for-profit.

# Filter 1: 4-year institutions only
df_filtered = df_raw.filter(pl.col("institution_level") == 4)
print(f"After institution_level == 4: {df_filtered.shape[0]:,} rows "
      f"(removed {pre_rows - df_filtered.shape[0]:,})")

# Filter 2: Public and private nonprofit only (exclude for-profit)
pre_control = df_filtered.shape[0]
df_filtered = df_filtered.filter(pl.col("inst_control").is_in([1, 2]))
print(f"After inst_control in [1, 2]: {df_filtered.shape[0]:,} rows "
      f"(removed {pre_control - df_filtered.shape[0]:,})")

# --- Select Columns ---
# INTENT: Reduce to only the columns needed for this analysis to minimize
# file size and clarify the analysis scope.
# REASONING: The full IPEDS directory has many columns we don't need. Selecting
# only Plan-specified columns keeps the raw data focused and manageable.
# ASSUMES: All SELECT_COLUMNS exist in the dataset for year 2020.

# Check which requested columns exist in the data
available_cols = [c for c in SELECT_COLUMNS if c in df_filtered.columns]
missing_cols = [c for c in SELECT_COLUMNS if c not in df_filtered.columns]

if missing_cols:
    print(f"\nWARNING: Requested columns not found in data: {missing_cols}")
    print(f"Available columns (sample): {df_filtered.columns[:20]}")

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

# Show distribution of key columns
print(f"\ninst_control distribution:")
print(df_final.group_by("inst_control").len().sort("inst_control"))

print(f"\nopen_admissions distribution:")
print(df_final.group_by("open_admissions").len().sort("open_admissions"))

print(f"\nstate_abbr unique count: {df_final['state_abbr'].n_unique()}")

# Show null counts for all columns
print(f"\nNull counts per column:")
for col in df_final.columns:
    null_ct = df_final[col].null_count()
    null_pct = null_ct / post_rows * 100 if post_rows > 0 else 0
    print(f"  {col}: {null_ct:,} ({null_pct:.1f}%)")

# --- Save ---
# Persist results in parquet format.
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

# CP1.2: Row count within expected range (2,000 - 4,000 per Plan)
row_count = df_final.shape[0]
rows_ok = 2000 <= row_count <= 4000
print(f"  [{'PASS' if rows_ok else 'WARN'}] Row count: {row_count:,} "
      f"(expected 2,000-4,000)")

# CP1.3: Critical columns present
critical_cols = ["unitid", "inst_name", "inst_control", "enrollment_undergrad", "open_admissions"]
cols_present = all(c in df_final.columns for c in critical_cols)
missing_critical = [c for c in critical_cols if c not in df_final.columns]
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: "
      f"{'all present' if cols_present else f'missing {missing_critical}'}")

# CP1.4: Null rate for key identifiers < 10%
unitid_null_rate = df_final["unitid"].null_count() / row_count if row_count > 0 else 1
instname_null_rate = df_final["inst_name"].null_count() / row_count if row_count > 0 else 1
instcontrol_null_rate = df_final["inst_control"].null_count() / row_count if row_count > 0 else 1
id_nulls_ok = all(rate < 0.10 for rate in [unitid_null_rate, instname_null_rate, instcontrol_null_rate])
print(f"  [{'PASS' if id_nulls_ok else 'FAIL'}] Null rate < 10% for key IDs: "
      f"unitid={unitid_null_rate:.1%}, inst_name={instname_null_rate:.1%}, "
      f"inst_control={instcontrol_null_rate:.1%}")

# CP1.5: inst_control only contains expected values [1, 2]
control_values = sorted(df_final["inst_control"].drop_nulls().unique().to_list())
control_ok = set(control_values).issubset({1, 2})
print(f"  [{'PASS' if control_ok else 'FAIL'}] inst_control values: {control_values} "
      f"(expected subset of [1, 2])")

# CP1.6: institution_level only contains value 4
level_values = sorted(df_final["institution_level"].drop_nulls().unique().to_list())
level_ok = level_values == [4]
print(f"  [{'PASS' if level_ok else 'FAIL'}] institution_level values: {level_values} "
      f"(expected [4])")

# CP1.7: unitid uniqueness (should be one row per institution for single year)
unitid_unique = df_final["unitid"].n_unique() == row_count
print(f"  [{'PASS' if unitid_unique else 'WARN'}] unitid uniqueness: "
      f"{df_final['unitid'].n_unique():,} unique / {row_count:,} rows")

# --- Overall CP1 ---
# REASONING: Critical checks (year, columns, ID nulls, filter values) must all
# pass. Row count outside range is a WARNING, not a failure, since it may
# reflect legitimate variation in the number of institutions meeting criteria.
# unitid uniqueness is also a warning — duplicates would indicate data issues
# but not a fetch failure per se.
critical_passed = all([year_ok, cols_present, id_nulls_ok, control_ok, level_ok])

if not rows_ok:
    print(f"\n  [WARN] Row count {row_count:,} outside expected range 2,000-4,000")
if not unitid_unique:
    print(f"\n  [WARN] unitid is not fully unique — potential duplicate rows")

assert critical_passed, (
    f"STOP: CP1 critical checks failed — "
    f"year_ok={year_ok}, cols_present={cols_present}, id_nulls_ok={id_nulls_ok}, "
    f"control_ok={control_ok}, level_ok={level_ok}"
)

cp1_status = "PASSED" if (critical_passed and rows_ok and unitid_unique) else "PASSED (with WARNINGS)"
print(f"\n{'=' * 60}")
print(f"CP1 VALIDATION: {cp1_status}")
print(f"{'=' * 60}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:08:43
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 5.1: Fetch IPEDS college directory
# ============================================================
# 
# Fetching IPEDS directory...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_directory.parquet
#   -> huggingface: 336,982 rows
#   After filters: 6,440 rows
# After year filter: 6,440 rows x 89 cols
# 
# Pre-state (year=2020, before institutional filters): 6,440 rows
# Columns available: 89
# After institution_level == 4: 2,898 rows (removed 3,542)
# After inst_control in [1, 2]: 2,528 rows (removed 370)
# 
# WARNING: Requested columns not found in data: ['open_admissions', 'enrollment_undergrad']
# Available columns (sample): ['unitid', 'year', 'opeid', 'inst_name', 'inst_alias', 'address', 'state_abbr', 'fips', 'zip', 'phone_number', 'city', 'county_name', 'county_fips', 'region', 'urban_centric_locale', 'cbsa', 'cbsa_type', 'csa', 'necta', 'longitude']
# 
# Selected 11 columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'cc_basic_2021', 'state_abbr', 'fips']
# 
# Post-state: 2,528 rows x 11 cols
# Row change from pre-state: -3,912 (-60.7%)
# 
# Sample rows (first 5):
# shape: (5, 11)
# ┌────────┬──────┬──────────────┬──────────────┬───┬──────────────┬─────────────┬────────────┬──────┐
# │ unitid ┆ year ┆ inst_name    ┆ inst_control ┆ … ┆ urban_centri ┆ cc_basic_20 ┆ state_abbr ┆ fips │
# │ ---    ┆ ---  ┆ ---          ┆ ---          ┆   ┆ c_locale     ┆ 21          ┆ ---        ┆ ---  │
# │ i64    ┆ i64  ┆ str          ┆ i64          ┆   ┆ ---          ┆ ---         ┆ str        ┆ i64  │
# │        ┆      ┆              ┆              ┆   ┆ i64          ┆ i64         ┆            ┆      │
# ╞════════╪══════╪══════════════╪══════════════╪═══╪══════════════╪═════════════╪════════════╪══════╡
# │ 100654 ┆ 2020 ┆ Alabama A &  ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ M University ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100663 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ at Birmi…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100690 ┆ 2020 ┆ Amridge      ┆ 2            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100706 ┆ 2020 ┆ University   ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ of Alabama   ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ in Hunts…    ┆              ┆   ┆              ┆             ┆            ┆      │
# │ 100724 ┆ 2020 ┆ Alabama      ┆ 1            ┆ … ┆ 12           ┆ null        ┆ AL         ┆ 1    │
# │        ┆      ┆ State        ┆              ┆   ┆              ┆             ┆            ┆      │
# │        ┆      ┆ University   ┆              ┆   ┆              ┆             ┆            ┆      │
# └────────┴──────┴──────────────┴──────────────┴───┴──────────────┴─────────────┴────────────┴──────┘
# 
# inst_control distribution:
# shape: (2, 2)
# ┌──────────────┬──────┐
# │ inst_control ┆ len  │
# │ ---          ┆ ---  │
# │ i64          ┆ u32  │
# ╞══════════════╪══════╡
# │ 1            ┆ 852  │
# │ 2            ┆ 1676 │
# └──────────────┴──────┘
# 
# open_admissions distribution:
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/01_fetch-directory.py", line 258, in <module>
#     print(df_final.group_by("open_admissions").len().sort("open_admissions"))
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/group_by.py", line 532, in len
#     return self.agg(len_expr)
#            ^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/group_by.py", line 298, in agg
#     .collect(optimizations=QueryOptFlags.none())
#      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 97, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/opt_flags.py", line 326, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/frame.py", line 2440, in collect
#     return wrap_df(ldf.collect(engine, callback))
#                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.ColumnNotFoundError: unable to find column "open_admissions"; valid columns: ["unitid", "year", "inst_name", "inst_control", "institution_level", "hbcu", "degree_granting", "urban_centric_locale", "cc_basic_2021", "state_abbr", "fips"]
# 
# Resolved plan until failure:
# 
# 	---> FAILED HERE RESOLVING 'sink' <---
# DF ["unitid", "year", "inst_name", "inst_control", ...]; PROJECT */11 COLUMNS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
