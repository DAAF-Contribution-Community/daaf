#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 5 Step 02 — Iteration 2 (Re-QA of BLOCKER revision)

Reviewed script: scripts/stage5_fetch/02_fetch-grad-rates_b.py
Prior QA script: scripts/cr/stage5_02_cr1.py

INVESTIGATION TRIGGER:
cr1 found BLOCKER: cohort_year column was missing from output parquet (6 cols).
The revised script (_b.py) adds cohort_year to SELECT_COLUMNS, producing 7 cols.
This cr2 verifies the fix resolved the BLOCKER and all prior PASSED checks hold.

HYPOTHESIS:
Adding cohort_year to SELECT_COLUMNS resolves the BLOCKER by enabling Stage 6
to filter to a single row per institution (cohort_year=2014).

EXPECTED OUTCOME:
- If CONFIRMED: cohort_year present, multiple cohort_year values per institution,
  filtering to cohort_year=2014 yields ~1,949 rows (1 per institution with
  non-null completion_rate_150pct).
- If REFUTED: cohort_year missing, or filtering produces unexpected row counts.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_ipeds_grad_rates.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 5 Step 02 — Iteration 2")
print("BLOCKER Re-QA: Verify cohort_year fix")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# ============================================================
# CHECK A: BLOCKER FIX — cohort_year column present
# ============================================================
print("\n" + "-" * 60)
print("CHECK A: BLOCKER FIX — cohort_year present?")
print("-" * 60)

cohort_year_present = "cohort_year" in df.columns
print(f"[{'PASS' if cohort_year_present else 'BLOCKER'}] cohort_year in output: {cohort_year_present}")

if not cohort_year_present:
    print("\nBLOCKER NOT RESOLVED. Stopping.")
    print("=" * 60)
    print("QA RESULT: BLOCKER")
    print("=" * 60)
    import sys
    sys.exit(1)

# ============================================================
# CHECK B: cohort_year value profile
# ============================================================
print("\n" + "-" * 60)
print("CHECK B: cohort_year value profile")
print("-" * 60)

cy_unique = df["cohort_year"].unique().sort().to_list()
cy_null_count = df["cohort_year"].null_count()
print(f"Unique cohort_year values: {cy_unique}")
print(f"Null count: {cy_null_count}")

cy_value_counts = df["cohort_year"].value_counts().sort("cohort_year")
print(f"Value distribution:")
print(cy_value_counts)

# Multiple cohort_year values per institution is the expected reason for duplicates
has_multiple_cy = len(cy_unique) > 1
print(f"[{'PASS' if has_multiple_cy else 'WARN'}] Multiple cohort_year values exist: {has_multiple_cy}")

# ============================================================
# CHECK C: Filtering to cohort_year=2014 yields ~1 row per institution
# ============================================================
print("\n" + "-" * 60)
print("CHECK C: cohort_year=2014 deduplication test")
print("-" * 60)

if 2014 in cy_unique:
    df_2014 = df.filter(pl.col("cohort_year") == 2014)
    n_2014 = df_2014.shape[0]
    n_unique_unitid_2014 = df_2014["unitid"].n_unique()
    is_one_per_inst = n_2014 == n_unique_unitid_2014
    print(f"Rows with cohort_year=2014: {n_2014:,}")
    print(f"Unique unitids in that subset: {n_unique_unitid_2014:,}")
    print(f"[{'PASS' if is_one_per_inst else 'WARN'}] 1:1 unitid mapping: {is_one_per_inst}")

    # Check non-null completion_rate count in cohort_year=2014
    non_null_rate = df_2014["completion_rate_150pct"].drop_nulls().shape[0]
    print(f"Non-null completion_rate_150pct in cohort_year=2014: {non_null_rate:,}")
    # Per cr1, we expect ~1,949 non-null rates
    rate_plausible = 1800 <= non_null_rate <= 2100
    print(f"[{'PASS' if rate_plausible else 'WARN'}] Non-null rate count plausible "
          f"(expected ~1,949): {non_null_rate:,}")
else:
    print(f"[WARN] cohort_year=2014 not found in data. Available: {cy_unique}")
    n_2014 = 0
    is_one_per_inst = False

# ============================================================
# CHECK D: Prior PASSED checks still hold (regression test)
# ============================================================
print("\n" + "-" * 60)
print("CHECK D: Regression checks (prior PASSED items)")
print("-" * 60)

