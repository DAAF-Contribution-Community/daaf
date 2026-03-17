# QA Checkpoints Reference

This document defines the continuous Quality Assurance checkpoint system that runs after each atomic script execution. QA checkpoints complement the existing CP1-CP4 validation system by providing independent secondary verification.

---

## Relationship to CP1-CP4

**CP1-CP4** = Primary validation (inline, during execution)
**QA1-QA4b** = Secondary validation (parallel script, after execution)

| Aspect | CP Checkpoints (Primary) | QA Checkpoints (Secondary) |
|--------|--------------------------|---------------------------|
| **Timing** | During script execution | After script completes |
| **Executor** | research-executor (inline) | code-reviewer (parallel script) |
| **Focus** | Operation correctness | Output quality & methodology |
| **Trust Model** | Validates the operation | Validates the validation |
| **Output** | Embedded in script log | Separate QA script + report |
| **Failure Mode** | STOP execution | BLOCKER → revision request |

**Why Both?** CP checkpoints catch operational failures (data access errors, type mismatches). QA checkpoints catch logical errors (wrong approach, inadequate validation, methodology drift).

**Cross-Reference:** See `agent_reference/VALIDATION_CHECKPOINTS.md` for CP1-CP4 code templates and checkpoint classification system.

---

## QA Philosophy

QA checkpoints exist because **primary validation has a structural blind spot**: it can only check what the script author thought to check. The code-reviewer's value comes from checking what the author *didn't* think to check — the orthogonal perspective, the creative edge case, the assumption that seemed too obvious to question.

**The QA mindset is adversarial by design.** A QA checkpoint that merely re-runs the same checks as the original script adds no value. Every QA script should include at least one validation that approaches the data from a different angle than the original script.

**Passing QA means "I tried hard to find problems and couldn't" — not "I ran some checks and they passed."**

The code-reviewer applies five skeptical lenses (Counterfactual, Semantic, Boundary, Absence, Downstream) to every script and hunts for "sleeping bugs" — errors latent in the logic that don't manifest with current data but could with different inputs. See `agents/code-reviewer.md` § Review Mindset for the full framework.

---

## QA Checkpoint Overview

| Checkpoint | Stage | Focus | Triggers BLOCKER When |
|------------|-------|-------|----------------------|
| **QA1** | After fetch (Stage 5) | Raw data quality | Schema wrong, years missing, unexpected geography |
| **QA2** | After clean (Stage 6) | Cleaning correctness | Coded values remain, wrong suppression calc |
| **QA3** | After transform (Stage 7) | Transform validity | Wrong join type, aggregation error, data loss |
| **QA4a** | After analysis & viz (Stage 8) | Statistical validity | Wrong data source, incorrect aggregations, model non-convergence, scale misrepresentation |
| **QA4b** | After analysis & viz (Stage 8) | Visualization quality | Missing figures, labeling errors, accessibility issues, misleading scales |

---

## QA1: Post-Fetch Quality Assessment

**Applies To:** Stage 5 scripts (data retrieval)

**Purpose:** Verify raw data is correct for the analysis, not just that it was fetched successfully.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Schema match | Columns match Plan specification | Critical columns missing |
| Year coverage | Years match Plan's year range | Target years absent |
| Geographic scope | Correct entity granularity per domain config (e.g., state/district/school for education) | Wrong geographic unit or entity level |
| ID uniqueness | Primary keys are unique | Duplicate IDs present |
| Dataset completeness | Expected rows and fields present | Partial data fetch |

### QA1 Standard Check Script (cr1)

```python
import polars as pl

# --- QA1: Post-Fetch Quality Assessment ---
print("\n" + "=" * 60)
print("QA1: POST-FETCH QUALITY ASSESSMENT")
print("=" * 60)

qa1_max_severity = "PASSED"  # Track highest severity: PASSED < WARNING < BLOCKER

# Schema validation
expected_cols = plan_spec["expected_columns"]
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    critical_missing = [c for c in missing if c in plan_spec["critical_columns"]]
    if critical_missing:
        print(f"[BLOCKER] Missing critical columns: {critical_missing}")
        qa1_max_severity = "BLOCKER"
    else:
        print(f"[WARNING] Missing non-critical columns: {missing}")
        qa1_max_severity = max(qa1_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
else:
    print(f"[PASS] All {len(expected_cols)} expected columns present")

# Year coverage
year_col = plan_spec.get("year_col", "year")  # From Plan Domain Configuration
if year_col and year_col in df.columns:
    years_present = set(df[year_col].unique().to_list())
    years_expected = set(plan_spec["year_range"])
    missing_years = years_expected - years_present
    if missing_years:
        severity = "BLOCKER" if len(missing_years) > len(years_expected) // 2 else "WARNING"
        print(f"[{severity}] Missing years: {sorted(missing_years)}")
        qa1_max_severity = max(qa1_max_severity, severity, key=["PASSED", "WARNING", "BLOCKER"].index)
    else:
        print(f"[PASS] All expected years present: {sorted(years_present)}")

# ID uniqueness
id_col = plan_spec.get("primary_key")
if id_col and id_col in df.columns:
    duplicates = df.group_by(id_col).count().filter(pl.col("count") > 1)
    if len(duplicates) > 0:
        print(f"[BLOCKER] {len(duplicates)} duplicate IDs found in '{id_col}'")
        qa1_max_severity = "BLOCKER"
    else:
        print(f"[PASS] All IDs unique in '{id_col}'")

# --- Data Profiling (for qa2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

print(f"\nQA1 RESULT: {qa1_max_severity}")
print("=" * 60)
```

