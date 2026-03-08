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

# Columns to retain from the FSA grants dataset.
# REASONING: We only need Pell Grant columns for this analysis. Keeping the
# full dataset would add unnecessary columns (loan data, campus-based aid)
# that are not relevant to the research question about graduation rates
# and selectivity. Selecting early reduces memory footprint and downstream
# confusion.
KEEP_COLUMNS = ["unitid", "year", "pell_recipients", "pell_disbursements"]

# Critical columns that MUST be present for downstream joins and analysis.
# unitid: institution identifier for joining with IPEDS data
# pell_recipients: primary variable measuring low-income student enrollment
CRITICAL_COLUMNS = ["unitid", "pell_recipients"]

# Expected row count range for year 2020.
# REASONING: There are roughly 5,000-7,000 Title IV institutions in any given
# year. The FSA dataset covers all Title IV-participating institutions. Some
# institutions may have zero Pell recipients but still appear in the data.
# The Plan estimates 3,000-7,000 rows.
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
print("Stage 5.4: Fetch FSA grants data")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download FSA grants dataset and filter to year 2020.
# REASONING: Single-file dataset (all years 1999-2021 in one file). Download
# once, filter locally with Polars. Year 2020 aligns with IPEDS graduation
# rate cohort year used in this analysis.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year"
# column for filtering. Dataset contains unitid for institutional identification.
print("\nFetching FSA grants data...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)

# --- Pre-state ---
# Capture state after fetch (before column selection) for audit trail.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state (after year filter, before column select):")
print(f"  Rows: {pre_rows:,}")
print(f"  Columns ({len(pre_cols)}): {pre_cols}")
print(f"  Sample unitids: {df['unitid'].head(3).to_list()}")

# --- Column Selection ---
# INTENT: Retain only the columns needed for this analysis to reduce
# downstream complexity and file size.
# REASONING: The FSA grants dataset contains many columns related to loans,
# campus-based aid, etc. We only need Pell Grant columns (pell_recipients,
# pell_disbursements) plus identifiers (unitid, year).
# ASSUMES: All KEEP_COLUMNS exist in the fetched dataset.

# Verify all requested columns exist before selecting
missing_cols = [c for c in KEEP_COLUMNS if c not in df.columns]
if missing_cols:
    print(f"\nWARNING: Missing columns: {missing_cols}")
    print(f"Available columns: {df.columns}")
    # Select only columns that exist
    available_keep = [c for c in KEEP_COLUMNS if c in df.columns]
    df = df.select(available_keep)
else:
    df = df.select(KEEP_COLUMNS)

print(f"\nPost column selection: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Post-state ---
post_rows = df.shape[0]
print(f"\nPost-state:")
print(f"  Rows: {post_rows:,}")
print(f"  Shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"  Sample unitids: {df['unitid'].head(3).to_list()}")
print(f"  Row change: {post_rows - pre_rows:+,} ({(post_rows - pre_rows) / pre_rows * 100 if pre_rows > 0 else 0:+.1f}%)")

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# year coverage, row counts, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Correct year present
years_found = sorted(df["year"].unique().to_list())
year_ok = years_found == [YEAR]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Year filter correct: {years_found} (expected [{YEAR}])")
if not year_ok:
    cp1_passed = False

# CP1.2: Row count in expected range
row_count = df.shape[0]
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"  [{'PASS' if rows_ok else 'WARN'}] Row count in range: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")
if not rows_ok:
    # Row count outside range is a warning, not a hard failure, because
    # the estimate may be approximate. But if zero rows, that's a failure.
    if row_count == 0:
        cp1_passed = False
        print("  STOP: Zero rows returned")

# CP1.3: Critical columns present
critical_present = all(c in df.columns for c in CRITICAL_COLUMNS)
print(f"  [{'PASS' if critical_present else 'FAIL'}] Critical columns present: {CRITICAL_COLUMNS}")
if not critical_present:
    missing = [c for c in CRITICAL_COLUMNS if c not in df.columns]
    print(f"  Missing: {missing}")
    cp1_passed = False

# CP1.4: No nulls in identifier column (unitid)
unitid_nulls = df["unitid"].null_count()
unitid_ok = unitid_nulls == 0
print(f"  [{'PASS' if unitid_ok else 'FAIL'}] No nulls in unitid: {unitid_nulls}")
if not unitid_ok:
    cp1_passed = False

# CP1.5: Unitid uniqueness check
# REASONING: Each institution should appear once per year in FSA data.
# Duplicates would indicate data issues that could corrupt downstream joins.
unitid_unique_count = df["unitid"].n_unique()
unitid_total = df.shape[0]
unitid_unique = unitid_unique_count == unitid_total
print(f"  [{'PASS' if unitid_unique else 'WARN'}] Unitid uniqueness: {unitid_unique_count:,} unique / {unitid_total:,} total")

# CP1.6: pell_recipients basic distribution check
# REASONING: pell_recipients should be non-negative for valid institutions.
# Coded values (-1, -2, -3) may be present and are handled in Stage 6.
if "pell_recipients" in df.columns:
    pell_null_count = df["pell_recipients"].null_count()
    pell_null_pct = pell_null_count / len(df) * 100 if len(df) > 0 else 0
    pell_stats = df["pell_recipients"].describe()
    print(f"  [INFO] pell_recipients nulls: {pell_null_count:,} ({pell_null_pct:.1f}%)")
    print(f"  [INFO] pell_recipients stats:\n{pell_stats}")

    # Check for coded values that will be handled in Stage 6
    for code in [-1, -2, -3]:
        coded_count = (df["pell_recipients"] == code).sum()
        if coded_count > 0:
            print(f"  [INFO] pell_recipients coded value {code}: {coded_count:,} rows (handled in Stage 6)")

# CP1.7: pell_disbursements basic check
if "pell_disbursements" in df.columns:
    pell_disb_nulls = df["pell_disbursements"].null_count()
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
# Executed: 2026-02-15 19:09:03
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA grants data
# ============================================================
# 
# Fetching FSA grants data...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/fsa/colleges_fsa_grants.parquet
#   OK huggingface: 608,510 rows
#   After filters: 24,975 rows
# 
# Pre-state (after year filter, before column select):
#   Rows: 24,975
#   Columns (13): ['unitid', 'year', 'fips', 'opeid', 'inst_name_fsa', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid', 'allocation_flag', 'combined_flag', 'other_assoc_opeids']
#   Sample unitids: [100654, 100654, 100654]
# 
# WARNING: Missing columns: ['pell_recipients', 'pell_disbursements']
# Available columns: ['unitid', 'year', 'fips', 'opeid', 'inst_name_fsa', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid', 'allocation_flag', 'combined_flag', 'other_assoc_opeids']
# 
# Post column selection: 24,975 rows x 2 cols
# Columns: ['unitid', 'year']
# 
# Post-state:
#   Rows: 24,975
#   Shape: 24,975 rows x 2 cols
#   Sample unitids: [100654, 100654, 100654]
#   Row change: +0 (+0.0%)
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-02-15_fsa_grants.parquet
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Year filter correct: [2020] (expected [2020])
#   [WARN] Row count in range: 24,975 (expected 3,000-7,000)
#   [FAIL] Critical columns present: ['unitid', 'pell_recipients']
#   Missing: ['pell_recipients']
#   [FAIL] No nulls in unitid: 5
#   [WARN] Unitid uniqueness: 4,995 unique / 24,975 total
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants.py", line 318, in <module>
#     assert cp1_passed, "STOP: CP1 validation failed -- see details above"
#            ^^^^^^^^^^
# AssertionError: STOP: CP1 validation failed -- see details above
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
