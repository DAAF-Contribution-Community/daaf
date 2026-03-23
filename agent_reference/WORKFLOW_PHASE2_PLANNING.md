# Workflow Reference: Phase 2 — Planning

Stages 4, 4.5. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline.md`.

---

## Stage 4: Plan Creation

**Executor:** Orchestrator (invokes `data-planner` agent via `general-purpose` subagent)
**Purpose:** Create Plan.md (strategic specification) and Plan_Tasks.md (executable task sequence) as persistent memory

### Actions

0. **Preserve Original Request for Plan**
   - Copy the user's original request text VERBATIM from the conversation
   - Collect all clarifications received during Stage 1
   - These MUST be passed to the data-planner agent in the Stage 4 invocation prompt
   - The data-planner embeds them in the Plan's `## Original Request & Clarifications` section

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
   - Create `LEARNINGS.md` in the project folder using the template from `WORKFLOW_PHASE5_SYNTHESIS.md` > "Lessons Learned Consolidation"
   - Populate project metadata (title, date, data sources, analysis type)
   - Include all section headers with empty content
   - This is a skeleton — content will be added incrementally during execution
   - **LEARNINGS.md is created at Stage 4 alongside Plan.md + Plan_Tasks.md + STATE.md. Gate G4 requires: Plan.md + Plan_Tasks.md + STATE.md + LEARNINGS.md all exist before proceeding to Stage 4.5.**

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
Could a subagent execute any stage of this analysis with ONLY the Plan documents (Plan.md + Plan_Tasks.md) as context (plus skill knowledge), without access to the original conversation?

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

### Invocation Template: data-planner

**Purpose:** Create comprehensive research plan with executable task sequences
**Stage:** 4 (Plan Creation)
**Agent:** `data-planner` (see `.claude/agents/data-planner.md`)
**Subagent:** general-purpose
**Skills:** `data-scientist`

```python
Agent({
    description: "Stage 4: Plan Creation",
    prompt: """Call the skill tool with name 'data-scientist'.

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
research/{date}_{title}/

**TASK:**
Create a comprehensive Plan document following `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md` and an executable task sequence following `{BASE_DIR}/agent_reference/PLAN_TASKS_TEMPLATE.md`.

CRITICAL: The Plan MUST begin with `## Original Request & Clarifications`
containing the VERBATIM original user request above as a blockquote.
Do NOT paraphrase or summarize — copy the exact text.

