# Validation Checkpoints Reference

This document provides Python code templates for all four validation checkpoints, along with checkpoint classification for determining human involvement levels.

---

## File-First Execution Context

**IMPORTANT:** Validation checkpoint code runs **inside scripts**, not interactively.

The workflow is:
1. Write script to `scripts/stage{N}_{type}/` including validation code
2. Execute as a single Bash call: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py` (automatically captures output and appends execution log)
3. Validation results get automatically embedded in scripts as comments
4. Checkpoint status (PASSED/FAILED) is captured in the embedded execution log

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol, complete script format, and checkpoint integration.

---

## Checkpoint Overview

### Primary Checkpoints (CP1-CP4)

| Checkpoint | When | Purpose | STOP Threshold |
|------------|------|---------|----------------|
| **CP1** | After data fetch | Verify data structure | Empty data, >90% missing |
| **CP2** | After cleaning | Verify data quality | >50% suppression, >90% loss |
| **CP3** | After transformation | Verify data integrity | >90% row loss, unexpected NAs |
| **CP4** | Before output | Verify completeness | Missing requirements |

### Secondary Checkpoints (QA1-QA4b)

QA checkpoints run AFTER primary checkpoints, providing independent secondary verification via code-reviewer agent. CP checkpoints validate operations; QA checkpoints validate outputs and methodology alignment.

**See:** `agent_reference/QA_CHECKPOINTS.md` for QA1-QA4b definitions, BLOCKER thresholds, severity classification, and complete QA checkpoint documentation.

---

## Checkpoint Classification System

Not all checkpoints require the same level of human involvement. Use this classification to determine the appropriate interaction pattern.

### checkpoint:auto (Default)

**Definition:** Claude executes and validates automatically. No human interaction needed unless a STOP condition is triggered.

**Applies To:**
- CP1 post-fetch validation (when data is returned successfully)
- CP2 suppression rate calculation (when rate < 30%)
- CP3 transformation validation (when row counts match expectations)
- CP4 pre-output validation (when all artifacts exist)
- Most code execution
- File saving operations
- Standard data fetch or data access calls

**Behavior:**
1. Execute action
2. Validate result
3. If PASSED → Proceed automatically
4. If FAILED → Trigger STOP condition, escalate

**Example:**
```python
# CP1 auto-validation (inline)
# ... CP1 inline validation block runs here ...
# If cp1_passed is True → proceed automatically to next stage
# If cp1_passed is False → raises ValueError, STOP condition triggered
```

---

### checkpoint:human-verify (Report and Confirm)

**Definition:** Claude automates the action, then reports results for human confirmation before proceeding to the next major step.

**Applies To:**
- Unusual suppression patterns (30-50% range)
- Unexpected data distributions
- Methodology decisions with tradeoffs
- Final Report before delivery
- Data lag detection (≥3 years)
- COVID-19 data quality warnings
- First-time use of a data source
- Results that differ significantly from expectations

**Behavior:**
1. Execute action
2. Present results with full context
3. Ask: "The results show [X]. Should I proceed with this?"
4. Wait for explicit confirmation ("yes", "proceed", "confirmed")
5. Document decision in Plan
6. Proceed only after confirmation

**Example:**
```markdown
**Human Verification Required: Suppression Rate**

CP2 validation found a suppression rate of 38% for the enrollment variable.

**Context:**
- This is below the 50% STOP threshold
- However, it's higher than typical (usually 10-20%)
- Affected: 38,000 of 100,000 records

**Options:**
1. Proceed with 38% suppression (document in limitations)
2. Aggregate to district level (reduces suppression to ~5%)
3. Exclude suppressed variable from analysis

**Recommendation:** Option 1 is acceptable for this analysis type.

Should I proceed with the current suppression rate?
```

---

### checkpoint:decision (User Choice Required)

**Definition:** Multiple valid paths exist with meaningful tradeoffs. User must choose before execution can continue.

**Applies To:**
- Which data sources to prioritize when multiple are available
- How to handle edge cases (aggregate vs. exclude vs. impute)
- Visualization style preferences
- Scope adjustments when data is limited
- Methodology alternatives (e.g., mean vs. median)
- Geographic scope choices
- Year range adjustments

**Behavior:**
1. Present options with clear pros/cons
2. Do NOT proceed without selection
3. Ask: "Which approach would you prefer?"
4. Wait for explicit selection
5. Document choice and rationale in Plan
6. Execute selected option

**Example:**
```markdown
**Decision Required: Handling Missing Poverty Data**

The MEPS poverty data is missing for 15% of schools. Three valid approaches exist:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A | Exclude schools with missing data | Clean analysis | Loses 15% of sample |
| B | Impute using district averages | Preserves sample size | Introduces estimation |
| C | Aggregate to district level | Eliminates missingness | Loses school-level detail |

**Research Question Consideration:**
Your question asks about school-level patterns, which favors Option A or B.

Which approach would you prefer?
```

---

### checkpoint:human-action (User Must Execute)

**Definition:** Claude cannot automate this step. User must perform the action themselves.

**Applies To:**
- External system authentication (e.g., restricted databases)
- Manual data entry (e.g., institutional data requests)
- File downloads from restricted sources
- API key configuration
- Credential management
- Physical verification (e.g., confirming data received)
- Approval workflows outside Claude's access

**Behavior:**
1. Explain what needs to happen
2. Provide specific, actionable instructions
3. Ask user to confirm when action is complete
4. Verify action was successful before proceeding
5. Document completion in Plan

**Example:**
```markdown
**Human Action Required: Institutional Data Access**

The analysis requires restricted institutional data from [source].

**Required Steps:**
1. Navigate to [URL]
2. Log in with your institutional credentials
3. Request access to dataset [name]
4. Download the file when approved
5. Place the file in: `research/[project]/data/raw/`

**File Expected:** `institutional_data.csv` or `.xlsx`

Please confirm when the file is in place, and I'll continue with the analysis.
```

---

### Key Rule: Automation Preference

**If Claude CAN automate (data access call, file operation, code execution), Claude MUST automate.**

Reserve human checkpoints for genuinely necessary cases:

| Situation | Correct Classification |
|-----------|----------------------|
| data access call succeeded | checkpoint:auto |
| data access call failed after 3 retries | STOP condition |
| Suppression rate is 15% | checkpoint:auto |
| Suppression rate is 45% | checkpoint:human-verify |
| Suppression rate is 55% | STOP condition |
| Choose between 2 valid methodologies | checkpoint:decision |
| External login required | checkpoint:human-action |

---

### Classification Decision Tree

```
Can Claude execute this action automatically?
├─ NO → checkpoint:human-action
└─ YES → Continue

Does the action involve external credentials/access?
├─ YES → checkpoint:human-action
└─ NO → Continue

Is the result within normal/expected parameters?
├─ NO → Does it hit a STOP threshold?
│   ├─ YES → STOP condition (escalate)
│   └─ NO → checkpoint:human-verify
└─ YES → Continue

