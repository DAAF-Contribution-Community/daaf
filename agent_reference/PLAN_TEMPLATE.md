---
# Plan Frontmatter
# This YAML block contains machine-readable metadata for orchestration

title: "[Analysis Title]"
date: "YYYY-MM-DD"
version: ""                           # Empty for original, "a", "b", etc. for revisions
status: "planning"                    # planning | in_progress | complete

# Goal-Backward Verification Criteria
must_haves:
  truths:
    - "[Observable behavior 1 - user perspective]"
    - "[Observable behavior 2 - testable outcome]"
    - "[Observable behavior 3 - measurable result]"

  artifacts:
    - path: "research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title].py"
      provides: "[What this file delivers]"
      min_lines: 200
      contains: "[Pattern or text that must be present]"

    - path: "research/YYYY-MM-DD [Title]/data/processed/YYYY-MM-DD_analysis.parquet"
      provides: "[What this file delivers]"
      has_columns: ["col1", "col2", "col3"]

    - path: "research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title] Report.md"
      provides: "[What this file delivers]"
      contains: ["## Section 1", "## Section 2"]

  key_links:
    - from: "[source file]"
      to: "[target file or resource]"
      via: "[connection mechanism]"
      pattern: "[regex pattern to verify connection]"

# Execution metadata (populated during execution)
execution:
  current_stage: 1
  checkpoints_passed: []
  blockers: []
---

# [Analysis Title]

## Philosophy: Plans are Prompts

**This document is not just documentation — it is an executable specification.**

Every task in the "Executable Task Sequence" section is written as a prompt that will be dispatched directly to a subagent. The task IS the instruction.

**Key Principles:**

1. **Task actions must be specific enough to execute without clarification.**
   - Invalid: "Process the data appropriately"
   - Valid: "Filter rows where enrollment == -1, save to data/processed/2026-01-31_ccd_clean.parquet"

2. **File paths must be explicit (no placeholders in the final plan).**
   - Invalid: `data/raw/[filename].parquet`
   - Valid: `data/raw/2026-01-31_ccd_schools.parquet`

3. **Verification must be executable (not subjective).**
   - Invalid: "Data looks correct"
   - Valid: "Row count > 0 AND row count < 200000"

4. **Done criteria must be measurable.**
   - Invalid: "Task complete"
   - Valid: "CP1 PASSED, files saved to data/raw/"

**The Test:** If you copy-paste a task XML into a fresh conversation with Claude + the relevant skill, can Claude execute it without asking questions?

---

## Version Information

*Include this section for all revisions. Omit for original deliveries.*

**Version:** [a | b | c | ...]
**Based On:** `YYYY-MM-DD[prior-suffix] [Title] Plan.md` (same folder)
**Prior Versions:**
- `YYYY-MM-DD[x] [Title] Plan.md` — [revision type, brief note]
- `YYYY-MM-DD [Title] Plan.md` — Original delivery

**Revision Trigger:**
> [Verbatim user request that triggered this revision]

**Revision Type:** [Documentation Re-research | Logic Correction | Output Adjustment | Minor Fix | Scope Expansion]

**Summary of Changes:**
- [Key change 1]
- [Key change 2]

**Data Regeneration Note:** Data regenerated fresh for this revision (not copied from prior version).

---

## Original Request & Clarifications

### Original Request

> [Paste the verbatim user request here]

### Clarifications Received

