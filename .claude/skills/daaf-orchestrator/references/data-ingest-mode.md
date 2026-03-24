# Data Ingest Mode

Data Ingest mode is triggered when a user wants to profile raw data files and create a standalone data source skill. It produces a SKILL.md + reference files in `.claude/skills/` backed by a fully reproducible research project containing profiling scripts, QA reviews, and session state tracking.

## User Orientation

After mode confirmation, briefly orient the user. Key points:

- 3 phases: Setup, Profiling (4 parts of scripted analysis), Skill Creation
- 2 checkpoints where you review: after setup (to confirm scope) and after profiling (to confirm interpretations before they become part of the skill)
- You receive: a standalone data source skill ready for use in future analyses, plus a research project folder with all profiling evidence
- You need to provide: data file(s), source name, file format, and optionally any documentation and priority columns
- Key characteristic: thorough automated profiling, but you review all interpretations before they are encoded into the skill
- Typical duration: a single session for files under 500 columns; larger files may require batched profiling across sessions

**When to skip:** User has completed a data ingest before and indicates familiarity.

**For more detail:** Consult `{BASE_DIR}/user_reference/04_extending_daaf.md`.

---

## Data Ingest Mode Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE DI-1: INTAKE & SETUP                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage DI-1: Initial Intake                                                 │
│      ├─ Collect: file path, format, source name, target skill name          │
│      ├─ Collect: domain context, documentation links, priority columns      │
│      ├─ Check for skill name conflict in .claude/skills/                     │
│      ├─ Verify file accessible and non-empty                                │
│      └─ Gate GDI-1: Required inputs collected, file accessible              │
│                          ↓                                                  │
│  Stage DI-2: Project Setup                                                  │
│      ├─ Create research project folder under research/                       │
│      ├─ Copy raw data into research project data/raw/                        │
│      ├─ Initialize STATE.md from agent_reference/STATE_TEMPLATE_INGEST.md   │
│      ├─ Initialize LEARNINGS.md                                             │
│      ├─ Copy run_with_capture.sh into project scripts/                       │
│      └─ Gate GDI-2: Project folder ready, STATE.md initialized              │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ┌──────────────────────────────────┐
            │  PSU-DI1: Setup Confirmation     │
            │  Present setup summary, profiling│
            │  plan; await user confirmation   │
            └──────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE DI-2: PROFILING & RECONCILIATION                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage DI-3: Structural Profile (Part A — scripts 01-03, sequential)        │
│      ├─ 01: Format detection, encoding validation, canonical load pattern   │
│      ├─ 02: Row/column counts, memory footprint, types, schema             │
│      ├─ 03: Per-column statistics, value distributions, patterns           │
│      ├─ Code-reviewer QA loop (QAP1)                                        │
│      ├─ UPDATE STATE.md (Per-Part Execution Cycle Step 5)                  │
│      └─ Gate GDI-3: CPP1 PASSED, QAP1 PASSED/WARNING                       │
│                          ↓                                                  │
│  Stage DI-4: Statistical Profile (Part B — scripts 04-06)                   │
│      ├─ 04: Distribution profiling (always)                                 │
│      ├─ 05: Temporal analysis (conditional — if date/time columns found)    │
│      ├─ 06: Entity coverage (conditional — if entity/geo ID found)          │
│      ├─ Code-reviewer QA loop (QAP2)                                        │
│      ├─ UPDATE STATE.md (Per-Part Execution Cycle Step 5)                  │
│      └─ Gate GDI-4: CPP2 PASSED, QAP2 PASSED/WARNING                       │
│                          ↓                                                  │
│  Stage DI-5: Relational Analysis (Part C — scripts 07-09)                   │
│      ├─ 07: Key candidate identification (always)                           │
│      ├─ 08: Correlation/dependency (conditional — if >=3 numeric cols)      │
│      ├─ 09: Completeness, coded missing values, anomaly catalog (always)    │
│      ├─ Code-reviewer QA loop (QAP3)                                        │
│      ├─ UPDATE STATE.md (Per-Part Execution Cycle Step 5)                  │
│      └─ Gate GDI-5: CPP3 PASSED, QAP3 PASSED/WARNING                       │
│                          ↓                                                  │
│  Stage DI-6: Interpretation (Part D — scripts 10-11)                        │
│      ├─ 10: Column semantic classification (always)                         │
│      ├─ 11: Documentation reconciliation (conditional — if docs provided)   │
│      ├─ Code-reviewer QA loop (QAP4)                                        │
│      ├─ UPDATE STATE.md (Per-Part Execution Cycle Step 5)                  │
│      └─ Gate GDI-6: CPP4 PASSED, QAP4 PASSED/WARNING                       │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
            ┌──────────────────────────────────┐
            │  PSU-DI2: Findings Review        │
            │  CRITICAL — user confirms or     │
            │  modifies interpretations before  │
            │  skill authoring proceeds         │
            └──────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE DI-3: SKILL AUTHORING & DELIVERY                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage DI-7: Skill Authoring                                                │
│      ├─ Synthesize profiling results + user-confirmed interpretations       │
│      ├─ Create SKILL.md using DATA_SOURCE_SKILL_TEMPLATE.md                 │
│      ├─ Create reference files in .claude/skills/{skill-name}/references/   │
│      ├─ Compliance check against template (CPP-SKILL)                       │
│      └─ Gate GDI-7: CPP-SKILL PASSED                                        │
│                          ↓                                                  │
│  Stage DI-8: Review & Delivery                                              │
│      ├─ Present skill to user for review                                    │
│      ├─ Provide registration guidance (skill-catalog.md entry)              │
│      ├─ Finalize STATE.md, LEARNINGS.md                                     │
│      └─ Gate GDI-8: User confirms skill, registration listed                │
└─────────────────────────────────────────────────────────────────────────────┘
                          ↓
                    Final Delivery
