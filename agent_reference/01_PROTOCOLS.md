# Protocol Reference

This document contains the full details for all six protocols. Protocols 1-5 are essential to every Full Pipeline analysis. Protocol 6 is used for session recovery.

---

## Protocol Overview

| Protocol | Name | Purpose | Phase | Executed By |
|----------|------|---------|-------|-------------|
| **1** | Data Discovery | Identify and understand available data | Phase 1 | Subagents (explore) |
| **2** | Data Acquisition | Retrieve and clean data from API | Phase 3 | Subagents (general-purpose) |
| **3** | Validation Checkpoints | Validate data at critical points | Phase 3-4 | Orchestrator + Code |
| **4** | Plan Management | Maintain Plan as persistent memory | Phase 2, ongoing | Orchestrator |
| **5** | Final Review | Verify completeness before delivery | Phase 5 | Orchestrator |
| **6** | Session Recovery | Resume interrupted analyses | Any | Orchestrator |

---

# Protocol 1: Data Discovery

**Phase:** 1 (Discovery & Scoping)
**Stages:** 2-3
**Execution:** Via subagents with `education-data-explorer` and `education-data-source-*` skills

## Purpose

Before writing any data query or analysis code, discover and understand available data sources. This protocol ensures the agent has complete, accurate information about what data exists and its limitations.

## Pre-Discovery: Check Prior Learnings

**Before dispatching Stage 2 subagent, the orchestrator should check prior learnings.**

### Repository-Level Learnings (Always Available)

Source-specific knowledge (API variable name discrepancies, endpoint gotchas, data availability and lag times, pagination and error handling patterns) is now embedded directly in the relevant `education-data-source-*` skills. These skills are loaded automatically by subagents during exploration and querying -- no separate learnings file needs to be consulted.

### Project-Level Learnings (When Available)

If prior analyses exist in `research/`, search for relevant learnings:

```bash
# Search for learnings mentioning intended data sources
grep -rl "[data-source]" research/*/LEARNINGS.md
```

**When to search project learnings:**
- ≥3 prior analyses exist in `research/`
- Similar data sources or analysis types planned
- User references prior work

**What to extract:**
- Data source gotchas not yet in repository-level file
- Methodology insights for similar analyses
- Time sinks to avoid

See `agent_reference/08_LESSONS_LEARNED.md: Consuming Prior Learnings` for full protocol.

---

## Stage 2: Data Exploration

**Skill:** `education-data-explorer`
**Subagent Type:** `Plan`

### Invocation Pattern

```python
Task({
    description: "Stage 2: Data Exploration",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'education-data-explorer'.

**RESEARCH QUESTION:**
[User's research question]

**CONTEXT:**
[Any clarifications or constraints from user]

**THOROUGHNESS DIRECTIVE:**
- Search ALL relevant data levels (schools, districts, colleges as appropriate)
- Consider multiple potential data sources before recommending
- Flag ALL variables that might need deeper source-specific investigation
- Check year coverage against research question needs
- Include a 'Limitations Encountered' section in your output

**OUTPUT FORMAT:**
Return findings in this structure:
1. Recommended Data Level: [schools | school-districts | college-university]
2. Candidate Endpoints: [table with endpoint, source, description, years]
3. Key Variables: [table with variable, endpoint, type, description]
4. Variables Flagged for Deep-Dive: [table with variable, reason]
5. Limitations Encountered: [table with limitation, impact, resolution]
6. Completeness Assessment: [checklist of what was searched]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "Plan"
})
```

### Expected Output

**From Stage 2:**
- Recommended data level (schools, school-districts, college-university)
- Candidate endpoints with source, description, and year coverage
- Key variables identified for research question
- Variables flagged for deep-dive with rationale
- Limitations encountered during exploration
- Completeness assessment checklist

### Gate Criteria

Before proceeding to Stage 3:
- [ ] At least one candidate endpoint identified
- [ ] Key variables identified for research question
- [ ] Variables requiring deep-dive explicitly flagged
- [ ] Year coverage verified
- [ ] If no data found: STOP and escalate to user

---

## Stage 3: Source Deep-Dive

**Skills:** `education-data-source-*` (one per source)
**Subagent Type:** `Plan`

### Invocation Pattern

```python
Task({
    description: "Stage 3: Source Deep-Dive - [Source Name]",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'education-data-source-[source]'.

**CONTEXT FROM STAGE 2:**
[Paste relevant Stage 2 findings]

**VARIABLES TO INVESTIGATE:**
[List of variables flagged for deep-dive]

**THOROUGHNESS DIRECTIVE:**
- Extract ALL coded value mappings for flagged variables
- Document ALL suppression patterns and thresholds
- Identify ALL source-specific caveats and limitations
- Note ANY cross-state comparability issues
- Check for historical definition changes
- Include COVID-19 impact notes (2020-2021 data)

**OUTPUT FORMAT:**
Return findings in this structure:
1. Source-Specific Caveats: [table with caveat, impact, mitigation]
2. Coded Value Mappings: [table with variable, code, meaning, action]
3. Suppression Patterns: [table with variable, rate, threshold, impact]
4. Cross-State Comparability: [table with analysis type, valid?, notes]
5. Critical Warnings: [numbered list with mitigation strategies]
6. Limitations Encountered: [table with limitation, impact, resolution]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "Plan"
})
```

**Note:** If multiple sources are needed (e.g., CCD + CRDC), invoke Stage 3 separately for each source.

