"""
Monte Carlo Simulation with Bootstrap Confidence Intervals

PURPOSE: Demonstrate Monte Carlo sampling and bootstrap CI methodology
METHODOLOGY: Draw 1000 samples from N(mu=50, sigma=10), compute sample mean,
             construct 95% bootstrap percentile CI via B=1000 resamples
OUTPUT: Parquet file with sample statistics, CI bounds, and bootstrap SE
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
RANDOM_SEED = 42
N_SAMPLES = 1000          # Number of observations to draw from normal distribution
MU = 50                   # Population mean parameter
SIGMA = 10                # Population standard deviation parameter
N_BOOTSTRAP = 1000        # Number of bootstrap resamples for CI estimation
CI_LEVEL = 0.95           # Nominal confidence level
ALPHA = 1 - CI_LEVEL      # Significance level for two-tailed interval

# --- Pre-State Capture ---
print("=" * 70)
print("MONTE CARLO SIMULATION WITH BOOTSTRAP CONFIDENCE INTERVALS")
print("=" * 70)
print(f"\nConfiguration:")
print(f"  Population distribution: N(mu={MU}, sigma={SIGMA})")
print(f"  Sample size: {N_SAMPLES}")
print(f"  Bootstrap resamples: {N_BOOTSTRAP}")
print(f"  Confidence level: {CI_LEVEL * 100:.0f}%")
print(f"  Random seed: {RANDOM_SEED}")

# --- Stage 1: Monte Carlo Sampling ---
print(f"\n{'=' * 70}")
print("STAGE 1: MONTE CARLO SAMPLING")
print(f"{'=' * 70}")

# INTENT: Generate random sample from a normal distribution to simulate
#         drawing data from a known population.
# REASONING: Monte Carlo simulation uses random sampling to study the
#            properties of estimators when the true DGP is known.
# ASSUMES: numpy's default_rng provides high-quality pseudo-random numbers;
#          the normal distribution is correctly parameterized.

rng = np.random.default_rng(RANDOM_SEED)
samples = rng.normal(loc=MU, scale=SIGMA, size=N_SAMPLES)

# Compute sample statistics from the drawn sample
sample_mean = np.mean(samples)
sample_sd = np.std(samples, ddof=1)  # ddof=1 for unbiased sample standard deviation

print(f"\nSamples drawn: {len(samples)}")
print(f"  Sample mean: {sample_mean:.4f}")
print(f"  Sample SD:   {sample_sd:.4f}")

# Validation: Confirm sample size and no non-finite values
assert len(samples) == N_SAMPLES, f"Expected {N_SAMPLES} samples, got {len(samples)}"
assert np.isfinite(samples).all(), "Non-finite values detected in samples"
print(f"  PASSED: Sample size correct, all values finite")

# --- Stage 2: Bootstrap Confidence Interval ---
print(f"\n{'=' * 70}")
print("STAGE 2: BOOTSTRAP PERCENTILE CONFIDENCE INTERVAL")
print(f"{'=' * 70}")

# INTENT: Construct a nonparametric bootstrap confidence interval for the
#         sample mean using the percentile method.
# REASONING: The bootstrap resamples the observed data with replacement to
#            approximate the sampling distribution of the mean without relying
#            on parametric assumptions (e.g., normality of the sample mean).
# ASSUMES: The original sample is representative of the population;
#          B=1000 resamples is sufficient for stable CI estimation.

bootstrap_means = np.empty(N_BOOTSTRAP)

for i in range(N_BOOTSTRAP):
    # INTENT: Draw one bootstrap resample (with replacement) of the same size
    #         as the original sample and compute its mean.
    # REASONING: Resampling with replacement from the observed data creates an
    #            empirical estimate of the sampling distribution.
    resample = rng.choice(samples, size=N_SAMPLES, replace=True)
    bootstrap_means[i] = np.mean(resample)

# Compute bootstrap standard error: standard deviation of bootstrap means
bootstrap_se = np.std(bootstrap_means, ddof=1)

# Extract percentile-based confidence interval bounds
# INTENT: The 2.5th and 97.5th percentiles of the bootstrap distribution give
#         the 95% confidence interval bounds.
# REASONING: The percentile method uses the empirical quantiles directly,
#            which is valid when the bootstrap distribution is approximately
#            symmetric and unbiased.
ci_lower = np.percentile(bootstrap_means, (ALPHA / 2) * 100)
ci_upper = np.percentile(bootstrap_means, (1 - ALPHA / 2) * 100)

print(f"\nBootstrap resamples completed: {N_BOOTSTRAP}")
print(f"  Bootstrap mean of means: {np.mean(bootstrap_means):.4f}")
print(f"  Bootstrap SE:            {bootstrap_se:.4f}")
print(f"")
print(f"  {CI_LEVEL * 100:.0f}% Percentile CI for population mean:")
print(f"    Lower bound (2.5th pctile): {ci_lower:.4f}")
print(f"    Upper bound (97.5th pctile): {ci_upper:.4f}")
print(f"    CI width:                    {ci_upper - ci_lower:.4f}")

# Validation: CI must contain the sample mean, and lower must be less than upper
assert ci_lower < sample_mean < ci_upper, (
    f"Sample mean {sample_mean:.4f} should fall within its own "
    f"bootstrap CI [{ci_lower:.4f}, {ci_upper:.4f}]"
)
assert ci_lower < ci_upper, f"CI lower bound {ci_lower} must be less than upper bound {ci_upper}"
print(f"  PASSED: Sample mean lies within CI, bounds are ordered")

# --- Stage 3: Compile Results into Polars DataFrame ---
print(f"\n{'=' * 70}")
print("STAGE 3: COMPILE RESULTS DATAFRAME")
print(f"{'=' * 70}")

# INTENT: Assemble all simulation outputs into a single-row DataFrame with
#         the exact column schema specified in the task definition.
# REASONING: A structured, column-named parquet file is the standard
#            intermediate format for downstream consumption and versioning.
# ASSUMES: All scalar values fit within their declared types.

results_df = pl.DataFrame({
    "sample_size": [N_SAMPLES],
    "sample_mean": [sample_mean],
    "sample_sd": [sample_sd],
    "ci_method": ["bootstrap_percentile"],
    "ci_level": [CI_LEVEL],
    "ci_lower": [ci_lower],
    "ci_upper": [ci_upper],
    "n_bootstrap": [N_BOOTSTRAP],
    "bootstrap_se": [bootstrap_se],
    "seed": [RANDOM_SEED],
})

# Verify DataFrame schema
print(f"\nResults DataFrame:")
print(f"  Shape: {results_df.shape}")
print(f"  Columns: {results_df.columns}")
print(f"  dtypes: {results_df.dtypes}")
print(f"\nContents:")
print(results_df)

# --- Stage 4: Persist to Parquet ---
print(f"\n{'=' * 70}")
print("STAGE 4: SAVE TO PARQUET")
print(f"{'=' * 70}")

# INTENT: Save the results as a parquet file for reproducibility and
#         downstream consumption.
# REASONING: Parquet is the standard DAAF format — efficient, typed,
#            and version-control-friendly.
# ASSUMES: Output directory exists and is writable.

output_dir = Path("/daaf/data/processed")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "monte_carlo_results.parquet"
results_df.write_parquet(output_path)

print(f"  File: {output_path}")
assert output_path.exists(), f"Output file was not created at {output_path}"
file_size = output_path.stat().st_size
print(f"  Size: {file_size:,} bytes")

# Verify round-trip integrity
read_back = pl.read_parquet(output_path)
assert read_back.shape == results_df.shape, "Shape mismatch on read-back"
assert read_back.columns == results_df.columns, "Column mismatch on read-back"
assert read_back.dtypes == results_df.dtypes, "Type mismatch on read-back"
print(f"  PASSED: Round-trip verification (shape, columns, types match)")

# --- Post-State Capture and Summary ---
print(f"\n{'=' * 70}")
print("EXECUTION SUMMARY")
print(f"{'=' * 70}")

print(f"\nInput Parameters:")
print(f"  Distribution:     N(mu={MU}, sigma={SIGMA})")
print(f"  Sample size:      {N_SAMPLES}")
print(f"  Bootstrap reps:   {N_BOOTSTRAP}")
print(f"  Confidence level: {CI_LEVEL * 100:.0f}%")

print(f"\nKey Results:")
print(f"  Sample mean:     {sample_mean:.4f}")
print(f"  Sample SD:       {sample_sd:.4f}")
print(f"  Bootstrap SE:    {bootstrap_se:.4f}")
print(f"  95% CI:          [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  CI width:        {ci_upper - ci_lower:.4f}")

print(f"\nOutput File:")
print(f"  Path:   {output_path}")
print(f"  Size:   {file_size:,} bytes")
print(f"  Rows:   {read_back.shape[0]}")
print(f"  Cols:   {read_back.shape[1]}")

print(f"\n{'=' * 70}")
print("SUCCESS: Monte Carlo simulation completed")
print(f"{'=' * 70}")

# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-09 01:15:17
# Command: python3 /daaf/scripts/adhoc/01_monte_carlo_bootstrap_a.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ======================================================================
# MONTE CARLO SIMULATION WITH BOOTSTRAP CONFIDENCE INTERVALS
# ======================================================================
# 
# Configuration:
#   Population distribution: N(mu=50, sigma=10)
#   Sample size: 1000
#   Bootstrap resamples: 1000
#   Confidence level: 95%
#   Random seed: 42
# 
# ======================================================================
# STAGE 1: MONTE CARLO SAMPLING
# ======================================================================
# 
# Samples drawn: 1000
#   Sample mean: 49.7111
#   Sample SD:   9.8922
#   PASSED: Sample size correct, all values finite
# 
# ======================================================================
# STAGE 2: BOOTSTRAP PERCENTILE CONFIDENCE INTERVAL
# ======================================================================
# 
# Bootstrap resamples completed: 1000
#   Bootstrap mean of means: 49.7174
#   Bootstrap SE:            0.3012
# 
#   95% Percentile CI for population mean:
#     Lower bound (2.5th pctile): 49.1059
#     Upper bound (97.5th pctile): 50.3107
#     CI width:                    1.2048
#   PASSED: Sample mean lies within CI, bounds are ordered
# 
# ======================================================================
# STAGE 3: COMPILE RESULTS DATAFRAME
# ======================================================================
# 
# Results DataFrame:
#   Shape: (1, 10)
#   Columns: ['sample_size', 'sample_mean', 'sample_sd', 'ci_method', 'ci_level', 'ci_lower', 'ci_upper', 'n_bootstrap', 'bootstrap_se', 'seed']
#   dtypes: [Int64, Float64, Float64, String, Float64, Float64, Float64, Int64, Float64, Int64]
# 
# Contents:
# shape: (1, 10)
# ┌────────────┬────────────┬───────────┬────────────┬───┬──────────┬────────────┬────────────┬──────┐
# │ sample_siz ┆ sample_mea ┆ sample_sd ┆ ci_method  ┆ … ┆ ci_upper ┆ n_bootstra ┆ bootstrap_ ┆ seed │
# │ e          ┆ n          ┆ ---       ┆ ---        ┆   ┆ ---      ┆ p          ┆ se         ┆ ---  │
# │ ---        ┆ ---        ┆ f64       ┆ str        ┆   ┆ f64      ┆ ---        ┆ ---        ┆ i64  │
# │ i64        ┆ f64        ┆           ┆            ┆   ┆          ┆ i64        ┆ f64        ┆      │
# ╞════════════╪════════════╪═══════════╪════════════╪═══╪══════════╪════════════╪════════════╪══════╡
# │ 1000       ┆ 49.711084  ┆ 9.892171  ┆ bootstrap_ ┆ … ┆ 50.3107  ┆ 1000       ┆ 0.3012     ┆ 42   │
# │            ┆            ┆           ┆ percentile ┆   ┆          ┆            ┆            ┆      │
# └────────────┴────────────┴───────────┴────────────┴───┴──────────┴────────────┴────────────┴──────┘
# 
# ======================================================================
# STAGE 4: SAVE TO PARQUET
# ======================================================================
#   File: /daaf/data/processed/monte_carlo_results.parquet
#   Size: 3,636 bytes
#   PASSED: Round-trip verification (shape, columns, types match)
# 
# ======================================================================
# EXECUTION SUMMARY
# ======================================================================
# 
# Input Parameters:
#   Distribution:     N(mu=50, sigma=10)
#   Sample size:      1000
#   Bootstrap reps:   1000
#   Confidence level: 95%
# 
# Key Results:
#   Sample mean:     49.7111
#   Sample SD:       9.8922
#   Bootstrap SE:    0.3012
#   95% CI:          [49.1059, 50.3107]
#   CI width:        1.2048
# 
# Output File:
#   Path:   /daaf/data/processed/monte_carlo_results.parquet
#   Size:   3,636 bytes
#   Rows:   1
#   Cols:   10
# 
# ======================================================================
# SUCCESS: Monte Carlo simulation completed
# ======================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
