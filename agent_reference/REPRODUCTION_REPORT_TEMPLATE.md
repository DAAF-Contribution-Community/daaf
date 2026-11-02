# Reproduction Report Template

This template defines the central artifact for Reproducibility Verification mode. It serves three purposes simultaneously: (1) progress tracker during re-execution, (2) comparison log capturing all deviations, and (3) final deliverable summarizing reproducibility findings.

**Update discipline:** The orchestrator and its subagents update this report **iteratively and frequently** — after every script re-execution, not in batch. The report is the running record of truth for the reproduction attempt.

---

## Template

Copy this template to `Reproduction_Report.md` in the reproduction project folder at RV-1 setup.

````markdown
# Reproduction Report: [Original Project Title]

**Reproduction Date:** YYYY-MM-DD
**Original Analysis Date:** [original date prefix]
**Original Project:** `research/[original_folder]/`
**Reproduction Project:** `research/[reproduction_folder]/`

---

## Executive Summary

<!-- Agent note (deleted at RV-4): written last, during RV-4 synthesis. Do not fill in until all in-scope scripts have been processed and the report verification is complete; exact pre-RV-2 exclusions remain separately reported. -->

**Overall Reproducibility Assessment:** [FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED]

**Scripts in Scope for Execution:** [N] (after [N] exclusions the researcher approved before re-running began)
**Scripts Re-executed:** [N] of [N] in scope
**Scripts Reproduced Successfully:** [N] ([X]% of in-scope scripts)
**Scripts with Deviations:** [N]
**Scripts that Failed:** [N]
**Scripts Requiring Modifications:** [N]
**Scripts Excluded by Frozen-Input Design:** [N] data-download scripts (not run; data download and mirrors not tested)

**Declared Output Artifacts:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Material Report Claims:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Figures:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Key Findings:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Required Comparison Dimensions:** [N] in scope; MATCH [N]; DIVERGED [N]; `NOT DIRECTLY VERIFIED` [N]
**Scope-Design Exclusions:** [N] exact items approved before re-running began (reported separately; excluded from denominators)

> `FULLY REPRODUCED` requires every in-scope script to be REPRODUCED and every in-scope claim, figure, finding, artifact, and required dimension to be `MATCH`, with zero `DIVERGED` or `NOT DIRECTLY VERIFIED` items and no substantive modifications. Any in-scope evidence gap caps the verdict at `PARTIALLY REPRODUCED`. Only exact exclusions the researcher approved before re-running began are removed from denominators; items skipped later are not exclusions. Missing or unsupported evidence is never a match.

**Summary of Findings:**
[3-5 sentences: What reproduced cleanly, what diverged and why, what failed and why. Written in plain language for a non-technical reviewer.]

**Summary of Methodological Concerns:**
[2-3 sentences: Key methodological observations surfaced during reproduction. These are concerns about the *analytical approach itself*, not about whether the code ran.]

---

## Methodological Concerns

Each concern names the script that prompted it and a severity from the scale below.

<!-- Agent note (deleted at RV-4): accumulated during RV-2 as the reproduction agent encounters each script; synthesized during RV-4. -->

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

<!-- Agent note (deleted at RV-4): written during RV-4. Group related concerns, assess their collective impact on the analysis conclusions, and provide an overall methodological assessment. -->

[Narrative synthesis here]

---

## Reproduction Inventory

<!-- Agent note (deleted at RV-4): populated during RV-1 from notebook decompilation; status updated during RV-2 as each script is re-executed. -->

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
| Frozen Raw-Data Fingerprints Before Re-running | [project-local evidence path / N/A for re-fetch] | [Present/N/A] |
| Frozen Raw-Data Fingerprints After Re-running | [project-local evidence path / N/A for re-fetch] | [MATCH/DIVERGED/N/A] |
| Original Dockerfile | `original_files/Dockerfile.original` | [Present/Unavailable] |
| Report-Claim Verification Findings | `output/preliminary_notes/[date]_rv3_report-verification.md` | [Present/Missing] |
| Reproduction Session Logs | `logs/` | [Present/Missing] |

