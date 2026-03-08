# Workflow Stages Reference

This document provides detailed execution guidance for each of the 12 stages (plus 2 intermediate stages) in the Full Pipeline workflow.

> **Domain Extensibility:** This workflow is domain-agnostic. Skill names referenced below (e.g., `education-data-explorer`, `education-data-query`, `education-data-context`) are the demonstration domain defaults. The orchestrator resolves actual skill names from the Plan's Domain Configuration section and provides them in Task prompts. New domains can be added by authoring domain-specific Skills and registering them in the Plan's Domain Configuration.

**Execution Model:** Stages 5-8 follow the **file-first execution pattern**—all code is written to script files before execution, then run as a single Bash call via `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/...` which automatically appends the execution log. Closely read `agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

---

## Stage Overview

| Stage | Phase | Name | Primary Skill/Agent | Subagent |
|-------|-------|------|---------------------|----------|
| 1 | 1 | Initial Intake | — | Orchestrator |
| 2 | 1 | Data Exploration | Domain explorer skill (e.g., `education-data-explorer`) | Plan |
| 3 | 1 | Source Deep-Dive | `*-data-source-*` | Plan |
| **3.5** | 1 | Findings Synthesis | `research-synthesizer` agent | general-purpose |
| 4 | 2 | Plan Creation | `data-planner` agent | Orchestrator (invokes data-planner) |
| **4.5** | 2 | Plan Validation | `plan-checker` agent | Plan |
| 5 | 3 | Data Retrieval | Domain query skill (e.g., `education-data-query`) | general-purpose |
| 6 | 3 | Context Application | Domain context skill (e.g., `education-data-context`) | general-purpose |
| 7 | 4 | EDA & Transformation | `data-scientist`, `polars` | general-purpose |
| 8 | 4 | Analysis & Visualization | `data-scientist`, `polars`, `plotnine`, `plotly` | general-purpose |
| 9 | 4 | Notebook Assembly | `marimo` | general-purpose |
| 10 | 4 | QA Aggregation | — (orchestrator) | — |
| 11 | 5 | Report Generation | `report-writer` agent | general-purpose |
| 12 | 5 | Final Review | `data-verifier` agent (adversarial verification with cross-artifact coherence) | Plan |

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
| 8 | 8.1.1 regression-analysis | 8.1.1-QA (QA4a) | code-reviewer |
| 8 | 8.1.2 effect-sizes | 8.1.2-QA (QA4a) | code-reviewer |
| 8 | 8.2.1 plot-enrollment | 8.2.1-QA (QA4b) | code-reviewer |

### QA Substage Flow

```
research-executor completes script (CP1/CP2/CP3 PASSED)
         ↓
orchestrator invokes code-reviewer
         ↓
code-reviewer creates QA scripts: scripts/cr/stage{N}_{step}_cr1.py (+ cr2..cr5 as warranted)
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

**IMPORTANT:** Gates G5-G8 require POSITIVE confirmation that QA was invoked, not just absence of BLOCKER.

Every Stage 5-8 task includes these MANDATORY requirements:

- [ ] **QA INVOKED** — orchestrator called code-reviewer via Task tool
- [ ] **QA RETURNED** — code-reviewer returned severity (PASSED/WARNING/BLOCKER)
- [ ] **QA status ∈ {PASSED, WARNING}** — BLOCKER resolved via revision or escalated
- [ ] **QA script saved to `scripts/cr/`**

**If QA was never invoked, the gate condition is NOT satisfied.** The orchestrator cannot proceed to the next stage without positive QA confirmation.

### Gate Exhaustion: BLOCKER Resolution Limits

**CRITICAL:** When code-reviewer returns BLOCKER, the orchestrator triggers a revision cycle with a **hard limit of 2 revisions** (base attempt + `_a.py` + `_b.py`). After the second revision attempt:

- **If QA still returns BLOCKER:** Gate is NOT satisfied. STOP execution immediately.
- **If BLOCKER is a methodology violation:** Escalate to user without attempting revisions (same session, immediate stop).
- **Escalation message must include:** Issue description, what was attempted, and why resolution is blocked.

**Result:** BLOCKER that persists after 2 revisions → Automatic escalation gate, no further orchestration.

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

**Note:** Stage 5 may produce multiple scripts (one per fetch task). All outputs must be passed forward.

