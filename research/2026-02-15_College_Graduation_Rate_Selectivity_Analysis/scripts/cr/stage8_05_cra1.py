#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 05 (QA4a — Statistical Validity)

Reviewed script: scripts/stage8_analysis/03_outperformers.py
Output files: output/analysis/2026-02-15_outperformers.parquet
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan expectations (27 cols = 26 original + performance_flag)
2. Row count preserved (exactly 2,528)
3. No suspicious distributions in performance_flag
4. Coded values properly handled (no -1, -2, -3)
5. No nulls in critical columns (unitid, selectivity_band)

Script-Specific Checks (Five Skeptical Lenses):
6. COUNTERFACTUAL: What if band SD were 0? What if all grad rates in a band were identical?
7. SEMANTIC: Does the classification serve the research question about institutional quality?
8. BOUNDARY: Ceiling effect in Highly Selective band (threshold > 100%)
9. ABSENCE: Are there institutions with non-null grad_rate but null performance_flag?
10. DOWNSTREAM: Will the performance_flag column be usable by viz scripts?

Spot-Checks:
11. Pick a known overperformer and verify its grad_rate > band_median + band_sd
12. Pick a known underperformer and verify its grad_rate < band_median - band_sd
13. Verify "typical" institutions are between thresholds
14. Verify the sum of flagged + null = 2,528
15. Cross-check band statistics by independent computation
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "output" / "analysis" / "2026-02-15_outperformers.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"

EXPECTED_COLUMNS_BASE = [
    "unitid", "year", "inst_name", "inst_control", "institution_level", "hbcu",
    "degree_granting", "urban_centric_locale", "state_abbr", "fips",
    "grad_rate_150pct", "cohort_year", "number_applied", "number_admitted",
    "number_enrolled_total", "admission_rate", "pell_recipients",
    "enrollment_undergrad", "pell_share", "urm_share", "urm_enrollment",
    "student_faculty_ratio", "retention_rate", "selectivity_band",
    "pell_band", "urm_band"
]
EXPECTED_COLUMNS = EXPECTED_COLUMNS_BASE + ["performance_flag"]
EXPECTED_ROWS = 2528
CRITICAL_COLUMNS = ["unitid", "selectivity_band", "year"]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 8 Step 05 (QA4a)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded output: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Also load input for cross-reference
df_input = pl.read_parquet(INPUT_FILE)
print(f"Loaded input: {df_input.shape[0]:,} rows x {df_input.shape[1]} cols")

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if schema_ok:
    print("All expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROWS:,})")

# --- Check 3: Performance flag distribution ---
flag_counts = df["performance_flag"].value_counts().sort("performance_flag")
null_flags = df["performance_flag"].null_count()
print(f"\n[INFO] Performance flag distribution:")
for row in flag_counts.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")
print(f"  null: {null_flags:,}")
total_accounted = flag_counts["count"].sum() + null_flags
dist_ok = total_accounted == EXPECTED_ROWS
print(f"[{'PASS' if dist_ok else 'FAIL'}] Total accounted (flagged + null): {total_accounted:,} == {EXPECTED_ROWS:,}")

# Check that not all are in one flag (QA threshold)
max_flag_count = flag_counts["count"].max()
all_one_flag = max_flag_count == flag_counts["count"].sum()
print(f"[{'PASS' if not all_one_flag else 'FAIL'}] Not all institutions in one flag category")

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        for code in [-1, -2, -3]:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"\n[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
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


# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# ============================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: COUNTERFACTUAL — What if band SD were 0 or near-0? ---
# Recompute band statistics independently to check for edge cases
print("\n--- COUNTERFACTUAL: Band SD edge cases ---")
df_with_grad = df.filter(pl.col("grad_rate_150pct").is_not_null())
band_stats_independent = df_with_grad.group_by("selectivity_band").agg(
    pl.col("grad_rate_150pct").median().alias("median_check"),
    pl.col("grad_rate_150pct").std().alias("sd_check"),
    pl.col("grad_rate_150pct").min().alias("min_check"),
    pl.col("grad_rate_150pct").max().alias("max_check"),
    pl.len().alias("n_check"),
).sort("selectivity_band")

