# [Analysis Title]

**Date:** YYYY-MM-DD
**Version:** [Original | Revision suffix]

## Source Mapping Guide

> **For the report-writer agent:** This guide maps each report section below to its primary pipeline artifact source. When populating each section, consult the primary source first, then secondary sources for additional detail.

| Report Section | Primary Source | Secondary Sources |
|---|---|---|
| Executive Summary | Plan § Observable Truths + Stage 7-8 execution logs | LEARNINGS.md |
| Research Question | Plan § Research Question (verbatim) | Plan § Context |
| Data & Methods: Data Sources | Plan § Data Sources table | Stage 5 execution logs |
| Data & Methods: Key Variables | Plan § Key Variables | — |
| Data & Methods: Methodology | Plan § Methodology Specification | Plan § Key Decisions |
| Data & Methods: Data Cleaning | Stage 6 execution logs | STATE.md checkpoints |
| Quality Assurance | Stage 10 QA summary | STATE.md QA sections |
| Key Findings | Stage 7-8 outputs + figures | Plan § Observable Truths |
| Summary Statistics | Analysis dataset metadata + Stage 7 EDA logs | Notebook data cells |
| Limitations | Plan § Risk Register + source caveats + LEARNINGS.md | STATE.md blockers |
| Data Sources & Citations | Stage 6 citation text (verbatim) | Plan § Data Sources |
| Technical Notes | Project file paths | — |
| Appendix | Additional figures + extended methodology from Plan | — |

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

---

## Technical Notes

### Reproducibility

- **Notebook:** `YYYY-MM-DD [Title].py`
- **Processed data:** `data/processed/YYYY-MM-DD_*.parquet`
- **Raw data:** `data/raw/YYYY-MM-DD_*.parquet`

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
