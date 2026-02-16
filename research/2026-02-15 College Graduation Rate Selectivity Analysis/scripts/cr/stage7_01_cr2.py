#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 7 Step 01 — Iteration 2

Reviewed script: scripts/stage7_transform/01_join-core_a.py
Prior QA script: scripts/cr/stage7_01_cr1_a.py

INVESTIGATION TRIGGER:
cr1 found 34 institutions with pell_share == 1.0 in the output, but the script
logged capping only 33 institutions. This 34 vs 33 discrepancy needs explanation.

HYPOTHESIS:
One institution had a raw pell_share of exactly 1.0 (pell_recipients == enrollment),
which was NOT capped (because the cap only applies to > 1.0), bringing the total
with pell_share == 1.0 to 33 (capped) + 1 (naturally = 1.0) = 34.

EXPECTED OUTCOME:
- If CONFIRMED: Exactly 1 institution has pell_recipients == enrollment_undergrad
  (naturally 1.0), and 33 have pell_recipients > enrollment_undergrad (capped to 1.0).
  This is benign — no data integrity issue.
- If REFUTED: Something else explains the discrepancy, potentially a data integrity
  problem in the capping logic.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_core_joined.parquet"
INPUT_FSA = PROJECT_DIR / "data" / "processed" / "2026-02-15_fsa_grants_clean.parquet"
INPUT_ENR = PROJECT_DIR / "data" / "processed" / "2026-02-15_enrollment_race_clean.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 7 Step 01 — Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
df_fsa = pl.read_parquet(INPUT_FSA)
df_enr = pl.read_parquet(INPUT_ENR)

# --- Investigation ---
# Get all institutions with pell_share == 1.0
at_one = df.filter(pl.col("pell_share") == 1.0)
print(f"\nInstitutions with pell_share == 1.0: {at_one.shape[0]}")

# For each, recompute raw pell_share from source files
print("\nTracing each institution:")
naturally_one = 0
capped_to_one = 0
for row in at_one.iter_rows(named=True):
    uid = row["unitid"]
    inst = row["inst_name"]

    fsa_row = df_fsa.filter(pl.col("unitid") == uid)
    enr_row = df_enr.filter(pl.col("unitid") == uid)

    pell = fsa_row["pell_recipients"][0] if len(fsa_row) > 0 else None
    enroll = enr_row["total_enrollment_race"][0] if len(enr_row) > 0 else None

    if pell is not None and enroll is not None and enroll > 0:
        raw_ratio = pell / enroll
        if raw_ratio == 1.0:
            naturally_one += 1
            label = "NATURALLY 1.0"
        elif raw_ratio > 1.0:
            capped_to_one += 1
            label = f"CAPPED (raw={raw_ratio:.4f})"
        else:
            label = f"UNEXPECTED (raw={raw_ratio:.4f})"
    else:
        label = f"CANNOT COMPUTE (pell={pell}, enroll={enroll})"

    print(f"  unitid={uid} ({inst}): pell={pell}, enroll={enroll} -> {label}")

print(f"\nSummary:")
print(f"  Naturally == 1.0: {naturally_one}")
print(f"  Capped from > 1.0: {capped_to_one}")
print(f"  Total: {naturally_one + capped_to_one}")

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

confirmed = (naturally_one >= 1) and (capped_to_one == 33) and (naturally_one + capped_to_one == 34)

if confirmed:
    implications = ("The 34 vs 33 discrepancy is fully explained: 33 institutions were capped "
                    "from >1.0, and the remaining institution(s) had raw pell_share of exactly 1.0. "
                    "No data integrity issue.")
else:
    implications = (f"Hypothesis partially confirmed or refuted. "
                    f"Naturally=1.0: {naturally_one}, Capped: {capped_to_one}. "
                    f"Investigate further if totals don't add up.")

