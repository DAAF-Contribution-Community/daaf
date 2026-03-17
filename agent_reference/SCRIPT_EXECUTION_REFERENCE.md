# Script Execution Reference

This document is the **single source of truth** for how Python scripts are written, executed, captured, versioned, and managed in DAAF. It covers both the file-first execution protocol and the standardized script format templates.

Every agent that writes or executes Python code (research-executor, code-reviewer, debugger, notebook-assembler) follows this reference.

**Documentation Standard:** All scripts follow the Inline Audit Trail (IAT) protocol. See `agent_reference/INLINE_AUDIT_TRAIL.md` for the complete standard.

---

# Part 1: File-First Execution Protocol

## Overview

**Why this protocol exists:** Scripts are the primary execution artifacts — not notebooks, not interactive sessions. Each script is a self-contained, reproducible unit with an embedded execution log that proves exactly what code ran and what it produced. This gives every analysis a complete audit trail: code + output + version history.

**The philosophy:** Write first. Execute once. Capture everything. Never modify, only version.

---

## The Protocol

Every Python execution follows these steps in order. No exceptions.

```
WRITE  -->  EXECUTE  -->  CAPTURE  -->  COMMIT
            (if failed: VERSION the script, then REPEAT from WRITE)
```

### Step 1: Write the Script to a File

Create the script file BEFORE executing any code. Use the standard template format from Part 2 of this document.

- Save to the appropriate stage directory (see Directory Structure below)
- Include: shebang, metadata docstring, config section, sequential code, inline validation
- Follow IAT documentation standards (see `agent_reference/INLINE_AUDIT_TRAIL.md`)
- Scripts are **flat, sequential** Python — no `def main()`, no `if __name__` guards, no helper function sections

### Step 2: Execute with the Wrapper

Run the script using the execution wrapper, which handles output capture and log appending automatically:

```bash
bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage{N}_{type}/{step}_{task-name}.py
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

1. The original script already has its failed output appended — leave it as-is
2. Create a new versioned copy: `cp {step}_{task-name}.py {step}_{task-name}_a.py`
3. Apply fixes to the new copy only
4. Execute the new copy with `run_with_capture.sh`
5. If it fails again, create `_b.py`, then `_c.py`, etc.

**Never modify a script after its execution log has been appended.** See Script Versioning below for complete suffix conventions, examples, and rules.

### Step 5: Commit

After successful execution:
1. Commit the script (two separate Bash calls):
   - `git add scripts/stage{N}_{type}/{step}_{task-name}.py`
   - `git commit -m "feat(stage{N}-{step}): {brief description}"`
2. Proceed to next step in the Transformation Sequence

If the script went through versioned revisions (Step 4), commit **all** versions for audit trail completeness.

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

### Inviolable (NEVER)

| Rule | Rationale |
|------|-----------|
| **NEVER execute Python interactively before writing to a file** | Scripts are the primary artifact. Interactive execution bypasses the audit trail. |
| **NEVER modify a script after appending its execution log** | The log documents that exact code. Modifications make the log misleading. |
| **NEVER run `python script.py` directly** | Use `run_with_capture.sh` so output is captured and appended automatically. |
| **NEVER delete failed script versions** | All versions form the audit trail. They document what was tried and what failed. |
| **NEVER use function definitions (`def main()`, helpers)** | Sequential scripts read top-to-bottom. Functions add indirection without reuse value. |

### Required Practices (ALWAYS)

| Rule | Rationale |
|------|-----------|
| **ALWAYS create a new versioned copy for fixes** | Preserves the full history of attempts and outputs. |
| **ALWAYS use the wrapper for execution** | It handles capture, timing, log appending, and re-run protection. |
| **ALWAYS use the final successful version downstream** | Notebook and report reference only the version that passed. |
| **ALWAYS follow one-operation-per-script** | Mixing multiple transformations hides the source of errors. |
| **ALWAYS commit all versions** | Audit trail shows evolution of code and results. |
| **ALWAYS include shebang, metadata docstring, and config section** | Required for traceability and reproducibility. |
| **ALWAYS use `Path` with `PROJECT_DIR` constant** | Hardcoded paths break when project location changes. |
| **ALWAYS capture pre/post state around transformations** | Enables validation of row count changes and data integrity. |
| **ALWAYS include checkpoint validation (`assert` + `print`)** | Every transformation needs inline proof of correctness. |
| **ALWAYS follow IAT protocol (INTENT, REASONING, ASSUMES)** | Uncommented transformations block QA review. See `INLINE_AUDIT_TRAIL.md`. |

---

# Part 2: Script Format and Templates

Part 1 defined **what to do** (the execution lifecycle). Part 2 defines **what the files look like** — the directory layout, naming conventions, and complete script templates for each stage. Use this as a reference when writing new scripts.

## Directory Structure

```
research/YYYY-MM-DD_[Title]/
├── scripts/
│   ├── stage5_fetch/           # Data retrieval scripts
│   │   ├── 01_fetch-ccd.py
│   │   └── 02_fetch-meps.py
│   ├── stage6_clean/           # Data cleaning scripts
│   │   ├── 01_clean-ccd.py
│   │   └── 02_clean-meps.py
│   ├── stage7_transform/       # Transformation scripts
│   │   ├── 01_initial-eda.py
│   │   ├── 02_join-data.py
│   │   └── 03_aggregate.py
│   ├── stage8_analysis/        # Analysis & visualization scripts
│   │   ├── 01_regression-poverty.py
│   │   └── 02_enrollment-plot.py
│   ├── cr/                     # QA inspection scripts (iterative)
│   │   ├── stage5_01_cr1.py    # CR for 01_fetch-ccd.py (standard + profiling)
│   │   ├── stage5_01_cr2.py    # (investigated year coverage anomaly)
│   │   ├── stage5_02_cr1.py    # CR for 02_fetch-meps.py
│   │   ├── stage6_01_cr1.py    # CR for 01_clean-ccd.py
│   │   ├── stage7_02_cr1.py    # CR for 02_join-data.py
│   │   ├── stage8_01_cra1.py   # QA4a (statistical validity) for 01_regression-poverty.py
│   │   └── stage8_02_crb1.py   # QA4b (viz quality) for 02_enrollment-plot.py
│   └── debug/                  # Debugger diagnostic scripts
│       └── 01_diag-key-mismatch.py
```

---

## Naming Convention

**Pattern:** `{step:02d}_{task-name}.py`

| Component | Source | Format |
|-----------|--------|--------|
| `step` | Step number from Transformation Sequence (e.g., 1.1, 2.3) | 2-digit zero-padded (01, 02) |
| `task-name` | Task Name from Transformation Sequence | lowercase-with-hyphens |

**Examples:**
- Step 1.1 `fetch-ccd` → `01_fetch-ccd.py`
- Step 2.3 `join-ccd-meps` → `03_join-ccd-meps.py`
- Debug issue `key-mismatch` → `01_diag-key-mismatch.py`

### QA Script Naming Convention (Iterative)

**Pattern:** `stage{N}_{step:02d}_cr{iteration}.py`

| Component | Source | Format |
|-----------|--------|--------|
| `stage{N}` | Stage number (5, 6, 7, 8) | single digit (Stage 8 uses `cra`/`crb` — see below) |
| `step` | Step number of the reviewed script | 2-digit zero-padded |
| `_cr{iteration}` | QA script suffix with iteration (1-5) | `_cr1`, `_cr2`, etc. |

**Examples:**
- QA for `01_fetch-ccd.py` (Stage 5) → `stage5_01_cr1.py` (first iteration), `stage5_01_cr2.py` (if needed)
- QA for `02_join-data.py` (Stage 7) → `stage7_02_cr1.py`
- QA for `02_enrollment-plot.py` (Stage 8 viz) → `stage8_02_crb1.py`

**Stage 8 QA Split:** Stage 8 uses separate QA prefixes for analysis (QA4a) and visualization (QA4b):
- QA4a for `01_regression-poverty.py` (Stage 8.1 analysis) → `stage8_01_cra1.py`
- QA4b for `02_enrollment-plot.py` (Stage 8.2 viz) → `stage8_02_crb1.py`

**QA scripts are created by code-reviewer** and saved in `scripts/cr/`.

### Debug Script Naming Convention

**Pattern:** `{seq:02d}_diag-{slug}.py`

**Example:** `01_diag-key-mismatch.py`

All debug scripts are saved in `scripts/debug/`.

---

## Standard Script Template

Every script is a **flat, sequential** Python file that reads top-to-bottom like a lab notebook. There are no `main()` functions, no helper function sections, and no `if __name__` guards. The script runs from top to bottom when executed with `python script.py`.

```python
#!/usr/bin/env python3
"""
Stage {N}.{step}: {Description}.

Task: {task-name}
Wave: {wave}, Step: {step}, Stage: {N}
Depends on: {dependencies}
Input: {input_path}
Output: {output_path}
Checkpoint: CP{n}
"""

