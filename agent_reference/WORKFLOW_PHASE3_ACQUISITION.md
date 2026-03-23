# Workflow Reference: Phase 3 — Data Acquisition & Preparation

Stages 5, 6. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline.md`.

**Execution Model:** All scripts follow the file-first execution pattern. See `SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

---

## Stage 5: Data Retrieval

**Executor:** Subagent (general-purpose)
**Skill:** Domain query skill (e.g., `education-data-query`)
**Purpose:** Fetch data from configured data mirrors

**Note:** Uses `general-purpose` subagent type (not `Plan`) because it must save data files to `data/raw/`.

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
   - Wait for QA result before proceeding to Stage 6
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to Stage 6

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
**Subagent:** general-purpose
**Skills:** `data-scientist`, `{domain_query_skill}`

> **Domain extensibility:** The orchestrator resolves the query skill name based on the active domain (from the Plan's Domain Configuration) and provides it in the Agent prompt. The example below uses `education-data-query` as the demonstration domain default.

```python
Agent({
    description: "Stage 5: Data Retrieval",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '{domain_query_skill}'.  # e.g., 'education-data-query'

**QUERY SPECIFICATION:**
- Dataset Path: {dataset_path}  (from datasets-reference.md, flat format e.g. "ccd/schools_ccd_directory")
- Years: {years}
- Filters: {filters}
- Variables: {variables}
- Expected Records: ~{expected_count}

**DATA OUTPUT REQUIREMENTS:**
- Save to: data/raw/{date_prefix}_{source}_{description}.parquet

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
4. Apply year/state/other filters locally with Polars
5. Log which mirror was used and the fetch result

**THOROUGHNESS DIRECTIVE:**
- Try each mirror in priority order
- Handle mirror failures with fallback
- Validate response shape immediately after fetch
- Document which mirror was used
- Verify all requested years are present
- Verify all requested columns are present

**OUTPUT FORMAT (1000-word hard cap):**
Return findings in this structure:

### Fetch Summary
- Mirror used: [name from mirrors.yaml]
- Download URL: [full URL used]
- Records retrieved: [count]
- Columns retrieved: [list]
- Years present: [list]
- Mirror fallback: [None | fell through from {mirror_name} due to {reason}]

### Initial Validation (CP1)
- Shape: [rows] x [cols]
- Expected rows: [from Plan.md]
- Row count ratio: [actual/expected]
- Missing values by column:
  | Column | Null Count | Null % |
  |--------|------------|--------|
- Critical columns present: [Yes/No]
- **CP1 Status:** [PASSED | FAILED | WARNING]
- **If FAILED:** [Stop reason]

### File Locations
- Parquet: data/raw/{filename}.parquet

### Confidence Assessment
| Check | Confidence | Rationale |
|-------|------------|-----------|
| Data completeness | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "research-executor"
})
```

### QA Follow-Up (MANDATORY)

**After research-executor completes EACH individual Stage 5 fetch script, orchestrator MUST immediately invoke code-reviewer to separately review that script.**
Use the **code-reviewer invocation template** from `full-pipeline.md`
with stage-specific values for Stage 5.

**Do NOT start the next Stage 5 script until QA returns PASSED or WARNING for the current script.**
**Do NOT proceed to Stage 6 until ALL Stage 5 scripts have been individually QA'd.**

### Validation (CP1)

```python
# Required checks
assert len(df) > 0, "STOP: Empty dataset"
assert all(col in df.columns for col in required_cols), "STOP: Missing columns"
assert df['year'].is_in(expected_years).all(), "WARNING: Unexpected years"
```

### Output Format

```markdown
### Fetch Summary:
- Endpoint: [URL]
- Records retrieved: [count]
- Columns: [list]
- Years present: [list]
- Data access issues: [any problems]

### Initial Validation (CP1):
- Shape: [rows x cols]
- Missing values: [summary]
- Unexpected values: [any anomalies]
- **CP1 Status:** [PASSED | FAILED]

### File Locations:
- Parquet: `data/raw/YYYY-MM-DD_[source]_[description].parquet`

### Scripts Saved (one per fetch task):
- Path: `scripts/stage5_fetch/{step}_{task-name}.py`
- Includes: Pagination handling, CP1 validation, output paths
- Note: Each fetch task produces a separate script; QA is invoked immediately after each
```

### Gate Criteria (G5)

- [ ] Data retrieved successfully
- [ ] CP1 passed (or warnings documented)
- [ ] Data saved to `data/raw/`
- [ ] **All scripts saved to `scripts/stage5_fetch/`** (one per fetch task) with standard header
- [ ] **If data lag ≥3 years:** User notified and decision documented
- [ ] STATE.md updated with Data Freshness Check findings
- [ ] **QA review completed for EACH Stage 5 script** (code-reviewer separately invoked immediately after each individual script, not batched)
- [ ] **All QA1 statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage5_{step}_cr1.py`** (+ cr2..cr5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 5, CP1 status, raw data paths recorded

---

## Stage 6: Context Application

**Executor:** Subagent (general-purpose)
**Skill:** Domain context skill (e.g., `education-data-context`)
**Purpose:** Apply source-specific cleaning and context

**Note:** Uses `general-purpose` subagent type (not `Plan`) because it must save cleaned data files to `data/processed/`.

### Actions

1. **Apply Coded Value Filters**
   - Filter -1 (missing)
   - Filter -2 (not applicable)
   - Filter -3 (suppressed)
   - Document rows removed

2. **Calculate Quality Metrics**
   - Suppression rate
   - Missing value rates
   - Data completeness

3. **Validate Analysis Type**
   - Check for invalid cross-state comparisons
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
   - Wait for QA result before proceeding to Stage 7
   - If BLOCKER: trigger revision flow (max 2 attempts)
   - If WARNING: log to STATE.md, proceed
   - If PASSED: proceed to Stage 7

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
**Subagent:** general-purpose
**Skills:** `data-scientist`, `{domain_context_skill}`

> **Domain extensibility:** The orchestrator resolves the context skill name based on the active domain (from the Plan's Domain Configuration) and provides it in the Agent prompt. The example below uses `education-data-context` as the demonstration domain default.

```python
Agent({
    description: "Stage 6: Context Application",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '{domain_context_skill}'.  # e.g., 'education-data-context'

**DATA SOURCE:** {source_name}

**RAW DATA LOCATION:** data/raw/{raw_data_filename}

**CAVEATS FROM STAGE 3:**
{source_caveats}

**CODED VALUE HANDLING (from Plan.md):**
{coded_value_specification}

**CLEAN DATA OUTPUT:**
- Save to: data/processed/{date_prefix}_{description}.parquet

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

**OUTPUT FORMAT (1000-word hard cap):**
Return findings in this structure:

### Cleaning Applied
| Code Filtered | Variable(s) | Rows Removed | % of Total |
|---------------|-------------|--------------|------------|
| -1 (Missing) | | | |
| -2 (N/A) | | | |
| -3 (Suppressed) | | | |
| **Total** | | | |

*(Coded values shown are education domain defaults. Substitute values from Plan Domain Configuration.)*

### Data Quality Report (CP2)
- Original rows: [count]
- Clean rows: [count]
- Total loss: [count] ([%])
- Suppression rate (key variable): [%]
- **CP2 Status:** [PASSED | FAILED]
- **If FAILED:** [Stop reason]

### Validity Check
- Analysis type: {analysis_description}
- Cross-state comparison: [Yes/No]
- **Valid:** [Yes | No | Conditional]
- **Warnings:** [list any concerns]

### Citation
> {full_citation_text}

### File Locations
- Parquet: data/processed/{filename}.parquet

### Confidence Assessment
| Check | Confidence | Rationale |
|-------|------------|-----------|
| Data quality | HIGH/MEDIUM/LOW | [why this confidence level] |
| Analysis validity | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "research-executor"
})
```

### QA Follow-Up (MANDATORY)

**After research-executor completes EACH individual Stage 6 cleaning script, orchestrator MUST immediately invoke code-reviewer to separately review that script.**
Use the **code-reviewer invocation template** from `full-pipeline.md`
with stage-specific values for Stage 6.

**Do NOT start the next Stage 6 script until QA returns PASSED or WARNING for the current script.**
**Do NOT proceed to Stage 7 until ALL Stage 6 scripts have been individually QA'd.**

**PSU Note:** Stage 6 concludes Phase 3. After all Stage 6 scripts are executed and QA'd, the orchestrator will present PSU3 to the user. The orchestrator compiles PSU3 from accumulated Stage 5-6 results -- no single agent produces the full PSU3 content.

### Validation (CP2)

```python
# Required checks
suppression_rate = (raw_df['key_var'] == SUPPRESSION_CODE).sum() / len(raw_df)  # SUPPRESSION_CODE from Plan Domain Configuration
assert suppression_rate < 0.5, f"STOP: Suppression {suppression_rate:.1%} > 50%"
assert len(clean_df) > len(raw_df) * 0.1, "STOP: >90% data loss"
```

### Output Format

```markdown
### Cleaning Applied:
- Coded values filtered: [summary by code]
- Rows removed: [count] ([percentage]%)

### Data Quality Report (CP2):
- Suppression rate: [percentage]
- Missing value summary: [by variable]
- **CP2 Status:** [PASSED | FAILED]

### Validity Check:
- Analysis type: [description]
- Valid: [Yes | No | Conditional]
- Warnings: [any concerns]

### Citation:
> [Full citation text]

### File Locations:
- Parquet: `data/processed/YYYY-MM-DD_[description].parquet`

### Scripts Saved (one per clean task):
- Path: `scripts/stage6_clean/{step}_{task-name}.py`
- Includes: Coded value filtering, suppression calculation, CP2 validation
- Note: Each clean task produces a separate script; QA is invoked immediately after each
```

### Gate Criteria (G6)

- [ ] Coded values handled
- [ ] CP2 passed
- [ ] Citation generated
- [ ] Data saved to `data/processed/`
- [ ] **All scripts saved to `scripts/stage6_clean/`** (one per clean task) with standard header
- [ ] **QA review completed for EACH Stage 6 script** (code-reviewer separately invoked immediately after each individual script, not batched)
- [ ] **All QA2 statuses:** PASSED/WARNING (any BLOCKER resolved via revision before next script)
- [ ] **QA scripts saved to `scripts/cr/stage6_{step}_cr1.py`** (+ cr2..cr5 if warranted)
- [ ] **STATE.md updated:** Current Stage: 6, CP2 status, suppression rate, processed data paths
- [ ] **PSU3 presented to user with data quality summary**
- [ ] **User confirmed PSU3**

---

### Phase Status Update 3 (PSU3): Data Acquired and Cleaned

**Trigger:** Gate G6 satisfied (all Stage 5-6 scripts executed and QA'd)
**Blocking:** YES — Stage 7 CANNOT begin until user confirms PSU3

**Actions:**
1. Compile data acquisition and cleaning summary from Stages 5-6
2. Include QA results from all QA1 and QA2 reviews
3. Present PSU3 to user using the PSU template
4. WAIT for explicit user confirmation

**PSU3 Content Requirements:**
- Datasets acquired: source name, shape (rows x columns), date range, file path
- Data freshness: most recent year available per source
- Data quality per dataset: missingness rates for critical columns, suppression rates
- Cleaning actions taken: rows removed (with counts and percentages), values recoded, filters applied
- QA summary table: each script's QA status (PASSED/WARNING) with details for any WARNINGs
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

#### PSU3 Content Requirements

The PSU3 checkpoint MUST include:
- Datasets acquired: source, shape, date range, file paths
- Data quality summary: missingness rates, suppression rates per dataset
- Cleaning actions taken and their impact (rows removed, values recoded)
- QA summary: QA1/QA2 results for each script (PASSED/WARNING with details)
- Any deviations from Plan.md during fetch/clean
- Data readiness assessment for analysis phase

### Post-Script Action Checklist (Stages 5-6)

After each script execution:
1. **QA:** Invoke code-reviewer immediately (see `full-pipeline.md` > Code-Reviewer Invocation)
2. **State:** Update STATE.md transformation progress table
3. **Next:** Proceed to next script in wave, or check gate if wave complete

---

## Error Recovery

For decision trees, retry logic, and escalation procedures for errors encountered during data acquisition stages, see `agent_reference/ERROR_RECOVERY.md`.

---

## Verification Checklists

Apply the relevant checklist after each subagent returns findings for the corresponding stage.

### Stage 5 (Data Retrieval) Verification

- [ ] Fetch Summary has actual counts (not "TBD")
- [ ] CP1 Status explicitly stated (PASSED/FAILED/WARNING)
- [ ] File locations provided with actual filenames
- [ ] If CP1 FAILED: Stop reason documented
- [ ] If data lag ≥3 years: Flagged for user notification
- [ ] If flag years (per FLAG_YEARS in Plan Domain Configuration) included: Flagged with warning

### Stage 6 (Context Application) Verification

- [ ] Cleaning Applied table shows actual row counts removed
- [ ] CP2 Status explicitly stated
- [ ] Suppression rate calculated and reported
- [ ] Validity Check completed (Yes/No/Conditional)
- [ ] Citation text present and complete
- [ ] File locations provided
- [ ] If CP2 FAILED: Stop reason documented