# D1: Schema — now 7 columns expected
expected_cols = ["unitid", "year", "cohort_year", "completion_rate_150pct",
                 "cohort_adj_150pct", "completers_150pct", "subcohort"]
missing = [c for c in expected_cols if c not in df.columns]
extra = [c for c in df.columns if c not in expected_cols]
schema_ok = len(missing) == 0 and len(extra) == 0
print(f"[{'PASS' if schema_ok else 'FAIL'}] D1 Schema: "
      f"missing={missing}, extra={extra}")

# D2: Row count in range
row_ok = 2000 <= df.shape[0] <= 5000
print(f"[{'PASS' if row_ok else 'FAIL'}] D2 Row count: {df.shape[0]:,} (expected 2,000-5,000)")

# D3: Only year 2020
years = df["year"].unique().to_list()
year_ok = years == [2020]
print(f"[{'PASS' if year_ok else 'FAIL'}] D3 Year filter: {years}")

# D4: Only subcohort 2
sc_vals = df["subcohort"].unique().to_list()
sc_ok = sc_vals == [2]
print(f"[{'PASS' if sc_ok else 'FAIL'}] D4 Subcohort filter: {sc_vals}")

# D5: No nulls in unitid
uid_nulls = df["unitid"].null_count()
uid_ok = uid_nulls == 0
print(f"[{'PASS' if uid_ok else 'FAIL'}] D5 Unitid nulls: {uid_nulls}")

# D6: completion_rate_150pct scale 0-1
rate_col = df["completion_rate_150pct"].drop_nulls()
if rate_col.shape[0] > 0:
    r_min, r_max = rate_col.min(), rate_col.max()
    scale_ok = r_min >= 0 and r_max <= 1.0
    print(f"[{'PASS' if scale_ok else 'FAIL'}] D6 Rate scale: {r_min:.4f} to {r_max:.4f}")
else:
    scale_ok = False
    print(f"[FAIL] D6 Rate scale: all null")

# D7: No negative coded values in any numeric column
coded_found = False
for col in df.columns:
    if df[col].dtype in [pl.Int64, pl.Float64]:
        for code in [-1, -2, -3]:
            ct = (df[col] == code).sum()
            if ct > 0:
                print(f"  [WARN] {col} has {ct} coded value {code}")
                coded_found = True
print(f"[{'PASS' if not coded_found else 'WARN'}] D7 No negative coded values")

# ============================================================
# CHECK E: Spot-check UC Berkeley (unitid=110635)
# ============================================================
print("\n" + "-" * 60)
print("CHECK E: Spot-check UC Berkeley (unitid=110635)")
print("-" * 60)

ucb = df.filter(pl.col("unitid") == 110635)
print(f"Rows for UC Berkeley: {ucb.shape[0]}")
if ucb.shape[0] > 0:
    print(ucb)
    # Should have cohort_year values now
    ucb_cy = ucb["cohort_year"].to_list()
    print(f"cohort_year values: {ucb_cy}")
    ucb_has_cy = all(v is not None for v in ucb_cy)
    print(f"[{'PASS' if ucb_has_cy else 'WARN'}] UC Berkeley has non-null cohort_year values")

    # Check the 2014 cohort row specifically
    ucb_2014 = ucb.filter(pl.col("cohort_year") == 2014)
    if ucb_2014.shape[0] == 1:
        rate = ucb_2014["completion_rate_150pct"][0]
        print(f"UCB cohort_year=2014 completion rate: {rate}")
        if rate is not None:
            plausible = 0.85 <= rate <= 0.98
            print(f"[{'PASS' if plausible else 'WARN'}] Rate {rate:.3f} plausible for UC Berkeley")
    elif ucb_2014.shape[0] == 0:
        print(f"[INFO] No cohort_year=2014 row for UC Berkeley")
else:
    print(f"[INFO] UC Berkeley not found in dataset")

# ============================================================
# INTERPRETATION
# ============================================================
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

blocker_resolved = cohort_year_present and has_multiple_cy
regression_ok = schema_ok and row_ok and year_ok and sc_ok and uid_ok and scale_ok
dedup_viable = is_one_per_inst if 2014 in cy_unique else False

confirmed = blocker_resolved and regression_ok and dedup_viable

