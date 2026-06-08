#!/usr/bin/env python3
"""
DIAGNOSTIC: Investigate SchemaError in FIPS code join (type mismatch).

Issue: Polars SchemaError when joining school_data (Int64 state_fips) with
       state_poverty (String state_fips)
Error: polars.exceptions.SchemaError: datatypes of join keys don't match -
       `state_fips`: i64 on left does not match `state_fips`: str on right
Stage: Transform (join operation, line 38)

Hypothesis Testing Log:
1. Type mismatch between join keys -> TEST via dtype inspection
2. Value semantics require string representation (leading zeros) -> TEST via
   sample value comparison and FIPS code domain knowledge
3. Naive int cast would destroy leading zeros -> TEST via round-trip comparison
"""

import polars as pl

# --- Config ---
# INTENT: Reproduce and diagnose the SchemaError from join_type_mismatch.py
# REASONING: Must examine both DataFrames' state_fips columns to confirm the
# type mismatch and determine the correct cast direction
PROJECT_DIR = "/daaf/benchmarks/_sandbox/run_dc-07_Opus_4.6_0"

# --- Reproduce Source Data ---
# INTENT: Recreate the exact DataFrames from the failing script to test against
# ASSUMES: Same construction logic as join_type_mismatch.py lines 16-29
school_data = pl.DataFrame({
    "ncessch": [f"A{i:05d}" for i in range(100)],
    "state_fips": [i % 50 + 1 for i in range(100)],
    "school_name": [f"School_{i}" for i in range(100)],
    "enrollment": [200 + (i * 7) % 500 for i in range(100)],
})

state_poverty = pl.DataFrame({
    "state_fips": [f"{i:02d}" for i in range(1, 51)],
    "state_name": [f"State_{i}" for i in range(1, 51)],
    "poverty_rate": [10.0 + (i * 1.3) % 15 for i in range(1, 51)],
    "median_income": [45000 + i * 800 for i in range(1, 51)],
})

# ============================================================
# EVIDENCE COLLECTION (before forming hypotheses)
# ============================================================
print("=" * 60)
print("EVIDENCE COLLECTION")
print("=" * 60)

# Evidence 1: Data types of join key in both DataFrames
left_dtype = school_data["state_fips"].dtype
right_dtype = state_poverty["state_fips"].dtype
print(f"\nEvidence 1 - Join key dtypes:")
print(f"  school_data.state_fips dtype: {left_dtype}")
print(f"  state_poverty.state_fips dtype: {right_dtype}")
print(f"  Types match: {left_dtype == right_dtype}")

# Evidence 2: Sample values from both sides
left_sample = school_data["state_fips"].unique().sort().head(10).to_list()
right_sample = state_poverty["state_fips"].unique().sort().head(10).to_list()
print(f"\nEvidence 2 - Sample values (first 10 unique, sorted):")
print(f"  school_data (Int64): {left_sample}")
print(f"  state_poverty (String): {right_sample}")

# Evidence 3: Value ranges
print(f"\nEvidence 3 - Value ranges:")
print(f"  school_data min/max: {school_data['state_fips'].min()} / {school_data['state_fips'].max()}")
print(f"  state_poverty min/max: {state_poverty['state_fips'].min()} / {state_poverty['state_fips'].max()}")

# Evidence 4: Unique value counts
print(f"\nEvidence 4 - Unique values:")
print(f"  school_data: {school_data['state_fips'].n_unique()} unique")
print(f"  state_poverty: {state_poverty['state_fips'].n_unique()} unique")

# Evidence 5: Can we reproduce the error?
print(f"\nEvidence 5 - Reproduce error:")
try:
    result = school_data.join(state_poverty, on="state_fips", how="left")
    print(f"  Join succeeded (unexpected): {result.shape}")
except Exception as e:
    print(f"  Error reproduced: {type(e).__name__}: {e}")

# ============================================================
# HYPOTHESIS 1: Type mismatch is the proximate cause
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 1: Type mismatch (Int64 vs String) causes SchemaError")
print("=" * 60)
# INTENT: Confirm that the Int64 vs String mismatch is what Polars rejects
# REASONING: Polars is strict about join key types -- it does not auto-cast.
# This is by design: implicit casting can silently produce wrong results.