Are there multiple valid approaches requiring user preference?
├─ YES → checkpoint:decision
└─ NO → checkpoint:auto
```

---

### Checkpoint Classification by Stage

| Stage | Default Classification | Elevate to human-verify If |
|-------|----------------------|---------------------------|
| 5 (Fetch) | auto | Data lag ≥3 years, unexpected shape |
| 5-QA | auto | Methodology BLOCKER (escalate immediately) |
| 6 (Clean) | auto | Suppression 30-50%, unusual patterns |
| 6-QA | auto | Methodology BLOCKER (escalate immediately) |
| 7 (Transform) | auto | Row loss 50-90%, unexpected nulls |
| 7-QA | auto | Methodology BLOCKER (escalate immediately) |
| 8 (Analyze & Visualize) | auto | Results differ from expectations |
| 8-QA | auto | Methodology BLOCKER (escalate immediately) |
| 9 (Notebook) | auto | Execution warnings |
| 10 (QA Aggregation) | auto | Unresolved BLOCKERs, WARNING patterns, missing QA reviews |
| 11 (Report) | human-verify | Always verify before delivery |
| 12 (Final Review) | human-verify | Always verify before delivery |

**Note:** QA substages (5-QA through 8-QA) run SEPARATELY after EACH individual Stage 5-8 script execution — not once at stage end. For example: Stage 5 with 2 fetch scripts = 2 independent QA1 invocations, each reviewing one script's output in isolation before the next script begins. Technical BLOCKERs trigger revision attempts (max 2 per script); methodology BLOCKERs escalate immediately.

---

## CP1: Post-Fetch Validation

**When:** Immediately after retrieving data from data access mirror
**Purpose:** Verify data structure and completeness before proceeding

### Code Template

```python
import polars as pl

# --- CP1 Validation: Post-Fetch ---
# INTENT: Verify fetched data structure and completeness before proceeding
# to cleaning. Checks shape, required columns, year coverage, and missingness.
# ASSUMES: df is the fetched DataFrame, expected_rows/required_cols/expected_years
# are configured above from Plan specification.
print("\n" + "=" * 60)
print("CP1 VALIDATION: POST-FETCH")
print("=" * 60)

cp1_passed = True

# Shape check
print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} cols")
if df.shape[0] == 0:
    print("[FAIL] Empty dataset returned from data access mirror")
    cp1_passed = False
else:
    print(f"[PASS] {df.shape[0]:,} rows loaded")

# Row count reasonableness (compare to expected_rows)
if df.shape[0] > 0 and expected_rows > 0:
    ratio = df.shape[0] / expected_rows
    print(f"Expected ~{expected_rows:,} rows, got {df.shape[0]:,} (ratio: {ratio:.2f}x)")
    if ratio < 0.01:
        print(f"[WARN] Row count much lower than expected")
    elif ratio > 10:
        print(f"[WARN] Row count much higher than expected")

# Required columns
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    print(f"[FAIL] Missing columns: {missing_cols}")
    cp1_passed = False
else:
    print(f"[PASS] All {len(required_cols)} required columns present")

# Expected years
if year_col and expected_years and year_col in df.columns:
    present_years = sorted(df[year_col].unique().to_list())
    missing_years = [y for y in expected_years if y not in present_years]
    print(f"Years present: {present_years}")
    if missing_years:
        print(f"[WARN] Missing expected years: {missing_years}")

# Missingness check
for col in required_cols:
    if col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        if null_pct > 90:
            print(f"[FAIL] {col}: {null_pct:.1f}% null (>90% threshold)")
            cp1_passed = False
        elif null_pct > 50:
            print(f"[WARN] {col}: {null_pct:.1f}% null (high)")
        elif null_pct > 5:
            print(f"[WARN] {col}: {null_pct:.1f}% null")

# Year freshness (data lag detection)
if year_col and expected_years and year_col in df.columns:
    max_expected = max(expected_years)
    max_actual = df[year_col].max()
    if max_actual < max_expected:
        lag_years = max_expected - max_actual
        print(f"[WARN] Data lag: requested {max_expected}, latest available {max_actual} ({lag_years}-year lag)")

# Flag years data quality check (e.g., COVID-19 for education: [2020, 2021])
if FLAG_YEARS and expected_years and any(y in FLAG_YEARS for y in expected_years):
    print(f"[WARN] FLAG-YEARS: Analysis includes data from flagged years {FLAG_YEARS}. "
          "Document comparability concerns in limitations.")

print(f"\nCP1 VALIDATION: {'PASSED' if cp1_passed else 'FAILED'}")
print("=" * 60)

if not cp1_passed:
    raise ValueError("CP1 FAILED - see details above")
```

### Usage Notes

Adapt the inline code above to each fetch script. Set these variables before running:

```python
# Configure before CP1 block
expected_rows = 10000
required_cols = ["ncessch", "school_name", "enrollment", "year"]
expected_years = [2020, 2021, 2022]

# Domain configuration (from Plan's Domain Configuration section)
YEAR_COL = "year"              # From Plan domain config; set to None if no temporal dimension
FLAG_YEARS = [2020, 2021]      # From Plan domain config; empty list [] if N/A (e.g., education: COVID years)
# Education domain defaults: YEAR_COL = "year", FLAG_YEARS = [2020, 2021]

year_col = YEAR_COL
# df = <your fetched DataFrame>
```

---

## CP2: Post-Cleaning Validation

**When:** After applying coded value filters and suppression handling
**Purpose:** Verify data quality after cleaning operations

### Code Template

```python
# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning operations — confirm coded values
# are removed, suppression rates are within tolerance, and data loss is acceptable.
# ASSUMES: raw_df is pre-cleaning state, clean_df is post-cleaning state,
# key_variables lists the columns to validate.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True
max_suppression = SUPPRESSION_THRESHOLD  # From Plan domain config (education default: 0.5)
max_data_loss = 0.9    # 90% threshold

# Data loss check
raw_rows = len(raw_df)
clean_rows = len(clean_df)
rows_removed = raw_rows - clean_rows
loss_rate = rows_removed / raw_rows if raw_rows > 0 else 0

print(f"\nData Loss:")
print(f"  Raw rows:     {raw_rows:,}")
print(f"  Clean rows:   {clean_rows:,}")
print(f"  Rows removed: {rows_removed:,} ({loss_rate:.1%})")

if loss_rate > max_data_loss:
    print(f"[FAIL] Data loss rate {loss_rate:.1%} exceeds {max_data_loss:.0%}")
    cp2_passed = False
elif loss_rate > 0.5:
    print(f"[WARN] High data loss rate: {loss_rate:.1%}")
else:
    print(f"[PASS] Data loss rate {loss_rate:.1%} within tolerance")

# Suppression rate check (on raw data)
print(f"\nSuppression Rates (in raw data):")
for var in key_variables:
    if var in raw_df.columns:
        suppressed = (raw_df[var] == SUPPRESSION_CODE).sum() if SUPPRESSION_CODE is not None else 0
        supp_rate = suppressed / raw_rows if raw_rows > 0 else 0
        if supp_rate > max_suppression:
            print(f"[FAIL] {var}: {supp_rate:.1%} suppressed (>{max_suppression:.0%} threshold)")
            cp2_passed = False
        elif supp_rate > 0.2:
            print(f"[WARN] {var}: {supp_rate:.1%} suppressed (notable)")
        else:
            print(f"[PASS] {var}: {supp_rate:.1%} suppressed")