import polars as pl
from pathlib import Path

# --- Config ---
# PROJECT_DIR: The orchestrator substitutes the absolute project path at invocation time.
# Example: Path("/home/user/my-project/research/2026-02-04_My_Analysis")
PROJECT_DIR = Path("{PROJECT_DIR}")
INPUT_PATH = PROJECT_DIR / "{input_path}"
OUTPUT_PATH = PROJECT_DIR / "{output_path}"

# --- Load ---
# Load input data and verify shape before proceeding.
print("=" * 60)
print("Stage {N}.{step}: {Description}")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"Pre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# --- Transform ---
# INTENT: [describe the goal of this transformation]
# REASONING: [why this approach was chosen over alternatives]
# ASSUMES: [data properties this code depends on]
# [Your transformation here — use Polars chain expressions]
result = (
    df
    .filter(...)
    .with_columns(...)
)

# --- Validate ---
# Checkpoint validation against Plan expectations.
print(f"\nPost-state: {result.shape[0]:,} rows x {result.shape[1]} cols")
print(f"Row change: {result.shape[0] - pre_rows:+,} ({(result.shape[0] - pre_rows) / pre_rows * 100:+.1f}%)")

assert result.shape[0] > 0, "STOP: Empty result"
assert all(c in result.columns for c in ["required_col"]), "STOP: Missing required columns"

# --- Save ---
# Persist results in parquet format.
result.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")
print(f"\nCP{n} VALIDATION: PASSED")

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

---

## Execution Log Section

**This section is auto-appended** after the script is executed. It provides:

- **Timestamp:** When the script was run
- **Duration:** How long execution took
- **Exit code:** 0 = success, non-zero = failure
- **Full stdout:** All printed output including validation results
- **Any stderr:** Warnings or errors

**Example of appended execution log:**

```python
# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-01-31 14:32:05
# Command: python scripts/stage5_fetch/01_fetch-ccd.py
# Duration: 45.23 seconds
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 5.1: Fetch CCD school directory
# ============================================================
#   Year 2018... Fetched 3 pages
#   Year 2019... Fetched 3 pages
#   Year 2020... Fetched 3 pages
#   Year 2021... Fetched 3 pages
#   Year 2022... Fetched 3 pages
#
# Total records fetched: 22,379
# Shape: 22,379 rows x 45 cols
# Saved: data/raw/2026-01-31_ccd_schools.parquet
#
# ============================================================
# CHECKPOINT 1 VALIDATION
# ============================================================
#   [PASS] All 5 years present: [2018, 2019, 2020, 2021, 2022]
#   [PASS] Row counts reasonable: 4,356 - 4,601
#   [PASS] Critical columns present: ['ncessch', 'year', 'school_name', 'fips']
#   [PASS] No nulls in ID columns: ncessch=0, year=0
#
# ============================================================
# CP1 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (none)
#
# =============================================================================
```

**If the script failed**, the execution log shows what went wrong:

