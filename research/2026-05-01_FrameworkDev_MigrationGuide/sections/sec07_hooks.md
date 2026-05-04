# 7. Hook System: Runtime Behavior Injection

**Classification: HYBRID** -- Claude Code provides the hook infrastructure (5 event types, JSON stdin protocol, exit code semantics, matcher routing, per-agent frontmatter hooks). DAAF designed all 12 hook scripts, the three functional categories (safety / observability / behavioral), the fail-closed vs. fail-open architecture, inter-hook communication via `/tmp` files, and the agent-scoped registration strategy.

**Criticality:** CRITICAL | **Interdependencies:** 8

---

## Design Intent

Hooks are where DAAF's design intent becomes runtime reality. Every safety
guarantee, every audit record, every behavioral nudge, and every observability
signal flows through the hook system. Without hooks, DAAF would be a collection
of written instructions with no programmatic enforcement -- compliance would
depend entirely on model instruction-following, which is insufficient for
research integrity.

The fundamental design problem is this: an AI coding agent makes dozens of tool
calls per session, each capable of destroying data, leaking credentials,
bypassing the audit trail, or dispatching unsuitable subagents. Written
instructions in CLAUDE.md can guide behavior, but they cannot *guarantee* it.
LLMs can ignore, misinterpret, or forget instructions, especially under context
pressure. DAAF needed a mechanism to intercept agent actions at runtime and
enforce invariants programmatically, independent of model compliance.

Claude Code's hook system provides exactly this: shell scripts that fire at
defined lifecycle points, receive structured JSON about the pending or completed
action, and can block execution, inject context, or record observations. DAAF
took this infrastructure and built a complete enforcement architecture on top of
it -- 12 scripts organized into three functional categories, each with a
deliberate failure mode, communicating through shared `/tmp` files, and
registered through a combination of project-wide settings and per-agent
frontmatter.

---

## What It Does

The hook system provides five capabilities that DAAF depends on:

1. **Pre-execution blocking** -- Safety hooks inspect tool calls before they
   execute and block dangerous operations (destructive commands, direct Python
   execution, unsuitable subagent dispatch). The blocked action never runs; the
   model receives an error message explaining why.

2. **Context injection** -- The context reporter hook injects utilization data
   into the model's context as `<system-reminder>` blocks, enabling informed
   decisions about delegation, state persistence, and session recovery without
   any explicit model action.

3. **Post-execution observation** -- After every tool call, the audit logger
   records a structured JSONL entry and the output scanner checks for leaked
   credentials. These hooks never block but produce the observability layer that
   makes sessions auditable.

4. **Session lifecycle management** -- Hooks on SessionStart and SessionEnd
   handle activity logging, crash recovery of orphaned transcripts, and full
   session archival with JSONL-to-Markdown conversion.

5. **Behavioral shaping** -- The orchestrator reminder hook ensures the
   daaf-orchestrator skill loads at the start of every session, providing
   deterministic initialization without relying on model memory across sessions.

---

## Current Realization on Claude Code

### The Hook Infrastructure (Native Primitive)

Claude Code provides five lifecycle event types to which shell scripts can be
registered:

| Event | When It Fires | Matcher Relevance |
|-------|---------------|-------------------|
| **SessionStart** | New session begins, before any user input | `""` only (no tools involved) |
| **UserPromptSubmit** | User submits a message, before model processes it | `""` only (no tools involved) |
| **PreToolUse** | Model decides to use a tool, BEFORE tool executes | Tool name matcher or `""` for all |
| **PostToolUse** | Tool finishes executing | Tool name matcher or `""` for all |
| **SessionEnd** | Session terminates (user exit, crash recovery) | `""` only |

**Registration** occurs in two places:

- **settings.json** (project-wide): The `hooks` key maps event types to arrays
  of matcher objects, each containing an array of hook command entries. Every hook
  registered here fires for the orchestrator and for all subagents whose tool
  calls match the event and matcher.

- **Agent frontmatter** (per-agent): The `hooks` field in an agent's YAML
  frontmatter registers hooks that fire *only* when that specific agent type makes
  matching tool calls. This is how DAAF achieves agent-scoped enforcement.

**Matcher semantics:**

- `""` (empty string) -- Universal: matches ALL tool calls for that event type.
- `"Bash"`, `"Task"`, `"Agent"`, `"Skill"` -- Matches only when the named tool
  is being invoked.

Multiple matchers can exist for the same event. A single tool call may trigger
hooks from both the universal matcher and a tool-specific matcher.

**Input protocol (stdin JSON):**

Every hook receives a JSON object on stdin. Common fields across all events:

| Field | Description |
|-------|-------------|
| `session_id` | UUID identifying the session |
| `transcript_path` | Absolute path to the session's JSONL transcript file |
| `hook_event_name` | The event type string (e.g., `"PreToolUse"`) |