### Original Artifact Inventory and Copy Verification

<!-- Agent note (deleted at RV-4): populate during RV-1, before RV-2. Inventory file counts and total sizes in the untouched original project before copying. After copying to `original_files/<same project-relative path>`, verify destination counts and sizes. An absent source is `NOT PRESENT` or `MISSING EVIDENCE`, never `COPIED`. Add one row for every additional declared output artifact beneath the original project's `output/` tree. -->

| Artifact Class / Declared Relative Path | Original Location | Pre-Copy Files | Pre-Copy Size | Copied Location | Post-Copy Files | Post-Copy Size | Copy Status / Evidence Gap |
|-----------------------------------------|-------------------|----------------|---------------|-----------------|-----------------|----------------|----------------------------|
| `data/raw/` | `[original_project]/data/raw/` | [N/N/A] | [bytes/N/A] | `original_files/data/raw/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `data/processed/` | `[original_project]/data/processed/` | [N/N/A] | [bytes/N/A] | `original_files/data/processed/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `output/analysis/` | `[original_project]/output/analysis/` | [N/N/A] | [bytes/N/A] | `original_files/output/analysis/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `output/figures/` | `[original_project]/output/figures/` | [N/N/A] | [bytes/N/A] | `original_files/output/figures/` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |
| `output/[additional/declared_artifact]` | `[original_project]/output/[same path]` | [N/N/A] | [bytes/N/A] | `original_files/output/[same path]` | [N/N/A] | [bytes/N/A] | [COPIED/NOT PRESENT/MISSING/FAILED] |

**Frozen raw-data seed:** [Not selected / Seeded the reproduction's `data/raw/` from `original_files/data/raw/` after the researcher chose frozen data at the checkpoint after the inventory, before re-running began (setup leaves `data/raw/` empty) / BLOCKED — frozen raw data absent]

### Frozen Raw-Input Integrity (when selected)

With frozen inputs, the data-download scripts are left out by the researcher's choice, so data download and the data mirrors are not tested. Each raw file's size and fingerprint (SHA-256 hash) is recorded before re-running and checked again afterward; any changed, added or missing raw file is a failure that needs investigation.

<!-- Agent note (deleted at RV-4): capture the exact inventory before downstream RV-2 execution and recompute it after all RV-2 execution. -->

| Relative Raw Path | Bytes Before | SHA-256 Before | Bytes After | SHA-256 After | Assessment |
|-------------------|--------------|----------------|-------------|---------------|------------|
| `data/raw/[file]` | [bytes] | [hash] | [bytes] | [hash] | [MATCH/DIVERGED] |

**Data-download scope:** [Re-fetch — the data-download scripts were in scope and re-run / Frozen inputs — exact list of data-download scripts EXCLUDED BY USER-CONFIRMED FROZEN-INPUT DESIGN]
**Data-download reproducibility:** [Tested in re-fetch mode / Out of scope with frozen inputs; no claim about the data mirrors]

### Evidence Coverage Summary

<!-- Agent note (deleted at RV-4): update during RV-1 as evidence is inventoried, after every RV-2 script, after RV-3 claim verification, and during the RV-4 rollup. Counts are derived from the inventory and result tables, not recalled. User exclusions count as out of scope only when confirmed and recorded before RV-2. -->

| Evidence Unit | In Scope | Directly Verified | Matched | Diverged | NOT DIRECTLY VERIFIED | Excluded Before Re-running |
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
- **EXCLUDED BY USER-CONFIRMED FROZEN-INPUT DESIGN** — a data-download script left out of scope, before re-running began, because the researcher chose frozen inputs. It was not run and is never counted as REPRODUCED, DIVERGED, FAILED, or silently skipped.

### Scope Decisions

The researcher makes these choices at the checkpoint after the inventory, before any script is re-run.

<!-- Agent note (deleted at RV-4): previewed at mode confirmation; decided at PSU-RV1, after the RV-1 inventory. RV-1 sets the Status to "Awaiting PSU-RV1" and leaves the choices unfilled; when the user decides, fill them and set "Confirmed at PSU-RV1 on YYYY-MM-DD". Session recovery reads this line, so keep its literal values. -->

**Status:** [Awaiting PSU-RV1 / Confirmed at PSU-RV1 on YYYY-MM-DD]

| Decision | User Choice | Rationale |
|----------|-------------|-----------|
| Re-fetch data from mirrors? | [Yes — re-run the data-download scripts / No — frozen inputs, data-download scripts left out by design] | [Why; if No, confirm the frozen seed and the fingerprints taken before re-running, and state that data download and mirrors are out of scope] |
| Methodological review depth | [Light / Full] | [Why] |
| Scripts excluded by scope design before re-running | [None / exact list with reasons, including the data-download scripts under frozen inputs] | [User confirmation and why; these alone leave denominators] |
| Declared outputs excluded before re-running | [None / exact project-relative paths with reasons] | [User confirmation and why] |
| Material Report claims excluded before re-running | [None / exact claims/locations with reasons] | [User confirmation and why] |

### Infrastructure Normalizations

Infrastructure normalizations are mechanical path and environment adjustments, applied during setup by `normalize_project_dir.py`, that make the decompiled scripts run in the reproduction project. They do not affect reproduction status: a script that needed only these adjustments can still be REPRODUCED.

<!-- Agent note (deleted at RV-4): applied during RV-1 setup by running `normalize_project_dir.py` on all decompiled scripts in batch. Paste the normalizer's Markdown table output below. -->

| File | Original Value | Normalized Value | Type |
|------|----------------|------------------|------|
| `stage5_fetch/01_fetch-data.py` | `PROJECT_DIR = Path("/daaf/research/original_project/")` | `PROJECT_DIR = Path("/daaf/research/reproduction_project/")` | PROJECT_DIR Path |
| `stage5_fetch/01_fetch-data.R` | `PROJECT_DIR <- file.path("/daaf", "research", "original_project")` | `PROJECT_DIR <- file.path("/daaf/research/reproduction_project")` | PROJECT_DIR file.path |

### Mandatory Path Containment Audit

**Utility:** `scripts/audit_reproduction_paths.py`
**Invocation:** `python3 /daaf/scripts/audit_reproduction_paths.py [scripts_root] [exact_original_root] [expected_reproduction_root] [--exclude exact/canonical/relative-script.py] [--exclude another/script.R]`
**Exit code / overall:** [0 MATCH / 1 DIVERGED / 2 NOT DIRECTLY VERIFIED]
**Setup check:** [PASSED — global exit 0 MATCH and every dispatched script has `scope: IN_SCOPE` + `assessment: MATCH` / BLOCKED — state the global or per-file failure]
**In-scope file assessments:** [List/cite deterministic `file_assessments`; every dispatched script must be MATCH]
**In-scope audit issues:** [None; none may remain before re-running begins]
**Excluded files and excluded issues:** [List `scope.excluded_files` and `excluded_issues` separately; excluded files never count as matches]
**Informational historical-log residue:** [List `ORIGINAL_ROOT_LOG_RESIDUE` from `informational_evidence`, or None; it is not a failure]
**Bounded assurance:** MATCH establishes only that the exact original-root string is absent from executable source before each in-scope script's unique canonical `# EXECUTION LOG` boundary and that every in-scope supported `.py`/uppercase `.R` script has one unique statically resolvable canonical `PROJECT_DIR` assignment equal to the reproduction root. Multiple canonical boundaries fail closed. Exact original-root residue after the unique boundary is informational immutable provenance, and arbitrary dynamically constructed paths are not proven safe.

