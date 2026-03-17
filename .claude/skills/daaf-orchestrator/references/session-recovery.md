# Session Recovery

> **When to use:** Resuming an interrupted or previous session. The orchestrator's Pre-Check in SKILL.md directs here when the user asks to resume.

**Phase:** Any (recovery protocol)
**Execution:** Orchestrator

## Purpose

Enable stateless recovery when resuming an interrupted analysis after LLM context has been cleared. The Plan documents (Plan.md + Plan_Tasks.md) and STATE.md serve as persistent memory for session continuity.

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
- Note the Plan.md and Plan_Tasks.md file paths from Current Position table
- Review **Checkpoint Status** tables (CP and QA)
- Review **Transformation Progress** table for per-script status
- Read **Context Snapshot** key findings summary
- Read **Runtime Risks** for risks discovered during execution
- Read **QA Findings Summary** for aggregated QA results
- Read **Final Review Log** (if Stage 12 was reached)
- Read **Next Actions** for immediate guidance
- Check **Blockers** section for any unresolved issues

### Step 2b: Read LEARNINGS.md

If the project has a `LEARNINGS.md` file, read it to recover accumulated insights from prior sessions. These signals — data quirks discovered, access patterns, performance notes, methodology decisions — prevent re-encountering resolved issues. Prioritize entries tagged with the current or upcoming stages.

### Step 3: Read Plan.md Selectively

**Do NOT read the entire Plan.md file.** Use targeted section loading to minimize context consumption and preserve capacity for execution work. Also verify that Plan_Tasks.md exists alongside Plan.md.

**3a. Verify both Plan files exist:** Confirm both `Plan.md` and `Plan_Tasks.md` are present in the project folder.

**3b. Build section map:** Search Plan.md for `^## ` headings to get all section names and line numbers (one search call).

**3c. Read Recovery Sections from Plan.md (always load these):**
- `## Original Request & Clarifications` — Anchors the analysis purpose
- `## Goal & Context` — Success criteria and background
- `## Decisions Log` — Pre-execution methodology decisions
- `## Risk Register` — Pre-execution risks and mitigations
- `## Current Status & To-Do's` — Complements STATE.md position info
- `### Transformation Sequence` (within Methodology Specification) — The wave/task summary table only

**3d. Read from STATE.md (already loaded in Step 2):**
- Runtime decisions → Key Decisions Made
- Runtime risks → Runtime Risks
- QA findings → QA Findings Summary
- Transformation progress → Transformation Progress table
- Final review results → Final Review Log (if Stage 12 reached)

**3e. Read stage-conditional sections (only when recovering at or after that stage):**

| Current Stage | Additional Sections to Load | Source |
|---------------|---------------------------|--------|
| 5-8 (Execution) | Specific task blocks for current wave | Plan_Tasks.md |
| 9+ (Notebook) | `## Output Specification` | Plan.md |
| 10+ (QA Aggregation) | QA Findings Summary | STATE.md (already in Step 2) |
| 11+ (Report/Review) | `## Must-Haves (Goal-Backward Verification)`, `## Output Specification` | Plan.md |
| 11+ (Report/Review) | QA Findings Summary, Final Review Log | STATE.md (already in Step 2) |

**3f. Do NOT load these sections at recovery time (load on-demand when needed):**
- `## Phase 1: Discovery Results` — Already consumed during planning
- Plan_Tasks.md task blocks — Load the specific task block when dispatching (search for `### Task {step}:`)
- `## Validation Checkpoints` — Load the specific CP when executing that checkpoint
- `## File Manifest` — Load when needed for verification
- `## Trade-offs Accepted` — Load when referenced
- `## Data Citations` — Load at Stage 11+
- `## Philosophy: Plans are Prompts` — Static preamble, not needed for recovery

### Step 4: Verify File System State

Check which artifacts exist vs. are expected:

```python
expected_files = {
    "plan": f"{date_prefix}_{title}_Plan.md",
    "plan_tasks": f"{date_prefix}_{title}_Plan_Tasks.md",
    "notebook": f"{date_prefix}_{title}.py",
    "report": f"{date_prefix}_{title}_Report.md",
    "raw_data": "data/raw/",
    "processed_data": "data/processed/",
    "figures": "output/figures/"
}

# Check existence for each
```