| Context Item | Source | Required In Stage 6 Prompt |
|--------------|--------|---------------------------|
| All raw data file paths (one per fetch script) | Stage 5 output | YES — exact paths for every file produced |
| CP1 validation results for ALL Stage 5 scripts | Stage 5 output | YES — what passed/failed per script |
| QA1 status for EACH Stage 5 script separately | Stage 5 QA | YES — per-script QA outcomes |
| Source caveats | Stage 3 → Plan | YES — inlined, not just referenced |
| Coded value handling rules | Plan | YES — complete specification |
| Suppression tolerance | Plan | YES — BLOCKER/WARNING thresholds |

### Stage 6 → Stage 7 Context

**Note:** Stage 6 may produce multiple scripts (one per clean task). All outputs must be passed forward.

| Context Item | Source | Required In Stage 7 Prompt |
|--------------|--------|---------------------------|
| All processed data file paths (one per clean script) | Stage 6 output | YES — exact paths for every file produced |
| CP2 validation results for ALL Stage 6 scripts | Stage 6 output | YES — suppression rates per script |
| QA2 status for EACH Stage 6 script separately | Stage 6 QA | YES — per-script QA outcomes |
| EDA findings (for 7.2+) | Stage 7.1 output | YES — distributions, quality issues |
| Prior transformation results (for 7.N) | Stage 7.(N-1) output | YES — row counts, changes, findings |
| Invariants to maintain | Prior transformations | YES — accumulated constraints |

### Code-Reviewer Context (All QA Invocations)

| Context Item | Source | Required In QA Prompt |
|--------------|--------|----------------------|
| Script path | research-executor | YES — exact path |
| Plan expectations | Plan (inlined) | YES — row counts, tolerances |
| Research Outcome contribution | Plan | YES — what this task enables |
| Risk Register items | Plan | YES — relevant mitigations |
| QA tolerance thresholds | Plan (QA Tolerance Decisions section) | YES — BLOCKER/WARNING criteria |
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
   - Await EXPLICIT user confirmation

4. **Ask Clarifying Questions (if needed)**
   - Ambiguous scope
   - Missing constraints
   - Multiple interpretations possible

### Output

- Confirmed engagement mode
- Research question formulation
- Any clarifications received

### Gate Criteria (G1)

- [ ] Mode classified and confirmed
- [ ] Research question clearly stated
- [ ] Any clarifications documented

### Pre-Flight Checklist (Full Pipeline Mode Only)

**REQUIRED:** Before proceeding past Stage 1 in Full Pipeline mode, confirm scope with user:

```
**Full Pipeline Analysis: Pre-Flight Check**

This analysis will create:
- [ ] Research Plan document summarizing all key goals, considerations, decisions, risks, interpretations, work stage summaries, and final work review notes
- [ ] STATE.md session state file (for progress tracking and session recovery)
- [ ] Comprehensive analytic scripts covering data fetch, clean, join, transformation, analysis, and QA for all of the above
- [ ] Validated datasets (raw + processed)
- [ ] Marimo notebook "walkthrough" of successfully completed analysis scripts and their execution runtime logs for inspection
- [ ] Illustrative key data visualizations
- [ ] Summary stakeholder report synthesizing key findings and interpreting key data visualizations
- [ ] LEARNINGS.md lessons learned

Estimated scope:
- Data sources: [identified sources]
- Years: [year range]
- Approximate records: [estimate]
- Geographic scope: [geography]

**Please confirm whether you'd like me to begin with this approach, or let me know if you have any changes you'd like to make.**
```

**User may:**
- Confirm → Proceed to Stage 2
- Request scope adjustment → Clarify and reconfirm
- Decline → Switch to Discovery or Targeted Assist mode
You MUST wait for user confirmation before proceeding.

---

## Stage 2: Data Exploration

**Executor:** Subagent (Plan)
**Skill:** Domain explorer skill (e.g., `education-data-explorer`)
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

### Gate Criteria (G2)

- [ ] At least one candidate endpoint identified
- [ ] Key variables identified
- [ ] Variables for deep-dive flagged
- [ ] Year coverage verified
- [ ] **If no data found:** STOP, escalate to user

---

## Stage 3: Source Deep-Dive

**Executor:** Subagent (Plan)
**Skills:** `*-data-source-*` (one per source)
**Purpose:** Understand source-specific limitations and caveats

### Actions

1. **Load Source Skill**
   - Identify which `*-data-source-*` skill(s) to load
   - One invocation per source
   - **Parallel cap:** If >5 sources identified, sub-batch source-researcher dispatch into groups of ≤5 (hard maximum of 5 concurrent subagents)

2. **Extract Caveats**
   - Source-specific limitations
   - Population definitions
   - Data collection methodology

