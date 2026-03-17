# Boundaries Reference

This document defines what the agent should Always Do, must Ask First about, and should Never Do.

---

## Always Do

These actions are **mandatory** for every analysis task.

### Data Integrity

| Action | Rationale |
|--------|-----------|
| Validate data at every checkpoint (CP1-CP4) | Catch errors early |
| Filter coded missing values (per domain config; e.g., -1, -2, -3 for education) before analysis | Prevent calculation errors |
| Document suppression rates and limitations | Ensure transparency |
| Save parquet for all data files | Parquet for processing |
| Check for unexpected nulls after transformations | Catch data corruption |
| Verify row counts before and after joins | Detect fan-out or data loss |

### Process

| Action | Rationale |
|--------|-----------|
| Classify engagement mode before executing | Set correct expectations |
| Create Plan document before data acquisition | Establish shared context |
| Complete Final Review (Stage 12) before delivery | Ensure quality and alignment |
| Update Plan with all decisions and deviations | Maintain audit trail |
| Update Risk Register when risks are discovered | Capture issues affecting analysis validity |
| Report progress adaptively (after phases, notable events) | Keep user informed |
| Escalate immediately when data is unavailable | Per design decision |

### Code Quality

| Action | Rationale |
|--------|-----------|
| Include validation assertions in notebooks | Self-documenting quality |
| Document every transformation with comments | Reproducibility |

### Documentation

| Action | Rationale |
|--------|-----------|
| Store original request verbatim in Plan | Accurate reference |
| Cite data sources properly (use domain context skill, e.g., `education-data-context`) | Academic integrity |
| Record all methodology decisions with rationale | Reproducibility |
| Version all files (never overwrite) | Audit trail |
| Include limitations section in every report | Transparency |

---

## Ask First Before

These actions require **explicit user approval** before proceeding.

### Scope Changes

| Action | Why Ask |
|--------|---------|
| Expanding analysis beyond original request scope | May exceed user expectations |
| Adding data sources not in original scope | Changes methodology |
| Changing methodology after Plan is created | Invalidates prior decisions |
| Switching engagement modes mid-execution | Changes deliverables |

### Resource-Intensive Operations

| Action | Why Ask |
|--------|---------|
| Queries that might return >100K records | Performance impact |
| Analyses spanning >10 years of data | Time and complexity |
| Operations requiring extended runtime | User may want to adjust |
| Pulling data from multiple sources requiring complex joins | Complexity risk |

### Structural Changes

| Action | Why Ask |
|--------|---------|
| Creating additional output formats beyond Plan | Scope creep |
| Modifying project folder structure | Affects organization |
| Adding dependencies not in standard toolkit | Environment impact |
| Creating files outside the project folder | Organization |

### Analysis Decisions

| Action | Why Ask |
|--------|---------|
| Choosing between multiple valid methodologies | User preference matters |
| Applying imputation for missing values | Methodological choice |
| Aggregating to higher level due to suppression | Changes granularity |
| Excluding populations or years | May affect conclusions |

---

## Never Do

These actions are **prohibited** under all circumstances.

### Data Security

| Prohibition | Consequence |
|-------------|-------------|
| Commit API keys, credentials, or tokens | Security breach |
| Store PII or sensitive data unencrypted | Privacy violation |
| Share data outside the research folder | Data governance |
| Expose raw data in public outputs | Privacy risk |

### Analysis Integrity

| Prohibition | Consequence |
|-------------|-------------|
| Violate domain governance rules (e.g., cross-state assessment comparison in education) | **NEVER valid** per domain governance |
| Skip validation checkpoints | Data quality unknown |
| Ignore LOW confidence findings without resolution | Silent failures |
| Proceed after STOP condition without user guidance | Quality compromise |
| Present suppressed data as complete | Misleading results |
| Impute without explicit documentation | Hidden assumptions |

### Process Violations

| Prohibition | Consequence |
|-------------|-------------|
| Overwrite existing version files | Loss of audit trail |
| Deliver without completing Final Review | Quality unknown |
| Execute code without understanding what it does | Risk of errors |
| Generate outputs that contradict the Plan | Inconsistent deliverables |
| Skip mode classification | Wrong deliverables |
| Create Plan before completing discovery | Incomplete context |

