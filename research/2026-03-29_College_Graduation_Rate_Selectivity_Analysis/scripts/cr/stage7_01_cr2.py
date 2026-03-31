#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 7 Step 01 -- Iteration 2

Reviewed script: scripts/stage7_transform/01_join-core.py
Prior QA script: scripts/cr/stage7_01_cr1.py

INVESTIGATION TRIGGER:
cr1 Spot-Check 14 found that 2,891 out of 2,893 institutions have open_public=1.
This is highly suspicious -- if nearly 100% of 4-year degree-granting institutions
are flagged as open admissions, the selectivity band creation in downstream task
6.2 (create-bands) would place almost all institutions into the "Open/Less Selective"
band, destroying the core analytical framework.

HYPOTHESIS:
The open_public column does NOT represent what the Plan assumes (0=not open admissions,
1=open admissions). Instead, the value coding may be different (e.g., 1=public, 2=private),
or the original cleaning script may have incorrectly interpreted this variable. If
open_public=1 truly means "open admissions" for 2,891 of 2,893 institutions, the
directory cleaning logic or the source data coding is wrong.

EXPECTED OUTCOME:
- If CONFIRMED (coding is wrong): The open_public variable needs recoding before
  the create-bands step. This is a WARNING for this script (data passes through
  unchanged from directory) but a critical issue for the downstream pipeline.
- If REFUTED (coding is correct): There's a benign explanation, such as open_public
  being a different variable than expected (e.g., publicly available indicator).
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_core.parquet"
DIR_CLEAN = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_directory_clean.parquet"
DIR_RAW = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_directory.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 7 Step 01 -- Iteration 2")
print("open_public variable analysis")
print("=" * 60)

df_core = pl.read_parquet(OUTPUT_FILE)
df_dir_clean = pl.read_parquet(DIR_CLEAN)

print(f"Core: {df_core.shape[0]:,} rows x {df_core.shape[1]} cols")
print(f"Directory clean: {df_dir_clean.shape[0]:,} rows x {df_dir_clean.shape[1]} cols")

# --- Investigation 1: open_public value distribution ---
print("\n--- open_public distribution in core ---")
vc = df_core["open_public"].value_counts().sort("open_public")
for row in vc.iter_rows():
    val, count = row[0], row[1]
    pct = count / len(df_core) * 100
    print(f"  open_public={val}: {count:,} ({pct:.1f}%)")

print("\n--- open_public distribution in directory_clean ---")
vc2 = df_dir_clean["open_public"].value_counts().sort("open_public")
for row in vc2.iter_rows():
    val, count = row[0], row[1]
    pct = count / len(df_dir_clean) * 100
    print(f"  open_public={val}: {count:,} ({pct:.1f}%)")

# --- Investigation 2: Check raw directory for original coding ---
print("\n--- Checking raw directory data ---")
try:
    df_raw = pl.read_parquet(DIR_RAW)
    print(f"Raw directory: {df_raw.shape[0]:,} rows x {df_raw.shape[1]} cols")
    print(f"Raw columns: {df_raw.columns}")

    if "open_public" in df_raw.columns:
        print("\nopen_public in raw data:")
        raw_vc = df_raw["open_public"].value_counts().sort("open_public")
        print(raw_vc)
        print(f"\nopen_public dtype in raw: {df_raw['open_public'].dtype}")
        print(f"open_public null count in raw: {df_raw['open_public'].null_count()}")
    else:
        print("WARNING: open_public not found in raw directory")
        # Check for similar column names
        similar = [c for c in df_raw.columns if "open" in c.lower() or "public" in c.lower()]
        print(f"Similar column names: {similar}")
except Exception as e:
    print(f"Could not load raw directory: {e}")

# --- Investigation 3: Cross-reference with admit_rate ---
# If open_public=1 truly means open admissions, then institutions with
# open_public=1 that also have very low admit_rates would be contradictory
print("\n--- Cross-reference: open_public=1 institutions with low admit_rate ---")
open_with_ar = df_core.filter(
    (pl.col("open_public") == 1) & pl.col("admit_rate").is_not_null()
)
if len(open_with_ar) > 0:
    # How many have admit_rate < 25% (highly selective)?
    highly_selective_open = open_with_ar.filter(pl.col("admit_rate") < 25).shape[0]
    selective_open = open_with_ar.filter(
        (pl.col("admit_rate") >= 25) & (pl.col("admit_rate") < 50)
    ).shape[0]
    moderate_open = open_with_ar.filter(
        (pl.col("admit_rate") >= 50) & (pl.col("admit_rate") < 75)
    ).shape[0]
    less_selective_open = open_with_ar.filter(pl.col("admit_rate") >= 75).shape[0]

    print(f"  open_public=1 institutions WITH admit_rate: {len(open_with_ar):,}")
    print(f"  Of those, admit_rate < 25%: {highly_selective_open}")
    print(f"  Of those, admit_rate 25-50%: {selective_open}")
    print(f"  Of those, admit_rate 50-75%: {moderate_open}")
    print(f"  Of those, admit_rate >= 75%: {less_selective_open}")

    # Show some specific examples of "open admissions" + highly selective
    if highly_selective_open > 0:
        examples = open_with_ar.filter(pl.col("admit_rate") < 25).select(
            ["unitid", "inst_name", "open_public", "admit_rate"]
        ).head(5)
        print(f"\n  Examples of open_public=1 + admit_rate < 25%:")
        print(examples)