### Expected Output

**From Stage 3:**
- Source-specific caveats with mitigation strategies
- Complete coded value mappings
- Suppression patterns and thresholds
- Cross-state comparability assessment
- Critical warnings

### Gate Criteria

Before proceeding to Phase 2:
- [ ] All flagged variables investigated
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings have mitigation strategies
- [ ] All LOW confidence findings resolved or escalated

---

## Re-run Guidance

If user clarifications reveal that discovery was inadequate:

| Situation | Stage(s) to Re-run | Mode |
|-----------|-------------------|------|
| Wrong endpoints identified | Stage 2 | Refresh |
| Missing data source | Stage 2, 3 | Additive |
| Caveats misunderstood | Stage 3 | Refresh (affected source) |

**Refresh Mode:** Replace prior output with new findings
**Additive Mode:** Supplement prior output with additional findings

---

# Protocol 2: Data Acquisition

**Phase:** 3 (Data Acquisition & Preparation)
**Stages:** 5-6
**Execution:** Via subagents with `education-data-query` and `education-data-context` skills

## Purpose

Retrieve data from the Education Data Portal API and apply proper context/cleaning based on source-specific knowledge.

## File-First Execution

**CRITICAL:** All code in Protocol 2 follows the **file-first pattern**:
1. Write script to `scripts/stage{5,6}_{type}/` before execution
2. Execute via Bash with output capture
3. Append output to script as comments
4. Version failed scripts (`_a`, `_b`, etc.)

See `agents/research-executor.md` for the complete protocol.

## Stage 5: Data Retrieval

**Skill:** `education-data-query`
**Subagent Type:** `general-purpose` (requires file write capability)

### Invocation Pattern

```python
Task({
    description: "Stage 5: Data Retrieval",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'education-data-query'.

**QUERY SPECIFICATION (from Plan):**
Endpoint: [endpoint path]
Years: [years]
Filters: [filter parameters]
Variables: [variables to select]
Expected Records: [approximate count]

**THOROUGHNESS DIRECTIVE:**
- Use pagination if dataset exceeds 10K records
- Validate response shape immediately after fetch
- Check for API errors and rate limiting
- Save data in BOTH parquet AND csv formats
- Document any API issues encountered

**OUTPUT FORMAT:**
Return findings in this structure:
1. Fetch Summary:
   - Records retrieved: [count]
   - Columns: [list]
   - Years present: [list]
   - API issues: [any problems encountered]
2. Data Freshness Report:
   | Source | Requested Years | Latest Available | Lag Warning |
   |--------|-----------------|------------------|-------------|
   | [source] | [requested] | [latest] | [⚠️ if gap exists] |
   
   - Impact: [How this affects the analysis]
   - Recommendation: [Adjust years or proceed with caveat]
3. Initial Validation:
   - Shape: [rows x cols]
   - Missing values: [summary by column]
   - Unexpected values: [any anomalies]
4. File Locations:
   - Parquet: [path]
   - CSV: [path]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "general-purpose"
})
```

### Validation (CP1)

Immediately after data fetch:

```python
# CP1: Post-Fetch Validation
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.to_list()}")
print(f"Types:\n{df.dtypes}")
print(f"Null counts:\n{df.null_count()}")
print(f"Years present: {df['year'].unique().to_list()}")

# STOP conditions
assert len(df) > 0, "STOP: Empty dataset returned"
assert len(df) < 1_000_000, "WARNING: Very large dataset - verify expected"
```

### Gate Criteria

Before proceeding to Stage 6:
- [ ] Data retrieved successfully
- [ ] Row count within expected range
- [ ] Critical columns present
- [ ] Years match specification
- [ ] Data saved to `data/raw/` (parquet + csv)
- [ ] **If data lag ≥3 years:** User notified and decision documented in Plan
- [ ] **If COVID years (2020-2021) included:** Warning documented in Plan's COVID-19 Data Quality Considerations section

---

## Stage 6: Context Application

**Skill:** `education-data-context`
**Subagent Type:** `general-purpose` (requires file write capability)

### Invocation Pattern

```python
Task({
    description: "Stage 6: Context Application",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'education-data-context'.

**DATA SOURCE:**
[Source name from Stage 2/3]

**RAW DATA SUMMARY:**
[Shape, columns, years from Stage 5]

**CAVEATS FROM STAGE 3:**
[Relevant caveats and coded value mappings]

**THOROUGHNESS DIRECTIVE:**
- Apply coded value filters (-1, -2, -3) as specified
- Calculate suppression rates for key variables
- BLOCK if cross-state assessment comparison attempted
- BLOCK if suppression rate exceeds 50%
- Generate proper citation text
- Document all cleaning decisions

**OUTPUT FORMAT:**
Return findings in this structure:
1. Cleaning Applied:
   - Coded values filtered: [summary]
   - Rows removed: [count and percentage]
2. Data Quality Report:
   - Suppression rate: [percentage]
   - Missing value summary: [by variable]
3. Validity Check:
   - Analysis type: [description]
   - Valid: [Yes/No/Conditional]
   - Warnings: [any concerns]
4. Citation:
   - Full citation text: [citation]
5. Clean Data Location:
   - Parquet: [path]
   - CSV: [path]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "general-purpose"
})
```

### Validation (CP2)

After cleaning:

