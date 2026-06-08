#!/usr/bin/env python3
"""
Ad Hoc: Monte Carlo simulation with bootstrap confidence interval.

Task: monte-carlo-sim
Mode: Ad Hoc Collaboration
Depends on: None
Input: None (generates synthetic data)
Output: output/analysis/2026-06-08_monte-carlo-results.parquet
Checkpoint: Inline validation (shape, CI bounds, sample statistics)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for Monte Carlo simulation and bootstrap CI estimation.
# Parameters are specified by the user request: N=1000 draws from Normal(50,10),
# bootstrap CI with B=10,000 resamples, seed=42 for reproducibility.
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session")
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / "2026-06-08_monte-carlo-results.parquet"

SEED = 42
N_SAMPLES = 1000
DIST_MEAN = 50
DIST_STD = 10
N_BOOTSTRAP = 10_000
CI_LEVEL = 0.95

print("=" * 60)
print("Ad Hoc: Monte Carlo Simulation + Bootstrap CI")
print("=" * 60)

# --- Pre-state ---
# No input data to capture pre-state for. Document parameter configuration.
print(f"\nParameters:")
print(f"  N samples:       {N_SAMPLES:,}")
print(f"  Distribution:    Normal(mean={DIST_MEAN}, std={DIST_STD})")
print(f"  Bootstrap B:     {N_BOOTSTRAP:,}")
print(f"  CI level:        {CI_LEVEL}")
print(f"  Random seed:     {SEED}")

# --- Generate Samples ---
# INTENT: Draw N=1000 samples from Normal(50, 10) to form the base dataset for
# bootstrap CI estimation. This simulates a single draw from a known population.
# REASONING: Using numpy's default_rng with explicit seed (42) rather than
# legacy np.random.seed() because Generator-based RNG is the modern numpy
# standard and provides better statistical properties.
# ASSUMES: numpy's PCG64 PRNG produces sufficiently random draws for this
# simulation purpose.
rng = np.random.default_rng(SEED)
samples = rng.normal(loc=DIST_MEAN, scale=DIST_STD, size=N_SAMPLES)

sample_mean = float(np.mean(samples))
sample_std = float(np.std(samples, ddof=1))
sample_min = float(np.min(samples))
sample_max = float(np.max(samples))

print(f"\nSample statistics:")
print(f"  Mean:   {sample_mean:.4f}")
print(f"  Std:    {sample_std:.4f}")
print(f"  Min:    {sample_min:.4f}")
print(f"  Max:    {sample_max:.4f}")

# --- Bootstrap CI ---
# INTENT: Compute a 95% bootstrap confidence interval for the sample mean using
# 10,000 bootstrap resamples (percentile method).
# REASONING: The percentile method is the simplest valid bootstrap CI approach.
# With B=10,000 resamples, the 2.5th and 97.5th percentiles of the bootstrap
# distribution give a non-parametric 95% CI. This is preferred over the normal
# approximation CI when distributional assumptions may not hold (though for this
# simulation the population is normal by construction).
# ASSUMES: B=10,000 is sufficient for stable CI bounds at the 95% level
# (standard recommendation is B >= 1,000 for percentile CIs).
alpha = 1 - CI_LEVEL
lower_pct = (alpha / 2) * 100  # 2.5th percentile
upper_pct = (1 - alpha / 2) * 100  # 97.5th percentile

# Generate all bootstrap resamples at once for efficiency
# REASONING: Drawing all B*N random indices in one call is vectorized and
# substantially faster than a Python loop over B iterations.
bootstrap_indices = rng.integers(0, N_SAMPLES, size=(N_BOOTSTRAP, N_SAMPLES))
bootstrap_means = np.mean(samples[bootstrap_indices], axis=1)

ci_lower = float(np.percentile(bootstrap_means, lower_pct))
ci_upper = float(np.percentile(bootstrap_means, upper_pct))

print(f"\nBootstrap 95% CI for the mean:")
print(f"  Lower: {ci_lower:.4f}")
print(f"  Upper: {ci_upper:.4f}")
print(f"  Width: {ci_upper - ci_lower:.4f}")

# --- Construct Output DataFrame ---
# INTENT: Save results as a parquet file containing both the summary statistics
# (sample mean, CI bounds) and the raw 1000 drawn samples.
# REASONING: Storing each sample as a row with repeated summary columns allows
# downstream consumers to both access raw data and read summary stats from any
# single row. This avoids needing separate files for summary vs. raw data.
# ASSUMES: Polars will broadcast scalar values across all 1000 rows automatically.
results_df = pl.DataFrame({
    "sample_id": list(range(1, N_SAMPLES + 1)),
    "sample_value": samples.tolist(),
    "sample_mean": [sample_mean] * N_SAMPLES,
    "ci_lower": [ci_lower] * N_SAMPLES,
    "ci_upper": [ci_upper] * N_SAMPLES,
})

print(f"\nOutput DataFrame shape: {results_df.shape[0]:,} rows x {results_df.shape[1]} cols")
print(f"Columns: {results_df.columns}")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- Validate ---
# Inline checkpoint: verify output integrity, CI properties, and file persistence.
print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

# V1: Correct number of samples
v1_ok = results_df.shape[0] == N_SAMPLES
print(f"  [{'PASS' if v1_ok else 'FAIL'}] Row count: {results_df.shape[0]:,} (expected {N_SAMPLES:,})")

# V2: All required columns present
required_cols = ["sample_id", "sample_value", "sample_mean", "ci_lower", "ci_upper"]
v2_ok = all(c in results_df.columns for c in required_cols)
print(f"  [{'PASS' if v2_ok else 'FAIL'}] Required columns present: {required_cols}")

# V3: No null values in any column
null_count = results_df.null_count().sum_horizontal()[0]
v3_ok = null_count == 0
print(f"  [{'PASS' if v3_ok else 'FAIL'}] No nulls: {null_count}")

# V4: CI lower < sample mean < CI upper (sanity check)
v4_ok = ci_lower < sample_mean < ci_upper
print(f"  [{'PASS' if v4_ok else 'FAIL'}] CI contains sample mean: {ci_lower:.4f} < {sample_mean:.4f} < {ci_upper:.4f}")

# V5: CI is reasonably narrow (for N=1000, SE ~ 10/sqrt(1000) ~ 0.316,
# so 95% CI width should be approximately 2 * 1.96 * 0.316 ~ 1.24)
# REASONING: Allow generous bounds (0.5 to 3.0) to account for bootstrap variability.
ci_width = ci_upper - ci_lower
v5_ok = 0.5 < ci_width < 3.0
print(f"  [{'PASS' if v5_ok else 'WARN'}] CI width reasonable: {ci_width:.4f} (expected ~1.24)")

# V6: Sample mean is within plausible range of true mean
# REASONING: With N=1000 and std=10, the sample mean should be within ~1 of
# the true mean (50) with very high probability.
v6_ok = abs(sample_mean - DIST_MEAN) < 3 * (DIST_STD / np.sqrt(N_SAMPLES))
print(f"  [{'PASS' if v6_ok else 'WARN'}] Sample mean plausible: |{sample_mean:.4f} - {DIST_MEAN}| < {3 * (DIST_STD / np.sqrt(N_SAMPLES)):.4f}")

# V7: Output file exists on disk
v7_ok = OUTPUT_PATH.exists()
print(f"  [{'PASS' if v7_ok else 'FAIL'}] Output file exists: {OUTPUT_PATH}")

# V8: Parquet file is readable
try:
    reread_df = pl.read_parquet(OUTPUT_PATH)
    v8_ok = reread_df.shape == results_df.shape
    print(f"  [{'PASS' if v8_ok else 'FAIL'}] Parquet readable: {reread_df.shape}")
except Exception as e:
    v8_ok = False
    print(f"  [FAIL] Parquet readable: {e}")

all_passed = all([v1_ok, v2_ok, v3_ok, v4_ok, v5_ok, v6_ok, v7_ok, v8_ok])

assert v1_ok, "STOP: Wrong number of rows"
assert v2_ok, "STOP: Missing required columns"
assert v3_ok, "STOP: Unexpected nulls"
assert v4_ok, "STOP: CI does not contain sample mean"
assert v7_ok, "STOP: Output file not saved"
assert v8_ok, "STOP: Output file not readable"

print("\n" + "=" * 60)
print(f"VALIDATION: {'PASSED' if all_passed else 'PASSED WITH WARNINGS'}")
print("=" * 60)

# --- Post-state ---
# Final summary of all outputs for the execution record.
print(f"\n--- Final Summary ---")
print(f"  Sample mean:    {sample_mean:.4f}")
print(f"  95% CI:         [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  Output shape:   {results_df.shape[0]} rows x {results_df.shape[1]} cols")
print(f"  Output file:    {OUTPUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 02:21:09
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_monte-carlo-sim.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Ad Hoc: Monte Carlo Simulation + Bootstrap CI
# ============================================================
# 
# Parameters:
#   N samples:       1,000
#   Distribution:    Normal(mean=50, std=10)
#   Bootstrap B:     10,000
#   CI level:        0.95
#   Random seed:     42
# 
# Sample statistics:
#   Mean:   49.7111
#   Std:    9.8922
#   Min:    13.5159
#   Max:    81.7885
# 
# Bootstrap 95% CI for the mean:
#   Lower: 49.0882
#   Upper: 50.3239
#   Width: 1.2357
# 
# Output DataFrame shape: 1,000 rows x 5 cols
# Columns: ['sample_id', 'sample_value', 'sample_mean', 'ci_lower', 'ci_upper']
# 
# Saved: /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/output/analysis/2026-06-08_monte-carlo-results.parquet
# 
# ============================================================
# VALIDATION
# ============================================================
#   [PASS] Row count: 1,000 (expected 1,000)
#   [PASS] Required columns present: ['sample_id', 'sample_value', 'sample_mean', 'ci_lower', 'ci_upper']
#   [PASS] No nulls: 0
#   [PASS] CI contains sample mean: 49.0882 < 49.7111 < 50.3239
#   [PASS] CI width reasonable: 1.2357 (expected ~1.24)
#   [PASS] Sample mean plausible: |49.7111 - 50| < 0.9487
#   [PASS] Output file exists: /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/output/analysis/2026-06-08_monte-carlo-results.parquet
#   [PASS] Parquet readable: (1000, 5)
# 
# ============================================================
# VALIDATION: PASSED
# ============================================================
# 
# --- Final Summary ---
#   Sample mean:    49.7111
#   95% CI:         [49.0882, 50.3239]
#   Output shape:   1000 rows x 5 cols
#   Output file:    /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/output/analysis/2026-06-08_monte-carlo-results.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
