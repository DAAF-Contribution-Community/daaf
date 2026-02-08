# Workflow Stages Reference

This document provides detailed execution guidance for each of the 12 stages (plus 2 intermediate stages) in the Full Pipeline workflow.

**Execution Model:** Stages 5-8 follow the **file-first execution pattern**—all code is written to script files before execution, with output appended as comments. See `CLAUDE.md` "File-First Execution Rule" and `agents/research-executor.md` for the complete protocol.

---

## Stage Overview

| Stage | Phase | Name | Primary Skill/Agent | Subagent |
|-------|-------|------|---------------------|----------|
| 1 | 1 | Initial Intake | — | Orchestrator |
| 2 | 1 | Data Exploration | `education-data-explorer` | Plan |
| 3 | 1 | Source Deep-Dive | `*-data-source-*` | Plan |
| **3.5** | 1 | Findings Synthesis (conditional) | `research-synthesizer` agent | general-purpose |
| 4 | 2 | Plan Creation | `data-planner` agent | Orchestrator |
| **4.5** | 2 | Plan Validation (required) | `plan-checker` agent | Plan |
| 5 | 3 | Data Retrieval | `education-data-query` | general-purpose |
| 6 | 3 | Context Application | `education-data-context` | general-purpose |
| 7 | 4 | EDA & Transformation | `data-scientist`, `polars` | general-purpose |
| 8 | 4 | Visualization | `plotnine`, `plotly` | general-purpose |
| 9 | 4 | Notebook Assembly | `marimo` | general-purpose |
| 10 | 4 | Quality Assurance | `ruff` | general-purpose |
| 11 | 5 | Report Generation | — | Orchestrator |
| 12 | 5 | Final Review | `data-verifier` agent (adversarial verification with cross-artifact coherence) | Plan |

**Note:** Stage 3.5 is conditional (invoked only when ≥2 data sources explored). Stage 4.5 is required for all Full Pipeline analyses.

---

## QA Substage Pattern (Stages 5-8) — MANDATORY

**CRITICAL:** After EACH script execution in Stages 5-8, the **orchestrator MUST INVOKE** code-reviewer for secondary QA. This is NOT optional. QA substages are created by active orchestrator invocation, not passively:

| Stage | Execution | QA Substage | Agent |
|-------|-----------|-------------|-------|
| 5 | 5.1 fetch-ccd | 5.1-QA | code-reviewer |
| 5 | 5.2 fetch-meps | 5.2-QA | code-reviewer |
| 6 | 6.1 clean-ccd | 6.1-QA | code-reviewer |
| 7 | 7.1 join-data | 7.1-QA | code-reviewer |
| 7 | 7.2 aggregate | 7.2-QA | code-reviewer |
| 8 | 8.1 plot-enrollment | 8.1-QA | code-reviewer |

### QA Substage Flow

```
research-executor completes script (CP1/CP2/CP3 PASSED)
         ↓
orchestrator invokes code-reviewer
         ↓
code-reviewer creates QA scripts: scripts/qa/stage{N}_{step}_qa1.py (+ qa2..qa5 as warranted)
         ↓
code-reviewer executes QA script, reviews code & output
         ↓
code-reviewer returns: PASSED | WARNING | INFO | BLOCKER
         ↓
    [Severity?]
     ├─ PASSED/INFO → Proceed to next script
     ├─ WARNING → Log for Stage 10, proceed
     └─ BLOCKER → Revision request to research-executor
                       ↓
                  research-executor creates _a.py version
                       ↓
                  code-reviewer re-reviews
                       ↓
                  (max 2 revisions, then escalate)
```

### QA Gate Criteria (Added to Each Stage) — ENFORCED

**IMPORTANT:** Gates G4-G7 now require POSITIVE confirmation that QA was invoked, not just absence of BLOCKER.

Every Stage 5-8 task now includes these MANDATORY requirements:

- [ ] **QA INVOKED** — orchestrator called code-reviewer via Task tool
- [ ] **QA RETURNED** — code-reviewer returned severity (PASSED/WARNING/BLOCKER)
- [ ] **QA status ∈ {PASSED, WARNING}** — BLOCKER resolved via revision or escalated
- [ ] **QA script saved to `scripts/qa/`**

**If QA was never invoked, the gate condition is NOT satisfied.** The orchestrator cannot proceed to the next stage without positive QA confirmation.

See `agents/code-reviewer.md` for the complete QA protocol and `agent_reference/QA_CHECKPOINTS.md` for QA checkpoint definitions.

---

## Context Passing Requirements by Stage Transition

**Principle:** Each stage transition requires explicit context handoff. The orchestrator MUST pass accumulated findings, not just file paths.

### Stage 2 → Stage 3 Context

| Context Item | Source | Required In Stage 3 Prompt |
|--------------|--------|---------------------------|
| Endpoints identified | Stage 2 output | YES — exact endpoint URLs |
| Variables flagged for deep-dive | Stage 2 output | YES — with reasons for flagging |
| Research question | Stage 1 | YES — verbatim |
| Years needed | Stage 1/2 | YES — exact range |
| Geographic scope | Stage 1 | YES — states or national |

### Stage 3 → Stage 4 Context

| Context Item | Source | Required In Stage 4 Prompt |
|--------------|--------|---------------------------|
| Source caveats | Stage 3 output (per source) | YES — all caveats, not summary |
| Coded value mappings | Stage 3 output | YES — complete table |
| Suppression patterns | Stage 3 output | YES — typical rates |
| Cross-state comparability | Stage 3 output | YES — assessment |
| Confidence levels | Stage 3 output | YES — LOW items especially |

### Stage 4 → Stage 5 Context

| Context Item | Source | Required In Stage 5 Prompt |
|--------------|--------|---------------------------|
| Query specifications | Plan | YES — exact endpoint, years, filters |
| Expected row counts | Plan | YES — ranges |
| Risk Register items for fetch | Plan | YES — relevant risks |
| Output file paths | Plan | YES — explicit paths |

### Stage 5 → Stage 6 Context

| Context Item | Source | Required In Stage 6 Prompt |
|--------------|--------|---------------------------|
| Raw data file paths | Stage 5 output | YES — exact paths |
| CP1 validation results | Stage 5 output | YES — what passed/failed |
| Source caveats | Stage 3 → Plan | YES — inlined, not just referenced |
| Coded value handling rules | Plan | YES — complete specification |
| Suppression tolerance | Plan | YES — BLOCKER/WARNING thresholds |

### Stage 6 → Stage 7 Context

