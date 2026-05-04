## 8. Context Management and Monitoring

**Classification: DAAF-BUILT** -- Claude Code provides the JSONL transcript (from which token usage is calculated) and the hook system (through which monitoring data is injected into the conversation). Everything else -- the dual-threshold severity system, the graduated behavioral responses, the early-return protocol, the five persistence mechanisms, the compaction-avoidance strategy, the orchestrator context budget rules -- is DAAF's own architectural design, implemented entirely through shell scripts, markdown instructions, and file-based conventions.

**Criticality:** HIGH | **Interdependencies:** 5 (hook system, agent system, instruction loading, logging/audit, session management)

---

### Design Intent

LLM output quality degrades as context fills. This degradation is not a sharp cliff but a gradual erosion: the model begins repeating itself, forgetting earlier decisions, generating contradictory outputs, and eventually producing truncated or incoherent responses. For a research orchestration system that may run multi-stage analytical pipelines across hours-long sessions, this degradation is not merely inconvenient -- it threatens the integrity of the research itself. A methodology decision forgotten mid-pipeline, a validation result lost to context pressure, or a data caveat silently dropped can propagate errors through every downstream step.

Claude Code's built-in response to context growth is **automatic compaction**: when utilization approaches a threshold (roughly 83.5% of the context window), the platform takes the entire conversation history, sends it to a separate model call for summarization, and replaces the full history with a condensed version. This is lossy compression -- details are irreversibly discarded based on a generic summarization heuristic that has no awareness of what information is analytically critical.

DAAF chose to forgo compaction entirely. The framework instead builds its own self-monitoring system with three interlocking components:

1. **Active monitoring** -- a hook-based utilization tracker that periodically injects severity-tagged usage data into the conversation, giving the model objective awareness of its own context consumption.
2. **Graduated behavioral responses** -- threshold-gated action rules, defined in CLAUDE.md, that specify what both the orchestrator and subagents must do at each severity level. The responses escalate from "continue normally" through "delegate more aggressively" to "cease work immediately and persist state."
3. **File-based lossless persistence** -- five distinct mechanisms that write critical state information to disk before context pressure forces a session restart. When the session resumes, the new context window reads these files to reconstruct the full working state without any information loss.

This design reflects a core DAAF principle: for scientific research, lossless persistence is always preferable to lossy compression. A session restart with full state recovery takes seconds. Compaction-induced information loss can take hours to diagnose -- if it is detected at all.

---

### What It Does

The context management system provides three capabilities that work together to keep multi-session research pipelines viable:

**Self-awareness.** The system gives the model continuous, quantitative visibility into its own context consumption. Rather than operating blind until the platform intervenes with compaction, the model receives periodic severity-tagged utilization reports (e.g., "Context utilization [ELEVATED]: 155k / 1000k tokens (15%)") and can make informed decisions about delegation, persistence, and session management.

**Graduated response.** The system defines different behavioral protocols for four severity levels, with distinct action tables for the orchestrator and for subagents. At low utilization, agents work normally. As utilization rises, they progressively shift from executing work directly to delegating it, then from delegating to persisting state and preparing for restart. The transitions are smooth rather than binary -- there is no single point where the system switches from "working" to "shutting down."

**Lossless persistence.** The system maintains five file-based persistence mechanisms that capture different aspects of session state at different granularities. When a session ends -- whether planned or due to context pressure -- the next session can reconstruct the full working state from these files. No information is lost. No summarization heuristic decides what to keep and what to discard. The human researcher and the framework's structured files make that determination.

---

### Current Realization on Claude Code

#### Disabling Auto-Compaction

DAAF explicitly instructs users to disable Claude Code's auto-compaction via the `/config` menu ("Set Auto-compact to False"). This is a user-level setting, not a `settings.json` configuration, and must be set manually during initial setup. Additionally, DAAF sets `CLAUDE_CODE_DISABLE_AUTO_MEMORY` to `1` in `settings.json` to disable Claude Code's automatic memory feature, ensuring DAAF retains full control over what state persists and how.

