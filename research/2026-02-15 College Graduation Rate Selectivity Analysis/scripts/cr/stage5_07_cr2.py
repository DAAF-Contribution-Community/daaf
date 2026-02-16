#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 5 Step 7 — Iteration 2

Reviewed script: scripts/stage5_fetch/07_fetch-retention.py
Prior QA script: scripts/cr/stage5_07_cr1.py

INVESTIGATION TRIGGER:
Harvard (unitid=166027) shows retention_rate=0.76, but Harvard's actual
first-year retention rate is consistently ~97%. This 21-percentage-point
discrepancy is too large to be a normal fluctuation. Either:
  (a) The retention_rate column means something different than expected, or
  (b) The data for highly selective institutions is wrong, or
  (c) COVID-related effects on the 2020 reporting year caused anomalous values.

HYPOTHESIS:
The retention_rate=0.76 for Harvard is a legitimate value in the dataset —
meaning the "retention_rate" variable in this IPEDS mirror may represent
something different than the commonly understood first-year retention rate,
OR the value IS the correct IPEDS value and our external expectation (~0.97)
is based on a different definition or reporting period.

EXPECTED OUTCOME:
- If CONFIRMED (data is wrong or means something different): Other highly
  selective institutions would also show unexpectedly low values. This would
  be a systemic issue.
- If REFUTED (Harvard is an outlier): Other highly selective institutions
  (MIT, Stanford, Yale) would show values near 0.95-0.99. Harvard at 0.76
  would be a genuine COVID/one-off anomaly.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_retention.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 5 Step 7 — Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)

# --- Investigation ---

# Check a set of well-known highly selective institutions
# These all have well-documented retention rates above 95%
known_selective = {
    166027: ("Harvard University", 0.97),
    166683: ("MIT", 0.98),
    243744: ("Stanford University", 0.98),
    130794: ("Yale University", 0.98),
    186131: ("Princeton University", 0.98),
    110404: ("Caltech", 0.98),
    215062: ("University of Pennsylvania", 0.96),
    144050: ("University of Chicago", 0.98),
    147767: ("Northwestern University", 0.97),
    190150: ("Columbia University", 0.97),
}

print("\nHighly selective institution retention rates:")
print(f"{'unitid':<10} {'Name':<35} {'Data Value':<12} {'Expected':<10} {'Match?'}")
print("-" * 80)

matches = 0
mismatches = 0
for uid, (name, expected) in known_selective.items():
    row = df.filter(pl.col("unitid") == uid)
    if row.shape[0] == 1:
        actual = row["retention_rate"][0]
        if actual is not None:
            match = abs(actual - expected) < 0.05  # within 5 percentage points
            status = "OK" if match else f"MISMATCH (diff={actual - expected:+.2f})"
            if match:
                matches += 1
            else:
                mismatches += 1
            print(f"{uid:<10} {name:<35} {actual:<12.2f} {expected:<10.2f} {status}")
        else:
            print(f"{uid:<10} {name:<35} {'null':<12} {expected:<10.2f} NULL")
    else:
        print(f"{uid:<10} {name:<35} {'not found':<12} {expected:<10.2f} MISSING")

print(f"\nResults: {matches} match, {mismatches} mismatch out of {len(known_selective)}")

# Also check some well-known open-access institutions for comparison
# Community colleges typically have 55-65% retention
open_access = {
    100654: "Alabama A&M University",
    131520: "University of Bridgeport",
}
print(f"\nOpen-access institution retention rates (for comparison):")
for uid, name in open_access.items():
    row = df.filter(pl.col("unitid") == uid)
    if row.shape[0] == 1:
        actual = row["retention_rate"][0]
        print(f"  {uid} ({name}): {actual}")

# Check the full raw data from the mirror to see if Harvard's retention_rate
# is different in the unfiltered dataset. Load from same mirror.
print("\n\nChecking original (unfiltered) mirror data for Harvard...")
try:
    url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ipeds/colleges_ipeds_fall-retention.parquet"
    df_full = pl.read_parquet(url)
    harvard_full = df_full.filter(
        (pl.col("unitid") == 166027) & (pl.col("year") == 2020)
    )
    print(f"Harvard rows in full mirror data (year=2020):")
    print(harvard_full)

    # Show all ftpt values for Harvard in 2020
    print(f"\nAll Harvard retention entries for year 2020:")
    harvard_all_ftpt = df_full.filter(
        (pl.col("unitid") == 166027) & (pl.col("year") == 2020)
    )
    print(harvard_all_ftpt)

    # Also check Harvard across multiple recent years to see trend
    print(f"\nHarvard retention_rate (ftpt=1) across years:")
    harvard_trend = (
        df_full.filter(
            (pl.col("unitid") == 166027) & (pl.col("ftpt") == 1)
        )
        .sort("year")
        .select(["year", "retention_rate"])
    )
    print(harvard_trend.tail(10))

except Exception as e:
    print(f"Could not load full mirror data: {e}")

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

# Determine confirmation status based on results
if mismatches > 3:
    confirmed = True
    implications = (
        "SYSTEMIC: Multiple highly selective institutions show unexpectedly low "
        "retention_rate values. This suggests the variable may measure something "
        "different than expected, or the 2020 data has a COVID-related anomaly."
    )
    needs_more = True
    is_blocker = False  # Not a fetch script issue; data is what the mirror provides
    is_warning = True
else:
    confirmed = False
    implications = (
        "Harvard's low value appears to be isolated or explained by the mirror's data. "
        "Most other selective institutions show expected retention rates. "
        "The value may reflect the Education Data Portal's specific calculation methodology."
    )
    needs_more = False
    is_blocker = False
    is_warning = False

