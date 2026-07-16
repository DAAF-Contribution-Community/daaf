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

> **Written last, during RV-4 synthesis.** Do not fill in until all in-scope scripts have been processed and the report verification is complete; exact pre-RV-2 exclusions remain separately reported.

**Overall Reproducibility Assessment:** [FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED]

**Scripts in Scope for Execution:** [N] (after [N] exact pre-RV-2 scope-design exclusions)
**Scripts Re-executed:** [N] of [N] in scope
**Scripts Reproduced Successfully:** [N] ([X]% of in-scope scripts)
**Scripts with Deviations:** [N]
**Scripts that Failed:** [N]
**Scripts Requiring Modifications:** [N]
**Scripts Excluded by Frozen-Input Design:** [N] Stage 5 scripts (not executed; acquisition/mirrors not tested)

**Declared Output Artifacts:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Material Report Claims:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Figures:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Key Findings:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Required Comparison Dimensions:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Scope-Design Exclusions:** [N] exact items approved before RV-2 (reported separately; excluded from denominators)

> `FULLY REPRODUCED` requires every in-scope script to be REPRODUCED and every in-scope claim, figure, finding, artifact, and required dimension to be `MATCH`, with zero `DIVERGED` or `NOT DIRECTLY VERIFIED` items and no substantive modifications. Any in-scope evidence gap caps the verdict at `PARTIALLY REPRODUCED`. Only exact exclusions user-approved before RV-2 are removed from denominators; ad hoc skips are not exclusions. Missing or unsupported evidence is never a match.

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

| Artifact | Location | Present / Status |
|----------|----------|------------------|
| Original Report | `original_files/[report_name]` | [Copied/Missing] |
| Original Notebook | `original_files/[notebook_name]` | [Copied/Missing] |
| Original Raw Data | `original_files/data/raw/` | [Copied/Missing/Not present in original] |
| Original Processed Data | `original_files/data/processed/` | [Copied/Missing/Not present in original] |
| Original Analysis Outputs | `original_files/output/analysis/` | [Copied/Missing/Not present in original] |
| Original Figures | `original_files/output/figures/` | [Copied/Missing/Not present in original] |
| Additional Declared Outputs | `original_files/output/[same relative paths]` | [Copied/Missing/N/A — enumerate below] |
| Original Preliminary Notes | `original_files/output/preliminary_notes/` | [Copied/Missing/Not present in original] |
| Decompiled Scripts | `original_files/scripts/` | [Present/Missing] |
| Decompilation Manifest | `original_files/scripts/MANIFEST.md` | [Present/Missing] |
| Path Containment Audit | [JSON output captured in this report or project-local evidence file] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED + exit code] |
| Frozen Raw Pre-RV-2 Hash Inventory | [project-local evidence path / N/A for re-fetch] | [Present/N/A] |
| Frozen Raw Post-RV-2 Hash Inventory | [project-local evidence path / N/A for re-fetch] | [MATCH/DIVERGED/N/A] |
| Original Dockerfile | `original_files/Dockerfile.original` | [Present/Unavailable] |
| RV-3 Verification Findings | `output/preliminary_notes/[date]_rv3_report-verification.md` | [Present/Missing] |
| Reproduction Session Logs | `logs/` | [Present/Missing] |

### Original Artifact Inventory and Copy Verification

> **Populate during RV-1 before RV-2.** Inventory file counts and total sizes in the untouched original project before copying. After copying to `original_files/<same project-relative path>`, verify destination counts and sizes. An absent source is `NOT PRESENT` or `MISSING EVIDENCE`, never `COPIED`. Add one row for every additional declared output artifact beneath the original project's `output/` tree.

