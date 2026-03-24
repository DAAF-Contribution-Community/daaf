# AI Use Disclosure Reference

This document provides framework-wide guidance for attributing and disclosing AI use in all work produced with DAAF. It follows the **GUIDE-LLM** reporting checklist (Feuerriegel et al., 2026), a consensus-based standard for transparent AI use in behavioral and social science research.

**Loading trigger:** Referenced by the report-writer agent (Stage 11) and available to all modes that produce user-facing deliverables.

---

## Why Disclosure Matters

DAAF's architecture already captures a rich audit trail — immutable scripts, inline audit trail (IAT) comments, QA checkpoint logs, session archives. But this internal record is legible only to someone with access to the project repository. **AI use disclosure translates DAAF's audit trail into a form that external audiences — journal reviewers, funders, collaborators, and the public — can evaluate.** As AI use disclosure norms and requirements continue to evolve rapidly across journals, funders, and institutions, having a structured disclosure process ensures DAAF-produced work meets these emerging standards.

---

## GUIDE-LLM Checklist: DAAF Mapping

The table below maps each GUIDE-LLM core item to its DAAF artifact source and indicates whether the report-writer agent can auto-populate it (`[AUTO]`) or whether the researcher must provide the content (`[RESEARCHER]`).

### Core Items

| GUIDE-LLM Item | Description | DAAF Source | Populated By |
|---|---|---|---|
| **A.1** | Purpose of LLM use | Plan.md (research question + methodology) | `[AUTO]` — report-writer derives from Plan.md |
| **A.2** | Human-in-the-loop vs. fully automated | DAAF architecture (checkpoint gates) | `[AUTO]` — always "Human-in-the-loop" for Full Pipeline |
| **B.1** | Model name, provider, version, date of access | Session metadata + CLAUDE.md | `[AUTO]` — orchestrator provides model ID and session date(s) |
| **B.2** | Access method (API/web/local) | DAAF architecture | `[AUTO]` — always "Claude Code CLI (local execution via API)" |
| **B.3** | Parameters (temperature, max tokens, seed) | DAAF architecture | `[AUTO]` — "Default API parameters; no user-configured overrides" |
| **B.4** | Fine-tuning or customization | DAAF framework files | `[AUTO]` — reference to DAAF skills, agents, and system instructions |
| **B.5** | Session state retention | STATE.md + session archives | `[AUTO]` — "Stateful within sessions; STATE.md tracks cross-session continuity" |
| **C.1** | Exact prompts reported | Agent `.md` files, skill files | `[AUTO]` — reference to version-controlled prompt files in DAAF repository |
| **C.2** | System-wide instructions | CLAUDE.md | `[AUTO]` — reference to CLAUDE.md in repository |
| **D.1** | Handling of personal/sensitive data | Safety guardrails in CLAUDE.md | `[RESEARCHER]` — researcher must confirm what data was processed and any PII considerations |
| **E.1** | Human validation of LLM outputs | QA checkpoints + user gates | `[AUTO]` — derived from STATE.md checkpoint statuses and QA summary |
| **E.2** | Filtering, reformatting, or post-processing | Script execution logs | `[RESEARCHER]` — researcher documents any manual edits made to AI-generated outputs after delivery |
| **F.1** | Code/scripts shared | Marimo notebook + `scripts/` archive | `[AUTO]` — file paths from project structure |
| **G.1** | Funding, support, or relevant relationships | N/A — external to DAAF | `[RESEARCHER]` — researcher must disclose funding sources, API cost disclosure, and any relevant relationships |

### Optional Items

| GUIDE-LLM Optional Item | DAAF Advantage | Populated By |
|---|---|---|
| Justification for LLM choice | DAAF framework selection rationale | `[RESEARCHER]` — why DAAF/Claude was chosen over alternatives |
| Rationale for prompt design | Agent `.md` files document behavioral protocols; skills document domain knowledge injection | `[AUTO]` — reference to agent and skill architecture |
| Comparison against other methods/LLMs | Not captured by default | `[RESEARCHER]` — if applicable |
| Training data leakage risks | Mitigated by data-driven validation (assert statements, QA checkpoints) | `[RESEARCHER]` — assess for specific analysis context |
| Risk of bias or systematic differences | LEARNINGS.md + Limitations section | `[AUTO]` partial — LEARNINGS.md entries; `[RESEARCHER]` for interpretation |
| Conversation transcripts | Session archives via `archive-session.sh` | `[AUTO]` — reference to archived session transcripts |
| Ethical implications | Not captured by default | `[RESEARCHER]` — if applicable |
| Computational resources | Session logs (duration, token usage) | `[AUTO]` partial — available from session archives |

---

## DAAF Version and Session Metadata

Every disclosure should include version and temporal metadata to support reproducibility:

