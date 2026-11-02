# Revision and Extension Mode

Revision and Extension mode is for modifying or extending existing analyses — fixing bugs, updating scope, changing methodology, or extending prior work. It always operates on a **new version** of existing artifacts, never modifying originals.

## User Orientation

The mode confirmation already gave the user this preview, so do not repeat it after confirmation. Present these points only when the user signals they are new to DAAF or asks for more detail.

- Locates existing analysis and classifies the change type
- Creates a new version — original is never modified
- Only affected steps re-run, with same quality checks as original

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Scope Check

**Tier:** Hard (blocking). **Where:** the **Revision Scope Check** (§ Revision Type Classification > Revision Scope Check), at the existing step that confirms the revision type, before any new version is created. **Read first:** the existing Plan.md, Plan_Tasks.md, notebook and STATE.md (§ Revision and Extension Workflow), plus anything the user cited, such as a Reproduction Report, reviewer comments or a memo, per `SKILL.md` § Scope Check > Read First (a cited PDF, or a large set of cited files, goes to one `search-agent` digest dispatch). **No staging here:** the project folder already exists, so fetches, PDF ingests and any digest made for this Scope Check go straight into it, per `SKILL.md` § Scope Check > Read First: fetches to `{PROJECT_DIR}/web_fetches/`, and a PDF's digest dispatch ingests into `{PROJECT_DIR}/papers/` and writes its record to `{PROJECT_DIR}/output/preliminary_notes/{date}_{slug}_materials-digest.md`. These writes are additive (new files and new manifest rows); nothing the original analysis delivered is touched, and the new version is created only after the user confirms (§ Revision Scope Check). **Rule and standard block:** `SKILL.md` § Scope Check. **On resume:** when STATE.md's Revision (current) section records `Scope Check status: Confirmed YYYY-MM-DD`, do not re-present the Scope Check; re-present it if the status reads "Awaiting confirmation" or the section is absent.

---

## Revision and Extension Workflow

```
Stage 1: Classify as Revision and Extension Mode → Confirm with user
    ↓
Locate Existing Project and Read
    ├─ Search research/ for the referenced analysis folder
    ├─ Read the COMPLETE existing Plan.md and Plan_Tasks.md
    ├─ Read the existing notebook (marimo `.py` or Quarto `.qmd`) to understand current state
    ├─ Read STATE.md and extract original execution context (see below)
    └─ Read anything else the user cited (e.g., a Reproduction Report, reviewer comments)
    ↓
Classify Revision Type → Revision Scope Check (user confirms)
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

Classify the revision type, then confirm it with the user at the Revision Scope Check (template below) before proceeding:

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

### Revision Scope Check

Present after reading the existing project and anything the user cited, and before creating the new version. It is this mode's Scope Check (`SKILL.md` § Scope Check): the user agreed at mode confirmation to *revise this analysis*; here they approve *what the revision will touch*, now that the plan, the execution record and their cited documents have been read. Without it, the revision type and re-run boundary would be settled silently.

```
**Scope Check: Revision of [Project Title]**

**What I read:** [the existing Plan.md, Plan_Tasks.md, notebook and STATE.md, plus anything you cited (e.g., the Reproduction Report, reviewer comments) — one line each on what in it shapes the revision]
**Proposed scope:**
- Revision type: [Bug Fix | Scope Change | Methodology Change | Extension | Correction] — [why, in one line]
- Steps to re-run: [the steps in plain words, e.g., "the join step and everything after it (analysis, notebook, report)"]
- Reused, not regenerated: [upstream outputs kept, e.g., "the downloaded and cleaned data files"]
- Regenerated: [outputs this revision rebuilds]
- New version: [prior version name] → [new version name]
**What changed from your original request:** [differences the materials introduced — e.g., "the Reproduction Report shows the same join also feeds Table 3, so the analysis step re-runs too" — or "Nothing — your request and the materials agree"]
**Decisions for you:**
- [each independent decision on its own line, with its default — e.g., "Base version: the latest, [name] (default), or an earlier one"]