Tool-related events (PreToolUse, PostToolUse) add:

| Field | Description |
|-------|-------------|
| `tool_name` | The tool being invoked (e.g., `"Bash"`, `"Read"`, `"Agent"`) |
| `tool_input` | Full input object (e.g., `{"command": "ls"}` for Bash) |

PostToolUse additionally adds:

| Field | Description |
|-------|-------------|
| `tool_response` | The tool's output/return value |
| `agent_type` | Agent type string for subagent calls; empty for orchestrator |
| `agent_id` | Agent instance UUID for subagent calls; empty for orchestrator |

SessionEnd adds `cwd` (current working directory) and `reason` (e.g.,
`"user_exit"`, `"recovered"`).

**Output protocol (exit codes and stdout):**

| Exit Code | Meaning | Effect |
|-----------|---------|--------|
| 0 | Pass/Allow | Tool execution proceeds; stdout processed by event type |
| 1 | Error | Hook error logged but does not block; tool proceeds |
| 2 | Block | **PreToolUse only.** Tool execution BLOCKED; stderr shown to model |

Stdout processing varies by event type:

| Event | Stdout Format | How Claude Code Injects It |
|-------|---------------|---------------------------|
| UserPromptSubmit | Plain text | Injected as `<user-prompt-submit-hook>` in user message context |
| PreToolUse | JSON with `hookSpecificOutput` | Two mechanisms (see below) |
| PostToolUse | Plain text | Injected as context after the tool result |
| SessionStart/SessionEnd | Plain text | Displayed to user only (not injected into model context) |

**PreToolUse has two distinct output mechanisms:**

*Mechanism 1 -- Exit code 2 + stderr (hard block):*

The hook exits with code 2 and writes an error message to stderr. Claude Code
blocks the tool call and surfaces the stderr message to the model. Used by
`bash-safety.sh` and `enforce-file-first.sh` for Bash command blocking, where
the command itself is the danger.

*Mechanism 2 -- JSON permission decision (structured block):*

The hook exits with code 0 but emits JSON on stdout:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Explanation shown to the model"
  }
}
```

Claude Code denies the tool call and shows the reason. Used by
`enforce-explore-model.sh`, `enforce-foreground-agents.sh`, and
`deny-claude-code-guide.sh` for Agent/Task blocking, where the hook needs to
provide a structured redirect message.

*Mechanism 3 -- JSON additional context (injection without blocking):*

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "Text injected as <system-reminder>"
  }
}
```

The tool proceeds normally, but the injected text appears as a
`<system-reminder>` the model sees. Used by `context-reporter.sh` for
utilization monitoring.

### Complete Hook Registration Table

**Project-wide registrations (settings.json) -- 15 entries, 11 unique scripts:**

| Event | Matcher | Script | Timeout |
|-------|---------|--------|---------|
| SessionStart | `""` (all) | recover-session-logs.sh | 5s |
| UserPromptSubmit | `""` (all) | context-reporter.sh | 5s |
| UserPromptSubmit | `""` (all) | remind-orchestrator.sh | 5s |
| PreToolUse | `""` (all) | context-reporter.sh | 5s |
| PreToolUse | `"Task"` | enforce-explore-model.sh | 5s |
| PreToolUse | `"Task"` | enforce-foreground-agents.sh | 5s |
| PreToolUse | `"Task"` | deny-claude-code-guide.sh | 5s |
| PreToolUse | `"Agent"` | enforce-explore-model.sh | 5s |
| PreToolUse | `"Agent"` | enforce-foreground-agents.sh | 5s |
| PreToolUse | `"Agent"` | deny-claude-code-guide.sh | 5s |
| PreToolUse | `"Bash"` | bash-safety.sh | 5s |
| PostToolUse | `""` (all) | audit-log.sh | 5s |
| PostToolUse | `""` (all) | output-scanner.sh | 5s |
| PostToolUse | `"Skill"` | flag-orchestrator-loaded.sh | 5s |
| SessionEnd | `""` (all) | archive-session.sh | 60s |

Three hooks (`enforce-explore-model.sh`, `enforce-foreground-agents.sh`,
`deny-claude-code-guide.sh`) are each registered twice -- once for the `"Task"`
matcher and once for `"Agent"` -- because Claude Code uses two different tool
names for subagent dispatch. This duplication ensures coverage regardless of
which dispatch mechanism the model selects.

**Per-agent registrations (frontmatter) -- 1 script, 4 agents:**

| Agent | Script | Event | Matcher | Timeout |
|-------|--------|-------|---------|---------|
| research-executor | enforce-file-first.sh | PreToolUse | Bash | 5s |
| code-reviewer | enforce-file-first.sh | PreToolUse | Bash | 5s |
| debugger | enforce-file-first.sh | PreToolUse | Bash | 5s |
| data-ingest | enforce-file-first.sh | PreToolUse | Bash | 5s |

