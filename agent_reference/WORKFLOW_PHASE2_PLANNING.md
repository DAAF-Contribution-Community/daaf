# Workflow Reference: Phase 2 — Planning

Stages 4, 4.5. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md`.

---

## Stage 4: Plan Creation

**Executor:** Orchestrator (dispatches the `data-planner` agent)
**Purpose:** Create Plan.md (strategic specification) and Plan_Tasks.md (executable task sequence) as persistent memory

### Actions

0. **Preserve Original Request for Plan**
   - Copy the user's original request text VERBATIM from the conversation
   - Collect all clarifications received during Stage 1
   - Collect the confirmed pre-flight Scope Check (scope as confirmed, what changed from the original request, decisions with the user's answers) and the user-referenced materials with their paths in the project folder, from `output/preliminary_notes/{date}_preflight_scope-check.md`
   - These MUST be passed to the data-planner agent in the Stage 4 invocation prompt (`CLARIFICATIONS RECEIVED:`, `CONFIRMED PRE-FLIGHT SCOPE:`, `USER-REFERENCED MATERIALS:`)
   - The data-planner embeds them in the Plan's `## Original Request & Clarifications` section (its Confirmed Pre-Flight Scope and User-Referenced Materials subsections, `agent_reference/PLAN_TEMPLATE.md`)

1. **Reuse the Project Folder**
   - The project folder `research/YYYY-MM-DD_[Title]/` was created when the user confirmed the pre-flight (Gate G1; layout in `full-pipeline-mode.md` § Pre-Flight Checklist > On Confirmation (Gate G1)), and Phase 1 wrote its notes into it. Reuse it; never create a second one
   - Check that every layout folder (`data/raw/`, `data/processed/`, `output/analysis/`, `output/figures/`, `output/preliminary_notes/`) exists, and create any that is missing

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

5. **Create STATE.md** from `agent_reference/STATE_TEMPLATE.md` after the data-planner returns (`full-pipeline-mode.md` § STATE.md (MANDATORY for Full Pipeline) > Creation Trigger). Its Pre-Flight Scope Check section records the confirmed pre-flight scope, the materials list with their project paths, and the dated old → new move line, copied from `output/preliminary_notes/{date}_preflight_scope-check.md`.

6. **Create LEARNINGS.md Skeleton**
   - Create `LEARNINGS.md` in the project folder using the template from `WORKFLOW_PHASE5_SYNTHESIS.md` > "Lessons Learned Consolidation"
   - Populate project metadata (title, date, data sources, analysis type)
   - Include all section headers with empty content
   - This is a skeleton — content will be added incrementally during execution
   - **LEARNINGS.md is created at Stage 4 alongside Plan.md + Plan_Tasks.md + STATE.md. Gate G4 requires: Plan.md + Plan_Tasks.md + STATE.md + LEARNINGS.md all exist before proceeding to Stage 4.5.**

7. **Phase Status Update (PSU2)**
   After plan-checker completes (Stage 4.5), present PSU2 to user.
   See "Phase Status Update 2 (PSU2)" section for full requirements.
   **MUST wait for explicit user confirmation before proceeding to Stage 5.**

### Plan Completeness Checklist

- [ ] Original request captured verbatim
- [ ] All clarifications documented
- [ ] Confirmed pre-flight scope and user-referenced materials reflected (any departure recorded in the Decisions Log)
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
| **Confirmed Pre-Flight Scope / User-Referenced Materials** | Both Full Pipeline subsections of `## Original Request & Clarifications` filled from the `CONFIRMED PRE-FLIGHT SCOPE:` and `USER-REFERENCED MATERIALS:` fields | Scope as confirmed at the pre-flight, not placeholder; every material listed with its path (or "none"); any departure recorded in the Decisions Log |
| **Research Question** | Clear, answerable statement | Specific and measurable |
| **Query Specification** | All fields populated | Dataset identifier(s), years, filters, variables, expected records all present |
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
**Skills:** `data-scientist`

> **Async dispatch note.** This phase dispatches single agents sequentially (data-planner, then plan-checker), not parallel waves. See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive. Do not advance to Stage 4.5 (plan-checker), evaluate Gate G4, or present PSU2 until that return has arrived and been fully processed — including confirming that Plan.md, Plan_Tasks.md, STATE.md, and LEARNINGS.md exist on disk.

