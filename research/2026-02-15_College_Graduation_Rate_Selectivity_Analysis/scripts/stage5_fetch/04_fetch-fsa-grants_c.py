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
    - Used grant_type == 4 (Iraq/Afghanistan Service Grant) -- wrong grant type
      but coincidentally had non-null data. All 5 grant types had equal row
      counts (4,995). The "most common" heuristic was arbitrary and wrong.
    - CP1 PASSED but with wrong grant type data.
  v3 (_b.py):
    - Correctly used grant_type == 1 (Federal Pell Grant) per FSA skill docs.
    - CP1 PASSED but pell_recipients was 100% null (4,994/4,994 rows).
    - The grant_recipients_unitid column is null for grant_type==1 (Pell) but
      populated for other grant types. This suggests the FSA grants dataset
      may store Pell data at the OPEID level, not the unitid level.
  v4 (_c.py, THIS VERSION):
    - Investigates which columns have actual data for grant_type==1 (Pell).
    - Per Truth Hierarchy: trust actual data (priority 1) over skill docs.
    - Uses grant_recipients_opeid if unitid-level is null, since OPEID is
      often a 1:1 mapping with unitid for most institutions.
    - If neither column has data, explores whether the dataset structure
      requires a different approach entirely.
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

# Grant type code for Federal Pell Grant per FSA skill docs.
PELL_GRANT_TYPE = 1

# Critical columns for downstream analysis.
CRITICAL_COLUMNS = ["unitid", "pell_recipients"]

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
    """Try each mirror in order. Return DataFrame on first success."""
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
print("Stage 5.4: Fetch FSA grants data (v4 - data-driven column selection)")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download FSA grants dataset and filter to year 2020.
# REASONING: Single-file dataset. Year 2020 aligns with IPEDS cohort.
# ASSUMES: Mirror URLs are current. Dataset has "year" column.
print("\nFetching FSA grants data...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=[YEAR],
)

# --- Pre-state ---
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state (raw fetch, year 2020):")
print(f"  Rows: {pre_rows:,}")
print(f"  Columns ({len(pre_cols)}): {pre_cols}")

# --- Data Structure Investigation ---
# INTENT: Understand which columns have actual data for each grant_type.
# REASONING: v3 showed grant_type==1 (Pell) has 100% null in
# grant_recipients_unitid. We need to determine the correct column to use.
# Per Truth Hierarchy, we trust the observed data over documentation.
print("\n--- DATA STRUCTURE INVESTIGATION ---")
print("Non-null counts by grant_type for recipient/disbursement columns:")
value_cols = [c for c in df.columns if "recipient" in c or "disbursed" in c or "value" in c]
print(f"  Value columns: {value_cols}")

for gt in sorted(df["grant_type"].drop_nulls().unique().to_list()):
    gt_df = df.filter(pl.col("grant_type") == gt)
    gt_total = gt_df.shape[0]
    print(f"\n  grant_type == {gt} ({gt_total} rows):")
    for col in value_cols:
        non_null = gt_total - gt_df[col].null_count()
        print(f"    {col}: {non_null:,} non-null / {gt_total:,} ({non_null/gt_total*100:.1f}%)")

# --- Filter to Pell Grants ---
# INTENT: Isolate Federal Pell Grant rows (grant_type == 1).
# REASONING: Per FSA skill docs, grant_type 1 = Federal Pell Grant.
print(f"\n--- FILTERING TO PELL GRANTS (grant_type == {PELL_GRANT_TYPE}) ---")
df_pell = df.filter(pl.col("grant_type") == PELL_GRANT_TYPE)
print(f"  After Pell filter: {df_pell.shape[0]:,} rows")

# Check which recipient/disbursement columns have data for Pell
# INTENT: Determine the best column to use for Pell recipient counts.
# REASONING: The unitid-level column may be null while the opeid-level column
# has data. OPEID (Office of Postsecondary Education ID) is an alternate
# institutional identifier; for most institutions unitid and opeid are 1:1.
print("\n  Column availability for Pell rows:")
unitid_recipients_non_null = df_pell.shape[0] - df_pell["grant_recipients_unitid"].null_count()
opeid_recipients_non_null = df_pell.shape[0] - df_pell["grant_recipients_opeid"].null_count()
unitid_disbursed_non_null = df_pell.shape[0] - df_pell["value_grants_disbursed_unitid"].null_count()
opeid_disbursed_non_null = df_pell.shape[0] - df_pell["value_grants_disbursed_opeid"].null_count()

