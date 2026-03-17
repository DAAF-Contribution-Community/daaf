# Workflow Reference: Universal Preamble

This document contains cross-phase orchestration guidance used across all engagement modes.
For phase-specific stage details and invocation templates, see the phase files:
- `WORKFLOW_PHASE1_DISCOVERY.md` (Stages 1, 2, 3, 3.5)
- `WORKFLOW_PHASE2_PLANNING.md` (Stages 4, 4.5)
- `WORKFLOW_PHASE3_ACQUISITION.md` (Stages 5, 6)
- `WORKFLOW_PHASE4_ANALYSIS.md` (Stages 7, 8, 9, 10)
- `WORKFLOW_PHASE5_SYNTHESIS.md` (Stages 11, 12)

> **Domain Extensibility:** This workflow is domain-agnostic. Skill names referenced below (e.g., `education-data-explorer`, `education-data-query`, `education-data-context`) are the demonstration domain defaults. The orchestrator resolves actual skill names from the Plan's Domain Configuration section and provides them in Agent prompts. New domains can be added by authoring domain-specific Skills and registering them in the Plan's Domain Configuration.

> **Invocation Pattern Authority:** Each agent's `## Invocation` section (in `agents/[agent-name].md`)
> is the **authoritative source** for that agent's invocation pattern. This file provides
> **orchestrator-focused context** that wraps those patterns with stage-specific details, context
> inlining guidance, and prompt size targets. When in doubt, defer to the agent file's Invocation section.

> **Parallel Dispatch Limit:** The orchestrator MUST NOT dispatch more than **5 subagents concurrently** — this applies to wave-based task dispatch, Stage 3 source-researcher dispatch, and any other parallel invocation. If more than 5 independent tasks need to run, sub-batch into groups of ≤5 and wait for each sub-batch to complete before dispatching the next. Parallel dispatch is achieved by making multiple Agent tool calls in a **single response message** (foreground parallel). **NEVER use `run_in_background`** — background agents cannot prompt for permissions and will silently fail.

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

For the complete per-script Composite Execution Pattern (execute → QA → revision loop), see `full-pipeline.md` > "Stage 5-8 Per-Script Execution & QA Loop".

### QA Gate Criteria (Added to Each Stage) — ENFORCED

**IMPORTANT:** Gates G5-G8 require POSITIVE confirmation that QA was invoked, not just absence of BLOCKER.

Every Stage 5-8 task includes these MANDATORY requirements:

- [ ] **QA INVOKED** — orchestrator called code-reviewer via Agent tool
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

## Standard Agent Prompt Structure

**REQUIRED:** Every subagent invocation MUST use this standardized format to ensure consistent handoffs and verifiable outputs.

### File-First Execution Rule

**CRITICAL:** For Stages 5-8, all code execution MUST follow the file-first pattern:

1. **Write script FIRST** — Code goes to `scripts/stage{N}_{type}/{step}_{task-name}.py`
2. **Execute via wrapper** — single Bash call: `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py` (automatically captures output, appends execution log)
3. **Version on failure** — Failed scripts get `_a`, `_b`, `_c` suffixes; original preserved with its failed output

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

### Template

```python
Agent({
    description: "[3-5 word summary]",
    prompt: """
**SUBAGENT CONTEXT:** You are a subagent invoked by the DAAF Orchestrator via the Agent tool. You are NOT interacting with a human user. Do not invoke the `daaf-orchestrator` skill.

## AGENT PROTOCOL
Follow the protocol in `{BASE_DIR}/agents/[agent-name].md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name '[skill-name]'.

