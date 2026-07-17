# Workflow Reference: Phase 4 — Analysis & Notebook Development

Stages 7, 8, 9, 10. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md`.

**Execution Model:** All scripts follow the file-first execution pattern. See `SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

> **Async dispatch note.** This phase is deliberately serial: one transformation, analysis, or visualization script per subagent invocation, each followed by its mandatory code-reviewer QA before the next begins (the "NEVER batch" rule below is load-bearing). Under async dispatch, each research-executor and code-reviewer returns via a completion notification rather than a synchronous tool return. Do not begin the next script, approve the next transformation, or evaluate a stage gate until the current dispatch's return has arrived and been fully processed. Should multiple visualization scripts (Stage 8.2) ever be dispatched together, treat every mid-flight notification as status-only and wait for all wave members to return before proceeding to Stage 9.

---

## Stage 7: EDA & Transformation

**Executor:** Subagent (general-purpose) - ITERATIVE INVOCATION REQUIRED
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
**Purpose:** Execute transformations ONE AT A TIME with validation

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
   - If PASS: Approve next transformation
   - If FAIL: Request fix (max 2 attempts) or STOP

5. **>>> INVOKE code-reviewer (MANDATORY, after EACH script) <<<**
   - Orchestrator MUST invoke code-reviewer after EACH transformation script
   - Do NOT batch multiple transformations before QA
   - Pass: script path, output files, Plan.md + Plan_Tasks.md locations
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed to next transformation
   - If PASSED: proceed to next transformation

6. **Repeat** for transformation #{n+1}

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

# PRE-STATE CAPTURE
df = pl.read_parquet("data/processed/2026-01-31_clean.parquet")
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
row_loss_pct = 1 - (post_shape[0] / pre_shape[0])
invariant_passed = row_loss_pct < 0.9  # <90% row loss

if invariant_passed:
    print("CP3 STATUS: PASSED")
    df_transformed.write_parquet("data/processed/2026-01-31_analysis.parquet")
else:
    print(f"CP3 STATUS: FAILED - Row loss {row_loss_pct:.1%}")

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

# --- Load ---
# PRE-STATE CAPTURE
df <- read_parquet("data/processed/2026-01-31_clean.parquet")
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
row_loss_pct <- 1 - (post_shape[1] / pre_shape[1])
invariant_passed <- row_loss_pct < 0.9  # <90% row loss

if (invariant_passed) {
  cat("CP3 STATUS: PASSED\n")
  write_parquet(df_transformed, "data/processed/2026-01-31_analysis.parquet")
} else {
  cat(sprintf("CP3 STATUS: FAILED - Row loss %.1f%%\n", row_loss_pct * 100))
}

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

# CP3 Status
cp3_status = "PASSED" | "WARNING" | "FAILED"
```

> **R projects:** implement the same report with `cat()` for the change summary, a `data.frame`/`tibble` for the transformation summary table, `sapply()`/`dplyr::summarise()` for per-column null deltas, and `stopifnot()`-backed status assignment. The checks and the PASSED/WARNING/FAILED contract are identical.

### Invocation Template: data-scientist + polars (Python) or tidyverse (R)

**Purpose:** Apply rigorous methodology to analysis
**Stage:** 7 (EDA & Transformation)
**Subagent:** general-purpose

```python
# ITERATIVE INVOCATION PATTERN (Required for Stage 7)
# Execute transformations ONE AT A TIME, not all at once