3. **Document Coded Values**
   - Domain-specific coded values (from Plan Domain Configuration; e.g., -1, -2, -3 for education)
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
- Include impact notes for any flagged years (per FLAG_YEARS in Plan Domain Configuration; e.g., COVID-19 years 2020-2021 for education)
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

### Gate Criteria (G3)

- [ ] All flagged variables investigated
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings have mitigations
- [ ] All LOW confidence findings resolved

---

## Stage 3.5: Findings Synthesis

**Executor:** Subagent (general-purpose)
**Agent:** `research-synthesizer`
**Purpose:** Consolidate findings from Stage 2-3 explorations into unified planning guidance

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

### Gate Criteria (G3.5)

- [ ] All source findings integrated
- [ ] Conflicts identified and resolved
- [ ] Unified context ready for data-planner
- [ ] **PSU1 presented to user**
- [ ] **User confirmed PSU1**

---

### Phase Status Update 1 (PSU1): Discovery Complete

**Trigger:** Gate G3.5 satisfied (synthesis complete, conflicts resolved)
**Blocking:** YES — Stage 4 CANNOT begin until user confirms PSU1

**Actions:**
1. Compile discovery findings from Stages 2, 3, and 3.5
2. Present PSU1 to user using the PSU template (see CLAUDE.md "Phase Status Updates" section)
3. WAIT for explicit user confirmation

**PSU1 Content Requirements:**
- Data sources identified (with endpoints and year ranges)
- Key variables discovered and their availability status
- Source-specific caveats and limitations (from Stage 3 deep-dives)
- Suppression patterns identified
- Cross-source conflicts and how they were resolved (from Stage 3.5)
- Feasibility assessment: can the research question be answered with available data?
- Recommended analytical approach for the Plan
- Any LOW-confidence items that need user input before planning

**User Response Handling:**
- **Approve** → Proceed to Stage 4 (Plan Creation)
- **Request more exploration** → Return to Stage 2 or 3 for additional discovery
- **Adjust scope** → Update research question/scope, re-confirm, then proceed to Stage 4
- **Ask questions** → Answer, then re-present approval request

---

# Phase 2: Planning

## Stage 4: Plan Creation

**Executor:** Orchestrator (invokes `data-planner` agent via `general-purpose` subagent)
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
   research/YYYY-MM-DD_[Title]/
   ├── data/
   │   ├── raw/
   │   └── processed/
   └── output/
       ├── analysis/
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

6. **Phase Status Update (PSU2)**
   After plan-checker completes (Stage 4.5), present PSU2 to user.
   See "Phase Status Update 2 (PSU2)" section for full requirements.
   **MUST wait for explicit user confirmation before proceeding to Stage 5.**

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

### Gate Criteria (G4)

- [ ] Plan document created at `research/[folder]/YYYY-MM-DD_[Title]_Plan.md`
- [ ] **STATE.md created** at `research/[folder]/STATE.md` (MANDATORY — Gate G4)
- [ ] **LEARNINGS.md skeleton created** at `research/[folder]/LEARNINGS.md` (MANDATORY — Gate G4)
- [ ] **Plan Completeness Gate passed** (all sections verified)
- [ ] Project folder structure created (`data/raw/`, `data/processed/`, `output/analysis/`, `output/figures/`)
- [ ] User notified (PSU2 presented after Stage 4.5 completes)

**Gate G4 Enforcement:** Plan-checker (Stage 4.5) CANNOT be invoked without Plan, STATE.md, and LEARNINGS.md all existing. (Stage 5 additionally requires G4.5 — see below.)

### Continuation Handling (Complex Plans)

The data-planner writes the Plan incrementally in four section groups (A through D), saving to disk after each group. If the planner's context is exhausted mid-generation or it returns `CONTINUATION`:

1. **Detect:** Orchestrator receives `CONTINUATION` status (or subagent crash with no return). Check the Plan file on disk for a progress marker: `<!-- PLAN_PROGRESS: NEXT_GROUP=X ... -->`
2. **Assess:** The marker indicates which group is needed next. If no marker is present and the file exists, check whether all expected sections are populated.
3. **Resume:** Invoke a fresh data-planner in continuation mode (see `03_SKILL_INVOCATIONS.md` continuation template). The fresh planner reads the partial Plan to recover all context — discovery findings are already embedded in the Plan's Group B sections, so they do NOT need to be re-provided.
4. **Cap:** Maximum 3 total planner invocations (initial + 2 continuations). If the Plan is still incomplete after 3 passes, STOP and escalate to user.

**Key principle:** The partial Plan on disk IS the handoff context. Each continuation planner reads it rather than requiring the orchestrator to re-supply discovery findings.

---

## Stage 4.5: Plan Validation (Required)

