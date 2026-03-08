#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 04 (create-bands) — Iteration 1

Reviewed script: scripts/stage7_transform/04_create-bands.py
Output files: data/processed/2026-02-15_analysis.parquet
Input files: data/processed/2026-02-15_pre_analysis.parquet

QA Checks (Default):
1. Schema matches Plan expectations (26 cols)
2. Row count exactly 2,528 (unchanged from input)
3. No suspicious distributions (single-value columns, all-zeros)
4. No coded values remain (-1, -2, -3)
5. No nulls in selectivity_band (critical column)

QA Checks (Script-Specific — Five Skeptical Lenses):
6. COUNTERFACTUAL: What if admission_rate had boundary-exact values? Test 0.25, 0.50, 0.75
7. SEMANTIC: Does the band logic serve the research question (not just Plan compliance)?
8. BOUNDARY: Verify null propagation — null admission_rate -> "Less Selective/Open",
   null pell_share -> null pell_band, null urm_share -> null urm_band
9. ABSENCE: Check for missing "UNCLASSIFIED" safety-catch values, verify no original columns dropped
10. DOWNSTREAM: Verify band column types are string (not numeric) for Stage 8 consumption

Spot-Checks:
11. Verify band counts sum to total rows (2,528 for selectivity, non-null total for pell/urm)
12. Cross-check: 869 null admission_rate institutions should be subset of "Less Selective/Open" band
13. Trace a specific institution: pick one known institution and verify its band assignment
14. Verify pell_band null count matches pell_share null count (518)
15. Verify urm_band null count matches urm_share null count (370)
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
INPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_pre_analysis.parquet"

EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "inst_control", "institution_level",
    "hbcu", "degree_granting", "urban_centric_locale", "state_abbr", "fips",
    "grad_rate_150pct", "cohort_year", "number_applied", "number_admitted",
    "number_enrolled_total", "admission_rate", "pell_recipients",
    "enrollment_undergrad", "pell_share", "urm_share", "urm_enrollment",
    "student_faculty_ratio", "retention_rate",
    "selectivity_band", "pell_band", "urm_band"
]
EXPECTED_ROW_COUNT = 2528
EXPECTED_COL_COUNT = 26
CRITICAL_COLUMNS = ["unitid", "selectivity_band"]

# --- Load output and input data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 04 (create-bands)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
df_input = pl.read_parquet(INPUT_FILE)
print(f"Output: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Input:  {df_input.shape[0]:,} rows x {df_input.shape[1]} cols")

max_severity = "PASSED"

def update_severity(current, new):
    order = ["PASSED", "WARNING", "BLOCKER"]
    return new if order.index(new) > order.index(current) else current


# =============================================================================
# DEFAULT CHECKS
# =============================================================================

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0 and len(extra_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema: ", end="")
if len(missing_cols) > 0:
    print(f"Missing columns: {missing_cols}")
    max_severity = update_severity(max_severity, "BLOCKER")
elif len(extra_cols) > 0:
    print(f"Extra unexpected columns: {extra_cols}")
    max_severity = update_severity(max_severity, "WARNING")
else:
    print(f"All {EXPECTED_COL_COUNT} expected columns present, no extras")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = row_count == EXPECTED_ROW_COUNT
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected exactly {EXPECTED_ROW_COUNT:,})")
if not rows_ok:
    max_severity = update_severity(max_severity, "BLOCKER")

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
print(f"[{'PASS' if dist_ok else 'WARN'}] Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))
if not dist_ok:
    max_severity = update_severity(max_severity, "WARNING")

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))
if not coded_ok:
    max_severity = update_severity(max_severity, "BLOCKER")

# --- Check 5: Critical nulls (selectivity_band must have 0 nulls) ---
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: ", end="")
print("None" if nulls_ok else "; ".join(null_issues))
if not nulls_ok:
    max_severity = update_severity(max_severity, "BLOCKER")


# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# =============================================================================

print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# --- Check 6: COUNTERFACTUAL — Boundary value correctness ---
# Test that institutions at EXACT boundary values (0.25, 0.50, 0.75)
# are classified into the correct band. The Plan says >= at the lower bound.
print("\n--- Check 6: COUNTERFACTUAL — Boundary value testing ---")

# For selectivity: admission_rate exactly 0.25 should be "Selective" (>= 0.25)
at_025 = df.filter(pl.col("admission_rate") == 0.25)
at_050 = df.filter(pl.col("admission_rate") == 0.50)
at_075 = df.filter(pl.col("admission_rate") == 0.75)

boundary_ok = True
if len(at_025) > 0:
    bands_at_025 = at_025["selectivity_band"].unique().to_list()
    correct_025 = bands_at_025 == ["Selective"]
    print(f"  admission_rate == 0.25 ({len(at_025)} inst): band(s) = {bands_at_025} — [{'PASS' if correct_025 else 'FAIL'}] Expected: ['Selective']")
    if not correct_025:
        boundary_ok = False
        max_severity = update_severity(max_severity, "BLOCKER")
else:
    print(f"  admission_rate == 0.25: no institutions at exact boundary (cannot test)")

if len(at_050) > 0:
    bands_at_050 = at_050["selectivity_band"].unique().to_list()
    correct_050 = bands_at_050 == ["Moderately Selective"]
    print(f"  admission_rate == 0.50 ({len(at_050)} inst): band(s) = {bands_at_050} — [{'PASS' if correct_050 else 'FAIL'}] Expected: ['Moderately Selective']")
    if not correct_050:
        boundary_ok = False
        max_severity = update_severity(max_severity, "BLOCKER")
