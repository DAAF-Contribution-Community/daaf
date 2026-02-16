#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 5 Step 04 — Iteration 2

Reviewed script: scripts/stage5_fetch/04_fetch-fsa-grants_d.py
Prior QA script: scripts/cr/stage5_04_cr1.py

INVESTIGATION TRIGGER:
cr1 Check 7 reported pell_recipients as "not integer-like" (is_integer_like=False)
despite values appearing as whole numbers (362.0, 3607.0, etc.). The dtype is Float64
which could mask fractional values that would be incorrect for recipient counts.
Also, cr1 Check 5 flagged 6 nulls in pell_recipients (a critical column).

HYPOTHESIS:
The Float64 dtype is due to the presence of null values (Polars/Parquet uses float
to represent nullable integers). All non-null values are actually exact integers.
If REFUTED (fractional values exist), this could indicate data corruption or
a formula-based calculation rather than raw counts — which would change how
pell_share is computed downstream.

EXPECTED OUTCOME:
- If CONFIRMED: All non-null pell_recipients values are exact integers (x.0),
  and the Float64 dtype is purely a null-handling artifact. Safe for downstream.
- If REFUTED: Some values have fractional parts, indicating the column may not
  be raw counts. Would need investigation of data source.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_fsa_grants.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 5 Step 04 — Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)

# --- Investigation: Are pell_recipients values truly integers? ---
print("\n--- Testing integer-ness of pell_recipients ---")

non_null = df.filter(pl.col("pell_recipients").is_not_null())
print(f"Non-null rows: {len(non_null):,}")

# Check if all values are exact integers (fractional part == 0)
fractional = non_null.filter(
    (pl.col("pell_recipients") % 1.0) != 0.0
)
print(f"Rows with fractional pell_recipients: {len(fractional)}")

if len(fractional) > 0:
    print("FRACTIONAL VALUES FOUND:")
    print(fractional.head(20))
else:
    print("All non-null values are exact integers (x.0)")

# Same check for pell_disbursements
print("\n--- Testing integer-ness of pell_disbursements ---")
non_null_disb = df.filter(pl.col("pell_disbursements").is_not_null())
fractional_disb = non_null_disb.filter(
    (pl.col("pell_disbursements") % 1.0) != 0.0
)
print(f"Rows with fractional pell_disbursements: {len(fractional_disb)}")

if len(fractional_disb) > 0:
    # Disbursements might legitimately be fractional (dollars and cents)
    print(f"Sample fractional disbursement values:")
    sample = fractional_disb.select("unitid", "pell_disbursements").head(10)
    print(sample)
    # Check if these are just floating-point precision artifacts
    # (e.g., values like 353417.4375 which looks like a real fractional value)
    max_frac = (fractional_disb["pell_disbursements"] % 1.0).abs().max()
    print(f"Max fractional part: {max_frac}")
    print("Note: Fractional disbursements are acceptable (dollars + cents)")

# --- Additional: Verify the 6 null rows don't overlap with institutions
# likely to be in our final analysis (4-year public/private nonprofit) ---
print("\n--- Null pell_recipients characterization ---")
null_rows = df.filter(pl.col("pell_recipients").is_null())
print(f"Null unitids: {null_rows['unitid'].to_list()}")
print("These 6 institutions will be excluded from Pell-based calculations.")
print("At 0.12% of the dataset, this is negligible data loss.")

# --- Interpretation ---
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

confirmed = len(fractional) == 0
if confirmed:
    print("Hypothesis: CONFIRMED")
    print("All non-null pell_recipients values are exact integers.")
    print("The Float64 dtype is purely a null-handling artifact from Parquet/Polars.")
    print("Safe for downstream pell_share computation (pell_recipients / enrollment).")
    print("Implications: No data quality concern. Stage 6 can optionally cast to Int64.")
    print("Further investigation needed: NO")
    print("Severity assessment: INFO")
else:
    print("Hypothesis: REFUTED")
    print("Fractional values found in pell_recipients — unexpected for count data.")
    print("Further investigation needed: YES — determine source of fractions")
    print("Severity assessment: WARNING")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:34:09
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage5_04_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 5 Step 04 — Iteration 2
# ============================================================
# 
# --- Testing integer-ness of pell_recipients ---
# Non-null rows: 4,988
# Rows with fractional pell_recipients: 38
# FRACTIONAL VALUES FOUND:
# shape: (20, 4)
# ┌────────┬──────┬─────────────────┬────────────────────┐
# │ unitid ┆ year ┆ pell_recipients ┆ pell_disbursements │
# │ ---    ┆ ---  ┆ ---             ┆ ---                │
# │ i64    ┆ i64  ┆ f64             ┆ f64                │
# ╞════════╪══════╪═════════════════╪════════════════════╡
# │ 131803 ┆ 2020 ┆ 2570.539307     ┆ 1.0439663e7        │
# │ 133553 ┆ 2020 ┆ 2603.908203     ┆ 9.380326e6         │
# │ 133881 ┆ 2020 ┆ 1345.304321     ┆ 5.445621e6         │
# │ 134130 ┆ 2020 ┆ 9578.478516     ┆ 4.7873936e7        │
# │ 139579 ┆ 2020 ┆ 653.223755      ┆ 2.499909e6         │
# │ …      ┆ …    ┆ …               ┆ …                  │
# │ 228875 ┆ 2020 ┆ 1403.825073     ┆ 6797272.5          │
# │ 236133 ┆ 2020 ┆ 354.626587      ┆ 1.3858e6           │
# │ 237066 ┆ 2020 ┆ 883.36908       ┆ 4.0436e6           │
# │ 240374 ┆ 2020 ┆ 1408.232056     ┆ 6.155052e6         │
# │ 240453 ┆ 2020 ┆ 6545.038574     ┆ 2.86391e7          │
# └────────┴──────┴─────────────────┴────────────────────┘
# 
# --- Testing integer-ness of pell_disbursements ---
# Rows with fractional pell_disbursements: 1589
# Sample fractional disbursement values:
# shape: (10, 2)
# ┌────────┬────────────────────┐
# │ unitid ┆ pell_disbursements │
# │ ---    ┆ ---                │
# │ i64    ┆ f64                │
# ╞════════╪════════════════════╡
# │ 100690 ┆ 1.0310e6           │
# │ 100760 ┆ 2.2938e6           │
# │ 100937 ┆ 1.2259e6           │
# │ 101277 ┆ 353417.4375        │
# │ 101301 ┆ 3400986.5          │
# │ 101462 ┆ 2.1299e6           │
# │ 101471 ┆ 358201.46875       │
# │ 101587 ┆ 6419880.5          │
# │ 101675 ┆ 6509975.5          │
# │ 101736 ┆ 5496885.5          │
# └────────┴────────────────────┘
# Max fractional part: 0.984375
# Note: Fractional disbursements are acceptable (dollars + cents)
# 
# --- Null pell_recipients characterization ---
# Null unitids: [112251, 189015, 196468, 409254, 475033, 495192]
# These 6 institutions will be excluded from Pell-based calculations.
# At 0.12% of the dataset, this is negligible data loss.
# 
# ============================================================
# INTERPRETATION
# ============================================================
# Hypothesis: REFUTED
# Fractional values found in pell_recipients — unexpected for count data.
# Further investigation needed: YES — determine source of fractions
# Severity assessment: WARNING
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
