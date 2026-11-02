# Workflow Reference: Phase 4 — Analysis & Notebook Development

Stages 7, 8, 9, 10. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md`.

**Execution Model:** All scripts follow the file-first execution pattern. See `SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

> **Dispatch order and returns.** Same-wave tasks run in parallel, at most 5 in flight: executors first, then one code-reviewer per script once all have returned. Each script is reviewed before any dependent script or the next wave starts. Each invocation still runs exactly one transformation, analysis or visualization script, and each review covers exactly one script (the "NEVER batch" rule below is load-bearing). See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive, and § Parallel Dispatch Guideline for the limit of 5. Treat every mid-wave return as status-only: do not start the next wave, approve a dependent transformation, or evaluate a stage gate until every dispatch in flight has returned and been processed.

---

## Stage 7: EDA & Transformation

**Agent:** research-executor — ITERATIVE INVOCATION REQUIRED
**Skills:** `data-scientist`, `polars` (Python) or `tidyverse` (R), `geopandas` (Python) or `sf-terra` (R) (if spatial data)
**Purpose:** Explore data and create analysis dataset through step-by-step validated transformations

**CRITICAL:** This stage is executed in MULTIPLE subagent calls, NOT a single invocation. Follow the Iteration Protocol.

### Execution Pattern

**Stage 7 is split into 3 sub-stages:**

#### Stage 7.1: Initial EDA (No Transformations)

**Executor:** Subagent invocation 1
**Purpose:** Profile data WITHOUT transforming it

**Actions:**
1. **Load Data**
   - Read from `data/processed/`
   - Verify schema matches expectation
   - DO NOT transform yet

2. **Profile Data**
   - Shape, types, memory
   - Distributions (head, describe, value_counts)
   - Identify missing values, outliers
   - Check for unexpected values

3. **Report Findings**
   - Return EDA summary to orchestrator
   - Flag any data quality issues
   - Confirm ready for transformations

**Gate:** Orchestrator reviews EDA before proceeding to transformations

#### Stage 7.2: Execute Transformations (Iteratively)

**Executor:** Multiple subagent invocations (one per transformation)
**Purpose:** Execute one transformation per invocation, with validation (same-wave transformations may run in parallel; a transformation waits for the review of every transformation it builds on)

**For EACH transformation in Plan_Tasks.md's task sequence:**

1. **Orchestrator provides:**
   - Transformation #{n} description
   - Expected outcome
   - Validation criteria
   - Current data location

2. **Subagent executes Iteration Protocol:**
   - **DESCRIBE:** Confirm what will be done
   - **CODE:** Write transformation with pre-state capture
   - **EXECUTE:** Run the code
   - **VALIDATE:** Compare pre/post state, check invariants
   - **DECIDE:** Report PASS/FAIL status

3. **Subagent returns to orchestrator:**
   - Validation report (pre/post metrics, invariants, status)
   - If PASS: Location of transformed data
   - If FAIL: Issue description, proposed fix

4. **Orchestrator reviews:**
   - If PASS: Proceed to QA (step 5)
   - If FAIL: Request fix (max 2 attempts) or STOP

5. **>>> INVOKE code-reviewer (MANDATORY, after EACH script) <<<**
   - Orchestrator MUST invoke code-reviewer after EACH transformation script
   - Do NOT batch multiple transformations before QA
   - Pass: script path, output files, Plan.md + Plan_Tasks.md locations
   - If BLOCKER: A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). Any other BLOCKER (a bug, a stub, a validation gap) corrects a defect without changing the method and also goes through revision; a code-reviewer STOP of another Issue Category routes as `full-pipeline-mode.md` § Gate Status Translation says. A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.
   - If WARNING: log to STATE.md, proceed (a dependent transformation or the next wave may start)
   - If PASSED: proceed (a dependent transformation or the next wave may start)

6. **Repeat** for transformation #{n+1} (same-wave transformations in parallel, per the dispatch rule at the top of this file)

**Special Case: Join Transformations**

For join operations, use enhanced validation from `VALIDATION_CHECKPOINTS.md`:

1. **Orchestrator provides additional context:**
   - **Expected cardinality** from Plan_Tasks.md's task specification (REQUIRED: must be specified as "1:1", "1:many", "many:1", or "many:many")
   - Join keys (column names)
   - Join type (inner, left, right, outer)
   - Expected relationship between datasets

