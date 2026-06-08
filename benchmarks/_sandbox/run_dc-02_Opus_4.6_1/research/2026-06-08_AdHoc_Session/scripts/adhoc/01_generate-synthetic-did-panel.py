#!/usr/bin/env python3
"""
Ad Hoc: Generate synthetic staggered difference-in-differences panel dataset.

Task: generate-synthetic-did-panel
Input: None (synthetic data generation)
Output: data/raw/2026-06-08_synthetic-staggered-did-panel.parquet
Checkpoint: CP1 (shape, types, structure verification)

Purpose: Create a pedagogical dataset for practicing staggered DiD estimation.
The dataset embeds a known treatment effect (+500 enrollment) so downstream
estimation can recover the ground truth ATT.
"""

import numpy as np
import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for synthetic panel generation. The panel structure (50 states x
# 10 years) is designed to be large enough for meaningful estimation but small
# enough for quick iteration. The treatment effect of +500 is chosen to be
# detectable against typical enrollment noise.
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-02_Opus_4.6_1/research/2026-06-08_AdHoc_Session")
DATA_RAW = PROJECT_DIR / "data" / "raw"
OUTPUT_PATH = DATA_RAW / "2026-06-08_synthetic-staggered-did-panel.parquet"

SEED = 42
N_STATES = 50
YEARS = list(range(2013, 2023))  # 2013-2022 inclusive = 10 years
N_YEARS = len(YEARS)

# INTENT: Define the true treatment effect that will be embedded in the data.
# REASONING: +500 enrollment is large enough to be recoverable by DiD estimators
# given the noise level (~N(0, 200) per observation), but small relative to the
# base enrollment range (~5,000-15,000), making it realistic.
TRUE_TREATMENT_EFFECT = 500

# INTENT: Define staggered treatment adoption years for each state.
# REASONING: We assign treatment years to create realistic staggered adoption:
#   - 10 states are never-treated (treatment_year = 0) for a clean control group
#   - Remaining 40 states adopt in waves spread across the panel period
#   - Adoption years range from 2015 to 2021 to leave pre-treatment and
#     post-treatment observations for each cohort
# ASSUMES: treatment_year = 0 denotes never-treated states. This is a common
# convention in DiD applications and will be stored as integer 0 in the parquet.
TREATMENT_YEARS_DISTRIBUTION = {
    2015: 6,   # 6 early adopters
    2016: 5,
    2017: 7,   # largest adoption wave
    2018: 6,
    2019: 6,
    2020: 5,
    2021: 5,   # 5 late adopters
    0: 10,     # 10 never-treated states
}

# --- Generate ---
print("=" * 60)
print("Generate Synthetic Staggered DiD Panel")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(SEED)

# INTENT: Assign each state a treatment adoption year based on the distribution above.
# REASONING: Building a flat list from the distribution dict ensures exact counts
# per cohort, giving us a balanced and interpretable staggered design.
# ASSUMES: Sum of all values in TREATMENT_YEARS_DISTRIBUTION equals N_STATES (50).
treatment_year_list = []
for ty, count in TREATMENT_YEARS_DISTRIBUTION.items():
    treatment_year_list.extend([ty] * count)

assert len(treatment_year_list) == N_STATES, (
    f"Treatment year assignments ({len(treatment_year_list)}) must equal N_STATES ({N_STATES})"
)

# Shuffle so state_id assignment is random (not ordered by treatment timing)
rng.shuffle(treatment_year_list)

# INTENT: Assign a stable base enrollment for each state that persists across years.
# REASONING: Real states have persistent enrollment levels driven by population size.
# Drawing from Uniform(5000, 15000) gives meaningful cross-sectional variation.
# A separate state-level fixed effect is not needed because the base enrollment
# already serves this purpose in the data generating process.
state_base_enrollment = rng.integers(5000, 15001, size=N_STATES)

# INTENT: Build the panel by iterating over states and years, constructing each
# observation with the appropriate treatment status and enrollment value.
# REASONING: Constructing row-by-row in lists and then creating a single DataFrame
# is more readable than complex broadcasting for a 500-row dataset. Performance
# is not a concern at this scale.
rows = {
    "state_id": [],
    "year": [],
    "enrollment": [],
    "treated": [],
    "treatment_year": [],
}

for state_idx in range(N_STATES):
    state_id = state_idx + 1  # 1-indexed
    ty = treatment_year_list[state_idx]
    base = state_base_enrollment[state_idx]

    for year in YEARS:
        # INTENT: Determine treatment status for this state-year observation.
        # REASONING: For never-treated states (ty == 0), treated is always 0.
        # For treated states, treated turns on at the adoption year and stays on,
        # which is the standard absorbing-treatment assumption in staggered DiD.
        if ty == 0:
            is_treated = 0
        else:
            is_treated = 1 if year >= ty else 0

        # INTENT: Generate enrollment with state fixed effect, year trend, noise,
        # and the treatment effect (if treated).
        # REASONING: The DGP includes:
        #   1. State base enrollment (cross-sectional variation, acts as state FE)
        #   2. A small positive time trend (+50 * (year - 2013)) simulating
        #      secular enrollment growth, so pre-trends are parallel absent treatment
        #   3. Random noise ~ N(0, 200) for idiosyncratic year-to-year variation
        #   4. Treatment effect of +500 added only when treated == 1
        # This ensures parallel trends hold in expectation for the untreated
        # potential outcome, making the true ATT recoverable by a correct estimator.
        # ASSUMES: No anticipation effects, no heterogeneous treatment effects
        # across cohorts (homogeneous ATT), and no dynamic treatment effects
        # (effect is constant post-adoption).
        time_trend = 50 * (year - 2013)
        noise = rng.normal(0, 200)
        enrollment = int(base + time_trend + noise + is_treated * TRUE_TREATMENT_EFFECT)

        rows["state_id"].append(state_id)
        rows["year"].append(year)
        rows["enrollment"].append(enrollment)
        rows["treated"].append(is_treated)
        rows["treatment_year"].append(ty)

# INTENT: Create a Polars DataFrame from the constructed dict of lists.
# REASONING: Using explicit schema to enforce correct types rather than relying
# on inference. state_id, year, enrollment, treated, and treatment_year are all
# integers by design.
df = pl.DataFrame(
    rows,
    schema={
        "state_id": pl.Int64,
        "year": pl.Int64,
        "enrollment": pl.Int64,
        "treated": pl.Int64,
        "treatment_year": pl.Int64,
    },
)

print(f"\nGenerated panel: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")
print(f"Types: {df.dtypes}")

# --- Validate ---
# Pre/post state is not applicable for data generation (no input data).
# Instead, validate the generated dataset structure and properties.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: Shape matches specification (50 states x 10 years = 500 rows)
expected_rows = N_STATES * N_YEARS
shape_ok = df.shape == (expected_rows, 5)
print(f"  [{'PASS' if shape_ok else 'FAIL'}] Shape: {df.shape} (expected ({expected_rows}, 5))")

# CP1.2: All years present
years_found = sorted(df["year"].unique().to_list())
years_ok = years_found == YEARS
print(f"  [{'PASS' if years_ok else 'FAIL'}] Years present: {years_found}")

# CP1.3: All states present with correct IDs (1-50)
states_found = sorted(df["state_id"].unique().to_list())
states_ok = states_found == list(range(1, N_STATES + 1))
print(f"  [{'PASS' if states_ok else 'FAIL'}] State IDs: 1-{max(states_found)} ({len(states_found)} unique)")

# CP1.4: No nulls in any column
null_counts = {col: df[col].null_count() for col in df.columns}
no_nulls = all(v == 0 for v in null_counts.values())
print(f"  [{'PASS' if no_nulls else 'FAIL'}] Null counts: {null_counts}")

# CP1.5: Panel is balanced (each state has exactly N_YEARS observations)
state_year_counts = df.group_by("state_id").len()
min_obs = state_year_counts["len"].min()
max_obs = state_year_counts["len"].max()
balanced_ok = min_obs == N_YEARS and max_obs == N_YEARS
print(f"  [{'PASS' if balanced_ok else 'FAIL'}] Balanced panel: {min_obs}-{max_obs} obs per state (expected {N_YEARS})")

# CP1.6: state_id x year uniquely identifies rows
unique_pairs = df.select("state_id", "year").n_unique()
unique_ok = unique_pairs == expected_rows
print(f"  [{'PASS' if unique_ok else 'FAIL'}] Unique (state_id, year) pairs: {unique_pairs} (expected {expected_rows})")

# CP1.7: Staggered treatment structure is correct
treatment_year_dist = (
    df.filter(pl.col("year") == YEARS[0])  # One row per state (first year)
    .group_by("treatment_year")
    .len()
    .sort("treatment_year")
)
print(f"\n  Treatment timing distribution (from first panel year):")
for row in treatment_year_dist.iter_rows(named=True):
    label = "never-treated" if row["treatment_year"] == 0 else f"adopts {row['treatment_year']}"
    print(f"    treatment_year={row['treatment_year']} ({label}): {row['len']} states")

# CP1.8: Treated indicator is consistent with treatment_year
# For treated states: treated should be 0 before treatment_year, 1 at and after
# For never-treated (treatment_year == 0): treated should always be 0
treated_states = df.filter(pl.col("treatment_year") > 0)
consistency_check = treated_states.with_columns(
    (pl.col("year") >= pl.col("treatment_year")).cast(pl.Int64).alias("expected_treated")
)
treated_consistent = (consistency_check["treated"] == consistency_check["expected_treated"]).all()

never_treated = df.filter(pl.col("treatment_year") == 0)
never_treated_consistent = (never_treated["treated"] == 0).all()

consistency_ok = treated_consistent and never_treated_consistent
print(f"  [{'PASS' if consistency_ok else 'FAIL'}] Treatment indicator consistent with treatment_year")

# CP1.9: Enrollment is in a reasonable range
enroll_min = df["enrollment"].min()
enroll_max = df["enrollment"].max()
enroll_range_ok = enroll_min > 0 and enroll_max < 25000
print(f"  [{'PASS' if enroll_range_ok else 'WARN'}] Enrollment range: {enroll_min:,} - {enroll_max:,}")

# CP1.10: Treatment_year is constant within each state
ty_per_state = df.group_by("state_id").agg(pl.col("treatment_year").n_unique().alias("n_ty"))
ty_constant = (ty_per_state["n_ty"] == 1).all()
print(f"  [{'PASS' if ty_constant else 'FAIL'}] Treatment year constant within state: {ty_constant}")

# Assertions for critical checks
assert shape_ok, f"STOP: Shape mismatch: {df.shape} != ({expected_rows}, 5)"
assert years_ok, f"STOP: Missing years: {years_found}"
assert states_ok, f"STOP: Missing states"
assert no_nulls, f"STOP: Nulls found: {null_counts}"
assert balanced_ok, f"STOP: Unbalanced panel"
assert unique_ok, f"STOP: Duplicate (state_id, year) pairs"
assert consistency_ok, f"STOP: Treatment indicator inconsistent with treatment_year"
assert ty_constant, f"STOP: Treatment year varies within state"

# --- Summary Statistics ---
# Display key summary statistics so the user can verify the data looks reasonable.
print("\n" + "=" * 60)
print("SUMMARY STATISTICS")
print("=" * 60)

print(f"\n  True treatment effect embedded: +{TRUE_TREATMENT_EFFECT}")
print(f"  Random seed: {SEED}")

n_treated_states = df.filter(pl.col("treatment_year") > 0).select("state_id").n_unique()
n_never_treated = df.filter(pl.col("treatment_year") == 0).select("state_id").n_unique()
print(f"  Treated states: {n_treated_states}")
print(f"  Never-treated states: {n_never_treated}")

n_treated_obs = df.filter(pl.col("treated") == 1).shape[0]
n_untreated_obs = df.filter(pl.col("treated") == 0).shape[0]
print(f"  Treated observations: {n_treated_obs}")
print(f"  Untreated observations: {n_untreated_obs}")

mean_enroll_treated = df.filter(pl.col("treated") == 1)["enrollment"].mean()
mean_enroll_untreated = df.filter(pl.col("treated") == 0)["enrollment"].mean()
print(f"  Mean enrollment (treated obs): {mean_enroll_treated:,.0f}")
print(f"  Mean enrollment (untreated obs): {mean_enroll_untreated:,.0f}")
print(f"  Raw difference (treated - untreated): {mean_enroll_treated - mean_enroll_untreated:,.0f}")
print(f"    (Note: raw difference != ATT due to composition effects; DiD estimator needed)")

print(f"\n  Sample rows:")
print(df.head(10))

# --- Save ---
# Persist generated panel as parquet.
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists and is readable
saved_df = pl.read_parquet(OUTPUT_PATH)
save_ok = saved_df.shape == df.shape
print(f"  [{'PASS' if save_ok else 'FAIL'}] Saved file readable with correct shape: {saved_df.shape}")

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 12:19:38
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-02_Opus_4.6_1/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_generate-synthetic-did-panel.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Generate Synthetic Staggered DiD Panel
# ============================================================
# 
# Generated panel: 500 rows x 5 cols
# Columns: ['state_id', 'year', 'enrollment', 'treated', 'treatment_year']
# Types: [Int64, Int64, Int64, Int64, Int64]
# 
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] Shape: (500, 5) (expected (500, 5))
#   [PASS] Years present: [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
#   [PASS] State IDs: 1-50 (50 unique)
#   [PASS] Null counts: {'state_id': 0, 'year': 0, 'enrollment': 0, 'treated': 0, 'treatment_year': 0}
#   [PASS] Balanced panel: 10-10 obs per state (expected 10)
#   [PASS] Unique (state_id, year) pairs: 500 (expected 500)
# 
#   Treatment timing distribution (from first panel year):
#     treatment_year=0 (never-treated): 10 states
#     treatment_year=2015 (adopts 2015): 6 states
#     treatment_year=2016 (adopts 2016): 5 states
#     treatment_year=2017 (adopts 2017): 7 states
#     treatment_year=2018 (adopts 2018): 6 states
#     treatment_year=2019 (adopts 2019): 6 states
#     treatment_year=2020 (adopts 2020): 5 states
#     treatment_year=2021 (adopts 2021): 5 states
#   [PASS] Treatment indicator consistent with treatment_year
#   [PASS] Enrollment range: 4,902 - 15,557
#   [PASS] Treatment year constant within state: True
# 
# ============================================================
# SUMMARY STATISTICS
# ============================================================
# 
#   True treatment effect embedded: +500
#   Random seed: 42
#   Treated states: 40
#   Never-treated states: 10
#   Treated observations: 204
#   Untreated observations: 296
#   Mean enrollment (treated obs): 10,779
#   Mean enrollment (untreated obs): 10,170
#   Raw difference (treated - untreated): 609
#     (Note: raw difference != ATT due to composition effects; DiD estimator needed)
# 
#   Sample rows:
# shape: (10, 5)
# ┌──────────┬──────┬────────────┬─────────┬────────────────┐
# │ state_id ┆ year ┆ enrollment ┆ treated ┆ treatment_year │
# │ ---      ┆ ---  ┆ ---        ┆ ---     ┆ ---            │
# │ i64      ┆ i64  ┆ i64        ┆ i64     ┆ i64            │
# ╞══════════╪══════╪════════════╪═════════╪════════════════╡
# │ 1        ┆ 2013 ┆ 7087       ┆ 0       ┆ 2015           │
# │ 1        ┆ 2014 ┆ 6607       ┆ 0       ┆ 2015           │
# │ 1        ┆ 2015 ┆ 7427       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2016 ┆ 7576       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2017 ┆ 7711       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2018 ┆ 7786       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2019 ┆ 7852       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2020 ┆ 7674       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2021 ┆ 7701       ┆ 1       ┆ 2015           │
# │ 1        ┆ 2022 ┆ 8015       ┆ 1       ┆ 2015           │
# └──────────┴──────┴────────────┴─────────┴────────────────┘
# 
# Saved: /daaf/benchmarks/_sandbox/run_dc-02_Opus_4.6_1/research/2026-06-08_AdHoc_Session/data/raw/2026-06-08_synthetic-staggered-did-panel.parquet
#   [PASS] Saved file readable with correct shape: (500, 5)
# 
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