| Metadata Item | Source | How to Capture |
|---|---|---|
| **Date of analysis** | Session date(s) from STATE.md or orchestrator | Report-writer uses the date prefix (e.g., "2026-02-11") provided by orchestrator |
| **DAAF version** | Git commit hash of the DAAF repository at time of analysis | Orchestrator captures via `git rev-parse --short HEAD` at project setup and provides to report-writer |
| **Model ID** | Claude model identifier | From CLAUDE.md or session metadata (e.g., "claude-opus-4-6") |
| **Session transcript** | Archived session log | Path to session archive; flag for researcher: *"Your full session transcript has been archived and can be included as supplementary material per GUIDE-LLM optional item on conversation transcripts"* |

**Note on session transcripts:** DAAF automatically archives full session transcripts via the `archive-session.sh` hook. These transcripts are a powerful differentiator — most AI-assisted research cannot point to a complete record of the human-AI interaction. Researchers are encouraged to include these as supplementary material when submitting to journals, as they provide unparalleled transparency into the AI-assisted research process.

---

## Mode-Specific Disclosure Guidance

Different engagement modes involve different levels of AI assistance. The disclosure should match the depth of involvement.

### Full Pipeline Mode

**Depth:** Comprehensive. AI was involved in every stage from data acquisition to report generation.

**Template:** Use the full "AI Use Disclosure" section in REPORT_TEMPLATE.md. The report-writer agent auto-populates `[AUTO]` fields; the researcher completes `[RESEARCHER]` fields before publication.

**Key points to document:**
- AI generated all analysis code (data fetching, cleaning, transformation, analysis, visualization)
- All code underwent automated QA review by a separate AI instance (code-reviewer agent)
- Researcher reviewed and approved methodology at Checkpoint 2, data quality at Checkpoint 3, and analytical results at Checkpoint 4
- All scripts, data files, and execution logs are archived for reproducibility

### Data Discovery Mode

**Depth:** Light. AI conducted read-only data exploration; no code was executed, no data was downloaded.

**Template:**
> This exploratory assessment was conducted using DAAF (Data Analyst Augmentation Framework) with [model ID] via Claude Code CLI on [date]. DAAF version: [commit hash]. The AI was used solely for read-only data landscape exploration — identifying available data sources, variables, and feasibility considerations. No analytical code was executed and no data was downloaded. The researcher reviewed and directed the exploration throughout. For the full GUIDE-LLM checklist, see the AI_DISCLOSURE_REFERENCE.md in the DAAF repository.

### Data Lookup Mode

**Depth:** Minimal. AI answered a specific factual question from structured documentation.

**Template:**
> AI assistance (DAAF with [model ID], [date]) was used to look up [specific information] from [data source documentation]. The answer was verified against [source]. DAAF version: [commit hash].

### Revision and Extension Mode

**Depth:** Inherits from original, plus revision scope.

**Template:** Include the original analysis's disclosure, then append:
> **Revision conducted on [date]:** AI assistance was used to [describe revision scope — e.g., "modify the poverty threshold variable and re-run affected analysis stages"]. The same QA review process was applied to all re-executed code. DAAF version: [commit hash].

### Data Ingest Mode

**Depth:** Moderate. AI profiled dataset structure and generated a reusable data source skill.

**Template:**
> Dataset profiling was conducted using DAAF (Data Analyst Augmentation Framework) with [model ID] via Claude Code CLI on [date]. DAAF version: [commit hash]. The AI executed structured profiling scripts across four phases (structural, statistical, relational, interpretation) to characterize the dataset. All profiling scripts underwent automated QA review. The researcher reviewed profiling findings at two checkpoints before the data source skill was finalized. All profiling scripts and execution logs are archived in the project's `scripts/` directory.

### Reproducibility Verification Mode

**Disclosure depth:** Moderate

**Key points to disclose:**
- AI performed mechanical re-execution of existing analysis scripts and output comparison
- AI assessed methodological concerns at user-selected depth (light or full)
- AI cross-referenced original Report claims against reproduced data
- Human researcher reviewed the final Reproduction Report and assessed the significance of all findings and deviations

**Template paragraph:**
> This reproduction was conducted using the DAAF Reproducibility Verification mode. An AI agent re-executed all [N] analysis scripts from the original marimo notebook, compared outputs against the original execution logs, and cross-referenced the Report's quantitative claims against reproduced results. The human researcher reviewed the resulting Reproduction Report, including all deviations and methodological concerns, and determined the overall reproducibility assessment.

### Consultative Mode (Planned)

**Depth:** Variable — depends on the nature of the consultation.

**Guidance:** Consultative interactions range from quick methodological advice to substantive code review or analytical suggestions. The disclosure should scale accordingly:

- **Light consultation** (methodological question, interpretation advice): Use the Data Lookup template adapted for the consultation context.
- **Substantive consultation** (code generation, analytical approach design, data interpretation): Use a template similar to:

