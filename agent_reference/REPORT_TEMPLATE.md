# [Analysis Title]

**Date:** YYYY-MM-DD
**Version:** [Original | Revision suffix]

## Source Mapping Guide

> **For the report-writer agent:** This guide maps each report section below to its primary pipeline artifact source. When populating each section, consult the primary source first, then secondary sources for additional detail.

| Report Section | Primary Source | Secondary Sources |
|---|---|---|
| Executive Summary | Plan.md § Research Outcomes + Stage 7-8 execution logs | LEARNINGS.md |
| Research Question | Plan.md § Research Question (verbatim) | Plan.md § Context |
| Data & Methods: Data Sources | Plan.md § Data Sources table | Stage 5 execution logs |
| Data & Methods: Key Variables | Plan.md § Key Variables | — |
| Data & Methods: Methodology | Plan.md § Methodology Specification | Plan.md § Key Decisions |
| Data & Methods: Data Cleaning | Stage 6 execution logs | STATE.md checkpoints |
| Quality Assurance | STATE.md QA Findings Summary | Stage 10 QA execution logs |
| Key Findings | Stage 7-8 outputs + figures | Plan.md § Research Outcomes + Plan.md § Hypotheses (if any) |
| Summary Statistics | Analysis dataset metadata + Stage 7 EDA logs | Notebook data cells |
| Limitations | Plan.md § Risk Register (planning risks) + STATE.md Runtime Risks + STATE.md Blockers | LEARNINGS.md + source caveats |
| Data Sources & Citations | Stage 6 citation text (verbatim) | Plan.md § Data Sources |
| AI Use Disclosure | STATE.md (session metadata) + QA summary + `agent_reference/AI_DISCLOSURE_REFERENCE.md` | CLAUDE.md (model info), DAAF commit hash from orchestrator |
| Technical Notes | Project file paths | — |
| Appendix | Additional figures + extended methodology from Plan.md | — |

---

## Executive Summary

[4-5 sentences summarizing the key findings and their implications. Write for a busy stakeholder who may only read this section.]

---

## Research Question

[Clear statement of the question this analysis addresses]

**Context:** [Brief background on why this question matters]

---

## Data & Methods

### Data Sources

| Source | Description | Years | Records |
|--------|-------------|-------|---------|
| [Source name] | [What it contains] | [Years used] | [Approximate count] |

### Key Variables

| Variable | Description | Source |
|----------|-------------|--------|
| [Variable] | [What it measures] | [Data source] |

### Methodology

[Description of the analytical approach]

**Key decisions:**
- [Decision 1 and rationale]
- [Decision 2 and rationale]
- [additional decisions and rationale as needed]

### Data Cleaning

- **Records analyzed:** [count] of [total fetched]
- **Records excluded:** [count] ([reason])
- **Suppression rate:** [percentage] (records suppressed for privacy)

---

## Quality Assurance

All analysis code underwent secondary QA review during execution:

| Checkpoint | Stage | What Was Validated | Status |
|------------|-------|-------------------|--------|
| QA1 | Data Fetch | Schema correctness, year coverage, ID uniqueness | PASSED |
| QA2 | Data Cleaning | Coded value handling, suppression calculation | PASSED |
| QA3 | Transformation | Join cardinality, row preservation, derived columns | PASSED |
| QA4a | Statistical Analysis | Statistical validity, assumption checks, sample sizes | PASSED |
| QA4b | Visualization | Figure accuracy, data source alignment | PASSED |

**QA Notes:**
- [Any resolved BLOCKERs: "A join cardinality issue was identified and corrected during Stage 7"]
- [Any logged WARNINGs: "Minor: Suppression rate approaches 30% in small school subset"]
- [Or: "No significant QA issues identified during execution"]

**QA Scripts:** `scripts/cr/` contains all QA inspection scripts for reproducibility.

---

## Key Findings

### Finding 1: [Title]

[Description of the finding]

![Figure description](output/figures/YYYY-MM-DD_figure_name.png)
*Figure 1: [Caption describing what the figure shows]*

**Interpretation:** [What this means in context]

---

### Finding 2: [Title]

[Description of the finding]

![Figure description](output/figures/YYYY-MM-DD_figure_name.png)
*Figure 2: [Caption]*

**Interpretation:** [What this means]

---

### Finding X: [Title]

[Continue providing findings in this format as needed]

---

## Summary Statistics

[Include key summary table if applicable]

| Metric | Value |
|--------|-------|
| [Metric] | [Value] |

---

## Limitations

This analysis has the following limitations that should be considered when interpreting results:

1. **[Limitation category]:** [Description and impact on conclusions]

2. **[Limitation category]:** [Description and impact on conclusions]

3. **[Limitation category, adding more line items as needed]:** [Description and impact on conclusions]

4. **Data suppression:** [X]% of records were suppressed for privacy, which may affect [specific impact]

5. **[Source-specific limitation]:** [From domain context skill (per Plan Domain Configuration)]

