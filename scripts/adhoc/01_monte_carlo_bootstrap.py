"""
Monte Carlo Simulation with Bootstrap Confidence Intervals

PURPOSE: Demonstrate Monte Carlo sampling and bootstrap CI methodology
METHODOLOGY: Draw 1000 samples from N(50,10), compute sample mean,
             construct 95% bootstrap CI via resampling
OUTPUT: Parquet file with mean, CI bounds, and sample statistics
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
RANDOM_SEED = 42
N_SAMPLES = 1000          # Number of samples to draw from normal distribution
MU = 50                   # Population mean
SIGMA = 10                # Population std deviation
N_BOOTSTRAP = 10000       # Number of bootstrap resamples
CI_LEVEL = 0.95          # Confidence level
ALPHA = 1 - CI_LEVEL     # Significance level (two-tailed)

# --- Pre-State Capture ---
print("="*70)
print("MONTE CARLO SIMULATION WITH BOOTSTRAP CONFIDENCE INTERVALS")
print("="*70)
print(f"\nConfiguration:")
print(f"  Population distribution: N(μ={MU}, σ={SIGMA})")
print(f"  Samples to draw: {N_SAMPLES}")
print(f"  Bootstrap resamples: {N_BOOTSTRAP}")
print(f"  Confidence level: {CI_LEVEL*100:.0f}%")

# --- Stage 1: Monte Carlo Sampling ---
print(f"\n{'='*70}")
print("STAGE 1: MONTE CARLO SAMPLING")
print(f"{'='*70}")

# INTENT: Generate random samples from normal distribution
# REASONING: Monte Carlo method uses random sampling to estimate
#           properties of a probability distribution
# ASSUMES: numpy.random.Generator provides adequate randomness,
#         normal distribution is valid model

np.random.seed(RANDOM_SEED)
rng = np.random.default_rng(RANDOM_SEED)
samples = rng.normal(loc=MU, scale=SIGMA, size=N_SAMPLES)

# Capture sample statistics
sample_mean = np.mean(samples)
sample_std = np.std(samples, ddof=1)  # unbiased estimator
sample_median = np.median(samples)
sample_min = np.min(samples)
sample_max = np.max(samples)

print(f"\nSamples drawn: {len(samples)}")
print(f"  Mean: {sample_mean:.4f}")
print(f"  Std Dev: {sample_std:.4f}")
print(f"  Median: {sample_median:.4f}")
print(f"  Min: {sample_min:.4f}")
print(f"  Max: {sample_max:.4f}")

# Validation: Confirm samples match expected distribution
assert len(samples) == N_SAMPLES, f"Expected {N_SAMPLES} samples, got {len(samples)}"
assert np.isfinite(samples).all(), "Found non-finite values in samples"
print(f"✓ Sampling validation passed")

# --- Stage 2: Bootstrap Confidence Interval ---
print(f"\n{'='*70}")
print("STAGE 2: BOOTSTRAP CONFIDENCE INTERVAL ESTIMATION")
print(f"{'='*70}")

# INTENT: Construct empirical bootstrap CI for the sample mean
# REASONING: Bootstrap resamples the observed data to estimate the
#           sampling distribution of the mean without parametric assumptions
# ASSUMES: Original sample is representative; resampling with replacement
#         approximates the true sampling distribution
# METHODOLOGY: For each bootstrap resample:
#   1. Sample N_SAMPLES values with replacement from the original samples
#   2. Compute mean of that resample
#   3. Collect all bootstrap means
#   4. Extract percentiles as CI bounds

bootstrap_means = np.empty(N_BOOTSTRAP)

for i in range(N_BOOTSTRAP):
    # INTENT: Draw one bootstrap resample (with replacement)
    # REASONING: With-replacement resampling from observed data creates
    #           empirical distribution of possible sample means
    resample = rng.choice(samples, size=N_SAMPLES, replace=True)
    bootstrap_means[i] = np.mean(resample)

# Extract percentile-based confidence interval
# INTENT: Compute 95% CI using empirical percentile method
# REASONING: The 2.5th and 97.5th percentiles of bootstrap means
#           approximate the bounds of the sampling distribution
ci_lower = np.percentile(bootstrap_means, (ALPHA/2)*100)
ci_upper = np.percentile(bootstrap_means, (1-ALPHA/2)*100)

print(f"\nBootstrap resamples completed: {N_BOOTSTRAP}")
print(f"Bootstrap mean of means: {np.mean(bootstrap_means):.4f}")
print(f"Bootstrap std of means: {np.std(bootstrap_means):.4f}")
print(f"\n{CI_LEVEL*100:.0f}% Confidence Interval for Mean:")
print(f"  Lower bound (2.5th percentile): {ci_lower:.4f}")
print(f"  Upper bound (97.5th percentile): {ci_upper:.4f}")
print(f"  CI width: {ci_upper - ci_lower:.4f}")

# Validation: CI bounds are reasonable
assert ci_lower < sample_mean < ci_upper, \
    "Sample mean should fall within its own bootstrap CI"
assert ci_lower < ci_upper, "CI lower bound must be less than upper bound"
print(f"✓ Bootstrap CI validation passed")

# --- Stage 3: Data Aggregation and Preparation ---
print(f"\n{'='*70}")
print("STAGE 3: RESULTS AGGREGATION")
print(f"{'='*70}")

# INTENT: Compile all results into a structured dataset
# REASONING: Consolidating results in parquet enables reproducible
#           documentation and downstream analysis
# ASSUMES: Results are conceptually grouped as one record

results_dict = {
    "sample_mean": [sample_mean],
    "sample_std": [sample_std],
    "sample_median": [sample_median],
    "sample_min": [sample_min],
    "sample_max": [sample_max],
    "ci_lower_95": [ci_lower],
    "ci_upper_95": [ci_upper],
    "ci_width": [ci_upper - ci_lower],
    "n_samples": [N_SAMPLES],
    "n_bootstrap_resamples": [N_BOOTSTRAP],
    "random_seed": [RANDOM_SEED],
}

# Convert to Polars DataFrame
results_df = pl.DataFrame(results_dict)

print(f"\nResults DataFrame:")
print(f"  Shape: {results_df.shape}")
print(f"  Columns: {results_df.columns}")
print(f"\nResults:")
print(results_df)

# --- Stage 4: File Persistence ---
print(f"\n{'='*70}")
print("STAGE 4: SAVING RESULTS TO PARQUET")
print(f"{'='*70}")

# Create output directory if it doesn't exist
output_dir = Path("/daaf/data/processed")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "monte_carlo_results.parquet"

# INTENT: Persist results in parquet format for reproducibility
# REASONING: Parquet provides efficient columnar storage, enables
#           version control, and supports downstream analysis
# ASSUMES: Output directory is writable and has sufficient disk space

results_df.write_parquet(output_path)

print(f"Results saved to: {output_path}")
assert output_path.exists(), f"Output file not created at {output_path}"
print(f"✓ File persistence validation passed")

# Verify file contents by reading back
read_back = pl.read_parquet(output_path)
assert read_back.shape == results_df.shape, "Read-back shape mismatch"
assert read_back.columns == results_df.columns, "Read-back columns mismatch"
print(f"✓ Read-back verification passed")

# --- Post-State Capture and Summary ---
print(f"\n{'='*70}")
print("EXECUTION SUMMARY")
print(f"{'='*70}")

print(f"\nInput Parameters:")
print(f"  Distribution: N({MU}, {SIGMA})")
print(f"  Sample size: {N_SAMPLES}")
print(f"  Bootstrap resamples: {N_BOOTSTRAP}")

print(f"\nKey Results:")
print(f"  Sample mean: {sample_mean:.4f}")
print(f"  Sample std: {sample_std:.4f}")
print(f"  95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  CI width: {ci_upper - ci_lower:.4f}")

print(f"\nOutput File:")
print(f"  Path: {output_path}")
print(f"  Size: {output_path.stat().st_size:,} bytes")
print(f"  Rows: {read_back.shape[0]}")
print(f"  Columns: {read_back.shape[1]}")

print(f"\n{'='*70}")
print("SUCCESS: Monte Carlo simulation completed")
print(f"{'='*70}\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 20:01:31
# Command: python3 /daaf/scripts/adhoc/01_monte_carlo_bootstrap.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ======================================================================
# MONTE CARLO SIMULATION WITH BOOTSTRAP CONFIDENCE INTERVALS
# ======================================================================
# 
# Configuration:
#   Population distribution: N(μ=50, σ=10)
#   Samples to draw: 1000
#   Bootstrap resamples: 10000
#   Confidence level: 95%
# 
# ======================================================================
# STAGE 1: MONTE CARLO SAMPLING
# ======================================================================
# 
# Samples drawn: 1000
#   Mean: 49.7111
#   Std Dev: 9.8922
#   Median: 50.0618
#   Min: 13.5159
#   Max: 81.7885
# ✓ Sampling validation passed
# 
# ======================================================================
# STAGE 2: BOOTSTRAP CONFIDENCE INTERVAL ESTIMATION
# ======================================================================
# 
# Bootstrap resamples completed: 10000
# Bootstrap mean of means: 49.7078
# Bootstrap std of means: 0.3125
# 
# 95% Confidence Interval for Mean:
#   Lower bound (2.5th percentile): 49.0882
#   Upper bound (97.5th percentile): 50.3239
#   CI width: 1.2357
# ✓ Bootstrap CI validation passed
# 
# ======================================================================
# STAGE 3: RESULTS AGGREGATION
# ======================================================================
# 
# Results DataFrame:
#   Shape: (1, 11)
#   Columns: ['sample_mean', 'sample_std', 'sample_median', 'sample_min', 'sample_max', 'ci_lower_95', 'ci_upper_95', 'ci_width', 'n_samples', 'n_bootstrap_resamples', 'random_seed']
# 
# Results:
# shape: (1, 11)
# ┌───────────┬───────────┬───────────┬───────────┬───┬──────────┬───────────┬───────────┬───────────┐
# │ sample_me ┆ sample_st ┆ sample_me ┆ sample_mi ┆ … ┆ ci_width ┆ n_samples ┆ n_bootstr ┆ random_se │
# │ an        ┆ d         ┆ dian      ┆ n         ┆   ┆ ---      ┆ ---       ┆ ap_resamp ┆ ed        │
# │ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ f64      ┆ i64       ┆ les       ┆ ---       │
# │ f64       ┆ f64       ┆ f64       ┆ f64       ┆   ┆          ┆           ┆ ---       ┆ i64       │
# │           ┆           ┆           ┆           ┆   ┆          ┆           ┆ i64       ┆           │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪══════════╪═══════════╪═══════════╪═══════════╡
# │ 49.711084 ┆ 9.892171  ┆ 50.061779 ┆ 13.515872 ┆ … ┆ 1.235739 ┆ 1000      ┆ 10000     ┆ 42        │
# └───────────┴───────────┴───────────┴───────────┴───┴──────────┴───────────┴───────────┴───────────┘
# 
# ======================================================================
# STAGE 4: SAVING RESULTS TO PARQUET
# ======================================================================
# Results saved to: /daaf/data/processed/monte_carlo_results.parquet
# ✓ File persistence validation passed
# ✓ Read-back verification passed
# 
# ======================================================================
# EXECUTION SUMMARY
# ======================================================================
# 
# Input Parameters:
#   Distribution: N(50, 10)
#   Sample size: 1000
#   Bootstrap resamples: 10000
# 
# Key Results:
#   Sample mean: 49.7111
#   Sample std: 9.8922
#   95% CI: [49.0882, 50.3239]
#   CI width: 1.2357
# 
# Output File:
#   Path: /daaf/data/processed/monte_carlo_results.parquet
#   Size: 3,904 bytes
#   Rows: 1
#   Columns: 11
# 
# ======================================================================
# SUCCESS: Monte Carlo simulation completed
# ======================================================================
# 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