for row in band_stats_independent.iter_rows(named=True):
    band = row["selectivity_band"]
    sd = row["sd_check"]
    n = row["n_check"]
    upper_threshold = row["median_check"] + sd
    lower_threshold = row["median_check"] - sd
    print(f"  {band}: n={n}, median={row['median_check']:.1f}, SD={sd:.2f}")
    print(f"    Thresholds: overperformer > {upper_threshold:.1f}, underperformer < {lower_threshold:.1f}")
    print(f"    Data range: [{row['min_check']:.1f}, {row['max_check']:.1f}]")
    if sd < 1.0:
        print(f"    [WARNING] Very small SD ({sd:.3f}) — thresholds may be too tight")
    if upper_threshold > 100:
        print(f"    [INFO] Ceiling effect: overperformer threshold ({upper_threshold:.1f}%) > 100% — no overperformers possible")
    if lower_threshold < 0:
        print(f"    [INFO] Floor effect: underperformer threshold ({lower_threshold:.1f}%) < 0% — no underperformers possible")

sd_ok = all(
    band_stats_independent.filter(pl.col("selectivity_band") == b)["sd_check"][0] > 0
    for b in band_stats_independent["selectivity_band"].to_list()
)
print(f"\n[{'PASS' if sd_ok else 'FAIL'}] All band SDs > 0 (no degenerate bands)")

# --- Check 7: SEMANTIC — Does the classification serve the research question? ---
print("\n--- SEMANTIC: Research question alignment ---")
# The research question asks about institutional quality vs selectivity.
# The outperformer analysis classifies institutions WITHIN selectivity bands,
# which is exactly the right approach — it controls for selectivity.
# Verify: overperformers and underperformers exist in at least some bands.
bands_with_over = df.filter(pl.col("performance_flag") == "overperformer")["selectivity_band"].n_unique()
bands_with_under = df.filter(pl.col("performance_flag") == "underperformer")["selectivity_band"].n_unique()
print(f"  Bands with overperformers: {bands_with_over}/4")
print(f"  Bands with underperformers: {bands_with_under}/4")
# The Highly Selective band has 0 overperformers due to ceiling effect.
# This is documented in the execution log. Verify:
hs_over = df.filter(
    (pl.col("selectivity_band") == "Highly Selective") &
    (pl.col("performance_flag") == "overperformer")
).shape[0]
print(f"  Highly Selective overperformers: {hs_over} (expected 0 due to ceiling)")
semantic_ok = bands_with_over >= 3 and bands_with_under >= 3
print(f"[{'PASS' if semantic_ok else 'WARN'}] Classification produces meaningful variation across most bands")

# --- Check 8: BOUNDARY — Ceiling effect and edge values ---
print("\n--- BOUNDARY: Ceiling effect and threshold exactness ---")
# Institutions exactly AT the threshold: should they be overperformer or typical?
# The code uses strict inequality: > for overperformer, < for underperformer.
# So exactly AT threshold = typical. This is correct for a classification scheme.
# Verify: no institutions have grad_rate == band_median + band_sd exactly
for band_name in band_stats_independent["selectivity_band"].to_list():
    bstats = band_stats_independent.filter(pl.col("selectivity_band") == band_name)
    median_val = bstats["median_check"][0]
    sd_val = bstats["sd_check"][0]
    upper = median_val + sd_val
    lower = median_val - sd_val

    exact_upper = df.filter(
        (pl.col("selectivity_band") == band_name) &
        (pl.col("grad_rate_150pct") == upper)
    ).shape[0]
    exact_lower = df.filter(
        (pl.col("selectivity_band") == band_name) &
        (pl.col("grad_rate_150pct") == lower)
    ).shape[0]

    if exact_upper > 0 or exact_lower > 0:
        print(f"  {band_name}: {exact_upper} at upper threshold, {exact_lower} at lower threshold (classified as 'typical')")
    else:
        print(f"  {band_name}: No institutions exactly at thresholds")

# Verify graduation rates are bounded 0-100 (or at least non-negative)
grad_min = df["grad_rate_150pct"].drop_nulls().min()
grad_max = df["grad_rate_150pct"].drop_nulls().max()
bounds_ok = grad_min >= 0 and grad_max <= 100
print(f"  grad_rate_150pct range: [{grad_min}, {grad_max}]")
print(f"[{'PASS' if bounds_ok else 'WARN'}] Graduation rates within [0, 100]")