```python
Agent({
    description: "Stage 4: Plan Creation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**ORIGINAL USER REQUEST (VERBATIM — paste into Plan as-is):**
> {original_user_request_verbatim}

**CLARIFICATIONS RECEIVED:**
{numbered_list_of_clarifications_or_None}

**CONFIRMED PRE-FLIGHT SCOPE:**
{the pre-flight Scope Check as the user confirmed it: proposed scope, what changed
from the original request, and each decision with the user's answer, from
{project_dir}/output/preliminary_notes/{date}_preflight_scope-check.md}

**USER-REFERENCED MATERIALS:**
{absolute paths of the materials the user pointed to, as moved into the project
folder (web_fetches/, papers/, the digest in output/preliminary_notes/) or at
the user's own location, each with one line on what it defines — or "none"}
Read these (or the digest). Carry what they define (outcome definitions, years,
a specification to replicate) into the Plan, and record any departure from them
in the Decisions Log.

**RESEARCH QUESTION (orchestrator formulation):**
{research_question}

**DISCOVERY PRELIMINARY NOTES:**
Read these files for full-fidelity discovery findings:
- Stage 2: {project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md
- Stage 3 (per source):
  - {project_dir}/output/preliminary_notes/{date}_stage3_{source1}_source-research.md
  - {project_dir}/output/preliminary_notes/{date}_stage3_{source2}_source-research.md
  [...one path per source]
- Stage 3.5: {project_dir}/output/preliminary_notes/{date}_stage3.5_research-synthesis.md

**ORCHESTRATOR CONTEXT (orientation summary):**
[5-8 sentence summary of the discovery phase — key sources, main constraints,
recommended approach. This is for quick orientation; consult the full preliminary
notes above for complete detail.]

**PROJECT FOLDER:** {project_dir}
**DATE PREFIX:** {date}

**TASK:**
Create a comprehensive Plan document following `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md` and an executable task sequence following `{BASE_DIR}/agent_reference/PLAN_TASKS_TEMPLATE.md`.

CRITICAL: The Plan's `## Original Request & Clarifications` section (in
PLAN_TEMPLATE order) MUST contain the VERBATIM original user request above
as a blockquote. Do NOT paraphrase or summarize — copy the exact text.

