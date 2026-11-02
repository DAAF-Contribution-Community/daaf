# Workflow Reference: Phase 5 — Synthesis & Delivery

Stages 11, 12. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md`.

> **Async dispatch note.** This phase dispatches single agents sequentially (report-writer then integration-checker for Stage 11; integration-checker then data-verifier for Stage 12), not parallel waves. See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive. Do not begin Stage 12 verification, evaluate a stage gate, or present the final deliverable to the user until the current dispatch's return has arrived and been fully processed.

---

## Stage 11: Report Generation

**Executor:** report-writer agent
**Purpose:** Synthesize all pipeline artifacts into a stakeholder-appropriate report

### Upstream Inputs

| Input | Source | Purpose |
|-------|--------|---------|
| Plan.md | Stage 4 | Research question, methodology, research outcomes, risk register (frozen after Stage 4.5) |
| Notebook — Marimo (.py) or Quarto (.qmd) | Stage 9 | Complete technical record: all scripts + execution logs |
| STATE.md | Maintained throughout | Checkpoint statuses, key decisions, blockers, runtime risks, QA findings summary, final review log |
| LEARNINGS.md | Maintained throughout | Data quality insights, methodology lessons |
| Stage 10 QA summary | Stage 10 | Aggregated QA findings (WARNINGs, resolved BLOCKERs) |
| Statistical results | Stage 8.1 (`output/analysis/`) | Analysis findings for Key Findings and interpretation |
| Figure files | Stage 8.2 (`output/figures/`) | Visualizations to embed in Key Findings |
| Citations Accumulated | STATE.md (accumulated during Stages 5-8) | Data source, methodological, software, and reporting standard citations with rationale |
| Analysis dataset metadata | Stage 7 | Final dataset shape, column list, key statistics |

### Section-Source Mapping

report-writer maps each REPORT_TEMPLATE.md section to its primary and secondary source artifacts; the mapping is defined in `.claude/agents/report-writer.md` Core Behavior 2 (Section-Source Mapping Discipline). The orchestrator does not draft the report: the Upstream Inputs table above is what the dispatch must supply, and the mapping matters to the orchestrator only when it checks Gate G11.

### Actions

1. **Read upstream artifacts** — Plan.md, Notebook, STATE.md, LEARNINGS.md
2. **Verify figures** — Confirm all figure files exist before referencing
3. **Draft report** — Follow REPORT_TEMPLATE.md section by section using Section-Source Mapping
4. **Cross-check Research Outcomes** — Every Research Outcome from Plan.md addressed in Key Findings
5. **Write the report** — Save to project folder with date prefix (`YYYY-MM-DD[suffix]_[Title]_Report.md`)

### Invocation Template: report-writer

**Agent:** report-writer
**Skills:** `data-scientist` (synthesis agent — key domain knowledge is in upstream artifacts)

```python
Agent({
    description: "Stage 11: Report Generation",
    prompt: """**BASE_DIR:** {BASE_DIR}
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

    **CITATIONS:** Read STATE.md > Citations Accumulated for all citation data.
    For verification, consult agent_reference/CITATION_REFERENCE.md.

    **ANALYSIS DATASET METADATA:**
    {dataset_metadata}

    **FIGURE FILES:**
    {figure_file_list}

    **AI DISCLOSURE METADATA (from STATE.md Session Metadata):**
    - DAAF Version: {daaf_commit_hash}
    - Session Model ID: {session_model_id}
    - Subagent Model Tiers: {subagent_model_tiers}
    - Provider Route: {provider_route}
    - Session Date(s): {session_dates}

    **Target Audience:** {target_audience} (from Plan.md; if non-technical, include instruction to load science-communication skill)

    **TASK:**
    Generate the stakeholder report following REPORT_TEMPLATE.md.
    Include the AI Use Disclosure section (Step 6b) using AI_DISCLOSURE_REFERENCE.md.
    Read Plan.md, Notebook, STATE.md, and LEARNINGS.md.
    Follow the Section-Source Mapping for every section.
    Verify all figure references before embedding.
    Cross-check all Research Outcomes from Plan.md.
    Write the report to the project folder as {report_filename} (the dated
    YYYY-MM-DD[suffix]_[Title]_Report.md name, never a bare Report.md).

    Return findings using the Report Writer Output Format.""",
    subagent_type: "report-writer"
})
```

#### Pre-Report: Session Log Collection

Before invoking report-writer, run the Scratch Graduation Check (`SCRIPT_EXECUTION_REFERENCE.md` § Scratch Graduation Check; the plan, notes and report never cite a file in `scripts/scratch/`, and graduated files, old → new, are named in the delivery message), then collect session transcripts into the project:
```
bash {BASE_DIR}/scripts/collect_session_logs.sh {PROJECT_DIR}
```
Then update STATE.md: confirm `logs/` holds the transcripts of the earlier sessions, and fill in the `Archive` column in the Session History table with the archive filenames for each of those session rows. The current session is archived only when it ends (its archive name carries the end time), and the collection request the script records should copy it into `logs/` then (if it is still missing afterwards, the script can be run again in a later session). So `logs/` holds no file for the current session yet, and a project worked on only in this session has an empty `logs/` at this point: that is expected. Enter "copied at session end" in the current session's `Archive` cell.

#### Context Completeness Checklist (Stage 11)

Before invoking report-writer, verify:
- [ ] Plan.md path provided (absolute) — methodology, research question, risk register
- [ ] Notebook path provided (absolute)
- [ ] STATE.md path provided (absolute)
- [ ] LEARNINGS.md path provided (absolute)
- [ ] Stage 10 QA summary inlined (not just path reference)
- [ ] STATE.md Citations Accumulated section populated (orchestrator responsibility during Stages 5-8)
- [ ] Analysis dataset metadata inlined (shape, columns, key stats)
- [ ] Figure file paths listed (all files in output/figures/)
- [ ] Date prefix specified
- [ ] Report filename specified (following naming convention)
- [ ] Project path specified (absolute)
- [ ] DAAF commit hash provided (from STATE.md Session Metadata)
- [ ] Session model ID and subagent model tiers provided (from STATE.md Session Metadata) — so report-writer can populate the Report's session + specialist model rows
- [ ] Scratch Graduation Check run (no cited file left in `scripts/scratch/`)
- [ ] Session logs collected into `logs/` (collect_session_logs.sh run)
- [ ] Target audience specified (from Plan.md; if non-technical, include `science-communication` skill loading instruction)

#### Expected Output

report-writer returns:
- **COMPLETE** → Dispatch integration-checker for the Stage 11 wiring check (below)
- **COMPLETE_WITH_GAPS** → Log gaps, then dispatch the Stage 11 wiring check (below); data-verifier assesses the gaps' severity at Stage 12
- **BLOCKED** → Resolve missing inputs, re-invoke

### Invocation Template: integration-checker (Stage 11 wiring check)

**Purpose:** Verify the new Report's references resolve before final review
**Stage:** 11, after report-writer returns COMPLETE or COMPLETE_WITH_GAPS
**Agent:** integration-checker (see `.claude/agents/integration-checker.md`, Core Behavior 6)
**Model:** `sonnet` (frontmatter default)

```python
Agent({
    description: "Stage 11: Integration Check (report wiring)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**STAGE:** 11 (use the Stage 11 scope in your Core Behavior 6)

**CONTEXT:**
- Plan path: {plan_path}
- Notebook path: {notebook_path}
- Report path: {report_path}
- Project folder: {PROJECT_DIR}
- Figure files: {figure_file_list}
- Stage 9 integration result: {stage9_status_and_open_warnings}

**TASK:**
Check Report -> figure references (exist, >1KB), Report -> notebook outputs and
analysis files, path and citation references in the Report, and figure orphans.
Read-only: no files written, no Python or R of your own, no render or export.

Return findings using the Integration Checker Output Format.""",
    subagent_type: "integration-checker"
})
```

**Handling the verdict:** Record every verdict in the Stage 11 row of STATE.md § Final Review Log > Integration Checks. CONNECTED satisfies the G11 wiring checkbox. WARNING: log it in that row and pass it to Stage 12. BLOCKER or STOP: G11 is not satisfied; route a broken Report reference to report-writer (a missing figure to research-executor), then re-dispatch integration-checker for Stage 11 (`ERROR_RECOVERY.md` § Error Recovery Routing, "Integration issue").

### Gate Criteria (G11)

- [ ] report-writer returned COMPLETE or COMPLETE_WITH_GAPS
- [ ] All REPORT_TEMPLATE.md sections populated (not placeholder text)
- [ ] All figure references resolve to existing files
- [ ] All Research Outcomes from Plan.md addressed in Key Findings
- [ ] Executive Summary is 4-5 sentences
- [ ] All statistics trace to execution logs or dataset metadata
- [ ] References section populated from STATE.md > Citations Accumulated (all four subsections addressed; cross-referenced against CITATION_REFERENCE.md if available)
- [ ] AI Use Disclosure section populated (GUIDE-LLM items addressed or marked N/A)
- [ ] **Wiring:** integration-checker (Stage 11 scope) returned CONNECTED, or ISSUES FOUND with WARNING only (logged in STATE.md § Integration Checks); no BLOCKER open

---

## Stage 12: Final Review

**Executor:** Orchestrator invokes `integration-checker` (full wiring check), then `data-verifier` (adversarial verification), then performs consolidation
**Purpose:** Adversarial goal-backward verification of completed analysis, followed by lessons consolidation and delivery

### Step 0: Invoke integration-checker (full scope)

**Division of labor:** integration-checker answers "are the pieces connected?" (every reference resolves, every file is non-empty and readable, no orphans, one E2E trace). data-verifier's wiring layer (Layer 3) starts from that result and asks whether the connections carry the right information and whether the artifacts cohere. Both run; neither replaces the other.

```python
Agent({
    description: "Stage 12: Integration Check (full pipeline wiring)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**STAGE:** 12 (full protocol, Core Behavior 6)

**CONTEXT:**
- Plan path: {plan_path}
- Notebook path: {notebook_path}
- Report path: {report_path}
- Project folder: {PROJECT_DIR}
- STATE.md path: {state_path}
- Execution scripts and their output files (Stages 5-8): {script_output_list}
- Expected figures: {figure_list}
- Stage 9 and 11 integration results: {prior_integration_results}

**TASK:**
Run the full protocol: every reference, all orphan directories, data source
coverage against Plan.md, and at least one E2E trace from download to Report.
Read-only: no files written, no Python or R of your own, no render or export.

Return findings using the Integration Checker Output Format.""",
    subagent_type: "integration-checker"
})
```

**Handling the verdict:** integration-checker has no Write tool, so the orchestrator persists its Stage 12 return in full and unmodified, with the provenance header, at `{project_dir}/output/preliminary_notes/{date}_stage12_integration-check.md` (`SKILL.md` § Subagent Return Processing steps 2a-2c; a gate condition), and records the verdict in the Stage 12 row of STATE.md § Final Review Log > Integration Checks. CONNECTED or WARNING-only: pass that path to data-verifier in Step 1, with the status and the count of references marked Not verified; data-verifier starts Layer 3 from its flow, reference and orphan tables. BLOCKER or STOP: fix before verification (Stage 9 or 11 routing above, or debugger for a disconnected stage), then re-dispatch integration-checker; do not dispatch data-verifier on a known broken connection.

### Step 1: Invoke data-verifier (MANDATORY)

The data-verifier agent performs adversarial, goal-backward verification across all four layers (existence, substantiveness, wiring, coherence). This is the **last line of defense** before delivery.

#### Invocation Template: data-verifier

```
Agent({
    description: "Stage 12: Final Verification",
    prompt: """**BASE_DIR:** {BASE_DIR}
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
    - Stage 12 integration-checker result (Step 0): status {integration_status}, references not verified {not_verified_count}; full return (flow, reference, orphan and issue tables) at {project_dir}/output/preliminary_notes/{date}_stage12_integration-check.md
    - Stage 9 render/export evidence (from STATE.md § Final Review Log > Stage 9 Check Evidence, with run timestamps): {stage9_check_evidence}

    **DISCOVERY PRELIMINARY NOTES (for Telephone Game trace):**
    The following preliminary notes contain the original source research. Use these
    for the Telephone Game trace — verify that constraints, caveats, and coded value
    rules established in discovery are faithfully reflected through Plan -> scripts -> output:
    - {project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md
    - {project_dir}/output/preliminary_notes/{date}_stage3_{source1}_source-research.md
    - {project_dir}/output/preliminary_notes/{date}_stage3_{source2}_source-research.md
    [...one path per source]
    - {project_dir}/output/preliminary_notes/{date}_stage3.5_research-synthesis.md

    **TASK:**
    Perform adversarial goal-backward verification of the completed
    analysis. Verify all four layers (existence, substantiveness,
    wiring, coherence). Perform research question stress test,
    Telephone Game trace, alternative interpretation probing, silent
    failure audit, and QA history review. Check the deliverables against
    the Plan's Confirmed Pre-Flight Scope and User-Referenced Materials
    subsections too (`agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md` §
    Traditional Review Checklist, 2a): a scope the
    user narrowed at the pre-flight binds them, unless the Decisions Log
    records the departure.

    Return findings using the Data Verifier Output Format.""",
    subagent_type: "data-verifier"
})
```

#### Expected Output

data-verifier returns (`full-pipeline-mode.md` § Gate Status Translation):
- **PASSED** → Proceed to Step 2 (consolidation and delivery)
- **ISSUES_FOUND (severity: WARNING)** → Log warnings in STATE.md Final Review Log, proceed to Step 2 with caveats
- **ISSUES_FOUND (severity: BLOCKER)**, or a **DATA-VERIFIER STOP** → STOP, escalate to user with specific failures and remediation options

---

### Goal-Backward Verification Framework

Before marking any analysis complete, verify each of the three categories below. This approach works backward from the goal state to ensure nothing is missing.

**Verification Stance:** The data-verifier agent approaches this framework with adversarial skepticism — its default hypothesis is that something was missed. See `.claude/agents/data-verifier.md` for the complete adversarial verification protocol including cross-artifact coherence, research question stress testing, and the Hidden Narrative principle.

#### 1. What Must Be EXAMINED (Research Outcomes)

These are topics that must be rigorously investigated and reported for the analysis to be complete:

| Requirement | Verification Method | Status |
|-------------|---------------------|--------|
| Research question addressed with evidence | Read Report conclusions | [ ] |
| All Plan research outcomes rigorously investigated | Compare Plan outcomes vs. report findings | [ ] |
| Hypotheses transparently assessed (if any) | Check hypothesis assessments in Report | [ ] |
| All Plan commitments fulfilled | Compare Plan vs. deliverables | [ ] |
| No validation checkpoints failed | Review CP1-CP4 status | [ ] |
| Limitations explicitly documented | Check Report limitations section | [ ] |
| Data transformations preserve integrity | Review transformation log | [ ] |
| No coded values in analysis variables | Read the CP2/CP3 coded-value counts in the Stage 6-7 execution logs and the code-reviewer QA logs | [ ] |
| Suppression rate acceptable (<50%) | Review CP2 results | [ ] |
| Cross-state comparisons valid (if any) | Check against validity matrix | [ ] |

**Verification:** For each item, actively verify (don't assume). Check file contents, read execution logs, checkpoint and QA output, and report sections. data-verifier does not query data (it has no Write tool and its file-first hook blocks direct Python and R): an item with no readable evidence is NOT VERIFIED, and the orchestrator decides whether an executor produces the evidence.

#### 2. What Must EXIST (Concrete Artifacts)

These files must exist in the project folder:

| Artifact | Path | Exists? | Substantive? |
|----------|------|---------|--------------|
| Plan document | `[project]/YYYY-MM-DD_[Title]_Plan.md` | [ ] | [ ] |
| Plan tasks | `[project]/YYYY-MM-DD_[Title]_Plan_Tasks.md` | [ ] | [ ] |
| Notebook (Marimo `.py` or Quarto `.qmd`) | `[project]/YYYY-MM-DD_[Title].py` (Python) or `.qmd` (R) | [ ] | [ ] |
| Stakeholder report | `[project]/YYYY-MM-DD_[Title]_Report.md` | [ ] | [ ] |
| Lessons learned | `[project]/LEARNINGS.md` | [ ] | [ ] |
| Raw data (parquet) | `[project]/data/raw/*.parquet` | [ ] | [ ] |
| Processed data (parquet) | `[project]/data/processed/*.parquet` | [ ] | [ ] |
| Visualizations | `[project]/output/figures/*.png` | [ ] | [ ] |
| STATE.md | `[project]/STATE.md` | [ ] | [ ] |

**Verification Protocol:**
1. List files in project folder
2. Verify each required file exists
3. Open each file and verify non-empty, valid content
4. Check file naming follows conventions
5. Check substantiveness (see below)

#### 2b. Substantiveness Check (Stub Detection)

Artifacts must contain **real implementation**, not placeholders. Flag these patterns as incomplete:

**Text File Stub Indicators:**
| Pattern | Example | Found In |
|---------|---------|----------|
| TODO comments | `# TODO: implement` | Code files |
| FIXME markers | `FIXME: add validation` | Code files |
| Placeholder text | `[add more]`, `TBD`, `XXX` | Markdown files |
| Empty sections | `## Results\n\n## Conclusion` | Report |
| Template remnants | `[Your finding here]` | Report |

**Code Stub Indicators:**
| Pattern | Example | Concern |
|---------|---------|---------|
| Empty returns | `return None`, `return {}` | Unimplemented function |
| Pass statements | `def process(): pass` | Placeholder function |
| NotImplementedError | `raise NotImplementedError` | Incomplete code |
| Hardcoded test values | `return 42` | Missing real logic |

**Data Stub Indicators:**
| Pattern | Example | Concern |
|---------|---------|---------|
| Single unique value | All rows have same value | Data not actually processed |
| All zeros | Count column is all 0 | Calculation not run |
| All nulls | Column entirely null | Join or filter failed |
| Suspiciously round numbers | All values end in 000 | Placeholder data |

**Stub Detection Protocol** (pseudocode for a search over each text file with the Grep tool where available, else `grep -n -i` via Bash; not a script to run):

```python
# Text files
stub_patterns = [
    r'\bTODO\b', r'\bFIXME\b', r'\bPLACEHOLDER\b', r'\bTBD\b',
    r'\bXXX\b', r'\[add more\]', r'\[your .* here\]',
    r'coming soon', r'lorem ipsum'
]

# For each text file:
for pattern in stub_patterns:
    if re.search(pattern, content, re.IGNORECASE):
        flag_as_incomplete(file, pattern)
```

**Substantiveness Checklist:**
- [ ] No TODO/FIXME comments in delivered code
- [ ] No placeholder text in Report
- [ ] No empty function bodies
- [ ] Data has expected variation (not all same value), per the value summaries in execution or QA logs
- [ ] Count columns have non-zero values, per the same log evidence
- [ ] All Report sections have content

#### 3. What Must Be WIRED (Critical Connections)

These connections between components must be valid:

| Connection | Verification | Status |
|------------|--------------|--------|
| Report → Figures | All figure references point to existing files | [ ] |
| Notebook → Data | Import statements load from correct paths | [ ] |
| Plan → Decisions | All methodology decisions documented | [ ] |
| Report → Citations | Report References section includes all citations from STATE.md > Citations Accumulated | [ ] |
| Files → Naming convention | All files follow YYYY-MM-DD pattern | [ ] |

**Verification Protocol:**
1. Read figure references in Report, verify paths exist
2. Check notebook imports, verify data files exist
3. Compare Plan decisions to implementation
4. Verify Report References includes all STATE.md > Citations Accumulated entries; cross-reference against CITATION_REFERENCE.md if available

#### Verification Execution Protocol

Execute verification in this order:

```
1. EXISTENCE CHECK
   └─ Run: ls -la [project]/**/*
   └─ Verify all required files present
   └─ Check file sizes (non-zero)