**Stale State Detection:** If STATE.md's last-updated information or session history timestamp is older than the most recent script file in `scripts/`, the state file may be stale (the prior session may have crashed before updating STATE.md). In this case:
1. Check git log for commits after the STATE.md timestamp
2. List scripts in `scripts/stage*_*/` and compare against the Transformation Progress table
3. If discrepancies exist, reconstruct current position from the filesystem and git history rather than trusting STATE.md alone
4. Note reconstructed entries in the Recovery Summary with a `[reconstructed]` tag

### Step 5: Identify Resume Point

From STATE.md's **Current Position** and **Next Actions**, confirmed by Plan.md's "Current Status & To-Do's":
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
- Tasks: research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Plan_Tasks.md
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

| Stage Interrupted | Recovery Action | Additional Sections to Load |
|-------------------|-----------------|---------------------------|
| 1-3 (Discovery) | Re-read findings, continue from incomplete stage | Plan.md `Phase 1: Discovery Results` |
| 4 (Planning) | Check if Plan.md + Plan_Tasks.md are complete, update if needed | Full Plan.md + Plan_Tasks.md (revision context) |
| 5 (Data Retrieval) | Check if data files exist; re-fetch if missing | Current task block from Plan_Tasks.md |
| 6 (Context Application) | Check for processed data; re-run if missing | Current task block from Plan_Tasks.md |
| 7 (Transformation) | Read STATE.md Transformation Progress, resume from next incomplete step | STATE.md Transformation Progress + current task block from Plan_Tasks.md |
| 8 (Analysis & Viz) | Check output directories, regenerate missing outputs | STATE.md Transformation Progress + current task block from Plan_Tasks.md |
| 9 (Notebook Assembly) | Check if notebook exists; if missing, invoke notebook-assembler agent | Plan.md `Output Specification` |
| 10 (QA Aggregation) | Re-aggregate QA findings from Stages 5-8 | STATE.md QA Findings Summary |
| 11-12 (Delivery) | Check if report exists, regenerate if needed | Plan.md `Must-Haves` + `Output Specification`; STATE.md QA Findings Summary + Final Review Log |

## On-Demand Plan Loading

After recovery, load additional Plan.md or Plan_Tasks.md sections as needed during execution. **Do NOT preload these — read them from the appropriate file when the specific need arises.**

| Action | Section to Load | Source File | How to Find It |
|--------|----------------|-------------|----------------|
| Dispatching a Stage 5-8 task | The specific task block (e.g., `### Task 3:`) | Plan_Tasks.md | Search for the task heading, read to next `### Task` heading |
| Constructing CP validation | The relevant CP subsection from `## Validation Checkpoints` | Plan.md | Search for the CP heading (e.g., `### CP3`) |
| Reviewing prior discovery | `## Phase 1: Discovery Results` | Plan.md | Search for heading, read to next `## ` heading |
| Checking file inventory | `## File Manifest` | Plan.md | Search for heading, read to end of file |
| Final review (Stage 12) | `## Must-Haves`, `## Output Specification` | Plan.md | Search for each heading |
| Final review (Stage 12) | QA Findings Summary, Final Review Log | STATE.md | Already loaded from Step 2 |
| Debugging or re-running | Relevant task block | Plan_Tasks.md | Search for the task heading |

**Procedure:** Search for the target heading in the appropriate file (e.g., `### Task 3:` in Plan_Tasks.md), note the line number, then read from that line to the next same-level heading. This costs one search + one targeted read per section, and avoids loading full files into context.

## Blocked/Failed Recovery

If the analysis is marked as "Blocked" or has failed checkpoints:
1. Read the Issue description from STATE.md (blockers) or Plan.md (methodology issues)
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
- [ ] STATE.md read and understood (current position, checkpoints, blockers, runtime risks, QA findings, next actions)
- [ ] Plan.md recovery sections read (Original Request, Goal & Context, Decisions Log, Risk Register, Current Status)
- [ ] Plan_Tasks.md existence verified
- [ ] Stage-conditional sections loaded if applicable (per Step 3e table)
- [ ] Current stage/status identified and consistent between STATE.md and Plan.md
- [ ] File system state verified
- [ ] Resume point identified
- [ ] LEARNINGS.md reviewed (if present) and key signals noted
- [ ] Any blocking issues presented to user
- [ ] User confirmed ready to proceed
