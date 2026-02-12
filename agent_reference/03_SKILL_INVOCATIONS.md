# Skill Invocation Patterns

This document provides complete invocation templates for all skills used in the research workflow.

> **Invocation Pattern Authority:** Each agent's `## Invocation` section (in `agents/[agent-name].md`)
> is the **authoritative source** for that agent's invocation pattern. This file provides
> **orchestrator-focused context** that wraps those patterns with stage-specific details, context
> inlining guidance, and prompt size limits. When in doubt, defer to the agent file's Invocation section.

---

## Standard Task Prompt Structure

**REQUIRED:** Every subagent invocation MUST use this standardized format to ensure consistent handoffs and verifiable outputs.

### File-First Execution Rule

**CRITICAL:** For Stages 5-8, all code execution MUST follow the file-first pattern:

1. **Write script FIRST** — Code goes to `scripts/stage{N}_{type}/{step}_{task-name}.py`
2. **Execute via wrapper** — single Bash call: `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py` (automatically captures output, appends execution log)
3. **Version on failure** — Failed scripts get `_a`, `_b`, `_c` suffixes; original preserved with its failed output

Closely read `agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

### Template

```python
Task({
    description: "[3-5 word summary]",
    prompt: """
## AGENT PROTOCOL
Follow the protocol in `{BASE_DIR}/agents/[agent-name].md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name '[skill-name]'.

## CONTEXT FROM PLAN
[Paste relevant Plan section - respect size limits from `{BASE_DIR}/agent_reference/07_CONTEXT_MANAGEMENT.md`]

Original Request: [verbatim user request — required for Stage 4; include for other stages when methodology alignment matters]
Research Question: [from Plan]
Data Source: [from Plan]
Current Stage: [N]
Wave: [N] (if applicable)

## TASK SPECIFICATION
<task name="[task-name]" type="[auto|checkpoint:human-verify|checkpoint:decision]" wave="[N]">
  <depends_on>[task-ids or "none"]</depends_on>
  <skill>[skill-name]</skill>
  <agent>[agent-name]</agent>
  <files>
    <input>[input file path]</input>
    <output>[output file path]</output>
  </files>
  <action>
    1. [Specific step 1]
    2. [Specific step 2]
    3. [Specific step 3]
  </action>
  <verify>
    - [Verification criterion 1]
    - [Verification criterion 2]
    - [Verification criterion 3]
  </verify>
  <done>[Measurable completion condition]</done>
</task>

## FILE-FIRST RULE (Stages 5-8)
Write Python code to a script file FIRST. Do NOT execute interactively.
Execute ONLY via single Bash call: `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py` — do NOT run `python script.py` directly, chain commands with `&&`/`;`, or prefix with `cd`.
Follow the IAT documentation standard (`{BASE_DIR}/agent_reference/INLINE_AUDIT_TRAIL.md`).
Closely read `{BASE_DIR}/agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

## OUTPUT FORMAT
Return findings in this EXACT structure:

### [Task Name] Results

**Status:** [PASSED | FAILED | WARNING]
**Task Type:** [auto | checkpoint:human-verify | checkpoint:decision]

**Summary:**
[2-3 sentence summary of what was done]

**Pre-State:** [For transformations: shape, sample]
**Post-State:** [For transformations: shape, sample]
**Row Change:** [+/-X% or N/A]

**Findings:**
- [Key finding 1]
- [Key finding 2]
- [Key finding 3]

**Verification:**
| Criterion | Result | Notes |
|-----------|--------|-------|
| [From verify block] | PASS/FAIL | [Details] |

**Files Created/Modified:**
- `[path]`: [description]

**Issues Encountered:**
- [Issue + resolution, or "None"]

**Confidence:** [HIGH | MEDIUM | LOW]
**If LOW:** [What needs resolution before proceeding]

**Deviations Applied:** [List per RULE 1-3 from `{BASE_DIR}/agent_reference/04_BOUNDARIES.md`, or "None"]

**Commit:** [If task completed, suggested commit message]
""",
    subagent_type: "[Plan | general-purpose]"
})
```

---

## Task Types

| Type | When to Use | Human Involvement |
|------|-------------|-------------------|
| `auto` | Fully automatable (90% of tasks) | None unless STOP condition |
| `checkpoint:human-verify` | Needs visual confirmation | Report results, await "proceed" |
| `checkpoint:decision` | Multiple valid approaches | Present options, await selection |
| `checkpoint:human-action` | User must perform action themselves | Report instructions, await completion |

**Note:** `checkpoint:human-action` is used when Claude cannot automate a step (e.g., external authentication, restricted data downloads). See `05_VALIDATION_CHECKPOINTS.md` for full classification details.

### checkpoint:auto (Default)

Use for:
- Mirror-based data downloads
- Data cleaning
- Transformations
- Aggregations
- Visualization generation
- Test execution

**Behavior:** Execute, validate, report status. Proceed if PASSED.

### checkpoint:human-verify

Use for:
- Unusual suppression patterns (30-50%)
- Data lag warnings (≥3 years)
- COVID-19 data quality flags
- Final Report before delivery
- Results that differ from expectations

**Behavior:** Execute, report results with context, ask "Should I proceed?"

### checkpoint:decision

Use for:
- Multiple valid data sources
- Methodology alternatives
- Scope adjustments when data is limited
- How to handle edge cases

**Behavior:** Present options with pros/cons, await selection, then execute

### Task Specificity Test

Before sending any task to a subagent, verify it passes this test:

**Test:** Could a fresh Claude instance with ONLY this task description + skill access complete it without asking clarifying questions?

**Checklist:**
- [ ] **Unambiguous Scope:** Clear what files/data this touches
- [ ] **Concrete Actions:** Steps specific enough to execute without interpretation
- [ ] **Verifiable Completion:** "done" condition is objectively measurable
- [ ] **No Hidden Dependencies:** All prerequisites explicitly stated
- [ ] **Size Appropriate:** Context within limits for subagent type

If any checkbox is unchecked → Add specificity until all pass.

---

## Prompt Size Limits by Subagent Type

| Subagent Type | Max Prompt Size | Max Context from Plan |
|---------------|-----------------|----------------------|
| Plan | 500 words | 200 words |
| general-purpose | 1000 words | 500 words |

**If you need more context than these limits, break the task into smaller subtasks.**

---

## Context Inlining Protocol

### Principle: Inline Critical Context Directly

**Rule:** When dispatching a Task, inline critical context directly in the prompt. Don't rely on subagent file reads for essential information.

**Why This Matters:**
- Eliminates round-trip file lookups
- Ensures subagent has complete context immediately
- Produces reproducible results across sessions
- Reduces failure points (no "file not found" errors)

### What to Inline

| Content Type | Inline? | Rationale |
|--------------|---------|-----------|
| Relevant Plan sections | YES | Methodology decisions needed |
| Prior stage findings | YES | Dependencies must be clear |
| Decision context | YES | Rationale affects execution |
| Expected values | YES | Validation needs targets |
| File paths | YES | Must be explicit |
| Full skill content | NO | Subagent loads via skill tool |
| Raw data samples | NO | Only shapes/summaries |
| Complete code files | NO | Only relevant sections |

### Inlining Template

```python
Task({
    description: "Stage [N]: [Name]",
    prompt: """## AGENT PROTOCOL
Follow the protocol in `{BASE_DIR}/agents/[agent-name].md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name '[skill-name]'.

## INLINED CONTEXT

### From Plan (Methodology):
{paste_relevant_methodology_section}

### From Stage [N-1] (Prior Findings):
- Key finding 1: [value]
- Key finding 2: [value]
- Files created: [paths]
- CP Status: [PASSED/FAILED]

### Decision Context:
- [Decision 1]: [what was decided and why]
- [Decision 2]: [what was decided and why]

## TASK SPECIFICATION
<task name="[task-name]" ...>
...
</task>
""",
    subagent_type: "[type]"
})
```

### What NOT to Inline

- **Full Plan document:** Too large. Inline only relevant sections.
- **Complete skill content:** Subagent loads via skill tool (5K-20K tokens saved).
- **Downloaded raw data:** Summarize to shapes and key values.
- **Complete notebooks:** Reference by path, inline only specific cells if needed.
- **Full error tracebacks:** Summarize to error type and key message.

### Size Limits for Inlined Content

See "Prompt Size Limits by Subagent Type" table above for size limits. The same limits apply to inlined content.

**If you need more context:** Break the task into smaller subtasks, each with focused context.

---

## Confidence Level Defaults

### Standard Confidence Assignments

| Source Type | Default Confidence | Upgrade Path | Downgrade Path |
|-------------|-------------------|--------------|----------------|
| Official NCES documentation | HIGH | — | Contradicted by actual data |
| Skill reference content | HIGH | — | Outdated info discovered |
| Data exploration results | MEDIUM | Multiple mirrors confirm | Single endpoint, unclear docs |
| Inferred from data patterns | LOW | Documentation confirms | Contradicted by test |
| User-provided information | HIGH | — | Conflicts with official sources |

### Confidence Requirements

**HIGH confidence findings:** Proceed normally.

**MEDIUM confidence findings:** Document the uncertainty and proceed with caution.

**LOW confidence findings:** MUST have resolution path before proceeding:
1. Re-run discovery with refined parameters
2. Escalate to user for guidance
3. Document risk acceptance explicitly in Plan

**LOW confidence items cannot be silently ignored.**

### Reporting Confidence

Every subagent return MUST include confidence assessment:

```markdown
**Confidence Assessment:**
| Finding | Confidence | Rationale |
|---------|------------|-----------|
| Mirror file exists | HIGH | Direct download successful |
| Variable meaning | MEDIUM | Skill reference, not NCES docs |
| Suppression threshold | LOW | Inferred from patterns |

