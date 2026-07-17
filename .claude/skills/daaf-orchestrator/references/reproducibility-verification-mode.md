# Reproducibility Verification Mode

Verify that an existing analysis can be mechanically reproduced from its delivered notebook (marimo `.py` for Python, or a canonical DAAF Stage 9 Quarto `.qmd` for R—or an archive exactly compatible with that contract). The orchestrator decompiles the notebook into individual scripts, re-executes each one, compares log-level and available artifact-level evidence, and cross-references the original Report's claims against the reproduced results.

## User Orientation

After mode confirmation, briefly orient the user. Key points:

- You will reproduce an existing analysis by re-running every in-scope script extracted from its notebook (marimo for Python, or a canonical DAAF Stage 9 Quarto archive for R); any exact exclusions must be approved before re-execution
- You will receive a Reproduction Report documenting what matched, what diverged, and any methodological concerns
- The original project is never modified — all reproduction work happens in a new project folder

**When to skip:** User has indicated familiarity with this mode or is a returning user.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## User Decisions (Confirm Twice)

Two decisions must be confirmed at **mode confirmation** AND reconfirmed **after RV-1** (once the inventory is visible):

| Decision | Default | Options | Why Confirm Twice |
|----------|---------|---------|-------------------|
| Re-fetch data from mirrors? | Yes (re-fetch) | Yes / No (use frozen raw data copied from the original project) | Re-fetch executes Stage 5 and tests current acquisition; frozen mode hash-verifies supplied inputs, excludes Stage 5 by design, and does not test mirrors |
| Methodological review depth | Light (concerns only) | Light / Full (Five Lenses per script) | Full review is thorough but significantly slower |

At mode confirmation: present defaults, ask user to confirm or adjust.
After RV-1: present the script inventory, original-artifact inventory, and evidence gaps, then ask the user to reconfirm both decisions with the scope now concrete. If the user chose frozen data but `original_files/data/raw/` has no copied raw files, stop and require a new choice before RV-2; do not silently fall back to re-fetching or to processed data.

---

## Reproducibility Verification Workflow

```
User points to existing analysis folder
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ RV-1: Intake & Setup                                │
│                                                     │
│  1. Locate original project folder                  │
│  2. Validate: Report + Notebook exist               │
│  3. Create reproduction project folder              │
│     YYYY-MM-DD_[OriginalProject]_Reproduction/      │
│  4. Inventory + copy bounded original artifacts     │
│     → original_files/<same relative paths>          │
│  5. Run decompiler → original_files/scripts/        │
│  6. Normalize paths, then mandatory containment audit│
│  7. Create Reproduction_Report.md from template     │
│  8. Populate Script + artifact/evidence inventories │
│                                                     │
│  PSU: Present inventory, reconfirm scope decisions  │
│  GATE: User confirms before proceeding              │
└──────────────────────┬──────────────────────────────┘
                       │ User confirms
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-2: Sequential Re-execution & Comparison          │
│                                                     │
│  For each in-scope script (in notebook order):      │
│    1. Copy script → scripts/repro/{stage_dir}/      │
│    2. Strip execution log from copy                 │
│    3. Execute via run_with_capture.sh               │
│    4. Compare available evidence                    │
│       - Optional log-level metrics helper           │
│       - Declared output artifacts when both exist   │
│    5. If DIVERGED or FAILED: log deviation details  │
│    6. If modification required: create versioned    │
│       copy (_repro_a.{py|R}), document prominently  │
│    7. Assess methodological concerns (light/full)   │
│    8. Update Reproduction_Report.md immediately     │
│                                                     │
│  Continue through ALL in-scope scripts sequentially           │
│  No early termination unless user requests stop     │
└──────────────────────┬──────────────────────────────┘
                       │ All scripts processed
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-3: Report Verification                           │
│                                                     │
│  1. Read original Report                            │
│  2. Extract all quantitative claims + figures       │
│  3. Cross-reference each claim against reproduced   │
│     script outputs and execution logs               │
│  4. Verify each figure can be regenerated           │
│  5. Assess: do reproduced results support the       │
│     same findings and conclusions?                  │
│  6. Update Report Verification section              │
│                                                     │
│  Agent: data-verifier (adversarial cross-check)     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Pre-Synthesis: Collect session logs                  │
│  └─ bash {BASE_DIR}/scripts/collect_session_logs.sh  │
│     {PROJECT_DIR}                                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-4: Synthesis                                     │
│                                                     │
│  1. Synthesize methodological concerns              │
│  2. Write Executive Summary                         │
│  3. Write Report Verification Summary narrative     │
│  4. Determine overall assessment:                   │
│     FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED   │
│  5. Present final Reproduction Report to user       │
│                                                     │
│  Agent: report-writer (synthesis)                   │
│                                                     │
│  PSU: Present findings to user                      │
└─────────────────────────────────────────────────────┘
```

---

## Stage Details

### RV-1: Intake & Setup

**Actor:** Orchestrator (directly, no subagent needed)

**Steps:**
1. User provides path to existing analysis folder
2. Identify exactly one original Report (`*_Report.md`) and exactly one supported delivered notebook:
   - **Python:** a canonical DAAF Stage 9 marimo `*.py` archive with the notebook-assembler identity and complete header/source/immediately-adjacent execution-log bundles. A generic marimo app is not valid RV intake.
   - **R:** a canonical DAAF Stage 9 Quarto `*.qmd` archive (or the bounded compatible legacy log form accepted by the decompiler): each script chunk uses the exact `# --- VERBATIM COPY of scripts/... ---` marker and is followed immediately by its collapsed Execution Log container. A generic Quarto project or arbitrary `.qmd` is not valid RV intake.
   - If multiple Report candidates, multiple notebook candidates, or both `.py` and `.qmd` candidates exist, STOP and ask the user to select the exact Report and notebook. Never guess from naming or timestamps.
3. Create a new project folder: `research/YYYY-MM-DD_[OriginalProjectName]_Reproduction/`. The destination must not already exist; never reuse, merge into, or overwrite a prior reproduction folder automatically.
4. Create subdirectories: `original_files/`, `scripts/`, `scripts/repro/`, `scripts/repro_checks/`, `data/raw/`, `data/processed/`, `output/analysis/`, `output/figures/`, and `output/preliminary_notes/`. **Do not create `original_files/scripts/`**: it is the decompiler extraction root and must remain absent until the selected decompiler validates the complete plan and creates it. Create other parents under `original_files/` as needed for copied artifacts while preserving project-relative paths.
5. **Inventory and copy original evidence without modifying the original project:**
   a. Before copying, inventory each bounded standard artifact class in the original project — `data/raw/`, `data/processed/`, `output/analysis/`, and `output/figures/` — recording whether it is present plus its file count and total size. Also inventory every additional output artifact declared by the notebook scripts or original Report that resolves beneath the original project's `output/` tree, preserving its project-relative path. Treat an absent class or declared artifact as missing evidence, not as a zero-file copy.
   b. Copy the Report and Notebook to `original_files/`. When present, recursively copy the inventoried standard classes to `original_files/data/raw/`, `original_files/data/processed/`, `original_files/output/analysis/`, and `original_files/output/figures/`. Copy each additional declared artifact under `output/` to `original_files/<same project-relative path>`. If `output/preliminary_notes/` is present, it is included as an additional output class and provides discovery-phase context.
   c. Verify copied file counts and total sizes against the pre-copy inventory. Record each copied or missing artifact class, each additional declared output path, and the before/after counts and sizes in the Reproduction Report. Never label an absent source or failed copy as copied.
   d. If the user chose **use frozen data**, seed only the reproduction project's `data/raw/` from immutable `original_files/data/raw/` after copy verification. Do not seed `data/processed/` or `output/analysis/`; RV-2 must regenerate those outputs. If no frozen raw files were copied, stop at RV-1 and reconfirm whether to re-fetch, supply the missing raw evidence, or change scope.
