# Reproducibility Verification Mode

Verify that an existing analysis can be mechanically reproduced from its delivered notebook (marimo `.py` for Python, or a canonical DAAF Stage 9 Quarto `.qmd` for R—or an archive exactly compatible with that contract). The orchestrator decompiles the notebook into individual scripts, re-executes each one, compares log-level and available artifact-level evidence, and cross-references the original Report's claims against the reproduced results.

A **package-intake variant (RV-P)** instead proves that a manuscript replication package regenerates every manuscript claim from a fresh, isolated copy, and classifies the result on the AEA Data Editor scale. It has its own intake, stages, gate, and invocation templates — see § RV-P: Package Intake Variant. Everything in the notebook-intake workflow below (RV-1 … RV-4) applies only where RV-P explicitly reuses it.

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

> **Bind-mounted inputs depend on externally-guaranteed files.** If the original analysis read inputs from a user-configured host bind mount (`/host_data`) rather than from data archived inside the project, those files live outside DAAF's hash/backup boundary — verification then depends on the user supplying the *same* mount contents. Confirm the frozen `data/raw/` copy (or an equivalent user-provided snapshot) is present before treating such a reproduction as complete; DAAF cannot hash-verify data it never archived.

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
10. **Check for dangling references** — inspect the decompiler's `MANIFEST.md` for a "Dangling Reference Warnings" section. If present, these scripts may reference variables defined in other marimo cells or Quarto chunks and may fail during RV-2 re-execution. Record the warnings in the Reproduction Report's **Runtime Notes** and flag affected scripts in the PSU-RV1 checkpoint so the user is aware before re-execution begins. Also check for an "Execution-Log Literal Warnings" section (Python only). It lists scripts whose archived log sits in a legacy non-raw `mo.md('''...''')` string containing backslashes; Python decodes those escapes (`\n` in a Windows path becomes a line break), so the decompiled log may differ from what the script printed. Current Stage 9 notebooks store logs in a raw `mo.md(r'''...''')` literal and never trigger it. Record each listed script in **Runtime Notes** and treat its archived log as not verified verbatim: compare it with the original script's log where the original project still has it. An "Execution-Log Fence Warnings" section (Python only) lists scripts whose log has a line that can close the log's code fence early, so the notebook's display may cut that log off; the decompiled log is unaffected. Note it in **Runtime Notes** as a display defect of the archive, not a fidelity problem.
11. Populate the Source Artifacts, Original Artifact Inventory, Evidence Coverage Summary, Scope Decisions, and Reproduction Environment sections. The inventory must distinguish copied evidence from missing evidence and retain the pre-copy and post-copy file counts/sizes.
12. **Language-aware Environment Compatibility Check** — Extract the DAAF version from the original Report's AI Use Disclosure (commit and/or semver), retrieve the original public build specification when available, and capture current installed evidence for the script language. When a project-local diagnostic is needed, write it under the reproduction project's `scripts/repro_checks/` directory and execute it through `run_with_capture.sh`; this is verification instrumentation, not new analysis. Keep every diagnostic and its appended log as provenance.
    - **Environment-date inputs (both languages):** from the original commit's Dockerfile (`original_files/Dockerfile.original`) and the current `/daaf/Dockerfile`, extract and record side by side `ARG UV_EXCLUDE_NEWER`, `ARG UBUNTU_SNAPSHOT`, the base-image digest (`ARG UBUNTU_BASE_IMAGE`, or the bare `FROM` line in older files), `ARG P3M_SNAPSHOT_DATE`, and every per-package `--exclude-newer-package PKG=DATE` override on a `uv pip install` line. Quote the matched lines, which are the evidence. Record an input the original Dockerfile does not declare as `ABSENT (pre-freeze)`, never as a guessed value; a tag-only `FROM` (e.g. `FROM ubuntu:24.04`, no digest) is recorded as `TAG ONLY`. Inside the current container, `echo $UV_EXCLUDE_NEWER` and `cat /etc/daaf/ubuntu-snapshot` confirm what the running image was actually built with.
    - **Python:** inventory the Python runtime, marimo, and installed Python packages actually imported by the decompiled scripts, using read-only installed-package inspection (`uv pip list --format=json`, `pip list`, or equivalent). Which original versions are established depends on the original Dockerfile:
      - **Frozen original** (it declares `UV_EXCLUDE_NEWER`): its `==` pins, that cutoff, and any `--exclude-newer-package` overrides establish the **full** Python set, transitive dependencies included, so treat the full set as established rather than UNKNOWN — subject to two caveats that apply to both branches below. *Yanks and deletions:* PyPI yank status and file availability are read live at resolution time, so a transitive version yanked after the cutoff can resolve differently today, and a deleted file fails resolution. *Architecture:* resolution is per platform, so a comparison across architectures stays `NOT DIRECTLY VERIFIED` for platform-specific packages. (a) If the original and current `UV_EXCLUDE_NEWER` values, `==` pins, and overrides all match, the original versions equal the current image's resolution, and observed `uv pip list` versions can be classified directly — the current image's own `uv pip list` is the observed truth. (b) If any differ, reconstruct the original resolved set read-only: extract the original `==` pins into `{PROJECT_DIR}/scripts/repro_checks/<name>.in` and run `uv pip compile --exclude-newer <original UV_EXCLUDE_NEWER> [--exclude-newer-package PKG=DATE ...] [--python-platform <original platform, e.g. aarch64-manylinux_2_39>] {PROJECT_DIR}/scripts/repro_checks/<name>.in -o {PROJECT_DIR}/scripts/repro_checks/<name>.txt` as a single Bash command with absolute paths (each Bash call starts in `/daaf`, so a relative `-o` path would write into the framework's own `scripts/` tree) (resolve only, never install; it is not Python/R code, so it does not go through `run_with_capture.sh` — quote the command and its output in the report instead), then compare the result against current `uv pip list`. A reconstructed version that differs from an observed one, or a package whose resolution fails, is `NOT DIRECTLY VERIFIED`, not `MAJOR`/`MINOR` — the reconstruction itself may reflect a later yank or deletion rather than a real environment difference.
      - **Pre-freeze original** (no `UV_EXCLUDE_NEWER`): only its `==` pins establish versions. Transitive dependency versions stay `UNKNOWN` / `NOT DIRECTLY VERIFIED`, because they floated at build time.
    - **R:** inventory the R runtime, Quarto CLI, repository/snapshot metadata, and `installed.packages()` versions for packages actually imported by the decompiled `.R` scripts. Do not infer exact package versions from unversioned original `install.packages()` calls that lack snapshot evidence, and do not supply a version from memory for a snapshot date. A P3M snapshot date plus a package name does determine the version that snapshot serves. A version is therefore established only when the original Dockerfile's `P3M_SNAPSHOT_DATE` is extracted and either (a) it equals the current image's `P3M_SNAPSHOT_DATE` (snapshot-installed packages then match the current installed versions), or (b) the version is actually looked up in the snapshot's repository index at that date and the lookup is quoted. Mark everything else `UNKNOWN` / `NOT DIRECTLY VERIFIED`: no snapshot evidence, no lookup performed, or a package installed outside the snapshot (archive or source builds, repository overrides). A falsely complete table produced by parsing only Python-style `package==version` lines is prohibited.
    - **System packages:** when the original and current `UBUNTU_SNAPSHOT` and base-image digest both match, apt-installed libraries (GDAL, OpenSSL, the Python interpreter) are established as identical. When either differs or is absent, record system-library versions as `UNKNOWN` / `NOT DIRECTLY VERIFIED` unless observed evidence establishes them.
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
5. **ASSESS:** Classify the result as REPRODUCED / DIVERGED / FAILED. A wrapper exit 74 (`EVIDENCE INCOMPLETE` banner) is neither REPRODUCED nor a script-logic FAILED — the appended log that COMPARE depends on is missing or marked `Capture: INCOMPLETE`; follow `ERROR_RECOVERY.md` § Execution Wrapper Evidence Outcomes (re-run in place or via a `_repro_` revision as the banner directs) before assessing. Per-script `REPRODUCED` means execution succeeded with a verified execution log and every *available directly evidenced required dimension* matched within tolerance; retain an explicit `NOT DIRECTLY VERIFIED` qualifier for every unavailable required dimension. An evidence gap does not by itself force a per-script `DIVERGED` status, but it remains load-bearing for the overall verdict. If a modified script also produces divergent output, classify as MODIFIED (document the divergence in the Deviations section).
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

## RV-P: Package Intake Variant

RV-P verifies a **replication package** rather than a Stage 9 notebook. It answers one question: does the package, run once from a clean copy with no help from DAAF's upstream research projects, regenerate every manuscript claim? The bar is the AEA Data Editor's: "Re-run… in a clean environment… (a) reproducible with minimal interaction (b) the results are numerically identical." The package's own anatomy (`main.py` entry point, `code/00_setup.*`, `requirements.txt` / `requirements-lock.txt` when the Python code imports third-party packages, and for R programs `renv.lock` with `.Rprofile` / `renv/activate.R`, `DATA_RIGHTS.md`, the SSDE README, the SC-01–SC-15 self-check) is defined by `.claude/skills/academic-manuscript/references/replication-package.md` and its assets (`main_template.py`, `package_selfcheck_template.py`, `DATA_RIGHTS_template.md`). This section defines only how RV verifies it.

**Why a variant, not a new mode:** RV already owns clean re-execution, the comparators, evidence-gap discipline, and the MATCH / DIVERGED / NOT DIRECTLY VERIFIED vocabulary. A package changes the intake and the unit of comparison (claims, not scripts). It does not change what counts as evidence.

### Trigger

- **Manuscript Preparation MP-4 hand-off.** After the package is assembled, the orchestrator proposes a transition to RV-P and the user confirms it. The Mode Confirmation Protocol still applies. The Manuscript Preparation mode file (`manuscript-preparation-mode.md`, MP-4 step 7b and § Transitions) defines its side of the transition. The orchestrator SKILL.md escalation rows between RV and Manuscript Preparation are **deferred** until Manuscript Preparation registers as a mode. Until then, the hand-off is described only here and in the Manuscript Preparation mode file, not in SKILL.md.
- **Direct user request.** The user asks to verify a DAAF replication package (e.g., "check that my replication package reproduces the paper"). The same intake applies. If the user has no claims ledger or values manifest, RV-P cannot check claims. Stop and offer notebook-intake RV (if a Stage 9 notebook exists) or Manuscript Preparation (to build the missing ledger).

### What Is Reused vs. New

| Component | RV-P use |
|-----------|----------|
| `run_with_capture.sh` | **Reused unchanged.** Wraps `main.py` once. It accepts `.py`/`.R` only, which is why the entry point is `main.py`, not a shell script |
| `compare_reproduction_artifacts.py` (parquet / exact modes, bounds, exit semantics) | **Reused unchanged** for table data, figure data, and rendered table includes. **Not** for figure image files: it classes `.png`/`.svg` as "figure visuals" and returns "Artifact class is outside this helper's scope" before checking the requested mode (observed in source: `scripts/compare_reproduction_artifacts.py:65-70, 137-146`). Figure-file hashes come from the snapshot inventory or a `sha256sum` probe (RV-P2 step 4) |
| `compare_execution_logs.py` | **Reused unchanged** for original DAAF logs vs. the proof-run log. Same exit semantics; exit 3 is `NOT DIRECTLY VERIFIED` |
| Comparison Standards, tolerances, MATCH / DIVERGED / NOT DIRECTLY VERIFIED vocabulary, "missing evidence is never a match" | **Reused unchanged** |
| Read-tool visual figure review | **Reused unchanged** |
| Reproduction Report as sole state document; Session Continuity; restart prompt | **Reused** with the template's Package Verification variant |
| `decompile_notebook.*`, `normalize_project_dir.py`, `audit_reproduction_paths.py` | **Not used.** There is no notebook to decompile. Package scripts set their root dynamically (`Path(__file__).resolve().parent`), so the path audit's single static `PROJECT_DIR` assignment does not apply (inferred from its documented contract in RV-1 step 7). RV-P uses the isolation audit below instead |
| Per-script `_repro_a` / `_repro_b` modifications | **Not permitted.** The package must run unchanged. Any fix is a package defect that goes back to Manuscript Preparation |
| Isolation audit; output deletion; environment-equivalence check; per-claim comparison at two precisions; SC-01–SC-15 hygiene results; AEA classification, reason codes, and priority tags; data-rights status summary; submission-ready gate | **New** |

### User Decisions (Confirm at Mode Confirmation and at Gate RV-P1)

| Decision | Default | Options | Why |
|----------|---------|---------|-----|
| Data path for the proof run | Package default (frozen extracts) | Package default / from-raw | `run_with_capture.sh` passes no arguments to the script (observed: line 390 runs `"$INTERPRETER" "$SCRIPT_PATH"`). The proof run can therefore only exercise `main.py`'s argument-free default. A from-raw proof is possible only if the package ships a separate argument-free entry script for it. Otherwise record acquisition as untested, as in RV frozen mode |
| Restricted-claims acknowledgement | Required when any source is not shipped | Confirm list | Claims built on non-shipped data cannot be regenerated. They can only be flagged restricted with a synthetic test path. The user confirms the list before the run |

### RV-P Workflow

```
Manuscript MP-4 hand-off  OR  user points to a replication package
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ RV-P1: Intake, Isolation & Environment  (orchestr.) │
│  1. Create YYYY-MM-DD_[ShortTitle]_PackageVerif./   │
│  2. Snapshot package + manuscript evidence          │
│     → original_files/ (sha256 inventory)            │
│  3. Copy original DAAF logs per crosswalk           │
│     → original_files/original_logs/                 │
│  4. Fresh copy → package_run/; delete outputs       │
│  5. Isolation audit + child-script install scan     │
│  6. Env. equivalence (Python lock + renv.lock)      │
│  7. Map claims → evidence → data rights             │
│  PSU-RVP1 · GATE: user confirms                     │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-P2: Proof Run & Comparison  (code-reviewer)      │
│  run main.py ONCE via run_with_capture.sh           │
│  claims at printed + full precision · tables ·      │
│  figures · logs · self-check SC-01–SC-15            │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-P3: Claims Verification  (data-verifier)         │
│  adversarial per-claim cross-check; returns only    │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-P4: Classification, Gate & Hand-off              │
│  (report-writer) SC-14/SC-15 · AEA class · reason   │
│  codes · priority-tagged action items · gate        │
│  PSU-RVP4 · return artifact paths to Manuscript     │
└─────────────────────────────────────────────────────┘
```

### RV-P Project Folder Structure

```
research/YYYY-MM-DD_[ShortTitle]_PackageVerification/
├── Reproduction_Report.md              # Package Verification variant (sole state document)
├── original_files/                     # Immutable evidence; never executed, never edited
│   ├── package_snapshot/               # Byte-for-byte copy of the package AS DELIVERED (incl. authors' outputs)
│   ├── PACKAGE_INVENTORY.md            # Per-file relative path, bytes, sha256 of the snapshot
│   ├── manuscript_evidence/            # claims_ledger.yaml, _values_manifest.json, _variables.yml,
│   │                                   #   references.bib, data_citations.bib, DATA_RIGHTS.md, DEPOSIT_METADATA.md,
│   │                                   #   DCAF_prefill.md, table/figure manifests, rendered PDF/DOCX
│   └── original_logs/                  # Upstream final-version scripts with appended DAAF logs,
│                                       #   copied per PROVENANCE_CROSSWALK.csv (log comparison only)
├── package_run/                        # Fresh working copy; outputs deleted; the ONLY tree main.py runs in
│   └── main.py                         # Receives run_with_capture.sh's appended log (copy, not the package)
├── scripts/
│   └── repro_checks/                   # Verification instrumentation, each with its appended log:
│       ├── 01_env-equivalence.py       #   installed versions vs requirements-lock.txt
│       ├── 01b_r-env-equivalence.R     #   R packages only: installed.packages() vs renv.lock
│       ├── 02_claims-comparison.py     #   per-claim printed + full precision → output/analysis/
│       └── 03_package-selfcheck.py     #   instantiated from package_selfcheck_template.py
├── output/
│   ├── analysis/claims_comparison.parquet
│   ├── analysis/selfcheck_03_package-selfcheck/   # self-check run 2 output (folder named after the script's
│   │                                   #   own stem: selfcheck_results.parquet, selfcheck_summary.md, pii_scan_hits.parquet)
│   └── preliminary_notes/              # Lossless RV-P2 / RV-P3 returns
└── logs/                               # collect_session_logs.sh
```

A re-verification after the package changes is a **new** project folder, using the date-suffix convention (`YYYY-MM-DDa_…`). Never reuse `package_run/`: its `main.py` already carries an execution log, and `run_with_capture.sh` refuses to run it again.

### RV-P1: Intake, Isolation & Environment

**Actor:** Orchestrator (directly). Verification diagnostics are written under `scripts/repro_checks/` and executed through `run_with_capture.sh`.

1. **Intake set.** Require all of the following. If any is missing, STOP and name it:
   - the package directory (Manuscript hub default: `{HUB}/replication/{PACKAGE_LABEL}/`, with `PACKAGE_LABEL = YYYY-MM-DD[a]_package`, plus `_run{K}` when an assembler run copy built it);
   - the manuscript evidence: `{HUB}/ledgers/claims_ledger.yaml`, `{HUB}/manuscript/_values_manifest.json`, `{HUB}/manuscript/_variables.yml`, every bibliography listed under `bibliography:` in `{HUB}/manuscript/_quarto.yml` (`references.bib` and `data_citations.bib`; self-check run 2 reads every `.bib` in `manuscript_evidence/` for SC-03), the table and figure manifests, and the rendered manuscript;
   - `DATA_RIGHTS.md`, `DEPOSIT_METADATA.md`, and `DCAF_prefill.md` (MP-4 step 7 drafts the last two before self-check run 1; the post-proof self-check reads these copies, step 6 of RV-P2, and its SC-07 fails without them);
   - `PROVENANCE_CROSSWALK.csv`.
   Refuse a ledger that still contains `is_example` rows. Exclude `superseded` claims, and list them separately.
2. **Create the project.** Create `research/YYYY-MM-DD_[ShortTitle]_PackageVerification/`. It must not already exist.
3. **Snapshot evidence.** Copy the package byte-for-byte to `original_files/package_snapshot/` and the manuscript evidence to `original_files/manuscript_evidence/`. Write `PACKAGE_INVENTORY.md` (relative path, bytes, sha256 per file). Verify the copied counts and sizes against the source, as in RV-1 step 5c. The delivered package and the hub are never modified.
4. **Copy original logs.** For each crosswalk row, copy the upstream final-version script (with its appended DAAF log) to `original_files/original_logs/<package script path>`. This is the only upstream read in RV-P, and it lands outside the run tree. Missing rows are recorded as `NOT DIRECTLY VERIFIED` log evidence.
5. **Fresh copy and clean slate.**
   - Copy the snapshot to `package_run/`.
   - Delete every declared output from `package_run/`: regenerated results, tables, figures, the values manifest and `_variables.yml` the package rebuilds, and any shipped `main.log`. The declared outputs come from the package's list of tables and programs plus `main.py`'s own clear-outputs list.
   - Never delete shipped inputs (`data/raw/`, frozen extracts, synthetic test data).
   - Record each deleted path. The authors' versions survive in `package_snapshot/` as the comparison baseline.
6. **Isolation audit.** The requirement is that the run has **no read access to upstream research projects**. The container cannot revoke read permission without changing upstream projects, which is forbidden. So enforce isolation by evidence and state its bound. Quote each probe and its output:
   - (a) Absolute-path scan of every executable or config file in `package_run/` (`.py`, `.R`, `.sh`, `.ps1`, `.yml`, `.yaml`, `.toml`, `.json`). Scan for `/daaf/`, for each upstream project root listed in SOURCES/crosswalk, and for Windows drive or backslash paths. Documentation files that legitimately name original paths, such as the crosswalk and README provenance notes, are listed but excluded; so are full-line comments and Python module docstrings in shipped programs (provenance text such as the hub build templates' run command, never executed; the assembler's own `/daaf` check skips them for the same reason, `replication-package.md` § 6 step 3). Shipped JSON/YAML manifests are not excluded: the assembler rewrites their paths to package paths, so a `/daaf/` hit there is a real finding. Two further known hits are listed but excluded, with the reason: the DAAF-container marker `/etc/daaf/ubuntu-snapshot`, in `code/00_setup.*` (a refusal check) and in `main.py` (`DAAF_MARKER`, the renv autoloader guard); both only test whether the file exists and never read upstream; and renv's generated `renv/activate.R`, which names user cache folders such as `~/.cache/R/renv` (observed in the installed template `renv/resources/activate.R:1220-1222`) and which the proof never executes because the autoloader is off (step 8).
   - (b) `find package_run -type l` must print nothing (no symlinks out of the tree).
   - (c) Flag every `../` that would resolve above the package root.
   - (d) After the run (RV-P2), list upstream files modified since the run start (`find <upstream_root> -newermt "<run start>"`). This must be empty.
   **Bounded assurance:** (a)–(c) prove that no static path reaches upstream. (d) proves that no upstream write happened. Neither proves the absence of dynamically constructed reads. Recommend that the user also run the package on a clean machine outside DAAF; the AEA "strongly encourage[s] running in batch" there.
7. **Child-script install and secret scan.** `run_with_capture.sh` scans only the script it wraps (`main.py`). It cannot see `code/**` children, which `main.py` launches with `subprocess`. Grep every shipped `.py`/`.R`, except `code/00_setup.*` and renv's generated `renv/activate.R`, with the wrapper's own `SCAN_TOKENS` patterns (reference them from `scripts/run_with_capture.sh`; do not copy them here). Any hit blocks the run. `renv/activate.R` is excluded because the proof never runs it (step 8) and because it carries a restore hint inside a message string that the R tokens would match (observed: `renv/resources/activate.R:1038` in the installed renv; the shipped file is generated from that template, inferred). `main.py` itself must not contain install tokens even in docstrings or strings: the wrapper ignores only full-line `#` comments and would refuse with exit 3. Setup instructions belong in the README and `00_setup.*`.
8. **Environment equivalence. Never run setup or install scripts in DAAF.** `code/00_setup.sh`/`.ps1`/`.R` are recorded as **not executed** (they would install packages at runtime). A package whose Python code imports no third-party module ships no `requirements-lock.txt` and no `code/00_setup.sh`/`.ps1` (`replication-package.md` § 8); record Python package equivalence as N/A with that reason, and check only the Python version. Otherwise write `scripts/repro_checks/01_env-equivalence.py` and run it through `run_with_capture.sh`. It:
   - parses `package_run/requirements-lock.txt` (`name==version` plus environment markers);
   - evaluates the markers with `packaging.markers` (installed: `packaging` 26.3, observed via `uv pip list` on 2026-10-03);
   - normalizes names per PEP 503;
   - compares each locked version with `importlib.metadata.version()`;
   - checks the Python version against the README's stated version.
   Status vocabulary: MATCH / PATCH / MINOR / MAJOR / REMOVED (locked but absent) / NOT DIRECTLY VERIFIED (unparseable line, marker error). Locked-but-inapplicable-marker lines are listed separately.

   **R packages (when the package ships `renv.lock`).** The R pin evidence is `renv.lock`, written at assembly by `renv::snapshot()` from the image's R library (`replication-package.md` § 8). Write `scripts/repro_checks/01b_r-env-equivalence.R` and run it through `run_with_capture.sh`. It reads `package_run/renv.lock` with `renv::lockfile_read()` (not an install call; the wrapper's R tokens block only renv's install, restore, update, and rebuild), compares each locked version with `installed.packages()`, and compares the lockfile's R version with `getRversion()` and with the README's stated version. Status vocabulary: MATCH / DIFFERS / REMOVED (locked but absent). It must never call renv's restore: the wrapper would refuse the script (exit 3), and DAAF never installs. Also confirm that `package_run/main.py` carries the template's renv autoloader guard, and quote the probe: `grep -n "RENV_CONFIG_AUTOLOADER_ENABLED\|DAAF_MARKER" {PROJECT_DIR}/package_run/main.py` must show the `DAAF_MARKER` definition and the assignment inside the marker check (RV-P2 step 1). A `main.py` without it is a package defect: STOP and return the package to Manuscript Preparation for re-assembly.

   Two bounds apply. First, the checks prove that the proof run used the locked versions. They do **not** prove that `00_setup` installs them on a replicator's machine, so the setup programs (`code/00_setup.sh`/`.ps1`, and `code/00_setup.R` with its `renv::restore()`) stay `NOT DIRECTLY VERIFIED (never executed in DAAF by design)`. Second, the proof uses the image's R library, not a restored project library: inside DAAF, `main.py`'s guard sets `RENV_CONFIG_AUTOLOADER_ENABLED=FALSE` for its R children, so `.Rprofile` does not bootstrap renv (RV-P2 step 1).
9. **Claim → evidence → rights map.** For every in-scope claim (`kind` of own-analysis or descriptive-context), resolve each `evidence` entry: values-manifest key → producer script → source parquet → S-id → `DATA_RIGHTS.md` record.
   - **Literature claims** are out of package scope by design. They are verified by MP-4's citation-integrity step and listed as scope-design exclusions, outside the denominators.
   - **Literature and prior-round values keys** (`lit_*`, `prev_*`; `source_kind` `lit_claim` / `prev_round`) are out of package scope by design too: the package contains no literature or prior-round content, its values script has those specs emptied, and its README lists the keys as scope-design exclusions (`replication-package.md` § 6 step 1). They are not compared, are not rows in `claims_comparison.parquet`, and do not lower the assessment of a claim that also cites package-scope keys. A claim whose evidence is only such keys is a scope-design exclusion.
   - **Restricted claims** are claims whose evidence needs data with `ship_raw` and `ship_derived` both false and no frozen extract. Mark them RESTRICTED and identify their synthetic test path. A restricted claim with no synthetic test path is a gate failure.
10. **Populate** the Package Verification variant of `Reproduction_Report.md`: intake inventory, deleted outputs, isolation audit, environment equivalence, claim map, data-rights status, and scope decisions.

**Gate RV-P1 (user-blocking):** The following must all hold, and then the user reconfirms the decisions and the restricted-claims list at PSU-RVP1:
- intake set complete and snapshot verified;
- outputs deleted and recorded;
- isolation probes (a)–(c) clean;
- child-script scan clean;
- environment equivalence recorded;
- every in-scope claim mapped.

**STOP if:** the intake is incomplete, the destination exists, the ledger has example rows, an isolation probe hits, the child-script scan hits, or a restricted claim lacks a synthetic test path.

### RV-P2: Proof Run & Comparison

**Actor:** code-reviewer (the RV-2 reproducer role, with the RV-P differences stated in the prompt).

1. **Run once.** `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/package_run/main.py`, with no environment prefix, also when the package ships `renv.lock`. Record the run start timestamp, the wrapper exit code, and the runtime.
   - Why no prefix is needed: `main.py` starts each R program in the package root, where `.Rprofile` loads `renv/activate.R`; with renv's autoloader on, it would try to bootstrap renv into the package's project library, a runtime install (inferred; that path was deliberately not run). The template's `main.py` guards against this itself: when the DAAF marker `/etc/daaf/ubuntu-snapshot` exists, it sets `RENV_CONFIG_AUTOLOADER_ENABLED=FALSE` in its children's environment and logs `DAAF container detected -> renv autoloader disabled for R programs (image library used)` (observed: `main_template.py`, Run section). With that variable set, a child R in a modelled package used only the image library and did not load renv (observed, `replication-package.md` § 8). Replicator machines lack the marker, so there the autoloader stays on and the restored library is used. RV-P1 step 8 confirmed the guard is present; if that evidence is absent, STOP without execution (do not add a prefix or edit `main.py`).
   - The wrapper runs from the caller's working directory, not the package root, so this also tests that `main.py` does not depend on the working directory.
   - Exit 74 follows `ERROR_RECOVERY.md` § Execution Wrapper Evidence Outcomes.
   - A non-zero exit is not retried with edits. Compare whatever was produced, and record the failure with its reason code.
   - The Bash tool's maximum timeout is 600000 ms (tool contract). DAAF ships `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, so a longer package cannot complete inside DAAF. Record `Insufficient time available to replicator`, and recommend an outside-DAAF run.
2. **Claims at two precisions.** Write `scripts/repro_checks/02_claims-comparison.py` and run it through `run_with_capture.sh`. It reads the ledger, the original `_values_manifest.json` (from `manuscript_evidence/`), and the regenerated manifest (in `package_run/`). For each values-manifest key behind each claim it compares:
   - (a) the **printed** formatted string, exactly;
   - (b) the **full-precision** raw value: exact for integer, string, boolean, and temporal values; 1e-6 relative tolerance for floats, per Comparison Standards.
   A key is MATCH only when both match. A printed match with a full-precision divergence is DIVERGED, with the note "printed value unchanged". A missing key on either side is NOT DIRECTLY VERIFIED. A key whose source the RV-P1 map marks restricted is RESTRICTED (its own status here; for the overall RV assessment it counts as `NOT DIRECTLY VERIFIED`, RV-P4). `lit_*` / `prev_*` keys are skipped (RV-P1 step 9). The script prints every row to its log and saves `output/analysis/claims_comparison.parquet` with exactly this schema, which the post-proof self-check (step 6) enforces:

   | Column | Content |
   |--------|---------|
   | `key` | values-manifest key (package scope only) |
   | `claim_ids` | list of the claims-ledger IDs whose evidence cites the key |
   | `status` | one of `MATCH`, `DIVERGED`, `NOT DIRECTLY VERIFIED`, `RESTRICTED` (uppercase, exactly) |

   Further columns (printed and full-precision values, notes) are allowed. A claim's assessment is the worst of its evidence entries.
3. **Tables.**
   - Run `compare_reproduction_artifacts.py --mode parquet` on each table's underlying data, and `--mode exact` on each rendered include (`tbl-*.md` or equivalent). Compare the snapshot's authors' version with the regenerated file.
   - Preserve the JSON and the exit codes. Exit semantics are unchanged.
4. **Figures.** Use the strongest evidence available:
   - (a) the underlying figure data, via parquet mode;
   - (b) the figure file's sha256: the authors' version from `PACKAGE_INVENTORY.md`, the regenerated file from a `sha256sum` probe (quote both). Not the comparator's exact mode: it rejects `.png`/`.svg` as "figure visuals" before checking the mode (§ What Is Reused vs. New);
   - (c) if the hashes differ, side-by-side Read-tool review of the PNG.
   A figure is MATCH when its data matches (or no data artifact is declared) and either its bytes or the visual review match. If the bytes differ and no viewable PNG exists, the image dimension is NOT DIRECTLY VERIFIED.
5. **Logs.** For each `original_files/original_logs/` script, run `compare_execution_logs.py <original_script> {PROJECT_DIR}/package_run/main.py`. `main.py`'s appended log holds every child's output, so duplicate metric identities across scripts will often return exit 3 (INCONCLUSIVE). That is `NOT DIRECTLY VERIFIED`, never success.
   - Logs are **supporting** evidence. A DIVERGED log metric must be investigated and recorded.
   - A NOT DIRECTLY VERIFIED log metric does not by itself fail a claim, because claims are verified directly through the values manifest.
   - Separately, scan the shipped proof-run `main.log` (teed by `main.py`) for absolute `/daaf/` paths. It ships with the package (the AEA publishes proof-run logs), so it must use package-relative paths only.
6. **Hygiene: self-check run 2 (SC-01–SC-15), after the proof.** Instantiate `package_selfcheck_template.py` as `scripts/repro_checks/03_package-selfcheck.py` with the run-2 Config (`replication-package.md` § 11): `SELFCHECK_RUN = 2`, `PACKAGE_LABEL` (the delivered label), and `RV_PROJECT_DIR = {PROJECT_DIR}`; the template derives the rest. It reads the shipped files from `original_files/package_snapshot/` (the package as delivered, never the regenerated outputs in `package_run/`), the proof log from `package_run/logs/main.log`, the rights, bib, deposit-metadata, and DCAF copies from `original_files/manuscript_evidence/`, the per-key results from `output/analysis/claims_comparison.parquet`, and writes its output folder under `output/analysis/`. Run it through `run_with_capture.sh` after step 2. SC-13 then reads `package_run/logs/main.log`; SC-14 reads the per-key results and stops with an error on a missing column or an unknown status label. The pre-proof run 1 at assembly reported SC-13/SC-14 as NOT RUN by design. SC-15 is provisional; RV-P4 assigns the final AEA class and reason codes. A self-check exit 1 (CRITICAL) is a recorded gate result, never fixed in RV-P.
7. **Write-isolation probe.** Run probe 6(d) from RV-P1 and record the result. When the package ships `renv.lock`, also run `find {PROJECT_DIR}/package_run/renv -mindepth 1 -maxdepth 1 -type d` and quote it: it must print nothing (no `renv/library` or other renv-built folder). Also quote the `DAAF container detected` line from `package_run/logs/main.log` (for example, `grep -n "DAAF container detected" {PROJECT_DIR}/package_run/logs/main.log`). Together they are the evidence that the autoloader stayed off.
8. **Update the report.** Fill in the Proof Run, Per-Claim, Table, Figure, Log, and Hygiene sections, and Session Continuity.

**Gate RV-P2 (automated):** single run completed or failed with evidence, every in-scope claim/table/figure assessed, hygiene results recorded, write-isolation probe recorded.

### RV-P3: Claims Verification

**Actor:** data-verifier (read-only; RV-3 override applies with the input substitutions below). It reads execution logs and Markdown, not parquet: it relies on the claims-comparison script's printed rows and the preserved helper JSON. The orchestrator persists the full return to `output/preliminary_notes/{date}_rvp3_claims-verification.md`, then transcribes the results into the report.

### RV-P4: Classification, Gate & Hand-off

**Actor:** report-writer (synthesis). The orchestrator derives all counts from the report's tables before dispatch, never from memory.

**AEA classification (verbatim levels and thresholds; REPLICATION.md, AEA Data Editor replication-template):**
- **Full reproduction**
- **Full reproduction with minor issues**
- **Partial reproduction**: "a significant number (>25%) of programs and/or numbers are different"; also, "if some data is confidential and not available, then a partial reproduction applies."
- **Not able to reproduce**: "only a small number of numbers were successfully generated (<25%)."

Two DAAF operationalizations are inference, not AEA text, and must be labeled as such in the report:
- **Denominators.** "Numbers" are the in-scope claims-ledger evidence entries. "Programs" are the shipped `code/**` scripts that `main.py` runs.
- **The 0–25% band.** A differing share at or below 25% (and above zero) is classified "with minor issues". Any RESTRICTED claim forces at least "partial", per the confidential-data rule.

**Reason codes (verbatim; mark each that applies, with evidence):** `Discrepancy in output` · `Bugs in code` · `Code missing` (sub-code `Data preparation code missing`) · `Code not functional` · `Software not available to replicator` · `Insufficient time available to replicator` · `Insufficient computing resources available to replicator` · `Data missing` · `Data not available` · `Missing README`.

**Action-item priority (verbatim order): `CRITICAL` > `CODE` > `FILES` > `METADATA`.** Rights violations are CRITICAL: "legally/rights-restricted content… data the authors do not have the right to redistribute. These block acceptance outright." Each item is routed `m` (manuscript), `d` (deposit), or `both`. A shipped file with no attested `DATA_RIGHTS.md` record (SC-02) or an unconfirmed PII hit (SC-09) is CRITICAL.

**Overall RV assessment:** FULLY / PARTIALLY / NOT REPRODUCED. These use the RV-4 criteria unchanged, applied to in-scope claims, tables, figures, and required dimensions. RESTRICTED claims are `NOT DIRECTLY VERIFIED` and cap the verdict at PARTIALLY, consistent with the AEA confidential-data rule.

**Submission-ready gate (Gate RV-P4):** the package is **SUBMISSION-READY** only when **every in-scope claim is MATCH**, or **is RESTRICTED with a synthetic test path that executed successfully** and is flagged in the README's list of tables. In addition, **no CRITICAL action item may be open**: the D4 rights gate and the AEA block acceptance outright on rights violations. Any other outcome is **BLOCKED**, with the action items as the fix list. The gate is deliberately stricter than the AEA classification: a "with minor issues" package with any DIVERGED claim is still BLOCKED.

**Hand-off to Manuscript Preparation (by artifact path).** RV-P never edits the package, the hub, or the ledger; Manuscript Preparation's orchestrator is the single writer of its ledgers. The return names:
- `{PROJECT_DIR}/Reproduction_Report.md` (verdict, AEA classification, gate result, action items);
- `{PROJECT_DIR}/output/analysis/claims_comparison.parquet` and `{PROJECT_DIR}/scripts/repro_checks/02_claims-comparison.py` (its log holds per-claim rows for non-Bash agents);
- `{PROJECT_DIR}/package_run/logs/main.log` (the proof-run log; MP-4 copies it into the package, because the AEA publishes proof-run logs). The MP-4 step 7b close-out is the only post-proof change allowed without a new RV-P run: copy in the proof run's `logs/`, fill the README `RUNTIME` and `HARDWARE` blocks from it, and re-render `README.pdf` (`replication-package.md` § 6, Immutability);
- the RV-P3 preliminary note.

MP-4 then updates each claim's `verification` field from the report, routes action items (code/files back to package assembly, metadata to README/DEPOSIT_METADATA, manuscript-routed items to MP-3), and, after any package change, requests a new RV-P run.

### RV-P Invocation Templates

**RV-P2 (code-reviewer):**

```python
Agent({
    description: "RV-P2: Package proof run and comparison",
    prompt: """[prompt below]""",
    subagent_type: "code-reviewer"
})
```

```
**BASE_DIR:** /daaf
**PROJECT_DIR:** {absolute_verification_project_path}
All project-relative paths resolve from PROJECT_DIR. All repo-level paths resolve from BASE_DIR.

**TASK:** Run the replication package's entry point once and compare every regenerated claim, table, figure, and log against the delivered package.

**MODE:** Reproducibility Verification — RV-P2 (Package Proof Run & Comparison). Apply your RV-2 reproducer overrides EXCEPT: no `_repro_a`/`_repro_b` modifications — the package must run unchanged; any failure is a package defect to record, not fix.

**RUN TREE:** `{PROJECT_DIR}/package_run/` (outputs already deleted at RV-P1). Do not read or write any upstream research project.
**DELIVERED BASELINE:** `{PROJECT_DIR}/original_files/package_snapshot/` (authors' outputs; immutable)
**MANUSCRIPT EVIDENCE:** `{PROJECT_DIR}/original_files/manuscript_evidence/` (claims_ledger.yaml, _values_manifest.json, _variables.yml, references.bib, data_citations.bib, DATA_RIGHTS.md, DEPOSIT_METADATA.md, DCAF_prefill.md, table/figure manifests)
**SELF-CHECK OUTPUT:** `{PROJECT_DIR}/output/analysis/selfcheck_03_package-selfcheck/` (written by step 5; named after the script's own stem)
**ORIGINAL LOGS:** `{PROJECT_DIR}/original_files/original_logs/`
**IN-SCOPE CLAIMS:** [claim IDs and evidence entries from the RV-P1 map; restricted claims with their synthetic test paths; scope-design exclusions listed separately]
**RV-P1 EVIDENCE:** isolation probes (a)–(c) clean [cite]; child-script scan clean [cite]; environment equivalence [overall + mismatches]; when `renv.lock` ships, main.py renv autoloader guard present [cite the RV-P1 step 8 grep]. If any is absent or not clean, STOP without execution.

**INSTRUCTIONS:**
1. Execute once: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/package_run/main.py` — the plain command, no environment prefix, also when `package_run/renv.lock` exists (main.py's own DAAF guard switches renv's autoloader off inside the container; RV-P1 confirmed the guard). Record run start, wrapper exit code, runtime. Exit 74 → ERROR_RECOVERY.md § Execution Wrapper Evidence Outcomes. Do not edit and re-run.
2. Write and run `{PROJECT_DIR}/scripts/repro_checks/02_claims-comparison.py` (file-first, IAT): per values-manifest key, printed string exact AND full-precision raw value (exact; floats 1e-6 relative). MATCH needs both; printed-only match is DIVERGED ("printed value unchanged"); missing either side is NOT DIRECTLY VERIFIED; restricted keys (RV-P1 map) are RESTRICTED; skip `lit_*`/`prev_*` keys (scope-design exclusions). Print every row; save `{PROJECT_DIR}/output/analysis/claims_comparison.parquet` with columns `key`, `claim_ids`, `status` (status exactly one of MATCH / DIVERGED / NOT DIRECTLY VERIFIED / RESTRICTED; extra columns allowed).
3. Tables: `compare_reproduction_artifacts.py --mode parquet` on table data and `--mode exact` on rendered includes (snapshot vs regenerated). Figures: data (parquet) → file sha256 (authors' version from `original_files/PACKAGE_INVENTORY.md`, regenerated file from a quoted `sha256sum` probe; NOT the comparator, which rejects `.png`/`.svg`) → Read-tool visual review of PNGs when hashes differ. Preserve all JSON and exit codes.
4. Logs: `compare_execution_logs.py <original_logs script> {PROJECT_DIR}/package_run/main.py`; exit 3 is NOT DIRECTLY VERIFIED. Scan `package_run/logs/main.log` for absolute `/daaf/` paths.
5. After step 2, instantiate `{BASE_DIR}/.claude/skills/academic-manuscript/assets/package_selfcheck_template.py` as `{PROJECT_DIR}/scripts/repro_checks/03_package-selfcheck.py` with the post-proof (run 2) Config: `SELFCHECK_RUN = 2`, `PACKAGE_LABEL = "[delivered label]"`, `RV_PROJECT_DIR = Path("{PROJECT_DIR}")`; the template derives the rest (shipped files from `original_files/package_snapshot/`, proof log from `package_run/`, rights/bib/deposit-metadata/DCAF from `original_files/manuscript_evidence/`, `claims_comparison.parquet`, output under `output/analysis/`); run it; carry SC-01–SC-15 results (SC-15 provisional). Exit 1 is a recorded gate result, not a defect to fix.
6. Run `find <each upstream root> -newermt "<run start>"`; quote the command and output (must be empty). If the package ships `renv.lock`, also run `find {PROJECT_DIR}/package_run/renv -mindepth 1 -maxdepth 1 -type d` and quote it (must be empty: no renv-built project library), and quote `grep -n "DAAF container detected" {PROJECT_DIR}/package_run/logs/main.log` (must show the autoloader-disabled line).
7. Update `{PROJECT_DIR}/Reproduction_Report.md` (Package Verification variant): Proof Run, Per-Claim Verification, Tables, Figures, Logs, Hygiene, Session Continuity. Derive counts from the rows.

**OUTPUT FORMAT (2000-word hard cap):** run status + exit code + runtime; counts (claims, tables, figures, log metrics) MATCH / DIVERGED / NOT DIRECTLY VERIFIED; every DIVERGED item with likely cause; SC-01–SC-15 failures with AEA tag; candidate reason codes; write-isolation result; files created.
```

**RV-P3 (data-verifier):**

```python
Agent({
    description: "RV-P3: Verify manuscript claims against package proof run",
    prompt: """[prompt below]""",
    subagent_type: "data-verifier"
})
```

```
**BASE_DIR:** /daaf
**PROJECT_DIR:** {absolute_verification_project_path}

**TASK:** Adversarially verify every in-scope manuscript claim against the package proof-run evidence.

**MODE:** Reproducibility Verification — RV-P3. Apply your RV-3 override with these input substitutions: the claims ledger replaces the original Report; the delivered package snapshot replaces the original artifact root; `package_run/` replaces the reproduced artifact root.

**CLAIMS LEDGER:** `{PROJECT_DIR}/original_files/manuscript_evidence/claims_ledger.yaml`
**PER-CLAIM ROWS:** execution log appended to `{PROJECT_DIR}/scripts/repro_checks/02_claims-comparison.py`
**HELPER EVIDENCE + REPORT:** `{PROJECT_DIR}/Reproduction_Report.md` (preserved comparator JSON, figure reviews, hygiene results, data-rights status)
**DATA RIGHTS:** `{PROJECT_DIR}/original_files/manuscript_evidence/DATA_RIGHTS.md`

**INSTRUCTIONS:**
1. For each in-scope claim, confirm every evidence entry was compared at printed AND full precision, and that the assessment is the worst of its entries.
2. Confirm RESTRICTED claims trace to non-shipped sources in DATA_RIGHTS.md and have a synthetic test path that executed; otherwise they are gate failures.
3. Check each shipped data file traces to an attested DATA_RIGHTS record (CRITICAL otherwise).
4. Challenge every MATCH whose evidence is indirect; an absent side is never a match.

**OUTPUT FORMAT (2000-word hard cap):** per-claim rows (claim | evidence | printed orig/repro | full orig/repro | assessment | restricted? | notes); counts; CRITICAL findings; disagreements with RV-P2 assessments.
```

**RV-P4 (report-writer):** use the RV-4 prompt template with these substitutions: TASK "Write the Package Verification synthesis"; inputs add the RV-P3 preliminary note; instructions replace step 6 with "determine the overall RV assessment, the AEA classification (verbatim levels; label the DAAF denominator and 0–25% band operationalizations as inference), applicable reason codes, priority-tagged action items (CRITICAL > CODE > FILES > METADATA, each routed m/d/both), SC-14/SC-15, and the submission-ready gate (SUBMISSION-READY only if every in-scope claim is MATCH or RESTRICTED with an executed synthetic test path, and no CRITICAL item is open)". Output: the gate result, the classification, and a 3-sentence summary.

### RV-P PSU Templates

**PSU-RVP1** (after RV-P1, before the run): package and snapshot inventory (files, bytes, inventory path); outputs deleted (count); isolation probes (a)–(c) with the commands and the bounded-assurance statement; child-script scan result; environment equivalence (overall, mismatches, setup program not executed); claims in scope / restricted (with synthetic paths) / excluded by design (literature, superseded); data-rights status per source; the data-path decision. Close with: **"Shall I run the package's entry point once with these settings?"**

**PSU-RVP4** (after RV-P4): **Gate: SUBMISSION-READY / BLOCKED**; overall RV assessment; AEA classification; claims / tables / figures MATCH / DIVERGED / NOT DIRECTLY VERIFIED of N; restricted claims; reason codes; action items grouped by priority tag; the hand-off artifact paths; next step ("return to Manuscript Preparation MP-4" or "fix and re-verify").

### RV-P Boundaries

- **Always:** snapshot before touching anything; run `main.py` exactly once per verification project, with the plain wrapper command (when the package ships `renv.lock`, confirm `main.py`'s renv autoloader guard at RV-P1 and its `DAAF container detected` log line after the run); compare both precisions; keep logs as supporting evidence; quote every isolation probe; record setup programs as not executed; derive every count from report rows; keep literature-claim exclusions outside denominators.
- **Never:**
  - execute `code/00_setup.*` or any install;
  - edit the package, the hub, the ledger, or `DATA_RIGHTS.md`;
  - attest data rights on the user's behalf;
  - re-run `package_run/main.py`;
  - read upstream projects except the crosswalk-listed log copies at RV-P1 step 4;
  - count a RESTRICTED claim as MATCH;
  - mark SUBMISSION-READY with any DIVERGED claim or open CRITICAL item.
- **Ask first:** expanding scope beyond the ledger; running a from-raw proof (network acquisition); treating any CRITICAL finding as resolved.

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
| RV-P package verification complete (either gate result) | Manuscript Preparation (MP-4) | Return by artifact path per § RV-P4 Hand-off; orchestrator SKILL.md escalation row deferred until Manuscript Preparation registers |

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

**Turn-end briefing.** The PSU-RV checkpoints below are the heavyweight, blocking instances of DAAF's general Turn-End Briefing standard. Every *other* substantive turn that returns control to the user — an environment-mismatch decision point, an error-recovery pause during re-execution, a mid-stage return — still closes with a briefing of what happened since the user's last message, taken altogether. See the master statement in `SKILL.md` § User-Facing Communication Standards > "Turn-End Briefing."

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
- **Environment date (original → current):** `UV_EXCLUDE_NEWER` [value / ABSENT (pre-freeze)] → [value]; `UBUNTU_SNAPSHOT` [value / ABSENT (pre-freeze)] → [value]; base digest [MATCH / DIFFERS / TAG ONLY]; `P3M_SNAPSHOT_DATE` [value / ABSENT (pre-freeze)] → [value]; `--exclude-newer-package` overrides [MATCH / DIFFERS / none]
- **Overall Compatibility:** [COMPATIBLE / MINOR DIFFERENCES / SIGNIFICANT DIFFERENCES / UNKNOWN]
- **UNKNOWN / NOT DIRECTLY VERIFIED versions:** [list; include unpinned R packages and pre-freeze transitive Python dependencies rather than inferring exact versions]

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

> **Wave barrier discipline (async dispatch).** RV-2 is deliberately sequential — one script's code-reviewer dispatch at a time, in notebook order. Dispatches return inline under DAAF's shipped settings (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, observed on the pinned Claude Code 2.1.281), but without that setting, or on other versions, they complete via async task notifications, so the barrier still applies at the single-dispatch level: do not begin the next script's cycle, advance Session Continuity, or draw cross-script conclusions until the current dispatch has actually returned. When RV-2 escalation dispatches the debugger, treat that as part of the same script's cycle — wait for it before moving on. (Updating the Reproduction Report after each script's own return is intended incremental behavior, not a barrier violation: each script is its own single-member wave.) See the master statement in `SKILL.md` § Subagent Coordination > "Wave Barrier Discipline (Async Dispatch)."

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

Trigger points are **threshold-profile-conditional** (percentage OR absolute tokens, whichever fires first); each agent is measured against the profile selected from its own exact model ID. Profile selection is version-specific and independent of physical context-window mapping. Exact GPT 5.6 Sol and GPT-6 Astra share a separate validated profile with independent 60%/75%/90% percentage boundaries while retaining higher validated absolute gates (300k/400k/500k); Astra joins this profile at Sol parity, and Sol's own tier history is unchanged. Since 2026-09-29, by user policy decision rather than DAAF quality validation, `gpt-6-sol` and the `-pro` form of all three flagships also use this profile. For that profile, the terminal model slug must be exactly `gpt-5.6-sol`, `gpt-6-astra`, or `gpt-6-sol`, optionally followed by `-pro` and then optionally by `[1m]` (e.g., `gpt-6-sol-pro[1m]`); the identifier may be bare or may contain one or more provider path prefixes ending in `/`. Malformed left-boundary strings such as `xgpt-5.6-sol`, `foo-gpt-5.6-sol`, and `vendor/notgpt-5.6-sol` remain conservative, as do right-side suffix or trailing variants (including near-misses such as `gpt-6-astra-pro-x` and `gpt-6-sol[1m]-pro`). GPT is not part of the Claude Fable/Mythos model family. Terra and Luna (including `gpt-6-luna` and their `-pro` forms), mini, chat, date snapshots, future variants, and trailing modifiers remain conservative unless separately registered, even when the wider GPT family maps to a 1,050,000-token physical window (Astra's, GPT-6 Sol's, and GPT-6 Luna's physical windows are 1,050,000 tokens). See `agent_reference/CONTEXT_THRESHOLDS_REFERENCE.md` for the full selection rules, including normalization of provider-dotted Claude IDs such as `anthropic/claude-opus-5.5`. That 1,050,000 figure is itself route-conditional: it holds on the API-key and OpenRouter routes, while the ChatGPT-subscription (Codex) shim lane is backend-capped at **919,000 tokens**, measured directly for both `gpt-6-astra` and `gpt-5.6-sol` on 2026-09-05 (superseding an earlier 2026-07-16 Sol-only figure of ~370,000), which DAAF's hooks lane-gate automatically. At the 919,000-token cap, the exact-Sol/Astra 60%/75%/90% percentage boundaries are 551.4k, 689.25k, and 827.1k tokens, respectively, so the 300k/400k/500k absolute gates fire first. At the 1,050,000-token full window, the corresponding percentage boundaries are 630k, 787.5k, and 945k, so the absolute gates likewise fire first; the same exact-Sol/Astra quality profile applies on both lanes even though their physical windows differ.

| Threshold Profile | Membership | ELEVATED at | HIGH at | CRITICAL at |
|-------------------|------------|-------------|---------|-------------|
| **Claude Fable/Mythos validated extended-horizon** | Registered Claude Fable/Mythos models, plus `claude-opus-5-5` (bare and `[1m]`) — admitted 2026-09-23 by user policy decision, not by DAAF quality validation | ≥ 30% or ≥ 300k tokens | ≥ 40% or ≥ 400k tokens | ≥ 50% or ≥ 500k tokens |
| **GPT Sol/Astra extended-horizon** | Exact terminal model slugs, bare or provider-prefixed, each optionally followed by `[1m]`: `gpt-5.6-sol` and `gpt-6-astra` (validated), plus `gpt-6-sol` and the `-pro` form of all three (e.g. `gpt-6-sol-pro[1m]`) — admitted 2026-09-29 by user policy decision, not by DAAF quality validation — and `gpt-6.1-sol` (with its `-pro` form) — admitted 2026-10-12 by user policy decision, not by DAAF quality validation | ≥ 60% or ≥ 300k tokens | ≥ 75% or ≥ 400k tokens | ≥ 90% or ≥ 500k tokens |
| **Conservative-default** | all Opus models except `claude-opus-5-5` (above), Sonnet, unknown model IDs, every other GPT variant, GLM models, and all other alternative-provider models unless individually validated and registered | ≥ 40% or ≥ 150k tokens | ≥ 60% or ≥ 200k tokens | ≥ 75% or ≥ 250k tokens |

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