print(f"\nBLOCKER fix (cohort_year present + useful): {'CONFIRMED' if blocker_resolved else 'REFUTED'}")
print(f"Regression checks (prior PASSED items hold): {'ALL PASS' if regression_ok else 'ISSUES'}")
print(f"Deduplication viability (cohort_year=2014 → 1:1): {'CONFIRMED' if dedup_viable else 'REFUTED'}")

print(f"\nHypothesis: {'CONFIRMED' if confirmed else 'REFUTED'}")
print(f"Further investigation needed: NO")

if confirmed:
    severity = "PASSED"
else:
    severity = "BLOCKER" if not blocker_resolved else "WARNING"

print(f"Severity assessment: {severity}")

print("\n" + "=" * 60)
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 20:21:29
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_02_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 5 Step 02 — Iteration 2
# BLOCKER Re-QA: Verify cohort_year fix
# ============================================================
# Loaded: 4,489 rows x 7 cols
# Columns: ['unitid', 'year', 'cohort_year', 'completion_rate_150pct', 'cohort_adj_150pct', 'completers_150pct', 'subcohort']
# 
# ------------------------------------------------------------
# CHECK A: BLOCKER FIX — cohort_year present?
# ------------------------------------------------------------
# [PASS] cohort_year in output: True
# 
# ------------------------------------------------------------
# CHECK B: cohort_year value profile
# ------------------------------------------------------------
# Unique cohort_year values: [2015]
# Null count: 0
# Value distribution:
# shape: (1, 2)
# ┌─────────────┬───────┐
# │ cohort_year ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 2015        ┆ 4489  │
# └─────────────┴───────┘
# [WARN] Multiple cohort_year values exist: False
# 
# ------------------------------------------------------------
# CHECK C: cohort_year=2014 deduplication test
# ------------------------------------------------------------
# [WARN] cohort_year=2014 not found in data. Available: [2015]
# 
# ------------------------------------------------------------
# CHECK D: Regression checks (prior PASSED items)
# ------------------------------------------------------------
# [PASS] D1 Schema: missing=[], extra=[]
# [PASS] D2 Row count: 4,489 (expected 2,000-5,000)
# [PASS] D3 Year filter: [2020]
# [PASS] D4 Subcohort filter: [2]
# [PASS] D5 Unitid nulls: 0
# [PASS] D6 Rate scale: 0.0380 to 1.0000
# [PASS] D7 No negative coded values
# 
# ------------------------------------------------------------
# CHECK E: Spot-check UC Berkeley (unitid=110635)
# ------------------------------------------------------------
# Rows for UC Berkeley: 2
# shape: (2, 7)
# ┌────────┬──────┬─────────────┬──────────────────┬──────────────────┬──────────────────┬───────────┐
# │ unitid ┆ year ┆ cohort_year ┆ completion_rate_ ┆ cohort_adj_150pc ┆ completers_150pc ┆ subcohort │
# │ ---    ┆ ---  ┆ ---         ┆ 150pct           ┆ t                ┆ t                ┆ ---       │
# │ i64    ┆ i64  ┆ i64         ┆ ---              ┆ ---              ┆ ---              ┆ i64       │
# │        ┆      ┆             ┆ f64              ┆ i64              ┆ i64              ┆           │
# ╞════════╪══════╪═════════════╪══════════════════╪══════════════════╪══════════════════╪═══════════╡
# │ 110635 ┆ 2020 ┆ 2015        ┆ null             ┆ null             ┆ 5114             ┆ 2         │
# │ 110635 ┆ 2020 ┆ 2015        ┆ 0.928            ┆ 5510             ┆ 5114             ┆ 2         │
# └────────┴──────┴─────────────┴──────────────────┴──────────────────┴──────────────────┴───────────┘
# cohort_year values: [2015, 2015]
# [PASS] UC Berkeley has non-null cohort_year values
# [INFO] No cohort_year=2014 row for UC Berkeley
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# BLOCKER fix (cohort_year present + useful): REFUTED
# Regression checks (prior PASSED items hold): ALL PASS
# Deduplication viability (cohort_year=2014 → 1:1): REFUTED
# 
# Hypothesis: REFUTED
# Further investigation needed: NO
# Severity assessment: BLOCKER
# 
# ============================================================
# QA RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
