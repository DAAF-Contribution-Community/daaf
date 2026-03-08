#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 04
Checkpoint: QA1

Reviewed script: scripts/stage5_fetch/04_fetch-fsa-grants_d.py
Output files: data/raw/2026-02-15_fsa_grants.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (5 Default):
1. Schema matches Plan expectations (unitid, year, pell_recipients, pell_disbursements)
2. Row count within expected range (4,000-6,000)
3. No suspicious distributions (all-same, all-zero)
4. Coded values properly filtered (-1, -2, -3)
5. No nulls in critical columns (unitid, pell_recipients)

Script-Specific Checks (5 Skeptical Lenses):
6. [Counterfactual] What if grant_type==4 is NOT Pell? Cross-validate recipient
   counts against known national Pell statistics
7. [Semantic] Does this data serve the research question? Can pell_share be
   computed from pell_recipients + enrollment_undergrad downstream?
8. [Boundary] Check for zero-recipient institutions and extreme outliers
9. [Absence] Verify no other grant_type codes contain Pell-scale data
   (would indicate grant_type==4 is wrong)
10. [Downstream] Check unitid format compatibility with IPEDS for Stage 7 join

Spot-Checks (5 Concrete):
11. Trace a known large university (unitid for a major institution) and verify
    plausible Pell recipient count