With compaction disabled, the model's context window fills monotonically during a session. There is no automatic relief valve. DAAF's monitoring and persistence systems are the replacement.

#### The context-reporter Hook (DAAF-Built)

The centerpiece of DAAF's monitoring system is `context-reporter.sh`, a 175-line bash script registered as a hook on two events: `UserPromptSubmit` (universal matcher) and `PreToolUse` (universal matcher). It fires for both the orchestrator and all subagents -- any agent in the system that uses a tool or receives a user message gets periodic utilization data injected into its conversation.

**Token calculation.** The hook reads the JSONL transcript file that Claude Code maintains for each session. Using `tail -50` on the transcript (to avoid parsing the entire file on every invocation), it extracts the most recent non-sidechain, non-error message and sums three usage fields:

- `input_tokens` -- direct input tokens
- `cache_read_input_tokens` -- tokens read from prompt cache
- `cache_creation_input_tokens` -- tokens written to prompt cache

This total represents the full context consumed by the most recent model turn, including all cached content. The percentage is calculated against the context window size.

**Context window size discovery.** The hook needs to know the model's context window size, but this information is not available in the hook's input payload. The solution is a two-component cache system that bridges the gap between Claude Code's status line system and its hook system:

1. The `context-bar.sh` status line script (not a hook -- it powers the terminal status bar) receives the `context_window.context_window_size` field in its input and writes it to `/tmp/claude-ctx-window-{session_id}`.
2. The `context-reporter.sh` hook reads from that cache file with a three-level fallback chain: first the exact session match, then the most recent `/tmp/claude-ctx-window-*` file from any session (critical for subagents, which have different session IDs from the parent orchestrator), then a hardcoded default of 200,000 tokens as a last resort.

The fallback to the most recent cache file from any session is a deliberate design choice for subagent support. Subagents run with different session IDs, so their session-specific cache will not exist at first invocation. The fallback finds the parent orchestrator's cache, ensuring subagents report utilization against the correct context window size.

**Rate limiting.** Both registered events share a single 60-second injection gate per session, implemented via a timestamp file at `/tmp/claude-ctx-ts-{session_id}`. Whichever event fires first (a user message or a tool call) resets the timer for both. This prevents the monitoring system from polluting the very context it is trying to protect -- without rate limiting, a rapid sequence of tool calls could inject dozens of utilization messages, consuming meaningful context budget on monitoring overhead alone.

**Output format.** The hook emits a single-line message with severity, absolute token count, maximum, percentage, and a UTC timestamp:

```
Context utilization [ELEVATED]: 155k / 1000k tokens (15%) | 2026-05-01 14:23:45 UTC
```

On `UserPromptSubmit`, this goes to stdout and Claude Code injects it as a `<user-prompt-submit-hook>` block. On `PreToolUse`, it is formatted as JSON with an `additionalContext` field, which Claude Code injects as a `<system-reminder>` block before the tool executes. Both paths are informational -- the hook always exits with code 0 and never blocks tool execution.

**Error safety.** The hook uses `set -u` (catch unset variables) but deliberately omits `set -e` (exit on error). All error paths exit with code 0. All file operations and jq commands include `2>/dev/null` redirections. The design principle is clear: a monitoring failure must never prevent the model from doing work.

**Additional feature.** The hook caches the model name from the transcript to `/tmp/claude-model-{session_id}`, which the `audit-log.sh` hook reads when writing audit log entries. This is a one-time operation per session, illustrating the inter-hook communication pattern documented in Section 7.

#### Dual-Threshold Severity System (DAAF-Designed)

The hook implements a dual-trigger threshold system where either a percentage threshold or an absolute token count triggers the severity level, whichever fires first:

| Severity | Percentage Trigger | Absolute Token Trigger | Effect |
|----------|-------------------|----------------------|--------|
| NOMINAL | < 40% | < 150k tokens | Neither trigger fires |
| ELEVATED | >= 40% | >= 150k tokens | Either trigger fires |
| HIGH | >= 60% | >= 200k tokens | Either trigger fires |
| CRITICAL | >= 75% | >= 250k tokens | Either trigger fires |

