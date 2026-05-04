# Finding 06: Logging, Session Management, and Audit Trail

## Overview

DAAF implements a multi-layered observability and audit trail system built on top of Claude Code's native hook infrastructure and JSONL session transcripts. The system serves five goals: post-session review, debugging, accountability, reproducibility, and research transparency. This document provides a complete technical reconstruction of every component.

The architecture has four major subsystems:

1. **Real-time audit logging** — JSONL append-only log of every tool invocation
2. **Output scanning** — PostToolUse secret detection to prevent credential leakage
3. **Session archiving** — Full session transcript archival with JSONL-to-Markdown conversion
4. **Script execution capture** — Inline execution logs appended to Python scripts as immutable audit artifacts

Additionally, DAAF provides:
- **Session recovery** — Crash-resilient recovery of orphaned transcripts on session start
- **Log collection and viewing** — Project-scoped log gathering and an interactive HTML viewer
- **Context monitoring** — Continuous context window utilization reporting

---

## 1. Audit Log System

### File: `.claude/hooks/audit-log.sh`

**Hook Type:** PostToolUse (matcher: `""` — fires for ALL tools)
**Registration:** `.claude/settings.json` under `hooks.PostToolUse[0].hooks[1]` (first PostToolUse handler along with output-scanner)
**Exit Code:** Always 0 (PostToolUse hooks must never block execution)

### What Events Trigger It

Every tool invocation in the Claude Code session triggers an audit log entry after the tool completes. This includes tool calls from both the orchestrator and all subagents. The hook fires indiscriminately for ALL tools — Read, Write, Edit, Bash, Glob, Grep, Skill, Agent, WebFetch, and any others.

### What Data Is Captured

Each log entry records seven (or eight) fields:

| Field | Source | Description |
|-------|--------|-------------|
| `timestamp` | `date -u '+%Y-%m-%dT%H:%M:%SZ'` | UTC ISO 8601 timestamp from the system clock |
| `session_id` | Hook JSON `.session_id` | UUID of the Claude Code session |
| `tool` | Hook JSON `.tool_name` | Name of the tool invoked (Read, Bash, Write, etc.) |
| `target` | Extracted per tool type (see below) | Human-readable summary of what was targeted |
| `daaf_version` | `git describe --always --dirty` | Git commit hash of the DAAF repo (provenance) |
| `model` | Cached from context-reporter (`/tmp/claude-model-{SESSION_ID}`) | The Claude model name (e.g., `claude-opus-4-6`) |
| `agent_type` | Hook JSON `.agent_type`, default `"orchestrator"` | Who made the call — `"orchestrator"` for main thread, agent type string for subagents |
| `agent_id` | Hook JSON `.agent_id` (optional) | Only present for subagent calls — the subagent's unique ID |

### Target Extraction Logic

The `target` field is extracted differently depending on the tool type:

```
Bash     → .tool_input.command (first 200 chars)
Read     → .tool_input.file_path
Write    → .tool_input.file_path
Edit     → .tool_input.file_path
Glob     → .tool_input.pattern
Grep     → .tool_input.pattern
Task     → .tool_input.description
Agent    → .tool_input.description
WebFetch → .tool_input.url
*        → "" (empty string for unknown tools)
```

### Where Logs Are Written

**Path:** `{CLAUDE_PROJECT_DIR}/.claude/logs/audit.jsonl`

In DAAF's Docker container, this resolves to `/daaf/.claude/logs/audit.jsonl`.

The directory is created with `mkdir -p` if it doesn't exist. The file is append-only (uses `>>` redirect).

### Log Entry Format

JSONL (one JSON object per line). Example entries from the actual log:

```json
{"timestamp":"2026-04-30T21:37:48Z","session_id":"eb0b4ff7-3beb-415a-907c-f52ce0a0a926","tool":"Glob","target":"**/run_daaf*","daaf_version":"v1.0.0-235-g08887d4","model":"claude-opus-4-6","agent_type":"orchestrator"}
```

```json
{"timestamp":"2026-04-30T21:42:25Z","session_id":"6fbf74d6-9ab4-4e8b-b548-de644112a442","tool":"Read","target":"/daaf/README.md","daaf_version":"v1.0.0-235-g08887d4","model":"claude-opus-4-6","agent_type":"search-agent","agent_id":"ab2f4c9bf7097ec58"}
```

Note: The `agent_id` field is only present when `agent_type` is not `"orchestrator"`. The JSON construction uses `jq` with a conditional to include it:

```bash
jq -n -c \
    --arg ts "$TIMESTAMP" \
    --arg sid "$SESSION_ID" \
    --arg tool "$TOOL_NAME" \
    --arg target "$TARGET" \
    --arg ver "$DAAF_VERSION" \
    --arg model "$MODEL" \
    --arg atype "$AGENT_TYPE" \
    --arg aid "$AGENT_ID" \
    '{timestamp: $ts, session_id: $sid, tool: $tool, target: $target, daaf_version: $ver, model: $model, agent_type: $atype}
     + (if $aid != "" then {agent_id: $aid} else {} end)' \
    >> "$LOG_FILE" 2>/dev/null
```

### Error Handling

The script uses `set -u` (catch unset variables) but deliberately omits `set -e` so that parsing failures don't block execution. Every `jq` invocation has `2>/dev/null` and `|| VAR="fallback"` error recovery. The final `exit 0` is unconditional.

### Integration with Claude Code's Hook System

Claude Code passes a JSON payload to the hook via stdin. The hook reads it with `INPUT=$(cat)`. The JSON includes fields like `tool_name`, `session_id`, `tool_input`, `agent_type`, and `agent_id`. The hook parses these with `jq -r` and constructs the log entry. Because it's registered as a PostToolUse hook with an empty matcher, it fires after every tool call regardless of tool type.