**Overall Confidence:** [MEDIUM]
**LOW Confidence Items Requiring Resolution:**
- Suppression threshold: Need to verify with source documentation
```

---

## Invocation Principles

### When to Delegate

Delegate to subagents to:
- Preserve orchestrator context
- Leverage specialized skill knowledge
- Execute focused tasks

### Skill Loading Confirmation

After invoking a skill, confirm it loaded successfully:

**Indicators of successful loading:**
1. The skill's core guidance is now available in your working context
2. Reference files can be accessed from the skill's `./references/` directory
3. The skill's decision trees and workflows are clear

**If skill loading fails:**
1. Report: "Unable to load [skill-name] skill"
2. Attempt to proceed with base knowledge (if possible)
3. Flag reduced confidence in output due to missing specialized guidance
4. Escalate to user if skill is critical for the task

**Example confirmation check:**
```markdown
After calling skill tool with name 'education-data-explorer':
- ✓ Core guidance loaded: Understand data levels (schools, districts, colleges)
- ✓ Reference files accessible: schools-endpoints.md, districts-endpoints.md, colleges-endpoints.md
- ✓ Decision trees clear: "What data level do I need?" flow available

Status: Skill loaded successfully, proceeding with data exploration
```

### Subagent Type Selection

See `CLAUDE.md` "Subagent Type Selection" for capabilities by type (`Plan` = read-only; `general-purpose` = full capabilities including file writes).

### Standard Invocation Pattern

```python
Task({
    description: "Stage [N]: [Name]",
    prompt: """You have access to a skill tool. First, call the skill tool with name '[skill-name]'.

**CONTEXT:**
[Relevant context from Plan or prior stages]

**TASK:**
[Specific task to complete]

**THOROUGHNESS DIRECTIVE:**
[Stage-specific requirements]

**OUTPUT FORMAT:**
[Expected output structure]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "[Plan | general-purpose]"
})
```

---

## Data Skills

### education-data-explorer

**Purpose:** Identify available datasets and variables
**Stage:** 2 (Data Exploration)
**Subagent:** Plan

```python
Task({
    description: "Stage 2: Data Exploration",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'education-data-explorer'.

**ORIGINAL REQUEST (for context):**
> {original_user_request_verbatim}

**RESEARCH QUESTION:**
{research_question}

**CONSTRAINTS:**
- Years of interest: {years}
- Geographic scope: {geography}
- Population: {population}

**THOROUGHNESS DIRECTIVE:**
- Search ALL relevant data levels (schools, districts, colleges as appropriate)
- Consider multiple potential data sources before recommending
- Flag ALL variables that might need deeper source-specific investigation
- Check year coverage against research question needs
- Include a 'Limitations Encountered' section in your output
- Be explicit about what you searched and what you found

**OUTPUT FORMAT:**
Return findings in this structure:

### 1. Recommended Data Level
[schools | school-districts | college-university] with rationale

### 2. Candidate Endpoints
| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|

### 3. Key Variables
| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|

### 4. Variables Flagged for Deep-Dive
| Variable | Reason for Deep-Dive |
|----------|---------------------|

### 5. Limitations Encountered
| Limitation | Impact | Recommended Resolution |
|------------|--------|------------------------|

### 6. Completeness Assessment
- [ ] Schools level searched: [Yes/No/NA]
- [ ] Districts level searched: [Yes/No/NA]
- [ ] Colleges level searched: [Yes/No/NA]
- [ ] Multiple sources considered: [list sources checked]

### 7. Confidence Assessment
| Finding | Confidence | Rationale |
|---------|------------|-----------|
| [key finding] | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "Plan"
})
```

---

### * -data-source- * (Source-Specific)

**Purpose:** Deep-dive into source-specific caveats and limitations
**Stage:** 3 (Source Deep-Dive)
**Subagent:** Plan

**Available source skills:**
- `education-data-source-ccd` — K-12 schools and districts
- `education-data-source-ipeds` — Colleges and universities
- `education-data-source-crdc` — Civil rights data
- `education-data-source-scorecard` — Post-college outcomes
- `education-data-source-edfacts` — State assessments and graduation
- `education-data-source-meps` — School poverty estimates
- `education-data-source-saipe` — District poverty estimates
- `education-data-source-eada` — College athletics
- `education-data-source-nacubo` — College endowments
- `education-data-source-pseo` — Post-secondary employment
- `education-data-source-fsa` — Federal student aid
- `education-data-source-nhgis` — Census geography
- `education-data-source-nccs` — Nonprofit data
- `education-data-source-campus-safety` — Campus crime

```python
Task({
    description: "Stage 3: Source Deep-Dive - {source_name}",
    prompt: """You are a Source Researcher. Follow the protocol in `{BASE_DIR}/agents/source-researcher.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name '{domain}-data-source-{source}'.

**CONTEXT FROM STAGE 2:**
Endpoints identified: {endpoints}
Variables to investigate: {variables}

**VARIABLES REQUIRING DEEP-DIVE:**
{flagged_variables_with_reasons}

**THOROUGHNESS DIRECTIVE:**
- Extract ALL coded value mappings for flagged variables
- Document ALL suppression patterns and thresholds
- Identify ALL source-specific caveats and limitations
- Note ANY cross-state comparability issues
- Check for historical definition changes
- Include COVID-19 impact notes for 2020-2021 data
- Document population coverage (who is included/excluded)

**OUTPUT FORMAT:**
Return findings in this structure:

### Source: {source_name}

### 1. Source-Specific Caveats
| Caveat | Impact on Analysis | Mitigation Strategy |
|--------|-------------------|---------------------|

### 2. Coded Value Mappings
| Variable | Code | Meaning | Recommended Action |
|----------|------|---------|-------------------|
| [var] | -1 | Missing/not reported | Filter before calculations |
| [var] | -2 | Not applicable | Exclude from analysis |
| [var] | -3 | Suppressed | Document; cannot recover |

### 3. Suppression Patterns
| Variable | Typical Rate | Threshold | Impact on Analysis |
|----------|--------------|-----------|-------------------|

### 4. Cross-State Comparability
| Analysis Type | Valid Across States? | Notes |
|---------------|---------------------|-------|

### 5. Critical Warnings
1. **[Warning Name]:** [Description]
   - **Mitigation:** [How to handle]

### 6. Limitations Encountered
| Limitation | Impact | Resolution |
|------------|--------|------------|

### 7. Confidence Assessment
| Finding | Confidence | Rationale |
|---------|------------|-----------|
| [key finding] | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "Plan"
})
```

---

### research-synthesizer (Stage 3.5: Findings Synthesis)

**Purpose:** Consolidate Stage 2-3 findings into unified planning guidance
**Stage:** 3.5 (after all Stage 3 source research completes)
**Agent:** `research-synthesizer` (see `agents/research-synthesizer.md`)
**Subagent:** general-purpose

For the complete invocation pattern, see `agents/research-synthesizer.md` Invocation section.
The orchestrator provides all Stage 2 and Stage 3 outputs as context. The agent returns
a unified synthesis with cross-source conflict resolution and join feasibility assessment.

---

### data-planner (Plan Creation)

**Purpose:** Create comprehensive research plan with executable task sequences
**Stage:** 4 (Plan Creation)
**Agent:** `data-planner` (see `agents/data-planner.md`)
**Subagent:** general-purpose

```python
Task({
    description: "Stage 4: Plan Creation",
    prompt: """You are a Data Planner. Follow the protocol in `{BASE_DIR}/agents/data-planner.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**ORIGINAL USER REQUEST (VERBATIM — paste into Plan as-is):**
> {original_user_request_verbatim}

**CLARIFICATIONS RECEIVED:**
{numbered_list_of_clarifications_or_None}

**RESEARCH QUESTION (orchestrator formulation):**
{research_question}

**STAGE 2 FINDINGS (Data Exploration):**
{stage_2_output_summary}

**STAGE 3 FINDINGS (Source Deep-Dive):**
{stage_3_output_summary}

**STAGE 3.5 FINDINGS (research synthesis):**
{stage_3_5_synthesis}

**PROJECT FOLDER:**
research/{date} {title}/

**TASK:**
Create a comprehensive Plan document following `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md`.

CRITICAL: The Plan MUST begin with `## Original Request & Clarifications`
containing the VERBATIM original user request above as a blockquote.
Do NOT paraphrase or summarize — copy the exact text.

**OUTPUT:**
- Plan saved to: research/{date} {title}/{date} {title} Plan.md
- Structure follows `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md`
- All sections populated (no placeholders)
""",
    subagent_type: "general-purpose"
})
```

**Orchestrator Checklist Before Invoking data-planner:**
- [ ] Original user request text available (verbatim, not paraphrased)
- [ ] Clarifications documented (numbered list)
- [ ] Stage 2 findings summarized
- [ ] Stage 3 findings summarized (per source)
- [ ] Stage 3.5 synthesis included
- [ ] Project folder path determined

---

### education-data-query

**Purpose:** Download data from mirrors
**Stage:** 5 (Data Retrieval)
**Subagent:** general-purpose

```python
Task({
    description: "Stage 5: Data Retrieval",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'education-data-query'.

**QUERY SPECIFICATION:**
- Dataset Path: {dataset_path}  (from datasets-reference.md, flat format e.g. "ccd/schools_ccd_directory")
- Years: {years}
- Filters: {filters}
- Variables: {variables}
- Expected Records: ~{expected_count}

**DATA OUTPUT REQUIREMENTS:**
- Save to: data/raw/{date_prefix}_{source}_{description}.parquet

**RISK REGISTER ITEMS FOR THIS TASK:**
| Risk | Likelihood | Impact | Mitigation | Watch For |
|------|------------|--------|------------|-----------|
| {risk_name} | {L/M/H} | {L/M/H} | {specific_action} | {symptom_to_monitor} |

During execution, ACTIVELY MONITOR for watch-for symptoms. Escalate if detected.

**CODED VALUE EXPECTATIONS:**
Retrieved data may include -1 (missing), -2 (not applicable), -3 (suppressed).
These will be handled in Stage 6. Report presence in CP1 output.

**MIRROR FETCH PROTOCOL (MANDATORY):**
Use the mirror-based fetch pattern from the education-data-query skill:
1. Try each mirror in priority order (per mirrors.yaml)
2. Build URLs from each mirror's url_template + dataset path parameters
3. Read using mirror's read_strategy; fall through on 404/timeout
4. Apply year/state/other filters locally with Polars
5. Log which mirror was used and the fetch result

**THOROUGHNESS DIRECTIVE:**
- Try each mirror in priority order
- Handle mirror failures with fallback
- Validate response shape immediately after fetch
- Document which mirror was used
- Verify all requested years are present
- Verify all requested columns are present

**OUTPUT FORMAT:**
Return findings in this structure:

### Fetch Summary
- Mirror used: [name from mirrors.yaml]
- Download URL: [full URL used]
- Records retrieved: [count]
- Columns retrieved: [list]
- Years present: [list]
- Mirror fallback: [None | fell through from {mirror_name} due to {reason}]

### Initial Validation (CP1)
- Shape: [rows] x [cols]
- Expected rows: [from Plan]
- Row count ratio: [actual/expected]
- Missing values by column:
  | Column | Null Count | Null % |
  |--------|------------|--------|
- Critical columns present: [Yes/No]
- **CP1 Status:** [PASSED | FAILED | WARNING]
- **If FAILED:** [Stop reason]

### File Locations
- Parquet: data/raw/{filename}.parquet

### Confidence Assessment
| Check | Confidence | Rationale |
|-------|------------|-----------|
| Data completeness | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "general-purpose"
})
```

#### QA Follow-Up (MANDATORY)

**After research-executor returns from Stage 5, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** below (see "code-reviewer (QA Agent)" section)
with stage-specific values for Stage 5.

**Do NOT proceed to Stage 6 until QA returns PASSED or WARNING.**

---

### education-data-context

**Purpose:** Apply source-specific cleaning and generate citations
**Stage:** 6 (Context Application)
**Subagent:** general-purpose

```python
Task({
    description: "Stage 6: Context Application",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'education-data-context'.

**DATA SOURCE:** {source_name}

**RAW DATA LOCATION:** data/raw/{raw_data_filename}

**CAVEATS FROM STAGE 3:**
{source_caveats}

**CODED VALUE HANDLING (from Plan):**
{coded_value_specification}

**CLEAN DATA OUTPUT:**
- Save to: data/processed/{date_prefix}_{description}.parquet

**RISK REGISTER ITEMS FOR THIS TASK:**
| Risk | Likelihood | Impact | Mitigation | Watch For |
|------|------------|--------|------------|-----------|
| {risk_name} | {L/M/H} | {L/M/H} | {specific_action} | {symptom_to_monitor} |

During execution, ACTIVELY MONITOR for watch-for symptoms. Escalate if detected.

**SUPPRESSION TOLERANCE (from Plan):**
- Target suppression rate: <{target}%
- WARNING threshold: {warning_threshold}%
- BLOCKER threshold: {blocker_threshold}%

**THOROUGHNESS DIRECTIVE:**
- Apply ALL coded value filters as specified
- Calculate suppression rate for key variables
- BLOCK if attempting cross-state assessment comparison (NEVER valid)
- BLOCK if suppression rate exceeds 50%
- Generate complete citation text with access date
- Document all cleaning decisions and row impacts

**OUTPUT FORMAT:**
Return findings in this structure:

### Cleaning Applied
| Code Filtered | Variable(s) | Rows Removed | % of Total |
|---------------|-------------|--------------|------------|
| -1 (Missing) | | | |
| -2 (N/A) | | | |
| -3 (Suppressed) | | | |
| **Total** | | | |

### Data Quality Report (CP2)
- Original rows: [count]
- Clean rows: [count]
- Total loss: [count] ([%])
- Suppression rate (key variable): [%]
- **CP2 Status:** [PASSED | FAILED]
- **If FAILED:** [Stop reason]

### Validity Check
- Analysis type: {analysis_description}
- Cross-state comparison: [Yes/No]
- **Valid:** [Yes | No | Conditional]
- **Warnings:** [list any concerns]

### Citation
> {full_citation_text}

### File Locations
- Parquet: data/processed/{filename}.parquet

### Confidence Assessment
| Check | Confidence | Rationale |
|-------|------------|-----------|
| Data quality | HIGH/MEDIUM/LOW | [why this confidence level] |
| Analysis validity | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "general-purpose"
})
```

#### QA Follow-Up (MANDATORY)

**After research-executor returns from Stage 6, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** below (see "code-reviewer (QA Agent)" section)
with stage-specific values for Stage 6.

**Do NOT proceed to Stage 7 until QA returns PASSED or WARNING.**

---

## Data Science Skills

### data-scientist

**Purpose:** Apply rigorous methodology to analysis
**Stage:** 7 (EDA & Transformation)
**Subagent:** general-purpose

```python
# ITERATIVE INVOCATION PATTERN (Required for Stage 7)
# Execute transformations ONE AT A TIME, not all at once

# Step 1: Initial EDA (no transformations yet)
Task({
    description: "Stage 7.1: Initial EDA",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.

**DATA LOCATION:** data/processed/{processed_data_filename}

**TASK:** Perform ONLY initial exploratory data analysis. DO NOT transform data yet.

**REQUIRED ACTIONS (from data-scientist skill):**
1. Load data
2. Check shape, types, memory usage
3. Profile distributions (head, describe, value_counts)
4. Identify missing values, outliers, unexpected values
5. Document findings

**OUTPUT FORMAT:**
Return EDA summary ONLY:
- Shape: [rows x cols]
- Key distributions: [summary]
- Data quality issues: [list]
- Ready for transformations: [Yes/No]

**Confidence Assessment:**
| Aspect | Confidence | Rationale |
|--------|------------|-----------|
| Data quality | HIGH/MEDIUM/LOW | [why] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**Issues Requiring Resolution:** [list or "None"]

Do NOT proceed to transformations. Return findings for orchestrator review.""",
    subagent_type: "general-purpose"
})