# --- Check 9: ABSENCE — Are there institutions with non-null grad but null flag? ---
print("\n--- ABSENCE: Missing flag for non-null grad rates ---")
non_null_grad_null_flag = df.filter(
    pl.col("grad_rate_150pct").is_not_null() &
    pl.col("performance_flag").is_null()
).shape[0]
absence_ok = non_null_grad_null_flag == 0
print(f"  Institutions with non-null grad but null flag: {non_null_grad_null_flag}")
print(f"[{'PASS' if absence_ok else 'FAIL'}] No non-null grad rates have null performance_flag")

# Also check the converse: null grad_rate should have null flag
null_grad_nonnull_flag = df.filter(
    pl.col("grad_rate_150pct").is_null() &
    pl.col("performance_flag").is_not_null()
).shape[0]
converse_ok = null_grad_nonnull_flag == 0
print(f"  Institutions with null grad but non-null flag: {null_grad_nonnull_flag}")
print(f"[{'PASS' if converse_ok else 'FAIL'}] No null grad rates have non-null performance_flag")

# --- Check 10: DOWNSTREAM — Is performance_flag usable for viz scripts? ---
print("\n--- DOWNSTREAM: performance_flag usability ---")
flag_dtype = df["performance_flag"].dtype
dtype_ok = flag_dtype == pl.String or flag_dtype == pl.Utf8
print(f"  performance_flag dtype: {flag_dtype} ({'PASS' if dtype_ok else 'WARN'} — viz needs string)")

# Check that flag values are consistent strings (no whitespace, no mixed case)
flag_values = df["performance_flag"].drop_nulls().unique().sort().to_list()
print(f"  Unique values: {flag_values}")
no_whitespace = all(v == v.strip() for v in flag_values)
all_lowercase = all(v == v.lower() for v in flag_values)
print(f"  No whitespace issues: {no_whitespace}")
print(f"  All lowercase: {all_lowercase}")
downstream_ok = dtype_ok and no_whitespace and all_lowercase
print(f"[{'PASS' if downstream_ok else 'WARN'}] performance_flag ready for downstream use")


# ============================================================
# SPOT-CHECKS (5 Concrete Verifications)
# ============================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-Check 11: Verify a specific overperformer ---
print("\n--- Spot-Check 11: Verify specific overperformer ---")
overperformers = df.filter(pl.col("performance_flag") == "overperformer").sort("grad_rate_150pct", descending=True)
if overperformers.shape[0] > 0:
    sample_over = overperformers.head(1)
    over_unitid = sample_over["unitid"][0]
    over_name = sample_over["inst_name"][0]
    over_grad = sample_over["grad_rate_150pct"][0]
    over_band = sample_over["selectivity_band"][0]

    # Get band stats
    bstats = band_stats_independent.filter(pl.col("selectivity_band") == over_band)
    band_median = bstats["median_check"][0]
    band_sd = bstats["sd_check"][0]
    threshold = band_median + band_sd

    correctly_classified = over_grad > threshold
    print(f"  Institution: {over_name} (unitid={over_unitid})")
    print(f"  Band: {over_band}, grad_rate={over_grad:.1f}")
    print(f"  Threshold: {band_median:.1f} + {band_sd:.2f} = {threshold:.2f}")
    print(f"  grad_rate ({over_grad:.1f}) > threshold ({threshold:.2f}): {correctly_classified}")
    print(f"[{'PASS' if correctly_classified else 'FAIL'}] Overperformer correctly above threshold")
else:
    print("  No overperformers found — cannot verify")

# --- Spot-Check 12: Verify a specific underperformer ---
print("\n--- Spot-Check 12: Verify specific underperformer ---")
underperformers = df.filter(pl.col("performance_flag") == "underperformer").sort("grad_rate_150pct")
if underperformers.shape[0] > 0:
    sample_under = underperformers.head(1)
    under_unitid = sample_under["unitid"][0]
    under_name = sample_under["inst_name"][0]
    under_grad = sample_under["grad_rate_150pct"][0]
    under_band = sample_under["selectivity_band"][0]

    bstats = band_stats_independent.filter(pl.col("selectivity_band") == under_band)
    band_median = bstats["median_check"][0]
    band_sd = bstats["sd_check"][0]
    threshold = band_median - band_sd

    correctly_classified = under_grad < threshold
    print(f"  Institution: {under_name} (unitid={under_unitid})")
    print(f"  Band: {under_band}, grad_rate={under_grad:.1f}")
    print(f"  Threshold: {band_median:.1f} - {band_sd:.2f} = {threshold:.2f}")
    print(f"  grad_rate ({under_grad:.1f}) < threshold ({threshold:.2f}): {correctly_classified}")
    print(f"[{'PASS' if correctly_classified else 'FAIL'}] Underperformer correctly below threshold")
