# 36_crdc-race-code-probe.py
# Orchestrator-run probe to settle the one open item from the wave-3 fix pass:
# variable-codes.md:154 documents CRDC race codes as "1-7, 20, 99". The CCD row
# was live-probed ({1-7,9,99}) but no CRDC probe was run, and the fix-pass
# engineer correctly refused to edit the CRDC row without evidence.

import json
import urllib.request

import polars as pl

# --- Config ---
# INTENT: Read the distinct race codes from race-disaggregated CRDC files on the
#   pinned mirror (2020 and 2021 vintages) to adjudicate the documented set.
# REASONING: The mirror is proven cell-exact to Urban bulk CSVs (Lane A 6/6) and
#   count-consistent with the live API (Lane B 16/16), so mirror distinct values
#   are valid evidence for the Portal's CRDC race coding.
# ASSUMES: CRDC enrollment files carry a `race` column; pinned revision serves.
REV = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{REV}"

candidates = [
    "crdc/schools_crdc_enrollment_k12_2020",
    "crdc/schools_crdc_enrollment_k12_2021",
]

# --- Load + Profile ---
for path in candidates:
    url = f"{BASE}/{path}.parquet"
    # INTENT: project only the race column; no full download.
    lf = pl.scan_parquet(url)
    schema_names = lf.collect_schema().names()
    race_cols = [c for c in schema_names if c == "race" or c.startswith("race")]
    print(f"{path}: race-like columns = {race_cols}")
    for col in race_cols:
        vals = (
            lf.select(pl.col(col).unique().sort())
            .collect()
            .get_column(col)
            .to_list()
        )
        print(f"  {path}.{col} distinct = {vals}")

# --- Validate ---
# INTENT: make the adjudication explicit — is 20 present? is 9 present?
# REASONING: documented set is {1..7, 20, 99}; the CCD correction moved 20 -> 9,
#   and we must not assume CRDC follows CCD.
print("Adjudication target: documented CRDC set = 1-7, 20, 99")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:46:52
# Command: python3 /daaf/scripts/mirror_maintenance/36_crdc-race-code-probe.py
# Duration: 4s
# Exit code: 0
#
# --- STDOUT ---
# crdc/schools_crdc_enrollment_k12_2020: race-like columns = ['race']
#   crdc/schools_crdc_enrollment_k12_2020.race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# crdc/schools_crdc_enrollment_k12_2021: race-like columns = ['race']
#   crdc/schools_crdc_enrollment_k12_2021.race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# Adjudication target: documented CRDC set = 1-7, 20, 99
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
