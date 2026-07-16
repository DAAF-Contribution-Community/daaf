# Specialized Agents

This directory contains behavioral definitions for specialized agents used in the research workflow. Unlike skills (which provide domain knowledge), agents define **behavioral protocols** for specific roles.

All agents in this directory MUST follow the canonical template at `agent_reference/AGENT_TEMPLATE.md`.

---

## Language Support

All code-producing agents support both Python and R. The execution language is determined by the user's `Primary execution language` preference in CLAUDE.md and propagated by the orchestrator to each agent's prompt; the separate `Primary analysis language background` preference drives cross-language annotation direction, not which language the pipeline runs in. Agents detect the pipeline language from script file extensions (`.py` vs `.R`) and load the appropriate library skills on demand.

Read-only agents (search-agent, plan-checker, data-verifier, integration-checker) and planning/synthesis agents (source-researcher, research-synthesizer, report-writer, framework-engineer) are language-agnostic — they reason about artifacts rather than authoring executable pipeline scripts, so they are not listed below. data-planner does not author scripts either, but its Plan_Tasks `<skill>` elements are language-load-bearing (research-executor loads exactly the library skills the task names), so it appears in the table.

| Agent | Python Support | R Support |
|-------|---------------|-----------|
| research-executor | Default. polars, plotnine, statsmodels, pyfixest | R execution via `run_with_capture.sh`. tidyverse, ggplot2, fixest, r-stats |
| data-planner | Routes Python skills into `<skill>` elements (polars, plotnine, statsmodels, pyfixest, ...) | Routes R skills under an R execution directive (tidyverse, ggplot2, r-stats, fixest, ...) |
| code-reviewer | Reviews `.py` scripts; QA scripts in Polars | Reviews `.R` scripts; QA scripts in dplyr/arrow |
| debugger | Diagnoses Python errors; writes `.py` diagnostics | Diagnoses R errors; writes `.R` diagnostics |
| data-ingest | Profiles with Python (polars, arrow) | Profiles with R (dplyr, arrow, skimr) |
| notebook-assembler | Assembles Marimo `.py` notebooks | Assembles Quarto `.qmd` notebooks |

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

## Output Size Discipline

**All agents returning output to the orchestrator MUST respect these universal constraints:**

1. **Hard cap: 2000 words maximum** for Agent return output (exception: `data-ingest` agent uses a 3500-word cap because profiling findings feed directly into skill authoring and must be comprehensive)
2. **Do NOT include:** Raw execution logs, data samples, Polars/pandas table displays, full checkpoint output, QA script code, or multi-paragraph explanations in any section
3. **Script files are the archive; the Agent return is the signal.** Execution logs are already appended to script files by `run_with_capture.sh`. Reference files by path — do not reproduce their contents.
4. **Summarize, don't echo.** "CP1 PASSED: 2,528 rows, 12 cols, 0.3% missing" — not the full stdout.

**Why this matters:** The orchestrator context window is shared across the entire pipeline. A single verbose subagent return (4,000+ words) consumes ~8,000 tokens. Over 10 subagent round-trips in a stage, that's 80,000 tokens — a meaningful share of the orchestrator's capacity — consumed by output alone.

---

## Agent Index

DAAF uses a two-tier model routing convention: `opus` for high-judgment and primary data-production roles where adversarial reasoning, analytical execution quality, cross-file synthesis, or stakeholder calibration is required; `sonnet` for well-specified support roles where the task structure is clear and skill guidance is comprehensive. `haiku` is excluded by policy. These are static defaults encoded in each agent's frontmatter `model:` field — the orchestrator may override any default per-dispatch via the Agent tool's `model` parameter. For the full routing rationale and override guidance, see the "Model Selection for Subagent Dispatch" section of the orchestrator SKILL.md.

