# Full Pipeline Mode

This reference is loaded after the orchestrator classifies a request as Full Pipeline mode and the user confirms. It contains the complete 5-phase, 12-stage workflow, subagent coordination patterns, quality framework, and session management protocol.

**Path variables** (defined in core SKILL.md):
- **`{BASE_DIR}`** = project root (where `CLAUDE.md` resides)
- **`{SKILL_REFS}`** = `{BASE_DIR}/.claude/skills/daaf-orchestrator/references`

> **Domain Extensibility:** This workflow is domain-agnostic. Skill names referenced below (e.g., `education-data-explorer`, `education-data-query`, `education-data-context`) are the demonstration domain defaults. The orchestrator resolves actual skill names from the Plan's Domain Configuration section and provides them in Agent prompts. New domains can be added by authoring domain-specific Skills and registering them in the Plan's Domain Configuration.

> **Invocation Pattern Authority:** Three layers, from most to least specific:
> 1. **`WORKFLOW_PHASE*.md`** — stage-specific invocation templates with full context fields, thoroughness directives, and gate criteria. **Start here** when constructing a subagent prompt.
> 2. **`agents/README.md`** — canonical generic templates for each agent. The PHASE files build on these; consult README when a PHASE file doesn't cover a particular agent or for the baseline pattern.
> 3. **This file (`full-pipeline.md`)** — orchestrator-level guidance: prompt structure, context inlining protocol, QA enforcement, and prompt size targets.

> **Parallel Dispatch Limit:** The orchestrator MUST NOT dispatch more than **5 subagents concurrently** — this applies to wave-based task dispatch, Stage 3 source-researcher dispatch, and any other parallel invocation. If more than 5 independent tasks need to run, sub-batch into groups of ≤5 and wait for each sub-batch to complete before dispatching the next. Parallel dispatch is achieved by making multiple Agent tool calls in a **single response message** (foreground parallel). **NEVER use `run_in_background`** — background agents cannot prompt for permissions and will silently fail.

---

## Pre-Flight Checklist

**REQUIRED:** Before proceeding past Stage 1 in Full Pipeline mode, include the following in the initial confirmation of engagement mode with user:

```
**Full Pipeline Analysis: Pre-Flight Check**

This analysis will create:
- [ ] Research Plan document summarizing all key goals, considerations, decisions, risks, interpretations, work stage summaries, and final work review notes
- [ ] STATE.md session state file (for progress tracking and session recovery)
- [ ] Comprehensive analytic scripts covering data fetch, clean, join, transformation, analysis, and QA for all of the above
- [ ] Validated datasets (raw + processed)
- [ ] Marimo notebook "walkthrough" of successfully completed analysis scripts and their execution runtime logs for inspection
- [ ] Statistical analysis results (saved to output/analysis/)
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

You MUST wait until the user has provided confirmation to begin the next steps. Do NOT immediately proceed.

See `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md` (Stage 1) for complete Pre-Flight Checklist.

---

## Critical Warning: Custom Planning Workflow

> **DO NOT use Claude Code's built-in `EnterPlanMode` tool for this workflow.**
>
> This research system has its own planning protocol that is DIFFERENT from Claude Code's native Plan Mode:
>
> | Aspect | Claude Code Plan Mode | This Workflow |
> |--------|----------------------|---------------|
> | **Plan Creation** | `EnterPlanMode` tool | Stage 4 + `data-planner` agent + `PLAN_TEMPLATE.md` |
> | **Validation** | User clicks "approve" | Stage 4.5 + `plan-checker` agent (automated) |
> | **Gate** | `ExitPlanMode` | Gate G4.5 (plan-checker PASSED) |
>
> **Why this matters:** The built-in Plan Mode has different semantics and will bypass the plan-checker validation gate (G4.5). Always use the custom workflow defined in this file.

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

> Quick reference for prompt construction. See "Core Workflow Overview" below for execution details and gate criteria.

---

## Core Workflow Overview

The Full Pipeline workflow consists of **5 Phases** and **12 Stages**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DISCOVERY & SCOPING                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 1: Initial Intake                                                    │
│      ├─ Classify engagement mode                                            │
│      ├─ Ask clarifying questions (if needed)                                │
│      ├─ Output: Research question + scope confirmed                         │
│      └─ Gate G1: Mode classified, scope confirmed                           │
│                          ↓                                                  │
│  Stage 2: Data Exploration ←── domain explorer skill                        │
│      ├─ Identify available endpoints and variables                          │
│      ├─ Report findings to user (adaptive)                                  │
│      └─ Gate G2: ≥1 endpoint identified, key variables flagged              │
│                          ↓                                                  │
│  Stage 3: Source Deep-Dive ←── domain source skills                         │
│      ├─ Understand limitations, caveats, suppression patterns               │
│      ├─ Document source-specific gotchas                                    │
│      └─ Gate G3: Coded values documented, suppression patterns identified   │
│                          ↓                                                  │
│  Stage 3.5: Findings Synthesis ←── research-synthesizer agent               │
│      ├─ Consolidate parallel Stage 2-3 findings                             │
│      ├─ Resolve cross-source conflicts                                      │
│      └─ Gate G3.5: Synthesis complete, unified guidance for Plan            │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────────────┐
            │  ★ PSU1: Phase Status Update 1  │
            │  Present findings, await user   │
            │  confirmation before planning   │
            └─────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: PLANNING                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 4: Plan Document Creation                                            │
│      ├─ Synthesize Phase 1 findings                                         │
│      ├─ Document methodology decisions                                      │
│      ├─ Create project folder + Plan.md                                     │
│      ├─ **CRITICAL:** Complete Transformation Sequence table                │
│      ├─ Create STATE.md with Plan Validation section (initially NOT_RUN)    │
│      ├─ Create LEARNINGS.md skeleton (project metadata + empty sections)    │
│      ├─ **WARNING:** DO NOT use Claude Code's EnterPlanMode tool here!      │
│      │   Use data-planner agent + PLAN_TEMPLATE.md instead.                 │
│      ├─ Report to user: "Plan created, invoking plan-checker..."            │
│      └─ Gate G4: Plan + STATE.md + LEARNINGS.md created                     │
│                          ↓                                                  │
│  Stage 4.5: Plan Validation ←── plan-checker agent                          │
│      ├─ Automated 6-dimension plan validation                               │
│      └─ Gate G4.5: plan-checker PASSED or PASSED_WITH_WARNINGS              │
│                                                                             │
│  **Transformation Sequence:** This table is REQUIRED and serves as the      │
│  contract between orchestrator and subagents during Stage 7. Each row       │
│  becomes a separate subagent invocation. Incomplete sequences lead to       │
│  incomplete validation and unreliable results.                              │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────────────┐
            │  ★ PSU2: Phase Status Update 2  │
            │  Present Plan for user review,  │
            │  await confirmation before      │
            │  data acquisition               │
            └─────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: DATA ACQUISITION & PREPARATION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─ STAGE 5 PRE-FLIGHT CHECK (MANDATORY) ─────────────────────────────────┐ │
│  │  Before executing ANY Stage 5 task, verify:                            │ │
│  │  □ Plan exists at expected path                                        │ │
│  │  □ STATE.md exists                                                     │ │
│  │  □ STATE.md "Plan Validation" section shows:                           │ │
│  │    - Plan-Checker Status: PASSED or PASSED_WITH_WARNINGS               │ │
│  │    - Gate G4.5 Status: SATISFIED                                       │ │
│  │  □ If Plan-Checker Status is NOT_RUN → STOP, invoke plan-checker first │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Stage 5: Data Retrieval ←── domain query skill                             │
│      ├─ Download from configured mirrors (per mirrors.yaml)                 │
│      ├─ Auto-validate: shape, types, missingness (CP1)                      │
│      ├─ STOP if: unexpected empty results, data access errors               │
│      ├─ [Per-script QA loop — see Composite Execution Pattern below]        │
│      └─ Gate G5: CP1 PASSED, QA1 PASSED/WARNING, data in data/raw/         │
│                          ↓                                                  │
│  Stage 6: Context Application ←── domain context skill                      │
│      ├─ Assess missingness and coded value presence                         │
│      ├─ Calculate suppression rates (CP2)                                   │
│      ├─ STOP if: >50% suppression, invalid analysis type                    │
│      ├─ [Per-script QA loop — see Composite Execution Pattern below]        │
│      └─ Gate G6: CP2 PASSED, QA2 PASSED/WARNING, data in processed/        │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────────────┐
            │  ★ PSU3: Phase Status Update 3  │
            │  Present data quality metrics,  │
            │  await confirmation before      │
            │  analysis                       │
            └─────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: ANALYSIS & NOTEBOOK DEVELOPMENT                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 7: EDA & Transformation ←── data-scientist + polars skills           │
│      ├─ Initial data profiling (auto-execute)                               │
│      ├─ Report key findings to user (adaptive)                              │
│      ├─ Transformations with validation (CP3 per transformation)            │
│      ├─ [Per-script QA loop — see Composite Execution Pattern below]        │
│      └─ Gate G7: All CP3 PASSED, all QA3 PASSED/WARNING                     │
│                          ↓                                                  │
│  Stage 8: Analysis & Visualization                                          │
│      ├─ 8.1: Run statistical analyses (save to output/analysis/)            │
│      │   └─ [Per-script QA loop (QA4a) — see Composite Execution Pattern]   │
│      ├─ 8.2: Generate exploratory and final plots (save to output/figures/) │
│      │   └─ [Per-script QA loop (QA4b) — see Composite Execution Pattern]   │
│      └─ Gate G8: Analyses + viz complete, QA4a AND QA4b PASSED/WARNING      │
│                          ↓                                                  │
│  Stage 9: Script Compilation ←── notebook-assembler agent                   │
│      ├─ LITERALLY COPY script file contents into marimo cells               │
│      ├─ VERBATIM execution logs in accordions (not summaries)               │
│      ├─ NO new code except pl.read_parquet() + mo.ui.table()                │
│      ├─ NO dashboards, NO widgets, NO filters, NO aggregations              │
│      └─ Gate G9: Notebook runs, all scripts represented, no prohibited items│
│                          ↓                                                  │
│  Stage 10: QA Aggregation                                                   │
│      ├─ **Aggregate QA findings from Stages 5-8 (WARNINGs reviewed)**       │
│      ├─ Review accumulated WARNINGs, confirm no unresolved BLOCKERs         │
│      ├─ STOP if: unresolved BLOCKERs or systemic WARNING patterns           │
│      └─ Gate G10: QA aggregated, BLOCKERs resolved, WARNINGs documented     │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────────────┐
            │  ★ PSU4: Phase Status Update 4  │
            │  Present analysis results and   │
            │  QA aggregation, await user     │
            │  confirmation before synthesis  │
            └─────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: SYNTHESIS & DELIVERY                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage 11: Report Generation ←── report-writer agent                        │
│      ├─ Synthesize Plan, Notebook, STATE, LEARNINGS, QA summary             │
│      ├─ Follow Section-Source Mapping for each REPORT_TEMPLATE.md section   │
│      ├─ Cross-check Research Outcomes against Key Findings                  │
│      └─ Gate G11: Report complete with all sections + figure references     │
│                          ↓                                                  │
│  Stage 12: Final Review                                                     │
│      ├─ Verify alignment with original request                              │
│      ├─ Check all Plan commitments fulfilled                                │
│      ├─ Document any deviations                                             │
│      ├─ Update Plan with Final Review Log                                   │
│      ├─ **Consolidate LEARNINGS.md (review incremental entries, fill gaps)**│
│      ├─ **Generate System Update Action Plan section in LEARNINGS.md**      │
│      └─ Gate G12: Final review passed, all commitments fulfilled            │
│                          ↓                                                  │
│  DELIVERY: Summary to user with file paths                                  │
│      + Learnings summary (key insights + action plan item count)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **AUTHORITATIVE EXECUTION LOOP:** The per-script QA loop referenced in each stage above is defined in full detail in the **Stage 5-8 Composite Execution Pattern** section below. That pattern is the MANDATORY atomic unit for all Stage 5-8 work. The workflow diagram above is a visual summary; the Composite Pattern is the binding specification.

---

## Stage 5-8 Per-Script Execution & QA Loop

**Every stage from 5 through 8 is executed as MULTIPLE subagent calls with interleaved QA, NOT as a single invocation per stage.** Each script in the Plan's Transformation Sequence table is executed by research-executor, then **immediately and separately** reviewed by code-reviewer, before the next script begins. This applies equally to Stage 5 (fetch scripts), Stage 6 (clean scripts), Stage 7 (transformation scripts), and Stage 8 (analysis and visualization scripts). Any Stage writing net new code must adhere to this. QA scripts are saved to `scripts/cr/stage{N}_{step}_cr{1..5}.py`. The **Stage 5-8 Composite Execution Pattern** below defines the authoritative execution flow — it is the MANDATORY atomic unit for all Stage 5-8 work. See `agents/code-reviewer.md` for the complete QA protocol and `agent_reference/QA_CHECKPOINTS.md` for checkpoint definitions.

**Why this matters:**
- The core principle "Every transformation has a validation" requires separate execution cycles
- Each subagent call captures pre-state, executes ONE script, validates post-state
- QA must run immediately after each script so findings can inform whether to proceed, revise, or stop
- Batching QA to stage end means errors in script 1 propagate silently through scripts 2, 3, 4 — compounding data corruption
- The Transformation Sequence table in the Plan is the contract for these invocations

**See:** the appropriate `agent_reference/WORKFLOW_PHASE*.md` file for detailed per-script execution guidance.

### QA Invocation Responsibility

**Expectation for QA depth:** The code-reviewer is not a rubber-stamp. The reviewer should reason adversarially about the script, not merely run templated checks. A high-quality QA report includes reasoning about *why* the code is correct, not just confirmation that checks passed. If a code-reviewer returns PASSED with only template-level checks and no script-specific observations, consider whether the review was thorough enough.

The complete QA invocation workflow is defined in the **Stage 5-8 Composite Execution Pattern** below. See `agents/code-reviewer.md` for the QA protocol and `agent_reference/QA_CHECKPOINTS.md` for checkpoint definitions.

### Stage 5-8 Composite Execution Pattern (MANDATORY)

For EACH task in Stages 5-8, follow this complete loop. **Do NOT skip any step.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: INVOKE research-executor                                           │
│      ├─ Use stage-specific template from the appropriate WORKFLOW_PHASE*.md  │
│      ├─ Capture from result: script_path, output_files, CP_status           │
│      └─ If CP_status == FAILED → Handle error, do not proceed to QA         │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 2: INVOKE code-reviewer (MANDATORY - DO NOT SKIP)                     │
│      │                                                                      │
│      │   Use the code-reviewer invocation template from the                  │
│      │   "Code-Reviewer Invocation" section below, with stage-specific      │
│      │   values.                                                            │
│      │                                                                      │
│      │   **Review Expectation:** code-reviewer should perform adversarial   │
│      │   analysis, not just template validation. Expect the QA report to    │
│      │   include script-specific checks and reasoning about WHY the code    │
│      │   is correct, not merely confirmation that checks passed.            │
│      │                                                                      │
│      └─ WAIT for code-reviewer to return before proceeding                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 3: EVALUATE QA severity                                               │
│      ├─ PASSED → Log to STATE.md, proceed to next task                      │
│      ├─ WARNING → Log to STATE.md (for Stage 10 review), proceed            │
│      └─ BLOCKER → Go to STEP 4                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 4: REVISION FLOW (if BLOCKER)                                         │
│      ├─ Invoke research-executor to create revised script (_a.py)           │
│      ├─ Re-invoke code-reviewer on revised script                           │
│      ├─ If still BLOCKER → Create _b.py revision, re-invoke code-reviewer   │
│      └─ If still BLOCKER after 2 revisions → STOP and escalate to user      │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 5: UPDATE STATE.md                                                    │
│      ├─ Update Transformation Progress table                                │
│      ├─ Record QA status and any findings                                   │
│      └─ Proceed to next task in wave                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CRITICAL:** Steps 1-5 form an atomic unit. NEVER proceed to the next task without completing all steps. NEVER batch multiple executor calls without intermediate QA.

---

## Code Preview Protocol

**When delegating complex transformations to subagents, use iterative code preview:**

### For Complex Transformations (joins, aggregations, multi-step operations)

**Step 1: Request Code Generation (without execution)**

Invoke a subagent to generate the transformation code but explicitly instruct it not to execute:

```python
Agent({
    description: "Generate transformation code",
    prompt: """You are a Research Executor. Follow the protocol in {BASE_DIR}/agents/research-executor.md.

Generate code for: {transformation_description}

**DO NOT execute the code yet.** Return only:
1. Proposed code with comments
2. Expected outcome (shape, key changes)
3. Validation approach

Format:
# Proposed code here

Expected: {outcome}
Validation: {approach}
"""
})
```

**Step 2: Review Code**
- Orchestrator reviews proposed approach
- Checks for alignment with Plan
- Verifies validation approach is adequate

**Step 3: Execute with Validation**

Invoke a subagent to execute the approved code with full validation:

```python
Agent({
    description: "Execute validated transformation",
    prompt: """You are a Research Executor. Follow the protocol in {BASE_DIR}/agents/research-executor.md.

Execute the following approved code:

{approved_code}

Use the Iteration Protocol:
1. Capture pre-state
2. Execute transformation
3. Validate results
4. Report PASS/FAIL status
"""
})
```

### Exception: Direct Execution Allowed

These operations may be executed without preview:
- Data loading (read_csv, read_parquet)
- Basic inspection (shape, head, describe, sample)
- Column selection

**All other transformations require the preview-execute pattern.**

---

## Phase-to-Protocol Mapping

| Phase | Primary Protocol | Also Applies | PSU at Boundary | Reference |
|-------|------------------|--------------|-----------------|-----------|
| Phase 1 | Data Discovery | — | PSU1 (after Phase 1) | `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md` |
| Phase 2 | Plan Management | — | PSU2 (after Phase 2) | `agent_reference/WORKFLOW_PHASE2_PLANNING.md` |
| Phase 3 | Data Acquisition | Validation (CP1-CP2) | PSU3 (after Phase 3) | `agent_reference/WORKFLOW_PHASE3_ACQUISITION.md` |
| Phase 4 | Validation Checkpoints | Plan Management (updates) | PSU4 (after Phase 4) | `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` |
| Phase 5 | Synthesis & Delivery | Stages 11-12 | Final Review | `agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md` |

**Note:** Session Recovery is documented in `{SKILL_REFS}/session-recovery.md`.

**Cross-Phase Concerns:**
- **Validation Checkpoints** apply across Phases 3-5 with different checkpoints:
  - Phase 3: CP1 (after fetch), CP2 (after cleaning)
  - Phase 4: CP3 (after transformation)
  - Phase 5: CP4 (before final output, during Stages 11-12)
- **QA Checkpoints (QA1-QA4b)** run in parallel as secondary validation during Phases 3-4
- **Plan Document Maintenance** — Plan is created in Phase 2 but updated throughout Phases 3-5

## Skill-to-Stage Mapping

| Stage | Primary Skill(s) | Subagent Type | Invocation Pattern |
|-------|------------------|---------------|-------------------|
| 2 | `data-scientist`, domain explorer skill | Plan | Subagent invokes skill |
| 3 | `data-scientist`, domain source skill(s) | Plan | Subagent invokes skill(s) |
| 3.5 | `data-scientist` | general-purpose | `research-synthesizer` agent |
| 4 | `data-scientist` | general-purpose | `data-planner` agent |
| 4.5 | `data-scientist` | Plan | `plan-checker` agent |
| 5 | `data-scientist`, domain query skill | general-purpose | Subagent invokes skill |
| **5-QA** | `data-scientist` | general-purpose | `code-reviewer` agent (after each Stage 5 script) |
| 6 | `data-scientist`, domain context skill | general-purpose | Subagent invokes skill |
| **6-QA** | `data-scientist` | general-purpose | `code-reviewer` agent (after each Stage 6 script) |
| 7 | `data-scientist`, `polars` | general-purpose | Subagent invokes skills |
| **7-QA** | `data-scientist` | general-purpose | `code-reviewer` agent (after each Stage 7 script) |
| 8 | `data-scientist`, `polars`, `plotnine`, `plotly` | general-purpose | Subagent invokes skill |
| **8-QA** | `data-scientist` | general-purpose | `code-reviewer` agent (after each Stage 8 script) |
| 9 | `marimo` | general-purpose | `notebook-assembler` agent (COMPILES scripts — NO new code, NO dashboards) |
| 10 | — | — | Orchestrator aggregates QA findings (no subagent) |
| 11 | `data-scientist` | general-purpose | `report-writer` agent |
| 12 | `data-scientist` | Plan | `data-verifier` agent |

**Notes:**
- Stages 5 and 6 use `general-purpose` subagent type because they require file write capability (saving parquet files to `data/raw/` and `data/processed/`).
- **Stage 4 responsibility split:** The `data-planner` agent creates the Plan document only. The **orchestrator** is responsible for creating STATE.md (from `agent_reference/STATE_TEMPLATE.md`) and the LEARNINGS.md skeleton (from `agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md`) after the data-planner returns. Gate G4 requires all three files.
- **Stage 10** has no dedicated agent — the orchestrator performs QA aggregation directly by reviewing accumulated code-reviewer findings from Stages 5-8.

**Stage 10 Protocol:** Read STATE.md's Transformation Progress table as the sole input. For each script: (1) Check QA status (PASS / PASS_WITH_WARNINGS / N/A), (2) Aggregate WARNING items into a summary, (3) Verify no unresolved BLOCKERs exist, (4) Compose QA Aggregation Summary for PSU4. Do NOT re-read individual QA scripts — STATE.md already tracks all QA outcomes.
- **QA substages** (5-QA through 8-QA) run code-reviewer after each script execution in the parent stage.
- The `Plan` type is read-only and cannot write files.
- All Stages 5-8 scripts must follow IAT documentation standards (`agent_reference/INLINE_AUDIT_TRAIL.md`).

**Note:** Stages 2, 3, 5, and 6 use domain-specific skills resolved by the orchestrator based on the active domain configuration in the Plan.

---

## Orchestrator Responsibilities

As the orchestrator, you maintain overall context and coordinate subagent execution.

### What Stays in Main Context

- Original user request and clarifications
- Mode classification and scope decisions
- High-level findings from each phase (summaries, not raw data)
- Plan document location and status
- Current stage and progress
- Errors and blockers requiring escalation

### What Gets Delegated to Subagents

- Detailed data exploration (skill invocations)
- Source-specific deep dives
- Code-heavy analysis work
- Visualization generation
- **QA code review (code-reviewer agent invoked to closely inspect each individual Stage 5-8 script)**
- Final report writing and review

### Task Types

See the "Task Types" section below for the complete taxonomy, behavioral descriptions, and the Task Specificity Test.

### Context Completeness Checklist (MANDATORY)

> For context-field-to-source mapping tables, see the "Context Passing Requirements by Stage Transition" section below.

**Before invoking ANY Stage 5-8 subagent, verify context is complete.** Incomplete context causes subagent confusion, wasted tokens, and incorrect results.

**Stage 5 (Fetch) Checklist:**
- [ ] Script target path specified (absolute, following naming convention)
- [ ] Plan path specified or relevant Plan sections inlined
- [ ] Research question inlined
- [ ] Years specified (exact range, not "recent years")
- [ ] Geographic scope specified (state, national, etc.)
- [ ] Filters specified (exact conditions)
- [ ] Expected row count range and critical columns specified
- [ ] Output file paths specified (not placeholder)
- [ ] Missingness and coded value expectations mentioned
- [ ] Risk Register items for fetch included (from Plan)
- [ ] Domain query skill specified
- [ ] Script follows IAT documentation standards

**Stage 6 (Clean) Checklist:**
- [ ] Script target path specified (absolute, following naming convention)
- [ ] Plan path specified or relevant Plan sections inlined
- [ ] Research question inlined
- [ ] Raw data location specified (exact path from Stage 5 output)
- [ ] Source caveats from Stage 3 inlined (not just referenced)
- [ ] Coded value handling specification provided
- [ ] Suppression tolerance thresholds specified
- [ ] Expected row count range and critical columns identified (from Plan Research Outcomes)
- [ ] Output file paths specified (not placeholder)
- [ ] Risk Register items for cleaning included
- [ ] Domain context skill specified (or N/A)
- [ ] Script follows IAT documentation standards

**Stage 7 (Transform) Checklist:**
- [ ] Script target path specified (absolute, following naming convention)
- [ ] Plan path specified or relevant Plan sections inlined
- [ ] Research question inlined
- [ ] Input file paths specified (absolute, from prior stage outputs)
- [ ] Output file paths specified (absolute, per Plan)
- [ ] Prior transformation context inlined (EDA findings, prior transform results)
- [ ] Invariants to maintain listed (from prior transformations)
- [ ] Transformation specification complete (exact columns, exact conditions)
- [ ] Expected outcome specified (row count, shape)
- [ ] Join cardinality specified (if join task)
- [ ] Risk Register items included
- [ ] Research Outcome contribution stated
- [ ] Skill(s) to load specified
- [ ] Script follows IAT documentation standards

**Code-Reviewer (QA) Checklist:**
- [ ] Script path specified (exact path)
- [ ] Plan expectations INLINED (not just path) — row counts, tolerances, critical columns
- [ ] QA tolerance thresholds specified (BLOCKER if, WARNING if)
- [ ] Risk Register items included
- [ ] Research Outcome contribution stated
- [ ] Prior QA findings accumulated (if any WARNING items from prior scripts)
- [ ] Coded values from Plan inlined
- [ ] IAT compliance expectations stated

**Stage 8.1 (Analysis) Checklist:**
- [ ] Script target path specified (absolute, following naming convention)
- [ ] Plan path specified or relevant Plan sections inlined
- [ ] Research question inlined
- [ ] Analysis dataset path specified (exact path from Stage 7 output)
- [ ] Statistical method specified (regression, summary stats, comparison, etc.)
- [ ] Dependent and independent variables identified
- [ ] Grouping/stratification variables specified (if applicable)
- [ ] Expected output format specified (summary table, model results, etc.)
- [ ] Output file path specified (`output/analysis/[date]_[description].parquet`)
- [ ] Significance thresholds or interpretation guidelines provided
- [ ] Research Outcome contribution stated
- [ ] Risk Register items included
- [ ] Skill(s) to load specified
- [ ] Script follows IAT documentation standards

**Stage 8.2 (Visualization) Checklist:**
- [ ] Script target path specified (absolute, following naming convention)
- [ ] Plan path specified or relevant Plan sections inlined
- [ ] Research question inlined
- [ ] Analysis dataset and/or analysis results paths specified
- [ ] Figure specification provided (chart type, variables, grouping)
- [ ] Output file path specified (`output/figures/[date]_[description].png`)
- [ ] Labeling requirements stated (title, axes, legend, source note)
- [ ] Accessibility considerations noted (colorblind-safe palette, etc.)
- [ ] Research Outcome contribution stated
- [ ] Risk Register items included
- [ ] Skill(s) to load specified
- [ ] Script follows IAT documentation standards

**Revision Request Checklist (when re-invoking research-executor after QA BLOCKER):**
- [ ] Original script path specified (absolute)
- [ ] Current final version path specified (absolute)
- [ ] QA report with BLOCKER details inlined
- [ ] Suggested fix from code-reviewer included
- [ ] Plan path specified or relevant Plan sections inlined

**If any checklist item is unchecked:** Add the missing context before invoking. Incomplete context = subagent asks clarifying questions = wasted round-trip.

These checklists correspond to the input requirements defined in each agent's definition file (e.g., `agents/research-executor.md` > Inputs).

### Progress Reporting Protocol

Report to the user **adaptively** at these trigger points:

| Trigger | Report Content |
|---------|----------------|
| Phase completion | Summary of phase outcomes, any issues encountered |
| Phase boundary | **Phase Status Update (PSU) — MANDATORY. Present comprehensive PSU and WAIT for user confirmation. See Phase Status Updates section.** |
| Notable finding | Surprising data insight, limitation discovered |
| Decision point | Methodology choice with rationale |
| Error/blocker | Issue description, attempted resolution, escalation if needed |
| STOP condition hit | Clear explanation of why execution paused |

**Report Format:**
```
**Progress Update: [Phase/Stage]**
- Completed: [What was done]
- Key Findings: [Notable insights or issues]
- Next Steps: [What happens next]
- [If applicable] Action Needed: [What user input is required]
```

**Note:** Progress reports during a phase are one-way informational updates. Phase Status Updates at phase boundaries are BLOCKING — the orchestrator must wait for user confirmation before proceeding.

### Phase Status Updates (Mandatory)

**Phase Status Updates (PSU) are enforced pause points at every phase boundary.** After completing a phase, the orchestrator MUST present a comprehensive Phase Status Update to the user and WAIT for explicit confirmation before proceeding to the next phase.

**Cardinal Rule:** No phase transition occurs without user approval. The orchestrator presents, the user decides.

#### PSU Design Principles

1. **Blocking:** The orchestrator MUST wait for an explicit user response. Do NOT proceed automatically.
2. **Comprehensive:** Each PSU includes everything the user needs to make an informed go/no-go decision.
3. **Actionable:** Each PSU ends with explicit approval request and clear options for the user.
4. **Cumulative:** Later PSUs reference earlier ones, building a coherent narrative of the analysis.

#### PSU Schedule

| ID | Transition | After Stage | Before Stage | What User Reviews |
|---|---|---|---|---|
| PSU1 | Phase 1 → Phase 2 | 3.5 (Synthesis) | 4 (Plan Creation) | Discovery findings, data availability, source caveats, feasibility, recommended approach |
| PSU2 | Phase 2 → Phase 3 | 4.5 (Plan Validation) | 5 (Data Retrieval) | The Plan document — methodology, scope, task sequence, research outcomes, hypotheses (if any) |
| PSU3 | Phase 3 → Phase 4 | 6 (Context Application) | 7 (EDA & Transformation) | Data quality metrics, suppression rates, datasets acquired, QA1/QA2 summaries |
| PSU4 | Phase 4 → Phase 5 | 10 (QA Aggregation) | 11 (Report Generation) | Statistical results, key visualizations, QA aggregation, deviations from Plan |

#### PSU Template and Content Requirements

Every Phase Status Update MUST follow this format:

```
**Phase Status Update: Phase [N] Complete — [Phase Name]**

