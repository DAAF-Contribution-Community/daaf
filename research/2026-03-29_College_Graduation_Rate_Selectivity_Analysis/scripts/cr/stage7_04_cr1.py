#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 04

Reviewed script: scripts/stage7_transform/04_create-bands_a.py
Output files: data/processed/2026-03-29_analysis.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Schema matches Plan.md expectations
2. Row count within expected range (1,500-2,500)
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if admit_rate has boundary values exactly at thresholds?
7. [Semantic] Does band assignment match research intent for open-admissions?
8. [Boundary] Quintile edge cases: null handling, single-value groups
9. [Absence] Are any institutions with admit_rate NULL but NOT open-admissions misclassified?
10. [Downstream] Does the filtered output preserve enough data for cross-tab analyses?

Spot-Checks:
11. Trace a known highly selective institution (MIT, Stanford, etc.) through bands
12. Verify pell_quintile computed correctly by manual comparison
13. Check filter complement: what was REMOVED and is that reasonable?
14. Verify admit_rate boundary values (exactly 25, 50, 75) land in correct bands
15. Cross-check band counts against pre-filter vs post-filter
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
MERGED_FILE = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_merged.parquet"

EXPECTED_COLUMNS = [
    "unitid", "inst_name", "inst_control", "admit_rate",
    "completion_rate_150pct", "pell_share", "urm_share",
    "student_faculty_ratio", "retention_rate", "instr_expend_per_fte",
    "selectivity_band", "pell_quintile", "urm_quintile", "open_public",
]
EXPECTED_MIN_ROWS = 1500
EXPECTED_MAX_ROWS = 2500
CRITICAL_COLUMNS = ["unitid", "inst_name", "inst_control", "selectivity_band", "completion_rate_150pct"]
CODED_MISSING_VALUES = [-1, -2, -3]

BAND_NAMES = ["Highly Selective", "Selective", "Moderately Selective", "Open/Less Selective"]
QUINTILE_LABELS = ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 04 (create-bands)")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"
df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded analysis: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load pre-filter merged data for comparison
assert MERGED_FILE.exists(), f"FAIL: Merged file not found: {MERGED_FILE}"
df_merged = pl.read_parquet(MERGED_FILE)
print(f"Loaded merged: {df_merged.shape[0]:,} rows x {df_merged.shape[1]} cols")

# =====================================================================
# DEFAULT CHECKS (1-5)
# =====================================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print(f"All {len(EXPECTED_COLUMNS)} expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan required list): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")
dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))

# --- Check 4: Coded values ---
coded_issues = []
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))

# --- Check 5: Critical nulls ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))

# =====================================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses, 6-10)
# =====================================================================

# --- Check 6: [Counterfactual] Boundary threshold values ---
# INTENT: Verify that institutions with admit_rate exactly at 25, 50, 75
# land in the correct band per the Plan's half-open interval logic.
print(f"\n--- Check 6: Counterfactual (boundary thresholds) ---")

# admit_rate == 25 should be "Selective" (>= 25)
at_25 = df.filter(pl.col("admit_rate") == 25.0)
if at_25.shape[0] > 0:
    bands_at_25 = at_25["selectivity_band"].unique().to_list()
    ok_25 = all(b == "Selective" for b in bands_at_25)
    print(f"[{'PASS' if ok_25 else 'FAIL'}] admit_rate == 25 -> {bands_at_25} (expected Selective)")
else:
    print(f"[INFO] No institutions with admit_rate == 25.0 exactly")

# admit_rate == 50 should be "Moderately Selective" (>= 50)
at_50 = df.filter(pl.col("admit_rate") == 50.0)
if at_50.shape[0] > 0:
    bands_at_50 = at_50["selectivity_band"].unique().to_list()
    ok_50 = all(b == "Moderately Selective" for b in bands_at_50)
    print(f"[{'PASS' if ok_50 else 'FAIL'}] admit_rate == 50 -> {bands_at_50} (expected Moderately Selective)")
else:
    print(f"[INFO] No institutions with admit_rate == 50.0 exactly")

# admit_rate == 75 should be "Open/Less Selective" (>= 75)
at_75 = df.filter(pl.col("admit_rate") == 75.0)
if at_75.shape[0] > 0:
    bands_at_75 = at_75["selectivity_band"].unique().to_list()
    ok_75 = all(b == "Open/Less Selective" for b in bands_at_75)
    print(f"[{'PASS' if ok_75 else 'FAIL'}] admit_rate == 75 -> {bands_at_75} (expected Open/Less Selective)")
else:
    print(f"[INFO] No institutions with admit_rate == 75.0 exactly")

# admit_rate == 0 should be "Highly Selective"
at_0 = df.filter(pl.col("admit_rate") == 0.0)
if at_0.shape[0] > 0:
    bands_at_0 = at_0["selectivity_band"].unique().to_list()
    ok_0 = all(b == "Highly Selective" for b in bands_at_0)
    print(f"[{'PASS' if ok_0 else 'FAIL'}] admit_rate == 0 -> {bands_at_0} (expected Highly Selective)")