**Shall I create the new version and re-run these steps?**
```

The template is user-facing, so it names steps in plain words, never stage numbers (`SKILL.md` § Plain-Language Rule); the stage numbers go into STATE.md.

Record the scope in STATE.md's Revision (current) section (§ Revision and Extension Session Management): `Scope Check status: Awaiting confirmation` when you present the check, `Confirmed YYYY-MM-DD` when the user agrees, before creating the new version. Nothing moves on confirmation: what was read for the check is already in the project folder (§ Scope Check, "No staging here"). List it, with its paths in the project, in the section's "Materials read" field.

## Version Control Protocol

Version suffixes follow the convention defined in `CLAUDE.md` > "Versioning & Naming" (e.g., original → `a` → `b` → `c`; full tables in `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` § Project File Naming Conventions).

**Rules:**
- Always create new version files — never modify existing versions
- All versions remain in the same project folder
- Regenerate data fresh from scripts — don't copy data files from prior version
- New versions of BOTH Plan.md AND Plan_Tasks.md document the revision rationale and what changed
- Both files get the same new version prefix (e.g., `2026-01-24a_School_Poverty_Analysis_Plan.md` and `2026-01-24a_School_Poverty_Analysis_Plan_Tasks.md`)
- Each re-executed script, changed or not, runs as a new version file made with `bash {BASE_DIR}/scripts/create_script_revision.sh <latest version> <next version>`, taking the next free letter suffix (`01_join-data.py` → `01_join-data_a.py`, or `_a` → `_b`); `run_with_capture.sh` refuses a script that already carries an execution log. The revised Plan_Tasks.md Task Index names these new script paths

**Skill element update:** When a Methodology Change revision changes the statistical approach (e.g., OLS to fixed effects, or adding spatial analysis), update the `<skill>` element in the relevant Plan_Tasks.md task blocks to reflect the new modeling library. Consult the `data-scientist` skill's routing tree or full-pipeline-mode.md's "Modeling library selection" section for the canonical routing. The routing is language-dependent: Python uses `statsmodels`/`pyfixest`/`linearmodels`/`svy`/`scikit-learn`/`geopandas`; R uses `r-stats`/`fixest`/`plm`/`survey-r`/`tidymodels`/`sf-terra`.

## Re-run Guidance

| Situation | Stage(s) to Re-run | Mode |
|-----------|-------------------|------|
| Wrong endpoints identified | Stage 2 | Refresh |
| Missing data source | Stage 2, 3 | Additive |
| Caveats misunderstood | Stage 3 | Refresh (affected source) |
| Query returned wrong data | Stage 5 | Refresh |
| Transformation logic wrong | Stage 7 | Refresh |
| Visualization incorrect | Stage 8 | Refresh |
| Statistical method change | Stage 8 | Refresh |
| Report error | Stage 11 | Refresh |

**Refresh Mode:** Replace prior stage output with new findings.
**Additive Mode:** Supplement prior output with additional findings.

The table above adds the revision cases (statistical method change, report error) to the canonical table in `agent_reference/ERROR_RECOVERY.md` § Re-run Procedures.

For stages that need re-execution, load `{SKILL_REFS}/full-pipeline-mode.md` and follow the relevant stage's Composite Execution Pattern. All QA requirements from the full pipeline apply to re-executed stages.

**Wave barrier discipline (async dispatch).** Because re-execution reuses the full pipeline's wave-based dispatch, the same barrier applies. See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive; the barrier holds however they arrive. When re-executing stages that dispatch multiple subagents in a wave, treat mid-wave notifications as status-only — do not run gates, update STATE.md conclusions, assemble the Revision Status Update, or present interim findings to the user until EVERY member of the wave has returned, and synthesize once over the complete wave (a failed or early-returning agent still counts as a completion). See the full statement in `full-pipeline-mode.md` § "Wave-Based Parallel Execution" and the master statement in `SKILL.md` § Subagent Coordination.

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

**STATE.md:** Update the existing project's STATE.md with the revision context. Do not create a new STATE.md. Add the `## Revision (current)` section from `agent_reference/STATE_TEMPLATE.md`, noting the revision type, affected stages, re-entry point, and `Scope Check status: Awaiting confirmation | Confirmed YYYY-MM-DD` (§ Revision Scope Check). When the revision completes, it gets a row in Revision History (Worked Example, Step 8). A project revised again already has the section: at the new revision's Scope Check, summarize its content into the previous revision's Revision History row (add the row if it is missing), then reset the section for the new revision, starting from `Scope Check status: Awaiting confirmation`, so recovery cannot mistake the earlier confirmation for this one.

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

**What was re-run:**
- [the step in plain words, e.g., "the join step"]: [what was done] — [quality review result in plain words]
- [the next step re-run]: [what was done] — [quality review result in plain words]

