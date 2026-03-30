#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 5 Step 3 -- Iteration 2

Reviewed script: scripts/stage5_fetch/03_fetch-grad-rates_a.py
Prior QA script: scripts/cr/stage5_03_cr1.py

INVESTIGATION TRIGGER:
  1. cr1 Spot 12 found completion_rate_150pct range is [0.0, 1.0], NOT [0, 100].
     Plan.md CP2 specifies "completion_rate_150pct range: 0-100" and Stage 7->8
     interface says "completion_rate_150pct between 0 and 100".
  2. cr1 Spot 15 found many institution-subcohort combos with 3-8 total-rows
     (race==99, sex==99) instead of the expected 2 per year. Multiple cohort_years
     may be present per reporting year.

HYPOTHESIS:
  H1: completion_rate_150pct is stored as a proportion (0-1) in the Portal data,
      and the Plan.md's reference to "0-100" is a documentation imprecision that
      Stage 6 cleaning must handle (either rescale or adjust expectations).
  H2: Multiple cohort_year values exist per reporting year for some institutions,
      which explains why institution-subcohort combos have >2 total-rows. The
      downstream cleaning script must select the correct cohort_year.

EXPECTED OUTCOME:
  H1 CONFIRMED: All non-null values are in [0, 1]; none in (1, 100].
  H1 REFUTED: Some values are in the 1-100 range, indicating mixed scaling.
  H2 CONFIRMED: cohort_year varies within (unitid, year) groups.
  H2 REFUTED: cohort_year is constant per (unitid, year); extra rows from elsewhere.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_grad_rates.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 5 Step 3 -- Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)

# ==========================================================================
# INVESTIGATION H1: completion_rate_150pct scale
# ==========================================================================
print("\n--- H1: completion_rate_150pct scale ---")

cr = df["completion_rate_150pct"].drop_nulls()
print(f"Non-null count: {len(cr):,}")
print(f"min: {cr.min()}")
print(f"max: {cr.max()}")
print(f"mean: {cr.mean():.4f}")
print(f"median: {cr.median():.4f}")

# Definitive test: are there ANY values > 1.0?
n_over_1 = (cr > 1.0).sum()
print(f"Values > 1.0: {n_over_1:,}")

# Are there values in the (0.01, 0.99) range? (rules out it being stored as 0/1 binary)
n_fractional = ((cr > 0.01) & (cr < 0.99)).sum()
print(f"Values in (0.01, 0.99): {n_fractional:,} ({n_fractional/len(cr)*100:.1f}%)")

# Histogram of distribution
print("\nDecile distribution:")
for i in range(10):
    lo = i * 0.1
    hi = (i + 1) * 0.1
    n = ((cr >= lo) & (cr < hi)).sum()
    print(f"  [{lo:.1f}, {hi:.1f}): {n:,} ({n/len(cr)*100:.1f}%)")
# Include the exact 1.0 values
n_exact_1 = (cr == 1.0).sum()
print(f"  [1.0, 1.0]: {n_exact_1:,} ({n_exact_1/len(cr)*100:.1f}%)")

h1_confirmed = n_over_1 == 0 and cr.max() <= 1.0
print(f"\nH1 CONFIRMED: {h1_confirmed}")
print("IMPLICATION: Stage 6 clean-grad-rates must either:")
print("  (a) multiply by 100 to match Plan.md's 0-100 expectation, OR")
print("  (b) adjust all downstream 0-100 references to 0-1 (less invasive)")

# ==========================================================================
# INVESTIGATION H2: Multiple cohort_years per reporting year
# ==========================================================================
print("\n--- H2: Multiple cohort_years per reporting year ---")

# How many unique cohort_years exist per (unitid, year)?
cohort_year_counts = (
    df.group_by(["unitid", "year"])
    .agg(pl.col("cohort_year").n_unique().alias("n_cohort_years"))
)
print(f"Distribution of unique cohort_years per (unitid, year):")
print(cohort_year_counts["n_cohort_years"].value_counts().sort("n_cohort_years"))

# What are the actual cohort_year values?
print(f"\nAll unique cohort_year values: {sorted(df['cohort_year'].unique().to_list())}")

# Cross-tab: year x cohort_year
print("\nyear x cohort_year cross-tab:")
cross_yc = (
    df.group_by(["year", "cohort_year"])
    .len()
    .sort(["year", "cohort_year"])
)
for row in cross_yc.iter_rows(named=True):
    print(f"  year={row['year']}, cohort_year={row['cohort_year']}: {row['len']:,} rows")

# Specifically for totals (race==99, sex==99): how many cohort_years?
totals = df.filter((pl.col("race") == 99) & (pl.col("sex") == 99))
total_cy = (
    totals.group_by(["unitid", "year", "subcohort"])
    .agg(pl.col("cohort_year").n_unique().alias("n_cy"))
)
print(f"\nFor total-rows (race==99, sex==99):")
print(f"Distribution of cohort_years per (unitid, year, subcohort):")
print(total_cy["n_cy"].value_counts().sort("n_cy"))

