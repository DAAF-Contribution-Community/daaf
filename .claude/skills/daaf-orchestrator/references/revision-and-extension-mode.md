# Revision and Extension Mode

Revision and Extension mode is for modifying or extending existing analyses — fixing bugs, updating scope, changing methodology, or extending prior work. It always operates on a **new version** of existing artifacts, never modifying originals.

## User Orientation

After mode confirmation, briefly orient the user. Key points:

- Locates existing analysis and classifies the change type
- Creates a new version — original is never modified
- Only affected steps re-run, with same quality checks as original

**When to skip:** User has indicated familiarity, or this is a follow-up in the same session.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Revision and Extension Workflow

```
Stage 1: Classify as Revision and Extension Mode → Confirm with user
    ↓
Locate Existing Project
    ├─ Search research/ for the referenced analysis folder
    ├─ Read the COMPLETE existing Plan.md and Plan_Tasks.md
    ├─ Read the existing notebook (marimo `.py` or Quarto `.qmd`) to understand current state
    └─ Read STATE.md and extract original execution context (see below)
    ↓
Classify Revision Type → Confirm with user
    ↓
Create New Version
    ├─ Create new versions of BOTH Plan.md AND Plan_Tasks.md (e.g., 2026-01-24a → 2026-01-24b)
    ├─ Document revision request and type in new Plan.md + updated task specs in new Plan_Tasks.md
    ├─ Resync STATE.md to the revised Plan_Tasks.md BEFORE any re-execution (see Session Management § STATE.md)
    └─ Execute required stages (load full-pipeline-mode.md if needed)
    ↓
Final Review
    └─ Complete full Final Review even for minor fixes
```

### STATE.md Extraction at Revision Start

