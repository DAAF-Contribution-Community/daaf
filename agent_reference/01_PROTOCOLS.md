# Protocol Reference

This document contains the full details for all six protocols. Protocols 1-5 are essential to every Full Pipeline analysis. Protocol 6 is used for session recovery.

---

## Protocol Overview

| Protocol | Name | Purpose | Phase | Executed By |
|----------|------|---------|-------|-------------|
| **1** | Data Discovery | Identify and understand available data | Phase 1 | Subagents (Plan) |
| **2** | Data Acquisition | Retrieve and clean data from data access mirrors | Phase 3 | Subagents (general-purpose) |
| **3** | Validation Checkpoints | Validate data at critical points | Phase 3-4 | Orchestrator + Code |
| **4** | Plan Management | Maintain Plan as persistent memory | Phase 2, ongoing | Orchestrator |
| **5** | Final Review | Verify completeness before delivery | Phase 5 | Orchestrator (Stage 11 via report-writer agent) |
| **6** | Session Recovery | Resume interrupted analyses | Any | Orchestrator |

---

# Protocol 1: Data Discovery

**Phase:** 1 (Discovery & Scoping)
**Stages:** 2-3
**Execution:** Via subagents with `education-data-explorer` and `*-data-source-*` skills

## Purpose

Before writing any data query or analysis code, discover and understand available data sources. This protocol ensures the agent has complete, accurate information about what data exists and its limitations.

## Stage 2: Data Exploration

**Skill:** `education-data-explorer`
**Subagent Type:** `Plan`

### Invocation Pattern

See `03_SKILL_INVOCATIONS.md` for the complete Stage 2 invocation template.

### Expected Output

**From Stage 2:**
- Recommended data level (schools, school-districts, college-university)
- Candidate endpoints with source, description, and year coverage
- Key variables identified for research question
- Variables flagged for deep-dive with rationale
- Limitations encountered during exploration
- Completeness assessment checklist

### Gate Criteria (G2)

Before proceeding to Stage 3:
- [ ] At least one candidate endpoint identified
- [ ] Key variables identified for research question
- [ ] Variables requiring deep-dive explicitly flagged
- [ ] Year coverage verified
- [ ] If no data found: STOP and escalate to user

---

## Stage 3: Source Deep-Dive

**Skills:** `*-data-source-*` (one per source)
**Agent:** `source-researcher` (see `agents/source-researcher.md`)
**Subagent Type:** `Plan`

### Invocation Pattern

See `03_SKILL_INVOCATIONS.md` for the complete Stage 3 invocation template.

**Note:** If multiple sources are needed (e.g., CCD + CRDC), invoke Stage 3 separately for each source.

### Expected Output

**From Stage 3:**
- Source-specific caveats with mitigation strategies
- Complete coded value mappings
- Suppression patterns and thresholds
- Cross-state comparability assessment
- Critical warnings

### Gate Criteria (G3)

Before proceeding to Stage 3.5:
- [ ] All flagged variables investigated
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings have mitigation strategies
- [ ] All LOW confidence findings resolved or escalated

---

## Stage 3.5: Findings Synthesis

**When:** After Stage 3 completes (all sources explored)
**Agent:** `research-synthesizer` (see `agents/research-synthesizer.md`)
**Subagent Type:** `general-purpose`
**Purpose:** Consolidate parallel Stage 2-3 findings into unified planning guidance

### Purpose

- Consolidate all Stage 2 and Stage 3 findings into unified planning guidance
- Resolve any cross-source conflicts or overlapping coverage
- Assess cross-source join feasibility and data compatibility

### Expected Output

- Unified summary of all source findings
- Conflict resolution (where sources disagree)
- Recommended approach for Plan creation (Stage 4)
- Cross-source join feasibility and key considerations

### Gate Criteria (G3.5)

Before proceeding to Phase 2 (Plan Creation):
- [ ] Synthesis complete — all source findings consolidated
- [ ] Conflicts between sources identified and resolved (or flagged for Plan)
- [ ] Cross-source join feasibility assessed with key considerations documented
- [ ] If synthesis reveals infeasibility: STOP and escalate to user

