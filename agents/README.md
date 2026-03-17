# Specialized Agents

This directory contains behavioral definitions for specialized agents used in the research workflow. Unlike skills (which provide domain knowledge), agents define **behavioral protocols** for specific roles.

All agents in this directory MUST follow the canonical template at `agent_reference/AGENT_TEMPLATE.md`.

---

## Agent vs Skill Distinction

| Aspect | Skill | Agent |
|--------|-------|-------|
| **Purpose** | Provide domain knowledge | Define behavioral protocol |
| **Content** | Reference material, decision trees | Execution patterns, validation rules |
| **Loading** | Subagent calls skill tool | Orchestrator includes agent definition in Agent prompt |
| **Example** | `education-data-source-ccd` (CCD knowledge -- education domain) | `research-executor` (execution protocol -- domain-agnostic) |

**Rule of thumb:** Skills answer "What do I need to know?" Agents answer "How should I behave?"

---

## Code Style: Sequential Inline Python

See `CLAUDE.md` > "Code Style: Sequential Inline Python" for the canonical rules. All agents follow flat, sequential Python with IAT documentation (`agent_reference/INLINE_AUDIT_TRAIL.md`).

### Bash Execution Rule: Single Command Per Call

See `CLAUDE.md` > "Bash Command Rule: One Command Per Call" for the canonical rule. Execution pattern: `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage{N}_{type}/{step}_{task}.py`

---

## Output Size Discipline

**All agents returning output to the orchestrator MUST respect these universal constraints:**

1. **Hard cap: 1000 words maximum** for Agent return output
2. **Do NOT include:** Raw execution logs, data samples, Polars/pandas table displays, full checkpoint output, QA script code, or multi-paragraph explanations in any section
3. **Script files are the archive; the Agent return is the signal.** Execution logs are already appended to script files by `run_with_capture.sh`. Reference files by path — do not reproduce their contents.
4. **Summarize, don't echo.** "CP1 PASSED: 2,528 rows, 12 cols, 0.3% missing" — not the full stdout.

**Why this matters:** The orchestrator context window is shared across the entire pipeline. A single verbose subagent return (2,000+ words) consumes ~4,000 tokens. Over 10 subagent round-trips in a stage, that's 40,000 tokens — 20% of the orchestrator's total capacity — consumed by output alone.

---

## Agent Index

| Agent | Purpose | Subagent Type | Stage(s) | Key Inputs | Key Outputs |
|-------|---------|---------------|----------|------------|-------------|
| **research-executor** | Execute data tasks with atomic precision, rigorous validation, and full audit-trail capture | `general-purpose` | 5, 6, 7, 8 | Task spec XML, Plan.md, skill knowledge, dependency outputs | Script + execution log + data files (parquet) |
| **code-reviewer** | Iterative QA review verifying code correctness, methodology alignment, and output data quality | `general-purpose` | 5-QA, 6-QA, 7-QA, 8-QA | Executed script + log, Plan.md, output data files, stage/step/wave context | QA scripts (cr1-cr5) + severity report (PASSED/WARNING/BLOCKER) |
| **data-planner** | Synthesize discovery findings into research plans with executable task sequences and wave-based parallelization | `general-purpose` | 4 | User request, clarifications, Stage 2-3 findings, project folder path | Plan.md + Plan_Tasks.md documents |
| **plan-checker** | Verify research plans will achieve analysis goals via goal-backward analysis across six dimensions | `Plan` | 4.5 | Plan.md + Plan_Tasks.md content (inlined), original user request, clarifications | Validation report: PASSED / PASSED_WITH_WARNINGS / ISSUES_FOUND |
| **data-verifier** | Adversarial goal-backward verification of completed analyses with cross-artifact coherence | `Plan` | 12 | Plan.md, Notebook, Report, project folder, STATE.md, LEARNINGS.md, QA summary | Verification report: PASSED / ISSUES_FOUND with four-layer evidence; STATE.md Final Review Log |
| **source-researcher** | Deep-dive into a single data source for caveats, coded values, suppression patterns, and pitfalls | `Plan` | 3 | Source name, variables of interest, research question, years, geographic scope | Five-section source report (Summary, Variables, Caveats, Patterns, Pitfalls) |
| **research-synthesizer** | Consolidate parallel Stage 2-3 findings into actionable planning guidance with conflict resolution | `general-purpose` | 3.5 | Stage 2 findings, all Stage 3 findings, research question, year range, geographic scope | Integrated synthesis with conflicts, resolutions, and planning recommendations |
| **debugger** | Diagnose data quality issues and analysis failures using scientific hypothesis-testing methodology | `general-purpose` | Any (on error) | Error message/symptom, failed script path, Plan.md, Plan_Tasks.md (optional), last successful operation | Root cause report with hypothesis log and verified fix |
| **notebook-assembler** | Compile scripts into Marimo notebook via VERBATIM copy (NO dashboards, NO widgets, NO new code) | `general-purpose` | 9 | Completed scripts (stages 5-8), Plan.md, data files, figure files, project path | Marimo `.py` notebook with script walkthroughs and data inspection cells |
| **integration-checker** | Validate component wiring: data flows, file references, and orphan detection | `Plan` | 9, 11, 12 | Plan.md, Notebook, Report, project folder, script-to-output mappings | Integration check report: CONNECTED / ISSUES FOUND with flow diagrams |
| **data-ingest** | Profile new datasets and author comprehensive Skills documenting structure, values, and quality | `general-purpose` | Pre-pipeline (on demand) | Data file path + format, target skill name, intended use, domain context, optional docs | New Skill at `.claude/skills/` + Data Ingest Report |
| **report-writer** | Synthesize pipeline artifacts into stakeholder report following REPORT_TEMPLATE.md | `general-purpose` | 11 | Plan.md, Notebook, STATE.md, LEARNINGS.md, QA summary, figures, citations, dataset metadata | Report.md (stakeholder prose) |