| Agent | Purpose | Subagent Type | Stage(s) | Model | Key Inputs | Key Outputs |
|-------|---------|---------------|----------|-------|------------|-------------|
| **research-executor** | Execute data tasks with atomic precision, rigorous validation, and full audit-trail capture | `research-executor` | 5, 6, 7, 8, DS-1/DS-3/DS-5 (synthetic path), Ad Hoc | `opus` | Task spec XML, Plan.md (or orchestrator context in Ad Hoc), skill knowledge, dependency outputs | Script + execution log + data files (parquet) |
| **code-reviewer** | Iterative QA review verifying code correctness, methodology alignment, and output data quality | `code-reviewer` | 5-QA, 6-QA, 7-QA, 8-QA, QAS-A/B/C (synthetic path), RV-2, Ad Hoc | `opus` | Executed script + log, Plan.md (or orchestrator context in Ad Hoc), output files; RV-2: original/reproduction paths, declared artifacts, path-audit MATCH, data strategy/scope exclusions, preliminary notes, and frozen-hash context | QA scripts + severity report; RV-2: per-script status with separate log metrics and direct-artifact evidence, helper JSON/dimensions, deviations, and evidence gaps |
| **data-planner** | Synthesize discovery findings into research plans with executable task sequences and wave-based parallelization | `data-planner` | 4, Ad Hoc | `opus` | User request, clarifications, Stage 2-3 findings (or user-provided context in Ad Hoc), project folder path | Plan.md + Plan_Tasks.md (Full Pipeline) or Advisory Outline (Ad Hoc) |
| **plan-checker** | Verify research plans will achieve analysis goals via goal-backward analysis across six dimensions | `plan-checker` | 4.5 | `opus` | Plan.md + Plan_Tasks.md content (inlined), original user request, clarifications | Validation report: PASSED / PASSED_WITH_WARNINGS / ISSUES_FOUND |
| **data-verifier** | Adversarial goal-backward verification of completed analyses with cross-artifact coherence | `data-verifier` | 12, RV-3 | `opus` | Standard: Plan/Notebook/Report/STATE/QA; RV-3: original Report and copied artifact root, reproduced scripts/artifact root, Reproduction Report, and preliminary notes when present | Standard verification report; RV-3: per-claim/figure/finding MATCH/DIVERGED/NOT DIRECTLY VERIFIED rows with both evidence sources, plus derived coverage counts for claims, figures, findings, artifacts, and dimensions |
| **source-researcher** | Deep-dive into a single data source for caveats, coded values, suppression patterns, and pitfalls | `source-researcher` | 3 | `sonnet` | Source name, variables of interest, research question, years, geographic scope | Five-section source report (Summary, Variables, Caveats, Patterns, Pitfalls) |
| **research-synthesizer** | Consolidate parallel Stage 2-3 findings into actionable planning guidance with conflict resolution | `research-synthesizer` | 3.5 | `sonnet` | Stage 2 findings, all Stage 3 findings, research question, year range, geographic scope | Integrated synthesis with conflicts, resolutions, and planning recommendations |
| **debugger** | Diagnose data quality issues and analysis failures using scientific hypothesis-testing methodology | `debugger` | Any (on error) | `opus` | Error message/symptom, failed script path, Plan.md, Plan_Tasks.md (optional), last successful operation | Root cause report with hypothesis log and verified fix |
| **notebook-assembler** | Compile scripts into notebook via VERBATIM copy — Marimo (Python) or Quarto (R) — NO dashboards, NO widgets, NO new code | `notebook-assembler` | 9 | `sonnet` | Completed scripts (stages 5-8), Plan.md, data files, figure files, project path | Marimo `.py` (Python) or Quarto `.qmd` (R) notebook with script walkthroughs and data inspection cells |
| **integration-checker** | Validate component wiring: data flows, file references, and orphan detection | `integration-checker` | 9, 11, 12 | `sonnet` | Plan.md, Notebook, Report, project folder, script-to-output mappings | Integration check report: CONNECTED / ISSUES FOUND with flow diagrams |
| **data-ingest** | Profile new datasets and produce comprehensive findings for skill authoring; also handles API acquisition (DI-0) | `data-ingest` | Data Onboarding Mode (Stages DI-0, DI-3 to DI-6, DS-4 synthetic path) | `opus` | Data file path(s) + format, target skill name, intended use, domain context, optional docs, API details (if DI-0) | Part-specific profiling findings for orchestrator; DI-0: acquisition script + API findings |
| **framework-engineer** | Author, modify, and integrate DAAF framework artifacts with template compliance and cross-file consistency | `framework-engineer` | Framework Development Mode | `opus` | Work type + scope + scoping findings + affected file paths | Framework artifacts (.md files) + integration checklist report |
| **report-writer** | Synthesize pipeline artifacts into stakeholder report following REPORT_TEMPLATE.md | `report-writer` | 11, RV-4 | `opus` | Standard pipeline artifacts; RV-4: complete Reproduction Report plus persisted full-fidelity RV-3 findings | Report.md; RV-4 synthesis with derived gap/exclusion counts and canonical FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED verdict |
| **search-agent** | Broad-purpose read-only exploration across codebases, documentation, and web sources | `search-agent` | Any (replaces generic Plan dispatches) | `sonnet` | Search prompt, BASE_DIR, optional scope constraints | Flexible findings report with source citations and confidence assessment |

