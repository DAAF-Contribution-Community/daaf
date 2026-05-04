# External AI Coding Harness Feature Survey

**Date:** 2026-05-01
**Purpose:** Awareness survey of alternative AI coding harness feature sets relative to DAAF's Claude Code architecture. This is NOT a migration plan -- it documents what exists in the landscape so that DAAF maintainers understand which features would have direct equivalents vs. what would require reimplementation.

**Research Method:** Web search of official documentation and developer community resources (April-May 2026). Confidence levels noted where documentation was sparse.

---

## Table of Contents

1. [ChatGPT Codex (OpenAI)](#1-chatgpt-codex-openai)
2. [OpenCode (Open-Source CLI)](#2-opencode-open-source-cli)
3. [Cursor (AI IDE)](#3-cursor-ai-ide)
4. [Aider (Open-Source CLI)](#4-aider-open-source-cli)
5. [Windsurf / Codeium (AI IDE)](#5-windsurf--codeium-ai-ide)
6. [Cross-Harness Comparison Matrix](#6-cross-harness-comparison-matrix)
7. [Sources](#7-sources)

---

## 1. ChatGPT Codex (OpenAI)

### Description

Codex is OpenAI's full-featured coding agent platform, available via CLI, web app, and desktop app (Windows and macOS as of March 2026). Originally launched in April 2025 with the codex-1 model (an o3 variant), it has evolved into a multi-agent development platform powered by the GPT-5 family. Available on ChatGPT Plus, Pro, Business, Edu, and Enterprise plans. Over one million developers have used Codex as of early 2026.

### Feature Comparison vs. Claude Code

| DAAF Feature | Claude Code | Codex CLI | Notes |
|---|---|---|---|
| **Custom instructions file** | `CLAUDE.md` (hierarchical, per-directory) | `AGENTS.md` (hierarchical, per-directory + global) | Very close equivalent. Codex reads AGENTS.md from multiple locations with directory-proximity precedence. Supports `project_doc_max_bytes` to control how much is loaded. Also reads fallback filenames when AGENTS.md is missing. |
| **Agent/subagent system** | Agent dispatch via `Agent` tool with named agents | Named custom agents via config files + subagent spawning | Strong equivalent. Each agent file defines one custom agent with overridable settings (model, sandbox, MCP, skills). Subagents spawn explicitly on request. `agents.max_depth` controls nesting (default 1). `/agent` command switches between active threads. |
| **Hooks/event callbacks** | `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd` in `settings.json` | `PreToolUse`, `PermissionRequest`, `PostToolUse`, `UserPromptSubmit`, `Stop` | Very close equivalent. Hooks are stable, configurable inline in `config.toml` or via `hooks.json`. Can observe MCP tools, `apply_patch`, and Bash sessions. Matcher field (regex) filters when hooks fire. Multiple hooks run concurrently. Enterprise managed hooks supported. |
| **Tool system** | File read/write, Bash, Grep, Glob, WebSearch, WebFetch, Agent, MCP | File read/write, Bash, apply_patch, MCP tools, web search | Comparable. MCP provides extensibility. Tool ecosystem growing via plugins. |
| **Permission system** | Allow/deny lists in `settings.json`, user approval prompts | Three modes: Auto (workspace scoped), Read-only, Full Access. Permission profiles (`:read-only`, `:workspace`, `:danger-no-sandbox`). Sandbox options. Trust/untrust for projects. Enterprise `requirements.toml` enforcement. | Codex has a more structured permission model with built-in profiles and sandbox modes. Claude Code's allow/deny pattern lists are more granular at the individual command level. |
| **Context management** | Context window with compaction, `context-reporter` hook | Context window with skill progressive disclosure (2% budget for skill list). Skills loaded on demand. Subagent isolation. | Both manage context actively. Codex's skill loading budget system is more formalized. Both use subagent context isolation. |
| **Session persistence** | `STATE.md` (manual), session transcripts | Persisted `/goal` workflows with pause/resume/clear. Session resume from interruption. Feature flags persisted in config. | Codex has stronger built-in session persistence with pause/resume. DAAF's STATE.md approach is manual but more flexible for research workflows. |
| **Skill/knowledge system** | `SKILL.md` files with progressive disclosure, loaded on demand | `SKILL.md` files in `~/.agents/skills/`. Progressive disclosure (name+description first, full load on use). 2% context budget cap. | Nearly identical design. Both use SKILL.md format. This is now an open standard (`agentskills.io`) adopted across platforms. |
| **Model selection** | Fixed to Claude family; model specified per-agent in frontmatter | GPT-5 family (gpt-5.5, gpt-5.4-mini, gpt-5.3-codex-spark). Per-agent model override in config. | Per-agent model selection available in both. Codex limited to OpenAI models. |
| **MCP support** | Yes, via `settings.json` MCP server configuration | Yes, with plugin-bundled MCP and auto-install via `agents/openai.yaml` | Both support MCP. Codex adds auto-wiring MCP dependencies declared in skills. |
| **Logging/transcripts** | Audit log hook (`audit-log.sh`), session archive hook | Session transcripts surfaced in app/CLI. Subagent activity visible via `/agent`. | Both provide audit trails. DAAF's hook-based approach is more customizable. |

### Notable Gaps and Advantages

**Advantages over Claude Code for DAAF-like use:**
- Built-in pause/resume for long-running goals -- no manual STATE.md needed
- Enterprise-managed hooks and requirements via `requirements.toml` -- centralized policy enforcement
- Desktop app with parallel agent management UI
- Trust/untrust project model for security

**Gaps relative to DAAF's needs:**
- Locked to OpenAI models only -- no model diversity
- Permission model is coarser (workspace-level modes vs. per-command allow/deny patterns)
- No equivalent of DAAF's `run_with_capture.sh` file-first execution audit trail (would need custom hooks)
- Subagent `max_depth` default of 1 limits deep orchestration patterns DAAF uses

### Key Migration Concerns

- DAAF's `CLAUDE.md` would map directly to `AGENTS.md` with minimal restructuring
- DAAF's `SKILL.md` files would transfer with no changes (same open standard)
- Hook events are nearly 1:1 but hook configuration syntax differs (`settings.json` vs. `config.toml`/`hooks.json`)
- The permission system would need rethinking -- DAAF's per-command deny patterns don't map cleanly to Codex's profile-based model
- Agent definitions would need conversion from DAAF's markdown frontmatter format to Codex's TOML/YAML config format
- `run_with_capture.sh` file-first execution pattern would need reimplementation as a custom hook

---

## 2. OpenCode (Open-Source CLI)

### Description

OpenCode is an open-source (Go-based) terminal AI coding agent with 110K+ GitHub stars. Its defining feature is provider freedom -- it supports 75+ LLM backends including OpenAI, Anthropic, Google, AWS Bedrock, Ollama (local), and more. It uses a client/server architecture and features a rich Terminal UI built with Bubble Tea. GitHub Copilot subscribers can authenticate directly since January 2026.

### Feature Comparison vs. Claude Code

| DAAF Feature | Claude Code | OpenCode | Notes |
|---|---|---|---|
| **Custom instructions file** | `CLAUDE.md` | `AGENTS.md` + config `instructions` option (array of file paths/globs) | Equivalent. Also supports community `opencode-rules` plugin for glob-matched, conditional rule injection with YAML frontmatter metadata. |
| **Agent/subagent system** | Named agents with dedicated definitions | Primary agents (Build, Plan) + subagents (General, Explore). Custom agents via config or markdown files in `.opencode/agents/`. Per-agent system prompts. | Strong equivalent. Supports custom agent definitions with per-agent model, tools, and prompt configuration. Event-driven multi-agent coordination with peer-to-peer messaging. |
| **Hooks/event callbacks** | PreToolUse, PostToolUse, etc. | Plugin-based hooks: `tool.execute.before`, `tool.execute.after`, `chat.message`, `experimental.session.compacting`, `experimental.chat.system.transform` | Equivalent via plugin system. JS/TS plugins loaded from `.opencode/plugins/` or npm packages. Compaction hook is unique -- allows injecting context during auto-summarization. |
| **Tool system** | File read/write, Bash, Grep, Glob, WebSearch, WebFetch, Agent, MCP | Shell execution, file modification (string replacement), regex search, LSP integration, web fetching, MCP, todo tool | Comparable. LSP integration is a unique advantage (code intelligence: definitions, references, hover). MCP for external tool expansion. |
| **Permission system** | Allow/deny in settings.json | Permission config per action type (edit, shell, etc.). Auto-approve in non-interactive mode. | Simpler than Claude Code. No per-command granularity or deny patterns. |
| **Context management** | Compaction with context-reporter monitoring | Auto-compact (summarizes when approaching context limit). `experimental.session.compacting` hook for custom compaction prompts. | Both have compaction. OpenCode's compaction hook is more extensible. No equivalent of DAAF's utilization monitoring with severity thresholds. |
| **Session persistence** | STATE.md (manual) | SQLite database for sessions. File change tracking. Snapshots for undo/revert. Multi-session support. Session sharing via links. | Stronger built-in persistence. SQLite storage is more robust than manual STATE.md. Snapshot/revert capability is a notable advantage. |
| **Skill/knowledge system** | SKILL.md with progressive disclosure | No native skill system equivalent. Knowledge can be loaded via `instructions` config paths or custom plugins. Community plugins (opencode-rules) provide conditional rule injection. | Gap. OpenCode lacks DAAF-style progressive skill disclosure. Knowledge loading is manual or plugin-driven, not agent-initiated. |
| **Model selection** | Claude family only | 75+ providers. Per-agent model override. Mix models from different providers in one team. Mid-session model switching. | Major advantage. OpenCode's provider freedom is its defining feature. |
| **MCP support** | Yes | Yes, via config | Equivalent. |
| **Logging/transcripts** | Audit log hook, session archive | Debug logging (`-d` flag). File change snapshots. Session history in SQLite. | Less structured logging. No equivalent of DAAF's audit-log hook or output-scanner. |

### Notable Gaps and Advantages

**Advantages over Claude Code for DAAF-like use:**
- Provider freedom -- run with any LLM including local models via Ollama
- Client/server architecture -- run inference on dedicated server, control from lightweight client
- SQLite session persistence with snapshot/revert
- LSP integration for code intelligence
- Compaction hook allows custom context summarization logic
- Open source (can modify the harness itself)

**Gaps relative to DAAF's needs:**
- No native skill/knowledge system -- DAAF's 20+ skills would need plugin-based reimplementation
- Permission system is much simpler -- no per-command deny patterns for safety guardrails
- No native hook events matching DAAF's `PreToolUse` blocking pattern (plugins approximate this)
- Logging and audit trail capabilities are less mature
- Plugin ecosystem is younger and less battle-tested
- No equivalent of DAAF's context-reporter utilization monitoring

### Key Migration Concerns

- The 75+ provider support is the primary draw, but DAAF's orchestration patterns depend heavily on skill loading and agent dispatch which would need significant reimplementation
- DAAF's safety hooks (bash-safety.sh, enforce-file-first.sh, output-scanner.sh) would need conversion to OpenCode's JS/TS plugin format
- The `AGENTS.md` instruction file format transfers directly
- Agent definitions would need conversion from DAAF markdown format to OpenCode JSON/markdown format
- The lack of a native skill system is the largest gap -- DAAF's progressive disclosure architecture is a core design pattern

---

## 3. Cursor (AI IDE)

### Description

Cursor is an AI-native IDE built on VS Code, featuring Agent mode (autonomous multi-step coding), Background/Cloud Agents (run tasks while laptop is closed), and a growing plugin marketplace. Cursor 3.0 (early 2026) introduced Cloud Agents, Composer 2.0, and canvases. It supports multiple LLM backends (Claude 4.x, GPT-5.x, Gemini 2.5, and Cursor's own Composer model).

### Feature Comparison vs. Claude Code

| DAAF Feature | Claude Code | Cursor | Notes |
|---|---|---|---|
| **Custom instructions file** | `CLAUDE.md` | `.cursor/rules/` directory with `.mdc` files (replaced deprecated `.cursorrules`). Rules can be always-on, @-mentionable, Cascade-requested, or glob-attached. | Equivalent but more granular. Individual rule files with activation conditions vs. single hierarchical CLAUDE.md. |
| **Agent/subagent system** | Named agents with definitions | Subagents (Cursor 2.4+) run in parallel with own context. Custom subagents via `.cursor/agents/`. Async subagents (2.5+) -- parent continues while subagents work. Recursive subagent spawning. Up to 8 parallel agents. | Strong equivalent. Cursor's async subagents and recursive spawning are more advanced than Claude Code's synchronous dispatch. |
| **Hooks/event callbacks** | PreToolUse, PostToolUse, etc. | PreToolUse, PostToolUse, `subagentStart`, `beforeSubmitPrompt`, stop hook. `failClosed` option for security-critical hooks. 40x faster hook startup. | Very close equivalent. `subagentStart` hook (can block subagent creation) and `failClosed` option are advantages. |
| **Tool system** | File read/write, Bash, Grep, Glob, WebSearch, WebFetch, Agent, MCP | File read/write, terminal commands, codebase search (semantic + regex), MCP, image processing, Figma integration, canvas rendering | Comparable. Semantic codebase search (vector embeddings) is an advantage. Image/design processing adds visual workflow. Canvas rendering is unique. |
| **Permission system** | Allow/deny in settings.json | Tool-name-based permission rules. Subagent allowlists/denylists. Hook matchers on tool names. "Run Everything", "Auto-Run in Sandbox", "Ask Every Time" modes. Unified CLI/editor permissions. | Comparable. Tool-name-based governance vocabulary is clean. Subagent-specific permission control is an advantage. |
| **Context management** | Compaction with context-reporter | 8K-128K tokens depending on model/mode. @mentions for selective context inclusion. Codebase indexing (chunked into functions/classes, vector embeddings). Auto-compact at 95% capacity. Subagent context isolation. | Different approach. Cursor emphasizes selective context inclusion (@mentions) over DAAF's utilization monitoring. Semantic search reduces need to load full files. |
| **Session persistence** | STATE.md (manual) | Cloud Agent handoff (local to cloud). Sessions persist across terminals/days. JSONL transcript logging. Headless mode transcripts. | Stronger persistence via cloud handoff. JSONL transcripts provide structured session records. |
| **Skill/knowledge system** | SKILL.md with progressive disclosure | Agent Skills (SKILL.md). Dynamically loaded when agent decides they are relevant. Same open standard as Claude Code. Skills marketplace (Cursor 3.0+). | Equivalent. Both use the SKILL.md open standard. Cursor adds a marketplace for skill discovery. |
| **Model selection** | Claude family only | Claude 4.x, GPT-5.x, Gemini 2.5, Cursor's Composer model. Per-subagent model configuration. | Multi-model advantage. Cursor's own Composer model adds a fast option. |
| **MCP support** | Yes | Yes, with plugin marketplace | Equivalent, with marketplace discovery advantage. |
| **Logging/transcripts** | Audit log hook, session archive | JSONL session transcripts. Cursor Blame (tracks AI code + conversations). Headless mode transcripts. | Cursor Blame is a unique advantage for tracking AI contributions to code. |

### Notable Gaps and Advantages

**Advantages over Claude Code for DAAF-like use:**
- Async subagents with recursive spawning -- more flexible orchestration than Claude Code's synchronous dispatch
- Cloud Agents -- tasks continue running on Cursor's infrastructure when laptop is closed
- Semantic codebase search via vector embeddings -- better context relevance for large codebases
- Skills marketplace for discovery and sharing
- JSONL transcripts + Cursor Blame for AI contribution tracking
- Multiple model backends available per-agent
- Canvas rendering for visual outputs
- `failClosed` hook option for security-critical enforcement

**Gaps relative to DAAF's needs:**
- IDE-based -- no pure CLI mode for headless/container operation (though headless mode exists for CI)
- Rule system is file-glob oriented, not hierarchy-aware like CLAUDE.md's directory-level precedence
- Auto-compact triggers at 95% -- too late for DAAF's quality-first approach (DAAF starts monitoring at 40%)
- No equivalent of DAAF's context utilization severity thresholds (NOMINAL/ELEVATED/HIGH/CRITICAL)
- Cannot run inside a Docker container the way DAAF's architecture requires

### Key Migration Concerns

- DAAF requires CLI/container operation -- Cursor is IDE-first, which is a fundamental architectural mismatch for DAAF's Docker-based isolation model
- DAAF's `CLAUDE.md` would need splitting into multiple `.mdc` rule files in `.cursor/rules/`
- DAAF's `SKILL.md` files transfer directly (same standard)
- Hook system is nearly 1:1 but Cursor's hook configuration format differs
- DAAF's `run_with_capture.sh` file-first execution would need adaptation to Cursor's agent workflow
- DAAF's context monitoring approach (40%/60%/75% thresholds with severity-based actions) has no equivalent -- would need custom hooks to approximate

---

## 4. Aider (Open-Source CLI)

### Description

Aider is an Apache 2.0-licensed, open-source AI pair programming CLI tool (Python-based, 41K+ GitHub stars, 5.3M+ PyPI installs). Its philosophy is git-first: every AI edit becomes a git commit with a descriptive message. It supports 100+ LLM providers via LiteLLM routing. Notable for its Architect/Editor dual-model approach and its focus on benchmarking (maintains the Aider polyglot leaderboard).

### Feature Comparison vs. Claude Code

| DAAF Feature | Claude Code | Aider | Notes |
|---|---|---|---|
| **Custom instructions file** | `CLAUDE.md` | `CONVENTIONS.md` loaded via `--read` or config. Supports multiple read-only context files. | Partial equivalent. CONVENTIONS.md is simpler -- a single flat file, no hierarchy or directory precedence. Loaded explicitly, not auto-discovered. |
| **Agent/subagent system** | Named agents with definitions | Architect/Editor dual-model mode (architect reasons, editor formats edits). No general-purpose subagent dispatch. Headless mode (`--message`) for scripted single-task execution. | Minimal equivalent. Architect mode is a two-model pipeline, not a general orchestration system. No named agents, no parallel dispatch, no agent definitions. |
| **Hooks/event callbacks** | PreToolUse, PostToolUse, etc. | Auto-lint (`--lint-cmd`) runs linter after every edit. Auto-test (`--test-cmd`) runs tests after every edit. Watch mode detects `AI!` markers. No general hook/event system. | No equivalent. Aider's lint/test integration is a fixed pipeline, not a configurable event system. Cannot block tool calls or inject custom logic at arbitrary points. |
| **Tool system** | File read/write, Bash, Grep, Glob, WebSearch, WebFetch, Agent, MCP | File editing (multiple formats: edit-block, whole-file, unified-diff, architect). Repo map (tree-sitter symbol graph). `/web` for URL scraping. `/run` for shell commands. Git operations. | More limited. No MCP, no structured search tools, no web search API. Repo map is a unique strength for codebase context without loading full files. |
| **Permission system** | Allow/deny in settings.json | `--yes-always` for auto-approve. No per-command allow/deny. No sandbox. Relies on git for rollback. | No equivalent. Aider has no permission guardrails -- it either asks for confirmation or auto-approves everything. Safety comes from git history (you can revert). |
| **Context management** | Compaction with context-reporter | Soft token limit for chat history with summarization. Repo map provides context without loading files. Prompt caching (`--cache-prompts`). | Simpler approach. Repo map is clever for reducing context load. No utilization monitoring or severity thresholds. |
| **Session persistence** | STATE.md (manual) | Chat history file (`--chat-history-file`), input history, LLM history file. Restore with `--restore-chat-history`. No structured state beyond conversation log. Works with tmux/screen for persistent sessions. | Minimal. Session is just conversation log, not structured project state. No pause/resume for complex workflows. |
| **Skill/knowledge system** | SKILL.md with progressive disclosure | None. Context provided via `--read` files (read-only, cached). No on-demand loading, no agent-initiated skill discovery. | No equivalent. All context must be pre-loaded. No progressive disclosure or dynamic loading. |
| **Model selection** | Claude family only | 100+ providers via LiteLLM. Per-role model selection (main, editor, weak/summarizer). Mid-session switching via `/model`. Short aliases (`sonnet`, `opus`, `haiku`). | Major advantage. Per-role model selection (architect vs. editor vs. summarizer) is more granular than most competitors. |
| **MCP support** | Yes | No | No MCP support. |
| **Logging/transcripts** | Audit log hook, session archive | Chat history file, LLM history file, input history. Git commits serve as audit trail. | Different philosophy. Git IS the audit trail -- every edit is a commit. Less structured than hook-based logging. |

### Notable Gaps and Advantages

**Advantages over Claude Code for DAAF-like use:**
- Git-native workflow -- every AI edit is an atomic commit with descriptive message (aligns with DAAF's immutable versioning philosophy)
- Architect/Editor mode -- separate reasoning from formatting, reducing errors on multi-file changes and saving 30-50% on costs
- Repo map (tree-sitter symbol graph) -- smart context without loading full files
- Broadest model support (100+ providers, per-role selection)
- Auto-lint/auto-test feedback loops -- catches issues immediately
- Lightweight, minimal dependencies, works over SSH

**Gaps relative to DAAF's needs:**
- No agent/subagent system -- DAAF's multi-agent orchestration is impossible
- No hook/event system -- DAAF's safety guardrails cannot be implemented
- No permission system -- DAAF's defense-in-depth architecture has no foundation to build on
- No skill/knowledge system -- DAAF's 20+ domain skills would need to be manually loaded as read files
- No MCP -- no tool extensibility
- No context monitoring -- DAAF's utilization-based quality management has no support

### Key Migration Concerns

- **Fundamental mismatch**: Aider is a pair programming tool, not an orchestration framework. DAAF's core architecture (multi-agent dispatch, hook-based safety, progressive skill loading) has no foundation in Aider.
- Could serve as a **component within** a larger system (e.g., as the "editor" tool called by an orchestrator) but cannot replace Claude Code as DAAF's harness
- CONVENTIONS.md provides basic instruction loading but lacks hierarchy, auto-discovery, and progressive disclosure
- Git-first workflow aligns philosophically with DAAF's immutable versioning but the implementation approach differs significantly
- Would require building an entire orchestration layer on top of Aider to approximate DAAF's capabilities

---

## 5. Windsurf / Codeium (AI IDE)

### Description

Windsurf is an AI-native IDE built on VS Code, originally developed by Codeium and now owned by Cognition AI (the Devin team) following a ~$250M acquisition in December 2025. Its core agent is Cascade, which features "Flow awareness" -- tracking user actions, edits, terminal commands, and clipboard to infer intent. Ranked #1 in LogRocket AI Dev Tool Power Rankings (Feb 2026). Uses proprietary SWE-1.5 model alongside third-party models (GPT-5.x, Claude 4.x, Gemini 3).

### Feature Comparison vs. Claude Code

| DAAF Feature | Claude Code | Windsurf/Cascade | Notes |
|---|---|---|---|
| **Custom instructions file** | `CLAUDE.md` | Rules files in project. Four activation modes: always-on, @mention-able, Cascade-requested, glob-attached. Enterprise `.codeiumignore`. Windsurf Directory for curated example rules. | Equivalent. Granular activation modes are an advantage over CLAUDE.md's always-on approach. |
| **Agent/subagent system** | Named agents with definitions | Cascade agent with Chat and Code modes. No documented subagent dispatch system. Background task execution. Reusable markdown commands. | Partial. Cascade is a single persistent agent, not a multi-agent orchestration system. No named agent definitions or parallel dispatch. |
| **Hooks/event callbacks** | PreToolUse, PostToolUse, etc. | Cascade Hooks (v1.12.41+): user prompt hooks (pre), model response hooks (post), `POST_CASCADE_RESPONSE_WITH_TRANSCRIPT`. Available to all tiers. Enterprise team settings management. | Partial equivalent. Fewer hook events than Claude Code or Codex. Focus is on logging/compliance rather than tool-call interception. User prompt hooks can block policy-violating prompts. |
| **Tool system** | File read/write, Bash, Grep, Glob, WebSearch, WebFetch, Agent, MCP | File read/write, terminal commands, codebase search (SWE-grep, 10x faster), MCP, image processing, Figma, Codemaps (visual code navigation). | Comparable. SWE-grep and Codemaps are unique advantages. MCP for extensibility. |
| **Permission system** | Allow/deny in settings.json | Transcript file permissions (0600). Auto-limit on transcript storage (100 files). Enterprise tier controls. No documented per-command allow/deny. | Weaker. No per-command permission granularity. Enterprise governance is tier-locked. |
| **Context management** | Compaction with context-reporter | "Flow awareness" -- tracks user edits, terminal commands, clipboard, conversation history as shared timeline. Fast Context (SWE-grep) for 10x faster code retrieval. | Different paradigm. Flow awareness is implicit context from user behavior rather than explicit context management. No documented compaction or utilization monitoring. |
| **Session persistence** | STATE.md (manual) | Memories -- persistent cross-session knowledge of coding patterns, project structure, preferences. JSONL transcript files. | Memories feature is a notable advantage -- true cross-session learning. JSONL transcripts provide structured records. |
| **Skill/knowledge system** | SKILL.md with progressive disclosure | No documented equivalent to SKILL.md. Domain knowledge provided via rules files. Terminal snippets and reusable markdown commands. | Gap. No progressive skill loading system. |
| **Model selection** | Claude family only | SWE-1.5 (proprietary, 13x faster than Sonnet 4.5), GPT-5.x, Claude 4.x, Gemini 3, BYOK support. | Multi-model advantage, including a proprietary fast model. |
| **MCP support** | Yes | Yes, with out-of-box integrations (Figma, Slack, Stripe, PostgreSQL, Playwright) | Equivalent, with more pre-built integrations. |
| **Logging/transcripts** | Audit log hook, session archive | JSONL transcripts via `POST_CASCADE_RESPONSE_WITH_TRANSCRIPT` hook. Full conversation context including file contents, command outputs, tool args, search results, applied rules. 0600 permissions. Auto-pruning at 100 files. | Strong logging. JSONL transcript format is more structured than text-based audit logs. Enterprise audit/compliance focus. |

### Notable Gaps and Advantages

**Advantages over Claude Code for DAAF-like use:**
- Memories -- cross-session persistent learning (no other harness has this built-in)
- Flow awareness -- implicit context tracking from user behavior
- SWE-1.5 proprietary model -- 13x faster than Sonnet 4.5
- Codemaps -- AI-annotated visual code navigation (unique feature)
- JSONL transcripts with full conversation context for audit compliance
- Pre-built MCP integrations (Figma, Slack, Stripe, etc.)

**Gaps relative to DAAF's needs:**
- No subagent system -- DAAF's multi-agent orchestration cannot be implemented
- Hook system is limited compared to Claude Code's PreToolUse/PostToolUse pattern
- No per-command permission system -- DAAF's safety guardrails have no foundation
- No skill/knowledge system -- progressive disclosure architecture unsupported
- IDE-based -- cannot run in Docker container environment
- Ownership changes (Codeium to Cognition) introduce platform stability risk

### Key Migration Concerns

- **Fundamental mismatch**: Like Cursor, Windsurf is IDE-first -- DAAF requires CLI/container operation
- No subagent system means DAAF's entire orchestration architecture would need replacement
- Memories feature is interesting for research workflows but lacks the structure of DAAF's STATE.md approach
- Hook system is too limited for DAAF's defense-in-depth safety architecture
- Platform ownership instability (multiple attempted acquisitions in 2025) raises questions about long-term investment
- Could complement a CLI harness for visual/interactive work but cannot serve as DAAF's primary harness

---

## 6. Cross-Harness Comparison Matrix

### Critical DAAF Features vs. All Harnesses

| DAAF Feature | Claude Code (Current) | Codex CLI | OpenCode | Cursor | Aider | Windsurf |
|---|---|---|---|---|---|---|
| **Custom instructions** | CLAUDE.md (hierarchical) | AGENTS.md (hierarchical) | AGENTS.md + rules plugin | .mdc rules (granular) | CONVENTIONS.md (flat) | Rules (4 activation modes) |
| **Multi-agent orchestration** | Yes (named agents) | Yes (custom agents, subagents) | Yes (primary + sub, event-driven) | Yes (async subagents, recursive) | No (architect/editor only) | No (single Cascade agent) |
| **Hook/event system** | 5 events, blocking PreToolUse | 5 events, concurrent hooks | Plugin-based, extensible | 6+ events, failClosed option | No (lint/test only) | 3 events, compliance focus |
| **Per-command permissions** | Allow/deny pattern lists | Profile-based + sandbox modes | Simple per-action-type | Tool-name-based rules | None (auto-approve or confirm all) | Enterprise tier only |
| **Context monitoring** | context-reporter with severity thresholds | Skill budget (2% cap) | Auto-compact with hook | @mentions, 95% auto-compact | Soft token limit + summarization | Flow awareness (implicit) |
| **Progressive skill loading** | SKILL.md (on-demand) | SKILL.md (on-demand, budgeted) | No native support | SKILL.md (on-demand, marketplace) | No | No |
| **Session persistence** | STATE.md (manual) | /goal with pause/resume | SQLite + snapshots | Cloud handoff, JSONL | Chat history file | Memories (cross-session) |
| **File-first execution** | run_with_capture.sh | Would need custom hook | Would need custom plugin | Would need custom hook | N/A (git commits as trail) | Would need custom hook |
| **Immutable script versioning** | Convention in CLAUDE.md | Would need AGENTS.md convention | Would need AGENTS.md convention | Would need rules convention | Git commits per edit | Would need rules convention |
| **Defense-in-depth safety** | 6-layer (hooks + deny + sandbox + container) | 4-layer (hooks + profiles + sandbox + enterprise) | 2-layer (permissions + plugins) | 4-layer (hooks + permissions + sandbox + plugins) | 1-layer (git revert) | 2-layer (hooks + enterprise) |
| **Model diversity** | Claude only | GPT-5 family only | 75+ providers | Multi-model (Claude, GPT, Gemini, Composer) | 100+ providers (LiteLLM) | Multi-model + SWE-1.5 |
| **MCP tool extensions** | Yes | Yes (with auto-wiring) | Yes | Yes (marketplace) | No | Yes (pre-built integrations) |
| **CLI/container operation** | Yes (native) | Yes (native) | Yes (native) | Partial (headless mode) | Yes (native) | No (IDE only) |
| **Open source** | No | No | Yes (Go) | No | Yes (Python, Apache 2.0) | No |
| **Audit trail/logging** | Hook-based (customizable) | App/CLI transcripts | Debug logs, SQLite | JSONL transcripts, Blame | Git history | JSONL transcripts |

### Readiness Tiers for DAAF Migration

Based on feature coverage of DAAF's critical needs:

| Tier | Harness | Rationale |
|---|---|---|
| **Tier 1: Closest Feature Parity** | **Codex CLI** | Most DAAF features have direct equivalents. AGENTS.md, SKILL.md, hooks, subagents, permissions all present. Primary gaps: per-command deny patterns, file-first execution pattern, OpenAI-model lock-in. |
| **Tier 1: Closest Feature Parity** | **Cursor** | Nearly all features present, strongest subagent system (async, recursive). Primary gaps: IDE-first (no container mode), context monitoring less sophisticated, no per-command deny patterns. |
| **Tier 2: Partial Coverage** | **OpenCode** | Strong multi-model support, agent system present, plugin extensibility. Major gaps: no native skill system, weaker permissions, immature logging. Open source allows custom development. |
| **Tier 3: Significant Gaps** | **Windsurf** | Good for single-agent workflows with strong logging. Major gaps: no multi-agent orchestration, no skill system, IDE-only, limited hooks. |
| **Tier 3: Significant Gaps** | **Aider** | Excellent for git-native pair programming. Fundamentally lacks orchestration, hooks, permissions, skills -- would require building an entire framework layer on top. |

### Features Unique to DAAF (No Direct Equivalent Anywhere)

These DAAF features have no direct equivalent in any surveyed harness and would require custom implementation regardless of target:

1. **Context utilization severity thresholds** (NOMINAL/ELEVATED/HIGH/CRITICAL with role-appropriate actions) -- Other harnesses have compaction but not quality-degradation monitoring with graduated response protocols
2. **File-first execution with `run_with_capture.sh`** (append stdout/stderr to script file as immutable audit record) -- Git commits approximate this but don't capture execution output inline
3. **Inline Audit Trail (IAT)** conventions (INTENT/REASONING/ASSUMES prefixes) -- A documentation convention, not a harness feature, but DAAF enforces it via agent instructions
4. **Immutable script versioning** (failed scripts keep execution logs, fixes go to `_a.py`, `_b.py`) -- A convention that would transfer via instruction files but has no harness enforcement
5. **Defense-in-depth with 6 coordinated safety layers** -- Other harnesses have subsets but none have the full layered architecture (hooks + deny rules + allow lists + output scanning + container isolation + pre-commit hooks)
6. **Subagent context monitoring with early-return protocol** -- Subagents in other harnesses have context limits but no graduated "return your work before you degrade" protocol

### Industry Convergence Observations

Several DAAF architectural patterns have become industry standards or near-standards as of 2026:

1. **SKILL.md / Agent Skills** -- The `agentskills.io` open standard (originated by Anthropic for Claude Code) has been adopted by Codex, Cursor, and is influencing OpenCode. DAAF's skill architecture is now portable.
2. **AGENTS.md / Custom instructions** -- Every harness supports project-level instruction files. The name `AGENTS.md` has become a de facto convention beyond just Codex.
3. **MCP (Model Context Protocol)** -- Supported by Claude Code, Codex, OpenCode, Cursor, and Windsurf. Tool extensibility is standardized.
4. **Hooks/lifecycle events** -- Four of five harnesses support hooks (Aider being the exception). Event names are converging (PreToolUse/PostToolUse).
5. **Subagent context isolation** -- Codex, OpenCode, and Cursor all isolate subagent context windows, matching Claude Code's approach.

---

## 7. Sources

### ChatGPT Codex
- [Codex Developer Documentation](https://developers.openai.com/codex)
- [AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md)
- [Codex Hooks](https://developers.openai.com/codex/hooks)
- [Codex Subagents](https://developers.openai.com/codex/subagents)
- [Codex Agent Skills](https://developers.openai.com/codex/skills)
- [Codex Models](https://developers.openai.com/codex/models)
- [Codex CLI Features](https://developers.openai.com/codex/cli/features)
- [Codex Configuration Reference](https://developers.openai.com/codex/config-reference)
- [Codex Changelog](https://developers.openai.com/codex/changelog)
- [Introducing the Codex App](https://openai.com/index/introducing-the-codex-app/)

### OpenCode
- [OpenCode Official Documentation](https://opencode.ai/docs/)
- [OpenCode Tools](https://opencode.ai/docs/tools/)
- [OpenCode Rules](https://opencode.ai/docs/rules/)
- [OpenCode Permissions](https://opencode.ai/docs/permissions/)
- [OpenCode Agents](https://opencode.ai/docs/agents/)
- [OpenCode Plugins](https://opencode.ai/docs/plugins/)
- [OpenCode Config](https://opencode.ai/docs/config/)
- [OpenCode GitHub Repository](https://github.com/opencode-ai/opencode)
- [Building Agent Teams in OpenCode](https://dev.to/uenyioha/porting-claude-codes-agent-teams-to-opencode-4hol)
- [OpenCode vs Claude Code Comparison](https://dev.to/tech_croc_f32fbb6ea8ed4/opencode-vs-claude-code-which-ai-cli-coding-agent-wins-in-2026-45md)

### Cursor
- [Cursor Agent Overview](https://cursor.com/docs/agent/overview)
- [Cursor Hooks Documentation](https://cursor.com/docs/hooks)
- [Cursor Agent Skills](https://cursor.com/docs/skills)
- [Cursor Best Practices](https://cursor.com/blog/agent-best-practices)
- [Cursor 2.0 Changelog](https://cursor.com/changelog/2-0)
- [Cursor 2.4 -- Subagents, Skills](https://cursor.com/changelog/2-4)
- [Cursor 2.5 -- Plugins, Sandbox, Async Subagents](https://cursor.com/changelog/2-5)
- [Cursor Context Window Guide](https://www.morphllm.com/cursor-context-window)
- [Cursor 2.4 Subagents Analysis](https://memu.pro/blog/cursor-2-4-subagents-skills-memory)

### Aider
- [Aider Official Documentation](https://aider.chat/docs/)
- [Aider Configuration](https://aider.chat/docs/config.html)
- [Aider YAML Config](https://aider.chat/docs/config/aider_conf.html)
- [Aider Conventions](https://aider.chat/docs/usage/conventions.html)
- [Aider Linting and Testing](https://aider.chat/docs/usage/lint-test.html)
- [Aider Chat Modes](https://aider.chat/docs/usage/modes.html)
- [Aider Options Reference](https://aider.chat/docs/config/options.html)
- [Aider Architect Mode](https://aider.chat/2024/09/26/architect.html)
- [Aider Guide 2026](https://www.deployhq.com/guides/aider)
- [CONVENTIONS.md Guide](https://www.claudemdeditor.com/aider-conventions-guide)

### Windsurf
- [Windsurf Cascade Hooks](https://docs.windsurf.com/windsurf/cascade/hooks)
- [Windsurf Changelog](https://windsurf.com/changelog)
- [Windsurf Review 2026 (Taskade)](https://www.taskade.com/blog/windsurf-review)
- [Windsurf Review 2026 (AI Agent Square)](https://aiagentsquare.com/agents/windsurf.html)
- [Windsurf SWE-1.5 and Cascade Hooks Guide](https://www.digitalapplied.com/blog/windsurf-swe-1-5-cascade-hooks-november-2025)
- [Windsurfrules Complete Guide 2026](https://thepromptshelf.dev/blog/windsurfrules-complete-guide-2026/)
- [Windsurf Flow Context Engine](https://markaicode.com/windsurf-flow-context-engine/)
- [Windsurf Cascade Review](https://www.seaflux.tech/blogs/cascade-windsurf-ai-keeps-developers-in-flow/)

### Cross-Harness
- [2026 Guide to Coding CLI Tools: 15 Agents Compared](https://www.tembo.io/blog/coding-cli-tools-comparison)
- [AI Agent Skills Open Standard Guide](https://www.thepromptindex.com/how-to-use-ai-agent-skills-the-complete-guide.html)
- [Building Effective AI Coding Agents (arxiv)](https://arxiv.org/html/2603.05344v2)
- [8 Best AI Coding Assistants (Augment Code)](https://www.augmentcode.com/tools/8-top-ai-coding-assistants-and-their-best-use-cases)
