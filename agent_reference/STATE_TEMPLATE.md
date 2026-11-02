# STATE.md Template

This template defines the session state file used for persistent memory across context windows and session recovery.

---

## Template

Copy this template to `STATE.md` in the project folder when starting a Full Pipeline analysis.

```markdown
# Session State: [Project Title]

**Last Updated:** [YYYY-MM-DD HH:MM]
**Session Count:** [N]

---

## Current Position

| Field | Value |
|-------|-------|
| **Project** | [Full title] |
| **Plan Location** | `research/[folder]/[filename]_Plan.md` |
| **Plan Tasks Location** | `research/[folder]/[filename]_Plan_Tasks.md` |
| **Current Phase** | [1-5]: [Phase Name] |
| **Current Stage** | [1-12]: [Stage Name] |
| **Status** | [In Progress / Awaiting Confirmation / Blocked / Complete] (Awaiting Confirmation: a user checkpoint was presented and the user has not yet answered it; Next Actions > Pending User Input names it) |

---

## Session Metadata

> Captured at project setup for AI use disclosure (see `agent_reference/AI_DISCLOSURE_REFERENCE.md`). The orchestrator populates these fields when creating STATE.md; Provider Route and Model Settings are found as `AI_DISCLOSURE_REFERENCE.md` § Determining the Provider Route says.

| Field | Value |
|-------|-------|
| **DAAF Version (at setup)** | [Short git commit hash — from `git rev-parse --short HEAD` at project setup. Recorded once at setup; NOT refreshed to current HEAD on later sessions. A session resuming against a newer DAAF checkout should read this as the setup-time commit, not current HEAD] |
| **Session Model ID** | [Model identifier driving the orchestrator/main session at session start — record the runtime value, not this example (e.g., "claude-opus-4-8[1m]")] |
| **Subagent Model Tiers** | [Distinct specialist model IDs by tier, from agent frontmatter defaults (`model: opus` / `model: sonnet`) plus any per-dispatch overrides the orchestrator applied. Record resolved IDs where known, or the tier alias + session date otherwise — e.g., "opus tier: claude-opus-4-8[1m]; sonnet tier: claude-sonnet-4-5". See `.claude/skills/daaf-orchestrator/SKILL.md` > "Model Selection for Subagent Dispatch" and AI_DISCLOSURE_REFERENCE.md > Multi-Model Sessions.] |
| **Provider Route** | [Anthropic subscription / Anthropic API key / OpenAI API via DAAF provider shim / ChatGPT subscription via DAAF provider shim / OpenRouter / AWS Bedrock / Google Vertex AI] |
| **Model Settings** | [Settings that reach the model on this route, recorded with it: Anthropic routes, "reasoning effort [`effortLevel` value]"; provider-shim routes, the shim's reasoning effort per model tier and its response verbosity; other routes, "[Not recorded]". The AI disclosure's Parameters line reads this field] |
| **Execution Language** | [Python or R — from CLAUDE.md User Preferences] |
| **Session Date(s)** | [Date(s) of analysis sessions — e.g., "2026-02-11"] |
| **Session Transcript(s)** | `logs/` — collected at project completion via `collect_session_logs.sh` |

---

## Checkpoint Status

### Primary Validation (CP1-CP4)

> Record the verdict **and** the counts from each checkpoint's count line. A verdict without counts cannot be distinguished later from a pass over checks that never ran.

| Checkpoint | Verdict | Passed | Warnings | Failed | Not Verified | Skipped | Timestamp | Notes |
|------------|---------|--------|----------|--------|--------------|---------|-----------|-------|
| CP1 (Post-Fetch) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes; reasons for any skipped or not-verified checks] |
| CP2 (Post-Clean) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |
| CP3 (Post-Transform) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |
| CP4 (Post-Analysis & Viz, Stage 8) | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [n] | [n] | [n] | [n] | [n] | [time] | [notes] |

**CP Verdict Values** (from the `CP{n} VALIDATION:` line in the script's execution log):
- **PENDING** — the checkpoint has not executed yet
- **PASSED** — every check ran and held; `failed` and `not verified` are both 0
- **PASSED WITH WARNINGS** — every check ran, one or more reported a non-fatal deviation; passes the gate, maps to a reported status of `WARNING`, and is not a clean pass. The warnings carry forward to the Stage 10 QA aggregation
- **FAILED** — one or more checks failed, **or one or more could not be verified**. A `not verified` count above zero forces FAILED regardless of the other counters: a validation gate that could not obtain its evidence has not gated. The script raises, so the transformation does not complete. Resolve by supplying the missing input, correcting the checkpoint configuration, or declaring the check not applicable with a written reason (which moves it to `skipped`) — see `agent_reference/ERROR_RECOVERY.md`

### Pre-Output Verification (Stage 12)

> Recorded in its own table because its outcomes are neither the CP nor the QA enum: Pre-Output
> Verification is a data-verifier checklist over Plan commitments (`agent_reference/VALIDATION_CHECKPOINTS.md`
> § Pre-Output Verification (Stage 12)), so its four counts — verified, deviations, not verified, not
> applicable — do not fit the CP table's Passed/Warnings/Failed/Not Verified/Skipped columns. No line
> here carries a `CP4` token.

| Checkpoint | Aggregate | Verified | Deviations | Not Verified | Not Applicable | Timestamp | Notes |
|------------|-----------|----------|------------|--------------|----------------|-----------|-------|
| Pre-Output Verification (PO.1-PO.4) | [PENDING/VERIFIED/DEVIATIONS FOUND/NOT VERIFIED] | [n] | [n] | [n] | [n] | [time] | [which items deviated or could not be checked, and why] |

**Aggregate Values** (from the `PRE-OUTPUT VERIFICATION:` line in the data-verifier report):
- **PENDING** — Stage 12 verification has not run yet
- **VERIFIED** — every item was checked against its artifact and the commitment was met; `deviations` and `not verified` are both 0
- **DEVIATIONS FOUND** — every item was checked and one or more departed from the Plan. A major deviation blocks delivery; a minor one is acceptable when the Report documents it
- **NOT VERIFIED** — one or more items could not be checked (Plan section absent, artifact missing). Zero items assessed is also NOT VERIFIED — an unchecked deliverable is never a clean pass

### Secondary Validation (QA1-QA4b)

| Checkpoint | Stage | Result | Passed | Warnings | Blockers | Not Verified | Skipped | Info | Revisions | Timestamp |
|------------|-------|--------|--------|----------|----------|--------------|---------|------|-----------|-----------|
| QA1 (Post-Fetch) | 5 | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QA2 (Post-Clean) | 6 | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QA3 (Post-Transform) | 7 | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QA4a (Post-Analysis) | 8.1 | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |
| QA4b (Post-Viz: visualization scripts and analysis scripts that draw figures) | 8.1, 8.2 | [PENDING/PASSED/WARNING/BLOCKER] | [n] | [n] | [n] | [n] | [n] | [n] | [count] | [time] |

**QA Result Values** (from the `QA{n} RESULT:` line in the code-reviewer's return):
- **PENDING** — QA checkpoint not yet executed for this stage
- **PASSED** — every default check for this stage ran on real inputs and held, with its evidence on the line; `blockers`, `warnings`, and `not verified` are all 0. PASSED does **not** mean "no BLOCKERs were raised" — a stage with unverified checks is not PASSED
- **WARNING** — the stage progresses, but something is on the record: a non-fatal deviation, **or a check that could not be verified** (`not verified > 0` forces at least WARNING), or a run in which zero substantive checks executed
- **BLOCKER** — a revision-required finding. A BLOCKER whose fix brings the code back to what the Plan already specifies (a MISALIGNED row under Methodology Alignment that a revision can correct, such as a LEFT join where the Plan says INNER) goes through revision (max 2). A methodology BLOCKER — the Plan's own methodology looks wrong for the data, or the Plan does not settle the choice — is a code-reviewer STOP with Issue Category `Methodology Conflict` and escalates to the user immediately.

**Recording NOT VERIFIED and SKIPPED.** For every checkpoint with `not verified > 0`, add a row under QA Findings Summary > "Checks Not Verified or Skipped" naming each unverified check, what input was missing, and the reviewer's escalation decision (left at WARNING, or escalated to BLOCKER because the Plan had promised the input). For every checkpoint with `skipped > 0`, record the declared reason per check.

**Note:** This table provides an aggregate summary per stage. Per-script QA tracking (which gates individual script progression) is recorded in the **Transformation Progress** table below, where each row tracks one script's independent QA status.

---

## Plan Validation (Stage 4.5)

| Field | Value |
|-------|-------|
| **Plan-Checker Status** | [NOT_RUN / PASSED / PASSED_WITH_WARNINGS / ISSUES_FOUND] |
| **Run Date** | [YYYY-MM-DD HH:MM or "Not run"] |
| **Revision Attempts** | [0 / 1 / 2] |

**Warnings (if PASSED_WITH_WARNINGS):**
- [Warning 1 from plan-checker]
- [Warning 2 from plan-checker]

**Blockers (if ISSUES_FOUND and unresolved):**
- [Blocker description]

**Gate G4.5 Status:** [NOT SATISFIED / SATISFIED]

> **CRITICAL:** Gate G4.5 is SATISFIED only when both conditions hold: Plan-Checker Status is PASSED or
> PASSED_WITH_WARNINGS, **and** the user has confirmed the plan checkpoint (PSU2), recorded in Key
> Decisions Made. Stage 5 CANNOT begin until then. If this section shows NOT_RUN, invoke plan-checker
> before proceeding. Gate definition: `full-pipeline-mode.md` § Stage Gates (Cannot Proceed Without).

---

## Data Status

| Dataset | Location | Rows | Status |
|---------|----------|------|--------|
| Raw Data | `data/raw/[filename]` | [count] | [fetched/pending] |
| Processed Data | `data/processed/[filename]` | [count] | [cleaned/pending] |
| Analysis Data | `data/processed/[filename]` | [count] | [ready/pending] |

**Suppression Rate:** [X%]
**Data Lag** (one line per source, from that source's CP1 year-freshness check):
- [Source]: latest year available [YYYY]; years requested but missing [None / list of years]
**Flagged Years** (one line per source, from that source's CP1 flagged-years check against the Plan's Flag Years; the education default flags the COVID years 2020 and 2021):
- [Source]: flagged years present in the fetched data [None / list of years]

---

## Hypothesis Assessment Progress

*Track status of Plan hypotheses (if any). Skip this section if Plan has no hypotheses.*

| Hypothesis ID | Statement | Status | Assessment | Stage Assessed |
|---------------|-----------|--------|------------|----------------|
| [H1] | [statement] | [PENDING/ASSESSED] | [SUPPORTED/NOT SUPPORTED/PARTIALLY SUPPORTED] | [Stage N] |

---

## Key Decisions Made

> **Planning-phase decisions** are in Plan.md `## Decisions Log` (frozen at Stage 4.5). Record here all **runtime decisions** made during Stages 5-12, and one row per user checkpoint: the user's answer and any changes they asked for. The first checkpoint (after discovery) is confirmed before STATE.md exists: add its row when STATE.md is created at Stage 4.

