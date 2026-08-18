# Error Recovery Reference

This document provides decision trees and procedures for handling common errors and failures during the research workflow.

---

## Iteration Limits Summary

**Standardized limits for all error types:**

| Error Type | Max Attempts | After Max Attempts | Notes |
|------------|--------------|-------------------|-------|
| Data unavailable | 0 | Escalate immediately | User must decide path forward |
| Access/network error | 3 | Stop, report to user | Exponential backoff between attempts |
| Code execution error | 2 | Stop, escalate to user | Try alternative approach on 2nd attempt |
| Validation failure (STOP condition) | 0 | Escalate immediately | Never retry STOP conditions |
| Validation failure (warning) | N/A | Document and proceed | Warnings don't consume retries |
| **QA BLOCKER (non-methodology)** | 2 | Stop, escalate to user | Apply Rule 5 fixes via revision (2 revision scripts: _a.py, _b.py after original fails) |
| **QA BLOCKER (methodology)** | 0 | Escalate immediately | Becomes Rule 4 escalation |
| **QA WARNING** | N/A | Document, flag for Stage 10 | Warnings don't block progress |
| Plan check failure | 2 revisions | Return to planning | Original check + max 2 revision cycles |
| Verification gap | 3 | Stop, report to user | Gap may indicate fundamental issue |
| Subagent re-invocation | 3 | Stop, fundamental issue | May need task redesign |

### Escalation Template

After max attempts reached, use this format:

```markdown
**ITERATION LIMIT REACHED**

**Error Type:** [type from table above]
**Attempts Made:** [N]
**Stage:** [current stage]

**What Was Tried:**
1. **Attempt 1:** [description]
   - Result: [outcome]
2. **Attempt 2:** [description]
   - Result: [outcome]
3. **Attempt 3:** [description] (if applicable)
   - Result: [outcome]

**Root Cause Analysis:**
[Your hypothesis for why it's not working]

**Options:**
1. **[Option Name]:** [description]
   - Pro: [benefit]
   - Con: [drawback]
2. **[Option Name]:** [description]
   - Pro: [benefit]
   - Con: [drawback]
3. **[Option Name]:** [description]
   - Pro: [benefit]
   - Con: [drawback]

**Recommendation:**
[Your suggested path forward with rationale]

Awaiting your guidance before proceeding.
```

---

## Error Classification

| Category | Examples | Typical Resolution | Per-Incident Limit |
|----------|----------|-------------------|-------------------|
| **Data Availability** | No data exists, mirror file not found | Escalate immediately | 0 retries |
| **Access/Network** | Timeout, 404 (mirror file not found), network errors | Retry with backoff | 3 retries |
| **Data Quality** | High suppression, unexpected nulls | Adjust approach or escalate | Varies |
| **Code Execution** | Syntax errors, runtime errors | Fix and retry | 2 attempts |
| **Validation Failure** | Checkpoint failed | Investigate and fix or escalate | Varies by severity |
| **QA BLOCKER** | Code-reviewer finds correctness issue | Revision via Rule 5 | 2 revisions |
| **QA Methodology Issue** | Code contradicts Plan | Escalate immediately | 0 revisions |
| **Resource** | Memory, timeout | Optimize or escalate | 1 attempt |

## Error Recovery Routing

When errors occur during pipeline execution, this routing determines which agent handles recovery:

```
ERROR DETECTED
      |
      +- Data issue (empty, wrong shape)?
      |       +-> research-executor retry (max 2)
      |               +-> debugger (if still failing)
      |
      +- QA BLOCKER found (code-reviewer)?
      |       +-> Is it a methodology issue?
      |               +-> YES -> ESCALATE to user immediately
      |               +-> NO -> research-executor revision
      |                       +-> code-reviewer re-reviews
      |                               +-> Resolved -> Proceed
      |                               +-> Still BLOCKER after 2 attempts -> ESCALATE
      |
      +- Transformation issue (unexpected row loss)?
      |       +-> debugger
      |               +-> Fix identified -> research-executor applies fix
      |               +-> Root cause unclear -> ESCALATE to user
      |
      +- Plan issue (missing section, ambiguous task)?
      |       +-> data-planner (revision)
      |               +-> plan-checker validates
      |
      +- Integration issue (broken references)?
      |       +-> integration-checker diagnoses
      |               +-> Orchestrator coordinates fix
      |
      +- Verification failure (stub detected, missing artifact)?
              +-> data-verifier documents
                      +-> Orchestrator coordinates completion
```

**Agent-Specific Error Budgets:**

| Agent | Max Attempts | Then |
|-------|-------------|------|
| research-executor | 2 retries per task | Invoke debugger |
| code-reviewer | 2 revision cycles per script | Escalate to user |
| debugger | 5 hypothesis cycles | Escalate to user |
| data-planner | 2 revision cycles | Escalate to user |
| Any agent | Context degradation detected | Compress and continue or restart |

---

## Debugger Invocation Template

The debugger agent is invoked during error recovery, not at a fixed pipeline stage. It is the only agent invoked on-demand rather than at a predetermined stage.

```python
Agent({
    description: "Debug: [Brief Error Description]",
    prompt: """You are a Debugger. Read and follow the protocol in
    `{BASE_DIR}/.claude/agents/debugger.md`.

    **BASE_DIR:** {BASE_DIR}
    All relative paths in referenced files resolve from BASE_DIR.

    [If data transformation issue: Call the skill tool with name 'polars'.]

    **CONTEXT:**
    Research Question: [verbatim]
    Plan Path: {BASE_DIR}/research/[project]/[Plan filename]
    Plan Tasks Path: {BASE_DIR}/research/[project]/[Plan_Tasks filename]

    **ERROR DETAILS:**
    - Error message: [verbatim error or symptom]
    - Stage and step: [Stage N, Step M]
    - Failed script: {BASE_DIR}/research/[project]/scripts/[path]
    - Last successful operation: [description + output]
    [If QA-triggered:]
    - QA report: {BASE_DIR}/research/[project]/scripts/cr/[cr script path]
    - Specific BLOCKER check: [which check failed]

    Diagnose the root cause using scientific hypothesis-testing.
    Return findings using the Debugger Output Format.""",
    subagent_type: "debugger"
})
```

---

## Session Error Budget

To prevent infinite retry loops and excessive resource consumption, track cumulative errors across the entire analysis session.

### Budget Limits

