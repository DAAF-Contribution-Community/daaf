# STATE.md Template (Data Onboarding Mode)

This template defines the session state file for Data Onboarding Mode. It is a lightweight adaptation of the Full Pipeline STATE template, tailored for profiling workflows.

---

## Template

Copy this template to `STATE.md` in the project folder when starting a Data Onboarding Mode session.

```markdown
# Session State: [Source Name] Data Onboarding

**Last Updated:** [YYYY-MM-DD HH:MM]
**Session Count:** [N]

---

## Current Position

| Field | Value |
|-------|-------|
| **Project** | [Full title, e.g., "County Presidential Election Returns Onboarding"] |
| **Current Phase** | [DI-0/DI-1/DI-2/DI-3]: [Phase Name] |
| **Current Stage** | [DI-0 through DI-8]: [Stage Name] |
| **Status** | [In Progress / Blocked / Complete] |

---

## Session Metadata

> Captured at project setup for AI use disclosure (see `agent_reference/AI_DISCLOSURE_REFERENCE.md`). The orchestrator populates these fields when creating STATE.md.

| Field | Value |
|-------|-------|
| **DAAF Version (at setup)** | [Short git commit hash — from `git rev-parse --short HEAD` at project setup. Recorded once at setup; NOT refreshed to current HEAD on later sessions. A session resuming against a newer DAAF checkout should read this as the setup-time commit, not current HEAD] |
| **Session Model ID** | [Model identifier driving the orchestrator/main session at session start — record the runtime value, not this example (e.g., "claude-opus-4-8[1m]")] |
| **Subagent Model Tiers** | [Distinct specialist model IDs by tier, from agent frontmatter defaults (`model: opus` / `model: sonnet`) plus any per-dispatch overrides the orchestrator applied. Record resolved IDs where known, or the tier alias + session date otherwise — e.g., "opus tier: claude-opus-4-8[1m]; sonnet tier: claude-sonnet-4-5". See `.claude/skills/daaf-orchestrator/SKILL.md` > "Model Selection for Subagent Dispatch" and AI_DISCLOSURE_REFERENCE.md > Multi-Model Sessions.] |
| **Session Date(s)** | [Date(s) of profiling sessions — e.g., "2026-03-23"] |
| **Session Transcript(s)** | `logs/` — collected at project completion via `collect_session_logs.sh` |

---

## Checkpoint Status

### Primary Validation (CPP1-CPP4 + CPP-SKILL)

> Record the verdict **and** the counts from each checkpoint's count line. A verdict without counts cannot be distinguished later from a pass over checks that never ran.

| Checkpoint | Verdict | Passed | Warnings | Failed | Not Verified | Skipped | Timestamp | Notes |
|------------|---------|--------|----------|--------|--------------|---------|-----------|-------|
| CPP1 (Post-Load / Structural) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes; reasons for any skipped or not-verified checks] |
| CPP2 (Post-Statistical) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |
| CPP3 (Post-Relational) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |
| CPP4 (Post-Interpretation) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |
| CPP-SKILL (Post-Authoring) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |

**CPP Verdict Values** (from the `CPP{n} VALIDATION:` line in the script's execution log):
- **PENDING** — the checkpoint has not executed yet
- **PASSED** — every check ran and held; `failed`, `not verified` are both 0
- **PASSED WITH WARNINGS** — every check ran, one or more reported a non-fatal deviation; passes the gate, and the warnings carry forward to the part summary and to the findings shown to the user
- **FAILED** — one or more checks failed, **or one or more could not be verified**. A `not verified` count above zero forces FAILED regardless of the other counters: a validation gate that could not obtain its evidence has not gated. The script raises, so the part does not complete. Resolve by supplying the missing input, correcting the checkpoint configuration, or declaring the check not applicable with a written reason (which moves it to `skipped`) — see `agent_reference/ERROR_RECOVERY.md` § Recovery from Different Stages (Data Onboarding)

### Secondary Validation (QAP1-QAP4)

| Checkpoint | Part | Result | Passed | Warnings | Blockers | Not Verified | Skipped | Info | Revisions | Timestamp |
|------------|------|--------|--------|----------|----------|--------------|---------|------|-----------|-----------|
| QAP1 (Post-Structural) | A | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QAP2 (Post-Statistical) | B | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QAP3 (Post-Relational) | C | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QAP4 (Post-Interpretation) | D | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |

**QAP Result Values** (from the `QAP{n} RESULT:` line in the code-reviewer's return):
- **PENDING** — QA checkpoint not yet executed for this part
- **PASSED** — every default check for this part ran on real inputs and held, with its evidence on the line; `blockers`, `warnings`, and `not verified` are all 0. PASSED does **not** mean "no BLOCKERs were raised" — a part with unverified checks is not PASSED
- **WARNING** — the part progresses, but something is on the record: a non-fatal deviation, **or a check that could not be verified** (`not verified > 0` forces at least WARNING), or a run in which zero substantive checks executed
- **BLOCKER** — a revision-required finding; routes to the revision flow and, if unresolved after 2 revisions, STOPs and escalates to the user

**Recording NOT VERIFIED and SKIPPED.** For every checkpoint with `not verified > 0`, add a line under QA Findings Summary naming each unverified check, what input was missing, and the reviewer's escalation decision (left at WARNING, or escalated to BLOCKER because the profiling protocol had promised the input). For every checkpoint with `skipped > 0`, record the declared reason per check. These are what PSU-DI2's "Checks We Could Not Complete" section is built from.

---

## Data Source Info

| Field | Value |
|-------|-------|
| **Source Name** | [e.g., "County Presidential Election Returns"] |
| **Source Provider** | [e.g., "MIT Election Data and Science Lab (MEDSL)"] |
| **Origin URL** | [URL where data was obtained, or "User-provided file"] |
| **Target Skill Name** | [e.g., "election-data-source-countypres"] |
| **Access Method** | [Local File / API] |
| **File Structure** | [SINGLE / HORIZONTAL / HIERARCHICAL] |
| **Skill Structure** | [Unified / Per-Entity] |
| **File Format** | [CSV/TSV/Parquet/Excel/JSON] |
| **File Location(s)** | `data/raw/[filename]` (inside research project); list all files if multi-file |
| **File Size** | [e.g., "8.4 MB" — combined total if multi-file] |
| **Documentation Available** | [Yes: list files / No] |
| **Data Pull Date** | [YYYY-MM-DD] |
| **Domain Context** | [e.g., "U.S. election data, county-level"] |
| **Priority Columns** | [list or "None specified"] |
| **User Notes** | [Any additional context provided by user, or "None"] |

### API Access Info (if Access Method = API)

*Omit this section entirely if Access Method = Local File.*

| Field | Value |
|-------|-------|
| **API Base URL** | [e.g., "https://dataverse.harvard.edu/api/"] |
| **API Key Env Var** | [e.g., "HARVARD_DATAVERSE_API_KEY"] |
| **API Key Status** | [Verified present / Missing — user notified] |
| **API Documentation URL** | [URL to API docs, or "None provided"] |
| **Data Persistence Preference** | [Local storage (download once) / Live query (fetch on demand)] |
| **API Complexity** | [Simple (1-3 endpoints) / Complex (many endpoints)] |
| **Separate Query Skill?** | [No (default) / Yes: skill name] |
| **Acquisition Script** | `scripts/stage5_fetch/00_api-fetch.py` |

### Multi-File Structure (if File Structure = HORIZONTAL or HIERARCHICAL)

*Omit this section entirely if File Structure = SINGLE.*

**File Inventory:**

| # | File | Entity Type | Row Count | Columns | Format | Join Key(s) | Role |
|---|------|-------------|-----------|---------|--------|-------------|------|
| 1 | [filename] | [e.g., schools] | [N or PENDING] | [N or PENDING] | [format] | [key cols] | Primary |
| 2 | [filename] | [e.g., districts] | [N or PENDING] | [N or PENDING] | [format] | [key cols] | Auxiliary |

**Concatenation Decision (HORIZONTAL only):**
| Field | Value |
|-------|-------|
| **Concatenation Approach** | [Concatenated (default) / Profiled separately] |
| **Schema Compatibility** | [PENDING / Identical / Divergent — details in Part A findings] |
| **Tracking Column** | `_source_file` (added during concatenation) |

**Entity Hierarchy (HIERARCHICAL only):**

```
[User-described hierarchy, e.g.:
States
  └─ Districts (linked by state_fips)
      └─ Schools (linked by leaid)]