The 11 agents *without* per-agent hooks (data-planner, data-verifier,
framework-engineer, integration-checker, notebook-assembler, plan-checker,
report-writer, research-synthesizer, search-agent, source-researcher, and the
orchestrator itself) are exempt from file-first enforcement.

### The 12 Hook Scripts (DAAF-Built)

DAAF organizes its hooks into three functional categories based on their failure
mode and purpose.

#### Category 1: Safety Hooks (Fail-Closed)

Safety hooks use a fail-closed architecture: if anything goes wrong during the
hook's own execution -- a missing dependency, a parse error, an unexpected input
format -- the hook blocks the tool call rather than allowing a potentially
dangerous action through. This is implemented via `trap 'exit 2' ERR` (for
exit-code-based hooks) or `trap 'emit deny JSON' ERR` (for JSON-based hooks).

**bash-safety.sh** -- Destructive Command Prevention

- **Event/Matcher:** PreToolUse / `"Bash"`
- **Fires for:** Orchestrator and all subagents
- **Fail mode:** Fail-closed (exit 2 on error)
- **Purpose:** Primary safety guardrail. Inspects Bash commands before execution
  and blocks five categories of dangerous operations: destructive filesystem
  commands (`rm -rf` targeting critical paths), destructive git commands (force
  push, reset hard, clean, checkout/restore `.`, branch -D), privilege escalation
  (`sudo`, `su`, `chmod 777/u+s`), dangerous network operations (pipe to shell,
  file upload via curl), and container escape attempts (`docker run`, `mount`,
  `chroot`).
- **Design:** Extracts the command from `tool_input.command`, normalizes
  whitespace, and runs regex checks ordered from most dangerous to least. The
  fail-closed trap ensures that if `jq` is missing or the JSON is malformed, the
  command is blocked -- an ambiguous failure is treated as dangerous.
- **Output:** Descriptive error message to stderr explaining what was blocked and
  why.
- **Relationship to deny rules:** Provides overlapping coverage with the
  settings.json deny list. The deny list uses glob patterns on the command string;
  this hook uses full regex matching on the normalized command. Both can block the
  same operation independently -- this is defense-in-depth by design.

**enforce-file-first.sh** -- File-First Execution Enforcement

- **Event/Matcher:** PreToolUse / `"Bash"` (agent frontmatter only)
- **Fires for:** 4 coding agents only (research-executor, code-reviewer,
  debugger, data-ingest)
- **Fail mode:** Fail-closed (exit 2 on error)
- **Purpose:** Enforces DAAF's file-first execution protocol. Blocks direct
  `python`/`python3` invocations, requiring all Python execution to go through
  `run_with_capture.sh` for audit trail capture. Uses a sophisticated regex to
  detect Python interpreter calls in various forms: bare (`python script.py`),
  versioned (`python3.11`), absolute path (`/usr/bin/python3`), and prefixed
  (`env python`, `exec python`, `nice python`, `VAR=value python`).
- **Whitelist:** Commands matching `python3?[.0-9]* /daaf/scripts/[A-Za-z0-9_-]+\.py`
  are allowed -- these are framework utility scripts (standalone CLI tools), not
  pipeline scripts that need audit trail capture.
- **Output:** Multi-line error message to stderr explaining the file-first
  protocol and pointing to `SCRIPT_EXECUTION_REFERENCE.md`.

**enforce-explore-model.sh** -- Explore Agent Blocking

- **Event/Matcher:** PreToolUse / `"Task"` and `"Agent"`
- **Fires for:** Orchestrator and all subagents (at dispatch time)
- **Fail mode:** Fail-closed (JSON deny on error)
- **Purpose:** Blocks Explore-type subagents. Explore agents run on Haiku (a
  smaller, faster model), which lacks the reasoning depth required for DAAF's
  research tasks. The hook redirects to `search-agent`, a DAAF-defined agent that
  runs on the same Opus model as all other agents.
- **Output:** JSON `permissionDecision: "deny"` with redirect instructions.

**enforce-foreground-agents.sh** -- Background Agent Blocking

- **Event/Matcher:** PreToolUse / `"Task"` and `"Agent"`
- **Fires for:** Orchestrator and all subagents (at dispatch time)
- **Fail mode:** Fail-closed (JSON deny on error)
- **Purpose:** Blocks background agent dispatch (`run_in_background: true`).
  Background agents cannot prompt the user for permission approvals, which means
  they would silently fail on any operation that requires confirmation --
  including most file reads (which DAAF intentionally does not auto-allow for
  transparency). A background agent that silently fails on permission prompts
  produces degraded output with no visible indication of what went wrong.
- **Output:** JSON `permissionDecision: "deny"`.

