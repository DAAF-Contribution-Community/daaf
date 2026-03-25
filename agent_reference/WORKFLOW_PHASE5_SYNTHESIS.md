# Workflow Reference: Phase 5 — Synthesis & Delivery

Stages 11, 12. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline.md`.

---

## Stage 11: Report Generation

**Executor:** report-writer agent (`general-purpose`)
**Purpose:** Synthesize all pipeline artifacts into a stakeholder-appropriate report

### Upstream Inputs

| Input | Source | Purpose |
|-------|--------|---------|
| Plan.md | Stage 4 | Research question, methodology, research outcomes, risk register (frozen after Stage 4.5) |
| Marimo notebook (.py) | Stage 9 | Complete technical record: all scripts + execution logs |
| STATE.md | Maintained throughout | Checkpoint statuses, key decisions, blockers, runtime risks, QA findings summary, final review log |
| LEARNINGS.md | Maintained throughout | Data quality insights, methodology lessons |
| Stage 10 QA summary | Stage 10 | Aggregated QA findings (WARNINGs, resolved BLOCKERs) |
| Statistical results | Stage 8.1 (`output/analysis/`) | Analysis findings for Key Findings and interpretation |
| Figure files | Stage 8.2 (`output/figures/`) | Visualizations to embed in Key Findings |
| Citation text | Stage 6 (education-data-context) | Pre-formatted data source citations |
| Analysis dataset metadata | Stage 7 | Final dataset shape, column list, key statistics |

### Section-Source Mapping

The report-writer follows a systematic mapping from REPORT_TEMPLATE.md sections to pipeline artifacts:

| Report Section | Primary Source | Secondary Sources |
|---|---|---|
| Executive Summary | Plan.md Research Outcomes + notebook execution logs | LEARNINGS.md |
| Research Question | Plan.md (verbatim) | — |
| Data & Methods | Plan.md Methodology + Stage 5-6 execution logs | STATE.md checkpoints |
| Quality Assurance | STATE.md QA Findings Summary | STATE.md checkpoint statuses |
| Key Findings | Stage 7 transforms + Stage 8.1 analysis results + Stage 8.2 figures | Plan.md Research Outcomes |
| Limitations | Plan.md Risk Register + STATE.md Runtime Risks + source caveats + suppression rates + LEARNINGS.md | STATE.md blockers |
| Citations | Stage 6 citation text | Plan.md Data Sources table |

### Actions

1. **Read upstream artifacts** — Plan.md, Notebook, STATE.md, LEARNINGS.md
2. **Verify figures** — Confirm all figure files exist before referencing
3. **Draft report** — Follow REPORT_TEMPLATE.md section by section using Section-Source Mapping
4. **Cross-check Research Outcomes** — Every Research Outcome from Plan.md addressed in Key Findings
5. **Write Report.md** — Save to project folder with date prefix

### Invocation Template: report-writer

**Agent:** report-writer
**Subagent Type:** `general-purpose`
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

    **CITATION TEXT (from Stage 6):**
    {citation_text}

    **ANALYSIS DATASET METADATA:**
    {dataset_metadata}

    **FIGURE FILES:**
    {figure_file_list}

    **AI DISCLOSURE METADATA (from STATE.md Session Metadata):**
    - DAAF Version: {daaf_commit_hash}
    - Model ID: {model_id}
    - Session Date(s): {session_dates}

    **TASK:**
    Generate the stakeholder report following REPORT_TEMPLATE.md.
    Include the AI Use Disclosure section (Step 6b) using AI_DISCLOSURE_REFERENCE.md.
    Read Plan.md, Notebook, STATE.md, and LEARNINGS.md.
    Follow the Section-Source Mapping for every section.
    Verify all figure references before embedding.
    Cross-check all Research Outcomes from Plan.md.
    Write Report.md to the project folder.

    Return findings using the Report Writer Output Format.""",
    subagent_type: "report-writer"
})
```

#### Pre-Report: Session Log Collection

Before invoking report-writer, collect session transcripts into the project:
```
bash {BASE_DIR}/scripts/collect_session_logs.sh {PROJECT_DIR}
```
Then update STATE.md: confirm `logs/` contains collected files, and fill in the `Archive` column in the Session History table with the archive filenames for each session row.

#### Context Completeness Checklist (Stage 11)

Before invoking report-writer, verify:
- [ ] Plan.md path provided (absolute) — methodology, research question, risk register
- [ ] Notebook path provided (absolute)
- [ ] STATE.md path provided (absolute)
- [ ] LEARNINGS.md path provided (absolute)
- [ ] Stage 10 QA summary inlined (not just path reference)
- [ ] Citation text inlined from Stage 6
- [ ] Analysis dataset metadata inlined (shape, columns, key stats)
- [ ] Figure file paths listed (all files in output/figures/)
- [ ] Date prefix specified
- [ ] Report filename specified (following naming convention)
- [ ] Project path specified (absolute)
- [ ] DAAF commit hash provided (from STATE.md Session Metadata)
- [ ] Model ID provided (from STATE.md Session Metadata)
- [ ] Session logs collected into `logs/` (collect_session_logs.sh run)

#### Expected Output

report-writer returns:
- **COMPLETE** → Proceed to Stage 12 (data-verifier)
- **COMPLETE_WITH_GAPS** → Log gaps, proceed to Stage 12 (verifier will assess severity)
- **BLOCKED** → Resolve missing inputs, re-invoke