| Error Type | Per-Stage Limit | Session Limit | Action When Exceeded |
|------------|----------------|---------------|---------------------|
| Data access retries | 3 | 9 | STOP with comprehensive error report |
| Code fix attempts | 2 | 6 | STOP, escalate to user |
| **QA BLOCKER revisions** | 2 per script | 8 per session | STOP, escalate to user |
| **QA methodology issues** | 0 | 2 | STOP, fundamental methodology question |
| Subagent re-invocations | 3 | 9 | STOP, fundamental issue present |
| Validation failures (STOP conditions) | 0 | 3 | STOP, analysis may not be feasible |

### Data Onboarding Error Budgets

| Resource | Per-Part Limit | Session Limit | Notes |
|----------|---------------|---------------|-------|
| Code fix attempts | 2 | 6 | Per profiling part (A/B/C/D) |
| Subagent re-invocations | 3 | 9 | Per profiling part |
| QA BLOCKER revisions | 2 | 8 | Per script within phase; 2 max before escalation |
| STOP conditions | — | 3 | Session-wide |
| QA escalations | — | 3 | Incremented when QA BLOCKER remains unresolved after max revision attempts and must be escalated to user |

> **Budget asymmetry note:** Session limits are deliberately lower than the sum of per-part limits (e.g., Code fix: 2/part × 4 = 8, but session limit is 6). This prevents error concentration — a session that consumes its full per-part budget in every part indicates systemic issues that warrant user intervention rather than continued automated recovery.

**Budget read-gating:** The Per-Part Execution Cycle's Step 0 (in `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md`) performs budget read-gating before each profiling part. If remaining budget is 0 for any category, the orchestrator must escalate to the user before proceeding.

### Budget Tracking

The orchestrator MUST track cumulative errors in STATE.md's `## Error Budget Consumed` section:

```markdown
### Error Budget Status

| Error Type | Used | Remaining | Status |
|------------|------|-----------|--------|
| Data access retries | 4 | 5/9 | ⚠️ Elevated |
| Code attempts | 2 | 4/6 | ✅ Normal |
| Subagent re-invocations | 1 | 8/9 | ✅ Normal |
| STOP conditions hit | 1 | 2/3 | ⚠️ Warning |
```

### Budget Read-Gating

The orchestrator reads the Error Budget Consumed section from STATE.md at Step 0 of each Composite Execution Pattern cycle (see `full-pipeline-mode.md`). If any category has remaining budget ≤ 0, the orchestrator MUST STOP and follow the Budget Exhaustion Protocol below rather than dispatching the next task. This ensures budget enforcement is data-driven (read from STATE.md) rather than memory-dependent.

**Data Onboarding mode:** The Per-Part Execution Cycle's Step 0 (in `data-onboarding-mode.md`) performs budget read-gating before each profiling part. The orchestrator reads STATE.md's Error Budget Consumed section and confirms remaining budget > 0 before dispatching the next part's subagent.

### Budget Exhaustion Protocol

When any session limit is exceeded:

1. **STOP all execution immediately**
2. **Generate comprehensive error report:**
   ```markdown
   **STOP: Session Error Budget Exhausted**
   
   **Budget Type:** [Data access retries | Code attempts | Subagent invocations | STOP conditions]
   **Limit:** [N]
   **Consumed:** [N+]
   
   **Error History:**
   | Stage | Error | Attempts | Resolution |
   |-------|-------|----------|------------|
   | Stage 5 | Data access timeout | 3 | Eventual success |
   | Stage 7 | Join error | 2 | Fixed |
   | Stage 7 | Transform error | 2 | Fixed |
   | Stage 7 | Filter error | 2 | Failed (budget exhausted) |
   
   **Analysis:**
   The high error rate suggests [fundamental data issue | Data access instability | methodology mismatch | complexity too high].
   
   **Recommendation:**
   [Simplify scope | Wait and retry later | Alternative data source | Escalate for manual intervention]
   
   Awaiting your guidance.
   ```
3. **Update Plan with budget exhaustion in Issues section**
4. **Await user guidance before any further attempts**

### Preventive Measures

To stay within budget:
- **Be precise in subagent prompts** to avoid re-invocations
- **Verify query parameters before execution** to avoid data access failures
- **Review code before execution** when delegating complex transformations
- **Escalate proactively** when patterns suggest fundamental issues

---

## Master Decision Tree

```
Error Encountered
    │
    ├─ Is it a data availability issue?
    │   ├─ YES → ESCALATE IMMEDIATELY
    │   │        (per design decision: user must decide path forward)
    │   └─ NO → Continue
    │
    ├─ Is it an data access/network error?
    │   ├─ YES → Apply retry logic
    │   │        ├─ Retry 1 (wait 1s)
    │   │        ├─ Retry 2 (wait 5s)
    │   │        ├─ Retry 3 (wait 15s)
    │   │        └─ Still failing? → ESCALATE
    │   └─ NO → Continue
    │
    ├─ Is it a data quality issue?
    │   ├─ YES → Is it a STOP condition?
    │   │        ├─ YES → ESCALATE with options
    │   │        └─ NO → Document and proceed with caution
    │   └─ NO → Continue
    │
    ├─ Is it a code execution error?
    │   ├─ YES → Attempt fix
    │   │        ├─ Fix attempt 1
    │   │        ├─ Fix attempt 2
    │   │        └─ Still failing? → ESCALATE
    │   └─ NO → Continue
    │
    ├─ Is it a validation failure?
    │   ├─ YES → Is it a STOP condition?
    │   │        ├─ YES → ESCALATE
    │   │        └─ NO → Document warning and proceed
    │   └─ NO → Continue
    │
    ├─ Is it a QA BLOCKER from code-reviewer?
    │   ├─ YES → Is it a methodology issue?
    │   │        ├─ YES → ESCALATE IMMEDIATELY (Rule 4)
    │   │        └─ NO → Apply revision (Rule 5)
    │   │                 ├─ Revision attempt 1
    │   │                 ├─ Revision attempt 2
    │   │                 └─ Still BLOCKER? → ESCALATE
    │   └─ NO (WARNING/INFO) → Log for Stage 10, proceed
    │
    └─ Unknown error → ESCALATE with full details
```

---

## Category-Specific Recovery

### Data Availability Errors

**Definition:** The requested data does not exist in the data access mirrors.

**Examples:**
- Endpoint returns 404
- Variable not found
- Years not available
- No data for specified filters

**Recovery:** ESCALATE IMMEDIATELY

