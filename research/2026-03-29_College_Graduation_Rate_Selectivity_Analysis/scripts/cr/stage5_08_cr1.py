#!/usr/bin/env python3
"""
QA INSPECTION: Stage 5 Step 08

Reviewed script: scripts/stage5_fetch/08_fetch-finance.py
Output files: data/raw/2026-03-29_ipeds_finance.parquet
Plan reference: 2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks:
1. Schema matches Plan.md expectations
2. Row count within expected range (3,000-10,000)
3. No suspicious distributions
4. Coded values presence check (-1, -2, -3)
5. No nulls in critical columns (unitid, year)

Script-Specific Checks (Five Lenses):
6. [Counterfactual] What if expenditure column name patterns were broader?
7. [Semantic] Does the column discovery actually find exp_instruc_total?
8. [Boundary] Check for zero FTE values and zero expenditure values
9. [Absence] Verify exp_instruc_total column IS in output despite being missed by discovery
10. [Downstream] Would clean-finance (Task 4.3) find the right columns?

Spot-Checks:
11. Trace a specific institution (unitid) through the data
12. Verify year is exactly 2017, no other years leaked
13. Check FTE column distributions for implausible values
14. Verify unitid uniqueness (1:1 per institution per year)
15. Cross-check row count against Plan Query 8 expected 6,000-8,000
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "raw" / "2026-03-29_ipeds_finance.parquet"
EXPECTED_COLUMNS_CRITICAL = ["unitid", "year", "fips"]
EXPECTED_COLUMNS_KEY = ["exp_instruc_total", "est_fte", "rep_fte", "calc_fte"]
EXPECTED_MIN_ROWS = 3000
EXPECTED_MAX_ROWS = 10000
CRITICAL_COLUMNS = ["unitid", "year"]
CODED_MISSING_VALUES = [-1, -2, -3]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 5 Step 08 (fetch-finance)")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Check 1: Schema ---
missing_critical = [c for c in EXPECTED_COLUMNS_CRITICAL if c not in df.columns]
missing_key = [c for c in EXPECTED_COLUMNS_KEY if c not in df.columns]
schema_ok = len(missing_critical) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Schema (critical): ", end="")
if schema_ok:
    print("All critical columns present (unitid, year, fips)")
else:
    print(f"Missing critical columns: {missing_critical}")

key_schema_ok = len(missing_key) == 0
print(f"[{'PASS' if key_schema_ok else 'FAIL'}] Schema (key analytical): ", end="")
if key_schema_ok:
    print(f"All key analytical columns present: {EXPECTED_COLUMNS_KEY}")
else:
    print(f"Missing key columns: {missing_key}")

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Row count: {row_count:,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distributions ---
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns[:20]:  # Sample first 20 numeric cols
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
for col in ["exp_instruc_total", "est_fte", "rep_fte", "calc_fte"]:
    if col not in df.columns:
        continue
    if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'WARN'}] Coded values in key cols: ", end="")
if coded_ok:
    print("None found in key analytical columns")
else:
    print("; ".join(coded_issues))

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

# =============================================================
# SCRIPT-SPECIFIC CHECKS
# =============================================================

# --- Check 6: [Counterfactual] Broader pattern matching for expenditure columns ---
# INTENT: The script used ["instruction", "expend", "expense"] to find expenditure cols.
# Let's check what a broader search would find, including "instruc" and "exp_".
print("\n" + "=" * 60)
print("SCRIPT-SPECIFIC CHECKS")
print("=" * 60)

# The script missed exp_instruc_total because "instruction" doesn't match "instruc"
broader_expenditure_cols = [
    c for c in df.columns
    if any(kw in c.lower() for kw in ["instruc", "instruction", "expend", "expense", "exp_"])
]
narrow_expenditure_cols = [
    c for c in df.columns
    if any(kw in c.lower() for kw in ["instruction", "expend", "expense"])
]
missed_by_narrow = set(broader_expenditure_cols) - set(narrow_expenditure_cols)
print(f"\n[WARN] Counterfactual -- broader expenditure column search:")
print(f"  Narrow search (script used): {narrow_expenditure_cols}")
print(f"  Broader search (instruc, exp_): found {len(broader_expenditure_cols)} columns")
print(f"  Columns MISSED by script's narrow search: {sorted(missed_by_narrow)}")
# Specifically check if exp_instruc_total was missed
exp_instruc_in_narrow = "exp_instruc_total" in narrow_expenditure_cols
exp_instruc_in_broad = "exp_instruc_total" in broader_expenditure_cols
exp_instruc_in_data = "exp_instruc_total" in df.columns
print(f"  exp_instruc_total in narrow search: {exp_instruc_in_narrow}")
print(f"  exp_instruc_total in broader search: {exp_instruc_in_broad}")
print(f"  exp_instruc_total in actual data: {exp_instruc_in_data}")
if exp_instruc_in_data and not exp_instruc_in_narrow:
    print(f"  [WARNING] Script's expenditure column discovery MISSED exp_instruc_total!")
    print(f"  The script reported: total_expenses_deductions, pension_expense, athletic_expense_treatment")
    print(f"  But the ACTUAL instructional expenditure column is exp_instruc_total (column #49)")

# --- Check 7: [Semantic] Does the data serve the research question? ---
# The research needs instructional expenditure per FTE for regression Model 3.
# Verify the actual column we need is present and has usable data.
print(f"\n[CHECK] Semantic -- exp_instruc_total data quality:")
if "exp_instruc_total" in df.columns:
    exp_col = df["exp_instruc_total"]
    exp_non_null = exp_col.drop_nulls()
    exp_valid = exp_non_null.filter(~exp_non_null.is_in(CODED_MISSING_VALUES))
    null_pct = exp_col.null_count() / len(df) * 100
    valid_pct = len(exp_valid) / len(df) * 100
    print(f"  Total rows: {len(df):,}")
    print(f"  Null: {exp_col.null_count():,} ({null_pct:.1f}%)")
    print(f"  Valid (non-null, non-coded): {len(exp_valid):,} ({valid_pct:.1f}%)")
    if len(exp_valid) > 0:
        print(f"  Min: ${exp_valid.min():,.0f}")
        print(f"  Max: ${exp_valid.max():,.0f}")
        print(f"  Mean: ${exp_valid.mean():,.0f}")
        print(f"  Median: ${exp_valid.median():,.0f}")
    semantic_ok = valid_pct > 50
    print(f"  [{'PASS' if semantic_ok else 'WARN'}] exp_instruc_total availability: {valid_pct:.1f}%")
else:
    print(f"  [FAIL] exp_instruc_total NOT FOUND in data!")
    semantic_ok = False

# --- Check 8: [Boundary] Zero values in FTE and expenditure ---
print(f"\n[CHECK] Boundary -- zero values in key columns:")
for col_name in ["exp_instruc_total", "est_fte", "rep_fte", "calc_fte"]:
    if col_name in df.columns:
        col_data = df[col_name].drop_nulls()
        zero_count = (col_data == 0).sum()
        neg_count = (col_data < 0).sum()
        # Separate coded negatives from real negatives
        coded_neg = 0
        if df[col_name].dtype in [pl.Int64, pl.Float64]:
            for code in CODED_MISSING_VALUES:
                coded_neg += (col_data == code).sum()
        real_neg = neg_count - coded_neg
        print(f"  {col_name}: zeros={zero_count}, real negatives={real_neg}, coded negatives={coded_neg}")
        if col_name == "est_fte" and zero_count > 0:
            print(f"    [WARN] {zero_count} institutions with est_fte=0 -- will cause division by zero in per-FTE calc")
        if col_name == "exp_instruc_total" and zero_count > 0:
            print(f"    [WARN] {zero_count} institutions with zero instructional expenditure -- may indicate non-reporting")

# --- Check 9: [Absence] Verify all expected columns present for downstream ---
# The clean-finance task (4.3) needs: unitid, exp_instruc_total (or similar), est_fte
print(f"\n[CHECK] Absence -- columns needed by downstream Task 4.3 (clean-finance):")
downstream_needed = {
    "unitid": "join key",
    "year": "year filter verification",
    "exp_instruc_total": "instructional expenditure (Plan: instr_expend_per_fte numerator)",
    "est_fte": "FTE enrollment (Plan: instr_expend_per_fte denominator)",
}
all_downstream_present = True
for col, purpose in downstream_needed.items():
    present = col in df.columns
    if not present:
        all_downstream_present = False
    print(f"  [{'PASS' if present else 'FAIL'}] {col}: {purpose} -- {'present' if present else 'MISSING'}")
print(f"  Overall downstream readiness: {'PASS' if all_downstream_present else 'FAIL'}")

# --- Check 10: [Downstream] Would clean-finance find the right columns? ---
# The clean-finance task says: "Look for columns containing 'instruction' or 'expenditure'"
# This is the SAME narrow pattern that missed exp_instruc_total in the fetch script!
print(f"\n[CHECK] Downstream -- clean-finance column discovery risk:")
clean_finance_pattern_cols = [
    c for c in df.columns
    if any(kw in c.lower() for kw in ["instruction", "expenditure"])
]
print(f"  Columns matching 'instruction' or 'expenditure': {clean_finance_pattern_cols}")
if "exp_instruc_total" not in clean_finance_pattern_cols:
    print(f"  [WARNING] The clean-finance task's documented search pattern would ALSO miss exp_instruc_total!")
    print(f"  Task 4.3 says: 'Look for columns containing instruction or expenditure in name'")
    print(f"  exp_instruc_total uses 'instruc' (abbreviated), not 'instruction'")
    print(f"  Recommendation: clean-finance should search for 'instruc' or use exact column name")
else:
    print(f"  [PASS] clean-finance pattern would find exp_instruc_total")

# =============================================================
# SPOT-CHECKS
# =============================================================

print("\n" + "=" * 60)
print("SPOT-CHECKS")
print("=" * 60)

# --- Spot-check 11: Trace a specific institution ---
# Pick a well-known large institution and verify its data looks reasonable
print(f"\nSpot-check 11: Trace specific institution")
# unitid 110635 = UC Berkeley (a large public research university)
# unitid 166027 = MIT
# Let's check both if available
for uid, name in [(110635, "UC Berkeley"), (166027, "MIT"), (243780, "U of Wisconsin-Madison")]:
    inst = df.filter(pl.col("unitid") == uid)
    if len(inst) > 0:
        print(f"\n  {name} (unitid={uid}):")
        exp_val = inst["exp_instruc_total"][0] if "exp_instruc_total" in df.columns else "N/A"
        fte_val = inst["est_fte"][0] if "est_fte" in df.columns else "N/A"
        print(f"    exp_instruc_total: {exp_val}")
        print(f"    est_fte: {fte_val}")
        if exp_val is not None and fte_val is not None and fte_val > 0 and exp_val != "N/A" and fte_val != "N/A":
            per_fte = exp_val / fte_val
            print(f"    Implied instr_expend_per_fte: ${per_fte:,.0f}")
            # Sanity: large research universities typically spend $15K-$80K per FTE
            reasonable = 5000 <= per_fte <= 200000
            print(f"    Reasonable range ($5K-$200K)? {'YES' if reasonable else 'NO'}")
    else:
        print(f"  {name} (unitid={uid}): NOT FOUND in data")

# --- Spot-check 12: Year is exactly 2017 ---
print(f"\nSpot-check 12: Year verification")
year_vals = sorted(df["year"].unique().to_list())
year_ok = year_vals == [2017]
print(f"  [{'PASS' if year_ok else 'FAIL'}] Years in data: {year_vals} (expected [2017])")

# --- Spot-check 13: FTE distribution plausibility ---
print(f"\nSpot-check 13: FTE column distributions")
for fte_col in ["est_fte", "rep_fte", "calc_fte"]:
    if fte_col in df.columns:
        col_data = df[fte_col].drop_nulls()
        if len(col_data) > 0:
            p10 = col_data.quantile(0.10)
            p50 = col_data.quantile(0.50)
            p90 = col_data.quantile(0.90)
            p99 = col_data.quantile(0.99)
            print(f"  {fte_col}: p10={p10:,.0f}, p50={p50:,.0f}, p90={p90:,.0f}, p99={p99:,.0f}")

# --- Spot-check 14: unitid uniqueness ---
print(f"\nSpot-check 14: unitid uniqueness")
total = len(df)
unique_unitids = df["unitid"].n_unique()
unique_ok = total == unique_unitids
print(f"  [{'PASS' if unique_ok else 'FAIL'}] unitid uniqueness: {unique_unitids:,} unique out of {total:,} rows")
if not unique_ok:
    dup_unitids = df.group_by("unitid").len().filter(pl.col("len") > 1)
    print(f"  Duplicate unitids: {len(dup_unitids):,} institutions have >1 row")
    print(f"  Sample duplicates:")
    print(dup_unitids.head(5))

# --- Spot-check 15: Row count vs Plan Query 8 ---
print(f"\nSpot-check 15: Row count vs Plan Query 8 (expected 6,000-8,000)")
plan_min = 6000
plan_max = 8000
in_plan_range = plan_min <= row_count <= plan_max
print(f"  [{'PASS' if in_plan_range else 'INFO'}] Row count {row_count:,} vs Plan Query 8 range {plan_min:,}-{plan_max:,}")
if not in_plan_range:
    print(f"  Note: Slightly outside Plan's tighter estimate but within task verify range (3K-10K)")

# =============================================================
# DATA PROFILING (for cr2+ decision)
# =============================================================

print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 5 rows (selected columns):")
display_cols = ["unitid", "year", "fips", "exp_instruc_total", "exp_instruc_salaries",
                "est_fte", "rep_fte", "calc_fte", "exp_total_current"]
available_display = [c for c in display_cols if c in df.columns]
print(df.select(available_display).head(5))

print("\nDescriptive statistics for key columns:")
key_stats_cols = ["exp_instruc_total", "exp_instruc_salaries", "est_fte", "rep_fte",
                  "calc_fte", "exp_total_current", "rev_total_current"]
available_stats = [c for c in key_stats_cols if c in df.columns]
print(df.select(available_stats).describe())

print("\nNull counts for ALL expenditure-related columns (exp_* prefix):")
exp_cols = [c for c in df.columns if c.startswith("exp_")]
for col in exp_cols:
    null_ct = df[col].null_count()
    null_pct = null_ct / len(df) * 100
    print(f"  {col}: {null_ct:,} nulls ({null_pct:.1f}%)")

print("\nColumn data types summary:")
dtype_counts = {}
for col in df.columns:
    dt = str(df[col].dtype)
    dtype_counts[dt] = dtype_counts.get(dt, 0) + 1
for dt, ct in sorted(dtype_counts.items()):
    print(f"  {dt}: {ct} columns")

# --- Summary ---
print("\n" + "=" * 60)
print("QA SUMMARY")
print("=" * 60)

all_base_passed = all([schema_ok, key_schema_ok, rows_ok, dist_ok, nulls_ok])
has_warnings = (not exp_instruc_in_narrow) or (not coded_ok)

if all_base_passed and not has_warnings:
    severity = "PASSED"
elif all_base_passed:
    severity = "WARNING"
else:
    severity = "BLOCKER"

print(f"Base checks: {'ALL PASSED' if all_base_passed else 'ISSUES FOUND'}")
print(f"Key finding: Script's expenditure column discovery missed exp_instruc_total")
print(f"  (uses 'instruction' but column uses abbreviated 'instruc')")
print(f"  Data impact: NONE -- all 141 columns saved to parquet, column IS in output")
print(f"  Downstream risk: clean-finance (Task 4.3) may repeat same pattern error")
print(f"QA RESULT: {severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-29 22:51:58
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage5_08_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 5 Step 08 (fetch-finance)
# ============================================================
# Loaded: 6,857 rows x 141 cols
# 
# [PASS] Schema (critical): All critical columns present (unitid, year, fips)
# [PASS] Schema (key analytical): All key analytical columns present: ['exp_instruc_total', 'est_fte', 'rep_fte', 'calc_fte']
# [PASS] Row count: 6,857 (expected 3,000-10,000)
# [FAIL] Distributions: year: all same value (2017)
# [PASS] Coded values in key cols: None found in key analytical columns
# [PASS] Critical nulls: None
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [WARN] Counterfactual -- broader expenditure column search:
#   Narrow search (script used): ['total_expenses_deductions', 'pension_expense', 'athletic_expense_treatment']
#   Broader search (instruc, exp_): found 37 columns
#   Columns MISSED by script's narrow search: ['exp_acad_inst_student_salaries', 'exp_acad_inst_student_total', 'exp_acad_supp_salaries', 'exp_acad_supp_total', 'exp_aux_ent_salaries', 'exp_aux_ent_total', 'exp_hospital_salaries', 'exp_hospital_total', 'exp_ind_op_salaries', 'exp_ind_op_total', 'exp_inst_supp_salaries', 'exp_inst_supp_total', 'exp_instruc_salaries', 'exp_instruc_total', 'exp_net_grant_aid_salaries', 'exp_net_grant_aid_total', 'exp_other_salaries', 'exp_other_total_funct', 'exp_pub_serv_salaries', 'exp_pub_serv_total', 'exp_res_pub_serv_salaries', 'exp_res_pub_serv_total', 'exp_research_salaries', 'exp_research_total', 'exp_student_serv_salaries', 'exp_student_serv_total', 'exp_total_benefits', 'exp_total_current', 'exp_total_depr', 'exp_total_interest', 'exp_total_opm', 'exp_total_other_nat', 'exp_total_salaries', 'sch_exp_net_fellowships']
#   exp_instruc_total in narrow search: False
#   exp_instruc_total in broader search: True
#   exp_instruc_total in actual data: True
#   [WARNING] Script's expenditure column discovery MISSED exp_instruc_total!
#   The script reported: total_expenses_deductions, pension_expense, athletic_expense_treatment
#   But the ACTUAL instructional expenditure column is exp_instruc_total (column #49)
# 
# [CHECK] Semantic -- exp_instruc_total data quality:
#   Total rows: 6,857
#   Null: 709 (10.3%)
#   Valid (non-null, non-coded): 6,148 (89.7%)
#   Min: $1,770
#   Max: $2,739,126,000
#   Mean: $29,706,556
#   Median: $3,129,670
#   [PASS] exp_instruc_total availability: 89.7%
# 
# [CHECK] Boundary -- zero values in key columns:
#   exp_instruc_total: zeros=0, real negatives=0, coded negatives=0
#   est_fte: zeros=39, real negatives=0, coded negatives=0
#     [WARN] 39 institutions with est_fte=0 -- will cause division by zero in per-FTE calc
#   rep_fte: zeros=3, real negatives=0, coded negatives=0
#   calc_fte: zeros=0, real negatives=0, coded negatives=0
# 
# [CHECK] Absence -- columns needed by downstream Task 4.3 (clean-finance):
#   [PASS] unitid: join key -- present
#   [PASS] year: year filter verification -- present
#   [PASS] exp_instruc_total: instructional expenditure (Plan: instr_expend_per_fte numerator) -- present
#   [PASS] est_fte: FTE enrollment (Plan: instr_expend_per_fte denominator) -- present
#   Overall downstream readiness: PASS
# 
# [CHECK] Downstream -- clean-finance column discovery risk:
#   Columns matching 'instruction' or 'expenditure': []
#   [WARNING] The clean-finance task's documented search pattern would ALSO miss exp_instruc_total!
#   Task 4.3 says: 'Look for columns containing instruction or expenditure in name'
#   exp_instruc_total uses 'instruc' (abbreviated), not 'instruction'
#   Recommendation: clean-finance should search for 'instruc' or use exact column name
# 
# ============================================================
# SPOT-CHECKS
# ============================================================
# 
# Spot-check 11: Trace specific institution
# 
#   UC Berkeley (unitid=110635):
#     exp_instruc_total: 855528260.0
#     est_fte: 40958
#     Implied instr_expend_per_fte: $20,888
#     Reasonable range ($5K-$200K)? YES
# 
#   MIT (unitid=166027):
#     exp_instruc_total: 1263491000.0
#     est_fte: 24921
#     Implied instr_expend_per_fte: $50,700
#     Reasonable range ($5K-$200K)? YES
# 
#   U of Wisconsin-Madison (unitid=243780):
#     exp_instruc_total: 808473200.0
#     est_fte: 40431
#     Implied instr_expend_per_fte: $19,996
#     Reasonable range ($5K-$200K)? YES
# 
# Spot-check 12: Year verification
#   [PASS] Years in data: [2017] (expected [2017])
# 
# Spot-check 13: FTE column distributions
#   est_fte: p10=46, p50=456, p90=6,542, p99=30,480
#   rep_fte: p10=49, p50=480, p90=6,660, p99=31,098
#   calc_fte: p10=40, p50=388, p90=6,028, p99=28,273
# 
# Spot-check 14: unitid uniqueness
#   [PASS] unitid uniqueness: 6,857 unique out of 6,857 rows
# 
# Spot-check 15: Row count vs Plan Query 8 (expected 6,000-8,000)
#   [PASS] Row count 6,857 vs Plan Query 8 range 6,000-8,000
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 5 rows (selected columns):
# shape: (5, 9)
# ┌────────┬──────┬──────┬───────────────────┬───┬─────────┬─────────┬──────────┬───────────────────┐
# │ unitid ┆ year ┆ fips ┆ exp_instruc_total ┆ … ┆ est_fte ┆ rep_fte ┆ calc_fte ┆ exp_total_current │
# │ ---    ┆ ---  ┆ ---  ┆ ---               ┆   ┆ ---     ┆ ---     ┆ ---      ┆ ---               │
# │ i64    ┆ i64  ┆ i64  ┆ f64               ┆   ┆ i64     ┆ i64     ┆ f64      ┆ f64               │
# ╞════════╪══════╪══════╪═══════════════════╪═══╪═════════╪═════════╪══════════╪═══════════════════╡
# │ 100654 ┆ 2017 ┆ 1    ┆ 3.0423688e7       ┆ … ┆ 5651    ┆ 5651    ┆ 5589.0   ┆ 1.48802592e8      │
# │ 100663 ┆ 2017 ┆ 1    ┆ 3.1680387e8       ┆ … ┆ 18069   ┆ 19254   ┆ 16471.0  ┆ 3.0288e9          │
# │ 100690 ┆ 2017 ┆ 1    ┆ 2.174518e6        ┆ … ┆ 517     ┆ 517     ┆ 416.0    ┆ 6.875035e6        │
# │ 100706 ┆ 2017 ┆ 1    ┆ 7.204525e7        ┆ … ┆ 7672    ┆ 7795    ┆ 7583.0   ┆ 2.39618816e8      │
# │ 100724 ┆ 2017 ┆ 1    ┆ 3.903584e7        ┆ … ┆ 4461    ┆ 4578    ┆ 4411.0   ┆ 1.48376528e8      │
# └────────┴──────┴──────┴───────────────────┴───┴─────────┴─────────┴──────────┴───────────────────┘
# 
# Descriptive statistics for key columns:
# shape: (9, 8)
# ┌────────────┬────────────┬────────────┬───────────┬───────────┬───────────┬───────────┬───────────┐
# │ statistic  ┆ exp_instru ┆ exp_instru ┆ est_fte   ┆ rep_fte   ┆ calc_fte  ┆ exp_total ┆ rev_total │
# │ ---        ┆ c_total    ┆ c_salaries ┆ ---       ┆ ---       ┆ ---       ┆ _current  ┆ _current  │
# │ str        ┆ ---        ┆ ---        ┆ f64       ┆ f64       ┆ f64       ┆ ---       ┆ ---       │
# │            ┆ f64        ┆ f64        ┆           ┆           ┆           ┆ f64       ┆ f64       │
# ╞════════════╪════════════╪════════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
# │ count      ┆ 6148.0     ┆ 6139.0     ┆ 6561.0    ┆ 6561.0    ┆ 6588.0    ┆ 6191.0    ┆ 6188.0    │
# │ null_count ┆ 709.0      ┆ 718.0      ┆ 296.0     ┆ 296.0     ┆ 269.0     ┆ 666.0     ┆ 669.0     │
# │ mean       ┆ 2.9707e7   ┆ 1.6971e7   ┆ 2491.9617 ┆ 2565.5851 ┆ 2340.5859 ┆ 9.8980e7  ┆ 1.0990e8  │
# │            ┆            ┆            ┆ 44        ┆ 24        ┆ 14        ┆           ┆           │
# │ std        ┆ 1.1430e8   ┆ 6.3388e7   ┆ 5772.5901 ┆ 5963.3561 ┆ 5574.3803 ┆ 4.4276e8  ┆ 5.1383e8  │
# │            ┆            ┆            ┆ 06        ┆ 4         ┆ 32        ┆           ┆           │
# │ min        ┆ 1770.0     ┆ 18.0       ┆ 0.0       ┆ 0.0       ┆ 2.0       ┆ 10200.0   ┆ 15250.0   │
# │ 25%        ┆ 618733.0   ┆ 363296.0   ┆ 116.0     ┆ 122.0     ┆ 99.0      ┆ 1.674179e ┆ 1.803362e │
# │            ┆            ┆            ┆           ┆           ┆           ┆ 6         ┆ 6         │
# │ 50%        ┆ 3.129885e6 ┆ 1.891804e6 ┆ 456.0     ┆ 480.0     ┆ 388.0     ┆ 9.405266e ┆ 9.999395e │
# │            ┆            ┆            ┆           ┆           ┆           ┆ 6         ┆ 6         │
# │ 75%        ┆ 1.8981826e ┆ 1.0829573e ┆ 2134.0    ┆ 2194.0    ┆ 2010.0    ┆ 5.2574136 ┆ 5.4777028 │
# │            ┆ 7          ┆ 7          ┆           ┆           ┆           ┆ e7        ┆ e7        │
# │ max        ┆ 2.7391e9   ┆ 1.4918e9   ┆ 79173.0   ┆ 79173.0   ┆ 103975.0  ┆ 9.5610e9  ┆ 1.1686e10 │
# └────────────┴────────────┴────────────┴───────────┴───────────┴───────────┴───────────┴───────────┘
# 
# Null counts for ALL expenditure-related columns (exp_* prefix):
#   exp_instruc_total: 709 nulls (10.3%)
#   exp_instruc_salaries: 718 nulls (10.5%)
#   exp_research_total: 5,560 nulls (81.1%)
#   exp_research_salaries: 5,683 nulls (82.9%)
#   exp_pub_serv_total: 4,892 nulls (71.3%)
#   exp_pub_serv_salaries: 5,133 nulls (74.9%)
#   exp_res_pub_serv_total: 4,600 nulls (67.1%)
#   exp_res_pub_serv_salaries: 4,860 nulls (70.9%)
#   exp_acad_supp_total: 1,278 nulls (18.6%)
#   exp_acad_supp_salaries: 1,665 nulls (24.3%)
#   exp_student_serv_total: 1,060 nulls (15.5%)
#   exp_student_serv_salaries: 1,343 nulls (19.6%)
#   exp_inst_supp_total: 853 nulls (12.4%)
#   exp_inst_supp_salaries: 1,181 nulls (17.2%)
#   exp_acad_inst_student_total: 763 nulls (11.1%)
#   exp_acad_inst_student_salaries: 942 nulls (13.7%)
#   exp_aux_ent_total: 3,936 nulls (57.4%)
#   exp_aux_ent_salaries: 4,307 nulls (62.8%)
#   exp_net_grant_aid_total: 4,804 nulls (70.1%)
#   exp_net_grant_aid_salaries: 6,857 nulls (100.0%)
#   exp_hospital_total: 6,782 nulls (98.9%)
#   exp_hospital_salaries: 6,782 nulls (98.9%)
#   exp_ind_op_total: 6,751 nulls (98.5%)
#   exp_ind_op_salaries: 6,776 nulls (98.8%)
#   exp_other_total_funct: 3,567 nulls (52.0%)
#   exp_other_salaries: 5,786 nulls (84.4%)
#   exp_total_current: 666 nulls (9.7%)
#   exp_total_salaries: 669 nulls (9.8%)
#   exp_total_benefits: 1,395 nulls (20.3%)
#   exp_total_opm: 1,021 nulls (14.9%)
#   exp_total_depr: 1,453 nulls (21.2%)
#   exp_total_interest: 3,336 nulls (48.7%)
#   exp_total_other_nat: 1,034 nulls (15.1%)
# 
# Column data types summary:
#   Float64: 126 columns
#   Int64: 15 columns
# 
# ============================================================
# QA SUMMARY
# ============================================================
# Base checks: ISSUES FOUND
# Key finding: Script's expenditure column discovery missed exp_instruc_total
#   (uses 'instruction' but column uses abbreviated 'instruc')
#   Data impact: NONE -- all 141 columns saved to parquet, column IS in output
#   Downstream risk: clean-finance (Task 4.3) may repeat same pattern error
# QA RESULT: BLOCKER
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