2. SUBSTANTIVENESS CHECK
   └─ Scan for stub indicators (TODO, FIXME, TBD)
   └─ Verify non-placeholder content
   └─ Check data has expected variation

3. WIRING CHECK
   └─ Trace Report → Figure references
   └─ Verify Notebook → Data imports

4. TRUTH CHECK
   └─ Compare Report conclusions to research question
   └─ Verify Plan.md commitments fulfilled
   └─ Check checkpoint statuses in STATE.md

5. EXECUTION CHECK (Python: read-only; data-verifier never runs `marimo export`)
   └─ Python 6a: `marimo check {PROJECT_DIR}/{notebook} --format json --select MB` (reads only; never
      `--fix`, `--unsafe-fixes` or `--strict`). PASS: exit 0, `summary.errored` false,
      `summary.files_with_issues` 0
   └─ Python 6b evidence, without re-executing: the session snapshot
      `{PROJECT_DIR}/__marimo__/session/{notebook}.json` that Stage 9's `marimo export html` wrote
      ├─ exists and is newer than the notebook:
      │  `ls -l --time-style=full-iso {PROJECT_DIR}/{notebook} {PROJECT_DIR}/__marimo__/session/{notebook}.json` (quote it)
      └─ `jq -c '{cells: (.cells | length), no_output: ([.cells[] | select((.outputs | length) == 0)] | length), errors: ([.cells[] | select(any(.outputs[]?; .type == "error"))] | length)}' {PROJECT_DIR}/__marimo__/session/{notebook}.json`
         prints `errors` 0, `no_output` 0, and `cells` equal to the notebook's cell count: the Grep
         tool in count mode (`output_mode: "count"`), pattern `^@app.cell`, path `{PROJECT_DIR}/{notebook}`,
         where available, else `grep -c '^@app.cell' {PROJECT_DIR}/{notebook}` via Bash
   └─ Snapshot missing or older than the notebook, `no_output` > 0, or the cell count differs: NOT VERIFIED.
      The orchestrator has Stage 9 Step 6 re-run; data-verifier does not run the export.
      Any `errors` > 0: the Stage 9 execution check did not pass (report the failing cells)
   └─ Python 6c evidence, read-only (data-verifier never runs the decompiler): the folder Stage 9's
      verbatim fidelity check wrote, `{PROJECT_DIR}/__marimo__/stage9_check/decompiled_{notebook-stem}_{n}`
      ├─ exists, and its MANIFEST.md is newer than the notebook:
      │  `ls -l --time-style=full-iso {PROJECT_DIR}/{notebook} {PROJECT_DIR}/__marimo__/stage9_check/decompiled_{notebook-stem}_[0-9]*/MANIFEST.md`
      │  (quote it; the folder names end in a number, so `[0-9]*` skips folders of a notebook whose name
      │  only starts with `{notebook-stem}`, such as `{notebook-stem}_draft.py`). Use the folder whose
      │  MANIFEST.md is newest; call it `{folder}`
      ├─ belongs to this notebook: the Grep tool where available, else `grep -n` via Bash, pattern
      │  `^\*\*Source Notebook:\*\* `, path `{folder}/MANIFEST.md`, prints one line whose file name, between its backticks, is exactly
      │  `{notebook}` (quote it). Any other name is NOT VERIFIED: `[0-9]*` still matches the folders of a notebook named
      │  `{notebook-stem}_2.py`, so the newest folder can belong to another notebook
      ├─ (i) + (ii): the Grep tool where available, pattern `Validated source/log associations|Legacy non-raw|can close their code fence`,
      │  else `grep -n -e 'Validated source/log associations' -e 'Legacy non-raw' -e 'can close their code fence'`
      │  via Bash, path `{folder}/MANIFEST.md`: the legacy-literal count and the early-fence count are 0, and the
      │  validated count equals the number of final-version scripts found in (iii)
      ├─ (iii): the decompiled paths (Glob tool, pattern `stage*/*.py`, path `{folder}`; or `ls -R {folder}`)
      │  are exactly the final versions in the four stage folders of `{PROJECT_DIR}/scripts`
      │  (`stage5_fetch`, `stage6_clean`, `stage7_transform`, `stage8_analysis`; per task the
      │  highest letter suffix wins, `_b` over `_a` over the base name)
      └─ (iv): `git diff --no-index --numstat --ignore-space-at-eol --ignore-blank-lines {PROJECT_DIR}/scripts {folder}`
         (reads only; exits 1 because MANIFEST.md differs, so judge by the lines): every line is an
         ` => dev/null}` line or the single line whose path starts with `/{dev/null => ` and ends in
         `/MANIFEST.md}`
   └─ No such folder, every MANIFEST.md older than the notebook, or a newest MANIFEST.md that names
      another notebook: NOT VERIFIED. The orchestrator has Stage 9 Step 6 re-run (a re-run writes a
      new, newest folder for this notebook). Any failed condition: the notebook does not archive the
      final scripts verbatim (report the missing, extra or differing paths)
   └─ R, read-only (data-verifier never runs `quarto render`, which writes the HTML): Stage 9's render
      evidence. notebook-assembler ran `quarto render {PROJECT_DIR}/{notebook}` (Step 6) and reported
      its outcome, which the orchestrator passes in the dispatch. Check that the rendered
      `{PROJECT_DIR}/{notebook-stem}.html` exists and is newer than the `.qmd`:
      `ls -l --time-style=full-iso {PROJECT_DIR}/{notebook} {PROJECT_DIR}/{notebook-stem}.html` (quote it)
   └─ No HTML, an HTML older than the `.qmd`, or no reported render outcome: NOT VERIFIED. The
      orchestrator has notebook-assembler re-run Stage 9 Step 6; a reported render error means the
      Stage 9 check did not pass