### Commonly Confused Pairs

When adding a new agent, ensure it doesn't overlap with these frequently confused pairs. Each new agent's Core Distinction table (Section 2 of the template) must differentiate from its closest neighbor(s).

| Pair | How They Differ |
|------|----------------|
| **code-reviewer** vs **data-verifier** | Reviewer validates individual scripts *during* execution (Stages 5-8); verifier performs adversarial whole-analysis check *after* completion (Stage 12) |
| **code-reviewer** vs **debugger** | Reviewer validates *correctness* of working code; debugger diagnoses *failures* when code doesn't work |
| **source-researcher** vs **research-synthesizer** | Researcher examines a *single* source in depth; synthesizer *combines* findings across multiple sources |
| **source-researcher** vs **data-ingest** | Researcher examines *existing* skills for a known source; ingest profiles data across four parts; skill authoring is handled by a separate subagent at Stage DI-7 |
| **data-planner** vs **plan-checker** | Planner *creates* plans; checker *validates* plans (never fixes them) |
| **notebook-assembler** vs **integration-checker** | Assembler *builds* the notebook (verbatim script compilation); checker *verifies* wiring between components |
| **report-writer** vs **research-synthesizer** | Writer synthesizes *post-execution* artifacts into a stakeholder report (Stage 11); synthesizer combines *pre-execution* research findings into planning guidance (Stage 3.5) |
| **framework-engineer** vs **data-ingest** | Engineer creates/modifies *framework* artifacts (skills, agents, modes, config); ingest *profiles data* to produce findings for skill authoring |
| **search-agent** vs **source-researcher** | Search-agent explores *broadly* across any information space with flexible output; source-researcher examines a *single known data source* in depth using an existing DAAF skill, producing a fixed five-section deliverable |
| **search-agent** vs **plan-checker** | Search-agent *gathers information* before or during work (exploration); plan-checker *validates* an existing plan against six dimensions (verification) |

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
| **notebook-assembler** | integration-checker | Marimo `.py` or Quarto `.qmd` notebook (VERBATIM script copies, NO new code) | After Stage 9 compilation |
| **integration-checker** | data-verifier | Wiring status (CONNECTED / ISSUES FOUND) | Stages 9, 11, 12 |
| **data-verifier** | Orchestrator | Verification report (PASSED / ISSUES_FOUND with four-layer evidence) | Before delivery |
| **report-writer** | integration-checker | Report.md (stakeholder report following REPORT_TEMPLATE.md) | After Stage 11 completes |
| **report-writer** | data-verifier | Report.md (stakeholder report) | Before Stage 12 verification |
| **report-writer** | Orchestrator | Status report (COMPLETE / COMPLETE_WITH_GAPS / BLOCKED) | After report generation |
| **Orchestrator** | data-ingest | Part assignment (DI-0/A/B/C/D), prior part findings, conditional script decisions, API details (DI-0), multi-file paths + schema map (HIERARCHICAL) | Stages DI-0, DI-3 to DI-6 |
| **data-ingest** | Orchestrator | Part-specific profiling findings, confidence assessment, issues; DI-0: acquisition script path + API findings | Stages DI-0, DI-3 to DI-6 |
| **code-reviewer** (RV-2) | Orchestrator | Per-script status; separate shared-log and direct-artifact evidence; helper JSON/per-dimension results; deviations, NOT DIRECTLY VERIFIED gaps, and frozen-hash integrity when applicable | RV-2 (per in-scope script) |
| **data-verifier** (RV-3) | Orchestrator | Per-claim/figure/finding MATCH/DIVERGED/NOT DIRECTLY VERIFIED rows with original and reproduced evidence sources, plus derived counts across all evidence-unit classes | RV-3 |
| **report-writer** (RV-4) | Orchestrator | Reproduction Report synthesis sourced from full-fidelity RV-3 findings, with gaps/exclusions counted and one canonical FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED verdict | RV-4 |
| **debugger** (RV-2) | Orchestrator | Root cause analysis + minimal fix for reproduction failure | RV-2 (on error) |
| **Orchestrator** | framework-engineer | Work type, scope, scoping findings, affected file paths | Framework Development Mode |
| **framework-engineer** | Orchestrator | Framework Engineering Report (status, artifacts, checklist, confidence) | Framework Development Mode |
| **framework-engineer** | Review subagents (Plan) | Created/modified files for multi-angle review | Framework Development Mode Phase 4 |
| **Orchestrator** | search-agent | Search prompts with scope constraints and output expectations | Any mode/stage |
| **search-agent** | data-planner | Stage 2 exploration findings (data landscape, variables, endpoints) | Full Pipeline Stage 2 |
| **search-agent** | research-synthesizer | Exploration baseline findings across sources | Full Pipeline Stage 3.5 |
| **search-agent** | framework-engineer | Scoping findings (current state, affected files, patterns) | Framework Development Mode |
| **search-agent** | Orchestrator | Flexible findings report with confidence assessment | Any mode/stage |