1. **[Topic]:** [User's response]
2. **[Topic]:** [User's response]

### Research Question

[Your interpretation of the request as a clear, answerable research question]

---

## Goal & Context

### Analysis Goal

[Clear statement of the analysis objective — what will be produced and why it matters]

### Background Context

[Business/policy context that informs the analysis approach]

### Success Criteria

- [ ] [Measurable outcome 1]
- [ ] [Measurable outcome 2]
- [ ] [Measurable outcome 3]

---

## Must-Haves (Goal-Backward Verification)

**Purpose:** This section defines what MUST be true for the analysis to be considered complete. Derived using goal-backward methodology — working from the desired outcome to identify observable truths, required artifacts, and critical connections.

### Deriving Must-Haves

**Goal-backward planning asks:** "What must be TRUE for the goal to be achieved?" rather than "What should we build?"

**Step 1: State the Goal (Outcome, Not Task)**
- Good: "Analysis shows enrollment trends by poverty level" (outcome)
- Bad: "Create enrollment visualization" (task)

**Step 2: Derive Observable Truths (User Perspective)**
Ask: "What must be TRUE for this goal to be achieved?"
List 3-7 truths that are verifiable by examining the outputs.

**Step 3: Derive Required Artifacts**
For each truth, ask: "What must EXIST for this to be true?"
Identify specific files with expected content.

**Step 4: Identify Key Links (Critical Connections)**
Ask: "Where is this most likely to break?"
Key links are connections that, if missing, cause cascading failures.

### Must-Haves Specification

```yaml
must_haves:
  truths:
    - "Analysis shows enrollment trends by year"
    - "Poverty rates are calculated at the school level"
    - "Suppression rates are documented with impact assessment"
    - "Data limitations are explicitly stated in the report"
    - "Visualizations include confidence intervals where applicable"

  artifacts:
    - path: "research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title].py"
      provides: "Interactive analysis notebook"
      min_lines: 200
      contains: "mo.md"  # Marimo markdown cells present

    - path: "research/YYYY-MM-DD [Title]/data/processed/YYYY-MM-DD_analysis.parquet"
      provides: "Cleaned analysis dataset"
      has_columns: ["ncessch", "year", "enrollment", "frl_rate"]

    - path: "research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title] Report.md"
      provides: "Stakeholder report with findings"
      contains: ["## Executive Summary", "## Limitations", "## Data Sources"]

    - path: "research/YYYY-MM-DD [Title]/output/figures/YYYY-MM-DD_enrollment_trends.png"
      provides: "Trend visualization"
      min_size_kb: 50

  key_links:
    - from: "YYYY-MM-DD [Title].py"
      to: "data/processed/YYYY-MM-DD_analysis.parquet"
      via: "pl.read_parquet() in data loading cell"
      pattern: "read_parquet.*analysis"

    - from: "YYYY-MM-DD [Title].py"
      to: "output/figures/"
      via: "ggplot.save() or fig.write_image()"
      pattern: "(ggsave|write_image|savefig)"

    - from: "YYYY-MM-DD [Title] Report.md"
      to: "output/figures/"
      via: "Markdown image references"
      pattern: "!\\[.*\\]\\(.*figures/"

    - from: "data/processed/*"
      to: "data/raw/*"
      via: "Cleaning transformations in notebook"
      pattern: "filter.*-[123]"  # Coded value filtering
```

### Common Must-Have Failures

| Failure Type | Bad Example | Good Example |
|--------------|-------------|--------------|
| **Truths too vague** | "Analysis is complete" | "Enrollment trends show year-over-year change with statistical significance" |
| **Truths not testable** | "Data is clean" | "No coded values (-1, -2, -3) remain in analysis columns" |
| **Artifacts too abstract** | "Analysis files" | "research/2026-01-31 School Poverty/2026-01-31 School Poverty.py" |
| **Artifacts missing content spec** | path only | path + provides + contains/has_columns |
| **Missing wiring** | Listing files without connections | "Notebook loads from data/processed/ via pl.read_parquet()" |
| **Key links too generic** | "Notebook uses data" | "Cell 3 loads YYYY-MM-DD_analysis.parquet with enrollment, frl columns" |

### Must-Haves Verification Checklist

*Use during Stage 12 (Final Review) to verify all must-haves are satisfied:*

**Truths Verification:**
- [ ] Each truth can be observed by examining outputs
- [ ] No truth requires subjective judgment
- [ ] Truths cover the core research question

**Artifacts Verification:**
- [ ] All artifact paths exist
- [ ] Content specifications are satisfied (contains, has_columns, min_lines)
- [ ] File sizes are reasonable (not empty, not stub)

**Key Links Verification:**
- [ ] Each key link pattern can be found in source file
- [ ] Links form complete data flow (raw → processed → analysis → output)
- [ ] No orphaned artifacts (files that nothing references)

---

## Prior Learnings Consulted

*Document which prior learnings were checked and what relevant insights were found.*

### Repository-Level Learnings

**Source:** `agent_reference/EDUCATION_DATA_API_LEARNINGS.md`
**Checked:** [ ] Yes / No

**Relevant Insights Applied:**
- [Insight 1 from API learnings that affects this analysis]
- [Insight 2]
- *None applicable* (if nothing relevant)

### Project-Level Learnings

**Prior Projects Searched:** [list of LEARNINGS.md files checked, or "N/A - fewer than 3 prior analyses"]

| Project | Relevant Finding | Applied How |
|---------|------------------|-------------|
| `research/YYYY-MM-DD [Title]/LEARNINGS.md` | [Finding] | [How it informed this Plan] |
| — | — | — |

**Note:** Project-level learnings search is recommended when ≥3 prior analyses exist. See `08_LESSONS_LEARNED.md: Consuming Prior Learnings`.

---

## Phase 1: Discovery Results

### Stage 2: Data Exploration

*Output from `education-data-explorer` skill*

**Data Level:** [schools | school-districts | college-university]

**Candidate Endpoints:**

| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|
| `/schools/ccd/directory/` | CCD | School directory info | 1986-2022 |
| [add more] | | | |

**Key Variables Identified:**

| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|
| `enrollment` | `/schools/ccd/enrollment/` | integer | Total student enrollment |
| [add more] | | | |

**Variables Flagged for Deep-Dive:**

| Variable | Reason for Deep-Dive |
|----------|---------------------|
| [variable] | [reason: coded values, suppression, caveats] |

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| [What could not be found] | [Effect on analysis] | [How addressed] |

**Stage 2 Completeness Assessment:**
- [ ] All relevant data levels searched (schools, districts, colleges as appropriate)
- [ ] Multiple potential sources considered
- [ ] Year coverage verified for research question
- [ ] Variables requiring deep-dive explicitly flagged
- [ ] Limitations documented

---

### Stage 3: Source Deep-Dive

*Output from `education-data-source-*` skill(s)*

**Sources Investigated:**

| Source | Skill Used | Relevance |
|--------|------------|-----------|
| CCD | `education-data-source-ccd` | Primary data source |
| [add more] | | |

**Source-Specific Caveats:**

#### [Source Name] (e.g., CCD)

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| Public schools only | Cannot analyze private schools | Document limitation |
| [add more] | | |

**Coded Value Mappings:**

| Variable | Code | Meaning | Action |
|----------|------|---------|--------|
| `charter` | 1 | Charter school | Include in filter |
| `charter` | 2 | Not charter | Include in filter |
| [variable] | -1 | Missing/not reported | Exclude from calculations |
| [variable] | -2 | Not applicable | Exclude from analysis |
| [variable] | -3 | Suppressed | Document; cannot recover |

**Suppression Patterns:**

| Variable | Typical Suppression Rate | Threshold | Impact |
|----------|--------------------------|-----------|--------|
| [variable] | ~15% | <3 students | Affects small schools |

**Cross-State Comparability:**

| Analysis Type | Valid Across States? | Notes |
|---------------|---------------------|-------|
| Enrollment counts | Yes | Comparable definitions |
| Assessment scores | **NO** | Different state tests |
| Graduation rates | Conditional | ACGR comparable; other rates vary |

**Critical Warnings:**

1. **[Warning]:** [Description and required mitigation]
2. **[Warning]:** [Description and required mitigation]

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| [What could not be found] | [Effect on analysis] | [How addressed] |

**Stage 3 Completeness Assessment:**
- [ ] All flagged variables investigated
- [ ] Source-specific skill(s) loaded and consulted
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings documented with mitigations

---

### Phase 1 Overall Assessment

**Completeness Status:** [COMPLETE | GAPS IDENTIFIED]

**If GAPS IDENTIFIED:**

| Gap | Source | Resolution |
|-----|--------|------------|
| [Description] | Stage [N] | [How addressed or escalated] |

**Phase 1 Integration Checklist:**

*Complete before proceeding to Phase 2:*

- [ ] All candidate endpoints documented with year coverage
- [ ] All key variables documented with types and descriptions
- [ ] All source-specific caveats captured
- [ ] All coded value mappings complete
- [ ] Suppression patterns documented
- [ ] Cross-state comparability assessed (if applicable)
- [ ] Critical warnings have mitigation strategies
- [ ] All LOW confidence findings resolved or escalated

---

## Methodology Specification

### Data Acquisition Strategy

**Single Source or Multi-Source:** [Single | Multi-Source Join]

**If Multi-Source, Join Strategy:**

| Left Source | Right Source | Join Key(s) | Expected Cardinality | Risks |
|-------------|--------------|-------------|---------------------|-------|
| CCD schools | CRDC | `ncessch` | 1:1 | Some schools may not appear in both |

### Query Specification

**Query 1: [Description]**

| Field | Value |
|-------|-------|
| Dataset | CCD Schools Directory |
| Mirror Paths | Per-mirror path parameters from datasets-reference.md |
| File Type | Single-file (all years) / Yearly |
| Years | `2020, 2021, 2022` |
| Filters (local) | `fips=6` (California), `charter=1` |
| Variables | `ncessch, school_name, enrollment, frl` |
| Expected Records | ~10,000 |

**Query 2: [Description]** (if applicable)

[Repeat structure]

### Data Freshness Check

**IMPORTANT:** This section is populated during Stage 5 (CP1 validation). If significant lag is discovered, the orchestrator MUST update the user before proceeding.

| Source | Requested Years | Latest Available | Lag | Impact | User Notified? |
|--------|-----------------|------------------|-----|--------|----------------|
| CCD | 2020-2023 | 2023 | 0 years | ✅ Current | N/A |
| CRDC | 2020-2021 | 2021 | 1 year | ✅ Acceptable | N/A |
| [add row per source] | | | | | |

**Lag Assessment Guidelines:**
- **No lag (0 years):** Data is current ✅ — Proceed normally
- **Minor lag (1-2 years):** Acceptable for most analyses ✅ — Document in report
- **Significant lag (3+ years):** ⚠️ **MUST update user before proceeding**
  - Explain the lag and its implications
  - Offer options: proceed with caveat, adjust year range, wait for updated data
  - Document user decision in Decisions Log

**Orchestrator Protocol for Significant Lag:**
If CP1 Check 6 detects lag ≥3 years:
1. PAUSE execution after Stage 5
2. Update this table with lag details
3. Report to user:
   ```
   **Data Lag Detected**
   Requested: {max_year_requested}
   Latest available: {max_year_available}
   Lag: {lag_years} years
   
   Options:
   1. Proceed with {max_year_available} data (document limitation)
   2. Adjust analysis to {revised_year_range}
   3. Wait for {expected_release_date}
   
   How would you like to proceed?
   ```
4. Document decision in Decisions Log
5. Update analysis scope if years changed

**COVID-19 Data Quality Considerations:**
If analysis includes 2020 or 2021 data, CP1 Check 7 will flag this automatically. Document the following:

| Year | Data Quality Impact | Mitigation |
|------|-------------------|------------|
| 2020 | [Collection disruptions, missing data, non-representative samples] | [Exclude year, document caveat, compare to pre/post-COVID trends] |
| 2021 | [Recovery period, partial return to normal collection] | [Document caveat, note recovery status] |

**Note:** Data freshness verified during Stage 5 (CP1 Check 6). COVID impact flagged by CP1 Check 7. Both are updated before proceeding to Stage 6.

### Data Cleaning Specification

**Coded Value Handling:**

*For complete coded value definitions, see `agent_reference/REFERENCE_TABLES.md: Coded Missing Values`*

| Variable | Codes to Filter | Rationale |
|----------|-----------------|-----------|
| `enrollment` | -1, -2 | Missing/not applicable (standard Education Data Portal codes) |
| `frl` | -1, -2, -3 | Missing/not applicable/suppressed (standard codes) |

**Suppression Handling:**

- Expected suppression rate: [X]%
- Threshold for STOP condition: 50%
- If exceeded: [escalate to user | aggregate to higher level | document and proceed]

### Transformation Sequence

**IMPORTANT:** Execute transformations following the Wave-Based Execution Protocol. Tasks in the same wave can run in parallel with independent subagent contexts. Tasks in later waves must wait for all prior waves to complete.

#### Wave-Based Task Table

| Wave | Step | Task Name | Operation | Expected Outcome | Script Path | Cardinality | Depends On | Status |
|------|------|-----------|-----------|------------------|-------------|-------------|------------|--------|
| 1 | 1.1 | fetch-ccd | Fetch CCD schools data | ~100K rows | `scripts/stage5_fetch/01_fetch-ccd.py` | N/A | — | ⬜ Pending |
| 1 | 1.2 | fetch-meps | Fetch MEPS poverty data | ~100K rows | `scripts/stage5_fetch/02_fetch-meps.py` | N/A | — | ⬜ Pending |
| 2 | 2.1 | clean-ccd | Filter coded values | ~95K rows (5% loss) | `scripts/stage6_clean/01_clean-ccd.py` | N/A | 1.1 | ⬜ Pending |
| 2 | 2.2 | clean-meps | Filter coded values | ~98K rows (2% loss) | `scripts/stage6_clean/02_clean-meps.py` | N/A | 1.2 | ⬜ Pending |
| 3 | 3.1 | join-data | Join CCD + MEPS on ncessch | ~93K rows | `scripts/stage7_transform/01_join-data.py` | 1:1 | 2.1, 2.2 | ⬜ Pending |
| 4 | 4.1 | filter-state | Filter to FIPS == 6 (CA) | ~9K rows (10% retained) | `scripts/stage7_transform/02_filter-state.py` | N/A | 3.1 | ⬜ Pending |
| 4 | 4.2 | calc-ratio | Calculate student-teacher ratio | Add 1 column | `scripts/stage7_transform/03_calc-ratio.py` | N/A | 3.1 | ⬜ Pending |
| 5 | 5.1 | aggregate | Aggregate by district | ~1K rows | `scripts/stage7_transform/04_aggregate.py` | N/A | 4.1, 4.2 | ⬜ Pending |

**Script Path Convention:**
- Pattern: `scripts/stage{N}_{type}/{step:02d}_{task-name}.py`
- Stage 5 (fetch) → `scripts/stage5_fetch/`
- Stage 6 (clean) → `scripts/stage6_clean/`
- Stage 7 (transform) → `scripts/stage7_transform/`
- Stage 8 (viz) → `scripts/stage8_viz/`

#### Wave Execution Rules

**Parallelization:**
- Same-wave tasks (e.g., 1.1 and 1.2) can run in parallel
- Each parallel task gets a fresh subagent context (200K tokens)
- Independent execution prevents context degradation

**Dependencies:**
- Later-wave tasks wait for ALL prior waves to complete
- `Depends On` column shows explicit task dependencies
- Dependencies MUST be satisfied before task can start

**Context Freshness:**
- Each wave starts with fresh subagent contexts
- Plan document provides continuity across waves
- No accumulated context degradation

#### Cardinality Reference

| Value | Meaning | Expected Row Change |
|-------|---------|-------------------|
| **N/A** | Not a join operation | Per operation logic |
| **1:1** | One-to-one match | Result ≈ left rows |
| **1:many** | One matches many | Result ≥ left rows (fan-out) |
| **many:1** | Many match one | Result ≈ left rows |
| **many:many** | Complex matching | Validate carefully |

**Validation Linkage:**
The cardinality specified here is passed to `validate_join()` function during Stage 7 execution. See `05_VALIDATION_CHECKPOINTS.md: Join-Specific Validation` for the validation logic.

#### Execution Protocol

1. **Wave Start:** Identify all tasks in current wave
2. **Parallel Dispatch:** Create Task for each, run simultaneously
3. **Wave Completion:** Wait for ALL wave tasks to complete
4. **Validation:** Review each task's CP status
5. **Wave Advance:** If all PASSED, proceed to next wave
6. **Update Status:** ⬜ Pending → ⏳ In Progress → ✅ Passed → ❌ Failed

**If any task fails:**
- Attempt fix (max 2 tries)
- If still failing, STOP and escalate
- Do NOT proceed to next wave

#### Transformation Log

*Updated during execution — one row per completed task*

| Wave | Step | Task | Pre-Rows | Post-Rows | Change % | CP Status | QA Status | Revisions | Commit Hash | Notes |
|------|------|------|----------|-----------|----------|-----------|-----------|-----------|-------------|-------|
| 1 | 1.1 | fetch-ccd | — | — | — | — | — | 0 | — | — |
| 1 | 1.2 | fetch-meps | — | — | — | — | — | 0 | — | — |
| 2 | 2.1 | clean-ccd | — | — | — | — | — | 0 | — | — |
| 2 | 2.2 | clean-meps | — | — | — | — | — | 0 | — | — |
| 3 | 3.1 | join-data | — | — | — | — | — | 0 | — | — |
| 4 | 4.1 | filter-state | — | — | — | — | — | 0 | — | — |
| 4 | 4.2 | calc-ratio | — | — | — | — | — | 0 | — | — |
| 5 | 5.1 | aggregate | — | — | — | — | — | 0 | — | — |

**QA Status Values:**
- **PENDING** — QA review not yet executed
- **PASSED** — QA review passed (no issues or INFO only)
- **WARNING** — QA review found non-blocking issues (logged for Stage 10)
- **BLOCKER** → **REVISED** — QA found blocking issue, revision applied
- **ESCALATED** — QA BLOCKER unresolved after 2 revision attempts

**Revisions Column:** Count of script revisions due to QA BLOCKER findings (max 2 before escalation)

---

## Executable Task Sequence

**PURPOSE:** Each task below is a self-contained specification that can be dispatched to a subagent. Tasks pass the **Task Specificity Test**: a fresh Claude instance with only this task + skill access can complete it without clarifying questions.

**WAVE EXECUTION:** Tasks are grouped by wave. Same-wave tasks dispatch in parallel. Later waves wait for all prior waves.

### Wave 1: Data Acquisition (Parallel)

<task name="fetch-ccd-schools" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/YYYY-MM-DD_ccd_schools.parquet</output>
    <output>data/raw/YYYY-MM-DD_ccd_schools.csv</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (see skill's fetch-patterns.md):
       - Dataset Paths: {dataset_paths}  (from datasets-reference.md)
       - File type: {single | yearly}
    3. Apply local filters with Polars:
       - Years: pl.col("year").is_in([year list])
       - Filters: [filter parameters as Polars expressions]
    4. Save to parquet and CSV formats
    5. Run CP1 validation
  </action>
  <verify>
    - Row count: [min]-[max] expected
    - Required columns present: [list]
    - Years present: [list]
    - Null rate < 10% for critical fields
    - Mirror used logged in script output
  </verify>
  <done>CP1 PASSED, files saved to data/raw/</done>
</task>

<task name="fetch-meps-poverty" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/YYYY-MM-DD_meps_poverty.parquet</output>
    <output>data/raw/YYYY-MM-DD_meps_poverty.csv</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern for MEPS poverty data
    3. Apply local filters with Polars
    4. Save to parquet and CSV formats
    5. Run CP1 validation
  </action>
  <verify>
    - Row count: [expected]
    - Join key (ncessch) present
    - Years match CCD fetch
  </verify>
  <done>CP1 PASSED, files saved to data/raw/</done>
</task>

### Wave 2: Data Cleaning (Parallel, depends on Wave 1)

<task name="clean-ccd" type="auto" wave="2">
  <depends_on>fetch-ccd-schools</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/YYYY-MM-DD_ccd_schools.parquet</input>
    <output>data/processed/YYYY-MM-DD_ccd_clean.parquet</output>
    <output>data/processed/YYYY-MM-DD_ccd_clean.csv</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input file
    3. Filter coded values:
       - Remove rows where [variable] == -1 (missing)
       - Remove rows where [variable] == -2 (not applicable)
       - Remove rows where [variable] == -3 (suppressed)
    4. Calculate suppression rate for key variable
    5. Generate citation text
    6. Save to parquet and CSV formats
    7. Run CP2 validation
  </action>
  <verify>
    - Suppression rate < 50%
    - No coded values (-1, -2, -3) remain
    - Data loss < 90%
    - Citation text complete
  </verify>
  <done>CP2 PASSED, files saved to data/processed/</done>
</task>

### Wave 3: Transformation (depends on Wave 2)

<task name="join-ccd-meps" type="auto" wave="3">
  <depends_on>clean-ccd, clean-meps</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/YYYY-MM-DD_ccd_clean.parquet</input>
    <input>data/processed/YYYY-MM-DD_meps_clean.parquet</input>
    <output>data/processed/YYYY-MM-DD_analysis.parquet</output>
  </files>
  <action>
    1. Load both skills
    2. Load both input files
    3. Capture pre-state (row counts, key overlap)
    4. Perform inner join on ncessch
    5. Validate cardinality (1:1 expected)
    6. Check for fan-out or data loss
    7. Save result
    8. Run CP3 validation
  </action>
  <verify>
    - Join key overlap: > 90%
    - No fan-out (result rows ≤ left rows)
    - Data loss < 50%
    - No unexpected nulls in joined columns
  </verify>
  <done>CP3 PASSED (join validation), file saved</done>
</task>

### Task Specificity Test

**REQUIRED:** Before dispatching any task, verify it passes this test.

**The Fresh Claude Test:** Could a new Claude instance with ONLY this task description + skill access execute it without asking clarifying questions?

#### Specificity Checklist

- [ ] **Unambiguous Scope:** File paths are explicit (no `[placeholders]` in final plan)
- [ ] **Concrete Actions:** Each step is a specific operation, not "process data"
- [ ] **Verifiable Completion:** "done" condition can be programmatically checked
- [ ] **No Hidden Dependencies:** All prerequisites in `depends_on`
- [ ] **Skill Identified:** Which skill to load is explicit
- [ ] **Agent Identified:** Which agent protocol to follow
- [ ] **Wave Assigned:** Enables parallel execution scheduling

#### Quick Validation

Read each task aloud and ask:
1. **Can I execute without asking "what does X mean?"** → If no, add specificity
2. **Are all file paths real?** → Replace any `[bracket]` placeholders
3. **Is verification executable?** → Should be code-checkable, not subjective
4. **Is done measurable?** → Should be yes/no, not "looks good"

#### Examples: Specific vs Vague

| Aspect | Vague (FAIL) | Specific (PASS) |
|--------|--------------|-----------------|
| Action | "Clean the data" | "Filter rows where enrollment == -1 OR enrollment == -2" |
| File | `data/raw/[source].parquet` | `data/raw/2026-01-31_ccd_schools.parquet` |
| Verify | "Data looks correct" | "Row count: 90,000-100,000; Null rate < 5% for enrollment" |
| Done | "Cleaning complete" | "CP2 PASSED, suppression rate 12%, files saved to data/processed/" |

#### If Any Check Fails

1. Add specificity until all checks pass
2. If you can't make it specific, the task may need to be split
3. Consult the Plan's Methodology section for guidance
4. Ask orchestrator for clarification if blocked

### Stage 6 Tasks

<task name="clean-[description]">
files:
  - input: data/raw/YYYY-MM-DD_[source]_[description].parquet
  - output: data/processed/YYYY-MM-DD_[description]_clean.parquet
  - output: data/processed/YYYY-MM-DD_[description]_clean.csv
action: |
  1. Call education-data-context skill
  2. Load raw data from input file
  3. Filter coded values:
     - Remove rows where [variable] == -1 (missing)
     - Remove rows where [variable] == -2 (not applicable)
     - Remove rows where [variable] == -3 (suppressed)
  4. Calculate suppression rate for [key variable]
  5. Generate citation text
  6. Save to parquet and CSV formats
  7. Run CP2 validation
verify: |
  - Suppression rate < 50%
  - No coded values (-1, -2, -3) remain in analysis variables
  - Data loss < 90%
  - Citation text complete
done: CP2 validation PASSED, files saved to data/processed/
</task>

### Stage 7 Tasks

<task name="transform-[step-number]-[description]">
files:
  - input: [current data file]
  - output: [output data file, or same if in-place]
action: |
  1. Call data-scientist skill
  2. Load data from input file
  3. Capture pre-state: shape, sample of key columns
  4. Execute transformation:
     [Specific transformation description]
  5. Capture post-state: shape, sample of key columns
  6. Validate transformation:
     [Specific validation criteria]
  7. Save if output file differs from input
verify: |
  - Pre-state captured: [expected shape]
  - Post-state: [expected shape]
  - Row change: [expected percentage or relationship]
  - Invariants: [list of invariants to check]
  - No unexpected nulls introduced
done: Transformation validated, PASSED status reported
</task>

### Stage 8 Tasks

<task name="visualize-[description]">
files:
  - input: data/processed/YYYY-MM-DD_[description].parquet
  - output: output/figures/YYYY-MM-DD_[figure-name].png
action: |
  1. Call plotnine or plotly skill (specify which)
  2. Load analysis data
  3. Create visualization:
     - Type: [chart type]
     - X-axis: [variable]
     - Y-axis: [variable]
     - Color/facet: [if applicable]
  4. Apply styling:
     - Theme: minimal
     - DPI: 300
  5. Save to output/figures/
verify: |
  - File exists at output path
  - File size > 0
  - Visual elements present (not blank)
done: Figure saved to output/figures/
</task>

### Task Specificity Checklist

Before finalizing each task above, verify:

- [ ] **Unambiguous Scope:** File paths are explicit, not placeholders
- [ ] **Concrete Actions:** Each step is a specific operation, not "process data"
- [ ] **Verifiable Completion:** "done" condition can be programmatically checked
- [ ] **No Hidden Dependencies:** All required inputs listed in files section
- [ ] **Skill Identified:** Which skill to load is explicit

**Test:** Read the task aloud. Could you execute it without asking "what does X mean?"

### Aggregation Specification

| Aggregation | Group By | Metrics | Output |
|-------------|----------|---------|--------|
| State summary | `fips`, `year` | `mean(enrollment)`, `sum(frl_count)` | state_summary_df |

### Analysis Approach

[Describe the analytical methodology: descriptive statistics, comparisons, trends, etc.]

---

## Output Specification

### Notebook Structure

**Marimo Notebook Sections:**

1. **Setup & Imports** — Dependencies, configuration
2. **Data Loading** — Load from processed data files
3. **Data Overview** — Shape, types, sample
4. **Exploratory Analysis** — Distributions, patterns
5. **Main Analysis** — [Specific analysis sections]
6. **Visualizations** — Key charts and graphs
7. **Findings Summary** — Markdown synthesis
8. **Interactive Elements** — [If applicable: filters, selectors]

**UI Elements (if applicable):**

| Element | Type | Purpose |
|---------|------|---------|
| State selector | `mo.ui.dropdown` | Filter analysis by state |
| Year range | `mo.ui.range_slider` | Select year range |

### Report Structure

**Report Sections:**

1. **Executive Summary** — Key findings in 2-3 sentences
2. **Research Question** — What we set out to answer
3. **Data & Methods** — Sources, cleaning, analysis approach
4. **Findings** — Results with visualizations
5. **Limitations** — Caveats and constraints
6. **Data Sources** — Full citations

### Visualization Requirements

| Figure | Type | Purpose | File Name |
|--------|------|---------|-----------|
| Enrollment trends | Line chart | Show change over time | `YYYY-MM-DD_enrollment_trends.png` |
| Distribution | Histogram | Show enrollment distribution | `YYYY-MM-DD_enrollment_dist.png` |

### Deliverables Checklist

| Deliverable | Location | Format |
|-------------|----------|--------|
| Plan document | `research/[project]/` | `.md` |
| Marimo notebook | `research/[project]/` | `.py` |
| Stakeholder report | `research/[project]/` | `.md` |
| Raw data | `research/[project]/data/raw/` | `.parquet`, `.csv` |
| Processed data | `research/[project]/data/processed/` | `.parquet`, `.csv` |
| Figures | `research/[project]/output/figures/` | `.png` |

---

## Validation Checkpoints

### CP1: After Data Fetch

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count | ~10,000 | 0 or >100,000 |
| Columns | 15 | Missing critical columns |
| Years present | 2020, 2021, 2022 | Missing years |
| Critical variable missingness | <10% | >90% |

### CP2: After Cleaning

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count change | -5% to -15% | >50% loss |
| Suppression rate | <20% | >50% |
| Coded values remaining | 0 | Any -1, -2, -3 in analysis vars |

### CP3: After Transformation

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count | Same as CP2 | >90% loss |
| New columns exist | Yes | Missing derived columns |
| Unexpected NAs | 0 | >10% NAs in derived columns |

### CP4: Before Output

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| All planned figures generated | Yes | Missing figures |
| Report sections complete | Yes | Missing sections |
| Notebook runs without error | Yes | Execution errors |

---

## Decisions Log

| Decision | Options Considered | Choice Made | Rationale |
|----------|-------------------|-------------|-----------|
| Data source | CCD vs. PSS | CCD | Research question focuses on public schools |
| Year range | 2018-2022 vs. 2020-2022 | 2020-2022 | Recent years sufficient; avoids COVID transition |
| Suppression handling | Exclude vs. Impute | Exclude | Imputation would introduce bias |

---

## Risk Register

Document risks identified during discovery and planning, with mitigation strategies.

| Risk | Likelihood | Impact | Mitigation | Owner/Stage |
|------|------------|--------|------------|-------------|
| High suppression in key variable | Medium | High | Aggregate to district level if >30%; proceed with caveat if 30-50% | Stage 6 |
| COVID data quality issues (2020) | High | Medium | Exclude 2020 or document caveat prominently | Stage 3 |
| Cross-state variation in reporting | Medium | Medium | Check CRDC state-specific notes; restrict to comparable states | Stage 3 |

**Risk Categories:**
- **Data Availability:** Risk that needed data doesn't exist or has insufficient coverage
- **Data Quality:** Risk of high suppression, missingness, or known collection issues
- **Methodological:** Risk that analysis approach may not be valid for this data
- **Scope:** Risk that analysis scope is too broad or complex
- **Timeline:** Risk that data sources have unexpected lag times
- **QA:** Risk that secondary validation will find issues requiring revision or escalation

**Update Triggers:** See `01_PROTOCOLS.md: Risk Register Updates` for complete trigger list.

**When to Update:**
- **Stage 3 (Source Deep-Dive):** Add risks from source caveats that affect validity/completeness
- **Stage 5 (Data Retrieval):** Add risks when CP1 reveals unexpected shape, data lag, or quality issues
- **Stage 6 (Context Application):** Add risks when suppression rate is 30-50% (below STOP but elevated)
- **Stage 7 (Transformation):** Add risks when unexpected row loss or cardinality violations occur
- **Any stage:** Add risks when data definitions changed between years or other quality issues arise

---

## Current Status & To-Do's

### Current Phase

**Phase:** [1 | 2 | 3 | 4 | 5]
**Stage:** [1-12]
**Status:** [In Progress | Blocked | Complete]

### Active To-Do's

- [ ] [Task 1]
- [ ] [Task 2]
- [ ] [Task 3]

### Blocked Items

| Item | Blocker | Awaiting |
|------|---------|----------|
| [Item] | [What's blocking] | [User guidance | Data | Resolution] |

---

## QA Findings Summary

*Aggregated during Stage 10, finalized during Stage 12*

### QA Checkpoint Summary

| Checkpoint | Stage | Scripts Reviewed | BLOCKERs | WARNINGs | INFOs | Revisions Applied |
|------------|-------|------------------|----------|----------|-------|-------------------|
| QA1 (Post-Fetch) | 5 | [count] | [count] | [count] | [count] | [count] |
| QA2 (Post-Clean) | 6 | [count] | [count] | [count] | [count] | [count] |
| QA3 (Post-Transform) | 7 | [count] | [count] | [count] | [count] | [count] |
| QA4 (Post-Viz) | 8 | [count] | [count] | [count] | [count] | [count] |
| **Total** | — | [sum] | [sum] | [sum] | [sum] | [sum] |

### BLOCKERs Resolved

*Document each QA BLOCKER that was resolved via revision*

| Stage | Script | Issue | Resolution | Revision |
|-------|--------|-------|------------|----------|
| [N] | [filename.py] | [What QA found] | [How fixed] | [_a/_b] |

### WARNINGs Logged

*Document QA WARNINGs for transparency (did not block execution)*

| Stage | Script | Warning | Impact Assessment |
|-------|--------|---------|-------------------|
| [N] | [filename.py] | [Warning description] | [Low/Medium — why acceptable] |

### Unresolved Issues

*Document any QA issues that could not be fully resolved*

| Stage | Issue | Attempts | Outcome | User Decision |
|-------|-------|----------|---------|---------------|
| [N] | [Description] | [N/2] | [Escalated/Accepted] | [Decision] |

**Note:** QA scripts are archived in `scripts/qa/` for reproducibility. See `agent_reference/QA_CHECKPOINTS.md` for checkpoint definitions.

---

## Final Review Log

*Complete during Phase 5, Stage 12*

### Review Date

[YYYY-MM-DD]

### Alignment Check

| Original Request Element | Addressed? | Location |
|--------------------------|------------|----------|
| [Element 1 from request] | [ ] Yes / No | [Section/file] |
| [Element 2 from request] | [ ] Yes / No | [Section/file] |

### Clarification Fulfillment

| Clarification | Implemented? | Notes |
|---------------|--------------|-------|
| [Clarification 1] | [ ] Yes / No | [Notes] |
| [Clarification 2] | [ ] Yes / No | [Notes] |

### Plan Commitments

| Commitment | Fulfilled? | Deviation Notes |
|------------|------------|-----------------|
| [Methodology commitment] | [ ] Yes / No | [If deviated, explain] |
| [Output commitment] | [ ] Yes / No | [If deviated, explain] |

### Quality Checklist

| Category | Item | Status |
|----------|------|--------|
| **Data Integrity** | Validation checkpoints passed | [ ] |
| | Coded values handled | [ ] |
| | Suppression documented | [ ] |
| **Code Quality** | Linting passed (`ruff check`) | [ ] |
| | Formatting applied (`ruff format`) | [ ] |
| **Documentation** | Plan complete | [ ] |
| | Notebook documented | [ ] |
| | Report complete | [ ] |
| | Citations included | [ ] |

### Deviations from Plan

| Deviation | Reason | Impact |
|-----------|--------|--------|
| [What changed] | [Why] | [Effect on analysis] |

### Issues Identified

| Issue | Severity | Resolution |
|-------|----------|------------|
| [Issue] | [Low/Medium/High] | [How resolved or documented] |

### Final Status

**Review Outcome:** [PASSED | ISSUES FOUND]

**If ISSUES FOUND:**
- Issues must be resolved before delivery
- Document resolution in this section
- Re-run Final Review after resolution

---

## Data Citations

*Generated using `education-data-context` skill*

### Primary Data Source

> [Full citation for primary data source]

### Additional Sources

> [Citation 2]

> [Citation 3]

---

## File Manifest

*Updated at delivery*

| File | Path | Description |
|------|------|-------------|
| Plan | `research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title] Plan.md` | This document |
| Notebook | `research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title].py` | Marimo analysis notebook |
| Report | `research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title] Report.md` | Stakeholder report |
| **Learnings** | `research/YYYY-MM-DD [Title]/LEARNINGS.md` | **Session learnings (API gotchas, methodology insights)** |
| Raw Data | `research/YYYY-MM-DD [Title]/data/raw/YYYY-MM-DD_*.parquet` | Original API responses |
| Processed Data | `research/YYYY-MM-DD [Title]/data/processed/YYYY-MM-DD_*.parquet` | Cleaned data |
| Figures | `research/YYYY-MM-DD [Title]/output/figures/YYYY-MM-DD_*.png` | Visualizations |
| Fetch Scripts | `research/YYYY-MM-DD [Title]/scripts/stage5_fetch/*.py` | Data retrieval code |
| Clean Scripts | `research/YYYY-MM-DD [Title]/scripts/stage6_clean/*.py` | Context application code |
| Transform Scripts | `research/YYYY-MM-DD [Title]/scripts/stage7_transform/*.py` | Transformation code |
| Viz Scripts | `research/YYYY-MM-DD [Title]/scripts/stage8_viz/*.py` | Visualization code |
| **QA Scripts** | `research/YYYY-MM-DD [Title]/scripts/qa/*.py` | **QA inspection scripts from code-reviewer** |
| Debug Scripts | `research/YYYY-MM-DD [Title]/scripts/debug/*.py` | Diagnostic scripts (if any) |