```markdown
**STOP: Data Unavailable**

**What I Searched:**
- Endpoint: [endpoint]
- Filters: [filters]
- Years: [years]

**What I Found:**
[Description of what was or wasn't available]

**Impact:**
[How this affects the research question]

**Options:**
1. **Alternative data source:** [if available]
2. **Modify research question:** [suggested modification]
3. **Use proxy variable:** [if applicable]
4. **Acknowledge limitation:** Proceed without this data, document limitation

**Recommendation:**
[Your suggested path]

Awaiting your guidance before proceeding.
```

---

### Data Access/Network Errors

**Definition:** Transient errors from data access mirror communication.

**Examples:**
- Connection timeout
- 429 Too Many Requests
- 500/502/503 Server errors
- Network unreachable

**Recovery:** Retry with exponential backoff

```python
import polars as pl

def fetch_from_mirrors(mirrors: list[dict], dataset_path: str) -> pl.DataFrame:
    """Download data from configured mirrors with fallback."""
    errors = []

    for mirror in mirrors:
        url = mirror["url_template"].format(path=dataset_path)
        try:
            if mirror.get("read_strategy") == "eager_parquet":
                df = pl.read_parquet(url)
            else:
                df = pl.read_csv(url)
            print(f"Mirror: {mirror['name']} — {df.shape[0]:,} rows fetched")
            return df

        except Exception as e:
            errors.append(f"{mirror['name']}: {e}")
            print(f"Mirror {mirror['name']} failed: {e}")
            continue

    # All mirrors failed
    error_report = "\n".join(errors)
    raise RuntimeError(
        f"All mirrors failed for {dataset_path}:\n{error_report}\n"
        "STOP: Escalate to user — check mirrors.yaml configuration"
    )
```

**R equivalent pattern:**

```r
# --- Data Access with Mirror Fallback ---
# INTENT: Download data from configured mirrors with fallback
library(arrow)

fetch_result <- NULL
errors <- character(0)

for (i in seq_along(mirrors)) {
  mirror <- mirrors[[i]]
  url <- sprintf(mirror$url_template, path = dataset_path)
  tryCatch({
    if (identical(mirror$read_strategy, "eager_parquet")) {
      # NOTE: plain read shown for template brevity — mirror parquet may be
      # Polars-written with string_view columns that fail a plain read under R
      # arrow ("cannot handle Array of type <utf8_view>"). Real recovery scripts
      # use the view-safe parquet read from the domain query skill's
      # fetch-patterns.md (e.g., education-data-query).
      fetch_result <- arrow::read_parquet(url)
    } else {
      fetch_result <- readr::read_csv(url, show_col_types = FALSE)
    }
    cat(sprintf("Mirror: %s - %s rows fetched\n", mirror$name, format(nrow(fetch_result), big.mark = ",")))
    break
  }, error = function(e) {
    errors <<- c(errors, sprintf("%s: %s", mirror$name, conditionMessage(e)))
    cat(sprintf("Mirror %s failed: %s\n", mirror$name, conditionMessage(e)))
  })
}

if (is.null(fetch_result)) {
  stop(sprintf("All mirrors failed for %s:\n%s\nSTOP: Escalate to user",
               dataset_path, paste(errors, collapse = "\n")))
}
```

**If retry fails:** ESCALATE

```markdown
**STOP: Data Access Error After Retries**

**Endpoint:** [URL]
**Error:** [error message]
**Attempts:** 3

**Possible Causes:**
- Data access mirror service disruption
- Rate limiting exceeded
- Invalid mirror file path

**Recommendation:**
Wait and retry later, or verify endpoint is correct.

Awaiting guidance.
```

---

### Data Quality Errors

**Definition:** Data retrieved but quality issues prevent analysis.

**Examples:**
- Suppression rate >50%
- Unexpected missingness patterns
- Data type mismatches
- Impossible values

**Recovery Decision Tree:**

```
Data Quality Issue
    │
    ├─ Is suppression rate >50%?
    │   └─ YES → STOP, propose alternatives:
    │            - Aggregate to higher level (state instead of district)
    │            - Use different variable
    │            - Document limitation and proceed if acceptable
    │
    ├─ Are there unexpected nulls?
    │   └─ YES → Investigate source
    │            ├─ From data access source (expected) → Document
    │            ├─ From transformation (bug) → Fix code
    │            └─ Unknown → STOP, investigate
    │
    ├─ Are there impossible values?
    │   └─ YES → Investigate
    │            ├─ Coded value not filtered → Fix filter
    │            ├─ Data entry error → Document, filter
    │            └─ Unknown → STOP, investigate
    │
    └─ Other quality issue → Document and assess impact
```

**Escalation format:**

```markdown
**STOP: Data Quality Issue**

**Issue:** [description]
**Variable(s):** [affected variables]
**Severity:** [rate/extent]

**Investigation:**
[What you found when investigating]

**Impact:**
[How this affects the analysis]

**Options:**
1. [Option with tradeoffs]
2. [Option with tradeoffs]
3. [Option with tradeoffs]

**Recommendation:** [your suggestion]

Awaiting guidance.
```

---

### Code Execution Errors

**Definition:** Python or R code fails to execute.

**Python Examples:**
- SyntaxError
- TypeError
- KeyError
- MemoryError

**R Examples:**
- `Error in ...: could not find function` — Missing `library()` call
- `Error in ...: object 'x' not found` — Variable doesn't exist or misspelled
- `subscript out of bounds` — Index exceeds vector/list length
- `non-conformable arguments` — Matrix/vector dimension mismatch
- `cannot allocate vector of size` — Out of memory
- `replacement has N rows, data has M` — Recycling/length mismatch in assignment
- `object of type 'closure' is not subsettable` — Trying to subset a function name
- `there is no package called 'X'` — Package not installed (check Dockerfile)
- `Error in parse(text = ...)` — Syntax error (unmatched brackets, pipes, assignments)

**Recovery:** Fix and retry (max 2 attempts) using **script versioning**

**CRITICAL: File-First Script Versioning**

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

When a script fails, DO NOT modify the original. Instead:
1. Original script (`01_task.py`) keeps its failed output appended (audit trail)
2. Create a clean versioned copy with `scripts/create_script_revision.sh` (`01_task_a.py`), then apply fixes — the utility strips the appended execution log so the copy runs (a plain `cp` would carry the marker and be refused)
3. Execute with automatic output capture wrapper to the new version
4. If still failing, create `01_task_b.py`, etc.
5. Marimo notebook uses only the final successful version

