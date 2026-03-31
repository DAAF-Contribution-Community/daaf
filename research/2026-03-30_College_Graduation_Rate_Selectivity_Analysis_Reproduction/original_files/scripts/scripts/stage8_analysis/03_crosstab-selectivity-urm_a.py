#!/usr/bin/env python3
"""
Stage 8.1: Cross-tabulation of graduation rates by selectivity band and URM quintile.

Task: crosstab-selectivity-urm
Wave: 7, Step: 3, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_crosstab_selectivity_urm.parquet
Checkpoint: CP4

Revision _a: Fix quintile label matching. v1 assumed plain "Q1"-"Q5" labels
but actual data uses "Q1 (Lowest)", "Q2", ..., "Q5 (Highest)". Updated
QUINTILE_ORDER to match actual labels and fixed Q1-Q5 gap logic accordingly.
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for the selectivity x URM quintile cross-tabulation.
# Band and quintile definitions come from the Stage 7 create-bands script.
# Band distribution from Plan context: HS=71, S=177, MS=577, OLS=1121 (total=1946).
PROJECT_DIR = Path("/daaf/research/2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_urm.parquet"

# REASONING: Selectivity bands are ordered from most to least selective for
# interpretability. This order matches the Plan's band definitions.
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]

# REASONING: URM quintile labels from the data include descriptive suffixes.
# v1 assumed plain "Q1"-"Q5" but actual data uses "Q1 (Lowest)" and "Q5 (Highest)".
# Per downstream caution from Plan: Q1 = lowest URM share, Q5 = highest URM share.
QUINTILE_ORDER = ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"]

# REASONING: Q1 and Q5 labels with suffixes for gap computation.
Q1_LABEL = "Q1 (Lowest)"
Q5_LABEL = "Q5 (Highest)"

# REASONING: N<10 threshold for flagging sparse cells. Per Plan downstream
# caution: 5 sparse cells expected with N<10; HS x Q5-URM may be empty.
SPARSE_THRESHOLD = 10

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands).
print("=" * 60)
print("Stage 8.1: Cross-tabulation Selectivity x URM Quintile")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state before filtering to non-null rows for the cross-tab.
# INTENT: Establish baseline row count and verify required columns exist.
pre_rows = df.shape[0]
required_cols = ["selectivity_band", "urm_quintile", "completion_rate_150pct"]
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"STOP: Missing required columns: {missing_cols}"

print(f"Pre-state: {pre_rows:,} rows")
print(f"  selectivity_band nulls: {df['selectivity_band'].null_count():,}")
print(f"  urm_quintile nulls: {df['urm_quintile'].null_count():,}")
print(f"  completion_rate_150pct nulls: {df['completion_rate_150pct'].null_count():,}")

# Verify actual quintile labels match our expected labels
actual_quintiles = sorted(df.filter(pl.col("urm_quintile").is_not_null())["urm_quintile"].unique().to_list())
print(f"  Actual urm_quintile labels: {actual_quintiles}")

# --- Filter to complete cases ---
# INTENT: Filter to rows where both selectivity_band and urm_quintile are non-null,
# as the cross-tabulation requires both grouping variables to be defined.
# REASONING: Rows with null band or quintile cannot be assigned to any cell
# in the 4x5 matrix, so they must be excluded. We also need non-null
# completion_rate_150pct to compute meaningful means/medians.
# ASSUMES: Nulls in these columns represent institutions that could not be
# classified (e.g., no admit_rate for selectivity, no URM data for quintile).
df_complete = df.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("urm_quintile").is_not_null()
    & pl.col("completion_rate_150pct").is_not_null()
)

dropped = pre_rows - df_complete.shape[0]
drop_pct = dropped / pre_rows * 100 if pre_rows > 0 else 0
print(f"\nComplete cases: {df_complete.shape[0]:,} ({dropped:,} rows dropped, {drop_pct:.1f}%)")

assert df_complete.shape[0] > 0, "STOP: No complete cases for cross-tabulation"

# --- Compute grouped statistics ---
# INTENT: Group by [selectivity_band, urm_quintile] and compute mean, median,
# and count of completion_rate_150pct for each cell of the 4x5 matrix.
# REASONING: Mean captures the central tendency; median provides a robust
# alternative less influenced by outliers. Count (N) is critical for
# assessing statistical reliability of each cell estimate.
crosstab = (
    df_complete
    .group_by(["selectivity_band", "urm_quintile"])
    .agg(
        pl.col("completion_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("completion_rate_150pct").median().alias("median_grad_rate"),
        pl.len().alias("N"),
    )
    .sort(["selectivity_band", "urm_quintile"])
)

print(f"\nGrouped statistics: {crosstab.shape[0]} cells")
print(crosstab)

# --- Format cross-tabulation for display ---
# INTENT: Pivot the grouped data into a readable 4x5 matrix with bands as rows
# and URM quintiles as columns.
# REASONING: Pivoted format is standard for cross-tabulations and allows
# easy visual comparison across quintiles within each band.

# Mean grad rate pivot
print("\n" + "=" * 60)
print("CROSS-TABULATION: Mean Graduation Rate")
print("  (rows = selectivity band, cols = URM quintile)")
print("  Q1 (Lowest) = lowest URM share, Q5 (Highest) = highest URM share")
print("=" * 60)

mean_pivot = (
    crosstab
    .pivot(on="urm_quintile", index="selectivity_band", values="mean_grad_rate")
)

# INTENT: Reorder rows and columns for consistent presentation.
# REASONING: Without explicit ordering, Polars may sort alphabetically which
# would place "Highly Selective" before "Moderately Selective" but after "Open/Less".
# We need the conceptual ordering from most to least selective.
available_quintile_cols = [q for q in QUINTILE_ORDER if q in mean_pivot.columns]
mean_pivot = (
    mean_pivot
    .with_columns(
        pl.col("selectivity_band")
        .cast(pl.Enum(BAND_ORDER))
        .alias("selectivity_band")
    )
    .sort("selectivity_band")
    .select(["selectivity_band"] + available_quintile_cols)
)

print(mean_pivot)

# N (count) pivot
print("\n" + "=" * 60)
print("CELL COUNTS (N)")
print("=" * 60)

n_pivot = (
    crosstab
    .pivot(on="urm_quintile", index="selectivity_band", values="N")
)

n_pivot = (
    n_pivot
    .with_columns(
        pl.col("selectivity_band")
        .cast(pl.Enum(BAND_ORDER))
        .alias("selectivity_band")
    )
    .sort("selectivity_band")
    .select(["selectivity_band"] + available_quintile_cols)
)

print(n_pivot)

# --- Flag sparse cells ---
# INTENT: Identify cells with N < 10 per the Plan's downstream caution.
# REASONING: Small cell sizes produce unreliable estimates of mean/median.
# Per Plan: 5 sparse cells expected with N<10; HS x Q5-URM may be empty.
print("\n" + "=" * 60)
print("SPARSE CELL CHECK (N < 10)")
print("=" * 60)

sparse_cells = crosstab.filter(pl.col("N") < SPARSE_THRESHOLD)
if sparse_cells.shape[0] > 0:
    print(f"WARNING: {sparse_cells.shape[0]} sparse cell(s) found:")
    print(sparse_cells)
else:
    print("No sparse cells found (all N >= 10)")

# Also check for missing cells (band x quintile combos with zero institutions)
all_combos = set()
for band in BAND_ORDER:
    for q in QUINTILE_ORDER:
        all_combos.add((band, q))

observed_combos = set(
    zip(
        crosstab["selectivity_band"].to_list(),
        crosstab["urm_quintile"].to_list(),
    )
)

missing_combos = all_combos - observed_combos
if missing_combos:
    print(f"\nWARNING: {len(missing_combos)} empty cell(s) (no institutions):")
    for band, q in sorted(missing_combos, key=lambda x: (BAND_ORDER.index(x[0]), QUINTILE_ORDER.index(x[1]))):
        print(f"  {band} x {q}: N=0")
else:
    print("\nNo empty cells -- all 20 combinations represented")

# --- Compute Q1-Q5 gap within each band ---
# INTENT: For each selectivity band, compute the difference in mean graduation
# rate between Q1 (lowest URM share) and Q5 (highest URM share).
# REASONING: This gap quantifies how much graduation rates differ between
# institutions serving the fewest vs. most underrepresented minority students
# within the same selectivity tier. A large positive gap suggests that
# institutions with more URM students have lower graduation rates even
# after controlling for selectivity.
# ASSUMES: Q1 and Q5 labels are "Q1 (Lowest)" and "Q5 (Highest)" respectively.
# Some bands may lack Q1 or Q5 entries (especially HS band per Plan caution).
print("\n" + "=" * 60)
print("Q1-Q5 URM GAP BY SELECTIVITY BAND")
print("  (Positive = Q1 higher than Q5)")
print("=" * 60)

q1_rates = crosstab.filter(pl.col("urm_quintile") == Q1_LABEL).select(
    "selectivity_band",
    pl.col("mean_grad_rate").alias("q1_mean"),
    pl.col("N").alias("q1_n"),
)

q5_rates = crosstab.filter(pl.col("urm_quintile") == Q5_LABEL).select(
    "selectivity_band",
    pl.col("mean_grad_rate").alias("q5_mean"),
    pl.col("N").alias("q5_n"),
)

print(f"Bands with Q1 data: {q1_rates.shape[0]}")
print(f"Bands with Q5 data: {q5_rates.shape[0]}")

if q1_rates.shape[0] > 0 and q5_rates.shape[0] > 0:
    # INTENT: Join Q1 and Q5 data by band to compute the gap.
    # REASONING: Using full join so we see bands that have Q1 but not Q5
    # (or vice versa), which is informative about where the gap cannot be computed.
    gap_df = q1_rates.join(q5_rates, on="selectivity_band", how="full", coalesce=True)
    gap_df = gap_df.with_columns(
        (pl.col("q1_mean") - pl.col("q5_mean")).alias("q1_q5_gap")  # Positive = Q1 higher
    )

    # Reorder by band order
    present_bands = [b for b in BAND_ORDER if b in gap_df["selectivity_band"].to_list()]
    if present_bands:
        gap_df = (
            gap_df
            .filter(pl.col("selectivity_band").is_in(present_bands))
            .with_columns(
                pl.col("selectivity_band")
                .cast(pl.Enum(BAND_ORDER))
                .alias("selectivity_band")
            )
            .sort("selectivity_band")
        )
    print(gap_df)
elif q1_rates.shape[0] > 0:
    print("Q5 data not available for any band -- gap cannot be computed")
elif q5_rates.shape[0] > 0:
    print("Q1 data not available for any band -- gap cannot be computed")
else:
    print("Neither Q1 nor Q5 data available -- gap cannot be computed")

# INTENT: Also compute the gap using Q2 vs Q4 as a supplementary measure.
# REASONING: Q1/Q5 may be empty for some bands (HS has only 71 institutions
# total), so Q2-Q4 gap provides a more robust comparison that covers all bands.
print("\n" + "=" * 60)
print("SUPPLEMENTARY: Q2-Q4 URM GAP BY SELECTIVITY BAND")
print("  (Fallback when Q1/Q5 not available for all bands)")
print("  (Positive = Q2 higher than Q4)")
print("=" * 60)

q2_rates = crosstab.filter(pl.col("urm_quintile") == "Q2").select(
    "selectivity_band",
    pl.col("mean_grad_rate").alias("q2_mean"),
    pl.col("N").alias("q2_n"),
)

q4_rates = crosstab.filter(pl.col("urm_quintile") == "Q4").select(
    "selectivity_band",
    pl.col("mean_grad_rate").alias("q4_mean"),
    pl.col("N").alias("q4_n"),
)

if q2_rates.shape[0] > 0 and q4_rates.shape[0] > 0:
    gap_q2q4 = q2_rates.join(q4_rates, on="selectivity_band", how="inner")
    gap_q2q4 = gap_q2q4.with_columns(
        (pl.col("q2_mean") - pl.col("q4_mean")).alias("q2_q4_gap")
    )
    present_bands = [b for b in BAND_ORDER if b in gap_q2q4["selectivity_band"].to_list()]
    if present_bands:
        gap_q2q4 = (
            gap_q2q4
            .filter(pl.col("selectivity_band").is_in(present_bands))
            .with_columns(
                pl.col("selectivity_band")
                .cast(pl.Enum(BAND_ORDER))
                .alias("selectivity_band")
            )
            .sort("selectivity_band")
        )
    print(gap_q2q4)
else:
    print("Q2 or Q4 data not available for gap computation")

# --- Save ---
# INTENT: Save the full cross-tabulation (long format) to parquet for downstream use.
# REASONING: Saving the long-format grouped data (not the pivoted version)
# because it preserves all computed statistics and is easier to manipulate
# programmatically. The pivoted format is for display only.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
crosstab.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# Verify file exists and is non-zero
file_size = OUTPUT_PATH.stat().st_size
print(f"File size: {file_size:,} bytes")

# --- CP4 Validation ---
# Checkpoint validation: verify cross-tabulation completeness, value ranges,
# cell counts, and output file persistence.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Output file exists and is non-zero
file_exists = OUTPUT_PATH.exists() and OUTPUT_PATH.stat().st_size > 0
if file_exists:
    print(f"[PASS] Output file exists and non-zero ({file_size:,} bytes)")
else:
    print(f"[FAIL] Output file missing or empty")
    cp4_passed = False

# CP4.2: Cross-tab cell count
# REASONING: 4 bands x 5 quintiles = 20 possible cells. Some may be empty
# (e.g., HS x Q5 per Plan caution), so we check actual vs expected.
total_possible = 20
actual_cells = crosstab.shape[0]
cell_count_note = f"{actual_cells}/{total_possible}"
if actual_cells == total_possible:
    print(f"[PASS] Cross-tab has {cell_count_note} cells (complete)")
elif actual_cells >= 15:
    print(f"[WARN] Cross-tab has {cell_count_note} cells ({total_possible - actual_cells} missing)")
else:
    print(f"[FAIL] Cross-tab has {cell_count_note} cells (too many missing)")
    cp4_passed = False

# CP4.3: Mean grad rates between 0 and 100
min_rate = crosstab["mean_grad_rate"].min()
max_rate = crosstab["mean_grad_rate"].max()
rates_valid = min_rate >= 0 and max_rate <= 100
if rates_valid:
    print(f"[PASS] Mean grad rates in [0, 100]: min={min_rate:.1f}, max={max_rate:.1f}")
else:
    print(f"[FAIL] Mean grad rates out of range: min={min_rate:.1f}, max={max_rate:.1f}")
    cp4_passed = False

# CP4.4: N per cell >= 10 (WARN if any cell < 10)
min_n = crosstab["N"].min()
n_sparse = crosstab.filter(pl.col("N") < SPARSE_THRESHOLD).shape[0]
total_issues = n_sparse + len(missing_combos)
if total_issues == 0:
    print(f"[PASS] All cells have N >= {SPARSE_THRESHOLD} (min N={min_n})")
else:
    print(f"[WARN] {n_sparse} sparse cell(s) (N<{SPARSE_THRESHOLD}) + {len(missing_combos)} empty cell(s)")

# CP4.5: Required columns in output
required_output_cols = ["selectivity_band", "urm_quintile", "mean_grad_rate", "median_grad_rate", "N"]
output_df = pl.read_parquet(OUTPUT_PATH)
missing_output_cols = [c for c in required_output_cols if c not in output_df.columns]
if not missing_output_cols:
    print(f"[PASS] All required columns present in output")
else:
    print(f"[FAIL] Missing columns in output: {missing_output_cols}")
    cp4_passed = False

assert cp4_passed, "STOP: CP4 validation failed"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 11:47:38
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_crosstab-selectivity-urm_a.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Cross-tabulation Selectivity x URM Quintile
# ============================================================
# Loaded: 1,946 rows x 25 cols
# Pre-state: 1,946 rows
#   selectivity_band nulls: 0
#   urm_quintile nulls: 7
#   completion_rate_150pct nulls: 0
#   Actual urm_quintile labels: ['Q1 (Lowest)', 'Q2', 'Q3', 'Q4', 'Q5 (Highest)']
#
# Complete cases: 1,939 (7 rows dropped, 0.4%)
#
# Grouped statistics: 19 cells
# shape: (19, 5)
# ┌──────────────────────┬──────────────┬────────────────┬──────────────────┬─────┐
# │ selectivity_band     ┆ urm_quintile ┆ mean_grad_rate ┆ median_grad_rate ┆ N   │
# │ ---                  ┆ ---          ┆ ---            ┆ ---              ┆ --- │
# │ str                  ┆ cat          ┆ f64            ┆ f64              ┆ u32 │
# ╞══════════════════════╪══════════════╪════════════════╪══════════════════╪═════╡
# │ Highly Selective     ┆ Q1 (Lowest)  ┆ 68.614286      ┆ 76.9             ┆ 7   │
# │ Highly Selective     ┆ Q2           ┆ 90.841935      ┆ 91.5             ┆ 31  │
# │ Highly Selective     ┆ Q3           ┆ 92.437931      ┆ 93.8             ┆ 29  │
# │ Highly Selective     ┆ Q4           ┆ 73.75          ┆ 89.95            ┆ 4   │
# │ Moderately Selective ┆ Q1 (Lowest)  ┆ 63.29386       ┆ 67.5             ┆ 114 │
# │ …                    ┆ …            ┆ …              ┆ …                ┆ …   │
# │ Selective            ┆ Q1 (Lowest)  ┆ 66.142105      ┆ 65.2             ┆ 19  │
# │ Selective            ┆ Q2           ┆ 78.688636      ┆ 83.7             ┆ 44  │
# │ Selective            ┆ Q3           ┆ 66.182857      ┆ 73.5             ┆ 35  │
# │ Selective            ┆ Q4           ┆ 50.697436      ┆ 53.7             ┆ 39  │
# │ Selective            ┆ Q5 (Highest) ┆ 37.564103      ┆ 37.0             ┆ 39  │
# └──────────────────────┴──────────────┴────────────────┴──────────────────┴─────┘
#
# ============================================================
# CROSS-TABULATION: Mean Graduation Rate
#   (rows = selectivity band, cols = URM quintile)
#   Q1 (Lowest) = lowest URM share, Q5 (Highest) = highest URM share
# ============================================================
# shape: (4, 6)
# ┌──────────────────────┬─────────────┬───────────┬───────────┬───────────┬──────────────┐
# │ selectivity_band     ┆ Q1 (Lowest) ┆ Q2        ┆ Q3        ┆ Q4        ┆ Q5 (Highest) │
# │ ---                  ┆ ---         ┆ ---       ┆ ---       ┆ ---       ┆ ---          │
# │ enum                 ┆ f64         ┆ f64       ┆ f64       ┆ f64       ┆ f64          │
# ╞══════════════════════╪═════════════╪═══════════╪═══════════╪═══════════╪══════════════╡
# │ Highly Selective     ┆ 68.614286   ┆ 90.841935 ┆ 92.437931 ┆ 73.75     ┆ null         │
# │ Selective            ┆ 66.142105   ┆ 78.688636 ┆ 66.182857 ┆ 50.697436 ┆ 37.564103    │
# │ Moderately Selective ┆ 63.29386    ┆ 64.397297 ┆ 58.721154 ┆ 50.998947 ┆ 39.03125     │
# │ Open/Less Selective  ┆ 54.283636   ┆ 58.407212 ┆ 54.196133 ┆ 48.455189 ┆ 43.917155    │
# └──────────────────────┴─────────────┴───────────┴───────────┴───────────┴──────────────┘
#
# ============================================================
# CELL COUNTS (N)
# ============================================================
# shape: (4, 6)
# ┌──────────────────────┬─────────────┬─────┬─────┬─────┬──────────────┐
# │ selectivity_band     ┆ Q1 (Lowest) ┆ Q2  ┆ Q3  ┆ Q4  ┆ Q5 (Highest) │
# │ ---                  ┆ ---         ┆ --- ┆ --- ┆ --- ┆ ---          │
# │ enum                 ┆ u32         ┆ u32 ┆ u32 ┆ u32 ┆ u32          │
# ╞══════════════════════╪═════════════╪═════╪═════╪═════╪══════════════╡
# │ Highly Selective     ┆ 7           ┆ 31  ┆ 29  ┆ 4   ┆ null         │
# │ Selective            ┆ 19          ┆ 44  ┆ 35  ┆ 39  ┆ 39           │
# │ Moderately Selective ┆ 114         ┆ 148 ┆ 156 ┆ 95  ┆ 64           │
# │ Open/Less Selective  ┆ 275         ┆ 208 ┆ 181 ┆ 212 ┆ 239          │
# └──────────────────────┴─────────────┴─────┴─────┴─────┴──────────────┘
#
# ============================================================
# SPARSE CELL CHECK (N < 10)
# ============================================================
# WARNING: 2 sparse cell(s) found:
# shape: (2, 5)
# ┌──────────────────┬──────────────┬────────────────┬──────────────────┬─────┐
# │ selectivity_band ┆ urm_quintile ┆ mean_grad_rate ┆ median_grad_rate ┆ N   │
# │ ---              ┆ ---          ┆ ---            ┆ ---              ┆ --- │
# │ str              ┆ cat          ┆ f64            ┆ f64              ┆ u32 │
# ╞══════════════════╪══════════════╪════════════════╪══════════════════╪═════╡
# │ Highly Selective ┆ Q1 (Lowest)  ┆ 68.614286      ┆ 76.9             ┆ 7   │
# │ Highly Selective ┆ Q4           ┆ 73.75          ┆ 89.95            ┆ 4   │
# └──────────────────┴──────────────┴────────────────┴──────────────────┴─────┘
#
# WARNING: 1 empty cell(s) (no institutions):
#   Highly Selective x Q5 (Highest): N=0
#
# ============================================================
# Q1-Q5 URM GAP BY SELECTIVITY BAND
#   (Positive = Q1 higher than Q5)
# ============================================================
# Bands with Q1 data: 4
# Bands with Q5 data: 3
# shape: (4, 6)
# ┌──────────────────────┬───────────┬──────┬───────────┬──────┬───────────┐
# │ selectivity_band     ┆ q1_mean   ┆ q1_n ┆ q5_mean   ┆ q5_n ┆ q1_q5_gap │
# │ ---                  ┆ ---       ┆ ---  ┆ ---       ┆ ---  ┆ ---       │
# │ enum                 ┆ f64       ┆ u32  ┆ f64       ┆ u32  ┆ f64       │
# ╞══════════════════════╪═══════════╪══════╪═══════════╪══════╪═══════════╡
# │ Highly Selective     ┆ 68.614286 ┆ 7    ┆ null      ┆ null ┆ null      │
# │ Selective            ┆ 66.142105 ┆ 19   ┆ 37.564103 ┆ 39   ┆ 28.578003 │
# │ Moderately Selective ┆ 63.29386  ┆ 114  ┆ 39.03125  ┆ 64   ┆ 24.26261  │
# │ Open/Less Selective  ┆ 54.283636 ┆ 275  ┆ 43.917155 ┆ 239  ┆ 10.366482 │
# └──────────────────────┴───────────┴──────┴───────────┴──────┴───────────┘
#
# ============================================================
# SUPPLEMENTARY: Q2-Q4 URM GAP BY SELECTIVITY BAND
#   (Fallback when Q1/Q5 not available for all bands)
#   (Positive = Q2 higher than Q4)
# ============================================================
# shape: (4, 6)
# ┌──────────────────────┬───────────┬──────┬───────────┬──────┬───────────┐
# │ selectivity_band     ┆ q2_mean   ┆ q2_n ┆ q4_mean   ┆ q4_n ┆ q2_q4_gap │
# │ ---                  ┆ ---       ┆ ---  ┆ ---       ┆ ---  ┆ ---       │
# │ enum                 ┆ f64       ┆ u32  ┆ f64       ┆ u32  ┆ f64       │
# ╞══════════════════════╪═══════════╪══════╪═══════════╪══════╪═══════════╡
# │ Highly Selective     ┆ 90.841935 ┆ 31   ┆ 73.75     ┆ 4    ┆ 17.091935 │
# │ Selective            ┆ 78.688636 ┆ 44   ┆ 50.697436 ┆ 39   ┆ 27.9912   │
# │ Moderately Selective ┆ 64.397297 ┆ 148  ┆ 50.998947 ┆ 95   ┆ 13.39835  │
# │ Open/Less Selective  ┆ 58.407212 ┆ 208  ┆ 48.455189 ┆ 212  ┆ 9.952023  │
# └──────────────────────┴───────────┴──────┴───────────┴──────┴───────────┘
#
# Saved: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_crosstab_selectivity_urm.parquet
# File size: 2,528 bytes
#
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
# [PASS] Output file exists and non-zero (2,528 bytes)
# [WARN] Cross-tab has 19/20 cells (1 missing)
# [PASS] Mean grad rates in [0, 100]: min=37.6, max=92.4
# [WARN] 2 sparse cell(s) (N<10) + 1 empty cell(s)
# [PASS] All required columns present in output
#
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
