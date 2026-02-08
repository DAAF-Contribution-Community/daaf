# Context Management Protocol

This document defines how to manage context utilization to prevent "context rot" - the quality degradation that occurs as the context window fills up.

---

## Context Quality Curve

Context utilization directly impacts reasoning quality. Monitor and manage proactively.

| Utilization | Quality Level | Reasoning Capability | Required Action |
|-------------|---------------|---------------------|-----------------|
| **0-30%** | PEAK | Full complex reasoning, nuanced analysis | Execute complex tasks freely |
| **30-40%** | GOOD | Strong reasoning, reliable execution | Continue normal operations |
| **40-60%** | DEGRADING | Reduced nuance, increased errors | Delegate to subagents, avoid complex reasoning |
| **60%+** | POOR | Significant degradation, unreliable | STOP, compress findings, summarize, or restart |

### Target Operating Range

**Orchestrator Target:** 25-35% utilization (conservative)

**Why This Matters:**
- Peak quality enables best decision-making
- Subagents get fresh 200K token windows (always PEAK)
- Delegating heavy tasks to subagents preserves orchestrator quality
- Orchestrator can then synthesize subagent findings effectively
- **Conservative buffer** ensures quality is maintained under varying workloads

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

When creating Task prompts for subagents, size the context appropriately:

| Stage | Subagent Type | Max Prompt Size | What to Include |
|-------|---------------|-----------------|-----------------|
| 2-3 (Discovery) | Plan | 500 words | Research question, constraints, scope |
| 5 (Retrieval) | general-purpose | 800 words | Query spec from Plan, expected values |
| 6 (Context) | general-purpose | 800 words | Caveats from Stage 3, cleaning spec |
| 7-8 (Analysis) | general-purpose | 1000 words | Data specs, methodology, transformation details |
| 9 (Notebook) | general-purpose | 800 words | Structure spec, analysis findings |
| 10 (QA) | general-purpose | 500 words | File paths, test requirements |

### Prompt Content Priority

When space is limited, prioritize in this order:

1. **Task specification** (what to do) - REQUIRED
2. **Verification criteria** (how to validate) - REQUIRED
3. **Expected outcomes** (what success looks like) - HIGH
4. **Relevant Plan sections** (methodology context) - MEDIUM
5. **Prior stage findings** (if dependencies) - MEDIUM
6. **Background context** (nice to have) - LOW

---

## Context Compression Protocol

### When to Compress

Trigger compression when:
- Phase completion (compress phase findings)
- Large subagent return (extract essentials only)
- Context utilization exceeds 40%
- Preparing for complex reasoning task
- Every 3 orchestrator turns (proactive compression)

### Compression Technique

Transform verbose content into compressed summaries:

**Before (verbose):**
```
The data exploration found that the CCD enrollment endpoint at
/schools/ccd/enrollment/ contains enrollment data from 1986 to 2022.
The key variables include total enrollment, enrollment by grade,
enrollment by race/ethnicity, and enrollment by gender. The data
is available at the school level with NCESSCH as the primary key...
[continues for 500+ words]
```

**After (compressed):**
```
Stage 2 Findings:
- Endpoint: /schools/ccd/enrollment/ (1986-2022)
- Key vars: enrollment, grade, race, gender
- Level: school (NCESSCH key)
- Flagged: race categories need Stage 3 deep-dive
- Confidence: HIGH
```

### Compression Checklist

When compressing subagent output:
- [ ] Extract key findings (bullet points)
- [ ] Preserve decision rationales (why, not just what)
- [ ] Keep data shapes (rows, columns, rates)
- [ ] Retain error/warning history
- [ ] Discard intermediate reasoning
- [ ] Discard raw data samples
- [ ] Discard verbose explanations

---

## Subagent Context Isolation

### Why Isolation Matters

Each subagent invocation gets a **fresh context window**:
- Subagent starts at 0% utilization (PEAK quality)
- Skill loading adds known, bounded content
- Task execution stays focused
- Return to orchestrator is compressed

### Isolation Protocol

1. **Don't pre-load skills** in orchestrator context
2. **Don't copy Plan content** into main context (reference by path)
3. **Don't accumulate** subagent returns verbatim
4. **Do compress** findings before integrating
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
5. Store compressed version in working memory
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