6. Run the language-specific decompiler:
   - Python (marimo): `python3 /daaf/scripts/decompile_notebook.py <notebook_path> <project>/original_files/scripts/`
   - R (canonical DAAF Stage 9 Quarto archive): `Rscript /daaf/scripts/decompile_notebook.R <notebook_path> <project>/original_files/scripts/`
   Both are standalone framework utilities, so these direct CLI invocations are intentional exceptions to research-script file-first execution. Both require the extraction root to be new and refuse any existing file, directory, or symlink at that path; never pre-create, reuse, merge, or overwrite the extraction root. Both validate the complete extraction plan before writes and never evaluate notebook-derived code. The Python decompiler also rejects empty or placeholder logs such as `No execution log found`. `decompile_notebook.R` inverts the canonical DAAF Stage 9 archive contract rather than arbitrary Quarto semantics: it extracts R chunks identified by the exact marker, mirrors their stage-directory paths, and re-appends the immediately adjacent canonical collapsed callout; the bounded legacy `<details><summary>Execution Log</summary>...` form is fallback only. Both produce `MANIFEST.md`.
7. **Path normalization and mandatory containment audit:**
   a. Run `python3 /daaf/scripts/normalize_project_dir.py <project>/original_files/scripts/ <project_absolute_path>`. The normalizer recursively processes `.py` and uppercase `.R` files and rewrites only the first recognized canonical `PROJECT_DIR` assignment: Python `Path("...")` or quoted string; R quoted string or `file.path(...)` with `<-` or `=`. Record its output in **Infrastructure Normalizations**. This deterministic rewrite is an infrastructure normalization, not a substantive modification.
   b. Immediately run `python3 /daaf/scripts/audit_reproduction_paths.py <project>/original_files/scripts/ <original_project_absolute_path> <project_absolute_path> [--exclude <canonical-relative-script-path> ...]` and preserve its JSON result in the Reproduction Report. Supply `--exclude` once per exact user-approved pre-RV-2 script exclusion; each value must be a unique canonical POSIX-style relative path to an existing supported script beneath the scripts root. Exit 0 / global `MATCH` means every in-scope file passed. Exit 1 / `DIVERGED` or exit 2 / `NOT DIRECTLY VERIFIED` blocks RV-2 until the in-scope problem is corrected and the audit returns global MATCH. The deterministic `file_assessments` array must show each dispatched script as `scope: IN_SCOPE` and `assessment: MATCH`; excluded files remain explicit under `scope.excluded_files`, `file_assessments`, and `excluded_issues` but never enter the global verdict or count as matches.
   c. State the bounded assurance accurately: executable source is audited only before the unique canonical `# EXECUTION LOG` boundary. Exact original-root residue after that boundary is informational `ORIGINAL_ROOT_LOG_RESIDUE`, not a failure; multiple canonical boundaries fail closed as `AMBIGUOUS_EXECUTION_LOG_BOUNDARY`. A global pass proves that the exact original-root string is absent from each in-scope file's executable source and each in-scope supported script has one unique, statically resolvable canonical assignment equal to the reproduction root. It does not prove arbitrary dynamically constructed paths safe.
8. Create `Reproduction_Report.md` from `agent_reference/REPRODUCTION_REPORT_TEMPLATE.md`
9. Populate the Script Inventory table from the decompiler's `MANIFEST.md`, mapping fields as follows:
   - `#` and `Script` — map directly from MANIFEST
   - `Step` — extract from script filename (e.g., `01_fetch-ccd.py` → step `01`)
   - `Stage` — extract from parent directory (e.g., `stage5_fetch/` → stage `5`)
   - `Type` — infer from stage directory name (`fetch`, `clean`, `transform`, `analysis`)
   - `Original Output` — list every declared project-relative output path found in header metadata or script save calls; use `—` only when no output is declared
   - `Repro Status` — initialize all rows to `PENDING`
   Reconcile these script declarations against the step 5 artifact inventory. For any newly identified output artifact under the original project's `output/` tree, inventory and copy it to `original_files/<same project-relative path>`, verify count/size, and update the Reproduction Report before Gate RV-1.
10. **Check for dangling references** — inspect the decompiler's `MANIFEST.md` for a "Dangling Reference Warnings" section. If present, these scripts may reference variables defined in other marimo cells or Quarto chunks and may fail during RV-2 re-execution. Record the warnings in the Reproduction Report's **Runtime Notes** and flag affected scripts in the PSU-RV1 checkpoint so the user is aware before re-execution begins.
11. Populate the Source Artifacts, Original Artifact Inventory, Evidence Coverage Summary, Scope Decisions, and Reproduction Environment sections. The inventory must distinguish copied evidence from missing evidence and retain the pre-copy and post-copy file counts/sizes.
12. **Language-aware Environment Compatibility Check** — Extract the DAAF version from the original Report's AI Use Disclosure (commit and/or semver), retrieve the original public build specification when available, and capture current installed evidence for the script language. When a project-local diagnostic is needed, write it under the reproduction project's `scripts/repro_checks/` directory and execute it through `run_with_capture.sh`; this is verification instrumentation, not new analysis. Keep every diagnostic and its appended log as provenance.
    - **Python:** inventory the Python runtime, marimo, and installed Python packages actually imported by the decompiled scripts. Read `/daaf/Dockerfile` and use read-only installed-package inspection (`uv pip list --format=json`, `pip list`, or equivalent). Compare observed installed versions where the original build evidence establishes them.
    - **R:** inventory the R runtime, Quarto CLI, repository/snapshot metadata, and `installed.packages()` versions for packages actually imported by the decompiled `.R` scripts. Do not infer exact package versions from unversioned original `install.packages()` calls or from a snapshot date alone; mark those original versions `UNKNOWN` / `NOT DIRECTLY VERIFIED` unless the original build evidence pins them. A falsely complete table produced by parsing only Python-style `package==version` lines is prohibited.
    - **Comparison vocabulary:** MATCH, PATCH, MINOR, MAJOR, ADDED, REMOVED, and UNKNOWN / NOT DIRECTLY VERIFIED. Classify overall compatibility as COMPATIBLE, MINOR DIFFERENCES, SIGNIFICANT DIFFERENCES, or UNKNOWN based only on established evidence.
    - **No runtime installation:** never write, execute, or recommend `pip`/`uv`/`conda` installs or R `install.packages()`/equivalent runtime install calls, including install verbs embedded in diagnostic scripts. If a dependency change is required, use the Dockerfile-and-rebuild path outside the active runtime.
    - Populate the Reproduction Report with the observed command/script evidence, original evidence source, language-specific inventory, unknowns, and compatibility assessment.
13. **Environment Compatibility Decision** — If SIGNIFICANT DIFFERENCES or UNKNOWN, present two options at PSU-RV1: (a) proceed as-is with the mismatch/unknowns as standing context for deviations, or (b) update the Dockerfile and have the user rebuild outside the container. Record the decision. If rebuilding is selected, update Session Continuity, stop, and wait for the user to rebuild and resume. Never claim the rebuilt environment matches until its installed inventory is observed and compared.

**Gate RV-1:** All source artifacts present, decompiler succeeded, script inventory populated, environment compatibility check completed, user reconfirms scope decisions.

### RV-2: Sequential Re-execution & Comparison

**Actor:** code-reviewer agent (with reproduction-specific prompt)

**Why code-reviewer:** The code-reviewer's adversarial stance and Five Lenses of Skeptical Review make it ideal for this task. It already has file-first execution capability (enforce-file-first.sh), writes QA-style comparison scripts, and classifies findings by severity. For reproduction, it both re-executes and evaluates — combining the mechanical work with skeptical assessment.