else:
    print("  No underperformers found — cannot verify")

# --- Spot-Check 13: Verify a typical institution is between thresholds ---
print("\n--- Spot-Check 13: Verify specific typical institution ---")
typicals = df.filter(
    (pl.col("performance_flag") == "typical") &
    (pl.col("grad_rate_150pct").is_not_null())
).sample(1, seed=42)
if typicals.shape[0] > 0:
    sample_typ = typicals.head(1)
    typ_name = sample_typ["inst_name"][0]
    typ_grad = sample_typ["grad_rate_150pct"][0]
    typ_band = sample_typ["selectivity_band"][0]

    bstats = band_stats_independent.filter(pl.col("selectivity_band") == typ_band)
    band_median = bstats["median_check"][0]
    band_sd = bstats["sd_check"][0]
    lower = band_median - band_sd
    upper = band_median + band_sd

    is_between = lower <= typ_grad <= upper
    print(f"  Institution: {typ_name}")
    print(f"  Band: {typ_band}, grad_rate={typ_grad:.1f}")
    print(f"  Thresholds: [{lower:.2f}, {upper:.2f}]")
    print(f"  Within range: {is_between}")
    print(f"[{'PASS' if is_between else 'FAIL'}] Typical institution between thresholds")

# --- Spot-Check 14: Verify total accounting ---
print("\n--- Spot-Check 14: Total accounting ---")
n_over = df.filter(pl.col("performance_flag") == "overperformer").shape[0]
n_under = df.filter(pl.col("performance_flag") == "underperformer").shape[0]
n_typical = df.filter(pl.col("performance_flag") == "typical").shape[0]
n_null = df.filter(pl.col("performance_flag").is_null()).shape[0]
total = n_over + n_under + n_typical + n_null
print(f"  Overperformer: {n_over}")
print(f"  Underperformer: {n_under}")
print(f"  Typical: {n_typical}")
print(f"  Null: {n_null}")
print(f"  Total: {total} (expected {EXPECTED_ROWS})")
accounting_ok = total == EXPECTED_ROWS
print(f"[{'PASS' if accounting_ok else 'FAIL'}] Total accounting matches expected rows")

# Verify counts match execution log
log_over = 231
log_under = 316
log_typical = 1249
log_null = 732
log_match = (n_over == log_over and n_under == log_under and
             n_typical == log_typical and n_null == log_null)
print(f"\n  Execution log match: over={n_over}=={log_over}, under={n_under}=={log_under}, "
      f"typical={n_typical}=={log_typical}, null={n_null}=={log_null}")
print(f"[{'PASS' if log_match else 'FAIL'}] Counts match execution log")

# --- Spot-Check 15: Cross-check band statistics independently ---
print("\n--- Spot-Check 15: Independent band stats verification ---")
# Recompute from the INPUT file (not output) to verify the script computed correctly
df_input_with_grad = df_input.filter(pl.col("grad_rate_150pct").is_not_null())
input_band_stats = df_input_with_grad.group_by("selectivity_band").agg(
    pl.col("grad_rate_150pct").median().alias("median_from_input"),
    pl.col("grad_rate_150pct").std().alias("sd_from_input"),
    pl.len().alias("n_from_input"),
).sort("selectivity_band")

stats_match = True
for row_i in input_band_stats.iter_rows(named=True):
    band = row_i["selectivity_band"]
    out_row = band_stats_independent.filter(pl.col("selectivity_band") == band)
    median_match = abs(row_i["median_from_input"] - out_row["median_check"][0]) < 0.01
    sd_match = abs(row_i["sd_from_input"] - out_row["sd_check"][0]) < 0.01
    n_match = row_i["n_from_input"] == out_row["n_check"][0]
    ok = median_match and sd_match and n_match
    stats_match = stats_match and ok
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {band}: "
          f"median input={row_i['median_from_input']:.2f} vs output={out_row['median_check'][0]:.2f}, "
          f"SD input={row_i['sd_from_input']:.3f} vs output={out_row['sd_check'][0]:.3f}, "
          f"n input={row_i['n_from_input']} vs output={out_row['n_check'][0]}")