**MANDATORY Creation (Gate G3):**
- At Stage 4 (Plan creation) for **ALL Full Pipeline analyses**
- Stage 5 CANNOT begin without STATE.md existing alongside Plan
- This is a forcing function, not a recommendation

**Secondary Triggers (if somehow missed at Stage 4):**
- When context utilization approaches 40%
- When analysis complexity increases unexpectedly
- After any self-assessment failure

### When to Update STATE.md

**MANDATORY Update Triggers:**
- After each checkpoint passes (CP1-CP4)
- After each QA review completes (QA1-QA4)
- When any stage completes
- When blockers are encountered
- When key decisions are made
- When utilization exceeds 40% (Utilization Gate)
- Before any planned session break
- After every self-assessment checkpoint (every 3 turns)

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

### When Context is Approaching Limits

If orchestrator context reaches 40-60%:

1. **Compress all phase summaries** to bullet points
2. **Delegate remaining complex tasks** to subagents
3. **Reference Plan by path** instead of content
4. **Create/update STATE.md** as external memory
5. **Run STOP-ASSESS-UPDATE-DECIDE cycle** before each action

### When Context Exceeds 60%

If orchestrator context exceeds 60%:

1. **STOP current execution**
2. **Update STATE.md** with full progress **and User Restart Prompt section** (concrete values, no placeholders)
3. **Report to user** — include the restart prompt so they can copy-paste it:
   ```
   **Context Limit Approaching**

   I've captured current progress in STATE.md.
   To continue with fresh context, start a new conversation and paste
   the restart prompt below. I'll use Protocol 6 to resume seamlessly.

   Current state:
   - Phase: [X]
   - Stage: [Y]
   - Last checkpoint: [CPn] - [status]
   - Next action: [description]

   **To resume in a new session, paste this:**
   > Resume the [Project Title] analysis. Plan: `[plan path]`. State: `[STATE.md path]`. Currently at Stage [N] ([Stage Name]) — next step is [task description].
   ```
4. **Await user direction** (new session or continue with degraded quality)

---

## Integration with Workflow

### Phase-Level Context Management

| Phase | Context Strategy | Compression Point |
|-------|-----------------|-------------------|
| Phase 1 | Delegate discovery to subagents | End of Phase 1 |
| Phase 2 | Create Plan (main context) | After Plan creation |
| Phase 3 | Delegate fetch/clean to subagents | After CP2 passes |
| Phase 4 | Delegate analysis to subagents | After each stage |
| Phase 5 | Orchestrator synthesizes | Before delivery |

### Stage-Level Context Actions

| Stage | Start Action | End Action |
|-------|--------------|------------|
| 1 | Load user request | Compress to scope summary |
| 2 | Delegate to Explore subagent | Compress findings |
| 3 | Delegate to Explore subagent(s) | Compress caveats |
| 4 | Create Plan (main context task) | Reference Plan by path |
| 5 | Delegate to general-purpose subagent | Compress CP1 results |
| **5-QA** | Delegate to code-reviewer | Keep PASSED/WARNING/BLOCKER + revision count |
| 6 | Delegate to general-purpose subagent | Compress CP2 results |
| **6-QA** | Delegate to code-reviewer | Keep PASSED/WARNING/BLOCKER + revision count |
| 7 | Delegate transformation tasks | Compress each CP3 result |
| **7-QA** | Delegate to code-reviewer (per script) | Keep severity summary |
| 8 | Delegate visualization tasks | Keep file paths only |
| **8-QA** | Delegate to code-reviewer | Keep severity summary |
| 9 | Delegate notebook creation | Keep path only |
| 10 | Aggregate QA findings from Stages 5-8 | Keep QA summary |
| 11 | Orchestrator creates report | - |
| 12 | Orchestrator runs final review | Update STATE.md |

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
| 40-60% | None | Continue with delegation, monitor closely |
| 40-60% | Minor repetition | Delegate next task to subagent, update STATE.md |
| 60-75% | None | STOP, update STATE.md, report to user |
| 60-75% | Forgetting context | STOP, compress findings, update STATE.md |
| 60-75% | Contradictions | STOP, do not proceed, compress or restart |
| 75%+ | Any | Save state, recommend session restart |