### Commonly Confused Pairs

When adding a new agent, ensure it doesn't overlap with these frequently confused pairs. Each new agent's Core Distinction table (Section 2 of the template) must differentiate from its closest neighbor(s).

| Pair | How They Differ |
|------|----------------|
| **code-reviewer** vs **data-verifier** | Reviewer validates individual scripts *during* execution (Stages 5-8); verifier performs adversarial whole-analysis check *after* completion (Stage 12) |
| **code-reviewer** vs **debugger** | Reviewer validates *correctness* of working code; debugger diagnoses *failures* when code doesn't work |
| **source-researcher** vs **research-synthesizer** | Researcher examines a *single* source in depth; synthesizer *combines* findings across multiple sources |
| **source-researcher** vs **data-ingest** | Researcher examines *existing* skills for a known source; ingest *creates new* skills from raw data files |
| **data-planner** vs **plan-checker** | Planner *creates* plans; checker *validates* plans (never fixes them) |
| **notebook-assembler** vs **integration-checker** | Assembler *builds* the notebook (verbatim script compilation); checker *verifies* wiring between components |
| **report-writer** vs **research-synthesizer** | Writer synthesizes *post-execution* artifacts into a stakeholder report (Stage 11); synthesizer combines *pre-execution* research findings into planning guidance (Stage 3.5) |

---

## Orchestration Flow

This diagram shows how agents interact throughout the pipeline:

```
                                USER REQUEST
                                     |
                                     v
                    +---------------------------------+
                    |   PHASE 1: DISCOVERY & SCOPING  |
                    |    (Orchestrator coordinates)   |
                    +---------------------------------+
                                     |
                    +----------------+----------------+
                    v                                 v
         +--------------------+             +--------------------+
         | source-researcher  |             | source-researcher  |
         |     (Source A)     |             |     (Source B)     |
         |      [Stage 3]     |             |      [Stage 3]     |
         +----------+---------+             +---------+----------+
                    |                                 |
                    +----------------+----------------+
                                     v
                    +---------------------------------+
                    |       research-synthesizer      |
                    |      [Stage 3.5 - synthesis]    |
                    +----------------+----------------+
                                     |
                    +---------------------------------+
                    |        PHASE 2: PLANNING        |
                    +---------------------------------+
                                     v
                    +---------------------------------+
                    |           data-planner          |
                    |            [Stage 4]            |
                    +----------------+----------------+
                                     |
                    +---------------------------------+
                    |       PLAN VALIDATION LOOP      |
                    +---------------------------------+
                                     v
                    +---------------------------------+
                    |           plan-checker          |<---------+
                    |           [Stage 4.5]           |          |
                    +----------------+----------------+          |
                                     |                           |
                    +----------------+----------------+          |
                    |                |                |          |
                    v                v                v          |
                  PASSED          WARNINGS         BLOCKED       |
                    |                |                |          |
                    |                |                v          |
                    |                |       +-----------------+ |
                    |                |       |   data-planner  | |
                    |                |       |    (revision)   |-+
                    |                |       +-----------------+
                    |                |                |
                    |                |                v
                    |                |       (max 2 iterations,
                    |                |     then escalate to user)
                    |                |
                    +----------------+----------------+
                                     v
                    +---------------------------------+
                    |  PHASE 3: DATA ACQUISITION &    |
                    |           PREPARATION           |
                    |  PHASE 4: ANALYSIS & NOTEBOOK   |
                    |           DEVELOPMENT           |
                    |      (research-executor +       |
                    |        code-reviewer QA)        |
                    +----------------+----------------+
                                     |
         +-----------+---------------+---------------+-----------+
         |           |                               |           |
         v           v                               v           v
    +---------+ +---------+                     +---------+ +---------+
    | Stage 5 | | Stage 6 |                     | Stage 7 | | Stage 8 |
    | (fetch) | | (clean) |                     | (trans) | |(ana&viz)|
    |   CP1   | |   CP2   |                     |  CP3xN  | |QA4a/4b |
    +----+----+ +----+----+                     +----+----+ +----+----+
         |           |                               |           |
         v           v                               v           v
    +---------+ +---------+                     +---------+ +---------+
    | Stage 5 | | Stage 6 |                     | Stage 7 | | Stage 8 |
    |   QA    |>|   QA    |>                    |   QA    |>|   QA    |
    | (review)| | (review)|                     | (review)| | (review)|
    +----+----+ +----+----+                     +----+----+ +----+----+
         |           |                               |           |
         | BLOCKER?  | BLOCKER?                      | BLOCKER?  | BLOCKER?
         +->Rev-+    +->Rev-+                        +->Rev-+    +->Rev-+
         |      |    |      |                        |      |    |      |
         |<-----+    |<-----+                        |<-----+    |<-----+
         |           |                               |           |
         | (error)   | (error)                       | (error)   | (error)
         +-----+-----+------+--------+---------------+----+------+
               v            v        v                    |
         +-------------+ +-----------+                    |
         |  debugger   | |   USER    |<-------------------+
         |  (diagnose) |>|(escalate) |
         +-------------+ +-----------+
                                     |
                                     v
                    +----------------+----------------+
                    |        notebook-assembler       |
                    |           [Stage 9]             |
                    +----------------+----------------+
                                     |
                                     v
                    +----------------+----------------+
                    |    QA Aggregation [Stage 10]    |
                    +----------------+----------------+
                                     |
                                     v
                    +----------------+----------------+
                    |          report-writer          |
                    |           [Stage 11]            |
                    +----------------+----------------+
                                     |
                                     v
                    +----------------+----------------+
                    |  PHASE 5: SYNTHESIS & DELIVERY  |
                    +----------------+----------------+
                                     |
                    +----------------+----------------+
                    v                                 v
         +---------------------+            +--------------------+
         | integration-checker |            |   data-verifier    |
         |   [Stage 9,11,12]   |            |     [Stage 12]     |
         +----------+----------+            +--------------------+
                    |                                 |
                    +----------------+----------------+
                                     v
                                 DELIVERY
```

