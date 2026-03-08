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
  v1 (04_fetch-fsa-grants.py): FAILED - assumed flat column names
  v2 (_a.py): Used grant_type==4 (data-bearing), CP1 PASSED but rationale wrong
  v3 (_b.py): Used grant_type==1 per FSA skill docs, but 100% null data
  v4 (_c.py): Comprehensive investigation confirming:
    - grant_type==1 has 0% non-null across ALL years (2018-2021)
    - grant_type==4 has 99.9% non-null with Pell-scale values
    - grant_type==2 has 1.9% non-null (FSEOG-scale small values)
    - grant_type==3 has 0% non-null
    - grant_type==5 has 15.1% non-null (small-count values)
  v5 (_d.py, THIS VERSION):
    - Uses grant_type==4 based on data evidence (Truth Hierarchy: actual data
      takes priority over skill documentation).
    - The FSA skill docs say grant_type 4 = "Iraq and Afghanistan Service
      Grant", but the observed data shows Pell-scale values (mean ~1,269,
      max ~70,813 recipients) which is consistent with Federal Pell Grants
      and inconsistent with Iraq/Afghanistan Service Grants (a niche program
      with typically <100 recipients per institution).
    - DISCREPANCY FLAGGED: The grant_type encoding in the mirror data does
      NOT match the FSA skill documentation. The skill documentation may be
      based on a different data version or encoding scheme.
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
DATASET_PATH = "fsa/colleges_fsa_grants"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_fsa_grants.parquet"

# Grant type code for Federal Pell Grant data.
# REASONING: Per the Truth Hierarchy (actual data > codebook > skill docs):
#   - FSA skill docs say grant_type 1 = Pell, but grant_type==1 has 100% null
#     recipient data across ALL years (2018-2021).
#   - grant_type==4 contains data with Pell-scale values: mean ~1,269
#     recipients, max 70,813 recipients, 99.9% non-null coverage.
#   - These values are consistent with Federal Pell Grants (the largest
#     federal grant program) and inconsistent with Iraq/Afghanistan Service
#     Grants (a niche program).
#   - DISCREPANCY: Skill docs may reflect a different encoding scheme.
#     The actual data is authoritative per Truth Hierarchy priority 1.
PELL_GRANT_TYPE = 4

# Critical columns for downstream joins and analysis.
CRITICAL_COLUMNS = ["unitid", "pell_recipients"]

# Expected row count range for year 2020.
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 7000

# --- Mirror Configuration ---
# INTENT: Load mirror configuration for data download.
# REASONING: mirrors.yaml is the single source of truth for mirror URLs.
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Rate Limiting ---
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

    Returns:
        Filtered Polars DataFrame.
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


# =============================================================================
# MAIN EXECUTION
# =============================================================================