### QA1 Discretionary Checks

Add when appropriate:

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Value range | Numeric analysis | Values within expected bounds |
| Category coverage | Categorical analysis | All expected categories present |
| Cross-source consistency | Multi-source fetch | Same entities across sources |
| **Concrete trace** | **Always (at minimum 5)** — see `agents/code-reviewer.md` for the five required categories | **Pick one entity (e.g., a specific school or state) and verify its record looks plausible** |

**Creative check prompt:** Before writing your QA1 script, ask: *"If the data access mirror returned data for the wrong geography or wrong year range, how would I detect that from the data alone?"* Design at least one check to answer that question.

### QA1 Iterative Investigation Triggers

Observations from qa1 that should trigger qa2+ investigation:

| qa1 Observation | Suggested qa2 Investigation |
|-----------------|---------------------------|
| Unexpected geography in data (states not in Plan scope) | Filter analysis: are extra states contaminating results? |
| Year distribution uneven (some years have 10x more records) | Investigate: data access issue or genuine enrollment change? |
| ID column has unexpected format variations | Trace: will downstream joins fail on format mismatch? |
| Row count far from Plan estimate (even if within tolerance) | Profile: what population is unexpectedly included/excluded? |

---

## QA2: Post-Clean Quality Assessment

**Applies To:** Stage 6 scripts (context application)

**Purpose:** Verify cleaning was done correctly, not just that cleaning operations ran.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Coded values gone | Domain-specific coded values filtered properly (e.g., -1, -2, -3 for education) | Coded values remain in analysis columns |
| Suppression calc | Rate calculated correctly | Suppression rate miscalculated |
| Filter correctness | Correct rows removed | Wrong filter criteria applied |
| Type consistency | Data types are appropriate | Analysis columns have wrong types |

### QA2 Standard Check Script (cr1)

```python
import polars as pl

# --- QA2: Post-Clean Quality Assessment ---
print("\n" + "=" * 60)
print("QA2: POST-CLEAN QUALITY ASSESSMENT")
print("=" * 60)

qa2_max_severity = "PASSED"

# Coded values verification
print("\nCoded Values Check:")
for col in plan_spec.get("numeric_columns", []):
    if col not in df.columns:
        continue
    coded_missing_values = plan_spec.get("coded_missing_values", [-1, -2, -3])  # Maps to Plan's "Coded Missing Values" field in Domain Configuration; education default: [-1, -2, -3]
    for code in coded_missing_values:
        count = (df[col] == code).sum()
        if count > 0:
            print(f"[BLOCKER] Column '{col}' still has {count} coded value {code}")
            qa2_max_severity = "BLOCKER"
    if all((df[col] == code).sum() == 0 for code in coded_missing_values):
        print(f"[PASS] '{col}': no coded values remain")

# Suppression rate recalculation
if "suppression_columns" in plan_spec:
    print("\nSuppression Rate Verification:")
    for col in plan_spec["suppression_columns"]:
        if col not in df.columns or col not in raw_df.columns:
            continue
        raw_count = len(raw_df)
        clean_count = len(df)
        actual_rate = 1 - (clean_count / raw_count) if raw_count > 0 else 0
        reported_rate = plan_spec.get("reported_suppression_rate", {}).get(col)
        if reported_rate and abs(actual_rate - reported_rate) > 0.05:
            print(f"[WARNING] Suppression rate mismatch for '{col}': reported {reported_rate:.1%}, actual {actual_rate:.1%}")
            qa2_max_severity = max(qa2_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
        else:
            print(f"[PASS] '{col}' suppression rate: {actual_rate:.1%}")

# Type validation
type_spec = plan_spec.get("column_types", {})
if type_spec:
    print("\nType Validation:")
    for col, expected_type in type_spec.items():
        if col in df.columns and str(df[col].dtype) != expected_type:
            print(f"[WARNING] '{col}' type mismatch: expected {expected_type}, got {df[col].dtype}")
            qa2_max_severity = max(qa2_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
        elif col in df.columns:
            print(f"[PASS] '{col}' type: {df[col].dtype}")

# --- Data Profiling (for qa2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

print(f"\nQA2 RESULT: {qa2_max_severity}")
print("=" * 60)
```