| Artifact Class / Declared Relative Path | Original Location | Pre-Copy Files | Pre-Copy Size | Copied Location | Post-Copy Files | Post-Copy Size | Copy Status / Evidence Gap |
|-----------------------------------------|-------------------|----------------|---------------|-----------------|-----------------|----------------|----------------------------|
| `data/raw/` | `[original_project]/data/raw/` | [N/N/A] | [bytes/N/A] | `original_files/data/raw/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `data/processed/` | `[original_project]/data/processed/` | [N/N/A] | [bytes/N/A] | `original_files/data/processed/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `output/analysis/` | `[original_project]/output/analysis/` | [N/N/A] | [bytes/N/A] | `original_files/output/analysis/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `output/figures/` | `[original_project]/output/figures/` | [N/N/A] | [bytes/N/A] | `original_files/output/figures/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `output/[additional/declared_artifact]` | `[original_project]/output/[same path]` | [N/N/A] | [bytes/N/A] | `original_files/output/[same path]` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |

**Frozen raw-data seed:** [Not selected / Seeded reproduction `data/raw/` from `original_files/data/raw/` after copy verification / BLOCKED — frozen raw data absent]

### Frozen Raw-Input Integrity (when selected)

> Frozen mode excludes Stage 5 acquisition scripts by user-confirmed scope design; it does not reproduce acquisition or test mirrors. Capture the exact inventory before downstream RV-2 execution and recompute it afterward. Any changed, added, or missing raw file is a failure requiring investigation.

| Relative Raw Path | Pre-RV-2 Bytes | Pre-RV-2 SHA-256 | Post-RV-2 Bytes | Post-RV-2 SHA-256 | Assessment |
|-------------------|-----------------|------------------|------------------|-------------------|------------|
| `data/raw/[file]` | [bytes] | [hash] | [bytes] | [hash] | [MATCH/DIVERGED] |

**Stage 5 acquisition scope:** [Re-fetch — in scope and executed / Frozen inputs — exact Stage 5 script list EXCLUDED BY USER-CONFIRMED FROZEN-INPUT DESIGN]
**Acquisition reproducibility:** [Tested in re-fetch mode / Out of scope in frozen mode; no mirror claim]

### Evidence Coverage Summary

> Update during RV-1 as evidence is inventoried, after every RV-2 script, after RV-3 claim verification, and during RV-4 rollup. Counts are derived from the inventory and result tables, not recalled. User exclusions count as out of scope only when confirmed and recorded before RV-2.

| Evidence Unit | In Scope | Directly Verified | Matched | Diverged | NOT DIRECTLY VERIFIED | Excluded Before RV-2 |
|---------------|----------|-------------------|---------|----------|-----------------------|----------------------|
| Declared output artifacts | [N] | [N] | [N] | [N] | [N] | [N] |
| Material Report claims | [N] | [N] | [N] | [N] | [N] | [N] |
| Figures | [N] | [N] | [N] | [N] | [N] | [N] |
| Key findings | [N] | [N] | [N] | [N] | [N] | [N] |
| Required per-script dimensions | [N] | [N] | [N] | [N] | [N] | [N] |

### Script Inventory

| # | Step | Script | Stage | Type | Original Output | Repro Status |
|---|------|--------|-------|------|-----------------|--------------|
| 1 | [step] | [script_name] | [5/6/7/8] | [fetch/clean/transform/analysis/viz] | [output_path] | [PENDING/REPRODUCED/DIVERGED/FAILED/MODIFIED/EXCLUDED BY USER-CONFIRMED FROZEN-INPUT DESIGN] |

**Status Definitions:**
- **PENDING** — In scope but not yet re-executed
- **REPRODUCED** — Re-execution succeeded and all directly evidenced comparison dimensions matched within tolerance; any unavailable dimensions remain explicitly `NOT DIRECTLY VERIFIED` rather than inferred as matches
- **DIVERGED** — Re-execution completed but output differs from original
- **FAILED** — Re-execution produced an error; script did not complete
- **MODIFIED** — Script required changes to run; modifications documented below
- **EXCLUDED BY USER-CONFIRMED FROZEN-INPUT DESIGN** — Stage 5 acquisition script was removed from scope by the user-confirmed frozen-input design before RV-2. It was not run and must never be counted as REPRODUCED, DIVERGED, FAILED, or silently skipped.