# Step 1: Initial EDA (no transformations yet)
Agent({
    description: "Stage 7.1: Initial EDA",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**DATA LOCATION:** data/processed/{processed_data_filename}

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

# Step 2: Execute transformations iteratively (one at a time, atomically)
# Orchestrator provides specific transformation from Plan_Tasks.md task sequence
# CRITICAL: Include prior transformation context for continuity

Agent({
    description: "Stage 7.2: Execute Transformation #{n}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

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

### Polars (Python) / Tidyverse (R) Skill

**Purpose:** DataFrame operations
**Stage:** 7 (EDA & Transformation)
**Subagent:** general-purpose

Typically invoked alongside `data-scientist` skill. Use for specific Polars/tidyverse syntax questions or complex operations.

```python
Agent({
    description: "DataFrame Operation: {operation_name}",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'polars' (Python) or 'tidyverse' (R).

**OPERATION NEEDED:**
{description_of_operation}

**INPUT DATA:**
- Location: {data_path}
- Columns involved: {columns}

**EXPECTED RESULT:**
{expected_outcome}

Return the code to accomplish this, with validation.""",
    subagent_type: "general-purpose"
})
```

### QA Follow-Up (MANDATORY)

**After research-executor returns from EACH Stage 7 transformation, orchestrator MUST invoke code-reviewer.**
Use the **code-reviewer invocation template** from `full-pipeline-mode.md`
with stage-specific values for Stage 7.

**Do NOT proceed to transformation #{n+1} until QA returns PASSED or WARNING.**

```python
# Step 3: Repeat Step 2 AND QA for each transformation in sequence
# Orchestrator increments {n} and provides next transformation
# QA is REQUIRED after EACH transformation, not just at the end

# Step 4: Final CP3 Validation (after all transformations complete)
Agent({
    description: "Stage 7.3: Final CP3 Validation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**TASK:** Perform final CP3 validation after all transformations complete.

**DATA LOCATIONS:**
- Original: data/processed/{original_filename}
- Transformed: data/processed/{transformed_filename}

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

**CP3 Status:** PASSED | FAILED | WARNING

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
- [ ] **QA review completed IMMEDIATELY AFTER THIS SCRIPT, before the next script begins** (code-reviewer separately invoked per script, not batched)
- [ ] **QA status:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
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

**Executor:** Subagent (general-purpose) — ITERATIVE INVOCATION REQUIRED
**Skills:** `data-scientist`, `polars` (Python) or `tidyverse` (R), modeling library per Plan — Python: `statsmodels` / `pyfixest` / `linearmodels` / `svy` / `geopandas` / `scikit-learn` / `igraph`; R: `r-stats` / `fixest` / `plm` / `survey-r` / `sf-terra` / `tidymodels` / `igraph-r` (Stage 8.1), `great-tables` (Python) or `gt` (R) (if formatted tables needed), `plotnine` (Python) or `ggplot2` (R), `plotly` (Python) or `plotly-r` (R), `geopandas` (Python) or `sf-terra` (R) (if map viz), `igraph` (Python) or `igraph-r` (R) (if network viz) (Stage 8.2)
**Purpose:** Conduct final statistical analyses on the analysis dataset AND generate visualizations specified in Plan

### Execution Pattern

**Stage 8 is split into 2 sub-stages, executed sequentially:**

```
Stage 8.1.x: Statistical Analysis (one script per analysis task)
    ↓  QA4a after each script
Stage 8.2.x: Visualization (one script per visualization task)
    ↓  QA4b after each script
```

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
   - After EACH analysis script, orchestrator MUST invoke code-reviewer
   - QA4a validates: statistical methodology, assumption checks, result plausibility
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to next analysis task or Stage 8.2

#### Invocation Template

**Purpose:** Run statistical analyses (regression, hypothesis tests, model fitting)
**Stage:** 8.1 (Statistical Analysis)
**Subagent:** general-purpose
**Skills:** `data-scientist`, `polars` (Python) or `tidyverse` (R), modeling library per Plan — Python: `statsmodels` / `pyfixest` / `linearmodels` / `svy` / `geopandas` / `scikit-learn` / `igraph`; R: `r-stats` / `fixest` / `plm` / `survey-r` / `sf-terra` / `tidymodels` / `igraph-r`

```python
# ITERATIVE INVOCATION PATTERN (Required for Stage 8.1)
# Execute each analysis task ONE AT A TIME, not all at once

Agent({
    description: "Stage 8.1: Statistical Analysis - {analysis_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'polars' (Python) or 'tidyverse' (R).
Call the skill tool with name '{modeling_library}' — Python options: statsmodels, pyfixest, linearmodels, svy, geopandas, scikit-learn, igraph; R options: r-stats, fixest, plm, survey-r, sf-terra, tidymodels, igraph-r — as specified in the <skill> element of Plan_Tasks.md for this task. For spatial regression tasks, geopandas (Python) or sf-terra (R) IS the modeling library. For network/graph analysis tasks, igraph (Python) or igraph-r (R) IS the modeling library. For complex survey data, svy (Python) or survey-r (R) IS the modeling library (design-based inference with Taylor/BRR/jackknife variance).
If formatted tables are needed: "Load `great-tables` skill (Python) or `gt` skill (R) for publication-quality table formatting."
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**IMPORTANT:** This is script-based execution, NOT marimo/Quarto. Write analysis to script files (.py or .R) following `{BASE_DIR}/agent_reference/SCRIPT_EXECUTION_REFERENCE.md`.

**DATA LOCATION:** data/processed/{analysis_data_filename}

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
- Statistical results: output/analysis/{date_prefix}_{analysis_name}.parquet
- Summary tables: output/analysis/{date_prefix}_{analysis_name}_summary.parquet
- Figures (if produced): output/figures/{date_prefix}_{analysis_name}_{plot_type}.png

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

**Do NOT proceed to the next analysis task until QA4a returns PASSED or WARNING.**

### Stage 8.2: Visualization

**Purpose:** Create visualizations specified in Plan, informed by Stage 8.1 results

**Input:** Analysis dataset from Stage 7 + statistical results from Stage 8.1
**Output:** Figures saved to `output/figures/`

#### Actions

1. **Create exploratory plots** — Distributions, relationships, patterns
2. **Create final visualizations** — As specified in Plan.md and Plan_Tasks.md, striving for publication-quality
3. **Export figures** — PNG format, appropriate dimensions, to `output/figures/`
4. **>>> INVOKE code-reviewer (MANDATORY, QA4b) <<<**
   - After EACH visualization script, orchestrator MUST invoke code-reviewer
   - QA4b validates: figure existence, data source accuracy, labeling, visual clarity
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to next visualization task or Stage 9

#### Invocation Template: plotnine (Python) or ggplot2 (R)

**Purpose:** Static visualizations (grammar of graphics)
**Stage:** 8.2 (Visualization)
**Subagent:** general-purpose
**Skills:** `data-scientist`, `plotnine` (Python) or `ggplot2` (R)

```python
Agent({
    description: "Stage 8.2: Visualization - Static Plots",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'plotnine' (Python) or 'ggplot2' (R).
If formatted summary tables are needed: "Load `great-tables` skill (Python) or `gt` skill (R) for publication-quality table formatting."
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**VISUALIZATION SPECIFICATION (from Plan.md):**
{visualization_requirements}

**DATA LOCATION:** data/processed/{analysis_data_filename}

**OUTPUT LOCATION:** output/figures/

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

**Purpose:** Interactive visualizations
**Stage:** 8.2 (Visualization)
**Subagent:** general-purpose
**Skills:** `data-scientist`, `plotly` (Python) or `plotly-r` (R)

```python
Agent({
    description: "Stage 8.2: Visualization - Interactive Plots",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'plotly' (Python) or 'plotly-r' (R).
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**VISUALIZATION SPECIFICATION (from Plan.md):**
{visualization_requirements}

**DATA LOCATION:** data/processed/{analysis_data_filename}

**OUTPUT LOCATION:** output/figures/

**REQUIRED PLOTS:**
1. {plot_description} → {date_prefix}_{plot_name}.html (interactive)
   Also export: {date_prefix}_{plot_name}.png (static)

**INTERACTIVITY REQUIREMENTS:**
- Hover information: {hover_fields}
- Selection: {selection_type}

**VISUAL INSPECTION:** After successful execution, use the **Read tool** to view each generated PNG file. Verify layout, labels, legend readability, and data representation before reporting.

Return the plotting code and confirm files are saved.""",
    subagent_type: "research-executor"
})
```

#### Invocation Template: geopandas (Python) or sf-terra (R) (Map Visualization)

**Purpose:** Choropleth maps, spatial plots, dot-density maps
**Stage:** 8.2 (Map Visualization)
**Subagent:** general-purpose
**Skills:** `data-scientist`, `geopandas` (Python) or `sf-terra` (R)

```python
Agent({
    description: "[3-5 word summary]",
    subagent_type: "research-executor",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name 'geopandas' (Python) or 'sf-terra' (R).
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

## CONTEXT FROM PLAN
[Paste relevant Plan.md methodology sections and Plan_Tasks.md task blocks]

Research Question: {research_question}
Current Stage: 8.2

## TASK
**Script Target:** {BASE_DIR}/research/{project_folder}/scripts/stage8_analysis/{step:02d}_{task-name}.py (.py for Python, .R for R)
**Map Type:** {map_type} (e.g., choropleth, dot-density, proportional symbol, bivariate)
**Geographic Unit:** {geographic_unit} (e.g., county, state, school district, tract)
**Variable(s) to Map:** {variables}
**Classification Scheme:** {scheme} (e.g., quantiles, natural breaks, equal interval)
**Output:** {BASE_DIR}/research/{project_folder}/output/figures/{date}_{description}.png
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

**Do NOT proceed to Stage 9 until QA4b returns PASSED or WARNING for all visualization scripts.**

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

**Static — Python (plotnine):**
```python
from plotnine import ggplot, aes, geom_point, theme_minimal

plot = (
    ggplot(df, aes(x='var1', y='var2'))
    + geom_point()
    + theme_minimal()
)
plot.save(f"output/figures/{date_prefix}_plot_name.png", dpi=300)
```

**Static — R (ggplot2):**
```r
library(ggplot2)

p <- ggplot(df, aes(x = var1, y = var2)) +
  geom_point() +
  theme_minimal()
ggsave(sprintf("output/figures/%s_plot_name.png", date_prefix), p, dpi = 300)
```

**Interactive — Python (plotly):**
```python
import plotly.express as px

fig = px.scatter(df, x='var1', y='var2', color='category')
fig.write_html(f"output/figures/{date_prefix}_plot_name.html")
# Note: kaleido/write_image is not available in DAAF — use plotnine for static PNG export
```

**Interactive — R (plotly):**
```r
library(plotly)

fig <- plot_ly(df, x = ~var1, y = ~var2, color = ~category, type = "scatter", mode = "markers")
htmlwidgets::saveWidget(fig, sprintf("output/figures/%s_plot_name.html", date_prefix))
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
- [ ] QA4a completed for EACH analysis script individually (PASSED/WARNING), invoked immediately after each script
- [ ] QA4b completed for EACH visualization script individually (PASSED/WARNING), invoked immediately after each script

### Gate Criteria (G8)

- [ ] All planned analyses and visualizations created
- [ ] Statistical results exported to `output/analysis/`
- [ ] Figures exported to `output/figures/`
- [ ] **All scripts saved to `scripts/stage8_analysis/`** with standard header
- [ ] **QA4a review completed for EACH analysis script** (code-reviewer separately invoked IMMEDIATELY AFTER each individual script, before the next script begins — not batched)
- [ ] **All QA4a statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA4b review completed for EACH visualization script** (code-reviewer separately invoked IMMEDIATELY AFTER each individual script, before the next script begins — not batched)
- [ ] **All QA4b statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage8_{step}_cra1.py`** (analysis) and **`stage8_{step}_crb1.py`** (viz) (`.R` for R projects)
- [ ] **STATE.md updated:** Current Stage: 8, QA4a and QA4b status, analysis result paths, figure paths recorded

### Multi-Skill Invocation Templates

#### Combined EDA + Transformation (Stage 7)

When EDA and transformation are closely linked:

```python
Agent({
    description: "Stage 7: EDA & Transformation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'polars' (Python) or 'tidyverse' (R).
If this task involves spatial operations (spatial join, point-in-polygon, buffer, geocoding, or working with geometry columns): also call the skill tool with name 'geopandas' (Python) or 'sf-terra' (R).
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**DATA LOCATION:** data/processed/{filename}

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

Call the skill tool with name 'plotnine' (Python) or 'ggplot2' (R) for static publication plots.
Call the skill tool with name 'plotly' (Python) or 'plotly-r' (R) for interactive exploration plots.
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**DATA LOCATION:** data/processed/{filename}

**STATIC PLOTS (plotnine):**
{static_plot_specs}

**INTERACTIVE PLOTS (plotly):**
{interactive_plot_specs}

**OUTPUT:** output/figures/

Return all plotting code and confirm files saved.""",
    subagent_type: "research-executor"
})
```

---

## Stage 9: Script Compilation (NOT Dashboard Building)

**Agent:** `notebook-assembler` (see `.claude/agents/notebook-assembler.md`)
**Executor:** Subagent (general-purpose)
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
- **Marimo/Python** — Three contiguous archive cells per script (header, comment-prefixed source ending with `pass`, and immediately adjacent `mo.accordion()` log); an optional post-bundle display may use `pl.read_parquet()` + `mo.ui.table()` or show an existing figure with `mo.image()`
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

Also call the skill tool with name 'marimo' (Python) or 'quarto' (R) for basic notebook syntax.

## CRITICAL: YOU ARE A COMPILER, NOT AN ANALYST

Your job is to:
1. READ each script file from `scripts/`
2. For Python, COPY code into the source cell of a canonical three-cell Marimo archive bundle; for R, COPY code literally and un-commented into a Quarto archive chunk with `#| code-fold: false`, `#| eval: false`, and the exact `# --- VERBATIM COPY of scripts/<path> ---` marker
3. COPY the execution log VERBATIM into a collapsed Marimo accordion or the immediately following collapsed Quarto callout titled `Execution Log`
4. OPTIONALLY ADD ONLY the format-specific display: `pl.read_parquet()` + `mo.ui.table()` or an existing-figure `mo.image()` (Python); for R, the canonical `arrow::read_parquet()` + `dplyr::glimpse(df)` + `head(df, 20)` preview or an existing saved figure (Markdown image preferred; a dedicated `knitr::include_graphics()` chunk is allowed only with `#| eval: true`, `#| echo: false`, and no other R statements)

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
3. **Immediately adjacent execution-log cell:** VERBATIM log in a collapsed `mo.accordion()`

After the complete three-cell bundle, an **optional inspection/display cell** may contain only:
    ```python
    df = pl.read_parquet("path/to/output.parquet")
    mo.ui.table(df.head(100))
    ```
    For an existing saved figure, use `mo.image()` instead of creating a plot.

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

The Marimo Cell 3 accordion should contain EXACTLY:
```
# EXECUTION LOG
# Executed: 2026-01-24
# STDOUT: Hello
```

## OUTPUT

**Notebook file:** {date_prefix}_{title}.py (Python/Marimo) or {date_prefix}_{title}.qmd (R/Quarto)

## VERIFICATION BEFORE RETURNING

For Marimo, confirm every script has one complete three-cell header/source/log archive bundle, any optional display follows that bundle, and no archived Python code is live. For Quarto, confirm every script has one heading, one literal archive chunk with both eval guards plus `code-fold: false` and the exact marker, and the immediately following Execution Log callout. Then reject any of these in newly authored notebook scaffolding:
- Marimo UI inputs or R/Shiny/htmlwidgets inputs
- group-by/summarise operations outside archived script code
- pivots outside archived script code
- filters in optional inspection code
- `with_columns` / `mutate` in optional inspection code
- newly generated visualizations

The ONLY acceptable optional new code is `pl.read_parquet()` + `mo.ui.table()` / existing-figure display (Python), or `arrow::read_parquet()` + `dplyr::glimpse(df)` + `head(df, 20)` / existing-figure display (R).""",
    subagent_type: "notebook-assembler"
})
```

### Gate Criteria (G9)

- [ ] All final successful script versions identified; prior versions documented
- [ ] **Marimo:** every script has a complete three-cell header/source/log archive bundle; archived Python is comment-prefixed with trailing `pass`; any optional display follows the bundle; `marimo run` completes without errors
- [ ] **Quarto:** every script uses heading + literal archive chunk + immediately following Execution Log callout + optional inspection; archive chunks include `#| code-fold: false`, per-chunk `#| eval: false`, and the exact decompiler marker; canonical rich YAML includes global `execute: eval: false`
- [ ] **Quarto render:** `quarto render` completes with only explicitly enabled optional previews evaluated; archived Stage 5-8 scripts are not re-run, and render success is not represented as full analysis reproduction
- [ ] Navigation is format-appropriate (Marimo navigation/TOC cells; Quarto YAML TOC and Markdown headings)
- [ ] Optional data and figure displays resolve existing artifacts without transformation or new visualization
- [ ] Every final script has a real, non-placeholder execution log displayed verbatim in a collapsed Marimo accordion or immediately following collapsed Quarto callout

---

## Stage 10: QA Aggregation

**Executor:** Orchestrator (no subagent — performed directly by orchestrator)
**Skills:** —
**Purpose:** Aggregation point for all QA findings from Stages 5-8

### Actions

1. **Aggregate Continuous QA Findings**
   - Collect all WARNING items logged during Stages 5-8
   - Collect all INFO items logged during Stages 5-8
   - Review for patterns across multiple scripts
   - Document BLOCKER issues that were resolved (and how)

2. **Generate QA Summary Report**
   ```markdown
   ## QA Summary Report

   ### Execution Overview
   | Stage | Scripts | QA Reviews | BLOCKERs Found | BLOCKERs Resolved |
   |-------|---------|------------|----------------|-------------------|
   | 5     | 2       | 2          | 0              | N/A               |
   | 6     | 2       | 2          | 0              | N/A               |
   | 7     | 3       | 3          | 2              | 2 (via revision)  |
   | 8 (QA4a) | 1    | 1          | 0              | N/A               |
   | 8 (QA4b) | 1    | 1          | 0              | N/A               |

   ### Resolved BLOCKERs
   | Script | Issue | Resolution | Revision Count |
   |--------|-------|------------|----------------|
   | 01_join-data.py | Fan-out join | Fixed key uniqueness | 2 |

   ### Outstanding WARNINGs
   | Script | Warning | Assessment |
   |--------|---------|------------|
   | 01_clean-ccd.py | 38% suppression | Acceptable, documented |

   ### INFO Items
   | Script | Observation |
   |--------|-------------|
   | 01_fetch-ccd.py | Could parallelize data access calls |
   ```

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
4. **Next:** Proceed to next script in wave, or check gate if wave complete

### Gate Criteria (G10)

- [ ] **QA Findings Summary written to STATE.md** (populate the `## QA Findings Summary` section with aggregated results: QA Checkpoint Summary table, BLOCKERs Resolved, WARNINGs Logged, Unresolved Issues)
- [ ] **QA Summary Report generated** (aggregates all Stages 5-8 findings)
- [ ] **All BLOCKERs resolved** (via revision during Stages 5-8)
- [ ] **All WARNINGs documented** (with assessment of impact)
- [ ] **No missing QA reviews** (every Stage 5-8 script has a corresponding code-reviewer invocation)
- [ ] **If unresolved issues found:** STOP, escalate
- [ ] **PSU4 presented to user with analysis results and QA summary**
- [ ] **User confirmed PSU4**

---

### Phase Status Update 4 (PSU4): Analysis Complete

**Trigger:** Gate G10 satisfied (QA aggregation complete, BLOCKERs resolved)
**Blocking:** YES — Stage 11 CANNOT begin until user confirms PSU4

**Actions:**
1. Compile analysis summary from Stages 7-8 and QA aggregation from Stage 10
2. Reference key visualizations by file path for user inspection
3. Present PSU4 to user using the PSU template
4. WAIT for explicit user confirmation

**PSU4 Content Requirements:**
- Transformation summary: joins performed, derived variables created, final analysis dataset shape
- EDA highlights: key distributions, notable patterns, surprising findings
- Statistical analysis results: key findings with effect sizes and confidence intervals where applicable
- Visualization inventory: file paths to all generated figures (so user can inspect them)
- QA aggregation summary: all accumulated WARNINGs from Stages 5-8, with resolution status
- Any deviations from Plan.md methodology (with rationale)
- Notebook compilation status (Stage 9): `marimo run` succeeded for Python or `quarto render` validated R/Quarto assembly and enabled previews; all scripts represented
- Research Outcomes progress: which can be evaluated, preliminary assessment

**User Response Handling:**
- **Approve** → Proceed to Stage 11 (Report Generation)
- **Request additional analysis** → Return to Stage 8 for supplementary work
- **Request re-transformation** → Return to Stage 7 with revised approach
- **Flag concern about findings** → Orchestrator investigates and reports back
- **Ask questions** → Answer, then re-present approval request

---

## Phase Status Update 4 (PSU4): Analysis Complete

After Stage 10 (QA Aggregation — performed by the orchestrator), present PSU4 to the user. Use the generic PSU template from `full-pipeline-mode.md` with the content below.

### PSU4 Checkpoint Purpose

Include in the "Why this checkpoint" field:
> "This is your chance to review all results and the quality review summary before they're synthesized into the final report."

### PSU4 Phase Transition Bridge

Include in the "What Comes Next" field:
> "All analysis is complete and quality-reviewed. I'll now compile everything into a final report and run an independent verification pass to make sure the report accurately reflects the data and methodology."

### PSU4 Feedback Guidance

Include in the "What's Most Useful From You Here" field:
> "Do the results make sense substantively? Are there additional analyses or visualizations you'd like to see? Any results that seem surprising and worth investigating further?"

### PSU4 Content Requirements

The PSU4 checkpoint MUST include:
- Transformation summary: joins performed, derived variables, final analysis dataset shape
- Statistical analysis results: key findings with effect sizes and confidence intervals
- Key visualizations produced (reference file paths for user to inspect)
- QA summary: QA3/QA4a/QA4b results across all scripts
- Accumulated warnings from Stages 5-8 (the Stage 10 QA aggregation)
- Any deviations from Plan.md methodology
- Notebook compilation status

---

## Verification Checklists

Apply the relevant checklist after each subagent returns findings for the corresponding stage.

### Stage 7 (Transformation) Verification

- [ ] Pre-state and post-state both documented
- [ ] Row change percentage calculated
- [ ] Invariants checked with PASS/FAIL status
- [ ] Overall status: PASSED/FAILED/WARNING
- [ ] If FAILED: Issue description and proposed fix present
- [ ] For joins: Cardinality validation performed

### Stage 8.1 (Statistical Analysis) Verification

- [ ] Statistical method appropriate for data type and research question
- [ ] Assumptions validated before analysis (documented in script)
- [ ] Results saved to `output/analysis/` as parquet
- [ ] Key findings documented with effect sizes and confidence intervals
- [ ] Interpretation aligned with Research Outcomes in Plan.md
- [ ] Overall status: PASSED/FAILED/WARNING

### Stage 8.2 (Visualization) Verification

- [ ] All Plan.md-specified figures generated
- [ ] Figures saved to `output/figures/` as PNG
- [ ] Proper labeling (title, axes, legend, source note)
- [ ] Data source in visualization matches analysis dataset
- [ ] Colorblind-safe palette used
- [ ] Visual inspection performed via **Read tool** on generated PNG files
- [ ] Overall status: PASSED/FAILED/WARNING

---

## Error Recovery

For decision trees, retry logic, and escalation procedures for errors encountered during analysis stages, see `agent_reference/ERROR_RECOVERY.md`.