print(f"\nTest: Are the dtypes different?")
print(f"  Left dtype: {left_dtype} (is integer: {left_dtype.is_integer()})")
print(f"  Right dtype: {right_dtype} (is string: {right_dtype == pl.String or right_dtype == pl.Utf8})")
h1_confirmed = left_dtype != right_dtype
print(f"\nResult: {'CONFIRMED' if h1_confirmed else 'REFUTED'}")
print(f"  Polars requires exact type match on join keys.")
print(f"  Int64 != String, so SchemaError is raised before any value comparison.")

# ============================================================
# HYPOTHESIS 2: Cast direction matters -- int-to-string is correct
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 2: FIPS codes are identifiers, not numbers; must be strings")
print("=" * 60)
# INTENT: Determine the semantically correct cast direction for FIPS codes
# REASONING: FIPS codes are standardized identifiers with fixed-width format.
# State FIPS are 2-digit zero-padded codes (e.g., "01" = Alabama, "06" = California).
# Casting string->int would LOSE the leading zero: "01" -> 1, which is lossy
# and breaks any downstream operation expecting standard FIPS format.

# Test 2a: Does casting int->string with zero-padding recover the correct values?
left_as_str = school_data.with_columns(
    pl.col("state_fips").cast(pl.String).str.zfill(2).alias("state_fips_str")
)
print(f"\nTest 2a: Cast int -> zero-padded string")
print(f"  Sample conversions:")
for row in left_as_str.select("state_fips", "state_fips_str").unique().sort("state_fips").head(10).iter_rows():
    print(f"    {row[0]:>3d} -> '{row[1]}'")

# Test 2b: Does casting string->int lose information?
right_as_int = state_poverty.with_columns(
    pl.col("state_fips").cast(pl.Int64).alias("state_fips_int")
)
print(f"\nTest 2b: Cast string -> int (DEMONSTRATES INFORMATION LOSS)")
print(f"  Sample conversions:")
for row in right_as_int.select("state_fips", "state_fips_int").unique().sort("state_fips").head(10).iter_rows():
    print(f"    '{row[0]}' -> {row[1]:>3d}  (leading zero lost: {'YES' if row[0].startswith('0') else 'no'})")

# Test 2c: Count how many values have meaningful leading zeros
leading_zero_count = state_poverty.filter(
    pl.col("state_fips").str.starts_with("0")
).shape[0]
print(f"\nTest 2c: Values with leading zeros: {leading_zero_count} / {state_poverty.shape[0]}")
print(f"  These values would be corrupted by string->int conversion.")

h2_supported = True  # Domain knowledge confirms FIPS codes must be strings
print(f"\nResult: SUPPORTED")
print(f"  FIPS codes are identifiers, not quantities.")
print(f"  '01' (Alabama) is semantically distinct from 1.")
print(f"  The correct direction is: cast Int64 -> zero-padded String.")

# ============================================================
# HYPOTHESIS 3: The fix (int->padded string) produces correct join
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 3: Casting left side to zero-padded string fixes the join")
print("=" * 60)
# INTENT: Verify that the proposed fix actually resolves the SchemaError
# REASONING: Confirmation test -- the fix must (a) eliminate the error,
# (b) produce the expected number of rows, and (c) match correctly.

# INTENT: Cast the integer FIPS to zero-padded 2-character string
# REASONING: Standard FIPS state codes are 2 digits. zfill(2) ensures
# single-digit codes like 1 become "01" to match the string source.
# ASSUMES: All state_fips values in school_data are in range 1-50
school_data_fixed = school_data.with_columns(
    pl.col("state_fips").cast(pl.String).str.zfill(2)
)

print(f"\nFixed school_data state_fips dtype: {school_data_fixed['state_fips'].dtype}")
print(f"Fixed school_data sample: {school_data_fixed['state_fips'].unique().sort().head(5).to_list()}")
print(f"state_poverty sample:     {state_poverty['state_fips'].unique().sort().head(5).to_list()}")