```json
[paste deterministic audit JSON, including file_assessments, excluded_issues, and informational_evidence]
```

### Comparison Standards

<!-- Agent note (deleted at RV-4): adjudication standards for RV-2 dimensions supported by evidence. `compare_execution_logs.py` is log-metric-only: it aligns metrics by normalized identity and stable context rather than position, and returns 0 only for `CONSISTENT`, 1 for `DIVERGED`, 2 for invalid invocation or input read/parse failure, and 3 for `INCOMPLETE`/`INCONCLUSIVE`. Exit 3 is `NOT DIRECTLY VERIFIED` evidence, never success. For supported artifacts, run `compare_reproduction_artifacts.py` and preserve its deterministic JSON/per-dimension result. Artifact-helper exit semantics are load-bearing: 0 `MATCH`, 1 `DIVERGED`, 2 invalid/unsupported invocation, 3 `NOT DIRECTLY VERIFIED`. Exit 2 requires a corrected invocation or a separate evidence path; exit 3 is an evidence gap. Neither is a match. Figures use side-by-side Read-tool review. Persisted tables/models use a defined inspectable representation or remain `NOT DIRECTLY VERIFIED`. -->

The table lists how each kind of output was compared with the original and how close a match must be. Evidence that is missing, or that no comparison tool supports, is labeled `NOT DIRECTLY VERIFIED`, never counted as a match.

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