```python
# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-01-31 14:45:12
# Command: python scripts/stage7_transform/01_join-ccd-meps.py
# Duration: 2.34 seconds
# Exit code: 1
#
# --- STDOUT ---
# ============================================================
# Stage 7.1: Join CCD + MEPS
# ============================================================
# CCD:  22,379 rows x 45 cols
# MEPS: 18,234 rows x 12 cols
#
# Key overlap: 0 / 22,379 (0.0%)
# CCD keys unique: True
# MEPS keys unique: True
#
# Join complete: 0 rows x 56 cols
# Row change from CCD: -100.0%
#
# --- STDERR ---
# Traceback (most recent call last):
#   File "scripts/stage7_transform/01_join-ccd-meps.py", line 52, in <module>
#     assert has_rows, "STOP: Join produced 0 rows"
# AssertionError: STOP: Join produced 0 rows
#
# =============================================================================
```

After seeing this failure, create `01_join-ccd-meps_a.py` with fixes, run it, and it will get its own execution log.

---

## Stage 5: Mirror-Based Fetch (MANDATORY)

**Applies to:** All Stage 5 fetch scripts.

Stage 5 scripts download data from configured mirrors (per mirrors.yaml).

### Fetch Decision

| Dataset Type | Pattern | Reference |
|--------------|---------|-----------|
| Single-file (all years) | `fetch_from_mirrors()` | Domain query skill `./references/fetch-patterns.md` (e.g., `education-data-query`) |
| Yearly files | `fetch_yearly_from_mirrors()` | Domain query skill `./references/fetch-patterns.md` (e.g., `education-data-query`) |

### Mirror Fetch Code Pattern

```python
# --- Mirror Configuration ---
# INTENT: Download {dataset} from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
# Format-specific read driven by each mirror's read_strategy field.
# All mirrors use the same canonical path from datasets-reference.md.
import yaml

# Education domain example — substitute your domain's query skill path
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# Dataset path: canonical path string from datasets-reference.md.
# All mirrors use the same path — only root_url and format differ.
DATASET_PATH = "ccd/schools_ccd_directory"  # Education domain example

# [Include fetch_from_mirrors(path, ...) function from fetch-patterns.md]
```

---

## Stage-Specific Examples

### Stage 5: Fetch Script Example (Mirror-Based)

*Education domain example — substitute your domain's query skill paths and dataset references.*