print(f"  grant_recipients_unitid: {unitid_recipients_non_null:,} non-null")
print(f"  grant_recipients_opeid: {opeid_recipients_non_null:,} non-null")
print(f"  value_grants_disbursed_unitid: {unitid_disbursed_non_null:,} non-null")
print(f"  value_grants_disbursed_opeid: {opeid_disbursed_non_null:,} non-null")

# --- Select Best Available Columns ---
# INTENT: Choose the column with actual data for Pell recipient counts.
# REASONING: If unitid-level data is available, prefer it (direct join key).
# If only opeid-level is available, use it and note the limitation.
# If neither has data, this is a STOP condition.
if unitid_recipients_non_null > 0:
    recipient_col = "grant_recipients_unitid"
    disbursed_col = "value_grants_disbursed_unitid"
    print(f"\n  Using unitid-level columns (preferred)")
elif opeid_recipients_non_null > 0:
    recipient_col = "grant_recipients_opeid"
    disbursed_col = "value_grants_disbursed_opeid"
    print(f"\n  Using opeid-level columns (unitid-level is all null)")
    print(f"  NOTE: OPEID-level data may aggregate across branch campuses")
else:
    # Neither column has data for Pell grants -- check if there's a
    # structural issue with how Pell data is stored in this dataset.
    # Maybe Pell data is not broken out at the institution level.
    print(f"\n  INVESTIGATION: Both recipient columns are null for Pell.")
    print(f"  Checking if any grant_type has data in unitid columns...")

    # Find which grant_types have unitid-level data
    for gt in sorted(df["grant_type"].drop_nulls().unique().to_list()):
        gt_df = df.filter(pl.col("grant_type") == gt)
        unitid_nn = gt_df.shape[0] - gt_df["grant_recipients_unitid"].null_count()
        opeid_nn = gt_df.shape[0] - gt_df["grant_recipients_opeid"].null_count()
        if unitid_nn > 0 or opeid_nn > 0:
            print(f"    grant_type {gt}: unitid={unitid_nn}, opeid={opeid_nn}")
            # Show sample values for this grant type
            sample = gt_df.filter(
                pl.col("grant_recipients_unitid").is_not_null()
                | pl.col("grant_recipients_opeid").is_not_null()
            ).head(3)
            print(f"    Sample: {sample.select(['unitid', 'grant_type', 'grant_recipients_unitid', 'grant_recipients_opeid']).to_dicts()}")

    # If Pell data is only in OPEID columns but they're also null, we need
    # to check if the data structure is fundamentally different for year 2020.
    # Let's check other years for Pell to see if this is a year-specific issue.
    print(f"\n  Checking Pell data availability across years...")
    df_all_years = fetch_from_mirrors(path=DATASET_PATH)
    df_pell_all = df_all_years.filter(pl.col("grant_type") == PELL_GRANT_TYPE)

    for check_year in [2018, 2019, 2020, 2021]:
        yr_df = df_pell_all.filter(pl.col("year") == check_year)
        if yr_df.shape[0] > 0:
            u_nn = yr_df.shape[0] - yr_df["grant_recipients_unitid"].null_count()
            o_nn = yr_df.shape[0] - yr_df["grant_recipients_opeid"].null_count()
            print(f"    Year {check_year}: {yr_df.shape[0]} rows, unitid_recip={u_nn}, opeid_recip={o_nn}")

    # Use opeid-level data as fallback even if partially null
    if opeid_recipients_non_null > 0:
        recipient_col = "grant_recipients_opeid"
        disbursed_col = "value_grants_disbursed_opeid"
        print(f"\n  Falling back to opeid-level columns")
    else:
        # Final fallback: check if another grant_type can serve as proxy
        # This should not normally happen for Pell
        raise ValueError(
            "STOP: No recipient data available for Pell Grants (grant_type==1) in year 2020. "
            "Both grant_recipients_unitid and grant_recipients_opeid are 100% null. "
            "This may indicate a data structure change. Escalate to orchestrator."
        )