<!-- Agent note (deleted at RV-4): updated incrementally during RV-2. Each script gets its own section immediately after re-execution. Do NOT batch these: update the report after every single script. -->

### Script [#]: [script_name]

**Script folder:** [e.g. `stage6_clean`] | **Step:** [N.N] | **Type:** [fetch/clean/transform/analysis/viz]

#### Execution Comparison

| Dimension | Original | Reproduced | Evidence Source / JSON Dimension | Assessment |
|-----------|----------|------------|----------------------------------|------------|
| Exit code | [0/1] | [0/1] | [Both execution logs] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Output rows | [N] | [N] | [Both logs / artifact helper `row_count`] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Output columns | [N] | [N] | [Both logs / artifact helper `column_count`] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Parquet schema/content | [summary/path] | [summary/path] | [`compare_reproduction_artifacts.py` JSON: schema/null/value/duplicate dimensions; helper exit code] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Key statistics | [summary] | [summary] | [Both logs / inspectable persisted representation] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |
| Declared artifact: [path/type] | [path/status] | [path/status] | [Artifact-helper JSON / visual Read review / defined saved representation / unavailable] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |

<!-- Agent note (deleted at RV-4): add one **Declared artifact** row for every output the script declares. Preserve artifact-helper JSON and its exit code for each supported Parquet/exact pair. Compare PNGs visually. Compare tables/models through a defined inspectable saved representation; opaque models remain `NOT DIRECTLY VERIFIED`. Exact-byte `MATCH` means byte identity only. Never infer a match from successful execution, another matching dimension, or a log-helper summary. -->

#### Checkpoint Comparison

A script with built-in automated validation prints a banner such as `CP2 VALIDATION: PASSED` in its execution log. This table compares the banner each run printed.

| Checkpoint | Original Result | Reproduced Result | Evidence Source | Assessment |
|------------|-----------------|-------------------|-----------------|------------|
| [CP1/CP2/CP3/CP4] | [PASSED / PASSED WITH WARNINGS / FAILED + count line + key metrics] | [PASSED / PASSED WITH WARNINGS / FAILED + count line + key metrics] | [Both execution logs / unavailable] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] |

<!-- Agent note (deleted at RV-4): transcribe the verdict line exactly as each log printed it — the three legal CP strings are `PASSED`, `PASSED WITH WARNINGS`, and `FAILED` (QA logs print `QA{n} RESULT: PASSED | WARNING | BLOCKER`). `PASSED WITH WARNINGS` is not `PASSED`; recording it as one manufactures a match. Include each log's count line (`Checks: N passed, N warnings, N failed, N not verified, N skipped`): two runs can print the same verdict while differing in what was actually checked, and a run with `not verified > 0` verified less than its verdict suggests. Differing count lines under an identical verdict are a `DIVERGED` assessment, not a match. -->

