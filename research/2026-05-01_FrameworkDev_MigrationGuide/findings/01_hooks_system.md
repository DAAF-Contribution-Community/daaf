# DAAF Hooks System — Complete Migration Reference

> **Generated:** 2026-05-01
> **Purpose:** Comprehensive documentation of DAAF's use of Claude Code's hooks system, sufficient to reconstruct the entire hooks architecture in another AI coding harness.

---

## Table of Contents

1. [Hook Registration Structure (settings.json)](#1-hook-registration-structure-settingsjson)
2. [Claude Code Hook Event Lifecycle](#2-claude-code-hook-event-lifecycle)
3. [Hook Scripts — Detailed Documentation](#3-hook-scripts--detailed-documentation)
4. [Per-Agent Hooks (Frontmatter)](#4-per-agent-hooks-frontmatter)
5. [Hook Interaction with Subagents](#5-hook-interaction-with-subagents)
6. [Supporting Files](#6-supporting-files)
7. [Cross-Cutting Patterns](#7-cross-cutting-patterns)
8. [Migration Considerations](#8-migration-considerations)

---

## 1. Hook Registration Structure (settings.json)

The `hooks` key in `/daaf/.claude/settings.json` (lines 96-227) defines hooks organized by event type. Each event type contains an array of matcher objects, each with an array of hook command entries.

### Complete JSON Structure

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/context-reporter.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/remind-orchestrator.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/context-reporter.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/enforce-explore-model.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/enforce-foreground-agents.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/deny-claude-code-guide.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Agent",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/enforce-explore-model.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/enforce-foreground-agents.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/deny-claude-code-guide.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bash-safety.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/audit-log.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/output-scanner.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/flag-orchestrator-loaded.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/archive-session.sh",
            "timeout": 60
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/recover-session-logs.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Matcher Semantics

- `""` (empty string): Matches ALL tool calls for that event type (universal hook).
- `"Bash"`: Matches only when the tool being invoked is the Bash tool.
- `"Task"`: Matches only when the tool being invoked is the Task (subagent) tool.
- `"Agent"`: Matches only when the tool being invoked is the Agent (subagent) tool.
- `"Skill"`: Matches only when the tool being invoked is the Skill tool.

### Summary Registration Table

| Event | Matcher | Script | Timeout |
|-------|---------|--------|---------|
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
| SessionStart | `""` (all) | recover-session-logs.sh | 5s |

**Note:** `enforce-explore-model.sh`, `enforce-foreground-agents.sh`, and `deny-claude-code-guide.sh` are each registered TWICE (once for `"Task"`, once for `"Agent"`) because Claude Code has two different subagent tool names.

**Note:** `enforce-file-first.sh` is NOT in settings.json. It is registered exclusively via per-agent frontmatter hooks (see Section 4).

---

## 2. Claude Code Hook Event Lifecycle

### 2.1 Event Types

| Event | When It Fires | Matcher Relevance |
|-------|---------------|-------------------|
| **SessionStart** | When a new Claude Code session begins (before any user input) | `""` only (no tools involved) |
| **UserPromptSubmit** | When the user submits a message (before the model processes it) | `""` only (no tools involved) |
| **PreToolUse** | After the model decides to use a tool, BEFORE the tool executes | Tool name matcher (e.g., `"Bash"`, `"Agent"`, `"Task"`, `"Skill"`, or `""` for all) |
| **PostToolUse** | AFTER a tool finishes executing | Tool name matcher (same as above) |
| **SessionEnd** | When the session terminates (user exits, /exit, crash recovery) | `""` only |

### 2.2 Data Passed to Hook Scripts (stdin JSON)

**Common fields (all events):**
- `session_id` — UUID string identifying the session
- `transcript_path` — absolute path to the session's JSONL transcript file
- `hook_event_name` — the event type string (e.g., `"PreToolUse"`)

**Tool-related events (PreToolUse, PostToolUse) add:**
- `tool_name` — the tool being invoked (e.g., `"Bash"`, `"Read"`, `"Agent"`, `"Skill"`)
- `tool_input` — the full input object being passed to the tool (e.g., `{"command": "ls"}` for Bash, `{"file_path": "/foo"}` for Read, `{"subagent_type": "search-agent"}` for Agent)

**PostToolUse additionally adds:**
- `tool_response` — the tool's output/return value
- `agent_type` — for subagent calls, the type of the running agent (e.g., `"research-executor"`); empty for orchestrator
- `agent_id` — for subagent calls, the UUID of the agent instance; empty for orchestrator

**SessionEnd adds:**
- `cwd` — the current working directory
- `reason` — why the session ended (e.g., `"unknown"`, `"recovered"`)

### 2.3 How Hook Output Is Processed by Claude Code

**Exit code handling:**

| Exit Code | Meaning | Effect |
|-----------|---------|--------|
| 0 | Pass/Allow | Tool execution proceeds. Any stdout is processed based on event type. |
| 1 | Error | The hook encountered an error. Claude Code logs it but does not block. Tool proceeds. |
| 2 | Block | **PreToolUse only.** The tool execution is BLOCKED. The stderr message is shown to the model as an error. |

**Stdout processing by event type:**

| Event | Stdout Format | How Claude Code Injects It |
|-------|---------------|---------------------------|
| **UserPromptSubmit** | Plain text | Injected as `<user-prompt-submit-hook>` block in the user's message context |
| **PreToolUse** | JSON with `hookSpecificOutput` | Two possible mechanisms (see below) |
| **PostToolUse** | Plain text | Injected as context after the tool result |
| **SessionStart/SessionEnd** | Plain text | Displayed to the user (not injected into model context) |

### 2.4 PreToolUse JSON Output Mechanisms

**Mechanism 1 — Permission decision (deny):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Explanation shown to the model"
  }
}
```
Tells Claude Code to deny the tool call. The `permissionDecisionReason` is shown to the model. The tool does NOT execute.

**Mechanism 2 — Additional context (inject):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "Text injected as a <system-reminder> before the tool executes"
  }
}
```
Does NOT block the tool. Injects the `additionalContext` string as a `<system-reminder>` that the model sees. The tool proceeds to execute.

**Key distinction:** Exit code 2 with stderr blocks via exit code (used by `bash-safety.sh`, `enforce-file-first.sh`). JSON `permissionDecision: "deny"` blocks via JSON (used by `enforce-explore-model.sh`, `enforce-foreground-agents.sh`, `deny-claude-code-guide.sh`). Both prevent execution, but JSON is more structured and provides a formatted redirect message.

| Mechanism | Scripts Using It | When to Use |
|-----------|------------------|-------------|
| Exit code 2 + stderr | bash-safety.sh, enforce-file-first.sh | For Bash commands: the command IS the danger |
| JSON permissionDecision: deny | enforce-explore-model.sh, enforce-foreground-agents.sh, deny-claude-code-guide.sh | For Agent/Task calls: redirect with structured explanation |
| JSON additionalContext | context-reporter.sh | Informational context injection without blocking |

---

## 3. Hook Scripts — Detailed Documentation

### 3.1 context-reporter.sh

- **File:** `/daaf/.claude/hooks/context-reporter.sh` (175 lines)
- **Events:** UserPromptSubmit + PreToolUse (universal matcher)
- **Purpose:** Injects context utilization percentage and severity into the conversation for informed delegation, state persistence, and session recovery decisions. Implements the dual-trigger threshold system from CLAUDE.md.
- **Input:** stdin JSON: `hook_event_name`, `session_id`, `transcript_path`
- **Processing logic:**
  1. Rate limiting via `/tmp/claude-ctx-ts-{session_id}` — skips if fewer than 60 seconds since last injection. Both events share the same gate.
  2. Reads context window size from `/tmp/claude-ctx-window-{session_id}` (written by `context-bar.sh` statusline). For subagents (different session ID), falls back to most recently modified `/tmp/claude-ctx-window-*`. Defaults to 200,000.
  3. Token calculation: `tail -50` on transcript JSONL, finds last non-sidechain/non-error message, sums `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
  4. Severity classification (dual-trigger — whichever fires first):
     - CRITICAL: pct >= 75 OR used_k >= 250
     - HIGH: pct >= 60 OR used_k >= 200
     - ELEVATED: pct >= 40 OR used_k >= 150
     - NOMINAL: below all thresholds
  5. Caches model name to `/tmp/claude-model-{session_id}` (consumed by `audit-log.sh`).
- **Output:**
  - UserPromptSubmit: plain text → `<user-prompt-submit-hook>`
    ```
    Context utilization [ELEVATED]: 156k / 1000k tokens (15%) | 2026-05-01 14:30:00 UTC
    ```
  - PreToolUse: JSON → `<system-reminder>`
    ```json
    {"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Context utilization [ELEVATED]: 156k / 1000k tokens (15%) | 2026-05-01 14:30:00 UTC"}}
    ```
- **Exit code:** Always 0 (never blocks)

### 3.2 remind-orchestrator.sh

- **File:** `/daaf/.claude/hooks/remind-orchestrator.sh` (56 lines)
- **Event:** UserPromptSubmit (universal matcher)
- **Purpose:** Ensures daaf-orchestrator skill is loaded at session start. On first-ever session, injects transparency onboarding.
- **Input:** stdin JSON: `session_id`
- **Processing logic:**
  1. Checks flag file `/tmp/claude-daaf-orchestrator-{session_id}` (set by `flag-orchestrator-loaded.sh`).
  2. If flag does NOT exist, emits reminder to load the skill.
  3. First-session detection: reads `.claude/logs/activity.log` line count. If <= 1, also reads and emits `first-run-transparency.txt`.
- **Output:** Plain text → `<user-prompt-submit-hook>`
  ```
  You are interacting with a human user. You MUST IMMEDIATELY invoke the daaf-orchestrator skill (Skill tool with skill: "daaf-orchestrator") BEFORE doing any other work.
  ```
- **Exit code:** Always 0

### 3.3 bash-safety.sh

- **File:** `/daaf/.claude/hooks/bash-safety.sh` (131 lines)
- **Event:** PreToolUse, matcher `"Bash"`
- **Purpose:** Primary safety guardrail. Blocks dangerous Bash commands.
- **Input:** stdin JSON: `tool_name`, `tool_input.command`
- **Processing logic:**
  1. Fail-closed trap: `trap 'echo "BLOCKED..." >&2; exit 2' ERR`
  2. Dependency check: blocks (exit 2) if `jq` missing.
  3. Extracts and normalizes command (collapses whitespace).
  4. Pattern checks (most dangerous first): destructive filesystem (`rm -rf` targeting critical paths), destructive git (force push, reset hard, clean, checkout/restore `.`, branch -D), privilege escalation (sudo, su, chmod 777/u+s), dangerous network (curl/wget pipe to shell, curl -d @file, --upload-file), container escape (docker run, mount, chroot).
- **Output:** On block: descriptive message to stderr. On pass: no output.
- **Exit code:** 0 = allow, 2 = BLOCK

### 3.4 enforce-explore-model.sh

- **File:** `/daaf/.claude/hooks/enforce-explore-model.sh` (24 lines)
- **Event:** PreToolUse, matchers `"Task"` and `"Agent"`
- **Purpose:** Blocks Explore-type subagents (which run on Haiku). Redirects to search-agent.
- **Input:** stdin JSON: `tool_input.subagent_type`
- **Processing logic:** Fail-closed trap. If subagent_type = "Explore", emit deny JSON.
- **Output:** JSON `permissionDecision: "deny"` with redirect instructions.
- **Exit code:** Always 0 (deny communicated via JSON)

### 3.5 enforce-foreground-agents.sh

- **File:** `/daaf/.claude/hooks/enforce-foreground-agents.sh` (27 lines)
- **Event:** PreToolUse, matchers `"Task"` and `"Agent"`
- **Purpose:** Blocks background agents (can't prompt for permissions).
- **Input:** stdin JSON: `tool_input.run_in_background`
- **Processing logic:** Fail-closed trap. If run_in_background = "true", emit deny JSON.
- **Output:** JSON `permissionDecision: "deny"`.
- **Exit code:** Always 0

### 3.6 deny-claude-code-guide.sh

- **File:** `/daaf/.claude/hooks/deny-claude-code-guide.sh` (25 lines)
- **Event:** PreToolUse, matchers `"Task"` and `"Agent"`
- **Purpose:** Blocks built-in claude-code-guide agent (opaque prompt, Haiku model).
- **Input:** stdin JSON: `tool_input.subagent_type`
- **Processing logic:** Fail-closed trap. If subagent_type = "claude-code-guide", emit deny JSON.
- **Output:** JSON `permissionDecision: "deny"` with redirect to search-agent + WebFetch.
- **Exit code:** Always 0

### 3.7 enforce-file-first.sh

- **File:** `/daaf/.claude/hooks/enforce-file-first.sh` (149 lines)
- **Event:** PreToolUse (via agent frontmatter only, NOT in settings.json)
- **Matcher:** `"Bash"` (in agent frontmatter)
- **Purpose:** Enforces file-first execution protocol: Python scripts must use `run_with_capture.sh`. Direct `python`/`python3` invocations blocked.
- **Input:** stdin JSON: `tool_name`, `tool_input.command`
- **Processing logic:**
  1. Fail-closed trap (exit 2 on error).
  2. Dependency and empty-input checks.
  3. Only inspects Bash tool calls.
  4. Normalization: replaces newlines with semicolons, collapses whitespace.
  5. Whitelist: commands matching `python3?[.0-9]* /daaf/scripts/[A-Za-z0-9_-]+\.py` are allowed (framework utility scripts).
  6. Detection regex: matches python/python3 invoked as command, with prefixes (env, exec, command, eval, nohup, nice, time, strace, VAR=value).
  7. On match: outputs multi-line error to stderr explaining the file-first protocol.
- **Output:** Error message to stderr when blocking. Explains the protocol and points to SCRIPT_EXECUTION_REFERENCE.md.
- **Exit code:** 0 = allow, 2 = BLOCK

### 3.8 audit-log.sh

- **File:** `/daaf/.claude/hooks/audit-log.sh` (99 lines)
- **Event:** PostToolUse (universal matcher)
- **Purpose:** Append-only JSONL audit trail at `.claude/logs/audit.jsonl`.
- **Input:** stdin JSON: `tool_name`, `session_id`, `agent_type`, `agent_id`, `tool_input.*`, `tool_response`
- **Processing logic:**
  1. Uses `set -u` but deliberately omits `set -e` (never blocks).
  2. Extracts tool name, session ID, agent type (defaults to "orchestrator"), agent ID.
  3. Gets DAAF version via `git describe --always --dirty`.
  4. Gets model from `/tmp/claude-model-{session_id}`.
  5. Extracts human-readable target per tool type (Bash: command, Read/Write/Edit: file_path, Glob/Grep: pattern, Task/Agent: description, WebFetch: url).
  6. Appends JSON line. `agent_id` included only for subagent calls.
- **Output:** No stdout. Writes to audit log only.
  ```json
  {"timestamp":"2026-05-01T14:30:00Z","session_id":"abc12345","tool":"Bash","target":"ls -la /daaf","daaf_version":"764f666","model":"claude-opus-4-6","agent_type":"orchestrator"}
  ```
- **Exit code:** Always 0

### 3.9 output-scanner.sh

- **File:** `/daaf/.claude/hooks/output-scanner.sh` (74 lines)
- **Event:** PostToolUse (universal matcher)
- **Purpose:** Scans tool output for leaked secrets/credentials.
- **Input:** stdin JSON: `tool_response`
- **Processing logic:**
  1. Extracts first 10,000 chars of `tool_response`.
  2. Regex checks for: AWS Access Key ID (`AKIA...`), AWS Secret (`aws_secret_access_key`), OpenAI/Anthropic keys (`sk-...`), Stripe live keys, GitHub tokens (`ghp_/gho_/ghs_/ghr_/github_pat_`), private key headers (`-----BEGIN...PRIVATE KEY-----`), long Bearer tokens.
- **Output:** Warning text to stdout if detected:
  ```
  WARNING: Potential secrets detected in tool output:
    - API key detected (sk-...)
    - GitHub token detected
  Do NOT display, log, or commit these values.
  ```
- **Exit code:** Always 0 (advisory only, never blocks)

### 3.10 flag-orchestrator-loaded.sh

- **File:** `/daaf/.claude/hooks/flag-orchestrator-loaded.sh` (22 lines)
- **Event:** PostToolUse, matcher `"Skill"`
- **Purpose:** Sets flag file when daaf-orchestrator skill loads, stopping reminders.
- **Input:** stdin JSON: `session_id`, `tool_input.skill`
- **Processing logic:** If skill = "daaf-orchestrator", touches `/tmp/claude-daaf-orchestrator-{session_id}`.
- **Output:** No stdout. Creates flag file.
- **Exit code:** Always 0

### 3.11 archive-session.sh

- **File:** `/daaf/.claude/hooks/archive-session.sh` (474 lines)
- **Event:** SessionEnd (universal matcher)
- **Timeout:** 60 seconds (longest of all hooks)
- **Purpose:** Archives complete session transcripts. Copies raw JSONL + converts to human-readable Markdown. Discovers and archives subagent transcripts. Processes pending log collection requests.
- **Input:** stdin JSON: `session_id`, `transcript_path`, `cwd`, `reason`
- **Processing logic:**
  1. Fail-open trap (archival is observability, not security).
  2. Creates archive directory `.claude/logs/sessions/`.
  3. For recovered sessions (`reason: "recovered"`), derives timestamp from transcript's last entry.
  4. Idempotency: compares source size against existing archive.
  5. Copies raw JSONL transcript.
  6. Markdown conversion via jq: user messages with timestamps, assistant messages with collapsible thinking blocks, tool uses with type-specific formatting, token usage. Tool results truncated at 1000 chars.
  7. Subagent archiving: discovers transcripts from `{transcript_dir}/{session-uuid}/subagents/agent-{id}.jsonl`. Reads `.meta.json` for agent type. Produces summary table + individual archives.
  8. Pending log collection: processes `.claude/logs/pending_log_collection.jsonl`.
- **Output:** Status to stdout. Creates files in `.claude/logs/sessions/`.
- **Archive naming:** `{date}_{time}_{session-short}_orchestrator.{jsonl,md}`, `{date}_{time}_{session-short}_subagent_{agent-id-short}.{jsonl,md}`
- **Exit code:** Always 0

### 3.12 recover-session-logs.sh

- **File:** `/daaf/.claude/hooks/recover-session-logs.sh` (165 lines)
- **Event:** SessionStart (universal matcher)
- **Purpose:** Activity logging + crash recovery for orphaned sessions.
- **Input:** stdin JSON: `session_id`, `transcript_path`
- **Processing logic:**
  1. Fail-open trap.
  2. **Foreground (fast):** Creates log directories. Appends to `.claude/logs/activity.log`: `Session started: {timestamp} | DAAF: {version} | Session: {short_id}`
  3. **Background (detached):** Builds index of already-archived sessions with file sizes. Timestamp-gated scan of transcripts modified since last recovery (`.claude/logs/.last_recovery`). Skips current session. For each unarchived transcript, synthesizes JSON payload with `reason: "recovered"` and pipes to `archive-session.sh`. Updates `.last_recovery`. Processes stale pending log collection.
  4. Background section runs fully detached: `( ... ) </dev/null >/dev/null 2>&1 &` + `disown`.
- **Output:** No stdout to model. Writes to activity.log and triggers archive-session.sh.
- **Exit code:** Always 0

---

## 4. Per-Agent Hooks (Frontmatter)

Four agent definition files register hooks in YAML frontmatter. All four register the same hook:

| Agent File | Agent Name | Hook Script | Event | Matcher | Timeout |
|------------|------------|-------------|-------|---------|---------|
| `/daaf/.claude/agents/code-reviewer.md` | code-reviewer | enforce-file-first.sh | PreToolUse | Bash | 5s |
| `/daaf/.claude/agents/data-ingest.md` | data-ingest | enforce-file-first.sh | PreToolUse | Bash | 5s |
| `/daaf/.claude/agents/debugger.md` | debugger | enforce-file-first.sh | PreToolUse | Bash | 5s |
| `/daaf/.claude/agents/research-executor.md` | research-executor | enforce-file-first.sh | PreToolUse | Bash | 5s |

**Frontmatter structure (identical across all four):**
```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

**Design rationale:** Only "coding agents" — those that write and execute Python scripts — need file-first enforcement. Read-only agents, the framework-engineer, report-writer, and notebook-assembler are exempt.

**Agents WITHOUT per-agent hooks (11 agents):** data-planner, data-verifier, framework-engineer, integration-checker, notebook-assembler, plan-checker, report-writer, research-synthesizer, search-agent, source-researcher.

---

## 5. Hook Interaction with Subagents

### 5.1 Settings.json Hooks: Firing Context

**Hooks that fire for BOTH orchestrator AND subagents:**

| Hook | Evidence |
|------|----------|
| context-reporter.sh | Script explicitly documents subagent support. Falls back to most recent context window cache when subagent's session-specific cache doesn't exist. |
| bash-safety.sh | PreToolUse/Bash — fires for any Bash call regardless of context. |
| audit-log.sh | PostToolUse universal. Explicitly captures `agent_type` and `agent_id`, defaulting to "orchestrator" when empty. |
| output-scanner.sh | PostToolUse universal — fires for all tool calls. |
| enforce-explore-model.sh | PreToolUse/Task+Agent — fires when orchestrator dispatches subagents. |
| enforce-foreground-agents.sh | Same — fires at dispatch time. |
| deny-claude-code-guide.sh | Same — fires at dispatch time. |
| flag-orchestrator-loaded.sh | PostToolUse/Skill — fires after any Skill call in any context. |

**Hooks that fire for orchestrator ONLY:**

| Hook | Reason |
|------|--------|
| remind-orchestrator.sh | UserPromptSubmit only fires when human user submits a message. Subagents don't trigger it. |
| archive-session.sh | SessionEnd fires once when main session ends. Archives subagent transcripts by scanning file hierarchy. |
| recover-session-logs.sh | SessionStart fires once when new session begins. |

### 5.2 Per-Agent Frontmatter Hooks

Fire ONLY for the specific agents that declare them. When research-executor makes a Bash call, `enforce-file-first.sh` fires. When search-agent makes a Bash call, it does NOT fire.

### 5.3 Summary Matrix

| Context | UserPromptSubmit | PreToolUse (settings.json) | PreToolUse (frontmatter) | PostToolUse | Session hooks |
|---------|-----------------|---------------------------|-------------------------|-------------|---------------|
| Orchestrator | Yes | Yes | N/A | Yes | Yes |
| Subagent (with frontmatter hooks) | No | Yes | Yes | Yes | No |
| Subagent (without frontmatter hooks) | No | Yes | No | Yes | No |

---

## 6. Supporting Files

### 6.1 first-run-transparency.txt

- **File:** `/daaf/.claude/hooks/first-run-transparency.txt` (59 lines)
- **Purpose:** Injected on first-ever session. Structured onboarding covering: what DAAF is, LLM limitations (hallucination, sycophancy, over-confidence, subtle logical errors, laziness, non-determinism), practical guidance, language background note, resource pointers.
- **Detection:** activity.log line count <= 1.

### 6.2 context-bar.sh (Status line, not a hook)

- **File:** `/daaf/.claude/scripts/context-bar.sh` (200 lines)
- **Registered as:** `statusLine` in settings.json
- **Purpose:** Terminal status bar showing model, directory, branch, context utilization.
- **Critical bridge function:** Writes context window size to `/tmp/claude-ctx-window-{session_id}` (consumed by `context-reporter.sh`). This enables the cross-script context monitoring system.
- **OpenRouter support:** Queries OpenRouter API for actual context_length when using non-Anthropic models.

---

## 7. Cross-Cutting Patterns

### 7.1 Fail-Closed vs Fail-Open

| Pattern | Used By | Rationale |
|---------|---------|-----------|
| **Fail-closed** (exit 2 on error) | bash-safety.sh, enforce-file-first.sh | Security: ambiguous failures must block |
| **Fail-closed** (JSON deny on error) | enforce-explore-model.sh, enforce-foreground-agents.sh, deny-claude-code-guide.sh | Policy: errors should deny |
| **Fail-open** (exit 0 on error) | All observability/informational hooks | Must never block operations |

### 7.2 Inter-Hook Communication via /tmp Files

| File | Writer | Reader | Purpose |
|------|--------|--------|---------|
| `/tmp/claude-ctx-window-{session_id}` | context-bar.sh | context-reporter.sh | Share context window size |
| `/tmp/claude-ctx-ts-{session_id}` | context-reporter.sh | context-reporter.sh | Rate-limiting gate |
| `/tmp/claude-model-{session_id}` | context-reporter.sh | audit-log.sh | Share model name |
| `/tmp/claude-daaf-orchestrator-{session_id}` | flag-orchestrator-loaded.sh | remind-orchestrator.sh | Skill-loaded flag |
| `/tmp/claude-or-models-{session_id}` | context-bar.sh | context-bar.sh | OpenRouter API cache |

### 7.3 Defense-in-Depth Layers

| Layer | Mechanism | Coverage |
|-------|-----------|----------|
| PreToolUse hooks | bash-safety.sh | Destructive commands, escalation, pipe-to-shell, exfiltration, escape |
| PreToolUse hooks (agent-scoped) | enforce-file-first.sh | Direct Python execution bypass |
| Permission deny rules | settings.json | File operations, credential access, infrastructure |
| Permission allow list | settings.json | Auto-execute allowlist |
| PostToolUse hooks | audit-log.sh, output-scanner.sh | Audit trail, secret detection |
| Context reporting | context-reporter.sh | Utilization monitoring |
| Session archival | archive-session.sh | Transcript preservation |
| Session recovery | recover-session-logs.sh | Crash recovery |
| Container isolation | Docker | OS-level containment |
| File exclusion | .claudeignore | Credential indexing prevention |
| Pre-commit hooks | .pre-commit-config.yaml | Commit-time validation |

---

## 8. Migration Considerations

### 8.1 Required Capabilities in Target Harness

| Capability | DAAF Usage | Migration Complexity |
|------------|-----------|---------------------|
| Pre-execution interception (PreToolUse) | Safety blocking, policy enforcement, context injection | HIGH — core safety mechanism |
| Post-execution interception (PostToolUse) | Audit logging, secret scanning | HIGH — observability foundation |
| Session lifecycle events (Start/End) | Activity logging, crash recovery, transcript archiving | MEDIUM — could be approximated |
| User message interception (UserPromptSubmit) | Skill loading enforcement, context reporting | HIGH — behavioral shaping |
| Tool-specific matchers | Bash safety, Agent blocking, Skill flagging | HIGH — granularity is essential |
| Per-agent hook registration | File-first enforcement for coding agents only | HIGH — agent-scoped behavior |
| Exit code 2 blocking | bash-safety.sh, enforce-file-first.sh | HIGH — fail-closed safety |
| JSON permission decision deny | Agent/Task blocking hooks | MEDIUM — could use exit code instead |
| JSON additionalContext injection | Context reporter | MEDIUM — needs system-reminder equivalent |
| Inter-hook /tmp file communication | Cross-script data sharing | LOW — standard Unix pattern |
| Hook timeout configuration | Per-hook timeout (5s default, 60s for archival) | LOW — standard process management |

### 8.2 Unique DAAF Hook Patterns

These patterns are DAAF-specific architectural decisions that would need to be replicated regardless of harness:

1. **Deterministic skill loading chain:** remind-orchestrator → Skill call → flag-orchestrator-loaded (three hooks cooperating via flag file)
2. **Dual-trigger context thresholds:** percentage OR absolute tokens, with rate limiting
3. **Subagent context window fallback:** reading most recent /tmp cache file when session-specific cache doesn't exist
4. **Crash recovery via SessionStart:** background reconciliation of transcripts against archives
5. **Idempotent archival:** file-size comparison to avoid re-archiving unchanged transcripts
6. **Agent-scoped enforcement:** using frontmatter hooks to restrict only certain agent types

### 8.3 Gaps and Limitations

- The exact Claude Code hook input JSON schema is inferred from what each script parses, not from an authoritative specification.
- Whether hooks fire for nested subagents (sub-subagents) is not explicitly documented. DAAF's `enforce-foreground-agents.sh` may prevent this scenario.
- The `statusLine` input schema differs from hook schemas and is documented only by observation of what `context-bar.sh` parses.
