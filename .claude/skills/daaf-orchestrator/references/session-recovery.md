# Session Recovery

> **When to use:** Resuming an interrupted or previous session. The orchestrator's Pre-Check in SKILL.md directs here when the user asks to resume.

**Phase:** Any (recovery protocol)
**Execution:** Orchestrator

## Purpose

Enable stateless recovery when resuming an interrupted analysis after LLM context has been cleared. The Plan document serves as persistent memory for session continuity.

## When to Use

- User returns to an in-progress analysis
- System context has been cleared between sessions
- User references a project by name or date

## Recovery Procedure

### Step 1: Locate Project

Search `research/` directory for matching project folder:
- Match on date: `research/YYYY-MM-DD*/`
- Match on keywords from user's message
- List candidates if multiple matches

### Step 2: Read STATE.md

Read the full STATE.md file. This is the primary recovery document:
- Extract current stage, status, and blockers from **Current Position**
- Note the Plan file path from Current Position table
- Review **Checkpoint Status** tables (CP and QA)
- Review **Transformation Progress** table for per-script status
- Read **Context Snapshot** key findings summary
- Read **Next Actions** for immediate guidance
- Check **Blockers** section for any unresolved issues

### Step 3: Read Plan Selectively

**Do NOT read the entire Plan file.** Use targeted section loading to minimize context consumption and preserve capacity for execution work.

**3a. Build section map:** Search the Plan file for `^## ` headings to get all section names and line numbers (one search call).

**3b. Read Recovery Sections (always load these):**
- `## Original Request & Clarifications` — Anchors the analysis purpose
- `## Goal & Context` — Success criteria and background
- `## Decisions Log` — All methodology decisions made so far
- `## Risk Register` — Active risks and mitigations
- `## Current Status & To-Do's` — Complements STATE.md position info
- `### Transformation Sequence` (within Methodology Specification) — The wave/task summary table only, NOT the full XML task blocks in Executable Task Sequence

**3c. Read stage-conditional sections (only when recovering at or after that stage):**

| Current Stage | Additional Sections to Load |
|---------------|---------------------------|
| 7+ (Transform) | `### Transformation Log` (within Methodology Specification) |
| 9+ (Notebook) | `## Output Specification` |
| 10+ (QA Aggregation) | `## QA Findings Summary` |
| 11+ (Report/Review) | `## Must-Haves (Goal-Backward Verification)`, `## Output Specification`, `## QA Findings Summary` |

**3d. Do NOT load these sections at recovery time (load on-demand when needed):**
- `## Phase 1: Discovery Results` — Already consumed during planning
- `## Executable Task Sequence` — Load the specific wave's task block when dispatching
- `## Validation Checkpoints` — Load the specific CP when executing that checkpoint
- `## File Manifest` — Load when needed for verification
- `## Final Review Log` — Load at Stage 12
- `## Trade-offs Accepted` — Load when referenced
- `## Data Citations` — Load at Stage 11+
- `## Philosophy: Plans are Prompts` — Static preamble, not needed for recovery

### Step 4: Verify File System State

Check which artifacts exist vs. are expected:

```python
expected_files = {
    "plan": f"{date_prefix}_{title}_Plan.md",
    "notebook": f"{date_prefix}_{title}.py",
    "report": f"{date_prefix}_{title}_Report.md",
    "raw_data": "data/raw/",
    "processed_data": "data/processed/",
    "figures": "output/figures/"
}

# Check existence for each
```

### Step 5: Identify Resume Point

