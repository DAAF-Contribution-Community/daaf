# Sample Project: College Graduation Rate & Selectivity Analysis

This is a **sample Full Pipeline project** included with DAAF to show what a complete, end-to-end research analysis looks like when produced with the framework. It was conducted using DAAF's [Full Pipeline mode](../../user_reference/02_understanding_daaf.md#full-pipeline-mode) -- the most comprehensive engagement mode, which takes a research question through data discovery, planning, acquisition, cleaning, transformation, analysis, visualization, and reporting with human oversight at every key decision point.

This project is presented in its entirety **without editing** -- warts and all. The goal is not to showcase a flawless analysis, but to give you a realistic and transparent look at what DAAF actually produces so you can judge for yourself what's impressive, what needs work, and how the human review process fits in. Some of the interpretation is arguably overblown in its conclusions, and some analytical choices could be questioned. That's the point: DAAF produces work that is **worth reviewing**, not work that can be trusted blindly.

A few quick visualization fixes were applied afterward via [Revision and Extension mode](../../user_reference/02_understanding_daaf.md#revision-and-extension-mode), but all substantive outputs are exactly as Claude produced them.

> **See also:** This project was subsequently [reproduced and verified](../2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/) using DAAF's Reproducibility Verification mode. That project has its own README with a walkthrough.

---

## How It Started

The analysis began with a single natural-language prompt -- no special formatting, no technical jargon required:

> *I'm aware that graduation rates are often thought of as a key outcome for assessing a university/college's quality by the general public, but many researchers argue that there's a very strong question of chicken-or-the-egg in interpreting it that way: Are graduation rates high because the college actually did a good job in serving its students, or are graduation rates high because the college selectively admits students who are already highly competitive and academically prepared and likely to graduate/succeed anyway? I'd like to more critically explore this dynamic with data to better understand how correlated these things are, especially when thinking about additional complicating institutional factors like share of students on financial aid, other underserved or historically disadvantaged student population rates, etc. I'd like an analysis that helps provide an intuitive and holistic view on how these factors all relate to one another, and what implications that might have for broadly thinking about college 'quality' in general.*

DAAF classified this as a Full Pipeline analysis and walked the researcher through a series of clarification questions before beginning. After DAAF presented its initial data scoping findings and proposed a hierarchical regression approach, the researcher provided a key clarification that reshaped the entire analytical strategy:

> *Yeah that all sounds good, please proceed. I think I'd like to have the more complicated methods, but also more intuitive simple descriptive analyses by bins of selectivity to get at some of the basic overview as well. Think of the regression work as supplementary so we can easily communicate findings*

This single clarification established two principles that guided the entire project:

1. **Analytical emphasis:** Descriptive analyses organized by selectivity bands as the *primary* approach -- intuitive and easy to communicate to broad audiences
2. **Regression role:** Regression should be *supplementary* evidence supporting the descriptive narrative, not the main story

From there, DAAF handled the rest -- data scoping, analytic planning, data acquisition and cleaning, in-depth code review, analysis, visualization, and report writing -- pausing at four checkpoints for the researcher to review and approve before continuing.

You can read the full original prompt and clarifications in the [Plan document](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#original-request--clarifications).

---

## Where It Goes: Start With the Report

The best place to start exploring this project is its final output -- **the Report**:

**[College Graduation Rate & Selectivity Analysis Report](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md)**

This is a stakeholder-ready research report with an executive summary, methodology description, 8 key findings with embedded visualizations, a full limitations section, data citations, an AI use disclosure following the [GUIDE-LLM](https://llm-checklist.com/) checklist, and regression results in the appendix. It analyzes 1,946 four-year institutions using data from 9 IPEDS endpoints (including SFA grants as a Pell Grant proxy after the original FSA data source was found to be unavailable).

Some highlights worth reading closely:

- [**Executive Summary**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md#executive-summary) -- A concise synthesis of key findings accessible to a general audience
- [**Finding 3**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md#finding-3-most-of-the-selectivity-effect-disappears-when-you-account-for-other-factors-h2-assessment) -- Where the hierarchical regression reveals that institutional *resources*, not student *demographics*, explain away selectivity's apparent effect
- [**Finding 4**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md#finding-4-financial-aid-dependency-and-graduation-rates--a-surprising-pattern-h3-assessment) -- A surprising reversal of the expected relationship between financial aid dependency and graduation rates
- [**Limitations**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md#limitations) -- Nine honest, specific limitations including the partially tautological nature of using retention rate as a predictor
- [**AI Use Disclosure**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md#ai-use-disclosure) -- Full GUIDE-LLM checklist disclosure documenting exactly how AI was used, including `[RESEARCHER]` placeholder fields that the human researcher is expected to fill in
- [**Quality Assurance**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md#quality-assurance) -- Summary of the automated QA process: 34 scripts reviewed, zero blockers, 36 warnings documented with rationale

---

## How It Got There: Understanding the Artifacts

### The Plan

**[Plan document](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md)** -- The research blueprint. Created during Stages 2-4 (data exploration, source deep-dives, and planning), this document captures everything DAAF learned about the available data and how it intends to analyze it. Key sections:

- [**Original Request & Clarifications**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#original-request--clarifications) -- Your prompt plus the clarifying dialogue
- [**Must-Haves**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#must-haves-goal-backward-verification) -- Machine-readable success criteria with specific hypotheses (H1, H2, H3) and artifact specifications used for automated verification at the end
- [**Phase 1: Discovery Results**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#phase-1-discovery-results) -- What DAAF found when it explored the available data sources, including every variable, coded value, and caveat discovered
- [**Methodology Specification**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#methodology-specification) -- Detailed join strategy, query specifications for all 9 data endpoints, and cleaning rules
- [**Transformation Sequence**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#transformation-sequence) -- The wave-based execution plan: 33 tasks organized into 11 waves with explicit dependencies
- [**Decisions Log**](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md#decisions-log) -- Every planning-phase decision with options considered and rationale (e.g., why Scorecard data was excluded, why descriptive analysis was chosen over regression-first)

The Plan is **frozen after validation** (Stage 4.5) -- it is never modified during execution. All runtime decisions go to STATE.md instead.

### Plan Tasks

**[Plan Tasks document](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md)** -- The machine-readable companion to the Plan. Contains XML-formatted task definitions that DAAF's orchestrator uses to dispatch work to specialist agents. Each task specifies:

- What agent executes it and what skills it needs
- Input and output file paths
- Step-by-step action instructions
- Verification criteria
- Done conditions

Browse the [Task Index](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md#task-index) for a compact overview of all 33 tasks, or read individual task definitions like [Task 1.3: fetch-grad-rates](2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md#task-13-fetch-grad-rates-stage-5) to see how specific tasks are structured.

### Scripts

The `scripts/` directory contains every Python script that was executed during the analysis, organized by pipeline stage:

| Directory | Stage | What It Does | Scripts |
|-----------|-------|-------------|---------|
| [`scripts/stage5_fetch/`](scripts/stage5_fetch/) | Data Fetch | Downloads raw data from IPEDS and FSA endpoints | 9 final scripts |
| [`scripts/stage6_clean/`](scripts/stage6_clean/) | Data Cleaning | Applies coded-value handling, filtering, type casting, derived variables | 8 final scripts |
| [`scripts/stage7_transform/`](scripts/stage7_transform/) | Transformation | Joins datasets, creates selectivity bands and quintiles | 4 final scripts |
| [`scripts/stage8_analysis/`](scripts/stage8_analysis/) | Analysis & Viz | Descriptive statistics, regression, correlation, visualizations | 13 final scripts |

**Good scripts to explore as examples:**

- [`02_fetch-admissions.py`](scripts/stage5_fetch/02_fetch-admissions.py) -- A straightforward data fetch script showing the standard structure (config, load, validate, save)
- [`05_clean-enrollment-race.py`](scripts/stage6_clean/05_clean-enrollment-race.py) -- Computing URM share from detailed race/ethnicity enrollment data, with inline audit trail comments explaining every decision
- [`01_join-core.py`](scripts/stage7_transform/01_join-core.py) -- A multi-source LEFT JOIN with pre/post validation of row counts, match rates, and fan-out checks
- [`06_regression-models.py`](scripts/stage8_analysis/06_regression-models.py) -- Hierarchical OLS regression with robust standard errors, R-squared decomposition, and variance attribution

#### Understanding Script Suffixes

You'll notice some scripts have letter suffixes like `_a`, `_b`, `_c`, `_d`. These are **revision versions** -- when a script fails during execution, DAAF never modifies the original. Instead, it creates a new version with a suffix, preserving the full history:

- `04_fetch-fsa-grants.py` -- Original (failed: Pell data was 100% null)
- `04_fetch-fsa-grants_a.py` -- First revision (failed: tried alternative approach)
- `04_fetch-fsa-grants_b.py` -- Second revision (failed)
- `04_fetch-fsa-grants_c.py` -- Third revision (failed)
- `04_fetch-fsa-grants_d.py` -- Fourth revision (finally succeeded with SFA endpoint as Pell proxy)

Each failed script retains its execution log appended at the bottom, so you can trace the full debugging history. The FSA Pell saga is a particularly interesting example -- it took 5 attempts before DAAF discovered that the Pell Grant recipient data was simply unavailable for 2020-2021 in the data source and pivoted to using IPEDS SFA data as a proxy.

Not all suffixed scripts represent failures -- `03_clean-grad-rates_c.py` went through iterations to handle an unexpected data format (graduation rates stored as 0-1 proportions instead of 0-100 percentages).

### Code Review (CR) Scripts

**[`scripts/cr/`](scripts/cr/)** -- Contains 42 quality assurance inspection scripts produced by DAAF's code-reviewer agent. Every pipeline script undergoes automated QA review by a separate AI instance that writes and executes its own independent verification code.

CR script naming follows the pattern `stage{N}_{step}_cr{N}.py` (for fetch/clean/transform) or `stage8_{step}_cra{N}.py` / `stage8_{step}_crb{N}.py` (for analysis vs. visualization QA):

- [`stage5_01_cr1.py`](scripts/cr/stage5_01_cr1.py) -- QA review of the directory fetch script
- [`stage7_01_cr2.py`](scripts/cr/stage7_01_cr2.py) -- Second-pass QA of the core join, checking match rates and fan-out
- [`stage8_01_cra1.py`](scripts/cr/stage8_01_cra1.py) -- Statistical analysis QA: verifying the descriptive statistics are substantively reasonable
- [`stage8_08_crb1.py`](scripts/cr/stage8_08_crb1.py) -- Visualization QA: checking that figure annotations match the underlying data

### Data

**`data/raw/`** -- Raw parquet files downloaded from IPEDS and FSA endpoints (9 files). These are the unmodified source data.

**`data/processed/`** -- Cleaned and transformed data files, culminating in the final analysis dataset. These are generated by running the Stage 6-7 scripts.

> **Note:** Data files (`.parquet`) are excluded from the git repository via `.gitignore` due to file size. If you clone this repo, you can regenerate all data files by running the scripts in order using `scripts/run_with_capture.sh`.

### Output

**[`output/figures/`](output/figures/)** -- The 6 publication-quality visualizations produced by the analysis:

| Figure | Script | Description |
|--------|--------|-------------|
| ![](output/figures/2026-03-29_grad_rate_vs_admission_rate.png) | [`08_viz-scatter-grad-admit.py`](scripts/stage8_analysis/08_viz-scatter-grad-admit.py) | Graduation rate vs. admission rate scatter with trend line |
| ![](output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png) | [`09_viz-boxplot-selectivity_b.py`](scripts/stage8_analysis/09_viz-boxplot-selectivity_b.py) | Distribution of graduation rates by selectivity band |
| ![](output/figures/2026-03-29_heatmap_selectivity_pell.png) | [`10_viz-heatmap-selectivity-pell_c.py`](scripts/stage8_analysis/10_viz-heatmap-selectivity-pell_c.py) | Mean graduation rate by selectivity and Pell share |
| ![](output/figures/2026-03-29_correlation_heatmap.png) | [`11_viz-correlation-heatmap_a.py`](scripts/stage8_analysis/11_viz-correlation-heatmap_a.py) | Correlation matrix of all institutional characteristics |
| ![](output/figures/2026-03-29_sector_comparison.png) | [`12_viz-sector-comparison_d.py`](scripts/stage8_analysis/12_viz-sector-comparison_d.py) | Selectivity-graduation relationship by sector |
| ![](output/figures/2026-03-29_actual_vs_predicted.png) | [`13_viz-residual-scatter_b.py`](scripts/stage8_analysis/13_viz-residual-scatter_b.py) | Outperformer identification: actual vs. predicted graduation rates |

### The Notebook

**[Marimo Notebook](2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py)** -- A reactive Python notebook (in [marimo](https://marimo.io/) `.py` format) that consolidates all final script versions into a single interactive document. This is compiled from the individual scripts during Stage 9 (notebook assembly) and serves as both a reproducibility artifact and an interactive exploration tool. You can run it locally with `marimo edit` if you have marimo installed.

### STATE.md

**[STATE.md](STATE.md)** -- The operational state tracker for the entire session. This is the orchestrator's working memory -- updated continuously as the analysis progresses. Key sections:

- [**Current Position**](STATE.md#current-position) -- Which phase and stage the analysis has reached
- [**Checkpoint Status**](STATE.md#checkpoint-status) -- Pass/fail status of all primary (CP1-CP4) and secondary (QA1-QA4b) validation checkpoints
- [**Key Decisions Made**](STATE.md#key-decisions-made) -- Runtime decisions not in the Plan, like discovering that FSA Pell data was unavailable and pivoting to SFA
- [**Transformation Progress**](STATE.md#transformation-progress) -- Detailed tracking table for all 33+ scripts: status, row counts, QA findings, revision history
- [**QA Findings Summary**](STATE.md#qa-findings-summary) -- All 36 warnings logged across the pipeline with accepted rationale
- [**Session Continuity**](STATE.md#session-continuity) -- Restart prompt for resuming work across multiple sessions

### LEARNINGS.md

**[LEARNINGS.md](LEARNINGS.md)** -- Lessons learned during the analysis, organized into what worked well, what didn't, surprises, and a system update action plan. These learnings are designed to be actionable -- they can be fed back into DAAF via Framework Development mode to improve future analyses. For example, this project discovered that FSA Pell Grant data was completely null for 2020-2021, which informed updates to DAAF's data source documentation.

### Session Logs

**[`logs/`](logs/)** -- Complete session transcripts in both raw JSONL and human-readable Markdown format. Each session gets an orchestrator log and individual subagent logs. This project ran across 5 sessions, producing the full audit trail of every tool call, every agent dispatch, and every decision made during the analysis. These are the ultimate transparency artifact -- you can trace any output back to the exact conversation that produced it.

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Institutions analyzed | 1,946 four-year degree-granting |
| Data sources used | 9 IPEDS endpoints (FSA attempted but data unavailable; IPEDS SFA used as Pell proxy) |
| Pipeline scripts | 34 (9 fetch + 8 clean + 4 transform + 13 analysis/viz) |
| Script revisions | 24 revision-suffixed files across the pipeline |
| QA review scripts | 42 |
| QA blockers found | 0 |
| QA warnings documented | 36 |
| Output figures | 6 |
| Sessions required | 5 |
| DAAF mode | Full Pipeline |
| Model | Claude Opus 4.6 |

---

## File Structure

```
2026-03-29_College_Graduation_Rate_Selectivity_Analysis/
|
|-- README.md                          <-- You are here
|
|-- ...Report.md                       <-- Start here: the final report
|-- ...Plan.md                         <-- Research blueprint (frozen after planning)
|-- ...Plan_Tasks.md                   <-- Machine-readable task sequence
|-- ....py                             <-- Marimo notebook (all scripts consolidated)
|
|-- STATE.md                           <-- Session state tracker
|-- LEARNINGS.md                       <-- Lessons learned
|
|-- scripts/
|   |-- stage5_fetch/                  <-- Data acquisition (9 scripts)
|   |   |-- 01_fetch-directory.py
|   |   |-- 02_fetch-admissions.py
|   |   |-- 03_fetch-grad-rates.py     <-- Original (failed)
|   |   |-- 03_fetch-grad-rates_a.py   <-- Revision (succeeded)
|   |   |-- 04_fetch-fsa-grants.py     <-- Original (failed: Pell data null)
|   |   |-- 04_fetch-fsa-grants_a.py   <-- ... through _d (5 attempts)
|   |   |-- 04_fetch-fsa-grants_b.py
|   |   |-- 04_fetch-fsa-grants_c.py
|   |   |-- 04_fetch-fsa-grants_d.py   <-- Final success (SFA proxy)
|   |   |-- 05_fetch-enrollment-race.py
|   |   |-- 06_fetch-sfr.py
|   |   |-- 07_fetch-retention.py
|   |   |-- 08_fetch-finance.py
|   |   +-- 09_fetch-sfa-grants.py     <-- Added after Pell data pivot
|   |
|   |-- stage6_clean/                  <-- Data cleaning (8 scripts + revisions)
|   |-- stage7_transform/              <-- Joins and derived variables (4 scripts)
|   |-- stage8_analysis/               <-- Analysis and visualization (13 scripts)
|   |
|   |-- cr/                            <-- Code review / QA scripts (42 scripts)
|   +-- _build_notebook.py             <-- Notebook assembly utility
|
|-- data/
|   |-- raw/                           <-- Downloaded source data (9 parquet files)
|   +-- processed/                     <-- Cleaned and joined data (not in git)
|
|-- output/
|   |-- figures/                       <-- 6 PNG visualizations
|   +-- analysis/                      <-- Analysis result tables (not in git)
|
+-- logs/                              <-- Full session transcripts (JSONL + MD)
```
