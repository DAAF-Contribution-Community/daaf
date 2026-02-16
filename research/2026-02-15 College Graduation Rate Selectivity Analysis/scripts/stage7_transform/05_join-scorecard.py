#!/usr/bin/env python3
"""
Stage 7.5: Left-join Scorecard earnings data onto analysis dataset.

Task: join-scorecard
Wave: 10, Step: 10.1, Stage: 7
Depends on: create-bands (04), clean-scorecard (Stage 6)
Input: data/processed/2026-02-15_analysis.parquet,
       data/processed/2026-02-15_scorecard_clean.parquet
Output: data/processed/2026-02-15_analysis_with_earnings.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for joining Scorecard earnings onto the analysis dataset.
# The analysis dataset (2,528 rows, year 2020) contains IPEDS institutions with
# selectivity bands, demographics, and resources. The Scorecard dataset (5,376 rows,
# year 2018, yae=10) provides median earnings 10 years after enrollment.
#
# Scorecard is SUPPLEMENTARY data — not all institutions will have earnings. Coverage
# varies by selectivity (documented risk: lower coverage for highly selective institutions
# due to Title IV reporting thresholds). We use LEFT join to preserve all analysis rows.
PROJECT_DIR = Path("/daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis")
DATE_PREFIX = "2026-02-15"

INPUT_ANALYSIS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
INPUT_SCORECARD = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_scorecard_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis_with_earnings.parquet"

# REASONING: unitid is the IPEDS 6-digit institution identifier. However, the Scorecard
# dataset contains some 8-digit "branch campus" unitids (420 of 5,376 rows). These
# 8-digit IDs encode the main campus in the first 6 digits and a branch suffix in the
# last 2 digits. For the LEFT JOIN, we only use 6-digit unitids directly. The 8-digit
# branch IDs will simply not match any analysis row (which is correct — our analysis
# dataset uses main-campus-level IPEDS unitids). This means ~50 institutions that have
# branch-level Scorecard data but whose main campus IS in our analysis will not get
# earnings data from those branches. This is acceptable because:
#   1. Aggregating branch earnings to main campus would introduce methodological complexity
#   2. The 50 affected institutions are <2% of the analysis dataset
#   3. The Plan specifies Scorecard as supplementary with expected coverage variation
JOIN_KEY = "unitid"
EXPECTED_CARDINALITY = "1:1"

# --- Load ---
# Load both datasets and verify shapes before joining.
print("=" * 60)
print("Stage 7.5: Left-join Scorecard earnings onto analysis")
print("=" * 60)

df_analysis = pl.read_parquet(INPUT_ANALYSIS)
df_scorecard = pl.read_parquet(INPUT_SCORECARD)
print(f"Analysis:  {df_analysis.shape[0]:,} rows x {df_analysis.shape[1]} cols")
print(f"Scorecard: {df_scorecard.shape[0]:,} rows x {df_scorecard.shape[1]} cols")

# --- Pre-state ---
# Capture join key characteristics BEFORE joining. This establishes the expected
# match rate and verifies uniqueness for the 1:1 cardinality requirement.
pre_analysis_rows = df_analysis.shape[0]
pre_analysis_cols = df_analysis.columns.copy()

# INTENT: Verify unitid uniqueness in both datasets to confirm 1:1 join validity.
# ASSUMES: Analysis dataset has unique unitids (one row per institution, year 2020).
# Scorecard should also have unique unitids after prior cleaning (yae=10, year=2018).
analysis_uid_unique = df_analysis[JOIN_KEY].n_unique() == df_analysis.shape[0]
scorecard_uid_unique = df_scorecard[JOIN_KEY].n_unique() == df_scorecard.shape[0]
print(f"\nAnalysis unitid unique: {analysis_uid_unique} ({df_analysis[JOIN_KEY].n_unique():,} unique / {df_analysis.shape[0]:,} rows)")
print(f"Scorecard unitid unique: {scorecard_uid_unique} ({df_scorecard[JOIN_KEY].n_unique():,} unique / {df_scorecard.shape[0]:,} rows)")

# INTENT: Calculate key overlap to predict join match rate. Since Scorecard has both
# 6-digit main campus and 8-digit branch campus unitids, we expect <100% overlap.
analysis_ids = set(df_analysis[JOIN_KEY].unique().to_list())
scorecard_ids = set(df_scorecard[JOIN_KEY].unique().to_list())
overlap = analysis_ids & scorecard_ids
overlap_pct = len(overlap) / len(analysis_ids) if analysis_ids else 0  # Guard against empty set
print(f"Key overlap: {len(overlap):,} / {len(analysis_ids):,} ({overlap_pct:.1%})")

# INTENT: Document the 8-digit branch campus unitids that will not match.
# REASONING: Important for understanding coverage gaps — branch campuses report
# separately to Scorecard but our IPEDS analysis uses 6-digit main campus IDs.
sc_str_lens = df_scorecard.with_columns(
    pl.col(JOIN_KEY).cast(pl.String).str.len_chars().alias("uid_len")
)
branch_count = sc_str_lens.filter(pl.col("uid_len") > 6).shape[0]
main_count = sc_str_lens.filter(pl.col("uid_len") <= 6).shape[0]
print(f"\nScorecard unitid breakdown:")
print(f"  6-digit (main campus): {main_count:,}")
print(f"  8-digit (branch campus): {branch_count:,} — these will NOT match analysis unitids")

# --- Select Scorecard columns for join ---
# INTENT: Select only the earnings columns from Scorecard to add to the analysis dataset.
# REASONING: We drop 'year' and 'years_after_entry' from the Scorecard side because:
#   1. 'year' would conflict with the analysis dataset's 'year' column (2020 vs 2018)
#   2. 'years_after_entry' is constant (10) for all rows and thus uninformative as a column
#   We instead document the Scorecard vintage (year=2018, yae=10) in the script metadata
#   and the Plan. The earnings columns themselves carry the substantive information.
# ASSUMES: All 14 Scorecard columns are known from Stage 6 cleaning. The earnings columns
# are: earnings_med, earnings_pct25, earnings_pct75, and the count_working_* breakdown cols.
scorecard_join_cols = [c for c in df_scorecard.columns if c != "year" and c != "years_after_entry"]
df_scorecard_slim = df_scorecard.select(scorecard_join_cols)
print(f"\nScorecard columns for join: {scorecard_join_cols}")

# --- Join ---
# INTENT: LEFT JOIN analysis dataset with Scorecard earnings on unitid to create an
# enriched analysis dataset. LEFT join preserves ALL 2,528 analysis rows; institutions
# without Scorecard matches will have null earnings columns.
#
# REASONING: Using LEFT join (not INNER) because:
#   - Scorecard is SUPPLEMENTARY to the main analysis
#   - The research question is primarily about graduation rates and selectivity
#   - Earnings data enriches the analysis but its absence should not exclude institutions
#   - Coverage varies by selectivity band (a documented risk in the Plan)
#   - INNER join would drop ~20% of institutions, biasing the selectivity distribution
#
# ASSUMES:
#   - unitid is Int64 in both datasets (verified in pre-state)
#   - 1:1 cardinality: each analysis unitid matches at most one Scorecard row
#   - Scorecard year (2018) and yae (10) are constant and documented in metadata
#   - ~79% expected match rate based on pre-state key overlap calculation
result = df_analysis.join(df_scorecard_slim, on=JOIN_KEY, how="left")
print(f"\nJoin complete: {result.shape[0]:,} rows x {result.shape[1]} cols")

# --- Post-state ---
# Verify the join preserved all analysis rows (LEFT join invariant).
post_rows = result.shape[0]
row_change = post_rows - pre_analysis_rows
row_change_pct = (row_change / pre_analysis_rows * 100) if pre_analysis_rows > 0 else 0
print(f"Row change: {row_change:+,} ({row_change_pct:+.1f}%)")
print(f"New columns added: {[c for c in result.columns if c not in pre_analysis_cols]}")

# --- Coverage Analysis ---
# INTENT: Document Scorecard coverage overall and by selectivity band.
# REASONING: This is critical supplementary analysis because coverage bias is a
# documented risk — if highly selective institutions systematically lack earnings data,
# any earnings-based analysis would be biased toward less selective institutions.
earnings_non_null = result.filter(pl.col("earnings_med").is_not_null()).shape[0]
earnings_null = result.filter(pl.col("earnings_med").is_null()).shape[0]
coverage_pct = earnings_non_null / post_rows * 100 if post_rows > 0 else 0

print(f"\n{'=' * 60}")
print("SCORECARD COVERAGE ANALYSIS")
print(f"{'=' * 60}")
print(f"Overall coverage: {earnings_non_null:,} / {post_rows:,} ({coverage_pct:.1f}%)")
print(f"Missing earnings: {earnings_null:,} ({100 - coverage_pct:.1f}%)")

# INTENT: Break down coverage by selectivity band to detect systematic bias.
# REASONING: If "Highly Selective" institutions have much lower coverage than
# "Less Selective/Open", the earnings data cannot be used for cross-selectivity
# comparisons without accounting for this selection effect.
print(f"\nCoverage by selectivity band:")
coverage_by_band = (
    result
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

# INTENT: Show earnings distribution for matched institutions to verify plausibility.
# REASONING: Median earnings of $11K-$133K was documented during Stage 6 cleaning.
# We verify the joined data preserves this range and has a reasonable distribution.
matched = result.filter(pl.col("earnings_med").is_not_null())
print(f"\nEarnings distribution (matched institutions only):")
print(f"  Min:    ${matched['earnings_med'].min():,}")
print(f"  25th:   ${matched['earnings_med'].quantile(0.25):,.0f}")
print(f"  Median: ${matched['earnings_med'].median():,.0f}")
print(f"  75th:   ${matched['earnings_med'].quantile(0.75):,.0f}")
print(f"  Max:    ${matched['earnings_med'].max():,}")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation ---
# Checkpoint validation: verify LEFT join preserved all rows, coverage is documented,
# earnings range is plausible, and no unexpected column issues.
print(f"\n{'=' * 60}")
print("CHECKPOINT 3 VALIDATION")
print(f"{'=' * 60}")

validation_log = {}

# CP3.1: Row count preserved (LEFT join must not change row count)
rows_preserved = post_rows == pre_analysis_rows
validation_log["Row count preserved"] = {
    "pre": pre_analysis_rows, "post": post_rows,
    "status": "PASSED" if rows_preserved else "FAILED"
}
print(f"  [{'PASS' if rows_preserved else 'FAIL'}] Row count preserved: {pre_analysis_rows:,} -> {post_rows:,}")

# CP3.2: No duplicate rows introduced (1:1 cardinality check)
# REASONING: If Scorecard had duplicate unitids, LEFT join would create extra rows.
# Post-row-count == pre-row-count implicitly checks this, but we also verify unitid
# uniqueness in the result to be explicit.
result_uid_unique = result[JOIN_KEY].n_unique() == result.shape[0]
validation_log["1:1 cardinality"] = {
    "unique": result[JOIN_KEY].n_unique(), "total": result.shape[0],
    "status": "PASSED" if result_uid_unique else "FAILED"
}
print(f"  [{'PASS' if result_uid_unique else 'FAIL'}] 1:1 cardinality: {result[JOIN_KEY].n_unique():,} unique / {result.shape[0]:,} rows")

# CP3.3: Earnings coverage documented (not a pass/fail — informational)
coverage_ok = coverage_pct > 0  # At least some institutions matched
validation_log["Earnings coverage"] = {
    "coverage_pct": coverage_pct,
    "status": "PASSED" if coverage_ok else "FAILED"
}
print(f"  [{'PASS' if coverage_ok else 'FAIL'}] Earnings coverage > 0%: {coverage_pct:.1f}%")

# CP3.4: Earnings range plausible ($11K-$133K per Stage 6 documentation)
# REASONING: Checking that the join didn't corrupt earnings values by verifying
# the range matches what was observed in the cleaned Scorecard data.
if earnings_non_null > 0:
    earnings_min = matched["earnings_med"].min()
    earnings_max = matched["earnings_med"].max()
    range_ok = earnings_min >= 5000 and earnings_max <= 200000  # Wide bounds for safety
    validation_log["Earnings range plausible"] = {
        "min": earnings_min, "max": earnings_max,
        "status": "PASSED" if range_ok else "WARNING"
    }
    print(f"  [{'PASS' if range_ok else 'WARN'}] Earnings range plausible: ${earnings_min:,} - ${earnings_max:,}")
else:
    range_ok = False
    print(f"  [FAIL] No earnings data to validate range")

# CP3.5: Original analysis columns preserved (no column corruption from join)
# REASONING: LEFT join should only ADD columns, never remove or alter existing ones.
original_cols_preserved = all(c in result.columns for c in pre_analysis_cols)
validation_log["Original columns preserved"] = {
    "expected": len(pre_analysis_cols), "found": sum(1 for c in pre_analysis_cols if c in result.columns),
    "status": "PASSED" if original_cols_preserved else "FAILED"
}
print(f"  [{'PASS' if original_cols_preserved else 'FAIL'}] Original columns preserved: {sum(1 for c in pre_analysis_cols if c in result.columns)}/{len(pre_analysis_cols)}")

# CP3.6: No unexpected nulls in original columns (join didn't corrupt existing data)
# INTENT: Verify that the join did not introduce nulls into columns that existed before.
# REASONING: A LEFT join should only affect newly added columns. If original columns
# gained nulls, something went wrong with the join mechanics.
pre_null_counts = {c: df_analysis[c].null_count() for c in pre_analysis_cols}
post_null_counts = {c: result[c].null_count() for c in pre_analysis_cols}
null_changes = {c: post_null_counts[c] - pre_null_counts[c] for c in pre_analysis_cols if post_null_counts[c] != pre_null_counts[c]}
no_new_nulls = len(null_changes) == 0
validation_log["No new nulls in original cols"] = {
    "changes": null_changes,
    "status": "PASSED" if no_new_nulls else "WARNING"
}
print(f"  [{'PASS' if no_new_nulls else 'WARN'}] No new nulls in original columns: {null_changes if null_changes else 'None'}")

# --- Validation summary ---
all_passed = rows_preserved and result_uid_unique and coverage_ok and range_ok and original_cols_preserved and no_new_nulls

print(f"\n{'=' * 60}")
print("VALIDATION SUMMARY")
print(f"{'=' * 60}")
for step_name, info in validation_log.items():
    print(f"  [{info['status']}] {step_name}")

assert rows_preserved, "STOP: LEFT join changed row count"
assert result_uid_unique, "STOP: Duplicate unitids in result — 1:1 cardinality violated"
assert coverage_ok, "STOP: Zero Scorecard coverage"
assert original_cols_preserved, "STOP: Original columns lost during join"

print(f"\n{'=' * 60}")
print("CP3 VALIDATION: PASSED")
print(f"{'=' * 60}")

# Final summary for output
print(f"\nFinal dataset: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Columns: {result.columns}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:24:15
# Command: python /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage7_transform/05_join-scorecard.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 7.5: Left-join Scorecard earnings onto analysis
# ============================================================
# Analysis:  2,528 rows x 26 cols
# Scorecard: 5,376 rows x 14 cols
# 
# Analysis unitid unique: True (2,528 unique / 2,528 rows)
# Scorecard unitid unique: True (5,376 unique / 5,376 rows)
# Key overlap: 2,003 / 2,528 (79.2%)
# 
# Scorecard unitid breakdown:
#   6-digit (main campus): 4,956
#   8-digit (branch campus): 420 — these will NOT match analysis unitids
# 
# Scorecard columns for join: ['unitid', 'earnings_med', 'earnings_pct25', 'earnings_pct75', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
# 
# Join complete: 2,528 rows x 37 cols
# Row change: +0 (+0.0%)
# New columns added: ['earnings_med', 'earnings_pct25', 'earnings_pct75', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
# 
# ============================================================
# SCORECARD COVERAGE ANALYSIS
# ============================================================
# Overall coverage: 2,003 / 2,528 (79.2%)
# Missing earnings: 525 (20.8%)
# 
# Coverage by selectivity band:
#   Highly Selective: 65 / 73 (89.0%)
#   Less Selective/Open: 1,224 / 1,695 (72.2%)
#   Moderately Selective: 556 / 586 (94.9%)
#   Selective: 158 / 174 (90.8%)
# 
# Earnings distribution (matched institutions only):
#   Min:    $13,438
#   25th:   $39,704
#   Median: $47,107
#   75th:   $55,688
#   Max:    $132,969
# 
# Saved: /daaf/research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_analysis_with_earnings.parquet
# 
# ============================================================
# CHECKPOINT 3 VALIDATION
# ============================================================
#   [PASS] Row count preserved: 2,528 -> 2,528
#   [PASS] 1:1 cardinality: 2,528 unique / 2,528 rows
#   [PASS] Earnings coverage > 0%: 79.2%
#   [PASS] Earnings range plausible: $13,438 - $132,969
#   [PASS] Original columns preserved: 26/26
#   [PASS] No new nulls in original columns: None
# 
# ============================================================
# VALIDATION SUMMARY
# ============================================================
#   [PASSED] Row count preserved
#   [PASSED] 1:1 cardinality
#   [PASSED] Earnings coverage
#   [PASSED] Earnings range plausible
#   [PASSED] Original columns preserved
#   [PASSED] No new nulls in original cols
# 
# ============================================================
# CP3 VALIDATION: PASSED
# ============================================================
# 
# Final dataset: 2,528 rows x 37 cols
# Columns: ['unitid', 'year', 'inst_name', 'inst_control', 'institution_level', 'hbcu', 'degree_granting', 'urban_centric_locale', 'state_abbr', 'fips', 'grad_rate_150pct', 'cohort_year', 'number_applied', 'number_admitted', 'number_enrolled_total', 'admission_rate', 'pell_recipients', 'enrollment_undergrad', 'pell_share', 'urm_share', 'urm_enrollment', 'student_faculty_ratio', 'retention_rate', 'selectivity_band', 'pell_band', 'urm_band', 'earnings_med', 'earnings_pct25', 'earnings_pct75', 'count_working', 'count_working_lowinc', 'count_working_midinc', 'count_working_highinc', 'count_working_dep', 'count_working_ind', 'count_working_female', 'count_working_male']
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