**Preliminary Notes Persistence:** Discovery and profiling agents' full returns are persisted to `output/preliminary_notes/` as lossless markdown files by the orchestrator. Downstream agents reference these files by path for full-fidelity access, while the orchestrator retains compressed summaries for its own coordination. This applies to search-agent (Stage 2), source-researcher (Stage 3), research-synthesizer (Stage 3.5), and data-ingest (DI-3 through DI-6) returns. See orchestrator SKILL.md for the complete protocol.

---

## When to Use Each Agent

> For stage-specific invocation templates with full context fields, see the corresponding `agent_reference/WORKFLOW_PHASE*.md` files.

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

**Ad Hoc Collaboration:** In Ad Hoc mode, research-executor writes scripts to `scripts/adhoc/` instead of stage-based directories. Plan.md is replaced by orchestrator-provided task context. See `ad-hoc-collaboration-mode.md` for the invocation pattern.

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### data-planner

**Use when:** Creating or refining the research Plan document at Stage 4, or handling plan revisions when plan-checker or user identifies issues.

**Key behaviors:**
- Requirements-driven planning (backward from Research Outcomes)
- Task specificity test (every task unambiguous for any agent)
- Wave-based sequencing for parallel execution
- Dependency mapping

**Ad Hoc Collaboration:** In Ad Hoc mode, data-planner produces an Advisory Outline (not full Plan.md + Plan_Tasks.md) from user-provided context instead of formal Stage 2-3 findings. See `ad-hoc-collaboration-mode.md`.

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

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