```

`{notebook}` is the notebook file name (e.g. `2026-01-24_Title.py`, or `.qmd` for R); `{notebook-stem}` is the same name without its extension. See notebook-assembler Step 6 for all three checks; `marimo run --headless` is a server and executes nothing. data-verifier derives the 6c final-version list itself from the scripts listing rather than taking it from the notebook or the MANIFEST, so (ii) and (iii) are checked against an independent expectation; the MANIFEST's legacy-literal and early-fence counts are the only read-only record of condition (i), and a notebook with a non-raw log literal, or with a log line that cuts its displayed log off, can pass (ii)-(iv).

---

### Traditional Review Checklist

In addition to goal-backward verification, complete these traditional checks:

#### 1. Alignment with Original Request

| Element from Request | Addressed? | Location |
|---------------------|------------|----------|
| [Extract each element] | Yes/No | [Where in deliverables] |

#### 2. Clarification Fulfillment

| Clarification | Implemented? | Notes |
|---------------|--------------|-------|
| [Each clarification] | Yes/No | [How implemented] |

#### 2a. Confirmed Pre-Flight Scope (Full Pipeline)

Read the Plan's `### Confirmed Pre-Flight Scope (Full Pipeline)` and `### User-Referenced Materials (Full Pipeline)` subsections. A scope the user narrowed or reshaped at the pre-flight binds the deliverables, not the original request alone; a departure counts as met only when the Plan's Decisions Log records it.