---

## Plan Validation Loop (plan-checker <-> data-planner)

When plan-checker identifies issues, the revision loop executes:

```
data-planner creates Plan
         |
         v
plan-checker validates
         |
    +----+----+
    |         |
 PASSED    ISSUES
    |         |
    v         v
Stage 5   Categorize issues
              |
    +---------+---------+
    |                   |
 WARNINGS           BLOCKERS
    |                   |
    v                   v
Document &         data-planner
 proceed           revises Plan
    |                   |
    v                   v
 Stage 5           plan-checker
                  validates again
                        |
             +----------+----------+
             |                     |
          PASSED              STILL BLOCKED
             |                     |
             v                     v
          Stage 5            (iteration 2?)
                                   |
                        +----------+----------+
                        |                     |
                     Yes (retry)         No (max reached)
                        |                     |
                        v                     v
                  data-planner         ESCALATE TO USER
                  revises again
```

**Iteration Limits:**
- Maximum 2 revision cycles before escalating to user
- Each revision must address specific issues identified by plan-checker
- If same issues persist after 2 revisions, user intervention required

---

## Agent Coordination Matrix

Shows which agents produce output consumed by other agents:

| Producer Agent | Consumer Agent(s) | Data Produced | When |
|----------------|-------------------|---------------|------|
| **source-researcher** | research-synthesizer | Five-section source report (per source) | Multi-source analyses |
| **source-researcher** | data-planner | Five-section source report | Single-source analyses |
| **research-synthesizer** | data-planner | Integrated synthesis with conflict resolutions and recommendations | Multi-source analyses |
| **data-planner** | plan-checker | Plan.md + Plan_Tasks.md documents | Always (Stage 4 -> 4.5) |
| **plan-checker** | data-planner | Issues report (YAML format with dimension, severity, details) | When ISSUES_FOUND with blockers |
| **plan-checker** | Orchestrator | Validation status (PASSED / PASSED_WITH_WARNINGS / ISSUES_FOUND) | Always |
| **research-executor** | code-reviewer | Executed script + appended execution log + output data files | After every Stage 5-8 script |
| **research-executor** | debugger | Failed script + error context + last successful operation | On failure |
| **code-reviewer** | Orchestrator | QA report with severity (PASSED / WARNING / BLOCKER) | After every script review |
| **code-reviewer** | research-executor | Revision request with BLOCKER details | When BLOCKER found |
| **code-reviewer** | Orchestrator | QA findings log (accumulated WARNINGs) | For aggregation |
| **debugger** | research-executor | Root cause diagnosis + verified fix + prevention recommendation | After diagnosis |
| **debugger** | Orchestrator | Escalation (when UNRESOLVED or methodology issue) | Undiagnosed issues |
| **research-executor** (Stage 8) | notebook-assembler | Scripts + data files + analysis results + figures | After Stage 8 completes |
| **notebook-assembler** | integration-checker | Marimo notebook (VERBATIM script copies, NO new code) | After Stage 9 compilation |
| **integration-checker** | data-verifier | Wiring status (CONNECTED / ISSUES FOUND) | Stages 9, 11, 12 |
| **data-verifier** | Orchestrator | Verification report (PASSED / ISSUES_FOUND with four-layer evidence) | Before delivery |
| **report-writer** | integration-checker | Report.md (stakeholder report following REPORT_TEMPLATE.md) | After Stage 11 completes |
| **report-writer** | data-verifier | Report.md (stakeholder report) | Before Stage 12 verification |
| **report-writer** | Orchestrator | Status report (COMPLETE / COMPLETE_WITH_GAPS / BLOCKED) | After report generation |
| **data-ingest** | Orchestrator | New Skill at `.claude/skills/` + Data Ingest Report | Pre-pipeline, on demand |

---

## Error Recovery Routing

When errors occur, this routing determines which agent handles recovery:

```
ERROR DETECTED
      |
      +- Data issue (empty, wrong shape)?
      |       +-> research-executor retry (max 2)
      |               +-> debugger (if still failing)
      |
      +- QA BLOCKER found (code-reviewer)?
      |       +-> Is it a methodology issue?
      |               +-> YES -> ESCALATE to user immediately
      |               +-> NO -> research-executor revision
      |                       +-> code-reviewer re-reviews
      |                               +-> Resolved -> Proceed
      |                               +-> Still BLOCKER after 2 attempts -> ESCALATE
      |
      +- Transformation issue (unexpected row loss)?
      |       +-> debugger
      |               +-> Fix identified -> research-executor applies fix
      |               +-> Root cause unclear -> ESCALATE to user
      |
      +- Plan issue (missing section, ambiguous task)?
      |       +-> data-planner (revision)
      |               +-> plan-checker validates
      |
      +- Integration issue (broken references)?
      |       +-> integration-checker diagnoses
      |               +-> Orchestrator coordinates fix
      |
      +- Verification failure (stub detected, missing artifact)?
              +-> data-verifier documents
                      +-> Orchestrator coordinates completion
```