#### Deviations

<!-- Agent note (deleted at RV-4): if status is REPRODUCED with no deviations, write "None — all directly evidenced comparison dimensions match within tolerance." List any `NOT DIRECTLY VERIFIED` dimensions separately; do not describe them as matches. -->

[Description of any differences observed. Include: what differs, magnitude of difference, likely cause (e.g., floating-point ordering, data source update, timestamp difference, random seed), and whether the deviation is substantive or cosmetic.]

#### Modifications Required

<!-- Agent note (deleted at RV-4): if no modifications were needed, write "None — original script executed successfully." If ANY modification was required, flag it prominently: modifications undermine reproduction fidelity. Each `_repro_a`/`_repro_b` revision must begin from a clean, log-free source (or have any inherited log stripped and verified absent) before fixes and one execution. Never copy and rerun the just-failed, log-appended file unchanged. -->

- **Modification type:** [Infrastructure / Substantive / None]
- **What was changed:** [exact description]
- **Why it was necessary:** [root cause]
- **Impact on output:** [whether the change could affect results]
- **Modified script location:** `scripts/repro/[script_name]`
- **Version suffix:** [_repro_a.py / _repro_b.py or _repro_a.R / _repro_b.R, as applicable]

#### Methodological Notes

<!-- Agent note (deleted at RV-4): brief observations about the analytical approach in this script. Concerns with severity >= NOTABLE should also be added to the Methodological Concerns Log above. -->

[Observations, or "No concerns noted."]

---

## Report Verification

This section checks specific claims, statistics and figures from the original Report against the reproduced outputs. Exclusions the researcher approved before re-running began stay outside the counts and are reported separately.

<!-- Agent note (deleted at RV-4): completed during RV-3, after all in-scope scripts are processed. -->

### Quantitative Claims

| # | Report Claim | Report Location | Original Value | Reproduced Value | Evidence Source | Assessment | Notes |
|---|-------------|-----------------|----------------|------------------|-----------------|------------|-------|
| 1 | [Specific stat or finding cited in Report] | [Section, paragraph] | [value] | [value from re-run] | [both logs / helper JSON dimension / saved representation] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] | [reason/evidence gap] |

### Figure Verification

| # | Figure | Report Location | Original Source Script | Original/Reproduced Evidence | Assessment | Notes |
|---|--------|-----------------|------------------------|------------------------------|------------|-------|
| 1 | [figure_name.png] | [Section] | [script_name] | [both paths viewed / missing side] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] | [visual evidence/cosmetic differences] |

### Findings Verification

A finding is MATCH only when direct reproduced evidence supports the same conclusion, DIVERGED when that evidence conflicts with it, and NOT DIRECTLY VERIFIED when the evidence it needs is missing or unsupported.

| # | Finding | Report Section | Evidence Source | Assessment | Confidence | Notes |
|---|---------|---------------|-----------------|------------|------------|-------|
| 1 | [Finding statement] | [Section] | [claim/artifact/figure evidence] | [MATCH/DIVERGED/NOT DIRECTLY VERIFIED] | [HIGH/MEDIUM/LOW] | [explanation] |

### Report Verification Summary

**Claims:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Figures:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Findings:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Declared artifacts:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Required dimensions:** [N] in scope — MATCH [N], DIVERGED [N], NOT DIRECTLY VERIFIED [N]
**Scope-design exclusions:** [N] exact exclusions approved before re-running began, listed separately

