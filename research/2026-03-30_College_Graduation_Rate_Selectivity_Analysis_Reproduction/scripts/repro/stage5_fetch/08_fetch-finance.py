#!/usr/bin/env python3
"""
Stage 5.8: Fetch IPEDS Finance data for instructional expenditure per FTE analysis.

Task: fetch-finance
Wave: 1, Step: 8, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-03-29_ipeds_finance.parquet
Checkpoint: CP1

Skill provenance note: education-data-query skill used for mirror configuration
and fetch patterns. The skill's coded value mappings and column definitions
should be verified against actual data (this fetch is a discovery step for
column names).
"""

import time

import polars as pl
import yaml
from pathlib import Path

# --- Config ---
# INTENT: Configure fetch parameters for IPEDS Finance data.
# REASONING: We need instructional expenditure and FTE data to calculate
#   instructional expenditure per FTE for the selectivity analysis. The exact
#   column names are TBD -- this fetch is partly a discovery step.
# ASSUMES: Dataset path from datasets-reference.md is correct.
#   Portal uses integer coding for missing values (-1, -2, -3).
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-03-29"

# INTENT: Try 2017 first (latest expected per Stage 3 findings), then fallback years.
# REASONING: IPEDS finance data may lag. We try preferred year first, then
#   fall back to adjacent years in order of proximity/preference.
PREFERRED_YEAR = 2017
FALLBACK_YEARS = [2016, 2018, 2019, 2020]

# Dataset path (from education-data-query datasets-reference.md)
# INTENT: Single-file dataset containing all years of IPEDS finance data.
DATASET_PATH = "ipeds/colleges_ipeds_finance"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ipeds_finance.parquet"

# Domain configuration (from Plan domain config)
YEAR_COL = "year"
FLAG_YEARS = [2020, 2021]
CODED_MISSING_VALUES = [-1, -2, -3]

# Expected row range per Plan risk register
EXPECTED_MIN_ROWS = 1000
EXPECTED_MAX_ROWS = 10000

# --- Mirror Configuration ---
# INTENT: Download IPEDS Finance from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
#   Format-specific read driven by each mirror's read_strategy field.
#   All mirrors use the same canonical path from datasets-reference.md.
# REFERENCE: mirrors.yaml for mirror config, datasets-reference.md for canonical paths.
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

        # Build URL from mirror's url_template + canonical path
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


# --- Load ---
print("=" * 60)
print("Stage 5.8: Fetch IPEDS Finance Data")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Full Dataset (no year filter yet) ---
# INTENT: Download the full IPEDS Finance file to discover available years and columns.
# REASONING: We need to inspect what years are available before filtering, since
#   the preferred year (2017) may not be present. We also need to discover all
#   column names since exact expenditure column names are not yet confirmed.
# ASSUMES: Dataset is a single-file type (all years in one file per datasets-reference.md).
print("\nFetching IPEDS Finance data (full dataset for year/column discovery)...")
df_full = fetch_from_mirrors(path=DATASET_PATH)
print(f"Full dataset shape: {df_full.shape[0]:,} rows x {df_full.shape[1]} cols")

# --- Column Discovery ---
# INTENT: Log ALL column names for downstream schema planning.
# REASONING: The exact column names for instructional expenditure and FTE are
#   not yet confirmed from the codebook. This is a discovery step.
print("\n" + "=" * 60)
print("COLUMN DISCOVERY")
print("=" * 60)
print(f"\nAll columns ({df_full.shape[1]}):")
for i, col in enumerate(df_full.columns):
    print(f"  {i+1:3d}. {col} ({df_full[col].dtype})")

# INTENT: Identify expenditure-related columns by name pattern matching.
# REASONING: IPEDS finance columns related to expenditure often contain
#   "instruction", "expend", or "expense" in the name.
expenditure_cols = [
    c for c in df_full.columns
    if any(kw in c.lower() for kw in ["instruction", "expend", "expense"])
]
print(f"\nExpenditure-related columns ({len(expenditure_cols)}):")
for col in expenditure_cols:
    print(f"  - {col} ({df_full[col].dtype})")