| Context Item | Source | Required In Stage 7 Prompt |
|--------------|--------|---------------------------|
| Processed data file paths | Stage 6 output | YES — exact paths |
| CP2 validation results | Stage 6 output | YES — suppression rates |
| EDA findings (for 7.2+) | Stage 7.1 output | YES — distributions, quality issues |
| Prior transformation results (for 7.N) | Stage 7.(N-1) output | YES — row counts, changes, findings |
| Invariants to maintain | Prior transformations | YES — accumulated constraints |

### Code-Reviewer Context (All QA Invocations)

| Context Item | Source | Required In QA Prompt |
|--------------|--------|----------------------|
| Script path | research-executor | YES — exact path |
| Plan expectations | Plan (inlined) | YES — row counts, tolerances |
| Observable Truth contribution | Plan | YES — what this task enables |
| Risk Register items | Plan | YES — relevant mitigations |
| QA tolerance thresholds | Plan/CONTEXT.md | YES — BLOCKER/WARNING criteria |
| Prior QA findings | Accumulated from prior scripts | YES — WARNING items to track |

---

# Phase 1: Discovery & Scoping

## Stage 1: Initial Intake

**Executor:** Orchestrator (main context)
**Purpose:** Understand the user's request and classify engagement mode

### Actions

1. **Parse Request**
   - Identify key terms and objectives
   - Note any explicit constraints (years, geography, etc.)
   - Identify implied requirements

2. **Classify Mode**
   - Apply mode classification decision tree
   - Consider trigger keywords
   - Assess scope and complexity

3. **Confirm Mode**
   - State classification with reasoning
   - Describe expected scope and outputs
   - Await user confirmation (implicit or explicit)

4. **Ask Clarifying Questions (if needed)**
   - Ambiguous scope
   - Missing constraints
   - Multiple interpretations possible

### Output

- Confirmed engagement mode
- Research question formulation
- Any clarifications received

### Gate Criteria

- [ ] Mode classified and confirmed
- [ ] Research question clearly stated
- [ ] Any clarifications documented

### Pre-Flight Checklist (Full Pipeline Mode Only)

**REQUIRED:** Before proceeding past Stage 1 in Full Pipeline mode, confirm scope with user:

```
**Full Pipeline Analysis: Pre-Flight Check**

This analysis will create:
- [ ] Research Plan document
- [ ] Marimo notebook (interactive walkthrough of pre-executed scripts)
- [ ] Stakeholder report
- [ ] Validated datasets (raw + processed)
- [ ] Visualizations

Estimated scope:
- Data sources: [identified sources]
- Years: [year range]
- Approximate records: [estimate]
- Geographic scope: [geography]

Estimated execution time: [time estimate based on complexity]

**Confirm to proceed, or request scope adjustment.**
```

**User may:**
- Confirm → Proceed to Stage 2
- Request scope adjustment → Clarify and reconfirm
- Decline → Switch to Discovery or Targeted Assist mode

---

## Stage 2: Data Exploration

**Executor:** Subagent (explore)
**Skill:** `education-data-explorer`
**Purpose:** Identify available data sources and variables

### Actions

1. **Determine Data Level**
   - Schools (K-12 individual schools)
   - School districts (LEAs)
   - College/university (postsecondary)

2. **Search Endpoints**
   - Query Education Data Portal metadata
   - Identify relevant sources (CCD, IPEDS, CRDC, etc.)
   - Check year coverage

3. **Identify Variables**
   - List variables relevant to research question
   - Note data types
   - Flag variables needing deep-dive

4. **Document Limitations**
   - What couldn't be found
   - Data gaps
   - Coverage limitations

### Thoroughness Directive

```
- Search ALL relevant data levels
- Consider multiple potential data sources
- Flag ALL variables that might need deeper investigation
- Check year coverage against research question needs
- Include 'Limitations Encountered' section
```

### Output Format

```markdown
1. Recommended Data Level: [schools | school-districts | college-university]

2. Candidate Endpoints:
| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|
| ... | ... | ... | ... |

3. Key Variables:
| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|
| ... | ... | ... | ... |

4. Variables Flagged for Deep-Dive:
| Variable | Reason |
|----------|--------|
| ... | ... |

5. Limitations Encountered:
| Limitation | Impact | Resolution |
|------------|--------|------------|
| ... | ... | ... |

6. Completeness Assessment:
- [ ] Schools level searched
- [ ] Districts level searched (if relevant)
- [ ] Colleges level searched (if relevant)
- [ ] Multiple sources considered
```

### Gate Criteria

- [ ] At least one candidate endpoint identified
- [ ] Key variables identified
- [ ] Variables for deep-dive flagged
- [ ] Year coverage verified
- [ ] **If no data found:** STOP, escalate to user

---

## Stage 3: Source Deep-Dive

**Executor:** Subagent (explore)
**Skills:** `*-data-source-*` (one per source)
**Purpose:** Understand source-specific limitations and caveats

### Actions

1. **Load Source Skill**
   - Identify which `*-data-source-*` skill(s) to load
   - One invocation per source

2. **Extract Caveats**
   - Source-specific limitations
   - Population definitions
   - Data collection methodology

3. **Document Coded Values**
   - Standard codes (-1, -2, -3)
   - Source-specific codes
   - Action for each code

4. **Assess Suppression**
   - Suppression thresholds
   - Typical suppression rates
   - Impact on analysis

5. **Check Comparability**
   - Cross-state validity
   - Cross-year consistency
   - Definition changes over time

### Thoroughness Directive

```
- Extract ALL coded value mappings
- Document ALL suppression patterns
- Identify ALL source-specific caveats
- Note ANY cross-state comparability issues
- Check for historical definition changes
- Include COVID-19 impact notes (2020-2021)
```

### Output Format

```markdown
## Source: [Source Name]

### Source-Specific Caveats:
| Caveat | Impact | Mitigation |
|--------|--------|------------|
| ... | ... | ... |

### Coded Value Mappings:
| Variable | Code | Meaning | Action |
|----------|------|---------|--------|
| ... | ... | ... | ... |

### Suppression Patterns:
| Variable | Rate | Threshold | Impact |
|----------|------|-----------|--------|
| ... | ... | ... | ... |

### Cross-State Comparability:
| Analysis Type | Valid? | Notes |
|---------------|--------|-------|
| ... | ... | ... |

### Critical Warnings:
1. **[Warning]:** [Description + Mitigation]

### Limitations Encountered:
| Limitation | Impact | Resolution |
|------------|--------|------------|
| ... | ... | ... |
```

