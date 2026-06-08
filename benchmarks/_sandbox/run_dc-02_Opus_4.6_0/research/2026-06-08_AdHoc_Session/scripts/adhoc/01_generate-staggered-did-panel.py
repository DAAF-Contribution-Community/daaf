#!/usr/bin/env python3
"""
Ad Hoc: Generate synthetic staggered difference-in-differences panel dataset.

Task: generate-staggered-did-panel
Mode: Ad Hoc Collaboration
Depends on: None (synthetic data generation)
Input: None (generated from random seed)
Output: data/raw/2026-06-08_synthetic-staggered-did-panel.parquet
Checkpoint: CP1 (shape, types, value distributions, treatment design)
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
# Configuration for synthetic panel generation. The panel structure is
# 50 states x 10 years = 500 rows, designed for staggered DiD analysis.
# Random seed ensures deterministic output for reproducibility.
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-02_Opus_4.6_0/research/2026-06-08_AdHoc_Session")
DATA_RAW = PROJECT_DIR / "data" / "raw"
OUTPUT_PATH = DATA_RAW / "2026-06-08_synthetic-staggered-did-panel.parquet"

N_STATES = 50
YEARS = list(range(2013, 2023))  # 2013-2022 inclusive = 10 years
N_YEARS = len(YEARS)
EXPECTED_ROWS = N_STATES * N_YEARS  # 500
SEED = 20260608  # Date-based seed for reproducibility

# --- Generate Panel Structure ---
# INTENT: Create the skeleton of a balanced panel with every combination
# of state_id (1-50) and year (2013-2022).
# REASONING: Using numpy meshgrid to produce the full Cartesian product
# ensures a balanced panel (every state observed in every year), which is
# the standard structure for two-way fixed effects DiD estimation.
# ASSUMES: No states enter or exit the panel (balanced, not unbalanced).
print("=" * 60)
print("Generate Synthetic Staggered DiD Panel")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(SEED)

state_ids = np.arange(1, N_STATES + 1)
state_grid, year_grid = np.meshgrid(state_ids, YEARS, indexing="ij")
state_col = state_grid.flatten()
year_col = year_grid.flatten()

print(f"Panel skeleton: {N_STATES} states x {N_YEARS} years = {len(state_col)} rows")

# --- Generate Enrollment ---
# INTENT: Create realistic enrollment counts that vary by state and year.
# REASONING: Each state gets a baseline enrollment drawn from a realistic range
# (5,000-50,000) plus small year-over-year random variation (+/- up to 5%).
# This produces heterogeneous but plausible enrollment trajectories.
# ASSUMES: Enrollment is always positive; the noise magnitude is small enough
# relative to baseline that negative values are effectively impossible.
state_baselines = rng.integers(5000, 50001, size=N_STATES)  # Baseline per state

enrollment = np.zeros(EXPECTED_ROWS, dtype=np.int64)
for i, sid in enumerate(state_ids):
    mask = state_col == sid
    base = state_baselines[i]
    # INTENT: Add year-over-year random variation around the state's baseline.
    # REASONING: Multiplicative noise (0.95 to 1.05) preserves the scale and
    # ensures enrollment stays proportional to the baseline, unlike additive noise.
    yearly_noise = rng.uniform(0.95, 1.05, size=N_YEARS)
    enrollment[mask] = (base * yearly_noise).astype(np.int64)

# --- Generate Staggered Treatment ---
# INTENT: Assign each state a treatment adoption year (or never-treated status)
# and construct the binary treated indicator that turns on at adoption and
# stays on for all subsequent years (absorbing treatment).
#
# REASONING: For staggered DiD, treatment timing must vary across units.
# We draw adoption years uniformly from the panel period (2014-2021) for
# treated states. We exclude the first year (2013) so every treated state
# has at least one pre-treatment observation, and exclude the last year
# (2022) so every treated state has at least one post-treatment observation.
# Approximately 20% of states are designated never-treated (adoption_year=None)
# to serve as a pure control group -- this is methodologically important for
# identification in modern staggered DiD estimators (e.g., Callaway & Sant'Anna).
#
# ASSUMES: Treatment is binary and absorbing (once adopted, never reversed).
# This is the standard assumption for staggered DiD designs.

n_never_treated = 10  # 20% of 50 states are never treated
n_treated = N_STATES - n_never_treated

# INTENT: Randomly select which states are never-treated vs treated.
# REASONING: Random assignment avoids systematic correlation between state
# characteristics and treatment status in the synthetic data.
never_treated_states = set(rng.choice(state_ids, size=n_never_treated, replace=False).tolist())

# INTENT: Assign adoption years to treated states from the interior of the panel.
# REASONING: Drawing from 2014-2021 (not 2013 or 2022) ensures at least 1 pre-
# and 1 post-treatment period for every treated state, which is required for
# DiD estimation.
treated_states = [s for s in state_ids if s not in never_treated_states]
adoption_years = rng.choice(range(2014, 2022), size=n_treated, replace=True)  # 2014-2021 inclusive
state_adoption = dict(zip(treated_states, adoption_years.tolist()))

# Build the treated column: 1 if year >= adoption year for that state, else 0
treated_col = np.zeros(EXPECTED_ROWS, dtype=np.int8)
for i in range(EXPECTED_ROWS):
    sid = state_col[i]
    yr = year_col[i]
    if sid in state_adoption and yr >= state_adoption[sid]:
        treated_col[i] = 1

# --- Assemble DataFrame ---
# INTENT: Combine all generated columns into a single Polars DataFrame.
# REASONING: Using Polars (not pandas) per DAAF conventions. Column types
# are explicitly cast to ensure schema clarity in the output parquet.
df = pl.DataFrame({
    "state_id": state_col.astype(np.int32),
    "year": year_col.astype(np.int32),
    "enrollment": enrollment.astype(np.int32),
    "treated": treated_col.astype(np.int8),
})

# --- Pre-state ---
# Capture dataset properties for validation reporting.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"Columns: {pre_cols}")
print(f"Dtypes: {df.dtypes}")

# --- Validate ---
# Checkpoint validation: verify generated data matches design specification.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Shape matches expected panel dimensions
shape_ok = df.shape == (EXPECTED_ROWS, 4)
print(f"  [{'PASS' if shape_ok else 'FAIL'}] Shape: {df.shape} (expected ({EXPECTED_ROWS}, 4))")

# CP1.2: All years present
years_found = sorted(df["year"].unique().to_list())
all_years = years_found == YEARS
print(f"  [{'PASS' if all_years else 'FAIL'}] Years present: {years_found}")

# CP1.3: All states present
states_found = sorted(df["state_id"].unique().to_list())
all_states = states_found == list(range(1, N_STATES + 1))
print(f"  [{'PASS' if all_states else 'FAIL'}] States present: {len(states_found)} unique (expected {N_STATES})")

# CP1.4: No missing values (synthetic data should have none)
null_counts = df.null_count()
total_nulls = sum(null_counts.row(0))
no_nulls = total_nulls == 0
print(f"  [{'PASS' if no_nulls else 'FAIL'}] No nulls: total null count = {total_nulls}")

# CP1.5: Enrollment values in realistic range
enrollment_min = df["enrollment"].min()
enrollment_max = df["enrollment"].max()
enrollment_range_ok = enrollment_min > 0 and enrollment_max < 100000
print(f"  [{'PASS' if enrollment_range_ok else 'FAIL'}] Enrollment range: {enrollment_min:,} - {enrollment_max:,}")

# CP1.6: Treated column is binary (0 or 1 only)
treated_values = sorted(df["treated"].unique().to_list())
treated_binary = treated_values == [0, 1]
print(f"  [{'PASS' if treated_binary else 'FAIL'}] Treated is binary: unique values = {treated_values}")

# CP1.7: Staggered treatment design verification
# Count never-treated states (treated == 0 for all years)
state_treatment_summary = (
    df.group_by("state_id")
    .agg(pl.col("treated").max().alias("ever_treated"))
)
n_never = state_treatment_summary.filter(pl.col("ever_treated") == 0).shape[0]
n_ever = state_treatment_summary.filter(pl.col("ever_treated") == 1).shape[0]

has_never_treated = n_never > 0
has_treated = n_ever > 0
print(f"  [{'PASS' if has_never_treated else 'FAIL'}] Never-treated states: {n_never}")
print(f"  [{'PASS' if has_treated else 'FAIL'}] Ever-treated states: {n_ever}")

# CP1.8: Treatment adoption is staggered (multiple distinct adoption years)
# For treated states, find the first year where treated == 1
first_treated_year = (
    df.filter(pl.col("treated") == 1)
    .group_by("state_id")
    .agg(pl.col("year").min().alias("adoption_year"))
)
n_distinct_adoption = first_treated_year["adoption_year"].n_unique()
is_staggered = n_distinct_adoption > 1
print(f"  [{'PASS' if is_staggered else 'FAIL'}] Staggered: {n_distinct_adoption} distinct adoption years")

# CP1.9: Treatment is absorbing (once on, stays on)
# For each treated state, verify no year after adoption has treated == 0
absorbing_ok = True
for row in first_treated_year.iter_rows(named=True):
    sid = row["state_id"]
    adopt_yr = row["adoption_year"]
    post_adopt = df.filter(
        (pl.col("state_id") == sid) & (pl.col("year") >= adopt_yr)
    )
    if post_adopt["treated"].min() != 1:
        absorbing_ok = False
        break
print(f"  [{'PASS' if absorbing_ok else 'FAIL'}] Absorbing treatment: once on, stays on")

# CP1.10: Panel is balanced (each state has exactly N_YEARS observations)
obs_per_state = df.group_by("state_id").len()
balanced = (obs_per_state["len"].min() == N_YEARS) and (obs_per_state["len"].max() == N_YEARS)
print(f"  [{'PASS' if balanced else 'FAIL'}] Balanced panel: every state has {N_YEARS} observations")

# --- Treatment Design Summary ---
# INTENT: Print a summary of the staggered treatment design for user review.
print("\n" + "=" * 60)
print("TREATMENT DESIGN SUMMARY")
print("=" * 60)

adoption_dist = first_treated_year["adoption_year"].value_counts().sort("adoption_year")
print(f"\nTreatment adoption year distribution:")
for row in adoption_dist.iter_rows(named=True):
    print(f"  {row['adoption_year']}: {row['count']} states")
print(f"  Never treated: {n_never} states")
print(f"  Total: {n_ever + n_never} states")

# --- Descriptive Statistics ---
print(f"\nEnrollment statistics:")
print(f"  Mean:   {df['enrollment'].mean():,.0f}")
print(f"  Median: {df['enrollment'].median():,.0f}")
print(f"  Std:    {df['enrollment'].std():,.0f}")
print(f"  Min:    {df['enrollment'].min():,}")
print(f"  Max:    {df['enrollment'].max():,}")

print(f"\nTreatment prevalence:")
print(f"  Treated observations: {df.filter(pl.col('treated') == 1).shape[0]} / {EXPECTED_ROWS} ({df['treated'].mean():.1%})")
print(f"  Control observations: {df.filter(pl.col('treated') == 0).shape[0]} / {EXPECTED_ROWS}")

# Print sample rows for inspection
print(f"\nSample rows (first 3 state_ids, all years):")
sample = df.filter(pl.col("state_id").is_in([1, 2, 3])).sort("state_id", "year")
print(sample)

# --- Assertions ---
assert shape_ok, "STOP: Shape mismatch"
assert all_years, "STOP: Missing years"
assert all_states, "STOP: Missing states"
assert no_nulls, "STOP: Unexpected nulls in synthetic data"
assert enrollment_range_ok, "STOP: Enrollment out of range"
assert treated_binary, "STOP: Treated column not binary"
assert has_never_treated, "STOP: No never-treated states"
assert has_treated, "STOP: No treated states"
assert is_staggered, "STOP: Treatment not staggered"
assert absorbing_ok, "STOP: Treatment not absorbing"
assert balanced, "STOP: Panel not balanced"

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists on disk
assert OUTPUT_PATH.exists(), f"STOP: Output file not found at {OUTPUT_PATH}"
file_size = OUTPUT_PATH.stat().st_size
print(f"File size: {file_size:,} bytes")

# Re-read and verify round-trip
df_verify = pl.read_parquet(OUTPUT_PATH)
assert df_verify.shape == df.shape, "STOP: Round-trip shape mismatch"
print(f"Round-trip verification: {df_verify.shape} matches")

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:19:33
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-02_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_generate-staggered-did-panel.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Generate Synthetic Staggered DiD Panel
# ============================================================
# Panel skeleton: 50 states x 10 years = 500 rows
# 
# Pre-state: 500 rows, 4 cols
# Columns: ['state_id', 'year', 'enrollment', 'treated']
# Dtypes: [Int32, Int32, Int32, Int8]
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Shape: (500, 4) (expected (500, 4))
#   [PASS] Years present: [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
#   [PASS] States present: 50 unique (expected 50)
#   [PASS] No nulls: total null count = 0
#   [PASS] Enrollment range: 4,998 - 48,395
#   [PASS] Treated is binary: unique values = [0, 1]
#   [PASS] Never-treated states: 10
#   [PASS] Ever-treated states: 40
#   [PASS] Staggered: 8 distinct adoption years
#   [PASS] Absorbing treatment: once on, stays on
#   [PASS] Balanced panel: every state has 10 observations
# 
# ============================================================
# TREATMENT DESIGN SUMMARY
# ============================================================
# 
# Treatment adoption year distribution:
#   2014: 5 states
#   2015: 4 states
#   2016: 5 states
#   2017: 3 states
#   2018: 4 states
#   2019: 6 states
#   2020: 9 states
#   2021: 4 states
#   Never treated: 10 states
#   Total: 50 states
# 
# Enrollment statistics:
#   Mean:   27,688
#   Median: 28,685
#   Std:    11,902
#   Min:    4,998
#   Max:    48,395
# 
# Treatment prevalence:
#   Treated observations: 209 / 500 (41.8%)
#   Control observations: 291 / 500
# 
# Sample rows (first 3 state_ids, all years):
# shape: (30, 4)
# ┌──────────┬──────┬────────────┬─────────┐
# │ state_id ┆ year ┆ enrollment ┆ treated │
# │ ---      ┆ ---  ┆ ---        ┆ ---     │
# │ i32      ┆ i32  ┆ i32        ┆ i8      │
# ╞══════════╪══════╪════════════╪═════════╡
# │ 1        ┆ 2013 ┆ 38043      ┆ 0       │
# │ 1        ┆ 2014 ┆ 35211      ┆ 0       │
# │ 1        ┆ 2015 ┆ 37916      ┆ 0       │
# │ 1        ┆ 2016 ┆ 35562      ┆ 0       │
# │ 1        ┆ 2017 ┆ 36128      ┆ 0       │
# │ …        ┆ …    ┆ …          ┆ …       │
# │ 3        ┆ 2018 ┆ 31327      ┆ 0       │
# │ 3        ┆ 2019 ┆ 31659      ┆ 0       │
# │ 3        ┆ 2020 ┆ 32590      ┆ 0       │
# │ 3        ┆ 2021 ┆ 31859      ┆ 1       │
# │ 3        ┆ 2022 ┆ 31282      ┆ 1       │
# └──────────┴──────┴────────────┴─────────┘
# 
# Saved: /daaf/benchmarks/_sandbox/run_dc-02_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/raw/2026-06-08_synthetic-staggered-did-panel.parquet
# File size: 3,561 bytes
# Round-trip verification: (500, 4) matches
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