```

**Linking Keys (HIERARCHICAL only):**

| Link | From File | To File | Key Column(s) | Expected Cardinality | Verified? |
|------|-----------|---------|---------------|---------------------|-----------|
| [description] | [file] | [file] | [cols] | [1:M / M:M] | [PENDING / Yes / No — issue] |

---

## Synthetic Path Tracking

*Include this section ONLY when the sensitivity gate (DI-1 intake fork) routed this onboarding to the privacy-preserving synthetic-data workflow (raw data must never enter the container). Omit entirely for conventional in-container onboarding. Stage sequence: DS-1 Script Preparation → DS-2 User Local Run → DS-3 Report Intake & Validation → DS-4 Interpretation → DS-5 Synthetic Generation & Validation → rejoin DI-7/DI-8. See the `synthetic-data-workflow` skill.*

| Field | Value |
|-------|-------|
| **Sensitivity Gate Outcome** | [Synthetic path chosen — reason: sensitive/PII/proprietary/enclave/"can't leave environment" / Conventional (this section omitted)] |
| **Disclosure Tier** | [T1 Schema / T2 Marginals (default) / T3 Relationships / T4 Local high-fidelity synthesis — confirmed at PSU-DS1; DS-3 copies the level number into CPS-INTAKE's `tier` — at T4, DS-3 copies the **T4 Companion Profile Tier** below instead, because CPS-INTAKE accepts only 1–3] |
| **Suppression Threshold** | [default 5 / user-set value — small cells below this are suppressed; the value the researcher approved at PSU-DS1. DS-3 copies it into CPS-INTAKE's `expected_threshold`. A returned report must declare a threshold ≥ this value. Never lower it to match a report] |
| **Relationship Spec (T3 only)** | [correlation matrices / named outcome~predictor summaries / cross-tabs requested — or "N/A (< T3)"] |
| **Profiling Script Version Handed Off** | [asset configured for the user, e.g., `profile_data_template.R` → handed-off filename + tier config; or PENDING] |
| **Wait-State Status** | [DS-1 in prep / Awaiting user local run (DS-2) / Report received (DS-3) / Past intake] |
| **Report Path** | [path to returned JSON profile report once imported, e.g., `data/profile_report/[filename].json`; or PENDING] |
| **Generation Seed** | [seed recorded for reproducibility once DS-5 runs (T4: the seed from the user's generation log); or PENDING] |
| **T4 Local-Synthesis Variant?** | [No / Yes — user ran `synthesize_local_template.*` locally; only synthetic rows crossed the boundary] |
| **T4 Companion Profile Tier** | [N/A (tier < 4, or no companion profile report) / T1 / T2 / T3 — the tier the researcher approved for the companion profiler run at T4. DS-3 copies this level number, not 4, into CPS-INTAKE's `tier` (CPS-INTAKE accepts only 1–3). A companion report whose `settings.tier` exceeds it fails CPS-INTAKE. Never raise it to match a report] |
| **T4 Missing-Seed Exception** | [N/A (seed recorded, or tier < 4) / Authorized by the researcher on [date] — [their words, or a pointer to them]; artifact labeled "non-reproducible T4 synthetic artifact". Written before the DS-5 import script runs: CPS-GEN's `seed_exception` points here, and an authorization not recorded here does not exist. Never set by the orchestrator on its own initiative] |
| **Synthetic Data Directory** | `data/synthetic/` (generated parquet; populated at DS-5) |

### Synthetic QA Status (QAS-A/B/C, CPS-INTAKE, CPS-GEN)

*The synthetic-path QA model replaces the standard recompute-against-source QA (impossible here — the real data never enters the container) with three review checkpoints (QAS-A/B/C) and two script-halting validators (CPS-INTAKE at DS-3, CPS-GEN at DS-5). Check definitions: `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints (QAS-A, QAS-B, QAS-C) and `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints. Record the verdict **and** the counts on every row — a verdict without counts cannot later be distinguished from a verdict over checks that never ran. `PENDING` is the pre-run value. The single exception is the CPS-GEN row's `EXEMPT (T4, no profile report)`, which records its reason in place of counts (see the note below the table).*

| Check | What It Verifies | Stage | Status | Counts |
|-------|------------------|-------|--------|--------|
| **QAS-A** | Disclosure-safety review of the OUTBOUND profiling script (does it emit anything the chosen tier forbids?) — highest-stakes; a leak is irreversible once the report is shared | DS-1 (before user runs it) | [PENDING/PASSED/BLOCKER] | [n] passed / [n] warnings / [n] blockers / [n] not verified / [n] skipped / [n] info |
| **CPS-INTAKE** | In-script intake validation of the RETURNED report (parses, required keys, monotone percentiles, counts ≤ row count, missingness in [0,1], well-formed correlations, no released count below threshold, embedded validation complete, no raw-value-shaped fields, identifier columns value-free, cross-tab schema/suppression) | DS-3 (script) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] passed / [n] warnings / [n] failed / [n] not verified / [n] skipped |
| **QAS-B** | Independent review of the RETURNED report and of the CPS-INTAKE script — re-derives the report's own numbers rather than trusting its embedded `all_passed` | DS-3 (review) | [PENDING/PASSED/WARNING/BLOCKER] | [n] passed / [n] warnings / [n] blockers / [n] not verified / [n] skipped / [n] info |
| **CPS-GEN** | In-script validation of GENERATED data against the profile (row count, column set/dtypes, marginals & correlations within tolerance, suppressed categories absent, synthetic levels within released levels, identifier columns value-free, missingness within tolerance, seed recorded) | DS-5 (script) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED/EXEMPT (T4, no profile report)] | [n] passed / [n] warnings / [n] failed / [n] not verified / [n] skipped — or, when EXEMPT, the reason |
| **QAS-C** | Independent synthetic-vs-profile review of the generated data and of the CPS-GEN script | DS-5 (review) | [PENDING/PASSED/WARNING/BLOCKER] | [n] passed / [n] warnings / [n] blockers / [n] not verified / [n] skipped / [n] info |

> **QAS-A is a BLOCKER gate, never a WARNING** — do not hand the profiling script to the user until disclosure-safety review passes, and any NOT VERIFIED item in QAS-A is a BLOCKER (an emission path that could not be traced is an unproven-safe path).

> **`EXEMPT (T4, no profile report)` is legal only on the CPS-GEN row, only at tier 4, and only when no profile report crossed the boundary** — CPS-GEN then has nothing to compare against and is not run, and QAS-C validates against the user's declared metadata instead. Record the reason in the Counts cell. GDS-5 accepts it under no other condition: a report present means CPS-GEN runs, and running the block with `report_path` unset is not an exemption (its NOT VERIFIED lines force FAILED). A CPS-GEN `PASSED WITH WARNINGS` whose warning is `seed_recorded` is the T4 missing-seed exception — it must match an authorization in Synthetic Path Tracking > T4 Missing-Seed Exception. See `WORKFLOW_PHASE_DO_SYNTHETIC.md` § T4 Variant.

---

## User Request

### Original Request

> [Paste the verbatim user request here]

### Clarifications Received

1. **[Topic]:** [User's response]
2. **[Topic]:** [User's response]

---

## Profiling Progress

*Tracks each profiling script's execution and QA status. Scripts marked "Conditional" may be skipped based on Part A findings.*

| # | Part | Script | Script Path | Conditional? | Status | CPP | QA Status | QA Script Path | Revisions | Notes |
|---|-------|--------|-------------|-------------|--------|-----|-----------|----------------|-----------|-------|
| 00 | DI-0 | api-fetch | `scripts/stage5_fetch/00_api-fetch.py` | Yes: API access | [PENDING/DONE/SKIPPED/N-A] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | — | — | [0-2] | Omit row if Access Method = Local File |
| 01 | A | load-and-format | `scripts/profile_structural/01_load-and-format.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PASSED/WARNING/REVISED] | `scripts/cr/profile_structural_cr1.py` | [0-2] | |
| 02 | A | structural-profile | `scripts/profile_structural/02_structural-profile.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 03 | A | column-profile | `scripts/profile_structural/03_column-profile.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 04 | B | distribution-analysis | `scripts/profile_statistical/04_distribution-analysis.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PASSED/WARNING/REVISED] | `scripts/cr/profile_statistical_cr1.py` | [0-2] | |
| 05 | B | temporal-coverage | `scripts/profile_statistical/05_temporal-coverage.py` | Yes: time column | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 06 | B | entity-coverage | `scripts/profile_statistical/06_entity-coverage.py` | Yes: entity/geo ID | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 07 | C | key-integrity | `scripts/profile_relational/07_key-integrity.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PASSED/WARNING/REVISED] | `scripts/cr/profile_relational_cr1.py` | [0-2] | |
| 07b | C | cross-level-linkage | `scripts/profile_relational/07b_cross-level-linkage.py` | Yes: HIERARCHICAL | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 08 | C | correlation-dependency | `scripts/profile_relational/08_correlation-dependency.py` | Yes: >=3 numeric cols | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 09 | C | quality-anomaly | `scripts/profile_relational/09_quality-anomaly.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |
| 10 | D | semantic-interpretation | `scripts/profile_interpretation/10_semantic-interpretation.py` | No | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PASSED/WARNING/REVISED] | `scripts/cr/profile_interpretation_cr1.py` | [0-2] | |
| 11 | D | reconcile-docs | `scripts/profile_interpretation/11_reconcile-docs.py` | Yes: docs provided | [PENDING/DONE/SKIPPED] | [—/PASSED/PASSED WITH WARNINGS/FAILED] | | | [0-2] | |

> **Note:** Script extensions are `.py` for Python projects and `.R` for R projects. QA scripts use the same extension as the execution language.

**Status Values:**
- **PENDING** — Script not yet executed
- **DONE** — Script executed successfully
- **SKIPPED** — Conditional script skipped (reason in Notes)

**QA Status Values (part-level):**
- **NOT_RUN** — Code-reviewer not yet invoked for this part
- **PASSED** — Every default check for the part ran on real inputs and held (no blockers, no warnings, nothing unverified)
- **WARNING** — Non-blocking issues logged, **or one or more checks could not be verified**; the part-level counts and the reasons live in the Secondary Validation table and QA Findings Summary
- **REVISED** — BLOCKER resolved via script revision

> The CPP column carries the script's own `CPP{n} VALIDATION:` verdict; `PASSED WITH WARNINGS` clears the gate with the warnings carried forward, and `FAILED` includes the case where a check could not be verified. The full counts belong in the Checkpoint Status tables above, not in this column.

**Note:** QA is part-level, not per-script. The QA Script Path column is populated only for the first script in each part (the QA review covers all scripts in that part together).

**Multi-file expansion (HIERARCHICAL only):** For HIERARCHICAL file structures, expand the table with per-file rows using the suffix convention. For example, with 2 files (schools + districts):
- Row `01a` for `01a_load-and-format.py` (schools), row `01b` for `01b_load-and-format.py` (districts)
- Similarly for scripts 02, 03, 04, 07, 09, 10

---

## Profiling Preliminary Notes

> Orchestrator writes lossless agent findings to disk as preliminary notes files
> immediately upon receiving each profiling agent's return. These files persist the
> full agent output (zero compression) and are referenced by subsequent profiling
> parts and the DI-7 skill authoring agent for full-fidelity access to prior
> findings. Gate conditions prevent the next part from proceeding until the
> current part's notes file exists on disk.

| Part | Agent | File Path | Status |
|------|-------|-----------|--------|
| A | data-ingest | `output/preliminary_notes/{date}_partA_structural-discovery.md` | [PENDING/WRITTEN] |
| B | data-ingest | `output/preliminary_notes/{date}_partB_statistical-deep-dive.md` | [PENDING/WRITTEN] |
| C | data-ingest | `output/preliminary_notes/{date}_partC_relational-analysis.md` | [PENDING/WRITTEN] |
| D | data-ingest | `output/preliminary_notes/{date}_partD_interpretation-reconciliation.md` | [PENDING/WRITTEN] |

**Status Values:**
- **PENDING** — Agent not yet dispatched or return not yet persisted
- **WRITTEN** — File exists on disk with full lossless agent return

**Note:** All four rows must show WRITTEN before DI-7 skill authoring can proceed.
- Script `07b` appears once (cross-file, not per-file)
- Conditional scripts (05, 06, 08) appear per-file only if applicable to that specific file
- Script 11 appears once (cross-file documentation reconciliation)

---

## Interpretation Tracking

*Tracks preliminary interpretations from Part D and user decisions at PSU-DI2.*

| Column/Feature | Preliminary Interpretation | User Decision | Final Interpretation | Notes |
|----------------|---------------------------|---------------|---------------------|-------|
| [column name] | [PRELIMINARY: interpretation from script 10] | [CONFIRMED/REJECTED/MODIFIED] | [final interpretation or "—" if rejected] | [user feedback] |
| [pattern/anomaly] | [PRELIMINARY: interpretation from script 10] | [CONFIRMED/REJECTED/MODIFIED] | [final interpretation] | [user feedback] |

**Populated:** Part D (script 10 output) → PSU-DI2 (user review) → Stage DI-7 (skill authoring uses Final Interpretation column)

---

## Documentation Reconciliation Summary

*Populated during Part D (script 11) if documentation was provided.*

| # | Discrepancy | Severity | Documented Claim | Observed Reality | Resolution |
|---|-------------|----------|------------------|------------------|------------|
| 1 | [description] | [BLOCKER/WARNING/INFO] | [what docs say] | [what data shows] | [how handled in skill] |

**Documentation Status:** [Not provided / Reconciliation complete / Reconciliation pending]

---

## Key Decisions Made

> All runtime decisions made during the onboarding session are recorded here.

| Decision | Choice | Rationale | Stage |
|----------|--------|-----------|-------|
| [Topic] | [What was decided] | [Why] | [DI-N] |
| Pre-Authoring Research offer | [Skipped / Accepted — Focused / Accepted — Deep] | [brief rationale / focus areas] | Post-PSU-DI2 |

---

## Blockers

### Execution Blockers
| Blocker | Stage | Impact | Resolution |
|---------|-------|--------|------------|
| [None or description] | [DI-N] | [effect] | [what's needed] |

### QA Blockers (Pending Resolution)
| Script | Part | Issue | Revision Attempts | Status |
|--------|------|-------|-------------------|--------|
| [None or script.py] | [A/B/C/D] | [QA finding] | [0/1/2] | [Pending/Resolved/Escalated] |

---

## Error Budget Consumed

### Per-Part (Current Part)
| Resource | Used | Limit | Remaining |
|----------|------|-------|-----------|
| Code Attempts | [X] | 2 | [Y] |
| Subagent Re-invocations | [X] | 3 | [Y] |
| **QA BLOCKER Revisions** | [X] | 2 | [Y] |

### QA Budget (Parts A-D)
| Part | Scripts | BLOCKERs Resolved | WARNINGs Logged | Escalations |
|------|---------|-------------------|-----------------|-------------|
| A (Structural) | [N] | [N] | [N] | [N] |
| B (Statistical) | [N] | [N] | [N] | [N] |
| C (Relational) | [N] | [N] | [N] | [N] |
| D (Interpretation) | [N] | [N] | [N] | [N] |

### Session Total
| Resource | Used | Limit | Remaining |
|----------|------|-------|-----------|
| Code Attempts | [X] | 6 | [Y] |
| Subagent Re-invocations | [X] | 9 | [Y] |
| **QA BLOCKER Revisions** | [X] | 8 | [Y] |
| STOP Conditions | [X] | 3 | [Y] |
| **QA Escalations** | [X] | 3 | [Y] |

**Budget Category Definitions:**
- **Code Attempts:** Script execution attempts that fail and require a new versioned script
- **Subagent Re-invocations:** Times the orchestrator must re-invoke a subagent for the same phase (includes revision requests)
- **QA BLOCKER Revisions:** Script revisions triggered by code-reviewer BLOCKER findings (max 2 per script before escalation)
- **STOP Conditions:** Data-ingest agent STOP conditions triggered (file issues, data corruption, missing keys)
- **QA Escalations:** Incremented when a QA BLOCKER remains unresolved after the maximum revision attempts (2 per script) and must be escalated to the user for resolution

> **Budget asymmetry:** Session limits are deliberately lower than per-part × 4 to prevent error concentration. A session consuming full per-part budgets in every part indicates systemic issues warranting user intervention.

> **Multi-file scaling (HIERARCHICAL only):** For HIERARCHICAL profiling with N files, per-part code attempt limits scale to 2×N (e.g., 2 files = 4 attempts per part, 3 files = 6 per part). Session limits scale proportionally but are capped at 2× the single-file session limit. If a single file consistently fails while others succeed, consider profiling it independently rather than exhausting the budget.

---

## Deviations Applied

| Deviation | Type | Stage | Notes |
|-----------|------|-------|-------|
| [None or description] | [Bug Fix/Critical Func/Test] | [DI-N] | |

---

## Runtime Risks

| Risk | Likelihood | Impact | Mitigation | Stage Discovered |
|------|------------|--------|------------|------------------|
| [None or description] | [Low/Medium/High] | [Low/Medium/High] | [Mitigation strategy] | [DI-N] |

---

## QA Findings Summary

*Aggregated after Part D completes, finalized during Stage DI-8.*

### QA Checkpoint Summary

| Checkpoint | Part | Scripts Reviewed | BLOCKERs | WARNINGs | NOT VERIFIED | SKIPPED | INFOs | Revisions Applied |
|------------|------|------------------|----------|----------|--------------|---------|-------|-------------------|
| QAP1 (Post-Structural) | A | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QAP2 (Post-Statistical) | B | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QAP3 (Post-Relational) | C | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QAP4 (Post-Interpretation) | D | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| **Total** | — | [sum] | [sum] | [sum] | [sum] | [sum] | [sum] | [sum] |

### BLOCKERs Resolved

| Part | Script | Issue | Resolution | Revision |
|------|--------|-------|------------|----------|
| [A-D] | [filename.py] | [What QA found] | [How fixed] | [_a/_b] |

### WARNINGs Logged

| Part | Script | Warning | Accepted Rationale |
|------|--------|---------|--------------------|
| [A-D] | [filename.py] | [Warning description] | [Why acceptable] |

### Checks Not Verified or Skipped

*One row per check that could not run. This table is the source for the "Checks We Could Not Complete" section presented to the user at PSU-DI2 — an empty table means every planned check ran on real data, and it should say so rather than be omitted.*

| Part | Checkpoint | Check (key) | Outcome | What Was Missing / Declared Reason | Escalation Decision |
|------|-----------|-------------|---------|-------------------------------------|---------------------|
| [A-D] | [CPP{n} / QAP{n}] | [e.g., `coverage_completeness`] | [NOT VERIFIED / SKIPPED] | [e.g., "no known universe available to compare entity coverage against"] | [Left at WARNING / Escalated to BLOCKER because … / N/A for SKIPPED] |

---

## Skill Authoring Status

| Field | Value |
|-------|-------|
| **Skill Draft Location** | `output/skill_draft/SKILL.md` |
| **Final Skill Location** | `.claude/skills/[skill-name]/SKILL.md` |
| **Template Compliance (CPP-SKILL)** | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] — record the count line alongside the verdict; a `not verified` count above zero is FAILED |
| **Reference Files Created** | [list or PENDING] |
| **Skill Line Count** | [N] (target: 200-350, hard limit: 500) |

### Discovery Status

Skills are automatically discoverable via YAML frontmatter once placed in `.claude/skills/`. No manual registration required.

---

## Pending Learning Signals

*Buffer for learning signals from subagents. Flushed to LEARNINGS.md at part boundaries and at session end.*

| Stage.Part | Category | Signal | Source Agent |
|-------------|----------|--------|-------------|
| [e.g., DI-3.A] | [Access/Data/Method/Perf/Process] | [One-line insight] | [data-ingest/code-reviewer] |

**Last Flushed:** [timestamp or "Not yet flushed"]
**Total Signals Captured (Session):** [N]
**Total Flushed to LEARNINGS.md:** [N]

---

## Next Actions

1. **Immediate:** [Next step to execute]
2. **After That:** [Following step]
3. **Pending User Input:** [If any decisions needed]

---

## Files Created This Session

| File | Type | Stage Created |
|------|------|---------------|
| [filename] | [Script/Data/Skill/etc] | [DI-N] |

---

## Session History

| Session | Date | Stages Completed | Notes |
|---------|------|------------------|-------|
| 1 | [date] | [DI-1 to DI-N] | [summary] |

---

## Session Continuity

### Last Action Completed

| Field | Value |
|-------|-------|
| **Phase** | [A/B/C/D or DI-1/DI-2/DI-7/DI-8] |
| **Script/Task** | [script name or task description] |
| **Timestamp** | [ISO 8601] |
| **Files Modified** | [list] |

### Next Action Required

| Field | Value |
|-------|-------|
| **Stage** | [DI-N] |
| **Task** | [description] |
| **Blocked By** | [None | task-name | user-decision | error] |
| **Ready to Execute** | [Yes | No - reason] |

### Context Snapshot

**Orchestrator Utilization:** [actual % from context-reporter hook]

**Key Findings Summary (max 5 bullets):**
- [Critical finding 1]
- [Critical finding 2]

**Open Questions:**
- [Question awaiting resolution, or "None"]

**Pending User Decisions:**
- [Decision needed, or "None"]

### User Restart Prompt

**To resume in a new session, run `/clear` to reset context, then paste this into the chat:**

> Resume the [Source Name] data onboarding. State: `[exact STATE.md path]`. Currently at Stage [DI-N] ([Stage Name]) — next step is [task description].

### Resumption Instructions (Agent Reference)

**For the orchestrator when recovering via Session Recovery:**

1. **Read this STATE.md first** — primary recovery document
2. **Review User Request and Data Source Info** for original scope and provenance
3. **Check Profiling Progress table** for current part and script status
4. **Check Interpretation Tracking** if past Part D (user decisions must be preserved)
5. **Current Phase:** [DI-N] — [Phase Name]
6. **Next Task:** `[task or script description]`

**Quick Resume Checklist:**
- [ ] STATE.md read and understood (position, checkpoints, blockers)
- [ ] Profiling Progress table reviewed (which scripts done/pending/skipped)
- [ ] Interpretation Tracking reviewed (if past PSU-DI2)
- [ ] User Request and Data Source Info reviewed
- [ ] Open blockers identified
- [ ] Next action ready for execution
```