## CONTEXT FROM PLAN
[Paste relevant Plan section - Context Completeness Checklist always takes priority over brevity]

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
Closely read `{BASE_DIR}/agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

## OUTPUT FORMAT

**Hard cap: 1000 words maximum.** The orchestrator has limited context — every word you return consumes shared capacity across the entire pipeline. Your Agent output is a *signal to the orchestrator*, not an archive. The script files on disk are the archive.

**Do NOT include in your output:**
- Raw execution logs or captured stdout/stderr (already appended to the script file by `run_with_capture.sh`)
- Data samples, row-level examples, or Polars/pandas table displays
- Full checkpoint output (summarize as PASSED/FAILED/WARNING + 1-line reason)
- QA script code or contents (reference by file path instead)

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

**User-Facing Summary:** [For phase-ending tasks only: 5-8 sentence summary for inclusion in the Phase Status Update. Write for a research professional audience. Omit this field for mid-phase tasks.]

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

## Prompt Size Targets by Subagent Type

| Subagent Type | Target Prompt Size | Typical Context from Plan |
|---------------|-------------------|--------------------------|
| Plan | ~500 words | ~200 words |
| general-purpose | ~1000 words | ~500 words |

These are efficiency TARGETS for typical tasks, not hard ceilings that override the Context Completeness Checklist (CLAUDE.md). If a task's checklist requires more context to meet all REQUIRED items, provide it — completeness beats brevity. An incomplete prompt wastes MORE tokens (subagent confusion, re-invocation, wasted output) than a thorough one.

**If context needs consistently exceed these targets:** Consider whether the task should be broken into smaller subtasks with more focused scope.

---

## Context Inlining Protocol

### Principle: Inline Critical Context Directly

**Rule:** When dispatching an Agent, inline critical context directly in the prompt. Don't rely on subagent file reads for essential information.

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
Agent({
    description: "Stage [N]: [Name]",
    prompt: """**SUBAGENT CONTEXT:** You are a subagent invoked by the DAAF Orchestrator via the Agent tool. You are NOT interacting with a human user. Do not invoke the `daaf-orchestrator` skill.

## AGENT PROTOCOL
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

See "Prompt Size Targets by Subagent Type" table above for size targets. The same targets apply to inlined content, but the Context Completeness Checklist always takes priority over brevity.

**If context needs consistently exceed targets:** Consider breaking the task into smaller subtasks, each with more focused scope.

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

See daaf-orchestrator SKILL.md "Subagent Type Selection" for capabilities by type (`Plan` = read-only; `general-purpose` = full capabilities including file writes).

### Standard Invocation Pattern

```python
Agent({
    description: "Stage [N]: [Name]",
    prompt: """**SUBAGENT CONTEXT:** You are a subagent invoked by the DAAF Orchestrator via the Agent tool. You are NOT interacting with a human user. Do not invoke the `daaf-orchestrator` skill.

You have access to a skill tool. First, call the skill tool with name '[skill-name]'.

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

## Code-Reviewer Invocation (Cross-Phase QA)

### code-reviewer (QA Agent)

**Purpose:** Secondary QA review of executed scripts
**Stage:** 5-QA, 6-QA, 7-QA, 8-QA (after each script execution; Stage 8 uses QA4a for analysis, QA4b for visualization)
**Subagent:** general-purpose

**Invocation Timing:** After research-executor completes each script (after CP validation passes).

```python
Agent({
    description: "QA Review: Stage {N} Step {step} - {task_name}",
    prompt: """**SUBAGENT CONTEXT:** You are a subagent invoked by the DAAF Orchestrator via the Agent tool. You are NOT interacting with a human user. Do not invoke the `daaf-orchestrator` skill.

You are a Code Reviewer. Follow the protocol in `{BASE_DIR}/agents/code-reviewer.md`.

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
| Critical columns | {column_list} | Plan Research Outcomes |
| Max acceptable loss | {loss_pct}% | Plan Risk Register |
| Join cardinality | {cardinality_or_NA} | Plan (if join task) |

## RISK REGISTER ITEMS FOR THIS STAGE

| Risk | Mitigation | Watch For |
|------|------------|-----------|
| {risk_1} | {mitigation_1} | {symptom_1} |

## RESEARCH OUTCOME CONTRIBUTION

This task contributes to: "{research_outcome_text}"
Addressed when: {verification_condition}

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

**OUTPUT FORMAT (1000-word hard cap):**
Return findings in this structure. Do NOT paste QA script code, raw execution logs, or data samples — reference cr/ script paths instead.

### QA Review: {task_name}

**QA Status:** [PASSED | ISSUES_FOUND]
**Severity:** [BLOCKER | WARNING | INFO | None]
**Script Reviewed:** scripts/stage{N}_{type}/{step}_{task-name}.py
**QA Scripts Created:** scripts/cr/stage{N}_{step}_cr1.py [+ cr2..cr5 if created]

**Code Review:**
| Check | Status | Notes |
|-------|--------|-------|
| Operations match intent | PASS/FAIL | [1 sentence] |
| Methodology alignment | PASS/FAIL | [1 sentence] |
| Validation robustness | PASS/FAIL | [1 sentence] |

**QA Script Results:**
[1-2 sentence summary per cr script — PASSED/FAILED + key finding. Do NOT paste raw output.]

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
Agent({
    description: "Revision: Stage {N} Step {step} - {task_name}",
    prompt: """**SUBAGENT CONTEXT:** You are a subagent invoked by the DAAF Orchestrator via the Agent tool. You are NOT interacting with a human user. Do not invoke the `daaf-orchestrator` skill.

You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

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
Agent({
    description: "Stage [N] - Retry",
    prompt: """**SUBAGENT CONTEXT:** You are a subagent invoked by the DAAF Orchestrator via the Agent tool. You are NOT interacting with a human user. Do not invoke the `daaf-orchestrator` skill.

Previous attempt encountered: {error_description}

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

## Learning Signal Protocol

### Purpose

Every analysis produces learning opportunities beyond its immediate findings:
- Data download behaviors not documented elsewhere
- Data quality patterns
- Methodology insights
- Performance optimizations
- Common pitfalls to avoid

Capturing these lessons prevents repeated mistakes and accelerates future analyses. **Equally important:** incorporating and formalizing prior learnings ensures we don't repeat past mistakes.

### Learning Signal Format

Agents (research-executor, code-reviewer, debugger) include a lightweight Learning Signal field in their output:

```
**Learning Signal:** [Category: Access|Data|Method|Perf|Process] — [One-line insight] | or "None"
```

**Examples:**
- `**Learning Signal:** CCD enrollment value codes were not as expected in the codebook; codes needed to be explicitly examined for progress to continue`
- `**Learning Signal:** Data — MEPS poverty rates have 15% suppression in rural counties (higher than Plan estimate of 5%)`
- `**Learning Signal:** None`

### Accumulation Flow

```
Agent returns with Learning Signal
     ↓
Orchestrator extracts signal (if not "None")
     ↓
Orchestrator appends to STATE.md "Pending Learning Signals" buffer
     ↓
At next flush trigger → orchestrator appends buffered signals to LEARNINGS.md
     ↓
Clear STATE.md buffer
```

### Flush Triggers

The orchestrator writes buffered signals to LEARNINGS.md at these points:

1. **Phase boundary** — end of Phase 1 (after Stage 3/3.5), Phase 2 (after Stage 4.5), Phase 3 (after Stage 6-QA), Phase 4 (after Stage 10 — QA Aggregation)
2. **After blocker resolution** — a resolved BLOCKER often yields the richest learnings
3. **After debugging session** — debugger agent's Prevention section feeds learnings directly
4. **At utilization gates** (40%, 60%) — ensures learnings are persisted before potential session end

*Not* at every stage transition or every subagent return — that would be too frequent and disruptive.

### Flush Operation

What the orchestrator does at each flush:

1. Read pending signals from STATE.md buffer
2. Categorize each signal into the appropriate LEARNINGS.md section (Access/Data Gotchas, What Worked Well, Surprises, etc.)
3. Append as a quick-capture entry with stage number and timestamp
4. Clear the STATE.md buffer
5. This should take ~1 minute of orchestrator time, not a subagent invocation

Stage-specific creation triggers (Stage 4 skeleton creation) and consolidation steps (Stage 12) live in their respective phase files (`WORKFLOW_PHASE2_PLANNING.md` and `WORKFLOW_PHASE5_SYNTHESIS.md`). See `WORKFLOW_PHASE5_SYNTHESIS.md` > "Lessons Learned Consolidation" for the LEARNINGS.md template and Stage 12 consolidation procedure.

---