2. **Subagent uses join-specific validation:**
   - Use the **Join-Specific Validation** inline code template from `VALIDATION_CHECKPOINTS.md` > "Join-Specific Validation" section
   - Pass cardinality value to the validation code block
   - Check for fan-out (unexpected row multiplication)
   - Check for data loss (unexpected row reduction)
   - Verify join keys matched as expected
   - Check for null keys in result (shouldn't happen for inner joins)
   - Report cardinality violations with metrics

3. **Join validation STOP conditions:**
   - >90% row loss from left side (for inner/left joins)
   - Cardinality violation (e.g., 1:1 specified but fan-out occurred)
   - Missing join keys in result

**Linking Cardinality to Validation:**
The cardinality in Plan_Tasks.md's task specification is the contract. The Join-Specific Validation code template enforces it:
- If Plan says "1:1", validation checks result rows ≈ left rows
- If Plan says "1:many", validation allows result rows > left rows
- Violations trigger warnings or STOP conditions based on severity

**Validation Pattern (Script-Based):**

All transformations are executed through script files, NOT interactive notebooks. See `SCRIPT_EXECUTION_REFERENCE.md` for the script format and the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

**Python example:**
```python
# scripts/stage7_transform/01_join-data.py
# Each transformation is a SEPARATE SCRIPT with embedded validation
# NOTE: Scripts use sequential top-level code (not wrapped in def main()).

import polars as pl
from pathlib import Path

# ASSUMES: run_with_capture.sh does not change directory, so every path is built from the absolute project path.
PROJECT_DIR = Path("{PROJECT_DIR}")

# PRE-STATE CAPTURE
df = pl.read_parquet(PROJECT_DIR / "data" / "processed" / "2026-01-31_clean.parquet")
pre_shape = df.shape
pre_sample_ids = df.select("id_col").sample(5, seed=42).to_series().to_list()

print(f"PRE-STATE: {pre_shape[0]:,} rows × {pre_shape[1]} cols")

# EXECUTE TRANSFORMATION
df_transformed = df.join(
    other_df,
    on="join_key",
    how="left"
)

# POST-STATE CAPTURE
post_shape = df_transformed.shape
print(f"POST-STATE: {post_shape[0]:,} rows × {post_shape[1]} cols")
print(f"ROW CHANGE: {(post_shape[0]/pre_shape[0]*100):.1f}%")

# VALIDATION (CP3)
# INTENT: count outcomes so the verdict line is derived, not asserted.
cp3 = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}

# ASSUMES: an empty input frame makes row loss untestable — 0 rows in is not 0% loss.
if pre_shape[0] == 0:
    print("[FAIL] Row loss: input frame is empty — loss untestable")
    cp3["failed"] += 1
else:
    row_loss_pct = 1 - (post_shape[0] / pre_shape[0])
    if row_loss_pct < 0.9:
        print(f"[PASS] Row loss: {row_loss_pct:.1%} ({pre_shape[0]:,} -> {post_shape[0]:,} rows, threshold 90%)")
        cp3["passed"] += 1
    else:
        print(f"[FAIL] Row loss: {row_loss_pct:.1%} ({pre_shape[0]:,} -> {post_shape[0]:,} rows, threshold 90%)")
        cp3["failed"] += 1

print(f"Checks: {cp3['passed']} passed, {cp3['warning']} warnings, {cp3['failed']} failed, "
      f"{cp3['not_verified']} not verified, {cp3['skipped']} skipped")
# REASONING: not-verified counts as FAILED — a gate with missing evidence has not gated.
if cp3["failed"] > 0 or cp3["not_verified"] > 0 or (cp3["passed"] + cp3["warning"] + cp3["failed"]) == 0:
    print("CP3 VALIDATION: FAILED")
    raise ValueError("CP3 FAILED - see details above")
elif cp3["warning"] > 0:
    print("CP3 VALIDATION: PASSED WITH WARNINGS")
else:
    print("CP3 VALIDATION: PASSED")

df_transformed.write_parquet(PROJECT_DIR / "data" / "processed" / "2026-01-31_analysis.parquet")

# EXECUTION LOG will be appended here after running:
# bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage7_transform/01_join-data.py
```

**R example:**
```r
# scripts/stage7_transform/01_join-data.R
# Each transformation is a SEPARATE SCRIPT with embedded validation
# NOTE: Scripts use sequential top-level code (no function definitions).

# --- Config ---
library(arrow)
library(dplyr)

# ASSUMES: run_with_capture.sh does not change directory, so every path is built from the absolute project path.
PROJECT_DIR <- "{PROJECT_DIR}"

# --- Load ---
# PRE-STATE CAPTURE
df <- read_parquet(file.path(PROJECT_DIR, "data/processed/2026-01-31_clean.parquet"))
pre_shape <- c(nrow(df), ncol(df))
pre_sample_ids <- df |> slice_sample(n = 5) |> pull(id_col)

cat(sprintf("PRE-STATE: %s rows x %d cols\n", format(pre_shape[1], big.mark = ","), pre_shape[2]))

# --- Transform ---
# EXECUTE TRANSFORMATION
df_transformed <- df |>
  left_join(other_df, by = "join_key")

# POST-STATE CAPTURE
post_shape <- c(nrow(df_transformed), ncol(df_transformed))
cat(sprintf("POST-STATE: %s rows x %d cols\n", format(post_shape[1], big.mark = ","), post_shape[2]))
cat(sprintf("ROW CHANGE: %.1f%%\n", post_shape[1] / pre_shape[1] * 100))

# --- Validate ---
# VALIDATION (CP3)
# INTENT: count outcomes so the verdict line is derived, not asserted.
cp3 <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)

# ASSUMES: an empty input frame makes row loss untestable — 0 rows in is not 0% loss.
if (pre_shape[1] == 0) {
  cat("[FAIL] Row loss: input frame is empty — loss untestable\n")
  cp3["failed"] <- cp3["failed"] + 1L
} else {
  row_loss_pct <- 1 - (post_shape[1] / pre_shape[1])
  if (row_loss_pct < 0.9) {
    cat(sprintf("[PASS] Row loss: %.1f%% (%s -> %s rows, threshold 90%%)\n",
                row_loss_pct * 100, format(pre_shape[1], big.mark = ","),
                format(post_shape[1], big.mark = ",")))
    cp3["passed"] <- cp3["passed"] + 1L
  } else {
    cat(sprintf("[FAIL] Row loss: %.1f%% (%s -> %s rows, threshold 90%%)\n",
                row_loss_pct * 100, format(pre_shape[1], big.mark = ","),
                format(post_shape[1], big.mark = ",")))
    cp3["failed"] <- cp3["failed"] + 1L
  }
}

cat(sprintf("Checks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            cp3[["passed"]], cp3[["warning"]], cp3[["failed"]],
            cp3[["not_verified"]], cp3[["skipped"]]))
# REASONING: not-verified counts as FAILED — a gate with missing evidence has not gated.
if (cp3[["failed"]] > 0 || cp3[["not_verified"]] > 0 ||
    (cp3[["passed"]] + cp3[["warning"]] + cp3[["failed"]]) == 0) {
  cat("CP3 VALIDATION: FAILED\n")
  stop("CP3 FAILED - see details above")
} else if (cp3[["warning"]] > 0) {
  cat("CP3 VALIDATION: PASSED WITH WARNINGS\n")
} else {
  cat("CP3 VALIDATION: PASSED\n")
}

write_parquet(df_transformed, file.path(PROJECT_DIR, "data/processed/2026-01-31_analysis.parquet"))

# EXECUTION LOG will be appended here after running:
# bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage7_transform/01_join-data.R
```

**If validation fails:** Create a new versioned script (`01_join-data_a.py` / `01_join-data_a.R`) with fixes using `bash {BASE_DIR}/scripts/create_script_revision.sh <source> <destination>` (which strips the appended execution log so the revision runs cleanly). Do NOT modify the original -- it serves as audit trail.

#### Stage 7.3: Final CP3 Validation

**Executor:** Subagent invocation (after all transformations complete)
**Purpose:** Overall validation of transformation sequence

**Actions:**
1. Compare original vs. final dataset
2. Generate transformation summary table
3. Verify all expected transformations applied
4. Check for unexpected nulls introduced
5. Verify invariants (totals, IDs preserved)

**CP3 Validation Report (implement in the project's execution language):**
```python
# Overall change summary
print(f"Overall: {original_shape} → {final_shape}")

# Transformation summary table
transformation_summary = pl.DataFrame([
    {"step": 1, "operation": "...", "row_change": "...", "status": "PASSED"},
    {"step": 2, "operation": "...", "row_change": "...", "status": "PASSED"},
    ...
])

# Data quality checks
new_nulls_by_col = {col: post_nulls - pre_nulls for col in ...}

# CP3 Status — the reported status, derived from the printed verdict line
cp3_status = "PASSED" | "WARNING" | "FAILED"
```

> **Log line vs. reported status.** The CP3 code prints a count line and one of three verdict
> strings: `CP3 VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`. The status reported back to
> the orchestrator is the three-valued `PASSED | WARNING | FAILED` used throughout this document.
> The mapping is fixed: `PASSED` ⇒ `PASSED`, **`PASSED WITH WARNINGS` ⇒ `WARNING`**, `FAILED` ⇒
> `FAILED`. The verdict is derived from the counters, never hard-coded — `FAILED` when
> `failed > 0` **or `not_verified > 0`** (a check that could not run has not gated anything) or
> when zero checks ran; `PASSED WITH WARNINGS` when `warning > 0`; `PASSED` otherwise.

> **R projects:** implement the same report with `cat()` for the change summary, a `data.frame`/`tibble` for the transformation summary table, `sapply()`/`dplyr::summarise()` for per-column null deltas, and counter-derived status assignment (`stopifnot()` for the halting conditions). The checks and the PASSED/WARNING/FAILED contract are identical.

### Invocation Template: data-scientist + polars (Python) or tidyverse (R)

**Purpose:** Apply rigorous methodology to analysis
**Stage:** 7 (EDA & Transformation)
**Agent:** research-executor

```python
# ITERATIVE INVOCATION PATTERN (Required for Stage 7)
# One transformation per invocation, never several in one call;
# same-wave transformations may run in parallel (dispatch rule at the top of this file)

# Step 1: Initial EDA (no transformations yet)
Agent({
    description: "Stage 7.1: Initial EDA",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage7_transform/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

**DATA LOCATION:** {PROJECT_DIR}/data/processed/{processed_data_filename}

**TASK:** Perform ONLY initial exploratory data analysis. DO NOT transform data yet.

If execution language is R: "Load `tidyverse` skill for data operations. If spatial data is involved, also load `sf-terra` skill."
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**REQUIRED ACTIONS (from data-scientist skill — preloaded via frontmatter):**
1. Load data
2. Check shape, types, memory usage
3. Profile distributions (head, describe, value_counts)
4. Identify missing values, outliers, unexpected values
5. Document findings

**OUTPUT FORMAT:**
Return findings using the Research Executor Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation:**
- Data shape, type summary, and memory usage
- Key distributions and data quality issues identified
- Readiness assessment for transformations (Yes/No with justification)

Do NOT proceed to transformations. Return findings for orchestrator review.""",
    subagent_type: "research-executor"
})

# Step 2: Execute transformations iteratively (one per invocation, atomically)
# Orchestrator provides specific transformation from Plan_Tasks.md task sequence
# CRITICAL: Include prior transformation context for continuity

Agent({
    description: "Stage 7.2: Execute Transformation #{n}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage7_transform/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

**IMPORTANT:** This is script-based execution, NOT marimo/Quarto. Write transformations to script files (.py or .R) following `{BASE_DIR}/agent_reference/SCRIPT_EXECUTION_REFERENCE.md`.
If execution language is R: "Load `tidyverse` skill for data operations. If spatial data is involved, also load `sf-terra` skill."
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**DATA LOCATION:** {current_data_location}

## PRIOR TRANSFORMATION CONTEXT (REQUIRED)

### From Stage 7.1 (EDA):
- Data shape: {eda_rows} rows × {eda_cols} columns
- Key distributions: {distribution_summary}
- Data quality issues identified:
  - {issue_1}
  - {issue_2}

### Transformations Completed:
| # | Name | Pre-Rows | Post-Rows | Change | CP3 | Issues |
|---|------|----------|-----------|--------|-----|--------|
{for_each_completed_transformation}
| {n-1} | {name} | {pre} | {post} | {%} | {status} | {issues_or_none} |

### Carry-Forward Findings:
{from_prior_transformation_reports}
- {finding_1}
- {finding_2}

### Invariants Established (MUST MAINTAIN):
- {invariant_1_from_prior}
- {invariant_2_from_prior}

---

**YOUR TRANSFORMATION (#{n}):** {specific_transformation_description}

**EXPECTED OUTCOME:** {expected_outcome_from_plan}

**VALIDATION CRITERIA:** {validation_criteria_from_plan}

**JOIN CARDINALITY (if join):** {cardinality_from_plan}
- If this transformation is a join, use the **Join-Specific Validation** inline code template from `{BASE_DIR}/agent_reference/VALIDATION_CHECKPOINTS.md` > "Join-Specific Validation" section
- Embed the cardinality value in the validation code block to verify row count expectations
- Check for fan-out (unexpected row multiplication) or data loss (unexpected row reduction)

**EXECUTION PROTOCOL:**
1. **DESCRIBE:** Confirm what you will do
2. **CODE:** Write transformation code with pre-state capture
3. **EXECUTE:** Run the code
4. **VALIDATE:** Compare pre/post state, check invariants
5. **DECIDE:** Report PASS/FAIL status

**THOROUGHNESS DIRECTIVE:**
- Capture pre-state (shape, sample) BEFORE transforming
- Execute ONLY this one transformation
- Validate immediately after (compare pre/post)
- Use script-based validation (see `{BASE_DIR}/agent_reference/SCRIPT_EXECUTION_REFERENCE.md`)
- Report clear PASS/FAIL with metrics

**OUTPUT FORMAT:**
Return findings using the Research Executor Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation:**
- Pre/post row counts and shape changes for this transformation
- Invariant validation results (pass/fail per invariant)
- Transformation status (PASSED/FAILED) with issue details if failed

Do NOT proceed to transformation #{n+1}. Return to orchestrator for approval.""",
    subagent_type: "research-executor"
})
```

### QA Follow-Up (MANDATORY)

**After research-executor returns from EACH Stage 7 transformation, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** from `full-pipeline-mode.md`
with stage-specific values for Stage 7.

**Do NOT start a transformation that builds on this one, or the next wave, until its QA returns PASSED or WARNING.**

> **QA verdict vocabulary.** A QA script prints a count line
> (`Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info`)
> followed by `QA{n} RESULT: PASSED | WARNING | BLOCKER`. `BLOCKER` if `blockers > 0`; else `WARNING`
> if `warnings > 0` **or `not_verified > 0`** or if zero checks ran; else `PASSED`. A `[NOT VERIFIED]`
> check whose input the Plan explicitly promised escalates to BLOCKER at the reviewer's judgment.
> `BLOCKER` does not satisfy this gate.

```python
# Step 3: Repeat Step 2 AND QA for each transformation in sequence
# Orchestrator increments {n} and provides next transformation
# QA is REQUIRED after EACH transformation, not just at the end

# Step 4: Final CP3 Validation (after all transformations complete)
Agent({
    description: "Stage 7.3: Final CP3 Validation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage7_transform/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

**TASK:** Perform final CP3 validation after all transformations complete.

**DATA LOCATIONS:**
- Original: {PROJECT_DIR}/data/processed/{original_filename}
- Transformed: {PROJECT_DIR}/data/processed/{transformed_filename}

**VALIDATION CHECKS:**
1. Compare original vs. final shape
2. Verify all expected transformations applied
3. Check for unexpected nulls introduced
4. Verify invariants (totals preserved, IDs intact)
5. Generate transformation summary table

**OUTPUT FORMAT:**
### CP3 Validation Report
**Overall change:** {original_shape} → {final_shape}

**Transformation summary:**
| Step | Operation | Row Change | Status |
|------|-----------|------------|--------|

**Data quality:**
- New nulls: {count by column}
- Unexpected changes: {list}

**Checkpoint tally (quote the script's count line):**
`Checks: {passed} passed, {warning} warnings, {failed} failed, {not_verified} not verified, {skipped} skipped`

**CP3 Status:** PASSED | WARNING | FAILED
(Map from the printed verdict: `PASSED` ⇒ PASSED, `PASSED WITH WARNINGS` ⇒ WARNING, `FAILED` ⇒ FAILED. `not verified > 0` ⇒ FAILED.)

If WARNING or FAILED, provide recommendations.""",
    subagent_type: "research-executor"
})
```

### Thoroughness Directive

```
MANDATORY EXECUTION PATTERN:
- Execute ONE transformation per subagent invocation
- Capture pre-state BEFORE every transformation
- Validate IMMEDIATELY after every transformation
- Return to orchestrator after EACH validation
- NEVER batch multiple transformations without intermediate validation
- Use script-based validation (see SCRIPT_EXECUTION_REFERENCE.md)
- Follow Iteration Protocol (DESCRIBE → CODE → EXECUTE → VALIDATE → DECIDE)
```

### Output (Across All Stages)

- **7.1:** EDA summary with data profile
- **7.2:** Validated transformation at each step, intermediate datasets
- **7.3:** Analysis-ready dataset, transformation log, CP3 validation report

### Gate Criteria

**After Stage 7.1 (Gate to 7.2):**
- [ ] Data profiled
- [ ] No blocking data quality issues
- [ ] Ready to proceed to transformations

**After Each Transformation in Stage 7.2 (Gate per transform):**
- [ ] Pre-state captured
- [ ] Transformation executed
- [ ] Validation performed
- [ ] Status reported (PASS/FAIL)
- [ ] **Script saved to `scripts/stage7_transform/`** with standard header
- [ ] **QA review completed for THIS SCRIPT before any dependent script or the next wave starts** (one code-reviewer per script, not batched)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER handled before any dependent script or the next wave: a methodology BLOCKER, raised as a `Methodology Conflict` STOP, escalated to the user; any other BLOCKER resolved through revision)
- [ ] **QA scripts saved to `scripts/cr/stage7_{step}_cr1.py`** (`.R` for R projects) (+ cr2..cr5 if warranted)

**After Stage 7.3 (G7):**
- [ ] All transformations complete
- [ ] CP3 validation passed for all transformations
- [ ] **All QA reviews passed** for all transformation scripts
- [ ] Analysis dataset ready at `data/processed/[date]_analysis.parquet`
- [ ] Transformation log complete
- [ ] **All transformation scripts archived in `scripts/stage7_transform/`**
- [ ] **All QA scripts archived in `scripts/cr/`**
- [ ] **STATE.md updated:** Current Stage: 7, all CP3 statuses, Transformation Progress table current

---

## Stage 8: Analysis & Visualization

**Agent:** research-executor — ITERATIVE INVOCATION REQUIRED
**Skills:** `data-scientist`, `polars` (Python) or `tidyverse` (R), modeling library per Plan — Python: `statsmodels` / `pyfixest` / `linearmodels` / `svy` / `geopandas` / `scikit-learn` / `igraph`; R: `r-stats` / `fixest` / `plm` / `survey-r` / `sf-terra` / `tidymodels` / `igraph-r` (Stage 8.1), `great-tables` (Python) or `gt` (R) (if formatted tables needed), `plotnine` (Python) or `ggplot2` (R), `plotly` (Python) or `plotly-r` (R), `geopandas` (Python) or `sf-terra` (R) (if map viz), `igraph` (Python) or `igraph-r` (R) (if network viz) (Stage 8.2)
**Purpose:** Conduct final statistical analyses on the analysis dataset AND generate visualizations specified in Plan

### Execution Pattern

**Stage 8 is split into 2 sub-stages, executed sequentially:**

```
Stage 8.1.x: Statistical Analysis (one script per analysis task)
    ↓  QA4a after each script (+ QA4b if it drew figures)
Stage 8.2.x: Visualization (one script per visualization task)
    ↓  QA4b after each script
```

**CP4 in every Stage 8 script.** Each analysis and visualization script embeds the CP4 block (`agent_reference/VALIDATION_CHECKPOINTS.md` § CP4: Post-Analysis & Visualization Validation): analysis outputs valid, no nulls in critical columns, every promised figure present, non-empty and inspected with the Read tool, and the input read from `data/processed/` (or the Plan's named input), not `data/raw/`. Write the Stage 8 input path with the literal `data/processed/` in it (Python `PROJECT_DIR / "data/processed/<file>"`, as `research-executor.md` does; R `file.path(PROJECT_DIR, "data/processed/<file>")`), not the component form `PROJECT_DIR / "data" / "processed" / …` the Stage 7 example uses: CP4.4 scans the script text for that literal and reports `[NOT VERIFIED]`, which fails CP4, when it finds none. It halts the script on FAILED, and its status is reported with its count line (`PASSED WITH WARNINGS` maps to WARNING). Deliverable completeness (report sections, Plan consistency) is not CP4: it is Pre-Output Verification at Stage 12.

### Stage 8.1: Statistical Analysis

**Purpose:** Run statistical analyses specified in Plan.md (regressions, correlations, group comparisons, effect sizes, etc.)

**Input:** Analysis dataset from Stage 7 (`data/processed/[date]_analysis.parquet`)
**Output:** Statistical results saved as parquet to `output/analysis/`

#### Actions

1. **Load analysis dataset** — Verify schema matches Plan expectations
2. **Execute analysis tasks** — One script per analysis task from Plan_Tasks.md
3. **Validate assumptions** — Check statistical assumptions before applying methods
4. **Save results** — Parquet format to `output/analysis/`
5. **>>> INVOKE code-reviewer (MANDATORY, QA4a) <<<**
   - After EACH analysis script, orchestrator MUST invoke code-reviewer (QA4a, plus a separate QA4b review when the script drew figures)
   - QA4a validates: statistical methodology, assumption checks, result plausibility
   - If BLOCKER: A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). Any other BLOCKER (a bug, a stub, a validation gap) corrects a defect without changing the method and also goes through revision; a code-reviewer STOP of another Issue Category routes as `full-pipeline-mode.md` § Gate Status Translation says. A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to the next wave of analysis tasks or Stage 8.2

#### Invocation Template

**Purpose:** Run statistical analyses (regression, hypothesis tests, model fitting)
**Stage:** 8.1 (Statistical Analysis)
**Agent:** research-executor
**Skills:** `data-scientist`, `polars` (Python) or `tidyverse` (R), modeling library per Plan — Python: `statsmodels` / `pyfixest` / `linearmodels` / `svy` / `geopandas` / `scikit-learn` / `igraph`; R: `r-stats` / `fixest` / `plm` / `survey-r` / `sf-terra` / `tidymodels` / `igraph-r`

```python
# ITERATIVE INVOCATION PATTERN (Required for Stage 8.1)
# One analysis task per invocation, never several in one call;
# same-wave tasks may run in parallel (dispatch rule at the top of this file)

Agent({
    description: "Stage 8.1: Statistical Analysis - {analysis_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage8_analysis/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name 'polars' (Python) or 'tidyverse' (R).
Call the skill tool with name '{modeling_library}' — Python options: statsmodels, pyfixest, linearmodels, svy, geopandas, scikit-learn, igraph; R options: r-stats, fixest, plm, survey-r, sf-terra, tidymodels, igraph-r — as specified in the <skill> element of Plan_Tasks.md for this task. For spatial regression tasks, geopandas (Python) or sf-terra (R) IS the modeling library. For network/graph analysis tasks, igraph (Python) or igraph-r (R) IS the modeling library. For complex survey data, svy (Python) or survey-r (R) IS the modeling library (design-based inference with Taylor/BRR/jackknife variance).
If formatted tables are needed: "Load `great-tables` skill (Python) or `gt` skill (R) for publication-quality table formatting."
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**IMPORTANT:** This is script-based execution, NOT marimo/Quarto. Write analysis to script files (.py or .R) following `{BASE_DIR}/agent_reference/SCRIPT_EXECUTION_REFERENCE.md`.

**DATA LOCATION:** {PROJECT_DIR}/data/processed/{analysis_data_filename}

## ANALYSIS SPECIFICATION (from Plan.md)

**Model Type:** {model_type} (e.g., OLS regression, logistic regression, t-test, ANOVA, chi-square)
**Hypothesis:** {hypothesis_statement}
**Dependent Variable(s):** {dv_list}
**Independent Variable(s):** {iv_list}
**Control Variable(s):** {control_list_or_none}

**Robustness Strategy:**
- {robustness_check_1} (e.g., alternate specification, sensitivity analysis)
- {robustness_check_2} (e.g., subset analysis, different controls)

**Assumption Validation:**
- {assumption_1} (e.g., normality of residuals, homoscedasticity)
- {assumption_2} (e.g., multicollinearity check via VIF)
- {assumption_3_if_applicable}

## PRIOR TRANSFORMATION CONTEXT (REQUIRED)

### From Stage 7 (Final Dataset):
- Data shape: {final_rows} rows × {final_cols} columns
- Key distributions: {distribution_summary}
- Data quality notes: {quality_notes}

### Carry-Forward Findings:
{from_prior_stage_reports}
- {finding_1}
- {finding_2}

---

**OUTPUT LOCATIONS:**
- Statistical results: {PROJECT_DIR}/output/analysis/{date_prefix}_{analysis_name}.parquet
- Summary tables: {PROJECT_DIR}/output/analysis/{date_prefix}_{analysis_name}_summary.parquet
- Figures (if produced): {PROJECT_DIR}/output/figures/{date_prefix}_{analysis_name}_{plot_type}.png

**RISK REGISTER ITEMS FOR THIS TASK:**
| Risk | Likelihood | Impact | Mitigation | Watch For |
|------|------------|--------|------------|-----------|
| {risk_name} | {L/M/H} | {L/M/H} | {specific_action} | {symptom_to_monitor} |

During execution, ACTIVELY MONITOR for watch-for symptoms. Escalate if detected.

**EXECUTION PROTOCOL:**
1. **DESCRIBE:** State the model specification and expected outcome
2. **VALIDATE ASSUMPTIONS:** Run assumption checks BEFORE fitting model
3. **FIT MODEL:** Execute primary analysis
4. **ROBUSTNESS:** Run robustness checks
5. **VALIDATE:** Verify results are interpretable and consistent
6. **SAVE:** Export results to output/analysis/

**THOROUGHNESS DIRECTIVE:**
- Validate ALL model assumptions before interpreting results
- Report assumption violations explicitly (do NOT ignore)
- Include effect sizes alongside p-values
- Run at least one robustness check
- Save all results as parquet for downstream use
- If producing figures, save to output/figures/

**OUTPUT FORMAT:**
Return findings using the Research Executor Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation:**
- Analysis results summary (key coefficients, effect sizes, p-values, model fit)
- Assumption check outcomes and robustness check consistency
- CP4 status with its count line
- File paths created (`output/analysis/`, `output/figures/` if applicable)

Do NOT proceed to next analysis task. Return to orchestrator for approval.""",
    subagent_type: "research-executor"
})
```

#### QA Follow-Up for Stage 8.1 (MANDATORY)

**After research-executor completes each Stage 8.1 analysis script, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** from `full-pipeline-mode.md`
with stage-specific values for Stage 8. Use **QA4a** (statistical validity) for the analysis script.

**If the analysis script also produced figures**, invoke code-reviewer again with **QA4b** (visualization quality) for those figures.

**Do NOT start a task that builds on this analysis, or the next wave, until QA4a, and QA4b if this script drew figures, return PASSED or WARNING.**

### Stage 8.2: Visualization

**Purpose:** Create visualizations specified in Plan, informed by Stage 8.1 results

**Input:** Analysis dataset from Stage 7 + statistical results from Stage 8.1
**Output:** Figures saved to `output/figures/`

#### Actions

1. **Create exploratory plots** — Distributions, relationships, patterns
2. **Create final visualizations** — As specified in Plan.md and Plan_Tasks.md, striving for publication-quality
3. **Export figures** — static figures as PNG (plotnine / ggplot2), interactive figures as HTML (plotly / plotly-r), appropriate dimensions, to `output/figures/`
4. **>>> INVOKE code-reviewer (MANDATORY, QA4b) <<<**
   - After EACH visualization script, orchestrator MUST invoke code-reviewer
   - QA4b validates: figure existence, data source accuracy, labeling, visual clarity
   - If BLOCKER: A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). Any other BLOCKER (a bug, a stub, a validation gap) corrects a defect without changing the method and also goes through revision; a code-reviewer STOP of another Issue Category routes as `full-pipeline-mode.md` § Gate Status Translation says. A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to the next wave of visualization tasks or Stage 9