**Reproducibility Verification (RV-3):** In RV mode, data-verifier compares persisted original and reproduced claims, tables, supported Parquet artifacts, and side-by-side figures using MATCH / DIVERGED / NOT DIRECTLY VERIFIED; logs alone are insufficient. It returns per-claim/figure/finding evidence sources and derived coverage counts, keeps exact pre-RV-2 scope exclusions separate, and RETURNS findings to the orchestrator (read-only) rather than writing the Reproduction Report.

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### research-synthesizer

**Use when:** Multiple data sources or exploration tasks need consolidation (Stage 3.5, after all per-source research completes).

**Key behaviors:**
- Multi-source integration with explicit conflict resolution
- Opinionated recommendations (not just descriptions)
- Uncertainty documentation with confidence levels
- Actionable guidance structured for data-planner consumption

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### debugger

**Use when:** Something fails and root cause is unclear, or code-reviewer identifies complex issues requiring root-cause analysis. Diagnoses both Python and R pipeline errors.

**Key behaviors:**
- Scientific hypothesis testing (max 5 cycles)
- Binary search for issue isolation
- Systematic evidence collection
- Falsifiable hypothesis formation
- Documented elimination process
- Writes diagnostic scripts matching the pipeline language (`.py` or `.R`)

**Escalation rules:**
- 2 diagnostic cycles maximum before escalating to user
- If root cause is a methodology issue, escalate immediately
- If root cause is unclear after 2 cycles, escalate with hypothesis log

**Reproducibility Verification (RV-2):** The debugger serves as an escalation target during RV-2 when the code-reviewer cannot resolve a script reproduction failure within 2 modification attempts (`_repro_a.py`, `_repro_b.py`). The debugger diagnoses root causes of reproduction failures (e.g., environment differences, missing dependencies, data drift) and provides minimal fixes to enable reproduction.

**Ad Hoc Collaboration:** In Ad Hoc mode, the debugger accepts user-provided scripts and error descriptions directly, without Plan.md. Diagnostic output is more explanatory since the user is the audience. See `ad-hoc-collaboration-mode.md`.

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

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

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### source-researcher

**Use when:** Deep-diving into a single data source's caveats, patterns, and pitfalls (Stage 3, one invocation per source identified in Stage 2).

**Key behaviors:**
- Single-source focus (one source per invocation)
- Five-deliverable output contract (Summary, Variables, Caveats, Patterns, Pitfalls)
- Confidence assessment per section
- Pitfall identification with mitigation
- Truth Hierarchy application for discrepancies

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### notebook-assembler

**Use when:** Stage 8 is complete and it's time to compile scripts into a notebook (Stage 9).

**Purpose:** LITERALLY COPY script file contents into notebook cells. Assembles Marimo (Python) or Quarto (R) notebooks. The notebook is a script viewer, NOT a dashboard.

**CRITICAL CONSTRAINT:** This agent COPIES files. It does NOT generate new code, dashboards, filters, or interactive widgets. If you see dropdowns, sliders, or new aggregations in the output, the agent FAILED.

**What this agent IS:**
- A file compiler (read files, copy contents)
- A copy-paste machine with formatting
- A script viewer

**What this agent is NOT:**
- A dashboard builder
- An analysis tool
- An interactive explorer

**Language detection:** Inspects script file extensions in `scripts/stage{5,6,7,8}_*/`. If `.py` → assembles Marimo. If `.R` → assembles Quarto.

**Key behaviors (Marimo — Python pipelines):**
- READ script files from `scripts/`
- COPY code VERBATIM into code cells (commented out with `# ` prefix)
- REQUIRE non-placeholder execution logs and COPY them VERBATIM into adjacent accordion cells
- OPTIONALLY ADD only a bounded existing-Parquet preview or `mo.image()` display of an already-created figure
- Applies a canonical three-cell archive bundle per script (header, commented code, log accordion), followed by an optional display cell