**Attempt 1: Create versioned fix**
```
1. Read the full error traceback in the script's appended output
2. Identify the root cause
3. Create a clean versioned copy: bash {BASE_DIR}/scripts/create_script_revision.sh {PROJECT_DIR}/scripts/.../01_task.py {PROJECT_DIR}/scripts/.../01_task_a.py
4. Apply fix in the new copy
5. Execute (single Bash call): `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../01_task_a.py`
```

**Attempt 2: Alternative approach in new version**
```
1. If same error, create another version (e.g., 01_task_b.py)
2. Try different approach in this copy
3. Execute and capture output
```

**If still failing after 2 attempts:** ESCALATE

```markdown
**STOP: Code Execution Error**

**Error:** [error type and message]

**Code:**
```python
[relevant code snippet]
```

**Attempts:**
1. [What was tried and result]
2. [What was tried and result]

**Analysis:**
[Your understanding of the issue]

**Recommendation:**
[Suggested resolution or alternative approach]

Awaiting guidance.
```

#### R Error Types and Recovery

| Error Pattern | Likely Cause | Recovery |
|--------------|-------------|----------|
| `could not find function "x"` | Missing `library()` call | Add the required `library()` to Config section |
| `object 'x' not found` | Variable doesn't exist | Check spelling, verify data loaded correctly |
| `subscript out of bounds` | Index exceeds vector/list length | Check dimensions before indexing |
| `non-conformable arguments` | Matrix/vector dimension mismatch | Verify shapes match for the operation |
| `cannot allocate vector of size` | Out of memory | Filter data earlier, use data.table, or increase memory |
| `replacement has N rows, data has M` | Recycling/length mismatch | Ensure assignment vectors match target length |
| `object of type 'closure' is not subsettable` | Trying to subset a function | Check for name collision with function names (e.g., `data`, `df`, `c`) |
| `there is no package called 'X'` | Package not installed | Check Dockerfile, verify with `packageVersion("X")` |
| `Error in parse(text = ...)` | Syntax error in R code | Check for unmatched brackets, pipes, assignments |
| `unused argument` | Wrong function signature | Check function documentation; argument may have been renamed |
| `argument is of length zero` | NULL passed to condition or subset | Add `is.null()` / `length() > 0` guards |
| `missing value where TRUE/FALSE needed` | NA in `if()` condition | Use `isTRUE()` or add `!is.na()` check |

**R Script Versioning:** R script versioning follows the same pattern as Python: `01_task.R` -> `01_task_a.R` -> `01_task_b.R`. The execution log is appended by `run_with_capture.sh` identically to Python scripts.

#### R Diagnostic Script Template

```r
# --- Diagnostic Script ---
# INTENT: Diagnose [error description]
library(dplyr)
library(arrow)

# --- Config ---
input_path <- "[input_path]"

# --- Load ---
df <- arrow::read_parquet(input_path)

# --- Structural Diagnosis ---
cat("=== STRUCTURAL DIAGNOSIS ===\n")
cat("Rows:", nrow(df), "\n")
cat("Cols:", ncol(df), "\n")
cat("\nColumn names:\n")
print(names(df))
cat("\nColumn types:\n")
print(data.frame(column = names(df), type = sapply(df, function(x) class(x)[1])))

# --- NA Summary ---
cat("\n=== NA SUMMARY ===\n")
na_counts <- colSums(is.na(df))
na_pct <- round(na_counts / nrow(df) * 100, 1)
na_summary <- data.frame(column = names(na_counts), na_count = na_counts, na_pct = na_pct)
na_summary <- na_summary[na_summary$na_count > 0, ]
if (nrow(na_summary) > 0) {
  print(na_summary)
} else {
  cat("No NA values found\n")
}

# --- Specific Checks ---
cat("\n=== SPECIFIC CHECKS ===\n")
# [Targeted checks based on the error]
# Example: check for coded values
for (col in names(df)[sapply(df, is.numeric)]) {
  for (code in c(-1, -2, -3, -9, -99, -999)) {
    count <- sum(df[[col]] == code, na.rm = TRUE)
    if (count > 0) {
      cat(sprintf("  %s: %d occurrences of coded value %d\n", col, count, code))
    }
  }
}

# --- Sample Rows ---
cat("\n=== SAMPLE DATA ===\n")
cat("First 5 rows:\n")
print(head(df, 5))

cat("\n=== DIAGNOSIS COMPLETE ===\n")
```

---

### QA BLOCKER Recovery (NEW)

**Definition:** code-reviewer returns BLOCKER severity after script review.

**Types of QA BLOCKERs:**

| Type | Examples | Recovery |
|------|----------|----------|
| **Correctness** | Wrong join type, incorrect filter, type mismatch | Fix via revision (Rule 5) |
| **Validation Gap** | Missing checkpoint, inadequate invariants | Add validation via revision |
| **Stub/Placeholder** | TODO, FIXME, pass, NotImplementedError | Complete implementation |
| **Data Corruption** | Unexpected nulls, wrong row count | Fix transformation |
| **Methodology** | Code contradicts Plan specification | ESCALATE immediately (Rule 4) |

**Additional BLOCKER types for Data Onboarding profiling QA (QAP1-QAP4):**

| Type | Example | Remediation |
|------|---------|-------------|
| Profiling Accuracy | Distribution claim unsupported by data; uniqueness count incorrect | Re-run profiling script with corrected logic |
| Interpretation Discipline | Semantic interpretation missing [PRELIMINARY] marker | Re-run interpretation script with markers enforced |
| Coded Value Omission | Standard sentinels (-1, -9, -99, -999) present but not catalogued | Re-run quality-anomaly script with expanded scan |

**Recovery Flow:**

```
code-reviewer returns BLOCKER
    │
    ├─ Is it a methodology issue?
    │   ├─ YES → STOP, escalate to user (Rule 4)
    │   └─ NO → Continue to revision
    │
    ├─ Revision Attempt 1
    │   ├─ Create new versioned script (_a.py/_a.R or next suffix)
    │   ├─ Apply fix suggested by code-reviewer
    │   ├─ Execute with full validation
    │   └─ Return for re-QA
    │
    ├─ Re-QA results
    │   ├─ PASSED/WARNING → Proceed
    │   └─ Still BLOCKER → Revision Attempt 2
    │
    ├─ Revision Attempt 2
    │   ├─ Create next versioned script (_b.py/_b.R)
    │   ├─ Try different approach
    │   ├─ Execute with full validation
    │   └─ Return for re-QA
    │
    └─ After 2 attempts, still BLOCKER → ESCALATE
```