### Protection Against Modification

The `settings.json` deny list includes:
```json
"Edit(.claude/logs/*)",
"Write(.claude/logs/*)"
```
This prevents Claude from modifying or overwriting log files, maintaining the append-only integrity.

---

## 2. Output Scanner

### File: `.claude/hooks/output-scanner.sh`

**Hook Type:** PostToolUse (matcher: `""` — fires for ALL tools)
**Registration:** `.claude/settings.json` under `hooks.PostToolUse[0].hooks[1]`
**Exit Code:** Always 0 (never blocks execution)

### What It Scans For

The scanner checks the first 10KB of every tool's response content for seven categories of credential patterns:

| Pattern | Regex | Description |
|---------|-------|-------------|
| AWS Access Key ID | `AKIA[0-9A-Z]{16}` | Always starts with AKIA, 20 chars total |
| AWS Secret Access Key | `(aws_secret_access_key\|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*[A-Za-z0-9/+=]{40}` | 40-char base64 after known key names |
| OpenAI/Anthropic API Key | `sk-[A-Za-z0-9_-]{20,}` | Generic `sk-` prefix, 20+ chars |
| Stripe Live Keys | `(sk_live_\|rk_live_\|pk_live_)[A-Za-z0-9]{20,}` | Stripe publishable/secret/restricted keys |
| GitHub Tokens | `(ghp_\|gho_\|ghs_\|ghr_\|github_pat_)[A-Za-z0-9_]{20,}` | Personal Access Tokens, OAuth, App, fine-grained |
| Private Key Headers | `-----BEGIN\s+(RSA\|DSA\|EC\|OPENSSH\|PGP)?\s*PRIVATE KEY-----` | PEM-format private key blocks |
| Bearer Tokens | `Bearer\s+[A-Za-z0-9_\-\.]{50,}` | Long (50+ char) bearer tokens |

### When It Fires

After every tool invocation (PostToolUse with empty matcher). The tool response content is extracted from the hook JSON's `.tool_response` field.

### What It Does When Detecting Secrets

If any pattern matches, the hook outputs a warning message to stdout. Claude Code injects this stdout into the model's conversation context, so the model becomes aware of the leak:

```
WARNING: Potential secrets detected in tool output:
  - AWS Access Key ID detected (AKIA...)
Do NOT display, log, or commit these values. Treat them as sensitive.
```

**Important:** The scanner does NOT block execution (always exits 0). It is an advisory warning, not an enforcement gate. The model is expected to respond appropriately upon receiving the warning (acknowledge the leak, avoid propagating the secret).

### Design Decisions

- **10KB limit:** Only the first 10KB of response content is scanned to avoid performance impact on large tool outputs. This means very large outputs could have secrets in the tail that go undetected.
- **Advisory, not blocking:** PostToolUse hooks cannot undo tool execution — the tool has already run. The scanner's role is to prevent the model from echoing/committing the secret downstream.
- **No false-positive handling:** The patterns are broad (e.g., any `sk-` prefix with 20+ chars). False positives are possible but harmless — an unnecessary warning is better than a missed leak.

---

## 3. Session Archiving

### File: `.claude/hooks/archive-session.sh`

**Hook Type:** SessionEnd (matcher: `""`)
**Registration:** `.claude/settings.json` under `hooks.SessionEnd[0].hooks[0]`
**Timeout:** 60 seconds (generous because archiving may process large transcripts)
**Exit Code:** Always 0

This is the most complex hook in DAAF (474 lines). It performs full session transcript archiving with JSONL-to-Markdown conversion.

### When It Fires

On `SessionEnd` — when the user ends a Claude Code session (via `/exit`, Ctrl-C, or the session naturally completes). It also fires when called synthetically by the recovery hook (see Section 4) with `reason: "recovered"`.

### What Data It Receives

Claude Code provides a JSON payload via stdin containing:

| Field | Description |
|-------|-------------|
| `session_id` | Full UUID of the session |
| `transcript_path` | Absolute path to Claude Code's native JSONL transcript file |
| `cwd` | Current working directory |
| `reason` | Why the session ended (e.g., `"user_exit"`, `"recovered"` for crash recovery) |

### Where Archives Are Stored

**Path:** `{PROJECT_DIR}/.claude/logs/sessions/`

In DAAF's container: `/daaf/.claude/logs/sessions/`

### Archive Naming Convention

Each session produces multiple files:

```
{date}_{time}_{session-short}_orchestrator.jsonl    — Raw JSONL copy of main session transcript
{date}_{time}_{session-short}_orchestrator.md       — Human-readable Markdown rendering
{date}_{time}_{session-short}_subagent_{agent-id-short}.jsonl  — Subagent transcript copies
{date}_{time}_{session-short}_subagent_{agent-id-short}.md     — Subagent Markdown renderings
```

Where:
- `{date}` = `YYYY-MM-DD`
- `{time}` = `HH-MM-SS`
- `{session-short}` = First 8 characters of the session UUID
- `{agent-id-short}` = First 8 characters of the subagent's agent ID

Example from the actual log archive:
```
2026-04-30_23-42-14_ee7114e8_orchestrator.jsonl
2026-04-30_23-42-14_ee7114e8_orchestrator.md
2026-04-30_23-42-14_ee7114e8_subagent_a3f5a4a1.jsonl
2026-04-30_23-42-14_ee7114e8_subagent_a3f5a4a1.md
2026-04-30_23-42-14_ee7114e8_subagent_a5737a52.jsonl
2026-04-30_23-42-14_ee7114e8_subagent_a5737a52.md
```

