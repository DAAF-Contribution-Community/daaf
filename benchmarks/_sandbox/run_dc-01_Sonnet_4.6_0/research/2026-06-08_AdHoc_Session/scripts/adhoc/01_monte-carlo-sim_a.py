#!/usr/bin/env python3
"""
Ad Hoc: Monte Carlo simulation — normal distribution sampling with bootstrap CI.

Task: monte-carlo-sim
Mode: Ad Hoc Collaboration
Depends on: None (standalone simulation, no input data files)
Input: None
Output: data/processed/2026-06-08_monte-carlo-results.parquet
Checkpoint: CP3 (post-transform validation of simulation outputs)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# INTENT: Define all simulation parameters and paths in one place for
# reproducibility and easy inspection.
# REASONING: Centralizing constants at the top means any re-run with
# different parameters only requires changes in this section.
# ASSUMES: The output directory already exists (created by project setup).
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-01_Sonnet_4.6_0/research/2026-06-08_AdHoc_Session")
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / "2026-06-08_monte-carlo-results.parquet"

# Simulation parameters
SEED = 42            # Fixed seed for full reproducibility
N_SAMPLES = 1000     # Number of draws from the normal distribution
MEAN = 50.0          # Population mean
STD = 10.0           # Population standard deviation

# Bootstrap parameters
N_BOOTSTRAP = 10_000   # Number of bootstrap resamples for CI estimation
CI_LEVEL = 0.95        # Confidence level for the interval
ALPHA = 1 - CI_LEVEL   # 0.05 -> tails share 2.5% each
CI_LOWER_PCT = (ALPHA / 2) * 100        # 2.5th percentile
CI_UPPER_PCT = (1 - ALPHA / 2) * 100   # 97.5th percentile

print("=" * 60)
print("Monte Carlo Simulation: Normal Distribution + Bootstrap CI")
print("=" * 60)
print(f"  Population:  N(mean={MEAN}, std={STD})")
print(f"  Draws:       {N_SAMPLES:,}")
print(f"  Bootstrap:   {N_BOOTSTRAP:,} resamples")
print(f"  CI level:    {CI_LEVEL:.0%}")
print(f"  Random seed: {SEED}")

# --- Simulate ---
# INTENT: Draw N_SAMPLES observations from the specified normal distribution.
# REASONING: Using numpy's default_rng (PCG64) seeded at SEED, which is the
# modern numpy random API (Generator, not the legacy RandomState). This
# produces a reproducible sample that matches the population N(50, 10).
# ASSUMES: numpy is available and supports Generator API (numpy >= 1.17).
rng = np.random.default_rng(seed=SEED)

# Draw 1000 samples from N(mean=50, std=10)
samples = rng.normal(loc=MEAN, scale=STD, size=N_SAMPLES)

sample_mean = float(np.mean(samples))
sample_std = float(np.std(samples, ddof=1))   # ddof=1: unbiased sample std

print(f"\n--- Simulation Results ---")
print(f"  Sample mean:  {sample_mean:.6f}  (population: {MEAN})")
print(f"  Sample std:   {sample_std:.6f}   (population: {STD})")
print(f"  Min:          {samples.min():.4f}")
print(f"  Max:          {samples.max():.4f}")

# --- Bootstrap ---
# INTENT: Estimate a 95% bootstrap confidence interval for the sample mean
# using 10,000 bootstrap resamples.
# REASONING: The percentile bootstrap is a nonparametric method that makes
# no distributional assumptions about the sampling distribution of the mean.
# With N=1000 the CLT guarantees the mean is approximately normal anyway,
# but bootstrap CIs are more general and directly estimable from the draws.
# ASSUMES: The 1000 original draws are the "observed" data. Each bootstrap
# resample draws N_SAMPLES=1000 observations WITH REPLACEMENT from those draws.
# The CI is constructed from the empirical distribution of bootstrap means.
print(f"\n--- Bootstrap CI Estimation ---")
print(f"  Generating {N_BOOTSTRAP:,} bootstrap resamples (each n={N_SAMPLES})...")

# Pre-allocate array for efficiency — avoids per-iteration list appends
bootstrap_means = np.empty(N_BOOTSTRAP, dtype=np.float64)

for i in range(N_BOOTSTRAP):
    # INTENT: Resample with replacement to approximate sampling variability.
    # REASONING: replacement=True is the defining feature of bootstrapping;
    # each resample mimics independently drawing from the same population.
    resample = rng.choice(samples, size=N_SAMPLES, replace=True)
    bootstrap_means[i] = np.mean(resample)

# Compute percentile-based CI bounds from the bootstrap distribution
ci_lower = float(np.percentile(bootstrap_means, CI_LOWER_PCT))
ci_upper = float(np.percentile(bootstrap_means, CI_UPPER_PCT))
bootstrap_mean_of_means = float(np.mean(bootstrap_means))

print(f"  Bootstrap mean of means: {bootstrap_mean_of_means:.6f}")
print(f"\n--- 95% Bootstrap Confidence Interval ---")
print(f"  Sample mean:  {sample_mean:.6f}")
print(f"  CI lower:     {ci_lower:.6f}")
print(f"  CI upper:     {ci_upper:.6f}")
print(f"  CI width:     {(ci_upper - ci_lower):.6f}")
print(f"  True mean ({MEAN}) inside CI: {ci_lower <= MEAN <= ci_upper}")

# --- Validate ---
# INTENT: Assert key invariants before saving to catch simulation logic errors.
# REASONING: Pre-save validation ensures the parquet file contains valid results,
# not degenerate output from a coding error (e.g., all-zeros, wrong shape).
# ASSUMES: With N=1000 draws from N(50,10), sample mean should be close to 50
# and the CI should be narrow (SEM ~0.316, so 95% CI width ~1.24).
print(f"\n--- Pre-Save Validation ---")

# Check 1: Sample is the right size
assert samples.shape == (N_SAMPLES,), f"STOP: samples shape mismatch — got {samples.shape}"
print(f"  [PASS] samples shape: {samples.shape}")

# Check 2: Sample mean is within 5 std errors of the true mean (very loose sanity check)
std_error = STD / np.sqrt(N_SAMPLES)
mean_deviation = abs(sample_mean - MEAN)
assert mean_deviation < 5 * std_error, (
    f"STOP: Sample mean {sample_mean:.4f} is {mean_deviation / std_error:.1f} SEs from true mean {MEAN}"
)
print(f"  [PASS] Sample mean deviation: {mean_deviation:.4f} ({mean_deviation / std_error:.2f} SEs from true mean)")

# Check 3: CI is ordered (lower < upper)
assert ci_lower < ci_upper, f"STOP: CI bounds inverted — lower={ci_lower:.4f}, upper={ci_upper:.4f}"
print(f"  [PASS] CI ordered: {ci_lower:.4f} < {ci_upper:.4f}")

# Check 4: Bootstrap means array has expected length
assert bootstrap_means.shape == (N_BOOTSTRAP,), f"STOP: bootstrap_means shape mismatch"
print(f"  [PASS] bootstrap_means shape: {bootstrap_means.shape}")

# Check 5: True mean is captured by CI (sanity; may rarely fail by chance)
ci_captures_true = ci_lower <= MEAN <= ci_upper
status = "PASS" if ci_captures_true else "NOTE"
print(f"  [{status}] True mean {MEAN} inside CI [{ci_lower:.4f}, {ci_upper:.4f}]: {ci_captures_true}")

# --- Save ---
# INTENT: Persist results in a structured parquet file with two logical sections:
# (1) scalar summary statistics, and (2) the raw 1,000 sample draws.
# REASONING: Polars requires equal-length columns in a DataFrame. The scalar
# results (mean, CI bounds) are repeated across all N_SAMPLES=1000 rows so they
# can coexist with the per-draw sample values in a single flat parquet file.
# This avoids splitting results across two files for a simple simulation task.
# ASSUMES: OUTPUT_PATH directory exists (verified by ls above at setup time).
print(f"\n--- Saving Results ---")

# Build the results DataFrame: 1000 rows (one per draw), with scalar summary
# columns broadcast across all rows.
# INTENT: Store raw draws alongside summary statistics for complete reproducibility.
# Any downstream reader can re-derive the CI or compute additional statistics
# directly from the 1000 raw samples.
results_df = pl.DataFrame({
    "draw_index": list(range(N_SAMPLES)),        # 0-based index of each draw
    "sample_value": samples.tolist(),             # The 1,000 raw draws
    "sample_mean": [sample_mean] * N_SAMPLES,    # Scalar: mean of all 1,000 draws
    "ci_lower": [ci_lower] * N_SAMPLES,          # Scalar: bootstrap 95% CI lower bound
    "ci_upper": [ci_upper] * N_SAMPLES,          # Scalar: bootstrap 95% CI upper bound
})

# Verify the DataFrame has expected shape before writing
pre_write_shape = results_df.shape
print(f"  DataFrame shape: {pre_write_shape[0]:,} rows x {pre_write_shape[1]} cols")
print(f"  Columns: {results_df.columns}")

assert pre_write_shape == (N_SAMPLES, 5), (
    f"STOP: Unexpected DataFrame shape {pre_write_shape}, expected ({N_SAMPLES}, 5)"
)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
results_df.write_parquet(OUTPUT_PATH)

# Verify the file was actually written and has expected size
assert OUTPUT_PATH.exists(), f"STOP: Parquet file not found after write: {OUTPUT_PATH}"
file_size_kb = OUTPUT_PATH.stat().st_size / 1024
print(f"  Saved: {OUTPUT_PATH}")
print(f"  File size: {file_size_kb:.1f} KB")

# Read it back to confirm round-trip integrity
readback = pl.read_parquet(OUTPUT_PATH)
assert readback.shape == (N_SAMPLES, 5), (
    f"STOP: Readback shape {readback.shape} != expected ({N_SAMPLES}, 5)"
)
print(f"  Readback shape: {readback.shape[0]:,} rows x {readback.shape[1]} cols — OK")

# Final summary
print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)
print(f"\n  Sample mean:      {sample_mean:.6f}")
print(f"  Bootstrap CI 95%: [{ci_lower:.6f}, {ci_upper:.6f}]")
print(f"  CI width:         {(ci_upper - ci_lower):.6f}")
print(f"  Output:           {OUTPUT_PATH}")



# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:19:46
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Sonnet_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_monte-carlo-sim_a.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Monte Carlo Simulation: Normal Distribution + Bootstrap CI
# ============================================================
#   Population:  N(mean=50.0, std=10.0)
#   Draws:       1,000
#   Bootstrap:   10,000 resamples
#   CI level:    95%
#   Random seed: 42
# 
# --- Simulation Results ---
#   Sample mean:  49.711084  (population: 50.0)
#   Sample std:   9.892171   (population: 10.0)
#   Min:          13.5159
#   Max:          81.7885
# 
# --- Bootstrap CI Estimation ---
#   Generating 10,000 bootstrap resamples (each n=1000)...
#   Bootstrap mean of means: 49.707847
# 
# --- 95% Bootstrap Confidence Interval ---
#   Sample mean:  49.711084
#   CI lower:     49.088176
#   CI upper:     50.323915
#   CI width:     1.235739
#   True mean (50.0) inside CI: True
# 
# --- Pre-Save Validation ---
#   [PASS] samples shape: (1000,)
#   [PASS] Sample mean deviation: 0.2889 (0.91 SEs from true mean)
#   [PASS] CI ordered: 49.0882 < 50.3239
#   [PASS] bootstrap_means shape: (10000,)
#   [PASS] True mean 50.0 inside CI [49.0882, 50.3239]: True
# 
# --- Saving Results ---
#   DataFrame shape: 1,000 rows x 5 cols
#   Columns: ['draw_index', 'sample_value', 'sample_mean', 'ci_lower', 'ci_upper']
#   Saved: /daaf/benchmarks/_sandbox/run_dc-01_Sonnet_4.6_0/research/2026-06-08_AdHoc_Session/data/processed/2026-06-08_monte-carlo-results.parquet
#   File size: 11.9 KB
#   Readback shape: 1,000 rows x 5 cols — OK
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
# 
#   Sample mean:      49.711084
#   Bootstrap CI 95%: [49.088176, 50.323915]
#   CI width:         1.235739
#   Output:           /daaf/benchmarks/_sandbox/run_dc-01_Sonnet_4.6_0/research/2026-06-08_AdHoc_Session/data/processed/2026-06-08_monte-carlo-results.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