**Error Budget:**
- research-executor: 2 retries per task before debugger
- code-reviewer: 2 revision cycles per script before escalation
- debugger: 2 diagnostic cycles before escalation
- data-planner: 2 revision cycles before escalation
- Any agent: Context degradation -> Compress and continue or restart

**QA BLOCKER Types:**

| Type | Definition | Revision Attempts | Action |
|------|------------|-------------------|--------|
| **Technical BLOCKER** | Code produces wrong results due to bug (wrong filter, bad join) | 2 | research-executor revises, code-reviewer re-reviews |
| **Methodology BLOCKER** | Code implements wrong approach (wrong data source, invalid comparison) | 0 | Escalate immediately to user |

**Distinction:** Technical BLOCKERs are fixable by correcting code. Methodology BLOCKERs require user decision because the fundamental approach is questionable.

---

## When to Use Each Agent

> **Canonical invocation templates.** This section is the single source of truth for generic agent invocation patterns. Individual agent `.md` files point here for their `## Invocation` section. Stage-specific templates with richer context fields live in the corresponding `agent_reference/WORKFLOW_PHASE*.md` files.

### research-executor

**Use when:** Executing data acquisition, cleaning, transformation, or visualization tasks in Stages 5-8. Each invocation performs exactly ONE operation with pre/post validation.

**CRITICAL: File-First Protocol Required**

This agent MUST follow the file-first execution pattern:
1. Write script to `scripts/stage{N}_{type}/` BEFORE execution
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. Version failed scripts with `_a`, `_b`, `_c` suffixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

**Key behaviors:**
- **File-first execution** (no interactive Python)
- Atomic execution (one operation at a time)
- Pre/post state capture
- Checkpoint integration (CP1-CP4)
- Immutable versioning (never modify after execution log appended)

**Invocation pattern:**
```python
Agent({
    description: "Stage [N]: [Task Name]",
    prompt: """You are a Research Executor. Follow the protocol in
    `{BASE_DIR}/agents/research-executor.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    Call the skill tool with name 'data-scientist'.
    Then, call the skill tool with name '[domain-skill-name]'.

    **CONTEXT:**
    Research Question: [verbatim]
    Plan Path: {BASE_DIR}/research/[project]/[Plan filename]
    Risk Register Items: [relevant items]
    Expected Row Count: [range] | Critical Columns: [list]

    **TASK:**
    <task name="[task-name]" type="auto" wave="[N]">
      <depends_on>[deps]</depends_on>
      <skill>[skill]</skill>
      <files><input>[abs path]</input><output>[abs path]</output></files>
      <action>1. [Step 1] 2. [Step 2] 3. [Step 3]</action>
      <verify>[Criterion 1]; [Criterion 2]</verify>
      <done>[Measurable completion condition]</done>
    </task>

    Return findings using the Research Executor Output Format.""",
    subagent_type: "general-purpose"
})
```

---

### data-planner

**Use when:** Creating or refining the research Plan document at Stage 4, or handling plan revisions when plan-checker or user identifies issues.

**Key behaviors:**
- Requirements-driven planning (backward from Research Outcomes)
- Task specificity test (every task unambiguous for any agent)
- Wave-based sequencing for parallel execution
- Dependency mapping

**Invocation pattern:**
```python
Agent({
    description: "Stage 4: Plan Creation",
    prompt: """You are a Data Planner. Follow the protocol in
    `{BASE_DIR}/agents/data-planner.md`.

    Call the skill tool with name 'data-scientist'.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    Read `{BASE_DIR}/agent_reference/PLAN_TEMPLATE.md` for the plan template.

    **ORIGINAL USER REQUEST:**
    {verbatim_user_request}

    **CLARIFICATIONS:**
    {clarifications}

    **STAGE 2 FINDINGS:**
    {stage_2_exploration_findings}

    **STAGE 3 FINDINGS:**
    {stage_3_source_deep_dive_findings}

    **PROJECT FOLDER:** {project_folder_path}
    **DATE PREFIX:** {date_prefix}

    **TASK:**
    Create a comprehensive research plan. Write Plan.md to the project
    folder. Return findings using the Data Planner Output Format.

    [If revision mode:]
    <revision_context>
    {checker_issues_yaml}
    </revision_context>
    Read existing Plan at {existing_plan_path} before making changes.
    """,
    subagent_type: "general-purpose"
})
```

---

### data-verifier

**Use when:** Final review before delivery (Stage 12), or verifying specific artifacts. Performs adversarial goal-backward verification with cross-artifact coherence checks.

**Key behaviors:**
- Adversarial goal-backward verification (skeptical, not checklist-driven)
- Four-level checks: Existence -> Substantive -> Wired -> Coherent
- Cross-artifact coherence verification (data, notebook, report tell same story)
- Research question stress test
- Independent assessment before Plan anchoring
- Stub detection and silent failure audit

**Invocation pattern:**
```python
Agent({
    description: "Stage 12: Final Verification",
    prompt: """You are a Data Verifier. Follow the protocol in
    `{BASE_DIR}/agents/data-verifier.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    - Research question (verbatim): {research_question}
    - Plan path: {plan_path}
    - Notebook path: {notebook_path}
    - Report path: {report_path}
    - Project folder: {project_folder}
    - STATE.md path: {state_path}
    - LEARNINGS.md path: {learnings_path}
    - QA Summary findings: {qa_summary_or_path}

    **TASK:**
    Perform adversarial goal-backward verification of the completed
    analysis. Verify all four layers (existence, substantiveness,
    wiring, coherence). Perform research question stress test,
    Telephone Game trace, alternative interpretation probing, silent
    failure audit, and QA history review.

    Return findings using the Data Verifier Output Format.""",
    subagent_type: "Plan"
})
```

