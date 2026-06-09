import numpy as np
import polars as pl
from scipy import stats

# --- Config ---
N_SAMPLES = 1000
TRUE_MEAN = 50
TRUE_STD = 10
N_BOOTSTRAP = 10000
N_BOOTSTRAP_SAMPLES = N_SAMPLES
CONFIDENCE_LEVEL = 0.95
OUTPUT_PARQUET = "/daaf/benchmarks/_sandbox/run_dc-01_Gemini_3.1_Pro_0/research/2026-06-09_AdHoc_MonteCarlo/data/processed/monte_carlo_results.parquet"
RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)

# --- Simulate Data ---
# INTENT: Draw 1000 samples from a Normal distribution
# REASONING: Simulating a baseline dataset for the Monte Carlo analysis to construct confidence intervals around the sample mean
# ASSUMES: Distribution is strictly normal with mean=50 and std=10
samples = np.random.normal(loc=TRUE_MEAN, scale=TRUE_STD, size=N_SAMPLES)
sample_mean = np.mean(samples)
sample_std = np.std(samples, ddof=1)

print("--- Simulated Data Stats ---")
print(f"Sample Mean: {sample_mean:.4f}")
print(f"Sample Std: {sample_std:.4f}")
print(f"Sample Size: {len(samples)}")
assert len(samples) == N_SAMPLES, f"Expected {N_SAMPLES} samples, got {len(samples)}"

# --- Bootstrap ---
# INTENT: Bootstrap to find the 95% confidence interval for the sample mean
# REASONING: The non-parametric bootstrap empirically constructs the sampling distribution of the mean, useful for checking robustness
# ASSUMES: Data points are independent and identically distributed, representative of underlying population

# Generate bootstrap samples
bootstrap_means = np.empty(N_BOOTSTRAP)
for i in range(N_BOOTSTRAP):
    boot_sample = np.random.choice(samples, size=N_BOOTSTRAP_SAMPLES, replace=True)
    bootstrap_means[i] = np.mean(boot_sample)

alpha = 1 - CONFIDENCE_LEVEL
lower_bound = np.percentile(bootstrap_means, alpha / 2 * 100)
upper_bound = np.percentile(bootstrap_means, (1 - alpha / 2) * 100)

print("\n--- Bootstrap Results ---")
print(f"Bootstrap Mean of Means: {np.mean(bootstrap_means):.4f}")
print(f"95% Confidence Interval: [{lower_bound:.4f}, {upper_bound:.4f}]")

# Statistical validation check
margin_of_error = upper_bound - sample_mean
expected_se = sample_std / np.sqrt(N_SAMPLES)
expected_me = stats.norm.ppf(1 - alpha / 2) * expected_se

print("\n--- Validation Check ---")
print(f"Empirical Margin of Error (Upper): {margin_of_error:.4f}")
print(f"Theoretical Asymptotic ME: {expected_me:.4f}")
assert abs(margin_of_error - expected_me) < (0.1 * expected_me), "Bootstrap ME diverges significantly from theoretical ME (check normality or bootstrap count)"
print("Validation Passed: Bootstrap CI is conceptually consistent with parametric expectations.")

# --- Save Results ---
# INTENT: Package the parameters and results into a tracked dataframe
# REASONING: Polars provides a clean framework to track experimental parameters alongside execution results for reproducible runs
# ASSUMES: A single-row tabular structure is sufficient for this single run
results_df = pl.DataFrame({
    "true_mean": [TRUE_MEAN],
    "true_std": [TRUE_STD],
    "n_samples": [N_SAMPLES],
    "n_bootstrap": [N_BOOTSTRAP],
    "sample_mean": [sample_mean],
    "sample_std": [sample_std],
    "bootstrap_mean": [np.mean(bootstrap_means)],
    "ci_lower_95": [lower_bound],
    "ci_upper_95": [upper_bound],
    "random_seed": [RANDOM_SEED]
})

print("\n--- Pre-Save State ---")
print(f"Shape: {results_df.shape}")
print(f"Columns: {results_df.columns}")

results_df.write_parquet(OUTPUT_PARQUET)

print(f"\nSaved successfully to {OUTPUT_PARQUET}")

# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-09 00:38:27
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-01_Gemini_3.1_Pro_0/research/2026-06-09_AdHoc_MonteCarlo/scripts/adhoc/monte_carlo_bootstrap.py
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# --- Simulated Data Stats ---
# Sample Mean: 50.1933
# Sample Std: 9.7922
# Sample Size: 1000
# 
# --- Bootstrap Results ---
# Bootstrap Mean of Means: 50.1968
# 95% Confidence Interval: [49.5942, 50.8122]
# 
# --- Validation Check ---
# Empirical Margin of Error (Upper): 0.6188
# Theoretical Asymptotic ME: 0.6069
# Validation Passed: Bootstrap CI is conceptually consistent with parametric expectations.
# 
# --- Pre-Save State ---
# Shape: (1, 10)
# Columns: ['true_mean', 'true_std', 'n_samples', 'n_bootstrap', 'sample_mean', 'sample_std', 'bootstrap_mean', 'ci_lower_95', 'ci_upper_95', 'random_seed']
# 
# Saved successfully to /daaf/benchmarks/_sandbox/run_dc-01_Gemini_3.1_Pro_0/research/2026-06-09_AdHoc_MonteCarlo/data/processed/monte_carlo_results.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