### Code Practices

| Prohibition | Consequence |
|-------------|-------------|
| Use bare `except:` without specific exception | Hidden errors |
| Print to stdout in production notebooks | Pollution |
| Hard-code file paths with user-specific directories | Non-portable |
| Leave debugging code in final notebooks | Unprofessional |

### File-First Execution Violations

| Prohibition | Consequence |
|-------------|-------------|
| Execute Python interactively before writing to a script file | No audit trail, not reproducible |
| Use `mcp__ide__executeCode` for analysis code (except quick exploration) | Hidden execution, no version control |
| Save scripts without embedded execution logs | Missing proof of what happened |
| Modify scripts after appending execution log (create new version instead) | Destroys audit trail |
| Create Marimo cells with code that wasn't first executed as a script | Unvalidated code in notebook |

**See:** Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

---

## Mode-Specific Boundaries

Different engagement modes have different boundary considerations. These **supplement** (not replace) the general boundaries above.

### Full Pipeline Mode

**Always Do:**
- Complete all five protocols in sequence
- Create plan file after receiving clarifications
- Complete Final Review (Stage 12) before delivery
- Generate all three deliverables (Plan, Notebook, Report)

**Never Do:**
- Skip any protocol
- Deliver without all three deliverables
- Proceed without resolving LOW confidence findings

---

### Discovery Mode, Targeted Assist Mode, Revision Mode

Mode-specific boundaries for these engagement modes are defined in their respective reference files:
- `.claude/skills/daaf-orchestrator/references/discovery-mode.md`
- `.claude/skills/daaf-orchestrator/references/targeted-assist-mode.md`
- `.claude/skills/daaf-orchestrator/references/revision-mode.md`

---

### QA-Specific Boundaries (Stages 5-8)

**Always Do:**
- Invoke code-reviewer after EVERY script execution in Stages 5-8
- Create QA scripts in `scripts/cr/` for every reviewed script
- Address BLOCKER issues via revision before proceeding
- Log WARNING issues for Stage 10 aggregation
- Preserve all script versions (failed and successful) as audit trail
- Include QA script execution log in the QA script file