**Executor:** Subagent (Plan)
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
| **Testability** | Research Outcomes are measurable investigation objectives, validation criteria specific |
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
Validate the Plan across all 6 dimensions. Return PASSED, PASSED_WITH_WARNINGS, or ISSUES_FOUND status.

**OUTPUT FORMAT:**
1. Dimension Scores (PASS/WARN/FAIL for each)
2. Issues Found (with severity and location)
3. Recommended Fixes (if ISSUES_FOUND)
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
├─ PASSED → Present PSU2, await user confirmation, then proceed to Stage 5
├─ PASSED_WITH_WARNINGS → Document warnings, present PSU2, await user confirmation, then proceed to Stage 5
└─ ISSUES_FOUND → Return to data-planner for revision
                ↓
            data-planner revises Plan
                ↓
            Re-run plan-checker (max 2 iterations)
                ↓
            If still ISSUES_FOUND after 2 attempts → STOP and escalate to user
```

### Gate Criteria (G4.5)

- [ ] Plan validation completed
- [ ] Status is PASSED or PASSED_WITH_WARNINGS
- [ ] If PASSED_WITH_WARNINGS: warnings documented in Plan
- [ ] **PSU2 presented to user with Plan summary, exact Plan filepath for their deeper inspection of the full file, and validation results**
- [ ] **User confirmed PSU2 (explicit approval of Plan)**

---

### Phase Status Update 2 (PSU2): Plan Ready for Approval

**Trigger:** Gate G4.5 satisfied (plan-checker PASSED or PASSED_WITH_WARNINGS)
**Blocking:** YES — Stage 5 CANNOT begin until user confirms PSU2

**Actions:**
1. Compile Plan summary and plan-checker results
2. Present PSU2 to user using the PSU template
3. Share the exact Plan filepath and indicate to the user that they should read it closely at this time
4. WAIT for explicit user confirmation

**PSU2 Content Requirements:**
- Research question as stated in the Plan
- Methodology summary: statistical approach, key analytical decisions
- Data sources confirmed: endpoints, year ranges, geographic scope
- Transformation sequence overview: number of tasks, wave structure, key joins
- Research Outcomes the analysis will investigate
- Risk Register highlights: top risks and mitigation strategies
- Plan-checker result: PASSED or PASSED_WITH_WARNINGS (include any warnings verbatim)
- Estimated scope: approximate record counts, number of scripts
- User informed of full Plan filepath and instructed to read it closely for their deep review

**User Response Handling:**
- **Approve** → Proceed to Stage 5 (Data Retrieval)
- **Request Plan changes** → Invoke data-planner for revision, re-run plan-checker, then re-present PSU2
- **Adjust scope/methodology** → Revise Plan accordingly, re-validate, re-present PSU2
- **Ask questions** → Answer, then re-present approval request

---

# Phase 3: Data Acquisition & Preparation

## Stage 5: Data Retrieval

**Executor:** Subagent (general-purpose)
**Skill:** Domain query skill (e.g., `education-data-query`)
**Purpose:** Fetch data from configured data mirrors

**Note:** Uses `general-purpose` subagent type (not `Plan`) because it must save data files to `data/raw/`.

### Actions

1. **Construct Query**
   - Build data access URL from Plan specification
   - Construct necessary sample filters (year, subgroups, etc.)

2. **Execute Query**
   - Implement timeout handling for mirror downloads
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
- Download complete file from mirror
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

### Scripts Saved (one per fetch task):
- Path: `scripts/stage5_fetch/{step}_{task-name}.py`
- Includes: Pagination handling, CP1 validation, output paths
- Note: Each fetch task produces a separate script; QA is invoked immediately after each
```

### Gate Criteria (G5)

- [ ] Data retrieved successfully
- [ ] CP1 passed (or warnings documented)
- [ ] Data saved to `data/raw/`
- [ ] **All scripts saved to `scripts/stage5_fetch/`** (one per fetch task) with standard header
- [ ] **If data lag ≥3 years:** User notified and decision documented
- [ ] Plan updated with Data Freshness Check table
- [ ] **QA review completed for EACH Stage 5 script** (code-reviewer separately invoked immediately after each individual script, not batched)
- [ ] **All QA1 statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage5_{step}_cr1.py`** (+ cr2..cr5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 5, CP1 status, raw data paths recorded

---

## Stage 6: Context Application

**Executor:** Subagent (general-purpose)
**Skill:** Domain context skill (e.g., `education-data-context`)
**Purpose:** Apply source-specific cleaning and context

**Note:** Uses `general-purpose` subagent type (not `Plan`) because it must save cleaned data files to `data/processed/`.

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
- BLOCK if any governance rules from Plan Domain Configuration are violated (e.g., cross-state assessment comparison for education)
- BLOCK if suppression rate >50%
- Generate proper citation text
```