```

> **AUTHORITATIVE EXECUTION LOOP:** The Per-Part Execution Cycle referenced in each stage above (DI-3 through DI-6) is defined in full detail in the **Per-Part Execution Cycle** section below. That cycle is the MANDATORY atomic unit for all profiling work. The workflow diagram above is a visual summary; the Per-Part Execution Cycle is the binding specification.

---

## Skill Naming Convention

At Stage DI-1, the orchestrator must determine the **target skill name** — the identifier used for the skill directory and frontmatter `name` field.

### Convention: `{domain}-data-source-{acronym}`

All data source skills follow this pattern. The `{domain}` groups related sources for pattern-based discovery, and the `{acronym}` is the standard abbreviation researchers use for the source.

**Examples:** `education-data-source-ccd`, `education-data-source-ipeds`, `election-data-source-countypres`

### Naming Rules

| Rule | Correct | Incorrect | Rationale |
|------|---------|-----------|-----------|
| Use the standard acronym when one exists | `education-data-source-ccd` | `education-data-source-common-core` | Acronyms are how researchers reference sources |
| Domain prefix must match `metadata.domain` | `election-data-source-countypres` (domain: `election-data`) | `voting-data-source-countypres` | Consistency enables pattern-based discovery |
| Identify specific tables when a source has multiple | `education-data-source-ccd-schools` | `education-data-source-ccd` (if ambiguous) | Prevents conflicts when ingesting additional tables later |
| Follow frontmatter validation: lowercase, hyphens only | `education-data-source-nhgis` | `education_data_source_NHGIS` | Regex: `^[a-z0-9]+(-[a-z0-9]+)*$` |

### Orchestrator Responsibilities at DI-1

1. **If the user provides a skill name:** Validate it against the `{domain}-data-source-{acronym}` convention. If it doesn't follow the pattern, suggest a corrected version and explain the convention briefly. Accept the user's preference if they insist.
2. **If the user does not provide a skill name:** Propose one using the source name, domain context, and any acronym the user mentions. Present the proposed name for confirmation.
3. **Always check** for conflicts against existing skills in `.claude/skills/` before confirming.
4. **Record** the confirmed skill name in STATE.md's Data Source Info section.

---

## Gate Definitions

| Gate | After Stage | Criteria | STOP If |
|------|-------------|----------|---------|
| GDI-1 | DI-1 | Required inputs collected, file accessible and non-empty | File cannot be loaded, file empty, or required inputs missing |
| GDI-2 | DI-2 | Project folder created, STATE.md initialized (from `agent_reference/STATE_TEMPLATE_INGEST.md`), data staged | Folder creation fails, run_with_capture.sh missing |
| GDI-3 | DI-3 | CPP1 PASSED, QAP1 PASSED or WARNING | File >1GB without sampling plan approved by user, or critical columns entirely null |
| GDI-4 | DI-4 | CPP2 PASSED, QAP2 PASSED or WARNING | >50% of columns are entirely null |
| GDI-5 | DI-5 | CPP3 PASSED, QAP3 PASSED or WARNING | No candidate keys identifiable across any table |
| GDI-6 | DI-6 | CPP4 PASSED, QAP4 PASSED or WARNING | >50% of documented columns missing from data |
| GDI-7 | DI-7 | CPP-SKILL PASSED (template compliance verified) | Template compliance fails after 2 revision attempts |
| GDI-8 | DI-8 | User confirms skill is acceptable, registration guidance listed | N/A (user decision point) |

**Gate enforcement:** Gates GDI-1 through GDI-7 are mandatory checkpoints. If a gate's STOP condition is triggered, halt execution, present the issue to the user, and await guidance before proceeding. Update STATE.md with the gate failure and resolution.

---

## Per-Part Execution Cycle (MANDATORY)

For EACH profiling part (DI-3 through DI-6), follow this complete cycle. **Do NOT skip any step.** This is the Data Ingest equivalent of the Full Pipeline's Stage 5-8 Composite Execution Pattern.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 0: READ STATE.md                                                      │
│      ├─ Verify current position and prior part statuses                    │
│      ├─ Check Profiling Progress table — confirm prior part rows updated   │
│      ├─ Check Error Budget — confirm remaining budget > 0                  │
│      └─ Confirm no unresolved BLOCKERs from prior parts                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 1: INVOKE data-ingest subagent                                        │
│      │                                                                      │
│      │   Use the part-specific invocation template (Part A/B/C/D)          │
│      │   from the Invocation Templates section below.                      │
│      │                                                                      │
│      │   Capture from return: script paths, CPP status, part summary,      │
│      │   conditional script decisions (Part A only), learning signals.     │
│      │                                                                      │
│      └─ WAIT for data-ingest subagent to return before proceeding          │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 2: INVOKE code-reviewer (MANDATORY — DO NOT SKIP)                     │
│      │                                                                      │
│      │   Use the QA Invocation Template with part-specific values.         │
│      │                                                                      │
│      │   **Review Expectation:** code-reviewer should perform adversarial  │
│      │   analysis, not just template validation. Expect the QA report to   │
│      │   include script-specific checks and reasoning about WHY the code   │
│      │   is correct, not merely confirmation that checks passed.           │
│      │                                                                      │
│      └─ WAIT for code-reviewer to return before proceeding                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 3: EVALUATE QA severity                                               │
│      ├─ PASSED → Log to STATE.md, proceed to STEP 5                        │
│      ├─ WARNING → Log to STATE.md (for PSU-DI2 review), proceed to STEP 5 │
│      └─ BLOCKER → Go to STEP 4                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 4: REVISION FLOW (if BLOCKER)                                         │
│      ├─ Re-invoke data-ingest subagent to revise failing script(s)         │
│      ├─ Re-invoke code-reviewer on revised scripts                         │
│      ├─ If still BLOCKER → Create next revision, re-invoke code-reviewer   │
│      └─ If still BLOCKER after 2 revisions → STOP and escalate to user    │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 5: UPDATE STATE.md                                                    │
│      ├─ Profiling Progress table: update Status, CPP, QA Status for each  │
│      │   script in this part; record skip reasons in Notes column           │
│      ├─ Checkpoint Status tables: update CPP row (Primary Validation)      │
│      │   and QAP row (Secondary Validation) for this part                  │
│      ├─ QA Findings Summary: append BLOCKERs Resolved / WARNINGs Logged   │
│      │   incrementally (don't defer to DI-8)                               │
│      ├─ Error Budget Consumed: update per-part and session totals         │
│      ├─ Current Position: update Current Phase and Current Stage            │
│      ├─ Next Actions: set to upcoming part or PSU-DI2 if Part D done      │
│      ├─ Key Decisions Made: record any conditional script skip decisions   │
│      ├─ Pending Learning Signals: append any signals from subagent return  │
│      ├─ Files Created This Session: append script paths created this part  │
│      ├─ If Part D: populate Interpretation Tracking (Preliminary column)   │
│      │   from subagent return; populate Documentation Reconciliation       │
│      │   Summary from Part D discrepancy findings (if docs provided)       │
│      ├─ Verify gate criteria (CPP + QAP status) before proceeding         │
│      └─ Proceed to next part or PSU-DI2                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  STEP 0 (before each cycle): READ STATE.md                                  │
│      ├─ Verify current position and prior part statuses                    │
│      ├─ Check Error Budget — confirm remaining budget > 0                  │
│      └─ Confirm no unresolved BLOCKERs from prior parts                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CRITICAL:** Steps 0-5 form an atomic unit. Step 0 runs before each new part cycle. NEVER proceed to the next part without completing all steps. NEVER invoke a new profiling subagent without first completing QA review and STATE.md update for the previous part.

**Stage DI-7 (Skill Authoring):** Does not follow this cycle. It has its own gate (GDI-7) and updates the Skill Authoring Status section of STATE.md directly. Stage DI-8 finalizes STATE.md as described in the Output Format section.

### STATE.md Update Gates

| Event | Required STATE.md Field Updates |
|-------|--------------------------------|
| Part starts (DI-3/4/5/6) | Current Position → Current Stage, Current Phase |
| Part cycle Step 5 completes | Profiling Progress → script Status and CPP columns for each script in part |
| Conditional script skipped | Profiling Progress → Status=SKIPPED, Notes=reason; Key Decisions Made |
| CPP checkpoint passes | Checkpoint Status → Primary Validation (CPP row for this part) |
| QA completes (QAP1-4) | Checkpoint Status → Secondary Validation (QAP row); QA Findings Summary |
| QA BLOCKER encountered | QA Blockers (Pending Resolution) table; Error Budget Consumed |
| QA BLOCKER resolved via revision | QA Blockers → Status=Resolved; Profiling Progress → Revisions column |
| Gate passes (GDI-3/4/5/6) | Current Position → Status; Next Actions |
| Gate STOP triggered | Blockers → Execution Blockers; Current Position → Status=Blocked |
| Key decision made | Key Decisions Made table |
| Context utilization >= 40% | Session Continuity → Context Snapshot |
| PSU-DI2 user response received | Interpretation Tracking table (all rows populated with user decisions) |
| Skill authoring completes (DI-7) | Skill Authoring Status table; Registration Status |
| Session break / finalization | Session Continuity → all fields; Session History |
| Learning signal received | Pending Learning Signals buffer |
| Files created | Files Created This Session table |

### Context Management

Context utilization thresholds from `CLAUDE.md` > "Context & Session Health" > "Context Quality Curve" apply to Data Ingest mode. The Per-Part Execution Cycle is the atomic unit for gating decisions.

| Utilization | Status | Data Ingest Action |
|-------------|--------|--------------------|
| **0-40%** | NOMINAL | Continue normally through profiling parts |
| **40-60%** | ELEVATED | Complete current part cycle; assess whether remaining parts are feasible in this session; update STATE.md Context Snapshot |
| **60-75%** | HIGH | Complete current part cycle at full quality; update STATE.md with restart prompt; report to user; do not start next part |
| **75%+** | CRITICAL | **Overrides atomic-unit requirement** — save STATE.md immediately (Current Position, Next Actions, Context Snapshot) and cease work; do not attempt to finish the current part cycle |

**Post-PSU-DI2 is a natural restart boundary.** If utilization is ELEVATED or higher after Part D completes, present PSU-DI2 findings, collect user decisions, populate Interpretation Tracking in STATE.md, then recommend restarting for DI-7 (skill authoring) in a fresh session.

### Post-PSU-DI2 Update Procedure

After the user responds to PSU-DI2 (confirming/rejecting/modifying interpretations), the orchestrator MUST update STATE.md before proceeding to DI-7:

1. **Interpretation Tracking table:** For each interpretation, populate User Decision (CONFIRMED/REJECTED/MODIFIED) and Final Interpretation columns from the user's response
2. **Documentation Reconciliation Summary:** If discrepancies were reported in Part D, populate the table from Part D subagent's findings
3. **Current Position:** Update to DI-7 (Skill Authoring)
4. **Next Actions:** Set to "Invoke skill authoring subagent"

This is a **mandatory gate** — DI-7 cannot be invoked until Interpretation Tracking has Final Interpretation values for all rows.

---

## Profiling Protocol

### Script Inventory

| # | Part | Script Name | Purpose | Conditional? | Script Path Pattern |
|---|-------|-------------|---------|--------------|---------------------|
| 01 | A | load-and-format | Format detection, encoding validation, canonical load pattern | No | `scripts/profile_structural/01_load-and-format.py` |
| 02 | A | structural-profile | Row/column counts, memory, types, schema | No | `scripts/profile_structural/02_structural-profile.py` |
| 03 | A | column-profile | Per-column statistics, value distributions | No | `scripts/profile_structural/03_column-profile.py` |
| 04 | B | distribution-analysis | Distribution fitting, outlier detection, multimodality | No | `scripts/profile_statistical/04_distribution-analysis.py` |
| 05 | B | temporal-coverage | Time coverage gaps, record count trends, drift | Yes: time column | `scripts/profile_statistical/05_temporal-coverage.py` |
| 06 | B | entity-coverage | Entity/geographic coverage, ID format validation | Yes: entity/geo ID | `scripts/profile_statistical/06_entity-coverage.py` |
| 07 | C | key-integrity | Uniqueness testing, composite keys, functional dependencies | No | `scripts/profile_relational/07_key-integrity.py` |
| 08 | C | correlation-dependency | Pearson/Spearman, Cramer's V, redundant column detection | Yes: >=3 numeric cols | `scripts/profile_relational/08_correlation-dependency.py` |
| 09 | C | quality-anomaly | Completeness, coded missing values, duplicates, anomaly catalog | No | `scripts/profile_relational/09_quality-anomaly.py` |
| 10 | D | semantic-interpretation | Column name/value pattern matching, data dictionary draft | No | `scripts/profile_interpretation/10_semantic-interpretation.py` |
| 11 | D | reconcile-docs | Documentation verification, discrepancy report | Yes: docs provided | `scripts/profile_interpretation/11_reconcile-docs.py` |

### Part Dependency Diagram

```
Part A: Structural Discovery            Part B: Statistical Deep Dive
  01 ──> 02 ──> 03                       04 (ALWAYS)
  (sequential — canonical load             05? (time column found)
   pattern established in 01)              06? (entity/geo ID found)
       │                                 (independent within part)
       │  Part A findings gate             │
       │  conditional decisions            │
       v                                   v