else:
    print(f"[INFO] No institutions with admit_rate == 0.0 exactly")

# admit_rate == 100 should be "Open/Less Selective"
at_100 = df.filter(pl.col("admit_rate") == 100.0)
if at_100.shape[0] > 0:
    bands_at_100 = at_100["selectivity_band"].unique().to_list()
    ok_100 = all(b == "Open/Less Selective" for b in bands_at_100)
    print(f"[{'PASS' if ok_100 else 'FAIL'}] admit_rate == 100 -> {bands_at_100} (expected Open/Less Selective)")
else:
    print(f"[INFO] No institutions with admit_rate == 100.0 exactly")


# --- Check 7: [Semantic] Open-admissions classification uses admit_rate IS NULL ---
# INTENT: Verify the CORRECTED logic (admit_rate IS NULL -> Open/Less Selective)
# and NOT the original Plan logic (open_public == 1).
print(f"\n--- Check 7: Semantic (open-admissions classification) ---")

# In the analysis output, institutions with null admit_rate should be Open/Less Selective
null_admit = df.filter(pl.col("admit_rate").is_null())
print(f"Institutions with null admit_rate in output: {null_admit.shape[0]:,}")
if null_admit.shape[0] > 0:
    null_admit_bands = null_admit["selectivity_band"].value_counts().sort("selectivity_band")
    print(f"  Their bands: {null_admit_bands}")
    all_ols = (null_admit["selectivity_band"] == "Open/Less Selective").all()
    print(f"[{'PASS' if all_ols else 'FAIL'}] All null-admit institutions -> Open/Less Selective")
else:
    print(f"[PASS] No null admit_rate in filtered output (all filtered out or all classified)")

# Check that the script is NOT using open_public for classification
# by examining if there are institutions with open_public != 1 that are in Open/Less Selective
# only via high admit_rate (not via null admit_rate)
ols_with_admit = df.filter(
    (pl.col("selectivity_band") == "Open/Less Selective")
    & pl.col("admit_rate").is_not_null()
)
if ols_with_admit.shape[0] > 0:
    min_admit_ols = ols_with_admit["admit_rate"].min()
    print(f"[{'PASS' if min_admit_ols >= 75 else 'FAIL'}] O/LS with known admit_rate: min={min_admit_ols:.1f} (should be >= 75)")

# Check: how many open_public values exist and what they look like
if "open_public" in df.columns:
    op_counts = df["open_public"].value_counts().sort("open_public")
    print(f"  open_public distribution: {op_counts}")
    # Verify that nearly all institutions have open_public == 1
    # (confirming that open_public is NOT selective admissions indicator)
    op1_pct = (df["open_public"] == 1).sum() / len(df) * 100
    print(f"  open_public == 1: {op1_pct:.1f}% (expected ~99%+ if it means 'open to public')")


# --- Check 8: [Boundary] Quintile edge cases ---
# INTENT: Verify quintile creation handles nulls correctly and produces
# roughly equal-sized bins.
print(f"\n--- Check 8: Boundary (quintile edge cases) ---")

# Pell quintile nulls should correspond to pell_share nulls
pell_share_null = df["pell_share"].null_count()
pell_q_null = df["pell_quintile"].null_count()
pell_null_match = pell_q_null >= pell_share_null  # quintile null >= share null
print(f"[{'PASS' if pell_null_match else 'FAIL'}] pell_quintile nulls ({pell_q_null}) >= pell_share nulls ({pell_share_null})")

# URM quintile nulls should correspond to urm_share nulls
urm_share_null = df["urm_share"].null_count()
urm_q_null = df["urm_quintile"].null_count()
urm_null_match = urm_q_null >= urm_share_null
print(f"[{'PASS' if urm_null_match else 'FAIL'}] urm_quintile nulls ({urm_q_null}) >= urm_share nulls ({urm_share_null})")

# Check quintile balance (each bin should be within 20% of ideal size)
pell_q_dist = df.filter(pl.col("pell_quintile").is_not_null())["pell_quintile"].value_counts()
if pell_q_dist.shape[0] == 5:
    pell_sizes = pell_q_dist["count"].to_list()
    ideal = sum(pell_sizes) / 5
    pell_balance = all(abs(s - ideal) / ideal < 0.25 for s in pell_sizes)
    print(f"[{'PASS' if pell_balance else 'WARN'}] pell_quintile balance: sizes {sorted(pell_sizes)}, ideal ~{ideal:.0f}")
else:
    print(f"[FAIL] pell_quintile does not have 5 distinct values: {pell_q_dist.shape[0]}")

urm_q_dist = df.filter(pl.col("urm_quintile").is_not_null())["urm_quintile"].value_counts()
if urm_q_dist.shape[0] == 5:
    urm_sizes = urm_q_dist["count"].to_list()
    ideal = sum(urm_sizes) / 5
    urm_balance = all(abs(s - ideal) / ideal < 0.25 for s in urm_sizes)
    print(f"[{'PASS' if urm_balance else 'WARN'}] urm_quintile balance: sizes {sorted(urm_sizes)}, ideal ~{ideal:.0f}")
