#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 5 Step 01 -- Iteration 2

Reviewed script: scripts/stage5_fetch/01_fetch-directory.py
Prior QA script: scripts/cr/stage5_01_cr1.py

INVESTIGATION TRIGGER:
cr1 profiling revealed that open_public has 12,725 rows with value 1 and only 4 rows
with value 0. Plan.md describes open_public as an "open admissions indicator" that
identifies institutions using no admissions criteria. If 99.97% of institutions are
"open public," this would mean nearly ALL institutions are open-admissions, which
contradicts the Plan's expectation of distinct selectivity bands. This value
distribution needs investigation to determine whether open_public==1 means "yes, open
admissions" or something else (e.g., "yes, institution is open/active" or binary is
reversed from expectation).

HYPOTHESIS:
open_public==1 does NOT mean "open admissions." Instead, it likely means "institution
is open to the public" (i.e., publicly accessible/enrolling, as opposed to closed).
The actual open-admissions variable may need to be interpreted differently, or there
may be a separate coding scheme. If open_public==1 meant "open admissions," then the
Plan's selectivity band assignment ("Open/Less Selective" for open_public==1) would
incorrectly classify nearly all institutions as open-admissions.

EXPECTED OUTCOME:
- If CONFIRMED (open_public != open admissions): Institutions known to be selective
  (e.g., MIT, Harvard, Stanford) will have open_public==1, proving it does NOT mean
  open admissions. This would be a WARNING for downstream methodology.
- If REFUTED (open_public == open admissions): Selective institutions will have
  open_public==0, confirming 1 means open admissions and the 99.97% rate is just the
  data including all institution types (most are non-selective).
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_directory.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 5 Step 01 -- Iteration 2")
print("open_public value interpretation")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)

# --- Investigation: Check known selective institutions ---
# INTENT: Use well-known highly selective institutions as test cases.
# If MIT, Harvard, Stanford have open_public==1, then open_public does NOT mean
# "open admissions" (these institutions have <10% admission rates).

known_selective = {
    166027: "MIT",
    166683: "Harvard University",
    243744: "Stanford University",
    130794: "Yale University",
    110635: "UC Berkeley",
    186131: "Princeton University",
}

print("\n--- Known Selective Institutions: open_public values ---")
for uid, name in known_selective.items():
    rows = df.filter((pl.col("unitid") == uid) & (pl.col("year") == 2020))
    if len(rows) > 0:
        op_val = rows["open_public"][0]
        inst_name = rows["inst_name"][0]
        print(f"  {inst_name} (unitid={uid}): open_public={op_val}")
    else:
        print(f"  {name} (unitid={uid}): NOT FOUND in 2020 data")

# --- Investigation: Check the 4 institutions with open_public==0 ---
print("\n--- Institutions with open_public==0 ---")
closed = df.filter(pl.col("open_public") == 0)
print(f"Count: {len(closed)}")
print(closed.select("unitid", "year", "inst_name", "inst_control", "institution_level",
                      "degree_granting", "open_public"))

# --- Investigation: Look at open_public by institution_level ---
print("\n--- open_public distribution by institution_level (2020 only) ---")
cross = (
    df.filter(pl.col("year") == 2020)
    .group_by("institution_level", "open_public")
    .len()
    .sort("institution_level", "open_public")
)
print(cross)

# --- Investigation: Check the IPEDS skill for open_public definition ---
# REASONING: Plan.md Stage 3 says "open_public variable identifies institutions
# that don't use admissions criteria." But the actual data coding might differ.
# Let's examine the 4-year institutions specifically.
print("\n--- open_public among 4-yr degree-granting institutions (2020) ---")
four_yr = df.filter(
    (pl.col("institution_level") == 4)
    & (pl.col("degree_granting") == 1)
    & (pl.col("year") == 2020)
)
op_dist = four_yr["open_public"].value_counts().sort("open_public")
print(f"Total 4-yr degree-granting: {len(four_yr):,}")
print(op_dist)

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

# Check if selective institutions have open_public==1
selective_check = df.filter(
    (pl.col("unitid").is_in(list(known_selective.keys())))
    & (pl.col("year") == 2020)
)
all_selective_have_1 = (selective_check["open_public"] == 1).all()

if all_selective_have_1:
    confirmed = True
    implications = (
        "open_public==1 means 'open to the public' (institution is operating/enrolling), "
        "NOT 'open admissions.' All known highly selective institutions have open_public==1. "
        "The Plan.md states 'open_public variable identifies institutions that don't use admissions criteria' "
        "-- this interpretation appears INCORRECT based on the data. The clean-directory script "
        "(Stage 6, Task 3.1) uses open_public in band assignment. This needs verification "
        "before band assignment in Task 6.2 (create-bands). If open_public==1 just means "
        "'institution is open/operating,' then using it to assign 'Open/Less Selective' band "
        "would incorrectly classify nearly all institutions."
    )
    is_blocker = False
    is_warning = True
    needs_more = False
    print(f"\nHypothesis: CONFIRMED")
    print(f"Known selective institutions (MIT, Harvard, Stanford, etc.) all have open_public==1.")
    print(f"\nImplications: {implications}")
    print(f"\nFurther investigation needed: NO -- the evidence is clear.")
    print(f"Severity assessment: WARNING")
    print(f"\nNOTE: This is a WARNING, not a BLOCKER for the fetch script because:")
    print(f"  1. The fetch script correctly downloaded the data as-is")
    print(f"  2. The variable interpretation issue affects Stage 6-7 (cleaning/transform)")
    print(f"  3. Plan.md Task 6.2 create-bands handles open_public assignment")
    print(f"  4. The clean-directory script should verify open_public semantics")
    print(f"\nHowever, the IPEDS documentation should be rechecked. It is possible that")
    print(f"open_public has changed meaning or that the 0/1 coding in this dataset version")
    print(f"differs from what the IPEDS skill documents. The 4 institutions with open_public==0")
    print(f"may be institutions that are NOT open to the public (e.g., military academies,")
    print(f"corporate training centers).")