---

### research-synthesizer

**Use when:** Multiple data sources or exploration tasks need consolidation (Stage 3.5, after all per-source research completes).

**Key behaviors:**
- Multi-source integration with explicit conflict resolution
- Opinionated recommendations (not just descriptions)
- Uncertainty documentation with confidence levels
- Actionable guidance structured for data-planner consumption

**Invocation pattern:**
```python
Agent({
    description: "Stage 3.5: Research Synthesis",
    prompt: """You are a Research Synthesizer. Follow the protocol in
    `{BASE_DIR}/agents/research-synthesizer.md`.

    Call the skill tool with name 'data-scientist'.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    Research question: [verbatim research question]
    Year range: [exact range, e.g., "2019-2023"]
    Geographic scope: [e.g., "national", "California only"]
    Sources identified in Stage 2: [count and names]

    **STAGE 2 FINDINGS:**
    [Full Stage 2 output from domain explorer skill]

    **STAGE 3a FINDINGS ([source name]):**
    [Full Stage 3a output from source-researcher]

    **STAGE 3b FINDINGS ([source name]):**
    [Full Stage 3b output from source-researcher]

    **TASK:**
    Synthesize all Stage 2-3 findings into unified planning guidance.
    Resolve all conflicts. Flag LOW confidence items.
    Produce actionable recommendations for data-planner.

    Return findings using the Research Synthesizer Output Format.""",
    subagent_type: "general-purpose"
})
```

---

### debugger

**Use when:** Something fails and root cause is unclear, or code-reviewer identifies complex issues requiring root-cause analysis.

**Key behaviors:**
- Scientific hypothesis testing (max 5 cycles)
- Binary search for issue isolation
- Systematic evidence collection
- Falsifiable hypothesis formation
- Documented elimination process

**Invocation pattern:**
```python
Agent({
    description: "Debug: Stage {N} - {error_description}",
    prompt: """You are a Debugger. Follow the protocol in
    `{BASE_DIR}/agents/debugger.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    - Error: {error_message_verbatim}
    - Stage: {stage_number}, Step: {step_number}
    - Failed script: {absolute_script_path}
    - Last successful operation: {last_success_description}
    - Plan: {absolute_plan_path}
    - Plan Tasks: {absolute_plan_tasks_path} (for task specification context)
    [If QA-triggered:]
    - QA Report: {qa_report_path}
    - BLOCKER check: {specific_check_that_failed}

    **TASK:**
    Diagnose the root cause of this failure. Follow the scientific
    debugging method (max 5 hypothesis cycles). Save diagnostic
    scripts to scripts/debug/. Return findings using the Debugger
    Output Format.""",
    subagent_type: "general-purpose"
})
```

---

### plan-checker

**Use when:** Validating a plan before execution begins (Stage 4.5, between Plan creation and Stage 5). Performs goal-backward analysis across six dimensions.

**Key behaviors:**
- Six-dimension validation (Completeness, Consistency, Feasibility, Testability, Clarity, Scope)
- Goal-backward verification (starts from research outcome, works backward)
- Task specificity testing
- Blocking issue identification
- Non-blocking (identifies issues but doesn't fix)
- Methodology precision enforcement

**Invocation pattern:**
```python
Agent({
    description: "Stage 4.5: Plan Verification",
    prompt: """You are a Plan Checker. Follow the protocol in
    `{BASE_DIR}/agents/plan-checker.md`.

    Call the skill tool with name 'data-scientist'.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **PLAN.MD CONTENT:**
    {inline the full Plan.md content here}

    **PLAN_TASKS.MD CONTENT:**
    {inline the full Plan_Tasks.md content here}

    **ORIGINAL REQUEST:**
    {inline the original user request verbatim}

    **CLARIFICATIONS:**
    {inline any user clarifications, or "None"}

    Validate the plan across all six dimensions (Completeness, Consistency,
    Feasibility, Testability, Clarity, Scope). Return structured report with
    per-dimension confidence and issues in YAML format.

    Return findings using the Plan Checker Output Format.""",
    subagent_type: "Plan"
})
```

---

### source-researcher

**Use when:** Deep-diving into a single data source's caveats, patterns, and pitfalls (Stage 3, one invocation per source identified in Stage 2).

**Key behaviors:**
- Single-source focus (one source per invocation)
- Five-deliverable output contract (Summary, Variables, Caveats, Patterns, Pitfalls)
- Confidence assessment per section
- Pitfall identification with mitigation
- Truth Hierarchy application for discrepancies

**Invocation pattern:**
```python
Agent({
    description: "Stage 3: Research [Source] source",
    prompt: """You are a Source Researcher. Follow the protocol in
    `{BASE_DIR}/agents/source-researcher.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    Call the skill tool with name 'data-scientist'.
    Then, call the skill tool with name '[domain-source-skill-name]'.

    **CONTEXT:**
    Research question: [verbatim question from Stage 1]
    Variables of interest: [list from Stage 2, with flagging reasons]
    Years needed: [exact start year]-[exact end year]
    Geographic scope: [national / state list / single state]

    **SPECIFIC INVESTIGATION NEEDS:**
    - [Variable flagged for deep-dive from Stage 2]
    - [Specific caveat question from Stage 2]

    **TASK:**
    Produce the five-section source research report with confidence
    assessment per section. Flag any LOW confidence findings with
    verification recommendations. Apply the Truth Hierarchy if any
    discrepancies are found between skill docs and other sources.

    Return findings using the Source Researcher Output Format.""",
    subagent_type: "Plan"
})
```

