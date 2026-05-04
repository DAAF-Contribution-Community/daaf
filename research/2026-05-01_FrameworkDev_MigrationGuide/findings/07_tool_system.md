# Tool System — DAAF Migration Findings

**Researcher:** search-agent
**Date:** 2026-05-01
**Scope:** Complete inventory, calling conventions, deferred tools, MCP, agent restrictions, DAAF-specific patterns
**Key Sources:** `.claude/settings.json`, `.claude/agents/*.md`, `CLAUDE.md`, `agent_reference/BOUNDARIES.md`, `agent_reference/SCRIPT_EXECUTION_REFERENCE.md`, `.claude/hooks/*.sh`, session log files

---

## 1. Built-in Tools Inventory

Claude Code provides a fixed set of tools to the model. DAAF uses the following, organized by category:

### 1.1 File Operation Tools

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **Read** | Read files from the filesystem | `file_path` (string, required), `offset` (int, optional), `limit` (int, optional), `pages` (string, optional for PDFs) | Can read text, images (multimodal), PDFs, Jupyter notebooks. Returns content with `cat -n` style line numbers. Default: up to 2000 lines from start. |
| **Write** | Create or overwrite files | `file_path` (string, required), `content` (string, required) | Creates parent directories as needed. Overwrites existing files entirely. |
| **Edit** | Make targeted edits to existing files | `file_path` (string, required), plus edit specification (old_string/new_string pairs) | Surgical edits without rewriting the entire file. Preferred over Write for modifications. |
| **NotebookEdit** | Edit Jupyter notebook cells | (Cell-level editing parameters) | Used for `.ipynb` files. DAAF does not use Jupyter notebooks (uses Marimo `.py` format) but the tool exists in the environment. Appears in `scripts/generate_log_viewer.py` (line 51) as a "write" category tool. |

### 1.2 Search Tools

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **Glob** | Find files by name pattern | `pattern` (string, required), `path` (string, optional) | Supports standard glob patterns (`**/*.py`, `src/**/*.ts`). Returns file paths sorted by modification time. |
| **Grep** | Search file contents by regex | `pattern` (string, required), `path` (string, optional), `output_mode` (enum: `"content"`, `"files_with_matches"`, `"count"`), `glob` (string, optional), `type` (string, optional), `-A`/`-B`/`-C`/`-n` (context options), `head_limit` (int), `offset` (int), `multiline` (bool), `-i` (bool) | Built on ripgrep. Default output mode is `files_with_matches`. Default `head_limit` is 250. |

### 1.3 Command Execution

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **Bash** | Execute shell commands | `command` (string, required), `description` (string, optional), `timeout` (number, optional, ms, max 600000), `run_in_background` (bool, optional), `dangerouslyDisableSandbox` (bool, optional) | Executes in a persistent working directory. Shell state does NOT persist between calls. Default timeout: 120000ms (2 min). |

### 1.4 Web Access Tools

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **WebSearch** | Search the web | `query` (string, required, min 2 chars), `allowed_domains` (string array, optional), `blocked_domains` (string array, optional) | Returns search results with links. Only available in the US. |
| **WebFetch** | Fetch and analyze a URL | `url` (string, required, URI format), `prompt` (string, required) | Fetches URL, converts HTML to markdown, processes with a small model. 15-minute cache. Auto-upgrades HTTP to HTTPS. |

### 1.5 Subagent/Task Management Tools

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **Agent** | Dispatch a foreground subagent | `prompt` (string), `description` (string), `subagent_type` (string) | Spawns a new model context with its own tool access. Blocks until complete. Can specify named agent type. |
| **Task** | Variant of Agent | Same as Agent | Both `Agent(...)` and `Task(...)` permission entries exist in settings.json. |
| **TaskCreate** | Create a trackable task | `subject` (string), `description` (string), `activeForm` (string) | Creates a task entry for tracking progress. Observed in RV mode session logs. |
| **TaskUpdate** | Update task status | (task ID and status fields) | Updates existing task progress. |
| **TaskGet** | Get task details | (task ID) | Retrieve task information. |
| **TaskList** | List all tasks | (filter parameters) | List tasks. |
| **TaskOutput** | Get task output | (task ID) | Retrieve completed task output. |
| **TaskStop** | Stop a running task | (task ID) | Cancel a task. |

**Note:** DAAF explicitly disables background tasks (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in `settings.json`) and enforces foreground-only agents via the `enforce-foreground-agents.sh` hook. TaskCreate/TaskUpdate are still used for progress tracking, not background execution.

