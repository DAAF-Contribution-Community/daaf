# Workflow Reference: Phase 3 — Data Acquisition & Preparation

Stages 5, 6. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md`.

**Execution Model:** All scripts follow the file-first execution pattern. See `SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

> **Dispatch order and returns.** Same-wave tasks run in parallel, at most 5 in flight: executors first, then one code-reviewer per script once all have returned. Each script is reviewed before any dependent script or the next wave starts. See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive. Treat every mid-wave return as status-only: do not start the next wave, evaluate a stage gate (G5, G6), or present PSU3 until every dispatch in flight has returned and been processed.

---

## Stage 5: Data Retrieval

**Agent:** research-executor
**Skill:** Domain query skill (e.g., `education-data-query`)
**Purpose:** Fetch data from configured data mirrors

**Note:** Dispatch `research-executor`: it writes the data files to `data/raw/` and runs under the `enforce-file-first.sh` hook its frontmatter registers.

### Actions

1. **Construct Query**
   - Build data access URL from Plan.md specification
   - Construct necessary sample filters (year, subgroups, etc.)

2. **Execute Query**
   - Implement timeout handling for mirror downloads
   - Retry on transient errors

3. **Validate Response**
   - Check shape
   - Verify columns
   - Confirm year coverage
   - Confirm subsample specifications

4. **Save Data**
   - Parquet format (for processing)
   - Location: `data/raw/`

5. **>>> INVOKE code-reviewer (MANDATORY) <<<**
   - After research-executor completes, orchestrator MUST invoke code-reviewer
   - Pass: script path, output files, Plan.md + Plan_Tasks.md locations
   - Wait for the QA result before any dependent script or the next wave starts; Stage 6 starts once every Stage 5 script has its result
   - If BLOCKER: A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). Any other BLOCKER (a bug, a stub, a validation gap) corrects a defect without changing the method and also goes through revision; a code-reviewer STOP of another Issue Category routes as `full-pipeline-mode.md` § Gate Status Translation says. A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed

### Thoroughness Directive

```
- Download complete file from mirror
- Validate response shape immediately
- Save ONLY in parquet format
- Document any data access issues encountered
```

### Invocation Template: Domain Query Skill

**Purpose:** Download data from mirrors
**Stage:** 5 (Data Retrieval)
**Agent:** research-executor
**Skills:** `data-scientist`, `{domain_query_skill}`