**Revision Request Format:**

```markdown
**REVISION REQUEST: [Task Name]**

**Original Script:** scripts/stage{N}_{type}/{step}_{name}.py
**Current Version:** scripts/stage{N}_{type}/{step}_{name}_{suffix}.py

**QA BLOCKER Issue:**
- **Type:** [Correctness | Validation Gap | Stub | Data Corruption]
- **Description:** [What's wrong]
- **Location:** [Where in code]
- **Suggested Fix:** [From code-reviewer]

**Instructions:**
1. Create new versioned script: {step}_{name}_{next_suffix}.py
2. Apply fix for the BLOCKER issue
3. Execute with full validation
4. Append execution log
5. Return execution report

**Do NOT modify prior script versions** — they serve as audit trail.
```

**Escalation after 2 failed revisions:**

```markdown
**STOP: QA BLOCKER Unresolved**

**Script:** scripts/stage{N}_{type}/{step}_{name}.py
**Issue:** [QA BLOCKER description]

**Revision Attempts:**
1. **{script}_a.py:** [What was tried and result]
2. **{script}_b.py:** [What was tried and result]

**Analysis:**
[Why the issue persists despite two fix attempts]

**Options:**
1. [Option with implications]
2. [Option with implications]
3. [Option with implications]

**Recommendation:**
[Your suggested path forward]

Awaiting guidance.
```

---

### Validation Failures

**Definition:** A checkpoint (CP1-CP4) fails.

**STOP Conditions (require escalation):**
- CP1: Empty data, missing critical columns
- CP2: >50% suppression, >90% data loss
- CP3: >90% row loss after transformation
- CP4: Missing critical requirements

**Warning Conditions (document and proceed):**
- High but acceptable missingness
- Unexpected but manageable row count changes
- Non-critical columns with issues

**Recovery:**

```
Validation Failure
    │
    ├─ Is it a STOP condition?
    │   └─ YES → ESCALATE immediately
    │
    ├─ Is it fixable?
    │   ├─ YES → Fix and re-validate
    │   └─ NO → Document and proceed (if warning-level)
    │
    └─ Document in Plan regardless of severity
```

---

## PreToolUse Safety-Hook Blocks

**Definition:** A `PreToolUse` safety hook denied a Bash command before it ran. A `bash-safety` block surfaces as **exit code 2** with a `BLOCKED by ...` message on stderr; `enforce-single-command` and `enforce-file-first` block the same way.

**A hook block is a deliberate guardrail, not a transient error.** It is not an access timeout or a flaky failure — the hook evaluated the command and refused it by design. Retrying the identical command will fail identically and consumes budget for nothing. The recovery is always to change *what* you are doing, per the block category below, not to re-issue the same command.

CLAUDE.md § Boundaries & Safety (summary) and the full Defense-in-Depth Architecture table in `agent_reference/BOUNDARIES.md` are the authoritative source for exactly which commands each hook blocks and why; the paths below are the recovery action, not a restatement of the rules.

| Block category | Why it fired | Recovery |
|----------------|-------------|----------|
| **Anti-tampering (`bash-safety.sh` §7)** | A shell *write* targeting `.claude/hooks/`, `.claude/logs/`, `.claude/settings*.json`, or `benchmarks/harness/hooks/` — these are user-only. | Do not retry as an agent. Draft the change to a project scratch/staged location (`scripts/scratch/` or a project-local staged path) and ask the **user** to apply it via a `!`-prefixed session command or a host terminal. Hooks do not vet user-typed `!` commands. (Reads and git index ops on these paths remain open; the Edit/Write tools on `settings.json` are also unaffected — only shell writes are blocked.) |
| **Package install (`bash-safety.sh` §8)** | A runtime command-line install — **Python** (`pip`/`uv`/`conda`-type) or **R** (`R CMD INSTALL`, `Rscript -e 'install.packages(...)'`, `remotes`/`devtools`/`pak`/`renv`/`BiocManager` verbs) — these drift from the Dockerfile and vanish on the next rebuild. | Add the dependency to the Dockerfile and rebuild (`bash rebuild_daaf.sh` from the `daaf-docker/` folder) — by default in the user additions block near the end of the Dockerfile, which rebuilds fast via layer caching (place it earlier only when functionally required, e.g. a build-time system dependency). For a one-off exploratory need, the user can run the install themselves via `!`-prefix (ephemeral — gone on rebuild). |
| **In-script package install (`run_with_capture.sh` content scan, exit 3)** | The wrapper's pre-execution scan found an install call written *inside* the `.py`/`.R` script body (e.g. `install.packages(...)`, `os.system("pip install ...")`) — the path shell-level hooks cannot see. The script was **not** executed and **no** execution log was appended. | Remove the install call from the script and re-run the **same file** — because no execution log was appended, immutable versioning has not engaged, so the file stays editable in place (no `_a`/`_b` version needed). If the package is genuinely missing, escalate: add it to the Dockerfile and rebuild (as in the §8 row above). |
| **/tmp provenance (`bash-safety.sh` §6)** | A shell *write* to `/tmp`, which is outside the backup and audit boundary. | Write inside the project instead — `{PROJECT_DIR}/scripts/scratch/`. (Reading DAAF's own `/tmp` coordination caches stays allowed; only writes are blocked.) |
| **`enforce-single-command`** | The command chained multiple statements (`&&`, `;`, `||`, or newlines). | Split into separate Bash calls, one command each. |
| **`enforce-file-first`** (coding agents) | Direct `python`/`python3`/`Rscript` (or bare `R` batch) execution, bypassing the audit trail. | Write the script to `scripts/` and run it via `run_with_capture.sh` (see `SCRIPT_EXECUTION_REFERENCE.md`). |

**Staged-draft → user-install pattern (anti-tampering):** Because hook, log, and settings changes cannot be applied by an agent's shell, the working pattern is: (1) draft the full change in a project scratch/staged file, (2) if it is a `bash-safety.sh` change, test the draft against the regression battery *before* install — `bash scripts/test_safety_hooks.sh <draft-path>` (see the `shell-scripting` skill's `testing.md`), then (3) hand the user the exact command to install it from a host terminal or a `!`-prefixed session command. The agent never writes the protected path directly.

