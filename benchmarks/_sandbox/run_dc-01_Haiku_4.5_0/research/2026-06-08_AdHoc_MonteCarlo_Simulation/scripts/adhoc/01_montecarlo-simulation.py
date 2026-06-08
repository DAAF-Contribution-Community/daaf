#!/usr/bin/env python3
"""
Monte Carlo Simulation: Normal Distribution Sampling with Bootstrap CI

INTENT: Demonstrate statistical simulation by drawing samples from a normal
        distribution, computing the sample mean, and constructing a bootstrap
        95% confidence interval around that estimate.

REASONING: Monte Carlo methods are foundational to computational statistics.
           This script illustrates the principle: we draw repeated samples
           from a known distribution, estimate a parameter (mean), and quantify
           our uncertainty via bootstrap resampling. Bootstrap CIs provide a
           model-free alternative to parametric confidence intervals.

ASSUMES: NumPy's random number generation provides adequate pseudo-random samples.
         The true population has mean=50 and std=10 (parameters are known).
         Bootstrap resampling (sampling with replacement) approximates the
         sampling distribution of the mean.
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
RNG_SEED = 42
POPULATION_MEAN = 50
POPULATION_STDDEV = 10
NUM_SAMPLES = 1000
BOOTSTRAP_RESAMPLES = 10000
CI_LEVEL = 0.95
CI_ALPHA = 1 - CI_LEVEL

# --- State capture: pre-simulation ---
print("="*70)
print("MONTE CARLO SIMULATION: Normal Distribution Sampling + Bootstrap CI")
print("="*70)
print()
print("Configuration:")
print(f"  Population mean: {POPULATION_MEAN}")
print(f"  Population std dev: {POPULATION_STDDEV}")
print(f"  Samples to draw: {NUM_SAMPLES}")
print(f"  Bootstrap resamples: {BOOTSTRAP_RESAMPLES}")
print(f"  CI confidence level: {CI_LEVEL} (alpha={CI_ALPHA})")
print(f"  Random seed: {RNG_SEED}")
print()

# --- Generate samples from normal distribution ---
np.random.seed(RNG_SEED)

# INTENT: Draw 1000 samples from N(50, 10^2)
# REASONING: Standard normal distribution sampling via NumPy. We use numpy.random.normal()
#            which implements the Ziggurat algorithm for efficient normal variate generation.
# ASSUMES: The RNG seed ensures reproducibility; NumPy's normal() is correct.
samples = np.random.normal(
    loc=POPULATION_MEAN,
    scale=POPULATION_STDDEV,
    size=NUM_SAMPLES
)

print(f"Pre-State: Generated {len(samples)} samples")
print(f"  Sample min: {samples.min():.4f}")
print(f"  Sample max: {samples.max():.4f}")
print(f"  Sample mean: {samples.mean():.4f}")
print(f"  Sample std: {samples.std(ddof=1):.4f}")
print()

# --- Compute the point estimate (sample mean) ---
sample_mean = np.mean(samples)
print(f"Point Estimate (Sample Mean): {sample_mean:.6f}")
print()

# --- Bootstrap resampling for confidence interval ---
print("Bootstrap Procedure:")
print(f"  Drawing {BOOTSTRAP_RESAMPLES} resamples with replacement...")

# INTENT: Perform bootstrap resampling to estimate the sampling distribution of the mean.
# REASONING: Bootstrap is a non-parametric method: we resample the original sample
#            WITH replacement, recompute the mean for each resample, and use the
#            empirical distribution of bootstrap means to construct a CI. This avoids
#            parametric assumptions while providing valid inference under standard conditions.
# ASSUMES: Bootstrap resamples are drawn uniformly with replacement; the empirical
#          distribution of bootstrap means approximates the true sampling distribution.
#          This holds (asymptotically) for smooth functionals like the mean.

bootstrap_means = []
for i in range(BOOTSTRAP_RESAMPLES):
    # Resample with replacement
    bootstrap_sample = np.random.choice(samples, size=len(samples), replace=True)
    bootstrap_means.append(np.mean(bootstrap_sample))

bootstrap_means = np.array(bootstrap_means)

print(f"  Completed {BOOTSTRAP_RESAMPLES} resamples")
print(f"  Bootstrap means - min: {bootstrap_means.min():.6f}")
print(f"  Bootstrap means - max: {bootstrap_means.max():.6f}")
print(f"  Bootstrap means - mean: {bootstrap_means.mean():.6f}")
print(f"  Bootstrap means - std: {bootstrap_means.std():.6f}")
print()

# --- Compute percentile-based 95% CI ---
# INTENT: Extract the CI bounds from the empirical distribution of bootstrap means.
# REASONING: The percentile method is straightforward: the (alpha/2)-th and (1-alpha/2)-th
#            percentiles of the bootstrap distribution form the confidence interval.
#            This is intuitive: 2.5% in each tail, leaving 95% in the middle.
# ASSUMES: The percentile method is valid (it has good coverage properties under standard
#          regularity conditions). NumPy's percentile() uses linear interpolation by default.

lower_percentile = (CI_ALPHA / 2) * 100  # 2.5 percentile
upper_percentile = (1 - CI_ALPHA / 2) * 100  # 97.5 percentile

ci_lower = np.percentile(bootstrap_means, lower_percentile)
ci_upper = np.percentile(bootstrap_means, upper_percentile)

print(f"Bootstrap 95% Confidence Interval (Percentile Method):")
print(f"  Lower bound ({lower_percentile:.1f}th percentile): {ci_lower:.6f}")
print(f"  Upper bound ({upper_percentile:.1f}th percentile): {ci_upper:.6f}")
print(f"  Interval: [{ci_lower:.6f}, {ci_upper:.6f}]")
print(f"  Interval width: {ci_upper - ci_lower:.6f}")
print()

# --- Validation checkpoint (CP3: post-transform validation) ---
print("="*70)
print("VALIDATION CHECKPOINT (CP3)")
print("="*70)

# Check 1: Sample size preserved
assert len(samples) == NUM_SAMPLES, "Sample size mismatch!"
print(f"  [PASS] Sample size preserved: {len(samples)} == {NUM_SAMPLES}")

# Check 2: Sample mean is within reasonable bounds
assert POPULATION_MEAN - 5 < sample_mean < POPULATION_MEAN + 5, \
    f"Sample mean {sample_mean} is unexpectedly far from population mean {POPULATION_MEAN}"
print(f"  [PASS] Sample mean {sample_mean:.4f} is close to population mean {POPULATION_MEAN}")

# Check 3: Bootstrap resamples count
assert len(bootstrap_means) == BOOTSTRAP_RESAMPLES, "Bootstrap resample count mismatch!"
print(f"  [PASS] Bootstrap resamples: {len(bootstrap_means)} == {BOOTSTRAP_RESAMPLES}")

# Check 4: CI bounds are ordered correctly
assert ci_lower < ci_upper, f"CI bounds out of order: {ci_lower} >= {ci_upper}"
print(f"  [PASS] CI bounds in correct order: {ci_lower:.6f} < {ci_upper:.6f}")

# Check 5: Population mean is within the CI (we expect it is, with high probability)
# This is not a hard requirement, but it's informative
contains_pop_mean = ci_lower <= POPULATION_MEAN <= ci_upper
print(f"  [INFO] True population mean within CI: {contains_pop_mean}")
if not contains_pop_mean:
    print(f"        (This is OK; happens ~5% of the time due to randomness)")

print()

# --- Prepare output data ---
print("Preparing output data...")

# Create a DataFrame with:
#   - original samples
#   - the computed sample mean (repeated for each row for easy export)
#   - the CI bounds (repeated for each row)
# This allows the results to be saved as a structured parquet file.

output_df = pl.DataFrame({
    "sample_index": list(range(NUM_SAMPLES)),
    "original_sample": samples,
    "sample_mean": np.full(NUM_SAMPLES, sample_mean),
    "ci_lower": np.full(NUM_SAMPLES, ci_lower),
    "ci_upper": np.full(NUM_SAMPLES, ci_upper),
})

print(f"Output DataFrame shape: {output_df.shape}")
print(f"Output DataFrame columns: {output_df.columns}")
print()

# --- Save to parquet ---
output_path = Path("/daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_0/research/2026-06-08_AdHoc_MonteCarlo_Simulation/data/processed/montecarlo_results.parquet")
output_path.parent.mkdir(parents=True, exist_ok=True)

# INTENT: Persist results to disk for downstream use.
# REASONING: Parquet is the DAAF standard: compressed, columnar, preserves schemas.
# ASSUMES: The path is writable; Polars can serialize the DataFrame successfully.

output_df.write_parquet(str(output_path))

print(f"Saved results to: {output_path}")
print(f"File size: {output_path.stat().st_size} bytes")
print()

# --- Post-save verification ---
print("Post-Save Verification:")
loaded_df = pl.read_parquet(str(output_path))
print(f"  Loaded shape: {loaded_df.shape}")
print(f"  Loaded columns: {loaded_df.columns}")
assert loaded_df.shape[0] == NUM_SAMPLES, "Row count mismatch in loaded data!"
print(f"  [PASS] Row count verified: {loaded_df.shape[0]}")

# Spot-check: verify that loaded mean and CI values match what we saved
loaded_mean = loaded_df.select(pl.col("sample_mean")).item(0, 0)
loaded_ci_lower = loaded_df.select(pl.col("ci_lower")).item(0, 0)
loaded_ci_upper = loaded_df.select(pl.col("ci_upper")).item(0, 0)

assert abs(loaded_mean - sample_mean) < 1e-10, "Sample mean not preserved!"
assert abs(loaded_ci_lower - ci_lower) < 1e-10, "CI lower bound not preserved!"
assert abs(loaded_ci_upper - ci_upper) < 1e-10, "CI upper bound not preserved!"
print(f"  [PASS] Loaded statistics match saved values")
print()

# --- Final Summary ---
print("="*70)
print("FINAL RESULTS SUMMARY")
print("="*70)
print()
print(f"Original Samples:")
print(f"  Count: {NUM_SAMPLES}")
print(f"  Mean: {sample_mean:.6f}")
print(f"  Std Dev: {samples.std(ddof=1):.6f}")
print()
print(f"Bootstrap Confidence Interval (95%, {BOOTSTRAP_RESAMPLES} resamples):")
print(f"  Lower: {ci_lower:.6f}")
print(f"  Upper: {ci_upper:.6f}")
print(f"  Width: {ci_upper - ci_lower:.6f}")
print()
print(f"Interpretation:")
print(f"  Based on {NUM_SAMPLES} samples from N({POPULATION_MEAN}, {POPULATION_STDDEV}^2),")
print(f"  the estimated population mean is {sample_mean:.4f}.")
print(f"  The bootstrap 95% confidence interval is [{ci_lower:.4f}, {ci_upper:.4f}].")
print(f"  This interval contains the plausible range for the true population mean,")
print(f"  accounting for sampling variability. With ~95% confidence, the true mean")
print(f"  lies within this range (assuming the bootstrap assumptions hold).")
print()
print(f"Output file: {output_path}")
print("="*70)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:24:24
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_0/research/2026-06-08_AdHoc_MonteCarlo_Simulation/scripts/adhoc/01_montecarlo-simulation.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ======================================================================
# MONTE CARLO SIMULATION: Normal Distribution Sampling + Bootstrap CI
# ======================================================================
# 
# Configuration:
#   Population mean: 50
#   Population std dev: 10
#   Samples to draw: 1000
#   Bootstrap resamples: 10000
#   CI confidence level: 0.95 (alpha=0.050000000000000044)
#   Random seed: 42
# 
# Pre-State: Generated 1000 samples
#   Sample min: 17.5873
#   Sample max: 88.5273
#   Sample mean: 50.1933
#   Sample std: 9.7922
# 
# Point Estimate (Sample Mean): 50.193321
# 
# Bootstrap Procedure:
#   Drawing 10000 resamples with replacement...
#   Completed 10000 resamples
#   Bootstrap means - min: 49.006361
#   Bootstrap means - max: 51.296374
#   Bootstrap means - mean: 50.196769
#   Bootstrap means - std: 0.310803
# 
# Bootstrap 95% Confidence Interval (Percentile Method):
#   Lower bound (2.5th percentile): 49.594178
#   Upper bound (97.5th percentile): 50.812164
#   Interval: [49.594178, 50.812164]
#   Interval width: 1.217985
# 
# ======================================================================
# VALIDATION CHECKPOINT (CP3)
# ======================================================================
#   [PASS] Sample size preserved: 1000 == 1000
#   [PASS] Sample mean 50.1933 is close to population mean 50
#   [PASS] Bootstrap resamples: 10000 == 10000
#   [PASS] CI bounds in correct order: 49.594178 < 50.812164
#   [INFO] True population mean within CI: True
# 
# Preparing output data...
# Output DataFrame shape: (1000, 5)
# Output DataFrame columns: ['sample_index', 'original_sample', 'sample_mean', 'ci_lower', 'ci_upper']
# 
# Saved results to: /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_0/research/2026-06-08_AdHoc_MonteCarlo_Simulation/data/processed/montecarlo_results.parquet
# File size: 12228 bytes
# 
# Post-Save Verification:
#   Loaded shape: (1000, 5)
#   Loaded columns: ['sample_index', 'original_sample', 'sample_mean', 'ci_lower', 'ci_upper']
#   [PASS] Row count verified: 1000
#   [PASS] Loaded statistics match saved values
# 
# ======================================================================
# FINAL RESULTS SUMMARY
# ======================================================================
# 
# Original Samples:
#   Count: 1000
#   Mean: 50.193321
#   Std Dev: 9.792159
# 
# Bootstrap Confidence Interval (95%, 10000 resamples):
#   Lower: 49.594178
#   Upper: 50.812164
#   Width: 1.217985
# 
# Interpretation:
#   Based on 1000 samples from N(50, 10^2),
#   the estimated population mean is 50.1933.
#   The bootstrap 95% confidence interval is [49.5942, 50.8122].
#   This interval contains the plausible range for the true population mean,
#   accounting for sampling variability. With ~95% confidence, the true mean
#   lies within this range (assuming the bootstrap assumptions hold).
# 
# Output file: /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_0/research/2026-06-08_AdHoc_MonteCarlo_Simulation/data/processed/montecarlo_results.parquet
# ======================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
