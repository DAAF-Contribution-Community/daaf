#!/usr/bin/env python3
"""
QA INVESTIGATION: Stage 5 Step 09 -- Iteration 2

Reviewed script: scripts/stage5_fetch/09_fetch-sfa-grants.py
Prior QA script: scripts/cr/stage5_09_cr1.py

INVESTIGATION TRIGGER:
cr1 found: (1) Distribution check falsely flagged constant columns (year, ftpt,
level_of_study, degree_seeking, class_level) as issues -- these are expected for
year=2020 filtered FT/UG data. (2) type_of_aid=9 has exactly 6 rows per unitid
(income_levels 1-5, 99), and income_level=99 appears to be the total row.
(3) tuition_type has values [1, 99] within toa=9 but the math says 6 rows per
unitid matches 6 income_levels, so tuition_type must not be a multiplying dimension.

HYPOTHESIS:
(A) The constant columns (year, ftpt, etc.) are structurally expected, and the
    cr1 BLOCKER from the distribution check should be reclassified to INFO.
(B) income_level=99 is a verified total row: its number_receiving_grants equals
    the sum across income_levels 1-5 for each unitid.
(C) tuition_type varies by institution (some have tuition_type=1, others 99),
    NOT as a cross-product dimension with income_level.

EXPECTED OUTCOME:
- If CONFIRMED: The cleaning script can safely filter to type_of_aid=9,
  income_level=99 to get one row per unitid with total grant recipients.
- If REFUTED: More complex aggregation is needed for the Pell proxy.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_sfa_grants.parquet"

# --- Load ---
print("=" * 60)
print("QA INVESTIGATION: Stage 5 Step 09 -- Iteration 2")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
toa9 = df.filter(pl.col("type_of_aid") == 9)
print(f"Loaded: {len(df):,} rows total, {len(toa9):,} type_of_aid=9 rows")

# =====================================================================
# HYPOTHESIS A: Constant columns are structurally expected
# =====================================================================
print("\n" + "-" * 60)
print("HYPOTHESIS A: Constant columns structurally expected")
print("-" * 60)

# INTENT: Verify that ftpt=1, level_of_study=1, degree_seeking=1, class_level=1
# represent expected filtering by the data source (FT UG students only).
# REASONING: IPEDS SFA data is scoped to first-time, full-time, degree-seeking
# undergraduates. Constant values for these dimensions are expected, not errors.
constant_cols = {
    "year": 2020,
    "ftpt": 1,
    "level_of_study": 1,
    "degree_seeking": 1,
    "class_level": 1,
}

all_expected = True
for col, expected_val in constant_cols.items():
    actual_vals = df[col].unique().to_list()
    matches = len(actual_vals) == 1 and actual_vals[0] == expected_val
    status = "CONFIRMED" if matches else "UNEXPECTED"
    if not matches:
        all_expected = False
    print(f"  {col}: unique values = {actual_vals} -- {status}")

print(f"\n  Hypothesis A: {'CONFIRMED' if all_expected else 'REFUTED'}")
print(f"  Implication: Distribution check BLOCKER should be reclassified to INFO")

# =====================================================================
# HYPOTHESIS B: income_level=99 is a total row
# =====================================================================
print("\n" + "-" * 60)
print("HYPOTHESIS B: income_level=99 is a verified total row")
print("-" * 60)

# INTENT: For a sample of unitids, verify that income_level=99 recipients
# equals the sum of income_levels 1-5.
# REASONING: If il=99 is the total, the cleaning script can filter to it directly.
# If it's something else (e.g., "unknown income"), aggregation logic changes.
sample_unitids = sorted(toa9["unitid"].unique().to_list())[:20]

mismatches = 0
matches = 0
close_matches = 0  # within 5%

print(f"  Testing {len(sample_unitids)} unitids:")
for uid in sample_unitids:
    uid_data = toa9.filter(pl.col("unitid") == uid)
    il99_recip = uid_data.filter(pl.col("income_level") == 99)["number_receiving_grants"].item()
    il_parts_recip = uid_data.filter(pl.col("income_level") != 99)["number_receiving_grants"].sum()

    il99_students = uid_data.filter(pl.col("income_level") == 99)["number_of_students"].item()
    il_parts_students = uid_data.filter(pl.col("income_level") != 99)["number_of_students"].sum()

    recip_match = il99_recip == il_parts_recip
    students_match = il99_students == il_parts_students

    if recip_match:
        matches += 1
    elif il_parts_recip > 0 and abs(il99_recip - il_parts_recip) / il_parts_recip < 0.05:
        close_matches += 1
    else:
        mismatches += 1

    if uid in sample_unitids[:5]:  # Show detail for first 5
        print(f"    unitid={uid}: il99_recip={il99_recip}, sum(il1-5)={il_parts_recip} "
              f"({'MATCH' if recip_match else 'CLOSE' if il_parts_recip > 0 and abs(il99_recip - il_parts_recip) / il_parts_recip < 0.05 else 'MISMATCH'})")
        print(f"                   il99_students={il99_students}, sum(il1-5)={il_parts_students} "
              f"({'MATCH' if students_match else 'MISMATCH'})")

print(f"\n  Results across {len(sample_unitids)} unitids:")
print(f"    Exact match: {matches}")
print(f"    Close match (<5%): {close_matches}")
print(f"    Mismatch: {mismatches}")

hypothesis_b = matches + close_matches >= len(sample_unitids) * 0.9
print(f"\n  Hypothesis B: {'CONFIRMED' if hypothesis_b else 'REFUTED'}")
if hypothesis_b:
    print(f"  Implication: Filter to income_level=99 for per-institution total")

# Now verify at scale: all 5,320 unitids
print(f"\n  Full-scale verification (all {toa9['unitid'].n_unique():,} unitids):")

il99 = toa9.filter(pl.col("income_level") == 99).select(
    "unitid", pl.col("number_receiving_grants").alias("il99_recip")
)
il_parts = (
    toa9.filter(pl.col("income_level") != 99)
    .group_by("unitid")
    .agg(pl.col("number_receiving_grants").sum().alias("parts_recip"))
)
compare = il99.join(il_parts, on="unitid", how="inner")
compare = compare.with_columns(
    (pl.col("il99_recip") == pl.col("parts_recip")).alias("exact_match"),
    ((pl.col("il99_recip") - pl.col("parts_recip")).abs()).alias("abs_diff"),
)

exact_match_count = compare["exact_match"].sum()
total_compared = len(compare)
print(f"    Exact matches: {exact_match_count:,} / {total_compared:,} ({exact_match_count/total_compared*100:.1f}%)")

if exact_match_count < total_compared:
    nonmatches = compare.filter(~pl.col("exact_match"))
    print(f"    Non-exact matches: {len(nonmatches):,}")
    print(f"    Max abs difference: {nonmatches['abs_diff'].max()}")
    print(f"    Mean abs difference: {nonmatches['abs_diff'].mean():.1f}")

# =====================================================================
# HYPOTHESIS C: tuition_type varies by institution, not as cross-dimension
# =====================================================================
print("\n" + "-" * 60)
print("HYPOTHESIS C: tuition_type varies by institution")
print("-" * 60)

# INTENT: Determine whether tuition_type=1 vs 99 splits institutions into
# separate groups, or creates multiple rows per (unitid, income_level).
# REASONING: If tuition_type creates a cross-product with income_level,
# some institutions would have 12 rows (6 IL * 2 TT). The cr1 finding
# that ALL unitids have exactly 6 rows means tuition_type must be constant
# per institution.

# Check: does each unitid have exactly one tuition_type value?
tt_per_uid = (
    toa9.group_by("unitid")
    .agg(pl.col("tuition_type").n_unique().alias("n_tt"))
)
n_multi_tt = (tt_per_uid["n_tt"] > 1).sum()
n_single_tt = (tt_per_uid["n_tt"] == 1).sum()

print(f"  Unitids with single tuition_type: {n_single_tt:,}")
print(f"  Unitids with multiple tuition_types: {n_multi_tt:,}")

# What's the split?
tt_dist = (
    toa9.select("unitid", "tuition_type").unique()
    .group_by("tuition_type")
    .agg(pl.col("unitid").n_unique().alias("n_unitids"))
    .sort("tuition_type")
)
print(f"\n  tuition_type distribution across institutions:")
for row in tt_dist.iter_rows(named=True):
    print(f"    tuition_type={row['tuition_type']}: {row['n_unitids']:,} unitids")

hypothesis_c = n_multi_tt == 0
print(f"\n  Hypothesis C: {'CONFIRMED' if hypothesis_c else 'REFUTED'}")
if hypothesis_c:
    print(f"  Implication: tuition_type is an institution-level attribute, not a row-multiplier")
    print(f"  Downstream: No additional filtering on tuition_type needed for aggregation")

# =====================================================================
# ADDITIONAL: Verify income_level=99 gives exactly 1 row per unitid
# =====================================================================
print("\n" + "-" * 60)
print("ADDITIONAL: income_level=99 uniqueness check")
print("-" * 60)

toa9_il99 = toa9.filter(pl.col("income_level") == 99)
n_rows = len(toa9_il99)
n_uids = toa9_il99["unitid"].n_unique()
print(f"  type_of_aid=9, income_level=99: {n_rows:,} rows, {n_uids:,} unique unitids")
is_1_to_1 = n_rows == n_uids
print(f"  1:1 (unitid to row): {'YES' if is_1_to_1 else 'NO'}")

if is_1_to_1:
    # Show summary of this slice -- this is what downstream cleaning will use
    print(f"\n  Summary of the usable slice (toa=9, il=99):")
    recip = toa9_il99["number_receiving_grants"]
    print(f"    Rows: {len(toa9_il99):,}")
    print(f"    number_receiving_grants: min={recip.min()}, median={recip.median()}, "
          f"mean={recip.mean():.1f}, max={recip.max()}")
    print(f"    Zeros: {(recip == 0).sum():,}")
    print(f"    Nulls: {recip.null_count()}")

# =====================================================================
# INTERPRETATION
# =====================================================================
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

confirmed = all([all_expected, hypothesis_b, hypothesis_c, is_1_to_1])
print(f"\nAll hypotheses: {'CONFIRMED' if confirmed else 'PARTIALLY CONFIRMED'}")

if confirmed:
    implications = (
        "The cr1 BLOCKER from distribution check was a false positive -- constant columns "
        "are structurally expected. The data structure is well-understood: "
        "type_of_aid=9, income_level=99 gives exactly 1 row per institution with total "
        "grant recipients. tuition_type is per-institution, not a row-multiplier. "
        "The cleaning script should filter to type_of_aid=9, income_level=99."
    )
else:
    implications = "Some hypotheses refuted -- further investigation needed."

print(f"Implications: {implications}")
print(f"Further investigation needed: NO")
print(f"Severity assessment: INFO (cr1 BLOCKER reclassified -- false positive on distribution check)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 23:14:56
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_09_cr2.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INVESTIGATION: Stage 5 Step 09 -- Iteration 2
# ============================================================
# Loaded: 37,292 rows total, 31,920 type_of_aid=9 rows
# 
# ------------------------------------------------------------
# HYPOTHESIS A: Constant columns structurally expected
# ------------------------------------------------------------
#   year: unique values = [2020] -- CONFIRMED
#   ftpt: unique values = [1] -- CONFIRMED
#   level_of_study: unique values = [1] -- CONFIRMED
#   degree_seeking: unique values = [1] -- CONFIRMED
#   class_level: unique values = [1] -- CONFIRMED
# 
#   Hypothesis A: CONFIRMED
#   Implication: Distribution check BLOCKER should be reclassified to INFO
# 
# ------------------------------------------------------------
# HYPOTHESIS B: income_level=99 is a verified total row
# ------------------------------------------------------------
#   Testing 20 unitids:
#     unitid=100654: il99_recip=642, sum(il1-5)=642 (MATCH)
#                    il99_students=657, sum(il1-5)=657 (MATCH)
#     unitid=100663: il99_recip=992, sum(il1-5)=992 (MATCH)
#                    il99_students=1053, sum(il1-5)=1053 (MATCH)
#     unitid=100706: il99_recip=492, sum(il1-5)=492 (MATCH)
#                    il99_students=515, sum(il1-5)=515 (MATCH)
#     unitid=100724: il99_recip=389, sum(il1-5)=389 (MATCH)
#                    il99_students=418, sum(il1-5)=418 (MATCH)
#     unitid=100751: il99_recip=1245, sum(il1-5)=1245 (MATCH)
#                    il99_students=1360, sum(il1-5)=1360 (MATCH)
# 
#   Results across 20 unitids:
#     Exact match: 20
#     Close match (<5%): 0
#     Mismatch: 0
# 
#   Hypothesis B: CONFIRMED
#   Implication: Filter to income_level=99 for per-institution total
# 
#   Full-scale verification (all 5,320 unitids):
#     Exact matches: 5,320 / 5,320 (100.0%)
# 
# ------------------------------------------------------------
# HYPOTHESIS C: tuition_type varies by institution
# ------------------------------------------------------------
#   Unitids with single tuition_type: 5,320
#   Unitids with multiple tuition_types: 0
# 
#   tuition_type distribution across institutions:
#     tuition_type=1: 1,821 unitids
#     tuition_type=99: 3,499 unitids
# 
#   Hypothesis C: CONFIRMED
#   Implication: tuition_type is an institution-level attribute, not a row-multiplier
#   Downstream: No additional filtering on tuition_type needed for aggregation
# 
# ------------------------------------------------------------
# ADDITIONAL: income_level=99 uniqueness check
# ------------------------------------------------------------
#   type_of_aid=9, income_level=99: 5,320 rows, 5,320 unique unitids
#   1:1 (unitid to row): YES
# 
#   Summary of the usable slice (toa=9, il=99):
#     Rows: 5,320
#     number_receiving_grants: min=0, median=77.0, mean=222.7, max=4519
#     Zeros: 11
#     Nulls: 0
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# All hypotheses: CONFIRMED
# Implications: The cr1 BLOCKER from distribution check was a false positive -- constant columns are structurally expected. The data structure is well-understood: type_of_aid=9, income_level=99 gives exactly 1 row per institution with total grant recipients. tuition_type is per-institution, not a row-multiplier. The cleaning script should filter to type_of_aid=9, income_level=99.
# Further investigation needed: NO
# Severity assessment: INFO (cr1 BLOCKER reclassified -- false positive on distribution check)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
