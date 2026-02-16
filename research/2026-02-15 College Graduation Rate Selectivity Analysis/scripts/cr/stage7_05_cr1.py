#!/usr/bin/env python3
"""
QA INSPECTION: Stage 7 Step 10.1
Task: join-scorecard (QA3)

Reviewed script: scripts/stage7_transform/05_join-scorecard.py
Output files: data/processed/2026-02-15_analysis_with_earnings.parquet
Plan reference: 2026-02-15 College Graduation Rate Selectivity Analysis Plan.md

QA Checks (Default):
1. Schema matches Plan expectations
2. Row count within expected range
3. No suspicious distributions
4. Coded values properly filtered
5. No nulls in critical columns (pre-join original columns)

QA Checks (Script-Specific — Five Lenses):
6. [Counterfactual] What if Scorecard had duplicate unitids? Verify no fan-out.
7. [Semantic] Does coverage-by-band pattern match Plan expectation (lower coverage for highly selective)?
8. [Boundary] Verify 8-digit branch campus unitids did NOT match any analysis row.
9. [Absence] Check that no Scorecard columns (year, years_after_entry) leaked into output.
10. [Downstream] Verify earnings nulls only in Scorecard-added columns, not original analysis columns.

Spot Checks:
11. Pick 3 specific unitids and trace their earnings values from Scorecard input to output.
12. Pick 3 unmatched unitids and confirm they are absent from Scorecard.
13. Verify earnings_med range matches Plan expectation ($11K-$133K).
14. Check the filter complement: are missing institutions the ones we'd expect?
15. Cross-reference: independently count matched rows vs. output non-null earnings.
"""

import polars as pl
from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
OUTPUT_FILE = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis_with_earnings.parquet"
INPUT_ANALYSIS = PROJECT_DIR / "data" / "processed" / "2026-02-15_analysis.parquet"
INPUT_SCORECARD = PROJECT_DIR / "data" / "processed" / "2026-02-15_scorecard_clean.parquet"

# Expected columns: 26 original analysis columns + 11 Scorecard columns = 37
EXPECTED_COLUMNS = [
    "unitid", "year", "inst_name", "inst_control", "institution_level", "hbcu",
    "degree_granting", "urban_centric_locale", "state_abbr", "fips",
    "grad_rate_150pct", "cohort_year", "number_applied", "number_admitted",
    "number_enrolled_total", "admission_rate", "pell_recipients",
    "enrollment_undergrad", "pell_share", "urm_share", "urm_enrollment",
    "student_faculty_ratio", "retention_rate", "selectivity_band", "pell_band",
    "urm_band",
    # Scorecard-added columns
    "earnings_med", "earnings_pct25", "earnings_pct75", "count_working",
    "count_working_lowinc", "count_working_midinc", "count_working_highinc",
    "count_working_dep", "count_working_ind", "count_working_female",
    "count_working_male",
]
EXPECTED_MIN_ROWS = 2528
EXPECTED_MAX_ROWS = 2528
# Critical columns: original analysis columns that must have NO new nulls from the join
CRITICAL_COLUMNS = [
    "unitid", "year", "inst_name", "grad_rate_150pct", "selectivity_band",
    "admission_rate", "pell_share", "urm_share"
]

# --- Load output data ---
print("=" * 60)
print("QA INSPECTION: Stage 7 Step 10.1 — join-scorecard")
print("=" * 60)