**Summary:**
[2-3 sentence overview of what was accomplished in this phase]

**Key Findings:**
- [Finding 1]
- [Finding 2]
- [Finding 3]

**Decisions Made:**
| Decision | Rationale | Impact |
|----------|-----------|--------|
| [decision] | [why] | [what it affects] |

**Warnings & Issues:**
| Item | Severity | Status | Details |
|------|----------|--------|---------|
| [item] | WARNING/INFO | Resolved/Open | [details] |

[If no warnings: "No warnings or issues encountered in this phase."]

**Artifacts Produced:**
- [File path 1]: [description]
- [File path 2]: [description]

**Next Phase Preview:**
Phase [N+1] ([Phase Name]) will [brief description of what comes next and what it involves].

**Please confirm you'd like to proceed to Phase [N+1], or let me know if you'd like me to revisit or adjust anything from Phase [N].**
```

##### PSU-Specific Content Requirements

**PSU1 (Discovery → Planning):**
- Data sources identified (with endpoints and year ranges)
- Key variables and their availability
- Source-specific caveats and limitations discovered
- Suppression patterns and cross-region comparability issues (e.g., cross-state for education)
- Feasibility assessment and recommended analytical approach
- Any LOW-confidence items requiring user input

**PSU2 (Planning → Data Acquisition):**
- Research question as stated in Plan
- Methodology summary (statistical approach, key decisions)
- Data sources and year ranges confirmed
- Transformation sequence overview (number of tasks, waves)
- Research Outcomes the analysis will investigate
- Hypotheses (if any) and their basis
- Risk Register highlights
- Plan-checker validation result (PASSED/PASSED_WITH_WARNINGS and any warnings)
- User informed of full Plan filepath and instructed to read it closely for their deep review

**PSU3 (Data Acquisition → Analysis):**
- Datasets acquired: source, shape, date range, file paths
- Data quality summary: missingness rates, suppression rates per dataset
- Cleaning actions taken and their impact (rows removed, values recoded)
- QA summary: QA1/QA2 results for each script (PASSED/WARNING with details)
- Any deviations from the Plan during fetch/clean
- Data readiness assessment for analysis phase

**PSU4 (Analysis → Synthesis):**
- Transformation summary: joins performed, derived variables, final analysis dataset shape
- Statistical analysis results: key findings with effect sizes and confidence intervals
- Key visualizations produced (reference file paths for user to inspect)
- QA summary: QA3/QA4a/QA4b results across all scripts
- Accumulated warnings from Stages 5-8 (the Stage 10 QA aggregation)
- Any deviations from Plan methodology
- Notebook compilation status

#### User Response Handling

At each PSU, the user may:
- **Approve** ("proceed", "looks good", "continue", etc.) → Proceed to next phase
- **Request revision** ("redo X", "fix Y", "I'm concerned about Z") → Orchestrator addresses within current phase, then re-presents PSU
- **Request scope change** ("can we also look at...", "let's narrow to...") → Triggers scope change protocol (Ask First), then revises as needed
- **Ask questions** ("what does X mean?", "why did you choose Y?") → Orchestrator answers, then re-presents approval request

**CRITICAL:** After answering questions or providing clarification, the orchestrator MUST re-present the approval request. Do not assume that a question implies approval.

### Plan Document Maintenance

The Plan document is your **persistent memory** across the workflow and the most important document for auditability, replicability, and rigor. Treat this as the highest of priorities at all times, being verbose as much as possible to prevent losing track of information or decisions crucial to the project, and to enforce clear communication with all subagents working in the project as well.

1. **Create** during Phase 2 (Stage 4)
2. **Update** as decisions are made and findings emerge
3. **Reference** when delegating to subagents (include relevant sections)
4. **Finalize** during Phase 5 with Final Review Log

See `agent_reference/PLAN_TEMPLATE.md` for the complete template.

The Plan document is the **single source of truth** for the analysis. It:
- Captures all decisions and their rationale
- Provides context for subagent invocations
- Enables session continuity (return to work later)
- Supports version control for revisions

**Completeness Standard:** The Plan must be comprehensive enough that any subagent can execute its stage with ONLY the Plan as context (plus skill knowledge).

### Plan Update Events

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

### Risk Register Updates

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

---

## Pipeline-Specific Subagent Patterns

These patterns supplement the Universal Prompt Requirements in `SKILL.md` and the invocation templates in the `agent_reference/WORKFLOW_PHASE*.md` files.

### Wave-Based Parallel Execution

Tasks in the Plan's transformation sequence have wave assignments:

```
Wave 1: [fetch-ccd, fetch-meps]     ← Run in parallel
Wave 2: [clean-ccd, clean-meps]     ← Depends on Wave 1
Wave 3: [join-data]                 ← Depends on Wave 2
```

**Execution Rules:**
- Same-wave tasks dispatch simultaneously by making multiple Agent tool calls in a **single response message** (foreground parallel). **NEVER use `run_in_background`** — background agents cannot prompt for permissions and will silently fail.
- If any parallel dispatch stage contains more than 5 tasks (e.g., Stage 3 source-researcher dispatch, any ad-hoc parallel exploration, and code-reviewer invocations), sub-batch into groups of ≤5 and wait for each sub-batch to complete before dispatching the next. NEVER dispatch more than 5 subagents concurrently.
- Each subagent gets fresh 200K-token context (no degradation)
- Later waves wait for ALL prior waves to complete
- Dependencies in `depends_on` must be satisfied

See `agent_reference/PLAN_TEMPLATE.md` for wave-based task table format.

### Thoroughness Directives by Stage

**Stage 2 (Data Exploration):**
- Search ALL relevant data levels (e.g., schools, districts, colleges for education)
- Consider multiple potential data sources
- Flag variables that need source-specific deep dives
- Include "Limitations Encountered" section

**Stage 3 (Source Deep-Dive):**
- Load the specific domain source skill for each source (per Plan domain config)
- Extract all relevant caveats and limitations
- Document suppression patterns and thresholds
- Note any cross-region comparability issues (e.g., cross-state comparability for education)

**Stage 3.5 (Findings Synthesis):**
- Consolidate all Stage 2 and Stage 3 findings into unified guidance
- Identify and resolve conflicts across multiple sources
- Assess join feasibility and data compatibility
- Document unified path forward for Plan creation

**Stage 5 (Data Retrieval):**
- Download from configured mirrors (per mirrors.yaml)
- Validate response shape immediately after fetch
- Save only parquet format
- Document which mirror was used

**Stage 6 (Context Application):**
- Assess missingness and filter coded values appropriately
- Calculate and report suppression rates
- BLOCK invalid analysis types (e.g., cross-state assessment comparison)
- Generate citation text

**Stage 7 (EDA & Transformation):**
- Verify all Transformation Sequence tasks are complete
- Follow data-scientist skill principles rigorously
- Validate before AND after every transformation
- Document any deviations from Plan in Plan document
- Document every methodological decision
- Report surprising findings to user

**Stage 8.1 (Statistical Analysis):**
- Select statistical methods appropriate to research question and data characteristics
- Validate assumptions before running analyses (normality, independence, sample size)
- Document all parameter choices and their rationale
- Save analysis results as parquet to `output/analysis/`
- Report key findings with effect sizes and confidence intervals where applicable

**Stage 8.2 (Visualization):**
- Generate both exploratory and publication-quality plots
- Use colorblind-safe palettes by default
- Include proper titles, axis labels, legends, and source notes
- Save to `output/figures/` in PNG format
- Ensure visualizations accurately represent the underlying data and analysis results

See the appropriate `agent_reference/WORKFLOW_PHASE*.md` file for complete invocation templates.

### Handoff Specifications

Each stage has explicit input/output contracts and gate criteria:

| Stage | Input From | Output To | Gate Criteria |
|-------|------------|-----------|---------------|
| 1 | User request | Stage 2 | G1: Mode classified, scope confirmed |
| 2 | Stage 1 (mode + scope) | Stage 3 | G2: ≥1 endpoint identified, key variables flagged |
| 3 | Stage 2 endpoints | Stage 3.5 | G3: All flagged variables investigated, coded values documented, suppression patterns identified |
| 3.5 | Stages 2, 3 | PSU1 to user, then Stage 4 | G3.5: Synthesis complete, conflicts resolved, user confirmed PSU1 |
| 4 | Phase 1 findings | Stage 4.5 | G4: Plan created, STATE.md created, LEARNINGS.md skeleton created |
| 4.5 | Stage 4 (Plan) | PSU2 to user, then Stage 5 | G4.5: Plan validation PASSED or PASSED_WITH_WARNINGS, user confirmed PSU2 |
| 5 | Plan (query spec) | Stage 6 | G5: CP1 PASSED per script, code-reviewer separately invoked per script immediately after completion, all QA1 ∈ {PASSED, WARNING}, data saved to data/raw/ |
| 6 | Stage 5 (raw data) | PSU3 to user, then Stage 7 | G6: CP2 PASSED per script, code-reviewer separately invoked per script immediately after completion, all QA2 ∈ {PASSED, WARNING}, suppression <50%, data saved to data/processed/, user confirmed PSU3 |
| 7 | Stage 6 (clean data) | Stage 8, 9 | G7: All transformations validated (CP3) per script, code-reviewer separately invoked per script immediately after completion, all QA3 ∈ {PASSED, WARNING}, analysis dataset saved to `data/processed/[date]_analysis.parquet` (at Stage 7.3) |
| 8 | Stage 7 (analysis data) | Stage 9, 11 | G8: Statistical results saved to output/analysis/, visualizations saved to output/figures/, code-reviewer separately invoked per 8.1 script (QA4a) and per 8.2 script (QA4b) immediately after each completes, all QA4a and QA4b ∈ {PASSED, WARNING} |
| 9 | Stages 7, 8 | Stage 10 | G9: Notebook runs without errors, all scripts represented with code + execution logs |
| 10 | Stage 9 (notebook) | PSU4 to user, then Stage 11 | G10: QA findings aggregated, all BLOCKERs resolved, all WARNINGs documented, user confirmed PSU4 |
| 11 | Stages 9, 10, Plan, STATE.md, LEARNINGS.md | Stage 12 | G11: report-writer returned COMPLETE or COMPLETE_WITH_GAPS, all REPORT_TEMPLATE.md sections populated, figure references verified |
| 12 | All prior stages | Delivery | G12: Final Review PASSED, all commitments fulfilled, LEARNINGS.md consolidated with System Update Action Plan, cross-artifact coherence verified |

**QA Gate Notes:**
- **PASSED or WARNING:** QA may log WARNINGs that don't block execution (documented for Stage 10 aggregation)
- **QA BLOCKER:** If QA returns BLOCKER, revision is required before handoff (max 2 attempts, then escalate)
- **QA findings aggregated:** Stage 10 consolidates all WARNINGs from Stages 5-8 for final review

### Subagent Output Verification Protocol

**CRITICAL:** Before integrating subagent findings into the Plan or proceeding to the next stage, verify that subagent output meets orchestrator expectations.

**Verification Checklist:**

| Check | What to Verify | Action if Failed |
|-------|----------------|------------------|
| **Size** | Output is under 1000 words | Extract only structured summary fields; discard verbose sections, raw logs, and data samples before integrating into context. If chronic, re-invoke with emphasis on the 1000-word hard cap. |
| **Completeness** | All required output sections present | Re-invoke with clarification |
| **Format** | Output matches specified OUTPUT FORMAT | Re-invoke with format emphasis |
| **Confidence** | No LOW confidence items without resolution | Request resolution or escalate |
| **Substantive** | Real findings, not template placeholders | Re-invoke with thoroughness emphasis |

**Verification Procedure:**

1. **After subagent returns findings:**
   - Review output against the OUTPUT FORMAT specification provided in the prompt
   - Check that all required sections contain substantive content
   - Verify any confidence assessments (HIGH/MEDIUM/LOW)
   - Confirm no placeholder text remains (e.g., "[add more]", "[description]")

2. **If verification fails (first time):**
   - Re-invoke subagent with clarification about what's missing
   - Provide more specific context or examples
   - Emphasize the missing elements

3. **If verification fails (second time):**
   - Re-invoke with simplified task scope
   - Break complex tasks into smaller subtasks
   - Consider if task is feasible with available skills

4. **If verification fails (third time):**
   - STOP execution
   - Escalate to user with explanation of what couldn't be completed
   - Propose alternative approaches

**Example Verification:**

```markdown
**Subagent Output Review: Stage 2 (Data Exploration)**

