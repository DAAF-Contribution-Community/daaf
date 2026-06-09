#!/usr/bin/env python3
"""
Ad Hoc: Generate synthetic staggered difference-in-differences panel dataset.

Task: gen-synthetic-staggered-did-panel
Mode: Ad Hoc Collaboration
Depends on: None
Input: None (synthetic data generation)
Output: data/processed/synthetic_staggered_did_panel.parquet
Checkpoint: CP3 (transform validation — row count, invariants, cohort structure)
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
# INTENT: Define all structural parameters for the synthetic panel in one place.
# REASONING: Centralizing parameters makes it easy to reproduce or modify the
# design without hunting for hard-coded values scattered through the script.
# ASSUMES: 50 states × 10 years = 500 rows; four treatment cohorts + never-treated.
PROJECT_DIR = Path("/daaf/research/2026-06-09_AdHoc_Synthetic_DiD_Panel")
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / "synthetic_staggered_did_panel.parquet"

SEED = 42
N_STATES = 50
YEARS = list(range(2013, 2023))          # 2013–2022 inclusive = 10 years
EXPECTED_ROWS = N_STATES * len(YEARS)    # 500

# Treatment cohort definitions (staggered design).
# Each tuple: (treat_year, n_states).
# Never-treated states use treat_year = None.
# REASONING: Staggered adoption is the canonical setup for modern DiD estimators
# (Callaway-Sant'Anna, Sun-Abraham, etc.). Having a never-treated group is
# critical — it provides a clean comparison group across all post-periods.
COHORT_SPEC = [
    (None, 10),   # Never-treated
    (2016, 10),   # Early adopters
    (2018, 10),   # Mid adopters
    (2020, 10),   # Late adopters
    (2022, 10),   # Very late (treated only in final year)
]

# Enrollment distribution parameters per state.
# REASONING: Real state enrollment (public K-12) ranges roughly 50K–500K.
# We simulate a stable state-specific baseline (drawn from Uniform[50K, 500K])
# plus year-over-year noise (±5% of baseline) to mimic realistic panel variation.
ENROLL_LOW = 50_000
ENROLL_HIGH = 500_000
NOISE_FRACTION = 0.05   # Noise = ±5% of state baseline

print("=" * 60)
print("Ad Hoc: Generate Synthetic Staggered DiD Panel")
print("=" * 60)
print(f"States: {N_STATES} | Years: {YEARS[0]}–{YEARS[-1]} | Expected rows: {EXPECTED_ROWS}")

# --- Generate ---

rng = np.random.default_rng(SEED)   # ASSUMES: seed=42 for reproducibility

# Step 1: Assign states to cohorts.
# INTENT: Shuffle state IDs (1–50) and slice into cohort blocks.
# REASONING: Shuffling before slicing ensures cohort assignment is not
# systematically related to state_id ordering (which could create spurious
# correlation between cohort and unobserved state characteristics).
state_ids = np.arange(1, N_STATES + 1)
shuffled = rng.permutation(state_ids)

# Build a mapping from state_id -> treat_year (or None).
state_treat_year = {}
cursor = 0
for treat_yr, n in COHORT_SPEC:
    block = shuffled[cursor : cursor + n]
    for sid in block:
        state_treat_year[int(sid)] = treat_yr
    cursor += n

print(f"\nCohort assignment complete. {cursor} states assigned.")

# Step 2: Generate stable per-state enrollment baselines.
# INTENT: Each state gets a baseline enrollment drawn once from Uniform[50K, 500K].
# REASONING: Drawing once per state (not per state-year) creates the cross-sectional
# stability that characterizes real enrollment data — states don't jump dramatically
# in size from year to year.
state_baselines = {
    int(sid): int(rng.integers(ENROLL_LOW, ENROLL_HIGH + 1))
    for sid in state_ids
}

# Step 3: Build the full panel row-by-row via list comprehension, then construct
# a Polars DataFrame.
# INTENT: Expand the state-level design into a state × year panel.
# REASONING: Using a list of dicts is straightforward for a small panel (500 rows)
# and avoids the complexity of cross-join + merge operations.
# ASSUMES: treat_year of None means never-treated; treat=0 for all years.
rows = []
for sid in state_ids:
    baseline = state_baselines[sid]
    treat_yr = state_treat_year[sid]

    for yr in YEARS:
        # Enrollment: stable baseline + symmetric noise capped to [50K, 500K].
        # REASONING: randint symmetric around baseline; clip ensures values stay
        # within plausible real-world range even for extreme noise draws.
        noise = int(rng.integers(
            -int(baseline * NOISE_FRACTION),
            int(baseline * NOISE_FRACTION) + 1
        ))
        enrollment = int(np.clip(baseline + noise, ENROLL_LOW, ENROLL_HIGH))

        # Treatment indicator: 1 if treated and year >= treat_year, else 0.
        # INTENT: Encode the absorbing treatment adoption in the binary indicator.
        # REASONING: treat=1 iff (state received treatment) AND (year is on/after
        # the adoption year). Never-treated states always have treat=0.
        # ASSUMES: Treatment is absorbing (no reversal) — once treated, always treated.
        if treat_yr is None:
            treat = 0
        else:
            treat = 1 if yr >= treat_yr else 0

        rows.append({
            "state_id": sid,
            "year": yr,
            "enrollment": enrollment,
            "treat_year": treat_yr,   # None for never-treated (will become null in Polars)
            "treat": treat,
        })

# Construct Polars DataFrame from list of dicts.
# ASSUMES: Polars correctly infers Int64 for state_id/year/enrollment/treat and
# nullable Int64 (i.e., Int64 with nulls) for treat_year when None values are present.
df = pl.DataFrame(rows)

print(f"\nDataFrame constructed: {df.shape[0]} rows × {df.shape[1]} cols")
print(f"Schema:\n{df.schema}")

# --- Validate ---
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: Correct shape
shape_ok = df.shape == (500, 5)
print(f"  [{'PASS' if shape_ok else 'FAIL'}] Shape is (500, 5): actual = {df.shape}")

# CP3.2: treat always 0 for never-treated states
# INTENT: Confirm the never-treated group has no treatment exposure in any year.
# REASONING: Any treat=1 in a never-treated state would indicate a logic error
# in the indicator construction loop above.
never_treated_states = [sid for sid, ty in state_treat_year.items() if ty is None]
df_never = df.filter(pl.col("state_id").is_in(never_treated_states))
never_treat_max = df_never["treat"].max()
never_ok = never_treat_max == 0
print(f"  [{'PASS' if never_ok else 'FAIL'}] treat always 0 for never-treated: max(treat) = {never_treat_max}")
print(f"    Never-treated states (n={len(never_treated_states)}): {sorted(never_treated_states)}")

# CP3.3: treat always 1 for rows where year >= treat_year (treated states only)
# INTENT: Verify post-treatment rows are correctly flagged.
df_post = df.filter(
    pl.col("treat_year").is_not_null() & (pl.col("year") >= pl.col("treat_year"))
)
post_treat_min = df_post["treat"].min()
post_ok = (df_post.shape[0] > 0) and (post_treat_min == 1)
print(f"  [{'PASS' if post_ok else 'FAIL'}] treat always 1 where year >= treat_year: min(treat) = {post_treat_min}, rows = {df_post.shape[0]}")

# CP3.4: treat always 0 for rows where year < treat_year (pre-treatment rows, treated states)
# INTENT: Verify pre-treatment rows for treated states are correctly flagged as 0.
df_pre = df.filter(
    pl.col("treat_year").is_not_null() & (pl.col("year") < pl.col("treat_year"))
)
pre_treat_max = df_pre["treat"].max()
pre_ok = (pre_treat_max == 0) or (df_pre.shape[0] == 0)
print(f"  [{'PASS' if pre_ok else 'FAIL'}] treat always 0 where year < treat_year: max(treat) = {pre_treat_max}, rows = {df_pre.shape[0]}")

# CP3.5: Cohort sizes are correct (10 states per cohort including never-treated).
print(f"\n  --- Cohort sizes (state-level, should be 10 each) ---")
cohort_counts = (
    df.select(["state_id", "treat_year"])
    .unique()
    .group_by("treat_year")
    .len()
    .sort("treat_year")
)
print(cohort_counts)
cohort_ok = (cohort_counts["len"] == 10).all()
print(f"  [{'PASS' if cohort_ok else 'FAIL'}] All cohorts have exactly 10 states")

# CP3.6: Enrollment within plausible range
enroll_min = df["enrollment"].min()
enroll_max = df["enrollment"].max()
enroll_ok = (enroll_min >= ENROLL_LOW) and (enroll_max <= ENROLL_HIGH)
print(f"\n  [{'PASS' if enroll_ok else 'FAIL'}] Enrollment in [{ENROLL_LOW:,}, {ENROLL_HIGH:,}]: min={enroll_min:,}, max={enroll_max:,}")

# CP3.7: No nulls in non-treat_year columns.
null_cols = {col: df[col].null_count() for col in ["state_id", "year", "enrollment", "treat"]}
null_ok = all(v == 0 for v in null_cols.values())
print(f"  [{'PASS' if null_ok else 'FAIL'}] No nulls in identifier/indicator columns: {null_cols}")
treat_year_nulls = df["treat_year"].null_count()
print(f"    treat_year nulls (expected = 10 states × 10 years = 100): {treat_year_nulls}")
treat_year_null_ok = treat_year_nulls == 100
print(f"  [{'PASS' if treat_year_null_ok else 'FAIL'}] treat_year null count = 100")

# Assert on hard blockers.
assert shape_ok,    "STOP: Shape is not (500, 5)"
assert never_ok,    "STOP: Never-treated states have treat=1 in some year"
assert post_ok,     "STOP: Post-treatment rows have treat=0"
assert pre_ok,      "STOP: Pre-treatment rows have treat=1"
assert cohort_ok,   "STOP: Cohort sizes are not all 10"
assert enroll_ok,   "STOP: Enrollment values out of plausible range"
assert null_ok,     "STOP: Unexpected nulls in key columns"

# Print a representative sample: one state from each cohort.
print("\n  --- Sample rows (one state per cohort, all years) ---")
sample_states = {}
for treat_yr, _ in COHORT_SPEC:
    for sid, ty in state_treat_year.items():
        if ty == treat_yr and sid not in sample_states.values():
            sample_states[str(treat_yr)] = sid
            break

sample_sids = list(sample_states.values())
df_sample = (
    df.filter(pl.col("state_id").is_in(sample_sids))
    .sort(["state_id", "year"])
)
print(df_sample)

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)

# --- Save ---
# INTENT: Persist the validated synthetic panel as parquet for downstream use.
# REASONING: Parquet is the DAAF standard format (compressed, typed, efficient).
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size:,} bytes")

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