print("=" * 60)
print("Stage 5.4: Fetch FSA grants data (v5 - data-verified grant_type=4)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download FSA grants dataset and filter to year 2020.
# REASONING: Single-file dataset (all years 1999-2021 in one file). Download
# once, filter locally with Polars. Year 2020 aligns with IPEDS graduation
# rate cohort year used in this analysis.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year"
# and "grant_type" columns for filtering.
print("\nFetching FSA grants data...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)

# --- Pre-state ---
pre_rows = df.shape[0]
print(f"\nPre-state (raw fetch, year 2020):")
print(f"  Rows: {pre_rows:,}")
print(f"  Columns ({len(df.columns)}): {df.columns}")
print(f"  Sample unitids: {df['unitid'].drop_nulls().head(3).to_list()}")

# --- Filter to Pell Grant data ---
# INTENT: Isolate the rows containing Federal Pell Grant recipient/
# disbursement data from the multi-grant-type dataset.
#
# REASONING: The FSA grants dataset has 5 grant_type codes (1-5), each with
# identical row counts (~4,995 for year 2020). Extensive investigation in
# v4 (_c.py) determined:
#   - grant_type==1: 100% null in all value columns (across ALL years)
#   - grant_type==4: 99.9% non-null, with Pell-scale values
#     (mean ~1,269 recipients, max ~70,813)
#   - The FSA skill docs label grant_type 1 as "Pell" and 4 as "Iraq/
#     Afghanistan Service Grant", but the OBSERVED DATA contradicts this:
#     Iraq/Afghanistan Service Grants are a niche program (~<100 recipients
#     per institution) while the values in grant_type==4 are clearly Pell-
#     scale (thousands of recipients per large institution).
#
# CONCLUSION: Per Truth Hierarchy (data > codebook > skill docs), we use
# grant_type==4 which contains the actual Pell Grant data.
#
# ASSUMES: The encoding discrepancy is a documentation issue, not a data
# issue. The values themselves (recipient counts, disbursement amounts)
# are correct. This discrepancy is flagged as a Learning Signal for the
# orchestrator to track.
print(f"\n  Filtering to grant_type == {PELL_GRANT_TYPE} (Pell data per observed evidence)")
df_pell = df.filter(pl.col("grant_type") == PELL_GRANT_TYPE)
print(f"  After filter: {df_pell.shape[0]:,} rows")

# Verify the filter isolated a single grant type
pell_types_after = df_pell["grant_type"].unique().to_list()
assert pell_types_after == [PELL_GRANT_TYPE], (
    f"Filter did not isolate grant_type={PELL_GRANT_TYPE}. Found: {pell_types_after}"
)

# --- Drop null unitids ---
# INTENT: Remove rows with null unitid since they cannot be joined downstream.
# REASONING: Institutions without unitid cannot be linked to IPEDS data.
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
# types. After filtering to the Pell data rows, we rename to Pell-specific
# names for clarity and to match the Plan's column expectations.
# ASSUMES: grant_recipients_unitid = number of Pell grant recipients;
# value_grants_disbursed_unitid = total Pell dollars disbursed.
rename_map = {
    "grant_recipients_unitid": "pell_recipients",
    "value_grants_disbursed_unitid": "pell_disbursements",
}

for src_col in rename_map:
    assert src_col in df_pell.columns, f"STOP: Expected column '{src_col}' not found"

select_cols = ["unitid", "year"] + list(rename_map.keys())
df_final = df_pell.select(select_cols).rename(rename_map)

print(f"\n  Column rename: {rename_map}")
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
df_final.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
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
if not rows_ok and row_count == 0:
    cp1_passed = False

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
# REASONING: After filtering to one grant_type and year, each institution
# should appear exactly once.
unitid_unique_count = df_final["unitid"].n_unique()
unitid_total = df_final.shape[0]
unitid_unique = unitid_unique_count == unitid_total
print(f"  [{'PASS' if unitid_unique else 'WARN'}] Unitid uniqueness: {unitid_unique_count:,} unique / {unitid_total:,} total")

# CP1.6: pell_recipients data availability and distribution
# REASONING: The key validation for this version -- we need to confirm that
# grant_type==4 actually contains meaningful Pell-scale data (not tiny
# Iraq/Afghanistan Service Grant numbers).
if "pell_recipients" in df_final.columns:
    pell_null_count = df_final["pell_recipients"].null_count()
    pell_non_null = df_final.shape[0] - pell_null_count
    pell_null_pct = pell_null_count / len(df_final) * 100 if len(df_final) > 0 else 0
    pell_data_ok = pell_non_null > 0.9 * df_final.shape[0]  # > 90% non-null
    print(f"  [{'PASS' if pell_data_ok else 'WARN'}] pell_recipients non-null: {pell_non_null:,} ({100 - pell_null_pct:.1f}%)")

    if pell_non_null > 0:
        print(f"  [INFO] pell_recipients describe:")
        print(f"{df_final['pell_recipients'].describe()}")

        # Verify these are Pell-scale values (not tiny Iraq/Afghanistan numbers)
        # REASONING: Federal Pell Grants serve ~7 million students nationally.
        # The median institution should have ~100-1,000 Pell recipients.
        # Iraq/Afghanistan Service Grants serve <500 students nationwide.
        median_val = df_final["pell_recipients"].drop_nulls().median()
        max_val = df_final["pell_recipients"].drop_nulls().max()
        pell_scale_ok = median_val > 50  # Pell median should be well above 50
        print(f"  [{'PASS' if pell_scale_ok else 'WARN'}] Values are Pell-scale: median={median_val:.0f}, max={max_val:.0f}")

        # Check for coded values (-1, -2, -3) that will be handled in Stage 6
        for code in [-1, -2, -3]:
            try:
                coded_count = (df_final["pell_recipients"] == code).sum()
                if coded_count > 0:
                    print(f"  [INFO] pell_recipients coded value {code}: {coded_count:,} rows (Stage 6)")
            except Exception:
                pass

    if pell_non_null == 0:
        print("  CRITICAL: pell_recipients is 100% null")
        cp1_passed = False

# CP1.7: pell_disbursements check
if "pell_disbursements" in df_final.columns:
    pell_disb_non_null = df_final.shape[0] - df_final["pell_disbursements"].null_count()
    print(f"  [INFO] pell_disbursements: {pell_disb_non_null:,} non-null")
    if pell_disb_non_null > 0:
        print(f"  [INFO] pell_disbursements describe:")
        print(f"{df_final['pell_disbursements'].describe()}")

# CP1.8: pell_recipients >= 0 for valid rows (non-coded values)
# REASONING: Recipient counts should be non-negative. Coded missing values
# (-1, -2, -3) are expected and handled in Stage 6. Any other negatives
# would indicate a data issue.
valid_pell = df_final.filter(~pl.col("pell_recipients").is_in([-1, -2, -3]))
neg_pell = valid_pell.filter(pl.col("pell_recipients") < 0).shape[0]
neg_ok = neg_pell == 0
print(f"  [{'PASS' if neg_ok else 'WARN'}] No unexpected negative pell_recipients: {neg_pell}")

# --- Final CP1 Status ---
assert cp1_passed, "STOP: CP1 validation failed -- see details above"

# --- Encoding Discrepancy Notice ---
# INTENT: Document the grant_type encoding discrepancy for audit trail.
print("\n" + "=" * 60)
print("ENCODING DISCREPANCY NOTICE")
print("=" * 60)
print("  FSA skill docs say grant_type 1 = Pell, 4 = Iraq/Afghanistan.")
print("  OBSERVED: grant_type 1 has 100% null data across all years.")
print("  OBSERVED: grant_type 4 has Pell-scale data (median ~362 recipients).")
print("  DECISION: Using grant_type 4 per Truth Hierarchy (data > docs).")
print("  ACTION: Flag for LEARNINGS.md -- skill docs need updating.")

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:16:55
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_d.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA grants data (v5 - data-verified grant_type=4)
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
#   Sample unitids: [100654, 100654, 100654]
# 
#   Filtering to grant_type == 4 (Pell data per observed evidence)
#   After filter: 4,995 rows
#   Dropping 1 rows with null unitid
# 
#   Column rename: {'grant_recipients_unitid': 'pell_recipients', 'value_grants_disbursed_unitid': 'pell_disbursements'}
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
#   [PASS] pell_recipients non-null: 4,988 (99.9%)
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
#   [PASS] Values are Pell-scale: median=362, max=70813
#   [INFO] pell_disbursements: 4,988 non-null
#   [INFO] pell_disbursements describe:
# shape: (9, 2)
# ┌────────────┬────────────┐
# │ statistic  ┆ value      │
# │ ---        ┆ ---        │
# │ str        ┆ f64        │
# ╞════════════╪════════════╡
# │ count      ┆ 4988.0     │
# │ null_count ┆ 6.0        │
# │ mean       ┆ 5.2844e6   │
# │ std        ┆ 1.2168e7   │
# │ min        ┆ 0.0        │
# │ 25%        ┆ 334101.0   │
# │ 50%        ┆ 1.5640e6   │
# │ 75%        ┆ 4946663.5  │
# │ max        ┆ 2.247628e8 │
# └────────────┴────────────┘
#   [PASS] No unexpected negative pell_recipients: 0
# 
# ============================================================
# ENCODING DISCREPANCY NOTICE
# ============================================================
#   FSA skill docs say grant_type 1 = Pell, 4 = Iraq/Afghanistan.
#   OBSERVED: grant_type 1 has 100% null data across all years.
#   OBSERVED: grant_type 4 has Pell-scale data (median ~362 recipients).
#   DECISION: Using grant_type 4 per Truth Hierarchy (data > docs).
#   ACTION: Flag for LEARNINGS.md -- skill docs need updating.
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
