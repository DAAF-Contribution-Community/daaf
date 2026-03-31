#!/usr/bin/env python3
"""
Stage 5.4: Fetch FSA Grants data (Pell Grant recipients, 2020-2021).

Task: fetch-fsa-grants
Wave: 1, Step: 4, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_fsa_grants.parquet
Checkpoint: CP1

Skill Provenance Note: education-data-query skill used for mirror config
and dataset paths. Check skill_last_updated for staleness if column
definitions or coded values appear inconsistent with observed data.
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# FSA grants data is a single-file dataset containing all years (1999-2021).
# We filter to 2020-2021 and grant_type == 1 (Pell Grant only) locally after
# downloading the full file from mirrors.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020, 2021]  # Per Plan query specification

# Dataset path from datasets-reference.md (FSA Grants section):
# Type: Single, Years: 1999-2021, path: fsa/colleges_fsa_grants
DATASET_PATH = "fsa/colleges_fsa_grants"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_fsa_grants.parquet"

# Domain configuration (from Plan)
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]  # COVID years -- document comparability concerns

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
                print(f"  Success {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  Success {name}: {df.shape[0]:,} rows")

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
            print(f"  Failed {name}: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Fetch ---
# INTENT: Download FSA grants data and filter to Pell Grant recipients
# for years 2020-2021. This provides institutional-level Pell Grant
# recipient counts and disbursement amounts, which serve as a proxy for
# the share of low-income students at each institution.
#
# REASONING: Single-file dataset (all years 1999-2021 in one file). Download
# once, then filter locally with Polars for years and grant_type.
# grant_type == 1 selects Pell Grant records specifically (as opposed to
# other grant types like FSEOG, TEACH, or Iraq/Afghanistan Service Grants).
#
# REVISION NOTE (v3/_c): v1 and v2 revealed that ALL grant_recipients and
# value_grants_disbursed columns (both _unitid and _opeid variants) are 100%
# null for years 2020-2021. This version first probes earlier years to determine
# whether this is a 2020-2021 data availability issue or a structural issue.
# If earlier years have data, we fall back to 2019-2020 as the closest available
# years with populated grant data. This is an autonomous deviation under Rule 1
# (auto-fix blocking issue).
#
# ASSUMES:
#   - At least one mirror is available and serves this dataset
#   - Dataset contains "year", "grant_type", "unitid" columns
#   - grant_type == 1 corresponds to Pell Grants per FSA documentation
#   - All variable names are lowercase (Portal convention)
print("=" * 60)
print("Stage 5.4: Fetch FSA Grants (Pell)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Probe data availability across years ---
# INTENT: Determine which years have non-null grant data before committing
# to a year filter. FSA data has 1-3 year lag; recent years may have rows
# but no populated grant columns.
# REASONING: v1/v2 showed 2020-2021 have 100% null grant columns. We need
# to find the most recent years with actual data.
print("\nProbing data availability across years...")
df_full = fetch_from_mirrors(path=DATASET_PATH)
print(f"Full dataset: {df_full.shape[0]:,} rows x {df_full.shape[1]} cols")

# Check which years have non-null grant data for Pell (grant_type == 1)
df_pell_all = df_full.filter(pl.col("grant_type") == 1)
print(f"All Pell rows: {df_pell_all.shape[0]:,}")

# INTENT: For each year, check non-null rate in grant columns to identify
# years with actual data vs. years with only stub rows.
data_col = "grant_recipients_opeid"
if data_col not in df_pell_all.columns:
    data_col = "grant_recipients_unitid"

year_data_availability = (
    df_pell_all
    .group_by("year")
    .agg([
        pl.len().alias("n_rows"),
        pl.col(data_col).null_count().alias("null_count"),
    ])
    .with_columns(
        (1 - pl.col("null_count") / pl.col("n_rows")).alias("non_null_rate")
    )
    .sort("year")
)
print(f"\nYear-level data availability ({data_col}):")
print(year_data_availability)

# INTENT: Select the best available years for the analysis.
# REASONING: Use 2020-2021 if they have data. Otherwise, fall back to the
# two most recent years that have >50% non-null rate in grant columns.
years_with_data = (
    year_data_availability
    .filter(pl.col("non_null_rate") > 0.5)
    .sort("year", descending=True)
)

if years_with_data.filter(pl.col("year").is_in(YEARS)).shape[0] == len(YEARS):
    # Requested years have data -- use them
    selected_years = YEARS
    print(f"\nRequested years {YEARS} have data -- using as specified.")
else:
    # Fall back to the two most recent years with data
    available_years = years_with_data["year"].to_list()
    selected_years = available_years[:2]  # Most recent 2 years with data
    print(f"\nWARNING: Requested years {YEARS} have no grant data.")
    print(f"Falling back to most recent years with data: {selected_years}")
    print("DEVIATION: Rule 1 (auto-fix blocking issue) -- using available years.")

# --- Filter to selected years ---
df = df_pell_all.filter(pl.col("year").is_in(selected_years))
print(f"\nAfter year + Pell filter: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Post-filter state ---
# Pell filter and year filter already applied above during probe logic.
post_rows = df.shape[0]
print(f"\nPost-filter state:")
print(f"  Rows: {post_rows:,}")
print(f"  Columns: {df.columns}")
print(f"  Years selected: {selected_years}")

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- Summary Statistics ---
# INTENT: Log key summary metrics for downstream verification and audit.
# REASONING: FSA data has two sets of columns: _unitid and _opeid suffixes.
# The _unitid columns are populated only when the unitid-opeid mapping is 1:1.
# In practice, _unitid columns are often entirely null while _opeid columns
# contain the actual data. We report both variants to document this pattern.
print("\n" + "-" * 40)
print("SUMMARY")
print("-" * 40)
n_unitids = df["unitid"].n_unique()
print(f"Unique unitids: {n_unitids:,}")
print(f"Years present: {sorted(df['year'].unique().to_list())}")

# Report null rates for all key data columns
for col in ["grant_recipients_unitid", "value_grants_disbursed_unitid",
            "grant_recipients_opeid", "value_grants_disbursed_opeid"]:
    if col in df.columns:
        non_null = df[col].drop_nulls()
        null_ct = df[col].null_count()
        print(f"  {col}: {len(non_null):,} non-null, {null_ct:,} null ({null_ct / len(df) * 100:.1f}%)")
        if len(non_null) > 0:
            print(f"    range: {non_null.min():,} - {non_null.max():,}, sum: {non_null.sum():,}")

# INTENT: Determine which column variant has data for recipient counts.
# REASONING: FSA data has _unitid and _opeid column variants. Check both
# to find the one with actual data.
for recip_col in ["grant_recipients_opeid", "grant_recipients_unitid"]:
    if recip_col in df.columns:
        non_null_recip = df[recip_col].drop_nulls()
        if len(non_null_recip) > 0:
            total_recipients = non_null_recip.sum()
            print(f"\nTotal Pell recipients ({recip_col}): {total_recipients:,}")
            print(f"{recip_col} range: {non_null_recip.min():,} - {non_null_recip.max():,}")
            break  # Use first non-null variant

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# row counts, year coverage, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Row count in expected range (8,000-15,000)
expected_min = 8000
expected_max = 15000
rows_ok = expected_min <= df.shape[0] <= expected_max
if not rows_ok:
    # REASONING: Row count outside expected range is a WARNING, not a FAIL,
    # because FSA coverage can vary. Only truly empty data is a FAIL.
    if df.shape[0] == 0:
        print(f"[FAIL] Empty dataset: 0 rows (expected {expected_min:,}-{expected_max:,})")
        cp1_passed = False
    else:
        print(f"[WARN] Row count {df.shape[0]:,} outside expected range {expected_min:,}-{expected_max:,}")
else:
    print(f"[PASS] Row count: {df.shape[0]:,} (expected {expected_min:,}-{expected_max:,})")

# CP1.2: Required columns present
# REASONING: The task spec lists grant_recipients_unitid and value_grants_disbursed_unitid
# as required. However, v1 execution revealed these are 100% null while the _opeid
# variants contain the actual data. We check for BOTH sets of columns to document
# the data structure, and require at least the _opeid variants for downstream use.
required_cols = ["unitid", "year", "grant_type"]
# Check for data columns -- prefer _opeid if _unitid are null
data_cols_unitid = ["grant_recipients_unitid", "value_grants_disbursed_unitid"]
data_cols_opeid = ["grant_recipients_opeid", "value_grants_disbursed_opeid"]
all_required = required_cols + data_cols_unitid + data_cols_opeid
missing_cols = [c for c in all_required if c not in df.columns]
cols_present = len(missing_cols) == 0
if cols_present:
    print(f"[PASS] All {len(all_required)} required columns present (both _unitid and _opeid variants)")
else:
    print(f"[FAIL] Missing required columns: {missing_cols}")
    cp1_passed = False

# CP1.3: Years present -- must match selected_years (which may differ from
# originally requested YEARS if fallback was applied)
years_found = sorted(df["year"].unique().to_list())
all_years = all(y in years_found for y in selected_years)
if all_years:
    print(f"[PASS] All selected years present: {years_found}")
    if selected_years != YEARS:
        print(f"[WARN] Years differ from Plan specification: selected {selected_years}, Plan requested {YEARS}")
else:
    print(f"[FAIL] Missing years. Found: {years_found}, expected: {selected_years}")
    cp1_passed = False

# CP1.4: grant_type contains only value 1 (Pell)
grant_types_remaining = df["grant_type"].unique().to_list()
pell_only = grant_types_remaining == [1]
if pell_only:
    print(f"[PASS] grant_type contains only Pell (1): {grant_types_remaining}")
else:
    print(f"[FAIL] Unexpected grant_type values: {grant_types_remaining}")
    cp1_passed = False

# CP1.5: Null rate < 10% for critical columns
# REASONING: Check both _unitid and _opeid column variants. At least one
# variant of grant_recipients must have data for downstream analysis.
critical_null_cols = ["unitid", "year"]
for col in critical_null_cols:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        if null_pct >= 10:
            print(f"[FAIL] {col}: {null_pct:.1f}% null (>= 10% threshold)")
            cp1_passed = False
        elif null_pct > 0:
            print(f"[WARN] {col}: {null_pct:.1f}% null")
        else:
            print(f"[PASS] {col}: 0.0% null")

# Check grant data columns -- at least one variant must have data
grant_data_available = False
for col in ["grant_recipients_opeid", "grant_recipients_unitid"]:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        if null_pct < 10:
            print(f"[PASS] {col}: {null_pct:.1f}% null")
            grant_data_available = True
        else:
            print(f"[NOTE] {col}: {null_pct:.1f}% null")

if not grant_data_available:
    print(f"[FAIL] Neither grant_recipients_opeid nor grant_recipients_unitid has data (<10% null)")
    cp1_passed = False

# CP1.6: Year freshness / data lag check
# REASONING: FSA data typically has 1-3 year lag. Flag if selected years
# differ from originally requested years.
max_selected = max(selected_years)
max_requested = max(YEARS)
if max_selected < max_requested:
    lag = max_requested - max_selected
    print(f"[WARN] Data lag: Plan requested up to {max_requested}, using {max_selected} ({lag}-year data lag)")

# CP1.7: COVID flag years
# REASONING: Both 2020 and 2021 are COVID-affected years. Pell enrollment
# patterns may differ from pre-COVID norms. Document for limitations.
if any(y in FLAG_YEARS for y in years_found):
    print(f"[WARN] FLAG-YEARS: Data includes COVID-affected years {[y for y in years_found if y in FLAG_YEARS]}. "
          "Document comparability concerns in limitations.")

# CP1.8: Year-level row counts
year_counts = df.group_by("year").len().sort("year")
print(f"\nRow counts by year:")
for row in year_counts.iter_rows(named=True):
    print(f"  {row['year']}: {row['len']:,}")

assert cp1_passed, "STOP: CP1 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 20:22:14
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA Grants (Pell)
# ============================================================
# 
# Probing data availability across years...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/fsa/colleges_fsa_grants.parquet
#   Success huggingface: 608,510 rows
#   After filters: 608,510 rows
# Full dataset: 608,510 rows x 13 cols
# All Pell rows: 121,702
# 
# Year-level data availability (grant_recipients_opeid):
# shape: (23, 4)
# ┌──────┬────────┬────────────┬───────────────┐
# │ year ┆ n_rows ┆ null_count ┆ non_null_rate │
# │ ---  ┆ ---    ┆ ---        ┆ ---           │
# │ i64  ┆ u32    ┆ u32        ┆ f64           │
# ╞══════╪════════╪════════════╪═══════════════╡
# │ 1999 ┆ 5146   ┆ 5146       ┆ 0.0           │
# │ 2000 ┆ 5133   ┆ 5133       ┆ 0.0           │
# │ 2001 ┆ 5162   ┆ 5162       ┆ 0.0           │
# │ 2002 ┆ 5155   ┆ 5155       ┆ 0.0           │
# │ 2003 ┆ 5182   ┆ 5182       ┆ 0.0           │
# │ …    ┆ …      ┆ …          ┆ …             │
# │ 2017 ┆ 5246   ┆ 5246       ┆ 0.0           │
# │ 2018 ┆ 5142   ┆ 5142       ┆ 0.0           │
# │ 2019 ┆ 5071   ┆ 5071       ┆ 0.0           │
# │ 2020 ┆ 4995   ┆ 4995       ┆ 0.0           │
# │ 2021 ┆ 4920   ┆ 4920       ┆ 0.0           │
# └──────┴────────┴────────────┴───────────────┘
# 
# WARNING: Requested years [2020, 2021] have no grant data.
# Falling back to most recent years with data: [2010, 2009]
# DEVIATION: Rule 1 (auto-fix blocking issue) -- using available years.
# 
# After year + Pell filter: 11,023 rows x 13 cols
# 
# Post-filter state:
#   Rows: 11,023
#   Columns: ['unitid', 'year', 'fips', 'opeid', 'inst_name_fsa', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid', 'allocation_flag', 'combined_flag', 'other_assoc_opeids']
#   Years selected: [2010, 2009]
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_fsa_grants.parquet
# 
# ----------------------------------------
# SUMMARY
# ----------------------------------------
# Unique unitids: 5,664
# Years present: [2009, 2010]
#   grant_recipients_unitid: 8,569 non-null, 2,454 null (22.3%)
#     range: 0.0 - 6,419.0, sum: 1,363,037.0000190735
#   value_grants_disbursed_unitid: 8,569 non-null, 2,454 null (22.3%)
#     range: 0.0 - 4,912,453.0, sum: 1,026,595,175.7998047
#   grant_recipients_opeid: 8,569 non-null, 2,454 null (22.3%)
#     range: 0.0 - 6,419.0, sum: 1,364,632.0
#   value_grants_disbursed_opeid: 8,569 non-null, 2,454 null (22.3%)
#     range: 0.0 - 4,912,453.0, sum: 1,027,630,596.64
# 
# Total Pell recipients (grant_recipients_opeid): 1,364,632.0
# grant_recipients_opeid range: 0.0 - 6,419.0
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
# [PASS] Row count: 11,023 (expected 8,000-15,000)
# [PASS] All 7 required columns present (both _unitid and _opeid variants)
# [PASS] All selected years present: [2009, 2010]
# [WARN] Years differ from Plan specification: selected [2010, 2009], Plan requested [2020, 2021]
# [PASS] grant_type contains only Pell (1): [1]
# [WARN] unitid: 0.1% null
# [PASS] year: 0.0% null
# [NOTE] grant_recipients_opeid: 22.3% null
# [NOTE] grant_recipients_unitid: 22.3% null
# [FAIL] Neither grant_recipients_opeid nor grant_recipients_unitid has data (<10% null)
# [WARN] Data lag: Plan requested up to 2021, using 2010 (11-year data lag)
# 
# Row counts by year:
#   2009: 5,490
#   2010: 5,533
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py", line 403, in <module>
#     assert cp1_passed, "STOP: CP1 validation failed -- see details above"
#            ^^^^^^^^^^
# AssertionError: STOP: CP1 validation failed -- see details above
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