Checklist:
- [x] Recommended Data Level specified
- [x] Candidate Endpoints table complete (3 endpoints found)
- [x] Key Variables table complete (8 variables identified)
- [x] Variables Flagged for Deep-Dive (2 flagged with reasons)
- [x] Limitations Encountered documented
- [x] Completeness Assessment all items checked
- [x] Confidence: HIGH (multiple sources confirm)

Status: VERIFIED - Proceeding to Stage 3
```

**Code-Reviewer Output Verification (Additional):**

When verifying code-reviewer QA reports specifically, also check:
- [ ] cr1 includes at least 5 script-specific checks (one per Skeptical Lens) and 5 spot-checks
- [ ] cr1 includes data profiling section; if multiple iterations, each has documented trigger
- [ ] Report includes reasoning (WHY correct, not just WHAT was checked)
- [ ] Adversarial analysis section has substantive content (not boilerplate)
- [ ] If PASSED: report articulates basis for confidence, not just absence of failures
- [ ] Report includes Investigation Narrative synthesizing across all iterations
- [ ] If capped at 5 iterations: "Additional Strands of Inquiry" section present

If the QA report reads like a template with values filled in and no script-specific reasoning, it has not met the review depth expectation. Consider re-invoking with emphasis on adversarial analysis.

### Learning Signal Extraction

For the complete Learning Signal Protocol (format, categories, accumulation flow, flush triggers), see the "Learning Signal Protocol" section below.

After verifying subagent output, extract any Learning Signal:

1. Check if subagent output contains a `**Learning Signal:**` field
2. If value is "None" → skip
3. If value is present → append to STATE.md "Pending Learning Signals" buffer:
   ```
   - [Stage N.step] [Category] — [Signal text]
   ```
4. Do NOT write to LEARNINGS.md on every signal — wait for flush triggers

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
    prompt: """You are a [Agent Role]. Follow the protocol in `{BASE_DIR}/agents/[agent-name].md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name '[skill-name]'.

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