### Scope Decisions

> **Confirmed at mode confirmation AND after RV-1 inventory.**

| Decision | User Choice | Rationale |
|----------|-------------|-----------|
| Re-fetch data from mirrors? | [Yes — execute Stage 5 / No — frozen inputs, exclude Stage 5 by design] | [Why; if No, confirm frozen seed + pre-hashes and state acquisition/mirrors are out of scope] |
| Methodological review depth | [Light / Full] | [Why] |
| Scripts excluded by scope design before RV-2 | [None / exact list with reasons, including Stage 5 under frozen mode] | [User confirmation and why; these alone leave denominators] |
| Declared outputs excluded before RV-2 | [None / exact project-relative paths with reasons] | [User confirmation and why] |
| Material Report claims excluded before RV-2 | [None / exact claims/locations with reasons] | [User confirmation and why] |

### Infrastructure Normalizations

> **Applied during RV-1 setup** by running `normalize_project_dir.py` on all decompiled scripts in batch. Infrastructure normalizations are mechanical path/environment adjustments that make scripts executable in the reproduction project. They do not affect reproduction status — a script requiring only infrastructure normalizations retains REPRODUCED status. Paste the normalizer's Markdown table output below.

| File | Original Value | Normalized Value | Type |
|------|----------------|------------------|------|
| `stage5_fetch/01_fetch-data.py` | `PROJECT_DIR = Path("/daaf/research/original_project/")` | `PROJECT_DIR = Path("/daaf/research/reproduction_project/")` | PROJECT_DIR Path |
| `stage5_fetch/01_fetch-data.R` | `PROJECT_DIR <- file.path("/daaf", "research", "original_project")` | `PROJECT_DIR <- file.path("/daaf/research/reproduction_project")` | PROJECT_DIR file.path |

### Mandatory Path Containment Audit

**Utility:** `scripts/audit_reproduction_paths.py`
**Invocation:** `python3 /daaf/scripts/audit_reproduction_paths.py [scripts_root] [exact_original_root] [expected_reproduction_root] [--exclude exact/canonical/relative-script.py] [--exclude another/script.R]`
**Exit code / overall:** [0 MATCH / 1 DIVERGED / 2 NOT DIRECTLY VERIFIED]
**RV-1 gate:** [PASSED — global exit 0 MATCH and every dispatched script has `scope: IN_SCOPE` + `assessment: MATCH` / BLOCKED — state the global or per-file failure]
**In-scope file assessments:** [List/cite deterministic `file_assessments`; every dispatched script must be MATCH]
**In-scope audit issues:** [None required before RV-2]
**Excluded files and excluded issues:** [List `scope.excluded_files` and `excluded_issues` separately; excluded files never count as matches]
**Informational historical-log residue:** [List `ORIGINAL_ROOT_LOG_RESIDUE` from `informational_evidence`, or None; it is not a failure]
**Bounded assurance:** MATCH establishes only that the exact original-root string is absent from executable source before each in-scope script's unique canonical `# EXECUTION LOG` boundary and that every in-scope supported `.py`/uppercase `.R` script has one unique statically resolvable canonical `PROJECT_DIR` assignment equal to the reproduction root. Multiple canonical boundaries fail closed. Exact original-root residue after the unique boundary is informational immutable provenance, and arbitrary dynamically constructed paths are not proven safe.

```json
[paste deterministic audit JSON, including file_assessments, excluded_issues, and informational_evidence]
```

### Comparison Standards

