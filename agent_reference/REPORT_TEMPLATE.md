# [Analysis Title]

**Date:** YYYY-MM-DD
**Version:** [Original | Revision suffix]

<!-- Agent note (delete before delivery): each HTML comment in this template that opens with "Agent note" is an instruction for the report-writer, not report text. Delete them all, and remove each `[AUTO]` tag, before delivering the report. Keep each `[RESEARCHER]` tag and its prompt: the researcher completes those fields. The sources for each section are mapped in `.claude/agents/report-writer.md` § Core Behaviors > 2. Section-Source Mapping Discipline; discovery-phase source caveats are also in `output/preliminary_notes/`. -->

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

The analysis scripts carry built-in automated validation checks. In addition, a separate AI quality reviewer inspected every script after it ran, before anything that builds on it started:

<!-- Agent note (delete before delivery): fill Result from STATE.md § Checkpoint Status > Secondary Validation (QA1-QA4b) and § QA Findings Summary, never from this template. Rows map QA1 = data download, QA2 = data cleaning, QA3 = joining and transforming, QA4a = statistical analysis, QA4b = figures. Result PASSED → "Passed"; WARNING → "Passed with notes" (a warning, or a check that could not be verified); a stage with a row under BLOCKERs Resolved → add "issue found and fixed"; PENDING or no row → "Not run". Never write a bare "Passed" for a stage with warnings, unverified checks or a resolved blocker. -->

| Step reviewed | What the quality reviewer checked | Result |
|---------------|-----------------------------------|--------|
| Data download | Schema correctness, year coverage, ID uniqueness | [Result] |
| Data cleaning | Coded value handling, suppression calculation | [Result] |
| Joining and transforming | Join matching (no unexpected duplicated or lost records), row preservation, derived columns | [Result] |
| Statistical analysis | Statistical validity, assumption checks, sample sizes | [Result] |
| Figures | Figure accuracy, match between each figure and its data | [Result] |

**Review notes:**
- [Each issue found and fixed: "A join matching issue was found and corrected while the data sources were being joined"]
- [Each note on record: "Minor: the suppression rate approaches 30% in the small-school subset"]
- [Each check that could not be run, from STATE.md § QA Findings Summary > Checks Not Verified or Skipped: what was not checked and why]
- [Or: "The quality review raised no issues"]

**Review scripts:** the quality reviewer's inspection scripts, each with its execution log, are in `scripts/cr/`.

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

## References

### Data Sources

> [Full citation from STATE.md > Citations Accumulated > Data Sources]

### Methodological References

[Only include if methodological citations were accumulated in STATE.md.
 Omit this subsection entirely for purely descriptive analyses.]

> [Citation entry from STATE.md]
> *Cited because: [rationale from STATE.md]*

### Software & Tools

> Kim, B.H. (2026). *DAAF: The Data Analyst Augmentation Framework* (Version 3.0.2) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf
> *Cited because: Analysis framework*

> [Additional software citations from STATE.md > Citations Accumulated > Software & Tools]
> *Cited because: [rationale from STATE.md]*

<!-- Agent note (delete before delivery): the DAAF citation is always included. For Python projects, the marimo citation is always included. For R projects, include R, Quarto, and key R package citations instead. Additional software citations come from STATE.md. Update the DAAF version number and year if `CITATION.cff` at the repository root specifies different values. -->

### Reporting Standards

[Only include if reporting standard citations were accumulated in STATE.md.
 Omit this subsection entirely if none apply.]

> [Citation entry from STATE.md]
> *Cited because: [rationale from STATE.md]*

---

## AI Use Disclosure

> This analysis was conducted using the **Data Analyst Augmentation Framework (DAAF)** (Kim, 2026), an open-source AI-assisted research orchestration system built on Claude Code (Anthropic). The following disclosure follows the GUIDE-LLM reporting checklist (Feuerriegel et al., 2026). For complete guidance, see `agent_reference/AI_DISCLOSURE_REFERENCE.md`.

**Date of analysis:** [AUTO — session date(s) from orchestrator date prefix]
**DAAF version:** [AUTO — short git commit hash captured at project setup]

### Role of AI in This Analysis (GUIDE-LLM A.1-A.2)

- **Purpose:** `[AUTO]` [Derived from Plan.md — e.g., "AI was used for data acquisition, cleaning script generation, transformation logic, statistical analysis code, and visualization generation. All code was checked by automated validation and an AI quality reviewer, and the researcher reviewed the work at each checkpoint."]
- **Human oversight model:** `[AUTO]` Human-in-the-loop. The researcher approved the analysis scope before any data exploration began, then reviewed the data sources found, approved the analysis plan, checked the prepared data's quality, and confirmed the results before the report was written.

### Model & Configuration (GUIDE-LLM B.1-B.5)