### Gate Criteria (G11)

- [ ] report-writer returned COMPLETE or COMPLETE_WITH_GAPS
- [ ] All REPORT_TEMPLATE.md sections populated (not placeholder text)
- [ ] All figure references resolve to existing files
- [ ] All Research Outcomes from Plan.md addressed in Key Findings
- [ ] Executive Summary is 4-5 sentences
- [ ] All statistics trace to execution logs or dataset metadata
- [ ] Citation text included verbatim
- [ ] AI Use Disclosure section populated (GUIDE-LLM items addressed or marked N/A)

---

## Stage 12: Final Review

**Executor:** Orchestrator invokes `data-verifier` agent (adversarial verification), then performs consolidation
**Purpose:** Adversarial goal-backward verification of completed analysis, followed by lessons consolidation and delivery

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

    **TASK:**
    Perform adversarial goal-backward verification of the completed
    analysis. Verify all four layers (existence, substantiveness,
    wiring, coherence). Perform research question stress test,
    Telephone Game trace, alternative interpretation probing, silent
    failure audit, and QA history review.

    Return findings using the Data Verifier Output Format.""",
    subagent_type: "data-verifier"
})
```

#### Expected Output

data-verifier returns:
- **VERIFIED** → Proceed to Step 2 (consolidation and delivery)
- **VERIFIED_WITH_WARNINGS** → Log warnings in STATE.md Final Review Log, proceed to Step 2
- **FAILED** → STOP, escalate to user with specific failures and remediation options

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
| No coded values in analysis variables | Check processed data | [ ] |
| Suppression rate acceptable (<50%) | Review CP2 results | [ ] |
| Cross-state comparisons valid (if any) | Check against validity matrix | [ ] |

**Verification:** For each item, actively verify (don't assume). Check file contents, run queries, read sections.

#### 2. What Must EXIST (Concrete Artifacts)

These files must exist in the project folder:

| Artifact | Path | Exists? | Substantive? |
|----------|------|---------|--------------|
| Plan document | `[project]/YYYY-MM-DD_[Title]_Plan.md` | [ ] | [ ] |
| Plan tasks | `[project]/YYYY-MM-DD_[Title]_Plan_Tasks.md` | [ ] | [ ] |
| Marimo notebook | `[project]/YYYY-MM-DD_[Title].py` | [ ] | [ ] |
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

**Stub Detection Protocol:**

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
- [ ] Data has expected variation (not all same value)
- [ ] Count columns have non-zero values
- [ ] All Report sections have content

#### 3. What Must Be WIRED (Critical Connections)

These connections between components must be valid:

| Connection | Verification | Status |
|------------|--------------|--------|
| Report → Figures | All figure references point to existing files | [ ] |
| Notebook → Data | Import statements load from correct paths | [ ] |
| Plan → Decisions | All methodology decisions documented | [ ] |
| Report → Citations | Citation text matches data sources used | [ ] |
| Files → Naming convention | All files follow YYYY-MM-DD pattern | [ ] |

**Verification Protocol:**
1. Read figure references in Report, verify paths exist
2. Check notebook imports, verify data files exist
3. Compare Plan decisions to implementation
4. Verify citation sources match data used

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

5. EXECUTION CHECK
   └─ Load notebook: marimo run [notebook].py --host 0.0.0.0 --port 2718 --headless
```

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
| | Notebook documented | [ ] |
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

**PASSED:** All checks complete, proceed to delivery.

**ISSUES FOUND:**
1. Document issues
2. Resolve issues
3. Re-run affected checkpoints
4. Re-run Final Review

---

### Step 2: Orchestrator Consolidation and Delivery

1. **Check Alignment**
   - Original request fulfilled?
   - Clarifications implemented?
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

6. **Generate System Update Action Plan (REQUIRED)**
   - Add "System Update Action Plan" section to LEARNINGS.md
   - For each learning: determine if it generalizes beyond this project
   - If yes: identify target file(s) and draft concrete change description
   - If no: place in "Not Actionable" with brief reasoning
   - Assign priority: P1 (correctness), P2 (efficiency), P3 (polish)
   - This plan is NOT auto-executed — it serves as a work queue
   - Include action item count in delivery message

7. **Deliver to User**
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
- Notebook: `research/[folder]/[Notebook file]`
- Report: `research/[folder]/[Report file]`
- Data: `research/[folder]/data/`
- Figures: `research/[folder]/output/figures/`
- Learnings: `research/[folder]/LEARNINGS.md`

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

This replaces the old "create from scratch at Stage 12" approach. Because entries were captured incrementally, consolidation is a review-and-polish task, not a reconstruction-from-memory task.

#### Step B: System Update Action Plan

After consolidation, the orchestrator adds a final section to LEARNINGS.md:

```markdown
---

## System Update Action Plan

*Generated at project completion. Each item maps a learning to a specific
system file with a proposed change. This plan is NOT auto-executed — it
serves as a work queue for future system maintenance.*

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

---

## Pre-Pipeline Skills

### data-ingest

**Purpose:** Profile new datasets and author comprehensive Skills
**Stage:** Pre-pipeline (on demand, when new data files arrive)
**Agent:** `data-ingest` (see `.claude/agents/data-ingest.md`)
**Subagent:** general-purpose

For the complete invocation pattern, see `.claude/agents/README.md` data-ingest section
or `.claude/agents/data-ingest.md` Invocation section.

---