**Frozen raw-data branch:** If the user confirmed frozen raw inputs, do not execute any Stage 5 acquisition script. After verified copy, seed reproduction `data/raw/` from `original_files/data/raw/`, capture a deterministic per-file inventory with SHA-256 hashes (or equivalent exact evidence), and record each Stage 5 script as **EXCLUDED BY USER-CONFIRMED FROZEN-INPUT DESIGN**. This is a scope-design exclusion, not REPRODUCED, DIVERGED, FAILED, MODIFIED, or an ad hoc skip. Begin RV-2 with the first downstream script that consumes the frozen inputs. After all RV-2 execution, recompute and compare the frozen raw inventory/hashes; any change is a failure requiring investigation. Acquisition reproducibility and mirror behavior remain outside this branch's scope. If the user selected re-fetch, execute Stage 5 normally.

Only exact exclusions confirmed before RV-2 are removed from verdict denominators and evidence-gap counts. Keep scope-design exclusions separate from ad hoc skipped/failed scripts in inventories, counts, and synthesis.

**Per-script atomic cycle:**

1. **COPY:** Copy `original_files/scripts/{stage_dir}/{script_name}` to `scripts/repro/{stage_dir}/{script_name}`
2. **STRIP:** Remove the execution log from the copy. Find the line matching `# EXECUTION LOG` (or the `# =====` separator immediately preceding it) and delete from that point to EOF. After stripping, verify the file does NOT contain the string `# EXECUTION LOG` — `run_with_capture.sh` will refuse to execute scripts that already have a log marker. Strip in place on the `scripts/repro/` copy (e.g., with the Edit tool); if any intermediate/scratch buffer is needed, write it to `{PROJECT_DIR}/scripts/scratch/`, never `/tmp` (which is outside the backup and audit boundary and blocked by the bash-safety.sh hook).
3. **EXECUTE:** `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/repro/{stage_dir}/{script_name}`
4. **COMPARE:** Account for each available evidence source rather than treating log comparison as complete output verification. For every declared project-relative output path `{relative_path}`, compare the original at `{PROJECT_DIR}/original_files/{relative_path}` with the reproduced artifact at `{PROJECT_DIR}/{relative_path}`. Never compare against the untouched original project during RV-2.
   - **Log metrics only:** Use `compare_execution_logs.py` only for metrics printed in both appended logs. It aligns row, column, and statistic metrics by normalized identity plus stable log context, never by position or value. Public exits are 0=`CONSISTENT` only, 1=`DIVERGED`, 2=invalid invocation or input read/parse failure, and 3=`INCOMPLETE`/`INCONCLUSIVE`. Exit 3 is `NOT DIRECTLY VERIFIED` log evidence, never success. The helper never compares artifacts, and `CONSISTENT` applies only to its extracted log metrics.
   - **Supported artifacts:** Run `python3 {BASE_DIR}/scripts/compare_reproduction_artifacts.py <original_artifact> <reproduced_artifact> [--mode parquet|exact]` for supported Parquet or intentionally exact-byte artifacts. Preserve its deterministic JSON and per-dimension evidence in the Reproduction Report. Exit 0=`MATCH`, exit 1=`DIVERGED`, exit 2=invalid/unsupported invocation and exit 3=`NOT DIRECTLY VERIFIED`; exits 2/3 never count as matches. Default pre-materialization limits are 512 MiB per input (`--max-input-bytes 536870912`) and 1,000,000 rows per input (`--max-rows 1000000`); exceeding either returns exit 3 before full materialization. Occurrence-aware tolerant float matching is bounded to 1,000,000 candidate pairs by default (`--max-pair-comparisons 1000000`). Parquet comparison requires ordered names/dtypes, matching row/column/null counts, exact supported scalar values except 1e-6 relative float tolerance, and occurrence-aware order-independent rows. Exact-key-set or exact-key-cardinality divergence is established before the tolerant-pair limit is applied; duplicate assessment reflects the comparison actually completed. Unsupported/nested values, NaN, or bounded tolerant work return `NOT DIRECTLY VERIFIED`. Exact mode proves byte identity (size + SHA-256), not semantic equivalence beyond those bytes.
   - **Separate evidence paths:** Compare PNG figures side by side with the **Read tool**. For persisted tables/models, compare an inspectable saved representation when a defined comparison exists; otherwise mark `NOT DIRECTLY VERIFIED`. The artifact helper explicitly excludes figures, logs, and opaque model formats.
   - **Unavailable evidence:** Record `NOT DIRECTLY VERIFIED` for every artifact or required dimension where either side is unavailable, the class is unsupported, or the dimension was neither persisted nor printed in both logs. Missing evidence is never a match and must not be inferred from successful execution or another matching dimension.
5. **ASSESS:** Classify the result as REPRODUCED / DIVERGED / FAILED. Per-script `REPRODUCED` means execution succeeded and every *available directly evidenced required dimension* matched within tolerance; retain an explicit `NOT DIRECTLY VERIFIED` qualifier for every unavailable required dimension. An evidence gap does not by itself force a per-script `DIVERGED` status, but it remains load-bearing for the overall verdict. If a modified script also produces divergent output, classify as MODIFIED (document the divergence in the Deviations section).
6. **METHODOLOGICAL REVIEW:** Examine the script's analytical approach:
   - **Light mode (default):** Note only NOTABLE or CRITICAL concerns
   - **Full mode:** Apply the Five Lenses of Skeptical Review
7. **UPDATE REPORT:** Update Reproduction_Report.md — Script Inventory status, Per-Script Reproduction Results section, Deviation Log if applicable, Concerns Log if applicable, Session Continuity (Last Script Completed, Next Script)
8. **IF FAILED:** If the script fails and a modification is needed for it to run:
   - Create `{script_name%.py}_repro_a.py` or `{script_name%.R}_repro_a.R` from a clean, log-free source copy. Never copy the just-failed, log-appended reproduction file and rerun it unchanged.
   - If a failed copy must be used as the starting point, strip the inherited execution log and verify the marker is absent before applying fixes and executing.
   - Apply and document the minimal fix, re-execute through `run_with_capture.sh`, and mark status MODIFIED (not REPRODUCED).
   - Apply the same clean-source/log-absence rule to `_repro_b`; each revision receives exactly its own newly appended execution log.

**Invocation pattern:**

```python
Agent({
    description: "RV-2: Reproduce script #{N}: {script_name}",
    prompt: """[prompt below]""",
    subagent_type: "code-reviewer"
})
```

**Prompt template:**

```
**BASE_DIR:** /daaf
**PROJECT_DIR:** {absolute_project_path}
All project-relative paths resolve from PROJECT_DIR. All repo-level paths resolve from BASE_DIR.

**TASK:** Reproduce script #{N} of {total}: `{script_name}`

**MODE:** Reproducibility Verification — RV-2 (Sequential Re-execution & Comparison)

**ORIGINAL SCRIPT:** `{PROJECT_DIR}/original_files/scripts/{stage_dir}/{script_name}`
**REPRODUCTION TARGET:** `{PROJECT_DIR}/scripts/repro/{stage_dir}/{script_name}`
**ORIGINAL ARTIFACT ROOT:** `{PROJECT_DIR}/original_files/`
**ORIGINAL RAW DATA:** `{PROJECT_DIR}/original_files/data/raw/` (if copied during RV-1)
**ORIGINAL PROCESSED DATA:** `{PROJECT_DIR}/original_files/data/processed/` (if copied during RV-1)
**ORIGINAL ANALYSIS OUTPUTS:** `{PROJECT_DIR}/original_files/output/analysis/` (if copied during RV-1)
**ORIGINAL FIGURES:** `{PROJECT_DIR}/original_files/output/figures/` (if copied during RV-1)
**ORIGINAL PRELIMINARY NOTES:** `{PROJECT_DIR}/original_files/output/preliminary_notes/` (if copied during RV-1)
**DIRECT COMPARISON RULE:** For each declared project-relative artifact path `{relative_path}`, compare `{PROJECT_DIR}/original_files/{relative_path}` with `{PROJECT_DIR}/{relative_path}`.
**DATA STRATEGY:** {RE-FETCH / FROZEN RAW INPUTS}. If FROZEN, this prompt must never target a Stage 5 script; Stage 5 is recorded separately as a user-approved scope-design exclusion. Use the pre-RV-2 raw hash inventory and return the post-cycle integrity status.
**PATH AUDIT EVIDENCE:** `audit_reproduction_paths.py` global exit 0 / `MATCH`, plus this exact script's deterministic `file_assessments` entry showing `scope: IN_SCOPE` and `assessment: MATCH` [paste or cite JSON]. Excluded files and `excluded_issues` are reported separately and are never dispatchable matches. If either the global result or this in-scope file assessment is absent or non-MATCH, STOP without execution.

**INSTRUCTIONS:**
1. Copy the original script to the reproduction target path
2. Strip the execution log from the copy: find the line containing `# EXECUTION LOG`
   (or the `# =====` separator immediately preceding it) and delete from that point to EOF.
   After stripping, verify the file does NOT contain `# EXECUTION LOG` —
   run_with_capture.sh will refuse to execute scripts that still have a log marker.
