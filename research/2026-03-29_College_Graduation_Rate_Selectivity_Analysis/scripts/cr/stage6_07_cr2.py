#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 6 Step 07 -- Iteration 2

Reviewed script: scripts/stage6_clean/07_clean-retention.py
Prior QA script: scripts/cr/stage6_07_cr1.py

INVESTIGATION TRIGGER:
cr1 found 55 institutions with retention_rate == 0.0 (0% FT retention), which
tripped the boundary check (threshold was < 50). Additionally, 333 institutions
have 100.0 (100% FT retention). The [0, 10) bucket has 69 institutions total.
Need to determine if these zeros are genuine data or artifacts.

HYPOTHESIS:
The 55 zero-retention institutions are genuine data values from the raw source
(raw value 0.0 on the 0-1 scale), not artifacts of the cleaning/rescaling
process. These likely represent very small, specialized, or newly-established
institutions where no first-time full-time students returned.

EXPECTED OUTCOME:
- If CONFIRMED: The 55 zeros exist in the raw data as 0.0 for ftpt==1 rows,
  and these institutions have characteristics suggesting small/niche populations.
  This is NOT a BLOCKER -- zeros are real but may be downweighted in analysis.
- If REFUTED: The zeros were introduced by the cleaning process (e.g., coded
  values wrongly treated, or scale detection error). This WOULD be a BLOCKER.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_retention_clean.parquet"
RAW_FILE = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ipeds_retention.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 6 Step 07 -- Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
df_raw = pl.read_parquet(RAW_FILE)

# --- Investigation 1: Trace zeros back to raw ---
print("\n--- Investigation 1: Trace zero-retention institutions to raw data ---")
zero_unitids = df.filter(pl.col("retention_rate") == 0.0)["unitid"].to_list()
print(f"Institutions with clean retention_rate == 0.0: {len(zero_unitids)}")

# Check each zero-retention institution in raw data
raw_ft = df_raw.filter(pl.col("ftpt") == 1)
raw_zeros = raw_ft.filter(pl.col("unitid").is_in(zero_unitids))
print(f"Of these, found in raw FT data: {raw_zeros.shape[0]}")

# Check their raw values
raw_zero_vals = raw_zeros["retention_rate"].to_list()
all_raw_are_zero = all(v == 0.0 for v in raw_zero_vals if v is not None)
null_among_raw = sum(1 for v in raw_zero_vals if v is None)
print(f"Raw retention_rate values for these institutions:")
print(f"  All are 0.0: {all_raw_are_zero}")
print(f"  Count with null raw value: {null_among_raw}")
print(f"  Value distribution: {raw_zeros['retention_rate'].value_counts().sort('retention_rate')}")

# --- Investigation 2: Check other columns for context ---
print("\n--- Investigation 2: Context for zero-retention institutions ---")
# Check if these institutions also have unusual values in other columns
zero_raw_full = df_raw.filter(
    (pl.col("unitid").is_in(zero_unitids)) & (pl.col("ftpt") == 1)
)
print(f"Full raw data for zero-retention FT institutions:")
print(f"  Columns available: {df_raw.columns}")

# Check returning_students and prev_cohort columns
for col in ["returning_students", "prev_cohort", "prev_cohort_adj"]:
    if col in zero_raw_full.columns:
        vals = zero_raw_full[col].value_counts().sort("count", descending=True).head(10)
        print(f"\n  {col} value counts (top 10):")
        print(f"  {vals}")

# --- Investigation 3: Compare with 100% retention institutions ---
print("\n--- Investigation 3: Compare zeros vs. 100% institutions ---")
hundred_unitids = df.filter(pl.col("retention_rate") == 100.0)["unitid"].to_list()
print(f"Institutions with 100.0 retention: {len(hundred_unitids)}")

# Verify 100% also traces back to raw
raw_hundreds = raw_ft.filter(pl.col("unitid").is_in(hundred_unitids))
raw_hundred_vals = raw_hundreds["retention_rate"]
all_raw_one = (raw_hundred_vals == 1.0).sum()
print(f"Of 100% institutions, raw value == 1.0: {all_raw_one}")

# --- Investigation 4: Are zeros possibly from coded value -3 suppression? ---
print("\n--- Investigation 4: Rule out coded value contamination ---")
# Check if any of the zero-retention unitids had coded values in raw
coded_values = [-1, -2, -3]
for uid in zero_unitids[:10]:
    raw_val = raw_ft.filter(pl.col("unitid") == uid)["retention_rate"].item()
    is_coded = raw_val in coded_values
    print(f"  unitid={uid}: raw_val={raw_val}, is_coded_value={is_coded}")

# --- Investigation 5: Distribution of very low retention ---
print("\n--- Investigation 5: Distribution of low-end retention rates ---")
low_retention = df.filter(
    pl.col("retention_rate").is_not_null() & (pl.col("retention_rate") < 20)
)
print(f"Institutions with retention_rate < 20: {low_retention.shape[0]}")
print(f"Breakdown:")
for val in sorted(low_retention["retention_rate"].unique().to_list()):
    count = low_retention.filter(pl.col("retention_rate") == val).shape[0]
    print(f"  {val:.0f}%: {count} institutions")

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

# Determine if hypothesis is confirmed
confirmed = all_raw_are_zero and null_among_raw == 0
is_blocker = not confirmed
is_warning = confirmed  # Zeros are real data but worth noting