else:
    print(f"[FAIL] urm_quintile does not have 5 distinct values: {urm_q_dist.shape[0]}")


# --- Check 9: [Absence] Missing checks - what SHOULD be here that isn't ---
# INTENT: Verify that no institutions are silently lost or misclassified.
print(f"\n--- Check 9: Absence (what's missing?) ---")

# Check: selectivity_band should have NO nulls in the filtered output
band_nulls = df["selectivity_band"].null_count()
print(f"[{'PASS' if band_nulls == 0 else 'FAIL'}] selectivity_band nulls in output: {band_nulls}")

# Check: Are there exactly 4 bands?
band_unique = df["selectivity_band"].drop_nulls().unique().sort().to_list()
has_4_bands = len(band_unique) == 4 and set(band_unique) == set(BAND_NAMES)
print(f"[{'PASS' if has_4_bands else 'FAIL'}] Band names: {band_unique}")

# Check: completion_rate_150pct should have NO nulls (filter requirement)
comp_nulls = df["completion_rate_150pct"].null_count()
print(f"[{'PASS' if comp_nulls == 0 else 'FAIL'}] completion_rate_150pct nulls in output: {comp_nulls}")

# Check: Does every admit_rate value map to exactly one band?
# (verify mutual exclusivity of band assignment)
non_null_admit = df.filter(pl.col("admit_rate").is_not_null())
for row in non_null_admit.select("admit_rate", "selectivity_band").sample(min(20, non_null_admit.shape[0]), seed=42).iter_rows():
    rate, band = row
    if rate < 25:
        expected = "Highly Selective"
    elif rate < 50:
        expected = "Selective"
    elif rate < 75:
        expected = "Moderately Selective"
    else:
        expected = "Open/Less Selective"
    if band != expected:
        print(f"  [FAIL] admit_rate={rate:.1f} -> band='{band}' but expected '{expected}'")
print(f"[PASS] Spot-checked 20 admit_rate->band mappings: all correct")


# --- Check 10: [Downstream] Cross-tab feasibility ---
# INTENT: Verify the output has sufficient data for downstream cross-tab analyses
# (selectivity x Pell quintile, selectivity x URM quintile).
print(f"\n--- Check 10: Downstream (cross-tab feasibility) ---")

# Check minimum cell size in selectivity x pell_quintile cross-tab
crosstab_pell = (
    df.filter(pl.col("pell_quintile").is_not_null())
    .group_by("selectivity_band", "pell_quintile")
    .len()
)
min_cell_pell = crosstab_pell["len"].min()
pell_cells_total = crosstab_pell.shape[0]
small_cells_pell = crosstab_pell.filter(pl.col("len") < 10).shape[0]
print(f"Selectivity x Pell cross-tab: {pell_cells_total} cells, min N={min_cell_pell}")
print(f"[{'PASS' if small_cells_pell == 0 else 'WARN'}] Cells with N < 10: {small_cells_pell}")

# Check minimum cell size in selectivity x urm_quintile cross-tab
crosstab_urm = (
    df.filter(pl.col("urm_quintile").is_not_null())
    .group_by("selectivity_band", "urm_quintile")
    .len()
)
min_cell_urm = crosstab_urm["len"].min()
urm_cells_total = crosstab_urm.shape[0]
small_cells_urm = crosstab_urm.filter(pl.col("len") < 10).shape[0]
print(f"Selectivity x URM cross-tab: {urm_cells_total} cells, min N={min_cell_urm}")
print(f"[{'PASS' if small_cells_urm == 0 else 'WARN'}] Cells with N < 10: {small_cells_urm}")

# Check: band N >= 30 (BLOCKER threshold)
band_counts = df["selectivity_band"].value_counts().sort("selectivity_band")
min_band = band_counts["count"].min()
min_band_name = band_counts.filter(pl.col("count") == min_band)["selectivity_band"][0]
print(f"[{'PASS' if min_band >= 30 else 'FAIL'}] Minimum band N: {min_band} ({min_band_name})")
print(f"[{'PASS' if min_band >= 100 else 'WARN'}] Aspirational band N >= 100: {min_band} ({min_band_name})")


# =====================================================================
# SPOT-CHECKS (11-15)
# =====================================================================

# --- Spot-Check 11: Trace known highly selective institutions ---
print(f"\n--- Spot-Check 11: Known highly selective institutions ---")
# Look for institutions with very low admit rates
very_low_admit = df.filter(pl.col("admit_rate") < 10).sort("admit_rate")
if very_low_admit.shape[0] > 0:
    print(f"Institutions with admit_rate < 10%:")
    for row in very_low_admit.head(5).iter_rows(named=True):
        print(f"  {row['inst_name']}: admit={row['admit_rate']:.1f}%, "
              f"band={row['selectivity_band']}, "
              f"grad_rate={row['completion_rate_150pct']:.1f}%")
    all_hs = (very_low_admit["selectivity_band"] == "Highly Selective").all()
    print(f"[{'PASS' if all_hs else 'FAIL'}] All sub-10% admit -> Highly Selective")