**OUTPUT:**
- Plan.md saved to: research/{date}_{title}/{date}_{title}_Plan.md
- Plan_Tasks.md saved to: research/{date}_{title}/{date}_{title}_Plan_Tasks.md
- Structure follows `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md`
- All sections populated (no placeholders)
""",
    subagent_type: "data-planner"
})
```

**Orchestrator Checklist Before Invoking data-planner:**
- [ ] Original user request text available (verbatim, not paraphrased)
- [ ] Clarifications documented (numbered list)
- [ ] Stage 2 findings summarized
- [ ] Stage 3 findings summarized (per source)
- [ ] Stage 3.5 synthesis included
- [ ] Project folder path determined

### Continuation Handling (Complex Plans)

The data-planner writes the Plan incrementally in four section groups (A through D), saving to disk after each group. If the planner's context is exhausted mid-generation or it returns `CONTINUATION`:

1. **Detect:** Orchestrator receives `CONTINUATION` status (or subagent crash with no return). Check the Plan file on disk for a progress marker: `<!-- PLAN_PROGRESS: NEXT_GROUP=X ... -->`
2. **Assess:** The marker indicates which group is needed next. If no marker is present and the file exists, check whether all expected sections are populated.
3. **Resume:** Invoke a fresh data-planner in continuation mode (see continuation template below). The fresh planner reads the partial Plan to recover all context — discovery findings are already embedded in the Plan's Group B sections, so they do NOT need to be re-provided.
4. **Cap:** Maximum 3 total planner invocations (initial + 2 continuations). If the Plan is still incomplete after 3 passes, STOP and escalate to user.

**Key principle:** The partial Plan on disk IS the handoff context. Each continuation planner reads it rather than requiring the orchestrator to re-supply discovery findings.

#### Continuation Mode Invocation Template

**When to use:** The data-planner returned `CONTINUATION`, or the subagent crashed and a partial Plan file exists on disk with a `<!-- PLAN_PROGRESS: ... -->` marker.

**Key savings:** Discovery findings are already embedded in the partial Plan (Group B). The continuation planner reads them from the file — do NOT re-supply Stage 2/3/3.5 findings in the prompt.

```python
Agent({
    description: "Stage 4: Plan Continuation",
    prompt: """**BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    Call the skill tool with name 'data-scientist'.

    **MODE:** continuation

    **PARTIAL PLAN PATH:** {partial_plan_path}
    Read the partial Plan file FIRST to understand all decisions and context
    already documented. Discovery findings are embedded in the Plan's
    Phase 1 Discovery Results section — do NOT re-derive them.

    **GROUPS REMAINING:** {groups_remaining}
    Continue writing from Group {next_group}. The Plan file ends with a
    progress marker `<!-- PLAN_PROGRESS: ... -->` showing exactly where
    to resume.

    **TASK:**
    Complete the remaining section groups of the Plan following
    `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md`.
    Use the Edit tool to replace the progress marker with new content.
    Follow the Sectional Writing Protocol (Step 9 of your protocol).

    Return findings using the Data Planner Output Format.""",
    subagent_type: "data-planner"
})
```

**Orchestrator Checklist Before Invoking Continuation:**
- [ ] Partial Plan file exists on disk
- [ ] Progress marker present (`<!-- PLAN_PROGRESS: ... -->`)
- [ ] Groups remaining identified from marker or CONTINUATION return
- [ ] Total planner invocations < 3 (initial + max 2 continuations)

### Gate Criteria (G4)

- [ ] Plan.md created at `research/[folder]/YYYY-MM-DD_[Title]_Plan.md`
- [ ] Plan_Tasks.md created at `research/[folder]/YYYY-MM-DD_[Title]_Plan_Tasks.md`
- [ ] **STATE.md created** at `research/[folder]/STATE.md` (MANDATORY — Gate G4) — includes Runtime Risks, QA Findings Summary, and Final Review Log skeleton sections
- [ ] **LEARNINGS.md skeleton created** at `research/[folder]/LEARNINGS.md` (MANDATORY — Gate G4)
- [ ] **Plan Completeness Gate passed** (all sections verified in both Plan.md and Plan_Tasks.md)
- [ ] Project folder structure created (`data/raw/`, `data/processed/`, `output/analysis/`, `output/figures/`)
- [ ] User notified (PSU2 presented after Stage 4.5 completes)

**Gate G4 Enforcement:** Plan-checker (Stage 4.5) CANNOT be invoked without Plan.md, Plan_Tasks.md, STATE.md, and LEARNINGS.md all existing. (Stage 5 additionally requires G4.5 — see below.)

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

### Invocation Template: plan-checker

**Purpose:** Validate research plan before execution
**Stage:** 4.5 (after Plan creation, before Stage 5)
**Agent:** `plan-checker` (see `.claude/agents/plan-checker.md`)
**Subagent:** Plan
**Skills:** `data-scientist`

For the complete invocation pattern, see `.claude/agents/plan-checker.md` Invocation section
and `.claude/agents/README.md` plan-checker section. The orchestrator inlines BOTH Plan.md and
Plan_Tasks.md content along with the original user request. The agent validates across six dimensions.

**Skill Loading:** Include `Call the skill tool with name 'data-scientist'.` in the Agent prompt.
The data-scientist skill helps the plan-checker assess methodological soundness
of the proposed transformation sequence and validation approach.

```python
Agent({
    description: "Stage 4.5: Plan Validation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PLAN.MD CONTENT:**
{inline the full Plan.md content here}

**PLAN_TASKS.MD CONTENT:**
{inline the full Plan_Tasks.md content here}

**ORIGINAL REQUEST:**
{inline the original user request verbatim}

**CLARIFICATIONS:**
{inline any user clarifications, or "None"}

**TASK:**
Validate BOTH Plan.md and Plan_Tasks.md across all 6 dimensions (Completeness, Consistency, Feasibility, Testability, Clarity, Scope). Return structured report with per-dimension confidence and issues in YAML format.

**OUTPUT FORMAT:**
1. Dimension Scores (PASS/WARN/FAIL for each)
2. Issues Found (with severity and location)
3. Recommended Fixes (if ISSUES_FOUND)
4. Overall Status: PASSED / PASSED_WITH_WARNINGS / ISSUES_FOUND
""",
    subagent_type: "plan-checker"
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
- [ ] If PASSED_WITH_WARNINGS: warnings documented in Plan.md
- [ ] **PSU2 presented to user with Plan summary, exact Plan filepath, clear indication that the user should read the full Plan before approving, and validation results**
- [ ] **User confirmed PSU2 (explicit approval of Plan)**