### QA2 Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Distribution comparison | Statistical analysis | Pre/post distributions similar |
| Outlier retention | Outlier-sensitive analysis | Correct outlier handling |
| Null pattern | Complex null logic | Nulls handled per specification |
| **Complement inspection** | **Always (at minimum 5)** — see `agents/code-reviewer.md` for the five required categories | **Examine what was REMOVED by cleaning — do the removed rows look like what you'd expect?** |

**Creative check prompt:** Before writing your QA2 script, ask: *"If the cleaning logic had an off-by-one error in the filter condition (e.g., `>= -1` instead of `== -1`), what would the symptom look like in the cleaned data?"* Design at least one check to catch that class of error.

### QA2 Iterative Investigation Triggers

Observations from qa1 that should trigger qa2+ investigation:

| qa1 Observation | Suggested qa2 Investigation |
|-----------------|---------------------------|
| Coded value removal affected >20% of rows for a column | Profile removed rows: is a specific subgroup disproportionately affected? |
| Suppression rate varies widely across states | Investigate: does suppression pattern correlate with state reporting practices? |
| Type casting changed value distributions | Verify: are boundary values (min/max) preserved correctly after cast? |
| Null pattern is non-random (clustered by year or state) | Analyze: could missing data pattern bias the analysis conclusions? |

---

## QA3: Post-Transform Quality Assessment

**Applies To:** Stage 7 scripts (EDA and transformation)

**Purpose:** Verify transformations produced correct results, not just that they executed.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Join cardinality | Expected 1:1, 1:many, many:1 | Unexpected fan-out or data loss |
| Aggregation correctness | Sums, means, counts correct | Aggregation logic error |
| Row preservation | Expected row change | >90% unexpected data loss |
| Column creation | New columns calculated correctly | Derived columns have wrong values |
| No surprise nulls | Expected nulls only | Unexpected nulls introduced |

### QA3 Standard Check Script (cr1)

```python
import polars as pl

# --- QA3: Post-Transform Quality Assessment ---
print("\n" + "=" * 60)
print("QA3: POST-TRANSFORM QUALITY ASSESSMENT")
print("=" * 60)

qa3_max_severity = "PASSED"

# Join cardinality validation
if "join" in transform_spec:
    expected_cardinality = transform_spec["join"]["expected_cardinality"]
    left_df = source_dfs["left"]
    right_df = source_dfs["right"]

    print(f"\nJoin Cardinality (expected: {expected_cardinality}):")
    if expected_cardinality == "1:1":
        if len(df) > max(len(left_df), len(right_df)) * 1.05:
            print(f"[BLOCKER] Fan-out detected: {len(df)} rows from {len(left_df)} and {len(right_df)}")
            qa3_max_severity = "BLOCKER"
        else:
            print(f"[PASS] No fan-out: {len(df)} rows")

# Aggregation spot-check
if "aggregation" in transform_spec:
    group_col = transform_spec["aggregation"]["group_by"]
    agg_col = transform_spec["aggregation"]["column"]
    agg_func = transform_spec["aggregation"]["function"]

    sample_group = df[group_col].unique()[0]
    sample_df = df.filter(pl.col(group_col) == sample_group)

    print(f"\nAggregation Spot-Check (group: {sample_group}):")
    if agg_func == "sum":
        source_sum = source_dfs["input"].filter(pl.col(group_col) == sample_group)[agg_col].sum()
        result_sum = sample_df[agg_col].sum()
        if abs(source_sum - result_sum) > 0.01 * source_sum:
            print(f"[BLOCKER] Aggregation mismatch: source sum {source_sum}, result sum {result_sum}")
            qa3_max_severity = "BLOCKER"
        else:
            print(f"[PASS] Aggregation verified: source={source_sum}, result={result_sum}")

# Row preservation
expected_rows = transform_spec.get("expected_rows")
if expected_rows:
    row_diff = abs(len(df) - expected_rows) / expected_rows
    print(f"\nRow Preservation:")
    if row_diff > 0.5:
        print(f"[BLOCKER] Row count deviation: expected ~{expected_rows:,}, got {len(df):,} ({row_diff:.1%})")
        qa3_max_severity = "BLOCKER"
    elif row_diff > 0.1:
        print(f"[WARNING] Row count deviation: expected ~{expected_rows:,}, got {len(df):,} ({row_diff:.1%})")
        qa3_max_severity = max(qa3_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
    else:
        print(f"[PASS] Row count: {len(df):,} (expected ~{expected_rows:,})")

# Unexpected null check
no_null_cols = transform_spec.get("no_null_columns", [])
if no_null_cols:
    print(f"\nUnexpected Nulls:")
    for col in no_null_cols:
        if col in df.columns:
            null_count = df[col].null_count()
            if null_count > 0:
                print(f"[BLOCKER] Column '{col}' has {null_count} unexpected nulls")
                qa3_max_severity = "BLOCKER"
            else:
                print(f"[PASS] '{col}': no nulls")

# --- Data Profiling (for qa2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

print(f"\nQA3 RESULT: {qa3_max_severity}")
print("=" * 60)
```