```python
#!/usr/bin/env python3
"""
Stage 5.1: Fetch CCD school directory data for 2018-2022.

Task: fetch-ccd
Wave: 1, Step: 1, Stage: 5
Depends on: None
Input: Mirror download (per mirrors.yaml priority order)
Output: data/raw/2026-01-24_ccd_schools.parquet
Checkpoint: CP1
"""

import time

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants derived from the Plan's query specification (Section 4.2).
# Data is downloaded from mirrors
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-01-24"

YEARS = list(range(2018, 2023))  # 2018-2022 per Plan query specification

# Dataset path (from domain query skill's datasets-reference.md)
DATASET_PATH = "ccd/schools_ccd_directory"  # Education domain example

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ccd_schools.parquet"

# --- Mirror Configuration ---
# INTENT: Download CCD school directory from the fastest available mirror.
# REASONING: Mirrors loaded from mirrors.yaml (single source of truth).
# Format-specific read driven by each mirror's read_strategy field.
import yaml

# Education domain example — substitute your domain's query skill path
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Rate Limiting ---
# INTENT: Prevent HTTP 429 (Too Many Requests) errors from mirrors.
# REASONING: Mirrors may rate-limit rapid successive requests.
FETCH_DELAY_SECONDS = 3
_last_fetch_time = 0.0


def _rate_limit():
    """Sleep if needed to maintain minimum delay between fetch requests."""
    global _last_fetch_time
    if _last_fetch_time > 0:
        elapsed = time.time() - _last_fetch_time
        if elapsed < FETCH_DELAY_SECONDS:
            wait = FETCH_DELAY_SECONDS - elapsed
            print(f"  (rate limit: waiting {wait:.1f}s)")
            time.sleep(wait)
    _last_fetch_time = time.time()


def fetch_from_mirrors(
    path: str,
    filters: dict | None = None,
    years: list[int] | None = None,
) -> pl.DataFrame:
    """Try each mirror in order. Return DataFrame on first success.

    Args:
        path: Canonical dataset path string from datasets-reference.md.
            All mirrors use the same path — only root_url and format differ.
            Example: "ccd/schools_ccd_directory"
        filters: Dict of column->value(s) filters to apply locally.
        years: List of years to filter to.
    """
    _rate_limit()
    last_error = None

    for mirror in MIRRORS:
        name = mirror["name"]
        strategy = mirror["read_strategy"]

        # Build URL from mirror's url_template + canonical path
        url = mirror["url_template"].format(root_url=mirror["root_url"], path=path, format=mirror["format"])

        print(f"  Trying {name}: {url}")

        try:
            if strategy in ("eager_parquet", "parquet"):
                df = pl.read_parquet(url)
            elif strategy in ("lazy_csv", "csv"):
                lazy = pl.scan_csv(url, infer_schema_length=10000)
                if years:
                    lazy = lazy.filter(pl.col("year").is_in(years))
                if filters:
                    for col, val in filters.items():
                        if isinstance(val, list):
                            lazy = lazy.filter(pl.col(col).is_in(val))
                        else:
                            lazy = lazy.filter(pl.col(col) == val)
                df = lazy.collect()
                print(f"  ✓ {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  ✓ {name}: {df.shape[0]:,} rows")

            # Apply filters for eagerly-loaded formats
            if years:
                df = df.filter(pl.col("year").is_in(years))
            if filters:
                for col, val in filters.items():
                    if isinstance(val, list):
                        df = df.filter(pl.col(col).is_in(val))
                    else:
                        df = df.filter(pl.col(col) == val)

            print(f"  After filters: {df.shape[0]:,} rows")
            return df

        except Exception as e:
            last_error = e
            print(f"  ✗ {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")


print("=" * 60)
print("Stage 5.1: Fetch CCD school directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

# --- Fetch Data ---
# INTENT: Download CCD school directory and filter to requested years.
# REASONING: Single-file dataset (all years in one file). Download once,
# filter locally with Polars.
# ASSUMES: Mirror URLs are current and accessible. Dataset contains "year" column.
print("\nFetching CCD school directory...")
df = fetch_from_mirrors(
    path=DATASET_PATH,
    years=YEARS,
)
print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Save ---
# Persist results in parquet format.
df.write_parquet(OUTPUT_PARQUET)
print(f"Saved: {OUTPUT_PARQUET}")

# --- CP1 Validation ---
# Checkpoint validation: verify fetched data meets Plan expectations for
# year coverage, row counts, critical columns, and identifier integrity.
print("\n" + "=" * 60)
print("CHECKPOINT 1 VALIDATION")
print("=" * 60)

# CP1.1: All years present
years_found = df["year"].unique().to_list()
all_years = all(y in years_found for y in YEARS)
print(f"  [{'PASS' if all_years else 'FAIL'}] All {len(YEARS)} years present: {sorted(years_found)}")

# CP1.2: Row counts reasonable per year
year_counts = df.group_by("year").len()
min_count = year_counts["len"].min()
max_count = year_counts["len"].max()
count_reasonable = min_count > 1000 and max_count < 200000
print(f"  [{'PASS' if count_reasonable else 'WARN'}] Row counts reasonable: {min_count:,} - {max_count:,}")

# CP1.3: Critical columns present
critical_cols = ["ncessch", "year", "school_name", "fips"]
cols_present = all(c in df.columns for c in critical_cols)
print(f"  [{'PASS' if cols_present else 'FAIL'}] Critical columns present: {critical_cols}")

# CP1.4: No nulls in identifier columns
ncessch_nulls = df["ncessch"].null_count()
year_nulls = df["year"].null_count()
no_id_nulls = ncessch_nulls == 0 and year_nulls == 0
print(f"  [{'PASS' if no_id_nulls else 'FAIL'}] No nulls in ID columns: ncessch={ncessch_nulls}, year={year_nulls}")

assert all_years, "STOP: Missing years"
assert cols_present, "STOP: Missing critical columns"
assert no_id_nulls, "STOP: Nulls in ID columns"

print("\n" + "=" * 60)
print("CP1 VALIDATION: PASSED")
print("=" * 60)

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

---

### Stage 6: Clean Script Example

```python
#!/usr/bin/env python3
"""
Stage 6.1: Clean CCD data — filter coded missing values, calculate suppression rate.

Task: clean-ccd
Wave: 2, Step: 1, Stage: 6
Depends on: fetch-ccd
Input: data/raw/2026-01-24_ccd_schools.parquet
Output: data/processed/2026-01-24_ccd_clean.parquet
Checkpoint: CP2
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration constants for CCD cleaning. Coded missing values (-1, -2, -3)
# are standard across the Education Data Portal and must be replaced with null
# before any statistical computation.
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATE_PREFIX = "2026-01-24"

INPUT_PATH = PROJECT_DIR / "data" / "raw" / f"{DATE_PREFIX}_ccd_schools.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_ccd_clean.parquet"

# REASONING: The Education Data Portal uses integer sentinel values for missing
# data rather than null. These must be mapped to null so they don't corrupt
# downstream statistical calculations (e.g., mean enrollment would be dragged
# down by -1 values if left in place).
CODED_MISSING = {-1: "Missing/not reported", -2: "Not applicable", -3: "Suppressed for privacy"}
NUMERIC_COLS = ["enrollment", "teachers_fte", "free_lunch", "reduced_lunch"]

# --- Load ---
# Load input data and verify shape before proceeding.
print("=" * 60)
print("Stage 6.1: Clean CCD data")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture current state BEFORE transformation for post-validation comparison.
# Also enumerate coded values present so we can verify they're all removed.
pre_rows = df.shape[0]
print(f"Pre-state: {pre_rows:,} rows")

coded_counts = {}
for col in NUMERIC_COLS:
    if col in df.columns:
        for code, meaning in CODED_MISSING.items():
            count = df.filter(pl.col(col) == code).height
            if count > 0:
                coded_counts[(col, code)] = count

print("Coded values found:")
for (col, code), count in coded_counts.items():
    print(f"  {col} = {code} ({CODED_MISSING[code]}): {count:,}")

# --- Clean ---
# INTENT: Replace coded missing values (-1, -2, -3) with null in all numeric
# columns so downstream statistical operations are not corrupted.
#
# REASONING: Using null (not zero, not NaN) because null is the semantically
# correct representation — these values were never observed. Zero would imply
# a measured value of zero, and NaN would complicate Polars aggregations.
#
# ASSUMES: All coded values in NUMERIC_COLS are in the CODED_MISSING dict
# per CCD source documentation (education-data-source-ccd skill).
for col in NUMERIC_COLS:
    if col in df.columns:
        df = df.with_columns(
            pl.when(pl.col(col).is_in(list(CODED_MISSING.keys())))
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )

print("Replaced coded values with null")

# --- Post-state ---
post_rows = df.shape[0]
print(f"\nPost-state: {post_rows:,} rows")
print(f"Row change: {((post_rows - pre_rows) / pre_rows * 100):+.1f}%")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"Saved: {OUTPUT_PATH}")

# --- CP2 Validation ---
# Checkpoint validation: verify all coded values removed, suppression rate
# is within acceptable bounds, and row count is preserved (cleaning replaces
# values but should not drop rows).
print("\n" + "=" * 60)
print("CHECKPOINT 2 VALIDATION")
print("=" * 60)

# CP2.1: No coded values remain
coded_remaining = 0
for col in NUMERIC_COLS:
    if col in df.columns:
        for code in CODED_MISSING.keys():
            coded_remaining += df.filter(pl.col(col) == code).height

no_coded = coded_remaining == 0
print(f"  [{'PASS' if no_coded else 'FAIL'}] No coded values remaining: {coded_remaining}")

# CP2.2: Suppression rate < 50%
# REASONING: The 50% threshold is from BOUNDARIES.md STOP conditions. Above 50%
# suppression, the remaining data is too sparse to support reliable analysis.
total_cells = len(df) * len(NUMERIC_COLS)
null_cells = sum(df[col].null_count() for col in NUMERIC_COLS if col in df.columns)
suppression_rate = null_cells / total_cells if total_cells > 0 else 0
suppression_ok = suppression_rate < 0.50
print(f"  [{'PASS' if suppression_ok else 'FAIL'}] Suppression rate < 50%: {suppression_rate:.1%}")

# CP2.3: Row count preserved (cleaning shouldn't drop rows)
rows_preserved = post_rows == pre_rows
print(f"  [{'PASS' if rows_preserved else 'WARN'}] Rows preserved: {pre_rows:,} -> {post_rows:,}")

assert no_coded, "STOP: Coded values still present"
assert suppression_ok, "STOP: Suppression rate >= 50%"

print("\n" + "=" * 60)
print("CP2 VALIDATION: PASSED")
print("=" * 60)

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

---

### Stage 7: Transform Script Example

```python
#!/usr/bin/env python3
"""
Stage 7.1: Join CCD and MEPS data on school identifier (ncessch).

