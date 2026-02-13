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
| **Plan Location** | `research/[folder]/[filename] Plan.md` |
| **Current Phase** | [1-5]: [Phase Name] |
| **Current Stage** | [1-12]: [Stage Name] |
| **Status** | [In Progress / Blocked / Complete] |

---

## Checkpoint Status

### Primary Validation (CP1-CP4)

| Checkpoint | Status | Timestamp | Notes |
|------------|--------|-----------|-------|
| CP1 (Post-Fetch) | [PENDING/PASSED/FAILED] | [time] | [notes] |
| CP2 (Post-Clean) | [PENDING/PASSED/FAILED] | [time] | [notes] |
| CP3 (Post-Transform) | [PENDING/PASSED/FAILED] | [time] | [notes] |
| CP4 (Pre-Output) | [PENDING/PASSED/FAILED] | [time] | [notes] |

### Secondary Validation (QA1-QA4b)

| Checkpoint | Stage | Status | BLOCKERs | WARNINGs | Revisions | Timestamp |
|------------|-------|--------|----------|----------|-----------|-----------|
| QA1 (Post-Fetch) | 5 | [PENDING/PASSED/ISSUES] | [count] | [count] | [count] | [time] |
| QA2 (Post-Clean) | 6 | [PENDING/PASSED/ISSUES] | [count] | [count] | [count] | [time] |
| QA3 (Post-Transform) | 7 | [PENDING/PASSED/ISSUES] | [count] | [count] | [count] | [time] |
| QA4a (Post-Analysis) | 8.1 | [PENDING/PASSED/ISSUES] | [count] | [count] | [count] | [time] |
| QA4b (Post-Viz) | 8.2 | [PENDING/PASSED/ISSUES] | [count] | [count] | [count] | [time] |

**QA Status Values:**
- **PENDING** — QA checkpoint not yet executed for this stage
- **PASSED** — All scripts passed QA review (no BLOCKERs, WARNINGs logged)
- **ISSUES** — BLOCKERs resolved via revision, or WARNINGs logged

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

**Blockers (if BLOCKED and unresolved):**
- [Blocker description]

**Gate G4.5 Status:** [OPEN / SATISFIED]

> **CRITICAL:** Stage 5 CANNOT begin until Plan-Checker Status is PASSED or PASSED_WITH_WARNINGS.
> If this section shows NOT_RUN, invoke plan-checker before proceeding.

---

## Data Status

| Dataset | Location | Rows | Status |
|---------|----------|------|--------|
| Raw Data | `data/raw/[filename]` | [count] | [fetched/pending] |
| Processed Data | `data/processed/[filename]` | [count] | [cleaned/pending] |
| Analysis Data | `data/processed/[filename]` | [count] | [ready/pending] |

**Suppression Rate:** [X%]
**Data Lag:** [None / X years]
**COVID Years Included:** [Yes/No]

---

## Key Decisions Made

| Decision | Choice | Rationale | Stage |
|----------|--------|-----------|-------|
| [Topic] | [What was decided] | [Why] | [N] |
| [Topic] | [What was decided] | [Why] | [N] |

---

## Transformation Progress

*For Stage 5-8 tracking (includes QA substages). Each row tracks ONE script with its independent QA status. A row with QA Status = NOT_RUN blocks the next script invocation.*

| # | Transformation | Script Path | CP Status | QA Status | QA Script Path | QA Depth | Revisions | Pre-Rows | Post-Rows | Notes |
|---|----------------|-------------|-----------|-----------|----------------|----------|-----------|----------|-----------|-------|
| 1 | Fetch CCD schools | `scripts/stage5_fetch/01_fetch-ccd.py` | [PENDING/PASSED/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage5_01_cr1.py` | [1 of 5] | [0-2] | [N] | [N] | |
| 2 | Clean CCD schools | `scripts/stage6_clean/01_clean-ccd.py` | [PENDING/PASSED/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage6_01_cr1.py` | [1 of 5] | [0-2] | [N] | [N] | |
| 3 | Join CCD + MEPS | `scripts/stage7_transform/01_join-data.py` | [PENDING/PASSED/FAILED] | [NOT_RUN/PENDING/PASSED/WARNING/REVISED] | `scripts/cr/stage7_01_cr1.py` | [1 of 5] | [0-2] | [N] | [N] | |

**QA Status Values:**
- **NOT_RUN** — code-reviewer has not been invoked for this script (blocks next script invocation)
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
| Subagent Re-invocations | [X] | 9 | [Y] |
| STOP Conditions | [X] | 3 | [Y] |
| **QA Escalations** | [X] | 3 | [Y] |

---

## Deviations Applied

| Deviation | Type | Stage | Notes |
|-----------|------|-------|-------|
| [None or description] | [Bug Fix/Critical Func/Test] | [N] | |

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

| Session | Date | Stages Completed | Notes |
|---------|------|------------------|-------|
| 1 | [date] | [1-N] | [summary] |
| 2 | [date] | [N-M] | [summary] |

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

**Orchestrator Utilization:** [actual % from context-reporter hook, e.g., "125k / 200k tokens (62%)"]

**Key Findings Summary (max 5 bullets):**
- [Critical finding 1]
- [Critical finding 2]
- [Critical finding 3]

**Open Questions:**
- [Question awaiting resolution, or "None"]

**Pending User Decisions:**
- [Decision needed, or "None"]

### User Restart Prompt

**To resume in a new session, run `/clear` to reset context, then paste this into the chat:**

> Resume the [Project Title] analysis. Plan: `[exact plan path]`. State: `[exact STATE.md path]`. Currently at Stage [N] ([Stage Name]) — next step is [task description].

**Orchestrator:** Update this prompt whenever hitting 60%/75% utilization gates, before planned session breaks, or when the user decides to stop. Use concrete values — no brackets or placeholders in the actual prompt.

### Resumption Instructions (Agent Reference)

**For the orchestrator when recovering via Protocol 6:**

1. **Read this STATE.md first** — This is the primary recovery document
2. **Locate Plan at:** `[exact path]`
3. **Read Plan SELECTIVELY** — Search for `## ` headings, then load only:
   - **Always:** Original Request, Goal & Context, Decisions Log, Risk Register, Current Status
   - **Stage-conditional:** See Protocol 6 Step 3c table for additional sections based on current stage
   - **On-demand:** Load specific wave task blocks only when dispatching (see Protocol 6 "On-Demand Plan Loading")
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

### When to Update

Update STATE.md after:
- Each checkpoint passes (CP1-CP4)
- Each stage completes
- Key decisions are made
- Blockers are encountered
- Error budget is consumed
- Deviations are applied
- Before any planned break
- Learning signals received from subagents (append to Pending buffer)
- Flush triggers met (flush buffer → LEARNINGS.md)

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

## Integration with Protocol 6

STATE.md is the primary input for Protocol 6 (Session Recovery):

1. **Recovery starts** with reading STATE.md
2. **Current position** tells where to resume
3. **Checkpoint status** shows what's validated
4. **Next actions** provide immediate guidance
5. **Blockers** surface issues needing resolution
6. **Error budget** prevents infinite retries

See `01_PROTOCOLS.md` Protocol 6 for complete recovery procedure.