### Context Preservation Priority

When compressing or deciding what to keep, prioritize in this order:

| Priority | Content | Action |
|----------|---------|--------|
| 1 (NEVER LOSE) | Original user request | Keep verbatim, never summarize away |
| 2 (CRITICAL) | Current stage and blockers | Keep current, can summarize past |
| 3 (HIGH) | Key decisions made | Keep decision + rationale |
| 4 (MEDIUM) | Phase summaries | Can compress to bullets |
| 5 (LOW) | Detailed findings | Delegate to subagents |
| 6 (DISCARD) | Intermediate reasoning | Let go |

### Proactive Quality Maintenance

**Every 3 orchestrator turns, assess (STOP-ASSESS-UPDATE-DECIDE):**

1. **Am I repeating myself?** → Sign of degradation
2. **Do I remember the original request clearly?** → If fuzzy, re-read
3. **Can I state the current stage and next action?** → If unclear, check STATE.md
4. **Are my responses getting longer without more content?** → Sign of inefficiency

**If 1+ check fails:** Log assessment and increase monitoring frequency.
**If 2+ checks fail:** Trigger compression protocol immediately.
**If 3+ checks fail:** Update STATE.md immediately, delegate all remaining tasks.

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
To ensure high-quality completion, please start a new conversation.
Reference: `research/[project]/STATE.md`

I'll use Protocol 6 (Session Recovery) to resume with fresh context.
```

---

## Self-Monitoring Protocol

### Context Utilization Reporting

The `context-reporter` hook provides deterministic utilization measurements on every orchestrator turn. The injected message format is:

```
Context utilization [SEVERITY]: XXXk / 200k tokens (YY%)
```

Where **SEVERITY** = OK (<40%) | MODERATE (40-60%) | HIGH (60-75%) | CRITICAL (75%+). Use the reported percentage directly for gating decisions — no estimation needed.

### Self-Assessment Checklist (Every 3 Turns)

Run this checklist every 3 orchestrator turns as part of the **STOP-ASSESS-UPDATE-DECIDE** cycle:

```markdown
**Self-Assessment (Turn [N]):**
1. [ ] Can state original request verbatim?
2. [ ] Can state current stage and next action?
3. [ ] Not repeating earlier information?
4. [ ] Response efficiency acceptable?

Failures: [count] → [action taken]
```

### STOP-ASSESS-UPDATE-DECIDE Cycle

At every self-assessment checkpoint (every 3 turns) and at every stage transition:

```
1. STOP: Pause before next action
2. ASSESS: Run 4-question checklist + check reported utilization
3. UPDATE: Persist state to STATE.md if needed (≥40% or any failures)
4. DECIDE: Continue, delegate, report, or restart based on utilization
```

### Utilization Gate Actions

| Threshold | Required Action |
|-----------|-----------------|
| 40% | Delegate ALL remaining complex tasks to subagents |
| 60% | Update STATE.md IMMEDIATELY, STOP, report to user |
| 75% | STOP, save state, offer session restart to user |

### Self-Assessment Scoring

| Failures | Action |
|----------|--------|
| 0 | Continue normally |
| 1 | Log assessment, continue with increased monitoring |
| 2 | Trigger compression: delegate next complex task |
| 3 | Update STATE.md immediately, compress phase summaries |
| 4 | STOP, update STATE.md, recommend session restart |

---

## Quick Reference

### Context Budget Summary

```
Orchestrator Target: 25-35% utilization (conservative)
Subagent Fresh Start: 0% (PEAK quality every time)

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

STOP-ASSESS-UPDATE-DECIDE Triggers:
- Every 3 orchestrator turns
- Every stage transition
- After every subagent return
- Before any complex reasoning task
```

### Compression Quick Guide

```
Verbose → Compressed

"I found that the endpoint..." → "Endpoint: [path] ([years])"
"The key variables are..." → "Vars: [list]"
"This is important because..." → [omit unless decision-relevant]
"The code executed successfully..." → "Status: PASSED"
"Here is the full output..." → "[summary only]"
```