### Timestamp Derivation for Recovered Sessions

For normal `SessionEnd` archiving, the timestamp comes from the wall clock (`date`). For recovered sessions (`reason="recovered"`), the timestamp is derived from the last entry in the JSONL transcript. This ensures recovered archives sort chronologically by when the session actually ran, not when recovery discovered them.

### Idempotency

The archiver uses file-size comparison to skip sessions already archived. Logic:

1. Look for any existing `*_{session-short}_orchestrator.jsonl` in the archive directory
2. If found, compare the source transcript size to the existing archive size
3. If source <= existing: skip (already archived with same or more content)
4. If source > existing: remove stale archive and re-archive (transcript has grown since last archive, e.g., recovery archived a still-running session prematurely)

### Provenance Metadata

Before archiving, the script extracts:
- **DAAF version:** `git describe --always --dirty` (commit hash)
- **Model:** First `.message.model` entry from the JSONL transcript

### JSONL-to-Markdown Conversion

The archiver uses a single `jq` invocation (written to a temp file as a jq program) to convert the entire JSONL transcript into human-readable Markdown. The jq program processes each JSONL line independently and produces:

**For user messages:**
```markdown
## 👤 User
**Time:** HH:MM:SS

[User's message text]

---
```

**For assistant messages:**
```markdown
## 🤖 Assistant
**Time:** HH:MM:SS

<details>
<summary>💭 Thinking (N chars)</summary>
[Thinking content, truncated at 2000 chars]
</details>

[Assistant text content]

### 🔧 Tool: [ToolName]
[Tool-specific formatting]

*Tokens: in=NNNN, out=NNNN*

---
```

**Tool-specific formatting:**
- `Bash` → Code block with bash syntax
- `Read` → `**File:** \`path\``
- `Edit`/`Write` → `**File:** \`path\``
- `Task` → `**Type:** subagent_type  **Task:** description`
- Other → JSON code block of the input (truncated to 500 chars)

**For tool results:**
```markdown
### 📋 Tool Result
```
[Result content, truncated at 1000 chars]
```
```
or on error:
```markdown
### ⚠️ Tool Error
```
[Error content]
```
```

### Subagent Discovery

The archiver discovers subagent transcripts directly from Claude Code's raw file hierarchy:

```
{transcript_dir}/{session-uuid}/subagents/agent-{agent-id}.jsonl
{transcript_dir}/{session-uuid}/subagents/agent-{agent-id}.meta.json
```

The `.meta.json` file contains agent metadata including `agentType`. For each subagent found:

1. The JSONL transcript is copied to the archive directory
2. A human-readable Markdown rendering is generated using the same jq program
3. A summary table entry is added to the orchestrator's Markdown archive

**Subagent summary table in the orchestrator Markdown:**
```markdown
## 🤖 Subagent Activity

**Subagents dispatched:** N

| Agent Type | Agent ID | Timestamp | Duration | Tool Uses | Archive |
|---|---|---|---|---|---|
| search-agent | a3f5a4a1 | 21:42:14 | 2m 30s | 15 | `...subagent_a3f5a4a1.jsonl` |
```

Followed by the last assistant message excerpt from each subagent (truncated to 300 chars).

### Session Summary Footer

Each Markdown archive ends with:
```markdown
## 📊 Session Summary

**Total messages:** N
**Model:** claude-opus-4-6
**DAAF Version:** v1.0.0-238-g764f666
**Archive:** `/path/to/archive.jsonl`

*Archive completed: YYYY-MM-DD HH:MM:SS*
```

### Pending Log Collection Processing

After archiving, the script processes any pending log collection markers left by `collect_session_logs.sh`. This is a deferred copy mechanism:

1. Check for `{PROJECT_DIR}/.claude/logs/pending_log_collection.jsonl`
2. Atomically move it to a temp file (prevents TOCTOU race)
3. For each entry, check if the just-archived transcript references the project
4. If so, copy all session archives to the project's `logs/` directory
5. Clean up the temp file

### Error Handling

The script uses `trap '' ERR` (fail OPEN) — archival is observability-only, not a security gate. A malformed JSONL line should produce a gap in the archive, not kill the archiver.

---

## 4. Session Recovery

### File: `.claude/hooks/recover-session-logs.sh`

**Hook Type:** SessionStart (matcher: `""`)
**Registration:** `.claude/settings.json` under `hooks.SessionStart[0].hooks[0]`
**Timeout:** 5 seconds (foreground work must be fast to not delay session start)
**Exit Code:** Always 0

### When It Fires

On `SessionStart` — when a new Claude Code session begins. It performs two tasks:

### Section 1: Activity Logging (Foreground, <1 second)

1. Creates log directories: `mkdir -p` for `.claude/logs/` and `.claude/logs/sessions/`
2. Appends a line to `.claude/logs/activity.log`:
   ```
   Session started: YYYY-MM-DD HH:MM:SS | DAAF: v1.0.0-238-g764f666 | Session: abeffb6e
   ```

### Section 2: Crash Recovery (Background, Detached Subprocess)

The recovery logic runs in a background subprocess (`(...) </dev/null >/dev/null 2>&1 &` with `disown`) so it never blocks session startup.

#### How It Detects Incomplete Sessions

The recovery process works by reconciling two directories:

1. **Claude Code's native transcript storage** — derived from the current session's `transcript_path` (e.g., `~/.claude/projects/.../sessions/`)
2. **DAAF's archive directory** — `.claude/logs/sessions/`

The algorithm:

1. Derive the Claude Code transcript directory from the current session's `transcript_path`
2. Build an associative array (bash) of already-archived session IDs with their file sizes
3. Use `find` with a timestamp gate (files newer than `.last_recovery`) to avoid rescanning old transcripts
4. For each unarchived (or grown) transcript:
   a. Skip the current session (it just started)
   b. Skip if already archived with same or larger file size
   c. Otherwise, pipe a synthesized JSON payload to `archive-session.sh`

The synthesized JSON payload looks like:
```json
{
  "session_id": "UUID",
  "transcript_path": "/path/to/raw/transcript.jsonl",
  "cwd": "/daaf",
  "reason": "recovered"
}
```

The `reason: "recovered"` field tells `archive-session.sh` to derive the archive timestamp from the transcript's last entry rather than the wall clock.

#### Performance Optimizations

- **Timestamp-gated:** Only processes transcripts modified since the last recovery (uses a `.last_recovery` touch file)
- **Index-based matching:** Builds a bash associative array for O(n+m) matching, not O(n*m) globs
- **Background execution:** Recovery runs detached so session startup is never blocked
- **Idempotency:** `archive-session.sh`'s own idempotency guard provides a second safety net

#### Stale Pending Log Collection

The recovery hook also processes stale `pending_log_collection.jsonl` markers that may have been left by `collect_session_logs.sh` if the session crashed before `SessionEnd` could process them.

#### Recovery Activity Logging

If any sessions were recovered, the hook appends to `activity.log`:
```
YYYY-MM-DD HH:MM:SS RECOVERY: archived N session(s), skipped M
```

---

## 5. Log Collection and Viewing

### 5.1 Log Collection Script

**File:** `scripts/collect_session_logs.sh`

**Purpose:** Retrospective collection of session transcripts relevant to a specific research project. Intended to run at project completion to gather all session transcripts that touched project files.

**Usage:**
```bash
bash /daaf/scripts/collect_session_logs.sh /daaf/research/YYYY-MM-DD_Title
```

**How It Works:**

1. **Search:** Greps only orchestrator JSONL archives (`*_orchestrator.jsonl`) for the project's basename (folder name, not full path)
2. **Session-grouped collection:** For each matching session, collects ALL archives (orchestrator + subagents) by session-short ID glob. This ensures subagent transcripts are collected even if they don't individually mention the project directory.
3. **Copy:** Copies matching JSONL + MD pairs to the project's `logs/` directory
4. **Idempotent:** Skips files already present in the destination
5. **Deferred marker:** Writes a `pending_log_collection.jsonl` entry so that the current session's transcript (which hasn't been archived yet since SessionEnd hasn't fired) will be collected when the session ends

**Output Example:**
```
=== DAAF Session Log Collection ===
Project:    2026-01-24_School_Poverty_Analysis
Source:     /daaf/.claude/logs/sessions
Dest:       /daaf/research/2026-01-24_School_Poverty_Analysis/logs

Found 3 session(s) referencing this project.

--- Summary ---
Sessions matched:  3
Files copied:      8
Files skipped:     0 (already present)
Total size copied: 2 MB
Destination:       /daaf/research/2026-01-24_School_Poverty_Analysis/logs/
```

### 5.2 Log Viewer Generator

**Files:**
- `scripts/generate_log_viewer.sh` — Shell wrapper that orchestrates manifest generation and HTTP serving
- `scripts/generate_log_viewer.py` — Python CLI tool that parses JSONL transcripts into a structured JSON manifest
- `scripts/log_viewer.html` — Interactive single-page HTML/JavaScript application (1731 lines)

**Usage:**
```bash
# View logs for a specific project
bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis

# View all sessions from the DAAF-wide archive
bash /daaf/scripts/generate_log_viewer.sh --archive

# Custom port
bash /daaf/scripts/generate_log_viewer.sh /daaf/research/2026-03-29_College_Analysis --port 2720
```

#### Manifest Generation (`generate_log_viewer.py`)

The Python script:

1. **Groups JSONL files by session** using the filename pattern: `{date}_{time}_{sessionShort}_{role}.jsonl`
2. **Merges streaming chunks:** Claude Code may write multiple consecutive JSONL lines for a single assistant response (streaming). The generator merges these by message ID, deduplicating tool_use blocks, keeping the longest text block, and using the final usage/stop_reason.
3. **Extracts activities:** Parses each message's content blocks to identify tool calls, text blocks, and their targets
4. **Back-patches tool results:** Links tool_result blocks in user records back to the original tool_use blocks in assistant records
5. **Links subagents to dispatches:** Matches subagent transcripts to their orchestrator dispatch points using `toolUseResult.agentId` and `sourceToolAssistantUUID` cross-references
6. **Extracts agent frontmatter skills:** Reads agent definition files to list which skills each subagent type declares
7. **Produces `session_manifest.json`:** A structured JSON manifest consumed by the HTML viewer

