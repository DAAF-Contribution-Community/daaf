# Context Management Protocol

This document provides **detailed procedures** for the context health rules defined in CLAUDE.md's "Context & Session Health" subsection. CLAUDE.md is the single source of truth for thresholds and the context monitoring protocol. This document covers the *how*: subagent context isolation, degradation symptom taxonomy, context budgets, and recovery strategies.

> **Quality Primacy Rule:** Context management is about maintaining awareness of remaining capacity so the orchestrator can make informed decisions about when to restart. It is NEVER about reducing the quality or completeness of work. Subagent prompt fidelity, Context Completeness Checklist compliance, and inlined context are NON-NEGOTIABLE regardless of utilization level. If maintaining quality means reaching a restart point sooner, that is the correct outcome. The STATE.md + Protocol 6 system exists precisely for clean handoffs at full quality.

---

## Context Quality Curve

Context utilization determines how much runway remains — it does NOT determine the quality of work performed. Quality is invariant; utilization determines WHEN to restart.

| Utilization | Status | Monitoring Posture | Required Action |
|-------------|--------|-------------------|-----------------|
| **0-40%** | NOMINAL | Normal operations | Continue normally |
| **40-60%** | ELEVATED | Monitor; plan for restart | Prefer subagent delegation for heavy execution; **maintain full prompt fidelity**; update STATE.md proactively |
| **60-75%** | HIGH | Prepare for restart | Complete current atomic unit at full quality; update STATE.md with restart prompt; report to user; do not start new stages |
| **75%+** | CRITICAL | Session restart required | Finalize STATE.md; recommend session restart; no new work |

### Target Operating Range

**Orchestrator Target:** Stay under 60% utilization through delegation. Plan for session restart when approaching 60%.

**Why This Matters:**
- Subagents get fresh 200K token windows (always NOMINAL quality)
- Delegating heavy execution to subagents preserves orchestrator runway
- Orchestrator retains capacity for high-quality prompt construction and synthesis
- **Quality of subagent prompts is never reduced** — if maintaining complete Context Completeness Checklist compliance means reaching the restart point sooner, that is the correct outcome
- STATE.md + Protocol 6 provide a robust, zero-loss restart mechanism

---

## Orchestrator Context Budget

### What Stays in Main Context

Keep only what's essential for orchestration:

| Content Type | Max Size | Rationale |
|--------------|----------|-----------|
| Original user request | <500 words | Verbatim reference for alignment |
| Mode classification | ~50 words | Guide workflow execution |
| Scope decisions | ~100 words | Bound the work |
| Phase summaries | ~200 words each | Track progress |
| Current stage + blockers | ~100 words | Know where we are |
| Plan document location | Path only | Don't load full Plan |
| Error history | ~200 words | Avoid repeating failures |

> **Plan Loading Strategy:** During session recovery (Protocol 6), load Plan selectively — search for `## ` headings to build a section map, then read only recovery-critical sections (Original Request, Goal & Context, Decisions Log, Risk Register, Current Status, Transformation Sequence summary). Task-specific sections (wave task blocks, validation checkpoints) are loaded on-demand when dispatching subagents. See Protocol 6 Steps 3a-3d and "On-Demand Plan Loading" for the complete procedure.

**Total Orchestrator Working Set:** ~1,500-2,000 words

### What Gets Delegated to Subagents

These tasks consume significant context and should ALWAYS be delegated:

| Task Type | Subagent Type | Why Delegate |
|-----------|---------------|--------------|
| Skill invocations | Plan/general-purpose | Skills add 5K-20K tokens |
| Data exploration | Plan | Iterative searching fills context |
| Source deep-dives | Plan | Reference docs are large |
| Code-heavy analysis | general-purpose | Code + output consumes tokens |
| Visualization generation | general-purpose | Plot code is verbose |
| QA aggregation | general-purpose | QA findings across stages are voluminous |

### What Never Goes in Orchestrator Context

- Full skill content (let subagents load)
- Raw data samples (only shapes and summaries)
- Complete code files (only references)
- Downloaded data summaries (only parsed findings)
- Full error tracebacks (only summaries)

---

## Task Prompt Size Guidelines

See `03_SKILL_INVOCATIONS.md` "Prompt Size Targets by Subagent Type" for size targets per subagent type. These are efficiency targets, not hard ceilings — the Context Completeness Checklist always takes priority over prompt brevity.

### Prompt Content Priority

Prioritize in this order. Items marked REQUIRED must never be omitted regardless of utilization level:

1. **Task specification** (what to do) - REQUIRED
2. **Verification criteria** (how to validate) - REQUIRED
3. **Expected outcomes** (what success looks like) - REQUIRED
4. **Relevant Plan sections** (methodology context) - REQUIRED when referenced by Context Completeness Checklist
5. **Prior stage findings** (if dependencies exist) - REQUIRED when task has `depends_on` entries
6. **Background context** (nice to have) - LOW

**Principle:** An incomplete prompt wastes MORE tokens than a thorough one (subagent confusion → re-invocation → wasted output). Never compress outgoing prompt quality to conserve context.

---

## Subagent Context Isolation

### Why Isolation Matters

Each subagent invocation gets a **fresh context window**:
- Subagent starts at 0% utilization (PEAK quality)
- Skill loading adds known, bounded content
- Task execution stays focused
- Return to orchestrator is concise and focused

### Isolation Protocol

1. **Don't pre-load skills** in orchestrator context
2. **Don't copy Plan content** into main context (reference by path)
3. **Don't accumulate** subagent returns verbatim
4. **Do summarize and focus on key findings** before integrating
5. **Do reference** prior findings by summary, not full text

### Subagent Return Processing

When subagent returns findings:

```
1. Receive full output
2. Verify against OUTPUT FORMAT (see 03_SKILL_INVOCATIONS.md)
3. Extract:
   - Status (PASSED/FAILED/WARNING)
   - Key findings (3-5 bullets)
   - File locations
   - Confidence level
   - Issues requiring escalation
4. Discard:
   - Verbose explanations
   - Intermediate steps
   - Full code blocks (keep references)
   - Raw data samples
5. Store summarized key findings in working memory
```

---

## Session State Management

### STATE.md Purpose

The STATE.md file serves as **persistent session memory**:
- Survives context window resets
- Enables session recovery (Protocol 6)
- Tracks progress across long analyses
- Documents key decisions for continuity

### When to Create STATE.md

**MANDATORY Creation (Gate G4):**
- At Stage 4 (Plan creation) for **ALL Full Pipeline analyses**
- Stage 5 CANNOT begin without STATE.md existing alongside Plan
- This is a forcing function, not a recommendation

**Secondary Triggers (if somehow missed at Stage 4):**
- When context utilization approaches ELEVATED (40%)
- When analysis complexity increases unexpectedly

### When to Update STATE.md

**MANDATORY Update Triggers:**
- After each checkpoint passes (CP1-CP4)
- After each QA review completes (QA1-QA4b)
- When any stage completes
- When blockers are encountered
- When key decisions are made
- When utilization reaches ELEVATED (40%+)
- Before any planned session break
- At every stage transition

**Minimal Update Pattern (after each stage):**
```markdown
**Last Updated:** [timestamp]
**Current Stage:** [N]
**Last Checkpoint:** [CPn] - [PASSED]
**Next Action:** [description]
```

**Full Update Pattern (at phase boundaries or blockers):**
Use the complete template from `STATE_TEMPLATE.md`.

### STATE.md Location

```
research/YYYY-MM-DD [Title]/
├── STATE.md                          # Session state file
├── YYYY-MM-DD [Title] Plan.md
├── ...
```

See `STATE_TEMPLATE.md` for the complete template.

---

## Context Recovery Strategies

### When Context is Approaching Limits (ELEVATED: 40-60%)

If orchestrator context reaches ELEVATED:

1. **Prefer subagent delegation** for heavy execution tasks
2. **Reload Plan sections from file** when constructing subagent prompts rather than retaining in context permanently
3. **Update STATE.md faithfully** — write complete stage summaries, accurate checkpoint statuses, and specific next-action descriptions. Resist the urge to abbreviate; STATE.md is the lifeline for session recovery.
4. **NEVER reduce subagent prompt quality** — the Context Completeness Checklist is mandatory at ALL utilization levels. If meeting the checklist requires reading the Plan (consuming tokens), do it. Reaching a restart point sooner with high-quality work is always preferable to continuing longer with degraded subagent tasking.

### When Context Exceeds 60%

If orchestrator context exceeds 60%:

1. **STOP current execution**
2. **Update STATE.md** with full progress **and User Restart Prompt section** (concrete values, no placeholders)
3. **Report to user** — include the restart prompt so they can copy-paste it:
   ```
   **Context Limit Approaching**

   I've captured current progress in STATE.md.
   To continue with fresh context, copy the session restart prompt below, run 
   `/clear` to reset the session, then paste the restart prompt into the new chat. 
   I'll use Protocol 6 to resume seamlessly.

   Current state:
   - Phase: [X]
   - Stage: [Y]
   - Last checkpoint: [CPn] - [status]
   - Next action: [description]

   **To resume, run `/clear` and then paste this:**
   > Resume the [Project Title] analysis. Plan: `[plan path]`. State: `[STATE.md path]`. Currently at Stage [N] ([Stage Name]) — next step is [task description].
   ```