The dual-trigger design exists because percentage thresholds alone fail on large context windows. On a 1M token window (which DAAF currently uses with `claude-opus-4-6[1m]`), 40% equals 400,000 tokens -- far too deep into the session for the model to respond effectively. The absolute thresholds ensure ELEVATED fires at 150k tokens (15% of a 1M window) rather than waiting until 400k tokens (40%). As the DAAF changelog notes: "While Opus and Sonnet can now handle token windows of up to 1m tokens, there's A LOT of evidence that its performance deteriorates quickly -- and regardless, costs skyrocket per turn because of it." The absolute thresholds cap effective session length regardless of window size.

#### Graduated Response Protocols (DAAF-Designed, Defined in CLAUDE.md)

CLAUDE.md defines separate action tables for the orchestrator and subagents at each severity level. These are behavioral instructions -- the model follows them because they are part of its system prompt, not because any runtime mechanism enforces them.

**Orchestrator actions:**

| Severity | Required Action |
|----------|-----------------|
| NOMINAL | Continue normally |
| ELEVATED | Monitor closely; consider how realistic the scope of remaining work is; consider delegating more to subagents |
| HIGH | Complete current atomic unit at full quality; report back to user; do not start new stages of work; update STATE.md with restart prompt |
| CRITICAL | Cease work immediately; report back to user; finalize STATE.md |

**Subagent actions:**

| Severity | Required Action |
|----------|-----------------|
| NOMINAL | Continue executing the assigned task normally |
| ELEVATED | Assess remaining work honestly; if completion is uncertain, begin structuring return output; continue working but prioritize the most valuable deliverables |
| HIGH | Return early -- complete only the current atomic unit; format return with completed work, incomplete items, and file paths; do not start new work items |
| CRITICAL | Stop immediately and return; report whatever has been completed; clearly mark output as incomplete; list all remaining work items |

The key asymmetry is that the orchestrator persists state to STATE.md and prepares a restart prompt, while subagents return structured output to the orchestrator so it can decide how to proceed (redelegate the remaining work, handle it directly, or prepare for restart). Subagents never write STATE.md directly -- that is exclusively the orchestrator's responsibility.

#### Early-Return Protocol (DAAF-Designed)

When subagents return early due to context pressure (at HIGH or CRITICAL severity), their response must include five structured elements that maximize the orchestrator's ability to continue the work:

1. **All file paths created or modified** -- absolute paths so the next agent or the orchestrator can locate artifacts without searching
2. **Summary of completed analysis or findings** -- what was accomplished before the early return
3. **Explicit list of tasks not yet started or partially completed** -- so the orchestrator knows exactly what remains and can redelegate efficiently
4. **Any decisions made or assumptions applied** that the next agent needs to know -- preventing duplicated reasoning or contradictory choices
5. **Confidence assessment of completed work** -- honest evaluation of whether the completed portions are reliable or need review

An incomplete but well-documented return is far more valuable than a context-exhausted agent that produces degraded output. This is a direct application of the quality primacy rule.

#### Context Degradation Symptoms (DAAF-Designed)

DAAF defines six observable symptoms that may indicate context degradation even before utilization thresholds fire, with a mapped severity for each:

| Symptom | Severity | Typically Indicates |
|---------|----------|---------------------|
| Repeating information already stated | MEDIUM | 40-60% utilization |
| Forgetting earlier decisions | HIGH | 60%+ utilization |
| Generating contradictory outputs | CRITICAL | 70%+ utilization |
| Incomplete or truncated responses | CRITICAL | Near limit |
| Losing track of current stage | HIGH | Context fragmentation |
| Mixing up file names or paths | MEDIUM | Working memory strain |

The behavioral rule is: if degradation symptoms are observed, treat the situation as equivalent to HIGH severity regardless of actual utilization -- prepare for restart immediately. This provides a qualitative safety net alongside the quantitative threshold system, catching cases where the model's effective capacity is lower than the raw token count suggests (due to particularly complex reasoning chains, many interleaved tool results, or other factors that reduce effective working memory).

