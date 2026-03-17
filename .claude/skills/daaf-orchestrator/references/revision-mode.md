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
Final Review (Protocol 5)
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

For stages that need re-execution, load `{SKILL_REFS}/full-pipeline.md` and follow the relevant stage's Composite Execution Pattern. All QA requirements from the full pipeline apply to re-executed stages.

## Boundaries

These boundaries supplement the universal boundaries in `CLAUDE.md` and `agent_reference/04_BOUNDARIES.md`.

**Always Do:**
- Search for and locate existing project first
- Read complete Plan and notebook before proposing changes
- Create fresh copy of Plan to record new changes
- Classify revision type and confirm with user
- Create new version files (never modify existing)
- Regenerate data fresh (don't copy from prior version)
- Complete full Protocol 5 even for minor fixes
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
