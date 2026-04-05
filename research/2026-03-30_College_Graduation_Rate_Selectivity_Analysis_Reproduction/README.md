# Sample Project: Reproducibility Verification of the College Graduation Rate & Selectivity Analysis

This is a **sample Reproducibility Verification project** included with DAAF to show what it looks like when DAAF independently re-executes and verifies a completed analysis. It was conducted using DAAF's [Reproducibility Verification mode](../../user_reference/02_understanding_daaf.md#reproducibility-verification-trust-but-verify), which takes a finished Full Pipeline project, decompiles its notebook into individual scripts, re-runs every one of them, compares outputs against the originals, and cross-references the Report's quantitative claims against the reproduced data.

The analysis being reproduced here is the [College Graduation Rate & Selectivity Analysis](../2026-03-29_College_Graduation_Rate_Selectivity_Analysis/) -- see that project's [README](../2026-03-29_College_Graduation_Rate_Selectivity_Analysis/README.md) for a full walkthrough of the original.

---

## How It Started

The reproduction was initiated the day after the original analysis was completed, with a single prompt:

> *I'd like to run a reproducibility verification run of /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis*

DAAF classified this as a Reproducibility Verification and asked the researcher to confirm two scope decisions before beginning: (1) whether to re-fetch data from mirrors or use the frozen data from the original project, and (2) how deep the methodological review should be. The researcher responded:

> *Let's just use frozen data today. 2. Just light, this is fine*

These two choices meant:

1. **Re-fetch data?** No -- use the existing frozen data from the original project, so any differences would reflect code behavior, not data source changes
2. **Methodological review depth?** Light -- focus on mechanical reproducibility rather than scrutinizing analytical choices