### Validation (CP2)

```python
# Required checks
suppression_rate = (raw_df['key_var'] == SUPPRESSION_CODE).sum() / len(raw_df)  # SUPPRESSION_CODE from Plan Domain Configuration
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

### Scripts Saved (one per clean task):
- Path: `scripts/stage6_clean/{step}_{task-name}.py`
- Includes: Coded value filtering, suppression calculation, CP2 validation
- Note: Each clean task produces a separate script; QA is invoked immediately after each
```

### Gate Criteria (G6)

- [ ] Coded values handled
- [ ] CP2 passed
- [ ] Citation generated
- [ ] Data saved to `data/processed/`
- [ ] **All scripts saved to `scripts/stage6_clean/`** (one per clean task) with standard header
- [ ] **QA review completed for EACH Stage 6 script** (code-reviewer separately invoked immediately after each individual script, not batched)
- [ ] **All QA2 statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage6_{step}_cr1.py`** (+ cr2..cr5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 6, CP2 status, suppression rate, processed data paths
- [ ] **PSU3 presented to user with data quality summary**
- [ ] **User confirmed PSU3**

---

### Phase Status Update 3 (PSU3): Data Acquired and Cleaned

**Trigger:** Gate G6 satisfied (all Stage 5-6 scripts executed and QA'd)
**Blocking:** YES — Stage 7 CANNOT begin until user confirms PSU3

**Actions:**
1. Compile data acquisition and cleaning summary from Stages 5-6
2. Include QA results from all QA1 and QA2 reviews
3. Present PSU3 to user using the PSU template
4. WAIT for explicit user confirmation

**PSU3 Content Requirements:**
- Datasets acquired: source name, shape (rows x columns), date range, file path
- Data freshness: most recent year available per source
- Data quality per dataset: missingness rates for critical columns, suppression rates
- Cleaning actions taken: rows removed (with counts and percentages), values recoded, filters applied
- QA summary table: each script's QA status (PASSED/WARNING) with details for any WARNINGs
- Any deviations from the Plan during fetch or clean (documented per RULE 1-3)
- If data lag >= 3 years: explicit flag for user awareness
- If flag years (per FLAG_YEARS in Plan Domain Configuration) are included: explicit flag with documented warning
- Data readiness assessment: are the cleaned datasets ready for analysis?

**User Response Handling:**
- **Approve** → Proceed to Stage 7 (EDA & Transformation)
- **Request re-fetch** → Return to Stage 5 for specific datasets
- **Request different cleaning approach** → Return to Stage 6 with revised parameters
- **Flag concern about data quality** → Orchestrator investigates and reports back
- **Ask questions** → Answer, then re-present approval request

---

# Phase 4: Analysis & Notebook Development

## Stage 7: EDA & Transformation

**Executor:** Subagent (general-purpose) - ITERATIVE INVOCATION REQUIRED
**Skills:** `data-scientist`, `polars`
**Purpose:** Explore data and create analysis dataset through step-by-step validated transformations

**CRITICAL:** This stage is executed in MULTIPLE subagent calls, NOT a single invocation. Follow the Iteration Protocol.

### Execution Pattern

**Stage 7 is split into 3 sub-stages:**

#### Stage 7.1: Initial EDA (No Transformations)

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

#### Stage 7.2: Execute Transformations (Iteratively)

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

All transformations are executed through script files, NOT interactive notebooks. See `agent_reference/SCRIPT_TEMPLATE.md` for the script format. Closely read `agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

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
# bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage7_transform/01_join-data.py
```

**If validation fails:** Create a new versioned script (`01_join-data_a.py`) with fixes. Do NOT modify the original—it serves as audit trail.

#### Stage 7.3: Final CP3 Validation

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

### Output (Across All Stages)

- **7.1:** EDA summary with data profile
- **7.2:** Validated transformation at each step, intermediate datasets
- **7.3:** Analysis-ready dataset, transformation log, CP3 validation report

### Gate Criteria

**After Stage 7.1 (Gate to 7.2):**
- [ ] Data profiled
- [ ] No blocking data quality issues
- [ ] Ready to proceed to transformations

**After Each Transformation in Stage 7.2 (Gate per transform):**
- [ ] Pre-state captured
- [ ] Transformation executed
- [ ] Validation performed
- [ ] Status reported (PASS/FAIL)
- [ ] **Script saved to `scripts/stage7_transform/`** with standard header
- [ ] **QA review completed IMMEDIATELY AFTER THIS SCRIPT, before the next script begins** (code-reviewer separately invoked per script, not batched)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage7_{step}_cr1.py`** (+ cr2..cr5 if warranted)