# Coded values remaining in clean data
print(f"\nCoded Values Check (clean data):")
coded_found = False
for var in key_variables:
    if var in clean_df.columns:
        dtype = clean_df[var].dtype
        if dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            coded = sum((clean_df[var] == c).sum() for c in CODED_MISSING_VALUES) if CODED_MISSING_VALUES else 0
            if coded > 0:
                print(f"[WARN] {var}: {coded} coded values remain")
                coded_found = True
if not coded_found:
    print("[PASS] No coded values remain in key variables")

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

if not cp2_passed:
    raise ValueError("CP2 FAILED - see details above")
```

### Usage Notes

Set these variables before the CP2 block:

```python
# Configure before CP2 block
# raw_df = <DataFrame before cleaning>
# clean_df = <DataFrame after cleaning>
key_variables = ["enrollment", "poverty_rate"]  # columns to check

# Domain configuration (from Plan's Domain Configuration section)
SUPPRESSION_CODE = -3              # From Plan domain config; None if domain has no suppression code
CODED_MISSING_VALUES = [-1, -2, -3]  # From Plan domain config; empty list [] if none
SUPPRESSION_THRESHOLD = 0.5        # From Plan domain config; 50% default for education
# Education domain defaults: SUPPRESSION_CODE = -3, CODED_MISSING_VALUES = [-1, -2, -3], SUPPRESSION_THRESHOLD = 0.5
```

---

## CP3: Post-Transformation Validation

**When:** After joins, aggregations, or derived variable creation
**Purpose:** Verify transformations preserved data integrity

### Code Template

```python
# --- CP3 Validation: Post-Transformation ---
# INTENT: Verify transformation preserved data integrity — check row counts,
# new nulls, and column preservation against Plan expectations.
# ASSUMES: input_df is pre-transform state, output_df is post-transform state,
# operation/expected_relationship/preserved_cols configured above.
print("\n" + "=" * 60)
print(f"CP3 VALIDATION: POST-TRANSFORMATION ({operation})")
print("=" * 60)

cp3_passed = True
max_row_loss = 0.9  # 90% threshold

input_rows = len(input_df)
output_rows = len(output_df)
row_change = output_rows - input_rows

print(f"\nRow Count Change:")
print(f"  Input rows:  {input_rows:,}")
print(f"  Output rows: {output_rows:,}")
print(f"  Change:      {row_change:+,}")
print(f"  Expected:    {expected_relationship}")

# Row count relationship check
if expected_relationship == "same" and row_change != 0:
    print(f"[WARN] Expected same row count, but changed by {row_change:+,}")
elif expected_relationship == "fewer" and row_change >= 0:
    print(f"[WARN] Expected fewer rows, but count changed by {row_change:+,}")
elif expected_relationship == "more" and row_change <= 0:
    print(f"[WARN] Expected more rows, but count changed by {row_change:+,}")
else:
    print(f"[PASS] Row count relationship matches expectation")

# Extreme row loss check
if input_rows > 0:
    loss_rate = 1 - (output_rows / input_rows)
    print(f"  Loss rate:   {loss_rate:.1%}")
    if loss_rate > max_row_loss:
        print(f"[FAIL] Row count dropped by {loss_rate:.1%} (>{max_row_loss:.0%} threshold)")
        cp3_passed = False

# New nulls introduced
print(f"\nNew Null Values:")
common_cols = set(input_df.columns) & set(output_df.columns)
new_nulls_found = False
for col in sorted(common_cols):
    input_nulls = input_df[col].null_count()
    output_nulls = output_df[col].null_count()
    new_nulls = output_nulls - input_nulls
    if new_nulls > 0:
        print(f"[WARN] {col}: {new_nulls:,} new nulls")
        new_nulls_found = True
if not new_nulls_found:
    print("[PASS] No new nulls introduced")

# Preserved columns check
if preserved_cols:
    missing = [c for c in preserved_cols if c not in output_df.columns]
    if missing:
        print(f"[FAIL] Preserved columns missing: {missing}")
        cp3_passed = False
    else:
        print(f"[PASS] All {len(preserved_cols)} preserved columns present")

print(f"\nCP3 VALIDATION: {'PASSED' if cp3_passed else 'FAILED'}")
print("=" * 60)

if not cp3_passed:
    raise ValueError("CP3 FAILED - see details above")
```

### Usage Notes

Set these variables before the CP3 block:

```python
# Configure before CP3 block
operation = "Join CCD + MEPS"           # description of the transformation
expected_relationship = "same"           # "same", "fewer", "more", "aggregated"
preserved_cols = ["ncessch", "year"]     # columns that must survive
# input_df = <DataFrame before transformation>
# output_df = <DataFrame after transformation>
```

---

## CP4: Pre-Output Validation

**When:** Before generating final outputs (Stage 11-12)
**Purpose:** Verify analysis is complete and consistent with Plan

### CP4 Detailed Sub-Checks

| Check | What It Validates | STOP Condition | Warning Condition |
|-------|-------------------|----------------|-------------------|
| **CP4.1: Required Columns** | All columns in Plan's output spec are present | Any missing required column | N/A |
| **CP4.2: Critical Nulls** | No nulls in columns marked critical in Plan | Any nulls in critical columns | >5% nulls in non-critical columns |
| **CP4.3: Analysis & Figure Generation** | All analysis outputs and figures in Plan's analysis/visualization specs exist | Any missing analysis output or figure file | File size <10KB (possibly empty) |
| **CP4.4: Report Sections** | All Plan-required report sections complete | Missing Executive Summary or Key Findings | Missing optional sections |
| **CP4.5: Plan Consistency** | Outputs match Plan commitments | Major deviation from Plan | Minor scope changes |
| **CP4.6: Research Outcomes** | Plan's Research Outcomes are addressed with evidence | Any Research Outcome not addressed | N/A |
| **CP4.7: Hypotheses Assessed** | Plan's Hypotheses (if any) are transparently assessed | N/A | Hypothesis assessed without adequate evidence |

### Plan Consistency Checks (CP4.5)

Verify these against the Plan document:

1. **Data Sources Match:** All sources in Plan were actually used
2. **Year Range Match:** Data covers the years specified in Plan
3. **Geographic Scope Match:** Analysis covers the geography in Plan
4. **Methodology Alignment:** Transformations followed Plan methodology
5. **Output Count Match:** Number of visualizations/tables matches Plan

### Research Outcomes Verification (CP4.6)

For each Research Outcome in the Plan:
1. Read the outcome statement
2. Verify the topic was rigorously investigated and reported
3. Document what evidence demonstrates thorough investigation
4. Mark as ADDRESSED or NOT ADDRESSED

**Example:**
```markdown
| Research Outcome | Evidence of Investigation | Status |
|------------------|--------------------------|--------|
| "Poverty rate variation across districts is characterized" | scatter plot in output/figures/, summary statistics in report, significance testing in analysis script | ADDRESSED |
| "Analysis dataset includes all required variables" | check analysis.parquet schema | ADDRESSED |
| "Data limitations are documented with scope implications" | Limitations section present in Report.md with suppression rate impact | ADDRESSED |
```

### Hypotheses Assessment (CP4.7)

For each Hypothesis in the Plan (if any):
1. Read the hypothesis statement and its basis
2. Verify it was assessed with adequate evidence
3. Mark as SUPPORTED / NOT SUPPORTED / PARTIALLY SUPPORTED
4. Either outcome is valid — a refuted hypothesis is a legitimate finding, not a failure

**Example:**
```markdown
| Hypothesis | Basis | Assessment | Evidence |
|------------|-------|------------|----------|
| "H1: Higher poverty rates are associated with lower enrollment growth" | Prior demographic literature | NOT SUPPORTED | r = 0.02, p = 0.74 — no significant relationship found. This null finding is reported as a key result. |
```

### Code Template

```python
from pathlib import Path