```python
# CP2: Post-Cleaning Validation
print(f"Original rows: {len(raw_df)}")
print(f"Clean rows: {len(clean_df)}")
print(f"Rows removed: {len(raw_df) - len(clean_df)} ({(len(raw_df) - len(clean_df)) / len(raw_df) * 100:.1f}%)")

# Check suppression rate
suppressed = (raw_df['key_variable'] == -3).sum()
suppression_rate = suppressed / len(raw_df)
print(f"Suppression rate: {suppression_rate:.1%}")

# STOP conditions
assert suppression_rate < 0.5, f"STOP: Suppression rate {suppression_rate:.1%} exceeds 50%"
assert len(clean_df) > len(raw_df) * 0.1, "STOP: >90% data loss after cleaning"
```

### Gate Criteria

Before proceeding to Phase 4:
- [ ] Coded values handled appropriately
- [ ] Suppression rate documented and acceptable (<50%)
- [ ] No invalid analysis types attempted
- [ ] Data saved to `data/processed/` (parquet + csv)
- [ ] Citation text generated

---

# Protocol 3: Validation Checkpoints

**Phase:** 3-4 (Data Acquisition through Analysis)
**Execution:** Embedded in code, verified by orchestrator

## Purpose

Validate data at each critical point in the pipeline to catch errors early and ensure data integrity.

## Four Required Checkpoints

### CP1: After Data Fetch

**When:** Immediately after retrieving data from API
**Purpose:** Verify data structure and completeness

```python
# --- CP1 Validation: Post-Fetch ---
# Configure these before running:
#   df = <fetched DataFrame>
#   expected_rows = 10000
#   required_cols = ["ncessch", "school_name", "enrollment", "year"]
print("\n" + "=" * 60)
print("CP1 VALIDATION: POST-FETCH")
print("=" * 60)

cp1_passed = True

# Check 1: Non-empty
has_rows = len(df) > 0
print(f"  [{'PASS' if has_rows else 'FAIL'}] Row count: {len(df):,}")
if not has_rows:
    cp1_passed = False

# Check 2: Row count in range
if has_rows and expected_rows > 0:
    ratio = len(df) / expected_rows
    print(f"  Expected ~{expected_rows:,} rows, got {len(df):,} (ratio: {ratio:.2f}x)")
    if ratio < 0.01:
        print(f"  [WARN] Row count much lower than expected")
    elif ratio > 10:
        print(f"  [WARN] Row count much higher than expected")

# Check 3: Required columns present
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    print(f"  [FAIL] Missing columns: {missing_cols}")
    cp1_passed = False
else:
    print(f"  [PASS] All {len(required_cols)} required columns present")

# Check 4: Critical field missingness
for col in required_cols:
    if col in df.columns:
        null_rate = df[col].null_count() / len(df)
        if null_rate > 0.9:
            print(f"  [FAIL] {col}: {null_rate:.1%} null (>90% threshold)")
            cp1_passed = False
        elif null_rate > 0.5:
            print(f"  [WARN] {col}: {null_rate:.1%} null (high)")

print(f"\nCP1 VALIDATION: {'PASSED' if cp1_passed else 'FAILED'}")
print("=" * 60)

assert cp1_passed, "STOP: CP1 validation failed"
```

**STOP Conditions:**
- Empty dataset
- Missing critical columns
- >90% missing in critical fields

---

### CP2: After Cleaning

**When:** After applying coded value filters and handling suppression
**Purpose:** Verify data quality and acceptable loss rates

```python
# --- CP2 Validation: Post-Cleaning ---
# Configure these before running:
#   raw_df = <DataFrame before cleaning>
#   clean_df = <DataFrame after cleaning>
#   key_variable = "enrollment"
#   max_suppression = 0.5
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

cp2_passed = True

# Check 1: Data loss rate
rows_removed = len(raw_df) - len(clean_df)
loss_rate = rows_removed / len(raw_df) if len(raw_df) > 0 else 0

print(f"\nData Loss:")
print(f"  Raw rows:     {len(raw_df):,}")
print(f"  Clean rows:   {len(clean_df):,}")
print(f"  Rows removed: {rows_removed:,} ({loss_rate:.1%})")

if loss_rate > 0.9:
    print(f"  [FAIL] Data loss rate {loss_rate:.1%} exceeds 90%")
    cp2_passed = False
elif loss_rate > 0.5:
    print(f"  [WARN] High data loss rate: {loss_rate:.1%}")
else:
    print(f"  [PASS] Data loss rate {loss_rate:.1%} within tolerance")

# Check 2: Suppression rate
if key_variable in raw_df.columns:
    suppressed = (raw_df[key_variable] == -3).sum()
    suppression_rate = suppressed / len(raw_df) if len(raw_df) > 0 else 0
    if suppression_rate > max_suppression:
        print(f"  [FAIL] {key_variable}: {suppression_rate:.1%} suppressed (>{max_suppression:.0%} threshold)")
        cp2_passed = False
    elif suppression_rate > 0.2:
        print(f"  [WARN] {key_variable}: {suppression_rate:.1%} suppressed (notable)")
    else:
        print(f"  [PASS] {key_variable}: {suppression_rate:.1%} suppressed")

# Check 3: No coded values remaining
print(f"\nCoded Values Check (clean data):")
coded_found = False
for col in clean_df.columns:
    if clean_df[col].dtype in [pl.Int32, pl.Int64, pl.Float64]:
        coded_remaining = (clean_df[col] < 0).sum()
        if coded_remaining > 0:
            print(f"  [WARN] {col}: {coded_remaining} coded values remain")
            coded_found = True
if not coded_found:
    print("  [PASS] No coded values remain in clean data")

print(f"\nCP2 VALIDATION: {'PASSED' if cp2_passed else 'FAILED'}")
print("=" * 60)

assert cp2_passed, "STOP: CP2 validation failed"
```