#### Invocation Template: plotnine (Python) or ggplot2 (R)

**Purpose:** Static visualizations (grammar of graphics)
**Stage:** 8.2 (Visualization)
**Agent:** research-executor
**Skills:** `data-scientist`, `plotnine` (Python) or `ggplot2` (R)

```python
Agent({
    description: "Stage 8.2: Visualization - Static Plots",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage8_analysis/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name 'plotnine' (Python) or 'ggplot2' (R).
If formatted summary tables are needed: "Load `great-tables` skill (Python) or `gt` skill (R) for publication-quality table formatting."
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**VISUALIZATION SPECIFICATION (from Plan.md):**
{visualization_requirements}

**DATA LOCATION:** {PROJECT_DIR}/data/processed/{analysis_data_filename}

**OUTPUT LOCATION:** {PROJECT_DIR}/output/figures/

**REQUIRED PLOTS:**
1. {plot_1_description} → {date_prefix}_{plot_1_name}.png
2. {plot_2_description} → {date_prefix}_{plot_2_name}.png

**STYLE REQUIREMENTS:**
- Theme: minimal/clean
- DPI: 300
- Dimensions: as appropriate for content

**VISUAL INSPECTION:** After successful execution, use the **Read tool** to view each generated PNG file. Verify layout, labels, legend readability, and data representation before reporting.

Return the plotting code and confirm files are saved.""",
    subagent_type: "research-executor"
})
```