### Phase Status Update 2 (PSU2): Plan Ready for Approval

**Trigger:** Gate G4.5 satisfied (plan-checker PASSED or PASSED_WITH_WARNINGS)
**Blocking:** YES — Stage 5 CANNOT begin until user confirms PSU2

**Important: Summary vs. Full Plan**
The PSU2 checkpoint presents a **high-level summary** of the Plan — not the Plan itself. The full Plan document contains critical detail (exact query specifications, complete transformation sequences with validation criteria, full risk registers, etc.) that cannot be adequately conveyed in a checkpoint summary. The user must be clearly told that reviewing the full Plan file is expected before they approve.

**Actions:**
1. Compile a high-level Plan summary and plan-checker results
2. Present PSU2 to user using the PSU template, explicitly framing it as a summary
3. Share the exact Plan.md filepath and clearly tell the user that this summary does not replace reading the full Plan — they should review Plan.md before approving (Plan_Tasks.md contains executable task details and does not require user review)
4. WAIT for explicit user confirmation

**PSU2 Content Requirements (this is a SUMMARY — not the full Plan):**
- Research question as stated in the Plan
- Methodology summary: statistical approach, key analytical decisions
- Data sources confirmed: endpoints, year ranges, geographic scope
- Transformation sequence overview: number of tasks, wave structure, key joins
- Research Outcomes the analysis will investigate
- Risk Register highlights: top risks and mitigation strategies
- Plan-checker result: PASSED or PASSED_WITH_WARNINGS (include any warnings verbatim)
- Estimated scope: approximate record counts, number of scripts
- **Full Plan.md filepath prominently displayed, with clear language that this checkpoint is a summary and the user should read the full Plan.md document before approving** (e.g., "This is a summary — the full plan with complete specifications is at [path]. Please review it before approving.")

**User Response Handling:**
- **Approve** → Proceed to Stage 5 (Data Retrieval)
- **Request Plan changes** → Invoke data-planner for revision, re-run plan-checker, then re-present PSU2
- **Adjust scope/methodology** → Revise Plan accordingly, re-validate, re-present PSU2
- **Ask questions** → Answer, then re-present approval request

#### PSU2 Checkpoint Purpose

Include in the "Why this checkpoint" field:
> "This is your most important review point — the plan defines exactly what analysis will be performed and how. What I'm presenting here is a summary; the full plan document has the complete details. Please review the full plan before approving — once you do, I'll start writing and executing code."

#### PSU2 Phase Transition Bridge

Include in the "What Comes Next" field:
> "With the plan approved, I'll now download and clean the data according to the plan. I'll run automated quality checks on everything and report back on data health before analysis begins."

#### PSU2 Feedback Guidance

Include in the "What's Most Useful From You Here" field:
> "What I've shared above is a high-level summary. The full plan — with complete query specifications, the detailed transformation sequence, validation criteria, and risk register — is at the filepath above. Please read through it before approving. Does the methodology match your intent? Are the research outcomes what you want to investigate? Any variables to add or remove?"

#### PSU2 Content Requirements

The PSU2 checkpoint presents a **summary**, not the full Plan. It MUST include:
- Research question as stated in Plan
- Methodology summary (statistical approach, key decisions)
- Data sources and year ranges confirmed
- Transformation sequence overview (number of tasks, waves)
- Research Outcomes the analysis will investigate
- Hypotheses (if any) and their basis
- Risk Register highlights
- Plan-checker validation result (PASSED/PASSED_WITH_WARNINGS and any warnings)
- **Full Plan.md filepath prominently displayed, with clear language that the user should read the complete Plan.md document before approving** — this summary covers the highlights but does not replace reviewing the full specification

---

## Verification Checklists

Apply this checklist after the data-planner subagent returns the Plan documents (Plan.md + Plan_Tasks.md).

### Stage 4 (Plan Creation) Verification

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