Part C: Relational Analysis             Part D: Interpretation & Reconciliation
  07 (ALWAYS)                              10 ──> 11?
  08? (>=3 numeric cols)                   (sequential — 11 verifies docs
  09 (ALWAYS)                               if provided)
  (independent within part)
```

### Conditional Execution Rules

Scripts 05, 06, 08, and 11 are conditional. The orchestrator decides at part boundaries based on Part A structural findings and intake information.

```
Script 05 (Temporal Analysis):
    Part A found date/time/year columns?
        YES → Execute script 05
        NO  → Skip; document "no temporal columns detected" in STATE.md

Script 06 (Entity Coverage):
    Part A found entity/geographic ID columns (state, county, FIPS, zip, entity ID)?
        YES → Execute script 06
        NO  → Skip; document "no entity/geographic ID columns detected" in STATE.md

Script 08 (Correlation/Dependency):
    Part A found >= 3 numeric columns?
        YES → Execute script 08
        NO  → Skip; document "fewer than 3 numeric columns — correlation analysis not applicable" in STATE.md

Script 11 (Documentation Reconciliation):
    User provided documentation at intake?
        YES → Execute script 11
        NO  → Skip; document "no documentation provided for reconciliation" in STATE.md
```

Document all skip decisions in STATE.md with the reasoning. Conditional scripts that are skipped do not affect gate passage — gates evaluate only the scripts that executed.

### Column Batching Strategy

For datasets with more than 100 columns, profiling scripts that inspect individual columns (02, 03, 04, 10) must be batched to avoid context overflow in subagent invocations.

- **Batch size:** ~50 columns per invocation
- **Batching method:** Partition the column list into groups of ~50; dispatch one subagent invocation per batch
- **Priority columns first:** If the user specified priority columns at intake, include them in the first batch
- **Merge outputs:** After all batches complete, merge per-batch outputs into a single consolidated result before proceeding to the next part
- **STATE.md tracking:** Record batch boundaries and completion status for each batch

### Multi-File Profiling

When intake includes multiple data files:

1. **Script 01** inventories all files, designates **primary** (largest/most complete) vs **auxiliary**
2. **Part A** runs on each file independently (scripts suffixed: `01a_`, `01b_`, etc.)
3. **Parts B-C** handle cross-file analysis: script 07 tests referential integrity across files, script 09 checks cross-file consistency
4. **Skill authoring subagent** synthesizes per-file and cross-file findings from all scripts

---

## Part Details

### Part A -- Structural Discovery

Scripts 01-03 establish foundational understanding. Always fully executed.

**01_load-and-format.py:** Detect file format (CSV/TSV/Parquet/Excel/JSON), validate encoding (BOM, line endings, delimiter inference), analyze character set, establish canonical `pl.read_*` call with exact parameters reused by all subsequent scripts. Outputs: detected format/encoding, canonical load statement, CPP1 results.

**02_structural-profile.py:** Extract row/column counts, estimated memory footprint (MB), column data types and order, first/last 5 rows for visual inspection, schema summary table. Outputs: shape, memory, type distribution, schema.

**03_column-profile.py:** Per-column stats: nulls, uniques, uniqueness ratio. Numerics: min/max/mean/median/std, percentiles (p5/p25/p50/p75/p95), skewness, kurtosis. Strings: min/max length, empty count, pattern detection (emails/phones/dates/IDs). Categoricals (<50 unique): top 20 value counts. Outputs: complete per-column profile, potential identifier flags (>95% unique).

#### CPP1: Post-Load Validation

Embedded in script 01.

```python
# --- CPP1: Post-Load Validation ---
assert df.shape[0] > 0, "STOP: Zero rows loaded"
assert df.shape[1] > 0, "STOP: Zero columns detected"
total_cells = df.shape[0] * df.shape[1]
total_nulls = sum(df[col].null_count() for col in df.columns)
null_rate = total_nulls / total_cells
assert null_rate < 0.5, f"STOP: Overall null rate {null_rate:.1%} exceeds 50%"
# INTENT: Warn about entirely null columns but don't stop
for col in df.columns:
    if df[col].null_count() == df.shape[0]:
        print(f"WARNING: Column '{col}' is entirely null")
if df.shape[0] < 100:
    print("WARNING: Dataset has < 100 rows — possible partial file")