# --- CP4 Validation: Pre-Output ---
# INTENT: Final completeness check before generating deliverables — verify all
# required columns, figures, and report sections exist and are substantive.
# ASSUMES: analysis_df is the final dataset, required_columns/critical_columns/
# required_figures/figures_dir configured above from Plan specification.
print("\n" + "=" * 60)
print("CP4 VALIDATION: PRE-OUTPUT")
print("=" * 60)

cp4_passed = True

# CP4.1: Required columns present
missing_cols = [c for c in required_columns if c not in analysis_df.columns]
if missing_cols:
    print(f"[FAIL] Missing required columns: {missing_cols}")
    cp4_passed = False
else:
    print(f"[PASS] All {len(required_columns)} required columns present")

# CP4.2: No nulls in critical columns
print(f"\nCritical Column Nulls:")
for col in critical_columns:
    if col in analysis_df.columns:
        null_count = analysis_df[col].null_count()
        if null_count > 0:
            print(f"[FAIL] {col}: {null_count:,} nulls")
            cp4_passed = False
        else:
            print(f"[PASS] {col}: 0 nulls")

# CP4.3: Required figures exist
print(f"\nRequired Figures:")
missing_figures = []
for fig in required_figures:
    fig_path = figures_dir / fig
    if fig_path.exists():
        size_kb = fig_path.stat().st_size / 1024
        print(f"[PASS] {fig} ({size_kb:.1f} KB)")
        if size_kb < 10:
            print(f"[WARN] {fig} is suspiciously small")
    else:
        print(f"[FAIL] {fig} NOT FOUND")
        missing_figures.append(fig)
        cp4_passed = False

# CP4.4: Report sections (if provided)
if required_sections:
    print(f"\nRequired Report Sections: {required_sections}")
    print("  (Verify manually that each section has substantive content)")

print(f"\nCP4 VALIDATION: {'PASSED' if cp4_passed else 'FAILED'}")
print("=" * 60)

if not cp4_passed:
    raise ValueError("CP4 FAILED - see details above")
```

### Usage Notes

Set these variables before the CP4 block:

```python
# Configure before CP4 block
required_columns = ["ncessch", "enrollment", "poverty_rate"]
critical_columns = ["ncessch", "enrollment"]
required_figures = ["enrollment_trends.png", "poverty_scatter.png"]
figures_dir = Path("output/figures/")
required_sections = ["Executive Summary", "Key Findings", "Limitations"]
# analysis_df = <final analysis DataFrame>
```

---

## Join-Specific Validation

**Purpose:** Joins have unique failure modes (fan-out, data loss, key mismatch) that require specialized validation.

### Code Template

```python
# --- Join Validation ---
# INTENT: Validate join operation by checking cardinality, fan-out, row loss,
# and key matching. Joins are high-risk operations where silent data corruption
# (duplicate rows, unexpected nulls) can go undetected without explicit checks.
# ASSUMES: left_df/right_df are input DataFrames, result_df is join output,
# join_keys/expected_cardinality/join_type configured above.
print("\n" + "=" * 60)
print(f"JOIN VALIDATION ({join_type.upper()} JOIN)")
print("=" * 60)

join_passed = True

left_rows = len(left_df)
right_rows = len(right_df)
result_rows = len(result_df)

print(f"\nRow Counts:")
print(f"  Left side:  {left_rows:,}")
print(f"  Right side: {right_rows:,}")
print(f"  Result:     {result_rows:,}")
print(f"  Expected cardinality: {expected_cardinality}")

# Cardinality check
if expected_cardinality == "1:1":
    if join_type in ["inner", "left"] and result_rows > left_rows * 1.01:
        print(f"[WARN] Expected 1:1 but result has {result_rows - left_rows:,} more rows than left (fan-out?)")
    elif join_type == "right" and result_rows > right_rows * 1.01:
        print(f"[WARN] Expected 1:1 but result has {result_rows - right_rows:,} more rows than right")
    else:
        print(f"[PASS] Cardinality consistent with 1:1")
elif expected_cardinality == "1:many":
    if result_rows < right_rows:
        print(f"[WARN] Expected 1:many but result has fewer rows than right side")
    else:
        print(f"[PASS] Cardinality consistent with 1:many")
elif expected_cardinality == "many:1":
    if result_rows < left_rows * 0.99:
        print(f"[WARN] Expected many:1 but result has {left_rows - result_rows:,} fewer rows than left")
    else:
        print(f"[PASS] Cardinality consistent with many:1")

# Fan-out check
if join_type == "inner":
    max_expected = max(left_rows, right_rows)
    if result_rows > max_expected * 2:
        print(f"[WARN] Possible fan-out: result has {result_rows / max_expected:.1f}x expected rows")

# Extreme row loss
if join_type in ["inner", "left"]:
    loss_rate = 1 - (result_rows / left_rows) if left_rows > 0 else 0
    print(f"  Loss rate from left: {loss_rate:.1%}")
    if loss_rate > 0.9:
        print(f"[FAIL] Join lost {loss_rate:.1%} of left side rows")
        join_passed = False
    elif loss_rate > 0.5:
        print(f"[WARN] High row loss from left: {loss_rate:.1%}")
    else:
        print(f"[PASS] Row loss acceptable: {loss_rate:.1%}")

# Join key matching
print(f"\nJoin Key Matching:")
for key in join_keys:
    if key in left_df.columns and key in right_df.columns:
        left_unique = left_df[key].n_unique()
        right_unique = right_df[key].n_unique()
        result_unique = result_df[key].n_unique() if key in result_df.columns else 0
        print(f"  {key}: left={left_unique:,} unique, right={right_unique:,} unique, result={result_unique:,} unique")

        if join_type == "inner" and min(left_unique, right_unique) > 0:
            match_rate = result_unique / min(left_unique, right_unique)
            if match_rate < 0.5:
                print(f"[WARN] Low key match rate for '{key}': {match_rate:.1%}")