### 1.6 Knowledge/Skill Tools

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **Skill** | Load a skill (slash command) | `skill` (string, required), `args` (string, optional) | Loads a `.claude/skills/*/SKILL.md` file into context. Skills provide domain knowledge. Available skills list is injected via system-reminder messages. |

### 1.7 Deferred/ToolSearch Tools

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| **ToolSearch** | Search for and load deferred tool schemas | `query` (string), `max_results` (int) | Used to discover tools not loaded by default. Observed in session logs: `{"query":"select:TaskCreate,TaskUpdate","max_results":2}`. |

---

## 2. Tool Calling Conventions

### 2.1 XML-Based Function Call Syntax

Claude Code uses XML blocks for tool invocations. The model emits `function_calls` blocks containing `invoke` elements with `parameter` sub-elements. Each parameter has a `name` attribute and text content. Tool results come back in `function_results` blocks containing `result` elements with `name` and `output` sub-elements.

### 2.2 Parameter Passing

- **String parameters:** Passed as-is (text content directly inside parameter tags)
- **Complex types (arrays, objects):** Passed as JSON. The system prompt states: "When making function calls using tools that accept array or object parameters ensure those are structured using JSON."
- **Optional parameters:** Omitted entirely (not set to "undefined" or "null") — the system prompt warns against entering these values

### 2.3 Parallel Tool Calls

Multiple tool invocations can be made in a single model response by including multiple `invoke` blocks within one `function_calls` block:

- System prompt: "You can call multiple tools in a single response."
- DAAF uses this for wave-based parallel dispatch: "Same-wave tasks dispatch simultaneously by making multiple Agent tool calls in a single response message (foreground parallel)." (`full-pipeline-mode.md` line 849)
- Maximum 5 parallel Agent dispatches in DAAF (hard limit, enforced by convention)

### 2.4 Tool Result Presentation

Tool results returned in `function_results` blocks. Multiple results appear when multiple tools were called in parallel.

### 2.5 Error Handling

- Tool errors appear in the result output (e.g., file not found, command failure)
- Bash returns stdout/stderr and exit code
- Hook-blocked commands return an error message (exit code 2 from PreToolUse hooks)
- Permission denials produce tool_use_error messages

---

## 3. Deferred Tools / ToolSearch System

### 3.1 How Deferred Tools Work

Not all tools are loaded into the model's context by default. Some tools are "deferred" — their schemas are not in the initial system prompt. This conserves context tokens. When needed, the model uses **ToolSearch** to discover and load the tool's schema.

**Observed ToolSearch usage** (session log line 1121):
```json
{"query":"select:TaskCreate,TaskUpdate","max_results":2}
```

### 3.2 Which Tools Appear to Be Deferred

Based on session log analysis:
- **TaskCreate, TaskUpdate, TaskGet, TaskList, TaskOutput, TaskStop** — Task management tools require ToolSearch
- **NotebookEdit** — Exists but not commonly loaded

### 3.3 Which Tools Are Always Loaded

Core tools always available without ToolSearch:
- Read, Write, Edit, Bash, Glob, Grep, Agent, Skill, WebSearch, WebFetch

### 3.4 Why Tools Are Deferred

Context conservation. Each tool schema consumes tokens. Deferring rarely-used tools keeps the base context smaller.

### 3.5 DAAF's Use of Deferred Tools

DAAF uses Task management tools (TaskCreate, TaskUpdate) for progress tracking in Reproducibility Verification mode. The only observed ToolSearch usage in DAAF session logs.

---

## 4. Tool Restrictions Per Agent

### 4.1 The `tools` Field in Agent Frontmatter

Each agent definition has a YAML frontmatter `tools` field declaring an explicit allowlist. Claude Code restricts the agent's tool access accordingly.

**Complete Agent Tool Matrix:**

| Agent | tools | permissionMode | hooks | Skills Preloaded |
|-------|-------|----------------|-------|-----------------|
| **research-executor** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | enforce-file-first (Bash) | data-scientist |
| **code-reviewer** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | enforce-file-first (Bash) | data-scientist |
| **data-planner** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | — | data-scientist |
| **plan-checker** | Read, Bash, Glob, Grep, Skill | plan | — | data-scientist |
| **data-verifier** | Read, Bash, Glob, Grep, Skill | plan | — | data-scientist |
| **source-researcher** | Read, Bash, Glob, Grep, Skill | plan | — | data-scientist |
| **research-synthesizer** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | — | data-scientist |
| **debugger** | Read, Write, Edit, Bash, Glob, Grep, Skill, WebFetch, WebSearch | default | enforce-file-first (Bash) | data-scientist |
| **notebook-assembler** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | — | data-scientist, marimo |
| **integration-checker** | Read, Bash, Glob, Grep, Skill | plan | — | data-scientist |
| **data-ingest** | Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill | default | enforce-file-first (Bash) | data-scientist |
| **framework-engineer** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | — | skill-authoring, agent-authoring |
| **report-writer** | Read, Write, Edit, Bash, Glob, Grep, Skill | default | — | data-scientist |
| **search-agent** | Read, Bash, Glob, Grep, Skill, WebSearch, WebFetch | plan | — | (none preloaded) |