### QA3 Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Statistical tests | Distribution-critical | K-S test for distribution preservation |
| Business logic | Complex derivations | Derived values match business rules |
| Cross-validation | Multiple sources | Results consistent across methods |
| Temporal consistency | Time-series | No impossible date sequences |
| **Concrete trace** | **Always (at minimum 5)** — see `agents/code-reviewer.md` for the five required categories | **Pick one entity and verify its journey through the transformation end-to-end** |

**Creative check prompt:** Before writing your QA3 script, ask: *"If this transformation had a subtle bug that affected 5% of records, what would the symptom look like in the output data? How would I detect it?"* Design at least one check to answer that question.

### QA3 Iterative Investigation Triggers

Observations from qa1 that should trigger qa2+ investigation:

| qa1 Observation | Suggested qa2 Investigation |
|-----------------|---------------------------|
| Join match rate < 80% | Profile non-matching keys: is there a systematic pattern (state, year, school type)? |
| Aggregation changed distribution shape significantly | Verify: are outlier groups driving the change? Is the aggregation logic correct? |
| Derived column has unexpected null rate | Trace: which input columns contribute nulls? Is the derivation formula correct? |
| Row count after transformation differs >10% from Plan estimate | Investigate: which filter or join step caused the unexpected change? |

---

## QA4a: Post-Analysis Statistical Validity

**Applies To:** Stage 8 scripts (statistical analysis and visualization)

**Purpose:** Verify data is represented accurately, statistical analyses are correct, and no misrepresentation occurs.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Data source accuracy | Correct dataset used | Figure/analysis uses wrong data file |
| Aggregation correctness | Calculations match script logic | Aggregated values don't match source data |
| Model convergence | Statistical models converged (if applicable) | Non-convergence without documentation |
| Assumption validation | Model assumptions checked (if applicable) | Critical assumptions violated without discussion |
| Coefficient reasonableness | Effect sizes plausible (if applicable) | Coefficients contradict domain knowledge |
| Robustness consistency | Alternative specs agree (if applicable) | Primary result reverses in robustness check |
| Axis scale appropriateness | Scales don't distort relationships | Y-axis truncation misleads interpretation |
| Statistical representation | Visual encoding matches data semantics | Bar chart for continuous data, pie chart for >7 categories |

### QA4a cra1 Script Template

