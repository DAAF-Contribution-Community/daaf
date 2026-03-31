#!/usr/bin/env python3
"""
Stage 5.9: Fetch IPEDS SFA Grants and Net Price data (Pell Grant proxy).

Task: fetch-sfa-grants
Wave: 2.4 (additional fetch to resolve Pell data gap), Step: 9, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_sfa_grants.parquet
Checkpoint: CP1

Background: The original Plan used FSA Grants for Pell recipient counts, but
grant_recipients_unitid is 100% NULL for 2020-2021. This dataset
(sfa_grants_and_net_price) is the alternative -- it covers 2008-2021 and has
number_receiving_grants by type_of_aid.

Discovery: This is partially a discovery task. We need to understand the data
structure, especially type_of_aid codes, to identify the Pell Grant proxy.
"""

import time

import polars as pl
from pathlib import Path

# --- Config ---
# INTENT: Set up paths and parameters for fetching SFA Grants and Net Price data.
# REASONING: Single-file dataset covering 2008-2021. We filter to year=2020 locally.
# ASSUMES: Mirror URLs in mirrors.yaml are current and the dataset path matches
#   datasets-reference.md entry: ipeds/colleges_ipeds_sfa_grants_and_net_price
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

YEARS = [2020]  # Per task specification: filter to year 2020
DATASET_PATH = "ipeds/colleges_ipeds_sfa_grants_and_net_price"
OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_sfa_grants.parquet"

# Education Data Portal coded missing values
# REASONING: Portal uses integer sentinel values: -1 (missing/not reported),
# -2 (not applicable), -3 (suppressed). These must be detected and reported
# in CP1 but NOT replaced here (that is Stage 6's job).
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed"}

