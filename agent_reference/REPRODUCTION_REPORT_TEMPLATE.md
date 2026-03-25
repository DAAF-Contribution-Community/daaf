# Reproduction Report Template

This template defines the central artifact for Reproducibility Verification mode. It serves three purposes simultaneously: (1) progress tracker during re-execution, (2) comparison log capturing all deviations, and (3) final deliverable summarizing reproducibility findings.

**Update discipline:** The orchestrator and its subagents update this report **iteratively and frequently** — after every script re-execution, not in batch. The report is the running record of truth for the reproduction attempt.

---

## Template

Copy this template to `Reproduction_Report.md` in the reproduction project folder at RV-1 setup.

```markdown
# Reproduction Report: [Original Project Title]

**Reproduction Date:** YYYY-MM-DD
**Original Analysis Date:** [original date prefix]
**Original Project:** `research/[original_folder]/`
**Reproduction Project:** `research/[reproduction_folder]/`

---

## Executive Summary

> **Written last, during RV-4 synthesis.** Do not fill in until all scripts have been re-executed and the report verification is complete.

**Overall Reproducibility Assessment:** [FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED]

**Scripts Re-executed:** [N] of [N]
**Scripts Reproduced Successfully:** [N] ([X]%)
**Scripts with Deviations:** [N]
**Scripts that Failed:** [N]
**Scripts Requiring Modifications:** [N]

**Summary of Findings:**
[3-5 sentences: What reproduced cleanly, what diverged and why, what failed and why. Written in plain language for a non-technical reviewer.]

**Summary of Methodological Concerns:**
[2-3 sentences: Key methodological observations surfaced during reproduction. These are concerns about the *analytical approach itself*, not about whether the code ran.]

---

## Methodological Concerns

> **Accumulated during RV-2** as the reproduction agent encounters each script. **Synthesized during RV-4.** Each concern is tagged with the script that prompted it and a severity assessment.

### Concern Severity Scale

| Severity | Meaning | Action Needed |
|----------|---------|---------------|
| **CRITICAL** | May invalidate one or more findings | Requires investigation before results are trusted |
| **NOTABLE** | Could affect interpretation or generalizability | Should be disclosed in limitations |
| **MINOR** | Stylistic or best-practice observation | No action required; noted for completeness |

### Concerns Log

| # | Script | Severity | Concern | Detail |
|---|--------|----------|---------|--------|
| 1 | [script_name] | [CRITICAL/NOTABLE/MINOR] | [One-line concern title] | [Explanation: what was observed, why it matters, what the alternative approach would be] |

### Synthesis of Methodological Concerns

> **Written during RV-4.** Group related concerns, assess their collective impact on the analysis conclusions, and provide an overall methodological assessment.

[Narrative synthesis here]

---

## Reproduction Inventory

> **Populated during RV-1** from notebook decompilation. Updated with status during RV-2 as each script is re-executed.

### Source Artifacts

| Artifact | Location | Present |
|----------|----------|---------|
| Original Report | `original_files/[report_name]` | [Yes/No] |
| Original Notebook | `original_files/[notebook_name]` | [Yes/No] |
| Decompiled Scripts | `original_files/scripts/` | [Yes/No] |
| Decompilation Manifest | `original_files/scripts/MANIFEST.md` | [Yes/No] |
| Reproduction Session Logs | `logs/` | [Yes/No] |

### Script Inventory

| # | Step | Script | Stage | Type | Original Output | Repro Status |
|---|------|--------|-------|------|-----------------|--------------|
| 1 | [step] | [script_name] | [5/6/7/8] | [fetch/clean/transform/analysis/viz] | [output_path] | [PENDING/REPRODUCED/DIVERGED/FAILED/MODIFIED] |

**Status Definitions:**
- **PENDING** — Not yet re-executed
- **REPRODUCED** — Re-execution produced matching output (within tolerance)
- **DIVERGED** — Re-execution completed but output differs from original
- **FAILED** — Re-execution produced an error; script did not complete
- **MODIFIED** — Script required changes to run; modifications documented below

### Scope Decisions

> **Confirmed at mode confirmation AND after RV-1 inventory.**

| Decision | User Choice | Rationale |
|----------|-------------|-----------|
| Re-fetch data from mirrors? | [Yes / No — use existing data] | [Why] |
| Methodological review depth | [Light / Full] | [Why] |
| Scripts excluded from reproduction | [None / list with reasons] | [Why] |

### Infrastructure Normalizations

> **Applied during RV-1 extraction.** Infrastructure normalizations are mechanical path/environment adjustments that make scripts executable in the reproduction project. They do not affect reproduction status — a script requiring only infrastructure normalizations retains REPRODUCED status.

| File | Original Value | Normalized Value | Type |
|------|----------------|------------------|------|
| [script_name] | `PROJECT_DIR = Path("/daaf/research/original_project/")` | `PROJECT_DIR = Path("/daaf/research/reproduction_project/")` | PROJECT_DIR path |

### Comparison Standards

> **Reference tolerances for RV-2 output comparison.** Apply these when classifying deviations as substantive or cosmetic.

| Metric | Tolerance | Notes |
|--------|-----------|-------|
| Row count | Exact match | 0 difference required |
| Column count | Exact match | 0 difference required |
| Float values | 1e-6 relative tolerance | Minor floating-point variance is expected |
| String values | Exact match | 0 difference required |
| Integer values | Exact match | 0 difference required |
| Timestamps in logs | Expected to differ | Cosmetic — do not flag |
| File paths in logs | Expected to differ | Cosmetic — do not flag |
| Figures | Visual inspection via Read tool | Minor rendering differences (anti-aliasing, font rendering) are expected |

---

## Per-Script Reproduction Results

> **Updated incrementally during RV-2.** Each script gets its own section immediately after re-execution. Do NOT batch these — update the report after every single script.

### Script [#]: [script_name]

**Stage:** [5/6/7/8] | **Step:** [N.N] | **Type:** [fetch/clean/transform/analysis/viz]

#### Execution Comparison

| Metric | Original | Reproduced | Match? |
|--------|----------|------------|--------|
| Exit code | [0/1] | [0/1] | [Yes/No] |
| Output rows | [N] | [N] | [Yes/No] |
| Output columns | [N] | [N] | [Yes/No] |
| Schema match | — | — | [Yes/No] |
| Key statistics | [summary] | [summary] | [Yes/No/Within tolerance] |

#### Checkpoint Comparison

| Checkpoint | Original Result | Reproduced Result | Match? |
|------------|----------------|-------------------|--------|
| [CP1/CP2/CP3/CP4] | [PASSED/FAILED + key metrics] | [PASSED/FAILED + key metrics] | [Yes/No] |

#### Deviations

> If status is REPRODUCED with no deviations, write "None — output matches original."

[Description of any differences observed. Include: what differs, magnitude of difference, likely cause (e.g., floating-point ordering, data source update, timestamp difference, random seed), and whether the deviation is substantive or cosmetic.]

#### Modifications Required

> If no modifications were needed, write "None — original script executed successfully."
> **If ANY modification was required, this must be prominently flagged.** Modifications undermine reproduction fidelity.

- **Modification type:** [Infrastructure / Substantive / None]
- **What was changed:** [exact description]
- **Why it was necessary:** [root cause]
- **Impact on output:** [whether the change could affect results]
- **Modified script location:** `scripts/repro/[script_name]`
- **Version suffix:** [_repro_a.py, etc.]

#### Methodological Notes

> Brief observations about the analytical approach in this script. Concerns with severity >= NOTABLE should also be added to the Methodological Concerns Log above.

[Observations, or "No concerns noted."]

---

## Report Verification (RV-3)

> **Completed after all scripts are re-executed.** Cross-references specific claims, statistics, and figures from the original Report against the reproduced outputs.

### Quantitative Claims

| # | Report Claim | Report Location | Original Value | Reproduced Value | Match? | Notes |
|---|-------------|-----------------|----------------|------------------|--------|-------|
| 1 | [Specific stat or finding cited in Report] | [Section, paragraph] | [value] | [value from re-run] | [Yes/No/Approx] | [If no: magnitude and likely cause] |

### Figure Verification

| # | Figure | Report Location | Original Source Script | Reproduced? | Visual Match? | Notes |
|---|--------|-----------------|----------------------|-------------|---------------|-------|
| 1 | [figure_name.png] | [Section] | [script_name] | [Yes/No] | [Yes/No/Approximate] | [notes] |

### Findings Verification

> For each key finding in the original Report, assess whether the reproduced data supports the same conclusion.

| # | Finding | Report Section | Supported by Reproduced Data? | Confidence | Notes |
|---|---------|---------------|-------------------------------|------------|-------|
| 1 | [Finding statement] | [Section] | [Yes / Partially / No] | [HIGH/MEDIUM/LOW] | [explanation] |

### Report Verification Summary

**Claims verified:** [N] of [N]
**Claims matching:** [N] ([X]%)
**Figures reproduced:** [N] of [N]
**Findings supported:** [N] of [N]

[Brief narrative: Are the Report's conclusions substantiated by the reproduction? Any caveats?]

---

## Reproduction Environment

| Field | Value |
|-------|-------|
| **DAAF Version** | [git commit hash] |
| **Model ID** | [e.g., claude-opus-4-6] |
| **Reproduction Date** | [YYYY-MM-DD] |
| **Original Analysis Date** | [YYYY-MM-DD] |
| **Python Version** | [e.g., 3.12] |
| **Key Packages** | [polars version, plotnine version, etc.] |

---

## Deviation Log

> **Running log of ALL deviations**, consolidated from per-script sections for easy scanning. Each row is added as deviations are discovered during RV-2.

| # | Script | Deviation Type | Description | Substantive? | Likely Cause |
|---|--------|---------------|-------------|--------------|--------------|
| 1 | [name] | [Output difference / Runtime error / Required modification / Data change] | [brief] | [Yes/No] | [cause] |

**Deviation Type Definitions:**
- **Output difference** — Script ran but produced different numerical results
- **Runtime error** — Script failed to execute (dependency, path, API change, etc.)
- **Required modification** — Script needed code changes to run at all
- **Data change** — Upstream data source returned different data than original fetch

---

## Files Created During Reproduction

| File | Type | Stage |
|------|------|-------|
| `original_files/[report]` | Original Report (copied) | RV-1 |
| `original_files/[notebook]` | Original Notebook (copied) | RV-1 |
| `original_files/scripts/[...]` | Decompiled scripts (from notebook) | RV-1 |
| `scripts/repro/[...]` | Re-executed scripts (with new logs) | RV-2 |
| `Reproduction_Report.md` | This document | RV-1 |

---

## Session Continuity

> The Reproduction Report is the **sole session state document** for Reproducibility Verification mode (no separate STATE.md). This section MUST be updated after every script re-execution, at every stage transition, and before any session break.

### Current Position

| Field | Value |
|-------|-------|
| **Current Stage** | [RV-1 / RV-2 / RV-3 / RV-4] |
| **Last Script Completed** | [#N: script_name] |
| **Next Script** | [#N+1: script_name] |
| **Scripts Remaining** | [N] |

### Error Tracking

| Metric | Count | Notes |
|--------|-------|-------|
| Scripts FAILED | [N] | [list if any] |
| Scripts MODIFIED | [N] | [list if any] |
| Debugger dispatches | [N] of 3 max | [status] |

### Runtime Notes

> Observations, decisions, or issues encountered during reproduction that affect session continuity.

| # | Stage | Note |
|---|-------|------|
| 1 | [RV-N] | [observation or decision] |

### Restart Prompt

> Copy this prompt after `/clear` to resume with fresh context.

Resume the reproduction of [Original Project Title]. Reproduction Report: `[exact path]`. Currently at [stage] — last completed [description], next step is [description].
```

