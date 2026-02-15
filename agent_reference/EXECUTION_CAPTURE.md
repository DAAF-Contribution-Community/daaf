# File-First Execution Protocol

## Overview

This document is the **single source of truth** for how Python scripts are written, executed, captured, versioned, and managed in DAAF. Every agent that writes or executes Python code (research-executor, code-reviewer, debugger, notebook-assembler) follows this protocol.

**Why this protocol exists:** Scripts are the primary execution artifacts -- not notebooks, not interactive sessions. Each script is a self-contained, reproducible unit with an embedded execution log that proves exactly what code ran and what it produced. This gives every analysis a complete audit trail: code + output + version history.

**The philosophy:** Write first. Execute once. Capture everything. Never modify, only version.

---

## The Protocol

Every Python execution follows these steps in order. No exceptions.

```
WRITE  -->  EXECUTE  -->  CAPTURE  -->  VERSION (if failed)  -->  REPEAT
```

### Step 1: Write the Script to a File

Create the script file BEFORE executing any code. Use the standard template format from `SCRIPT_TEMPLATE.md`.

- Save to the appropriate stage directory (see Naming Conventions below)
- Include: shebang, metadata docstring, config section, sequential code, inline validation
- Follow IAT documentation standards (see `INLINE_AUDIT_TRAIL.md`)
- Scripts are **flat, sequential** Python -- no `def main()`, no `if __name__` guards, no helper function sections

### Step 2: Execute with the Wrapper

Run the script using the execution wrapper, which handles output capture and log appending automatically:

```bash
bash /path/to/research/[project]/scripts/run_with_capture.sh /path/to/research/[project]/scripts/stage{N}_{type}/{step}_{task-name}.py
```

**Single command only.** Do not chain with `&&` or `;`. Do not prefix with `cd`. Use absolute paths.

**Do NOT run `python script.py` directly.** Direct execution bypasses output capture and log appending.

### Step 3: Capture is Automatic

The wrapper automatically:
1. Executes the script and captures all stdout/stderr
2. Records timestamp, duration, and exit code
3. Appends the complete execution log to the script file as comments
4. Returns the script's exit code

After execution, the script file itself contains both the code AND proof of what happened when it ran.

### Step 4: If Failed, Create a Versioned Copy

If the script fails (non-zero exit code or failed validation):

1. The original script already has its failed output appended -- leave it as-is
2. Create a new versioned copy: `cp {step}_{task-name}.py {step}_{task-name}_a.py`
3. Apply fixes to the new copy only
4. Execute the new copy with `run_with_capture.sh`
5. If it fails again, create `_b.py`, then `_c.py`, etc.

**Never modify a script after its execution log has been appended.** The log documents that exact code. Any fix goes in a new versioned file.

---

## Script Naming Conventions

### Stage Directories

| Stage | Directory | Purpose |
|-------|-----------|---------|
| 5 (Fetch) | `scripts/stage5_fetch/` | Data retrieval scripts |
| 6 (Clean) | `scripts/stage6_clean/` | Context application / cleaning scripts |
| 7 (Transform) | `scripts/stage7_transform/` | EDA and transformation scripts |
| 8 (Analysis & Viz) | `scripts/stage8_analysis/` | Statistical analysis and visualization scripts |
| Debug | `scripts/debug/` | Debugger diagnostic scripts |
| QA | `scripts/cr/` | Code-reviewer inspection scripts |

### Script Filename Pattern

**Pattern:** `{step:02d}_{task-name}.py`

| Component | Source | Format |
|-----------|--------|--------|
| `step` | Step number from the Plan's Transformation Sequence (e.g., 1.1, 2.3) | 2-digit zero-padded (01, 02, 03) |
| `task-name` | Task name from the Transformation Sequence | lowercase-with-hyphens |

**Examples:**
- Step 1.1 `fetch-ccd` --> `01_fetch-ccd.py`
- Step 2.3 `join-ccd-meps` --> `03_join-ccd-meps.py`

### QA Script Filename Pattern

**Pattern:** `stage{N}_{step:02d}_cr{iteration}.py`

| Component | Source | Format |
|-----------|--------|--------|
| `stage{N}` | Stage number (5, 6, 7, 8) | Single digit |
| `step` | Step number of the reviewed script | 2-digit zero-padded |
| `_cr{iteration}` | QA iteration number (1-5) | `_cr1`, `_cr2`, etc. |

**Examples:**
- QA for `01_fetch-ccd.py` (Stage 5) --> `stage5_01_cr1.py`
- Second QA iteration for same --> `stage5_01_cr2.py`
- QA for `02_join-data.py` (Stage 7) --> `stage7_02_cr1.py`

All QA scripts are saved in `scripts/cr/`.

### Debug Script Filename Pattern

**Pattern:** `{seq:02d}_diag-{slug}.py`

**Example:** `01_diag-key-mismatch.py`

All debug scripts are saved in `scripts/debug/`.

---

## Execution Wrapper

### Location and Setup

The canonical wrapper lives at the **repo root**: `/daaf/scripts/run_with_capture.sh`.

During project setup (Stage 4), copy it into the project's `scripts/` directory:

```bash
cp /daaf/scripts/run_with_capture.sh scripts/run_with_capture.sh
chmod +x scripts/run_with_capture.sh
```

**Do NOT recreate this script from memory or documentation.** Always copy from the repo-level source to avoid drift.

### What It Does

1. Validates the script path exists
2. Checks whether the script already has an execution log (blocks re-runs if so)
3. Executes `python <script>` with stdout/stderr capture via `tee`
4. Records timestamp, duration, and exit code
5. Appends the complete execution log to the script file as comments
6. Returns the script's exit code

### Usage

```bash
# Execute a script (single Bash call, absolute paths)
bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage5_fetch/01_fetch-ccd.py

# If it fails, create a versioned copy and fix
cp {PROJECT_DIR}/scripts/stage5_fetch/01_fetch-ccd.py {PROJECT_DIR}/scripts/stage5_fetch/01_fetch-ccd_a.py
# Edit 01_fetch-ccd_a.py with fixes, then execute the new version
bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage5_fetch/01_fetch-ccd_a.py
```

### Re-run Protection

The wrapper checks for the marker `# EXECUTION LOG` in the script file. If found, it **refuses to run** and prints guidance to create a versioned copy instead. This enforces the versioning rule: once a script has been executed, it is a historical record.

---

## Script Versioning

### Rules

1. **Never modify a script after its execution log has been appended.** The log documents that exact code's behavior. Modifying it destroys the audit trail.
2. **Always create a new versioned copy for fixes.** The original (with its failed output) is preserved as evidence of what was tried.
3. **Preserve all versions.** Failed attempts are part of the audit trail. They document what was tried and why it failed.
4. **Only the final successful version is used downstream.** The notebook-assembler (Stage 9) uses the last passing version. QA reviews the final version.

### Suffix Convention

| Attempt | Suffix | Filename Example |
|---------|--------|------------------|
| First (original) | _(none)_ | `01_join-ccd-meps.py` |
| Second | `_a` | `01_join-ccd-meps_a.py` |
| Third | `_b` | `01_join-ccd-meps_b.py` |
| Fourth | `_c` | `01_join-ccd-meps_c.py` |
| ... | ... | ... |
| Twenty-seventh | `_aa` | `01_join-ccd-meps_aa.py` |

### Example Progression

```
scripts/stage7_transform/
  01_join-ccd-meps.py       # v1: FAILED (key mismatch) - output appended showing 0 rows
  01_join-ccd-meps_a.py     # v2: FAILED (type error) - output appended showing cast error
  01_join-ccd-meps_b.py     # v3: PASSED - output appended showing CP3 PASSED
```

After this progression:
- All three files are preserved (audit trail)
- `01_join-ccd-meps_b.py` is the **final successful version** used by downstream stages
- Anyone reviewing the history can see exactly what went wrong and how it was fixed

### QA-Triggered Revisions

If code-reviewer returns a BLOCKER after the script's primary checkpoint passed, the revision continues from the current suffix:

```
01_join-data.py       # v1: CP3 PASSED, but QA finds wrong join type --> BLOCKER
01_join-data_a.py     # v2: Fixed join type, CP3 PASSED, QA PASSED
```

Maximum 2 revision attempts per QA BLOCKER. If still failing after 2 revisions, escalate to the user.

---

## Returning Output to the Orchestrator

**Execution logs are captured in the script file. Agents returning output to the orchestrator should SUMMARIZE checkpoint results (PASSED/FAILED/WARNING + 1-line reason), not echo the raw log.**

The `run_with_capture.sh` wrapper appends the complete execution log to the script file as comments. This means the full audit trail is *already preserved on disk*. When an agent (research-executor, code-reviewer, debugger) finishes its work and returns a Task result to the orchestrator:

- **Report outcomes, not process:** "CP1 PASSED: 2,528 rows, 12 columns, 0.3% missingness" — not the full stdout.
- **Reference files by path, don't reproduce contents:** The orchestrator can read any file if it needs detail.
- **Keep verification tables to results only:** PASS/FAIL per check with a short note, not the underlying data that proved it.
- **Summarize, don't echo:** If the execution log shows 50 lines of data profiling output, the agent returns "Distributions reasonable, no outliers detected" — not the 50 lines.

This separation — exhaustive in the files, concise in the message — is what keeps the orchestrator's context viable across a full pipeline.

---

## Critical Rules

| Rule | Rationale |
|------|-----------|
| **NEVER execute Python interactively before writing to a file** | Scripts are the primary artifact. Interactive execution bypasses the audit trail. |
| **NEVER modify a script after appending its execution log** | The log documents that exact code. Modifications make the log misleading. |
| **NEVER run `python script.py` directly** | Use `run_with_capture.sh` so output is captured and appended automatically. |
| **NEVER delete failed script versions** | All versions form the audit trail. They document what was tried and what failed. |
| **ALWAYS create a new versioned copy for fixes** | Preserves the full history of attempts and outputs. |
| **ALWAYS use the wrapper for execution** | It handles capture, timing, log appending, and re-run protection. |
| **ALWAYS use the final successful version downstream** | Notebook and report reference only the version that passed. |
| **ALWAYS follow one-operation-per-script** | Mixing multiple transformations hides the source of errors. |