**Never Do:**
- Skip QA review for "simple" scripts (all scripts get QA)
- Proceed with unresolved BLOCKER issues
- Modify scripts after QA review (create new version instead)
- Create QA-of-QA loops (QA scripts themselves don't need QA review)
- Rubber-stamp scripts that passed CP validation (QA is secondary verification)
- Allow code-reviewer to directly modify execution scripts (separation of concerns)

**Ask First Before:**
- Overriding a BLOCKER with justification (rare; should escalate instead)
- Skipping QA for an entire stage (never allowed in Full Pipeline mode)
- Changing QA script naming convention

**BLOCKER Escalation:** See `06_ERROR_RECOVERY.md` § QA BLOCKER Recovery for the full escalation flow.

---

## Autonomous Deviation Rules

When executing Plan tasks, the agent **WILL discover work not in the plan.** This is normal. Apply these rules automatically to enable efficient execution while maintaining quality. Track all deviations for documentation.

---

### RULE 1: Auto-Fix Bugs (Always Allowed)

**Trigger:** Code doesn't work as intended (broken behavior, incorrect output, errors)

**Action:** Fix immediately, document in Plan under "Deviations Applied"

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Wrong Query** | Polars filter using wrong column name, incorrect join key, filter condition inverted |
| **Logic Errors** | Off-by-one in row slicing, inverted condition (`>` vs `<`), wrong aggregation function |
| **Type Errors** | Filtering string column with integer, datetime vs string mismatch, float vs int division |
| **Validation Failures** | Assertion fails due to incorrect expected value, checkpoint logic wrong |
| **Reference Errors** | Using undefined variable, wrong DataFrame reference after transformation |
| **Data Corruption** | Mutation of source DataFrame, accidental column overwrite, incorrect in-place operation |

**Process:**
1. Fix the bug inline
2. Add/update validation to prevent regression
3. Verify fix works
4. Continue task
5. Track in deviations list: `[Rule 1 - Bug] [description]`

**Example:**
```python
# Plan specified:
df.filter(pl.col("year") == 2020)

# But year column is string type, agent auto-fixes to:
df.filter(pl.col("year") == "2020")

# Document: "[Rule 1 - Bug] Fixed type mismatch in year filter (string, not int)"
```

**No user permission needed.** Bugs must be fixed for correct operation.

---

### RULE 2: Auto-Add Missing Critical Functionality (Always Allowed)

**Trigger:** Code is missing essential features for correctness, data integrity, or basic operation

**Action:** Add immediately, document in Plan under "Deviations Applied"

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Missing Null Handling** | No check for null before division, missing `.drop_nulls()` before aggregation, no handling of `-1/-2/-3` coded values |
| **No Data Validation** | No row count check after filter, no shape validation after join, missing assertion for expected columns |
| **Missing Error Handling** | No try/except around data access calls, no handling for empty DataFrame, no timeout for large queries |
| **No Pre/Post State Capture** | Transformation without capturing row count before/after, no logging of data characteristics |
| **Missing Type Coercion** | No explicit casting before comparison, missing `.cast()` for safe operations |
| **No Bounds Checking** | No validation that percentages are 0-100, no check for negative enrollment values |

**Process:**
1. Add the missing functionality inline
2. Verify it works
3. Continue task
4. Track in deviations list: `[Rule 2 - Missing Critical] [description]`

**Example:**
```python
# Plan specified transformation, agent adds validation:
pre_rows = len(df)
df = df.filter(...)
post_rows = len(df)
assert post_rows > 0, "Filter removed all rows unexpectedly"
assert post_rows >= pre_rows * 0.1, f"Filter removed {100 - (post_rows/pre_rows)*100:.1f}% of rows"

# Document: "[Rule 2 - Missing Critical] Added row count validation after filter"
```

**Critical = required for correct/secure/reproducible operation.**
**No user permission needed.** These are not "features" - they're requirements for basic correctness.

---

### RULE 3: Auto-Fix Blocking Issues (Always Allowed)

**Trigger:** Something prevents you from completing the current task

**Action:** Fix immediately to unblock, document in Plan under "Deviations Applied"

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Missing Dependency** | `import polars` fails, missing `plotnine` package |
| **Import Errors** | Wrong import path, circular import, missing `__init__.py` |
| **Data Access Connection Issues** | Data access timeout, mirror service unavailable, mirror file path changed |
| **File Path Errors** | Parquet file not found, wrong directory structure, missing data folder |
| **Environment Issues** | Missing mirror configuration (mirrors.yaml), wrong Python version |
| **Data Format Issues** | Data file has unexpected encoding, parquet schema mismatch, date format parsing failure |

**Process:**
1. Fix the blocking issue
2. Verify task can now proceed
3. Continue task
4. Track in deviations list: `[Rule 3 - Blocking] [description]`

**Example:**
```python
# Task requires reading parquet but file path is wrong:
# Plan: df = pl.read_parquet("data/raw/ccd_schools.parquet")
# Actual structure has date prefix:
df = pl.read_parquet("data/raw/2026-01-31_ccd_schools.parquet")

# Document: "[Rule 3 - Blocking] Corrected parquet file path to include date prefix"
```

**No user permission needed.** Can't complete task without fixing blocker.

---

### RULE 4: Ask About Methodological Changes (Always Escalate)

**Trigger:** Fix/addition requires significant structural or methodological modification

**Action:** STOP, present to user, wait for decision

**Data Science Trigger Examples:**

| Category | Examples |
|----------|----------|
| **Changing Analysis Methodology** | Switching from mean to median aggregation, changing from cross-sectional to longitudinal approach |
| **Adding New Data Sources** | Incorporating additional dataset not in Plan, adding new mirror or data source |
| **Modifying Aggregation Approach** | Changing from school-level to district-level, altering grouping variables |
| **Changing Join Strategy** | Switching from inner join to left join, changing join keys |
| **Altering Population/Sample** | Excluding years not originally planned, filtering to different states |
| **Changing Model Specification** | Switching regression type, changing dependent/independent variables, altering model assumptions |
| **Switching Libraries** | Changing from Polars to pandas, switching visualization library |
| **Schema Changes** | Adding new columns to output, changing output data structure |
| **Imputation Decisions** | Deciding to impute missing values, choosing imputation method |

**Process:**
1. STOP current task
2. Document what you found, proposed change, why needed, impact, alternatives
3. Return to orchestrator/user with decision needed
4. WAIT for user decision
5. Continue with decision

**Example:**
```markdown
**STOP: Methodological Decision Required**

**What I Found:**
Inner join between CCD and MEPS loses 15% of schools (no poverty match).

**Proposed Change:**
Switch to left join and document unmatched schools.

**Why Needed:**
Current approach excludes schools we may want to analyze.

**Impact:**
- Changes row count from 85K to 100K
- Introduces null values in poverty columns for unmatched schools
- Affects downstream aggregations

**Alternatives:**
1. Keep inner join, document loss (current Plan)
2. Left join, exclude unmatched from calculations
3. Left join, impute poverty values for unmatched

**Recommendation:** Option 2 - Left join with explicit exclusion in calculations.

Awaiting your guidance before proceeding.
```

**User decision required.** These changes affect analysis methodology and conclusions.

---

### RULE 5: QA-Triggered Revisions (Always Execute)

**Trigger:** code-reviewer returns BLOCKER for non-methodology issues

**Action:** Create versioned revision, apply fix, re-execute

**QA BLOCKER Categories:**

| Category | Examples | Action |
|----------|----------|--------|
| **Correctness Issue** | Wrong join type, incorrect filter logic, type mismatch | Fix immediately via revision |
| **Validation Gap** | Missing checkpoint, inadequate invariant check | Add validation via revision |
| **Stub/Placeholder** | TODO, FIXME, pass, NotImplementedError in code | Complete implementation via revision |
| **Data Corruption** | Output has unexpected nulls, wrong row count | Fix transformation via revision |
| **Statistical Analysis Issue** | Incorrect regression specification in Stage 8 analysis, wrong model variables, invalid assumptions | Fix via revision (or escalate if methodology change needed) |
| **Methodology Violation** | Code contradicts Plan specification | STOP → Escalate to user (becomes Rule 4) |

**Process:**
1. Receive QA BLOCKER from code-reviewer
2. Check if methodology issue → If yes, escalate (Rule 4)
3. Create versioned revision file (`_a.py`, `_b.py`, etc.)
4. Apply fix as suggested by code-reviewer
5. Execute and capture output
6. Return for re-QA
7. Max 2 revision attempts; after that, escalate

**Example:**
```markdown
# QA BLOCKER: Wrong join type

## Issue
code-reviewer found: Script uses LEFT join but Plan specifies INNER join for 1:1 cardinality validation.

## Action (Rule 5)
Create revision: 01_join-data_a.py
Fix: Change join type from "left" to "inner"
Execute and capture
Return for re-QA

## Document
[Rule 5 - QA Fix] Changed join type from left to inner per Plan specification
```

**Escalation Path:**
- Attempt 1: Fix per QA suggestion → Re-QA → If still BLOCKER → Attempt 2
- Attempt 2: Different fix approach → Re-QA → If still BLOCKER → STOP, escalate to user

**No user permission needed** for non-methodology BLOCKER fixes. These are correctness issues.

---

### Rule Priority Order

When multiple rules could apply, use this priority:

1. **If Rule 4 applies** → STOP and escalate (methodological decision)
2. **If Rule 5 applies (QA BLOCKER)** → Fix via revision, re-QA (unless methodology issue → Rule 4)
3. **If Rules 1-3 apply** → Fix automatically, document
4. **If genuinely unsure which rule** → Apply Rule 4 (escalate for decision)

**Edge Case Guidance:**

| Scenario | Rule | Rationale |
|----------|------|-----------|
| "Filter crashes on null column" | Rule 1 (Bug) | Code doesn't work |
| "No validation after filter" | Rule 2 (Missing Critical) | Essential for correctness |
| "Need to add missing import" | Rule 3 (Blocking) | Can't proceed without it |
| "Need to add new column from different source" | Rule 4 (Methodology) | Changes analysis scope |
| "This validation is wrong" | Rule 1 (Bug) | Incorrect behavior |
| "No null check before division" | Rule 2 (Missing Critical) | Required for safety |
| "Should switch to left join" | Rule 4 (Methodology) | Affects results |

**Decision Heuristic:** Ask yourself "Does this affect correctness, data integrity, or ability to complete task?"
- **YES (local fix)** → Rules 1-3 (fix automatically)
- **YES (structural change)** → Rule 4 (escalate for user decision)
- **MAYBE** → Rule 4 (escalate to be safe)

---

### Escalation Threshold: System Design Impact

The key principle for deciding whether to auto-fix or escalate is **system design impact**, not complexity.

**Auto-fix (Rules 1-3) when impact is:**
- Single function/file scope
- No methodology changes
- No changes to data sources
- No changes to aggregation level
- No changes to population/sample
- Behavior change is localized

**Escalate (Rule 4) when impact is:**
- New data sources or endpoints
- Different aggregation approach
- Changed join strategy affecting results
- Population or year exclusions
- Library or framework switches
- Changes affecting analysis conclusions
- Methodology changes

**Quick Test:** "Would this change require updating the Plan's methodology section?" If yes → escalate.

---

### What ALWAYS Requires User Approval

These actions can NEVER be taken autonomously, regardless of perceived benefit:

| Action | Why Approval Required |
|--------|----------------------|
| Scope expansion beyond Plan | Changes deliverables |
| Additional data sources | Affects methodology and timeline |
| Methodology changes | Invalidates prior decisions |
| Removing validation steps | Reduces quality assurance |
| Skipping checkpoints | Violates protocol |
| Changing output formats | Affects stakeholder expectations |
| Aggregating to different level | Changes analysis granularity |
| Excluding populations or years | Affects conclusions |

---

### Deviation Documentation Format

All deviations must be documented in the Plan's "Deviations from Plan" section:

```markdown
## Deviations from Plan

| Deviation | Rule | Stage | Impact | Notes |
|-----------|------|-------|--------|-------|
| Fixed type mismatch in year filter | Rule 1 (Bug) | 7 | None | year column was string, not int |
| Added null check before division | Rule 2 (Missing Critical) | 7 | None | Prevents divide-by-zero |
| Corrected parquet file path | Rule 3 (Blocking) | 5 | None | Path needed date prefix |
```

---

### Deviation Decision Tree

```
Is this a bug fix (code doesn't work as intended)?
├─ YES → RULE 1: Fix immediately, document
└─ NO → Continue

Does this add validation, error handling, or data safety checks?
├─ YES → RULE 2: Add immediately, document
└─ NO → Continue

Is this fixing something that blocks task completion?
├─ YES → RULE 3: Fix immediately, document
└─ NO → Continue

Does this change methodology, data sources, or analysis approach?
├─ YES → RULE 4: STOP, escalate for user decision
└─ NO → Continue

Is this an improvement or optimization not required for correctness?
├─ YES → Track for "Future Improvements", do NOT implement
└─ NO → Ask: Is this necessary for task completion?
    ├─ YES → Likely Rule 3 or 4, re-evaluate
    └─ NO → Skip entirely
```

---

## Git Commit Protocol

**Philosophy:** Commit outcomes, not process. Git log should read as a changelog of shipped work.

### Commit Timing

| Event | Commit? | Notes |
|-------|---------|-------|
| Task completion (CP passed) | Yes | Atomic commit per task |
| Wave completion | Optional | Metadata update commit |
| Stage completion | Yes | Summary commit if multiple tasks |
| Plan update | Yes | Document changes |
| Bug fix during execution | Yes | Separate fix commit |

### Commit Message Format

```
{type}({stage}-{task}): {description}

- Validation: {CP status}
- Rows: {count}
- Files: {file list}

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New data acquisition, transformation | `feat(05-01): Fetch CCD enrollment data` |
| `fix` | Bug fixes, data corrections | `fix(07-02): Handle negative values in join` |
| `chore` | Metadata, Plan updates | `chore(wave-1): Update transformation log` |
| `test` | Test additions | `test(10-01): Add enrollment validation tests` |
| `docs` | Report, documentation | `docs(11-01): Generate stakeholder report` |

### Per-Task Commit Examples

**Data Fetch (Stage 5):**
```
feat(05-01): Fetch CCD school enrollment data

- Validation: CP1 PASSED
- Rows: 98,234
- Files: data/raw/2026-01-31_ccd_schools.parquet

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Data Cleaning (Stage 6):**
```
feat(06-01): Clean CCD data, filter coded values

- Validation: CP2 PASSED
- Rows: 94,102 (4% removed)
- Suppression rate: 12%
- Files: data/processed/2026-01-31_ccd_clean.parquet

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Transformation (Stage 7):**
```
feat(07-02): Join CCD schools with MEPS poverty data

- Validation: CP3 PASSED (join validation)
- Rows: 91,847 (1:1 cardinality confirmed)
- Files: data/processed/2026-01-31_analysis.parquet

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Bug Fix During Execution:**
```
fix(07-02): Correct type mismatch in year filter

- Issue: Year column was string, filter used integer
- Resolution: Changed filter to use string comparison
- Rows affected: All (was filtering to 0)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Wave Completion Commit

After all tasks in a wave complete, optionally commit metadata:

```
chore(wave-2): Complete data cleaning phase

Completed tasks:
- clean-ccd: 94,102 rows (CP2 PASSED)
- clean-meps: 97,503 rows (CP2 PASSED)

Updated: Plan.md transformation log

Co-Authored-By: Claude <noreply@anthropic.com>
```

### What NOT to Commit

| Don't Commit | Reason |
|--------------|--------|
| Mid-task work | Incomplete state |
| Failed validation | Not shippable |
| Debug attempts | Process noise |
| Temporary files | Not deliverables |

### Commit Safety Rules

- **NEVER** use `--amend` after hook failures (creates new commit instead)
- **NEVER** use `--force` push to main/master
- **NEVER** skip hooks with `--no-verify`
- **ALWAYS** stage specific files (not `git add -A`)
- **ALWAYS** review diff before committing

---

## STOP Conditions

These conditions trigger an immediate STOP with escalation to user.

### Automatic STOP Triggers

| Condition | Stage | Response |
|-----------|-------|----------|
| Data access mirror returns empty data | Stage 5 | STOP, report to user, await guidance |
| Suppression rate >50% | Stage 6 | STOP, report issue, propose alternatives |
| Domain governance rule violated (e.g., cross-state assessment comparison in education) | Stage 6 | BLOCK with explanation (never valid per domain governance) |
| Row count drops >90% after transformation | Stage 7 | STOP, verify transformation logic |
| **QA BLOCKER after 2 revisions** | 5-QA to 8-QA | STOP, escalate to user |
| **QA methodology violation** | 5-QA to 8-QA | STOP, escalate immediately |
| Notebook execution error after 2 fix attempts | Stage 9 | STOP, report error details |
| Data unavailable in Education Data Portal | Stage 2-3 | STOP, escalate immediately |
| LOW confidence finding unresolved | Any | Cannot proceed |

### STOP Message Format

See `06_ERROR_RECOVERY.md` "Escalation Format" for the authoritative STOP/escalation message template.

---

## Boundary Violations

### If You Catch Yourself Violating a Boundary

1. **STOP** the current action immediately
2. **Document** what happened
3. **Report** to user with:
   - What boundary was violated
   - What the impact might be
   - How to remediate
4. **Await** guidance before continuing

### If User Requests a Boundary Violation

Explain why the boundary exists and propose alternatives:

```markdown
**Boundary Notice**

You've requested [action], which falls under "Never Do" because [reason].

**Risk:** [What could go wrong]

**Alternatives:**
1. [Alternative approach that achieves similar goal]
2. [Modified version that stays within boundaries]

Would you like me to proceed with one of these alternatives?
```

For security-related Never Do items, do not proceed even if user insists.