> AI assistance (DAAF with [model ID], [date], version [commit hash]) was used for [specific consultation purpose — e.g., "designing the regression specification" or "reviewing data cleaning logic"]. The researcher independently verified [what was verified] and takes responsibility for all final analytical decisions.

---

## Boilerplate: Methods Section Language

For researchers writing up DAAF-assisted work for publication, the following boilerplate can be adapted for a manuscript's methods section:

### Short Version (for methods sections with space constraints)

> Data analysis was conducted using the Data Analyst Augmentation Framework (DAAF; Kim, 2026), an open-source AI-assisted research orchestration system built on Claude Code (Anthropic, [model ID]). DAAF enforces human-in-the-loop oversight through structured checkpoints, automated code review, and full audit trail preservation. All analysis code, data files, and AI interaction transcripts are archived for reproducibility. A completed GUIDE-LLM checklist (Feuerriegel et al., 2026) is included as supplementary material.

### Long Version (for detailed methods sections or supplementary materials)

> Data analysis was conducted using the Data Analyst Augmentation Framework (DAAF; Kim, 2026), an open-source AI-assisted research orchestration system built on Claude Code (Anthropic). DAAF structures the analysis pipeline into discrete phases — discovery, planning, data acquisition, analysis, and synthesis — with mandatory human review checkpoints between each phase. The AI generated all analysis code, which was then reviewed by a separate AI instance acting as an automated quality reviewer before the researcher's own review. The researcher reviewed and approved the analytical methodology before any code was executed, verified data quality after acquisition, and validated all results before report generation.
>
> The specific model used was [model ID], accessed via the Claude Code CLI with default API parameters on [date(s)]. DAAF version [commit hash] was used. No personally identifiable information was submitted to the AI model. The complete set of analysis scripts with execution logs, intermediate data files, a consolidated analytic notebook, and the full AI session transcript are available as supplementary materials. All AI prompts and system instructions are version-controlled in the DAAF repository. A completed GUIDE-LLM reporting checklist (Feuerriegel et al., 2026) is included as Supplementary Material [X].

---

## Journal-Specific Considerations

AI disclosure requirements vary across journals and are evolving rapidly. The following is general guidance as of early 2026:

| Context | Typical Requirement | DAAF Coverage |
|---|---|---|
| **APA journals** | Disclose AI use in methods; AI cannot be listed as author | Full Pipeline disclosure section covers this; ensure researcher is sole author |
| **Nature portfolio** | Disclose AI use in methods and/or acknowledgments; AI cannot be listed as author | Methods boilerplate + GUIDE-LLM checklist as supplement |
| **Science** | Disclose AI use; no AI authorship | Methods boilerplate covers this |
| **PNAS** | Disclose AI use in methods | Methods boilerplate covers this |
| **Funder requirements** | Varies — increasingly requiring AI disclosure | GUIDE-LLM checklist as supplement is broadly acceptable |
| **Preprint servers** | Generally no strict requirement, but disclosure is best practice | Include at minimum the short methods boilerplate |

**General best practice:** Include the completed GUIDE-LLM checklist as supplementary material regardless of journal requirements. This future-proofs the submission against evolving standards and signals methodological rigor.

**Important:** Always check the specific submission guidelines of your target venue. Requirements are changing frequently. The guidance above reflects general trends and may not capture recent policy updates.

---

## GUIDE-LLM Citation

When referencing the GUIDE-LLM framework in publications, use:

> Feuerriegel, S., Barrie, C., Crockett, M. J., Globig, L. K., McLoughlin, K. L., Mirea, D.-M., Spirling, A., Yang, D., ..., Rathje, S., & Ribeiro, M. H. (2026). A consensus-based reporting checklist for large language models in behavioral and social science. Available at: https://llm-checklist.com/

---

## DAAF Citation

When citing DAAF in publications, use:

> Kim, B. H. (2026). *DAAF: The Data Analyst Augmentation Framework* (Version 2.0.0) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf

**BibTeX:**

```bibtex
@software{kim2026daaf,
  author = {Kim, Brian Heseung},
  title = {{DAAF}: The Data Analyst Augmentation Framework},
  year = {2026},
  url = {https://github.com/DAAF-Contribution-Community/daaf},
  version = {2.0.0},
  license = {LGPL-3.0-or-later}
}
```

**Version note:** If the version in `CITATION.cff` at the DAAF repository root differs from the version shown above, use the version from `CITATION.cff`.

---

## Integration Points

This reference is consumed by:

| Consumer | How It's Used |
|---|---|
| **report-writer** (Stage 11) | Populates the "AI Use Disclosure" section of REPORT_TEMPLATE.md using `[AUTO]` field mappings |
| **Orchestrator** (all modes) | Provides mode-specific disclosure templates for non-pipeline outputs |
| **Researcher** (post-delivery) | Completes `[RESEARCHER]` fields, adapts methods boilerplate for manuscripts, prepares GUIDE-LLM checklist as supplementary material |
