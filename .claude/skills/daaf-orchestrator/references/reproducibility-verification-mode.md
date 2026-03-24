# Reproducibility Verification Mode

Verify that an existing analysis can be mechanically reproduced from its delivered marimo notebook. The orchestrator decompiles the notebook into individual scripts, re-executes each one, compares outputs against the original execution logs, and cross-references the original Report's claims against the reproduced results.

## User Orientation

After mode confirmation, briefly orient the user. Key points:

- You will reproduce an existing analysis by re-running every script extracted from its marimo notebook
- You will receive a Reproduction Report documenting what matched, what diverged, and any methodological concerns
- The original project is never modified — all reproduction work happens in a new project folder

**When to skip:** User has indicated familiarity with this mode or is a returning user.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## User Decisions (Confirm Twice)

Two decisions must be confirmed at **mode confirmation** AND reconfirmed **after RV-1** (once the inventory is visible):

| Decision | Default | Options | Why Confirm Twice |
|----------|---------|---------|-------------------|
| Re-fetch data from mirrors? | Yes (re-fetch) | Yes / No (use existing data files if available) | Mirror data may have changed; user may want to test with original data instead |
| Methodological review depth | Light (concerns only) | Light / Full (Five Lenses per script) | Full review is thorough but significantly slower |

At mode confirmation: present defaults, ask user to confirm or adjust.
After RV-1: present the script inventory count and ask user to reconfirm both decisions with the scope now concrete.

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
│  4. Copy Report + Notebook → original_files/        │
│  5. Copy run_with_capture.sh → scripts/             │
│  6. Run decompiler → original_files/scripts/        │
│  7. Create Reproduction_Report.md from template     │
│  8. Populate Script Inventory + Source Artifacts     │
│                                                     │
│  PSU: Present inventory, reconfirm scope decisions  │
│  GATE: User confirms before proceeding              │
└──────────────────────┬──────────────────────────────┘
                       │ User confirms
                       ▼
┌─────────────────────────────────────────────────────┐
│ RV-2: Sequential Re-execution & Comparison          │
│                                                     │
│  For each script (in notebook order):               │
│    1. Copy script → scripts/repro/{stage_dir}/      │
│    2. Strip execution log from copy                 │
│    3. Execute via run_with_capture.sh               │
│    4. Compare new output vs. original execution log │
│       - Row counts, schema, key statistics          │
│       - Checkpoint results (CP1-CP4)                │
│    5. If DIVERGED or FAILED: log deviation details  │
│    6. If modification required: create versioned    │
│       copy (_repro_a.py), document prominently      │
│    7. Assess methodological concerns (light/full)   │
│    8. Update Reproduction_Report.md immediately     │
│                                                     │
│  Continue through ALL scripts sequentially           │
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
│ RV-4: Synthesis                                     │
│                                                     │
│  1. Synthesize methodological concerns              │
│  2. Write Executive Summary                         │
│  3. Write Report Verification Summary narrative     │
│  4. Determine overall assessment:                   │
│     FULLY REPRODUCED / PARTIALLY / NOT REPRODUCED   │
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
2. Validate that the folder contains both a Report (`*_Report.md`) and a Notebook (`*.py` with `import marimo`)
3. Create new project folder: `research/YYYY-MM-DD_[OriginalProjectName]_Reproduction/`
4. Create subdirectories: `original_files/`, `original_files/scripts/`, `scripts/`, `scripts/repro/`
5. Copy the Report and Notebook into `original_files/`
6. Copy `run_with_capture.sh` from `/daaf/scripts/` into `scripts/`
7. Run the decompiler: `python /daaf/scripts/decompile_notebook.py <notebook_path> <project>/original_files/scripts/`
8. Create `Reproduction_Report.md` from `agent_reference/REPRODUCTION_REPORT_TEMPLATE.md`
9. Populate the Script Inventory table from the decompiler's `MANIFEST.md`, mapping fields as follows:
   - `#` and `Script` — map directly from MANIFEST
   - `Step` — extract from script filename (e.g., `01_fetch-ccd.py` → step `01`)
   - `Stage` — extract from parent directory (e.g., `stage5_fetch/` → stage `5`)
   - `Type` — infer from stage directory name (`fetch`, `clean`, `transform`, `analysis`)
   - `Original Output` — extract from the Cell 1 header metadata if available, otherwise `—`
   - `Repro Status` — initialize all rows to `PENDING`