**Manifest Structure:**
```json
{
  "version": 1,
  "generated": "2026-05-01T12:00:00.000Z",
  "project": {
    "name": "Project Name",
    "path": "research/2026-01-24_Analysis"
  },
  "sessions": [
    {
      "sessionId": "abcdef01",
      "fullSessionId": "abcdef01-...",
      "startTime": "2026-05-01T12:00:00Z",
      "endTime": "2026-05-01T13:00:00Z",
      "durationSec": 3600.0,
      "model": "claude-opus-4-6",
      "cliVersion": "1.0.0",
      "daafVersion": "v1.0.0-238-g764f666",
      "gitBranch": "main",
      "orchestratorFile": ".claude/logs/sessions/..._orchestrator.jsonl",
      "blocks": [
        {
          "id": "s0_b001",
          "type": "user|assistant",
          "startTime": "...",
          "endTime": "...",
          "durationSec": 5.0,
          "lineStart": 1,
          "lineEnd": 3,
          "file": "path/to/jsonl",
          "summary": "Read 3 files, Ran 2 commands",
          "activities": [
            {
              "type": "read|write|execute|delegate|skill|search|track|text",
              "tool": "Read",
              "description": "Read .claude/hooks/audit-log.sh",
              "target": ".claude/hooks/audit-log.sh",
              "line": 5,
              "resultLine": 6,
              "error": false
            }
          ],
          "tokenUsage": {
            "input": 5000,
            "output": 1000,
            "cacheRead": 3000,
            "cacheWrite": 500
          }
        }
      ],
      "subagents": [
        {
          "id": "a3f5a4a1",
          "fullId": "a3f5a4a1...",
          "agentType": "search-agent",
          "label": "Explore framework structure",
          "file": "path/to/subagent.jsonl",
          "parentBlockId": "s0_b005",
          "startTime": "...",
          "endTime": "...",
          "durationMs": 150000,
          "tokens": 50000,
          "toolUseCount": 15,
          "frontmatterSkills": ["polars", "data-scientist"],
          "invocation": {
            "promptPreview": "Full dispatch prompt text...",
            "orchestratorFile": "...",
            "orchestratorLine": 25,
            "subagentFile": "...",
            "subagentLine": 1
          },
          "report": {
            "summaryPreview": "Full final report text...",
            "orchestratorFile": "...",
            "orchestratorLine": 30,
            "subagentFile": "...",
            "subagentLine": 45
          },
          "activities": [...]
        }
      ]
    }
  ]
}
```

#### HTML Log Viewer (`scripts/log_viewer.html`)

A single-file, self-contained HTML/CSS/JavaScript application (1731 lines, no external dependencies) that provides:

**Layout:**
- **Header:** Project name, session dropdown selector
- **Stats Bar:** Session duration, model, interaction turns, subagent count, CLI version, DAAF version
- **Timeline Panel (top):** Horizontal block-based timeline showing orchestrator turns (user = blue, assistant = green) with subagent bars nested below their parent blocks (color-coded by agent type)
- **Detail Panel (bottom-left):** Detailed view of the selected block or subagent, showing activities, messages, tool calls, and subagent dispatch/report content
- **File Preview Panel (bottom-right):** File viewer with line numbers, Markdown rendering for .md files, binary file detection

**Features:**
- Multi-session support via dropdown selector
- Clickable timeline blocks with selection highlighting
- Consecutive assistant blocks without subagents are merged into compact groups
- Subagent bars color-coded by type (14 distinct colors for different agent types)
- Activity list with categorized dots (read=blue, write=orange, execute=red, delegate=purple, skill=green, search=teal)
- Clickable file references that load content in the preview panel
- Raw JSONL line viewer (click `[L23]` badges to see the raw transcript line)
- Resizable panels (horizontal and vertical drag handles)
- Markdown rendering for text content (headers, bold, code blocks, tables, lists)
- Synchronized scroll proxy for horizontal timeline overflow

**Subagent Detail View:**
When clicking a subagent bar, the detail panel shows:
- Agent type, ID, duration, tool call count
- Link to agent protocol file (`.claude/agents/{type}.md`)
- Frontmatter skills list with links to skill files
- Full dispatch prompt (scrollable)
- Full final report (scrollable)
- Complete activity timeline within the subagent

**HTTP Serving:**
The shell wrapper (`generate_log_viewer.sh`) starts a Python HTTP server (default port 2719, mapped in docker-compose.yml) from the DAAF root, serving the viewer at:
```
http://localhost:2719/scripts/log_viewer.html?manifest=path/to/session_manifest.json
```

---

## 6. Claude Code's Native Logging

### Session Transcript Storage

Claude Code stores session transcripts as JSONL files in a per-project directory hierarchy. The path is derived from the `transcript_path` field available in hook event JSON. The typical structure:

```
~/.claude/projects/{project-hash}/sessions/{session-uuid}.jsonl
~/.claude/projects/{project-hash}/sessions/{session-uuid}/subagents/agent-{agent-id}.jsonl
~/.claude/projects/{project-hash}/sessions/{session-uuid}/subagents/agent-{agent-id}.meta.json
```

### Transcript Format

Each line of the JSONL file is a JSON object representing one event in the conversation. Key record types and fields observed:

**Common fields across all records:**
- `type`: Record type (`"user"`, `"assistant"`, `"system"`, etc.)
- `timestamp`: ISO 8601 timestamp (e.g., `"2026-04-30T21:37:48.123Z"`)
- `uuid`: Unique identifier for this record
- `message`: The message payload (structure varies by type)
- `sessionId`: Session UUID
- `version`: Claude Code CLI version

**Assistant records (`type: "assistant"`):**
- `message.role`: `"assistant"`
- `message.model`: Model name (e.g., `"claude-opus-4-6"`)
- `message.content`: Array of content blocks:
  - `{type: "thinking", thinking: "...", signature: "..."}` — Extended thinking
  - `{type: "text", text: "..."}` — Text content
  - `{type: "tool_use", id: "...", name: "...", input: {...}}` — Tool invocations
- `message.usage`: Token usage breakdown:
  - `input_tokens`, `output_tokens`
  - `cache_read_input_tokens`, `cache_creation_input_tokens`
- `message.stop_reason`: Why generation stopped (e.g., `"end_turn"`, `"tool_use"`)