> **Domain extensibility:** The orchestrator resolves the query skill name based on the active domain (from the Plan's Domain Configuration) and provides it in the Agent prompt. The example below uses `education-data-query` as the demonstration domain default.

```python
Agent({
    description: "Stage 5: Data Retrieval",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage5_fetch/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name '{domain_query_skill}'.  # e.g., 'education-data-query'
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**QUERY SPECIFICATION:**
- Dataset Path: {dataset_path}  (from datasets-reference.md, flat format e.g. "ccd/schools_ccd_directory")
- Years: {years}
- Filters: {filters}
- Variables: {variables}
- Expected Records: ~{expected_count}

**DATA OUTPUT REQUIREMENTS:**
- Save to: {PROJECT_DIR}/data/raw/{date_prefix}_{source}_{description}.parquet

**RISK REGISTER ITEMS FOR THIS TASK:**
| Risk | Likelihood | Impact | Mitigation | Watch For |
|------|------------|--------|------------|-----------|
| {risk_name} | {L/M/H} | {L/M/H} | {specific_action} | {symptom_to_monitor} |

During execution, ACTIVELY MONITOR for watch-for symptoms. Escalate if detected.

**CODED VALUE EXPECTATIONS:**
Retrieved data may include domain-specific coded missing values (per Plan Domain Configuration; e.g., -1, -2, -3 for education).
These will be handled in Stage 6. Report presence in CP1 output.

**MIRROR FETCH PROTOCOL (MANDATORY):**
Use the mirror-based fetch pattern from the education-data-query skill:
1. Try each mirror in priority order (per mirrors.yaml)
2. Build URLs from each mirror's url_template + dataset path parameters
3. Read using mirror's read_strategy; fall through on 404/timeout
4. Apply year/state/other filters locally with Polars (Python) or dplyr/arrow (R)
5. Log which mirror and pinned vintage (revision) were used, and the fetch result

**THOROUGHNESS DIRECTIVE:**
- Try each mirror in priority order
- Handle mirror failures with fallback
- Validate response shape immediately after fetch
- Document which mirror and vintage were used (the vintage feeds the data citation)
- Verify all requested years are present
- Verify all requested columns are present

**OUTPUT FORMAT:**
Return findings using the Research Executor Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation:**
- File locations (parquet paths in `data/raw/`), mirror and vintage used, and any fallback events
- Row counts, column lists, year coverage, and CP1 status with its count line
- Initial data quality observations (missingness, coded values present)""",
    subagent_type: "research-executor"
})
```

### QA Follow-Up (MANDATORY)

**After research-executor completes EACH individual Stage 5 fetch script, orchestrator MUST invoke code-reviewer to review that script on its own (one code-reviewer per script, never several scripts in one review).**
Use the **code-reviewer invocation template** from `full-pipeline-mode.md`
with stage-specific values for Stage 5.

**Same-wave tasks run in parallel, at most 5 in flight: executors first, then one code-reviewer per script once all have returned. Each script is reviewed before any dependent script or the next wave starts.**
**Do NOT start a dependent script or the next wave until every script in the current wave has QA PASSED or WARNING.**
**Do NOT proceed to Stage 6 until ALL Stage 5 scripts have been individually QA'd.**

### Validation (CP1)

Each fetch script embeds the CP1 block from `agent_reference/VALIDATION_CHECKPOINTS.md` § CP1: Post-Fetch Validation (Python and R templates), configured from the Plan (expected rows, required columns, expected years, `FLAG_YEARS`). It prints one outcome line per check, the `Checks:` count line and the `CP1 VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED` verdict, and halts the script on FAILED. FAILED: an empty fetch, a missing required column, a required column more than 90% null, or any check that could not run (`not verified`). WARNING: expected years missing, a data lag, or flagged years present. A check is skipped only through its `not_applicable` entry with a written reason.

### Output Format

```markdown
### Fetch Summary:
- Mirror and vintage: [mirror used; pinned revision or source version]
- Records retrieved: [count]
- Columns: [list]
- Years present: [list]
- Data access issues: [any problems]

### Initial Validation (CP1):
- Shape: [rows x cols]
- Missing values: [summary]
- Unexpected values: [any anomalies]
- **CP1 Status:** [PASSED | WARNING | FAILED] (log verdict `PASSED WITH WARNINGS` maps to WARNING)
- **Checks:** [the CP1 count line, quoted]

### File Locations:
- Parquet: `data/raw/YYYY-MM-DD_[source]_[description].parquet`

### Scripts Saved (one per fetch task):
- Path: `scripts/stage5_fetch/{step}_{task-name}.py` (Python) or `{step}_{task-name}.R` (R)
- Includes: Mirror fallback, CP1 validation, output paths
- Note: Each fetch task produces a separate script; QA is invoked immediately after each
```

### Gate Criteria (G5)

- [ ] Data retrieved successfully
- [ ] CP1 passed (or warnings documented)
- [ ] Data saved to `data/raw/`
- [ ] **All scripts saved to `scripts/stage5_fetch/`** (one per fetch task) with standard header
- [ ] **If data lag ≥3 years:** User notified and decision documented
- [ ] STATE.md § Data Status updated with the data-freshness findings: one Data Lag line per source (latest year available; years requested but missing); a lag also gets a Runtime Risks row
- [ ] **QA review completed for EACH Stage 5 script** (one code-reviewer per script, before any dependent script or the next wave; not batched)
- [ ] **All QA1 statuses:** PASSED/WARNING (any BLOCKER handled before any dependent script or the next wave: a methodology BLOCKER, raised as a `Methodology Conflict` STOP, escalated to the user; any other BLOCKER resolved through revision)
- [ ] **QA scripts saved to `scripts/cr/stage5_{step}_cr1.py`** (`.R` for R projects) (+ cr2..cr5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 5, CP1 status, raw data paths recorded

---

## Stage 6: Context Application

**Agent:** research-executor
**Skill:** Domain context skill (e.g., `education-data-context`)
**Purpose:** Apply source-specific cleaning and context

**Note:** Dispatch `research-executor`: it writes the cleaned data files to `data/processed/` and runs under the `enforce-file-first.sh` hook its frontmatter registers.

### Actions

1. **Apply Coded Value Filters**
   - Filter the coded values listed in Plan Domain Configuration (education default: -1 missing, -2 not applicable, -3 suppressed)
   - Document rows removed

2. **Calculate Quality Metrics**
   - Suppression rate
   - Missing value rates
   - Data completeness

3. **Validate Analysis Type**
   - Check the governance rules in Plan Domain Configuration (education: no cross-state assessment comparisons)
   - Verify methodology is valid for source

4. **Generate Citation**
   - Full citation text
   - Data vintage
   - Access date

5. **Save Clean Data**
   - Parquet format
   - Location: `data/processed/`

6. **>>> INVOKE code-reviewer (MANDATORY) <<<**
   - After research-executor completes, orchestrator MUST invoke code-reviewer
   - Pass: script path, output files, Plan.md + Plan_Tasks.md locations
   - Wait for the QA result before any dependent script or the next wave starts; Stage 7 starts once every Stage 6 script has its result
   - If BLOCKER: A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). Any other BLOCKER (a bug, a stub, a validation gap) corrects a defect without changing the method and also goes through revision; a code-reviewer STOP of another Issue Category routes as `full-pipeline-mode.md` § Gate Status Translation says. A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed

### Thoroughness Directive

```
- Apply coded value filters as specified in Plan.md
- Calculate suppression rates for key variables
- BLOCK if any governance rules from Plan Domain Configuration are violated (e.g., cross-state assessment comparison for education)
- BLOCK if suppression rate >50%
- Generate proper citation text
```

### Invocation Template: Domain Context Skill

**Purpose:** Apply source-specific cleaning and generate citations
**Stage:** 6 (Context Application)
**Agent:** research-executor
**Skills:** `data-scientist`, `{domain_context_skill}`

> **Domain extensibility:** The orchestrator resolves the context skill name based on the active domain (from the Plan's Domain Configuration) and provides it in the Agent prompt. The example below uses `education-data-context` as the demonstration domain default.

```python
Agent({
    description: "Stage 6: Context Application",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**PROJECT_DIR:** {PROJECT_DIR} (absolute project path; build every data and output path in the script from it)

**SCRIPT TARGET:** {PROJECT_DIR}/scripts/stage6_clean/{step}_{task-name}.py (.R for R)
**PLAN:** {plan_path} (absolute; or inline the relevant Plan.md sections below)

**RESEARCH QUESTION (verbatim):**
{research_question}

Call the skill tool with name '{domain_context_skill}'.  # e.g., 'education-data-context'
If user has R/Stata background, also include: "User has [R/Stata] background. Load [r-python-translation/stata-python-translation] skill. Add inline [R/Stata]-equivalent comments for non-trivial data operations."
When execution language is R and user has Python/Stata background, instead include: "User has [Python/Stata] background. Load [python-r-translation/stata-r-translation] skill. Add inline [Python/Stata]-equivalent comments for non-trivial data operations."

**DATA SOURCE:** {source_name}

**RAW DATA LOCATION:** {PROJECT_DIR}/data/raw/{raw_data_filename}

**CAVEATS FROM STAGE 3:**
{source_caveats}

**CODED VALUE HANDLING (from Plan.md):**
{coded_value_specification}

**CLEAN DATA OUTPUT:**
- Save to: {PROJECT_DIR}/data/processed/{date_prefix}_{description}.parquet

**RISK REGISTER ITEMS FOR THIS TASK:**
| Risk | Likelihood | Impact | Mitigation | Watch For |
|------|------------|--------|------------|-----------|
| {risk_name} | {L/M/H} | {L/M/H} | {specific_action} | {symptom_to_monitor} |

During execution, ACTIVELY MONITOR for watch-for symptoms. Escalate if detected.

**SUPPRESSION TOLERANCE (from Plan.md):**
- Target suppression rate: <{target}%
- WARNING threshold: {warning_threshold}%
- BLOCKER threshold: {blocker_threshold}%

**THOROUGHNESS DIRECTIVE:**
- Apply ALL coded value filters as specified
- Calculate suppression rate for key variables
- BLOCK if any governance rules from Plan Domain Configuration are violated (e.g., cross-state assessment comparison for education)
- BLOCK if suppression rate exceeds 50%
- Generate complete citation text with access date
- Document all cleaning decisions and row impacts

**OUTPUT FORMAT:**
Return findings using the Research Executor Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation:**
- Cleaning operations applied (coded value filters, row removal counts, suppression rates)
- Data quality metrics (CP2 status with its count line, original vs. clean row counts, loss percentage)
- Citation data (full citation text with access date) and file locations""",
    subagent_type: "research-executor"
})
```

### QA Follow-Up (MANDATORY)

**After research-executor completes EACH individual Stage 6 cleaning script, orchestrator MUST invoke code-reviewer to review that script on its own (one code-reviewer per script, never several scripts in one review).**
Use the **code-reviewer invocation template** from `full-pipeline-mode.md`
with stage-specific values for Stage 6.

**Same-wave tasks run in parallel, at most 5 in flight: executors first, then one code-reviewer per script once all have returned. Each script is reviewed before any dependent script or the next wave starts.**
**Do NOT start a dependent script or the next wave until every script in the current wave has QA PASSED or WARNING.**
**Do NOT proceed to Stage 7 until ALL Stage 6 scripts have been individually QA'd.**

**PSU Note:** Stage 6 concludes Phase 3. After all Stage 6 scripts are executed and QA'd, the orchestrator will present PSU3 to the user. The orchestrator compiles PSU3 from accumulated Stage 5-6 results -- no single agent produces the full PSU3 content.

### Validation (CP2)

Each cleaning script embeds the CP2 block from `agent_reference/VALIDATION_CHECKPOINTS.md` § CP2: Post-Cleaning Validation (Python and R templates), configured from Plan Domain Configuration (`SUPPRESSION_CODE`, `SUPPRESSION_THRESHOLD`, the coded missing values, the key variables). It prints one outcome line per check, the `Checks:` count line and the `CP2 VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED` verdict, and halts the script on FAILED. FAILED: data loss above 90%, a key variable whose suppression rate exceeds the threshold (education default 50%), or any check that could not run (`not verified`). Coded values left in the clean data are a WARNING. A check is skipped only through its `not_applicable` entry with a written reason.

### Output Format

```markdown
### Cleaning Applied:
- Coded values filtered: [summary by code]
- Rows removed: [count] ([percentage]%)

### Data Quality Report (CP2):
- Suppression rate: [percentage]
- Missing value summary: [by variable]
- **CP2 Status:** [PASSED | WARNING | FAILED] (log verdict `PASSED WITH WARNINGS` maps to WARNING)
- **Checks:** [the CP2 count line, quoted]

### Validity Check:
- Analysis type: [description]
- Valid: [Yes | No | Conditional]
- Warnings: [any concerns]

### Citation:
> [Full citation text]

### File Locations:
- Parquet: `data/processed/YYYY-MM-DD_[description].parquet`

### Scripts Saved (one per clean task):
- Path: `scripts/stage6_clean/{step}_{task-name}.py` (Python) or `{step}_{task-name}.R` (R)
- Includes: Coded value filtering, suppression calculation, CP2 validation
- Note: Each clean task produces a separate script; QA is invoked immediately after each
```

### Gate Criteria (G6)

- [ ] Coded values handled
- [ ] CP2 passed
- [ ] Citation generated
- [ ] Data saved to `data/processed/`
- [ ] **All scripts saved to `scripts/stage6_clean/`** (one per clean task) with standard header
- [ ] **QA review completed for EACH Stage 6 script** (one code-reviewer per script, before any dependent script or the next wave; not batched)
- [ ] **All QA2 statuses:** PASSED/WARNING (any BLOCKER handled before any dependent script or the next wave: a methodology BLOCKER, raised as a `Methodology Conflict` STOP, escalated to the user; any other BLOCKER resolved through revision)
- [ ] **QA scripts saved to `scripts/cr/stage6_{step}_cr1.py`** (`.R` for R projects) (+ cr2..cr5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 6, CP2 status, suppression rate, processed data paths
- [ ] **PSU3 presented to user with data quality summary**
- [ ] **User confirmed PSU3**

---

### Phase Status Update 3 (PSU3): Data Acquired and Cleaned

**Trigger:** Every G6 item above the two PSU3 items is checked (all Stage 5-6 scripts executed and QA'd)
**Blocking:** YES — Stage 7 CANNOT begin until user confirms PSU3
**Header shown to the user:** `**Checkpoint: Data Preparation Complete**`

**Actions:**
1. Compile data acquisition and cleaning summary from Stages 5-6
2. Include QA results from all QA1 and QA2 reviews
3. Present PSU3 to user using the PSU template (`full-pipeline-mode.md` § Phase Status Updates (Mandatory))
4. WAIT for explicit user confirmation

**PSU3 Content Requirements** (this is the one list for PSU3; every item lands in text the user reads, so word it per the Plain-Language Rule in `SKILL.md` § User-Facing Communication Standards):
- Datasets acquired: source name, shape (rows x columns), date range, file path
- Data freshness: most recent year available per source
- Data quality per dataset: missingness rates for critical columns, suppression rates
- Cleaning actions taken: rows removed (with counts and percentages), values recoded, filters applied
- Quality review table: one row per script with its result (passed, or passed with notes for your awareness), each note explained in plain words (the QA1 and QA2 results; no QA codes or severity labels in the user's text)
- Any deviations from Plan.md during fetch or clean (documented per RULE 1-3)
- If data lag >= 3 years: explicit flag for user awareness
- If flag years (per FLAG_YEARS in Plan Domain Configuration) are included: explicit flag with documented warning
- Data readiness assessment: are the cleaned datasets ready for analysis?

**User Response Handling:**
- **Approve** → Proceed to Stage 7 (EDA & Transformation)
- **Request re-fetch** → Return to Stage 5 for specific datasets
- **Request different cleaning approach** → Return to Stage 6 with revised parameters
- **Flag concern about data quality** → Orchestrator investigates and reports back
- **Ask questions** → Answer, then re-present approval request

#### PSU3 Checkpoint Purpose

Include in the "Why this checkpoint" field:
> "I'm checking in to confirm the data is clean and trustworthy before running any statistics on it."

#### PSU3 Phase Transition Bridge

Include in the "What Comes Next" field:
> "The data is ready. Now comes the analysis itself — transformations, statistics, and visualizations, all following the plan we agreed on. Each script goes through a quality review. I'll compile all results and come back for one more checkpoint before writing the final report."

#### PSU3 Feedback Guidance

Include in the "What's Most Useful From You Here" field:
> "Are the data quality levels acceptable for your purposes? Any concerns about missing data rates or the cleaning decisions I made?"

### Post-Script Action Checklist (Stages 5-6)

After each script execution:
1. **QA:** Invoke code-reviewer immediately (see `full-pipeline-mode.md` > Code-Reviewer Invocation)
2. **State:** Update STATE.md transformation progress table
3. **Citations (Stage 6):** After each Stage 6 script completes, extract the data source citation from the research-executor's output (the `### Citation` section in the Stage 6 output format). Append the citation to STATE.md > Citations Accumulated > Data Sources table with the source name, full citation text, stage number, and script filename. If the citation already exists in the table (duplicate source), skip it.
4. **Next:** When every script in the wave has its review recorded, dispatch the next wave, or check the stage gate after the last wave

---

## Error Recovery

For decision trees, retry logic, and escalation procedures for errors encountered during data acquisition stages, see `agent_reference/ERROR_RECOVERY.md`.

---

## Verification Checklists

Apply the relevant checklist after each subagent returns findings for the corresponding stage.

### Stage 5 (Data Retrieval) Verification

- [ ] Fetch Summary has actual counts (not "TBD")
- [ ] CP1 Status explicitly stated (PASSED/WARNING/FAILED; log verdict `PASSED WITH WARNINGS` maps to WARNING) with its count line
- [ ] File locations provided with actual filenames
- [ ] If CP1 FAILED: Stop reason documented
- [ ] If data lag ≥3 years: Flagged for user notification
- [ ] If flag years (per FLAG_YEARS in Plan Domain Configuration) included: Flagged with warning

### Stage 6 (Context Application) Verification

- [ ] Cleaning Applied table shows actual row counts removed
- [ ] CP2 Status explicitly stated (PASSED/WARNING/FAILED; log verdict `PASSED WITH WARNINGS` maps to WARNING) with its count line
- [ ] Suppression rate calculated and reported
- [ ] Validity Check completed (Yes/No/Conditional)
- [ ] Citation text present and complete
- [ ] File locations provided
- [ ] If CP2 FAILED: Stop reason documented