| Confirmed scope item, decision, or referenced material | Honoured? | Location |
|-----------------------------------------------------------|-----------|----------|
| [Each confirmed scope item and decision; each material and what it defines] | Yes/No/Departure logged | [Where in deliverables, or the Decisions Log entry] |

#### 3. Plan Commitments

| Commitment | Fulfilled? | Deviation Notes |
|------------|------------|-----------------|
| Data source | Yes/No | |
| Methodology | Yes/No | |
| Output format | Yes/No | |
| Visualizations | Yes/No | |

#### 4. Quality Checklist

| Category | Item | Status |
|----------|------|--------|
| **Data Integrity** | CP1-CP4 passed | [ ] |
| | Coded values handled | [ ] |
| | Suppression documented | [ ] |
| **Documentation** | Plan complete | [ ] |
| | Notebook documented (Marimo or Quarto) | [ ] |
| | Report complete | [ ] |
| | Citations included | [ ] |
| | LEARNINGS.md created | [ ] |
| **Files** | All files named correctly | [ ] |
| | Parquet saved | [ ] |
| | Figures exported | [ ] |

#### 5. Deviations

Document any deviations from the original Plan:

| Deviation | Reason | Impact |
|-----------|--------|--------|
| [What changed] | [Why] | [Effect] |