**User records (`type: "user"`):**
- `message.role`: `"user"`
- `message.content`: Array of content blocks:
  - `{type: "text", text: "..."}` — User message text
  - `{type: "tool_result", tool_use_id: "...", content: "...", is_error: bool}` — Tool results
- `toolUseResult`: (when present) Metadata about a completed subagent invocation:
  - `agentId`, `agentType`, `status`, `totalDurationMs`, `totalTokens`, `totalToolUseCount`, `prompt`
- `sourceToolAssistantUUID`: UUID of the assistant record that dispatched the tool
- `isMeta`: Boolean flag for metadata-only records (no user-visible content)

**System/meta records:**
- `type: "system"` — System-level events
- `type: "file-history-snapshot"` — File state snapshots
- `type: "queue-operation"` — Internal queue management

**Subagent metadata (`.meta.json`):**
```json
{
  "agentType": "search-agent"
}
```

### How DAAF Builds On Native Logging

Claude Code provides the raw JSONL transcripts. DAAF adds five layers on top:

1. **Durable archiving:** Native transcripts live in a volatile location that may be cleaned up. DAAF copies them to `.claude/logs/sessions/` in the project directory with predictable names.

2. **Human-readable rendering:** Raw JSONL is machine-readable but not human-reviewable. DAAF converts each session to Markdown with formatted messages, tool call rendering, thinking block collapsing, and token usage summaries.

3. **Crash recovery:** If a session terminates abnormally (crash, network loss, container restart), the native transcript exists but no SessionEnd hook fires. DAAF's recovery hook detects these orphans on the next session start and archives them.

4. **Structured audit log:** The per-tool JSONL audit log (`audit.jsonl`) provides a flattened, queryable index of all tool invocations across all sessions — far simpler to analyze than parsing full transcripts.

5. **Project-scoped collection:** The `collect_session_logs.sh` script enables retrospective gathering of all session transcripts relevant to a specific research project, and the HTML viewer provides an interactive browser for exploring the full conversation history.

---

## 7. Script Execution Capture (`run_with_capture.sh`)

### File: `scripts/run_with_capture.sh`

**Purpose:** Execute Python scripts with automatic output capture and inline log appending. This is the cornerstone of DAAF's "file-first execution" audit trail.

### How It Captures Output

```bash
python3 "$SCRIPT_PATH" 2>&1 | tee "$TEMP_LOG"
EXIT_CODE=${PIPESTATUS[0]}
```

1. Executes the Python script via `python3`
2. Merges stderr into stdout (`2>&1`)
3. Pipes through `tee` to simultaneously display output in the terminal AND write to a temp file
4. Captures the Python script's exit code via `PIPESTATUS[0]` (not tee's exit code)
5. Records start time and end time to compute duration (integer seconds via `date +%s`)

### How It Appends Output to the Script File

After execution, the complete output is appended to the Python script itself as commented lines:

```bash
cat >> "$SCRIPT_PATH" << EOF


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: $TIMESTAMP
# Command: python3 $SCRIPT_PATH
# Duration: ${DURATION}s
# Exit code: $EXIT_CODE
#
# --- STDOUT ---
$(sed 's/^/# /' "$TEMP_LOG")
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
EOF
```

The `sed 's/^/# /'` command prefixes every line of output with `# ` so it becomes a Python comment. This means the Python file remains valid Python after the log is appended — it just has a large comment block at the end.

### Re-Run Protection

Before executing, the script checks:
```bash
if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "WARNING: Script already has an execution log."
    # ... prints guidance to create a versioned copy
    exit 1
fi
```

This enforces immutability: once a script has been executed and has its log appended, it cannot be re-run. The user must create a versioned copy (`_a.py`, `_b.py`, etc.) for fixes.

### The Immutable Audit Artifact Pattern

This creates a single file that is simultaneously:
- **The source code** that was executed
- **The complete output** of that execution
- **The execution metadata** (timestamp, duration, exit code)

After execution, the script file becomes a self-contained, immutable audit artifact. Anyone can read the file top-to-bottom and see exactly what code ran and exactly what it produced. This pattern is fundamental to DAAF's reproducibility guarantees.

### Versioning on Failure

If the script fails:
1. The original file (with its failed output) is preserved as-is
2. A new versioned copy is created: `01_task.py` → `01_task_a.py`
3. Fixes are applied only to the new copy
4. The new copy is executed through `run_with_capture.sh`, getting its own execution log
5. All versions are committed to git for complete traceability

Example progression:
```
01_join-ccd-meps.py       # v1: FAILED (key mismatch) - output shows 0 rows
01_join-ccd-meps_a.py     # v2: FAILED (type error) - output shows cast error
01_join-ccd-meps_b.py     # v3: PASSED - output shows CP3 PASSED
```

---

## 8. Audit Trail Philosophy: How It All Works Together

DAAF's audit trail is built on four interlocking principles:

### 8.1 File-First Execution

**Every operation is a script.** Claude never executes Python interactively. Every data transformation, analysis, and visualization is written as a `.py` file first, then executed through `run_with_capture.sh`. This ensures:

- There is always a permanent record of what code was executed
- The output is captured alongside the code
- No "ephemeral" computation can happen without a trace

The `enforce-file-first.sh` PreToolUse hook enforces this for coding agents (research-executor, code-reviewer, debugger, data-ingest) by blocking any direct `python` or `python3` invocations in Bash commands. The hook uses a sophisticated regex to detect Python interpreter calls in various forms (bare, versioned, absolute path, env-prefixed, exec-wrapped) while allowing legitimate uses (package management via pip, framework utility scripts, marimo runtime). Framework utility scripts in `/daaf/scripts/` are whitelisted since they are standalone CLI tools, not pipeline scripts.