Read STATE.md and extract:
- **Transformation Progress** — which scripts ran, which succeeded/failed, row counts
- **Runtime Risks** — risks discovered during original execution (separate from Plan.md's planning-phase Risk Register)
- **QA Findings Summary** — aggregated QA results: BLOCKERs resolved, WARNINGs logged, unresolved issues
- **Final Review Log** — Stage 12 verification results (if original execution reached Stage 12)
- **Key Decisions Made** — runtime decisions from Stages 5-12
- **Deviations Applied** — any deviations from the original Plan.md during execution

This context is critical for informed revision planning. Plan.md captures planning-phase intent; STATE.md captures what actually happened during execution. Revisions that ignore STATE.md risk repeating resolved issues or missing known risks.

## Revision Type Classification

Confirm the revision type with the user before proceeding:

| Type | Description | Typical Stages to Re-run |
|------|-------------|-------------------------|
| **Bug Fix** | Code error, wrong filter, incorrect join | Re-run affected stage + downstream |
| **Scope Change** | Add/remove data sources, change geography/years | May re-run from Stage 2 or 5 |
| **Methodology Change** | Different statistical approach, new transformation | Re-run from Stage 7 or 8 |
| **Extension** | Add analysis or visualization to existing work | Stage 8 + downstream |
| **Correction** | Fix factual error in report or interpretation | Stage 11-12 only |

### Decision Tree for Ambiguous Revisions

```
User's Change Request
    |
    +-- Does it fix a code error (wrong filter, bad join, incorrect logic)?
    |   YES → Bug Fix (re-run affected stage + downstream)
    |
    +-- Does it add/remove data sources, change geography, or change years?
    |   YES → Scope Change (may re-run from Stage 2 or 5)
    |
    +-- Does it change the statistical method, model, or transformation approach?
    |   YES → Methodology Change (re-run from Stage 7 or 8)
    |
    +-- Does it add new analysis or visualization to existing, correct work?
    |   YES → Extension (Stage 8 + downstream)
    |
    +-- Does it only fix text, labels, or interpretation in the report?
        YES → Correction (Stage 11-12 only)
```

When ambiguous, prefer the type that re-runs MORE stages (safer). For example, "add a variable to the regression" is a Methodology Change (not Extension) because it changes the statistical approach.

## Version Control Protocol

Version suffixes follow the convention defined in `CLAUDE.md` > "Version Control Protocol" (e.g., original → `a` → `b` → `c`).

**Rules:**
- Always create new version files — never modify existing versions
- All versions remain in the same project folder
- Regenerate data fresh from scripts — don't copy data files from prior version
- New versions of BOTH Plan.md AND Plan_Tasks.md document the revision rationale and what changed
- Version suffix applies consistently to both files (e.g., both get `_a` suffix)

**Skill element update:** When a Methodology Change revision changes the statistical approach (e.g., OLS to fixed effects, or adding spatial analysis), update the `<skill>` element in the relevant Plan_Tasks.md task blocks to reflect the new modeling library. Consult the `data-scientist` skill's routing tree or full-pipeline-mode.md's "Modeling library selection" section for the canonical routing. The routing is language-dependent: Python uses `statsmodels`/`pyfixest`/`linearmodels`/`svy`/`scikit-learn`/`geopandas`; R uses `r-stats`/`fixest`/`plm`/`survey-r`/`tidymodels`/`sf-terra`.

## Re-run Guidance

| Situation | Stage(s) to Re-run | Mode |
|-----------|-------------------|------|
| Wrong endpoints identified | Stage 2 | Refresh |
| Missing data source | Stage 2, 3 | Additive |
| Caveats misunderstood | Stage 3 | Refresh (affected source) |
| Query returned wrong data | Stage 5 | Refresh |
| Transformation logic wrong | Stage 7 | Refresh |
| Statistical method change | Stage 8 | Refresh |
| Report error | Stage 11 | Refresh |

**Refresh Mode:** Replace prior stage output with new findings.
**Additive Mode:** Supplement prior output with additional findings.

The canonical re-run decision trees live in `agent_reference/ERROR_RECOVERY.md`. The table above is a quick reference for revision-specific scenarios.

For stages that need re-execution, load `{SKILL_REFS}/full-pipeline-mode.md` and follow the relevant stage's Composite Execution Pattern. All QA requirements from the full pipeline apply to re-executed stages.

**Wave barrier discipline (async dispatch).** Because re-execution reuses the full pipeline's wave-based dispatch, the same barrier applies: subagents run in the background by default and return via completion notifications that may arrive one at a time. When re-executing stages that dispatch multiple subagents in a wave, treat mid-wave notifications as status-only — do not run gates, update STATE.md conclusions, assemble the Revision Status Update, or present interim findings to the user until EVERY member of the wave has returned, and synthesize once over the complete wave (a failed or early-returning agent still counts as a completion). See the full statement in `full-pipeline-mode.md` § "Wave-Based Parallel Execution" and the master statement in `SKILL.md` § Subagent Coordination.

**Gate applicability:** Stage gates from `full-pipeline-mode.md` apply to all re-executed stages. Gates for stages that are NOT being re-executed are considered already satisfied from the prior version. PSUs are NOT required (replaced by Revision Status Update), but gates within re-executed stages are mandatory.

### Re-Entry File Loading

When re-executing pipeline stages for a revision, load these files based on the re-entry point:

| Re-Entry Stage | Load These Files | Key Sections |
|----------------|-----------------|--------------|
| Stage 2-3 (Discovery) | `WORKFLOW_PHASE1_DISCOVERY.md` | Stage 2/3 invocation templates, gate criteria |
| Stage 4-4.5 (Planning) | `WORKFLOW_PHASE2_PLANNING.md` | data-planner invocation, plan-checker validation |
| Stage 5-6 (Acquisition) | `WORKFLOW_PHASE3_ACQUISITION.md` | Fetch/clean invocation templates + QA pattern |
| Stage 7-8 (Analysis) | `WORKFLOW_PHASE4_ANALYSIS.md` | Transform/analysis templates + QA pattern |
| Stage 9-10 (Assembly) | `WORKFLOW_PHASE4_ANALYSIS.md` | Notebook assembly, QA aggregation |
| Stage 11-12 (Synthesis) | `WORKFLOW_PHASE5_SYNTHESIS.md` | Report generation, final review |
| Any stage | `full-pipeline-mode.md` | QA enforcement protocol, invocation templates, context checklists |

**Progressive loading:** Only load the phase file for the re-entry point and any downstream phases. Do not load all phase files at once.

### Revision and Extension Session Management

**STATE.md:** Update the existing project's STATE.md with the revision context. Do not create a new STATE.md. Add a "Revision" section noting the revision type, affected stages, and re-entry point.

**Pre-execution STATE.md synchronization (mandatory, before any re-execution dispatch).** Immediately after the revised Plan.md + Plan_Tasks.md versions are written at "Create New Version" — and BEFORE dispatching any re-execution subagent — resynchronize STATE.md to the revised Plan_Tasks.md: rebuild the Transformation Progress table from the revised Task Index (reset rows for affected/regenerated tasks to pending; carry over completed rows for unaffected tasks ONLY when the task still exists with an identical script path), and update the Plan.md / Plan_Tasks.md paths, Current Stage, and Next Actions. Then validate: Transformation Progress row count == the revised Plan_Tasks.md `total_tasks`; every script path appears in both the table and the revised Task Index; no STATE.md content references a superseded plan-version filename. If any check fails, STOP — fix STATE.md and re-validate before dispatching. This mirrors the Gate G4.5 plan-revision synchronization in `full-pipeline-mode.md`. It is distinct from and complements the *post-execution* status update at Worked Example Step 8, which records executed script versions' QA status after re-execution completes. The orchestrator owns this synchronization; subagents never write STATE.md.

**LEARNINGS.md:** Append revision-specific learnings to the existing LEARNINGS.md. Revision sessions often produce the richest learnings about data quality and methodology edge cases.

**Phase Status Updates (PSUs):** PSUs are NOT required for revision re-execution. Instead, present a single **Revision Status Update** to the user after all re-executed stages complete, summarizing what changed and verification results.

The Revision Status Update is this mode's instance of DAAF's Turn-End Briefing standard — the comprehensive catch-up presented once re-execution finishes. Between that and any interim returns (an error pause, a question answered mid-revision), the general standard still governs: close each substantive turn with a briefing of what happened since the user's last message, taken altogether. See the master statement in `SKILL.md` § User-Facing Communication Standards > "Turn-End Briefing."

### Revision-Specific Subagent Context

When dispatching subagents for re-executed stages during a revision, include this additional context beyond the standard invocation template:

1. **Revision context:** What changed and why (from the revision classification)
2. **Prior version reference:** Path to the prior version's script/output for comparison
3. **Preserved context:** Which upstream data files are being reused vs. regenerated
4. **Scope boundary:** Explicitly state what should change vs. what must remain identical
5. **Original execution context from STATE.md:**
   - QA findings relevant to the affected stages (from QA Findings Summary)
   - Runtime risks that may affect revised stages (from Runtime Risks)
   - Prior transformation outcomes for affected scripts (from Transformation Progress)

Example addition to subagent prompt:
```
## REVISION CONTEXT
**Revision Type:** [Bug Fix | Scope Change | Methodology Change | Extension | Correction]
**What Changed:** [description of the change]
**Prior Version:** [path to prior script version]
**Reusing:** [list of upstream files NOT being regenerated]
**Regenerating:** [list of files being regenerated by this and downstream stages]
```

## Output Format

### Revision Status Update (presented to user after all re-executed stages complete)

```markdown
**Revision Complete: [Project Title] ([prior version] → [new version])**

**Revision Type:** [Bug Fix | Scope Change | Methodology Change | Extension | Correction]
**What Changed:** [1-2 sentence summary]

**Re-executed Stages:**
- [Stage N]: [what was done] — [QA status]
- [Stage M]: [what was done] — [QA status]

**Verification:** Final Review [PASSED | PASSED with notes]
**New Version Files:** [list key new-version artifacts]
```

### Deliverables

All deliverables are new-version copies; originals remain untouched:
- Plan.md (revised, documenting change rationale)
- Plan_Tasks.md (revised, with updated task specs)
- Re-executed scripts (new versions in `scripts/`, `.py` for Python or `.R` for R)
- Updated data files (regenerated, not copied)
- Notebook (reassembled with final script versions — marimo `.py` for Python, Quarto `.qmd` for R)
- Report (regenerated to reflect changes)
- Session logs collected into `logs/` (run `collect_session_logs.sh` before report generation)

**Session Log Collection:** Before Stage 11 (Report), the orchestrator runs:
```
bash {BASE_DIR}/scripts/collect_session_logs.sh {PROJECT_DIR}
```
This collects transcripts from both the original analysis sessions and the revision session(s), since both reference the same project folder basename.

### AI Use Disclosure in Revisions

When the report is regenerated (Stage 11), the AI Use Disclosure section should **inherit the original disclosure and append a revision note.** The report-writer carries forward the original analysis's `[AUTO]` metadata and adds:

> **Revision conducted on [date]:** AI assistance was used to [describe revision scope]. The same QA review process was applied to all re-executed code. DAAF version: [commit hash].

If the original report predates the AI Use Disclosure section (i.e., was created before this feature), the report-writer should generate a full disclosure section for the revised version. See `agent_reference/AI_DISCLOSURE_REFERENCE.md` for the Revision and Extension mode template.

## Subagent Invocation

Revision and Extension mode reuses the standard invocation templates from the relevant `WORKFLOW_PHASE*.md` file for each re-executed stage. Construct subagent prompts using:

1. **Base:** The stage-specific invocation template from the appropriate phase file (see Re-Entry File Loading table above)
2. **Augment:** Add the REVISION CONTEXT block (see Revision-Specific Subagent Context above) to every subagent prompt
3. **QA:** Invoke code-reviewer after each re-executed script, following the same QA pattern from `full-pipeline-mode.md`

No revision-specific invocation templates are needed — the standard templates plus REVISION CONTEXT block provide complete dispatch guidance.

**Cross-language annotation preference:** If the original analysis used cross-language annotations (check STATE.md or SESSION_NOTES.md), propagate the same translation directive to all re-execution agent prompts. Select the directive based on execution language and background per orchestrator SKILL.md § User Language Preference Propagation (4-way table: `r-python-translation`, `stata-python-translation`, `python-r-translation`, or `stata-r-translation`). This ensures revised scripts maintain the same translation annotation pattern as the originals.

## Worked Example: Bug Fix Revision

**User request:** "The join in Stage 7 used the wrong key — it should join on `ncessch` not `school_id`."

**Step 1: Classify.** This is a **Bug Fix** — a code error in a join operation.

**Step 2: Determine affected stages.** Stage 7 (where the bad join is) + Stage 8, 9, 10, 11, 12 (all downstream).

**Step 3: Create new version.** If the prior version was `2026-01-24_School_Poverty_Analysis`, create `2026-01-24a_School_Poverty_Analysis`. Create new versions of BOTH Plan.md and Plan_Tasks.md documenting the fix rationale.

**Step 4: Determine what to reuse.** Stage 5 (fetch) and Stage 6 (clean) data files are unaffected — reuse them. Only re-execute Stage 7+ scripts.

**Step 5: Load references.**
- `revision-and-extension-mode.md` (already loaded)
- `full-pipeline-mode.md` (for composite execution pattern and QA enforcement)
- `WORKFLOW_PHASE4_ANALYSIS.md` (for Stage 7-8 invocation templates)
- `WORKFLOW_PHASE5_SYNTHESIS.md` (for Stage 11-12 templates)

**Step 6: Dispatch subagents.** For each re-executed stage, use the standard invocation template from the relevant WORKFLOW_PHASE file, adding the Revision Context block:

```
## REVISION CONTEXT
**Revision Type:** Bug Fix
**What Changed:** Join key corrected from school_id to ncessch
**Prior Version:** research/.../scripts/stage7_transform/01_join-data.py (or .R)
**Reusing:** data/raw/*.parquet, data/processed/*_clean.parquet (Stage 5-6 outputs)
**Regenerating:** All Stage 7+ outputs
```

**Step 7: QA loop.** Code-reviewer validates each re-executed script. Gates G7-G12 must pass.

**Step 8: Update STATE.md (post-execution status update).** Add entry to Revision History table. Update Transformation Progress with the executed script versions' QA status and row counts. This is the *post-execution* status update — it complements, and does NOT replace, the *pre-execution* STATE.md synchronization performed at "Create New Version" (see Revision and Extension Session Management § STATE.md), which rebuilt Transformation Progress from the revised Task Index before any re-execution began.

**Step 9: Present Revision Status Update** to user with summary of changes made and verification results.

## Boundaries

These boundaries supplement the universal boundaries in `CLAUDE.md` and `agent_reference/BOUNDARIES.md`.

**Always Do:**
- Search for and locate existing project first
- Read complete Plan.md, Plan_Tasks.md, and notebook (marimo `.py` or Quarto `.qmd`) before proposing changes
- Read STATE.md before planning any revision — original execution context is critical for informed revision decisions
- Create fresh copies of both Plan.md and Plan_Tasks.md to record new changes
- Classify revision type and confirm with user
- Create new version files (never modify existing)
- Regenerate data fresh (don't copy from prior version)
- Complete full Stage 12 Final Review even for minor fixes
- Document revision in Version Information section

**Ask First Before:**
- Converting a minor fix to scope expansion
- Discarding significant portions of prior work
- Making changes beyond revision request scope
- Using a non-latest version as base

**Never Do:**
- Overwrite or modify prior version files
- Skip revision type classification
- Copy raw data files from prior version (regenerate fresh)
- Proceed without reading existing Plan.md, Plan_Tasks.md, and STATE.md

**Version Suffix Convention:** See `CLAUDE.md` > "Version Control Protocol" for the canonical convention (e.g., original → `a` → `b` → `c`).

## Arriving from Reproducibility Verification Mode

When a user arrives at Revision and Extension mode from Reproducibility Verification (RV) mode, it is because the Reproduction Report identified divergences or methodological concerns that the user wants to fix in the original analysis. The Reproduction Report's Deviation Log and Methodological Concerns sections serve as the specification for what needs to change — they document exactly where the original analysis diverged from expected behavior and why.

The orchestrator should reference specific deviations from the Reproduction Report when constructing the revision scope and classifying the revision type. For example, a deviation flagged as "data source returned different values" may indicate a Scope Change or Bug Fix depending on the cause, while a methodological concern may indicate a Methodology Change. The Reproduction Report provides the evidence base that informs these classifications.

Note that the **original project** (not the reproduction project) is the target of revision. The reproduction project folder is a read-only verification artifact. When setting up the revision, locate the original project's Plan.md, Plan_Tasks.md, and STATE.md as described in the standard workflow above, and use the Reproduction Report as supplementary context for understanding what went wrong and what needs to change.

## Escalation Triggers

| Condition | Escalate To | Action |
|-----------|-------------|--------|
| Revision scope expands to require new data sources or fundamentally different methodology | Full Pipeline | Propose starting a new Full Pipeline analysis, referencing the existing project for context |
| Revision requires a data source with no existing skill | Data Onboarding | Propose onboarding the data source first, then returning to the revision |

When escalation is appropriate, propose explicitly and await user confirmation before proceeding.