df = pl.read_parquet(OUTPUT_FILE)
df_analysis = pl.read_parquet(INPUT_ANALYSIS)
df_scorecard = pl.read_parquet(INPUT_SCORECARD)
print(f"Output loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"Input analysis loaded: {df_analysis.shape[0]:,} rows x {df_analysis.shape[1]} cols")
print(f"Input scorecard loaded: {df_scorecard.shape[0]:,} rows x {df_scorecard.shape[1]} cols")

issues = []

# --- Check 1: Schema ---
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
schema_ok = len(missing_cols) == 0
print(f"\n[{'PASS' if schema_ok else 'FAIL'}] Check 1 — Schema: ", end="")
if schema_ok:
    print("All 37 expected columns present")
else:
    print(f"Missing columns: {missing_cols}")
    issues.append(("BLOCKER", f"Missing columns: {missing_cols}"))
if extra_cols:
    print(f"  Extra columns (not in Plan): {extra_cols}")
    issues.append(("WARNING", f"Extra columns not in Plan: {extra_cols}"))

# --- Check 2: Row count ---
row_count = len(df)
rows_ok = EXPECTED_MIN_ROWS <= row_count <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Check 2 — Row count: {row_count:,} (expected exactly {EXPECTED_MIN_ROWS:,})")
if not rows_ok:
    issues.append(("BLOCKER", f"Row count {row_count} != expected {EXPECTED_MIN_ROWS}"))

# --- Check 3: Distributions (numeric columns) ---
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
print(f"[{'PASS' if dist_ok else 'FAIL'}] Check 3 — Distributions: ", end="")
print("Look reasonable" if dist_ok else "; ".join(dist_issues))
if not dist_ok:
    for d in dist_issues:
        issues.append(("WARNING", f"Distribution issue: {d}"))

# --- Check 4: Coded values ---
coded_issues = []
for col in df.columns:
    if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
        continue
    for code in [-1, -2, -3, -9, -99]:
        count = (df[col] == code).sum()
        if count > 0:
            coded_issues.append(f"{col} has {count} coded value {code}")
coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Check 4 — Coded values: ", end="")
print("None remain" if coded_ok else "; ".join(coded_issues))
if not coded_ok:
    for c in coded_issues:
        issues.append(("WARNING", f"Coded value: {c}"))

# --- Check 5: Critical nulls (original columns) ---
# For original analysis columns, compare null counts between input and output
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns and col in df_analysis.columns:
        pre_nulls = df_analysis[col].null_count()
        post_nulls = df[col].null_count()
        new_nulls = post_nulls - pre_nulls
        if new_nulls > 0:
            null_issues.append(f"{col}: {new_nulls} NEW nulls introduced by join")
nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Check 5 — Critical nulls (original cols): ", end="")
print("No new nulls" if nulls_ok else "; ".join(null_issues))
if not nulls_ok:
    for n in null_issues:
        issues.append(("BLOCKER", f"Original column corruption: {n}"))

# ============================================================
# SCRIPT-SPECIFIC CHECKS (Five Lenses)
# ============================================================
print(f"\n{'=' * 60}")
print("SCRIPT-SPECIFIC CHECKS")
print(f"{'=' * 60}")

# --- Check 6: [Counterfactual] Fan-out detection ---
# If Scorecard had duplicate unitids, LEFT join would create extra rows.
# Verify unitid is still unique in output.
uid_unique = df["unitid"].n_unique() == df.shape[0]
print(f"\n[{'PASS' if uid_unique else 'FAIL'}] Check 6 — [Counterfactual] No fan-out: ", end="")
print(f"{df['unitid'].n_unique():,} unique unitids / {df.shape[0]:,} rows")
if not uid_unique:
    issues.append(("BLOCKER", "Fan-out detected: unitid not unique after join"))

# --- Check 7: [Semantic] Coverage-by-band pattern ---
# Plan Risk Register says: "30-50% at elite, 80%+ at less selective"
# But execution log shows: Highly Selective 89%, Less Selective/Open 72.2%
# This is the OPPOSITE pattern. Investigate whether this is a concern or expected
# for our specific analysis subset (IPEDS 4-year, non-profit/public).
print(f"\n[INFO] Check 7 — [Semantic] Coverage by selectivity band:")
coverage_by_band = (
    df
    .group_by("selectivity_band")
    .agg(
        pl.len().alias("total"),
        pl.col("earnings_med").is_not_null().sum().alias("has_earnings"),
    )
    .with_columns(
        (pl.col("has_earnings") / pl.col("total") * 100).round(1).alias("coverage_pct")
    )
    .sort("selectivity_band")
)
for row in coverage_by_band.iter_rows(named=True):
    print(f"  {row['selectivity_band']}: {row['has_earnings']:,} / {row['total']:,} ({row['coverage_pct']}%)")

# Plan says "30-50% at elite institutions" for Title IV coverage, but that refers
# to the raw Scorecard universe. Our analysis subset is IPEDS 4-year degree-granting,
# which already filters to institutions that are likely Title IV eligible.
# The higher coverage for selective institutions in our subset is plausible because
# selective 4-year institutions are almost always Title IV.
# Less Selective/Open having LOWER coverage (72.2%) is expected because this group
# includes many smaller institutions that may lack Scorecard data.
hs_row = coverage_by_band.filter(pl.col("selectivity_band") == "Highly Selective")
ls_row = coverage_by_band.filter(pl.col("selectivity_band") == "Less Selective/Open")
if hs_row.shape[0] > 0 and ls_row.shape[0] > 0:
    hs_cov = hs_row["coverage_pct"][0]
    ls_cov = ls_row["coverage_pct"][0]
    pattern_inverted = hs_cov > ls_cov
    print(f"  Pattern note: Highly Selective ({hs_cov}%) > Less Selective/Open ({ls_cov}%)")
    print(f"  This is INVERTED from Plan Risk Register expectation (30-50% elite, 80%+ less selective)")
    print(f"  Explanation: Plan cites raw Scorecard Title IV coverage; our subset is IPEDS 4-yr only")
    if pattern_inverted:
        issues.append(("INFO", "Coverage pattern inverted vs Plan Risk Register — expected for IPEDS 4-yr subset"))

# --- Check 8: [Boundary] 8-digit branch campus unitids ---
# Verify that NO 8-digit Scorecard unitids accidentally matched an analysis unitid.
analysis_ids = set(df_analysis["unitid"].unique().to_list())
sc_str = df_scorecard.with_columns(
    pl.col("unitid").cast(pl.String).str.len_chars().alias("uid_len")
)
branch_ids = set(sc_str.filter(pl.col("uid_len") > 6)["unitid"].to_list())
branch_matches = branch_ids & analysis_ids
branch_ok = len(branch_matches) == 0
print(f"\n[{'PASS' if branch_ok else 'WARN'}] Check 8 — [Boundary] 8-digit branch IDs not in analysis: ", end="")
print(f"{len(branch_matches)} branch campus unitids matched analysis")
if not branch_ok:
    print(f"  Matched branch unitids: {list(branch_matches)[:10]}")
    issues.append(("WARNING", f"{len(branch_matches)} branch campus unitids matched analysis dataset"))

# --- Check 9: [Absence] Scorecard columns that should NOT be in output ---
# The script drops 'year' (from Scorecard) and 'years_after_entry' before joining.
# Verify these don't appear as duplicates (e.g., 'year_right').
leaked_cols = [c for c in df.columns if c in ("years_after_entry",) or c.endswith("_right")]
absence_ok = len(leaked_cols) == 0
print(f"[{'PASS' if absence_ok else 'FAIL'}] Check 9 — [Absence] No leaked Scorecard columns: ", end="")
print("Clean" if absence_ok else f"Found: {leaked_cols}")
if not absence_ok:
    issues.append(("BLOCKER", f"Leaked Scorecard columns: {leaked_cols}"))

# --- Check 10: [Downstream] Earnings nulls ONLY in Scorecard-added columns ---
scorecard_added = ["earnings_med", "earnings_pct25", "earnings_pct75", "count_working",
                   "count_working_lowinc", "count_working_midinc", "count_working_highinc",
                   "count_working_dep", "count_working_ind", "count_working_female",
                   "count_working_male"]
# All Scorecard columns should have the SAME null pattern (all null or all non-null per row)
# because a match brings ALL Scorecard columns.
if "earnings_med" in df.columns and "earnings_pct25" in df.columns:
    med_null = df["earnings_med"].is_null()
    pct25_null = df["earnings_pct25"].is_null()
    null_pattern_consistent = (med_null == pct25_null).all()
    print(f"[{'PASS' if null_pattern_consistent else 'WARN'}] Check 10 — [Downstream] Null pattern consistent across Scorecard cols: ", end="")
    print("Yes" if null_pattern_consistent else "Inconsistent null patterns!")
    if not null_pattern_consistent:
        mismatch_count = (med_null != pct25_null).sum()
        print(f"  {mismatch_count} rows have inconsistent nulls between earnings_med and earnings_pct25")
        issues.append(("WARNING", f"Inconsistent null pattern across Scorecard columns: {mismatch_count} rows"))
else:
    print("[SKIP] Check 10 — Missing Scorecard columns")

# ============================================================
# SPOT CHECKS
# ============================================================
print(f"\n{'=' * 60}")
print("SPOT CHECKS")
print(f"{'=' * 60}")

# --- Spot Check 11: Trace 3 specific unitids from Scorecard input to output ---
# Pick 3 unitids that exist in both analysis and scorecard
overlap_ids = sorted(list(analysis_ids & set(df_scorecard["unitid"].unique().to_list())))
if len(overlap_ids) >= 3:
    sample_ids = [overlap_ids[0], overlap_ids[len(overlap_ids)//2], overlap_ids[-1]]
    print(f"\nSpot Check 11 — Tracing 3 matched unitids: {sample_ids}")
    all_traced_ok = True
    for uid in sample_ids:
        sc_val = df_scorecard.filter(pl.col("unitid") == uid)["earnings_med"]
        out_val = df.filter(pl.col("unitid") == uid)["earnings_med"]
        sc_earn = sc_val[0] if len(sc_val) > 0 else None
        out_earn = out_val[0] if len(out_val) > 0 else None
        match = sc_earn == out_earn
        if not match:
            all_traced_ok = False
        print(f"  unitid {uid}: Scorecard=${sc_earn:,} -> Output=${out_earn:,} {'OK' if match else 'MISMATCH!'}")
    print(f"  [{'PASS' if all_traced_ok else 'FAIL'}] All 3 values traced correctly")
    if not all_traced_ok:
        issues.append(("BLOCKER", "Earnings value mismatch between Scorecard input and output"))
else:
    print("  [SKIP] Not enough overlapping unitids for spot check")

# --- Spot Check 12: Verify 3 unmatched unitids are absent from Scorecard ---
scorecard_ids = set(df_scorecard["unitid"].unique().to_list())
unmatched_ids = sorted(list(analysis_ids - scorecard_ids))
if len(unmatched_ids) >= 3:
    sample_unmatched = [unmatched_ids[0], unmatched_ids[len(unmatched_ids)//2], unmatched_ids[-1]]
    print(f"\nSpot Check 12 — Verifying 3 unmatched unitids have null earnings: {sample_unmatched}")
    all_null_ok = True
    for uid in sample_unmatched:
        out_row = df.filter(pl.col("unitid") == uid)
        if out_row.shape[0] > 0:
            earn = out_row["earnings_med"][0]
            is_null = earn is None
            if not is_null:
                all_null_ok = False
            print(f"  unitid {uid}: earnings_med = {earn} ({'null, OK' if is_null else 'NOT NULL — UNEXPECTED!'})")
        else:
            all_null_ok = False
            print(f"  unitid {uid}: NOT IN OUTPUT (expected in LEFT join!)")
    print(f"  [{'PASS' if all_null_ok else 'FAIL'}] Unmatched unitids have null earnings")
    if not all_null_ok:
        issues.append(("BLOCKER", "Unmatched unitids have non-null earnings — join logic error"))
else:
    print("  [SKIP] No unmatched unitids found")

# --- Spot Check 13: Earnings range ---
matched = df.filter(pl.col("earnings_med").is_not_null())
earn_min = matched["earnings_med"].min()
earn_max = matched["earnings_med"].max()
earn_median = matched["earnings_med"].median()
range_ok = earn_min >= 10000 and earn_max <= 140000  # Plan says $11K-$133K
print(f"\nSpot Check 13 — Earnings range: ${earn_min:,} to ${earn_max:,} (median ${earn_median:,.0f})")
print(f"  Plan expectation: $11K-$133K")
print(f"  [{'PASS' if range_ok else 'WARN'}] Range {'within' if range_ok else 'outside'} expected bounds")
if not range_ok:
    issues.append(("WARNING", f"Earnings range ${earn_min:,}-${earn_max:,} outside Plan $11K-$133K bounds"))

# --- Spot Check 14: Filter complement — who's missing? ---
# Characterize the 525 institutions without earnings
print(f"\nSpot Check 14 — Characterizing unmatched institutions (no earnings):")
unmatched_df = df.filter(pl.col("earnings_med").is_null())
matched_df = df.filter(pl.col("earnings_med").is_not_null())
print(f"  Total unmatched: {unmatched_df.shape[0]:,}")
print(f"  Unmatched by sector:")
if "inst_control" in unmatched_df.columns:
    for row in unmatched_df["inst_control"].value_counts().sort("inst_control").iter_rows(named=True):
        print(f"    {row['inst_control']}: {row['count']}")
print(f"  Unmatched by selectivity_band:")
for row in unmatched_df["selectivity_band"].value_counts().sort("selectivity_band").iter_rows(named=True):
    print(f"    {row['selectivity_band']}: {row['count']}")
# Check if unmatched institutions tend to be smaller
med_enrolled_unmatched = unmatched_df["enrollment_undergrad"].median() if "enrollment_undergrad" in unmatched_df.columns else None
med_enrolled_matched = matched_df["enrollment_undergrad"].median() if "enrollment_undergrad" in matched_df.columns else None
if med_enrolled_unmatched is not None and med_enrolled_matched is not None:
    print(f"  Median undergrad enrollment: unmatched={med_enrolled_unmatched:,.0f}, matched={med_enrolled_matched:,.0f}")

# --- Spot Check 15: Independent match count cross-reference ---
# Independently compute how many analysis unitids exist in Scorecard
independent_match = len(analysis_ids & scorecard_ids)
output_non_null = df.filter(pl.col("earnings_med").is_not_null()).shape[0]
crossref_ok = independent_match == output_non_null
print(f"\nSpot Check 15 — Independent match count: {independent_match:,} vs output non-null: {output_non_null:,}")
print(f"  [{'PASS' if crossref_ok else 'FAIL'}] Counts {'match' if crossref_ok else 'MISMATCH'}")
if not crossref_ok:
    issues.append(("WARNING", f"Independent match count ({independent_match}) != output non-null ({output_non_null})"))

# --- Summary ---
print(f"\n{'=' * 60}")
print("QA SUMMARY")
print(f"{'=' * 60}")

blockers = [i for i in issues if i[0] == "BLOCKER"]
warnings = [i for i in issues if i[0] == "WARNING"]
infos = [i for i in issues if i[0] == "INFO"]

print(f"BLOCKERs: {len(blockers)}")
for b in blockers:
    print(f"  - {b[1]}")
print(f"WARNINGs: {len(warnings)}")
for w in warnings:
    print(f"  - {w[1]}")
print(f"INFOs: {len(infos)}")
for i in infos:
    print(f"  - {i[1]}")

if blockers:
    severity = "BLOCKER"
elif warnings:
    severity = "WARNING"
else:
    severity = "PASSED"

print(f"\nQA RESULT: {severity}")
print("=" * 60)

# --- Data Profiling (for cr2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFirst 5 rows (select columns):")
print(df.select(["unitid", "inst_name", "selectivity_band", "grad_rate_150pct",
                  "admission_rate", "earnings_med"]).head(5))

print("\nDescriptive statistics (earnings columns):")
print(df.select(["earnings_med", "earnings_pct25", "earnings_pct75", "count_working"]).describe())

print("\nNull counts per Scorecard column:")
for col in scorecard_added:
    if col in df.columns:
        nc = df[col].null_count()
        print(f"  {col}: {nc:,} nulls ({nc/df.shape[0]*100:.1f}%)")

print("\nSelectivity band distribution:")
print(df["selectivity_band"].value_counts().sort("selectivity_band"))

print("\nEarnings by selectivity band (non-null only):")
earnings_by_band = (
    df.filter(pl.col("earnings_med").is_not_null())
    .group_by("selectivity_band")
    .agg(
        pl.col("earnings_med").median().alias("median_earnings"),
        pl.col("earnings_med").mean().alias("mean_earnings"),
        pl.col("earnings_med").min().alias("min_earnings"),
        pl.col("earnings_med").max().alias("max_earnings"),
        pl.len().alias("n"),
    )
    .sort("selectivity_band")
)
print(earnings_by_band)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:27:50
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/stage7_05_cr1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA INSPECTION: Stage 7 Step 10.1 — join-scorecard
# ============================================================
# Output loaded: 2,528 rows x 37 cols
# Input analysis loaded: 2,528 rows x 26 cols
# Input scorecard loaded: 5,376 rows x 14 cols
# 
# [PASS] Check 1 — Schema: All 37 expected columns present
# [PASS] Check 2 — Row count: 2,528 (expected exactly 2,528)
# [FAIL] Check 3 — Distributions: year: all same value (2020); institution_level: all same value (4); cohort_year: all same value (2015)
# [PASS] Check 4 — Coded values: None remain
# [PASS] Check 5 — Critical nulls (original cols): No new nulls
# 
# ============================================================
# SCRIPT-SPECIFIC CHECKS
# ============================================================
# 
# [PASS] Check 6 — [Counterfactual] No fan-out: 2,528 unique unitids / 2,528 rows
# 
# [INFO] Check 7 — [Semantic] Coverage by selectivity band:
#   Highly Selective: 65 / 73 (89.0%)
#   Less Selective/Open: 1,224 / 1,695 (72.2%)
#   Moderately Selective: 556 / 586 (94.9%)
#   Selective: 158 / 174 (90.8%)
#   Pattern note: Highly Selective (89.0%) > Less Selective/Open (72.2%)
#   This is INVERTED from Plan Risk Register expectation (30-50% elite, 80%+ less selective)
#   Explanation: Plan cites raw Scorecard Title IV coverage; our subset is IPEDS 4-yr only
# 
# [PASS] Check 8 — [Boundary] 8-digit branch IDs not in analysis: 0 branch campus unitids matched analysis
# [PASS] Check 9 — [Absence] No leaked Scorecard columns: Clean
# [WARN] Check 10 — [Downstream] Null pattern consistent across Scorecard cols: Inconsistent null patterns!
#   20 rows have inconsistent nulls between earnings_med and earnings_pct25
# 
# ============================================================
# SPOT CHECKS
# ============================================================
# 
# Spot Check 11 — Tracing 3 matched unitids: [100654, 192110, 492962]
#   unitid 100654: Scorecard=$36,339 -> Output=$36,339 OK
#   unitid 192110: Scorecard=$37,960 -> Output=$37,960 OK
#   unitid 492962: Scorecard=$46,035 -> Output=$46,035 OK
#   [PASS] All 3 values traced correctly
# 
# Spot Check 12 — Verifying 3 unmatched unitids have null earnings: [100733, 220792, 496070]
#   unitid 100733: earnings_med = None (null, OK)
#   unitid 220792: earnings_med = None (null, OK)
#   unitid 496070: earnings_med = None (null, OK)
#   [PASS] Unmatched unitids have null earnings
# 
# Spot Check 13 — Earnings range: $13,438 to $132,969 (median $47,107)
#   Plan expectation: $11K-$133K
#   [PASS] Range within expected bounds
# 
# Spot Check 14 — Characterizing unmatched institutions (no earnings):
#   Total unmatched: 525
#   Unmatched by sector:
#     1: 73
#     2: 452
#   Unmatched by selectivity_band:
#     Highly Selective: 8
#     Less Selective/Open: 471
#     Moderately Selective: 30
#     Selective: 16
#   Median undergrad enrollment: unmatched=88, matched=2,071
# 
# Spot Check 15 — Independent match count: 2,003 vs output non-null: 2,003
#   [PASS] Counts match
# 
# ============================================================
# QA SUMMARY
# ============================================================
# BLOCKERs: 0
# WARNINGs: 4
#   - Distribution issue: year: all same value (2020)
#   - Distribution issue: institution_level: all same value (4)
#   - Distribution issue: cohort_year: all same value (2015)
#   - Inconsistent null pattern across Scorecard columns: 20 rows
# INFOs: 1
#   - Coverage pattern inverted vs Plan Risk Register — expected for IPEDS 4-yr subset
# 
# QA RESULT: WARNING
# ============================================================
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# First 5 rows (select columns):
# shape: (5, 6)
# ┌────────┬───────────────┬──────────────────────┬──────────────────┬────────────────┬──────────────┐
# │ unitid ┆ inst_name     ┆ selectivity_band     ┆ grad_rate_150pct ┆ admission_rate ┆ earnings_med │
# │ ---    ┆ ---           ┆ ---                  ┆ ---              ┆ ---            ┆ ---          │
# │ i64    ┆ str           ┆ str                  ┆ f64              ┆ f64            ┆ i64          │
# ╞════════╪═══════════════╪══════════════════════╪══════════════════╪════════════════╪══════════════╡
# │ 100654 ┆ Alabama A & M ┆ Less Selective/Open  ┆ 28.1             ┆ 0.896499       ┆ 36339        │
# │        ┆ University    ┆                      ┆                  ┆                ┆              │
# │ 100663 ┆ University of ┆ Less Selective/Open  ┆ 62.4             ┆ 0.805986       ┆ 46990        │
# │        ┆ Alabama at    ┆                      ┆                  ┆                ┆              │
# │        ┆ Birmi…        ┆                      ┆                  ┆                ┆              │
# │ 100690 ┆ Amridge       ┆ Less Selective/Open  ┆ 66.7             ┆ null           ┆ 37895        │
# │        ┆ University    ┆                      ┆                  ┆                ┆              │
# │ 100706 ┆ University of ┆ Less Selective/Open  ┆ 60.7             ┆ 0.771103       ┆ 54361        │
# │        ┆ Alabama in    ┆                      ┆                  ┆                ┆              │
# │        ┆ Hunts…        ┆                      ┆                  ┆                ┆              │
# │ 100724 ┆ Alabama State ┆ Less Selective/Open  ┆ 28.4             ┆ 0.988758       ┆ 32084        │
# │        ┆ University    ┆                      ┆                  ┆                ┆              │
# └────────┴───────────────┴──────────────────────┴──────────────────┴────────────────┴──────────────┘
# 
# Descriptive statistics (earnings columns):
# shape: (9, 5)
# ┌────────────┬──────────────┬────────────────┬────────────────┬───────────────┐
# │ statistic  ┆ earnings_med ┆ earnings_pct25 ┆ earnings_pct75 ┆ count_working │
# │ ---        ┆ ---          ┆ ---            ┆ ---            ┆ ---           │
# │ str        ┆ f64          ┆ f64            ┆ f64            ┆ f64           │
# ╞════════════╪══════════════╪════════════════╪════════════════╪═══════════════╡
# │ count      ┆ 2003.0       ┆ 1983.0         ┆ 1995.0         ┆ 2003.0        │
# │ null_count ┆ 525.0        ┆ 545.0          ┆ 533.0          ┆ 525.0         │
# │ mean       ┆ 48865.581628 ┆ 31249.618759   ┆ 70996.290727   ┆ 1803.69346    │
# │ std        ┆ 14606.904679 ┆ 10742.091519   ┆ 20847.99472    ┆ 3179.10795    │
# │ min        ┆ 13438.0      ┆ 2474.0         ┆ 23435.0        ┆ 16.0          │
# │ 25%        ┆ 39704.0      ┆ 24035.0        ┆ 58230.0        ┆ 319.0         │
# │ 50%        ┆ 47107.0      ┆ 30419.0        ┆ 67626.0        ┆ 727.0         │
# │ 75%        ┆ 55688.0      ┆ 36624.0        ┆ 80481.0        ┆ 1801.0        │
# │ max        ┆ 132969.0     ┆ 88530.0        ┆ 175675.0       ┆ 30991.0       │
# └────────────┴──────────────┴────────────────┴────────────────┴───────────────┘
# 
# Null counts per Scorecard column:
#   earnings_med: 525 nulls (20.8%)
#   earnings_pct25: 545 nulls (21.6%)
#   earnings_pct75: 533 nulls (21.1%)
#   count_working: 525 nulls (20.8%)
#   count_working_lowinc: 587 nulls (23.2%)
#   count_working_midinc: 624 nulls (24.7%)
#   count_working_highinc: 779 nulls (30.8%)
#   count_working_dep: 576 nulls (22.8%)
#   count_working_ind: 809 nulls (32.0%)
#   count_working_female: 592 nulls (23.4%)
#   count_working_male: 637 nulls (25.2%)
# 
# Selectivity band distribution:
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
# Earnings by selectivity band (non-null only):
# shape: (4, 6)
# ┌──────────────────────┬─────────────────┬───────────────┬──────────────┬──────────────┬──────┐
# │ selectivity_band     ┆ median_earnings ┆ mean_earnings ┆ min_earnings ┆ max_earnings ┆ n    │
# │ ---                  ┆ ---             ┆ ---           ┆ ---          ┆ ---          ┆ ---  │
# │ str                  ┆ f64             ┆ f64           ┆ i64          ┆ i64          ┆ u32  │
# ╞══════════════════════╪═════════════════╪═══════════════╪══════════════╪══════════════╪══════╡
# │ Highly Selective     ┆ 75642.0         ┆ 76160.984615  ┆ 37960        ┆ 132969       ┆ 65   │
# │ Less Selective/Open  ┆ 45600.5         ┆ 46528.401961  ┆ 13438        ┆ 123966       ┆ 1224 │
# │ Moderately Selective ┆ 48288.0         ┆ 50076.057554  ┆ 19513        ┆ 107974       ┆ 556  │
# │ Selective            ┆ 49199.5         ┆ 51482.556962  ┆ 20682        ┆ 106595       ┆ 158  │
# └──────────────────────┴─────────────────┴───────────────┴──────────────┴──────────────┴──────┘
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