## Standard Agent Prompt Structure

**REQUIRED:** Every subagent invocation MUST use this standardized format to ensure consistent handoffs and verifiable outputs.

### File-First Execution Rule

All code execution in Stages 5-8 MUST follow the file-first pattern (write → execute via wrapper → version on failure). See `CLAUDE.md` > "Execution Philosophy" and `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the complete file-first protocol.

### Template

```python
Agent({
    description: "[3-5 word summary]",
    prompt: """You are a [Agent Role]. Follow the protocol in `{BASE_DIR}/agents/[agent-name].md`.

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

**Deviations Applied:** [List per RULE 1-3 from `{BASE_DIR}/agent_reference/BOUNDARIES.md`, or "None"]

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

**Note:** `checkpoint:human-action` is used when Claude cannot automate a step (e.g., external authentication, restricted data downloads). See `VALIDATION_CHECKPOINTS.md` for full classification details.

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
    prompt: """You are a [Agent Role]. Follow the protocol in `{BASE_DIR}/agents/[agent-name].md`.

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

See "Prompt Size Targets by Subagent Type" above for size targets. The same targets apply to inlined content, but the Context Completeness Checklist always takes priority over brevity.

**If context needs consistently exceed targets:** Consider breaking the task into smaller subtasks, each with more focused scope.

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

> For retry limits and the escalation decision table, see the "Error Recovery" section below.

### Retry Pattern

```python
# If subagent returns error, retry with clarification
Agent({
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

## Quality & Validation Framework

This section consolidates all quality standards, validation checkpoints, enforcement gates, and stage-specific verification checklists.

### Confidence Levels

See the "Confidence Level Defaults" section above for the complete three-tier system (HIGH/MEDIUM/LOW), source-type defaults, and upgrade/downgrade paths.

**Critical rule:** LOW confidence items cannot be silently ignored — they require resolution before proceeding.

### Truth Hierarchy for Data Interpretation

When interpreting data values and resolving discrepancies between sources, apply this priority:

| Priority | Source | Rationale | Example |
|----------|--------|-----------|---------|
| 1 (highest) | **Actual data file** (parquet) | What you observe IS the truth | Column has values 1-7, not 1-5 as documented |
| 2 | **Live codebook/metadata** (.xls in mirror) | Authoritative documentation; may lag behind data | Codebook says "1=Regular, 2=Special Ed" (e.g., in education) |
| 3 (lowest) | **Archived skill docs** (e.g., variable-definitions.md) | Summarized; convenient but may drift | Skill says "values 1-5" but codebook says "1-7" |

**Application Rules:**
- When skill docs contradict observed data → trust the data, flag the discrepancy
- When codebook contradicts observed data → trust the data, but investigate (codebook may describe a different year)
- When skill docs contradict codebook → trust the codebook, update skill docs
- For education domain: Codebook URLs are cataloged in `datasets-reference.md` (codebook column); use `get_codebook_url()` in `fetch-patterns.md` to construct download URLs. Other domains will use analogous structures in their domain query skill.
- See also: `agents/data-ingest.md` Data Primacy table for the same hierarchy applied during data ingest

### Validation Checkpoints

| Checkpoint | When | Validates | STOP Condition |
|------------|------|-----------|----------------|
| **CP1** | After data fetch | Shape, types, missingness, expected rows | Empty data, >90% missing critical fields |
| **CP2** | After cleaning | Coded values handled, suppression rate | >50% suppression, invalid analysis type |
| **CP3** | After transformation | Row counts, join validation, no data loss | >90% row loss, unexpected NAs |
| **CP4** | Before output | Completeness, consistency with Plan | Missing required outputs, Plan violations |

**CP4 Detail:** CP4 runs during Stages 11-12 and validates:
- **CP4.1:** All required columns present in analysis data
- **CP4.2:** No nulls in critical columns defined in Plan
- **CP4.3:** All analysis outputs in Plan's analysis spec exist in output/analysis/ and all figures in Plan's visualization spec exist in output/figures/
- **CP4.4:** All Plan-required report sections complete
- **CP4.5:** Outputs match Plan commitments (data sources, years, geography, methodology)
- **CP4.6:** All Research Outcomes in Plan are addressed with evidence
- **CP4.7:** All Hypotheses in Plan (if any) are transparently assessed

**CP4 STOP Conditions:** Missing Executive Summary, missing Key Findings, any Research Outcome not addressed, major deviation from Plan methodology.

See `agent_reference/VALIDATION_CHECKPOINTS.md` for Python code templates.

### QA Checkpoints (Secondary Validation)

In addition to CP checkpoints (embedded in code), **QA checkpoints** provide independent secondary validation after each script execution in Stages 5-8.

| Checkpoint | Stage | Validates | BLOCKER Threshold |
|------------|-------|-----------|-------------------|
| **QA1** | After fetch (5) | Schema correctness, ID uniqueness, distributions | Data integrity compromised |
| **QA2** | After clean (6) | Coded value handling, filtering logic, methodology | Cleaning logic invalid |
| **QA3** | After transform (7) | Join cardinality, aggregation logic, derived columns | Transformation produces wrong results |
| **QA4a** | After analysis (8.1) | Statistical validity, assumption checks, result interpretation | Analysis methodology invalid or results unreliable |
| **QA4b** | After viz (8.2) | Figure existence, data source accuracy, labeling | Visualization misleading or incorrect |

**Key Difference:** CP checkpoints catch **operational failures** (empty data, wrong types). QA checkpoints catch **logical errors** (wrong methodology, misinterpretation).

**Severity Levels:**
- **BLOCKER:** Revision required (max 2 attempts, then escalate)
- **WARNING:** Log for Stage 10 aggregation, proceed
- **INFO:** Log only, proceed

See `agent_reference/QA_CHECKPOINTS.md` for complete definitions and `agents/code-reviewer.md` for the QA agent protocol.

### Stage Gates (Cannot Proceed Without)

Forcing functions are mandatory design interventions that **prevent** poor practices as the main enforcement mechanism for core design principles and values. The following gates CANNOT be bypassed.

| Gate | Transition | Requires | Enforcement |
|------|------------|----------|-------------|
| G1 | 1 → 2 | Mode classified and confirmed | Cannot invoke Stage 2 subagent |
| G2 | 2 → 3 | ≥1 endpoint identified, key variables flagged | Cannot invoke source deep-dive |
| G3 | 3 → 3.5 | All flagged variables investigated, coded values documented, suppression patterns identified | Cannot invoke research-synthesizer |
| G3.5 | 3.5 → 4 | Synthesis complete, cross-source conflicts resolved, **User confirmed PSU1** | Cannot create Plan without user PSU1 confirmation |
| **G4** | **4 → 4.5** | **Plan created AND STATE.md created AND LEARNINGS.md skeleton created** | **Cannot invoke plan-checker** |
| **G4.5** | **4.5 → 5** | **plan-checker returned PASSED or PASSED_WITH_WARNINGS, User confirmed PSU2** | **Cannot begin data acquisition without user PSU2 confirmation** |
| G5 | 5 → 6 | CP1 PASSED per script, data saved to data/raw/, code-reviewer separately invoked per script immediately after completion, every QA1 ∈ {PASSED, WARNING} | Cannot proceed to cleaning |
| G6 | 6 → 7 | CP2 PASSED per script, suppression <50%, data saved to data/processed/, code-reviewer separately invoked per script immediately after completion, every QA2 ∈ {PASSED, WARNING}, **User confirmed PSU3** | Cannot proceed to transformation without user PSU3 confirmation |
| G7 | 7 → 8 | All transformations CP3 PASSED per script, code-reviewer separately invoked per script immediately after completion, every QA3 ∈ {PASSED, WARNING} | Cannot proceed to analysis and visualization |
| G8 | 8 → 9 | Analyses and visualizations complete, code-reviewer separately invoked per 8.1 script (QA4a) and per 8.2 script (QA4b) immediately after each completes, every QA4a and QA4b ∈ {PASSED, WARNING} | Cannot assemble notebook |
| G9 | 9 → 10 | Notebook runs without errors, all scripts represented with code + execution logs | Cannot run QA aggregation |
| G10 | 10 → 11 | QA findings aggregated, all BLOCKERs resolved, all WARNINGs documented, **User confirmed PSU4** | Cannot generate report without user PSU4 confirmation |
| G11 | 11 → 12 | Report complete with all sections and figure references | Cannot run final review |
| G12 | 12 → Delivery | Final Review verification PASSED, all commitments fulfilled, LEARNINGS.md consolidated with System Update Action Plan, cross-artifact coherence verified | Cannot deliver |

**Gate G4 Enforcement:** Plan-checker (Stage 4.5) CANNOT be invoked without all three files: Plan.md, STATE.md (`agent_reference/STATE_TEMPLATE.md`), and LEARNINGS.md (`agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md`). If any are missing, create before proceeding. After plan-checker returns, the orchestrator MUST present PSU2 to the user and wait for confirmation before proceeding to Stage 5.

**Gate G4.5 Enforcement:** plan-checker MUST be invoked and return PASSED or PASSED_WITH_WARNINGS. If ISSUES_FOUND, revise Plan (max 2 attempts) then escalate. Update STATE.md "Plan Validation" section with the result before proceeding. See Stage 4.5 in `agent_reference/WORKFLOW_PHASE2_PLANNING.md` for the invocation pattern.

**CRITICAL:** Gate G4.5 requires POSITIVE confirmation that plan-checker was invoked and returned PASSED or PASSED_WITH_WARNINGS. If plan-checker was never invoked, the gate condition is NOT satisfied. Update STATE.md "Plan Validation" section with the result before proceeding to Stage 5. Additionally, after plan-checker returns PASSED or PASSED_WITH_WARNINGS, the orchestrator MUST present PSU2 (Phase Status Update) to the user including the plan-checker result, a Plan summary, and the exact filepath to the Plan for the user's deeper inspection. Stage 5 CANNOT begin until the user confirms PSU2.

**Gate G5-G8 Enforcement (Per-Script QA Invocation):** Gates G5-G8 require POSITIVE confirmation that code-reviewer was **separately invoked to review each individual script immediately after that script completed execution** — not batched at stage end. "Immediately" means: before the next script in the same stage begins. "Separately" means: one code-reviewer invocation per script, not one invocation reviewing multiple scripts. Running all scripts in a stage and then invoking code-reviewer once (or once per script after-the-fact) does **NOT** satisfy these gates — the QA must be interleaved with execution so that each script's QA findings can inform whether to proceed, revise, or stop before the next script runs. If code-reviewer was never invoked for a given script, that script's QA status is NOT_RUN and the gate is NOT satisfied. For Gate G8, BOTH QA4a (statistical analysis) and QA4b (visualization) must be independently and separately invoked per script. See the **Stage 5-8 Composite Execution Pattern** for the complete flow.

### Per-Script QA Enforcement Protocol

**To prevent batching, the orchestrator MUST maintain a QA invocation discipline throughout Stages 5-8.**

**Rule: One script in, one QA out, before the next script begins.**

Concretely:
1. **Before invoking research-executor for script N+1**, verify that script N has a completed code-reviewer QA entry in STATE.md (with QA status ∈ {PASSED, WARNING} or BLOCKER resolved via revision). If script N's QA entry is missing or incomplete, STOP and invoke code-reviewer for script N first.
2. **STATE.md Transformation Progress table** must have one row per script, and each row must include: script path, CP status, QA status, and QA script path. A row with QA status = `NOT_RUN` blocks the next script invocation.
3. **Self-check before every research-executor call**: *"What was the last script I executed? Did I invoke code-reviewer separately for it? Is its QA status recorded in STATE.md? If any answer is no → invoke code-reviewer NOW, do not invoke research-executor."*

**Why this matters:** Batching QA to the end of a stage means errors in script 1 propagate silently through scripts 2, 3, and 4 — producing compounding data corruption that is far harder to diagnose and fix. Per-script QA catches errors at the source, before they cascade.

### Gate Status Translation

Agents use domain-specific status vocabularies. The orchestrator translates these to gate vocabulary:

| Agent | Agent Output | Gate Interpretation |
|-------|-------------|-------------------|
| **research-executor** | PASSED | Proceed to QA |
| | WARNING | Proceed to QA (log warning) |
| | FAILED | Attempt versioned fix or STOP |
| **code-reviewer** | PASSED (severity: None/INFO) | QA = PASSED |
| | ISSUES_FOUND (severity: WARNING) | QA = WARNING |
| | ISSUES_FOUND (severity: BLOCKER) | QA = BLOCKER |
| **data-planner** | COMPLETE | Proceed to Stage 4.5 |
| | CONTINUATION | Read partial Plan on disk, invoke fresh data-planner in continuation mode |
| | REVISION_COMPLETE | Re-invoke plan-checker |
| | BLOCKED | Escalate to user |
| **plan-checker** | PASSED | G4.5 = SATISFIED |
| | PASSED_WITH_WARNINGS | G4.5 = SATISFIED (log warnings) |
| | ISSUES_FOUND | G4.5 = NOT SATISFIED (revision needed) |
| **data-verifier** | PASSED | G12 = SATISFIED |
| | ISSUES_FOUND (severity: WARNING) | Log, proceed with caveats |
| | ISSUES_FOUND (severity: BLOCKER) | G12 = NOT SATISFIED |
| **source-researcher** | COMPLETE | Proceed to next source or Stage 3.5 |
| | COMPLETE_WITH_WARNINGS | Log warnings; proceed |
| | BLOCKED | Escalate |
| **notebook-assembler** | PASSED | G9 = SATISFIED |
| | WARNING | Log; proceed |
| | BLOCKER | Revision needed |
| **report-writer** | COMPLETE | G11 = SATISFIED |
| | COMPLETE_WITH_GAPS | G11 = SATISFIED (log gaps) |
| | BLOCKED | G11 = NOT SATISFIED |
| **research-synthesizer** | PASSED | G3.5 = SATISFIED, proceed to Stage 4 |
| | WARNING | G3.5 = SATISFIED (log warnings for Plan) |
| | BLOCKER | G3.5 = NOT SATISFIED (resolve or escalate) |
| **debugger** | RESOLVED (Bug fix) | Apply fix, re-run task via research-executor |
| | RESOLVED (Data quality) | Document limitation, adjust scope |
| | RESOLVED (Transient) | Retry operation |
| | UNRESOLVED | Escalate to user with hypothesis log |
| | PARTIAL | Escalate with findings; user decides |
| **integration-checker** | CONNECTED | Gate satisfied (G9, G11, or G12 depending on stage) |
| | ISSUES FOUND (severity: WARNING) | Log; proceed with caveats |
| | ISSUES FOUND (severity: BLOCKER) | Gate NOT SATISFIED; revision needed |
| **data-ingest** | COMPLETE | Present integration guidance; offer skill registration |
| | COMPLETE_WITH_WARNINGS | Present discrepancies; user review required |
| | BLOCKED | Present STOP condition; await user resolution |

### STATE.md Update Gates

| Event | Required STATE.md Field Updates |
|-------|--------------------------------|
| Stage N starts | Current Stage → N |
| Checkpoint passes | Checkpoint Status table |
| QA completes | QA Status section |
| Blocker encountered | Blockers section + Next Actions |
| Key decision made | Key Decisions Made table |
| Context Utilization ≥40% | Context Snapshot section |
| Phase boundary reached | Phase Status Update section + User confirmation status |
| Phase completes | Session History (if multi-session) |

### Automatic STOP Conditions

These conditions trigger an immediate STOP with escalation to user. See `agent_reference/BOUNDARIES.md` for complete specifications.

| Condition | Stage | Action |
|-----------|-------|--------|
| Data access mirror returns empty data | Stage 5 | STOP, report to user, await guidance |
| Suppression rate >50% | Stage 6 | STOP, report issue, propose alternatives |
| Domain governance rule violation (e.g., cross-state assessment comparison in education) | Stage 6 | BLOCK with explanation (never valid) |
| Row count drops >90% after transformation | Stage 7 | STOP, verify transformation logic |
| **QA BLOCKER after 2 revisions** | 5-QA to 8-QA | STOP, escalate to user |
| **QA methodology violation** | 5-QA to 8-QA | STOP, escalate immediately |
| Notebook execution error after 2 fix attempts | Stage 9 | STOP, report error details |
| Data unavailable in configured data source | Stage 2-3 | STOP, escalate immediately |

**STOP/Escalation Format:** See `agent_reference/ERROR_RECOVERY.md` "Escalation Template" for the detailed format. At minimum, include: what happened, what was tried, options with pros/cons, and a recommendation.

### Verification Checklists by Stage

**Stage 4 (Plan Creation) Verification:**
- [ ] Research question clearly stated (not placeholder)
- [ ] Research Outcomes section has ≥3 investigation/measurement objectives that do not pre-specify directional results
- [ ] Hypotheses (if any) are clearly separated from Research Outcomes and include basis citations
- [ ] Data Sources table complete with endpoints and years
- [ ] Transformation Sequence table has all tasks with waves assigned
- [ ] Every task has explicit file paths (no placeholders like "TBD")
- [ ] Every task has a skill or agent identified
- [ ] Every join task has cardinality specified (1:1, 1:many, many:1)
- [ ] Every task has verifiable "done" condition
- [ ] Risk Register identifies ≥1 risk with mitigation
- [ ] Wave dependencies are correct (no circular dependencies)
- [ ] Validation checkpoints specified for each phase

**Stage 2 (Data Exploration) Verification:**
- [ ] Recommended Data Level specified (not "TBD" or placeholder)
- [ ] Candidate Endpoints table has ≥1 endpoint with complete rows
- [ ] Key Variables table has actual variable names (not "[add more]")
- [ ] Variables Flagged for Deep-Dive has rationale for each flag
- [ ] Completeness Assessment checkboxes all marked
- [ ] Confidence Assessment present with overall confidence level
- [ ] If confidence is LOW: resolution plan or escalation present

**Stage 3 (Source Deep-Dive) Verification:**
- [ ] Source name explicitly stated
- [ ] Source-Specific Caveats table populated (not empty)
- [ ] Coded Value Mappings complete for all flagged variables
- [ ] Suppression Patterns documented with typical rates
- [ ] Cross-region comparability assessed (if multi-region analysis, e.g., cross-state for education)
- [ ] Critical Warnings have mitigation strategies
- [ ] Confidence Assessment present
- [ ] If confidence is LOW: resolution present

**Stage 3.5 (Findings Synthesis) Verification:**
- [ ] All source findings consolidated into unified summary
- [ ] Cross-source conflicts identified and resolved (or flagged for Plan)
- [ ] Join feasibility assessed with key considerations documented
- [ ] Unified guidance ready for data-planner input
- [ ] Confidence Assessment present

**Stage 5 (Data Retrieval) Verification:**
- [ ] Fetch Summary has actual counts (not "TBD")
- [ ] CP1 Status explicitly stated (PASSED/FAILED/WARNING)
- [ ] File locations provided with actual filenames
- [ ] If CP1 FAILED: Stop reason documented
- [ ] If data lag ≥3 years: Flagged for user notification
- [ ] If flag years (per FLAG_YEARS in Plan Domain Configuration) included: Flagged with warning

**Stage 6 (Context Application) Verification:**
- [ ] Cleaning Applied table shows actual row counts removed
- [ ] CP2 Status explicitly stated
- [ ] Suppression rate calculated and reported
- [ ] Validity Check completed (Yes/No/Conditional)
- [ ] Citation text present and complete
- [ ] File locations provided
- [ ] If CP2 FAILED: Stop reason documented

**Stage 7 (Transformation) Verification:**
- [ ] Pre-state and post-state both documented
- [ ] Row change percentage calculated
- [ ] Invariants checked with PASS/FAIL status
- [ ] Overall status: PASSED/FAILED/WARNING
- [ ] If FAILED: Issue description and proposed fix present
- [ ] For joins: Cardinality validation performed

**Stage 8.1 (Statistical Analysis) Verification:**
- [ ] Statistical method appropriate for data type and research question
- [ ] Assumptions validated before analysis (documented in script)
- [ ] Results saved to `output/analysis/` as parquet
- [ ] Key findings documented with effect sizes and confidence intervals
- [ ] Interpretation aligned with Research Outcomes in Plan
- [ ] Overall status: PASSED/FAILED/WARNING

**Stage 8.2 (Visualization) Verification:**
- [ ] All Plan-specified figures generated
- [ ] Figures saved to `output/figures/` as PNG
- [ ] Proper labeling (title, axes, legend, source note)
- [ ] Data source in visualization matches analysis dataset
- [ ] Colorblind-safe palette used
- [ ] Overall status: PASSED/FAILED/WARNING

**Stage 12 (Final Verification) Output Verification:**
- [ ] Independent assessment performed (expectations listed before Plan comparison)
- [ ] All four verification layers completed (Existence, Substantive, Wired, Coherent)
- [ ] Research question stress test result stated with reasoning
- [ ] At least one key finding traced end-to-end (Telephone Game test performed)
- [ ] Confidence assessment completed for all five aspects with rationale
- [ ] Verification Quality Self-Check results included (all 8 questions)
- [ ] If PASSED: conclusion articulates WHY the analysis is sound, not just absence of failures

---

## Pipeline-Specific Behavioral Boundaries

These supplement the universal boundaries in `CLAUDE.md` (Boundaries & Safety) and `agent_reference/BOUNDARIES.md`. See `BOUNDARIES.md` > Full Pipeline Mode for complete specifications.

**Always Do:**
- Validate data at every checkpoint (CP1-CP4)
- Create Plan document before data acquisition
- Complete Final Review (Final Review) before delivery
- Generate all three deliverables (Plan, Notebook, Report)
- Follow the Inline Audit Trail (IAT) protocol for all Python scripts (`agent_reference/INLINE_AUDIT_TRAIL.md`)
- Include validation assertions in notebooks
- Update Plan with all decisions and deviations

**Never Do:**
- Skip any protocol or checkpoint
- Deliver without all three deliverables
- Proceed without resolving LOW confidence findings
- Proceed after STOP condition without user guidance

**QA-Specific Boundaries (Stages 5-8):**
- Invoke code-reviewer after EVERY script execution
- Create QA scripts in `scripts/cr/` for every reviewed script
- Address BLOCKER issues via revision before proceeding
- Never skip QA for "simple" scripts
- Never modify scripts after QA review (create new version instead)
- Never allow code-reviewer to directly modify execution scripts

See `agent_reference/BOUNDARIES.md` > QA-Specific Boundaries for complete specifications.

### Autonomous Deviation Rules (Quick Reference)

When executing Plan tasks, the agent MAY deviate **without asking** for these categories:

| Rule | Category | Action |
|------|----------|--------|
| RULE 1 | Bug fixes (syntax, types, imports) | Fix immediately, document |
| RULE 2 | Critical functionality (validation, error handling) | Add silently, document |
| RULE 3 | Blocking issues (missing deps, wrong paths) | Fix immediately, document |
| RULE 4 | Methodological changes | STOP, escalate to user |
| RULE 5 | QA-triggered revisions (non-methodology BLOCKER) | Fix via versioned revision, re-QA |

**Always Requires Approval:** Scope expansion, methodology changes, removing validation, skipping checkpoints.

See `agent_reference/BOUNDARIES.md` for complete boundary specifications and deviation decision tree.

---

## Context Utilization Management

The orchestrator receives actual context utilization via the `context-reporter` hook. See `CLAUDE.md` > "Context & Session Health" for the complete threshold table and required actions.

**Cardinal Principle: Quality Is the Invariant, Session Restart Is the Pressure Valve.** Never sacrifice subagent prompt completeness, skip checklist items, or reduce inlined context to "save space." Use session restart (see `{SKILL_REFS}/session-recovery.md`) as the relief mechanism instead.

---

## Session State Management

### STATE.md (MANDATORY for Full Pipeline)

**STATE.md is REQUIRED for all Full Pipeline analyses.** This is not optional.

**Why Mandatory:**
- Enables session recovery if context is exhausted
- Provides checkpoint history for debugging
- Creates audit trail of progress and decisions
- Allows handoff between sessions
- Prevents context exhaustion without recovery path

**Creation Trigger:**
- **Create:** At Stage 4 (Plan creation) — IMMEDIATELY after Plan file is written
- **Gate:** Stage 5 CANNOT begin until STATE.md exists alongside Plan (see Gate G4) and Plan-Checker Status is PASSED or PASSED_WITH_WARNINGS (see Gate G4.5).

**Update Triggers:** See the **STATE.md Update Gates** table above for the complete list of mandatory update events and which fields to update.

See `agent_reference/STATE_TEMPLATE.md` for the complete template.

### Session Transcript Archiving

On session end, the `archive-session.sh` hook automatically archives the full session transcript (JSONL + readable Markdown) to `.claude/logs/sessions/`. This provides a complete audit trail independent of STATE.md, useful for debugging cross-session issues or reviewing past decisions.

---

## Error Recovery

> For retry/escalation prompt templates, see the "Error Handling in Invocations" section above.

See `agent_reference/ERROR_RECOVERY.md` for complete decision trees and recovery procedures.

### Quick Reference: Error Types & Responses

| Error Type | Max Retries | Escalation Trigger | Reference |
|------------|-------------|-------------------|-----------|
| Data unavailable | 0 | Immediate | `ERROR_RECOVERY.md` § Data Availability |
| Access/network error | 3 | After 3 failures | `ERROR_RECOVERY.md` § Access/Network |
| Code execution error | 2 | After 2 failures | `ERROR_RECOVERY.md` § Code Execution |
| Validation failure (STOP condition) | 0 | Immediate | `ERROR_RECOVERY.md` § Validation |
| Validation failure (warning) | N/A | Document and proceed | `ERROR_RECOVERY.md` § Validation |

### Re-run Guidance

For the complete re-run guidance table (situations, stages to re-run, and refresh/additive modes), see `{SKILL_REFS}/revision-mode.md` > Re-run Guidance.

See `agent_reference/ERROR_RECOVERY.md` "Re-run Procedures" for complete re-run decision trees.