# --- Investigation 4: Check the Plan's expectation ---
# Plan says: open_public variable identifies institutions that don't use admissions criteria
# Plan says: open_public == 1 overrides admit_rate for band assignment
# Plan's selectivity band definition: Open/Less Selective = admit_rate >= 75% OR open_public == 1
print("\n--- Plan expectation check ---")
# If open_public=1 for 99.9% of institutions, the band logic would be:
# open_public==1 -> Open/Less Selective for nearly everyone
# This would destroy the selectivity band distribution
print("Plan expects 4 bands with reasonable N per band:")
print("  Highly Selective (<25%): ~150-250")
print("  Selective (25-50%): ~300-500")
print("  Moderately Selective (50-75%): ~500-800")
print("  Open/Less Selective (>=75% or open_public==1): ~500-800")
print()
print(f"If open_public=1 means open admissions for {vc.filter(pl.col('open_public') == 1)['count'][0]:,} institutions,")
print("then nearly ALL institutions would be in Open/Less Selective band.")

# --- Investigation 5: Check if open_public might mean something else ---
# IPEDS directory has open_public as an indicator. In IPEDS:
# 1 = Yes, this institution has open admission (admits all who apply)
# 2 = No, this institution does NOT have open admission
# Check if the cleaning script might have incorrectly treated this
print("\n--- Checking open_public value meaning ---")
# If open_public uses IPEDS coding (1=yes open, 2=no not open), we'd expect
# a MINORITY of 4-year institutions to have open_public=1
# But if 99.9% have value 1, this is more consistent with:
# - open_public meaning "public institution" (most 4-yr are public or publicly reporting)
# - Coded as a simple indicator where 1 means "yes, publicly available" or similar
# - OR the clean script filtered/recoded incorrectly

# Check the open_public=0 institutions
not_open = df_core.filter(pl.col("open_public") != 1)
print(f"\nInstitutions with open_public != 1: {len(not_open):,}")
if len(not_open) > 0:
    print(not_open.select(["unitid", "inst_name", "inst_control", "open_public", "admit_rate"]))

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

# Determine if this is a problem
n_open_1 = df_core.filter(pl.col("open_public") == 1).shape[0]
n_total = len(df_core)
pct_open = n_open_1 / n_total * 100

if pct_open > 90:
    # Very likely NOT an open admissions indicator -- or it is but the values
    # represent something different than expected
    confirmed = True
    implications = (
        "open_public=1 for {:.1f}% of institutions cannot mean 'open admissions' "
        "in the traditional sense. Either the variable coding is different from "
        "Plan expectation (IPEDS uses 1=yes open, 2=no), or the cleaning script "
        "incorrectly interpreted the variable. The create-bands step (Task 6.2) "
        "uses open_public==1 to override admit_rate for band assignment. If this "
        "variable is wrong, selectivity bands will be wrong."
    ).format(pct_open)
    is_blocker = False  # This script just passes through the data; issue is upstream
    is_warning = True
    needs_more = False
else:
    confirmed = False
    implications = "open_public distribution is plausible."
    is_blocker = False
    is_warning = False
    needs_more = False

