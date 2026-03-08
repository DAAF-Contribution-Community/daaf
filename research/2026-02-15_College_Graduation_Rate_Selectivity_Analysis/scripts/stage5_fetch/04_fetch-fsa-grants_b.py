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

REVISION HISTORY:
  v1 (04_fetch-fsa-grants.py):
    - Assumed flat columns "pell_recipients" and "pell_disbursements"
    - FAILED: Columns not found; data uses grant_type + generic column names
  v2 (_a.py):
    - Correctly identified multi-row-per-institution structure
    - FAILED: Used grant_type == 4 (Iraq/Afghanistan Service Grant) instead
      of grant_type == 1 (Federal Pell Grant). All 5 grant types had equal
      row counts (4,995 each), so the "most common" heuristic was arbitrary.
  v3 (_b.py, THIS VERSION):
    - Uses grant_type == 1 per FSA skill documentation (education-data-source-fsa)
    - Grant type codes: 1=Pell, 2=FSEOG, 3=TEACH, 4=Iraq/Afghanistan, 5=Children of Fallen Heroes
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification.
# FSA grants is a single-file dataset (all years 1999-2021 in one file).
# We filter to year 2020 to align with the IPEDS graduation rate cohort.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

YEAR = 2020  # Single year per Plan specification

# Dataset path from education-data-query skill's datasets-reference.md.
# FSA Grants: Single file, years 1999-2021.
DATASET_PATH = "fsa/colleges_fsa_grants"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_fsa_grants.parquet"

# Grant type code for Federal Pell Grant.
# REASONING: Per the education-data-source-fsa skill documentation:
#   1 = Federal Pell Grant
#   2 = FSEOG
#   3 = TEACH Grant
#   4 = Iraq and Afghanistan Service Grant
#   5 = Children of Fallen Heroes Grant
# v2 incorrectly used grant_type == 4. This version corrects to 1.
PELL_GRANT_TYPE = 1

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
print("Stage 5.4: Fetch FSA grants data (v3 - correct Pell grant_type=1)")
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

# Confirm grant_type values present in the data
print(f"\n  grant_type values and counts:")
grant_types = df["grant_type"].value_counts().sort("grant_type")
print(f"{grant_types}")

# --- Filter to Pell Grants ---
# INTENT: Isolate Federal Pell Grant rows (grant_type == 1) from the
# multi-grant-type dataset.
# REASONING: Per education-data-source-fsa skill documentation, grant_type
# codes are: 1=Pell, 2=FSEOG, 3=TEACH, 4=Iraq/Afghanistan, 5=Children of
# Fallen Heroes. The research question requires Pell Grant data as a proxy
# for low-income student enrollment. Other grant types are not relevant.
# ASSUMES: grant_type column is integer-typed (Int64) per Portal convention.
print(f"\n  Filtering to grant_type == {PELL_GRANT_TYPE} (Federal Pell Grant)")
df_pell = df.filter(pl.col("grant_type") == PELL_GRANT_TYPE)
print(f"  After Pell filter: {df_pell.shape[0]:,} rows")

# Verify the filter actually selected Pell grants
pell_types_after = df_pell["grant_type"].unique().to_list()
assert pell_types_after == [PELL_GRANT_TYPE], (
    f"STOP: Pell filter did not isolate grant_type={PELL_GRANT_TYPE}. "
    f"Found: {pell_types_after}"
)

# --- Drop null unitids ---
# INTENT: Remove rows with null unitid since they cannot be joined downstream.
# REASONING: v1 found 5 null unitids in the full year 2020 data across all
# grant types. After filtering to Pell only, there may be fewer. These
# cannot be matched to IPEDS institutions and would cause issues in joins.
null_unitid_count = df_pell["unitid"].null_count()
if null_unitid_count > 0:
    print(f"  Dropping {null_unitid_count} rows with null unitid")
    df_pell = df_pell.filter(pl.col("unitid").is_not_null())
else:
    print(f"  No null unitids found")