print(f"CPP1 PASSED: {df.shape[0]} rows, {df.shape[1]} columns, {null_rate:.1%} null rate")
```

#### QAP1: Post-Structural QA

| Check | Validates | BLOCKER If |
|-------|-----------|------------|
| Re-load verification | Load with alternative params produces same result | Row/column counts differ |
| Sample row spot-check | Random rows match raw file inspection | Values corrupted |
| Encoding verification | No mojibake or replacement characters | Non-ASCII corrupted |
| Schema stability | Re-running type inference produces same types | Types change between runs |
| Column coverage | Every column appears in profile output | Column missing from profile |

**QA Script Path:** `scripts/cr/profile_structural_cr1.py`

### Part B -- Statistical Deep Dive

Scripts 04-06 analyze distributions, temporal patterns, and entity coverage. Independent within part. Scripts 05 and 06 are conditional.

**04_distribution-analysis.py (ALWAYS):** Distribution fitting per numeric column, multimodality detection (histogram gap analysis), outlier ID via IQR (1.5x/3x) and z-score (|z|>3), skewness/kurtosis interpretation, heavy-tail flagging. Outputs: distribution classifications, outlier counts/percentages, multimodality flags.

**05_temporal-coverage.py (CONDITIONAL: time column):** Year/period coverage gaps, record count trends over time, value drift across periods, panel completeness (entity-time matrix), structural break detection. Outputs: coverage listing, trend analysis, completeness matrix, break flags.

**06_entity-coverage.py (CONDITIONAL: entity/geo ID):** Coverage completeness vs known universe, identifier format validation (FIPS padding, ISO codes), geographic anomaly catalog, entity appearance frequency distribution. Outputs: completeness ratio, format validation results, anomaly catalog.

#### CPP2: Post-Statistical Validation

Embedded in the last executed script of Part B.

```python
# --- CPP2: Post-Statistical Validation ---
# INTENT: Verify numeric summary statistics are internally consistent
for col in numeric_columns:
    col_min = df[col].min()
    col_max = df[col].max()
    col_mean = df[col].mean()
    # REASONING: Mean must fall within [min, max] for any valid distribution
    assert col_min <= col_mean <= col_max, (
        f"STOP: Mean for '{col}' ({col_mean}) outside [{col_min}, {col_max}]"
    )
    # REASONING: Percentiles must be monotonically non-decreasing
    p25 = df[col].quantile(0.25)
    p50 = df[col].quantile(0.50)
    p75 = df[col].quantile(0.75)
    assert p25 <= p50 <= p75, (
        f"STOP: Percentile monotonicity violated for '{col}': p25={p25}, p50={p50}, p75={p75}"
    )
# INTENT: Verify temporal script found time columns if dataset is temporal
# ASSUMES: Orchestrator marked dataset as temporal based on Part A findings
if temporal_expected and not time_columns_found:
    print("WARNING: Dataset expected to have temporal columns but none identified")
print("CPP2 PASSED: Statistical summaries internally consistent")
```

#### QAP2: Post-Statistical QA

| Check | Validates | BLOCKER If |
|-------|-----------|------------|
| Independent stat verification | Recompute mean/median for random columns | Independently computed stat differs |
| Distribution label accuracy | Distribution claims pass appropriate tests | "Normal" claim fails normality test at p < 0.01 |
| Outlier boundary reasonableness | IQR fences are sensible | Fences exclude >20% of data without explanation |
| Temporal break detection | Obvious structural breaks are flagged | Dramatic year-to-year changes missed |
| Coverage completeness | Entity/geographic coverage is assessed | Known universe not checked when identifiers present |

**QA Script Path:** `scripts/cr/profile_statistical_cr1.py`

### Part C -- Relational Analysis

Scripts 07-09 examine inter-column relationships. Independent within part. Script 08 is conditional.

**07_key-integrity.py (ALWAYS):** Single-column uniqueness for all columns, composite key combinatorial testing (pairs/triples), functional dependency detection, near-duplicate keys (edit distance for strings), multi-file referential integrity. Outputs: uniqueness results, composite key candidates, dependency map, recommended primary key.

**08_correlation-dependency.py (CONDITIONAL: >=3 numeric):** Pearson/Spearman correlation matrices, Cramer's V for categoricals, high-correlation flagging (|r|>0.8), redundant column detection (|r|>0.95), conditional distributions across categorical groups. Outputs: correlation matrices, redundancy candidates, conditional summaries.

**09_quality-anomaly.py (ALWAYS):** Completeness summary, coded missing value scan (negatives: -1,-2,-3,-9,-99,-999; strings: "NA","N/A","Missing","","Unknown","."; high sentinels: 999,9999), exact/near duplicate rows, cross-column consistency rules, anomaly catalog with BLOCKER/WARNING/INFO severity. Outputs: completeness table, sentinel scan results, duplicate counts, anomaly catalog.

#### CPP3: Post-Relational Validation

Embedded in the last executed script of Part C.

```python
# --- CPP3: Post-Relational Validation ---
# INTENT: Verify correlation matrix is symmetric (basic sanity)
if correlation_matrix is not None:
    import numpy as np
    assert np.allclose(correlation_matrix, correlation_matrix.T, atol=1e-10), (
        "STOP: Correlation matrix is not symmetric"
    )
# INTENT: Verify uniqueness counts agree with n_unique
for col in key_candidates:
    reported_unique = uniqueness_results[col]
    actual_unique = df[col].n_unique()
    assert reported_unique == actual_unique, (
        f"STOP: Uniqueness count mismatch for '{col}': reported {reported_unique}, actual {actual_unique}"
    )
# INTENT: Anomaly catalog must be non-empty (at minimum INFO-level observations)
assert len(anomaly_catalog) > 0, (
    "STOP: Anomaly catalog is empty — quality analysis must produce at least one observation"
)
print(f"CPP3 PASSED: Relational checks consistent, {len(anomaly_catalog)} anomalies cataloged")
```

#### QAP3: Post-Relational QA

| Check | Validates | BLOCKER If |
|-------|-----------|------------|
| Key uniqueness counter-check | Claimed keys tested independently | Claimed unique key has duplicates |
| Dependency verification | Functional dependencies are real | Counter-examples exist for claimed A->B dependency |
| Anomaly catalog completeness | All major anomalies found | Known pattern (duplicates, coded values) present but uncatalogued |
| Cross-column consistency | Consistency rules are complete | Obvious logical constraint violated but not flagged |
| Coded value scan completeness | Standard sentinels checked | Numeric columns not scanned for -1, -2, -3, -9, -99, -999 |

**QA Script Path:** `scripts/cr/profile_relational_cr1.py`

### Part D -- Interpretation & Reconciliation

Scripts 10-11 produce interpretations and reconciliation. Sequential: 10 before 11 (if applicable).

**10_semantic-interpretation.py (ALWAYS):** Column name pattern matching (FIPS->geo, _id->identifier, _pct->percentage, _dt->temporal, _cd->categorical), value patterns (binary 0/1, year-like 1900-2100, percentage-like 0-100 or 0-1), domain heuristics, derived metric feasibility, join key candidates, data dictionary draft. ALL marked `[PRELIMINARY]`. Outputs: role assignments, pattern classifications, draft data dictionary.

**11_reconcile-docs.py (CONDITIONAL: docs provided):** Column existence/order/type verification against documentation, value enumeration verification, scope verification (time range, coverage, entity count), cross-document consistency, discrepancy report with BLOCKER/WARNING/INFO severity. Outputs: verification results per documented claim, discrepancy catalog.

#### CPP4: Post-Interpretation Validation

Embedded in the last executed Part D script (script 11 if docs provided, otherwise script 10).

```python
# --- CPP4: Post-Interpretation Validation ---
# INTENT: All semantic interpretations must contain [PRELIMINARY] marker
for entry in data_dictionary_draft:
    assert "[PRELIMINARY]" in entry["interpretation"], (
        f"STOP: Interpretation for '{entry['column']}' missing [PRELIMINARY] marker"
    )