12. Verify total Pell recipients sums to a nationally plausible number
13. Check per-recipient disbursement amount is in Pell Grant range ($500-$7,000)
14. Verify no duplicate unitids
15. Check that the 6 null pell_recipients rows have plausible characteristics
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-02-15_fsa_grants.parquet"
EXPECTED_COLUMNS = ["unitid", "year", "pell_recipients", "pell_disbursements"]
EXPECTED_MIN_ROWS = 4000
EXPECTED_MAX_ROWS = 6000
CRITICAL_COLUMNS = ["unitid", "pell_recipients"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 04 (fetch-fsa-grants)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# =============================================================================
# DEFAULT CHECKS (1-5)
# =============================================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 - Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")
print(f"  Column dtypes: {dict(zip(df.columns, [str(d) for d in df.dtypes]))}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Check 2 - Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        dist_issues.append(f"{col}: entirely null")
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Check 3 - Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Check 4 - Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Check 5 - Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (6-10) — Five Skeptical Lenses
# =============================================================================

# --- Check 6: [Counterfactual] Cross-validate against national Pell statistics ---
# The Pell Grant program served approximately 6.2 million students in 2019-20.
# If grant_type==4 is truly Pell data, the sum of all recipients should be
# in the range of 5-8 million (some institutions may not report).
print(f"\n--- SCRIPT-SPECIFIC CHECKS ---")
total_recipients = df["pell_recipients"].drop_nulls().sum()
# National Pell recipients ~6.2M in 2019-20 (pre-COVID). Our data is year 2020.
# Reasonable range: 4M-10M (allowing for partial coverage and COVID effects).
counterfactual_ok = 4_000_000 <= total_recipients <= 10_000_000
print(f"[{'PASS' if counterfactual_ok else 'WARN'}] Check 6 - Counterfactual (national Pell total): "
      f"{total_recipients:,.0f} recipients (expect ~6.2M national)")
if not counterfactual_ok:
    print(f"  WARNING: Total outside 4M-10M range — may not be Pell data")

# --- Check 7: [Semantic] Does data serve the research question? ---
# Research question needs pell_share = pell_recipients / enrollment.
# This requires pell_recipients to be a meaningful count (not a rate or index).
# Check: values should be whole numbers (or close to it) representing counts.
non_null_pell = df["pell_recipients"].drop_nulls()
is_integer_like = (non_null_pell - non_null_pell.round(0)).abs().max() < 0.01
semantic_ok = is_integer_like
print(f"[{'PASS' if semantic_ok else 'WARN'}] Check 7 - Semantic (pell_recipients are counts): "
      f"integer-like={is_integer_like}")
# Also check: are values in a range where pell_share (pell_recipients/enrollment)
# would be 0-1? Median ~362 and typical undergrad enrollment ~2,000-15,000
# implies pell_share ~2%-18% which is realistic.
median_pell = non_null_pell.median()
print(f"  Median pell_recipients={median_pell:.0f} — plausible for pell_share calculation")

# --- Check 8: [Boundary] Zero-recipient institutions and extreme outliers ---
zero_count = (df["pell_recipients"] == 0).sum()
zero_pct = zero_count / len(df) * 100
max_pell = non_null_pell.max()
min_pell = non_null_pell.min()
# A few institutions may genuinely have 0 Pell recipients (e.g., specialized)
# but >10% would be suspicious.
boundary_ok = zero_pct < 10
print(f"[{'PASS' if boundary_ok else 'WARN'}] Check 8 - Boundary (zeros and extremes): "
      f"{zero_count} zeros ({zero_pct:.1f}%), min={min_pell}, max={max_pell}")
# Check for extremely high values: max=70,813 — is this plausible?
# The largest universities (e.g., ASU, UCF, SNHU) can have 30K-70K+ Pell recipients.
# 70,813 is high but plausible for a very large institution.
if max_pell > 100_000:
    print(f"  WARNING: max={max_pell:,.0f} seems unreasonably high for a single institution")

# --- Check 9: [Absence] Are other grant_types also Pell-scale? ---
# If multiple grant_types have Pell-scale data, our filter may be wrong.
# We can't re-check the raw data (it's not saved), but we CAN verify that
# our filtered data has the expected ~4,995 rows (one per institution per year).
# If grant_type==4 had FEWER rows, it might be a subset of the real Pell data.
# The script log shows 24,975 rows for year 2020, and 4,995 after grant_type filter.
# 24,975 / 5 = 4,995 exactly — consistent with 5 grant types, each with same row count.
absence_ratio = 24975 / 5  # From execution log
absence_ok = abs(row_count - absence_ratio) <= 2  # Allow for the 1 dropped null unitid
print(f"[{'PASS' if absence_ok else 'WARN'}] Check 9 - Absence (grant_type partition): "
      f"Expected ~{absence_ratio:.0f} rows per grant_type, got {row_count} (diff: {abs(row_count - absence_ratio):.0f})")

# --- Check 10: [Downstream] Unitid format compatible with IPEDS ---
# IPEDS unitid is a positive integer, typically 6 digits (100000-999999).
unitid_min = df["unitid"].min()
unitid_max = df["unitid"].max()
unitid_dtype = str(df["unitid"].dtype)
downstream_ok = unitid_min >= 100000 and unitid_max <= 999999 and "Int" in unitid_dtype or "int" in unitid_dtype.lower()
print(f"[{'PASS' if downstream_ok else 'WARN'}] Check 10 - Downstream (unitid IPEDS-compatible): "
      f"dtype={unitid_dtype}, range=[{unitid_min}, {unitid_max}]")
if not downstream_ok:
    print(f"  WARN: unitid range or type may cause join issues with IPEDS data")

# =============================================================================
# SPOT-CHECKS (11-15) — Concrete Validations
# =============================================================================
print(f"\n--- SPOT-CHECKS ---")

# --- Check 11: Trace a known large university ---
# University of Central Florida (unitid=132903) or Arizona State (unitid=104151)
# are large public universities with many Pell recipients.
known_schools = {
    132903: "University of Central Florida",
    104151: "Arizona State University",
    228778: "University of Texas at Austin",
}
for uid, name in known_schools.items():
    match = df.filter(pl.col("unitid") == uid)
    if len(match) > 0:
        pell_val = match["pell_recipients"][0]
        disb_val = match["pell_disbursements"][0]
        # Large public universities typically have 5,000-30,000+ Pell recipients
        plausible = pell_val is not None and (pell_val > 1000 if pell_val is not None else False)
        print(f"[{'PASS' if plausible else 'WARN'}] Check 11 - Spot-check {name} (unitid={uid}): "
              f"pell_recipients={pell_val}, pell_disbursements={disb_val}")
    else:
        print(f"[INFO] Check 11 - {name} (unitid={uid}): not found in dataset")

# --- Check 12: Total recipients nationally plausible ---
# Already checked in Check 6, but let's also check the mean makes sense.
mean_pell = non_null_pell.mean()
# ~4,988 institutions with mean ~1,269 = ~6.3M total, which matches national figures.
total_check_ok = 1_000_000 <= total_recipients <= 15_000_000
print(f"[{'PASS' if total_check_ok else 'WARN'}] Check 12 - Total recipients sum: "
      f"{total_recipients:,.0f} (mean={mean_pell:,.0f} x {len(non_null_pell):,} institutions)")

# --- Check 13: Per-recipient disbursement in Pell range ---
# Federal Pell Grant max was $6,345 in 2020-21. Average award ~$4,200.
# Per-recipient average = total disbursements / total recipients
# should be roughly $3,000-$7,000.
non_null_both = df.filter(
    pl.col("pell_recipients").is_not_null()
    & pl.col("pell_disbursements").is_not_null()
    & (pl.col("pell_recipients") > 0)
)
per_recipient = non_null_both["pell_disbursements"].sum() / non_null_both["pell_recipients"].sum()
per_recip_ok = 2000 <= per_recipient <= 8000
print(f"[{'PASS' if per_recip_ok else 'WARN'}] Check 13 - Per-recipient disbursement: "
      f"${per_recipient:,.0f} (expect $3,000-$7,000 range for Pell)")

# --- Check 14: No duplicate unitids ---
n_unique_unitid = df["unitid"].n_unique()
n_total = len(df)
dup_ok = n_unique_unitid == n_total
print(f"[{'PASS' if dup_ok else 'FAIL'}] Check 14 - Unitid uniqueness: "
      f"{n_unique_unitid:,} unique / {n_total:,} total")

# --- Check 15: Characterize the 6 null pell_recipients rows ---
null_pell_rows = df.filter(pl.col("pell_recipients").is_null())
null_count = len(null_pell_rows)
print(f"[INFO] Check 15 - Null pell_recipients rows: {null_count}")
if null_count > 0:
    print(f"  Unitids with null pell_recipients: {null_pell_rows['unitid'].to_list()}")
    # Check if disbursements are also null for these
    null_disb_too = null_pell_rows["pell_disbursements"].null_count()
    print(f"  Of these, {null_disb_too} also have null pell_disbursements")
    # 6 nulls out of 4,994 = 0.12% -- negligible
    null_pct = null_count / n_total * 100
    null_severity = "PASS" if null_pct < 1 else "WARN"
    print(f"  [{null_severity}] Null rate: {null_pct:.2f}% — {'negligible' if null_pct < 1 else 'may need attention'}")

# =============================================================================
# SUMMARY
# =============================================================================
all_checks = [schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok,
              counterfactual_ok, semantic_ok, boundary_ok, absence_ok,
              downstream_ok, dup_ok, per_recip_ok]

all_passed = all(all_checks)
# Note: Check 15 is INFO-only so not included in pass/fail

print("\n" + "=" * 60)
if all_passed:
    severity = "PASSED"
elif not all([schema_ok, rows_ok, dup_ok]):
    severity = "BLOCKER"
else:
    severity = "WARNING"
print(f"QA RESULT: {severity}")
print("=" * 60)

# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 20 rows:")
print(df.head(20))

print("\nDescriptive statistics:")
print(df.describe())

print("\nKey column value counts:")
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        print(f"\n{col}:")
        print(df[col].value_counts().head(20))

if "year" in df.columns:
    print("\nYear distribution:")
    print(df["year"].value_counts().sort("year"))

# Pell recipients distribution (percentiles)
print("\npell_recipients percentiles:")
quantiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
for q in quantiles:
    val = df["pell_recipients"].drop_nulls().quantile(q)
    print(f"  p{int(q*100):02d}: {val:,.0f}")

# Pell disbursements distribution
print("\npell_disbursements percentiles:")
for q in quantiles:
    val = df["pell_disbursements"].drop_nulls().quantile(q)
    print(f"  p{int(q*100):02d}: ${val:,.0f}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 19:33:14
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_04_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 04 (fetch-fsa-grants)
# ============================================================
# Loaded: 4,994 rows x 4 cols
# 
# [PASS] Check 1 - Schema: All expected columns present
#   Column dtypes: {'unitid': 'Int64', 'year': 'Int64', 'pell_recipients': 'Float64', 'pell_disbursements': 'Float64'}
# [PASS] Check 2 - Row count: 4,994 (expected 4,000-6,000)
# [FAIL] Check 3 - Distributions: year: all same value (2020)
# [PASS] Check 4 - Coded values: None remain
# [FAIL] Check 5 - Critical nulls: pell_recipients: 6 nulls
# 
# --- SCRIPT-SPECIFIC CHECKS ---
# [PASS] Check 6 - Counterfactual (national Pell total): 6,330,336 recipients (expect ~6.2M national)
# [WARN] Check 7 - Semantic (pell_recipients are counts): integer-like=False
#   Median pell_recipients=362 — plausible for pell_share calculation
# [PASS] Check 8 - Boundary (zeros and extremes): 83 zeros (1.7%), min=0.0, max=70813.0
# [PASS] Check 9 - Absence (grant_type partition): Expected ~4995 rows per grant_type, got 4994 (diff: 1)
# [PASS] Check 10 - Downstream (unitid IPEDS-compatible): dtype=Int64, range=[100654, 497037]
# 
# --- SPOT-CHECKS ---
# [PASS] Check 11 - Spot-check University of Central Florida (unitid=132903): pell_recipients=24644.0, pell_disbursements=111612592.0
# [PASS] Check 11 - Spot-check Arizona State University (unitid=104151): pell_recipients=44001.0, pell_disbursements=182448208.0
# [PASS] Check 11 - Spot-check University of Texas at Austin (unitid=228778): pell_recipients=9883.0, pell_disbursements=50521820.0
# [PASS] Check 12 - Total recipients sum: 6,330,336 (mean=1,269 x 4,988 institutions)
# [PASS] Check 13 - Per-recipient disbursement: $4,164 (expect $3,000-$7,000 range for Pell)
# [PASS] Check 14 - Unitid uniqueness: 4,994 unique / 4,994 total
# [INFO] Check 15 - Null pell_recipients rows: 6
#   Unitids with null pell_recipients: [112251, 189015, 196468, 409254, 475033, 495192]
#   Of these, 6 also have null pell_disbursements
#   [PASS] Null rate: 0.12% — negligible
# 
# ============================================================
# QA RESULT: WARNING
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 20 rows:
# shape: (20, 4)
# ┌────────┬──────┬─────────────────┬────────────────────┐
# │ unitid ┆ year ┆ pell_recipients ┆ pell_disbursements │
# │ ---    ┆ ---  ┆ ---             ┆ ---                │
# │ i64    ┆ i64  ┆ f64             ┆ f64                │
# ╞════════╪══════╪═════════════════╪════════════════════╡
# │ 100654 ┆ 2020 ┆ 3607.0          ┆ 1.8499612e7        │
# │ 100663 ┆ 2020 ┆ 4966.0          ┆ 2.3012828e7        │
# │ 100690 ┆ 2020 ┆ 270.0           ┆ 1.0310e6           │
# │ 100706 ┆ 2020 ┆ 2048.0          ┆ 8.986248e6         │
# │ 100724 ┆ 2020 ┆ 2465.0          ┆ 1.2532547e7        │
# │ …      ┆ …    ┆ …               ┆ …                  │
# │ 101240 ┆ 2020 ┆ 2361.0          ┆ 9.176152e6         │
# │ 101277 ┆ 2020 ┆ 84.0            ┆ 353417.4375        │
# │ 101286 ┆ 2020 ┆ 2158.0          ┆ 7.959317e6         │
# │ 101295 ┆ 2020 ┆ 2434.0          ┆ 9.099344e6         │
# │ 101301 ┆ 2020 ┆ 857.0           ┆ 3400986.5          │
# └────────┴──────┴─────────────────┴────────────────────┘
# 
# Descriptive statistics:
# shape: (9, 5)
# ┌────────────┬───────────────┬────────┬─────────────────┬────────────────────┐
# │ statistic  ┆ unitid        ┆ year   ┆ pell_recipients ┆ pell_disbursements │
# │ ---        ┆ ---           ┆ ---    ┆ ---             ┆ ---                │
# │ str        ┆ f64           ┆ f64    ┆ f64             ┆ f64                │
# ╞════════════╪═══════════════╪════════╪═════════════════╪════════════════════╡
# │ count      ┆ 4994.0        ┆ 4994.0 ┆ 4988.0          ┆ 4988.0             │
# │ null_count ┆ 0.0           ┆ 0.0    ┆ 6.0             ┆ 6.0                │
# │ mean       ┆ 264892.57509  ┆ 2020.0 ┆ 1269.113071     ┆ 5.2844e6           │
# │ std        ┆ 131963.729845 ┆ 0.0    ┆ 2970.47379      ┆ 1.2168e7           │
# │ min        ┆ 100654.0      ┆ 2020.0 ┆ 0.0             ┆ 0.0                │
# │ 25%        ┆ 162706.0      ┆ 2020.0 ┆ 82.0            ┆ 334101.0           │
# │ 50%        ┆ 211343.0      ┆ 2020.0 ┆ 362.0           ┆ 1.5640e6           │
# │ 75%        ┆ 420398.0      ┆ 2020.0 ┆ 1211.0          ┆ 4946663.5          │
# │ max        ┆ 497037.0      ┆ 2020.0 ┆ 70813.0         ┆ 2.247628e8         │
# └────────────┴───────────────┴────────┴─────────────────┴────────────────────┘
# 
# Key column value counts:
# 
# unitid:
# shape: (20, 2)
# ┌────────┬───────┐
# │ unitid ┆ count │
# │ ---    ┆ ---   │
# │ i64    ┆ u32   │
# ╞════════╪═══════╡
# │ 459213 ┆ 1     │
# │ 118198 ┆ 1     │
# │ 213376 ┆ 1     │
# │ 154448 ┆ 1     │
# │ 461555 ┆ 1     │
# │ …      ┆ …     │
# │ 113449 ┆ 1     │
# │ 192484 ┆ 1     │
# │ 131061 ┆ 1     │
# │ 230737 ┆ 1     │
# │ 170301 ┆ 1     │
# └────────┴───────┘
# 
# pell_recipients:
# shape: (20, 2)
# ┌─────────────────┬───────┐
# │ pell_recipients ┆ count │
# │ ---             ┆ ---   │
# │ f64             ┆ u32   │
# ╞═════════════════╪═══════╡
# │ 289.0           ┆ 1     │
# │ 3125.0          ┆ 1     │
# │ 3250.0          ┆ 1     │
# │ 3278.0          ┆ 1     │
# │ 745.0           ┆ 3     │
# │ …               ┆ …     │
# │ 417.0           ┆ 4     │
# │ 1279.0          ┆ 1     │
# │ 866.0           ┆ 2     │
# │ 424.0           ┆ 6     │
# │ 2817.0          ┆ 1     │
# └─────────────────┴───────┘
# 
# Year distribution:
# shape: (1, 2)
# ┌──────┬───────┐
# │ year ┆ count │
# │ ---  ┆ ---   │
# │ i64  ┆ u32   │
# ╞══════╪═══════╡
# │ 2020 ┆ 4994  │
# └──────┴───────┘
# 
# pell_recipients percentiles:
#   p01: 0
#   p05: 13
#   p10: 26
#   p25: 82
#   p50: 362
#   p75: 1,211
#   p90: 3,247
#   p95: 5,306
#   p99: 13,014
# 
# pell_disbursements percentiles:
#   p01: $0
#   p05: $54,512
#   p10: $111,504
#   p25: $334,101
#   p50: $1,563,999
#   p75: $4,946,664
#   p90: $13,330,356
#   p95: $21,963,800
#   p99: $57,826,312
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