### 8.2 Immutable Script Versioning

**Never modify a script after its execution log is appended.** Once `run_with_capture.sh` has appended output to a script, that file becomes a historical record. Any fixes go into a new versioned copy (`_a.py`, `_b.py`, etc.). Both failed and successful versions are preserved and committed.

This gives reviewers a complete record of:
- What was attempted (the code)
- What happened (the output)
- What was tried next (the version history)
- What ultimately succeeded (the final version)

### 8.3 Inline Audit Trail (IAT) Comments

**Every transformation is documented in the code itself.** DAAF mandates five types of inline comments in all Python scripts:

| Type | Prefix | Purpose |
|------|--------|---------|
| Section Preamble | Block comment above `# --- Section ---` | Orients the reader to each section |
| Intent Comment | `# INTENT:` | What a code block does and why it exists |
| Reasoning Comment | `# REASONING:` | Why this approach was chosen over alternatives |
| Assumption Comment | `# ASSUMES:` | What data properties the code depends on |
| Inline Annotation | End-of-line `#` | Non-obvious single operations |

The philosophy: "Code tells you HOW. Comments tell you WHY, WHAT FOR, and WHAT'S ASSUMED."

This ensures that a human reviewer can follow every decision by reading the source alone, without needing to re-derive intent from the code.

### 8.4 Multi-Layer Observability Stack

The four subsystems work together to provide complete observability at different granularities:

| Layer | Granularity | What It Captures |
|-------|-------------|-----------------|
| **Audit log** (`audit.jsonl`) | Per-tool-call | Flat index of every tool invocation across all sessions — who, when, what |
| **Session transcripts** (`.claude/logs/sessions/`) | Per-session | Complete conversation including messages, thinking, tool calls, and results |
| **Session Markdown** (`*_orchestrator.md`) | Per-session (human-readable) | Rendered version of the transcript for human review |
| **Script execution logs** (appended to `.py` files) | Per-script | Code + complete output + metadata as a single self-contained artifact |
| **Activity log** (`activity.log`) | Per-session (summary) | One-line session start records and recovery events |

### How These Interact for a Typical Pipeline Run

1. **Session starts** → `recover-session-logs.sh` logs to `activity.log`, recovers any orphaned sessions
2. **Every tool call** → `audit-log.sh` appends to `audit.jsonl`, `output-scanner.sh` checks for secrets
3. **Script execution** → `run_with_capture.sh` creates immutable script+output artifacts
4. **Session ends** → `archive-session.sh` copies and converts the full transcript
5. **Project completion** → `collect_session_logs.sh` gathers all relevant transcripts
6. **Review** → `generate_log_viewer.sh` creates an interactive HTML viewer

### Permissions and Protection

The system is protected by multiple layers:

1. **Deny rules in `settings.json`:** Prevent editing/writing to `.claude/logs/*` and `.claude/hooks/*`
2. **Append-only log design:** Audit log uses `>>` (append), not `>` (overwrite)
3. **Re-run protection:** `run_with_capture.sh` refuses to re-execute a script that already has a log
4. **Immutable versioning:** Framework convention prohibits modifying executed scripts
5. **Git tracking:** All script versions (failed and successful) are committed

---

## 9. Context Monitoring (Supplementary)

### File: `.claude/hooks/context-reporter.sh`

**Hook Types:** UserPromptSubmit (empty matcher), PreToolUse (empty matcher)
**Purpose:** Inject context window utilization into the conversation

While not strictly part of the audit trail, this hook is part of the observability system. It:

1. Reads the latest token usage from the session transcript (last 50 lines for performance)
2. Computes utilization percentage against the max context window
3. Applies dual-trigger thresholds (percentage OR absolute token count):
   - NOMINAL: < 40% AND < 150k tokens
   - ELEVATED: >= 40% OR >= 150k tokens
   - HIGH: >= 60% OR >= 200k tokens
   - CRITICAL: >= 75% OR >= 250k tokens
4. Rate-limits injections to once per 60 seconds (shared gate across events)
5. Formats the message differently per event:
   - UserPromptSubmit: Plain text stdout
   - PreToolUse: JSON `additionalContext` field

The hook also caches the model name (from the transcript) to `/tmp/claude-model-{SESSION_ID}`, which `audit-log.sh` reads to include the model in audit entries.

**Context window size** is read from a cache file written by `context-bar.sh` (the status line script). For subagents (different session ID), it falls back to the most recent cache from any session.

---

## 10. Hook Registration Map

Complete mapping of all hooks registered in `.claude/settings.json`:

### SessionStart
| Hook | Script | Timeout | Purpose |
|------|--------|---------|---------|
| `""` (all) | `recover-session-logs.sh` | 5s | Activity logging + crash recovery |

### UserPromptSubmit
| Hook | Script | Timeout | Purpose |
|------|--------|---------|---------|
| `""` (all) | `context-reporter.sh` | 5s | Context utilization injection |
| `""` (all) | `remind-orchestrator.sh` | 5s | Remind user to load orchestrator skill |

### PreToolUse
| Hook | Script | Timeout | Purpose |
|------|--------|---------|---------|
| `""` (all) | `context-reporter.sh` | 5s | Context utilization injection |
| `"Task"` | `enforce-explore-model.sh` | 5s | Enforce model selection for agents |
| `"Task"` | `enforce-foreground-agents.sh` | 5s | Block background agent execution |
| `"Task"` | `deny-claude-code-guide.sh` | 5s | Block Claude Code guide tool |
| `"Agent"` | `enforce-explore-model.sh` | 5s | Enforce model selection for agents |
| `"Agent"` | `enforce-foreground-agents.sh` | 5s | Block background agent execution |
| `"Agent"` | `deny-claude-code-guide.sh` | 5s | Block Claude Code guide tool |
| `"Bash"` | `bash-safety.sh` | 5s | Destructive command prevention |