else:
    confirmed = False
    implications = "Selective institutions do NOT all have open_public==1, so the variable may correctly indicate open admissions."
    is_blocker = False
    is_warning = False
    needs_more = True
    print(f"\nHypothesis: REFUTED")
    print(f"Implications: {implications}")
    print(f"Further investigation needed: YES -- check actual distribution more carefully")
    print(f"Severity assessment: INFO")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:08:02
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_01_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 5 Step 01 -- Iteration 2
# open_public value interpretation
# ============================================================
# 
# --- Known Selective Institutions: open_public values ---
#   Harvard University (unitid=166027): open_public=1
#   Massachusetts Institute of Technology (unitid=166683): open_public=1
#   Stanford University (unitid=243744): open_public=1
#   Yale University (unitid=130794): open_public=1
#   University of California-Berkeley (unitid=110635): open_public=1
#   Princeton University (unitid=186131): open_public=1
# 
# --- Institutions with open_public==0 ---
# Count: 4
# shape: (4, 7)
# ┌────────┬──────┬──────────────┬──────────────┬────────────────────┬─────────────────┬─────────────┐
# │ unitid ┆ year ┆ inst_name    ┆ inst_control ┆ institution_level  ┆ degree_granting ┆ open_public │
# │ ---    ┆ ---  ┆ ---          ┆ ---          ┆ ---                ┆ ---             ┆ ---         │
# │ i64    ┆ i64  ┆ str          ┆ i64          ┆ i64                ┆ i64             ┆ i64         │
# ╞════════╪══════╪══════════════╪══════════════╪════════════════════╪═════════════════╪═════════════╡
# │ 119678 ┆ 2020 ┆ Naval        ┆ 1            ┆ 4                  ┆ 1               ┆ 0           │
# │        ┆      ┆ Postgraduate ┆              ┆                    ┆                 ┆             │
# │        ┆      ┆ School       ┆              ┆                    ┆                 ┆             │
# │ 119678 ┆ 2021 ┆ Naval        ┆ 1            ┆ 4                  ┆ 1               ┆ 0           │
# │        ┆      ┆ Postgraduate ┆              ┆                    ┆                 ┆             │
# │        ┆      ┆ School       ┆              ┆                    ┆                 ┆             │
# │ 200697 ┆ 2020 ┆ Air Force    ┆ 1            ┆ 4                  ┆ 1               ┆ 0           │
# │        ┆      ┆ Institute of ┆              ┆                    ┆                 ┆             │
# │        ┆      ┆ Technol…     ┆              ┆                    ┆                 ┆             │
# │ 200697 ┆ 2021 ┆ Air Force    ┆ 1            ┆ 4                  ┆ 1               ┆ 0           │
# │        ┆      ┆ Institute of ┆              ┆                    ┆                 ┆             │
# │        ┆      ┆ Technol…     ┆              ┆                    ┆                 ┆             │
# └────────┴──────┴──────────────┴──────────────┴────────────────────┴─────────────────┴─────────────┘
# 
# --- open_public distribution by institution_level (2020 only) ---
# shape: (5, 3)
# ┌───────────────────┬─────────────┬──────┐
# │ institution_level ┆ open_public ┆ len  │
# │ ---               ┆ ---         ┆ ---  │
# │ i64               ┆ i64         ┆ u32  │
# ╞═══════════════════╪═════════════╪══════╡
# │ -1                ┆ 1           ┆ 52   │
# │ 1                 ┆ 1           ┆ 1805 │
# │ 2                 ┆ 1           ┆ 1685 │
# │ 4                 ┆ 0           ┆ 2    │
# │ 4                 ┆ 1           ┆ 2896 │
# └───────────────────┴─────────────┴──────┘
# 
# --- open_public among 4-yr degree-granting institutions (2020) ---
# Total 4-yr degree-granting: 2,893
# shape: (2, 2)
# ┌─────────────┬───────┐
# │ open_public ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 0           ┆ 2     │
# │ 1           ┆ 2891  │
# └─────────────┴───────┘
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Hypothesis: CONFIRMED
# Known selective institutions (MIT, Harvard, Stanford, etc.) all have open_public==1.
# 
# Implications: open_public==1 means 'open to the public' (institution is operating/enrolling), NOT 'open admissions.' All known highly selective institutions have open_public==1. The Plan.md states 'open_public variable identifies institutions that don't use admissions criteria' -- this interpretation appears INCORRECT based on the data. The clean-directory script (Stage 6, Task 3.1) uses open_public in band assignment. This needs verification before band assignment in Task 6.2 (create-bands). If open_public==1 just means 'institution is open/operating,' then using it to assign 'Open/Less Selective' band would incorrectly classify nearly all institutions.
# 
# Further investigation needed: NO -- the evidence is clear.
# Severity assessment: WARNING
# 
# NOTE: This is a WARNING, not a BLOCKER for the fetch script because:
#   1. The fetch script correctly downloaded the data as-is
#   2. The variable interpretation issue affects Stage 6-7 (cleaning/transform)
#   3. Plan.md Task 6.2 create-bands handles open_public assignment
#   4. The clean-directory script should verify open_public semantics
# 
# However, the IPEDS documentation should be rechecked. It is possible that
# open_public has changed meaning or that the 0/1 coding in this dataset version
# differs from what the IPEDS skill documents. The 4 institutions with open_public==0
# may be institutions that are NOT open to the public (e.g., military academies,
# corporate training centers).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