#### Quality Primacy Rule (DAAF-Designed)

A single sentence in CLAUDE.md anchors the entire context management philosophy: "Context management is NEVER about reducing the quality or completeness of work." Thresholds control WHEN to restart, never WHETHER to maintain quality. At ELEVATED utilization, the orchestrator delegates more execution to subagents but constructs prompts with the same thoroughness as at NOMINAL. Documentation completeness, subagent prompt fidelity, and inlined context are non-negotiable regardless of utilization level. If maintaining quality means reaching a restart point sooner, that is the correct outcome.

This rule prevents a common failure mode where the model, aware of context pressure, begins cutting corners -- producing shorter prompts, skipping validation, or abbreviating STATE.md updates. These shortcuts save context in the short term but create gaps that cost far more to diagnose and repair in subsequent sessions.

#### Five Persistence Mechanisms (DAAF-Built)

DAAF maintains five file-based persistence mechanisms, each serving a different scope and purpose. Together they form a lossless alternative to compaction.

**1. STATE.md -- Primary session state.** Used in Full Pipeline, Data Onboarding, Revision, and Reproducibility Verification modes. STATE.md is the comprehensive session state document containing: current position (phase, stage, status), session metadata, checkpoint status, data status, key decisions made, transformation progress with per-script tracking, blockers, error budget, deviations, QA findings, citations, pending learning signals, next actions, files created, velocity metrics, and a context snapshot with the actual utilization percentage from the context-reporter hook. It is created during planning (Stage 4) and updated after each checkpoint, stage completion, key decision, blocker, error budget consumption, and session break. Its most critical field is the **restart prompt** -- a pre-formatted prompt with concrete values (no placeholders) that the user copies after running `/clear` to resume the session:

```
Resume the [Project Title] analysis. Plan: `[exact plan path]`.
Plan Tasks: `[exact Plan_Tasks path]`. State: `[exact STATE.md path]`.
Currently at Stage [N] ([Stage Name]) -- next step is [task description].
```

STATE.md also contains detailed resumption instructions that guide the recovering orchestrator through a mechanical recovery sequence: read STATE.md first, locate Plan at specific path, read Plan selectively (specific sections, not the entire file), identify current phase and next task.

The behavioral guardrail for STATE.md is explicit: "When updating STATE.md under context pressure, resist the urge to abbreviate. STATE.md is what the next session reads to resume -- every shortcut taken here becomes a gap in the recovery context."

**2. SESSION_NOTES.md -- Lightweight state for ad-hoc modes.** Used in Ad Hoc Collaboration and Framework Development modes, which do not require the full STATE.md machinery. SESSION_NOTES.md captures accomplishments (with file paths), key decisions (with rationale), in-progress work, open questions, and AI disclosure. It is created at the first substantive milestone and updated after each deliverable, key decision, topic change, context reaching ELEVATED, and session end. At context thresholds, the orchestrator updates SESSION_NOTES.md with current state, summarizes accomplishments, and suggests the user start a fresh session pointing to SESSION_NOTES.md as the continuity mechanism.

**3. LEARNINGS.md -- Cross-session learning signals.** Created during planning (Stage 4) as a skeleton alongside Plan.md, Plan_Tasks.md, and STATE.md. Accumulates insights from subagent execution -- data quirks discovered, access patterns, performance notes, methodology decisions -- categorized as Access, Data, Method, Perf, or Process signals. The population pattern is: subagents return learning signals as part of their output; the orchestrator buffers them in STATE.md's "Pending Learning Signals" section; the buffer is flushed to LEARNINGS.md at phase boundaries, after blocker resolution, after debugging, and at utilization gates. When recovering a session, the orchestrator reads LEARNINGS.md to prevent re-encountering resolved issues, prioritizing entries tagged with the current or upcoming stages.