```python
import polars as pl
from pathlib import Path

# --- QA4a: Post-Analysis Statistical Validity ---
print("\n" + "=" * 60)
print("QA4a: POST-ANALYSIS STATISTICAL VALIDITY")
print("=" * 60)

qa4a_max_severity = "PASSED"

# Data source accuracy
print("\nData Source Check:")
script_path = Path(script_spec["script_path"])
script_text = script_path.read_text()
expected_data_source = plan_spec["data_source"]
if expected_data_source not in script_text:
    print(f"[BLOCKER] Script does not load expected data source: {expected_data_source}")
    qa4a_max_severity = "BLOCKER"
elif "data/raw/" in script_text and "data/processed/" not in script_text:
    print("[WARNING] Script appears to use raw data instead of processed data")
    qa4a_max_severity = max(qa4a_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
else:
    print(f"[PASS] Script loads expected data source")

# Aggregation spot-check
if "aggregation" in plan_spec:
    print("\nAggregation Spot-Check:")
    group_col = plan_spec["aggregation"]["group_by"]
    agg_col = plan_spec["aggregation"]["column"]
    sample_group = df[group_col].unique()[0]
    source_val = source_df.filter(pl.col(group_col) == sample_group)[agg_col].sum()
    result_val = df.filter(pl.col(group_col) == sample_group)[agg_col].sum()
    if abs(source_val - result_val) > 0.01 * abs(source_val) and source_val != 0:
        print(f"[BLOCKER] Aggregation mismatch: source={source_val}, result={result_val}")
        qa4a_max_severity = "BLOCKER"
    else:
        print(f"[PASS] Aggregation verified: source={source_val}, result={result_val}")

# Model convergence (if applicable)
if "model_results" in plan_spec:
    print("\nModel Convergence Check:")
    model_results = plan_spec["model_results"]
    if model_results.get("converged") is False and not model_results.get("convergence_documented"):
        print("[BLOCKER] Model did not converge and non-convergence is not documented")
        qa4a_max_severity = "BLOCKER"
    elif model_results.get("converged") is False:
        print("[WARNING] Model did not converge (documented in script)")
        qa4a_max_severity = max(qa4a_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
    else:
        print("[PASS] Model converged successfully")

# Assumption validation (if applicable)
if "assumptions" in plan_spec:
    print("\nAssumption Validation:")
    for assumption in plan_spec["assumptions"]:
        name = assumption["name"]
        checked = assumption.get("checked", False)
        violated = assumption.get("violated", False)
        discussed = assumption.get("discussed", False)
        if not checked:
            print(f"[WARNING] Assumption '{name}' not checked")
            qa4a_max_severity = max(qa4a_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
        elif violated and not discussed:
            print(f"[BLOCKER] Assumption '{name}' violated without discussion")
            qa4a_max_severity = "BLOCKER"
        elif violated and discussed:
            print(f"[WARNING] Assumption '{name}' violated (discussed in script)")
            qa4a_max_severity = max(qa4a_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
        else:
            print(f"[PASS] Assumption '{name}' holds")

# Robustness consistency (if applicable)
if "robustness_checks" in plan_spec:
    print("\nRobustness Consistency:")
    for rob_check in plan_spec["robustness_checks"]:
        name = rob_check["name"]
        primary_sign = rob_check.get("primary_sign")
        alt_sign = rob_check.get("alt_sign")
        if primary_sign and alt_sign and primary_sign != alt_sign:
            print(f"[BLOCKER] Result reversal in '{name}': primary sign={primary_sign}, alt sign={alt_sign}")
            qa4a_max_severity = "BLOCKER"
        else:
            print(f"[PASS] Robustness check '{name}' consistent")

# --- Data Profiling (for cra2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

print(f"\nQA4a RESULT: {qa4a_max_severity}")
print("=" * 60)
```

### QA4a Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Effect size plausibility | Regression/causal analysis | Estimated effects within domain-reasonable bounds |
| Sample size adequacy | Statistical tests | Sufficient N for claimed significance |
| Multiple comparison adjustment | Multiple hypotheses tested | p-values adjusted appropriately |
| Outlier influence | Regression analysis | Results not driven by a few extreme observations |
| **Concrete trace** | **Always (at minimum 5)** — see `agents/code-reviewer.md` for the five required categories | **Pick one data point and verify its representation in the analysis output is accurate** |

**Creative check prompt:** Before writing your QA4a script, ask: *"If the script used the wrong column for a key calculation, or aggregated at the wrong level, how would the output differ from correct output?"* Design at least one check to catch that class of error.

### QA4a Iterative Investigation Triggers

Observations from cra1 that should trigger cra2+ investigation:

| cra1 Observation | Suggested cra2 Investigation |
|-----------------|---------------------------|
| Aggregated totals don't match source data sums | Trace: which group(s) account for the discrepancy? Is a filter being applied incorrectly? |
| Model coefficients have unexpected signs | Investigate: is there multicollinearity, omitted variable bias, or data coding error? |
| Effect sizes implausibly large or small | Profile: are outliers driving the result? Does winsorization change the conclusion? |
| Robustness check shows marginal consistency | Deeper analysis: how sensitive is the result to specification choices? |

---

## QA4b: Post-Analysis Visualization Quality

**Applies To:** Stage 8 scripts (visualization)