# INTENT: If docs were provided, reconciliation must have run
if documentation_provided:
    assert reconciliation_ran, (
        "STOP: Documentation was provided but reconciliation script did not execute"
    )
print(f"CPP4 PASSED: {len(data_dictionary_draft)} columns interpreted, "
      f"documentation reconciliation: {'completed' if documentation_provided else 'N/A (no docs)'}")
```

#### QAP4: Post-Interpretation QA

| Check | Validates | BLOCKER If |
|-------|-----------|------------|
| PRELIMINARY marking | All interpretations hedged | Any interpretation stated as fact without [PRELIMINARY] marker |
| Documentation coverage | All documented claims checked against data | Documented column present but not reconciled |
| Discrepancy evidence | Every discrepancy has actual-vs-documented values | Discrepancy noted without showing evidence |
| Interpretation completeness | All columns with non-trivial semantics have an interpretation entry | Column with identifiable meaning has no interpretation |

**QA Script Path:** `scripts/cr/profile_interpretation_cr1.py`

---

## PSU Templates

### PSU-DI1: Setup Confirmation

Present after Stage DI-2 completes. All user-facing text uses plain language — no internal terms (gate, QA, CPP, stage DI-N).

```
**Data Ingest: Setup Complete**

**Data Source Summary:**
- File: [file name and path]
- Format: [parquet / CSV / etc.]
- Size: [file size]
- Source name: [source-name]
- Target skill: [skill-name]

**Project Folder:** [absolute path to research project]

**Profiling Plan:**
The following profiling parts will run automatically:
- Part A: Structural profiling (schema, column details, file metadata) — scripts 01-03
- Part B: Statistical profiling (distributions[, temporal analysis][, geographic analysis]) — scripts 04[-06]
- Part C: Relational analysis (key candidates[, cross-table joins], referential integrity) — scripts 07[-09]
- Part D: Interpretation (semantic classification[, documentation reconciliation]) — scripts 10[-11]

[Note which scripts are conditional and why they will/will not run based on intake info.]

**What You Receive:**
- A standalone data source skill for use in future DAAF analyses
- A research project folder with all profiling scripts, outputs, and QA reviews

**What Happens Next:**
Profiling runs through all four parts automatically. After profiling completes, you will review the findings and confirm or adjust interpretations before the skill is written.

**Does this look correct? Ready to begin profiling?**
```

### PSU-DI2: Profiling Findings Review

Present after Stage DI-6 completes. This is the CRITICAL user review point — interpretations presented here become the basis for the skill definition in Stage DI-7.

```
**Data Ingest: Profiling Complete — Review Needed**

**Quality Summary:**
[From Part A-D profiling findings — overall data quality assessment in plain language]

**Structural Findings:**
- Rows: [count]
- Columns: [count]
- Data types: [summary of type distribution]
- [Notable structural observations]

**Column Highlights:**
- Key columns: [identified primary/candidate keys]
- High-null columns: [columns with significant missingness and rates]
- Distribution notes: [notable distributions, outliers, or skew]

**Temporal Coverage:** [date range, granularity — or "N/A" if no temporal columns]

**Geographic Coverage:** [geographic levels, scope — or "N/A" if no geographic columns]

**Quality Issues:**
- Coded values: [list of columns with coded values and their mappings if identified]
- Anomalies: [unexpected patterns, potential data quality issues]
- Suppression: [any suppressed or redacted values found]

**Preliminary Interpretations:**

| # | Interpretation | Basis | Status |
|---|---------------|-------|--------|
| 1 | [e.g., "Column X appears to be a fiscal year indicator"] | [evidence from profiling] | CONFIRM / REJECT / MODIFY |
| 2 | [e.g., "Table grain is one row per school per year"] | [evidence from profiling] | CONFIRM / REJECT / MODIFY |
| ... | ... | ... | ... |

[If documentation was provided and reconciled:]
**Documentation Discrepancies:**
- [Column/field where data differs from documentation]
- [Expected vs. observed behavior]

Please review each interpretation above. For each row, indicate:
- **CONFIRM** — interpretation is correct as stated
- **REJECT** — interpretation is wrong; provide correction
- **MODIFY** — interpretation is partially correct; provide adjustment

**Are these interpretations accurate? Please confirm, reject, or modify each one.**
```

---

## Invocation Templates

Invocation templates for all profiling, QA, and skill authoring subagent calls are below.

### Part A: Structural Discovery

**Purpose:** Execute scripts 01-03  |  **Stage:** DI-3, Part A  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part A: Structural Discovery (scripts 01-03)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part A work (scripts 01-03).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.

**CONTEXT:**
- Profiling part: A
- Data file: {data_file_path}
- File format: {file_format}
- File size: {file_size}
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- run_with_capture path: {run_with_capture_path}
- Priority columns: {priority_columns_or_none}
- Documentation files: {doc_file_paths_or_none}
- Documentation website URL: {doc_url_or_none}
- Prior part findings: (none — this is Part A)
- Conditional script decisions: (determined by Part A output)

**TASK:**
1. Write and execute 01_load-and-format.py — canonical load pattern, embed CPP1
2. Write and execute 02_structural-profile.py — shape, types, memory, schema
3. Write and execute 03_column-profile.py — per-column stats, value distributions
Scripts go to: scripts/profile_structural/
Execute: bash {project_script_dir}/run_with_capture.sh {project_script_dir}/profile_structural/{script}.py

**OUTPUT FORMAT (1000-word hard cap):**
### Part A: Structural Discovery
- CPP1 Status, Rows/Columns/Memory, type summary
- Potential identifiers (>95% unique), categoricals (<50 unique)
- Coded value indicators (negative values or sentinels)
### Conditional Script Decisions
- Script 05: [EXECUTE/SKIP] -- [reason based on temporal/date columns]
- Script 06: [EXECUTE/SKIP] -- [reason based on entity/geo ID columns]
- Script 08: [EXECUTE/SKIP] -- [reason based on numeric column count]
- Script 11: [EXECUTE/SKIP] -- [reason based on documentation availability]
### Scripts Created
- [paths with execution status]
### Confidence Assessment
**Part Confidence:** [HIGH | MEDIUM | LOW]
| Aspect | Confidence | Rationale |
### Issues Requiring Attention
[BLOCKERs, WARNINGs, or "None"]
### Learning Signal
**Learning Signal:** [Category] -- [One-line insight] | "None"
### Recommendations
- **Proceed?** [YES | NO -- issues block | NO -- escalate]
- [Specific next actions] """,
    subagent_type: "data-ingest"
})
```

### Part B: Statistical Deep Dive

**Purpose:** Execute scripts 04-06  |  **Stage:** DI-4, Part B  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part B: Statistical Deep Dive (scripts 04-06)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part B work (scripts 04-06).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.

**CONTEXT:**
- Profiling part: B
- Data file: {data_file_path}
- File format: {file_format}
- Canonical load pattern: {canonical_load_from_part_a}
- Prior part findings: {part_a_summary}
- Conditional script decisions: Script 05 [{EXECUTE/SKIP}], Script 06 [{EXECUTE/SKIP}]
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- run_with_capture path: {run_with_capture_path}
- Priority columns: {priority_columns_or_none}

**TASK:**
1. Write and execute 04_distribution-analysis.py — distributions, outliers, multimodality
2. If EXECUTE: 05_temporal-coverage.py — time gaps, trends, drift
3. If EXECUTE: 06_entity-coverage.py — coverage, ID validation
4. Embed CPP2 in last executed script
Scripts go to: scripts/profile_statistical/
Execute: bash {project_script_dir}/run_with_capture.sh {project_script_dir}/profile_statistical/{script}.py