else:
    print(f"  admission_rate == 0.50: no institutions at exact boundary (cannot test)")

if len(at_075) > 0:
    bands_at_075 = at_075["selectivity_band"].unique().to_list()
    correct_075 = bands_at_075 == ["Less Selective/Open"]
    print(f"  admission_rate == 0.75 ({len(at_075)} inst): band(s) = {bands_at_075} — [{'PASS' if correct_075 else 'FAIL'}] Expected: ['Less Selective/Open']")
    if not correct_075:
        boundary_ok = False
        max_severity = update_severity(max_severity, "BLOCKER")
else:
    print(f"  admission_rate == 0.75: no institutions at exact boundary (cannot test)")

# Also test pell_share boundaries
for boundary_val, expected_band in [(0.20, "Moderate Pell (20-40%)"), (0.40, "High Pell (40-60%)"), (0.60, "Very High Pell (60%+)")]:
    at_val = df.filter(pl.col("pell_share") == boundary_val)
    if len(at_val) > 0:
        bands_at_val = at_val["pell_band"].unique().to_list()
        correct = bands_at_val == [expected_band]
        print(f"  pell_share == {boundary_val} ({len(at_val)} inst): band(s) = {bands_at_val} — [{'PASS' if correct else 'FAIL'}] Expected: ['{expected_band}']")
        if not correct:
            boundary_ok = False
            max_severity = update_severity(max_severity, "BLOCKER")
    else:
        print(f"  pell_share == {boundary_val}: no institutions at exact boundary")

# Also test urm_share boundaries
for boundary_val, expected_band in [(0.20, "Moderate URM (20-40%)"), (0.40, "High URM (40-60%)"), (0.60, "Very High URM (60%+)")]:
    at_val = df.filter(pl.col("urm_share") == boundary_val)
    if len(at_val) > 0:
        bands_at_val = at_val["urm_band"].unique().to_list()
        correct = bands_at_val == [expected_band]
        print(f"  urm_share == {boundary_val} ({len(at_val)} inst): band(s) = {bands_at_val} — [{'PASS' if correct else 'FAIL'}] Expected: ['{expected_band}']")
        if not correct:
            boundary_ok = False
            max_severity = update_severity(max_severity, "BLOCKER")
    else:
        print(f"  urm_share == {boundary_val}: no institutions at exact boundary")

print(f"  Overall boundary check: [{'PASS' if boundary_ok else 'FAIL'}]")


# --- Check 7: SEMANTIC — Does band logic serve the research question? ---
# The research question asks about the relationship between selectivity and
# graduation rates. The bands should create meaningful analytical groups where
# graduation rates differ across bands.
print("\n--- Check 7: SEMANTIC — Do bands create analytically useful groups? ---")

semantic_ok = True
# Check that selectivity bands have meaningfully different grad rate distributions
grad_by_sel = (
    df.filter(pl.col("grad_rate_150pct").is_not_null())
    .group_by("selectivity_band")
    .agg([
        pl.col("grad_rate_150pct").median().alias("median_grad"),
        pl.col("grad_rate_150pct").count().alias("n"),
    ])
    .sort("median_grad", descending=True)
)
print("  Graduation rate by selectivity band (median):")
for row in grad_by_sel.iter_rows(named=True):
    print(f"    {row['selectivity_band']:25s}: median={row['median_grad']:.1f}%, n={row['n']}")

# The bands should show a gradient — higher selectivity = higher grad rate
medians = grad_by_sel.sort("selectivity_band")["median_grad"].to_list()
band_names = grad_by_sel.sort("selectivity_band")["selectivity_band"].to_list()
# Highly Selective should have the highest median grad rate
highly_sel = grad_by_sel.filter(pl.col("selectivity_band") == "Highly Selective")["median_grad"][0]
less_sel = grad_by_sel.filter(pl.col("selectivity_band") == "Less Selective/Open")["median_grad"][0]
if highly_sel > less_sel:
    print(f"  [PASS] Highly Selective median ({highly_sel:.1f}%) > Less Selective/Open ({less_sel:.1f}%) — confirms bands reflect selectivity gradient")
else:
    print(f"  [WARN] Highly Selective median ({highly_sel:.1f}%) <= Less Selective/Open ({less_sel:.1f}%) — bands may not reflect selectivity gradient")
    semantic_ok = False
    max_severity = update_severity(max_severity, "WARNING")


# --- Check 8: BOUNDARY — Null propagation correctness ---
print("\n--- Check 8: BOUNDARY — Null propagation ---")

null_prop_ok = True

# selectivity_band: null admission_rate -> "Less Selective/Open" (NOT null band)
null_ar_count = df.filter(pl.col("admission_rate").is_null()).shape[0]
null_ar_in_less_sel = df.filter(
    pl.col("admission_rate").is_null() & (pl.col("selectivity_band") == "Less Selective/Open")
).shape[0]
sel_null_correct = null_ar_count == null_ar_in_less_sel
print(f"  Null admission_rate -> 'Less Selective/Open': {null_ar_in_less_sel}/{null_ar_count} — [{'PASS' if sel_null_correct else 'FAIL'}]")
if not sel_null_correct:
    null_prop_ok = False
    max_severity = update_severity(max_severity, "BLOCKER")