Note: `enforce-file-first.sh` is registered in individual agent frontmatter (research-executor, code-reviewer, debugger, data-ingest), NOT in the project-wide settings.json. This means it only fires for those specific agent types, not for the orchestrator or read-only agents.

### PostToolUse
| Hook | Script | Timeout | Purpose |
|------|--------|---------|---------|
| `""` (all) | `audit-log.sh` | 5s | Append-only audit log |
| `""` (all) | `output-scanner.sh` | 5s | Secret detection in output |
| `"Skill"` | `flag-orchestrator-loaded.sh` | 5s | Track orchestrator skill loading |

### SessionEnd
| Hook | Script | Timeout | Purpose |
|------|--------|---------|---------|
| `""` (all) | `archive-session.sh` | 60s | Full session archival |

---

## 11. File System Layout Summary

```
/daaf/
├── .claude/
│   ├── hooks/
│   │   ├── archive-session.sh          # SessionEnd: full session archival
│   │   ├── audit-log.sh                # PostToolUse: append-only audit log
│   │   ├── bash-safety.sh              # PreToolUse(Bash): destructive command prevention
│   │   ├── context-reporter.sh         # PreToolUse + UserPromptSubmit: utilization monitoring
│   │   ├── deny-claude-code-guide.sh   # PreToolUse(Task/Agent): block guide tool
│   │   ├── enforce-explore-model.sh    # PreToolUse(Task/Agent): model enforcement
│   │   ├── enforce-file-first.sh       # PreToolUse(Bash): agent-scoped file-first enforcement
│   │   ├── enforce-foreground-agents.sh # PreToolUse(Task/Agent): block background agents
│   │   ├── flag-orchestrator-loaded.sh # PostToolUse(Skill): track skill loading
│   │   ├── output-scanner.sh           # PostToolUse: secret detection
│   │   ├── recover-session-logs.sh     # SessionStart: crash recovery
│   │   └── remind-orchestrator.sh      # UserPromptSubmit: orchestrator reminder
│   ├── logs/
│   │   ├── .gitkeep
│   │   ├── .last_recovery              # Timestamp file for recovery gating
│   │   ├── activity.log                # One-line session start records
│   │   ├── audit.jsonl                 # Append-only tool invocation log
│   │   ├── pending_log_collection.jsonl # Deferred collection markers (transient)
│   │   └── sessions/                   # Archived session transcripts
│   │       ├── {date}_{time}_{short}_orchestrator.jsonl
│   │       ├── {date}_{time}_{short}_orchestrator.md
│   │       ├── {date}_{time}_{short}_subagent_{id}.jsonl
│   │       └── {date}_{time}_{short}_subagent_{id}.md
│   ├── scripts/
│   │   └── context-bar.sh             # Status line script (writes context window cache)
│   └── settings.json                  # Hook registration, permissions, env vars
├── scripts/
│   ├── run_with_capture.sh            # Script execution wrapper
│   ├── collect_session_logs.sh        # Project-scoped log collection
│   ├── generate_log_viewer.sh         # Log viewer generator + HTTP server
│   ├── generate_log_viewer.py         # JSONL→manifest converter
│   └── log_viewer.html               # Interactive HTML session viewer
└── research/{project}/
    ├── logs/                          # Project-specific collected session logs
    │   ├── {date}_{time}_{short}_orchestrator.jsonl
    │   ├── {date}_{time}_{short}_orchestrator.md
    │   └── session_manifest.json      # Viewer manifest
    └── scripts/
        └── stage{N}_{type}/
            ├── 01_task.py             # Script with appended execution log
            ├── 01_task_a.py           # Versioned revision with its own log
            └── 01_task_b.py           # Further revision
```

---

## 12. Migration Considerations

For porting DAAF's logging and audit trail to another AI coding harness:

### Must-Have Capabilities
1. **PostToolUse hook equivalent** — Ability to run code after every tool invocation (for audit logging and output scanning)
2. **SessionStart/SessionEnd hooks** — Lifecycle events for session archival and crash recovery
3. **Access to session transcript** — Ability to read the raw conversation transcript for archiving
4. **Stdin JSON payload in hooks** — Hook scripts need structured context (session ID, tool name, tool input, transcript path)
5. **Exit code semantics** — Distinguish between "allow" (0), "block" (2), and "advisory output" (stdout injection)

### Important Design Patterns to Preserve
1. **Append-only logging** — Audit log must be append-only with protection against overwriting
2. **Fail-open for observability hooks** — Archival and logging must never block the session
3. **Fail-closed for enforcement hooks** — `enforce-file-first.sh` and `bash-safety.sh` must block on error
4. **Background recovery** — Crash recovery must not delay session startup
5. **Idempotent archiving** — Multiple archive attempts for the same session must be safe
6. **Script-as-artifact pattern** — The inline execution log pattern is framework-level, not harness-level, but the enforcement hook needs harness support

### Harness-Specific Dependencies
- Claude Code's `agent_type` and `agent_id` fields in hook JSON (for subagent attribution in audit log)
- Claude Code's transcript directory structure (`{session}/subagents/agent-{id}.jsonl`)
- Claude Code's `.meta.json` sidecar files for agent metadata
- Claude Code's `toolUseResult` record type for subagent return metadata
- Claude Code's streaming chunk pattern (multiple JSONL lines per assistant response)
