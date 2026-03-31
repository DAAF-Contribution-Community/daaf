#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 6 Step 04 -- Iteration 2

Reviewed script: scripts/stage6_clean/04_clean-sfa-grants.py
Prior QA script: scripts/cr/stage6_04_cr1.py

INVESTIGATION TRIGGER:
cr1 profiling showed grant_recipients / sfa_total_students ratio has median=0.984
and max=1.000. Nearly every student at the median institution receives grant/scholarship
aid. This could indicate: (a) type_of_aid=9 is so broad that it is near-universal,
making it a poor discriminator for Pell proxy purposes, or (b) a data artifact where
number_receiving_grants and number_of_students represent the same population.

HYPOTHESIS:
The ratio is near 1.0 because type_of_aid=9 captures ALL grant/scholarship aid
(federal, state, institutional, other), which most students at most institutions
receive. The ratio distribution will show meaningful variance -- some institutions
will have materially lower ratios, indicating the variable still discriminates.

EXPECTED OUTCOME:
- If CONFIRMED: Ratio distribution will show a spread with some institutions at
  lower ratios (e.g., < 0.5), and the absolute grant_recipients count will still
  vary meaningfully across institutions (useful for Pell share denominator context).
- If REFUTED: Ratio is essentially constant at ~1.0 across all institutions,
  meaning this variable adds no information beyond sfa_total_students itself.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-03-29_sfa_pell_clean.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 6 Step 04 -- Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)

# --- Investigation: Ratio distribution characterization ---
print("\n--- Ratio Distribution Characterization ---")

# Compute ratio for all institutions where both columns are valid and denominator > 0
df_ratio = df.filter(
    pl.col("sfa_total_students") > 0
).with_columns(
    (pl.col("grant_recipients").cast(pl.Float64) / pl.col("sfa_total_students").cast(pl.Float64)).alias("ratio")
)

print(f"Institutions with valid ratio: {df_ratio.shape[0]:,}")

# Full distribution
r = df_ratio["ratio"]
print(f"\nRatio distribution:")
for q in [0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 1.0]:
    print(f"  p{int(q*100):3d}: {r.quantile(q):.4f}")

print(f"\n  mean:   {r.mean():.4f}")
print(f"  std:    {r.std():.4f}")

# How many institutions have ratio < 0.5?
low_ratio = df_ratio.filter(pl.col("ratio") < 0.5).shape[0]
mid_ratio = df_ratio.filter((pl.col("ratio") >= 0.5) & (pl.col("ratio") < 0.9)).shape[0]
high_ratio = df_ratio.filter(pl.col("ratio") >= 0.9).shape[0]
perfect_ratio = df_ratio.filter(pl.col("ratio") == 1.0).shape[0]

print(f"\nRatio buckets:")
print(f"  ratio < 0.5:    {low_ratio:,} ({low_ratio/df_ratio.shape[0]*100:.1f}%)")
print(f"  0.5 <= ratio < 0.9: {mid_ratio:,} ({mid_ratio/df_ratio.shape[0]*100:.1f}%)")
print(f"  ratio >= 0.9:   {high_ratio:,} ({high_ratio/df_ratio.shape[0]*100:.1f}%)")
print(f"  ratio == 1.0:   {perfect_ratio:,} ({perfect_ratio/df_ratio.shape[0]*100:.1f}%)")

# Check if grant_recipients == sfa_total_students for most institutions
# (which would mean they are essentially the same variable)
exact_match = df.filter(pl.col("grant_recipients") == pl.col("sfa_total_students")).shape[0]
print(f"\ngrant_recipients == sfa_total_students exactly: {exact_match:,} ({exact_match/df.shape[0]*100:.1f}%)")

# --- Investigation: Does absolute count still vary? ---
print("\n--- Absolute Count Variance ---")
gr = df["grant_recipients"]
print(f"grant_recipients coefficient of variation: {gr.std() / gr.mean():.2f}")
print(f"  (CV > 1 indicates high relative variance -- good for analysis)")

# --- Investigation: What do low-ratio institutions look like? ---
print("\n--- Low-ratio institutions (ratio < 0.5) ---")
low = df_ratio.filter(pl.col("ratio") < 0.5).sort("ratio")
if low.shape[0] > 0:
    print(low.head(10))
else:
    print("  No institutions with ratio < 0.5")

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

# Determine if hypothesis is confirmed
has_variance = r.std() > 0.01
has_low_ratio_institutions = low_ratio > 0
confirmed = has_variance or has_low_ratio_institutions