### Review Outcome

The outcome uses data-verifier's status vocabulary (`.claude/agents/data-verifier.md` § Output Format; Step 1 > Expected Output above):

**PASSED:** All checks complete, proceed to delivery.

**ISSUES_FOUND (WARNING only):** Log the warnings in STATE.md § Final Review Log and proceed to delivery with caveats.

**ISSUES_FOUND (BLOCKER), or a DATA-VERIFIER STOP:** Escalate to the user with the specific failures and remediation options, then:
1. Document issues
2. Resolve issues
3. Re-run affected checkpoints
4. Re-run Final Review

---

### Step 2: Orchestrator Consolidation and Delivery

1. **Check Alignment**
   - Original request fulfilled?
   - Clarifications implemented?
   - Confirmed pre-flight scope honoured, and referenced materials used (Full Pipeline)?
   - Plan commitments met?

2. **Document Deviations**
   - What changed from Plan.md?
   - Why?
   - What's the impact?

3. **Update STATE.md**
   - Fill Final Review Log section
   - Record data-verifier outcome and any warnings

4. **Consolidate LEARNINGS.md (REQUIRED)**
   - Review incremental entries captured during Stages 5-8
   - Fill gaps in sections still empty
   - Expand quick-capture entries where warranted
   - Deduplicate entries describing the same insight
   - Ensure minimum sections populated: What Worked Well, What Didn't Work, Access/Data Gotchas
   - Flush any remaining signals from STATE.md buffer
   - See "Lessons Learned Consolidation" section below for the full consolidation protocol

