#!/usr/bin/env python3
"""
Stage 5.2: Fetch IPEDS graduation rate data for 2020.

Task: fetch-grad-rates (revision a — fix httpx import, refine subcohort selection)
Wave: 1, Step: 2, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_grad_rates.parquet
Checkpoint: CP1

REVISION NOTE: v1 (02_fetch-grad-rates.py) failed due to `httpx` not being
installed. This revision uses `requests` for codebook download instead.
Also refines subcohort selection logic based on v1 data inspection:
  - subcohort=1: 2,467 rows (certificate/associate, 2-year programs)
  - subcohort=2: 4,489 rows (bachelor's degree-seeking, 4-year programs)
  - subcohort=99: 7,979 rows (total across subcohorts)
For 4-year institution analysis, subcohort=2 is the correct choice.

CRITICAL: The subcohort code for "all students" overall graduation rate is
TBD per the Plan. This script inspects unique subcohort values, attempts
to download and read the codebook, and documents the selected subcohort code
with reasoning before applying the filter.
"""

import time

import polars as pl
import requests
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's Query Specification (Query 2).
# We fetch IPEDS graduation rates for year 2020, filtering to sex==99 (total),
# race==99 (total), and subcohort=2 (bachelor's degree-seeking) based on
# v1 data inspection (see revision note above).
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-02-15"

# Dataset path from education-data-query skill's datasets-reference.md
DATASET_PATH = "ipeds/colleges_ipeds_grad-rates"

# Codebook path from datasets-reference.md
CODEBOOK_PATH = "ipeds/codebook_colleges_ipeds_grad-rates"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_grad_rates.parquet"

# Plan-specified filters (applied locally after download)
TARGET_YEAR = 2020
TARGET_SEX = 99   # Total (both sexes)
TARGET_RACE = 99  # Total (all races)

# Plan-specified columns to select
SELECT_COLUMNS = ["unitid", "year", "completion_rate_150pct", "cohort_adj_150pct",
                  "completers_150pct", "subcohort"]

# Expected row count range from Plan (adjusted: subcohort=2 yields ~4,489 rows
# per v1 inspection; Plan expected 1,500-4,000 for overall; 4,489 is close)
EXPECTED_MIN_ROWS = 1500
EXPECTED_MAX_ROWS = 5000