---

## Usage Guidelines

### When to Create

Create `Reproduction_Report.md` during **RV-1 (Intake & Setup)** after copying original artifacts and running the decompiler.

### Update Cadence

This report must be updated **after every single script re-execution** during RV-2. Do not batch updates. The report is both a live progress tracker and a final deliverable — it must be current at all times.

**After each script re-execution:**
1. Update the Script Inventory table (Repro Status column)
2. Fill in the Per-Script Reproduction Results section for that script
3. Add any deviations to the Deviation Log
4. Add any methodological concerns to the Concerns Log

**After RV-3 (Report Verification):**
5. Fill in all Report Verification tables

**During RV-4 (Synthesis):**
6. Write the Executive Summary
7. Write the Methodological Concerns Synthesis
8. Write the Report Verification Summary narrative

### Comparison Tolerances

When comparing original vs. reproduced outputs, apply these tolerances:

| Metric | Exact Match Required? | Tolerance |
|--------|----------------------|-----------|
| Row count | Yes | 0 (must match exactly) |
| Column count | Yes | 0 |
| Column names | Yes | 0 |
| Column dtypes | Yes | 0 |
| Integer values | Yes | 0 |
| Float values | No | 1e-6 relative tolerance |
| String values | Yes | 0 |
| Null counts | Yes | 0 |
| Row ordering | No | Order-independent comparison acceptable |
| Timestamps in logs | No | Expected to differ |
| File paths in logs | No | Expected to differ if project moved |
| Figure pixel comparison | No | Visual inspection sufficient |

### Substantive vs. Cosmetic Deviations

- **Cosmetic:** Timestamps, file paths, floating-point display rounding, row ordering. These are expected and do not affect reproducibility assessment.
- **Substantive:** Different row counts, different column values, missing data, changed statistical results, different figures. These indicate genuine reproducibility issues.

Only substantive deviations affect the overall reproducibility assessment.