**Do not count a hook block against a retry budget as if it were a code-execution error** — it is not fixable by a second attempt at the same command. If the correct recovery path above is itself blocked or unavailable, escalate to the user rather than looping.

---

## Stage-Specific Recovery

### Stage 2 (Data Exploration) Failures

| Issue | Recovery |
|-------|----------|
| No endpoints found | Escalate immediately |
| Unexpected data level | Re-search with broader criteria |
| Missing years | Document limitation, adjust scope |

### Stage 3 (Source Deep-Dive) Failures

| Issue | Recovery |
|-------|----------|
| Skill not available | Use the domain's general context skill (per Plan Domain Configuration) |
| Contradictory documentation | Document both versions, note uncertainty |
| Missing coded value info | Flag for manual verification |

### Stage 5 (Data Retrieval) Failures

| Issue | Recovery |
|-------|----------|
| Data access timeout | Retry with backoff |
| Empty response | Verify filters, escalate if correct |
| Partial data | Verify download completed, retry from mirror |

### Stage 6 (Context Application) Failures

| Issue | Recovery |
|-------|----------|
| High suppression | Escalate with aggregation options |
| Invalid analysis type | Block and explain why |
| Cleaning removes too much | Investigate and escalate |

### Stage 7 (EDA & Transformation) Failures

| Issue | Recovery |
|-------|----------|
| Transformation error | Fix code, retry |
| Unexpected patterns | Report to user, proceed with caution |
| Memory issues | Use lazy evaluation, chunk processing |

### Stage 9 (Notebook Assembly) Failures

**Marimo (Python):**

| Issue | Recovery |
|-------|----------|
| Archive/header/log bundle error | Restore the canonical adjacent header → commented source → non-placeholder execution-log sequence; never substitute `No execution log found` |
| Reactivity or validation error | Review only notebook scaffolding, bounded Parquet preview, and existing-figure display dependencies; archived script code remains comment-prefixed |
| New widget/analysis code detected | Remove it; Stage 9 permits only bounded preview of existing Parquet data or display of an already-created figure |

**Quarto (R):**

Archive chunks remain disabled by global and per-chunk `eval: false`; they do
not execute or provide cross-chunk state. Only optional data-preview chunks and
dedicated existing-figure display chunks that explicitly set `#| eval: true`
execute during rendering.

| Issue | Recovery |
|-------|----------|
| Missing/empty/placeholder execution log | Block canonical assembly and correct the source script evidence; never archive `No execution log found` as a valid callout |
| Enabled preview/display chunk execution error | Fix only the explicitly enabled chunk: use the exact `arrow::read_parquet()` + `dplyr::glimpse()` + `head()` preview, or a dedicated figure-display chunk containing only `knitr::include_graphics("existing/path.png")` with `#| echo: false`; preserve archive chunks unchanged and disabled |
| Render failure | Check YAML frontmatter, Markdown/chunk syntax, callouts, and existing resource paths; verify the knitr engine is available |
| Package loading error in an enabled data preview | Verify `arrow` and `dplyr` are available through the Dockerfile-defined environment; do not add runtime package installs or `library()` calls to archive chunks |
| Object not found in an enabled data preview | Do not rely on cross-chunk state. Ensure that preview chunk loads its own existing parquet into `df`; for a figure, use a path-only Markdown image or dedicated `include_graphics()` display |

### R-Specific Recovery Patterns

Common R error recovery strategies when working with tidyverse/arrow pipelines:

**Package/Library Errors:**
```r
# --- Diagnostic: Package availability ---
cat("=== PACKAGE DIAGNOSIS ===\n")
required_pkgs <- c("dplyr", "tidyr", "arrow", "ggplot2", "readr")
for (pkg in required_pkgs) {
  if (requireNamespace(pkg, quietly = TRUE)) {
    cat(sprintf("[PASS] %s %s\n", pkg, packageVersion(pkg)))
  } else {
    cat(sprintf("[FAIL] %s not installed\n", pkg))
  }
}
```

**Column Name Conflicts (common after joins):**
```r
# --- Diagnostic: Duplicate column names after join ---
cat("=== COLUMN CONFLICT DIAGNOSIS ===\n")
col_names <- names(df)
dup_cols <- col_names[duplicated(col_names)]
if (length(dup_cols) > 0) {
  cat(sprintf("[ISSUE] Duplicate columns: %s\n", paste(dup_cols, collapse = ", ")))
  cat("FIX: Use suffix argument in join or rename before join\n")
} else {
  cat("[PASS] No duplicate column names\n")
}
```

**Type Coercion Issues:**
```r
# --- Diagnostic: Unexpected types after read_parquet ---
cat("=== TYPE DIAGNOSIS ===\n")
type_issues <- character(0)
for (col in names(df)) {
  col_class <- class(df[[col]])[1]
  # Check for unexpected list columns (common with nested parquet)
  if (col_class == "list") {
    type_issues <- c(type_issues, sprintf("%s: list-column (may need unnest)", col))
  }
  # Check for character columns that should be numeric
  if (col_class == "character") {
    non_na <- df[[col]][!is.na(df[[col]])]
    if (length(non_na) > 0 && all(grepl("^-?[0-9.]+$", non_na))) {
      type_issues <- c(type_issues, sprintf("%s: character but looks numeric", col))
    }
  }
}
if (length(type_issues) > 0) {
  cat("Issues found:\n")
  for (issue in type_issues) cat(sprintf("  - %s\n", issue))
} else {
  cat("[PASS] No type issues detected\n")
}
```

### Stage 10 (QA Aggregation) Failures

| Issue | Recovery |
|-------|----------|
| Unresolved BLOCKER from Stages 5-8 | Review revision history; escalate if 2 attempts already exhausted |
| Systemic WARNING pattern detected | Assess cumulative impact; escalate if pattern indicates methodology flaw |
| Missing QA reviews | Invoke code-reviewer for any unreviewed scripts before proceeding |

---

## Recovery from Different Stages (Data Onboarding)

Data Onboarding uses a different error recovery pattern than the Full Pipeline. The Per-Part Execution Cycle in `data-onboarding-mode.md` defines the atomic unit of work, and STATE.md (the sole persistent document) tracks all progress.

### Stage-Specific Recovery