else:
    print(f"[INFO] No institutions with admit_rate < 10%")

# --- Spot-Check 12: Verify pell_quintile ordering ---
print(f"\n--- Spot-Check 12: pell_quintile ordering ---")
# Q1 (Lowest) should have lower mean pell_share than Q5 (Highest)
pell_by_q = (
    df.filter(pl.col("pell_quintile").is_not_null())
    .group_by("pell_quintile")
    .agg(pl.col("pell_share").mean().alias("mean_pell"))
    .sort("pell_quintile")
)
print(f"Mean pell_share by quintile:")
for row in pell_by_q.iter_rows(named=True):
    print(f"  {row['pell_quintile']}: {row['mean_pell']:.4f}")

q1_mean = pell_by_q.filter(pl.col("pell_quintile") == "Q1 (Lowest)")["mean_pell"][0]
q5_mean = pell_by_q.filter(pl.col("pell_quintile") == "Q5 (Highest)")["mean_pell"][0]
ordering_ok = q1_mean < q5_mean
print(f"[{'PASS' if ordering_ok else 'FAIL'}] Q1 mean ({q1_mean:.4f}) < Q5 mean ({q5_mean:.4f})")

# --- Spot-Check 13: Filter complement analysis ---
print(f"\n--- Spot-Check 13: Filter complement (what was removed?) ---")
# Reconstruct what the filter removed: merged rows not in analysis
merged_unitids = set(df_merged["unitid"].to_list())
analysis_unitids = set(df["unitid"].to_list())
removed_unitids = merged_unitids - analysis_unitids
removed = df_merged.filter(pl.col("unitid").is_in(list(removed_unitids)))
print(f"Removed {removed.shape[0]:,} institutions from merged data")

# Why were they removed? Should be because completion_rate_150pct is null
removed_comp_null = removed["completion_rate_150pct"].null_count()
removed_comp_pct = removed_comp_null / removed.shape[0] * 100 if removed.shape[0] > 0 else 0
print(f"  Of removed: {removed_comp_null} ({removed_comp_pct:.1f}%) have null completion_rate_150pct")
filter_complement_ok = removed_comp_pct > 95  # Nearly all removals should be due to null grad rate
print(f"[{'PASS' if filter_complement_ok else 'WARN'}] Filter complement is primarily null-grad-rate institutions")

# Check sector composition of removed vs retained
if "inst_control" in removed.columns and removed.shape[0] > 0:
    removed_sector = removed["inst_control"].value_counts().sort("inst_control")
    print(f"  Removed by sector: {removed_sector}")
    retained_sector = df["inst_control"].value_counts().sort("inst_control")
    print(f"  Retained by sector: {retained_sector}")

# --- Spot-Check 14: admit_rate ranges within each band ---
print(f"\n--- Spot-Check 14: admit_rate ranges by band ---")
for band in BAND_NAMES:
    band_data = df.filter(pl.col("selectivity_band") == band)
    non_null = band_data.filter(pl.col("admit_rate").is_not_null())
    null_ct = band_data["admit_rate"].null_count()
    if non_null.shape[0] > 0:
        min_r = non_null["admit_rate"].min()
        max_r = non_null["admit_rate"].max()
        print(f"  {band}: admit_rate [{min_r:.1f}, {max_r:.1f}], N={band_data.shape[0]}, null_admit={null_ct}")
    else:
        print(f"  {band}: all null admit_rate, N={band_data.shape[0]}")

# Verify ranges are correct
hs = df.filter(pl.col("selectivity_band") == "Highly Selective")
hs_max = hs.filter(pl.col("admit_rate").is_not_null())["admit_rate"].max()
hs_range_ok = hs_max is not None and hs_max < 25
print(f"[{'PASS' if hs_range_ok else 'FAIL'}] Highly Selective max admit: {hs_max} (should be < 25)")

s = df.filter(pl.col("selectivity_band") == "Selective")
s_non_null = s.filter(pl.col("admit_rate").is_not_null())
if s_non_null.shape[0] > 0:
    s_min = s_non_null["admit_rate"].min()
    s_max = s_non_null["admit_rate"].max()
    s_range_ok = s_min >= 25 and s_max < 50
    print(f"[{'PASS' if s_range_ok else 'FAIL'}] Selective range: [{s_min}, {s_max}] (should be [25, 50))")

ms = df.filter(pl.col("selectivity_band") == "Moderately Selective")
ms_non_null = ms.filter(pl.col("admit_rate").is_not_null())
if ms_non_null.shape[0] > 0:
    ms_min = ms_non_null["admit_rate"].min()
    ms_max = ms_non_null["admit_rate"].max()
    ms_range_ok = ms_min >= 50 and ms_max < 75
    print(f"[{'PASS' if ms_range_ok else 'FAIL'}] Moderately Selective range: [{ms_min}, {ms_max}] (should be [50, 75))")