Task: join-ccd-meps
Wave: 3, Step: 1, Stage: 7
Depends on: clean-ccd, clean-meps
Input: data/processed/2026-01-24_ccd_clean.parquet, data/processed/2026-01-24_meps_clean.parquet
Output: data/processed/2026-01-24_analysis.parquet
Checkpoint: CP3
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Configuration for joining CCD school directory with MEPS poverty estimates.
# Join key and cardinality are specified in the Plan's Transformation Sequence.
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATE_PREFIX = "2026-01-24"

INPUT_CCD = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_ccd_clean.parquet"
INPUT_MEPS = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_meps_clean.parquet"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"

# REASONING: ncessch is the 12-digit NCES school identifier, the canonical
# key for linking school-level datasets. It is unique per school and consistent
# across CCD and MEPS because both are NCES products.
JOIN_KEY = "ncessch"
EXPECTED_CARDINALITY = "1:1"

# --- Load ---
# Load both cleaned datasets and verify shapes before joining.
print("=" * 60)
print("Stage 7.1: Join CCD + MEPS")
print("=" * 60)

df_ccd = pl.read_parquet(INPUT_CCD)
df_meps = pl.read_parquet(INPUT_MEPS)
print(f"CCD:  {df_ccd.shape[0]:,} rows x {df_ccd.shape[1]} cols")
print(f"MEPS: {df_meps.shape[0]:,} rows x {df_meps.shape[1]} cols")

# --- Pre-state ---
# Capture key overlap statistics BEFORE joining. This establishes the expected
# match rate and verifies uniqueness assumptions required for a 1:1 join.
pre_ccd_rows = df_ccd.shape[0]
pre_meps_rows = df_meps.shape[0]

ccd_keys = set(df_ccd[JOIN_KEY].unique().to_list())
meps_keys = set(df_meps[JOIN_KEY].unique().to_list())
key_overlap = len(ccd_keys & meps_keys)
overlap_pct = key_overlap / len(ccd_keys) if ccd_keys else 0  # Guard against empty set division
print(f"\nKey overlap: {key_overlap:,} / {len(ccd_keys):,} ({overlap_pct:.1%})")

ccd_key_unique = df_ccd[JOIN_KEY].n_unique() == len(df_ccd)
meps_key_unique = df_meps[JOIN_KEY].n_unique() == len(df_meps)
print(f"CCD keys unique: {ccd_key_unique}")
print(f"MEPS keys unique: {meps_key_unique}")

# --- Join ---
# INTENT: Combine CCD school directory data with MEPS poverty estimates to
# create a unified analysis dataset with both enrollment and poverty metrics.
#
# REASONING: Using INNER join (not LEFT) because:
#   - We need BOTH enrollment AND poverty data for every school in the analysis
#   - Schools missing from MEPS lack poverty estimates and cannot contribute
#     to the research question ("How does poverty correlate with enrollment?")
#   - Plan specifies inner join with expected match rate of ~85%
#
# ASSUMES:
#   - JOIN_KEY ("ncessch") is the 12-digit NCES school ID, unique per school-year
#   - Both datasets have been cleaned (Stage 6) — no coded missing values remain
#   - Key overlap was verified in pre-state check above (~85% expected)
#   - CCD has one row per school per year; MEPS has one row per school per year
df = df_ccd.join(df_meps, on=JOIN_KEY, how="inner")
print(f"\nJoin complete: {df.shape[0]:,} rows x {df.shape[1]} cols")

row_change_pct = ((df.shape[0] - pre_ccd_rows) / pre_ccd_rows * 100)  # Negative = rows lost in join
print(f"Row change from CCD: {row_change_pct:+.1f}%")

# --- Save ---
# Persist results in parquet format.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP3 Validation ---
# Checkpoint validation: verify join produced rows, row loss is within
# acceptable bounds, cardinality matches expectation, and nulls are reasonable.
print("\n" + "=" * 60)
print("CHECKPOINT 3 VALIDATION")
print("=" * 60)

# CP3.1: Join produced rows
has_rows = df.shape[0] > 0
print(f"  [{'PASS' if has_rows else 'FAIL'}] Join produced rows: {df.shape[0]:,}")

# CP3.2: No unexpected row loss (>90% loss suspicious)
acceptable_loss = row_change_pct > -90
print(f"  [{'PASS' if acceptable_loss else 'FAIL'}] Acceptable row change: {row_change_pct:+.1f}%")

# CP3.3: Cardinality check (for 1:1, output <= min of inputs)
if EXPECTED_CARDINALITY == "1:1":
    expected_max = min(pre_ccd_rows, pre_meps_rows)
    cardinality_ok = df.shape[0] <= expected_max
    print(f"  [{'PASS' if cardinality_ok else 'FAIL'}] 1:1 cardinality: {df.shape[0]:,} <= {expected_max:,}")

# CP3.4: No unexpected nulls from join
new_nulls = df.null_count().sum_horizontal()[0]
ccd_nulls = df_ccd.null_count().sum_horizontal()[0]
meps_nulls = df_meps.null_count().sum_horizontal()[0]
expected_nulls = ccd_nulls + meps_nulls
nulls_ok = new_nulls <= expected_nulls * 1.1  # Allow 10% tolerance
print(f"  [{'PASS' if nulls_ok else 'WARN'}] Null count reasonable: {new_nulls:,} (expected ~{expected_nulls:,})")

