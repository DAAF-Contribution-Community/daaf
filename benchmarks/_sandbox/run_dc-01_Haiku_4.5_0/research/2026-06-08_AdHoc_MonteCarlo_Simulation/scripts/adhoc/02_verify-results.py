#!/usr/bin/env python3
"""Verification script for Monte Carlo results parquet file."""

import polars as pl

parquet_path = "/daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_0/research/2026-06-08_AdHoc_MonteCarlo_Simulation/data/processed/montecarlo_results.parquet"

df = pl.read_parquet(parquet_path)

print("Parquet File Contents Summary:")
print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
print(f"  Columns: {df.columns}")
print()
print("First 5 rows:")
print(df.head())
print()
print("Summary Statistics:")
print(f"  Sample Mean (constant): {df['sample_mean'].unique().item():.6f}")
print(f"  CI Lower (constant): {df['ci_lower'].unique().item():.6f}")
print(f"  CI Upper (constant): {df['ci_upper'].unique().item():.6f}")
print(f"  Original Samples - Mean: {df['original_sample'].mean():.6f}")
print(f"  Original Samples - Min: {df['original_sample'].min():.6f}")
print(f"  Original Samples - Max: {df['original_sample'].max():.6f}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:24:39
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_0/research/2026-06-08_AdHoc_MonteCarlo_Simulation/scripts/adhoc/02_verify-results.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Parquet File Contents Summary:
#   Shape: 1000 rows × 5 columns
#   Columns: ['sample_index', 'original_sample', 'sample_mean', 'ci_lower', 'ci_upper']
# 
# First 5 rows:
# shape: (5, 5)
# ┌──────────────┬─────────────────┬─────────────┬───────────┬───────────┐
# │ sample_index ┆ original_sample ┆ sample_mean ┆ ci_lower  ┆ ci_upper  │
# │ ---          ┆ ---             ┆ ---         ┆ ---       ┆ ---       │
# │ i64          ┆ f64             ┆ f64         ┆ f64       ┆ f64       │
# ╞══════════════╪═════════════════╪═════════════╪═══════════╪═══════════╡
# │ 0            ┆ 54.967142       ┆ 50.193321   ┆ 49.594178 ┆ 50.812164 │
# │ 1            ┆ 48.617357       ┆ 50.193321   ┆ 49.594178 ┆ 50.812164 │
# │ 2            ┆ 56.476885       ┆ 50.193321   ┆ 49.594178 ┆ 50.812164 │
# │ 3            ┆ 65.230299       ┆ 50.193321   ┆ 49.594178 ┆ 50.812164 │
# │ 4            ┆ 47.658466       ┆ 50.193321   ┆ 49.594178 ┆ 50.812164 │
# └──────────────┴─────────────────┴─────────────┴───────────┴───────────┘
# 
# Summary Statistics:
#   Sample Mean (constant): 50.193321
#   CI Lower (constant): 49.594178
#   CI Upper (constant): 50.812164
#   Original Samples - Mean: 50.193321
#   Original Samples - Min: 17.587327
#   Original Samples - Max: 88.527315
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
