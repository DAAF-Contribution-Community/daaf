#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 7 Step 10.1 — Iteration 2

Reviewed script: scripts/stage7_transform/05_join-scorecard.py
Prior QA script: scripts/cr/stage7_05_cr1.py

INVESTIGATION TRIGGER:
cr1 Check 10 found 20 rows where earnings_med is NOT null but earnings_pct25 IS null.
Null counts vary across Scorecard columns: earnings_med=525, earnings_pct25=545,
earnings_pct75=533, count_working=525, count_working_highinc=779, count_working_ind=809.
This suggests differential suppression of Scorecard subgroup data.

HYPOTHESIS:
The inconsistent null pattern is caused by Scorecard's privacy suppression of small-count
breakdowns (percentiles and subgroup counts are suppressed at higher thresholds than the
overall median and total count). This is a DATA-ORIGIN property, not a join defect.

EXPECTED OUTCOME:
- If CONFIRMED: The 20 rows with earnings_med but no earnings_pct25 will have low
  count_working values (small cohorts trigger suppression). The join did not cause this.
- If REFUTED: The 20 rows have normal count_working values, suggesting the join
  introduced the inconsistency (a BLOCKER).
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis_with_earnings.parquet"
INPUT_SCORECARD = PROJECT_DIR / "data" / "processed" / "2026-02-15_scorecard_clean.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 7 Step 10.1 — Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
df_sc = pl.read_parquet(INPUT_SCORECARD)

# --- Investigation: Characterize the 20 inconsistent rows ---
# Find rows with earnings_med non-null but earnings_pct25 null
inconsistent = df.filter(
    pl.col("earnings_med").is_not_null() & pl.col("earnings_pct25").is_null()
)
print(f"\nRows with earnings_med but no earnings_pct25: {inconsistent.shape[0]:,}")

if inconsistent.shape[0] > 0:
    # Check their count_working values — small cohorts trigger suppression
    print(f"\ncount_working for these institutions:")
    print(inconsistent.select(["unitid", "inst_name", "earnings_med", "count_working",
                                "earnings_pct25", "earnings_pct75"]))

    print(f"\ncount_working stats for inconsistent rows:")
    print(f"  Min:    {inconsistent['count_working'].min()}")
    print(f"  Median: {inconsistent['count_working'].median()}")
    print(f"  Max:    {inconsistent['count_working'].max()}")

    # Compare to overall count_working stats
    matched = df.filter(pl.col("earnings_med").is_not_null())
    print(f"\ncount_working stats for ALL matched rows:")
    print(f"  Min:    {matched['count_working'].min()}")
    print(f"  Median: {matched['count_working'].median()}")
    print(f"  Max:    {matched['count_working'].max()}")

    # Verify: does the same pattern exist in the RAW Scorecard input?
    inconsistent_ids = inconsistent["unitid"].to_list()
    sc_rows = df_sc.filter(pl.col("unitid").is_in(inconsistent_ids))
    print(f"\nSame institutions in RAW Scorecard input:")
    print(sc_rows.select(["unitid", "earnings_med", "earnings_pct25", "earnings_pct75"]))

    # KEY TEST: Is earnings_pct25 already null in the Scorecard input?
    sc_already_null = sc_rows.filter(pl.col("earnings_pct25").is_null()).shape[0]
    print(f"\nOf {sc_rows.shape[0]} rows, {sc_already_null} already had null earnings_pct25 in Scorecard input")

    if sc_already_null == inconsistent.shape[0]:
        print("\n>> CONFIRMED: All inconsistent nulls originate from Scorecard input data.")
        print(">> The join did NOT introduce these nulls — they are a data-origin property.")
        confirmed = True
    else:
        print(f"\n>> PARTIAL: {sc_already_null}/{inconsistent.shape[0]} were already null in input.")
        print(">> Need to investigate the remaining rows.")
        confirmed = False
else:
    print("No inconsistent rows found — prior cr1 finding may have been transient.")
    confirmed = True

# --- Also characterize the broader null pattern ---
print(f"\n{'=' * 60}")
print("BROADER NULL PATTERN ANALYSIS")
print(f"{'=' * 60}")

