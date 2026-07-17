"""
Test fixture: Join type mismatch between integer and string FIPS codes.
Simulates a common data integration bug where CCD numeric FIPS codes
cannot join against CSV-sourced string FIPS codes with leading zeros.
"""
import polars as pl

# --- Config ---
# INTENT: Merge school-level enrollment with state-level poverty estimates
# REASONING: Need poverty context for school analysis; SAIPE provides state poverty rates
PROJECT_DIR = "/tmp/daaf_test_join"

# --- Load ---
# INTENT: Build synthetic school enrollment data (mimics CCD extract)
# ASSUMES: state_fips arrives as integer from parquet-based CCD source
school_data = pl.DataFrame({
    "ncessch": [f"A{i:05d}" for i in range(100)],
    "state_fips": [i % 50 + 1 for i in range(100)],  # Int64 range 1-50
    "school_name": [f"School_{i}" for i in range(100)],
    "enrollment": [200 + (i * 7) % 500 for i in range(100)],
})

# INTENT: Build synthetic state poverty data (mimics SAIPE CSV extract)
# ASSUMES: state_fips preserved as string from CSV with leading zeros
state_poverty = pl.DataFrame({
    "state_fips": [f"{i:02d}" for i in range(1, 51)],  # Utf8 "01".."50"
    "state_name": [f"State_{i}" for i in range(1, 51)],
    "poverty_rate": [10.0 + (i * 1.3) % 15 for i in range(1, 51)],
    "median_income": [45000 + i * 800 for i in range(1, 51)],
})

print(f"School data: {school_data.shape[0]} rows, state_fips dtype: {school_data['state_fips'].dtype}")
print(f"State poverty: {state_poverty.shape[0]} rows, state_fips dtype: {state_poverty['state_fips'].dtype}")

# --- Transform ---
# INTENT: Left join to attach poverty context to each school record
# REASONING: Left join preserves all schools even if poverty data missing for some states
analysis_df = school_data.join(
    state_poverty,
    on="state_fips",
    how="left",
)

# --- Validate ---
print(f"Joined result: {analysis_df.shape[0]} rows, {analysis_df.shape[1]} columns")
assert analysis_df.shape[0] == school_data.shape[0], "Row count changed after left join"
null_poverty = analysis_df.filter(pl.col("poverty_rate").is_null()).shape[0]
print(f"Schools without poverty match: {null_poverty}")

# --- Save ---
print("Join complete. Analysis dataframe ready for downstream modeling.")

# EXECUTION OUTPUT:
# School data: 100 rows, state_fips dtype: Int64
# State poverty: 50 rows, state_fips dtype: String
# Traceback (most recent call last):
#   File "/daaf/benchmarks/datasets/test_fixtures/debugger/join_type_mismatch.py", line 38, in <module>
#     analysis_df = school_data.join(
#                   ^^^^^^^^^^^^^^^^^
#   ...
# polars.exceptions.SchemaError: datatypes of join keys don't match -
#   `state_fips`: i64 on left does not match `state_fips`: str on right
#   (and no other type was available to cast to)