**4. Preliminary notes -- Lossless subagent returns written to disk.** When discovery or profiling agents complete their work and return findings to the orchestrator, the orchestrator writes the full, unmodified return text to a file in `output/preliminary_notes/` with a provenance header identifying the agent, stage, and timestamp. This write is a gate condition: the orchestrator does not proceed until the file exists on disk and contains the complete agent return. The orchestrator then extracts a compressed summary (status, 3-5 key bullets, file locations, confidence, escalation items) for its own working memory and discards the verbose content. Downstream agents receive the preliminary notes file path and read the lossless version themselves.

This creates a two-tier information architecture: the orchestrator tier holds compressed summaries for coordination decisions; the disk tier holds lossless full findings for downstream agents to consume. The orchestrator's context stays lean while no information is actually lost.

**5. Orchestrator context budget rules -- Delegation as context preservation.** The orchestrator skill defines what stays in the orchestrator's context (approximately 2,000 words maximum: original user request, mode classification, scope decisions, phase summaries, current stage, STATE.md, Plan.md, Plan_Tasks.md paths, error history) and what gets delegated to subagents (skill invocations, data exploration, source deep-dives, code-heavy analysis, visualization, QA aggregation). Content that never enters orchestrator context includes full skill bodies, raw data samples, complete code files, and full error tracebacks.

A specific example of this discipline is the Plan_Tasks.md extraction protocol. Plan_Tasks.md can exceed 1,000 lines. The orchestrator never reads the full file into context. Instead, it reads only the Task Index table (the first 30-40 lines), identifies the target task by step number, searches for that specific task header, and reads only that task block (typically 20-40 lines). This on-demand loading pattern preserves hundreds of kilobytes of context budget over a full pipeline run.

Subagent dispatch itself is explicitly used as a context preservation strategy. Each subagent gets a fresh context window, so skill loading (5k-20k tokens per skill), iterative data exploration, and code execution all consume subagent context rather than orchestrator context. The orchestrator skill states this directly: "Dispatch generously to subagents. Each subagent gets a fresh context window."

#### Session Recovery Protocol

When a session is restarted (after `/clear` or after a crash), the recovering orchestrator follows a structured 7-step recovery procedure:

1. Locate the project folder in `research/`
2. Read STATE.md in full -- the primary recovery document
3. Read LEARNINGS.md to recover accumulated insights
4. Read Plan.md selectively -- only recovery-relevant sections (Original Request, Goal and Context, Decisions Log, Risk Register, Current Status, Transformation Sequence summary)
5. Verify filesystem state -- check which artifacts exist versus what STATE.md expects
6. Identify resume point from STATE.md's Current Position and Next Actions
7. Present recovery summary to the user showing what is complete and what remains

The procedure includes stale-state detection: if STATE.md's timestamp is older than the most recent script file, the state file may be stale from a crash that occurred before the orchestrator could update it. In that case, the recovery procedure reconstructs position from the filesystem and git history rather than trusting the potentially outdated STATE.md.

---

### Design Choices and Rationale

**Why disable auto-compaction rather than configuring it.** Compaction is lossy summarization controlled by a generic heuristic with no awareness of what information is analytically critical. For a research pipeline where methodology decisions, data caveats, coded values, and validation results must be precisely tracked across stages, lossy compression risks introducing silent errors. A compaction summary might preserve "we filtered the data" while discarding the specific filter criteria and the validation that confirmed no records were incorrectly dropped. DAAF's file-based persistence is lossless by construction -- STATE.md captures every decision, preliminary notes preserve every finding, and LEARNINGS.md records every cross-session insight. The cost of this approach is more frequent session restarts; the benefit is that no information is ever silently discarded. Additionally, compaction disrupts orchestration state -- the mental model the orchestrator maintains about current stage, pending decisions, and subagent outcomes may not survive the summarization intact.

**Why dual thresholds (percentage and absolute).** On a 200k token window, percentage thresholds work well: 40% is 80k tokens, a reasonable point to begin monitoring. On a 1M token window, 40% is 400k tokens -- the model has consumed enormous context before any alert fires. Absolute thresholds (150k, 200k, 250k) fire at the same point regardless of window size, capping effective session length where evidence shows quality begins to degrade. The dual-trigger design (either fires the threshold) ensures the system behaves conservatively on large windows without penalizing small ones.