---

## Usage Guidelines

### When to Create

Create STATE.md at **Stage DI-2 (Project Setup)** for all Data Onboarding Mode sessions.

### When to Update

**Authoritative cycle:** The Per-Part Execution Cycle in `data-onboarding-mode.md` defines the mandatory STATE.md read/write rhythm for profiling parts DI-3 through DI-6. The list below enumerates the specific trigger events; the STATE.md Update Gates table in `data-onboarding-mode.md` maps each event to the exact fields that must be updated.

Update STATE.md after:
- Each profiling script executes (update Profiling Progress row)
- Each part QA completes (update Checkpoint Status + QA Findings)
- PSU-DI1 presented (update Current Position)
- PSU-DI2 user response received (populate Interpretation Tracking)
- Skill authoring completes (update Skill Authoring Status)
- Key decisions are made
- Blockers are encountered
- Error budget is consumed
- Before any planned break
- Learning signals received from subagents

### Minimal Update Pattern

For quick updates during execution:

```markdown
**Last Updated:** [timestamp]
**Current Stage:** [DI-N]
**Last Script:** [script name] - [DONE/FAILED]
**Next Action:** [description]
```

### Full Update Pattern

Use full template update:
- At end of each profiling part (A, B, C, D)
- When blockers encountered
- Before session breaks
- After PSU-DI2 user review

---

## Integration with Session Recovery

STATE.md is the primary input for session recovery:

1. **Recovery starts** with reading STATE.md
2. **Profiling Progress** shows exactly which scripts completed
3. **Interpretation Tracking** preserves user decisions from PSU-DI2
4. **Next actions** provide immediate guidance
5. **Skill Authoring Status** shows whether skill creation has begun

**Reading verdicts on recovery.** A resuming session reads the Checkpoint Status tables as verdict *plus counts*, never verdict alone. A part recorded `PASSED` with a nonzero NOT VERIFIED count is a contradiction — the recorded verdict is stale or was written before this contract; re-read the part's execution log for the `CPP{n} VALIDATION:` / `QAP{n} RESULT:` line and its count line, and treat the log as authoritative. Before advancing past a gate, confirm the "Checks Not Verified or Skipped" table has an entry for every unverified or skipped check the counts imply; if the counts and that table disagree, the part's QA is unresolved and must be re-reviewed rather than assumed clean.

See `{BASE_DIR}/.claude/skills/daaf-orchestrator/references/session-recovery.md` for the complete recovery procedure.
