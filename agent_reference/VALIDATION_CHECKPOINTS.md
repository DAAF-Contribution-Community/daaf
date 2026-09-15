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