You can see these decisions recorded in the [Reproduction Report's Scope Decisions table](Reproduction_Report.md#scope-decisions).

---

## Where It Goes: Start With the Reproduction Report

The central artifact of a Reproducibility Verification project is the **Reproduction Report**:

**[Reproduction Report](Reproduction_Report.md)**

This document serves as both the final deliverable and the session state tracker (unlike Full Pipeline projects, which use separate Report and STATE.md files). It records every script's re-execution results, compares all quantitative claims from the original Report against the reproduced data, and provides an overall reproducibility assessment.

**Bottom line: FULLY REPRODUCED.** All 34 scripts were re-executed; 33 reproduced without any modification; 1 required a minor fix for a decompilation artifact (missing variable definitions lost at a notebook cell boundary). All 53 quantitative claims in the original Report matched. All 6 figures were visually confirmed.

Sections worth reading closely:

- [**Executive Summary**](Reproduction_Report.md#executive-summary) -- The overall reproducibility verdict and key statistics
- [**Quantitative Claims**](Reproduction_Report.md#quantitative-claims) -- A table verifying all 53 numerical claims from the original Report against reproduced values, with match status for each
- [**Figure Verification**](Reproduction_Report.md#figure-verification) -- Side-by-side comparison results for all 6 figures
- [**Findings Verification**](Reproduction_Report.md#findings-verification) -- Whether each of the 8 key findings is supported by the reproduced data
- [**Deviation Log**](Reproduction_Report.md#deviation-log) -- The single deviation encountered: script #34 needed 3 missing variable definitions restored after decompilation
- [**Synthesis of Methodological Concerns**](Reproduction_Report.md#synthesis-of-methodological-concerns) -- Notes on what a deeper review *would* examine, even though this light review found no concerns

---

## How It Got There: Understanding the Artifacts

### The Reproduction Process (RV-1 through RV-4)

Reproducibility Verification follows four stages:

| Stage | Name | What Happens |
|-------|------|-------------|
| **RV-1** | Setup | Copy original artifacts, decompile notebook into scripts, normalize paths, set up project structure |
| **RV-2** | Re-execution | Re-run every script, compare outputs against originals, log deviations |
| **RV-3** | Report Verification | Extract all quantitative claims from the original Report and verify each against reproduced execution logs |
| **RV-4** | Synthesis | Write the Executive Summary, synthesize methodological concerns, produce the final Reproduction Report |

### Original Files

**[`original_files/`](original_files/)** -- Read-only copies of artifacts from the original project, preserved as reference points:

- [**Original Report**](original_files/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md) -- The Report being verified against
- [**Original Notebook**](original_files/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py) -- The marimo notebook that was decompiled into individual scripts
- [**Original Figures**](original_files/output/figures/) -- The 6 PNG visualizations for visual comparison
- [**Decompiled Scripts**](original_files/scripts/) -- The 34 individual scripts extracted from the notebook during RV-1

### The MANIFEST

**[MANIFEST.md](original_files/scripts/MANIFEST.md)** -- The decompilation manifest produced during RV-1. Lists all 34 scripts extracted from the notebook with their stage, line counts, and whether they contain execution logs. This is the "table of contents" for the decompiled codebase.

### Re-executed Scripts

**[`scripts/repro/`](scripts/repro/)** -- Contains the 34 re-executed scripts, organized in the same stage structure as the originals:

| Directory | Stage | Scripts |
|-----------|-------|---------|
| [`scripts/repro/stage5_fetch/`](scripts/repro/stage5_fetch/) | Data Fetch | 9 scripts |
| [`scripts/repro/stage6_clean/`](scripts/repro/stage6_clean/) | Data Cleaning | 8 scripts |
| [`scripts/repro/stage7_transform/`](scripts/repro/stage7_transform/) | Transformation | 4 scripts |
| [`scripts/repro/stage8_analysis/`](scripts/repro/stage8_analysis/) | Analysis & Viz | 13 scripts + 1 modified variant |

Each script is a copy of the decompiled original with one infrastructure normalization applied: the `PROJECT_DIR` path is updated to point to the reproduction project directory instead of the original. You can see all path normalizations in the [Infrastructure Normalizations table](Reproduction_Report.md#infrastructure-normalizations).

The single modified script deserves special attention:
- [`13_viz-residual-scatter_b.py`](scripts/repro/stage8_analysis/13_viz-residual-scatter_b.py) -- Failed on re-execution (NameError)
- [`13_viz-residual-scatter_b_repro_a.py`](scripts/repro/stage8_analysis/13_viz-residual-scatter_b_repro_a.py) -- The fixed version, restoring 3 variable definitions (`N_LABELS`, `x_lo`, `x_hi`) that were lost during notebook decompilation at a marimo cell boundary. The fix is documented in [Script #34's results](Reproduction_Report.md#script-34-13_viz-residual-scatter_bpy). The output was identical to the original.

### Reproduced Figures

**[`output/figures/`](output/figures/)** -- The 6 figures as regenerated by the reproduction scripts. These were compared against the [originals](original_files/output/figures/) during RV-3 and confirmed as visually identical (with expected minor rendering differences in file size for 2 of 6 figures).

### Session Logs

**[`logs/`](logs/)** -- Complete session transcripts in both raw JSONL and human-readable Markdown format. Each session gets an orchestrator log and individual subagent logs. This project ran in a single session, producing the full audit trail of every tool call, every agent dispatch, and every decision made during the reproduction. You can trace any verification result back to the exact conversation that produced it.

### Per-Script Results

The heart of the Reproduction Report is the [per-script reproduction results](Reproduction_Report.md#per-script-reproduction-results) section, with 34 detailed entries. Each records:

- Exit code (original vs. reproduced)
- Row count and column count comparison
- Key metrics from the execution log
- Checkpoint validation result
- Any deviations or concerns

Browse a few representative entries to see the level of detail:
- [**Script #1**](Reproduction_Report.md#script-1-01_fetch-directorypy) -- A clean REPRODUCED result with exact row/column matches
- [**Script #12**](Reproduction_Report.md#script-12-03_clean-grad-rates_cpy) -- Shows how non-deterministic group_by ordering produces a cosmetic deviation (different sample unitid) that doesn't affect results
- [**Script #34**](Reproduction_Report.md#script-34-13_viz-residual-scatter_bpy) -- The only MODIFIED script, with full documentation of what changed and why

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Original analysis date | 2026-03-29 |
| Reproduction date | 2026-03-30 |
| Scripts re-executed | 34 of 34 |
| Scripts reproduced without modification | 33 (97.1%) |
| Scripts requiring modification | 1 (decompilation artifact) |
| Quantitative claims verified | 53 of 53 (100%) |
| Figures reproduced | 6 of 6 |
| Findings supported | 8 of 8 |
| Overall assessment | FULLY REPRODUCED |
| Review depth | Light (mechanical reproducibility) |
| Data mode | Frozen (no re-fetch) |

---

## File Structure

```
2026-03-30_College_Graduation_Rate_Selectivity_Analysis_Reproduction/
|
|-- README.md                          <-- You are here
|
|-- Reproduction_Report.md             <-- Start here: the reproduction verdict
|
|-- original_files/                    <-- Read-only copies from original project
|   |-- ...Report.md                   <-- Original report (for claim verification)
|   |-- ....py                         <-- Original notebook (decompiled in RV-1)
|   |-- output/figures/                <-- Original figures (for visual comparison)
|   |   |-- 2026-03-29_actual_vs_predicted.png
|   |   |-- 2026-03-29_boxplot_grad_rate_by_selectivity.png
|   |   |-- 2026-03-29_correlation_heatmap.png
|   |   |-- 2026-03-29_grad_rate_vs_admission_rate.png
|   |   |-- 2026-03-29_heatmap_selectivity_pell.png
|   |   +-- 2026-03-29_sector_comparison.png
|   +-- scripts/                       <-- Decompiled scripts + manifest
|       |-- MANIFEST.md
|       +-- scripts/                   <-- 34 decompiled scripts by stage
|           |-- stage5_fetch/
|           |-- stage6_clean/
|           |-- stage7_transform/
|           +-- stage8_analysis/
|
|-- scripts/
|   +-- repro/                         <-- Re-executed scripts (with new logs)
|       |-- stage5_fetch/              <-- 9 fetch scripts
|       |-- stage6_clean/              <-- 8 clean scripts
|       |-- stage7_transform/          <-- 4 transform scripts
|       +-- stage8_analysis/           <-- 13 scripts + 1 _repro_a variant
|
|-- output/
|   +-- figures/                       <-- Reproduced figures (6 PNGs)
|
+-- logs/                              <-- Full session transcripts (JSONL + MD)
```