10. Populate Source Artifacts table and Reproduction Environment section

**Gate RV-1:** All source artifacts present, decompiler succeeded, script inventory populated, user reconfirms scope decisions.

### RV-2: Sequential Re-execution & Comparison

**Actor:** code-reviewer agent (with reproduction-specific prompt)

**Why code-reviewer:** The code-reviewer's adversarial stance and Five Lenses of Skeptical Review make it ideal for this task. It already has file-first execution capability (enforce-file-first.sh), writes QA-style comparison scripts, and classifies findings by severity. For reproduction, it both re-executes and evaluates — combining the mechanical work with skeptical assessment.

**Per-script atomic cycle:**

1. **COPY:** Copy `original_files/scripts/{stage_dir}/{script_name}` to `scripts/repro/{stage_dir}/{script_name}`
2. **STRIP:** Remove the execution log from the copy. Find the line matching `# EXECUTION LOG` (or the `# =====` separator immediately preceding it) and delete from that point to EOF. After stripping, verify the file does NOT contain the string `# EXECUTION LOG` — `run_with_capture.sh` will refuse to execute scripts that already have a log marker.
3. **EXECUTE:** `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/repro/{stage_dir}/{script_name}`
4. **COMPARE:** Read both the original script (with original log) and the re-executed script (with new log). Compare:
   - Exit codes
   - Row counts from stdout
   - Column counts and schema
   - Checkpoint pass/fail results
   - Key statistics printed in validation output
5. **ASSESS:** Classify the result as REPRODUCED / DIVERGED / FAILED
6. **METHODOLOGICAL REVIEW:** Examine the script's analytical approach:
   - **Light mode (default):** Note only NOTABLE or CRITICAL concerns
   - **Full mode:** Apply the Five Lenses of Skeptical Review
7. **UPDATE REPORT:** Update Reproduction_Report.md — Script Inventory status, Per-Script Results section, Deviation Log if applicable, Methodological Concerns Log if applicable
8. **IF FAILED:** If the script fails and a modification is needed for it to run:
   - Create versioned copy: `{script_name%.py}_repro_a.py`
   - Document the modification prominently in Per-Script Results
   - Re-execute the modified version
   - Mark status as MODIFIED (not REPRODUCED)

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
**BASE_DIR:** {absolute_project_path}
All relative paths resolve from BASE_DIR.

**TASK:** Reproduce script #{N} of {total}: `{script_name}`

**MODE:** Reproducibility Verification — RV-2 (Sequential Re-execution & Comparison)

**ORIGINAL SCRIPT:** `{BASE_DIR}/original_files/scripts/{stage_dir}/{script_name}`
**REPRODUCTION TARGET:** `{BASE_DIR}/scripts/repro/{stage_dir}/{script_name}`

**INSTRUCTIONS:**
1. Copy the original script to the reproduction target path
2. Strip the execution log from the copy: find the line containing `# EXECUTION LOG`
   (or the `# =====` separator immediately preceding it) and delete from that point to EOF.
   After stripping, verify the file does NOT contain `# EXECUTION LOG` —
   run_with_capture.sh will refuse to execute scripts that still have a log marker.
3. Execute via: `bash {BASE_DIR}/scripts/run_with_capture.sh {BASE_DIR}/scripts/repro/{stage_dir}/{script_name}`
4. Compare the new execution log against the original script's execution log
5. Classify result: REPRODUCED / DIVERGED / FAILED
6. Methodological review depth: {LIGHT | FULL}
7. Update `{BASE_DIR}/Reproduction_Report.md`:
   - Script Inventory table: update Repro Status for script #{N}
   - Per-Script Results: fill in section for Script #{N}
   - Deviation Log: add row if any deviations found
   - Methodological Concerns Log: add row if concerns found
   - Session Continuity: update Last Script Completed and Next Script