### 4.2 Tool Access Patterns

Three distinct profiles:

**Read-Only Agents** (`permissionMode: plan`): plan-checker, data-verifier, source-researcher, integration-checker, search-agent. Cannot use Write or Edit.

**Read-Write Agents** (`permissionMode: default`): research-executor, code-reviewer, data-planner, research-synthesizer, debugger, notebook-assembler, data-ingest, framework-engineer, report-writer. Full Write and Edit access.

**Web-Enabled Agents**: Only debugger, data-ingest, search-agent have WebSearch + WebFetch.

### 4.3 How Tool Restrictions Are Enforced

1. **Frontmatter `tools` field:** Claude Code only makes listed tools available. Error on unlisted tool: "No such tool available: Write. Write exists but is not enabled in this context."
2. **Frontmatter `permissionMode`:** `default` = normal; `plan` = read-only (Write/Edit unavailable).

From CHANGELOG.md: "Claude Code automatically loads the agent's protocol file and applies its `tools` and `permissionMode` settings."

### 4.4 The `model` Field

`search-agent` has `model: inherit` — runs on the same model as orchestrator (Opus), not the default cheaper model. Significant because Explore defaults to Haiku.

### 4.5 The `skills` Field

Auto-loaded skills: most agents preload `data-scientist`. Exceptions: notebook-assembler adds `marimo`, framework-engineer preloads `skill-authoring` + `agent-authoring`.

---

## 5. MCP (Model Context Protocol)

### 5.1 Does DAAF Use MCP Servers?

**No.** No MCP server configuration exists. No `.mcp.json` found.

### 5.2 MCP References

Only reference: `agent_reference/BOUNDARIES.md` line 144 prohibits `mcp__ide__executeCode` (IDE integration tool) as it bypasses file-first audit trail.

### 5.3 How MCP Would Be Configured

Create `.mcp.json`, tools appear as `mcp__server__toolname`, add to settings.json and agent frontmatter.

---

## 6. DAAF-Specific Tool Usage Patterns

### 6.1 One Command Per Bash Call

Every Bash call = exactly ONE command. No `&&`, `;`, `||`. Source: `CLAUDE.md`. Reason: each call independently evaluated by bash-safety hook and permissions.

### 6.2 File-First Execution Pattern

1. WRITE script via Write tool
2. EXECUTE via `bash {BASE_DIR}/scripts/run_with_capture.sh {script_path}`
3. CAPTURE automatic (stdout/stderr appended to script file)

**Enforcement via `enforce-file-first.sh`:** PreToolUse hook on Bash matcher, registered in agent frontmatter for code-producing agents only (research-executor, code-reviewer, debugger, data-ingest). Blocks python/python3 invocations. Exit code 2 = BLOCK. Whitelists framework utilities in `/daaf/scripts/`.

### 6.3 Interactive Python Prohibition

Three enforcement layers: enforce-file-first hook, BOUNDARIES.md mcp prohibition, convention in CLAUDE.md.

### 6.4 Read-Only Agent Restrictions

`permissionMode: plan` agents cannot Write or Edit. Tools not available in context.

### 6.5 Web Access Restrictions

Only 3 of 14 agents have web access. Design choice: prioritize curated skills over web searches.

---

## 7. Permission System (settings.json)

### 7.1 Allow List

Auto-approved: specific Bash commands (marimo, pip, python, bash, ls, mkdir, git, cp, chmod, cd, head, wc, file, find), Grep, Glob, Edit, Write, Skill, WebSearch, and Agent/Task for generic types (general-purpose, Plan, Explore, search-agent).

**Key:** Named DAAF agents NOT auto-allowed (require user confirmation). WebFetch NOT auto-allowed. Read presumably always allowed by default.

### 7.2 Deny List

Blocked: destructive shell commands (rm -rf, sudo, docker, mount, chroot), destructive git (force push, hard reset, clean, checkout/restore ., branch -D), credential files (.env, .pem, .key, credentials, secrets), hook/log files.

