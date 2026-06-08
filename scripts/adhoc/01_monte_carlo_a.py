"""
Monte Carlo Simulation: Bootstrap Confidence Interval for Sample Mean

INTENT: Draw random samples from a normal distribution, compute the sample mean,
and construct a bootstrap 95% CI for the true mean.

METHODOLOGY:
- Generate 1000 samples from N(mean=50, SD=10)
- Compute the observed sample mean
- Use bootstrap resampling (1000 resamples) to construct the empirical 95% CI
  via percentile method (2.5th and 97.5th percentiles of bootstrap distribution)

ASSUMPTIONS:
- Normal population distribution
- Independence of samples
- Bootstrap is appropriate for CI estimation (mean is well-behaved)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---

# INTENT: Set random seed for reproducibility
np.random.seed(42)

# INTENT: Define Monte Carlo parameters
MEAN = 50  # Population mean
SD = 10    # Population standard deviation
N_SAMPLES = 1000  # Number of samples to draw
N_BOOTSTRAP = 1000  # Number of bootstrap resamples
CI_LEVEL = 0.95  # Confidence level
ALPHA = 1 - CI_LEVEL  # Significance level

# INTENT: Define output path
OUTPUT_DIR = Path("/daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/output")
OUTPUT_FILE = OUTPUT_DIR / "simulation_results.parquet"

# --- Load ---

print("\n" + "="*70)
print("MONTE CARLO SIMULATION: Bootstrap CI for Sample Mean")
print("="*70)

# INTENT: Verify output directory exists
if not OUTPUT_DIR.exists():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created output directory: {OUTPUT_DIR}")
else:
    print(f"Output directory verified: {OUTPUT_DIR}")

# --- Simulate ---

print("\n--- Step 1: Draw Sample from Normal Distribution ---")

# INTENT: Generate 1000 samples from N(50, 10)
# REASONING: Using numpy.random.normal for efficiency
# ASSUMES: numpy's generator is properly seeded
# NOTE: numpy uses 'scale' parameter (not 'sd') for standard deviation
samples = np.random.normal(loc=MEAN, scale=SD, size=N_SAMPLES)

# INTENT: Validate sample generation
print(f"Generated {len(samples)} samples")
print(f"Sample shape: {samples.shape}")
print(f"Sample type: {samples.dtype}")
print(f"First 5 values: {samples[:5]}")
print(f"Last 5 values: {samples[-5:]}")

# --- Compute Sample Statistics ---

print("\n--- Step 2: Compute Sample Mean ---")

# INTENT: Calculate the observed sample mean
# REASONING: This is our point estimate of the population mean
sample_mean = np.mean(samples)
sample_sd = np.std(samples, ddof=1)  # Use unbiased estimator (N-1)
sample_se = sample_sd / np.sqrt(len(samples))

print(f"Sample mean: {sample_mean:.4f}")
print(f"Sample SD (unbiased): {sample_sd:.4f}")
print(f"Standard error of mean: {sample_se:.4f}")
print(f"Theoretical SE (SD/sqrt(N)): {SD / np.sqrt(N_SAMPLES):.4f}")

# --- Bootstrap Confidence Interval ---

print("\n--- Step 3: Bootstrap 95% Confidence Interval ---")

# INTENT: Resample from the observed sample to construct empirical CI
# REASONING: Bootstrap allows non-parametric CI without normality assumptions
# ASSUMES: Samples are iid; percentile method is appropriate

bootstrap_means = []
for b in range(N_BOOTSTRAP):
    # INTENT: Resample with replacement from the original sample
    # REASONING: Each bootstrap replicate is a random sample of size N from the original data
    bootstrap_sample = np.random.choice(samples, size=len(samples), replace=True)
    bootstrap_means.append(np.mean(bootstrap_sample))

bootstrap_means = np.array(bootstrap_means)

# INTENT: Compute percentile-based CI
# REASONING: 2.5th and 97.5th percentiles give symmetric 95% CI
ci_lower = np.percentile(bootstrap_means, q=ALPHA/2 * 100)
ci_upper = np.percentile(bootstrap_means, q=(1 - ALPHA/2) * 100)

print(f"Bootstrap resamples: {len(bootstrap_means)}")
print(f"Bootstrap mean of means: {np.mean(bootstrap_means):.4f}")
print(f"Bootstrap SD of means: {np.std(bootstrap_means):.4f}")
print(f"95% Confidence Interval (percentile method):")
print(f"  Lower: {ci_lower:.4f}")
print(f"  Upper: {ci_upper:.4f}")
print(f"  Width: {ci_upper - ci_lower:.4f}")
print(f"  Includes true mean ({MEAN})? {ci_lower <= MEAN <= ci_upper}")

# --- Validate ---

print("\n--- Step 4: Validation ---")

# INTENT: Check that CI is reasonable
# REASONING: CI should be narrower than sample ±1SD, and should contain true mean
# ASSUMES: Normal population; bootstrap percentile method is appropriate

# Check CI width
expected_ci_width_approx = 2 * 1.96 * sample_se  # Rough approximation
print(f"Expected CI width (approx): {expected_ci_width_approx:.4f}")
print(f"Observed CI width: {ci_upper - ci_lower:.4f}")
print(f"Ratio (observed/expected): {(ci_upper - ci_lower) / expected_ci_width_approx:.2f}")

# Check bootstrap distribution
print(f"Bootstrap dist symmetry:")
print(f"  Distance from mean to lower: {np.mean(bootstrap_means) - ci_lower:.4f}")
print(f"  Distance from mean to upper: {ci_upper - np.mean(bootstrap_means):.4f}")

# --- Save Results ---

print("\n--- Step 5: Save Results to Parquet ---")

# INTENT: Create results DataFrame with all summary statistics
# REASONING: Parquet is columnar, efficient for storage and retrieval
# ASSUMES: All results are scalar or can be serialized to parquet

results_dict = {
    "sample_mean": [sample_mean],
    "sample_sd": [sample_sd],
    "standard_error": [sample_se],
    "ci_lower": [ci_lower],
    "ci_upper": [ci_upper],
    "ci_width": [ci_upper - ci_lower],
    "sample_count": [N_SAMPLES],
    "bootstrap_resamples": [N_BOOTSTRAP],
    "ci_level": [CI_LEVEL],
    "population_mean": [MEAN],
    "population_sd": [SD],
}

# INTENT: Convert to polars DataFrame
# REASONING: Polars provides efficient I/O and schema control
results_df = pl.DataFrame(results_dict)

print(f"Results DataFrame shape: {results_df.shape}")
print(f"Results DataFrame columns: {results_df.columns}")
print(f"\nResults DataFrame:")
print(results_df)

# INTENT: Save to parquet
# REASONING: Parquet is language-agnostic, compressed, and preserves schema
results_df.write_parquet(str(OUTPUT_FILE))

print(f"\nResults saved to: {OUTPUT_FILE}")
print(f"File size: {OUTPUT_FILE.stat().st_size} bytes")

# --- Final Summary ---

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Monte Carlo Simulation Results:")
print(f"  Sample size: {N_SAMPLES}")
print(f"  Sample mean: {sample_mean:.4f}")
print(f"  95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  CI contains true mean ({MEAN}): {ci_lower <= MEAN <= ci_upper}")
print(f"\nOutput saved to: {OUTPUT_FILE}")
print("="*70 + "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 18:57:09
# Command: python3 /daaf/scripts/adhoc/01_monte_carlo_a.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# 
# ======================================================================
# MONTE CARLO SIMULATION: Bootstrap CI for Sample Mean
# ======================================================================
# Output directory verified: /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/output
# 
# --- Step 1: Draw Sample from Normal Distribution ---
# Generated 1000 samples
# Sample shape: (1000,)
# Sample type: float64
# First 5 values: [54.96714153 48.61735699 56.47688538 65.23029856 47.65846625]
# Last 5 values: [47.18899707 67.97686527 56.40842861 44.2882101  55.72582781]
# 
# --- Step 2: Compute Sample Mean ---
# Sample mean: 50.1933
# Sample SD (unbiased): 9.7922
# Standard error of mean: 0.3097
# Theoretical SE (SD/sqrt(N)): 0.3162
# 
# --- Step 3: Bootstrap 95% Confidence Interval ---
# Bootstrap resamples: 1000
# Bootstrap mean of means: 50.2042
# Bootstrap SD of means: 0.3101
# 95% Confidence Interval (percentile method):
#   Lower: 49.6071
#   Upper: 50.8502
#   Width: 1.2432
#   Includes true mean (50)? True
# 
# --- Step 4: Validation ---
# Expected CI width (approx): 1.2138
# Observed CI width: 1.2432
# Ratio (observed/expected): 1.02
# Bootstrap dist symmetry:
#   Distance from mean to lower: 0.5972
#   Distance from mean to upper: 0.6460
# 
# --- Step 5: Save Results to Parquet ---
# Results DataFrame shape: (1, 11)
# Results DataFrame columns: ['sample_mean', 'sample_sd', 'standard_error', 'ci_lower', 'ci_upper', 'ci_width', 'sample_count', 'bootstrap_resamples', 'ci_level', 'population_mean', 'population_sd']
# 
# Results DataFrame:
# shape: (1, 11)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬──────────┬───────────┬───────────┐
# │ sample_me ┆ sample_sd ┆ standard_ ┆ ci_lower  ┆ … ┆ bootstrap ┆ ci_level ┆ populatio ┆ populatio │
# │ an        ┆ ---       ┆ error     ┆ ---       ┆   ┆ _resample ┆ ---      ┆ n_mean    ┆ n_sd      │
# │ ---       ┆ f64       ┆ ---       ┆ f64       ┆   ┆ s         ┆ f64      ┆ ---       ┆ ---       │
# │ f64       ┆           ┆ f64       ┆           ┆   ┆ ---       ┆          ┆ i64       ┆ i64       │
# │           ┆           ┆           ┆           ┆   ┆ i64       ┆          ┆           ┆           │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪══════════╪═══════════╪═══════════╡
# │ 50.193321 ┆ 9.792159  ┆ 0.309655  ┆ 49.607054 ┆ … ┆ 1000      ┆ 0.95     ┆ 50        ┆ 10        │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴──────────┴───────────┴───────────┘
# 
# Results saved to: /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/output/simulation_results.parquet
# File size: 3947 bytes
# 
# ======================================================================
# SUMMARY
# ======================================================================
# Monte Carlo Simulation Results:
#   Sample size: 1000
#   Sample mean: 50.1933
#   95% CI: [49.6071, 50.8502]
#   CI contains true mean (50): True
# 
# Output saved to: /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/output/simulation_results.parquet
# ======================================================================
# 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
