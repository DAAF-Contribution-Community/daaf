"""
Monte Carlo Simulation: Bootstrap Confidence Intervals
======================================================

INTENT: Draw samples from a normal distribution, compute sample statistics,
        and generate bootstrap confidence intervals to demonstrate sampling
        variability and interval estimation.

REASONING: This simulation illustrates fundamental statistical concepts—
           how sample means vary across repeated sampling, and how bootstrap
           resampling provides valid confidence intervals without distributional
           assumptions. Results are saved for review and documentation.

ASSUMES: NumPy's random seed is fixed for reproducibility. Bootstrap CI
         calculation assumes iid resampling without replacement. All
         intermediate and final statistics are printed to stdout for capture.
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
SEED = 42
SAMPLE_SIZE = 1000
NORMAL_MEAN = 50
NORMAL_SD = 10
BOOTSTRAP_RESAMPLES = 10000
CI_LEVEL = 0.95
OUTPUT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_1/research/2026-06-08_AdHoc_MonteCarlo/data/processed")

# --- Load ---
# Set seed for reproducibility
np.random.seed(SEED)

# INTENT: Draw a sample of size 1000 from the target normal distribution.
# REASONING: We use np.random.normal() with the specified parameters to
#           generate iid normal observations.
# ASSUMES: NumPy's RNG produces sufficient samples without memory issues.
sample = np.random.normal(loc=NORMAL_MEAN, scale=NORMAL_SD, size=SAMPLE_SIZE)

print("=" * 70)
print("MONTE CARLO SIMULATION: BOOTSTRAP CONFIDENCE INTERVALS")
print("=" * 70)

# --- Pre-State Capture ---
print("\n[PRE-STATE] Original Sample")
print(f"  Sample size: {len(sample)}")
print(f"  First 5 values: {sample[:5].tolist()}")
print(f"  Last 5 values: {sample[-5:].tolist()}")
print(f"  Min: {sample.min():.4f}, Max: {sample.max():.4f}")

# --- Transform: Compute Sample Mean ---
# INTENT: Calculate the sample mean as our point estimate.
# REASONING: The sample mean is the standard estimator of the population mean;
#           it is unbiased and has known sampling distribution under normality.
# ASSUMES: No missing values in the sample.
sample_mean = np.mean(sample)

print(f"\n[POINT ESTIMATE]")
print(f"  Sample mean: {sample_mean:.6f}")
print(f"  Target population mean: {NORMAL_MEAN}")
print(f"  Difference from target: {sample_mean - NORMAL_MEAN:.6f}")

# --- Transform: Bootstrap Confidence Interval ---
# INTENT: Generate bootstrap confidence interval via percentile method.
# REASONING: Bootstrap resampling estimates the sampling distribution of the mean
#           without parametric assumptions. The percentile method uses the empirical
#           quantiles of the bootstrap distribution as CI endpoints.
# ASSUMES: iid bootstrap resamples with replacement from the original sample.
#         Percentile method is valid for sample sizes ≥ 1000 (sufficient resamples).

print(f"\n[BOOTSTRAP RESAMPLING]")
print(f"  Number of bootstrap resamples: {BOOTSTRAP_RESAMPLES:,}")

bootstrap_means = np.array([
    np.mean(np.random.choice(sample, size=len(sample), replace=True))
    for _ in range(BOOTSTRAP_RESAMPLES)
])

# Calculate percentile CI
alpha = 1 - CI_LEVEL
lower_percentile = (alpha / 2) * 100
upper_percentile = (1 - alpha / 2) * 100

ci_lower = np.percentile(bootstrap_means, lower_percentile)
ci_upper = np.percentile(bootstrap_means, upper_percentile)

print(f"  Bootstrap CI percentiles: {lower_percentile:.1f}%, {upper_percentile:.1f}%")
print(f"  Bootstrap mean of bootstrap means: {np.mean(bootstrap_means):.6f}")
print(f"  Bootstrap SD of sample mean: {np.std(bootstrap_means):.6f}")

# --- Validate: Checkpoint (CP3 - Post-Transform) ---
# INTENT: Verify that bootstrap calculation produced valid results.
# REASONING: Check that CI bounds are sensible (lower < upper), CI covers the
#           sample mean, and the bootstrap distribution has expected properties.

print(f"\n[CP3: POST-TRANSFORM VALIDATION]")

# Check CI bounds sanity
assert ci_lower < ci_upper, f"CI bounds inverted: {ci_lower} >= {ci_upper}"
assert ci_lower < sample_mean < ci_upper, f"Sample mean outside own CI: [{ci_lower}, {ci_upper}]"
assert len(bootstrap_means) == BOOTSTRAP_RESAMPLES, \
    f"Bootstrap resamples mismatch: {len(bootstrap_means)} != {BOOTSTRAP_RESAMPLES}"

print(f"  ✓ CI bounds are sensible (lower < upper)")
print(f"  ✓ Sample mean falls within its own CI")
print(f"  ✓ Bootstrap resamples count matches config")
print(f"  ✓ CP3 PASSED")

# --- Save: Prepare Results DataFrame ---
# INTENT: Create a summary table with key results for persistence.
# REASONING: A single-row parquet file serves as a data artifact that can be
#           loaded and inspected later. This maintains reproducibility and
#           allows downstream analysis if needed.
# ASSUMES: Polars can write to the output directory (permissions, existence).

print(f"\n[SAVE]")

results_df = pl.DataFrame({
    "sample_size": [SAMPLE_SIZE],
    "mean": [sample_mean],
    "ci_lower": [ci_lower],
    "ci_upper": [ci_upper],
    "ci_level": [CI_LEVEL],
    "bootstrap_resamples": [BOOTSTRAP_RESAMPLES],
    "seed": [SEED],
})

print(f"  Results DataFrame shape: {results_df.shape}")
print(f"  Columns: {results_df.columns}")

# Create output directory if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Write parquet file
output_file = OUTPUT_DIR / "2026-06-08_monte-carlo-results.parquet"
results_df.write_parquet(output_file)

print(f"  Parquet file written: {output_file}")

# Verify file was written
assert output_file.exists(), f"Output file not found: {output_file}"
print(f"  ✓ File verified on disk")

# --- Post-State Capture ---
print(f"\n[POST-STATE] Results DataFrame")
print(f"  Rows: {len(results_df)}")
print(f"  Columns: {results_df.columns}")
print(f"\n{results_df}")

# --- Summary Output ---
print("\n" + "=" * 70)
print("SIMULATION SUMMARY")
print("=" * 70)
print(f"Sample mean:        {sample_mean:.6f}")
print(f"95% CI (bootstrap): [{ci_lower:.6f}, {ci_upper:.6f}]")
print(f"CI width:           {ci_upper - ci_lower:.6f}")
print(f"Results saved to:   {output_file}")
print("=" * 70)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:17:51
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_1/research/2026-06-08_AdHoc_MonteCarlo/scripts/adhoc/01_monte-carlo-sim.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ======================================================================
# MONTE CARLO SIMULATION: BOOTSTRAP CONFIDENCE INTERVALS
# ======================================================================
# 
# [PRE-STATE] Original Sample
#   Sample size: 1000
#   First 5 values: [54.96714153011233, 48.61735698828815, 56.47688538100692, 65.23029856408026, 47.658466252766644]
#   Last 5 values: [47.18899707114045, 67.97686526849523, 56.4084286126701, 44.28821010217203, 55.72582781356159]
#   Min: 17.5873, Max: 88.5273
# 
# [POINT ESTIMATE]
#   Sample mean: 50.193321
#   Target population mean: 50
#   Difference from target: 0.193321
# 
# [BOOTSTRAP RESAMPLING]
#   Number of bootstrap resamples: 10,000
#   Bootstrap CI percentiles: 2.5%, 97.5%
#   Bootstrap mean of bootstrap means: 50.196769
#   Bootstrap SD of sample mean: 0.310803
# 
# [CP3: POST-TRANSFORM VALIDATION]
#   ✓ CI bounds are sensible (lower < upper)
#   ✓ Sample mean falls within its own CI
#   ✓ Bootstrap resamples count matches config
#   ✓ CP3 PASSED
# 
# [SAVE]
#   Results DataFrame shape: (1, 7)
#   Columns: ['sample_size', 'mean', 'ci_lower', 'ci_upper', 'ci_level', 'bootstrap_resamples', 'seed']
#   Parquet file written: /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_1/research/2026-06-08_AdHoc_MonteCarlo/data/processed/2026-06-08_monte-carlo-results.parquet
#   ✓ File verified on disk
# 
# [POST-STATE] Results DataFrame
#   Rows: 1
#   Columns: ['sample_size', 'mean', 'ci_lower', 'ci_upper', 'ci_level', 'bootstrap_resamples', 'seed']
# 
# shape: (1, 7)
# ┌─────────────┬───────────┬───────────┬───────────┬──────────┬─────────────────────┬──────┐
# │ sample_size ┆ mean      ┆ ci_lower  ┆ ci_upper  ┆ ci_level ┆ bootstrap_resamples ┆ seed │
# │ ---         ┆ ---       ┆ ---       ┆ ---       ┆ ---      ┆ ---                 ┆ ---  │
# │ i64         ┆ f64       ┆ f64       ┆ f64       ┆ f64      ┆ i64                 ┆ i64  │
# ╞═════════════╪═══════════╪═══════════╪═══════════╪══════════╪═════════════════════╪══════╡
# │ 1000        ┆ 50.193321 ┆ 49.594178 ┆ 50.812164 ┆ 0.95     ┆ 10000               ┆ 42   │
# └─────────────┴───────────┴───────────┴───────────┴──────────┴─────────────────────┴──────┘
# 
# ======================================================================
# SIMULATION SUMMARY
# ======================================================================
# Sample mean:        50.193321
# 95% CI (bootstrap): [49.594178, 50.812164]
# CI width:           1.217985
# Results saved to:   /daaf/benchmarks/_sandbox/run_dc-01_Haiku_4.5_1/research/2026-06-08_AdHoc_MonteCarlo/data/processed/2026-06-08_monte-carlo-results.parquet
# ======================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