---

### notebook-assembler

**Use when:** Stage 8 is complete and it's time to compile scripts into a marimo notebook (Stage 9).

**Purpose:** LITERALLY COPY script file contents into marimo cells. The notebook is a script viewer, NOT a dashboard.

**CRITICAL CONSTRAINT:** This agent COPIES files. It does NOT generate new code, dashboards, filters, or interactive widgets. If you see dropdowns, sliders, or new aggregations in the output, the agent FAILED.

**What this agent IS:**
- A file compiler (read files, copy contents)
- A copy-paste machine with formatting
- A script viewer

**What this agent is NOT:**
- A dashboard builder
- An analysis tool
- An interactive explorer

**Key behaviors:**
- READ script files from `scripts/`
- COPY code VERBATIM into code cells (commented out with `# ` prefix)
- COPY execution logs VERBATIM into accordion cells
- ADD ONLY `pl.read_parquet() + mo.ui.table()` cells
- Applies the Four-Cell Pattern per script (header, commented code, log accordion, data load)

**PROHIBITIONS (agent FAILED if output contains):**
- `mo.ui.dropdown()` -- NO dropdowns
- `mo.ui.slider()` -- NO sliders
- `mo.ui.multiselect()` -- NO multiselects
- `.group_by()` outside script code -- NO new aggregations
- `.pivot()` outside script code -- NO new pivots
- `.filter()` in data cells -- NO filtering
- `.with_columns()` in data cells -- NO transforms

**Invocation pattern:**
```python
Agent({
    description: "Stage 9: Notebook Assembly",
    prompt: """You are a Notebook Assembler. Follow the protocol in
    `{BASE_DIR}/agents/notebook-assembler.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    - Project path: {project_path}
    - Plan path: {plan_path}
    - Research question: {research_question}
    - Date prefix: {date_prefix}
    - Scripts directory: {scripts_dir}

    **TASK:**
    Compile all scripts from scripts/stage{5,6,7,8}_*/ into a
    Marimo notebook at {notebook_path}. Apply the Four-Cell Pattern
    per script (header, commented code, log accordion, data load).
    NO new analysis code. NO dashboards. NO widgets.
    Test with marimo run before reporting.

    Return findings using the Notebook Assembler Output Format.""",
    subagent_type: "general-purpose"
})
```

**What notebook-assembler produces:**
- Marimo notebook with navigation (markdown only)
- VERBATIM script code in code cells (commented out)
- VERBATIM execution logs in accordion cells
- Simple data load + display cells (THE ONLY NEW CODE)

**Verification:** If output contains `mo.ui.dropdown`, `mo.ui.slider`, `group_by` outside scripts, or `filter` in data cells -> REJECT and re-run

---

### report-writer

**Use when:** Generating the stakeholder report at Stage 11, after QA aggregation (Stage 10) confirms no unresolved BLOCKERs.

**Key behaviors:**
- Follows REPORT_TEMPLATE.md section by section using a systematic Section-Source Mapping
- Reads the full pipeline artifact set: Plan, Notebook, STATE.md, LEARNINGS.md, QA summary, figures, citations
- Every statistic must trace to an execution log or dataset metadata — never hallucinated
- Cross-checks all Research Outcomes from Plan against Key Findings
- Verifies all figure file paths resolve before embedding references

**Invocation pattern:**

```python
Agent({
    description: "Stage 11: Report Generation",
    prompt: """You are a Report Writer. Follow the protocol in
    `{BASE_DIR}/agents/report-writer.md`.

    Call the skill tool with name 'data-scientist'.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    - Project path: {project_path}
    - Plan path: {plan_path}
    - Notebook path: {notebook_path}
    - STATE.md path: {state_path}
    - LEARNINGS.md path: {learnings_path}
    - Date prefix: {date_prefix}
    - Report filename: {report_filename}

    **STAGE 10 QA SUMMARY:**
    {qa_summary_text}

    **CITATION TEXT (from Stage 6):**
    {citation_text}

    **ANALYSIS DATASET METADATA:**
    {dataset_metadata}

    **FIGURE FILES:**
    {figure_file_list}

    **TASK:**
    Generate the stakeholder report following REPORT_TEMPLATE.md.
    Read the Plan, Notebook, STATE.md, and LEARNINGS.md.
    Follow the Section-Source Mapping for every section.
    Verify all figure references before embedding.
    Cross-check all Research Outcomes from the Plan.
    Write Report.md to the project folder.

    Return findings using the Report Writer Output Format.""",
    subagent_type: "general-purpose"
})
```

---

### integration-checker

**Use when:** Verifying connections between components work (Stages 9, 11, 12). Traces data flows from raw inputs to final outputs, ensures nothing is orphaned, broken, or disconnected.

**Key behaviors:**
- Flow tracing (source to output through complete pipeline)
- Reference validation (notebook->data, report->figures)
- Export/import mapping
- Orphan detection
- E2E flow verification

**Invocation pattern:**
```python
Agent({
    description: "Stage [9|11|12]: Integration Check",
    prompt: """You are an Integration Checker. Follow the protocol in
    `{BASE_DIR}/agents/integration-checker.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    - Plan path: {plan_path}
    - Notebook path: {notebook_path}
    - Report path: {report_path}
    - Project folder: {project_folder}
    - Execution scripts: {list of script paths with their output files}
    - Expected figures: {list of expected figure paths}

    **TASK:**
    Verify all components are properly connected:
    1. Map expected data flow from Plan
    2. Verify all file references resolve (notebook->data, report->figures)
    3. Verify stage-to-stage transitions are connected
    4. Trace at least one E2E flow from raw data to Report
    5. Detect orphaned components
    6. Verify QA script coverage
    7. Verify data source coverage

    Return findings using the Integration Checker Output Format.""",
    subagent_type: "Plan"
})
```