| Decision | Choice | Rationale | Stage |
|----------|--------|-----------|-------|
| [Topic] | [What was decided] | [Why] | [N] |
| [Topic] | [What was decided] | [Why] | [N] |

---

## Transformation Progress

*For Stage 5-8 tracking (includes QA substages). Each row tracks ONE script with its independent QA status. A row with QA Status = NOT_RUN blocks the next wave.*

| # | Transformation | Script Path | CP Status | QA Status | QA Script Path | QA Depth | Revisions | Pre-Rows | Post-Rows | Notes |
|---|----------------|-------------|-----------|-----------|----------------|----------|-----------|----------|-----------|-------|
| 1 | Fetch CCD schools | `scripts/stage5_fetch/01_fetch-ccd.py` | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage5_01_cr1.py` | [1 of 5] | [0-2] | [N] | [N] | |
| 2 | Clean CCD schools | `scripts/stage6_clean/01_clean-ccd.py` | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage6_01_cr1.py` | [1 of 5] | [0-2] | [N] | [N] | |
| 3 | Join CCD + MEPS | `scripts/stage7_transform/01_join-data.py` | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage7_01_cr1.py` | [1 of 5] | [0-2] | [N] | [N] | |
| 4 | Regression: poverty | `scripts/stage8_analysis/01_regression-poverty.py` | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage8_01_cra1.py` | [1 of 5] | [0-2] | [N] | [N] | QA4a (statistical validity) |
| 5 | Enrollment trends plot | `scripts/stage8_analysis/02_enrollment-trends.py` | [PENDING/PASSED/PASSED WITH WARNINGS/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage8_02_crb1.py` | [1 of 5] | [0-2] | [N] | [N] | QA4b (visualization quality) |

> **Note:** Script extensions are `.py` for Python projects and `.R` for R projects. QA scripts use the same extension as the execution language. Stages 5-7 use the standard QA suffix `_cr{N}` (e.g., `stage5_01_cr1`), but **Stage 8 uses the split-QA suffix**: `_cra{N}` for QA4a (analysis/statistical review) and `_crb{N}` for QA4b (visualization review) — e.g., `stage8_01_cra1` and `stage8_02_crb1`, per `agent_reference/QA_CHECKPOINTS.md`.

**QA Status Values:**
- **NOT_RUN** — code-reviewer has not been invoked for this script (blocks the next wave)
- **PENDING** — QA review invoked but not yet completed for this script
- **PASSED** — QA review passed for this script (no issues)
- **WARNING** — QA found non-blocking issues for this script (logged for Stage 10 aggregation)
- **REVISED** — QA BLOCKER for this script resolved via revision

---

## Blockers

### Execution Blockers
| Blocker | Stage | Impact | Resolution |
|---------|-------|--------|------------|
| [None or description] | [N] | [effect] | [what's needed] |

### QA Blockers (Pending Resolution)
| Script | Stage | Issue | Revision Attempts | Status |
|--------|-------|-------|-------------------|--------|
| [None or script.py] | [N] | [QA finding] | [0/1/2] | [Pending/Resolved/Escalated] |

---

## Error Budget Consumed

### Per-Stage (Current Stage)
| Resource | Used | Limit | Remaining |
|----------|------|-------|-----------|
| Data Access Retries | [X] | 3 | [Y] |
| Code Attempts | [X] | 2 | [Y] |
| Subagent Re-invocations | [X] | 3 | [Y] |
| **QA BLOCKER Revisions** | [X] | 2 | [Y] |

### QA Budget (Stages 5-8)
| Stage | Scripts | BLOCKERs Resolved | WARNINGs Logged | Escalations |
|-------|---------|-------------------|-----------------|-------------|
| 5 (Fetch) | [N] | [N] | [N] | [N] |
| 6 (Clean) | [N] | [N] | [N] | [N] |
| 7 (Transform) | [N] | [N] | [N] | [N] |
| 8 (Analyze & Viz) | [N] | [N] | [N] | [N] |

### Session Total
| Resource | Used | Limit | Remaining |
|----------|------|-------|-----------|
| Data Access Retries | [X] | 9 | [Y] |
| Code Attempts | [X] | 6 | [Y] |
| **QA BLOCKER Revisions** | [X] | 8 | [Y] |
| **QA Methodology Issues** | [X] | 2 | [Y] |
| Subagent Re-invocations | [X] | 9 | [Y] |
| STOP Conditions | [X] | 3 | [Y] |

> Limits match `agent_reference/ERROR_RECOVERY.md` § Session Error Budget > Budget Limits, which is canonical. The orchestrator reads this section at Step 0 of each execution cycle (§ Budget Read-Gating there): a row with Remaining at 0 or below means STOP and follow the Budget Exhaustion Protocol there, not the next dispatch.

---

## Deviations Applied

| Deviation | Type | Stage | Notes |
|-----------|------|-------|-------|
| [None or description] | [Bug Fix/Critical Func/Test] | [N] | |

---

## Runtime Risks

> **Planning-phase risks** are in Plan.md `## Risk Register` (frozen at Stage 4.5). Risks discovered during execution (Stages 5-12) are recorded here.

| Risk | Likelihood | Impact | Mitigation | Stage Discovered |
|------|------------|--------|------------|------------------|
| [None or description] | [Low/Medium/High] | [Low/Medium/High] | [Mitigation strategy] | [N] |

**When to Add:**
- Stage 5: CP1 reveals unexpected data shape, data lag, or quality issues
- Stage 6: Suppression rate is 30-50% (below STOP but elevated)
- Stage 7: Unexpected row loss or cardinality violations occur
- Any stage: Data definitions changed between years, other quality issues arise

---

## QA Findings Summary

*Aggregated during Stage 10, finalized during Stage 12.*

### QA Checkpoint Summary

| Checkpoint | Stage | Scripts Reviewed | BLOCKERs | WARNINGs | NOT VERIFIED | SKIPPED | INFOs | Revisions Applied |
|------------|-------|------------------|----------|----------|--------------|---------|-------|-------------------|
| QA1 (Post-Fetch) | 5 | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QA2 (Post-Clean) | 6 | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QA3 (Post-Transform) | 7 | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QA4a (Post-Analysis) | 8.1 | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| QA4b (Post-Viz: visualization scripts and analysis scripts that draw figures) | 8.1, 8.2 | [count] | [count] | [count] | [count] | [count] | [count] | [count] |
| **Total** | — | [sum] | [sum] | [sum] | [sum] | [sum] | [sum] | [sum] |

### BLOCKERs Resolved

*Document each QA BLOCKER that was resolved via revision.*

| Stage | Script | Issue | Resolution | Revision |
|-------|--------|-------|------------|----------|
| [N] | [filename.py] | [What QA found] | [How fixed] | [_a/_b] |

### WARNINGs Logged

*Document QA WARNINGs for transparency (did not block execution).*

| Stage | Script | Warning | Accepted Rationale |
|-------|--------|---------|--------------------|
| [N] | [filename.py] | [Warning description] | [Why acceptable] |

### Checks Not Verified or Skipped

*One row per check that could not run. An empty table means every planned check ran on real data, and it should say so rather than be omitted. This table is the source for the limitations the report must disclose at Stage 11.*

| Stage | Checkpoint | Check (key) | Outcome | What Was Missing / Declared Reason | Escalation Decision |
|-------|-----------|-------------|---------|-------------------------------------|---------------------|
| [N] | [CP{n} / QA{n}] | [e.g., `suppression_rate`] | [NOT VERIFIED / SKIPPED] | [e.g., "no suppression_code declared in the Plan's Domain Configuration"] | [Left at WARNING / Escalated to BLOCKER because … / N/A for SKIPPED] |

### Unresolved Issues

*Document any QA issues that could not be fully resolved.*

| Stage | Issue | Attempts | Outcome | User Decision |
|-------|-------|----------|---------|---------------|
| [N] | [Description] | [N/2] | [Escalated/Accepted] | [Decision] |

**Note:** QA scripts are archived in `scripts/cr/` for reproducibility. See `agent_reference/QA_CHECKPOINTS.md` for checkpoint definitions.

---

## Pre-Flight Scope Check

> Copied at creation from `output/preliminary_notes/{date}_preflight_scope-check.md`, written when the user confirmed the pre-flight (Gate G1; `full-pipeline-mode.md` § Pre-Flight Checklist > On Confirmation (Gate G1)). The data-planner receives it as `CONFIRMED PRE-FLIGHT SCOPE:` and `USER-REFERENCED MATERIALS:`. Cite the materials by their paths in the project; a staged path appears only in the dated move line, which is a historical record.

**Confirmed:** [YYYY-MM-DD]
**Confirmed scope:** [research question, data sources, years, geography, as confirmed — including the user's adjustments]
**What changed from the original request:** [as confirmed, or "Nothing"]
**Decisions:** [each decision with the user's answer, or "None"]

| Material | Path in project | What it shapes |
|----------|-----------------|----------------|
| [title or URL] | [`web_fetches/...`, `papers/...`, `output/preliminary_notes/{date}_{slug}_materials-digest.md`, or the user's own path] | [one line] |

**Moves (old → new):** [YYYY-MM-DD: each staged path → its path in the project, or "Nothing was staged"]

---

## Discovery Preliminary Notes

> Each discovery-phase agent's lossless findings are on disk as a preliminary
> notes file before the next stage: search-agent (Stage 2) and source-researcher
> (Stage 3) write their own notes at the dispatch-named path, which the
> orchestrator confirms and never overwrites (it persists one only if it came
> back inline); the orchestrator writes research-synthesizer's (Stage 3.5)
> immediately upon its return. These files
> persist the full agent output (zero compression) and are referenced by
> downstream agents (data-planner, plan-checker, data-verifier) for full-fidelity
> access to discovery findings. Gate conditions prevent downstream stages from
> proceeding until the relevant files exist on disk.

| Stage | Agent | File Path | Status |
|-------|-------|-----------|--------|
| 2 | search-agent | `output/preliminary_notes/{date}_stage2_data-exploration.md` | [PENDING/WRITTEN] |
| 3 | source-researcher | `output/preliminary_notes/{date}_stage3_{source}_source-research.md` | [PENDING/WRITTEN] |
| 3.5 | research-synthesizer | `output/preliminary_notes/{date}_stage3.5_research-synthesis.md` | [PENDING/WRITTEN] |

**Status Values:**
- **PENDING** — Agent not yet dispatched or return not yet persisted
- **WRITTEN** — File exists on disk with the agent's full lossless findings (agent-written notes, or the full return the orchestrator persisted)

**Note:** Add one row per source-researcher dispatch (one per data source). All rows must show WRITTEN before Stage 4 can proceed.

---

## Citations Accumulated

> Orchestrator populates this section after each Stage 6, 7, and 8 script completion,
> extracting citation data from research-executor output. The report-writer reads this
> as the primary source for the report's References section.
> Pre-populated entries (DAAF, marimo, GUIDE-LLM) are added at project setup.

### Data Sources

| Source | Citation | Stage | Script |
|--------|----------|-------|--------|

### Methodological References

| Method | Citation | Rationale | Stage | Script |
|--------|----------|-----------|-------|--------|

### Software & Tools

| Library | Citation | Rationale | Stage | Script |
|---------|----------|-----------|-------|--------|
| DAAF | Kim, B.H. (2026). *DAAF: The Data Analyst Augmentation Framework* (Version 3.1.0) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf | Analysis framework | — | — |
| marimo | Agrawal, A., & Scolnick, M. (2023). *marimo - an open-source reactive notebook for Python* [Computer software]. https://doi.org/10.5281/zenodo.12735329 | Analysis notebook format (Python projects) | — | — |

> **Language-conditional pre-population:** For Python projects, pre-populate the marimo row above. For R projects, replace the marimo row with R, Quarto, and tidyverse:
> - R Core Team (2026). R: A Language and Environment for Statistical Computing (Version 4.5.3) [Computer software]. R Foundation for Statistical Computing, Vienna, Austria. https://www.R-project.org/ (year and version as `citation()` and `R --version` report them for the image's R; update both when the Dockerfile's `R_VERSION` changes)
> - Allaire, J.J., Teague, C., Scheidegger, C., Xie, Y., Dervieux, C., & Woodhull, G. (2026). Quarto (Version 1.10) [Computer software]. https://doi.org/10.5281/zenodo.5960048
> - Wickham, H. et al. (2019). "Welcome to the Tidyverse." *Journal of Open Source Software*, 4(43), 1686. https://doi.org/10.21105/joss.01686

### Reporting Standards

| Standard | Citation | Rationale | Stage | Script |
|----------|----------|-----------|-------|--------|
| GUIDE-LLM | Feuerriegel, S. et al. (2026). "A Reporting Checklist for Large Language Models in Behavioural Science." *Nature Human Behaviour*, 10(7), 1182-1186. https://doi.org/10.1038/s41562-026-02492-7 | AI disclosure framework | — | — |

---

## Final Review Log

*The orchestrator writes this whole section: the two subsections below from Stage 9 onward, the rest at Stage 12 from data-verifier's return (data-verifier has no Write tool).*

### Stage 9 Check Evidence (notebook-assembler Step 6)

> Orchestrator records this from notebook-assembler's Stage 9 return
> (`WORKFLOW_PHASE4_ANALYSIS.md` § Stage 9, "Render and export evidence for
> Stage 12"). data-verifier reads it at Stage 12 and never re-runs the export,
> render or decompiler (a read-only `marimo check` is allowed; data-verifier
> anti-pattern 8).
> Fill the row for the project's language; mark the other N/A.

| Check | Result (quoted from the return) | Output Path | Recorded At (ISO timestamp of the run) |
|-------|---------------------------------|-------------|----------------------------------------|
| Python: `marimo check --select MB` | [exit code; `summary.errored`; `summary.files_with_issues`] | — | [YYYY-MM-DDTHH:MM:SSZ] |
| Python: `marimo export html` | [exit code] | [`__marimo__/stage9_check/...html`] | [YYYY-MM-DDTHH:MM:SSZ] |
| Python: Step 6c fidelity check | [PASS/FAIL per condition (i)-(iv)] | [decompiled folder path] | [YYYY-MM-DDTHH:MM:SSZ] |
| R: `quarto render` | [exit status] | [rendered HTML path] | [YYYY-MM-DDTHH:MM:SSZ] |

### Integration Checks (integration-checker)

> Orchestrator fills one row per integration-checker return (Stages 9, 11, 12;
> `WORKFLOW_PHASE4_ANALYSIS.md` § Stage 9 and `WORKFLOW_PHASE5_SYNTHESIS.md`
> §§ Stage 11 and Stage 12, Step 0). The Stage 12 return is also persisted in
> full at `output/preliminary_notes/{date}_stage12_integration-check.md` and
> that path is passed to data-verifier.

| Stage | Status | Highest Severity | References Not Verified | Open Issues |
|-------|--------|------------------|-------------------------|-------------|
| 9 | [PENDING / CONNECTED / ISSUES FOUND] | [None/INFO/WARNING/BLOCKER] | [count] | [List or "None"] |
| 11 | [PENDING / CONNECTED / ISSUES FOUND] | [None/INFO/WARNING/BLOCKER] | [count] | [List or "None"] |
| 12 | [PENDING / CONNECTED / ISSUES FOUND] | [None/INFO/WARNING/BLOCKER] | [count] | [List or "None"] |

### Review Date

[YYYY-MM-DD]

### Alignment Check

| Research Outcome | Addressed? | Evidence Location | Quality |
|------------------|------------|-------------------|---------|
| [Outcome 1 from Plan] | [Yes / No] | [Section/file] | [HIGH/MEDIUM/LOW] |
| [Outcome 2 from Plan] | [Yes / No] | [Section/file] | [HIGH/MEDIUM/LOW] |

### Clarification Fulfillment

| Clarification | Fulfilled? | How |
|---------------|------------|-----|
| [Clarification 1] | [Yes / No] | [Notes] |
| [Clarification 2] | [Yes / No] | [Notes] |

### Pre-Flight Scope Fulfillment

| Confirmed scope item, decision, or referenced material (Plan's Confirmed Pre-Flight Scope and User-Referenced Materials) | Honoured? | Where |
|------------------------------------------------------------------------------------------------------------------------|-----------|-------|
| [Item 1] | [Yes / No / Departure logged] | [Section/file, or Decisions Log entry] |

### Plan Commitments

| Commitment | Met? | Notes |
|------------|------|-------|
| [Methodology commitment] | [Yes / No] | [If deviated, explain] |
| [Output commitment] | [Yes / No] | [If deviated, explain] |

### Quality Checklist

| Category | Item | Status |
|----------|------|--------|
| **Data Integrity** | Validation checkpoints passed | [ ] |
| | Coded values handled | [ ] |
| | Suppression documented | [ ] |
| **Documentation** | Plan complete | [ ] |
| | Notebook documented | [ ] |
| | Report complete | [ ] |
| | Citations included | [ ] |

### Deviations from Plan

| Aspect | Planned | Actual | Rationale |
|--------|---------|--------|-----------|
| [What changed] | [Original plan] | [What actually happened] | [Why] |

### Issues Identified

| Issue | Severity | Recommendation |
|-------|----------|----------------|
| [Issue] | [Low/Medium/High] | [How resolved or documented] |

### Final Status

**Review Outcome:** [PASSED | ISSUES_FOUND | STOP] (data-verifier's Overall Status, or STOP for a DATA-VERIFIER STOP; `.claude/agents/data-verifier.md` § Output Format)
**Highest Severity Found:** [BLOCKER | WARNING | INFO | None]

**If ISSUES_FOUND with WARNING only:**
- Caveats must be documented in Report.md Limitations section
- Document each caveat and its impact on conclusions

**If ISSUES_FOUND with a BLOCKER, or STOP:**
- Escalate to the user with the specific failures and remediation options (`WORKFLOW_PHASE5_SYNTHESIS.md` § Review Outcome)
- Issues must be resolved before delivery
- Document resolution in this section
- Re-run Final Review after resolution

---

## Revision (current) (if applicable)

*Added when Revision and Extension mode starts a revision, at its Revision Scope Check (`revision-and-extension-mode.md` § Revision Scope Check and § Revision and Extension Session Management). Session recovery reads the status line. When the revision completes, it gets a row in Revision History below. When a later revision starts, summarize this section's content into the previous revision's Revision History row (adding the row if it is missing), then reset the section for the new revision, so recovery never reads the previous revision's confirmed status.*

- **Revision type:** [Bug Fix / Scope Change / Methodology Change / Extension / Correction]
- **Affected stages:** [stages to re-run]
- **Re-entry point:** [Stage N]
- **New version prefix:** [prior date prefix] → [new date+suffix prefix]
- **Scope Check status:** [Awaiting confirmation | Confirmed YYYY-MM-DD]
- **Materials read:** [what the user cited, with paths in the project (fetches, ingests and any digest are written straight into the project folder; nothing is staged)]

---

## Revision History (if applicable)

*Populated when a project undergoes Revision and Extension Mode. Each revision adds a row.*

| # | Revision Type | Prior Version | Affected Stages | Re-entry Point | New Version Prefix | Rationale |
|---|--------------|---------------|-----------------|----------------|-------------------|-----------|
| 1 | [Bug Fix / Scope Change / Methodology Change / Extension / Correction] | [prior date prefix] | [list of stages re-run] | [Stage N] | [new date+suffix prefix] | [brief description] |

---

## Pending Learning Signals

*Buffer for learning signals from subagents. Flushed to LEARNINGS.md at phase boundaries, after blocker resolution, after debugging, and at utilization gates.*

| Stage.Step | Category | Signal | Source Agent |
|------------|----------|--------|-------------|
| [e.g., 5.1] | [Access/Data/Method/Perf/Process] | [One-line insight] | [research-executor/code-reviewer/debugger] |

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
| [filename] | [Plan/Data/Figure/etc] | [N] |

---

## Session History

*Track multi-session analyses*

| Session | Date | Stages Completed | Archive | Notes |
|---------|------|------------------|---------|-------|
| 1 | [date] | [1-N] | [filename or "pre-project"] | [summary] |
| 2 | [date] | [N-M] | [filename] | [summary] |

---

## Velocity Metrics

*For multi-session tracking*

| Metric | Value |
|--------|-------|
| Sessions to Date | [N] |
| Avg Stages per Session | [X] |
| Trend | [improving/stable/degrading] |
| Estimated Sessions Remaining | [N] |

---

## Session Continuity

*For enabling perfect session resumption*

### Last Action Completed

| Field | Value |
|-------|-------|
| **Wave** | [N] |
| **Task** | [task-name] |
| **Commit** | [hash or "uncommitted"] |
| **Timestamp** | [ISO 8601: YYYY-MM-DDTHH:MM:SS] |
| **Files Modified** | [list] |

### Next Action Required

| Field | Value |
|-------|-------|
| **Wave** | [N] |
| **Task** | [task-name] |
| **Blocked By** | [None | task-name | user-decision | error] |
| **Ready to Execute** | [Yes | No - reason] |

### Context Snapshot

**Orchestrator Utilization:** [actual % from context-reporter hook, e.g., "125k / 1000k tokens (12%)"]

**Key Findings Summary (max 5 bullets):**
- [Critical finding 1]
- [Critical finding 2]
- [Critical finding 3]

**Open Questions:**
- [Question awaiting resolution, or "None"]

**Pending User Decisions:**
- [Decision needed, or "None"]

### User Restart Prompt

**To pick up where we left off, run `/clear` to start a fresh session, then paste this into the chat:**

> Resume my analysis "[Project Title]". Plan: `[exact plan path]`. Task list: `[exact Plan_Tasks path]`. Saved progress: `[exact STATE.md path]`. We were [the activity in plain words, e.g., "combining the two data sources; 3 of 5 steps are done"]. Next: [the next step in plain words, e.g., "run the last two combining steps, then start the analysis"].

**Orchestrator:** keep this prompt in plain words (no stage, phase or checkpoint codes, no agent or status names); the paths stay. Update it whenever hitting the HIGH or CRITICAL utilization gates (see CLAUDE.md § Context & Session Health > Context Quality Curve for the trigger points of each threshold profile), before planned session breaks, or when the user decides to stop. Use concrete values — no brackets or placeholders in the actual prompt.

### Resumption Instructions (Agent Reference)

**For the orchestrator when recovering via Session Recovery:**

1. **Read this STATE.md first** — This is the primary recovery document
2. **Locate Plan at:** `[exact path]` and Plan Tasks at: `[exact Plan_Tasks path]`
3. **Read Plan SELECTIVELY** — Search for `## ` headings, then load only:
   - **Always:** the recovery sections in `session-recovery.md` § Step 3, item 3c: Original Request & Clarifications, Goal & Context, Decisions Log, Risk Register, and the Transformation Sequence table (within Methodology Specification)
   - **Stage-conditional:** the table in `session-recovery.md` § Step 3, item 3e, for the sections the current stage adds
   - **On-demand:** Load specific wave task blocks only when dispatching (see Session Recovery "On-Demand Plan Loading")
4. **Current Phase:** [N] — [Phase Name]
5. **Current Stage:** [N] — [Stage Name]
6. **Next Task:** `[task-name]` (Wave [N])
7. **Required Plan Sections for Next Task:** [List the specific Plan sections needed — e.g., "Wave 5 task block from Executable Task Sequence, CP4 from Validation Checkpoints"]
8. **Prior Findings to Review:** [Specific findings or "See Context Snapshot above"]

**Quick Resume Checklist:**
- [ ] STATE.md read and understood (position, checkpoints, blockers, next actions, context snapshot)
- [ ] Plan recovery sections loaded selectively (NOT entire Plan)
- [ ] Stage-conditional sections loaded if applicable
- [ ] Open blockers identified
- [ ] Next task ready for execution (wave task block loaded on-demand when dispatching)
```

---

## Usage Guidelines

### When to Create

Create STATE.md at **Stage 4 (Plan Creation)** for any analysis expected to:
- Span multiple sessions
- Involve complex multi-stage transformations
- Have elevated risk of context exhaustion
- Require collaboration or handoff

At creation, fill the Pre-Flight Scope Check section from `output/preliminary_notes/{date}_preflight_scope-check.md`.

### When to Update

Update STATE.md after:
- Each checkpoint passes (CP1-CP4)
- A user checkpoint is presented (Current Position > Status = Awaiting Confirmation, and Next Actions > Pending User Input names it) or answered (Status back to In Progress; the answer goes in Key Decisions Made)
- Each stage completes
- Key decisions are made
- Blockers are encountered
- Error budget is consumed
- Deviations are applied
- Before any planned break
- Learning signals received from subagents (append to Pending buffer)
- Flush triggers met (flush buffer → LEARNINGS.md)
- Citations extracted from research-executor output (append to Citations Accumulated)
- QA findings reported by code-reviewer (append to QA Findings Summary)
- Runtime risks discovered (append to Runtime Risks)
- Stage 10 QA aggregation (finalize QA Findings Summary)
- Stage 12 final review (populate Final Review Log)
- A Revision Scope Check is presented or confirmed (Revision and Extension mode) — set Revision (current) > Scope Check status to "Awaiting confirmation" or "Confirmed YYYY-MM-DD"
- A plan revision is accepted (Stage 4.5 revision loop, or Revision and Extension mode new-version creation) — rebuild the Transformation Progress table from the revised Plan_Tasks.md Task Index, update Current Position (Plan/Plan_Tasks paths, Current Stage) and Next Actions, then validate parity (row count == `total_tasks`; every script path present in both the table and the revised Task Index; no superseded plan-version filename remains). This is a blocking condition inside Gate G4.5; see `full-pipeline-mode.md` § STATE.md Update Gates

### Minimal Update Pattern

For quick updates during execution:

```markdown
**Last Updated:** [timestamp]
**Current Stage:** [N]
**Last Checkpoint:** [CPn] - [PASSED]
**Next Action:** [description]
```

### Full Update Pattern

Use full template update:
- At end of each phase
- When blockers encountered
- Before session breaks
- When resuming after interruption

---

## Integration with Session Recovery

STATE.md is the primary input for the Session Recovery procedure:

1. **Recovery starts** with reading STATE.md
2. **Current position** tells where to resume
3. **Checkpoint status** shows what's validated
4. **Next actions** provide immediate guidance
5. **Blockers** surface issues needing resolution
6. **Error budget** prevents infinite retries

**Reading verdicts on recovery.** A resuming session reads the Checkpoint Status tables as verdict *plus counts*, never verdict alone. A checkpoint recorded `PASSED` with a nonzero NOT VERIFIED count is a contradiction: treat the recorded verdict as stale; re-read the script's execution log for the `CP{n} VALIDATION:` / `QA{n} RESULT:` line and its count line, and treat the log as authoritative. Before advancing past a gate, confirm the "Checks Not Verified or Skipped" table has an entry for every unverified or skipped check the counts imply; if the counts and that table disagree, the stage's QA is unresolved and must be re-reviewed rather than assumed clean.

See `{BASE_DIR}/.claude/skills/daaf-orchestrator/references/session-recovery.md` for complete recovery procedure.