# pell_band: null pell_share -> null pell_band
null_ps_count = df.filter(pl.col("pell_share").is_null()).shape[0]
null_pb_count = df["pell_band"].null_count()
pell_null_correct = null_ps_count == null_pb_count
print(f"  Null pell_share ({null_ps_count}) -> null pell_band ({null_pb_count}) — [{'PASS' if pell_null_correct else 'FAIL'}]")
if not pell_null_correct:
    null_prop_ok = False
    max_severity = update_severity(max_severity, "BLOCKER")

# urm_band: null urm_share -> null urm_band
null_us_count = df.filter(pl.col("urm_share").is_null()).shape[0]
null_ub_count = df["urm_band"].null_count()
urm_null_correct = null_us_count == null_ub_count
print(f"  Null urm_share ({null_us_count}) -> null urm_band ({null_ub_count}) — [{'PASS' if urm_null_correct else 'FAIL'}]")
if not urm_null_correct:
    null_prop_ok = False
    max_severity = update_severity(max_severity, "BLOCKER")

# Cross-check: verify null pell_share count matches expectation (518)
pell_null_expected = 518
urm_null_expected = 370
pell_null_match = null_ps_count == pell_null_expected
urm_null_match = null_us_count == urm_null_expected
print(f"  Pell null count {null_ps_count} matches expected {pell_null_expected} — [{'PASS' if pell_null_match else 'WARN'}]")
print(f"  URM null count {null_us_count} matches expected {urm_null_expected} — [{'PASS' if urm_null_match else 'WARN'}]")
if not pell_null_match or not urm_null_match:
    max_severity = update_severity(max_severity, "WARNING")


# --- Check 9: ABSENCE — What's NOT there that should/shouldn't be ---
print("\n--- Check 9: ABSENCE — Missing or unexpected values ---")

absence_ok = True

# No "UNCLASSIFIED" values in selectivity_band (safety catch should never trigger)
unclassified = df.filter(pl.col("selectivity_band") == "UNCLASSIFIED").shape[0]
print(f"  UNCLASSIFIED in selectivity_band: {unclassified} — [{'PASS' if unclassified == 0 else 'FAIL'}]")
if unclassified > 0:
    absence_ok = False
    max_severity = update_severity(max_severity, "BLOCKER")

# All 23 original columns from input should still be present and unchanged
input_cols = df_input.columns
missing_original = [c for c in input_cols if c not in df.columns]
print(f"  All {len(input_cols)} original columns preserved: [{'PASS' if len(missing_original) == 0 else 'FAIL'}]")
if len(missing_original) > 0:
    print(f"    Missing: {missing_original}")
    absence_ok = False
    max_severity = update_severity(max_severity, "BLOCKER")

# Check that band labels are EXACTLY the expected set (no typos, no extra labels)
expected_sel_labels = {"Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"}
actual_sel_labels = set(df["selectivity_band"].unique().to_list())
sel_labels_exact = actual_sel_labels == expected_sel_labels
print(f"  Selectivity labels exactly match Plan: [{'PASS' if sel_labels_exact else 'FAIL'}] {sorted(actual_sel_labels)}")
if not sel_labels_exact:
    absence_ok = False
    max_severity = update_severity(max_severity, "BLOCKER")


# --- Check 10: DOWNSTREAM — Band column types for Stage 8 ---
print("\n--- Check 10: DOWNSTREAM — Band column types for Stage 8 consumption ---")

downstream_ok = True
for band_col in ["selectivity_band", "pell_band", "urm_band"]:
    col_type = df[band_col].dtype
    is_string = col_type == pl.String
    print(f"  {band_col}: type={col_type} — [{'PASS' if is_string else 'FAIL'}] (expected String)")
    if not is_string:
        downstream_ok = False
        max_severity = update_severity(max_severity, "BLOCKER")


# =============================================================================
# SPOT-CHECKS
# =============================================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Band counts sum to total rows ---
print("\n--- Spot-check 11: Band count summation ---")
sel_counts = df["selectivity_band"].value_counts()
sel_total = sel_counts["count"].sum()
sel_sum_ok = sel_total == EXPECTED_ROW_COUNT
print(f"  selectivity_band total: {sel_total} (expected {EXPECTED_ROW_COUNT}) — [{'PASS' if sel_sum_ok else 'FAIL'}]")
if not sel_sum_ok:
    max_severity = update_severity(max_severity, "BLOCKER")

pell_non_null = df.filter(pl.col("pell_band").is_not_null()).shape[0]
pell_null = df["pell_band"].null_count()
pell_sum_ok = (pell_non_null + pell_null) == EXPECTED_ROW_COUNT
print(f"  pell_band non-null ({pell_non_null}) + null ({pell_null}) = {pell_non_null + pell_null} (expected {EXPECTED_ROW_COUNT}) — [{'PASS' if pell_sum_ok else 'FAIL'}]")

urm_non_null = df.filter(pl.col("urm_band").is_not_null()).shape[0]
urm_null = df["urm_band"].null_count()
urm_sum_ok = (urm_non_null + urm_null) == EXPECTED_ROW_COUNT
print(f"  urm_band non-null ({urm_non_null}) + null ({urm_null}) = {urm_non_null + urm_null} (expected {EXPECTED_ROW_COUNT}) — [{'PASS' if urm_sum_ok else 'FAIL'}]")