3. Execute via: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/repro/{stage_dir}/{script_name}`
4. Compare the available evidence and account for its source.
   - Use `compare_execution_logs.py` only for metrics printed into both appended logs. It
     aligns metrics by normalized identity and stable log context, never by position. Public
     exits are 0 CONSISTENT, 1 DIVERGED, 2 invalid invocation or input read/parse failure,
     and 3 INCOMPLETE/INCONCLUSIVE. Exit 3 is NOT DIRECTLY VERIFIED evidence, never success;
     `CONSISTENT` is log-metric evidence only and never an artifact verdict.
   - For every supported Parquet or intentionally exact-byte artifact pair, run
     `python3 {BASE_DIR}/scripts/compare_reproduction_artifacts.py {PROJECT_DIR}/original_files/{relative_path} {PROJECT_DIR}/{relative_path} [--mode parquet|exact]`.
     Preserve the helper's JSON and every dimension in the Reproduction Report. Interpret
     exit 0 as MATCH, exit 1 as DIVERGED, exit 2 as an invalid/unsupported invocation that must be corrected or routed to a separate evidence path, and exit 3 as NOT DIRECTLY VERIFIED.
     Defaults bound each Parquet input to 536870912 bytes and 1000000 rows before full
     materialization, and tolerant matching to 1000000 candidate pairs. A bound exceedance
     is exit 3. Exact-key/cardinality divergence is established before the pair limit, and
     duplicate status follows actual verification. Exact mode proves byte identity only,
     not format-level semantic equivalence.
   - Compare PNGs side by side with the Read tool. Compare persisted tables/models only through
     a defined inspectable saved representation; otherwise use NOT DIRECTLY VERIFIED. Figures,
     logs, and opaque model formats are outside the artifact helper's scope.
   - For every unavailable, unsupported, or unlogged artifact/dimension, record NOT DIRECTLY
     VERIFIED with the reason. Never infer a match from successful execution or another dimension.
5. Classify result: REPRODUCED / DIVERGED / FAILED. `REPRODUCED` is permitted when execution
   succeeded and every available directly evidenced required dimension matched within tolerance,
   but preserve each unavailable required dimension as an explicit `NOT DIRECTLY VERIFIED`
   qualifier. Do not turn the qualifier into a match or omit it from evidence coverage. If a
   modified script also produces divergent output, classify as MODIFIED (document divergence
   in Deviations section).
6. Methodological review depth: {LIGHT | FULL}
   If original preliminary notes exist, consult them for discovery-phase context
   (source caveats, coded value definitions, analytical rationale) when assessing
   methodological concerns. These notes document why certain analytical decisions
   were made in the original analysis.
7. Update `{PROJECT_DIR}/Reproduction_Report.md`:
   - Script Inventory table: update Repro Status for script #{N}
   - Per-Script Reproduction Results: fill in section for Script #{N}
   - Deviation Log: add row if any deviations found
   - Concerns Log: add row if concerns found
   - Session Continuity: update Last Script Completed and Next Script

**NOTE:** Scripts in `original_files/scripts/` were batch path-normalized during RV-1
(PROJECT_DIR values rewritten to the reproduction project path via `normalize_project_dir.py`).
Path differences between original and reproduction scripts are infrastructure normalizations,
NOT substantive modifications — do NOT count them as modifications or deviations.

**COMPARISON TOLERANCES:** See Reproduction Report § Comparison Standards

**ENVIRONMENT COMPATIBILITY:**
[If environment compatibility is COMPATIBLE, omit this block entirely.]
[If MINOR DIFFERENCES or SIGNIFICANT DIFFERENCES:]
The reproduction environment differs from the original analysis environment.
Overall compatibility: {COMPATIBLE/MINOR DIFFERENCES/SIGNIFICANT DIFFERENCES/UNKNOWN}.
Key mismatches: {list packages with MAJOR, MINOR, or REMOVED status}.
When classifying deviation causes, consider whether the deviation could be
attributable to library version differences. If a deviation occurs in a script
that uses a package with a MAJOR or MINOR version mismatch, note this as a
likely contributing factor. See the Reproduction Report § Environment
Compatibility Assessment for full details.
[If UNKNOWN:]
The original analysis environment could not be determined. Exercise additional
caution when classifying deviation causes — version differences are a plausible
factor for any divergence.

**IF SCRIPT FAILS:**
- Create each `_repro_a` / `_repro_b` revision from the clean, log-free original source copy. Never clone the just-failed log-appended file and rerun it unchanged.
- Before applying fixes, verify the revision contains no inherited `# EXECUTION LOG` marker; if inherited content exists, strip it and verify absence.
- Apply necessary fixes (max 2 versions; preserve `.py` or `.R`), document ALL modifications, execute once through `run_with_capture.sh`, and mark MODIFIED rather than REPRODUCED.

**OUTPUT FORMAT (2000-word hard cap):**
Return a concise summary:
- Status: [REPRODUCED/DIVERGED/FAILED/MODIFIED]
- Evidence-source accounting: counts of required dimensions and declared artifacts directly verified, diverged, and `NOT DIRECTLY VERIFIED`, with reasons for gaps
- Key comparison results and deviations (if any, with likely cause)
- Methodological concerns (if any, with severity)
- Files created/modified
```

**Sequencing:** Scripts are re-executed in the order they appear in the notebook (which matches the original execution order). Later scripts may depend on data produced by earlier scripts, so order must be preserved.

**No early termination:** Continue through ALL in-scope scripts even if some fail. The goal is a complete reproduction picture, not a pass/fail gate.

### RV-3: Report Verification

**Actor:** data-verifier agent (adversarial cross-artifact verification, read-only)

**Note:** The data-verifier agent is read-only (`permissionMode: plan`). It RETURNS its findings to the orchestrator, which then updates the Reproduction Report. This is consistent with how data-verifier operates at Stage 12 in Full Pipeline — it verifies and reports, never writes.

**Orchestrator post-processing:** After receiving the data-verifier's return, the orchestrator:
1. **[PERSIST]** Writes the full, unmodified data-verifier return to `output/preliminary_notes/{date}_rv3_report-verification.md` with provenance header (per orchestrator SKILL.md § Subagent Return Processing). This preserves the raw verification findings as an audit record and allows the RV-4 report-writer to reference full-fidelity findings rather than depending solely on the orchestrator's transcription.
2. Updates the Reproduction Report:
   - Report Verification § Quantitative Claims table
   - Report Verification § Figure Verification table
   - Report Verification § Findings Verification table
   - Report Verification § Summary

**Invocation pattern:**

```python
Agent({
    description: "RV-3: Verify Report claims against reproduced outputs",
    prompt: """[prompt below]""",
    subagent_type: "data-verifier"
})
```

**Prompt template:**

```
**BASE_DIR:** /daaf
**PROJECT_DIR:** {absolute_project_path}
All project-relative paths resolve from PROJECT_DIR. All repo-level paths resolve from BASE_DIR.