**STOP Conditions:**
- >90% data loss
- >50% suppression rate

---

### CP3: After Transformation

**When:** After joins, aggregations, or derived variable creation
**Purpose:** Verify transformations preserved data integrity

```python
# --- CP3 Validation: Post-Transformation ---
# Configure these before running:
#   input_df = <DataFrame before transformation>
#   output_df = <DataFrame after transformation>
#   operation = "Join CCD + MEPS"
#   expected_relationship = "same"  # "same", "fewer", "more", "aggregated"
print("\n" + "=" * 60)
print(f"CP3 VALIDATION: POST-TRANSFORMATION ({operation})")
print("=" * 60)

cp3_passed = True

# Check 1: Row count relationship
input_rows = len(input_df)
output_rows = len(output_df)
row_change = output_rows - input_rows

print(f"\nRow Count Change:")
print(f"  Input rows:  {input_rows:,}")
print(f"  Output rows: {output_rows:,}")
print(f"  Change:      {row_change:+,}")
print(f"  Expected:    {expected_relationship}")

if expected_relationship == "same" and row_change != 0:
    print(f"  [WARN] Expected same row count, but changed by {row_change:+,}")
elif expected_relationship == "fewer" and row_change >= 0:
    print(f"  [WARN] Expected fewer rows, but count changed by {row_change:+,}")
elif expected_relationship == "more" and row_change <= 0:
    print(f"  [WARN] Expected more rows, but count changed by {row_change:+,}")
else:
    print(f"  [PASS] Row count relationship matches expectation")

# Check 2: Unexpected NAs introduced
print(f"\nNew Null Values:")
new_nulls_found = False
common_cols = set(input_df.columns) & set(output_df.columns)
for col in sorted(common_cols):
    input_nulls = input_df[col].null_count()
    output_nulls = output_df[col].null_count()
    new_nulls = output_nulls - input_nulls
    if new_nulls > 0:
        print(f"  [WARN] {col}: {new_nulls:,} new nulls")
        new_nulls_found = True
if not new_nulls_found:
    print("  [PASS] No new nulls introduced")

# Check 3: Extreme row loss
if input_rows > 0:
    loss_rate = 1 - (output_rows / input_rows)
    if loss_rate > 0.9:
        print(f"  [FAIL] Row count dropped by {loss_rate:.1%} (>90% threshold)")
        cp3_passed = False

print(f"\nCP3 VALIDATION: {'PASSED' if cp3_passed else 'FAILED'}")
print("=" * 60)

assert cp3_passed, "STOP: CP3 validation failed"
```

**STOP Conditions:**
- >90% row loss after transformation

---

### CP4: Before Output

**When:** Before generating final outputs
**Purpose:** Verify analysis is complete and consistent with Plan

```python
from pathlib import Path

# --- CP4 Validation: Pre-Output ---
# Configure these before running:
#   analysis_df = <final analysis DataFrame>
#   required_columns = ["ncessch", "year", "enrollment", "poverty_rate"]
#   critical_columns = ["ncessch", "year"]
#   required_figures = ["enrollment_trends.png", "poverty_scatter.png"]
#   figures_dir = Path("output/figures")
#   required_sections = ["Executive Summary", "Key Findings", "Limitations"]
print("\n" + "=" * 60)
print("CP4 VALIDATION: PRE-OUTPUT")
print("=" * 60)

cp4_passed = True

# Check 1: Required columns in final data
missing_cols = [c for c in required_columns if c not in analysis_df.columns]
if missing_cols:
    print(f"  [FAIL] Missing required columns: {missing_cols}")
    cp4_passed = False
else:
    print(f"  [PASS] All {len(required_columns)} required columns present")

# Check 2: No NAs in critical columns
print(f"\nCritical Column Nulls:")
for col in critical_columns:
    if col in analysis_df.columns:
        null_count = analysis_df[col].null_count()
        if null_count > 0:
            print(f"  [FAIL] {col}: {null_count:,} nulls")
            cp4_passed = False
        else:
            print(f"  [PASS] {col}: 0 nulls")

# Check 3: Required figures generated
print(f"\nRequired Figures:")
for fig in required_figures:
    fig_path = figures_dir / fig
    if fig_path.exists():
        size_kb = fig_path.stat().st_size / 1024
        print(f"  [PASS] {fig} ({size_kb:.1f} KB)")
        if size_kb < 10:
            print(f"  [WARN] {fig} is suspiciously small")
    else:
        print(f"  [FAIL] {fig} NOT FOUND")
        cp4_passed = False

# Check 4: Report sections complete
if required_sections:
    print(f"\nRequired Report Sections: {required_sections}")
    print("  (Verify manually that each section has substantive content)")

print(f"\nCP4 VALIDATION: {'PASSED' if cp4_passed else 'FAILED'}")
print("=" * 60)

assert cp4_passed, "STOP: CP4 validation failed"
```

**STOP Conditions:**
- Missing required columns
- NAs in critical columns
- Missing required figures or report sections

---

## Secondary Validation: QA Checkpoints (QA1-QA4)

