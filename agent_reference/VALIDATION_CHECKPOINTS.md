# Validation Checkpoints Reference

This document provides Python and R code templates for all four validation checkpoints, along with checkpoint classification for determining human involvement levels.

---

## File-First Execution Context

**IMPORTANT:** Validation checkpoint code runs **inside scripts**, not interactively.

The workflow is:
1. Write script to `scripts/stage{N}_{type}/` including validation code
2. Execute as a single Bash call: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py` (or `script.R` — automatically captures output, appends the execution log, and verifies it landed)
3. Validation results get automatically embedded in scripts as comments
4. Checkpoint status (PASSED/FAILED) is captured in the embedded execution log — but only trust it when the wrapper reported the record verified (no `EVIDENCE INCOMPLETE` banner / exit 74, and the log's `# Capture:` line reads `COMPLETE`); an incomplete record can truncate or omit the checkpoint lines. See `ERROR_RECOVERY.md` § Execution Wrapper Evidence Outcomes.

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol, complete script format, and checkpoint integration.

---

## Checkpoint Overview

### Primary Checkpoints (CP1-CP4)

| Checkpoint | When | Purpose | Classification | STOP Threshold |
|------------|------|---------|----------------|----------------|
| **CP1** | After data fetch (Stage 5) | Verify data structure | `checkpoint:auto` | Empty data, >90% missing |
| **CP2** | After cleaning (Stage 6) | Verify data quality | `checkpoint:auto` | >50% suppression, >90% loss |
| **CP3** | After transformation (Stage 7) | Verify data integrity | `checkpoint:auto` | >90% row loss, unexpected NAs |
| **CP4** | After analysis & visualization (Stage 8) | Verify analysis outputs, critical nulls, figures, and input source | `checkpoint:auto` | Non-finite/non-converged results, missing or empty figures, wrong input directory |

> **CP4 is a Stage-8 checkpoint, not a pre-delivery one.** Deliverable-level completeness — report sections present, Plan consistency, Research Outcomes addressed, Hypotheses assessed — is **not** CP4. It is the agent checklist in § Pre-Output Verification (Stage 12), classified `checkpoint:human-verify` and owned by the data-verifier agent.

### Additional Validation Blocks

| Block | When | Purpose | Halts on FAILED? |
|-------|------|---------|------------------|
| **Join-Specific Validation** | Any join (usually Stage 7) | Cardinality, fan-out, row loss, key matching | Yes (`raise` / `stop()`) |
| **Substantiveness Validation** | Stage 12 final review | Stub and placeholder detection in data, text, and code | No — **advisory only** |
| **Pre-Output Verification** | Stage 12 | Deliverable completeness against the Plan | Human gate (`checkpoint:human-verify`) |

> **Mode-specific blocks.** Data Onboarding Mode adds two further families, both `checkpoint:auto` and script-halting: **CPP1-CPP4 / CPP-SKILL** (§ Profiling Validation Checkpoints) on the standard path, and **CPS-INTAKE / CPS-GEN** (§ Synthetic-Path Validation Checkpoints, stages DS-3 and DS-5) on the privacy-preserving synthetic path.

### Secondary Checkpoints (QA1-QA4b)

QA checkpoints run AFTER primary checkpoints, providing independent secondary verification via code-reviewer agent. CP checkpoints validate operations; QA checkpoints validate outputs and methodology alignment.

**See:** `agent_reference/QA_CHECKPOINTS.md` for QA1-QA4b definitions, BLOCKER thresholds, severity classification, and complete QA checkpoint documentation.

---

## Per-Check Outcome Vocabulary

Every check in every template below prints **exactly one line** beginning with one of these tokens, and increments exactly one counter. No other line in a checkpoint block starts with `[`.

| Token | Meaning |
|-------|---------|
| `[PASS]` | The check ran on real inputs and the claimed condition held. **The line carries the observed evidence** — counts, rates, the values compared. A PASS without its numbers is not a PASS. |
| `[WARNING]` | The check ran; a non-fatal deviation was observed. Carries the numbers. (Replaces the retired `[WARN]` spelling.) |
| `[FAIL]` | The check ran; a fatal condition was observed — including an unrecognized configuration value, which is a present-but-wrong config, not a missing one. |
| `[NOT VERIFIED]` | The check **could not run**: a required input was missing, empty, `None`/`NULL`/`NA`, or of the wrong type, and the check was not declared not-applicable. The line names exactly what was missing. |
| `[SKIPPED]` | The check was declared not applicable in the template's `not_applicable` config, and the line prints the declared reason. Counted, never silent. |

**Why the two "did not run" tokens are distinct:** `[SKIPPED]` is a documented decision by the Plan author; `[NOT VERIFIED]` is an accident of configuration. Only the second one is a defect, and only the second one fails the checkpoint.

**Never put a `CP<n>` / `QA<n>` identifier on a per-check line.** `scripts/compare_execution_logs.py` treats any line containing `CP\d` plus PASS/FAIL as a checkpoint *verdict* line. Per-check lines describe the check, not the checkpoint.

**Presence testing, not truthiness.** Python: `is None`, `len(x) == 0`, `col not in df.columns` — never bare truthiness, because `0` and `0.0` are valid observed values. R: `is.null()`, `length(x) == 0`, `isTRUE()`; index config lists with `[[ ]]`, never `$` (partial matching silently binds the wrong key); guard `NA` before any `if ()`.

---

## Count Line and Verdict Line

Immediately before the verdict, every template prints a count line derived from the accumulator, then the verdict derived from the counts:

```
Checks: {passed} passed, {warning} warnings, {failed} failed, {not_verified} not verified, {skipped} skipped
CP3 VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED
```

Verdict rules (identical in both languages, all CP/Join/Substantiveness templates):

1. `FAILED` if `failed > 0` **or `not_verified > 0`** — a gate with missing evidence has not gated.
2. Otherwise `FAILED` if zero checks actually ran (`passed + warning + failed == 0`). An all-skipped checkpoint is not a pass.
3. Otherwise `PASSED WITH WARNINGS` if `warning > 0`.
4. Otherwise `PASSED`.

These three strings are the only permitted verdicts. Join prints `JOIN VALIDATION:`; the substantiveness blocks print `DATA SUBSTANTIVENESS:` / `TEXT SUBSTANTIVENESS:` / `CODE SUBSTANTIVENESS:`.

**Reported-status mapping.** The agent-reported status in return outputs stays the three-valued `PASSED | WARNING | FAILED` contract from `WORKFLOW_PHASE4_ANALYSIS.md`. The log line `PASSED WITH WARNINGS` maps to reported status **`WARNING`**; `PASSED` maps to `PASSED`; `FAILED` maps to `FAILED`. Report the mapped value, never the raw log string.

**Halting.** CP1-CP4 and Join `raise ValueError(...)` / `stop(...)` on `FAILED`, exactly as before. The substantiveness blocks are advisory and do **not** halt.

---

## Applicability Configuration (`not_applicable`)

Each template's `# --- Config ---` region declares one mapping of checks that genuinely do not apply to this dataset or domain:

```python
not_applicable = {}  # e.g. {"suppression": "CCD directory file carries no suppression code"}
```

```r
not_applicable <- list()  # e.g. list(suppression = "CCD directory file carries no suppression code")
```

Each check owns a stable snake_case key; the keys for each template are listed in that template's Usage Notes. Before running, a check tests, in order:

1. Key present in `not_applicable` with a non-empty reason → `[SKIPPED] <check>: <reason>`
2. Required inputs missing → `[NOT VERIFIED] <check>: <what is missing>`
3. Otherwise → run the check and emit `[PASS]` / `[WARNING]` / `[FAIL]` with the observed numbers.

A reason string is mandatory. Each template drops reason-less entries at config time so that an unexplained skip degrades to `[NOT VERIFIED]` rather than passing silently.

---

## Checkpoint Classification System

Not all checkpoints require the same level of human involvement. Use this classification to determine the appropriate interaction pattern.

### checkpoint:auto (Default)

**Definition:** Claude executes and validates automatically. No human interaction needed unless a STOP condition is triggered.

**Applies To:**
- CP1 post-fetch validation (when data is returned successfully)
- CP2 suppression rate calculation (when rate < 30%)
- CP3 transformation validation (when row counts match expectations)
- CP4 post-analysis & visualization validation (Stage 8 — when analysis outputs, figures, and the input source check all report evidence)
- Most code execution
- File saving operations
- Standard data fetch or data access calls

**Behavior:**
1. Execute action
2. Validate result — every check emits one outcome token and counts itself
3. If the derived verdict is `PASSED` → Proceed automatically
4. If `PASSED WITH WARNINGS` → Proceed, report status `WARNING`, and surface the warning lines
5. If `FAILED` → the block raises/stops; STOP condition triggered. `FAILED` includes the case where a check could not run (`[NOT VERIFIED]`), because an ungated gate is not a pass

**Example:**
```python
# CP1 auto-validation (inline)
# ... CP1 inline validation block runs here ...
# cp1 = {"passed": .., "warning": .., "failed": .., "not_verified": .., "skipped": ..}
# Verdict is derived from those counters, never asserted:
#   PASSED               → proceed automatically to next stage
#   PASSED WITH WARNINGS → proceed; report status WARNING
#   FAILED               → raises ValueError, STOP condition triggered
```

---

### checkpoint:human-verify (Report and Confirm)

**Definition:** Claude automates the action, then reports results for human confirmation before proceeding to the next major step.

**Applies To:**
- Unusual suppression patterns (30-50% range)
- Unexpected data distributions
- Methodology decisions with tradeoffs
- Final Report before delivery
- Data lag detection (≥3 years)
- COVID-19 data quality warnings
- First-time use of a data source
- Results that differ significantly from expectations

**Behavior:**
1. Execute action
2. Present results with full context
3. Ask: "The results show [X]. Should I proceed with this?"
4. Wait for explicit confirmation ("yes", "proceed", "confirmed")
5. Document decision in Plan
6. Proceed only after confirmation

**Example:**
```markdown
**Human Verification Required: Suppression Rate**

CP2 validation found a suppression rate of 38% for the enrollment variable.

**Context:**
- This is below the 50% STOP threshold
- However, it's higher than typical (usually 10-20%)
- Affected: 38,000 of 100,000 records

**Options:**
1. Proceed with 38% suppression (document in limitations)
2. Aggregate to district level (reduces suppression to ~5%)
3. Exclude suppressed variable from analysis

**Recommendation:** Option 1 is acceptable for this analysis type.

Should I proceed with the current suppression rate?
```

---

### checkpoint:decision (User Choice Required)

**Definition:** Multiple valid paths exist with meaningful tradeoffs. User must choose before execution can continue.

**Applies To:**
- Which data sources to prioritize when multiple are available
- How to handle edge cases (aggregate vs. exclude vs. impute)
- Visualization style preferences
- Scope adjustments when data is limited
- Methodology alternatives (e.g., mean vs. median)
- Geographic scope choices
- Year range adjustments

**Behavior:**
1. Present options with clear pros/cons
2. Do NOT proceed without selection
3. Ask: "Which approach would you prefer?"
4. Wait for explicit selection
5. Document choice and rationale in Plan
6. Execute selected option

**Example:**
```markdown
**Decision Required: Handling Missing Poverty Data**

The MEPS poverty data is missing for 15% of schools. Three valid approaches exist:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A | Exclude schools with missing data | Clean analysis | Loses 15% of sample |
| B | Impute using district averages | Preserves sample size | Introduces estimation |
| C | Aggregate to district level | Eliminates missingness | Loses school-level detail |

**Research Question Consideration:**
Your question asks about school-level patterns, which favors Option A or B.

Which approach would you prefer?
```

---

### checkpoint:human-action (User Must Execute)

**Definition:** Claude cannot automate this step. User must perform the action themselves.

**Applies To:**
- External system authentication (e.g., restricted databases)
- Manual data entry (e.g., institutional data requests)
- File downloads from restricted sources
- API key configuration
- Credential management
- Physical verification (e.g., confirming data received)
- Approval workflows outside Claude's access

**Behavior:**
1. Explain what needs to happen
2. Provide specific, actionable instructions
3. Ask user to confirm when action is complete
4. Verify action was successful before proceeding
5. Document completion in Plan

**Example:**
```markdown
**Human Action Required: Institutional Data Access**

The analysis requires restricted institutional data from [source].

**Required Steps:**
1. Navigate to [URL]
2. Log in with your institutional credentials
3. Request access to dataset [name]
4. Download the file when approved
5. Place the file in: `research/[project]/data/raw/`

**File Expected:** `institutional_data.csv` or `.xlsx`

Please confirm when the file is in place, and I'll continue with the analysis.
```

---

### Key Rule: Automation Preference

**If Claude CAN automate (data access call, file operation, code execution), Claude MUST automate.**

Reserve human checkpoints for genuinely necessary cases:

| Situation | Correct Classification |
|-----------|----------------------|
| data access call succeeded | checkpoint:auto |
| data access call failed after 3 retries | STOP condition |
| Suppression rate is 15% | checkpoint:auto |
| Suppression rate is 45% | checkpoint:human-verify |
| Suppression rate is 55% | STOP condition |
| Choose between 2 valid methodologies | checkpoint:decision |
| External login required | checkpoint:human-action |

---

### Classification Decision Tree

```
Can Claude execute this action automatically?
├─ NO → checkpoint:human-action
└─ YES → Continue

Does the action involve external credentials/access?
├─ YES → checkpoint:human-action
└─ NO → Continue

Is the result within normal/expected parameters?
├─ NO → Does it hit a STOP threshold?
│   ├─ YES → STOP condition (escalate)
│   └─ NO → checkpoint:human-verify
└─ YES → Continue

Are there multiple valid approaches requiring user preference?
├─ YES → checkpoint:decision
└─ NO → checkpoint:auto
```

---

### Checkpoint Classification by Stage

| Stage | Checkpoint(s) | Default Classification | Elevate to human-verify If |
|-------|---------------|----------------------|---------------------------|
| 5 (Fetch) | CP1 | auto | Data lag ≥3 years, unexpected shape |
| 5-QA | QA1 | auto | Methodology BLOCKER (escalate immediately) |
| 6 (Clean) | CP2 | auto | Suppression 30-50%, unusual patterns |
| 6-QA | QA2 | auto | Methodology BLOCKER (escalate immediately) |
| 7 (Transform) | CP3, Join Validation | auto | Row loss 50-90%, unexpected nulls |
| 7-QA | QA3 | auto | Methodology BLOCKER (escalate immediately) |
| 8 (Analyze & Visualize) | **CP4** | auto | Results differ from expectations |
| 8-QA | QA4a | auto | Methodology BLOCKER (escalate immediately) |
| 9 (Notebook) | — | auto | Execution warnings |
| 10 (QA Aggregation) | — | auto | Unresolved BLOCKERs, WARNING patterns, missing QA reviews |
| 11 (Report) | — | human-verify | Always verify before delivery |
| 12 (Final Review) | **Pre-Output Verification**, Substantiveness Validation, QA4b | human-verify | Always verify before delivery |

**CP4 placement.** CP4 is `checkpoint:auto` and runs **inside the Stage-8 analysis and visualization scripts** — it validates analysis outputs, critical nulls, figures, and the input source at the moment those artifacts are produced. Deliverable completeness at Stages 11-12 is covered by § Pre-Output Verification (Stage 12), which is `checkpoint:human-verify` and owned by data-verifier. Nothing at Stage 11 or 12 is labelled CP4.

**Note:** QA substages (5-QA through 8-QA) run SEPARATELY after EACH individual Stage 5-8 script execution — not once at stage end. For example: Stage 5 with 2 fetch scripts = 2 independent QA1 invocations, each reviewing one script's output in isolation before the next script begins. Technical BLOCKERs trigger revision attempts (max 2 per script); methodology BLOCKERs escalate immediately.

---

## CP1: Post-Fetch Validation

**When:** Immediately after retrieving data from a data access mirror (Stage 5)
**Purpose:** Verify data structure and completeness before proceeding
**Classification:** `checkpoint:auto` — halts on `FAILED`

### Code Template

```python
import polars as pl

# --- CP1 Validation: Post-Fetch ---
# INTENT: Verify fetched data structure and completeness before cleaning: shape,
# row-count reasonableness, required columns, year coverage, missingness, data
# lag, and flagged-year exposure.
# REASONING: Each check emits exactly one outcome token and increments exactly one
# counter, so the verdict is derived from what actually ran. A check that cannot
# run says so ([NOT VERIFIED]) and fails the checkpoint rather than passing silently.
# ASSUMES: df is the fetched DataFrame; expected_rows / required_cols /
# expected_years / year_col / FLAG_YEARS / not_applicable are configured above
# from the Plan's specification and Domain Configuration.
print("\n" + "=" * 60)
print("CP1 VALIDATION: POST-FETCH")
print("=" * 60)

# INTENT: A declared skip without a reason is indistinguishable from a silent one.
# REASONING: Dropping reason-less entries here degrades them to [NOT VERIFIED].
not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cp1 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Check: shape
print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} cols")
if df.shape[0] == 0:
    print("[FAIL] shape: 0 rows returned from the data access mirror")
    cp1["failed"] += 1
else:
    print(f"[PASS] shape: {df.shape[0]:,} rows x {df.shape[1]} cols loaded")
    cp1["passed"] += 1

# Check: row-count reasonableness vs the Plan's expected_rows
# ASSUMES: expected_rows is a positive Plan estimate; 0/None means the Plan made none.
if "row_count" in not_applicable:
    print(f"[SKIPPED] row count: {not_applicable['row_count']}")
    cp1["skipped"] += 1
elif expected_rows is None or not isinstance(expected_rows, (int, float)) or expected_rows <= 0:
    print(f"[NOT VERIFIED] row count: expected_rows is {expected_rows!r} — no positive Plan estimate to compare against")
    cp1["not_verified"] += 1
elif df.shape[0] == 0:
    print(f"[FAIL] row count: 0 rows fetched vs expected ~{expected_rows:,} — nothing to compare")
    cp1["failed"] += 1
else:
    ratio = df.shape[0] / expected_rows
    if ratio < 0.01:
        print(f"[WARNING] row count: {df.shape[0]:,} rows vs expected ~{expected_rows:,} (ratio {ratio:.2f}x — far lower)")
        cp1["warning"] += 1
    elif ratio > 10:
        print(f"[WARNING] row count: {df.shape[0]:,} rows vs expected ~{expected_rows:,} (ratio {ratio:.2f}x — far higher)")
        cp1["warning"] += 1
    else:
        print(f"[PASS] row count: {df.shape[0]:,} rows vs expected ~{expected_rows:,} (ratio {ratio:.2f}x, within 0.01x-10x)")
        cp1["passed"] += 1

# Check: required columns present
if "required_columns" in not_applicable:
    print(f"[SKIPPED] required columns: {not_applicable['required_columns']}")
    cp1["skipped"] += 1
elif required_cols is None or len(required_cols) == 0:
    print("[NOT VERIFIED] required columns: required_cols is empty — the Plan named no columns to verify")
    cp1["not_verified"] += 1
else:
    missing_cols = [c for c in required_cols if c not in df.columns]
    if len(missing_cols) > 0:
        print(f"[FAIL] required columns: {len(missing_cols)} of {len(required_cols)} absent: {missing_cols}")
        cp1["failed"] += 1
    else:
        print(f"[PASS] required columns: all {len(required_cols)} present ({', '.join(required_cols)})")
        cp1["passed"] += 1

# Check: expected year coverage
if "year_coverage" in not_applicable:
    print(f"[SKIPPED] year coverage: {not_applicable['year_coverage']}")
    cp1["skipped"] += 1
elif year_col is None:
    print("[NOT VERIFIED] year coverage: year_col is None — declare not_applicable['year_coverage'] if this dataset has no temporal dimension")
    cp1["not_verified"] += 1
elif expected_years is None or len(expected_years) == 0:
    print("[NOT VERIFIED] year coverage: expected_years is empty — no Plan year range to check against")
    cp1["not_verified"] += 1
elif year_col not in df.columns:
    print(f"[FAIL] year coverage: year column '{year_col}' absent from the fetched frame")
    cp1["failed"] += 1
else:
    present_years = sorted(df[year_col].drop_nulls().unique().to_list())
    missing_years = [y for y in expected_years if y not in present_years]
    if len(missing_years) > 0:
        print(f"[WARNING] year coverage: {len(missing_years)} of {len(expected_years)} expected years absent {missing_years} (present: {present_years})")
        cp1["warning"] += 1
    else:
        print(f"[PASS] year coverage: all {len(expected_years)} expected years present (present: {present_years})")
        cp1["passed"] += 1

# Check: missingness — one check per required column
print("\nMissingness (per required column):")
if "missingness" in not_applicable:
    print(f"[SKIPPED] missingness: {not_applicable['missingness']}")
    cp1["skipped"] += 1
elif required_cols is None or len(required_cols) == 0:
    print("[NOT VERIFIED] missingness: required_cols is empty — no columns to measure")
    cp1["not_verified"] += 1
elif df.shape[0] == 0:
    print("[FAIL] missingness: 0 rows fetched — null rates undefined")
    cp1["failed"] += 1
else:
    for col in required_cols:
        if col not in df.columns:
            print(f"[FAIL] missingness '{col}': column absent from the fetched frame — missingness untestable")
            cp1["failed"] += 1
            continue
        n_null = df[col].null_count()
        null_pct = n_null / df.shape[0] * 100
        if null_pct > 90:
            print(f"[FAIL] missingness '{col}': {null_pct:.1f}% null ({n_null:,}/{df.shape[0]:,}, >90% threshold)")
            cp1["failed"] += 1
        elif null_pct > 50:
            print(f"[WARNING] missingness '{col}': {null_pct:.1f}% null ({n_null:,}/{df.shape[0]:,}, high)")
            cp1["warning"] += 1
        elif null_pct > 5:
            print(f"[WARNING] missingness '{col}': {null_pct:.1f}% null ({n_null:,}/{df.shape[0]:,})")
            cp1["warning"] += 1
        else:
            print(f"[PASS] missingness '{col}': {null_pct:.1f}% null ({n_null:,}/{df.shape[0]:,}, <=5%)")
            cp1["passed"] += 1

# Check: year freshness (data lag detection)
if "year_freshness" in not_applicable:
    print(f"[SKIPPED] year freshness: {not_applicable['year_freshness']}")
    cp1["skipped"] += 1
elif year_col is None or expected_years is None or len(expected_years) == 0:
    print(f"[NOT VERIFIED] year freshness: year_col is {year_col!r} and expected_years has {0 if expected_years is None else len(expected_years)} entries")
    cp1["not_verified"] += 1
elif year_col not in df.columns:
    print(f"[FAIL] year freshness: year column '{year_col}' absent from the fetched frame")
    cp1["failed"] += 1
elif df.shape[0] == 0 or df[year_col].null_count() == df.shape[0]:
    # ASSUMES: an all-null year column cannot yield a maximum; R's max() would return -Inf.
    print(f"[FAIL] year freshness: '{year_col}' is entirely null over {df.shape[0]:,} rows — latest year undefined")
    cp1["failed"] += 1
else:
    max_expected = max(expected_years)
    max_actual = df[year_col].max()
    if max_actual < max_expected:
        lag_years = max_expected - max_actual
        print(f"[WARNING] year freshness: requested through {max_expected}, latest available {max_actual} ({lag_years}-year lag)")
        cp1["warning"] += 1
    else:
        print(f"[PASS] year freshness: latest available {max_actual} >= requested {max_expected} (no lag)")
        cp1["passed"] += 1

# Check: flagged years actually present in the fetched data
# REASONING: This is a data fact, so it is computed from df, not from the Plan's
# expected_years — the Plan can request a year the mirror does not return.
if "flag_years" in not_applicable:
    print(f"[SKIPPED] flagged years: {not_applicable['flag_years']}")
    cp1["skipped"] += 1
elif FLAG_YEARS is None or len(FLAG_YEARS) == 0:
    print("[NOT VERIFIED] flagged years: FLAG_YEARS is empty — declare not_applicable['flag_years'] if the domain flags no years")
    cp1["not_verified"] += 1
elif year_col is None or year_col not in df.columns:
    print(f"[NOT VERIFIED] flagged years: year column {year_col!r} unavailable — flagged-year exposure not computable")
    cp1["not_verified"] += 1
else:
    present_years = set(df[year_col].drop_nulls().unique().to_list())
    flagged_present = sorted(y for y in FLAG_YEARS if y in present_years)
    if len(flagged_present) > 0:
        print(f"[WARNING] flagged years: fetched data includes {flagged_present} of flagged set {list(FLAG_YEARS)} — document comparability concerns in limitations")
        cp1["warning"] += 1
    else:
        print(f"[PASS] flagged years: none of {list(FLAG_YEARS)} present in the fetched data")
        cp1["passed"] += 1

# Count line, then verdict derived from the counts (never asserted)
cp1_checks_run = cp1["passed"] + cp1["warning"] + cp1["failed"]
if cp1["failed"] > 0 or cp1["not_verified"] > 0 or cp1_checks_run == 0:
    cp1_verdict = "FAILED"
elif cp1["warning"] > 0:
    cp1_verdict = "PASSED WITH WARNINGS"
else:
    cp1_verdict = "PASSED"

print(f"\nChecks: {cp1['passed']} passed, {cp1['warning']} warnings, {cp1['failed']} failed, {cp1['not_verified']} not verified, {cp1['skipped']} skipped")
print(f"CP1 VALIDATION: {cp1_verdict}")
print("=" * 60)

if cp1_verdict == "FAILED":
    raise ValueError("CP1 FAILED - see details above")
```

### R Code Template

```r
library(dplyr)
library(arrow)

# --- CP1 Validation: Post-Fetch ---
# INTENT: Verify fetched data structure and completeness before cleaning: shape,
# row-count reasonableness, required columns, year coverage, missingness, data
# lag, and flagged-year exposure.
# REASONING: Each check emits exactly one outcome token and increments exactly one
# counter, so the verdict is derived from what actually ran.
# ASSUMES: df is the fetched data frame; expected_rows / required_cols /
# expected_years / year_col / FLAG_YEARS / not_applicable are configured above.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CP1 VALIDATION: POST-FETCH\n")
cat(strrep("=", 60), "\n")

# INTENT: Drop declared-not-applicable entries that carry no reason.
na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cp1 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# Check: shape
cat(sprintf("\nShape: %s rows x %s cols\n", format(nrow(df), big.mark = ","), ncol(df)))
if (nrow(df) == 0) {
  cat("[FAIL] shape: 0 rows returned from the data access mirror\n")
  cp1["failed"] <- cp1["failed"] + 1L
} else {
  cat(sprintf("[PASS] shape: %s rows x %d cols loaded\n", format(nrow(df), big.mark = ","), ncol(df)))
  cp1["passed"] <- cp1["passed"] + 1L
}

# Check: row-count reasonableness vs the Plan's expected_rows
if ("row_count" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row count: %s\n", not_applicable[["row_count"]]))
  cp1["skipped"] <- cp1["skipped"] + 1L
} else if (is.null(expected_rows) || length(expected_rows) != 1 || !is.numeric(expected_rows) ||
           is.na(expected_rows) || expected_rows <= 0) {
  cat("[NOT VERIFIED] row count: expected_rows is missing, NA, or not a positive Plan estimate\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else if (nrow(df) == 0) {
  cat(sprintf("[FAIL] row count: 0 rows fetched vs expected ~%s — nothing to compare\n",
              format(expected_rows, big.mark = ",")))
  cp1["failed"] <- cp1["failed"] + 1L
} else {
  ratio <- nrow(df) / expected_rows
  if (ratio < 0.01) {
    cat(sprintf("[WARNING] row count: %s rows vs expected ~%s (ratio %.2fx — far lower)\n",
                format(nrow(df), big.mark = ","), format(expected_rows, big.mark = ","), ratio))
    cp1["warning"] <- cp1["warning"] + 1L
  } else if (ratio > 10) {
    cat(sprintf("[WARNING] row count: %s rows vs expected ~%s (ratio %.2fx — far higher)\n",
                format(nrow(df), big.mark = ","), format(expected_rows, big.mark = ","), ratio))
    cp1["warning"] <- cp1["warning"] + 1L
  } else {
    cat(sprintf("[PASS] row count: %s rows vs expected ~%s (ratio %.2fx, within 0.01x-10x)\n",
                format(nrow(df), big.mark = ","), format(expected_rows, big.mark = ","), ratio))
    cp1["passed"] <- cp1["passed"] + 1L
  }
}

# Check: required columns present
if ("required_columns" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] required columns: %s\n", not_applicable[["required_columns"]]))
  cp1["skipped"] <- cp1["skipped"] + 1L
} else if (is.null(required_cols) || length(required_cols) == 0) {
  cat("[NOT VERIFIED] required columns: required_cols is empty — the Plan named no columns to verify\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else {
  missing_cols <- setdiff(required_cols, names(df))
  if (length(missing_cols) > 0) {
    cat(sprintf("[FAIL] required columns: %d of %d absent: %s\n",
                length(missing_cols), length(required_cols), paste(missing_cols, collapse = ", ")))
    cp1["failed"] <- cp1["failed"] + 1L
  } else {
    cat(sprintf("[PASS] required columns: all %d present (%s)\n",
                length(required_cols), paste(required_cols, collapse = ", ")))
    cp1["passed"] <- cp1["passed"] + 1L
  }
}

# Check: expected year coverage
if ("year_coverage" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] year coverage: %s\n", not_applicable[["year_coverage"]]))
  cp1["skipped"] <- cp1["skipped"] + 1L
} else if (is.null(year_col) || length(year_col) == 0) {
  cat("[NOT VERIFIED] year coverage: year_col is NULL — declare not_applicable$year_coverage if this dataset has no temporal dimension\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else if (is.null(expected_years) || length(expected_years) == 0) {
  cat("[NOT VERIFIED] year coverage: expected_years is empty — no Plan year range to check against\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else if (!year_col %in% names(df)) {
  cat(sprintf("[FAIL] year coverage: year column '%s' absent from the fetched frame\n", year_col))
  cp1["failed"] <- cp1["failed"] + 1L
} else {
  present_years <- sort(unique(df[[year_col]][!is.na(df[[year_col]])]))
  missing_years <- setdiff(expected_years, present_years)
  if (length(missing_years) > 0) {
    cat(sprintf("[WARNING] year coverage: %d of %d expected years absent (%s); present: %s\n",
                length(missing_years), length(expected_years),
                paste(missing_years, collapse = ", "), paste(present_years, collapse = ", ")))
    cp1["warning"] <- cp1["warning"] + 1L
  } else {
    cat(sprintf("[PASS] year coverage: all %d expected years present (%s)\n",
                length(expected_years), paste(present_years, collapse = ", ")))
    cp1["passed"] <- cp1["passed"] + 1L
  }
}

# Check: missingness — one check per required column
cat("\nMissingness (per required column):\n")
if ("missingness" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] missingness: %s\n", not_applicable[["missingness"]]))
  cp1["skipped"] <- cp1["skipped"] + 1L
} else if (is.null(required_cols) || length(required_cols) == 0) {
  cat("[NOT VERIFIED] missingness: required_cols is empty — no columns to measure\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else if (nrow(df) == 0) {
  cat("[FAIL] missingness: 0 rows fetched — NA rates undefined\n")
  cp1["failed"] <- cp1["failed"] + 1L
} else {
  for (col in required_cols) {
    if (!col %in% names(df)) {
      cat(sprintf("[FAIL] missingness '%s': column absent from the fetched frame — missingness untestable\n", col))
      cp1["failed"] <- cp1["failed"] + 1L
      next
    }
    n_null <- sum(is.na(df[[col]]))
    null_pct <- n_null / nrow(df) * 100
    if (null_pct > 90) {
      cat(sprintf("[FAIL] missingness '%s': %.1f%% NA (%s/%s, >90%% threshold)\n", col, null_pct,
                  format(n_null, big.mark = ","), format(nrow(df), big.mark = ",")))
      cp1["failed"] <- cp1["failed"] + 1L
    } else if (null_pct > 50) {
      cat(sprintf("[WARNING] missingness '%s': %.1f%% NA (%s/%s, high)\n", col, null_pct,
                  format(n_null, big.mark = ","), format(nrow(df), big.mark = ",")))
      cp1["warning"] <- cp1["warning"] + 1L
    } else if (null_pct > 5) {
      cat(sprintf("[WARNING] missingness '%s': %.1f%% NA (%s/%s)\n", col, null_pct,
                  format(n_null, big.mark = ","), format(nrow(df), big.mark = ",")))
      cp1["warning"] <- cp1["warning"] + 1L
    } else {
      cat(sprintf("[PASS] missingness '%s': %.1f%% NA (%s/%s, <=5%%)\n", col, null_pct,
                  format(n_null, big.mark = ","), format(nrow(df), big.mark = ",")))
      cp1["passed"] <- cp1["passed"] + 1L
    }
  }
}

# Check: year freshness (data lag detection)
if ("year_freshness" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] year freshness: %s\n", not_applicable[["year_freshness"]]))
  cp1["skipped"] <- cp1["skipped"] + 1L
} else if (is.null(year_col) || length(year_col) == 0 || is.null(expected_years) || length(expected_years) == 0) {
  cat("[NOT VERIFIED] year freshness: year_col or expected_years not configured\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else if (!year_col %in% names(df)) {
  cat(sprintf("[FAIL] year freshness: year column '%s' absent from the fetched frame\n", year_col))
  cp1["failed"] <- cp1["failed"] + 1L
} else if (nrow(df) == 0 || all(is.na(df[[year_col]]))) {
  # REASONING: max(x, na.rm = TRUE) on an all-NA column returns -Inf and a nonsense lag.
  cat(sprintf("[FAIL] year freshness: '%s' is entirely NA over %s rows — latest year undefined\n",
              year_col, format(nrow(df), big.mark = ",")))
  cp1["failed"] <- cp1["failed"] + 1L
} else {
  max_expected <- max(expected_years, na.rm = TRUE)
  max_actual <- max(df[[year_col]], na.rm = TRUE)
  if (max_actual < max_expected) {
    lag_years <- max_expected - max_actual
    cat(sprintf("[WARNING] year freshness: requested through %d, latest available %d (%d-year lag)\n",
                as.integer(max_expected), as.integer(max_actual), as.integer(lag_years)))
    cp1["warning"] <- cp1["warning"] + 1L
  } else {
    cat(sprintf("[PASS] year freshness: latest available %d >= requested %d (no lag)\n",
                as.integer(max_actual), as.integer(max_expected)))
    cp1["passed"] <- cp1["passed"] + 1L
  }
}

# Check: flagged years actually present in the fetched data
if ("flag_years" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] flagged years: %s\n", not_applicable[["flag_years"]]))
  cp1["skipped"] <- cp1["skipped"] + 1L
} else if (is.null(FLAG_YEARS) || length(FLAG_YEARS) == 0) {
  cat("[NOT VERIFIED] flagged years: FLAG_YEARS is empty — declare not_applicable$flag_years if the domain flags no years\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else if (is.null(year_col) || length(year_col) == 0 || !year_col %in% names(df)) {
  cat("[NOT VERIFIED] flagged years: year column unavailable — flagged-year exposure not computable\n")
  cp1["not_verified"] <- cp1["not_verified"] + 1L
} else {
  present_years <- unique(df[[year_col]][!is.na(df[[year_col]])])
  flagged_present <- sort(FLAG_YEARS[FLAG_YEARS %in% present_years])
  if (length(flagged_present) > 0) {
    cat(sprintf("[WARNING] flagged years: fetched data includes %s of flagged set %s — document comparability concerns in limitations\n",
                paste(flagged_present, collapse = ", "), paste(FLAG_YEARS, collapse = ", ")))
    cp1["warning"] <- cp1["warning"] + 1L
  } else {
    cat(sprintf("[PASS] flagged years: none of %s present in the fetched data\n",
                paste(FLAG_YEARS, collapse = ", ")))
    cp1["passed"] <- cp1["passed"] + 1L
  }
}

# Count line, then verdict derived from the counts (never asserted)
cp1_checks_run <- cp1[["passed"]] + cp1[["warning"]] + cp1[["failed"]]
if (cp1[["failed"]] > 0 || cp1[["not_verified"]] > 0 || cp1_checks_run == 0) {
  cp1_verdict <- "FAILED"
} else if (cp1[["warning"]] > 0) {
  cp1_verdict <- "PASSED WITH WARNINGS"
} else {
  cp1_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cp1[["passed"]], cp1[["warning"]], cp1[["failed"]], cp1[["not_verified"]], cp1[["skipped"]]))
cat(sprintf("CP1 VALIDATION: %s\n", cp1_verdict))
cat(strrep("=", 60), "\n")

if (cp1_verdict == "FAILED") {
  stop("CP1 FAILED - see details above")
}
```

### Usage Notes

Adapt the inline code above to each fetch script. Set these variables before running:

**Python:**
```python
# Configure before CP1 block
expected_rows = 10000
required_cols = ["ncessch", "school_name", "enrollment", "year"]
expected_years = [2020, 2021, 2022]

# Domain configuration (from Plan's Domain Configuration section)
YEAR_COL = "year"              # From Plan domain config; None if no temporal dimension
FLAG_YEARS = [2020, 2021]      # From Plan domain config; education default: COVID years
# Education domain defaults: YEAR_COL = "year", FLAG_YEARS = [2020, 2021]

year_col = YEAR_COL

# Checks that genuinely do not apply, each with a mandatory reason
not_applicable = {}  # e.g. {"flag_years": "domain flags no years"}
# df = <your fetched DataFrame>
```

**R:**
```r
# Configure before CP1 block
expected_rows <- 10000
required_cols <- c("ncessch", "school_name", "enrollment", "year")
expected_years <- c(2020, 2021, 2022)

# Domain configuration (from Plan's Domain Configuration section)
YEAR_COL <- "year"              # From Plan domain config; NULL if no temporal dimension
FLAG_YEARS <- c(2020, 2021)     # From Plan domain config; education default: COVID years
# Education domain defaults: YEAR_COL = "year", FLAG_YEARS = c(2020, 2021)

year_col <- YEAR_COL

# Checks that genuinely do not apply, each with a mandatory reason
not_applicable <- list()  # e.g. list(flag_years = "domain flags no years")
# df <- <your fetched data frame>
```

**`not_applicable` keys recognized by CP1:**

| Key | Suppresses | Declare it when |
|-----|-----------|-----------------|
| `row_count` | Row-count reasonableness vs `expected_rows` | The Plan deliberately made no row estimate (e.g. exploratory first fetch) |
| `required_columns` | Required-column presence | The fetch is a schema discovery run with no committed column list |
| `year_coverage` | Expected-year coverage | The dataset has no temporal dimension |
| `missingness` | Per-column null rates | Nulls are the analytic subject and thresholds are meaningless |
| `year_freshness` | Data-lag detection | The Plan pins a historical vintage on purpose |
| `flag_years` | Flagged-year exposure | The domain flags no years (`FLAG_YEARS` legitimately empty) |

**Semantics reminders:**
- `[NOT VERIFIED]` means the check could not run — it makes the verdict `FAILED`. If a check genuinely does not apply, declare it in `not_applicable` with a reason so it becomes a counted `[SKIPPED]` instead. An empty year list or `year_col = None` without such a declaration is a configuration defect, not a pass.
- `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`** in the executor's return output; `PASSED` maps to `PASSED`, `FAILED` to `FAILED`.
- A CP1 block where every check was skipped prints `FAILED` — an all-skipped checkpoint has verified nothing.

---

## CP2: Post-Cleaning Validation

**When:** After applying coded value filters and suppression handling (Stage 6)
**Purpose:** Verify data quality after cleaning operations
**Classification:** `checkpoint:auto` — halts on `FAILED`

### Code Template

```python
import numbers

import polars as pl

# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning — confirm data loss is acceptable,
# suppression rates are within tolerance, and coded missing values are gone.
# REASONING: Suppression is measured per column as the share of that column's raw
# values carrying the domain suppression sentinel — NOT as row attrition, which is
# identical for every column and reads 0% whenever suppression is handled by
# nulling in place (the DAAF-normal path).
# ASSUMES: raw_df is pre-cleaning state, clean_df is post-cleaning state,
# key_variables lists the columns to validate, and the domain config below is
# taken from the Plan's Domain Configuration section.
print("\n" + "=" * 60)
print("CP2 VALIDATION: POST-CLEANING")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cp2 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}
max_suppression = SUPPRESSION_THRESHOLD  # From Plan domain config (education default: 0.5)
max_data_loss = 0.9                      # 90% threshold

# Shared numeric-dtype predicate — the same list is used by the substantiveness
# checks, so a UInt or Int8 column cannot be silently exempted in one and not the other.
NUMERIC_DTYPES = [pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                  pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                  pl.Float32, pl.Float64]

raw_rows = len(raw_df)
clean_rows = len(clean_df)
rows_removed = raw_rows - clean_rows

print("\nData Loss:")
print(f"  Raw rows:     {raw_rows:,}")
print(f"  Clean rows:   {clean_rows:,}")
print(f"  Rows removed: {rows_removed:,}")

# Check: data loss
if "data_loss" in not_applicable:
    print(f"[SKIPPED] data loss: {not_applicable['data_loss']}")
    cp2["skipped"] += 1
elif raw_rows == 0:
    print("[FAIL] data loss: raw_df is empty (0 rows) — loss rate undefined, cleaning untestable")
    cp2["failed"] += 1
else:
    loss_rate = rows_removed / raw_rows
    if loss_rate > max_data_loss:
        print(f"[FAIL] data loss: {loss_rate:.1%} ({rows_removed:,}/{raw_rows:,}) exceeds {max_data_loss:.0%} threshold")
        cp2["failed"] += 1
    elif loss_rate > 0.5:
        print(f"[WARNING] data loss: {loss_rate:.1%} ({rows_removed:,}/{raw_rows:,}) is high")
        cp2["warning"] += 1
    else:
        print(f"[PASS] data loss: {loss_rate:.1%} ({rows_removed:,}/{raw_rows:,}) within {max_data_loss:.0%} tolerance")
        cp2["passed"] += 1

# Check: suppression rate per key variable (measured on raw data)
print("\nSuppression Rates (share of raw column values carrying the suppression sentinel):")
if "suppression" in not_applicable:
    print(f"[SKIPPED] suppression: {not_applicable['suppression']}")
    cp2["skipped"] += 1
elif key_variables is None or len(key_variables) == 0:
    print("[NOT VERIFIED] suppression: key_variables is empty — no columns nominated for a suppression rate")
    cp2["not_verified"] += 1
elif SUPPRESSION_CODE is None:
    print("[NOT VERIFIED] suppression: SUPPRESSION_CODE is None — the sentinel is unknown, so no rate can be computed. "
          "Declare not_applicable['suppression'] with a reason if this domain truly has no suppression code")
    cp2["not_verified"] += 1
elif raw_rows == 0:
    print("[FAIL] suppression: raw_df is empty (0 rows) — suppression rate undefined")
    cp2["failed"] += 1
else:
    for var in key_variables:
        if var not in raw_df.columns:
            print(f"[FAIL] suppression '{var}': column absent from raw_df — rate untestable")
            cp2["failed"] += 1
            continue
        # REASONING: Polars compares a string column against a numeric sentinel by
        # returning all-False rather than raising, so an unguarded compare on a
        # string-typed column reports "[PASS] 0.0%" over a fully suppressed column —
        # the exact evidence-free pass this template exists to remove. Guard on
        # comparability in BOTH directions: a numeric sentinel needs a numeric
        # column, and a string sentinel needs a non-numeric one.
        sentinel_is_numeric = isinstance(SUPPRESSION_CODE, numbers.Real) and not isinstance(SUPPRESSION_CODE, bool)
        column_is_numeric = raw_df[var].dtype in NUMERIC_DTYPES
        if sentinel_is_numeric != column_is_numeric:
            print(f"[NOT VERIFIED] suppression '{var}': column dtype {raw_df[var].dtype} is not comparable to sentinel {SUPPRESSION_CODE!r} — the comparison would silently match 0 rows rather than raise")
            cp2["not_verified"] += 1
            continue
        suppressed = int((raw_df[var] == SUPPRESSION_CODE).sum())
        supp_rate = suppressed / raw_rows
        if supp_rate > max_suppression:
            print(f"[FAIL] suppression '{var}': {supp_rate:.1%} (n={suppressed:,}/{raw_rows:,} sentinel {SUPPRESSION_CODE}) exceeds {max_suppression:.0%} threshold")
            cp2["failed"] += 1
        elif supp_rate > 0.2:
            print(f"[WARNING] suppression '{var}': {supp_rate:.1%} (n={suppressed:,}/{raw_rows:,} sentinel {SUPPRESSION_CODE}) is notable")
            cp2["warning"] += 1
        else:
            print(f"[PASS] suppression '{var}': {supp_rate:.1%} (n={suppressed:,}/{raw_rows:,} sentinel {SUPPRESSION_CODE}) below {max_suppression:.0%} threshold")
            cp2["passed"] += 1

# Check: coded missing values remaining in clean data, per key variable
print("\nCoded Values Check (clean data):")
if "coded_values" in not_applicable:
    print(f"[SKIPPED] coded values: {not_applicable['coded_values']}")
    cp2["skipped"] += 1
elif key_variables is None or len(key_variables) == 0:
    print("[NOT VERIFIED] coded values: key_variables is empty — no columns nominated for the scan")
    cp2["not_verified"] += 1
elif CODED_MISSING_VALUES is None or len(CODED_MISSING_VALUES) == 0:
    print("[NOT VERIFIED] coded values: CODED_MISSING_VALUES is empty — no vocabulary to scan for. "
          "Declare not_applicable['coded_values'] with a reason if this domain uses none")
    cp2["not_verified"] += 1
else:
    for var in key_variables:
        if var not in clean_df.columns:
            print(f"[FAIL] coded values '{var}': column absent from clean_df — scan untestable")
            cp2["failed"] += 1
            continue
        if clean_df[var].dtype not in NUMERIC_DTYPES:
            print(f"[NOT VERIFIED] coded values '{var}': dtype {clean_df[var].dtype} is not numeric — numeric sentinels {list(CODED_MISSING_VALUES)} not comparable")
            cp2["not_verified"] += 1
            continue
        coded = int(sum((clean_df[var] == c).sum() for c in CODED_MISSING_VALUES))
        if coded > 0:
            print(f"[WARNING] coded values '{var}': {coded:,} of {len(clean_df):,} values still match {list(CODED_MISSING_VALUES)}")
            cp2["warning"] += 1
        else:
            print(f"[PASS] coded values '{var}': 0 of {len(clean_df):,} values match {list(CODED_MISSING_VALUES)}")
            cp2["passed"] += 1

# Count line, then verdict derived from the counts
cp2_checks_run = cp2["passed"] + cp2["warning"] + cp2["failed"]
if cp2["failed"] > 0 or cp2["not_verified"] > 0 or cp2_checks_run == 0:
    cp2_verdict = "FAILED"
elif cp2["warning"] > 0:
    cp2_verdict = "PASSED WITH WARNINGS"
else:
    cp2_verdict = "PASSED"

print(f"\nChecks: {cp2['passed']} passed, {cp2['warning']} warnings, {cp2['failed']} failed, {cp2['not_verified']} not verified, {cp2['skipped']} skipped")
print(f"CP2 VALIDATION: {cp2_verdict}")
print("=" * 60)

if cp2_verdict == "FAILED":
    raise ValueError("CP2 FAILED - see details above")
```

### R Code Template

```r
# --- CP2 Validation: Post-Cleaning ---
# INTENT: Verify data quality after cleaning — data loss, per-column suppression
# rates, and residual coded missing values.
# REASONING: Suppression is a per-column sentinel share, not row attrition.
# ASSUMES: raw_df is pre-cleaning state, clean_df is post-cleaning state,
# key_variables lists the columns to validate.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CP2 VALIDATION: POST-CLEANING\n")
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cp2 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)
max_suppression <- SUPPRESSION_THRESHOLD  # From Plan domain config (education default: 0.5)
max_data_loss <- 0.9                      # 90% threshold

raw_rows <- nrow(raw_df)
clean_rows <- nrow(clean_df)
rows_removed <- raw_rows - clean_rows

cat("\nData Loss:\n")
cat(sprintf("  Raw rows:     %s\n", format(raw_rows, big.mark = ",")))
cat(sprintf("  Clean rows:   %s\n", format(clean_rows, big.mark = ",")))
cat(sprintf("  Rows removed: %s\n", format(rows_removed, big.mark = ",")))

# Check: data loss
if ("data_loss" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] data loss: %s\n", not_applicable[["data_loss"]]))
  cp2["skipped"] <- cp2["skipped"] + 1L
} else if (raw_rows == 0) {
  cat("[FAIL] data loss: raw_df is empty (0 rows) — loss rate undefined, cleaning untestable\n")
  cp2["failed"] <- cp2["failed"] + 1L
} else {
  loss_rate <- rows_removed / raw_rows
  if (loss_rate > max_data_loss) {
    cat(sprintf("[FAIL] data loss: %.1f%% (%s/%s) exceeds %.0f%% threshold\n", loss_rate * 100,
                format(rows_removed, big.mark = ","), format(raw_rows, big.mark = ","), max_data_loss * 100))
    cp2["failed"] <- cp2["failed"] + 1L
  } else if (loss_rate > 0.5) {
    cat(sprintf("[WARNING] data loss: %.1f%% (%s/%s) is high\n", loss_rate * 100,
                format(rows_removed, big.mark = ","), format(raw_rows, big.mark = ",")))
    cp2["warning"] <- cp2["warning"] + 1L
  } else {
    cat(sprintf("[PASS] data loss: %.1f%% (%s/%s) within %.0f%% tolerance\n", loss_rate * 100,
                format(rows_removed, big.mark = ","), format(raw_rows, big.mark = ","), max_data_loss * 100))
    cp2["passed"] <- cp2["passed"] + 1L
  }
}

# Check: suppression rate per key variable (measured on raw data)
cat("\nSuppression Rates (share of raw column values carrying the suppression sentinel):\n")
if ("suppression" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] suppression: %s\n", not_applicable[["suppression"]]))
  cp2["skipped"] <- cp2["skipped"] + 1L
} else if (is.null(key_variables) || length(key_variables) == 0) {
  cat("[NOT VERIFIED] suppression: key_variables is empty — no columns nominated for a suppression rate\n")
  cp2["not_verified"] <- cp2["not_verified"] + 1L
} else if (is.null(SUPPRESSION_CODE) || length(SUPPRESSION_CODE) == 0 || is.na(SUPPRESSION_CODE)) {
  cat("[NOT VERIFIED] suppression: SUPPRESSION_CODE is NULL/NA — the sentinel is unknown, so no rate can be computed. Declare not_applicable$suppression with a reason if this domain truly has no suppression code\n")
  cp2["not_verified"] <- cp2["not_verified"] + 1L
} else if (raw_rows == 0) {
  cat("[FAIL] suppression: raw_df is empty (0 rows) — suppression rate undefined\n")
  cp2["failed"] <- cp2["failed"] + 1L
} else {
  for (var in key_variables) {
    if (!var %in% names(raw_df)) {
      cat(sprintf("[FAIL] suppression '%s': column absent from raw_df — rate untestable\n", var))
      cp2["failed"] <- cp2["failed"] + 1L
      next
    }
    # REASONING: R coerces silently in the other direction from Polars — comparing a
    # character column to a numeric sentinel coerces the sentinel to a string and can
    # match (or miss) the wrong values without any warning. Guard comparability in
    # both directions so a non-comparable pair reports [NOT VERIFIED], not a rate.
    if (is.numeric(SUPPRESSION_CODE) != is.numeric(raw_df[[var]])) {
      cat(sprintf("[NOT VERIFIED] suppression '%s': column is %s, not comparable to sentinel %s — the comparison would coerce rather than raise\n",
                  var, class(raw_df[[var]])[1], as.character(SUPPRESSION_CODE)))
      cp2["not_verified"] <- cp2["not_verified"] + 1L
      next
    }
    suppressed <- sum(raw_df[[var]] == SUPPRESSION_CODE, na.rm = TRUE)
    supp_rate <- suppressed / raw_rows
    if (supp_rate > max_suppression) {
      cat(sprintf("[FAIL] suppression '%s': %.1f%% (n=%s/%s sentinel %s) exceeds %.0f%% threshold\n",
                  var, supp_rate * 100, format(suppressed, big.mark = ","),
                  format(raw_rows, big.mark = ","), as.character(SUPPRESSION_CODE), max_suppression * 100))
      cp2["failed"] <- cp2["failed"] + 1L
    } else if (supp_rate > 0.2) {
      cat(sprintf("[WARNING] suppression '%s': %.1f%% (n=%s/%s sentinel %s) is notable\n",
                  var, supp_rate * 100, format(suppressed, big.mark = ","),
                  format(raw_rows, big.mark = ","), as.character(SUPPRESSION_CODE)))
      cp2["warning"] <- cp2["warning"] + 1L
    } else {
      cat(sprintf("[PASS] suppression '%s': %.1f%% (n=%s/%s sentinel %s) below %.0f%% threshold\n",
                  var, supp_rate * 100, format(suppressed, big.mark = ","),
                  format(raw_rows, big.mark = ","), as.character(SUPPRESSION_CODE), max_suppression * 100))
      cp2["passed"] <- cp2["passed"] + 1L
    }
  }
}

# Check: coded missing values remaining in clean data, per key variable
cat("\nCoded Values Check (clean data):\n")
if ("coded_values" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] coded values: %s\n", not_applicable[["coded_values"]]))
  cp2["skipped"] <- cp2["skipped"] + 1L
} else if (is.null(key_variables) || length(key_variables) == 0) {
  cat("[NOT VERIFIED] coded values: key_variables is empty — no columns nominated for the scan\n")
  cp2["not_verified"] <- cp2["not_verified"] + 1L
} else if (is.null(CODED_MISSING_VALUES) || length(CODED_MISSING_VALUES) == 0) {
  # REASONING: sum(sapply(c(), ...)) errors on an empty vocabulary; guard length() first.
  cat("[NOT VERIFIED] coded values: CODED_MISSING_VALUES is empty — no vocabulary to scan for. Declare not_applicable$coded_values with a reason if this domain uses none\n")
  cp2["not_verified"] <- cp2["not_verified"] + 1L
} else {
  for (var in key_variables) {
    if (!var %in% names(clean_df)) {
      cat(sprintf("[FAIL] coded values '%s': column absent from clean_df — scan untestable\n", var))
      cp2["failed"] <- cp2["failed"] + 1L
      next
    }
    if (!is.numeric(clean_df[[var]])) {
      cat(sprintf("[NOT VERIFIED] coded values '%s': column is %s, not numeric — numeric sentinels (%s) not comparable\n",
                  var, class(clean_df[[var]])[1], paste(CODED_MISSING_VALUES, collapse = ", ")))
      cp2["not_verified"] <- cp2["not_verified"] + 1L
      next
    }
    coded <- 0L
    for (code in CODED_MISSING_VALUES) {
      coded <- coded + sum(clean_df[[var]] == code, na.rm = TRUE)
    }
    if (coded > 0) {
      cat(sprintf("[WARNING] coded values '%s': %s of %s values still match (%s)\n", var,
                  format(coded, big.mark = ","), format(nrow(clean_df), big.mark = ","),
                  paste(CODED_MISSING_VALUES, collapse = ", ")))
      cp2["warning"] <- cp2["warning"] + 1L
    } else {
      cat(sprintf("[PASS] coded values '%s': 0 of %s values match (%s)\n", var,
                  format(nrow(clean_df), big.mark = ","), paste(CODED_MISSING_VALUES, collapse = ", ")))
      cp2["passed"] <- cp2["passed"] + 1L
    }
  }
}

# Count line, then verdict derived from the counts
cp2_checks_run <- cp2[["passed"]] + cp2[["warning"]] + cp2[["failed"]]
if (cp2[["failed"]] > 0 || cp2[["not_verified"]] > 0 || cp2_checks_run == 0) {
  cp2_verdict <- "FAILED"
} else if (cp2[["warning"]] > 0) {
  cp2_verdict <- "PASSED WITH WARNINGS"
} else {
  cp2_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cp2[["passed"]], cp2[["warning"]], cp2[["failed"]], cp2[["not_verified"]], cp2[["skipped"]]))
cat(sprintf("CP2 VALIDATION: %s\n", cp2_verdict))
cat(strrep("=", 60), "\n")

if (cp2_verdict == "FAILED") {
  stop("CP2 FAILED - see details above")
}
```

### Usage Notes

Set these variables before the CP2 block:

**Python:**
```python
# Configure before CP2 block
# raw_df = <DataFrame before cleaning>
# clean_df = <DataFrame after cleaning>
key_variables = ["enrollment", "poverty_rate"]  # columns to check

# Domain configuration (from Plan's Domain Configuration section)
SUPPRESSION_CODE = -3                # From Plan domain config; None if the domain has no sentinel
CODED_MISSING_VALUES = [-1, -2, -3]  # From Plan domain config; empty list [] if none
SUPPRESSION_THRESHOLD = 0.5          # From Plan domain config; 50% default for education
# Education domain defaults: SUPPRESSION_CODE = -3, CODED_MISSING_VALUES = [-1, -2, -3], SUPPRESSION_THRESHOLD = 0.5

not_applicable = {}  # e.g. {"suppression": "CCD directory file carries no suppression code"}
```

**R:**
```r
# Configure before CP2 block
# raw_df <- <data frame before cleaning>
# clean_df <- <data frame after cleaning>
key_variables <- c("enrollment", "poverty_rate")  # columns to check

# Domain configuration (from Plan's Domain Configuration section)
SUPPRESSION_CODE <- -3                 # From Plan domain config; NULL if the domain has no sentinel
CODED_MISSING_VALUES <- c(-1, -2, -3)  # From Plan domain config; empty c() if none
SUPPRESSION_THRESHOLD <- 0.5           # From Plan domain config; 50% default for education
# Education domain defaults: SUPPRESSION_CODE = -3, CODED_MISSING_VALUES = c(-1, -2, -3), SUPPRESSION_THRESHOLD = 0.5

not_applicable <- list()  # e.g. list(suppression = "CCD directory file carries no suppression code")
```

**`not_applicable` keys recognized by CP2:**

| Key | Suppresses | Declare it when |
|-----|-----------|-----------------|
| `data_loss` | Row-attrition tolerance check | Cleaning is known to be a pure filter to a declared subset and the Plan documents the expected size |
| `suppression` | Per-column suppression rate | The domain publishes no suppression sentinel (`SUPPRESSION_CODE` legitimately `None`/`NULL`) |
| `coded_values` | Residual coded-value scan | The domain uses no coded missing values (`CODED_MISSING_VALUES` legitimately empty) |

**Metric definition (important):** the suppression rate is the share of *that column's* raw values equal to `SUPPRESSION_CODE`, denominator = rows in `raw_df`. It is **not** row attrition. When suppression is handled by nulling in place, attrition is 0 while the true column rate can be any value — the previous row-attrition formulation reported 0% for fully suppressed columns.

**Semantics reminders:**
- `SUPPRESSION_CODE = None` / `CODED_MISSING_VALUES = []` produce `[NOT VERIFIED]`, which makes the verdict `FAILED`. That is deliberate: a domain with no sentinel must say so via `not_applicable` so the log records the decision and its reason.
- `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`**.
- `NUMERIC_DTYPES` in this block is the same list used by the substantiveness data check — keep them in sync so no integer width is exempted in one place and not the other.
- **Dtype comparability is a precondition, not a detail.** Both the suppression and coded-values checks refuse to compare a column to a sentinel of the other kind: Polars returns all-False for a string-column-vs-number compare (yielding `[PASS] 0.0%` over a fully suppressed column), and R coerces and matches the wrong values. Either way the pair reports `[NOT VERIFIED]` naming the dtype, which fails the checkpoint. If a domain genuinely encodes suppression as a string, set `SUPPRESSION_CODE` to that string — the guard tests comparability, not numeric-ness.

---

## CP3: Post-Transformation Validation

**When:** After joins, aggregations, or derived variable creation
**Purpose:** Verify transformations preserved data integrity

### Code Template

```python
# --- CP3 Validation: Post-Transformation ---
# INTENT: Verify the transformation preserved data integrity — row-count
# relationship, extreme row loss, newly introduced nulls, and column preservation.
# REASONING: expected_relationship is an enumerated Plan commitment. An
# unrecognized value (typo, None, or a relationship the template does not model)
# is a configuration defect and fails loudly rather than falling through to PASS.
# ASSUMES: input_df is pre-transform state, output_df is post-transform state;
# operation / expected_relationship / preserved_cols / not_applicable are
# configured above from the Plan.
print("\n" + "=" * 60)
print(f"CP3 VALIDATION: POST-TRANSFORMATION ({operation})")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cp3 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}
max_row_loss = 0.9  # 90% threshold

input_rows = len(input_df)
output_rows = len(output_df)
row_change = output_rows - input_rows

print("\nRow Count Change:")
print(f"  Input rows:  {input_rows:,}")
print(f"  Output rows: {output_rows:,}")
print(f"  Change:      {row_change:+,}")
print(f"  Expected:    {expected_relationship!r}")

# Check: row-count relationship — one explicit branch per documented value
if "row_relationship" in not_applicable:
    print(f"[SKIPPED] row relationship: {not_applicable['row_relationship']}")
    cp3["skipped"] += 1
elif expected_relationship not in ("same", "fewer", "more", "aggregated"):
    print(f"[FAIL] row relationship: unrecognized expected_relationship {expected_relationship!r} — legal values are 'same', 'fewer', 'more', 'aggregated'")
    cp3["failed"] += 1
elif expected_relationship == "same":
    if row_change == 0:
        print(f"[PASS] row relationship 'same': {input_rows:,} -> {output_rows:,} (change {row_change:+,})")
        cp3["passed"] += 1
    else:
        print(f"[WARNING] row relationship 'same': expected no change but {input_rows:,} -> {output_rows:,} (change {row_change:+,})")
        cp3["warning"] += 1
elif expected_relationship == "fewer":
    if row_change < 0:
        print(f"[PASS] row relationship 'fewer': {input_rows:,} -> {output_rows:,} (change {row_change:+,})")
        cp3["passed"] += 1
    else:
        print(f"[WARNING] row relationship 'fewer': expected a decrease but {input_rows:,} -> {output_rows:,} (change {row_change:+,})")
        cp3["warning"] += 1
elif expected_relationship == "more":
    if row_change > 0:
        print(f"[PASS] row relationship 'more': {input_rows:,} -> {output_rows:,} (change {row_change:+,})")
        cp3["passed"] += 1
    else:
        print(f"[WARNING] row relationship 'more': expected an increase but {input_rows:,} -> {output_rows:,} (change {row_change:+,})")
        cp3["warning"] += 1
else:
    # expected_relationship == "aggregated"
    # ASSUMES: aggregation collapses groups, so the output must be strictly smaller.
    if row_change < 0:
        print(f"[PASS] row relationship 'aggregated': {input_rows:,} -> {output_rows:,} groups (change {row_change:+,})")
        cp3["passed"] += 1
    elif row_change == 0:
        print(f"[WARNING] row relationship 'aggregated': {input_rows:,} -> {output_rows:,} — every input row formed its own group, so no aggregation occurred")
        cp3["warning"] += 1
    else:
        print(f"[FAIL] row relationship 'aggregated': {input_rows:,} -> {output_rows:,} (change {row_change:+,}) — aggregation cannot increase row count")
        cp3["failed"] += 1

# Check: extreme row loss
if "row_loss" in not_applicable:
    print(f"[SKIPPED] row loss: {not_applicable['row_loss']}")
    cp3["skipped"] += 1
elif input_rows == 0:
    print("[FAIL] row loss: input_df is empty (0 rows) — loss rate undefined, transformation untestable")
    cp3["failed"] += 1
else:
    loss_rate = 1 - (output_rows / input_rows)
    if loss_rate > max_row_loss:
        print(f"[FAIL] row loss: {loss_rate:.1%} ({input_rows - output_rows:,}/{input_rows:,}) exceeds {max_row_loss:.0%} threshold")
        cp3["failed"] += 1
    elif loss_rate > 0.5:
        print(f"[WARNING] row loss: {loss_rate:.1%} ({input_rows - output_rows:,}/{input_rows:,}) is high")
        cp3["warning"] += 1
    else:
        print(f"[PASS] row loss: {loss_rate:.1%} ({input_rows - output_rows:,}/{input_rows:,}) within {max_row_loss:.0%} tolerance")
        cp3["passed"] += 1

# Check: new nulls introduced across columns common to both frames
print("\nNew Null Values:")
common_cols = sorted(set(input_df.columns) & set(output_df.columns))
if "new_nulls" in not_applicable:
    print(f"[SKIPPED] new nulls: {not_applicable['new_nulls']}")
    cp3["skipped"] += 1
elif len(common_cols) == 0:
    print(f"[NOT VERIFIED] new nulls: input and output share no columns (input {len(input_df.columns)}, output {len(output_df.columns)}) — null deltas not computable")
    cp3["not_verified"] += 1
else:
    new_null_detail = []
    for col in common_cols:
        delta = output_df[col].null_count() - input_df[col].null_count()
        if delta > 0:
            new_null_detail.append(f"{col}: +{delta:,}")
    if len(new_null_detail) > 0:
        print(f"[WARNING] new nulls: {len(new_null_detail)} of {len(common_cols)} common columns gained nulls ({'; '.join(new_null_detail)})")
        cp3["warning"] += 1
    else:
        print(f"[PASS] new nulls: 0 of {len(common_cols)} common columns gained nulls")
        cp3["passed"] += 1

# Check: preserved columns
if "preserved_columns" in not_applicable:
    print(f"[SKIPPED] preserved columns: {not_applicable['preserved_columns']}")
    cp3["skipped"] += 1
elif preserved_cols is None or len(preserved_cols) == 0:
    print("[NOT VERIFIED] preserved columns: preserved_cols is empty — the Plan named no columns that must survive")
    cp3["not_verified"] += 1
else:
    missing = [c for c in preserved_cols if c not in output_df.columns]
    if len(missing) > 0:
        print(f"[FAIL] preserved columns: {len(missing)} of {len(preserved_cols)} absent from output: {missing}")
        cp3["failed"] += 1
    else:
        print(f"[PASS] preserved columns: all {len(preserved_cols)} present ({', '.join(preserved_cols)})")
        cp3["passed"] += 1

# Count line, then verdict derived from the counts
cp3_checks_run = cp3["passed"] + cp3["warning"] + cp3["failed"]
if cp3["failed"] > 0 or cp3["not_verified"] > 0 or cp3_checks_run == 0:
    cp3_verdict = "FAILED"
elif cp3["warning"] > 0:
    cp3_verdict = "PASSED WITH WARNINGS"
else:
    cp3_verdict = "PASSED"

print(f"\nChecks: {cp3['passed']} passed, {cp3['warning']} warnings, {cp3['failed']} failed, {cp3['not_verified']} not verified, {cp3['skipped']} skipped")
print(f"CP3 VALIDATION: {cp3_verdict}")
print("=" * 60)

if cp3_verdict == "FAILED":
    raise ValueError("CP3 FAILED - see details above")
```

### R Code Template

```r
# --- CP3 Validation: Post-Transformation ---
# INTENT: Verify the transformation preserved data integrity — row-count
# relationship, extreme row loss, newly introduced NAs, and column preservation.
# REASONING: An unrecognized expected_relationship (typo, NULL, or an unmodelled
# relationship) is a configuration defect and fails loudly.
# ASSUMES: input_df is pre-transform state, output_df is post-transform state.
cat("\n")
cat(strrep("=", 60), "\n")
cat(sprintf("CP3 VALIDATION: POST-TRANSFORMATION (%s)\n", operation))
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cp3 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)
max_row_loss <- 0.9  # 90% threshold

input_rows <- nrow(input_df)
output_rows <- nrow(output_df)
row_change <- output_rows - input_rows

cat("\nRow Count Change:\n")
cat(sprintf("  Input rows:  %s\n", format(input_rows, big.mark = ",")))
cat(sprintf("  Output rows: %s\n", format(output_rows, big.mark = ",")))
cat(sprintf("  Change:      %+d\n", row_change))
cat(sprintf("  Expected:    %s\n", if (is.null(expected_relationship)) "NULL" else as.character(expected_relationship)))

# Check: row-count relationship — one explicit branch per documented value
# REASONING: is.null()/length() are tested before any comparison so a NULL config
# cannot reach if() and raise "missing value where TRUE/FALSE needed".
rel_ok <- !is.null(expected_relationship) && length(expected_relationship) == 1 &&
          is.character(expected_relationship) && !is.na(expected_relationship) &&
          expected_relationship %in% c("same", "fewer", "more", "aggregated")
if ("row_relationship" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row relationship: %s\n", not_applicable[["row_relationship"]]))
  cp3["skipped"] <- cp3["skipped"] + 1L
} else if (!rel_ok) {
  cat(sprintf("[FAIL] row relationship: unrecognized expected_relationship '%s' — legal values are 'same', 'fewer', 'more', 'aggregated'\n",
              if (is.null(expected_relationship)) "NULL" else paste(as.character(expected_relationship), collapse = ",")))
  cp3["failed"] <- cp3["failed"] + 1L
} else if (expected_relationship == "same") {
  if (row_change == 0) {
    cat(sprintf("[PASS] row relationship 'same': %s -> %s (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["passed"] <- cp3["passed"] + 1L
  } else {
    cat(sprintf("[WARNING] row relationship 'same': expected no change but %s -> %s (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["warning"] <- cp3["warning"] + 1L
  }
} else if (expected_relationship == "fewer") {
  if (row_change < 0) {
    cat(sprintf("[PASS] row relationship 'fewer': %s -> %s (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["passed"] <- cp3["passed"] + 1L
  } else {
    cat(sprintf("[WARNING] row relationship 'fewer': expected a decrease but %s -> %s (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["warning"] <- cp3["warning"] + 1L
  }
} else if (expected_relationship == "more") {
  if (row_change > 0) {
    cat(sprintf("[PASS] row relationship 'more': %s -> %s (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["passed"] <- cp3["passed"] + 1L
  } else {
    cat(sprintf("[WARNING] row relationship 'more': expected an increase but %s -> %s (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["warning"] <- cp3["warning"] + 1L
  }
} else {
  # expected_relationship == "aggregated"
  if (row_change < 0) {
    cat(sprintf("[PASS] row relationship 'aggregated': %s -> %s groups (change %+d)\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["passed"] <- cp3["passed"] + 1L
  } else if (row_change == 0) {
    cat(sprintf("[WARNING] row relationship 'aggregated': %s -> %s — every input row formed its own group, so no aggregation occurred\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ",")))
    cp3["warning"] <- cp3["warning"] + 1L
  } else {
    cat(sprintf("[FAIL] row relationship 'aggregated': %s -> %s (change %+d) — aggregation cannot increase row count\n",
                format(input_rows, big.mark = ","), format(output_rows, big.mark = ","), row_change))
    cp3["failed"] <- cp3["failed"] + 1L
  }
}

# Check: extreme row loss
if ("row_loss" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row loss: %s\n", not_applicable[["row_loss"]]))
  cp3["skipped"] <- cp3["skipped"] + 1L
} else if (input_rows == 0) {
  cat("[FAIL] row loss: input_df is empty (0 rows) — loss rate undefined, transformation untestable\n")
  cp3["failed"] <- cp3["failed"] + 1L
} else {
  loss_rate <- 1 - (output_rows / input_rows)
  if (loss_rate > max_row_loss) {
    cat(sprintf("[FAIL] row loss: %.1f%% (%s/%s) exceeds %.0f%% threshold\n", loss_rate * 100,
                format(input_rows - output_rows, big.mark = ","), format(input_rows, big.mark = ","), max_row_loss * 100))
    cp3["failed"] <- cp3["failed"] + 1L
  } else if (loss_rate > 0.5) {
    cat(sprintf("[WARNING] row loss: %.1f%% (%s/%s) is high\n", loss_rate * 100,
                format(input_rows - output_rows, big.mark = ","), format(input_rows, big.mark = ",")))
    cp3["warning"] <- cp3["warning"] + 1L
  } else {
    cat(sprintf("[PASS] row loss: %.1f%% (%s/%s) within %.0f%% tolerance\n", loss_rate * 100,
                format(input_rows - output_rows, big.mark = ","), format(input_rows, big.mark = ","), max_row_loss * 100))
    cp3["passed"] <- cp3["passed"] + 1L
  }
}

# Check: new NAs introduced across columns common to both frames
cat("\nNew NA Values:\n")
common_cols <- sort(intersect(names(input_df), names(output_df)))
if ("new_nulls" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] new NAs: %s\n", not_applicable[["new_nulls"]]))
  cp3["skipped"] <- cp3["skipped"] + 1L
} else if (length(common_cols) == 0) {
  cat(sprintf("[NOT VERIFIED] new NAs: input and output share no columns (input %d, output %d) — NA deltas not computable\n",
              ncol(input_df), ncol(output_df)))
  cp3["not_verified"] <- cp3["not_verified"] + 1L
} else {
  new_null_detail <- character(0)
  for (col in common_cols) {
    delta <- sum(is.na(output_df[[col]])) - sum(is.na(input_df[[col]]))
    if (delta > 0) {
      new_null_detail <- c(new_null_detail, sprintf("%s: +%s", col, format(delta, big.mark = ",")))
    }
  }
  if (length(new_null_detail) > 0) {
    cat(sprintf("[WARNING] new NAs: %d of %d common columns gained NAs (%s)\n",
                length(new_null_detail), length(common_cols), paste(new_null_detail, collapse = "; ")))
    cp3["warning"] <- cp3["warning"] + 1L
  } else {
    cat(sprintf("[PASS] new NAs: 0 of %d common columns gained NAs\n", length(common_cols)))
    cp3["passed"] <- cp3["passed"] + 1L
  }
}

# Check: preserved columns
if ("preserved_columns" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] preserved columns: %s\n", not_applicable[["preserved_columns"]]))
  cp3["skipped"] <- cp3["skipped"] + 1L
} else if (is.null(preserved_cols) || length(preserved_cols) == 0) {
  cat("[NOT VERIFIED] preserved columns: preserved_cols is empty — the Plan named no columns that must survive\n")
  cp3["not_verified"] <- cp3["not_verified"] + 1L
} else {
  missing <- setdiff(preserved_cols, names(output_df))
  if (length(missing) > 0) {
    cat(sprintf("[FAIL] preserved columns: %d of %d absent from output: %s\n",
                length(missing), length(preserved_cols), paste(missing, collapse = ", ")))
    cp3["failed"] <- cp3["failed"] + 1L
  } else {
    cat(sprintf("[PASS] preserved columns: all %d present (%s)\n",
                length(preserved_cols), paste(preserved_cols, collapse = ", ")))
    cp3["passed"] <- cp3["passed"] + 1L
  }
}

# Count line, then verdict derived from the counts
cp3_checks_run <- cp3[["passed"]] + cp3[["warning"]] + cp3[["failed"]]
if (cp3[["failed"]] > 0 || cp3[["not_verified"]] > 0 || cp3_checks_run == 0) {
  cp3_verdict <- "FAILED"
} else if (cp3[["warning"]] > 0) {
  cp3_verdict <- "PASSED WITH WARNINGS"
} else {
  cp3_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cp3[["passed"]], cp3[["warning"]], cp3[["failed"]], cp3[["not_verified"]], cp3[["skipped"]]))
cat(sprintf("CP3 VALIDATION: %s\n", cp3_verdict))
cat(strrep("=", 60), "\n")

if (cp3_verdict == "FAILED") {
  stop("CP3 FAILED - see details above")
}
```

### Usage Notes

Set these variables before the CP3 block:

**Python:**
```python
# Configure before CP3 block
operation = "Join CCD + MEPS"          # description of the transformation
expected_relationship = "same"          # "same" | "fewer" | "more" | "aggregated" — no other value is legal
preserved_cols = ["ncessch", "year"]    # columns that must survive
not_applicable = {}                     # e.g. {"new_nulls": "output is a fresh aggregate with no shared columns"}
# input_df = <DataFrame before transformation>
# output_df = <DataFrame after transformation>
```

**R:**
```r
# Configure before CP3 block
operation <- "Join CCD + MEPS"          # description of the transformation
expected_relationship <- "same"         # "same" | "fewer" | "more" | "aggregated" — no other value is legal
preserved_cols <- c("ncessch", "year")  # columns that must survive
not_applicable <- list()                # e.g. list(new_nulls = "output is a fresh aggregate with no shared columns")
# input_df <- <data frame before transformation>
# output_df <- <data frame after transformation>
```

**`not_applicable` keys recognized by CP3:**

| Key | Suppresses | Declare it when |
|-----|-----------|-----------------|
| `row_relationship` | Row-count relationship branch | The transformation's row behavior is genuinely unpredictable and the Plan says so |
| `row_loss` | Extreme row-loss threshold | The transformation is an intentional deep filter with a Plan-documented target size |
| `new_nulls` | New-null delta across common columns | The output shares no columns with the input by design (e.g. a pure aggregate) |
| `preserved_columns` | Preserved-column presence | The transformation intentionally replaces the whole schema |

**Semantics reminders:**
- The four relationship values are exhaustive. Anything else — including `None`/`NULL` and a typo such as `"smae"` — is `[FAIL] unrecognized expected_relationship`, never a silent PASS. `"aggregated"` has its own branch: a strict decrease passes, no change warns, an increase fails.
- `[NOT VERIFIED]` (empty `preserved_cols`, no common columns) makes the verdict `FAILED`. Declare the check `not_applicable` with a reason instead of leaving the config empty.
- `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`**.

---

## CP4: Post-Analysis & Visualization Validation

**When:** Inside each Stage 8 analysis or visualization script, immediately after the results and figures are produced
**Purpose:** Verify the analysis outputs are valid, the analysis frame has no critical nulls, every promised figure exists and is non-empty, and the script read the correct input
**Classification:** `checkpoint:auto` — halts on `FAILED`
**Owner:** research-executor (embedded in the script)

> **CP4 is not a pre-delivery checkpoint.** Report sections, Plan consistency, Research Outcomes, and Hypotheses are verified at Stage 12 by data-verifier — see § Pre-Output Verification (Stage 12) below. Those are not CP4 sub-checks and are never reported as `CP4 ...` in an execution log.

### CP4 Sub-Checks

| Sub-check | What It Validates | FAIL Condition | WARNING Condition |
|-----------|-------------------|----------------|-------------------|
| **CP4.1: Analysis Outputs Valid** | The results object exists; estimates are finite; the convergence flag is `True` when the estimator reports one; n meets the Plan's minimum; estimate signs match any pre-registered direction | Missing/empty results, non-finite estimate, `converged` false, n below the Plan minimum, sign opposite to a pre-registered direction | n within 10% of the Plan minimum |
| **CP4.2: Critical Nulls** | No nulls in the analysis frame's outcome and key columns | Any null in a critical column; a critical column absent from the frame | N/A |
| **CP4.3: Figures** | Every figure the task promised exists and is non-empty; the executor has visually inspected each one via Read | Missing figure file; zero-byte file | File under 10 KB (possibly blank canvas) |
| **CP4.4: Correct Data Source** | The script loads the Plan's named input (normally `data/processed/`), not raw data | A raw-data literal appears on an executable line outside the CP4 config assignments and the CP4 block itself | N/A |

### Code Template

```python
import math
import numbers
import re
from pathlib import Path

# --- CP4 Validation: Post-Analysis & Visualization (Stage 8) ---
# INTENT: Confirm the analysis this script just produced is valid, complete, and
# built from the right input, before its results reach the notebook or report.
# REASONING: Each sub-check emits exactly one outcome token per item and counts
# itself; the verdict is derived from the counters, so a sub-check that could not
# run ([NOT VERIFIED]) fails the checkpoint instead of inflating a PASS.
# ASSUMES: analysis_results / analysis_df / critical_columns / required_figures /
# figures_dir / min_n / expected_signs / script_source_path / expected_input_dir /
# forbidden_input_dir / not_applicable are configured above from the Plan.
print("\n" + "=" * 60)
print("CP4 VALIDATION: POST-ANALYSIS & VISUALIZATION")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cp4 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# --- CP4.1: Analysis outputs valid ---
print("\nCP4.1 Analysis Outputs:")

# Check: results object exists
if "analysis_results" in not_applicable:
    print(f"[SKIPPED] analysis results: {not_applicable['analysis_results']}")
    cp4["skipped"] += 1
elif analysis_results is None or len(analysis_results) == 0:
    print("[NOT VERIFIED] analysis results: analysis_results is None or empty — nothing produced to validate")
    cp4["not_verified"] += 1
else:
    print(f"[PASS] analysis results: object present with {len(analysis_results)} entries ({', '.join(sorted(analysis_results.keys()))})")
    cp4["passed"] += 1

# Check: estimates finite
estimates = analysis_results.get("estimates") if analysis_results is not None else None
if "estimates_finite" in not_applicable:
    print(f"[SKIPPED] estimates finite: {not_applicable['estimates_finite']}")
    cp4["skipped"] += 1
elif estimates is None or len(estimates) == 0:
    print("[NOT VERIFIED] estimates finite: analysis_results['estimates'] is missing or empty — no coefficients to inspect")
    cp4["not_verified"] += 1
else:
    # REASONING: `isinstance(v, (int, float))` rejects every numpy scalar an
    # estimator actually returns (np.int64, np.float64), turning a valid estimate
    # into a false [FAIL]; and it accepts `True`, because bool subclasses int.
    # numbers.Real covers the numpy scalars (they register as Real) while the
    # explicit bool exclusion keeps a flag from passing as an estimate. The
    # float() conversion is inside try because a Real-registered type may still
    # refuse conversion (e.g. a Decimal NaN or a 0-d object array).
    bad = []
    for k, v in estimates.items():
        try:
            is_finite_number = (isinstance(v, numbers.Real)
                                and not isinstance(v, bool)
                                and math.isfinite(float(v)))
        except (TypeError, ValueError, OverflowError):
            is_finite_number = False
        if not is_finite_number:
            bad.append(f"{k}={v!r}")
    if len(bad) > 0:
        print(f"[FAIL] estimates finite: {len(bad)} of {len(estimates)} non-finite ({'; '.join(bad)})")
        cp4["failed"] += 1
    else:
        print(f"[PASS] estimates finite: all {len(estimates)} finite ({'; '.join(f'{k}={float(v):.6g}' for k, v in estimates.items())})")
        cp4["passed"] += 1

# Check: convergence flag, when the estimator reports one
# REASONING: estimators report numpy booleans, and `np.bool_` is neither a `bool`
# instance nor ever `is True` / `is False`, so `isinstance(v, bool)` turned a real
# convergence flag into a false [NOT VERIFIED] (and hence FAILED). Matching the type
# name accepts numpy's boolean scalar (`bool_` on numpy 1.x, `bool` on 2.x) without
# importing numpy here; int, str, and None still fall through to [NOT VERIFIED], and
# the bool() coercion below keeps a numpy False on the [FAIL] branch.
if "convergence" in not_applicable:
    print(f"[SKIPPED] convergence: {not_applicable['convergence']}")
    cp4["skipped"] += 1
elif analysis_results is None or "converged" not in analysis_results or type(analysis_results.get("converged")).__name__ not in ("bool", "bool_"):
    print("[NOT VERIFIED] convergence: analysis_results['converged'] is absent or not a boolean — declare not_applicable['convergence'] for closed-form estimators that report no flag")
    cp4["not_verified"] += 1
elif bool(analysis_results["converged"]) is False:
    print("[FAIL] convergence: estimator reported converged=False — coefficients are not trustworthy")
    cp4["failed"] += 1
else:
    print("[PASS] convergence: estimator reported converged=True")
    cp4["passed"] += 1

# Check: sample size against the Plan's minimum
n_obs = analysis_results.get("n") if analysis_results is not None else None
if "sample_size" in not_applicable:
    print(f"[SKIPPED] sample size: {not_applicable['sample_size']}")
    cp4["skipped"] += 1
elif not isinstance(n_obs, numbers.Real) or isinstance(n_obs, bool):
    # Same numeric predicate as the finiteness check: np.int64 is a Real, `True` is not an n.
    print(f"[NOT VERIFIED] sample size: analysis_results['n'] is {n_obs!r} — estimation n not reported as a real number")
    cp4["not_verified"] += 1
elif not isinstance(min_n, numbers.Real) or isinstance(min_n, bool) or min_n <= 0:
    print(f"[NOT VERIFIED] sample size: min_n is {min_n!r} — the Plan set no positive minimum to compare against")
    cp4["not_verified"] += 1
elif n_obs < min_n:
    print(f"[FAIL] sample size: n={float(n_obs):,.0f} is below the Plan minimum {float(min_n):,.0f}")
    cp4["failed"] += 1
elif n_obs < min_n * 1.1:
    print(f"[WARNING] sample size: n={float(n_obs):,.0f} is within 10% of the Plan minimum {float(min_n):,.0f}")
    cp4["warning"] += 1
else:
    print(f"[PASS] sample size: n={float(n_obs):,.0f} meets the Plan minimum {float(min_n):,.0f}")
    cp4["passed"] += 1

# Check: pre-registered estimate signs
# ASSUMES: expected_signs maps estimate name -> -1 | 0 | +1 and is populated ONLY
# when the Plan pre-registers a direction. An empty mapping is itself the
# declaration that no direction was pre-registered, and prints as [SKIPPED].
if "expected_signs" in not_applicable:
    print(f"[SKIPPED] expected signs: {not_applicable['expected_signs']}")
    cp4["skipped"] += 1
elif expected_signs is None or len(expected_signs) == 0:
    print("[SKIPPED] expected signs: expected_signs is empty — the Plan pre-registers no directional hypothesis")
    cp4["skipped"] += 1
elif estimates is None or len(estimates) == 0:
    print("[NOT VERIFIED] expected signs: no estimates available to compare against the pre-registered directions")
    cp4["not_verified"] += 1
else:
    sign_absent = [k for k in expected_signs if k not in estimates]
    if len(sign_absent) > 0:
        print(f"[NOT VERIFIED] expected signs: {sign_absent} pre-registered but absent from the estimates")
        cp4["not_verified"] += 1
    else:
        wrong = []
        for k, want in expected_signs.items():
            got = estimates[k]
            observed = 0 if got == 0 else (1 if got > 0 else -1)
            if observed != want:
                wrong.append(f"{k}: expected {want:+d}, observed {observed:+d} ({got:.6g})")
        if len(wrong) > 0:
            print(f"[FAIL] expected signs: {len(wrong)} of {len(expected_signs)} contradict the pre-registered direction ({'; '.join(wrong)})")
            cp4["failed"] += 1
        else:
            print(f"[PASS] expected signs: all {len(expected_signs)} match the pre-registered direction ({'; '.join(f'{k}={estimates[k]:.6g}' for k in expected_signs)})")
            cp4["passed"] += 1

# --- CP4.2: Critical nulls in the analysis frame ---
print("\nCP4.2 Critical Column Nulls:")
if "critical_nulls" in not_applicable:
    print(f"[SKIPPED] critical nulls: {not_applicable['critical_nulls']}")
    cp4["skipped"] += 1
elif critical_columns is None or len(critical_columns) == 0:
    print("[NOT VERIFIED] critical nulls: critical_columns is empty — the Plan named no column that must be complete")
    cp4["not_verified"] += 1
else:
    for col in critical_columns:
        if col not in analysis_df.columns:
            print(f"[FAIL] critical nulls '{col}': column absent from the analysis frame — completeness untestable")
            cp4["failed"] += 1
            continue
        null_count = analysis_df[col].null_count()
        if null_count > 0:
            print(f"[FAIL] critical nulls '{col}': {null_count:,} of {len(analysis_df):,} rows null")
            cp4["failed"] += 1
        else:
            print(f"[PASS] critical nulls '{col}': 0 of {len(analysis_df):,} rows null")
            cp4["passed"] += 1

# --- CP4.3: Figures exist and are non-empty ---
print("\nCP4.3 Required Figures:")
if "figures" in not_applicable:
    print(f"[SKIPPED] figures: {not_applicable['figures']}")
    cp4["skipped"] += 1
elif required_figures is None or len(required_figures) == 0:
    print("[NOT VERIFIED] figures: required_figures is empty — the task promised no figure, or the list was never populated")
    cp4["not_verified"] += 1
else:
    for fig in required_figures:
        fig_path = Path(figures_dir) / fig
        if not fig_path.exists():
            print(f"[FAIL] figure '{fig}': not found at {fig_path}")
            cp4["failed"] += 1
            continue
        size_kb = fig_path.stat().st_size / 1024
        if size_kb == 0:
            print(f"[FAIL] figure '{fig}': 0 bytes at {fig_path}")
            cp4["failed"] += 1
        elif size_kb < 10:
            print(f"[WARNING] figure '{fig}': {size_kb:.1f} KB — under the 10 KB floor, possibly a blank canvas")
            cp4["warning"] += 1
        else:
            print(f"[PASS] figure '{fig}': {size_kb:.1f} KB at {fig_path}")
            cp4["passed"] += 1
    # File existence is necessary, not sufficient — a 40 KB PNG can still be an
    # empty axis. The executor MUST open each figure with the Read tool and confirm
    # the rendered content matches the task before reporting CP4 upward.
    print("  Visual inspection required: open each figure above with Read and confirm the rendered content; report the inspection in the CP4 status.")

# --- CP4.4: Correct data source ---
print("\nCP4.4 Input Source:")
if "data_source" in not_applicable:
    print(f"[SKIPPED] data source: {not_applicable['data_source']}")
    cp4["skipped"] += 1
elif script_source_path is None or not Path(script_source_path).exists():
    print(f"[NOT VERIFIED] data source: script_source_path {script_source_path!r} does not exist — cannot inspect the input paths this script reads")
    cp4["not_verified"] += 1
else:
    # REASONING: three classes of line must be excluded before the scan, or the
    # check fails every correct Stage-8 script by reading its own configuration:
    #   1. comments — a commented-out or merely mentioned raw path is not a read;
    #   2. the CP4 config assignments — `forbidden_input_dir = "data/raw/"` is a
    #      literal occurrence of the forbidden path in EVERY correct script, and
    #      matching it was a guaranteed self-referential [FAIL];
    #   3. the CP4 block itself, which quotes both literals in its own messages.
    # What remains is the script's real I/O, which is what the check is about.
    src_lines = Path(script_source_path).read_text().split("\n")
    cp4_begin_re = re.compile(r"^\s*#\s*---\s*CP4 Validation")
    config_assign_re = re.compile(r"^\s*(expected_input_dir|forbidden_input_dir)\s*=")
    inside_cp4 = False
    scanned = []            # (1-based line number, comment-stripped text)
    for lineno, line in enumerate(src_lines, start=1):
        if cp4_begin_re.match(line):
            inside_cp4 = True
        if not inside_cp4 and config_assign_re.match(line) is None:
            scanned.append((lineno, re.sub(r"#.*$", "", line)))
        if inside_cp4 and "CP4 FAILED - see details above" in line:
            inside_cp4 = False   # the raise/stop line closes the checkpoint block
    forbidden_hits = [n for n, text in scanned if forbidden_input_dir in text]
    expected_hits = [n for n, text in scanned if expected_input_dir in text]
    if len(forbidden_hits) > 0:
        print(f"[FAIL] data source: line {forbidden_hits[0]} references '{forbidden_input_dir}' ({len(forbidden_hits)} line(s) of {len(scanned)} scanned) — Stage 8 must read the cleaned/transformed input, not raw data")
        cp4["failed"] += 1
    elif len(expected_hits) > 0:
        # NOTE: this line must not contain a `CP<n>` token — the log comparator
        # reads any line with `CP\d` plus PASS/FAIL as a checkpoint verdict.
        print(f"[PASS] data source: line {expected_hits[0]} reads '{expected_input_dir}' and no scanned line references '{forbidden_input_dir}' ({len(scanned)} lines scanned; comments, the checkpoint's own config assignments, and the checkpoint block are excluded)")
        cp4["passed"] += 1
    else:
        print(f"[NOT VERIFIED] data source: no scanned line references '{expected_input_dir}' or '{forbidden_input_dir}' ({len(scanned)} lines scanned) — the input path is composed from variables. Declare not_applicable['data_source'] naming the Plan's input if that is intended")
        cp4["not_verified"] += 1

# Count line, then verdict derived from the counts
cp4_checks_run = cp4["passed"] + cp4["warning"] + cp4["failed"]
if cp4["failed"] > 0 or cp4["not_verified"] > 0 or cp4_checks_run == 0:
    cp4_verdict = "FAILED"
elif cp4["warning"] > 0:
    cp4_verdict = "PASSED WITH WARNINGS"
else:
    cp4_verdict = "PASSED"

print(f"\nChecks: {cp4['passed']} passed, {cp4['warning']} warnings, {cp4['failed']} failed, {cp4['not_verified']} not verified, {cp4['skipped']} skipped")
print(f"CP4 VALIDATION: {cp4_verdict}")
print("=" * 60)

if cp4_verdict == "FAILED":
    raise ValueError("CP4 FAILED - see details above")
```

### R Code Template

```r
# --- CP4 Validation: Post-Analysis & Visualization (Stage 8) ---
# INTENT: Confirm the analysis this script just produced is valid, complete, and
# built from the right input.
# REASONING: Sub-check numbering matches the Python template exactly (CP4.1-CP4.4).
# ASSUMES: analysis_results is a named list, analysis_df the analysis frame.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CP4 VALIDATION: POST-ANALYSIS & VISUALIZATION\n")
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cp4 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# --- CP4.1: Analysis outputs valid ---
cat("\nCP4.1 Analysis Outputs:\n")

# Check: results object exists
if ("analysis_results" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] analysis results: %s\n", not_applicable[["analysis_results"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(analysis_results) || length(analysis_results) == 0) {
  cat("[NOT VERIFIED] analysis results: analysis_results is NULL or empty — nothing produced to validate\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else {
  cat(sprintf("[PASS] analysis results: object present with %d entries (%s)\n",
              length(analysis_results), paste(sort(names(analysis_results)), collapse = ", ")))
  cp4["passed"] <- cp4["passed"] + 1L
}

# Check: estimates finite
estimates <- if (!is.null(analysis_results)) analysis_results[["estimates"]] else NULL
if ("estimates_finite" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] estimates finite: %s\n", not_applicable[["estimates_finite"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(estimates) || length(estimates) == 0) {
  cat("[NOT VERIFIED] estimates finite: analysis_results[['estimates']] is missing or empty — no coefficients to inspect\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else {
  bad <- character(0)
  for (nm in names(estimates)) {
    v <- estimates[[nm]]
    if (is.null(v) || length(v) != 1 || !is.numeric(v) || is.na(v) || !is.finite(v)) {
      bad <- c(bad, sprintf("%s=%s", nm, paste(as.character(v), collapse = ",")))
    }
  }
  if (length(bad) > 0) {
    cat(sprintf("[FAIL] estimates finite: %d of %d non-finite (%s)\n",
                length(bad), length(estimates), paste(bad, collapse = "; ")))
    cp4["failed"] <- cp4["failed"] + 1L
  } else {
    shown <- character(0)
    for (nm in names(estimates)) shown <- c(shown, sprintf("%s=%.6g", nm, estimates[[nm]]))
    cat(sprintf("[PASS] estimates finite: all %d finite (%s)\n", length(estimates), paste(shown, collapse = "; ")))
    cp4["passed"] <- cp4["passed"] + 1L
  }
}

# Check: convergence flag, when the estimator reports one
conv <- if (!is.null(analysis_results)) analysis_results[["converged"]] else NULL
if ("convergence" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] convergence: %s\n", not_applicable[["convergence"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(conv) || length(conv) != 1 || !is.logical(conv) || is.na(conv)) {
  cat("[NOT VERIFIED] convergence: analysis_results[['converged']] is absent or not a single TRUE/FALSE — declare not_applicable$convergence for closed-form estimators\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else if (isFALSE(conv)) {
  cat("[FAIL] convergence: estimator reported converged=FALSE — coefficients are not trustworthy\n")
  cp4["failed"] <- cp4["failed"] + 1L
} else {
  cat("[PASS] convergence: estimator reported converged=TRUE\n")
  cp4["passed"] <- cp4["passed"] + 1L
}

# Check: sample size against the Plan's minimum
n_obs <- if (!is.null(analysis_results)) analysis_results[["n"]] else NULL
if ("sample_size" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] sample size: %s\n", not_applicable[["sample_size"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(n_obs) || length(n_obs) != 1 || !is.numeric(n_obs) || is.na(n_obs)) {
  cat("[NOT VERIFIED] sample size: analysis_results[['n']] is absent or not numeric — estimation n not reported\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else if (is.null(min_n) || length(min_n) != 1 || !is.numeric(min_n) || is.na(min_n) || min_n <= 0) {
  cat("[NOT VERIFIED] sample size: min_n is absent or not a positive Plan minimum\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else if (n_obs < min_n) {
  cat(sprintf("[FAIL] sample size: n=%s is below the Plan minimum %s\n",
              format(n_obs, big.mark = ","), format(min_n, big.mark = ",")))
  cp4["failed"] <- cp4["failed"] + 1L
} else if (n_obs < min_n * 1.1) {
  cat(sprintf("[WARNING] sample size: n=%s is within 10%% of the Plan minimum %s\n",
              format(n_obs, big.mark = ","), format(min_n, big.mark = ",")))
  cp4["warning"] <- cp4["warning"] + 1L
} else {
  cat(sprintf("[PASS] sample size: n=%s meets the Plan minimum %s\n",
              format(n_obs, big.mark = ","), format(min_n, big.mark = ",")))
  cp4["passed"] <- cp4["passed"] + 1L
}

# Check: pre-registered estimate signs
if ("expected_signs" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] expected signs: %s\n", not_applicable[["expected_signs"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(expected_signs) || length(expected_signs) == 0) {
  cat("[SKIPPED] expected signs: expected_signs is empty — the Plan pre-registers no directional hypothesis\n")
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(estimates) || length(estimates) == 0) {
  cat("[NOT VERIFIED] expected signs: no estimates available to compare against the pre-registered directions\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else {
  sign_absent <- setdiff(names(expected_signs), names(estimates))
  if (length(sign_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] expected signs: %s pre-registered but absent from the estimates\n",
                paste(sign_absent, collapse = ", ")))
    cp4["not_verified"] <- cp4["not_verified"] + 1L
  } else {
    wrong <- character(0)
    for (nm in names(expected_signs)) {
      got <- estimates[[nm]]
      observed <- if (got == 0) 0L else if (got > 0) 1L else -1L
      if (observed != expected_signs[[nm]]) {
        wrong <- c(wrong, sprintf("%s: expected %+d, observed %+d (%.6g)", nm, expected_signs[[nm]], observed, got))
      }
    }
    if (length(wrong) > 0) {
      cat(sprintf("[FAIL] expected signs: %d of %d contradict the pre-registered direction (%s)\n",
                  length(wrong), length(expected_signs), paste(wrong, collapse = "; ")))
      cp4["failed"] <- cp4["failed"] + 1L
    } else {
      cat(sprintf("[PASS] expected signs: all %d match the pre-registered direction\n", length(expected_signs)))
      cp4["passed"] <- cp4["passed"] + 1L
    }
  }
}

# --- CP4.2: Critical nulls in the analysis frame ---
cat("\nCP4.2 Critical Column NAs:\n")
if ("critical_nulls" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] critical NAs: %s\n", not_applicable[["critical_nulls"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(critical_columns) || length(critical_columns) == 0) {
  cat("[NOT VERIFIED] critical NAs: critical_columns is empty — the Plan named no column that must be complete\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else {
  for (col in critical_columns) {
    if (!col %in% names(analysis_df)) {
      cat(sprintf("[FAIL] critical NAs '%s': column absent from the analysis frame — completeness untestable\n", col))
      cp4["failed"] <- cp4["failed"] + 1L
      next
    }
    null_count <- sum(is.na(analysis_df[[col]]))
    if (null_count > 0) {
      cat(sprintf("[FAIL] critical NAs '%s': %s of %s rows NA\n", col,
                  format(null_count, big.mark = ","), format(nrow(analysis_df), big.mark = ",")))
      cp4["failed"] <- cp4["failed"] + 1L
    } else {
      cat(sprintf("[PASS] critical NAs '%s': 0 of %s rows NA\n", col, format(nrow(analysis_df), big.mark = ",")))
      cp4["passed"] <- cp4["passed"] + 1L
    }
  }
}

# --- CP4.3: Figures exist and are non-empty ---
cat("\nCP4.3 Required Figures:\n")
if ("figures" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] figures: %s\n", not_applicable[["figures"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(required_figures) || length(required_figures) == 0) {
  cat("[NOT VERIFIED] figures: required_figures is empty — the task promised no figure, or the list was never populated\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else {
  for (fig in required_figures) {
    fig_path <- file.path(figures_dir, fig)
    if (!file.exists(fig_path)) {
      cat(sprintf("[FAIL] figure '%s': not found at %s\n", fig, fig_path))
      cp4["failed"] <- cp4["failed"] + 1L
      next
    }
    size_kb <- file.info(fig_path)$size / 1024
    if (is.na(size_kb) || size_kb == 0) {
      cat(sprintf("[FAIL] figure '%s': 0 bytes at %s\n", fig, fig_path))
      cp4["failed"] <- cp4["failed"] + 1L
    } else if (size_kb < 10) {
      cat(sprintf("[WARNING] figure '%s': %.1f KB — under the 10 KB floor, possibly a blank canvas\n", fig, size_kb))
      cp4["warning"] <- cp4["warning"] + 1L
    } else {
      cat(sprintf("[PASS] figure '%s': %.1f KB at %s\n", fig, size_kb, fig_path))
      cp4["passed"] <- cp4["passed"] + 1L
    }
  }
  cat("  Visual inspection required: open each figure above with Read and confirm the rendered content; report the inspection in the CP4 status.\n")
}

# --- CP4.4: Correct data source ---
cat("\nCP4.4 Input Source:\n")
if ("data_source" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] data source: %s\n", not_applicable[["data_source"]]))
  cp4["skipped"] <- cp4["skipped"] + 1L
} else if (is.null(script_source_path) || length(script_source_path) == 0 || !file.exists(script_source_path)) {
  cat("[NOT VERIFIED] data source: script_source_path does not exist — cannot inspect the input paths this script reads\n")
  cp4["not_verified"] <- cp4["not_verified"] + 1L
} else {
  # REASONING: identical exclusion rule to the Python template — comments, the CP4
  # config assignments (which contain the forbidden literal in every correct
  # script), and the CP4 block itself are removed before the scan. Without that,
  # the check reads its own `forbidden_input_dir <- "data/raw/"` line and fails
  # every correct Stage-8 script.
  src_lines <- readLines(script_source_path, warn = FALSE)
  inside_cp4 <- FALSE
  scan_lineno <- integer(0)
  scan_text <- character(0)
  for (i in seq_along(src_lines)) {
    ln <- src_lines[i]
    if (grepl("^\\s*#\\s*---\\s*CP4 Validation", ln, perl = TRUE)) inside_cp4 <- TRUE
    is_config <- grepl("^\\s*(expected_input_dir|forbidden_input_dir)\\s*(<-|=)", ln, perl = TRUE)
    if (!inside_cp4 && !is_config) {
      scan_lineno <- c(scan_lineno, i)
      scan_text <- c(scan_text, sub("#.*$", "", ln))
    }
    if (inside_cp4 && grepl("CP4 FAILED - see details above", ln, fixed = TRUE)) inside_cp4 <- FALSE
  }
  forbidden_hits <- scan_lineno[grepl(forbidden_input_dir, scan_text, fixed = TRUE)]
  expected_hits <- scan_lineno[grepl(expected_input_dir, scan_text, fixed = TRUE)]
  if (length(forbidden_hits) > 0) {
    cat(sprintf("[FAIL] data source: line %d references '%s' (%d line(s) of %d scanned) — Stage 8 must read the cleaned/transformed input, not raw data\n",
                forbidden_hits[1], forbidden_input_dir, length(forbidden_hits), length(scan_text)))
    cp4["failed"] <- cp4["failed"] + 1L
  } else if (length(expected_hits) > 0) {
    # NOTE: no `CP<n>` token on this line — the log comparator would read it as a verdict.
    cat(sprintf("[PASS] data source: line %d reads '%s' and no scanned line references '%s' (%d lines scanned; comments, the checkpoint's own config assignments, and the checkpoint block are excluded)\n",
                expected_hits[1], expected_input_dir, forbidden_input_dir, length(scan_text)))
    cp4["passed"] <- cp4["passed"] + 1L
  } else {
    cat(sprintf("[NOT VERIFIED] data source: no scanned line references '%s' or '%s' (%d lines scanned) — the input path is composed from variables. Declare not_applicable$data_source naming the Plan's input if that is intended\n",
                expected_input_dir, forbidden_input_dir, length(scan_text)))
    cp4["not_verified"] <- cp4["not_verified"] + 1L
  }
}

# Count line, then verdict derived from the counts
cp4_checks_run <- cp4[["passed"]] + cp4[["warning"]] + cp4[["failed"]]
if (cp4[["failed"]] > 0 || cp4[["not_verified"]] > 0 || cp4_checks_run == 0) {
  cp4_verdict <- "FAILED"
} else if (cp4[["warning"]] > 0) {
  cp4_verdict <- "PASSED WITH WARNINGS"
} else {
  cp4_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cp4[["passed"]], cp4[["warning"]], cp4[["failed"]], cp4[["not_verified"]], cp4[["skipped"]]))
cat(sprintf("CP4 VALIDATION: %s\n", cp4_verdict))
cat(strrep("=", 60), "\n")

if (cp4_verdict == "FAILED") {
  stop("CP4 FAILED - see details above")
}
```

### Usage Notes

Set these variables before the CP4 block:

**Python:**
```python
# Configure before CP4 block
# analysis_df = <the frame the estimator consumed>
analysis_results = {                       # assembled from the estimator's own output
    "estimates": {"poverty_rate": -0.184},  # name -> point estimate
    "n": 8421,                              # estimation sample size
    "converged": True,                      # omit for closed-form estimators; then declare not_applicable
}
min_n = 500                                 # Plan's minimum analytic sample
expected_signs = {"poverty_rate": -1}       # ONLY when the Plan pre-registers a direction; {} otherwise
critical_columns = ["ncessch", "enrollment"]
required_figures = ["enrollment_trends.png", "poverty_scatter.png"]
figures_dir = Path("output/figures/")
script_source_path = Path("scripts/stage8_analyze/01_poverty-enrollment.py")
expected_input_dir = "data/processed/"
forbidden_input_dir = "data/raw/"
not_applicable = {}  # e.g. {"convergence": "OLS is closed-form and reports no convergence flag"}
```

**R:**
```r
# Configure before CP4 block
# analysis_df <- <the frame the estimator consumed>
analysis_results <- list(
  estimates = list(poverty_rate = -0.184),
  n = 8421L,
  converged = TRUE
)
min_n <- 500
expected_signs <- list(poverty_rate = -1L)   # ONLY when pre-registered; list() otherwise
critical_columns <- c("ncessch", "enrollment")
required_figures <- c("enrollment_trends.png", "poverty_scatter.png")
figures_dir <- "output/figures/"
script_source_path <- "scripts/stage8_analyze/01_poverty-enrollment.R"
expected_input_dir <- "data/processed/"
forbidden_input_dir <- "data/raw/"
not_applicable <- list()  # e.g. list(convergence = "lm() is closed-form and reports no convergence flag")
```

**`not_applicable` keys recognized by CP4:**

| Key | Suppresses | Declare it when |
|-----|-----------|-----------------|
| `analysis_results` | Results-object presence | The script is visualization-only and produces no estimates |
| `estimates_finite` | Finiteness of point estimates | The output is not a set of scalar estimates (e.g. a fitted surface) |
| `convergence` | Convergence flag | The estimator is closed-form (OLS, `lm()`) and reports no flag |
| `sample_size` | n vs the Plan minimum | The Plan sets no minimum because the universe is fixed and known |
| `expected_signs` | Pre-registered direction | Used only to document a Plan-level decision; an empty `expected_signs` already prints `[SKIPPED]` on its own |
| `critical_nulls` | Critical-column completeness | Nulls in the outcome are themselves the analytic subject |
| `figures` | Figure existence | The script is analysis-only and promises no figure |
| `data_source` | Input-path check | The script builds its input in memory and reads no file, **or** composes its input path from variables so no literal is scannable (the check reports `[NOT VERIFIED]` in that case; declare the key with the Plan's named input as the reason) |

**Semantics reminders:**
- CP4 runs at **Stage 8**, inside the analysis/visualization script — not at Stage 11 or 12. Deliverable completeness is § Pre-Output Verification (Stage 12).
- CP4.3 passing means the file exists and is non-trivial in size. It does **not** mean the figure is correct. The executor must open each figure with Read; the printed reminder is part of the checkpoint, and a CP4 status reported without that inspection is incomplete.
- `[NOT VERIFIED]` makes the verdict `FAILED`. An empty `required_figures` or `critical_columns` is a configuration gap, not a pass.
- `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`**.
- **CP4.4 scans the script, minus three exclusions.** A line is eligible for the data-source scan only if it is (a) not a comment, (b) not an `expected_input_dir` / `forbidden_input_dir` assignment, and (c) not inside the CP4 block (from the `# --- CP4 Validation` marker through the `CP4 FAILED - see details above` raise/stop). Without (b) and (c) the check reads its own configuration — `forbidden_input_dir = "data/raw/"` is a literal `data/raw/` present in *every* correct Stage-8 script — and returns `[FAIL]` unconditionally. Outcomes on the remaining lines: a forbidden literal is `[FAIL]` naming the line; otherwise an expected literal is `[PASS]` naming the line; otherwise `[NOT VERIFIED]`.
- **`[NOT VERIFIED]` here usually means the path is composed from variables** (`INPUT_DIR / f"{year}.parquet"`), which the literal scan cannot resolve. That is a real gap, not a nuisance: declare `not_applicable["data_source"]` with the Plan's named input as the reason, and the block records a counted `[SKIPPED]` with that reason instead.
- The exclusion rule assumes the CP4 block is the one in this reference. A script embedding a renamed or hand-edited CP4 block loses exclusion (c) and will `[FAIL]` on the block's own message strings — another reason not to hand-edit the template.
- The empty-`expected_signs` `[SKIPPED]` is the one place a skip is declared by the config's own emptiness rather than by a `not_applicable` entry — the line still prints the reason and is still counted, and pre-registering a direction that was never planned would be worse than the exception.

---

## Pre-Output Verification (Stage 12)

**When:** Stage 12 final review, after the Report draft exists and before delivery
**Purpose:** Verify the deliverables honor the Plan's commitments — sections present and substantive, scope consistent, Research Outcomes addressed with evidence, Hypotheses transparently assessed
**Classification:** `checkpoint:human-verify` — the agent reports; the researcher confirms before delivery
**Owner:** data-verifier (see `.claude/agents/data-verifier.md`)

This is an **agent checklist, not a script template.** These questions cannot be settled by a file-existence test: "the Limitations section exists" is a regex result, while "the Limitations section honestly describes what the suppression rate does to the conclusions" is a judgment. Attempting to automate them was what produced the old CP4.4's `(Verify manually...)` line — printed inside a block whose verdict then read `PASSED`. Nothing here emits a `CP4` token.

**Relationship to other checks:** substantiveness scanning (§ Substantiveness Validation) supplies the mechanical evidence — stub markers, empty sections, one-value columns — and is advisory. Pre-Output Verification is where a human-accountable agent reads that evidence together with the Plan and the Report and forms a verdict. QA4b covers the reviewer-side pass; this section covers the verifier-side pass.

### PO.1 Report Sections Present and Substantive

Check the Report against `agent_reference/REPORT_TEMPLATE.md`:

1. Every section the Plan requires exists, with the template's heading text
2. Executive Summary and Key Findings are present — their absence blocks delivery
3. Limitations is present and names the specific limitations this analysis actually has, not generic caveats
4. References and the AI Use Disclosure section are complete (GUIDE-LLM A-G, per `agent_reference/AI_DISCLOSURE_REFERENCE.md`)
5. No section is a heading with nothing under it, and no stub marker (TODO, TBD, PLACEHOLDER, lorem ipsum) survives

Record each as PRESENT / MISSING / PRESENT BUT THIN, with the evidence that decided it.

### PO.2 Plan Consistency

Verify these against the Plan document:

1. **Data Sources Match:** every source named in the Plan was actually used, and no undeclared source appears
2. **Year Range Match:** the data covers the years the Plan specified — and the Report says so where it does not
3. **Geographic Scope Match:** the analysis covers the geography in the Plan
4. **Methodology Alignment:** transformations and estimators followed the Plan's methodology, and any deviation is documented with its rationale
5. **Output Count Match:** the number of visualizations and tables matches what the Plan committed to
6. **Notebook Renders:** the Stage 9 notebook renders (`marimo run` / `quarto render`) without error

A **major** deviation from the Plan blocks delivery; a **minor** scope change is acceptable when the Report documents it.

### PO.3 Research Outcomes Verification

For each Research Outcome in the Plan:

1. Read the outcome statement
2. Verify the topic was rigorously investigated and reported
3. Document what evidence demonstrates thorough investigation
4. Mark as ADDRESSED or NOT ADDRESSED — any NOT ADDRESSED outcome blocks delivery

**Example:**
```markdown
| Research Outcome | Evidence of Investigation | Status |
|------------------|--------------------------|--------|
| "Poverty rate variation across districts is characterized" | scatter plot in output/figures/, summary statistics in report, significance testing in analysis script | ADDRESSED |
| "Analysis dataset includes all required variables" | check analysis.parquet schema | ADDRESSED |
| "Data limitations are documented with scope implications" | Limitations section present in Report.md with suppression rate impact | ADDRESSED |
```

> data-verifier forms its own expectations from the research question **before** reading the Plan's Research Outcomes (see `.claude/agents/data-verifier.md` § Independent Assessment). PO.3 is the second half of that protocol, not a substitute for it.

### PO.4 Hypotheses Assessment

For each Hypothesis in the Plan (if any):

1. Read the hypothesis statement and its basis
2. Verify it was assessed with adequate evidence
3. Mark as SUPPORTED / NOT SUPPORTED / PARTIALLY SUPPORTED
4. Either outcome is valid — a refuted hypothesis is a legitimate finding, not a failure. What is not valid is an unassessed hypothesis, or an assessment whose evidence is not shown

**Example:**
```markdown
| Hypothesis | Basis | Assessment | Evidence |
|------------|-------|------------|----------|
| "H1: Higher poverty rates are associated with lower enrollment growth" | Prior demographic literature | NOT SUPPORTED | r = 0.02, p = 0.74 — no significant relationship found. This null finding is reported as a key result. |
```

### Reporting Pre-Output Verification

Report each of PO.1-PO.4 with the same evidence discipline the script templates enforce: state what was checked, what was observed, and which artifact shows it. Use the vocabulary below; the aggregate feeds the data-verifier Verification Report and the researcher's go/no-go decision.

| Outcome | Meaning |
|---------|---------|
| VERIFIED | Checked against the artifact; the commitment is met, and the evidence is named |
| DEVIATION | Checked; the artifact departs from the Plan. Blocks delivery if major; documented if minor |
| NOT VERIFIED | Could not be checked (Plan section absent, artifact missing) — say what was missing; never report this as verified |
| NOT APPLICABLE | The Plan makes no such commitment (e.g. no Hypotheses) — say so explicitly |

An item nobody could check is `NOT VERIFIED`, and a Pre-Output Verification containing a `NOT VERIFIED` item is not a clean pass — exactly as `[NOT VERIFIED]` fails a CP checkpoint.

**Aggregate.** Per-item outcomes are not the reportable result on their own; PO.1-PO.4 roll up into a count line and a derived aggregate, in the same shape the script templates use:

```
Pre-Output items: {verified} verified, {deviation} deviations, {not_verified} not verified, {not_applicable} not applicable
PRE-OUTPUT VERIFICATION: VERIFIED | DEVIATIONS FOUND | NOT VERIFIED
```

Derivation, in order:

1. `NOT VERIFIED` if `not_verified > 0` — an unchecked commitment is not a verified one.
2. Otherwise `DEVIATIONS FOUND` if `deviation > 0`.
3. Otherwise `VERIFIED`.
4. Zero items assessed is `NOT VERIFIED`, never `VERIFIED`. An empty checklist has verified nothing.

These three strings are the only permitted aggregates. `NOT APPLICABLE` items are counted and never silent, but they do not make the aggregate anything other than what rules 1-3 produce. `STATE_TEMPLATE.md` records the Pre-Output row with these four counts and this three-string aggregate — not the CP/QA enums, which mean different things.

**Comparator safety.** No Pre-Output line carries a `CP<n>` token. `scripts/compare_execution_logs.py` reads any line containing `CP\d` plus PASS/FAIL as a checkpoint verdict, and Pre-Output Verification is a Stage-12 human gate, not a checkpoint. Report `PRE-OUTPUT VERIFICATION: …`, never `CP4 …`.

---

## Join-Specific Validation

**Purpose:** Joins have unique failure modes (fan-out, data loss, key mismatch) that require specialized validation.

### Code Template

```python
# --- Join Validation ---
# INTENT: Validate a join by checking the declared cardinality against an explicit
# row-count bound, row retention, key matching, null keys, and duplicate keys.
# REASONING: Joins are the highest-risk transformation — fan-out and silent key
# mismatch corrupt every downstream number. The cardinality check therefore
# derives an explicit upper bound for each (expected_cardinality, join_type) pair
# rather than falling through to PASS for pairs it does not model.
# ASSUMES: left_df/right_df are the inputs, result_df is the join output;
# join_keys/expected_cardinality/join_type/not_applicable configured above.
print("\n" + "=" * 60)
print(f"JOIN VALIDATION ({join_type} join, declared {expected_cardinality})")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

joinv = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

LEGAL_JOIN_TYPES = ("inner", "left", "right", "outer", "full", "semi", "anti")
LEGAL_CARDINALITIES = ("1:1", "1:many", "many:1", "many:many")
LOW_MATCH_THRESHOLD = 0.5   # key overlap below this fraction warns
HIGH_LOSS_THRESHOLD = 0.9   # retention loss above this fraction fails
MED_LOSS_THRESHOLD = 0.5    # retention loss above this fraction warns

left_rows = len(left_df)
right_rows = len(right_df)
result_rows = len(result_df)

print("\nRow Counts:")
print(f"  Left side:  {left_rows:,}")
print(f"  Right side: {right_rows:,}")
print(f"  Result:     {result_rows:,}")

# Check: cardinality against an explicit upper bound for this (cardinality, join_type) pair
if "cardinality" in not_applicable:
    print(f"[SKIPPED] cardinality: {not_applicable['cardinality']}")
    joinv["skipped"] += 1
elif join_type not in LEGAL_JOIN_TYPES:
    print(f"[FAIL] cardinality: unrecognized join_type {join_type!r} — legal values are {list(LEGAL_JOIN_TYPES)}")
    joinv["failed"] += 1
elif expected_cardinality not in LEGAL_CARDINALITIES:
    print(f"[FAIL] cardinality: unrecognized expected_cardinality {expected_cardinality!r} — legal values are {list(LEGAL_CARDINALITIES)}")
    joinv["failed"] += 1
else:
    # INTENT: the maximum number of result rows the declared cardinality permits.
    # None means this pair has no finite bound the check can assert.
    card_upper = None
    if expected_cardinality == "1:1":
        # REASONING: under a declared 1:1 every match consumes one row from EACH
        # side, so an inner or semi join cannot return more rows than the smaller
        # input. Bounding these by left_rows alone let a 1:1 inner join against a
        # 3-row right side return 6 rows and still PASS — a fan-out the declared
        # cardinality forbids. Only the outer-preserved side relaxes the bound.
        if join_type in ("inner", "semi"):
            card_upper = min(left_rows, right_rows)
        elif join_type in ("left", "anti"):
            card_upper = left_rows          # every left row survives at most once
        elif join_type == "right":
            card_upper = right_rows
        else:  # outer / full — unmatched rows from both sides survive
            card_upper = left_rows + right_rows
    elif expected_cardinality == "1:many":
        if join_type in ("semi", "anti"):
            card_upper = left_rows          # filtering joins never fan out
        elif join_type in ("inner", "right"):
            card_upper = right_rows         # each "many"-side row matches at most one left row
        else:  # left / outer / full — plus unmatched left rows
            card_upper = right_rows + left_rows
    elif expected_cardinality == "many:1":
        if join_type in ("inner", "left", "semi", "anti"):
            card_upper = left_rows
        else:  # right / outer / full — plus unmatched right rows
            card_upper = left_rows + right_rows
    else:  # many:many
        if join_type in ("semi", "anti"):
            card_upper = left_rows
        else:
            card_upper = None               # a many:many product has no useful bound here

    if card_upper is None:
        print(f"[NOT VERIFIED] cardinality: no row-count bound is derivable for the pair ('{expected_cardinality}', '{join_type}') — declare the expected result size in the Plan and use not_applicable['cardinality'] with that reason")
        joinv["not_verified"] += 1
    elif result_rows > card_upper:
        ratio = result_rows / card_upper if card_upper > 0 else float("inf")
        print(f"[FAIL] cardinality: result {result_rows:,} rows exceeds the '{expected_cardinality}'/'{join_type}' upper bound of {card_upper:,} ({ratio:.1f}x — fan-out)")
        joinv["failed"] += 1
    else:
        print(f"[PASS] cardinality: result {result_rows:,} rows within the '{expected_cardinality}'/'{join_type}' upper bound of {card_upper:,}")
        joinv["passed"] += 1

# Check: row retention, measured against the side the join type preserves
if "row_loss" in not_applicable:
    print(f"[SKIPPED] row loss: {not_applicable['row_loss']}")
    joinv["skipped"] += 1
elif left_rows == 0:
    print("[FAIL] row loss: left_df is empty (0 rows) — retention undefined, the join is untestable")
    joinv["failed"] += 1
elif join_type not in LEGAL_JOIN_TYPES:
    print(f"[FAIL] row loss: unrecognized join_type {join_type!r} — cannot choose a retention baseline")
    joinv["failed"] += 1
elif join_type in ("inner", "left", "semi"):
    loss_rate = 1 - (result_rows / left_rows)
    if loss_rate > HIGH_LOSS_THRESHOLD:
        print(f"[FAIL] row loss: {loss_rate:.1%} of left rows lost ({left_rows - result_rows:,}/{left_rows:,}, >{HIGH_LOSS_THRESHOLD:.0%})")
        joinv["failed"] += 1
    elif loss_rate > MED_LOSS_THRESHOLD:
        print(f"[WARNING] row loss: {loss_rate:.1%} of left rows lost ({left_rows - result_rows:,}/{left_rows:,}, >{MED_LOSS_THRESHOLD:.0%})")
        joinv["warning"] += 1
    elif loss_rate < 0:
        # REASONING: a negative loss rate is a row GAIN, and printing it as
        # "-25.0% of left rows lost (-1/4)" made a legitimate 1:many fan-out read
        # as a nonsense loss figure. Row growth is not a retention defect — the
        # cardinality check above is what bounds fan-out — so this stays a PASS,
        # phrased as the gain it is.
        print(f"[PASS] row loss: 0 left rows lost; the result gained {result_rows - left_rows:,} rows over the {left_rows:,} left rows ({-loss_rate:.1%} gain — fan-out is bounded by the cardinality check)")
        joinv["passed"] += 1
    else:
        print(f"[PASS] row loss: {loss_rate:.1%} of left rows lost ({left_rows - result_rows:,}/{left_rows:,})")
        joinv["passed"] += 1
elif join_type == "right":
    if right_rows == 0:
        print("[FAIL] row loss: right_df is empty (0 rows) — retention undefined for a right join")
        joinv["failed"] += 1
    else:
        loss_rate = 1 - (result_rows / right_rows)
        if loss_rate > HIGH_LOSS_THRESHOLD:
            print(f"[FAIL] row loss: {loss_rate:.1%} of right rows lost ({right_rows - result_rows:,}/{right_rows:,}, >{HIGH_LOSS_THRESHOLD:.0%})")
            joinv["failed"] += 1
        elif loss_rate > MED_LOSS_THRESHOLD:
            print(f"[WARNING] row loss: {loss_rate:.1%} of right rows lost ({right_rows - result_rows:,}/{right_rows:,}, >{MED_LOSS_THRESHOLD:.0%})")
            joinv["warning"] += 1
        elif loss_rate < 0:
            # REASONING: negative loss is a gain; see the left-side branch above.
            print(f"[PASS] row loss: 0 right rows lost; the result gained {result_rows - right_rows:,} rows over the {right_rows:,} right rows ({-loss_rate:.1%} gain — fan-out is bounded by the cardinality check)")
            joinv["passed"] += 1
        else:
            print(f"[PASS] row loss: {loss_rate:.1%} of right rows lost ({right_rows - result_rows:,}/{right_rows:,})")
            joinv["passed"] += 1
elif join_type in ("outer", "full"):
    # REASONING: an outer join cannot drop a row from either side.
    floor = max(left_rows, right_rows)
    if result_rows < floor:
        print(f"[FAIL] row loss: outer join returned {result_rows:,} rows, fewer than the larger input ({floor:,}) — rows were dropped")
        joinv["failed"] += 1
    else:
        print(f"[PASS] row loss: outer join returned {result_rows:,} rows, at least the larger input ({floor:,})")
        joinv["passed"] += 1
else:  # anti
    if result_rows == 0:
        print(f"[WARNING] row loss: anti join returned 0 of {left_rows:,} left rows — every left row found a match")
        joinv["warning"] += 1
    else:
        print(f"[PASS] row loss: anti join returned {result_rows:,} of {left_rows:,} unmatched left rows ({result_rows / left_rows:.1%})")
        joinv["passed"] += 1

# Check: key matching — one check per join key
print("\nJoin Key Matching:")
if "key_matching" in not_applicable:
    print(f"[SKIPPED] key matching: {not_applicable['key_matching']}")
    joinv["skipped"] += 1
elif join_keys is None or len(join_keys) == 0:
    print("[NOT VERIFIED] key matching: join_keys is empty — the join columns were never declared")
    joinv["not_verified"] += 1
else:
    for key in join_keys:
        if key not in left_df.columns or key not in right_df.columns:
            side = "left_df" if key not in left_df.columns else "right_df"
            print(f"[FAIL] key matching '{key}': absent from {side} — the declared join key does not exist")
            joinv["failed"] += 1
            continue
        left_keys = set(left_df[key].drop_nulls().unique().to_list())
        right_keys = set(right_df[key].drop_nulls().unique().to_list())
        denom = min(len(left_keys), len(right_keys))
        if denom == 0:
            print(f"[FAIL] key matching '{key}': one side has 0 non-null distinct keys (left={len(left_keys):,}, right={len(right_keys):,}) — nothing can match")
            joinv["failed"] += 1
            continue
        overlap = len(left_keys & right_keys)
        match_rate = overlap / denom
        # REASONING: the min-denominated rate answers "did the two key spaces
        # meet at all", which is the threshold question; it says nothing about
        # how much of the LEFT side found a partner. A small lookup table fully
        # contained in a large left frame reads 100% on the min denominator while
        # most left rows go unmatched. Both rates are printed so the line carries
        # the coverage the reader actually needs; the threshold stays on the
        # min-denominated rate so the pass/warn boundary is unchanged.
        left_match_rate = overlap / len(left_keys)
        if match_rate < LOW_MATCH_THRESHOLD:
            print(f"[WARNING] key matching '{key}': {match_rate:.1%} overlap ({overlap:,} shared of min({len(left_keys):,}, {len(right_keys):,}) distinct) — below the {LOW_MATCH_THRESHOLD:.0%} threshold; {left_match_rate:.1%} of the {len(left_keys):,} left distinct keys matched")
            joinv["warning"] += 1
        else:
            print(f"[PASS] key matching '{key}': {match_rate:.1%} overlap ({overlap:,} shared of min({len(left_keys):,}, {len(right_keys):,}) distinct); {left_match_rate:.1%} of the {len(left_keys):,} left distinct keys matched")
            joinv["passed"] += 1

# Check: null join keys in the result — one check per join key
print("\nNull Join Keys in Result:")
if "null_keys" in not_applicable:
    print(f"[SKIPPED] null keys: {not_applicable['null_keys']}")
    joinv["skipped"] += 1
elif join_keys is None or len(join_keys) == 0:
    print("[NOT VERIFIED] null keys: join_keys is empty — no key column to inspect")
    joinv["not_verified"] += 1
else:
    for key in join_keys:
        if key not in result_df.columns:
            print(f"[FAIL] null keys '{key}': join key absent from result_df — the join did not carry its own key through")
            joinv["failed"] += 1
            continue
        null_keys = result_df[key].null_count()
        if null_keys > 0 and join_type in ("inner", "semi"):
            print(f"[WARNING] null keys '{key}': {null_keys:,} of {result_rows:,} result rows have a null key — unexpected for a '{join_type}' join")
            joinv["warning"] += 1
        elif null_keys > 0:
            print(f"[PASS] null keys '{key}': {null_keys:,} of {result_rows:,} result rows have a null key — expected for a '{join_type}' join (unmatched side)")
            joinv["passed"] += 1
        else:
            print(f"[PASS] null keys '{key}': 0 of {result_rows:,} result rows have a null key")
            joinv["passed"] += 1

# Check: duplicate keys on each input side vs the declared cardinality
print("\nDuplicate Keys in Inputs:")
if "duplicate_keys" in not_applicable:
    print(f"[SKIPPED] duplicate keys: {not_applicable['duplicate_keys']}")
    joinv["skipped"] += 1
elif join_keys is None or len(join_keys) == 0:
    print("[NOT VERIFIED] duplicate keys: join_keys is empty — no key column to inspect")
    joinv["not_verified"] += 1
else:
    for key in join_keys:
        if key not in left_df.columns or key not in right_df.columns:
            print(f"[FAIL] duplicate keys '{key}': absent from at least one input — duplication untestable")
            joinv["failed"] += 1
            continue
        left_dups = left_rows - left_df[key].n_unique()
        right_dups = right_rows - right_df[key].n_unique()
        # REASONING: duplicate keys on a side the declared cardinality says is
        # unique are a contradiction between the declaration and the data, not a
        # stylistic concern — the declaration is what every downstream bound and
        # every reader's mental model rests on. A WARNING here let the block still
        # print PASSED WITH WARNINGS, so a 1:1 join over a duplicated key survived
        # review. This is a separate, independent check from the row-count bound:
        # the bound can hold (a right join over a duplicated right key returns
        # exactly right_rows) while the cardinality claim is still false.
        if expected_cardinality == "1:1" and (left_dups > 0 or right_dups > 0):
            print(f"[FAIL] duplicate keys '{key}': declared 1:1 but left has {left_dups:,} and right has {right_dups:,} duplicate key rows — the declared cardinality is contradicted by the inputs")
            joinv["failed"] += 1
        elif expected_cardinality == "1:many" and left_dups > 0:
            print(f"[FAIL] duplicate keys '{key}': declared 1:many but the left ('1') side has {left_dups:,} duplicate key rows — the declared cardinality is contradicted by the inputs")
            joinv["failed"] += 1
        elif expected_cardinality == "many:1" and right_dups > 0:
            print(f"[FAIL] duplicate keys '{key}': declared many:1 but the right ('1') side has {right_dups:,} duplicate key rows — the declared cardinality is contradicted by the inputs")
            joinv["failed"] += 1
        else:
            print(f"[PASS] duplicate keys '{key}': left {left_dups:,}, right {right_dups:,} duplicate key rows — consistent with declared '{expected_cardinality}'")
            joinv["passed"] += 1

# Count line, then verdict derived from the counts
join_checks_run = joinv["passed"] + joinv["warning"] + joinv["failed"]
if joinv["failed"] > 0 or joinv["not_verified"] > 0 or join_checks_run == 0:
    join_verdict = "FAILED"
elif joinv["warning"] > 0:
    join_verdict = "PASSED WITH WARNINGS"
else:
    join_verdict = "PASSED"

print(f"\nChecks: {joinv['passed']} passed, {joinv['warning']} warnings, {joinv['failed']} failed, {joinv['not_verified']} not verified, {joinv['skipped']} skipped")
print(f"JOIN VALIDATION: {join_verdict}")
print("=" * 60)

if join_verdict == "FAILED":
    raise ValueError("Join validation FAILED - see details above")
```

### R Code Template

```r
library(dplyr)

# --- Join Validation ---
# INTENT: Validate a join by checking the declared cardinality against an explicit
# row-count bound, row retention, key matching, null keys, and duplicate keys.
# REASONING: Each (expected_cardinality, join_type) pair gets an explicit bound;
# pairs with no derivable bound report NOT VERIFIED naming the pair.
# ASSUMES: left_df/right_df are the inputs, result_df is the join output.
cat("\n")
cat(strrep("=", 60), "\n")
cat(sprintf("JOIN VALIDATION (%s join, declared %s)\n",
            if (is.null(join_type)) "NULL" else as.character(join_type),
            if (is.null(expected_cardinality)) "NULL" else as.character(expected_cardinality)))
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

joinv <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

LEGAL_JOIN_TYPES <- c("inner", "left", "right", "outer", "full", "semi", "anti")
LEGAL_CARDINALITIES <- c("1:1", "1:many", "many:1", "many:many")
LOW_MATCH_THRESHOLD <- 0.5
HIGH_LOSS_THRESHOLD <- 0.9
MED_LOSS_THRESHOLD <- 0.5

left_rows <- nrow(left_df)
right_rows <- nrow(right_df)
result_rows <- nrow(result_df)

cat("\nRow Counts:\n")
cat(sprintf("  Left side:  %s\n", format(left_rows, big.mark = ",")))
cat(sprintf("  Right side: %s\n", format(right_rows, big.mark = ",")))
cat(sprintf("  Result:     %s\n", format(result_rows, big.mark = ",")))

jt_ok <- !is.null(join_type) && length(join_type) == 1 && is.character(join_type) &&
         !is.na(join_type) && join_type %in% LEGAL_JOIN_TYPES
card_ok <- !is.null(expected_cardinality) && length(expected_cardinality) == 1 &&
           is.character(expected_cardinality) && !is.na(expected_cardinality) &&
           expected_cardinality %in% LEGAL_CARDINALITIES

# Check: cardinality against an explicit upper bound
if ("cardinality" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] cardinality: %s\n", not_applicable[["cardinality"]]))
  joinv["skipped"] <- joinv["skipped"] + 1L
} else if (!jt_ok) {
  cat(sprintf("[FAIL] cardinality: unrecognized join_type '%s' — legal values are %s\n",
              if (is.null(join_type)) "NULL" else paste(as.character(join_type), collapse = ","),
              paste(LEGAL_JOIN_TYPES, collapse = ", ")))
  joinv["failed"] <- joinv["failed"] + 1L
} else if (!card_ok) {
  cat(sprintf("[FAIL] cardinality: unrecognized expected_cardinality '%s' — legal values are %s\n",
              if (is.null(expected_cardinality)) "NULL" else paste(as.character(expected_cardinality), collapse = ","),
              paste(LEGAL_CARDINALITIES, collapse = ", ")))
  joinv["failed"] <- joinv["failed"] + 1L
} else {
  card_upper <- NA_real_
  if (expected_cardinality == "1:1") {
    # REASONING: a 1:1 match consumes one row from each side, so inner/semi cannot
    # exceed the SMALLER input; bounding by left_rows alone missed fan-out whenever
    # the right side was smaller than the left.
    if (join_type %in% c("inner", "semi")) card_upper <- min(left_rows, right_rows)
    else if (join_type %in% c("left", "anti")) card_upper <- left_rows
    else if (join_type == "right") card_upper <- right_rows
    else card_upper <- left_rows + right_rows
  } else if (expected_cardinality == "1:many") {
    if (join_type %in% c("semi", "anti")) card_upper <- left_rows
    else if (join_type %in% c("inner", "right")) card_upper <- right_rows
    else card_upper <- right_rows + left_rows
  } else if (expected_cardinality == "many:1") {
    if (join_type %in% c("inner", "left", "semi", "anti")) card_upper <- left_rows
    else card_upper <- left_rows + right_rows
  } else {
    if (join_type %in% c("semi", "anti")) card_upper <- left_rows else card_upper <- NA_real_
  }

  if (is.na(card_upper)) {
    cat(sprintf("[NOT VERIFIED] cardinality: no row-count bound is derivable for the pair ('%s', '%s') — declare the expected result size in the Plan and use not_applicable$cardinality with that reason\n",
                expected_cardinality, join_type))
    joinv["not_verified"] <- joinv["not_verified"] + 1L
  } else if (result_rows > card_upper) {
    cat(sprintf("[FAIL] cardinality: result %s rows exceeds the '%s'/'%s' upper bound of %s (%.1fx — fan-out)\n",
                format(result_rows, big.mark = ","), expected_cardinality, join_type,
                format(card_upper, big.mark = ","),
                if (card_upper > 0) result_rows / card_upper else Inf))
    joinv["failed"] <- joinv["failed"] + 1L
  } else {
    cat(sprintf("[PASS] cardinality: result %s rows within the '%s'/'%s' upper bound of %s\n",
                format(result_rows, big.mark = ","), expected_cardinality, join_type,
                format(card_upper, big.mark = ",")))
    joinv["passed"] <- joinv["passed"] + 1L
  }
}

# Check: row retention against the side the join type preserves
if ("row_loss" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row loss: %s\n", not_applicable[["row_loss"]]))
  joinv["skipped"] <- joinv["skipped"] + 1L
} else if (left_rows == 0) {
  cat("[FAIL] row loss: left_df is empty (0 rows) — retention undefined, the join is untestable\n")
  joinv["failed"] <- joinv["failed"] + 1L
} else if (!jt_ok) {
  cat("[FAIL] row loss: unrecognized join_type — cannot choose a retention baseline\n")
  joinv["failed"] <- joinv["failed"] + 1L
} else if (join_type %in% c("inner", "left", "semi")) {
  loss_rate <- 1 - (result_rows / left_rows)
  if (loss_rate > HIGH_LOSS_THRESHOLD) {
    cat(sprintf("[FAIL] row loss: %.1f%% of left rows lost (%s/%s, >%.0f%%)\n", loss_rate * 100,
                format(left_rows - result_rows, big.mark = ","), format(left_rows, big.mark = ","),
                HIGH_LOSS_THRESHOLD * 100))
    joinv["failed"] <- joinv["failed"] + 1L
  } else if (loss_rate > MED_LOSS_THRESHOLD) {
    cat(sprintf("[WARNING] row loss: %.1f%% of left rows lost (%s/%s, >%.0f%%)\n", loss_rate * 100,
                format(left_rows - result_rows, big.mark = ","), format(left_rows, big.mark = ","),
                MED_LOSS_THRESHOLD * 100))
    joinv["warning"] <- joinv["warning"] + 1L
  } else if (loss_rate < 0) {
    # REASONING: a negative loss rate is a row GAIN; printing it as
    # "-25.0% of left rows lost" made a legitimate fan-out read as nonsense.
    # Fan-out is bounded by the cardinality check, so this stays a PASS.
    cat(sprintf("[PASS] row loss: 0 left rows lost; the result gained %s rows over the %s left rows (%.1f%% gain — fan-out is bounded by the cardinality check)\n",
                format(result_rows - left_rows, big.mark = ","), format(left_rows, big.mark = ","),
                -loss_rate * 100))
    joinv["passed"] <- joinv["passed"] + 1L
  } else {
    cat(sprintf("[PASS] row loss: %.1f%% of left rows lost (%s/%s)\n", loss_rate * 100,
                format(left_rows - result_rows, big.mark = ","), format(left_rows, big.mark = ",")))
    joinv["passed"] <- joinv["passed"] + 1L
  }
} else if (join_type == "right") {
  if (right_rows == 0) {
    cat("[FAIL] row loss: right_df is empty (0 rows) — retention undefined for a right join\n")
    joinv["failed"] <- joinv["failed"] + 1L
  } else {
    loss_rate <- 1 - (result_rows / right_rows)
    if (loss_rate > HIGH_LOSS_THRESHOLD) {
      cat(sprintf("[FAIL] row loss: %.1f%% of right rows lost (%s/%s, >%.0f%%)\n", loss_rate * 100,
                  format(right_rows - result_rows, big.mark = ","), format(right_rows, big.mark = ","),
                  HIGH_LOSS_THRESHOLD * 100))
      joinv["failed"] <- joinv["failed"] + 1L
    } else if (loss_rate > MED_LOSS_THRESHOLD) {
      cat(sprintf("[WARNING] row loss: %.1f%% of right rows lost (%s/%s, >%.0f%%)\n", loss_rate * 100,
                  format(right_rows - result_rows, big.mark = ","), format(right_rows, big.mark = ","),
                  MED_LOSS_THRESHOLD * 100))
      joinv["warning"] <- joinv["warning"] + 1L
    } else if (loss_rate < 0) {
      # REASONING: negative loss is a gain; see the left-side branch above.
      cat(sprintf("[PASS] row loss: 0 right rows lost; the result gained %s rows over the %s right rows (%.1f%% gain — fan-out is bounded by the cardinality check)\n",
                  format(result_rows - right_rows, big.mark = ","), format(right_rows, big.mark = ","),
                  -loss_rate * 100))
      joinv["passed"] <- joinv["passed"] + 1L
    } else {
      cat(sprintf("[PASS] row loss: %.1f%% of right rows lost (%s/%s)\n", loss_rate * 100,
                  format(right_rows - result_rows, big.mark = ","), format(right_rows, big.mark = ",")))
      joinv["passed"] <- joinv["passed"] + 1L
    }
  }
} else if (join_type %in% c("outer", "full")) {
  floor_rows <- max(left_rows, right_rows)
  if (result_rows < floor_rows) {
    cat(sprintf("[FAIL] row loss: outer join returned %s rows, fewer than the larger input (%s) — rows were dropped\n",
                format(result_rows, big.mark = ","), format(floor_rows, big.mark = ",")))
    joinv["failed"] <- joinv["failed"] + 1L
  } else {
    cat(sprintf("[PASS] row loss: outer join returned %s rows, at least the larger input (%s)\n",
                format(result_rows, big.mark = ","), format(floor_rows, big.mark = ",")))
    joinv["passed"] <- joinv["passed"] + 1L
  }
} else {
  if (result_rows == 0) {
    cat(sprintf("[WARNING] row loss: anti join returned 0 of %s left rows — every left row found a match\n",
                format(left_rows, big.mark = ",")))
    joinv["warning"] <- joinv["warning"] + 1L
  } else {
    cat(sprintf("[PASS] row loss: anti join returned %s of %s unmatched left rows (%.1f%%)\n",
                format(result_rows, big.mark = ","), format(left_rows, big.mark = ","),
                result_rows / left_rows * 100))
    joinv["passed"] <- joinv["passed"] + 1L
  }
}

# Check: key matching — one check per join key
cat("\nJoin Key Matching:\n")
if ("key_matching" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] key matching: %s\n", not_applicable[["key_matching"]]))
  joinv["skipped"] <- joinv["skipped"] + 1L
} else if (is.null(join_keys) || length(join_keys) == 0) {
  cat("[NOT VERIFIED] key matching: join_keys is empty — the join columns were never declared\n")
  joinv["not_verified"] <- joinv["not_verified"] + 1L
} else {
  for (key in join_keys) {
    if (!key %in% names(left_df) || !key %in% names(right_df)) {
      side <- if (!key %in% names(left_df)) "left_df" else "right_df"
      cat(sprintf("[FAIL] key matching '%s': absent from %s — the declared join key does not exist\n", key, side))
      joinv["failed"] <- joinv["failed"] + 1L
      next
    }
    left_keys <- unique(left_df[[key]][!is.na(left_df[[key]])])
    right_keys <- unique(right_df[[key]][!is.na(right_df[[key]])])
    denom <- min(length(left_keys), length(right_keys))
    if (denom == 0) {
      cat(sprintf("[FAIL] key matching '%s': one side has 0 non-NA distinct keys (left=%d, right=%d) — nothing can match\n",
                  key, length(left_keys), length(right_keys)))
      joinv["failed"] <- joinv["failed"] + 1L
      next
    }
    overlap <- length(intersect(left_keys, right_keys))
    match_rate <- overlap / denom
    # REASONING: the min-denominated rate is the threshold question ("did the key
    # spaces meet"); the left-side rate is the coverage question ("how much of the
    # left frame found a partner"). Both are printed; the threshold stays on the
    # min-denominated rate.
    left_match_rate <- overlap / length(left_keys)
    if (match_rate < LOW_MATCH_THRESHOLD) {
      cat(sprintf("[WARNING] key matching '%s': %.1f%% overlap (%s shared of min(%s, %s) distinct) — below the %.0f%% threshold; %.1f%% of the %s left distinct keys matched\n",
                  key, match_rate * 100, format(overlap, big.mark = ","),
                  format(length(left_keys), big.mark = ","), format(length(right_keys), big.mark = ","),
                  LOW_MATCH_THRESHOLD * 100, left_match_rate * 100,
                  format(length(left_keys), big.mark = ",")))
      joinv["warning"] <- joinv["warning"] + 1L
    } else {
      cat(sprintf("[PASS] key matching '%s': %.1f%% overlap (%s shared of min(%s, %s) distinct); %.1f%% of the %s left distinct keys matched\n",
                  key, match_rate * 100, format(overlap, big.mark = ","),
                  format(length(left_keys), big.mark = ","), format(length(right_keys), big.mark = ","),
                  left_match_rate * 100, format(length(left_keys), big.mark = ",")))
      joinv["passed"] <- joinv["passed"] + 1L
    }
  }
}

# Check: null join keys in the result
cat("\nNull Join Keys in Result:\n")
if ("null_keys" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] null keys: %s\n", not_applicable[["null_keys"]]))
  joinv["skipped"] <- joinv["skipped"] + 1L
} else if (is.null(join_keys) || length(join_keys) == 0) {
  cat("[NOT VERIFIED] null keys: join_keys is empty — no key column to inspect\n")
  joinv["not_verified"] <- joinv["not_verified"] + 1L
} else {
  for (key in join_keys) {
    if (!key %in% names(result_df)) {
      cat(sprintf("[FAIL] null keys '%s': join key absent from result_df — the join did not carry its own key through\n", key))
      joinv["failed"] <- joinv["failed"] + 1L
      next
    }
    null_keys <- sum(is.na(result_df[[key]]))
    if (null_keys > 0 && jt_ok && join_type %in% c("inner", "semi")) {
      cat(sprintf("[WARNING] null keys '%s': %s of %s result rows have an NA key — unexpected for a '%s' join\n",
                  key, format(null_keys, big.mark = ","), format(result_rows, big.mark = ","), join_type))
      joinv["warning"] <- joinv["warning"] + 1L
    } else if (null_keys > 0) {
      cat(sprintf("[PASS] null keys '%s': %s of %s result rows have an NA key — expected for this join type (unmatched side)\n",
                  key, format(null_keys, big.mark = ","), format(result_rows, big.mark = ",")))
      joinv["passed"] <- joinv["passed"] + 1L
    } else {
      cat(sprintf("[PASS] null keys '%s': 0 of %s result rows have an NA key\n",
                  key, format(result_rows, big.mark = ",")))
      joinv["passed"] <- joinv["passed"] + 1L
    }
  }
}

# Check: duplicate keys on each input side vs the declared cardinality
cat("\nDuplicate Keys in Inputs:\n")
if ("duplicate_keys" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] duplicate keys: %s\n", not_applicable[["duplicate_keys"]]))
  joinv["skipped"] <- joinv["skipped"] + 1L
} else if (is.null(join_keys) || length(join_keys) == 0) {
  cat("[NOT VERIFIED] duplicate keys: join_keys is empty — no key column to inspect\n")
  joinv["not_verified"] <- joinv["not_verified"] + 1L
} else {
  for (key in join_keys) {
    if (!key %in% names(left_df) || !key %in% names(right_df)) {
      cat(sprintf("[FAIL] duplicate keys '%s': absent from at least one input — duplication untestable\n", key))
      joinv["failed"] <- joinv["failed"] + 1L
      next
    }
    left_dups <- left_rows - n_distinct(left_df[[key]])
    right_dups <- right_rows - n_distinct(right_df[[key]])
    # REASONING: same ruling as the Python block — a duplicate key on a side the
    # declaration calls unique contradicts the declaration, so it is [FAIL], not a
    # warning. Independent of the row-count bound, which can hold while the
    # cardinality claim is false.
    if (card_ok && expected_cardinality == "1:1" && (left_dups > 0 || right_dups > 0)) {
      cat(sprintf("[FAIL] duplicate keys '%s': declared 1:1 but left has %s and right has %s duplicate key rows — the declared cardinality is contradicted by the inputs\n",
                  key, format(left_dups, big.mark = ","), format(right_dups, big.mark = ",")))
      joinv["failed"] <- joinv["failed"] + 1L
    } else if (card_ok && expected_cardinality == "1:many" && left_dups > 0) {
      cat(sprintf("[FAIL] duplicate keys '%s': declared 1:many but the left ('1') side has %s duplicate key rows — the declared cardinality is contradicted by the inputs\n",
                  key, format(left_dups, big.mark = ",")))
      joinv["failed"] <- joinv["failed"] + 1L
    } else if (card_ok && expected_cardinality == "many:1" && right_dups > 0) {
      cat(sprintf("[FAIL] duplicate keys '%s': declared many:1 but the right ('1') side has %s duplicate key rows — the declared cardinality is contradicted by the inputs\n",
                  key, format(right_dups, big.mark = ",")))
      joinv["failed"] <- joinv["failed"] + 1L
    } else {
      cat(sprintf("[PASS] duplicate keys '%s': left %s, right %s duplicate key rows — consistent with the declared cardinality\n",
                  key, format(left_dups, big.mark = ","), format(right_dups, big.mark = ",")))
      joinv["passed"] <- joinv["passed"] + 1L
    }
  }
}

# Count line, then verdict derived from the counts
join_checks_run <- joinv[["passed"]] + joinv[["warning"]] + joinv[["failed"]]
if (joinv[["failed"]] > 0 || joinv[["not_verified"]] > 0 || join_checks_run == 0) {
  join_verdict <- "FAILED"
} else if (joinv[["warning"]] > 0) {
  join_verdict <- "PASSED WITH WARNINGS"
} else {
  join_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            joinv[["passed"]], joinv[["warning"]], joinv[["failed"]], joinv[["not_verified"]], joinv[["skipped"]]))
cat(sprintf("JOIN VALIDATION: %s\n", join_verdict))
cat(strrep("=", 60), "\n")

if (join_verdict == "FAILED") {
  stop("Join validation FAILED - see details above")
}
```

### Usage Notes

Set these variables before the join validation block:

**Python:**
```python
# Configure before join validation block
join_keys = ["ncessch"]
expected_cardinality = "1:1"  # "1:1" | "1:many" | "many:1" | "many:many"
join_type = "inner"           # "inner" | "left" | "right" | "outer" | "full" | "semi" | "anti"
not_applicable = {}           # e.g. {"duplicate_keys": "right side is a deduplicated lookup by construction"}
# left_df = <left DataFrame>
# right_df = <right DataFrame>
# result_df = <join result DataFrame>
```

**R:**
```r
# Configure before join validation block
join_keys <- c("ncessch")
expected_cardinality <- "1:1"  # "1:1" | "1:many" | "many:1" | "many:many"
join_type <- "inner"           # "inner" | "left" | "right" | "outer" | "full" | "semi" | "anti"
not_applicable <- list()       # e.g. list(duplicate_keys = "right side is a deduplicated lookup by construction")
# left_df <- <left data frame>
# right_df <- <right data frame>
# result_df <- <join result data frame>
```

**Cardinality bounds actually asserted.** The cardinality check compares `result_rows` against an explicit upper bound per pair. Fan-out beyond the bound is a `[FAIL]`, not a warning — an unnoticed fan-out multiplies every downstream aggregate.

| Declared cardinality | inner | left | right | outer / full | semi | anti |
|---|---|---|---|---|---|---|
| `1:1` | min(left, right) | left | right | left + right | min(left, right) | left |
| `1:many` | right | right + left | right | right + left | left | left |
| `many:1` | left | left | left + right | left + right | left | left |
| `many:many` | — | — | — | — | left | left |

Cells marked `—` have no finite bound this check can derive; those pairs emit `[NOT VERIFIED] cardinality` naming the pair, which fails the block. Declare the expected result size in the Plan and record it via `not_applicable["cardinality"]` if a many:many product is genuinely intended.

**Cardinality is checked twice, independently.** The bound above tests the *result*; the duplicate-keys check tests the *inputs*. A declared cardinality that says a side is unique is contradicted the moment that side carries a duplicate key, and that contradiction is a `[FAIL]` regardless of whether the row-count bound held:

| Declared cardinality | Contradicting input condition | Outcome |
|---|---|---|
| `1:1` | duplicate keys on **either** side | `[FAIL] duplicate keys …` |
| `1:many` | duplicate keys on the **left** (`1`) side | `[FAIL] duplicate keys …` |
| `many:1` | duplicate keys on the **right** (`1`) side | `[FAIL] duplicate keys …` |
| `many:many` | none — duplication is declared on both sides | `[PASS]` with both counts |

The bound alone does not catch these. A `1:1` **right** join over a right side with one duplicated key returns exactly `right_rows`, inside its bound, while the 1:1 claim every downstream aggregate rests on is already false. Previously this printed `[WARNING]` and the block reported `PASSED WITH WARNINGS`; it now fails and raises. If the duplication is known and intended, declare it: `not_applicable["duplicate_keys"] = "<reason>"` prints one `[SKIPPED]` line and leaves the bound check running.

**Why `1:1` inner and semi are bounded by the *smaller* side.** A declared 1:1 means each match consumes one row from each input, so the result cannot be larger than either input. The earlier `left` bound was vacuous whenever the right side was smaller — a 1:1 inner join of 6 left rows against 3 right rows returning 6 rows is a fan-out on the right key, and `result_rows <= left_rows` waved it through. The outer-preserved cells (`left`, `right`, `outer/full`) keep their looser bounds because unmatched rows from the preserved side legitimately survive.

**`not_applicable` keys recognized by Join Validation:**

| Key | Suppresses | Declare it when |
|-----|-----------|-----------------|
| `cardinality` | Row-count bound check | A many:many join is intended and the Plan states the expected result size |
| `row_loss` | Retention check | The join is an intentional filter to a documented subset |
| `key_matching` | Key overlap rate | Low overlap is the analytic finding (e.g. measuring coverage gaps) |
| `null_keys` | Null keys in result | Null keys are meaningful data in this domain |
| `duplicate_keys` | Input-side duplication vs declared cardinality (a `[FAIL]` when undeclared) | Duplication is known and documented in the Plan |

**Thresholds stated in the output lines:** key overlap warns below **50%** of the smaller key space; retention loss warns above **50%** and fails above **90%**; an outer join returning fewer rows than its larger input fails; an anti join returning zero rows warns.

**Two match rates on every key-matching line.** The threshold rate is `overlap / min(left distinct, right distinct)` — "did the two key spaces meet at all". The line also reports `overlap / left distinct` — "how much of the left frame found a partner" — because a small lookup table wholly contained in a large left frame reads 100% on the min denominator while most left rows go unmatched. Only the min-denominated rate drives the pass/warn boundary; the left rate is reported evidence.

**Semantics reminders:**
- Unrecognized `join_type` or `expected_cardinality` is `[FAIL]` with the offending value quoted — the config was present and wrong, which is different from missing.
- Duplicate keys contradicting the declared cardinality are `[FAIL]`, not a warning (table above).
- `left_df` with 0 rows is `[FAIL]`, never a 0.0% loss PASS.
- A result *larger* than the retention baseline is reported as a row **gain**, not a negative loss — a `1:many` fan-out is a legitimate PASS on the retention check, and the row-count bound above is what constrains it.
- `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`**.

---

## Substantiveness Validation (Stub Detection)

**Purpose:** Verify that data and outputs contain real implementation, not placeholders or suspicious patterns that indicate incomplete processing.

**Advisory, by design.** Unlike CP1-CP4 and Join validation, these blocks do **not** raise or `stop()` on `FAILED`. They produce evidence for a human-accountable reviewer (data-verifier at Stage 12, code-reviewer at QA4b) who decides what a stub finding means for delivery. That is a deliberate choice, not an omission — but it means a `FAILED` substantiveness verdict must be read and acted on by an agent; nothing in the pipeline halts on it.

### Code Template

```python
import polars as pl

# --- Substantiveness Validation: Data ---
# INTENT: Detect columns that look processed but carry no information — one value,
# all zeros, all null, or implausibly round numbers.
# REASONING: Every column named in key_columns produces exactly one line per
# sub-check, so an absent column reports [NOT VERIFIED] instead of vanishing from
# the output and leaving a bare "[PASS] no issues found".
# ASSUMES: df is the frame to inspect; key_columns/context/not_applicable configured above.
print("\n" + "=" * 60)
print(f"SUBSTANTIVENESS CHECK: {context}")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

subst = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Same numeric-dtype list as CP2 — keep the two in sync so no integer width is
# exempted here that CP2 would have inspected.
NUMERIC_DTYPES = [pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                  pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                  pl.Float32, pl.Float64]

n_rows = len(df)

# INTENT: resolve applicability ONCE per check, before the per-column loop.
# REASONING: testing `"all_null" in not_applicable` inside the loop emitted one
# [SKIPPED] line per column for a single declared decision, so a 40-column frame
# inflated the skipped count 40x and buried the real findings. A declaration is
# about the check, not about each column it would have visited.
skip_all_null = "all_null" in not_applicable
skip_single_value = "single_value" in not_applicable
skip_all_zeros = "all_zeros" in not_applicable
skip_round_numbers = "round_numbers" in not_applicable
for na_key, na_label in (("all_null", "all-null"), ("single_value", "single-value"),
                         ("all_zeros", "all-zeros"), ("round_numbers", "round-numbers")):
    if na_key in not_applicable:
        print(f"[SKIPPED] {na_label}: {not_applicable[na_key]}")
        subst["skipped"] += 1

if key_columns is None or len(key_columns) == 0:
    print("[NOT VERIFIED] data substantiveness: key_columns is empty — no column was nominated for inspection")
    subst["not_verified"] += 1
elif n_rows == 0:
    print("[FAIL] data substantiveness: the frame has 0 rows — there is nothing substantive to find")
    subst["failed"] += 1
else:
    # A frame of 1-10 rows is real data, just too small for the distributional
    # sub-checks to mean much. That is a [WARNING] carrying the count, not a
    # [NOT VERIFIED] — the latter would fail the block for every small frame.
    if n_rows <= 10:
        print(f"[WARNING] frame size: {n_rows} rows — constant-column and rounding-rate evidence is weak below 10 rows")
        subst["warning"] += 1
    for col in key_columns:
        if col not in df.columns:
            print(f"[NOT VERIFIED] substantiveness '{col}': column absent from the frame — nothing inspected")
            subst["not_verified"] += 1
            continue

        n_null = df[col].null_count()

        # Sub-check: entirely null
        if skip_all_null:
            pass
        elif n_null == n_rows:
            print(f"[FAIL] all-null '{col}': {n_null:,} of {n_rows:,} values are null — the column is empty")
            subst["failed"] += 1
        else:
            print(f"[PASS] all-null '{col}': {n_rows - n_null:,} of {n_rows:,} values are non-null")
            subst["passed"] += 1

        # Sub-check: single unique value
        if skip_single_value:
            pass
        else:
            n_unique = df[col].drop_nulls().n_unique()
            if n_unique == 1:
                value = df[col].drop_nulls().unique().to_list()[0]
                print(f"[FAIL] single-value '{col}': 1 distinct non-null value ({value!r}) across {n_rows:,} rows")
                subst["failed"] += 1
            elif n_unique == 0:
                print(f"[FAIL] single-value '{col}': 0 distinct non-null values across {n_rows:,} rows")
                subst["failed"] += 1
            else:
                print(f"[PASS] single-value '{col}': {n_unique:,} distinct non-null values across {n_rows:,} rows")
                subst["passed"] += 1

        # Numeric-only sub-checks
        if df[col].dtype not in NUMERIC_DTYPES:
            print(f"[SKIPPED] numeric checks '{col}': dtype {df[col].dtype} is not numeric — all-zeros and round-number checks do not apply")
            subst["skipped"] += 1
            continue

        non_null = df[col].drop_nulls()

        # Sub-check: all zeros
        if skip_all_zeros:
            pass
        elif len(non_null) == 0:
            print(f"[NOT VERIFIED] all-zeros '{col}': no non-null values to inspect")
            subst["not_verified"] += 1
        else:
            n_zero = int((non_null == 0).sum())
            if n_zero == len(non_null):
                print(f"[FAIL] all-zeros '{col}': all {len(non_null):,} non-null values are 0")
                subst["failed"] += 1
            else:
                print(f"[PASS] all-zeros '{col}': {n_zero:,} of {len(non_null):,} non-null values are 0")
                subst["passed"] += 1

        # Sub-check: suspiciously round numbers
        if skip_round_numbers:
            pass
        elif len(non_null) <= 10:
            # Weak evidence, but the values were inspected — [WARNING] with the
            # count, not [NOT VERIFIED], which would fail the block for a small frame.
            print(f"[WARNING] round-numbers '{col}': only {len(non_null)} non-null values — too few for a meaningful rounding rate")
            subst["warning"] += 1
        else:
            round_count = int((non_null % 1000 == 0).sum())
            round_rate = round_count / len(non_null)
            col_max = non_null.max()
            if round_rate > 0.9 and col_max > 1000:
                print(f"[WARNING] round-numbers '{col}': {round_rate:.0%} of {len(non_null):,} values are multiples of 1000 (max {col_max})")
                subst["warning"] += 1
            else:
                print(f"[PASS] round-numbers '{col}': {round_rate:.0%} of {len(non_null):,} values are multiples of 1000 (max {col_max})")
                subst["passed"] += 1

subst_checks_run = subst["passed"] + subst["warning"] + subst["failed"]
if subst["failed"] > 0 or subst["not_verified"] > 0 or subst_checks_run == 0:
    subst_verdict = "FAILED"
elif subst["warning"] > 0:
    subst_verdict = "PASSED WITH WARNINGS"
else:
    subst_verdict = "PASSED"

print(f"\nChecks: {subst['passed']} passed, {subst['warning']} warnings, {subst['failed']} failed, {subst['not_verified']} not verified, {subst['skipped']} skipped")
print(f"DATA SUBSTANTIVENESS: {subst_verdict}")
print("=" * 60)
# Advisory block: no raise. A FAILED verdict here is evidence for the reviewer,
# not a pipeline halt.
```

#### Data Substantiveness Check (R)

```r
library(dplyr)

# --- Substantiveness Validation: Data ---
# INTENT: Detect columns that look processed but carry no information.
# ASSUMES: df is the frame to inspect; key_columns/context/not_applicable configured above.
cat("\n")
cat(strrep("=", 60), "\n")
cat(sprintf("SUBSTANTIVENESS CHECK: %s\n", context))
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

subst <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)
n_rows <- nrow(df)

# Applicability resolved once per check, before the per-column loop — one
# [SKIPPED] line per declared decision, not one per column it would have visited.
na_keys <- c("all_null", "single_value", "all_zeros", "round_numbers")
na_labels <- c("all-NA", "single-value", "all-zeros", "round-numbers")
for (i in seq_along(na_keys)) {
  if (na_keys[i] %in% names(not_applicable)) {
    cat(sprintf("[SKIPPED] %s: %s\n", na_labels[i], not_applicable[[na_keys[i]]]))
    subst["skipped"] <- subst["skipped"] + 1L
  }
}
skip_all_null <- "all_null" %in% names(not_applicable)
skip_single_value <- "single_value" %in% names(not_applicable)
skip_all_zeros <- "all_zeros" %in% names(not_applicable)
skip_round_numbers <- "round_numbers" %in% names(not_applicable)

if (is.null(key_columns) || length(key_columns) == 0) {
  cat("[NOT VERIFIED] data substantiveness: key_columns is empty — no column was nominated for inspection\n")
  subst["not_verified"] <- subst["not_verified"] + 1L
} else if (n_rows == 0) {
  cat("[FAIL] data substantiveness: the frame has 0 rows — there is nothing substantive to find\n")
  subst["failed"] <- subst["failed"] + 1L
} else {
  if (n_rows <= 10) {
    cat(sprintf("[WARNING] frame size: %d rows — constant-column and rounding-rate evidence is weak below 10 rows\n", n_rows))
    subst["warning"] <- subst["warning"] + 1L
  }
  for (col in key_columns) {
    if (!col %in% names(df)) {
      cat(sprintf("[NOT VERIFIED] substantiveness '%s': column absent from the frame — nothing inspected\n", col))
      subst["not_verified"] <- subst["not_verified"] + 1L
      next
    }

    n_null <- sum(is.na(df[[col]]))

    # Sub-check: entirely NA
    if (skip_all_null) {
      invisible(NULL)
    } else if (n_null == n_rows) {
      cat(sprintf("[FAIL] all-NA '%s': %s of %s values are NA — the column is empty\n", col,
                  format(n_null, big.mark = ","), format(n_rows, big.mark = ",")))
      subst["failed"] <- subst["failed"] + 1L
    } else {
      cat(sprintf("[PASS] all-NA '%s': %s of %s values are non-NA\n", col,
                  format(n_rows - n_null, big.mark = ","), format(n_rows, big.mark = ",")))
      subst["passed"] <- subst["passed"] + 1L
    }

    non_null <- df[[col]][!is.na(df[[col]])]

    # Sub-check: single unique value
    if (skip_single_value) {
      invisible(NULL)
    } else {
      n_unique <- length(unique(non_null))
      if (n_unique == 1) {
        cat(sprintf("[FAIL] single-value '%s': 1 distinct non-NA value (%s) across %s rows\n", col,
                    as.character(non_null[1]), format(n_rows, big.mark = ",")))
        subst["failed"] <- subst["failed"] + 1L
      } else if (n_unique == 0) {
        cat(sprintf("[FAIL] single-value '%s': 0 distinct non-NA values across %s rows\n", col,
                    format(n_rows, big.mark = ",")))
        subst["failed"] <- subst["failed"] + 1L
      } else {
        cat(sprintf("[PASS] single-value '%s': %s distinct non-NA values across %s rows\n", col,
                    format(n_unique, big.mark = ","), format(n_rows, big.mark = ",")))
        subst["passed"] <- subst["passed"] + 1L
      }
    }

    # Numeric-only sub-checks
    if (!is.numeric(df[[col]])) {
      cat(sprintf("[SKIPPED] numeric checks '%s': column is %s, not numeric — all-zeros and round-number checks do not apply\n",
                  col, class(df[[col]])[1]))
      subst["skipped"] <- subst["skipped"] + 1L
      next
    }

    # Sub-check: all zeros
    if (skip_all_zeros) {
      invisible(NULL)
    } else if (length(non_null) == 0) {
      cat(sprintf("[NOT VERIFIED] all-zeros '%s': no non-NA values to inspect\n", col))
      subst["not_verified"] <- subst["not_verified"] + 1L
    } else {
      n_zero <- sum(non_null == 0)
      if (n_zero == length(non_null)) {
        cat(sprintf("[FAIL] all-zeros '%s': all %s non-NA values are 0\n", col, format(length(non_null), big.mark = ",")))
        subst["failed"] <- subst["failed"] + 1L
      } else {
        cat(sprintf("[PASS] all-zeros '%s': %s of %s non-NA values are 0\n", col,
                    format(n_zero, big.mark = ","), format(length(non_null), big.mark = ",")))
        subst["passed"] <- subst["passed"] + 1L
      }
    }

    # Sub-check: suspiciously round numbers
    if (skip_round_numbers) {
      invisible(NULL)
    } else if (length(non_null) <= 10) {
      cat(sprintf("[WARNING] round-numbers '%s': only %d non-NA values — too few for a meaningful rounding rate\n",
                  col, length(non_null)))
      subst["warning"] <- subst["warning"] + 1L
    } else {
      round_count <- sum(non_null %% 1000 == 0)
      round_rate <- round_count / length(non_null)
      col_max <- max(non_null)
      if (round_rate > 0.9 && col_max > 1000) {
        cat(sprintf("[WARNING] round-numbers '%s': %.0f%% of %s values are multiples of 1000 (max %s)\n",
                    col, round_rate * 100, format(length(non_null), big.mark = ","), as.character(col_max)))
        subst["warning"] <- subst["warning"] + 1L
      } else {
        cat(sprintf("[PASS] round-numbers '%s': %.0f%% of %s values are multiples of 1000 (max %s)\n",
                    col, round_rate * 100, format(length(non_null), big.mark = ","), as.character(col_max)))
        subst["passed"] <- subst["passed"] + 1L
      }
    }
  }
}

subst_checks_run <- subst[["passed"]] + subst[["warning"]] + subst[["failed"]]
if (subst[["failed"]] > 0 || subst[["not_verified"]] > 0 || subst_checks_run == 0) {
  subst_verdict <- "FAILED"
} else if (subst[["warning"]] > 0) {
  subst_verdict <- "PASSED WITH WARNINGS"
} else {
  subst_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            subst[["passed"]], subst[["warning"]], subst[["failed"]], subst[["not_verified"]], subst[["skipped"]]))
cat(sprintf("DATA SUBSTANTIVENESS: %s\n", subst_verdict))
cat(strrep("=", 60), "\n")
# Advisory block: no stop(). A FAILED verdict is evidence for the reviewer.
```

#### Text Substantiveness Check

> *Language note: this is verifier tooling that scans text files, not pipeline code — it may run in Python even on R projects.*

```python
import re
from pathlib import Path

# --- Substantiveness Validation: Text ---
# INTENT: Detect stub markers, empty sections, and missing/thin required sections
# in a written deliverable.
# ASSUMES: file_path points at the document; required_sections/not_applicable configured above.
print("\n" + "=" * 60)
print(f"TEXT SUBSTANTIVENESS CHECK: {file_path}")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

text_subst = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

stub_patterns = [
    (r'\bTODO\b', "TODO marker"),
    (r'\bFIXME\b', "FIXME marker"),
    (r'\bPLACEHOLDER\b', "PLACEHOLDER marker"),
    (r'\bTBD\b', "TBD marker"),
    (r'\bXXX\b', "XXX marker"),
    (r'\[add more\]', "Placeholder [add more]"),
    (r'\[your .* here\]', "Template placeholder"),
    (r'\[TODO.*?\]', "TODO in brackets"),
    (r'coming soon', "Coming soon placeholder"),
    (r'lorem ipsum', "Lorem ipsum placeholder"),
]

if not Path(file_path).exists():
    print(f"[NOT VERIFIED] text substantiveness: {file_path} does not exist — nothing scanned")
    text_subst["not_verified"] += 1
    content = ""
else:
    content = Path(file_path).read_text()
    if len(content.strip()) == 0:
        print(f"[FAIL] text substantiveness: {file_path} is empty ({len(content)} bytes) — no content to assess")
        text_subst["failed"] += 1
        content = ""
    else:
        # Check: stub markers
        if "stub_patterns" in not_applicable:
            print(f"[SKIPPED] stub markers: {not_applicable['stub_patterns']}")
            text_subst["skipped"] += 1
        else:
            hits = []
            for pattern, description in stub_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if len(matches) > 0:
                    hits.append(f"{description} x{len(matches)}")
            if len(hits) > 0:
                print(f"[FAIL] stub markers: {len(hits)} pattern(s) matched in {len(content):,} chars ({'; '.join(hits)})")
                text_subst["failed"] += 1
            else:
                print(f"[PASS] stub markers: 0 of {len(stub_patterns)} patterns matched in {len(content):,} chars")
                text_subst["passed"] += 1

        # Check: empty sections
        if "empty_sections" in not_applicable:
            print(f"[SKIPPED] empty sections: {not_applicable['empty_sections']}")
            text_subst["skipped"] += 1
        else:
            all_sections = re.findall(r'^##\s+([^\n]+)', content, re.MULTILINE)
            empty = [s.strip() for s in re.findall(r'(##\s+[^\n]+)\n\s*(?=##|\Z)', content)]
            if len(all_sections) == 0:
                print("[NOT VERIFIED] empty sections: the document has no '##' headings — section structure not assessable")
                text_subst["not_verified"] += 1
            elif len(empty) > 0:
                print(f"[FAIL] empty sections: {len(empty)} of {len(all_sections)} headings have no body ({'; '.join(empty)})")
                text_subst["failed"] += 1
            else:
                print(f"[PASS] empty sections: 0 of {len(all_sections)} headings have an empty body")
                text_subst["passed"] += 1

        # Check: required sections present and substantive
        if "required_sections" in not_applicable:
            print(f"[SKIPPED] required sections: {not_applicable['required_sections']}")
            text_subst["skipped"] += 1
        elif required_sections is None or len(required_sections) == 0:
            print("[NOT VERIFIED] required sections: required_sections is empty — no section list to check against")
            text_subst["not_verified"] += 1
        else:
            for section in required_sections:
                section_pattern = rf'##\s*{re.escape(section)}\s*\n(.+?)(?=\n##|\Z)'
                match = re.search(section_pattern, content, re.DOTALL | re.IGNORECASE)
                if match is None:
                    print(f"[FAIL] required section '{section}': heading not found")
                    text_subst["failed"] += 1
                elif len(match.group(1).strip()) < 20:
                    print(f"[FAIL] required section '{section}': body is {len(match.group(1).strip())} chars (<20) — empty or minimal")
                    text_subst["failed"] += 1
                else:
                    print(f"[PASS] required section '{section}': body is {len(match.group(1).strip()):,} chars")
                    text_subst["passed"] += 1

text_checks_run = text_subst["passed"] + text_subst["warning"] + text_subst["failed"]
if text_subst["failed"] > 0 or text_subst["not_verified"] > 0 or text_checks_run == 0:
    text_verdict = "FAILED"
elif text_subst["warning"] > 0:
    text_verdict = "PASSED WITH WARNINGS"
else:
    text_verdict = "PASSED"

print(f"\nChecks: {text_subst['passed']} passed, {text_subst['warning']} warnings, {text_subst['failed']} failed, {text_subst['not_verified']} not verified, {text_subst['skipped']} skipped")
print(f"TEXT SUBSTANTIVENESS: {text_verdict}")
print("=" * 60)
# Advisory block: no raise.
```

#### Code Substantiveness Check

> *Language note: this is verifier tooling that scans script text, not pipeline code — it may run in Python even on R projects. It dispatches its pattern set on the file suffix.*

```python
import re
from pathlib import Path

# --- Substantiveness Validation: Code ---
# INTENT: Detect stub function bodies and not-implemented markers in a script.
# REASONING: The Python pattern set cannot see an R stub, so the language is
# resolved from the file suffix and an unrecognized suffix reports NOT VERIFIED
# rather than scanning with the wrong patterns and printing a vacuous PASS.
# ASSUMES: file_path points at the script; not_applicable configured above.
print("\n" + "=" * 60)
print(f"CODE SUBSTANTIVENESS CHECK: {file_path}")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

code_subst = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

python_patterns = [
    (r'def\s+\w+\([^)]*\):\s*\n\s+pass\s*$', "Empty function (pass)"),
    (r'def\s+\w+\([^)]*\):\s*\n\s+\.\.\.\s*$', "Empty function (...)"),
    (r'raise\s+NotImplementedError', "NotImplementedError"),
    (r'return\s+None\s*#.*TODO', "return None with TODO"),
    (r'return\s+\{\}\s*#.*TODO', "return {} with TODO"),
    (r'return\s+\[\]\s*#.*TODO', "return [] with TODO"),
]

r_patterns = [
    (r'function\s*\([^)]*\)\s*\{\s*\}', "Empty function body"),
    (r'function\s*\([^)]*\)\s*NULL\s*$', "Function returning bare NULL"),
    (r'stop\s*\(\s*["\'][^"\']*not implemented', "stop(\"not implemented\")"),
    (r'\.NotYetImplemented|NotYetImplemented\s*\(', "NotYetImplemented marker"),
    (r'return\s*\(\s*NULL\s*\)\s*#.*TODO', "return(NULL) with TODO"),
    (r'return\s*\(\s*data\.frame\s*\(\s*\)\s*\)', "return(data.frame()) — empty frame"),
]

suffix = Path(file_path).suffix.lower()
if not Path(file_path).exists():
    print(f"[NOT VERIFIED] code substantiveness: {file_path} does not exist — nothing scanned")
    code_subst["not_verified"] += 1
elif "stub_patterns" in not_applicable:
    print(f"[SKIPPED] code stub patterns: {not_applicable['stub_patterns']}")
    code_subst["skipped"] += 1
elif suffix not in (".py", ".r"):
    print(f"[NOT VERIFIED] code substantiveness: suffix '{suffix}' is neither .py nor .R — no stub pattern set applies, so nothing was scanned")
    code_subst["not_verified"] += 1
else:
    content = Path(file_path).read_text()
    if len(content.strip()) == 0:
        print(f"[FAIL] code substantiveness: {file_path} is empty ({len(content)} bytes) — no implementation present")
        code_subst["failed"] += 1
    else:
        code_patterns = python_patterns if suffix == ".py" else r_patterns
        language = "Python" if suffix == ".py" else "R"
        hits = []
        for pattern, description in code_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            if len(matches) > 0:
                hits.append(f"{description} x{len(matches)}")
        if len(hits) > 0:
            print(f"[FAIL] code stub patterns ({language}): {len(hits)} of {len(code_patterns)} patterns matched in {len(content):,} chars ({'; '.join(hits)})")
            code_subst["failed"] += 1
        else:
            print(f"[PASS] code stub patterns ({language}): 0 of {len(code_patterns)} patterns matched in {len(content):,} chars")
            code_subst["passed"] += 1

code_checks_run = code_subst["passed"] + code_subst["warning"] + code_subst["failed"]
if code_subst["failed"] > 0 or code_subst["not_verified"] > 0 or code_checks_run == 0:
    code_verdict = "FAILED"
elif code_subst["warning"] > 0:
    code_verdict = "PASSED WITH WARNINGS"
else:
    code_verdict = "PASSED"

print(f"\nChecks: {code_subst['passed']} passed, {code_subst['warning']} warnings, {code_subst['failed']} failed, {code_subst['not_verified']} not verified, {code_subst['skipped']} skipped")
print(f"CODE SUBSTANTIVENESS: {code_verdict}")
print("=" * 60)
# Advisory block: no raise.
```

### Usage in Final Review

Run each substantiveness block inline within the appropriate script. Set variables before each block:

```python
# For data substantiveness:
# df = <analysis DataFrame>
key_columns = ["enrollment", "poverty_rate", "student_teacher_ratio"]
context = "Final analysis dataset"
not_applicable = {}  # e.g. {"round_numbers": "enrollment is officially reported rounded to the nearest 10"}

# For text substantiveness:
# file_path = Path("research/project/Report.md")
required_sections = ["Executive Summary", "Findings", "Limitations"]
not_applicable = {}

# For code substantiveness:
# file_path = Path("research/project/analysis.py")   # or .R — the pattern set follows the suffix
not_applicable = {}
```

**`not_applicable` keys recognized by the substantiveness blocks:**

| Block | Key | Suppresses |
|-------|-----|-----------|
| Data | `all_null` | The entirely-null column check |
| Data | `single_value` | The single-distinct-value check |
| Data | `all_zeros` | The all-zeros check |
| Data | `round_numbers` | The multiples-of-1000 rate check |
| Text | `stub_patterns` | TODO/FIXME/PLACEHOLDER scanning |
| Text | `empty_sections` | The heading-with-no-body check |
| Text | `required_sections` | Presence and length of the Plan's required sections |
| Code | `stub_patterns` | Stub-body scanning for the resolved language |

**Semantics reminders:**
- **These blocks are advisory: they never raise or `stop()`.** A `FAILED` verdict is a finding for data-verifier (Stage 12) or code-reviewer (QA4b) to act on — the script continues either way. Any agent that runs a substantiveness block must read its verdict and report it; nothing else will.
- An empty `key_columns`, an absent column, or a file that does not exist reports `[NOT VERIFIED]`, which makes the verdict `FAILED`. "Nothing was inspected" never reads as "no issues found".
- **Applicability is resolved once per check, not once per column.** The data block emits a single `[SKIPPED] all-null: <reason>` before the per-column loop and then omits that sub-check for every column. Declaring `single_value` on a 40-column frame used to print 40 identical `[SKIPPED]` lines and inflate the skipped count 40x; the decision is about the check, so it is counted once.
- **Small frames warn, they do not fail.** A frame with 1-10 rows emits one `[WARNING] frame size: N rows` and the per-column checks still run; a column with 1-10 non-null values emits `[WARNING] round-numbers` rather than `[NOT VERIFIED]`. Only `n_rows == 0` is `[FAIL]`. Previously a legitimately small frame produced `[NOT VERIFIED]` lines and therefore a `FAILED` verdict, which trained readers to ignore the verdict.
- The per-column `[SKIPPED] numeric checks '<col>'` line is the one skip that *is* per column, because non-numeric dtype is a property of the column rather than a declaration about the check.
- The code check resolves its pattern set from the file suffix: `.py` uses the Python patterns, `.R`/`.r` uses the R patterns, and anything else is `[NOT VERIFIED]`. The previous Python-only pattern list silently passed every R script it was pointed at.
- `NUMERIC_DTYPES` in the data block is the same list as CP2's — an Int8 or UInt32 column is inspected in both, not exempted in one.
- `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`**.

---

## Validation Approach

> **Note:** Validation code is embedded inline within each script. No separate `validation.py` module is needed. Each script's execution log captures the validation output as part of the audit trail.

**Project Structure:**
```
research/YYYY-MM-DD_[Title]/
├── YYYY-MM-DD_[Title]_Plan.md
├── YYYY-MM-DD_[Title].py     # Marimo notebook (Python)
├── YYYY-MM-DD_[Title].qmd    # Quarto notebook (R)
├── scripts/                   # Scripts with inline validation
│   ├── stage5_fetch/
│   ├── stage6_clean/
│   ├── stage7_transform/
│   └── stage8_analysis/
├── data/
│   ├── raw/
│   └── processed/
└── output/
    ├── figures/
    └── preliminary_notes/
```

**Rationale:**
- Each script is self-contained with its own validation
- Validation output is captured in the script's execution log
- No import dependencies between scripts
- Thresholds are customized per script to match the Plan

---

## Stub Detection Patterns

**Purpose:** Identify incomplete implementations, placeholders, and patterns that indicate code is not production-ready. Stub detection is critical during Final Review (Stage 12) and should be run on all artifacts before delivery.

### Severity Levels

| Level | Name | Description | Action Required |
|-------|------|-------------|-----------------|
| **BLOCKER** | Critical stub | Prevents analysis from producing valid results | Must fix before delivery |
| **WARNING** | Incomplete indicator | Suggests work in progress; may affect quality | Document and assess impact |
| **INFO** | Notable pattern | Worth investigating but not necessarily problematic | Review during QA |

---

### Universal Stub Patterns

These patterns indicate incomplete work across any Python file.

#### Comment-Based Stubs (BLOCKER)

```python
# Patterns to detect
TODO_PATTERNS = [
    r'\bTODO\b',           # TODO marker
    r'\bFIXME\b',          # FIXME marker
    r'\bXXX\b',            # XXX marker
    r'\bHACK\b',           # HACK marker
    r'\bPLACEHOLDER\b',    # Explicit placeholder
]
```

**Severity:** BLOCKER if in core analysis code; WARNING if in comments explaining future work.

#### Placeholder Text (BLOCKER)

```python
PLACEHOLDER_PATTERNS = [
    r'placeholder',
    r'coming soon',
    r'will be (added|implemented|done)',
    r'not yet implemented',
    r'lorem ipsum',
    r'add more',
    r'\[TBD\]',
    r'\[description\]',
    r'\[your .* here\]',
]
```

---

### Python Function Stubs

These patterns indicate functions that exist but have no real implementation.

#### Empty Function Bodies (BLOCKER)

```python
# STUB EXAMPLES - These are RED FLAGS:

def analyze_data():
    pass

def transform_data():
    ...

def fetch_data():
    raise NotImplementedError

def process_records():
    raise NotImplementedError("Will implement later")

def calculate_metrics():
    return None  # Just returns None with no logic

def get_statistics():
    return {}    # Empty dict with no computation

def load_data():
    return []    # Empty list with no file read
```

#### Return Stubs with TODO Comments (BLOCKER)

```python
# RED FLAGS:
def get_enrollment():
    return None  # TODO: fetch from data access mirror

def calculate_rate():
    return 0.0  # FIXME: implement calculation

def fetch_schools():
    return []  # placeholder data
```

---

### Polars/Data Analysis Stubs

These patterns are specific to data science workflows using Polars.

#### Empty DataFrame Returns (BLOCKER)

```python
# RED FLAGS:
def load_data():
    return pl.DataFrame()  # Empty DataFrame with no logic

def transform_data(df):
    return pl.DataFrame({})  # Returns empty instead of transforming

# RED FLAG: Returns empty DataFrame with just schema
result = pl.DataFrame(schema=df.schema)  # Empty — this is a stub!
```

#### Hardcoded Sample Data Instead of Processing (WARNING/BLOCKER)

```python
# RED FLAGS - Hardcoded data instead of real processing:

def get_enrollment_data():
    # This should fetch from data access mirror but returns hardcoded values
    return pl.DataFrame({
        "school": ["School A", "School B"],
        "enrollment": [100, 200]
    })

def calculate_statistics(df):
    # Ignores input and returns fake stats
    return {"mean": 500, "median": 450}  # Magic numbers
```

#### Filter That Returns Input Unchanged (WARNING)

```python
# RED FLAG - Transform that does nothing:
def filter_active_schools(df):
    # Filter that passes everything through
    return df.filter(pl.lit(True))

def clean_data(df):
    # "Cleaning" that doesn't clean
    return df
```

#### Aggregations That Don't Aggregate (BLOCKER)

```python
# RED FLAGS:
def calculate_totals(df):
    # Group by but no aggregation
    return df.group_by("state")  # Missing .agg()

def summarize_enrollment(df):
    # Aggregation returns input column unchanged
    return df.group_by("state").agg(pl.col("enrollment"))  # No agg function applied
```

---

### Marimo Notebook Stubs

These patterns are specific to marimo reactive notebooks.

#### Cells With Only Comments (WARNING)

```python
# RED FLAG - Cell that does nothing:
@app.cell
def _():
    # This will be implemented
    pass

@app.cell
def _():
    # TODO: add visualization
    ...
```

#### Cells Returning Hardcoded Strings (WARNING)

```python
# RED FLAG - Placeholder output:
@app.cell
def _():
    return mo.md("# Analysis Coming Soon")

@app.cell
def _():
    return mo.md("TODO: Add findings here")
```

#### Placeholder Markdown Cells (WARNING)

```python
# RED FLAGS:
mo.md("""
## Findings

[Add findings here]

## Methodology

TBD
""")
```

#### Import Cells With No Usage (INFO)

```python
# REVIEW - Imports that may be unused:
@app.cell
def _():
    import plotly.express as px  # Never used in notebook
    import seaborn as sns        # Never used
```

---

### Quarto Notebook Stubs

These patterns are specific to Quarto (`.qmd`) notebooks used in R pipelines.

#### Chunks With Only Comments (WARNING)

````markdown
```{r}
#| label: analysis
#| eval: false

# TODO: add analysis code
```

```{r}
#| label: visualization

# This will be implemented later
```
````

#### Placeholder Markdown Sections (WARNING)

```markdown
## Findings

[Add findings here]

## Methodology

TBD
```

#### Chunks Returning Hardcoded Strings (WARNING)

````markdown
```{r}
#| label: summary

cat("Analysis Coming Soon")
```

```{r}
#| label: results

# TODO: Add findings here
cat("Results pending")
```
````

#### Library Calls With No Usage (INFO)

````markdown
```{r}
#| label: setup

library(sf)          # Never used in notebook
library(tidymodels)  # Never used
```
````

---

### Wiring Red Flags

These patterns indicate data/artifacts exist but aren't properly connected.

#### Data Loaded But Not Used in Analysis (BLOCKER)

```python
# RED FLAG - Load but never use:
df = pl.read_parquet("data/raw/schools.parquet")
# ... df never used again in analysis
# Report references different dataset

# Or loaded but only displayed, never analyzed:
df = pl.read_parquet("data/raw/schools.parquet")
print(df.head())  # Only inspection, no actual analysis
```

#### Transformations Exist But Output Not Saved (BLOCKER)

```python
# RED FLAG - Transform without saving:
clean_df = df.filter(pl.col("enrollment") > 0).with_columns(...)
# clean_df never written to data/processed/
# Notebook just displays but doesn't persist

# Analysis done but results not captured:
summary = df.group_by("state").agg(pl.col("enrollment").mean())
# summary not used in report, not saved
```

#### Figures Created But Not Referenced in Report (WARNING)

```python
# RED FLAG - Figure generated but not in report:
fig = px.scatter(df, x="poverty_rate", y="enrollment")
fig.write_html("output/figures/scatter.html")  # kaleido/write_image not available in DAAF
# Report.md doesn't reference scatter.png
```

#### Data Access Response Not Integrated (BLOCKER)

```python
# RED FLAG - Fetch but don't use result:
df = fetch_from_mirrors(dataset_paths=DATASET_PATHS, years=YEARS)
# df never written to parquet, never validated, never used downstream

# Or partial integration:
fetch_from_mirrors(dataset_paths=DATASET_PATHS, years=YEARS)
# Return value never assigned to a variable
```

---

### Validation Integrity Anti-Patterns

These patterns indicate a checkpoint that reports a verdict without actually testing anything.

#### Hard-Coded PASS Verdicts (BLOCKER)

**Doctrine — derive, never assert.** Every PASS/FAIL must be *computed* from observed values (an `assert`/comparison in Python, `stopifnot()`/comparison in R), never asserted by construction. A validation that prints `[PASS]` (or sets a pass flag) unconditionally cannot ever fail — and a checkpoint that cannot fail is not a checkpoint. It is a stub of a checkpoint: it puts a green mark in the audit trail while verifying nothing. (QA-reviewer-facing counterpart: `QA_CHECKPOINTS.md` § Anti-Patterns, "DO NOT issue PASSED without articulating WHY.")

```python
# RED FLAG - PASS asserted by construction; this line runs no matter what the data says:
print("[PASS] Row count check")   # No comparison — prints PASS unconditionally
passed = True                      # Flag set without deriving it from anything

# CORRECT - verdict derived from a runtime comparison of observed vs. expected:
actual = df.height
assert actual == expected_rows, f"[FAIL] Row count: expected {expected_rows}, got {actual}"
print(f"[PASS] Row count check: {actual} == {expected_rows}")
```

```r
# RED FLAG - PASS asserted by construction; cannot fail regardless of the data:
cat("[PASS] Row count check\n")   # No comparison — prints PASS unconditionally
passed <- TRUE                     # Flag set without deriving it from anything

# CORRECT - verdict derived from a runtime comparison of observed vs. expected:
actual <- nrow(df)
stopifnot(actual == expected_rows)
cat(sprintf("[PASS] Row count check: %d == %d\n", actual, expected_rows))
```

#### Evidence-Free PASS (BLOCKER)

**Doctrine — a PASS carries its numbers.** A `[PASS]` line that names no observed value is indistinguishable from a hard-coded one at read time, and it is what let a 75%-suppressed column report `[PASS] enrollment: 0.0% suppressed`. Every PASS states what was measured, against what, and how many rows or values it saw. A reviewer must be able to falsify the claim from the line alone.

```python
# RED FLAG - PASS with no observable: nothing in this line can be checked or falsified.
print("[PASS] No coded values remain in key variables")
print(f"[PASS] {var}: {supp_rate:.1%} suppressed")   # rate computed from a null sentinel: always 0.0%

# CORRECT - the line carries the numerator, the denominator, and the comparison basis:
print(f"[PASS] coded values '{var}': 0 of {len(clean_df):,} values match {CODED_MISSING_VALUES}")
print(f"[PASS] suppression '{var}': {supp_rate:.1%} (n={suppressed:,}/{raw_rows:,} sentinel {SUPPRESSION_CODE}) below {max_suppression:.0%} threshold")
```

```r
# RED FLAG - PASS with no observable:
cat("[PASS] No coded values remain in key variables\n")

# CORRECT:
cat(sprintf("[PASS] coded values '%s': 0 of %s values match (%s)\n", var,
            format(nrow(clean_df), big.mark = ","), paste(CODED_MISSING_VALUES, collapse = ", ")))
```

**Reviewer test:** delete the data and re-read the line. If it would print the same words, it is evidence-free.

---

#### Silent Skip (BLOCKER)

**Doctrine — a check that did not run must say so, and must not pass.** The most dangerous defect is not a wrong verdict but an absent one: a `continue` on a missing column, an `if config:` guard that never fires, an empty loop, a `None` sentinel that makes a counter zero. The block prints nothing, the checkpoint prints `PASSED`, and the audit trail records a gate that never gated.

```python
# RED FLAG - three silent skips, each of which lets the verdict read PASSED:
for col in required_cols:
    if col in df.columns:          # absent column: no line, no failure
        ...
if year_col and expected_years:    # None/empty config: whole check vanishes
    ...
suppressed = (raw[var] == CODE).sum() if CODE is not None else 0   # no sentinel -> 0 -> "0.0% PASS"

# CORRECT - every path emits exactly one token line and increments one counter:
for col in required_cols:
    if col not in df.columns:
        print(f"[FAIL] missingness '{col}': column absent from the frame — missingness untestable")
        cp1["failed"] += 1
        continue
    ...
if year_col is None or expected_years is None or len(expected_years) == 0:
    print("[NOT VERIFIED] year coverage: year_col or expected_years not configured")
    cp1["not_verified"] += 1
```

```r
# RED FLAG - `next` without a line, and a truthiness guard on config:
for (col in required_cols) { if (col %in% names(df)) { ... } }

# CORRECT - name what is missing, count it, and let the verdict inherit it:
for (col in required_cols) {
  if (!col %in% names(df)) {
    cat(sprintf("[FAIL] missingness '%s': column absent from the frame — missingness untestable\n", col))
    cp1["failed"] <- cp1["failed"] + 1L
    next
  }
  ...
}
```

**The rule that closes the loophole:** `[NOT VERIFIED] > 0` forces the verdict to `FAILED`, and a checkpoint where zero checks ran is `FAILED` rather than `PASSED`. A skip that is genuinely legitimate is declared in `not_applicable` with a reason and prints `[SKIPPED] <check>: <reason>` — visible, counted, and attributable. An undeclared skip is a defect, not a pass. (See § Per-Check Outcome Vocabulary and § Count Line and Verdict Line.)

---

### Python Stub Detection (Inline)

Use this sequential inline code within a Final Review script to detect stubs across project files:

```python
import re
from pathlib import Path

# --- Stub Detection: Project Scan ---
# INTENT: Scan every project .py/.md file for stub and placeholder markers.
# REASONING: This block used a boolean `stub_passed` with no count line, so a scan
# that read zero files printed "STUB DETECTION: PASSED" — a pass over nothing. It
# now uses the same counter / token / count-line / derived-verdict shape as the
# substantiveness blocks, so "no files scanned" is [NOT VERIFIED], not PASSED.
# ADVISORY: like the substantiveness blocks, this never raises. The verdict is
# evidence for data-verifier (Stage 12) or code-reviewer (QA4b) to act on.
# NO not_applicable PATH: this block carries exactly ONE check, so declaring it
# not applicable would leave zero checks run — which the shared verdict rule
# turns into FAILED anyway, after printing a reassuring [SKIPPED] line. The scan
# always runs. `skipped` stays in the counter so the count line keeps the same
# shape as every other block, but nothing here can increment it.
# ASSUMES: project_dir is a Path.
print("\n" + "=" * 60)
print(f"STUB DETECTION: {project_dir}")
print("=" * 60)

stubv = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Patterns to scan for
FAIL_PATTERNS = [
    (r'\bTODO\b', "TODO marker"),
    (r'\bFIXME\b', "FIXME marker"),
    (r'\bXXX\b', "XXX marker"),
    (r'\bHACK\b', "HACK marker"),
    (r'\bPLACEHOLDER\b', "PLACEHOLDER marker"),
    (r'raise\s+NotImplementedError', "NotImplementedError"),
    (r'\bplaceholder\b', "Placeholder text"),
    (r'coming soon', "Coming soon text"),
    (r'\[TBD\]', "TBD marker"),
    (r'\[add more\]', "Add more placeholder"),
    (r'\[your .* here\]', "Template placeholder"),
    (r'return pl\.DataFrame\(\)', "Empty DataFrame return"),
]

WARNING_PATTERNS = [
    (r'mo\.md\([^)]*TODO', "Marimo TODO in markdown"),
    (r'mo\.md\([^)]*Coming Soon', "Marimo Coming Soon text"),
]

if project_dir is None or not Path(project_dir).is_dir():
    print(f"[NOT VERIFIED] stub scan: project_dir {project_dir!r} is not a directory — nothing scanned")
    stubv["not_verified"] += 1
else:
    scanned_files = []
    for pattern_glob in ["*.py", "*.md"]:
        for file_path in sorted(Path(project_dir).rglob(pattern_glob)):
            if any(part.startswith('.') for part in file_path.parts):
                continue
            scanned_files.append(file_path)

    if len(scanned_files) == 0:
        print(f"[NOT VERIFIED] stub scan: 0 .py/.md files found under {project_dir} — an empty scan is not a clean scan")
        stubv["not_verified"] += 1
    else:
        hit_count = 0
        for file_path in scanned_files:
            content = file_path.read_text()

            for pattern, description in FAIL_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    print(f"[FAIL] {file_path.relative_to(project_dir)}: {description} ({len(matches)}x)")
                    stubv["failed"] += 1
                    hit_count += len(matches)

            for pattern, description in WARNING_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    print(f"[WARNING] {file_path.relative_to(project_dir)}: {description} ({len(matches)}x)")
                    stubv["warning"] += 1
                    hit_count += len(matches)

        # The clean case still needs a line that carries its evidence, or the
        # count line would read "0 passed" and the verdict would be FAILED.
        if hit_count == 0:
            print(f"[PASS] stub scan: 0 matches for {len(FAIL_PATTERNS)} stub and {len(WARNING_PATTERNS)} warning patterns across {len(scanned_files)} .py/.md files")
            stubv["passed"] += 1

# Count line, then verdict derived from the counts
stub_checks_run = stubv["passed"] + stubv["warning"] + stubv["failed"]
if stubv["failed"] > 0 or stubv["not_verified"] > 0 or stub_checks_run == 0:
    stub_verdict = "FAILED"
elif stubv["warning"] > 0:
    stub_verdict = "PASSED WITH WARNINGS"
else:
    stub_verdict = "PASSED"

print(f"\nChecks: {stubv['passed']} passed, {stubv['warning']} warnings, {stubv['failed']} failed, {stubv['not_verified']} not verified, {stubv['skipped']} skipped")
print(f"STUB DETECTION: {stub_verdict}")
print("=" * 60)
# Advisory block: no raise. A FAILED verdict is evidence for the reviewer.
```

### R/Quarto Stub Detection (Inline)

Use this sequential inline code within a Final Review script to detect stubs across R project files:

```r
# --- Stub Detection: Project Scan ---
# INTENT: Scan every project .R/.qmd/.md file for stub and placeholder markers.
# REASONING: Same repair as the Python block — a boolean accumulator with no count
# line reported PASSED for a scan that read zero files. Counter, tokens, count
# line, and derived verdict now match the substantiveness blocks.
# ADVISORY: never calls stop(). The verdict is evidence for the reviewer.
# NO not_applicable PATH: one check means declaring it not applicable leaves zero
# checks run, which is FAILED regardless — so the scan always runs. `skipped`
# stays in the counter only to keep the count line's shape.
# ASSUMES: project_dir is a directory path.
cat("============================================================\n")
cat(sprintf("STUB DETECTION: %s\n", project_dir))
cat("============================================================\n")

stubv <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# Patterns to scan for
FAIL_PATTERNS <- list(
    list("\\bTODO\\b", "TODO marker"),
    list("\\bFIXME\\b", "FIXME marker"),
    list("\\bXXX\\b", "XXX marker"),
    list("\\bHACK\\b", "HACK marker"),
    list("\\bPLACEHOLDER\\b", "PLACEHOLDER marker"),
    list("stop\\(", "stop() — potential NotImplementedError equivalent"),
    list("\\bplaceholder\\b", "Placeholder text"),
    list("coming soon", "Coming soon text"),
    list("\\[TBD\\]", "TBD marker"),
    list("\\[add more\\]", "Add more placeholder"),
    list("\\[your .* here\\]", "Template placeholder")
)

WARNING_PATTERNS <- list(
    list("cat\\(.*TODO", "R TODO in output"),
    list("cat\\(.*Coming Soon", "R Coming Soon text"),
    list("#\\| eval:\\s*false", "Quarto chunk with eval: false")
)

if (is.null(project_dir) || length(project_dir) != 1 || !dir.exists(project_dir)) {
    cat("[NOT VERIFIED] stub scan: project_dir is not an existing directory — nothing scanned\n")
    stubv["not_verified"] <- stubv["not_verified"] + 1L
} else {
    scan_files <- sort(c(
        list.files(project_dir, pattern = "\\.R$", recursive = TRUE, full.names = TRUE),
        list.files(project_dir, pattern = "\\.qmd$", recursive = TRUE, full.names = TRUE),
        list.files(project_dir, pattern = "\\.md$", recursive = TRUE, full.names = TRUE)
    ))
    scan_files <- scan_files[!grepl("/\\.", scan_files)]

    if (length(scan_files) == 0) {
        cat(sprintf("[NOT VERIFIED] stub scan: 0 .R/.qmd/.md files found under %s — an empty scan is not a clean scan\n",
                    project_dir))
        stubv["not_verified"] <- stubv["not_verified"] + 1L
    } else {
        hit_count <- 0L
        for (fp in scan_files) {
            content <- readLines(fp, warn = FALSE)
            content_text <- paste(content, collapse = "\n")
            rel_path <- sub(paste0("^", project_dir, "/?"), "", fp)

            for (pat in FAIL_PATTERNS) {
                matches <- gregexpr(pat[[1]], content_text, ignore.case = TRUE, perl = TRUE)
                n <- sum(matches[[1]] > 0)
                if (n > 0) {
                    cat(sprintf("[FAIL] %s: %s (%dx)\n", rel_path, pat[[2]], n))
                    stubv["failed"] <- stubv["failed"] + 1L
                    hit_count <- hit_count + n
                }
            }

            for (pat in WARNING_PATTERNS) {
                matches <- gregexpr(pat[[1]], content_text, ignore.case = TRUE, perl = TRUE)
                n <- sum(matches[[1]] > 0)
                if (n > 0) {
                    cat(sprintf("[WARNING] %s: %s (%dx)\n", rel_path, pat[[2]], n))
                    stubv["warning"] <- stubv["warning"] + 1L
                    hit_count <- hit_count + n
                }
            }
        }

        if (hit_count == 0) {
            cat(sprintf("[PASS] stub scan: 0 matches for %d stub and %d warning patterns across %d .R/.qmd/.md files\n",
                        length(FAIL_PATTERNS), length(WARNING_PATTERNS), length(scan_files)))
            stubv["passed"] <- stubv["passed"] + 1L
        }
    }
}

# Count line, then verdict derived from the counts
stub_checks_run <- stubv[["passed"]] + stubv[["warning"]] + stubv[["failed"]]
if (stubv[["failed"]] > 0 || stubv[["not_verified"]] > 0 || stub_checks_run == 0) {
    stub_verdict <- "FAILED"
} else if (stubv[["warning"]] > 0) {
    stub_verdict <- "PASSED WITH WARNINGS"
} else {
    stub_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            stubv[["passed"]], stubv[["warning"]], stubv[["failed"]], stubv[["not_verified"]], stubv[["skipped"]]))
cat(sprintf("STUB DETECTION: %s\n", stub_verdict))
cat("============================================================\n")
# Advisory block: no stop(). A FAILED verdict is evidence for the reviewer.
```

#### Wiring Check (Inline)

> *Language note: this is verifier tooling that scans file references across artifacts, not pipeline code — it may run in Python even on R projects.*

```python
import re
from pathlib import Path

# --- Wiring Check ---
# INTENT: Confirm the notebook's data actually flows — loads are used,
# transformations reach a save, and saved figures are cited in the Report.
# REASONING: The old block printed "[PASS] {transforms} transforms, {saves} saves"
# for 0 transforms and 0 saves, i.e. a notebook that does no data work at all read
# as PASSED; and a missing report silently skipped check 3 with no line at all.
# Both are now explicit outcomes with counts.
# ADVISORY: never raises. The verdict is evidence for the reviewer.
# ASSUMES: project_dir (printed in the banner) / notebook_path / report_path /
# not_applicable are configured above.
print("\n" + "=" * 60)
print(f"WIRING CHECK: {project_dir}")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

wiring = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

notebook_content = None
if notebook_path is None or not Path(notebook_path).exists():
    print(f"[NOT VERIFIED] notebook: {notebook_path!r} does not exist — no artifact to trace wiring through")
    wiring["not_verified"] += 1
else:
    notebook_content = Path(notebook_path).read_text()

# Check 1: Data loaded is used
if "data_usage" in not_applicable:
    print(f"[SKIPPED] data usage: {not_applicable['data_usage']}")
    wiring["skipped"] += 1
elif notebook_content is None:
    print("[NOT VERIFIED] data usage: the notebook was not read — load sites unknown")
    wiring["not_verified"] += 1
else:
    data_loads = re.findall(r'(\w+)\s*=\s*pl\.(read_parquet|read_csv)\(["\']([^"\']+)', notebook_content)
    if len(data_loads) == 0:
        print(f"[NOT VERIFIED] data usage: no `<var> = pl.read_parquet/read_csv(...)` load site found in {notebook_path} — either the notebook loads nothing or it loads by a pattern this scan does not model")
        wiring["not_verified"] += 1
    else:
        for var_name, method, path in data_loads:
            uses = len(re.findall(rf'\b{var_name}\b', notebook_content)) - 1
            # REASONING: the question this check answers is "was the loaded frame
            # used at all", so the only defensible failure is ZERO downstream
            # references — a dead load. Requiring two references failed the most
            # idiomatic shape there is (`df = pl.read_parquet(...)` followed by
            # `out = df.filter(...)`, which transforms into a new name and never
            # mentions `df` again), producing a guaranteed false [FAIL] on clean
            # notebooks. The count is named either way so the reader can judge.
            if uses == 0:
                print(f"[FAIL] data usage '{var_name}': loaded from {path} via {method} but never referenced again — the load is dead")
                wiring["failed"] += 1
            else:
                print(f"[PASS] data usage '{var_name}': loaded from {path} via {method} and referenced {uses} time(s) after the load")
                wiring["passed"] += 1

# Check 2: Transformations produce saved output
if "transform_saves" in not_applicable:
    print(f"[SKIPPED] transform saves: {not_applicable['transform_saves']}")
    wiring["skipped"] += 1
elif notebook_content is None:
    print("[NOT VERIFIED] transform saves: the notebook was not read — transformation and save counts unknown")
    wiring["not_verified"] += 1
else:
    transforms = len(re.findall(r'\.(filter|with_columns|group_by|join)\(', notebook_content))
    saves = len(re.findall(r'\.(write_parquet|write_csv)\(', notebook_content))
    if transforms == 0 and saves == 0:
        print(f"[FAIL] transform saves: 0 transformations and 0 saves in {notebook_path} — the notebook performs no data work, which is not a passing wiring state")
        wiring["failed"] += 1
    elif transforms > 0 and saves == 0:
        print(f"[FAIL] transform saves: {transforms} transformations but 0 saves — the transformed frame never reaches disk")
        wiring["failed"] += 1
    elif transforms == 0 and saves > 0:
        print(f"[WARNING] transform saves: {saves} saves but 0 transformations detected — the notebook may be writing its input back out unchanged")
        wiring["warning"] += 1
    else:
        print(f"[PASS] transform saves: {transforms} transformations and {saves} saves")
        wiring["passed"] += 1

# Check 3: Figures referenced in report
if "figure_references" in not_applicable:
    print(f"[SKIPPED] figure references: {not_applicable['figure_references']}")
    wiring["skipped"] += 1
elif notebook_content is None:
    print("[NOT VERIFIED] figure references: the notebook was not read — figure save sites unknown")
    wiring["not_verified"] += 1
elif report_path is None or not Path(report_path).exists():
    print(f"[NOT VERIFIED] figure references: report_path {report_path!r} does not exist — nothing to check the figures against")
    wiring["not_verified"] += 1
else:
    report_content = Path(report_path).read_text()
    figures_saved = re.findall(r'(?:savefig|write_image|write_html)\(["\']([^"\']+)', notebook_content)
    if len(figures_saved) == 0:
        print(f"[NOT VERIFIED] figure references: no savefig/write_image/write_html call found in {notebook_path} — no figure to trace into the Report")
        wiring["not_verified"] += 1
    else:
        for fig_path_str in figures_saved:
            fig_name = Path(fig_path_str).name
            if fig_name not in report_content:
                print(f"[WARNING] figure references '{fig_name}': saved by the notebook but not named anywhere in {report_path}")
                wiring["warning"] += 1
            else:
                print(f"[PASS] figure references '{fig_name}': saved by the notebook and named in {report_path}")
                wiring["passed"] += 1

# Count line, then verdict derived from the counts
wiring_checks_run = wiring["passed"] + wiring["warning"] + wiring["failed"]
if wiring["failed"] > 0 or wiring["not_verified"] > 0 or wiring_checks_run == 0:
    wiring_verdict = "FAILED"
elif wiring["warning"] > 0:
    wiring_verdict = "PASSED WITH WARNINGS"
else:
    wiring_verdict = "PASSED"

print(f"\nChecks: {wiring['passed']} passed, {wiring['warning']} warnings, {wiring['failed']} failed, {wiring['not_verified']} not verified, {wiring['skipped']} skipped")
print(f"WIRING CHECK: {wiring_verdict}")
print("=" * 60)
# Advisory block: no raise. A FAILED verdict is evidence for the reviewer.
```

### Usage in Final Review (Stage 12)

Run stub detection and wiring checks inline in a Final Review script. Set variables before each block:

```python
# Configure before stub detection
project_dir = Path("research/2026-01-24_School_Analysis/")
# Stub detection takes no `not_applicable` mapping — the scan always runs.

# Configure before wiring check
notebook_path = Path("research/2026-01-24_School_Analysis/2026-01-24_School_Analysis.py")
report_path = Path("research/2026-01-24_School_Analysis/2026-01-24_School_Analysis_Report.md")
not_applicable = {}  # e.g. {"figure_references": "this analysis produces tables only"}
```

The wiring check also reads `project_dir` — it prints it in the banner — so set it before both blocks.

**Verdict shape.** Both blocks follow the same contract as the substantiveness blocks: one outcome token per check, a `Checks: …` count line, and a verdict derived from the counters — `STUB DETECTION: PASSED | PASSED WITH WARNINGS | FAILED` and `WIRING CHECK: PASSED | PASSED WITH WARNINGS | FAILED`. Both are **advisory**: neither raises. A `FAILED` verdict is evidence for data-verifier (Stage 12) or code-reviewer (QA4b), and an agent that runs either block must read and report the verdict, because nothing in the pipeline halts on it.

**What changed and why.** Both blocks previously carried a boolean accumulator (`stub_passed`, `wiring_passed`), printed no count line, and derived the verdict from the boolean. Three evidence-free passes followed from that shape and are now explicit outcomes:

| Situation | Was | Now |
|---|---|---|
| Stub scan matched zero files (wrong `project_dir`, empty project) | `STUB DETECTION: PASSED` | `[NOT VERIFIED] stub scan: 0 .py/.md files found …` ⇒ `FAILED` |
| Notebook with 0 transformations and 0 saves | `[PASS] 0 transforms, 0 saves` | `[FAIL] transform saves: 0 transformations and 0 saves …` |
| No Report present for the figure cross-check | no line printed at all | `[NOT VERIFIED] figure references: report_path … does not exist` |
| Notebook loads a frame and transforms it once into a new name | `[FAIL] data usage … referenced only 1 time(s)` | `[PASS] data usage … referenced 1 time(s) after the load` |
| Stub detection declared `not_applicable` (its only check) | `[SKIPPED] stub scan: …` then `STUB DETECTION: FAILED` | no such path — the scan always runs |

**Stub detection has no `not_applicable` path.** The block carries exactly one check. Declaring it not applicable left zero checks run, which the shared verdict rule turns into `FAILED` anyway — so the reassuring `[SKIPPED]` line was followed by a failure it did not explain. The declaration and its branch are removed; the scan always runs. `skipped` remains in the counter purely so the `Checks: …` line keeps the same five fields as every other block, and stub detection can never increment it.

**`data usage` fails only on a dead load.** Zero downstream references to a loaded frame is `[FAIL]`; one or more is `[PASS]` naming the count. The earlier `uses < 2` rule failed the most common idiom in the framework's own examples — `df = pl.read_parquet(...)` followed by `out = df.filter(...)` — so a correct notebook could not pass. Whether one downstream use is *enough* analysis is a reviewer judgment the printed count supports; it is not a wiring defect.

`[BLOCKER]` is retired from both blocks. It is a review-severity token belonging to the QA family, and these blocks carry the CP-family counter (`passed`/`warning`/`failed`/`not_verified`/`skipped`); a fatal finding here is `[FAIL]`.

**`not_applicable` keys:** stub detection recognizes **none** (see above); the wiring check recognizes `data_usage`, `transform_saves`, and `figure_references`.

---

### Stub Detection Checklist for Final Review

Before delivery, verify all of the following pass:

| Check | Detection Method | Severity |
|-------|------------------|----------|
| No TODO/FIXME/XXX markers in code | `grep -rn "TODO\|FIXME\|XXX"` | BLOCKER |
| No NotImplementedError | `grep -rn "raise NotImplementedError"` | BLOCKER |
| No pass-only or ellipsis-only functions | Pattern match | BLOCKER |
| No placeholder text in markdown | `grep -ri "placeholder\|coming soon"` | BLOCKER |
| No empty DataFrame returns | `grep -rn "return pl.DataFrame()"` | BLOCKER |
| No unused imports | `grep` for imported names unused in file | WARNING |
| Data loaded is used in analysis | Wiring check | BLOCKER |
| Transformations produce saved output | Wiring check | BLOCKER |
| Figures are referenced in report | Wiring check | WARNING |
| Report has substantive content | Text substantiveness check | BLOCKER |

---

## Integration in Notebooks

> **Note:** Validation code is inline within each script, not imported from a module. The Marimo notebook assembles successful scripts verbatim. Validation output is captured in each script's execution log (appended as comments), which becomes part of the audit trail.

Validation results appear in the notebook as accordion sections containing the script's execution log. The notebook-assembler agent copies script content verbatim, including the inline validation blocks.

---

## Profiling Validation Checkpoints (CPP1-CPP4, CPP-SKILL)

> **Mode:** These checkpoints apply to Data Onboarding Mode only. They are the profiling equivalent of CP1-CP4.
>
> **This section is canonical.** The blocks below are the only maintained copies of the CPP code. `.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_PROFILING.md` tells the data-ingest agent *when* to embed each checkpoint and supplies the per-part `# --- Config ---` stanza, then points here for the block itself. Copy the block for the relevant checkpoint verbatim into the profiling script's `# --- Validate ---` section; do not paraphrase it and do not maintain a second copy elsewhere.

### CPP Overview

CPP checkpoints follow the same outcome vocabulary, count line, and verdict rules as CP1-CP4 (see § Per-Check Outcome Vocabulary, § Count Line and Verdict Line, § Applicability Configuration above). Each block prints `Checks: ...` then `CPP{n} VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`, and raises/stops on `FAILED` — but only after every check has reported, so the log records the complete picture rather than aborting at the first problem.

| Checkpoint | After Part | Purpose | FAILED when |
|------------|-----------|---------|-------------|
| CPP1 | A (Structural) | Data loads correctly | Zero rows, zero columns, >=50% null, encoding damage — or any input needed for those checks is missing |
| CPP2 | B (Statistical) | Stats are internally consistent | Mean outside [min,max], non-monotonic percentiles — or `numeric_columns` unset/empty, or a named column is absent or entirely null |
| CPP3 | C (Relational) | Relationships are coherent | Non-symmetric correlation, uniqueness disagreement, empty anomaly catalog — or the correlation matrix / key candidates / uniqueness results were not produced and not declared not-applicable |
| CPP4 | D (Interpretation) | Interpretations are disciplined | Any interpretation line unhedged, reconciliation promised but not run — or the interpretation records were not produced |
| CPP-SKILL | Skill Authoring | Skill template compliance | Missing required section or reference file, >500 lines, fewer than 2 decision trees, density below 3x — or a manual checklist item has no recorded determination |

**Why `[NOT VERIFIED]` matters here specifically.** Profiling checkpoints run over inputs that upstream scripts may or may not have produced (`correlation_matrix` exists only if script 08 ran; `reconciliation_ran` only if script 11 ran). Under the old two-state templates those absences fell through to a printed `CPP{n} PASSED` line. They now print `[NOT VERIFIED]` and fail the checkpoint, unless the orchestrator's documented skip decision is carried into `not_applicable` with its reason — which is exactly where the conditional-execution rationale from `WORKFLOW_PHASE_DO_PROFILING.md` § Conditional Execution Rules belongs.

### CPP1: Post-Load Validation

**Embedded in:** `scripts/profile_structural/01_load-and-format.py` (`.R` for R)

**Config stanza (assign before the block):**
```python
# --- Config ---
df = None                # set to the loaded frame; stays None if the load produced nothing
not_applicable = {}      # e.g. {"encoding": "parquet input — encoding was fixed at write time"}
```

```python
import polars as pl

# --- CPP1 Validation: Post-Load ---
# INTENT: Verify the canonical load produced a frame fit to profile — shape, overall
# null rate, entirely-null columns, row volume, and encoding damage.
# REASONING: Each check emits exactly one outcome token and increments exactly one
# counter, so the verdict is derived from what actually ran. A check that cannot run
# says so ([NOT VERIFIED]) and fails the checkpoint rather than passing silently.
# ASSUMES: df and not_applicable are assigned in this script's `# --- Config ---`
# region; df is None when the load produced no frame.
print("\n" + "=" * 60)
print("CPP1 VALIDATION: POST-LOAD")
print("=" * 60)

# INTENT: A declared skip without a reason is indistinguishable from a silent one.
not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cpp1 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Check: shape — the frame exists and has both rows and columns
if "shape" in not_applicable:
    print(f"[SKIPPED] shape: {not_applicable['shape']}")
    cpp1["skipped"] += 1
elif df is None:
    print("[NOT VERIFIED] shape: df is None — the canonical load produced no frame")
    cpp1["not_verified"] += 1
elif df.shape[0] == 0 or df.shape[1] == 0:
    print(f"[FAIL] shape: {df.shape[0]:,} rows x {df.shape[1]} cols — an empty frame cannot be profiled")
    cpp1["failed"] += 1
else:
    print(f"[PASS] shape: {df.shape[0]:,} rows x {df.shape[1]} cols loaded")
    cpp1["passed"] += 1

# Check: overall null rate across every cell
if "null_rate" in not_applicable:
    print(f"[SKIPPED] null rate: {not_applicable['null_rate']}")
    cpp1["skipped"] += 1
elif df is None or df.shape[0] == 0 or df.shape[1] == 0:
    print("[NOT VERIFIED] null rate: no non-empty frame — total cells is 0 and the rate is undefined")
    cpp1["not_verified"] += 1
else:
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = sum(df[c].null_count() for c in df.columns)
    null_rate = total_nulls / total_cells
    if null_rate >= 0.5:
        print(f"[FAIL] null rate: {null_rate:.1%} of cells null ({total_nulls:,}/{total_cells:,}, >=50% threshold)")
        cpp1["failed"] += 1
    else:
        print(f"[PASS] null rate: {null_rate:.1%} of cells null ({total_nulls:,}/{total_cells:,}, <50%)")
        cpp1["passed"] += 1

# Check: entirely null columns — a column with no data cannot be profiled downstream
if "all_null_columns" in not_applicable:
    print(f"[SKIPPED] all-null columns: {not_applicable['all_null_columns']}")
    cpp1["skipped"] += 1
elif df is None or df.shape[0] == 0 or df.shape[1] == 0:
    print("[NOT VERIFIED] all-null columns: no non-empty frame to scan")
    cpp1["not_verified"] += 1
else:
    all_null_cols = [c for c in df.columns if df[c].null_count() == df.shape[0]]
    if len(all_null_cols) > 0:
        print(f"[WARNING] all-null columns: {len(all_null_cols)} of {df.shape[1]} entirely null {all_null_cols} — these columns cannot be statistically profiled")
        cpp1["warning"] += 1
    else:
        print(f"[PASS] all-null columns: 0 of {df.shape[1]} columns entirely null")
        cpp1["passed"] += 1

# Check: row volume — a very small frame often means a partial or truncated file
if "row_volume" in not_applicable:
    print(f"[SKIPPED] row volume: {not_applicable['row_volume']}")
    cpp1["skipped"] += 1
elif df is None:
    print("[NOT VERIFIED] row volume: df is None — row count unavailable")
    cpp1["not_verified"] += 1
elif df.shape[0] < 100:
    print(f"[WARNING] row volume: {df.shape[0]:,} rows (<100) — confirm this is the complete file, not a sample or truncated read")
    cpp1["warning"] += 1
else:
    print(f"[PASS] row volume: {df.shape[0]:,} rows (>=100)")
    cpp1["passed"] += 1

# Check: encoding damage — U+FFFD replacement characters mean the decode was lossy
# REASONING: The CPP1 STOP condition names "encoding errors"; this makes that
# condition computable from the frame rather than asserted by the agent in prose.
if "encoding" in not_applicable:
    print(f"[SKIPPED] encoding: {not_applicable['encoding']}")
    cpp1["skipped"] += 1
elif df is None or df.shape[1] == 0:
    print("[NOT VERIFIED] encoding: no frame to scan for replacement characters")
    cpp1["not_verified"] += 1
else:
    text_cols = [c for c in df.columns if df.schema[c] == pl.Utf8]
    damaged = {}
    for c in text_cols:
        n_bad = int(df[c].str.contains("�", literal=True).sum() or 0)
        if n_bad > 0:
            damaged[c] = n_bad
    if len(damaged) > 0:
        print(f"[FAIL] encoding: U+FFFD replacement characters in {len(damaged)} of {len(text_cols)} text columns {damaged} — the decode was lossy, re-read with the correct encoding")
        cpp1["failed"] += 1
    else:
        print(f"[PASS] encoding: 0 U+FFFD replacement characters across {len(text_cols)} of {df.shape[1]} text columns")
        cpp1["passed"] += 1

# Count line, then verdict derived from the counts (never asserted)
cpp1_checks_run = cpp1["passed"] + cpp1["warning"] + cpp1["failed"]
if cpp1["failed"] > 0 or cpp1["not_verified"] > 0 or cpp1_checks_run == 0:
    cpp1_verdict = "FAILED"
elif cpp1["warning"] > 0:
    cpp1_verdict = "PASSED WITH WARNINGS"
else:
    cpp1_verdict = "PASSED"

print(f"\nChecks: {cpp1['passed']} passed, {cpp1['warning']} warnings, {cpp1['failed']} failed, {cpp1['not_verified']} not verified, {cpp1['skipped']} skipped")
print(f"CPP1 VALIDATION: {cpp1_verdict}")
print("=" * 60)

if cpp1_verdict == "FAILED":
    raise ValueError("CPP1 FAILED - see details above")
```

**R:**
```r
# --- CPP1 Validation: Post-Load ---
# INTENT: Verify the canonical load produced a frame fit to profile — shape, overall
# NA rate, entirely-NA columns, row volume, and encoding damage.
# REASONING: Each check emits exactly one outcome token and increments exactly one
# counter, so the verdict is derived from what actually ran.
# ASSUMES: df and not_applicable are assigned in this script's `# --- Config ---`
# region; df is NULL when the load produced no frame.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CPP1 VALIDATION: POST-LOAD\n")
cat(strrep("=", 60), "\n")

# INTENT: Drop declared-not-applicable entries that carry no reason.
na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cpp1 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# Check: shape — the frame exists and has both rows and columns
if ("shape" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] shape: %s\n", not_applicable[["shape"]]))
  cpp1["skipped"] <- cpp1["skipped"] + 1L
} else if (is.null(df)) {
  cat("[NOT VERIFIED] shape: df is NULL — the canonical load produced no frame\n")
  cpp1["not_verified"] <- cpp1["not_verified"] + 1L
} else if (nrow(df) == 0 || ncol(df) == 0) {
  cat(sprintf("[FAIL] shape: %s rows x %d cols — an empty frame cannot be profiled\n",
              format(nrow(df), big.mark = ","), ncol(df)))
  cpp1["failed"] <- cpp1["failed"] + 1L
} else {
  cat(sprintf("[PASS] shape: %s rows x %d cols loaded\n",
              format(nrow(df), big.mark = ","), ncol(df)))
  cpp1["passed"] <- cpp1["passed"] + 1L
}

# Check: overall NA rate across every cell
if ("null_rate" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] null rate: %s\n", not_applicable[["null_rate"]]))
  cpp1["skipped"] <- cpp1["skipped"] + 1L
} else if (is.null(df) || nrow(df) == 0 || ncol(df) == 0) {
  cat("[NOT VERIFIED] null rate: no non-empty frame — total cells is 0 and the rate is undefined\n")
  cpp1["not_verified"] <- cpp1["not_verified"] + 1L
} else {
  total_cells <- nrow(df) * ncol(df)
  total_nulls <- sum(vapply(df, function(x) sum(is.na(x)), numeric(1)))
  null_rate <- total_nulls / total_cells
  if (null_rate >= 0.5) {
    cat(sprintf("[FAIL] null rate: %.1f%% of cells NA (%s/%s, >=50%% threshold)\n",
                null_rate * 100, format(total_nulls, big.mark = ","), format(total_cells, big.mark = ",")))
    cpp1["failed"] <- cpp1["failed"] + 1L
  } else {
    cat(sprintf("[PASS] null rate: %.1f%% of cells NA (%s/%s, <50%%)\n",
                null_rate * 100, format(total_nulls, big.mark = ","), format(total_cells, big.mark = ",")))
    cpp1["passed"] <- cpp1["passed"] + 1L
  }
}

# Check: entirely NA columns
if ("all_null_columns" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] all-null columns: %s\n", not_applicable[["all_null_columns"]]))
  cpp1["skipped"] <- cpp1["skipped"] + 1L
} else if (is.null(df) || nrow(df) == 0 || ncol(df) == 0) {
  cat("[NOT VERIFIED] all-null columns: no non-empty frame to scan\n")
  cpp1["not_verified"] <- cpp1["not_verified"] + 1L
} else {
  all_null_cols <- names(df)[vapply(df, function(x) all(is.na(x)), logical(1))]
  if (length(all_null_cols) > 0) {
    cat(sprintf("[WARNING] all-null columns: %d of %d entirely NA (%s) — these columns cannot be statistically profiled\n",
                length(all_null_cols), ncol(df), paste(all_null_cols, collapse = ", ")))
    cpp1["warning"] <- cpp1["warning"] + 1L
  } else {
    cat(sprintf("[PASS] all-null columns: 0 of %d columns entirely NA\n", ncol(df)))
    cpp1["passed"] <- cpp1["passed"] + 1L
  }
}

# Check: row volume
if ("row_volume" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row volume: %s\n", not_applicable[["row_volume"]]))
  cpp1["skipped"] <- cpp1["skipped"] + 1L
} else if (is.null(df)) {
  cat("[NOT VERIFIED] row volume: df is NULL — row count unavailable\n")
  cpp1["not_verified"] <- cpp1["not_verified"] + 1L
} else if (nrow(df) < 100) {
  cat(sprintf("[WARNING] row volume: %s rows (<100) — confirm this is the complete file, not a sample or truncated read\n",
              format(nrow(df), big.mark = ",")))
  cpp1["warning"] <- cpp1["warning"] + 1L
} else {
  cat(sprintf("[PASS] row volume: %s rows (>=100)\n", format(nrow(df), big.mark = ",")))
  cpp1["passed"] <- cpp1["passed"] + 1L
}

# Check: encoding damage — U+FFFD replacement characters mean the decode was lossy
if ("encoding" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] encoding: %s\n", not_applicable[["encoding"]]))
  cpp1["skipped"] <- cpp1["skipped"] + 1L
} else if (is.null(df) || ncol(df) == 0) {
  cat("[NOT VERIFIED] encoding: no frame to scan for replacement characters\n")
  cpp1["not_verified"] <- cpp1["not_verified"] + 1L
} else {
  text_cols <- names(df)[vapply(df, is.character, logical(1))]
  damaged_names <- character(0)
  damaged_counts <- integer(0)
  for (col_name in text_cols) {
    n_bad <- sum(grepl("�", df[[col_name]], fixed = TRUE), na.rm = TRUE)
    if (n_bad > 0) {
      damaged_names <- c(damaged_names, col_name)
      damaged_counts <- c(damaged_counts, as.integer(n_bad))
    }
  }
  if (length(damaged_names) > 0) {
    cat(sprintf("[FAIL] encoding: U+FFFD replacement characters in %d of %d text columns (%s) — the decode was lossy, re-read with the correct encoding\n",
                length(damaged_names), length(text_cols),
                paste(sprintf("%s=%d", damaged_names, damaged_counts), collapse = ", ")))
    cpp1["failed"] <- cpp1["failed"] + 1L
  } else {
    cat(sprintf("[PASS] encoding: 0 U+FFFD replacement characters across %d of %d text columns\n",
                length(text_cols), ncol(df)))
    cpp1["passed"] <- cpp1["passed"] + 1L
  }
}

# Count line, then verdict derived from the counts (never asserted)
cpp1_checks_run <- cpp1[["passed"]] + cpp1[["warning"]] + cpp1[["failed"]]
if (cpp1[["failed"]] > 0 || cpp1[["not_verified"]] > 0 || cpp1_checks_run == 0) {
  cpp1_verdict <- "FAILED"
} else if (cpp1[["warning"]] > 0) {
  cpp1_verdict <- "PASSED WITH WARNINGS"
} else {
  cpp1_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cpp1[["passed"]], cpp1[["warning"]], cpp1[["failed"]], cpp1[["not_verified"]], cpp1[["skipped"]]))
cat(sprintf("CPP1 VALIDATION: %s\n", cpp1_verdict))
cat(strrep("=", 60), "\n")

if (cpp1_verdict == "FAILED") {
  stop("CPP1 FAILED - see details above")
}
```

**`not_applicable` keys recognized by CPP1:** `shape`, `null_rate`, `all_null_columns`, `row_volume`, `encoding`.

### CPP2: Post-Statistical Validation

**Embedded in:** Last script of Part B (04, 05, or 06 depending on conditional execution)

**Config stanza (assign before the block):**
```python
# --- Config ---
df = None                    # the frame profiled in Part B
numeric_columns = []         # numeric column names identified in Part A; [] means none were identified
temporal_expected = None     # True/False from the orchestrator's Part A determination; None if never made
time_columns_found = None    # True/False from script 05; None if script 05 did not run
not_applicable = {}          # e.g. {"temporal_detection": "script 05 skipped — no date/time/year columns in Part A"}
```

```python
# --- CPP2 Validation: Post-Statistical ---
# INTENT: Verify the numeric summaries Part B reported are internally consistent —
# mean inside [min, max], percentiles monotone — and that the temporal determination
# the orchestrator made in Part A is reflected in what script 05 found.
# REASONING: The old template looped over numeric_columns with bare asserts, so an
# empty list ran zero checks and still printed PASSED, and an all-null column raised
# a TypeError (Python) / compared NA in `if ()` (R) instead of reporting.
# ASSUMES: df / numeric_columns / temporal_expected / time_columns_found /
# not_applicable are assigned in this script's `# --- Config ---` region.
print("\n" + "=" * 60)
print("CPP2 VALIDATION: POST-STATISTICAL")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cpp2 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Check: mean lies inside [min, max] — one check per numeric column
print("\nNumeric summary consistency (per column):")
if "numeric_summaries" in not_applicable:
    print(f"[SKIPPED] numeric summaries: {not_applicable['numeric_summaries']}")
    cpp2["skipped"] += 1
elif df is None:
    print("[NOT VERIFIED] numeric summaries: df is None — no frame to summarize")
    cpp2["not_verified"] += 1
elif numeric_columns is None or len(numeric_columns) == 0:
    print("[NOT VERIFIED] numeric summaries: numeric_columns is empty — Part A identified no numeric columns to check; declare not_applicable['numeric_summaries'] if this dataset genuinely has none")
    cpp2["not_verified"] += 1
else:
    for col in numeric_columns:
        if col not in df.columns:
            print(f"[FAIL] numeric summary '{col}': column absent from the profiled frame")
            cpp2["failed"] += 1
        elif not df.schema[col].is_numeric():
            print(f"[FAIL] numeric summary '{col}': dtype is {df.schema[col]} — numeric_columns named a non-numeric column")
            cpp2["failed"] += 1
        elif df[col].null_count() == df.shape[0]:
            # REASONING: min/max/mean of an all-null column are None (Python) / Inf,
            # -Inf, NaN (R). Comparing them is not a check, it is an error.
            print(f"[NOT VERIFIED] numeric summary '{col}': entirely null over {df.shape[0]:,} rows — min/max/mean undefined")
            cpp2["not_verified"] += 1
        else:
            col_min = df[col].min()
            col_max = df[col].max()
            col_mean = df[col].mean()
            if col_min <= col_mean <= col_max:
                print(f"[PASS] numeric summary '{col}': mean {col_mean:.4g} within [{col_min:.4g}, {col_max:.4g}]")
                cpp2["passed"] += 1
            else:
                print(f"[FAIL] numeric summary '{col}': mean {col_mean:.4g} outside [{col_min:.4g}, {col_max:.4g}]")
                cpp2["failed"] += 1

# Check: percentile monotonicity — one check per numeric column
print("\nPercentile monotonicity (per column):")
if "percentile_monotonicity" in not_applicable:
    print(f"[SKIPPED] percentile monotonicity: {not_applicable['percentile_monotonicity']}")
    cpp2["skipped"] += 1
elif df is None:
    print("[NOT VERIFIED] percentile monotonicity: df is None — no frame to summarize")
    cpp2["not_verified"] += 1
elif numeric_columns is None or len(numeric_columns) == 0:
    print("[NOT VERIFIED] percentile monotonicity: numeric_columns is empty — no columns to check")
    cpp2["not_verified"] += 1
else:
    for col in numeric_columns:
        if col not in df.columns or not df.schema[col].is_numeric():
            print(f"[FAIL] percentiles '{col}': column absent or non-numeric — percentiles untestable")
            cpp2["failed"] += 1
        elif df[col].null_count() == df.shape[0]:
            print(f"[NOT VERIFIED] percentiles '{col}': entirely null over {df.shape[0]:,} rows — quantiles undefined")
            cpp2["not_verified"] += 1
        else:
            p25 = df[col].quantile(0.25)
            p50 = df[col].quantile(0.50)
            p75 = df[col].quantile(0.75)
            if p25 is None or p50 is None or p75 is None:
                print(f"[NOT VERIFIED] percentiles '{col}': quantile returned None (p25={p25}, p50={p50}, p75={p75})")
                cpp2["not_verified"] += 1
            elif p25 <= p50 <= p75:
                print(f"[PASS] percentiles '{col}': p25={p25:.4g} <= p50={p50:.4g} <= p75={p75:.4g}")
                cpp2["passed"] += 1
            else:
                print(f"[FAIL] percentiles '{col}': monotonicity violated — p25={p25:.4g}, p50={p50:.4g}, p75={p75:.4g}")
                cpp2["failed"] += 1

# Check: temporal determination vs what script 05 found
# ASSUMES: temporal_expected is the orchestrator's Part A determination (a bool),
# not a default. None means no determination was recorded, which is not a pass.
if "temporal_detection" in not_applicable:
    print(f"[SKIPPED] temporal detection: {not_applicable['temporal_detection']}")
    cpp2["skipped"] += 1
elif not isinstance(temporal_expected, bool):
    print(f"[NOT VERIFIED] temporal detection: temporal_expected is {temporal_expected!r}, not a recorded True/False determination from Part A")
    cpp2["not_verified"] += 1
elif temporal_expected is False:
    print("[PASS] temporal detection: Part A recorded no temporal dimension (temporal_expected=False) — script 05 correctly not required")
    cpp2["passed"] += 1
elif not isinstance(time_columns_found, bool):
    print(f"[NOT VERIFIED] temporal detection: temporal_expected=True but time_columns_found is {time_columns_found!r} — script 05's result was not recorded")
    cpp2["not_verified"] += 1
elif time_columns_found is False:
    print("[WARNING] temporal detection: Part A expected temporal columns (temporal_expected=True) but script 05 identified none — reconcile before Part C")
    cpp2["warning"] += 1
else:
    print("[PASS] temporal detection: Part A expected temporal columns and script 05 identified them (temporal_expected=True, time_columns_found=True)")
    cpp2["passed"] += 1

# Count line, then verdict derived from the counts
cpp2_checks_run = cpp2["passed"] + cpp2["warning"] + cpp2["failed"]
if cpp2["failed"] > 0 or cpp2["not_verified"] > 0 or cpp2_checks_run == 0:
    cpp2_verdict = "FAILED"
elif cpp2["warning"] > 0:
    cpp2_verdict = "PASSED WITH WARNINGS"
else:
    cpp2_verdict = "PASSED"

print(f"\nChecks: {cpp2['passed']} passed, {cpp2['warning']} warnings, {cpp2['failed']} failed, {cpp2['not_verified']} not verified, {cpp2['skipped']} skipped")
print(f"CPP2 VALIDATION: {cpp2_verdict}")
print("=" * 60)

if cpp2_verdict == "FAILED":
    raise ValueError("CPP2 FAILED - see details above")
```

**R:**
```r
# --- CPP2 Validation: Post-Statistical ---
# INTENT: Verify the numeric summaries Part B reported are internally consistent and
# that the Part A temporal determination matches what script 05 found.
# REASONING: min()/max() on an all-NA column return Inf/-Inf with a warning and mean()
# returns NaN, so the old `if (!(col_min <= col_mean))` compared NA and errored with
# "missing value where TRUE/FALSE needed". Guard NA before any if ().
# ASSUMES: df / numeric_columns / temporal_expected / time_columns_found /
# not_applicable are assigned in this script's `# --- Config ---` region.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CPP2 VALIDATION: POST-STATISTICAL\n")
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cpp2 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# Check: mean lies inside [min, max] — one check per numeric column
cat("\nNumeric summary consistency (per column):\n")
if ("numeric_summaries" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] numeric summaries: %s\n", not_applicable[["numeric_summaries"]]))
  cpp2["skipped"] <- cpp2["skipped"] + 1L
} else if (is.null(df)) {
  cat("[NOT VERIFIED] numeric summaries: df is NULL — no frame to summarize\n")
  cpp2["not_verified"] <- cpp2["not_verified"] + 1L
} else if (is.null(numeric_columns) || length(numeric_columns) == 0) {
  cat("[NOT VERIFIED] numeric summaries: numeric_columns is empty — Part A identified no numeric columns to check; declare not_applicable$numeric_summaries if this dataset genuinely has none\n")
  cpp2["not_verified"] <- cpp2["not_verified"] + 1L
} else {
  for (col_name in numeric_columns) {
    if (!col_name %in% names(df)) {
      cat(sprintf("[FAIL] numeric summary '%s': column absent from the profiled frame\n", col_name))
      cpp2["failed"] <- cpp2["failed"] + 1L
    } else if (!is.numeric(df[[col_name]])) {
      cat(sprintf("[FAIL] numeric summary '%s': class is %s — numeric_columns named a non-numeric column\n",
                  col_name, paste(class(df[[col_name]]), collapse = "/")))
      cpp2["failed"] <- cpp2["failed"] + 1L
    } else if (sum(!is.na(df[[col_name]])) == 0) {
      cat(sprintf("[NOT VERIFIED] numeric summary '%s': entirely NA over %s rows — min/max/mean undefined\n",
                  col_name, format(nrow(df), big.mark = ",")))
      cpp2["not_verified"] <- cpp2["not_verified"] + 1L
    } else {
      col_min <- min(df[[col_name]], na.rm = TRUE)
      col_max <- max(df[[col_name]], na.rm = TRUE)
      col_mean <- mean(df[[col_name]], na.rm = TRUE)
      if (isTRUE(col_min <= col_mean && col_mean <= col_max)) {
        cat(sprintf("[PASS] numeric summary '%s': mean %.4g within [%.4g, %.4g]\n",
                    col_name, col_mean, col_min, col_max))
        cpp2["passed"] <- cpp2["passed"] + 1L
      } else {
        cat(sprintf("[FAIL] numeric summary '%s': mean %.4g outside [%.4g, %.4g]\n",
                    col_name, col_mean, col_min, col_max))
        cpp2["failed"] <- cpp2["failed"] + 1L
      }
    }
  }
}

# Check: percentile monotonicity — one check per numeric column
cat("\nPercentile monotonicity (per column):\n")
if ("percentile_monotonicity" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] percentile monotonicity: %s\n", not_applicable[["percentile_monotonicity"]]))
  cpp2["skipped"] <- cpp2["skipped"] + 1L
} else if (is.null(df)) {
  cat("[NOT VERIFIED] percentile monotonicity: df is NULL — no frame to summarize\n")
  cpp2["not_verified"] <- cpp2["not_verified"] + 1L
} else if (is.null(numeric_columns) || length(numeric_columns) == 0) {
  cat("[NOT VERIFIED] percentile monotonicity: numeric_columns is empty — no columns to check\n")
  cpp2["not_verified"] <- cpp2["not_verified"] + 1L
} else {
  for (col_name in numeric_columns) {
    if (!col_name %in% names(df) || !is.numeric(df[[col_name]])) {
      cat(sprintf("[FAIL] percentiles '%s': column absent or non-numeric — percentiles untestable\n", col_name))
      cpp2["failed"] <- cpp2["failed"] + 1L
    } else if (sum(!is.na(df[[col_name]])) == 0) {
      cat(sprintf("[NOT VERIFIED] percentiles '%s': entirely NA over %s rows — quantiles undefined\n",
                  col_name, format(nrow(df), big.mark = ",")))
      cpp2["not_verified"] <- cpp2["not_verified"] + 1L
    } else {
      p25 <- quantile(df[[col_name]], 0.25, na.rm = TRUE, names = FALSE)
      p50 <- quantile(df[[col_name]], 0.50, na.rm = TRUE, names = FALSE)
      p75 <- quantile(df[[col_name]], 0.75, na.rm = TRUE, names = FALSE)
      if (any(is.na(c(p25, p50, p75)))) {
        cat(sprintf("[NOT VERIFIED] percentiles '%s': quantile returned NA (p25=%s, p50=%s, p75=%s)\n",
                    col_name, format(p25), format(p50), format(p75)))
        cpp2["not_verified"] <- cpp2["not_verified"] + 1L
      } else if (isTRUE(p25 <= p50 && p50 <= p75)) {
        cat(sprintf("[PASS] percentiles '%s': p25=%.4g <= p50=%.4g <= p75=%.4g\n", col_name, p25, p50, p75))
        cpp2["passed"] <- cpp2["passed"] + 1L
      } else {
        cat(sprintf("[FAIL] percentiles '%s': monotonicity violated — p25=%.4g, p50=%.4g, p75=%.4g\n",
                    col_name, p25, p50, p75))
        cpp2["failed"] <- cpp2["failed"] + 1L
      }
    }
  }
}

# Check: temporal determination vs what script 05 found
if ("temporal_detection" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] temporal detection: %s\n", not_applicable[["temporal_detection"]]))
  cpp2["skipped"] <- cpp2["skipped"] + 1L
} else if (!(is.logical(temporal_expected) && length(temporal_expected) == 1 && !is.na(temporal_expected))) {
  cat("[NOT VERIFIED] temporal detection: temporal_expected is not a recorded TRUE/FALSE determination from Part A\n")
  cpp2["not_verified"] <- cpp2["not_verified"] + 1L
} else if (isFALSE(temporal_expected)) {
  cat("[PASS] temporal detection: Part A recorded no temporal dimension (temporal_expected=FALSE) — script 05 correctly not required\n")
  cpp2["passed"] <- cpp2["passed"] + 1L
} else if (!(is.logical(time_columns_found) && length(time_columns_found) == 1 && !is.na(time_columns_found))) {
  cat("[NOT VERIFIED] temporal detection: temporal_expected=TRUE but time_columns_found was not recorded by script 05\n")
  cpp2["not_verified"] <- cpp2["not_verified"] + 1L
} else if (isFALSE(time_columns_found)) {
  cat("[WARNING] temporal detection: Part A expected temporal columns (temporal_expected=TRUE) but script 05 identified none — reconcile before Part C\n")
  cpp2["warning"] <- cpp2["warning"] + 1L
} else {
  cat("[PASS] temporal detection: Part A expected temporal columns and script 05 identified them (temporal_expected=TRUE, time_columns_found=TRUE)\n")
  cpp2["passed"] <- cpp2["passed"] + 1L
}

# Count line, then verdict derived from the counts
cpp2_checks_run <- cpp2[["passed"]] + cpp2[["warning"]] + cpp2[["failed"]]
if (cpp2[["failed"]] > 0 || cpp2[["not_verified"]] > 0 || cpp2_checks_run == 0) {
  cpp2_verdict <- "FAILED"
} else if (cpp2[["warning"]] > 0) {
  cpp2_verdict <- "PASSED WITH WARNINGS"
} else {
  cpp2_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cpp2[["passed"]], cpp2[["warning"]], cpp2[["failed"]], cpp2[["not_verified"]], cpp2[["skipped"]]))
cat(sprintf("CPP2 VALIDATION: %s\n", cpp2_verdict))
cat(strrep("=", 60), "\n")

if (cpp2_verdict == "FAILED") {
  stop("CPP2 FAILED - see details above")
}
```

**`not_applicable` keys recognized by CPP2:** `numeric_summaries`, `percentile_monotonicity`, `temporal_detection`.

### CPP3: Post-Relational Validation

**Embedded in:** `scripts/profile_relational/09_quality-anomaly.py` (`.R` for R)

> **Re-computation NOTE (do not drop this when copying).** Each profiling script runs
> as its own process; there is no shared in-memory state. Variables produced by other
> Part C scripts — `uniqueness_results` (script 07), `correlation_matrix` (script 08) —
> must be **recomputed or loaded inside script 09** before this block runs. If script 08
> was skipped by the conditional-execution rule, carry that decision into
> `not_applicable["correlation_symmetry"]` with its reason rather than leaving
> `correlation_matrix` as `None`/`NULL`: an undeclared absence is `[NOT VERIFIED]`.

**Config stanza (assign before the block):**
```python
# --- Config ---
df = None                    # the frame profiled in Part C
anomaly_catalog = None       # list of anomaly records from script 09; None if not built
correlation_matrix = None    # square numpy array recomputed/loaded here; None if script 08 skipped
key_candidates = []          # key columns from script 07; [] means none were nominated
uniqueness_results = {}      # {column: reported_n_unique} recomputed/loaded here
not_applicable = {}          # e.g. {"correlation_symmetry": "script 08 skipped — fewer than 3 numeric columns"}
```

```python
import numpy as np

# --- CPP3 Validation: Post-Relational ---
# INTENT: Verify the relational claims Part C reported are coherent — the anomaly
# catalog exists, the correlation matrix is genuinely symmetric, and every reported
# uniqueness count matches a recount against the frame.
# REASONING: The old template silently skipped the symmetry check when
# correlation_matrix was None, ran zero iterations when key_candidates was empty, and
# raised KeyError (Python) / a length-zero error (R) when a key was missing from
# uniqueness_results — all three printed or aborted instead of reporting.
# ASSUMES: the config variables above are assigned in `# --- Config ---`.
print("\n" + "=" * 60)
print("CPP3 VALIDATION: POST-RELATIONAL")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cpp3 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Check: anomaly catalog is non-empty (at minimum INFO-level observations)
if "anomaly_catalog" in not_applicable:
    print(f"[SKIPPED] anomaly catalog: {not_applicable['anomaly_catalog']}")
    cpp3["skipped"] += 1
elif anomaly_catalog is None:
    print("[NOT VERIFIED] anomaly catalog: anomaly_catalog is None — script 09 produced no catalog object")
    cpp3["not_verified"] += 1
elif len(anomaly_catalog) == 0:
    print("[FAIL] anomaly catalog: 0 entries — quality analysis must produce at least one observation, even INFO-level")
    cpp3["failed"] += 1
else:
    print(f"[PASS] anomaly catalog: {len(anomaly_catalog)} entries cataloged")
    cpp3["passed"] += 1

# Check: correlation matrix symmetry
if "correlation_symmetry" in not_applicable:
    print(f"[SKIPPED] correlation symmetry: {not_applicable['correlation_symmetry']}")
    cpp3["skipped"] += 1
elif correlation_matrix is None:
    print("[NOT VERIFIED] correlation symmetry: correlation_matrix is None — recompute or load it in this script, or declare not_applicable['correlation_symmetry'] if script 08 was skipped")
    cpp3["not_verified"] += 1
else:
    corr = np.asarray(correlation_matrix, dtype=float)
    if corr.ndim != 2 or corr.shape[0] != corr.shape[1]:
        print(f"[FAIL] correlation symmetry: matrix is {corr.shape} — not square, symmetry undefined")
        cpp3["failed"] += 1
    elif corr.size == 0 or int(np.isfinite(corr).sum()) == 0:
        # REASONING: an all-NaN matrix compares vacuously true under nan-tolerant
        # comparison; that is an absence of evidence, not symmetry.
        print(f"[NOT VERIFIED] correlation symmetry: {corr.shape} matrix has 0 finite entries — nothing to compare")
        cpp3["not_verified"] += 1
    else:
        deviation = np.abs(corr - corr.T)
        max_dev = float(np.nanmax(deviation))
        n_finite = int(np.isfinite(corr).sum())
        if max_dev > 1e-10:
            print(f"[FAIL] correlation symmetry: max |M - M'| = {max_dev:.3g} exceeds 1e-10 over {n_finite} finite entries of a {corr.shape[0]}x{corr.shape[1]} matrix")
            cpp3["failed"] += 1
        else:
            print(f"[PASS] correlation symmetry: max |M - M'| = {max_dev:.3g} <= 1e-10 over {n_finite} finite entries of a {corr.shape[0]}x{corr.shape[1]} matrix")
            cpp3["passed"] += 1

# Check: reported uniqueness counts agree with a recount — one check per key candidate
print("\nUniqueness agreement (per key candidate):")
if "uniqueness_agreement" in not_applicable:
    print(f"[SKIPPED] uniqueness agreement: {not_applicable['uniqueness_agreement']}")
    cpp3["skipped"] += 1
elif df is None:
    print("[NOT VERIFIED] uniqueness agreement: df is None — no frame to recount against")
    cpp3["not_verified"] += 1
elif key_candidates is None or len(key_candidates) == 0:
    print("[NOT VERIFIED] uniqueness agreement: key_candidates is empty — script 07 nominated no key columns to verify")
    cpp3["not_verified"] += 1
elif uniqueness_results is None or len(uniqueness_results) == 0:
    print("[NOT VERIFIED] uniqueness agreement: uniqueness_results is empty — recompute or load script 07's counts in this script")
    cpp3["not_verified"] += 1
else:
    for col in key_candidates:
        if col not in uniqueness_results:
            print(f"[NOT VERIFIED] uniqueness '{col}': no reported count in uniqueness_results — nothing to compare the recount against")
            cpp3["not_verified"] += 1
        elif col not in df.columns:
            print(f"[FAIL] uniqueness '{col}': column absent from the profiled frame — recount impossible")
            cpp3["failed"] += 1
        else:
            reported_unique = uniqueness_results[col]
            actual_unique = df[col].n_unique()
            if not isinstance(reported_unique, (int, float)) or isinstance(reported_unique, bool):
                print(f"[NOT VERIFIED] uniqueness '{col}': reported count is {reported_unique!r}, not a number")
                cpp3["not_verified"] += 1
            elif reported_unique == actual_unique:
                print(f"[PASS] uniqueness '{col}': reported {reported_unique} == recounted {actual_unique} over {df.shape[0]:,} rows")
                cpp3["passed"] += 1
            else:
                print(f"[FAIL] uniqueness '{col}': reported {reported_unique} != recounted {actual_unique} over {df.shape[0]:,} rows")
                cpp3["failed"] += 1

# Count line, then verdict derived from the counts
cpp3_checks_run = cpp3["passed"] + cpp3["warning"] + cpp3["failed"]
if cpp3["failed"] > 0 or cpp3["not_verified"] > 0 or cpp3_checks_run == 0:
    cpp3_verdict = "FAILED"
elif cpp3["warning"] > 0:
    cpp3_verdict = "PASSED WITH WARNINGS"
else:
    cpp3_verdict = "PASSED"

print(f"\nChecks: {cpp3['passed']} passed, {cpp3['warning']} warnings, {cpp3['failed']} failed, {cpp3['not_verified']} not verified, {cpp3['skipped']} skipped")
print(f"CPP3 VALIDATION: {cpp3_verdict}")
print("=" * 60)

if cpp3_verdict == "FAILED":
    raise ValueError("CPP3 FAILED - see details above")
```

**R:**
```r
# --- CPP3 Validation: Post-Relational ---
# INTENT: Verify the relational claims Part C reported are coherent.
# REASONING: `all(abs(M - t(M)) < 1e-10, na.rm = TRUE)` returns TRUE for an all-NA
# matrix — a vacuous pass. Guard with sum(!is.na(M)) > 0 before comparing, and index
# uniqueness_results with [[ ]] plus a name test so a missing key reports instead of
# erroring with "argument is of length zero".
# ASSUMES: the config variables are assigned in `# --- Config ---`; the
# re-computation NOTE above applies equally to the R scripts.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CPP3 VALIDATION: POST-RELATIONAL\n")
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cpp3 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# Check: anomaly catalog is non-empty
if ("anomaly_catalog" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] anomaly catalog: %s\n", not_applicable[["anomaly_catalog"]]))
  cpp3["skipped"] <- cpp3["skipped"] + 1L
} else if (is.null(anomaly_catalog)) {
  cat("[NOT VERIFIED] anomaly catalog: anomaly_catalog is NULL — script 09 produced no catalog object\n")
  cpp3["not_verified"] <- cpp3["not_verified"] + 1L
} else if (length(anomaly_catalog) == 0) {
  cat("[FAIL] anomaly catalog: 0 entries — quality analysis must produce at least one observation, even INFO-level\n")
  cpp3["failed"] <- cpp3["failed"] + 1L
} else {
  cat(sprintf("[PASS] anomaly catalog: %d entries cataloged\n", length(anomaly_catalog)))
  cpp3["passed"] <- cpp3["passed"] + 1L
}

# Check: correlation matrix symmetry
if ("correlation_symmetry" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] correlation symmetry: %s\n", not_applicable[["correlation_symmetry"]]))
  cpp3["skipped"] <- cpp3["skipped"] + 1L
} else if (is.null(correlation_matrix)) {
  cat("[NOT VERIFIED] correlation symmetry: correlation_matrix is NULL — recompute or load it in this script, or declare not_applicable$correlation_symmetry if script 08 was skipped\n")
  cpp3["not_verified"] <- cpp3["not_verified"] + 1L
} else {
  corr <- as.matrix(correlation_matrix)
  if (nrow(corr) != ncol(corr)) {
    cat(sprintf("[FAIL] correlation symmetry: matrix is %dx%d — not square, symmetry undefined\n",
                nrow(corr), ncol(corr)))
    cpp3["failed"] <- cpp3["failed"] + 1L
  } else if (length(corr) == 0 || sum(!is.na(corr)) == 0) {
    cat(sprintf("[NOT VERIFIED] correlation symmetry: %dx%d matrix has 0 non-NA entries — nothing to compare\n",
                nrow(corr), ncol(corr)))
    cpp3["not_verified"] <- cpp3["not_verified"] + 1L
  } else {
    deviation <- abs(corr - t(corr))
    max_dev <- max(deviation, na.rm = TRUE)
    n_finite <- sum(!is.na(corr))
    if (isTRUE(max_dev > 1e-10)) {
      cat(sprintf("[FAIL] correlation symmetry: max |M - M'| = %.3g exceeds 1e-10 over %d non-NA entries of a %dx%d matrix\n",
                  max_dev, n_finite, nrow(corr), ncol(corr)))
      cpp3["failed"] <- cpp3["failed"] + 1L
    } else {
      cat(sprintf("[PASS] correlation symmetry: max |M - M'| = %.3g <= 1e-10 over %d non-NA entries of a %dx%d matrix\n",
                  max_dev, n_finite, nrow(corr), ncol(corr)))
      cpp3["passed"] <- cpp3["passed"] + 1L
    }
  }
}

# Check: reported uniqueness counts agree with a recount — one check per key candidate
cat("\nUniqueness agreement (per key candidate):\n")
if ("uniqueness_agreement" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] uniqueness agreement: %s\n", not_applicable[["uniqueness_agreement"]]))
  cpp3["skipped"] <- cpp3["skipped"] + 1L
} else if (is.null(df)) {
  cat("[NOT VERIFIED] uniqueness agreement: df is NULL — no frame to recount against\n")
  cpp3["not_verified"] <- cpp3["not_verified"] + 1L
} else if (is.null(key_candidates) || length(key_candidates) == 0) {
  cat("[NOT VERIFIED] uniqueness agreement: key_candidates is empty — script 07 nominated no key columns to verify\n")
  cpp3["not_verified"] <- cpp3["not_verified"] + 1L
} else if (is.null(uniqueness_results) || length(uniqueness_results) == 0) {
  cat("[NOT VERIFIED] uniqueness agreement: uniqueness_results is empty — recompute or load script 07's counts in this script\n")
  cpp3["not_verified"] <- cpp3["not_verified"] + 1L
} else {
  for (col_name in key_candidates) {
    if (!col_name %in% names(uniqueness_results)) {
      cat(sprintf("[NOT VERIFIED] uniqueness '%s': no reported count in uniqueness_results — nothing to compare the recount against\n", col_name))
      cpp3["not_verified"] <- cpp3["not_verified"] + 1L
    } else if (!col_name %in% names(df)) {
      cat(sprintf("[FAIL] uniqueness '%s': column absent from the profiled frame — recount impossible\n", col_name))
      cpp3["failed"] <- cpp3["failed"] + 1L
    } else {
      reported_unique <- uniqueness_results[[col_name]]
      actual_unique <- length(unique(df[[col_name]]))
      if (!(is.numeric(reported_unique) && length(reported_unique) == 1 && !is.na(reported_unique))) {
        cat(sprintf("[NOT VERIFIED] uniqueness '%s': reported count is not a single number\n", col_name))
        cpp3["not_verified"] <- cpp3["not_verified"] + 1L
      } else if (isTRUE(reported_unique == actual_unique)) {
        cat(sprintf("[PASS] uniqueness '%s': reported %d == recounted %d over %s rows\n",
                    col_name, as.integer(reported_unique), actual_unique, format(nrow(df), big.mark = ",")))
        cpp3["passed"] <- cpp3["passed"] + 1L
      } else {
        cat(sprintf("[FAIL] uniqueness '%s': reported %d != recounted %d over %s rows\n",
                    col_name, as.integer(reported_unique), actual_unique, format(nrow(df), big.mark = ",")))
        cpp3["failed"] <- cpp3["failed"] + 1L
      }
    }
  }
}

# Count line, then verdict derived from the counts
cpp3_checks_run <- cpp3[["passed"]] + cpp3[["warning"]] + cpp3[["failed"]]
if (cpp3[["failed"]] > 0 || cpp3[["not_verified"]] > 0 || cpp3_checks_run == 0) {
  cpp3_verdict <- "FAILED"
} else if (cpp3[["warning"]] > 0) {
  cpp3_verdict <- "PASSED WITH WARNINGS"
} else {
  cpp3_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cpp3[["passed"]], cpp3[["warning"]], cpp3[["failed"]], cpp3[["not_verified"]], cpp3[["skipped"]]))
cat(sprintf("CPP3 VALIDATION: %s\n", cpp3_verdict))
cat(strrep("=", 60), "\n")

if (cpp3_verdict == "FAILED") {
  stop("CPP3 FAILED - see details above")
}
```

**`not_applicable` keys recognized by CPP3:** `anomaly_catalog`, `correlation_symmetry`, `uniqueness_agreement`.

### CPP4: Post-Interpretation Validation

**Embedded in:** The last executed Part D script (script 11 if docs provided, otherwise script 10).

> **Input is the structured draft, not the printed text.** CPP4 checks
> `data_dictionary_draft` — the draft data dictionary that script 10 is required to
> produce (`WORKFLOW_PHASE_DO_PROFILING.md` § Part D) — as a list of records, one per
> interpreted column. It does **not** regex the script's printed output. Scanning
> printed text was the source of two silent passes: an empty or differently formatted
> output matched zero lines and printed `CPP4 PASSED` over nothing, and in R the
> default (TRE) regex engine let `.` match newlines, so a multi-line block collapsed
> into a single match and one leading `[PRELIMINARY]` laundered every unhedged claim
> below it. Records are enumerable, so "zero records" is detectable; and each record's
> text is still scanned **line by line**, so a hedge on the first line cannot cover the
> rest.

**Config stanza (assign before the block):**
```python
# --- Config ---
data_dictionary_draft = None   # list of {"column": str, "interpretation": str} from script 10
documentation_provided = None  # True/False from intake; None if never recorded
reconciliation_ran = None      # True/False set by script 11; None if script 11 did not run
not_applicable = {}            # e.g. {"reconciliation": "..."} — rarely needed; see Usage Notes
```

```python
# --- CPP4 Validation: Post-Interpretation ---
# INTENT: Verify interpretation discipline — every line of every interpretation record
# is hedged with [PRELIMINARY] (or explicitly marked [NO INTERPRETATION]) — and that
# documentation reconciliation ran whenever documentation was provided at intake.
# REASONING: Records are counted, so an absent or empty draft is [NOT VERIFIED] rather
# than a vacuous pass; per-line scanning stops a single leading hedge from covering
# unhedged claims further down the same record.
# ASSUMES: data_dictionary_draft / documentation_provided / reconciliation_ran /
# not_applicable are assigned in this script's `# --- Config ---` region.
print("\n" + "=" * 60)
print("CPP4 VALIDATION: POST-INTERPRETATION")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cpp4 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# Check: [PRELIMINARY] hedging — one check per interpretation record
print("\nInterpretation hedging (per record):")
if "preliminary_markers" in not_applicable:
    print(f"[SKIPPED] preliminary markers: {not_applicable['preliminary_markers']}")
    cpp4["skipped"] += 1
elif data_dictionary_draft is None:
    print("[NOT VERIFIED] preliminary markers: data_dictionary_draft is None — script 10 produced no structured interpretation records")
    cpp4["not_verified"] += 1
elif len(data_dictionary_draft) == 0:
    print("[NOT VERIFIED] preliminary markers: data_dictionary_draft has 0 records — nothing to check hedging on")
    cpp4["not_verified"] += 1
else:
    for entry in data_dictionary_draft:
        col_name = entry.get("column") if isinstance(entry, dict) else None
        interp = entry.get("interpretation") if isinstance(entry, dict) else None
        label = col_name if isinstance(col_name, str) and col_name.strip() else "<unnamed record>"
        if not isinstance(interp, str) or interp.strip() == "":
            print(f"[NOT VERIFIED] interpretation '{label}': record has no non-empty 'interpretation' text")
            cpp4["not_verified"] += 1
            continue
        claim_lines = [ln for ln in interp.split("\n") if ln.strip() != ""]
        # REASONING: [PRELIMINARY] is a prefix marker — it may lead a line of text.
        # [NO INTERPRETATION] is a standalone declaration that the column was NOT
        # interpreted, so it can only hedge a line that says nothing else. Accepting
        # it as a substring let "[NO INTERPRETATION] enrollment is a headcount"
        # launder a real interpretive claim as an abstention.
        unhedged = [ln for ln in claim_lines
                    if "[PRELIMINARY]" not in ln and ln.strip() != "[NO INTERPRETATION]"]
        if len(unhedged) > 0:
            print(f"[FAIL] interpretation '{label}': {len(unhedged)} of {len(claim_lines)} claim lines unhedged — first is {unhedged[0].strip()[:80]!r}")
            cpp4["failed"] += 1
        else:
            print(f"[PASS] interpretation '{label}': all {len(claim_lines)} claim lines carry [PRELIMINARY] or [NO INTERPRETATION]")
            cpp4["passed"] += 1

# Check: documentation reconciliation ran when documentation was provided
if "reconciliation" in not_applicable:
    print(f"[SKIPPED] reconciliation: {not_applicable['reconciliation']}")
    cpp4["skipped"] += 1
elif not isinstance(documentation_provided, bool):
    print(f"[NOT VERIFIED] reconciliation: documentation_provided is {documentation_provided!r}, not a recorded True/False from intake")
    cpp4["not_verified"] += 1
elif documentation_provided is False:
    print("[PASS] reconciliation: no documentation supplied at intake (documentation_provided=False) — script 11 correctly not required")
    cpp4["passed"] += 1
elif not isinstance(reconciliation_ran, bool):
    print(f"[NOT VERIFIED] reconciliation: documentation_provided=True but reconciliation_ran is {reconciliation_ran!r} — script 11's execution was not recorded")
    cpp4["not_verified"] += 1
elif reconciliation_ran is False:
    print("[FAIL] reconciliation: documentation was provided at intake but script 11 did not execute (reconciliation_ran=False)")
    cpp4["failed"] += 1
else:
    print("[PASS] reconciliation: documentation provided at intake and script 11 executed (documentation_provided=True, reconciliation_ran=True)")
    cpp4["passed"] += 1

# Count line, then verdict derived from the counts
cpp4_checks_run = cpp4["passed"] + cpp4["warning"] + cpp4["failed"]
if cpp4["failed"] > 0 or cpp4["not_verified"] > 0 or cpp4_checks_run == 0:
    cpp4_verdict = "FAILED"
elif cpp4["warning"] > 0:
    cpp4_verdict = "PASSED WITH WARNINGS"
else:
    cpp4_verdict = "PASSED"

print(f"\nChecks: {cpp4['passed']} passed, {cpp4['warning']} warnings, {cpp4['failed']} failed, {cpp4['not_verified']} not verified, {cpp4['skipped']} skipped")
print(f"CPP4 VALIDATION: {cpp4_verdict}")
print("=" * 60)

if cpp4_verdict == "FAILED":
    raise ValueError("CPP4 FAILED - see details above")
```

**R:**
```r
# --- CPP4 Validation: Post-Interpretation ---
# INTENT: Verify interpretation discipline and documentation reconciliation.
# REASONING: R's default TRE engine lets `.` match a newline, so a regex over a
# multi-line block returns one match and a single leading [PRELIMINARY] hedges the
# whole block. This template never regexes across lines: it splits each record's text
# on "\n" first and tests each line with perl = TRUE.
# ASSUMES: data_dictionary_draft is a data.frame with `column` and `interpretation`
# character columns (NULL if script 10 produced no structured draft); the other
# config variables are assigned in `# --- Config ---`.
cat("\n")
cat(strrep("=", 60), "\n")
cat("CPP4 VALIDATION: POST-INTERPRETATION\n")
cat(strrep("=", 60), "\n")

na_keep <- character(0)
for (k in names(not_applicable)) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && nzchar(trimws(v))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]

cpp4 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# Check: [PRELIMINARY] hedging — one check per interpretation record
cat("\nInterpretation hedging (per record):\n")
if ("preliminary_markers" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] preliminary markers: %s\n", not_applicable[["preliminary_markers"]]))
  cpp4["skipped"] <- cpp4["skipped"] + 1L
} else if (is.null(data_dictionary_draft)) {
  cat("[NOT VERIFIED] preliminary markers: data_dictionary_draft is NULL — script 10 produced no structured interpretation records\n")
  cpp4["not_verified"] <- cpp4["not_verified"] + 1L
} else if (!is.data.frame(data_dictionary_draft) || !all(c("column", "interpretation") %in% names(data_dictionary_draft))) {
  cat("[NOT VERIFIED] preliminary markers: data_dictionary_draft is not a data.frame with 'column' and 'interpretation' columns\n")
  cpp4["not_verified"] <- cpp4["not_verified"] + 1L
} else if (nrow(data_dictionary_draft) == 0) {
  cat("[NOT VERIFIED] preliminary markers: data_dictionary_draft has 0 records — nothing to check hedging on\n")
  cpp4["not_verified"] <- cpp4["not_verified"] + 1L
} else {
  for (i in seq_len(nrow(data_dictionary_draft))) {
    col_name <- data_dictionary_draft[["column"]][i]
    interp <- data_dictionary_draft[["interpretation"]][i]
    label <- if (is.character(col_name) && !is.na(col_name) && nzchar(trimws(col_name))) col_name else "<unnamed record>"
    if (!is.character(interp) || is.na(interp) || !nzchar(trimws(interp))) {
      cat(sprintf("[NOT VERIFIED] interpretation '%s': record has no non-empty 'interpretation' text\n", label))
      cpp4["not_verified"] <- cpp4["not_verified"] + 1L
      next
    }
    all_lines <- strsplit(interp, "\n", fixed = TRUE)[[1]]
    claim_lines <- all_lines[nzchar(trimws(all_lines))]
    # [PRELIMINARY] may prefix text; [NO INTERPRETATION] hedges only when it is the
    # entire trimmed line, otherwise it laundered claims sharing its line.
    hedged <- grepl("\\[PRELIMINARY\\]", claim_lines, perl = TRUE) |
              (trimws(claim_lines) == "[NO INTERPRETATION]")
    unhedged <- claim_lines[!hedged]
    if (length(unhedged) > 0) {
      cat(sprintf("[FAIL] interpretation '%s': %d of %d claim lines unhedged — first is '%s'\n",
                  label, length(unhedged), length(claim_lines), substr(trimws(unhedged[1]), 1, 80)))
      cpp4["failed"] <- cpp4["failed"] + 1L
    } else {
      cat(sprintf("[PASS] interpretation '%s': all %d claim lines carry [PRELIMINARY] or [NO INTERPRETATION]\n",
                  label, length(claim_lines)))
      cpp4["passed"] <- cpp4["passed"] + 1L
    }
  }
}

# Check: documentation reconciliation ran when documentation was provided
if ("reconciliation" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] reconciliation: %s\n", not_applicable[["reconciliation"]]))
  cpp4["skipped"] <- cpp4["skipped"] + 1L
} else if (!(is.logical(documentation_provided) && length(documentation_provided) == 1 && !is.na(documentation_provided))) {
  cat("[NOT VERIFIED] reconciliation: documentation_provided is not a recorded TRUE/FALSE from intake\n")
  cpp4["not_verified"] <- cpp4["not_verified"] + 1L
} else if (isFALSE(documentation_provided)) {
  cat("[PASS] reconciliation: no documentation supplied at intake (documentation_provided=FALSE) — script 11 correctly not required\n")
  cpp4["passed"] <- cpp4["passed"] + 1L
} else if (!(is.logical(reconciliation_ran) && length(reconciliation_ran) == 1 && !is.na(reconciliation_ran))) {
  cat("[NOT VERIFIED] reconciliation: documentation_provided=TRUE but reconciliation_ran was not recorded by script 11\n")
  cpp4["not_verified"] <- cpp4["not_verified"] + 1L
} else if (isFALSE(reconciliation_ran)) {
  cat("[FAIL] reconciliation: documentation was provided at intake but script 11 did not execute (reconciliation_ran=FALSE)\n")
  cpp4["failed"] <- cpp4["failed"] + 1L
} else {
  cat("[PASS] reconciliation: documentation provided at intake and script 11 executed (documentation_provided=TRUE, reconciliation_ran=TRUE)\n")
  cpp4["passed"] <- cpp4["passed"] + 1L
}

# Count line, then verdict derived from the counts
cpp4_checks_run <- cpp4[["passed"]] + cpp4[["warning"]] + cpp4[["failed"]]
if (cpp4[["failed"]] > 0 || cpp4[["not_verified"]] > 0 || cpp4_checks_run == 0) {
  cpp4_verdict <- "FAILED"
} else if (cpp4[["warning"]] > 0) {
  cpp4_verdict <- "PASSED WITH WARNINGS"
} else {
  cpp4_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cpp4[["passed"]], cpp4[["warning"]], cpp4[["failed"]], cpp4[["not_verified"]], cpp4[["skipped"]]))
cat(sprintf("CPP4 VALIDATION: %s\n", cpp4_verdict))
cat(strrep("=", 60), "\n")

if (cpp4_verdict == "FAILED") {
  stop("CPP4 FAILED - see details above")
}
```

**Marker semantics.** `[PRELIMINARY]` is a *prefix*: it may lead a line that also carries text, because hedged interpretation is still interpretation. `[NO INTERPRETATION]` is an *abstention*: it counts only when it is the entire trimmed line. Treating it as a substring let `[NO INTERPRETATION] enrollment is a headcount, not an FTE` pass as an abstention while asserting an interpretation — the abstention marker cannot cover a claim it shares a line with.

**`not_applicable` keys recognized by CPP4:** `preliminary_markers`, `reconciliation`. Neither is expected in normal operation — script 10 always produces interpretation records, and `documentation_provided=False` is handled as a `[PASS]` with evidence rather than a skip, because "no documentation at intake" is an observed fact, not an undeclared absence.

### CPP-SKILL: Post-Authoring Validation

**Embedded in:** Stage DI-7 skill authoring subagent output

> *Language note: this is verifier tooling that scans the generated SKILL.md (markdown), not pipeline code — it runs in Python even on R projects. There is deliberately no R variant; the artifact under test is markdown, and maintaining two scanners would reintroduce the drift this section exists to remove.*

**Coverage contract.** This block is the machine half of the CPP-SKILL checklist in `.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_AUTHORING.md`. Every checklist item is either **automated here** or listed in `MANUAL_ITEMS` and emitted as `[NOT VERIFIED]` until the authoring agent records a determination in `manual_determinations`. There is no third category: an item the code does not check and the agent does not adjudicate cannot be covered by a `PASSED` verdict, because an unadjudicated manual item counts as `not_verified` and forces `FAILED`.

Two properties of the checklist are deliberately **not** emitted as checks. *Itemized reporting* — "report per item, not an overall status" — is a property of this block's output shape (one outcome token per item, a count line, a derived verdict), so it is satisfied structurally; emitting it as a check produced a `[PASS]` whose condition was true by construction, which is an evidence-free pass of exactly the kind this repair removes, and it inflated the passed count by one on every run. A check that cannot fail is not evidence. The same reasoning governs *manual determinations*: a determination counts only when it carries at least 20 characters of evidence after `PASS:` / `FAIL:`, because `"PASS: ok"` satisfies a prefix test while asserting nothing reviewable.

**Config stanza (assign before the block):**
```python
# --- Config ---
skill_draft_dir = None    # absolute path to the drafted skill directory
profiled_columns = None   # list of every column name from Part A; None if not carried forward
not_applicable = {}       # e.g. {"bundled_scripts": "..."} — see Usage Notes
# Determinations for the checklist items the code cannot judge. Each value must be a
# non-empty string starting with "PASS: " or "FAIL: " and carrying the evidence.
manual_determinations = {}
```

```python
# --- CPP-SKILL Validation: Post-Authoring ---
# INTENT: Verify the drafted skill satisfies the canonical data source skill template
# and the DI-7 authoring checklist, itemized one outcome token per check item.
# REASONING: The old block used substring matching ("## What is" matched a
# "## What is NOT Included" heading), computed decision_tree_count without ever
# asserting it, hard-required coded-values.md although value-interpretation.md is an
# accepted substitute, and covered roughly two thirds of the checklist while printing
# an unqualified PASSED line.
# ASSUMES: skill_draft_dir / profiled_columns / manual_determinations /
# not_applicable are assigned in the `# --- Config ---` region above.
import os
import re

print("\n" + "=" * 60)
print("CPP-SKILL VALIDATION: POST-AUTHORING")
print("=" * 60)

not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

cpps = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# The 8 level-2 sections of the canonical 12-section order (items 5-12); items 1-4 are
# frontmatter, title, summary, and the Value Encodings blockquote, checked separately.
# REASONING: each pattern is anchored at line start with ^##\s and bounded, so a
# deeper heading (###) or a longer title ("## What is NOT Included") cannot satisfy it.
CANONICAL_H2 = [
    ("What is [Source]?", r"^##\s+What is\s+(?![Nn][Oo][Tt]\b)\S"),
    ("Reference File Structure", r"^##\s+Reference File Structure\s*$"),
    ("Decision Trees", r"^##\s+Decision Trees\s*$"),
    ("Quick Reference", r"^##\s+Quick Reference\b"),
    ("Data Access", r"^##\s+Data Access\s*$"),
    ("Common Pitfalls", r"^##\s+Common Pitfalls\s*$"),
    ("Related Data Sources", r"^##\s+Related Data Sources\s*$"),
    ("Topic Index", r"^##\s+Topic Index\s*$"),
]

# Checklist items this block cannot judge. Each needs a recorded determination.
MANUAL_ITEMS = [
    ("related_skills_crossref", "Related Data Sources names the domain explorer and query skills (if they exist)"),
    ("coded_values_complete", "coded-values.md / value-interpretation.md enumerates ALL coded values found during profiling"),
    ("data_quality_complete", "data-quality.md catalogs ALL anomalies from the profiling scripts"),
    ("variable_definitions_grouped", "variable-definitions.md groups columns by semantic family with descriptions"),
    ("interpretive_share", "Reference files are ~40-60% interpretive/analytical content"),
    ("topic_specific_file", "If the source has 3+ distinct analytical use cases, a topic-specific reference file exists"),
    ("cross_dataset_join", "If the source shares join keys with other DAAF skills, a cross-dataset join example is present"),
]

# Check: SKILL.md exists and is readable
content = None
lines = []
if skill_draft_dir is None or not isinstance(skill_draft_dir, str) or not skill_draft_dir.strip():
    print(f"[NOT VERIFIED] skill file: skill_draft_dir is {skill_draft_dir!r} — no draft directory to scan")
    cpps["not_verified"] += 1
    skill_path = None
else:
    skill_path = os.path.join(skill_draft_dir, "SKILL.md")
    if not os.path.exists(skill_path):
        print(f"[FAIL] skill file: {skill_path} does not exist — the authoring step produced no SKILL.md")
        cpps["failed"] += 1
    else:
        with open(skill_path) as f:
            content = f.read()
        lines = content.split("\n")
        print(f"[PASS] skill file: {skill_path} exists ({len(content):,} chars, {len(lines)} lines)")
        cpps["passed"] += 1

# Check: line count ceiling
if content is None:
    print("[NOT VERIFIED] line count: SKILL.md was not read — line count unavailable")
    cpps["not_verified"] += 1
elif len(lines) > 500:
    print(f"[FAIL] line count: SKILL.md is {len(lines)} lines (limit 500)")
    cpps["failed"] += 1
else:
    print(f"[PASS] line count: SKILL.md is {len(lines)} lines (limit 500)")
    cpps["passed"] += 1

# Check: frontmatter carries provenance dates
if content is None:
    print("[NOT VERIFIED] frontmatter provenance: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if fm_match is None:
        print("[FAIL] frontmatter provenance: no YAML frontmatter block at the top of SKILL.md")
        cpps["failed"] += 1
    else:
        fm_dates = re.findall(r"\d{4}-\d{2}-\d{2}", fm_match.group(1))
        if len(fm_dates) == 0:
            print("[FAIL] frontmatter provenance: frontmatter carries no YYYY-MM-DD provenance date")
            cpps["failed"] += 1
        else:
            print(f"[PASS] frontmatter provenance: {len(fm_dates)} date(s) present in frontmatter ({', '.join(fm_dates)})")
            cpps["passed"] += 1

# Check: the 8 canonical level-2 sections are present, anchored, and in order
if content is None:
    print("[NOT VERIFIED] canonical sections: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    section_pos = {}
    missing_sections = []
    for label, pattern in CANONICAL_H2:
        m = re.search(pattern, content, re.MULTILINE)
        if m is None:
            missing_sections.append(label)
        else:
            section_pos[label] = m.start()
    if len(missing_sections) > 0:
        print(f"[FAIL] canonical sections: {len(missing_sections)} of {len(CANONICAL_H2)} absent (anchored ^## match): {missing_sections}")
        cpps["failed"] += 1
    else:
        ordered = [lbl for lbl, _ in CANONICAL_H2]
        actual_order = sorted(ordered, key=lambda lbl: section_pos[lbl])
        if actual_order != ordered:
            print(f"[FAIL] canonical sections: all {len(CANONICAL_H2)} present but out of canonical order — found {actual_order}")
            cpps["failed"] += 1
        else:
            print(f"[PASS] canonical sections: all {len(CANONICAL_H2)} present in canonical order")
            cpps["passed"] += 1

# Check: Value Encodings Warning sits at position 4 (before "What is") and carries a table
if content is None:
    print("[NOT VERIFIED] value encodings: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    ve_match = re.search(r"^#{2,3}\s+Value Encodings?\b.*$", content, re.MULTILINE)
    whatis_match = re.search(r"^##\s+What is\s+(?![Nn][Oo][Tt]\b)\S", content, re.MULTILINE)
    if ve_match is None:
        print("[FAIL] value encodings: no Value Encodings Warning heading found")
        cpps["failed"] += 1
    elif whatis_match is None:
        print("[NOT VERIFIED] value encodings: position is relative to the 'What is [Source]?' section, which is absent")
        cpps["not_verified"] += 1
    elif ve_match.start() > whatis_match.start():
        print(f"[FAIL] value encodings: warning appears at char {ve_match.start():,}, after 'What is' at char {whatis_match.start():,} — it belongs at position 4")
        cpps["failed"] += 1
    else:
        ve_body = content[ve_match.end():whatis_match.start()]
        table_rows = [ln for ln in ve_body.split("\n") if ln.strip().startswith("|")]
        if len(table_rows) < 3:
            print(f"[FAIL] value encodings: warning present at position 4 but its comparison table has {len(table_rows)} pipe rows (need header + separator + >=1 row)")
            cpps["failed"] += 1
        else:
            print(f"[PASS] value encodings: warning at char {ve_match.start():,} precedes 'What is' at char {whatis_match.start():,}, comparison table has {len(table_rows)} pipe rows")
            cpps["passed"] += 1

# Check: at least 2 decision trees inside the Decision Trees section
# REASONING: the old template computed decision_tree_count and then never asserted it.
if content is None:
    print("[NOT VERIFIED] decision trees: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    dt_match = re.search(r"^##\s+Decision Trees\s*$", content, re.MULTILINE)
    if dt_match is None:
        print("[NOT VERIFIED] decision trees: Decision Trees section absent — no region to count trees in")
        cpps["not_verified"] += 1
    else:
        next_h2 = re.search(r"^##\s+\S", content[dt_match.end():], re.MULTILINE)
        dt_body = content[dt_match.end():dt_match.end() + next_h2.start()] if next_h2 else content[dt_match.end():]
        decision_tree_count = len(re.findall(r"^```", dt_body, re.MULTILINE)) // 2
        if decision_tree_count < 2:
            print(f"[FAIL] decision trees: {decision_tree_count} fenced tree block(s) in the Decision Trees section (minimum 2)")
            cpps["failed"] += 1
        else:
            print(f"[PASS] decision trees: {decision_tree_count} fenced tree blocks in the Decision Trees section (minimum 2)")
            cpps["passed"] += 1

# Check: Missing Data Codes subsection inside Quick Reference
if content is None:
    print("[NOT VERIFIED] missing data codes: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    mdc_match = re.search(r"^#{3,4}\s+Missing Data Codes\s*$", content, re.MULTILINE)
    if mdc_match is None:
        print("[FAIL] missing data codes: no '### Missing Data Codes' subsection (anchored heading match)")
        cpps["failed"] += 1
    else:
        print(f"[PASS] missing data codes: '### Missing Data Codes' subsection present at char {mdc_match.start():,}")
        cpps["passed"] += 1

# Check: Truth Hierarchy blockquote inside Data Access
if content is None:
    print("[NOT VERIFIED] truth hierarchy: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    th_match = re.search(r"^>\s*.*Truth Hierarchy", content, re.MULTILINE)
    if th_match is None:
        print("[FAIL] truth hierarchy: no blockquote line ('> ...') mentioning Truth Hierarchy")
        cpps["failed"] += 1
    else:
        print(f"[PASS] truth hierarchy: blockquote present at char {th_match.start():,}")
        cpps["passed"] += 1

# Check: Common Pitfalls is a 3-column table with at least 3 data rows
if content is None:
    print("[NOT VERIFIED] common pitfalls table: SKILL.md was not read")
    cpps["not_verified"] += 1
else:
    cp_match = re.search(r"^##\s+Common Pitfalls\s*$", content, re.MULTILINE)
    if cp_match is None:
        print("[NOT VERIFIED] common pitfalls table: Common Pitfalls section absent — no table to measure")
        cpps["not_verified"] += 1
    else:
        next_h2 = re.search(r"^##\s+\S", content[cp_match.end():], re.MULTILINE)
        cp_body = content[cp_match.end():cp_match.end() + next_h2.start()] if next_h2 else content[cp_match.end():]
        cp_rows = [ln.strip() for ln in cp_body.split("\n") if ln.strip().startswith("|")]
        cp_data_rows = [r for r in cp_rows if not re.match(r"^\|[\s:|-]+\|$", r)][1:]
        widths = set(len([c for c in r.strip("|").split("|")]) for r in cp_data_rows) if cp_data_rows else set()
        if len(cp_data_rows) < 3:
            print(f"[FAIL] common pitfalls table: {len(cp_data_rows)} data rows (minimum 3)")
            cpps["failed"] += 1
        elif widths != {3}:
            print(f"[FAIL] common pitfalls table: {len(cp_data_rows)} data rows but column widths {sorted(widths)} — the canonical table is 3 columns")
            cpps["failed"] += 1
        else:
            print(f"[PASS] common pitfalls table: {len(cp_data_rows)} data rows x 3 columns")
            cpps["passed"] += 1

# Check: required reference files exist (coded-values.md OR value-interpretation.md)
# REASONING: WORKFLOW_PHASE_DO_AUTHORING.md accepts value-interpretation.md when the
# source has no coded values; hard-requiring coded-values.md was a false FAIL.
if skill_draft_dir is None:
    print("[NOT VERIFIED] reference files: skill_draft_dir is None — nothing to list")
    cpps["not_verified"] += 1
else:
    ref_dir = os.path.join(skill_draft_dir, "references")
    always_required = ["columns.md", "data-quality.md", "variable-definitions.md", "analytical-context.md"]
    missing_refs = [f for f in always_required if not os.path.exists(os.path.join(ref_dir, f))]
    has_codes_file = (os.path.exists(os.path.join(ref_dir, "coded-values.md"))
                      or os.path.exists(os.path.join(ref_dir, "value-interpretation.md")))
    if not has_codes_file:
        missing_refs.append("coded-values.md or value-interpretation.md")
    if len(missing_refs) > 0:
        print(f"[FAIL] reference files: {len(missing_refs)} of {len(always_required) + 1} absent from {ref_dir}: {missing_refs}")
        cpps["failed"] += 1
    else:
        print(f"[PASS] reference files: all {len(always_required) + 1} present in {ref_dir} (codes file: {'coded-values.md' if os.path.exists(os.path.join(ref_dir, 'coded-values.md')) else 'value-interpretation.md'})")
        cpps["passed"] += 1

# Check: columns.md names every profiled column
if skill_draft_dir is None:
    print("[NOT VERIFIED] column coverage: skill_draft_dir is None")
    cpps["not_verified"] += 1
elif profiled_columns is None or len(profiled_columns) == 0:
    print("[NOT VERIFIED] column coverage: profiled_columns is empty — Part A's column list was not carried into DI-7, so completeness is unmeasurable")
    cpps["not_verified"] += 1
elif not os.path.exists(os.path.join(skill_draft_dir, "references", "columns.md")):
    print("[FAIL] column coverage: references/columns.md does not exist")
    cpps["failed"] += 1
else:
    with open(os.path.join(skill_draft_dir, "references", "columns.md")) as f:
        cols_text = f.read()
    undocumented = [c for c in profiled_columns if c not in cols_text]
    if len(undocumented) > 0:
        print(f"[FAIL] column coverage: {len(undocumented)} of {len(profiled_columns)} profiled columns absent from columns.md: {undocumented[:10]}")
        cpps["failed"] += 1
    else:
        print(f"[PASS] column coverage: all {len(profiled_columns)} profiled columns appear in columns.md")
        cpps["passed"] += 1

# Check: analytical-context.md structure — required subsections, exclusions, valid/invalid patterns
ac_text = None
if skill_draft_dir is not None and os.path.exists(os.path.join(skill_draft_dir, "references", "analytical-context.md")):
    with open(os.path.join(skill_draft_dir, "references", "analytical-context.md")) as f:
        ac_text = f.read()

if ac_text is None:
    print("[NOT VERIFIED] analytical-context sections: references/analytical-context.md not readable")
    cpps["not_verified"] += 1
else:
    ac_required = ["Study Design", "Population Coverage", "Temporal Scope"]
    ac_missing = [s for s in ac_required
                  if re.search(r"^#{2,4}\s+" + re.escape(s) + r"\b", ac_text, re.MULTILINE) is None]
    if len(ac_missing) > 0:
        print(f"[FAIL] analytical-context sections: {len(ac_missing)} of {len(ac_required)} required headings absent: {ac_missing}")
        cpps["failed"] += 1
    else:
        print(f"[PASS] analytical-context sections: all {len(ac_required)} required headings present ({', '.join(ac_required)})")
        cpps["passed"] += 1

if ac_text is None:
    print("[NOT VERIFIED] exclusions: references/analytical-context.md not readable")
    cpps["not_verified"] += 1
else:
    excl_match = re.search(r"^#{2,4}\s+What is NOT Included\b.*$", ac_text, re.MULTILINE | re.IGNORECASE)
    if excl_match is None:
        print("[FAIL] exclusions: no 'What is NOT Included' subsection in analytical-context.md")
        cpps["failed"] += 1
    else:
        next_head = re.search(r"^#{2,4}\s+\S", ac_text[excl_match.end():], re.MULTILINE)
        excl_body = ac_text[excl_match.end():excl_match.end() + next_head.start()] if next_head else ac_text[excl_match.end():]
        excl_items = [ln for ln in excl_body.split("\n")
                      if ln.strip().startswith(("-", "*")) or (ln.strip().startswith("|") and not re.match(r"^\|[\s:|-]+\|$", ln.strip()))]
        if len(excl_items) < 2:
            print(f"[FAIL] exclusions: 'What is NOT Included' lists {len(excl_items)} exclusion(s) (minimum 2)")
            cpps["failed"] += 1
        else:
            print(f"[PASS] exclusions: 'What is NOT Included' lists {len(excl_items)} exclusions (minimum 2)")
            cpps["passed"] += 1

if ac_text is None:
    print("[NOT VERIFIED] analysis patterns: references/analytical-context.md not readable")
    cpps["not_verified"] += 1
else:
    valid_match = re.search(r"^#{2,4}\s+Valid Analyses\b.*$", ac_text, re.MULTILINE)
    invalid_match = re.search(r"^#{2,4}\s+(Invalid|Invalid or Problematic) Analyses\b.*$", ac_text, re.MULTILINE)
    if valid_match is None or invalid_match is None:
        print(f"[FAIL] analysis patterns: Valid Analyses heading {'found' if valid_match else 'absent'}, Invalid Analyses heading {'found' if invalid_match else 'absent'}")
        cpps["failed"] += 1
    else:
        v_next = re.search(r"^#{2,4}\s+\S", ac_text[valid_match.end():], re.MULTILINE)
        v_body = ac_text[valid_match.end():valid_match.end() + v_next.start()] if v_next else ac_text[valid_match.end():]
        i_next = re.search(r"^#{2,4}\s+\S", ac_text[invalid_match.end():], re.MULTILINE)
        i_body = ac_text[invalid_match.end():invalid_match.end() + i_next.start()] if i_next else ac_text[invalid_match.end():]
        v_rows = [ln for ln in v_body.split("\n") if ln.strip().startswith("|") and not re.match(r"^\|[\s:|-]+\|$", ln.strip())][1:]
        i_rows = [ln for ln in i_body.split("\n") if ln.strip().startswith("|") and not re.match(r"^\|[\s:|-]+\|$", ln.strip())][1:]
        if len(v_rows) < 3 or len(i_rows) < 3:
            print(f"[FAIL] analysis patterns: {len(v_rows)} valid and {len(i_rows)} invalid patterns (minimum 3 each)")
            cpps["failed"] += 1
        else:
            print(f"[PASS] analysis patterns: {len(v_rows)} valid and {len(i_rows)} invalid patterns (minimum 3 each)")
            cpps["passed"] += 1

# Check: reference file density >= 3x SKILL.md lines
if skill_draft_dir is None or content is None:
    print("[NOT VERIFIED] reference density: SKILL.md line count or draft directory unavailable")
    cpps["not_verified"] += 1
else:
    ref_dir = os.path.join(skill_draft_dir, "references")
    ref_total = 0
    ref_files_counted = 0
    if os.path.isdir(ref_dir):
        for fname in sorted(os.listdir(ref_dir)):
            if fname.endswith(".md"):
                with open(os.path.join(ref_dir, fname)) as f:
                    ref_total += len(f.read().split("\n"))
                ref_files_counted += 1
    ratio = ref_total / len(lines) if len(lines) > 0 else 0
    if ref_files_counted == 0:
        print(f"[FAIL] reference density: 0 reference .md files in {ref_dir}")
        cpps["failed"] += 1
    elif ratio < 3:
        print(f"[FAIL] reference density: {ref_total:,} reference lines across {ref_files_counted} files vs {len(lines)} SKILL.md lines = {ratio:.1f}x (minimum 3x)")
        cpps["failed"] += 1
    else:
        print(f"[PASS] reference density: {ref_total:,} reference lines across {ref_files_counted} files vs {len(lines)} SKILL.md lines = {ratio:.1f}x (minimum 3x)")
        cpps["passed"] += 1

# Check: profiling scripts bundled with the skill, QA/cr scripts excluded
if "bundled_scripts" in not_applicable:
    print(f"[SKIPPED] bundled scripts: {not_applicable['bundled_scripts']}")
    cpps["skipped"] += 1
elif skill_draft_dir is None:
    print("[NOT VERIFIED] bundled scripts: skill_draft_dir is None")
    cpps["not_verified"] += 1
else:
    scripts_dir = os.path.join(skill_draft_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        print(f"[FAIL] bundled scripts: {scripts_dir} does not exist — profiling scripts were not bundled")
        cpps["failed"] += 1
    else:
        bundled = [f for f in sorted(os.listdir(scripts_dir)) if f.endswith((".py", ".R"))]
        cr_leaked = [f for f in bundled if "_cr" in f]
        if len(bundled) == 0:
            print(f"[FAIL] bundled scripts: {scripts_dir} contains 0 .py/.R profiling scripts")
            cpps["failed"] += 1
        elif len(cr_leaked) > 0:
            print(f"[FAIL] bundled scripts: {len(cr_leaked)} QA/cr script(s) bundled alongside {len(bundled)} scripts: {cr_leaked}")
            cpps["failed"] += 1
        else:
            print(f"[PASS] bundled scripts: {len(bundled)} profiling scripts bundled, 0 QA/cr scripts included")
            cpps["passed"] += 1

# Checks: manual checklist items — one line each, [NOT VERIFIED] until adjudicated
print("\nManual checklist items (one determination each):")
for item_key, item_desc in MANUAL_ITEMS:
    if item_key in not_applicable:
        print(f"[SKIPPED] {item_desc}: {not_applicable[item_key]}")
        cpps["skipped"] += 1
        continue
    determination = manual_determinations.get(item_key)
    if not isinstance(determination, str) or determination.strip() == "":
        print(f"[NOT VERIFIED] {item_desc}: manual checklist item — no determination recorded in manual_determinations['{item_key}']")
        cpps["not_verified"] += 1
    # MIN_EVIDENCE_CHARS: a determination reading "PASS: ok" satisfies a prefix test
    # while asserting nothing a reviewer can check. Twenty characters is not a
    # quality bar — it is the floor below which the text cannot be evidence at all.
    elif determination.strip().startswith("PASS:") and len(determination.strip()[len("PASS:"):].strip()) >= 20:
        print(f"[PASS] {item_desc}: manual determination — {determination.strip()[len('PASS:'):].strip()}")
        cpps["passed"] += 1
    elif determination.strip().startswith("FAIL:") and len(determination.strip()[len("FAIL:"):].strip()) >= 20:
        print(f"[FAIL] {item_desc}: manual determination — {determination.strip()[len('FAIL:'):].strip()}")
        cpps["failed"] += 1
    else:
        print(f"[NOT VERIFIED] {item_desc}: determination {determination.strip()[:60]!r} does not start with 'PASS: ' or 'FAIL: ' followed by at least 20 characters of evidence")
        cpps["not_verified"] += 1

# Count line, then verdict derived from the counts
cpps_checks_run = cpps["passed"] + cpps["warning"] + cpps["failed"]
if cpps["failed"] > 0 or cpps["not_verified"] > 0 or cpps_checks_run == 0:
    cpps_verdict = "FAILED"
elif cpps["warning"] > 0:
    cpps_verdict = "PASSED WITH WARNINGS"
else:
    cpps_verdict = "PASSED"

print(f"\nChecks: {cpps['passed']} passed, {cpps['warning']} warnings, {cpps['failed']} failed, {cpps['not_verified']} not verified, {cpps['skipped']} skipped")
print(f"CPP-SKILL VALIDATION: {cpps_verdict}")
print("=" * 60)

if cpps_verdict == "FAILED":
    raise ValueError("CPP-SKILL FAILED - see details above")
```

**`not_applicable` keys recognized by CPP-SKILL:** `bundled_scripts`, plus any `MANUAL_ITEMS` key (declare a manual item not applicable — for example `cross_dataset_join` when the source shares no keys with any DAAF skill — instead of leaving it unadjudicated).

### CPP Usage Notes

**Where the config comes from.** Every variable a CPP block reads is assigned in the profiling script's `# --- Config ---` region, with `None`/`NULL` meaning "the upstream step did not produce this". The old templates read variables that were sometimes never bound at all (`temporal_expected`, `skill_draft_dir`), which raised `NameError` — an unhandled crash rather than a reported outcome. Binding every input in Config converts those crashes into `[NOT VERIFIED]` lines.

**Conditional scripts and `not_applicable`.** The orchestrator's conditional-execution decisions (`WORKFLOW_PHASE_DO_PROFILING.md` § Conditional Execution Rules) are already documented in STATE.md with their reasoning. Carry the same reason into `not_applicable` so the checkpoint records a counted `[SKIPPED]` rather than an undeclared absence:

| Skipped script | Declare | Suggested reason |
|----------------|---------|------------------|
| 05 (temporal) | `not_applicable["temporal_detection"]` (CPP2) | "script 05 skipped — Part A found no date/time/year columns" |
| 08 (correlation) | `not_applicable["correlation_symmetry"]` (CPP3) | "script 08 skipped — fewer than 3 numeric columns" |
| 11 (reconcile) | *nothing* | `documentation_provided=False` is checked and passes with evidence; do not declare it skipped |

**Reported-status mapping.** As with CP1-CP4, `PASSED WITH WARNINGS` on the log line maps to reported status **`WARNING`** in the data-ingest agent's return; `PASSED` maps to `PASSED`, `FAILED` to `FAILED`. Report the mapped value, never the raw log string.

**Comparator note.** `scripts/compare_execution_logs.py` matches `CP\d` verdict lines; `CPP\d` lines are not currently machine-compared across runs. The count line is therefore the primary machine-readable evidence for CPP checkpoints, and the human reviewer (code-reviewer at QAP) is the consumer that matters. Do not assume a CPP regression would be caught by log comparison.

---

## Synthetic-Path Validation Checkpoints (Data Onboarding, synthetic path)

> **Mode:** These checkpoints apply to Data Onboarding Mode's **synthetic (privacy-preserving) path** only — the branch taken when the raw data must never enter the container. They replace CPP1-CPP4, which cannot run here because there is no source file to load and recompute against: everything DAAF knows about the data arrives as a profile report.
>
> **This section is canonical.** The blocks below are the only maintained copies of the CPS code. `.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_SYNTHETIC.md` tells the executing agent *when* to embed each checkpoint and supplies the per-stage `# --- Config ---` values, then points here for the block itself. Copy the block verbatim into the validation script's `# --- Validate ---` section; do not paraphrase it and do not maintain a second copy elsewhere.

### CPS Overview

CPS checkpoints follow the same outcome vocabulary, count line, and verdict rules as CP1-CP4 and CPP1-CPP4 (see § Per-Check Outcome Vocabulary, § Count Line and Verdict Line, § Applicability Configuration above). Each block prints `Checks: ...` then `CPS-{name} VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`, and raises/stops on `FAILED` — but only after every check has reported, so the log records the complete picture rather than aborting at the first problem.

| Checkpoint | Stage | Runs in | Classification | Purpose | FAILED when |
|------------|-------|---------|----------------|---------|-------------|
| **CPS-INTAKE** | DS-3 (report intake) | `scripts/profile_report_intake/01_validate-report.py` (`.R` for R) | `checkpoint:auto`, script-halting | The returned profile report is structurally sound, internally consistent, and free of disclosure-shaped content | Schema violated, a released count below threshold, a report threshold below the approved one, a report beyond the approved tier ceiling (its `settings.tier` above the approved tier, or a `relationships` block released below tier 3), released totals that do not reconcile (a categorical or cross-tab residual recoverable by differencing), a hidden cross-tab cell recoverable from the released row and column totals (a lone hidden cell or any other bridge), a missing-partner count below the threshold recoverable from those totals and the released missing counts, an available regression with a complement group below the threshold, a categorical block that repeats a level label, a cross-tab that names one column twice or repeats another entry's pair, an available cross-tab whose rows or cols differ from its columns' released level counts, an incomplete disclosure sweep, a raw-value-shaped field, a field outside the spec's key allow-lists or vocabularies — or any input those checks need is missing and not declared not-applicable |
| **CPS-GEN** | DS-5 (post-generation) | `scripts/synth_generate/01_generate-synthetic.py` (`.R` for R), at the end of the generation script (T4: `scripts/synth_generate/01_import-synthetic.{py,R}`, at the end of the import) | `checkpoint:auto`, script-halting | The generated synthetic data matches the profile it was built from and fabricates nothing the report withheld | Row count/schema mismatch, a synthetic level outside the released level set, a required `__OTHER__` bucket missing, a synthetic column outside the text-comparable types where it must be compared with released labels, a non-numeric column under a released percentile grid or correlation, an identifier that is not unique or carries a released value, a configured `tier` that differs from the report's declared `settings.tier`, no recorded seed, or `seed_exception` misused (set at tier 1–3, or alongside `seed`) — or any input those checks need is missing and not declared not-applicable |

**Relationship to the review family.** CPS-INTAKE and CPS-GEN are the script-halting counterparts of QAS-B and QAS-C (`agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints). The CPS blocks implement the *computable* subset of the b- and c-checks; the reviewer re-derives the rest and reads the source of these scripts. A gate reads both — a CPS `PASSED` is necessary, never sufficient.

**Why `[NOT VERIFIED]` matters here specifically.** On every other path a missing input can be recovered by going back to the data. Here the data is unreachable by construction, so an absent report field is not a temporary gap — it is the end of the evidence. A check that cannot run therefore says so and fails the checkpoint rather than passing on a report the container cannot cross-examine.

### CPS-INTAKE: Profile Report Intake Validation (DS-3)

**When:** Immediately after the returned profile report lands in `data/profile_report/` and before any generation work reads it (DS-3).

CPS-INTAKE re-derives every claim the report makes from the report's own numbers. It never trusts the report's embedded `validation.all_passed` as evidence of anything except that the user's profiler said so — that flag is a claim the block checks, not a result it consumes. Four of its twelve checks are disclosure-critical and carry no legal `not_applicable` key; declaring one of them is itself a `[FAIL]`, and the check still runs.

One input deliberately comes from outside the report: `expected_threshold`, the suppression threshold the researcher approved at tier selection (PSU-DS1) and recorded in STATE.md § Synthetic Path Tracking (**Suppression Threshold**). The disclosure sweep gates on it as well as on the report's own `settings.suppression_threshold`, so a report cannot lower its own bar. The config `tier` is treated the same way: it is the tier the researcher approved at PSU-DS1, and a report whose `settings.tier` exceeds it, or that releases a `relationships` block below tier 3, fails the sweep — a report cannot widen its own release scope either. Released totals must reconcile, so no hidden count can be recovered by subtraction: in the sweep, a categorical block's level counts must sum to its `n` (and that `n` must equal its column's `nonmissing_n`); in `crosstab_schema_and_suppression`, a cross-tab entry's visible cells must not sum past its `n`, and must sum to it exactly when no cell is hidden. The same check keeps hidden cross-tab cells hidden: with every row and column total treated as released, no hidden cell may be a bridge, because a bridge is exactly recoverable from those totals. A lone hidden cell in its row or column is the simplest bridge; a hidden cell that is the only link between two otherwise separate groups of hidden cells is one too. The same test covers the records whose partner column is missing: the categorical blocks count them while the grid does not, so a sub-threshold count of them must not be pinned by the released totals either. In the sweep, a named regression is released only when each column's complement group, the records with that column but not the other, is empty or at least the threshold, because the released mean and the fitted line together give the summed value of that group. Each cross-tab must also sit on its own unordered pair of two distinct column names, and an available one on the released categories of both (its `rows` and `cols` equal to the two columns' released level counts), so a second table of the same named pair, or a row for a level pooled into `__OTHER__`, cannot be differenced against what the report already releases. The guarantee is per entry and stops at the row and column totals: no hidden cell or missing-partner count is recoverable from one cross-tab together with the released totals, and no named regression has a small complement group. At tier 3 the released Cramér's V, computed on the full table, can let a determined analyst reconstruct small cells from the released margins, or split the pooled `__OTHER__` category into its rare source levels' counts; and several cross-tabs or regressions that share a column, or two encodings of one variable under different names, can disclose together what each protects alone. No check here detects either — both are accepted, documented tier-3 limitations (§ CPS Usage Notes). The block also never stops early on a malformed report: a field of the wrong JSON type becomes a named `[FAIL]` or `[NOT VERIFIED]`, every check prints its own outcome line, and the count and verdict lines always print. These rules are spelled out in § CPS Usage Notes.

**Embedded in:** `scripts/profile_report_intake/01_validate-report.py` (`.R` for R)

**Config stanza (the block's own `# --- Config ---` region, reproduced for reference — assign your values there):**
```python
# --- Config ---
report_path = None       # path to the returned profile report JSON; None if intake staged no file
tier = None              # 1 | 2 | 3 — the tier approved at PSU-DS1 (STATE Disclosure Tier; at T4, T4 Companion Profile Tier) — never the report's settings.tier; None if not recorded
expected_threshold = None  # the suppression threshold approved at tier selection (STATE.md § Synthetic Path Tracking); None if not recorded
not_applicable = {}      # e.g. {"correlation_matrix_wellformed": "tier 2 — the report releases no correlations"}
```

```python
# --- CPS-INTAKE Validation ---
# INTENT: Verify that a returned profile report is structurally sound, internally
# consistent, and free of disclosure-shaped content before anything downstream
# generates data from it.
# REASONING: The report is the only artifact that crosses the privacy boundary, so
# every claim must be re-derived from its own numbers rather than taken from its
# embedded all_passed flag. Each check emits exactly one token and increments
# exactly one counter; the verdict is derived from the counters, never asserted.
# ASSUMES: report_path / tier / expected_threshold / not_applicable are assigned in the
# `# --- Config ---` region below; report_path is None when intake staged no file.
# A field of the wrong JSON type never raises: it becomes a [FAIL] when it is the
# field a check validates, or a [NOT VERIFIED] when it is evidence a check needs.
import json
import re
from pathlib import Path

# --- Config ---
report_path = None       # path to the returned profile report JSON; None if intake staged no file
tier = None              # 1 | 2 | 3 — the tier approved at PSU-DS1 (STATE Disclosure Tier; at T4, T4 Companion Profile Tier) — never the report's settings.tier; None if not recorded
expected_threshold = None  # the suppression threshold approved at tier selection (STATE.md § Synthetic Path Tracking); None if not recorded
not_applicable = {}      # e.g. {"correlation_matrix_wellformed": "tier 2 — the report releases no correlations"}

print("\n" + "=" * 60)
print("CPS-INTAKE VALIDATION: PROFILE REPORT INTAKE")
print("=" * 60)

cps_intake = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# INTENT: A declared skip without a reason is indistinguishable from a silent one, so
# it is dropped — but the key stays visible to the two sweeps below, so an empty
# reason cannot be used to smuggle a declaration past the non-declarable or
# unrecognized-key gates. The declarable check it named does not then run either:
# `cpsi_empty_reason` carries it to a [NOT VERIFIED], because printing a [PASS]
# would answer a question the author explicitly withdrew.
cpsi_declared_keys = sorted(not_applicable)
cpsi_empty_reason = {k for k, v in not_applicable.items() if not (isinstance(v, str) and v.strip())}
not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}

# INTENT: Disclosure-critical checks may never be declared not applicable.
# REASONING: Once a report has crossed the boundary it cannot be recalled, so the
# only safe reading of "this disclosure check does not apply" is that someone
# wanted it not to run. The declaration is itself the finding, and the check
# still runs afterwards on the un-declared path.
cpsi_non_declarable = ("no_released_count_below_threshold", "no_raw_value_shaped_fields",
                       "identifier_columns_value_free", "crosstab_schema_and_suppression")
for cpsi_key in cpsi_non_declarable:
    if cpsi_key in cpsi_declared_keys:
        print(f"[FAIL] {cpsi_key}: non-declarable check declared not_applicable under key '{cpsi_key}'")
        cps_intake["failed"] += 1
        not_applicable.pop(cpsi_key, None)

# INTENT: A not_applicable key that names no check of this block is a silent no-op.
# REASONING: A typo'd or stale key would otherwise declare nothing and be ignored,
# leaving the author believing a check was skipped when it in fact ran (or the
# reverse). Naming it once is the only way the log can carry the discrepancy.
cpsi_declarable = ("report_version", "required_top_level_keys", "row_count_positive",
                   "percentiles_monotone", "category_counts_le_rowcount",
                   "missing_rate_in_unit_interval", "correlation_matrix_wellformed",
                   "embedded_validation_complete")
for cpsi_key in cpsi_declared_keys:
    if cpsi_key in cpsi_non_declarable or cpsi_key in cpsi_declarable:
        continue
    print(f"[FAIL] not_applicable: unrecognized key '{cpsi_key}' (declarable keys: {', '.join(cpsi_declarable)})")
    cps_intake["failed"] += 1
    not_applicable.pop(cpsi_key, None)

# INTENT: Bind every downstream input once, so a missing piece becomes a named
# [NOT VERIFIED] rather than a KeyError halfway through the block.
cpsi_parse_error = "report did not parse as JSON (parser message withheld: it can quote report content)"
cpsi_report = None
cpsi_load_error = None
cpsi_report_strings = set()
if report_path is None:
    cpsi_load_error = "report_path is not set — no report was staged for intake"
elif not Path(report_path).is_file():
    cpsi_load_error = f"no file at report_path '{report_path}'"
else:
    # REASONING: the parser's own message is withheld — it can quote report text,
    # and the R parser words it differently, so neither belongs on an outcome line.
    # Parsing is STRICT, with the same outcome as the R block and as CPS-GEN on every
    # file: `parse_constant=int` makes the non-JSON literals NaN / Infinity / -Infinity
    # a parse error (int("NaN") raises ValueError), as they are in jsonlite: Python's
    # default would admit them, and a NaN in a field no check reads then PASSED here
    # while the R block FAILED the same file. A duplicate object key at any depth is a
    # parse error too: Python's dict keeps the LAST value silently while jsonlite keeps
    # BOTH and `[[` reads the FIRST, so one file was judged on two different values.
    # The first pass keeps every object as its raw (key, value) list, so a repeat stays
    # visible to the sweep below; the second builds the dicts the checks read.
    # RecursionError is caught because json.loads recurses once per nesting level and
    # a deep enough file used to escape the block with no verdict.
    cpsi_pairs = None
    cpsi_text = None
    # INTENT: Refuse, before either parser runs, every input the two parsers would read
    # differently.
    # REASONING: jsonlite accepts a leading UTF-8 byte-order mark with only a warning
    # where json.loads refuses it; jsonlite silently cuts a string at an escaped NUL
    # (\u0000) and replaces an unpaired surrogate escape, where Python keeps both. A raw
    # NUL byte and invalid UTF-8 are refused by both parsers, but R's text reader would
    # stop at the NUL first. All of these are therefore parse errors, decided on the
    # bytes and on the escape sequences, the same way in both blocks.
    try:
        cpsi_bytes = Path(report_path).read_bytes()
        if cpsi_bytes[:3] != b"\xef\xbb\xbf" and b"\x00" not in cpsi_bytes:
            cpsi_text = cpsi_bytes.decode("utf-8")
    except (ValueError, OSError):
        cpsi_text = None
    if cpsi_text is not None:
        # INTENT: Walk the escape sequences left to right. An escaped backslash is one
        # token, so the text `\\u0000` (a backslash, then u0000) is not an escape.
        # ASSUMES: a \u escape is exactly six characters, so a surrogate pair is a high
        # escape immediately followed by a low one.
        cpsi_toks = [(cpsi_m.start(), cpsi_m.group(0)) for cpsi_m in re.finditer(r"\\(?:u[0-9a-fA-F]{4}|[^u])", cpsi_text)]
        cpsi_cps = [int(cpsi_t[1][2:], 16) if cpsi_t[1][1] == "u" else -1 for cpsi_t in cpsi_toks]
        for cpsi_i in range(len(cpsi_toks)):
            cpsi_cp = cpsi_cps[cpsi_i]
            cpsi_hi_ok = (cpsi_i + 1 < len(cpsi_toks) and cpsi_toks[cpsi_i + 1][0] == cpsi_toks[cpsi_i][0] + 6
                          and 0xDC00 <= cpsi_cps[cpsi_i + 1] <= 0xDFFF)
            cpsi_lo_ok = (cpsi_i > 0 and cpsi_toks[cpsi_i - 1][0] == cpsi_toks[cpsi_i][0] - 6
                          and 0xD800 <= cpsi_cps[cpsi_i - 1] <= 0xDBFF)
            if (cpsi_cp == 0 or (0xD800 <= cpsi_cp <= 0xDBFF and not cpsi_hi_ok)
                    or (0xDC00 <= cpsi_cp <= 0xDFFF and not cpsi_lo_ok)):
                cpsi_text = None
                break
    if cpsi_text is not None:
        # INTENT: A JSON number token longer than 64 characters (sign, digits, fraction
        # and exponent together), outside strings, is a parse error.
        # REASONING: The two parsers split on long numbers: Python refuses an integer of
        # more than 4300 digits while jsonlite reads it (and any huge literal) as Inf, so
        # the same file got two verdicts. No number the profiler writes comes near 64
        # characters. Strings are blanked first (an escaped quote stays inside its
        # string), so digits inside a label are never counted; the R block applies the
        # same two patterns to the same text.
        cpsi_unstrung = re.sub(r'(?s)"[^"\\]*(?:\\.[^"\\]*)*"', '""', cpsi_text)
        if re.search(r"[-+0-9.eE]{65,}", cpsi_unstrung) is not None:
            cpsi_text = None
    if cpsi_text is None:
        cpsi_load_error = cpsi_parse_error
    else:
        try:
            cpsi_pairs = json.loads(cpsi_text, parse_constant=int, object_pairs_hook=list)
            cpsi_report = json.loads(cpsi_text, parse_constant=int)
        except (ValueError, RecursionError):
            cpsi_load_error = cpsi_parse_error
            cpsi_report = None
    # INTENT: Iterative sweep over the pair-list tree (no recursion, so depth cannot
    # raise) that refuses a duplicate key and any container nested deeper than 64
    # levels, counting the top-level object as level 1. Under the list hook an object
    # is a list of (key, value) tuples ({} is an empty list); a decoded array never
    # holds a tuple, so every object and array is one list and one level. The sweep
    # also collects every key and string value, so any report text a line prints can
    # be escaped (see the escape table below).
    # REASONING: The two parsers give up at different depths (Python's recursion limit,
    # jsonlite's own), so between those limits one block judged a file the other refused.
    # An explicit cap far above the schema's own depth (6) makes the outcome depend on
    # the file, not on the parser.
    cpsi_max_depth = 64
    cpsi_stack = [] if cpsi_report is None else [(cpsi_pairs, 1)]
    while len(cpsi_stack) > 0:
        cpsi_node, cpsi_depth = cpsi_stack.pop()
        if isinstance(cpsi_node, str):
            cpsi_report_strings.add(cpsi_node)
            continue
        if not isinstance(cpsi_node, list):
            continue
        if cpsi_depth > cpsi_max_depth:
            cpsi_load_error = cpsi_parse_error
            cpsi_report = None
            break
        if len(cpsi_node) > 0 and all(isinstance(cpsi_e, tuple) for cpsi_e in cpsi_node):
            if len(set(cpsi_e[0] for cpsi_e in cpsi_node)) != len(cpsi_node):
                cpsi_load_error = cpsi_parse_error
                cpsi_report = None
                break
            cpsi_report_strings.update(cpsi_e[0] for cpsi_e in cpsi_node)
            cpsi_stack.extend((cpsi_e[1], cpsi_depth + 1) for cpsi_e in cpsi_node)
        else:
            cpsi_stack.extend((cpsi_e, cpsi_depth + 1) for cpsi_e in cpsi_node)
if cpsi_report is not None and not isinstance(cpsi_report, dict):
    cpsi_load_error = "report parsed, but its top level is not a JSON object"
    cpsi_report = None

# INTENT: Escape every report-derived string before it reaches an outcome line,
# identically in both languages: a character outside printable ASCII (0x20-0x7E)
# prints as \uXXXX in lowercase hex, and one above U+FFFF as its UTF-16 surrogate pair.
# REASONING: A column name or key carrying a newline or control character could
# otherwise forge an extra outcome line (a fake count line or verdict), and a non-ASCII
# one could fail the write on a console that cannot encode it. The table covers every
# key and string value of the parsed report, so each print site looks its text up in
# it. Config strings (report_path, not_applicable reasons) are the researcher's own
# text and print as written.
cpsi_esc = {cpsi_s: "".join(cpsi_ch if " " <= cpsi_ch <= "~" else (
    "\\u%04x" % ord(cpsi_ch) if ord(cpsi_ch) < 0x10000 else "\\u%04x\\u%04x" % (
        0xD800 + ((ord(cpsi_ch) - 0x10000) >> 10), 0xDC00 + ((ord(cpsi_ch) - 0x10000) & 0x3FF)))
    for cpsi_ch in cpsi_s) for cpsi_s in cpsi_report_strings}
# INTENT: Value-shaped key names are matched case-insensitively over ASCII letters
# only, so both languages fold exactly the same characters (str.lower() and tolower()
# each fold some non-ASCII letters, and not the same ones).
cpsi_ascii_lower = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")

# INTENT: One numeric model for both languages. A JSON number is usable only when it
# is finite and |v| < 2^53 — the profiler refuses larger magnitudes, every such value
# is exact in a double, and jsonlite turns a 401-digit integer into Inf where Python
# keeps an exact int (math.isfinite on that int raises OverflowError). Whole numbers
# are compared by value (40 and 40.0 agree), because JSON does not type them apart.
# ASSUMES: chained comparisons short-circuit after the isinstance test, so a string
# or list never reaches `<`.
cpsi_max_exact = 2 ** 53

cpsi_columns_raw = None
cpsi_columns = None
cpsi_row_count = None
cpsi_threshold = None
cpsi_rep_tier = None
cpsi_relationships = None
cpsi_crosstabs = []
cpsi_crosstabs_not_array = False
if cpsi_report is not None:
    if isinstance(cpsi_report.get("columns"), list):
        cpsi_columns_raw = cpsi_report["columns"]
        cpsi_columns = [c for c in cpsi_columns_raw if isinstance(c, dict)]
    if isinstance(cpsi_report.get("settings"), dict):
        cpsi_threshold = cpsi_report["settings"].get("suppression_threshold")
        cpsi_rep_tier = cpsi_report["settings"].get("tier")
    if isinstance(cpsi_report.get("dataset"), dict):
        cpsi_row_count = cpsi_report["dataset"].get("row_count")
    if isinstance(cpsi_report.get("relationships"), dict):
        cpsi_relationships = cpsi_report["relationships"]
        if isinstance(cpsi_relationships.get("crosstabs"), list):
            cpsi_crosstabs = cpsi_relationships["crosstabs"]
        elif cpsi_relationships.get("crosstabs") is not None:
            cpsi_crosstabs_not_array = True
cpsi_col_names = set() if cpsi_columns is None else {c["name"] for c in cpsi_columns if isinstance(c.get("name"), str)}
cpsi_rc_ok = (isinstance(cpsi_row_count, (int, float)) and not isinstance(cpsi_row_count, bool)
              and -cpsi_max_exact < cpsi_row_count < cpsi_max_exact
              and cpsi_row_count == int(cpsi_row_count) and cpsi_row_count > 0)
cpsi_rc = int(cpsi_row_count) if cpsi_rc_ok else None
cpsi_tier_ok = not isinstance(tier, bool) and tier in (1, 2, 3)
cpsi_tier_label = str(int(tier)) if cpsi_tier_ok else ("unrecorded" if tier is None else "invalid")
cpsi_rep_tier_ok = not isinstance(cpsi_rep_tier, bool) and isinstance(cpsi_rep_tier, (int, float)) and cpsi_rep_tier in (1, 2, 3)
# INTENT: "released relationships content" is any `relationships` value other than an
# absent key, JSON null, or an empty object / array.
cpsi_rel_content = (cpsi_report is not None and cpsi_report.get("relationships") is not None
                    and not (isinstance(cpsi_report["relationships"], (dict, list)) and len(cpsi_report["relationships"]) == 0))

# Check: report_version — the accepted schema, never a relabelled legacy report
if "report_version" in not_applicable:
    print(f"[SKIPPED] report_version: {not_applicable['report_version']}")
    cps_intake["skipped"] += 1
elif "report_version" in cpsi_empty_reason:
    print("[NOT VERIFIED] report_version: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] report_version: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif "report_version" not in cpsi_report:
    print("[NOT VERIFIED] report_version: the report carries no report_version field")
    cps_intake["not_verified"] += 1
elif not (isinstance(cpsi_report["report_version"], str) and 0 < len(cpsi_report["report_version"]) <= 16
          and all(ch in "0123456789." for ch in cpsi_report["report_version"])):
    # REASONING: only a dotted version string is echoed; anything else could be
    # report content, so it is named by shape, never quoted.
    print("[FAIL] report_version: the report_version field is not a dotted version string — a legacy or unknown report is never relabelled into compliance")
    cps_intake["failed"] += 1
elif cpsi_report["report_version"] != "2.0":
    print(f"[FAIL] report_version: '{cpsi_report['report_version']}' is not the accepted 2.0 schema — a legacy or unknown report is never relabelled into compliance")
    cps_intake["failed"] += 1
else:
    print("[PASS] report_version: '2.0' — the accepted schema version")
    cps_intake["passed"] += 1

# Check: required top-level keys — set equality against the 2.0 schema
# ASSUMES: `relationships` is optional below tier 3 and required at tier 3.
cpsi_required_top = {"report_version", "dataset_name", "generated_utc", "generator",
                     "settings", "dataset", "columns", "validation"}
if "required_top_level_keys" in not_applicable:
    print(f"[SKIPPED] required_top_level_keys: {not_applicable['required_top_level_keys']}")
    cps_intake["skipped"] += 1
elif "required_top_level_keys" in cpsi_empty_reason:
    print("[NOT VERIFIED] required_top_level_keys: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] required_top_level_keys: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
else:
    cpsi_present = set(cpsi_report.keys())
    cpsi_missing = sorted(cpsi_required_top - cpsi_present)
    cpsi_unexpected = sorted(cpsi_present - cpsi_required_top - {"relationships"})
    if cpsi_tier_ok and tier == 3 and "relationships" not in cpsi_present:
        cpsi_missing = sorted(cpsi_missing + ["relationships"])
    # INTENT: a present key of the wrong JSON type is a schema violation this check
    # owns (report_version's own type is judged by the report_version check).
    cpsi_top_kinds = {"dataset_name": str, "generated_utc": str, "generator": dict, "settings": dict,
                      "dataset": dict, "columns": list, "validation": dict, "relationships": dict}
    cpsi_wrong_kind = sorted(k for k, t in cpsi_top_kinds.items() if k in cpsi_present and not isinstance(cpsi_report[k], t))
    if len(cpsi_missing) > 0 or len(cpsi_unexpected) > 0 or len(cpsi_wrong_kind) > 0:
        print(f"[FAIL] required_top_level_keys: missing [{', '.join(cpsi_missing)}], unexpected [{', '.join(cpsi_esc[k] for k in cpsi_unexpected)}]"
              + (f", wrong JSON type [{', '.join(cpsi_wrong_kind)}]" if len(cpsi_wrong_kind) > 0 else "")
              + f" (tier {cpsi_tier_label})")
        cps_intake["failed"] += 1
    else:
        print(f"[PASS] required_top_level_keys: {len(cpsi_required_top)} of {len(cpsi_required_top)} required keys present, 0 unexpected (tier {cpsi_tier_label})")
        cps_intake["passed"] += 1

# Check: row count is a positive integer — the denominator every later check needs
if "row_count_positive" in not_applicable:
    print(f"[SKIPPED] row_count_positive: {not_applicable['row_count_positive']}")
    cps_intake["skipped"] += 1
elif "row_count_positive" in cpsi_empty_reason:
    print("[NOT VERIFIED] row_count_positive: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] row_count_positive: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_row_count is None:
    print("[NOT VERIFIED] row_count_positive: dataset.row_count is absent — no denominator for the count checks")
    cps_intake["not_verified"] += 1
elif not cpsi_rc_ok:
    print("[FAIL] row_count_positive: dataset.row_count is not a positive whole number")
    cps_intake["failed"] += 1
else:
    print(f"[PASS] row_count_positive: dataset.row_count = {cpsi_rc:,} over {len(cpsi_columns_raw) if cpsi_columns_raw is not None else 0} declared columns")
    cps_intake["passed"] += 1

# Check: released percentile grids are non-decreasing in probability order
# REASONING: A column that declares a role but carries no block is missing
# evidence ([NOT VERIFIED]); a report that declares no columns of that role at
# all is a structural fact about the tier ([SKIPPED]).
cpsi_pctl_order = ["p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
cpsi_num_cols = [] if cpsi_columns is None else [c for c in cpsi_columns if c.get("role") == "numeric"]
if "percentiles_monotone" in not_applicable:
    print(f"[SKIPPED] percentiles_monotone: {not_applicable['percentiles_monotone']}")
    cps_intake["skipped"] += 1
elif "percentiles_monotone" in cpsi_empty_reason:
    print("[NOT VERIFIED] percentiles_monotone: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] percentiles_monotone: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_columns is None:
    print("[NOT VERIFIED] percentiles_monotone: the report carries no columns array")
    cps_intake["not_verified"] += 1
elif len(cpsi_num_cols) == 0:
    print(f"[SKIPPED] percentiles_monotone: report declares 0 numeric columns at tier {cpsi_tier_label} (0 grids, 0 percentiles)")
    cps_intake["skipped"] += 1
else:
    cpsi_grids = 0
    cpsi_points = 0
    cpsi_bad = []
    cpsi_absent = []
    for cpsi_col in cpsi_num_cols:
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        cpsi_blk = cpsi_col.get("numeric")
        if not isinstance(cpsi_blk, dict):
            cpsi_absent.append(f"column '{cpsi_name}' declares role numeric but has no numeric block")
        elif "percentiles" not in cpsi_blk:
            # A withheld / all-missing / constant shape legitimately carries no grid.
            if not (cpsi_blk.get("withheld") is True or cpsi_blk.get("all_missing") is True
                    or cpsi_blk.get("constant") is True):
                cpsi_absent.append(f"column '{cpsi_name}' has a numeric block with no percentiles and no withheld/all_missing/constant marker")
        elif not isinstance(cpsi_blk["percentiles"], dict) or len(cpsi_blk["percentiles"]) == 0:
            cpsi_absent.append(f"column '{cpsi_name}' has an empty or non-object percentiles block")
        else:
            cpsi_grid = cpsi_blk["percentiles"]
            cpsi_unknown = [k for k in cpsi_grid if k not in cpsi_pctl_order]
            cpsi_vals = [cpsi_grid[k] for k in cpsi_pctl_order if k in cpsi_grid]
            cpsi_nonreal = [v for v in cpsi_vals
                            if not (isinstance(v, (int, float)) and not isinstance(v, bool)
                                    and -cpsi_max_exact < v < cpsi_max_exact)]
            if len(cpsi_unknown) > 0:
                cpsi_bad.append(f"column '{cpsi_name}' carries unrecognized percentile keys [{', '.join(cpsi_esc[k] for k in sorted(cpsi_unknown))}]")
            elif len(cpsi_nonreal) > 0:
                cpsi_absent.append(f"column '{cpsi_name}' has a non-numeric or out-of-range percentile value")
            else:
                cpsi_grids += 1
                cpsi_points += len(cpsi_vals)
                cpsi_keys_in_order = [k for k in cpsi_pctl_order if k in cpsi_grid]
                for cpsi_i in range(1, len(cpsi_vals)):
                    if cpsi_vals[cpsi_i] < cpsi_vals[cpsi_i - 1]:
                        cpsi_bad.append(f"column '{cpsi_name}' is non-monotone between {cpsi_keys_in_order[cpsi_i - 1]} and {cpsi_keys_in_order[cpsi_i]}")
                        break
    if len(cpsi_bad) > 0:
        print(f"[FAIL] percentiles_monotone: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    elif len(cpsi_absent) > 0:
        print(f"[NOT VERIFIED] percentiles_monotone: {cpsi_absent[0]}" + (f" (+{len(cpsi_absent) - 1} more)" if len(cpsi_absent) > 1 else ""))
        cps_intake["not_verified"] += 1
    else:
        print(f"[PASS] percentiles_monotone: {len(cpsi_num_cols)} numeric columns, {cpsi_grids} released grids x {cpsi_points} percentiles checked, all non-decreasing")
        cps_intake["passed"] += 1

# Check: every category count, and each column's level total, is <= row_count
cpsi_cat_cols = [] if cpsi_columns is None else [c for c in cpsi_columns if c.get("role") == "categorical"]
if "category_counts_le_rowcount" in not_applicable:
    print(f"[SKIPPED] category_counts_le_rowcount: {not_applicable['category_counts_le_rowcount']}")
    cps_intake["skipped"] += 1
elif "category_counts_le_rowcount" in cpsi_empty_reason:
    print("[NOT VERIFIED] category_counts_le_rowcount: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] category_counts_le_rowcount: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_columns is None:
    print("[NOT VERIFIED] category_counts_le_rowcount: the report carries no columns array")
    cps_intake["not_verified"] += 1
elif len(cpsi_cat_cols) == 0:
    print(f"[SKIPPED] category_counts_le_rowcount: report declares 0 categorical columns at tier {cpsi_tier_label} (0 levels)")
    cps_intake["skipped"] += 1
elif not cpsi_rc_ok:
    print("[NOT VERIFIED] category_counts_le_rowcount: dataset.row_count is absent or not a positive integer — no comparison basis")
    cps_intake["not_verified"] += 1
else:
    cpsi_levels_seen = 0
    cpsi_bad = []
    cpsi_absent = []
    for cpsi_col in cpsi_cat_cols:
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        cpsi_blk = cpsi_col.get("categorical")
        if not isinstance(cpsi_blk, dict):
            cpsi_absent.append(f"column '{cpsi_name}' declares role categorical but has no categorical block")
        elif not isinstance(cpsi_blk.get("levels"), list):
            cpsi_absent.append(f"column '{cpsi_name}' has a categorical block with no levels array")
        else:
            cpsi_total = 0
            for cpsi_i, cpsi_lv in enumerate(cpsi_blk["levels"]):
                if not isinstance(cpsi_lv, dict) or "count" not in cpsi_lv:
                    cpsi_absent.append(f"column '{cpsi_name}' level index {cpsi_i} carries no count field")
                    continue
                cpsi_v = cpsi_lv["count"]
                if not (isinstance(cpsi_v, (int, float)) and not isinstance(cpsi_v, bool)
                        and -cpsi_max_exact < cpsi_v < cpsi_max_exact and cpsi_v == int(cpsi_v)):
                    cpsi_bad.append(f"column '{cpsi_name}' level index {cpsi_i} has a non-integer count")
                    continue
                cpsi_levels_seen += 1
                cpsi_total += cpsi_v
                if cpsi_v > cpsi_rc:
                    cpsi_bad.append(f"column '{cpsi_name}' level index {cpsi_i} exceeds row_count")
            if cpsi_total > cpsi_rc:
                cpsi_bad.append(f"column '{cpsi_name}' level total exceeds row_count")
    if len(cpsi_bad) > 0:
        print(f"[FAIL] category_counts_le_rowcount: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    elif len(cpsi_absent) > 0:
        print(f"[NOT VERIFIED] category_counts_le_rowcount: {cpsi_absent[0]}" + (f" (+{len(cpsi_absent) - 1} more)" if len(cpsi_absent) > 1 else ""))
        cps_intake["not_verified"] += 1
    else:
        print(f"[PASS] category_counts_le_rowcount: {len(cpsi_cat_cols)} categorical columns, {cpsi_levels_seen} levels, every count and column total <= row_count {cpsi_rc:,}")
        cps_intake["passed"] += 1

# Check: missingness rates are finite reals in [0, 1] and agree with nonmissing_n
cpsi_rated = [] if cpsi_columns is None else [c for c in cpsi_columns if "missing_rate" in c]
if "missing_rate_in_unit_interval" in not_applicable:
    print(f"[SKIPPED] missing_rate_in_unit_interval: {not_applicable['missing_rate_in_unit_interval']}")
    cps_intake["skipped"] += 1
elif "missing_rate_in_unit_interval" in cpsi_empty_reason:
    print("[NOT VERIFIED] missing_rate_in_unit_interval: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] missing_rate_in_unit_interval: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_columns is None:
    print("[NOT VERIFIED] missing_rate_in_unit_interval: the report carries no columns array")
    cps_intake["not_verified"] += 1
elif len(cpsi_rated) == 0 and cpsi_tier_ok and tier == 1:
    print("[SKIPPED] missing_rate_in_unit_interval: tier 1 releases no missingness rates (0 of 0 columns carry one)")
    cps_intake["skipped"] += 1
elif len(cpsi_rated) == 0:
    print(f"[NOT VERIFIED] missing_rate_in_unit_interval: no column carries a missing_rate at tier {cpsi_tier_label}, where rates are expected")
    cps_intake["not_verified"] += 1
else:
    cpsi_bad = []
    cpsi_absent = []
    cpsi_agreed = 0
    for cpsi_col in cpsi_rated:
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        cpsi_v = cpsi_col["missing_rate"]
        if not (isinstance(cpsi_v, (int, float)) and not isinstance(cpsi_v, bool)
                and -cpsi_max_exact < cpsi_v < cpsi_max_exact):
            cpsi_bad.append(f"column '{cpsi_name}' has a non-finite or non-numeric missing_rate")
        elif cpsi_v < 0.0 or cpsi_v > 1.0:
            cpsi_bad.append(f"column '{cpsi_name}' has a missing_rate outside [0, 1]")
        else:
            cpsi_nm = cpsi_col.get("nonmissing_n")
            if not (isinstance(cpsi_nm, (int, float)) and not isinstance(cpsi_nm, bool)
                    and -cpsi_max_exact < cpsi_nm < cpsi_max_exact and cpsi_nm == int(cpsi_nm)):
                cpsi_absent.append(f"column '{cpsi_name}' carries a rate but no whole-number nonmissing_n to reconcile it against")
            elif not cpsi_rc_ok:
                cpsi_absent.append("dataset.row_count is absent or not positive — rates cannot be reconciled")
            elif abs(cpsi_v - (cpsi_rc - cpsi_nm) / cpsi_rc) > 1e-6:
                cpsi_bad.append(f"column '{cpsi_name}' missing_rate disagrees with nonmissing_n beyond rounding tolerance")
            else:
                cpsi_agreed += 1
    if len(cpsi_bad) > 0:
        print(f"[FAIL] missing_rate_in_unit_interval: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    elif len(cpsi_absent) > 0:
        print(f"[NOT VERIFIED] missing_rate_in_unit_interval: {cpsi_absent[0]}" + (f" (+{len(cpsi_absent) - 1} more)" if len(cpsi_absent) > 1 else ""))
        cps_intake["not_verified"] += 1
    else:
        print(f"[PASS] missing_rate_in_unit_interval: {len(cpsi_rated)} rates in [0, 1], {cpsi_agreed} reconciled against nonmissing_n within 1e-06")
        cps_intake["passed"] += 1

# Check: released correlation matrices are square, symmetric, unit-diagonal, in [-1, 1]
if "correlation_matrix_wellformed" in not_applicable:
    print(f"[SKIPPED] correlation_matrix_wellformed: {not_applicable['correlation_matrix_wellformed']}")
    cps_intake["skipped"] += 1
elif "correlation_matrix_wellformed" in cpsi_empty_reason:
    print("[NOT VERIFIED] correlation_matrix_wellformed: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] correlation_matrix_wellformed: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif not cpsi_tier_ok:
    print("[NOT VERIFIED] correlation_matrix_wellformed: tier is not a recorded 1/2/3 — the tier decides whether matrices are expected")
    cps_intake["not_verified"] += 1
elif tier < 3:
    # The count is what the report actually declares; matrices released below tier 3 are
    # no_released_count_below_threshold's finding, not a structural fact to wave through.
    cpsi_mats = len([k for k in ("pearson", "spearman") if isinstance(cpsi_relationships, dict)
                     and isinstance(cpsi_relationships.get(k), dict) and cpsi_relationships[k].get("available") is True])
    print(f"[SKIPPED] correlation_matrix_wellformed: tier {cpsi_tier_label} releases no correlation matrices ({cpsi_mats} matrices declared)")
    cps_intake["skipped"] += 1
elif not isinstance(cpsi_relationships, dict):
    print("[NOT VERIFIED] correlation_matrix_wellformed: tier 3 but the report carries no relationships object")
    cps_intake["not_verified"] += 1
else:
    cpsi_bad = []
    cpsi_absent = []
    cpsi_checked = 0
    cpsi_max_asym = 0.0
    cpsi_dim = 0
    for cpsi_name in ("pearson", "spearman"):
        cpsi_blk = cpsi_relationships.get(cpsi_name)
        if not isinstance(cpsi_blk, dict):
            cpsi_absent.append(f"the '{cpsi_name}' block is absent at tier 3")
            continue
        if cpsi_blk.get("available") is not True:
            if not (isinstance(cpsi_blk.get("reason"), str) and cpsi_blk["reason"].strip()):
                cpsi_bad.append(f"the '{cpsi_name}' block is unavailable with no recorded reason")
            continue
        cpsi_m = cpsi_blk.get("matrix")
        if not isinstance(cpsi_m, list) or len(cpsi_m) == 0:
            cpsi_absent.append(f"the '{cpsi_name}' block is available but carries no matrix")
            continue
        cpsi_n = len(cpsi_m)
        if any(not isinstance(row, list) or len(row) != cpsi_n for row in cpsi_m):
            cpsi_bad.append(f"the '{cpsi_name}' matrix is not square")
            continue
        cpsi_flat = [v for row in cpsi_m for v in row]
        if any(not (isinstance(v, (int, float)) and not isinstance(v, bool) and -cpsi_max_exact < v < cpsi_max_exact)
               for v in cpsi_flat):
            cpsi_bad.append(f"the '{cpsi_name}' matrix carries a non-finite entry")
            continue
        cpsi_asym = max(abs(cpsi_m[i][j] - cpsi_m[j][i]) for i in range(cpsi_n) for j in range(cpsi_n))
        if cpsi_asym > 1e-09:
            cpsi_bad.append(f"the '{cpsi_name}' matrix is not symmetric within 1e-09")
        elif any(abs(cpsi_m[i][i] - 1.0) > 1e-09 for i in range(cpsi_n)):
            cpsi_bad.append(f"the '{cpsi_name}' matrix does not have a unit diagonal")
        elif any(v < -1.0 or v > 1.0 for v in cpsi_flat):
            cpsi_bad.append(f"the '{cpsi_name}' matrix carries an entry outside [-1, 1]")
        else:
            cpsi_checked += 1
            cpsi_dim = cpsi_n
            cpsi_max_asym = max(cpsi_max_asym, cpsi_asym)
    if len(cpsi_bad) > 0:
        print(f"[FAIL] correlation_matrix_wellformed: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    elif len(cpsi_absent) > 0:
        print(f"[NOT VERIFIED] correlation_matrix_wellformed: {cpsi_absent[0]}" + (f" (+{len(cpsi_absent) - 1} more)" if len(cpsi_absent) > 1 else ""))
        cps_intake["not_verified"] += 1
    elif cpsi_checked == 0:
        print("[PASS] correlation_matrix_wellformed: 0 available matrices at tier 3, every block unavailable with a recorded reason")
        cps_intake["passed"] += 1
    else:
        print(f"[PASS] correlation_matrix_wellformed: {cpsi_checked} matrices, {cpsi_dim}x{cpsi_dim}, max asymmetry {cpsi_max_asym:.2e}, unit diagonal, entries in [-1, 1]")
        cps_intake["passed"] += 1

# Check: no released count lies below the suppression threshold (NON-DECLARABLE)
# REASONING: This is the disclosure sweep. Its evidence is aggregate by design —
# the PASS line reports how many blocks and cells were examined against which
# threshold and never a count value; a FAIL names the block and the cell
# position only. Scanning is also a completeness claim: the number of blocks
# actually scanned is cross-checked against the number the report declares, so a
# missing block cannot masquerade as a clean sweep.
# The gate is never the report's word alone: a report could declare threshold 1 and
# release a count of 2. `expected_threshold` is the threshold the researcher approved
# at tier selection (recorded in STATE.md); a report declaring less is a [FAIL], and
# visible counts are gated at max(declared, approved). Thresholds are allowed facts.
cpsi_exp_ok = (isinstance(expected_threshold, (int, float)) and not isinstance(expected_threshold, bool)
               and -cpsi_max_exact < expected_threshold < cpsi_max_exact
               and expected_threshold == int(expected_threshold) and expected_threshold >= 1)
cpsi_thr_ok = (isinstance(cpsi_threshold, (int, float)) and not isinstance(cpsi_threshold, bool)
               and -cpsi_max_exact < cpsi_threshold < cpsi_max_exact
               and cpsi_threshold == int(cpsi_threshold) and cpsi_threshold >= 1)
if cpsi_report is None:
    print(f"[NOT VERIFIED] no_released_count_below_threshold: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_columns is None:
    print("[NOT VERIFIED] no_released_count_below_threshold: the report carries no columns array — the sweep has nothing to enumerate")
    cps_intake["not_verified"] += 1
elif not cpsi_exp_ok:
    print("[NOT VERIFIED] no_released_count_below_threshold: expected_threshold not configured")
    cps_intake["not_verified"] += 1
elif not cpsi_tier_ok:
    # INTENT: the approved tier is the other PSU-DS1 approval this check enforces; without
    # it the release scope cannot be checked, exactly as with an unset threshold.
    print("[NOT VERIFIED] no_released_count_below_threshold: tier not configured — the approved release scope is unknown")
    cps_intake["not_verified"] += 1
elif not cpsi_thr_ok:
    print("[NOT VERIFIED] no_released_count_below_threshold: settings.suppression_threshold is absent or not a positive integer — the sweep has no gate to test against")
    cps_intake["not_verified"] += 1
elif int(cpsi_threshold) < int(expected_threshold):
    print(f"[FAIL] no_released_count_below_threshold: report declares threshold {int(cpsi_threshold)}, below the approved threshold {int(expected_threshold)}")
    cps_intake["failed"] += 1
elif not cpsi_rep_tier_ok:
    print("[FAIL] no_released_count_below_threshold: settings.tier is absent or not a whole number 1-3 — the report's release scope is unstated")
    cps_intake["failed"] += 1
elif int(cpsi_rep_tier) > int(tier):
    # REASONING: a report profiled at a higher tier than the researcher approved has
    # already released blocks nobody approved; tiers are settings, allowed on the line.
    print(f"[FAIL] no_released_count_below_threshold: report declares tier {int(cpsi_rep_tier)}, above the approved tier {cpsi_tier_label}")
    cps_intake["failed"] += 1
elif (int(tier) < 3 or int(cpsi_rep_tier) < 3) and cpsi_rel_content:
    print(f"[FAIL] no_released_count_below_threshold: the report releases a relationships block below tier 3 (approved tier {cpsi_tier_label}, declared tier {int(cpsi_rep_tier)})")
    cps_intake["failed"] += 1
else:
    cpsi_gate = max(int(cpsi_threshold), int(expected_threshold))
    cpsi_declared_cat = len(cpsi_cat_cols)
    cpsi_declared_ct = len([x for x in cpsi_crosstabs if isinstance(x, dict) and x.get("available") is True])
    cpsi_declared = cpsi_declared_cat + cpsi_declared_ct
    cpsi_scanned = 0
    cpsi_cells = 0
    cpsi_breach = []
    for cpsi_col in cpsi_cat_cols:
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        cpsi_blk = cpsi_col.get("categorical")
        if not isinstance(cpsi_blk, dict) or not isinstance(cpsi_blk.get("levels"), list):
            continue
        cpsi_scanned += 1
        cpsi_blk_breaches = len(cpsi_breach)
        for cpsi_i, cpsi_lv in enumerate(cpsi_blk["levels"]):
            if not isinstance(cpsi_lv, dict) or "count" not in cpsi_lv:
                cpsi_breach.append(f"categorical block '{cpsi_name}' level index {cpsi_i} carries no count to gate")
                continue
            cpsi_v = cpsi_lv["count"]
            cpsi_cells += 1
            if not (isinstance(cpsi_v, (int, float)) and not isinstance(cpsi_v, bool)
                    and -cpsi_max_exact < cpsi_v < cpsi_max_exact and cpsi_v == int(cpsi_v)):
                cpsi_breach.append(f"categorical block '{cpsi_name}' level index {cpsi_i} carries a non-integer count")
            elif cpsi_v < cpsi_gate:
                # INTENT: a released level is a positive count >= the gate, so 0 and
                # negatives breach too — a level listed at 0 still names a category, and a
                # negative count is a sub-threshold count wearing a sign.
                cpsi_breach.append(f"categorical block '{cpsi_name}' level index {cpsi_i} carries a visible count below the gate")
        # INTENT: Differencing residuals, mirroring the profiler's own assertions
        # (profiling-script-spec.md § Categorical and string structure): the block's n is
        # its column's nonmissing_n; when n >= gate the released levels (`__OTHER__`
        # included) sum to n, and when n < gate no level is released at all.
        # REASONING: Otherwise n minus the visible sum (or nonmissing_n minus n) is a
        # hidden count anyone can recover by subtraction. The sum is tested only when
        # every level count in the block already passed the gate.
        cpsi_cn = cpsi_blk.get("n")
        cpsi_nm = cpsi_col.get("nonmissing_n")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and -cpsi_max_exact < x < cpsi_max_exact
                   and x == int(x) for x in (cpsi_cn, cpsi_nm)):
            cpsi_breach.append(f"categorical block '{cpsi_name}' carries no whole-number n and nonmissing_n to reconcile its levels against")
        elif cpsi_cn != cpsi_nm:
            cpsi_breach.append(f"categorical block '{cpsi_name}' n does not equal its column's nonmissing_n")
        elif cpsi_cn < cpsi_gate and len(cpsi_blk["levels"]) > 0:
            cpsi_breach.append(f"categorical block '{cpsi_name}' releases levels although its n is below the gate")
        elif (cpsi_cn >= cpsi_gate and len(cpsi_breach) == cpsi_blk_breaches
              and sum(int(lv["count"]) for lv in cpsi_blk["levels"]) != cpsi_cn):
            cpsi_breach.append(f"categorical block '{cpsi_name}' level counts do not sum to its n")
    for cpsi_idx, cpsi_ct in enumerate(cpsi_crosstabs):
        if not isinstance(cpsi_ct, dict) or cpsi_ct.get("available") is not True or not isinstance(cpsi_ct.get("cells"), list):
            continue
        cpsi_scanned += 1
        # INTENT: a pair is printed only when it names declared columns (schema facts);
        # anything else is referred to by its position, never quoted.
        cpsi_pair = cpsi_ct.get("pair")
        cpsi_pair = (" x ".join(cpsi_esc[p] for p in cpsi_pair) if isinstance(cpsi_pair, list) and len(cpsi_pair) > 0
                     and all(isinstance(p, str) and p in cpsi_col_names for p in cpsi_pair)
                     else f"index {cpsi_idx}")
        for cpsi_i, cpsi_v in enumerate(cpsi_ct["cells"]):
            if cpsi_v is None:
                continue
            cpsi_cells += 1
            if not (isinstance(cpsi_v, (int, float)) and not isinstance(cpsi_v, bool)
                    and -cpsi_max_exact < cpsi_v < cpsi_max_exact and cpsi_v == int(cpsi_v)):
                cpsi_breach.append(f"cross-tab block {cpsi_pair} cell index {cpsi_i} carries a non-integer count")
            elif cpsi_v < 0 or 0 < cpsi_v < cpsi_gate:
                # A visible 0 is a legitimate structural zero (the profiler emits them);
                # a negative cell is a sub-threshold count wearing a sign.
                cpsi_breach.append(f"cross-tab block {cpsi_pair} cell index {cpsi_i} carries a visible count below the gate")
    # INTENT: Support gate — every value summary's shape must be the one its support
    # admits (profiling-script-spec.md § Numeric shapes, § Categorical and string
    # structure, § Relationships; both profilers branch identically). With k the gate
    # and f = max(k, 10) the full-summary cutoff (the spec's derived
    # `full_summary_cutoff`, recomputed here so the report cannot lower it), a numeric
    # block of n usable values is all_missing (n = 0 and nonmissing_n = 0), withheld
    # (n < k), constant (n >= k), small_n (k <= n < f) or a full summary (n >= f), and
    # its n never exceeds the column's nonmissing_n; a string_structure's n equals its
    # column's nonmissing_n and is withheld below k, full at or above it; an available
    # named relationship needs n >= f and complement groups of 0 or >= k (below), and an
    # available Cramer's V n >= k.
    # REASONING: A summary of fewer than k values is close to the values themselves —
    # one value at n = 1. The gate is never the report's word alone: k already includes
    # the approved threshold. A FAIL names the column or entry and the shape, never n.
    # ASSUMES: a numeric shape is named by its first marker that is literally true, in
    # the spec's branch order; with none, a block carrying mean / sd / percentiles /
    # value is a full summary, and one carrying none of them releases no value (the
    # percentile check owns that finding).
    cpsi_cutoff = max(cpsi_gate, 10)
    for cpsi_col in cpsi_columns:
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        cpsi_nm = cpsi_col.get("nonmissing_n")
        cpsi_blk = cpsi_col.get("numeric")
        if isinstance(cpsi_blk, dict):
            cpsi_bn = cpsi_blk.get("n")
            cpsi_shape = next((m for m in ("all_missing", "withheld", "constant", "small_n") if cpsi_blk.get(m) is True),
                              "full" if any(k in cpsi_blk for k in ("mean", "sd", "percentiles", "value")) else None)
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < cpsi_max_exact
                       and x == int(x) for x in (cpsi_bn, cpsi_nm)):
                cpsi_breach.append(f"numeric block '{cpsi_name}' carries no non-negative whole-number n and nonmissing_n to gate its shape on")
            elif cpsi_bn > cpsi_nm:
                cpsi_breach.append(f"numeric block '{cpsi_name}' n exceeds its column's nonmissing_n")
            elif cpsi_shape is not None and not (
                    (cpsi_shape == "all_missing" and cpsi_bn == 0 and cpsi_nm == 0)
                    or (cpsi_shape == "withheld" and cpsi_bn < cpsi_gate)
                    or (cpsi_shape == "constant" and cpsi_bn >= cpsi_gate)
                    or (cpsi_shape == "small_n" and cpsi_gate <= cpsi_bn < cpsi_cutoff)
                    or (cpsi_shape == "full" and cpsi_bn >= cpsi_cutoff)):
                cpsi_breach.append(f"numeric block '{cpsi_name}' shape '{cpsi_shape}' does not match the support band of its n")
        cpsi_blk = cpsi_col.get("string_structure")
        if isinstance(cpsi_blk, dict):
            cpsi_bn = cpsi_blk.get("n")
            cpsi_shape = "withheld" if cpsi_blk.get("withheld") is True else "full"
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < cpsi_max_exact
                       and x == int(x) for x in (cpsi_bn, cpsi_nm)):
                cpsi_breach.append(f"string_structure block '{cpsi_name}' carries no non-negative whole-number n and nonmissing_n to gate its shape on")
            elif cpsi_bn != cpsi_nm:
                cpsi_breach.append(f"string_structure block '{cpsi_name}' n does not equal its column's nonmissing_n")
            elif (cpsi_shape == "withheld") != (cpsi_bn < cpsi_gate):
                cpsi_breach.append(f"string_structure block '{cpsi_name}' shape '{cpsi_shape}' does not match the support band of its n")
    for cpsi_kind, cpsi_floor in (("named", cpsi_cutoff), ("cramers_v", cpsi_gate)):
        cpsi_entries = cpsi_relationships.get(cpsi_kind) if isinstance(cpsi_relationships, dict) else None
        for cpsi_idx, cpsi_ent in enumerate(cpsi_entries if isinstance(cpsi_entries, list) else []):
            if not isinstance(cpsi_ent, dict) or cpsi_ent.get("available") is not True:
                continue
            cpsi_ends = [cpsi_ent.get("outcome"), cpsi_ent.get("predictor")] if cpsi_kind == "named" else cpsi_ent.get("pair")
            cpsi_label = ((" ~ " if cpsi_kind == "named" else " x ").join(cpsi_esc[p] for p in cpsi_ends)
                          if isinstance(cpsi_ends, list) and len(cpsi_ends) == 2
                          and all(isinstance(p, str) and p in cpsi_col_names for p in cpsi_ends)
                          else f"index {cpsi_idx}")
            cpsi_bn = cpsi_ent.get("n")
            if not (isinstance(cpsi_bn, (int, float)) and not isinstance(cpsi_bn, bool)
                    and 0 <= cpsi_bn < cpsi_max_exact and cpsi_bn == int(cpsi_bn)):
                cpsi_breach.append(f"{cpsi_kind} entry {cpsi_label} carries no non-negative whole-number n to gate its availability on")
            elif cpsi_bn < cpsi_floor:
                cpsi_breach.append(f"{cpsi_kind} entry {cpsi_label} is available although its n is below the "
                                   + ("full-summary cutoff" if cpsi_kind == "named" else "gate"))
            elif cpsi_kind == "named":
                # INTENT: Complement-group gate. For each end of an available named entry,
                # g = (the end column's numeric-block n) - (the entry's pair-complete n) is the
                # number of records with that column finite but the other end missing. It must
                # be 0 or at least k (the profilers' `small_complement_group` reason).
                # REASONING: the released mean of x describes the numeric block's n_x records
                # and the fitted line pins the mean of x over the n pair-complete ones, so
                # n_x * mean_x - n * (that mean) is the summed value of the n_x - n records
                # lacking y — one record's value when g = 1. A negative g (more pair-complete
                # records than the column holds) is a sub-threshold count wearing a sign.
                # Outcome first, then predictor; one finding per entry, naming the end only.
                # ASSUMES: the first column record carrying the name is the end column, as for
                # cross-tab pair columns; a missing or non-whole numeric n is a breach too.
                for cpsi_end_role in ("outcome", "predictor"):
                    cpsi_end = cpsi_ent.get(cpsi_end_role)
                    cpsi_end_col = next((c for c in cpsi_columns if isinstance(cpsi_end, str) and c.get("name") == cpsi_end), None)
                    cpsi_end_blk = None if cpsi_end_col is None else cpsi_end_col.get("numeric")
                    cpsi_end_n = cpsi_end_blk.get("n") if isinstance(cpsi_end_blk, dict) else None
                    if not (isinstance(cpsi_end_n, (int, float)) and not isinstance(cpsi_end_n, bool)
                            and 0 <= cpsi_end_n < cpsi_max_exact and cpsi_end_n == int(cpsi_end_n)):
                        cpsi_breach.append(f"named entry {cpsi_label} has no whole-number numeric n for its {cpsi_end_role} to gate the complement group on")
                        break
                    cpsi_g = int(cpsi_end_n) - int(cpsi_bn)
                    if cpsi_g < 0 or 0 < cpsi_g < cpsi_gate:
                        cpsi_breach.append(f"named entry {cpsi_label} is available although the complement group of its {cpsi_end_role} is below the gate")
                        break
    if len(cpsi_breach) > 0:
        print(f"[FAIL] no_released_count_below_threshold: {cpsi_breach[0]}" + (f" (+{len(cpsi_breach) - 1} more)" if len(cpsi_breach) > 1 else ""))
        cps_intake["failed"] += 1
    elif cpsi_scanned != cpsi_declared:
        print(f"[FAIL] no_released_count_below_threshold: scanned {cpsi_scanned} of {cpsi_declared} declared blocks — the sweep is incomplete")
        cps_intake["failed"] += 1
    else:
        print(f"[PASS] no_released_count_below_threshold: {cpsi_scanned} of {cpsi_declared} declared blocks scanned ({cpsi_declared_cat} categorical + {cpsi_declared_ct} cross-tab), {cpsi_cells} visible cells examined, all >= effective threshold {cpsi_gate} (declared {int(cpsi_threshold)}, approved {int(expected_threshold)})")
        cps_intake["passed"] += 1

# Check: the embedded validation record is complete and internally honest
cpsi_required_checks = {"column_shapes_and_support", "percentiles_monotone",
                        "category_counts_le_rowcount", "missing_rate_in_unit_interval",
                        "no_subthreshold_cells_emitted", "correlation_matrix_symmetric",
                        "relationship_support_and_shape"}
cpsi_legal_status = {"PASS", "FAIL", "NOT_APPLICABLE", "NOT_VERIFIED"}
if "embedded_validation_complete" in not_applicable:
    print(f"[SKIPPED] embedded_validation_complete: {not_applicable['embedded_validation_complete']}")
    cps_intake["skipped"] += 1
elif "embedded_validation_complete" in cpsi_empty_reason:
    print("[NOT VERIFIED] embedded_validation_complete: declared not_applicable with an empty reason")
    cps_intake["not_verified"] += 1
elif cpsi_report is None:
    print(f"[NOT VERIFIED] embedded_validation_complete: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif not isinstance(cpsi_report.get("validation"), dict) or not isinstance(cpsi_report["validation"].get("checks"), list):
    print("[NOT VERIFIED] embedded_validation_complete: the report carries no validation object with a checks array")
    cps_intake["not_verified"] += 1
else:
    # INTENT: every entry, name, and status is type-tested before it is hashed or
    # compared — a JSON array in `name` or `status` used to escape as a TypeError
    # with no verdict. Names outside the required set are counted, never quoted:
    # an arbitrary string here is report content, not a schema fact.
    cpsi_val = cpsi_report["validation"]
    cpsi_names = []
    cpsi_rec_bad = []
    for cpsi_i, cpsi_rec in enumerate(cpsi_val["checks"]):
        if not isinstance(cpsi_rec, dict):
            cpsi_rec_bad.append(f"checks entry {cpsi_i} is not a JSON object")
            continue
        cpsi_nm = cpsi_rec.get("name")
        if not isinstance(cpsi_nm, str):
            cpsi_rec_bad.append(f"checks entry {cpsi_i} has a name that is not a string")
            cpsi_label = f"entry {cpsi_i}"
        else:
            cpsi_names.append(cpsi_nm)
            cpsi_label = f"'{cpsi_nm}'" if cpsi_nm in cpsi_required_checks else f"entry {cpsi_i}"
        cpsi_st = cpsi_rec.get("status")
        if not isinstance(cpsi_st, str) or cpsi_st not in cpsi_legal_status:
            cpsi_rec_bad.append(f"check {cpsi_label} has a status outside the wire enum")
        elif cpsi_st in ("FAIL", "NOT_VERIFIED"):
            cpsi_rec_bad.append(f"check {cpsi_label} reports {cpsi_st}")
        if not (isinstance(cpsi_rec.get("reason"), str) and cpsi_rec["reason"].strip()):
            cpsi_rec_bad.append(f"check {cpsi_label} carries an empty reason")
    cpsi_bad = []
    cpsi_missing_checks = sorted(cpsi_required_checks - set(cpsi_names))
    cpsi_unrecognized = len([n for n in cpsi_names if n not in cpsi_required_checks])
    if len(cpsi_missing_checks) > 0 or cpsi_unrecognized > 0:
        cpsi_bad.append(f"check set is not the seven required names (missing [{', '.join(cpsi_missing_checks)}], {cpsi_unrecognized} unrecognized)")
    if len(cpsi_names) != len(set(cpsi_names)):
        cpsi_bad.append("the checks array carries duplicate names")
    cpsi_bad.extend(cpsi_rec_bad)
    if cpsi_val.get("all_passed") is not True:
        cpsi_bad.append("all_passed is not true")
    if len(cpsi_bad) > 0:
        print(f"[FAIL] embedded_validation_complete: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    else:
        print(f"[PASS] embedded_validation_complete: {len(cpsi_names)} of {len(cpsi_required_checks)} required checks present, every status in the wire enum with a non-empty reason, all_passed true")
        cps_intake["passed"] += 1

# Check: no raw-value-shaped fields anywhere in the report (NON-DECLARABLE)
# REASONING: Two heuristics, both stated in the CPS Usage Notes. (1) A list
# parked under a value-shaped key name (values / sample / rows / head /
# examples) is a raw dump regardless of its contents — note the type test, since
# a cross-tab's integer `rows` dimension is legitimate. (2) A list of scalars
# longer than the largest structure the report itself declares is carrying
# something the schema did not ask for. (3) A *string*-valued key whose name is one
# of the value-shaped names below is a single released value — the one-row version
# of the same leak, which rules (1) and (2) miss because they only inspect lists.
# (4) Every non-identifier column record is held to a per-role ALLOW-LIST of the
# schema's keys (profiling-script-spec.md § Column metadata and the numeric /
# categorical / string_structure shapes), at the record and inside its role block —
# the same pattern identifier_columns_value_free applies to identifier columns,
# which it owns. A deny-list only catches the names someone thought of (`Sample`,
# `top_values` both passed one); the schema already says which keys are legitimate.
# Name tests are case-insensitive; only key names, column names and JSON paths
# are ever printed, never a value.
cpsi_value_keys = {"values", "sample", "rows", "head", "examples"}
cpsi_scalar_value_keys = {"example", "examples", "sample", "first_value", "last_value",
                          "mode_value", "min_value", "max_value", "values", "head", "tail"}
cpsi_col_allowed = ("name", "dtype", "role", "missing_rate", "nonmissing_n",
                    "n_distinct", "uniqueness_ratio", "is_identifier")
cpsi_role_block = {"numeric": "numeric", "categorical": "categorical", "string": "string_structure"}
# ASSUMES: a numeric block's shape is named by its first present marker, in the
# spec's branch order; a marker that is not literally true is not that shape.
cpsi_num_shapes = (("all_missing", ("n", "all_missing")),
                   ("withheld", ("n", "withheld", "reason")),
                   ("constant", ("n", "constant", "value", "mean", "sd")),
                   ("small_n", ("n", "small_n", "percentiles")))
cpsi_num_full = ("n", "mean", "sd", "percentiles")
cpsi_cat_allowed = ("n", "n_levels_binned", "levels")
cpsi_level_allowed = ("value", "count")
cpsi_ss_allowed_full = ("n", "length_min", "length_mean", "length_max", "pattern_flags")
cpsi_ss_allowed_withheld = ("n", "withheld", "reason")
cpsi_flag_allowed = ("email", "phone", "date", "id", "free_text")
# INTENT: An allow-listed key the schema types as a number or boolean must hold one —
# a string (or array / object) parked under `n` or `p50` is a released value wearing
# a structural key's name, and the key-name test alone let it through. JSON null is
# accepted (the spec emits `sd: null` at n = 1). Applies at the record, inside the
# role block (except the shape markers, held to literal true above), and to every
# percentile / pattern_flags entry. Level `value` labels are strings by design and
# are not in this set; level `count` is gated by the threshold sweep.
cpsi_number_keys = ("missing_rate", "nonmissing_n", "n_distinct", "uniqueness_ratio", "is_identifier",
                    "n", "mean", "sd", "value", "n_levels_binned", "length_min", "length_mean", "length_max")
# INTENT: The column-record strings the spec fixes to a vocabulary are held to it —
# `dtype`, `role` (profiling-script-spec.md § Column metadata) and a withheld block's
# `reason` (§ Numeric shapes, § Categorical and string structure). A free string there
# is a released value wearing a structural key's name, exactly like a string under `n`.
cpsi_col_vocab = {"dtype": ("integer", "double", "string"),
                  "role": ("numeric", "categorical", "identifier", "string")}
cpsi_block_reason_vocab = {"numeric": ("no_finite_values", "insufficient_support"),
                           "string_structure": ("all_missing", "insufficient_support")}
# INTENT: Rule (5) — the report's other free-text leak paths. Every record outside
# `columns` is held to the spec's key allow-list (profiling-script-spec.md § Canonical
# JSON report schema, § Relationships, § Embedded validation checks), and each field to
# the type or closed vocabulary the spec fixes for it. Kinds: "number" (number, boolean
# or null — the cpsi_number_keys rule), "flag" (a JSON boolean), "vocab:<v>" (one string
# of cpsi_r5_vocab[v]), "name" / "names" / "pair" / "pairs" (declared column names in the
# spec's shape), "matrix" (rows of numbers), "record:<s>" / "entries:<s>" (a nested
# object / array of objects held to spec <s>), "check_reason" (below), and "owned" (a
# subtree another check owns: cross-tab entries belong to crosstab_schema_and_suppression).
cpsi_r5_specs = {
    "dataset": {"row_count": "number", "column_count": "number"},
    "settings": {"tier": "number", "suppression_threshold": "number", "max_categorical_levels": "number",
                 "relationship_spec": "pairs", "support_unit": "vocab:support_unit", "full_summary_cutoff": "number"},
    "generator": {"language": "vocab:language", "template": "vocab:template", "template_version": "vocab:template_version"},
    "relationships": {"pearson": "record:correlation", "spearman": "record:correlation", "cramers_v": "entries:cramers_v",
                      "named": "entries:named", "crosstabs": "owned"},
    "correlation": {"available": "flag", "columns": "names", "pair_n": "matrix", "matrix": "matrix",
                    "reason": "vocab:correlation_reason"},
    "cramers_v": {"pair": "pair", "n": "number", "available": "flag", "v": "number", "reason": "vocab:cramers_v_reason"},
    "named": {"outcome": "name", "predictor": "name", "n": "number", "available": "flag", "pearson": "number",
              "spearman": "number", "ols": "record:ols", "reason": "vocab:named_reason"},
    "ols": {"intercept": "number", "slope": "number", "r_squared": "number"},
    "validation": {"checks": "entries:check", "all_passed": "flag"},
    "check": {"name": "vocab:check_name", "status": "vocab:check_status", "applicable": "flag", "reason": "check_reason"},
}
# ASSUMES: `language` / `template` take the two shipped profilers' constants
# (profile_data_template.py / .R, Candidate section); the spec fixes template_version.
cpsi_r5_vocab = {
    "support_unit": ("record",),
    "language": ("Python", "R"),
    "template": ("profile_data_template.py", "profile_data_template.R"),
    "template_version": ("2.0",),
    "correlation_reason": ("fewer_than_two_eligible_columns", "insufficient_pair_support",
                           "zero_pair_variance", "nonfinite_correlation"),
    "cramers_v_reason": ("insufficient_support", "degenerate_table"),
    "named_reason": ("insufficient_support", "ineligible_marginal", "small_complement_group", "zero_pair_variance"),
    "check_name": tuple(sorted(cpsi_required_checks)),
    "check_status": tuple(sorted(cpsi_legal_status)),
}
# INTENT: `validation.checks[].reason` is held to the forms the two profilers emit.
# REASONING: A report is written only when every check is PASS or NOT_APPLICABLE, so
# those are the only statuses with a shareable reason. PASS carries the fixed token
# `candidate_fields_checked`; NOT_APPLICABLE carries the spec's no-target / tier /
# unavailable forms below (fullmatch; the numbers are counts and tiers, the
# parenthesis a spec correlation reason). The profilers take no researcher
# declarations and write only these forms, so any other reason means a modified
# template or a hand-edited report. A FAIL /
# NOT_VERIFIED entry has no shareable reason at all; an entry whose status is outside
# the wire enum is named by its `status` finding instead.
cpsi_na_reason_forms = {
    "percentiles_monotone": (r"report declares 0 numeric columns at tier [123]",
                             r"0 of [1-9][0-9]* numeric columns release a percentile grid"),
    "category_counts_le_rowcount": (r"report declares 0 categorical columns at tier [123]",),
    "missing_rate_in_unit_interval": (r"tier 1 releases name and dtype only",),
    "correlation_matrix_symmetric": (r"tier [12] releases no correlations",
                                     r"0 of 2 correlation blocks released \((fewer_than_two_eligible_columns|insufficient_pair_support|zero_pair_variance|nonfinite_correlation|no reason stated)\)"),
    "relationship_support_and_shape": (r"tier [12] releases no relationships",),
}
if cpsi_report is None:
    print(f"[NOT VERIFIED] no_raw_value_shaped_fields: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
else:
    cpsi_cap = max(len(cpsi_pctl_order), 0 if cpsi_columns is None else len(cpsi_columns))
    for cpsi_col in cpsi_cat_cols:
        cpsi_blk = cpsi_col.get("categorical")
        if isinstance(cpsi_blk, dict) and isinstance(cpsi_blk.get("levels"), list):
            cpsi_cap = max(cpsi_cap, len(cpsi_blk["levels"]))
    for cpsi_ct in cpsi_crosstabs:
        if isinstance(cpsi_ct, dict) and isinstance(cpsi_ct.get("cells"), list):
            cpsi_cap = max(cpsi_cap, len(cpsi_ct["cells"]))
    cpsi_stack = [("report", cpsi_report)]
    cpsi_nodes = 0
    cpsi_longest = 0
    cpsi_hits = []
    while len(cpsi_stack) > 0:
        cpsi_path, cpsi_node = cpsi_stack.pop()
        cpsi_nodes += 1
        if isinstance(cpsi_node, dict):
            for cpsi_k, cpsi_v in cpsi_node.items():
                if cpsi_k.translate(cpsi_ascii_lower) in cpsi_value_keys and isinstance(cpsi_v, list):
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_esc[cpsi_k]} is a list under a value-shaped key name")
                if isinstance(cpsi_v, str) and cpsi_k.translate(cpsi_ascii_lower) in cpsi_scalar_value_keys:
                    cpsi_hits.append(f"value-shaped key '{cpsi_esc[cpsi_k]}' at {cpsi_path}.{cpsi_esc[cpsi_k]}")
                cpsi_stack.append((f"{cpsi_path}.{cpsi_esc[cpsi_k]}", cpsi_v))
        elif isinstance(cpsi_node, list):
            if len(cpsi_node) > 0 and all(not isinstance(x, (dict, list)) for x in cpsi_node):
                cpsi_longest = max(cpsi_longest, len(cpsi_node))
                if len(cpsi_node) > cpsi_cap:
                    cpsi_hits.append(f"{cpsi_path} is a {len(cpsi_node)}-element scalar list, longer than the declared cap {cpsi_cap}")
            for cpsi_i, cpsi_v in enumerate(cpsi_node):
                cpsi_stack.append((f"{cpsi_path}[{cpsi_i}]", cpsi_v))
    # Rule (4): the per-role column-record allow-list. Hits follow the walker's.
    cpsi_records = 0
    for cpsi_i, cpsi_col in enumerate([] if cpsi_columns_raw is None else cpsi_columns_raw):
        if not isinstance(cpsi_col, dict):
            cpsi_hits.append(f"column index {cpsi_i} is not a JSON object")
            continue
        if not isinstance(cpsi_col.get("name"), str):
            cpsi_hits.append(f"column index {cpsi_i} has a name that is not a string")
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        if cpsi_col.get("role") == "identifier" or cpsi_col.get("is_identifier") is True:
            continue
        cpsi_records += 1
        cpsi_role = cpsi_col.get("role")
        cpsi_bkey = cpsi_role_block.get(cpsi_role) if isinstance(cpsi_role, str) and not (cpsi_tier_ok and tier == 1) else None
        cpsi_allowed = ("name", "dtype") if cpsi_tier_ok and tier == 1 else cpsi_col_allowed + (() if cpsi_bkey is None else (cpsi_bkey,))
        for cpsi_f in sorted(cpsi_col):
            if cpsi_f not in cpsi_allowed:
                cpsi_hits.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
            elif cpsi_f in cpsi_number_keys and not (cpsi_col[cpsi_f] is None or isinstance(cpsi_col[cpsi_f], (int, float))):
                cpsi_hits.append(f"column '{cpsi_name}' carries a non-numeric '{cpsi_f}'")
            elif cpsi_f in cpsi_col_vocab and not (isinstance(cpsi_col[cpsi_f], str) and cpsi_col[cpsi_f] in cpsi_col_vocab[cpsi_f]):
                cpsi_hits.append(f"column '{cpsi_name}' carries a '{cpsi_f}' outside the spec vocabulary")
        # INTENT: A categorical column is a string column: both profilers assign the
        # categorical role only to dtype "string" (a numeric dtype is profiled as
        # numeric), so a categorical record declaring "integer" or "double" is not
        # something either profiler writes. The dtype is a vocabulary word but is not
        # echoed; a dtype outside the vocabulary is the line above's finding.
        if (cpsi_bkey == "categorical" and cpsi_col.get("dtype") in cpsi_col_vocab["dtype"]
                and cpsi_col.get("dtype") != "string"):
            cpsi_hits.append(f"column '{cpsi_name}' declares role 'categorical' with a dtype other than 'string'")
        cpsi_blk = None if cpsi_bkey is None else cpsi_col.get(cpsi_bkey)
        if cpsi_blk is None:
            continue
        if not isinstance(cpsi_blk, dict):
            cpsi_hits.append(f"column '{cpsi_name}' carries a non-object '{cpsi_bkey}'")
            continue
        cpsi_sub = None
        cpsi_sub_allowed = ()
        if cpsi_bkey == "numeric":
            cpsi_blk_allowed = cpsi_num_full
            for cpsi_marker, cpsi_keys in cpsi_num_shapes:
                if cpsi_marker in cpsi_blk:
                    cpsi_blk_allowed = cpsi_keys
                    if cpsi_blk.get(cpsi_marker) is not True:
                        cpsi_hits.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_marker}'")
                    break
            cpsi_sub = "percentiles"
            cpsi_sub_allowed = ("p25", "p50", "p75") if "small_n" in cpsi_blk_allowed else tuple(cpsi_pctl_order)
        elif cpsi_bkey == "categorical":
            cpsi_blk_allowed = cpsi_cat_allowed
        else:
            cpsi_blk_allowed = cpsi_ss_allowed_withheld if "withheld" in cpsi_blk else cpsi_ss_allowed_full
            if "withheld" in cpsi_blk and cpsi_blk.get("withheld") is not True:
                cpsi_hits.append(f"column '{cpsi_name}' carries non-structural key 'withheld'")
            cpsi_sub = "pattern_flags"
            cpsi_sub_allowed = cpsi_flag_allowed
        for cpsi_f in sorted(cpsi_blk):
            if cpsi_f not in cpsi_blk_allowed:
                cpsi_hits.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
            elif cpsi_f in cpsi_number_keys and not (cpsi_blk[cpsi_f] is None or isinstance(cpsi_blk[cpsi_f], (int, float))):
                cpsi_hits.append(f"column '{cpsi_name}' carries a non-numeric '{cpsi_f}'")
            elif cpsi_f == "reason" and not (isinstance(cpsi_blk[cpsi_f], str) and cpsi_blk[cpsi_f] in cpsi_block_reason_vocab.get(cpsi_bkey, ())):
                cpsi_hits.append(f"column '{cpsi_name}' carries a 'reason' outside the spec vocabulary")
        if cpsi_sub is not None and cpsi_sub in cpsi_blk_allowed and cpsi_blk.get(cpsi_sub) is not None:
            if not isinstance(cpsi_blk[cpsi_sub], dict):
                cpsi_hits.append(f"column '{cpsi_name}' carries a non-object '{cpsi_sub}'")
            else:
                for cpsi_f in sorted(cpsi_blk[cpsi_sub]):
                    if cpsi_f not in cpsi_sub_allowed:
                        cpsi_hits.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
                    elif not (cpsi_blk[cpsi_sub][cpsi_f] is None or isinstance(cpsi_blk[cpsi_sub][cpsi_f], (int, float))):
                        cpsi_hits.append(f"column '{cpsi_name}' carries a non-numeric '{cpsi_f}'")
        if cpsi_bkey == "categorical" and cpsi_blk.get("levels") is not None:
            if not isinstance(cpsi_blk["levels"], list):
                cpsi_hits.append(f"column '{cpsi_name}' carries a non-array 'levels'")
            else:
                # INTENT: one released level per label. A string label repeated within a
                # block is named by the later level's index and the first one's, never by
                # the label itself.
                # REASONING: no profiler writes a label twice (each released level is one
                # category), and two entries under one label would split a category's count
                # in a way no check reconciles, make the cross-tab's category mapping
                # ambiguous, and leave generation two counts for one level.
                cpsi_lv_first = {}
                for cpsi_j, cpsi_lv in enumerate(cpsi_blk["levels"]):
                    if not isinstance(cpsi_lv, dict):
                        cpsi_hits.append(f"column '{cpsi_name}' level index {cpsi_j} is not a JSON object")
                        continue
                    for cpsi_f in sorted(cpsi_lv):
                        if cpsi_f not in cpsi_level_allowed:
                            cpsi_hits.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
                        elif cpsi_f == "value" and not isinstance(cpsi_lv[cpsi_f], str):
                            # A level label is a string by schema; an array or object
                            # there is a value dump wearing the label's name.
                            cpsi_hits.append(f"column '{cpsi_name}' level index {cpsi_j} carries a non-string 'value'")
                    if isinstance(cpsi_lv.get("value"), str):
                        if cpsi_lv["value"] in cpsi_lv_first:
                            cpsi_hits.append(f"column '{cpsi_name}' level index {cpsi_j} repeats the 'value' of level index {cpsi_lv_first[cpsi_lv['value']]}")
                        else:
                            cpsi_lv_first[cpsi_lv["value"]] = cpsi_j
    # Rule (5): the subtree records, breadth-first in a fixed order (both languages).
    # A top-level subtree of the wrong JSON type is required_top_level_keys' finding.
    cpsi_queue = [(k, cpsi_report[k], k) for k in ("dataset", "settings", "generator", "relationships", "validation")
                  if isinstance(cpsi_report.get(k), dict)]
    cpsi_qi = 0
    while cpsi_qi < len(cpsi_queue):
        cpsi_path, cpsi_rec, cpsi_spec_name = cpsi_queue[cpsi_qi]
        cpsi_qi += 1
        cpsi_spec = cpsi_r5_specs[cpsi_spec_name]
        for cpsi_f in sorted(cpsi_rec):
            cpsi_v = cpsi_rec[cpsi_f]
            cpsi_kind = cpsi_spec.get(cpsi_f)
            if cpsi_kind is None:
                cpsi_hits.append(f"{cpsi_path} carries non-structural key '{cpsi_esc[cpsi_f]}'")
            elif cpsi_kind == "number":
                if not (cpsi_v is None or isinstance(cpsi_v, (int, float))):
                    cpsi_hits.append(f"{cpsi_path} carries a non-numeric '{cpsi_f}'")
            elif cpsi_kind == "flag":
                if not isinstance(cpsi_v, bool):
                    cpsi_hits.append(f"{cpsi_path} carries a non-boolean '{cpsi_f}'")
            elif cpsi_kind.startswith("vocab:"):
                if not (isinstance(cpsi_v, str) and cpsi_v in cpsi_r5_vocab[cpsi_kind[6:]]):
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_f} is outside the spec vocabulary")
            elif cpsi_kind == "check_reason":
                cpsi_st = cpsi_rec.get("status")
                cpsi_nm = cpsi_rec.get("name")
                if cpsi_st == "PASS":
                    cpsi_ok = cpsi_v == "candidate_fields_checked"
                elif cpsi_st == "NOT_APPLICABLE":
                    cpsi_ok = (isinstance(cpsi_v, str) and isinstance(cpsi_nm, str)
                               and any(re.fullmatch(p, cpsi_v) is not None for p in cpsi_na_reason_forms.get(cpsi_nm, ())))
                else:
                    cpsi_ok = cpsi_st not in ("FAIL", "NOT_VERIFIED")
                if not cpsi_ok:
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_f} is outside the spec vocabulary")
            elif cpsi_kind in ("name", "names", "pair", "pairs"):
                if cpsi_kind == "pairs":
                    cpsi_ok = cpsi_v is None or (isinstance(cpsi_v, list) and all(
                        isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and x in cpsi_col_names for x in p)
                        for p in cpsi_v))
                else:
                    cpsi_items = [cpsi_v] if cpsi_kind == "name" else (cpsi_v if isinstance(cpsi_v, list) else None)
                    cpsi_ok = (cpsi_items is not None and (cpsi_kind != "pair" or len(cpsi_items) == 2)
                               and all(isinstance(x, str) and x in cpsi_col_names for x in cpsi_items))
                if not cpsi_ok:
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_f} is not built from declared column names")
            elif cpsi_kind == "matrix":
                if not (isinstance(cpsi_v, list) and all(
                        isinstance(r, list) and all(x is None or isinstance(x, (int, float)) for x in r) for r in cpsi_v)):
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_f} is not an array of numeric rows")
            elif cpsi_kind.startswith("record:"):
                if isinstance(cpsi_v, dict):
                    cpsi_queue.append((f"{cpsi_path}.{cpsi_f}", cpsi_v, cpsi_kind[7:]))
                else:
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_f} is not a JSON object")
            elif cpsi_kind.startswith("entries:"):
                if isinstance(cpsi_v, list):
                    for cpsi_e, cpsi_ent in enumerate(cpsi_v):
                        if isinstance(cpsi_ent, dict):
                            cpsi_queue.append((f"{cpsi_path}.{cpsi_f}[{cpsi_e}]", cpsi_ent, cpsi_kind[8:]))
                        else:
                            cpsi_hits.append(f"{cpsi_path}.{cpsi_f}[{cpsi_e}] is not a JSON object")
                else:
                    cpsi_hits.append(f"{cpsi_path}.{cpsi_f} is not a JSON array")
    # Rule (6): the top level itself — key set, value types, and the formats both shipped
    # profilers write (report_version a dotted version, dataset_name the Config slug
    # `[A-Za-z0-9_-]+`, generated_utc `YYYY-MM-DDTHH:MM:SSZ`). Held here as well as in
    # required_top_level_keys because that check is declarable: declaring it away must
    # not open a free-text channel at the top of the report. Missing keys are not a
    # channel and stay required_top_level_keys' finding. ASCII classes only ([0-9],
    # never \d, which is Unicode-aware in Python).
    cpsi_top_kind = {"report_version": "fmt", "dataset_name": "fmt", "generated_utc": "fmt", "generator": "object",
                     "settings": "object", "dataset": "object", "validation": "object", "relationships": "object",
                     "columns": "array"}
    cpsi_top_fmt = {"report_version": r"[0-9.]{1,16}", "dataset_name": r"[A-Za-z0-9_-]+",
                    "generated_utc": r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"}
    for cpsi_k in sorted(cpsi_report):
        cpsi_v = cpsi_report[cpsi_k]
        cpsi_kind = cpsi_top_kind.get(cpsi_k)
        if cpsi_kind is None:
            cpsi_hits.append(f"report carries non-structural key '{cpsi_esc[cpsi_k]}'")
        elif cpsi_kind == "object" and not isinstance(cpsi_v, dict):
            cpsi_hits.append(f"report.{cpsi_k} is not a JSON object")
        elif cpsi_kind == "array" and not isinstance(cpsi_v, list):
            cpsi_hits.append(f"report.{cpsi_k} is not a JSON array")
        elif cpsi_kind == "fmt" and not (isinstance(cpsi_v, str) and re.fullmatch(cpsi_top_fmt[cpsi_k], cpsi_v) is not None):
            cpsi_hits.append(f"report.{cpsi_k} is outside the spec format")
    if len(cpsi_hits) > 0:
        print(f"[FAIL] no_raw_value_shaped_fields: {cpsi_hits[0]}" + (f" (+{len(cpsi_hits) - 1} more)" if len(cpsi_hits) > 1 else ""))
        cps_intake["failed"] += 1
    else:
        print(f"[PASS] no_raw_value_shaped_fields: {cpsi_nodes} JSON nodes walked, 0 value-shaped keys, longest scalar list {cpsi_longest} <= declared cap {cpsi_cap}, {cpsi_records} column records within the per-role key allow-list, {cpsi_qi} subtree records within the spec key allow-lists and vocabularies")
        cps_intake["passed"] += 1

# Check: identifier columns carry structure only, never values (NON-DECLARABLE)
# REASONING: An allow-list, not a deny-list. A deny-list only catches the leak
# shapes someone thought of — `string_structure.example` sailed past one. The
# schema fixes exactly which keys an identifier record may carry
# (profiling-script-spec.md: name, dtype, role, missing_rate, nonmissing_n,
# n_distinct, uniqueness_ratio, is_identifier, and the one role block), so any
# other key is by construction something the schema did not sanction. Only the
# key NAME is printed — naming its value would be the leak itself.
cpsi_id_allowed_col = ("name", "dtype", "role", "missing_rate", "nonmissing_n",
                       "n_distinct", "uniqueness_ratio", "is_identifier", "string_structure")
cpsi_id_allowed_ss = cpsi_ss_allowed_full
cpsi_id_allowed_ss_withheld = cpsi_ss_allowed_withheld
# INTENT: At tier 1 — the approved tier or the report's own settings.tier — an
# identifier record is held to {name, dtype}, like every other tier-1 record.
# REASONING: Tier 1 releases the schema only (profiling-script-spec.md: T1 columns are
# exactly {name,dtype}). Rule (4) of no_raw_value_shaped_fields skips identifier
# records because this check owns them, so a tier-1 identifier carrying tier-2
# metadata and a string_structure would otherwise pass both checks.
cpsi_id_t1 = (cpsi_tier_ok and tier == 1) or (cpsi_rep_tier_ok and cpsi_rep_tier == 1)
if cpsi_report is None:
    print(f"[NOT VERIFIED] identifier_columns_value_free: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_columns is None:
    print("[NOT VERIFIED] identifier_columns_value_free: the report carries no columns array")
    cps_intake["not_verified"] += 1
else:
    cpsi_id_cols = [c for c in cpsi_columns if c.get("role") == "identifier" or c.get("is_identifier") is True]
    cpsi_bad = []
    cpsi_withheld = 0
    for cpsi_col in cpsi_id_cols:
        cpsi_name = cpsi_esc[cpsi_col["name"]] if isinstance(cpsi_col.get("name"), str) else "<unnamed>"
        # INTENT: the same number-or-boolean typing rule as no_raw_value_shaped_fields
        # (cpsi_number_keys): a string under `n_distinct` is a value, not structure.
        for cpsi_f in sorted(cpsi_col):
            if cpsi_f not in (("name", "dtype") if cpsi_id_t1 else cpsi_id_allowed_col):
                cpsi_bad.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
            elif cpsi_f in cpsi_number_keys and not (cpsi_col[cpsi_f] is None or isinstance(cpsi_col[cpsi_f], (int, float))):
                cpsi_bad.append(f"column '{cpsi_name}' carries a non-numeric '{cpsi_f}'")
            elif cpsi_f in cpsi_col_vocab and not (isinstance(cpsi_col[cpsi_f], str) and cpsi_col[cpsi_f] in cpsi_col_vocab[cpsi_f]):
                cpsi_bad.append(f"column '{cpsi_name}' carries a '{cpsi_f}' outside the spec vocabulary")
        # At tier 1 the string_structure key itself is the finding (named above).
        cpsi_ss = None if cpsi_id_t1 else cpsi_col.get("string_structure")
        # INTENT: a non-object string_structure (e.g. a bare string) is the value
        # itself standing where structure belongs — it used to pass unexamined.
        if cpsi_ss is not None and not isinstance(cpsi_ss, dict):
            cpsi_bad.append(f"column '{cpsi_name}' carries a non-object 'string_structure'")
        if isinstance(cpsi_ss, dict):
            # ASSUMES: the withheld shape is identified by the presence of the
            # `withheld` key (n < k, profiling-script-spec.md); a `withheld` that
            # is not literally true is not that shape, so the key is unsanctioned.
            if "withheld" in cpsi_ss:
                cpsi_ss_allowed = cpsi_id_allowed_ss_withheld
                if cpsi_ss.get("withheld") is True:
                    cpsi_withheld += 1
                else:
                    cpsi_bad.append(f"column '{cpsi_name}' carries non-structural key 'withheld'")
            else:
                cpsi_ss_allowed = cpsi_id_allowed_ss
            for cpsi_f in sorted(cpsi_ss):
                if cpsi_f not in cpsi_ss_allowed:
                    cpsi_bad.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
                elif cpsi_f in cpsi_number_keys and not (cpsi_ss[cpsi_f] is None or isinstance(cpsi_ss[cpsi_f], (int, float))):
                    cpsi_bad.append(f"column '{cpsi_name}' carries a non-numeric '{cpsi_f}'")
                elif cpsi_f == "reason" and not (isinstance(cpsi_ss[cpsi_f], str) and cpsi_ss[cpsi_f] in cpsi_block_reason_vocab["string_structure"]):
                    cpsi_bad.append(f"column '{cpsi_name}' carries a 'reason' outside the spec vocabulary")
            # The pattern_flags object is held to its five schema flags too.
            if "pattern_flags" in cpsi_ss_allowed and cpsi_ss.get("pattern_flags") is not None:
                if not isinstance(cpsi_ss["pattern_flags"], dict):
                    cpsi_bad.append(f"column '{cpsi_name}' carries a non-object 'pattern_flags'")
                else:
                    for cpsi_f in sorted(cpsi_ss["pattern_flags"]):
                        if cpsi_f not in cpsi_flag_allowed:
                            cpsi_bad.append(f"column '{cpsi_name}' carries non-structural key '{cpsi_esc[cpsi_f]}'")
                        elif not (cpsi_ss["pattern_flags"][cpsi_f] is None or isinstance(cpsi_ss["pattern_flags"][cpsi_f], (int, float))):
                            cpsi_bad.append(f"column '{cpsi_name}' carries a non-numeric '{cpsi_f}'")
    if len(cpsi_bad) > 0:
        print(f"[FAIL] identifier_columns_value_free: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    else:
        print(f"[PASS] identifier_columns_value_free: {len(cpsi_id_cols)} identifier columns examined, structure keys only (allow-list), {cpsi_withheld} withheld")
        cps_intake["passed"] += 1

# Check: cross-tab schema and suppression are well formed (NON-DECLARABLE)
if cpsi_report is None:
    print(f"[NOT VERIFIED] crosstab_schema_and_suppression: {cpsi_load_error}")
    cps_intake["not_verified"] += 1
elif cpsi_crosstabs_not_array:
    print("[FAIL] crosstab_schema_and_suppression: relationships.crosstabs is not a JSON array")
    cps_intake["failed"] += 1
elif len(cpsi_crosstabs) == 0:
    print(f"[PASS] crosstab_schema_and_suppression: 0 cross-tab entries declared at tier {cpsi_tier_label}")
    cps_intake["passed"] += 1
else:
    cpsi_bad = []
    cpsi_absent = []
    cpsi_cells = 0
    cpsi_hidden = 0
    cpsi_collapsed = 0
    # Unordered pair (sorted column names) -> index of the first entry on it.
    cpsi_pair_seen = {}
    # INTENT: the missing-partner scan below gates a recovered count on the same effective
    # threshold the sweep uses, max(declared, approved); None when either is unusable.
    cpsi_xgate = max(int(cpsi_threshold), int(expected_threshold)) if cpsi_thr_ok and cpsi_exp_ok else None
    for cpsi_idx, cpsi_ct in enumerate(cpsi_crosstabs):
        if not isinstance(cpsi_ct, dict):
            cpsi_bad.append(f"entry index {cpsi_idx} is not a JSON object")
            continue
        # Same pair-label rule as the sweep: declared column names, else the position.
        cpsi_pair = cpsi_ct.get("pair")
        cpsi_pair = (" x ".join(cpsi_esc[p] for p in cpsi_pair) if isinstance(cpsi_pair, list) and len(cpsi_pair) > 0
                     and all(isinstance(p, str) and p in cpsi_col_names for p in cpsi_pair)
                     else f"index {cpsi_idx}")
        # INTENT: The entry is held to the spec's key allow-list (profiling-script-
        # spec.md § Relationships, cross-tab), `pair` to two declared column names,
        # `available` to a boolean, `n` to a number, `collapsed` to literal true, and an
        # unavailable entry's reason to the spec's two reasons. Only the key, the pair
        # label (declared names) or the index is printed, never a value. rows / cols /
        # cells on an unavailable entry keep their own `still carries` finding below.
        cpsi_raw_pair = cpsi_ct.get("pair")
        cpsi_pair_ok = (isinstance(cpsi_raw_pair, list) and len(cpsi_raw_pair) == 2
                        and all(isinstance(p, str) and p in cpsi_col_names for p in cpsi_raw_pair))
        if not cpsi_pair_ok:
            cpsi_bad.append(f"entry index {cpsi_idx} carries a 'pair' that is not two declared column names")
        else:
            # INTENT: one cross-tab per unordered pair of two distinct columns, whatever
            # each entry's `available` says (the profiler refuses both shapes).
            # REASONING: two tables of one pair can hide different cells, and the union
            # of what they release recovers cells that neither hides alone; a pair that
            # names one column twice is no cross-tab at all. Only entry indices print.
            if cpsi_raw_pair[0] == cpsi_raw_pair[1]:
                cpsi_bad.append(f"entry index {cpsi_idx} names one column twice in its 'pair'")
            cpsi_key = tuple(sorted(cpsi_raw_pair))
            if cpsi_key in cpsi_pair_seen:
                cpsi_bad.append(f"entry index {cpsi_idx} repeats the pair of entry index {cpsi_pair_seen[cpsi_key]}")
            else:
                cpsi_pair_seen[cpsi_key] = cpsi_idx
        if not isinstance(cpsi_ct.get("available"), bool):
            cpsi_bad.append(f"entry {cpsi_pair} carries a non-boolean 'available'")
        cpsi_ct_allowed = (("pair", "n", "available", "rows", "cols", "cells", "cells_suppressed", "collapsed")
                           if cpsi_ct.get("available") is True
                           else ("pair", "n", "available", "reason", "rows", "cols", "cells"))
        for cpsi_f in sorted(cpsi_ct):
            if cpsi_f not in cpsi_ct_allowed:
                cpsi_bad.append(f"entry {cpsi_pair} carries non-structural key '{cpsi_esc[cpsi_f]}'")
            elif cpsi_f == "n" and not (cpsi_ct[cpsi_f] is None or isinstance(cpsi_ct[cpsi_f], (int, float))):
                cpsi_bad.append(f"entry {cpsi_pair} carries a non-numeric 'n'")
            elif cpsi_f == "collapsed" and cpsi_ct[cpsi_f] is not True:
                cpsi_bad.append(f"entry {cpsi_pair} carries non-structural key 'collapsed'")
        if cpsi_ct.get("available") is not True:
            if not (isinstance(cpsi_ct.get("reason"), str) and cpsi_ct["reason"].strip()):
                cpsi_bad.append(f"unavailable entry {cpsi_pair} carries no reason")
            elif cpsi_ct["reason"] not in ("ineligible_roles", "insufficient_support"):
                cpsi_bad.append(f"unavailable entry {cpsi_pair} carries a reason outside the spec vocabulary")
            for cpsi_f in ("rows", "cols", "cells"):
                if cpsi_f in cpsi_ct:
                    cpsi_bad.append(f"unavailable entry {cpsi_pair} still carries '{cpsi_f}'")
            continue
        cpsi_r = cpsi_ct.get("rows")
        cpsi_c = cpsi_ct.get("cols")
        cpsi_grid = cpsi_ct.get("cells")
        if not (isinstance(cpsi_r, (int, float)) and not isinstance(cpsi_r, bool)
                and 0 < cpsi_r < cpsi_max_exact and cpsi_r == int(cpsi_r)
                and isinstance(cpsi_c, (int, float)) and not isinstance(cpsi_c, bool)
                and 0 < cpsi_c < cpsi_max_exact and cpsi_c == int(cpsi_c)
                and isinstance(cpsi_grid, list)):
            # REASONING: rows / cols / cells are fields this check validates, so a wrong type
            # or a non-positive / non-whole dimension is a [FAIL], not missing evidence.
            cpsi_bad.append(f"entry {cpsi_pair} has no positive integer rows/cols with a cells array — the grid cannot be reshaped")
            continue
        cpsi_r = int(cpsi_r)
        cpsi_c = int(cpsi_c)
        # INTENT: an available grid sits on the released categories: its rows are the
        # first pair column's released levels and its cols the second's, so rows / cols
        # must equal those level counts (the profiler asserts the same).
        # REASONING: a row or column for a source level the categorical block pooled into
        # __OTHER__ could be subtracted from the released __OTHER__ count to isolate a
        # rare level; a grid on the released categories has no such row. The level cap
        # bounds the grid's size for the same reason. Only the position prints.
        # ASSUMES: the first column record carrying the name is the pair column.
        # The two pair column records are kept for the missing-partner scan below, which
        # runs only on an entry of two distinct columns whose grid passed this rule.
        cpsi_x_cols = []
        if cpsi_pair_ok:
            for cpsi_p, cpsi_dim, cpsi_side in ((0, cpsi_r, "rows"), (1, cpsi_c, "cols")):
                cpsi_pc = next(c for c in cpsi_columns if c.get("name") == cpsi_raw_pair[cpsi_p])
                cpsi_pblk = cpsi_pc.get("categorical")
                if not (cpsi_pc.get("role") == "categorical" and isinstance(cpsi_pblk, dict)
                        and isinstance(cpsi_pblk.get("levels"), list)):
                    cpsi_bad.append(f"entry {cpsi_pair} pair position {cpsi_p} is not a categorical column with a released levels array")
                elif len(cpsi_pblk["levels"]) != cpsi_dim:
                    cpsi_bad.append(f"entry {cpsi_pair} has {cpsi_side} unequal to the released level count of pair position {cpsi_p}")
                else:
                    cpsi_x_cols.append(cpsi_pc)
        cpsi_x_run = len(cpsi_x_cols) == 2 and cpsi_raw_pair[0] != cpsi_raw_pair[1]
        if len(cpsi_grid) != cpsi_r * cpsi_c:
            cpsi_bad.append(f"entry {cpsi_pair} has {len(cpsi_grid)} cells, not rows x cols = {cpsi_r * cpsi_c}")
            continue
        cpsi_nulls = [i for i, v in enumerate(cpsi_grid) if v is None]
        cpsi_cells += len(cpsi_grid)
        cpsi_hidden += len(cpsi_nulls)
        # A visible 0 is a structural zero and legitimate; a hidden cell mis-coded as 0
        # still shows up here, because cells_suppressed then disagrees with the nulls.
        cpsi_cs = cpsi_ct.get("cells_suppressed")
        if not (isinstance(cpsi_cs, (int, float)) and not isinstance(cpsi_cs, bool) and cpsi_cs == len(cpsi_nulls)):
            cpsi_bad.append(f"entry {cpsi_pair} reports a cells_suppressed that disagrees with the {len(cpsi_nulls)} nulls in the grid")
        # INTENT: Differencing residual, mirroring the profiler (profiling-script-spec.md
        # § Relationships, cross-tab): visible cells never sum past the entry's n, and with
        # no hidden cell they sum to it exactly — else n minus the visible sum is a
        # released count. Tested only when every visible cell is a whole number >= 0
        # (a malformed cell is the threshold sweep's finding).
        cpsi_vis = [v for v in cpsi_grid if v is not None]
        cpsi_ctn = cpsi_ct.get("n")
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < cpsi_max_exact and v == int(v) for v in cpsi_vis):
            cpsi_tot = sum(int(v) for v in cpsi_vis)
            if not (isinstance(cpsi_ctn, (int, float)) and not isinstance(cpsi_ctn, bool)
                    and 0 <= cpsi_ctn < cpsi_max_exact and cpsi_ctn == int(cpsi_ctn)):
                cpsi_bad.append(f"entry {cpsi_pair} carries no whole-number 'n' to reconcile its cells against")
            elif cpsi_tot > cpsi_ctn:
                cpsi_bad.append(f"entry {cpsi_pair} releases visible cells that sum past its n")
            elif len(cpsi_nulls) == 0 and cpsi_tot != cpsi_ctn:
                cpsi_bad.append(f"entry {cpsi_pair} hides no cell but its visible cells do not sum to its n")
        # INTENT: `collapsed: true` is the whole-table hide of last resort, so it
        # earns the bypass only when the table really is hidden whole.
        # REASONING: A collapsed flag over a grid that still shows cells would
        # otherwise switch off the complementary-suppression scan while the
        # recoverable cells stay on the wire — the flag would be a bypass, not a
        # suppression. The index, not the pair, is what a FAIL needs to point at.
        if cpsi_ct.get("collapsed") is True:
            if len(cpsi_nulls) == len(cpsi_grid):
                cpsi_collapsed += 1
            else:
                cpsi_bad.append(f"entry {cpsi_idx} is marked collapsed but still releases visible cells")
        else:
            for cpsi_i in range(cpsi_r):
                if len([j for j in range(cpsi_c) if cpsi_grid[cpsi_i * cpsi_c + j] is None]) == 1:
                    cpsi_bad.append(f"entry {cpsi_pair} leaves a lone hidden cell in row index {cpsi_i} — recoverable by differencing")
                    break
            for cpsi_j in range(cpsi_c):
                if len([i for i in range(cpsi_r) if cpsi_grid[i * cpsi_c + cpsi_j] is None]) == 1:
                    cpsi_bad.append(f"entry {cpsi_pair} leaves a lone hidden cell in column index {cpsi_j} — recoverable by differencing")
                    break
            # INTENT: Bridge scan. Read the hidden cells as the edges of a bipartite graph
            # whose vertices are the entry's rows and columns, and treat every row and
            # column total as released (the categorical blocks release the margins). A
            # hidden cell is then pinned exactly by the totals iff its edge lies on no
            # cycle, i.e. it is a bridge. The lone hidden cell is the degree-1 case and
            # keeps its own finding above; every other bridge is named here by row and
            # column index, in row-major order.
            # REASONING: One iterative depth-first walk per component (low-link bridge
            # test) visits each hidden cell a bounded number of times, so a large grid
            # cannot stall the block. Vertices: row i is i, column j is rows + j.
            # ASSUMES: Interval (non-exact) inference from non-negativity is out of
            # scope; a fully collapsed entry is exempt (it releases no visible cell).
            cpsi_br_adj = {}
            for cpsi_br_k in cpsi_nulls:
                cpsi_br_adj.setdefault(cpsi_br_k // cpsi_c, []).append(cpsi_br_k)
                cpsi_br_adj.setdefault(cpsi_r + cpsi_br_k % cpsi_c, []).append(cpsi_br_k)
            cpsi_br_disc = {}
            cpsi_br_low = {}
            cpsi_br_found = []
            for cpsi_br_root in sorted(cpsi_br_adj):
                if cpsi_br_root in cpsi_br_disc:
                    continue
                cpsi_br_disc[cpsi_br_root] = len(cpsi_br_disc) + 1
                cpsi_br_low[cpsi_br_root] = cpsi_br_disc[cpsi_br_root]
                # Stack frames: [vertex, hidden cell it was reached by (-1 at the root),
                # next position in its adjacency list].
                cpsi_br_stack = [[cpsi_br_root, -1, 0]]
                while len(cpsi_br_stack) > 0:
                    cpsi_br_top = cpsi_br_stack[-1]
                    cpsi_br_v = cpsi_br_top[0]
                    if cpsi_br_top[2] < len(cpsi_br_adj[cpsi_br_v]):
                        cpsi_br_k = cpsi_br_adj[cpsi_br_v][cpsi_br_top[2]]
                        cpsi_br_top[2] += 1
                        if cpsi_br_k == cpsi_br_top[1]:
                            continue
                        cpsi_br_w = cpsi_r + cpsi_br_k % cpsi_c if cpsi_br_v < cpsi_r else cpsi_br_k // cpsi_c
                        if cpsi_br_w not in cpsi_br_disc:
                            cpsi_br_disc[cpsi_br_w] = len(cpsi_br_disc) + 1
                            cpsi_br_low[cpsi_br_w] = cpsi_br_disc[cpsi_br_w]
                            cpsi_br_stack.append([cpsi_br_w, cpsi_br_k, 0])
                        else:
                            cpsi_br_low[cpsi_br_v] = min(cpsi_br_low[cpsi_br_v], cpsi_br_disc[cpsi_br_w])
                    else:
                        cpsi_br_stack.pop()
                        if len(cpsi_br_stack) > 0:
                            cpsi_br_u = cpsi_br_stack[-1][0]
                            cpsi_br_low[cpsi_br_u] = min(cpsi_br_low[cpsi_br_u], cpsi_br_low[cpsi_br_v])
                            if cpsi_br_low[cpsi_br_v] > cpsi_br_disc[cpsi_br_u]:
                                cpsi_br_found.append(cpsi_br_top[1])
            for cpsi_br_k in sorted(cpsi_br_found):
                if len(cpsi_br_adj[cpsi_br_k // cpsi_c]) > 1 and len(cpsi_br_adj[cpsi_r + cpsi_br_k % cpsi_c]) > 1:
                    cpsi_bad.append(f"entry {cpsi_pair} leaves hidden cell at row index {cpsi_br_k // cpsi_c}, "
                                    f"column index {cpsi_br_k % cpsi_c} recoverable from the released totals")
        # INTENT: Missing-partner scan. A record whose partner column is missing sits outside
        # the grid but inside both categorical blocks' counts. Extend the grid by a "partner
        # missing" column (row category i, the second pair column missing) and a "partner
        # missing" row (the first pair column missing, column category j); the both-missing
        # corner is then fixed by released facts, corner = (row_count - nonmissing_n of
        # position 0) + (row_count - nonmissing_n of position 1) - (row_count - n), so it is
        # known, not an edge. The extended graph's vertices are the rows, the columns, the
        # missing row and the missing column; its edges are the hidden cells plus every
        # missing-partner cell of a line whose total (nonmissing_n - n of its column) is
        # non-zero — a line totalling 0 is a line of known zeros and adds no edge. With
        # every vertex total released, a missing-partner cell is pinned exactly iff its
        # edge is a bridge, and its value is the cut: over the side S of the graph without
        # it that holds its row-side end, value = sum over S's row-side vertices of
        # (total - known cells) minus the same sum over S's column-side vertices. The
        # weights below fold the known cells (visible cells, the corner) into each vertex.
        # A bridge also present when EVERY grid cell is hidden — a missing-partner column
        # cell of a one-row grid, a missing-partner row cell of a one-column grid — is
        # pinned by the released n and missing counts alone, whatever the grid shows, so it
        # is exempt (a documented residual). Every other bridge whose value is negative or
        # in (0, gate) is a [FAIL] naming the entry and the position, never the value.
        # REASONING: the categorical blocks release every level count over ALL non-missing
        # records, while the grid counts pair-complete records only; a fully visible row
        # then leaves "level count minus row sum" — the count of that category among records
        # missing the partner — on the wire. Zero-total lines change nothing, so with no
        # missing value in either pair column this scan adds no edge and no finding. An
        # all-null grid (collapsed or not) leaves exactly the all-hidden graph, so it is
        # skipped. One iterative low-link walk finds every bridge and the subtree sums give
        # each cut, so the cost stays linear in the grid.
        # ASSUMES: grid rows / cols follow the released categories in the profilers' order
        # (kept labels in code-point order, then __OTHER__), checked above by count only;
        # every released total is a whole number >= 0, their sum is below 2^53 (so both
        # languages add exactly), and labels are distinct — otherwise the scan cannot run
        # and the entry is [NOT VERIFIED] evidence. Vertices: row i is i, column j is
        # rows + j, the missing row rows + cols, the missing column rows + cols + 1.
        if cpsi_x_run:
            cpsi_xn = cpsi_ct.get("n")
            cpsi_xnn = [cpsi_x_cols[0].get("nonmissing_n"), cpsi_x_cols[1].get("nonmissing_n")]
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < cpsi_max_exact and x == int(x)
                       for x in [cpsi_xn] + cpsi_xnn):
                cpsi_absent.append(f"entry {cpsi_pair} lacks the released totals the missing-partner scan needs")
            else:
                cpsi_xn = int(cpsi_xn)
                cpsi_xnn = [int(x) for x in cpsi_xnn]
                for cpsi_p in (0, 1):
                    if cpsi_xn > cpsi_xnn[cpsi_p]:
                        cpsi_bad.append(f"entry {cpsi_pair} has an n above the nonmissing_n of pair position {cpsi_p}")
                # Line totals: records with a category of position 0 and position 1 missing,
                # and records with position 0 missing and a category of position 1.
                cpsi_xa = cpsi_xnn[0] - cpsi_xn
                cpsi_xb = cpsi_xnn[1] - cpsi_xn
                cpsi_xtot = []
                if cpsi_xa >= 0 and cpsi_xb >= 0 and cpsi_xa + cpsi_xb > 0 and len(cpsi_nulls) < len(cpsi_grid):
                    for cpsi_pc in cpsi_x_cols:
                        cpsi_lvs = cpsi_pc["categorical"]["levels"]
                        if not (all(isinstance(lv, dict) and isinstance(lv.get("value"), str)
                                    and isinstance(lv.get("count"), (int, float)) and not isinstance(lv.get("count"), bool)
                                    and 0 <= lv["count"] < cpsi_max_exact and lv["count"] == int(lv["count"]) for lv in cpsi_lvs)
                                and len(set(lv["value"] for lv in cpsi_lvs)) == len(cpsi_lvs)):
                            cpsi_xtot = None
                            break
                        # Released categories in grid order: kept labels in code-point order,
                        # then __OTHER__ last when the block releases it.
                        cpsi_xcnt = {lv["value"]: int(lv["count"]) for lv in cpsi_lvs}
                        cpsi_xtot.append([cpsi_xcnt[v] for v in sorted(v for v in cpsi_xcnt if v != "__OTHER__")]
                                         + ([cpsi_xcnt["__OTHER__"]] if "__OTHER__" in cpsi_xcnt else []))
                    cpsi_xvis_ok = all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < cpsi_max_exact
                                       and v == int(v) for v in cpsi_vis)
                    if (cpsi_xtot is None or not cpsi_xvis_ok
                            or sum(cpsi_xtot[0]) + sum(cpsi_xtot[1]) + 2 * sum(int(v) for v in cpsi_vis)
                            + cpsi_xnn[0] + cpsi_xnn[1] + 2 * cpsi_xn >= cpsi_max_exact):
                        cpsi_absent.append(f"entry {cpsi_pair} lacks the released totals the missing-partner scan needs")
                    else:
                        # Vertex weights: (total - known cells) for a row-side vertex and its
                        # negative for a column-side one. The missing row's residual is
                        # nonmissing_n(1) - n and the missing column's nonmissing_n(0) - n
                        # (their totals minus the known corner).
                        cpsi_xw = [0] * (cpsi_r + cpsi_c + 2)
                        for cpsi_i in range(cpsi_r):
                            cpsi_xw[cpsi_i] = cpsi_xtot[0][cpsi_i] - sum(int(v) for v in cpsi_grid[cpsi_i * cpsi_c:(cpsi_i + 1) * cpsi_c] if v is not None)
                        for cpsi_j in range(cpsi_c):
                            cpsi_xw[cpsi_r + cpsi_j] = -(cpsi_xtot[1][cpsi_j] - sum(int(cpsi_grid[cpsi_i * cpsi_c + cpsi_j]) for cpsi_i in range(cpsi_r)
                                                                                   if cpsi_grid[cpsi_i * cpsi_c + cpsi_j] is not None))
                        cpsi_xw[cpsi_r + cpsi_c] = cpsi_xb
                        cpsi_xw[cpsi_r + cpsi_c + 1] = -cpsi_xa
                        # Edges, row-side end first: the hidden cells (row-major), then the
                        # missing-partner column cells (rows 0..), then the missing-partner row
                        # cells (columns 0..), each line only when its total is non-zero.
                        cpsi_xu = [cpsi_k // cpsi_c for cpsi_k in cpsi_nulls]
                        cpsi_xv = [cpsi_r + cpsi_k % cpsi_c for cpsi_k in cpsi_nulls]
                        cpsi_xcore = len(cpsi_xu)
                        if cpsi_xa > 0:
                            cpsi_xu += list(range(cpsi_r))
                            cpsi_xv += [cpsi_r + cpsi_c + 1] * cpsi_r
                        if cpsi_xb > 0:
                            cpsi_xu += [cpsi_r + cpsi_c] * cpsi_c
                            cpsi_xv += [cpsi_r + cpsi_j for cpsi_j in range(cpsi_c)]
                        cpsi_xadj = [[] for cpsi_i in range(cpsi_r + cpsi_c + 2)]
                        for cpsi_e in range(len(cpsi_xu)):
                            cpsi_xadj[cpsi_xu[cpsi_e]].append(cpsi_e)
                            cpsi_xadj[cpsi_xv[cpsi_e]].append(cpsi_e)
                        # Iterative low-link walk; frames are [vertex, edge it was reached by
                        # (-1 at a root), next adjacency position]. cpsi_xsub accumulates each
                        # vertex's subtree weight, so a bridge's cut is its child's subtree.
                        cpsi_xdisc = [0] * (cpsi_r + cpsi_c + 2)
                        cpsi_xlow = [0] * (cpsi_r + cpsi_c + 2)
                        cpsi_xsub = list(cpsi_xw)
                        cpsi_xtime = 0
                        cpsi_xfound = []
                        for cpsi_xroot in range(cpsi_r + cpsi_c + 2):
                            if cpsi_xdisc[cpsi_xroot] > 0 or len(cpsi_xadj[cpsi_xroot]) == 0:
                                continue
                            cpsi_xtime += 1
                            cpsi_xdisc[cpsi_xroot] = cpsi_xtime
                            cpsi_xlow[cpsi_xroot] = cpsi_xtime
                            cpsi_xstack = [[cpsi_xroot, -1, 0]]
                            while len(cpsi_xstack) > 0:
                                cpsi_xtop = cpsi_xstack[-1]
                                cpsi_xvx = cpsi_xtop[0]
                                if cpsi_xtop[2] < len(cpsi_xadj[cpsi_xvx]):
                                    cpsi_e = cpsi_xadj[cpsi_xvx][cpsi_xtop[2]]
                                    cpsi_xtop[2] += 1
                                    if cpsi_e == cpsi_xtop[1]:
                                        continue
                                    cpsi_xw2 = cpsi_xv[cpsi_e] if cpsi_xu[cpsi_e] == cpsi_xvx else cpsi_xu[cpsi_e]
                                    if cpsi_xdisc[cpsi_xw2] == 0:
                                        cpsi_xtime += 1
                                        cpsi_xdisc[cpsi_xw2] = cpsi_xtime
                                        cpsi_xlow[cpsi_xw2] = cpsi_xtime
                                        cpsi_xstack.append([cpsi_xw2, cpsi_e, 0])
                                    else:
                                        cpsi_xlow[cpsi_xvx] = min(cpsi_xlow[cpsi_xvx], cpsi_xdisc[cpsi_xw2])
                                else:
                                    cpsi_xstack.pop()
                                    if len(cpsi_xstack) > 0:
                                        cpsi_xpar = cpsi_xstack[-1][0]
                                        cpsi_xlow[cpsi_xpar] = min(cpsi_xlow[cpsi_xpar], cpsi_xlow[cpsi_xvx])
                                        cpsi_xsub[cpsi_xpar] += cpsi_xsub[cpsi_xvx]
                                        if cpsi_xlow[cpsi_xvx] > cpsi_xdisc[cpsi_xpar] and cpsi_xtop[1] >= cpsi_xcore:
                                            # The child's subtree is one side of the cut; its sum
                                            # is the value when the child is the row-side end.
                                            cpsi_xfound.append((cpsi_xtop[1], cpsi_xsub[cpsi_xvx] if cpsi_xu[cpsi_xtop[1]] == cpsi_xvx
                                                                else -cpsi_xsub[cpsi_xvx]))
                        cpsi_xungated = False
                        for cpsi_e, cpsi_xval in sorted(cpsi_xfound):
                            cpsi_xt = cpsi_e - cpsi_xcore
                            if cpsi_xa > 0 and cpsi_xt < cpsi_r:
                                cpsi_xside, cpsi_xpos, cpsi_xexempt = "row", cpsi_xt, cpsi_r == 1
                            else:
                                cpsi_xside, cpsi_xpos, cpsi_xexempt = "column", cpsi_xt - (cpsi_r if cpsi_xa > 0 else 0), cpsi_c == 1
                            if cpsi_xexempt:
                                continue
                            if cpsi_xgate is None:
                                cpsi_xungated = True
                            elif cpsi_xval < 0 or 0 < cpsi_xval < cpsi_xgate:
                                cpsi_bad.append(f"entry {cpsi_pair} leaves the missing-partner cell at {cpsi_xside} index {cpsi_xpos} recoverable from the released totals")
                        if cpsi_xungated:
                            cpsi_absent.append(f"entry {cpsi_pair} cannot gate its missing-partner cells: expected_threshold or settings.suppression_threshold is unusable")
    if len(cpsi_bad) > 0:
        print(f"[FAIL] crosstab_schema_and_suppression: {cpsi_bad[0]}" + (f" (+{len(cpsi_bad) - 1} more)" if len(cpsi_bad) > 1 else ""))
        cps_intake["failed"] += 1
    elif len(cpsi_absent) > 0:
        print(f"[NOT VERIFIED] crosstab_schema_and_suppression: {cpsi_absent[0]}" + (f" (+{len(cpsi_absent) - 1} more)" if len(cpsi_absent) > 1 else ""))
        cps_intake["not_verified"] += 1
    else:
        print(f"[PASS] crosstab_schema_and_suppression: {len(cpsi_crosstabs)} entries, {cpsi_cells} cells examined, {cpsi_hidden} hidden as null, {cpsi_collapsed} fully collapsed, no hidden cell recoverable from the row and column totals")
        cps_intake["passed"] += 1

# Count line, then verdict derived from the counts. Every check above reaches its own
# outcome line without raising, so the count line and verdict are always printed.
cpsi_checks_run = cps_intake["passed"] + cps_intake["warning"] + cps_intake["failed"]
if cps_intake["failed"] > 0 or cps_intake["not_verified"] > 0 or cpsi_checks_run == 0:
    cpsi_verdict = "FAILED"
elif cps_intake["warning"] > 0:
    cpsi_verdict = "PASSED WITH WARNINGS"
else:
    cpsi_verdict = "PASSED"

print(f"\nChecks: {cps_intake['passed']} passed, {cps_intake['warning']} warnings, {cps_intake['failed']} failed, {cps_intake['not_verified']} not verified, {cps_intake['skipped']} skipped")
print(f"CPS-INTAKE VALIDATION: {cpsi_verdict}")
print("=" * 60)

if cpsi_verdict == "FAILED":
    raise ValueError("CPS-INTAKE FAILED - see details above")
```

**R:**
```r
# --- CPS-INTAKE Validation ---
# INTENT: Verify that a returned profile report is structurally sound, internally
# consistent, and free of disclosure-shaped content before generation reads it.
# REASONING: Same contract as the Python block. jsonlite parses with
# simplifyVector = FALSE so the nested structure survives intact: simplification
# would silently turn a ragged cells array into something else and a null cell
# into NA, which is exactly the distinction the suppression checks rest on.
# ASSUMES: report_path / tier / expected_threshold / not_applicable are assigned in the
# `# --- Config ---` region below; report_path is NULL when intake staged no file.
# A field of the wrong JSON type never stops the block: it becomes a [FAIL] when it is
# the field a check validates, or a [NOT VERIFIED] when it is evidence a check needs.
# A JSON object is a named list and a JSON array an unnamed one (jsonlite keeps `{}`
# named), so `is.list()` alone is never used as a type test. Printed lists are sorted
# with method = "radix" (C-locale byte order) to match Python's sorted().
library(jsonlite)

# --- Config ---
report_path <- NULL      # path to the returned profile report JSON; NULL if intake staged no file
tier <- NULL             # 1 | 2 | 3 — the tier approved at PSU-DS1 (STATE Disclosure Tier; at T4, T4 Companion Profile Tier) — never the report's settings.tier; NULL if not recorded
expected_threshold <- NULL # the suppression threshold approved at tier selection (STATE.md § Synthetic Path Tracking); NULL if not recorded
not_applicable <- list() # e.g. list(correlation_matrix_wellformed = "tier 2 — the report releases no correlations")

cat("\n")
cat(strrep("=", 60), "\n")
cat("CPS-INTAKE VALIDATION: PROFILE REPORT INTAKE\n")
cat(strrep("=", 60), "\n")

cps_intake <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# INTENT: One definition of "blank" for both languages: a string is blank when every
# code point is Unicode whitespace — exactly the 29 code points Python's str.strip()
# removes (str.isspace). trimws(whitespace = "[\\h\\v]") is not that set: PCRE's \h\v
# omit U+001C-U+001F and include U+180E. Testing code points needs no regex, so it also
# cannot stop on a string that is not valid UTF-8 (utf8ToInt gives NA: not blank).
cpsi_ws <- c(9:13, 28:32, 133, 160, 5760, 8192:8202, 8232, 8233, 8239, 8287, 12288)

# INTENT: A declared skip without a reason is indistinguishable from a silent one, so
# it is dropped — but the key stays visible to the two sweeps below, so an empty
# reason cannot be used to smuggle a declaration past the non-declarable or
# unrecognized-key gates. The declarable check it named does not then run either:
# `cpsi_empty_reason` carries it to a [NOT VERIFIED], because printing a [PASS]
# would answer a question the author explicitly withdrew.
cpsi_declared_keys <- names(not_applicable)
if (is.null(cpsi_declared_keys)) cpsi_declared_keys <- character(0)
cpsi_declared_keys <- sort(cpsi_declared_keys, method = "radix")
na_keep <- character(0)
for (k in cpsi_declared_keys) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && !all(utf8ToInt(v) %in% cpsi_ws)) na_keep <- c(na_keep, k)
}
cpsi_empty_reason <- setdiff(cpsi_declared_keys, na_keep)
not_applicable <- not_applicable[na_keep]

# INTENT: Disclosure-critical checks may never be declared not applicable.
cpsi_non_declarable <- c("no_released_count_below_threshold", "no_raw_value_shaped_fields",
                         "identifier_columns_value_free", "crosstab_schema_and_suppression")
for (cpsi_key in cpsi_non_declarable) {
  if (cpsi_key %in% cpsi_declared_keys) {
    cat(sprintf("[FAIL] %s: non-declarable check declared not_applicable under key '%s'\n",
                cpsi_key, cpsi_key))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
    not_applicable[[cpsi_key]] <- NULL
  }
}

# INTENT: A not_applicable key that names no check of this block is a silent no-op.
# REASONING: A typo'd or stale key would otherwise declare nothing and be ignored,
# leaving the author believing a check was skipped when it in fact ran (or the
# reverse). Naming it once is the only way the log can carry the discrepancy.
cpsi_declarable <- c("report_version", "required_top_level_keys", "row_count_positive",
                     "percentiles_monotone", "category_counts_le_rowcount",
                     "missing_rate_in_unit_interval", "correlation_matrix_wellformed",
                     "embedded_validation_complete")
for (cpsi_key in cpsi_declared_keys) {
  if (cpsi_key %in% cpsi_non_declarable || cpsi_key %in% cpsi_declarable) next
  cat(sprintf("[FAIL] not_applicable: unrecognized key '%s' (declarable keys: %s)\n",
              cpsi_key, paste(cpsi_declarable, collapse = ", ")))
  cps_intake["failed"] <- cps_intake["failed"] + 1L
  not_applicable[[cpsi_key]] <- NULL
}

cpsi_parse_error <- "report did not parse as JSON (parser message withheld: it can quote report content)"
cpsi_report <- NULL
cpsi_load_error <- NULL
cpsi_report_strings <- character(0)
if (is.null(report_path)) {
  cpsi_load_error <- "report_path is not set — no report was staged for intake"
} else if (!(file.exists(report_path) && !dir.exists(report_path))) {
  cpsi_load_error <- sprintf("no file at report_path '%s'", report_path)
} else {
  # REASONING: the parser's own message is withheld — it can quote report text, and
  # the Python parser words it differently, so neither belongs on an outcome line.
  # Parsing is STRICT, with the same outcome as the Python block and as CPS-GEN on
  # every file. jsonlite already refuses NaN / Infinity / -Infinity, but it KEEPS a
  # duplicate object key as a repeated name (`[[` then reads the first, where Python's
  # dict keeps the last), so the sweep below makes a duplicate key at any depth a parse
  # error, and refuses nesting deeper than the schema could need (cap 64): the two
  # parsers give up at different depths, and the cap makes the outcome depend on the
  # file rather than on the parser.
  # INTENT: Refuse, before the parser runs, every input the two parsers would read
  # differently: a leading UTF-8 byte-order mark (jsonlite accepts it with a warning,
  # json.loads refuses it), a NUL byte (R's text reader would stop at it), invalid
  # UTF-8, an escaped NUL (jsonlite cuts the string there) and an unpaired surrogate
  # escape (jsonlite replaces it). The bytes are read whole and parsed as text with
  # parse_json(), which never treats its input as a path or URL.
  cpsi_text <- NULL
  cpsi_raw_bytes <- try(readBin(report_path, what = "raw", n = file.info(report_path)$size), silent = TRUE)
  if (!inherits(cpsi_raw_bytes, "try-error") &&
      !(length(cpsi_raw_bytes) >= 3 && identical(cpsi_raw_bytes[1:3], as.raw(c(0xef, 0xbb, 0xbf)))) &&
      !any(cpsi_raw_bytes == as.raw(0))) {
    cpsi_text <- rawToChar(cpsi_raw_bytes)
    Encoding(cpsi_text) <- "UTF-8"
    if (!validUTF8(cpsi_text)) cpsi_text <- NULL
  }
  if (!is.null(cpsi_text)) {
    # INTENT: Walk the escape sequences left to right, as the Python block does. An
    # escaped backslash is one token, so the text `\\u0000` is not an escape.
    # ASSUMES: a \u escape is exactly six characters, so a surrogate pair is a high
    # escape immediately followed by a low one.
    cpsi_m <- gregexpr("\\\\(?:u[0-9a-fA-F]{4}|[^u])", cpsi_text, perl = TRUE)[[1]]
    cpsi_pos <- if (cpsi_m[1] == -1L) integer(0) else as.integer(cpsi_m)
    cpsi_toks <- if (cpsi_m[1] == -1L) character(0) else regmatches(cpsi_text, list(cpsi_m))[[1]]
    cpsi_cps <- rep(-1, length(cpsi_toks))
    cpsi_is_u <- substr(cpsi_toks, 2, 2) == "u"
    cpsi_cps[cpsi_is_u] <- strtoi(substr(cpsi_toks[cpsi_is_u], 3, 6), 16L)
    for (cpsi_i in seq_along(cpsi_toks)) {
      cpsi_cp <- cpsi_cps[cpsi_i]
      cpsi_hi_ok <- cpsi_i < length(cpsi_toks) && cpsi_pos[cpsi_i + 1L] == cpsi_pos[cpsi_i] + 6L &&
        cpsi_cps[cpsi_i + 1L] >= 0xDC00 && cpsi_cps[cpsi_i + 1L] <= 0xDFFF
      cpsi_lo_ok <- cpsi_i > 1L && cpsi_pos[cpsi_i - 1L] == cpsi_pos[cpsi_i] - 6L &&
        cpsi_cps[cpsi_i - 1L] >= 0xD800 && cpsi_cps[cpsi_i - 1L] <= 0xDBFF
      if (cpsi_cp == 0 || (cpsi_cp >= 0xD800 && cpsi_cp <= 0xDBFF && !cpsi_hi_ok) ||
          (cpsi_cp >= 0xDC00 && cpsi_cp <= 0xDFFF && !cpsi_lo_ok)) {
        cpsi_text <- NULL
        break
      }
    }
  }
  if (!is.null(cpsi_text)) {
    # INTENT: A JSON number token longer than 64 characters (sign, digits, fraction and
    # exponent together), outside strings, is a parse error — the same two patterns on
    # the same text as the Python block.
    # REASONING: jsonlite reads a huge literal as Inf where Python keeps an exact int (or
    # refuses one of more than 4300 digits), so the same file got two verdicts. Strings
    # are blanked first, so digits inside a label are never counted.
    cpsi_unstrung <- gsub('(?s)"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"', '""', cpsi_text, perl = TRUE)
    if (grepl("[-+0-9.eE]{65,}", cpsi_unstrung, perl = TRUE)) cpsi_text <- NULL
  }
  cpsi_parsed <- if (is.null(cpsi_text)) NULL else try(jsonlite::parse_json(cpsi_text, simplifyVector = FALSE), silent = TRUE)
  if (is.null(cpsi_text) || inherits(cpsi_parsed, "try-error")) {
    cpsi_load_error <- cpsi_parse_error
  } else {
    # INTENT: Breadth-first sweep over every container in the tree that refuses a
    # duplicate object name and any container nested deeper than 64 levels, counting
    # the top-level object as level 1; an array is an unnamed list, an object a named
    # one (an empty object has names() of length 0, never NULL), and each is one level.
    # The sweep also collects every key and string value, so any report text a line
    # prints can be escaped (see the escape table below).
    cpsi_max_depth <- 64L
    cpsi_queue <- list(cpsi_parsed)
    cpsi_queue_depth <- 1L
    cpsi_qi <- 1L
    cpsi_refused <- FALSE
    while (cpsi_qi <= length(cpsi_queue) && !cpsi_refused) {
      cpsi_node <- cpsi_queue[[cpsi_qi]]
      cpsi_d <- cpsi_queue_depth[cpsi_qi]
      cpsi_qi <- cpsi_qi + 1L
      if (is.list(cpsi_node)) {
        if (cpsi_d > cpsi_max_depth || (!is.null(names(cpsi_node)) && anyDuplicated(names(cpsi_node)) > 0)) cpsi_refused <- TRUE
        if (!is.null(names(cpsi_node))) cpsi_report_strings <- c(cpsi_report_strings, names(cpsi_node))
        cpsi_queue <- c(cpsi_queue, unname(cpsi_node))
        cpsi_queue_depth <- c(cpsi_queue_depth, rep(cpsi_d + 1L, length(cpsi_node)))
      } else if (is.character(cpsi_node)) {
        cpsi_report_strings <- c(cpsi_report_strings, cpsi_node)
      }
    }
    if (cpsi_refused) {
      cpsi_load_error <- cpsi_parse_error
    } else if (!is.list(cpsi_parsed) || is.null(names(cpsi_parsed))) {
      cpsi_load_error <- "report parsed, but its top level is not a JSON object"
    } else {
      cpsi_report <- cpsi_parsed
    }
  }
}

# INTENT: Escape every report-derived string before it reaches an outcome line,
# exactly as the Python block does: a character outside printable ASCII (0x20-0x7E)
# prints as \uXXXX in lowercase hex, and one above U+FFFF as its UTF-16 surrogate pair.
# REASONING: A column name or key carrying a newline or control character could
# otherwise forge an extra outcome line (a fake count line or verdict), and a non-ASCII
# one could fail the write on a console that cannot encode it. The table covers every
# key and string value of the parsed report; each print site looks its text up with
# match(), which — unlike [[ ]] — also finds an empty name. Config strings
# (report_path, not_applicable reasons) are the researcher's own text and print as written.
cpsi_esc_from <- unique(cpsi_report_strings)
cpsi_esc_to <- character(length(cpsi_esc_from))
for (cpsi_i in seq_along(cpsi_esc_from)) {
  cpsi_cp <- utf8ToInt(enc2utf8(cpsi_esc_from[cpsi_i]))
  if (length(cpsi_cp) == 0 || anyNA(cpsi_cp)) {
    cpsi_esc_to[cpsi_i] <- if (length(cpsi_cp) == 0) "" else "\\ufffd"
    next
  }
  cpsi_esc_to[cpsi_i] <- paste(ifelse(cpsi_cp >= 32L & cpsi_cp <= 126L, intToUtf8(cpsi_cp, multiple = TRUE),
                                      ifelse(cpsi_cp < 65536L, sprintf("\\u%04x", cpsi_cp),
                                             sprintf("\\u%04x\\u%04x", 55296L + (cpsi_cp - 65536L) %/% 1024L,
                                                     56320L + (cpsi_cp - 65536L) %% 1024L))), collapse = "")
}
# INTENT: Value-shaped key names are matched case-insensitively over ASCII letters
# only, exactly as the Python block does (tolower() follows the locale and folds some
# non-ASCII letters; chartr() over the 26 ASCII letters folds nothing else).
cpsi_upper_ascii <- "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
cpsi_lower_ascii <- "abcdefghijklmnopqrstuvwxyz"

# INTENT: One numeric model for both languages: a JSON number is usable only when it
# is finite and |v| < 2^53 (the profiler refuses larger magnitudes; jsonlite turns a
# 401-digit integer into Inf). Whole numbers are tested as v == floor(v), never via
# as.integer(), which turns 3e9 into NA and would hand `if ()` an NA.
cpsi_max_exact <- 2^53

cpsi_columns_raw <- NULL
cpsi_columns <- NULL
cpsi_row_count <- NULL
cpsi_threshold <- NULL
cpsi_relationships <- NULL
cpsi_crosstabs <- list()
cpsi_crosstabs_not_array <- FALSE
if (!is.null(cpsi_report)) {
  cpsi_x <- cpsi_report[["columns"]]
  if (is.list(cpsi_x) && is.null(names(cpsi_x))) {
    cpsi_columns_raw <- cpsi_x
    cpsi_columns <- Filter(function(c) is.list(c) && !is.null(names(c)), cpsi_x)
  }
  cpsi_x <- cpsi_report[["settings"]]
  if (is.list(cpsi_x) && !is.null(names(cpsi_x))) cpsi_threshold <- cpsi_x[["suppression_threshold"]]
  cpsi_x <- cpsi_report[["dataset"]]
  if (is.list(cpsi_x) && !is.null(names(cpsi_x))) cpsi_row_count <- cpsi_x[["row_count"]]
  cpsi_x <- cpsi_report[["relationships"]]
  if (is.list(cpsi_x) && !is.null(names(cpsi_x))) {
    cpsi_relationships <- cpsi_x
    cpsi_x <- cpsi_relationships[["crosstabs"]]
    if (is.list(cpsi_x) && is.null(names(cpsi_x))) {
      cpsi_crosstabs <- cpsi_x
    } else if (!is.null(cpsi_x)) {
      cpsi_crosstabs_not_array <- TRUE
    }
  }
}
cpsi_col_names <- character(0)
for (cpsi_col in if (is.null(cpsi_columns)) list() else cpsi_columns) {
  if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_col_names <- c(cpsi_col_names, cpsi_col[["name"]])
}
cpsi_tier_ok <- is.numeric(tier) && length(tier) == 1 && !is.na(tier) && tier %in% c(1, 2, 3)
cpsi_tier_label <- if (cpsi_tier_ok) as.character(as.integer(tier)) else if (is.null(tier)) "unrecorded" else "invalid"
cpsi_rep_tier <- if (!is.null(cpsi_report) && is.list(cpsi_report[["settings"]]) && !is.null(names(cpsi_report[["settings"]]))) cpsi_report[["settings"]][["tier"]] else NULL
cpsi_rep_tier_ok <- is.numeric(cpsi_rep_tier) && length(cpsi_rep_tier) == 1 && !is.na(cpsi_rep_tier) && cpsi_rep_tier %in% c(1, 2, 3)
# INTENT: "released relationships content" is any `relationships` value other than an
# absent key, JSON null, or an empty object / array (same rule as the Python block).
cpsi_rel_raw <- if (is.null(cpsi_report)) NULL else cpsi_report[["relationships"]]
cpsi_rel_content <- !is.null(cpsi_rel_raw) && !(is.list(cpsi_rel_raw) && length(cpsi_rel_raw) == 0)

# INTENT: Bind the role subsets once — every later check partitions the same way. A
# role counts only as a single string, as in Python (R's list == "x" would coerce).
cpsi_num_cols <- list()
cpsi_cat_cols <- list()
cpsi_id_cols <- list()
cpsi_rated <- list()
if (!is.null(cpsi_columns)) {
  for (cpsi_col in cpsi_columns) {
    cpsi_role <- cpsi_col[["role"]]
    if (!(is.character(cpsi_role) && length(cpsi_role) == 1)) cpsi_role <- NA_character_
    if (isTRUE(cpsi_role == "numeric")) cpsi_num_cols <- c(cpsi_num_cols, list(cpsi_col))
    if (isTRUE(cpsi_role == "categorical")) cpsi_cat_cols <- c(cpsi_cat_cols, list(cpsi_col))
    if (isTRUE(cpsi_role == "identifier") || isTRUE(cpsi_col[["is_identifier"]])) {
      cpsi_id_cols <- c(cpsi_id_cols, list(cpsi_col))
    }
    if ("missing_rate" %in% names(cpsi_col)) cpsi_rated <- c(cpsi_rated, list(cpsi_col))
  }
}
cpsi_row_count_ok <- is.numeric(cpsi_row_count) && length(cpsi_row_count) == 1 &&
  !is.na(cpsi_row_count) && abs(cpsi_row_count) < cpsi_max_exact &&
  cpsi_row_count == floor(cpsi_row_count) && cpsi_row_count > 0

# Check: report_version
if ("report_version" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] report_version: %s\n", not_applicable[["report_version"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("report_version" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] report_version: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] report_version: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!("report_version" %in% names(cpsi_report))) {
  cat("[NOT VERIFIED] report_version: the report carries no report_version field\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!(is.character(cpsi_report[["report_version"]]) && length(cpsi_report[["report_version"]]) == 1 &&
             grepl("^[0-9.]{1,16}$", cpsi_report[["report_version"]]))) {
  # REASONING: only a dotted version string is echoed; anything else could be report
  # content, so it is named by shape, never quoted.
  cat("[FAIL] report_version: the report_version field is not a dotted version string — a legacy or unknown report is never relabelled into compliance\n")
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else if (!identical(cpsi_report[["report_version"]], "2.0")) {
  cat(sprintf("[FAIL] report_version: '%s' is not the accepted 2.0 schema — a legacy or unknown report is never relabelled into compliance\n",
              cpsi_report[["report_version"]]))
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else {
  cat("[PASS] report_version: '2.0' — the accepted schema version\n")
  cps_intake["passed"] <- cps_intake["passed"] + 1L
}

# Check: required top-level keys
cpsi_required_top <- c("report_version", "dataset_name", "generated_utc", "generator",
                       "settings", "dataset", "columns", "validation")
if ("required_top_level_keys" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] required_top_level_keys: %s\n", not_applicable[["required_top_level_keys"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("required_top_level_keys" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] required_top_level_keys: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] required_top_level_keys: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  cpsi_present <- names(cpsi_report)
  cpsi_missing <- sort(setdiff(cpsi_required_top, cpsi_present), method = "radix")
  cpsi_unexpected <- sort(setdiff(cpsi_present, c(cpsi_required_top, "relationships")), method = "radix")
  if (cpsi_tier_ok && tier == 3 && !("relationships" %in% cpsi_present)) {
    cpsi_missing <- sort(c(cpsi_missing, "relationships"), method = "radix")
  }
  # INTENT: a present key of the wrong JSON type is a schema violation this check owns.
  cpsi_top_kinds <- c(dataset_name = "string", generated_utc = "string", generator = "object",
                      settings = "object", dataset = "object", columns = "array",
                      validation = "object", relationships = "object")
  cpsi_wrong_kind <- character(0)
  for (cpsi_k in names(cpsi_top_kinds)) {
    if (!(cpsi_k %in% cpsi_present)) next
    cpsi_x <- cpsi_report[[cpsi_k]]
    cpsi_kind_ok <- switch(cpsi_top_kinds[[cpsi_k]],
                           string = is.character(cpsi_x) && length(cpsi_x) == 1,
                           object = is.list(cpsi_x) && !is.null(names(cpsi_x)),
                           array = is.list(cpsi_x) && is.null(names(cpsi_x)))
    if (!cpsi_kind_ok) cpsi_wrong_kind <- c(cpsi_wrong_kind, cpsi_k)
  }
  cpsi_wrong_kind <- sort(cpsi_wrong_kind, method = "radix")
  if (length(cpsi_missing) > 0 || length(cpsi_unexpected) > 0 || length(cpsi_wrong_kind) > 0) {
    cat(sprintf("[FAIL] required_top_level_keys: missing [%s], unexpected [%s]%s (tier %s)\n",
                paste(cpsi_missing, collapse = ", "), paste(cpsi_esc_to[match(cpsi_unexpected, cpsi_esc_from)], collapse = ", "),
                if (length(cpsi_wrong_kind) > 0) sprintf(", wrong JSON type [%s]", paste(cpsi_wrong_kind, collapse = ", ")) else "",
                cpsi_tier_label))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else {
    cat(sprintf("[PASS] required_top_level_keys: %d of %d required keys present, 0 unexpected (tier %s)\n",
                length(cpsi_required_top), length(cpsi_required_top), cpsi_tier_label))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: row count is a positive integer
if ("row_count_positive" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row_count_positive: %s\n", not_applicable[["row_count_positive"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("row_count_positive" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] row_count_positive: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] row_count_positive: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_row_count)) {
  cat("[NOT VERIFIED] row_count_positive: dataset.row_count is absent — no denominator for the count checks\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!cpsi_row_count_ok) {
  cat("[FAIL] row_count_positive: dataset.row_count is not a positive whole number\n")
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else {
  cat(sprintf("[PASS] row_count_positive: dataset.row_count = %s over %d declared columns\n",
              format(cpsi_row_count, big.mark = ",", scientific = FALSE),
              if (is.null(cpsi_columns_raw)) 0L else length(cpsi_columns_raw)))
  cps_intake["passed"] <- cps_intake["passed"] + 1L
}

# Check: released percentile grids are non-decreasing in probability order
cpsi_pctl_order <- c("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
if ("percentiles_monotone" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] percentiles_monotone: %s\n", not_applicable[["percentiles_monotone"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("percentiles_monotone" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] percentiles_monotone: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] percentiles_monotone: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_columns)) {
  cat("[NOT VERIFIED] percentiles_monotone: the report carries no columns array\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (length(cpsi_num_cols) == 0) {
  cat(sprintf("[SKIPPED] percentiles_monotone: report declares 0 numeric columns at tier %s (0 grids, 0 percentiles)\n",
              cpsi_tier_label))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else {
  cpsi_grids <- 0L
  cpsi_points <- 0L
  cpsi_bad <- character(0)
  cpsi_absent <- character(0)
  for (cpsi_col in cpsi_num_cols) {
    cpsi_name <- if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    cpsi_blk <- cpsi_col[["numeric"]]
    if (!(is.list(cpsi_blk) && !is.null(names(cpsi_blk)))) {
      cpsi_absent <- c(cpsi_absent, sprintf("column '%s' declares role numeric but has no numeric block", cpsi_name))
    } else if (!("percentiles" %in% names(cpsi_blk))) {
      if (!(isTRUE(cpsi_blk[["withheld"]]) || isTRUE(cpsi_blk[["all_missing"]]) || isTRUE(cpsi_blk[["constant"]]))) {
        cpsi_absent <- c(cpsi_absent, sprintf("column '%s' has a numeric block with no percentiles and no withheld/all_missing/constant marker", cpsi_name))
      }
    } else if (!(is.list(cpsi_blk[["percentiles"]]) && !is.null(names(cpsi_blk[["percentiles"]]))) ||
               length(cpsi_blk[["percentiles"]]) == 0) {
      cpsi_absent <- c(cpsi_absent, sprintf("column '%s' has an empty or non-object percentiles block", cpsi_name))
    } else {
      cpsi_grid <- cpsi_blk[["percentiles"]]
      cpsi_unknown <- setdiff(names(cpsi_grid), cpsi_pctl_order)
      cpsi_keys <- cpsi_pctl_order[cpsi_pctl_order %in% names(cpsi_grid)]
      cpsi_vals <- unlist(lapply(cpsi_keys, function(k) {
        v <- cpsi_grid[[k]]
        if (is.numeric(v) && length(v) == 1 && !is.na(v) && abs(v) < cpsi_max_exact) v else NA_real_
      }))
      if (length(cpsi_unknown) > 0) {
        cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries unrecognized percentile keys [%s]",
                                        cpsi_name, paste(cpsi_esc_to[match(sort(cpsi_unknown, method = "radix"), cpsi_esc_from)], collapse = ", ")))
      } else if (any(is.na(cpsi_vals))) {
        cpsi_absent <- c(cpsi_absent, sprintf("column '%s' has a non-numeric or out-of-range percentile value", cpsi_name))
      } else {
        cpsi_grids <- cpsi_grids + 1L
        cpsi_points <- cpsi_points + length(cpsi_vals)
        if (length(cpsi_vals) > 1) {
          for (cpsi_i in seq(2, length(cpsi_vals))) {
            if (cpsi_vals[cpsi_i] < cpsi_vals[cpsi_i - 1]) {
              cpsi_bad <- c(cpsi_bad, sprintf("column '%s' is non-monotone between %s and %s",
                                              cpsi_name, cpsi_keys[cpsi_i - 1], cpsi_keys[cpsi_i]))
              break
            }
          }
        }
      }
    }
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] percentiles_monotone: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else if (length(cpsi_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] percentiles_monotone: %s%s\n", cpsi_absent[1],
                if (length(cpsi_absent) > 1) sprintf(" (+%d more)", length(cpsi_absent) - 1) else ""))
    cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] percentiles_monotone: %d numeric columns, %d released grids x %d percentiles checked, all non-decreasing\n",
                length(cpsi_num_cols), cpsi_grids, cpsi_points))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: every category count, and each column's level total, is <= row_count
if ("category_counts_le_rowcount" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] category_counts_le_rowcount: %s\n", not_applicable[["category_counts_le_rowcount"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("category_counts_le_rowcount" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] category_counts_le_rowcount: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] category_counts_le_rowcount: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_columns)) {
  cat("[NOT VERIFIED] category_counts_le_rowcount: the report carries no columns array\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (length(cpsi_cat_cols) == 0) {
  cat(sprintf("[SKIPPED] category_counts_le_rowcount: report declares 0 categorical columns at tier %s (0 levels)\n",
              cpsi_tier_label))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if (!cpsi_row_count_ok) {
  cat("[NOT VERIFIED] category_counts_le_rowcount: dataset.row_count is absent or not a positive integer — no comparison basis\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  cpsi_levels_seen <- 0L
  cpsi_bad <- character(0)
  cpsi_absent <- character(0)
  for (cpsi_col in cpsi_cat_cols) {
    cpsi_name <- if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    cpsi_blk <- cpsi_col[["categorical"]]
    if (!(is.list(cpsi_blk) && !is.null(names(cpsi_blk)))) {
      cpsi_absent <- c(cpsi_absent, sprintf("column '%s' declares role categorical but has no categorical block", cpsi_name))
    } else if (!(is.list(cpsi_blk[["levels"]]) && is.null(names(cpsi_blk[["levels"]])))) {
      cpsi_absent <- c(cpsi_absent, sprintf("column '%s' has a categorical block with no levels array", cpsi_name))
    } else {
      cpsi_total <- 0
      cpsi_levels <- cpsi_blk[["levels"]]
      for (cpsi_i in seq_along(cpsi_levels)) {
        cpsi_lv <- cpsi_levels[[cpsi_i]]
        if (!is.list(cpsi_lv) || !("count" %in% names(cpsi_lv))) {
          cpsi_absent <- c(cpsi_absent, sprintf("column '%s' level index %d carries no count field", cpsi_name, cpsi_i - 1L))
          next
        }
        cpsi_v <- cpsi_lv[["count"]]
        if (!(is.numeric(cpsi_v) && length(cpsi_v) == 1 && !is.na(cpsi_v) && abs(cpsi_v) < cpsi_max_exact &&
              cpsi_v == floor(cpsi_v))) {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' level index %d has a non-integer count", cpsi_name, cpsi_i - 1L))
          next
        }
        cpsi_levels_seen <- cpsi_levels_seen + 1L
        cpsi_total <- cpsi_total + cpsi_v
        if (cpsi_v > cpsi_row_count) {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' level index %d exceeds row_count", cpsi_name, cpsi_i - 1L))
        }
      }
      if (cpsi_total > cpsi_row_count) {
        cpsi_bad <- c(cpsi_bad, sprintf("column '%s' level total exceeds row_count", cpsi_name))
      }
    }
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] category_counts_le_rowcount: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else if (length(cpsi_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] category_counts_le_rowcount: %s%s\n", cpsi_absent[1],
                if (length(cpsi_absent) > 1) sprintf(" (+%d more)", length(cpsi_absent) - 1) else ""))
    cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] category_counts_le_rowcount: %d categorical columns, %d levels, every count and column total <= row_count %s\n",
                length(cpsi_cat_cols), cpsi_levels_seen, format(cpsi_row_count, big.mark = ",", scientific = FALSE)))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: missingness rates are finite reals in [0, 1] and agree with nonmissing_n
if ("missing_rate_in_unit_interval" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] missing_rate_in_unit_interval: %s\n", not_applicable[["missing_rate_in_unit_interval"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("missing_rate_in_unit_interval" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] missing_rate_in_unit_interval: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] missing_rate_in_unit_interval: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_columns)) {
  cat("[NOT VERIFIED] missing_rate_in_unit_interval: the report carries no columns array\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (length(cpsi_rated) == 0 && cpsi_tier_ok && tier == 1) {
  cat("[SKIPPED] missing_rate_in_unit_interval: tier 1 releases no missingness rates (0 of 0 columns carry one)\n")
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if (length(cpsi_rated) == 0) {
  cat(sprintf("[NOT VERIFIED] missing_rate_in_unit_interval: no column carries a missing_rate at tier %s, where rates are expected\n",
              cpsi_tier_label))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  cpsi_bad <- character(0)
  cpsi_absent <- character(0)
  cpsi_agreed <- 0L
  for (cpsi_col in cpsi_rated) {
    cpsi_name <- if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    cpsi_v <- cpsi_col[["missing_rate"]]
    if (!(is.numeric(cpsi_v) && length(cpsi_v) == 1 && !is.na(cpsi_v) && abs(cpsi_v) < cpsi_max_exact)) {
      cpsi_bad <- c(cpsi_bad, sprintf("column '%s' has a non-finite or non-numeric missing_rate", cpsi_name))
    } else if (cpsi_v < 0 || cpsi_v > 1) {
      cpsi_bad <- c(cpsi_bad, sprintf("column '%s' has a missing_rate outside [0, 1]", cpsi_name))
    } else {
      cpsi_nm <- cpsi_col[["nonmissing_n"]]
      if (!(is.numeric(cpsi_nm) && length(cpsi_nm) == 1 && !is.na(cpsi_nm) && abs(cpsi_nm) < cpsi_max_exact &&
            cpsi_nm == floor(cpsi_nm))) {
        cpsi_absent <- c(cpsi_absent, sprintf("column '%s' carries a rate but no whole-number nonmissing_n to reconcile it against", cpsi_name))
      } else if (!cpsi_row_count_ok) {
        cpsi_absent <- c(cpsi_absent, "dataset.row_count is absent or not positive — rates cannot be reconciled")
      } else if (abs(cpsi_v - (cpsi_row_count - cpsi_nm) / cpsi_row_count) > 1e-06) {
        cpsi_bad <- c(cpsi_bad, sprintf("column '%s' missing_rate disagrees with nonmissing_n beyond rounding tolerance", cpsi_name))
      } else {
        cpsi_agreed <- cpsi_agreed + 1L
      }
    }
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] missing_rate_in_unit_interval: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else if (length(cpsi_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] missing_rate_in_unit_interval: %s%s\n", cpsi_absent[1],
                if (length(cpsi_absent) > 1) sprintf(" (+%d more)", length(cpsi_absent) - 1) else ""))
    cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] missing_rate_in_unit_interval: %d rates in [0, 1], %d reconciled against nonmissing_n within 1e-06\n",
                length(cpsi_rated), cpsi_agreed))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: released correlation matrices are square, symmetric, unit-diagonal, in [-1, 1]
if ("correlation_matrix_wellformed" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] correlation_matrix_wellformed: %s\n", not_applicable[["correlation_matrix_wellformed"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("correlation_matrix_wellformed" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] correlation_matrix_wellformed: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] correlation_matrix_wellformed: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!cpsi_tier_ok) {
  cat("[NOT VERIFIED] correlation_matrix_wellformed: tier is not a recorded 1/2/3 — the tier decides whether matrices are expected\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (tier < 3) {
  # The count is what the report actually declares (same rule as the Python block).
  cpsi_mats <- 0L
  for (cpsi_k in c("pearson", "spearman")) {
    cpsi_x <- if (is.null(cpsi_relationships)) NULL else cpsi_relationships[[cpsi_k]]
    if (is.list(cpsi_x) && !is.null(names(cpsi_x)) && isTRUE(cpsi_x[["available"]])) cpsi_mats <- cpsi_mats + 1L
  }
  cat(sprintf("[SKIPPED] correlation_matrix_wellformed: tier %s releases no correlation matrices (%d matrices declared)\n",
              cpsi_tier_label, cpsi_mats))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if (is.null(cpsi_relationships)) {
  cat("[NOT VERIFIED] correlation_matrix_wellformed: tier 3 but the report carries no relationships object\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  cpsi_bad <- character(0)
  cpsi_absent <- character(0)
  cpsi_checked <- 0L
  cpsi_max_asym <- 0
  cpsi_dim <- 0L
  for (cpsi_name in c("pearson", "spearman")) {
    cpsi_blk <- cpsi_relationships[[cpsi_name]]
    if (!(is.list(cpsi_blk) && !is.null(names(cpsi_blk)))) {
      cpsi_absent <- c(cpsi_absent, sprintf("the '%s' block is absent at tier 3", cpsi_name))
      next
    }
    if (!isTRUE(cpsi_blk[["available"]])) {
      cpsi_reason <- cpsi_blk[["reason"]]
      if (!(is.character(cpsi_reason) && length(cpsi_reason) == 1 && !all(utf8ToInt(cpsi_reason) %in% cpsi_ws))) {
        cpsi_bad <- c(cpsi_bad, sprintf("the '%s' block is unavailable with no recorded reason", cpsi_name))
      }
      next
    }
    cpsi_rows <- cpsi_blk[["matrix"]]
    if (!(is.list(cpsi_rows) && is.null(names(cpsi_rows))) || length(cpsi_rows) == 0) {
      cpsi_absent <- c(cpsi_absent, sprintf("the '%s' block is available but carries no matrix", cpsi_name))
      next
    }
    cpsi_n <- length(cpsi_rows)
    cpsi_ok_shape <- all(vapply(cpsi_rows, function(r) is.list(r) && is.null(names(r)) && length(r) == cpsi_n, logical(1)))
    if (!cpsi_ok_shape) {
      cpsi_bad <- c(cpsi_bad, sprintf("the '%s' matrix is not square", cpsi_name))
      next
    }
    cpsi_m <- matrix(NA_real_, nrow = cpsi_n, ncol = cpsi_n)
    for (cpsi_i in seq_len(cpsi_n)) {
      for (cpsi_j in seq_len(cpsi_n)) {
        cpsi_v <- cpsi_rows[[cpsi_i]][[cpsi_j]]
        if (is.numeric(cpsi_v) && length(cpsi_v) == 1 && !is.na(cpsi_v) && abs(cpsi_v) < cpsi_max_exact) cpsi_m[cpsi_i, cpsi_j] <- cpsi_v
      }
    }
    if (any(is.na(cpsi_m))) {
      cpsi_bad <- c(cpsi_bad, sprintf("the '%s' matrix carries a non-finite entry", cpsi_name))
      next
    }
    cpsi_asym <- max(abs(cpsi_m - t(cpsi_m)))
    if (cpsi_asym > 1e-09) {
      cpsi_bad <- c(cpsi_bad, sprintf("the '%s' matrix is not symmetric within 1e-09", cpsi_name))
    } else if (max(abs(diag(cpsi_m) - 1)) > 1e-09) {
      cpsi_bad <- c(cpsi_bad, sprintf("the '%s' matrix does not have a unit diagonal", cpsi_name))
    } else if (max(abs(cpsi_m)) > 1) {
      cpsi_bad <- c(cpsi_bad, sprintf("the '%s' matrix carries an entry outside [-1, 1]", cpsi_name))
    } else {
      cpsi_checked <- cpsi_checked + 1L
      cpsi_dim <- cpsi_n
      cpsi_max_asym <- max(cpsi_max_asym, cpsi_asym)
    }
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] correlation_matrix_wellformed: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else if (length(cpsi_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] correlation_matrix_wellformed: %s%s\n", cpsi_absent[1],
                if (length(cpsi_absent) > 1) sprintf(" (+%d more)", length(cpsi_absent) - 1) else ""))
    cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
  } else if (cpsi_checked == 0) {
    cat("[PASS] correlation_matrix_wellformed: 0 available matrices at tier 3, every block unavailable with a recorded reason\n")
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  } else {
    cat(sprintf("[PASS] correlation_matrix_wellformed: %d matrices, %dx%d, max asymmetry %.2e, unit diagonal, entries in [-1, 1]\n",
                cpsi_checked, cpsi_dim, cpsi_dim, cpsi_max_asym))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: no released count lies below the suppression threshold (NON-DECLARABLE)
# The gate is never the report's word alone (same contract as the Python block): a
# report declaring less than the approved expected_threshold is a [FAIL], and visible
# counts are gated at max(declared, approved). Thresholds are allowed facts.
cpsi_exp_ok <- is.numeric(expected_threshold) && length(expected_threshold) == 1 &&
  !is.na(expected_threshold) && abs(expected_threshold) < cpsi_max_exact &&
  expected_threshold == floor(expected_threshold) && expected_threshold >= 1
cpsi_threshold_ok <- is.numeric(cpsi_threshold) && length(cpsi_threshold) == 1 &&
  !is.na(cpsi_threshold) && abs(cpsi_threshold) < cpsi_max_exact &&
  cpsi_threshold == floor(cpsi_threshold) && cpsi_threshold >= 1
if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] no_released_count_below_threshold: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_columns)) {
  cat("[NOT VERIFIED] no_released_count_below_threshold: the report carries no columns array — the sweep has nothing to enumerate\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!cpsi_exp_ok) {
  cat("[NOT VERIFIED] no_released_count_below_threshold: expected_threshold not configured\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!cpsi_tier_ok) {
  # INTENT: the approved tier is the other PSU-DS1 approval this check enforces.
  cat("[NOT VERIFIED] no_released_count_below_threshold: tier not configured — the approved release scope is unknown\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (!cpsi_threshold_ok) {
  cat("[NOT VERIFIED] no_released_count_below_threshold: settings.suppression_threshold is absent or not a positive integer — the sweep has no gate to test against\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (cpsi_threshold < expected_threshold) {
  cat(sprintf("[FAIL] no_released_count_below_threshold: report declares threshold %s, below the approved threshold %s\n",
              format(cpsi_threshold, scientific = FALSE), format(expected_threshold, scientific = FALSE)))
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else if (!cpsi_rep_tier_ok) {
  cat("[FAIL] no_released_count_below_threshold: settings.tier is absent or not a whole number 1-3 — the report's release scope is unstated\n")
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else if (cpsi_rep_tier > tier) {
  # REASONING: blocks profiled above the approved tier were released without approval.
  cat(sprintf("[FAIL] no_released_count_below_threshold: report declares tier %d, above the approved tier %s\n",
              as.integer(cpsi_rep_tier), cpsi_tier_label))
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else if ((tier < 3 || cpsi_rep_tier < 3) && cpsi_rel_content) {
  cat(sprintf("[FAIL] no_released_count_below_threshold: the report releases a relationships block below tier 3 (approved tier %s, declared tier %d)\n",
              cpsi_tier_label, as.integer(cpsi_rep_tier)))
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else {
  cpsi_gate <- max(cpsi_threshold, expected_threshold)
  cpsi_declared_cat <- length(cpsi_cat_cols)
  cpsi_declared_ct <- 0L
  for (cpsi_ct in cpsi_crosstabs) {
    if (is.list(cpsi_ct) && !is.null(names(cpsi_ct)) && isTRUE(cpsi_ct[["available"]])) cpsi_declared_ct <- cpsi_declared_ct + 1L
  }
  cpsi_declared <- cpsi_declared_cat + cpsi_declared_ct
  cpsi_scanned <- 0L
  cpsi_cells <- 0L
  cpsi_breach <- character(0)
  for (cpsi_col in cpsi_cat_cols) {
    cpsi_name <- if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    cpsi_blk <- cpsi_col[["categorical"]]
    if (!(is.list(cpsi_blk) && !is.null(names(cpsi_blk))) ||
        !(is.list(cpsi_blk[["levels"]]) && is.null(names(cpsi_blk[["levels"]])))) next
    cpsi_scanned <- cpsi_scanned + 1L
    cpsi_blk_breaches <- length(cpsi_breach)
    cpsi_levels <- cpsi_blk[["levels"]]
    for (cpsi_i in seq_along(cpsi_levels)) {
      cpsi_lv <- cpsi_levels[[cpsi_i]]
      if (!is.list(cpsi_lv) || !("count" %in% names(cpsi_lv))) {
        cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' level index %d carries no count to gate", cpsi_name, cpsi_i - 1L))
        next
      }
      cpsi_v <- cpsi_lv[["count"]]
      cpsi_cells <- cpsi_cells + 1L
      if (!(is.numeric(cpsi_v) && length(cpsi_v) == 1 && !is.na(cpsi_v) && abs(cpsi_v) < cpsi_max_exact &&
            cpsi_v == floor(cpsi_v))) {
        cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' level index %d carries a non-integer count", cpsi_name, cpsi_i - 1L))
      } else if (cpsi_v < cpsi_gate) {
        # INTENT: 0 and negatives breach too (same rule as the Python block).
        cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' level index %d carries a visible count below the gate", cpsi_name, cpsi_i - 1L))
      }
    }
    # INTENT: Differencing residuals — same rule, order and wording as the Python block:
    # n == nonmissing_n; n >= gate => the levels sum to n; n < gate => no level released.
    cpsi_cn <- cpsi_blk[["n"]]
    cpsi_nm <- cpsi_col[["nonmissing_n"]]
    if (!all(vapply(list(cpsi_cn, cpsi_nm), function(x) is.numeric(x) && length(x) == 1 && !is.na(x) &&
                    abs(x) < cpsi_max_exact && x == floor(x), logical(1)))) {
      cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' carries no whole-number n and nonmissing_n to reconcile its levels against", cpsi_name))
    } else if (cpsi_cn != cpsi_nm) {
      cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' n does not equal its column's nonmissing_n", cpsi_name))
    } else if (cpsi_cn < cpsi_gate && length(cpsi_levels) > 0) {
      cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' releases levels although its n is below the gate", cpsi_name))
    } else if (cpsi_cn >= cpsi_gate && length(cpsi_breach) == cpsi_blk_breaches &&
               sum(vapply(cpsi_levels, function(lv) lv[["count"]], numeric(1))) != cpsi_cn) {
      cpsi_breach <- c(cpsi_breach, sprintf("categorical block '%s' level counts do not sum to its n", cpsi_name))
    }
  }
  for (cpsi_e in seq_along(cpsi_crosstabs)) {
    cpsi_ct <- cpsi_crosstabs[[cpsi_e]]
    if (!(is.list(cpsi_ct) && !is.null(names(cpsi_ct))) || !isTRUE(cpsi_ct[["available"]])) next
    if (!(is.list(cpsi_ct[["cells"]]) && is.null(names(cpsi_ct[["cells"]])))) next
    cpsi_scanned <- cpsi_scanned + 1L
    # INTENT: a pair is printed only when it names declared columns (schema facts);
    # anything else is referred to by its 0-based position, never quoted.
    cpsi_pair <- cpsi_ct[["pair"]]
    cpsi_pair <- if (is.list(cpsi_pair) && is.null(names(cpsi_pair)) && length(cpsi_pair) > 0 &&
                     all(vapply(cpsi_pair, function(p) is.character(p) && length(p) == 1 && p %in% cpsi_col_names, logical(1)))) {
      paste(cpsi_esc_to[match(unlist(cpsi_pair), cpsi_esc_from)], collapse = " x ")
    } else {
      sprintf("index %d", cpsi_e - 1L)
    }
    cpsi_grid <- cpsi_ct[["cells"]]
    for (cpsi_i in seq_along(cpsi_grid)) {
      cpsi_v <- cpsi_grid[[cpsi_i]]
      if (is.null(cpsi_v)) next
      cpsi_cells <- cpsi_cells + 1L
      if (!(is.numeric(cpsi_v) && length(cpsi_v) == 1 && !is.na(cpsi_v) && abs(cpsi_v) < cpsi_max_exact &&
            cpsi_v == floor(cpsi_v))) {
        cpsi_breach <- c(cpsi_breach, sprintf("cross-tab block %s cell index %d carries a non-integer count", cpsi_pair, cpsi_i - 1L))
      } else if (cpsi_v < 0 || (cpsi_v > 0 && cpsi_v < cpsi_gate)) {
        # A visible 0 is a legitimate structural zero; a negative cell breaches.
        cpsi_breach <- c(cpsi_breach, sprintf("cross-tab block %s cell index %d carries a visible count below the gate", cpsi_pair, cpsi_i - 1L))
      }
    }
  }
  # INTENT: Support gate — same bands, order and wording as the Python block
  # (profiling-script-spec.md § Numeric shapes, § Categorical and string structure,
  # § Relationships). k is the gate and f = max(k, 10) the full-summary cutoff,
  # recomputed so the report cannot lower it: numeric all_missing (n = 0 and
  # nonmissing_n = 0), withheld (n < k), constant (n >= k), small_n (k <= n < f), full
  # summary (n >= f), and n never above nonmissing_n; string_structure n equals
  # nonmissing_n, withheld below k and full at or above it; an available named entry
  # needs n >= f and complement groups of 0 or >= k, and an available Cramer's V n >= k.
  # A FAIL names the column or entry and the shape, never n.
  # ASSUMES: a numeric shape is its first marker that is literally TRUE in the spec's
  # branch order; with none, a block carrying mean / sd / percentiles / value is a full
  # summary, and one carrying none of them releases no value.
  cpsi_cutoff <- max(cpsi_gate, 10)
  for (cpsi_col in cpsi_columns) {
    cpsi_name <- if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    cpsi_nm <- cpsi_col[["nonmissing_n"]]
    cpsi_blk <- cpsi_col[["numeric"]]
    if (is.list(cpsi_blk) && !is.null(names(cpsi_blk))) {
      cpsi_bn <- cpsi_blk[["n"]]
      cpsi_shape <- NA_character_
      for (cpsi_m in c("all_missing", "withheld", "constant", "small_n")) {
        if (isTRUE(cpsi_blk[[cpsi_m]])) {
          cpsi_shape <- cpsi_m
          break
        }
      }
      if (is.na(cpsi_shape) && any(c("mean", "sd", "percentiles", "value") %in% names(cpsi_blk))) cpsi_shape <- "full"
      if (!all(vapply(list(cpsi_bn, cpsi_nm), function(x) is.numeric(x) && length(x) == 1 && !is.na(x) &&
                      x >= 0 && x < cpsi_max_exact && x == floor(x), logical(1)))) {
        cpsi_breach <- c(cpsi_breach, sprintf("numeric block '%s' carries no non-negative whole-number n and nonmissing_n to gate its shape on", cpsi_name))
      } else if (cpsi_bn > cpsi_nm) {
        cpsi_breach <- c(cpsi_breach, sprintf("numeric block '%s' n exceeds its column's nonmissing_n", cpsi_name))
      } else if (!is.na(cpsi_shape) && !(
          (cpsi_shape == "all_missing" && cpsi_bn == 0 && cpsi_nm == 0) ||
          (cpsi_shape == "withheld" && cpsi_bn < cpsi_gate) ||
          (cpsi_shape == "constant" && cpsi_bn >= cpsi_gate) ||
          (cpsi_shape == "small_n" && cpsi_bn >= cpsi_gate && cpsi_bn < cpsi_cutoff) ||
          (cpsi_shape == "full" && cpsi_bn >= cpsi_cutoff))) {
        cpsi_breach <- c(cpsi_breach, sprintf("numeric block '%s' shape '%s' does not match the support band of its n", cpsi_name, cpsi_shape))
      }
    }
    cpsi_blk <- cpsi_col[["string_structure"]]
    if (is.list(cpsi_blk) && !is.null(names(cpsi_blk))) {
      cpsi_bn <- cpsi_blk[["n"]]
      cpsi_shape <- if (isTRUE(cpsi_blk[["withheld"]])) "withheld" else "full"
      if (!all(vapply(list(cpsi_bn, cpsi_nm), function(x) is.numeric(x) && length(x) == 1 && !is.na(x) &&
                      x >= 0 && x < cpsi_max_exact && x == floor(x), logical(1)))) {
        cpsi_breach <- c(cpsi_breach, sprintf("string_structure block '%s' carries no non-negative whole-number n and nonmissing_n to gate its shape on", cpsi_name))
      } else if (cpsi_bn != cpsi_nm) {
        cpsi_breach <- c(cpsi_breach, sprintf("string_structure block '%s' n does not equal its column's nonmissing_n", cpsi_name))
      } else if ((cpsi_shape == "withheld") != (cpsi_bn < cpsi_gate)) {
        cpsi_breach <- c(cpsi_breach, sprintf("string_structure block '%s' shape '%s' does not match the support band of its n", cpsi_name, cpsi_shape))
      }
    }
  }
  for (cpsi_kind in c("named", "cramers_v")) {
    cpsi_floor <- if (cpsi_kind == "named") cpsi_cutoff else cpsi_gate
    cpsi_entries <- if (is.list(cpsi_relationships) && !is.null(names(cpsi_relationships))) cpsi_relationships[[cpsi_kind]] else NULL
    if (!(is.list(cpsi_entries) && is.null(names(cpsi_entries)))) cpsi_entries <- list()
    for (cpsi_idx in seq_along(cpsi_entries)) {
      cpsi_ent <- cpsi_entries[[cpsi_idx]]
      if (!(is.list(cpsi_ent) && !is.null(names(cpsi_ent))) || !isTRUE(cpsi_ent[["available"]])) next
      cpsi_ends <- if (cpsi_kind == "named") list(cpsi_ent[["outcome"]], cpsi_ent[["predictor"]]) else cpsi_ent[["pair"]]
      cpsi_label <- if (is.list(cpsi_ends) && is.null(names(cpsi_ends)) && length(cpsi_ends) == 2 &&
                        all(vapply(cpsi_ends, function(p) is.character(p) && length(p) == 1 && p %in% cpsi_col_names, logical(1)))) {
        paste(cpsi_esc_to[match(unlist(cpsi_ends), cpsi_esc_from)], collapse = if (cpsi_kind == "named") " ~ " else " x ")
      } else {
        sprintf("index %d", cpsi_idx - 1L)
      }
      cpsi_bn <- cpsi_ent[["n"]]
      if (!(is.numeric(cpsi_bn) && length(cpsi_bn) == 1 && !is.na(cpsi_bn) && cpsi_bn >= 0 &&
            cpsi_bn < cpsi_max_exact && cpsi_bn == floor(cpsi_bn))) {
        cpsi_breach <- c(cpsi_breach, sprintf("%s entry %s carries no non-negative whole-number n to gate its availability on", cpsi_kind, cpsi_label))
      } else if (cpsi_bn < cpsi_floor) {
        cpsi_breach <- c(cpsi_breach, sprintf("%s entry %s is available although its n is below the %s", cpsi_kind, cpsi_label,
                                              if (cpsi_kind == "named") "full-summary cutoff" else "gate"))
      } else if (cpsi_kind == "named") {
        # INTENT: Complement-group gate — same rule, order and wording as the Python block:
        # for each end, g = (end column's numeric-block n) - (entry n) must be 0 or >= k;
        # a negative g breaches too; outcome first, one finding per entry; the first column
        # record carrying the name is the end column.
        for (cpsi_end_role in c("outcome", "predictor")) {
          cpsi_end <- cpsi_ent[[cpsi_end_role]]
          cpsi_end_n <- NULL
          if (is.character(cpsi_end) && length(cpsi_end) == 1) {
            for (cpsi_ecand in cpsi_columns) {
              if (is.character(cpsi_ecand[["name"]]) && length(cpsi_ecand[["name"]]) == 1 && cpsi_ecand[["name"]] == cpsi_end) {
                cpsi_end_blk <- cpsi_ecand[["numeric"]]
                if (is.list(cpsi_end_blk) && !is.null(names(cpsi_end_blk))) cpsi_end_n <- cpsi_end_blk[["n"]]
                break
              }
            }
          }
          if (!(is.numeric(cpsi_end_n) && length(cpsi_end_n) == 1 && !is.na(cpsi_end_n) && cpsi_end_n >= 0 &&
                cpsi_end_n < cpsi_max_exact && cpsi_end_n == floor(cpsi_end_n))) {
            cpsi_breach <- c(cpsi_breach, sprintf("named entry %s has no whole-number numeric n for its %s to gate the complement group on",
                                                  cpsi_label, cpsi_end_role))
            break
          }
          cpsi_g <- cpsi_end_n - cpsi_bn
          if (cpsi_g < 0 || (cpsi_g > 0 && cpsi_g < cpsi_gate)) {
            cpsi_breach <- c(cpsi_breach, sprintf("named entry %s is available although the complement group of its %s is below the gate",
                                                  cpsi_label, cpsi_end_role))
            break
          }
        }
      }
    }
  }
  if (length(cpsi_breach) > 0) {
    cat(sprintf("[FAIL] no_released_count_below_threshold: %s%s\n", cpsi_breach[1],
                if (length(cpsi_breach) > 1) sprintf(" (+%d more)", length(cpsi_breach) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else if (cpsi_scanned != cpsi_declared) {
    cat(sprintf("[FAIL] no_released_count_below_threshold: scanned %d of %d declared blocks — the sweep is incomplete\n",
                cpsi_scanned, cpsi_declared))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else {
    cat(sprintf("[PASS] no_released_count_below_threshold: %d of %d declared blocks scanned (%d categorical + %d cross-tab), %d visible cells examined, all >= effective threshold %s (declared %s, approved %s)\n",
                cpsi_scanned, cpsi_declared, cpsi_declared_cat, cpsi_declared_ct, cpsi_cells,
                format(cpsi_gate, scientific = FALSE), format(cpsi_threshold, scientific = FALSE),
                format(expected_threshold, scientific = FALSE)))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: the embedded validation record is complete and internally honest
cpsi_required_checks <- c("column_shapes_and_support", "percentiles_monotone",
                          "category_counts_le_rowcount", "missing_rate_in_unit_interval",
                          "no_subthreshold_cells_emitted", "correlation_matrix_symmetric",
                          "relationship_support_and_shape")
cpsi_legal_status <- c("PASS", "FAIL", "NOT_APPLICABLE", "NOT_VERIFIED")
cpsi_val <- NULL
if (!is.null(cpsi_report) && is.list(cpsi_report[["validation"]]) && !is.null(names(cpsi_report[["validation"]]))) {
  cpsi_val <- cpsi_report[["validation"]]
}
if ("embedded_validation_complete" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] embedded_validation_complete: %s\n", not_applicable[["embedded_validation_complete"]]))
  cps_intake["skipped"] <- cps_intake["skipped"] + 1L
} else if ("embedded_validation_complete" %in% cpsi_empty_reason) {
  cat("[NOT VERIFIED] embedded_validation_complete: declared not_applicable with an empty reason\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] embedded_validation_complete: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_val) || !(is.list(cpsi_val[["checks"]]) && is.null(names(cpsi_val[["checks"]])))) {
  cat("[NOT VERIFIED] embedded_validation_complete: the report carries no validation object with a checks array\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  # INTENT: every entry, name, and status is type-tested before use (as.character()
  # on a list name used to yield several names, and on a null name none at all);
  # names outside the required set are counted, never quoted. Same order of
  # findings as the Python block: set, duplicates, per-entry, all_passed.
  cpsi_recs <- cpsi_val[["checks"]]
  cpsi_names <- character(0)
  cpsi_rec_bad <- character(0)
  for (cpsi_i in seq_along(cpsi_recs)) {
    cpsi_rec <- cpsi_recs[[cpsi_i]]
    if (!(is.list(cpsi_rec) && !is.null(names(cpsi_rec)))) {
      cpsi_rec_bad <- c(cpsi_rec_bad, sprintf("checks entry %d is not a JSON object", cpsi_i - 1L))
      next
    }
    cpsi_nm <- cpsi_rec[["name"]]
    if (!(is.character(cpsi_nm) && length(cpsi_nm) == 1)) {
      cpsi_rec_bad <- c(cpsi_rec_bad, sprintf("checks entry %d has a name that is not a string", cpsi_i - 1L))
      cpsi_label <- sprintf("entry %d", cpsi_i - 1L)
    } else {
      cpsi_names <- c(cpsi_names, cpsi_nm)
      cpsi_label <- if (cpsi_nm %in% cpsi_required_checks) sprintf("'%s'", cpsi_nm) else sprintf("entry %d", cpsi_i - 1L)
    }
    cpsi_st <- cpsi_rec[["status"]]
    if (!(is.character(cpsi_st) && length(cpsi_st) == 1 && cpsi_st %in% cpsi_legal_status)) {
      cpsi_rec_bad <- c(cpsi_rec_bad, sprintf("check %s has a status outside the wire enum", cpsi_label))
    } else if (cpsi_st %in% c("FAIL", "NOT_VERIFIED")) {
      cpsi_rec_bad <- c(cpsi_rec_bad, sprintf("check %s reports %s", cpsi_label, cpsi_st))
    }
    cpsi_rs <- cpsi_rec[["reason"]]
    if (!(is.character(cpsi_rs) && length(cpsi_rs) == 1 && !all(utf8ToInt(cpsi_rs) %in% cpsi_ws))) {
      cpsi_rec_bad <- c(cpsi_rec_bad, sprintf("check %s carries an empty reason", cpsi_label))
    }
  }
  cpsi_bad <- character(0)
  cpsi_missing_checks <- sort(setdiff(cpsi_required_checks, cpsi_names), method = "radix")
  cpsi_unrecognized <- sum(!(cpsi_names %in% cpsi_required_checks))
  if (length(cpsi_missing_checks) > 0 || cpsi_unrecognized > 0) {
    cpsi_bad <- c(cpsi_bad, sprintf("check set is not the seven required names (missing [%s], %d unrecognized)",
                                    paste(cpsi_missing_checks, collapse = ", "), cpsi_unrecognized))
  }
  if (length(cpsi_names) != length(unique(cpsi_names))) {
    cpsi_bad <- c(cpsi_bad, "the checks array carries duplicate names")
  }
  cpsi_bad <- c(cpsi_bad, cpsi_rec_bad)
  if (!isTRUE(cpsi_val[["all_passed"]])) {
    cpsi_bad <- c(cpsi_bad, "all_passed is not true")
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] embedded_validation_complete: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else {
    cat(sprintf("[PASS] embedded_validation_complete: %d of %d required checks present, every status in the wire enum with a non-empty reason, all_passed true\n",
                length(cpsi_names), length(cpsi_required_checks)))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: no raw-value-shaped fields anywhere in the report (NON-DECLARABLE)
# REASONING: Rule (3), parallel to the Python block — a *string*-valued key with a
# value-shaped name is the one-row version of a value dump, which the list-only
# rules miss. Rule (4), also parallel: every non-identifier column record is held to
# the per-role allow-list of schema keys, at the record and inside its role block.
# Name tests are case-insensitive; only key names, column names and JSON paths print.
cpsi_value_keys <- c("values", "sample", "rows", "head", "examples")
cpsi_scalar_value_keys <- c("example", "examples", "sample", "first_value", "last_value",
                            "mode_value", "min_value", "max_value", "values", "head", "tail")
cpsi_col_allowed <- c("name", "dtype", "role", "missing_rate", "nonmissing_n",
                      "n_distinct", "uniqueness_ratio", "is_identifier")
cpsi_role_block <- c(numeric = "numeric", categorical = "categorical", string = "string_structure")
# ASSUMES: a numeric block's shape is named by its first present marker, in the spec's
# branch order; a marker that is not literally TRUE is not that shape.
cpsi_num_shapes <- list(all_missing = c("n", "all_missing"),
                        withheld = c("n", "withheld", "reason"),
                        constant = c("n", "constant", "value", "mean", "sd"),
                        small_n = c("n", "small_n", "percentiles"))
cpsi_num_full <- c("n", "mean", "sd", "percentiles")
cpsi_cat_allowed <- c("n", "n_levels_binned", "levels")
cpsi_level_allowed <- c("value", "count")
cpsi_ss_allowed_full <- c("n", "length_min", "length_mean", "length_max", "pattern_flags")
cpsi_ss_allowed_withheld <- c("n", "withheld", "reason")
cpsi_flag_allowed <- c("email", "phone", "date", "id", "free_text")
# INTENT: Same typing rule as the Python block — an allow-listed key the schema types
# as a number or boolean must hold a single number / logical or JSON null (NULL); a
# string, array (unnamed list) or object (named list) there is a value wearing a
# structural key's name. Shape markers keep their literal-TRUE test instead.
cpsi_number_keys <- c("missing_rate", "nonmissing_n", "n_distinct", "uniqueness_ratio", "is_identifier",
                      "n", "mean", "sd", "value", "n_levels_binned", "length_min", "length_mean", "length_max")
# INTENT: Same vocabularies as the Python block — `dtype`, `role`, and a withheld
# block's `reason` are held to the spec's closed sets.
cpsi_col_vocab <- list(dtype = c("integer", "double", "string"),
                       role = c("numeric", "categorical", "identifier", "string"))
cpsi_block_reason_vocab <- list(numeric = c("no_finite_values", "insufficient_support"),
                                string_structure = c("all_missing", "insufficient_support"))
# INTENT: Rule (5), same specs, kinds and vocabularies as the Python block (see its
# comments for the spec sections each list comes from).
cpsi_r5_specs <- list(
  dataset = c(row_count = "number", column_count = "number"),
  settings = c(tier = "number", suppression_threshold = "number", max_categorical_levels = "number",
               relationship_spec = "pairs", support_unit = "vocab:support_unit", full_summary_cutoff = "number"),
  generator = c(language = "vocab:language", template = "vocab:template", template_version = "vocab:template_version"),
  relationships = c(pearson = "record:correlation", spearman = "record:correlation", cramers_v = "entries:cramers_v",
                    named = "entries:named", crosstabs = "owned"),
  correlation = c(available = "flag", columns = "names", pair_n = "matrix", matrix = "matrix",
                  reason = "vocab:correlation_reason"),
  cramers_v = c(pair = "pair", n = "number", available = "flag", v = "number", reason = "vocab:cramers_v_reason"),
  named = c(outcome = "name", predictor = "name", n = "number", available = "flag", pearson = "number",
            spearman = "number", ols = "record:ols", reason = "vocab:named_reason"),
  ols = c(intercept = "number", slope = "number", r_squared = "number"),
  validation = c(checks = "entries:check", all_passed = "flag"),
  check = c(name = "vocab:check_name", status = "vocab:check_status", applicable = "flag", reason = "check_reason")
)
cpsi_r5_vocab <- list(
  support_unit = "record",
  language = c("Python", "R"),
  template = c("profile_data_template.py", "profile_data_template.R"),
  template_version = "2.0",
  correlation_reason = c("fewer_than_two_eligible_columns", "insufficient_pair_support",
                         "zero_pair_variance", "nonfinite_correlation"),
  cramers_v_reason = c("insufficient_support", "degenerate_table"),
  named_reason = c("insufficient_support", "ineligible_marginal", "small_complement_group", "zero_pair_variance"),
  check_name = cpsi_required_checks,
  check_status = cpsi_legal_status
)
# INTENT: `validation.checks[].reason` forms — same rule as the Python block. Patterns
# are anchored with ^(?: … )\z under perl = TRUE so they match exactly what Python's
# re.fullmatch matches (a PCRE `$` would also accept a trailing newline).
cpsi_na_reason_forms <- list(
  percentiles_monotone = c("report declares 0 numeric columns at tier [123]",
                           "0 of [1-9][0-9]* numeric columns release a percentile grid"),
  category_counts_le_rowcount = "report declares 0 categorical columns at tier [123]",
  missing_rate_in_unit_interval = "tier 1 releases name and dtype only",
  correlation_matrix_symmetric = c("tier [12] releases no correlations",
                                   "0 of 2 correlation blocks released \\((fewer_than_two_eligible_columns|insufficient_pair_support|zero_pair_variance|nonfinite_correlation|no reason stated)\\)"),
  relationship_support_and_shape = "tier [12] releases no relationships"
)
if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] no_raw_value_shaped_fields: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  cpsi_cap <- length(cpsi_pctl_order)
  if (!is.null(cpsi_columns)) cpsi_cap <- max(cpsi_cap, length(cpsi_columns))
  for (cpsi_col in cpsi_cat_cols) {
    cpsi_blk <- cpsi_col[["categorical"]]
    if (is.list(cpsi_blk) && !is.null(names(cpsi_blk)) && is.list(cpsi_blk[["levels"]]) &&
        is.null(names(cpsi_blk[["levels"]]))) cpsi_cap <- max(cpsi_cap, length(cpsi_blk[["levels"]]))
  }
  for (cpsi_ct in cpsi_crosstabs) {
    if (is.list(cpsi_ct) && !is.null(names(cpsi_ct)) && is.list(cpsi_ct[["cells"]]) &&
        is.null(names(cpsi_ct[["cells"]]))) cpsi_cap <- max(cpsi_cap, length(cpsi_ct[["cells"]]))
  }
  # INTENT: the walk's stack (nodes and their JSON paths) is preallocated and grown by
  # doubling, with an explicit top index. Push and pop order are the Python block's
  # (last pushed, first walked), so every path and finding is unchanged.
  # REASONING: appending with c() or at length + 1 and dropping the last element copy
  # the whole stack on every step — quadratic in the node count, so a 300 x 300
  # cross-tab (90,000 cells) took about a minute where it now takes about a second.
  cpsi_stack_size <- 1024L
  cpsi_nodes_stack <- vector("list", cpsi_stack_size)
  cpsi_paths <- character(cpsi_stack_size)
  cpsi_nodes_stack[1L] <- list(cpsi_report)
  cpsi_paths[1L] <- "report"
  cpsi_top <- 1L
  cpsi_nodes <- 0L
  cpsi_longest <- 0L
  cpsi_hits <- character(0)
  while (cpsi_top > 0L) {
    cpsi_node <- cpsi_nodes_stack[[cpsi_top]]
    cpsi_path <- cpsi_paths[cpsi_top]
    cpsi_nodes_stack[cpsi_top] <- list(NULL)
    cpsi_top <- cpsi_top - 1L
    cpsi_nodes <- cpsi_nodes + 1L
    if (!is.list(cpsi_node)) next
    if (cpsi_top + length(cpsi_node) > cpsi_stack_size) {
      cpsi_stack_size <- max(2L * cpsi_stack_size, cpsi_top + length(cpsi_node))
      length(cpsi_nodes_stack) <- cpsi_stack_size
      length(cpsi_paths) <- cpsi_stack_size
    }
    cpsi_nms <- names(cpsi_node)
    if (is.null(cpsi_nms)) {
      # An unnamed list is a JSON array. A scalar array is the value-dump shape.
      # ASSUMES: a JSON null (NULL here) is a scalar, as in the Python block — else
      # one null would exempt an over-long value list from rule (2).
      cpsi_is_scalar <- all(vapply(cpsi_node, function(x) is.null(x) || (!is.list(x) && length(x) == 1), logical(1)))
      if (length(cpsi_node) > 0 && cpsi_is_scalar) {
        cpsi_longest <- max(cpsi_longest, length(cpsi_node))
        if (length(cpsi_node) > cpsi_cap) {
          cpsi_hits <- c(cpsi_hits, sprintf("%s is a %d-element scalar list, longer than the declared cap %d",
                                            cpsi_path, length(cpsi_node), cpsi_cap))
        }
      }
      # INTENT: push with `[<- list(x)`, never `[[<- x`: assigning a NULL through
      # `[[<-` deletes the slot instead of storing a JSON null, which would
      # desynchronise the node stack from cpsi_paths and print a FAIL at the wrong
      # JSON path.
      for (cpsi_i in seq_along(cpsi_node)) {
        cpsi_top <- cpsi_top + 1L
        cpsi_nodes_stack[cpsi_top] <- list(cpsi_node[[cpsi_i]])
        cpsi_paths[cpsi_top] <- sprintf("%s[%d]", cpsi_path, cpsi_i - 1L)
      }
    } else {
      for (cpsi_i in seq_along(cpsi_node)) {
        cpsi_k <- cpsi_nms[cpsi_i]
        cpsi_ek <- cpsi_esc_to[match(cpsi_k, cpsi_esc_from)]
        cpsi_v <- cpsi_node[[cpsi_i]]
        if (chartr(cpsi_upper_ascii, cpsi_lower_ascii, cpsi_k) %in% cpsi_value_keys && is.list(cpsi_v) && is.null(names(cpsi_v))) {
          cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is a list under a value-shaped key name", cpsi_path, cpsi_ek))
        }
        if (is.character(cpsi_v) && length(cpsi_v) == 1 &&
            chartr(cpsi_upper_ascii, cpsi_lower_ascii, cpsi_k) %in% cpsi_scalar_value_keys) {
          cpsi_hits <- c(cpsi_hits, sprintf("value-shaped key '%s' at %s.%s", cpsi_ek, cpsi_path, cpsi_ek))
        }
        cpsi_top <- cpsi_top + 1L
        cpsi_nodes_stack[cpsi_top] <- list(cpsi_v)
        cpsi_paths[cpsi_top] <- sprintf("%s.%s", cpsi_path, cpsi_ek)
      }
    }
  }
  # Rule (4): the per-role column-record allow-list. Hits follow the walker's.
  cpsi_records <- 0L
  cpsi_raw <- if (is.null(cpsi_columns_raw)) list() else cpsi_columns_raw
  for (cpsi_i in seq_along(cpsi_raw)) {
    cpsi_col <- cpsi_raw[[cpsi_i]]
    if (!(is.list(cpsi_col) && !is.null(names(cpsi_col)))) {
      cpsi_hits <- c(cpsi_hits, sprintf("column index %d is not a JSON object", cpsi_i - 1L))
      next
    }
    cpsi_name_ok <- is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1
    if (!cpsi_name_ok) cpsi_hits <- c(cpsi_hits, sprintf("column index %d has a name that is not a string", cpsi_i - 1L))
    cpsi_name <- if (cpsi_name_ok) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    cpsi_role <- cpsi_col[["role"]]
    if (!(is.character(cpsi_role) && length(cpsi_role) == 1)) cpsi_role <- NA_character_
    if (isTRUE(cpsi_role == "identifier") || isTRUE(cpsi_col[["is_identifier"]])) next
    cpsi_records <- cpsi_records + 1L
    cpsi_t1 <- cpsi_tier_ok && tier == 1
    cpsi_bkey <- if (!cpsi_t1 && !is.na(cpsi_role) && cpsi_role %in% names(cpsi_role_block)) cpsi_role_block[[cpsi_role]] else NA_character_
    cpsi_allowed <- if (cpsi_t1) c("name", "dtype") else c(cpsi_col_allowed, if (is.na(cpsi_bkey)) character(0) else cpsi_bkey)
    for (cpsi_f in sort(names(cpsi_col), method = "radix")) {
      cpsi_fv <- cpsi_col[[cpsi_f]]
      if (!(cpsi_f %in% cpsi_allowed)) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
      } else if (cpsi_f %in% cpsi_number_keys && !(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a non-numeric '%s'", cpsi_name, cpsi_f))
      } else if (cpsi_f %in% names(cpsi_col_vocab) &&
                 !(is.character(cpsi_fv) && length(cpsi_fv) == 1 && cpsi_fv %in% cpsi_col_vocab[[cpsi_f]])) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a '%s' outside the spec vocabulary", cpsi_name, cpsi_f))
      }
    }
    # INTENT: A categorical column is a string column (same rule and wording as the
    # Python block): a vocabulary dtype other than "string" is not something either
    # profiler writes. The dtype itself is not echoed.
    cpsi_dt <- cpsi_col[["dtype"]]
    if (isTRUE(cpsi_bkey == "categorical") && is.character(cpsi_dt) && length(cpsi_dt) == 1 &&
        cpsi_dt %in% cpsi_col_vocab[["dtype"]] && cpsi_dt != "string") {
      cpsi_hits <- c(cpsi_hits, sprintf("column '%s' declares role 'categorical' with a dtype other than 'string'", cpsi_name))
    }
    cpsi_blk <- if (is.na(cpsi_bkey)) NULL else cpsi_col[[cpsi_bkey]]
    if (is.null(cpsi_blk)) next
    if (!(is.list(cpsi_blk) && !is.null(names(cpsi_blk)))) {
      cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a non-object '%s'", cpsi_name, cpsi_bkey))
      next
    }
    cpsi_sub <- NA_character_
    cpsi_sub_allowed <- character(0)
    if (cpsi_bkey == "numeric") {
      cpsi_blk_allowed <- cpsi_num_full
      for (cpsi_marker in names(cpsi_num_shapes)) {
        if (cpsi_marker %in% names(cpsi_blk)) {
          cpsi_blk_allowed <- cpsi_num_shapes[[cpsi_marker]]
          if (!isTRUE(cpsi_blk[[cpsi_marker]])) {
            cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_marker))
          }
          break
        }
      }
      cpsi_sub <- "percentiles"
      cpsi_sub_allowed <- if ("small_n" %in% cpsi_blk_allowed) c("p25", "p50", "p75") else cpsi_pctl_order
    } else if (cpsi_bkey == "categorical") {
      cpsi_blk_allowed <- cpsi_cat_allowed
    } else {
      cpsi_blk_allowed <- if ("withheld" %in% names(cpsi_blk)) cpsi_ss_allowed_withheld else cpsi_ss_allowed_full
      if ("withheld" %in% names(cpsi_blk) && !isTRUE(cpsi_blk[["withheld"]])) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries non-structural key 'withheld'", cpsi_name))
      }
      cpsi_sub <- "pattern_flags"
      cpsi_sub_allowed <- cpsi_flag_allowed
    }
    for (cpsi_f in sort(names(cpsi_blk), method = "radix")) {
      cpsi_fv <- cpsi_blk[[cpsi_f]]
      if (!(cpsi_f %in% cpsi_blk_allowed)) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
      } else if (cpsi_f %in% cpsi_number_keys && !(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a non-numeric '%s'", cpsi_name, cpsi_f))
      } else if (cpsi_f == "reason" &&
                 !(is.character(cpsi_fv) && length(cpsi_fv) == 1 &&
                   cpsi_bkey %in% names(cpsi_block_reason_vocab) && cpsi_fv %in% cpsi_block_reason_vocab[[cpsi_bkey]])) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a 'reason' outside the spec vocabulary", cpsi_name))
      }
    }
    if (!is.na(cpsi_sub) && cpsi_sub %in% cpsi_blk_allowed && !is.null(cpsi_blk[[cpsi_sub]])) {
      cpsi_x <- cpsi_blk[[cpsi_sub]]
      if (!(is.list(cpsi_x) && !is.null(names(cpsi_x)))) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a non-object '%s'", cpsi_name, cpsi_sub))
      } else {
        for (cpsi_f in sort(names(cpsi_x), method = "radix")) {
          cpsi_fv <- cpsi_x[[cpsi_f]]
          if (!(cpsi_f %in% cpsi_sub_allowed)) {
            cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
          } else if (!(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
            cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a non-numeric '%s'", cpsi_name, cpsi_f))
          }
        }
      }
    }
    if (cpsi_bkey == "categorical" && !is.null(cpsi_blk[["levels"]])) {
      cpsi_x <- cpsi_blk[["levels"]]
      if (!(is.list(cpsi_x) && is.null(names(cpsi_x)))) {
        cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries a non-array 'levels'", cpsi_name))
      } else {
        # INTENT: one released level per label — same rule, order and wording as the Python
        # block: a repeated string label names the later level index and the first one's.
        cpsi_lv_vals <- character(0)
        cpsi_lv_idx <- integer(0)
        for (cpsi_j in seq_along(cpsi_x)) {
          cpsi_lv <- cpsi_x[[cpsi_j]]
          if (!(is.list(cpsi_lv) && !is.null(names(cpsi_lv)))) {
            cpsi_hits <- c(cpsi_hits, sprintf("column '%s' level index %d is not a JSON object", cpsi_name, cpsi_j - 1L))
            next
          }
          for (cpsi_f in sort(names(cpsi_lv), method = "radix")) {
            if (!(cpsi_f %in% cpsi_level_allowed)) {
              cpsi_hits <- c(cpsi_hits, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
            } else if (cpsi_f == "value" && !(is.character(cpsi_lv[["value"]]) && length(cpsi_lv[["value"]]) == 1)) {
              # A level label is a string by schema (same rule as the Python block).
              cpsi_hits <- c(cpsi_hits, sprintf("column '%s' level index %d carries a non-string 'value'", cpsi_name, cpsi_j - 1L))
            }
          }
          cpsi_lvv <- cpsi_lv[["value"]]
          if (is.character(cpsi_lvv) && length(cpsi_lvv) == 1) {
            cpsi_seen <- match(cpsi_lvv, cpsi_lv_vals)
            if (!is.na(cpsi_seen)) {
              cpsi_hits <- c(cpsi_hits, sprintf("column '%s' level index %d repeats the 'value' of level index %d",
                                                cpsi_name, cpsi_j - 1L, cpsi_lv_idx[cpsi_seen]))
            } else {
              cpsi_lv_vals <- c(cpsi_lv_vals, cpsi_lvv)
              cpsi_lv_idx <- c(cpsi_lv_idx, cpsi_j - 1L)
            }
          }
        }
      }
    }
  }
  # Rule (5): the subtree records, breadth-first in the same fixed order as Python.
  # Fields are visited by position in C-locale name order, so an empty-string key
  # is reached without a `[[""]]` lookup.
  cpsi_queue <- list()
  cpsi_queue_path <- character(0)
  cpsi_queue_spec <- character(0)
  for (cpsi_k in c("dataset", "settings", "generator", "relationships", "validation")) {
    cpsi_x <- cpsi_report[[cpsi_k]]
    if (is.list(cpsi_x) && !is.null(names(cpsi_x))) {
      cpsi_queue[length(cpsi_queue) + 1L] <- list(cpsi_x)
      cpsi_queue_path <- c(cpsi_queue_path, cpsi_k)
      cpsi_queue_spec <- c(cpsi_queue_spec, cpsi_k)
    }
  }
  cpsi_qi <- 0L
  while (cpsi_qi < length(cpsi_queue)) {
    cpsi_qi <- cpsi_qi + 1L
    cpsi_rec <- cpsi_queue[[cpsi_qi]]
    cpsi_path <- cpsi_queue_path[cpsi_qi]
    cpsi_spec <- cpsi_r5_specs[[cpsi_queue_spec[cpsi_qi]]]
    cpsi_rec_names <- names(cpsi_rec)
    for (cpsi_j in order(cpsi_rec_names, method = "radix")) {
      cpsi_f <- cpsi_rec_names[cpsi_j]
      cpsi_v <- cpsi_rec[[cpsi_j]]
      cpsi_kind <- if (cpsi_f %in% names(cpsi_spec)) cpsi_spec[[cpsi_f]] else NA_character_
      if (is.na(cpsi_kind)) {
        cpsi_hits <- c(cpsi_hits, sprintf("%s carries non-structural key '%s'", cpsi_path, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
      } else if (cpsi_kind == "number") {
        if (!(is.null(cpsi_v) || ((is.numeric(cpsi_v) || is.logical(cpsi_v)) && length(cpsi_v) == 1))) {
          cpsi_hits <- c(cpsi_hits, sprintf("%s carries a non-numeric '%s'", cpsi_path, cpsi_f))
        }
      } else if (cpsi_kind == "flag") {
        if (!(is.logical(cpsi_v) && length(cpsi_v) == 1 && !is.na(cpsi_v))) {
          cpsi_hits <- c(cpsi_hits, sprintf("%s carries a non-boolean '%s'", cpsi_path, cpsi_f))
        }
      } else if (startsWith(cpsi_kind, "vocab:")) {
        if (!(is.character(cpsi_v) && length(cpsi_v) == 1 && cpsi_v %in% cpsi_r5_vocab[[substring(cpsi_kind, 7)]])) {
          cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is outside the spec vocabulary", cpsi_path, cpsi_f))
        }
      } else if (cpsi_kind == "check_reason") {
        cpsi_st <- cpsi_rec[["status"]]
        cpsi_nm <- cpsi_rec[["name"]]
        cpsi_st <- if (is.character(cpsi_st) && length(cpsi_st) == 1) cpsi_st else NA_character_
        cpsi_nm <- if (is.character(cpsi_nm) && length(cpsi_nm) == 1) cpsi_nm else NA_character_
        cpsi_is_str <- is.character(cpsi_v) && length(cpsi_v) == 1
        cpsi_ok <- if (identical(cpsi_st, "PASS")) {
          cpsi_is_str && identical(cpsi_v, "candidate_fields_checked")
        } else if (identical(cpsi_st, "NOT_APPLICABLE")) {
          cpsi_is_str && !is.na(cpsi_nm) && cpsi_nm %in% names(cpsi_na_reason_forms) &&
            any(vapply(cpsi_na_reason_forms[[cpsi_nm]],
                       function(p) grepl(paste0("^(?:", p, ")\\z"), cpsi_v, perl = TRUE), logical(1)))
        } else {
          !(cpsi_st %in% c("FAIL", "NOT_VERIFIED"))
        }
        if (!cpsi_ok) cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is outside the spec vocabulary", cpsi_path, cpsi_f))
      } else if (cpsi_kind %in% c("name", "names", "pair", "pairs")) {
        if (cpsi_kind == "pairs") {
          cpsi_ok <- is.null(cpsi_v) || (is.list(cpsi_v) && is.null(names(cpsi_v)) && all(vapply(cpsi_v, function(p)
            is.list(p) && is.null(names(p)) && length(p) == 2 &&
              all(vapply(p, function(x) is.character(x) && length(x) == 1 && x %in% cpsi_col_names, logical(1))),
            logical(1))))
        } else {
          cpsi_items <- if (cpsi_kind == "name") list(cpsi_v) else if (is.list(cpsi_v) && is.null(names(cpsi_v))) cpsi_v else NULL
          cpsi_ok <- !is.null(cpsi_items) && (cpsi_kind != "pair" || length(cpsi_items) == 2) &&
            all(vapply(cpsi_items, function(x) is.character(x) && length(x) == 1 && x %in% cpsi_col_names, logical(1)))
        }
        if (!cpsi_ok) cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is not built from declared column names", cpsi_path, cpsi_f))
      } else if (cpsi_kind == "matrix") {
        cpsi_ok <- is.list(cpsi_v) && is.null(names(cpsi_v)) && all(vapply(cpsi_v, function(r)
          is.list(r) && is.null(names(r)) &&
            all(vapply(r, function(x) is.null(x) || ((is.numeric(x) || is.logical(x)) && length(x) == 1), logical(1))),
          logical(1)))
        if (!cpsi_ok) cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is not an array of numeric rows", cpsi_path, cpsi_f))
      } else if (startsWith(cpsi_kind, "record:")) {
        if (is.list(cpsi_v) && !is.null(names(cpsi_v))) {
          cpsi_queue[length(cpsi_queue) + 1L] <- list(cpsi_v)
          cpsi_queue_path <- c(cpsi_queue_path, sprintf("%s.%s", cpsi_path, cpsi_f))
          cpsi_queue_spec <- c(cpsi_queue_spec, substring(cpsi_kind, 8))
        } else {
          cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is not a JSON object", cpsi_path, cpsi_f))
        }
      } else if (startsWith(cpsi_kind, "entries:")) {
        if (is.list(cpsi_v) && is.null(names(cpsi_v))) {
          for (cpsi_e in seq_along(cpsi_v)) {
            cpsi_ent <- cpsi_v[[cpsi_e]]
            if (is.list(cpsi_ent) && !is.null(names(cpsi_ent))) {
              cpsi_queue[length(cpsi_queue) + 1L] <- list(cpsi_ent)
              cpsi_queue_path <- c(cpsi_queue_path, sprintf("%s.%s[%d]", cpsi_path, cpsi_f, cpsi_e - 1L))
              cpsi_queue_spec <- c(cpsi_queue_spec, substring(cpsi_kind, 9))
            } else {
              cpsi_hits <- c(cpsi_hits, sprintf("%s.%s[%d] is not a JSON object", cpsi_path, cpsi_f, cpsi_e - 1L))
            }
          }
        } else {
          cpsi_hits <- c(cpsi_hits, sprintf("%s.%s is not a JSON array", cpsi_path, cpsi_f))
        }
      }
    }
  }
  # Rule (6): the top level itself — same key set, types, formats and order as the
  # Python block. Patterns are anchored with ^(?: … )\z under perl = TRUE and matched
  # byte-wise (useBytes), so a non-ASCII or invalid string simply fails the ASCII class.
  cpsi_top_kind <- c(report_version = "fmt", dataset_name = "fmt", generated_utc = "fmt", generator = "object",
                     settings = "object", dataset = "object", validation = "object", relationships = "object",
                     columns = "array")
  cpsi_top_fmt <- c(report_version = "[0-9.]{1,16}", dataset_name = "[A-Za-z0-9_-]+",
                    generated_utc = "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
  cpsi_top_names <- names(cpsi_report)
  for (cpsi_j in order(cpsi_top_names, method = "radix")) {
    cpsi_k <- cpsi_top_names[cpsi_j]
    cpsi_v <- cpsi_report[[cpsi_j]]
    cpsi_kind <- if (cpsi_k %in% names(cpsi_top_kind)) cpsi_top_kind[[cpsi_k]] else NA_character_
    if (is.na(cpsi_kind)) {
      cpsi_hits <- c(cpsi_hits, sprintf("report carries non-structural key '%s'", cpsi_esc_to[match(cpsi_k, cpsi_esc_from)]))
    } else if (cpsi_kind == "object" && !(is.list(cpsi_v) && !is.null(names(cpsi_v)))) {
      cpsi_hits <- c(cpsi_hits, sprintf("report.%s is not a JSON object", cpsi_k))
    } else if (cpsi_kind == "array" && !(is.list(cpsi_v) && is.null(names(cpsi_v)))) {
      cpsi_hits <- c(cpsi_hits, sprintf("report.%s is not a JSON array", cpsi_k))
    } else if (cpsi_kind == "fmt" && !(is.character(cpsi_v) && length(cpsi_v) == 1 &&
                                       grepl(paste0("^(?:", cpsi_top_fmt[[cpsi_k]], ")\\z"), cpsi_v, perl = TRUE, useBytes = TRUE))) {
      cpsi_hits <- c(cpsi_hits, sprintf("report.%s is outside the spec format", cpsi_k))
    }
  }
  if (length(cpsi_hits) > 0) {
    cat(sprintf("[FAIL] no_raw_value_shaped_fields: %s%s\n", cpsi_hits[1],
                if (length(cpsi_hits) > 1) sprintf(" (+%d more)", length(cpsi_hits) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else {
    cat(sprintf("[PASS] no_raw_value_shaped_fields: %d JSON nodes walked, 0 value-shaped keys, longest scalar list %d <= declared cap %d, %d column records within the per-role key allow-list, %d subtree records within the spec key allow-lists and vocabularies\n",
                cpsi_nodes, cpsi_longest, cpsi_cap, cpsi_records, cpsi_qi))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: identifier columns carry structure only, never values (NON-DECLARABLE)
# REASONING: An allow-list, not a deny-list — same contract as the Python block. The
# schema fixes exactly which keys an identifier record may carry, so any other key
# is by construction unsanctioned, and only the key NAME is ever printed.
cpsi_id_allowed_col <- c("name", "dtype", "role", "missing_rate", "nonmissing_n",
                         "n_distinct", "uniqueness_ratio", "is_identifier", "string_structure")
cpsi_id_allowed_ss <- cpsi_ss_allowed_full
cpsi_id_allowed_ss_withheld <- cpsi_ss_allowed_withheld
# INTENT: At tier 1 — the approved tier or the report's own settings.tier — an
# identifier record is held to {name, dtype} (same rule as the Python block).
cpsi_id_t1 <- (cpsi_tier_ok && tier == 1) || (cpsi_rep_tier_ok && cpsi_rep_tier == 1)
if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] identifier_columns_value_free: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (is.null(cpsi_columns)) {
  cat("[NOT VERIFIED] identifier_columns_value_free: the report carries no columns array\n")
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else {
  cpsi_bad <- character(0)
  cpsi_withheld <- 0L
  for (cpsi_col in cpsi_id_cols) {
    cpsi_name <- if (is.character(cpsi_col[["name"]]) && length(cpsi_col[["name"]]) == 1) cpsi_esc_to[match(cpsi_col[["name"]], cpsi_esc_from)] else "<unnamed>"
    # INTENT: the same number-or-boolean typing rule as no_raw_value_shaped_fields
    # (cpsi_number_keys): a string under `n_distinct` is a value, not structure.
    for (cpsi_f in sort(names(cpsi_col), method = "radix")) {
      cpsi_fv <- cpsi_col[[cpsi_f]]
      if (!(cpsi_f %in% (if (cpsi_id_t1) c("name", "dtype") else cpsi_id_allowed_col))) {
        cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
      } else if (cpsi_f %in% cpsi_number_keys && !(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
        cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a non-numeric '%s'", cpsi_name, cpsi_f))
      } else if (cpsi_f %in% names(cpsi_col_vocab) &&
                 !(is.character(cpsi_fv) && length(cpsi_fv) == 1 && cpsi_fv %in% cpsi_col_vocab[[cpsi_f]])) {
        cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a '%s' outside the spec vocabulary", cpsi_name, cpsi_f))
      }
    }
    # At tier 1 the string_structure key itself is the finding (named above).
    cpsi_ss <- if (cpsi_id_t1) NULL else cpsi_col[["string_structure"]]
    # INTENT: a non-object string_structure (e.g. a bare string) is the value itself
    # standing where structure belongs — it used to pass unexamined.
    if (!is.null(cpsi_ss) && !(is.list(cpsi_ss) && !is.null(names(cpsi_ss)))) {
      cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a non-object 'string_structure'", cpsi_name))
    }
    if (is.list(cpsi_ss) && !is.null(names(cpsi_ss))) {
      # ASSUMES: the withheld shape is identified by the presence of the `withheld`
      # key (n < k); a `withheld` that is not literally TRUE is not that shape.
      if ("withheld" %in% names(cpsi_ss)) {
        cpsi_ss_allowed <- cpsi_id_allowed_ss_withheld
        if (isTRUE(cpsi_ss[["withheld"]])) {
          cpsi_withheld <- cpsi_withheld + 1L
        } else {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries non-structural key 'withheld'", cpsi_name))
        }
      } else {
        cpsi_ss_allowed <- cpsi_id_allowed_ss
      }
      for (cpsi_f in sort(names(cpsi_ss), method = "radix")) {
        cpsi_fv <- cpsi_ss[[cpsi_f]]
        if (!(cpsi_f %in% cpsi_ss_allowed)) {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
        } else if (cpsi_f %in% cpsi_number_keys && !(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a non-numeric '%s'", cpsi_name, cpsi_f))
        } else if (cpsi_f == "reason" &&
                   !(is.character(cpsi_fv) && length(cpsi_fv) == 1 && cpsi_fv %in% cpsi_block_reason_vocab[["string_structure"]])) {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a 'reason' outside the spec vocabulary", cpsi_name))
        }
      }
      # The pattern_flags object is held to its five schema flags too.
      if ("pattern_flags" %in% cpsi_ss_allowed && !is.null(cpsi_ss[["pattern_flags"]])) {
        cpsi_x <- cpsi_ss[["pattern_flags"]]
        if (!(is.list(cpsi_x) && !is.null(names(cpsi_x)))) {
          cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a non-object 'pattern_flags'", cpsi_name))
        } else {
          for (cpsi_f in sort(names(cpsi_x), method = "radix")) {
            cpsi_fv <- cpsi_x[[cpsi_f]]
            if (!(cpsi_f %in% cpsi_flag_allowed)) {
              cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries non-structural key '%s'", cpsi_name, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
            } else if (!(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
              cpsi_bad <- c(cpsi_bad, sprintf("column '%s' carries a non-numeric '%s'", cpsi_name, cpsi_f))
            }
          }
        }
      }
    }
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] identifier_columns_value_free: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else {
    cat(sprintf("[PASS] identifier_columns_value_free: %d identifier columns examined, structure keys only (allow-list), %d withheld\n",
                length(cpsi_id_cols), cpsi_withheld))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Check: cross-tab schema and suppression are well formed (NON-DECLARABLE)
if (is.null(cpsi_report)) {
  cat(sprintf("[NOT VERIFIED] crosstab_schema_and_suppression: %s\n", cpsi_load_error))
  cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
} else if (cpsi_crosstabs_not_array) {
  cat("[FAIL] crosstab_schema_and_suppression: relationships.crosstabs is not a JSON array\n")
  cps_intake["failed"] <- cps_intake["failed"] + 1L
} else if (length(cpsi_crosstabs) == 0) {
  cat(sprintf("[PASS] crosstab_schema_and_suppression: 0 cross-tab entries declared at tier %s\n", cpsi_tier_label))
  cps_intake["passed"] <- cps_intake["passed"] + 1L
} else {
  cpsi_bad <- character(0)
  cpsi_absent <- character(0)
  cpsi_cells <- 0L
  cpsi_hidden <- 0L
  cpsi_collapsed <- 0L
  # INTENT: the missing-partner scan gates on the sweep's effective threshold,
  # max(declared, approved); NULL when either is unusable (same rule as the Python block).
  cpsi_xgate <- if (cpsi_threshold_ok && cpsi_exp_ok) max(cpsi_threshold, expected_threshold) else NULL
  # Unordered pairs seen so far (sorted column names) and the first entry index on each.
  cpsi_pair_k1 <- character(0)
  cpsi_pair_k2 <- character(0)
  cpsi_pair_ix <- integer(0)
  for (cpsi_e in seq_along(cpsi_crosstabs)) {
    cpsi_ct <- cpsi_crosstabs[[cpsi_e]]
    # INTENT: 0-based index for parity with the Python block's message text.
    cpsi_idx <- cpsi_e - 1L
    if (!(is.list(cpsi_ct) && !is.null(names(cpsi_ct)))) {
      cpsi_bad <- c(cpsi_bad, sprintf("entry index %d is not a JSON object", cpsi_idx))
      next
    }
    # Same pair-label rule as the sweep: declared column names, else the position.
    cpsi_pair <- cpsi_ct[["pair"]]
    cpsi_pair <- if (is.list(cpsi_pair) && is.null(names(cpsi_pair)) && length(cpsi_pair) > 0 &&
                     all(vapply(cpsi_pair, function(p) is.character(p) && length(p) == 1 && p %in% cpsi_col_names, logical(1)))) {
      paste(cpsi_esc_to[match(unlist(cpsi_pair), cpsi_esc_from)], collapse = " x ")
    } else {
      sprintf("index %d", cpsi_idx)
    }
    # INTENT: Entry allow-list and free-text fields — same contract and order of
    # findings as the Python block. Fields are visited by position in C-locale order.
    cpsi_raw_pair <- cpsi_ct[["pair"]]
    cpsi_pair_ok <- is.list(cpsi_raw_pair) && is.null(names(cpsi_raw_pair)) && length(cpsi_raw_pair) == 2 &&
      all(vapply(cpsi_raw_pair, function(p) is.character(p) && length(p) == 1 && p %in% cpsi_col_names, logical(1)))
    if (!cpsi_pair_ok) {
      cpsi_bad <- c(cpsi_bad, sprintf("entry index %d carries a 'pair' that is not two declared column names", cpsi_idx))
    } else {
      # INTENT: one cross-tab per unordered pair of two distinct columns, whatever each
      # entry's `available` says — same rule, order and wording as the Python block.
      if (cpsi_raw_pair[[1]] == cpsi_raw_pair[[2]]) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry index %d names one column twice in its 'pair'", cpsi_idx))
      }
      cpsi_key <- sort(c(cpsi_raw_pair[[1]], cpsi_raw_pair[[2]]), method = "radix")
      cpsi_seen <- which(cpsi_pair_k1 == cpsi_key[1] & cpsi_pair_k2 == cpsi_key[2])
      if (length(cpsi_seen) > 0) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry index %d repeats the pair of entry index %d", cpsi_idx, cpsi_pair_ix[cpsi_seen[1]]))
      } else {
        cpsi_pair_k1 <- c(cpsi_pair_k1, cpsi_key[1])
        cpsi_pair_k2 <- c(cpsi_pair_k2, cpsi_key[2])
        cpsi_pair_ix <- c(cpsi_pair_ix, cpsi_idx)
      }
    }
    cpsi_av <- cpsi_ct[["available"]]
    if (!(is.logical(cpsi_av) && length(cpsi_av) == 1 && !is.na(cpsi_av))) {
      cpsi_bad <- c(cpsi_bad, sprintf("entry %s carries a non-boolean 'available'", cpsi_pair))
    }
    cpsi_ct_allowed <- if (isTRUE(cpsi_av)) c("pair", "n", "available", "rows", "cols", "cells", "cells_suppressed", "collapsed") else
      c("pair", "n", "available", "reason", "rows", "cols", "cells")
    cpsi_ct_names <- names(cpsi_ct)
    for (cpsi_j in order(cpsi_ct_names, method = "radix")) {
      cpsi_f <- cpsi_ct_names[cpsi_j]
      cpsi_fv <- cpsi_ct[[cpsi_j]]
      if (!(cpsi_f %in% cpsi_ct_allowed)) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s carries non-structural key '%s'", cpsi_pair, cpsi_esc_to[match(cpsi_f, cpsi_esc_from)]))
      } else if (cpsi_f == "n" && !(is.null(cpsi_fv) || ((is.numeric(cpsi_fv) || is.logical(cpsi_fv)) && length(cpsi_fv) == 1))) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s carries a non-numeric 'n'", cpsi_pair))
      } else if (cpsi_f == "collapsed" && !isTRUE(cpsi_fv)) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s carries non-structural key 'collapsed'", cpsi_pair))
      }
    }
    if (!isTRUE(cpsi_ct[["available"]])) {
      cpsi_reason <- cpsi_ct[["reason"]]
      if (!(is.character(cpsi_reason) && length(cpsi_reason) == 1 && !all(utf8ToInt(cpsi_reason) %in% cpsi_ws))) {
        cpsi_bad <- c(cpsi_bad, sprintf("unavailable entry %s carries no reason", cpsi_pair))
      } else if (!(cpsi_reason %in% c("ineligible_roles", "insufficient_support"))) {
        cpsi_bad <- c(cpsi_bad, sprintf("unavailable entry %s carries a reason outside the spec vocabulary", cpsi_pair))
      }
      for (cpsi_f in c("rows", "cols", "cells")) {
        if (cpsi_f %in% names(cpsi_ct)) {
          cpsi_bad <- c(cpsi_bad, sprintf("unavailable entry %s still carries '%s'", cpsi_pair, cpsi_f))
        }
      }
      next
    }
    cpsi_r <- cpsi_ct[["rows"]]
    cpsi_c <- cpsi_ct[["cols"]]
    cpsi_grid <- cpsi_ct[["cells"]]
    if (!(is.numeric(cpsi_r) && length(cpsi_r) == 1 && !is.na(cpsi_r) && cpsi_r > 0 &&
          cpsi_r < cpsi_max_exact && cpsi_r == floor(cpsi_r)) ||
        !(is.numeric(cpsi_c) && length(cpsi_c) == 1 && !is.na(cpsi_c) && cpsi_c > 0 &&
          cpsi_c < cpsi_max_exact && cpsi_c == floor(cpsi_c)) ||
        !(is.list(cpsi_grid) && is.null(names(cpsi_grid)))) {
      # REASONING: validated fields, so a wrong type or bad dimension is a [FAIL].
      cpsi_bad <- c(cpsi_bad, sprintf("entry %s has no positive integer rows/cols with a cells array — the grid cannot be reshaped", cpsi_pair))
      next
    }
    # INTENT: an available grid sits on the released categories — rows / cols equal the
    # released level counts of the first / second pair column. Same rule, order and
    # wording as the Python block; the first column record carrying the name is used.
    # The two pair column records are kept for the missing-partner scan below.
    cpsi_x_cols <- list()
    if (cpsi_pair_ok) {
      for (cpsi_p in 0:1) {
        cpsi_pc <- NULL
        for (cpsi_pcand in cpsi_columns) {
          if (is.character(cpsi_pcand[["name"]]) && length(cpsi_pcand[["name"]]) == 1 &&
              cpsi_pcand[["name"]] == cpsi_raw_pair[[cpsi_p + 1L]]) {
            cpsi_pc <- cpsi_pcand
            break
          }
        }
        cpsi_prole <- cpsi_pc[["role"]]
        cpsi_pblk <- cpsi_pc[["categorical"]]
        if (!(is.character(cpsi_prole) && length(cpsi_prole) == 1 && cpsi_prole == "categorical" &&
              is.list(cpsi_pblk) && !is.null(names(cpsi_pblk)) &&
              is.list(cpsi_pblk[["levels"]]) && is.null(names(cpsi_pblk[["levels"]])))) {
          cpsi_bad <- c(cpsi_bad, sprintf("entry %s pair position %d is not a categorical column with a released levels array",
                                          cpsi_pair, cpsi_p))
        } else if (length(cpsi_pblk[["levels"]]) != (if (cpsi_p == 0L) cpsi_r else cpsi_c)) {
          cpsi_bad <- c(cpsi_bad, sprintf("entry %s has %s unequal to the released level count of pair position %d",
                                          cpsi_pair, if (cpsi_p == 0L) "rows" else "cols", cpsi_p))
        } else {
          cpsi_x_cols <- c(cpsi_x_cols, list(cpsi_pc))
        }
      }
    }
    cpsi_x_run <- length(cpsi_x_cols) == 2 && cpsi_raw_pair[[1]] != cpsi_raw_pair[[2]]
    if (length(cpsi_grid) != cpsi_r * cpsi_c) {
      # INTENT: print rows x cols from exact integers, as Python's int product does: a
      # double product above 2^53 rounds. Base-1e7 limbs keep every partial product and
      # carry below 2^53, so each step is exact; the limbs are then printed in order.
      cpsi_rl <- c(cpsi_r %% 1e7, ((cpsi_r - cpsi_r %% 1e7) / 1e7) %% 1e7, (cpsi_r - cpsi_r %% 1e14) / 1e14)
      cpsi_cl <- c(cpsi_c %% 1e7, ((cpsi_c - cpsi_c %% 1e7) / 1e7) %% 1e7, (cpsi_c - cpsi_c %% 1e14) / 1e14)
      cpsi_pl <- numeric(6)
      for (cpsi_i in 1:3) for (cpsi_j in 1:3) cpsi_pl[cpsi_i + cpsi_j - 1] <- cpsi_pl[cpsi_i + cpsi_j - 1] + cpsi_rl[cpsi_i] * cpsi_cl[cpsi_j]
      for (cpsi_i in 1:5) {
        cpsi_pl[cpsi_i + 1] <- cpsi_pl[cpsi_i + 1] + (cpsi_pl[cpsi_i] - cpsi_pl[cpsi_i] %% 1e7) / 1e7
        cpsi_pl[cpsi_i] <- cpsi_pl[cpsi_i] %% 1e7
      }
      cpsi_prod <- sub("^0+(?=[0-9])", "", paste(sprintf("%07.0f", rev(cpsi_pl)), collapse = ""), perl = TRUE)
      cpsi_bad <- c(cpsi_bad, sprintf("entry %s has %d cells, not rows x cols = %s",
                                      cpsi_pair, length(cpsi_grid), cpsi_prod))
      next
    }
    cpsi_is_null <- vapply(cpsi_grid, is.null, logical(1))
    cpsi_cells <- cpsi_cells + length(cpsi_grid)
    cpsi_hidden <- cpsi_hidden + sum(cpsi_is_null)
    # A visible 0 is a structural zero and legitimate; a hidden cell mis-coded as 0 is
    # still caught, because cells_suppressed then disagrees with the nulls.
    cpsi_reported <- cpsi_ct[["cells_suppressed"]]
    if (!(is.numeric(cpsi_reported) && length(cpsi_reported) == 1 && !is.na(cpsi_reported) &&
          cpsi_reported == sum(cpsi_is_null))) {
      cpsi_bad <- c(cpsi_bad, sprintf("entry %s reports a cells_suppressed that disagrees with the %d nulls in the grid",
                                      cpsi_pair, sum(cpsi_is_null)))
    }
    # INTENT: Differencing residual — same rule, order and wording as the Python block.
    # ASSUMES: with every visible cell a whole number in [0, 2^53) the running double sum
    # is exact until it passes 2^53, after which it stays above any valid n.
    cpsi_vis <- cpsi_grid[!cpsi_is_null]
    cpsi_ctn <- cpsi_ct[["n"]]
    if (all(vapply(cpsi_vis, function(v) is.numeric(v) && length(v) == 1 && !is.na(v) && v >= 0 &&
                   v < cpsi_max_exact && v == floor(v), logical(1)))) {
      cpsi_tot <- sum(vapply(cpsi_vis, function(v) as.numeric(v), numeric(1)))
      if (!(is.numeric(cpsi_ctn) && length(cpsi_ctn) == 1 && !is.na(cpsi_ctn) && cpsi_ctn >= 0 &&
            cpsi_ctn < cpsi_max_exact && cpsi_ctn == floor(cpsi_ctn))) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s carries no whole-number 'n' to reconcile its cells against", cpsi_pair))
      } else if (cpsi_tot > cpsi_ctn) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s releases visible cells that sum past its n", cpsi_pair))
      } else if (sum(cpsi_is_null) == 0 && cpsi_tot != cpsi_ctn) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s hides no cell but its visible cells do not sum to its n", cpsi_pair))
      }
    }
    # INTENT: `collapsed: true` earns the lone-cell bypass only when the table is
    # hidden whole; a collapsed flag over visible cells is a bypass, not a
    # suppression. Same contract as the Python block.
    if (isTRUE(cpsi_ct[["collapsed"]])) {
      if (sum(cpsi_is_null) == length(cpsi_grid)) {
        cpsi_collapsed <- cpsi_collapsed + 1L
      } else {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %d is marked collapsed but still releases visible cells", cpsi_idx))
      }
    } else {
      # INTENT: name the first offending row / column by 0-based index, as Python does.
      cpsi_mask <- matrix(cpsi_is_null, nrow = cpsi_r, ncol = cpsi_c, byrow = TRUE)
      cpsi_lone <- which(rowSums(cpsi_mask) == 1)
      if (length(cpsi_lone) > 0) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s leaves a lone hidden cell in row index %d — recoverable by differencing", cpsi_pair, cpsi_lone[1] - 1L))
      }
      cpsi_lone <- which(colSums(cpsi_mask) == 1)
      if (length(cpsi_lone) > 0) {
        cpsi_bad <- c(cpsi_bad, sprintf("entry %s leaves a lone hidden cell in column index %d — recoverable by differencing", cpsi_pair, cpsi_lone[1] - 1L))
      }
      # INTENT: Bridge scan — same rule, order and wording as the Python block: a hidden
      # cell whose edge in the row/column graph of hidden cells lies on no cycle is
      # pinned exactly by the released totals. Degree-1 bridges keep the lone-cell
      # finding above; every other bridge is named by 0-based row and column index in
      # row-major order. Vertices (1-based here): row i is i + 1, column j is rows + j + 1;
      # cells are carried by their 0-based row-major index, as in the Python block.
      # REASONING: iterative low-link walk with the stack held in parallel vectors, so
      # a large grid neither recurses nor stalls the block. The adjacency lists are built
      # in one split() rather than by appending cell by cell (which copies each list on
      # every append); split() keeps each vertex's cells in ascending order, the order
      # the Python block appends them in.
      cpsi_br_ks <- which(cpsi_is_null) - 1
      cpsi_br_adj <- unname(split(c(cpsi_br_ks, cpsi_br_ks),
                                  factor(c(cpsi_br_ks %/% cpsi_c + 1, cpsi_r + cpsi_br_ks %% cpsi_c + 1),
                                         levels = seq_len(cpsi_r + cpsi_c))))
      cpsi_br_disc <- numeric(cpsi_r + cpsi_c)
      cpsi_br_low <- numeric(cpsi_r + cpsi_c)
      cpsi_br_time <- 0
      cpsi_br_found <- numeric(0)
      for (cpsi_br_root in which(lengths(cpsi_br_adj) > 0)) {
        if (cpsi_br_disc[cpsi_br_root] > 0) next
        cpsi_br_time <- cpsi_br_time + 1
        cpsi_br_disc[cpsi_br_root] <- cpsi_br_time
        cpsi_br_low[cpsi_br_root] <- cpsi_br_time
        # Stack frames: vertex, hidden cell it was reached by (-1 at the root), next
        # position in its adjacency list.
        cpsi_br_sv <- cpsi_br_root
        cpsi_br_se <- -1
        cpsi_br_si <- 1
        while (length(cpsi_br_sv) > 0) {
          cpsi_br_n <- length(cpsi_br_sv)
          cpsi_br_v <- cpsi_br_sv[cpsi_br_n]
          if (cpsi_br_si[cpsi_br_n] <= length(cpsi_br_adj[[cpsi_br_v]])) {
            cpsi_br_k <- cpsi_br_adj[[cpsi_br_v]][cpsi_br_si[cpsi_br_n]]
            cpsi_br_si[cpsi_br_n] <- cpsi_br_si[cpsi_br_n] + 1
            if (cpsi_br_k == cpsi_br_se[cpsi_br_n]) next
            cpsi_br_w <- if (cpsi_br_v <= cpsi_r) cpsi_r + cpsi_br_k %% cpsi_c + 1 else cpsi_br_k %/% cpsi_c + 1
            if (cpsi_br_disc[cpsi_br_w] == 0) {
              cpsi_br_time <- cpsi_br_time + 1
              cpsi_br_disc[cpsi_br_w] <- cpsi_br_time
              cpsi_br_low[cpsi_br_w] <- cpsi_br_time
              cpsi_br_sv <- c(cpsi_br_sv, cpsi_br_w)
              cpsi_br_se <- c(cpsi_br_se, cpsi_br_k)
              cpsi_br_si <- c(cpsi_br_si, 1)
            } else {
              cpsi_br_low[cpsi_br_v] <- min(cpsi_br_low[cpsi_br_v], cpsi_br_disc[cpsi_br_w])
            }
          } else {
            cpsi_br_pe <- cpsi_br_se[cpsi_br_n]
            cpsi_br_sv <- cpsi_br_sv[-cpsi_br_n]
            cpsi_br_se <- cpsi_br_se[-cpsi_br_n]
            cpsi_br_si <- cpsi_br_si[-cpsi_br_n]
            if (cpsi_br_n > 1) {
              cpsi_br_u <- cpsi_br_sv[cpsi_br_n - 1]
              cpsi_br_low[cpsi_br_u] <- min(cpsi_br_low[cpsi_br_u], cpsi_br_low[cpsi_br_v])
              if (cpsi_br_low[cpsi_br_v] > cpsi_br_disc[cpsi_br_u]) cpsi_br_found <- c(cpsi_br_found, cpsi_br_pe)
            }
          }
        }
      }
      for (cpsi_br_k in sort(cpsi_br_found, method = "radix")) {
        if (length(cpsi_br_adj[[cpsi_br_k %/% cpsi_c + 1]]) > 1 && length(cpsi_br_adj[[cpsi_r + cpsi_br_k %% cpsi_c + 1]]) > 1) {
          cpsi_bad <- c(cpsi_bad, sprintf("entry %s leaves hidden cell at row index %.0f, column index %.0f recoverable from the released totals",
                                          cpsi_pair, cpsi_br_k %/% cpsi_c, cpsi_br_k %% cpsi_c))
        }
      }
    }
    # INTENT: Missing-partner scan — same model, order and wording as the Python block
    # (see its comment): the grid is extended by a partner-missing column (vertex
    # rows + cols + 2 here, 1-based) and a partner-missing row (rows + cols + 1); the
    # corner is known; a line totalling 0 adds no edge; a missing-partner cell whose edge
    # is a bridge is pinned, with the value of its cut; bridges of the all-hidden graph
    # (a one-row grid's column cells, a one-column grid's row cells) are exempt; a value
    # that is negative or in (0, gate) is a [FAIL] naming the position only.
    # REASONING: every total is a whole number below 2^53 and so is their sum, so each
    # subtree sum below is an exact double. Edges are carried by 1-based id in the
    # Python block's order (hidden cells, then the partner-missing column, then the
    # partner-missing row); every vertex appears at one end only, so split() keeps each
    # adjacency list in ascending id order, the order the Python block appends in, and
    # the walk visits the graph identically.
    if (cpsi_x_run) {
      cpsi_xn <- cpsi_ct[["n"]]
      cpsi_xnn <- list(cpsi_x_cols[[1]][["nonmissing_n"]], cpsi_x_cols[[2]][["nonmissing_n"]])
      if (!all(vapply(c(list(cpsi_xn), cpsi_xnn), function(x) is.numeric(x) && length(x) == 1 && !is.na(x) &&
                      x >= 0 && x < cpsi_max_exact && x == floor(x), logical(1)))) {
        cpsi_absent <- c(cpsi_absent, sprintf("entry %s lacks the released totals the missing-partner scan needs", cpsi_pair))
      } else {
        cpsi_xnn <- c(cpsi_xnn[[1]], cpsi_xnn[[2]])
        for (cpsi_p in 0:1) {
          if (cpsi_xn > cpsi_xnn[cpsi_p + 1L]) {
            cpsi_bad <- c(cpsi_bad, sprintf("entry %s has an n above the nonmissing_n of pair position %d", cpsi_pair, cpsi_p))
          }
        }
        cpsi_xa <- cpsi_xnn[1] - cpsi_xn
        cpsi_xb <- cpsi_xnn[2] - cpsi_xn
        if (cpsi_xa >= 0 && cpsi_xb >= 0 && cpsi_xa + cpsi_xb > 0 && sum(cpsi_is_null) < length(cpsi_grid)) {
          cpsi_xtot <- list()
          for (cpsi_pc in cpsi_x_cols) {
            cpsi_lvs <- cpsi_pc[["categorical"]][["levels"]]
            cpsi_lv_ok <- all(vapply(cpsi_lvs, function(lv) is.list(lv) && !is.null(names(lv)) &&
                                       is.character(lv[["value"]]) && length(lv[["value"]]) == 1 &&
                                       is.numeric(lv[["count"]]) && length(lv[["count"]]) == 1 && !is.na(lv[["count"]]) &&
                                       lv[["count"]] >= 0 && lv[["count"]] < cpsi_max_exact && lv[["count"]] == floor(lv[["count"]]),
                                     logical(1)))
            cpsi_xvals <- if (cpsi_lv_ok) vapply(cpsi_lvs, function(lv) lv[["value"]], character(1)) else character(0)
            if (!cpsi_lv_ok || anyDuplicated(cpsi_xvals) > 0) {
              cpsi_xtot <- NULL
              break
            }
            # Released categories in grid order: kept labels in code-point (C-locale byte)
            # order, then __OTHER__ last when the block releases it.
            cpsi_xcnts <- vapply(cpsi_lvs, function(lv) as.numeric(lv[["count"]]), numeric(1))
            cpsi_xord <- c(sort(cpsi_xvals[cpsi_xvals != "__OTHER__"], method = "radix"), cpsi_xvals[cpsi_xvals == "__OTHER__"])
            cpsi_xtot <- c(cpsi_xtot, list(cpsi_xcnts[match(cpsi_xord, cpsi_xvals)]))
          }
          cpsi_xvis_ok <- all(vapply(cpsi_vis, function(v) is.numeric(v) && length(v) == 1 && !is.na(v) && v >= 0 &&
                                       v < cpsi_max_exact && v == floor(v), logical(1)))
          if (is.null(cpsi_xtot) || !cpsi_xvis_ok ||
              sum(cpsi_xtot[[1]]) + sum(cpsi_xtot[[2]]) + 2 * sum(vapply(cpsi_vis, as.numeric, numeric(1))) +
              cpsi_xnn[1] + cpsi_xnn[2] + 2 * cpsi_xn >= cpsi_max_exact) {
            cpsi_absent <- c(cpsi_absent, sprintf("entry %s lacks the released totals the missing-partner scan needs", cpsi_pair))
          } else {
            cpsi_xV <- cpsi_r + cpsi_c + 2
            cpsi_xm <- matrix(vapply(cpsi_grid, function(v) if (is.null(v)) 0 else as.numeric(v), numeric(1)),
                              nrow = cpsi_r, ncol = cpsi_c, byrow = TRUE)
            cpsi_xw <- c(cpsi_xtot[[1]] - rowSums(cpsi_xm), -(cpsi_xtot[[2]] - colSums(cpsi_xm)), cpsi_xb, -cpsi_xa)
            cpsi_xks <- which(cpsi_is_null) - 1
            cpsi_xu <- cpsi_xks %/% cpsi_c
            cpsi_xv <- cpsi_r + cpsi_xks %% cpsi_c
            cpsi_xcore <- length(cpsi_xu)
            if (cpsi_xa > 0) {
              cpsi_xu <- c(cpsi_xu, seq_len(cpsi_r) - 1)
              cpsi_xv <- c(cpsi_xv, rep(cpsi_r + cpsi_c + 1, cpsi_r))
            }
            if (cpsi_xb > 0) {
              cpsi_xu <- c(cpsi_xu, rep(cpsi_r + cpsi_c, cpsi_c))
              cpsi_xv <- c(cpsi_xv, cpsi_r + seq_len(cpsi_c) - 1)
            }
            cpsi_xids <- seq_along(cpsi_xu)
            cpsi_xadj <- unname(split(c(cpsi_xids, cpsi_xids), factor(c(cpsi_xu, cpsi_xv) + 1, levels = seq_len(cpsi_xV))))
            cpsi_xdisc <- numeric(cpsi_xV)
            cpsi_xlow <- numeric(cpsi_xV)
            cpsi_xsub <- cpsi_xw
            cpsi_xtime <- 0
            cpsi_xfe <- numeric(0)
            cpsi_xfv <- numeric(0)
            for (cpsi_xroot in seq_len(cpsi_xV)) {
              if (cpsi_xdisc[cpsi_xroot] > 0 || length(cpsi_xadj[[cpsi_xroot]]) == 0) next
              cpsi_xtime <- cpsi_xtime + 1
              cpsi_xdisc[cpsi_xroot] <- cpsi_xtime
              cpsi_xlow[cpsi_xroot] <- cpsi_xtime
              # Stack frames: vertex, edge id it was reached by (-1 at the root), next
              # adjacency position; a bridge's cut is its child's subtree sum.
              cpsi_xsv <- cpsi_xroot
              cpsi_xse <- -1
              cpsi_xsi <- 1
              while (length(cpsi_xsv) > 0) {
                cpsi_xdepth <- length(cpsi_xsv)
                cpsi_xvx <- cpsi_xsv[cpsi_xdepth]
                if (cpsi_xsi[cpsi_xdepth] <= length(cpsi_xadj[[cpsi_xvx]])) {
                  cpsi_xe <- cpsi_xadj[[cpsi_xvx]][cpsi_xsi[cpsi_xdepth]]
                  cpsi_xsi[cpsi_xdepth] <- cpsi_xsi[cpsi_xdepth] + 1
                  if (cpsi_xe == cpsi_xse[cpsi_xdepth]) next
                  cpsi_xw2 <- if (cpsi_xu[cpsi_xe] + 1 == cpsi_xvx) cpsi_xv[cpsi_xe] + 1 else cpsi_xu[cpsi_xe] + 1
                  if (cpsi_xdisc[cpsi_xw2] == 0) {
                    cpsi_xtime <- cpsi_xtime + 1
                    cpsi_xdisc[cpsi_xw2] <- cpsi_xtime
                    cpsi_xlow[cpsi_xw2] <- cpsi_xtime
                    cpsi_xsv <- c(cpsi_xsv, cpsi_xw2)
                    cpsi_xse <- c(cpsi_xse, cpsi_xe)
                    cpsi_xsi <- c(cpsi_xsi, 1)
                  } else {
                    cpsi_xlow[cpsi_xvx] <- min(cpsi_xlow[cpsi_xvx], cpsi_xdisc[cpsi_xw2])
                  }
                } else {
                  cpsi_xpe <- cpsi_xse[cpsi_xdepth]
                  cpsi_xsv <- cpsi_xsv[-cpsi_xdepth]
                  cpsi_xse <- cpsi_xse[-cpsi_xdepth]
                  cpsi_xsi <- cpsi_xsi[-cpsi_xdepth]
                  if (cpsi_xdepth > 1) {
                    cpsi_xpar <- cpsi_xsv[cpsi_xdepth - 1]
                    cpsi_xlow[cpsi_xpar] <- min(cpsi_xlow[cpsi_xpar], cpsi_xlow[cpsi_xvx])
                    cpsi_xsub[cpsi_xpar] <- cpsi_xsub[cpsi_xpar] + cpsi_xsub[cpsi_xvx]
                    if (cpsi_xlow[cpsi_xvx] > cpsi_xdisc[cpsi_xpar] && cpsi_xpe > cpsi_xcore) {
                      cpsi_xfe <- c(cpsi_xfe, cpsi_xpe)
                      cpsi_xfv <- c(cpsi_xfv, if (cpsi_xu[cpsi_xpe] + 1 == cpsi_xvx) cpsi_xsub[cpsi_xvx] else -cpsi_xsub[cpsi_xvx])
                    }
                  }
                }
              }
            }
            cpsi_xungated <- FALSE
            for (cpsi_xk in order(cpsi_xfe, method = "radix")) {
              cpsi_xt <- cpsi_xfe[cpsi_xk] - cpsi_xcore - 1
              if (cpsi_xa > 0 && cpsi_xt < cpsi_r) {
                cpsi_xside <- "row"
                cpsi_xpos <- cpsi_xt
                cpsi_xexempt <- cpsi_r == 1
              } else {
                cpsi_xside <- "column"
                cpsi_xpos <- cpsi_xt - (if (cpsi_xa > 0) cpsi_r else 0)
                cpsi_xexempt <- cpsi_c == 1
              }
              if (cpsi_xexempt) next
              cpsi_xval <- cpsi_xfv[cpsi_xk]
              if (is.null(cpsi_xgate)) {
                cpsi_xungated <- TRUE
              } else if (cpsi_xval < 0 || (cpsi_xval > 0 && cpsi_xval < cpsi_xgate)) {
                cpsi_bad <- c(cpsi_bad, sprintf("entry %s leaves the missing-partner cell at %s index %.0f recoverable from the released totals",
                                                cpsi_pair, cpsi_xside, cpsi_xpos))
              }
            }
            if (cpsi_xungated) {
              cpsi_absent <- c(cpsi_absent, sprintf("entry %s cannot gate its missing-partner cells: expected_threshold or settings.suppression_threshold is unusable", cpsi_pair))
            }
          }
        }
      }
    }
  }
  if (length(cpsi_bad) > 0) {
    cat(sprintf("[FAIL] crosstab_schema_and_suppression: %s%s\n", cpsi_bad[1],
                if (length(cpsi_bad) > 1) sprintf(" (+%d more)", length(cpsi_bad) - 1) else ""))
    cps_intake["failed"] <- cps_intake["failed"] + 1L
  } else if (length(cpsi_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] crosstab_schema_and_suppression: %s%s\n", cpsi_absent[1],
                if (length(cpsi_absent) > 1) sprintf(" (+%d more)", length(cpsi_absent) - 1) else ""))
    cps_intake["not_verified"] <- cps_intake["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] crosstab_schema_and_suppression: %d entries, %d cells examined, %d hidden as null, %d fully collapsed, no hidden cell recoverable from the row and column totals\n",
                length(cpsi_crosstabs), cpsi_cells, cpsi_hidden, cpsi_collapsed))
    cps_intake["passed"] <- cps_intake["passed"] + 1L
  }
}

# Count line, then verdict derived from the counts
cpsi_checks_run <- cps_intake[["passed"]] + cps_intake[["warning"]] + cps_intake[["failed"]]
if (cps_intake[["failed"]] > 0 || cps_intake[["not_verified"]] > 0 || cpsi_checks_run == 0) {
  cpsi_verdict <- "FAILED"
} else if (cps_intake[["warning"]] > 0) {
  cpsi_verdict <- "PASSED WITH WARNINGS"
} else {
  cpsi_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cps_intake[["passed"]], cps_intake[["warning"]], cps_intake[["failed"]],
            cps_intake[["not_verified"]], cps_intake[["skipped"]]))
cat(sprintf("CPS-INTAKE VALIDATION: %s\n", cpsi_verdict))
cat(strrep("=", 60), "\n")

if (cpsi_verdict == "FAILED") {
  stop("CPS-INTAKE FAILED - see details above")
}
```

**`not_applicable` keys recognized by CPS-INTAKE:** `report_version`, `required_top_level_keys`, `row_count_positive`, `percentiles_monotone`, `category_counts_le_rowcount`, `missing_rate_in_unit_interval`, `correlation_matrix_wellformed`, `embedded_validation_complete`. The remaining four keys — `no_released_count_below_threshold`, `no_raw_value_shaped_fields`, `identifier_columns_value_free`, `crosstab_schema_and_suppression` — are **non-declarable**: declaring one is itself a `[FAIL]` and the check runs anyway.

### CPS-GEN: Synthetic Generation Validation (DS-5)

**When:** Immediately after the generation script writes the synthetic parquet to `data/synthetic/` and before any downstream code, notebook, or skill example reads it (DS-5). (T4: `scripts/synth_generate/01_import-synthetic.{py,R}`, at the end of the import — once the user's synthetic rows are in `data/synthetic/` as Parquet.)

CPS-GEN compares the generated frame against the profile report it was built from. Its distinctive risk is the mirror image of CPS-INTAKE's: not that the report leaked something, but that generation *invented* something the report deliberately withheld — a rare level that suppression removed, an identifier carrying a real value, a distribution nobody targeted. Fidelity deviations are `[WARNING]` (a generator tuning question); fabrication and structural mismatch are `[FAIL]`.

**Embedded in:** `scripts/synth_generate/01_generate-synthetic.py` (`.R` for R) — CPS-GEN is embedded at the **end of the generation script itself**, after the synthetic parquet has been written, not in a separate validation script. The frame it checks is the one the script just produced. (T4: `scripts/synth_generate/01_import-synthetic.{py,R}`, at the end of the import — the frame it checks is the one the import just wrote.)

**Config stanza (the block's own `# --- Config ---` region, reproduced for reference — assign your values there):**
```python
# --- Config ---
synthetic_path = None      # the parquet the generation (T4: import) step wrote; None if it produced nothing
report_path = None         # the profile report the generation targeted
seed = None                # the integer seed the generator ran with (T4: from the user's generation log); None if never recorded
seed_exception = None      # T4 only: non-empty pointer to the researcher-authorized missing-seed exception in STATE; never printed
tier = None                # the tier the report was produced at (its settings.tier); 4 only for a T4 import
numeric_tolerance = 0.10   # relative tolerance per reproduced percentile, floor 1.0 absolute
proportion_tolerance = 0.02  # absolute tolerance on categorical level proportions
correlation_tolerance = 0.10  # the one absolute tolerance applied to every reproduced correlation
missingness_tolerance = 0.01  # absolute tolerance on per-column null rates
not_applicable = {}        # e.g. {"correlations_within_tolerance": "tier 2 — no correlations released"}
```

`seed` and `seed_exception` are mutually exclusive: set `seed` whenever a seed exists; set `seed_exception` only at tier 4, only when the user's generation recorded no seed and the researcher authorized that exception at the gate (its value points into STATE and is never printed). R uses the same names with `NULL` in place of `None` (`seed_exception <- NULL`).

```python
# --- CPS-GEN Validation ---
# INTENT: Verify the generated synthetic frame matches the profile it was built
# from — shape, schema, marginals, missingness — and fabricates nothing the
# report withheld.
# REASONING: Fidelity gaps are a tuning question ([WARNING]); fabrication is a
# disclosure-adjacent defect ([FAIL]), because a level the report suppressed and
# the generator re-invented looks to a reader exactly like a released one. No input
# stops the block early: a wrong-typed value in the synthetic frame under validation
# is a [FAIL], wrong-typed report evidence a check needs is a [NOT VERIFIED], and
# every check reaches its own outcome line before the count line and verdict.
# ASSUMES: synthetic_path / report_path / seed / seed_exception / tier / the
# tolerances / not_applicable are assigned in the `# --- Config ---` region below.
import json
import math
import re
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

# --- Config ---
synthetic_path = None      # the parquet the generation (T4: import) step wrote; None if it produced nothing
report_path = None         # the profile report the generation targeted
seed = None                # the integer seed the generator ran with (T4: from the user's generation log); None if never recorded
seed_exception = None      # T4 only: non-empty pointer to the researcher-authorized missing-seed exception in STATE; never printed
tier = None                # the tier the report was produced at (its settings.tier); 4 only for a T4 import
numeric_tolerance = 0.10   # relative tolerance per reproduced percentile, floor 1.0 absolute
proportion_tolerance = 0.02  # absolute tolerance on categorical level proportions
correlation_tolerance = 0.10  # the one absolute tolerance applied to every reproduced correlation
missingness_tolerance = 0.01  # absolute tolerance on per-column null rates
not_applicable = {}        # e.g. {"correlations_within_tolerance": "tier 2 — no correlations released"}

print("\n" + "=" * 60)
print("CPS-GEN VALIDATION: SYNTHETIC GENERATION")
print("=" * 60)

cps_gen = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# INTENT: A declared skip without a reason is indistinguishable from a silent one, so
# it is dropped — but the key stays visible to the two sweeps below, so an empty
# reason cannot be used to smuggle a declaration past the non-declarable or
# unrecognized-key gates.
# REASONING: "Empty" means blank under Unicode whitespace — Python's str.strip() set,
# which the R block reproduces code point for code point — so a reason made only of
# no-break or ideographic spaces is blank in both languages.
cpsg_declared_keys = sorted(not_applicable)
not_applicable = {k: v for k, v in not_applicable.items() if isinstance(v, str) and v.strip()}
# INTENT: Remember which declarable keys were dropped for an empty reason, so the
# check they name reports [NOT VERIFIED] rather than silently running.
# REASONING: The author declared the check inapplicable; running it anyway and
# printing [PASS] would answer a question they explicitly withdrew. The reason is
# the evidence, and there is none — so the outcome is "not verified", not "passed".
cpsg_empty_reason = set(cpsg_declared_keys) - set(not_applicable)

# INTENT: Disclosure-critical checks may never be declared not applicable.
cpsg_non_declarable = ("suppressed_categories_absent", "synthetic_levels_within_released_levels",
                       "identifier_columns_value_free", "seed_recorded")
for cpsg_key in cpsg_non_declarable:
    if cpsg_key in cpsg_declared_keys:
        print(f"[FAIL] {cpsg_key}: non-declarable check declared not_applicable under key '{cpsg_key}'")
        cps_gen["failed"] += 1
        not_applicable.pop(cpsg_key, None)

# INTENT: A not_applicable key that names no check of this block is a silent no-op.
# REASONING: A typo'd or stale key would otherwise declare nothing and be ignored,
# leaving the author believing a check was skipped when it in fact ran (or the
# reverse). Naming it once is the only way the log can carry the discrepancy.
cpsg_declarable = ("row_count_matches", "column_set_and_dtypes",
                   "numeric_marginals_within_tolerance",
                   "categorical_proportions_within_tolerance",
                   "correlations_within_tolerance", "missingness_within_tolerance")
for cpsg_key in cpsg_declared_keys:
    if cpsg_key in cpsg_non_declarable or cpsg_key in cpsg_declarable:
        continue
    print(f"[FAIL] not_applicable: unrecognized key '{cpsg_key}' (declarable keys: {', '.join(cpsg_declarable)})")
    cps_gen["failed"] += 1
    not_applicable.pop(cpsg_key, None)

# INTENT: Bind both inputs once so a missing one becomes a named [NOT VERIFIED].
cpsg_parse_error = "report did not parse as JSON (parser message withheld: it can quote report content)"
cpsg_report = None
cpsg_report_error = None
cpsg_report_strings = set()
if report_path is None:
    cpsg_report_error = "report_path is not set — the generation target is unknown"
elif not Path(report_path).is_file():
    cpsg_report_error = f"no file at report_path '{report_path}'"
else:
    # REASONING: Parsing is strict and identical to CPS-INTAKE and to the R block.
    # `parse_constant=int` makes the non-JSON literals NaN / Infinity / -Infinity a
    # parse error (int("NaN") raises ValueError), as they are in jsonlite. A
    # duplicate object key at any depth is a parse error too: a Python dict keeps
    # the last value while jsonlite keeps both, so the two languages would otherwise
    # validate two different reports. The first pass keeps every object as its raw
    # (key, value) list, so a repeat stays visible; the second builds the dicts the
    # checks read. Nesting deeper than 64 levels is a parse error as well, with the
    # same cap and level count as CPS-INTAKE (sweep below), and so is a number token
    # longer than 64 characters (scan below). The parser's own message is withheld —
    # it can quote report text, and the R parser words it differently.
    cpsg_pairs = None
    cpsg_text = None
    # INTENT: Refuse, before either parser runs, every input the two parsers would read
    # differently.
    # REASONING: jsonlite accepts a leading UTF-8 byte-order mark with only a warning
    # where json.loads refuses it; jsonlite silently cuts a string at an escaped NUL
    # (\u0000) and replaces an unpaired surrogate escape, where Python keeps both. A raw
    # NUL byte and invalid UTF-8 are refused by both parsers, but R's text reader would
    # stop at the NUL first. All of these are therefore parse errors, decided on the
    # bytes and on the escape sequences, the same way in both blocks.
    try:
        cpsg_bytes = Path(report_path).read_bytes()
        if cpsg_bytes[:3] != b"\xef\xbb\xbf" and b"\x00" not in cpsg_bytes:
            cpsg_text = cpsg_bytes.decode("utf-8")
    except (ValueError, OSError):
        cpsg_text = None
    if cpsg_text is not None:
        # INTENT: Walk the escape sequences left to right. An escaped backslash is one
        # token, so the text `\\u0000` (a backslash, then u0000) is not an escape.
        # ASSUMES: a \u escape is exactly six characters, so a surrogate pair is a high
        # escape immediately followed by a low one.
        cpsg_toks = [(cpsg_m.start(), cpsg_m.group(0)) for cpsg_m in re.finditer(r"\\(?:u[0-9a-fA-F]{4}|[^u])", cpsg_text)]
        cpsg_cps = [int(cpsg_t[1][2:], 16) if cpsg_t[1][1] == "u" else -1 for cpsg_t in cpsg_toks]
        for cpsg_i in range(len(cpsg_toks)):
            cpsg_cp = cpsg_cps[cpsg_i]
            cpsg_hi_ok = (cpsg_i + 1 < len(cpsg_toks) and cpsg_toks[cpsg_i + 1][0] == cpsg_toks[cpsg_i][0] + 6
                          and 0xDC00 <= cpsg_cps[cpsg_i + 1] <= 0xDFFF)
            cpsg_lo_ok = (cpsg_i > 0 and cpsg_toks[cpsg_i - 1][0] == cpsg_toks[cpsg_i][0] - 6
                          and 0xD800 <= cpsg_cps[cpsg_i - 1] <= 0xDBFF)
            if (cpsg_cp == 0 or (0xD800 <= cpsg_cp <= 0xDBFF and not cpsg_hi_ok)
                    or (0xDC00 <= cpsg_cp <= 0xDFFF and not cpsg_lo_ok)):
                cpsg_text = None
                break
    if cpsg_text is not None:
        # INTENT: Refuse any JSON number token longer than 64 characters (sign, digits,
        # fraction and exponent counted together) outside strings, the same decision as
        # CPS-INTAKE and the R block.
        # REASONING: Python refuses an integer past its 4300-digit conversion limit while
        # jsonlite reads it as Inf and parses on, so the two languages would otherwise
        # reach different verdicts on the same file. A profiler never writes a number
        # anywhere near 64 characters (a double needs at most 24), so the cap refuses
        # only text the two parsers read differently. Each string is matched whole first,
        # so digits inside a string never count; the R block uses the same pattern.
        for cpsg_nm in re.finditer(r'"[^"\\]*(?:\\.[^"\\]*)*"|[-+.0-9eE]+', cpsg_text, re.S):
            if cpsg_nm.group(0)[0] != '"' and len(cpsg_nm.group(0)) > 64:
                cpsg_text = None
                break
    if cpsg_text is None:
        cpsg_report_error = cpsg_parse_error
    else:
        try:
            cpsg_pairs = json.loads(cpsg_text, parse_constant=int, object_pairs_hook=list)
            cpsg_report = json.loads(cpsg_text, parse_constant=int)
        except (ValueError, RecursionError):
            cpsg_report_error = cpsg_parse_error
            cpsg_report = None
    # INTENT: Iterative sweep over the pair-list tree (no recursion, so depth cannot
    # raise) that refuses a duplicate key and any container nested deeper than 64
    # levels, counting the top-level object as level 1. Under the list hook an object
    # is a list of (key, value) tuples ({} is an empty list); a decoded array never
    # holds a tuple, so every object and array is one list and one level. The sweep
    # also collects every key and string value, so any report text a line prints can
    # be escaped (see the escape table below).
    # REASONING: The two parsers give up at different depths (Python's recursion limit,
    # jsonlite's own), so between those limits one block judged a file the other refused.
    # The cap is CPS-INTAKE's (far above any depth a well-formed report reaches), so the
    # outcome depends on the file, not on the parser or the block.
    cpsg_max_depth = 64
    cpsg_stack = [] if cpsg_report is None else [(cpsg_pairs, 1)]
    while len(cpsg_stack) > 0:
        cpsg_node, cpsg_depth = cpsg_stack.pop()
        if isinstance(cpsg_node, str):
            cpsg_report_strings.add(cpsg_node)
            continue
        if not isinstance(cpsg_node, list):
            continue
        if cpsg_depth > cpsg_max_depth:
            cpsg_report_error = cpsg_parse_error
            cpsg_report = None
            break
        if len(cpsg_node) > 0 and all(isinstance(cpsg_e, tuple) for cpsg_e in cpsg_node):
            if len(set(cpsg_e[0] for cpsg_e in cpsg_node)) != len(cpsg_node):
                cpsg_report_error = cpsg_parse_error
                cpsg_report = None
                break
            cpsg_report_strings.update(cpsg_e[0] for cpsg_e in cpsg_node)
            cpsg_stack.extend((cpsg_e[1], cpsg_depth + 1) for cpsg_e in cpsg_node)
        else:
            cpsg_stack.extend((cpsg_e, cpsg_depth + 1) for cpsg_e in cpsg_node)
if cpsg_report is not None and not isinstance(cpsg_report, dict):
    cpsg_report_error = "report parsed, but its top level is not a JSON object"
    cpsg_report = None

cpsg_syn = None
cpsg_syn_error = None
if synthetic_path is None:
    cpsg_syn_error = "synthetic_path is not set — generation produced no file"
elif not Path(synthetic_path).is_file():
    cpsg_syn_error = f"no file at synthetic_path '{synthetic_path}'"
else:
    # INTENT: A parquet that repeats a column name is refused as unreadable, before
    # polars reads it.
    # REASONING: polars keeps only one of the repeated columns and reads the file
    # without complaint, while the R block (arrow) sees every column and refuses it —
    # so the two languages would otherwise validate two different frames. The raw
    # schema keeps every stored name, so a repeat is visible there.
    try:
        cpsg_raw_names = pq.read_schema(synthetic_path).names
        if len(set(cpsg_raw_names)) == len(cpsg_raw_names):
            cpsg_syn = pl.read_parquet(synthetic_path)
    except Exception:
        cpsg_syn = None
    if cpsg_syn is None:
        cpsg_syn_error = "the synthetic parquet did not read (reader message withheld: the two readers word it differently)"

# INTENT: Classify every synthetic column once by its stored type, into the classes the
# R block derives from the arrow schema, so both languages agree on which comparisons a
# column can take part in.
# REASONING: text = a string column; text_dict = a dictionary-encoded string column
# (polars Categorical / Enum, an R factor); integer = 8- to 64-bit signed or unsigned;
# float = 32- or 64-bit; boolean. Every other stored type (decimal, half float, date,
# time, timestamp, duration, binary, nested, null) is "other": the two readers disagree
# on its values — R reads a half float as its raw bits and a decimal as a double — so no
# check compares the values of an "other" column, and a check that must is a [FAIL].
cpsg_class = {}
cpsg_int_types = (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
if cpsg_syn is not None:
    for cpsg_c, cpsg_dt in cpsg_syn.schema.items():
        if cpsg_dt == pl.String:
            cpsg_class[cpsg_c] = "text"
        elif cpsg_dt.base_type() in (pl.Categorical, pl.Enum):
            cpsg_class[cpsg_c] = "text_dict"
        elif cpsg_dt.base_type() in cpsg_int_types:
            cpsg_class[cpsg_c] = "integer"
        elif cpsg_dt.base_type() in (pl.Float32, pl.Float64):
            cpsg_class[cpsg_c] = "float"
        elif cpsg_dt == pl.Boolean:
            cpsg_class[cpsg_c] = "boolean"
        else:
            cpsg_class[cpsg_c] = "other"
# INTENT: The columns whose values cannot be compared with released labels as text: an
# "other" column, and an integer column holding a magnitude of 2^53 or more (R reads a
# large 64-bit integer as a double, so its text would no longer be exact).
cpsg_untextable = set()
for cpsg_c, cpsg_k in cpsg_class.items():
    if cpsg_k == "other" or (cpsg_k == "integer" and (cpsg_syn[cpsg_c].cast(pl.Float64).abs() >= 2.0 ** 53).any() is True):
        cpsg_untextable.add(cpsg_c)
cpsg_untextable_msg = "holds values outside the text-comparable types (string, categorical, integer below 2^53, float, boolean)"

# INTENT: Escape every report- or frame-derived string before it reaches an outcome line,
# identically in both languages: a character outside printable ASCII (0x20-0x7E) prints
# as \uXXXX in lowercase hex, and one above U+FFFF as its UTF-16 surrogate pair.
# REASONING: A column name or key carrying a newline or control character could otherwise
# forge an extra outcome line, and a non-ASCII one could fail the write on a console that
# cannot encode it. The table covers every key and string value of the parsed report and
# every synthetic column name, so each print site looks its text up in it.
cpsg_esc_src = set(cpsg_report_strings)
if cpsg_syn is not None:
    cpsg_esc_src.update(cpsg_syn.columns)
cpsg_esc = {cpsg_s: "".join(cpsg_ch if " " <= cpsg_ch <= "~" else (
    "\\u%04x" % ord(cpsg_ch) if ord(cpsg_ch) < 0x10000 else "\\u%04x\\u%04x" % (
        0xD800 + ((ord(cpsg_ch) - 0x10000) >> 10), 0xDC00 + ((ord(cpsg_ch) - 0x10000) & 0x3FF)))
    for cpsg_ch in cpsg_s) for cpsg_s in cpsg_esc_src}

# INTENT: One numeric model for both languages, shared with CPS-INTAKE. A JSON number
# is usable only when it is finite and |v| < 2^53 — the profiler refuses larger
# magnitudes, every such value is exact in a double, and a token within the 64-character
# parse cap can still exceed 2^53, which jsonlite rounds where Python keeps an exact
# int. Whole numbers are compared by value (40 and 40.0 agree), because JSON does not
# type them apart.
# ASSUMES: each test below puts the isinstance check first and the range check
# before int(), so a string, a list, inf or NaN never reaches `<` or int().
cpsg_max_exact = 2 ** 53

cpsg_columns = None
cpsg_columns_unusable = 0
cpsg_row_count = None
cpsg_relationships = None
cpsg_report_tier = None
if cpsg_report is not None:
    if isinstance(cpsg_report.get("columns"), list):
        cpsg_columns = [c for c in cpsg_report["columns"] if isinstance(c, dict)]
        cpsg_columns_unusable = len(cpsg_report["columns"]) - len(cpsg_columns)
    if isinstance(cpsg_report.get("dataset"), dict):
        cpsg_row_count = cpsg_report["dataset"].get("row_count")
    if isinstance(cpsg_report.get("relationships"), dict):
        cpsg_relationships = cpsg_report["relationships"]
    if isinstance(cpsg_report.get("settings"), dict):
        cpsg_report_tier = cpsg_report["settings"].get("tier")
# INTENT: A role counts only as the exact JSON string and an identifier flag only as
# JSON true, so a list-valued role can never satisfy `==` (the R block tests the same).
cpsg_cat_cols = [] if cpsg_columns is None else [c for c in cpsg_columns if c.get("role") == "categorical"]
cpsg_num_cols = [] if cpsg_columns is None else [c for c in cpsg_columns if c.get("role") == "numeric"]
cpsg_id_cols = [] if cpsg_columns is None else [c for c in cpsg_columns
                                                if c.get("role") == "identifier" or c.get("is_identifier") is True]
cpsg_inputs_error = cpsg_report_error if cpsg_report_error is not None else cpsg_syn_error

# INTENT: Resolve the tier whose release rules apply. Config `tier` is the tier the
# report was produced at (its settings.tier), so tiers 1-3 are the config value; at
# tier 4 (local synthesis, imported here) the profile report's own settings.tier
# governs which blocks were released, so a T4 import is held to exactly what crossed.
# REASONING: A config tier copied from elsewhere (the approved tier CPS-INTAKE takes,
# say) would change which blocks are expected: a tier 2 report checked at tier 3 reads
# as a missing pearson block. So correlations_within_tolerance, the one check whose
# outcome the tier decides, fails when a configured 1-3 differs from a whole-number
# 1-3 the report declares.
cpsg_tier_ok = not isinstance(tier, bool) and tier in (1, 2, 3, 4)
cpsg_report_tier_ok = not isinstance(cpsg_report_tier, bool) and cpsg_report_tier in (1, 2, 3)
cpsg_release_tier = None
if cpsg_tier_ok and tier != 4:
    cpsg_release_tier = int(tier)
elif cpsg_tier_ok and cpsg_report_tier_ok:
    cpsg_release_tier = int(cpsg_report_tier)
if cpsg_release_tier is not None:
    cpsg_tier_label = str(cpsg_release_tier)
elif tier is None:
    cpsg_tier_label = "unrecorded"
elif cpsg_tier_ok:
    cpsg_tier_label = "4 (report tier unrecorded)"
else:
    cpsg_tier_label = "invalid"

# INTENT: Validate every categorical record's released level set once, so the four
# checks that read it agree on what is usable and none can raise on a bad entry.
# REASONING: A level entry is usable only as {value: <string>, count: <whole number
# >= 0>} — the profiler's own shape. Anything else is wrong-typed evidence: the
# entry is named by its index, never by its label or count, and every check that
# needs it reports [NOT VERIFIED] instead of a TypeError (null count) or an
# unhashable-key crash (list label).
cpsg_cat_entries = []
for cpsg_col in cpsg_cat_cols:
    cpsg_name = cpsg_col.get("name")
    cpsg_blk = cpsg_col.get("categorical")
    cpsg_entry = {"name": cpsg_name if isinstance(cpsg_name, str) else None, "problem": None,
                  "levels": [], "n": None, "binned": None}
    if not isinstance(cpsg_name, str):
        cpsg_entry["problem"] = "a categorical column record carries no string name"
    elif not isinstance(cpsg_blk, dict) or not isinstance(cpsg_blk.get("levels"), list):
        cpsg_entry["problem"] = f"column '{cpsg_esc[cpsg_name]}' declares role categorical but has no levels array to compare against"
    if isinstance(cpsg_blk, dict) and isinstance(cpsg_blk.get("levels"), list):
        for cpsg_i, cpsg_lv in enumerate(cpsg_blk["levels"]):
            cpsg_cnt = cpsg_lv.get("count") if isinstance(cpsg_lv, dict) else None
            if (isinstance(cpsg_lv, dict) and isinstance(cpsg_lv.get("value"), str)
                    and isinstance(cpsg_cnt, (int, float)) and not isinstance(cpsg_cnt, bool)
                    and 0 <= cpsg_cnt < cpsg_max_exact and cpsg_cnt == int(cpsg_cnt)):
                cpsg_entry["levels"].append((cpsg_lv["value"], int(cpsg_cnt)))
            elif cpsg_entry["problem"] is None:
                cpsg_entry["problem"] = f"column '{cpsg_esc[cpsg_name]}' level index {cpsg_i} is not a string label with a whole-number count"
        cpsg_x = cpsg_blk.get("n")
        if (isinstance(cpsg_x, (int, float)) and not isinstance(cpsg_x, bool)
                and 0 < cpsg_x < cpsg_max_exact and cpsg_x == int(cpsg_x)):
            cpsg_entry["n"] = int(cpsg_x)
        cpsg_x = cpsg_blk.get("n_levels_binned")
        if (isinstance(cpsg_x, (int, float)) and not isinstance(cpsg_x, bool)
                and 0 <= cpsg_x < cpsg_max_exact and cpsg_x == int(cpsg_x)):
            cpsg_entry["binned"] = int(cpsg_x)
    cpsg_cat_entries.append(cpsg_entry)

# INTENT: Reduce every synthetic column a check compares with released labels to one
# canonical text per value, with its count — identical in both languages and matching
# the labels both profilers write.
# REASONING: Both profiler templates write a level label as text (Python: pandas
# astype(str); R: as.character()). A string or categorical value compares as written.
# A whole-number value — integer or float — is integer text, so 1, 1.0 and the R
# template's "1" agree and -0 is "0"; any other finite float is %.17g text and an
# infinity is inf / -inf; NaN counts as missing, as in the missingness check and R's
# is.na(). A boolean is true / false, and a released label is compared with it
# case-insensitively, so the Python template's "True" and the R template's "TRUE" both
# match. The R block builds the same text with sprintf(), which shares this printf
# format, so the two blocks compare the same strings.
cpsg_text_counts = {}
cpsg_text_names = set(e["name"] for e in cpsg_cat_entries if e["name"] is not None)
cpsg_text_names.update(c.get("name") for c in cpsg_id_cols if isinstance(c.get("name"), str))
for cpsg_name in sorted(cpsg_text_names):
    if cpsg_syn is None or cpsg_name not in cpsg_syn.columns or cpsg_name in cpsg_untextable:
        continue
    cpsg_k = cpsg_class[cpsg_name]
    cpsg_series = cpsg_syn[cpsg_name].alias("cpsg_v")
    if cpsg_k == "float":
        cpsg_series = cpsg_series.cast(pl.Float64).drop_nulls().drop_nans()
    elif cpsg_k == "text_dict":
        cpsg_series = cpsg_series.cast(pl.String).drop_nulls()
    else:
        cpsg_series = cpsg_series.drop_nulls()
    # ASSUMES: value_counts() row order is NOT stable across calls, so the value column
    # and the count column come from the SAME frame.
    cpsg_vc = cpsg_series.value_counts()
    cpsg_raw = cpsg_vc["cpsg_v"].to_list()
    if cpsg_k == "integer":
        cpsg_canon = ["%d" % cpsg_v for cpsg_v in cpsg_raw]
    elif cpsg_k == "float":
        cpsg_canon = [("%.0f" % (cpsg_v + 0.0)) if math.isfinite(cpsg_v) and cpsg_v == math.floor(cpsg_v)
                      else ("%.17g" % cpsg_v if math.isfinite(cpsg_v) else ("inf" if cpsg_v > 0 else "-inf"))
                      for cpsg_v in cpsg_raw]
    elif cpsg_k == "boolean":
        cpsg_canon = ["true" if cpsg_v else "false" for cpsg_v in cpsg_raw]
    else:
        cpsg_canon = cpsg_raw
    cpsg_counts = {}
    for cpsg_t, cpsg_n in zip(cpsg_canon, cpsg_vc["count"].to_list()):
        cpsg_counts[cpsg_t] = cpsg_counts.get(cpsg_t, 0) + cpsg_n
    cpsg_text_counts[cpsg_name] = cpsg_counts

# Check: the synthetic row count equals the count the report declares
if "row_count_matches" in not_applicable:
    print(f"[SKIPPED] row_count_matches: {not_applicable['row_count_matches']}")
    cps_gen["skipped"] += 1
elif "row_count_matches" in cpsg_empty_reason:
    print("[NOT VERIFIED] row_count_matches: declared not_applicable with an empty reason")
    cps_gen["not_verified"] += 1
elif cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] row_count_matches: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
elif not (isinstance(cpsg_row_count, (int, float)) and not isinstance(cpsg_row_count, bool)
          and -cpsg_max_exact < cpsg_row_count < cpsg_max_exact and cpsg_row_count == int(cpsg_row_count)):
    print("[NOT VERIFIED] row_count_matches: dataset.row_count is absent or not a whole number — no target to match")
    cps_gen["not_verified"] += 1
elif cpsg_syn.height != int(cpsg_row_count):
    print(f"[FAIL] row_count_matches: synthetic has {cpsg_syn.height:,} rows, the report declares {int(cpsg_row_count):,}")
    cps_gen["failed"] += 1
else:
    print(f"[PASS] row_count_matches: {cpsg_syn.height:,} synthetic rows == declared row_count {int(cpsg_row_count):,}")
    cps_gen["passed"] += 1

# Check: column set and dtypes match the report's declared schema
if "column_set_and_dtypes" in not_applicable:
    print(f"[SKIPPED] column_set_and_dtypes: {not_applicable['column_set_and_dtypes']}")
    cps_gen["skipped"] += 1
elif "column_set_and_dtypes" in cpsg_empty_reason:
    print("[NOT VERIFIED] column_set_and_dtypes: declared not_applicable with an empty reason")
    cps_gen["not_verified"] += 1
elif cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] column_set_and_dtypes: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
elif cpsg_columns is None or len(cpsg_columns) == 0:
    print("[NOT VERIFIED] column_set_and_dtypes: the report declares no columns to match against")
    cps_gen["not_verified"] += 1
elif cpsg_columns_unusable > 0 or any(not isinstance(c.get("name"), str) for c in cpsg_columns):
    # REASONING: a record with no string name is report evidence of the wrong type —
    # the declared schema it belongs to cannot be matched, so nothing is concluded.
    cpsg_unnamed = cpsg_columns_unusable + sum(1 for c in cpsg_columns if not isinstance(c.get("name"), str))
    print(f"[NOT VERIFIED] column_set_and_dtypes: {cpsg_unnamed} of {cpsg_columns_unusable + len(cpsg_columns)} column records carry no string name — the declared schema cannot be matched")
    cps_gen["not_verified"] += 1
else:
    cpsg_declared_names = [c["name"] for c in cpsg_columns]
    cpsg_missing = sorted(set(cpsg_declared_names) - set(cpsg_syn.columns))
    cpsg_extra = sorted(set(cpsg_syn.columns) - set(cpsg_declared_names))
    cpsg_bad = []
    if len(cpsg_missing) > 0 or len(cpsg_extra) > 0:
        cpsg_bad.append(f"column set differs — missing [{', '.join(cpsg_esc[c] for c in cpsg_missing)}], unexpected [{', '.join(cpsg_esc[c] for c in cpsg_extra)}]")
    else:
        # REASONING: the stored type is judged by its class, the one both languages
        # derive. "string" needs a plain string column; "double" an integer or float
        # column; "integer" an integer column, or a float column whose values are all
        # whole — the claim the R block can make after arrow's round trip. A declared
        # dtype is never echoed: it is free text from the report.
        for cpsg_col in cpsg_columns:
            cpsg_name = cpsg_col["name"]
            cpsg_dtype = cpsg_col.get("dtype")
            cpsg_k = cpsg_class[cpsg_name]
            if not isinstance(cpsg_dtype, str) or cpsg_dtype not in ("integer", "double", "string"):
                cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' declares an unrecognized dtype")
            elif cpsg_dtype == "integer":
                cpsg_whole = cpsg_k == "integer"
                if cpsg_k == "float":
                    cpsg_vals = cpsg_syn[cpsg_name].cast(pl.Float64).drop_nulls().drop_nans()
                    cpsg_whole = bool(((cpsg_vals == cpsg_vals.floor()) & cpsg_vals.is_finite()).all())
                if not cpsg_whole:
                    cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' is not whole-numeric, the report declares integer")
            elif cpsg_dtype == "double" and cpsg_k not in ("integer", "float"):
                cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' is not numeric, the report declares double")
            elif cpsg_dtype == "string" and cpsg_k != "text":
                cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' is not a string column, the report declares string")
    if len(cpsg_bad) > 0:
        print(f"[FAIL] column_set_and_dtypes: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
        cps_gen["failed"] += 1
    else:
        print(f"[PASS] column_set_and_dtypes: {len(cpsg_columns)} declared columns, names and dtypes all matched")
        cps_gen["passed"] += 1

# Check: reproduced numeric percentiles sit within tolerance of the released grid
# REASONING: A withheld, all-missing or constant numeric block released no percentile
# grid, so it is not a miss — it is nothing to compare. A numeric column with no
# numeric block at all, or a grid value that is not a usable number, is missing
# evidence and is counted, never silently passed over. Tolerance is relative with a
# floor of 1.0 so a target near zero does not demand impossible precision.
if "numeric_marginals_within_tolerance" in not_applicable:
    print(f"[SKIPPED] numeric_marginals_within_tolerance: {not_applicable['numeric_marginals_within_tolerance']}")
    cps_gen["skipped"] += 1
elif "numeric_marginals_within_tolerance" in cpsg_empty_reason:
    print("[NOT VERIFIED] numeric_marginals_within_tolerance: declared not_applicable with an empty reason")
    cps_gen["not_verified"] += 1
elif cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] numeric_marginals_within_tolerance: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
else:
    cpsg_targets = []
    cpsg_absent = []
    for cpsg_col in cpsg_num_cols:
        cpsg_name = cpsg_col.get("name")
        cpsg_blk = cpsg_col.get("numeric")
        if not isinstance(cpsg_name, str):
            cpsg_absent.append("a numeric column record carries no string name")
        elif not isinstance(cpsg_blk, dict):
            cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' declares role numeric but has no numeric block")
        elif "percentiles" in cpsg_blk and not isinstance(cpsg_blk["percentiles"], dict):
            cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' carries a percentiles field that is not an object")
        elif "percentiles" in cpsg_blk:
            cpsg_targets.append((cpsg_name, cpsg_blk["percentiles"]))
    if len(cpsg_targets) == 0 and len(cpsg_absent) == 0:
        print(f"[SKIPPED] numeric_marginals_within_tolerance: report declares 0 numeric distribution targets at tier {cpsg_tier_label}")
        cps_gen["skipped"] += 1
    else:
        cpsg_compared = 0
        cpsg_off = []
        cpsg_bad = []
        # INTENT: The grid's keys are a closed set fixed by the profiling spec; parse
        # nothing that is not in it.
        # REASONING: `float(key[1:])` on an unvetted key either raises (Python) or
        # coerces to a silent NaN/NA (R) — both misreport a malformed report as a
        # tooling failure. Naming the key is the finding.
        # ASSUMES: the released grid is the spec's ordered percentile set (the small-n
        # shape releases the p25/p50/p75 subset of it). Quantiles use linear
        # interpolation over the non-null, non-NaN values — R's default type 7 — so
        # both languages compute the same deviation and print the same line.
        cpsg_pct_names = ("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
        for cpsg_name, cpsg_grid in cpsg_targets:
            if cpsg_name not in cpsg_syn.columns:
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' has a released grid but is absent from the synthetic frame")
                continue
            # REASONING: the synthetic column is the thing under validation, so one
            # outside the integer and float classes is a [FAIL] — quantile() on it would
            # raise, or (decimal, half float) the two readers would see different values.
            if cpsg_class[cpsg_name] not in ("integer", "float"):
                cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' is not numeric in the synthetic frame — its released percentiles cannot be reproduced")
                continue
            cpsg_vals = cpsg_syn[cpsg_name].cast(pl.Float64).drop_nulls().drop_nans()
            if cpsg_vals.len() == 0:
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' has a released grid but is entirely null in the synthetic frame")
                continue
            for cpsg_k, cpsg_target in cpsg_grid.items():
                if cpsg_k not in cpsg_pct_names:
                    cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' percentile grid carries unrecognized key '{cpsg_esc[cpsg_k]}'")
                    continue
                if not (isinstance(cpsg_target, (int, float)) and not isinstance(cpsg_target, bool)
                        and -cpsg_max_exact < cpsg_target < cpsg_max_exact):
                    cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' percentile {cpsg_k} target is not a usable number")
                    continue
                cpsg_obs = cpsg_vals.quantile(float(cpsg_k[1:]) / 100.0, interpolation="linear")
                if cpsg_obs is None or not math.isfinite(cpsg_obs):
                    cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' quantile {cpsg_k} came back empty")
                    continue
                cpsg_compared += 1
                if abs(cpsg_obs - cpsg_target) > numeric_tolerance * max(abs(cpsg_target), 1.0):
                    cpsg_off.append(f"column '{cpsg_esc[cpsg_name]}' {cpsg_k} deviates by {abs(cpsg_obs - cpsg_target):.4g}")
        if len(cpsg_bad) > 0:
            print(f"[FAIL] numeric_marginals_within_tolerance: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
            cps_gen["failed"] += 1
        elif len(cpsg_absent) > 0:
            print(f"[NOT VERIFIED] numeric_marginals_within_tolerance: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
            cps_gen["not_verified"] += 1
        elif cpsg_compared == 0:
            # REASONING: a grid that yielded no comparison verified nothing; printing
            # [PASS] over zero comparisons is the empty-evidence pass this block exists
            # to refuse.
            print(f"[NOT VERIFIED] numeric_marginals_within_tolerance: {len(cpsg_targets)} columns released a percentile grid but 0 percentile comparisons were made")
            cps_gen["not_verified"] += 1
        elif len(cpsg_off) > 0:
            print(f"[WARNING] numeric_marginals_within_tolerance: {len(cpsg_off)} of {cpsg_compared} percentile comparisons outside the {numeric_tolerance * 100:.4g}% relative band — {cpsg_off[0]}")
            cps_gen["warning"] += 1
        else:
            print(f"[PASS] numeric_marginals_within_tolerance: {len(cpsg_targets)} columns, {cpsg_compared} percentile comparisons, all within the {numeric_tolerance * 100:.4g}% relative band")
            cps_gen["passed"] += 1

# Check: reproduced categorical proportions sit within tolerance of the released levels
if "categorical_proportions_within_tolerance" in not_applicable:
    print(f"[SKIPPED] categorical_proportions_within_tolerance: {not_applicable['categorical_proportions_within_tolerance']}")
    cps_gen["skipped"] += 1
elif "categorical_proportions_within_tolerance" in cpsg_empty_reason:
    print("[NOT VERIFIED] categorical_proportions_within_tolerance: declared not_applicable with an empty reason")
    cps_gen["not_verified"] += 1
elif cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] categorical_proportions_within_tolerance: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
else:
    # INTENT: A record whose level set is unusable is counted as missing evidence; a
    # usable but empty level set (every level suppressed) released no target.
    cpsg_targets = [e for e in cpsg_cat_entries if e["problem"] is None and len(e["levels"]) > 0]
    cpsg_absent = [e["problem"] for e in cpsg_cat_entries if e["problem"] is not None]
    if len(cpsg_targets) == 0 and len(cpsg_absent) == 0:
        print(f"[SKIPPED] categorical_proportions_within_tolerance: report declares 0 categorical level targets at tier {cpsg_tier_label}")
        cps_gen["skipped"] += 1
    else:
        cpsg_compared = 0
        cpsg_off = []
        cpsg_bad = []
        for cpsg_entry in cpsg_targets:
            cpsg_name = cpsg_entry["name"]
            if cpsg_name not in cpsg_syn.columns:
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' has released levels but is absent from the synthetic frame")
                continue
            if cpsg_name in cpsg_untextable:
                cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' {cpsg_untextable_msg} — its levels cannot be compared")
                continue
            cpsg_denom = cpsg_entry["n"]
            if cpsg_denom is None:
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' categorical block carries no positive n to form proportions from")
                continue
            # ASSUMES: levels are compared through the canonical text form above, which
            # the R block builds identically, so the two blocks agree on what matches.
            cpsg_counts = cpsg_text_counts[cpsg_name]
            cpsg_obs_n = sum(cpsg_counts.values())
            if cpsg_obs_n == 0:
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' is entirely null in the synthetic frame")
                continue
            cpsg_bool = cpsg_class[cpsg_name] == "boolean"
            for cpsg_value, cpsg_count in cpsg_entry["levels"]:
                cpsg_key = cpsg_value.lower() if cpsg_bool and cpsg_value.lower() in ("true", "false") else cpsg_value
                cpsg_target = cpsg_count / cpsg_denom
                cpsg_obs = cpsg_counts.get(cpsg_key, 0) / cpsg_obs_n
                cpsg_compared += 1
                if abs(cpsg_obs - cpsg_target) > proportion_tolerance:
                    cpsg_off.append(f"column '{cpsg_esc[cpsg_name]}' has a level proportion off by {abs(cpsg_obs - cpsg_target):.4f}")
        if len(cpsg_bad) > 0:
            print(f"[FAIL] categorical_proportions_within_tolerance: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
            cps_gen["failed"] += 1
        elif len(cpsg_absent) > 0:
            print(f"[NOT VERIFIED] categorical_proportions_within_tolerance: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
            cps_gen["not_verified"] += 1
        elif cpsg_compared == 0:
            print(f"[NOT VERIFIED] categorical_proportions_within_tolerance: {len(cpsg_targets)} columns released levels but 0 level proportions were compared")
            cps_gen["not_verified"] += 1
        elif len(cpsg_off) > 0:
            print(f"[WARNING] categorical_proportions_within_tolerance: {len(cpsg_off)} of {cpsg_compared} level proportions outside +/-{proportion_tolerance:.4g} — {cpsg_off[0]}")
            cps_gen["warning"] += 1
        else:
            print(f"[PASS] categorical_proportions_within_tolerance: {len(cpsg_targets)} columns, {cpsg_compared} level proportions, all within +/-{proportion_tolerance:.4g}")
            cps_gen["passed"] += 1

# Check: pooled/suppressed categories were not re-invented (NON-DECLARABLE)
# REASONING: Suppression removed levels the generator never saw. If the synthetic
# frame carries more distinct levels than the report released, or dropped the
# __OTHER__ bucket the report released for the pooled ones, generation has filled the
# gap with something — and a reader cannot tell invented from released. __OTHER__ is
# required only where the report released it. Where every source level was pooled
# away (levels: [] with n_levels_binned > 0, the profiler's shape when 0 < n < the
# threshold), the literal __OTHER__ is the one level a generator may still emit: it
# names the withheld pool and carries no source value, so the column's released
# non-missing count can be reproduced without inventing a label.
if cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] suppressed_categories_absent: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
elif len(cpsg_cat_cols) == 0:
    print(f"[PASS] suppressed_categories_absent: 0 categorical columns declared at tier {cpsg_tier_label}, 0 pooled buckets to preserve")
    cps_gen["passed"] += 1
else:
    cpsg_bad = []
    cpsg_absent = []
    cpsg_pools = 0
    cpsg_checked = 0
    for cpsg_entry in cpsg_cat_entries:
        cpsg_name = cpsg_entry["name"]
        if cpsg_entry["problem"] is not None:
            cpsg_absent.append(cpsg_entry["problem"])
            continue
        if cpsg_name not in cpsg_syn.columns:
            cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' has released levels but is absent from the synthetic frame")
            continue
        if cpsg_name in cpsg_untextable:
            cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' {cpsg_untextable_msg} — its levels cannot be compared")
            continue
        # REASONING: whether the generator kept the pool is judged against the
        # report's pool count, so an unusable count is missing evidence, not a pass.
        if cpsg_entry["binned"] is None:
            cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' categorical block carries no whole-number n_levels_binned")
            continue
        cpsg_checked += 1
        cpsg_bool = cpsg_class[cpsg_name] == "boolean"
        cpsg_released = set(cpsg_v.lower() if cpsg_bool and cpsg_v.lower() in ("true", "false") else cpsg_v
                            for cpsg_v, _cpsg_c in cpsg_entry["levels"])
        cpsg_observed = set(cpsg_text_counts[cpsg_name])
        cpsg_pool_only = 1 if len(cpsg_entry["levels"]) == 0 and cpsg_entry["binned"] > 0 else 0
        if len(cpsg_observed) > len(cpsg_released) + cpsg_pool_only:
            cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' carries {len(cpsg_observed)} distinct synthetic levels against {len(cpsg_released)} released")
        if any(cpsg_v == "__OTHER__" for cpsg_v, _cpsg_c in cpsg_entry["levels"]):
            cpsg_pools += 1
            if "__OTHER__" not in cpsg_observed:
                cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' pooled {cpsg_entry['binned']} source levels but the synthetic frame has no __OTHER__ bucket")
    if len(cpsg_bad) > 0:
        print(f"[FAIL] suppressed_categories_absent: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
        cps_gen["failed"] += 1
    elif len(cpsg_absent) > 0:
        print(f"[NOT VERIFIED] suppressed_categories_absent: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
        cps_gen["not_verified"] += 1
    else:
        print(f"[PASS] suppressed_categories_absent: {cpsg_checked} categorical columns examined, {cpsg_pools} pooled buckets preserved, 0 levels added")
        cps_gen["passed"] += 1

# Check: reproduced correlations sit within tolerance of the released matrix
# REASONING: CPS-GEN applies ONE absolute band, `correlation_tolerance`, to every
# released pair. The wider +/-0.20 allowance for binary or low-cardinality pairs is a
# QAS-C reviewer judgement, not a band this block applies or implies. Below tier 3
# nothing is released, so the absence is structural ([SKIPPED]); at tier 3 the spec
# always carries a pearson block, so its absence is missing evidence ([NOT VERIFIED]).
if "correlations_within_tolerance" in not_applicable:
    print(f"[SKIPPED] correlations_within_tolerance: {not_applicable['correlations_within_tolerance']}")
    cps_gen["skipped"] += 1
elif "correlations_within_tolerance" in cpsg_empty_reason:
    print("[NOT VERIFIED] correlations_within_tolerance: declared not_applicable with an empty reason")
    cps_gen["not_verified"] += 1
elif cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] correlations_within_tolerance: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
elif not cpsg_tier_ok:
    print("[NOT VERIFIED] correlations_within_tolerance: tier is not a recorded 1/2/3/4")
    cps_gen["not_verified"] += 1
elif tier != 4 and cpsg_report_tier_ok and int(cpsg_report_tier) != cpsg_release_tier:
    print(f"[FAIL] correlations_within_tolerance: configured tier {cpsg_release_tier} differs from the report's declared tier {int(cpsg_report_tier)}")
    cps_gen["failed"] += 1
elif cpsg_release_tier is None:
    print("[NOT VERIFIED] correlations_within_tolerance: tier 4 import, but the report declares no settings.tier of 1/2/3 — which blocks were released is unknown")
    cps_gen["not_verified"] += 1
elif cpsg_release_tier < 3:
    print(f"[SKIPPED] correlations_within_tolerance: no available correlation matrix at tier {cpsg_tier_label} — nothing was released to reproduce")
    cps_gen["skipped"] += 1
elif not isinstance(cpsg_relationships, dict) or not isinstance(cpsg_relationships.get("pearson"), dict):
    print(f"[NOT VERIFIED] correlations_within_tolerance: the report at {'declared' if tier == 4 else 'configured'} tier {cpsg_tier_label} carries no pearson block — the released correlations cannot be compared")
    cps_gen["not_verified"] += 1
elif cpsg_relationships["pearson"].get("available") is False:
    print(f"[SKIPPED] correlations_within_tolerance: no available correlation matrix at tier {cpsg_tier_label} — nothing was released to reproduce")
    cps_gen["skipped"] += 1
elif cpsg_relationships["pearson"].get("available") is not True:
    print("[NOT VERIFIED] correlations_within_tolerance: the pearson block carries no boolean available flag")
    cps_gen["not_verified"] += 1
else:
    cpsg_blk = cpsg_relationships["pearson"]
    cpsg_names = cpsg_blk.get("columns")
    cpsg_m = cpsg_blk.get("matrix")
    cpsg_off = []
    cpsg_absent = []
    cpsg_bad = []
    cpsg_compared = 0
    if not isinstance(cpsg_names, list) or not all(isinstance(n, str) for n in cpsg_names) or not isinstance(cpsg_m, list):
        cpsg_absent.append("the available pearson block carries no columns/matrix pair")
    # INTENT: Confirm the released matrix is square with dimension == len(columns)
    # before any positional indexing.
    # REASONING: Indexing a short matrix by column position raises IndexError, which
    # aborts the block before the remaining checks report — the single outcome this
    # checkpoint exists to prevent. The shape discrepancy is itself the finding, so it
    # is named (counts only, no coefficients) and the pair loop is skipped.
    elif len(cpsg_m) != len(cpsg_names) or any(not isinstance(cpsg_r, list) or len(cpsg_r) != len(cpsg_names) for cpsg_r in cpsg_m):
        cpsg_dim = max((len(cpsg_r) for cpsg_r in cpsg_m if isinstance(cpsg_r, list)), default=0)
        cpsg_bad.append(f"released pearson block declares {len(cpsg_names)} columns but carries an {len(cpsg_m)}x{cpsg_dim} matrix")
    elif any(n not in cpsg_syn.columns for n in cpsg_names):
        cpsg_absent.append("a correlated column is absent from the synthetic frame")
    elif any(cpsg_class[n] not in ("integer", "float") for n in cpsg_names):
        # REASONING: the synthetic column is under validation, so one outside the
        # integer and float classes is a [FAIL]; polars would silently coerce it and R's
        # cor() would raise.
        cpsg_bad.append(f"column '{cpsg_esc[[n for n in cpsg_names if cpsg_class[n] not in ('integer', 'float')][0]]}' is correlated in the report but not numeric in the synthetic frame")
    else:
        for cpsg_i in range(len(cpsg_names)):
            for cpsg_j in range(cpsg_i + 1, len(cpsg_names)):
                cpsg_target = cpsg_m[cpsg_i][cpsg_j]
                # REASONING: a null or non-number coefficient is wrong-typed evidence.
                if not (isinstance(cpsg_target, (int, float)) and not isinstance(cpsg_target, bool)
                        and -cpsg_max_exact < cpsg_target < cpsg_max_exact):
                    cpsg_absent.append(f"the released pearson matrix carries no usable coefficient for pair ({cpsg_esc[cpsg_names[cpsg_i]]}, {cpsg_esc[cpsg_names[cpsg_j]]})")
                    continue
                # ASSUMES: complete cases only (non-null, non-NaN on both sides), as R's
                # cor(use = "complete.obs") — so the two blocks correlate the same rows.
                cpsg_pair = cpsg_syn.select(pl.col(cpsg_names[cpsg_i]).cast(pl.Float64).alias("cpsg_x"),
                                            pl.col(cpsg_names[cpsg_j]).cast(pl.Float64).alias("cpsg_y"))
                cpsg_pair = cpsg_pair.filter(pl.col("cpsg_x").is_not_null() & pl.col("cpsg_y").is_not_null()
                                             & pl.col("cpsg_x").is_not_nan() & pl.col("cpsg_y").is_not_nan())
                cpsg_obs = None if cpsg_pair.height < 2 else cpsg_pair.select(pl.corr(pl.col("cpsg_x"), pl.col("cpsg_y"))).item()
                if cpsg_obs is None or not math.isfinite(cpsg_obs):
                    cpsg_absent.append(f"the synthetic pair ({cpsg_esc[cpsg_names[cpsg_i]]}, {cpsg_esc[cpsg_names[cpsg_j]]}) has no defined correlation")
                    continue
                cpsg_compared += 1
                if abs(cpsg_obs - cpsg_target) > correlation_tolerance:
                    cpsg_off.append(f"pair ({cpsg_esc[cpsg_names[cpsg_i]]}, {cpsg_esc[cpsg_names[cpsg_j]]}) deviates by {abs(cpsg_obs - cpsg_target):.4f}")
    if len(cpsg_bad) > 0:
        print(f"[FAIL] correlations_within_tolerance: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
        cps_gen["failed"] += 1
    elif len(cpsg_absent) > 0:
        print(f"[NOT VERIFIED] correlations_within_tolerance: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
        cps_gen["not_verified"] += 1
    elif cpsg_compared == 0:
        print(f"[NOT VERIFIED] correlations_within_tolerance: the available pearson block names {len(cpsg_names)} columns but 0 pairs were compared")
        cps_gen["not_verified"] += 1
    elif len(cpsg_off) > 0:
        print(f"[WARNING] correlations_within_tolerance: {len(cpsg_off)} of {cpsg_compared} pairs outside the correlation_tolerance band +/-{correlation_tolerance:.4g} — {cpsg_off[0]}")
        cps_gen["warning"] += 1
    else:
        print(f"[PASS] correlations_within_tolerance: {cpsg_compared} released pairs reproduced within the correlation_tolerance band +/-{correlation_tolerance:.4g}")
        cps_gen["passed"] += 1

# Check: every synthetic level lies inside the released level set (NON-DECLARABLE)
# REASONING: compared through the canonical text form. The literal __OTHER__ is also
# admissible where every source level was pooled away (levels: [] with n_levels_binned
# > 0), for the reason given at suppressed_categories_absent.
if cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] synthetic_levels_within_released_levels: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
elif len(cpsg_cat_cols) == 0:
    print(f"[PASS] synthetic_levels_within_released_levels: 0 categorical columns declared at tier {cpsg_tier_label}, 0 level sets to police")
    cps_gen["passed"] += 1
else:
    cpsg_bad = []
    cpsg_absent = []
    cpsg_checked = 0
    cpsg_levels_seen = 0
    for cpsg_entry in cpsg_cat_entries:
        cpsg_name = cpsg_entry["name"]
        if cpsg_entry["problem"] is not None:
            cpsg_absent.append(cpsg_entry["problem"])
            continue
        if cpsg_name not in cpsg_syn.columns:
            cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' is absent from the synthetic frame")
            continue
        if cpsg_name in cpsg_untextable:
            cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' {cpsg_untextable_msg} — its levels cannot be compared")
            continue
        cpsg_checked += 1
        cpsg_bool = cpsg_class[cpsg_name] == "boolean"
        cpsg_released = set(cpsg_v.lower() if cpsg_bool and cpsg_v.lower() in ("true", "false") else cpsg_v
                            for cpsg_v, _cpsg_c in cpsg_entry["levels"])
        if len(cpsg_entry["levels"]) == 0 and cpsg_entry["binned"] is not None and cpsg_entry["binned"] > 0:
            cpsg_released.add("__OTHER__")
        cpsg_observed = list(cpsg_text_counts[cpsg_name])
        cpsg_levels_seen += len(cpsg_observed)
        cpsg_outside = [v for v in cpsg_observed if v not in cpsg_released]
        if len(cpsg_outside) > 0:
            cpsg_bad.append(f"column '{cpsg_esc[cpsg_name]}' carries {len(cpsg_outside)} synthetic levels outside the released set")
    if len(cpsg_bad) > 0:
        print(f"[FAIL] synthetic_levels_within_released_levels: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
        cps_gen["failed"] += 1
    elif len(cpsg_absent) > 0:
        print(f"[NOT VERIFIED] synthetic_levels_within_released_levels: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
        cps_gen["not_verified"] += 1
    else:
        print(f"[PASS] synthetic_levels_within_released_levels: {cpsg_checked} columns, {cpsg_levels_seen} distinct synthetic levels, all inside the released sets")
        cps_gen["passed"] += 1

# Check: synthetic identifiers are structurally shaped but value-free (NON-DECLARABLE)
if cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] identifier_columns_value_free: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
elif len(cpsg_id_cols) == 0:
    print(f"[PASS] identifier_columns_value_free: 0 identifier columns declared at tier {cpsg_tier_label}")
    cps_gen["passed"] += 1
else:
    # ASSUMES: a released label is a string (the profiler's own shape); an entry that
    # is not one cannot equal a synthetic identifier's canonical text, so it adds nothing.
    # A boolean identifier column is compared with the labels case-insensitively, as
    # the categorical checks compare a boolean column.
    cpsg_released_values = set()
    for cpsg_entry in cpsg_cat_entries:
        for cpsg_v, _cpsg_c in cpsg_entry["levels"]:
            cpsg_released_values.add(cpsg_v)
    cpsg_released_bool = set(cpsg_v.lower() if cpsg_v.lower() in ("true", "false") else cpsg_v for cpsg_v in cpsg_released_values)
    cpsg_bad = []
    cpsg_absent = []
    cpsg_checked = 0
    for cpsg_col in cpsg_id_cols:
        cpsg_name = cpsg_col.get("name")
        if not isinstance(cpsg_name, str):
            cpsg_absent.append("an identifier column record carries no string name")
            continue
        if cpsg_name not in cpsg_syn.columns:
            cpsg_absent.append(f"identifier column '{cpsg_esc[cpsg_name]}' is absent from the synthetic frame")
            continue
        if cpsg_name in cpsg_untextable:
            cpsg_bad.append(f"identifier column '{cpsg_esc[cpsg_name]}' {cpsg_untextable_msg}")
            continue
        cpsg_checked += 1
        cpsg_counts = cpsg_text_counts[cpsg_name]
        if any(cpsg_n > 1 for cpsg_n in cpsg_counts.values()):
            cpsg_bad.append(f"identifier column '{cpsg_esc[cpsg_name]}' is not unique across rows")
        cpsg_against = cpsg_released_bool if cpsg_class[cpsg_name] == "boolean" else cpsg_released_values
        if len(set(cpsg_counts) & cpsg_against) > 0:
            cpsg_bad.append(f"identifier column '{cpsg_esc[cpsg_name]}' reuses a value from a released level set")
    if len(cpsg_bad) > 0:
        print(f"[FAIL] identifier_columns_value_free: {cpsg_bad[0]}" + (f" (+{len(cpsg_bad) - 1} more)" if len(cpsg_bad) > 1 else ""))
        cps_gen["failed"] += 1
    elif len(cpsg_absent) > 0:
        print(f"[NOT VERIFIED] identifier_columns_value_free: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
        cps_gen["not_verified"] += 1
    else:
        print(f"[PASS] identifier_columns_value_free: {cpsg_checked} identifier columns, all-unique scaffolds, 0 released values reused")
        cps_gen["passed"] += 1

# Check: per-column null rates reproduce the reported missingness
if "missingness_within_tolerance" in not_applicable:
    print(f"[SKIPPED] missingness_within_tolerance: {not_applicable['missingness_within_tolerance']}")
    cps_gen["skipped"] += 1
elif "missingness_within_tolerance" in cpsg_empty_reason:
    print("[NOT VERIFIED] missingness_within_tolerance: declared not_applicable with an empty reason")
    cps_gen["not_verified"] += 1
elif cpsg_syn is None or cpsg_report is None:
    print(f"[NOT VERIFIED] missingness_within_tolerance: {cpsg_inputs_error}")
    cps_gen["not_verified"] += 1
else:
    cpsg_targets = [] if cpsg_columns is None else [c for c in cpsg_columns if "missing_rate" in c]
    if len(cpsg_targets) == 0:
        print(f"[SKIPPED] missingness_within_tolerance: report declares 0 missingness targets at tier {cpsg_tier_label}")
        cps_gen["skipped"] += 1
    else:
        cpsg_off = []
        cpsg_absent = []
        cpsg_compared = 0
        for cpsg_col in cpsg_targets:
            cpsg_name = cpsg_col.get("name")
            cpsg_target = cpsg_col.get("missing_rate")
            if not isinstance(cpsg_name, str):
                cpsg_absent.append("a column record with a missingness target carries no string name")
                continue
            if cpsg_name not in cpsg_syn.columns:
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' has a missingness target but is absent from the synthetic frame")
                continue
            if not (isinstance(cpsg_target, (int, float)) and not isinstance(cpsg_target, bool)
                    and -cpsg_max_exact < cpsg_target < cpsg_max_exact):
                cpsg_absent.append(f"column '{cpsg_esc[cpsg_name]}' carries a non-numeric missing_rate target")
                continue
            cpsg_compared += 1
            # ASSUMES: NaN is missing in a float column, as in the profiling spec and in
            # R's is.na(); the null count is the stored one, which the R block reads from
            # arrow, so the two agree for every column class.
            cpsg_n_missing = cpsg_syn[cpsg_name].null_count()
            if cpsg_class[cpsg_name] == "float":
                cpsg_n_missing += int(cpsg_syn[cpsg_name].is_nan().sum())
            cpsg_obs = cpsg_n_missing / cpsg_syn.height if cpsg_syn.height > 0 else 0.0
            if abs(cpsg_obs - cpsg_target) > missingness_tolerance:
                cpsg_off.append(f"column '{cpsg_esc[cpsg_name]}' null rate is off by {abs(cpsg_obs - cpsg_target):.4f}")
        if len(cpsg_absent) > 0:
            print(f"[NOT VERIFIED] missingness_within_tolerance: {cpsg_absent[0]}" + (f" (+{len(cpsg_absent) - 1} more)" if len(cpsg_absent) > 1 else ""))
            cps_gen["not_verified"] += 1
        elif len(cpsg_off) > 0:
            print(f"[WARNING] missingness_within_tolerance: {len(cpsg_off)} of {cpsg_compared} columns outside +/-{missingness_tolerance:.4g} — {cpsg_off[0]}")
            cps_gen["warning"] += 1
        else:
            print(f"[PASS] missingness_within_tolerance: {cpsg_compared} columns, all null rates within +/-{missingness_tolerance:.4g} of the reported rate")
            cps_gen["passed"] += 1

# Check: the generation seed is recorded and printed (NON-DECLARABLE)
# REASONING: Reproducibility is not a fidelity nicety here — without the seed the
# synthetic frame cannot be regenerated, so nothing downstream can be re-derived.
# The one exception is a tier 4 import whose seed the user's own generation never
# recorded: the researcher may authorize it at the gate, `seed_exception` then
# points at that authorization in STATE, and the outcome is a [WARNING] — never a
# [PASS]. The pointer's value is never printed. With neither a seed nor an exception
# the outcome is [FAIL]. The check reads only the config, so it runs whether or not
# the report parsed.
# ASSUMES: seed_exception counts as set only when it is a string with visible
# content (blank under the same Unicode whitespace set as the not_applicable
# reasons); anything else is no authorization and leaves the seed rule in force.
cpsg_exception_set = isinstance(seed_exception, str) and seed_exception.strip() != ""
cpsg_seed_ok = (isinstance(seed, (int, float)) and not isinstance(seed, bool)
                and -cpsg_max_exact < seed < cpsg_max_exact and seed == int(seed))
if cpsg_exception_set and seed is not None:
    print("[FAIL] seed_recorded: seed and seed_exception are both set — record one")
    cps_gen["failed"] += 1
elif cpsg_exception_set and not (cpsg_tier_ok and tier == 4):
    print("[FAIL] seed_recorded: seed_exception is honored only at tier 4")
    cps_gen["failed"] += 1
elif cpsg_exception_set:
    print("[WARNING] seed_recorded: tier 4 import with no recorded seed — researcher-authorized non-reproducible T4 exception (authorization recorded in STATE)")
    cps_gen["warning"] += 1
elif not cpsg_seed_ok:
    print("[FAIL] seed_recorded: the generation seed is not an integer recorded in this script's config")
    cps_gen["failed"] += 1
else:
    print(f"[PASS] seed_recorded: generation seed {int(seed)} present in the script config and printed to the log")
    cps_gen["passed"] += 1

# Count line, then verdict derived from the counts
cpsg_checks_run = cps_gen["passed"] + cps_gen["warning"] + cps_gen["failed"]
if cps_gen["failed"] > 0 or cps_gen["not_verified"] > 0 or cpsg_checks_run == 0:
    cpsg_verdict = "FAILED"
elif cps_gen["warning"] > 0:
    cpsg_verdict = "PASSED WITH WARNINGS"
else:
    cpsg_verdict = "PASSED"

print(f"\nChecks: {cps_gen['passed']} passed, {cps_gen['warning']} warnings, {cps_gen['failed']} failed, {cps_gen['not_verified']} not verified, {cps_gen['skipped']} skipped")
print(f"CPS-GEN VALIDATION: {cpsg_verdict}")
print("=" * 60)

if cpsg_verdict == "FAILED":
    raise ValueError("CPS-GEN FAILED - see details above")
```

**R:**
```r
# --- CPS-GEN Validation ---
# INTENT: Verify the generated synthetic frame matches the profile it was built
# from and fabricates nothing the report withheld.
# REASONING: Same contract as the Python block. The synthetic parquet is read as an
# arrow Table and each column is classified from its arrow type, so both languages
# agree on which comparisons a column can take part in; arrow's round trip widens the
# stored integer types, so the dtype check tests "integer, or float and whole" for a
# declared integer rather than an exact storage width — an honest weaker claim, stated
# here rather than hidden in a passing line, which the Python block applies too. Every
# outcome line is byte-identical to the Python block's on the same inputs, and no
# input stops the block before its count line and verdict: every `if ()` below is
# handed a single TRUE/FALSE, never NULL, NA or a length-0 value.
# ASSUMES: synthetic_path / report_path / seed / seed_exception / tier / the
# tolerances / not_applicable are assigned in the `# --- Config ---` region below.
library(jsonlite)
library(arrow)

# --- Config ---
synthetic_path <- NULL       # the parquet the generation (T4: import) step wrote; NULL if it produced nothing
report_path <- NULL          # the profile report the generation targeted
seed <- NULL                 # the integer seed the generator ran with (T4: from the user's generation log); NULL if never recorded
seed_exception <- NULL       # T4 only: non-empty pointer to the researcher-authorized missing-seed exception in STATE; never printed
tier <- NULL                 # the tier the report was produced at (its settings.tier); 4 only for a T4 import
numeric_tolerance <- 0.10    # relative tolerance per reproduced percentile, floor 1.0 absolute
proportion_tolerance <- 0.02 # absolute tolerance on categorical level proportions
correlation_tolerance <- 0.10 # the one absolute tolerance applied to every reproduced correlation
missingness_tolerance <- 0.01 # absolute tolerance on per-column null rates
not_applicable <- list()     # e.g. list(correlations_within_tolerance = "tier 2 — no correlations released")

cat("\n")
cat(strrep("=", 60), "\n")
cat("CPS-GEN VALIDATION: SYNTHETIC GENERATION\n")
cat(strrep("=", 60), "\n")

cps_gen <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# INTENT: "Blank" means Unicode whitespace only — exactly the 29 code points Python's
# str.strip() removes, so a reason or pointer made only of no-break or ideographic
# spaces is blank in both languages.
# REASONING: trimws()'s default strips only [ \t\r\n], and the PCRE class [\h\v] differs
# from Python's set (it adds U+180E and lacks U+001C-U+001F), so the class is spelled
# out. It is assembled with intToUtf8() because an R string literal cannot mix \x and
# \u escapes; the UTF-8 pattern puts PCRE in UTF mode.
cpsg_ws <- paste0("[", intToUtf8(c(0x9, 0xa, 0xb, 0xc, 0xd, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000)),
                  "-", intToUtf8(c(0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000)), "]")

# INTENT: A declared skip without a reason is indistinguishable from a silent one, so
# it is dropped — but the key stays visible to the two sweeps below, so an empty
# reason cannot be used to smuggle a declaration past the non-declarable or
# unrecognized-key gates. Keys sort by code point (radix), as Python's sorted() does.
cpsg_declared_keys <- names(not_applicable)
if (is.null(cpsg_declared_keys)) cpsg_declared_keys <- character(0)
cpsg_declared_keys <- sort(cpsg_declared_keys, method = "radix")
na_keep <- character(0)
for (k in cpsg_declared_keys) {
  v <- not_applicable[[k]]
  if (is.character(v) && length(v) == 1 && !is.na(v) && nzchar(trimws(v, whitespace = cpsg_ws))) na_keep <- c(na_keep, k)
}
not_applicable <- not_applicable[na_keep]
# INTENT: Remember which declarable keys were dropped for an empty reason, so the
# check they name reports [NOT VERIFIED] rather than silently running.
# REASONING: The author declared the check inapplicable; running it anyway and
# printing [PASS] would answer a question they explicitly withdrew. The reason is
# the evidence, and there is none — so the outcome is "not verified", not "passed".
cpsg_empty_reason <- setdiff(cpsg_declared_keys, na_keep)

cpsg_non_declarable <- c("suppressed_categories_absent", "synthetic_levels_within_released_levels",
                         "identifier_columns_value_free", "seed_recorded")
for (cpsg_key in cpsg_non_declarable) {
  if (cpsg_key %in% cpsg_declared_keys) {
    cat(sprintf("[FAIL] %s: non-declarable check declared not_applicable under key '%s'\n",
                cpsg_key, cpsg_key))
    cps_gen["failed"] <- cps_gen["failed"] + 1L
    not_applicable[[cpsg_key]] <- NULL
  }
}

# INTENT: A not_applicable key that names no check of this block is a silent no-op.
# REASONING: A typo'd or stale key would otherwise declare nothing and be ignored,
# leaving the author believing a check was skipped when it in fact ran (or the
# reverse). Naming it once is the only way the log can carry the discrepancy.
cpsg_declarable <- c("row_count_matches", "column_set_and_dtypes",
                     "numeric_marginals_within_tolerance",
                     "categorical_proportions_within_tolerance",
                     "correlations_within_tolerance", "missingness_within_tolerance")
for (cpsg_key in cpsg_declared_keys) {
  if (cpsg_key %in% cpsg_non_declarable || cpsg_key %in% cpsg_declarable) next
  cat(sprintf("[FAIL] not_applicable: unrecognized key '%s' (declarable keys: %s)\n",
              cpsg_key, paste(cpsg_declarable, collapse = ", ")))
  cps_gen["failed"] <- cps_gen["failed"] + 1L
  not_applicable[[cpsg_key]] <- NULL
}

cpsg_parse_error <- "report did not parse as JSON (parser message withheld: it can quote report content)"
cpsg_report <- NULL
cpsg_report_error <- NULL
cpsg_report_strings <- character(0)
if (is.null(report_path)) {
  cpsg_report_error <- "report_path is not set — the generation target is unknown"
} else if (!(file.exists(report_path) && !dir.exists(report_path))) {
  cpsg_report_error <- sprintf("no file at report_path '%s'", report_path)
} else {
  # REASONING: Parsing is strict and identical to CPS-INTAKE and to the Python block.
  # jsonlite already rejects the non-JSON literals NaN / Infinity / -Infinity. It
  # keeps every duplicate object key as a repeated name, at any depth, where Python's
  # dict would keep only the last — so the sweep below makes a repeat a parse error in
  # both languages. Nesting deeper than 64 levels is a parse error as well, with the
  # same cap and level count as CPS-INTAKE, and so is a number token longer than 64
  # characters (scan below). The parser's own message is withheld: it can quote
  # report text.
  # INTENT: Refuse, before the parser runs, every input the two parsers would read
  # differently: a leading UTF-8 byte-order mark (jsonlite accepts it with a warning,
  # json.loads refuses it), a NUL byte (R's text reader would stop at it), invalid
  # UTF-8, an escaped NUL (jsonlite cuts the string there) and an unpaired surrogate
  # escape (jsonlite replaces it). The bytes are read whole and parsed as text with
  # parse_json(), which never treats its input as a path or URL.
  cpsg_text <- NULL
  cpsg_raw <- try(readBin(report_path, what = "raw", n = file.info(report_path)$size), silent = TRUE)
  if (!inherits(cpsg_raw, "try-error") &&
      !(length(cpsg_raw) >= 3 && identical(cpsg_raw[1:3], as.raw(c(0xef, 0xbb, 0xbf)))) &&
      !any(cpsg_raw == as.raw(0))) {
    cpsg_text <- rawToChar(cpsg_raw)
    Encoding(cpsg_text) <- "UTF-8"
    if (!validUTF8(cpsg_text)) cpsg_text <- NULL
  }
  if (!is.null(cpsg_text)) {
    # INTENT: Walk the escape sequences left to right, as the Python block does. An
    # escaped backslash is one token, so the text `\\u0000` is not an escape.
    # ASSUMES: a \u escape is exactly six characters, so a surrogate pair is a high
    # escape immediately followed by a low one.
    cpsg_m <- gregexpr("\\\\(?:u[0-9a-fA-F]{4}|[^u])", cpsg_text, perl = TRUE)[[1]]
    cpsg_pos <- if (cpsg_m[1] == -1L) integer(0) else as.integer(cpsg_m)
    cpsg_toks <- if (cpsg_m[1] == -1L) character(0) else regmatches(cpsg_text, list(cpsg_m))[[1]]
    cpsg_cps <- rep(-1, length(cpsg_toks))
    cpsg_is_u <- substr(cpsg_toks, 2, 2) == "u"
    cpsg_cps[cpsg_is_u] <- strtoi(substr(cpsg_toks[cpsg_is_u], 3, 6), 16L)
    for (cpsg_i in seq_along(cpsg_toks)) {
      cpsg_cp <- cpsg_cps[cpsg_i]
      cpsg_hi_ok <- cpsg_i < length(cpsg_toks) && cpsg_pos[cpsg_i + 1L] == cpsg_pos[cpsg_i] + 6L &&
        cpsg_cps[cpsg_i + 1L] >= 0xDC00 && cpsg_cps[cpsg_i + 1L] <= 0xDFFF
      cpsg_lo_ok <- cpsg_i > 1L && cpsg_pos[cpsg_i - 1L] == cpsg_pos[cpsg_i] - 6L &&
        cpsg_cps[cpsg_i - 1L] >= 0xD800 && cpsg_cps[cpsg_i - 1L] <= 0xDBFF
      if (cpsg_cp == 0 || (cpsg_cp >= 0xD800 && cpsg_cp <= 0xDBFF && !cpsg_hi_ok) ||
          (cpsg_cp >= 0xDC00 && cpsg_cp <= 0xDFFF && !cpsg_lo_ok)) {
        cpsg_text <- NULL
        break
      }
    }
  }
  if (!is.null(cpsg_text)) {
    # INTENT: Refuse any JSON number token longer than 64 characters (sign, digits,
    # fraction and exponent counted together) outside strings, as the Python block and
    # CPS-INTAKE do.
    # REASONING: jsonlite reads an integer past Python's 4300-digit conversion limit as
    # Inf and parses on, where Python refuses it, so the verdicts would split. A
    # profiler never writes a number near 64 characters. The pattern is the Python
    # block's: each string is matched whole first, so digits inside one never count.
    cpsg_nm <- gregexpr('(?s)"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"|[-+.0-9eE]+', cpsg_text, perl = TRUE)[[1]]
    cpsg_ntoks <- if (cpsg_nm[1] == -1L) character(0) else regmatches(cpsg_text, list(cpsg_nm))[[1]]
    if (any(substr(cpsg_ntoks, 1, 1) != "\"" & nchar(cpsg_ntoks) > 64)) cpsg_text <- NULL
  }
  cpsg_parsed <- if (is.null(cpsg_text)) NULL else try(jsonlite::parse_json(cpsg_text, simplifyVector = FALSE), silent = TRUE)
  if (is.null(cpsg_text) || inherits(cpsg_parsed, "try-error")) {
    cpsg_report_error <- cpsg_parse_error
  } else {
    # INTENT: Breadth-first sweep over every container in the tree that refuses a
    # duplicate object name and any container nested deeper than 64 levels, counting
    # the top-level object as level 1; an array is an unnamed list, an object a named
    # one (an empty object has names() of length 0, never NULL), and each is one level.
    # The sweep also collects every key and string value, so any report text a line
    # prints can be escaped (see the escape table below).
    # REASONING: The two parsers give up at different depths (jsonlite's own limit,
    # Python's recursion limit), so between those limits one block judged a file the
    # other refused. The cap is CPS-INTAKE's, so the outcome depends on the file, not
    # on the parser or the block.
    cpsg_max_depth <- 64L
    cpsg_queue <- list(cpsg_parsed)
    cpsg_queue_depth <- 1L
    cpsg_qi <- 1L
    cpsg_refused <- FALSE
    while (cpsg_qi <= length(cpsg_queue) && !cpsg_refused) {
      cpsg_node <- cpsg_queue[[cpsg_qi]]
      cpsg_d <- cpsg_queue_depth[cpsg_qi]
      cpsg_qi <- cpsg_qi + 1L
      if (is.list(cpsg_node)) {
        if (cpsg_d > cpsg_max_depth || (!is.null(names(cpsg_node)) && anyDuplicated(names(cpsg_node)) > 0)) cpsg_refused <- TRUE
        if (!is.null(names(cpsg_node))) cpsg_report_strings <- c(cpsg_report_strings, names(cpsg_node))
        cpsg_queue <- c(cpsg_queue, unname(cpsg_node))
        cpsg_queue_depth <- c(cpsg_queue_depth, rep(cpsg_d + 1L, length(cpsg_node)))
      } else if (is.character(cpsg_node)) {
        cpsg_report_strings <- c(cpsg_report_strings, cpsg_node)
      }
    }
    if (cpsg_refused) {
      cpsg_report_error <- cpsg_parse_error
    } else if (!is.list(cpsg_parsed) || is.null(names(cpsg_parsed))) {
      cpsg_report_error <- "report parsed, but its top level is not a JSON object"
    } else {
      cpsg_report <- cpsg_parsed
    }
  }
}

# INTENT: Read the synthetic parquet as an arrow Table and keep, per column, its name,
# its class, its stored null count and (for the classes a check reads) its values.
# REASONING: The classes are the Python block's: text = string; text_dict = a
# dictionary-encoded string (polars Categorical / Enum); integer = 8- to 64-bit signed
# or unsigned; float = 32- or 64-bit; boolean. Every other arrow type (decimal, half
# float, date, time, timestamp, duration, binary, nested, null) is "other" — arrow
# reads a half float as its raw bits and a decimal as a double, so the two readers
# would disagree on its values — and no check compares an "other" column's values.
# Columns are converted one at a time, never through as.data.frame(): a polars
# Categorical (uint32 dictionary indices) does not convert to a factor, so a
# dictionary-encoded string is cast to plain strings on the arrow side first. A
# repeated column name is refused as unreadable, as the Python block refuses it from
# the raw parquet schema (polars alone would keep one of the repeats).
cpsg_syn <- NULL
cpsg_syn_error <- NULL
cpsg_syn_names <- character(0)
cpsg_syn_class <- character(0)
cpsg_syn_nulls <- numeric(0)
cpsg_syn_nrow <- 0
if (is.null(synthetic_path)) {
  cpsg_syn_error <- "synthetic_path is not set — generation produced no file"
} else if (!(file.exists(synthetic_path) && !dir.exists(synthetic_path))) {
  cpsg_syn_error <- sprintf("no file at synthetic_path '%s'", synthetic_path)
} else {
  cpsg_read <- try({
    cpsg_tbl <- arrow::read_parquet(synthetic_path, as_data_frame = FALSE)
    cpsg_syn_names <- names(cpsg_tbl)
    if (anyDuplicated(cpsg_syn_names) > 0) stop("repeated column name")
    cpsg_syn_nrow <- as.numeric(cpsg_tbl$num_rows)
    cpsg_syn_class <- character(length(cpsg_syn_names))
    cpsg_syn_nulls <- numeric(length(cpsg_syn_names))
    cpsg_vals_list <- vector("list", length(cpsg_syn_names))
    for (cpsg_i in seq_along(cpsg_syn_names)) {
      cpsg_arr <- cpsg_tbl$column(cpsg_i - 1L)
      cpsg_ty <- cpsg_arr$type$ToString()
      cpsg_k <- if (cpsg_ty %in% c("string", "large_string", "string_view")) {
        "text"
      } else if (startsWith(cpsg_ty, "dictionary<values=string,") || startsWith(cpsg_ty, "dictionary<values=large_string,") ||
                 startsWith(cpsg_ty, "dictionary<values=string_view,")) {
        "text_dict"
      } else if (cpsg_ty %in% c("int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64")) {
        "integer"
      } else if (cpsg_ty %in% c("float", "double")) {
        "float"
      } else if (cpsg_ty == "bool") {
        "boolean"
      } else {
        "other"
      }
      cpsg_syn_class[cpsg_i] <- cpsg_k
      cpsg_syn_nulls[cpsg_i] <- as.numeric(cpsg_arr$null_count)
      if (cpsg_k == "text_dict") {
        cpsg_vals_list[[cpsg_i]] <- cpsg_arr$cast(arrow::utf8())$as_vector()
      } else if (cpsg_k != "other") {
        cpsg_vals_list[[cpsg_i]] <- suppressWarnings(cpsg_arr$as_vector())
      }
    }
    cpsg_vals_list
  }, silent = TRUE)
  if (inherits(cpsg_read, "try-error")) {
    cpsg_syn_error <- "the synthetic parquet did not read (reader message withheld: the two readers word it differently)"
    cpsg_syn_names <- character(0)
    cpsg_syn_class <- character(0)
  } else {
    cpsg_syn <- cpsg_read
  }
}
# INTENT: The columns whose values cannot be compared with released labels as text: an
# "other" column, and an integer column holding a magnitude of 2^53 or more (arrow
# hands a large 64-bit integer to R as a double, so its text would no longer be exact).
cpsg_untextable <- character(0)
for (cpsg_i in seq_along(cpsg_syn_names)) {
  if (cpsg_syn_class[cpsg_i] == "other" ||
      (cpsg_syn_class[cpsg_i] == "integer" && isTRUE(any(abs(suppressWarnings(as.numeric(cpsg_syn[[cpsg_i]]))) >= 2^53, na.rm = TRUE)))) {
    cpsg_untextable <- c(cpsg_untextable, cpsg_syn_names[cpsg_i])
  }
}
cpsg_untextable_msg <- "holds values outside the text-comparable types (string, categorical, integer below 2^53, float, boolean)"

# INTENT: Escape every report- or frame-derived string before it reaches an outcome line,
# exactly as the Python block does: a character outside printable ASCII (0x20-0x7E)
# prints as \uXXXX in lowercase hex, and one above U+FFFF as its UTF-16 surrogate pair.
# REASONING: A column name or key carrying a newline or control character could otherwise
# forge an extra outcome line, and a non-ASCII one could fail the write on a console that
# cannot encode it. The table covers every key and string value of the parsed report and
# every synthetic column name; each print site looks its text up with match(), which —
# unlike [[ ]] — also finds an empty name.
cpsg_esc_from <- unique(c(cpsg_report_strings, cpsg_syn_names))
cpsg_esc_to <- character(length(cpsg_esc_from))
for (cpsg_i in seq_along(cpsg_esc_from)) {
  cpsg_cp <- utf8ToInt(enc2utf8(cpsg_esc_from[cpsg_i]))
  if (length(cpsg_cp) == 0 || anyNA(cpsg_cp)) {
    cpsg_esc_to[cpsg_i] <- if (length(cpsg_cp) == 0) "" else "\\ufffd"
    next
  }
  cpsg_esc_to[cpsg_i] <- paste(ifelse(cpsg_cp >= 32L & cpsg_cp <= 126L, intToUtf8(cpsg_cp, multiple = TRUE),
                                      ifelse(cpsg_cp < 65536L, sprintf("\\u%04x", cpsg_cp),
                                             sprintf("\\u%04x\\u%04x", 55296L + (cpsg_cp - 65536L) %/% 1024L,
                                                     56320L + (cpsg_cp - 65536L) %% 1024L))), collapse = "")
}

# INTENT: One numeric model for both languages, shared with CPS-INTAKE: a JSON number
# is usable only when it is finite and |v| < 2^53. Whole numbers are tested as
# v == floor(v), never via as.integer(), which turns 3e9 into NA and would hand
# `if ()` an NA.
cpsg_max_exact <- 2^53

# INTENT: Bind the report's parts once. An object is a named list and an array an
# unnamed one, tested exactly as the Python block tests dict / list.
cpsg_columns <- NULL
cpsg_columns_unusable <- 0L
cpsg_row_count <- NULL
cpsg_relationships <- NULL
cpsg_report_tier <- NULL
if (!is.null(cpsg_report)) {
  cpsg_x <- cpsg_report[["columns"]]
  if (is.list(cpsg_x) && is.null(names(cpsg_x))) {
    cpsg_columns <- list()
    for (cpsg_c in cpsg_x) {
      if (is.list(cpsg_c) && !is.null(names(cpsg_c))) cpsg_columns <- c(cpsg_columns, list(cpsg_c))
    }
    cpsg_columns_unusable <- length(cpsg_x) - length(cpsg_columns)
  }
  cpsg_x <- cpsg_report[["dataset"]]
  if (is.list(cpsg_x) && !is.null(names(cpsg_x))) cpsg_row_count <- cpsg_x[["row_count"]]
  cpsg_x <- cpsg_report[["relationships"]]
  if (is.list(cpsg_x) && !is.null(names(cpsg_x))) cpsg_relationships <- cpsg_x
  cpsg_x <- cpsg_report[["settings"]]
  if (is.list(cpsg_x) && !is.null(names(cpsg_x))) cpsg_report_tier <- cpsg_x[["tier"]]
}
# INTENT: A role counts only as a single string and an identifier flag only as a
# single TRUE, as in Python (R's list("numeric") == "numeric" would coerce to TRUE).
cpsg_cat_cols <- list()
cpsg_num_cols <- list()
cpsg_id_cols <- list()
cpsg_rated <- list()
for (cpsg_col in if (is.null(cpsg_columns)) list() else cpsg_columns) {
  cpsg_role <- cpsg_col[["role"]]
  if (!(is.character(cpsg_role) && length(cpsg_role) == 1 && !is.na(cpsg_role))) cpsg_role <- ""
  if (cpsg_role == "numeric") cpsg_num_cols <- c(cpsg_num_cols, list(cpsg_col))
  if (cpsg_role == "categorical") cpsg_cat_cols <- c(cpsg_cat_cols, list(cpsg_col))
  if (cpsg_role == "identifier" || isTRUE(cpsg_col[["is_identifier"]])) {
    cpsg_id_cols <- c(cpsg_id_cols, list(cpsg_col))
  }
  if ("missing_rate" %in% names(cpsg_col)) cpsg_rated <- c(cpsg_rated, list(cpsg_col))
}
cpsg_inputs_error <- if (!is.null(cpsg_report_error)) cpsg_report_error else cpsg_syn_error
# INTENT: Column names count only as single strings; a record without one is counted.
cpsg_declared_names <- character(0)
cpsg_unnamed <- cpsg_columns_unusable
for (cpsg_col in if (is.null(cpsg_columns)) list() else cpsg_columns) {
  cpsg_name <- cpsg_col[["name"]]
  if (is.character(cpsg_name) && length(cpsg_name) == 1 && !is.na(cpsg_name)) {
    cpsg_declared_names <- c(cpsg_declared_names, cpsg_name)
  } else {
    cpsg_unnamed <- cpsg_unnamed + 1L
  }
}
cpsg_row_count_ok <- is.numeric(cpsg_row_count) && length(cpsg_row_count) == 1 &&
  !is.na(cpsg_row_count) && abs(cpsg_row_count) < cpsg_max_exact &&
  cpsg_row_count == floor(cpsg_row_count)

# INTENT: Resolve the tier whose release rules apply. Config `tier` is the tier the
# report was produced at (its settings.tier), so tiers 1-3 come from the config; at
# tier 4 (local synthesis, imported here) the report's own settings.tier governs.
# REASONING: as in the Python block, correlations_within_tolerance (the one check whose
# outcome the tier decides) fails when a configured 1-3 differs from a whole-number 1-3
# the report declares, so a mis-copied tier is caught rather than misread.
cpsg_tier_ok <- is.numeric(tier) && length(tier) == 1 && !is.na(tier) && tier %in% c(1, 2, 3, 4)
cpsg_report_tier_ok <- is.numeric(cpsg_report_tier) && length(cpsg_report_tier) == 1 &&
  !is.na(cpsg_report_tier) && cpsg_report_tier %in% c(1, 2, 3)
cpsg_release_tier <- NULL
if (cpsg_tier_ok && tier != 4) {
  cpsg_release_tier <- as.integer(tier)
} else if (cpsg_tier_ok && cpsg_report_tier_ok) {
  cpsg_release_tier <- as.integer(cpsg_report_tier)
}
cpsg_tier_label <- if (!is.null(cpsg_release_tier)) {
  as.character(cpsg_release_tier)
} else if (is.null(tier)) {
  "unrecorded"
} else if (cpsg_tier_ok) {
  "4 (report tier unrecorded)"
} else {
  "invalid"
}

# INTENT: Validate every categorical record's released level set once (same rules and
# same 0-based level index as the Python block), so the checks that read it agree on
# what is usable and none can hand `if ()` a NULL count or index a scalar entry.
cpsg_cat_entries <- list()
for (cpsg_col in cpsg_cat_cols) {
  cpsg_name <- cpsg_col[["name"]]
  cpsg_name_ok <- is.character(cpsg_name) && length(cpsg_name) == 1 && !is.na(cpsg_name)
  cpsg_blk <- cpsg_col[["categorical"]]
  cpsg_lvls <- if (is.list(cpsg_blk) && !is.null(names(cpsg_blk))) cpsg_blk[["levels"]] else NULL
  cpsg_lvls_ok <- is.list(cpsg_lvls) && is.null(names(cpsg_lvls))
  cpsg_entry <- list(name = if (cpsg_name_ok) cpsg_name else NA_character_, problem = NA_character_,
                     values = character(0), counts = numeric(0), n = NA_real_, binned = NA_real_)
  if (!cpsg_name_ok) {
    cpsg_entry$problem <- "a categorical column record carries no string name"
  } else if (!cpsg_lvls_ok) {
    cpsg_entry$problem <- sprintf("column '%s' declares role categorical but has no levels array to compare against",
                                  cpsg_esc_to[match(cpsg_name, cpsg_esc_from)])
  }
  if (cpsg_lvls_ok) {
    for (cpsg_i in seq_along(cpsg_lvls)) {
      cpsg_lv <- cpsg_lvls[[cpsg_i]]
      cpsg_ok <- FALSE
      if (is.list(cpsg_lv) && !is.null(names(cpsg_lv))) {
        cpsg_v <- cpsg_lv[["value"]]
        cpsg_cnt <- cpsg_lv[["count"]]
        cpsg_ok <- is.character(cpsg_v) && length(cpsg_v) == 1 && !is.na(cpsg_v) &&
          is.numeric(cpsg_cnt) && length(cpsg_cnt) == 1 && !is.na(cpsg_cnt) &&
          cpsg_cnt >= 0 && cpsg_cnt < cpsg_max_exact && cpsg_cnt == floor(cpsg_cnt)
      }
      if (cpsg_ok) {
        cpsg_entry$values <- c(cpsg_entry$values, cpsg_v)
        cpsg_entry$counts <- c(cpsg_entry$counts, as.numeric(cpsg_cnt))
      } else if (is.na(cpsg_entry$problem)) {
        cpsg_entry$problem <- sprintf("column '%s' level index %d is not a string label with a whole-number count",
                                      cpsg_esc_to[match(cpsg_name, cpsg_esc_from)], cpsg_i - 1L)
      }
    }
    cpsg_x <- cpsg_blk[["n"]]
    if (is.numeric(cpsg_x) && length(cpsg_x) == 1 && !is.na(cpsg_x) && cpsg_x > 0 &&
        cpsg_x < cpsg_max_exact && cpsg_x == floor(cpsg_x)) cpsg_entry$n <- as.numeric(cpsg_x)
    cpsg_x <- cpsg_blk[["n_levels_binned"]]
    if (is.numeric(cpsg_x) && length(cpsg_x) == 1 && !is.na(cpsg_x) && cpsg_x >= 0 &&
        cpsg_x < cpsg_max_exact && cpsg_x == floor(cpsg_x)) cpsg_entry$binned <- as.numeric(cpsg_x)
  }
  cpsg_cat_entries <- c(cpsg_cat_entries, list(cpsg_entry))
}

# INTENT: Reduce every synthetic column a check compares with released labels to one
# canonical text per distinct value, with its count — the Python block's form, built
# with the same printf formats.
# REASONING: A string or categorical value compares as written; a whole-number value —
# integer or float — is integer text (sprintf("%.0f", v + 0), so -0 is "0"); any other
# finite float is %.17g text and an infinity inf / -inf; NaN is missing (is.na()); a
# boolean is true / false. Counting by match() + tabulate() avoids table()'s name
# lookup, which cannot address an empty-string label.
cpsg_tc_names <- character(0)
cpsg_tc_values <- list()
cpsg_tc_counts <- list()
cpsg_text_names <- character(0)
for (cpsg_entry in cpsg_cat_entries) {
  if (!is.na(cpsg_entry$name)) cpsg_text_names <- c(cpsg_text_names, cpsg_entry$name)
}
for (cpsg_col in cpsg_id_cols) {
  cpsg_name <- cpsg_col[["name"]]
  if (is.character(cpsg_name) && length(cpsg_name) == 1 && !is.na(cpsg_name)) cpsg_text_names <- c(cpsg_text_names, cpsg_name)
}
for (cpsg_name in sort(unique(cpsg_text_names), method = "radix")) {
  cpsg_idx <- match(cpsg_name, cpsg_syn_names)
  if (is.null(cpsg_syn) || is.na(cpsg_idx) || cpsg_name %in% cpsg_untextable) next
  cpsg_k <- cpsg_syn_class[cpsg_idx]
  cpsg_vec <- cpsg_syn[[cpsg_idx]]
  cpsg_vec <- cpsg_vec[!is.na(cpsg_vec)]
  cpsg_canon <- if (cpsg_k == "integer") {
    sprintf("%.0f", suppressWarnings(as.numeric(cpsg_vec)) + 0)
  } else if (cpsg_k == "float") {
    ifelse(is.finite(cpsg_vec) & cpsg_vec == floor(cpsg_vec), sprintf("%.0f", cpsg_vec + 0),
           ifelse(is.finite(cpsg_vec), sprintf("%.17g", cpsg_vec), ifelse(cpsg_vec > 0, "inf", "-inf")))
  } else if (cpsg_k == "boolean") {
    ifelse(cpsg_vec, "true", "false")
  } else {
    as.character(cpsg_vec)
  }
  cpsg_u <- unique(cpsg_canon)
  cpsg_tc_names <- c(cpsg_tc_names, cpsg_name)
  cpsg_tc_values <- c(cpsg_tc_values, list(cpsg_u))
  cpsg_tc_counts <- c(cpsg_tc_counts, list(tabulate(match(cpsg_canon, cpsg_u), nbins = length(cpsg_u))))
}

# Check: the synthetic row count equals the count the report declares
if ("row_count_matches" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] row_count_matches: %s\n", not_applicable[["row_count_matches"]]))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if ("row_count_matches" %in% cpsg_empty_reason) {
  cat("[NOT VERIFIED] row_count_matches: declared not_applicable with an empty reason\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] row_count_matches: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (!cpsg_row_count_ok) {
  cat("[NOT VERIFIED] row_count_matches: dataset.row_count is absent or not a whole number — no target to match\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (cpsg_syn_nrow != cpsg_row_count) {
  cat(sprintf("[FAIL] row_count_matches: synthetic has %s rows, the report declares %s\n",
              format(cpsg_syn_nrow, big.mark = ",", scientific = FALSE, trim = TRUE),
              format(cpsg_row_count, big.mark = ",", scientific = FALSE, trim = TRUE)))
  cps_gen["failed"] <- cps_gen["failed"] + 1L
} else {
  cat(sprintf("[PASS] row_count_matches: %s synthetic rows == declared row_count %s\n",
              format(cpsg_syn_nrow, big.mark = ",", scientific = FALSE, trim = TRUE),
              format(cpsg_row_count, big.mark = ",", scientific = FALSE, trim = TRUE)))
  cps_gen["passed"] <- cps_gen["passed"] + 1L
}

# Check: column set and dtypes match the report's declared schema
if ("column_set_and_dtypes" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] column_set_and_dtypes: %s\n", not_applicable[["column_set_and_dtypes"]]))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if ("column_set_and_dtypes" %in% cpsg_empty_reason) {
  cat("[NOT VERIFIED] column_set_and_dtypes: declared not_applicable with an empty reason\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] column_set_and_dtypes: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_columns) || length(cpsg_columns) == 0) {
  cat("[NOT VERIFIED] column_set_and_dtypes: the report declares no columns to match against\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (cpsg_unnamed > 0) {
  # REASONING: a record with no string name is report evidence of the wrong type —
  # the declared schema it belongs to cannot be matched, so nothing is concluded.
  cat(sprintf("[NOT VERIFIED] column_set_and_dtypes: %d of %d column records carry no string name — the declared schema cannot be matched\n",
              as.integer(cpsg_unnamed), as.integer(cpsg_columns_unusable + length(cpsg_columns))))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else {
  cpsg_missing <- sort(unique(setdiff(cpsg_declared_names, cpsg_syn_names)), method = "radix")
  cpsg_extra <- sort(unique(setdiff(cpsg_syn_names, cpsg_declared_names)), method = "radix")
  cpsg_bad <- character(0)
  if (length(cpsg_missing) > 0 || length(cpsg_extra) > 0) {
    cpsg_bad <- c(cpsg_bad, sprintf("column set differs — missing [%s], unexpected [%s]",
                                    paste(cpsg_esc_to[match(cpsg_missing, cpsg_esc_from)], collapse = ", "),
                                    paste(cpsg_esc_to[match(cpsg_extra, cpsg_esc_from)], collapse = ", ")))
  } else {
    # REASONING: judged by the column class, as in the Python block: "string" needs a
    # plain string column, "double" an integer or float column, "integer" an integer
    # column or a float column whose values are all whole.
    for (cpsg_col in cpsg_columns) {
      cpsg_name <- cpsg_col[["name"]]
      cpsg_dtype <- cpsg_col[["dtype"]]
      cpsg_idx <- match(cpsg_name, cpsg_syn_names)
      cpsg_k <- cpsg_syn_class[cpsg_idx]
      cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
      cpsg_dtype_ok <- is.character(cpsg_dtype) && length(cpsg_dtype) == 1 && !is.na(cpsg_dtype) &&
        cpsg_dtype %in% c("integer", "double", "string")
      if (!cpsg_dtype_ok) {
        cpsg_bad <- c(cpsg_bad, sprintf("column '%s' declares an unrecognized dtype", cpsg_ename))
      } else if (cpsg_dtype == "integer") {
        cpsg_whole <- cpsg_k == "integer"
        if (cpsg_k == "float") {
          cpsg_v <- cpsg_syn[[cpsg_idx]]
          cpsg_v <- cpsg_v[!is.na(cpsg_v)]
          cpsg_whole <- all(is.finite(cpsg_v) & cpsg_v == floor(cpsg_v))
        }
        if (!cpsg_whole) {
          cpsg_bad <- c(cpsg_bad, sprintf("column '%s' is not whole-numeric, the report declares integer", cpsg_ename))
        }
      } else if (cpsg_dtype == "double") {
        if (!(cpsg_k %in% c("integer", "float"))) {
          cpsg_bad <- c(cpsg_bad, sprintf("column '%s' is not numeric, the report declares double", cpsg_ename))
        }
      } else if (cpsg_k != "text") {
        cpsg_bad <- c(cpsg_bad, sprintf("column '%s' is not a string column, the report declares string", cpsg_ename))
      }
    }
  }
  if (length(cpsg_bad) > 0) {
    cat(sprintf("[FAIL] column_set_and_dtypes: %s%s\n", cpsg_bad[1],
                if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
    cps_gen["failed"] <- cps_gen["failed"] + 1L
  } else {
    cat(sprintf("[PASS] column_set_and_dtypes: %d declared columns, names and dtypes all matched\n",
                length(cpsg_columns)))
    cps_gen["passed"] <- cps_gen["passed"] + 1L
  }
}

# Check: reproduced numeric percentiles sit within tolerance of the released grid
if ("numeric_marginals_within_tolerance" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] numeric_marginals_within_tolerance: %s\n", not_applicable[["numeric_marginals_within_tolerance"]]))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if ("numeric_marginals_within_tolerance" %in% cpsg_empty_reason) {
  cat("[NOT VERIFIED] numeric_marginals_within_tolerance: declared not_applicable with an empty reason\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] numeric_marginals_within_tolerance: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else {
  # REASONING: same partition as the Python block — no-percentile shapes (withheld,
  # all-missing, constant) are not targets; a record with no name or no numeric block,
  # or a percentiles field that is not an object, is counted as missing evidence.
  cpsg_targets <- list()
  cpsg_absent <- character(0)
  for (cpsg_col in cpsg_num_cols) {
    cpsg_name <- cpsg_col[["name"]]
    cpsg_blk <- cpsg_col[["numeric"]]
    if (!(is.character(cpsg_name) && length(cpsg_name) == 1 && !is.na(cpsg_name))) {
      cpsg_absent <- c(cpsg_absent, "a numeric column record carries no string name")
    } else if (!(is.list(cpsg_blk) && !is.null(names(cpsg_blk)))) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' declares role numeric but has no numeric block",
                                            cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]))
    } else if ("percentiles" %in% names(cpsg_blk) &&
               !(is.list(cpsg_blk[["percentiles"]]) && !is.null(names(cpsg_blk[["percentiles"]])))) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' carries a percentiles field that is not an object",
                                            cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]))
    } else if ("percentiles" %in% names(cpsg_blk)) {
      cpsg_targets <- c(cpsg_targets, list(list(name = cpsg_name, grid = cpsg_blk[["percentiles"]])))
    }
  }
  if (length(cpsg_targets) == 0 && length(cpsg_absent) == 0) {
    cat(sprintf("[SKIPPED] numeric_marginals_within_tolerance: report declares 0 numeric distribution targets at tier %s\n",
                cpsg_tier_label))
    cps_gen["skipped"] <- cps_gen["skipped"] + 1L
  } else {
    cpsg_compared <- 0L
    cpsg_off <- character(0)
    cpsg_bad <- character(0)
    # INTENT: The grid's keys are a closed set fixed by the profiling spec; parse
    # nothing that is not in it.
    # REASONING: `as.numeric(sub("^p", "", key))` on an unvetted key coerces to NA with
    # only a coercion warning, and the run then reports [NOT VERIFIED] "quantile came
    # back NA" — blaming the quantile for a malformed report key. Naming the key is
    # the finding.
    # ASSUMES: the released grid is the spec's ordered percentile set (the small-n
    # shape releases the p25/p50/p75 subset of it). quantile() type 7 over the non-NA
    # values is the Python block's linear interpolation, so both print one line.
    cpsg_pct_names <- c("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
    for (cpsg_t in cpsg_targets) {
      cpsg_name <- cpsg_t[["name"]]
      cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
      cpsg_idx <- match(cpsg_name, cpsg_syn_names)
      if (is.na(cpsg_idx)) {
        cpsg_absent <- c(cpsg_absent, sprintf("column '%s' has a released grid but is absent from the synthetic frame", cpsg_ename))
        next
      }
      # REASONING: the synthetic column is under validation, so one outside the
      # integer and float classes is a [FAIL] — quantile() on it would stop the block,
      # or (decimal, half float) the two readers would see different values.
      if (!(cpsg_syn_class[cpsg_idx] %in% c("integer", "float"))) {
        cpsg_bad <- c(cpsg_bad, sprintf("column '%s' is not numeric in the synthetic frame — its released percentiles cannot be reproduced", cpsg_ename))
        next
      }
      cpsg_vec <- suppressWarnings(as.numeric(cpsg_syn[[cpsg_idx]]))
      cpsg_vals <- cpsg_vec[!is.na(cpsg_vec)]
      if (length(cpsg_vals) == 0) {
        cpsg_absent <- c(cpsg_absent, sprintf("column '%s' has a released grid but is entirely null in the synthetic frame", cpsg_ename))
        next
      }
      cpsg_grid <- cpsg_t[["grid"]]
      for (cpsg_k in names(cpsg_grid)) {
        if (!(cpsg_k %in% cpsg_pct_names)) {
          cpsg_bad <- c(cpsg_bad, sprintf("column '%s' percentile grid carries unrecognized key '%s'",
                                          cpsg_ename, cpsg_esc_to[match(cpsg_k, cpsg_esc_from)]))
          next
        }
        cpsg_target <- cpsg_grid[[cpsg_k]]
        if (!(is.numeric(cpsg_target) && length(cpsg_target) == 1 && !is.na(cpsg_target) &&
              abs(cpsg_target) < cpsg_max_exact)) {
          cpsg_absent <- c(cpsg_absent, sprintf("column '%s' percentile %s target is not a usable number", cpsg_ename, cpsg_k))
          next
        }
        cpsg_q <- as.numeric(sub("^p", "", cpsg_k)) / 100
        cpsg_obs <- quantile(cpsg_vals, cpsg_q, names = FALSE, type = 7)
        if (!is.finite(cpsg_obs)) {
          cpsg_absent <- c(cpsg_absent, sprintf("column '%s' quantile %s came back empty", cpsg_ename, cpsg_k))
          next
        }
        cpsg_compared <- cpsg_compared + 1L
        if (abs(cpsg_obs - cpsg_target) > numeric_tolerance * max(abs(cpsg_target), 1)) {
          cpsg_off <- c(cpsg_off, sprintf("column '%s' %s deviates by %.4g", cpsg_ename, cpsg_k,
                                          abs(cpsg_obs - cpsg_target)))
        }
      }
    }
    if (length(cpsg_bad) > 0) {
      cat(sprintf("[FAIL] numeric_marginals_within_tolerance: %s%s\n", cpsg_bad[1],
                  if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
      cps_gen["failed"] <- cps_gen["failed"] + 1L
    } else if (length(cpsg_absent) > 0) {
      cat(sprintf("[NOT VERIFIED] numeric_marginals_within_tolerance: %s%s\n", cpsg_absent[1],
                  if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
      cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
    } else if (cpsg_compared == 0) {
      cat(sprintf("[NOT VERIFIED] numeric_marginals_within_tolerance: %d columns released a percentile grid but 0 percentile comparisons were made\n",
                  length(cpsg_targets)))
      cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
    } else if (length(cpsg_off) > 0) {
      cat(sprintf("[WARNING] numeric_marginals_within_tolerance: %d of %d percentile comparisons outside the %.4g%% relative band — %s\n",
                  length(cpsg_off), cpsg_compared, numeric_tolerance * 100, cpsg_off[1]))
      cps_gen["warning"] <- cps_gen["warning"] + 1L
    } else {
      cat(sprintf("[PASS] numeric_marginals_within_tolerance: %d columns, %d percentile comparisons, all within the %.4g%% relative band\n",
                  length(cpsg_targets), cpsg_compared, numeric_tolerance * 100))
      cps_gen["passed"] <- cps_gen["passed"] + 1L
    }
  }
}

# Check: reproduced categorical proportions sit within tolerance of the released levels
if ("categorical_proportions_within_tolerance" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] categorical_proportions_within_tolerance: %s\n", not_applicable[["categorical_proportions_within_tolerance"]]))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if ("categorical_proportions_within_tolerance" %in% cpsg_empty_reason) {
  cat("[NOT VERIFIED] categorical_proportions_within_tolerance: declared not_applicable with an empty reason\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] categorical_proportions_within_tolerance: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else {
  # INTENT: An unusable level set is counted as missing evidence; a usable but empty
  # one (every level suppressed) released no target.
  cpsg_targets <- list()
  cpsg_absent <- character(0)
  for (cpsg_entry in cpsg_cat_entries) {
    if (!is.na(cpsg_entry$problem)) {
      cpsg_absent <- c(cpsg_absent, cpsg_entry$problem)
    } else if (length(cpsg_entry$values) > 0) {
      cpsg_targets <- c(cpsg_targets, list(cpsg_entry))
    }
  }
  if (length(cpsg_targets) == 0 && length(cpsg_absent) == 0) {
    cat(sprintf("[SKIPPED] categorical_proportions_within_tolerance: report declares 0 categorical level targets at tier %s\n",
                cpsg_tier_label))
    cps_gen["skipped"] <- cps_gen["skipped"] + 1L
  } else {
    cpsg_compared <- 0L
    cpsg_off <- character(0)
    cpsg_bad <- character(0)
    for (cpsg_entry in cpsg_targets) {
      cpsg_name <- cpsg_entry$name
      cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
      if (!(cpsg_name %in% cpsg_syn_names)) {
        cpsg_absent <- c(cpsg_absent, sprintf("column '%s' has released levels but is absent from the synthetic frame", cpsg_ename))
        next
      }
      if (cpsg_name %in% cpsg_untextable) {
        cpsg_bad <- c(cpsg_bad, sprintf("column '%s' %s — its levels cannot be compared", cpsg_ename, cpsg_untextable_msg))
        next
      }
      cpsg_denom <- cpsg_entry$n
      if (is.na(cpsg_denom)) {
        cpsg_absent <- c(cpsg_absent, sprintf("column '%s' categorical block carries no positive n to form proportions from", cpsg_ename))
        next
      }
      # ASSUMES: levels are compared through the canonical text form above, which the
      # Python block builds identically.
      cpsg_ti <- match(cpsg_name, cpsg_tc_names)
      cpsg_u <- cpsg_tc_values[[cpsg_ti]]
      cpsg_n <- cpsg_tc_counts[[cpsg_ti]]
      cpsg_obs_n <- sum(cpsg_n)
      if (cpsg_obs_n == 0) {
        cpsg_absent <- c(cpsg_absent, sprintf("column '%s' is entirely null in the synthetic frame", cpsg_ename))
        next
      }
      cpsg_bool <- cpsg_syn_class[match(cpsg_name, cpsg_syn_names)] == "boolean"
      for (cpsg_i in seq_along(cpsg_entry$values)) {
        cpsg_key <- cpsg_entry$values[cpsg_i]
        if (cpsg_bool && tolower(cpsg_key) %in% c("true", "false")) cpsg_key <- tolower(cpsg_key)
        cpsg_hit <- match(cpsg_key, cpsg_u)
        cpsg_target <- cpsg_entry$counts[cpsg_i] / cpsg_denom
        cpsg_obs <- (if (is.na(cpsg_hit)) 0 else cpsg_n[cpsg_hit]) / cpsg_obs_n
        cpsg_compared <- cpsg_compared + 1L
        if (abs(cpsg_obs - cpsg_target) > proportion_tolerance) {
          cpsg_off <- c(cpsg_off, sprintf("column '%s' has a level proportion off by %.4f", cpsg_ename,
                                          abs(cpsg_obs - cpsg_target)))
        }
      }
    }
    if (length(cpsg_bad) > 0) {
      cat(sprintf("[FAIL] categorical_proportions_within_tolerance: %s%s\n", cpsg_bad[1],
                  if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
      cps_gen["failed"] <- cps_gen["failed"] + 1L
    } else if (length(cpsg_absent) > 0) {
      cat(sprintf("[NOT VERIFIED] categorical_proportions_within_tolerance: %s%s\n", cpsg_absent[1],
                  if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
      cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
    } else if (cpsg_compared == 0) {
      cat(sprintf("[NOT VERIFIED] categorical_proportions_within_tolerance: %d columns released levels but 0 level proportions were compared\n",
                  length(cpsg_targets)))
      cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
    } else if (length(cpsg_off) > 0) {
      cat(sprintf("[WARNING] categorical_proportions_within_tolerance: %d of %d level proportions outside +/-%.4g — %s\n",
                  length(cpsg_off), cpsg_compared, proportion_tolerance, cpsg_off[1]))
      cps_gen["warning"] <- cps_gen["warning"] + 1L
    } else {
      cat(sprintf("[PASS] categorical_proportions_within_tolerance: %d columns, %d level proportions, all within +/-%.4g\n",
                  length(cpsg_targets), cpsg_compared, proportion_tolerance))
      cps_gen["passed"] <- cps_gen["passed"] + 1L
    }
  }
}

# Check: pooled/suppressed categories were not re-invented (NON-DECLARABLE)
# REASONING: as in the Python block — __OTHER__ is required only where the report
# released it, and where every source level was pooled away (levels: [] with
# n_levels_binned > 0) the literal __OTHER__ is the one level a generator may emit.
if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] suppressed_categories_absent: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (length(cpsg_cat_cols) == 0) {
  cat(sprintf("[PASS] suppressed_categories_absent: 0 categorical columns declared at tier %s, 0 pooled buckets to preserve\n",
              cpsg_tier_label))
  cps_gen["passed"] <- cps_gen["passed"] + 1L
} else {
  cpsg_bad <- character(0)
  cpsg_absent <- character(0)
  cpsg_pools <- 0L
  cpsg_checked <- 0L
  for (cpsg_entry in cpsg_cat_entries) {
    cpsg_name <- cpsg_entry$name
    if (!is.na(cpsg_entry$problem)) {
      cpsg_absent <- c(cpsg_absent, cpsg_entry$problem)
      next
    }
    cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
    if (!(cpsg_name %in% cpsg_syn_names)) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' has released levels but is absent from the synthetic frame", cpsg_ename))
      next
    }
    if (cpsg_name %in% cpsg_untextable) {
      cpsg_bad <- c(cpsg_bad, sprintf("column '%s' %s — its levels cannot be compared", cpsg_ename, cpsg_untextable_msg))
      next
    }
    # REASONING: the pool is judged against the report's pool count, so an unusable
    # count is missing evidence, not a pass.
    if (is.na(cpsg_entry$binned)) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' categorical block carries no whole-number n_levels_binned", cpsg_ename))
      next
    }
    cpsg_checked <- cpsg_checked + 1L
    cpsg_bool <- cpsg_syn_class[match(cpsg_name, cpsg_syn_names)] == "boolean"
    cpsg_released <- cpsg_entry$values
    if (cpsg_bool) cpsg_released <- ifelse(tolower(cpsg_released) %in% c("true", "false"), tolower(cpsg_released), cpsg_released)
    cpsg_released <- unique(cpsg_released)
    cpsg_observed <- cpsg_tc_values[[match(cpsg_name, cpsg_tc_names)]]
    cpsg_pool_only <- if (length(cpsg_entry$values) == 0 && cpsg_entry$binned > 0) 1L else 0L
    if (length(cpsg_observed) > length(cpsg_released) + cpsg_pool_only) {
      cpsg_bad <- c(cpsg_bad, sprintf("column '%s' carries %d distinct synthetic levels against %d released",
                                      cpsg_ename, length(cpsg_observed), length(cpsg_released)))
    }
    if ("__OTHER__" %in% cpsg_entry$values) {
      cpsg_pools <- cpsg_pools + 1L
      if (!("__OTHER__" %in% cpsg_observed)) {
        cpsg_bad <- c(cpsg_bad, sprintf("column '%s' pooled %.0f source levels but the synthetic frame has no __OTHER__ bucket",
                                        cpsg_ename, cpsg_entry$binned))
      }
    }
  }
  if (length(cpsg_bad) > 0) {
    cat(sprintf("[FAIL] suppressed_categories_absent: %s%s\n", cpsg_bad[1],
                if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
    cps_gen["failed"] <- cps_gen["failed"] + 1L
  } else if (length(cpsg_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] suppressed_categories_absent: %s%s\n", cpsg_absent[1],
                if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
    cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] suppressed_categories_absent: %d categorical columns examined, %d pooled buckets preserved, 0 levels added\n",
                cpsg_checked, cpsg_pools))
    cps_gen["passed"] <- cps_gen["passed"] + 1L
  }
}

# Check: reproduced correlations sit within tolerance of the released matrix
# REASONING: ONE absolute band, `correlation_tolerance`, for every released pair; the
# wider +/-0.20 binary/low-cardinality allowance is a QAS-C reviewer judgement, never
# applied here. Below tier 3 nothing is released ([SKIPPED]); at tier 3 the spec always
# carries a pearson block, so its absence is missing evidence ([NOT VERIFIED]).
cpsg_pearson <- NULL
if (is.list(cpsg_relationships) && is.list(cpsg_relationships[["pearson"]]) &&
    !is.null(names(cpsg_relationships[["pearson"]]))) {
  cpsg_pearson <- cpsg_relationships[["pearson"]]
}
if ("correlations_within_tolerance" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] correlations_within_tolerance: %s\n", not_applicable[["correlations_within_tolerance"]]))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if ("correlations_within_tolerance" %in% cpsg_empty_reason) {
  cat("[NOT VERIFIED] correlations_within_tolerance: declared not_applicable with an empty reason\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] correlations_within_tolerance: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (!cpsg_tier_ok) {
  cat("[NOT VERIFIED] correlations_within_tolerance: tier is not a recorded 1/2/3/4\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (tier != 4 && cpsg_report_tier_ok && cpsg_report_tier != cpsg_release_tier) {
  cat(sprintf("[FAIL] correlations_within_tolerance: configured tier %d differs from the report's declared tier %d\n",
              cpsg_release_tier, as.integer(cpsg_report_tier)))
  cps_gen["failed"] <- cps_gen["failed"] + 1L
} else if (is.null(cpsg_release_tier)) {
  cat("[NOT VERIFIED] correlations_within_tolerance: tier 4 import, but the report declares no settings.tier of 1/2/3 — which blocks were released is unknown\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (cpsg_release_tier < 3) {
  cat(sprintf("[SKIPPED] correlations_within_tolerance: no available correlation matrix at tier %s — nothing was released to reproduce\n",
              cpsg_tier_label))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if (is.null(cpsg_pearson)) {
  cat(sprintf("[NOT VERIFIED] correlations_within_tolerance: the report at %s tier %s carries no pearson block — the released correlations cannot be compared\n",
              if (tier == 4) "declared" else "configured", cpsg_tier_label))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (identical(cpsg_pearson[["available"]], FALSE)) {
  cat(sprintf("[SKIPPED] correlations_within_tolerance: no available correlation matrix at tier %s — nothing was released to reproduce\n",
              cpsg_tier_label))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if (!identical(cpsg_pearson[["available"]], TRUE)) {
  cat("[NOT VERIFIED] correlations_within_tolerance: the pearson block carries no boolean available flag\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else {
  cpsg_cols <- cpsg_pearson[["columns"]]
  cpsg_rows <- cpsg_pearson[["matrix"]]
  cpsg_off <- character(0)
  cpsg_absent <- character(0)
  cpsg_bad <- character(0)
  cpsg_compared <- 0L
  # INTENT: columns must be an array of single strings and matrix an array, exactly
  # as the Python block requires (a list of str and a list).
  cpsg_names_ok <- is.list(cpsg_cols) && is.null(names(cpsg_cols))
  for (cpsg_c in if (cpsg_names_ok) cpsg_cols else list()) {
    if (!(is.character(cpsg_c) && length(cpsg_c) == 1 && !is.na(cpsg_c))) cpsg_names_ok <- FALSE
  }
  cpsg_names <- if (cpsg_names_ok) as.character(unlist(cpsg_cols)) else character(0)
  cpsg_enames <- cpsg_esc_to[match(cpsg_names, cpsg_esc_from)]
  cpsg_rows_ok <- is.list(cpsg_rows) && is.null(names(cpsg_rows))
  # INTENT: Confirm the released matrix is square with dimension == length(columns)
  # before any positional indexing.
  # REASONING: Indexing a short matrix by column position raises "subscript out of
  # bounds", which aborts the block before the remaining checks report — the single
  # outcome this checkpoint exists to prevent. The shape discrepancy is itself the
  # finding, so it is named (counts only, no coefficients) and the pair loop skipped.
  cpsg_shape_ok <- cpsg_rows_ok && length(cpsg_rows) == length(cpsg_names)
  cpsg_dim <- 0L
  for (cpsg_r in if (cpsg_rows_ok) cpsg_rows else list()) {
    if (is.list(cpsg_r) && is.null(names(cpsg_r))) {
      cpsg_dim <- max(cpsg_dim, length(cpsg_r))
      if (length(cpsg_r) != length(cpsg_names)) cpsg_shape_ok <- FALSE
    } else {
      cpsg_shape_ok <- FALSE
    }
  }
  cpsg_nonnum <- character(0)
  for (cpsg_c in cpsg_names) {
    cpsg_idx <- match(cpsg_c, cpsg_syn_names)
    if (!is.na(cpsg_idx) && !(cpsg_syn_class[cpsg_idx] %in% c("integer", "float"))) cpsg_nonnum <- c(cpsg_nonnum, cpsg_c)
  }
  if (!cpsg_names_ok || !cpsg_rows_ok) {
    cpsg_absent <- c(cpsg_absent, "the available pearson block carries no columns/matrix pair")
  } else if (!cpsg_shape_ok) {
    cpsg_bad <- c(cpsg_bad, sprintf("released pearson block declares %d columns but carries an %dx%d matrix",
                                    length(cpsg_names), length(cpsg_rows), as.integer(cpsg_dim)))
  } else if (!all(cpsg_names %in% cpsg_syn_names)) {
    cpsg_absent <- c(cpsg_absent, "a correlated column is absent from the synthetic frame")
  } else if (length(cpsg_nonnum) > 0) {
    # REASONING: the synthetic column is under validation, so one outside the integer
    # and float classes is a [FAIL]; cor() on it would stop the block.
    cpsg_bad <- c(cpsg_bad, sprintf("column '%s' is correlated in the report but not numeric in the synthetic frame",
                                    cpsg_esc_to[match(cpsg_nonnum[1], cpsg_esc_from)]))
  } else {
    for (cpsg_i in seq_along(cpsg_names)) {
      if (cpsg_i == length(cpsg_names)) break
      for (cpsg_j in seq(cpsg_i + 1, length(cpsg_names))) {
        cpsg_target <- cpsg_rows[[cpsg_i]][[cpsg_j]]
        # REASONING: a null or non-number coefficient is wrong-typed evidence.
        if (!(is.numeric(cpsg_target) && length(cpsg_target) == 1 && !is.na(cpsg_target) &&
              abs(cpsg_target) < cpsg_max_exact)) {
          cpsg_absent <- c(cpsg_absent, sprintf("the released pearson matrix carries no usable coefficient for pair (%s, %s)",
                                                cpsg_enames[cpsg_i], cpsg_enames[cpsg_j]))
          next
        }
        # ASSUMES: complete cases only (non-NA, non-NaN on both sides), as the Python
        # block filters; fewer than two pairs has no correlation (cor() would stop).
        cpsg_x <- suppressWarnings(as.numeric(cpsg_syn[[match(cpsg_names[cpsg_i], cpsg_syn_names)]]))
        cpsg_y <- suppressWarnings(as.numeric(cpsg_syn[[match(cpsg_names[cpsg_j], cpsg_syn_names)]]))
        cpsg_cc <- !is.na(cpsg_x) & !is.na(cpsg_y)
        cpsg_obs <- if (sum(cpsg_cc) < 2) NA_real_ else suppressWarnings(cor(cpsg_x[cpsg_cc], cpsg_y[cpsg_cc]))
        if (!(is.numeric(cpsg_obs) && length(cpsg_obs) == 1 && is.finite(cpsg_obs))) {
          cpsg_absent <- c(cpsg_absent, sprintf("the synthetic pair (%s, %s) has no defined correlation",
                                                cpsg_enames[cpsg_i], cpsg_enames[cpsg_j]))
          next
        }
        cpsg_compared <- cpsg_compared + 1L
        if (abs(cpsg_obs - cpsg_target) > correlation_tolerance) {
          cpsg_off <- c(cpsg_off, sprintf("pair (%s, %s) deviates by %.4f",
                                          cpsg_enames[cpsg_i], cpsg_enames[cpsg_j], abs(cpsg_obs - cpsg_target)))
        }
      }
    }
  }
  if (length(cpsg_bad) > 0) {
    cat(sprintf("[FAIL] correlations_within_tolerance: %s%s\n", cpsg_bad[1],
                if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
    cps_gen["failed"] <- cps_gen["failed"] + 1L
  } else if (length(cpsg_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] correlations_within_tolerance: %s%s\n", cpsg_absent[1],
                if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
    cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
  } else if (cpsg_compared == 0) {
    cat(sprintf("[NOT VERIFIED] correlations_within_tolerance: the available pearson block names %d columns but 0 pairs were compared\n",
                length(cpsg_names)))
    cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
  } else if (length(cpsg_off) > 0) {
    cat(sprintf("[WARNING] correlations_within_tolerance: %d of %d pairs outside the correlation_tolerance band +/-%.4g — %s\n",
                length(cpsg_off), cpsg_compared, correlation_tolerance, cpsg_off[1]))
    cps_gen["warning"] <- cps_gen["warning"] + 1L
  } else {
    cat(sprintf("[PASS] correlations_within_tolerance: %d released pairs reproduced within the correlation_tolerance band +/-%.4g\n",
                cpsg_compared, correlation_tolerance))
    cps_gen["passed"] <- cps_gen["passed"] + 1L
  }
}

# Check: every synthetic level lies inside the released level set (NON-DECLARABLE)
# REASONING: compared through the canonical text form; the literal __OTHER__ is also
# admissible where every source level was pooled away, as in the Python block.
if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] synthetic_levels_within_released_levels: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (length(cpsg_cat_cols) == 0) {
  cat(sprintf("[PASS] synthetic_levels_within_released_levels: 0 categorical columns declared at tier %s, 0 level sets to police\n",
              cpsg_tier_label))
  cps_gen["passed"] <- cps_gen["passed"] + 1L
} else {
  cpsg_bad <- character(0)
  cpsg_absent <- character(0)
  cpsg_checked <- 0L
  cpsg_levels_seen <- 0L
  for (cpsg_entry in cpsg_cat_entries) {
    cpsg_name <- cpsg_entry$name
    if (!is.na(cpsg_entry$problem)) {
      cpsg_absent <- c(cpsg_absent, cpsg_entry$problem)
      next
    }
    cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
    if (!(cpsg_name %in% cpsg_syn_names)) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' is absent from the synthetic frame", cpsg_ename))
      next
    }
    if (cpsg_name %in% cpsg_untextable) {
      cpsg_bad <- c(cpsg_bad, sprintf("column '%s' %s — its levels cannot be compared", cpsg_ename, cpsg_untextable_msg))
      next
    }
    cpsg_checked <- cpsg_checked + 1L
    cpsg_bool <- cpsg_syn_class[match(cpsg_name, cpsg_syn_names)] == "boolean"
    cpsg_released <- cpsg_entry$values
    if (cpsg_bool) cpsg_released <- ifelse(tolower(cpsg_released) %in% c("true", "false"), tolower(cpsg_released), cpsg_released)
    if (length(cpsg_entry$values) == 0 && !is.na(cpsg_entry$binned) && cpsg_entry$binned > 0) cpsg_released <- c(cpsg_released, "__OTHER__")
    cpsg_observed <- cpsg_tc_values[[match(cpsg_name, cpsg_tc_names)]]
    cpsg_levels_seen <- cpsg_levels_seen + length(cpsg_observed)
    cpsg_outside <- cpsg_observed[!(cpsg_observed %in% cpsg_released)]
    if (length(cpsg_outside) > 0) {
      cpsg_bad <- c(cpsg_bad, sprintf("column '%s' carries %d synthetic levels outside the released set",
                                      cpsg_ename, length(cpsg_outside)))
    }
  }
  if (length(cpsg_bad) > 0) {
    cat(sprintf("[FAIL] synthetic_levels_within_released_levels: %s%s\n", cpsg_bad[1],
                if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
    cps_gen["failed"] <- cps_gen["failed"] + 1L
  } else if (length(cpsg_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] synthetic_levels_within_released_levels: %s%s\n", cpsg_absent[1],
                if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
    cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] synthetic_levels_within_released_levels: %d columns, %d distinct synthetic levels, all inside the released sets\n",
                cpsg_checked, cpsg_levels_seen))
    cps_gen["passed"] <- cps_gen["passed"] + 1L
  }
}

# Check: synthetic identifiers are structurally shaped but value-free (NON-DECLARABLE)
if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] identifier_columns_value_free: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (length(cpsg_id_cols) == 0) {
  cat(sprintf("[PASS] identifier_columns_value_free: 0 identifier columns declared at tier %s\n", cpsg_tier_label))
  cps_gen["passed"] <- cps_gen["passed"] + 1L
} else {
  # ASSUMES: a released label is a string (the profiler's own shape), as in Python; a
  # boolean identifier column is compared with the labels case-insensitively.
  cpsg_released_values <- character(0)
  for (cpsg_entry in cpsg_cat_entries) {
    cpsg_released_values <- c(cpsg_released_values, cpsg_entry$values)
  }
  cpsg_released_bool <- ifelse(tolower(cpsg_released_values) %in% c("true", "false"), tolower(cpsg_released_values), cpsg_released_values)
  cpsg_bad <- character(0)
  cpsg_absent <- character(0)
  cpsg_checked <- 0L
  for (cpsg_col in cpsg_id_cols) {
    cpsg_name <- cpsg_col[["name"]]
    if (!(is.character(cpsg_name) && length(cpsg_name) == 1 && !is.na(cpsg_name))) {
      cpsg_absent <- c(cpsg_absent, "an identifier column record carries no string name")
      next
    }
    cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
    if (!(cpsg_name %in% cpsg_syn_names)) {
      cpsg_absent <- c(cpsg_absent, sprintf("identifier column '%s' is absent from the synthetic frame", cpsg_ename))
      next
    }
    if (cpsg_name %in% cpsg_untextable) {
      cpsg_bad <- c(cpsg_bad, sprintf("identifier column '%s' %s", cpsg_ename, cpsg_untextable_msg))
      next
    }
    cpsg_checked <- cpsg_checked + 1L
    cpsg_ti <- match(cpsg_name, cpsg_tc_names)
    if (any(cpsg_tc_counts[[cpsg_ti]] > 1)) {
      cpsg_bad <- c(cpsg_bad, sprintf("identifier column '%s' is not unique across rows", cpsg_ename))
    }
    cpsg_against <- if (cpsg_syn_class[match(cpsg_name, cpsg_syn_names)] == "boolean") cpsg_released_bool else cpsg_released_values
    if (any(cpsg_tc_values[[cpsg_ti]] %in% cpsg_against)) {
      cpsg_bad <- c(cpsg_bad, sprintf("identifier column '%s' reuses a value from a released level set", cpsg_ename))
    }
  }
  if (length(cpsg_bad) > 0) {
    cat(sprintf("[FAIL] identifier_columns_value_free: %s%s\n", cpsg_bad[1],
                if (length(cpsg_bad) > 1) sprintf(" (+%d more)", length(cpsg_bad) - 1) else ""))
    cps_gen["failed"] <- cps_gen["failed"] + 1L
  } else if (length(cpsg_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] identifier_columns_value_free: %s%s\n", cpsg_absent[1],
                if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
    cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
  } else {
    cat(sprintf("[PASS] identifier_columns_value_free: %d identifier columns, all-unique scaffolds, 0 released values reused\n",
                cpsg_checked))
    cps_gen["passed"] <- cps_gen["passed"] + 1L
  }
}

# Check: per-column null rates reproduce the reported missingness
if ("missingness_within_tolerance" %in% names(not_applicable)) {
  cat(sprintf("[SKIPPED] missingness_within_tolerance: %s\n", not_applicable[["missingness_within_tolerance"]]))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else if ("missingness_within_tolerance" %in% cpsg_empty_reason) {
  cat("[NOT VERIFIED] missingness_within_tolerance: declared not_applicable with an empty reason\n")
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (is.null(cpsg_syn) || is.null(cpsg_report)) {
  cat(sprintf("[NOT VERIFIED] missingness_within_tolerance: %s\n", cpsg_inputs_error))
  cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
} else if (length(cpsg_rated) == 0) {
  cat(sprintf("[SKIPPED] missingness_within_tolerance: report declares 0 missingness targets at tier %s\n",
              cpsg_tier_label))
  cps_gen["skipped"] <- cps_gen["skipped"] + 1L
} else {
  cpsg_off <- character(0)
  cpsg_absent <- character(0)
  cpsg_compared <- 0L
  for (cpsg_col in cpsg_rated) {
    cpsg_name <- cpsg_col[["name"]]
    cpsg_target <- cpsg_col[["missing_rate"]]
    if (!(is.character(cpsg_name) && length(cpsg_name) == 1 && !is.na(cpsg_name))) {
      cpsg_absent <- c(cpsg_absent, "a column record with a missingness target carries no string name")
      next
    }
    cpsg_ename <- cpsg_esc_to[match(cpsg_name, cpsg_esc_from)]
    cpsg_idx <- match(cpsg_name, cpsg_syn_names)
    if (is.na(cpsg_idx)) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' has a missingness target but is absent from the synthetic frame", cpsg_ename))
      next
    }
    if (!(is.numeric(cpsg_target) && length(cpsg_target) == 1 && !is.na(cpsg_target) &&
          abs(cpsg_target) < cpsg_max_exact)) {
      cpsg_absent <- c(cpsg_absent, sprintf("column '%s' carries a non-numeric missing_rate target", cpsg_ename))
      next
    }
    cpsg_compared <- cpsg_compared + 1L
    # ASSUMES: the stored null count comes from arrow, as polars reports it; NaN adds
    # to it in a float column (is.nan(), since a null converts to NA, never NaN).
    cpsg_n_missing <- cpsg_syn_nulls[cpsg_idx]
    if (cpsg_syn_class[cpsg_idx] == "float") cpsg_n_missing <- cpsg_n_missing + sum(is.nan(cpsg_syn[[cpsg_idx]]))
    cpsg_obs <- if (cpsg_syn_nrow > 0) cpsg_n_missing / cpsg_syn_nrow else 0
    if (abs(cpsg_obs - cpsg_target) > missingness_tolerance) {
      cpsg_off <- c(cpsg_off, sprintf("column '%s' null rate is off by %.4f", cpsg_ename, abs(cpsg_obs - cpsg_target)))
    }
  }
  if (length(cpsg_absent) > 0) {
    cat(sprintf("[NOT VERIFIED] missingness_within_tolerance: %s%s\n", cpsg_absent[1],
                if (length(cpsg_absent) > 1) sprintf(" (+%d more)", length(cpsg_absent) - 1) else ""))
    cps_gen["not_verified"] <- cps_gen["not_verified"] + 1L
  } else if (length(cpsg_off) > 0) {
    cat(sprintf("[WARNING] missingness_within_tolerance: %d of %d columns outside +/-%.4g — %s\n",
                length(cpsg_off), cpsg_compared, missingness_tolerance, cpsg_off[1]))
    cps_gen["warning"] <- cps_gen["warning"] + 1L
  } else {
    cat(sprintf("[PASS] missingness_within_tolerance: %d columns, all null rates within +/-%.4g of the reported rate\n",
                cpsg_compared, missingness_tolerance))
    cps_gen["passed"] <- cps_gen["passed"] + 1L
  }
}

# Check: the generation seed is recorded and printed (NON-DECLARABLE)
# REASONING: same five outcomes as the Python block. seed_exception (a pointer to the
# researcher's T4 missing-seed authorization in STATE) is honored only at tier 4 with
# no seed, yields a [WARNING] — never a [PASS] — and its value is never printed; with
# neither a seed nor an exception the outcome is [FAIL]. The check reads only the
# config, so it runs whether or not the report parsed. A whole seed prints via %.0f of
# seed + 0 — never as.integer(), which turns a seed above 2^31 into NA, and the + 0
# turns a negative zero into 0, as Python's int() does. seed_exception is blank under
# the same Unicode whitespace set as the not_applicable reasons.
cpsg_exception_set <- is.character(seed_exception) && length(seed_exception) == 1 &&
  !is.na(seed_exception) && nzchar(trimws(seed_exception, whitespace = cpsg_ws))
cpsg_seed_ok <- is.numeric(seed) && length(seed) == 1 && !is.na(seed) &&
  abs(seed) < cpsg_max_exact && seed == floor(seed)
if (cpsg_exception_set && !is.null(seed)) {
  cat("[FAIL] seed_recorded: seed and seed_exception are both set — record one\n")
  cps_gen["failed"] <- cps_gen["failed"] + 1L
} else if (cpsg_exception_set && !(cpsg_tier_ok && tier == 4)) {
  cat("[FAIL] seed_recorded: seed_exception is honored only at tier 4\n")
  cps_gen["failed"] <- cps_gen["failed"] + 1L
} else if (cpsg_exception_set) {
  cat("[WARNING] seed_recorded: tier 4 import with no recorded seed — researcher-authorized non-reproducible T4 exception (authorization recorded in STATE)\n")
  cps_gen["warning"] <- cps_gen["warning"] + 1L
} else if (!cpsg_seed_ok) {
  cat("[FAIL] seed_recorded: the generation seed is not an integer recorded in this script's config\n")
  cps_gen["failed"] <- cps_gen["failed"] + 1L
} else {
  cat(sprintf("[PASS] seed_recorded: generation seed %.0f present in the script config and printed to the log\n",
              as.numeric(seed) + 0))
  cps_gen["passed"] <- cps_gen["passed"] + 1L
}

# Count line, then verdict derived from the counts
cpsg_checks_run <- cps_gen[["passed"]] + cps_gen[["warning"]] + cps_gen[["failed"]]
if (cps_gen[["failed"]] > 0 || cps_gen[["not_verified"]] > 0 || cpsg_checks_run == 0) {
  cpsg_verdict <- "FAILED"
} else if (cps_gen[["warning"]] > 0) {
  cpsg_verdict <- "PASSED WITH WARNINGS"
} else {
  cpsg_verdict <- "PASSED"
}

cat(sprintf("\nChecks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cps_gen[["passed"]], cps_gen[["warning"]], cps_gen[["failed"]],
            cps_gen[["not_verified"]], cps_gen[["skipped"]]))
cat(sprintf("CPS-GEN VALIDATION: %s\n", cpsg_verdict))
cat(strrep("=", 60), "\n")

if (cpsg_verdict == "FAILED") {
  stop("CPS-GEN FAILED - see details above")
}
```

**`not_applicable` keys recognized by CPS-GEN:** `row_count_matches`, `column_set_and_dtypes`, `numeric_marginals_within_tolerance`, `categorical_proportions_within_tolerance`, `correlations_within_tolerance`, `missingness_within_tolerance`. The remaining four keys — `suppressed_categories_absent`, `synthetic_levels_within_released_levels`, `identifier_columns_value_free`, `seed_recorded` — are **non-declarable**.

### CPS Usage Notes

**Applicability keys.** The declarable and non-declarable sets, in one place:

| Checkpoint | Declarable `not_applicable` keys | Non-declarable keys |
|------------|----------------------------------|---------------------|
| CPS-INTAKE | `report_version`, `required_top_level_keys`, `row_count_positive`, `percentiles_monotone`, `category_counts_le_rowcount`, `missing_rate_in_unit_interval`, `correlation_matrix_wellformed`, `embedded_validation_complete` | `no_released_count_below_threshold`, `no_raw_value_shaped_fields`, `identifier_columns_value_free`, `crosstab_schema_and_suppression` |
| CPS-GEN | `row_count_matches`, `column_set_and_dtypes`, `numeric_marginals_within_tolerance`, `categorical_proportions_within_tolerance`, `correlations_within_tolerance`, `missingness_within_tolerance` | `suppressed_categories_absent`, `synthetic_levels_within_released_levels`, `identifier_columns_value_free`, `seed_recorded` |

Declaring a non-declarable key emits `[FAIL] <check>: non-declarable check declared not_applicable under key '<key>'`, counts one failure, **and runs the check anyway** on the un-declared path — so the log carries both the contract violation and the check's own finding.

**An unrecognized `not_applicable` key is a failure, not a no-op.** After the non-declarable sweep, any remaining key that is not in the block's declarable set above emits `[FAIL] not_applicable: unrecognized key '<key>' (declarable keys: …)` exactly once and counts one failure. A typo'd or stale key would otherwise declare nothing at all, leaving the author believing a check was skipped when it in fact ran — the log has to carry that discrepancy. Both sweeps see the key whether or not its reason was non-empty, so dropping a reason cannot be used to slip a declaration past either gate. The reviewer applies the equivalent rule under the QAS key names with `[BLOCKER]` in place of `[FAIL]` (`QA_CHECKPOINTS.md` § QAS Applicability Declarations); the sets differ by construction — CPS-GEN additionally treats `seed_recorded` as non-declarable.

**A declarable key with an empty reason is `[NOT VERIFIED]`, not a silent run.** A declaration whose reason is missing, empty, or whitespace is dropped from the applicability map, but the check it names does **not** then run: it reports `[NOT VERIFIED] <check>: declared not_applicable with an empty reason`, counts one not-verified, and fails the checkpoint. Running it anyway and printing `[PASS]` would answer a question the author explicitly withdrew; skipping it silently would lose the withdrawal. Non-declarable keys are unaffected — they keep their `[FAIL]` and still run, because no reason can make a disclosure-critical check optional.

**What the tolerances actually compare (CPS-GEN).** `numeric_tolerance` is a **relative** tolerance applied per reproduced percentile, with a floor of 1.0 in absolute terms so a target near zero does not demand impossible precision — the live comparison is `abs(cpsg_obs - cpsg_target) > numeric_tolerance * max(abs(cpsg_target), 1.0)`. The other three (`proportion_tolerance`, `correlation_tolerance`, `missingness_tolerance`) are plain absolute bands on quantities already expressed in [0,1] or [-1,1]. All four comparisons are strict `>`: a deviation landing exactly on the tolerance passes. The `synthetic-data-workflow` skill's § Tolerances states the same rule; if the two ever disagree, this section is the code and therefore the fact. CPS-GEN applies **one** correlation band, `correlation_tolerance`, to every released pair. The wider ±0.20 band for binary or low-cardinality pairs is a QAS-C reviewer allowance only. The block never applies it, and its PASS/WARNING lines name `the correlation_tolerance band` so they cannot be read as implying it. Percentiles are recomputed with linear interpolation over non-null, non-NaN values (polars `interpolation="linear"`, R `quantile(type = 7)`), and correlations use complete cases only. Tolerances print with `%.4g`, so both languages compute and print the same numbers. Both blocks read the same frame. Python reads the parquet's raw schema first (`pyarrow.parquet.read_schema`), to refuse a repeated column name, and then the frame with polars. R reads it with arrow as a Table and converts one column at a time, never through `as.data.frame()`, because a polars `Categorical` column does not convert to a factor; a dictionary-encoded string column is cast to plain strings on the arrow side first. Null counts are the stored ones in both languages, and in a float column a NaN also counts as missing, for missingness, quantiles, correlations, and level text alike.

**CPS-GEN never stops early, and both languages print the same lines (CPS-GEN).** Every check reaches its own outcome line on any input, followed by the count line and the verdict. A value of the wrong type follows one rule. If it sits in the synthetic frame, which is what is being validated, the outcome is `[FAIL]`: a non-numeric column with a released percentile grid or correlation, a column outside the text-comparable types compared with released labels (see **Synthetic column types and the canonical text form** below), or a declared dtype the frame does not hold. If it is report evidence a check needs, the outcome is `[NOT VERIFIED]`. Examples are a null percentile or correlation coefficient, a level entry that is not a `{value: <string>, count: <whole number>}` pair (named by its index, never its label or count), a column record with no string name, and a missing or non-whole `n` / `n_levels_binned`. The numeric model is the one CPS-INTAKE uses: finite, `|v| < 2^53`, and whole numbers compared by value. Every outcome line is byte-identical between the Python and R blocks on the same input, and declared dtypes and parser messages are never echoed.

**Strict report parsing (CPS-GEN).** A `NaN`, `Infinity` or `-Infinity` literal, a duplicate object key at any depth, or nesting deeper than 64 levels (counting the top-level object as level 1; a well-formed report stays far below that) is a parse error in both languages — the same three rules and the same cap as CPS-INTAKE. Python uses `parse_constant` plus one iterative sweep over an `object_pairs_hook=list` parse that refuses both a duplicate key and a depth above 64, and it catches `RecursionError`. R uses one iterative sweep that refuses both a repeated name (`anyDuplicated(names())`) and a depth above 64, because jsonlite keeps every duplicate key while Python's dict keeps only the last, and the two parsers give up at different depths. Every check that reads the report then prints `[NOT VERIFIED] <check>: report did not parse as JSON (parser message withheld: it can quote report content)`. `seed_recorded` reads only the script config, so it still runs.

Six more inputs are refused the same way, before either parser runs, because the two parsers would otherwise read them differently. Both blocks decide them on the file's bytes, its escape sequences, and its number tokens:
- a leading UTF-8 byte-order mark (jsonlite accepts it with a warning, `json.loads` refuses it);
- a raw NUL byte anywhere in the file (R's text reader would stop at it);
- bytes that are not valid UTF-8;
- an escaped NUL, `\u0000`, inside a string (jsonlite cuts the string there, Python keeps it);
- an unpaired surrogate escape: a `\ud800`–`\udbff` not immediately followed by a `\udc00`–`\udfff`, or a low surrogate with no high one before it (jsonlite replaces it, Python keeps it). A correctly paired escape, such as `\ud83d\ude00`, is accepted;
- a number token longer than 64 characters outside a string, with sign, digits, fraction and exponent counted together (Python refuses an integer past its 4300-digit conversion limit, while jsonlite reads it as `Inf` and parses on). No profiler writes a number anywhere near that long (a double needs at most 24 characters), and a token of 64 characters or fewer parses as before.

The escape scan reads an escaped backslash as one token, so the six characters `\\u0000` (a literal backslash, then `u0000`) are text, not an escaped NUL, and parse normally. The number scan matches each string whole before it looks for numbers, so digits inside a string never count, and both blocks use the same pattern for it.

**Synthetic column types and the canonical text form (CPS-GEN).** Each synthetic column is classified once by its stored type, and both languages derive the same class:

| Class | Python (polars) | R (arrow type) |
|---|---|---|
| text | `String` | `string`, `large_string`, `string_view` |
| text_dict | `Categorical`, `Enum` | a dictionary of string values (a factor) |
| integer | `Int8`–`Int64`, `UInt8`–`UInt64` | `int8`–`int64`, `uint8`–`uint64` |
| float | `Float32`, `Float64` | `float`, `double` |
| boolean | `Boolean` | `bool` |
| other | every other type: decimal, half float, date, time, timestamp, duration, binary, nested, null | the same |

An "other" column's values are never compared, because the two readers disagree on them: arrow hands R a half float as its raw bits and a decimal as a double. An integer column holding any magnitude of 2^53 or more is treated the same way when its values must be compared with labels, because R receives such a column as doubles and its text would no longer be exact. A check that has to compare such a column with released labels is a `[FAIL]`. The categorical checks print `column '<c>' holds values outside the text-comparable types (string, categorical, integer below 2^53, float, boolean) — its levels cannot be compared`, and `identifier_columns_value_free` prints `identifier column '<c>' holds values outside the text-comparable types (string, categorical, integer below 2^53, float, boolean)`.

`column_set_and_dtypes` judges a declared dtype by class. `string` needs a text column, so a categorical, Enum, or factor column fails with `column '<c>' is not a string column, the report declares string`. `double` needs an integer or float column. `integer` needs an integer column, or a float column whose non-missing values are all whole, which is what R can still claim after arrow's round trip.

Where a synthetic value is compared with a released level label, which is always a string, both blocks first reduce it to one canonical text, built to match the labels both profilers write (pandas `astype(str)` in Python, `as.character()` in R):
- text and text_dict values compare as written;
- an integer, or a finite float with a whole value, is `%.0f` of `v + 0`, so `1`, `1.0`, and the label `"1"` agree and `-0` prints as `0`;
- any other finite float is `%.17g` text, and an infinity is `inf` or `-inf`;
- NaN counts as missing, as it does in the missingness check and in R's `is.na()`;
- a boolean is `true` or `false`, and a released `true`/`false` label is then compared case-insensitively, so the Python profiler's `True` and the R profiler's `TRUE` both match.

A column whose class does not match its declared dtype (an integer-coded column where the report declares `string`, say) still fails `column_set_and_dtypes`, but the level checks compare its values through this text form rather than giving up on it.

**`__OTHER__` (CPS-GEN).** `suppressed_categories_absent` requires a synthetic `__OTHER__` bucket only where `__OTHER__` is among the column's released levels. A column whose every source level was pooled away (`levels: []` with `n_levels_binned > 0`, the profiler's shape when the non-missing count is below the threshold) may carry the literal `__OTHER__` as its one level: it names the withheld pool and carries no source value, so a generator can reproduce the column's non-missing count without inventing a label. Both `suppressed_categories_absent` and `synthetic_levels_within_released_levels` admit it for such a column, and any other value there is a level outside the released set. A column with `levels: []` and `n_levels_binned` of 0 admits no value at all, so it can only be entirely null.

**Repeated column names (CPS-GEN).** A synthetic parquet that stores the same column name twice is unreadable in both languages. Every check that reads the frame prints `[NOT VERIFIED] <check>: the synthetic parquet did not read (reader message withheld: the two readers word it differently)`, so the verdict is `FAILED`. Polars on its own would keep one of the repeats and read the file without complaint, while arrow sees every column. Python therefore checks the raw parquet schema before reading the frame.

**Escaping and blank strings (CPS-GEN).** Every report-derived or frame-derived string an outcome line prints (column names, keys, percentile keys) is escaped identically in both languages. A character outside printable ASCII (0x20–0x7E), including control characters, newlines, and all non-ASCII, prints as `\uXXXX` in lowercase hex, and a character above U+FFFF prints as its UTF-16 surrogate pair. A column named `café` prints as `caf\u00e9`, and a name carrying a newline cannot forge a second outcome line. Each run builds one escape table from every key and string value of the parsed report and every synthetic column name. Config strings (paths, `not_applicable` reasons) are the researcher's own and print as written. "Empty" or "blank", for a `not_applicable` reason or for `seed_exception`, means Unicode whitespace only: exactly the 29 code points Python's `str.strip()` removes (U+0009–U+000D, U+001C–U+001F, U+0020, U+0085, U+00A0, U+1680, U+2000–U+200A, U+2028, U+2029, U+202F, U+205F, U+3000). R spells that class out, because `trimws()` strips only `[ \t\r\n]` by default and PCRE's `[\h\v]` lacks U+001C–U+001F and adds U+180E. So a reason made only of no-break or ideographic spaces is blank in both languages, and one made only of U+180E is not blank in either.

**A fidelity check that compared nothing is `[NOT VERIFIED]` (CPS-GEN).** `numeric_marginals_within_tolerance`, `categorical_proportions_within_tolerance` and `correlations_within_tolerance` never print `[PASS]` over zero comparisons. Examples are a released grid of null or empty percentiles, or a one-column pearson block. A target that could not be used, because a value is not a number or a column is absent or entirely null, is counted in the outcome line (`… (+N more)`) instead of being silently skipped. A report that declares no target of the role at all (no numeric columns, or only withheld/constant/all-missing shapes) remains `[SKIPPED]`: a structural fact, not missing evidence.

**Correlations at tier 3 (CPS-GEN).** CPS-GEN's config `tier` is the tier the report was produced at: its `settings.tier`, copied from the report the generation targeted, and `4` only for a T4 import (see below). It is not the approved tier that CPS-INTAKE's config `tier` carries, which a report may sit below. Below tier 3 nothing is released, so `correlations_within_tolerance` is `[SKIPPED]`. A tier 3 report always carries a pearson block, so one with no `relationships` object or no `pearson` block prints `[NOT VERIFIED] correlations_within_tolerance: the report at configured tier 3 carries no pearson block — the released correlations cannot be compared` (at tier 4 the line says `declared tier 3`, because the tier is then the report's own). A pearson block marked `available: false` is `[SKIPPED]` (nothing was released). One whose `available` is not a boolean is `[NOT VERIFIED]`. A configured tier of 1–3 that differs from a whole-number 1–3 in the report's `settings.tier` prints `[FAIL] correlations_within_tolerance: configured tier N differs from the report's declared tier M`. Without it, a mis-copied tier would pass unseen or mislead: a tier 2 report checked at tier 3 would read as a missing pearson block (`[NOT VERIFIED]`), and a tier 3 report checked at tier 2 would skip its released correlations. The comparison sits on `correlations_within_tolerance` because that is the one check whose outcome the tier decides; the other checks only print it. It therefore runs only when that check runs (not declared not applicable, and both inputs read). A report with no whole-number `settings.tier` of 1–3 is held to the configured tier.

**Tier 4 and `seed_exception` (CPS-GEN).** Config `tier` is `4` only for a T4 import; otherwise it is the report's own `settings.tier` (see **Correlations at tier 3** above). At tier 4, DS-5 imports the user's locally synthesized data, and the profile report's own `settings.tier` decides which blocks were released. A tier 4 run whose report declares no `settings.tier` of 1–3 is `[NOT VERIFIED]` on correlations. With a profile report, CPS-GEN runs in full at tier 4, with `seed` set to the seed from the user's T4 generation log. Without a profile report, CPS-GEN is **not run**. STATE's CPS-GEN row records `EXEMPT (T4, no profile report)`. Running the block with `report_path` unset is not an exemption path: every report-reading check is `[NOT VERIFIED]` and the verdict is `FAILED`. `seed_recorded` stays non-declarable and has five outcomes:

| Config | Outcome |
|---|---|
| valid whole-number `seed`, `seed_exception` unset | `[PASS] seed_recorded: generation seed <seed> present in the script config and printed to the log` |
| `seed` unset, `seed_exception` set, tier 4 | `[WARNING] seed_recorded: tier 4 import with no recorded seed — researcher-authorized non-reproducible T4 exception (authorization recorded in STATE)`, so the verdict is at best `PASSED WITH WARNINGS` |
| `seed_exception` set at tier 1–3 (or an unrecorded tier) | `[FAIL] seed_recorded: seed_exception is honored only at tier 4` |
| both set | `[FAIL] seed_recorded: seed and seed_exception are both set — record one` |
| neither | `[FAIL] seed_recorded: the generation seed is not an integer recorded in this script's config` |

`seed_exception` counts as set only when it is a string with visible content. It is a pointer to the researcher's gate-time authorization in STATE, and its value is never printed.

**What `identifier_columns_value_free` can and cannot show (CPS-GEN).** The CPS-GEN check tests exactly two things: that each synthetic identifier column is all-unique across rows, and that it reuses no value from any released categorical level set. It **cannot** detect a memorised real identifier, because the report never released identifier values to compare against — identifier columns cross the boundary as structure only (see CPS-INTAKE's own `identifier_columns_value_free`, which polices that). A `[PASS]` here means the scaffold is well-formed and collides with nothing the report disclosed; it is not evidence that the generator invented rather than remembered. The comparison runs through the canonical text form (see **Synthetic column types and the canonical text form** above), so a numeric synthetic identifier `1` or `1.0` collides with a released label `"1"`. A generator that numbers its identifiers from 0 or 1 will therefore fail against any integer-coded categorical; offset numeric identifiers past every released label instead.

**What `identifier_columns_value_free` allows (CPS-INTAKE).** The intake check is an **allow-list**, not a deny-list: an identifier column record may carry only the schema's column keys (`name`, `dtype`, `role`, `missing_rate`, `nonmissing_n`, `n_distinct`, `uniqueness_ratio`, `is_identifier`, `string_structure` — `profiling-script-spec.md` § Column metadata), and its `string_structure` may carry only `{n, length_min, length_mean, length_max, pattern_flags}` (the `n >= k` shape) **or** `{n, withheld, reason}` with `withheld` literally `true` (the `n < k` shape). Anything else at either level is `[FAIL] identifier_columns_value_free: column '<c>' carries non-structural key '<key>'`, naming the key and never its value; the `[PASS]` line reports how many identifier columns were examined and how many were withheld. A deny-list only catches the leak shapes someone thought of — `string_structure.example` walked past one — whereas the schema already says exactly which keys are legitimate. **At tier 1** — the approved `tier` or the report's own `settings.tier` — the allow-list shrinks to `{name, dtype}`, because tier 1 releases the schema only (`profiling-script-spec.md`: T1 columns are exactly `{name,dtype}`). Any other key on an identifier record, `string_structure` included, is then `[FAIL] identifier_columns_value_free: column '<c>' carries non-structural key '<key>'`, and the `string_structure` is not inspected further. Rule 4 of `no_raw_value_shaped_fields` already holds every other tier-1 record to `{name, dtype}`; this closes the identifier records it skips.

The allow-list reaches one level further and closes the type gap too. A `string_structure` that is present but not a JSON object — a bare string standing where the structure belongs — is `[FAIL] identifier_columns_value_free: column '<c>' carries a non-object 'string_structure'`. Inside the `n >= k` shape, `pattern_flags` is held to its five schema flags (`email`, `phone`, `date`, `id`, `free_text`): any other flag name is the same `carries non-structural key '<key>'` form, and a `pattern_flags` that is not a JSON object is `carries a non-object 'pattern_flags'`. A `withheld` key whose value is not literally `true` does not earn the withheld shape; it is reported as `carries non-structural key 'withheld'`. The typing and vocabulary rules of rule 4 (below) apply here as well. An allow-listed numeric key, or a `pattern_flags` entry, that holds anything other than a number, boolean, or `null` is `column '<c>' carries a non-numeric '<key>'`. A `dtype` or `role` outside its vocabulary is `column '<c>' carries a '<key>' outside the spec vocabulary`. A withheld `string_structure` whose `reason` is not `all_missing` or `insufficient_support` is `column '<c>' carries a 'reason' outside the spec vocabulary`. None of these forms echoes the offending value. Identifier columns are this check's alone — `no_raw_value_shaped_fields` rule 4 (below) applies the same allow-list pattern to every *other* column record and skips identifier records, so no column is held to two lists.

**Value-shaped keys can be scalars too.** `no_raw_value_shaped_fields` additionally flags any **string-valued** key named `example`, `examples`, `sample`, `first_value`, `last_value`, `mode_value`, `min_value`, `max_value`, `values`, `head`, or `tail` (case-insensitive) anywhere in the report tree, emitting `[FAIL] no_raw_value_shaped_fields: value-shaped key '<key>' at <json path>` — path and key name only, never the value — because a single released value is the one-row version of the dump the list rules catch.

**`collapsed: true` must actually collapse the table.** In `crosstab_schema_and_suppression` the collapsed flag bypasses the complementary-suppression scan (lone hidden cells and bridges, see **Complementary suppression** below) **only** when every cell in the entry is `null`. An entry flagged collapsed that still releases visible cells is `[FAIL] crosstab_schema_and_suppression: entry <index> is marked collapsed but still releases visible cells` (the positional index, nothing else) — otherwise the flag would switch off complementary-suppression detection while the recoverable cells stayed on the wire. The `[PASS]` line carries the count of fully collapsed entries alongside the cells examined and hidden.

**Each cross-tab entry is held to the spec's key allow-list.** `crosstab_schema_and_suppression` owns `relationships.crosstabs` outright, and rule 5 of `no_raw_value_shaped_fields` (below) does not walk it. An entry whose `available` is `true` may carry only `pair`, `n`, `available`, `rows`, `cols`, `cells`, `cells_suppressed`, and `collapsed`. Any other entry may carry only `pair`, `n`, `available`, and `reason`. It may also carry `rows`, `cols`, or `cells`, but only so the `still carries` finding can name them. Within those keys, `pair` must be two declared column names, `available` a JSON boolean, `n` a number (or boolean or `null`, the same rule as rule 4's numeric keys), and `collapsed` literally `true`. An unavailable entry's `reason` must be `ineligible_roles` or `insufficient_support`. On an available entry, `rows` and `cols` must be positive whole numbers and `cells` an array. These are fields the check validates, so a malformed one is a `[FAIL]`. There is no `[NOT VERIFIED]` branch for them. Each `[FAIL]` names the key, the pair label (see **Pair labels and cross-language parity** below), or the entry index, and never a value:
- `entry index <i> is not a JSON object`
- `entry index <i> carries a 'pair' that is not two declared column names`
- `entry index <i> names one column twice in its 'pair'`
- `entry index <i> repeats the pair of entry index <k>`
- `entry <label> carries a non-boolean 'available'`
- `entry <label> carries non-structural key '<key>'`, which also covers a `collapsed` that is not literally `true`
- `entry <label> carries a non-numeric 'n'`
- `unavailable entry <label> carries no reason`
- `unavailable entry <label> carries a reason outside the spec vocabulary`
- `unavailable entry <label> still carries '<key>'`
- `entry <label> has no positive integer rows/cols with a cells array — the grid cannot be reshaped`

Here `<label>` is `cat_a x cat_b` or `index N`.

**One cross-tab per unordered pair of two distinct columns.** Once an entry's `pair` is two declared column names, the entries must cover distinct unordered pairs, and no pair may name one column twice. This holds for every entry, whatever its `available` says, because the shipped profilers refuse both shapes before writing anything. Two cross-tabs of one pair (`[a, b]` and later `[b, a]`, or the same pair twice) can hide different cells, and the union of what they release recovers cells that neither hides alone. A pair such as `[a, a]` is no cross-tab at all. A self-pair is `entry index <i> names one column twice in its 'pair'`. A repeat is reported on the later entry and names the first entry on that pair: `entry index <i> repeats the pair of entry index <k>`, where `<k>` is the zero-based position of the first entry that covers the same two columns in either order. A self-pair entered twice gets both findings. Only entry indices print, never a column name. The rule compares names: two columns that hold one variable under different names (a code column and its label column) are different columns to it, so pairing each with one partner passes (see **Linked-release residuals** below).

Once an available entry's grid can be reshaped, six more rules apply, each a `[FAIL]` that names the entry and never a cell value (the sixth can also be `[NOT VERIFIED]`, below):
- **Released categories.** An available grid sits on the released categories of its two columns. Its rows are the released `levels` of the first pair column's categorical block, and its columns are those of the second, with `__OTHER__` as one level when the block releases it. So `rows` must equal the number of entries in the first column's `levels` array, and `cols` the number in the second's. The shipped profilers build every cross-tab this way (kept levels in code-point order, then `__OTHER__`), so a level the categorical block pools into `__OTHER__` never gets a row or column of its own. If it did, subtracting that fully visible row from the released `__OTHER__` count could isolate a rare level's count. Since a block releases at most `max_categorical_levels` levels, the rule also caps the grid's size. The forms are `entry <label> pair position <p> is not a categorical column with a released levels array`, `entry <label> has rows unequal to the released level count of pair position 0`, and `entry <label> has cols unequal to the released level count of pair position 1`. The first covers a pair column whose `role` is not `categorical`, that has no categorical block, or whose block has no `levels` array; `<p>` is `0` or `1`, and both positions are tested. The rule runs only when `pair` is two declared column names, reads the first column record carrying each name, and prints no count. It compares counts only: cells carry no labels, so it cannot see whether the rows follow the released order. An unavailable entry carries no grid and is not tested.
- **Grid size.** The `cells` array must hold exactly `rows × cols` entries; otherwise `entry <label> has <m> cells, not rows x cols = <p>`. `<p>` is the exact integer product in both languages: Python multiplies exact ints, and R builds the product from exact base-10⁷ limbs, so a product above 2^53 prints the same digits rather than a rounded double.
- **Structural zeros.** A visible `0` is a legitimate structural zero, and the profiler emits them. It is not a finding, and nothing tests it as a disguised hidden cell. A hidden cell must be `null`, and one mis-coded as `0` is still caught, because `cells_suppressed` then disagrees with the number of `null`s: `entry <label> reports a cells_suppressed that disagrees with the <k> nulls in the grid`.
- **Differencing residual.** The entry's `n` must reconcile with its visible cells, mirroring the profiler's own assertion (`profiling-script-spec.md` § Relationships). Visible cells never sum past `n`, and when no cell is hidden they sum to exactly `n`. Otherwise `n` minus the visible sum is a released count that anyone can recover by subtraction. The test runs only when every visible cell is a whole number ≥ 0, because a malformed or negative cell is already the threshold sweep's finding. The three forms are `entry <label> carries no whole-number 'n' to reconcile its cells against`, `entry <label> releases visible cells that sum past its n`, and `entry <label> hides no cell but its visible cells do not sum to its n`.
- **Complementary suppression.** Every row and column total of the entry is treated as released, because the categorical blocks release the margins. Read the entry's hidden (`null`) cells as the edges of a bipartite graph whose vertices are its rows and columns. A hidden cell is exactly recoverable from those totals when its edge is a **bridge**, meaning it lies on no cycle of hidden cells, so the row and column equations pin its value. Suppression is therefore safe only when no hidden cell is a bridge: each connected group of hidden cells must be 2-edge-connected. In particular every row and column holds zero or at least two hidden cells, and no single hidden cell is the only link between two groups. The simplest bridge is a lone hidden cell, the only one in its row or column. It keeps its own forms, reported once per entry for the first such row and the first such column: `entry <label> leaves a lone hidden cell in row index <i> — recoverable by differencing` and `entry <label> leaves a lone hidden cell in column index <j> — recoverable by differencing`. Any other bridge is one whose row and column both hold two or more hidden cells, for example a hidden cell joining two otherwise separate 2 × 2 blocks of hidden cells. Each such bridge is reported per cell, in row-major order after the lone-cell forms: `entry <label> leaves hidden cell at row index <i>, column index <j> recoverable from the released totals`. Indexes are zero-based positions, no cell value is printed, and further findings count into `(+N more)`. A fully collapsed entry is exempt, because it releases no visible cell. The scan is one iterative low-link walk per connected group of hidden cells that visits each hidden cell a bounded number of times, so its cost grows linearly with the size of the grid. The report-tree walk of `no_raw_value_shaped_fields` is linear as well, and both blocks hold that walk's stack in place rather than copying it on every step. The R block's low-link walks (this one and the missing-partner scan below) grow and shrink their stacks by copying short vectors; a stack never gets deeper than about twice the grid's smaller dimension, so the copying keeps the cost proportional to the grid size. A report with a 300 × 300 cross-tab of hidden cells runs through the R block in about a second and the Python block in a fraction of one. That timing is the bridge scan: with every cell hidden, the missing-partner scan skips the entry. The `[PASS]` line ends `… no hidden cell recoverable from the row and column totals`: no hidden cell is a bridge, lone or otherwise. Interval bounds that non-negativity puts on a hidden cell on a cycle are out of scope: the rule removes exact recovery only.
- **Missing-partner cells.** The categorical blocks count every non-missing record of a column, while the grid counts only records where both columns are present. So a fully visible row leaves "released level count minus row sum" on the wire: the number of records in that category whose partner column is missing. The scan reads the entry as an extended table. It adds a missing-partner column (row category `i`, second pair column missing) and a missing-partner row (first pair column missing, column category `j`). The both-missing corner is `(row_count − nonmissing_n₀) + (row_count − nonmissing_n₁) − (row_count − n)`, fixed by released facts, so it is known rather than hidden. Every total of the extended table is released: the level counts, and each missing line's residual `nonmissing_n − n` of its own column. The extended graph's edges are the hidden cells plus every cell of each missing-partner line whose residual is non-zero. A line whose residual is 0 is a line of known zeros and adds no edge, so a pair with no missing value in either column adds nothing to the scan. As with hidden cells, a missing-partner cell is pinned exactly when its edge is a bridge. Its value is the cut: take the side of the graph, without that edge, that holds the cell's row-side end. The value is the sum, over that side's row-side vertices, of each total minus the known cells on it, less the same sum over the side's column-side vertices. A pinned cell whose value is negative or in `(0, gate)` fails as `entry <label> leaves the missing-partner cell at row index <i> recoverable from the released totals` (the missing-partner column, row category `i`) or `entry <label> leaves the missing-partner cell at column index <j> recoverable from the released totals` (the missing-partner row, column category `j`). Findings follow the hidden-cell findings, row positions first and then column positions, and never carry a value. The gate is the sweep's effective threshold `max(declared, approved)`. Three cases are not findings:
  - **The baseline is exempt.** A cell that is a bridge even when *every* grid cell is hidden is pinned by the released `n` and missing counts alone, whatever the grid shows, and no cell suppression can protect it. That is exactly the missing-partner column cell of a one-row grid and the missing-partner row cell of a one-column grid. This is a documented residual of releasing `n` and the missing counts, not a profiler or intake failure.
  - **An all-null grid is skipped**, collapsed or not. With every grid cell hidden, the graph is the baseline itself.
  - **The corner is never printed.** When the derivable both-missing count lies in `(0, gate)`, it is a pre-existing consequence of releasing `n`, both `nonmissing_n` values and `row_count`. It is not suppressible within a cross-tab, and the outcome vocabulary has no informational token. The block reports nothing for it, and the reviewer weighs it (QAS-B).

  The scan first reconciles the entry's `n` with both pair columns: `entry <label> has an n above the nonmissing_n of pair position <p>`. A pair-complete count above either column's non-missing count cannot be true, and the scan does not run on that entry. The scan reads the first column record carrying each name, every level count, both `nonmissing_n` values, the entry's `n`, and every visible cell. Each must be a whole number ≥ 0, their sum must be below 2^53 (so both languages add exactly), and each block's labels must be distinct, so the levels map onto grid rows (kept labels in code-point order, then `__OTHER__`). That mapping is checked by count only, under **Released categories** above. When a needed input fails these tests, the entry is evidence the check could not use, and the outcome is `[NOT VERIFIED] crosstab_schema_and_suppression: entry <label> lacks the released totals the missing-partner scan needs`. The scan has a pinned cell to gate, but `expected_threshold` or `settings.suppression_threshold` is unusable → `[NOT VERIFIED] crosstab_schema_and_suppression: entry <label> cannot gate its missing-partner cells: expected_threshold or settings.suppression_threshold is unusable`. A `[FAIL]` on the same check outranks either, and `(+N more)` counts further entries. The scan is one more iterative low-link walk over a graph two vertices larger than the hidden-cell graph, and its cut values come from subtree sums, so its cost stays proportional to the grid. In R its stack is copied on every push and pop (see **Complementary suppression** above), and the missing-partner scan on a 300 × 300 grid with missing values takes about 1.7 seconds. The `[PASS]` line is unchanged. On a report with missing values, it now also means no non-baseline missing-partner count below the gate is pinned by that entry's own cells and the released totals.

**What the cross-tab guarantee covers, and the accepted residual risk.** `crosstab_schema_and_suppression` guarantees one thing about hidden cells and missing-partner counts, entry by entry: none is recoverable from one cross-tab together with the released row and column totals, apart from the baseline missing-partner cells and the both-missing corner described above, which the released `n` and missing counts fix on their own. The `[PASS]` line says exactly that and no more. It does not cover Cramér's V, and it does not cover several entries read together (see **Linked-release residuals** below). At tier 3 the report also releases a Cramér's V for every categorical pair with enough paired support, computed on the full table (before pooling into `__OTHER__` and before any cell suppression) and rounded to six decimals. V is a function of the table's cells, so a determined analyst who combines it with the released margins can sometimes reconstruct small cross-tab cells, including for a pair that has no released cross-tab. Because V is computed before pooling, it can also undo the `__OTHER__` pooling: the rare source levels' counts, and how they spread across the partner column, can sometimes be recovered, though their labels stay unknown. CPS-INTAKE does not detect this and cannot: the report holds no data to test such a reconstruction against, and V is a statistic the spec releases on purpose. This is an accepted, documented limitation of tier 3, not a defect (`synthetic-data-workflow` skill, `references/disclosure-tiers.md` § T3, *Residual risk (accepted)*). A researcher choosing tier 3 should weigh it. If small cells in a categorical pair are sensitive, stay at tier 2, which releases no Cramér's V, or leave one of the two columns out of the profiled data.

**Linked-release residuals (accepted).** Every relationship protection CPS-INTAKE checks is stated for one release: no hidden cell or missing-partner count is recoverable from one cross-tab together with the released totals (`crosstab_schema_and_suppression`), no available named regression has a complement group below the gate, judged for one regression together with the released marginal summaries (the support gate of `no_released_count_below_threshold`), and the one-entry-per-pair rule compares column names. No check compares one release with another, so three combinations pass every check and can still disclose:
- **Cross-tabs sharing a column.** Several cross-tabs that pair one column with partners missing on the same (or overlapping) records can jointly pin a small missing-partner count that each entry leaves unpinned on its own.
- **Named regressions sharing a column.** Several regressions on one column whose pair-complete record sets differ by a few records reveal that column's mean over those records (one record's value when the sets differ by one), although each passes the complement-group gate.
- **Two encodings of one variable.** A code column and its label column, each paired with the same partner, give two differently suppressed tables of what is one table. Their visible cells together can recover cells each hides, and the name-based pair rule cannot see it.

CPS-INTAKE does not detect these. They are an accepted, documented limitation of tier 3, not a defect (`synthetic-data-workflow` skill, `references/disclosure-tiers.md` § T3, *Linked-release residuals (accepted)*). The researcher controls them through `RELATIONSHIP_SPEC`: list each column in as few pairs as possible, never profile two encodings of the same variable, and prefer tier 2 when many overlapping relationships are needed.

**`[SKIPPED]` versus `[NOT VERIFIED]` on this path.** A report that declares **zero columns of a role** is a structural fact about the tier and the dataset — `[SKIPPED] percentiles_monotone: report declares 0 numeric columns at tier 2 (0 grids, 0 percentiles)`, counted as skipped, carrying its zeros as evidence. A column that **declares a role but carries no block** is missing evidence — `[NOT VERIFIED] category_counts_le_rowcount: column 'region' declares role categorical but has no categorical block` — which fails the checkpoint. The distinction is the whole point: the first is something the report told us, the second is something the report should have told us and did not.

**`expected_threshold`: the gate is never the report's word alone.** A report could declare `settings.suppression_threshold: 1` and then release a count of 2; a sweep that trusted the declared value would pass it. `expected_threshold` is the suppression threshold the researcher approved at the tier-selection checkpoint (PSU-DS1) and recorded in STATE.md § Synthetic Path Tracking (**Suppression Threshold**); the DS-3 config stanza copies it from there (`WORKFLOW_PHASE_DO_SYNTHETIC.md` § DS-3). It belongs to the non-declarable check `no_released_count_below_threshold`, so there is no way to opt out of it. The same check carries the other PSU-DS1 approval, the **tier**: the config `tier` is the tier the researcher approved (STATE.md § Synthetic Path Tracking, **Disclosure Tier**; at T4, the tier approved for the companion profiler run, and CPS-INTAKE still accepts only 1–3). A report could just as well be profiled at a higher tier than was approved, and a tier ceiling that trusted `settings.tier` alone would never notice. Once the report has loaded and carries a `columns` array, the check resolves in this order:
- `expected_threshold` unset, or not a whole number ≥ 1 → `[NOT VERIFIED] no_released_count_below_threshold: expected_threshold not configured`, which fails the checkpoint. This is a config defect: fill the stanza from STATE.md and re-run under a new revision.
- Config `tier` unset or not 1–3 → `[NOT VERIFIED] no_released_count_below_threshold: tier not configured — the approved release scope is unknown`. Also a config defect, fixed the same way.
- `settings.suppression_threshold` absent or not a positive whole number → `[NOT VERIFIED] no_released_count_below_threshold: settings.suppression_threshold is absent or not a positive integer — the sweep has no gate to test against`.
- The report declares less than the approved value → `[FAIL] no_released_count_below_threshold: report declares threshold d, below the approved threshold e`. The profiler ran with a weaker gate than the researcher approved, so cells between the two thresholds may already have crossed the boundary. Treat it as a disclosure event. The remedy is a corrected local re-run at the approved threshold. Never lower `expected_threshold` to match the report: that would turn the one external check on the report's threshold into an echo of it.
- `settings.tier` absent or not a whole number 1–3 → `[FAIL] no_released_count_below_threshold: settings.tier is absent or not a whole number 1-3 — the report's release scope is unstated`. This is a `[FAIL]`, not `[NOT VERIFIED]`: the tier is a field the check validates, and a report that does not state its scope cannot be held to one.
- The report declares a higher tier than was approved → `[FAIL] no_released_count_below_threshold: report declares tier R, above the approved tier T`. Blocks above the approved tier have already crossed the boundary without approval. Treat it as a disclosure event and request a corrected local re-run at the approved tier. Never raise the config `tier` to match the report.
- Either tier is below 3 and the report carries `relationships` content (anything other than an absent key, `null`, or an empty object or array) → `[FAIL] no_released_count_below_threshold: the report releases a relationships block below tier 3 (approved tier T, declared tier R)`. Relationships are a tier-3 release, so this is the same disclosure event and the same remedy. In the same report, `correlation_matrix_wellformed` prints `[SKIPPED] correlation_matrix_wellformed: tier T releases no correlation matrices (N matrices declared)`. `N` counts the `available: true` pearson and spearman blocks the report actually carries, so a matrix released below tier 3 shows as a non-zero `N` on the skip line rather than being waved through as a structural fact.
- Otherwise the sweep runs against the **effective threshold** `max(declared, approved)`. A report that declares more than was approved is honoured at its stricter value. A released categorical level is a whole-number count at or above the gate, so any visible level count below it breaches, **including 0 and negatives**: a level listed at 0 still names a category, and a negative count is a sub-threshold count wearing a sign. The form is `categorical block '<c>' level index <j> carries a visible count below the gate`. A cross-tab cell breaches when it is negative or in `(0, gate)`: `cross-tab block <a x b> cell index <i> carries a visible count below the gate`. A visible cross-tab `0` is a legitimate structural zero and does not breach.
- In the same pass, each categorical block's **differencing residual** must reconcile, mirroring the profiler's own assertions (`profiling-script-spec.md` § Categorical and string structure). Otherwise `n` minus the visible sum, or `nonmissing_n` minus `n`, is a hidden count that anyone can recover by subtraction. In order: the block's `n` and its column's `nonmissing_n` must both be whole numbers (`categorical block '<c>' carries no whole-number n and nonmissing_n to reconcile its levels against`); they must be equal (`categorical block '<c>' n does not equal its column's nonmissing_n`); when `n` is below the gate, no level may be released (`categorical block '<c>' releases levels although its n is below the gate`); and when `n` is at or above the gate, the level counts, `__OTHER__` included, must sum to exactly `n` (`categorical block '<c>' level counts do not sum to its n`). The sum is tested only when every level count in the block has already passed the gate. All of these forms are `[FAIL]` breaches of the sweep. They name the block and an index, never a count.

Both thresholds and both tiers are allowed facts on an outcome line — they are settings, not data.

**Aggregate-only disclosure evidence.** The `[PASS]` line for `no_released_count_below_threshold` reports blocks scanned against blocks declared (split into categorical and cross-tab), visible cells examined, and the effective threshold together with the declared and approved values it came from — `[PASS] no_released_count_below_threshold: N of M declared blocks scanned (a categorical + b cross-tab), C visible cells examined, all >= effective threshold G (declared d, approved e)`. It never carries a count value, a minimum, or a level label with its count. A `[FAIL]` names the block and, for a cell finding, the cell position, and stops there (`categorical block 'cat_b' level index 2 carries a visible count below the gate`, or `categorical block 'cat_b' level counts do not sum to its n` for a residual). Further breaches are counted as `(+N more)`, never listed. Anyone reading the log learns that the sweep ran, what it covered, and which bar it applied, and learns nothing about the underlying data that the report did not already release in aggregate.

**Scan completeness is part of the sweep.** The block counts the categorical and cross-tab blocks it actually enumerated and compares that to the number the report declares (categorical columns plus `available: true` cross-tab entries). A shortfall is `[FAIL] …: scanned N of M declared blocks — the sweep is incomplete`, because a block that was never visited cannot have been cleared. A report with zero categorical columns and zero cross-tabs yields `[PASS] no_released_count_below_threshold: 0 of 0 declared blocks scanned (0 categorical + 0 cross-tab), 0 visible cells examined, all >= effective threshold G (declared d, approved e)` — evidence-bearing, not N/A.

**Support gate (CPS-INTAKE).** In the same pass, `no_released_count_below_threshold` holds every value summary to the shape its support admits, exactly as `profiling-script-spec.md` (§ Numeric shapes, § Categorical and string structure, § Relationships) and both profilers branch. Let `k` be the effective threshold and `f = max(k, 10)` the full-summary cutoff. The spec records `f` as `settings.full_summary_cutoff`; the block recomputes it from `k`, so a report cannot lower it.

| Block | Shape (marker) | Support band |
|-------|----------------|--------------|
| `numeric` | `all_missing` | `n = 0` and the column's `nonmissing_n = 0` |
| `numeric` | `withheld` | `n < k` |
| `numeric` | `constant` | `n >= k` |
| `numeric` | `small_n` | `k <= n < f` |
| `numeric` | full summary (no marker; carries `mean`, `sd`, `percentiles` or `value`) | `n >= f` |
| `string_structure` (identifier or string column) | `withheld` | `n < k` |
| `string_structure` | full (`n, length_*, pattern_flags`) | `n >= k` |
| `relationships.named[]`, `available: true` | — | `n >= f` |
| `relationships.named[]`, `available: true`, each end | complement group `g = n_end - n` | `g = 0` or `g >= k` |
| `relationships.cramers_v[]`, `available: true` | — | `n >= k` |

A numeric block's shape is its first marker that is literally `true`, in the spec's branch order. A block with no true marker and none of the value keys releases no value; `percentiles_monotone` owns that finding. A numeric `n` may not exceed its column's `nonmissing_n`, and a `string_structure` `n` must equal it. Every finding is a `[FAIL]` breach of the sweep. Each names the column or entry and the shape, never `n`:
- `numeric block '<c>' carries no non-negative whole-number n and nonmissing_n to gate its shape on`
- `numeric block '<c>' n exceeds its column's nonmissing_n`
- `numeric block '<c>' shape '<shape>' does not match the support band of its n` (`<shape>`: `all_missing`, `withheld`, `constant`, `small_n`, `full`)
- `string_structure block '<c>' carries no non-negative whole-number n and nonmissing_n to gate its shape on`
- `string_structure block '<c>' n does not equal its column's nonmissing_n`
- `string_structure block '<c>' shape '<shape>' does not match the support band of its n` (`<shape>`: `withheld`, `full`)
- `named entry <outcome> ~ <predictor> is available although its n is below the full-summary cutoff`
- `cramers_v entry <a> x <b> is available although its n is below the gate`
- `<kind> entry <label> carries no non-negative whole-number n to gate its availability on`
- `named entry <outcome> ~ <predictor> is available although the complement group of its <outcome|predictor> is below the gate`
- `named entry <label> has no whole-number numeric n for its <outcome|predictor> to gate the complement group on`

**Complement groups of a named regression.** For an available `named` entry, each end's complement group is `g = n_end - n`: the end column's numeric-block `n` (the records its released mean describes) minus the entry's pair-complete `n`, so it counts the records that have that column but lack the other. It must be `0` or at least `k`, the same effective threshold the rest of the support gate uses (`max(declared, approved)`). The released mean covers `n_end` records and the fitted line pins the mean over the `n` pair-complete ones (through the other column's released mean, or through the reversed regression), so `n_end × mean − n × (that mean)` is the summed value of the `g` records lacking the partner, which is one record's value when `g = 1`. The shipped profilers then mark the entry `available: false` with reason `small_complement_group`. The outcome is tested first, then the predictor, with at most one finding per entry. A negative `g` (more pair-complete records than the column holds) breaches too, as a sub-threshold count wearing a sign. An end whose first column record carries no numeric block, or a numeric `n` that is not a whole number, is the second form. Pearson and Spearman matrices are not gated this way, because a correlation carries no mean. The gate judges each regression on its own; several regressions that share a column are not compared (see **Linked-release residuals** above).

An entry is labelled by its column names only when both name declared columns; otherwise it is `index N`, as for cross-tabs. The band edges are exact both ways: a full summary at `n = f - 1` fails and at `n = f` passes, and a withheld block at `n = k` fails as over-suppressed, because no profiler writes it. The `[PASS]` line's counts are unchanged; a `[PASS]` now also means every value summary sat in its band.

**The `no_raw_value_shaped_fields` heuristic, stated plainly.** Six rules, all intentionally conservative:
1. **Value-shaped key names.** A key named `values`, `sample`, `rows`, `head`, or `examples` (case-insensitive, so `Sample` and `ROWS` count) whose value is a **list** is flagged as `<path>.<k> is a list under a value-shaped key name`, where `<path>` starts at `report` (for example `report.columns[0].values`). The type test matters: a cross-tab entry's `rows` is an integer dimension and is legitimate, while a `rows` array is a row dump.
2. **Over-long scalar lists.** A list whose elements are all scalars (JSON `null` counts as a scalar) and whose length exceeds the report's own declared cap is flagged. The cap is the largest structure the report legitimately declares: `max(9 percentile grid points, number of columns, largest released level count, largest cross-tab cell grid)`.
3. **String-valued value-shaped key names.** A key named `example`, `examples`, `sample`, `first_value`, `last_value`, `mode_value`, `min_value`, `max_value`, `values`, `head`, or `tail` (case-insensitive) whose value is a **string** is flagged wherever it appears. Rules 1 and 2 inspect lists only, so a single memorised value parked under such a name would otherwise pass.
4. **Per-role key allow-list for column records.** Every column record that is not an identifier (identifier records belong to `identifier_columns_value_free`) may carry only the keys `profiling-script-spec.md` § Column metadata sanctions for its role. Rules 1-3 are deny-lists, and a deny-list only catches the names someone thought of: `top_values`, or a `Sample` key before rule 1 went case-insensitive, walked past them. The schema already says which keys are legitimate:
   - **Tier 1:** the record is exactly `{name, dtype}`, with no role block.
   - **Tier 2+:** the eight base keys (`name`, `dtype`, `role`, `missing_rate`, `nonmissing_n`, `n_distinct`, `uniqueness_ratio`, `is_identifier`) plus the one block for the record's role. `numeric` takes `numeric`, `categorical` takes `categorical`, and `string` takes `string_structure`.
   - **`numeric` block:** the first shape marker present, in the spec's branch order, names the shape. `all_missing` allows `{n, all_missing}`. `withheld` allows `{n, withheld, reason}`. `constant` allows `{n, constant, value, mean, sd}`. `small_n` allows `{n, small_n, percentiles}`. A block with no marker is the full shape, `{n, mean, sd, percentiles}`. A marker whose value is not literally `true` is itself a non-structural key. The nested `percentiles` object is held to `p25`/`p50`/`p75` for `small_n` and to the nine grid keys `p1`…`p99` otherwise.
   - **`categorical` block:** exactly `{n, n_levels_binned, levels}`, and each `levels[]` entry exactly `{value, count}`.
   - **`string_structure`:** `{n, length_min, length_mean, length_max, pattern_flags}`, or the withheld shape `{n, withheld, reason}`. `pattern_flags` is held to its five flags (`email`, `phone`, `date`, `id`, `free_text`).
   - **Typed values.** An allowed key name is not enough: the key must also hold the type the schema gives it. The numeric keys `missing_rate`, `nonmissing_n`, `n_distinct`, `uniqueness_ratio`, `is_identifier`, `n`, `mean`, `sd`, `value`, `n_levels_binned`, `length_min`, `length_mean`, and `length_max` must hold a number, a boolean, or `null`, and so must every percentile entry and every `pattern_flags` entry. The spec emits `sd: null` at n = 1, which is why `null` is accepted. A string, array, or object under one of these keys is a released value wearing a structural key's name. Shape markers (`all_missing`, `withheld`, `constant`, `small_n`) keep their literal-`true` test instead. A level's `value` label is the one string in the record: it must be a JSON string, because an array or object there is a value dump wearing the label's name, and it is not held to a vocabulary. A non-string label is `column '<c>' level index <j> carries a non-string 'value'`. The level's `count` is gated by the threshold sweep.
   - **Distinct labels.** No profiler writes a label twice in one block, because each released level is one category. A string label repeated within a categorical block (`__OTHER__` and the empty string included) is `column '<c>' level index <j> repeats the 'value' of level index <i>`, naming the later level and the first one with that label, never the label. Two entries under one label would split a category's count in a way no other check reconciles, would make the cross-tab's category order ambiguous, and would hand generation two counts for one level. Non-string labels are the previous finding only, and are not compared.
   - **Vocabularies.** Three column-record strings are held to the spec's closed sets. `dtype` must be one of `integer`, `double`, `string`, and `role` one of `numeric`, `categorical`, `identifier`, `string`. A withheld block's `reason` must be `no_finite_values` or `insufficient_support` in a `numeric` block, and `all_missing` or `insufficient_support` in a `string_structure`. A free string in any of these places is a released value, just as a string under `n` would be.
   - **Categorical columns are string columns.** Both profilers give the `categorical` role only to dtype `string` (a numeric dtype is profiled as `numeric`), so a categorical record whose `dtype` is `integer` or `double` is `[FAIL] no_raw_value_shaped_fields: column '<c>' declares role 'categorical' with a dtype other than 'string'`. The dtype is not echoed. A `dtype` outside the vocabulary stays the Vocabularies finding above, with no second line.

   Every rule-4 `[FAIL]` names a key, column, or index and never a value. The forms are: `column '<c>' carries non-structural key '<key>'`; `column '<c>' carries a non-numeric '<key>'`; `column '<c>' carries a '<key>' outside the spec vocabulary` (for `dtype` or `role`); `column '<c>' carries a 'reason' outside the spec vocabulary`; `column '<c>' carries a non-object '<block>'` (for a role block, `percentiles`, or `pattern_flags`); `column '<c>' carries a non-array 'levels'`; `column '<c>' level index <j> is not a JSON object`; `column '<c>' level index <j> carries a non-string 'value'`; `column '<c>' level index <j> repeats the 'value' of level index <i>`; `column index <i> is not a JSON object`; and `column index <i> has a name that is not a string`.
5. **Spec key allow-lists and vocabularies outside `columns`.** Column records are not the only place a free string can sit. Rule 5 walks the `dataset`, `settings`, `generator`, `relationships`, and `validation` subtrees breadth-first, in that fixed order and in the same order in both languages. It holds every record to the spec's key allow-list and every field to the type or closed vocabulary the spec fixes for it (`profiling-script-spec.md` § Canonical JSON report schema, § Relationships, § Embedded validation checks). A subtree that is not a JSON object is skipped here, because rule 6 (below) and `required_top_level_keys` both report it. Cross-tab entries are skipped too: `crosstab_schema_and_suppression` owns them (see **Each cross-tab entry is held to the spec's key allow-list** above). The rule permits keys; it does not require them, so an absent key is never a rule-5 finding. "Number" below means a number, boolean, or `null`, the same rule as rule 4's numeric keys. "Boolean" means a JSON boolean only, and `null` does not qualify.

   | Record | Allowed keys and what each must hold |
   |---|---|
   | `dataset` | `row_count`, `column_count`: number |
   | `settings` | `tier`, `suppression_threshold`, `max_categorical_levels`, `full_summary_cutoff`: number. `support_unit`: `"record"`. `relationship_spec`: `null` or a list of pairs, each pair two declared column names |
   | `generator` | `language`: `Python` or `R`. `template`: `profile_data_template.py` or `profile_data_template.R`, the two shipped profilers' constants. `template_version`: `"2.0"` |
   | `relationships` | `pearson`, `spearman`: a correlation record. `cramers_v`, `named`: arrays of entry records. `crosstabs`: owned by `crosstab_schema_and_suppression` and not walked here |
   | `relationships.pearson`, `relationships.spearman` | `available`: boolean. `columns`: an array of declared column names. `pair_n`, `matrix`: arrays of rows whose entries are numbers or `null`. `reason`: `fewer_than_two_eligible_columns`, `insufficient_pair_support`, `zero_pair_variance`, or `nonfinite_correlation` |
   | `relationships.cramers_v[i]` | `pair`: two declared column names. `n`, `v`: number. `available`: boolean. `reason`: `insufficient_support` or `degenerate_table` |
   | `relationships.named[i]` | `outcome`, `predictor`: a declared column name. `n`, `pearson`, `spearman`: number. `available`: boolean. `ols`: a record of `intercept`, `slope`, and `r_squared`, each a number. `reason`: `insufficient_support`, `ineligible_marginal`, `small_complement_group`, or `zero_pair_variance` |
   | `validation` | `checks`: an array of check records. `all_passed`: boolean |
   | `validation.checks[i]` | `name`: one of the seven required embedded check names. `status`: `PASS`, `FAIL`, `NOT_APPLICABLE`, or `NOT_VERIFIED`. `applicable`: boolean. `reason`: see below |

   A check record's `reason` is judged by its `status`. A `PASS` record's reason must be exactly `candidate_fields_checked`. A `NOT_APPLICABLE` record's reason must fully match one of the forms the shipped profilers generate for that check name. `T` is a tier and `N` a count of one or more:

   | Embedded check | Accepted `NOT_APPLICABLE` reasons |
   |---|---|
   | `percentiles_monotone` | `report declares 0 numeric columns at tier T` (T = 1–3); `0 of N numeric columns release a percentile grid` |
   | `category_counts_le_rowcount` | `report declares 0 categorical columns at tier T` (T = 1–3) |
   | `missing_rate_in_unit_interval` | `tier 1 releases name and dtype only` |
   | `correlation_matrix_symmetric` | `tier T releases no correlations` (T = 1–2); `0 of 2 correlation blocks released (<r>)`, where `<r>` is one of the four correlation reasons above or `no reason stated` |
   | `relationship_support_and_shape` | `tier T releases no relationships` (T = 1–2) |

   The remaining two embedded checks, `column_shapes_and_support` and `no_subthreshold_cells_emitted`, have no accepted `NOT_APPLICABLE` reason. A `FAIL` or `NOT_VERIFIED` record has no shareable reason at all, so any reason it carries is outside the vocabulary. A record whose `status` is outside the wire enum is reported through that `status`, and its reason is not judged separately.

   **A reason outside these forms.** The profilers take no researcher declarations: `profile_data_template.py` / `.R` have no `not_applicable` setting, and they mark every structural no-target case `NOT_APPLICABLE` themselves, using the forms above, so a genuine report always passes this rule. Any other reason therefore means a modified template or a hand-edited report. It fails this rule with `[FAIL] no_raw_value_shaped_fields: validation.checks[<i>].reason is outside the spec vocabulary`, and CPS-INTAKE returns `FAILED`. The rule does not judge how the reason got there.

   Every rule-5 `[FAIL]` names a JSON path and a key, and never a value. A rule-5 path starts at the subtree name, for example `settings`, `relationships.cramers_v[0]`, or `validation.checks[2]`, with no `report.` prefix. The forms are:
   - `<path> carries non-structural key '<k>'`
   - `<path> carries a non-numeric '<k>'`
   - `<path> carries a non-boolean '<k>'`
   - `<path>.<k> is outside the spec vocabulary`
   - `<path>.<k> is not built from declared column names`
   - `<path>.<k> is not an array of numeric rows`
   - `<path>.<k> is not a JSON object`
   - `<path>.<k> is not a JSON array`
   - `<path>.<k>[<e>] is not a JSON object`, for an array element that should be a record

6. **Top-level key set, types, and formats.** The top level of the report is held to the spec's nine keys and the type of each. `generator`, `settings`, `dataset`, `validation`, and `relationships` must be JSON objects, and `columns` must be a JSON array. A present key holding `null` fails too, which matches the shipped profilers: they omit `relationships` below tier 3 rather than writing `null`. The three scalar keys must fully match the format both shipped profilers write: `report_version` matches `[0-9.]{1,16}` (a dotted version), `dataset_name` matches `[A-Za-z0-9_-]+` (the Config slug), and `generated_utc` matches `YYYY-MM-DDTHH:MM:SSZ`. The patterns use ASCII classes only in both languages, so a non-ASCII digit or letter fails them. `required_top_level_keys` checks the same key set, but it is declarable. Rule 6 repeats the check inside a non-declarable one, so declaring `required_top_level_keys` away cannot open a free-text channel at the top of the report. A missing key is not a channel, so it stays `required_top_level_keys`' finding: rule 6 judges only the keys that are present, in C-locale sorted order in both languages. No form echoes a value:
   - `report carries non-structural key '<k>'`
   - `report.<k> is not a JSON object`
   - `report.<k> is not a JSON array`
   - `report.<k> is outside the spec format`

The `[PASS]` line carries the evidence for rules 1–5, and rule 6 adds no counter of its own: `[PASS] no_raw_value_shaped_fields: N JSON nodes walked, 0 value-shaped keys, longest scalar list L <= declared cap C, K column records within the per-role key allow-list, S subtree records within the spec key allow-lists and vocabularies`. `K` counts the non-identifier records rule 4 examined, and `S` counts the records rule 5 visited, nested entries included. No rule can prove the absence of a leak — they catch the shapes a value dump takes. They are a floor under the reviewer's QAS-B judgment, not a replacement for it. `no_raw_value_shaped_fields`, `identifier_columns_value_free`, and `crosstab_schema_and_suppression` are all non-declarable, so none of these rules can be switched off by a `not_applicable` entry.

**Malformed types never stop the block.** Every check reaches its own outcome line on any input, and the block always reaches its count line and verdict line. A field of the wrong JSON type follows one rule. If it is the field a check *validates*, the outcome is `[FAIL]`. Examples: a top-level key of the wrong type (`required_top_level_keys … wrong JSON type [...]`), a non-whole `dataset.row_count`, a non-integer level count, a non-object `string_structure`, and an available cross-tab entry whose `rows` or `cols` is not a positive whole number or whose `cells` is not an array (`crosstab_schema_and_suppression … the grid cannot be reshaped`). If it is *evidence* a check needs in order to run, the outcome is `[NOT VERIFIED]`. Examples: a non-whole `nonmissing_n` behind a `missing_rate`, a non-numeric percentile value, a mistyped `settings.suppression_threshold`. Both languages use one numeric model. A JSON number counts only if it is finite and `|v| < 2^53`: the profiler refuses larger magnitudes, every whole number below the bound is exact in a double, and jsonlite would turn a 401-digit integer into `Inf` where Python keeps an exact int. Whole numbers are compared by value, so `40` and `40.0` agree, because JSON does not type them apart. A report that fails to parse is `[NOT VERIFIED]` on every check not declared `not_applicable`, with `report did not parse as JSON (parser message withheld: it can quote report content)`. The parser's own message is withheld because it can quote report text, and the two parsers word it differently anyway.

**Strict report parsing (CPS-INTAKE).** Parsing is strict, and both languages reach the same outcome on every file — the same rules CPS-GEN applies. Things a lenient parser would accept, or that the two parsers read differently, are parse errors here:
- a leading UTF-8 byte-order mark (jsonlite accepts it with a warning; `json.loads` refuses it);
- a raw NUL byte, or bytes that are not valid UTF-8 (including a surrogate code point encoded directly as UTF-8 bytes);
- an escaped NUL (`\u0000`), which jsonlite silently cuts the string at while Python keeps it;
- an unpaired surrogate escape — a `\ud800`–`\udbff` not immediately followed by a `\udc00`–`\udfff`, or a low surrogate with no high one before it — which jsonlite replaces while Python keeps it. A correctly paired escape (an emoji written as `\ud83d\ude00`) is valid, and an escaped backslash followed by the text `u0000` is not an escape at all;
- a `NaN`, `Infinity`, or `-Infinity` literal, which is not JSON;
- a JSON number token longer than 64 characters, outside strings — sign, digits, fraction and exponent counted together. Python refuses an integer of more than 4300 digits while jsonlite reads any huge literal as `Inf`, so the two blocks used to reach different verdicts on the same file. No number a profiler writes comes near 64 characters, and a 64-character number parses as before;
- a duplicate object key at any depth;
- nesting deeper than 64 levels, counting the top-level object as level 1. A well-formed report reaches depth 6 (report > columns > column > categorical > levels > level).

Both blocks read the file as bytes and refuse the first four before any parser runs: the BOM and NUL tests are byte tests, the UTF-8 test is a strict decode (Python) or `validUTF8()` (R), and the escape test walks the `\` sequences left to right so that an escaped backslash is one token. The number test runs on the same text, also before any parser: it blanks every string literal (an escaped quote stays inside its string, so digits in a label or key never count) and refuses any remaining run of 65 or more of the characters `-`, `+`, `0`–`9`, `.`, `e`, `E` — the same two patterns in both languages. Python then parses twice — once with `object_pairs_hook=list`, so a repeated key stays visible, and once into the dicts the checks read — passing `parse_constant` so the three literals raise and catching `RecursionError`. R parses the text with `jsonlite::parse_json()`, which already refuses the literals. One iterative sweep in each language then refuses a repeated name and a depth above 64. Each rule closes a cross-language gap: Python's default parser admits `NaN` while jsonlite refuses it; on a duplicate key Python's dict keeps the last value while jsonlite keeps both and `[[` reads the first, so one file would be judged on two different values; and the two parsers give up at different depths. A file that breaks any rule makes every check not declared `not_applicable` print `[NOT VERIFIED] <check>: report did not parse as JSON (parser message withheld: it can quote report content)`. That always includes the four non-declarable checks, so the verdict is `FAILED`. A file that parses but whose top level is not a JSON object prints `report parsed, but its top level is not a JSON object` on those same lines instead.

The same sweep collects every key and string value of the report into one escape table per run. Any report-derived text an outcome line prints — a column name, a key, a cross-tab pair label — prints through that table: every character outside printable ASCII (0x20–0x7E) becomes `\uXXXX` in lowercase hex, and a character above U+FFFF becomes its UTF-16 surrogate pair (`\ud83d\ude00`). A newline, carriage return or other control character in a column name therefore cannot start a new line, so no report can forge a `Checks:` line or a verdict, and no non-ASCII name can fail the write on a console that cannot encode it. Config strings (`report_path`, `not_applicable` reasons) are the researcher's own text and print as written. Two further text rules keep the languages in step: value-shaped key names are matched case-insensitively over the 26 ASCII letters only (`str.translate` in Python, `chartr()` in R — the locale-aware `lower()`/`tolower()` fold different non-ASCII letters), and "blank" (an empty `not_applicable` or record reason) means only Unicode whitespace, the 29 code points Python's `str.strip()` removes, spelled out explicitly in R because PCRE's `[\h\v]` is a different set.

**Pair labels and cross-language parity.** The Python and R blocks print identical outcome lines for the same report, and the R block is written to keep it that way: printed lists are sorted in C-locale byte order (`method = "radix"`, matching Python's `sorted()`), whole-number thresholds and counts print without scientific notation, and every index is zero-based. A cross-tab entry is labelled `cat_a x cat_b` only when every element of its `pair` is a string naming a declared column. Otherwise it is labelled `index N`, its zero-based position in `relationships.crosstabs`. A `pair` is report content, and only declared column names are schema facts, so arbitrary text in a `pair` never reaches the log. The rule applies to both `no_released_count_below_threshold` and `crosstab_schema_and_suppression`.

**Verdict mapping.** As with CP1-CP4 and CPP1-CPP4, the log line `PASSED WITH WARNINGS` maps to the reported status **`WARNING`**; `PASSED` maps to `PASSED`, `FAILED` to `FAILED`. Report the mapped value in STATE.md and in the agent's return, never the raw log string.

**STATE.md rows these blocks feed** (`agent_reference/STATE_TEMPLATE_ONBOARDING.md` § Synthetic QA Status):

| Row | Enum | Count columns |
|-----|------|---------------|
| CPS-INTAKE (DS-3 script) | `[PENDING/PASSED/PASSED WITH WARNINGS/FAILED]` | passed / warnings / failed / not verified / skipped |
| CPS-GEN (DS-5 script) | `[PENDING/PASSED/PASSED WITH WARNINGS/FAILED/EXEMPT (T4, no profile report)]` | passed / warnings / failed / not verified / skipped — or, when EXEMPT, the reason |

`PENDING` is the pre-run value; the five counts come straight from the block's count line. `EXEMPT (T4, no profile report)` is legal only on the CPS-GEN row, only at tier 4 when no profile report crossed: the block is not run, and the Counts cell records the reason in place of counts (see **Tier 4 and `seed_exception`** above).

**Execution.** Both blocks run inside a script under the file-first protocol, never interactively:

```
bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.py
bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.py
```

(`.R` in place of `.py` for R projects. T4: the second command runs `scripts/synth_generate/01_import-synthetic.{py,R}` instead, with CPS-GEN at the end of the import.) A `FAILED` verdict raises/stops, so the wrapper records a non-zero exit alongside the complete check log — which is the intended outcome, not an error to retry around.

**Comparator note.** `scripts/compare_execution_logs.py` matches `CP\d` verdict lines. `CPS-INTAKE` and `CPS-GEN` contain no `CP\d` substring and are therefore not machine-compared across runs; the count line is the primary machine-readable evidence, and QAS-B / QAS-C are the consumers that matter.