**After Stage 7.3 (G7):**
- [ ] All transformations complete
- [ ] CP3 validation passed for all transformations
- [ ] **All QA reviews passed** for all transformation scripts
- [ ] Analysis dataset ready at `data/processed/[date]_analysis.parquet`
- [ ] Transformation log complete
- [ ] **All transformation scripts archived in `scripts/stage7_transform/`**
- [ ] **All QA scripts archived in `scripts/cr/`**
- [ ] **STATE.md updated:** Current Stage: 7, all CP3 statuses, Transformation Progress table current

---

## Stage 8: Analysis & Visualization

**Executor:** Subagent (general-purpose) — ITERATIVE INVOCATION REQUIRED
**Skills:** `data-scientist`, `polars` (Stage 8.1), `plotnine`, `plotly` (Stage 8.2)
**Purpose:** Conduct final statistical analyses on the analysis dataset AND generate visualizations specified in Plan

### Execution Pattern

**Stage 8 is split into 2 sub-stages, executed sequentially:**

```
Stage 8.1.x: Statistical Analysis (one script per analysis task)
    ↓  QA4a after each script
Stage 8.2.x: Visualization (one script per visualization task)
    ↓  QA4b after each script
```

#### Stage 8.1: Statistical Analysis

**Purpose:** Run statistical analyses specified in the Plan (regressions, correlations, group comparisons, effect sizes, etc.)

**Input:** Analysis dataset from Stage 7 (`data/processed/[date]_analysis.parquet`)
**Output:** Statistical results saved as parquet to `output/analysis/`

**Actions:**
1. **Load analysis dataset** — Verify schema matches Plan expectations
2. **Execute analysis tasks** — One script per analysis task from Plan's Transformation Sequence
3. **Validate assumptions** — Check statistical assumptions before applying methods
4. **Save results** — Parquet format to `output/analysis/`
5. **>>> INVOKE code-reviewer (MANDATORY, QA4a) <<<**
   - After EACH analysis script, orchestrator MUST invoke code-reviewer
   - QA4a validates: statistical methodology, assumption checks, result plausibility
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to next analysis task or Stage 8.2

#### Stage 8.2: Visualization

**Purpose:** Create visualizations specified in Plan, informed by Stage 8.1 results

**Input:** Analysis dataset from Stage 7 + statistical results from Stage 8.1
**Output:** Figures saved to `output/figures/`

**Actions:**
1. **Create exploratory plots** — Distributions, relationships, patterns
2. **Create final visualizations** — As specified in Plan, striving for publication-quality
3. **Export figures** — PNG format, appropriate dimensions, to `output/figures/`
4. **>>> INVOKE code-reviewer (MANDATORY, QA4b) <<<**
   - After EACH visualization script, orchestrator MUST invoke code-reviewer
   - QA4b validates: figure existence, data source accuracy, labeling, visual clarity
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to next visualization task or Stage 9

### Analysis Principles

```
- Validate statistical assumptions BEFORE applying methods (normality, homoscedasticity, etc.)
- Document all methodology decisions with rationale in script comments (IAT)
- Perform robustness checks where appropriate (sensitivity analysis, alternative specifications)
- Report effect sizes alongside statistical significance
- Save all intermediate and final results as parquet (never just print to log)
- Follow the Iteration Protocol: one analysis per script, validate before proceeding
```

### Visualization Principles

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

### Context Requirements

**Stage 8.1 (Analysis) — Orchestrator must provide:**

| Context Item | Source | Required In Prompt |
|--------------|--------|-------------------|
| Analysis dataset path | Stage 7 output | YES — exact path |
| Research question | Plan | YES — verbatim |
| Analysis specification | Plan (Analysis Requirements) | YES — methods, variables, hypotheses |
| Research Outcome contribution | Plan | YES — which outcomes this analysis addresses |
| Statistical assumptions to check | Plan / data-scientist skill | YES — method-specific |
| Risk Register items | Plan | YES — relevant risks |

**Stage 8.2 (Visualization) — Orchestrator must provide:**

| Context Item | Source | Required In Prompt |
|--------------|--------|-------------------|
| Analysis dataset path | Stage 7 output | YES — exact path |
| Statistical results path(s) | Stage 8.1 output | YES — exact paths from `output/analysis/` |
| Visualization specification | Plan (Visualization Requirements) | YES — plot types, variables, dimensions |
| Key findings from 8.1 | Stage 8.1 results | YES — what to highlight in visualizations |
| Figure naming convention | Plan | YES — date prefix + descriptive name |