# Null keys in result (unexpected for inner join)
if join_type == "inner":
    for key in join_keys:
        if key in result_df.columns:
            null_keys = result_df[key].null_count()
            if null_keys > 0:
                print(f"[WARN] Join key '{key}' has {null_keys:,} nulls in result")

# Duplicate keys (indicates many-side)
for key in join_keys:
    if key in left_df.columns:
        left_dups = left_rows - left_df[key].n_unique()
        if left_dups > 0:
            print(f"  Left key '{key}' duplicates: {left_dups:,}")
    if key in right_df.columns:
        right_dups = right_rows - right_df[key].n_unique()
        if right_dups > 0:
            print(f"  Right key '{key}' duplicates: {right_dups:,}")

print(f"\nJOIN VALIDATION: {'PASSED' if join_passed else 'FAILED'}")
print("=" * 60)

if not join_passed:
    raise ValueError("Join validation FAILED - see details above")
```

### Usage Notes

Set these variables before the join validation block:

```python
# Configure before join validation block
join_keys = ["ncessch"]
expected_cardinality = "1:1"  # "1:1", "1:many", "many:1", "many:many"
join_type = "inner"           # "inner", "left", "right", "outer"
# left_df = <left DataFrame>
# right_df = <right DataFrame>
# result_df = <join result DataFrame>
```

---

## Substantiveness Validation (Stub Detection)

**Purpose:** Verify that data and outputs contain real implementation, not placeholders or suspicious patterns that indicate incomplete processing.

### Code Template

```python
import re
from pathlib import Path

# --- Substantiveness Validation: Data ---
print("\n" + "=" * 60)
print(f"SUBSTANTIVENESS CHECK: {context}")
print("=" * 60)

subst_passed = True

for col in key_columns:
    if col not in df.columns:
        continue

    # Single unique value (suspicious)
    n_unique = df[col].n_unique()
    if n_unique == 1 and len(df) > 10:
        value = df[col].unique()[0]
        print(f"[FAIL] Column '{col}' has only one unique value: {value}")
        subst_passed = False

    # All zeros in numeric columns
    if df[col].dtype in [pl.Int32, pl.Int64, pl.Float64]:
        non_null = df[col].drop_nulls()
        if len(non_null) > 0 and (non_null == 0).all():
            print(f"[FAIL] Column '{col}' is all zeros")
            subst_passed = False

        # Suspiciously round numbers
        if len(non_null) > 10:
            round_count = (non_null % 1000 == 0).sum()
            round_rate = round_count / len(non_null)
            if round_rate > 0.9 and non_null.max() > 1000:
                print(f"[WARN] Column '{col}' has {round_rate:.0%} suspiciously round values")

    # All nulls
    if df[col].null_count() == len(df):
        print(f"[FAIL] Column '{col}' is entirely null")
        subst_passed = False

if subst_passed:
    print("[PASS] No data substantiveness issues found")

print(f"\nDATA SUBSTANTIVENESS: {'PASSED' if subst_passed else 'FAILED'}")
print("=" * 60)
```

#### Text Substantiveness Check

```python
import re
from pathlib import Path

# --- Substantiveness Validation: Text ---
print("\n" + "=" * 60)
print(f"TEXT SUBSTANTIVENESS CHECK: {file_path}")
print("=" * 60)

text_subst_passed = True
content = file_path.read_text()

# Stub patterns to detect
stub_patterns = [
    (r'\bTODO\b', "TODO marker"),
    (r'\bFIXME\b', "FIXME marker"),
    (r'\bPLACEHOLDER\b', "PLACEHOLDER marker"),
    (r'\bTBD\b', "TBD marker"),
    (r'\bXXX\b', "XXX marker"),
    (r'\[add more\]', "Placeholder [add more]"),
    (r'\[your .* here\]', "Template placeholder"),
    (r'\[TODO.*?\]', "TODO in brackets"),
    (r'coming soon', "Coming soon placeholder"),
    (r'lorem ipsum', "Lorem ipsum placeholder"),
]

for pattern, description in stub_patterns:
    matches = re.findall(pattern, content, re.IGNORECASE)
    if matches:
        print(f"[FAIL] Found {description}: {len(matches)} occurrence(s)")
        text_subst_passed = False

# Empty sections
empty_section_pattern = r'(##\s+[^\n]+)\n\s*(?=##|\Z)'
for section in re.findall(empty_section_pattern, content):
    print(f"[FAIL] Empty section: {section.strip()}")
    text_subst_passed = False