# Test: Does the join now succeed?
try:
    result = school_data_fixed.join(state_poverty, on="state_fips", how="left")
    print(f"\nJoin succeeded: {result.shape[0]} rows x {result.shape[1]} columns")
    print(f"Expected rows: {school_data.shape[0]} (left join preserves all left rows)")
    rows_match = result.shape[0] == school_data.shape[0]
    print(f"Row count matches: {rows_match}")

    # Check for null matches (schools that did not find a poverty match)
    null_poverty = result.filter(pl.col("poverty_rate").is_null()).shape[0]
    print(f"Schools without poverty match: {null_poverty}")

    # Spot-check: Verify state 1 (FIPS "01") matched correctly
    state1_school = result.filter(pl.col("state_fips") == "01").head(1)
    state1_poverty = state_poverty.filter(pl.col("state_fips") == "01")
    print(f"\nSpot check - FIPS '01':")
    print(f"  School record: {state1_school.select('ncessch', 'state_fips', 'poverty_rate').to_dicts()}")
    print(f"  Poverty source: {state1_poverty.select('state_fips', 'poverty_rate').to_dicts()}")

    values_match = (
        state1_school["poverty_rate"][0] == state1_poverty["poverty_rate"][0]
    )
    print(f"  Values match: {values_match}")

    h3_confirmed = rows_match and null_poverty == 0 and values_match
    print(f"\nResult: {'CONFIRMED' if h3_confirmed else 'REFUTED'}")

except Exception as e:
    h3_confirmed = False
    print(f"\nJoin FAILED: {type(e).__name__}: {e}")
    print(f"Result: REFUTED -- fix did not resolve the error")

# ============================================================
# ADDITIONAL: Test the WRONG direction (string->int) to confirm it is inferior
# ============================================================
print("\n" + "=" * 60)
print("COUNTER-TEST: Casting right side to int (WRONG direction)")
print("=" * 60)
# INTENT: Demonstrate that casting string->int also fixes the join mechanically,
# but produces an inferior result because it destroys the canonical FIPS format.
# REASONING: Important to show the user WHY cast direction matters, not just
# that the join works.

state_poverty_as_int = state_poverty.with_columns(
    pl.col("state_fips").cast(pl.Int64)
)

try:
    result_wrong = school_data.join(state_poverty_as_int, on="state_fips", how="left")
    print(f"Join succeeded (both int): {result_wrong.shape[0]} rows")
    print(f"Null poverty matches: {result_wrong.filter(pl.col('poverty_rate').is_null()).shape[0]}")
    print(f"Result state_fips dtype: {result_wrong['state_fips'].dtype}")
    print(f"Result state_fips sample: {result_wrong['state_fips'].unique().sort().head(5).to_list()}")
    print(f"\nPROBLEM: state_fips is now Int64 in the output.")
    print(f"  Any downstream join to another dataset using string FIPS will FAIL again.")
    print(f"  Any display or export will show '1' instead of '01' (Alabama).")
    print(f"  This 'fix' creates a new problem downstream.")
except Exception as e:
    print(f"Join failed: {e}")

# ============================================================
# DIAGNOSIS SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("DIAGNOSIS SUMMARY")
print("=" * 60)
print(f"H1 (type mismatch causes error): CONFIRMED")
print(f"H2 (FIPS must be strings, not ints): SUPPORTED (domain knowledge)")
print(f"H3 (int->padded string fixes join): {'CONFIRMED' if h3_confirmed else 'REFUTED'}")

print(f"\nROOT CAUSE: school_data.state_fips is Int64 (from parquet/CCD source)")
print(f"while state_poverty.state_fips is String (from CSV/SAIPE source).")
print(f"Polars enforces strict type matching on join keys and raises SchemaError.")