# INTENT: Identify FTE-related columns.
# REASONING: We need est_fte or similar column for per-FTE calculations.
fte_cols = [c for c in df_full.columns if "fte" in c.lower()]
print(f"\nFTE-related columns ({len(fte_cols)}):")
for col in fte_cols:
    print(f"  - {col} ({df_full[col].dtype})")

# --- Year Discovery ---
# INTENT: Determine which years are available in the dataset.
# REASONING: Finance data may have a different cutoff than other IPEDS datasets.
print("\n" + "=" * 60)
print("YEAR DISCOVERY")
print("=" * 60)

if "year" in df_full.columns:
    years_available = sorted(df_full["year"].unique().to_list())
    max_year = max(years_available)
    min_year = min(years_available)
    print(f"Years available: {min_year} to {max_year}")
    print(f"All years: {years_available}")
    print(f"Max year in dataset: {max_year}")

    # Year counts
    year_counts = df_full.group_by("year").len().sort("year")
    print("\nRows per year:")
    for row in year_counts.iter_rows():
        print(f"  {row[0]}: {row[1]:,} rows")
else:
    print("[WARN] No 'year' column found in dataset")
    years_available = []
    max_year = None

# --- Select Target Year ---
# INTENT: Use preferred year (2017) if available, otherwise try fallback years.
# REASONING: Per task specification, prefer 2017 as latest expected in Portal.
#   Fallback order: 2016, 2018, 2019, 2020. Log actual year used.
# ASSUMES: At least one of the target years exists in the dataset.
actual_year = None
if PREFERRED_YEAR in years_available:
    actual_year = PREFERRED_YEAR
    print(f"\nPreferred year {PREFERRED_YEAR} is available. Using it.")
else:
    print(f"\nPreferred year {PREFERRED_YEAR} NOT available.")
    for fallback_year in FALLBACK_YEARS:
        if fallback_year in years_available:
            actual_year = fallback_year
            print(f"Fallback year {fallback_year} is available. Using it.")
            break
        else:
            print(f"  Fallback year {fallback_year} not available.")

if actual_year is None:
    # INTENT: Try the max year available as last resort.
    # REASONING: If none of the preferred/fallback years are available,
    #   we still want to fetch data if any year exists.
    if max_year is not None:
        actual_year = max_year
        print(f"No preferred/fallback years found. Using max available year: {actual_year}")
    else:
        raise RuntimeError("STOP: No years available in IPEDS Finance dataset")