**When:** After each script execution in Stages 5-8
**Executor:** code-reviewer agent (invoked by orchestrator)
**Purpose:** Independent secondary validation of output quality and methodology alignment

### Relationship to Primary Checkpoints

| Aspect | CP Checkpoints (CP1-CP4) | QA Checkpoints (QA1-QA4) |
|--------|--------------------------|--------------------------|
| **Timing** | Inline, during script execution | After script execution |
| **Executor** | research-executor (embedded in code) | code-reviewer (separate agent) |
| **Focus** | Operational correctness (shape, types, counts) | Methodology alignment, data quality, logic |
| **Output** | PASSED/FAILED (binary) | PASSED/WARNING/INFO/BLOCKER (graduated) |
| **Failure Mode** | STOP execution | Revision attempt (max 2) or escalate |

**Key Insight:** CP checkpoints catch **operational failures** (empty data, wrong types, missing columns). QA checkpoints catch **logical errors** (wrong methodology, data misinterpretation, validation gaps).

### QA Checkpoint Definitions

| Checkpoint | Stage | What It Validates |
|------------|-------|-------------------|
| **QA1** | 5 (Post-Fetch) | Schema correctness, year coverage, ID uniqueness, unexpected distributions |
| **QA2** | 6 (Post-Clean) | Coded value handling, suppression calculation, filtering logic |
| **QA3** | 7 (Post-Transform) | Join cardinality, row preservation, aggregation logic, derived column correctness |
| **QA4** | 8 (Post-Viz) | Figure existence, data source accuracy, visual correctness |

### QA Severity Classification

| Severity | Definition | Orchestrator Response |
|----------|------------|----------------------|
| **BLOCKER** | Code produces invalid results | Trigger revision (max 2 attempts) |
| **WARNING** | Code works but has concerns | Log for Stage 10 aggregation, proceed |
| **INFO** | Suggestions for improvement | Log only, proceed |

### QA Recovery Protocol

When code-reviewer returns BLOCKER:

```
BLOCKER returned by code-reviewer
    │
    ├─ Is it a methodology issue?
    │   ├─ YES → STOP, escalate to user immediately
    │   └─ NO → Continue to revision flow
    │
    ├─ Revision Attempt 1:
    │   ├─ research-executor creates versioned revision (_a.py)
    │   ├─ code-reviewer re-reviews
    │   └─ Resolved? → Proceed; Still BLOCKER? → Attempt 2
    │
    ├─ Revision Attempt 2:
    │   ├─ research-executor creates second revision (_b.py)
    │   ├─ code-reviewer re-reviews
    │   └─ Resolved? → Proceed; Still BLOCKER? → Escalate
    │
    └─ After 2 failed attempts:
        └─ STOP and escalate to user with explanation
```

### Integration with Protocol 3

QA checkpoints complement, not replace, CP checkpoints:

1. **Stage 5:** CP1 validates fetch success → QA1 validates data quality
2. **Stage 6:** CP2 validates cleaning metrics → QA2 validates methodology
3. **Stage 7:** CP3 validates transformation → QA3 validates logic and cardinality
4. **Stage 8:** QA4 validates visualization correctness (no CP checkpoint at Stage 8)
5. **Stages 11-12:** CP4 validates final output completeness (runs during Final Review)

Both must pass for stage handoff. A script can pass CP validation but fail QA review.

**See:** `agent_reference/QA_CHECKPOINTS.md` for complete checkpoint definitions and `agents/code-reviewer.md` for the QA agent protocol.

---

# Protocol 4: Plan Management

**Phase:** 2 (created), ongoing (updated)
**Execution:** Orchestrator

## Purpose

Maintain the Plan document as the single source of truth for the analysis, enabling context transfer to subagents and session continuity.

## Plan Creation (Phase 2, Stage 4)

### Timing

Create the Plan document **after** completing Phase 1 (Discovery) and **before** starting Phase 3 (Data Acquisition).

### Creation Checklist

- [ ] Project folder created: `research/YYYY-MM-DD [Title]/`
- [ ] Plan file created from template
- [ ] Original request captured verbatim
- [ ] Clarifications documented
- [ ] All Stage 2 findings integrated
- [ ] All Stage 3 findings integrated
- [ ] Methodology decisions documented
- [ ] Output specification complete

### Completeness Standard

The Plan must be **self-contained**: any subagent should be able to execute its stage with ONLY the Plan as context (plus skill knowledge).

**Test:** Read the Plan. Could you execute the analysis without any additional conversation context?

### Plan Completeness Verification (REQUIRED)

Before proceeding to Phase 3, verify the Plan meets completeness standards. See `02_WORKFLOW_STAGES.md: Stage 4 - Plan Completeness Gate` for the complete verification checklist.

**Critical sections that must be complete:**
1. Query Specification (all fields populated)
2. Transformation Sequence (all rows complete with validation criteria and cardinality)
3. Validation Checkpoints (expected values defined for CP1-CP4)

**If verification fails:** Do not proceed; complete missing sections first.

## Plan Updates

Update the Plan as the analysis progresses:

| Event | Update Required |
|-------|-----------------|
| Decision made | Add to Decisions Log |
| Limitation discovered | Add to appropriate section |
| Deviation from plan | Document in Deviations section |
| Checkpoint passed | Update status |
| Error encountered | Document in Issues section |
| Phase completed | Update Current Status |
| **Risk identified** | **Add to Risk Register (see below)** |