**TASK:** Verify the original Report's claims against reproduced analysis outputs.

**MODE:** Reproducibility Verification — RV-3 (Report Verification)

**ORIGINAL REPORT:** `{PROJECT_DIR}/original_files/{report_filename}`
**ORIGINAL ARTIFACT ROOT:** `{PROJECT_DIR}/original_files/` (including copied `data/processed/`, `output/analysis/`, `output/figures/`, and any additional declared outputs)
**REPRODUCED SCRIPTS:** `{PROJECT_DIR}/scripts/repro/`
**REPRODUCED ARTIFACT ROOT:** `{PROJECT_DIR}/` (compare each declared relative path against `original_files/<same relative path>`)
**REPRODUCTION REPORT:** `{PROJECT_DIR}/Reproduction_Report.md`
**ORIGINAL PRELIMINARY NOTES:** `{PROJECT_DIR}/original_files/output/preliminary_notes/` (if present — discovery-phase findings from original analysis)

**INSTRUCTIONS:**
1. Read the original Report in full
2. If original preliminary notes exist, read them for discovery-phase context —
   source caveats, coded value definitions, data limitations, and analytical
   rationale documented during the original analysis. These inform whether Report
   claims properly reflect the constraints discovered during data exploration.
3. Extract every quantitative claim (statistics, counts, percentages, coefficients)
4. Extract every figure reference
5. For each claim: locate the producing script and identify the strongest available evidence.
   Use `compare_execution_logs.py` only when the value appears in both logs; its exit 0
   CONSISTENT is log-only evidence, exit 1 is DIVERGED, exit 2 is invalid/read failure, and
   exit 3 INCOMPLETE/INCONCLUSIVE is NOT DIRECTLY VERIFIED rather than success. For supported
   Parquet or exact-byte evidence, use the preserved `compare_reproduction_artifacts.py` JSON
   (or run the helper if it has not yet been run) and carry its per-dimension result forward.
   Interpret artifact-helper exit 0 as MATCH, exit 1 as DIVERGED, exit 2 as invalid/unsupported (correct the invocation or use the separate evidence path), and exit 3 as NOT DIRECTLY VERIFIED.
   Use MATCH / DIVERGED / NOT DIRECTLY VERIFIED for every claim assessment.
6. For each figure: compare `original_files/<declared figure path>` with the reproduced path
   side by side using the Read tool. Use MATCH / DIVERGED / NOT DIRECTLY VERIFIED; an absent
   side is never a match. Minor anti-aliasing/font differences may be documented as cosmetic.
7. For each key finding: assess the conclusion as MATCH / DIVERGED / NOT DIRECTLY VERIFIED,
   distinguishing direct support from an evidence gap. For an inspectable persisted table/model,
   use its defined saved representation; otherwise use NOT DIRECTLY VERIFIED. Verify relevant
   caveats from preliminary notes were acknowledged.

**OUTPUT FORMAT (2000-word hard cap):**
Return structured findings for orchestrator to populate the Reproduction Report:
- Claims: N in scope; MATCH N; DIVERGED N; NOT DIRECTLY VERIFIED N
- Figures: N in scope; MATCH N; DIVERGED N; NOT DIRECTLY VERIFIED N
- Findings: N in scope; MATCH N; DIVERGED N; NOT DIRECTLY VERIFIED N
- Declared artifacts: N in scope; MATCH N; DIVERGED N; NOT DIRECTLY VERIFIED N
- Required dimensions: N in scope; MATCH N; DIVERGED N; NOT DIRECTLY VERIFIED N
- Per-row detail: item | original evidence | reproduced evidence | assessment | helper JSON/visual evidence | notes
- Keep exact pre-RV-2 scope-design exclusions in a separate list; do not place them in the denominator
- List every NOT DIRECTLY VERIFIED item with its missing/unsupported evidence reason
```

### Session Log Collection (Pre-Synthesis)

Before RV-4 synthesis, collect session logs into the project:
```
bash {BASE_DIR}/scripts/collect_session_logs.sh {PROJECT_DIR}
```
Update the Reproduction Report's Source Artifacts table to confirm `Reproduction Session Logs | logs/ | Yes`.

### RV-4: Synthesis

**Actor:** report-writer agent (narrative synthesis)

**Invocation pattern:**

```python
Agent({
    description: "RV-4: Synthesize Reproduction Report findings",
    prompt: """[prompt below]""",
    subagent_type: "report-writer"
})
```

**Prompt template:**

```
**BASE_DIR:** /daaf
**PROJECT_DIR:** {absolute_project_path}
All project-relative paths resolve from PROJECT_DIR. All repo-level paths resolve from BASE_DIR.

**TASK:** Write the synthesis sections of the Reproduction Report.

**MODE:** Reproducibility Verification — RV-4 (Synthesis)

**REPRODUCTION REPORT:** `{PROJECT_DIR}/Reproduction_Report.md`
**RV-3 VERIFICATION FINDINGS:** `{PROJECT_DIR}/output/preliminary_notes/{date}_rv3_report-verification.md` (full-fidelity data-verifier return)

**INSTRUCTIONS:**
1. Read the entire Reproduction Report (all per-script results, deviations,
   methodological concerns, report verification findings)
2. Read the RV-3 verification findings preliminary notes for the full-fidelity
   data-verifier return — this contains the raw per-claim, per-figure, and
   per-finding detail that may be more granular than the Reproduction Report's
   transcribed tables
3. Write the Executive Summary section:
   - Overall reproducibility assessment
   - In-scope script counts and percentages, with exact pre-RV-2 scope-design exclusions reported separately (including frozen-mode Stage 5)
   - Evidence coverage counts for claims, figures, findings, declared artifacts, and required dimensions: MATCH, DIVERGED, and `NOT DIRECTLY VERIFIED`
   - 3-5 sentence summary of findings
   - 2-3 sentence summary of methodological concerns
4. Write the Methodological Concerns § Synthesis section:
   - Group related concerns
   - Assess collective impact on conclusions
   - Provide overall methodological assessment
5. Ensure the Report Verification Summary narrative is complete
6. Determine overall assessment: FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED

**ASSESSMENT CRITERIA:**
- **FULLY REPRODUCED:** Every in-scope script is `REPRODUCED`; every in-scope material claim, figure, finding, declared artifact, and required comparison dimension is directly assessed `MATCH` (zero `NOT DIRECTLY VERIFIED` or `DIVERGED` items); and no in-scope script required substantive modification. Cosmetic differences are allowed only when they do not violate the applicable defined comparison.
- **PARTIALLY REPRODUCED:** At least some analysis reproduced, but an in-scope script diverged/failed/required modification, a directly evidenced item is `DIVERGED`, or any in-scope claim, figure, finding, artifact, or required dimension remains `NOT DIRECTLY VERIFIED`. Any in-scope evidence gap caps the verdict here.
- **NOT REPRODUCED:** Reproduction failures or substantive divergences prevent the key findings from being supported. Missing evidence is never itself a match and must not be upgraded by inference.

Before assigning the verdict, derive counts from the Reproduction Report for scripts, claims, figures, findings, artifacts, and required dimensions. Keep exact pre-RV-2 user-approved scope-design exclusions separate; only those exclusions are removed from denominators and verdict-gap counts. Ad hoc skips remain in scope and cannot be relabeled as exclusions after execution begins.