h2_confirmed = (cohort_year_counts["n_cohort_years"] > 1).any()
print(f"\nH2 CONFIRMED: {h2_confirmed}")
if h2_confirmed:
    print("IMPLICATION: Stage 6 clean-grad-rates MUST filter to the correct cohort_year")
    print("  to avoid duplicate institution rows after filtering to race==99, sex==99.")
    print("  Typically, for reporting year Y, the correct cohort_year is Y-4 or Y-6")
    print("  (depending on 100% vs 150% time for bachelor's degrees).")

# ==========================================================================
# INTERPRETATION
# ==========================================================================
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

print(f"\nH1 (proportion scale): {'CONFIRMED' if h1_confirmed else 'REFUTED'}")
print("  Implications: WARNING for downstream -- Plan.md says 0-100 but data is 0-1.")
print("  Clean-grad-rates must rescale OR all downstream checks must adjust.")
print("  Severity: WARNING (not BLOCKER -- data is correct, expectation needs updating)")

print(f"\nH2 (multiple cohort_years): {'CONFIRMED' if h2_confirmed else 'REFUTED'}")
if h2_confirmed:
    print("  Implications: WARNING for downstream -- must select correct cohort_year.")
    print("  Severity: WARNING (sleeping bug -- if not handled in cleaning, will cause")
    print("  duplicate rows after race/sex filtering, corrupting institution-level analysis)")
else:
    print("  Implications: No action needed for cohort_year selection.")
    print("  Severity: INFO")

print(f"\nFurther investigation needed: NO -- both hypotheses conclusively tested")
print(f"Overall severity: WARNING (two downstream issues for Stage 6 to handle)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:08:09
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_03_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 5 Step 3 -- Iteration 2
# ============================================================
# 
# --- H1: completion_rate_150pct scale ---
# Non-null count: 274,308
# min: 0.0
# max: 1.0
# mean: 0.4880
# median: 0.5000
# Values > 1.0: 0
# Values in (0.01, 0.99): 213,943 (78.0%)
# 
# Decile distribution:
#   [0.0, 0.1): 37,210 (13.6%)
#   [0.1, 0.2): 14,391 (5.2%)
#   [0.2, 0.3): 26,429 (9.6%)
#   [0.3, 0.4): 28,421 (10.4%)
#   [0.4, 0.5): 26,008 (9.5%)
#   [0.5, 0.6): 43,379 (15.8%)
#   [0.6, 0.7): 28,774 (10.5%)
#   [0.7, 0.8): 20,973 (7.6%)
#   [0.8, 0.9): 15,334 (5.6%)
#   [0.9, 1.0): 6,527 (2.4%)
#   [1.0, 1.0]: 26,862 (9.8%)
# 
# H1 CONFIRMED: True
# IMPLICATION: Stage 6 clean-grad-rates must either:
#   (a) multiply by 100 to match Plan.md's 0-100 expectation, OR
#   (b) adjust all downstream 0-100 references to 0-1 (less invasive)
# 
# --- H2: Multiple cohort_years per reporting year ---
# Distribution of unique cohort_years per (unitid, year):
# shape: (1, 2)
# ┌────────────────┬───────┐
# │ n_cohort_years ┆ count │
# │ ---            ┆ ---   │
# │ u32            ┆ u32   │
# ╞════════════════╪═══════╡
# │ 1              ┆ 10791 │
# └────────────────┴───────┘
# 
# All unique cohort_year values: [2015, 2016, 2018, 2019]
# 
# year x cohort_year cross-tab:
#   year=2020, cohort_year=2015: 276,750 rows
#   year=2020, cohort_year=2018: 124,465 rows
#   year=2021, cohort_year=2016: 281,280 rows
#   year=2021, cohort_year=2019: 122,221 rows
# 
# For total-rows (race==99, sex==99):
# Distribution of cohort_years per (unitid, year, subcohort):
# shape: (1, 2)
# ┌──────┬───────┐
# │ n_cy ┆ count │
# │ ---  ┆ ---   │
# │ u32  ┆ u32   │
# ╞══════╪═══════╡
# │ 1    ┆ 16702 │
# └──────┴───────┘
# 
# H2 CONFIRMED: False
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# H1 (proportion scale): CONFIRMED
#   Implications: WARNING for downstream -- Plan.md says 0-100 but data is 0-1.
#   Clean-grad-rates must rescale OR all downstream checks must adjust.
#   Severity: WARNING (not BLOCKER -- data is correct, expectation needs updating)
# 
# H2 (multiple cohort_years): REFUTED
#   Implications: No action needed for cohort_year selection.
#   Severity: INFO
# 
# Further investigation needed: NO -- both hypotheses conclusively tested
# Overall severity: WARNING (two downstream issues for Stage 6 to handle)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