### 7.3 Pattern Syntax

`ToolName(pattern)`: `*` = glob wildcard, `**` = directory separator crossing. Matches command string (Bash), file path (Read/Write/Edit), or subagent_type (Agent/Task).

---

## 8. Hook System as Tool-Adjacent Feature

### 8.1 Five Hook Events

UserPromptSubmit, PreToolUse, PostToolUse, SessionStart, SessionEnd.

### 8.2 PreToolUse Gatekeeping

Project-wide: `context-reporter.sh` (all tools). Bash-specific: `bash-safety.sh` (project-wide), `enforce-file-first.sh` (agent-specific). Agent/Task-specific: `enforce-explore-model.sh`, `enforce-foreground-agents.sh`, `deny-claude-code-guide.sh`.

### 8.3 Hook I/O Protocol

Input: JSON on stdin with tool_name and tool_input. Output: exit 0 (allow), exit 2 (block with stderr message), or JSON with permissionDecision deny.

### 8.4 PostToolUse

`audit-log.sh` (all tools), `output-scanner.sh` (all tools), `flag-orchestrator-loaded.sh` (Skill matcher).

---

## 9. Skill Tool — Domain Knowledge Loading

### 9.1 Mechanism

Available skills list injected as system-reminder. Skill tool loads SKILL.md into context on demand. Content persists for session.

### 9.2 Two Loading Paths

Frontmatter `skills` field (auto-load at start) vs. runtime Skill tool call (conditional loading).

### 9.3 Ecosystem

50+ skills: data sources, tool/library references, methodology, framework, translation.

---

## 10. Agent/Task Tool — Subagent Dispatch

### 10.1 Parameters

`description`, `prompt`, `subagent_type` (maps to agent `name` in frontmatter).

### 10.2 Type Resolution

Named agents: file loaded, tools/permissions/skills/hooks applied. Generic: general-purpose, Plan, Explore (blocked).

### 10.3 Blocked Built-in Types

Explore (Haiku, insufficient reasoning) and claude-code-guide (Haiku, opaque prompt). Both replaced by search-agent.

### 10.4 Foreground Only

`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` + `enforce-foreground-agents.sh`. Parallel = multiple Agent calls in one response.

---

## 11. Environment Configuration

Model: Opus 4.6 (1M context). Effort: high. Auto-memory disabled. Background tasks disabled. Prompt caching: 1 hour. Status line: custom context-bar.sh.

---

## 12. Tool-Adjacent Features

Slash commands = Skill tool. Context reporter injects utilization data. Output style: Explanatory. Thinking summaries: enabled.

---

## 13. Migration Implications

### 13.1 Core Requirements

File ops, command execution, file search, web access, subagent dispatch, knowledge injection, tool discovery (nice-to-have), task tracking (used sparingly).

### 13.2 Patterns to Replicate

| Pattern | Complexity |
|---------|------------|
| One command per Bash call | LOW |
| File-first execution | MEDIUM |
| Tool restrictions per agent | HIGH |
| Permission modes | HIGH |
| PreToolUse hooks | HIGH |
| PostToolUse audit | MEDIUM |
| Parallel dispatch | MEDIUM |
| Background blocking | LOW |
| Skill auto-loading | MEDIUM |
| Permission allow/deny | MEDIUM |

### 13.3 Claude Code Specific

XML tool syntax, system-reminder injection, deferred tools (ToolSearch), hook lifecycle events, agent frontmatter YAML.

---

## Confidence Assessment

**Overall Confidence:** HIGH

| Aspect | Confidence | Rationale |
|--------|------------|-----------|
| Tool inventory | HIGH | Cross-referenced system prompt, settings.json, agent frontmatter, session logs, log viewer |
| Calling conventions | HIGH | Directly observable from system prompt and tool definitions |
| Deferred tools | MEDIUM | Based on session log analysis; could not test directly |
| Agent restrictions | HIGH | Complete inventory from all 14 agent files; enforcement confirmed |
| MCP | HIGH | Comprehensive search; no configuration found |
| DAAF patterns | HIGH | From CLAUDE.md, BOUNDARIES.md, SCRIPT_EXECUTION_REFERENCE.md, hooks |
| Migration implications | MEDIUM | Depends on target platform |

## Gaps and Limitations

- ToolSearch internals not fully documented; understanding from session logs
- Task tool parameter schemas incomplete; observed but not formally documented
- Config tool mentioned in update-config skill but not observed in DAAF usage
- Permission evaluation order (allow vs deny precedence) not documented
- Whether orchestrator can dynamically add named agents to allow list unknown