## Risk Register Updates

The Risk Register in the Plan document MUST be updated when new risks are discovered during execution.

**Update Triggers:**

| Trigger Event | Risk Type | When to Add |
|---------------|-----------|-------------|
| Stage 3 discovers source-specific limitations | Data Quality | When caveats affect analysis validity or completeness |
| Stage 5 fetch returns unexpected shape | Data Availability | When row count deviates significantly from expected |
| Stage 6 suppression rate is 30-50% | Data Quality | Even if below STOP threshold (50%), document the risk |
| Stage 6 data lag detected (CP1 Check 6) | Data Quality | When latest year available is older than requested |
| Stage 7 transformation has unexpected row loss | Methodological | When row count drops >20% unexpectedly |
| Stage 7 join cardinality violation | Methodological | When actual cardinality differs from expected |
| Any stage encounters data definition changes | Data Quality | When variable definitions changed between years |

**Update Format:**

Add row to Risk Register section of Plan with:
- **Risk:** Clear description of the issue
- **Likelihood:** Low/Medium/High
- **Impact:** Low/Medium/High (on analysis validity/completeness)
- **Mitigation:** What was done or will be done to address it
- **Owner/Stage:** Which stage discovered and owns the risk

**Example Update:**
```markdown
| Suppression Rate Elevated | Medium | Medium | Aggregate to district level if exceeds 40% | Stage 6 |
```

## Plan for Subagent Invocation

When invoking subagents, include relevant Plan sections:

```python
Task({
    description: "Stage [N]: [Name]",
    prompt: """...
    
**CONTEXT FROM PLAN:**
[Paste relevant sections from Plan]
- Query Specification: [from Plan]
- Expected Values: [from Plan]
- Critical Warnings: [from Plan]

...""",
    subagent_type: "..."
})
```

---

# Protocol 5: Final Review

**Phase:** 5 (Synthesis & Delivery)
**Stage:** 12
**Execution:** Orchestrator

## Purpose

Verify that the completed analysis aligns with the original request and all Plan commitments have been fulfilled using **goal-backward verification**.

---

## Goal-Backward Verification Framework

Before marking any analysis complete, verify each of the three categories below. This approach works backward from the goal state to ensure nothing is missing.

**Verification Stance:** The data-verifier agent approaches this framework with adversarial skepticism — its default hypothesis is that something was missed. See `agents/data-verifier.md` for the complete adversarial verification protocol including cross-artifact coherence, research question stress testing, and the Hidden Narrative principle.

### 1. What Must Be TRUE (Observable Behaviors)

These are properties that must hold for the analysis to be valid:

| Requirement | Verification Method | Status |
|-------------|---------------------|--------|
| Research question answered with evidence | Read Report conclusions | [ ] |
| All Plan commitments fulfilled | Compare Plan vs. deliverables | [ ] |
| No validation checkpoints failed | Review CP1-CP4 status | [ ] |
| Limitations explicitly documented | Check Report limitations section | [ ] |
| Data transformations preserve integrity | Review transformation log | [ ] |
| No coded values in analysis variables | Check processed data | [ ] |
| Suppression rate acceptable (<50%) | Review CP2 results | [ ] |
| Cross-state comparisons valid (if any) | Check against validity matrix | [ ] |