**OUTPUT FORMAT (2000-word hard cap):**
Return the overall assessment and a 3-sentence summary of the reproduction findings.
```

---

## Project Folder Structure

```
research/YYYY-MM-DD_[OriginalProject]_Reproduction/
├── Reproduction_Report.md              # Central artifact (created RV-1, updated throughout)
├── original_files/                     # Immutable copied evidence; same relative paths as original
│   ├── [original_report].md            # Copied from original project
│   ├── [original_notebook].py/.qmd     # Copied from original project (marimo or Quarto)
│   ├── Dockerfile.original             # Fetched from public repo at original commit (RV-1)
│   ├── data/
│   │   ├── raw/                        # Original frozen raw data, when present
│   │   └── processed/                  # Original processed Parquet evidence, when present
│   ├── output/
│   │   ├── analysis/                   # Original tables/models/results, when present
│   │   ├── figures/                    # Original figures for visual comparison, when present
│   │   ├── preliminary_notes/          # Discovery-phase findings, when present
│   │   └── ...                         # Other declared outputs, preserving relative paths
│   └── scripts/                        # Decompiled from notebook
│       ├── MANIFEST.md                 # Decompiler output manifest
│       ├── stage5_fetch/
│       │   ├── 01_fetch-*.py           # Original scripts with execution logs
│       │   └── ...
│       ├── stage6_clean/
│       ├── stage7_transform/
│       └── stage8_analysis/
├── data/
│   ├── raw/                            # Re-fetched, or seeded from original_files/data/raw/
│   └── processed/                      # Regenerated during RV-2; never pre-seeded
├── output/                             # Reproduced output (generated during RV-2/RV-3)
│   ├── analysis/                       # Regenerated tables/models/results
│   ├── figures/
│   │   └── *.png
│   └── preliminary_notes/              # Lossless agent returns persisted by orchestrator
│       └── {date}_rv3_report-verification.md
└── scripts/
    ├── repro/                          # Re-executed scripts
    │   ├── stage5_fetch/
    │   │   ├── 01_fetch-*.py           # Re-executed with new logs
    │   │   └── ...
    │   ├── stage6_clean/
    │   ├── stage7_transform/
    │   └── stage8_analysis/
    └── repro_checks/                   # Language-aware environment/evidence diagnostics with logs
```

---

## Boundaries

### Infrastructure vs. Substantive Modifications

Not all script modifications are equal. The distinction between infrastructure and substantive changes determines reproduction classification:

- **Infrastructure modifications:** Path rewrites (`PROJECT_DIR` values), import path adjustments, environment-specific configuration changes (e.g., temp directory paths, platform-specific settings). These are mechanical, deterministic transformations that do not alter the analytical logic. A script that required **only** infrastructure modifications retains **REPRODUCED** status.

- **Substantive modifications:** Changes to data transformations, filters, joins, aggregations, statistical methods, analytical logic, or any code that affects output values. These indicate the original script could not reproduce as-is and **must** be classified as **MODIFIED**. Every substantive modification must be documented in the Per-Script Reproduction Results with full justification.

The path normalization performed during RV-1 (step 7) is the canonical example of an infrastructure modification. It is applied deterministically to all scripts and documented in the Reproduction Report's Infrastructure Normalizations section.

### Always Do
- Process ALL in-scope scripts in the notebook, even if some fail; keep exact pre-RV-2 exclusions separate
- Update the Reproduction Report after EVERY script re-execution
- Preserve the original project completely untouched
- Inventory counts and sizes before copying bounded original artifacts; verify copied counts/sizes and record copied versus missing classes in the Reproduction Report
- Compare declared artifacts only as `original_files/<declared relative path>` versus `<PROJECT_DIR>/<declared relative path>`
- Run the normalizer and then run `audit_reproduction_paths.py` with repeatable validated `--exclude` values for exact pre-RV-2 script exclusions; require global exit 0 / MATCH and each dispatched script's `file_assessments` entry to be in-scope MATCH before RV-2
- When frozen data is selected, seed only `data/raw/` from immutable `original_files/data/raw/`; capture per-file hash inventory, exclude Stage 5 by explicit design, start downstream, and verify the frozen inventory is unchanged after RV-2
- Document ANY modification required to run a script, no matter how small
- Create every `_repro_a` / `_repro_b` revision from a clean log-free source and verify no inherited log marker before execution
- Use `compare_execution_logs.py` only for shared log metrics and `compare_reproduction_artifacts.py` for supported Parquet/exact-byte evidence; preserve JSON and exit semantics
- Apply Reproduction Report tolerances only to dimensions supported by direct evidence; mark unavailable or unsupported dimensions `NOT DIRECTLY VERIFIED`
- Never treat missing evidence, an absent artifact, an unsupported comparison, or an unlogged dimension as a match

### Never Do
- Modify files in the original project folder
- Reuse, merge into, or overwrite an existing reproduction destination or decompiler extraction root
- Seed reproduction `data/processed/` or `output/analysis/` from original evidence; those artifacts must be regenerated
- Execute Stage 5 when frozen raw inputs were selected, or claim that frozen mode tested acquisition/mirrors
- Skip scripts without explicit pre-RV-2 user approval or conflate a scope-design exclusion with an ad hoc skip
- Mark a modified script as REPRODUCED (must be MODIFIED)
- Write new analysis code — this mode verifies existing code, not creates new
- Change the analytical methodology to "improve" results
- Suppress or minimize deviations — every deviation is documented

### Ask First
- Before skipping any script (even if it appears redundant)
- Before making modifications to a script that go beyond path fixes
- If a deviation pattern suggests a systemic issue (e.g., all data changed)

**See also:** `agent_reference/BOUNDARIES.md` § Reproducibility Verification Mode

---

## Escalation Triggers

| Condition | Escalation Target | Trigger |
|-----------|-------------------|---------|
| Re-execution fails, needs code fix | Debugger dispatch within RV-2 | Script error that is not a simple path fix |
| Divergence found, user wants to fix original | Revision & Extension mode | User requests fixing the original analysis |
| Original analysis is fundamentally broken | Full Pipeline mode | Multiple structural failures across stages |
| Data source has changed substantially | User decision | Data mirror returns different schema or >5% row count difference |

When escalation is appropriate, propose it explicitly and await user confirmation.

---

## AI Disclosure

Reproducibility Verification uses AI to re-execute scripts and compare outputs. Disclose:
- AI performed the mechanical re-execution and output comparison
- AI assessed methodological concerns (at user-selected depth)
- AI cross-referenced Report claims against reproduced data
- Human reviewed the final Reproduction Report and assessed significance of findings

See `agent_reference/AI_DISCLOSURE_REFERENCE.md` § Reproducibility Verification Mode.

---

## Gate Definitions

| Gate | After Stage | Criteria | STOP If |
|------|-------------|----------|---------|
| **Gate RV-1** | RV-1 | Exactly one user-selected Report and one supported DAAF Stage 9 notebook; new reproduction destination and new extraction root; original evidence inventoried/copied/verified; decompiler succeeded; normalizer completed; path audit invoked with each exact user-approved script exclusion as a validated repeatable `--exclude`; global exit 0 / MATCH; every dispatched script has an in-scope MATCH `file_assessments` entry; excluded files/issues and informational log residue recorded separately; bounded assurance recorded; Script Inventory populated; language-aware environment evidence captured; frozen `data/raw/` seeded and hashed only when selected; user reconfirms scope and exact exclusions | Ambiguous intake; destination/root already exists; decompiler fails; Report/Notebook missing; global path audit is DIVERGED or NOT DIRECTLY VERIFIED; any dispatched script lacks an in-scope MATCH assessment; frozen data selected but unavailable |
| **Gate RV-2** | RV-2 | All in-scope scripts processed; frozen-design Stage 5 exclusions recorded separately and raw hashes unchanged; Reproduction Report updated after every script; helper JSON/per-dimension artifact evidence and NOT DIRECTLY VERIFIED gaps populated | User requests stop; frozen raw inventory changed |
| **Gate RV-3** | RV-3 | All in-scope claims, figures, findings, artifacts, and required dimensions assessed as MATCH, DIVERGED, or `NOT DIRECTLY VERIFIED`; exact scope-design exclusions remain separate; evidence coverage populated | N/A (always proceed to synthesis) |
| **Gate RV-4** | RV-4 | Executive Summary written; overall assessment determined; Reproduction Report complete | N/A (final stage) |

**Gate enforcement:** Gate RV-1 is a user-blocking gate (PSU + explicit user confirmation required). Gates RV-2 through RV-4 are automated (proceed when criteria met).

---

## PSU Templates

### PSU-RV1: Post-Inventory Checkpoint

Present to the user after RV-1 completes, before proceeding to RV-2:

```markdown
**Reproduction Setup Complete**