print(f"\n  Selected columns: {recipient_col} -> pell_recipients, {disbursed_col} -> pell_disbursements")

# --- Drop null unitids ---
# INTENT: Remove rows with null unitid since they cannot be joined downstream.
null_unitid_count = df_pell["unitid"].null_count()
if null_unitid_count > 0:
    print(f"  Dropping {null_unitid_count} rows with null unitid")
    df_pell = df_pell.filter(pl.col("unitid").is_not_null())
else:
    print(f"  No null unitids found")

# --- Rename and select columns ---
# INTENT: Rename FSA column names to Plan-expected names.
# REASONING: Generic column names are specific to the grant type after
# filtering. Renaming makes downstream code more readable.
rename_map = {
    recipient_col: "pell_recipients",
    disbursed_col: "pell_disbursements",
}

select_cols = ["unitid", "year", recipient_col, disbursed_col]
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
unitid_unique_count = df_final["unitid"].n_unique()
unitid_total = df_final.shape[0]
unitid_unique = unitid_unique_count == unitid_total
print(f"  [{'PASS' if unitid_unique else 'WARN'}] Unitid uniqueness: {unitid_unique_count:,} unique / {unitid_total:,} total")

# CP1.6: pell_recipients data availability
# REASONING: We need at least SOME non-null pell_recipients values.
# If all values are null, the data is not usable for the analysis.
if "pell_recipients" in df_final.columns:
    pell_null_count = df_final["pell_recipients"].null_count()
    pell_non_null = df_final.shape[0] - pell_null_count
    pell_null_pct = pell_null_count / len(df_final) * 100 if len(df_final) > 0 else 0
    pell_non_null_pct = 100 - pell_null_pct

    # If > 90% null, this is a WARNING (data may be too sparse)
    pell_data_ok = pell_non_null_pct > 10
    print(f"  [{'PASS' if pell_data_ok else 'WARN'}] pell_recipients data availability: {pell_non_null:,} non-null ({pell_non_null_pct:.1f}%)")

    if pell_non_null > 0:
        print(f"  [INFO] pell_recipients describe:")
        print(f"{df_final['pell_recipients'].describe()}")

        # Check for coded values
        for code in [-1, -2, -3]:
            try:
                coded_count = (df_final["pell_recipients"] == code).sum()
                if coded_count > 0:
                    print(f"  [INFO] pell_recipients coded value {code}: {coded_count:,} rows")
            except Exception:
                pass

    if pell_non_null == 0:
        print("  CRITICAL: pell_recipients is 100% null -- data not usable")
        cp1_passed = False

# CP1.7: pell_disbursements basic check
if "pell_disbursements" in df_final.columns:
    pell_disb_nulls = df_final["pell_disbursements"].null_count()
    pell_disb_non_null = df_final.shape[0] - pell_disb_nulls
    print(f"  [INFO] pell_disbursements: {pell_disb_non_null:,} non-null")