> **Adjudication standards for RV-2 dimensions supported by evidence.** `compare_execution_logs.py` is log-metric-only: it aligns metrics by normalized identity and stable context rather than position, and returns 0 only for `CONSISTENT`, 1 for `DIVERGED`, 2 for invalid invocation or input read/parse failure, and 3 for `INCOMPLETE`/`INCONCLUSIVE`. Exit 3 is `NOT DIRECTLY VERIFIED` evidence, never success. For supported artifacts, run `compare_reproduction_artifacts.py` and preserve its deterministic JSON/per-dimension result. Artifact-helper exit semantics are load-bearing: 0 `MATCH`, 1 `DIVERGED`, 2 invalid/unsupported invocation, 3 `NOT DIRECTLY VERIFIED`. Exit 2 requires a corrected invocation or a separate evidence path; exit 3 is an evidence gap. Neither is a match. Figures use side-by-side Read-tool review. Persisted tables/models use a defined inspectable representation or remain `NOT DIRECTLY VERIFIED`.

| Metric / Artifact | Tolerance / Tool | Notes |
|-------------------|------------------|-------|
| Log metrics printed in both logs | `compare_execution_logs.py` | Identity/context alignment, not position; never generalize `CONSISTENT` to artifact equality; exit 3 is NOT DIRECTLY VERIFIED |
| Parquet pre-materialization size | 512 MiB per input (`--max-input-bytes 536870912`) | Default; exceedance returns exit 3 before full materialization |
| Parquet pre-materialization rows | 1,000,000 per input (`--max-rows 1000000`) | Default; metadata exceedance returns exit 3 before full materialization |
| Tolerant candidate pairs | 1,000,000 (`--max-pair-comparisons 1000000`) | Default; exact-key/cardinality divergence is decided first; otherwise exceedance returns exit 3 |
| Parquet schema | Exact ordered names and dtypes | `compare_reproduction_artifacts.py`; column order is significant |
| Parquet shape/null counts | Exact | Row count, column count, null counts |
| Supported Parquet scalar content | Exact except float tolerance | Occurrence-aware, order-independent rows; duplicate assessment follows actual verification; nested/unsupported/NaN/excess tolerant work is `NOT DIRECTLY VERIFIED` |
| Float values | 1e-6 relative, zero absolute tolerance | Per artifact helper contract |
| String/integer/boolean/temporal values | Exact | Per artifact helper contract |
| Exact-byte artifact | Size + SHA-256 exact | Proves byte identity only, not semantic equivalence beyond bytes |
| Persisted tables/models | Defined inspectable saved representation | Otherwise `NOT DIRECTLY VERIFIED`; opaque models are excluded from helper |
| Timestamps/file paths in logs | Expected to differ | Cosmetic only when not part of a required substantive metric |
| Figures | Side-by-side Read-tool visual review | Helper excludes figures; minor anti-aliasing/font differences may be cosmetic |

---

## Per-Script Reproduction Results

> **Updated incrementally during RV-2.** Each script gets its own section immediately after re-execution. Do NOT batch these — update the report after every single script.

### Script [#]: [script_name]

**Stage:** [5/6/7/8] | **Step:** [N.N] | **Type:** [fetch/clean/transform/analysis/viz]

#### Execution Comparison

| Dimension | Original | Reproduced | Evidence Source / JSON Dimension | Assessment |
|-----------|----------|------------|----------------------------------|------------|
| Exit code | [0/1] | [0/1] | [Both execution logs] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Output rows | [N] | [N] | [Both logs / artifact helper `row_count`] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Output columns | [N] | [N] | [Both logs / artifact helper `column_count`] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Parquet schema/content | [summary/path] | [summary/path] | [`compare_reproduction_artifacts.py` JSON: schema/null/value/duplicate dimensions; helper exit code] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Key statistics | [summary] | [summary] | [Both logs / inspectable persisted representation] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Declared artifact: [path/type] | [path/status] | [path/status] | [Artifact-helper JSON / visual Read review / defined saved representation / unavailable] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |

> Add one **Declared artifact** row for every output the script declares. Preserve artifact-helper JSON and its exit code for each supported Parquet/exact pair. Compare PNGs visually. Compare tables/models through a defined inspectable saved representation; opaque models remain `NOT DIRECTLY VERIFIED`. Exact-byte `MATCH` means byte identity only. Never infer a match from successful execution, another matching dimension, or a log-helper summary.

#### Checkpoint Comparison

| Checkpoint | Original Result | Reproduced Result | Evidence Source | Assessment |
|------------|-----------------|-------------------|-----------------|------------|
| [CP1/CP2/CP3/CP4] | [PASSED/FAILED + key metrics] | [PASSED/FAILED + key metrics] | [Both execution logs / unavailable] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |

#### Deviations

> If status is REPRODUCED with no deviations, write "None — all directly evidenced comparison dimensions match within tolerance." List any `NOT DIRECTLY VERIFIED` dimensions separately; do not describe them as matches.

[Description of any differences observed. Include: what differs, magnitude of difference, likely cause (e.g., floating-point ordering, data source update, timestamp difference, random seed), and whether the deviation is substantive or cosmetic.]

#### Modifications Required

> If no modifications were needed, write "None — original script executed successfully."
> **If ANY modification was required, this must be prominently flagged.** Each `_repro_a`/`_repro_b` revision must begin from a clean, log-free source (or have any inherited log stripped and verified absent) before fixes and one execution. Never copy and rerun the just-failed, log-appended file unchanged. Modifications undermine reproduction fidelity.

- **Modification type:** [Infrastructure / Substantive / None]
- **What was changed:** [exact description]
- **Why it was necessary:** [root cause]
- **Impact on output:** [whether the change could affect results]
- **Modified script location:** `scripts/repro/[script_name]`
- **Version suffix:** [_repro_a.py / _repro_b.py or _repro_a.R / _repro_b.R, as applicable]

#### Methodological Notes

> Brief observations about the analytical approach in this script. Concerns with severity >= NOTABLE should also be added to the Methodological Concerns Log above.

[Observations, or "No concerns noted."]

---

## Report Verification (RV-3)

> **Completed after all in-scope scripts are processed.** Cross-references specific claims, statistics, and figures from the original Report against the reproduced outputs; exact pre-RV-2 exclusions remain outside the denominator and are reported separately.

### Quantitative Claims

| # | Report Claim | Report Location | Original Value | Reproduced Value | Evidence Source | Assessment | Notes |
|---|-------------|-----------------|----------------|------------------|-----------------|------------|-------|
| 1 | [Specific stat or finding cited in Report] | [Section, paragraph] | [value] | [value from re-run] | [both logs / helper JSON dimension / saved representation] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] | [reason/evidence gap] |

### Figure Verification

| # | Figure | Report Location | Original Source Script | Original/Reproduced Evidence | Assessment | Notes |
|---|--------|-----------------|------------------------|------------------------------|------------|-------|
| 1 | [figure_name.png] | [Section] | [script_name] | [both paths viewed / missing side] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] | [visual evidence/cosmetic differences] |

### Findings Verification

> For each key finding, use MATCH only when direct reproduced evidence supports the same conclusion, DIVERGED when it conflicts, and NOT DIRECTLY VERIFIED when required evidence is missing or unsupported.

| # | Finding | Report Section | Evidence Source | Assessment | Confidence | Notes |
|---|---------|---------------|-----------------|------------|------------|-------|
| 1 | [Finding statement] | [Section] | [claim/artifact/figure evidence] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] | [HIGH/MEDIUM/LOW] | [explanation] |

### Report Verification Summary

**Claims:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Figures:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Findings:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Declared artifacts:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Required dimensions:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Scope-design exclusions:** [N] exact pre-RV-2 exclusions, listed separately