### Gate Criteria

- [ ] All flagged variables investigated
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings have mitigations
- [ ] All LOW confidence findings resolved

---

## Stage 3.5: Findings Synthesis (Conditional)

**Executor:** Subagent (general-purpose)
**Agent:** `research-synthesizer`
**Purpose:** Consolidate findings from parallel Stage 2-3 explorations when multiple data sources were explored

### When to Invoke

This stage is **conditional** and should be invoked when:
- Stage 2-3 explored ≥2 data sources (e.g., CCD + CRDC, IPEDS + Scorecard)
- Conflicting findings exist between sources
- Multiple valid approaches need reconciliation

**Skip this stage if:** Only one data source was explored.

### Actions

1. **Consolidate Parallel Findings**
   - Merge Stage 2 exploration results
   - Merge Stage 3 deep-dive findings per source
   - Identify overlapping variables and entities

2. **Resolve Conflicts**
   - Flag contradictions between sources
   - Document resolution rationale
   - Choose primary vs. supplementary sources

3. **Create Unified Context**
   - Single integrated data model
   - Unified variable mapping
   - Consolidated limitations list

### Invocation Pattern

```python
Task({
    description: "Stage 3.5: Findings Synthesis",
    prompt: """You are a research-synthesizer. Follow the protocol in `{BASE_DIR}/agents/research-synthesizer.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**STAGE 2 FINDINGS:**
[Insert Stage 2 output]

**STAGE 3 FINDINGS (per source):**
[Insert Stage 3 outputs for each source]

**TASK:**
Consolidate these parallel findings into a unified context for Plan creation.

**OUTPUT FORMAT:**
1. Integrated Data Model
2. Conflict Resolution Log
3. Unified Variable Mapping
4. Consolidated Limitations
5. Recommended Approach
""",
    subagent_type: "general-purpose"
})
```

### Gate Criteria

- [ ] All source findings integrated
- [ ] Conflicts identified and resolved
- [ ] Unified context ready for data-planner

---

# Phase 2: Planning

## Stage 4: Plan Creation

**Executor:** Orchestrator (main context)
**Purpose:** Create the Plan document as persistent memory

### Actions

0. **Preserve Original Request for Plan**
   - Copy the user's original request text VERBATIM from the conversation
   - Collect all clarifications received during Stage 1
   - These MUST be passed to the data-planner agent in the Stage 4 invocation prompt
   - The data-planner embeds them in the Plan's `## Original Request & Clarifications` section
   - See `03_SKILL_INVOCATIONS.md` Stage 4 template for the exact invocation pattern

1. **Create Project Folder**
   ```
   research/YYYY-MM-DD [Title]/
   ├── data/
   │   ├── raw/
   │   └── processed/
   └── output/
       └── figures/
   ```

2. **Synthesize Phase 1 Findings**
   - Integrate Stage 2 and Stage 3 outputs
   - Resolve any contradictions
   - Fill gaps with orchestrator context

3. **Document Methodology**
   - Query specification
   - Cleaning approach
   - Transformation steps
   - Aggregation plan

4. **Specify Outputs**
   - Notebook structure
   - Report sections
   - Required visualizations

5. **Create LEARNINGS.md Skeleton**
   - Create `LEARNINGS.md` in the project folder using the template from `08_LESSONS_LEARNED.md`
   - Populate project metadata (title, date, data sources, analysis type)
   - Include all section headers with empty content
   - This is a skeleton — content will be added incrementally during execution

6. **Report to User**
   ```
   **Progress Update: Phase 2 Complete**
   - Created: Plan document at [path]
   - Methodology: [brief summary]
   - Next: Proceeding to data acquisition
   
   [User may review Plan; execution continues unless objections raised]
   ```

### Plan Completeness Checklist

- [ ] Original request captured verbatim
- [ ] All clarifications documented
- [ ] All Stage 2 findings integrated
- [ ] All Stage 3 findings integrated
- [ ] Query specification complete
- [ ] Cleaning specification complete
- [ ] Transformation specification complete
- [ ] Output specification complete
- [ ] Validation checkpoint expectations defined

### Plan Completeness Gate (REQUIRED VERIFICATION)

Before proceeding to Phase 3, the orchestrator MUST verify the Plan is complete enough to serve as the single source of truth. Review each critical section:

| Section | Required Content | Verification Check |
|---------|-----------------|-------------------|
| **Original Request** | Verbatim user request present | Contains actual request text, not placeholder |
| **Research Question** | Clear, answerable statement | Specific and measurable |
| **Query Specification** | All fields populated | Endpoint, years, filters, variables, expected records all present |
| **Transformation Sequence** | All rows complete with validation criteria | Each row has: transformation description, expected outcome, validation criteria, cardinality (if join) |
| **Validation Checkpoints** | Expected values defined | CP1-CP4 sections have specific thresholds |
| **Output Specification** | Required deliverables listed | Notebook structure, report sections, visualizations specified |

**Completeness Test:** 
Could a subagent execute any stage of this analysis with ONLY the Plan as context (plus skill knowledge), without access to the original conversation?

**If ANY section fails verification:**
- DO NOT proceed to Phase 3
- Complete the missing sections
- Document decisions in Decisions Log
- Re-run completeness verification

**Special Focus: Transformation Sequence Table**
This table is CRITICAL. Each row must have:
- Transformation description (what operation)
- Expected outcome (row count change, column changes)
- Validation criteria (how to verify success)
- Join cardinality (if transformation is a join: "1:1", "1:many", "many:1", "many:many", or "N/A")

Incomplete transformation sequences lead to incomplete validation and unreliable results.

### Gate Criteria

- [ ] Plan document created at `research/[folder]/YYYY-MM-DD [Title] Plan.md`
- [ ] **STATE.md created** at `research/[folder]/STATE.md` (MANDATORY — Gate G3)
- [ ] **LEARNINGS.md skeleton created** at `research/[folder]/LEARNINGS.md` (MANDATORY — Gate G3)
- [ ] **Plan Completeness Gate passed** (all sections verified)
- [ ] Project folder structure created (`data/raw/`, `data/processed/`, `output/figures/`)
- [ ] User notified
- [ ] Ready to proceed unless user objects

**Gate G3 Enforcement:** Stage 5 CANNOT begin without Plan, STATE.md, and LEARNINGS.md all existing.

---

## Stage 4.5: Plan Validation (Required)

**Executor:** Subagent (explore)
**Agent:** `plan-checker`
**Purpose:** Validate Plan across 6 dimensions before execution begins

### Why This Stage is Required

Plans created by data-planner may contain:
- Incomplete task specifications
- Inconsistent methodology
- Infeasible data requirements
- Missing validation criteria
- Unclear scope boundaries

Stage 4.5 catches these issues **before** expensive data acquisition begins.

### Validation Dimensions

| Dimension | What It Checks |
|-----------|----------------|
| **Completeness** | All required sections populated, no placeholders |
| **Consistency** | Internal references match, no contradictions |
| **Feasibility** | Data sources exist, endpoints valid, years available |
| **Testability** | Observable Truths are measurable, validation criteria specific |
| **Clarity** | Tasks unambiguous, file paths explicit |
| **Scope** | Boundaries defined, escalation conditions clear |

### Invocation Pattern

```python
Task({
    description: "Stage 4.5: Plan Validation",
    prompt: """You are a plan-checker. Follow the protocol in `{BASE_DIR}/agents/plan-checker.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PLAN LOCATION:**
[Path to Plan document]

**TASK:**
Validate the Plan across all 6 dimensions. Return PASSED, PASSED_WITH_WARNINGS, or BLOCKED status.

**OUTPUT FORMAT:**
1. Dimension Scores (PASS/WARN/FAIL for each)
2. Issues Found (with severity and location)
3. Recommended Fixes (if BLOCKED)
4. Overall Status
""",
    subagent_type: "Plan"
})
```