**Why 60-second rate limiting on the hook.** Without rate limiting, a rapid sequence of tool calls (common during code execution where the model may make 10-20 tool calls in quick succession) would inject a utilization message before each one. At roughly 30 tokens per injection, 20 rapid tool calls would add 600 tokens of pure monitoring overhead -- a small but recurring cost that compounds over a long session. The 60-second gate ensures the model gets updated utilization data at a human-readable cadence (roughly once per minute of active work) without paying a meaningful context cost for the monitoring itself.

**Why subagents have their own monitoring protocol.** Subagents run in separate context windows from the orchestrator. A subagent that exhausts its context without returning structured output wastes the orchestrator's context budget -- the orchestrator must re-dispatch the work, re-construct the prompt, and process the (now missing) results. Worse, any work the subagent completed but did not report is lost. By having subagents monitor their own utilization and follow the early-return protocol, DAAF ensures that even under context pressure, completed work and remaining task lists are preserved and returned to the orchestrator in a usable format.

**Why file-based persistence instead of compaction.** This is the fundamental architectural choice. Compaction operates on in-context information and produces a compressed in-context summary. File-based persistence operates on disk and produces lossless artifacts that survive across sessions, across crashes, and across context clears. A compacted summary exists only in the current conversation; a STATE.md file exists permanently and can be read by any future session, reviewed by the human researcher, or processed by automated tools. For research reproducibility -- where the goal is an auditable trail of every decision -- disk persistence is categorically superior.

**The two-tier information architecture.** The preliminary notes pattern illustrates a broader design principle: the orchestrator keeps compressed summaries for coordination, while disk holds full-fidelity content for downstream consumption. This is not merely a storage optimization -- it is a separation of concerns. The orchestrator needs to know "the CCD data has 98,469 schools across 52 states and territories with 3 data quality issues to track" (50 words). A downstream coding agent needs the full 2,000-word profiling report to write correct data transformations. By writing the full report to disk and keeping only the summary in orchestrator context, both needs are served without compromise.

**Why STATE.md fidelity is emphasized under context pressure.** It is tempting, when context is running low, to write a shorter STATE.md update. But STATE.md is what the next session reads to resume. Every abbreviation becomes a gap in the recovery context. An orchestrator that saves 200 tokens by writing a terse STATE.md update may cost the next session 2,000 tokens of re-investigation to figure out what the terse update meant. The behavioral guardrail -- "resist the urge to abbreviate" -- exists because the natural instinct under pressure is exactly wrong for this use case.

---

### Replication Specification

An implementer porting DAAF's context management system to another harness must provide or build the following capabilities:

**Required: Periodic utilization injection.** The model must receive quantitative utilization data injected into its conversation at regular intervals. This requires: (a) access to token usage data for the current session, either via transcript parsing, API response metadata, or a platform-provided usage endpoint; (b) a mechanism to inject text into the model's conversation stream without requiring user action, analogous to Claude Code's `additionalContext` injection via PreToolUse hooks or the `<user-prompt-submit-hook>` block; (c) rate limiting to prevent monitoring overhead from becoming a significant context consumer itself.

**Required: Compaction control.** The harness must either provide a way to disable automatic compaction entirely (preferred) or provide compaction hooks that let the framework control what gets summarized and what gets preserved verbatim. If neither is available, the framework must build recovery mechanisms that re-read STATE.md and critical context from disk after compaction occurs, accepting that compaction will periodically disrupt orchestration state.

**Required: Subagent context isolation.** Subagents must run in separate context windows from the parent orchestrator. This is fundamental to the context budget strategy -- without isolation, skill loading, code execution, and data exploration consume the orchestrator's context directly, making the budget rules unworkable. The target harness must provide an equivalent of "spawn a new agent conversation with its own context" where the subagent inherits project-level instructions but not conversation history.

**Required: Subagent monitoring parity.** The utilization injection mechanism must fire for both the orchestrator and all subagents. If hooks fire only for the parent context, subagents operate blind to their own utilization and cannot follow the early-return protocol.