# --- Spot-check 12: 869 null admission_rate institutions in "Less Selective/Open" ---
print("\n--- Spot-check 12: Cross-check null admission_rate in 'Less Selective/Open' ---")
null_ar_total = df.filter(pl.col("admission_rate").is_null()).shape[0]
less_sel_total = df.filter(pl.col("selectivity_band") == "Less Selective/Open").shape[0]
nonnull_ar_in_less_sel = df.filter(
    pl.col("admission_rate").is_not_null() & (pl.col("selectivity_band") == "Less Selective/Open")
).shape[0]
print(f"  Null admission_rate: {null_ar_total}")
print(f"  'Less Selective/Open' total: {less_sel_total}")
print(f"  Non-null admission_rate in 'Less Selective/Open': {nonnull_ar_in_less_sel}")
print(f"  Null admission_rate portion of 'Less Selective/Open': {null_ar_total}")
expected_ls = null_ar_total + nonnull_ar_in_less_sel
composition_ok = expected_ls == less_sel_total
print(f"  {null_ar_total} (null AR) + {nonnull_ar_in_less_sel} (AR >= 0.75) = {expected_ls} == {less_sel_total} — [{'PASS' if composition_ok else 'FAIL'}]")
if not composition_ok:
    max_severity = update_severity(max_severity, "BLOCKER")

# Verify the non-null AR in Less Selective/Open are all >= 0.75
if nonnull_ar_in_less_sel > 0:
    min_ar_in_ls = df.filter(
        pl.col("admission_rate").is_not_null() & (pl.col("selectivity_band") == "Less Selective/Open")
    )["admission_rate"].min()
    ar_threshold_ok = min_ar_in_ls >= 0.75
    print(f"  Min admission_rate in 'Less Selective/Open' (non-null): {min_ar_in_ls:.4f} — [{'PASS' if ar_threshold_ok else 'FAIL'}] (expected >= 0.75)")
    if not ar_threshold_ok:
        max_severity = update_severity(max_severity, "BLOCKER")


# --- Spot-check 13: Trace a specific institution ---
print("\n--- Spot-check 13: Trace specific institution ---")
# Pick a well-known institution: Harvard (unitid ~166027) or similar
# Let's find a few institutions with known characteristics
sample_inst = df.filter(pl.col("inst_name").str.contains("(?i)harvard"))
if len(sample_inst) > 0:
    inst = sample_inst.row(0, named=True)
    print(f"  Institution: {inst['inst_name']} (unitid={inst['unitid']})")
    print(f"    admission_rate: {inst['admission_rate']}")
    print(f"    selectivity_band: {inst['selectivity_band']}")
    # Harvard's admission rate is typically < 5%, so should be "Highly Selective"
    if inst['admission_rate'] is not None and inst['admission_rate'] < 0.25:
        harvard_ok = inst['selectivity_band'] == "Highly Selective"
        print(f"    Expected 'Highly Selective' for AR < 0.25 — [{'PASS' if harvard_ok else 'FAIL'}]")
        if not harvard_ok:
            max_severity = update_severity(max_severity, "BLOCKER")
else:
    print("  Harvard not found; trying another well-known institution")
    sample_inst = df.filter(pl.col("inst_name").str.contains("(?i)community"))
    if len(sample_inst) > 0:
        inst = sample_inst.row(0, named=True)
        print(f"  Institution: {inst['inst_name']} (unitid={inst['unitid']})")
        print(f"    admission_rate: {inst['admission_rate']}")
        print(f"    selectivity_band: {inst['selectivity_band']}")
    else:
        print("  No familiar institution found for spot-check")

# Also trace an institution with null admission_rate
null_ar_sample = df.filter(pl.col("admission_rate").is_null()).head(1)
if len(null_ar_sample) > 0:
    inst2 = null_ar_sample.row(0, named=True)
    print(f"\n  Institution with null admission_rate: {inst2['inst_name']} (unitid={inst2['unitid']})")
    print(f"    admission_rate: {inst2['admission_rate']}")
    print(f"    selectivity_band: {inst2['selectivity_band']}")
    null_ar_band_ok = inst2['selectivity_band'] == "Less Selective/Open"
    print(f"    Expected 'Less Selective/Open' — [{'PASS' if null_ar_band_ok else 'FAIL'}]")
    if not null_ar_band_ok:
        max_severity = update_severity(max_severity, "BLOCKER")


# --- Spot-check 14: pell_band null count matches pell_share null count ---
print("\n--- Spot-check 14: pell_band null count matches pell_share null count ---")
ps_null = df["pell_share"].null_count()
pb_null = df["pell_band"].null_count()
pell_null_match = ps_null == pb_null
print(f"  pell_share nulls: {ps_null}, pell_band nulls: {pb_null} — [{'PASS' if pell_null_match else 'FAIL'}]")
if not pell_null_match:
    max_severity = update_severity(max_severity, "WARNING")

# Verify the exact same rows are null in both
pell_null_same_rows = df.filter(
    pl.col("pell_share").is_null() != pl.col("pell_band").is_null()
).shape[0]
pell_rows_ok = pell_null_same_rows == 0
print(f"  Rows where pell_share null != pell_band null: {pell_null_same_rows} — [{'PASS' if pell_rows_ok else 'FAIL'}]")
if not pell_rows_ok:
    max_severity = update_severity(max_severity, "BLOCKER")


# --- Spot-check 15: urm_band null count matches urm_share null count ---
print("\n--- Spot-check 15: urm_band null count matches urm_share null count ---")
us_null = df["urm_share"].null_count()
ub_null = df["urm_band"].null_count()
urm_null_match = us_null == ub_null
print(f"  urm_share nulls: {us_null}, urm_band nulls: {ub_null} — [{'PASS' if urm_null_match else 'FAIL'}]")
if not urm_null_match:
    max_severity = update_severity(max_severity, "WARNING")