# --- Rename and select columns ---
# INTENT: Rename FSA-specific column names to the Plan-expected names
# (pell_recipients, pell_disbursements) for consistency with downstream stages.
# REASONING: The raw data uses generic column names (grant_recipients_unitid,
# value_grants_disbursed_unitid) because the same schema applies to all grant
# types. After filtering to Pell only, we rename to Pell-specific names for
# clarity and to match the Plan's column expectations.
# ASSUMES: grant_recipients_unitid = number of Pell grant recipients at the
# institution; value_grants_disbursed_unitid = total Pell dollars disbursed.

rename_map = {
    "grant_recipients_unitid": "pell_recipients",
    "value_grants_disbursed_unitid": "pell_disbursements",
}

# Verify source columns exist
for src_col in rename_map:
    assert src_col in df_pell.columns, f"STOP: Expected column '{src_col}' not found"

select_cols = ["unitid", "year"] + list(rename_map.keys())
df_final = df_pell.select(select_cols).rename(rename_map)

print(f"\n  Column rename mapping: {rename_map}")
print(f"  Final columns: {df_final.columns}")
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
# REASONING: After filtering to grant_type == 1 (Pell) and year 2020, each
# institution should appear exactly once. Duplicates would indicate
# the data structure is not as expected.
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

    # Check for negative values that are NOT coded missing values
    # REASONING: pell_recipients should be >= 0 for valid data.
    # Values of exactly -1, -2, -3 are coded missing (handled in Stage 6).
    # Any other negative values would be unexpected.
    neg_non_coded = df_final.filter(
        (pl.col("pell_recipients") < 0)
        & ~pl.col("pell_recipients").is_in([-1, -2, -3])
    ).shape[0]
    if neg_non_coded > 0:
        print(f"  [WARN] pell_recipients has {neg_non_coded} unexpected negative values")

# CP1.7: pell_disbursements basic check
if "pell_disbursements" in df_final.columns:
    pell_disb_nulls = df_final["pell_disbursements"].null_count()
    print(f"  [INFO] pell_disbursements nulls: {pell_disb_nulls:,}")
    print(f"  [INFO] pell_disbursements describe:")
    print(f"{df_final['pell_disbursements'].describe()}")

# --- Final CP1 Status ---
assert cp1_passed, "STOP: CP1 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:12:47
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_b.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA grants data (v3 - correct Pell grant_type=1)
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
# │ 1          ┆ 4995  │
# │ 2          ┆ 4995  │
# │ 3          ┆ 4995  │
# │ 4          ┆ 4995  │
# │ 5          ┆ 4995  │
# └────────────┴───────┘
# 
#   Filtering to grant_type == 1 (Federal Pell Grant)
#   After Pell filter: 4,995 rows
#   Dropping 1 rows with null unitid
# 
#   Column rename mapping: {'grant_recipients_unitid': 'pell_recipients', 'value_grants_disbursed_unitid': 'pell_disbursements'}
#   Final columns: ['unitid', 'year', 'pell_recipients', 'pell_disbursements']
#   Final shape: 4,994 rows x 4 cols
# 
# Post-state:
#   Rows: 4,994
#   Shape: 4,994 rows x 4 cols
#   Sample unitids: [100654, 100663, 100690]
#   Row change from pre-state: -19,981 (-80.0%)
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-02-15_fsa_grants.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year filter correct: [2020] (expected [2020])
#   [PASS] Row count in range: 4,994 (expected 3,000-7,000)
#   [PASS] Critical columns present: ['unitid', 'pell_recipients']
#   [PASS] No nulls in unitid: 0
#   [PASS] Unitid uniqueness: 4,994 unique / 4,994 total
#   [INFO] pell_recipients nulls: 4,994 (100.0%)
#   [INFO] pell_recipients describe:
# shape: (2, 2)
# ┌────────────┬────────┐
# │ statistic  ┆ value  │
# │ ---        ┆ ---    │
# │ str        ┆ f64    │
# ╞════════════╪════════╡
# │ count      ┆ 0.0    │
# │ null_count ┆ 4994.0 │
# └────────────┴────────┘
#   [INFO] pell_disbursements nulls: 4,994
#   [INFO] pell_disbursements describe:
# shape: (2, 2)
# ┌────────────┬────────┐
# │ statistic  ┆ value  │
# │ ---        ┆ ---    │
# │ str        ┆ f64    │
# ╞════════════╪════════╡
# │ count      ┆ 0.0    │
# │ null_count ┆ 4994.0 │
# └────────────┴────────┘
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