[Brief narrative: Are the Report's conclusions substantiated by the reproduction? Any caveats?]

---

## Reproduction Environment

| Field | Value |
|-------|-------|
| **DAAF Version** | [git commit hash] |
| **Session Model ID** | [Model driving the orchestrator/main session at reproduction start — record the runtime value, e.g., claude-opus-4-8[1m]] |
| **Subagent Model Tiers** | [Distinct specialist model IDs by tier used during reproduction (re-execution, debugging, verification) — from agent frontmatter defaults plus any per-dispatch overrides. Record resolved IDs where known, or the tier alias + session date otherwise — e.g., "opus tier: claude-opus-4-8[1m]; sonnet tier: claude-sonnet-4-5". Record BOTH session and subagent models of the reproduction run; the original run's models are separately captured from its Report's AI Disclosure.] |
| **Reproduction Date** | [YYYY-MM-DD] |
| **Original Analysis Date** | [YYYY-MM-DD] |
| **Execution Language** | [Python or R] |
| **Python Runtime** | [observed version, or N/A for R-only project] |
| **Marimo Version** | [observed installed version, or N/A] |
| **R Runtime** | [observed version, or N/A for Python-only project] |
| **Quarto CLI Version** | [observed version, or N/A] |
| **R Repository/Snapshot Metadata** | [observed repository URLs/snapshot metadata / unavailable / N/A] |
| **Imported Package Inventory Evidence** | [`scripts/repro_checks/[diagnostic].py/.R` + appended `run_with_capture.sh` log, read-only package listing, or equivalent] |

### Environment Compatibility Assessment

> **Populated during RV-1 with language-aware observed evidence.** Python comparison covers the runtime, marimo, and installed versions of packages imported by scripts. R comparison covers the R runtime, Quarto, repository/snapshot metadata, and `installed.packages()` versions for imported packages. Unversioned original `install.packages()` lines and snapshot dates do not prove exact package versions; mark original values UNKNOWN / NOT DIRECTLY VERIFIED rather than synthesizing a complete table from Python-style pins. Diagnostic scripts are verification instrumentation: store them under project `scripts/repro_checks/`, execute them through `run_with_capture.sh`, and retain their appended logs.

**Original DAAF Version:** [commit hash from Report's AI Disclosure, e.g., `abc1234`]
**Original DAAF Release:** [semver if identifiable, e.g., `v2.1.0`, or `—` if not mapped to a release]
**Current DAAF Version:** [current commit hash]
**Current DAAF Release:** [current semver if identifiable]
**Original Dockerfile Source:** [URL used to fetch, e.g., `https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/{hash}/Dockerfile`, or `unavailable — see notes`]

**Overall Compatibility:** [COMPATIBLE / MINOR DIFFERENCES / SIGNIFICANT DIFFERENCES / UNKNOWN]

| Runtime / Tool / Imported Package | Original Version Evidence | Current Observed Version | Status | Risk / Evidence Gap |
|-----------------------------------|---------------------------|--------------------------|--------|---------------------|
| [Python/R/Quarto/marimo/package] | [version + source / UNKNOWN] | [observed version] | [MATCH/PATCH/MINOR/MAJOR/ADDED/REMOVED/UNKNOWN/NOT DIRECTLY VERIFIED] | [—/description] |

**Status Definitions:**
- **MATCH**: Identical version — no risk
- **PATCH**: Patch version differs (x.y.Z) — minimal risk, bug fixes only
- **MINOR**: Minor version differs (x.Y.z) — low-moderate risk, new features may change defaults
- **MAJOR**: Major version differs (X.y.z) — high risk, breaking changes likely
- **ADDED**: Package present in current environment but absent in original — no direct risk unless it shadows behavior
- **REMOVED**: Package present in original environment but absent in current — high risk, scripts may fail
- **UNKNOWN / NOT DIRECTLY VERIFIED**: Original evidence does not establish an exact version or current installed evidence is unavailable; do not infer parity

**Compatibility Summary:**
- Packages compared: [N]
- MATCH: [N] | PATCH: [N] | MINOR: [N] | MAJOR: [N] | ADDED: [N] | REMOVED: [N]

**User Decision:** [Proceed with current environment / Rebuilt to match original / N/A — environments compatible]

**Impact on Reproduction Assessment:**
[Statement about how environment differences should be factored into interpretation of deviations. E.g., "Environment differences are minimal and unlikely to cause deviations" or "Significant version differences in polars and statsmodels may explain observed deviations in transform and analysis scripts — deviations in scripts using these packages should be interpreted with this context."]

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
| `original_files/output/figures/` | Original figures (copied) | RV-1 |
| `original_files/output/preliminary_notes/` | Original discovery findings (copied, if present) | RV-1 |
| `original_files/scripts/[...]` | Decompiled scripts (from notebook) | RV-1 |
| `original_files/Dockerfile.original` | Original Dockerfile (fetched from public repo at original commit) | RV-1 |
| `scripts/repro/[...]` | Re-executed scripts (with new logs) | RV-2 |
| `scripts/repro_checks/[...]` | Environment/evidence diagnostics (with appended logs, when needed) | RV-1/RV-2 |
| `output/figures/[...]` | Reproduced figures (generated) | RV-2 |
| `output/preliminary_notes/[date]_rv3_report-verification.md` | Lossless data-verifier return (persisted) | RV-3 |
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

These tolerances apply only to direct evidence. The log helper covers shared printed metrics only, aligns them by identity/context rather than position, and returns 0 CONSISTENT only, 1 DIVERGED, 2 invalid/read failure, or 3 INCOMPLETE/INCONCLUSIVE; exit 3 is NOT DIRECTLY VERIFIED, never success. The artifact helper covers supported Parquet and intentional exact-byte pairs, emits deterministic JSON, and uses exit 0 MATCH, 1 DIVERGED, 2 invalid/unsupported, 3 NOT DIRECTLY VERIFIED. Preserve its per-dimension evidence; exit 2 requires correction or a separate evidence path, exit 3 is an evidence gap, and neither is a match. Its default pre-materialization limits are 536870912 bytes and 1000000 rows per input, with at most 1000000 tolerant candidate pairs; bound exceedance returns exit 3 before full materialization or unbounded tolerant matching. Exact-key/cardinality divergence is established before the pair-work limit, and duplicate assessment follows what was actually verified. Figures and inspectable saved model/table representations use separate review paths:

| Metric | Exact Match Required? | Tolerance |
|--------|----------------------|-----------|
| Input compressed size | N/A | Maximum 536870912 bytes per Parquet input before full materialization |
| Input row count | N/A | Maximum 1000000 rows per Parquet input before full materialization |
| Tolerant candidate pairs | N/A | Maximum 1000000 after exact-key/cardinality checks |
| Row count | Yes | 0 (must match exactly) |
| Column count | Yes | 0 |
| Column names | Yes | 0 |
| Column dtypes | Yes | 0 |
| Integer values | Yes | 0 |
| Float values | No | 1e-6 relative tolerance |
| String values | Yes | 0 |
| Null counts | Yes | 0 |
| Row ordering | No | Artifact helper uses occurrence-aware order-independent comparison |
| Unsupported/nested Parquet or NaN | N/A | `NOT DIRECTLY VERIFIED`; no silent value match |
| Exact-byte files | Yes | Size + SHA-256; proves byte identity only |
| Timestamps in logs | No | Expected to differ |
| File paths in logs | No | Expected to differ if project moved |
| Figures | No | Side-by-side visual inspection via Read tool; artifact helper excludes them |

### Substantive vs. Cosmetic Deviations

- **Cosmetic:** Timestamps, file paths, floating-point display rounding, row ordering. These are expected and do not affect reproducibility assessment.
- **Substantive:** Different row counts, different column values, missing data, changed statistical results, different figures. These indicate genuine reproducibility issues.

Only substantive deviations affect the overall reproducibility assessment.