### Validation Loop

```
Plan created (Stage 4)
    ↓
Run plan-checker
    ↓
├─ PASSED → Proceed to Stage 5
├─ PASSED_WITH_WARNINGS → Document warnings, proceed to Stage 5
└─ BLOCKED → Return to data-planner for revision
                ↓
            data-planner revises Plan
                ↓
            Re-run plan-checker (max 2 iterations)
                ↓
            If still BLOCKED after 2 attempts → STOP and escalate to user
```

### Gate Criteria

- [ ] Plan validation completed
- [ ] Status is PASSED or PASSED_WITH_WARNINGS
- [ ] If PASSED_WITH_WARNINGS: warnings documented in Plan
- [ ] Ready to proceed to Phase 3

---

# Phase 3: Data Acquisition & Preparation

## Stage 5: Data Retrieval

**Executor:** Subagent (general-purpose)
**Skill:** `education-data-query`
**Purpose:** Fetch data from Education Data Portal mirrors

**Note:** Uses `general-purpose` subagent type (not `explore`) because it must save data files to `data/raw/`.

### Actions

1. **Construct Query**
   - Build data access URL from Plan specification
   - Construct necessary sample filters (year, subgroups, etc.)

2. **Execute Query**
   - Implement rate limiting
   - Retry on transient errors

3. **Validate Response**
   - Check shape
   - Verify columns
   - Confirm year coverage
   - Confirm subsample specifications

4. **Save Data**
   - Parquet format (for processing)
   - Location: `data/raw/`

5. **>>> INVOKE code-reviewer (MANDATORY) <<<**
   - After research-executor completes, orchestrator MUST invoke code-reviewer
   - Pass: script path, output files, Plan location
   - Wait for QA result before proceeding to Stage 6
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to Stage 6

### Thoroughness Directive

```
- Use pagination for datasets >10K records
- Validate response shape immediately
- Save ONLY in parquet format
- Document any data access issues encountered
```

### Validation (CP1)

```python
# Required checks
assert len(df) > 0, "STOP: Empty dataset"
assert all(col in df.columns for col in required_cols), "STOP: Missing columns"
assert df['year'].is_in(expected_years).all(), "WARNING: Unexpected years"
```

### Output Format

```markdown
### Fetch Summary:
- Endpoint: [URL]
- Records retrieved: [count]
- Columns: [list]
- Years present: [list]
- Data access issues: [any problems]

### Initial Validation (CP1):
- Shape: [rows x cols]
- Missing values: [summary]
- Unexpected values: [any anomalies]
- **CP1 Status:** [PASSED | FAILED]

### File Locations:
- Parquet: `data/raw/YYYY-MM-DD_[source]_[description].parquet`

### Script Saved:
- Path: `scripts/stage5_fetch/{step}_{task-name}.py`
- Includes: Pagination handling, CP1 validation, output paths
```

### Gate Criteria