### QA Context (code-reviewer invocations)

| Context Item | QA4a (Analysis) | QA4b (Visualization) |
|--------------|-----------------|---------------------|
| Script path | YES | YES |
| Plan expectations | YES — statistical methods, expected directions | YES — figure specs, labeling requirements |
| QA tolerance thresholds | YES — methodology validity, assumption violations | YES — figure existence, data accuracy |
| Prior QA findings | YES — accumulated from 8.1 scripts | YES — accumulated from 8.1 + 8.2 scripts |
| Research Outcome contribution | YES | YES |

### Output

- **Stage 8.1:** Statistical result files in `output/analysis/` (parquet), analysis summaries
- **Stage 8.2:** Exported figure files in `output/figures/`, figure descriptions for report

### Completion Checklist

- [ ] All planned statistical analyses executed (Stage 8.1)
- [ ] Statistical results saved to `output/analysis/`
- [ ] All planned visualizations created (Stage 8.2)
- [ ] Figures exported to `output/figures/`
- [ ] All analysis scripts saved to `scripts/stage8_analysis/` with standard header
- [ ] All visualization scripts saved to `scripts/stage8_analysis/` with standard header
- [ ] QA4a completed for EACH analysis script individually (PASSED/WARNING), invoked immediately after each script
- [ ] QA4b completed for EACH visualization script individually (PASSED/WARNING), invoked immediately after each script

### Gate Criteria (G8)