---

### code-reviewer

**Use when:** After research-executor completes any script in Stages 5-8.

**Purpose:** Perform secondary QA review to verify:
- Code correctness (does it do what it claims?)
- Methodology alignment (does it match the Plan?)
- Validation robustness (are checks comprehensive?)
- Output data quality (is the data correct?)

**Key behaviors:**
- Adversarial stance (default hypothesis: something is wrong)
- Three-phase review (code, execution log, iterative output data inspection)
- Creates iterative QA scripts in `scripts/cr/` (cr1 always; cr2-cr5 when warranted)
- Severity classification (BLOCKER/WARNING/INFO)
- Never fixes code directly (reviewer, not executor)

**Invocation timing:**
```
research-executor completes task
         |
    [Primary CP validation passed]
         |
orchestrator invokes code-reviewer  <-- HERE
         |
code-reviewer returns QA report
         |
    [Severity?]
     +- None/INFO -> Proceed to next task
     +- WARNING -> Log, proceed, flag for Stage 10
     +- BLOCKER -> Trigger revision flow
```

**Invocation pattern:**
```python
Agent({
    description: "QA Review: Stage {N} Step {step} - {task_name}",
    prompt: """You are a Code Reviewer. Follow the protocol in
    `{BASE_DIR}/agents/code-reviewer.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **SCRIPT TO REVIEW:**
    Path: {script_path}

    **PLAN LOCATION:**
    {plan_path}

    **OUTPUT FILES:**
    {output_files}

    **CONTEXT:**
    - Stage: {stage}
    - Step: {step}
    - Wave: {wave}
    - Task: {task_name}
    - Research Question: {research_question}

    **TASK:**
    1. Review the executed script for correctness and methodology alignment
    2. Review the execution log for outcome verification
    3. Create cr1 at scripts/cr/stage{N}_{step}_cr1.py with 5 default +
       5 script-specific + 5 spot-checks + profiling
    4. Execute cr1 and review output (including profiling)
    5. DECIDE: If anomalies found, create cr2..cr5 as needed
       (each with trigger + hypothesis)
    6. Synthesize findings across all iterations into Investigation Narrative
    7. Return QA report with severity classification

    **PRIOR QA FINDINGS (if any):**
    {prior_cr_warnings}

    Return findings using the code-reviewer Output Format.""",
    subagent_type: "general-purpose"
})
```

**Revision flow (when BLOCKER):**
```
code-reviewer returns BLOCKER
         |
    [Is methodology issue?]
     +- YES -> ESCALATE to user immediately
     +- NO -> research-executor creates revision (_a.py)
                 |
         code-reviewer re-reviews
                 |
         [Still BLOCKER?]
          +- NO -> Proceed
          +- YES -> Revision attempt 2 (_b.py)
                       |
               [After 2 attempts, still BLOCKER?]
                +- YES -> ESCALATE to user
```

---

### data-ingest

**Use when:** User provides a new data file (CSV, parquet, Excel, TSV) for profiling and integration into the workflow.

**Purpose:** Exhaustively profile new datasets and create comprehensive Skills that document:
- Data structure, types, and quality characteristics
- Coded values and their meanings
- **Preliminary semantic interpretations** (variable meanings, flagged for user review)
- Discrepancies between documentation and actual data
- Usage patterns and loading examples

**Key behaviors:**
- Two-mode investigation: Deductive (data -> understanding) + Documentation reconciliation (docs -> verification)
- **Semantic interpretation:** Infers likely variable meanings from names, values, patterns (marked PRELIMINARY)
- **Website documentation support:** Can fetch and parse documentation from provided URLs
- Data file is source of truth; documentation claims are verified against data
- Creates complete skill with references and archived profiling scripts
- Reports all discrepancies AND preliminary interpretations for user review

**Invocation pattern:**
```python
Agent({
    description: "Ingest: {data_name}",
    prompt: """You are a Data Ingest Specialist. Follow the protocol in
    `{BASE_DIR}/agents/data-ingest.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    First, call the skill tool with name 'skill-authoring' to understand
    generic skill structure. Then read
    `{BASE_DIR}/agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md` for the
    canonical data source skill section order. The template OVERRIDES the
    generic skill-authoring layout.

    **DATA FILE:**
    Path: {data_file_path}
    Format: {csv | parquet | xlsx | tsv}

    **DOCUMENTATION FILES:** (if any)
    - {doc_path_1}: {description}

    **DOCUMENTATION WEBSITE:** (if any)
    URL: {website_url}
    Description: {what information is available there}

    **SKILL CONFIGURATION:**
    Target skill name: {skill-name}
    Intended use: {how the data will be used}
    Priority columns: {columns requiring extra attention}
    Domain context: {domain for semantic interpretation}

    **TASK:**
    1. Profile the data file exhaustively (Mode 1: Phases 1-5)
    2. Generate preliminary semantic interpretations (Phase 5)
    3. Fetch website documentation (if URL provided)
    4. Read and reconcile local documentation (Mode 2: if docs provided)
    5. Create complete skill at `.claude/skills/{skill-name}/`
    6. Report all discrepancies AND preliminary interpretations for review

    Return findings using the Data Ingest Output Format.""",
    subagent_type: "general-purpose"
})
```