**OUTPUT FORMAT (1000-word hard cap):**
### Part B: Statistical Deep Dive
- CPP2 Status, distribution summary, outlier summary, multimodality
- Temporal/entity coverage: [executed/skipped — key findings]
### Scripts Created
### Confidence Assessment
**Part Confidence:** [HIGH | MEDIUM | LOW]
| Aspect | Confidence | Rationale |
### Issues Requiring Attention
[BLOCKERs, WARNINGs, or "None"]
### Learning Signal
**Learning Signal:** [Category] -- [One-line insight] | "None"
### Recommendations
- **Proceed?** [YES | NO -- issues block | NO -- escalate]
- [Specific next actions] """,
    subagent_type: "data-ingest"
})
```

### Part C: Relational Analysis

**Purpose:** Execute scripts 07-09  |  **Stage:** DI-5, Part C  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part C: Relational Analysis (scripts 07-09)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part C work (scripts 07-09).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.

**CONTEXT:**
- Profiling part: C
- Data file: {data_file_path}
- File format: {file_format}
- Canonical load pattern: {canonical_load_from_part_a}
- Prior part findings: {part_a_summary}, {part_b_summary}
- Conditional script decisions: Script 08 [{EXECUTE/SKIP}]
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- run_with_capture path: {run_with_capture_path}
- Priority columns: {priority_columns_or_none}

**TASK:**
1. Write and execute 07_key-integrity.py — uniqueness, composite keys, dependencies
2. If EXECUTE: 08_correlation-dependency.py — correlations, redundancy
3. Write and execute 09_quality-anomaly.py — completeness, coded values, anomaly catalog
4. Embed CPP3 in last executed script
Scripts go to: scripts/profile_relational/
Execute: bash {project_script_dir}/run_with_capture.sh {project_script_dir}/profile_relational/{script}.py

**OUTPUT FORMAT (1000-word hard cap):**
### Part C: Relational Analysis
- CPP3 Status, recommended key, dependencies, high correlations
- Coded missing values found, anomaly catalog counts, duplicate rows
### Scripts Created
### Confidence Assessment
**Part Confidence:** [HIGH | MEDIUM | LOW]
| Aspect | Confidence | Rationale |
### Issues Requiring Attention
[BLOCKERs, WARNINGs, or "None"]
### Learning Signal
**Learning Signal:** [Category] -- [One-line insight] | "None"
### Recommendations
- **Proceed?** [YES | NO -- issues block | NO -- escalate]
- [Specific next actions] """,
    subagent_type: "data-ingest"
})
```

### Part D: Interpretation & Reconciliation

**Purpose:** Execute scripts 10-11  |  **Stage:** DI-6, Part D  |  **Subagent:** data-ingest  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Part D: Interpretation & Reconciliation (scripts 10-11)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. Execute ONLY Part D work (scripts 10-11).
Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the file-first protocol.

**CONTEXT:**
- Profiling part: D
- Data file: {data_file_path}
- File format: {file_format}
- Canonical load pattern: {canonical_load_from_part_a}
- Prior part findings: {part_a_summary}, {part_b_summary}, {part_c_summary}
- Documentation files: {doc_file_paths_or_none}
- Conditional script decisions: Script 11 [{EXECUTE/SKIP}]
- Target skill name: {skill_name}
- Domain context: {domain_context}
- Intended use: {intended_use}
- Data pull date: {data_pull_date}
- Project script dir: {project_script_dir}
- run_with_capture path: {run_with_capture_path}
- Documentation website URL: {doc_url_or_none}
- Priority columns: {priority_columns_or_none}

**TASK:**
1. Write and execute 10_semantic-interpretation.py — ALL outputs marked [PRELIMINARY]
2. If EXECUTE: 11_reconcile-docs.py — verify docs against data
3. Embed CPP4 in the last executed script (script 11 if docs provided, otherwise script 10)
Scripts go to: scripts/profile_interpretation/
Execute: bash {project_script_dir}/run_with_capture.sh {project_script_dir}/profile_interpretation/{script}.py

**OUTPUT FORMAT (1000-word hard cap):**
### Part D: Interpretation & Reconciliation
- CPP4 Status, interpretation count
- Documentation reconciliation: [executed/skipped — discrepancy count]
### Preliminary Interpretations (top 10)
| Column | Interpretation | Confidence | Basis |
### Scripts Created
### Confidence Assessment
**Part Confidence:** [HIGH | MEDIUM | LOW]
| Aspect | Confidence | Rationale |
### Issues Requiring Attention
[BLOCKERs, WARNINGs, or "None"]
### Learning Signal
**Learning Signal:** [Category] -- [One-line insight] | "None"
### Recommendations
- **Proceed?** [YES | NO -- issues block | NO -- escalate]
- [Specific next actions] """,
    subagent_type: "data-ingest"
})
```

### QA Invocation Template

Invoked after each profiling part completes. Orchestrator substitutes part-specific values.

```python
Agent({
    description: "QA Review: Part {A/B/C/D} — {Part Name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/code-reviewer.md`. This is a Data Ingest QA review (not Full Pipeline) — there is no Plan.md. Use the context below for methodology alignment instead.

**SCRIPTS TO REVIEW:**
{list_of_script_paths_in_part}

**CPP RESULT:** {cpp_checkpoint_status_and_output}

**DATA INGEST CONTEXT:**
Task name: QAP{N} review of {part_name} profiling scripts
Domain context: {domain_context}
Research question / Intended use: {intended_use}
Data file: {data_file_path}
File format: {file_format}
Data characteristics: {row_count} rows, {col_count} columns, {file_size}
run_with_capture path: {run_with_capture_path}
Prior QA findings: {prior_qap_summary_or_none}
IAT compliance: Required per agent_reference/INLINE_AUDIT_TRAIL.md

**Note:** In Data Ingest mode, profiling scripts produce embedded output (appended to script files via run_with_capture.sh), not separate data files. QA scripts should verify the appended execution log, not look for separate output files.

**QAP FOCUS AREAS (Part {A/B/C/D}):**
{qap_focus_table_from_relevant_part_section}

**TASK:**
1. Review all executed scripts in Part {X} for correctness and completeness
2. Verify CPP{N} results are legitimate (not bypassed or incomplete)
3. Create QA scripts at: scripts/cr/profile_{part_dir}_cr1.py (+ cr2..cr5 as warranted)
4. Execute QA scripts and synthesize findings
5. Return QA report with severity classification