**deny-claude-code-guide.sh** -- Built-In Guide Agent Blocking

- **Event/Matcher:** PreToolUse / `"Task"` and `"Agent"`
- **Fires for:** Orchestrator and all subagents (at dispatch time)
- **Fail mode:** Fail-closed (JSON deny on error)
- **Purpose:** Blocks the built-in `claude-code-guide` agent. This agent has two
  problems: it runs on Haiku (insufficient reasoning depth) and it uses an opaque
  system prompt that DAAF cannot inspect or control. Since DAAF's transparency
  principle requires that every instruction the AI receives be auditable, an agent
  with an opaque prompt violates a core design requirement. The hook redirects to
  `search-agent` combined with `WebFetch` for documentation lookups.
- **Output:** JSON `permissionDecision: "deny"` with redirect to search-agent +
  WebFetch.

#### Category 2: Observability Hooks (Fail-Open)

Observability hooks use a fail-open architecture: if the hook encounters any
error during its own execution, it exits with code 0 (or silently recovers) and
the tool call proceeds unimpeded. Observability must never block operations.
A failed audit log entry is unfortunate; a blocked research operation because the
audit logger crashed would be unacceptable. This is implemented via
`trap '' ERR` (ignore errors) or explicit error recovery with fallback defaults.

**audit-log.sh** -- JSONL Audit Trail

- **Event/Matcher:** PostToolUse / `""` (universal)
- **Fires for:** Orchestrator and all subagents
- **Fail mode:** Fail-open (exit 0 unconditionally)
- **Purpose:** Appends a structured JSONL entry to `.claude/logs/audit.jsonl`
  for every tool call. Records timestamp, session ID, tool name, human-readable
  target (extracted per tool type), DAAF version (`git describe`), model name
  (from `/tmp` cache written by context-reporter), agent type (defaults to
  `"orchestrator"`), and agent ID (included only for subagent calls).
- **Protection:** The audit log file is protected by settings.json deny rules
  (`Edit(.claude/logs/*)`, `Write(.claude/logs/*)`) that prevent the AI from
  modifying or overwriting it. The log is append-only by design.
- **Output:** No stdout (writes only to the log file).

**output-scanner.sh** -- Secret Detection

- **Event/Matcher:** PostToolUse / `""` (universal)
- **Fires for:** Orchestrator and all subagents
- **Fail mode:** Fail-open (exit 0 unconditionally)
- **Purpose:** Scans the first 10KB of every tool response for credential
  patterns: AWS Access Key IDs (`AKIA...`), AWS secret keys, OpenAI/Anthropic
  API keys (`sk-...`), Stripe live keys, GitHub tokens (`ghp_`/`gho_`/`ghs_`/
  `ghr_`/`github_pat_`), private key PEM headers, and long Bearer tokens. If
  detected, emits a warning that Claude Code injects into the model's context,
  alerting it not to display, log, or commit the values.
- **Design:** Advisory only -- PostToolUse hooks cannot undo a completed tool
  execution. The scanner's role is to prevent the model from *propagating* a
  leaked secret downstream (echoing it in output, committing it to git). The
  10KB scan limit is a performance tradeoff; secrets deep in large outputs may
  go undetected.
- **Output:** Warning text to stdout when secrets detected; nothing otherwise.

**archive-session.sh** -- Session Transcript Archival

- **Event/Matcher:** SessionEnd / `""` (universal)
- **Fires for:** Orchestrator only (SessionEnd fires once per session)
- **Fail mode:** Fail-open
- **Timeout:** 60 seconds (longest of all hooks -- processes large transcripts)
- **Purpose:** Comprehensive session archival. Copies raw JSONL transcripts to
  `.claude/logs/sessions/`, converts them to human-readable Markdown (via a
  474-line jq program), discovers and archives subagent transcripts from Claude
  Code's file hierarchy (`{session-uuid}/subagents/agent-{id}.jsonl`), generates
  a subagent summary table in the orchestrator's Markdown, and processes pending
  log collection requests.
- **Design features:** Idempotent (compares source/archive file sizes to avoid
  re-archiving); timestamp-aware for recovered sessions (uses transcript's last
  entry timestamp, not wall clock); discovers subagent metadata from `.meta.json`
  sidecar files.
- **Output:** Status messages to stdout (displayed to user, not injected into
  model context).

**recover-session-logs.sh** -- Crash Recovery

- **Event/Matcher:** SessionStart / `""` (universal)
- **Fires for:** Orchestrator only (SessionStart fires once per session)
- **Fail mode:** Fail-open
- **Purpose:** Two-phase operation. *Foreground phase* (<1 second): creates log
  directories and appends a session-start entry to `.claude/logs/activity.log`.
  *Background phase* (detached subprocess): reconciles Claude Code's native
  transcript directory against DAAF's archive directory, identifies orphaned
  transcripts from sessions that terminated without SessionEnd firing (crashes,
  network loss, container restart), and pipes synthesized JSON payloads to
  `archive-session.sh` with `reason: "recovered"` so timestamps are derived
  correctly.