5. **Generate System Update Action Plan (REQUIRED)**
   - Add "System Update Action Plan" section to LEARNINGS.md
   - For each learning: determine if it generalizes beyond this project
   - If yes: identify target file(s) and draft concrete change description
   - If no: place in "Not Actionable" with brief reasoning
   - Assign priority: P1 (correctness), P2 (efficiency), P3 (polish)
   - This plan is NOT auto-executed — it serves as a work queue
   - Include action item count in delivery message

6. **Deliver to User**
   - Summary message
   - File locations
   - Key findings
   - Limitations

#### Delivery Format

After passing Final Review, deliver to user:

```
**Analysis Complete: [Title]**

**Summary:**
[2-3 sentence summary of findings]

**Deliverables:**
- Plan: `research/[folder]/[Plan file]`
- Notebook: `research/[folder]/[Notebook file]` (Marimo `.py` for Python, Quarto `.qmd` for R)
- Report: `research/[folder]/[Report file]`
- Data: `research/[folder]/data/`
- Figures: `research/[folder]/output/figures/`
- Lessons file: `research/[folder]/LEARNINGS.md` (what this project taught us: data quirks, decisions, and ideas for improving DAAF)
- Session logs: `research/[folder]/logs/`

[If any working files were moved out of scratch for the record:]
**Files moved for the record:**
- `[old path]` → `[new path]`

**Explore Session Logs:**
This session's transcript should reach `logs/` when the session ends. After that, to browse the session timeline in your browser, choose **3) View Session Logs** in the DAAF Control Panel and pick this project. (From a terminal in the container, `bash /daaf/scripts/generate_log_viewer.sh /daaf/research/[folder]` does the same.)

**Key Findings:**
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

**Limitations:**
- [Key limitation 1]
- [Key limitation 2]

**Data Citation:**
> [Full citation]

**Lessons Learned:** [Brief summary of key insights captured - data access gotchas, methodology improvements, etc.]

[If System Update Action Plan has action items:]
**Framework Updates Available:** The analysis generated [N] action items for improving DAAF's skills, agents, or reference files. To incorporate these into the framework, start a new session and say "incorporate learnings from [project name]" — this will use Framework Development mode to process the action plan.

Let me know if you have any questions or would like any modifications.
```

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

