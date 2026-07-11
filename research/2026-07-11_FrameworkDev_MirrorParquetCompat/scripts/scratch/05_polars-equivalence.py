#!/usr/bin/env python3
"""
Verify the R view-safe read produced results equivalent to a native Polars read
of the same files (row count + ordered column names + sample values).

Reads the R-side metadata emitted by 04_minimal-pattern-and-equivalence.R and
compares against Polars reading the parquet files directly.
"""

# --- Config ---
import os
import polars as pl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
saipe = os.path.join(SCRATCH, "saipe_districts_FAILING.parquet")
meps = os.path.join(SCRATCH, "meps_schools_WORKING.parquet")

print(f"polars version: {pl.__version__}")

# --- Load: Polars native reads ---
# INTENT: Polars reads its own StringView output natively — establishes the
# reference row count and column ordering the R read must match.
df_saipe = pl.read_parquet(saipe)
df_meps = pl.read_parquet(meps)

print(f"polars SAIPE: rows={df_saipe.height:,} cols={df_saipe.width} dtypes: "
      f"{ {c: str(t) for c, t in zip(df_saipe.columns, df_saipe.dtypes)} }")
print(f"polars MEPS : rows={df_meps.height:,} cols={df_meps.width}")

# --- Load: R-side metadata ---
def read_meta(name):
    with open(os.path.join(SCRATCH, name)) as f:
        lines = f.read().splitlines()
    return int(lines[0]), lines[1].split(",")

r_saipe_rows, r_saipe_cols = read_meta("r_read_saipe_meta.txt")
r_meps_rows, r_meps_cols = read_meta("r_read_meps_meta.txt")
with open(os.path.join(SCRATCH, "r_read_saipe_sample.txt")) as f:
    r_saipe_sample = f.read().splitlines()

# --- Validate: row counts match ---
# ASSUMES: a lossless read preserves exact row count.
assert df_saipe.height == r_saipe_rows, f"SAIPE row mismatch: polars={df_saipe.height} R={r_saipe_rows}"
assert df_meps.height == r_meps_rows, f"MEPS row mismatch: polars={df_meps.height} R={r_meps_rows}"
print("row counts match: SAIPE and MEPS")

# --- Validate: column names + order match ---
assert df_saipe.columns == r_saipe_cols, f"SAIPE columns differ:\n polars={df_saipe.columns}\n R={r_saipe_cols}"
assert df_meps.columns == r_meps_cols, f"MEPS columns differ:\n polars={df_meps.columns}\n R={r_meps_cols}"
print("column names + order match: SAIPE and MEPS")

# --- Validate: district_name sample values match (string_view roundtrip) ---
# INTENT: the string_view column is the one the R binding choked on — verify its
# values survived the cast identically to Polars' native read.
polars_sample = df_saipe["district_name"].head(5).to_list()
assert polars_sample == r_saipe_sample, f"district_name sample differs:\n polars={polars_sample}\n R={r_saipe_sample}"
print(f"district_name sample values match: {polars_sample}")

# --- Summary ---
print("SUMMARY: R view-safe read is EQUIVALENT to Polars native read "
      "(rows, columns, and string_view values all match).")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:32:25
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/05_polars-equivalence.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# polars version: 1.38.1
# polars SAIPE: rows=368,967 cols=10 dtypes: {'district_id': 'Int64', 'district_name': 'String', 'est_population_total': 'Int64', 'est_population_5_17': 'Int64', 'est_population_5_17_poverty': 'Int64', 'year': 'Int64', 'leaid': 'Int64', 'fips': 'Int64', 'est_population_5_17_poverty_pct': 'Float64', 'est_population_5_17_pct': 'Float64'}
# polars MEPS : rows=1,345,122 cols=11
# row counts match: SAIPE and MEPS
# column names + order match: SAIPE and MEPS
# district_name sample values match: ['ALBERTVILLE CITY SCH DIST', 'ALEXANDER CITY CITY SCH DIST', 'ANDALUSIA CITY SCH DIST', 'ANNISTON CITY SCH DIST', 'ARAB CITY SCH DIST']
# SUMMARY: R view-safe read is EQUIVALENT to Polars native read (rows, columns, and string_view values all match).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