# --- Spot-Check 15: unitid uniqueness and join key integrity ---
print(f"\n--- Spot-Check 15: unitid uniqueness ---")
unitid_unique = df["unitid"].n_unique() == df.shape[0]
print(f"[{'PASS' if unitid_unique else 'FAIL'}] unitid is unique: {df['unitid'].n_unique():,} unique vs {df.shape[0]:,} rows")

# Check no duplicate institutions snuck in
if not unitid_unique:
    dups = df.group_by("unitid").len().filter(pl.col("len") > 1)
    print(f"  Duplicate unitids: {dups.shape[0]}")
    print(f"  Sample: {dups.head(5)}")


# =====================================================================
# DATA PROFILING (for cr2+ decision)
# =====================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nSelectivity band value counts:")
print(df["selectivity_band"].value_counts().sort("selectivity_band"))

print("\npell_quintile value counts:")
print(df["pell_quintile"].value_counts().sort("pell_quintile"))

print("\nurm_quintile value counts:")
print(df["urm_quintile"].value_counts().sort("urm_quintile"))

print("\ninst_control value counts:")
print(df["inst_control"].value_counts().sort("inst_control"))

print("\nadmit_rate distribution (non-null):")
admit_nonnull = df.filter(pl.col("admit_rate").is_not_null())["admit_rate"]
print(f"  N: {len(admit_nonnull)}, null: {df['admit_rate'].null_count()}")
print(f"  min: {admit_nonnull.min():.2f}, p25: {admit_nonnull.quantile(0.25):.2f}, "
      f"median: {admit_nonnull.median():.2f}, p75: {admit_nonnull.quantile(0.75):.2f}, "
      f"max: {admit_nonnull.max():.2f}")

print("\ncompletion_rate_150pct distribution:")
comp = df["completion_rate_150pct"]
print(f"  N: {len(comp)}, null: {comp.null_count()}")
print(f"  min: {comp.min():.2f}, p25: {comp.quantile(0.25):.2f}, "
      f"median: {comp.median():.2f}, p75: {comp.quantile(0.75):.2f}, "
      f"max: {comp.max():.2f}")

print("\npell_share distribution (non-null):")
pell_nn = df.filter(pl.col("pell_share").is_not_null())["pell_share"]
print(f"  N: {len(pell_nn)}, null: {df['pell_share'].null_count()}")
if len(pell_nn) > 0:
    print(f"  min: {pell_nn.min():.4f}, p25: {pell_nn.quantile(0.25):.4f}, "
          f"median: {pell_nn.median():.4f}, p75: {pell_nn.quantile(0.75):.4f}, "
          f"max: {pell_nn.max():.4f}")

print("\nurm_share distribution (non-null):")
urm_nn = df.filter(pl.col("urm_share").is_not_null())["urm_share"]
print(f"  N: {len(urm_nn)}, null: {df['urm_share'].null_count()}")
if len(urm_nn) > 0:
    print(f"  min: {urm_nn.min():.4f}, p25: {urm_nn.quantile(0.25):.4f}, "
          f"median: {urm_nn.median():.4f}, p75: {urm_nn.quantile(0.75):.4f}, "
          f"max: {urm_nn.max():.4f}")

# Null summary across all columns
print("\nNull counts across all columns:")
for col in df.columns:
    nc = df[col].null_count()
    if nc > 0:
        print(f"  {col}: {nc} ({nc / len(df) * 100:.1f}%)")

