#!/usr/bin/env python3
"""
Ad Hoc: Monte Carlo simulation with bootstrap confidence intervals.

Task: monte-carlo-sim
Mode: Ad Hoc Collaboration
Depends on: None
Input: None (generated via simulation)
Output: data/processed/monte_carlo_results.parquet
Checkpoint: Inline validation (sample mean, CI bounds, CI coverage, file persistence)
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# INTENT: Define simulation parameters for a Monte Carlo draw with bootstrap CI.
# REASONING: Fixed seed ensures reproducibility across runs. Parameters chosen
# per user specification: N(mean=50, sd=10), 1000 samples, 10000 bootstrap resamples.
# ASSUMES: numpy and polars are available in the execution environment.

PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session")
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / "monte_carlo_results.parquet"

SEED = 42
TRUE_MEAN = 50
TRUE_SD = 10
N_SAMPLES = 1000
N_BOOTSTRAP = 10_000
CI_LEVEL = 0.95

print("=" * 60)
print("Monte Carlo Simulation with Bootstrap 95% CI")
print("=" * 60)
print(f"  True mean:          {TRUE_MEAN}")
print(f"  True SD:            {TRUE_SD}")
print(f"  N samples:          {N_SAMPLES:,}")
print(f"  N bootstrap:        {N_BOOTSTRAP:,}")
print(f"  CI level:           {CI_LEVEL}")
print(f"  Random seed:        {SEED}")

# --- Generate Samples ---
# INTENT: Draw 1000 samples from N(50, 10) using a fixed seed for reproducibility.
# REASONING: numpy's default_rng provides a modern, reproducible PRNG. Drawing
# all samples at once is efficient and ensures a single random stream.
# ASSUMES: Normal distribution is the correct generative model per user request.

rng = np.random.default_rng(SEED)
samples = rng.normal(loc=TRUE_MEAN, scale=TRUE_SD, size=N_SAMPLES)

sample_mean = float(np.mean(samples))
sample_sd = float(np.std(samples, ddof=1))

print(f"\n--- Sample Statistics ---")
print(f"  Sample mean:        {sample_mean:.4f}")
print(f"  Sample SD:          {sample_sd:.4f}")
print(f"  Sample min:         {np.min(samples):.4f}")
print(f"  Sample max:         {np.max(samples):.4f}")

# --- Bootstrap Confidence Interval ---
# INTENT: Compute a 95% confidence interval for the sample mean using the
# percentile bootstrap method with 10,000 resamples.
# REASONING: The percentile bootstrap is simple, assumption-free, and
# appropriate for estimating the sampling distribution of the mean. With
# 10,000 resamples, the CI boundaries are stable (Monte Carlo error is small).
# ASSUMES: The original sample is representative enough that resampling from
# it approximates the true sampling distribution. For N=1000 from a normal
# distribution, this is well-justified.

alpha = 1 - CI_LEVEL
lower_pct = (alpha / 2) * 100      # 2.5th percentile
upper_pct = (1 - alpha / 2) * 100  # 97.5th percentile

# INTENT: Generate bootstrap resamples and compute the mean of each.
# REASONING: Vectorized approach -- draw all bootstrap indices at once as a
# (N_BOOTSTRAP x N_SAMPLES) matrix, then compute row means. This avoids a
# Python loop over 10,000 iterations and is significantly faster.
# ASSUMES: Memory is sufficient for a (10000 x 1000) float64 array (~76 MB).

bootstrap_indices = rng.integers(0, N_SAMPLES, size=(N_BOOTSTRAP, N_SAMPLES))
bootstrap_means = np.mean(samples[bootstrap_indices], axis=1)

ci_lower = float(np.percentile(bootstrap_means, lower_pct))
ci_upper = float(np.percentile(bootstrap_means, upper_pct))
ci_width = ci_upper - ci_lower

print(f"\n--- Bootstrap Results ---")
print(f"  Bootstrap mean of means:  {np.mean(bootstrap_means):.4f}")
print(f"  Bootstrap SE of mean:     {np.std(bootstrap_means, ddof=1):.4f}")
print(f"  95% CI lower bound:       {ci_lower:.4f}")
print(f"  95% CI upper bound:       {ci_upper:.4f}")
print(f"  CI width:                 {ci_width:.4f}")

# --- Save Results ---
# INTENT: Save the sample mean, CI bounds, and original 1000 samples as a
# parquet file for downstream consumption.
# REASONING: The results parquet contains one row per original sample, plus
# metadata columns (sample_mean, ci_lower, ci_upper) repeated on each row.
# This keeps the original samples accessible while attaching summary statistics.
# An alternative would be separate summary and sample tables, but a single file
# is simpler for ad hoc use.
# ASSUMES: Repeating scalar metadata across rows is acceptable for a 1000-row
# dataset (minimal storage overhead).

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

results_df = pl.DataFrame({
    "sample_id": list(range(1, N_SAMPLES + 1)),
    "sample_value": samples.tolist(),
    "sample_mean": [sample_mean] * N_SAMPLES,
    "ci_lower": [ci_lower] * N_SAMPLES,
    "ci_upper": [ci_upper] * N_SAMPLES,
})

results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"  Shape: {results_df.shape[0]:,} rows x {results_df.shape[1]} cols")
print(f"  Columns: {results_df.columns}")

# --- Validate ---
# INTENT: Verify simulation correctness, CI coverage, and file persistence.
# REASONING: These checks confirm the simulation ran as specified and produced
# sensible results. The CI should contain the true mean (50) with high
# probability. File persistence confirms the parquet was written successfully.

print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

# V1: Sample count matches specification
count_ok = len(samples) == N_SAMPLES
print(f"  [{'PASS' if count_ok else 'FAIL'}] Sample count: {len(samples)} (expected {N_SAMPLES})")

# V2: Sample mean is plausible (within 3 SE of true mean)
# REASONING: For N=1000, SE = 10/sqrt(1000) ~ 0.316. Three SEs gives a
# range of ~49.05 to ~50.95. Any sample mean outside this is extremely unlikely.
se_theoretical = TRUE_SD / np.sqrt(N_SAMPLES)
mean_plausible = abs(sample_mean - TRUE_MEAN) < 3 * se_theoretical
print(f"  [{'PASS' if mean_plausible else 'WARN'}] Sample mean plausible: {sample_mean:.4f} (true={TRUE_MEAN}, 3SE={3*se_theoretical:.4f})")

# V3: CI contains the true mean
ci_contains_true = ci_lower <= TRUE_MEAN <= ci_upper
print(f"  [{'PASS' if ci_contains_true else 'NOTE'}] CI contains true mean ({TRUE_MEAN}): [{ci_lower:.4f}, {ci_upper:.4f}]")

# V4: CI width is reasonable
# REASONING: Theoretical 95% CI width for N=1000 is approximately
# 2 * 1.96 * SE = 2 * 1.96 * 0.316 ~ 1.24. Bootstrap CI should be similar.
theoretical_ci_width = 2 * 1.96 * se_theoretical
width_reasonable = 0.5 * theoretical_ci_width < ci_width < 2.0 * theoretical_ci_width
print(f"  [{'PASS' if width_reasonable else 'WARN'}] CI width reasonable: {ci_width:.4f} (theoretical ~{theoretical_ci_width:.4f})")

# V5: Bootstrap resamples count
bootstrap_count_ok = len(bootstrap_means) == N_BOOTSTRAP
print(f"  [{'PASS' if bootstrap_count_ok else 'FAIL'}] Bootstrap resample count: {len(bootstrap_means):,} (expected {N_BOOTSTRAP:,})")

# V6: Output file exists and is readable
file_exists = OUTPUT_PATH.exists()
print(f"  [{'PASS' if file_exists else 'FAIL'}] Output file exists: {OUTPUT_PATH}")

if file_exists:
    verify_df = pl.read_parquet(OUTPUT_PATH)
    file_readable = verify_df.shape == (N_SAMPLES, 5)
    print(f"  [{'PASS' if file_readable else 'FAIL'}] File readable with correct shape: {verify_df.shape}")
else:
    file_readable = False

# V7: Data types correct
if file_exists:
    dtypes = {col: str(dtype) for col, dtype in zip(verify_df.columns, verify_df.dtypes)}
    print(f"  [INFO] Column dtypes: {dtypes}")

# --- Final Status ---
all_passed = all([count_ok, mean_plausible, ci_contains_true, width_reasonable,
                  bootstrap_count_ok, file_exists, file_readable])

assert count_ok, "STOP: Sample count mismatch"
assert file_exists, "STOP: Output file not written"
assert file_readable, "STOP: Output file has wrong shape"

print("\n" + "=" * 60)
if all_passed:
    print("VALIDATION: PASSED")
else:
    print("VALIDATION: PASSED WITH NOTES")
print("=" * 60)

# --- Key Results Summary ---
print(f"\n--- KEY RESULTS ---")
print(f"  Sample mean:     {sample_mean:.4f}")
print(f"  95% CI:          [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"  CI width:        {ci_width:.4f}")
print(f"  True mean in CI: {ci_contains_true}")
print(f"  Output file:     {OUTPUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:18:57
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_monte-carlo-sim.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Monte Carlo Simulation with Bootstrap 95% CI
# ============================================================
#   True mean:          50
#   True SD:            10
#   N samples:          1,000
#   N bootstrap:        10,000
#   CI level:           0.95
#   Random seed:        42
# 
# --- Sample Statistics ---
#   Sample mean:        49.7111
#   Sample SD:          9.8922
#   Sample min:         13.5159
#   Sample max:         81.7885
# 
# --- Bootstrap Results ---
#   Bootstrap mean of means:  49.7078
#   Bootstrap SE of mean:     0.3125
#   95% CI lower bound:       49.0882
#   95% CI upper bound:       50.3239
#   CI width:                 1.2357
# 
# Saved: /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/processed/monte_carlo_results.parquet
#   Shape: 1,000 rows x 5 cols
#   Columns: ['sample_id', 'sample_value', 'sample_mean', 'ci_lower', 'ci_upper']
# 
# ============================================================
# VALIDATION
# ============================================================
#   [PASS] Sample count: 1000 (expected 1000)
#   [PASS] Sample mean plausible: 49.7111 (true=50, 3SE=0.9487)
#   [PASS] CI contains true mean (50): [49.0882, 50.3239]
#   [PASS] CI width reasonable: 1.2357 (theoretical ~1.2396)
#   [PASS] Bootstrap resample count: 10,000 (expected 10,000)
#   [PASS] Output file exists: /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/processed/monte_carlo_results.parquet
#   [PASS] File readable with correct shape: (1000, 5)
#   [INFO] Column dtypes: {'sample_id': 'Int64', 'sample_value': 'Float64', 'sample_mean': 'Float64', 'ci_lower': 'Float64', 'ci_upper': 'Float64'}
# 
# ============================================================
# VALIDATION: PASSED
# ============================================================
# 
# --- KEY RESULTS ---
#   Sample mean:     49.7111
#   95% CI:          [49.0882, 50.3239]
#   CI width:        1.2357
#   True mean in CI: True
#   Output file:     /daaf/benchmarks/_sandbox/run_dc-01_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/processed/monte_carlo_results.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
