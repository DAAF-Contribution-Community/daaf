# Specialized Agents

This directory contains behavioral definitions for specialized agents used in the research workflow. Unlike skills (which provide domain knowledge), agents define **behavioral protocols** for specific roles.

---

## Agent vs Skill Distinction

| Aspect | Skill | Agent |
|--------|-------|-------|
| **Purpose** | Provide domain knowledge | Define behavioral protocol |
| **Content** | Reference material, decision trees | Execution patterns, validation rules |
| **Loading** | Subagent calls skill tool | Orchestrator includes agent definition in Task prompt |
| **Example** | `education-data-source-ccd` (CCD knowledge) | `research-executor` (execution protocol) |

**Rule of thumb:** Skills answer "What do I need to know?" Agents answer "How should I behave?"

---

## Code Style: Sequential Inline Python

All Python code produced by agents follows a **flat, sequential** style. Scripts read top-to-bottom like lab notebooks — no function definitions, no class hierarchies, no module abstractions.

### Rules

1. **No function definitions** — No `def main()`, no helper functions, no `if __name__ == "__main__"` guards
2. **Exceptions to Rule 1:**
   - Marimo cell wrappers (`def _():`) — framework convention, not user functions
   - Standalone CLI tools (e.g., `fetch_paginated.py`) — argparse requires `main()`
3. **Inline validation** — Use `print()` statements and `assert` for validation, never a separate `validation.py` module
4. **Section separators** — Organize scripts with comment headers:
   ```python
   # --- Config ---
   # --- Load ---
   # --- Transform ---
   # --- Validate ---
   # --- Save ---
   ```
5. **No type annotations** — Sequential scripts don't define function signatures, so type hints are unnecessary
6. **No test files** — Validation is inline (`assert` + `print`), not in `tests/` directories
7. **Inline Audit Trail (IAT)** — All transformations, filters, joins, and aggregations must include verbose inline comments documenting intent, reasoning, and assumptions. See `agent_reference/INLINE_AUDIT_TRAIL.md` for the full standard.

### Why This Style?