**Original Analysis:** [project name]
**Scripts Found:** [N] scripts across [N] stages

| Stage | Scripts | Description |
|-------|---------|-------------|
| Fetch (5) | [N] | [brief] |
| Clean (6) | [N] | [brief] |
| Transform (7) | [N] | [brief] |
| Analysis (8) | [N] | [brief] |

**Original Artifact Evidence:**
- **Copied:** [artifact classes/declared paths with verified file counts and sizes]
- **Missing:** [artifact classes/declared paths; "None" if none]
- **Declared outputs directly comparable:** [N] of [N]
- **Material Report claims with direct original evidence identified:** [N] of [N]

**Path Containment Audit:**
- **Invocation:** `python3 /daaf/scripts/audit_reproduction_paths.py [scripts_root] [original_root] [reproduction_root] [--exclude exact/relative/script ...]`
- **Result:** [MATCH + exit 0 required; include JSON evidence path]
- **In-scope file assessments:** [Every dispatched script is `IN_SCOPE` + `MATCH`]
- **Excluded files/issues:** [Exact pre-RV-2 exclusions and `excluded_issues`; never counted as matches]
- **Informational log residue:** [`ORIGINAL_ROOT_LOG_RESIDUE` entries, or None; historical-log residue is not a failure]
- **Bounded assurance:** Audits executable source before the unique canonical `# EXECUTION LOG` boundary. Confirms exact original-root residue is absent there and each supported in-scope script has one unique canonical PROJECT_DIR assignment resolving to the reproduction root; ambiguous boundaries fail closed and arbitrary dynamic paths are not proven safe.

**Environment Compatibility:**
- **Execution language:** [Python / R]
- **Original DAAF Version:** [commit hash / semver from Report]
- **Current DAAF Version:** [current commit hash / semver]
- **Overall Compatibility:** [COMPATIBLE / MINOR DIFFERENCES / SIGNIFICANT DIFFERENCES / UNKNOWN]
- **UNKNOWN / NOT DIRECTLY VERIFIED versions:** [list; include unpinned R packages rather than inferring exact versions]

[If COMPATIBLE:]
Environment matches the original — no version-related divergence expected.

[If MINOR DIFFERENCES:]
[N] packages have minor version differences (details in the Reproduction Report). These are unlikely to cause failures but may explain small numerical differences if any appear.

[If SIGNIFICANT DIFFERENCES:]
**Attention needed:** [N] packages have major version differences or are missing from the current environment. This may cause script failures or significant output divergence. Key mismatches:
- [package]: [original_version] → [current_version] ([MAJOR/REMOVED])
- ...

You have two options:
1. **Proceed as-is** — I'll document the environment mismatch and factor it into the reproduction assessment. Any deviations may be attributable to version differences.
2. **Rebuild to match** — I can modify the Dockerfile to match the original versions. You'd exit, rebuild the container, and resume. This gives the cleanest reproduction.

[If UNKNOWN:]
**Note:** I couldn't determine the original environment (commit hash not found on the public repo). I'll proceed with the current environment and flag this limitation in the Reproduction Report.

**Your Scope Decisions (please reconfirm):**
- **Re-fetch data from mirrors?** Currently: [Yes/No]. [If Yes: execute Stage 5 and data may differ. If No: seed `data/raw/` from immutable copied evidence, capture per-file hashes, exclude Stage 5 acquisition scripts by explicit frozen-input design, start with downstream consumers, and verify raw hashes remain unchanged after RV-2. Acquisition/mirrors are not tested. If frozen raw evidence is absent: STOP and ask the user to choose re-fetch, supply evidence, or change scope.]
- **Methodological review depth?** Currently: [Light/Full]. [Light flags only notable concerns; Full applies the Five Lenses to every in-scope script.]
[If SIGNIFICANT DIFFERENCES:] - **Environment mismatch action?** [Proceed as-is / Rebuild to match]

**What happens next:** I'll re-execute each in-scope script in notebook order, compare outputs against the originals, and update the Reproduction Report after each one. This runs through all [N] in-scope scripts; [N] exact pre-RV-2 exclusions remain separately reported. I will not stop early unless you ask me to.

**Shall I proceed with these settings, or would you like to adjust?**
```

### PSU-RV4: Reproduction Findings

Present to the user after RV-4 completes:

```markdown
**Reproduction Complete**

**Overall Assessment:** [FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED]

**Summary:**
- **Scripts:** [N] of [N] in-scope scripts reproduced successfully ([X]%); [N] exact pre-RV-2 scope-design exclusions reported separately
- **Deviations:** [N] substantive, [N] cosmetic
- **Modifications Required:** [N] scripts needed changes to run
- **Report Claims:** MATCH [N], DIVERGED [N], `NOT DIRECTLY VERIFIED` [N] of [N] in scope
- **Figures:** MATCH [N], DIVERGED [N], `NOT DIRECTLY VERIFIED` [N] of [N] in scope
- **Findings:** MATCH [N], DIVERGED [N], `NOT DIRECTLY VERIFIED` [N] of [N] in scope
- **Declared Artifacts:** MATCH [N], DIVERGED [N], `NOT DIRECTLY VERIFIED` [N] of [N] in scope
- **Required Dimensions:** MATCH [N], DIVERGED [N], `NOT DIRECTLY VERIFIED` [N] of [N] in scope

[2-3 sentence narrative from Executive Summary]

**Key Findings:**
[Top 3-5 findings, bulleted]

**Methodological Concerns:** [None / Brief summary]

The full Reproduction Report is at: `[path]`
Session logs collected in: `[project_dir]/logs/`

**Explore Session Logs:**
To browse the session timeline interactively in your browser, run in the Docker terminal:
`bash /daaf/scripts/generate_log_viewer.sh [project_dir]`

**What would you like to do?**
- Review the Reproduction Report in detail
- Discuss specific deviations or concerns
- Fix issues in the original analysis (switches to Revision & Extension mode)
```

---

## Per-Script Execution Cycle (Formalized)

The RV-2 per-script cycle is lightweight compared to Full Pipeline's Composite Execution Pattern. The re-execution IS the review — the code-reviewer both re-executes and evaluates in a single invocation.

> **Wave barrier discipline (async dispatch).** RV-2 is deliberately sequential — one script's code-reviewer dispatch at a time, in notebook order. Because subagents run in the background by default and complete via async task notifications, the barrier still applies at the single-dispatch level: do not begin the next script's cycle, advance Session Continuity, or draw cross-script conclusions until the current dispatch has actually returned. When RV-2 escalation dispatches the debugger, treat that as part of the same script's cycle — wait for it before moving on. (Updating the Reproduction Report after each script's own return is intended incremental behavior, not a barrier violation: each script is its own single-member wave.) See the master statement in `SKILL.md` § Subagent Coordination > "Wave Barrier Discipline (Async Dispatch)."

**Atomic cycle per script:**

| Step | Action | Detail |
|------|--------|--------|
| 0 | READ | Check Reproduction Report § Session Continuity and scope design. In frozen mode, Stage 5 rows are recorded as design exclusions and not dispatched. |
| 1 | COPY | Copy original script to `scripts/repro/{stage_dir}/` |
| 2 | STRIP | Remove execution log and verify no `# EXECUTION LOG` marker remains |
| 3 | EXECUTE | Run via `run_with_capture.sh` |
| 4 | COMPARE | Use the identity/context-aligned log helper only for metrics printed in both logs (0 CONSISTENT only, 1 DIVERGED, 2 invalid/read failure, 3 INCOMPLETE/INCONCLUSIVE = NOT DIRECTLY VERIFIED); use `compare_reproduction_artifacts.py` JSON for supported Parquet/exact artifacts (0 MATCH, 1 DIVERGED, 2 invalid/unsupported, 3 NOT DIRECTLY VERIFIED), retaining its default 512 MiB/input, 1,000,000 rows/input, and 1,000,000 tolerant-pair bounds; inspect figures visually and saved table/model representations when defined. |
| 5 | ASSESS | Classify: REPRODUCED / DIVERGED / FAILED / MODIFIED, retaining every NOT DIRECTLY VERIFIED qualifier. Keep pre-RV-2 design exclusions separate. |
| 6 | REVIEW | Methodological review (Light: notable/critical only; Full: Five Lenses) |
| 7 | UPDATE | Update Reproduction Report (Script Inventory + Per-Script Reproduction Results + Deviation Log + Concerns Log + Session Continuity) |
| 8 | RETURN | Return concise summary to orchestrator |