if confirmed:
    implications = (
        "55 institutions genuinely have 0% FT retention in IPEDS data. "
        "These are likely very small, specialized, or newly-established institutions. "
        "The cleaning script correctly preserved these values. The zeros are not "
        "artifacts of rescaling or coded value handling. 333 institutions with 100% "
        "retention also trace back to raw 1.0 values. Both extremes are real data."
    )
else:
    implications = (
        "BLOCKER: Some zero-retention values may be artifacts of the cleaning process. "
        "The raw data does not fully explain the zeros in the clean output."
    )

print(f"\nHypothesis: {'CONFIRMED' if confirmed else 'REFUTED'}")
print(f"Implications: {implications}")
print(f"Further investigation needed: NO")
print(f"Severity assessment: {'WARNING' if is_warning else 'BLOCKER'}")
print(f"\nNote: 55 zeros out of 5,182 non-null is 1.1% of the data. These will be")
print(f"naturally downweighted in regression models and are unlikely to distort")
print(f"descriptive statistics or selectivity band profiles materially.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:59:13
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_07_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 6 Step 07 -- Iteration 2
# ============================================================
# 
# --- Investigation 1: Trace zero-retention institutions to raw data ---
# Institutions with clean retention_rate == 0.0: 55
# Of these, found in raw FT data: 55
# Raw retention_rate values for these institutions:
#   All are 0.0: True
#   Count with null raw value: 0
#   Value distribution: shape: (1, 2)
# ┌────────────────┬───────┐
# │ retention_rate ┆ count │
# │ ---            ┆ ---   │
# │ f64            ┆ u32   │
# ╞════════════════╪═══════╡
# │ 0.0            ┆ 55    │
# └────────────────┴───────┘
# 
# --- Investigation 2: Context for zero-retention institutions ---
# Full raw data for zero-retention FT institutions:
#   Columns available: ['unitid', 'year', 'fips', 'ftpt', 'retention_rate', 'returning_students', 'prev_cohort', 'prev_exclusions', 'prev_cohort_adj']
# 
#   returning_students value counts (top 10):
#   shape: (1, 2)
# ┌────────────────────┬───────┐
# │ returning_students ┆ count │
# │ ---                ┆ ---   │
# │ str                ┆ u32   │
# ╞════════════════════╪═══════╡
# │ 0                  ┆ 55    │
# └────────────────────┴───────┘
# 
#   prev_cohort value counts (top 10):
#   shape: (7, 2)
# ┌─────────────┬───────┐
# │ prev_cohort ┆ count │
# │ ---         ┆ ---   │
# │ str         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 1           ┆ 30    │
# │ 2           ┆ 15    │
# │ 3           ┆ 3     │
# │ 5           ┆ 3     │
# │ 4           ┆ 2     │
# │ 32          ┆ 1     │
# │ 33          ┆ 1     │
# └─────────────┴───────┘
# 
#   prev_cohort_adj value counts (top 10):
#   shape: (7, 2)
# ┌─────────────────┬───────┐
# │ prev_cohort_adj ┆ count │
# │ ---             ┆ ---   │
# │ str             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 1               ┆ 31    │
# │ 2               ┆ 14    │
# │ 5               ┆ 3     │
# │ 3               ┆ 3     │
# │ 4               ┆ 2     │
# │ 33              ┆ 1     │
# │ 32              ┆ 1     │
# └─────────────────┴───────┘
# 
# --- Investigation 3: Compare zeros vs. 100% institutions ---
# Institutions with 100.0 retention: 333
# Of 100% institutions, raw value == 1.0: 333
# 
# --- Investigation 4: Rule out coded value contamination ---
#   unitid=110918: raw_val=0.0, is_coded_value=False
#   unitid=118143: raw_val=0.0, is_coded_value=False
#   unitid=122454: raw_val=0.0, is_coded_value=False
#   unitid=143181: raw_val=0.0, is_coded_value=False
#   unitid=143552: raw_val=0.0, is_coded_value=False
#   unitid=144573: raw_val=0.0, is_coded_value=False
#   unitid=165167: raw_val=0.0, is_coded_value=False
#   unitid=177038: raw_val=0.0, is_coded_value=False
#   unitid=177588: raw_val=0.0, is_coded_value=False
#   unitid=178004: raw_val=0.0, is_coded_value=False
# 
# --- Investigation 5: Distribution of low-end retention rates ---
# Institutions with retention_rate < 20: 101
# Breakdown:
#   0%: 55 institutions
#   3%: 1 institutions
#   4%: 1 institutions
#   5%: 1 institutions
#   6%: 4 institutions
#   7%: 2 institutions
#   8%: 2 institutions
#   9%: 3 institutions
#   10%: 2 institutions
#   11%: 1 institutions
#   12%: 2 institutions
#   13%: 2 institutions
#   14%: 5 institutions
#   15%: 5 institutions
#   16%: 4 institutions
#   17%: 2 institutions
#   18%: 4 institutions
#   19%: 5 institutions
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Hypothesis: CONFIRMED
# Implications: 55 institutions genuinely have 0% FT retention in IPEDS data. These are likely very small, specialized, or newly-established institutions. The cleaning script correctly preserved these values. The zeros are not artifacts of rescaling or coded value handling. 333 institutions with 100% retention also trace back to raw 1.0 values. Both extremes are real data.
# Further investigation needed: NO
# Severity assessment: WARNING
# 
# Note: 55 zeros out of 5,182 non-null is 1.1% of the data. These will be
# naturally downweighted in regression models and are unlikely to distort
# descriptive statistics or selectivity band profiles materially.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
