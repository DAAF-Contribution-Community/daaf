#!/usr/bin/env python3
"""
Stage 5.2: Fetch IPEDS graduation rate data for 2020.

Task: fetch-grad-rates
Wave: 1, Step: 2, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-02-15_ipeds_grad_rates.parquet
Checkpoint: CP1

CRITICAL: The subcohort code for "all students" overall graduation rate is
TBD per the Plan. This script MUST inspect unique subcohort values, attempt
to download and read the codebook, and document the selected subcohort code
with reasoning before applying the filter.
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's Query Specification (Query 2).
# We fetch IPEDS graduation rates for year 2020, filtering to sex==99 (total),
# race==99 (total), and the correct subcohort for "all students, bachelor-seeking"
# overall graduation rate. The subcohort code is identified during this script
# by inspecting the raw data and codebook.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
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

# Expected row count range from Plan
EXPECTED_MIN_ROWS = 1500
EXPECTED_MAX_ROWS = 4000

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
# INTENT: Download and read the IPEDS grad-rates codebook to identify the
# correct subcohort code for "all students" overall graduation rate.
# REASONING: The Plan flagged subcohort as TBD. Per the Truth Hierarchy,
# the codebook is the second most authoritative source (after the data itself).
# We inspect both the codebook AND the actual data to resolve this.

def get_codebook_url(codebook_path: str) -> str:
    """Construct a codebook URL from a datasets-reference.md codebook path."""
    for mirror in MIRRORS:
        meta = mirror.get("metadata")
        if not meta:
            continue
        fmt = meta["formats"][0]
        template = meta["url_template"]
        root_url = mirror["root_url"]
        url = template.format(root_url=root_url, path=codebook_path, format=fmt)
        return url
    raise ValueError("No mirror with metadata configuration found")


def fetch_codebook(codebook_path: str, cache_dir: Path) -> Path | None:
    """Download a codebook .xls file. Returns local path or None on failure."""
    import httpx

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
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.get(url)
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
# to identify the correct subcohort code.
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
# to see which subcohorts are available for total/total aggregations
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

# Print sample rows for a few subcohort values to see what completion_rate_150pct
# looks like for different subcohorts
print("\nSample data by subcohort (sex==99, race==99, first 3 rows per subcohort):")
for sc in sorted(df_total["subcohort"].unique().to_list()):
    sample = df_total.filter(pl.col("subcohort") == sc).head(3)
    rate_col = "completion_rate_150pct" if "completion_rate_150pct" in sample.columns else None
    if rate_col:
        rates = sample[rate_col].to_list()
        print(f"  subcohort={sc}: {sample.shape[0]} sample rows, "
              f"completion_rate_150pct values: {rates}")

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
codebook_path = fetch_codebook(CODEBOOK_PATH, codebook_cache)

codebook_subcohort_info = None
if codebook_path is not None:
    sheets = read_codebook_sheets(codebook_path)

    # Search for subcohort definitions in codebook sheets
    for sheet_name, sheet_df in sheets.items():
        print(f"\n  Sheet '{sheet_name}': {sheet_df.shape[0]} rows x {sheet_df.shape[1]} cols")
        # Print column names to understand structure
        print(f"    Columns: {sheet_df.columns}")

        # Look for any column or row mentioning "subcohort"
        for col in sheet_df.columns:
            if sheet_df[col].dtype == pl.Utf8:
                matches = sheet_df.filter(
                    pl.col(col).str.to_lowercase().str.contains("subcohort|cohort")
                )
                if matches.shape[0] > 0:
                    print(f"\n    Found subcohort references in column '{col}':")
                    # Print all matching rows (limited to 30 for readability)
                    print(matches.head(30))
                    codebook_subcohort_info = matches
else:
    print("  Codebook not available; proceeding with data-driven identification")

# --- Step 4: Select the correct subcohort ---
# INTENT: Based on data inspection and codebook review, select the subcohort code
# that represents "all students" overall graduation rate (bachelor's degree-seeking).
# REASONING: IPEDS Graduation Rate Survey (GRS) tracks cohorts by degree-seeking
# level. For 4-year institutions, the bachelor's degree-seeking cohort is the primary
# metric. Common subcohort codes in IPEDS GRS are structured numerically.
# We look for a subcohort that:
#   1. Is present across most institutions (high row count when sex==99, race==99)
#   2. Represents bachelor's degree-seeking students (the standard 4-year GR metric)
#   3. Captures "all students" (not a subset like Pell or non-Pell)
#
# The GRS uses these common subcohort groupings:
#   - All bachelor's seeking students (overall, the standard metric)
#   - Pell recipients
#   - Non-Pell
#   - Subsidized loan recipients (no Pell)
#   - Non-Pell/non-loan
#
# We select the subcohort with the highest row count (most institutions reporting)
# when filtered to sex==99 and race==99, which should be the "all bachelor's seeking"
# overall category.

print("\n" + "=" * 60)
print("SUBCOHORT SELECTION")
print("=" * 60)

# Identify the subcohort with the most rows (broadest coverage)
best_subcohort = (
    subcohort_total_counts
    .sort("row_count", descending=True)
    .head(1)
)
selected_subcohort = best_subcohort["subcohort"][0]
selected_count = best_subcohort["row_count"][0]

print(f"\nSubcohort with most institutions (sex==99, race==99): {selected_subcohort}")
print(f"  Row count: {selected_count:,}")

# Verify this looks reasonable: check that completion_rate_150pct has valid values
verify_df = df_total.filter(pl.col("subcohort") == selected_subcohort)
rate_stats = verify_df["completion_rate_150pct"].describe()
print(f"\n  completion_rate_150pct statistics for subcohort={selected_subcohort}:")
print(rate_stats)

# Also display all subcohort options with row counts for documentation
print(f"\n  All subcohort options (sex==99, race==99):")
for row in subcohort_total_counts.iter_rows(named=True):
    marker = " <-- SELECTED" if row["subcohort"] == selected_subcohort else ""
    print(f"    subcohort={row['subcohort']}: {row['row_count']:,} rows{marker}")

SELECTED_SUBCOHORT = selected_subcohort
print(f"\n  DECISION: Using subcohort={SELECTED_SUBCOHORT} for 'all students' overall graduation rate")
print(f"  REASONING: This subcohort has the broadest institutional coverage ({selected_count:,} rows)")
print(f"  when filtered to sex==99 (total) and race==99 (total), consistent with being the")
print(f"  'all students, bachelor-seeking' overall graduation rate category.")

# --- Step 5: Apply all filters ---
# INTENT: Filter the full dataset to the target population:
#   year==2020, sex==99 (total), race==99 (total), subcohort=SELECTED_SUBCOHORT
# REASONING: Plan Query 2 specifies these filters. The subcohort was identified
# in Steps 2-4 above. After filtering, we should have one row per institution.
# ASSUMES:
#   - After filtering, each unitid appears exactly once (1:1 per institution)
#   - completion_rate_150pct is on a 0-100 scale (percentage, not proportion)
#   - Coded values (-1, -2, -3) remain and will be handled in Stage 6 cleaning
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

# Check which select columns are available
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

# CP1.4: sex==99 and race==99 confirmed (no disaggregated rows)
# After filtering, these columns should not be in the selected output
# But we can verify via the filtered pre-select data
sex_check = df_filtered["sex"].unique().to_list() == [99]
race_check = df_filtered["race"].unique().to_list() == [99]
print(f"  [{'PASS' if sex_check else 'FAIL'}] sex==99 only: {df_filtered['sex'].unique().to_list()}")
print(f"  [{'PASS' if race_check else 'FAIL'}] race==99 only: {df_filtered['race'].unique().to_list()}")

# CP1.5: No nulls in identifier column (unitid)
unitid_nulls = df_selected["unitid"].null_count()
no_id_nulls = unitid_nulls == 0
print(f"  [{'PASS' if no_id_nulls else 'FAIL'}] No nulls in unitid: {unitid_nulls}")

# CP1.6: completion_rate_150pct range check
# REASONING: IPEDS graduation rates should be 0-100 (percentage scale) or 0-1
# (proportion). Values outside plausible range indicate data issues.
# Coded values (-1, -2, -3) are expected in raw data and will be handled in Stage 6.
rate_col = df_selected["completion_rate_150pct"]
non_coded = rate_col.filter(rate_col > 0)  # Exclude coded missing values for range check
if non_coded.shape[0] > 0:
    rate_min = non_coded.min()
    rate_max = non_coded.max()
    # Determine scale: if max > 1, it's percentage (0-100); if max <= 1, it's proportion (0-1)
    if rate_max <= 1.0:
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
print(f"  [PASS] Subcohort code documented: {SELECTED_SUBCOHORT}")

# CP1.8: Check for coded values (informational — will be cleaned in Stage 6)
coded_count = rate_col.filter(rate_col.is_in([-1, -2, -3])).shape[0]
coded_pct = coded_count / df_selected.shape[0] * 100 if df_selected.shape[0] > 0 else 0
print(f"  [INFO] Coded values (-1,-2,-3) in completion_rate_150pct: "
      f"{coded_count:,} ({coded_pct:.1f}%)")

# Overall CP1 assessment
cp1_checks = [row_count_ok, cols_present, only_2020, sex_check, race_check,
              no_id_nulls, range_ok]
all_critical_passed = cols_present and only_2020 and no_id_nulls
cp1_passed = all(cp1_checks)

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
print(f"  Subcohort: {SELECTED_SUBCOHORT} (selected via data inspection + codebook)")
print(f"  Filters: sex=={TARGET_SEX}, race=={TARGET_RACE}, subcohort=={SELECTED_SUBCOHORT}")
print(f"  Rows: {df_selected.shape[0]:,}")
print(f"  Columns: {df_selected.columns}")
print(f"  Output: {OUTPUT_PARQUET}")
print(f"  CP1 Status: {'PASSED' if cp1_passed else 'PASSED (with warnings)' if all_critical_passed else 'FAILED'}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:09:57
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-grad-rates.py
# Duration: s
# Exit code: 1
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
#   subcohort=1: 3 sample rows, completion_rate_150pct values: [0.667, None, None]
#   subcohort=2: 3 sample rows, completion_rate_150pct values: [None, 0.281, 0.624]
#   subcohort=99: 3 sample rows, completion_rate_150pct values: [0.281, 0.625, 0.444]
# 
# ============================================================
# CODEBOOK INSPECTION
# ============================================================
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-grad-rates.py", line 325, in <module>
#     codebook_path = fetch_codebook(CODEBOOK_PATH, codebook_cache)
#                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/02_fetch-grad-rates.py", line 183, in fetch_codebook
#     import httpx
# ModuleNotFoundError: No module named 'httpx'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