**Verification:** For each item, actively verify (don't assume). Check file contents, run queries, read sections.

---

### 2. What Must EXIST (Concrete Artifacts)

These files must exist in the project folder:

| Artifact | Path | Exists? | Substantive? |
|----------|------|---------|--------------|
| Plan document | `[project]/YYYY-MM-DD [Title] Plan.md` | [ ] | [ ] |
| Marimo notebook | `[project]/YYYY-MM-DD [Title].py` | [ ] | [ ] |
| Stakeholder report | `[project]/YYYY-MM-DD [Title] Report.md` | [ ] | [ ] |
| **Lessons learned** | `[project]/LEARNINGS.md` | [ ] | [ ] |
| Raw data (parquet) | `[project]/data/raw/*.parquet` | [ ] | [ ] |
| Raw data (csv) | `[project]/data/raw/*.csv` | [ ] | [ ] |
| Processed data (parquet) | `[project]/data/processed/*.parquet` | [ ] | [ ] |
| Processed data (csv) | `[project]/data/processed/*.csv` | [ ] | [ ] |
| Visualizations | `[project]/output/figures/*.png` | [ ] | [ ] |
| STATE.md (if multi-session) | `[project]/STATE.md` | [ ] | [ ] |
| CONTEXT.md (if created) | `[project]/CONTEXT.md` | [ ] | [ ] |

**Verification Protocol:**
1. List files in project folder
2. Verify each required file exists
3. Open each file and verify non-empty, valid content
4. Check file naming follows conventions
5. **Check substantiveness** (see below)

---

### 2b. Substantiveness Check (Stub Detection)

Artifacts must contain **real implementation**, not placeholders. Flag these patterns as incomplete:

**Text File Stub Indicators:**
| Pattern | Example | Found In |
|---------|---------|----------|
| TODO comments | `# TODO: implement` | Code files |
| FIXME markers | `FIXME: add validation` | Code files |
| Placeholder text | `[add more]`, `TBD`, `XXX` | Markdown files |
| Empty sections | `## Results\n\n## Conclusion` | Report |
| Template remnants | `[Your finding here]` | Report |

**Code Stub Indicators:**
| Pattern | Example | Concern |
|---------|---------|---------|
| Empty returns | `return None`, `return {}` | Unimplemented function |
| Pass statements | `def process(): pass` | Placeholder function |
| NotImplementedError | `raise NotImplementedError` | Incomplete code |
| Hardcoded test values | `return 42` | Missing real logic |

**Data Stub Indicators:**
| Pattern | Example | Concern |
|---------|---------|---------|
| Single unique value | All rows have same value | Data not actually processed |
| All zeros | Count column is all 0 | Calculation not run |
| All nulls | Column entirely null | Join or filter failed |
| Suspiciously round numbers | All values end in 000 | Placeholder data |

**Stub Detection Protocol:**

```python
# Text files
stub_patterns = [
    r'\bTODO\b', r'\bFIXME\b', r'\bPLACEHOLDER\b', r'\bTBD\b',
    r'\bXXX\b', r'\[add more\]', r'\[your .* here\]',
    r'coming soon', r'lorem ipsum'
]

# For each text file:
for pattern in stub_patterns:
    if re.search(pattern, content, re.IGNORECASE):
        flag_as_incomplete(file, pattern)
```

**Substantiveness Checklist:**
- [ ] No TODO/FIXME comments in delivered code
- [ ] No placeholder text in Report
- [ ] No empty function bodies
- [ ] Data has expected variation (not all same value)
- [ ] Count columns have non-zero values
- [ ] All Report sections have content

---

### 3. What Must Be WIRED (Critical Connections)

These connections between components must be valid:

| Connection | Verification | Status |
|------------|--------------|--------|
| Report → Figures | All figure references point to existing files | [ ] |
| Notebook → Data | Import statements load from correct paths | [ ] |
| Plan → Decisions | All methodology decisions documented | [ ] |
| Report → Citations | Citation text matches data sources used | [ ] |
| Files → Naming convention | All files follow YYYY-MM-DD pattern | [ ] |

**Verification Protocol:**
1. Read figure references in Report, verify paths exist
2. Check notebook imports, verify data files exist
3. Compare Plan decisions to implementation
5. Verify citation sources match data used

---

### Verification Execution Protocol

Execute verification in this order:

```
1. EXISTENCE CHECK
   └─ Run: ls -la [project]/**/*
   └─ Verify all required files present
   └─ Check file sizes (non-zero)

2. SUBSTANTIVENESS CHECK
   └─ Scan for stub indicators (TODO, FIXME, TBD)
   └─ Verify non-placeholder content
   └─ Check data has expected variation

3. WIRING CHECK
   └─ Trace Report → Figure references
   └─ Verify Notebook → Data imports

4. TRUTH CHECK
   └─ Compare Report conclusions to research question
   └─ Verify Plan commitments fulfilled
   └─ Check checkpoint statuses in Plan

5. EXECUTION CHECK
   └─ Load notebook: marimo run [notebook].py --host 0.0.0.0 --port 2718 --headless
   └─ Verify linting: ruff check .
```

---

### Agent Integration: Data Verifier

For comprehensive verification, invoke the **data-verifier** agent:

```python
Task({
    description: "Stage 12: Final verification",
    prompt: """You are a Data Verifier. Follow the protocol in `{BASE_DIR}/agents/data-verifier.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **PROJECT TO VERIFY:**
    Path: research/YYYY-MM-DD [Title]/

    **RESEARCH QUESTION:**
    [Verbatim from Plan]

    **PLAN COMMITMENTS:**
    [Paste relevant Plan sections including Observable Truths]

    **QA HISTORY:**
    [Summary of QA findings from Stage 10]

    Execute the full verification protocol including:
    1. Independent assessment (before reading Observable Truths)
    2. Four-level verification (Existence, Substantive, Wired, Coherent)
    3. Adversarial verification (research question stress test, alternative interpretations, silent failure audit)
    4. Cross-artifact coherence check

    Return verification report with PASSED/FAILED status and articulated reasoning.
    """,
    subagent_type: "Plan"
})
```

**When to use data-verifier agent:**
- Full Pipeline delivery (always)
- After Revision Mode changes
- When user requests verification
- After fixing issues found in prior verification

---

## Traditional Review Checklist

In addition to goal-backward verification, complete these traditional checks:

### 1. Alignment with Original Request

| Element from Request | Addressed? | Location |
|---------------------|------------|----------|
| [Extract each element] | Yes/No | [Where in deliverables] |

### 2. Clarification Fulfillment

| Clarification | Implemented? | Notes |
|---------------|--------------|-------|
| [Each clarification] | Yes/No | [How implemented] |

### 3. Plan Commitments

| Commitment | Fulfilled? | Deviation Notes |
|------------|------------|-----------------|
| Data source | Yes/No | |
| Methodology | Yes/No | |
| Output format | Yes/No | |
| Visualizations | Yes/No | |

### 4. Quality Checklist

| Category | Item | Status |
|----------|------|--------|
| **Data Integrity** | CP1-CP4 passed | [ ] |
| | Coded values handled | [ ] |
| | Suppression documented | [ ] |
| **Code Quality** | `ruff check` passes | [ ] |
| | `ruff format` applied | [ ] |
| **Documentation** | Plan complete | [ ] |
| | Notebook documented | [ ] |
| | Report complete | [ ] |
| | Citations included | [ ] |
| | **LEARNINGS.md created** | [ ] |
| **Files** | All files named correctly | [ ] |
| | Parquet + CSV saved | [ ] |
| | Figures exported | [ ] |

### 5. Deviations

Document any deviations from the original Plan:

| Deviation | Reason | Impact |
|-----------|--------|--------|
| [What changed] | [Why] | [Effect] |

## Review Outcome

**PASSED:** All checks complete, proceed to delivery.

**ISSUES FOUND:**
1. Document issues
2. Resolve issues
3. Re-run affected checkpoints
4. Re-run Final Review

## Delivery Format

After passing Final Review, deliver to user:

```
**Analysis Complete: [Title]**

**Summary:**
[2-3 sentence summary of findings]

**Deliverables:**
- Plan: `research/[folder]/[Plan file]`
- Notebook: `research/[folder]/[Notebook file]`
- Report: `research/[folder]/[Report file]`
- Data: `research/[folder]/data/`
- Figures: `research/[folder]/output/figures/`
- Learnings: `research/[folder]/LEARNINGS.md`

**Key Findings:**
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

**Limitations:**
- [Key limitation 1]
- [Key limitation 2]

**Data Citation:**
> [Full citation]

**Lessons Learned:** [Brief summary of key insights captured - API gotchas, methodology improvements, etc.]

Let me know if you have any questions or would like any modifications.
```

---

# Protocol 6: Session Recovery

**Phase:** Any (recovery protocol)
**Execution:** Orchestrator

## Purpose

Enable stateless recovery when resuming an interrupted analysis after LLM context has been cleared. The Plan document serves as persistent memory for session continuity.

## When to Use

- User returns to an in-progress analysis
- System context has been cleared between sessions
- User references a project by name or date

## Recovery Procedure

### Step 1: Locate Project

Search `research/` directory for matching project folder:
- Match on date: `research/YYYY-MM-DD*/`
- Match on keywords from user's message
- List candidates if multiple matches

### Step 2: Read Plan Document

Load the complete Plan document into context:
- Read entire Plan file (not just sections)
- Pay special attention to:
  - Current Status & To-Do's section
  - Transformation Log (if in Stage 7)
  - Decisions Log
  - Issues/Blocked Items

### Step 3: Verify File System State

Check which artifacts exist vs. are expected:

```python
expected_files = {
    "plan": f"{date_prefix} {title} Plan.md",
    "notebook": f"{date_prefix} {title}.py",
    "report": f"{date_prefix} {title} Report.md",
    "raw_data": "data/raw/",
    "processed_data": "data/processed/",
    "figures": "output/figures/"
}

# Check existence for each
```

### Step 4: Identify Resume Point

From Plan's "Current Status & To-Do's" section:
- Current Phase: [1-5]
- Current Stage: [1-12]
- Status: [In Progress | Blocked | Complete]
- Last Checkpoint: [CP# result]

Determine what's complete and what remains.

### Step 5: Present Recovery Summary

```markdown
**Session Recovery: [Project Title]**

I found your in-progress analysis:
- Plan: research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title] Plan.md
- Current Stage: [N] - [Stage Name]
- Status: [status]
- Last Checkpoint: [CP#] - [PASSED/FAILED]

**Completed:**
- [✓] Phase 1: Discovery complete
- [✓] Phase 2: Plan created
- [✓] Stage 5: Data retrieved
- [✓] Stage 6: Data cleaned (CP2 passed)

**Remaining:**
- [ ] Stage 7: Transformations (3 of 5 complete)
- [ ] Stage 8-12: Analysis, notebook, QA, report, final review

**Files Present:**
- Raw data: ✓ (data/raw/YYYY-MM-DD_*.parquet)
- Processed data: ✓ (data/processed/YYYY-MM-DD_*.parquet)
- Notebook: ✗ (not yet created)

Ready to continue from Stage 7, Transformation #4?
```

## Recovery from Different Stages

| Stage Interrupted | Recovery Action |
|-------------------|-----------------|
| 1-3 (Discovery) | Re-read findings, continue from incomplete stage |
| 4 (Planning) | Check if Plan is complete, update if needed |
| 5 (Data Retrieval) | Check if data files exist; re-fetch if missing |
| 6 (Context Application) | Check for processed data; re-run if missing |
| 7 (Transformation) | Read Transformation Log, resume from next incomplete step |
| 8 (Visualization) | Check figures directory, regenerate missing figures |
| 9 (Notebook Assembly) | Check if notebook exists; if missing, invoke notebook-assembler agent |
| 10 (QA) | Re-run linting and tests |
| 11-12 (Delivery) | Check if report exists, regenerate if needed |

## Blocked/Failed Recovery

If the analysis is marked as "Blocked" or has failed checkpoints:
1. Read the Issue description from Plan
2. Present issue to user
3. Ask for guidance before proceeding

**Example:**
```markdown
**Recovery Issue: Analysis Blocked**

This analysis is currently blocked at Stage 6 (Context Application).

**Issue:** Suppression rate of 52% exceeds 50% threshold (CP2 failed)

**Options documented in Plan:**
1. Aggregate to district level (reduces suppression)
2. Exclude suppressed variable from analysis
3. Proceed with caveat and document limitation

Which approach would you like to take?
```

## Recovery Verification Checklist

Before resuming work:
- [ ] Plan document read completely
- [ ] Current stage/status identified
- [ ] File system state verified
- [ ] Resume point identified
- [ ] Any blocking issues presented to user
- [ ] User confirmed ready to proceed