- **Design features:** Background execution via `( ... ) </dev/null >/dev/null 2>&1 & disown`
  ensures recovery never delays session startup. Timestamp-gated scanning (via
  `.last_recovery` touch file) avoids redundant work. Index-based matching
  (bash associative array) provides O(n+m) performance.
- **Output:** No stdout to model; writes to activity.log.

**context-reporter.sh** -- Context Utilization Monitoring

- **Event/Matcher:** UserPromptSubmit / `""` (universal) AND PreToolUse / `""`
  (universal)
- **Fires for:** Orchestrator and all subagents
- **Fail mode:** Fail-open (exit 0 unconditionally)
- **Purpose:** Injects context utilization data with severity classification
  into the model's context. Enables informed decisions about delegation, state
  persistence, and session recovery. Implements the dual-trigger threshold system
  defined in CLAUDE.md (NOMINAL, ELEVATED, HIGH, CRITICAL).
- **Processing:** Rate-limited to 60-second intervals via
  `/tmp/claude-ctx-ts-{session_id}`. Reads context window size from
  `/tmp/claude-ctx-window-{session_id}` (written by `context-bar.sh`
  statusLine); for subagents, falls back to most recently modified cache file.
  Calculates token usage from the session transcript's last 50 lines. Classifies
  severity using dual triggers (percentage OR absolute token count, whichever
  fires first). Caches model name to `/tmp/claude-model-{session_id}` for
  consumption by `audit-log.sh`.
- **Output:** On UserPromptSubmit: plain text injected as
  `<user-prompt-submit-hook>`. On PreToolUse: JSON `additionalContext` injected
  as `<system-reminder>`. Format:
  `Context utilization [ELEVATED]: 156k / 1000k tokens (15%) | 2026-05-01 14:30:00 UTC`

#### Category 3: Behavioral Hooks

Behavioral hooks shape agent behavior through deterministic prompting rather than
blocking or observing. They are neither fail-closed nor fail-open in the safety
sense -- they always exit 0 and their failure mode is simply the absence of the
behavioral nudge.

**remind-orchestrator.sh** -- Deterministic Skill Loading

- **Event/Matcher:** UserPromptSubmit / `""` (universal)
- **Fires for:** Orchestrator only (UserPromptSubmit fires on human input only)
- **Purpose:** Ensures the `daaf-orchestrator` skill loads at the start of every
  session. Without this hook, the orchestrator would need to remember to load
  its operational skill from session to session -- unreliable across context
  boundaries. The hook checks a flag file
  (`/tmp/claude-daaf-orchestrator-{session_id}`) set by
  `flag-orchestrator-loaded.sh`; if absent, it emits a directive to load the
  skill. On first-ever session (detected by activity.log line count <= 1), it
  also injects the transparency onboarding message from
  `first-run-transparency.txt`.
- **Output:** Plain text directive injected as `<user-prompt-submit-hook>`.

**flag-orchestrator-loaded.sh** -- Loading Chain Completion

- **Event/Matcher:** PostToolUse / `"Skill"`
- **Fires for:** Orchestrator and all subagents (fires after any Skill call)
- **Purpose:** Completes the deterministic skill loading chain. When the
  `daaf-orchestrator` skill is loaded (detected by checking
  `tool_input.skill == "daaf-orchestrator"`), this hook creates the flag file
  that `remind-orchestrator.sh` checks. This stops further reminders for the
  remainder of the session.
- **Output:** No stdout; creates `/tmp/claude-daaf-orchestrator-{session_id}`.

---

## Design Choices and Rationale

### Fail-Closed vs. Fail-Open Architecture

The most important architectural decision in DAAF's hook system is the assignment
of failure modes. The principle is straightforward:

- **Safety hooks fail closed** because an ambiguous failure during safety
  checking must be treated as dangerous. If `bash-safety.sh` cannot parse the
  command it is supposed to inspect, the correct response is to block execution,
  not to allow an uninspected command through. A false positive (blocking a safe
  command) is recoverable; a false negative (allowing a destructive command) may
  not be.

- **Observability hooks fail open** because the opposite priority applies. If
  `audit-log.sh` encounters a malformed JSON payload, the correct response is to
  skip the log entry and allow the tool call to proceed. A gap in the audit log
  is unfortunate; blocking a research operation because the logger crashed would
  be unacceptable.

The assignment is categorical, not per-hook: every safety hook is fail-closed,
every observability hook is fail-open, with no exceptions.

### Why enforce-file-first Is Agent-Scoped