---

## Re-run Guidance

See `06_ERROR_RECOVERY.md` "Re-run Procedures" for the complete re-run guidance table and mode definitions (Refresh vs Additive).

---

# Protocol 2: Data Acquisition

**Phase:** 3 (Data Acquisition & Preparation)
**Stages:** 5-6
**Execution:** Via subagents with `education-data-query` and `education-data-context` skills

## Purpose

Retrieve data from the data access mirrors and apply proper context/cleaning based on source-specific knowledge.

## File-First Execution

**CRITICAL:** All code in Protocol 2 follows the **file-first pattern**:
1. Write script to `scripts/stage{5,6}_{type}/` before execution
2. Execute as a single Bash call with absolute paths: `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/...` (automatically captures output and appends execution log)
3. Version failed scripts (`_a`, `_b`, etc.) — re-run wrapper on new version

Closely read `agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

## Stage 5: Data Retrieval

**Skill:** `education-data-query`
**Subagent Type:** `general-purpose` (requires file write capability)

### Invocation Pattern

See `03_SKILL_INVOCATIONS.md` for the complete Stage 5 invocation template.

### Validation (CP1)

Immediately after data fetch:

```python
# CP1: Post-Fetch Validation
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.to_list()}")
print(f"Types:\n{df.dtypes}")
print(f"Null counts:\n{df.null_count()}")
print(f"Years present: {df['year'].unique().to_list()}")

# STOP conditions
assert len(df) > 0, "STOP: Empty dataset returned"
assert len(df) < 1_000_000, "WARNING: Very large dataset - verify expected"
```

### Gate Criteria (G5)

Before proceeding to Stage 6:
- [ ] Data retrieved successfully
- [ ] Row count within expected range
- [ ] Critical columns present
- [ ] Years match specification
- [ ] Data saved to `data/raw/` (parquet)
- [ ] **If data lag ≥3 years:** User notified and decision documented in Plan
- [ ] **If COVID years (2020-2021) included:** Warning documented in Plan's COVID-19 Data Quality Considerations section
- [ ] **QA review completed for EACH Stage 5 script** (code-reviewer separately invoked immediately after each individual fetch script completes, not batched at stage end)
- [ ] **All QA1 statuses ∈ {PASSED, WARNING}** (any BLOCKER resolved via revision before next script)

---

## Stage 6: Context Application

**Skill:** `education-data-context`
**Subagent Type:** `general-purpose` (requires file write capability)

### Invocation Pattern

See `03_SKILL_INVOCATIONS.md` for the complete Stage 6 invocation template.

### Validation (CP2)

After cleaning:

```python
# CP2: Post-Cleaning Validation
print(f"Original rows: {len(raw_df)}")
print(f"Clean rows: {len(clean_df)}")
print(f"Rows removed: {len(raw_df) - len(clean_df)} ({(len(raw_df) - len(clean_df)) / len(raw_df) * 100:.1f}%)")

# Check suppression rate
suppressed = (raw_df['key_variable'] == -3).sum()
suppression_rate = suppressed / len(raw_df)
print(f"Suppression rate: {suppression_rate:.1%}")