<!-- Agent note (delete before delivery): model IDs, dates, the provider route and the parameters come from STATE.md § Session Metadata (Session Model ID, Subagent Model Tiers, Session Date(s), Provider Route, Model Settings). Model Settings depends on the route (`agent_reference/AI_DISCLOSURE_REFERENCE.md` § Determining the Provider Route): `effortLevel` reaches the model on Anthropic routes, while on the provider-shim routes the shim sets the reasoning effort and response verbosity. If Model Settings is empty or reads "[Not recorded]", write "[Not recorded: the researcher should state the model settings used, such as reasoning effort]" in the Parameters row. Add any model setting the researcher changed during the work if STATE.md § Key Decisions Made records one. If Provider Route is empty, write "[Not recorded: the researcher should state how DAAF connected to its models]" in the Provider and Access method rows rather than guessing. -->

| Item | Value |
|------|-------|
| Model (session) | `[AUTO]` [Session model name and ID in use at session start — e.g., Claude Opus 4.8 (claude-opus-4-8[1m])] |
| Specialist models | `[AUTO]` [Distinct subagent-tier model IDs actually dispatched — e.g., "opus tier: claude-opus-4-8[1m]; sonnet tier: claude-sonnet-4-5". Record resolved IDs where known, or the tier alias + session date otherwise. See AI_DISCLOSURE_REFERENCE.md > Multi-Model Sessions.] |
| Provider | `[AUTO]` [The company that served the models, from the provider route: Anthropic (Anthropic subscription or API key); OpenAI (OpenAI API or ChatGPT subscription through DAAF's provider shim); OpenRouter, naming each model's maker too; Amazon Web Services (AWS Bedrock); Google Cloud (Vertex AI)] |
| Access method | `[AUTO]` Claude Code command-line tool, run locally in DAAF's container and connected through [the provider route, e.g. "an Anthropic subscription" or "the OpenAI API via DAAF's provider shim"]. Claude Code works agentically: one task involves many separate model calls, some made by specialist AI agents. |
| Date of use | `[AUTO]` [Session date(s)] |
| Parameters | `[AUTO]` Claude Code's defaults, except [the recorded model settings, in plain words — e.g. "reasoning effort set to high (DAAF's `effortLevel` setting)" or "reasoning effort and response verbosity set by DAAF's provider shim: reasoning effort high, response verbosity medium"]. DAAF sets no temperature, output-length or random-seed values. |
| Customization | `[AUTO]` DAAF framework: domain-specific skills, agent definitions, and system instructions (see References > Software & Tools for the repository link) |
| Session state | `[AUTO]` Stateful within sessions; STATE.md tracks cross-session continuity |

### Prompts & Instructions (GUIDE-LLM C.1-C.2)

`[AUTO]` All prompts and system instructions are version-controlled in the DAAF repository:
- System instructions: `CLAUDE.md`
- Agent behavioral specifications: `.claude/agents/` directory
- Domain knowledge skills: `.claude/skills/` directory

### Data Privacy (GUIDE-LLM D.1)

`[RESEARCHER]` [Researcher must confirm: What data was submitted to the AI model? Was any personally identifiable information (PII) involved? Default for public federal data: "No personally identifiable information was submitted to the LLM. All data accessed was from public federal data sources."]

### Validation of AI Outputs (GUIDE-LLM E.1-E.2)

- **Automated code review:** `[AUTO]` All scripts were reviewed by a separate AI quality reviewer (see the Quality Assurance section above)
- **Human validation:** `[AUTO]` [What the researcher approved or changed at each checkpoint, in plain words, from STATE.md § Pre-Flight Scope Check and the user-checkpoint rows in § Key Decisions Made — e.g., "At the planning checkpoint the researcher approved the plan and asked to add 2019 data." Never cite automated validation results here: they are machine checks, reported in the Quality Assurance section.]
- **Post-processing:** `[RESEARCHER]` [Researcher documents any manual edits made to AI-generated outputs after delivery. Default if none: "No manual post-processing was applied to AI-generated outputs."]

### Reproducibility (GUIDE-LLM F.1)

`[AUTO]`
- All analysis scripts with execution logs: `scripts/` directory
- Consolidated analytic notebook: `[notebook filename]`
- Session transcript(s): `logs/` directory (full JSONL + human-readable MD for each work session)

### Funding & Conflicts of Interest (GUIDE-LLM G.1)

`[RESEARCHER]` [Researcher must disclose: Funding sources for this research and any relevant relationships with AI providers or other potential conflicts of interest (GUIDE-LLM G.1). DAAF addition, not GUIDE-LLM G.1 text: also report approximate API costs incurred (nearest GUIDE-LLM item: the optional "Computational resources").]

---

## Technical Notes

### Reproducibility

- **Notebook:** `YYYY-MM-DD_[Title].py` (Marimo) or `YYYY-MM-DD_[Title].qmd` (Quarto)
- **Processed data:** `data/processed/YYYY-MM-DD_*.parquet`
- **Raw data:** `data/raw/YYYY-MM-DD_*.parquet`
- **Session logs:** `logs/*.{jsonl,md}` (complete interaction transcripts)

### Analysis Environment

**Python execution:**
- Python 3.12
- Key packages: polars, plotnine, marimo

**R execution:**
- R 4.5.3
- Key packages: tidyverse, ggplot2, arrow, quarto
- Quarto 1.10.18

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
