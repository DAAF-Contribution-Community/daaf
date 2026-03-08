#!/usr/bin/env python3
"""
Stage 8.1: Outperformer/underperformer analysis — identify institutions
that graduate students at rates significantly above or below expectations
given their selectivity band.

Task: outperformers
Wave: 7, Step: 3, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-02-15_analysis.parquet
Output: output/analysis/2026-02-15_outperformers.parquet
Checkpoint: CP3 (analysis validation)
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's analysis specification.
# The outperformer classification uses a +/-1 SD threshold relative to each
# selectivity band's median graduation rate. This threshold balances
# identifying meaningfully different institutions against statistical noise.
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_outperformers.parquet"

# --- Load ---
# Load the final analysis dataset containing selectivity_band, grad_rate_150pct,
# and all institution characteristics needed for profiling.
print("=" * 60)
print("Stage 8.1: Outperformer / Underperformer Analysis")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Columns: {df.columns}")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Document the missingness in grad_rate_150pct since we will filter to non-null
# rows for classification, then rejoin to the full dataset.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
grad_null_count = df["grad_rate_150pct"].null_count()
grad_non_null_count = pre_rows - grad_null_count
print(f"\nPre-state: {pre_rows:,} rows, {len(pre_cols)} cols")
print(f"  grad_rate_150pct: {grad_non_null_count:,} non-null ({grad_null_count:,} null, {grad_null_count/pre_rows*100:.1f}%)")

# Show selectivity band distribution
print(f"\nSelectivity band distribution:")
band_counts = df.group_by("selectivity_band").len().sort("selectivity_band")
for row in band_counts.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

# --- Transform: Compute band statistics ---
# INTENT: For each selectivity_band, compute the median and standard deviation
# of grad_rate_150pct. These statistics form the basis for classifying
# institutions as overperformers (>median+1SD) or underperformers (<median-1SD).
#
# REASONING: Using median (not mean) as the center because graduation rate
# distributions within bands may be skewed — median is more robust to outliers.
# Using 1 SD (not 1.5 or 2) as the threshold because:
#   - Education data often has moderate spread within selectivity bands
#   - 1 SD captures the top/bottom ~15% (under normality), providing enough
#     institutions in each tail for meaningful characterization
#   - More extreme thresholds (2 SD) would yield very few flagged institutions,
#     limiting analytical insight
#
# ASSUMES:
#   - selectivity_band is non-null for all rows (created in prior Stage 7 step)
#   - grad_rate_150pct is on a 0-100 scale (percentage)
#   - Sufficient institutions per band to compute meaningful statistics
#     (context: Highly Selective 73, Selective 174, Mod Selective 586,
#     Less Selective/Open 1695)

# Filter to rows with non-null graduation rates for band statistics
df_with_grad = df.filter(pl.col("grad_rate_150pct").is_not_null())
print(f"\nRows with non-null grad_rate: {df_with_grad.shape[0]:,}")

# Compute band-level statistics
band_stats = df_with_grad.group_by("selectivity_band").agg(
    pl.col("grad_rate_150pct").median().alias("band_median"),
    pl.col("grad_rate_150pct").std().alias("band_sd"),
    pl.col("grad_rate_150pct").mean().alias("band_mean"),
    pl.col("grad_rate_150pct").min().alias("band_min"),
    pl.col("grad_rate_150pct").max().alias("band_max"),
    pl.len().alias("band_n"),
).sort("selectivity_band")

print("\nBand statistics (grad_rate_150pct):")
print(band_stats)

# --- Transform: Classify performance ---
# INTENT: Assign each institution a performance_flag based on where its graduation
# rate falls relative to its selectivity band's median +/- 1 SD. This tests the
# Observable Truth that "some institutions graduate students at rates significantly
# above/below expectations given their selectivity and student body."
#
# REASONING: Joining band stats back to the full dataset (not just filtered)
# so that institutions with null grad rates receive a null performance_flag
# rather than being silently dropped. The full dataset is preserved for
# downstream use.
#
# ASSUMES:
#   - band_sd > 0 for all bands (would be 0 only if all institutions in a band
#     had identical grad rates, which is implausible given the data)

# Join band stats to full dataset
df = df.join(band_stats, on="selectivity_band", how="left")

# Classify performance
# INTENT: Create performance_flag with three categories:
#   - "overperformer": grad_rate > band_median + 1*SD (beats expectations)
#   - "underperformer": grad_rate < band_median - 1*SD (below expectations)
#   - "typical": within 1 SD of band median
#   - null: grad_rate_150pct is null (cannot classify)
df = df.with_columns(
    pl.when(pl.col("grad_rate_150pct").is_null())
    .then(pl.lit(None, dtype=pl.String))
    .when(pl.col("grad_rate_150pct") > (pl.col("band_median") + pl.col("band_sd")))
    .then(pl.lit("overperformer"))
    .when(pl.col("grad_rate_150pct") < (pl.col("band_median") - pl.col("band_sd")))
    .then(pl.lit("underperformer"))
    .otherwise(pl.lit("typical"))
    .alias("performance_flag")
)

# --- Validate: Performance flag distribution ---
# Print count of each flag by selectivity band
print("\n" + "=" * 60)
print("PERFORMANCE FLAG DISTRIBUTION")
print("=" * 60)

flag_by_band = (
    df.filter(pl.col("performance_flag").is_not_null())
    .group_by("selectivity_band", "performance_flag")
    .len()
    .sort("selectivity_band", "performance_flag")
)
print(flag_by_band)

# Also print as percentages within each band
print("\nPercentages within each band:")
for band_name in ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]:
    band_data = flag_by_band.filter(pl.col("selectivity_band") == band_name)
    if band_data.shape[0] == 0:
        continue
    band_total = band_data["len"].sum()
    print(f"\n  {band_name} (n={band_total}):")
    for row in band_data.iter_rows():
        pct = row[2] / band_total * 100
        print(f"    {row[1]}: {row[2]} ({pct:.1f}%)")

# Null flag count (institutions without grad rate)
null_flag_count = df.filter(pl.col("performance_flag").is_null()).shape[0]
print(f"\n  Institutions with null performance_flag (no grad rate): {null_flag_count}")

# --- Characterize: Overperformers vs Underperformers ---
# INTENT: Compare the characteristics of overperformers and underperformers
# to identify what distinguishes institutions that beat expectations from those
# that fall short. This directly informs the research question about factors
# beyond selectivity that predict graduation success.
#
# REASONING: We compare means of key variables (pell_share, urm_share,
# student_faculty_ratio, retention_rate) and inst_control distribution.
# These variables were specifically selected in the Plan because they capture
# different dimensions of institutional character: student body composition
# (pell, urm), resource intensity (student-faculty ratio), and institutional
# effectiveness (retention).
print("\n" + "=" * 60)
print("CHARACTERIZATION OF OVER/UNDERPERFORMERS")
print("=" * 60)

char_cols = ["pell_share", "urm_share", "student_faculty_ratio", "retention_rate"]

for flag_value in ["overperformer", "underperformer", "typical"]:
    subset = df.filter(pl.col("performance_flag") == flag_value)
    n = subset.shape[0]
    print(f"\n--- {flag_value.upper()} (n={n}) ---")

    # Mean characteristics
    for col in char_cols:
        if col in subset.columns:
            non_null = subset[col].drop_nulls()
            if len(non_null) > 0:
                mean_val = non_null.mean()
                median_val = non_null.median()
                print(f"  {col}: mean={mean_val:.3f}, median={median_val:.3f}, n_valid={len(non_null)}")
            else:
                print(f"  {col}: no valid values")

    # inst_control distribution
    if "inst_control" in subset.columns:
        control_dist = subset.group_by("inst_control").len().sort("inst_control")
        print(f"\n  inst_control distribution:")
        for row in control_dist.iter_rows():
            label = "Public" if row[0] == 1 else "Private nonprofit" if row[0] == 2 else f"Code {row[0]}"
            pct = row[1] / n * 100 if n > 0 else 0
            print(f"    {label}: {row[1]} ({pct:.1f}%)")

# --- Characterize by band: Overperformers vs Underperformers ---
# INTENT: Drill down into band-specific characteristics to see if the same
# patterns hold across selectivity levels or if different factors matter
# in different contexts.
print("\n" + "=" * 60)
print("BAND-SPECIFIC CHARACTERIZATION")
print("=" * 60)

for band_name in ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]:
    band_df = df.filter(pl.col("selectivity_band") == band_name)
    print(f"\n{'='*40}")
    print(f"BAND: {band_name}")
    print(f"{'='*40}")

    for flag_value in ["overperformer", "underperformer"]:
        subset = band_df.filter(pl.col("performance_flag") == flag_value)
        n = subset.shape[0]
        if n == 0:
            print(f"\n  {flag_value}: n=0 (skipped)")
            continue
        print(f"\n  {flag_value} (n={n}):")

        # Mean graduation rate
        grad_mean = subset["grad_rate_150pct"].mean()
        print(f"    grad_rate_150pct: mean={grad_mean:.1f}")

        # Key characteristics
        for col in char_cols:
            if col in subset.columns:
                non_null = subset[col].drop_nulls()
                if len(non_null) > 0:
                    print(f"    {col}: mean={non_null.mean():.3f}")

        # Control distribution
        if "inst_control" in subset.columns:
            n_public = subset.filter(pl.col("inst_control") == 1).shape[0]
            n_private = subset.filter(pl.col("inst_control") == 2).shape[0]
            print(f"    public: {n_public} ({n_public/n*100:.1f}%), private: {n_private} ({n_private/n*100:.1f}%)")

# --- INTERPRETATION ---
# INTENT: Synthesize the characterization findings to answer the research
# question: "What distinguishes institutions that beat expectations?"
print("\n" + "=" * 60)
print("INTERPRETATION")
print("=" * 60)

# Compute summary comparison: over vs under
over = df.filter(pl.col("performance_flag") == "overperformer")
under = df.filter(pl.col("performance_flag") == "underperformer")

print(f"\nOverperformers (n={over.shape[0]}) vs Underperformers (n={under.shape[0]}):")
print(f"\nKey differences:")

for col in char_cols:
    over_mean = over[col].drop_nulls().mean() if over[col].drop_nulls().len() > 0 else None
    under_mean = under[col].drop_nulls().mean() if under[col].drop_nulls().len() > 0 else None
    if over_mean is not None and under_mean is not None:
        diff = over_mean - under_mean
        direction = "higher" if diff > 0 else "lower"
        print(f"  {col}: overperformers {over_mean:.3f} vs underperformers {under_mean:.3f} (diff: {diff:+.3f}, {direction})")

# Control distribution comparison
over_public_pct = over.filter(pl.col("inst_control") == 1).shape[0] / over.shape[0] * 100 if over.shape[0] > 0 else 0
under_public_pct = under.filter(pl.col("inst_control") == 1).shape[0] / under.shape[0] * 100 if under.shape[0] > 0 else 0
print(f"  public share: overperformers {over_public_pct:.1f}% vs underperformers {under_public_pct:.1f}%")

# --- Drop intermediate band stats columns before saving ---
# INTENT: Remove the band_median, band_sd, band_mean, band_min, band_max,
# band_n columns that were used for computation but are not needed in the
# output dataset. Keep performance_flag as the key new column.
#
# REASONING: Downstream consumers (visualization, report) need the
# performance_flag but not the intermediate statistics. Keeping the dataset
# lean reduces confusion about which columns are authoritative.
cols_to_drop = ["band_median", "band_sd", "band_mean", "band_min", "band_max", "band_n"]
existing_drop_cols = [c for c in cols_to_drop if c in df.columns]
df_output = df.drop(existing_drop_cols)

# --- Save ---
# Persist the FULL dataset (all 2,528 rows) with the performance_flag column.
# Institutions with null grad_rate_150pct have null performance_flag.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_output.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"Output shape: {df_output.shape[0]:,} rows x {df_output.shape[1]} cols")

# --- CP3 Validation ---
# Checkpoint validation: verify outperformer classification integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: All rows preserved (no rows should be dropped)
rows_preserved = df_output.shape[0] == pre_rows
print(f"  [{'PASS' if rows_preserved else 'FAIL'}] All rows preserved: {df_output.shape[0]:,} == {pre_rows:,}")

# CP3.2: performance_flag exists
has_flag = "performance_flag" in df_output.columns
print(f"  [{'PASS' if has_flag else 'FAIL'}] performance_flag column exists")

# CP3.3: All non-null grad_rate rows have a performance_flag
non_null_grad = df_output.filter(pl.col("grad_rate_150pct").is_not_null())
flagged = non_null_grad.filter(pl.col("performance_flag").is_not_null()).shape[0]
all_flagged = flagged == non_null_grad.shape[0]
print(f"  [{'PASS' if all_flagged else 'FAIL'}] All non-null grad_rate have flag: {flagged:,} / {non_null_grad.shape[0]:,}")

# CP3.4: Null grad_rate rows have null performance_flag
null_grad = df_output.filter(pl.col("grad_rate_150pct").is_null())
null_flag = null_grad.filter(pl.col("performance_flag").is_null()).shape[0]
null_consistent = null_flag == null_grad.shape[0]
print(f"  [{'PASS' if null_consistent else 'FAIL'}] Null grad_rate have null flag: {null_flag:,} / {null_grad.shape[0]:,}")

# CP3.5: Overperformers are above band median + 1 SD
# Re-join band stats temporarily for validation
df_check = df_output.join(band_stats.select("selectivity_band", "band_median", "band_sd"), on="selectivity_band", how="left")
over_check = df_check.filter(pl.col("performance_flag") == "overperformer")
all_over_above = over_check.filter(
    pl.col("grad_rate_150pct") > (pl.col("band_median") + pl.col("band_sd"))
).shape[0] == over_check.shape[0]
print(f"  [{'PASS' if all_over_above else 'FAIL'}] All overperformers above median+1SD: {over_check.shape[0]:,} verified")

# CP3.6: Underperformers are below band median - 1 SD
under_check = df_check.filter(pl.col("performance_flag") == "underperformer")
all_under_below = under_check.filter(
    pl.col("grad_rate_150pct") < (pl.col("band_median") - pl.col("band_sd"))
).shape[0] == under_check.shape[0]
print(f"  [{'PASS' if all_under_below else 'FAIL'}] All underperformers below median-1SD: {under_check.shape[0]:,} verified")

# CP3.7: Flag values are valid
valid_flags = {"overperformer", "underperformer", "typical"}
actual_flags = set(df_output["performance_flag"].drop_nulls().unique().to_list())
flags_valid = actual_flags.issubset(valid_flags)
print(f"  [{'PASS' if flags_valid else 'FAIL'}] Valid flag values: {sorted(actual_flags)}")

assert rows_preserved, "STOP: Row count changed"
assert has_flag, "STOP: Missing performance_flag column"
assert all_flagged, "STOP: Some non-null grad_rate rows lack flag"
assert null_consistent, "STOP: Some null grad_rate rows have non-null flag"
assert all_over_above, "STOP: Overperformer threshold violation"
assert all_under_below, "STOP: Underperformer threshold violation"
assert flags_valid, "STOP: Invalid flag values"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:51:08
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_outperformers.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Outperformer / Underperformer Analysis
# ============================================================
# Loaded: 2,528 rows x 26 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment', 'student_faculty_ratio', 'retention_rate', 'selectivity_band', 'pell_band', 'urm_band']
# 
# Pre-state: 2,528 rows, 26 cols
#   grad_rate_150pct: 1,796 non-null (732 null, 29.0%)
# 
# Selectivity band distribution:
#   Highly Selective: 73
#   Less Selective/Open: 1,695
#   Moderately Selective: 586
#   Selective: 174
# 
# Rows with non-null grad_rate: 1,796
# 
# Band statistics (grad_rate_150pct):
# shape: (4, 7)
# ┌──────────────────────┬─────────────┬───────────┬───────────┬──────────┬──────────┬────────┐
# │ selectivity_band     ┆ band_median ┆ band_sd   ┆ band_mean ┆ band_min ┆ band_max ┆ band_n │
# │ ---                  ┆ ---         ┆ ---       ┆ ---       ┆ ---      ┆ ---      ┆ ---    │
# │ str                  ┆ f64         ┆ f64       ┆ f64       ┆ f64      ┆ f64      ┆ u32    │
# ╞══════════════════════╪═════════════╪═══════════╪═══════════╪══════════╪══════════╪════════╡
# │ Highly Selective     ┆ 92.3        ┆ 13.552898 ┆ 88.544928 ┆ 19.3     ┆ 97.6     ┆ 69     │
# │ Less Selective/Open  ┆ 53.7        ┆ 18.469357 ┆ 52.467032 ┆ 3.8      ┆ 100.0    ┆ 1004   │
# │ Moderately Selective ┆ 58.85       ┆ 17.301891 ┆ 57.665071 ┆ 7.1      ┆ 100.0    ┆ 564    │
# │ Selective            ┆ 63.6        ┆ 22.41471  ┆ 62.654088 ┆ 7.2      ┆ 100.0    ┆ 159    │
# └──────────────────────┴─────────────┴───────────┴───────────┴──────────┴──────────┴────────┘
# 
# ============================================================
# PERFORMANCE FLAG DISTRIBUTION
# ============================================================
# shape: (11, 3)
# ┌──────────────────────┬──────────────────┬─────┐
# │ selectivity_band     ┆ performance_flag ┆ len │
# │ ---                  ┆ ---              ┆ --- │
# │ str                  ┆ str              ┆ u32 │
# ╞══════════════════════╪══════════════════╪═════╡
# │ Highly Selective     ┆ typical          ┆ 63  │
# │ Highly Selective     ┆ underperformer   ┆ 6   │
# │ Less Selective/Open  ┆ overperformer    ┆ 127 │
# │ Less Selective/Open  ┆ typical          ┆ 698 │
# │ Less Selective/Open  ┆ underperformer   ┆ 179 │
# │ …                    ┆ …                ┆ …   │
# │ Moderately Selective ┆ typical          ┆ 391 │
# │ Moderately Selective ┆ underperformer   ┆ 97  │
# │ Selective            ┆ overperformer    ┆ 28  │
# │ Selective            ┆ typical          ┆ 97  │
# │ Selective            ┆ underperformer   ┆ 34  │
# └──────────────────────┴──────────────────┴─────┘
# 
# Percentages within each band:
# 
#   Highly Selective (n=69):
#     typical: 63 (91.3%)
#     underperformer: 6 (8.7%)
# 
#   Selective (n=159):
#     overperformer: 28 (17.6%)
#     typical: 97 (61.0%)
#     underperformer: 34 (21.4%)
# 
#   Moderately Selective (n=564):
#     overperformer: 76 (13.5%)
#     typical: 391 (69.3%)
#     underperformer: 97 (17.2%)
# 
#   Less Selective/Open (n=1004):
#     overperformer: 127 (12.6%)
#     typical: 698 (69.5%)
#     underperformer: 179 (17.8%)
# 
#   Institutions with null performance_flag (no grad rate): 732
# 
# ============================================================
# CHARACTERIZATION OF OVER/UNDERPERFORMERS
# ============================================================
# 
# --- OVERPERFORMER (n=231) ---
#   pell_share: mean=0.258, median=0.209, n_valid=219
#   urm_share: mean=0.178, median=0.140, n_valid=229
#   student_faculty_ratio: mean=12.397, median=12.000, n_valid=229
#   retention_rate: mean=85.774, median=87.000, n_valid=217
# 
#   inst_control distribution:
#     Public: 58 (25.1%)
#     Private nonprofit: 173 (74.9%)
# 
# --- UNDERPERFORMER (n=316) ---
#   pell_share: mean=0.576, median=0.552, n_valid=283
#   urm_share: mean=0.433, median=0.350, n_valid=314
#   student_faculty_ratio: mean=14.519, median=14.000, n_valid=314
#   retention_rate: mean=61.726, median=62.000, n_valid=307
# 
#   inst_control distribution:
#     Public: 102 (32.3%)
#     Private nonprofit: 214 (67.7%)
# 
# --- TYPICAL (n=1249) ---
#   pell_share: mean=0.383, median=0.364, n_valid=1202
#   urm_share: mean=0.268, median=0.203, n_valid=1248
#   student_faculty_ratio: mean=13.857, median=13.500, n_valid=1248
#   retention_rate: mean=76.213, median=77.000, n_valid=1237
# 
#   inst_control distribution:
#     Public: 434 (34.7%)
#     Private nonprofit: 815 (65.3%)
# 
# ============================================================
# BAND-SPECIFIC CHARACTERIZATION
# ============================================================
# 
# ========================================
# BAND: Highly Selective
# ========================================
# 
#   overperformer: n=0 (skipped)
# 
#   underperformer (n=6):
#     grad_rate_150pct: mean=52.3
#     pell_share: mean=0.394
#     urm_share: mean=0.128
#     student_faculty_ratio: mean=12.000
#     retention_rate: mean=68.833
#     public: 0 (0.0%), private: 6 (100.0%)
# 
# ========================================
# BAND: Selective
# ========================================
# 
#   overperformer (n=28):
#     grad_rate_150pct: mean=90.7
#     pell_share: mean=0.214
#     urm_share: mean=0.161
#     student_faculty_ratio: mean=11.286
#     retention_rate: mean=90.333
#     public: 8 (28.6%), private: 20 (71.4%)
# 
#   underperformer (n=34):
#     grad_rate_150pct: mean=30.4
#     pell_share: mean=0.649
#     urm_share: mean=0.557
#     student_faculty_ratio: mean=15.029
#     retention_rate: mean=62.242
#     public: 6 (17.6%), private: 28 (82.4%)
# 
# ========================================
# BAND: Moderately Selective
# ========================================
# 
#   overperformer (n=76):
#     grad_rate_150pct: mean=82.9
#     pell_share: mean=0.204
#     urm_share: mean=0.158
#     student_faculty_ratio: mean=12.882
#     retention_rate: mean=88.289
#     public: 22 (28.9%), private: 54 (71.1%)
# 
#   underperformer (n=97):
#     grad_rate_150pct: mean=30.0
#     pell_share: mean=0.567
#     urm_share: mean=0.439
#     student_faculty_ratio: mean=13.763
#     retention_rate: mean=61.844
#     public: 28 (28.9%), private: 69 (71.1%)
# 
# ========================================
# BAND: Less Selective/Open
# ========================================
# 
#   overperformer (n=127):
#     grad_rate_150pct: mean=81.5
#     pell_share: mean=0.303
#     urm_share: mean=0.193
#     student_faculty_ratio: mean=12.352
#     retention_rate: mean=83.018
#     public: 28 (22.0%), private: 99 (78.0%)
# 
#   underperformer (n=179):
#     grad_rate_150pct: mean=24.6
#     pell_share: mean=0.574
#     urm_share: mean=0.417
#     student_faculty_ratio: mean=14.921
#     retention_rate: mean=61.314
#     public: 68 (38.0%), private: 111 (62.0%)
# 
# ============================================================
# INTERPRETATION
# ============================================================
# 
# Overperformers (n=231) vs Underperformers (n=316):
# 
# Key differences:
#   pell_share: overperformers 0.258 vs underperformers 0.576 (diff: -0.318, lower)
#   urm_share: overperformers 0.178 vs underperformers 0.433 (diff: -0.256, lower)
#   student_faculty_ratio: overperformers 12.397 vs underperformers 14.519 (diff: -2.122, lower)
#   retention_rate: overperformers 85.774 vs underperformers 61.726 (diff: +24.048, higher)
#   public share: overperformers 25.1% vs underperformers 32.3%
# 
# Saved: /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-02-15_outperformers.parquet
# Output shape: 2,528 rows x 27 cols
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] All rows preserved: 2,528 == 2,528
#   [PASS] performance_flag column exists
#   [PASS] All non-null grad_rate have flag: 1,796 / 1,796
#   [PASS] Null grad_rate have null flag: 732 / 732
#   [PASS] All overperformers above median+1SD: 231 verified
#   [PASS] All underperformers below median-1SD: 316 verified
#   [PASS] Valid flag values: ['overperformer', 'typical', 'underperformer']
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