print(f"\n" + "=" * 60)
print("RECOMMENDED FIX")
print("=" * 60)
print("""
# Cast integer FIPS to zero-padded 2-character string BEFORE the join.
# INTENT: Normalize state_fips to canonical 2-digit zero-padded string format.
# REASONING: FIPS codes are identifiers with fixed width. Leading zeros are
# semantically meaningful (e.g., "01" = Alabama). Integer representation
# destroys this information. Always normalize toward string, never toward int.
# ASSUMES: All state_fips values are valid 1-2 digit state FIPS codes.
school_data = school_data.with_columns(
    pl.col("state_fips").cast(pl.String).str.zfill(2)
)

# Then proceed with join as before:
analysis_df = school_data.join(
    state_poverty,
    on="state_fips",
    how="left",
)
""")

print("DEFENSIVE VALIDATIONS TO ADD:")
print("""
# 1. Pre-join type assertion
assert school_data["state_fips"].dtype == state_poverty["state_fips"].dtype, \\
    f"Type mismatch: {school_data['state_fips'].dtype} vs {state_poverty['state_fips'].dtype}"

# 2. Pre-join value overlap check
left_keys = set(school_data["state_fips"].unique().to_list())
right_keys = set(state_poverty["state_fips"].unique().to_list())
overlap = len(left_keys & right_keys)
overlap_pct = overlap / len(left_keys) * 100
print(f"Key overlap: {overlap}/{len(left_keys)} ({overlap_pct:.1f}%)")
assert overlap_pct > 50, f"Low key overlap ({overlap_pct:.1f}%) -- check FIPS formatting"

# 3. Post-join null check for left join
null_rate = analysis_df.filter(pl.col("poverty_rate").is_null()).shape[0] / len(analysis_df)
print(f"Unmatched rate: {null_rate:.1%}")
""")

