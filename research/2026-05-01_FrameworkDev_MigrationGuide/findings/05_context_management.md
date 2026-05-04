# Finding 05: Context Window Management, Compaction, and Monitoring

## Overview

DAAF implements a comprehensive, multi-layered context management system designed to prevent quality degradation in long-running AI-assisted research sessions. Rather than relying on Claude Code's built-in automatic compaction (which DAAF explicitly disables), DAAF builds its own context monitoring, threshold-gated action system, and persistence mechanisms that work across orchestrator and subagent boundaries.

The system has three pillars:
1. **Active monitoring** — A shell hook (`context-reporter.sh`) that periodically injects utilization data into the conversation
2. **Behavioral rules** — Threshold-gated actions defined in `CLAUDE.md` that govern what agents do at each utilization level
3. **Persistence mechanisms** — STATE.md, SESSION_NOTES.md, LEARNINGS.md, and preliminary notes files that preserve state across context boundaries

---

## 1. Context Reporter Hook — Complete Technical Analysis

### Source File
`/daaf/.claude/hooks/context-reporter.sh` (174 lines)

### Purpose
Injects context window utilization data and timestamps into Claude's conversation so the model can make informed decisions about delegation, state persistence, and session recovery.

### How It Measures Utilization

The hook calculates token usage by parsing the **JSONL transcript file** that Claude Code maintains for each session. It uses a performance-optimized approach:

```bash
# Uses tail -50 to read only the end of the transcript, avoiding full-file parsing
tokens=$(tail -50 "$transcript" 2>/dev/null | jq -s '
    [.[] | select(
        .message.usage and
        .isSidechain != true and
        .isApiErrorMessage != true
    )] | last |
    if . then
        (.message.usage.input_tokens // 0) +
        (.message.usage.cache_read_input_tokens // 0) +
        (.message.usage.cache_creation_input_tokens // 0)
    else 0 end
' 2>/dev/null)
```

**Token calculation formula:** The hook sums three components from the most recent non-sidechain, non-error message's usage data:
- `input_tokens` — Direct input tokens
- `cache_read_input_tokens` — Tokens read from prompt cache
- `cache_creation_input_tokens` — Tokens written to prompt cache

This gives a comprehensive view of the total context consumed, including cached content.

**Percentage calculation:**
```bash
pct=$((tokens * 100 / MAX_CONTEXT))
```

Where `MAX_CONTEXT` is the context window size read from a shared cache file (see below).

### Context Window Size Discovery

The hook needs to know the model's context window size, but this information is not provided in the hook's input payload. The solution is a **two-component cache system**:

1. **`context-bar.sh` (statusline script)** receives the `context_window.context_window_size` field in its JSON input and writes it to `/tmp/claude-ctx-window-{session_id}`.