- [ ] All planned analyses and visualizations created
- [ ] Statistical results exported to `output/analysis/`
- [ ] Figures exported to `output/figures/`
- [ ] **All scripts saved to `scripts/stage8_analysis/`** with standard header
- [ ] **QA4a review completed for EACH analysis script** (code-reviewer separately invoked IMMEDIATELY AFTER each individual script, before the next script begins — not batched)
- [ ] **All QA4a statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA4b review completed for EACH visualization script** (code-reviewer separately invoked IMMEDIATELY AFTER each individual script, before the next script begins — not batched)
- [ ] **All QA4b statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage8_{step}_cra1.py`** (analysis) and **`stage8_{step}_crb1.py`** (viz)
- [ ] **STATE.md updated:** Current Stage: 8, QA4a and QA4b status, analysis result paths, figure paths recorded

---

## Stage 9: Script Compilation (NOT Dashboard Building)

**Agent:** `notebook-assembler` (see `agents/notebook-assembler.md`)
**Executor:** Subagent (general-purpose)
**Skill:** `marimo` (for basic syntax only; agent provides behavioral constraints)
**Purpose:** LITERALLY COPY script file contents into marimo cells

> **CRITICAL:** Stage 9 is a FILE COMPILATION task. See `agents/notebook-assembler.md`
> for the complete protocol including the Four-Cell Pattern, helper functions, and
> WRONG vs. RIGHT examples.

### Key Constraints (Summary)

- **LITERAL COPY** — Read each script file and copy contents verbatim into cells
- NO new analysis code — only `pl.read_parquet()` + `mo.ui.table()` for data inspection
- NO dashboards, widgets, dropdowns, sliders
- All script code presented as-is; execution logs in accordions
- Script versioning: use final successful version (`_b.py` > `_a.py` > base)

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

### Gate Criteria (G9)

- [ ] All final script versions identified
- [ ] Each script represented with: header, code, execution log, data preview
- [ ] Navigation cells link to all sections
- [ ] Notebook executes without errors
- [ ] Interactive elements (tables, accordions) work
- [ ] Data flows correctly between cells

---

## Stage 10: QA Aggregation

**Executor:** Orchestrator (no subagent — performed directly by orchestrator)
**Skills:** —
**Purpose:** Aggregation point for all QA findings from Stages 5-8

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
   | 8 (QA4a) | 1    | 1          | 0              | N/A               |
   | 8 (QA4b) | 1    | 1          | 0              | N/A               |

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

3. **Review WARNING Patterns**
   - Identify systemic issues across multiple scripts
   - Assess cumulative impact of individual WARNINGs
   - Flag any WARNING clusters that together constitute a concern

### Gate Criteria (G10)

- [ ] **QA Summary Report generated** (aggregates all Stages 5-8 findings)
- [ ] **All BLOCKERs resolved** (via revision during Stages 5-8)
- [ ] **All WARNINGs documented** (with assessment of impact)
- [ ] **No missing QA reviews** (every Stage 5-8 script has a corresponding code-reviewer invocation)
- [ ] **If unresolved issues found:** STOP, escalate
- [ ] **PSU4 presented to user with analysis results and QA summary**
- [ ] **User confirmed PSU4**

---

### Phase Status Update 4 (PSU4): Analysis Complete

**Trigger:** Gate G10 satisfied (QA aggregation complete, BLOCKERs resolved)
**Blocking:** YES — Stage 11 CANNOT begin until user confirms PSU4

**Actions:**
1. Compile analysis summary from Stages 7-8 and QA aggregation from Stage 10
2. Reference key visualizations by file path for user inspection
3. Present PSU4 to user using the PSU template
4. WAIT for explicit user confirmation

**PSU4 Content Requirements:**
- Transformation summary: joins performed, derived variables created, final analysis dataset shape
- EDA highlights: key distributions, notable patterns, surprising findings
- Statistical analysis results: key findings with effect sizes and confidence intervals where applicable
- Visualization inventory: file paths to all generated figures (so user can inspect them)
- QA aggregation summary: all accumulated WARNINGs from Stages 5-8, with resolution status
- Any deviations from Plan methodology (with rationale)
- Notebook compilation status (Stage 9): runs successfully, all scripts represented
- Research Outcomes progress: which can be evaluated, preliminary assessment

**User Response Handling:**
- **Approve** → Proceed to Stage 11 (Report Generation)
- **Request additional analysis** → Return to Stage 8 for supplementary work
- **Request re-transformation** → Return to Stage 7 with revised approach
- **Flag concern about findings** → Orchestrator investigates and reports back
- **Ask questions** → Answer, then re-present approval request

---

# Phase 5: Synthesis & Delivery

## Stage 11: Report Generation

**Executor:** report-writer agent (`general-purpose`)
**Purpose:** Synthesize all pipeline artifacts into a stakeholder-appropriate report

### Upstream Inputs

| Input | Source | Purpose |
|-------|--------|---------|
| Plan.md | Stage 4 | Research question, methodology, research outcomes, risk register |
| Marimo notebook (.py) | Stage 9 | Complete technical record: all scripts + execution logs |
| STATE.md | Maintained throughout | Checkpoint statuses, key decisions, blockers |
| LEARNINGS.md | Maintained throughout | Data quality insights, methodology lessons |
| Stage 10 QA summary | Stage 10 | Aggregated QA findings (WARNINGs, resolved BLOCKERs) |
| Statistical results | Stage 8.1 (`output/analysis/`) | Analysis findings for Key Findings and interpretation |
| Figure files | Stage 8.2 (`output/figures/`) | Visualizations to embed in Key Findings |
| Citation text | Stage 6 (education-data-context) | Pre-formatted data source citations |
| Analysis dataset metadata | Stage 7 | Final dataset shape, column list, key statistics |

### Section-Source Mapping

The report-writer follows a systematic mapping from REPORT_TEMPLATE.md sections to pipeline artifacts:

| Report Section | Primary Source | Secondary Sources |
|---|---|---|
| Executive Summary | Plan Research Outcomes + notebook execution logs | LEARNINGS.md |
| Research Question | Plan (verbatim) | — |
| Data & Methods | Plan Methodology + Stage 5-6 execution logs | STATE.md checkpoints |
| Quality Assurance | Stage 10 QA summary | STATE.md QA sections |
| Key Findings | Stage 7 transforms + Stage 8.1 analysis results + Stage 8.2 figures | Plan Research Outcomes |
| Limitations | Plan Risk Register + source caveats + suppression rates + LEARNINGS.md | STATE.md blockers |
| Citations | Stage 6 citation text | Plan Data Sources table |

### Actions

1. **Read upstream artifacts** — Plan, Notebook, STATE.md, LEARNINGS.md
2. **Verify figures** — Confirm all figure files exist before referencing
3. **Draft report** — Follow REPORT_TEMPLATE.md section by section using Section-Source Mapping
4. **Cross-check Research Outcomes** — Every Research Outcome addressed in Key Findings
5. **Write Report.md** — Save to project folder with date prefix

### Gate Criteria (G11)

- [ ] report-writer returned COMPLETE or COMPLETE_WITH_GAPS
- [ ] All REPORT_TEMPLATE.md sections populated (not placeholder text)
- [ ] All figure references resolve to existing files
- [ ] All Research Outcomes from Plan addressed in Key Findings
- [ ] Executive Summary is 4-5 sentences
- [ ] All statistics trace to execution logs or dataset metadata
- [ ] Citation text included verbatim

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

### Gate Criteria (G12)

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