**OUTPUT FORMAT (1000-word hard cap):**
### QA Review: Part {X}
**QAP{N} Status:** [PASSED | ISSUES_FOUND]
**Severity:** [BLOCKER | WARNING | INFO | None]
**Scripts Reviewed / QA Scripts Created**
**Checks Performed:** [table]
**Issues Found:** BLOCKER / WARNING / INFO lists
**Recommendation:** [PROCEED | REVISION_REQUIRED | ESCALATE]""",
    subagent_type: "code-reviewer"
})
```

### Revision Invocation Template

When a code-reviewer QAP review returns a BLOCKER, the orchestrator re-invokes the data-ingest agent to create a revised script. Use this template:

**Agent:** `subagent_type: "data-ingest"`

```
**BASE_DIR:** {BASE_DIR}

Read your agent protocol at `.claude/agents/data-ingest.md`.

**TASK:** Revise a failing profiling script based on QA BLOCKER findings.

**CONTEXT:**
- Profiling part: {A/B/C/D}
- Data file: {data_file_path}
- File format: {file_format}
- Target skill name: {skill_name}
- Project script dir: {project_script_dir}
- run_with_capture path: {run_with_capture_path}
- Canonical load pattern: {canonical_load_from_part_a}

**FAILING SCRIPT:**
- Script path: {failing_script_path}
- Script version: {original or _a/_b suffix}

**QA BLOCKER DETAILS:**
{code_reviewer_blocker_findings}

**REVISION INSTRUCTIONS:**
1. Read the failing script and its appended execution log
2. Read the code-reviewer's QA script and its findings
3. Create a NEW versioned script with suffix _a (or _b if _a exists): `{failing_script_name_without_ext}_a.py`
4. Fix ONLY the issues identified in the BLOCKER findings
5. Preserve all IAT documentation from the original script
6. Execute via run_with_capture.sh
7. Verify the fix resolves the identified issues

**CONSTRAINTS:**
- Do NOT modify the original script (it is an immutable audit artifact with its execution log)
- Do NOT change the script's scope or add new functionality
- Maximum 2 revision attempts per script (_a, _b) before escalating to user
```

**Expected Output:** Same as standard part output, but focused on the revised script's status.

### Skill Authoring Invocation Template

Invoked at Stage DI-7 after PSU-DI2 user confirmation of preliminary interpretations.

**Purpose:** Author the data source skill  |  **Stage:** DI-7  |  **Subagent:** general-purpose  |  **Skills:** `data-scientist`, `skill-authoring`

```python
Agent({
    description: "Stage DI-7: Skill Authoring for {skill_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name 'skill-authoring'.
Read `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md` for the canonical 12-section order.

**PROJECT DIRECTORY:** {project_dir}

**PROJECT STATE:** {path_to_STATE_md}
Read the full STATE.md file. Key sections for skill authoring:
- **Data Source Info** — provenance, source provider, origin URL, format, domain context
- **Interpretation Tracking** — user-confirmed interpretations (use Final Interpretation column, not Preliminary)
- **Documentation Reconciliation Summary** — discrepancies between docs and data (if populated)
- **Profiling Progress** — script paths for all executed profiling scripts

**PROFILING SCRIPTS:** All executed scripts with execution logs are in `{project_dir}/scripts/`.
Read these scripts as primary sources for skill content:
- Scripts 01-03 (structural) → schema, column details, data access patterns
- Script 04 (distributions) → distribution notes, Common Pitfalls
- Scripts 05-06 (temporal/entity) → coverage scope, Common Pitfalls (if executed)
- Script 07 (key-integrity) → Key Identifiers, join keys
- Scripts 08-09 (correlation/quality) → anomaly catalog, coded values, Common Pitfalls
- Script 10 (interpretation) → Decision Trees, variable definitions
- Script 11 (reconciliation) → data-quality, discrepancies (if executed)

**TARGET SKILL:**
- Name: {skill_name}
- Location: .claude/skills/{skill_name}/SKILL.md
- Draft: {project_dir}/output/skill_draft/SKILL.md

**TASK:**
1. Read all executed profiling scripts from {project_dir}/scripts/ (check STATE.md Profiling Progress for paths)
2. Read STATE.md for provenance, user-confirmed interpretations, and reconciliation findings
3. Use user-confirmed interpretations (not preliminary) for all semantic claims
5. Author SKILL.md per canonical 12-section data source template
6. Create reference files in .claude/skills/{skill_name}/references/:
   - columns.md — full column definitions, types, null rates (from scripts 02, 03)
   - coded-values.md — all coded/sentinel value mappings (from scripts 03, 09)
   - data-quality.md — data quality observations, anomalies, doc discrepancies (from scripts 09, 11)
   - variable-definitions.md — semantic column interpretations, user-confirmed (from script 10 + PSU-DI2)
7. Run CPP-SKILL validation (checklist below)
8. Save draft to {project_dir}/output/skill_draft/ and final to .claude/skills/{skill_name}/

**CPP-SKILL VALIDATION:**
- [ ] All 12 canonical sections in correct order
- [ ] Frontmatter includes provenance dates
- [ ] Value Encodings Warning in position 4 with comparison table
- [ ] Decision Trees: at least 2
- [ ] Missing Data Codes subsection in Quick Reference
- [ ] Truth Hierarchy blockquote in Data Access
- [ ] Common Pitfalls: 3-column table with >=3 rows
- [ ] Total SKILL.md under 500 lines

**OUTPUT FORMAT (1000-word hard cap):**
### Skill Authoring: {skill_name}
- CPP-SKILL Status, line count, reference files, compliance, registration guidance""",
    subagent_type: "general-purpose"
})
```

---

## Context Completeness Checklists

### Profiling Invocation Checklist

Before dispatching a profiling subagent (Stages DI-3 through DI-6), verify:

- [ ] Script target path specified (absolute, following naming convention)
- [ ] Data file path(s) specified (absolute)
- [ ] Source name and format inlined
- [ ] Column batching boundaries specified (if >100 columns)
- [ ] Prior part outputs inlined (for Parts B-D: structural findings from Part A)
- [ ] Conditional script decisions documented with reasoning
- [ ] Priority columns from intake highlighted (if any)
- [ ] Documentation excerpts inlined (if provided and relevant to current part)
- [ ] run_with_capture.sh path specified
- [ ] IAT documentation standards referenced

### QA Invocation Checklist

Before dispatching a code-reviewer subagent (QAP1 through QAP4), verify:

- [ ] Script path specified (exact path to script being reviewed)
- [ ] Expected outputs described (what the script should produce)
- [ ] Profiling part context inlined (what this part was meant to accomplish)
- [ ] Data characteristics inlined (row count, column count, file size)
- [ ] IAT compliance expectations stated
- [ ] QA tolerance thresholds specified (BLOCKER if, WARNING if)
- [ ] Prior QA findings inlined (for QAP2-QAP4: issues from earlier parts)

### Skill Authoring Invocation Checklist

Before dispatching the skill authoring subagent (Stage DI-7), verify:

- [ ] Project directory path specified (absolute)
- [ ] STATE.md path specified (subagent reads full file)
- [ ] PSU-DI2 user review is complete (Interpretation Tracking table has Final Interpretation column populated)
- [ ] Target skill name and directory path specified
- [ ] Skill name conflict checked (no existing skill at `.claude/skills/{skill_name}/`)

---

## Operational References

### Data Location Convention

All data for a Data Ingest project lives inside the research project folder, following the same pattern as Full Pipeline projects.

#### Project Data Structure

```
research/YYYY-MM-DD_{Source_Name}_Ingest/
├── data/
│   └── raw/                    # Original data files (immutable after drop)
│       ├── {file1}.parquet
│       └── {file2}.parquet
├── ...
```

#### Setup Protocol

1. **Stage DI-2:** Create the research project folder under `research/`
2. **Create `data/raw/`** subdirectory inside the research project
3. **Copy** user-provided data files into `data/raw/`
4. **Initialize STATE.md** from `{BASE_DIR}/agent_reference/STATE_TEMPLATE_INGEST.md` — this template has ingest-specific sections (DI-1 through DI-8 stages, Profiling Progress table, Interpretation Tracking, Skill Authoring Status) that differ from the Full Pipeline template. Populate the Data Source Info and User Request sections with intake information.
5. **Instruct user** if files need manual placement (e.g., files too large to copy, or user prefers to place them directly)

### Script-to-Skill-Template Mapping

| Script | Feeds SKILL.md Section(s) |
|--------|---------------------------|
| 01 load-and-format | Data Access (Example Fetch, load parameters) |
| 02 structural-profile | Summary, "What is [Source]?" |
| 03 column-profile | Quick Reference (Key Identifiers), Reference File Structure |
| 04 distribution-analysis | Quick Reference (distribution notes), Common Pitfalls |
| 05 temporal-coverage | "What is" (years, frequency), Common Pitfalls |
| 06 entity-coverage | "What is" (coverage scope), Decision Trees, Common Pitfalls |
| 07 key-integrity | Quick Reference (Key Identifiers), Data Access (join keys) |
| 08 correlation-dependency | Common Pitfalls (redundant columns), Decision Trees |
| 09 quality-anomaly | Value Encodings Warning, Quick Reference (Missing Data Codes), Common Pitfalls |
| 10 semantic-interpretation | Decision Trees, coded value tables |
| 11 reconcile-docs | Reference File Structure, data-quality.md |

### Profiling Script Template

```python
#!/usr/bin/env python3
"""
Script: {NN}_{name}.py
Part: {A/B/C/D} — {Part Name}
Project: {project_name}
Created: {YYYY-MM-DD}

Purpose: {brief description}
"""
import polars as pl

