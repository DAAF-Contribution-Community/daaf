# Plan Template (Data Ingest Mode)

This template defines the lightweight Plan document for Data Ingest Mode profiling projects. It is a streamlined adaptation of the Full Pipeline Plan template, focused on data profiling scope rather than research methodology.

---

## Template

```markdown
---
# Plan Frontmatter
# Machine-readable metadata for orchestration

title: "[Source Name] Data Ingest"
date: "YYYY-MM-DD"
version: ""                           # Empty for original, "a", "b", etc. for revisions
status: "planning"                    # planning | in_progress | complete
mode: "data-ingest"

# Goal-Backward Verification for Data Ingest
must_haves:
  profiling_outcomes:
    - "Data structure and schema are fully characterized"
    - "All columns are profiled with types, distributions, and quality metrics"
    - "Primary/composite keys are identified and validated"
    - "Coded missing values and anomalies are cataloged"
    - "Preliminary interpretations are documented with [PRELIMINARY] markers"

  artifacts:
    - path: ".claude/skills/[skill-name]/SKILL.md"
      provides: "Standalone data source skill"
      contains: ["## What is", "## Quick Reference", "## Data Access", "## Common Pitfalls"]

    - path: "research/YYYY-MM-DD_Ingest_[SourceName]/output/skill_draft/SKILL.md"
      provides: "Draft skill (audit artifact)"

    - path: "research/YYYY-MM-DD_Ingest_[SourceName]/scripts/profile_interpretation/12_profile-synthesis.py"
      provides: "Profiling synthesis with execution log"

  key_links:
    - from: ".claude/skills/[skill-name]/SKILL.md"
      to: "research/YYYY-MM-DD_Ingest_[SourceName]/scripts/"
      via: "Profiling scripts generated the knowledge in the skill"
---

# [Source Name] Data Ingest

**Key Principles:**

1. **Data Primacy:** The data file is the ultimate source of truth. Documentation claims are verified against data, not the other way around.
2. **Preliminary Interpretation Discipline:** All semantic interpretations are marked [PRELIMINARY] until user-confirmed at PSU-DI2.
3. **File paths must be explicit** (no placeholders in the final plan).
4. **Verification must be executable** (CPP1-CPP4 + CPP-SKILL inline checks).

---

## Companion Files

| File | Purpose |
|------|---------|
| `YYYY-MM-DD_Ingest_[SourceName]_Plan_Tasks.md` | Executable task sequence for all 12 profiling scripts |
| `STATE.md` | Operational state tracking (profiling progress, interpretation tracking, QA findings) |
| `LEARNINGS.md` | Session learnings — data quality insights, format gotchas, process observations |

> **Immutability Rule:** This Plan and companion Plan_Tasks.md are frozen after Stage DI-2 (Project Setup). Conditional script decisions may be updated after Phase A findings (documented in STATE.md Key Decisions).

---

## Source Identification

| Field | Value |
|-------|-------|
| **Source Name** | [e.g., "County Presidential Election Returns 2000-2024"] |
| **Source Provider** | [e.g., "MIT Election Data and Science Lab (MEDSL)"] |
| **Origin URL** | [URL where data was obtained] |
| **Data Pull Date** | [YYYY-MM-DD] |
| **File Format** | [CSV/TSV/Parquet/Excel/JSON] |
| **File Size** | [e.g., "8.4 MB"] |
| **File Count** | [N files — list if multiple] |
| **Documentation Files** | [List or "None provided"] |
| **Domain Context** | [Brief description: what domain, what level, what scope] |

---

## Profiling Scope

| Field | Value |
|-------|-------|
| **Target Skill Name** | [e.g., "election-data-source-countypres"] |
| **Intended Use** | [How will this data be used in future analyses?] |
| **Priority Columns** | [Columns user flagged for deep investigation, or "None specified"] |
| **Known Context** | [Any prior knowledge about this data the user shared] |

---

## Original Request & Clarifications

### Original Request

> [Paste the verbatim user request here]

### Clarifications Received

1. **[Topic]:** [User's response]
2. **[Topic]:** [User's response]

---

## Conditional Execution Plan

*Determined after Phase A (scripts 01-03) structural profiling reveals data characteristics.*

### Always-Execute Scripts (8 core scripts)

| # | Phase | Script | Purpose |
|---|-------|--------|---------|
| 01 | A | load-and-format | Format detection, encoding validation, canonical load pattern |
| 02 | A | structural-profile | Row/column count, memory, types, schema |
| 03 | A | column-profile | Per-column stats, distributions, pattern detection |
| 04 | B | distribution-analysis | Distribution fitting, outlier identification, skewness |
| 07 | C | key-integrity | Key uniqueness, composite keys, functional dependencies |
| 09 | C | quality-anomaly | Coded missing values, duplicates, consistency rules, anomaly catalog |
| 10 | D | semantic-interpretation | Name patterns, value patterns, data dictionary draft |
| 12 | D | profile-synthesis | Aggregate all findings, skill authoring readiness |

### Conditional Scripts (4 scripts — execute based on Phase A findings)

| # | Phase | Script | Condition | Status |
|---|-------|--------|-----------|--------|
| 05 | B | temporal-coverage | Time/year/date column identified in Phase A | [EXECUTE/SKIP — decided after Phase A] |
| 06 | B | entity-coverage | Geographic or entity ID column identified | [EXECUTE/SKIP — decided after Phase A] |
| 08 | C | correlation-dependency | >= 3 numeric columns present | [EXECUTE/SKIP — decided after Phase A] |
| 11 | D | reconcile-docs | Documentation files provided | [EXECUTE/SKIP — known at intake] |

### Column Batching (if applicable)

**Total Columns:** [N]
**Batching Required:** [Yes: N batches of ~50 columns / No]

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| File format parsing issues (encoding, delimiters) | [L/M/H] | Medium | Script 01 validates format before profiling begins |
| Large file (>500MB) causes memory issues | [L/M/H] | High | Use sampling strategy; symlink instead of copy |
| No documentation available | [L/M/H] | Medium | Skip script 11; rely on deductive profiling (Mode 1) |
| Coded values use non-standard sentinels | [L/M/H] | Medium | Script 09 scans for common patterns (-1, -9, -99, -999, 999, 9999) |
| Dataset has >100 columns | [L/M/H] | Medium | Column batching at ~50 per profiling invocation |
| Multi-file source with complex relationships | [L/M/H] | High | Script 07 handles referential integrity; escalate if >5 files |

---

## Output Specification

### Skill Structure (target)

The profiling produces a SKILL.md following the canonical 12-section `DATA_SOURCE_SKILL_TEMPLATE.md`:

1. Frontmatter (YAML with provenance dates)
2. Title
3. Summary paragraph
4. Value Encodings Warnings (MANDATORY)
5. "What is [Source]?"
6. Reference File Structure
7. Decision Trees (minimum 2)
8. Quick Reference (Key Identifiers + Missing Data Codes)
9. Data Access (Dataset Paths + Example Fetch)
10. Common Pitfalls (minimum 3)
11. Related Data Sources
12. Topic Index (MUST be last)

**Target size:** 200-350 lines (hard limit: 500)

### Reference Files

| File | Purpose | Source Scripts |
|------|---------|---------------|
| `columns.md` | Full column definitions and types | 02, 03 |
| `coded-values.md` | All coded/sentinel value mappings | 03, 09 |
| `quality-notes.md` | Data quality observations and warnings | 09, 11 |
| `variable-definitions.md` | Semantic column interpretations | 10 |
| `interpretations.md` | User-confirmed interpretations from PSU-DI2 | 10 (confirmed at PSU-DI2) |

### Deliverables Checklist

| Deliverable | Location | Format |
|-------------|----------|--------|
| Profiling Plan | `research/[project]/` | `.md` |
| Profiling Plan Tasks | `research/[project]/` | `.md` |
| Profiling scripts (12) | `research/[project]/scripts/profile_*/` | `.py` |
| QA review scripts (4) | `research/[project]/scripts/cr/` | `.py` |
| Skill draft | `research/[project]/output/skill_draft/` | `.md` |
| Final skill | `.claude/skills/[skill-name]/` | `.md` + refs |
| Profile report | `research/[project]/output/` | `.md` |

---

## File Manifest

*Updated at delivery*

| File | Path | Description |
|------|------|-------------|
| Plan | `research/YYYY-MM-DD_Ingest_[SourceName]/YYYY-MM-DD_Ingest_[SourceName]_Plan.md` | This document |
| Plan Tasks | `research/YYYY-MM-DD_Ingest_[SourceName]/YYYY-MM-DD_Ingest_[SourceName]_Plan_Tasks.md` | Executable task sequence |
| **Learnings** | `research/YYYY-MM-DD_Ingest_[SourceName]/LEARNINGS.md` | Session learnings |
| Profiling Scripts | `research/YYYY-MM-DD_Ingest_[SourceName]/scripts/profile_*/` | All profiling scripts with execution logs |
| QA Scripts | `research/YYYY-MM-DD_Ingest_[SourceName]/scripts/cr/` | Phase-level QA review scripts |
| Skill Draft | `research/YYYY-MM-DD_Ingest_[SourceName]/output/skill_draft/SKILL.md` | Working draft (audit artifact) |
| Final Skill | `.claude/skills/[skill-name]/SKILL.md` | Standalone skill for future use |
| Reference Files | `.claude/skills/[skill-name]/references/` | Supporting reference documents |
| Profile Report | `research/YYYY-MM-DD_Ingest_[SourceName]/output/YYYY-MM-DD_[source]_profile_report.md` | Final profiling report |
```

---

## Template Usage Notes

### When This Template Is Used

The orchestrator creates this Plan at **Stage DI-2 (Project Setup)** using information collected at Stage DI-1 (Initial Intake). The Conditional Execution Plan section is updated after Phase A findings.