**OUTPUT:**
- Plan.md saved to: {project_dir}/{date}_{title}_Plan.md
- Plan_Tasks.md saved to: {project_dir}/{date}_{title}_Plan_Tasks.md
- Structure follows `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md`
- All sections populated (no placeholders)
""",
    subagent_type: "data-planner"
})
```

**Orchestrator Checklist Before Invoking data-planner:**
- [ ] Original user request text available (verbatim, not paraphrased)
- [ ] Clarifications documented (numbered list)
- [ ] Confirmed pre-flight scope and user-referenced materials (project paths, or "none") filled in from `{date}_preflight_scope-check.md`
- [ ] Preliminary notes file paths confirmed on disk (Stage 2, Stage 3 per source, Stage 3.5)
- [ ] Orientation summary drafted (5-8 sentences covering key sources, constraints, approach)
- [ ] Project folder path (absolute) and date prefix filled in

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
- [ ] **STATE.md created** at `research/[folder]/STATE.md` (MANDATORY — Gate G4) — includes Runtime Risks, QA Findings Summary, and Final Review Log skeleton sections, and the Pre-Flight Scope Check section (confirmed scope, materials with their project paths, move record)
- [ ] **LEARNINGS.md skeleton created** at `research/[folder]/LEARNINGS.md` (MANDATORY — Gate G4)
- [ ] **Plan Completeness Gate passed** (all sections verified in both Plan.md and Plan_Tasks.md)
- [ ] Project folder structure in place (`data/raw/`, `data/processed/`, `output/analysis/`, `output/figures/`, `output/preliminary_notes/`; created at Gate G1)
- [ ] User notified (PSU2 presented after Stage 4.5 completes)

**Gate G4 Enforcement:** Plan-checker (Stage 4.5) CANNOT be invoked without Plan.md, Plan_Tasks.md, STATE.md, and LEARNINGS.md all existing. (Stage 5 additionally requires G4.5 — see below.)

---

## Stage 4.5: Plan Validation (Required)

**Executor:** Subagent (plan-checker)
**Purpose:** Validate Plan across 6 dimensions before execution begins

### Why This Stage is Required

Plans created by data-planner may contain:
- Requirements of the research question that no task covers
- Incomplete or vague task specifications
- Dangling or circular task dependencies
- Missing validation criteria
- File paths that do not match between the task that writes a file and the task that reads it
- Unclear scope boundaries

Stage 4.5 catches these issues **before** expensive data acquisition begins. Data availability (sources, dataset identifiers, years) is established at Stages 2-3; plan-checker checks the Plan against those notes, not against the data.

### Validation Dimensions

The definitions are plan-checker's own (`.claude/agents/plan-checker.md` § Protocol, Steps 3-8); this table summarizes them.

| Dimension | What It Checks |
|-----------|----------------|
| **Completeness (D1)** | Every requirement decomposed from the research question has a covering task (coverage matrix) |
| **Consistency (D2)** | Every task has the fields its type requires (files, action, verify, done) with substantive content and no placeholders; methodology is exact (variables, filters, aggregations, joins) |
| **Feasibility (D3)** | Dependency graph is valid: no dangling or circular dependencies, wave numbers consistent with dependencies |
| **Testability (D4)** | Research Outcomes are data-observable and non-directional; CP1-CP4 mapped to tasks; STOP conditions for high-risk operations; join tasks specify cardinality |
| **Clarity (D5)** | Artifact wiring: each producing task's output path matches the consuming task's input path exactly |
| **Scope (D6)** | Task-count, tasks-per-wave and transformations-per-task bands; the bands and the 21+ user-decision protocol are canonical in `agent_reference/SCOPE_POLICY.md` |

### Invocation Template: plan-checker

**Purpose:** Validate research plan before execution
**Stage:** 4.5 (after Plan creation, before Stage 5)
**Agent:** `plan-checker` (see `.claude/agents/plan-checker.md`)
**Skills:** `data-scientist`

The orchestrator inlines BOTH Plan.md and
Plan_Tasks.md content along with the original user request, the confirmed pre-flight scope and the
user-referenced materials. The agent validates across six dimensions.

**Skill Loading:** The `plan-checker` agent preloads `data-scientist` via frontmatter —
do NOT include a redundant `Call the skill tool` instruction in the Agent prompt. The skill
helps the plan-checker assess methodological soundness of the proposed transformation sequence
and validation approach.

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

**CONFIRMED PRE-FLIGHT SCOPE:**
{the same text the data-planner received: the pre-flight Scope Check as the
user confirmed it, from
{project_dir}/output/preliminary_notes/{date}_preflight_scope-check.md}

**USER-REFERENCED MATERIALS:**
{the same absolute paths the data-planner received (materials in the project
folder or at the user's own location, and the digest), each with one line on
what it defines — or "none"}
Verify that the Plan stays within the confirmed scope and carries what the
materials define (outcome definitions, years, a specification to replicate);
a departure from either that the Decisions Log does not record is an issue.

**DISCOVERY PRELIMINARY NOTES (for verification against Plan):**
Read these files to verify the Plan accurately represents the data landscape:
- {project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md
- {project_dir}/output/preliminary_notes/{date}_stage3_{source1}_source-research.md
- {project_dir}/output/preliminary_notes/{date}_stage3_{source2}_source-research.md
- {project_dir}/output/preliminary_notes/{date}_stage3.5_research-synthesis.md

Use these to verify:
- All caveats from source research are reflected in the Plan's Risk Register
- Coded value handling matches source-researcher recommendations
- Suppression thresholds are documented as constraints
- The Plan's methodology aligns with the synthesis's Recommended Approach

**TASK:**
Validate BOTH Plan.md and Plan_Tasks.md across all 6 dimensions (Completeness, Consistency, Feasibility, Testability, Clarity, Scope). Return structured report with per-dimension confidence and issues in YAML format.

**OUTPUT FORMAT:**
Return findings using the Plan Checker Output Format
(see your agent protocol, § Output Format).
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
├─ PASSED_WITH_WARNINGS → Record warnings in STATE.md § Plan Validation, present PSU2, await user confirmation, then proceed to Stage 5
├─ ISSUES_FOUND with a 21+ task scope issue → Bring the scope question to the user first
│       (`SCOPE_POLICY.md` § Escalation (21+ tasks): User Decision Point). Approval resolves
│       the count objection: data-planner records it in the Plan's Scope Sizing block
│       (Pre-Approved Scope Record) along with any other fixes. A requested split is a
│       revision. Either way, continue with the data-planner revision below
└─ ISSUES_FOUND → Return to data-planner for revision
                ↓
            data-planner revises Plan (returns REVISION_COMPLETE + Task Index change summary)
                ↓
            Re-run plan-checker (max 2 iterations)
                ↓
            ├─ PASSED / PASSED_WITH_WARNINGS →
            │       Resync STATE.md to the revised Plan_Tasks.md (BLOCKING, within Gate G4.5):
            │       rebuild Transformation Progress from the revised Task Index;
            │       update Plan/Plan_Tasks paths, Current Stage, Next Actions;
            │       validate (Transformation Progress rows == total_tasks;
            │       every script path in both the table and the Task Index;
            │       no superseded plan-version filename remains).
            │       If any check fails → STOP, fix STATE.md, re-validate.
            │           ↓
            │       Present PSU2, await user confirmation, then proceed to Stage 5
            └─ If still ISSUES_FOUND after 2 attempts → STOP and escalate to user
```

**Record every plan-checker result in STATE.md.** After each plan-checker return, update STATE.md § Plan Validation (Stage 4.5) with the status, run date, revision attempts, and any warnings or blockers (`full-pipeline-mode.md` § "Gate G4.5 Enforcement"). Warnings go there, not into the Plan: the Plan is frozen after Stage 4.5 and has no slot for checker output.

**STATE.md synchronization after revision (blocking).** STATE.md's Transformation Progress table, Current Position paths, and Next Actions are first populated at Stage 4 from the *original* Plan_Tasks.md. A Stage 4.5 revision can change the task count, task names, script paths, or wave structure, which leaves those STATE.md sections stale — a session restart in that window would resume against a dead plan. Before proceeding to Stage 5 after any accepted revision, the orchestrator MUST rebuild them from the revised Plan_Tasks.md Task Index and validate parity (row count against `total_tasks`, script-path correspondence in both directions, and no lingering reference to the superseded plan-version filename). The orchestrator owns this synchronization; subagents never write STATE.md. It is a blocking condition inside Gate G4.5 — not a new gate. See `full-pipeline-mode.md` § "Gate G4.5 Enforcement" and the STATE.md Update Gates table row "Plan revised (accepted revision)" for the field-level specification.

### Gate Criteria (G4.5)

- [ ] Plan validation completed
- [ ] Status is PASSED or PASSED_WITH_WARNINGS
- [ ] STATE.md § Plan Validation (Stage 4.5) updated with the status, run date, revision attempts and any warnings (`full-pipeline-mode.md` § "Gate G4.5 Enforcement")
- [ ] **PSU2 presented to user with Plan summary, exact Plan filepath, clear indication that the user should read the full Plan before approving, and validation results**
- [ ] **User confirmed PSU2 (explicit approval of Plan)**

### Phase Status Update 2 (PSU2): Plan Ready for Approval

**Trigger:** Every G4.5 item above the two PSU2 items is checked (plan-checker PASSED or PASSED_WITH_WARNINGS, STATE.md § Plan Validation updated)
**Blocking:** YES — Stage 5 CANNOT begin until user confirms PSU2

**Important: Summary vs. Full Plan**
The PSU2 checkpoint presents a **high-level summary** of the Plan — not the Plan itself. The full Plan document contains critical detail (exact query specifications, complete transformation sequences with validation criteria, full risk registers, etc.) that cannot be adequately conveyed in a checkpoint summary. The user must be clearly told that reviewing the full Plan file is expected before they approve.

**Actions:**
1. Compile a high-level Plan summary and plan-checker results
2. Present PSU2 to user using the PSU template, headed `**Checkpoint: Planning Complete**`, explicitly framing it as a summary
3. Share the exact Plan.md filepath and clearly tell the user that this summary does not replace reading the full Plan — they should review Plan.md before approving (Plan_Tasks.md contains executable task details and does not require user review)
4. WAIT for explicit user confirmation

**PSU2 Content Requirements (this is a SUMMARY — not the full Plan; the checkpoint MUST include; every item lands in text the user reads, so word it per the Plain-Language Rule in `SKILL.md` § User-Facing Communication Standards):**
- Research question as stated in the Plan
- Methodology summary: statistical approach, key analytical decisions
- Data sources confirmed: dataset identifiers, year ranges, geographic scope
- Transformation sequence overview: number of tasks, wave structure, key joins
- Research Outcomes the analysis will investigate
- Hypotheses (if any) and their basis
- Risk Register highlights: top risks and mitigation strategies
- The plan check's result (passed, or passed with notes), each note explained in plain words
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
> "What I've shared above is a high-level summary. The full plan — with complete query specifications, the planned analysis steps with what each one checks, and the risk register — is at the filepath above. Please read through it before approving. Does the methodology match your intent? Are the research outcomes what you want to investigate? Any variables to add or remove?"

---

## Verification Checklists

Apply this checklist after the data-planner subagent returns the Plan documents (Plan.md + Plan_Tasks.md).

### Stage 4 (Plan Creation) Verification

- [ ] Research question clearly stated (not placeholder)
- [ ] Must-Haves lists 3-7 research outcomes: investigation/measurement objectives that do not pre-specify directional results
- [ ] Hypotheses (if any) are clearly separated from Research Outcomes and include basis citations
- [ ] Candidate Datasets (Phase 1: Discovery Results) and Query Specification complete with dataset identifiers and years
- [ ] Transformation Sequence table has all tasks with waves assigned
- [ ] Every task has explicit file paths (no placeholders like "TBD")
- [ ] Every task has a skill or agent identified
- [ ] Every join task has cardinality specified (1:1, 1:many, many:1)
- [ ] Every task has verifiable "done" condition
- [ ] Risk Register identifies ≥1 risk with mitigation
- [ ] Wave dependencies are correct (no circular dependencies)
- [ ] Validation checkpoints specified for each phase