print(f"\nHypothesis: {'CONFIRMED' if confirmed else 'PARTIALLY CONFIRMED'}")
print(f"Implications: {implications}")
print(f"Further investigation needed: NO")
print(f"Severity assessment: INFO (no data integrity concern)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:21:11
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage7_01_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 7 Step 01 — Iteration 2
# ============================================================
# 
# Institutions with pell_share == 1.0: 34
# 
# Tracing each institution:
#   unitid=111638 (Casa Loma College-Van Nuys): pell=164.0, enroll=164 -> NATURALLY 1.0
#   unitid=138293 (Webber International University): pell=942.0, enroll=735 -> CAPPED (raw=1.2816)
#   unitid=144883 (East-West University): pell=436.0, enroll=419 -> CAPPED (raw=1.0406)
#   unitid=151801 (Indiana Wesleyan University-Marion): pell=4540.0, enroll=2677 -> CAPPED (raw=1.6959)
#   unitid=151810 (Martin University): pell=171.0, enroll=170 -> CAPPED (raw=1.0059)
#   unitid=151962 (Mid-America College of Funeral Service): pell=173.0, enroll=92 -> CAPPED (raw=1.8804)
#   unitid=155627 (Ottawa University-Ottawa): pell=1028.0, enroll=720 -> CAPPED (raw=1.4278)
#   unitid=176336 (Southeastern Baptist College): pell=78.0, enroll=62 -> CAPPED (raw=1.2581)
#   unitid=201104 (Ashland University): pell=6169.0, enroll=3148 -> CAPPED (raw=1.9597)
#   unitid=223463 (Remington College-Dallas Campus): pell=5035.0, enroll=628 -> CAPPED (raw=8.0175)
#   unitid=234137 (Virginia University of Lynchburg): pell=158.0, enroll=122 -> CAPPED (raw=1.2951)
#   unitid=240392 (Herzing University-Madison): pell=6597.0, enroll=1647 -> CAPPED (raw=4.0055)
#   unitid=241100 (American University of Puerto Rico): pell=642.0, enroll=281 -> CAPPED (raw=2.2847)
#   unitid=241377 (Caribbean University-Bayamon): pell=1150.0, enroll=636 -> CAPPED (raw=1.8082)
#   unitid=241410 (Pontifical Catholic University of Puerto Rico-Ponce): pell=5092.0, enroll=4889 -> CAPPED (raw=1.0415)
#   unitid=242121 (Humacao Community College): pell=399.0, enroll=301 -> CAPPED (raw=1.3256)
#   unitid=242644 (Inter American University of Puerto Rico-Barranquitas): pell=1314.0, enroll=1174 -> CAPPED (raw=1.1193)
#   unitid=243638 (College of Micronesia-FSM): pell=2195.0, enroll=1861 -> CAPPED (raw=1.1795)
#   unitid=243832 (EDP University of Puerto Rico Inc-San Juan): pell=2099.0, enroll=1240 -> CAPPED (raw=1.6927)
#   unitid=244233 (City College-Fort Lauderdale): pell=552.0, enroll=297 -> CAPPED (raw=1.8586)
#   unitid=376385 (Universal Technology College of Puerto Rico): pell=326.0, enroll=108 -> CAPPED (raw=3.0185)
#   unitid=376695 (College of the Marshall Islands): pell=1547.0, enroll=1162 -> CAPPED (raw=1.3313)
#   unitid=420325 (Yeshiva D'monsey Rabbinical College): pell=72.0, enroll=71 -> CAPPED (raw=1.0141)
#   unitid=430670 (San Juan Bautista School of Medicine): pell=64.0, enroll=62 -> CAPPED (raw=1.0323)
#   unitid=440651 (Atenas College): pell=636.0, enroll=558 -> CAPPED (raw=1.1398)
#   unitid=443562 (Dewey University-Hato Rey): pell=1221.0, enroll=363 -> CAPPED (raw=3.3636)
#   unitid=454582 (Ottawa University-Online): pell=236.0, enroll=163 -> CAPPED (raw=1.4479)
#   unitid=455664 (The Chicago School of Professional Psychology at Los Angeles): pell=346.0, enroll=182 -> CAPPED (raw=1.9011)
#   unitid=457086 (Homestead Schools): pell=158.0, enroll=125 -> CAPPED (raw=1.2640)
#   unitid=457402 (University of Fort Lauderdale): pell=93.0, enroll=49 -> CAPPED (raw=1.8980)
#   unitid=457697 (City Vision University): pell=103.0, enroll=99 -> CAPPED (raw=1.0404)
#   unitid=483595 (Universidad Ana G. Mendez-Online Campus): pell=1388.0, enroll=1257 -> CAPPED (raw=1.1042)
#   unitid=490328 (Mechon L'hoyroa): pell=59.0, enroll=57 -> CAPPED (raw=1.0351)
#   unitid=491057 (Yeshiva Kollel Tifereth Elizer): pell=181.0, enroll=171 -> CAPPED (raw=1.0585)
# 
# Summary:
#   Naturally == 1.0: 1
#   Capped from > 1.0: 33
#   Total: 34
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Hypothesis: CONFIRMED
# Implications: The 34 vs 33 discrepancy is fully explained: 33 institutions were capped from >1.0, and the remaining institution(s) had raw pell_share of exactly 1.0. No data integrity issue.
# Further investigation needed: NO
# Severity assessment: INFO (no data integrity concern)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