4. **Await user direction** (start a new session to continue at full quality, or complete only the current atomic unit before restarting)

---

## Context Quality Monitoring

### Symptoms of Context Degradation

Watch for these warning signs that indicate context quality is declining:

| Symptom | Severity | Indicates |
|---------|----------|-----------|
| Repeating information already stated | MEDIUM | 40-60% utilization |
| Forgetting earlier decisions | HIGH | 60%+ utilization |
| Asking questions already answered | HIGH | 60%+ utilization |
| Generating contradictory outputs | CRITICAL | 70%+ utilization |
| Incomplete or truncated responses | CRITICAL | Near limit |
| Losing track of current stage | HIGH | Context fragmentation |
| Mixing up file names or paths | MEDIUM | Working memory strain |

### Recovery Actions by Utilization

| Utilization | Symptoms Present? | Action |
|-------------|-------------------|--------|
| ELEVATED (40-60%) | None | Prefer delegation for execution; maintain full prompt quality; update STATE.md |
| ELEVATED (40-60%) | Minor repetition | Delegate execution to subagent; update STATE.md |
| HIGH (60-75%) | None | Complete current atomic unit at full quality; update STATE.md with restart prompt; report to user |
| HIGH (60-75%) | Any symptoms | Complete current atomic unit at full quality; update STATE.md with restart prompt; report to user |
| CRITICAL (75%+) | Any | Finalize STATE.md; recommend session restart; no new work |

**In all cases:** Quality of current work output (including subagent prompts and STATE.md writes) is never reduced. The variable is WHEN to stop, not HOW WELL to work.

### Proactive Quality Maintenance

Context monitoring is objective and continuous via the `context-reporter` hook. At each stage transition and after each subagent return:

1. **Check** the utilization percentage from the hook report
2. **Act** per the threshold table (NOMINAL → proceed; ELEVATED → delegate execution, maintain prompt quality; HIGH → finish current unit, prepare restart)
3. **Update STATE.md** if at ELEVATED or above — write faithfully and completely

**If degradation symptoms are observed** (repetition, path confusion, forgetting decisions): treat as equivalent to HIGH regardless of actual utilization — update STATE.md immediately and prepare for restart. These symptoms indicate the context is fragmented even if not numerically full.

### Emergency Context Reset

If context becomes severely degraded:

```markdown
**CONTEXT QUALITY CRITICAL**

I'm experiencing context degradation that may affect output quality.

**Current State Captured:**
- Phase: [N]
- Stage: [N]
- Last checkpoint: [CPn] - [status]
- Next action: [description]

**Saved to:** STATE.md (updated)

**Recommendation:**
To ensure high-quality completion, please copy the restart prompt below,
run `/clear` to reset the session, then paste the restart prompt from STATE.md.
Reference: `research/[project]/STATE.md`

I'll then use Protocol 6 (Session Recovery) to resume with fresh context.
```

---

## Context Monitoring

The `context-reporter` hook provides objective, continuous utilization measurements on every orchestrator turn. This is the sole mechanism for context monitoring — no subjective self-assessment is needed.

### Context Utilization Reporting

The hook injects the following message format:

```
Context utilization [STATUS]: XXXk / 200k tokens (YY%)
```

Where **STATUS** = OK (<40%) | ELEVATED (40-60%) | HIGH (60-75%) | CRITICAL (75%+). Use the reported percentage directly for gating decisions — no estimation needed.

Thresholds and required actions are defined in CLAUDE.md's "Context & Session Health" subsection.

---

## Quick Reference

### Context Budget Summary

```
Orchestrator Target: Stay under 60% through delegation
Quality: INVARIANT at all utilization levels
Subagent Fresh Start: 0% (NOMINAL quality every time)

Keep in Orchestrator:
- Request + scope (~600 words)
- Phase summaries (~1000 words)
- Current state (~400 words)
- Total: ~2000 words

Always Delegate:
- Skill loading
- Data exploration
- Code execution
- Visualization
- Testing

Context Monitoring Triggers:
- Every stage transition
- After every subagent return (lightweight: check utilization + decide)
- When degradation symptoms observed (treat as HIGH)

Never Compress:
- Subagent prompt content (Context Completeness Checklist is mandatory)
- STATE.md writes (lifeline for session recovery)
- QA BLOCKER details (until resolved)
- Methodology decision rationales (audit-critical)
```