# --- Final CP1 Status ---
assert cp1_passed, "STOP: CP1 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:14:53
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 5.4: Fetch FSA grants data (v4 - data-driven column selection)
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
# 
# --- DATA STRUCTURE INVESTIGATION ---
# Non-null counts by grant_type for recipient/disbursement columns:
#   Value columns: ['grant_recipients_unitid', 'value_grants_disbursed_unitid', 'grant_recipients_opeid', 'value_grants_disbursed_opeid']
# 
#   grant_type == 1 (4995 rows):
#     grant_recipients_unitid: 0 non-null / 4,995 (0.0%)
#     value_grants_disbursed_unitid: 0 non-null / 4,995 (0.0%)
#     grant_recipients_opeid: 0 non-null / 4,995 (0.0%)
#     value_grants_disbursed_opeid: 0 non-null / 4,995 (0.0%)
# 
#   grant_type == 2 (4995 rows):
#     grant_recipients_unitid: 95 non-null / 4,995 (1.9%)
#     value_grants_disbursed_unitid: 95 non-null / 4,995 (1.9%)
#     grant_recipients_opeid: 95 non-null / 4,995 (1.9%)
#     value_grants_disbursed_opeid: 95 non-null / 4,995 (1.9%)
# 
#   grant_type == 3 (4995 rows):
#     grant_recipients_unitid: 0 non-null / 4,995 (0.0%)
#     value_grants_disbursed_unitid: 0 non-null / 4,995 (0.0%)
#     grant_recipients_opeid: 0 non-null / 4,995 (0.0%)
#     value_grants_disbursed_opeid: 0 non-null / 4,995 (0.0%)
# 
#   grant_type == 4 (4995 rows):
#     grant_recipients_unitid: 4,989 non-null / 4,995 (99.9%)
#     value_grants_disbursed_unitid: 4,989 non-null / 4,995 (99.9%)
#     grant_recipients_opeid: 4,989 non-null / 4,995 (99.9%)
#     value_grants_disbursed_opeid: 4,989 non-null / 4,995 (99.9%)
# 
#   grant_type == 5 (4995 rows):
#     grant_recipients_unitid: 752 non-null / 4,995 (15.1%)
#     value_grants_disbursed_unitid: 752 non-null / 4,995 (15.1%)
#     grant_recipients_opeid: 752 non-null / 4,995 (15.1%)
#     value_grants_disbursed_opeid: 752 non-null / 4,995 (15.1%)
# 
# --- FILTERING TO PELL GRANTS (grant_type == 1) ---
#   After Pell filter: 4,995 rows
# 
#   Column availability for Pell rows:
#   grant_recipients_unitid: 0 non-null
#   grant_recipients_opeid: 0 non-null
#   value_grants_disbursed_unitid: 0 non-null
#   value_grants_disbursed_opeid: 0 non-null
# 
#   INVESTIGATION: Both recipient columns are null for Pell.
#   Checking if any grant_type has data in unitid columns...
#     grant_type 2: unitid=95, opeid=95
#     Sample: [{'unitid': 100858, 'grant_type': 2, 'grant_recipients_unitid': 1.0, 'grant_recipients_opeid': 1.0}, {'unitid': 101480, 'grant_type': 2, 'grant_recipients_unitid': 1.0, 'grant_recipients_opeid': 1.0}, {'unitid': 104151, 'grant_type': 2, 'grant_recipients_unitid': 2.0, 'grant_recipients_opeid': 2.0}]
#     grant_type 4: unitid=4989, opeid=4989
#     Sample: [{'unitid': 100654, 'grant_type': 4, 'grant_recipients_unitid': 3607.0, 'grant_recipients_opeid': 3607.0}, {'unitid': 100663, 'grant_type': 4, 'grant_recipients_unitid': 4966.0, 'grant_recipients_opeid': 4966.0}, {'unitid': 100690, 'grant_type': 4, 'grant_recipients_unitid': 270.0, 'grant_recipients_opeid': 270.0}]
#     grant_type 5: unitid=752, opeid=752
#     Sample: [{'unitid': 100654, 'grant_type': 5, 'grant_recipients_unitid': 1.0, 'grant_recipients_opeid': 1.0}, {'unitid': 100663, 'grant_type': 5, 'grant_recipients_unitid': 11.0, 'grant_recipients_opeid': 11.0}, {'unitid': 100812, 'grant_type': 5, 'grant_recipients_unitid': 50.0, 'grant_recipients_opeid': 50.0}]
# 
#   Checking Pell data availability across years...
#   (rate limit: waiting 2.0s)
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/fsa/colleges_fsa_grants.parquet
#   OK huggingface: 608,510 rows
#   After filters: 608,510 rows
#     Year 2018: 5142 rows, unitid_recip=0, opeid_recip=0
#     Year 2019: 5071 rows, unitid_recip=0, opeid_recip=0
#     Year 2020: 4995 rows, unitid_recip=0, opeid_recip=0
#     Year 2021: 4920 rows, unitid_recip=0, opeid_recip=0
# Traceback (most recent call last):
#   File "/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/04_fetch-fsa-grants_c.py", line 284, in <module>
#     raise ValueError(
# ValueError: STOP: No recipient data available for Pell Grants (grant_type==1) in year 2020. Both grant_recipients_unitid and grant_recipients_opeid are 100% null. This may indicate a data structure change. Escalate to orchestrator.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
