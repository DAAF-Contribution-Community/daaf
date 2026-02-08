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
| Plan check failure | 3 | Return to planning | Revise plan before re-checking |
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

### Budget Tracking

The orchestrator MUST track cumulative errors in the Plan document's "Current Status & To-Do's" section:

```markdown
### Error Budget Status

| Error Type | Used | Remaining | Status |
|------------|------|-----------|--------|
| Data access retries | 4 | 5/9 | ⚠️ Elevated |
| Code attempts | 2 | 4/6 | ✅ Normal |
| Subagent re-invocations | 1 | 8/9 | ✅ Normal |
| STOP conditions hit | 1 | 2/3 | ⚠️ Warning |
```

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

**Definition:** Python code fails to execute.

**Examples:**
- SyntaxError
- TypeError
- KeyError
- MemoryError

**Recovery:** Fix and retry (max 2 attempts) using **script versioning**

**CRITICAL: File-First Script Versioning**

When a script fails, DO NOT modify the original. Instead:
1. Original script (`01_task.py`) keeps its failed output appended (audit trail)
2. Create versioned copy (`01_task_a.py`) with fixes
3. Execute and capture output to the new version
4. If still failing, create `01_task_b.py`, etc.
5. Marimo notebook uses only the final successful version

**Attempt 1: Create versioned fix**
```
1. Read the full error traceback in the script's appended output
2. Identify the root cause
3. Create new versioned copy (e.g., 01_task_a.py)
4. Apply fix in the new copy
5. Execute: python scripts/.../01_task_a.py 2>&1
6. Append output to the new version
```

**Attempt 2: Alternative approach in new version**
```
1. If same error, create another version (e.g., 01_task_b.py)
2. Try different approach in this copy
3. Execute and capture output
```

See `agents/research-executor.md` for the complete file-first protocol and versioning rules.

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

**Recovery Flow:**

```
code-reviewer returns BLOCKER
    │
    ├─ Is it a methodology issue?
    │   ├─ YES → STOP, escalate to user (Rule 4)
    │   └─ NO → Continue to revision
    │
    ├─ Revision Attempt 1
    │   ├─ Create new versioned script (_a.py or next suffix)
    │   ├─ Apply fix suggested by code-reviewer
    │   ├─ Execute with full validation
    │   └─ Return for re-QA
    │
    ├─ Re-QA results
    │   ├─ PASSED/WARNING → Proceed
    │   └─ Still BLOCKER → Revision Attempt 2
    │
    ├─ Revision Attempt 2
    │   ├─ Create next versioned script (_b.py)
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
| Skill not available | Use general education-data-context |
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

| Issue | Recovery |
|-------|----------|
| Cell execution error | Fix and retry |
| Reactivity issues | Review variable dependencies |
| UI element errors | Simplify or remove interactivity |

### Stage 10 (Quality Assurance) Failures

| Issue | Recovery |
|-------|----------|
| Linting errors | Auto-fix if possible |
| Test failures | Investigate root cause |
| Persistent failures | Escalate after 2 attempts |

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
Task({
    description: "Stage [N] Re-run: [Name]",
    prompt: """Previous execution encountered issues.

**ISSUE:** [what went wrong]
**MODE:** [REFRESH | ADDITIVE]

**CORRECTIVE CONTEXT:**
[What to do differently]

[If ADDITIVE: Prior findings to preserve: ...]

Re-execute the stage with this correction.

[Original stage specification]""",
    subagent_type: "..."
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