scorecard_cols = ["earnings_med", "earnings_pct25", "earnings_pct75", "count_working",
                  "count_working_lowinc", "count_working_midinc", "count_working_highinc",
                  "count_working_dep", "count_working_ind", "count_working_female",
                  "count_working_male"]

print("\nNull counts (output dataset):")
for col in scorecard_cols:
    if col in df.columns:
        nc = df[col].null_count()
        print(f"  {col}: {nc:,} nulls ({nc/df.shape[0]*100:.1f}%)")

print("\nNull counts (Scorecard input):")
for col in scorecard_cols:
    if col in df_sc.columns:
        nc = df_sc[col].null_count()
        print(f"  {col}: {nc:,} nulls ({nc/df_sc.shape[0]*100:.1f}%)")

# The key insight: differential null rates across Scorecard columns are a known
# Scorecard feature. Privacy thresholds suppress subgroup breakdowns at lower
# cohort sizes than the overall median/count. This is documented in Scorecard
# methodology.

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

if confirmed:
    print("\nHypothesis: CONFIRMED")
    print("Implications: The 20 rows with inconsistent nulls are a Scorecard data-origin")
    print("property, not a join defect. Scorecard suppresses percentile breakdowns for")
    print("small cohorts. The join correctly preserved the input data's null pattern.")
    print("Further investigation needed: NO")
    print("Severity assessment: INFO (not a code issue; document for downstream awareness)")