# --- Mirror Configuration ---
# INTENT: Download SFA Grants and Net Price from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
#   Format-specific read strategy driven by each mirror's read_strategy field.
#   All mirrors use the same canonical path from datasets-reference.md.
# ASSUMES: Mirror URLs are current and accessible; dataset contains "year" column.
# REFERENCE: mirrors.yaml for mirror config, datasets-reference.md for paths.
import yaml

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
            if strategy in ("eager_parquet", "parquet"):
                df = pl.read_parquet(url)
            elif strategy in ("lazy_csv", "csv"):
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
                print(f"  [OK] {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  [OK] {name}: {df.shape[0]:,} rows")

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
            print(f"  [FAIL] {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


# --- Fetch Data ---
print("=" * 60)
print("Stage 5.9: Fetch IPEDS SFA Grants and Net Price")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# INTENT: Download the SFA Grants and Net Price dataset and filter to year 2020.
# REASONING: Single-file dataset (all years in one file, 2008-2021). Download once,
#   filter locally with Polars. We need year 2020 to match the other IPEDS data
#   already fetched for this analysis.
# ASSUMES: Dataset has a "year" column with integer year values.
print("\nFetching IPEDS SFA Grants and Net Price...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"\nFiltered shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Discovery: Full Column Inventory ---
# INTENT: Log ALL column names and dtypes for discovery.
# REASONING: This is partially a discovery task -- we need to understand the data
#   structure to identify the Pell Grant proxy variable.
print("\n" + "=" * 60)
print("DATA DISCOVERY")
print("=" * 60)

print(f"\nAll columns ({df.shape[1]}):")
for i, (col, dtype) in enumerate(zip(df.columns, df.dtypes)):
    print(f"  {i+1:2d}. {col:<45s} {str(dtype)}")

# INTENT: Check for any column containing "pell" in the name.
# REASONING: If there is a dedicated pell column, it would be the most direct proxy.
pell_cols = [c for c in df.columns if "pell" in c.lower()]
print(f"\nColumns containing 'pell': {pell_cols if pell_cols else 'NONE FOUND'}")

# --- Discovery: type_of_aid Analysis ---
# INTENT: Enumerate all unique type_of_aid values with counts and summary statistics.
# REASONING: The type_of_aid column determines which rows represent Pell Grant recipients.
#   Understanding all codes is essential before selecting the Pell proxy.
# ASSUMES: Column "type_of_aid" exists in the dataset.
print("\n" + "-" * 60)
print("type_of_aid Discovery")
print("-" * 60)

if "type_of_aid" in df.columns:
    # Overall value counts
    type_counts = (
        df.group_by("type_of_aid")
        .agg([
            pl.len().alias("count"),
            pl.col("number_receiving_grants").drop_nulls().len().alias("nonnull_recipients"),
            pl.col("number_receiving_grants").mean().alias("mean_recipients"),
            pl.col("number_receiving_grants").median().alias("median_recipients"),
        ])
        .sort("type_of_aid")
    )

    print(f"\ntype_of_aid summary (year=2020):")
    print(f"{'Code':<8} {'Count':>8} {'NonNull':>10} {'NonNull%':>10} {'Mean':>12} {'Median':>10}")
    print("-" * 60)
    for row in type_counts.iter_rows(named=True):
        code = row["type_of_aid"]
        count = row["count"]
        nonnull = row["nonnull_recipients"]
        nonnull_pct = (nonnull / count * 100) if count > 0 else 0
        mean_val = row["mean_recipients"]
        median_val = row["median_recipients"]
        mean_str = f"{mean_val:,.1f}" if mean_val is not None else "N/A"
        median_str = f"{median_val:,.1f}" if median_val is not None else "N/A"
        print(f"{code:<8} {count:>8,} {nonnull:>10,} {nonnull_pct:>9.1f}% {mean_str:>12} {median_str:>10}")

    # INTENT: Print sample rows for each type_of_aid value to understand data patterns.
    # REASONING: Seeing actual rows helps interpret what each code represents, especially
    #   when official codebook documentation may be unavailable or stale.
    print("\n" + "-" * 60)
    print("Sample rows per type_of_aid")
    print("-" * 60)
    unique_types = sorted(df["type_of_aid"].unique().to_list())
    for toa in unique_types:
        subset = df.filter(pl.col("type_of_aid") == toa)
        sample_n = min(5, subset.shape[0])
        sample = subset.head(sample_n)
        print(f"\n--- type_of_aid = {toa} (showing {sample_n} of {subset.shape[0]:,}) ---")
        print(sample)
else:
    print("WARNING: 'type_of_aid' column NOT FOUND in dataset")

# --- Discovery: Additional numeric columns ---
# INTENT: Identify all numeric columns and their null rates for completeness.
# REASONING: There may be other useful columns beyond number_receiving_grants.
print("\n" + "-" * 60)
print("Numeric Column Summary")
print("-" * 60)
numeric_cols = [c for c, d in zip(df.columns, df.dtypes)
                if d in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64)]
for col in numeric_cols:
    total = df.shape[0]
    null_ct = df[col].null_count()
    null_pct = null_ct / total * 100 if total > 0 else 0
    # Check for coded missing values
    coded_counts = {}
    for code, meaning in CODED_MISSING.items():
        ct = (df[col] == code).sum()
        if ct > 0:
            coded_counts[code] = ct
    coded_str = ", ".join(f"{k}:{v}" for k, v in coded_counts.items()) if coded_counts else "none"
    print(f"  {col:<45s} null={null_pct:5.1f}%  coded_missing=[{coded_str}]")

# --- Save ---
# INTENT: Persist the year-2020 filtered data for downstream cleaning (Stage 6).
# REASONING: Save the full dataset (all type_of_aid values) so that the cleaning
#   script can select the appropriate Pell proxy code after discovery is reviewed.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")
print(f"File size: {OUTPUT_PARQUET.stat().st_size / 1024:.1f} KB")

# --- CP1 Validation: Post-Fetch ---
# INTENT: Verify fetched data structure and completeness before proceeding to cleaning.
# ASSUMES: df is the fetched and year-filtered DataFrame.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Non-empty dataset
if df.shape[0] == 0:
    print("[FAIL] Empty dataset returned from mirror")
    cp1_passed = False
else:
    print(f"[PASS] {df.shape[0]:,} rows loaded")

# CP1.2: Row count reasonableness
# REASONING: Expecting ~10,000-50,000 rows (multiple type_of_aid rows per institution).
expected_min = 10000
expected_max = 100000
rows_in_range = expected_min <= df.shape[0] <= expected_max
if rows_in_range:
    print(f"[PASS] Row count {df.shape[0]:,} within expected range ({expected_min:,}-{expected_max:,})")
else:
    print(f"[WARN] Row count {df.shape[0]:,} outside expected range ({expected_min:,}-{expected_max:,})")

# CP1.3: Critical columns present
critical_cols = ["unitid", "year", "type_of_aid", "number_receiving_grants"]
missing_cols = [c for c in critical_cols if c not in df.columns]
if missing_cols:
    print(f"[FAIL] Missing critical columns: {missing_cols}")
    cp1_passed = False
else:
    print(f"[PASS] All critical columns present: {critical_cols}")

# CP1.4: Year coverage
years_found = sorted(df["year"].unique().to_list())
all_years = all(y in years_found for y in YEARS)
if all_years:
    print(f"[PASS] Year coverage: {years_found}")
else:
    print(f"[FAIL] Missing expected years. Found: {years_found}, expected: {YEARS}")
    cp1_passed = False

# CP1.5: Identifier nulls
unitid_nulls = df["unitid"].null_count()
year_nulls = df["year"].null_count()
no_id_nulls = unitid_nulls == 0 and year_nulls == 0
if no_id_nulls:
    print(f"[PASS] No nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")
else:
    print(f"[FAIL] Nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")
    cp1_passed = False

# CP1.6: Missingness in key columns
for col in critical_cols:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        if null_pct > 90:
            print(f"[FAIL] {col}: {null_pct:.1f}% null (>90% threshold)")
            cp1_passed = False
        elif null_pct > 50:
            print(f"[WARN] {col}: {null_pct:.1f}% null (high)")
        elif null_pct > 5:
            print(f"[WARN] {col}: {null_pct:.1f}% null")
        else:
            print(f"[PASS] {col}: {null_pct:.1f}% null")

# CP1.7: Flag year check (COVID-19 for education)
FLAG_YEARS = [2020, 2021]
if any(y in FLAG_YEARS for y in YEARS):
    print(f"[WARN] FLAG-YEARS: Data from flagged years {[y for y in YEARS if y in FLAG_YEARS]}. "
          "Document comparability concerns in limitations.")

# CP1.8: Coded missing values presence
print("\nCoded missing values detected:")
coded_found_any = False
for col in numeric_cols:
    for code, meaning in CODED_MISSING.items():
        ct = (df[col] == code).sum()
        if ct > 0:
            print(f"  {col}: {code} ({meaning}): {ct:,}")
            coded_found_any = True
if not coded_found_any:
    print("  None detected")

assert cp1_passed, "CP1 FAILED - see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)



# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:18:31
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage5_fetch/09_fetch-sfa-grants.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.9: Fetch IPEDS SFA Grants and Net Price
# ============================================================
# 
# Fetching IPEDS SFA Grants and Net Price...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_sfa_grants_and_net_price.parquet
#   [OK] huggingface: 597,920 rows
#   After filters: 37,292 rows
# 
# Filtered shape: 37,292 rows x 15 cols
# 
# ============================================================
# DATA DISCOVERY
# ============================================================
# 
# All columns (15):
#    1. unitid                                        Int64
#    2. year                                          Int64
#    3. fips                                          Int64
#    4. ftpt                                          Int64
#    5. level_of_study                                Int64
#    6. degree_seeking                                Int64
#    7. class_level                                   Int64
#    8. tuition_type                                  Int64
#    9. type_of_aid                                   Int64
#   10. income_level                                  Int64
#   11. average_grant                                 Int64
#   12. number_of_students                            Int64
#   13. total_grant                                   Int64
#   14. net_price                                     Int64
#   15. number_receiving_grants                       Int64
# 
# Columns containing 'pell': NONE FOUND
# 
# ------------------------------------------------------------
# type_of_aid Discovery
# ------------------------------------------------------------
# 
# type_of_aid summary (year=2020):
# Code        Count    NonNull   NonNull%         Mean     Median
# ------------------------------------------------------------
# 3           5,372          0       0.0%          N/A        N/A
# 9          31,920     31,920     100.0%         74.2       14.0
# 
# ------------------------------------------------------------
# Sample rows per type_of_aid
# ------------------------------------------------------------
# 
# --- type_of_aid = 3 (showing 5 of 5,372) ---
# shape: (5, 15)
# ┌────────┬──────┬──────┬──────┬───┬───────────────────┬─────────────┬───────────┬──────────────────┐
# │ unitid ┆ year ┆ fips ┆ ftpt ┆ … ┆ number_of_student ┆ total_grant ┆ net_price ┆ number_receiving │
# │ ---    ┆ ---  ┆ ---  ┆ ---  ┆   ┆ s                 ┆ ---         ┆ ---       ┆ _grants          │
# │ i64    ┆ i64  ┆ i64  ┆ i64  ┆   ┆ ---               ┆ i64         ┆ i64       ┆ ---              │
# │        ┆      ┆      ┆      ┆   ┆ i64               ┆             ┆           ┆ i64              │
# ╞════════╪══════╪══════╪══════╪═══╪═══════════════════╪═════════════╪═══════════╪══════════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 693               ┆ 6240985     ┆ 12921     ┆ null             │
# │ 100663 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 1585              ┆ 15046376    ┆ 16990     ┆ null             │
# │ 100706 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 902               ┆ 6724413     ┆ 17302     ┆ null             │
# │ 100724 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 430               ┆ 3895022     ┆ 12875     ┆ null             │
# │ 100751 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 2403              ┆ 23517427    ┆ 21263     ┆ null             │
# └────────┴──────┴──────┴──────┴───┴───────────────────┴─────────────┴───────────┴──────────────────┘
# 
# --- type_of_aid = 9 (showing 5 of 31,920) ---
# shape: (5, 15)
# ┌────────┬──────┬──────┬──────┬───┬───────────────────┬─────────────┬───────────┬──────────────────┐
# │ unitid ┆ year ┆ fips ┆ ftpt ┆ … ┆ number_of_student ┆ total_grant ┆ net_price ┆ number_receiving │
# │ ---    ┆ ---  ┆ ---  ┆ ---  ┆   ┆ s                 ┆ ---         ┆ ---       ┆ _grants          │
# │ i64    ┆ i64  ┆ i64  ┆ i64  ┆   ┆ ---               ┆ i64         ┆ i64       ┆ ---              │
# │        ┆      ┆      ┆      ┆   ┆ i64               ┆             ┆           ┆ i64              │
# ╞════════╪══════╪══════╪══════╪═══╪═══════════════════╪═════════════╪═══════════╪══════════════════╡
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 657               ┆ 5825299     ┆ null      ┆ 642              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 76                ┆ 487604      ┆ 15508     ┆ 73               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 381               ┆ 3713735     ┆ 12177     ┆ 380              │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 19                ┆ 58270       ┆ 18857     ┆ 14               │
# │ 100654 ┆ 2020 ┆ 1    ┆ 1    ┆ … ┆ 141               ┆ 1357002     ┆ 12300     ┆ 141              │
# └────────┴──────┴──────┴──────┴───┴───────────────────┴─────────────┴───────────┴──────────────────┘
# 
# ------------------------------------------------------------
# Numeric Column Summary
# ------------------------------------------------------------
#   unitid                                        null=  0.0%  coded_missing=[none]
#   year                                          null=  0.0%  coded_missing=[none]
#   fips                                          null=  0.0%  coded_missing=[none]
#   ftpt                                          null=  0.0%  coded_missing=[none]
#   level_of_study                                null=  0.0%  coded_missing=[none]
#   degree_seeking                                null=  0.0%  coded_missing=[none]
#   class_level                                   null=  0.0%  coded_missing=[none]
#   tuition_type                                  null=  0.0%  coded_missing=[none]
#   type_of_aid                                   null=  0.0%  coded_missing=[none]
#   income_level                                  null=  0.0%  coded_missing=[none]
#   average_grant                                 null= 15.4%  coded_missing=[none]
#   number_of_students                            null=  0.0%  coded_missing=[none]
#   total_grant                                   null=  0.0%  coded_missing=[none]
#   net_price                                     null= 29.7%  coded_missing=[none]
#   number_receiving_grants                       null= 14.4%  coded_missing=[none]
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/raw/2026-03-29_ipeds_sfa_grants.parquet
# File size: 484.7 KB
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
# [PASS] 37,292 rows loaded
# [PASS] Row count 37,292 within expected range (10,000-100,000)
# [PASS] All critical columns present: ['unitid', 'year', 'type_of_aid', 'number_receiving_grants']
# [PASS] Year coverage: [2020]
# [PASS] No nulls in ID columns: unitid=0, year=0
# [PASS] unitid: 0.0% null
# [PASS] year: 0.0% null
# [PASS] type_of_aid: 0.0% null
# [WARN] number_receiving_grants: 14.4% null
# [WARN] FLAG-YEARS: Data from flagged years [2020]. Document comparability concerns in limitations.
# 
# Coded missing values detected:
#   None detected
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