| Stage | Common Errors | Recovery Action |
|-------|--------------|-----------------|
| DI-0 (API Acquisition) | API auth failure (401/403), rate limit (429), empty response, unreachable docs, pagination error | Verify API key env var is set and valid; retry with backoff (max 3); adjust query params if empty response; fall back to user description if docs unreachable; reduce page size if pagination fails |
| DI-1 (Intake) | File not found, file empty, missing inputs | Re-collect inputs from user; verify file path and accessibility |
| DI-2 (Project Setup) | Folder creation fails | Create folder manually; verify `{BASE_DIR}/scripts/run_with_capture.sh` is accessible |
| DI-3 (Part A) | Encoding errors, format detection failure, CPP1 fails | Check file format; try alternative encoding; re-invoke data-ingest subagent |
| DI-4 (Part B) | Distribution analysis errors, temporal column misidentified | Review Part A conditional decisions; re-invoke with corrected decisions |
| DI-5 (Part C) | Key detection failure, no candidate keys found | Expand composite key search; consult user about grain of data |
| DI-6 (Part D) | Interpretation ambiguity, documentation contradicts data | Flag uncertainties as [PRELIMINARY] with LOW confidence; proceed to PSU-DI2 for user review |
| DI-7 (Skill Authoring) | Template compliance failure (CPP-SKILL) | Revise skill draft (max 2 attempts); escalate if still non-compliant |
| DI-8 (Review & Delivery) | User rejects skill | Collect feedback; return to DI-7 with revision instructions |

### Data Onboarding STOP Conditions

| Condition | Triggered By | Recovery Path |
|-----------|-------------|---------------|
| API authentication fails | data-ingest agent (DI-0) or Gate GDI-0 | User verifies API key env var name and value; re-generate key if expired |
| API returns empty dataset | data-ingest agent (DI-0) or Gate GDI-0 | User verifies endpoint URL and query parameters; check if filters are too restrictive |
| API rate limited | data-ingest agent (DI-0) | Retry with exponential backoff; reduce request scope; wait and retry |
| File cannot be loaded | data-ingest agent (Part A) | User provides corrected file or format info |
| File is empty | data-ingest agent (Part A) | User provides correct file |
| >50% documented columns missing | data-ingest agent (Part D) or Gate GDI-6 | Verify correct file version; user confirms column mapping |
| File >1GB without sampling guidance | data-ingest agent or Gate GDI-3 | User approves sampling strategy |
| Critical columns entirely null | data-ingest agent | User verifies data extraction was complete |
| >50% of columns entirely null | Gate GDI-4 | User verifies file is not truncated or corrupted |
| No candidate keys identifiable | Gate GDI-5 | User provides domain knowledge about data grain |
| Template compliance fails after 2 revisions | Gate GDI-7 | Escalate to user; manual skill editing may be needed |

### Revision Request Format (Data Onboarding)

When re-invoking the data-ingest subagent to fix a BLOCKER:

```
**REVISION REQUEST**
Part: {A/B/C/D}
Failing script: {script_path}
BLOCKER: {description from code-reviewer}
QA script: {qa_script_path}

Fix the identified issue in a new script version ({script_name}_a.py).
The original script with its execution log is an immutable audit artifact — do not modify it.
```

### Revision and Extension Mode Error Recovery

Revision and Extension mode re-executes pipeline stages using Full Pipeline's error recovery patterns. The standard QA BLOCKER revision flow (max 2 attempts, then escalate) applies to all re-executed scripts.

**Revision-specific considerations:**

| Error | Source | Recovery |
|-------|--------|----------|
| Prior version data files missing/corrupted | Re-execution depends on prior Stage 5-6 outputs | Re-run from earliest affected stage rather than just the revision's re-entry point |
| Revision scope grows beyond classification | Mid-execution discovery | STOP, present to user, re-classify or escalate to Full Pipeline |
| STATE.md from prior version is incomplete | Missing execution context | Reconstruct from filesystem (script execution logs, git history) before planning revision |

For QA BLOCKER revision requests during re-execution, use the standard Revision Request format from the Full Pipeline section above.

### Reproducibility Verification Mode Error Recovery

RV mode has a lightweight, language-paired error recovery pattern. The per-script atomic cycle handles most failures inline — the code-reviewer creates Python versions (`_repro_a.py`, `_repro_b.py`) or R versions (`_repro_a.R`, `_repro_b.R`) to match the reproduced script's language.

| Stage | Common Errors | Recovery Action |
|-------|--------------|-----------------|
| RV-1 (Intake) | Missing/ambiguous Report or notebook; generic Marimo/Quarto input; existing reproduction/extraction root; decompiler failure | Require one user-selected Report and one canonical DAAF Stage 9 archive. Stop on multiple candidates or both formats. Use new destination/root only; decompilers never merge/overwrite. |
| RV-1 (Containment) | Path audit global exit 1 DIVERGED or exit 2 NOT DIRECTLY VERIFIED; dispatched script lacks in-scope MATCH assessment | Supply each exact pre-RV-2 script exclusion through repeatable validated `--exclude`, then block RV-2 until the overall result—computed only from in-scope files—is exit 0 MATCH and every dispatched script's deterministic `file_assessments` entry is `IN_SCOPE` + `MATCH`. Keep excluded files and `excluded_issues` explicit; they never become matches. Audit source only before the unique `# EXECUTION LOG` boundary: `ORIGINAL_ROOT_LOG_RESIDUE` afterward is informational, but ambiguous boundaries fail closed. State bounded assurance; dynamic paths remain outside proof. |
| RV-1 (Environment) | Original versions unpinned or R inventory incomplete | Record UNKNOWN / NOT DIRECTLY VERIFIED. Capture language-aware installed evidence via read-only commands or a diagnostic under project `scripts/repro_checks/`, executed through `run_with_capture.sh` with its appended log retained; never install packages at runtime. |
| RV-2 (Frozen inputs) | Stage 5 would run, raw hash inventory changes, or frozen evidence absent | Do not execute Stage 5. If evidence is absent, reconfirm mode. If hashes differ, fail and investigate; acquisition/mirrors remain out of scope. |
| RV-2 (Re-execution) | Python/R script fails or inherited log remains | Create `_repro_a` then `_repro_b` from clean log-free source. If `scripts/create_script_revision.sh` or a stripped failed copy is used, independently verify the inherited log marker is absent before fixes and re-execution. Apply minimal fixes, never rerun the just-failed appended file unchanged, and dispatch debugger after both revisions fail. |
| RV-2 (Log comparison) | Log helper exit 1 DIVERGED, exit 2 invalid/read failure, or exit 3 INCOMPLETE/INCONCLUSIVE | Aligning is by metric identity and stable context, never position. Exit 0 alone is CONSISTENT; exit 1 is divergent log evidence; correct exit-2 invocation/input failures; record exit 3 as NOT DIRECTLY VERIFIED, never success. Keep the result explicitly log-only. |
| RV-2 (Artifact comparison) | Artifact helper exit 2 invalid/unsupported, exit 3 NOT DIRECTLY VERIFIED, unsupported artifact, missing side, or bound exceedance | For exit 2, correct the invocation or route the artifact to its separate evidence path; for exit 3 or unavailable direct evidence, record NOT DIRECTLY VERIFIED. Defaults cap each Parquet input at 536870912 bytes and 1000000 rows before full materialization and tolerant matching at 1000000 candidate pairs. Exact-key/cardinality divergence is decided before the pair limit; duplicate assessment follows actual verification. Never infer a match. Use the artifact helper for supported Parquet/exact evidence, Read for figures, and defined representations for tables/models. |
| RV-2 (Re-execution) | Data re-fetch returns different data | Log as Data change deviation; if schema differs, STOP and present to user (escalation trigger) |
| RV-3 (Verification) | Claim/figure/finding/artifact/dimension lacks direct evidence | Record `NOT DIRECTLY VERIFIED` with reason; use only MATCH/DIVERGED/NOT DIRECTLY VERIFIED and derive coverage counts. |
| RV-4 (Synthesis) | In-scope evidence gap or incomplete report | Any gap caps verdict at PARTIALLY REPRODUCED; return incomplete report before synthesis. Keep exact pre-RV-2 exclusions separate. |