`enforce-file-first.sh` is the only hook registered exclusively via agent
frontmatter rather than project-wide settings.json. This is a deliberate design
choice driven by role-based applicability:

- **Coding agents** (research-executor, code-reviewer, debugger, data-ingest)
  write and execute Python scripts as their primary function. These agents must
  use `run_with_capture.sh` to maintain the audit trail. File-first enforcement
  is essential for them.

- **The orchestrator** runs administrative Bash commands (directory listing, git
  operations, file management) that are not Python scripts. Applying file-first
  enforcement to the orchestrator would block legitimate operations.

- **Read-only agents** (search-agent, source-researcher, data-verifier,
  plan-checker, integration-checker) operate in `plan` permission mode and
  cannot write files or execute scripts at all. File-first enforcement is
  irrelevant to them.

- **Non-coding write agents** (framework-engineer, notebook-assembler,
  report-writer, research-synthesizer) write files but do not execute Python
  scripts through Bash. They are exempt because file-first enforcement would
  provide no benefit.

Agent-scoped registration via frontmatter is the mechanism that makes this
differentiation possible. A project-wide hook cannot distinguish which agent is
making the tool call.

### Why Explore and claude-code-guide Agents Are Blocked

Both are blocked for model quality and transparency reasons:

- **Explore agents** run on Claude Haiku, a smaller and faster model. Haiku lacks
  the reasoning depth required for DAAF's research tasks, which demand careful
  analytical judgment, nuanced data interpretation, and faithful adherence to
  complex multi-section agent protocols. Dispatching a Haiku-powered agent for
  any DAAF task risks producing low-quality output that wastes the orchestrator's
  context budget to review and correct. The redirect to `search-agent` (which
  runs on Opus via model inheritance) ensures equivalent functionality with
  adequate reasoning capacity.

- **claude-code-guide** uses an opaque system prompt that DAAF cannot inspect,
  audit, or control. DAAF's transparency principle requires that every
  instruction influencing AI behavior be visible and auditable by the researcher.
  An agent operating under undisclosed instructions violates this principle. It
  also runs on Haiku, compounding the model quality concern.

### Why Background Agents Are Blocked

Background agents (`run_in_background: true`) cannot surface permission prompts
to the user. In Claude Code's permission model, many operations require explicit
user approval -- including file reads (which DAAF intentionally does not
auto-allow). A background agent that encounters a permission prompt silently
stalls or fails, producing incomplete output with no visible indication of what
went wrong. The orchestrator, unaware of the failure mode, may consume context
budget processing the degraded output. Blocking background dispatch eliminates
this silent failure path entirely.

### The Deterministic Skill Loading Chain

Three hooks cooperate to ensure the `daaf-orchestrator` skill loads at the start
of every session, regardless of whether the model "remembers" to do so:

1. **remind-orchestrator.sh** (UserPromptSubmit) checks for a flag file. If
   absent, injects a directive to load the skill.
2. The model, receiving the directive, calls the Skill tool with
   `skill: "daaf-orchestrator"`.
3. **flag-orchestrator-loaded.sh** (PostToolUse/Skill) detects the skill name
   and creates the flag file.
4. On the next user message, **remind-orchestrator.sh** finds the flag file and
   emits nothing -- the loading chain is complete.

This three-hook chain converts a behavioral expectation (load the orchestrator
skill) into a deterministic guarantee. The flag file is session-scoped
(`/tmp/claude-daaf-orchestrator-{session_id}`), so it resets on each new session,
ensuring the skill is loaded fresh every time.

### Inter-Hook Communication via /tmp Files

Five `/tmp` cache files enable data sharing across hooks and supporting scripts
that fire at different lifecycle points:

| File Pattern | Writer | Reader(s) | Purpose |
|-------------|--------|-----------|---------|
| `/tmp/claude-ctx-window-{session_id}` | context-bar.sh (statusLine) | context-reporter.sh | Share context window size from the status bar to the utilization monitor |
| `/tmp/claude-ctx-ts-{session_id}` | context-reporter.sh | context-reporter.sh | Rate-limiting gate: stores timestamp of last injection to enforce 60-second interval |
| `/tmp/claude-model-{session_id}` | context-reporter.sh | audit-log.sh | Share model name extracted from the transcript for inclusion in audit entries |
| `/tmp/claude-daaf-orchestrator-{session_id}` | flag-orchestrator-loaded.sh | remind-orchestrator.sh | Skill-loaded flag: stops orchestrator reminders after skill loads |
| `/tmp/claude-or-models-{session_id}` | context-bar.sh | context-bar.sh | OpenRouter API model cache (self-consumption for API response caching) |

The `/tmp` filesystem is the natural communication channel because: hooks run as
independent shell processes with no shared memory, the data is session-scoped and
ephemeral (correctly discarded on container restart), and `/tmp` is always
writable regardless of project directory permissions.

