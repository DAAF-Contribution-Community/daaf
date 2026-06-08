#!/usr/bin/env python3
"""
Ad Hoc: Monte Carlo simulation with bootstrap confidence interval.

Task: monte-carlo-sim
Mode: Ad Hoc Collaboration
Depends on: None
Input: None (synthetic data generation)
Output: output/analysis/2026-06-08_monte-carlo-results.parquet
Checkpoint: Inline validation (shape, CI bounds, file persistence)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for Monte Carlo sampling and bootstrap CI estimation.
# All parameters specified by the user's request.
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_1/research/2026-06-08_AdHoc_Session")
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / "2026-06-08_monte-carlo-results.parquet"

# INTENT: Set reproducible random seed so results are deterministic across runs.
# REASONING: Seed 42 is specified in the task instructions for reproducibility.
SEED = 42
SAMPLE_SIZE = 1000
POPULATION_MEAN = 50
POPULATION_SD = 10
N_BOOTSTRAP = 10_000
CI_LEVEL = 0.95

print("=" * 60)
print("Ad Hoc: Monte Carlo Simulation + Bootstrap CI")
print("=" * 60)

# --- Generate Samples ---
# INTENT: Draw 1000 samples from N(50, 10) to serve as our observed data.
# REASONING: Normal distribution with known parameters allows us to verify
# that the bootstrap CI captures the true population mean (50).
# ASSUMES: numpy's default_rng provides high-quality pseudorandom numbers
# suitable for Monte Carlo simulation.
rng = np.random.default_rng(SEED)
samples = rng.normal(loc=POPULATION_MEAN, scale=POPULATION_SD, size=SAMPLE_SIZE)

print(f"\nGenerated {SAMPLE_SIZE:,} samples from N({POPULATION_MEAN}, {POPULATION_SD})")
print(f"Sample shape: ({len(samples)},)")

# --- Pre-state ---
# Capture sample properties before bootstrap computation.
sample_mean = float(np.mean(samples))
sample_sd = float(np.std(samples, ddof=1))
sample_min = float(np.min(samples))
sample_max = float(np.max(samples))

print(f"\nPre-state (raw samples):")
print(f"  Sample mean: {sample_mean:.4f}")
print(f"  Sample SD:   {sample_sd:.4f}")
print(f"  Min:         {sample_min:.4f}")
print(f"  Max:         {sample_max:.4f}")

# --- Bootstrap CI ---
# INTENT: Compute a 95% confidence interval for the sample mean using the
# percentile bootstrap method with 10,000 resamples.
#
# REASONING: The percentile bootstrap is a nonparametric method that does not
# require distributional assumptions about the sampling distribution of the mean.
# With 10,000 resamples, the bootstrap distribution is well-resolved, yielding
# stable CI bounds. For a sample of size 1000 from a normal distribution, the
# bootstrap CI should closely approximate the analytical CI based on the t-distribution.
#
# ASSUMES:
#   - The 1000 samples are i.i.d. draws (guaranteed by our generation process)
#   - 10,000 bootstrap resamples are sufficient for stable percentile estimates
#   - The percentile method (not BCa or studentized) is adequate for this symmetric distribution
alpha = 1 - CI_LEVEL
bootstrap_means = np.empty(N_BOOTSTRAP)

for i in range(N_BOOTSTRAP):
    # INTENT: Resample with replacement from the original 1000 observations,
    # then compute the mean of each resample.
    resample = rng.choice(samples, size=SAMPLE_SIZE, replace=True)
    bootstrap_means[i] = np.mean(resample)

# INTENT: Extract the 2.5th and 97.5th percentiles of the bootstrap distribution
# to form the 95% confidence interval.
# REASONING: The percentile method directly uses quantiles of the bootstrap
# distribution as CI bounds. For symmetric distributions like the normal,
# this is equivalent to more sophisticated methods (BCa, studentized).
ci_lower = float(np.percentile(bootstrap_means, 100 * alpha / 2))
ci_upper = float(np.percentile(bootstrap_means, 100 * (1 - alpha / 2)))

print(f"\nBootstrap Results ({N_BOOTSTRAP:,} resamples):")
print(f"  Sample Mean:        {sample_mean:.4f}")
print(f"  95% CI Lower Bound: {ci_lower:.4f}")
print(f"  95% CI Upper Bound: {ci_upper:.4f}")
print(f"  CI Width:           {ci_upper - ci_lower:.4f}")

# --- Analytical Comparison ---
# INTENT: Compare bootstrap CI to the analytical normal-theory CI for validation.
# REASONING: With n=1000 from a normal distribution, the analytical CI
# (mean +/- 1.96 * SE) should be very close to the bootstrap CI.
# This serves as a sanity check on the bootstrap procedure.
se = sample_sd / np.sqrt(SAMPLE_SIZE)
analytical_lower = sample_mean - 1.96 * se
analytical_upper = sample_mean + 1.96 * se

print(f"\nAnalytical CI (for comparison):")
print(f"  SE:                 {se:.4f}")
print(f"  95% CI Lower Bound: {analytical_lower:.4f}")
print(f"  95% CI Upper Bound: {analytical_upper:.4f}")
print(f"  CI Width:           {analytical_upper - analytical_lower:.4f}")

# --- Save ---
# INTENT: Save the sample mean, CI bounds, and all 1000 raw samples to a parquet file.
# REASONING: Using a two-part structure: (1) a scalar results row with the summary
# statistics and (2) a column containing all 1000 raw samples. Polars stores
# the raw samples as a list column, keeping everything in one tidy DataFrame.
# ASSUMES: Output directory exists or can be created.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

results_df = pl.DataFrame({
    "sample_mean": [sample_mean],
    "ci_lower": [ci_lower],
    "ci_upper": [ci_upper],
    "n_samples": [SAMPLE_SIZE],
    "n_bootstrap": [N_BOOTSTRAP],
    "ci_level": [CI_LEVEL],
    "population_mean": [POPULATION_MEAN],
    "population_sd": [POPULATION_SD],
    "seed": [SEED],
    "raw_samples": [samples.tolist()],
})

results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- Validate ---
# INTENT: Read the parquet file back and verify it was written correctly.
# REASONING: Round-trip verification ensures parquet serialization preserved
# all values, especially the nested list column (raw_samples).
print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

validation_passed = True

# Check 1: File exists and is readable
readback = pl.read_parquet(OUTPUT_PATH)
print(f"\n[PASS] Parquet file readable: {readback.shape[0]} row x {readback.shape[1]} cols")

# Check 2: Schema correctness
expected_cols = ["sample_mean", "ci_lower", "ci_upper", "n_samples",
                 "n_bootstrap", "ci_level", "population_mean", "population_sd",
                 "seed", "raw_samples"]
missing_cols = [c for c in expected_cols if c not in readback.columns]
if missing_cols:
    print(f"[FAIL] Missing columns: {missing_cols}")
    validation_passed = False
else:
    print(f"[PASS] All {len(expected_cols)} expected columns present")

# Check 3: Sample mean matches
readback_mean = readback["sample_mean"][0]
mean_match = abs(readback_mean - sample_mean) < 1e-10
if mean_match:
    print(f"[PASS] Sample mean round-trip: {readback_mean:.4f}")
else:
    print(f"[FAIL] Sample mean mismatch: written={sample_mean}, read={readback_mean}")
    validation_passed = False

# Check 4: CI bounds are sensible
ci_contains_pop_mean = ci_lower <= POPULATION_MEAN <= ci_upper
if ci_contains_pop_mean:
    print(f"[PASS] 95% CI [{ci_lower:.4f}, {ci_upper:.4f}] contains population mean {POPULATION_MEAN}")
else:
    print(f"[NOTE] 95% CI [{ci_lower:.4f}, {ci_upper:.4f}] does not contain population mean {POPULATION_MEAN}")
    print(f"       (This can happen ~5% of the time by design)")

# Check 5: CI width is reasonable
# REASONING: For n=1000, SD=10, the analytical CI width is ~2*1.96*10/sqrt(1000) = ~1.24.
# Bootstrap CI width should be similar. Flag if wildly different.
expected_width = 2 * 1.96 * POPULATION_SD / np.sqrt(SAMPLE_SIZE)
actual_width = ci_upper - ci_lower
width_ratio = actual_width / expected_width
if 0.7 < width_ratio < 1.3:
    print(f"[PASS] CI width {actual_width:.4f} is within 30% of analytical expectation {expected_width:.4f}")
else:
    print(f"[WARN] CI width {actual_width:.4f} deviates from analytical expectation {expected_width:.4f} (ratio: {width_ratio:.2f})")

# Check 6: Raw samples round-trip
raw_samples_readback = readback["raw_samples"][0]
if len(raw_samples_readback) == SAMPLE_SIZE:
    print(f"[PASS] Raw samples round-trip: {len(raw_samples_readback)} samples preserved")
else:
    print(f"[FAIL] Raw samples count mismatch: expected {SAMPLE_SIZE}, got {len(raw_samples_readback)}")
    validation_passed = False

# Check 7: File size sanity
file_size_kb = OUTPUT_PATH.stat().st_size / 1024
print(f"[PASS] File size: {file_size_kb:.1f} KB")

print(f"\nVALIDATION: {'PASSED' if validation_passed else 'FAILED'}")
print("=" * 60)

if not validation_passed:
    raise ValueError("Validation FAILED - see details above")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:19:15
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_1/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_monte-carlo-sim.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Ad Hoc: Monte Carlo Simulation + Bootstrap CI
# ============================================================
# 
# Generated 1,000 samples from N(50, 10)
# Sample shape: (1000,)
# 
# Pre-state (raw samples):
#   Sample mean: 49.7111
#   Sample SD:   9.8922
#   Min:         13.5159
#   Max:         81.7885
# 
# Bootstrap Results (10,000 resamples):
#   Sample Mean:        49.7111
#   95% CI Lower Bound: 49.0882
#   95% CI Upper Bound: 50.3239
#   CI Width:           1.2357
# 
# Analytical CI (for comparison):
#   SE:                 0.3128
#   95% CI Lower Bound: 49.0980
#   95% CI Upper Bound: 50.3242
#   CI Width:           1.2262
# 
# Saved: /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_1/research/2026-06-08_AdHoc_Session/output/analysis/2026-06-08_monte-carlo-results.parquet
# 
# ============================================================
# VALIDATION
# ============================================================
# 
# [PASS] Parquet file readable: 1 row x 10 cols
# [PASS] All 10 expected columns present
# [PASS] Sample mean round-trip: 49.7111
# [PASS] 95% CI [49.0882, 50.3239] contains population mean 50
# [PASS] CI width 1.2357 is within 30% of analytical expectation 1.2396
# [PASS] Raw samples round-trip: 1000 samples preserved
# [PASS] File size: 10.9 KB
# 
# VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