#### Invocation Template: plotly (Python) or plotly-r (R)

**Purpose:** Interactive visualizations (saved as HTML only)
**Stage:** 8.2 (Visualization)
**Agent:** research-executor
**Skills:** `data-scientist`, `plotly` (Python) or `plotly-r` (R)

Static image export from plotly (kaleido, orca) is not installed in DAAF (`plotly` and `plotly-r` skills). A figure that also needs a PNG (for the report, the executor's visual inspection, or the QA4b review) gets a separate static version from the plotnine / ggplot2 template above.

```python
Agent({
    description: "Stage 8.2: Visualization - Interactive Plots",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage8_analysis/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name 'plotly' (Python) or 'plotly-r' (R).
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**VISUALIZATION SPECIFICATION (from Plan.md):**
{visualization_requirements}

**DATA LOCATION:** {PROJECT_DIR}/data/processed/{analysis_data_filename}

**OUTPUT LOCATION:** {PROJECT_DIR}/output/figures/

**REQUIRED PLOTS:**
1. {plot_description} → {date_prefix}_{plot_name}.html (interactive)

Save each figure as HTML only (`write_html` in Python, `htmlwidgets::saveWidget()` in R). Do not attempt a PNG export: kaleido and orca are not installed. Any PNG version of these figures comes from a separate plotnine / ggplot2 script.

**INTERACTIVITY REQUIREMENTS:**
- Hover information: {hover_fields}
- Selection: {selection_type}

**OUTPUT CHECK:** After successful execution, confirm each HTML file exists and is non-empty. Visual inspection with the **Read tool** is done on the PNG of the figure's static version.

Return the plotting code and confirm files are saved.""",
    subagent_type: "research-executor"
})
```

#### Invocation Template: geopandas (Python) or sf-terra (R) (Map Visualization)

**Purpose:** Choropleth maps, spatial plots, dot-density maps
**Stage:** 8.2 (Map Visualization)
**Agent:** research-executor
**Skills:** `data-scientist`, `geopandas` (Python) or `sf-terra` (R)

```python
Agent({
    description: "[3-5 word summary]",
    subagent_type: "research-executor",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

## SKILL LOADING
Call the skill tool with name 'geopandas' (Python) or 'sf-terra' (R).
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

## CONTEXT FROM PLAN
[Paste relevant Plan.md methodology sections and Plan_Tasks.md task blocks]

Research Question: {research_question}
Current Stage: 8.2

## TASK
**Script Target:** {PROJECT_DIR}/scripts/stage8_analysis/{step:02d}_{task-name}.py (.py for Python, .R for R)
**Map Type:** {map_type} (e.g., choropleth, dot-density, proportional symbol, bivariate)
**Geographic Unit:** {geographic_unit} (e.g., county, state, school district, tract)
**Variable(s) to Map:** {variables}
**Classification Scheme:** {scheme} (e.g., quantiles, natural breaks, equal interval)
**Output:** {PROJECT_DIR}/output/figures/{date}_{description}.png
**Input Data:** {input_data_path}
**Shapefile/Geometry Source:** {geometry_source}

## EXECUTION
Follow the file-first execution protocol:
1. Write script to target path
2. Execute via: bash {BASE_DIR}/scripts/run_with_capture.sh {script_path}
3. Verify output file exists and is non-zero size
4. Use the **Read tool** to view each generated PNG file — verify layout, labels, legend readability, geographic accuracy, and data representation before reporting
"""
})
```

#### QA Follow-Up for Stage 8.2 (MANDATORY)

**After research-executor completes each Stage 8.2 visualization script, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** from `full-pipeline-mode.md`
with stage-specific values for Stage 8. Use **QA4b** (visualization quality) for visualization scripts.

**Do NOT start a task that builds on this visualization, or the next wave, until its QA4b returns PASSED or WARNING. Do NOT proceed to Stage 9 until every Stage 8 script has passed its reviews: QA4a for each analysis script, QA4b for each visualization script and for each analysis script that drew figures.**

### Analysis Principles

```
- Validate statistical assumptions BEFORE applying methods (normality, homoscedasticity, etc.)
- Document all methodology decisions with rationale in script comments (IAT)
- Perform robustness checks where appropriate (sensitivity analysis, alternative specifications)
- Report effect sizes alongside statistical significance
- Save all intermediate and final results as parquet (never just print to log)
- Follow the Iteration Protocol: one analysis per script, validate before proceeding
```

### Visualization Principles

The snippets assume `PROJECT_DIR` is set in the script's Config section, as in the Stage 7 example (`PROJECT_DIR = Path("{PROJECT_DIR}")` in Python, `PROJECT_DIR <- "{PROJECT_DIR}"` in R).

**Static — Python (plotnine):**
```python
from plotnine import ggplot, aes, geom_point, theme_minimal

plot = (
    ggplot(df, aes(x='var1', y='var2'))
    + geom_point()
    + theme_minimal()
)
plot.save(f"{PROJECT_DIR}/output/figures/{date_prefix}_plot_name.png", dpi=300)
```

**Static — R (ggplot2):**
```r
library(ggplot2)

p <- ggplot(df, aes(x = var1, y = var2)) +
  geom_point() +
  theme_minimal()
ggsave(file.path(PROJECT_DIR, sprintf("output/figures/%s_plot_name.png", date_prefix)), p, dpi = 300)
```

**Interactive — Python (plotly):**
```python
import plotly.express as px

fig = px.scatter(df, x='var1', y='var2', color='category')
fig.write_html(f"{PROJECT_DIR}/output/figures/{date_prefix}_plot_name.html")
# Note: kaleido/write_image is not available in DAAF — use plotnine for static PNG export
```

**Interactive — R (plotly):**
```r
library(plotly)

fig <- plot_ly(df, x = ~var1, y = ~var2, color = ~category, type = "scatter", mode = "markers")
htmlwidgets::saveWidget(fig, file.path(PROJECT_DIR, sprintf("output/figures/%s_plot_name.html", date_prefix)))
# Note: orca()/kaleido() static export is not available in DAAF — use ggplot2 for static PNG export
```

### Context Requirements

**Stage 8.1 (Analysis) — Orchestrator must provide:**

| Context Item | Source | Required In Prompt |
|--------------|--------|-------------------|
| Analysis dataset path | Stage 7 output | YES — exact path |
| Research question | Plan.md | YES — verbatim |
| Analysis specification | Plan.md (Analysis Requirements) | YES — methods, variables, hypotheses |
| Task specification | Plan_Tasks.md | YES — specific task block for this analysis |
| Research Outcome contribution | Plan.md | YES — which outcomes this analysis addresses |
| Statistical assumptions to check | Plan.md / data-scientist skill | YES — method-specific |
| Risk Register items | Plan.md | YES — relevant risks |

**Stage 8.2 (Visualization) — Orchestrator must provide:**

| Context Item | Source | Required In Prompt |
|--------------|--------|-------------------|
| Analysis dataset path | Stage 7 output | YES — exact path |
| Statistical results path(s) | Stage 8.1 output | YES — exact paths from `output/analysis/` |
| Visualization specification | Plan.md (Visualization Requirements) + Plan_Tasks.md task block | YES — plot types, variables, dimensions |
| Key findings from 8.1 | Stage 8.1 results | YES — what to highlight in visualizations |
| Figure naming convention | Plan.md | YES — date prefix + descriptive name |

### QA Context (code-reviewer invocations)

| Context Item | QA4a (Analysis) | QA4b (Visualization) |
|--------------|-----------------|---------------------|
| Script path | YES | YES |
| Plan.md methodology + Plan_Tasks.md task spec | YES — statistical methods, expected directions | YES — figure specs, labeling requirements |
| QA tolerance thresholds | YES — methodology validity, assumption violations | YES — figure existence, data accuracy |
| Prior QA findings | YES — accumulated from 8.1 scripts | YES — accumulated from 8.1 + 8.2 scripts |
| Research Outcome contribution | YES | YES |

### Output

- **Stage 8.1:** Statistical result files in `output/analysis/` (parquet), analysis summaries
- **Stage 8.2:** Exported figure files in `output/figures/`, figure descriptions for report

### Completion Checklist

- [ ] All planned statistical analyses executed (Stage 8.1)
- [ ] Statistical results saved to `output/analysis/`
- [ ] All planned visualizations created (Stage 8.2)
- [ ] Figures exported to `output/figures/`
- [ ] All analysis scripts saved to `scripts/stage8_analysis/` with standard header
- [ ] All visualization scripts saved to `scripts/stage8_analysis/` with standard header
- [ ] CP4 PASSED (or PASSED WITH WARNINGS, reported WARNING) in every Stage 8 script, with its count line
- [ ] QA4a completed for EACH analysis script individually (PASSED/WARNING), invoked immediately after each script
- [ ] QA4b completed for EACH visualization script, and for each analysis script that also produced figures, individually (PASSED/WARNING), invoked immediately after each script

### Gate Criteria (G8)

- [ ] All planned analyses and visualizations created
- [ ] Statistical results exported to `output/analysis/`
- [ ] Figures exported to `output/figures/`
- [ ] **All scripts saved to `scripts/stage8_analysis/`** with standard header
- [ ] **CP4 PASSED in every Stage 8 script** (or PASSED WITH WARNINGS, reported WARNING), with its count line
- [ ] **QA4a review completed for EACH analysis script** (one code-reviewer per script, before any dependent script or the next wave starts — not batched)
- [ ] **All QA4a statuses:** PASSED/WARNING (any BLOCKER handled before any dependent script or the next wave: a methodology BLOCKER, raised as a `Methodology Conflict` STOP, escalated to the user; any other BLOCKER resolved through revision)
- [ ] **QA4b review completed for EACH visualization script, and for each analysis script that also produced figures** (one code-reviewer per script, before any dependent script or the next wave starts — not batched)
- [ ] **All QA4b statuses:** PASSED/WARNING (any BLOCKER handled before any dependent script or the next wave: a methodology BLOCKER, raised as a `Methodology Conflict` STOP, escalated to the user; any other BLOCKER resolved through revision)
- [ ] **QA scripts saved to `scripts/cr/stage8_{step}_cra1.py`** (analysis) and **`stage8_{step}_crb1.py`** (viz, and an analysis script that also produced figures, which gets both) (`.R` for R projects)
- [ ] **STATE.md updated:** Current Stage: 8, CP4, QA4a and QA4b status, analysis result paths, figure paths recorded

### Multi-Skill Invocation Templates

#### Combined EDA + Transformation (Stage 7)

When EDA and transformation are closely linked:

```python
Agent({
    description: "Stage 7: EDA & Transformation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage7_transform/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name 'polars' (Python) or 'tidyverse' (R).
If this task involves spatial operations (spatial join, point-in-polygon, buffer, geocoding, or working with geometry columns): also call the skill tool with name 'geopandas' (Python) or 'sf-terra' (R).
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**DATA LOCATION:** {PROJECT_DIR}/data/processed/{filename}

**TASK:**
1. Profile the data following data-scientist methodology (preloaded via frontmatter)
2. Implement transformations using Polars (Python) or tidyverse (R)
3. Validate each step

**TRANSFORMATION SPECIFICATION:**
{transformation_spec_from_plan}

Return comprehensive EDA findings and validated transformation code.""",
    subagent_type: "research-executor"
})
```

#### Combined Visualization (Stage 8.2)

When both static and interactive plots are needed:

```python
Agent({
    description: "Stage 8.2: Visualization - Combined",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage8_analysis/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name 'plotnine' (Python) or 'ggplot2' (R) for static publication plots.
Call the skill tool with name 'plotly' (Python) or 'plotly-r' (R) for interactive exploration plots.
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**DATA LOCATION:** {PROJECT_DIR}/data/processed/{filename}

**STATIC PLOTS (plotnine / ggplot2, saved as PNG; inspect each with the Read tool):**
{static_plot_specs}

**INTERACTIVE PLOTS (plotly / plotly-r, saved as HTML only; kaleido and orca are not installed, so a PNG of any of these comes from the static plots above):**
{interactive_plot_specs}

**OUTPUT:** {PROJECT_DIR}/output/figures/

Return all plotting code and confirm files saved.""",
    subagent_type: "research-executor"
})
```

---

## Stage 9: Script Compilation (NOT Dashboard Building)

**Agent:** `notebook-assembler` (see `.claude/agents/notebook-assembler.md`)
**Skill:** `marimo` (Python) or `quarto` (R) — for basic syntax only; agent provides behavioral constraints
**Purpose:** LITERALLY COPY script file contents into notebook cells (marimo .py or Quarto .qmd)

> **CRITICAL:** Stage 9 is a FILE COMPILATION task. See `.claude/agents/notebook-assembler.md`
> for the complete protocol. Python uses the canonical Marimo three-cell archive
> bundle (header, source, immediately adjacent execution log) followed by an
> optional display cell; R uses the canonical Quarto heading + archive chunk +
> immediately following Execution Log callout + optional display pattern defined
> in `.claude/skills/quarto/references/daaf-notebook.md`.

### Key Constraints (Summary)

- **LITERAL COPY** — Read each script and archive its code without changing its analysis logic
- **Marimo/Python** — Three contiguous archive cells per script (header, comment-prefixed source ending with `pass`, and immediately adjacent `mo.accordion()` log held in a raw `mo.md(r'''...''')` literal, so backslashes in the log stay verbatim); an optional post-bundle display may use `pl.read_parquet()` + `mo.ui.table(..., selection=None, show_column_summaries=False)` or show an existing figure with `mo.image()`
- **Quarto/R** — Heading + literal un-commented R archive chunk + immediately following collapsed Execution Log callout + optional display: either the non-transforming Parquet preview or an existing saved Stage 8 figure; every archive chunk has `#| code-fold: false`, `#| eval: false`, and the exact `# --- VERBATIM COPY of scripts/<path> ---` marker, while YAML sets global `execute: eval: false`
- **Quarto figure display** — Prefer standard Markdown image syntax. The only chunk alternative is a dedicated `#| eval: true`, `#| echo: false` chunk containing only `knitr::include_graphics("existing/path.png")`; it never creates a new visualization.
- **Execution evidence** — Every final script must have a real, non-empty execution log. A missing log or placeholder such as `No execution log found` blocks canonical Stage 9 assembly; do not archive it as evidence.
- NO new analysis code, dashboards, widgets, filters, aggregations, summaries, or visualizations
- Script versioning: use the final successful version (`_b.py`/`_b.R` > `_a.py`/`_a.R` > base) and document prior versions

### ABSOLUTE PROHIBITIONS

The following are **NEVER ALLOWED** in Stage 9 notebooks:

| Prohibited | Why |
|------------|-----|
| `mo.ui.dropdown()` | Not a dashboard |
| `mo.ui.slider()` | Not a dashboard |
| `mo.ui.multiselect()` | Not a dashboard |
| `mo.ui.text()` for search | Not a dashboard |
| `mo.ui.dataframe()` | No transform editor — it filters, groups, aggregates, and pivots |
| `mo.ui.data_editor()` | No data editing — display existing data only |
| `.group_by()` (new) | No new aggregations |
| `.agg()` (new) | No new aggregations |
| `.pivot()` (new) | No new pivot tables |
| `.filter()` in data cells | Just load and display |
| `.with_columns()` in data cells | Just load and display |
| "Interactive Filters" section | Not a dashboard |
| "Data Explorer" with new code | Not a dashboard |
| "Institution Lookup" feature | Not a dashboard |
| New visualizations | Stage 8 created them |

**If the notebook contains ANY of the above, it FAILED.**

### Invocation Template: marimo (Python) or quarto (R) (via notebook-assembler)

**Purpose:** COMPILE executed scripts into notebook by LITERALLY COPYING file contents
**Stage:** 9 (Script Compilation)
**Agent:** notebook-assembler (see `.claude/agents/notebook-assembler.md`)
**Subagent:** notebook-assembler

> **Language note:** For Python projects, produce a Marimo notebook (`.py`) using the canonical three-cell archive bundle plus optional post-bundle display. For R projects, produce a Quarto notebook (`.qmd`) using the canonical archive-section pattern in `.claude/skills/quarto/references/daaf-notebook.md`. The notebook-assembler agent handles both formats -- load `marimo` for Python or `quarto` for R.

> **CRITICAL CONSTRAINT:** The notebook LITERALLY COPIES script file contents into cells. It does NOT generate new code, dashboards, filters, or interactive widgets. The notebook is a script viewer.

> **WHAT THIS IS:** A compiler that copies files into cells.
> **WHAT THIS IS NOT:** A dashboard builder, an analysis tool, or an interactive explorer.

```python
Agent({
    description: "Stage 9: Compile Scripts into Notebook",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; the Marimo template's `PROJECT_DIR` cell is set to it, and every display path and Step 6 command builds on it)

Also call the skill tool with name 'marimo' (Python) or 'quarto' (R) for basic notebook syntax.

## CRITICAL: YOU ARE A COMPILER, NOT AN ANALYST

Your job is to:
1. READ each script file from `scripts/`
2. For Python, COPY code into the source cell of a canonical three-cell Marimo archive bundle; for R, COPY code literally and un-commented into a Quarto archive chunk with `#| code-fold: false`, `#| eval: false`, and the exact `# --- VERBATIM COPY of scripts/<path> ---` marker
3. COPY the execution log VERBATIM into a collapsed Marimo accordion or the immediately following collapsed Quarto callout titled `Execution Log`
4. OPTIONALLY ADD ONLY the format-specific display: `pl.read_parquet()` + `mo.ui.table(..., selection=None, show_column_summaries=False)` or an existing-figure `mo.image()` (Python); for R, the canonical `arrow::read_parquet()` + `dplyr::glimpse(df)` + `head(df, 20)` preview or an existing saved figure (Markdown image preferred; a dedicated `knitr::include_graphics()` chunk is allowed only with `#| eval: true`, `#| echo: false`, and no other R statements)

You are a COPY-PASTE MACHINE with formatting. Nothing more.

## WHAT YOU MUST NOT DO (ABSOLUTE PROHIBITIONS)

NO dashboards, NO widgets, NO new aggregations, NO new visualizations, NO paraphrasing script code. See the full prohibition table above.

## SCRIPTS LOCATION

scripts/
├── stage5_fetch/   ← Read each .py/.R file
├── stage6_clean/   ← Read each .py/.R file
├── stage7_transform/ ← Read each .py/.R file
└── stage8_analysis/ ← Read each .py/.R file

## ASSEMBLE EACH SCRIPT USING THE SELECTED FORMAT

### Python / Marimo: Three-Cell Archive Bundle + Optional Display

1. **Header cell (Markdown):** script name, paths, status, and version history
2. **Code archive cell:** VERBATIM Python code copy, every line prefixed with `# `, ending with `pass`
3. **Immediately adjacent execution-log cell:** VERBATIM log in a collapsed `mo.accordion()`, held in a RAW literal: `mo.md(r'''...''')`, or the `r`-prefixed triple-double-quote form when the log contains `'''`; a log containing both delimiters is a STOP (notebook-assembler "Marimo: Format the Log Literal")

After the complete three-cell bundle, an **optional inspection/display cell** may contain only:
    ```python
    df_5_1 = pl.read_parquet(PROJECT_DIR / "path/to/output.parquet")
    mo.ui.table(df_5_1.head(100), selection=None, show_column_summaries=False)
    ```
    `selection=None` drops the row-selection checkboxes and
    `show_column_summaries=False` the column summary charts: a plain read-only table.
    For an existing saved figure, use `mo.image(PROJECT_DIR / "...")` instead of
    creating a plot, passing the `Path` itself, never `str(...)` (only a `Path`
    to a missing file fails the Step 6b check).
    Build every display path from `PROJECT_DIR` and give each preview its own
    name (`df_5_1`, `df_5_2`, ...); a relative path or a reused name fails the
    Step 6 checks.

### R / Quarto: Canonical Archive-Section Pattern

1. **Script heading:** script name, paths, status, and version history
2. **Archive chunk:** literal, un-commented R code beneath all three required anchors:
    ```r
    #| code-fold: false
    #| eval: false

    # --- VERBATIM COPY of scripts/stageN_type/script.R ---
    ```
3. **Execution Log callout:** VERBATIM log in the immediately following `::: {.callout-note collapse="true" title="Execution Log"}` block
4. **Optional display:** one of exactly two permitted Stage 9 display types:
    - **Non-transforming Parquet preview:** explicitly opts into `#| eval: true` and contains only:
      ```r
      df <- arrow::read_parquet("path/to/output.parquet")
      dplyr::glimpse(df)
      head(df, 20)
      ```
    - **Existing saved figure:** prefer standard Markdown image syntax. The dedicated chunk alternative uses `#| eval: true`, `#| echo: false`, and contains only `knitr::include_graphics("existing/path.png")`.

    Neither display type may create a plot, transform data, summarize, or add other R statements.

The Quarto YAML MUST use the canonical rich baseline (title, subtitle, author,
date, HTML `toc`, `toc-depth`, `code-fold`, `embed-resources`, `theme`, and
global `execute: echo: true`, `eval: false`, `warning: false`). Nothing in
either format may filter, mutate, aggregate, summarize, or create a new figure.

## LITERAL COPY EXAMPLE

If script file contains:
```
import polars as pl

print("Hello")

# EXECUTION LOG
# Executed: 2026-01-24
# STDOUT: Hello
```

Then Marimo Cell 2 should contain the Python code as a comment-prefixed archive:
```python
# SOURCE: scripts/stage5_fetch/01_example.py
# import polars as pl
#
# print("Hello")
pass
```
(R/Quarto: this is an archive chunk, not Cell 2. It includes `#| code-fold: false`, `#| eval: false`, then `# --- VERBATIM COPY of scripts/stage5_fetch/01_fetch-source.R ---` — the exact anchor `scripts/decompile_notebook.R` uses to extract scripts — followed by the literal, un-commented R code.)

The Marimo Cell 3 accordion should contain EXACTLY the log lines below the `# EXECUTION LOG` marker with their `# ` prefix removed (here `Executed: 2026-01-24` and `STDOUT: Hello`; a real `run_with_capture.sh` log also has `=====` banner lines, which are dropped), inside one plain fence in a raw `mo.md(r'''...''')` literal. A raw literal keeps every backslash in the log as printed; never use a non-raw string. The fence is three backticks unless the log itself contains a run of three or more, in which case it is one backtick longer than the longest run, so no log line can close it early.

## OUTPUT

**Notebook file:** {PROJECT_DIR}/{date_prefix}_{title}.py (Python/Marimo) or {PROJECT_DIR}/{date_prefix}_{title}.qmd (R/Quarto)

## VERIFICATION BEFORE RETURNING

For Marimo, confirm every script has one complete three-cell header/source/log archive bundle, any optional display follows that bundle, and no archived Python code is live. For Quarto, confirm every script has one heading, one literal archive chunk with both eval guards plus `code-fold: false` and the exact marker, and the immediately following Execution Log callout. Then reject any of these in newly authored notebook scaffolding:
- Marimo UI inputs or R/Shiny/htmlwidgets inputs
- group-by/summarise operations outside archived script code
- pivots outside archived script code
- filters in optional inspection code
- `with_columns` / `mutate` in optional inspection code
- newly generated visualizations

The ONLY acceptable optional new code is `pl.read_parquet()` + `mo.ui.table(..., selection=None, show_column_summaries=False)` / existing-figure display (Python), or `arrow::read_parquet()` + `dplyr::glimpse(df)` + `head(df, 20)` / existing-figure display (R).

Before emitting each Cell 3, run the delimiter and fence searches on the script's EXECUTION LOG section (notebook-assembler "Marimo: Check the Log Before Emitting Cell 3"); never edit a log to fit a fence.

Then run your Step 6 checks exactly as notebook-assembler Step 6 defines them, and quote the evidence each requires. Python: 6a `marimo check {PROJECT_DIR}/{date_prefix}_{title}.py --format json --select MB` (never `--fix`, `--unsafe-fixes` or `--strict`); 6b `marimo export html` writing to `{PROJECT_DIR}/__marimo__/stage9_check/{date_prefix}_{title}.html` (never `marimo run --headless`); 6c decompile into a new `{PROJECT_DIR}/__marimo__/stage9_check/decompiled_{date_prefix}_{title}_{n}` folder with `python3 /daaf/scripts/decompile_notebook.py` and compare with `git diff --no-index --numstat --ignore-space-at-eol --ignore-blank-lines {PROJECT_DIR}/scripts <that folder>`. 6c passes only when all four of its conditions hold: (i) a clean decompile; (ii) the `Validated {N}` count equals your Step 1 final-version inventory, built from the scripts directory; (iii) the decompiled paths are exactly those final-version paths; (iv) every numstat line is an ` => dev/null}` line or the single `MANIFEST.md` line. Judge 6c by those lines, never by the `git diff` exit code. Then run the trailing-whitespace search (`[ \t]$`) on each final script and report every match as an INFO under Issues Found (Step 6c says why). Never alter archived code or log text to pass any check: if that is the only fix, STOP and report; a failure of 6c (ii), (iii) or (iv) is always a STOP. R: `quarto render {PROJECT_DIR}/{date_prefix}_{title}.qmd`.""",
    subagent_type: "notebook-assembler"
})
```

**Render and export evidence for Stage 12.** Record notebook-assembler's Step 6 outcome in STATE.md § Final Review Log > Stage 9 Check Evidence (Python: the `marimo check` summary, the `marimo export html` exit code and the 6c result; R: the `quarto render` exit status and the rendered HTML path; each with the timestamp of the run, so Stage 12 can tell whether a later edit or failed re-render postdates it). data-verifier never re-runs the export, render or decompiler at Stage 12 (a read-only `marimo check` is allowed; data-verifier anti-pattern 8); it reads this evidence.

### Invocation Template: integration-checker (Stage 9 wiring check)

**Purpose:** Verify the new notebook is wired to the data, figures and QA scripts it claims
**Stage:** 9, after notebook-assembler returns PASSED or WARNING
**Agent:** integration-checker (see `.claude/agents/integration-checker.md`, Core Behavior 6 for the per-stage scope)
**Model:** `sonnet` (frontmatter default)

```python
Agent({
    description: "Stage 9: Integration Check (notebook wiring)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**STAGE:** 9 (Report not written yet; use the Stage 9 scope in your Core Behavior 6)

**CONTEXT:**
- Plan path: {plan_path}
- Notebook path: {notebook_path}
- Project folder: {PROJECT_DIR}
- Execution scripts and their output files (Stages 5-8): {script_output_list}
- Expected figures (Plan.md / Stage 8): {figure_list}

**TASK:**
Check notebook -> data and notebook -> figure references, script -> QA-script
coverage in scripts/cr/, stage transitions 5 -> 9, and data orphans. Read-only:
no files written, no Python or R of your own, no render or export.

Return findings using the Integration Checker Output Format, naming the
protocol steps that were out of scope at this stage.""",
    subagent_type: "integration-checker"
})
```

**Handling the verdict** (`full-pipeline-mode.md` § Gate Status Translation; `ERROR_RECOVERY.md` § Error Recovery Routing, "Integration issue"): Record every verdict in the Stage 9 row of STATE.md § Final Review Log > Integration Checks. CONNECTED (INFO findings allowed) satisfies the G9 wiring checkbox. ISSUES FOUND at WARNING: log it in that row; Stage 10 reads that row and carries the WARNING into the QA Summary Report. ISSUES FOUND at BLOCKER or a STOP: the gate is not satisfied; the orchestrator routes the fix (notebook path or display fixes to notebook-assembler; a missing QA script to code-reviewer; a missing or misplaced output to research-executor or debugger), then re-dispatches integration-checker for Stage 9. Orphans are INFO and never deleted.

### Gate Criteria (G9)

- [ ] All final successful script versions identified; prior versions documented
- [ ] **Marimo:** every script has a complete three-cell header/source/log archive bundle; archived Python is comment-prefixed with trailing `pass`; any optional display follows the bundle; the `marimo check --select MB` structural gate passes (exit 0, `summary.errored` false, `summary.files_with_issues` 0) and the `marimo export html` execution check exits 0, and the Step 6c verbatim fidelity check passes all four conditions (clean decompile; bundle count and decompiled paths equal the Step 1 final-version inventory; every numstat line is an ` => dev/null}` line or the single `MANIFEST.md` line; notebook-assembler Step 6c), with the assembler's report quoting the evidence for each
- [ ] **Quarto:** every script uses heading + literal archive chunk + immediately following Execution Log callout + optional inspection; archive chunks include `#| code-fold: false`, per-chunk `#| eval: false`, and the exact decompiler marker; canonical rich YAML includes global `execute: eval: false`
- [ ] **Quarto render:** `quarto render` completes with only explicitly enabled optional previews evaluated; archived Stage 5-8 scripts are not re-run, and render success is not represented as full analysis reproduction
- [ ] Navigation is format-appropriate (Marimo navigation/TOC cells; Quarto YAML TOC and Markdown headings)
- [ ] Optional data and figure displays resolve existing artifacts without transformation or new visualization
- [ ] Every final script has a real, non-placeholder execution log displayed verbatim in a collapsed Marimo accordion (raw `mo.md()` literal) or immediately following collapsed Quarto callout
- [ ] **Wiring:** integration-checker (Stage 9 scope) returned CONNECTED, or ISSUES FOUND with WARNING only (logged in STATE.md § Integration Checks); no BLOCKER open