The cross-script data flow for context monitoring illustrates this pattern's
power: `context-bar.sh` (running as a statusLine, not a hook) discovers the
context window size and writes it to `/tmp`. `context-reporter.sh` (running as a
hook on different events) reads that value to compute utilization percentage and
writes the model name. `audit-log.sh` (running as a PostToolUse hook) reads the
model name to include in audit entries. Three independent scripts, firing at
different lifecycle points, sharing data through files -- no coupling, no
coordination protocol, no race conditions (each file has a single writer).

### Subagent Firing Matrix

Understanding which hooks fire in which context is critical for reasoning about
enforcement coverage. The matrix below summarizes firing behavior across three
contexts:

| Hook Script | Orchestrator | Subagent (with frontmatter hooks) | Subagent (without frontmatter hooks) |
|-------------|:------------:|:---------------------------------:|:------------------------------------:|
| **SessionStart hooks** | | | |
| recover-session-logs.sh | Yes | No | No |
| **UserPromptSubmit hooks** | | | |
| context-reporter.sh | Yes | No | No |
| remind-orchestrator.sh | Yes | No | No |
| **PreToolUse hooks (settings.json)** | | | |
| context-reporter.sh | Yes | Yes | Yes |
| enforce-explore-model.sh | Yes | Yes | Yes |
| enforce-foreground-agents.sh | Yes | Yes | Yes |
| deny-claude-code-guide.sh | Yes | Yes | Yes |
| bash-safety.sh | Yes | Yes | Yes |
| **PreToolUse hooks (frontmatter)** | | | |
| enforce-file-first.sh | No | Yes (4 coding agents) | No |
| **PostToolUse hooks** | | | |
| audit-log.sh | Yes | Yes | Yes |
| output-scanner.sh | Yes | Yes | Yes |
| flag-orchestrator-loaded.sh | Yes | Yes | Yes |
| **SessionEnd hooks** | | | |
| archive-session.sh | Yes | No | No |

Key observations:

- **Safety hooks have universal coverage** through settings.json. Every Bash
  command is inspected by `bash-safety.sh` whether it originates from the
  orchestrator or any subagent. Every subagent dispatch is inspected by the three
  agent-blocking hooks regardless of who dispatches it.

- **File-first enforcement is precisely scoped.** Only the four coding agents
  have `enforce-file-first.sh` in their frontmatter. The orchestrator is exempt
  (it runs administrative commands), and read-only agents are exempt (they cannot
  execute scripts).

- **Observability has universal coverage** for tool calls. `audit-log.sh` and
  `output-scanner.sh` fire for every PostToolUse event regardless of context.
  The audit log explicitly captures `agent_type` and `agent_id` to attribute
  tool calls to their originating agent.

- **Session lifecycle hooks are orchestrator-only.** SessionStart and SessionEnd
  fire once per session, not per subagent. `archive-session.sh` handles
  subagent transcripts by discovering them from the file hierarchy, not by
  firing separately for each subagent.

- **UserPromptSubmit is orchestrator-only.** This event fires when a *human user*
  submits a message. Subagents receive their prompts from the orchestrator via
  tool dispatch, not from user input, so UserPromptSubmit never fires in a
  subagent context. This is why `remind-orchestrator.sh` reaches only the
  orchestrator -- by design.

- **context-reporter.sh reaches subagents via PreToolUse** even though it cannot
  reach them via UserPromptSubmit. The PreToolUse registration (universal
  matcher) ensures subagents receive utilization injections, enabling them to
  follow the early-return protocol under context pressure.

---

## Replication Specification

An implementer must provide the following capabilities to achieve hook system
feature parity:

### Required Harness Capabilities

| Capability | Purpose | Used By |
|------------|---------|---------|
| Pre-execution tool interception with blocking | Inspect and block tool calls before execution | bash-safety, enforce-file-first, agent-blocking hooks |
| Post-execution tool interception | Observe tool results after execution | audit-log, output-scanner, flag-orchestrator-loaded |
| User message interception | Inject context before model processes user input | context-reporter, remind-orchestrator |
| Session lifecycle events | Respond to session start and end | recover-session-logs, archive-session |
| Tool-specific routing/matching | Route hooks to specific tool types | Bash matcher, Task/Agent matcher, Skill matcher |
| Per-agent hook registration | Scope hooks to specific agent types | enforce-file-first (4 coding agents) |
| Structured context injection | Inject text into model context without blocking | context-reporter (additionalContext) |
| Access to session transcript | Read the raw conversation for archival/analysis | archive-session, context-reporter, recover-session-logs |
| Structured input to hooks | Provide session ID, tool name, tool input, tool response, agent identity | All hooks |
| Configurable timeouts | Different hooks need different time budgets | archive-session (60s) vs. others (5s) |