print(f"\nHypothesis: {'CONFIRMED' if confirmed else 'REFUTED'}")
print(f"Implications: {implications}")
print(f"Further investigation needed: {'YES — characterize the variable definition' if needs_more else 'NO'}")
print(f"Severity assessment: {'BLOCKER' if is_blocker else 'WARNING' if is_warning else 'INFO'}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:30:18
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_07_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 5 Step 7 — Iteration 2
# ============================================================
# 
# Highly selective institution retention rates:
# unitid     Name                                Data Value   Expected   Match?
# --------------------------------------------------------------------------------
# 166027     Harvard University                  0.76         0.97       MISMATCH (diff=-0.21)
# 166683     MIT                                 0.98         0.98       OK
# 243744     Stanford University                 0.86         0.98       MISMATCH (diff=-0.12)
# 130794     Yale University                     0.65         0.98       MISMATCH (diff=-0.33)
# 186131     Princeton University                0.83         0.98       MISMATCH (diff=-0.15)
# 110404     Caltech                             0.94         0.98       OK
# 215062     University of Pennsylvania          0.95         0.96       OK
# 144050     University of Chicago               1.00         0.98       OK
# 147767     Northwestern University             0.97         0.97       OK
# 190150     Columbia University                 0.95         0.97       OK
# 
# Results: 6 match, 4 mismatch out of 10
# 
# Open-access institution retention rates (for comparison):
#   100654 (Alabama A&M University): 0.54
#   131520 (University of Bridgeport): 0.9
# 
# 
# Checking original (unfiltered) mirror data for Harvard...
# Harvard rows in full mirror data (year=2020):
# shape: (3, 9)
# ┌────────┬──────┬──────┬──────┬───┬────────────────┬─────────────┬────────────────┬────────────────┐
# │ unitid ┆ year ┆ fips ┆ ftpt ┆ … ┆ returning_stud ┆ prev_cohort ┆ prev_exclusion ┆ prev_cohort_ad │
# │ ---    ┆ ---  ┆ ---  ┆ ---  ┆   ┆ ents           ┆ ---         ┆ s              ┆ j              │
# │ i64    ┆ i64  ┆ i64  ┆ i64  ┆   ┆ ---            ┆ str         ┆ ---            ┆ ---            │
# │        ┆      ┆      ┆      ┆   ┆ str            ┆             ┆ str            ┆ str            │
# ╞════════╪══════╪══════╪══════╪═══╪════════════════╪═════════════╪════════════════╪════════════════╡
# │ 166027 ┆ 2020 ┆ 25   ┆ 1    ┆ … ┆ 1244           ┆ 1644        ┆ 0              ┆ 1644           │
# │ 166027 ┆ 2020 ┆ 25   ┆ 2    ┆ … ┆ 0              ┆ 0           ┆ 0              ┆ 0              │
# │ 166027 ┆ 2020 ┆ 25   ┆ 99   ┆ … ┆ 1244           ┆ 1644        ┆ 0              ┆ 1644           │
# └────────┴──────┴──────┴──────┴───┴────────────────┴─────────────┴────────────────┴────────────────┘
# 
# All Harvard retention entries for year 2020:
# shape: (3, 9)
# ┌────────┬──────┬──────┬──────┬───┬────────────────┬─────────────┬────────────────┬────────────────┐
# │ unitid ┆ year ┆ fips ┆ ftpt ┆ … ┆ returning_stud ┆ prev_cohort ┆ prev_exclusion ┆ prev_cohort_ad │
# │ ---    ┆ ---  ┆ ---  ┆ ---  ┆   ┆ ents           ┆ ---         ┆ s              ┆ j              │
# │ i64    ┆ i64  ┆ i64  ┆ i64  ┆   ┆ ---            ┆ str         ┆ ---            ┆ ---            │
# │        ┆      ┆      ┆      ┆   ┆ str            ┆             ┆ str            ┆ str            │
# ╞════════╪══════╪══════╪══════╪═══╪════════════════╪═════════════╪════════════════╪════════════════╡
# │ 166027 ┆ 2020 ┆ 25   ┆ 1    ┆ … ┆ 1244           ┆ 1644        ┆ 0              ┆ 1644           │
# │ 166027 ┆ 2020 ┆ 25   ┆ 2    ┆ … ┆ 0              ┆ 0           ┆ 0              ┆ 0              │
# │ 166027 ┆ 2020 ┆ 25   ┆ 99   ┆ … ┆ 1244           ┆ 1644        ┆ 0              ┆ 1644           │
# └────────┴──────┴──────┴──────┴───┴────────────────┴─────────────┴────────────────┴────────────────┘
# 
# Harvard retention_rate (ftpt=1) across years:
# shape: (10, 2)
# ┌──────┬────────────────┐
# │ year ┆ retention_rate │
# │ ---  ┆ ---            │
# │ i64  ┆ f64            │
# ╞══════╪════════════════╡
# │ 2011 ┆ 0.97           │
# │ 2012 ┆ 0.97           │
# │ 2013 ┆ 0.97           │
# │ 2014 ┆ 0.98           │
# │ 2015 ┆ 0.98           │
# │ 2016 ┆ 0.97           │
# │ 2017 ┆ 0.98           │
# │ 2018 ┆ 0.99           │
# │ 2019 ┆ 0.97           │
# │ 2020 ┆ 0.76           │
# └──────┴────────────────┘
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Hypothesis: CONFIRMED
# Implications: SYSTEMIC: Multiple highly selective institutions show unexpectedly low retention_rate values. This suggests the variable may measure something different than expected, or the 2020 data has a COVID-related anomaly.
# Further investigation needed: YES — characterize the variable definition
# Severity assessment: WARNING
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