**Purpose:** Verify visualizations are complete, labeled, accessible, visually coherent, and publication-ready.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| File existence | All planned figures created | Required figures missing |
| File size | Figures have content | File size < 10KB (likely empty) |
| Title/labels | All axes labeled with units, descriptive title | Missing titles or axis labels |
| Colorblind-safe palette | Accessible color scheme used | Color-only encoding without texture/shape |
| COVID period annotation | Years 2020-2022 flagged visually (if present) | COVID years present but not annotated |
| Legend clarity | Legend present if needed, labels interpretable | Legend missing when required |
| Resolution | Exported at appropriate DPI | DPI <150 for print-intended figures |
| Misleading scales | Y-axis starts at 0 for bar charts | Truncated axis distorts interpretation |

### QA4b crb1 Script Template

```python
from pathlib import Path
import re

# --- QA4b: Post-Analysis Visualization Quality ---
print("\n" + "=" * 60)
print("QA4b: POST-ANALYSIS VISUALIZATION QUALITY")
print("=" * 60)

qa4b_max_severity = "PASSED"

# File existence and size check
expected_figures = viz_spec.get("expected_figures", [])
print(f"\nExpected Figures ({len(expected_figures)}):")
for fig_name in expected_figures:
    fig_path = output_dir / "figures" / fig_name
    if not fig_path.exists():
        print(f"[BLOCKER] Not found: {fig_name}")
        qa4b_max_severity = "BLOCKER"
    else:
        size_kb = fig_path.stat().st_size / 1024
        if size_kb < 10:
            print(f"[WARNING] {fig_name} is suspiciously small ({size_kb:.1f} KB)")
            qa4b_max_severity = max(qa4b_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
        else:
            print(f"[PASS] {fig_name} ({size_kb:.1f} KB)")

# Title and label check (via script inspection)
print("\nTitle/Label Check:")
script_path = Path(script_spec["script_path"])
script_text = script_path.read_text()
has_xlabel = bool(re.search(r'(xlab|xlabel|labs\(.*x\s*=|axis_title_x)', script_text))
has_ylabel = bool(re.search(r'(ylab|ylabel|labs\(.*y\s*=|axis_title_y)', script_text))
has_title = bool(re.search(r'(ggtitle|title\s*=|labs\(.*title)', script_text))

if not has_xlabel or not has_ylabel:
    print(f"[BLOCKER] Missing axis labels")
    qa4b_max_severity = "BLOCKER"
else:
    print("[PASS] Axis labels present in script")

if not has_title:
    print("[WARNING] No title detected in script")
    qa4b_max_severity = max(qa4b_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
else:
    print("[PASS] Title present in script")

# COVID period annotation check
print("\nCOVID Annotation Check:")
covid_years = viz_spec.get("covid_years_present", False)
if covid_years:
    has_covid = bool(re.search(r'(covid|pandemic|2020.*2022|annotate|vline|geom_rect)', script_text, re.IGNORECASE))
    if not has_covid:
        print("[BLOCKER] COVID years (2020-2022) present but not annotated visually")
        qa4b_max_severity = "BLOCKER"
    else:
        print("[PASS] COVID period annotation detected")
else:
    print("[PASS] No COVID years in data range")

# Resolution check
print("\nResolution Check:")
dpi_match = re.search(r'dpi\s*=\s*(\d+)', script_text)
if dpi_match:
    dpi = int(dpi_match.group(1))
    if dpi < 150:
        print(f"[WARNING] Low DPI ({dpi}) — may be insufficient for print")
        qa4b_max_severity = max(qa4b_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)
    else:
        print(f"[PASS] DPI = {dpi}")
else:
    print("[WARNING] No explicit DPI setting found")
    qa4b_max_severity = max(qa4b_max_severity, "WARNING", key=["PASSED", "WARNING", "BLOCKER"].index)

# --- Data Profiling (for crb2+ decision) ---
print("\n" + "=" * 60)
print("FIGURES DIRECTORY LISTING")
print("=" * 60)
figures_dir = output_dir / "figures"
if figures_dir.exists():
    for f in sorted(figures_dir.iterdir()):
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")

print(f"\nQA4b RESULT: {qa4b_max_severity}")
print("=" * 60)
```

### QA4b Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Aspect ratio | Publication submission | Figure dimensions meet requirements |
| Font size | Presentation figures | Text readable at intended display size |
| Annotation accuracy | Annotated plots | Annotation text matches data values |
| Multi-panel consistency | Faceted plots | Consistent scales across panels |
| **Visual trace** | **Always (at minimum 5)** — see `agents/code-reviewer.md` for the five required categories | **Pick one data point and verify it appears in the correct position in the figure** |

**Creative check prompt:** Before writing your QA4b script, ask: *"If a figure were missing its legend, had truncated axes, or used a color scheme indistinguishable to colorblind readers, how would I detect that programmatically?"* Design at least one check to catch that class of error.

### QA4b Iterative Investigation Triggers