From STATE.md's **Current Position** and **Next Actions**, confirmed by Plan's "Current Status & To-Do's":
- Current Phase: [1-5]
- Current Stage: [1-12]
- Status: [In Progress | Blocked | Complete]
- Last Checkpoint: [CP# result]

Determine what's complete and what remains.

### Step 6: Present Recovery Summary

```markdown
**Session Recovery: [Project Title]**

I found your in-progress analysis:
- Plan: research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Plan.md
- Current Stage: [N] - [Stage Name]
- Status: [status]
- Last Checkpoint: [CP#] - [PASSED/FAILED]

**Completed:**
- [✓] Phase 1: Discovery complete
- [✓] Phase 2: Plan created
- [✓] Stage 5: Data retrieved
- [✓] Stage 6: Data cleaned (CP2 passed)

**Remaining:**
- [ ] Stage 7: Transformations (3 of 5 complete)
- [ ] Stage 8-12: Analysis, notebook, QA, report, final review

**Files Present:**
- Raw data: ✓ (data/raw/YYYY-MM-DD_*.parquet)
- Processed data: ✓ (data/processed/YYYY-MM-DD_*.parquet)
- Notebook: ✗ (not yet created)

Ready to continue from Stage 7, Transformation #4?
```

## Recovery from Different Stages

| Stage Interrupted | Recovery Action | Additional Plan Sections to Load |
|-------------------|-----------------|----------------------------------|
| 1-3 (Discovery) | Re-read findings, continue from incomplete stage | `Phase 1: Discovery Results` |
| 4 (Planning) | Check if Plan is complete, update if needed | Full Plan (revision context) |
| 5 (Data Retrieval) | Check if data files exist; re-fetch if missing | Current wave's task block from `Executable Task Sequence` |
| 6 (Context Application) | Check for processed data; re-run if missing | Current wave's task block from `Executable Task Sequence` |
| 7 (Transformation) | Read Transformation Log, resume from next incomplete step | `Transformation Log` + current wave's task block |
| 8 (Analysis & Viz) | Check output directories, regenerate missing outputs | `Transformation Log` + current wave's task block |
| 9 (Notebook Assembly) | Check if notebook exists; if missing, invoke notebook-assembler agent | `Output Specification` |
| 10 (QA Aggregation) | Re-aggregate QA findings from Stages 5-8 | `QA Findings Summary` |
| 11-12 (Delivery) | Check if report exists, regenerate if needed | `Must-Haves`, `Output Specification`, `QA Findings Summary` |

## On-Demand Plan Loading

After recovery, load additional Plan sections as needed during execution. **Do NOT preload these — read them from the Plan file when the specific need arises.**

| Action | Plan Section to Load | How to Find It |
|--------|---------------------|----------------|
| Dispatching a Stage 5-8 task | The specific wave's task block (e.g., `### Wave 3`) from `## Executable Task Sequence` | Search for the wave heading, read to next `### Wave` heading |
| Constructing CP validation | The relevant CP subsection from `## Validation Checkpoints` | Search for the CP heading (e.g., `### CP3`) |
| Reviewing prior discovery | `## Phase 1: Discovery Results` | Search for heading, read to next `## ` heading |
| Checking file inventory | `## File Manifest` | Search for heading, read to end of file |
| Final review (Stage 12) | `## Must-Haves`, `## Output Specification` | Search for each heading |
| Debugging or re-running | Relevant prior wave's task block | Search for the wave heading |

**Procedure:** Search for the target heading in the Plan file (e.g., `### Wave 3`), note the line number, then read from that line to the next same-level heading. This costs one search + one targeted read per section, and avoids loading the full Plan into context.

## Blocked/Failed Recovery

If the analysis is marked as "Blocked" or has failed checkpoints:
1. Read the Issue description from Plan
2. Present issue to user
3. Ask for guidance before proceeding

**Example:**
```markdown
**Recovery Issue: Analysis Blocked**

This analysis is currently blocked at Stage 6 (Context Application).

**Issue:** Suppression rate of 52% exceeds 50% threshold (CP2 failed)

**Options documented in Plan:**
1. Aggregate to district level (reduces suppression)
2. Exclude suppressed variable from analysis
3. Proceed with caveat and document limitation

Which approach would you like to take?
```

## Recovery Verification Checklist

Before resuming work:
- [ ] STATE.md read and understood (current position, checkpoints, blockers, next actions)
- [ ] Plan recovery sections read (Original Request, Goal & Context, Decisions Log, Risk Register, Current Status)
- [ ] Stage-conditional Plan sections loaded if applicable (per Step 3c table)
- [ ] Current stage/status identified and consistent between STATE.md and Plan
- [ ] File system state verified
- [ ] Resume point identified
- [ ] Any blocking issues presented to user
- [ ] User confirmed ready to proceed