**Error handling within the cycle:**
- If Step 3 fails: create `_repro_a.{ext}` from a clean, log-free source, verify no inherited marker, apply minimal fixes, execute once, document, and mark MODIFIED
- If modification also fails: independently create `_repro_b.{ext}` from clean, log-free source (or strip and verify any inherited log before fixes); never copy and rerun the just-failed appended file unchanged; after 2 versions mark FAILED
- If FAILED after 2 modification attempts: orchestrator may dispatch debugger (max 1 per script, max 3 per session)

---

## Revision Invocation Template

When a script fails during RV-2 and the code-reviewer's modification attempts also fail, the orchestrator may dispatch the debugger:

```python
Agent({
    description: "Debug: RV-2 script failure: {script_name}",
    prompt: """You are a Debugger. Read and follow the protocol in
    `{BASE_DIR}/.claude/agents/debugger.md`.

    **BASE_DIR:** /daaf
    **PROJECT_DIR:** {absolute_project_path}
    All project-relative paths resolve from PROJECT_DIR. All repo-level paths resolve from BASE_DIR.

    **CONTEXT:**
    Mode: Reproducibility Verification (RV-2)
    Original Script: {PROJECT_DIR}/original_files/scripts/{stage_dir}/{script_name}
    Failed Reproduction: {PROJECT_DIR}/scripts/repro/{stage_dir}/{script_name}
    Modified Version: {PROJECT_DIR}/scripts/repro/{stage_dir}/{modified_script_name}

    **ERROR DETAILS:**
    - Error message: [verbatim error from execution log]
    - Modification attempted: [what the code-reviewer changed]
    - Result of modification: [what happened]

    **CONSTRAINTS:**
    - This is a REPRODUCTION — the goal is MINIMAL changes to get the script running.
    - Any fix must be documented as a modification in the Reproduction Report.
    - The script's analytical logic must not be altered.

    Diagnose the root cause and return a minimal fix recommendation.""",
    subagent_type: "debugger"
})
```

---

## Context Management

Reproducibility Verification can span many scripts, each consuming subagent context. Follow the context utilization thresholds in `CLAUDE.md` > "Context & Session Health".

**Natural restart boundaries:**
- Between any two scripts in RV-2 (each is atomic)
- Between RV-2 and RV-3
- Between RV-3 and RV-4

**Actions by utilization level:**

Trigger points are **threshold-profile-conditional** (percentage OR absolute tokens, whichever fires first); each agent is measured against the profile selected from its own exact model ID. Profile selection is version-specific and independent of physical context-window mapping. Exact GPT 5.6 Sol has a separate validated profile that shares the standard 40%/60%/75% percentage boundaries (also used by the conservative default) while retaining higher validated absolute gates (300k/400k/500k). For that profile, the terminal model slug must be exactly `gpt-5.6-sol` or `gpt-5.6-sol[1m]`; the identifier may be bare or may contain one or more provider path prefixes ending in `/`. Malformed left-boundary strings such as `xgpt-5.6-sol`, `foo-gpt-5.6-sol`, and `vendor/notgpt-5.6-sol` remain conservative, as do right-side suffix or trailing variants. GPT is not part of the Claude Fable/Mythos model family. Terra, Luna, Pro, mini, chat, date snapshots, future variants, and trailing modifiers remain conservative unless separately validated and registered, even when the wider GPT 5.6 family maps to a 1,050,000-token physical window. That 1,050,000 figure is itself route-conditional: it holds on the API-key and OpenRouter routes, while the ChatGPT-subscription (Codex) shim lane is backend-capped at approximately 370,000 tokens (measured for Sol, 2026-07-16), which DAAF's hooks lane-gate automatically. At that cap, exact Sol's 40%/60%/75% percentage boundaries are 148k, 222k, and 277.5k tokens, respectively, and therefore fire before its 300k/400k/500k absolute gates; the same exact-Sol quality profile applies on both lanes even though their physical windows differ.

| Threshold Profile | Membership | ELEVATED at | HIGH at | CRITICAL at |
|-------------------|------------|-------------|---------|-------------|
| **Claude Fable/Mythos validated extended-horizon** | Registered Claude Fable/Mythos models | ≥ 30% or ≥ 300k tokens | ≥ 40% or ≥ 400k tokens | ≥ 50% or ≥ 500k tokens |
| **Exact GPT 5.6 Sol validated** | Exact terminal model slugs, bare or provider-prefixed: `gpt-5.6-sol` or `gpt-5.6-sol[1m]` | ≥ 40% or ≥ 300k tokens | ≥ 60% or ≥ 400k tokens | ≥ 75% or ≥ 500k tokens |
| **Conservative-default** | Opus, Sonnet, unknown model IDs, every other GPT variant, GLM models, and all other alternative-provider models unless individually validated and registered | ≥ 40% or ≥ 150k tokens | ≥ 60% or ≥ 200k tokens | ≥ 75% or ≥ 250k tokens |

The status levels and their actions are identical across profiles (NOMINAL is any utilization below the ELEVATED trigger):

| Status | Action |
|--------|--------|
| NOMINAL (below ELEVATED) | Continue normally |
| ELEVATED | Update Session Continuity after each script; monitor closely |
| HIGH | Complete current script's atomic cycle; update Session Continuity; present checkpoint to user with restart guidance |
| CRITICAL | Cease work; update Session Continuity; present restart prompt to user |

**Restart procedure:** User copies the Restart Prompt from the Reproduction Report's Session Continuity section, runs `/clear`, and pastes it. The new session reads the Reproduction Report to establish position and resumes from the next unprocessed script.

---

## Reproduction Report as State

Reproducibility Verification mode does NOT use `STATE.md`. The **Reproduction Report itself is the sole session state document**.

**Design rationale:** In Full Pipeline and Data Onboarding, STATE.md exists separately because the primary deliverables are not updated incrementally during execution. The Reproduction Report, by contrast, is designed for continuous incremental updates after every script re-execution. It already tracks:

- **Current position** — Session Continuity § Current Position
- **Progress** — Script Inventory (every script has a status)
- **Findings** — Per-Script Reproduction Results (filled incrementally)
- **Errors and deviations** — Deviation Log (running record)
- **Methodological observations** — Concerns Log (running record)
- **Scope decisions** — Scope Decisions table
- **Environment** — Reproduction Environment table
- **Restart context** — Session Continuity § Restart Prompt

A separate STATE.md would duplicate this without adding value.

**Update discipline:** The Reproduction Report MUST be updated after every atomic action:
- After each script re-execution (RV-2): Script Inventory + Per-Script Reproduction Results + Session Continuity
- After report verification (RV-3): Report Verification sections
- After synthesis (RV-4): Executive Summary + Synthesis of Methodological Concerns
- At every stage transition: Session Continuity § Current Stage
- Before any session break: Session Continuity § Restart Prompt
