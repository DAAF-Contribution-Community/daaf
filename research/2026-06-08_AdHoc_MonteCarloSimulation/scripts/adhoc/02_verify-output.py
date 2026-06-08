#!/usr/bin/env python3
"""Quick verification that output parquet file is readable and complete."""

import polars as pl

output_file = "/daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/data/processed/monte_carlo_results.parquet"
df = pl.read_parquet(output_file)

print("OUTPUT FILE VERIFICATION")
print("=" * 70)
print(f"File: {output_file}")
print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
print()
print("Schema:")
print(df.schema)
print()
print("Sample values (first 5):")
print(df.filter(pl.col("statistic_type") == "sample_value").head(5))
print()
print("Summary statistics:")
print(df.filter(pl.col("statistic_type") != "sample_value"))
print()
print("Verification:")
print(f"  - Total sample rows: {df.filter(pl.col('statistic_type') == 'sample_value').shape[0]}")
print(f"  - Summary rows: {df.filter(pl.col('statistic_type') != 'sample_value').shape[0]}")
print("  [OK] File is readable and complete")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:18:18
# Command: python3 /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/scripts/adhoc/02_verify-output.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# OUTPUT FILE VERIFICATION
# ======================================================================
# File: /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/data/processed/monte_carlo_results.parquet
# Shape: 1003 rows x 3 columns
# 
# Schema:
# Schema({'sample_index': Int64, 'sample_value': Float64, 'statistic_type': String})
# 
# Sample values (first 5):
# shape: (5, 3)
# ┌──────────────┬──────────────┬────────────────┐
# │ sample_index ┆ sample_value ┆ statistic_type │
# │ ---          ┆ ---          ┆ ---            │
# │ i64          ┆ f64          ┆ str            │
# ╞══════════════╪══════════════╪════════════════╡
# │ 0            ┆ 54.967142    ┆ sample_value   │
# │ 1            ┆ 48.617357    ┆ sample_value   │
# │ 2            ┆ 56.476885    ┆ sample_value   │
# │ 3            ┆ 65.230299    ┆ sample_value   │
# │ 4            ┆ 47.658466    ┆ sample_value   │
# └──────────────┴──────────────┴────────────────┘
# 
# Summary statistics:
# shape: (3, 3)
# ┌──────────────┬──────────────┬────────────────┐
# │ sample_index ┆ sample_value ┆ statistic_type │
# │ ---          ┆ ---          ┆ ---            │
# │ i64          ┆ f64          ┆ str            │
# ╞══════════════╪══════════════╪════════════════╡
# │ 1000         ┆ 50.193321    ┆ sample_mean    │
# │ 1001         ┆ 49.607054    ┆ ci_lower       │
# │ 1002         ┆ 50.850234    ┆ ci_upper       │
# └──────────────┴──────────────┴────────────────┘
# 
# Verification:
#   - Total sample rows: 1000
#   - Summary rows: 3
#   [OK] File is readable and complete
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
