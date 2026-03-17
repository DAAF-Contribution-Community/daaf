# Revision Mode

Revision mode is for modifying existing analyses — fixing bugs, updating scope, changing methodology, or extending prior work. It always operates on a **new version** of existing artifacts, never modifying originals.

## User Orientation

After mode confirmation, briefly orient the user. Key points:

- Locates existing analysis and classifies the change type
- Creates a new version — original is never modified
- Only affected steps re-run, with same quality checks as original

**When to skip:** User has indicated familiarity, or this is a follow-up in the same session.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Revision Workflow

```
Stage 1: Classify as Revision Mode → Confirm with user
    ↓
Locate Existing Project
    ├─ Search research/ for the referenced analysis folder
    ├─ Read the COMPLETE existing Plan document
    └─ Read the existing notebook to understand current state
    ↓
Classify Revision Type → Confirm with user
    ↓
Create New Version
    ├─ Create new version of Plan (e.g., 2026-01-24a → 2026-01-24b)
    ├─ Document revision request and type in new Plan
    └─ Execute required stages (load full-pipeline.md if needed)
    ↓
Final Review
    └─ Complete full Final Review even for minor fixes
```

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
- The new Plan documents the revision rationale and what changed

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

For stages that need re-execution, load `{SKILL_REFS}/full-pipeline.md` and follow the relevant stage's Composite Execution Pattern. All QA requirements from the full pipeline apply to re-executed stages.

**Gate applicability:** Stage gates from `full-pipeline.md` apply to all re-executed stages. Gates for stages that are NOT being re-executed are considered already satisfied from the prior version. PSUs are NOT required (replaced by Revision Status Update), but gates within re-executed stages are mandatory.

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
| Any stage | `full-pipeline.md` | QA enforcement protocol, invocation templates, context checklists |

**Progressive loading:** Only load the phase file for the re-entry point and any downstream phases. Do not load all phase files at once.

### Revision Session Management

**STATE.md:** Update the existing project's STATE.md with the revision context. Do not create a new STATE.md. Add a "Revision" section noting the revision type, affected stages, and re-entry point.

**LEARNINGS.md:** Append revision-specific learnings to the existing LEARNINGS.md. Revision sessions often produce the richest learnings about data quality and methodology edge cases.

**Phase Status Updates (PSUs):** PSUs are NOT required for revision re-execution. Instead, present a single **Revision Status Update** to the user after all re-executed stages complete, summarizing what changed and verification results.

### Revision-Specific Subagent Context

When dispatching subagents for re-executed stages during a revision, include this additional context beyond the standard invocation template:

1. **Revision context:** What changed and why (from the revision classification)
2. **Prior version reference:** Path to the prior version's script/output for comparison
3. **Preserved context:** Which upstream data files are being reused vs. regenerated
4. **Scope boundary:** Explicitly state what should change vs. what must remain identical

Example addition to subagent prompt:
```
## REVISION CONTEXT
**Revision Type:** [Bug Fix | Scope Change | Methodology Change | Extension | Correction]
**What Changed:** [description of the change]
**Prior Version:** [path to prior script version]
**Reusing:** [list of upstream files NOT being regenerated]
**Regenerating:** [list of files being regenerated by this and downstream stages]
```

## Worked Example: Bug Fix Revision

**User request:** "The join in Stage 7 used the wrong key — it should join on `ncessch` not `school_id`."

**Step 1: Classify.** This is a **Bug Fix** — a code error in a join operation.

**Step 2: Determine affected stages.** Stage 7 (where the bad join is) + Stage 8, 9, 10, 11, 12 (all downstream).

**Step 3: Create new version.** If the prior version was `2026-01-24_School_Poverty_Analysis`, create `2026-01-24a_School_Poverty_Analysis`. Create new Plan version documenting the fix rationale.

**Step 4: Determine what to reuse.** Stage 5 (fetch) and Stage 6 (clean) data files are unaffected — reuse them. Only re-execute Stage 7+ scripts.

**Step 5: Load references.**
- `revision-mode.md` (already loaded)
- `full-pipeline.md` (for composite execution pattern and QA enforcement)
- `WORKFLOW_PHASE4_ANALYSIS.md` (for Stage 7-8 invocation templates)
- `WORKFLOW_PHASE5_SYNTHESIS.md` (for Stage 11-12 templates)

**Step 6: Dispatch subagents.** For each re-executed stage, use the standard invocation template from the relevant WORKFLOW_PHASE file, adding the Revision Context block:

```
## REVISION CONTEXT
**Revision Type:** Bug Fix
**What Changed:** Join key corrected from school_id to ncessch
**Prior Version:** research/.../scripts/stage7_transform/01_join-data.py
**Reusing:** data/raw/*.parquet, data/processed/*_clean.parquet (Stage 5-6 outputs)
**Regenerating:** All Stage 7+ outputs
```

**Step 7: QA loop.** Code-reviewer validates each re-executed script. Gates G7-G12 must pass.

**Step 8: Update STATE.md.** Add entry to Revision History table. Update Transformation Progress with new script paths and QA status.

**Step 9: Present Revision Status Update** to user with summary of changes made and verification results.

## Boundaries

These boundaries supplement the universal boundaries in `CLAUDE.md` and `agent_reference/BOUNDARIES.md`.

**Always Do:**
- Search for and locate existing project first
- Read complete Plan and notebook before proposing changes
- Create fresh copy of Plan to record new changes
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
- Proceed without reading existing Plan

**Version Suffix Convention:** See `CLAUDE.md` > "Version Control Protocol" for the canonical convention (e.g., original → `a` → `b` → `c`).