# STOP conditions
assert suppression_rate < 0.5, f"STOP: Suppression rate {suppression_rate:.1%} exceeds 50%"
assert len(clean_df) > len(raw_df) * 0.1, "STOP: >90% data loss after cleaning"
```

### Gate Criteria (G6)

Before proceeding to Stage 7 / Phase 4:
- [ ] Coded values handled appropriately
- [ ] Suppression rate documented and acceptable (<50%)
- [ ] No invalid analysis types attempted
- [ ] Data saved to `data/processed/` (parquet)
- [ ] Citation text generated
- [ ] **QA review completed for EACH Stage 6 script** (code-reviewer separately invoked immediately after each individual cleaning script completes, not batched at stage end)
- [ ] **All QA2 statuses ∈ {PASSED, WARNING}** (any BLOCKER resolved via revision before next script)

---

# Protocol 3: Validation Checkpoints

**Phase:** 3-4 (Data Acquisition through Analysis)
**Execution:** Embedded in code, verified by orchestrator

## Purpose

Validate data at each critical point in the pipeline to catch errors early and ensure data integrity.

## Four Required Checkpoints (CP1-CP4)

See `05_VALIDATION_CHECKPOINTS.md` for CP1-CP4 definitions, STOP thresholds, and Python code templates.

---

## Secondary Validation: QA Checkpoints (QA1-QA4b)

**When:** After each script execution in Stages 5-8
**Executor:** code-reviewer agent (invoked by orchestrator)
**Purpose:** Independent secondary validation of output quality and methodology alignment

CP checkpoints catch **operational failures** (empty data, wrong types). QA checkpoints catch **logical errors** (wrong methodology, data misinterpretation). Both must pass for stage handoff.

**See:** `agent_reference/QA_CHECKPOINTS.md` for complete QA checkpoint definitions (QA1-QA4b), severity classification, recovery protocol, and `agents/code-reviewer.md` for the QA agent protocol.

---

# Protocol 4: Plan Management

**Phase:** 2 (created), ongoing (updated)
**Execution:** Orchestrator

## Purpose

Maintain the Plan document as the single source of truth for the analysis, enabling context transfer to subagents and session continuity.

## Plan Creation (Phase 2, Stage 4)

### Timing

Create the Plan document **after** completing Phase 1 (Discovery) and **before** starting Phase 3 (Data Acquisition).

### Creation Checklist

- [ ] Project folder created: `research/YYYY-MM-DD [Title]/`
- [ ] Plan file created from template
- [ ] Original request captured verbatim
- [ ] Clarifications documented
- [ ] All Stage 2 findings integrated
- [ ] All Stage 3 findings integrated
- [ ] Methodology decisions documented
- [ ] Output specification complete

### Completeness Standard

The Plan must be **self-contained**: any subagent should be able to execute its stage with ONLY the Plan as context (plus skill knowledge).

**Test:** Read the Plan. Could you execute the analysis without any additional conversation context?

### Plan Completeness Verification (REQUIRED)

Before proceeding to Phase 3, verify the Plan meets completeness standards. See `02_WORKFLOW_STAGES.md: Stage 4 - Plan Completeness Gate` for the complete verification checklist.

**Critical sections that must be complete:**
1. Query Specification (all fields populated)
2. Transformation Sequence (all rows complete with validation criteria and cardinality)
3. Validation Checkpoints (expected values defined for CP1-CP4)

**If verification fails:** Do not proceed; complete missing sections first.

## Plan Updates

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

## Risk Register Updates

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

## Plan for Subagent Invocation

When invoking subagents, include relevant Plan sections:

```python
Task({
    description: "Stage [N]: [Name]",
    prompt: """...
    
**CONTEXT FROM PLAN:**
[Paste relevant sections from Plan]
- Query Specification: [from Plan]
- Expected Values: [from Plan]
- Critical Warnings: [from Plan]

...""",
    subagent_type: "..."
})
```

## Learning Signal Handling

All agents include a **Learning Signal** field in their output (per AGENT_TEMPLATE.md Section 6).
The orchestrator extracts and buffers these signals in STATE.md, then flushes to LEARNINGS.md
at phase boundaries.

See CLAUDE.md "Learning Signal Extraction" section for the complete extraction and flush protocol.

---

# Protocol 5: Final Review

**Phase:** 5 (Synthesis & Delivery)
**Stage:** 12
**Execution:** Orchestrator

## Purpose

Verify that the completed analysis aligns with the original request and all Plan commitments have been fulfilled using **goal-backward verification**.

---

## Goal-Backward Verification Framework

Before marking any analysis complete, verify each of the three categories below. This approach works backward from the goal state to ensure nothing is missing.

**Verification Stance:** The data-verifier agent approaches this framework with adversarial skepticism — its default hypothesis is that something was missed. See `agents/data-verifier.md` for the complete adversarial verification protocol including cross-artifact coherence, research question stress testing, and the Hidden Narrative principle.

### 1. What Must Be TRUE (Observable Behaviors)

These are properties that must hold for the analysis to be valid:

| Requirement | Verification Method | Status |
|-------------|---------------------|--------|
| Research question answered with evidence | Read Report conclusions | [ ] |
| All Plan commitments fulfilled | Compare Plan vs. deliverables | [ ] |
| No validation checkpoints failed | Review CP1-CP4 status | [ ] |
| Limitations explicitly documented | Check Report limitations section | [ ] |
| Data transformations preserve integrity | Review transformation log | [ ] |
| No coded values in analysis variables | Check processed data | [ ] |
| Suppression rate acceptable (<50%) | Review CP2 results | [ ] |
| Cross-state comparisons valid (if any) | Check against validity matrix | [ ] |

**Verification:** For each item, actively verify (don't assume). Check file contents, run queries, read sections.

---

### 2. What Must EXIST (Concrete Artifacts)

These files must exist in the project folder:

| Artifact | Path | Exists? | Substantive? |
|----------|------|---------|--------------|
| Plan document | `[project]/YYYY-MM-DD [Title] Plan.md` | [ ] | [ ] |
| Marimo notebook | `[project]/YYYY-MM-DD [Title].py` | [ ] | [ ] |
| Stakeholder report | `[project]/YYYY-MM-DD [Title] Report.md` | [ ] | [ ] |
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

---

### 2b. Substantiveness Check (Stub Detection)

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

---

### 3. What Must Be WIRED (Critical Connections)

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
5. Verify citation sources match data used

---

### Verification Execution Protocol

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
   └─ Verify Plan commitments fulfilled
   └─ Check checkpoint statuses in Plan

5. EXECUTION CHECK
   └─ Load notebook: marimo run [notebook].py --host 0.0.0.0 --port 2718 --headless
```