**COMPARISON TOLERANCES:** See Reproduction Report template § Comparison Tolerances

**IF SCRIPT FAILS:**
- Create `{script_name%.py}_repro_a.py` with necessary fixes (max 2 versions: _repro_a.py, _repro_b.py)
- Document ALL modifications in Per-Script Results § Modifications Required
- Re-execute the modified version
- Mark status as MODIFIED, not REPRODUCED

**OUTPUT FORMAT (1000-word hard cap):**
Return a concise summary:
- Status: [REPRODUCED/DIVERGED/FAILED/MODIFIED]
- Key comparison metrics (row counts, checkpoint results)
- Deviations found (if any, with likely cause)
- Methodological concerns (if any, with severity)
- Files created/modified
```

**Sequencing:** Scripts are re-executed in the order they appear in the notebook (which matches the original execution order). Later scripts may depend on data produced by earlier scripts, so order must be preserved.

**No early termination:** Continue through ALL scripts even if some fail. The goal is a complete reproduction picture, not a pass/fail gate.

### RV-3: Report Verification

**Actor:** data-verifier agent (adversarial cross-artifact verification, read-only)

**Note:** The data-verifier agent is read-only (`permissionMode: plan`). It RETURNS its findings to the orchestrator, which then updates the Reproduction Report. This is consistent with how data-verifier operates at Stage 12 in Full Pipeline — it verifies and reports, never writes.

**Orchestrator post-processing:** After receiving the data-verifier's return, the orchestrator updates:
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
**BASE_DIR:** {absolute_project_path}
All relative paths resolve from BASE_DIR.

**TASK:** Verify the original Report's claims against reproduced analysis outputs.

**MODE:** Reproducibility Verification — RV-3 (Report Verification)

**ORIGINAL REPORT:** `{BASE_DIR}/original_files/{report_filename}`
**REPRODUCED SCRIPTS:** `{BASE_DIR}/scripts/repro/`
**REPRODUCTION REPORT:** `{BASE_DIR}/Reproduction_Report.md`

**INSTRUCTIONS:**
1. Read the original Report in full
2. Extract every quantitative claim (statistics, counts, percentages, coefficients)
3. Extract every figure reference
4. For each claim: locate the reproduced script that produced it, check the
   reproduced execution log for the matching value
5. For each figure: verify the reproducing script generated the figure file
6. For each key finding: assess whether the reproduced data supports the
   same conclusion

**OUTPUT FORMAT (1000-word hard cap):**
Return structured findings for orchestrator to populate the Reproduction Report:
- Claims verified: N of N (N% match)
- Figures reproduced: N of N
- Findings supported: N of N
- Per-claim detail: [claim text] | [original value] | [reproduced value] | [match?] | [notes]
- Per-figure detail: [figure name] | [reproduced?] | [visual match?] | [notes]
- Per-finding detail: [finding] | [supported?] | [confidence] | [notes]
- Any claims that could NOT be verified (with reason)
```

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
**BASE_DIR:** {absolute_project_path}

**TASK:** Write the synthesis sections of the Reproduction Report.

**MODE:** Reproducibility Verification — RV-4 (Synthesis)

**REPRODUCTION REPORT:** `{BASE_DIR}/Reproduction_Report.md`

**INSTRUCTIONS:**
1. Read the entire Reproduction Report (all per-script results, deviations,
   methodological concerns, report verification findings)
2. Write the Executive Summary section:
   - Overall reproducibility assessment
   - Script counts and percentages
   - 3-5 sentence summary of findings
   - 2-3 sentence summary of methodological concerns
3. Write the Methodological Concerns § Synthesis section:
   - Group related concerns
   - Assess collective impact on conclusions
   - Provide overall methodological assessment
4. Ensure the Report Verification Summary narrative is complete
5. Determine overall assessment: FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED

**ASSESSMENT CRITERIA:**
- FULLY REPRODUCED: All scripts reproduced or diverged only cosmetically; all Report claims verified; no modifications required
- PARTIALLY REPRODUCED: Most scripts reproduced; some substantive deviations or modifications; most Report claims verified
- NOT REPRODUCED: Multiple scripts failed or required modifications; key Report claims cannot be verified

**OUTPUT FORMAT (1000-word hard cap):**
Return the overall assessment and a 3-sentence summary of the reproduction findings.
```

---

## Project Folder Structure

```
research/YYYY-MM-DD_[OriginalProject]_Reproduction/
├── Reproduction_Report.md              # Central artifact (created RV-1, updated throughout)
├── original_files/
│   ├── [original_report].md            # Copied from original project
│   ├── [original_notebook].py          # Copied from original project
│   └── scripts/                        # Decompiled from notebook
│       ├── MANIFEST.md                 # Decompiler output manifest
│       ├── stage5_fetch/
│       │   ├── 01_fetch-*.py           # Original scripts with execution logs
│       │   └── ...
│       ├── stage6_clean/
│       ├── stage7_transform/
│       └── stage8_analysis/
└── scripts/
    ├── run_with_capture.sh             # Copied from /daaf/scripts/
    └── repro/                          # Re-executed scripts
        ├── stage5_fetch/
        │   ├── 01_fetch-*.py           # Re-executed with new logs
        │   └── ...
        ├── stage6_clean/
        ├── stage7_transform/
        └── stage8_analysis/
```

---

## Boundaries

### Always Do
- Process ALL scripts in the notebook, even if some fail
- Update the Reproduction Report after EVERY script re-execution
- Preserve the original project completely untouched
- Document ANY modification required to run a script, no matter how small
- Use versioned copies (_repro_a.py) for any modifications, following DAAF conventions
- Compare against tolerances defined in the Reproduction Report template

### Never Do
- Modify files in the original project folder
- Skip scripts without explicit user approval
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
| **Gate RV-1** | RV-1 | All source artifacts present; decompiler succeeded; Script Inventory populated; user reconfirms scope decisions | Decompiler fails; Report or Notebook missing |
| **Gate RV-2** | RV-2 | All scripts processed (each has status REPRODUCED, DIVERGED, FAILED, or MODIFIED); Reproduction Report updated for every script | User requests stop |
| **Gate RV-3** | RV-3 | All quantitative claims, figures, and findings verified; Report Verification section populated | N/A (always proceed to synthesis) |
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

**Your Scope Decisions (please reconfirm):**
- **Re-fetch data from mirrors?** Currently: [Yes/No]. [If Yes: data may differ from original. If No: uses existing data files.]
- **Methodological review depth?** Currently: [Light/Full]. [Light flags only notable concerns; Full applies the Five Lenses to every script.]

**What happens next:** I'll re-execute each script in notebook order, compare outputs against the originals, and update the Reproduction Report after each one. This runs through all [N] scripts without stopping unless you ask me to.

**Shall I proceed with these settings, or would you like to adjust?**
```

### PSU-RV4: Reproduction Findings

Present to the user after RV-4 completes:

```markdown
**Reproduction Complete**

**Overall Assessment:** [FULLY REPRODUCED / PARTIALLY REPRODUCED / NOT REPRODUCED]

**Summary:**
- **Scripts:** [N] of [N] reproduced successfully ([X]%)
- **Deviations:** [N] substantive, [N] cosmetic
- **Modifications Required:** [N] scripts needed changes to run
- **Report Claims Verified:** [N] of [N] ([X]%)

[2-3 sentence narrative from Executive Summary]

**Key Findings:**
[Top 3-5 findings, bulleted]

**Methodological Concerns:** [None / Brief summary]

The full Reproduction Report is at: `[path]`

**What would you like to do?**
- Review the Reproduction Report in detail
- Discuss specific deviations or concerns
- Fix issues in the original analysis (switches to Revision & Extension mode)
```

---