**Key behaviors (Quarto — R pipelines):**
- READ script files from `scripts/`
- COPY code VERBATIM into ```` ```{r} ```` chunks with `#| eval: false`
- REQUIRE non-placeholder execution logs and COPY them VERBATIM into immediately following callouts
- OPTIONALLY ADD only a bounded Parquet preview or display of an already-created figure (Markdown preferred; dedicated `knitr::include_graphics()` allowed)
- Applies heading + chunk + callout + optional display pattern per script

**PROHIBITIONS (agent FAILED if output contains):**
- New analysis code (aggregations, pivots, filters, transforms) not from original scripts
- Interactive widgets (Marimo: `mo.ui.dropdown()`, `mo.ui.slider()`, etc.)
- New visualizations not from original scripts

**Verification:** If output contains interactive widgets, new aggregations outside scripts, or new analysis code -> REJECT and re-run

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### report-writer

**Use when:** Generating the stakeholder report at Stage 11, after QA aggregation (Stage 10) confirms no unresolved BLOCKERs.

**Key behaviors:**
- Follows REPORT_TEMPLATE.md section by section using a systematic Section-Source Mapping
- Reads the full pipeline artifact set: Plan, Notebook, STATE.md, LEARNINGS.md, QA summary, figures, citations
- Every statistic must trace to an execution log or dataset metadata — never hallucinated
- Cross-checks all Research Outcomes from Plan against Key Findings
- Verifies all figure file paths resolve before embedding references

**Reproducibility Verification (RV-4):** In RV mode, report-writer reads the complete Reproduction Report and persisted full-fidelity RV-3 findings, derives all completion/evidence-gap counts, reports exact scope-design exclusions separately, and assigns only FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED. Any in-scope evidence gap caps the verdict at PARTIALLY REPRODUCED.

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### integration-checker

**Use when:** Verifying connections between components work (Stages 9, 11, 12). Traces data flows from raw inputs to final outputs, ensures nothing is orphaned, broken, or disconnected.

**Key behaviors:**
- Flow tracing (source to output through complete pipeline)
- Reference validation (notebook->data, report->figures)
- Export/import mapping
- Orphan detection
- E2E flow verification

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

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

**Reproducibility Verification (RV-2):** In RV mode, the code-reviewer re-executes each in-scope script and compares shared log metrics with direct original-versus-reproduced artifact evidence; logs alone never establish artifact equality. It requires prior path-audit MATCH, executes Stage 5 in re-fetch mode, excludes rather than executes Stage 5 under the pre-approved frozen-input design, verifies frozen raw hashes afterward, preserves artifact-helper JSON for supported Parquet/exact evidence, and creates failure revisions from clean log-free sources.

**Ad Hoc Collaboration:** In Ad Hoc mode, code-reviewer can review user-provided scripts that may lack execution logs or Plan.md context. Methodology alignment is evaluated against the user's stated intent rather than a formal Plan. See `ad-hoc-collaboration-mode.md`.

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### data-ingest

**Use when:** The orchestrator is running Data Onboarding Mode and needs to dispatch a profiling part (A/B/C/D) for a new data file. Each part is a separate subagent invocation managed by the orchestrator. Profiles data with Python or R scripts depending on the user's execution language preference.

**Purpose:** Profile new datasets across four orchestrator-managed parts:
- **Part A:** Structural Discovery (schema, types, shapes, nulls)
- **Part B:** Statistical Deep Dive (distributions, temporal coverage, entity coverage)
- **Part C:** Relational Analysis (key candidates, correlations, quality anomalies)
- **Part D:** Interpretation & Reconciliation (semantic classification, documentation reconciliation)

**Key behaviors:**
- Operates as an orchestrator-managed profiling specialist (one part per invocation)
- Receives part assignment and prior part findings from orchestrator
- Data file is source of truth; documentation claims are verified against data
- Returns part-specific profiling findings with confidence assessment
- Writes profiling scripts in the pipeline language (Python with polars, or R with dplyr/arrow)
- Skill authoring is NOT performed by this agent (handled at Stage DI-7 by a separate subagent)