assert has_rows, "STOP: Join produced 0 rows"
assert acceptable_loss, "STOP: Row loss > 90%"

print("\n" + "=" * 60)
print("CP3 VALIDATION: PASSED")
print("=" * 60)

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

---

### Stage 8: Analysis Script Example

Stage 8 encompasses both statistical analysis (8.1) and visualization (8.2). This example covers 8.1 (analysis). For 8.2 (visualization), follow the same template structure but output figures to `output/figures/` and use the `plotnine` or `plotly` skills for plot construction. See `agent_reference/QA_CHECKPOINTS.md` for the QA4a (analysis) and QA4b (visualization) checkpoint definitions.

```python
#!/usr/bin/env python3
"""
Stage 8.1: Regression analysis — poverty rate vs. enrollment metrics.

Task: regression-poverty
Wave: 4, Step: 1, Stage: 8
Depends on: join-ccd-meps (Stage 7)
Input: data/processed/2026-01-24_analysis.parquet
Output: output/analysis/2026-01-24_regression_results.parquet
Checkpoint: CP4
"""

import polars as pl
import numpy as np
from pathlib import Path

# --- Config ---
# Configuration for poverty-enrollment regression analysis.
# Model specification and variable selections from Plan Section 5 (Analysis Design).
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATE_PREFIX = "2026-01-24"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_regression_results.parquet"

OUTCOME_VAR = "enrollment"
PREDICTOR_VAR = "poverty_rate"
CONTROL_VARS = ["teachers_fte", "urban_centric_locale"]

# --- Load ---
# Load the joined analysis dataset and verify shape before proceeding.
print("=" * 60)
print("Stage 8.1: Poverty-Enrollment Regression")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Verify all analysis variables exist, then create complete-case dataset.
pre_rows = df.shape[0]
analysis_vars = [OUTCOME_VAR, PREDICTOR_VAR] + CONTROL_VARS

missing_vars = [v for v in analysis_vars if v not in df.columns]
assert not missing_vars, f"STOP: Missing analysis variables: {missing_vars}"

# INTENT: Create complete-case dataset for regression via listwise deletion.
# REASONING: OLS requires complete observations. Listwise deletion is appropriate
# when missingness is < 10% (Plan Section 5 specifies this threshold).
# ASSUMES: Missingness is MCAR or MAR — not systematically related to outcomes.
df_complete = df.drop_nulls(subset=analysis_vars)
dropped = pre_rows - df_complete.shape[0]
drop_pct = dropped / pre_rows * 100
print(f"Complete cases: {df_complete.shape[0]:,} ({dropped:,} rows dropped, {drop_pct:.1f}%)")

assert drop_pct < 10, f"STOP: Listwise deletion removed {drop_pct:.1f}% of rows (threshold: 10%)"

# --- Analysis ---
# INTENT: Estimate OLS regression of enrollment on poverty rate with controls.
# REASONING: OLS is the Plan-specified method (Section 5). Using numpy for
# coefficient estimation to avoid heavy dependencies (statsmodels/sklearn).
# ASSUMES: Linear relationship is appropriate for this exploratory analysis.
# Results are descriptive associations, not causal estimates.

# Build design matrix
y = df_complete[OUTCOME_VAR].to_numpy().astype(float)
X_cols = [PREDICTOR_VAR] + CONTROL_VARS
X = np.column_stack([
    df_complete[col].to_numpy().astype(float) for col in X_cols
])

# Add intercept
X = np.column_stack([np.ones(len(y)), X])
col_names = ["intercept"] + X_cols

# OLS: beta = (X'X)^-1 X'y
# INTENT: Compute OLS coefficients via normal equations.
# REASONING: Direct normal equation is stable for datasets of this size
# (typically < 100K rows, < 10 predictors). No need for iterative solvers.
XtX_inv = np.linalg.inv(X.T @ X)
beta = XtX_inv @ (X.T @ y)

# Residuals and standard errors
y_hat = X @ beta
residuals = y - y_hat
n, k = X.shape
dof = n - k
mse = np.sum(residuals**2) / dof
se = np.sqrt(np.diag(mse * XtX_inv))
t_stats = beta / se
r_squared = 1 - np.sum(residuals**2) / np.sum((y - np.mean(y))**2)

print(f"\nR-squared: {r_squared:.4f}")
print(f"Observations: {n:,}")
print(f"Degrees of freedom: {dof:,}")
print(f"\n{'Variable':<25} {'Coef':>12} {'Std Err':>12} {'t-stat':>10}")
print("-" * 60)
for i, name in enumerate(col_names):
    print(f"{name:<25} {beta[i]:>12.4f} {se[i]:>12.4f} {t_stats[i]:>10.2f}")

# --- Save ---
# Persist regression results as a structured parquet file for downstream use.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

results_df = pl.DataFrame({
    "variable": col_names,
    "coefficient": beta.tolist(),
    "std_error": se.tolist(),
    "t_statistic": t_stats.tolist(),
})
results_df = results_df.with_columns([
    pl.lit(r_squared).alias("r_squared"),
    pl.lit(n).alias("n_obs"),
    pl.lit(dof).alias("degrees_of_freedom"),
])

results_df.write_parquet(OUTPUT_PATH)
print(f"\nSaved: {OUTPUT_PATH}")

# --- CP4 Validation ---
# Checkpoint validation: verify regression produced valid results,
# coefficients are finite, and model diagnostics are reasonable.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

# CP4.1: All coefficients finite
all_finite = np.all(np.isfinite(beta)) and np.all(np.isfinite(se))
print(f"  [{'PASS' if all_finite else 'FAIL'}] All coefficients finite")

# CP4.2: R-squared in valid range
r2_valid = 0 <= r_squared <= 1
print(f"  [{'PASS' if r2_valid else 'FAIL'}] R-squared in [0, 1]: {r_squared:.4f}")

# CP4.3: Sufficient observations for number of predictors (n > 10*k)
obs_adequate = n > 10 * k
print(f"  [{'PASS' if obs_adequate else 'WARN'}] n/k ratio: {n}/{k} = {n/k:.0f} (>10 required)")

# CP4.4: Primary predictor has expected sign (from Plan hypothesis)
predictor_idx = col_names.index(PREDICTOR_VAR)
sign_expected = beta[predictor_idx] < 0  # Plan hypothesizes negative association
print(f"  [{'PASS' if sign_expected else 'NOTE'}] Primary predictor sign: {beta[predictor_idx]:.4f} (expected negative)")

assert all_finite, "STOP: Non-finite coefficients"
assert r2_valid, "STOP: R-squared out of range"

print("\n" + "=" * 60)
print("CP4 VALIDATION: PASSED")
print("=" * 60)

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

---

### Debug Script Example

```python
#!/usr/bin/env python3
"""
DIAGNOSTIC: Investigate join key mismatch between CCD and MEPS.

Issue: Join producing 0 rows when ~80K expected
Error: "Join result empty"
Stage: 7 (Transformation)

Hypothesis Testing Log:
1. Key column name mismatch -> REFUTED
2. Key type mismatch (string vs int) -> CONFIRMED
3. Key value format difference -> CONFIRMED (leading zeros stripped)
"""