## Per-Script Execution Cycle (Formalized)

The RV-2 per-script cycle is lightweight compared to Full Pipeline's Composite Execution Pattern. The re-execution IS the review — the code-reviewer both re-executes and evaluates in a single invocation.

**Atomic cycle per script:**

| Step | Action | Detail |
|------|--------|--------|
| 0 | READ | Check Reproduction Report § Session Continuity for current position |
| 1 | COPY | Copy original script to `scripts/repro/{stage_dir}/` |
| 2 | STRIP | Remove execution log (verify no `# EXECUTION LOG` marker remains) |
| 3 | EXECUTE | Run via `run_with_capture.sh` |
| 4 | COMPARE | Compare new log against original log (apply tolerances) |
| 5 | UPDATE | Update Reproduction Report (Script Inventory + Per-Script Results + Deviation Log + Concerns Log + Session Continuity) |
| 6 | RETURN | Return concise summary to orchestrator |

**Error handling within the cycle:**
- If Step 3 fails: create `_repro_a.py` with minimal fixes, document modification, re-execute, mark MODIFIED
- If modification also fails: create `_repro_b.py` (max 2 versions), then mark FAILED
- If FAILED after 2 modification attempts: orchestrator may dispatch debugger (max 1 per script, max 3 per session)

---

## Revision Invocation Template

When a script fails during RV-2 and the code-reviewer's modification attempts also fail, the orchestrator may dispatch the debugger:

```python
Agent({
    description: "Debug: RV-2 script failure: {script_name}",
    prompt: """You are a Debugger. Read and follow the protocol in
    `{BASE_DIR}/.claude/agents/debugger.md`.

    **BASE_DIR:** {absolute_project_path}
    All relative paths in referenced files resolve from BASE_DIR.

    **CONTEXT:**
    Mode: Reproducibility Verification (RV-2)
    Original Script: {BASE_DIR}/original_files/scripts/{stage_dir}/{script_name}
    Failed Reproduction: {BASE_DIR}/scripts/repro/{stage_dir}/{script_name}
    Modified Version: {BASE_DIR}/scripts/repro/{stage_dir}/{modified_script_name}

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

| Utilization | Action |
|-------------|--------|
| 0-40% (NOMINAL) | Continue normally |
| 40-60% (ELEVATED) | Update Session Continuity after each script; monitor closely |
| 60-75% (HIGH) | Complete current script's atomic cycle; update Session Continuity; present checkpoint to user with restart guidance |
| 75%+ (CRITICAL) | Cease work; update Session Continuity; present restart prompt to user |

**Restart procedure:** User copies the Restart Prompt from the Reproduction Report's Session Continuity section, runs `/clear`, and pastes it. The new session reads the Reproduction Report to establish position and resumes from the next unprocessed script.

---

## Reproduction Report as State

Reproducibility Verification mode does NOT use `STATE.md`. The **Reproduction Report itself is the sole session state document**.

**Design rationale:** In Full Pipeline and Data Ingest, STATE.md exists separately because the primary deliverables are not updated incrementally during execution. The Reproduction Report, by contrast, is designed for continuous incremental updates after every script re-execution. It already tracks:

- **Current position** — Session Continuity § Current Position
- **Progress** — Script Inventory (every script has a status)
- **Findings** — Per-Script Results (filled incrementally)
- **Errors and deviations** — Deviation Log (running record)
- **Methodological observations** — Concerns Log (running record)
- **Scope decisions** — Scope Decisions table
- **Environment** — Reproduction Environment table
- **Restart context** — Session Continuity § Restart Prompt

A separate STATE.md would duplicate this without adding value.

**Update discipline:** The Reproduction Report MUST be updated after every atomic action:
- After each script re-execution (RV-2): Script Inventory + Per-Script Results + Session Continuity
- After report verification (RV-3): Report Verification sections
- After synthesis (RV-4): Executive Summary + Methodological Synthesis
- At every stage transition: Session Continuity § Current Stage
- Before any session break: Session Continuity § Restart Prompt