**Invocation template:** See the appropriate WORKFLOW_PHASE*.md or mode reference file for stage-specific invocation templates.

---

### framework-engineer

**Use when:** The orchestrator is running Framework Development Mode and needs to create or modify framework components (skills, agents, modes, reference files). Each invocation handles one work type (new skill, new agent, new mode, modify existing, or multi-component).

**Key behaviors:**
- Template fidelity (follows AGENT_TEMPLATE, MODE_TEMPLATE, skill-authoring rules exactly)
- Read before write (never modify a file without reading it first)
- Integration completeness (executes FRAMEWORK_INTEGRATION_CHECKLIST.md for every component)
- Cross-file consistency verification after all edits
- Minimal disruption (surgical edits, match existing style)

**Preloaded skills:** `skill-authoring`, `agent-authoring` (loaded via frontmatter)

**Invocation template:** See `framework-development-mode.md` for the invocation pattern.

---

### search-agent

**Use when:** The orchestrator needs to find information across codebases, documentation, datasets, or the web. Replaces all generic `Plan` and `Explore` subagent type dispatches with a DAAF-native agent that understands the framework's conventions and skill ecosystem.

**Key behaviors:**
- Breadth-first exploration (scan broadly, then drill into best candidates)
- Evidence-based findings with mandatory source citations (file:line or URL)
- Flexible output format adapted to the task (inventories, direct answers, surveys)
- Web-capable research via WebSearch and WebFetch (unique among read-only agents)
- Skill-aware domain knowledge (loads relevant DAAF skills for authoritative context)

**Key distinction from source-researcher:** The source-researcher examines a single known data source in depth using an existing DAAF skill, producing a fixed five-section deliverable. The search-agent explores broadly across any information space with flexible output. If you already know which data source skill to investigate, use source-researcher.

**Key distinction from plan-checker and data-verifier:** Those agents perform verification of completed work. The search-agent gathers information before or during work -- it explores, it does not verify.

**Invocation template:** See the search-agent definition file for invocation patterns used across multiple modes and stages.

---

## Adding New Agents

> **Comprehensive guide:** Use the `agent-authoring` skill for full guidance including section-by-section walkthrough, cross-agent standards, and a complete integration checklist covering every file that needs updating. The summary below provides a quick orientation.

### Quick Summary

1. **Design:** Identify the agent's role, pipeline stage, subagent type, and similar agents to differentiate from (see "Commonly Confused Pairs" above)
2. **Author:** Create `.claude/agents/[agent-name].md` following `agent_reference/AGENT_TEMPLATE.md` (12 mandatory sections)
3. **Integrate:** Update all registry files — use the `agent-authoring` skill's integration checklist for the complete list
4. **Validate:** Verify the agent appears in all registry files and cross-agent standards are met

### Required Frontmatter

```yaml
---
name: agent-name-here
description: >
  [Third person. What it does AND when to use it.]
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]   # Explicit allowlist. Omit for all.
permissionMode: default                          # Or: plan (read-only agents)
model: sonnet                                    # Or: opus (high-judgment roles). See Agent Index prose above.
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

- [ ] `.claude/agents/README.md` — Agent Index + "When to Use" section + Coordination Matrix
- [ ] `.claude/agents/README.md` — Agent catalog table (canonical Specialized Agents registry) + `full-pipeline-mode.md` > Skill-to-Stage Mapping (if stage-specific)
- [ ] `README.md` — Agent Ecosystem table + update agent count

For the **complete 29-item integration checklist** (including conditional workflow and narrative updates), invoke the `agent-authoring` skill and read `references/integration-checklist.md`.

**Naming convention:** `lowercase-hyphenated.md`

**Target length:** 400-700 lines per agent (never exceed 1000).