print(f"[{'PASS' if stats_match else 'FAIL'}] Band statistics match between input and output")


# ============================================================
# ADDITIONAL: Verify no band stats leak into output
# ============================================================
print("\n" + "=" * 60)
print("ADDITIONAL CHECK: Intermediate columns dropped")
print("=" * 60)
intermediate_cols = ["band_median", "band_sd", "band_mean", "band_min", "band_max", "band_n"]
leaked = [c for c in intermediate_cols if c in df.columns]
leak_ok = len(leaked) == 0
print(f"  Intermediate columns in output: {leaked if leaked else 'None'}")
print(f"[{'PASS' if leak_ok else 'FAIL'}] No intermediate band stats columns leaked into output")


# ============================================================
# ADDITIONAL: Input row preservation
# ============================================================
print("\n" + "=" * 60)
print("ADDITIONAL CHECK: Input data preservation")
print("=" * 60)
# Verify that the 26 original columns are unchanged from input to output
for col in EXPECTED_COLUMNS_BASE:
    if col in df.columns and col in df_input.columns:
        # Check nulls match
        input_nulls = df_input[col].null_count()
        output_nulls = df[col].null_count()
        if input_nulls != output_nulls:
            print(f"  [FAIL] {col}: null count changed from {input_nulls} to {output_nulls}")
        else:
            # Check non-null values for a sample of unitids
            pass
print("  Null counts match for all original columns: checking...")
all_nulls_match = all(
    df_input[col].null_count() == df[col].null_count()
    for col in EXPECTED_COLUMNS_BASE
    if col in df.columns and col in df_input.columns
)
print(f"[{'PASS' if all_nulls_match else 'FAIL'}] All original column null counts preserved")

# Check sort order preservation (unitid order should be same)
input_unitids = df_input["unitid"].to_list()
output_unitids = df["unitid"].to_list()
order_preserved = input_unitids == output_unitids
print(f"[{'PASS' if order_preserved else 'INFO'}] Row order preserved from input to output")