6. **COVID-19 impact (if applicable):** [If analysis includes 2020-2021 data, REQUIRED to document: Data from 2020-2021 may be affected by COVID-19 pandemic disruptions including collection method changes, missing data, and non-representative samples. Comparisons to pre-pandemic years should be interpreted with caution.]

---

## Data Sources & Citations

### Primary Data

> [Full citation from domain context skill (per Plan Domain Configuration)]

### Additional Sources

> [Citation 2 if applicable]

### Software & Tools

> Kim, B. H. (2026). *DAAF: Data Analyst Augmentation Framework* (Version 2.0.0) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf

> [AUTO — report-writer: Always include the DAAF citation above. Update the version number if CITATION.cff in the DAAF repository root specifies a different version.]

---

## AI Use Disclosure

> This analysis was conducted using the **Data Analyst Augmentation Framework (DAAF)** (Kim, 2026), an open-source AI-assisted research orchestration system built on Claude Code (Anthropic). The following disclosure follows the GUIDE-LLM reporting checklist (Feuerriegel et al., 2026). For complete guidance, see `agent_reference/AI_DISCLOSURE_REFERENCE.md`.

**Date of analysis:** [AUTO — session date(s) from orchestrator date prefix]
**DAAF version:** [AUTO — short git commit hash captured at project setup]

### Role of AI in This Analysis (GUIDE-LLM A.1-A.2)

- **Purpose:** `[AUTO]` [Derived from Plan.md — e.g., "AI was used for data acquisition, cleaning script generation, transformation logic, statistical analysis code, and visualization generation. All code was reviewed through automated QA checkpoints and human oversight gates."]
- **Human oversight model:** `[AUTO]` Human-in-the-loop. The researcher reviewed and approved methodology (Checkpoint 2), data quality (Checkpoint 3), and analytical results (Checkpoint 4) before each phase advanced.

### Model & Configuration (GUIDE-LLM B.1-B.5)

| Item | Value | Source |
|------|-------|--------|
| Model | `[AUTO]` [e.g., Claude Opus 4.6 (claude-opus-4-6)] | Session metadata |
| Provider | `[AUTO]` Anthropic | — |
| Access method | `[AUTO]` Claude Code CLI (local execution via API) | — |
| Date of use | `[AUTO]` [Session date(s)] | STATE.md |
| Parameters | `[AUTO]` Default API parameters; no user-configured overrides | — |
| Customization | `[AUTO]` DAAF framework: domain-specific skills, agent definitions, and system instructions (see Technical Notes for repository link) | — |
| Session state | `[AUTO]` Stateful within sessions; STATE.md tracks cross-session continuity | — |

### Prompts & Instructions (GUIDE-LLM C.1-C.2)

`[AUTO]` All prompts and system instructions are version-controlled in the DAAF repository:
- System instructions: `CLAUDE.md`
- Agent behavioral specifications: `.claude/agents/` directory
- Domain knowledge skills: `.claude/skills/` directory

### Data Privacy (GUIDE-LLM D.1)

`[RESEARCHER]` [Researcher must confirm: What data was submitted to the AI model? Was any personally identifiable information (PII) involved? Default for public federal data: "No personally identifiable information was submitted to the LLM. All data accessed was from public federal data sources."]

### Validation of AI Outputs (GUIDE-LLM E.1-E.2)

- **Automated code review:** `[AUTO]` All scripts underwent automated QA review by a separate AI instance (see Quality Assurance section above)
- **Human validation:** `[AUTO]` [Derived from STATE.md checkpoint statuses — e.g., "Researcher approved methodology at Checkpoint 2, verified data quality at Checkpoint 3, and validated analytical results at Checkpoint 4"]
- **Post-processing:** `[RESEARCHER]` [Researcher documents any manual edits made to AI-generated outputs after delivery. Default if none: "No manual post-processing was applied to AI-generated outputs."]

### Reproducibility (GUIDE-LLM F.1)

`[AUTO]`
- All analysis scripts with execution logs: `scripts/` directory
- Consolidated analytic notebook: `[notebook filename]`
- Session transcript(s): `logs/` directory (full JSONL + human-readable MD for each work session)

### Funding & Conflicts of Interest (GUIDE-LLM G.1)

`[RESEARCHER]` [Researcher must disclose: Funding sources for this research, approximate API costs incurred, and any relevant relationships with AI providers or other potential conflicts of interest.]

---

## Technical Notes

### Reproducibility

- **Notebook:** `YYYY-MM-DD_[Title].py`
- **Processed data:** `data/processed/YYYY-MM-DD_*.parquet`
- **Raw data:** `data/raw/YYYY-MM-DD_*.parquet`
- **Session logs:** `logs/*.{jsonl,md}` (complete interaction transcripts)

### Analysis Environment

- Python 3.12
- Key packages: polars, plotnine, marimo

---

## Appendix

### A. Additional Figures

[Any supplementary visualizations not included in main findings]

### B. Detailed Methodology

[Extended methodology notes if valuable for auditability and full explanations]

### C. Data Dictionary

[Definitions of key variables if helpful for reader]

| Variable | Definition | Values |
|----------|------------|--------|
| [var] | [definition] | [possible values] |