import polars as pl
from pathlib import Path

# --- Config ---
# Diagnostic script for investigating join key mismatch. Loads both datasets
# that failed to join and tests three hypotheses about the root cause.
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATE_PREFIX = "2026-01-24"

CCD_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_ccd_clean.parquet"
MEPS_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_meps_clean.parquet"

# --- Load data once ---
print("=" * 60)
print("DIAGNOSTIC: join-key-mismatch")
print("=" * 60)

df_ccd = pl.read_parquet(CCD_PATH)
df_meps = pl.read_parquet(MEPS_PATH)

# --- Hypothesis 1: Column name mismatch ---
# INTENT: Test whether the join key column "ncessch" exists in both datasets.
# REASONING: The simplest failure mode — if the column is named differently
# in one dataset, the join would fail or match on the wrong column.
print("\n" + "=" * 60)
print("HYPOTHESIS 1: Column name mismatch")
print("=" * 60)

print(f"CCD columns: {df_ccd.columns[:10]}...")
print(f"MEPS columns: {df_meps.columns[:10]}...")

has_ncessch_ccd = "ncessch" in df_ccd.columns
has_ncessch_meps = "ncessch" in df_meps.columns

print(f"\n'ncessch' in CCD: {has_ncessch_ccd}")
print(f"'ncessch' in MEPS: {has_ncessch_meps}")

h1_confirmed = not (has_ncessch_ccd and has_ncessch_meps)
print(f"\nRESULT: {'CONFIRMED' if h1_confirmed else 'REFUTED'}")

# --- Hypothesis 2: Type mismatch ---
# INTENT: Test whether the join key has different data types across datasets.
# REASONING: Polars inner join on mismatched types (e.g., Int64 vs Utf8) will
# produce zero matches because no value can be equal across types.
print("\n" + "=" * 60)
print("HYPOTHESIS 2: Type mismatch")
print("=" * 60)

ccd_type = df_ccd["ncessch"].dtype
meps_type = df_meps["ncessch"].dtype

print(f"CCD ncessch type: {ccd_type}")
print(f"MEPS ncessch type: {meps_type}")

h2_confirmed = ccd_type != meps_type
print(f"\nRESULT: {'CONFIRMED' if h2_confirmed else 'REFUTED'} - {ccd_type} vs {meps_type}")

# --- Hypothesis 3: Value format difference ---
# INTENT: Test whether key values have different formatting (e.g., leading
# zeros stripped from integer representation) even if types appear compatible.
# REASONING: NCES IDs are 12-digit codes. If one source stores them as integers,
# leading zeros are lost (e.g., 010000000001 becomes 10000000001), preventing match.
print("\n" + "=" * 60)
print("HYPOTHESIS 3: Value format difference")
print("=" * 60)

ccd_sample = df_ccd["ncessch"].head(5).to_list()
meps_sample = df_meps["ncessch"].head(5).to_list()
print(f"CCD sample values: {ccd_sample}")
print(f"MEPS sample values: {meps_sample}")

if df_ccd["ncessch"].dtype == pl.Utf8:
    ccd_lengths = df_ccd["ncessch"].str.len_chars().unique().to_list()
    print(f"CCD string lengths: {sorted(ccd_lengths)}")

if df_meps["ncessch"].dtype == pl.Utf8:
    meps_lengths = df_meps["ncessch"].str.len_chars().unique().to_list()
    print(f"MEPS string lengths: {sorted(meps_lengths)}")

ccd_keys = set(str(x) for x in df_ccd["ncessch"].unique().to_list())
meps_keys = set(str(x) for x in df_meps["ncessch"].unique().to_list())
overlap = len(ccd_keys & meps_keys)
print(f"\nKey overlap (as strings): {overlap} / {len(ccd_keys)}")

h3_confirmed = overlap < len(ccd_keys) * 0.5
print(f"\nRESULT: {'CONFIRMED - Format difference causing low overlap' if h3_confirmed else 'REFUTED - Good overlap as strings'}")

# --- Summary ---
# ASSUMES: If H2 or H3 is confirmed, the root cause is key format/type mismatch
# and the fix is to normalize both keys to zero-padded 12-character strings.
# If all hypotheses are refuted, a different diagnostic approach is needed.
print("\n" + "=" * 60)
print("DIAGNOSIS SUMMARY")
print("=" * 60)
print(f"H1 (column names): {'CONFIRMED' if h1_confirmed else 'REFUTED'}")
print(f"H2 (type mismatch): {'CONFIRMED' if h2_confirmed else 'REFUTED'}")
print(f"H3 (value format): {'CONFIRMED' if h3_confirmed else 'REFUTED'}")

if h2_confirmed or h3_confirmed:
    print("\nROOT CAUSE: Key format/type mismatch")
    print("\n" + "=" * 60)
    print("RECOMMENDED FIX")
    print("=" * 60)
    print("""
# Cast both keys to string with consistent format
df_ccd = df_ccd.with_columns(
    pl.col("ncessch").cast(pl.Utf8).str.zfill(12).alias("ncessch")
)
df_meps = df_meps.with_columns(
    pl.col("ncessch").cast(pl.Utf8).str.zfill(12).alias("ncessch")
)

# Now join
df = df_ccd.join(df_meps, on="ncessch", how="inner")
""")
    print("Verification: Re-run join with normalized keys and check row count > 0")

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

