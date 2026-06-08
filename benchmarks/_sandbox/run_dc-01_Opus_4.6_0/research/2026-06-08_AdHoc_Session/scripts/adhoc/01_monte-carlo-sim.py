#!/usr/bin/env python3
"""
Ad Hoc: Monte Carlo simulation with bootstrap confidence interval.

Task: monte-carlo-sim
Mode: Ad Hoc Collaboration
Depends on: None
Input: None (generates synthetic data)
Output: data/processed/2026-06-08_monte-carlo-results.parquet
Checkpoint: Inline validation (CI contains true mean, ordering)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for the Monte Carlo + bootstrap CI exercise.
# All parameters are fixed for reproducibility.
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session")
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / "2026-06-08_monte-carlo-results.parquet"

SEED = 42
N_SAMPLES = 1000
TRUE_MEAN = 50
TRUE_SD = 10
N_BOOTSTRAP = 10_000
CI_LEVEL = 0.95

# --- Pre-state ---
# No input data to load; we are generating synthetic data from scratch.
# Document the generation parameters for reproducibility.
print("=" * 60)
print("Ad Hoc: Monte Carlo Simulation + Bootstrap CI")
print("=" * 60)
print(f"Parameters:")
print(f"  True mean:          {TRUE_MEAN}")
print(f"  True SD:            {TRUE_SD}")
print(f"  Sample size (N):    {N_SAMPLES}")
print(f"  Bootstrap resamples: {N_BOOTSTRAP:,}")
print(f"  CI level:           {CI_LEVEL}")
print(f"  Random seed:        {SEED}")

# --- Generate ---
# INTENT: Draw a single sample of N_SAMPLES observations from N(TRUE_MEAN, TRUE_SD).
# This represents one realization of the data-generating process.
# REASONING: Using numpy's default_rng with a fixed seed for full reproducibility.
# The Generator API (default_rng) is preferred over the legacy np.random functions
# because it provides better statistical properties and explicit state management.
# ASSUMES: Normal distribution is the intended DGP per the task specification.
rng = np.random.default_rng(SEED)
samples = rng.normal(loc=TRUE_MEAN, scale=TRUE_SD, size=N_SAMPLES)

sample_mean = float(np.mean(samples))
print(f"\nSample mean: {sample_mean:.4f}")
print(f"Sample SD:   {float(np.std(samples, ddof=1)):.4f}")
print(f"Sample size: {len(samples)}")

# --- Bootstrap ---
# INTENT: Compute a 95% bootstrap confidence interval for the sample mean using
# the percentile method with 10,000 bootstrap resamples.
#
# REASONING: The percentile bootstrap is a nonparametric method that makes no
# distributional assumptions about the sampling distribution of the mean. With
# 10,000 resamples, the percentile estimates are stable (Monte Carlo error
# for the 2.5th/97.5th percentiles is negligible at this resample count).
#
# ASSUMES:
#   - The original sample of 1,000 is large enough for bootstrap validity
#     (bootstrap consistency requires the sample to be representative)
#   - The percentile method is appropriate here (for a sample mean from a
#     symmetric distribution, bias-corrected methods offer little advantage)
#   - 10,000 resamples provide sufficient precision for CI endpoints
alpha = 1 - CI_LEVEL
bootstrap_means = np.empty(N_BOOTSTRAP)

for i in range(N_BOOTSTRAP):
    # INTENT: Draw a resample of size N_SAMPLES with replacement from the original sample.
    # Each resample mimics drawing a new dataset from the empirical distribution.
    resample = rng.choice(samples, size=N_SAMPLES, replace=True)
    bootstrap_means[i] = np.mean(resample)

# INTENT: Extract the alpha/2 and 1-alpha/2 percentiles from the bootstrap
# distribution to form the confidence interval.
# REASONING: For a 95% CI, we take the 2.5th and 97.5th percentiles.
ci_lower = float(np.percentile(bootstrap_means, 100 * alpha / 2))
ci_upper = float(np.percentile(bootstrap_means, 100 * (1 - alpha / 2)))

print(f"\nBootstrap 95% CI for the mean:")
print(f"  Lower bound: {ci_lower:.4f}")
print(f"  Upper bound: {ci_upper:.4f}")
print(f"  CI width:    {ci_upper - ci_lower:.4f}")

# --- Validate ---
# Checkpoint validation: verify that results are internally consistent and
# that the CI contains the true mean (expected with high probability for a
# well-behaved symmetric distribution with N=1000).
print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

# Check 1: CI ordering (lower < mean < upper)
ordering_ok = ci_lower < sample_mean < ci_upper
print(f"  [{'PASS' if ordering_ok else 'FAIL'}] CI ordering: {ci_lower:.4f} < {sample_mean:.4f} < {ci_upper:.4f}")
assert ordering_ok, "STOP: CI bounds are not correctly ordered around the sample mean"

# Check 2: CI contains true mean (expected with ~95% probability; with seed=42
# and N=1000, this should hold comfortably)
contains_true = ci_lower <= TRUE_MEAN <= ci_upper
print(f"  [{'PASS' if contains_true else 'WARN'}] CI contains true mean ({TRUE_MEAN}): {contains_true}")
assert contains_true, f"STOP: CI [{ci_lower:.4f}, {ci_upper:.4f}] does not contain true mean {TRUE_MEAN}"

# Check 3: Sample mean is within reasonable range of true mean
# REASONING: With N=1000 and SD=10, the SE of the mean is ~0.316.
# A sample mean more than 4 SEs away would be extremely unlikely.
se_theoretical = TRUE_SD / np.sqrt(N_SAMPLES)  # ~0.316
deviation_ses = abs(sample_mean - TRUE_MEAN) / se_theoretical
mean_reasonable = deviation_ses < 4
print(f"  [{'PASS' if mean_reasonable else 'WARN'}] Sample mean within 4 SEs of true mean: {deviation_ses:.2f} SEs away")

# Check 4: CI width is reasonable
# REASONING: For a normal distribution, the 95% CI for the mean should be
# approximately +/- 1.96 * SE = +/- 0.62. The bootstrap CI should be close.
expected_width = 2 * 1.96 * se_theoretical  # ~1.24
width_ratio = (ci_upper - ci_lower) / expected_width
width_reasonable = 0.7 < width_ratio < 1.3
print(f"  [{'PASS' if width_reasonable else 'WARN'}] CI width reasonable: {ci_upper - ci_lower:.4f} vs expected ~{expected_width:.4f} (ratio: {width_ratio:.2f})")

# Check 5: Correct number of samples generated
samples_ok = len(samples) == N_SAMPLES
print(f"  [{'PASS' if samples_ok else 'FAIL'}] Sample count: {len(samples)} (expected {N_SAMPLES})")

# Check 6: Bootstrap resample count
bootstrap_ok = len(bootstrap_means) == N_BOOTSTRAP
print(f"  [{'PASS' if bootstrap_ok else 'FAIL'}] Bootstrap resample count: {len(bootstrap_means):,} (expected {N_BOOTSTRAP:,})")

# --- Save ---
# INTENT: Save the results as a parquet file containing the summary statistics
# (sample mean, CI bounds) alongside the 1,000 drawn samples.
#
# REASONING: Storing all 1,000 samples enables downstream re-analysis (e.g.,
# different CI methods, different confidence levels) without regeneration.
# The summary statistics are stored as constant columns replicated across all
# rows for simplicity -- this is a flat structure that any consumer can filter
# to row 0 for summary stats or use the full samples column.
#
# ASSUMES: Parquet format preserves full float64 precision for all values.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

results_df = pl.DataFrame({
    "sample_id": list(range(1, N_SAMPLES + 1)),
    "sample_value": samples.tolist(),
    "sample_mean": [sample_mean] * N_SAMPLES,
    "ci_lower_95": [ci_lower] * N_SAMPLES,
    "ci_upper_95": [ci_upper] * N_SAMPLES,
})

results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Shape: {results_df.shape[0]:,} rows x {results_df.shape[1]} cols")
print(f"Columns: {results_df.columns}")

# --- Post-state ---
# Verify saved file exists and is readable.
saved_df = pl.read_parquet(OUTPUT_PATH)
print(f"\nVerification read: {saved_df.shape[0]:,} rows x {saved_df.shape[1]} cols")
file_size = OUTPUT_PATH.stat().st_size
print(f"File size: {file_size:,} bytes")

print("\n" + "=" * 60)
print("VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 11:47:51
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_monte-carlo-sim.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Ad Hoc: Monte Carlo Simulation + Bootstrap CI
# ============================================================
# Parameters:
#   True mean:          50
#   True SD:            10
#   Sample size (N):    1000
#   Bootstrap resamples: 10,000
#   CI level:           0.95
#   Random seed:        42
# 
# Sample mean: 49.7111
# Sample SD:   9.8922
# Sample size: 1000
# 
# Bootstrap 95% CI for the mean:
#   Lower bound: 49.0882
#   Upper bound: 50.3239
#   CI width:    1.2357
# 
# ============================================================
# VALIDATION
# ============================================================
#   [PASS] CI ordering: 49.0882 < 49.7111 < 50.3239
#   [PASS] CI contains true mean (50): True
#   [PASS] Sample mean within 4 SEs of true mean: 0.91 SEs away
#   [PASS] CI width reasonable: 1.2357 vs expected ~1.2396 (ratio: 1.00)
#   [PASS] Sample count: 1000 (expected 1000)
#   [PASS] Bootstrap resample count: 10,000 (expected 10,000)
# 
# Saved: /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/processed/2026-06-08_monte-carlo-results.parquet
# Shape: 1,000 rows x 5 cols
# Columns: ['sample_id', 'sample_value', 'sample_mean', 'ci_lower_95', 'ci_upper_95']
# 
# Verification read: 1,000 rows x 5 cols
# File size: 12,284 bytes
# 
# ============================================================
# VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