---

## Stage 10: QA Aggregation

**Executor:** Orchestrator (no subagent — performed directly by orchestrator)
**Skills:** —
**Purpose:** Aggregation point for all QA findings from Stages 5-8

### Actions

1. **Aggregate Continuous QA Findings**
   - Collect all WARNING items logged during Stages 5-8
   - Collect all INFO items logged during Stages 5-8
   - Collect any WARNING carried from the Stage 9 integration check (the Stage 9 row of STATE.md § Final Review Log > Integration Checks) and list it under Outstanding WARNINGs
   - Review for patterns across multiple scripts
   - Document BLOCKER issues that were resolved (and how)

2. **Generate QA Summary Report**
   - Use the template in `agent_reference/QA_CHECKPOINTS.md` § Integration with Stage 10 > QA Summary for Stage 10 (Execution Overview, Resolved BLOCKERs, Outstanding WARNINGs, INFO Items)
   - In the Execution Overview, give Stage 8 two rows, `8 (QA4a)` and `8 (QA4b)`, because an analysis script that drew figures has one review of each kind
   - List any WARNING carried from the Stage 9 integration check under Outstanding WARNINGs (step 1)

3. **Review WARNING Patterns**
   - Identify systemic issues across multiple scripts
   - Assess cumulative impact of individual WARNINGs
   - Flag any WARNING clusters that together constitute a concern