# Step 2: Execute transformations iteratively (one or small batch at a time)
# Orchestrator provides specific transformation from Plan's transformation sequence
# CRITICAL: Include prior transformation context for continuity

Task({
    description: "Stage 7.2: Execute Transformation #{n}",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.

**IMPORTANT:** This is script-based execution, NOT marimo. Write transformations to script files following `{BASE_DIR}/agent_reference/SCRIPT_TEMPLATE.md`.

**DATA LOCATION:** {current_data_location}

## PRIOR TRANSFORMATION CONTEXT (REQUIRED)

### From Stage 7.1 (EDA):
- Data shape: {eda_rows} rows × {eda_cols} columns
- Key distributions: {distribution_summary}
- Data quality issues identified:
  - {issue_1}
  - {issue_2}

### Transformations Completed:
| # | Name | Pre-Rows | Post-Rows | Change | CP3 | Issues |
|---|------|----------|-----------|--------|-----|--------|
{for_each_completed_transformation}
| {n-1} | {name} | {pre} | {post} | {%} | {status} | {issues_or_none} |

### Carry-Forward Findings:
{from_prior_transformation_reports}
- {finding_1}
- {finding_2}

### Invariants Established (MUST MAINTAIN):
- {invariant_1_from_prior}
- {invariant_2_from_prior}

---

**YOUR TRANSFORMATION (#{n}):** {specific_transformation_description}

**EXPECTED OUTCOME:** {expected_outcome_from_plan}

**VALIDATION CRITERIA:** {validation_criteria_from_plan}

**JOIN CARDINALITY (if join):** {cardinality_from_plan}
- If this transformation is a join, use `validate_join()` function from `{BASE_DIR}/agent_reference/05_VALIDATION_CHECKPOINTS.md`
- Pass the cardinality value to verify row count expectations
- Check for fan-out (unexpected row multiplication) or data loss (unexpected row reduction)

**EXECUTION PROTOCOL (from `{BASE_DIR}/CLAUDE.md` Iteration Protocol):**
1. **DESCRIBE:** Confirm what you will do
2. **CODE:** Write transformation code with pre-state capture
3. **EXECUTE:** Run the code
4. **VALIDATE:** Compare pre/post state, check invariants
5. **DECIDE:** Report PASS/FAIL status

**THOROUGHNESS DIRECTIVE:**
- Capture pre-state (shape, sample) BEFORE transforming
- Execute ONLY this one transformation
- Validate immediately after (compare pre/post)
- Use script-based validation (see `{BASE_DIR}/agent_reference/SCRIPT_TEMPLATE.md` and `{BASE_DIR}/agent_reference/EXECUTION_CAPTURE.md`)
- Report clear PASS/FAIL with metrics

**OUTPUT FORMAT:**
Return validation report:

### Transformation #{n}: {description}
**Pre-state:** {shape}, sample: {sample_ids}
**Post-state:** {shape}, sample: {sample_ids}
**Row change:** {percent}
**Invariants:** {list with pass/fail}
**Status:** PASSED | FAILED

If FAILED:
- Issue description: [what went wrong]
- Proposed fix: [how to correct]

Do NOT proceed to transformation #{n+1}. Return to orchestrator for approval.""",
    subagent_type: "general-purpose"
})
```

#### QA Follow-Up (MANDATORY - After EACH Transformation)

**After research-executor returns from EACH Stage 7 transformation, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** below (see "code-reviewer (QA Agent)" section)
with stage-specific values for Stage 7.

**Do NOT proceed to transformation #{n+1} until QA returns PASSED or WARNING.**

```python
# Step 3: Repeat Step 2 AND QA for each transformation in sequence
# Orchestrator increments {n} and provides next transformation
# QA is REQUIRED after EACH transformation, not just at the end

# Step 4: Final CP3 Validation (after all transformations complete)
Task({
    description: "Stage 7.3: Final CP3 Validation",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.

**TASK:** Perform final CP3 validation after all transformations complete.

**DATA LOCATIONS:**
- Original: data/processed/{original_filename}
- Transformed: data/processed/{transformed_filename}

**VALIDATION CHECKS:**
1. Compare original vs. final shape
2. Verify all expected transformations applied
3. Check for unexpected nulls introduced
4. Verify invariants (totals preserved, IDs intact)
5. Generate transformation summary table

**OUTPUT FORMAT:**
### CP3 Validation Report
**Overall change:** {original_shape} → {final_shape}

**Transformation summary:**
| Step | Operation | Row Change | Status |
|------|-----------|------------|--------|

**Data quality:**
- New nulls: {count by column}
- Unexpected changes: {list}

**CP3 Status:** PASSED | FAILED | WARNING

If WARNING or FAILED, provide recommendations.""",
    subagent_type: "general-purpose"
})
```

---

### polars

**Purpose:** DataFrame operations
**Stage:** 7 (EDA & Transformation)
**Subagent:** general-purpose

Typically invoked alongside `data-scientist` skill. Use for specific Polars syntax questions or complex operations.

```python
Task({
    description: "Polars Operation: {operation_name}",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'polars'.

**OPERATION NEEDED:**
{description_of_operation}

**INPUT DATA:**
- Location: {data_path}
- Columns involved: {columns}

**EXPECTED RESULT:**
{expected_outcome}

Return the Polars code to accomplish this, with validation.""",
    subagent_type: "general-purpose"
})
```

---

### plotnine

**Purpose:** Static visualizations (ggplot2 style)
**Stage:** 8 (Visualization)
**Subagent:** general-purpose

```python
Task({
    description: "Stage 8: Visualization - Static Plots",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'plotnine'.

**VISUALIZATION SPECIFICATION (from Plan):**
{visualization_requirements}

**DATA LOCATION:** data/processed/{analysis_data_filename}

**OUTPUT LOCATION:** output/figures/

**REQUIRED PLOTS:**
1. {plot_1_description} → {date_prefix}_{plot_1_name}.png
2. {plot_2_description} → {date_prefix}_{plot_2_name}.png

**STYLE REQUIREMENTS:**
- Theme: minimal/clean
- DPI: 300
- Dimensions: as appropriate for content

Return the plotting code and confirm files are saved.""",
    subagent_type: "general-purpose"
})
```

---

### plotly

**Purpose:** Interactive visualizations
**Stage:** 8 (Visualization)
**Subagent:** general-purpose

```python
Task({
    description: "Stage 8: Visualization - Interactive Plots",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'plotly'.

**VISUALIZATION SPECIFICATION (from Plan):**
{visualization_requirements}

**DATA LOCATION:** data/processed/{analysis_data_filename}

**OUTPUT LOCATION:** output/figures/

**REQUIRED PLOTS:**
1. {plot_description} → {date_prefix}_{plot_name}.html (interactive)
   Also export: {date_prefix}_{plot_name}.png (static)

**INTERACTIVITY REQUIREMENTS:**
- Hover information: {hover_fields}
- Selection: {selection_type}

Return the plotting code and confirm files are saved.""",
    subagent_type: "general-purpose"
})
```

#### QA Follow-Up for Stage 8 (MANDATORY)

**After research-executor completes visualization scripts, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** below (see "code-reviewer (QA Agent)" section)
with stage-specific values for Stage 8.

**Do NOT proceed to Stage 9 until QA returns PASSED or WARNING for all visualization scripts.**

---

### marimo (via notebook-assembler agent)

**Purpose:** COMPILE executed scripts into notebook by LITERALLY COPYING file contents
**Stage:** 9 (Script Compilation)
**Agent:** notebook-assembler (see `agents/notebook-assembler.md`)
**Subagent:** general-purpose

> **CRITICAL CONSTRAINT:** The notebook LITERALLY COPIES script file contents into cells. It does NOT generate new code, dashboards, filters, or interactive widgets. The notebook is a script viewer.

> **WHAT THIS IS:** A compiler that copies files into cells.
> **WHAT THIS IS NOT:** A dashboard builder, an analysis tool, or an interactive explorer.

```python
Task({
    description: "Stage 9: Compile Scripts into Notebook",
    prompt: """You are a Notebook Assembler. Follow the protocol in `{BASE_DIR}/agents/notebook-assembler.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Also call the skill tool with name 'marimo' for basic marimo syntax.

## CRITICAL: YOU ARE A COMPILER, NOT AN ANALYST

Your job is to:
1. READ each script file from `scripts/`
2. COPY the Python code VERBATIM into a marimo cell
3. COPY the execution log VERBATIM into a collapsed accordion
4. ADD ONLY a simple `pl.read_parquet() + mo.ui.table()` cell

You are a COPY-PASTE MACHINE with formatting. Nothing more.

## WHAT YOU MUST NOT DO (ABSOLUTE PROHIBITIONS)

See `02_WORKFLOW_STAGES.md` Stage 9 "ABSOLUTE PROHIBITIONS" for the complete prohibition list. In short: NO dashboards, NO widgets, NO new aggregations, NO new visualizations, NO paraphrasing script code.

## SCRIPTS LOCATION

scripts/
├── stage5_fetch/   ← Read each .py file
├── stage6_clean/   ← Read each .py file
├── stage7_transform/ ← Read each .py file
└── stage8_viz/     ← Read each .py file

## FOR EACH SCRIPT, CREATE EXACTLY 4 CELLS

**Cell 1 (Markdown):** Header with script name, paths, status
**Cell 2 (Code):** VERBATIM COPY of script code (before execution log marker)
**Cell 3 (Markdown):** VERBATIM COPY of execution log in accordion
**Cell 4 (Code):** THE ONLY NEW CODE ALLOWED:
    ```python
    df = pl.read_parquet("path/to/output.parquet")
    mo.ui.table(df.head(100))
    ```
    NOTHING ELSE. No .filter(), no .with_columns(), no aggregations.

## LITERAL COPY EXAMPLE

If script file contains:
```
import polars as pl

print("Hello")

# EXECUTION LOG
# Executed: 2026-01-24
# STDOUT: Hello
```

Then Cell 2 should contain EXACTLY:
```python
# SOURCE: scripts/stage5_fetch/01_example.py
import polars as pl

print("Hello")
```

And Cell 3 accordion should contain EXACTLY:
```
# EXECUTION LOG
# Executed: 2026-01-24
# STDOUT: Hello
```

## OUTPUT

**Notebook file:** {date_prefix} {title}.py

## VERIFICATION BEFORE RETURNING

Count your code cells. If you have ANY of these, you failed:
- mo.ui.dropdown: FAIL
- mo.ui.slider: FAIL
- mo.ui.multiselect: FAIL
- group_by outside script code: FAIL
- pivot outside script code: FAIL
- filter in data inspection: FAIL
- with_columns in data inspection: FAIL

The ONLY acceptable new code is `pl.read_parquet()` + `mo.ui.table()`.""",
    subagent_type: "general-purpose"
})
```

---

## Multi-Skill Invocations

### Combined EDA + Transformation (Stage 7)

When EDA and transformation are closely linked:

```python
Task({
    description: "Stage 7: EDA & Transformation",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist' for methodology.
Then, call the skill tool with name 'polars' for implementation.

**DATA LOCATION:** data/processed/{filename}

**TASK:**
1. Profile the data following data-scientist principles
2. Implement transformations using Polars
3. Validate each step

**TRANSFORMATION SPECIFICATION:**
{transformation_spec_from_plan}

Return comprehensive EDA findings and validated transformation code.""",
    subagent_type: "general-purpose"
})
```

---

### Combined Visualization (Stage 8)

When both static and interactive plots are needed:

```python
Task({
    description: "Stage 8: Visualization",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'plotnine' for static publication plots.
Call the skill tool with name 'plotly' for interactive exploration plots.

**DATA LOCATION:** data/processed/{filename}

**STATIC PLOTS (plotnine):**
{static_plot_specs}

**INTERACTIVE PLOTS (plotly):**
{interactive_plot_specs}

**OUTPUT:** output/figures/

Return all plotting code and confirm files saved.""",
    subagent_type: "general-purpose"
})
```

---

### code-reviewer (QA Agent)

**Purpose:** Secondary QA review of executed scripts
**Stage:** 5-QA, 6-QA, 7-QA, 8-QA (after each script execution)
**Subagent:** general-purpose

**Invocation Timing:** After research-executor completes each script (after CP validation passes).

```python
Task({
    description: "QA Review: Stage {N} Step {step} - {task_name}",
    prompt: """You are a Code Reviewer. Follow the protocol in `{BASE_DIR}/agents/code-reviewer.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**SCRIPT TO REVIEW:**
Path: scripts/stage{N}_{type}/{step}_{task-name}.py

**PLAN LOCATION:**
{plan_path}

**OUTPUT FILES:**
{list_of_output_files}

**CONTEXT:**
- Stage: {N}
- Step: {step}
- Wave: {wave}
- Task: {task_name}
- Research Question: {research_question}

## PLAN EXPECTATIONS FOR THIS TASK (REQUIRED - Inline, not just path)

| Aspect | Expected | Source |
|--------|----------|--------|
| Output rows | {min_rows} - {max_rows} | Plan Transformation Sequence row {step} |
| Row change | ±{tolerance}% | Plan expected outcome |
| Critical columns | {column_list} | Plan Observable Truths |
| Max acceptable loss | {loss_pct}% | Plan Risk Register |
| Join cardinality | {cardinality_or_NA} | Plan (if join task) |

## RISK REGISTER ITEMS FOR THIS STAGE

| Risk | Mitigation | Watch For |
|------|------------|-----------|
| {risk_1} | {mitigation_1} | {symptom_1} |

## OBSERVABLE TRUTH CONTRIBUTION

This task contributes to: "{observable_truth_text}"
Verified when: {verification_condition}

## QA TOLERANCE FOR THIS ANALYSIS

- Acceptable row change: ±{tolerance}%
- Acceptable new nulls: {null_tolerance}%
- BLOCKER if: {blocker_condition}
- WARNING if: {warning_condition}

**TASK:**
1. Review the executed script for correctness and methodology alignment
2. Review the execution log for outcome verification
3. Create iterative QA scripts at: scripts/cr/stage{N}_{step}_cr1.py (+ cr2..cr5 as warranted)
4. Execute QA scripts and synthesize findings across iterations
5. Return QA report with severity classification

**PRIOR QA FINDINGS (if any):**
{accumulated_warnings_from_prior_scripts}

**OUTPUT FORMAT:**
Return findings in this structure:

### QA Review: {task_name}

**QA Status:** [PASSED | ISSUES_FOUND]
**Severity:** [BLOCKER | WARNING | INFO | None]
**Script Reviewed:** scripts/stage{N}_{type}/{step}_{task-name}.py
**QA Scripts Created:** scripts/cr/stage{N}_{step}_cr1.py [+ cr2..cr5 if created]

**Code Review:**
| Check | Status | Notes |
|-------|--------|-------|
| Operations match intent | PASS/FAIL | ... |
| Methodology alignment | PASS/FAIL | ... |
| Validation robustness | PASS/FAIL | ... |

**QA Script Results:**
[Captured output from QA script]

**Issues Found:**
- BLOCKER: [list or "None"]
- WARNING: [list or "None"]
- INFO: [list or "None"]

**Recommendation:** [PROCEED | REVISION_REQUIRED | ESCALATE]
**If Revision:** [Specific changes needed]
""",
    subagent_type: "general-purpose"
})
```

### Revision Request (After QA BLOCKER)

When code-reviewer returns BLOCKER, orchestrator sends revision request to research-executor:

```python
Task({
    description: "Revision: Stage {N} Step {step} - {task_name}",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**REVISION REQUEST**

**Original Script:** scripts/stage{N}_{type}/{step}_{task-name}.py
**Current Final Version:** scripts/stage{N}_{type}/{step}_{task-name}_{suffix}.py

**QA BLOCKER Issue:**
- **Type:** {issue_type}
- **Description:** {issue_description}
- **Location:** {location_in_code}
- **Suggested Fix:** {suggested_fix_from_code_reviewer}

**Instructions:**
1. Create new versioned script: {step}_{task-name}_{next_suffix}.py
2. Apply fix for the BLOCKER issue
3. Execute with full validation
4. Append execution log
5. Return execution report

**Do NOT modify prior script versions** — they serve as audit trail.

**OUTPUT FORMAT:**
[Standard research-executor output format]
""",
    subagent_type: "general-purpose"
})
```

---

## Error Handling in Invocations

### Retry Pattern

```python
# If subagent returns error, retry with clarification
Task({
    description: "Stage [N] - Retry",
    prompt: """Previous attempt encountered: {error_description}

**CORRECTIVE CONTEXT:**
{what_went_wrong}
{how_to_fix}

Please retry the task with this correction.

[Original task specification]""",
    subagent_type: "..."
})
```

### Escalation Pattern

After 2 failed attempts:

```python
# Return to orchestrator with escalation
"""
**ESCALATION: Stage [N] Failed**

**Error:** {error_description}

**Attempts Made:**
1. {attempt_1_description}
2. {attempt_2_description}

**Recommendation:** {suggested_resolution}

Awaiting user guidance.
"""
```

---

## Pre-Pipeline Skills

### data-ingest

**Purpose:** Profile new datasets and author comprehensive Skills
**Stage:** Pre-pipeline (on demand, when new data files arrive)
**Agent:** `data-ingest` (see `agents/data-ingest.md`)
**Subagent:** general-purpose

For the complete invocation pattern, see `agents/README.md` data-ingest section
or `agents/data-ingest.md` Invocation section.
