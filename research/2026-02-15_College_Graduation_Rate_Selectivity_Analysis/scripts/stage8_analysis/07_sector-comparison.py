#!/usr/bin/env python3
"""
Stage 8.7: Sector comparison — graduation rates by selectivity band and institutional sector.

Task: sector-comparison
Wave: 8, Step: 7, Stage: 8
Depends on: create-bands (Wave 7)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_sector_comparison.parquet
Checkpoint: CP4

Observable Truth: "Private nonprofit institutions have higher graduation rates
than public institutions within the same selectivity band."
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan. This script groups the analysis
# dataset by selectivity_band and inst_control (1=Public, 2=Private nonprofit)
# to compare graduation rates within selectivity tiers. The analysis tests
# whether the public/private gap persists after controlling for selectivity,
# and whether compositional differences (Pell share, URM share) explain the gap.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_sector_comparison.parquet"

# REASONING: Selectivity band ordering follows the natural hierarchy from the
# Plan's create-bands step. This ordering ensures the comparison table reads
# logically from most to least selective.
SELECTIVITY_ORDER = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]

# inst_control mapping from IPEDS: 1=Public, 2=Private nonprofit.
# For-profits (3) were excluded at the fetch stage per Plan.
SECTOR_LABELS = {1: "Public", 2: "Private nonprofit"}

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands). This dataset
# has selectivity_band, pell_band, and urm_band already assigned.
print("=" * 60)
print("Stage 8.7: Sector Comparison — Grad Rates by Selectivity & Sector")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture the state of the data before the groupby aggregation. We need to
# verify that selectivity_band and inst_control have the expected value
# distributions so the groupby produces the expected number of rows.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Check selectivity_band distribution
print("\nSelectivity band distribution:")
band_counts = df.group_by("selectivity_band").len().sort("selectivity_band")
for row in band_counts.iter_rows(named=True):
    print(f"  {row['selectivity_band']}: {row['len']:,}")

# Check inst_control distribution
print("\nInstitutional control distribution:")
ctrl_counts = df.group_by("inst_control").len().sort("inst_control")
for row in ctrl_counts.iter_rows(named=True):
    label = SECTOR_LABELS.get(row["inst_control"], f"Unknown({row['inst_control']})")
    print(f"  {row['inst_control']} ({label}): {row['len']:,}")

# Count non-null grad_rate_150pct for context on how many institutions
# contribute to the median/mean calculations
grad_rate_non_null = df.filter(pl.col("grad_rate_150pct").is_not_null()).shape[0]
print(f"\nInstitutions with non-null grad_rate_150pct: {grad_rate_non_null:,} / {pre_rows:,} "
      f"({grad_rate_non_null / pre_rows * 100:.1f}%)")

# --- Transform ---
# INTENT: Group by selectivity_band AND inst_control to compute summary
# statistics for graduation rate, Pell share, and URM share within each
# selectivity-sector cell. This directly tests whether private nonprofits
# outperform publics within the same selectivity tier and whether compositional
# differences (Pell share, URM share) provide an explanation.
#
# REASONING: Using group_by with multiple aggregation expressions in a single
# .agg() call is the idiomatic Polars pattern. We compute both median and mean
# for grad_rate_150pct because median is robust to skew (especially in smaller
# cells like "Highly Selective" x "Public") while mean provides a complementary
# view. Pell and URM medians contextualize whether the two sectors serve
# different student populations within the same selectivity band.
#
# ASSUMES:
#   - selectivity_band has exactly 4 values matching SELECTIVITY_ORDER
#   - inst_control has values 1 (Public) and 2 (Private nonprofit) only
#   - grad_rate_150pct is on a 0-100 percentage scale; nulls are legitimate
#     (institution did not report) and should be excluded from aggregation
#   - pell_share and urm_share are proportions (0-1 scale)
result = (
    df
    .group_by("selectivity_band", "inst_control")
    .agg(
        pl.len().alias("n"),  # Total institutions in cell
        pl.col("grad_rate_150pct").drop_nulls().len().alias("n_with_grad_rate"),  # How many have grad rate data
        pl.col("grad_rate_150pct").median().alias("median_grad_rate"),
        pl.col("grad_rate_150pct").mean().alias("mean_grad_rate"),
        pl.col("grad_rate_150pct").std().alias("std_grad_rate"),  # Dispersion within cell
        pl.col("pell_share").median().alias("median_pell_share"),
        pl.col("urm_share").median().alias("median_urm_share"),
        pl.col("student_faculty_ratio").median().alias("median_student_faculty_ratio"),
        pl.col("retention_rate").median().alias("median_retention_rate"),
    )
)

# INTENT: Add a human-readable sector label and sort for presentation clarity.
# REASONING: Sorting by selectivity_band (in logical order) then by inst_control
# ensures the comparison table pairs public and private rows within each band.
result = result.with_columns(
    pl.col("inst_control")
    .replace_strict(SECTOR_LABELS, return_dtype=pl.String)
    .alias("sector_label")
)

# Sort by selectivity band order then by sector
# REASONING: Using a categorical ordering ensures the sort respects the logical
# selectivity hierarchy rather than alphabetical order.
result = result.with_columns(
    pl.col("selectivity_band").cast(pl.Categorical)
)

# Manual sort: map selectivity_band to ordinal for sorting
result = result.with_columns(
    pl.col("selectivity_band").replace_strict(
        {band: i for i, band in enumerate(SELECTIVITY_ORDER)},
        return_dtype=pl.Int32,
    ).alias("_sort_order")
).sort("_sort_order", "inst_control").drop("_sort_order")

# --- Post-state & Interpretation ---
print(f"\nPost-state: {result.shape[0]:,} rows x {result.shape[1]} cols")

print("\n" + "=" * 60)
print("SECTOR COMPARISON TABLE")
print("=" * 60)

# Print the comparison table in a readable format
for band in SELECTIVITY_ORDER:
    band_data = result.filter(pl.col("selectivity_band") == band)
    print(f"\n--- {band} ---")
    for row in band_data.iter_rows(named=True):
        label = row["sector_label"]
        n = row["n"]
        n_gr = row["n_with_grad_rate"]
        med_gr = row["median_grad_rate"]
        mean_gr = row["mean_grad_rate"]
        std_gr = row["std_grad_rate"]
        med_pell = row["median_pell_share"]
        med_urm = row["median_urm_share"]
        med_sfr = row["median_student_faculty_ratio"]
        med_ret = row["median_retention_rate"]

        med_gr_str = f"{med_gr:.1f}%" if med_gr is not None else "N/A"
        mean_gr_str = f"{mean_gr:.1f}%" if mean_gr is not None else "N/A"
        std_gr_str = f"{std_gr:.1f}" if std_gr is not None else "N/A"
        med_pell_str = f"{med_pell:.1%}" if med_pell is not None else "N/A"
        med_urm_str = f"{med_urm:.1%}" if med_urm is not None else "N/A"
        med_sfr_str = f"{med_sfr:.1f}" if med_sfr is not None else "N/A"
        med_ret_str = f"{med_ret:.1f}%" if med_ret is not None else "N/A"

        print(f"  {label} (n={n}, with grad rate={n_gr}):")
        print(f"    Grad Rate:  median={med_gr_str}, mean={mean_gr_str}, std={std_gr_str}")
        print(f"    Pell Share: median={med_pell_str}")
        print(f"    URM Share:  median={med_urm_str}")
        print(f"    S/F Ratio:  median={med_sfr_str}")
        print(f"    Retention:  median={med_ret_str}")

# INTENT: Compute the public-private gap within each selectivity band to
# directly test the Observable Truth.
# REASONING: Pivoting to wide format (one column per sector) makes it easy
# to compute the gap as Private minus Public. A positive gap confirms the
# Observable Truth that privates have higher grad rates within the same band.
print("\n" + "=" * 60)
print("PUBLIC-PRIVATE GAP ANALYSIS (Within-Band)")
print("=" * 60)

gap_found_all_bands = True
for band in SELECTIVITY_ORDER:
    band_data = result.filter(pl.col("selectivity_band") == band)
    public_row = band_data.filter(pl.col("inst_control") == 1)
    private_row = band_data.filter(pl.col("inst_control") == 2)

    if public_row.height == 0 or private_row.height == 0:
        print(f"\n{band}: SKIPPED (missing sector data)")
        gap_found_all_bands = False
        continue

    pub_med = public_row["median_grad_rate"][0]
    priv_med = private_row["median_grad_rate"][0]
    pub_pell = public_row["median_pell_share"][0]
    priv_pell = private_row["median_pell_share"][0]
    pub_urm = public_row["median_urm_share"][0]
    priv_urm = private_row["median_urm_share"][0]
    pub_n = public_row["n_with_grad_rate"][0]
    priv_n = private_row["n_with_grad_rate"][0]

    if pub_med is not None and priv_med is not None:
        gap = priv_med - pub_med
        print(f"\n{band}:")
        print(f"  Public median grad rate:          {pub_med:.1f}% (n={pub_n})")
        print(f"  Private nonprofit median grad rate:{priv_med:.1f}% (n={priv_n})")
        print(f"  Gap (Private - Public):           {gap:+.1f} pp")

        # Compositional context
        if pub_pell is not None and priv_pell is not None:
            pell_diff = priv_pell - pub_pell
            print(f"  Pell share diff (Priv - Pub):     {pell_diff:+.1%}")
        if pub_urm is not None and priv_urm is not None:
            urm_diff = priv_urm - pub_urm
            print(f"  URM share diff (Priv - Pub):      {urm_diff:+.1%}")

        # Interpret the gap in context
        if gap > 0:
            print(f"  Interpretation: Private nonprofits have HIGHER grad rates (+{gap:.1f}pp)")
        elif gap < 0:
            print(f"  Interpretation: Public institutions have HIGHER grad rates ({gap:+.1f}pp)")
        else:
            print(f"  Interpretation: No gap between sectors")
    else:
        print(f"\n{band}: Insufficient data for gap calculation")
        gap_found_all_bands = False

# --- Validate ---
# CP4 validation: verify the output has the expected structure and plausible values.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

# CP4.1: Output has rows for each selectivity band x sector combination
# REASONING: With 4 bands and 2 sectors, we expect up to 8 rows. Some
# combinations may be sparse (e.g., very few public Highly Selective) but
# should still be present.
expected_combos = len(SELECTIVITY_ORDER) * len(SECTOR_LABELS)
actual_combos = result.shape[0]
combos_ok = actual_combos >= expected_combos - 1  # Allow 1 missing combo for edge cases
print(f"  [{'PASS' if combos_ok else 'FAIL'}] Row count: {actual_combos} "
      f"(expected ~{expected_combos} = {len(SELECTIVITY_ORDER)} bands x {len(SECTOR_LABELS)} sectors)")

# CP4.2: n values sum approximately to the total institutions
# ASSUMES: Each institution appears in exactly one band and one sector
n_sum = result["n"].sum()
n_sum_ok = abs(n_sum - pre_rows) <= 1  # Allow rounding tolerance
print(f"  [{'PASS' if n_sum_ok else 'FAIL'}] n sum: {n_sum:,} (total institutions: {pre_rows:,})")

# CP4.3: Grad rate values are in plausible range (0-100)
med_vals = result["median_grad_rate"].drop_nulls()
if med_vals.len() > 0:
    min_gr = med_vals.min()
    max_gr = med_vals.max()
    range_ok = min_gr >= 0 and max_gr <= 100
    print(f"  [{'PASS' if range_ok else 'FAIL'}] Median grad rate range: {min_gr:.1f} - {max_gr:.1f} (expected 0-100)")
else:
    range_ok = False
    print(f"  [FAIL] No non-null median grad rate values")

mean_vals = result["mean_grad_rate"].drop_nulls()
if mean_vals.len() > 0:
    min_mean = mean_vals.min()
    max_mean = mean_vals.max()
    mean_range_ok = min_mean >= 0 and max_mean <= 100
    print(f"  [{'PASS' if mean_range_ok else 'FAIL'}] Mean grad rate range: {min_mean:.1f} - {max_mean:.1f} (expected 0-100)")
else:
    mean_range_ok = False
    print(f"  [FAIL] No non-null mean grad rate values")

# CP4.4: Pell share and URM share in plausible range (0-1 proportion)
pell_vals = result["median_pell_share"].drop_nulls()
if pell_vals.len() > 0:
    pell_range_ok = pell_vals.min() >= 0 and pell_vals.max() <= 1
    print(f"  [{'PASS' if pell_range_ok else 'FAIL'}] Median Pell share range: "
          f"{pell_vals.min():.3f} - {pell_vals.max():.3f} (expected 0-1)")
else:
    pell_range_ok = True  # No data is not a failure here
    print(f"  [WARN] No non-null Pell share values")

urm_vals = result["median_urm_share"].drop_nulls()
if urm_vals.len() > 0:
    urm_range_ok = urm_vals.min() >= 0 and urm_vals.max() <= 1
    print(f"  [{'PASS' if urm_range_ok else 'FAIL'}] Median URM share range: "
          f"{urm_vals.min():.3f} - {urm_vals.max():.3f} (expected 0-1)")
else:
    urm_range_ok = True
    print(f"  [WARN] No non-null URM share values")

# CP4.5: Required columns present in output
required_output_cols = ["selectivity_band", "inst_control", "sector_label", "n",
                        "n_with_grad_rate", "median_grad_rate", "mean_grad_rate",
                        "median_pell_share", "median_urm_share"]
missing_cols = [c for c in required_output_cols if c not in result.columns]
cols_ok = len(missing_cols) == 0
print(f"  [{'PASS' if cols_ok else 'FAIL'}] Required columns: "
      f"{'all present' if cols_ok else f'missing {missing_cols}'}")

all_checks = combos_ok and n_sum_ok and range_ok and mean_range_ok and pell_range_ok and urm_range_ok and cols_ok
assert all_checks, "STOP: CP4 validation failed — see check details above"

# --- Save ---
# Persist the sector comparison results in parquet format for downstream
# consumption by the report-writer and notebook-assembler.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Output shape: {result.shape[0]} rows x {result.shape[1]} cols")

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:03:42
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/07_sector-comparison.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.7: Sector Comparison — Grad Rates by Selectivity & Sector
# ============================================================
# Loaded: 2,528 rows x 26 cols
# 
# Pre-state: 2,528 rows, 26 cols
# 
# Selectivity band distribution:
#   Highly Selective: 73
#   Less Selective/Open: 1,695
#   Moderately Selective: 586
#   Selective: 174
# 
# Institutional control distribution:
#   1 (Public): 852
#   2 (Private nonprofit): 1,676
# 
# Institutions with non-null grad_rate_150pct: 1,796 / 2,528 (71.0%)
# 
# Post-state: 8 rows x 12 cols
# 
# ============================================================
# SECTOR COMPARISON TABLE
# ============================================================
# 
# --- Highly Selective ---
#   Public (n=9, with grad rate=9):
#     Grad Rate:  median=91.9%, mean=89.4%, std=4.6
#     Pell Share: median=15.3%
#     URM Share:  median=18.2%
#     S/F Ratio:  median=13.0
#     Retention:  median=97.0%
#   Private nonprofit (n=64, with grad rate=60):
#     Grad Rate:  median=92.6%, mean=88.4%, std=14.4
#     Pell Share: median=16.7%
#     URM Share:  median=18.6%
#     S/F Ratio:  median=8.0
#     Retention:  median=92.0%
# 
# --- Selective ---
#   Public (n=38, with grad rate=37):
#     Grad Rate:  median=74.6%, mean=65.8%, std=23.0
#     Pell Share: median=38.8%
#     URM Share:  median=31.1%
#     S/F Ratio:  median=17.0
#     Retention:  median=89.0%
#   Private nonprofit (n=136, with grad rate=122):
#     Grad Rate:  median=62.6%, mean=61.7%, std=22.2
#     Pell Share: median=33.6%
#     URM Share:  median=19.6%
#     S/F Ratio:  median=10.0
#     Retention:  median=79.0%
# 
# --- Moderately Selective ---
#   Public (n=160, with grad rate=157):
#     Grad Rate:  median=54.2%, mean=56.2%, std=16.9
#     Pell Share: median=37.5%
#     URM Share:  median=25.8%
#     S/F Ratio:  median=16.0
#     Retention:  median=78.0%
#   Private nonprofit (n=426, with grad rate=407):
#     Grad Rate:  median=60.3%, mean=58.2%, std=17.5
#     Pell Share: median=36.4%
#     URM Share:  median=18.6%
#     S/F Ratio:  median=12.0
#     Retention:  median=75.5%
# 
# --- Less Selective/Open ---
#   Public (n=645, with grad rate=391):
#     Grad Rate:  median=50.5%, mean=49.3%, std=15.4
#     Pell Share: median=36.7%
#     URM Share:  median=23.0%
#     S/F Ratio:  median=17.0
#     Retention:  median=75.0%
#   Private nonprofit (n=1050, with grad rate=613):
#     Grad Rate:  median=57.0%, mean=54.5%, std=19.9
#     Pell Share: median=40.2%
#     URM Share:  median=20.7%
#     S/F Ratio:  median=12.0
#     Retention:  median=75.0%
# 
# ============================================================
# PUBLIC-PRIVATE GAP ANALYSIS (Within-Band)
# ============================================================
# 
# Highly Selective:
#   Public median grad rate:          91.9% (n=9)
#   Private nonprofit median grad rate:92.6% (n=60)
#   Gap (Private - Public):           +0.7 pp
#   Pell share diff (Priv - Pub):     +1.4%
#   URM share diff (Priv - Pub):      +0.3%
#   Interpretation: Private nonprofits have HIGHER grad rates (+0.7pp)
# 
# Selective:
#   Public median grad rate:          74.6% (n=37)
#   Private nonprofit median grad rate:62.6% (n=122)
#   Gap (Private - Public):           -12.0 pp
#   Pell share diff (Priv - Pub):     -5.3%
#   URM share diff (Priv - Pub):      -11.4%
#   Interpretation: Public institutions have HIGHER grad rates (-12.0pp)
# 
# Moderately Selective:
#   Public median grad rate:          54.2% (n=157)
#   Private nonprofit median grad rate:60.3% (n=407)
#   Gap (Private - Public):           +6.1 pp
#   Pell share diff (Priv - Pub):     -1.1%
#   URM share diff (Priv - Pub):      -7.2%
#   Interpretation: Private nonprofits have HIGHER grad rates (+6.1pp)
# 
# Less Selective/Open:
#   Public median grad rate:          50.5% (n=391)
#   Private nonprofit median grad rate:57.0% (n=613)
#   Gap (Private - Public):           +6.5 pp
#   Pell share diff (Priv - Pub):     +3.5%
#   URM share diff (Priv - Pub):      -2.3%
#   Interpretation: Private nonprofits have HIGHER grad rates (+6.5pp)
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] Row count: 8 (expected ~8 = 4 bands x 2 sectors)
#   [PASS] n sum: 2,528 (total institutions: 2,528)
#   [PASS] Median grad rate range: 50.5 - 92.6 (expected 0-100)
#   [PASS] Mean grad rate range: 49.3 - 89.4 (expected 0-100)
#   [PASS] Median Pell share range: 0.153 - 0.402 (expected 0-1)
#   [PASS] Median URM share range: 0.182 - 0.311 (expected 0-1)
#   [PASS] Required columns: all present
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-02-15_sector_comparison.parquet
# Output shape: 8 rows x 12 cols
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
