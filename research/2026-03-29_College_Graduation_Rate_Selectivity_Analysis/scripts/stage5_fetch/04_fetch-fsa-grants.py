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
# ASSUMES:
#   - At least one mirror is available and serves this dataset
#   - Dataset contains "year", "grant_type", "unitid" columns
#   - grant_type == 1 corresponds to Pell Grants per FSA documentation
#   - All variable names are lowercase (Portal convention)
print("=" * 60)
print("Stage 5.4: Fetch FSA Grants (Pell)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

print("\nFetching FSA grants data...")
# INTENT: Fetch full dataset from mirrors, then filter to years and Pell only.
# REASONING: Applying year filter during fetch for efficiency, then applying
# grant_type filter separately for clarity in the audit trail.
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"After year filter: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state BEFORE grant_type filter for audit trail.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state (after year filter, before grant_type filter):")
print(f"  Rows: {pre_rows:,}")
print(f"  Columns: {len(pre_cols)}")
print(f"  Column names: {pre_cols}")

# Check what grant_type values exist before filtering
if "grant_type" in df.columns:
    grant_types = df["grant_type"].value_counts().sort("grant_type")
    print(f"\nGrant type distribution (before filter):")
    print(grant_types)
else:
    print("\nWARNING: 'grant_type' column not found in dataset")

# --- Filter to Pell Grants ---
# INTENT: Keep only Pell Grant records (grant_type == 1).
# REASONING: The research question examines the relationship between
# selectivity and graduation rates. Pell Grant receipt is the standard proxy
# for low-income student enrollment at the institutional level, used by
# IPEDS GRS reporting and College Scorecard.
# ASSUMES: grant_type == 1 is Pell Grant per FSA data documentation.
df = df.filter(pl.col("grant_type") == 1)
print(f"\nAfter Pell filter (grant_type == 1): {df.shape[0]:,} rows")

# --- Post-state ---
post_rows = df.shape[0]
print(f"\nPost-state:")
print(f"  Rows: {post_rows:,}")
print(f"  Row change from pre-state: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100:+.1f}%)")

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- Summary Statistics ---
# INTENT: Log key summary metrics for downstream verification and audit.
print("\n" + "-" * 40)
print("SUMMARY")
print("-" * 40)
n_unitids = df["unitid"].n_unique()
print(f"Unique unitids: {n_unitids:,}")
print(f"Years present: {sorted(df['year'].unique().to_list())}")

if "grant_recipients_unitid" in df.columns:
    total_recipients = df["grant_recipients_unitid"].sum()
    min_recip = df["grant_recipients_unitid"].min()
    max_recip = df["grant_recipients_unitid"].max()
    print(f"Total Pell recipients across all institutions: {total_recipients:,}")
    print(f"grant_recipients_unitid range: {min_recip} - {max_recip:,}")

if "value_grants_disbursed_unitid" in df.columns:
    total_disbursed = df["value_grants_disbursed_unitid"].sum()
    print(f"Total Pell disbursements: ${total_disbursed:,.0f}")

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
required_cols = ["unitid", "year", "grant_type", "grant_recipients_unitid", "value_grants_disbursed_unitid"]
missing_cols = [c for c in required_cols if c not in df.columns]
cols_present = len(missing_cols) == 0
if cols_present:
    print(f"[PASS] All {len(required_cols)} required columns present")
else:
    print(f"[FAIL] Missing required columns: {missing_cols}")
    cp1_passed = False

# CP1.3: Years present -- both 2020 and 2021
years_found = sorted(df["year"].unique().to_list())
all_years = all(y in years_found for y in YEARS)
if all_years:
    print(f"[PASS] All expected years present: {years_found}")
else:
    print(f"[FAIL] Missing years. Found: {years_found}, expected: {YEARS}")
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
critical_null_cols = ["unitid", "year", "grant_recipients_unitid"]
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

# CP1.6: Year freshness / data lag check
# REASONING: FSA data typically has 1-3 year lag. Flag if max year is less
# than expected.
max_expected_year = max(YEARS)
max_actual_year = df["year"].max()
if max_actual_year < max_expected_year:
    lag = max_expected_year - max_actual_year
    print(f"[WARN] Data lag: requested up to {max_expected_year}, latest available {max_actual_year} ({lag}-year lag)")

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
# Executed: 2026-03-29 20:17:43
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA Grants (Pell)
# ============================================================
# 
# Fetching FSA grants data...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/fsa/colleges_fsa_grants.parquet
#   Success huggingface: 608,510 rows
#   After filters: 49,575 rows
# After year filter: 49,575 rows x 13 cols
# 
# Pre-state (after year filter, before grant_type filter):
#   Rows: 49,575
#   Columns: 13
#   Column names: ['unitid', 'year', 'fips', 'opeid', 'inst_name_fsa', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid', 'allocation_flag', 'combined_flag', 'other_assoc_opeids']
# 
# Grant type distribution (before filter):
# shape: (5, 2)
# ┌────────────┬───────┐
# │ grant_type ┆ count │
# │ ---        ┆ ---   │
# │ i64        ┆ u32   │
# ╞════════════╪═══════╡
# │ 1          ┆ 9915  │
# │ 2          ┆ 9915  │
# │ 3          ┆ 9915  │
# │ 4          ┆ 9915  │
# │ 5          ┆ 9915  │
# └────────────┴───────┘
# 
# After Pell filter (grant_type == 1): 9,915 rows
# 
# Post-state:
#   Rows: 9,915
#   Row change from pre-state: -39,660 (-80.0%)
# 
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_fsa_grants.parquet
# 
# ----------------------------------------
# SUMMARY
# ----------------------------------------
# Unique unitids: 5,009
# Years present: [2020, 2021]
# Total Pell recipients across all institutions: 0.0
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py", line 234, in <module>
#     print(f"grant_recipients_unitid range: {min_recip} - {max_recip:,}")
#                                                          ^^^^^^^^^^^^^
# TypeError: unsupported format string passed to NoneType.__format__
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