---

## QA Script Template

QA scripts are created by **code-reviewer** to validate outputs independently from the original execution script.

**Reference:** See `agent_reference/QA_CHECKPOINTS.md` for complete QA checkpoint definitions (QA1-QA4b) and stage-specific validation criteria.

### QA Script Structure

```python
#!/usr/bin/env python3
"""
QA Inspection: Stage {N} Step {step}

Reviewed Script: scripts/stage{N}_{type}/{step}_{task-name}.py
Output Files: {list of output files}
Plan Reference: {plan_path}

QA Checks:
1. Schema validation
2. Row count verification
3. Distribution sanity
4. Coded value absence
5. Critical null check
"""

import polars as pl
from pathlib import Path

# --- Config ---
# QA inspection configuration. Expected values are derived from the Plan
# specification and the reviewed script's checkpoint assertions. This script
# provides independent secondary validation of the output data.
PROJECT_DIR = Path("/daaf/research/{project_name}")
OUTPUT_FILE = PROJECT_DIR / "data" / "{subdir}" / "{filename}.parquet"

EXPECTED_COLUMNS = ["col1", "col2", "col3"]
EXPECTED_MIN_ROWS = 1000
EXPECTED_MAX_ROWS = 100000
CRITICAL_COLUMNS = ["id_col", "year"]
CODED_MISSING_VALUES = [-1, -2, -3]  # From Plan Domain Configuration; empty list if N/A

# --- Load ---
# Load the output file produced by the reviewed script. Verify it exists
# before attempting to read.
print("=" * 60)
print("QA INSPECTION: Stage {N} Step {step}")
print("=" * 60)

assert OUTPUT_FILE.exists(), f"FAIL: Output file not found: {OUTPUT_FILE}"

df = pl.read_parquet(OUTPUT_FILE)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Check 1: Schema ---
# INTENT: Verify all Plan-required columns exist in the output. Missing columns
# indicate the transformation dropped or failed to create expected fields.
missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
schema_ok = len(missing_cols) == 0
print(f"[{'PASS' if schema_ok else 'FAIL'}] Schema: {'OK' if schema_ok else f'Missing {missing_cols}'}")

# --- Check 2: Row count ---
# INTENT: Verify row count falls within the Plan's expected range. Counts far
# outside this range indicate a fetch, filter, or join error upstream.
rows_ok = EXPECTED_MIN_ROWS <= len(df) <= EXPECTED_MAX_ROWS
print(f"[{'PASS' if rows_ok else 'FAIL'}] Rows: {len(df):,} (expected {EXPECTED_MIN_ROWS:,}-{EXPECTED_MAX_ROWS:,})")

# --- Check 3: Distribution sanity ---
# INTENT: Detect degenerate distributions that indicate data corruption — e.g.,
# all values identical (constant column) or all zeros (failed computation).
dist_issues = []
for col in df.select(pl.col(pl.Int64, pl.Float64)).columns:
    col_data = df[col].drop_nulls()
    if len(col_data) == 0:
        continue
    if col_data.n_unique() == 1 and len(col_data) > 10:
        dist_issues.append(f"{col}: all same value ({col_data[0]})")
    if (col_data == 0).all():
        dist_issues.append(f"{col}: all zeros")

dist_ok = len(dist_issues) == 0
print(f"[{'PASS' if dist_ok else 'FAIL'}] Distribution: {'; '.join(dist_issues) if dist_issues else 'OK'}")

# --- Check 4: No coded values ---
# INTENT: Verify that domain-specific coded missing values have been properly
# replaced with null. Their presence in post-Stage-6 data would corrupt
# downstream statistical calculations.
# CODED_MISSING_VALUES from Plan's Domain Configuration (e.g., [-1, -2, -3] for education data).
# If empty, skip coded value checks.
coded_issues = []
if CODED_MISSING_VALUES:
    for col in df.columns:
        if df[col].dtype not in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            continue
        for code in CODED_MISSING_VALUES:
            count = (df[col] == code).sum()
            if count > 0:
                coded_issues.append(f"{col} has {count} coded value {code}")

coded_ok = len(coded_issues) == 0
print(f"[{'PASS' if coded_ok else 'FAIL'}] Coded values: {'; '.join(coded_issues) if coded_issues else 'None remain'}")

# --- Check 5: Critical nulls ---
# INTENT: Verify that identifier and key columns contain no nulls. Nulls in
# these columns would cause silent data loss in downstream joins and groupbys.
null_issues = []
for col in CRITICAL_COLUMNS:
    if col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_issues.append(f"{col}: {null_count} nulls")

nulls_ok = len(null_issues) == 0
print(f"[{'PASS' if nulls_ok else 'FAIL'}] Critical nulls: {'; '.join(null_issues) if null_issues else 'None'}")

# --- Summary ---
all_passed = all([schema_ok, rows_ok, dist_ok, coded_ok, nulls_ok])
print("\n" + "=" * 60)
print(f"QA STATUS: {'PASSED' if all_passed else 'ISSUES FOUND'}")
print("=" * 60)

if not all_passed:
    raise SystemExit(1)

# =============================================================================
# EXECUTION LOG
# Executed: [auto-appended after running]
# Duration: [auto-appended]
# Exit code: [auto-appended]
# --- STDOUT ---
# [auto-appended]
# =============================================================================
```

### QA Script Best Practices

| Practice | Rationale |
|----------|-----------|
| **Load data independently** | Don't trust the original script's data handling |
| **Use values from Plan** | Expected columns, row counts come from Plan specification |
| **Run default checks always** | Schema, rows, distribution, coded values, nulls |
| **Add discretionary checks** | Statistical tests, methodology checks when context warrants |
| **Exit non-zero on failure** | Use `raise SystemExit(1)` so the wrapper captures failure |
| **Save to scripts/cr/** | Keeps QA scripts separate from execution scripts |