- [ ] Data retrieved successfully
- [ ] CP1 passed (or warnings documented)
- [ ] Data saved to `data/raw/`
- [ ] **Script saved to `scripts/stage5_fetch/`** with standard header
- [ ] **If data lag ≥3 years:** User notified and decision documented
- [ ] Plan updated with Data Freshness Check table
- [ ] **QA review completed** (code-reviewer invoked after script execution)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER resolved via revision)
- [ ] **QA scripts saved to `scripts/qa/stage5_{step}_qa1.py`** (+ qa2..qa5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 5, CP1 status, raw data paths recorded

---

## Stage 6: Context Application

**Executor:** Subagent (general-purpose)
**Skill:** `education-data-context`
**Purpose:** Apply source-specific cleaning and context

**Note:** Uses `general-purpose` subagent type (not `explore`) because it must save cleaned data files to `data/processed/`.

### Actions

1. **Apply Coded Value Filters**
   - Filter -1 (missing)
   - Filter -2 (not applicable)
   - Filter -3 (suppressed)
   - Document rows removed

2. **Calculate Quality Metrics**
   - Suppression rate
   - Missing value rates
   - Data completeness

3. **Validate Analysis Type**
   - Check for invalid cross-state comparisons
   - Verify methodology is valid for source

4. **Generate Citation**
   - Full citation text
   - Data vintage
   - Access date

5. **Save Clean Data**
   - Parquet format
   - Location: `data/processed/`

6. **>>> INVOKE code-reviewer (MANDATORY) <<<**
   - After research-executor completes, orchestrator MUST invoke code-reviewer
   - Pass: script path, output files, Plan location
   - Wait for QA result before proceeding to Stage 7
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to Stage 7

### Thoroughness Directive

```
- Apply coded value filters as specified in Plan
- Calculate suppression rates for key variables
- BLOCK if cross-state assessment comparison
- BLOCK if suppression rate >50%
- Generate proper citation text
```

### Validation (CP2)

```python
# Required checks
suppression_rate = (raw_df['key_var'] == -3).sum() / len(raw_df)
assert suppression_rate < 0.5, f"STOP: Suppression {suppression_rate:.1%} > 50%"
assert len(clean_df) > len(raw_df) * 0.1, "STOP: >90% data loss"
```

### Output Format

```markdown
### Cleaning Applied:
- Coded values filtered: [summary by code]
- Rows removed: [count] ([percentage]%)

### Data Quality Report (CP2):
- Suppression rate: [percentage]
- Missing value summary: [by variable]
- **CP2 Status:** [PASSED | FAILED]

### Validity Check:
- Analysis type: [description]
- Valid: [Yes | No | Conditional]
- Warnings: [any concerns]

### Citation:
> [Full citation text]

### File Locations:
- Parquet: `data/processed/YYYY-MM-DD_[description].parquet`

### Script Saved:
- Path: `scripts/stage6_clean/{step}_{task-name}.py`
- Includes: Coded value filtering, suppression calculation, CP2 validation
```

### Gate Criteria

- [ ] Coded values handled
- [ ] CP2 passed
- [ ] Citation generated
- [ ] Data saved to `data/processed/`
- [ ] **Script saved to `scripts/stage6_clean/`** with standard header
- [ ] **QA review completed** (code-reviewer invoked after script execution)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER resolved via revision)
- [ ] **QA scripts saved to `scripts/qa/stage6_{step}_qa1.py`** (+ qa2..qa5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 6, CP2 status, suppression rate, processed data paths

---

# Phase 4: Analysis & Notebook Development

## Stage 7: EDA & Transformation

**Executor:** Subagent (general-purpose) - ITERATIVE INVOCATION REQUIRED
**Skills:** `data-scientist`, `polars`
**Purpose:** Explore data and create analysis dataset through step-by-step validated transformations

**CRITICAL:** This stage is executed in MULTIPLE subagent calls, NOT a single invocation. Follow the Iteration Protocol.

### Execution Pattern

**Stage 7 is split into 3 sub-stages:**

#### Sub-Stage 7.1: Initial EDA (No Transformations)

**Executor:** Subagent invocation 1
**Purpose:** Profile data WITHOUT transforming it

**Actions:**
1. **Load Data**
   - Read from `data/processed/`
   - Verify schema matches expectation
   - DO NOT transform yet

2. **Profile Data**
   - Shape, types, memory
   - Distributions (head, describe, value_counts)
   - Identify missing values, outliers
   - Check for unexpected values

3. **Report Findings**
   - Return EDA summary to orchestrator
   - Flag any data quality issues
   - Confirm ready for transformations

**Gate:** Orchestrator reviews EDA before proceeding to transformations

#### Sub-Stage 7.2: Execute Transformations (Iteratively)

**Executor:** Multiple subagent invocations (one per transformation)
**Purpose:** Execute transformations ONE AT A TIME with validation

**For EACH transformation in Plan's Transformation Sequence:**

1. **Orchestrator provides:**
   - Transformation #{n} description
   - Expected outcome
   - Validation criteria
   - Current data location

2. **Subagent executes Iteration Protocol:**
   - **DESCRIBE:** Confirm what will be done
   - **CODE:** Write transformation with pre-state capture
   - **EXECUTE:** Run the code
   - **VALIDATE:** Compare pre/post state, check invariants
   - **DECIDE:** Report PASS/FAIL status

3. **Subagent returns to orchestrator:**
   - Validation report (pre/post metrics, invariants, status)
   - If PASS: Location of transformed data
   - If FAIL: Issue description, proposed fix

4. **Orchestrator reviews:**
   - If PASS: Approve next transformation
   - If FAIL: Request fix (max 2 attempts) or STOP

5. **>>> INVOKE code-reviewer (MANDATORY, after EACH script) <<<**
   - Orchestrator MUST invoke code-reviewer after EACH transformation script
   - Do NOT batch multiple transformations before QA
   - Pass: script path, output files, Plan location
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed to next transformation
   - If PASSED: proceed to next transformation

6. **Repeat** for transformation #{n+1}

**Special Case: Join Transformations**

For join operations, use enhanced validation from `05_VALIDATION_CHECKPOINTS.md`:

1. **Orchestrator provides additional context:**
   - **Expected cardinality** from Plan's Transformation Sequence table (REQUIRED: must be specified as "1:1", "1:many", "many:1", or "many:many")
   - Join keys (column names)
   - Join type (inner, left, right, outer)
   - Expected relationship between datasets

2. **Subagent uses join-specific validation:**
   - Use `validate_join()` function from `05_VALIDATION_CHECKPOINTS.md`
   - Pass cardinality value to validation function
   - Check for fan-out (unexpected row multiplication)
   - Check for data loss (unexpected row reduction)
   - Verify join keys matched as expected
   - Check for null keys in result (shouldn't happen for inner joins)
   - Report cardinality violations with metrics

3. **Join validation STOP conditions:**
   - >90% row loss from left side (for inner/left joins)
   - Cardinality violation (e.g., 1:1 specified but fan-out occurred)
   - Missing join keys in result

**Linking Cardinality to Validation:**
The cardinality in the Plan's Transformation Sequence is the contract. The `validate_join()` function enforces it:
- If Plan says "1:1", validation checks result rows ≈ left rows
- If Plan says "1:many", validation allows result rows > left rows
- Violations trigger warnings or STOP conditions based on severity

**Validation Pattern (Script-Based):**

All transformations are executed through script files, NOT interactive notebooks. See `agent_reference/SCRIPT_TEMPLATE.md` for the complete script format and `agents/research-executor.md` for the file-first protocol.

```python
# scripts/stage7_transform/01_join-data.py
# Each transformation is a SEPARATE SCRIPT with embedded validation
# NOTE: Scripts use sequential top-level code (not wrapped in def main()).

import polars as pl
from pathlib import Path

# PRE-STATE CAPTURE
df = pl.read_parquet("data/processed/2026-01-31_clean.parquet")
pre_shape = df.shape
pre_sample_ids = df.select("id_col").sample(5, seed=42).to_series().to_list()

print(f"PRE-STATE: {pre_shape[0]:,} rows × {pre_shape[1]} cols")

# EXECUTE TRANSFORMATION
df_transformed = df.join(
    other_df,
    on="join_key",
    how="left"
)

# POST-STATE CAPTURE
post_shape = df_transformed.shape
print(f"POST-STATE: {post_shape[0]:,} rows × {post_shape[1]} cols")
print(f"ROW CHANGE: {(post_shape[0]/pre_shape[0]*100):.1f}%")

# VALIDATION (CP3)
row_loss_pct = 1 - (post_shape[0] / pre_shape[0])
invariant_passed = row_loss_pct < 0.9  # <90% row loss

if invariant_passed:
    print("CP3 STATUS: PASSED")
    df_transformed.write_parquet("data/processed/2026-01-31_analysis.parquet")
else:
    print(f"CP3 STATUS: FAILED - Row loss {row_loss_pct:.1%}")

# EXECUTION LOG will be appended here after running:
# python scripts/stage7_transform/01_join-data.py 2>&1
```

**If validation fails:** Create a new versioned script (`01_join-data_a.py`) with fixes. Do NOT modify the original—it serves as audit trail.

#### Sub-Stage 7.3: Final CP3 Validation

**Executor:** Subagent invocation (after all transformations complete)
**Purpose:** Overall validation of transformation sequence

**Actions:**
1. Compare original vs. final dataset
2. Generate transformation summary table
3. Verify all expected transformations applied
4. Check for unexpected nulls introduced
5. Verify invariants (totals, IDs preserved)

**CP3 Validation Report:**
```python
# Overall change summary
print(f"Overall: {original_shape} → {final_shape}")

# Transformation summary table
transformation_summary = pl.DataFrame([
    {"step": 1, "operation": "...", "row_change": "...", "status": "PASSED"},
    {"step": 2, "operation": "...", "row_change": "...", "status": "PASSED"},
    ...
])

# Data quality checks
new_nulls_by_col = {col: post_nulls - pre_nulls for col in ...}

# CP3 Status
cp3_status = "PASSED" | "WARNING" | "FAILED"
```

### Thoroughness Directive

```
MANDATORY EXECUTION PATTERN:
- Execute ONE transformation per subagent invocation
- Capture pre-state BEFORE every transformation
- Validate IMMEDIATELY after every transformation
- Return to orchestrator after EACH validation
- NEVER batch multiple transformations without intermediate validation
- Use script-based validation (see SCRIPT_TEMPLATE.md)
- Follow Iteration Protocol (DESCRIBE → CODE → EXECUTE → VALIDATE → DECIDE)
```

### Output (Across All Sub-Stages)

- **7.1:** EDA summary with data profile
- **7.2:** Validated transformation at each step, intermediate datasets
- **7.3:** Analysis-ready dataset, transformation log, CP3 validation report

### Gate Criteria

**After Sub-Stage 7.1:**
- [ ] Data profiled
- [ ] No blocking data quality issues
- [ ] Ready to proceed to transformations

**After Each Transformation in 7.2:**
- [ ] Pre-state captured
- [ ] Transformation executed
- [ ] Validation performed
- [ ] Status reported (PASS/FAIL)
- [ ] **Script saved to `scripts/stage7_transform/`** with standard header
- [ ] **QA review completed** (code-reviewer invoked after each script)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER resolved via revision)
- [ ] **QA scripts saved to `scripts/qa/stage7_{step}_qa1.py`** (+ qa2..qa5 if warranted)

**After Sub-Stage 7.3:**
- [ ] All transformations complete
- [ ] CP3 validation passed for all transformations
- [ ] **All QA reviews passed** for all transformation scripts
- [ ] Analysis dataset ready at `data/processed/[date]_analysis.parquet`
- [ ] Transformation log complete
- [ ] **All transformation scripts archived in `scripts/stage7_transform/`**
- [ ] **All QA scripts archived in `scripts/qa/`**
- [ ] **STATE.md updated:** Current Stage: 7, all CP3 statuses, Transformation Progress table current

---

## Stage 8: Visualization

**Executor:** Subagent (general-purpose)
**Skills:** `plotnine`, `plotly`
**Purpose:** Create visualizations specified in Plan

### Actions

1. **Create Exploratory Plots**
   - Distributions
   - Relationships
   - Patterns

2. **Create Final Visualizations**
   - As specified in Plan
   - Publication-quality

3. **Export Figures**
   - PNG format
   - Appropriate dimensions
   - Location: `output/figures/`

4. **>>> INVOKE code-reviewer (MANDATORY) <<<**
   - After research-executor completes visualization scripts, orchestrator MUST invoke code-reviewer
   - Pass: script path, output figures, Plan location
   - Wait for QA result before proceeding to Stage 9
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to Stage 9

### Visualization Patterns

**Static (plotnine):**
```python
from plotnine import ggplot, aes, geom_point, theme_minimal

plot = (
    ggplot(df, aes(x='var1', y='var2'))
    + geom_point()
    + theme_minimal()
)
plot.save(f"output/figures/{date_prefix}_plot_name.png", dpi=300)
```

**Interactive (plotly):**
```python
import plotly.express as px

fig = px.scatter(df, x='var1', y='var2', color='category')
fig.write_html(f"output/figures/{date_prefix}_plot_name.html")
fig.write_image(f"output/figures/{date_prefix}_plot_name.png")
```

### Output

- Exported figure files
- Figure descriptions for report

### Gate Criteria

- [ ] All planned visualizations created
- [ ] Figures exported to `output/figures/`
- [ ] **Visualization scripts saved to `scripts/stage8_viz/`** with standard header
- [ ] **QA review completed** (code-reviewer invoked after each visualization script)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER resolved via revision)
- [ ] **QA scripts saved to `scripts/qa/stage8_{step}_qa1.py`** (+ qa2..qa5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 8, QA4 status, figure paths recorded

---

## Stage 9: Script Compilation (NOT Dashboard Building)

**Agent:** `notebook-assembler` (see `agents/notebook-assembler.md`)
**Executor:** Subagent (general-purpose)
**Skill:** `marimo` (for basic syntax only; agent provides behavioral constraints)
**Purpose:** LITERALLY COPY script file contents into marimo cells

> **CRITICAL:** Stage 9 is a FILE COMPILATION task. The agent READS script files and COPIES their contents verbatim into cells. It does NOT generate new code, dashboards, filters, or interactive widgets.

### What Stage 9 IS

- **A file compiler** — Read script files, copy contents into cells
- **A script viewer** — Display what was executed
- **An audit tool** — Show execution logs as proof

### What Stage 9 is NOT

- ❌ **NOT a dashboard builder** — No dropdowns, sliders, multiselects
- ❌ **NOT an analysis tool** — No new aggregations or transformations
- ❌ **NOT an interactive explorer** — No search boxes or filters
- ❌ **NOT a report generator** — Report.md is created in Stage 11

### Key Principle: LITERAL COPY

The agent READS each script file and COPIES its contents:
- **Cell 2:** VERBATIM copy of script code (before execution log marker)
- **Cell 3:** VERBATIM copy of execution log (in accordion)
- **Cell 4:** THE ONLY NEW CODE: `pl.read_parquet()` + `mo.ui.table()`

No paraphrasing. No summarizing. No "improving." Just copy.

### Actions

1. **Scan Script Directories**
   - List all `.py` files in `scripts/stage{5,6,7,8}_*/`
   - Identify final versions (highest suffix: `_b.py` > `_a.py` > base)

2. **For Each Script, Create EXACTLY 4 Cells:**

   **Cell 1 (Markdown):** Header
   - Script filename and path
   - Input/output file paths
   - Checkpoint status

   **Cell 2 (Code):** VERBATIM Script Code
   - READ the script file
   - COPY everything BEFORE the `# EXECUTION LOG` marker
   - Include ALL imports, ALL functions, the ENTIRE body
   - Do NOT modify, summarize, or paraphrase

   **Cell 3 (Markdown):** VERBATIM Execution Log
   - READ the script file
   - COPY everything AFTER the `# EXECUTION LOG` marker
   - Wrap in `mo.accordion()` for collapsed display

   **Cell 4 (Code):** Data Inspection — THE ONLY NEW CODE
   - ONLY these two lines:
     ```python
     df = pl.read_parquet("path/to/output.parquet")
     mo.ui.table(df.head(100))
     ```
   - NO `.filter()`, NO `.with_columns()`, NO aggregations

3. **Test Notebook**
   - Run `marimo run notebook.py --host 0.0.0.0 --port 2718 --headless`
   - Verify all cells execute without errors

### ABSOLUTE PROHIBITIONS

The following are **NEVER ALLOWED** in Stage 9 notebooks:

| Prohibited | Why |
|------------|-----|
| `mo.ui.dropdown()` | Not a dashboard |
| `mo.ui.slider()` | Not a dashboard |
| `mo.ui.multiselect()` | Not a dashboard |
| `mo.ui.text()` for search | Not a dashboard |
| `.group_by()` (new) | No new aggregations |
| `.agg()` (new) | No new aggregations |
| `.pivot()` (new) | No new pivot tables |
| `.filter()` in data cells | Just load and display |
| `.with_columns()` in data cells | Just load and display |
| "Interactive Filters" section | Not a dashboard |
| "Data Explorer" with new code | Not a dashboard |
| "Institution Lookup" feature | Not a dashboard |
| New visualizations | Stage 8 created them |

**If the notebook contains ANY of the above, it FAILED.**

### Notebook Structure Template

```python
import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")

# =============================================================================
# CELL: Title and Navigation
# =============================================================================
@app.cell
def _(mo):
    mo.md("""
    # Analysis Walkthrough: [Title]

    This notebook is an **interactive walkthrough** of the executed analysis scripts.
    Each section corresponds to a script in `scripts/`. You can:
    - Review the code that was executed
    - See the captured output (execution logs)
    - Inspect data at each step
    - Modify and re-run individual steps

    ## Pipeline Overview

    | Stage | Script | Status |
    |-------|--------|--------|
    | 5.1 | `01_fetch-ccd.py` | ✓ Passed |
    | 5.2 | `02_fetch-meps.py` | ✓ Passed |
    | 6.1 | `01_clean-ccd.py` | ✓ Passed |
    | 6.2 | `02_clean-meps.py` | ✓ Passed |
    | 7.1 | `01_join-data_b.py` | ✓ Passed (v3) |
    | 8.1 | `01_enrollment-plot.py` | ✓ Passed |
    """)

# =============================================================================
# CELL: Imports
# =============================================================================
@app.cell
def _():
    import marimo as mo
    import polars as pl
    from pathlib import Path
    return mo, pl, Path

# =============================================================================
# STAGE 5: Data Fetch
# =============================================================================
@app.cell
def _(mo):
    mo.md("""
    ---
    ## Stage 5: Data Fetch

    Scripts in this stage retrieve raw data from the data access mirrors.
    """)

# --- Script 5.1: fetch-ccd ---
@app.cell
def _(mo):
    mo.md("""
    ### 5.1: Fetch CCD Data

    **Script:** `scripts/stage5_fetch/01_fetch-ccd.py`
    **Output:** `data/raw/2026-01-31_ccd_schools.parquet`
    """)

@app.cell
def _(pl, Path):
    # =========================================================================
    # CODE FROM: scripts/stage5_fetch/01_fetch-ccd.py
    # =========================================================================
    # (Insert the main() function content here, adapted for marimo)
    # Users can modify this and re-run to experiment

    # For walkthrough, just load the result:
    fetch_ccd_result = pl.read_parquet("data/raw/2026-01-31_ccd_schools.parquet")
    fetch_ccd_result

@app.cell
def _(mo):
    # Execution log from the script
    mo.accordion({
        "Execution Log (01_fetch-ccd.py)": mo.md("""
```
Executed: 2026-01-31 14:32:05
Duration: 45.23 seconds
Exit code: 0

--- STDOUT ---
============================================================
EXECUTING: fetch-ccd
============================================================
[... captured output ...]
CP1 STATUS: PASSED
```
        """)
    })

# =============================================================================
# STAGE 6: Data Cleaning
# =============================================================================
@app.cell
def _(mo):
    mo.md("""
    ---
    ## Stage 6: Data Cleaning

    Scripts in this stage apply coded value filters and calculate suppression rates.
    """)

# --- Continue pattern for each script ---

# =============================================================================
# STAGE 7: Transformations
# =============================================================================
@app.cell
def _(mo):
    mo.md("""
    ---
    ## Stage 7: Transformations

    **Note:** Script `01_join-data.py` required 2 revisions. The final
    successful version is `01_join-data_b.py`. Failed attempts are preserved
    in the scripts folder for audit.
    """)

# =============================================================================
# FINAL: Summary
# =============================================================================
@app.cell
def _(mo):
    mo.md("""
    ---
    ## Pipeline Summary

    | Stage | Scripts | Status |
    |-------|---------|--------|
    | Stage 5 (Fetch) | 2 scripts | All passed |
    | Stage 6 (Clean) | 2 scripts | All passed |
    | Stage 7 (Transform) | 1 script (3 versions) | Final passed |
    | Stage 8 (Visualize) | 1 script | Passed |

    **Total Revisions:** 2 (all in Stage 7 join operation)

    **Final Analysis Dataset:** `data/processed/2026-01-31_analysis.parquet`
    """)

if __name__ == "__main__":  # marimo framework boilerplate (auto-generated)
    app.run()
```

### Parsing Execution Logs from Scripts

To extract execution logs from script files:

```python
import re
from pathlib import Path

def extract_execution_log(script_path: Path) -> str | None:
    """Extract the execution log section from a script file."""
    content = script_path.read_text()

    # Find the execution log section
    match = re.search(
        r'# EXECUTION LOG\n# =+\n(.*?)(?=\n# =+\s*$|\Z)',
        content,
        re.DOTALL
    )

    if match:
        return match.group(0)
    return None

def get_final_script_version(base_name: str, scripts_dir: Path) -> Path | None:
    """Find the final (successful) version of a script."""
    # List all versions: base.py, base_a.py, base_b.py, etc.
    pattern = f"{base_name}*.py"
    versions = sorted(scripts_dir.glob(pattern))

    if not versions:
        return None

    # Return the last version (highest suffix = final attempt)
    return versions[-1]
```

### Gate Criteria

- [ ] All final script versions identified
- [ ] Each script represented with: header, code, execution log, data preview
- [ ] Navigation cells link to all sections
- [ ] Notebook executes without errors
- [ ] Interactive elements (tables, accordions) work
- [ ] Data flows correctly between cells

---

## Stage 10: Quality Assurance (Enhanced with QA Aggregation)

**Executor:** Subagent (general-purpose)
**Skill:** `ruff`
**Purpose:** Final code quality checks AND aggregation of continuous QA findings from Stages 5-8

### NEW: QA Aggregation Responsibilities

Stage 10 is now the **aggregation point** for all QA findings from Stages 5-8. Before running linting and tests, aggregate and review all QA results.

### Actions

1. **Aggregate Continuous QA Findings**
   - Collect all WARNING items logged during Stages 5-8
   - Collect all INFO items logged during Stages 5-8
   - Review for patterns across multiple scripts
   - Document BLOCKER issues that were resolved (and how)

2. **Generate QA Summary Report**
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
   | 01_join-data.py | Fan-out join | Fixed key uniqueness | 2 |

   ### Outstanding WARNINGs
   | Script | Warning | Assessment |
   |--------|---------|------------|
   | 01_clean-ccd.py | 38% suppression | Acceptable, documented |

   ### INFO Items
   | Script | Observation |
   |--------|-------------|
   | 01_fetch-ccd.py | Could parallelize data access calls |
   ```

3. **Lint Code**
   ```bash
   ruff check . --fix
   ruff format .
   ```

4. **Fix Issues**
   - Address linting errors
   - Max 2 attempts before escalating

### Gate Criteria

- [ ] **QA Summary Report generated** (aggregates all Stages 5-8 findings)
- [ ] **All BLOCKERs resolved** (via revision during Stages 5-8)
- [ ] **All WARNINGs documented** (with assessment of impact)
- [ ] `ruff check` passes
- [ ] `ruff format` applied
- [ ] **If failures persist after 2 attempts:** STOP, escalate

---

# Phase 5: Synthesis & Delivery

## Stage 11: Report Generation

**Executor:** Orchestrator (main context)
**Purpose:** Create stakeholder report

### Actions

1. **Extract Findings**
   - Key insights from notebook
   - Supporting visualizations
   - Methodology summary

2. **Write Report**
   - Follow REPORT_TEMPLATE.md
   - Plain language for stakeholders
   - Include figure references

3. **Include Citations**
   - Data sources
   - Methodology references

### Report Sections

1. Executive Summary (2-3 sentences)
2. Research Question
3. Data & Methods
4. Key Findings (with figures)
5. Limitations
6. Data Sources (citations)

### Gate Criteria

- [ ] Report complete
- [ ] All sections present
- [ ] Figures referenced correctly

---

## Stage 12: Final Review

**Executor:** Orchestrator (main context)
**Purpose:** Verify alignment and completeness

### Actions

1. **Check Alignment**
   - Original request fulfilled?
   - Clarifications implemented?
   - Plan commitments met?

2. **Verify Quality**
   - All checkpoints passed?
   - Code quality verified?
   - Documentation complete?

3. **Document Deviations**
   - What changed from Plan?
   - Why?
   - What's the impact?

4. **Update Plan**
   - Fill Final Review Log section
   - Record outcome

5. **Consolidate LEARNINGS.md (REQUIRED)**
   - Review incremental entries captured during Stages 5-8
   - Fill gaps in sections still empty
   - Expand quick-capture entries where warranted
   - Deduplicate entries describing the same insight
   - Ensure minimum sections populated: What Worked Well, What Didn't Work, Access/Data Gotchas
   - Flush any remaining signals from STATE.md buffer
   - See `agent_reference/08_LESSONS_LEARNED.md` for consolidation protocol

6. **Generate System Update Action Plan (REQUIRED)**
   - Add "System Update Action Plan" section to LEARNINGS.md
   - For each learning: determine if it generalizes beyond this project
   - If yes: identify target file(s) and draft concrete change description
   - If no: place in "Not Actionable" with brief reasoning
   - Assign priority: P1 (correctness), P2 (efficiency), P3 (polish)
   - This plan is NOT auto-executed — it serves as a work queue
   - Include action item count in delivery message

7. **Deliver to User**
   - Summary message
   - File locations
   - Key findings
   - Limitations

### Consolidation & Action Plan Checklist

At Stage 12, the orchestrator consolidates LEARNINGS.md (which already contains incremental entries) and generates the System Update Action Plan:

- [ ] LEARNINGS.md incremental entries reviewed (gaps identified and filled)
- [ ] Quick-capture entries expanded where warranted
- [ ] Duplicate entries merged
- [ ] Minimum sections populated: What Worked Well, What Didn't Work, Access/Data Gotchas
- [ ] STATE.md pending signals flushed
- [ ] System Update Action Plan section added with ≥1 action item or explicit "no generalizable learnings" statement
- [ ] Action items grouped by target type (Skills, Agents, Agent Reference, Orchestrator)
- [ ] Action item count included in delivery message

### Gate Criteria

- [ ] All alignment checks pass
- [ ] Quality verified
- [ ] Deviations documented
- [ ] Plan updated with Final Review Log
- [ ] **LEARNINGS.md consolidated** (incremental entries reviewed, gaps filled)
- [ ] **System Update Action Plan section present** (≥1 action item or "no generalizable learnings")
- [ ] **Key findings flagged for repository consolidation** (in Action Plan)
- [ ] **Action item count included in delivery message**
- [ ] **STATE.md finalized:** Status: Complete, all checkpoints marked, Session History complete
- [ ] User notified with delivery summary