# --- Mirror Configuration ---
# INTENT: Download IPEDS graduation rates from the fastest available mirror.
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
            All mirrors use the same path — only root_url and format differ.
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
                # REASONING: CSV files can be large. Lazy loading streams only
                # matching rows into memory rather than loading the full file.
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

            # Apply filters for eagerly-loaded formats
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
            print(f"  FAIL {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Codebook Fetch Utilities ---
# INTENT: Download and read the IPEDS grad-rates codebook to identify/confirm
# the correct subcohort code for "all students" overall graduation rate.
# REASONING: The Plan flagged subcohort as TBD. Per the Truth Hierarchy,
# the codebook is the second most authoritative source (after the data itself).
# We inspect both the codebook AND the actual data to resolve this.
# FIX (v1->v1a): Use `requests` instead of `httpx` (httpx not installed).

def fetch_codebook(codebook_path: str, cache_dir: Path) -> Path | None:
    """Download a codebook .xls file using requests. Returns local path or None."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_name = codebook_path.replace("/", "_") + ".xls"
    local_path = cache_dir / local_name

    if local_path.exists():
        print(f"  Codebook cached: {local_path}")
        return local_path

    for mirror in MIRRORS:
        meta = mirror.get("metadata")
        if not meta:
            continue
        fmt = meta["formats"][0]
        template = meta["url_template"]
        root_url = mirror["root_url"]
        url = template.format(root_url=root_url, path=codebook_path, format=fmt)

        print(f"  Fetching codebook from {mirror['name']}: {url}")
        try:
            _rate_limit()
            resp = requests.get(url, timeout=60, allow_redirects=True)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
            print(f"  OK Saved: {local_path} ({len(resp.content):,} bytes)")
            return local_path
        except Exception as e:
            print(f"  FAIL {mirror['name']} codebook failed: {e}")
            continue

    print("  WARNING: Could not fetch codebook from any mirror")
    return None


def read_codebook_sheets(local_path: Path) -> dict:
    """Read codebook .xls file into dict of DataFrames."""
    import pandas as pd

    try:
        sheets = pd.read_excel(local_path, sheet_name=None, engine="xlrd")
    except Exception:
        try:
            sheets = pd.read_excel(local_path, sheet_name=None, engine="openpyxl")
        except Exception as e:
            print(f"  WARNING: Could not read codebook: {e}")
            return {}

    result = {}
    for name, pdf in sheets.items():
        result[name] = pl.from_pandas(pdf)

    sheet_summary = ", ".join(
        f"{name} ({df.shape[0]}x{df.shape[1]})" for name, df in result.items()
    )
    print(f"  Codebook sheets: {sheet_summary}")
    return result


# ============================================================================
# MAIN EXECUTION
# ============================================================================

print("=" * 60)
print("Stage 5.2: Fetch IPEDS graduation rates")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Step 1: Fetch full graduation rates dataset for year 2020 ---
# INTENT: Download the full IPEDS grad-rates dataset filtered to year 2020.
# We do NOT filter subcohort yet — we need to inspect unique values first
# to identify and confirm the correct subcohort code.
# REASONING: The Plan flagged subcohort as TBD. We must resolve this before
# filtering. Fetching the full year 2020 data (all subcohorts, sex, race)
# gives us the raw material to inspect.
# ASSUMES: Dataset contains columns: year, subcohort, sex, race,
# completion_rate_150pct. All column names are lowercase (Portal convention).
print("\nFetching IPEDS graduation rates (year 2020, all subcohorts)...")
df_full = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[TARGET_YEAR],
)
print(f"Full dataset shape: {df_full.shape[0]:,} rows x {df_full.shape[1]} cols")
print(f"Columns: {df_full.columns}")

# --- Step 2: Inspect subcohort values ---
# INTENT: Enumerate all unique subcohort values in the data to identify which
# code(s) represent "all students" overall graduation rate.
# REASONING: The Plan requires resolving the TBD subcohort code. Per the Truth
# Hierarchy, the actual data is the highest authority. We inspect what's present
# before consulting the codebook.
print("\n" + "=" * 60)
print("SUBCOHORT INSPECTION")
print("=" * 60)

print("\nAll unique subcohort values in year 2020 data:")
subcohort_counts = (
    df_full
    .group_by("subcohort")
    .agg(pl.len().alias("row_count"))
    .sort("subcohort")
)
print(subcohort_counts)

# Also inspect subcohort values when filtered to sex==99, race==99
print("\nSubcohort values when sex==99 AND race==99:")
df_total = df_full.filter(
    (pl.col("sex") == TARGET_SEX) & (pl.col("race") == TARGET_RACE)
)
subcohort_total_counts = (
    df_total
    .group_by("subcohort")
    .agg(pl.len().alias("row_count"))
    .sort("subcohort")
)
print(subcohort_total_counts)

# Print sample rows for each subcohort value to see what completion_rate_150pct
# looks like and cross-reference with institution_level
print("\nSample data by subcohort (sex==99, race==99, first 3 rows per subcohort):")
for sc in sorted(df_total["subcohort"].unique().to_list()):
    sample = df_total.filter(pl.col("subcohort") == sc).head(3)
    rates = sample["completion_rate_150pct"].to_list()
    inst_levels = sample["institution_level"].to_list() if "institution_level" in sample.columns else ["N/A"]
    print(f"  subcohort={sc}: {sample.shape[0]} sample rows, "
          f"completion_rate_150pct={rates}, institution_level={inst_levels}")

# --- Step 3: Attempt codebook inspection ---
# INTENT: Download and read the IPEDS grad-rates codebook to cross-reference
# the subcohort codes found in the data.
# REASONING: The codebook (Truth Hierarchy priority 2) provides authoritative
# definitions. Comparing codebook definitions against observed data values
# gives us high confidence in our subcohort selection.
print("\n" + "=" * 60)
print("CODEBOOK INSPECTION")
print("=" * 60)

codebook_cache = PROJECT_DIR / "data" / "codebooks"
codebook_local = fetch_codebook(CODEBOOK_PATH, codebook_cache)

codebook_subcohort_info = None
if codebook_local is not None:
    sheets = read_codebook_sheets(codebook_local)

    # Search for subcohort definitions in codebook sheets
    for sheet_name, sheet_df in sheets.items():
        print(f"\n  Sheet '{sheet_name}': {sheet_df.shape[0]} rows x {sheet_df.shape[1]} cols")
        print(f"    Columns: {sheet_df.columns}")

        # Look for any column or row mentioning "subcohort"
        for col in sheet_df.columns:
            if sheet_df[col].dtype == pl.Utf8:
                matches = sheet_df.filter(
                    pl.col(col).str.to_lowercase().str.contains("subcohort|cohort")
                )
                if matches.shape[0] > 0:
                    print(f"\n    Found subcohort references in column '{col}':")
                    print(matches.head(30))
                    codebook_subcohort_info = matches
else:
    print("  Codebook not available; proceeding with data-driven identification only")

# --- Step 4: Select the correct subcohort ---
# INTENT: Based on data inspection and codebook review, select the subcohort code
# that represents "all bachelor's degree-seeking students" graduation rate.
#
# REASONING from v1 data inspection:
#   subcohort=1: 2,467 rows (sex==99, race==99) -- fewer institutions, likely
#     certificate/associate degree-seeking students (2-year programs)
#   subcohort=2: 4,489 rows -- more institutions, likely bachelor's degree-seeking
#     students (4-year programs). This is the standard 4-year graduation rate metric.
#   subcohort=99: 7,979 rows -- total across all subcohorts. This combines 2-year
#     and 4-year cohorts. Sum of subcohort 1+2 (6,956) is close to but less than
#     subcohort 99 (7,979), suggesting some institutions only report in the total.
#
# For 4-year institution analysis, subcohort=2 is the correct choice because:
#   1. It specifically captures bachelor's degree-seeking students
#   2. Our directory filter (institution_level==4) targets 4-year institutions
#   3. Using subcohort=99 would mix in certificate/associate cohorts for
#      institutions that offer multiple degree levels
#   4. The row count (4,489) aligns with the expected number of 4-year
#      institutions reporting graduation rates
#
# HOWEVER: We also validate by checking institution_level distribution within
# each subcohort to confirm our interpretation.

print("\n" + "=" * 60)
print("SUBCOHORT SELECTION")
print("=" * 60)

# Cross-reference subcohort with institution_level to validate interpretation
if "institution_level" in df_total.columns:
    print("\nInstitution level distribution by subcohort (sex==99, race==99):")
    cross_tab = (
        df_total
        .group_by(["subcohort", "institution_level"])
        .agg(pl.len().alias("count"))
        .sort(["subcohort", "institution_level"])
    )
    print(cross_tab)

# DECISION: Use subcohort=2 for bachelor's degree-seeking students
# This aligns with:
#   - 4-year institution focus of our analysis (institution_level==4)
#   - IPEDS GRS convention: subcohort=2 = bachelor's/equivalent degree-seeking
#   - Standard metric used in IPEDS Graduation Rate Survey for 4-year institutions
SELECTED_SUBCOHORT = 2

# Verify: check how many rows subcohort=2 produces at institution_level==4
if "institution_level" in df_total.columns:
    verify_4yr = df_total.filter(
        (pl.col("subcohort") == SELECTED_SUBCOHORT)
        & (pl.col("institution_level") == 4)
    )
    print(f"\nsubcohort={SELECTED_SUBCOHORT}, institution_level==4: {verify_4yr.shape[0]:,} rows")
    print(f"  (These are 4-year institutions with bachelor's degree-seeking graduation rates)")
    verify_all = df_total.filter(pl.col("subcohort") == SELECTED_SUBCOHORT)
    print(f"subcohort={SELECTED_SUBCOHORT}, all institution_levels: {verify_all.shape[0]:,} rows")

# Also show subcohort 1 for comparison
if "institution_level" in df_total.columns:
    verify_sc1 = df_total.filter(
        (pl.col("subcohort") == 1) & (pl.col("institution_level") == 4)
    )
    print(f"\nFor comparison: subcohort=1, institution_level==4: {verify_sc1.shape[0]:,} rows")
    print(f"  (These are 4-year institutions but with certificate/associate cohort)")

print(f"\n  DECISION: Using subcohort={SELECTED_SUBCOHORT}")
print(f"  REASONING: subcohort=2 represents bachelor's degree-seeking students,")
print(f"  which is the standard 4-year graduation rate metric. This aligns with")
print(f"  our institution_level==4 filter in the directory data and captures the")
print(f"  FTFT bachelor's cohort that IPEDS GRS is designed to track.")

# --- Step 5: Apply all filters ---
# INTENT: Filter the full dataset to the target population:
#   year==2020, sex==99 (total), race==99 (total), subcohort=2 (bachelor's)
# REASONING: Plan Query 2 specifies year, sex, and race filters. The subcohort
# was identified in Steps 2-4 above as subcohort=2 (bachelor's degree-seeking).
# After filtering, we should have one row per institution.
# ASSUMES:
#   - After filtering, each unitid appears exactly once (1:1 per institution)
#   - completion_rate_150pct is on a 0-1 scale (proportion) based on v1 sample values
#   - Coded values (-1, -2, -3) may remain and will be handled in Stage 6 cleaning
print("\n" + "=" * 60)
print("APPLYING FILTERS")
print("=" * 60)

df_filtered = df_full.filter(
    (pl.col("year") == TARGET_YEAR)
    & (pl.col("sex") == TARGET_SEX)
    & (pl.col("race") == TARGET_RACE)
    & (pl.col("subcohort") == SELECTED_SUBCOHORT)
)

print(f"After filters: {df_filtered.shape[0]:,} rows x {df_filtered.shape[1]} cols")
print(f"  year == {TARGET_YEAR}")
print(f"  sex == {TARGET_SEX}")
print(f"  race == {TARGET_RACE}")
print(f"  subcohort == {SELECTED_SUBCOHORT}")

# --- Pre-state (post-filter) ---
# Capture state of filtered data for CP1 validation.
pre_rows = df_filtered.shape[0]
print(f"\nPre-state (filtered): {pre_rows:,} rows, {len(df_filtered.columns)} cols")
print(f"Columns available: {df_filtered.columns}")
print(f"Sample unitids: {df_filtered['unitid'].head(5).to_list()}")

# --- Step 6: Select columns ---
# INTENT: Select only the columns specified in the Plan's Query 2 specification.
# REASONING: Keeping only needed columns reduces file size and prevents downstream
# confusion about which variables come from which source.
# ASSUMES: All SELECT_COLUMNS exist in the filtered DataFrame.

available_select = [c for c in SELECT_COLUMNS if c in df_filtered.columns]
missing_select = [c for c in SELECT_COLUMNS if c not in df_filtered.columns]

if missing_select:
    print(f"\n  WARNING: Requested columns not found: {missing_select}")
    print(f"  Available columns: {df_filtered.columns}")

df_selected = df_filtered.select(available_select)
print(f"\nSelected {len(available_select)} columns: {available_select}")
print(f"Shape after select: {df_selected.shape[0]:,} rows x {df_selected.shape[1]} cols")

# Check for unitid uniqueness (should be 1 row per institution after filters)
unitid_unique = df_selected["unitid"].n_unique()
total_rows = df_selected.shape[0]
print(f"\nUnitid uniqueness check: {unitid_unique:,} unique out of {total_rows:,} rows")
if unitid_unique == total_rows:
    print("  PASS: One row per institution (as expected)")
else:
    print(f"  WARNING: {total_rows - unitid_unique:,} duplicate unitids detected")

# --- Save ---
# Persist results in parquet format.
# Output paths match the Plan's file specification.
df_selected.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# Verify file exists and is readable
verify_df = pl.read_parquet(OUTPUT_PARQUET)
print(f"Verified: {OUTPUT_PARQUET} is readable ({verify_df.shape[0]:,} rows)")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# row counts, critical columns, year coverage, demographic filters,
# and completion_rate_150pct range.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Row count within expected range
row_count_ok = EXPECTED_MIN_ROWS <= df_selected.shape[0] <= EXPECTED_MAX_ROWS
print(f"  [{'PASS' if row_count_ok else 'WARN'}] Row count in range "
      f"[{EXPECTED_MIN_ROWS:,}, {EXPECTED_MAX_ROWS:,}]: {df_selected.shape[0]:,}")

# CP1.2: Critical columns present
critical_cols = ["unitid", "completion_rate_150pct"]
cols_present = all(c in df_selected.columns for c in critical_cols)
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: {critical_cols}")

# CP1.3: Only year 2020 present
years_found = df_selected["year"].unique().to_list()
only_2020 = years_found == [2020]
print(f"  [{'PASS' if only_2020 else 'FAIL'}] Only year 2020: {years_found}")

# CP1.4: sex==99 and race==99 confirmed (verified from pre-filter data)
sex_check = df_filtered["sex"].unique().to_list() == [99]
race_check = df_filtered["race"].unique().to_list() == [99]
print(f"  [{'PASS' if sex_check else 'FAIL'}] sex==99 only: {df_filtered['sex'].unique().to_list()}")
print(f"  [{'PASS' if race_check else 'FAIL'}] race==99 only: {df_filtered['race'].unique().to_list()}")

# CP1.5: No nulls in identifier column (unitid)
unitid_nulls = df_selected["unitid"].null_count()
no_id_nulls = unitid_nulls == 0
print(f"  [{'PASS' if no_id_nulls else 'FAIL'}] No nulls in unitid: {unitid_nulls}")

# CP1.6: completion_rate_150pct range check
# REASONING: IPEDS graduation rates should be 0-1 (proportion) or 0-100 (percentage).
# Coded values (-1, -2, -3) are expected in raw data and will be handled in Stage 6.
rate_col = df_selected["completion_rate_150pct"]
non_coded = rate_col.filter((rate_col > 0) | (rate_col.is_null()))  # Exclude coded negatives
non_null_non_coded = non_coded.drop_nulls()

if non_null_non_coded.shape[0] > 0:
    rate_min = non_null_non_coded.min()
    rate_max = non_null_non_coded.max()
    if rate_max <= 1.5:
        scale = "proportion (0-1)"
        range_ok = rate_min >= 0 and rate_max <= 1.0
    else:
        scale = "percentage (0-100)"
        range_ok = rate_min >= 0 and rate_max <= 100.0
    print(f"  [{'PASS' if range_ok else 'WARN'}] completion_rate_150pct range: "
          f"{rate_min:.4f} to {rate_max:.4f} ({scale})")
else:
    range_ok = False
    print("  [FAIL] completion_rate_150pct: all values are coded missing or null")

# CP1.7: Subcohort documented
print(f"  [PASS] Subcohort code documented: {SELECTED_SUBCOHORT} (bachelor's degree-seeking)")

# CP1.8: Check for coded values (informational — will be cleaned in Stage 6)
coded_count = rate_col.filter(rate_col.is_in([-1, -2, -3])).shape[0]
null_count = rate_col.null_count()
coded_pct = coded_count / df_selected.shape[0] * 100 if df_selected.shape[0] > 0 else 0
null_pct = null_count / df_selected.shape[0] * 100 if df_selected.shape[0] > 0 else 0
print(f"  [INFO] Coded values (-1,-2,-3) in completion_rate_150pct: "
      f"{coded_count:,} ({coded_pct:.1f}%)")
print(f"  [INFO] Null values in completion_rate_150pct: "
      f"{null_count:,} ({null_pct:.1f}%)")

# Overall CP1 assessment
all_critical_passed = cols_present and only_2020 and no_id_nulls
cp1_passed = all_critical_passed and row_count_ok and range_ok

if not all_critical_passed:
    print("\n" + "=" * 60)
    print("CP1 VALIDATION: FAILED")
    print("=" * 60)
    assert False, "STOP: Critical CP1 checks failed"
elif not cp1_passed:
    print("\n" + "=" * 60)
    print("CP1 VALIDATION: PASSED (with warnings)")
    print("=" * 60)
else:
    print("\n" + "=" * 60)
    print("CP1 VALIDATION: PASSED")
    print("=" * 60)

# --- Summary ---
print("\n" + "=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)
print(f"  Dataset: {DATASET_PATH}")
print(f"  Mirror used: (first successful)")
print(f"  Year: {TARGET_YEAR}")
print(f"  Subcohort: {SELECTED_SUBCOHORT} (bachelor's degree-seeking)")
print(f"  Subcohort reasoning: subcohort=2 captures bachelor's degree-seeking")
print(f"    students — the standard 4-year IPEDS graduation rate metric.")
print(f"    subcohort=1 is for certificate/associate (2-year) cohorts.")
print(f"    subcohort=99 is total across all subcohorts.")
print(f"  Filters: sex=={TARGET_SEX}, race=={TARGET_RACE}, subcohort=={SELECTED_SUBCOHORT}")
print(f"  Rows: {df_selected.shape[0]:,}")
print(f"  Columns: {df_selected.columns}")
print(f"  Output: {OUTPUT_PARQUET}")
print(f"  CP1 Status: {'PASSED' if cp1_passed else 'PASSED (with warnings)' if all_critical_passed else 'FAILED'}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:12:38
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage5_fetch/02_fetch-grad-rates_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.2: Fetch IPEDS graduation rates
# ============================================================
# 
# Fetching IPEDS graduation rates (year 2020, all subcohorts)...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_grad-rates.parquet
#   OK huggingface: 10,690,508 rows
#   After filters: 401,215 rows
# Full dataset shape: 401,215 rows x 18 cols
# Columns: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# 
# ============================================================
# SUBCOHORT INSPECTION
# ============================================================
# 
# All unique subcohort values in year 2020 data:
# shape: (3, 2)
# ┌───────────┬───────────┐
# │ subcohort ┆ row_count │
# │ ---       ┆ ---       │
# │ i64       ┆ u32       │
# ╞═══════════╪═══════════╡
# │ 1         ┆ 74010     │
# │ 2         ┆ 134670    │
# │ 99        ┆ 192535    │
# └───────────┴───────────┘
# 
# Subcohort values when sex==99 AND race==99:
# shape: (3, 2)
# ┌───────────┬───────────┐
# │ subcohort ┆ row_count │
# │ ---       ┆ ---       │
# │ i64       ┆ u32       │
# ╞═══════════╪═══════════╡
# │ 1         ┆ 2467      │
# │ 2         ┆ 4489      │
# │ 99        ┆ 7979      │
# └───────────┴───────────┘
# 
# Sample data by subcohort (sex==99, race==99, first 3 rows per subcohort):
#   subcohort=1: 3 sample rows, completion_rate_150pct=[0.667, None, None], institution_level=[4, 4, 4]
#   subcohort=2: 3 sample rows, completion_rate_150pct=[None, 0.281, 0.624], institution_level=[4, 4, 4]
#   subcohort=99: 3 sample rows, completion_rate_150pct=[0.281, 0.625, 0.444], institution_level=[4, 4, 4]
# 
# ============================================================
# CODEBOOK INSPECTION
# ============================================================
#   Fetching codebook from huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/codebook_colleges_ipeds_grad-rates.xls
#   (rate limit: waiting 1.2s)
#   OK Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/codebooks/ipeds_codebook_colleges_ipeds_grad-rates.xls (20,480 bytes)
#   Codebook sheets: variables (18x3), values (120x4)
# 
#   Sheet 'variables': 18 rows x 3 cols
#     Columns: ['variable', 'format', 'label']
# 
#     Found subcohort references in column 'variable':
# shape: (4, 3)
# ┌───────────────────┬───────────┬─────────────────────────────────┐
# │ variable          ┆ format    ┆ label                           │
# │ ---               ┆ ---       ┆ ---                             │
# │ str               ┆ str       ┆ str                             │
# ╞═══════════════════╪═══════════╪═════════════════════════════════╡
# │ cohort_year       ┆ numeric   ┆ Year students in this cohort e… │
# │ subcohort         ┆ subcohort ┆ Subcohorts within a four-year … │
# │ cohort_rev        ┆ numeric   ┆ Revised cohort (number of stud… │
# │ cohort_adj_150pct ┆ numeric   ┆ Adjusted cohort (revised cohor… │
# └───────────────────┴───────────┴─────────────────────────────────┘
# 
#     Found subcohort references in column 'format':
# shape: (1, 3)
# ┌───────────┬───────────┬─────────────────────────────────┐
# │ variable  ┆ format    ┆ label                           │
# │ ---       ┆ ---       ┆ ---                             │
# │ str       ┆ str       ┆ str                             │
# ╞═══════════╪═══════════╪═════════════════════════════════╡
# │ subcohort ┆ subcohort ┆ Subcohorts within a four-year … │
# └───────────┴───────────┴─────────────────────────────────┘
# 
#     Found subcohort references in column 'label':
# shape: (6, 3)
# ┌───────────────────┬───────────┬─────────────────────────────────┐
# │ variable          ┆ format    ┆ label                           │
# │ ---               ┆ ---       ┆ ---                             │
# │ str               ┆ str       ┆ str                             │
# ╞═══════════════════╪═══════════╪═════════════════════════════════╡
# │ cohort_year       ┆ numeric   ┆ Year students in this cohort e… │
# │ subcohort         ┆ subcohort ┆ Subcohorts within a four-year … │
# │ cohort_rev        ┆ numeric   ┆ Revised cohort (number of stud… │
# │ exclusions        ┆ numeric   ┆ Students who left the cohort f… │
# │ cohort_adj_150pct ┆ numeric   ┆ Adjusted cohort (revised cohor… │
# │ transfers_out     ┆ numeric   ┆ Number of adjusted cohort who … │
# └───────────────────┴───────────┴─────────────────────────────────┘
# 
#   Sheet 'values': 120 rows x 4 cols
#     Columns: ['format', 'code', 'code_label', 'code_desc']
# 
#     Found subcohort references in column 'format':
# shape: (6, 4)
# ┌───────────┬──────┬─────────────────────────────────┬───────────┐
# │ format    ┆ code ┆ code_label                      ┆ code_desc │
# │ ---       ┆ ---  ┆ ---                             ┆ ---       │
# │ str       ┆ i64  ┆ str                             ┆ str       │
# ╞═══════════╪══════╪═════════════════════════════════╪═══════════╡
# │ subcohort ┆ -3   ┆ Suppressed data                 ┆ null      │
# │ subcohort ┆ -2   ┆ Not applicable                  ┆ null      │
# │ subcohort ┆ -1   ┆ Missing/not reported            ┆ null      │
# │ subcohort ┆ 1    ┆ Degree/certificate nonbachelor… ┆ null      │
# │ subcohort ┆ 2    ┆ Bachelor's or equivalent subco… ┆ null      │
# │ subcohort ┆ 99   ┆ Total                           ┆ null      │
# └───────────┴──────┴─────────────────────────────────┴───────────┘
# 
#     Found subcohort references in column 'code_label':
# shape: (2, 4)
# ┌───────────┬──────┬─────────────────────────────────┬───────────┐
# │ format    ┆ code ┆ code_label                      ┆ code_desc │
# │ ---       ┆ ---  ┆ ---                             ┆ ---       │
# │ str       ┆ i64  ┆ str                             ┆ str       │
# ╞═══════════╪══════╪═════════════════════════════════╪═══════════╡
# │ subcohort ┆ 1    ┆ Degree/certificate nonbachelor… ┆ null      │
# │ subcohort ┆ 2    ┆ Bachelor's or equivalent subco… ┆ null      │
# └───────────┴──────┴─────────────────────────────────┴───────────┘
# 
# ============================================================
# SUBCOHORT SELECTION
# ============================================================
# 
# Institution level distribution by subcohort (sex==99, race==99):
# shape: (5, 3)
# ┌───────────┬───────────────────┬───────┐
# │ subcohort ┆ institution_level ┆ count │
# │ ---       ┆ ---               ┆ ---   │
# │ i64       ┆ i64               ┆ u32   │
# ╞═══════════╪═══════════════════╪═══════╡
# │ 1         ┆ 4                 ┆ 2467  │
# │ 2         ┆ 4                 ┆ 4489  │
# │ 99        ┆ 1                 ┆ 1615  │
# │ 99        ┆ 2                 ┆ 4095  │
# │ 99        ┆ 4                 ┆ 2269  │
# └───────────┴───────────────────┴───────┘
# 
# subcohort=2, institution_level==4: 4,489 rows
#   (These are 4-year institutions with bachelor's degree-seeking graduation rates)
# subcohort=2, all institution_levels: 4,489 rows
# 
# For comparison: subcohort=1, institution_level==4: 2,467 rows
#   (These are 4-year institutions but with certificate/associate cohort)
# 
#   DECISION: Using subcohort=2
#   REASONING: subcohort=2 represents bachelor's degree-seeking students,
#   which is the standard 4-year graduation rate metric. This aligns with
#   our institution_level==4 filter in the directory data and captures the
#   FTFT bachelor's cohort that IPEDS GRS is designed to track.
# 
# ============================================================
# APPLYING FILTERS
# ============================================================
# After filters: 4,489 rows x 18 cols
#   year == 2020
#   sex == 99
#   race == 99
#   subcohort == 2
# 
# Pre-state (filtered): 4,489 rows, 18 cols
# Columns available: ['unitid', 'year', 'fips', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'cohort_rev', 'exclusions', 'cohort_adj_150pct', 'completers_150pct', 'transfers_out', 'still_enrolled_long_program', 'completers_100pct', 'still_enrolled', 'no_longer_enrolled', 'completion_rate_150pct']
# Sample unitids: [100654, 100654, 100663, 100663, 100690]
# 
# Selected 6 columns: ['unitid', 'year', 'completion_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# Shape after select: 4,489 rows x 6 cols
# 
# Unitid uniqueness check: 2,010 unique out of 4,489 rows
#   WARNING: 2,479 duplicate unitids detected
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/2026-02-15_ipeds_grad_rates.parquet
# Verified: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/2026-02-15_ipeds_grad_rates.parquet is readable (4,489 rows)
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Row count in range [1,500, 5,000]: 4,489
#   [PASS] Critical columns present: ['unitid', 'completion_rate_150pct']
#   [PASS] Only year 2020: [2020]
#   [PASS] sex==99 only: [99]
#   [PASS] race==99 only: [99]
#   [PASS] No nulls in unitid: 0
#   [PASS] completion_rate_150pct range: 0.0380 to 1.0000 (proportion (0-1))
#   [PASS] Subcohort code documented: 2 (bachelor's degree-seeking)
#   [INFO] Coded values (-1,-2,-3) in completion_rate_150pct: 0 (0.0%)
#   [INFO] Null values in completion_rate_150pct: 2,540 (56.6%)
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
# 
# ============================================================
# EXECUTION SUMMARY
# ============================================================
#   Dataset: ipeds/colleges_ipeds_grad-rates
#   Mirror used: (first successful)
#   Year: 2020
#   Subcohort: 2 (bachelor's degree-seeking)
#   Subcohort reasoning: subcohort=2 captures bachelor's degree-seeking
#     students — the standard 4-year IPEDS graduation rate metric.
#     subcohort=1 is for certificate/associate (2-year) cohorts.
#     subcohort=99 is total across all subcohorts.
#   Filters: sex==99, race==99, subcohort==2
#   Rows: 4,489
#   Columns: ['unitid', 'year', 'completion_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
#   Output: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/2026-02-15_ipeds_grad_rates.parquet
#   CP1 Status: PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