# --- Data Profiling (for cra2 decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows (key columns):")
print(df.select(["unitid", "inst_name", "selectivity_band", "grad_rate_150pct",
                  "performance_flag", "pell_share", "urm_share"]).head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nPerformance flag by selectivity_band:")
cross = (
    df.group_by("selectivity_band", "performance_flag")
    .len()
    .sort("selectivity_band", "performance_flag")
)
print(cross)

print("\nKey column value counts for performance_flag:")
print(df["performance_flag"].value_counts().sort("performance_flag"))

print("\nOverperformer characteristics (mean):")
over_df = df.filter(pl.col("performance_flag") == "overperformer")
for col in ["pell_share", "urm_share", "student_faculty_ratio", "retention_rate"]:
    if col in over_df.columns:
        val = over_df[col].drop_nulls().mean()
        print(f"  {col}: {val:.3f}" if val is not None else f"  {col}: null")

print("\nUnderperformer characteristics (mean):")
under_df = df.filter(pl.col("performance_flag") == "underperformer")
for col in ["pell_share", "urm_share", "student_faculty_ratio", "retention_rate"]:
    if col in under_df.columns:
        val = under_df[col].drop_nulls().mean()
        print(f"  {col}: {val:.3f}" if val is not None else f"  {col}: null")


# --- Summary ---
all_default_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
all_specific_passed = all([sd_ok, semantic_ok, bounds_ok, absence_ok, converse_ok, downstream_ok])
all_spot_passed = all([accounting_ok, log_match, stats_match, leak_ok, all_nulls_match])

all_passed = all_default_passed and all_specific_passed and all_spot_passed
print("\n" + "=" * 60)
severity = "PASSED" if all_passed else "BLOCKER"
print(f"QA4a RESULT: {severity}")
if not all_passed:
    print("  Failed checks:")
    checks = {
        "schema": schema_ok, "rows": rows_ok, "distribution": dist_ok,
        "coded_values": coded_ok, "critical_nulls": nulls_ok,
        "band_sd": sd_ok, "semantic": semantic_ok, "bounds": bounds_ok,
        "absence": absence_ok, "converse": converse_ok, "downstream": downstream_ok,
        "accounting": accounting_ok, "log_match": log_match,
        "stats_match": stats_match, "leak": leak_ok, "null_preservation": all_nulls_match,
    }
    for name, status in checks.items():
        if not status:
            print(f"    - {name}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:55:20
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_05_cra1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 8 Step 05 (QA4a)
# ============================================================
# Loaded output: 2,528 rows x 27 cols
# Loaded input: 2,528 rows x 26 cols
# 
# [PASS] Schema: All expected columns present
# [PASS] Row count: 2,528 (expected exactly 2,528)
# 
# [INFO] Performance flag distribution:
#   None: 732
#   overperformer: 231
#   typical: 1,249
#   underperformer: 316
#   null: 732
# [FAIL] Total accounted (flagged + null): 3,260 == 2,528
# [PASS] Not all institutions in one flag category
# 
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- COUNTERFACTUAL: Band SD edge cases ---
#   Highly Selective: n=69, median=92.3, SD=13.55
#     Thresholds: overperformer > 105.9, underperformer < 78.7
#     Data range: [19.3, 97.6]
#     [INFO] Ceiling effect: overperformer threshold (105.9%) > 100% — no overperformers possible
#   Less Selective/Open: n=1004, median=53.7, SD=18.47
#     Thresholds: overperformer > 72.2, underperformer < 35.2
#     Data range: [3.8, 100.0]
#   Moderately Selective: n=564, median=58.8, SD=17.30
#     Thresholds: overperformer > 76.2, underperformer < 41.5
#     Data range: [7.1, 100.0]
#   Selective: n=159, median=63.6, SD=22.41
#     Thresholds: overperformer > 86.0, underperformer < 41.2
#     Data range: [7.2, 100.0]
# 
# [PASS] All band SDs > 0 (no degenerate bands)
# 
# --- SEMANTIC: Research question alignment ---
#   Bands with overperformers: 3/4
#   Bands with underperformers: 4/4
#   Highly Selective overperformers: 0 (expected 0 due to ceiling)
# [PASS] Classification produces meaningful variation across most bands
# 
# --- BOUNDARY: Ceiling effect and threshold exactness ---
#   Highly Selective: No institutions exactly at thresholds
#   Less Selective/Open: No institutions exactly at thresholds
#   Moderately Selective: No institutions exactly at thresholds
#   Selective: No institutions exactly at thresholds
#   grad_rate_150pct range: [3.8, 100.0]
# [PASS] Graduation rates within [0, 100]
# 
# --- ABSENCE: Missing flag for non-null grad rates ---
#   Institutions with non-null grad but null flag: 0
# [PASS] No non-null grad rates have null performance_flag
#   Institutions with null grad but non-null flag: 0
# [PASS] No null grad rates have non-null performance_flag
# 
# --- DOWNSTREAM: performance_flag usability ---
#   performance_flag dtype: String (PASS — viz needs string)
#   Unique values: ['overperformer', 'typical', 'underperformer']
#   No whitespace issues: True
#   All lowercase: True
# [PASS] performance_flag ready for downstream use
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-Check 11: Verify specific overperformer ---
#   Institution: Haven University (unitid=111045)
#   Band: Less Selective/Open, grad_rate=100.0
#   Threshold: 53.7 + 18.47 = 72.17
#   grad_rate (100.0) > threshold (72.17): True
# [PASS] Overperformer correctly above threshold
# 
# --- Spot-Check 12: Verify specific underperformer ---
#   Institution: Yeshivas Emek Hatorah (unitid=491765)
#   Band: Less Selective/Open, grad_rate=3.8
#   Threshold: 53.7 - 18.47 = 35.23
#   grad_rate (3.8) < threshold (35.23): True
# [PASS] Underperformer correctly below threshold
# 
# --- Spot-Check 13: Verify specific typical institution ---
#   Institution: Schreiner University
#   Band: Less Selective/Open, grad_rate=45.3
#   Thresholds: [35.23, 72.17]
#   Within range: True
# [PASS] Typical institution between thresholds
# 
# --- Spot-Check 14: Total accounting ---
#   Overperformer: 231
#   Underperformer: 316
#   Typical: 1249
#   Null: 732
#   Total: 2528 (expected 2528)
# [PASS] Total accounting matches expected rows
# 
#   Execution log match: over=231==231, under=316==316, typical=1249==1249, null=732==732
# [PASS] Counts match execution log
# 
# --- Spot-Check 15: Independent band stats verification ---
#   [PASS] Highly Selective: median input=92.30 vs output=92.30, SD input=13.553 vs output=13.553, n input=69 vs output=69
#   [PASS] Less Selective/Open: median input=53.70 vs output=53.70, SD input=18.469 vs output=18.469, n input=1004 vs output=1004
#   [PASS] Moderately Selective: median input=58.85 vs output=58.85, SD input=17.302 vs output=17.302, n input=564 vs output=564
#   [PASS] Selective: median input=63.60 vs output=63.60, SD input=22.415 vs output=22.415, n input=159 vs output=159
# [PASS] Band statistics match between input and output
# 
# ============================================================
# ADDITIONAL CHECK: Intermediate columns dropped
# ============================================================
#   Intermediate columns in output: None
# [PASS] No intermediate band stats columns leaked into output
# 
# ============================================================
# ADDITIONAL CHECK: Input data preservation
# ============================================================
#   Null counts match for all original columns: checking...
# [PASS] All original column null counts preserved
# [PASS] Row order preserved from input to output
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows (key columns):
# shape: (10, 7)
# ┌────────┬────────────────┬───────────────┬───────────────┬───────────────┬────────────┬───────────┐
# │ unitid ┆ inst_name      ┆ selectivity_b ┆ grad_rate_150 ┆ performance_f ┆ pell_share ┆ urm_share │
# │ ---    ┆ ---            ┆ and           ┆ pct           ┆ lag           ┆ ---        ┆ ---       │
# │ i64    ┆ str            ┆ ---           ┆ ---           ┆ ---           ┆ f64        ┆ f64       │
# │        ┆                ┆ str           ┆ f64           ┆ str           ┆            ┆           │
# ╞════════╪════════════════╪═══════════════╪═══════════════╪═══════════════╪════════════╪═══════════╡
# │ 100654 ┆ Alabama A & M  ┆ Less Selectiv ┆ 28.1          ┆ underperforme ┆ 0.708227   ┆ 0.916552  │
# │        ┆ University     ┆ e/Open        ┆               ┆ r             ┆            ┆           │
# │ 100663 ┆ University of  ┆ Less Selectiv ┆ 62.4          ┆ typical       ┆ 0.357833   ┆ 0.301845  │
# │        ┆ Alabama at     ┆ e/Open        ┆               ┆               ┆            ┆           │
# │        ┆ Birmi…         ┆               ┆               ┆               ┆            ┆           │
# │ 100690 ┆ Amridge        ┆ Less Selectiv ┆ 66.7          ┆ typical       ┆ 0.90604    ┆ 0.718121  │
# │        ┆ University     ┆ e/Open        ┆               ┆               ┆            ┆           │
# │ 100706 ┆ University of  ┆ Less Selectiv ┆ 60.7          ┆ typical       ┆ 0.255139   ┆ 0.159836  │
# │        ┆ Alabama in     ┆ e/Open        ┆               ┆               ┆            ┆           │
# │        ┆ Hunts…         ┆               ┆               ┆               ┆            ┆           │
# │ 100724 ┆ Alabama State  ┆ Less Selectiv ┆ 28.4          ┆ underperforme ┆ 0.68207    ┆ 0.941063  │
# │        ┆ University     ┆ e/Open        ┆               ┆ r             ┆            ┆           │
# │ 100733 ┆ University of  ┆ Less Selectiv ┆ null          ┆ null          ┆ null       ┆ null      │
# │        ┆ Alabama System ┆ e/Open        ┆               ┆               ┆            ┆           │
# │        ┆ O…             ┆               ┆               ┆               ┆            ┆           │
# │ 100751 ┆ The University ┆ Less Selectiv ┆ 72.2          ┆ overperformer ┆ 0.182033   ┆ 0.158952  │
# │        ┆ of Alabama     ┆ e/Open        ┆               ┆               ┆            ┆           │
# │ 100812 ┆ Athens State   ┆ Less Selectiv ┆ null          ┆ null          ┆ 0.503348   ┆ 0.18006   │
# │        ┆ University     ┆ e/Open        ┆               ┆               ┆            ┆           │
# │ 100830 ┆ Auburn         ┆ Less Selectiv ┆ 35.7          ┆ typical       ┆ 0.519314   ┆ 0.462629  │
# │        ┆ University at  ┆ e/Open        ┆               ┆               ┆            ┆           │
# │        ┆ Montgomer…     ┆               ┆               ┆               ┆            ┆           │
# │ 100858 ┆ Auburn         ┆ Less Selectiv ┆ 80.9          ┆ overperformer ┆ 0.13736    ┆ 0.084636  │
# │        ┆ University     ┆ e/Open        ┆               ┆               ┆            ┆           │
# └────────┴────────────────┴───────────────┴───────────────┴───────────────┴────────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 28)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ inst_name ┆ … ┆ selectivi ┆ pell_band ┆ urm_band  ┆ performan │
# │ ---        ┆ ---        ┆ ---    ┆ ---       ┆   ┆ ty_band   ┆ ---       ┆ ---       ┆ ce_flag   │
# │ str        ┆ f64        ┆ f64    ┆ str       ┆   ┆ ---       ┆ str       ┆ str       ┆ ---       │
# │            ┆            ┆        ┆           ┆   ┆ str       ┆           ┆           ┆ str       │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 2528.0     ┆ 2528.0 ┆ 2528      ┆ … ┆ 2528      ┆ 2010      ┆ 2158      ┆ 1796      │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0         ┆ … ┆ 0         ┆ 518       ┆ 370       ┆ 732       │
# │ mean       ┆ 220569.164 ┆ 2020.0 ┆ null      ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │            ┆ 161        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ std        ┆ 103707.401 ┆ 0.0    ┆ null      ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │            ┆ 134        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ A T Still ┆ … ┆ Highly    ┆ High Pell ┆ High URM  ┆ overperfo │
# │            ┆            ┆        ┆ Universit ┆   ┆ Selective ┆ (40-60%)  ┆ (40-60%)  ┆ rmer      │
# │            ┆            ┆        ┆ y of      ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ Health…   ┆   ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 155089.0   ┆ 2020.0 ┆ null      ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │ 50%        ┆ 196121.0   ┆ 2020.0 ┆ null      ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │ 75%        ┆ 230597.0   ┆ 2020.0 ┆ null      ┆ … ┆ null      ┆ null      ┆ null      ┆ null      │
# │ max        ┆ 496070.0   ┆ 2020.0 ┆ Zaytuna   ┆ … ┆ Selective ┆ Very High ┆ Very High ┆ underperf │
# │            ┆            ┆        ┆ College   ┆   ┆           ┆ Pell      ┆ URM       ┆ ormer     │
# │            ┆            ┆        ┆           ┆   ┆           ┆ (60%+)    ┆ (60%+)    ┆           │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Performance flag by selectivity_band:
# shape: (15, 3)
# ┌──────────────────────┬──────────────────┬─────┐
# │ selectivity_band     ┆ performance_flag ┆ len │
# │ ---                  ┆ ---              ┆ --- │
# │ str                  ┆ str              ┆ u32 │
# ╞══════════════════════╪══════════════════╪═════╡
# │ Highly Selective     ┆ null             ┆ 4   │
# │ Highly Selective     ┆ typical          ┆ 63  │
# │ Highly Selective     ┆ underperformer   ┆ 6   │
# │ Less Selective/Open  ┆ null             ┆ 691 │
# │ Less Selective/Open  ┆ overperformer    ┆ 127 │
# │ …                    ┆ …                ┆ …   │
# │ Moderately Selective ┆ underperformer   ┆ 97  │
# │ Selective            ┆ null             ┆ 15  │
# │ Selective            ┆ overperformer    ┆ 28  │
# │ Selective            ┆ typical          ┆ 97  │
# │ Selective            ┆ underperformer   ┆ 34  │
# └──────────────────────┴──────────────────┴─────┘
# 
# Key column value counts for performance_flag:
# shape: (4, 2)
# ┌──────────────────┬───────┐
# │ performance_flag ┆ count │
# │ ---              ┆ ---   │
# │ str              ┆ u32   │
# ╞══════════════════╪═══════╡
# │ null             ┆ 732   │
# │ overperformer    ┆ 231   │
# │ typical          ┆ 1249  │
# │ underperformer   ┆ 316   │
# └──────────────────┴───────┘
# 
# Overperformer characteristics (mean):
#   pell_share: 0.258
#   urm_share: 0.178
#   student_faculty_ratio: 12.397
#   retention_rate: 85.774
# 
# Underperformer characteristics (mean):
#   pell_share: 0.576
#   urm_share: 0.433
#   student_faculty_ratio: 14.519
#   retention_rate: 61.726
# 
# ============================================================
# QA4a RESULT: BLOCKER
#   Failed checks:
#     - distribution
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