**Required: Project-level instruction inheritance.** The context quality rules, degradation symptoms table, and early-return protocol are defined in CLAUDE.md, which Claude Code automatically injects into every agent's system prompt. The target harness must have an equivalent "project instructions visible to all agents" mechanism so that universal behavioral rules apply without per-agent configuration.

**Required: File I/O for persistence.** All five persistence mechanisms require the ability to create, read, and write files on disk. This is universally available across harnesses.

**Acceptance criteria for feature parity:**

1. The model reports its own utilization at regular intervals with severity classification
2. Severity levels match the dual-threshold system (both percentage and absolute triggers)
3. The orchestrator follows graduated response protocols at each severity level
4. Subagents independently monitor their utilization and follow the early-return protocol
5. STATE.md (or equivalent) captures full session state including a pre-formatted restart prompt
6. Session recovery after a context clear restores the full working state from disk files without information loss
7. Auto-compaction is disabled or controlled so that the framework's own persistence mechanisms are the primary state management strategy

**Degraded-mode options.** If periodic injection is not achievable (no hook equivalent for system reminders), the model can be instructed to manually check utilization at defined intervals (e.g., "after every 5 tool calls, check your token usage"). This is unreliable compared to automatic injection but provides some self-awareness. If compaction cannot be disabled, the framework can build post-compaction recovery by re-reading STATE.md at the start of every model turn where compaction may have occurred -- but this adds overhead and does not prevent the loss of in-flight analytical reasoning that was not yet persisted to disk.

---

### Harness Landscape

Context monitoring at DAAF's level of sophistication is not a standard feature of any surveyed harness. Most harnesses rely on automatic compaction with no user-facing utilization reporting and no graduated response system.

**Claude Code** provides the primitives DAAF builds on: JSONL transcripts with token usage data, hook-based context injection, and a user-facing compaction toggle.

**Codex (OpenAI)** operates with a context limit per task (roughly 192k tokens) and uses sandboxed execution with no documented equivalent of in-conversation utilization injection. Its task-based model (each task is a separate context) provides natural context isolation but no cross-task state persistence mechanism beyond the filesystem.

**Cursor** provides a context window with visible token counts in the UI but no documented hook mechanism for injecting utilization data into the model's conversation. Its agent mode supports multi-step tool use but context management is handled by the platform rather than exposed to the user.

**Aider** works within a single conversation context and provides commit-based persistence but no documented context monitoring, utilization injection, or graduated response system.

**OpenCode** provides subagent isolation and hook support but no documented equivalent of DAAF's dual-threshold monitoring or behavioral response protocols.

Across all surveyed harnesses, DAAF's combination of compaction avoidance, self-monitoring injection, dual-threshold severity, graduated behavioral responses, and structured file-based persistence represents a novel architecture that would need to be custom-built on any target platform.

---

### Dependencies

**Depends on:**

- **Hook system (Section 7):** The context-reporter hook is the monitoring mechanism. Registration in `settings.json` on both `UserPromptSubmit` and `PreToolUse` events with universal matchers ensures it fires for all agents. The `additionalContext` injection mechanism on `PreToolUse` is how utilization data reaches the model.
- **Instruction loading (Section 3):** The graduated response protocols, early-return protocol, quality primacy rule, and degradation symptoms table are all defined in CLAUDE.md, which must be auto-injected into every agent's system prompt for the behavioral rules to take effect.
- **Agent system (Section 4):** Subagent context isolation is what makes the context budget strategy viable. The 2,000-word return cap on subagent output, the preliminary notes pattern, and the skill-loading-via-subagents principle all depend on subagents having separate context windows.

**Depended on by:**

- **Logging and session management (Section 9):** Session archiving and crash recovery depend on the session being in a recoverable state when it ends. Context management's STATE.md updates and restart prompt ensure that sessions interrupted by context pressure can be resumed.
- **All pipeline execution:** Every DAAF workflow mode (Full Pipeline, Data Onboarding, Revision, Reproducibility Verification, Ad Hoc, Framework Development) depends on context management for session viability. Without it, long-running research pipelines cannot span multiple sessions reliably.