**RV-Specific Error Budget:**

| Error Type | Per-Script Limit | Session Limit | After Max |
|------------|-----------------|---------------|-----------|
| Script modification versions | 2 (`_repro_a.py`, `_repro_b.py` or `_repro_a.R`, `_repro_b.R`) | — | Mark FAILED, continue to next script |
| Debugger dispatches | 1 per script | 3 per session | Mark FAILED, continue |
| Data source schema change | — | — | STOP, present to user immediately |

**Key difference from Full Pipeline:** RV mode does NOT stop on individual script failures. The goal is a complete reproduction picture — failed scripts are documented and the process continues to the next script.

### Framework Development Mode Error Recovery

Framework Development errors are typically file-level issues (template compliance failures, integration checklist gaps, cross-reference breaks). Recovery is straightforward:

| Error Type | Recovery |
|------------|----------|
| Template compliance failure | Re-read the canonical template, identify missing sections, create revised artifact |
| Integration checklist gap | Re-read FRAMEWORK_INTEGRATION_CHECKLIST.md, identify and complete missing items |
| Cross-file inconsistency | Grep for the component name across all framework files, fix discrepancies |
| Name collision | Choose a different name; update all already-written references |

**STOP Conditions:** If the error involves safety-critical files (CLAUDE.md, settings.json, hooks), escalate to the user immediately.

---

## Re-run Procedures

### When to Re-run a Stage

| Situation | Stage(s) to Re-run | Mode |
|-----------|-------------------|------|
| Wrong endpoints identified | 2 | Refresh |
| Missing data source | 2, 3 | Additive |
| Caveats misunderstood | 3 | Refresh (affected source) |
| Query returned wrong data | 5 | Refresh |
| Transformation logic wrong | 7 | Refresh |
| Visualization incorrect | 8 | Refresh |

### Re-run Modes

**Refresh Mode:**
- Replace prior stage output entirely
- Use when fundamental assumptions were wrong
- Requires updating Plan document

**Additive Mode:**
- Supplement prior output with new findings
- Use when scope expanded or new elements added
- Add to existing Plan sections

### Re-run Invocation

```python
Agent({
    description: "Stage [N] Re-run: [Name]",
    prompt: """Previous execution encountered issues.

**ISSUE:** [what went wrong]
**MODE:** [REFRESH | ADDITIVE]

**CORRECTIVE CONTEXT:**
[What to do differently]

[If ADDITIVE: Prior findings to preserve: ...]

Re-execute the stage with this correction.

[Original stage specification]""",
    subagent_type: "[agent-name]"
})
```

---

## Escalation Format

### Standard Escalation Message

```markdown
**[STOP | WARNING]: [Brief Issue Title]**

**Stage:** [Stage number and name]
**Severity:** [Critical | High | Medium | Low]

**What Happened:**
[Clear description of the issue]

**What I Tried:**
1. [Attempt 1 and result]
2. [Attempt 2 and result]

**Impact:**
[How this affects the analysis]

**Options:**
1. **[Option Name]:** [Description]
   - Pro: [benefit]
   - Con: [drawback]

2. **[Option Name]:** [Description]
   - Pro: [benefit]
   - Con: [drawback]

3. **[Option Name]:** [Description]
   - Pro: [benefit]
   - Con: [drawback]

**Recommendation:**
[Your suggested path forward with rationale]

**To Proceed:**
[What input you need from user]

Awaiting your guidance.
```

---

## Error Logging

All errors should be logged in the Plan document:

```markdown
## Error Log

| Timestamp | Stage | Error | Resolution |
|-----------|-------|-------|------------|
| YYYY-MM-DD HH:MM | Stage N | [Brief description] | [How resolved or escalated] |
```

---

## Session-Level Recovery

Session transcript archiving is handled automatically by two hooks that work as a pair:

- **`archive-session.sh`** (fires on `SessionEnd`): Archives the complete JSONL transcript and a human-readable Markdown rendering to `.claude/logs/sessions/`, including all subagent transcripts discovered from Claude Code's raw file hierarchy.
- **`recover-session-logs.sh`** (fires on `SessionStart`): Runs a background scan for raw transcripts that were never archived — typically from sessions that crashed, were killed, or lost network connectivity before `SessionEnd` fired. For each orphaned transcript found, it pipes a synthesized payload to `archive-session.sh`, reusing all existing archiving logic. Recovered archives are timestamped using the last entry in the original transcript (not the recovery runtime), so they sort chronologically by when the session actually ran.

**No manual intervention is required.** Orphaned transcripts are recovered automatically on the next session start. The idempotency guard in `archive-session.sh` (file-size comparison keyed on session ID) prevents duplicate archives and ensures that if a still-running session was prematurely archived by recovery, the complete version from `SessionEnd` replaces the partial one.
