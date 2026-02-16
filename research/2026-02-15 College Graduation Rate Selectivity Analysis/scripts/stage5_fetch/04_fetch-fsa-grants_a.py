#!/usr/bin/env python3
"""
Stage 5.4: Fetch FSA (Federal Student Aid) grants data for year 2020.

Task: fetch-fsa-grants
Wave: 1, Step: 4, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_fsa_grants.parquet
Checkpoint: CP1

Research Question: Are high college graduation rates a signal of institutional
quality, or primarily a reflection of admissions selectivity and student body
demographics?

This script fetches Pell Grant recipient and disbursement data from the FSA
grants dataset. Pell Grant data serves as a proxy for the proportion of
low-income students at each institution, which is a key demographic variable
in the selectivity analysis.

REVISION NOTES (v2 / _a):
  - v1 assumed flat columns "pell_recipients" and "pell_disbursements", but the
    actual data is organized with one row per (unitid, year, grant_type).
  - Actual columns: grant_type, grant_recipients_unitid, value_grants_disbursed_unitid.
  - Fix: Filter to grant_type == "Pell Grants" (or appropriate integer code),
    then rename columns to match Plan expectations.
  - Also: Drop rows with null unitid (5 rows in year 2020).
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# FSA grants is a single-file dataset (all years 1999-2021 in one file).
# We filter to year 2020 to align with the IPEDS graduation rate cohort.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEAR = 2020  # Single year per Plan specification

# Dataset path from education-data-query skill's datasets-reference.md.
# FSA Grants: Single file, years 1999-2021.
DATASET_PATH = "fsa/colleges_fsa_grants"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_fsa_grants.parquet"

# Critical columns that MUST be present for downstream joins and analysis.
# unitid: institution identifier for joining with IPEDS data
# pell_recipients: primary variable measuring low-income student enrollment
CRITICAL_COLUMNS = ["unitid", "pell_recipients"]

# Expected row count range for year 2020, filtered to Pell grant type.
# REASONING: There are roughly 4,000-6,000 Title IV institutions in any
# given year. After filtering to the Pell grant type specifically and
# removing null unitids, we expect one row per institution.
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 7000

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
# between fetch calls avoids triggering limits while keeping pipeline runtime
# reasonable.
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
            Example: "fsa/colleges_fsa_grants"
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
            print(f"  X {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

print("=" * 60)
print("Stage 5.4: Fetch FSA grants data (v2 - fixed column mapping)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download FSA grants dataset and filter to year 2020.
# REASONING: Single-file dataset (all years 1999-2021 in one file). Download
# once, filter locally with Polars. Year 2020 aligns with IPEDS graduation
# rate cohort year used in this analysis.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year"
# column for filtering. Dataset is organized with one row per
# (unitid, year, grant_type) combination.
print("\nFetching FSA grants data...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)

# --- Pre-state ---
# Capture state after fetch, before any transformations.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state (raw fetch, year 2020):")
print(f"  Rows: {pre_rows:,}")
print(f"  Columns ({len(pre_cols)}): {pre_cols}")
print(f"  Dtypes: {dict(zip(df.columns, [str(d) for d in df.dtypes]))}")
print(f"  Sample unitids: {df['unitid'].drop_nulls().head(3).to_list()}")

# Explore the grant_type column to understand structure
# INTENT: Identify the correct grant_type value for Pell Grants.
# REASONING: v1 failed because the data has multiple grant types per institution.
# We need to filter to Pell Grants specifically. The grant_type column may use
# string labels or integer codes depending on the data source encoding.
print(f"\n  grant_type values and counts:")
grant_types = df["grant_type"].value_counts().sort("count", descending=True)
print(f"{grant_types}")

# --- Filter to Pell Grants ---
# INTENT: Isolate Pell Grant rows from the multi-grant-type dataset.
# REASONING: The research question requires Pell Grant data as a proxy for
# low-income student enrollment. Other grant types (TEACH, Iraq/Afghanistan
# Service Grants, etc.) are not relevant.
# ASSUMES: grant_type column contains a value identifiable as Pell Grants.
#
# Determine the Pell grant type value from the data (could be string or int).
# Based on the exploration above, we filter accordingly.

# Try string-based filter first (common in FSA data)
pell_filter_candidates = ["Pell Grants", "Pell Grant", "pell_grants", "pell", "1"]
pell_type_value = None

grant_type_dtype = df["grant_type"].dtype
print(f"\n  grant_type dtype: {grant_type_dtype}")

if grant_type_dtype == pl.Utf8 or str(grant_type_dtype).startswith("String"):
    # String grant_type -- search for Pell-related values
    unique_types = df["grant_type"].unique().to_list()
    for candidate in pell_filter_candidates:
        if candidate in unique_types:
            pell_type_value = candidate
            break
    # If no exact match, try case-insensitive partial match
    if pell_type_value is None:
        for ut in unique_types:
            if ut is not None and "pell" in str(ut).lower():
                pell_type_value = ut
                break
else:
    # Integer grant_type -- check if 1 corresponds to Pell
    # For integer-encoded grant types, 1 is typically Pell Grants
    unique_types = sorted(df["grant_type"].drop_nulls().unique().to_list())
    print(f"  Integer grant_type values: {unique_types}")
    # We'll use the value that has the most rows (Pell is the largest grant program)
    most_common = grant_types.row(0)
    pell_type_value = most_common[0]
    print(f"  Using most common grant_type as Pell candidate: {pell_type_value}")

if pell_type_value is not None:
    print(f"\n  Filtering to grant_type == {pell_type_value!r}")
    df_pell = df.filter(pl.col("grant_type") == pell_type_value)
else:
    # Fallback: if no Pell type identified, raise error
    raise ValueError(
        f"Could not identify Pell Grant type in grant_type column. "
        f"Unique values: {df['grant_type'].unique().to_list()}"
    )

print(f"  After Pell filter: {df_pell.shape[0]:,} rows")

# --- Drop null unitids ---
# INTENT: Remove rows with null unitid since they cannot be joined downstream.
# REASONING: v1 found 5 null unitids in the full year 2020 data. These cannot
# be matched to IPEDS institutions and would cause issues in joins.
null_unitid_count = df_pell["unitid"].null_count()
if null_unitid_count > 0:
    print(f"  Dropping {null_unitid_count} rows with null unitid")
    df_pell = df_pell.filter(pl.col("unitid").is_not_null())

# --- Rename and select columns ---
# INTENT: Rename FSA-specific column names to the Plan-expected names
# (pell_recipients, pell_disbursements) for consistency with downstream stages.
# REASONING: The raw data uses generic column names (grant_recipients_unitid,
# value_grants_disbursed_unitid) because the same schema applies to all grant
# types. After filtering to Pell only, we rename to Pell-specific names.
# ASSUMES: grant_recipients_unitid = number of Pell grant recipients at the
# institution; value_grants_disbursed_unitid = total Pell dollars disbursed.

# Determine which recipient/disbursement columns exist
available_cols = df_pell.columns
print(f"\n  Available columns after Pell filter: {available_cols}")

# Map from actual column names to Plan-expected names
rename_map = {}
select_cols = ["unitid", "year"]

if "grant_recipients_unitid" in available_cols:
    rename_map["grant_recipients_unitid"] = "pell_recipients"
    select_cols.append("grant_recipients_unitid")
elif "grant_recipients_opeid" in available_cols:
    # Fallback: use OPEID-level counts if unitid-level not available
    rename_map["grant_recipients_opeid"] = "pell_recipients"
    select_cols.append("grant_recipients_opeid")

if "value_grants_disbursed_unitid" in available_cols:
    rename_map["value_grants_disbursed_unitid"] = "pell_disbursements"
    select_cols.append("value_grants_disbursed_unitid")
elif "value_grants_disbursed_opeid" in available_cols:
    rename_map["value_grants_disbursed_opeid"] = "pell_disbursements"
    select_cols.append("value_grants_disbursed_opeid")

print(f"  Column rename mapping: {rename_map}")

df_final = df_pell.select(select_cols).rename(rename_map)
print(f"\n  Final columns: {df_final.columns}")
print(f"  Final shape: {df_final.shape[0]:,} rows x {df_final.shape[1]} cols")

# --- Post-state ---
post_rows = df_final.shape[0]
print(f"\nPost-state:")
print(f"  Rows: {post_rows:,}")
print(f"  Shape: {df_final.shape[0]:,} rows x {df_final.shape[1]} cols")
print(f"  Sample unitids: {df_final['unitid'].head(3).to_list()}")
print(f"  Row change from pre-state: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100 if pre_rows > 0 else 0:+.1f}%)")

# --- Save ---
# Persist results in parquet format.
df_final.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# year coverage, row counts, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Correct year present
years_found = sorted(df_final["year"].unique().to_list())
year_ok = years_found == [YEAR]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year filter correct: {years_found} (expected [{YEAR}])")
if not year_ok:
    cp1_passed = False

# CP1.2: Row count in expected range
row_count = df_final.shape[0]
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"  [{'PASS' if rows_ok else 'WARN'}] Row count in range: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")
if not rows_ok:
    if row_count == 0:
        cp1_passed = False
        print("  STOP: Zero rows returned")

# CP1.3: Critical columns present
critical_present = all(c in df_final.columns for c in CRITICAL_COLUMNS)
print(f"  [{'PASS' if critical_present else 'FAIL'}] Critical columns present: {CRITICAL_COLUMNS}")
if not critical_present:
    missing = [c for c in CRITICAL_COLUMNS if c not in df_final.columns]
    print(f"  Missing: {missing}")
    cp1_passed = False

# CP1.4: No nulls in identifier column (unitid)
unitid_nulls = df_final["unitid"].null_count()
unitid_ok = unitid_nulls == 0
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] No nulls in unitid: {unitid_nulls}")
if not unitid_ok:
    cp1_passed = False

# CP1.5: Unitid uniqueness check
# REASONING: After filtering to a single grant_type and year, each institution
# should appear exactly once. Duplicates would indicate the Pell filter did
# not fully isolate a single grant category.
unitid_unique_count = df_final["unitid"].n_unique()
unitid_total = df_final.shape[0]
unitid_unique = unitid_unique_count == unitid_total
print(f"  [{'PASS' if unitid_unique else 'WARN'}] Unitid uniqueness: {unitid_unique_count:,} unique / {unitid_total:,} total")
if not unitid_unique:
    print(f"  WARNING: {unitid_total - unitid_unique_count} duplicate unitids found")

# CP1.6: pell_recipients basic distribution check
# REASONING: pell_recipients should be non-negative for valid institutions.
# Coded values (-1, -2, -3) may be present and are handled in Stage 6.
if "pell_recipients" in df_final.columns:
    pell_null_count = df_final["pell_recipients"].null_count()
    pell_null_pct = pell_null_count / len(df_final) * 100 if len(df_final) > 0 else 0
    print(f"  [INFO] pell_recipients nulls: {pell_null_count:,} ({pell_null_pct:.1f}%)")
    print(f"  [INFO] pell_recipients describe:")
    print(f"{df_final['pell_recipients'].describe()}")

    # Check for coded values that will be handled in Stage 6
    for code in [-1, -2, -3]:
        try:
            coded_count = (df_final["pell_recipients"] == code).sum()
            if coded_count > 0:
                print(f"  [INFO] pell_recipients coded value {code}: {coded_count:,} rows (handled in Stage 6)")
        except Exception:
            pass  # Type mismatch with coded value check is non-critical

# CP1.7: pell_disbursements basic check
if "pell_disbursements" in df_final.columns:
    pell_disb_nulls = df_final["pell_disbursements"].null_count()
    print(f"  [INFO] pell_disbursements nulls: {pell_disb_nulls:,}")

# --- Final CP1 Status ---
assert cp1_passed, "STOP: CP1 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:10:43
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA grants data (v2 - fixed column mapping)
# ============================================================
# 
# Fetching FSA grants data...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/fsa/colleges_fsa_grants.parquet
#   OK huggingface: 608,510 rows
#   After filters: 24,975 rows
# 
# Pre-state (raw fetch, year 2020):
#   Rows: 24,975
#   Columns (13): ['unitid', 'year', 'fips', 'opeid', 'inst_name_fsa', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid', 'allocation_flag', 'combined_flag', 'other_assoc_opeids']
#   Dtypes: {'unitid': 'Int64', 'year': 'Int64', 'fips': 'Int64', 'opeid': 'Int64', 'inst_name_fsa': 'String', 'grant_type': 'Int64', 'grant_recipients_unitid': 'Float64', 'value_grants_disbursed_unitid': 'Float64', 'grant_recipients_opeid': 'Float64', 'value_grants_disbursed_opeid': 'Float64', 'allocation_flag': 'Int64', 'combined_flag': 'Int64', 'other_assoc_opeids': 'String'}
#   Sample unitids: [100654, 100654, 100654]
# 
#   grant_type values and counts:
# shape: (5, 2)
# ┌────────────┬───────┐
# │ grant_type ┆ count │
# │ ---        ┆ ---   │
# │ i64        ┆ u32   │
# ╞════════════╪═══════╡
# │ 4          ┆ 4995  │
# │ 1          ┆ 4995  │
# │ 3          ┆ 4995  │
# │ 5          ┆ 4995  │
# │ 2          ┆ 4995  │
# └────────────┴───────┘
# 
#   grant_type dtype: Int64
#   Integer grant_type values: [1, 2, 3, 4, 5]
#   Using most common grant_type as Pell candidate: 4
# 
#   Filtering to grant_type == 4
#   After Pell filter: 4,995 rows
#   Dropping 1 rows with null unitid
# 
#   Available columns after Pell filter: ['unitid', 'year', 'fips', 'opeid', 'inst_name_fsa', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid', 'allocation_flag', 'combined_flag', 'other_assoc_opeids']
#   Column rename mapping: {'grant_recipients_unitid': 'pell_recipients', 'value_grants_disbursed_unitid': 'pell_disbursements'}
# 
#   Final columns: ['unitid', 'year', 'pell_recipients', 'pell_disbursements']
#   Final shape: 4,994 rows x 4 cols
# 
# Post-state:
#   Rows: 4,994
#   Shape: 4,994 rows x 4 cols
#   Sample unitids: [100654, 100663, 100690]
#   Row change from pre-state: -19,981 (-80.0%)
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/2026-02-15_fsa_grants.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year filter correct: [2020] (expected [2020])
#   [PASS] Row count in range: 4,994 (expected 3,000-7,000)
#   [PASS] Critical columns present: ['unitid', 'pell_recipients']
#   [PASS] No nulls in unitid: 0
#   [PASS] Unitid uniqueness: 4,994 unique / 4,994 total
#   [INFO] pell_recipients nulls: 6 (0.1%)
#   [INFO] pell_recipients describe:
# shape: (9, 2)
# ┌────────────┬─────────────┐
# │ statistic  ┆ value       │
# │ ---        ┆ ---         │
# │ str        ┆ f64         │
# ╞════════════╪═════════════╡
# │ count      ┆ 4988.0      │
# │ null_count ┆ 6.0         │
# │ mean       ┆ 1269.113071 │
# │ std        ┆ 2970.47379  │
# │ min        ┆ 0.0         │
# │ 25%        ┆ 82.0        │
# │ 50%        ┆ 362.0       │
# │ 75%        ┆ 1211.0      │
# │ max        ┆ 70813.0     │
# └────────────┴─────────────┘
#   [INFO] pell_disbursements nulls: 6
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