### Invocation Pattern

Stage 10 is performed by the orchestrator directly (no dedicated subagent). The orchestrator reviews all accumulated code-reviewer findings from Stages 5-8.

**PSU Note:** Stage 10 concludes Phase 4. The orchestrator will present PSU4 to the user with the complete analysis picture. PSU4 is compiled from accumulated Stage 7-8 results plus this QA aggregation.

### Post-Script Action Checklist (Stages 7-8)

After each script execution:
1. **QA:** Invoke code-reviewer immediately (see `full-pipeline-mode.md` > Code-Reviewer Invocation)
2. **State:** Update STATE.md transformation progress table
3. **Citations (Stages 7-8):** After each Stage 7 or Stage 8 script completes, check the research-executor's output for a `### Citations` section. If present, extract each citation entry and append to the appropriate STATE.md > Citations Accumulated table:
   - `software` type --> Software & Tools table
   - `method` type --> Methodological References table
   Deduplicate: if a citation with the same Library/Method name already exists in STATE.md, skip it (first occurrence wins). Include the rationale, stage number, and script filename.
4. **Next:** When every script in the wave has its review recorded, dispatch the next wave, or check the stage gate after the last wave

### Gate Criteria (G10)

- [ ] **QA Findings Summary written to STATE.md** (populate the `## QA Findings Summary` section with aggregated results: QA Checkpoint Summary table, BLOCKERs Resolved, WARNINGs Logged, Unresolved Issues)
- [ ] **QA Summary Report generated** (aggregates all Stages 5-8 findings)
- [ ] **All BLOCKERs resolved** (during Stages 5-8: through revision, or by the user's decision for a methodology BLOCKER)
- [ ] **All WARNINGs documented** (with assessment of impact)
- [ ] **No missing QA reviews** (every Stage 5-8 script has a corresponding code-reviewer invocation)
- [ ] **If unresolved issues found:** STOP, escalate
- [ ] **PSU4 presented to user with analysis results and QA summary**
- [ ] **User confirmed PSU4**

---

### Phase Status Update 4 (PSU4): Analysis Complete

**Trigger:** Every G10 item above the two PSU4 items is checked (QA aggregation complete, BLOCKERs resolved)
**Blocking:** YES — Stage 11 CANNOT begin until user confirms PSU4
**Header shown to the user:** `**Checkpoint: Analysis Complete**`

**Actions:**
1. Compile analysis summary from Stages 7-8 and QA aggregation from Stage 10
2. Reference key visualizations by file path for user inspection
3. Present PSU4 to user using the PSU template (`full-pipeline-mode.md` § Phase Status Updates (Mandatory))
4. WAIT for explicit user confirmation

**PSU4 Content Requirements** (this is the one list for PSU4; every item lands in text the user reads, so word it per the Plain-Language Rule in `SKILL.md` § User-Facing Communication Standards):
- Transformation summary: joins performed, derived variables created, final analysis dataset shape
- EDA highlights: key distributions, notable patterns, surprising findings
- Statistical analysis results: key findings with effect sizes and confidence intervals where applicable
- Visualization inventory: file paths to all generated figures (so user can inspect them)
- Quality review summary: every note for your awareness from the quality reviews of all scripts, with its status, each explained in plain words (the Stage 10 aggregation of the QA1-QA4b results; no QA codes or severity labels in the user's text)
- Any deviations from Plan.md methodology (with rationale)
- Notebook status: the notebook's path, that it opens and runs, that every final script is in it with its execution record, and that each archived script matches its original file (internally, Python: the `marimo check` gate passed, `marimo export html` ran every cell, and the Step 6c fidelity check passed all four conditions; R: `quarto render` validated assembly and enabled previews)
- Research Outcomes progress: which can be evaluated, preliminary assessment

**User Response Handling:**
- **Approve** → Proceed to Stage 11 (Report Generation)
- **Request additional analysis** → Return to Stage 8 for supplementary work
- **Request re-transformation** → Return to Stage 7 with revised approach
- **Flag concern about findings** → Orchestrator investigates and reports back
- **Ask questions** → Answer, then re-present approval request

#### PSU4 Checkpoint Purpose

Include in the "Why this checkpoint" field:
> "This is your chance to review all results and the quality review summary before they're synthesized into the final report."

#### PSU4 Phase Transition Bridge

Include in the "What Comes Next" field:
> "All analysis is complete and quality-reviewed. I'll now compile everything into a final report and run an independent verification pass to make sure the report accurately reflects the data and methodology."

#### PSU4 Feedback Guidance

Include in the "What's Most Useful From You Here" field:
> "Do the results make sense substantively? Are there additional analyses or visualizations you'd like to see? Any results that seem surprising and worth investigating further?"

---

## Verification Checklists

Apply the relevant checklist after each subagent returns findings for the corresponding stage.

### Stage 7 (Transformation) Verification

- [ ] Pre-state and post-state both documented
- [ ] Row change percentage calculated
- [ ] Invariants checked with PASS/FAIL status
- [ ] Overall status: PASSED/WARNING/FAILED (log verdict `PASSED WITH WARNINGS` maps to WARNING; count line shows 0 not verified)
- [ ] If FAILED: Issue description and proposed fix present
- [ ] For joins: Cardinality validation performed

### Stage 8.1 (Statistical Analysis) Verification

- [ ] Statistical method appropriate for data type and research question
- [ ] Assumptions validated before analysis (documented in script)
- [ ] Results saved to `output/analysis/` as parquet
- [ ] Key findings documented with effect sizes and confidence intervals
- [ ] Interpretation aligned with Research Outcomes in Plan.md
- [ ] CP4 status stated (PASSED/WARNING/FAILED; log verdict `PASSED WITH WARNINGS` maps to WARNING) with its count line, showing 0 not verified

### Stage 8.2 (Visualization) Verification

- [ ] All Plan.md-specified figures generated
- [ ] Figures saved to `output/figures/`: static figures as PNG, interactive figures as HTML (each with a static PNG version where the report or a visual check needs one)
- [ ] Proper labeling (title, axes, legend, source note)
- [ ] Data source in visualization matches analysis dataset
- [ ] Colorblind-safe palette used
- [ ] Visual inspection performed via **Read tool** on generated PNG files
- [ ] CP4 status stated (PASSED/WARNING/FAILED; log verdict `PASSED WITH WARNINGS` maps to WARNING) with its count line, showing 0 not verified

---

## Error Recovery

For decision trees, retry logic, and escalation procedures for errors encountered during analysis stages, see `agent_reference/ERROR_RECOVERY.md`.