### Lessons Learned Consolidation

This section defines the complete consolidation and action plan procedure for Stage 12. LEARNINGS.md should already contain incremental entries captured during Stages 5-8 via Learning Signals.

#### Step A: Consolidation

By Stage 12, LEARNINGS.md should already contain incremental entries from Stages 5-8. The orchestrator now consolidates:

1. **Review incremental entries** — Are there sections still empty? Reflect on whether signals were missed or if there genuinely were no learnings in that category.
2. **Expand quick-capture entries** — Entries that warrant more detail get expanded with context, examples, and recommendations.
3. **Deduplicate** — Multiple signals about the same issue get merged into one entry.
4. **Ensure minimum sections populated:** What Worked Well, What Didn't Work, Access/Data Gotchas.
5. **Flush any remaining signals** from STATE.md buffer.

Because entries are captured incrementally, consolidation is a review-and-polish task, not a reconstruction from memory.

#### Step B: System Update Action Plan

After consolidation, the orchestrator adds a final section to LEARNINGS.md:

```markdown
---

## System Update Action Plan

*Generated at project completion. Each item maps a learning to a specific
system file with a proposed change. This plan is NOT auto-executed — it
serves as a work queue for future system maintenance. To process this
queue, use Framework Development mode with the "Incorporate Learnings"
work type, which scans project LEARNINGS.md files and presents a
consolidated backlog for implementation.*

### Priority Legend
- **P1 (High):** Prevents incorrect results in future analyses
- **P2 (Medium):** Improves efficiency or clarity
- **P3 (Low):** Nice-to-have improvement

### Action Items

| # | Learning | Target File | Change Type | Proposed Change | Priority |
|---|---------|-------------|-------------|-----------------|----------|
| 1 | [1-line learning summary] | `path/to/file.md` | [Add/Update/Clarify] | [Specific proposed change] | P1 |
| 2 | ... | ... | ... | ... | P2 |

### Grouped by Target

#### Skills (`.claude/skills/*/SKILL.md`)
- [ ] [Skill name]: [What to add/change] (from Learning #N)

#### Agents (`.claude/agents/*.md`)
- [ ] [Agent name]: [What to add/change] (from Learning #N)

#### Agent Reference (`agent_reference/*.md`)
- [ ] [File name]: [What to add/change] (from Learning #N)

#### Universal Rules (`CLAUDE.md`) and Orchestrator Skill
- [ ] [Section]: [What to add/change] (from Learning #N)

### Not Actionable (Context Only)
- [Learnings that are project-specific and don't generalize to system updates]
```

The orchestrator produces this by:
1. Reading each learning entry in the consolidated LEARNINGS.md
2. For each: determining if it generalizes beyond this project
3. If yes: identifying the specific target file(s) and drafting a concrete change description
4. If no: placing it in "Not Actionable" with brief reasoning
5. Assigning priority based on impact (P1 = correctness, P2 = efficiency, P3 = polish)

#### LEARNINGS.md Template

*This template is created as a skeleton at Stage 4 (project metadata + empty section headers) and populated incrementally during Stages 5-8 via Learning Signals. At Stage 12, entries are consolidated and the System Update Action Plan is appended.*

```markdown
# Learnings: [Project Title]

**Date:** YYYY-MM-DD
**Data Sources:** [list]
**Analysis Type:** [description]

---

## What Worked Well

Approaches that succeeded and should be reused:

- **[Technique/Pattern]:** [Description of what worked and why]
- **[Technique/Pattern]:** [Description]

---

## What Didn't Work

Approaches that failed, with explanations:

- **[Approach]:** [What was tried]
  - **Why it failed:** [Root cause]
  - **Alternative:** [What worked instead]

- **[Approach]:** [What was tried]
  - **Why it failed:** [Root cause]
  - **Alternative:** [What worked instead]

---

## Surprises

Unexpected findings about data, access, or methodology:

- **[Finding]:** [Description]
  - **Impact:** [How this affected the analysis]
  - **Recommendation:** [How to handle in future]

---

## Access/Data Gotchas

Specific issues with data sources worth documenting:

### [Source Name] (e.g., CCD)

- **[Variable/Data Source]:** [Issue description]
  - **Example:** [Concrete example]
  - **Workaround:** [How to handle]

### [Source Name]

- **[Variable/Data Source]:** [Issue description]

---

## Time Sinks

What took longer than expected and how to avoid:

- **[Task]:** [What took extra time]
  - **Root cause:** [Why]
  - **Optimization:** [How to avoid in future]
  - **Estimated time saved:** [if applicable]

---

## Reusable Patterns

Code snippets, queries, or approaches to extract for reuse:

### [Pattern Name]

**Use case:** [When to use this]

```python
# [Code snippet]
```

**Notes:** [Any caveats or variations]

---

## Data Quality Notes

Issues specific to this dataset/analysis:

| Variable | Issue | Rate | Handling |
|----------|-------|------|----------|
| [var] | [issue] | [X%] | [approach] |

---

## Questions for Future Investigation

Open questions raised by this analysis:

- [ ] [Question 1]
- [ ] [Question 2]
- [ ] [Question 3]

---

## Recommendations for Similar Analyses

If someone were to do a similar analysis:

1. **Start with:** [First step recommendation]
2. **Watch out for:** [Key pitfall]
3. **Don't bother with:** [Approach to skip]
4. **Make sure to:** [Critical step not to miss]
```

#### Quick Capture Template

*This is the primary format used during incremental capture (not just a convenience shortcut). Learning Signals from agents are expanded into quick-capture entries when flushed to LEARNINGS.md.*

For rapid capture during analysis, use this abbreviated format:

```markdown
## Quick Note: [timestamp]

**Category:** [Access/Data/Method/Perf/Process]
**Issue:** [One-line description]
**Context:** [What I was doing]
**Solution:** [What worked]
**Flag for consolidation:** [Yes/No]
```

These quick notes can be expanded into full entries at Stage 12.

#### Learning Categories Reference

##### Category: Data Access Behavior

- Rate limiting patterns
- Variable naming inconsistencies
- File size inconsistencies or issues
- Authentication/access issues

##### Category: Data Quality

- Suppression patterns by source
- Missing value encoding
- Year-over-year definition changes
- State-level reporting variations
- COVID-19 data impacts

##### Category: Methodology

- Transformation approaches
- Aggregation strategies
- Join key selection
- Validation techniques
- Visualization patterns

##### Category: Performance

- Query optimization
- Bulk download strategies
- Memory management
- Parallel processing
- Caching approaches

##### Category: Process

- Stage ordering insights
- Checkpoint timing
- Error recovery patterns
- User communication
- Documentation practices

#### Anti-Patterns

##### Don't Do

- Wait until end to document (you'll forget details)
- Document only failures (successes are valuable too)
- Skip the "why" (reasons matter more than what)
- Duplicate existing documentation (link instead)
- Over-generalize from single instances (note sample size)
- Treat Stage 12 as the primary capture point (use incremental capture instead)

##### Do Instead

- Capture in the moment
- Document both successes and failures
- Always explain the reason
- Reference existing docs, extend don't repeat
- Be specific about when insights apply

### Gate Criteria (G12)

- [ ] integration-checker (Stage 12, full scope) returned CONNECTED, or ISSUES FOUND with WARNING only (logged in STATE.md § Integration Checks); its return was persisted at `output/preliminary_notes/{date}_stage12_integration-check.md` and that path was passed to data-verifier
- [ ] All alignment checks pass
- [ ] Quality verified
- [ ] Deviations documented
- [ ] STATE.md updated with Final Review Log
- [ ] **LEARNINGS.md consolidated** (incremental entries reviewed, gaps filled)
- [ ] **System Update Action Plan section present** (≥1 action item or "no generalizable learnings")
- [ ] **Key findings flagged for repository consolidation** (in Action Plan)
- [ ] **Action item count included in delivery message**
- [ ] **STATE.md finalized:** Status: Complete, all checkpoints marked, Session History complete
- [ ] **Session logs collected** into `logs/` (WARNING if empty or not run — does not block delivery)
- [ ] User notified with delivery summary

---

## Verification Checklists

Apply this checklist after the data-verifier subagent returns its final review findings.

### Stage 12 (Final Verification) Output Verification

- [ ] Independent assessment performed (expectations listed before Plan comparison)
- [ ] All four verification layers completed (Existence, Substantive, Wired, Coherent)
- [ ] Research question stress test result stated with reasoning
- [ ] At least one key finding traced end-to-end (Telephone Game test performed)
- [ ] Confidence assessment completed for all five aspects with rationale
- [ ] Verification Quality Self-Check results included (all 8 questions)
- [ ] If PASSED: conclusion articulates WHY the analysis is sound, not just absence of failures