---

### Agent Integration: Data Verifier

For comprehensive verification, invoke the **data-verifier** agent:

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

**When to use data-verifier agent:**
- Full Pipeline delivery (always)
- After Revision Mode changes
- When user requests verification
- After fixing issues found in prior verification

---

## Traditional Review Checklist

In addition to goal-backward verification, complete these traditional checks:

### 1. Alignment with Original Request

| Element from Request | Addressed? | Location |
|---------------------|------------|----------|
| [Extract each element] | Yes/No | [Where in deliverables] |

### 2. Clarification Fulfillment

| Clarification | Implemented? | Notes |
|---------------|--------------|-------|
| [Each clarification] | Yes/No | [How implemented] |

### 3. Plan Commitments

| Commitment | Fulfilled? | Deviation Notes |
|------------|------------|-----------------|
| Data source | Yes/No | |
| Methodology | Yes/No | |
| Output format | Yes/No | |
| Visualizations | Yes/No | |

### 4. Quality Checklist

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

### 5. Deviations

Document any deviations from the original Plan:

| Deviation | Reason | Impact |
|-----------|--------|--------|
| [What changed] | [Why] | [Effect] |

## Review Outcome

**PASSED:** All checks complete, proceed to delivery.

**ISSUES FOUND:**
1. Document issues
2. Resolve issues
3. Re-run affected checkpoints
4. Re-run Final Review

## LEARNINGS.md Consolidation (REQUIRED)

After data-verifier returns and before delivery, the orchestrator consolidates LEARNINGS.md:

1. Review incremental entries captured during Stages 5-8
2. Fill gaps in sections still empty
3. Deduplicate entries describing the same insight
4. Generate System Update Action Plan section
5. Include action item count in delivery message

See `agent_reference/08_LESSONS_LEARNED.md` for the complete consolidation protocol
and `02_WORKFLOW_STAGES.md` Stage 12 for the consolidation checklist.

## Delivery Format

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

---

# Protocol 6: Session Recovery

**Phase:** Any (recovery protocol)
**Execution:** Orchestrator

## Purpose