print(f"Hypothesis: {'CONFIRMED' if confirmed else 'REFUTED'}")
print(f"Implications: {implications}")
print(f"Further investigation needed: {'YES' if needs_more else 'NO'}")
print(f"Severity assessment: {'BLOCKER' if is_blocker else 'WARNING' if is_warning else 'INFO'}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 00:16:46
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_01_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 7 Step 01 -- Iteration 2
# open_public variable analysis
# ============================================================
# Core: 2,893 rows x 14 cols
# Directory clean: 2,893 rows x 7 cols
# 
# --- open_public distribution in core ---
#   open_public=0: 2 (0.1%)
#   open_public=1: 2,891 (99.9%)
# 
# --- open_public distribution in directory_clean ---
#   open_public=0: 2 (0.1%)
#   open_public=1: 2,891 (99.9%)
# 
# --- Checking raw directory data ---
# Raw directory: 12,729 rows x 89 cols
# Raw columns: ['unitid', 'year', 'opeid', 'inst_name', 'inst_alias', 'address', 'state_abbr', 'fips', 'zip', 'phone_number', 'city', 'county_name', 'county_fips', 'region', 'urban_centric_locale', 'cbsa', 'cbsa_type', 'csa', 'necta', 'longitude', 'latitude', 'congress_district_id', 'ein', 'ueis', 'chief_admin_name', 'chief_admin_title', 'inst_status', 'currently_active_ipeds', 'degree_granting', 'open_public', 'title_iv_indicator', 'postsec_public_active', 'postsec_public_active_title_iv', 'date_closed', 'newid', 'year_deleted', 'inst_control', 'institution_level', 'inst_category', 'inst_size', 'sector', 'primarily_postsecondary', 'hbcu', 'hospital', 'medical_degree', 'tribal_college', 'land_grant', 'offering_highest_degree', 'offering_highest_level', 'offering_undergrad', 'offering_grad', 'url_school', 'url_fin_aid', 'url_application', 'url_netprice', 'url_veterans', 'url_athletes', 'url_disability_services', 'cc_basic_2010', 'cc_instruc_undergrad_2010', 'cc_instruc_grad_2010', 'cc_undergrad_2010', 'cc_enroll_2010', 'cc_size_setting_2010', 'cc_basic_2000', 'cc_basic_2015', 'cc_instruc_undergrad_2015', 'cc_instruc_grad_2015', 'cc_undergrad_2015', 'cc_enroll_2015', 'cc_size_setting_2015', 'cc_basic_2018', 'cc_instruc_undergrad_2018', 'cc_instruc_grad_2018', 'cc_undergrad_2018', 'cc_enroll_2018', 'cc_size_setting_2018', 'comparison_group', 'comparison_group_custom', 'inst_system_flag', 'inst_system_name', 'reporting_method', 'duns', 'cc_basic_2021', 'cc_instruc_undergrad_2021', 'cc_instruc_grad_2021', 'cc_undergrad_2021', 'cc_enroll_2021', 'cc_size_setting_2021']
# 
# open_public in raw data:
# shape: (2, 2)
# ┌─────────────┬───────┐
# │ open_public ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 0           ┆ 4     │
# │ 1           ┆ 12725 │
# └─────────────┴───────┘
# 
# open_public dtype in raw: Int64
# open_public null count in raw: 0
# 
# --- Cross-reference: open_public=1 institutions with low admit_rate ---
#   open_public=1 institutions WITH admit_rate: 1,751
#   Of those, admit_rate < 25%: 76
#   Of those, admit_rate 25-50%: 201
#   Of those, admit_rate 50-75%: 610
#   Of those, admit_rate >= 75%: 864
# 
#   Examples of open_public=1 + admit_rate < 25%:
# shape: (5, 4)
# ┌────────┬─────────────────────────────────┬─────────────┬────────────┐
# │ unitid ┆ inst_name                       ┆ open_public ┆ admit_rate │
# │ ---    ┆ ---                             ┆ ---         ┆ ---        │
# │ i64    ┆ str                             ┆ i64         ┆ f64        │
# ╞════════╪═════════════════════════════════╪═════════════╪════════════╡
# │ 110404 ┆ California Institute of Techno… ┆ 1           ┆ 6.694143   │
# │ 110635 ┆ University of California-Berke… ┆ 1           ┆ 17.476323  │
# │ 110662 ┆ University of California-Los A… ┆ 1           ┆ 14.330853  │
# │ 112260 ┆ Claremont McKenna College       ┆ 1           ┆ 13.343385  │
# │ 115409 ┆ Harvey Mudd College             ┆ 1           ┆ 17.957021  │
# └────────┴─────────────────────────────────┴─────────────┴────────────┘
# 
# --- Plan expectation check ---
# Plan expects 4 bands with reasonable N per band:
#   Highly Selective (<25%): ~150-250
#   Selective (25-50%): ~300-500
#   Moderately Selective (50-75%): ~500-800
#   Open/Less Selective (>=75% or open_public==1): ~500-800
# 
# If open_public=1 means open admissions for 2,891 institutions,
# then nearly ALL institutions would be in Open/Less Selective band.
# 
# --- Checking open_public value meaning ---
# 
# Institutions with open_public != 1: 2
# shape: (2, 5)
# ┌────────┬─────────────────────────────────┬──────────────┬─────────────┬────────────┐
# │ unitid ┆ inst_name                       ┆ inst_control ┆ open_public ┆ admit_rate │
# │ ---    ┆ ---                             ┆ ---          ┆ ---         ┆ ---        │
# │ i64    ┆ str                             ┆ i64          ┆ i64         ┆ f64        │
# ╞════════╪═════════════════════════════════╪══════════════╪═════════════╪════════════╡
# │ 119678 ┆ Naval Postgraduate School       ┆ 1            ┆ 0           ┆ null       │
# │ 200697 ┆ Air Force Institute of Technol… ┆ 1            ┆ 0           ┆ null       │
# └────────┴─────────────────────────────────┴──────────────┴─────────────┴────────────┘
# 
# ============================================================
# INTERPRETATION
# ============================================================
# Hypothesis: CONFIRMED
# Implications: open_public=1 for 99.9% of institutions cannot mean 'open admissions' in the traditional sense. Either the variable coding is different from Plan expectation (IPEDS uses 1=yes open, 2=no), or the cleaning script incorrectly interpreted the variable. The create-bands step (Task 6.2) uses open_public==1 to override admit_rate for band assignment. If this variable is wrong, selectivity bands will be wrong.
# Further investigation needed: NO
# Severity assessment: WARNING
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