# --- Config ---
# INTENT: Central configuration for file paths and parameters
DATA_FILE = "{absolute_path_to_data_file}"
# ASSUMES: Canonical load pattern established by script 01

# --- Load ---
# INTENT: Load data using canonical pattern from script 01
# REASONING: Reuse exact load parameters to ensure consistency across scripts
df = pl.read_{format}(DATA_FILE, {canonical_params})
print(f"Loaded: {df.shape[0]} rows, {df.shape[1]} columns")

# --- Profile ---
# INTENT: {part-specific profiling purpose}
{profiling_logic}

# --- Validate ---
# INTENT: {CPP checkpoint if this is the last script in part}
{validation_code_if_applicable}

# --- Summary ---
# INTENT: Structured output for orchestrator consumption
print("=" * 60)
print(f"PART {part} PROFILING COMPLETE: {script_name}")
print("=" * 60)
{structured_summary_output}

# === EXECUTION LOG ===
# (Appended by run_with_capture.sh — do not edit below this line)
```

**Conventions:** Polars only (never pandas). IAT comments (INTENT:, REASONING:, ASSUMES:) on every non-trivial operation. Section separators: Config, Load, Profile, Validate, Summary. No function definitions. Canonical load pattern from script 01 reused verbatim.

### Verification Checklists

#### Part A (Structural Discovery)

- [ ] Script 01 established canonical load pattern (format, encoding, params documented)
- [ ] CPP1 PASSED with row count, column count, and null rate reported
- [ ] Script 02 produced row/column counts, memory footprint, and complete type listing
- [ ] Script 03 produced per-column stats for every column (none missing)
- [ ] Conditional script decisions documented with Part A evidence
- [ ] All scripts saved to `scripts/profile_structural/` with execution logs
- [ ] QAP1 completed (code-reviewer invoked, QA script in `scripts/cr/`)

#### Part B (Statistical Deep Dive)

- [ ] Script 04 produced distribution classification for all numeric columns
- [ ] Script 05 executed or skipped with documented rationale
- [ ] Script 06 executed or skipped with documented rationale
- [ ] CPP2 PASSED (mean within [min,max], percentile monotonicity)
- [ ] Outlier counts and thresholds documented per column
- [ ] All scripts saved to `scripts/profile_statistical/` with execution logs
- [ ] QAP2 completed

#### Part C (Relational Analysis)

- [ ] Script 07 tested single-column uniqueness for all columns
- [ ] Script 08 executed or skipped with documented rationale
- [ ] Script 09 produced anomaly catalog with severity classifications
- [ ] CPP3 PASSED (correlation symmetry, uniqueness agreement, non-empty catalog)
- [ ] Coded missing value scan covered all standard sentinels
- [ ] Recommended primary key documented with uniqueness ratio
- [ ] All scripts saved to `scripts/profile_relational/` with execution logs
- [ ] QAP3 completed

#### Part D (Interpretation & Reconciliation)

- [ ] Script 10 marked ALL interpretations with `[PRELIMINARY]`
- [ ] Script 11 executed or skipped with documented rationale
- [ ] CPP4 PASSED (PRELIMINARY markers verified, reconciliation confirmed if docs provided)
- [ ] All scripts saved to `scripts/profile_interpretation/` with execution logs
- [ ] QAP4 completed

---

## Output Format

### Final Delivery (Stage DI-8)

Present to the user after Stage DI-7 completes and the skill passes compliance:

```
**Data Ingest Complete**

**Skill Created:**
- Name: {skill-name}
- Location: {BASE_DIR}/.claude/skills/{skill-name}/
- Files: SKILL.md + [N] reference files

**Profiling Summary:**
- [Row count] rows, [column count] columns
- [Key quality findings in 2-3 bullets]
- [Temporal/geographic coverage summary if applicable]

**Registration Guidance:**
To make this skill available in future analyses:

**Registration Checklist (for your reference):**
1. Add entry to `{SKILL_REFS}/skill-catalog.md` (Skill Quick Reference table)
2. Add source to `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md` (data source explorer list)
3. Add source to `.claude/agents/source-researcher.md` (known sources for deep-dive)

**Research Project:**
- Location: [absolute path to research project folder]
- Contains: [N] profiling scripts, [N] QA reviews, STATE.md, LEARNINGS.md

**Confidence Assessment:**
- Structural profile: [HIGH/MEDIUM/LOW] — [brief rationale]
- Statistical profile: [HIGH/MEDIUM/LOW] — [brief rationale]
- Semantic interpretation: [HIGH/MEDIUM/LOW] — [brief rationale]

**Recommendations:**
- [Any follow-up actions: e.g., columns needing manual review, documentation gaps, suggested analyses]
```

---

## Boundaries

These boundaries supplement the universal safety boundaries in `CLAUDE.md`. This section is the canonical source for all Data Ingest Mode-specific boundaries.

**Always Do:**
1. Verify file accessibility and non-emptiness before starting profiling
2. Place raw data files inside the research project's `data/raw/` folder and record provenance in STATE.md's Data Source Info section
3. Run all mandatory scripts (01-04, 07, 09, 10) regardless of file characteristics
4. Apply conditional script rules strictly based on Part A findings and intake info
5. Present all interpretations to the user at PSU-DI2 and wait for confirmation
6. Use DATA_SOURCE_SKILL_TEMPLATE.md as the structural basis for all generated skills
7. Follow the Per-Part Execution Cycle for all profiling parts — STATE.md must be updated after every part per the STATE.md Update Gates table
8. Preserve the full audit trail — never modify scripts after execution log is appended

**Ask First Before:**
1. Profiling files larger than 1GB (propose sampling strategy)
2. Skipping a conditional script when the evidence is ambiguous
3. Interpreting coded values that are not self-evident
4. Creating a skill that covers multiple unrelated data sources
5. Overwriting an existing skill with the same name

**Never Do:**
1. Encode interpretations into the skill without user confirmation at PSU-DI2
2. Modify the original data files in `data/raw/`
3. Skip QA review for any profiling part
4. Create analysis scripts or run statistical models (profiling only, not analysis)
5. Register the skill in skill-catalog.md without user instruction
6. Proceed past PSU-DI2 without explicit user confirmation of interpretations

---

## Escalation Triggers

### Data Ingest to Full Pipeline

After skill creation completes (Stage DI-8), the user may want to analyze the data they just profiled. Propose escalation:

> "The data source skill is ready. Would you like to proceed with a Full Pipeline analysis using this data?"

If confirmed, load `{SKILL_REFS}/full-pipeline.md` and begin Full Pipeline mode. The newly created skill is immediately available for the pipeline's domain configuration.

### Full Pipeline Phase 1 to Data Ingest

During Full Pipeline Discovery (Stages 2-3), if a required data source has no existing skill and the user has the raw data file, propose escalation:

> "This analysis needs [source name] data, but no skill exists for it yet. You have the raw file — would you like to pause the pipeline and run Data Ingest to create the skill first?"

If confirmed, pause Full Pipeline (record state in STATE.md), switch to Data Ingest mode. After skill creation, resume Full Pipeline from the point of interruption.

### Data Discovery to Data Ingest

During Data Discovery mode, if the user has a data file but no skill exists for it, propose escalation:

> "It looks like you have a data file for [source name] but there is no skill for it yet. Would you like to switch to Data Ingest mode to profile it and create a skill?"

If confirmed, load this mode reference and begin Data Ingest. The user can return to Data Discovery afterward if needed.