# Required sections
if required_sections:
    for section in required_sections:
        section_pattern = rf'##\s*{re.escape(section)}\s*\n(.+?)(?=\n##|\Z)'
        match = re.search(section_pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
            print(f"[FAIL] Missing required section: {section}")
            text_subst_passed = False
        elif len(match.group(1).strip()) < 20:
            print(f"[FAIL] Section '{section}' appears empty or minimal")
            text_subst_passed = False

if text_subst_passed:
    print("[PASS] No text stub indicators found")

print(f"\nTEXT SUBSTANTIVENESS: {'PASSED' if text_subst_passed else 'FAILED'}")
print("=" * 60)
```

#### Code Substantiveness Check

```python
import re
from pathlib import Path

# --- Substantiveness Validation: Code ---
print("\n" + "=" * 60)
print(f"CODE SUBSTANTIVENESS CHECK: {file_path}")
print("=" * 60)

code_subst_passed = True
content = file_path.read_text()

code_patterns = [
    (r'def\s+\w+\([^)]*\):\s*\n\s+pass\s*$', "Empty function (pass)"),
    (r'def\s+\w+\([^)]*\):\s*\n\s+\.\.\.\s*$', "Empty function (...)"),
    (r'raise\s+NotImplementedError', "NotImplementedError"),
    (r'return\s+None\s*#.*TODO', "return None with TODO"),
    (r'return\s+\{\}\s*#.*TODO', "return {} with TODO"),
    (r'return\s+\[\]\s*#.*TODO', "return [] with TODO"),
]

for pattern, description in code_patterns:
    matches = re.findall(pattern, content, re.MULTILINE)
    if matches:
        print(f"[FAIL] Found {description}: {len(matches)} occurrence(s)")
        code_subst_passed = False

if code_subst_passed:
    print("[PASS] No code stub indicators found")

print(f"\nCODE SUBSTANTIVENESS: {'PASSED' if code_subst_passed else 'FAILED'}")
print("=" * 60)
```

### Usage in Final Review

Run each substantiveness block inline within the appropriate script. Set variables before each block:

```python
# For data substantiveness:
# df = <analysis DataFrame>
key_columns = ["enrollment", "poverty_rate", "student_teacher_ratio"]
context = "Final analysis dataset"

# For text substantiveness:
# file_path = Path("research/project/Report.md")
required_sections = ["Executive Summary", "Findings", "Limitations"]

# For code substantiveness:
# file_path = Path("research/project/analysis.py")
```

---

## Validation Approach

> **Note:** Validation code is embedded inline within each script. No separate `validation.py` module is needed. Each script's execution log captures the validation output as part of the audit trail.

**Project Structure:**
```
research/YYYY-MM-DD_[Title]/
├── YYYY-MM-DD_[Title]_Plan.md
├── YYYY-MM-DD_[Title].py     # Marimo notebook
├── scripts/                   # Scripts with inline validation
│   ├── stage5_fetch/
│   ├── stage6_clean/
│   ├── stage7_transform/
│   └── stage8_analysis/
├── data/
│   ├── raw/
│   └── processed/
└── output/
    └── figures/
```

**Rationale:**
- Each script is self-contained with its own validation
- Validation output is captured in the script's execution log
- No import dependencies between scripts
- Thresholds are customized per script to match the Plan

---

## Stub Detection Patterns

**Purpose:** Identify incomplete implementations, placeholders, and patterns that indicate code is not production-ready. Stub detection is critical during Final Review (Stage 12) and should be run on all artifacts before delivery.

### Severity Levels

| Level | Name | Description | Action Required |
|-------|------|-------------|-----------------|
| **BLOCKER** | Critical stub | Prevents analysis from producing valid results | Must fix before delivery |
| **WARNING** | Incomplete indicator | Suggests work in progress; may affect quality | Document and assess impact |
| **INFO** | Notable pattern | Worth investigating but not necessarily problematic | Review during QA |

---

### Universal Stub Patterns

These patterns indicate incomplete work across any Python file.

#### Comment-Based Stubs (BLOCKER)

```python
# Patterns to detect
TODO_PATTERNS = [
    r'\bTODO\b',           # TODO marker
    r'\bFIXME\b',          # FIXME marker
    r'\bXXX\b',            # XXX marker
    r'\bHACK\b',           # HACK marker
    r'\bPLACEHOLDER\b',    # Explicit placeholder
]
```

**Severity:** BLOCKER if in core analysis code; WARNING if in comments explaining future work.

#### Placeholder Text (BLOCKER)

```python
PLACEHOLDER_PATTERNS = [
    r'placeholder',
    r'coming soon',
    r'will be (added|implemented|done)',
    r'not yet implemented',
    r'lorem ipsum',
    r'add more',
    r'\[TBD\]',
    r'\[description\]',
    r'\[your .* here\]',
]
```

---

### Python Function Stubs

These patterns indicate functions that exist but have no real implementation.

#### Empty Function Bodies (BLOCKER)

```python
# STUB EXAMPLES - These are RED FLAGS:

def analyze_data():
    pass

def transform_data():
    ...

def fetch_data():
    raise NotImplementedError

def process_records():
    raise NotImplementedError("Will implement later")

def calculate_metrics():
    return None  # Just returns None with no logic

def get_statistics():
    return {}    # Empty dict with no computation

def load_data():
    return []    # Empty list with no file read
```

#### Return Stubs with TODO Comments (BLOCKER)

```python
# RED FLAGS:
def get_enrollment():
    return None  # TODO: fetch from data access mirror

def calculate_rate():
    return 0.0  # FIXME: implement calculation

def fetch_schools():
    return []  # placeholder data
```

---

### Polars/Data Analysis Stubs

These patterns are specific to data science workflows using Polars.

#### Empty DataFrame Returns (BLOCKER)

```python
# RED FLAGS:
def load_data():
    return pl.DataFrame()  # Empty DataFrame with no logic

def transform_data(df):
    return pl.DataFrame({})  # Returns empty instead of transforming

# RED FLAG: Returns empty DataFrame with just schema
result = pl.DataFrame(schema=df.schema)  # Empty — this is a stub!
```

#### Hardcoded Sample Data Instead of Processing (WARNING/BLOCKER)

```python
# RED FLAGS - Hardcoded data instead of real processing:

def get_enrollment_data():
    # This should fetch from data access mirror but returns hardcoded values
    return pl.DataFrame({
        "school": ["School A", "School B"],
        "enrollment": [100, 200]
    })

def calculate_statistics(df):
    # Ignores input and returns fake stats
    return {"mean": 500, "median": 450}  # Magic numbers
```

#### Filter That Returns Input Unchanged (WARNING)

```python
# RED FLAG - Transform that does nothing:
def filter_active_schools(df):
    # Filter that passes everything through
    return df.filter(pl.lit(True))

def clean_data(df):
    # "Cleaning" that doesn't clean
    return df
```

#### Aggregations That Don't Aggregate (BLOCKER)

```python
# RED FLAGS:
def calculate_totals(df):
    # Group by but no aggregation
    return df.group_by("state")  # Missing .agg()

def summarize_enrollment(df):
    # Aggregation returns input column unchanged
    return df.group_by("state").agg(pl.col("enrollment"))  # No agg function applied
```

---

### Marimo Notebook Stubs

These patterns are specific to marimo reactive notebooks.

#### Cells With Only Comments (WARNING)

```python
# RED FLAG - Cell that does nothing:
@app.cell
def _():
    # This will be implemented
    pass

@app.cell
def _():
    # TODO: add visualization
    ...
```

#### Cells Returning Hardcoded Strings (WARNING)

```python
# RED FLAG - Placeholder output:
@app.cell
def _():
    return mo.md("# Analysis Coming Soon")

@app.cell
def _():
    return mo.md("TODO: Add findings here")
```

#### Placeholder Markdown Cells (WARNING)

```python
# RED FLAGS:
mo.md("""
## Findings

[Add findings here]

## Methodology

TBD
""")
```

#### Import Cells With No Usage (INFO)

```python
# REVIEW - Imports that may be unused:
@app.cell
def _():
    import plotly.express as px  # Never used in notebook
    import seaborn as sns        # Never used
```

---

### Wiring Red Flags

These patterns indicate data/artifacts exist but aren't properly connected.

#### Data Loaded But Not Used in Analysis (BLOCKER)

```python
# RED FLAG - Load but never use:
df = pl.read_parquet("data/raw/schools.parquet")
# ... df never used again in analysis
# Report references different dataset

# Or loaded but only displayed, never analyzed:
df = pl.read_parquet("data/raw/schools.parquet")
print(df.head())  # Only inspection, no actual analysis
```

#### Transformations Exist But Output Not Saved (BLOCKER)

```python
# RED FLAG - Transform without saving:
clean_df = df.filter(pl.col("enrollment") > 0).with_columns(...)
# clean_df never written to data/processed/
# Notebook just displays but doesn't persist

# Analysis done but results not captured:
summary = df.group_by("state").agg(pl.col("enrollment").mean())
# summary not used in report, not saved
```

#### Figures Created But Not Referenced in Report (WARNING)

```python
# RED FLAG - Figure generated but not in report:
fig = px.scatter(df, x="poverty_rate", y="enrollment")
fig.write_html("output/figures/scatter.html")  # kaleido/write_image not available in DAAF
# Report.md doesn't reference scatter.png
```

#### Data Access Response Not Integrated (BLOCKER)

```python
# RED FLAG - Fetch but don't use result:
df = fetch_from_mirrors(dataset_paths=DATASET_PATHS, years=YEARS)
# df never written to parquet, never validated, never used downstream

# Or partial integration:
fetch_from_mirrors(dataset_paths=DATASET_PATHS, years=YEARS)
# Return value never assigned to a variable
```

---

### Python Stub Detection (Inline)

Use this sequential inline code within a Final Review script to detect stubs across project files:

```python
import re
from pathlib import Path

# --- Stub Detection: Project Scan ---
print("\n" + "=" * 60)
print(f"STUB DETECTION: {project_dir}")
print("=" * 60)

stub_passed = True
blocker_count = 0
warning_count = 0

# Patterns to scan for
BLOCKER_PATTERNS = [
    (r'\bTODO\b', "TODO marker"),
    (r'\bFIXME\b', "FIXME marker"),
    (r'\bXXX\b', "XXX marker"),
    (r'\bHACK\b', "HACK marker"),
    (r'\bPLACEHOLDER\b', "PLACEHOLDER marker"),
    (r'raise\s+NotImplementedError', "NotImplementedError"),
    (r'\bplaceholder\b', "Placeholder text"),
    (r'coming soon', "Coming soon text"),
    (r'\[TBD\]', "TBD marker"),
    (r'\[add more\]', "Add more placeholder"),
    (r'\[your .* here\]', "Template placeholder"),
    (r'return pl\.DataFrame\(\)', "Empty DataFrame return"),
]

WARNING_PATTERNS = [
    (r'mo\.md\([^)]*TODO', "Marimo TODO in markdown"),
    (r'mo\.md\([^)]*Coming Soon', "Marimo Coming Soon text"),
]

for pattern_glob in ["*.py", "*.md"]:
    for file_path in project_dir.rglob(pattern_glob):
        if any(part.startswith('.') for part in file_path.parts):
            continue
        content = file_path.read_text()

        for pattern, description in BLOCKER_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                print(f"[BLOCKER] {file_path.relative_to(project_dir)}: {description} ({len(matches)}x)")
                blocker_count += len(matches)
                stub_passed = False

        for pattern, description in WARNING_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                print(f"[WARNING] {file_path.relative_to(project_dir)}: {description} ({len(matches)}x)")
                warning_count += len(matches)

print(f"\nSummary: {blocker_count} blockers, {warning_count} warnings")
print(f"STUB DETECTION: {'PASSED' if stub_passed else 'FAILED'}")
print("=" * 60)
```

#### Wiring Check (Inline)

```python
import re
from pathlib import Path

# --- Wiring Check ---
print("\n" + "=" * 60)
print(f"WIRING CHECK: {project_dir}")
print("=" * 60)

wiring_passed = True
notebook_content = notebook_path.read_text()

# Check 1: Data loaded is used
data_loads = re.findall(r'(\w+)\s*=\s*pl\.(read_parquet|read_csv)\(["\']([^"\']+)', notebook_content)
for var_name, method, path in data_loads:
    uses = len(re.findall(rf'\b{var_name}\b', notebook_content)) - 1
    if uses < 2:
        print(f"[BLOCKER] Data '{var_name}' loaded from {path} but used only {uses} time(s)")
        wiring_passed = False
    else:
        print(f"[PASS] Data '{var_name}' loaded and used {uses} times")

# Check 2: Transformations produce saved output
transforms = len(re.findall(r'\.(filter|with_columns|group_by|join)\(', notebook_content))
saves = len(re.findall(r'\.(write_parquet|write_csv)\(', notebook_content))
if transforms > 0 and saves == 0:
    print(f"[BLOCKER] {transforms} transformations but no data saves")
    wiring_passed = False
else:
    print(f"[PASS] {transforms} transforms, {saves} saves")

# Check 3: Figures referenced in report
if report_path and report_path.exists():
    report_content = report_path.read_text()
    figures_saved = re.findall(r'(?:savefig|write_image|write_html)\(["\']([^"\']+)', notebook_content)
    for fig_path_str in figures_saved:
        fig_name = Path(fig_path_str).name
        if fig_name not in report_content:
            print(f"[WARN] Figure not referenced in report: {fig_name}")

print(f"\nWIRING CHECK: {'PASSED' if wiring_passed else 'FAILED'}")
print("=" * 60)
```

### Usage in Final Review (Stage 12)

Run stub detection and wiring checks inline in a Final Review script. Set variables before each block:

```python
# Configure before stub detection
project_dir = Path("research/2026-01-24_School_Analysis/")

# Configure before wiring check
notebook_path = Path("research/2026-01-24_School_Analysis/2026-01-24_School_Analysis.py")
report_path = Path("research/2026-01-24_School_Analysis/2026-01-24_School_Analysis_Report.md")
```

---

### Stub Detection Checklist for Final Review

Before delivery, verify all of the following pass:

| Check | Detection Method | Severity |
|-------|------------------|----------|
| No TODO/FIXME/XXX markers in code | `grep -rn "TODO\|FIXME\|XXX"` | BLOCKER |
| No NotImplementedError | `grep -rn "raise NotImplementedError"` | BLOCKER |
| No pass-only or ellipsis-only functions | Pattern match | BLOCKER |
| No placeholder text in markdown | `grep -ri "placeholder\|coming soon"` | BLOCKER |
| No empty DataFrame returns | `grep -rn "return pl.DataFrame()"` | BLOCKER |
| No unused imports | `grep` for imported names unused in file | WARNING |
| Data loaded is used in analysis | Wiring check | BLOCKER |
| Transformations produce saved output | Wiring check | BLOCKER |
| Figures are referenced in report | Wiring check | WARNING |
| Report has substantive content | Text substantiveness check | BLOCKER |

---

## Integration in Notebooks

> **Note:** Validation code is inline within each script, not imported from a module. The Marimo notebook assembles successful scripts verbatim. Validation output is captured in each script's execution log (appended as comments), which becomes part of the audit trail.

Validation results appear in the notebook as accordion sections containing the script's execution log. The notebook-assembler agent copies script content verbatim, including the inline validation blocks.

---

## Profiling Validation Checkpoints (CPP1-CPP4, CPP-SKILL)

> **Mode:** These checkpoints apply to Data Onboarding Mode only. They are the profiling equivalent of CP1-CP4. See `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` for complete code templates.

### CPP Overview

| Checkpoint | After Part | Purpose | STOP If |
|------------|-----------|---------|---------|
| CPP1 | A (Structural) | Data loads correctly | Zero rows, zero columns, >50% null, encoding errors |
| CPP2 | B (Statistical) | Stats are internally consistent | Mean outside [min,max], non-monotonic percentiles |
| CPP3 | C (Relational) | Relationships are coherent | Non-symmetric correlation, uniqueness disagreement, empty anomaly catalog |
| CPP4 | D (Interpretation) | Interpretations are disciplined | Missing [PRELIMINARY] markers, synthesis gaps |
| CPP-SKILL | Skill Authoring | Skill template compliance | Missing required sections, >500 lines, failed self-check |

### CPP1: Post-Load Validation

**Embedded in:** `scripts/profile_structural/01_load-and-format.py`

```python
# --- CPP1: Post-Load Validation ---
# INTENT: Verify data loaded correctly before profiling begins
assert df.shape[0] > 0, "STOP: Zero rows loaded"
assert df.shape[1] > 0, "STOP: Zero columns detected"

# INTENT: Check overall data quality
total_cells = df.shape[0] * df.shape[1]
total_nulls = sum(df[col].null_count() for col in df.columns)
null_rate = total_nulls / total_cells
assert null_rate < 0.5, f"STOP: Overall null rate {null_rate:.1%} exceeds 50%"

# INTENT: Warn about potential issues without stopping
for col in df.columns:
    if df[col].null_count() == df.shape[0]:
        print(f"WARNING: Column '{col}' is entirely null")
if df.shape[0] < 100:
    print("WARNING: Dataset has < 100 rows - possible partial file")

print(f"CPP1 PASSED: {df.shape[0]:,} rows, {df.shape[1]} columns, {null_rate:.1%} null rate")
```

### CPP2: Post-Statistical Validation

**Embedded in:** Last script of Part B (04, 05, or 06 depending on conditional execution)

```python
# --- CPP2: Post-Statistical Validation ---
# INTENT: Verify numeric summary statistics are internally consistent
for col in numeric_columns:
    col_min = df[col].min()
    col_max = df[col].max()
    col_mean = df[col].mean()
    # REASONING: Mean must fall within [min, max] for any valid distribution
    assert col_min <= col_mean <= col_max, (
        f"STOP: Mean for '{col}' ({col_mean}) outside [{col_min}, {col_max}]"
    )
    # REASONING: Percentiles must be monotonically non-decreasing
    p25 = df[col].quantile(0.25)
    p50 = df[col].quantile(0.50)
    p75 = df[col].quantile(0.75)
    assert p25 <= p50 <= p75, (
        f"STOP: Percentile monotonicity violated for '{col}': p25={p25}, p50={p50}, p75={p75}"
    )
# INTENT: Verify temporal script found time columns if dataset is temporal
# ASSUMES: Orchestrator marked dataset as temporal based on Part A findings
if temporal_expected and not time_columns_found:
    print("WARNING: Dataset expected to have temporal columns but none identified")
print("CPP2 PASSED: Statistical summaries internally consistent")
```

### CPP3: Post-Relational Validation

**Embedded in:** `scripts/profile_relational/09_quality-anomaly.py`

```python
# --- CPP3: Post-Relational Validation ---
# NOTE: This checkpoint is embedded in script 09 (quality-anomaly.py).
# Variables from other scripts (e.g., uniqueness_results from script 07,
# correlation_matrix from script 08) must be recomputed or loaded within
# this script before validation. Each profiling script runs independently;
# there is no shared in-memory state between scripts.

# INTENT: Anomaly catalog must be non-empty (at minimum INFO-level observations)
assert len(anomaly_catalog) > 0, (
    "STOP: Anomaly catalog is empty — quality analysis must produce at least one observation"
)

# INTENT: Verify correlation matrix is symmetric (if computed in this script or loaded)
if correlation_matrix is not None:
    import numpy as np
    assert np.allclose(correlation_matrix, correlation_matrix.T, atol=1e-10), (
        "STOP: Correlation matrix is not symmetric"
    )

# INTENT: Verify uniqueness counts agree with n_unique
# ASSUMES: uniqueness_results was computed or loaded in this script (not inherited from script 07)
for col in key_candidates:
    reported_unique = uniqueness_results[col]
    actual_unique = df[col].n_unique()
    assert reported_unique == actual_unique, (
        f"STOP: Uniqueness count mismatch for '{col}': reported {reported_unique}, actual {actual_unique}"
    )

print(f"CPP3 PASSED: Relational checks consistent, {len(anomaly_catalog)} anomalies cataloged")
```

### CPP4: Post-Interpretation Validation

**Embedded in:** The last executed Part D script (script 11 if docs provided, otherwise script 10).

```python
# --- CPP4: Post-Interpretation Validation ---
# INTENT: Verify interpretation discipline was maintained
import re

# ASSUMES: interpretation_output is the string output from script 10
# REASONING: Every semantic claim must be hedged with [PRELIMINARY]
interpretations = re.findall(r"(?:->|interpretation:)\s*(.+)", interpretation_output)
for interp in interpretations:
    if "[NO INTERPRETATION]" not in interp:
        assert "[PRELIMINARY]" in interp, (
            f"STOP: Interpretation missing [PRELIMINARY] marker: {interp[:80]}"
        )

# INTENT: If docs were provided, reconciliation must have run
# ASSUMES: documentation_provided is True if user supplied documentation at intake
if documentation_provided:
    assert reconciliation_ran, (
        "STOP: Documentation was provided but reconciliation script did not execute"
    )

print(f"CPP4 PASSED: All interpretations marked PRELIMINARY, "
      f"documentation reconciliation: {'completed' if documentation_provided else 'N/A (no docs)'}")
```

### CPP-SKILL: Post-Authoring Validation

**Embedded in:** Stage DI-7 skill authoring subagent output

```python
# --- CPP-SKILL: Template Compliance Check ---
# INTENT: Verify generated skill follows canonical 12-section template
import os

skill_path = f"{skill_draft_dir}/SKILL.md"
assert os.path.exists(skill_path), "STOP: SKILL.md not created"

with open(skill_path) as f:
    content = f.read()
    lines = content.split("\n")

# INTENT: Check line count constraint
assert len(lines) <= 500, f"STOP: SKILL.md is {len(lines)} lines (limit: 500)"

# INTENT: Verify required sections present
required_sections = [
    "## What is",
    "## Reference File Structure",
    "## Decision Trees",
    "## Quick Reference",
    "## Data Access",
    "## Common Pitfalls",
    "## Topic Index",
]
for section in required_sections:
    assert section in content, f"STOP: Missing required section: {section}"

# INTENT: Verify reference files created
ref_dir = f"{skill_draft_dir}/references"
for ref_file in ["columns.md", "coded-values.md", "data-quality.md", "variable-definitions.md"]:
    assert os.path.exists(f"{ref_dir}/{ref_file}"), f"STOP: Missing reference file: {ref_file}"

# INTENT: Verify key structural requirements from CPP-SKILL checklist
# REASONING: These checks catch common skill authoring omissions
assert "## Value Encodings" in content, "STOP: Missing Value Encodings Warning section"
assert content.index("## Value Encodings") < content.index("## Decision Trees"), (
    "STOP: Value Encodings Warning must appear before Decision Trees (position 4)"
)
decision_tree_count = content.count("```\n")  # Approximate tree block count
assert "## Decision Trees" in content, "STOP: Missing Decision Trees section"
assert "### Missing Data Codes" in content or "Missing Data Codes" in content, (
    "STOP: Missing Data Codes subsection in Quick Reference"
)
assert "> **Truth Hierarchy" in content or "Truth Hierarchy" in content, (
    "STOP: Missing Truth Hierarchy in Data Access section"
)
assert "## Common Pitfalls" in content, "STOP: Missing Common Pitfalls section"

print(f"CPP-SKILL PASSED: {len(lines)} lines, all required sections and reference files present")
```