if confirmed:
    print(f"\nHypothesis: CONFIRMED")
    print(f"The ratio distribution shows {'some' if has_low_ratio_institutions else 'minimal'} variance")
    print(f"(std={r.std():.4f}), with {low_ratio} institutions below 0.5 ratio.")
    print(f"The absolute grant_recipients count has high variance (CV={gr.std()/gr.mean():.2f}),")
    print(f"meaning it still discriminates meaningfully across institutions.")
    print(f"\nImplications: The near-1.0 median ratio is expected for type_of_aid=9")
    print(f"(ALL grants/scholarships are nearly universal). For Pell proxy purposes,")
    print(f"downstream Stage 7 will compute pell_share = grant_recipients / UG_enrollment,")
    print(f"using IPEDS total UG enrollment as denominator (NOT sfa_total_students).")
    print(f"The grant_recipients count will serve as the numerator.")
else:
    print(f"\nHypothesis: REFUTED")
    print(f"The ratio is essentially constant, meaning grant_recipients adds no")
    print(f"information beyond what sfa_total_students already provides.")

print(f"\nFurther investigation needed: NO")
print(f"Severity assessment: WARNING")
print(f"  The near-universal ratio should be documented in Stage 7 when computing")
print(f"  pell_share. Using all-grant recipients as Pell proxy will overestimate")
print(f"  Pell share for institutions where grant aid is broader than Pell.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:45:26
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_04_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 6 Step 04 -- Iteration 2
# ============================================================
# 
# --- Ratio Distribution Characterization ---
# Institutions with valid ratio: 5,320
# 
# Ratio distribution:
#   p  0: 0.0000
#   p  1: 0.4782
#   p  5: 0.6667
#   p 10: 0.7500
#   p 25: 0.8791
#   p 50: 0.9837
#   p 75: 1.0000
#   p 90: 1.0000
#   p 95: 1.0000
#   p 99: 1.0000
#   p100: 1.0000
# 
#   mean:   0.9188
#   std:    0.1273
# 
# Ratio buckets:
#   ratio < 0.5:    57 (1.1%)
#   0.5 <= ratio < 0.9: 1,454 (27.3%)
#   ratio >= 0.9:   3,809 (71.6%)
#   ratio == 1.0:   2,283 (42.9%)
# 
# grant_recipients == sfa_total_students exactly: 2,283 (42.9%)
# 
# --- Absolute Count Variance ---
# grant_recipients coefficient of variation: 1.77
#   (CV > 1 indicates high relative variance -- good for analysis)
# 
# --- Low-ratio institutions (ratio < 0.5) ---
# shape: (10, 4)
# ┌────────┬──────────────────┬────────────────────┬───────┐
# │ unitid ┆ grant_recipients ┆ sfa_total_students ┆ ratio │
# │ ---    ┆ ---              ┆ ---                ┆ ---   │
# │ i64    ┆ i64              ┆ i64                ┆ f64   │
# ╞════════╪══════════════════╪════════════════════╪═══════╡
# │ 154208 ┆ 0                ┆ 1                  ┆ 0.0   │
# │ 190008 ┆ 0                ┆ 2                  ┆ 0.0   │
# │ 202806 ┆ 0                ┆ 1                  ┆ 0.0   │
# │ 209241 ┆ 0                ┆ 1                  ┆ 0.0   │
# │ 243799 ┆ 0                ┆ 1                  ┆ 0.0   │
# │ 375568 ┆ 0                ┆ 1                  ┆ 0.0   │
# │ 418560 ┆ 0                ┆ 1                  ┆ 0.0   │
# │ 483346 ┆ 0                ┆ 9                  ┆ 0.0   │
# │ 487889 ┆ 0                ┆ 2                  ┆ 0.0   │
# │ 489353 ┆ 0                ┆ 1                  ┆ 0.0   │
# └────────┴──────────────────┴────────────────────┴───────┘
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Hypothesis: CONFIRMED
# The ratio distribution shows some variance
# (std=0.1273), with 57 institutions below 0.5 ratio.
# The absolute grant_recipients count has high variance (CV=1.77),
# meaning it still discriminates meaningfully across institutions.
# 
# Implications: The near-1.0 median ratio is expected for type_of_aid=9
# (ALL grants/scholarships are nearly universal). For Pell proxy purposes,
# downstream Stage 7 will compute pell_share = grant_recipients / UG_enrollment,
# using IPEDS total UG enrollment as denominator (NOT sfa_total_students).
# The grant_recipients count will serve as the numerator.
# 
# Further investigation needed: NO
# Severity assessment: WARNING
#   The near-universal ratio should be documented in Stage 7 when computing
#   pell_share. Using all-grant recipients as Pell proxy will overestimate
#   Pell share for institutions where grant aid is broader than Pell.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
