#!/usr/bin/env python3
"""
Monte Carlo Simulation: Sampling Variability and Bootstrap Confidence Intervals

INTENT:
    Demonstrate sampling variability by drawing repeated samples from a known
    population distribution. Construct a bootstrap confidence interval to show
    how we quantify uncertainty about the sample mean.

REASONING:
    This script illustrates fundamental statistical concepts:
    1. Single sample from N(50, 10) with n=1000
    2. Bootstrap resampling to construct a 95% CI without assuming normality
    3. Validation that the CI bounds are reasonable (mean is contained)

ASSUMES:
    - numpy's random.standard_normal() produces independent N(0,1) samples
    - Bootstrap resamples with replacement from the observed sample
    - 1000 bootstrap iterations are sufficient for a stable 95% CI
    - Parquet format is available via polars
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---

# INTENT: Define simulation parameters (true population distribution)
# REASONING: These values are arbitrary but realistic for demonstration
TRUE_MEAN = 50
TRUE_STD = 10
SAMPLE_SIZE = 1000

# INTENT: Define bootstrap configuration for confidence interval
# REASONING: 1000 iterations provides stable quantile estimates; 95% CI uses 2.5/97.5 percentiles
BOOTSTRAP_SAMPLES = 1000
CI_LOWER_PERCENTILE = 2.5
CI_UPPER_PERCENTILE = 97.5

# INTENT: Define output file path
# REASONING: Ad Hoc mode stores processed results in data/processed/ directory
OUTPUT_DIR = Path("/daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/data/processed")
OUTPUT_FILE = OUTPUT_DIR / "monte_carlo_results.parquet"

print(f"[CONFIG] Sample size: {SAMPLE_SIZE}")
print(f"[CONFIG] Population: N({TRUE_MEAN}, {TRUE_STD})")
print(f"[CONFIG] Bootstrap iterations: {BOOTSTRAP_SAMPLES}")
print(f"[CONFIG] CI: {CI_LOWER_PERCENTILE}th to {CI_UPPER_PERCENTILE}th percentiles")
print()

# --- Load ---
# No external data load; we generate the sample from scratch

# --- Generate Sample ---

print("=" * 60)
print("STAGE 1: GENERATE SAMPLE FROM KNOWN DISTRIBUTION")
print("=" * 60)

# INTENT: Set random seed for reproducibility
# REASONING: Ensures results can be exactly replicated in future runs
# ASSUMES: seed=42 is arbitrary but fixed
np.random.seed(42)

# INTENT: Generate 1000 samples from N(50, 10)
# REASONING: numpy.random.normal(loc, scale, size) is the standard method
# ASSUMES: loc=50 (mean), scale=10 (std dev), size=1000 (number of samples)
sample = np.random.normal(loc=TRUE_MEAN, scale=TRUE_STD, size=SAMPLE_SIZE)

print(f"Generated sample of size: {len(sample)}")
print(f"Sample min: {sample.min():.4f}")
print(f"Sample max: {sample.max():.4f}")
print(f"Sample mean: {sample.mean():.4f}")
print(f"Sample std: {sample.std(ddof=1):.4f}")  # ddof=1 for sample std
print()

# --- Pre-State Capture ---

print("=" * 60)
print("CHECKPOINT 1: PRE-STATE CAPTURE")
print("=" * 60)

pre_state = {
    "sample_size": len(sample),
    "sample_mean": float(sample.mean()),
    "sample_std": float(sample.std(ddof=1)),
    "sample_min": float(sample.min()),
    "sample_max": float(sample.max()),
    "sample_first_3": sample[:3].tolist(),
}

print(f"Pre-state captured:")
print(f"  - Sample size: {pre_state['sample_size']}")
print(f"  - Mean: {pre_state['sample_mean']:.6f}")
print(f"  - Std: {pre_state['sample_std']:.6f}")
print(f"  - First 3 values: {pre_state['sample_first_3']}")
print()

# --- Bootstrap Confidence Interval ---

print("=" * 60)
print("STAGE 2: BOOTSTRAP 95% CONFIDENCE INTERVAL")
print("=" * 60)

# INTENT: Resample from the sample with replacement and compute bootstrap distribution
# REASONING: Bootstrap doesn't assume normality; uses observed data distribution
# ASSUMES: We resample with replacement (standard bootstrap); same size as original sample
bootstrap_means = []
for i in range(BOOTSTRAP_SAMPLES):
    # INTENT: Resample from the original sample with replacement
    # REASONING: Each bootstrap sample has the same size as original; some observations repeated
    # ASSUMES: random.choice samples with replacement uniformly
    bootstrap_sample = np.random.choice(sample, size=SAMPLE_SIZE, replace=True)
    bootstrap_means.append(bootstrap_sample.mean())

bootstrap_means = np.array(bootstrap_means)

print(f"Bootstrap iterations completed: {len(bootstrap_means)}")
print(f"Bootstrap mean estimates: min={bootstrap_means.min():.6f}, max={bootstrap_means.max():.6f}")
print()

# INTENT: Extract confidence interval bounds from bootstrap distribution
# REASONING: 2.5th and 97.5th percentiles define the central 95% CI
# ASSUMES: np.percentile() uses linear interpolation; sufficient for stable estimates
ci_lower = np.percentile(bootstrap_means, CI_LOWER_PERCENTILE)
ci_upper = np.percentile(bootstrap_means, CI_UPPER_PERCENTILE)

print(f"Bootstrap 95% CI for the mean:")
print(f"  Lower bound (2.5%): {ci_lower:.6f}")
print(f"  Upper bound (97.5%): {ci_upper:.6f}")
print(f"  CI width: {ci_upper - ci_lower:.6f}")
print()

# --- Validate Bootstrap CI ---

print("=" * 60)
print("CHECKPOINT 2: BOOTSTRAP CI VALIDATION")
print("=" * 60)

# INTENT: Verify that the sample mean lies within the bootstrap CI
# REASONING: This is a sanity check; the observed mean should be inside its own CI
# ASSUMES: If the mean is outside the CI, something is wrong with bootstrap computation
sample_mean = sample.mean()
ci_contains_mean = ci_lower <= sample_mean <= ci_upper

print(f"Sample mean: {sample_mean:.6f}")
print(f"CI range: [{ci_lower:.6f}, {ci_upper:.6f}]")
print(f"Mean is inside CI: {ci_contains_mean} (EXPECTED: True)")

if not ci_contains_mean:
    print("  [WARNING] Sample mean is OUTSIDE the bootstrap CI!")
    print("  This suggests a problem with bootstrap computation or insufficient iterations.")
else:
    print("  [PASS] Sample mean is properly contained in the CI.")
print()

# INTENT: Verify CI bounds are properly ordered and reasonable width
# REASONING: CI lower < upper is a basic requirement; width should be positive
# ASSUMES: Bootstrap iterations are sufficient to produce a non-degenerate interval
ci_is_valid = ci_lower < ci_upper
ci_width = ci_upper - ci_lower
ci_width_reasonable = ci_width > 0 and ci_width < (TRUE_STD / 2)  # Heuristic: should be narrower than half the std

print(f"CI bounds are properly ordered (lower < upper): {ci_is_valid}")
print(f"CI width ({ci_width:.6f}) is reasonable: {ci_width_reasonable}")

if not ci_is_valid:
    print("  [FAIL] CI bounds are not properly ordered!")
    raise ValueError("Bootstrap CI construction failed: bounds are reversed or identical.")

if not ci_width_reasonable:
    print("  [WARNING] CI width seems unexpectedly large or zero.")
else:
    print("  [PASS] CI width is reasonable.")
print()

# --- Prepare Output Data ---

print("=" * 60)
print("STAGE 3: PREPARE OUTPUT DATA")
print("=" * 60)

# INTENT: Create a DataFrame with the original sample and summary statistics
# REASONING: Include all relevant information in output for transparency and reproducibility
# ASSUMES: Polars DataFrame can efficiently serialize to parquet

# INTENT: Reshape sample and summary statistics into a table format
# REASONING: Parquet is columnar; one row per observation allows easy inspection
# Create a table with the sample values in one column
sample_data = {
    "sample_index": list(range(SAMPLE_SIZE)),
    "sample_value": sample.tolist(),
}

df_sample = pl.DataFrame(sample_data)

# INTENT: Create a separate summary row with the point estimates and CI bounds
# REASONING: Store scalar values (mean, CI bounds) as metadata rows or separate table
# ASSUMES: We can add metadata as additional rows or columns
summary_data = {
    "sample_index": [SAMPLE_SIZE, SAMPLE_SIZE + 1, SAMPLE_SIZE + 2],  # Index past the sample
    "sample_value": [sample_mean, ci_lower, ci_upper],
    "statistic_type": ["sample_mean", "ci_lower", "ci_upper"],
}

df_summary = pl.DataFrame(summary_data)

# INTENT: Combine sample values and summary statistics into a single table
# REASONING: Single output file simplifies downstream analysis; interpretation via statistic_type column
# ASSUMES: We add a column to distinguish sample values from statistics
df_sample = df_sample.with_columns(
    pl.lit("sample_value").alias("statistic_type")
)

df_output = pl.concat([df_sample, df_summary], how="vertical")

print(f"Output table shape: {df_output.shape}")
print(f"Columns: {df_output.columns}")
print()

# --- Pre-Save State ---

print("=" * 60)
print("CHECKPOINT 3: PRE-SAVE STATE")
print("=" * 60)

print(f"Output DataFrame shape: {df_output.shape[0]} rows x {df_output.shape[1]} columns")
print(f"Column names: {df_output.columns}")
print(f"Data types:\n{df_output.schema}")
print()

# --- Save to Parquet ---

print("=" * 60)
print("STAGE 4: SAVE OUTPUT")
print("=" * 60)

# INTENT: Ensure output directory exists
# REASONING: Prevents FileNotFoundError if directory was not created
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# INTENT: Write DataFrame to parquet format
# REASONING: Parquet is compressed, columnar, and portable; preserves dtypes
# ASSUMES: polars.write_parquet() is available and writeable to the target path
df_output.write_parquet(str(OUTPUT_FILE))

print(f"Saved output to: {OUTPUT_FILE}")
print(f"File exists: {OUTPUT_FILE.exists()}")
print(f"File size: {OUTPUT_FILE.stat().st_size:,} bytes")
print()

# --- Post-Save Validation ---

print("=" * 60)
print("CHECKPOINT 4: POST-SAVE VALIDATION")
print("=" * 60)

# INTENT: Read the saved file to verify integrity and completeness
# REASONING: Ensures data was written correctly and is readable
# ASSUMES: parquet file was successfully created and contains expected data

df_verified = pl.read_parquet(str(OUTPUT_FILE))

print(f"Verified read from disk:")
print(f"  Shape: {df_verified.shape}")
print(f"  Columns: {df_verified.columns}")
print(f"  First 3 rows:\n{df_verified.head(3)}")
print()

# INTENT: Extract and verify the summary statistics from the saved file
# REASONING: Cross-check that scalar values were preserved correctly
summary_rows = df_verified.filter(pl.col("statistic_type") != "sample_value")

print(f"Summary statistics rows:")
for row in summary_rows.to_dicts():
    print(f"  {row['statistic_type']}: {row['sample_value']:.6f}")
print()

# --- Final Validation Summary ---

print("=" * 60)
print("FINAL VALIDATION SUMMARY")
print("=" * 60)

validation_checks = {
    "Sample size is 1000": SAMPLE_SIZE == 1000,
    "Sample mean computed": True,  # Always computed
    "Bootstrap CI computed": ci_lower < ci_upper,
    "Mean is in CI": ci_contains_mean,
    "CI bounds are valid": ci_is_valid,
    "Output file exists": OUTPUT_FILE.exists(),
    "Output file is readable": True,  # Would have raised exception if not
    "Output shape matches input": df_verified.shape[0] == (SAMPLE_SIZE + 3),  # 1000 samples + 3 summary rows
}

for check_name, result in validation_checks.items():
    status = "PASS" if result else "FAIL"
    print(f"  [{status}] {check_name}")

all_passed = all(validation_checks.values())
print()

if all_passed:
    print("[SUCCESS] All validation checks passed.")
else:
    print("[FAILURE] Some validation checks failed!")
    failed = [k for k, v in validation_checks.items() if not v]
    for f in failed:
        print(f"  - {f}")

print()
print("=" * 60)
print("EXECUTION COMPLETE")
print("=" * 60)
print(f"Sample mean: {sample_mean:.6f}")
print(f"95% CI: [{ci_lower:.6f}, {ci_upper:.6f}]")
print(f"Output file: {OUTPUT_FILE}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:17:54
# Command: python3 /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/scripts/adhoc/01_monte-carlo-sim.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# [CONFIG] Sample size: 1000
# [CONFIG] Population: N(50, 10)
# [CONFIG] Bootstrap iterations: 1000
# [CONFIG] CI: 2.5th to 97.5th percentiles
# 
# ============================================================
# STAGE 1: GENERATE SAMPLE FROM KNOWN DISTRIBUTION
# ============================================================
# Generated sample of size: 1000
# Sample min: 17.5873
# Sample max: 88.5273
# Sample mean: 50.1933
# Sample std: 9.7922
# 
# ============================================================
# CHECKPOINT 1: PRE-STATE CAPTURE
# ============================================================
# Pre-state captured:
#   - Sample size: 1000
#   - Mean: 50.193321
#   - Std: 9.792159
#   - First 3 values: [54.96714153011233, 48.61735698828815, 56.47688538100692]
# 
# ============================================================
# STAGE 2: BOOTSTRAP 95% CONFIDENCE INTERVAL
# ============================================================
# Bootstrap iterations completed: 1000
# Bootstrap mean estimates: min=49.296590, max=51.140472
# 
# Bootstrap 95% CI for the mean:
#   Lower bound (2.5%): 49.607054
#   Upper bound (97.5%): 50.850234
#   CI width: 1.243180
# 
# ============================================================
# CHECKPOINT 2: BOOTSTRAP CI VALIDATION
# ============================================================
# Sample mean: 50.193321
# CI range: [49.607054, 50.850234]
# Mean is inside CI: True (EXPECTED: True)
#   [PASS] Sample mean is properly contained in the CI.
# 
# CI bounds are properly ordered (lower < upper): True
# CI width (1.243180) is reasonable: True
#   [PASS] CI width is reasonable.
# 
# ============================================================
# STAGE 3: PREPARE OUTPUT DATA
# ============================================================
# Output table shape: (1003, 3)
# Columns: ['sample_index', 'sample_value', 'statistic_type']
# 
# ============================================================
# CHECKPOINT 3: PRE-SAVE STATE
# ============================================================
# Output DataFrame shape: 1003 rows x 3 columns
# Column names: ['sample_index', 'sample_value', 'statistic_type']
# Data types:
# Schema({'sample_index': Int64, 'sample_value': Float64, 'statistic_type': String})
# 
# ============================================================
# STAGE 4: SAVE OUTPUT
# ============================================================
# Saved output to: /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/data/processed/monte_carlo_results.parquet
# File exists: True
# File size: 11,674 bytes
# 
# ============================================================
# CHECKPOINT 4: POST-SAVE VALIDATION
# ============================================================
# Verified read from disk:
#   Shape: (1003, 3)
#   Columns: ['sample_index', 'sample_value', 'statistic_type']
#   First 3 rows:
# shape: (3, 3)
# ┌──────────────┬──────────────┬────────────────┐
# │ sample_index ┆ sample_value ┆ statistic_type │
# │ ---          ┆ ---          ┆ ---            │
# │ i64          ┆ f64          ┆ str            │
# ╞══════════════╪══════════════╪════════════════╡
# │ 0            ┆ 54.967142    ┆ sample_value   │
# │ 1            ┆ 48.617357    ┆ sample_value   │
# │ 2            ┆ 56.476885    ┆ sample_value   │
# └──────────────┴──────────────┴────────────────┘
# 
# Summary statistics rows:
#   sample_mean: 50.193321
#   ci_lower: 49.607054
#   ci_upper: 50.850234
# 
# ============================================================
# FINAL VALIDATION SUMMARY
# ============================================================
#   [PASS] Sample size is 1000
#   [PASS] Sample mean computed
#   [PASS] Bootstrap CI computed
#   [PASS] Mean is in CI
#   [PASS] CI bounds are valid
#   [PASS] Output file exists
#   [PASS] Output file is readable
#   [PASS] Output shape matches input
# 
# [SUCCESS] All validation checks passed.
# 
# ============================================================
# EXECUTION COMPLETE
# ============================================================
# Sample mean: 50.193321
# 95% CI: [49.607054, 50.850234]
# Output file: /daaf/research/2026-06-08_AdHoc_MonteCarloSimulation/data/processed/monte_carlo_results.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