Enable stateless recovery when resuming an interrupted analysis after LLM context has been cleared. The Plan document serves as persistent memory for session continuity.

## When to Use

- User returns to an in-progress analysis
- System context has been cleared between sessions
- User references a project by name or date

## Recovery Procedure

### Step 1: Locate Project

Search `research/` directory for matching project folder:
- Match on date: `research/YYYY-MM-DD*/`
- Match on keywords from user's message
- List candidates if multiple matches

### Step 2: Read STATE.md

Read the full STATE.md file. This is the primary recovery document:
- Extract current stage, status, and blockers from **Current Position**
- Note the Plan file path from Current Position table
- Review **Checkpoint Status** tables (CP and QA)
- Review **Transformation Progress** table for per-script status
- Read **Context Snapshot** key findings summary
- Read **Next Actions** for immediate guidance
- Check **Blockers** section for any unresolved issues

### Step 3: Read Plan Selectively

**Do NOT read the entire Plan file.** Use targeted section loading to minimize context consumption and preserve capacity for execution work.

**3a. Build section map:** Search the Plan file for `^## ` headings to get all section names and line numbers (one search call).

**3b. Read Recovery Sections (always load these):**
- `## Original Request & Clarifications` — Anchors the analysis purpose
- `## Goal & Context` — Success criteria and background
- `## Decisions Log` — All methodology decisions made so far
- `## Risk Register` — Active risks and mitigations
- `## Current Status & To-Do's` — Complements STATE.md position info
- `### Transformation Sequence` (within Methodology Specification) — The wave/task summary table only, NOT the full XML task blocks in Executable Task Sequence

**3c. Read stage-conditional sections (only when recovering at or after that stage):**

| Current Stage | Additional Sections to Load |
|---------------|---------------------------|
| 7+ (Transform) | `### Transformation Log` (within Methodology Specification) |
| 9+ (Notebook) | `## Output Specification` |
| 10+ (QA Aggregation) | `## QA Findings Summary` |
| 11+ (Report/Review) | `## Must-Haves (Goal-Backward Verification)`, `## Output Specification`, `## QA Findings Summary` |

**3d. Do NOT load these sections at recovery time (load on-demand when needed):**
- `## Phase 1: Discovery Results` — Already consumed during planning
- `## Executable Task Sequence` — Load the specific wave's task block when dispatching
- `## Validation Checkpoints` — Load the specific CP when executing that checkpoint
- `## File Manifest` — Load when needed for verification
- `## Final Review Log` — Load at Stage 12
- `## Trade-offs Accepted` — Load when referenced
- `## Data Citations` — Load at Stage 11+
- `## Philosophy: Plans are Prompts` — Static preamble, not needed for recovery

### Step 4: Verify File System State

Check which artifacts exist vs. are expected:

```python
expected_files = {
    "plan": f"{date_prefix} {title} Plan.md",
    "notebook": f"{date_prefix} {title}.py",
    "report": f"{date_prefix} {title} Report.md",
    "raw_data": "data/raw/",
    "processed_data": "data/processed/",
    "figures": "output/figures/"
}

# Check existence for each
```

### Step 5: Identify Resume Point