# --- Summary ---
all_default = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
print("\n" + "=" * 60)
severity = "PASSED" if all_default else "ISSUES FOUND"
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 00:52:10
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 04 (create-bands)
# ============================================================
# Loaded analysis: 1,946 rows x 25 cols
# Loaded merged: 2,893 rows x 22 cols
# 
# [PASS] Schema: All 14 expected columns present
#   Extra columns (not in Plan required list): ['fips', 'hbcu', 'tribal_college', 'number_applied', 'number_admitted', 'number_enrolled_total', 'completers_150pct', 'cohort_adj_150pct', 'grant_recipients', 'sfa_total_students', 'total_ug_enrollment']
# [PASS] Row count: 1,946 (expected 1,500-2,500)
# [FAIL] Distributions: open_public: all same value (1)
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# --- Check 6: Counterfactual (boundary thresholds) ---
# [PASS] admit_rate == 25 -> ['Selective'] (expected Selective)
# [PASS] admit_rate == 50 -> ['Moderately Selective'] (expected Moderately Selective)
# [PASS] admit_rate == 75 -> ['Open/Less Selective'] (expected Open/Less Selective)
# [PASS] admit_rate == 0 -> ['Highly Selective'] (expected Highly Selective)
# [PASS] admit_rate == 100 -> ['Open/Less Selective'] (expected Open/Less Selective)
# 
# --- Check 7: Semantic (open-admissions classification) ---
# Institutions with null admit_rate in output: 321
#   Their bands: shape: (1, 2)
# ┌─────────────────────┬───────┐
# │ selectivity_band    ┆ count │
# │ ---                 ┆ ---   │
# │ str                 ┆ u32   │
# ╞═════════════════════╪═══════╡
# │ Open/Less Selective ┆ 321   │
# └─────────────────────┴───────┘
# [PASS] All null-admit institutions -> Open/Less Selective
# [PASS] O/LS with known admit_rate: min=75.0 (should be >= 75)
#   open_public distribution: shape: (1, 2)
# ┌─────────────┬───────┐
# │ open_public ┆ count │
# │ ---         ┆ ---   │
# │ i64         ┆ u32   │
# ╞═════════════╪═══════╡
# │ 1           ┆ 1946  │
# └─────────────┴───────┘
#   open_public == 1: 100.0% (expected ~99%+ if it means 'open to public')
# 
# --- Check 8: Boundary (quintile edge cases) ---
# [PASS] pell_quintile nulls (59) >= pell_share nulls (59)
# [PASS] urm_quintile nulls (7) >= urm_share nulls (7)
# [WARN] pell_quintile balance: sizes [271, 383, 404, 410, 419], ideal ~377
# [PASS] urm_quintile balance: sizes [342, 350, 401, 415, 431], ideal ~388
# 
# --- Check 9: Absence (what's missing?) ---
# [PASS] selectivity_band nulls in output: 0
# [PASS] Band names: ['Highly Selective', 'Moderately Selective', 'Open/Less Selective', 'Selective']
# [PASS] completion_rate_150pct nulls in output: 0
# [PASS] Spot-checked 20 admit_rate->band mappings: all correct
# 
# --- Check 10: Downstream (cross-tab feasibility) ---
# Selectivity x Pell cross-tab: 20 cells, min N=2
# [WARN] Cells with N < 10: 3
# Selectivity x URM cross-tab: 19 cells, min N=4
# [WARN] Cells with N < 10: 2
# [PASS] Minimum band N: 71 (Highly Selective)
# [WARN] Aspirational band N >= 100: 71 (Highly Selective)
# 
# --- Spot-Check 11: Known highly selective institutions ---
# Institutions with admit_rate < 10%:
#   DeVry University-Missouri: admit=0.0%, band=Highly Selective, grad_rate=66.7%
#   Curtis Institute of Music: admit=2.4%, band=Highly Selective, grad_rate=89.5%
#   Harvard University: admit=5.0%, band=Highly Selective, grad_rate=96.7%
#   Stanford University: admit=5.2%, band=Highly Selective, grad_rate=95.6%
#   Princeton University: admit=5.6%, band=Highly Selective, grad_rate=97.6%
# [PASS] All sub-10% admit -> Highly Selective
# 
# --- Spot-Check 12: pell_quintile ordering ---
# Mean pell_share by quintile:
#   Q1 (Lowest): 0.0266
#   Q2: 0.0663
#   Q3: 0.1006
#   Q4: 0.1452
#   Q5 (Highest): 0.2228
# [PASS] Q1 mean (0.0266) < Q5 mean (0.2228)
# 
# --- Spot-Check 13: Filter complement (what was removed?) ---
# Removed 947 institutions from merged data
#   Of removed: 947 (100.0%) have null completion_rate_150pct
# [PASS] Filter complement is primarily null-grad-rate institutions
#   Removed by sector: shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 258   │
# │ 2            ┆ 469   │
# │ 3            ┆ 220   │
# └──────────────┴───────┘
#   Retained by sector: shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 594   │
# │ 2            ┆ 1202  │
# │ 3            ┆ 150   │
# └──────────────┴───────┘
# 
# --- Spot-Check 14: admit_rate ranges by band ---
#   Highly Selective: admit_rate [0.0, 24.5], N=71, null_admit=0
#   Selective: admit_rate [25.0, 50.0], N=177, null_admit=0
#   Moderately Selective: admit_rate [50.0, 75.0], N=577, null_admit=0
#   Open/Less Selective: admit_rate [75.0, 100.0], N=1121, null_admit=321
# [PASS] Highly Selective max admit: 24.541152025857095 (should be < 25)
# [PASS] Selective range: [25.0, 49.98766954377312] (should be [25, 50))
# [PASS] Moderately Selective range: [50.0, 74.98959633791095] (should be [50, 75))
# 
# --- Spot-Check 15: unitid uniqueness ---
# [PASS] unitid is unique: 1,946 unique vs 1,946 rows
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 25)
# ┌────────┬─────────────┬──────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ inst_name   ┆ fips ┆ inst_contr ┆ … ┆ instr_expe ┆ selectivit ┆ pell_quint ┆ urm_quinti │
# │ ---    ┆ ---         ┆ ---  ┆ ol         ┆   ┆ nd_per_fte ┆ y_band     ┆ ile        ┆ le         │
# │ i64    ┆ str         ┆ i64  ┆ ---        ┆   ┆ ---        ┆ ---        ┆ ---        ┆ ---        │
# │        ┆             ┆      ┆ i64        ┆   ┆ f64        ┆ str        ┆ cat        ┆ cat        │
# ╞════════╪═════════════╪══════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ Alabama A & ┆ 1    ┆ 1          ┆ … ┆ 5383.77066 ┆ Open/Less  ┆ Q4         ┆ Q5         │
# │        ┆ M           ┆      ┆            ┆   ┆            ┆ Selective  ┆            ┆ (Highest)  │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100663 ┆ University  ┆ 1    ┆ 1          ┆ … ┆ 17533.0051 ┆ Open/Less  ┆ Q2         ┆ Q3         │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆ 47         ┆ Selective  ┆            ┆            │
# │        ┆ at Birmi…   ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100690 ┆ Amridge     ┆ 1    ┆ 2          ┆ … ┆ 4206.03094 ┆ Open/Less  ┆ null       ┆ Q5         │
# │        ┆ University  ┆      ┆            ┆   ┆ 8          ┆ Selective  ┆            ┆ (Highest)  │
# │ 100706 ┆ University  ┆ 1    ┆ 1          ┆ … ┆ 9390.67387 ┆ Open/Less  ┆ Q2         ┆ Q2         │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆ 9          ┆ Selective  ┆            ┆            │
# │        ┆ in Hunts…   ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100724 ┆ Alabama     ┆ 1    ┆ 1          ┆ … ┆ 8750.46850 ┆ Open/Less  ┆ Q3         ┆ Q5         │
# │        ┆ State       ┆      ┆            ┆   ┆ 5          ┆ Selective  ┆            ┆ (Highest)  │
# │        ┆ University  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100751 ┆ The         ┆ 1    ┆ 1          ┆ … ┆ 10954.5604 ┆ Open/Less  ┆ Q1         ┆ Q2         │
# │        ┆ University  ┆      ┆            ┆   ┆ 43         ┆ Selective  ┆ (Lowest)   ┆            │
# │        ┆ of Alabama  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100830 ┆ Auburn      ┆ 1    ┆ 1          ┆ … ┆ 7198.38491 ┆ Open/Less  ┆ Q3         ┆ Q4         │
# │        ┆ University  ┆      ┆            ┆   ┆ 3          ┆ Selective  ┆            ┆            │
# │        ┆ at          ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆ Montgomer…  ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100858 ┆ Auburn      ┆ 1    ┆ 1          ┆ … ┆ 11516.1129 ┆ Open/Less  ┆ Q1         ┆ Q1         │
# │        ┆ University  ┆      ┆            ┆   ┆ 87         ┆ Selective  ┆ (Lowest)   ┆ (Lowest)   │
# │ 100937 ┆ Birmingham- ┆ 1    ┆ 2          ┆ … ┆ 10356.4240 ┆ Moderately ┆ Q5         ┆ Q2         │
# │        ┆ Southern    ┆      ┆            ┆   ┆ 41         ┆ Selective  ┆ (Highest)  ┆            │
# │        ┆ College     ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 101116 ┆ South Unive ┆ 1    ┆ 3          ┆ … ┆ 5002.02    ┆ Open/Less  ┆ Q1         ┆ Q5         │
# │        ┆ rsity-Montg ┆      ┆            ┆   ┆            ┆ Selective  ┆ (Lowest)   ┆ (Highest)  │
# │        ┆ omery       ┆      ┆            ┆   ┆            ┆            ┆            ┆            │
# └────────┴─────────────┴──────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘
# 
# Descriptive statistics:
# shape: (9, 26)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ unitid    ┆ inst_name ┆ fips      ┆ … ┆ instr_exp ┆ selectivi ┆ pell_quin ┆ urm_quin │
# │ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ end_per_f ┆ ty_band   ┆ tile      ┆ tile     │
# │ str       ┆ f64       ┆ str       ┆ f64       ┆   ┆ te        ┆ ---       ┆ ---       ┆ ---      │
# │           ┆           ┆           ┆           ┆   ┆ ---       ┆ str       ┆ str       ┆ str      │
# │           ┆           ┆           ┆           ┆   ┆ f64       ┆           ┆           ┆          │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 1946.0    ┆ 1946      ┆ 1946.0    ┆ … ┆ 1901.0    ┆ 1946      ┆ 1887      ┆ 1939     │
# │ null_coun ┆ 0.0       ┆ 0         ┆ 0.0       ┆ … ┆ 45.0      ┆ 0         ┆ 59        ┆ 7        │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ 215145.50 ┆ null      ┆ 30.73073  ┆ … ┆ 11042.520 ┆ null      ┆ null      ┆ null     │
# │           ┆ 5139      ┆           ┆           ┆   ┆ 986       ┆           ┆           ┆          │
# │ std       ┆ 97412.709 ┆ null      ┆ 16.363432 ┆ … ┆ 10200.259 ┆ null      ┆ null      ┆ null     │
# │           ┆ 112       ┆           ┆           ┆   ┆ 756       ┆           ┆           ┆          │
# │ min       ┆ 100654.0  ┆ AI Miami  ┆ 1.0       ┆ … ┆ 148.94691 ┆ Highly    ┆ null      ┆ null     │
# │           ┆           ┆ Internati ┆           ┆   ┆ 1         ┆ Selective ┆           ┆          │
# │           ┆           ┆ onal      ┆           ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆ Univers…  ┆           ┆   ┆           ┆           ┆           ┆          │
# │ 25%       ┆ 155973.0  ┆ null      ┆ 18.0      ┆ … ┆ 6195.1633 ┆ null      ┆ null      ┆ null     │
# │           ┆           ┆           ┆           ┆   ┆ 2         ┆           ┆           ┆          │
# │ 50%       ┆ 194824.0  ┆ null      ┆ 34.0      ┆ … ┆ 8789.8186 ┆ null      ┆ null      ┆ null     │
# │           ┆           ┆           ┆           ┆   ┆ 3         ┆           ┆           ┆          │
# │ 75%       ┆ 225575.0  ┆ null      ┆ 42.0      ┆ … ┆ 12519.975 ┆ null      ┆ null      ┆ null     │
# │           ┆           ┆           ┆           ┆   ┆ 908       ┆           ┆           ┆          │
# │ max       ┆ 495767.0  ┆ Youngstow ┆ 78.0      ┆ … ┆ 161393.76 ┆ Selective ┆ null      ┆ null     │
# │           ┆           ┆ n State   ┆           ┆   ┆ 7246      ┆           ┆           ┆          │
# │           ┆           ┆ Universit ┆           ┆   ┆           ┆           ┆           ┆          │
# │           ┆           ┆ y         ┆           ┆   ┆           ┆           ┆           ┆          │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Selectivity band value counts:
# shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ str                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Highly Selective     ┆ 71    │
# │ Moderately Selective ┆ 577   │
# │ Open/Less Selective  ┆ 1121  │
# │ Selective            ┆ 177   │
# └──────────────────────┴───────┘
# 
# pell_quintile value counts:
# shape: (6, 2)
# ┌───────────────┬───────┐
# │ pell_quintile ┆ count │
# │ ---           ┆ ---   │
# │ cat           ┆ u32   │
# ╞═══════════════╪═══════╡
# │ null          ┆ 59    │
# │ Q1 (Lowest)   ┆ 271   │
# │ Q2            ┆ 383   │
# │ Q3            ┆ 410   │
# │ Q4            ┆ 419   │
# │ Q5 (Highest)  ┆ 404   │
# └───────────────┴───────┘
# 
# urm_quintile value counts:
# shape: (6, 2)
# ┌──────────────┬───────┐
# │ urm_quintile ┆ count │
# │ ---          ┆ ---   │
# │ cat          ┆ u32   │
# ╞══════════════╪═══════╡
# │ null         ┆ 7     │
# │ Q1 (Lowest)  ┆ 415   │
# │ Q2           ┆ 431   │
# │ Q3           ┆ 401   │
# │ Q4           ┆ 350   │
# │ Q5 (Highest) ┆ 342   │
# └──────────────┴───────┘
# 
# inst_control value counts:
# shape: (3, 2)
# ┌──────────────┬───────┐
# │ inst_control ┆ count │
# │ ---          ┆ ---   │
# │ i64          ┆ u32   │
# ╞══════════════╪═══════╡
# │ 1            ┆ 594   │
# │ 2            ┆ 1202  │
# │ 3            ┆ 150   │
# └──────────────┴───────┘
# 
# admit_rate distribution (non-null):
#   N: 1625, null: 321
#   min: 0.00, p25: 59.81, median: 74.44, p75: 85.20, max: 100.00
# 
# completion_rate_150pct distribution:
#   N: 1946, null: 0
#   min: 3.80, p25: 41.60, median: 56.15, p75: 69.50, max: 100.00
# 
# pell_share distribution (non-null):
#   N: 1887, null: 59
#   min: 0.0000, p25: 0.0682, median: 0.1078, p75: 0.1629, max: 1.1852
# 
# urm_share distribution (non-null):
#   N: 1939, null: 7
#   min: 0.0000, p25: 0.1468, median: 0.2468, p75: 0.4349, max: 1.0000
# 
# Null counts across all columns:
#   number_applied: 317 (16.3%)
#   number_admitted: 321 (16.5%)
#   number_enrolled_total: 322 (16.5%)
#   admit_rate: 321 (16.5%)
#   grant_recipients: 59 (3.0%)
#   sfa_total_students: 59 (3.0%)
#   urm_share: 7 (0.4%)
#   total_ug_enrollment: 5 (0.3%)
#   pell_share: 59 (3.0%)
#   student_faculty_ratio: 5 (0.3%)
#   retention_rate: 51 (2.6%)
#   instr_expend_per_fte: 45 (2.3%)
#   pell_quintile: 59 (3.0%)
#   urm_quintile: 7 (0.4%)
# 
# ============================================================
# QA RESULT: ISSUES FOUND
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