# --- Filter to Target Year ---
# INTENT: Filter full dataset to selected year only.
# REASONING: We need a single year of cross-sectional finance data.
print(f"\nFiltering to year {actual_year}...")
df = df_full.filter(pl.col("year") == actual_year)
print(f"Filtered shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Expenditure Column Stats ---
# INTENT: Report descriptive statistics for expenditure-related columns found.
# REASONING: This helps verify data quality and identify which columns to use
#   for the instructional expenditure per FTE calculation.
print("\n" + "=" * 60)
print("EXPENDITURE COLUMN STATISTICS (filtered year)")
print("=" * 60)

for col in expenditure_cols:
    if col in df.columns:
        col_data = df[col]
        non_null = col_data.drop_nulls()
        # INTENT: Count coded missing values separately from true nulls.
        # REASONING: Portal coded values (-1, -2, -3) are semantically missing
        #   but stored as integers. Report both true nulls and coded values.
        coded_count = 0
        if col_data.dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            for code in CODED_MISSING_VALUES:
                coded_count += (col_data == code).sum()

        print(f"\n  {col}:")
        print(f"    dtype: {col_data.dtype}")
        print(f"    null count: {col_data.null_count()} ({col_data.null_count() / len(df) * 100:.1f}%)")
        print(f"    coded missing (-1/-2/-3): {coded_count}")
        if non_null.shape[0] > 0 and col_data.dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            # Filter out coded missing for stats
            valid = non_null.filter(~non_null.is_in(CODED_MISSING_VALUES))
            if valid.shape[0] > 0:
                print(f"    min: {valid.min()}")
                print(f"    max: {valid.max()}")
                print(f"    mean: {valid.mean():.2f}")
                print(f"    median: {valid.median():.2f}")

# --- FTE Column Stats ---
print("\n" + "=" * 60)
print("FTE COLUMN STATISTICS (filtered year)")
print("=" * 60)

for col in fte_cols:
    if col in df.columns:
        col_data = df[col]
        non_null = col_data.drop_nulls()
        coded_count = 0
        if col_data.dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            for code in CODED_MISSING_VALUES:
                coded_count += (col_data == code).sum()

        print(f"\n  {col}:")
        print(f"    dtype: {col_data.dtype}")
        print(f"    null count: {col_data.null_count()} ({col_data.null_count() / len(df) * 100:.1f}%)")
        print(f"    coded missing (-1/-2/-3): {coded_count}")
        if non_null.shape[0] > 0 and col_data.dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            valid = non_null.filter(~non_null.is_in(CODED_MISSING_VALUES))
            if valid.shape[0] > 0:
                print(f"    min: {valid.min()}")
                print(f"    max: {valid.max()}")
                print(f"    mean: {valid.mean():.2f}")
                print(f"    median: {valid.median():.2f}")
                print(f"    null rate (true + coded): {(col_data.null_count() + coded_count) / len(df) * 100:.1f}%")

# --- Save ---
# INTENT: Persist filtered finance data as parquet for downstream cleaning.
# REASONING: Parquet preserves schema and compresses efficiently.
df.write_parquet(OUTPUT_PARQUET)
print(f"\nSaved: {OUTPUT_PARQUET}")
print(f"Actual year saved: {actual_year}")

# --- CP1 Validation ---
# INTENT: Verify fetched data meets Plan expectations for row counts,
#   critical columns, year coverage, and missingness.
# REASONING: CP1 ensures data is structurally sound before proceeding
#   to Stage 6 cleaning.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

cp1_passed = True

# CP1.1: Non-empty dataset
if df.shape[0] == 0:
    print("[FAIL] Empty dataset after year filter")
    cp1_passed = False
else:
    print(f"[PASS] {df.shape[0]:,} rows loaded for year {actual_year}")

# CP1.2: Row count reasonableness
rows_ok = EXPECTED_MIN_ROWS <= df.shape[0] <= EXPECTED_MAX_ROWS
if rows_ok:
    print(f"[PASS] Row count {df.shape[0]:,} within expected range ({EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")
elif df.shape[0] < EXPECTED_MIN_ROWS:
    print(f"[WARN] Row count {df.shape[0]:,} below expected minimum ({EXPECTED_MIN_ROWS:,})")
else:
    print(f"[WARN] Row count {df.shape[0]:,} above expected maximum ({EXPECTED_MAX_ROWS:,})")

# CP1.3: Critical columns present (unitid, year, fips are core identifiers)
required_cols = ["unitid", "year", "fips"]
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    print(f"[FAIL] Missing critical columns: {missing_cols}")
    cp1_passed = False
else:
    print(f"[PASS] All critical columns present: {required_cols}")

# CP1.4: No nulls in identifier columns
if "unitid" in df.columns:
    unitid_nulls = df["unitid"].null_count()
    year_nulls = df["year"].null_count()
    no_id_nulls = unitid_nulls == 0 and year_nulls == 0
    if no_id_nulls:
        print(f"[PASS] No nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")
    else:
        print(f"[FAIL] Nulls in ID columns: unitid={unitid_nulls}, year={year_nulls}")
        cp1_passed = False

# CP1.5: Year matches what we intended
actual_years_in_data = sorted(df["year"].unique().to_list()) if "year" in df.columns else []
if actual_years_in_data == [actual_year]:
    print(f"[PASS] Data contains only the target year: {actual_year}")
else:
    print(f"[WARN] Expected only year {actual_year}, found: {actual_years_in_data}")

# CP1.6: Expenditure and FTE columns found
if len(expenditure_cols) > 0:
    print(f"[PASS] Found {len(expenditure_cols)} expenditure-related column(s)")
else:
    print(f"[WARN] No expenditure-related columns found by name pattern")

if len(fte_cols) > 0:
    print(f"[PASS] Found {len(fte_cols)} FTE-related column(s)")
else:
    print(f"[WARN] No FTE-related columns found by name pattern")

# CP1.7: Missingness summary for key columns
print("\nMissingness summary (key columns):")
key_check_cols = required_cols + expenditure_cols + fte_cols
for col in key_check_cols:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        coded = 0
        if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            for code in CODED_MISSING_VALUES:
                coded += (df[col] == code).sum()
        total_missing_pct = (df[col].null_count() + coded) / len(df) * 100
        status = "PASS" if total_missing_pct < 50 else ("WARN" if total_missing_pct < 90 else "FAIL")
        print(f"  [{status}] {col}: null={df[col].null_count()} ({null_pct:.1f}%), coded={coded}, total_missing={total_missing_pct:.1f}%")
        if total_missing_pct > 90:
            cp1_passed = False

# CP1.8: Data lag check
if actual_year < PREFERRED_YEAR:
    lag_years = PREFERRED_YEAR - actual_year
    print(f"\n[WARN] Data lag: preferred {PREFERRED_YEAR}, actual {actual_year} ({lag_years}-year lag)")
elif actual_year > PREFERRED_YEAR:
    print(f"\n[NOTE] Using year {actual_year} which is newer than preferred {PREFERRED_YEAR}")

# CP1.9: COVID flag year check
if actual_year in FLAG_YEARS:
    print(f"[WARN] FLAG-YEARS: Using data from {actual_year} which is a COVID-impacted year. "
          "Document comparability concerns in limitations.")

# Final CP1 status
print(f"\nCP1 VALIDATION: {'PASSED' if cp1_passed else 'FAILED'}")
print("=" * 60)

if not cp1_passed:
    raise ValueError("CP1 FAILED - see details above")

# --- Recommendation ---
# INTENT: Summarize column discovery findings for downstream Stage 6 script.
print("\n" + "=" * 60)
print("COLUMN RECOMMENDATIONS FOR DOWNSTREAM")
print("=" * 60)
print(f"Expenditure columns found: {expenditure_cols}")
print(f"FTE columns found: {fte_cols}")
if expenditure_cols and fte_cols:
    print("Recommended: Use these columns in Stage 6 cleaning and Stage 7 transform")
    print("  to calculate instructional_expenditure_per_fte.")
else:
    print("[WARN] Column discovery incomplete. Manual review of full column list needed.")



# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 22:17:50
# Command: python3 /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/scripts/repro/stage5_fetch/08_fetch-finance.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.8: Fetch IPEDS Finance Data
# ============================================================
# 
# Fetching IPEDS Finance data (full dataset for year/column discovery)...
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_finance.parquet
#   [OK] huggingface: 227,084 rows
#   After filters: 227,084 rows
# Full dataset shape: 227,084 rows x 141 cols
# 
# ============================================================
# COLUMN DISCOVERY
# ============================================================
# 
# All columns (141):
#     1. unitid (Int64)
#     2. year (Int64)
#     3. fips (Int64)
#     4. rev_tuition_fees_gross (Float64)
#     5. rev_tuition_fees_net (Float64)
#     6. rev_appropriations_fed (Float64)
#     7. rev_appropriations_state (Float64)
#     8. rev_appropriations_local (Float64)
#     9. rev_grants_contracts_federal (Float64)
#    10. rev_grants_contracts_state (Float64)
#    11. rev_grants_contracts_local (Float64)
#    12. rev_fed_approps_grants (Float64)
#    13. rev_state_local_approps_grants (Float64)
#    14. rev_gifts_grants_contracts (Float64)
#    15. rev_affiliated_entities (Float64)
#    16. rev_investment_return (Float64)
#    17. rev_edu_services_sales (Float64)
#    18. rev_auxiliary_enterprises_gross (Float64)
#    19. rev_auxiliary_enterprises_net (Float64)
#    20. rev_independent_operations (Float64)
#    21. rev_other_operating (Float64)
#    22. rev_other_nonoperating (Float64)
#    23. rev_other_additions (Float64)
#    24. rev_other (Float64)
#    25. rev_hospital (Float64)
#    26. rev_hosp_ind_op_other (Float64)
#    27. rev_operating (Float64)
#    28. rev_nonoperating (Float64)
#    29. rev_capital_approps (Float64)
#    30. rev_capital_grants_gifts (Float64)
#    31. rev_endowment_income (Float64)
#    32. rev_endowment_additions (Float64)
#    33. rev_additions (Float64)
#    34. rev_total_current (Float64)
#    35. sch_pell_grant (Float64)
#    36. sch_other_federal_grants (Float64)
#    37. sch_grants_state (Float64)
#    38. sch_grants_local (Float64)
#    39. sch_grants_state_local (Float64)
#    40. sch_restricted_inst_grants (Float64)
#    41. sch_unrestricted_inst_grants (Float64)
#    42. sch_grants_institutional (Float64)
#    43. sch_grants_private (Float64)
#    44. sch_total_student_aid (Float64)
#    45. sch_allowances_tuition_fees (Float64)
#    46. sch_allowances_aux_enterp (Float64)
#    47. sch_allowances_total (Float64)
#    48. sch_exp_net_fellowships (Float64)
#    49. exp_instruc_total (Float64)
#    50. exp_instruc_salaries (Float64)
#    51. exp_research_total (Float64)
#    52. exp_research_salaries (Float64)
#    53. exp_pub_serv_total (Float64)
#    54. exp_pub_serv_salaries (Float64)
#    55. exp_res_pub_serv_total (Float64)
#    56. exp_res_pub_serv_salaries (Float64)
#    57. exp_acad_supp_total (Float64)
#    58. exp_acad_supp_salaries (Float64)
#    59. exp_student_serv_total (Float64)
#    60. exp_student_serv_salaries (Float64)
#    61. exp_inst_supp_total (Float64)
#    62. exp_inst_supp_salaries (Float64)
#    63. exp_acad_inst_student_total (Float64)
#    64. exp_acad_inst_student_salaries (Float64)
#    65. exp_aux_ent_total (Float64)
#    66. exp_aux_ent_salaries (Float64)
#    67. exp_net_grant_aid_total (Float64)
#    68. exp_net_grant_aid_salaries (Float64)
#    69. exp_hospital_total (Float64)
#    70. exp_hospital_salaries (Float64)
#    71. exp_ind_op_total (Float64)
#    72. exp_ind_op_salaries (Float64)
#    73. exp_other_total_funct (Float64)
#    74. exp_other_salaries (Float64)
#    75. exp_total_current (Float64)
#    76. exp_total_salaries (Float64)
#    77. exp_total_benefits (Float64)
#    78. exp_total_opm (Float64)
#    79. exp_total_depr (Float64)
#    80. exp_total_interest (Float64)
#    81. exp_total_other_nat (Float64)
#    82. endowment_beg (Float64)
#    83. endowment_end (Float64)
#    84. own_endowment_assets (Int64)
#    85. longterm_investments (Float64)
#    86. depr_capital_assets (Float64)
#    87. assets (Float64)
#    88. liabilities (Float64)
#    89. assets_net (Float64)
#    90. def_outflows_resources (Float64)
#    91. longterm_debt (Float64)
#    92. def_inflows_resources (Float64)
#    93. invest_capital_assets (Float64)
#    94. position_net (Float64)
#    95. plant_prop_equip_debt (Float64)
#    96. equity_total (Float64)
#    97. land_improvements (Float64)
#    98. infrastructure (Float64)
#    99. buildings (Float64)
#   100. equipment (Float64)
#   101. construction_in_progress (Float64)
#   102. other_plant_prop_equip (Float64)
#   103. plant_property_equipment (Float64)
#   104. depreciation_accumulated (Float64)
#   105. intangible_assets_net (Float64)
#   106. capital_assets_other (Float64)
#   107. plant_prop_equip_net (Float64)
#   108. total_revenues_additions (Float64)
#   109. total_expenses_deductions (Float64)
#   110. equity_changes_total (Float64)
#   111. income_net (Float64)
#   112. equity_changes_other (Float64)
#   113. equity_beg (Float64)
#   114. net_equity_beg_adjust (Float64)
#   115. equity_end (Float64)
#   116. net_position_change (Float64)
#   117. net_position_beginning (Float64)
#   118. net_position_adjustments (Float64)
#   119. net_position_end (Float64)
#   120. income_tax_fed (Float64)
#   121. income_tax_state (Float64)
#   122. pension_info_reported (Int64)
#   123. def_inflows_pension (Float64)
#   124. def_outflows_pension (Float64)
#   125. pension_expense (Float64)
#   126. net_pension_liability (Float64)
#   127. parent_child_flag (Int64)
#   128. parent_child_system_flag (Int64)
#   129. parent_unitid (Int64)
#   130. parent_child_allocation (Float64)
#   131. reporting_form (Int64)
#   132. form_type (Int64)
#   133. gasb_alternative_accounting (Int64)
#   134. pell_grant_treatment (Int64)
#   135. athletic_expense_treatment (Int64)
#   136. cpi (Float64)
#   137. hepi (Float64)
#   138. heca (Float64)
#   139. est_fte (Int64)
#   140. rep_fte (Int64)
#   141. calc_fte (Float64)
# 
# Expenditure-related columns (3):
#   - total_expenses_deductions (Float64)
#   - pension_expense (Float64)
#   - athletic_expense_treatment (Int64)
# 
# FTE-related columns (3):
#   - est_fte (Int64)
#   - rep_fte (Int64)
#   - calc_fte (Float64)
# 
# ============================================================
# YEAR DISCOVERY
# ============================================================
# Years available: 1979 to 2017
# All years: [1979, 1983, 1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017]
# Max year in dataset: 2017
# 
# Rows per year:
#   1979: 3,189 rows
#   1983: 3,302 rows
#   1984: 3,379 rows
#   1985: 3,388 rows
#   1986: 3,604 rows
#   1987: 3,626 rows
#   1988: 4,238 rows
#   1989: 3,617 rows
#   1990: 3,646 rows
#   1991: 3,726 rows
#   1992: 3,728 rows
#   1993: 3,787 rows
#   1994: 3,813 rows
#   1995: 6,960 rows
#   1996: 9,896 rows
#   1997: 9,744 rows
#   1998: 9,496 rows
#   1999: 9,513 rows
#   2000: 9,769 rows
#   2001: 7,643 rows
#   2002: 7,030 rows
#   2003: 6,916 rows
#   2004: 7,018 rows
#   2005: 7,052 rows
#   2006: 7,052 rows
#   2007: 7,126 rows
#   2008: 7,316 rows
#   2009: 7,503 rows
#   2010: 7,643 rows
#   2011: 7,735 rows
#   2012: 7,764 rows
#   2013: 7,687 rows
#   2014: 7,647 rows
#   2015: 7,521 rows
#   2016: 7,153 rows
#   2017: 6,857 rows
# 
# Preferred year 2017 is available. Using it.
# 
# Filtering to year 2017...
# Filtered shape: 6,857 rows x 141 cols
# 
# ============================================================
# EXPENDITURE COLUMN STATISTICS (filtered year)
# ============================================================
# 
#   total_expenses_deductions:
#     dtype: Float64
#     null count: 3124 (45.6%)
#     coded missing (-1/-2/-3): 0
#     min: 65138.0
#     max: 36180086784.0
#     mean: 162237673.80
#     median: 34888824.00
# 
#   pension_expense:
#     dtype: Float64
#     null count: 5447 (79.4%)
#     coded missing (-1/-2/-3): 0
#     min: -261974400.0
#     max: 438106240.0
#     mean: 7414429.10
#     median: 1639894.00
# 
#   athletic_expense_treatment:
#     dtype: Int64
#     null count: 0 (0.0%)
#     coded missing (-1/-2/-3): 3483
#     min: 1
#     max: 4
#     mean: 2.26
#     median: 2.00
# 
# ============================================================
# FTE COLUMN STATISTICS (filtered year)
# ============================================================
# 
#   est_fte:
#     dtype: Int64
#     null count: 296 (4.3%)
#     coded missing (-1/-2/-3): 0
#     min: 0
#     max: 79173
#     mean: 2491.96
#     median: 456.00
#     null rate (true + coded): 4.3%
# 
#   rep_fte:
#     dtype: Int64
#     null count: 296 (4.3%)
#     coded missing (-1/-2/-3): 0
#     min: 0
#     max: 79173
#     mean: 2565.59
#     median: 480.00
#     null rate (true + coded): 4.3%
# 
#   calc_fte:
#     dtype: Float64
#     null count: 269 (3.9%)
#     coded missing (-1/-2/-3): 0
#     min: 2.0
#     max: 103975.0
#     mean: 2340.59
#     median: 387.50
#     null rate (true + coded): 3.9%
# 
# Saved: /daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/data/raw/2026-03-29_ipeds_finance.parquet
# Actual year saved: 2017
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
# [PASS] 6,857 rows loaded for year 2017
# [PASS] Row count 6,857 within expected range (1,000-10,000)
# [PASS] All critical columns present: ['unitid', 'year', 'fips']
# [PASS] No nulls in ID columns: unitid=0, year=0
# [PASS] Data contains only the target year: 2017
# [PASS] Found 3 expenditure-related column(s)
# [PASS] Found 3 FTE-related column(s)
# 
# Missingness summary (key columns):
#   [PASS] unitid: null=0 (0.0%), coded=0, total_missing=0.0%
#   [PASS] year: null=0 (0.0%), coded=0, total_missing=0.0%
#   [PASS] fips: null=172 (2.5%), coded=0, total_missing=2.5%
#   [PASS] total_expenses_deductions: null=3124 (45.6%), coded=0, total_missing=45.6%
#   [WARN] pension_expense: null=5447 (79.4%), coded=0, total_missing=79.4%
#   [WARN] athletic_expense_treatment: null=0 (0.0%), coded=3483, total_missing=50.8%
#   [PASS] est_fte: null=296 (4.3%), coded=0, total_missing=4.3%
#   [PASS] rep_fte: null=296 (4.3%), coded=0, total_missing=4.3%
#   [PASS] calc_fte: null=269 (3.9%), coded=0, total_missing=3.9%
# 
# CP1 VALIDATION: PASSED
# ============================================================
# 
# ============================================================
# COLUMN RECOMMENDATIONS FOR DOWNSTREAM
# ============================================================
# Expenditure columns found: ['total_expenses_deductions', 'pension_expense', 'athletic_expense_treatment']
# FTE columns found: ['est_fte', 'rep_fte', 'calc_fte']
# Recommended: Use these columns in Stage 6 cleaning and Stage 7 transform
#   to calculate instructional_expenditure_per_fte.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