urm_null_same_rows = df.filter(
    pl.col("urm_share").is_null() != pl.col("urm_band").is_null()
).shape[0]
urm_rows_ok = urm_null_same_rows == 0
print(f"  Rows where urm_share null != urm_band null: {urm_null_same_rows} — [{'PASS' if urm_rows_ok else 'FAIL'}]")
if not urm_rows_ok:
    max_severity = update_severity(max_severity, "BLOCKER")


# =============================================================================
# ADDITIONAL: Verify original column values unchanged
# =============================================================================

print("\n" + "=" * 60)
print("COLUMN PRESERVATION SPOT-CHECK")
print("=" * 60)

# Sample 5 rows from input and verify their original column values are identical in output
sample_unitids = df_input.sample(5, seed=42)["unitid"].to_list()
for uid in sample_unitids:
    input_row = df_input.filter(pl.col("unitid") == uid)
    output_row = df.filter(pl.col("unitid") == uid)
    if len(input_row) == 0 or len(output_row) == 0:
        print(f"  unitid {uid}: row missing in {'input' if len(input_row) == 0 else 'output'} — [FAIL]")
        max_severity = update_severity(max_severity, "BLOCKER")
        continue
    # Compare all original columns
    mismatches = []
    for col in df_input.columns:
        in_val = input_row[col][0]
        out_val = output_row[col][0]
        # Handle null comparison
        if in_val is None and out_val is None:
            continue
        if in_val != out_val:
            mismatches.append(f"{col}: {in_val} -> {out_val}")
    if mismatches:
        print(f"  unitid {uid}: MISMATCHES: {mismatches} — [FAIL]")
        max_severity = update_severity(max_severity, "BLOCKER")
    else:
        print(f"  unitid {uid}: all {len(df_input.columns)} original columns match — [PASS]")


# =============================================================================
# ADDITIONAL: Thin band check
# =============================================================================

print("\n" + "=" * 60)
print("THIN BAND CHECK (< 10 institutions)")
print("=" * 60)

thin_bands = []
for band_col in ["selectivity_band", "pell_band", "urm_band"]:
    vc = df[band_col].value_counts()
    for row in vc.iter_rows(named=True):
        if row[band_col] is not None and row["count"] < 10:
            thin_bands.append(f"{band_col}='{row[band_col]}': {row['count']} institutions")
            print(f"  [WARN] {band_col}='{row[band_col]}': {row['count']} institutions")

if thin_bands:
    print(f"  {len(thin_bands)} thin band(s) found")
    max_severity = update_severity(max_severity, "WARNING")
else:
    print("  [PASS] All non-null bands have >= 10 institutions")


# =============================================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 10 rows:")
print(df.head(10))

print("\nDescriptive statistics:")
print(df.describe())

print("\nBand column value counts:")
for col in ["selectivity_band", "pell_band", "urm_band"]:
    print(f"\n{col}:")
    print(df[col].value_counts().sort(col))

print("\nBand column cross-tabulation (selectivity x pell_band):")
cross = (
    df.filter(pl.col("pell_band").is_not_null())
    .group_by(["selectivity_band", "pell_band"])
    .agg(pl.count().alias("n"))
    .sort(["selectivity_band", "pell_band"])
)
print(cross)

print("\nAdmission rate summary by selectivity_band:")
ar_summary = (
    df.group_by("selectivity_band")
    .agg([
        pl.col("admission_rate").min().alias("ar_min"),
        pl.col("admission_rate").max().alias("ar_max"),
        pl.col("admission_rate").null_count().alias("ar_nulls"),
        pl.count().alias("n"),
    ])
    .sort("selectivity_band")
)
print(ar_summary)


# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print(f"QA RESULT: {max_severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 21:43:49
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 04 (create-bands)
# ============================================================
# Output: 2,528 rows x 26 cols
# Input:  2,528 rows x 23 cols
# 
# [PASS] Schema: All 26 expected columns present, no extras
# [PASS] Row count: 2,528 (expected exactly 2,528)
# [WARN] Distributions: year: all same value (2020); institution_level: all same value (4); cohort_year: all same value (2015)
# [PASS] Coded values: None remain
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# --- Check 6: COUNTERFACTUAL — Boundary value testing ---
#   admission_rate == 0.25 (2 inst): band(s) = ['Selective'] — [PASS] Expected: ['Selective']
#   admission_rate == 0.50 (5 inst): band(s) = ['Moderately Selective'] — [PASS] Expected: ['Moderately Selective']
#   admission_rate == 0.75 (4 inst): band(s) = ['Less Selective/Open'] — [PASS] Expected: ['Less Selective/Open']
#   pell_share == 0.2 (2 inst): band(s) = ['Moderate Pell (20-40%)'] — [PASS] Expected: ['Moderate Pell (20-40%)']
#   pell_share == 0.4: no institutions at exact boundary
#   pell_share == 0.6 (2 inst): band(s) = ['Very High Pell (60%+)'] — [PASS] Expected: ['Very High Pell (60%+)']
#   urm_share == 0.2 (2 inst): band(s) = ['Moderate URM (20-40%)'] — [PASS] Expected: ['Moderate URM (20-40%)']
#   urm_share == 0.4: no institutions at exact boundary
#   urm_share == 0.6: no institutions at exact boundary
#   Overall boundary check: [PASS]
# 
# --- Check 7: SEMANTIC — Do bands create analytically useful groups? ---
#   Graduation rate by selectivity band (median):
#     Highly Selective         : median=92.3%, n=69
#     Selective                : median=63.6%, n=159
#     Moderately Selective     : median=58.8%, n=564
#     Less Selective/Open      : median=53.7%, n=1004
#   [PASS] Highly Selective median (92.3%) > Less Selective/Open (53.7%) — confirms bands reflect selectivity gradient
# 
# --- Check 8: BOUNDARY — Null propagation ---
#   Null admission_rate -> 'Less Selective/Open': 869/869 — [PASS]
#   Null pell_share (518) -> null pell_band (518) — [PASS]
#   Null urm_share (370) -> null urm_band (370) — [PASS]
#   Pell null count 518 matches expected 518 — [PASS]
#   URM null count 370 matches expected 370 — [PASS]
# 
# --- Check 9: ABSENCE — Missing or unexpected values ---
#   UNCLASSIFIED in selectivity_band: 0 — [PASS]
#   All 23 original columns preserved: [PASS]
#   Selectivity labels exactly match Plan: [PASS] ['Highly Selective', 'Less Selective/Open', 'Moderately Selective', 'Selective']
# 
# --- Check 10: DOWNSTREAM — Band column types for Stage 8 consumption ---
#   selectivity_band: type=String — [PASS] (expected String)
#   pell_band: type=String — [PASS] (expected String)
#   urm_band: type=String — [PASS] (expected String)
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# --- Spot-check 11: Band count summation ---
#   selectivity_band total: 2528 (expected 2528) — [PASS]
#   pell_band non-null (2010) + null (518) = 2528 (expected 2528) — [PASS]
#   urm_band non-null (2158) + null (370) = 2528 (expected 2528) — [PASS]
# 
# --- Spot-check 12: Cross-check null admission_rate in 'Less Selective/Open' ---
#   Null admission_rate: 869
#   'Less Selective/Open' total: 1695
#   Non-null admission_rate in 'Less Selective/Open': 826
#   Null admission_rate portion of 'Less Selective/Open': 869
#   869 (null AR) + 826 (AR >= 0.75) = 1695 == 1695 — [PASS]
#   Min admission_rate in 'Less Selective/Open' (non-null): 0.7500 — [PASS] (expected >= 0.75)
# 
# --- Spot-check 13: Trace specific institution ---
#   Institution: Harvard University (unitid=166027)
#     admission_rate: 0.05006459948320414
#     selectivity_band: Highly Selective
#     Expected 'Highly Selective' for AR < 0.25 — [PASS]
# 
#   Institution with null admission_rate: Amridge University (unitid=100690)
#     admission_rate: None
#     selectivity_band: Less Selective/Open
#     Expected 'Less Selective/Open' — [PASS]
# 
# --- Spot-check 14: pell_band null count matches pell_share null count ---
#   pell_share nulls: 518, pell_band nulls: 518 — [PASS]
#   Rows where pell_share null != pell_band null: 0 — [PASS]
# 
# --- Spot-check 15: urm_band null count matches urm_share null count ---
#   urm_share nulls: 370, urm_band nulls: 370 — [PASS]
#   Rows where urm_share null != urm_band null: 0 — [PASS]
# 
# ============================================================
# COLUMN PRESERVATION SPOT-CHECK
# ============================================================
#   unitid 239424: all 23 original columns match — [PASS]
#   unitid 166665: all 23 original columns match — [PASS]
#   unitid 491622: all 23 original columns match — [PASS]
#   unitid 220862: all 23 original columns match — [PASS]
#   unitid 236896: all 23 original columns match — [PASS]
# 
# ============================================================
# THIN BAND CHECK (< 10 institutions)
# ============================================================
#   [PASS] All non-null bands have >= 10 institutions
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 10 rows:
# shape: (10, 26)
# ┌────────┬──────┬─────────────┬────────────┬───┬────────────┬────────────┬────────────┬────────────┐
# │ unitid ┆ year ┆ inst_name   ┆ inst_contr ┆ … ┆ retention_ ┆ selectivit ┆ pell_band  ┆ urm_band   │
# │ ---    ┆ ---  ┆ ---         ┆ ol         ┆   ┆ rate       ┆ y_band     ┆ ---        ┆ ---        │
# │ i64    ┆ i64  ┆ str         ┆ ---        ┆   ┆ ---        ┆ ---        ┆ str        ┆ str        │
# │        ┆      ┆             ┆ i64        ┆   ┆ f64        ┆ str        ┆            ┆            │
# ╞════════╪══════╪═════════════╪════════════╪═══╪════════════╪════════════╪════════════╪════════════╡
# │ 100654 ┆ 2020 ┆ Alabama A & ┆ 1          ┆ … ┆ 54.0       ┆ Less Selec ┆ Very High  ┆ Very High  │
# │        ┆      ┆ M           ┆            ┆   ┆            ┆ tive/Open  ┆ Pell       ┆ URM (60%+) │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆            ┆ (60%+)     ┆            │
# │ 100663 ┆ 2020 ┆ University  ┆ 1          ┆ … ┆ 86.0       ┆ Less Selec ┆ Moderate   ┆ Moderate   │
# │        ┆      ┆ of Alabama  ┆            ┆   ┆            ┆ tive/Open  ┆ Pell       ┆ URM        │
# │        ┆      ┆ at Birmi…   ┆            ┆   ┆            ┆            ┆ (20-40%)   ┆ (20-40%)   │
# │ 100690 ┆ 2020 ┆ Amridge     ┆ 2          ┆ … ┆ 50.0       ┆ Less Selec ┆ Very High  ┆ Very High  │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆ tive/Open  ┆ Pell       ┆ URM (60%+) │
# │        ┆      ┆             ┆            ┆   ┆            ┆            ┆ (60%+)     ┆            │
# │ 100706 ┆ 2020 ┆ University  ┆ 1          ┆ … ┆ 82.0       ┆ Less Selec ┆ Moderate   ┆ Low URM    │
# │        ┆      ┆ of Alabama  ┆            ┆   ┆            ┆ tive/Open  ┆ Pell       ┆ (under     │
# │        ┆      ┆ in Hunts…   ┆            ┆   ┆            ┆            ┆ (20-40%)   ┆ 20%)       │
# │ 100724 ┆ 2020 ┆ Alabama     ┆ 1          ┆ … ┆ 62.0       ┆ Less Selec ┆ Very High  ┆ Very High  │
# │        ┆      ┆ State       ┆            ┆   ┆            ┆ tive/Open  ┆ Pell       ┆ URM (60%+) │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆            ┆ (60%+)     ┆            │
# │ 100733 ┆ 2020 ┆ University  ┆ 1          ┆ … ┆ null       ┆ Less Selec ┆ null       ┆ null       │
# │        ┆      ┆ of Alabama  ┆            ┆   ┆            ┆ tive/Open  ┆            ┆            │
# │        ┆      ┆ System O…   ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100751 ┆ 2020 ┆ The         ┆ 1          ┆ … ┆ 87.0       ┆ Less Selec ┆ Low Pell   ┆ Low URM    │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆ tive/Open  ┆ (under     ┆ (under     │
# │        ┆      ┆ of Alabama  ┆            ┆   ┆            ┆            ┆ 20%)       ┆ 20%)       │
# │ 100812 ┆ 2020 ┆ Athens      ┆ 1          ┆ … ┆ null       ┆ Less Selec ┆ High Pell  ┆ Low URM    │
# │        ┆      ┆ State       ┆            ┆   ┆            ┆ tive/Open  ┆ (40-60%)   ┆ (under     │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆            ┆            ┆ 20%)       │
# │ 100830 ┆ 2020 ┆ Auburn      ┆ 1          ┆ … ┆ 70.0       ┆ Less Selec ┆ High Pell  ┆ High URM   │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆ tive/Open  ┆ (40-60%)   ┆ (40-60%)   │
# │        ┆      ┆ at          ┆            ┆   ┆            ┆            ┆            ┆            │
# │        ┆      ┆ Montgomer…  ┆            ┆   ┆            ┆            ┆            ┆            │
# │ 100858 ┆ 2020 ┆ Auburn      ┆ 1          ┆ … ┆ 92.0       ┆ Less Selec ┆ Low Pell   ┆ Low URM    │
# │        ┆      ┆ University  ┆            ┆   ┆            ┆ tive/Open  ┆ (under     ┆ (under     │
# │        ┆      ┆             ┆            ┆   ┆            ┆            ┆ 20%)       ┆ 20%)       │
# └────────┴──────┴─────────────┴────────────┴───┴────────────┴────────────┴────────────┴────────────┘/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr1.py:555: DeprecationWarning: `pl.count()` is deprecated. Please use `pl.len()` instead.
# (Deprecated in version 0.20.5)
#   .agg(pl.count().alias("n"))
# /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage7_04_cr1.py:567: DeprecationWarning: `pl.count()` is deprecated. Please use `pl.len()` instead.
# (Deprecated in version 0.20.5)
#   pl.count().alias("n"),
# 
# 
# Descriptive statistics:
# shape: (9, 27)
# ┌────────────┬────────────┬────────┬───────────┬───┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ unitid     ┆ year   ┆ inst_name ┆ … ┆ retention ┆ selectivi ┆ pell_band ┆ urm_band  │
# │ ---        ┆ ---        ┆ ---    ┆ ---       ┆   ┆ _rate     ┆ ty_band   ┆ ---       ┆ ---       │
# │ str        ┆ f64        ┆ f64    ┆ str       ┆   ┆ ---       ┆ ---       ┆ str       ┆ str       │
# │            ┆            ┆        ┆           ┆   ┆ f64       ┆ str       ┆           ┆           │
# ╞════════════╪════════════╪════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 2528.0     ┆ 2528.0 ┆ 2528      ┆ … ┆ 1875.0    ┆ 2528      ┆ 2010      ┆ 2158      │
# │ null_count ┆ 0.0        ┆ 0.0    ┆ 0         ┆ … ┆ 653.0     ┆ 0         ┆ 518       ┆ 370       │
# │ mean       ┆ 220569.164 ┆ 2020.0 ┆ null      ┆ … ┆ 74.213333 ┆ null      ┆ null      ┆ null      │
# │            ┆ 161        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ std        ┆ 103707.401 ┆ 0.0    ┆ null      ┆ … ┆ 14.751312 ┆ null      ┆ null      ┆ null      │
# │            ┆ 134        ┆        ┆           ┆   ┆           ┆           ┆           ┆           │
# │ min        ┆ 100654.0   ┆ 2020.0 ┆ A T Still ┆ … ┆ 0.0       ┆ Highly    ┆ High Pell ┆ High URM  │
# │            ┆            ┆        ┆ Universit ┆   ┆           ┆ Selective ┆ (40-60%)  ┆ (40-60%)  │
# │            ┆            ┆        ┆ y of      ┆   ┆           ┆           ┆           ┆           │
# │            ┆            ┆        ┆ Health…   ┆   ┆           ┆           ┆           ┆           │
# │ 25%        ┆ 155089.0   ┆ 2020.0 ┆ null      ┆ … ┆ 67.0      ┆ null      ┆ null      ┆ null      │
# │ 50%        ┆ 196121.0   ┆ 2020.0 ┆ null      ┆ … ┆ 76.0      ┆ null      ┆ null      ┆ null      │
# │ 75%        ┆ 230597.0   ┆ 2020.0 ┆ null      ┆ … ┆ 84.0      ┆ null      ┆ null      ┆ null      │
# │ max        ┆ 496070.0   ┆ 2020.0 ┆ Zaytuna   ┆ … ┆ 100.0     ┆ Selective ┆ Very High ┆ Very High │
# │            ┆            ┆        ┆ College   ┆   ┆           ┆           ┆ Pell      ┆ URM       │
# │            ┆            ┆        ┆           ┆   ┆           ┆           ┆ (60%+)    ┆ (60%+)    │
# └────────────┴────────────┴────────┴───────────┴───┴───────────┴───────────┴───────────┴───────────┘
# 
# Band column value counts:
# 
# selectivity_band:
# shape: (4, 2)
# ┌──────────────────────┬───────┐
# │ selectivity_band     ┆ count │
# │ ---                  ┆ ---   │
# │ str                  ┆ u32   │
# ╞══════════════════════╪═══════╡
# │ Highly Selective     ┆ 73    │
# │ Less Selective/Open  ┆ 1695  │
# │ Moderately Selective ┆ 586   │
# │ Selective            ┆ 174   │
# └──────────────────────┴───────┘
# 
# pell_band:
# shape: (5, 2)
# ┌────────────────────────┬───────┐
# │ pell_band              ┆ count │
# │ ---                    ┆ ---   │
# │ str                    ┆ u32   │
# ╞════════════════════════╪═══════╡
# │ null                   ┆ 518   │
# │ High Pell (40-60%)     ┆ 576   │
# │ Low Pell (under 20%)   ┆ 261   │
# │ Moderate Pell (20-40%) ┆ 877   │
# │ Very High Pell (60%+)  ┆ 296   │
# └────────────────────────┴───────┘
# 
# urm_band:
# shape: (5, 2)
# ┌───────────────────────┬───────┐
# │ urm_band              ┆ count │
# │ ---                   ┆ ---   │
# │ str                   ┆ u32   │
# ╞═══════════════════════╪═══════╡
# │ null                  ┆ 370   │
# │ High URM (40-60%)     ┆ 228   │
# │ Low URM (under 20%)   ┆ 1025  │
# │ Moderate URM (20-40%) ┆ 635   │
# │ Very High URM (60%+)  ┆ 270   │
# └───────────────────────┴───────┘
# 
# Band column cross-tabulation (selectivity x pell_band):
# shape: (16, 3)
# ┌──────────────────────┬────────────────────────┬─────┐
# │ selectivity_band     ┆ pell_band              ┆ n   │
# │ ---                  ┆ ---                    ┆ --- │
# │ str                  ┆ str                    ┆ u32 │
# ╞══════════════════════╪════════════════════════╪═════╡
# │ Highly Selective     ┆ High Pell (40-60%)     ┆ 3   │
# │ Highly Selective     ┆ Low Pell (under 20%)   ┆ 45  │
# │ Highly Selective     ┆ Moderate Pell (20-40%) ┆ 17  │
# │ Highly Selective     ┆ Very High Pell (60%+)  ┆ 2   │
# │ Less Selective/Open  ┆ High Pell (40-60%)     ┆ 355 │
# │ …                    ┆ …                      ┆ …   │
# │ Moderately Selective ┆ Very High Pell (60%+)  ┆ 64  │
# │ Selective            ┆ High Pell (40-60%)     ┆ 38  │
# │ Selective            ┆ Low Pell (under 20%)   ┆ 43  │
# │ Selective            ┆ Moderate Pell (20-40%) ┆ 52  │
# │ Selective            ┆ Very High Pell (60%+)  ┆ 36  │
# └──────────────────────┴────────────────────────┴─────┘
# 
# Admission rate summary by selectivity_band:
# shape: (4, 5)
# ┌──────────────────────┬────────┬──────────┬──────────┬──────┐
# │ selectivity_band     ┆ ar_min ┆ ar_max   ┆ ar_nulls ┆ n    │
# │ ---                  ┆ ---    ┆ ---      ┆ ---      ┆ ---  │
# │ str                  ┆ f64    ┆ f64      ┆ u32      ┆ u32  │
# ╞══════════════════════╪════════╪══════════╪══════════╪══════╡
# │ Highly Selective     ┆ 0.0    ┆ 0.245412 ┆ 0        ┆ 73   │
# │ Less Selective/Open  ┆ 0.75   ┆ 1.0      ┆ 869      ┆ 1695 │
# │ Moderately Selective ┆ 0.5    ┆ 0.749896 ┆ 0        ┆ 586  │
# │ Selective            ┆ 0.25   ┆ 0.499877 ┆ 0        ┆ 174  │
# └──────────────────────┴────────┴──────────┴──────────┴──────┘
# 
# ============================================================
# QA RESULT: WARNING
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