Observations from crb1 that should trigger crb2+ investigation:

| crb1 Observation | Suggested crb2 Investigation |
|-----------------|---------------------------|
| Figure file size varies wildly across expected figures | Investigate: are some figures blank or truncated? |
| Script has no explicit DPI or size settings | Verify: do output figures meet minimum resolution? |
| Color palette not from known accessible set | Test: verify redundant encoding (shape/linetype) present |
| COVID years in data but annotation only on some figures | Audit: which figures include COVID years and which lack annotation? |

---

## Severity Classification Rules

### BLOCKER (Revision Required)

A finding is BLOCKER severity when:

1. **Data Correctness Compromised**
   - Wrong data is being used (wrong years, wrong geography, wrong columns)
   - Transformations produce incorrect results
   - Joins have unexpected cardinality

2. **Methodology Violated**
   - Implementation contradicts Plan specification
   - Critical cleaning steps skipped or wrong
   - Business logic errors in calculations

3. **Validation Inadequate**
   - Code could pass despite data corruption
   - Critical checks missing entirely
   - STOP conditions not implemented

4. **Output Invalid**
   - Missing required outputs
   - Outputs contain clearly wrong data
   - Stub/placeholder code detected

### WARNING (Document and Proceed)

A finding is WARNING severity when:

1. **Quality Concern (Not Correctness)**
   - Suboptimal approach that still works
   - Edge cases not explicitly handled (but unlikely)
   - Validation could be more robust

2. **Minor Deviation**
   - Slight methodology variation (acceptable)
   - Row counts differ from expectation (within tolerance)
   - Performance could be improved

3. **Documentation Gap (IAT Compliance)**
   - Missing INTENT comments on transformations
   - Missing REASONING comments on non-obvious choices
   - Assumptions not explicitly stated (missing ASSUMES comments)
   - Section preambles absent
   - Magic numbers without explanation
   - See `agent_reference/INLINE_AUDIT_TRAIL.md` for the full standard

### INFO (Log Only)

A finding is INFO severity when:

1. **Suggestions for Improvement**
   - Code could be cleaner
   - Better approaches exist
   - Optimization opportunities

2. **Observations**
   - Interesting data patterns
   - Potential future enhancements
   - Style preferences

---

## QA Script Directory Structure

```
scripts/
├── stage5_fetch/
│   └── 01_fetch-ccd.py
├── stage6_clean/
│   └── 01_clean-ccd.py
├── stage7_transform/
│   └── 01_join-data.py
├── stage8_analysis/
│   ├── 01_regression-analysis.py
│   └── 02_enrollment-plot.py
├── cr/                              # Code-review scripts directory (iterative)
│   ├── stage5_01_cr1.py             # QA1 for Stage 5, Step 01 (standard + profiling)
│   ├── stage5_01_cr2.py             # QA2: Investigated year coverage anomaly
│   ├── stage6_01_cr1.py             # QA1 for Stage 6, Step 01
│   ├── stage7_01_cr1.py             # QA1 for Stage 7, Step 01
│   ├── stage7_01_cr2.py             # QA2: Investigated join non-matches
│   ├── stage7_01_cr3.py             # QA3: Traced 10 entities end-to-end
│   ├── stage8_01_cra1.py            # QA4a (statistical validity) for Stage 8, Step 01
│   └── stage8_02_crb1.py            # QA4b (visualization quality) for Stage 8, Step 02
└── debug/
    └── ...
```

### Naming Convention

**Standard pattern (Stages 5-7):** `stage{N}_{step:02d}_cr{iteration}.py`

| Component | Description | Example |
|-----------|-------------|---------|
| `stage{N}` | Stage number (5, 6, 7) | `stage7` |
| `{step}` | Step number from reviewed script | `01`, `02` |
| `_cr{iteration}` | QA script suffix with iteration number (1-5) | `_cr1`, `_cr2` |

**Stage 8 pattern (split QA):** `stage8_{step:02d}_cr{a|b}{iteration}.py`

| Component | Description | Example |
|-----------|-------------|---------|
| `stage8` | Stage 8 (analysis & visualization) | `stage8` |
| `{step}` | Step number from reviewed script | `01`, `02` |
| `_cra{iteration}` | QA4a (statistical validity) suffix | `_cra1`, `_cra2` |
| `_crb{iteration}` | QA4b (visualization quality) suffix | `_crb1`, `_crb2` |