2. **`context-reporter.sh`** reads from that cache file. Fallback chain:
   - First: Try `/tmp/claude-ctx-window-{session_id}` (exact session match)
   - Second: Try the most recent `/tmp/claude-ctx-window-*` file (for subagents with different session IDs — typically finds the parent orchestrator's cache)
   - Third: Default to 200,000 tokens as a last resort

This design is critical for **subagent support**: subagents run with different session IDs, so their session-specific cache won't exist. The fallback to the most recent cache from any session (typically the parent orchestrator) ensures subagents report utilization against the correct context window size.

### Dual-Threshold Severity System

The hook implements a dual-trigger threshold system where **either percentage OR absolute token count triggers the threshold, whichever fires first**. This design caps effective session length on large context windows (like the 1M window DAAF currently uses) where percentage thresholds alone would allow excessive token usage.

```bash
if   [[ $pct -ge 75 ]] || [[ $used_k -ge 250 ]]; then severity="CRITICAL"
elif [[ $pct -ge 60 ]] || [[ $used_k -ge 200 ]]; then severity="HIGH"
elif [[ $pct -ge 40 ]] || [[ $used_k -ge 150 ]]; then severity="ELEVATED"
else                                                    severity="NOMINAL"
fi
```

| Severity | Percentage Trigger | Absolute Token Trigger | Whichever Fires First |
|----------|-------------------|----------------------|----------------------|
| NOMINAL | < 40% | < 150k tokens | Neither |
| ELEVATED | >= 40% | >= 150k tokens | Either |
| HIGH | >= 60% | >= 200k tokens | Either |
| CRITICAL | >= 75% | >= 250k tokens | Either |

**Why absolute thresholds matter:** On a 1M token context window, 40% = 400k tokens. The CHANGELOG explicitly notes: "While Opus and Sonnet can now handle token windows of up to 1m tokens, there's A LOT of evidence that its performance deteriorates quickly -- and regardless, costs skyrocket per turn because of it." The absolute thresholds ensure ELEVATED fires at 150k tokens (15% of 1M) rather than waiting until 400k tokens (40% of 1M).

### Output Format

The hook emits a single-line message:
```
Context utilization [SEVERITY]: {used_k}k / {max_k}k tokens ({pct}%) | {timestamp}
```

Example: `Context utilization [ELEVATED]: 155k / 1000k tokens (15%) | 2026-05-01 14:23:45 UTC`

### Injection Mechanism (Two Events)

The hook is registered for **two events** in `settings.json`, with different output formats:

1. **`UserPromptSubmit` event**: Output goes to stdout, which Claude Code injects as a `<user-prompt-submit-hook>` block visible to the model.

2. **`PreToolUse` event**: Output is formatted as JSON with `additionalContext`, which Claude Code injects as a `<system-reminder>` block before the tool executes:
   ```json
   {
     "hookSpecificOutput": {
       "hookEventName": "PreToolUse",
       "additionalContext": "Context utilization [ELEVATED]: 155k / 1000k tokens (15%) | ..."
     }
   }
   ```

### Rate Limiting

Both events share a **single 60-second injection gate** per session, implemented via an epoch-timestamp cache file (`/tmp/claude-ctx-ts-{session_id}`). Whichever event fires first resets the timer for both. This prevents redundant context injection across rapid tool calls and user messages while ensuring the model gets periodic utilization updates.

```bash
INJECT_INTERVAL=60  # seconds between injections
NOW=$(date +%s)
LAST_INJECT=0
[[ -f "$LAST_INJECT_FILE" ]] && LAST_INJECT=$(cat "$LAST_INJECT_FILE" 2>/dev/null)

if [[ $((NOW - LAST_INJECT)) -lt $INJECT_INTERVAL ]]; then
    exit 0  # Skip injection
fi
```

### Subagent Support

Subagents run with different session IDs from the parent orchestrator. The hook handles this through:
- **Context window size fallback**: Falls back to the most recent `/tmp/claude-ctx-window-*` file from any session
- **Independent rate limiting**: Each session has its own rate-limit file, so subagent injections don't interfere with orchestrator injections
- **Same threshold logic**: Subagents evaluate the same NOMINAL/ELEVATED/HIGH/CRITICAL thresholds

### Error Safety

The hook is designed to **never block tool execution**:
- Uses `set -u` (catch unset variables) but deliberately omits `set -e` (exit on error)
- All error paths exit with code 0
- All jq and file operations have `2>/dev/null` redirections
- Unknown hook events fall through to a no-op case with `exit 0`

### Additional Feature: Model Caching

The hook also caches the model name from the transcript to `/tmp/claude-model-{session_id}`, which `audit-log.sh` reads to include the model in audit entries. This is a one-time operation per session.

---

## 2. Context Quality Curve — CLAUDE.md Rules

### Source File
`/daaf/CLAUDE.md`, section "Context & Session Health"

### Threshold-Action Table (Orchestrator)

| Utilization | Status | Required Action |
|-------------|--------|-----------------|
| < 40% and < 150k tokens | NOMINAL | Continue normally |
| >= 40% or >= 150k tokens | ELEVATED | Monitor closely; consider how realistic the scope of remaining work is and how to redelegate work |
| >= 60% or >= 200k tokens | HIGH | Complete current atomic unit at full quality; report back to user; do not start new stages of work; Orchestrator must update STATE.md with restart prompt |
| >= 75% or >= 250k tokens | CRITICAL | Cease work immediately and report back to user; Orchestrator must finalize STATE.md |

### Subagent-Specific Actions

| Status | Subagent Action |
|--------|-----------------|
| NOMINAL | Continue executing the assigned task normally |
| ELEVATED | Assess remaining work honestly. If completion is uncertain, begin structuring return output — summarize key findings so far, note what remains. Continue working but prioritize completing the most valuable deliverables first |
| HIGH | **Return early.** Complete only the current atomic unit. Format return output with: (1) completed work and findings, (2) clear list of incomplete items, (3) any file paths created or modified. Do not start new work items |
| CRITICAL | **Stop immediately and return.** Report whatever has been completed, clearly mark output as incomplete, list all remaining work items |

### Early Return Protocol

When subagents return early due to context pressure, they must structure their response for seamless continuation:

1. All file paths created or modified (absolute paths)
2. Summary of completed analysis or findings
3. Explicit list of tasks not yet started or partially completed
4. Any decisions made or assumptions applied that the next agent needs to know
5. Confidence assessment of completed work

**STATE.md responsibility:** Subagents do NOT write STATE.md directly — that is the orchestrator's responsibility. Subagents returning early should include enough structured information for the orchestrator to update STATE.md accurately.

### Symptoms of Context Degradation

DAAF defines observable symptoms that may indicate context degradation even before thresholds fire:

| Symptom | Severity | Indicates |
|---------|----------|-----------|
| Repeating information already stated | MEDIUM | 40-60% utilization |
| Forgetting earlier decisions | HIGH | 60%+ utilization |
| Generating contradictory outputs | CRITICAL | 70%+ utilization |
| Incomplete or truncated responses | CRITICAL | Near limit |
| Losing track of current stage | HIGH | Context fragmentation |
| Mixing up file names or paths | MEDIUM | Working memory strain |

**Rule:** If degradation symptoms are observed, treat as equivalent to HIGH regardless of actual utilization — prepare for restart immediately.

### Quality Primacy Rule

> "Context management is NEVER about reducing the quality or completeness of work. Subagent prompt fidelity, documentation completeness, and inlined context are non-negotiable regardless of utilization level. If maintaining quality means reaching a restart point sooner, that is the correct outcome."

This means DAAF would rather restart a session than produce lower-quality output. Thresholds control WHEN to restart, never WHETHER to maintain quality.

### Behavioral Guardrails

> "What thresholds control: Utilization determines WHEN to restart, never WHETHER to maintain fidelity. At ELEVATED, delegate more execution to subagents but construct prompts with the same thoroughness as at NOMINAL."

> "STATE.md fidelity is critical: When updating STATE.md under context pressure, resist the urge to abbreviate. STATE.md is what the next session reads to resume — every shortcut taken here becomes a gap in the recovery context."

---

## 3. Orchestrator Context Budget

### Source File
`/daaf/.claude/skills/daaf-orchestrator/SKILL.md`, section "Orchestrator Context Budget"

### What Stays in Main Context (~2,000 words max)

| Content Type | Max Size | Rationale |
|--------------|----------|-----------|
| Original user request | <500 words | Verbatim reference for alignment |
| Mode classification | ~50 words | Guide workflow execution |
| Scope decisions | ~100 words | Bound the work |
| Phase summaries | ~200 words each | Track progress |
| Current stage + blockers | ~100 words | Know where we are |
| STATE.md | Full document | Know current status of project execution |
| Plan.md | Full document | Know overarching work strategy and goals |
| Plan_Tasks.md | Paths only | Be ready to distribute tasks to subagents |
| Error history | ~200 words | Avoid repeating failures |

### What Gets Delegated to Subagents

- Skill invocations (skills add 5K-20K tokens)
- Data exploration (iterative searching fills context)
- Source deep-dives (reference docs are large)
- Code-heavy analysis (code + output consumes tokens)
- Visualization generation (plot code is verbose)
- QA aggregation (QA findings across stages are voluminous)

### What Never Goes in Orchestrator Context

- Full skill content (let subagents load)
- Raw data samples (only shapes and summaries)
- Complete code files (only references)
- Full error tracebacks (only summaries)

### Plan_Tasks.md Extraction Protocol

Plan_Tasks.md can be 1000+ lines. The orchestrator is instructed to **never read the full file into context**. Instead:

1. Read the Task Index table (first ~30-40 lines)
2. Identify the target task by step number or name
3. Search for the specific task header (e.g., `### Task 1.1: fetch-ccd-schools`)
4. Read only that task block (typically 20-40 lines per block)

This is a concrete example of DAAF's "on-demand loading" pattern to preserve context.

---

## 4. Compaction Behavior — Claude Code Platform Feature

### What Claude Code Does Natively

Claude Code has built-in automatic compaction that triggers when context approaches ~83.5% of the window (~167K tokens on a 200K window, or ~835K on a 1M window). When triggered, it:

1. Takes the entire conversation history
2. Sends it to a separate model call with a summarization prompt
3. Replaces the full history with a condensed summary
4. Starts a new internal conversation with the summary as context

There is also a manual `/compact` command that users can invoke proactively.

### DAAF's Relationship to Compaction: Explicitly Disabled

**DAAF explicitly instructs users to disable auto-compaction.**

From `/daaf/README.md` (line 79):
> Set **Auto-compact** to **False** and **Verbose output** to **True** via `/config`.

From `/daaf/user_reference/01_installation_and_quickstart.md` (line 153):
> **"Auto-compact"** -- set to **False**. DAAF manages its own context carefully; auto-compaction can disrupt its orchestration and cause unexpected behavior.

### Why DAAF Disables Auto-Compaction

DAAF does not rely on compaction because:

1. **Information loss is unacceptable for research pipelines.** Compaction summaries inherently lose details. For a multi-stage research pipeline where methodology decisions, data caveats, coded values, and validation results must be precisely tracked, lossy compression risks introducing errors.

2. **DAAF has its own context management.** The dual-threshold system (context-reporter + behavioral rules) provides finer-grained control than compaction's single trigger point. DAAF can take graduated actions (delegate more, return early, persist state) rather than the binary "compress everything" approach.

3. **Compaction disrupts orchestration state.** The orchestrator maintains mental state about current stage, pending decisions, and subagent outcomes. Compaction replaces this with a summary that may not preserve the precise decision-state the orchestrator needs.

4. **DAAF uses file-based persistence instead.** Rather than relying on in-context summaries, DAAF writes critical information to disk (STATE.md, preliminary notes, LEARNINGS.md) and re-reads it when needed. This is lossless and survives across sessions.

### Migration Implication

Any alternative harness must either:
- **Provide a way to disable auto-compaction** (preferred — DAAF's own context management is more appropriate for structured workflows)
- **Provide compaction hooks** that let DAAF control what gets summarized and what gets preserved
- **Accept that compaction may occur** and build recovery mechanisms (re-reading STATE.md, re-loading critical context from disk) — but this degrades the orchestration experience

---

## 5. Subagent Context Isolation

### How Claude Code Subagents Work

In Claude Code, subagents (invoked via the `Agent` tool) operate with **separate context windows** from the parent orchestrator.

### What Subagents See

**CLAUDE.md**: Yes. Claude Code automatically includes CLAUDE.md in every agent's system prompt — both the orchestrator and all subagents. This is why CLAUDE.md contains the universal context monitoring rules — they apply to all agents equally.

**Named agent protocol file**: Yes. When a named agent (e.g., `subagent_type: "research-executor"`) is invoked, Claude Code loads the agent's `.md` file from `.claude/agents/` and applies its `tools` and `permissionMode` settings.

**Parent conversation history**: No. Subagents do NOT see the parent orchestrator's conversation history. They receive only:
1. The system prompt (CLAUDE.md + agent protocol file)
2. The orchestrator's prompt message (which the orchestrator constructs with all necessary context)
3. Their own conversation history (tool calls and responses during their execution)

**Skills**: Subagents load skills themselves by calling the Skill tool. The orchestrator does NOT pre-load skills into subagent context.

### Context Budget Implications

From `/daaf/.claude/agents/README.md` (line 31):
> "The orchestrator context window is shared across the entire pipeline. A single verbose subagent return (4,000+ words) consumes ~8,000 tokens. Over 10 subagent round-trips in a stage, that's 80,000 tokens — a meaningful share of the orchestrator's capacity — consumed by output alone."

This is why DAAF enforces strict output size discipline:
- **General agents**: 2,000-word hard cap on return output
- **data-ingest agent**: 3,500-word cap (exception because profiling findings feed directly into skill authoring)

### What Happens When a Subagent Exhausts Its Context

Per CLAUDE.md: "Subagents that exhaust their context without reporting back waste the orchestrator's context budget (which must re-dispatch the work) and risk losing completed work."

The early return protocol (documented in Section 2 above) is DAAF's defense against this. Subagents are expected to monitor their own utilization and return structured output before exhaustion.

### Subagent Context Monitoring

Subagents receive the same `context-reporter` utilization injections as the orchestrator because:
1. `context-reporter.sh` is registered on the `PreToolUse` event with an empty matcher (`""`) in `settings.json`, meaning it fires for ALL tool uses — including those made by subagents
2. The hook's context window size fallback mechanism (see Section 1) ensures subagents get accurate window size data even though they have different session IDs

---

## 6. Session State Persistence Across Context Boundaries

DAAF uses multiple persistence mechanisms, each serving a different purpose and mode.

### STATE.md — Primary Session State (Full Pipeline, Data Onboarding, Revision)

**Template**: `/daaf/agent_reference/STATE_TEMPLATE.md` (Full Pipeline), `/daaf/agent_reference/STATE_TEMPLATE_ONBOARDING.md` (Data Onboarding)

**Purpose**: "Persistent memory across context windows and session recovery." STATE.md is the primary document the orchestrator reads when resuming a session.

**Contents** (Full Pipeline version — comprehensive):
- Current Position (phase, stage, status)
- Session Metadata (DAAF version, model ID, session dates)
- Checkpoint Status (CP1-CP4 primary, QA1-QA4b secondary)
- Plan Validation (Stage 4.5 status)
- Data Status (datasets, rows, status)
- Hypothesis Assessment Progress
- Key Decisions Made (runtime decisions)
- Transformation Progress (per-script tracking with QA status)
- Blockers (execution and QA)
- Error Budget Consumed (per-stage and session total)
- Deviations Applied
- Runtime Risks
- QA Findings Summary
- Discovery Preliminary Notes (file paths and status)
- Citations Accumulated
- Final Review Log (Stage 12)
- Pending Learning Signals (buffer for LEARNINGS.md)
- Next Actions
- Files Created This Session
- Session History
- Velocity Metrics
- Session Continuity (last action, next action, context snapshot, restart prompt)

**When Created**: Stage 4 (Plan Creation) or Stage DI-2 (Data Onboarding project setup)

**When Updated**: After each checkpoint, stage completion, key decision, blocker, error budget consumption, deviation, session break, learning signal, citation extraction, QA finding, runtime risk discovery, and at various QA aggregation points.

**Context Snapshot Field**: STATE.md includes an explicit "Orchestrator Utilization" field that records the actual utilization percentage from the context-reporter hook, plus a 5-bullet key findings summary, open questions, and pending user decisions.

### The Restart Prompt Pattern

STATE.md contains a "User Restart Prompt" section — a pre-formatted prompt that the user copies after running `/clear` to resume the session:

```
> Resume the [Project Title] analysis. Plan: `[exact plan path]`.
> Plan Tasks: `[exact Plan_Tasks path]`. State: `[exact STATE.md path]`.
> Currently at Stage [N] ([Stage Name]) — next step is [task description].
```

**When Updated**: Whenever hitting HIGH/CRITICAL utilization gates (>= 60%/200k or >= 75%/250k tokens), before planned session breaks, or when the user decides to stop.

**Rule**: Use concrete values — no brackets or placeholders in the actual prompt.

### Resumption Instructions (Agent Reference)

STATE.md also contains detailed resumption instructions for the orchestrator, including:
1. Read STATE.md first (primary recovery document)
2. Locate Plan at specific path
3. Read Plan SELECTIVELY (specific sections only, not the entire file)
4. Current phase, stage, next task
5. Required Plan sections for next task
6. Prior findings to review

This acts as a "how to resume" recipe that the recovering orchestrator can follow mechanically.

### SESSION_NOTES.md — Lightweight State (Ad Hoc, Framework Development)

**Source**: `/daaf/.claude/skills/daaf-orchestrator/references/ad-hoc-collaboration-mode.md`, lines 247-317

**Purpose**: Lightweight continuity for modes that don't use the full STATE.md machinery.

**When Created**: At the first substantive milestone — a task plan produced, a key decision made, a deliverable completed, or context reaching ELEVATED.

**Contents**:
```markdown
# Session Notes: {Topic}
**Started:** YYYY-MM-DD
**Workspace:** {PROJECT_DIR}

## Accomplishments
- [What was completed, with file paths]

## Key Decisions
- [Decisions made, with rationale]

## In Progress
- [Current work when session ended]

## Open Questions
- [Unresolved questions or next steps]

## AI Disclosure
[AI contribution disclosure]
```

**When to Update**: After producing a plan or advisory outline, making a key decision, completing a deliverable, changing topic substantially, reaching ELEVATED context, signaling session end, or before mode escalation.

**Context Recovery**: At context thresholds, the orchestrator updates SESSION_NOTES.md with current state, summarizes accomplishments, suggests the user start a fresh session, and points to SESSION_NOTES.md as the continuity mechanism.

### LEARNINGS.md — Cross-Session Learning Signals

**Created**: Stage 4 (Plan Creation), as a skeleton alongside Plan.md, Plan_Tasks.md, and STATE.md. Gate G4 requires all four files to exist.

**Purpose**: Accumulate insights from subagent execution that can inform future work — data quirks discovered, access patterns, performance notes, methodology decisions.

**Population Pattern**:
1. Subagents return "learning signals" as part of their output (categorized as Access, Data, Method, Perf, or Process)
2. The orchestrator buffers these in STATE.md's "Pending Learning Signals" section
3. Buffer is flushed to LEARNINGS.md at phase boundaries, after blocker resolution, after debugging, and at utilization gates
4. STATE.md tracks: last flushed timestamp, total signals captured, total flushed

**Cross-Session Value**: When recovering a session, the orchestrator reads LEARNINGS.md (Step 2b of Session Recovery) to "prevent re-encountering resolved issues," prioritizing entries tagged with the current or upcoming stages.

**Immutability**: LEARNINGS.md files are project artifacts that should NOT be modified by framework-engineer or other agents. They serve as historical records.

### Preliminary Notes — Lossless Subagent Returns

**Purpose**: Persist rich, structured findings from discovery and profiling agents at full fidelity to disk, so downstream agents can access them without depending on the orchestrator's compressed inline summaries.

**Location**: `output/preliminary_notes/` in the project directory

**Pattern**:
1. Discovery/profiling agent completes and returns findings to the orchestrator
2. The orchestrator writes the FULL, UNMODIFIED return text to a preliminary notes file
3. The orchestrator prepends a provenance header:
   ```
   <!-- Preliminary Notes: auto-generated by orchestrator from {agent_type} return -->
   <!-- Stage: {stage_identifier} | Agent: {agent_name} | Generated: {ISO_timestamp} -->
   ```
4. The orchestrator confirms the file was written successfully — **this is a gate condition**: do not proceed until the file exists on disk and contains the complete agent return
5. The orchestrator then extracts a compressed summary (status, 3-5 key bullets, file locations, confidence, escalation items) for its own working memory
6. The orchestrator discards from working memory: verbose explanations, intermediate steps, full code blocks, raw data samples
7. Downstream agents receive the preliminary notes **file path** and read the lossless version themselves

**Gate Conditions** (Full Pipeline):
| Stage | Agent | File Path |
|-------|-------|-----------|
| 2 | search-agent | `output/preliminary_notes/{date}_stage2_data-exploration.md` |
| 3 | source-researcher | `output/preliminary_notes/{date}_stage3_{source}_source-research.md` |
| 3.5 | research-synthesizer | `output/preliminary_notes/{date}_stage3.5_research-synthesis.md` |

All rows must show WRITTEN before Stage 4 can proceed.

**Gate Conditions** (Data Onboarding): Similar pattern with parts A-D, all must be WRITTEN before DI-7 skill authoring.

---

## 7. Context-Aware Patterns Throughout DAAF

### Progressive Disclosure

DAAF's architecture is built around loading documents at the right time for the right task, not all at once. The orchestrator skill defines a **Documentation Loading Decision Tree** that maps each mode and stage to the specific reference files to load:

```
Mode Confirmed
    |
    +-- Data Onboarding Mode
    |   +-- Read: data-onboarding-mode.md
    |          +-- Stage DI-2: Read STATE_TEMPLATE_ONBOARDING.md
    |          +-- Profiling: Read WORKFLOW_PHASE_DO_PROFILING.md
    |          +-- Skill Authoring: Read WORKFLOW_PHASE_DO_AUTHORING.md
    |
    +-- Full Pipeline Mode
    |   +-- Read: full-pipeline-mode.md
    |          +-- Phase 1: WORKFLOW_PHASE1_DISCOVERY.md
    |          +-- Phase 2: WORKFLOW_PHASE2_PLANNING.md
    |          +-- Phase 3: WORKFLOW_PHASE3_ACQUISITION.md
    |          +-- Phase 4: WORKFLOW_PHASE4_ANALYSIS.md
    |          +-- Phase 5: WORKFLOW_PHASE5_SYNTHESIS.md
    ...
```

From the CHANGELOG:
> "This enables far better progressive disclosure: the orchestrator loads only the reference file for the confirmed engagement mode, rather than ingesting thousands of lines of workflow documentation upfront. Each mode reference file is self-contained with its own invocation templates, gate definitions, PSU templates, and escalation triggers."

**CLAUDE.md itself documents this principle**: "DAAF's progressive disclosure architecture loads relevant documents at the right time for the right task, not all at once. When a loading trigger fires, the document must be read completely."

### Skill Loading via Subagents (Not Orchestrator)

Skills are loaded **by subagents**, not by the orchestrator:
1. Orchestrator creates Agent call with agent protocol and skill name in the prompt
2. Subagent receives prompt and reads its agent protocol file
3. Subagent calls skill tool to load specialized knowledge into its own context
4. Subagent follows agent protocol using the skill's guidance
5. Subagent returns findings to orchestrator

**What the orchestrator does NOT do:**
- Does not call the skill tool directly in orchestrator context
- Does not pre-load all skills at conversation start
- Does not copy skill content into prompts to subagents

Skills add 5K-20K tokens each. By having subagents load them, the cost is borne by the subagent's separate context window, not the orchestrator's.

**Exception**: Ad Hoc Collaboration mode and Framework Development mode load some skills directly in the orchestrator context (e.g., `data-scientist`, `skill-authoring`, `agent-authoring`) because these modes need the orchestrator to have direct domain knowledge for the conversation.

### Subagent Return Processing Protocol

When a subagent returns findings to the orchestrator:

1. **Verify** against expected output format
2. **Write to disk** (if workflow requires lossless capture): Full, unmodified return text to preliminary notes file with provenance header. Confirm file exists — **gate condition**.
3. **Extract** for orchestrator working memory: Status, key findings (3-5 bullets), file locations, confidence level, issues requiring escalation
4. **Discard** from working memory: Verbose explanations, intermediate steps, full code blocks, raw data samples
5. **Store** summarized key findings + preliminary notes file path in working memory

This creates a two-tier information architecture:
- **Orchestrator tier**: Compressed summaries for coordination decisions
- **Disk tier**: Lossless full findings for downstream agents to read

### Output Size Discipline

All agents have a hard word cap on return output:
- **General agents**: 2,000 words maximum
- **data-ingest agent**: 3,500 words (exception for skill authoring)

Specific rules:
- Do NOT include raw execution logs, data samples, table displays, full checkpoint output, QA script code
- Script files are the archive; the agent return is the signal
- Execution logs are already appended to script files on disk by `run_with_capture.sh`
- Reference files by path — do not reproduce their contents

### Context Recovery via Session Recovery Protocol

The session recovery procedure (`/daaf/.claude/skills/daaf-orchestrator/references/session-recovery.md`) defines how to resume after context has been cleared:

1. **Locate Project**: Search `research/` for matching project folder
2. **Read STATE.md**: Full document — primary recovery input
3. **Read LEARNINGS.md**: Recover accumulated insights from prior sessions
4. **Read Plan.md SELECTIVELY**: Only recovery sections (Original Request, Goal & Context, Decisions Log, Risk Register, Current Status, Transformation Sequence summary)
5. **Verify File System State**: Check which artifacts exist vs. expected
6. **Identify Resume Point**: From STATE.md's Current Position and Next Actions
7. **Present Recovery Summary**: Show user what's complete and what remains

**Stale State Detection**: If STATE.md's timestamp is older than the most recent script file, the state file may be stale (prior session crashed before updating). The recovery procedure reconstructs position from the filesystem and git history.

**On-Demand Plan Loading**: After recovery, additional Plan.md or Plan_Tasks.md sections are loaded only when needed — not preloaded.

### Dispatch as Context Preservation

DAAF uses subagent dispatch explicitly as a context preservation strategy:

From the Ad Hoc Collaboration mode:
> "Dispatch generously to subagents. Each subagent gets a fresh context window. For tasks that involve code execution, deep research, or formal review, dispatching preserves orchestrator context for the ongoing conversation."

> "Limit orchestrator skill loading. The orchestrator loads data-scientist at session start. Additional skills should generally be loaded by subagents. If the orchestrator has loaded more than 2-3 skills directly, prefer dispatching to subagents for subsequent tasks to avoid context pressure."

---

## 8. Environment Configuration for Context Management

### settings.json Environment Variables

DAAF configures several environment variables in `/daaf/.claude/settings.json` that affect context behavior:

```json
{
  "env": {
    "ANTHROPIC_MODEL": "claude-opus-4-6[1m]",
    "CLAUDE_CODE_EFFORT_LEVEL": "high",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ENABLE_PROMPT_CACHING_1H": "1"
  }
}
```

| Variable | Value | Purpose |
|----------|-------|---------|
| `ANTHROPIC_MODEL` | `claude-opus-4-6[1m]` | Explicitly requests the 1M context window variant |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | `1` | Disables Claude Code's automatic memory feature (DAAF manages its own state persistence) |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | `1` | Prevents background tasks that could consume context or cause unexpected behavior |
| `ENABLE_PROMPT_CACHING_1H` | `1` | Enables 1-hour prompt caching for token efficiency |
| `showThinkingSummaries` | `true` | Shows thinking summaries (useful for following reasoning) |

**Note**: The auto-compact disable is handled at the user level via the `/config` menu, not in settings.json. DAAF's README and installation guide instruct users to set "Auto-compact" to "False" in the `/config` menu.

### context-bar.sh Statusline

The statusline script (`/daaf/.claude/scripts/context-bar.sh`) provides a persistent visual display of context utilization in the terminal:

- Shows a 10-segment progress bar with color-coded fill
- Displays percentage and total token counts (e.g., "15% of 1000k tokens")
- Includes a reminder: "lower session context use enhances performance"
- Shows the model name, directory, git branch, and last user message
- Handles OpenRouter models by querying the OpenRouter API for actual context window size (Claude Code reports a hardcoded 200k default for third-party models)
- **Crucially**: Writes the context window size to `/tmp/claude-ctx-window-{session_id}`, which the context-reporter hook reads

---

## 9. Migration Considerations Summary

### What a Target Harness Must Provide

| Capability | DAAF Requirement | Claude Code Feature Used | Migration Path |
|-----------|-----------------|------------------------|---------------|
| **Context monitoring** | Periodic utilization injection into model conversation | PreToolUse hooks + JSONL transcript parsing | Need hook equivalent or polling mechanism; transcript/usage data access is critical |
| **Dual thresholds** | Both percentage AND absolute token triggers | Bash hook with session-scoped cache files | Can be reimplemented in any language with access to token usage data |
| **Subagent isolation** | Separate context windows for delegated work | Agent tool with named agents | Need equivalent of "spawn new conversation with its own context" |
| **Subagent monitoring** | Subagents receive same utilization injections | Hooks fire for all agents via empty matcher | Need hooks that fire in both parent and child contexts |
| **Auto-compact disable** | DAAF manages its own context; auto-compaction is harmful | User-level `/config` setting | Need ability to control or disable automatic context compression |
| **CLAUDE.md inheritance** | Universal rules apply to all agents | CLAUDE.md auto-loaded for orchestrator and all subagents | Need equivalent of "project-level instructions visible to all spawned agents" |
| **Named agents with protocols** | Agent behavior defined in `.md` files with tools and permission mode | `.claude/agents/*.md` with frontmatter | Need way to define agent roles with constrained tool access and behavioral protocols |
| **File-based state persistence** | STATE.md, LEARNINGS.md, preliminary notes written to disk | Standard file I/O | Portable — any harness with file write capability |
| **Prompt caching** | Reduce cost of repeated context loading | `ENABLE_PROMPT_CACHING_1H` env var | Depends on provider API; prompt caching is an Anthropic feature |
| **Hook system** | Multiple lifecycle hooks (PreToolUse, PostToolUse, SessionStart, SessionEnd, UserPromptSubmit) | `settings.json` hooks configuration | Need equivalent event system for lifecycle hooks |
| **Statusline / UI feedback** | Visual context bar in terminal | `statusLine` configuration in settings.json | Nice-to-have; not functionally required |

### Critical Dependencies on Claude Code

1. **JSONL transcript access** — The context-reporter hook reads the transcript file to calculate token usage. This is a Claude Code-specific file format and path. Alternative harnesses would need their own mechanism for accessing token usage data.

2. **Hook event model** — DAAF relies on five hook events (UserPromptSubmit, PreToolUse, PostToolUse, SessionStart, SessionEnd) with both stdout and JSON output modes. The PreToolUse additionalContext injection is particularly important for context monitoring.

3. **Subagent context isolation** — The Agent tool in Claude Code creates separate context windows. This is fundamental to DAAF's context budget strategy. Without it, skill loading and code execution would consume the orchestrator's context directly.

4. **Named agent definitions** — The `.claude/agents/*.md` pattern with frontmatter-defined tools and permission modes is Claude Code-specific. Any port would need to reimplement this agent definition and routing mechanism.

5. **CLAUDE.md auto-loading** — Claude Code automatically includes CLAUDE.md content in all agent system prompts. DAAF depends on this for universal rules (context monitoring, code style, safety). Alternative harnesses need an equivalent "project instructions always visible" mechanism.

---

## Sources

All findings are sourced from the DAAF codebase:

| Source | Path | Key Sections |
|--------|------|-------------|
| Context reporter hook | `/daaf/.claude/hooks/context-reporter.sh` | Full file (174 lines) |
| Context bar statusline | `/daaf/.claude/scripts/context-bar.sh` | Full file (201 lines) |
| CLAUDE.md | `/daaf/CLAUDE.md` | "Context & Session Health" section (lines 136-199), "Context-Efficient Reading" (lines 99-119) |
| Orchestrator skill | `/daaf/.claude/skills/daaf-orchestrator/SKILL.md` | "Orchestrator Context Budget" (lines 525-593), "Subagent Coordination" (lines 415-523) |
| Settings configuration | `/daaf/.claude/settings.json` | Full file (228 lines) |
| Session recovery | `/daaf/.claude/skills/daaf-orchestrator/references/session-recovery.md` | Full file (328 lines) |
| STATE.md template | `/daaf/agent_reference/STATE_TEMPLATE.md` | Full file (580 lines) |
| STATE.md template (Onboarding) | `/daaf/agent_reference/STATE_TEMPLATE_ONBOARDING.md` | Full file (522 lines) |
| Ad Hoc Collaboration mode | `/daaf/.claude/skills/daaf-orchestrator/references/ad-hoc-collaboration-mode.md` | "Session Notes and Continuity" (lines 247-345) |
| Framework Development mode | `/daaf/.claude/skills/daaf-orchestrator/references/framework-development-mode.md` | SESSION_NOTES.md pattern |
| Full Pipeline mode | `/daaf/.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` | "Plan_Tasks.md Extraction Protocol" (lines 857-864) |
| Agent README | `/daaf/.claude/agents/README.md` | "Output Size Discipline" (lines 22-31) |
| README | `/daaf/README.md` | Auto-compact instruction (line 79) |
| Installation guide | `/daaf/user_reference/01_installation_and_quickstart.md` | Auto-compact instruction (line 153) |
| CHANGELOG | `/daaf/CHANGELOG.md` | Context threshold rationale (line 348), progressive disclosure (lines 137-141), prompt caching (line 77) |
| Workflow Phase 2 | `/daaf/agent_reference/WORKFLOW_PHASE2_PLANNING.md` | LEARNINGS.md creation (lines 48-53) |
