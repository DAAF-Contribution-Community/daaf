#!/usr/bin/env python3
"""
Monte Carlo Simulation: Bootstrap Confidence Interval for the Mean

Draws 1000 samples from N(50, 10), computes the sample mean, and constructs a
bootstrap 95% confidence interval using 10,000 bootstrap replicates.

Output:
  - data/processed/monte_carlo_results.parquet: 1000 individual samples
  - summary statistics printed to stdout (captured in execution log)

DAAF Conventions:
  - Sequential inline style (no function definitions)
  - IAT documentation on all transforms
  - File-first execution via run_with_capture.sh
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# Simulation parameters. The normal distribution N(50, 10) is an arbitrary
# choice to demonstrate Monte Carlo methodology with a known ground truth.
# Bootstrap uses 10,000 replicates, which provides stable percentile-based
# confidence intervals (Monte Carlo error of the CI bounds is ~0.5-1% of the SE).
N_SAMPLES = 1000
TRUE_MEAN = 50.0
TRUE_STD = 10.0
N_BOOTSTRAP = 10_000
CONFIDENCE_LEVEL = 0.95
RANDOM_SEED = 42

# Project paths — all absolute per DAAF convention
PROJECT_DIR = Path("/daaf/research/2026-06-09_AdHoc_Session")
DATA_PROCESSED = PROJECT_DIR / "data" / "processed"
OUTPUT_PARQUET = DATA_PROCESSED / "monte_carlo_results.parquet"
OUTPUT_SUMMARY = DATA_PROCESSED / "monte_carlo_summary.parquet"

# --- Validate Config ---
# Ensure output directory exists before any computation, so we fail fast
# if there's a filesystem issue rather than after generating data.
print("=" * 60)
print("Monte Carlo Simulation: Bootstrap CI for Normal Mean")
print("=" * 60)
print(f"\nParameters:")
print(f"  N(samples)         = {N_SAMPLES:,}")
print(f"  True distribution  = N({TRUE_MEAN}, {TRUE_STD})")
print(f"  Bootstrap reps     = {N_BOOTSTRAP:,}")
print(f"  Confidence level   = {CONFIDENCE_LEVEL}")
print(f"  Random seed        = {RANDOM_SEED}")

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
print(f"\nOutput directory verified: {DATA_PROCESSED}")

# --- Simulation: Draw Samples ---
# INTENT: Generate N_SAMPLES independent draws from a normal distribution
# with known mean and standard deviation. Each draw represents one observation.
#
# REASONING: numpy's default RandomState with a fixed seed ensures exact
# reproducibility. The seed locks the entire random sequence so that every
# run of this script produces identical results — critical for auditability.
#
# ASSUMES: numpy's MT19937 PRNG is adequate for this level of simulation
# (we are not doing cryptography or high-dimensional integration that would
# require a higher-quality generator like PCG64).
rng = np.random.RandomState(RANDOM_SEED)  # Reproducible generator instance
samples = rng.normal(loc=TRUE_MEAN, scale=TRUE_STD, size=N_SAMPLES)

print(f"\nGenerated {len(samples):,} samples from N({TRUE_MEAN}, {TRUE_STD})")

# --- Pre-state (for transformation tracking) ---
# Not strictly applicable here since we are generating data, but we record
# the state of the generated array for audit purposes.
pre_shape = samples.shape
print(f"  Raw array shape: {pre_shape}")
print(f"  First 5 values:  {samples[:5].round(4).tolist()}")
print(f"  Last 5 values:   {samples[-5:].round(4).tolist()}")

# --- Compute Sample Mean ---
# INTENT: Compute the sample mean — the point estimate of the population mean.
# This is the MLE and unbiased estimator for the mean of a normal distribution.
#
# REASONING: The arithmetic mean is the standard estimator for the normal
# location parameter. It is UMVUE (uniformly minimum variance unbiased
# estimator) for this distribution family.
sample_mean = float(np.mean(samples))

# --- Compute Standard Error (classical, for comparison) ---
# INTENT: Compute the classical (parametric) standard error of the mean
# as a benchmark against which to compare the bootstrap estimate.
# The classical SE is sigma_hat / sqrt(n), where sigma_hat is the sample
# standard deviation. This serves as a sanity check: the bootstrap SE
# should be close to this value.
sample_std = float(np.std(samples, ddof=1))  # ddof=1 for unbiased estimator
classical_se = sample_std / np.sqrt(N_SAMPLES)

# --- Bootstrap Confidence Interval ---
# INTENT: Construct a 95% percentile bootstrap confidence interval for the
# mean. We resample with replacement from the observed data N_BOOTSTRAP times,
# compute the mean of each resample, and take the empirical percentiles of
# the bootstrap distribution.
#
# REASONING: Bootstrap percentile intervals are nonparametric and do not
# assume normality of the estimator's sampling distribution. With 10,000
# replicates, the Monte Carlo error on the percentile bounds is approximately
# SE_bootstrap / sqrt(N_BOOTSTRAP), which is negligible for well-behaved
# distributions. The percentile method (rather than BCa or studentized) is
# chosen because the sample mean is a pivotal quantity under normality and
# the percentile interval is first-order accurate for this setting.
#
# ASSUMES:
#   - The original sample is i.i.d. (true by construction from rng.normal)
#   - 10,000 replicates is sufficient for stable percentile estimates
#   - The bootstrap distribution is roughly symmetric (expected for means)
#
# Alternative considered: BCa (bias-corrected and accelerated) would provide
# second-order accuracy but adds complexity; for the normal mean, percentile
# and BCa intervals are asymptotically equivalent.

# Generate all bootstrap means in one vectorized operation:
#   (1) Draw an N_SAMPLES x N_BOOTSTRAP matrix of resample indices
#   (2) Index into samples with those indices
#   (3) Compute column means
# This vectorized approach runs ~50x faster than a Python for loop.
print(f"\nRunning {N_BOOTSTRAP:,} bootstrap replicates...")

# Step 1: Generate resample indices as a 2D array
# Each column represents one bootstrap replicate; each element is a random
# index (0 to N_SAMPLES-1) drawn with replacement
bootstrap_indices = rng.randint(0, N_SAMPLES, size=(N_BOOTSTRAP, N_SAMPLES))

# Step 2: Index into the original samples using the 2D index array
# This creates an (N_BOOTSTRAP, N_SAMPLES) array of resampled values
bootstrap_samples = samples[bootstrap_indices]

# Step 3: Compute the mean of each bootstrap replicate (across columns)
bootstrap_means = np.mean(bootstrap_samples, axis=1)

# Compute the percentile confidence interval
# alpha/2 and 1-alpha/2 cutoffs for the desired confidence level
alpha = 1.0 - CONFIDENCE_LEVEL  # = 0.05 for 95% CI
ci_lower = float(np.percentile(bootstrap_means, 100 * alpha / 2))  # 2.5th percentile
ci_upper = float(np.percentile(bootstrap_means, 100 * (1 - alpha / 2)))  # 97.5th percentile

# Bootstrap standard error (for comparison with classical SE)
bootstrap_se = float(np.std(bootstrap_means, ddof=1))

print(f"  Bootstrap complete.")

# --- Validate ---
# Checkpoint validation against expected properties.
# Since we know the ground truth (mu=50, sigma=10), we can verify that:
#   1. The sample mean is within a reasonable range of the true mean
#   2. The confidence interval contains the true mean
#   3. The bootstrap SE is close to the classical SE

# Check 1: Sample mean should be within ~3 classical SE of true mean
mean_deviation = abs(sample_mean - TRUE_MEAN)
mean_within_tolerance = mean_deviation < 3 * classical_se

print(f"\n--- Validation ---")
print(f"  Sample mean:        {sample_mean:.4f}")
print(f"  True mean:          {TRUE_MEAN}")
print(f"  Deviation:          {mean_deviation:.4f}")
print(f"  Classical SE:       {classical_se:.4f}")
print(f"  Bootstrap SE:       {bootstrap_se:.4f}")
print(f"  Check 1 (mean ~3SE): {'PASSED' if mean_within_tolerance else 'FAILED'}")

# Check 2: CI should contain the true mean
ci_contains_true = ci_lower <= TRUE_MEAN <= ci_upper
print(f"  95% CI:             [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  Check 2 (CI covers mu=50): {'PASSED' if ci_contains_true else 'FAILED'}")

# Check 3: Bootstrap SE and classical SE should be close (within ~10% relative difference)
se_ratio = bootstrap_se / classical_se if classical_se > 0 else float('inf')
se_close = 0.9 <= se_ratio <= 1.1
print(f"  SE ratio (boot/class): {se_ratio:.4f}")
print(f"  Check 3 (SE agreement): {'PASSED' if se_close else 'WARNING'}")

# Overall validation
all_checks_pass = mean_within_tolerance and ci_contains_true and se_close
print(f"\n  Overall validation: {'PASSED' if all_checks_pass else 'WARNING'}")

# --- Build Output DataFrames ---
# INTENT: Package the individual samples and summary statistics into Polars
# DataFrames for parquet output. The samples DataFrame contains one row per
# draw; the summary DataFrame contains the point estimate and CI bounds.

# Individual samples: 1000 rows with sequential sample IDs
samples_df = pl.DataFrame({
    "sample_id": list(range(1, N_SAMPLES + 1)),
    "value": samples.tolist(),
})

# Summary statistics: single row with the key estimates
summary_df = pl.DataFrame({
    "metric": ["sample_mean", "ci_lower", "ci_upper", "sample_std", "classical_se", "bootstrap_se", "n_samples", "n_bootstrap"],
    "value": [sample_mean, ci_lower, ci_upper, sample_std, classical_se, bootstrap_se, N_SAMPLES, N_BOOTSTRAP],
})

# --- Post-state: Verify DataFrames before saving ---
print(f"\n--- DataFrames Ready to Save ---")
print(f"  Samples: {samples_df.shape[0]:,} rows x {samples_df.shape[1]} cols")
print(f"  Summary: {summary_df.shape[0]:,} rows x {summary_df.shape[1]} cols")
print(f"  Sample IDs range: {samples_df['sample_id'].min()} to {samples_df['sample_id'].max()}")
print(f"  Values range:     [{samples_df['value'].min():.4f}, {samples_df['value'].max():.4f}]")
print(f"  No nulls in samples:  {samples_df.null_count().sum_horizontal().item() == 0}")
print(f"  No nulls in summary:  {summary_df.null_count().sum_horizontal().item() == 0}")

# --- Save ---
# Persist both the individual samples and the summary statistics as parquet.
# Parquet format is required by DAAF convention — it preserves types, compresses
# efficiently, and is readable by any parquet-compatible tool.
samples_df.write_parquet(OUTPUT_PARQUET)
summary_df.write_parquet(OUTPUT_SUMMARY)

print(f"\n--- Files Saved ---")
print(f"  Samples: {OUTPUT_PARQUET} ({OUTPUT_PARQUET.stat().st_size:,} bytes)")
print(f"  Summary: {OUTPUT_SUMMARY} ({OUTPUT_SUMMARY.stat().st_size:,} bytes)")

# --- Final Summary ---
print(f"\n{'=' * 60}")
print(f"RESULTS SUMMARY")
print(f"{'=' * 60}")
print(f"  Sample mean (point estimate): {sample_mean:.4f}")
print(f"  Bootstrap 95% CI:             [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  True mean (mu=50):            {'INSIDE CI' if ci_contains_true else 'OUTSIDE CI'}")
print(f"  Classical SE:                 {classical_se:.4f}")
print(f"  Bootstrap SE:                 {bootstrap_se:.4f}")
print(f"{'=' * 60}")

# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-09 01:01:34
# Command: python3 /daaf/research/2026-06-09_AdHoc_Session/scripts/adhoc/monte_carlo_simulation.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Monte Carlo Simulation: Bootstrap CI for Normal Mean
# ============================================================
# 
# Parameters:
#   N(samples)         = 1,000
#   True distribution  = N(50.0, 10.0)
#   Bootstrap reps     = 10,000
#   Confidence level   = 0.95
#   Random seed        = 42
# 
# Output directory verified: /daaf/research/2026-06-09_AdHoc_Session/data/processed
# 
# Generated 1,000 samples from N(50.0, 10.0)
#   Raw array shape: (1000,)
#   First 5 values:  [54.9671, 48.6174, 56.4769, 65.2303, 47.6585]
#   Last 5 values:   [47.189, 67.9769, 56.4084, 44.2882, 55.7258]
# 
# Running 10,000 bootstrap replicates...
#   Bootstrap complete.
# 
# --- Validation ---
#   Sample mean:        50.1933
#   True mean:          50.0
#   Deviation:          0.1933
#   Classical SE:       0.3097
#   Bootstrap SE:       0.3108
#   Check 1 (mean ~3SE): PASSED
#   95% CI:             [49.5942, 50.8122]
#   Check 2 (CI covers mu=50): PASSED
#   SE ratio (boot/class): 1.0038
#   Check 3 (SE agreement): PASSED
# 
#   Overall validation: PASSED
# 
# --- DataFrames Ready to Save ---
#   Samples: 1,000 rows x 2 cols
#   Summary: 8 rows x 2 cols
#   Sample IDs range: 1 to 1000
#   Values range:     [17.5873, 88.5273]
#   No nulls in samples:  True
#   No nulls in summary:  True
# 
# --- Files Saved ---
#   Samples: /daaf/research/2026-06-09_AdHoc_Session/data/processed/monte_carlo_results.parquet (11,219 bytes)
#   Summary: /daaf/research/2026-06-09_AdHoc_Session/data/processed/monte_carlo_summary.parquet (977 bytes)
# 
# ============================================================
# RESULTS SUMMARY
# ============================================================
#   Sample mean (point estimate): 50.1933
#   Bootstrap 95% CI:             [49.5942, 50.8122]
#   True mean (mu=50):            INSIDE CI
#   Classical SE:                 0.3097
#   Bootstrap SE:                 0.3108
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