**Examples:**
- Script `01_fetch-ccd.py` in Stage 5 → `stage5_01_cr1.py` (first iteration), `stage5_01_cr2.py` (if needed)
- Script `02_aggregate.py` in Stage 7 → `stage7_02_cr1.py`
- Script `01_regression-analysis.py` in Stage 8 → `stage8_01_cra1.py` (QA4a), `stage8_01_crb1.py` (QA4b)

---

## QA Report Format

QA checkpoint results follow this conceptual schema. The actual output to the orchestrator uses Markdown format (see the code-reviewer invocation template in `full-pipeline.md`). This YAML schema documents the logical structure:

```yaml
qa_report:
  script_reviewed: "scripts/stage7_transform/01_join-data.py"
  qa_script: "scripts/cr/stage7_01_cr1.py"
  status: "ISSUES_FOUND"  # or "PASSED"
  severity: "BLOCKER"      # highest severity found

  checks:
    - name: "join_cardinality"
      status: "FAIL"
      severity: "BLOCKER"
      message: "Expected 1:1 join but got fan-out"
      evidence: "Output has 150,000 rows from 100,000 source rows"

    - name: "schema_match"
      status: "PASS"
      severity: null
      message: "All expected columns present"

    - name: "distribution"
      status: "WARN"
      severity: "WARNING"
      message: "Enrollment distribution shifted after join"
      evidence: "Pre-join mean: 450, post-join mean: 380"

  issues:
    blockers:
      - check: "join_cardinality"
        description: "Fan-out detected in 1:1 join"
        suggested_fix: "Check for duplicate keys in right table"

    warnings:
      - check: "distribution"
        description: "Distribution shifted unexpectedly"
        recommendation: "Verify join key matching is correct"

    info: []

  recommendation: "REVISION_REQUIRED"  # or "PROCEED" or "ESCALATE"
```

---

## Integration with Stage 10

Stage 10 aggregates all QA findings from Stages 5-8:

### QA Summary for Stage 10

```markdown
## QA Summary Report

### Execution Overview
| Stage | Scripts | QA Reviews | BLOCKERs Found | BLOCKERs Resolved |
|-------|---------|------------|----------------|-------------------|
| 5     | 2       | 2          | 0              | N/A               |
| 6     | 2       | 2          | 0              | N/A               |
| 7     | 3       | 3          | 2              | 2 (via revision)  |
| 8     | 1       | 1          | 0              | N/A               |

### Resolved BLOCKERs
| Script | Issue | Resolution | Revision Count |
|--------|-------|------------|----------------|
| 01_join-data.py | Fan-out join | Fixed duplicate keys | 2 |

### Outstanding WARNINGs
| Script | Warning | Assessment | Documentation |
|--------|---------|------------|---------------|
| 01_clean-ccd.py | 38% suppression | Acceptable | Added to limitations |

### INFO Items
| Script | Observation |
|--------|-------------|
| 01_fetch-ccd.py | Could parallelize data access calls |
```

---

## QA Checkpoint STOP Conditions

QA checkpoints can trigger STOP conditions that prevent proceeding:

| Condition | Checkpoint | Action |
|-----------|------------|--------|
| BLOCKER after 2 revision scripts (_a.py, _b.py) | Any | STOP, escalate to user |
| Methodology violation | Any | STOP, escalate immediately |
| Data corruption detected | QA3 | STOP, invoke debugger |
| Statistical misrepresentation detected | QA4a | STOP, revision required |
| Missing critical figures | QA4b | STOP, revision required |
| QA script execution fails | Any | STOP, investigate |

---

## Anti-Patterns

**DO NOT skip QA for "simple" scripts.** Even simple fetch or filter operations can produce surprising results. Every Stage 5-8 script gets a QA checkpoint.

**DO NOT conflate CP and QA failures.** A script can pass CP3 but fail QA3 if the validation was inadequate. QA catches what CP misses.

**DO NOT create QA-of-QA loops.** QA scripts themselves don't need secondary review. If a QA script fails, debug the QA script or the original script, not both recursively.

**DO NOT treat all BLOCKERs the same.** Methodology BLOCKERs escalate immediately. Technical BLOCKERs get revision attempts.

**DO NOT proceed with unresolved BLOCKERs.** The entire point of QA is to catch issues early. Proceeding with known BLOCKERs defeats the purpose.

**DO NOT write QA scripts that only re-run the original script's checks.** QA value comes from orthogonal validation — checking from a different angle. If your QA script duplicates the original's checks with no additions, you've added audit trail but not safety.

**DO NOT issue PASSED without articulating WHY.** "All checks passed" is not a QA finding — it's an absence of findings. A proper PASSED includes reasoning: what you looked for, what alternative failure modes you considered, and why you're confident the code is correct.