From STATE.md's **Current Position** and **Next Actions**, confirmed by Plan's "Current Status & To-Do's":
- Current Phase: [1-5]
- Current Stage: [1-12]
- Status: [In Progress | Blocked | Complete]
- Last Checkpoint: [CP# result]

Determine what's complete and what remains.

### Step 6: Present Recovery Summary

```markdown
**Session Recovery: [Project Title]**

I found your in-progress analysis:
- Plan: research/YYYY-MM-DD [Title]/YYYY-MM-DD [Title] Plan.md
- Current Stage: [N] - [Stage Name]
- Status: [status]
- Last Checkpoint: [CP#] - [PASSED/FAILED]

**Completed:**
- [✓] Phase 1: Discovery complete
- [✓] Phase 2: Plan created
- [✓] Stage 5: Data retrieved
- [✓] Stage 6: Data cleaned (CP2 passed)

**Remaining:**
- [ ] Stage 7: Transformations (3 of 5 complete)
- [ ] Stage 8-12: Analysis, notebook, QA, report, final review

**Files Present:**
- Raw data: ✓ (data/raw/YYYY-MM-DD_*.parquet)
- Processed data: ✓ (data/processed/YYYY-MM-DD_*.parquet)
- Notebook: ✗ (not yet created)

Ready to continue from Stage 7, Transformation #4?
```

## Recovery from Different Stages

| Stage Interrupted | Recovery Action | Additional Plan Sections to Load |
|-------------------|-----------------|----------------------------------|
| 1-3 (Discovery) | Re-read findings, continue from incomplete stage | `Phase 1: Discovery Results` |
| 4 (Planning) | Check if Plan is complete, update if needed | Full Plan (revision context) |
| 5 (Data Retrieval) | Check if data files exist; re-fetch if missing | Current wave's task block from `Executable Task Sequence` |
| 6 (Context Application) | Check for processed data; re-run if missing | Current wave's task block from `Executable Task Sequence` |
| 7 (Transformation) | Read Transformation Log, resume from next incomplete step | `Transformation Log` + current wave's task block |
| 8 (Analysis & Viz) | Check output directories, regenerate missing outputs | `Transformation Log` + current wave's task block |
| 9 (Notebook Assembly) | Check if notebook exists; if missing, invoke notebook-assembler agent | `Output Specification` |
| 10 (QA Aggregation) | Re-aggregate QA findings from Stages 5-8 | `QA Findings Summary` |
| 11-12 (Delivery) | Check if report exists, regenerate if needed | `Must-Haves`, `Output Specification`, `QA Findings Summary` |

## On-Demand Plan Loading

After recovery, load additional Plan sections as needed during execution. **Do NOT preload these — read them from the Plan file when the specific need arises.**

| Action | Plan Section to Load | How to Find It |
|--------|---------------------|----------------|
| Dispatching a Stage 5-8 task | The specific wave's task block (e.g., `### Wave 3`) from `## Executable Task Sequence` | Search for the wave heading, read to next `### Wave` heading |
| Constructing CP validation | The relevant CP subsection from `## Validation Checkpoints` | Search for the CP heading (e.g., `### CP3`) |
| Reviewing prior discovery | `## Phase 1: Discovery Results` | Search for heading, read to next `## ` heading |
| Checking file inventory | `## File Manifest` | Search for heading, read to end of file |
| Final review (Stage 12) | `## Must-Haves`, `## Output Specification` | Search for each heading |
| Debugging or re-running | Relevant prior wave's task block | Search for the wave heading |

**Procedure:** Search for the target heading in the Plan file (e.g., `### Wave 3`), note the line number, then read from that line to the next same-level heading. This costs one search + one targeted read per section, and avoids loading the full Plan into context.

## Blocked/Failed Recovery

If the analysis is marked as "Blocked" or has failed checkpoints:
1. Read the Issue description from Plan
2. Present issue to user
3. Ask for guidance before proceeding

**Example:**
```markdown
**Recovery Issue: Analysis Blocked**

This analysis is currently blocked at Stage 6 (Context Application).

**Issue:** Suppression rate of 52% exceeds 50% threshold (CP2 failed)

**Options documented in Plan:**
1. Aggregate to district level (reduces suppression)
2. Exclude suppressed variable from analysis
3. Proceed with caveat and document limitation

Which approach would you like to take?
```

## Recovery Verification Checklist

Before resuming work:
- [ ] STATE.md read and understood (current position, checkpoints, blockers, next actions)
- [ ] Plan recovery sections read (Original Request, Goal & Context, Decisions Log, Risk Register, Current Status)
- [ ] Stage-conditional Plan sections loaded if applicable (per Step 3c table)
- [ ] Current stage/status identified and consistent between STATE.md and Plan
- [ ] File system state verified
- [ ] Resume point identified
- [ ] Any blocking issues presented to user
- [ ] User confirmed ready to proceed

