#!/usr/bin/env python3
"""
Stage 8.1: Cross-tabulation of graduation rates by selectivity band and Pell quintile.

Task: crosstab-selectivity-pell
Wave: 7, Step: 2, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_crosstab_selectivity_pell.parquet
Checkpoint: CP4
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for the selectivity x Pell quintile cross-tabulation.
# This analysis examines how graduation rates vary across selectivity bands and
# Pell grant share quintiles, and computes the "Pell gap" (difference between
# Q1 lowest-Pell and Q5 highest-Pell) within each selectivity band.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_crosstab_selectivity_pell.parquet"

# REASONING: Selectivity bands are ordered from most to least selective for
# interpretability. This ordering will be used for display and any ordinal analysis.
BAND_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]

# REASONING: Pell quintile labels Q1-Q5 where Q1 = lowest Pell share (most
# affluent student body) and Q5 = highest Pell share (most aid-dependent).
# This convention is established in the Plan's downstream cautions.
PELL_QUINTILE_ORDER = ["Q1", "Q2", "Q3", "Q4", "Q5"]

# Sparse cell threshold per downstream caution: FLAG cells with N < 10
SPARSE_THRESHOLD = 10

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands).
print("=" * 60)
print("Stage 8.1: Cross-tabulation Selectivity x Pell Quintile")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture state before filtering to non-null rows. We need both selectivity_band
# and pell_quintile to be non-null for the cross-tabulation.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()

# INTENT: Check how many rows will be dropped due to null grouping variables.
selectivity_nulls = df["selectivity_band"].null_count()
pell_quintile_nulls = df["pell_quintile"].null_count()
print(f"\nPre-state: {pre_rows:,} rows")
print(f"  selectivity_band nulls: {selectivity_nulls:,}")
print(f"  pell_quintile nulls: {pell_quintile_nulls:,}")

# --- Filter ---
# INTENT: Keep only rows where both grouping variables are non-null, since
# null values cannot participate in the cross-tabulation.
# REASONING: This is a descriptive analysis that requires both dimensions.
# Rows missing either dimension are uninformative for this specific task.
# ASSUMES: Nulls in these columns are already accounted for in the Plan's
# expected row counts (1,946 total, with some having null Pell/selectivity).
df_complete = df.filter(
    pl.col("selectivity_band").is_not_null()
    & pl.col("pell_quintile").is_not_null()
    & pl.col("completion_rate_150pct").is_not_null()
)

post_filter_rows = df_complete.shape[0]
dropped = pre_rows - post_filter_rows
print(f"  After filtering to complete cases: {post_filter_rows:,} rows ({dropped:,} dropped)")

# --- Cross-tabulation ---
# INTENT: Compute mean and median graduation rates, plus cell counts, for each
# combination of selectivity band and Pell quintile. This creates the primary
# analytical artifact: a 4x5 matrix showing how graduation rates vary along
# both dimensions simultaneously.
# REASONING: Both mean and median are reported because skewed distributions
# (especially in smaller cells) may make the median more representative.
# Count (N) is critical for assessing cell reliability.
crosstab = (
    df_complete
    .group_by(["selectivity_band", "pell_quintile"])
    .agg(
        pl.col("completion_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("completion_rate_150pct").median().alias("median_grad_rate"),
        pl.len().alias("N"),
    )
    .sort(["selectivity_band", "pell_quintile"])
)

print(f"\nCross-tabulation computed: {crosstab.shape[0]} cells")

# --- Display cross-tabulation ---
# INTENT: Print a formatted cross-tab matrix for human review in the execution log.
# This makes the results immediately visible without needing to load the parquet file.
print("\n" + "=" * 60)
print("MEAN GRADUATION RATE BY SELECTIVITY BAND x PELL QUINTILE")
print("=" * 60)

# Print header row
header = f"{'Band':<25}"
for q in PELL_QUINTILE_ORDER:
    header += f"  {q:>8}"
header += f"  {'N_total':>8}"
print(header)
print("-" * len(header))

# INTENT: Print each band's row with mean grad rates across Pell quintiles.
# REASONING: Iterating over BAND_ORDER ensures consistent display ordering
# from most selective to least selective.
for band in BAND_ORDER:
    row_str = f"{band:<25}"
    band_total_n = 0
    for q in PELL_QUINTILE_ORDER:
        cell = crosstab.filter(
            (pl.col("selectivity_band") == band)
            & (pl.col("pell_quintile") == q)
        )
        if cell.shape[0] > 0:
            mean_val = cell["mean_grad_rate"][0]
            n_val = cell["N"][0]
            band_total_n += n_val
            # INTENT: Flag sparse cells with asterisk per downstream caution.
            sparse_flag = "*" if n_val < SPARSE_THRESHOLD else " "
            row_str += f"  {mean_val:>7.1f}{sparse_flag}"
        else:
            row_str += f"  {'N/A':>8}"
    row_str += f"  {band_total_n:>8}"
    print(row_str)

print("\n* = sparse cell (N < 10)")

# Print N per cell
print("\n" + "=" * 60)
print("CELL COUNTS (N)")
print("=" * 60)

header_n = f"{'Band':<25}"
for q in PELL_QUINTILE_ORDER:
    header_n += f"  {q:>8}"
print(header_n)
print("-" * len(header_n))

sparse_cells = []
for band in BAND_ORDER:
    row_str = f"{band:<25}"
    for q in PELL_QUINTILE_ORDER:
        cell = crosstab.filter(
            (pl.col("selectivity_band") == band)
            & (pl.col("pell_quintile") == q)
        )
        if cell.shape[0] > 0:
            n_val = cell["N"][0]
            sparse_flag = "*" if n_val < SPARSE_THRESHOLD else " "
            row_str += f"  {n_val:>7}{sparse_flag}"
            if n_val < SPARSE_THRESHOLD:
                sparse_cells.append((band, q, n_val))
        else:
            row_str += f"  {'N/A':>8}"
    print(row_str)

print(f"\nSparse cells (N < {SPARSE_THRESHOLD}): {len(sparse_cells)}")
for band, q, n in sparse_cells:
    print(f"  WARNING: {band} x {q} has N={n}")

# --- Pell Gap Computation ---
# INTENT: Compute the "Pell gap" within each selectivity band -- the difference
# in mean graduation rate between Q1 (lowest Pell share / most affluent) and
# Q5 (highest Pell share / most aid-dependent). A positive gap means institutions
# with fewer Pell recipients have higher graduation rates.
#
# REASONING: The Pell gap quantifies the within-selectivity-tier disparity in
# graduation outcomes by student body economic composition. This is a key
# measure for the research question about how financial aid dependency
# complicates the selectivity-graduation relationship.
#
# ASSUMES:
#   - pell_quintile uses Q1-Q5 labels (Q1 = lowest Pell share)
#   - Both Q1 and Q5 cells exist for each band (may not if data is sparse)
print("\n" + "=" * 60)
print("PELL GAP (Q1 - Q5 Mean Grad Rate) BY SELECTIVITY BAND")
print("=" * 60)

pell_gap_records = []
for band in BAND_ORDER:
    q1_cell = crosstab.filter(
        (pl.col("selectivity_band") == band) & (pl.col("pell_quintile") == "Q1")
    )
    q5_cell = crosstab.filter(
        (pl.col("selectivity_band") == band) & (pl.col("pell_quintile") == "Q5")
    )

    if q1_cell.shape[0] > 0 and q5_cell.shape[0] > 0:
        q1_mean = q1_cell["mean_grad_rate"][0]
        q5_mean = q5_cell["mean_grad_rate"][0]
        q1_n = q1_cell["N"][0]
        q5_n = q5_cell["N"][0]
        gap = q1_mean - q5_mean  # Positive = Q1 (low Pell) has higher grad rate
        pell_gap_records.append({
            "selectivity_band": band,
            "q1_mean_grad_rate": q1_mean,
            "q5_mean_grad_rate": q5_mean,
            "pell_gap": gap,
            "q1_N": q1_n,
            "q5_N": q5_n,
        })
        sparse_note = ""
        if q1_n < SPARSE_THRESHOLD or q5_n < SPARSE_THRESHOLD:
            sparse_note = " (CAUTION: sparse cell)"
        print(f"  {band:<25}: Q1={q1_mean:.1f}%, Q5={q5_mean:.1f}%, Gap={gap:+.1f} pp{sparse_note}")
    else:
        print(f"  {band:<25}: Cannot compute (missing Q1 or Q5 data)")

pell_gap_df = pl.DataFrame(pell_gap_records)
print(f"\nPell gap computed for {len(pell_gap_records)} bands")

# --- Save ---
# INTENT: Save both the full cross-tabulation and the Pell gap summary to a
# single parquet file. The cross-tabulation is the primary artifact; the Pell gap
# is a derived summary that is also valuable for downstream analysis and reporting.
#
# REASONING: Saving as a single parquet with the detailed cross-tab data. The
# Pell gap is printed to stdout and can be reconstructed from the cross-tab,
# but we add a pell_gap column for cells where it applies (Q1 and Q5 rows).
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# INTENT: Enrich the cross-tab with a pell_gap column that shows the gap value
# for each band (applied only to Q1 rows for clarity, null for others).
# REASONING: This makes the parquet self-contained -- both the cell-level data
# and the band-level Pell gap are in one file.
# ASSUMES: pell_gap_df contains one row per band with the gap calculation.
crosstab_enriched = crosstab.join(
    pell_gap_df.select("selectivity_band", "pell_gap"),
    on="selectivity_band",
    how="left",
)

crosstab_enriched.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"  Shape: {crosstab_enriched.shape[0]} rows x {crosstab_enriched.shape[1]} cols")

# --- CP4 Validation ---
# Checkpoint validation: verify cross-tabulation meets Plan expectations for
# cell coverage, value ranges, and output file existence.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Output file exists and is non-zero
file_exists = OUTPUT_PATH.exists()
file_size = OUTPUT_PATH.stat().st_size if file_exists else 0
size_ok = file_size > 0
print(f"  [{'PASS' if (file_exists and size_ok) else 'FAIL'}] Output file exists and non-zero: {file_size:,} bytes")
if not (file_exists and size_ok):
    cp4_passed = False

# CP4.2: Cross-tab has 20 cells (4 bands x 5 quintiles)
n_cells = crosstab.shape[0]
# REASONING: Some cells may be missing if no institutions fall in that combination.
# We expect 20 but allow fewer with a warning.
cells_expected = 20
cells_ok = n_cells == cells_expected
print(f"  [{'PASS' if cells_ok else 'WARN'}] Cell count: {n_cells} (expected {cells_expected})")
if n_cells < cells_expected:
    print(f"    Missing {cells_expected - n_cells} cells -- some band x quintile combinations have no data")

# CP4.3: Mean graduation rates are between 0 and 100
min_grad = crosstab["mean_grad_rate"].min()
max_grad = crosstab["mean_grad_rate"].max()
range_ok = min_grad >= 0 and max_grad <= 100
print(f"  [{'PASS' if range_ok else 'FAIL'}] Grad rates in [0, 100]: min={min_grad:.1f}, max={max_grad:.1f}")
if not range_ok:
    cp4_passed = False

# CP4.4: Check for sparse cells (N < 10) -- WARN only, not FAIL
n_sparse = len(sparse_cells)
print(f"  [{'PASS' if n_sparse == 0 else 'WARN'}] Sparse cells (N < {SPARSE_THRESHOLD}): {n_sparse}")
for band, q, n in sparse_cells:
    print(f"    FLAG: {band} x {q} has N={n}")

# CP4.5: Verify all bands are represented
bands_present = crosstab["selectivity_band"].unique().to_list()
all_bands = all(b in bands_present for b in BAND_ORDER)
print(f"  [{'PASS' if all_bands else 'WARN'}] All 4 bands present: {all_bands}")

# CP4.6: Verify all quintiles are represented
quintiles_present = crosstab["pell_quintile"].unique().to_list()
all_quintiles = all(q in quintiles_present for q in PELL_QUINTILE_ORDER)
print(f"  [{'PASS' if all_quintiles else 'WARN'}] All 5 quintiles present: {all_quintiles}")

# CP4.7: Verify Pell gap was computed for at least 3 bands
gap_count = len(pell_gap_records)
gap_ok = gap_count >= 3
print(f"  [{'PASS' if gap_ok else 'WARN'}] Pell gap computed for {gap_count}/4 bands")

assert cp4_passed, "STOP: CP4 validation failed -- see details above"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 11:44:28
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell.py
# Duration: s
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Cross-tabulation Selectivity x Pell Quintile
# ============================================================
# Loaded: 1,946 rows x 25 cols
# 
# Pre-state: 1,946 rows
#   selectivity_band nulls: 0
#   pell_quintile nulls: 59
#   After filtering to complete cases: 1,887 rows (59 dropped)
# 
# Cross-tabulation computed: 20 cells
# 
# ============================================================
# MEAN GRADUATION RATE BY SELECTIVITY BAND x PELL QUINTILE
# ============================================================
# Band                             Q1        Q2        Q3        Q4        Q5   N_total
# -------------------------------------------------------------------------------------
# Highly Selective                N/A     91.4      89.3      64.7*       N/A        60
# Selective                       N/A     67.7      73.2      55.9        N/A       119
# Moderately Selective            N/A     57.7      61.4      59.4        N/A       356
# Open/Less Selective             N/A     51.6      50.5      55.0        N/A       677
# 
# * = sparse cell (N < 10)
# 
# ============================================================
# CELL COUNTS (N)
# ============================================================
# Band                             Q1        Q2        Q3        Q4        Q5
# ---------------------------------------------------------------------------
# Highly Selective                N/A       38        19         3*       N/A
# Selective                       N/A       37        41        41        N/A
# Moderately Selective            N/A       85       124       147        N/A
# Open/Less Selective             N/A      223       226       228        N/A
# 
# Sparse cells (N < 10): 1
#   WARNING: Highly Selective x Q4 has N=3
# 
# ============================================================
# PELL GAP (Q1 - Q5 Mean Grad Rate) BY SELECTIVITY BAND
# ============================================================
#   Highly Selective         : Cannot compute (missing Q1 or Q5 data)
#   Selective                : Cannot compute (missing Q1 or Q5 data)
#   Moderately Selective     : Cannot compute (missing Q1 or Q5 data)
#   Open/Less Selective      : Cannot compute (missing Q1 or Q5 data)
# 
# Pell gap computed for 0 bands
# Traceback (most recent call last):
#   File "/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/02_crosstab-selectivity-pell.py", line 239, in <module>
#     pell_gap_df.select("selectivity_band", "pell_gap"),
#     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/dataframe/frame.py", line 10307, in select
#     .collect(optimizations=QueryOptFlags._eager())
#      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 97, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/opt_flags.py", line 326, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/lazyframe/frame.py", line 2440, in collect
#     return wrap_df(ldf.collect(engine, callback))
#                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.ColumnNotFoundError: unable to find column "selectivity_band"; valid columns: []
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