else:
    print("\nHypothesis: PARTIALLY CONFIRMED")
    print("Further investigation needed: YES — check if join mechanics introduced new nulls")
    print("Severity assessment: WARNING (pending further investigation)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:28:32
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage7_05_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 7 Step 10.1 — Iteration 2
# ============================================================
# 
# Rows with earnings_med but no earnings_pct25: 20
# 
# count_working for these institutions:
# shape: (20, 6)
# ┌────────┬────────────────────────┬──────────────┬───────────────┬────────────────┬────────────────┐
# │ unitid ┆ inst_name              ┆ earnings_med ┆ count_working ┆ earnings_pct25 ┆ earnings_pct75 │
# │ ---    ┆ ---                    ┆ ---          ┆ ---           ┆ ---            ┆ ---            │
# │ i64    ┆ str                    ┆ i64          ┆ i64           ┆ i64            ┆ i64            │
# ╞════════╪════════════════════════╪══════════════╪═══════════════╪════════════════╪════════════════╡
# │ 122506 ┆ San Francisco          ┆ 37744        ┆ 43            ┆ null           ┆ 57060          │
# │        ┆ Conservatory of …      ┆              ┆               ┆                ┆                │
# │ 124487 ┆ Epic Bible College     ┆ 44637        ┆ 68            ┆ null           ┆ 58412          │
# │ 130314 ┆ University of Saint    ┆ 46100        ┆ 46            ┆ null           ┆ 63320          │
# │        ┆ Joseph                 ┆              ┆               ┆                ┆                │
# │ 135364 ┆ Luther Rice College &  ┆ 40186        ┆ 68            ┆ null           ┆ 58230          │
# │        ┆ Seminary               ┆              ┆               ┆                ┆                │
# │ 161235 ┆ University of Maine at ┆ 32709        ┆ 29            ┆ null           ┆ 68758          │
# │        ┆ Fort Ke…               ┆              ┆               ┆                ┆                │
# │ …      ┆ …                      ┆ …            ┆ …             ┆ …              ┆ …              │
# │ 439862 ┆ Pacific Islands        ┆ 20443        ┆ 35            ┆ null           ┆ 26745          │
# │        ┆ University             ┆              ┆               ┆                ┆                │
# │ 440794 ┆ Pillar College         ┆ 30497        ┆ 42            ┆ null           ┆ 55838          │
# │ 441982 ┆ Franklin W Olin        ┆ 132969       ┆ 24            ┆ null           ┆ 170900         │
# │        ┆ College of Eng…        ┆              ┆               ┆                ┆                │
# │ 443049 ┆ Faith International    ┆ 42958        ┆ 30            ┆ null           ┆ 58168          │
# │        ┆ University             ┆              ┆               ┆                ┆                │
# │ 443340 ┆ Williamson Christian   ┆ 31932        ┆ 17            ┆ null           ┆ null           │
# │        ┆ College                ┆              ┆               ┆                ┆                │
# └────────┴────────────────────────┴──────────────┴───────────────┴────────────────┴────────────────┘
# 
# count_working stats for inconsistent rows:
#   Min:    17
#   Median: 37.0
#   Max:    95
# 
# count_working stats for ALL matched rows:
#   Min:    16
#   Median: 727.0
#   Max:    30991
# 
# Same institutions in RAW Scorecard input:
# shape: (20, 4)
# ┌────────┬──────────────┬────────────────┬────────────────┐
# │ unitid ┆ earnings_med ┆ earnings_pct25 ┆ earnings_pct75 │
# │ ---    ┆ ---          ┆ ---            ┆ ---            │
# │ i64    ┆ i64          ┆ i64            ┆ i64            │
# ╞════════╪══════════════╪════════════════╪════════════════╡
# │ 122506 ┆ 37744        ┆ null           ┆ 57060          │
# │ 124487 ┆ 44637        ┆ null           ┆ 58412          │
# │ 130314 ┆ 46100        ┆ null           ┆ 63320          │
# │ 135364 ┆ 40186        ┆ null           ┆ 58230          │
# │ 161235 ┆ 32709        ┆ null           ┆ 68758          │
# │ …      ┆ …            ┆ …              ┆ …              │
# │ 439862 ┆ 20443        ┆ null           ┆ 26745          │
# │ 440794 ┆ 30497        ┆ null           ┆ 55838          │
# │ 441982 ┆ 132969       ┆ null           ┆ 170900         │
# │ 443049 ┆ 42958        ┆ null           ┆ 58168          │
# │ 443340 ┆ 31932        ┆ null           ┆ null           │
# └────────┴──────────────┴────────────────┴────────────────┘
# 
# Of 20 rows, 20 already had null earnings_pct25 in Scorecard input
# 
# >> CONFIRMED: All inconsistent nulls originate from Scorecard input data.
# >> The join did NOT introduce these nulls — they are a data-origin property.
# 
# ============================================================
# BROADER NULL PATTERN ANALYSIS
# ============================================================
# 
# Null counts (output dataset):
#   earnings_med: 525 nulls (20.8%)
#   earnings_pct25: 545 nulls (21.6%)
#   earnings_pct75: 533 nulls (21.1%)
#   count_working: 525 nulls (20.8%)
#   count_working_lowinc: 587 nulls (23.2%)
#   count_working_midinc: 624 nulls (24.7%)
#   count_working_highinc: 779 nulls (30.8%)
#   count_working_dep: 576 nulls (22.8%)
#   count_working_ind: 809 nulls (32.0%)
#   count_working_female: 592 nulls (23.4%)
#   count_working_male: 637 nulls (25.2%)
# 
# Null counts (Scorecard input):
#   earnings_med: 0 nulls (0.0%)
#   earnings_pct25: 137 nulls (2.5%)
#   earnings_pct75: 49 nulls (0.9%)
#   count_working: 0 nulls (0.0%)
#   count_working_lowinc: 188 nulls (3.5%)
#   count_working_midinc: 770 nulls (14.3%)
#   count_working_highinc: 1,828 nulls (34.0%)
#   count_working_dep: 515 nulls (9.6%)
#   count_working_ind: 474 nulls (8.8%)
#   count_working_female: 236 nulls (4.4%)
#   count_working_male: 954 nulls (17.7%)
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Hypothesis: CONFIRMED
# Implications: The 20 rows with inconsistent nulls are a Scorecard data-origin
# property, not a join defect. Scorecard suppresses percentile breakdowns for
# small cohorts. The join correctly preserved the input data's null pattern.
# Further investigation needed: NO
# Severity assessment: INFO (not a code issue; document for downstream awareness)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