print("\nDiagnostic complete.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 02:21:13
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-07_Opus_4.6_0/scripts/debug/01_diag-join-type-mismatch.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# EVIDENCE COLLECTION
# ============================================================
# 
# Evidence 1 - Join key dtypes:
#   school_data.state_fips dtype: Int64
#   state_poverty.state_fips dtype: String
#   Types match: False
# 
# Evidence 2 - Sample values (first 10 unique, sorted):
#   school_data (Int64): [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
#   state_poverty (String): ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10']
# 
# Evidence 3 - Value ranges:
#   school_data min/max: 1 / 50
#   state_poverty min/max: 01 / 50
# 
# Evidence 4 - Unique values:
#   school_data: 50 unique
#   state_poverty: 50 unique
# 
# Evidence 5 - Reproduce error:
#   Error reproduced: SchemaError: datatypes of join keys don't match - `state_fips`: i64 on left does not match `state_fips`: str on right (and no other type was available to cast to)
# 
# ============================================================
# HYPOTHESIS 1: Type mismatch (Int64 vs String) causes SchemaError
# ============================================================
# 
# Test: Are the dtypes different?
#   Left dtype: Int64 (is integer: True)
#   Right dtype: String (is string: True)
# 
# Result: CONFIRMED
#   Polars requires exact type match on join keys.
#   Int64 != String, so SchemaError is raised before any value comparison.
# 
# ============================================================
# HYPOTHESIS 2: FIPS codes are identifiers, not numbers; must be strings
# ============================================================
# 
# Test 2a: Cast int -> zero-padded string
#   Sample conversions:
#       1 -> '01'
#       2 -> '02'
#       3 -> '03'
#       4 -> '04'
#       5 -> '05'
#       6 -> '06'
#       7 -> '07'
#       8 -> '08'
#       9 -> '09'
#      10 -> '10'
# 
# Test 2b: Cast string -> int (DEMONSTRATES INFORMATION LOSS)
#   Sample conversions:
#     '01' ->   1  (leading zero lost: YES)
#     '02' ->   2  (leading zero lost: YES)
#     '03' ->   3  (leading zero lost: YES)
#     '04' ->   4  (leading zero lost: YES)
#     '05' ->   5  (leading zero lost: YES)
#     '06' ->   6  (leading zero lost: YES)
#     '07' ->   7  (leading zero lost: YES)
#     '08' ->   8  (leading zero lost: YES)
#     '09' ->   9  (leading zero lost: YES)
#     '10' ->  10  (leading zero lost: no)
# 
# Test 2c: Values with leading zeros: 9 / 50
#   These values would be corrupted by string->int conversion.
# 
# Result: SUPPORTED
#   FIPS codes are identifiers, not quantities.
#   '01' (Alabama) is semantically distinct from 1.
#   The correct direction is: cast Int64 -> zero-padded String.
# 
# ============================================================
# HYPOTHESIS 3: Casting left side to zero-padded string fixes the join
# ============================================================
# 
# Fixed school_data state_fips dtype: String
# Fixed school_data sample: ['01', '02', '03', '04', '05']
# state_poverty sample:     ['01', '02', '03', '04', '05']
# 
# Join succeeded: 100 rows x 7 columns
# Expected rows: 100 (left join preserves all left rows)
# Row count matches: True
# Schools without poverty match: 0
# 
# Spot check - FIPS '01':
#   School record: [{'ncessch': 'A00000', 'state_fips': '01', 'poverty_rate': 11.3}]
#   Poverty source: [{'state_fips': '01', 'poverty_rate': 11.3}]
#   Values match: True
# 
# Result: CONFIRMED
# 
# ============================================================
# COUNTER-TEST: Casting right side to int (WRONG direction)
# ============================================================
# Join succeeded (both int): 100 rows
# Null poverty matches: 0
# Result state_fips dtype: Int64
# Result state_fips sample: [1, 2, 3, 4, 5]
# 
# PROBLEM: state_fips is now Int64 in the output.
#   Any downstream join to another dataset using string FIPS will FAIL again.
#   Any display or export will show '1' instead of '01' (Alabama).
#   This 'fix' creates a new problem downstream.
# 
# ============================================================
# DIAGNOSIS SUMMARY
# ============================================================
# H1 (type mismatch causes error): CONFIRMED
# H2 (FIPS must be strings, not ints): SUPPORTED (domain knowledge)
# H3 (int->padded string fixes join): CONFIRMED
# 
# ROOT CAUSE: school_data.state_fips is Int64 (from parquet/CCD source)
# while state_poverty.state_fips is String (from CSV/SAIPE source).
# Polars enforces strict type matching on join keys and raises SchemaError.
# 
# ============================================================
# RECOMMENDED FIX
# ============================================================
# 
# # Cast integer FIPS to zero-padded 2-character string BEFORE the join.
# # INTENT: Normalize state_fips to canonical 2-digit zero-padded string format.
# # REASONING: FIPS codes are identifiers with fixed width. Leading zeros are
# # semantically meaningful (e.g., "01" = Alabama). Integer representation
# # destroys this information. Always normalize toward string, never toward int.
# # ASSUMES: All state_fips values are valid 1-2 digit state FIPS codes.
# school_data = school_data.with_columns(
#     pl.col("state_fips").cast(pl.String).str.zfill(2)
# )
# 
# # Then proceed with join as before:
# analysis_df = school_data.join(
#     state_poverty,
#     on="state_fips",
#     how="left",
# )
# 
# DEFENSIVE VALIDATIONS TO ADD:
# 
# # 1. Pre-join type assertion
# assert school_data["state_fips"].dtype == state_poverty["state_fips"].dtype, \
#     f"Type mismatch: {school_data['state_fips'].dtype} vs {state_poverty['state_fips'].dtype}"
# 
# # 2. Pre-join value overlap check
# left_keys = set(school_data["state_fips"].unique().to_list())
# right_keys = set(state_poverty["state_fips"].unique().to_list())
# overlap = len(left_keys & right_keys)
# overlap_pct = overlap / len(left_keys) * 100
# print(f"Key overlap: {overlap}/{len(left_keys)} ({overlap_pct:.1f}%)")
# assert overlap_pct > 50, f"Low key overlap ({overlap_pct:.1f}%) -- check FIPS formatting"
# 
# # 3. Post-join null check for left join
# null_rate = analysis_df.filter(pl.col("poverty_rate").is_null()).shape[0] / len(analysis_df)
# print(f"Unmatched rate: {null_rate:.1%}")
# 
# 
# Diagnostic complete.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