---

## Agent + Skill Combinations

Some tasks benefit from combining an agent protocol with skill knowledge. The domain-specific skills shown below are from the education demonstration domain -- substitute the appropriate domain skills for your data domain.

| Task | Agent | Skill(s) |
|------|-------|----------|
| Explore data (Stage 2) | (Plan subagent) | data-scientist, *domain explorer* (e.g., education-data-explorer) |
| Source deep-dive (Stage 3) | source-researcher | data-scientist, *domain source skill* (e.g., education-data-source-*) |
| Synthesize findings (Stage 3.5) | research-synthesizer | data-scientist |
| Create analysis plan (Stage 4) | data-planner | data-scientist |
| Validate plan (Stage 4.5) | plan-checker | data-scientist |
| Fetch data (Stage 5) | research-executor | data-scientist, *domain query skill* (e.g., education-data-query) |
| Clean data (Stage 6) | research-executor | data-scientist, *domain context skill* (e.g., education-data-context) |
| Transform data (Stage 7) | research-executor | data-scientist, polars |
| Conduct analyses and create visualizations (Stage 8) | research-executor | data-scientist, polars, plotnine/plotly |
| Compile notebook (Stage 9) | notebook-assembler | data-scientist, marimo |
| Generate report (Stage 11) | report-writer | data-scientist |
| Final verification (Stage 12) | data-verifier | data-scientist |
| Diagnose failure (any) | debugger | data-scientist, polars |
| Ingest new dataset (pre-pipeline) | data-ingest | skill-authoring, polars |

**Invocation pattern for combined** *(education domain example -- substitute domain-specific skill names)*:
```python
Agent({
    description: "Stage 6: Clean CCD data",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    Also load the skill 'education-data-context' for coded value handling.

    [Task specification]
    """,
    subagent_type: "general-purpose"
})
```

---

## Orchestrator Responsibilities

The orchestrator (main conversation) remains responsible for:
- Mode classification (Full Pipeline, Discovery, etc.)
- High-level progress tracking
- User communication
- Agent invocation decisions
- Context management (staying lean)

Agents handle:
- Focused task execution
- Protocol adherence
- Detailed validation
- Structured reporting

---

## Adding New Agents

> **Comprehensive guide:** Use the `agent-authoring` skill for full guidance including section-by-section walkthrough, cross-agent standards, and a complete integration checklist covering every file that needs updating. The summary below provides a quick orientation.

### Quick Summary

1. **Design:** Identify the agent's role, pipeline stage, subagent type, and similar agents to differentiate from (see "Commonly Confused Pairs" above)
2. **Author:** Create `agents/[agent-name].md` following `agent_reference/AGENT_TEMPLATE.md` (12 mandatory sections)
3. **Integrate:** Update all registry files — use the `agent-authoring` skill's integration checklist for the complete list
4. **Validate:** Verify the agent appears in all registry files and cross-agent standards are met

### Required Frontmatter

```yaml
---
name: agent-name-here
description: >
  [Third person. What it does AND when to use it.]
tools: [Read, Write, Edit, Bash, Glob, Grep]   # Explicit allowlist. Omit for all.
permissionMode: default                          # Or: plan (read-only agents)
---
```

### Required Body Sections (12 total)

| # | Section | Key Requirements |
|---|---------|-----------------|
| 1 | Title and Purpose | H1 + one-sentence purpose + invocation type |
| 2 | Identity and Philosophy | Role, philosophy maxim, **Core Distinction table** |
| 3 | Upstream Inputs | `<upstream_input>` tags, orchestrator checklist |
| 4 | Core Behaviors | 3-7 numbered principles (not steps) |
| 5 | Execution Protocol | Sequential steps + decision points |
| 6 | Output Format | Status, Confidence (H/M/L), Learning Signal, Recommendations |
| 7 | Downstream Consumers | `<downstream_consumer>` tags, severity-to-action mapping |
| 8 | Boundaries | Always/Ask/Never tiers + STOP Conditions |
| 9 | Anti-Patterns | `<anti_patterns>` tags, 3-column table (min 5) |
| 10 | Quality and Completion | COMPLETE/INCOMPLETE criteria + Self-Check |
| 11 | Invocation Pattern | Exact Agent() syntax with BASE_DIR |
| 12 | References | CONDITIONAL — only when agent references external files |

### Integration Checklist (Abbreviated)

After writing the agent file, update these registries at minimum:

- [ ] `agents/README.md` — Agent Index + "When to Use" section + Coordination Matrix
- [ ] `agents/README.md` — Agent catalog table (canonical Specialized Agents registry) + `full-pipeline.md` > Skill-to-Stage Mapping (if stage-specific)
- [ ] `README.md` — Agent Ecosystem table + update agent count

For the **complete 29-item integration checklist** (including conditional workflow and narrative updates), invoke the `agent-authoring` skill and read `references/integration-checklist.md`.

**Naming convention:** `lowercase-hyphenated.md`

**Target length:** 400-700 lines per agent (never exceed 1000).