Research scripts are **write-once, execute-once, archive** artifacts — fundamentally different from application code. Functions add cognitive overhead (What does it return? Where's the entry point?) without providing reuse value. Sequential code is immediately readable and self-documenting through its execution order. Combined with the IAT documentation protocol, sequential code becomes not just readable but self-explanatory — a human auditor can follow every decision without running the code.

---

## Agent Index

| Agent | Purpose | Invocation | Stage(s) |
|-------|---------|------------|----------|
| **research-executor** | Execute data tasks with atomic precision | `general-purpose` | 5, 6, 7, 8 |
| **code-reviewer** | Iterative QA review of executed scripts | `general-purpose` | 5-QA, 6-QA, 7-QA, 8-QA |
| **data-planner** | Create research plans with task sequences | `general-purpose` | 4 |
| **plan-checker** | Pre-execution plan validation (6 dimensions) | `Plan` | 4.5 (before 5) |
| **data-verifier** | Adversarial goal-backward verification with cross-artifact coherence | `Plan` | 12 |
| **source-researcher** | Deep-dive into single data sources | `Plan` | 3 |
| **research-synthesizer** | Consolidate parallel findings | `general-purpose` | 3.5 |
| **debugger** | Diagnose issues scientifically | `general-purpose` | Any (on error) |
| **notebook-assembler** | COMPILE scripts (VERBATIM copy, NO dashboards/widgets) | `general-purpose` | 9 |
| **integration-checker** | Verify component wiring | `Plan` | 11, 12 |
| **data-ingest** | Profile new datasets and author documentation Skills | `general-purpose` | Pre-pipeline (on demand) |

---

## Orchestration Flow

This diagram shows how agents interact throughout the pipeline:

```
                              USER REQUEST
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  PHASE 1: DISCOVERY          │
                    │  (Orchestrator coordinates)  │
                    └──────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
         ┌───────────────────┐         ┌───────────────────┐
         │ source-researcher │         │ source-researcher │
         │   (Source A)      │         │   (Source B)      │
         │   [Stage 3]       │         │   [Stage 3]       │
         └─────────┬─────────┘         └─────────┬─────────┘
                   │                              │
                   └──────────────┬───────────────┘
                                  ▼
                    ┌──────────────────────────────┐
                    │   research-synthesizer       │
                    │   [Stage 3.5 - if needed]    │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴──────────────────┐
                    │  PHASE 2: PLANNING              │
                    └──────────────┬──────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │      data-planner            │
                    │      [Stage 4]               │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴──────────────────┐
                    │       PLAN VALIDATION LOOP      │
                    └──────────────┬──────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │       plan-checker           │◄───────┐
                    │       [Stage 4.5]            │        │
                    └──────────────┬───────────────┘        │
                                   │                        │
                    ┌──────────────┼──────────────┐         │
                    │              │              │         │
                    ▼              ▼              ▼         │
                 PASSED      WARNINGS       BLOCKED         │
                    │              │              │         │
                    │              │              ▼         │
                    │              │    ┌─────────────┐     │
                    │              │    │data-planner │     │
                    │              │    │ (revision)  │─────┘
                    │              │    └─────────────┘
                    │              │         │
                    │              │         ▼
                    │              │    (max 2 iterations,
                    │              │     then escalate to user)
                    │              │
                    └──────────────┼──────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  PHASE 3-4: EXECUTION        │
                    │  (research-executor +        │
                    │   code-reviewer QA)          │
                    └──────────────┬───────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┬─────────────────────────┐
         │                         │                         │                         │
         ▼                         ▼                         ▼                         ▼
    ┌─────────┐              ┌─────────┐              ┌─────────┐              ┌─────────┐
    │Stage 5  │              │Stage 6  │              │Stage 7  │              │Stage 8  │
    │(fetch)  │              │(clean)  │              │(trans)  │              │(viz)    │
    │ CP1     │              │ CP2     │              │ CP3×N   │              │ CP4     │
    └────┬────┘              └────┬────┘              └────┬────┘              └────┬────┘
         │                        │                        │                        │
         ▼                        ▼                        ▼                        ▼
    ┌─────────┐              ┌─────────┐              ┌─────────┐              ┌─────────┐
    │Stage 5  │              │Stage 6  │              │Stage 7  │              │Stage 8  │
    │   QA    │─────────────▶│   QA    │─────────────▶│   QA    │─────────────▶│   QA    │
    │(review) │              │(review) │              │(review) │              │(review) │
    └────┬────┘              └────┬────┘              └────┬────┘              └────┬────┘
         │                        │                        │                        │
         │ BLOCKER?               │ BLOCKER?               │ BLOCKER?               │ BLOCKER?
         ├─► Revision ─┐          ├─► Revision ─┐          ├─► Revision ─┐          ├─► Revision ─┐
         │             │          │             │          │             │          │             │
         │◄────────────┘          │◄────────────┘          │◄────────────┘          │◄────────────┘
         │                        │                        │                        │
         │ (on error)             │ (on error)             │ (on error)             │ (on error)
         └───────────┬────────────┴────────────┬───────────┴────────────┬───────────┘
                     ▼                         ▼                        │
              ┌─────────────┐           ┌───────────┐                   │
              │  debugger   │           │   USER    │◄──────────────────┘
              │  (diagnose) │──────────▶│(escalate) │
              └─────────────┘           └───────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  PHASE 5: DELIVERY           │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              │
         ┌───────────────────┐                     │
         │notebook-assembler │                     │
         │    [Stage 9]      │                     │
         └─────────┬─────────┘                     │
                   │                               │
                   ▼                               │
         ┌───────────────────┐                     │
         │integration-checker│◄────────────────────┘
         │  [Stage 11,12]    │
         └─────────┬─────────┘
                   │
                   ▼
         ┌───────────────────┐
         │   data-verifier   │
         │   [Stage 12]      │
         └───────────────────┘
                                   │
                                   ▼
                              DELIVERY
```

---

## Plan Validation Loop (plan-checker ↔ data-planner)

When plan-checker identifies issues, the revision loop executes:

```
data-planner creates Plan
         │
         ▼
plan-checker validates
         │
    ┌────┴────┐
    │         │
 PASSED    ISSUES
    │         │
    ▼         ▼
Stage 5   Categorize issues
              │
    ┌─────────┴─────────┐
    │                   │
 WARNINGS           BLOCKERS
    │                   │
    ▼                   ▼
Document &         data-planner
proceed            revises Plan
    │                   │
    ▼                   ▼
Stage 5           plan-checker
               validates again
                       │
            ┌──────────┴──────────┐
            │                     │
         PASSED              STILL BLOCKED
            │                     │
            ▼                     ▼
         Stage 5          (iteration 2?)
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 Yes (retry)         No (max reached)
                    │                     │
                    ▼                     ▼
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
| **source-researcher** | research-synthesizer | Source findings (per source) | Multi-source analyses |
| **source-researcher** | data-planner | Source findings | Single-source analyses |
| **research-synthesizer** | data-planner | Consolidated synthesis report | Multi-source analyses |
| **data-planner** | plan-checker | Plan document | Always (Stage 4→4.5) |
| **plan-checker** | data-planner | Issues report | When BLOCKED |
| **plan-checker** | Orchestrator | Validation status | PASSED or WARNINGS |
| **research-executor** | code-reviewer | Executed script + output files | After every script |
| **research-executor** | debugger | Error context | On failure |
| **code-reviewer** | Orchestrator | QA report (BLOCKER/WARNING/INFO) | After every script |
| **code-reviewer** | research-executor | Revision request | When BLOCKER found |
| **code-reviewer** | Stage 10 | QA findings log | For aggregation |
| **debugger** | research-executor | Diagnosis + fix | After diagnosis |
| **debugger** | Orchestrator | Escalation | Undiagnosed issues |
| **research-executor** (Stage 8) | notebook-assembler | Scripts + data files | After Stage 8 completes |
| **notebook-assembler** | integration-checker | Marimo notebook (VERBATIM script copies, NO new code) | After Stage 9 compilation |
| **integration-checker** | data-verifier | Wiring status | Stage 11,12 |
| **data-verifier** | Orchestrator | Verification report | Before delivery |

---

## Error Recovery Routing

When errors occur, this routing determines which agent handles recovery:

```
ERROR DETECTED
      │
      ├─ Data issue (empty, wrong shape)?
      │       └─► research-executor retry (max 2)
      │               └─► debugger (if still failing)
      │
      ├─ QA BLOCKER found (code-reviewer)?
      │       └─► Is it a methodology issue?
      │               ├─► YES → ESCALATE to user immediately
      │               └─► NO → research-executor revision
      │                       └─► code-reviewer re-reviews
      │                               ├─► Resolved → Proceed
      │                               └─► Still BLOCKER after 2 attempts → ESCALATE
      │
      ├─ Transformation issue (unexpected row loss)?
      │       └─► debugger
      │               ├─► Fix identified → research-executor applies fix
      │               └─► Root cause unclear → ESCALATE to user
      │
      ├─ Plan issue (missing section, ambiguous task)?
      │       └─► data-planner (revision)
      │               └─► plan-checker validates
      │
      ├─ Integration issue (broken references)?
      │       └─► integration-checker diagnoses
      │               └─► Orchestrator coordinates fix
      │
      └─ Verification failure (stub detected, missing artifact)?
              └─► data-verifier documents
                      └─► Orchestrator coordinates completion
```

**Error Budget:**
- research-executor: 2 retries per task before debugger
- code-reviewer: 2 revision cycles per script before escalation
- debugger: 2 diagnostic cycles before escalation
- data-planner: 2 revision cycles before escalation
- Any agent: Context degradation → Compress and continue or restart

**QA BLOCKER Types:**

| Type | Definition | Revision Attempts | Action |
|------|------------|-------------------|--------|
| **Technical BLOCKER** | Code produces wrong results due to bug (wrong filter, bad join) | 2 | research-executor revises, code-reviewer re-reviews |
| **Methodology BLOCKER** | Code implements wrong approach (wrong data source, invalid comparison) | 0 | Escalate immediately to user |

**Distinction:** Technical BLOCKERs are fixable by correcting code. Methodology BLOCKERs require user decision because the fundamental approach is questionable.

---

## When to Use Each Agent

### research-executor

**Use when:** Executing data acquisition, cleaning, or transformation tasks.

**CRITICAL: File-First Protocol Required**

This agent MUST follow the file-first execution pattern:
1. Write script to `scripts/stage{N}_{type}/` BEFORE execution
2. Execute via Bash with output capture
3. Append output to script as comments
4. Version failed scripts with `_a`, `_b`, `_c` suffixes

See `agents/research-executor.md` for the complete protocol.

**Key behaviors:**
- **File-first execution** (no interactive Python)
- Atomic execution (one operation at a time)
- Pre/post state capture
- Checkpoint integration (CP1-CP4)
- Commit after each successful task (script + embedded log)

**Invocation pattern:**
```python
Task({
    description: "Stage 5: Fetch CCD data",
    prompt: """You are a Research Executor. Follow the protocol in `{BASE_DIR}/agents/research-executor.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    [Task specification]
    """,
    subagent_type: "general-purpose"
})
```

---

### data-planner

**Use when:** Creating or refining the research Plan document.

**Key behaviors:**
- Requirements-driven planning (from research question)
- Task specificity test
- Wave-based sequencing for parallel execution
- Dependency mapping

**Invocation pattern:**
```python
Task({
    description: "Stage 4: Create research plan",
    prompt: """You are a Data Planner. Follow the protocol in `{BASE_DIR}/agents/data-planner.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    [Discovery findings to synthesize]
    """,
    subagent_type: "general-purpose"
})
```

---

### data-verifier

**Use when:** Final review before delivery, or verifying specific artifacts.

**Key behaviors:**
- Adversarial goal-backward verification (skeptical, not checklist-driven)
- Four-level checks: Existence → Substantive → Wired → Coherent
- Cross-artifact coherence verification (data, notebook, report tell same story)
- Research question stress test
- Independent assessment before Plan anchoring
- Stub detection and silent failure audit

**Invocation pattern:**
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

---

### research-synthesizer

**Use when:** Multiple data sources or exploration tasks need consolidation.

**Key behaviors:**
- Multi-source integration
- Conflict resolution
- Uncertainty documentation
- Actionable recommendations

**Invocation pattern:**
```python
Task({
    description: "Synthesize Stage 2-3 findings",
    prompt: """You are a Research Synthesizer. Follow the protocol in `{BASE_DIR}/agents/research-synthesizer.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    [Findings from Stage 2, Stage 3a, Stage 3b, ...]
    """,
    subagent_type: "general-purpose"
})
```

---

### debugger

**Use when:** Something fails and root cause is unclear.

**Key behaviors:**
- Scientific hypothesis testing
- Binary search for issue isolation
- Systematic evidence collection
- Falsifiable hypothesis formation

**Invocation pattern:**
```python
Task({
    description: "Debug: Row count drop in Stage 7",
    prompt: """You are a Debugger. Follow the protocol in `{BASE_DIR}/agents/debugger.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    [Problem description and evidence]
    """,
    subagent_type: "general-purpose"
})
```

---

### plan-checker

**Use when:** Validating a plan before execution begins (between Stage 4 and Stage 5).

**Key behaviors:**
- Six-dimension validation (requirements, completeness, dependencies, skills, scope, verification)
- Task specificity testing
- Blocking issue identification
- Non-blocking (identifies issues but doesn't fix)

**Invocation pattern:**
```python
Task({
    description: "Validate plan before execution",
    prompt: """You are a Plan Checker. Follow the protocol in `{BASE_DIR}/agents/plan-checker.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    **PLAN CONTENT:**
    {inline the plan content}

    **ORIGINAL REQUEST:**
    {inline the request}
    """,
    subagent_type: "Plan"  # Read-only validation
})
```

---

### source-researcher

**Use when:** Deep-diving into a single data source's caveats, patterns, and pitfalls.

**Key behaviors:**
- Single-source focus (one source per invocation)
- Five-section output (SUMMARY, VARIABLES, CAVEATS, PATTERNS, PITFALLS)
- Confidence assessment
- Pitfall identification

**Invocation pattern:**
```python
Task({
    description: "Stage 3: Research CCD source",
    prompt: """You are a Source Researcher. Follow the protocol in `{BASE_DIR}/agents/source-researcher.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    Call the skill tool with name 'education-data-source-ccd'.

    [Context and variables to investigate]
    """,
    subagent_type: "Plan"  # Read-only
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
- ❌ A dashboard builder
- ❌ An analysis tool
- ❌ An interactive explorer

**Key behaviors:**
- READ script files from `scripts/`
- COPY code VERBATIM into code cells
- COPY execution logs VERBATIM into accordion cells
- ADD ONLY `pl.read_parquet() + mo.ui.table()` cells

**PROHIBITIONS (agent FAILED if output contains):**
- `mo.ui.dropdown()` — NO dropdowns
- `mo.ui.slider()` — NO sliders
- `mo.ui.multiselect()` — NO multiselects
- `.group_by()` outside script code — NO new aggregations
- `.pivot()` outside script code — NO new pivots
- `.filter()` in data cells — NO filtering
- `.with_columns()` in data cells — NO transforms

**Invocation pattern:**
```python
Task({
    description: "Stage 9: Compile scripts into notebook",
    prompt: """You are a Notebook Assembler. Follow the protocol in `{BASE_DIR}/agents/notebook-assembler.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

You are a FILE COMPILER. Your job:
1. READ each script file from scripts/
2. COPY code VERBATIM into marimo cells
3. COPY execution logs VERBATIM into accordions
4. ADD ONLY pl.read_parquet() + mo.ui.table() cells

❌ DO NOT create dropdowns, sliders, or filters
❌ DO NOT write new aggregations or transformations
❌ DO NOT build a dashboard

**PROJECT:** research/2026-01-24 Analysis/
**SCRIPTS:** scripts/stage5_fetch/, stage6_clean/, stage7_transform/, stage8_viz/
**OUTPUT:** 2026-01-24 Analysis.py
    """,
    subagent_type: "general-purpose"
})
```

**What notebook-assembler produces:**
- Marimo notebook with navigation (markdown only)
- VERBATIM script code in code cells
- VERBATIM execution logs in accordion cells
- Simple data load + display cells (THE ONLY NEW CODE)

**Verification:** If output contains `mo.ui.dropdown`, `mo.ui.slider`, `group_by` outside scripts, or `filter` in data cells → REJECT and re-run

---

### integration-checker

**Use when:** Verifying connections between components work (Stage 11, 12).

**Key behaviors:**
- Flow tracing (source to output)
- Reference validation
- Export/import mapping
- Orphan detection

**Invocation pattern:**
```python
Task({
    description: "Verify notebook-to-data integration",
    prompt: """You are an Integration Checker. Follow the protocol in `{BASE_DIR}/agents/integration-checker.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    [Components to verify]
    """,
    subagent_type: "Plan"  # Read-only
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
- Three-phase review (code, execution log, iterative output data inspection)
- Creates iterative QA scripts in `scripts/cr/` (cr1 always; cr2-cr5 when warranted)
- Severity classification (BLOCKER/WARNING/INFO)
- Never fixes code directly (reviewer, not executor)

**Invocation timing:**
```
research-executor completes task
         ↓
    [Primary CP validation passed]
         ↓
orchestrator invokes code-reviewer  ← HERE
         ↓
code-reviewer returns QA report
         ↓
    [Severity?]
     ├─ None/INFO → Proceed to next task
     ├─ WARNING → Log, proceed, flag for Stage 10
     └─ BLOCKER → Trigger revision flow
```

**Invocation pattern:**
```python
Task({
    description: "QA Review: Stage 7 Step 01 - join-data",
    prompt: """You are a Code Reviewer. Follow the protocol in `{BASE_DIR}/agents/code-reviewer.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

**SCRIPT TO REVIEW:**
Path: scripts/stage7_transform/01_join-data.py

**PLAN LOCATION:**
research/2026-01-24 Analysis/2026-01-24 Analysis Plan.md

**OUTPUT FILES:**
- data/processed/2026-01-24_analysis.parquet

**CONTEXT:**
- Stage: 7
- Step: 01
- Task: join-data
- Research Question: [from Plan]

**TASK:**
1. Review script for correctness and methodology alignment
2. Review execution log for outcome verification
3. Create iterative QA scripts at: scripts/cr/stage7_01_cr1.py (+ cr2..cr5 as warranted)
4. Execute QA scripts and synthesize findings across iterations
5. Return QA report with severity classification
    """,
    subagent_type: "general-purpose"
})
```

**Revision flow (when BLOCKER):**
```
code-reviewer returns BLOCKER
         ↓
    [Is methodology issue?]
     ├─ YES → ESCALATE to user immediately
     └─ NO → research-executor creates revision (_a.py)
                 ↓
         code-reviewer re-reviews
                 ↓
         [Still BLOCKER?]
          ├─ NO → Proceed
          └─ YES → Revision attempt 2 (_b.py)
                       ↓
               [After 2 attempts, still BLOCKER?]
                └─ YES → ESCALATE to user
```

---

### data-ingest

**Use when:** User provides a new data file (CSV, parquet, Excel, TSV) for documentation and integration into the workflow.

**Purpose:** Exhaustively profile new datasets and create comprehensive Skills that document:
- Data structure, types, and quality characteristics
- Coded values and their meanings
- **Preliminary semantic interpretations** (variable meanings, flagged for user review)
- Discrepancies between documentation and actual data
- Usage patterns and loading examples

**Key behaviors:**
- Two-mode investigation: Deductive (data → understanding) + Documentation reconciliation (docs → verification)
- **Semantic interpretation:** Infers likely variable meanings from names, values, patterns (marked PRELIMINARY)
- **Website documentation support:** Can fetch and parse documentation from provided URLs
- Data file is source of truth; documentation claims are verified against data
- Creates complete skill with references and archived profiling scripts
- Reports all discrepancies AND preliminary interpretations for user review

**Invocation pattern:**
```python
Task({
    description: "Ingest: {data_name}",
    prompt: """You are a Data Ingest Specialist. Follow `{BASE_DIR}/agents/data-ingest.md`.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

First, call the skill tool with name 'skill-authoring' to understand skill structure requirements.

**DATA FILE:**
Path: {data_file_path}
Format: {csv | parquet | xlsx | tsv}

**DOCUMENTATION FILES:** (if any)
- {doc_path_1}: Data dictionary
- {doc_path_2}: README

**DOCUMENTATION WEBSITE:** (if any)
URL: {website_url}
Description: {what information is available there}

**SKILL CONFIGURATION:**
Target skill name: {skill-name}
Intended use: {how the data will be used}
Priority columns: {columns requiring extra attention}
Domain context: {domain for semantic interpretation}

**TASK:**
1. Profile the data file exhaustively (Mode 1: Deductive, Phases 1-5)
2. Generate preliminary semantic interpretations (Phase 5)
3. Fetch website documentation (if URL provided)
4. Read and reconcile local documentation (Mode 2: if docs provided)
5. Create complete skill at `.claude/skills/{skill-name}/`
6. Report all discrepancies AND preliminary interpretations for user review

Return the complete Data Ingest Report.""",
    subagent_type: "general-purpose"
})
```

---

## Agent + Skill Combinations

Some tasks benefit from combining an agent protocol with skill knowledge:

| Task | Agent | Skill(s) |
|------|-------|----------|
| Fetch CCD data | research-executor | education-data-query |
| Clean MEPS data | research-executor | education-data-context |
| Create analysis plan | data-planner | — |
| Diagnose join failure | debugger | polars |
| Final verification | data-verifier | — |
| Ingest new dataset | data-ingest | skill-authoring, polars |

**Invocation pattern for combined:**
```python
Task({
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

To add a new agent:

1. Create `agents/[agent-name].md`
2. Include **YAML frontmatter** at the top:
   ```yaml
   ---
   name: agent-name                    # Required: lowercase, hyphens
   description: Clear delegation description  # Required: tells orchestrator when to use
   tools: Read, Bash, Glob, Grep       # Optional: restrict available tools
   permissionMode: plan                # Optional: plan (read-only), default, etc.
   ---
   ```
3. Include these body sections:
   - **Identity:** Who the agent is
   - **Core Behaviors:** Key behavioral patterns
   - **`<upstream_input>`:** What inputs the agent receives
   - **`<downstream_consumer>`:** Who uses the agent's output
   - **Protocol:** Step-by-step execution process
   - **Output Format:** Expected return structure
   - **STOP Conditions:** When to escalate
   - **`<anti_patterns>`:** What the agent should NOT do
4. Add to this README's index
5. Update CLAUDE.md's agent reference section

**Naming convention:** `lowercase-hyphenated.md`

**Frontmatter fields:**
| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Agent identifier (lowercase, hyphens) |
| `description` | Yes | When Claude should delegate to this agent |
| `tools` | No | Allowlist of tools (restricts capabilities) |
| `permissionMode` | No | `plan` for read-only, `default` for full access |
| `skills` | No | Skills to preload (e.g., `[polars, data-scientist]`) |