[Brief narrative: Are the Report's conclusions substantiated by the reproduction? Any caveats?]

---

## AI Use Disclosure

<!-- Agent note (deleted at RV-4): written during RV-4 from `agent_reference/AI_DISCLOSURE_REFERENCE.md` § Reproducibility Verification Mode (template paragraph and key points). Take the models, DAAF version, dates and provider route from the Reproduction Environment table below, and the verdict from the Executive Summary. -->

[One paragraph following the reproducibility disclosure template: the models and how they were reached, the date(s) and DAAF version, what the AI did (decompiling the notebook, checking script paths, re-running [N] scripts, comparing outputs, reviewing methods and checking the Report's claims), the data strategy, what remained NOT DIRECTLY VERIFIED, and, as a `[RESEARCHER]` sentence the researcher confirms after reading this report, that they reviewed it and are responsible for the final verdict.]

---

## Reproduction Environment

| Field | Value |
|-------|-------|
| **DAAF Version** | [git commit hash] |
| **Provider Route** | [Anthropic subscription / Anthropic API key / OpenAI API via DAAF provider shim / ChatGPT subscription via DAAF provider shim / OpenRouter / AWS Bedrock / Google Vertex AI] |
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

This compares the software environment of the original analysis with the one used for the reproduction. A version the evidence cannot establish is marked UNKNOWN or NOT DIRECTLY VERIFIED rather than guessed.

<!-- Agent note (deleted at RV-4): populated during RV-1 with language-aware observed evidence. Python comparison covers the runtime, marimo, and installed versions of packages imported by scripts. R comparison covers the R runtime, Quarto, repository/snapshot metadata, and `installed.packages()` versions for imported packages. Unversioned original `install.packages()` lines without snapshot evidence, and snapshot dates without either a matching current snapshot date or a quoted lookup, do not prove exact package versions; mark such original values UNKNOWN / NOT DIRECTLY VERIFIED rather than synthesizing a complete table from Python-style pins. When the original Dockerfile declares `UV_EXCLUDE_NEWER`, its `==` pins plus that cutoff (and any `--exclude-newer-package` overrides) establish the full original Python set, subject to the yank/deletion and architecture caveats (reconstruct it read-only with `uv pip compile --exclude-newer`, run as a single Bash command with absolute `{PROJECT_DIR}` paths — not via `run_with_capture.sh` — and quote the command and its output; never install). A reconstructed version that differs from an observed one, or a package that fails to resolve, is NOT DIRECTLY VERIFIED, not a version difference. Pre-freeze originals leave transitive Python versions UNKNOWN. See the mode reference's RV-1 step 12. Diagnostic scripts are verification instrumentation: store them under project `scripts/repro_checks/`, execute them through `run_with_capture.sh`, retain their appended logs, and never install packages at runtime. -->

**Original DAAF Version:** [commit hash from Report's AI Disclosure, e.g., `abc1234`]
**Original DAAF Release:** [semver if identifiable, e.g., `v2.1.0`, or `—` if not mapped to a release]
**Current DAAF Version:** [current commit hash]
**Current DAAF Release:** [current semver if identifiable]
**Original Dockerfile Source:** [URL used to fetch, e.g., `https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/{hash}/Dockerfile`, or `unavailable — see notes`]

**Environment-date inputs** (quote the matched Dockerfile lines as evidence; record a setting the original Dockerfile does not declare as `ABSENT (pre-freeze)`):

| Input | Original (original commit's Dockerfile) | Current (`/daaf/Dockerfile` + running image) | Status |
|-------|------------------------------------------|----------------------------------------------|--------|
| `UV_EXCLUDE_NEWER` (Python cutoff) | [timestamp / ABSENT (pre-freeze)] | [timestamp; running image `echo $UV_EXCLUDE_NEWER`] | [MATCH / DIFFERS / ABSENT] |
| `UBUNTU_SNAPSHOT` (apt snapshot) | [snapshot ID / ABSENT (pre-freeze)] | [snapshot ID; running image `/etc/daaf/ubuntu-snapshot`] | [MATCH / DIFFERS / ABSENT] |
| Base image digest (`UBUNTU_BASE_IMAGE` / `FROM`) | [digest / tag only] | [digest] | [MATCH / DIFFERS / TAG ONLY] |
| `P3M_SNAPSHOT_DATE` (R snapshot) | [date / ABSENT (pre-freeze)] | [date] | [MATCH / DIFFERS / ABSENT] |
| `--exclude-newer-package` overrides | [PKG=DATE list / none] | [PKG=DATE list / none] | [MATCH / DIFFERS] |

**Original Python set reconstruction:** [N/A — cutoffs, pins, and overrides match / `{PROJECT_DIR}/scripts/repro_checks/[file]` from read-only `uv pip compile --exclude-newer <original cutoff> [--exclude-newer-package ...]` (quote the command) / not possible — pre-freeze original]

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

A running log of all deviations, consolidated from the per-script sections for easy scanning.

<!-- Agent note (deleted at RV-4): add each row as the deviation is discovered during RV-2. -->

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

| File | Type | Created during |
|------|------|----------------|
| `original_files/[report]` | Original Report (copied) | setup |
| `original_files/[notebook]` | Original Notebook (copied) | setup |
| `original_files/output/figures/` | Original figures (copied) | setup |
| `original_files/output/preliminary_notes/` | Original discovery findings (copied, if present) | setup |
| `original_files/scripts/[...]` | Decompiled scripts (from notebook) | setup |
| `original_files/Dockerfile.original` | Original Dockerfile (fetched from public repo at original commit) | setup |
| `scripts/repro/[...]` | Re-executed scripts (with new logs) | re-running the scripts |
| `scripts/repro_checks/[...]` | Environment/evidence diagnostics (with appended logs, when needed) | setup / re-running the scripts |
| `output/figures/[...]` | Reproduced figures (generated) | re-running the scripts |
| `output/preliminary_notes/[date]_rv3_report-verification.md` | Full record of the report-claim verification | checking the report's claims |
| `Reproduction_Report.md` | This document | setup |

---

## Session Continuity

This report is also the saved progress of the reproduction: a new session resumes from the position recorded here.

<!-- Agent note (deleted at RV-4): the Reproduction Report is the sole session state document for Reproducibility Verification mode (no separate STATE.md). Update this section after every script re-execution, at every stage transition, and before any session break. Current Stage keeps its RV-1..RV-4 values: session recovery keys resume actions on them. -->

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

Observations, decisions, or issues encountered during reproduction that affect session continuity.

| # | When | Note |
|---|------|------|
| 1 | [the activity, e.g. "re-running the scripts"] | [observation or decision] |

### Restart Prompt

> Copy this prompt after `/clear` to resume with fresh context.

Resume the reproduction of [Original Project Title]. Reproduction Report: `[exact path]`. Currently [where we are, in plain words, e.g. "re-running the scripts: 12 of 30 done"]; last completed [description], next step is [description].
````

---

## Usage Guidelines

### When to Create

Create `Reproduction_Report.md` during **RV-1 (Intake & Setup)** after copying original artifacts and running the decompiler.

### Agent Notes

The report is both the working record and the deliverable the researcher reads. Per-section instructions for the agents filling it are HTML comments that open with `<!-- Agent note (deleted at RV-4):`, each on one line. They stay in the working file while the reproduction runs (Markdown viewers hide them; agents editing the file see them at the point of use), and the RV-4 report-writer deletes every one of them as its last step, so the delivered report carries none. If work resumes on a section after RV-4, its note is still in this template. Text outside those comments is written for the researcher (`agent_reference/DOCUMENTATION_STANDARDS.md` § S3 Plain for Users), except the parsed fields kept as they are: the Scope Decisions **Status** values ("Awaiting PSU-RV1" / "Confirmed at PSU-RV1 on YYYY-MM-DD") and the Current Position **Current Stage** values (RV-1 to RV-4), which session recovery reads.

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
9. Write the AI Use Disclosure from `agent_reference/AI_DISCLOSURE_REFERENCE.md` § Reproducibility Verification Mode
10. Delete every agent-note comment (§ Agent Notes) as the last edit

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
