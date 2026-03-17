# Revision Mode

Revision mode is for modifying existing analyses — fixing bugs, updating scope, changing methodology, or extending prior work. It always operates on a **new version** of existing artifacts, never modifying originals.

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

The canonical re-run decision trees live in `agent_reference/06_ERROR_RECOVERY.md`. The table above is a quick reference for revision-specific scenarios.

For stages that need re-execution, load `{SKILL_REFS}/full-pipeline.md` and follow the relevant stage's Composite Execution Pattern. All QA requirements from the full pipeline apply to re-executed stages.

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

## Boundaries

These boundaries supplement the universal boundaries in `CLAUDE.md` and `agent_reference/04_BOUNDARIES.md`.

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