### Behavioral Contract

1. **Safety hooks must block before execution.** If the harness cannot intercept
   tool calls before execution, safety hooks cannot function. Post-execution
   notification is insufficient -- the damage is already done.

2. **Blocking must surface a reason.** The model must receive an explanation of
   why its action was blocked so it can adjust its approach. Silent blocking
   produces retry loops.

3. **Observability hooks must never block.** Even if a hook times out, errors,
   or produces malformed output, the tool call must proceed.

4. **Hook execution must be synchronous for Pre/PostToolUse.** The tool call
   must wait for all PreToolUse hooks to complete before executing, and all
   PostToolUse hooks must complete before the result is processed by the model.
   Asynchronous hooks would create race conditions in safety enforcement.

5. **Session hooks may be asynchronous.** SessionStart recovery can run in the
   background (and does). SessionEnd archival runs synchronously but with a
   generous timeout.

### Acceptance Criteria

Feature parity is achieved when:

- A `rm -rf /` command issued by any agent (orchestrator or subagent) is blocked
  before execution, and the model receives a descriptive error message.
- A direct `python script.py` command issued by a coding agent is blocked, while
  the same command issued by the orchestrator is allowed.
- An Explore, claude-code-guide, or background agent dispatch is blocked with a
  redirect message.
- Every tool call (orchestrator and subagent) produces an audit log entry with
  correct agent attribution.
- Tool output containing an API key pattern triggers a warning injected into
  model context.
- Context utilization data is injected into model context at least once per 60
  seconds during active operation, for both orchestrator and subagents.
- The orchestrator skill loading chain completes deterministically on every new
  session.
- Sessions that terminate abnormally are recovered and archived on the next
  session start.
- All of the above continues to function when hooks encounter malformed input,
  missing dependencies, or timeout conditions -- with safety hooks blocking and
  observability hooks allowing.

### Degraded-Mode Options

If full parity is not achievable:

- **No per-agent hook scoping:** Register `enforce-file-first.sh` globally and
  add an internal check for agent type (if the harness provides agent identity in
  the hook input). The hook would need to maintain a list of exempt agents and
  pass through for non-coding agents.

- **No PreToolUse blocking (critical gap):** If the harness lacks pre-execution
  interception, safety enforcement must move to the permission system (deny
  patterns) and behavioral instructions. This significantly weakens the safety
  model -- deny patterns cannot match with the regex sophistication of
  `bash-safety.sh`, and instructions can be ignored.

- **No UserPromptSubmit event:** The orchestrator skill loading chain would need
  to be triggered differently -- perhaps via a SessionStart hook that injects the
  directive, or via a "first PreToolUse" detection pattern.

- **No structured context injection (additionalContext):** Context monitoring
  could fall back to a less integrated mechanism, such as including utilization
  data in tool error messages or writing it to a file the model is instructed to
  check periodically. This is substantially less effective than transparent
  injection.

---

## Harness Landscape

Four of six surveyed harnesses support some form of hook system:

- **Codex (OpenAI):** Pre/post-execution hooks planned but not yet shipped as of
  survey date. Sandbox enforcement is built-in rather than hook-based.
- **Cursor:** Supports `rules` with triggering conditions, which can approximate
  PreToolUse injection. No exit-code-based blocking.
- **OpenCode:** Supports event hooks with pre/post tool execution. Closest
  architectural match to Claude Code's hook model.
- **Aider:** No hook system. Behavioral control is instruction-only.
- **Windsurf:** Limited lifecycle events. No pre-execution blocking.

The key differentiator is **pre-execution blocking with exit code semantics** --
only Claude Code and OpenCode currently support hooks that can prevent a tool
call from executing based on inspection of the call's parameters. This is the
foundation of DAAF's safety model.

---

## Dependencies

**This section depends on:**
- Section 3 (Instruction Loading) -- Hooks are registered in settings.json, which
  is part of the instruction loading infrastructure
- Section 4 (Agent System) -- Per-agent hooks depend on the agent frontmatter
  system; agent-blocking hooks depend on the dispatch mechanism
- Section 5 (Permission System) -- Hooks and permissions form complementary
  enforcement layers in the defense-in-depth architecture

**Other sections that depend on this one:**
- Section 5 (Permission System) -- Hooks are listed as a security layer in the
  defense-in-depth model
- Section 6 (Skill System) -- The deterministic skill loading chain uses three
  cooperating hooks
- Section 8 (Context Management) -- context-reporter.sh is the implementation
  mechanism for DAAF's context self-monitoring
- Section 9 (Logging and Audit Trail) -- audit-log.sh, output-scanner.sh,
  archive-session.sh, and recover-session-logs.sh are all hooks
- Section 10 (Tool System) -- bash-safety.sh and enforce-file-first.sh gate tool
  execution