**Final check:** [passed | passed with notes]
**New Version Files:** [list key new-version artifacts]
```

Like the Revision Scope Check, this update is user-facing: it names steps in plain words, and the stage numbers go into STATE.md.

### Deliverables

All deliverables are new-version copies; originals remain untouched:
- Plan.md (revised, documenting change rationale)
- Plan_Tasks.md (revised, with updated task specs)
- Re-executed scripts (new version files in `scripts/`, `.py` for Python or `.R` for R, each made with `create_script_revision.sh` per § Version Control Protocol)
- Updated data files (regenerated, not copied)
- Notebook (reassembled with final script versions — marimo `.py` for Python, Quarto `.qmd` for R)
- Report (regenerated to reflect changes)
- Session logs collected into `logs/` (run `collect_session_logs.sh` before report generation)

**Session Log Collection:** Before Stage 11 (Report), the orchestrator runs the Scratch Graduation Check (`agent_reference/SCRIPT_EXECUTION_REFERENCE.md` § Scratch Graduation Check; the revised plan, notes and report never cite a file in `scripts/scratch/`), then:
```
bash {BASE_DIR}/scripts/collect_session_logs.sh {PROJECT_DIR}
```
This collects transcripts from both the original analysis sessions and the revision session(s), since both reference the same project folder basename.

### AI Use Disclosure in Revisions

When the report is regenerated (Stage 11), the AI Use Disclosure section should **inherit the original disclosure and append a revision note.** The report-writer carries forward the original analysis's `[AUTO]` metadata and adds:

> **Revision conducted on [date]:** AI assistance was used to [describe revision scope]. The same QA review process was applied to all re-executed code. DAAF version: [commit hash].

See `agent_reference/AI_DISCLOSURE_REFERENCE.md` for the Revision and Extension mode template.

> **Recognizing older forms.** A report with no AI Use Disclosure section gets a full disclosure in the revised version (`agent_reference/AI_DISCLOSURE_REFERENCE.md`), not an appended revision note.

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

**Step 3: Create new version.** If the prior version was `2026-01-24_School_Poverty_Analysis`, name the new version files with the prefix `2026-01-24a_School_Poverty_Analysis` (e.g., `2026-01-24a_School_Poverty_Analysis_Plan.md`) in the same project folder. Create new versions of BOTH Plan.md and Plan_Tasks.md documenting the fix rationale.

**Step 4: Determine what to reuse.** Stage 5 (fetch) and Stage 6 (clean) data files are unaffected — reuse them. Only re-execute Stage 7+ scripts, each as a new version file (e.g., `01_join-data_a.py`; § Version Control Protocol).

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
- Read anything the user cited (Reproduction Report, reviewer comments, memos) before proposing the revision scope
- Create fresh copies of both Plan.md and Plan_Tasks.md to record new changes
- Classify revision type and confirm the scope with the user at the Revision Scope Check
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

**Version Suffix Convention:** See `CLAUDE.md` > "Versioning & Naming" for the canonical convention (e.g., original → `a` → `b` → `c`).

## Arriving from Reproducibility Verification Mode

When a user arrives at Revision and Extension mode from Reproducibility Verification (RV) mode, it is because the Reproduction Report identified divergences or methodological concerns that the user wants to fix in the original analysis. The Reproduction Report's Deviation Log and Methodological Concerns sections serve as the specification for what needs to change — they document exactly where the original analysis diverged from expected behavior and why.

Read the Reproduction Report before the Revision Scope Check: it belongs on the "What I read" line, and its deviations usually drive "What changed from your original request". The orchestrator should reference specific deviations from the Reproduction Report when constructing the revision scope and classifying the revision type. For example, a deviation flagged as "data source returned different values" may indicate a Scope Change or Bug Fix depending on the cause, while a methodological concern may indicate a Methodology Change. The Reproduction Report provides the evidence base that informs these classifications.

Note that the **original project** (not the reproduction project) is the target of revision. The reproduction project folder is a read-only verification artifact. When setting up the revision, locate the original project's Plan.md, Plan_Tasks.md, and STATE.md as described in the standard workflow above, and use the Reproduction Report as supplementary context for understanding what went wrong and what needs to change.

## Escalation Triggers

| Condition | Escalate To | Action |
|-----------|-------------|--------|
| Revision scope expands to require new data sources or fundamentally different methodology | Full Pipeline | Propose starting a new Full Pipeline analysis, referencing the existing project for context |
| Revision requires a data source with no existing skill | Data Onboarding | Propose onboarding the data source first, then returning to the revision |

When escalation is appropriate, propose explicitly and await user confirmation before proceeding.
