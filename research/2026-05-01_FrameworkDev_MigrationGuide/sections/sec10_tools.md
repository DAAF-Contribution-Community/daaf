## 10. Tool System and Calling Conventions

**Classification: HYBRID** -- Claude Code provides the built-in tools, the XML-based calling convention, deferred tool loading via ToolSearch, and the per-agent tool restriction mechanism. DAAF designed the one-command-per-Bash-call rule, the four-tier tool-access system, the file-first execution pattern, and the interactive Python prohibition.

**Criticality:** HIGH | **Interdependencies:** 5 (agent system, permission system, hook system, logging/audit, instruction loading)

---

### Design Intent

An AI coding agent's tool system is where instructions become actions. The tools themselves -- reading files, running commands, searching code -- are general-purpose capabilities provided by the harness. But how those tools are *governed* determines whether the system produces auditable, reproducible research or ephemeral, unverifiable output. DAAF layers three design decisions onto Claude Code's tool system, each addressing a specific failure mode:

1. **One command per Bash call** prevents safety-hook bypass. If multiple commands can be chained in a single Bash invocation, a dangerous command can hide behind a benign one -- the safety hook evaluates the string once, and a destructive `&&`-chained suffix may escape pattern matching. Separating commands ensures each is independently evaluated, independently logged, and independently subject to user approval.

2. **Per-agent tool restrictions** enforce the principle of least privilege. A read-only verification agent has no need for Write or Edit tools. Granting them creates risk (accidental writes, confused scope) with no benefit. DAAF defines four distinct tool-access tiers aligned to agent roles, so each agent has exactly the capabilities its job requires and nothing more.

3. **File-first execution** ensures every analytical operation produces a permanent, auditable artifact. Interactive Python execution is fast and convenient, but it leaves no trace: no script file to review, no captured output to verify, no immutable record to archive. DAAF prohibits interactive execution and requires that all Python runs go through the write-execute-capture pipeline (detailed in Section 9). The tool system is where this prohibition is enforced.

---

### What It Does

The tool system provides every capability the AI agent uses to interact with the project: reading and writing files, searching code, executing commands, accessing the web, dispatching subagents, and loading domain knowledge. It encompasses both the tools themselves and the conventions governing their use. At the harness level, it resolves tool invocations into actions, handles parameter passing, supports parallel execution, and returns results (including errors). At the DAAF level, it constrains *how* tools are used -- limiting Bash to single commands, restricting which agents can use which tools, and enforcing that all Python execution flows through the file-first protocol.

---

### Current Realization on Claude Code

#### Tool Inventory (Native Primitive)

Claude Code provides 17+ built-in tools organized into six functional categories:

| Category | Tools | DAAF Notes |
|----------|-------|------------|
| **File operations** | Read, Write, Edit, NotebookEdit | NotebookEdit unused (DAAF uses Marimo `.py`, not `.ipynb`). Read supports text, images, PDFs, notebooks. Edit preferred over Write for modifications. |
| **Search** | Glob, Grep | Available to all agents. Grep is built on ripgrep. |
| **Command execution** | Bash | Primary execution tool; heavily constrained by DAAF conventions and hooks. Supports timeout and background mode. |
| **Web access** | WebSearch, WebFetch | Restricted to 3 of 14 agents. WebFetch NOT auto-allowed (exfiltration vector -- see Section 5). |
| **Subagent/task management** | Agent, Task, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskOutput, TaskStop | Agent/Task are the core dispatch tools. Task* tools used sparingly for progress tracking. Background tasks disabled (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`) and blocked by hook. |
| **Knowledge** | Skill | On-demand domain knowledge injection (see Section 6). |
| **Tool discovery** | ToolSearch | Loads deferred tool schemas on demand. |

#### Calling Conventions (Native Primitive)

Claude Code uses an XML-based calling convention: the model emits `<function_calls>` blocks containing `<invoke>` elements with named `<parameter>` sub-elements. String parameters are passed as text; arrays and objects as JSON. Results return in `<function_results>` blocks. Optional parameters are omitted entirely (not set to null).

The two features DAAF depends on architecturally are **parallel invocation** -- multiple `<invoke>` elements in one block execute concurrently, enabling wave-based parallel subagent dispatch (up to 5 simultaneous Agent calls) -- and **structured error returns** -- hook-blocked commands, permission denials, and tool failures all return descriptive messages the model can interpret and act on.

The specific XML format is Claude Code-specific and not architecturally significant. Any structured protocol supporting named parameters, parallel invocation, and error returns is sufficient.

#### Deferred Tools and ToolSearch (Native Primitive)

Not all tools are loaded into the model's context by default. Deferred tools have their schemas withheld from the initial system prompt to conserve context tokens. When needed, the model uses **ToolSearch** to discover and load a tool's schema, after which the tool becomes callable.

**Always loaded (core 10):** Read, Write, Edit, Bash, Glob, Grep, Agent, Skill, WebSearch, WebFetch.

**Deferred (loaded via ToolSearch):** TaskCreate, TaskUpdate, TaskGet, TaskList, TaskOutput, TaskStop, NotebookEdit.

DAAF's only observed use of ToolSearch is to load TaskCreate and TaskUpdate for progress tracking during Reproducibility Verification mode. The mechanism is a context optimization -- each tool schema consumes tokens, and deferring rarely-used tools keeps the base context smaller. For migration purposes, deferred tool loading is a nice-to-have, not a requirement. If the target harness loads all tool schemas eagerly, the only cost is slightly higher base context usage.

#### Per-Agent Tool Restrictions (Native Primitive, DAAF-Configured)

Claude Code supports a `tools` field in agent YAML frontmatter that declares an explicit allowlist. When specified, the agent can *only* use the listed tools; attempting an unlisted tool produces an error ("No such tool available: Write. Write exists but is not enabled in this context."). DAAF specifies this field on every agent for explicitness, producing four distinct access tiers.

#### File-First Execution Enforcement (DAAF-Built, Multiple Layers)

The connection between the tool system and DAAF's audit trail is the file-first execution protocol. Every Python operation must follow the write-execute-capture pattern: write a complete script via Write, execute it via `run_with_capture.sh` (invoked through the Bash tool), and let the wrapper capture stdout/stderr back into the script file. This is detailed in Section 9; the tool system's role is enforcement via the `enforce-file-first.sh` PreToolUse hook, which blocks direct `python`/`python3` invocations on coding agents (see Section 7 for the hook specification).

---

### Design Choices and Rationale

**One command per Bash call.** CLAUDE.md mandates: "Every Bash tool call must contain exactly one command. No `&&`, `;`, or `||` chaining." This is not a stylistic preference -- it is a safety architecture decision. DAAF's safety hooks (`bash-safety.sh`, `enforce-file-first.sh`) evaluate each Bash invocation as a string. A chained command like `ls && rm -rf /` would present the entire string to the hook, which might match on `ls` (benign) and fail to catch the `rm -rf /` suffix depending on pattern structure. Equally important, the permission system evaluates each Bash call independently: the user sees and approves one command at a time, not an opaque multi-command string. And the audit log records one command per entry, making the execution history reviewable at the granularity of individual operations. The cost is verbose tool-calling (three Bash calls instead of one chained command), which is acceptable because tool calls are cheap and safety is not.

**Four tool-access tiers, not two.** A simpler design would offer "read-only" and "read-write" tiers. DAAF adds two web-enabled tiers because web access introduces a distinct risk surface: data exfiltration (WebFetch can make arbitrary HTTP requests), exposure to unvetted information, and hallucination risk from web content. By restricting WebSearch and WebFetch to three agents (debugger, data-ingest, search-agent), DAAF ensures that only agents with an explicit need for external information -- and whose protocols include instructions for handling it -- have web access. The four tiers are:

| Tier | Tools | Agents | Count |
|------|-------|--------|-------|
| **Full read/write** | Read, Write, Edit, Bash, Glob, Grep, Skill | code-reviewer, data-planner, framework-engineer, notebook-assembler, report-writer, research-executor, research-synthesizer | 7 |
| **Read-only** | Read, Bash, Glob, Grep, Skill | data-verifier, integration-checker, plan-checker, source-researcher | 4 |
| **Read-only + web** | Read, Bash, Glob, Grep, Skill, WebSearch, WebFetch | search-agent | 1 |
| **Full read/write + web** | Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill | data-ingest, debugger | 2 |

Note that the `tools` field operates in conjunction with `permissionMode`. Read-only agents (`plan` mode) cannot write files even via Bash -- the runtime blocks it at a layer below the tool system (see Section 5). The `tools` field removes the tools from the agent's context entirely, so the agent does not even *consider* writing; `permissionMode` provides the hard enforcement if it somehow tries.

**Interactive Python is prohibited, not merely discouraged.** Three independent mechanisms enforce this:

1. **CLAUDE.md instructions** (behavioral): "You NEVER execute Python code interactively" with explicit mandated write-execute-capture pattern.
2. **enforce-file-first.sh hook** (programmatic, agent-scoped): Blocks direct `python`/`python3` Bash invocations on the four coding agents (research-executor, code-reviewer, debugger, data-ingest). Exits with code 2 (BLOCK) and returns a message directing the agent to use `run_with_capture.sh`.
3. **BOUNDARIES.md prohibition** (documented policy): `mcp__ide__executeCode` is explicitly prohibited because it would bypass the file-first audit trail.

The three layers follow DAAF's defense-in-depth philosophy: instructions can be ignored, hooks can malfunction, and documented policies can be overlooked. Any single layer is sufficient for the common case; all three together provide robust enforcement. The hook is registered per-agent (only on coding agents, via agent frontmatter) rather than project-wide because not all agents execute Python -- applying it globally would interfere with non-coding agents that legitimately run other Bash commands.

**MCP is not used.** The Model Context Protocol (MCP) provides a standardized way to connect AI agents to external tools and services. DAAF does not use MCP servers -- no `.mcp.json` configuration exists, and the only MCP reference in the framework is the explicit prohibition of `mcp__ide__executeCode` in BOUNDARIES.md. The prohibition exists because IDE code execution tools bypass the file-first protocol: they run code interactively with no script artifact, no captured output, and no immutable record. DAAF's built-in tools and skill system satisfy all current integration needs. An implementer adding MCP tools to a DAAF port should verify that each tool preserves the audit trail -- any tool that executes code without producing a permanent script artifact violates DAAF's reproducibility guarantee.

**Agent and Task are interchangeable.** Claude Code provides both `Agent` and `Task` dispatch tools; DAAF includes permission entries for both. The distinction is a Claude Code internal detail -- an implementer needs only one subagent dispatch mechanism.

---

### Replication Specification

**Required capabilities in the target harness:**

1. **Core tool categories.** The harness must provide tools for: file reading, file writing, targeted file editing, shell command execution, file-name search, file-content search, web search, URL fetching, subagent dispatch, and domain knowledge injection. These nine functional categories cover DAAF's operational needs. The specific tool count is less important than categorical coverage.

2. **Per-agent tool restriction.** The harness must support declaring which tools each agent can access, as an explicit allowlist. When a tool is not in the agent's list, the agent must be unable to invoke it -- ideally the tool should not appear in the agent's context at all, so the model does not waste reasoning on unavailable capabilities. This is how DAAF enforces the four-tier access system.

3. **Parallel tool invocation.** The harness must support invoking multiple tools in a single model turn, with all invocations executing concurrently. DAAF uses this for wave-based parallel subagent dispatch (up to 5 simultaneous Agent calls). Without parallel invocation, DAAF's dispatch architecture degrades to sequential execution, significantly increasing pipeline latency.

4. **Structured error returns.** When a tool call fails (command error, hook block, permission denial), the error message must be returned to the model in a structured format that the model can interpret and act on. DAAF's safety hooks return descriptive messages (e.g., "Direct Python execution blocked. Use run_with_capture.sh instead.") that guide the model toward the correct behavior.

5. **Pre-execution interception.** The harness must support intercepting tool calls before execution (see Section 7 for the full hook specification). For the tool system specifically, this enables: single-command enforcement for shell execution, file-first enforcement for Python execution, and agent-type validation for subagent dispatch.

6. **Shell command isolation.** Each shell command execution should not carry state from previous executions. Claude Code resets shell state between Bash calls (the working directory persists but shell variables, aliases, and environment modifications do not). DAAF depends on this isolation -- each command is a standalone operation, not part of an implicit shell session.

**Behavioral contract:**

- Each tool call is an atomic operation: it succeeds completely or fails with an error message. No partial execution.
- Tool results are returned to the model before the next tool call begins (within a single turn, parallel calls return together).
- The harness enforces tool restrictions at runtime -- an agent cannot invoke tools outside its allowlist regardless of what the model attempts.
- Deferred/lazy tool loading is optional; eager loading of all tool schemas is acceptable if context budget permits.

**Acceptance criteria:**

Feature parity is achieved when: (a) all nine functional tool categories are available, (b) per-agent tool restrictions prevent agents from using unlisted tools, (c) parallel tool invocation supports at least 5 concurrent calls, (d) shell command execution does not carry state between calls, (e) the one-command-per-Bash-call convention is enforceable (via pre-execution hooks or harness configuration), and (f) the file-first execution pattern can be enforced (blocking direct interpreter invocations for designated agents).

**Degraded-mode options:**

- Without deferred tool loading: load all tool schemas eagerly. Cost is higher base context usage; no functional impact.
- Without parallel tool invocation: dispatch subagents sequentially. Pipeline execution time increases linearly with wave size, but correctness is unaffected.
- Without per-agent tool restrictions: enforce restrictions via agent instructions combined with hook-based blocking. Weaker (instructions can be ignored) but partially effective, especially when combined with hooks that block specific tool patterns.

---

### Harness Landscape

- **Codex (OpenAI):** JSON function calling; supports tool restrictions on agents via configuration. Sandboxed container aligns with single-command enforcement. Closest parity.
- **Cursor:** Agent-level tool configuration supported. MCP integration provides extensibility. No container isolation for shell commands.
- **OpenCode:** Tool plugins with configurable access. Hook system supports pre-execution interception. Parallel tool calls supported.
- **Windsurf / Aider:** Limited tool restriction mechanisms. Enforcing per-agent tool allowlists would require middleware. Single-command enforcement would need custom shell wrapper.

---

### Dependencies

| Depends On | Relationship |
|------------|-------------|
| **Instruction Loading (Section 3)** | CLAUDE.md carries the one-command-per-Bash-call rule and the file-first execution mandate |
| **Agent System (Section 4)** | The `tools` frontmatter field defines per-agent tool restrictions; agent dispatch is itself a tool |
| **Permission System (Section 5)** | Allow/deny lists gate which tool invocations auto-execute, prompt, or block; tools are the subject of permission evaluation |
| **Hook System (Section 7)** | PreToolUse hooks enforce single-command discipline (`bash-safety.sh`), file-first execution (`enforce-file-first.sh`), and agent dispatch restrictions (`enforce-explore-model.sh`, `enforce-foreground-agents.sh`, `deny-claude-code-guide.sh`) |
| **Logging/Audit (Section 9)** | File-first execution connects the tool system to the audit trail; `audit-log.sh` records every tool invocation; `run_with_capture.sh` is invoked via the Bash tool |

| Depended On By | Relationship |
|----------------|-------------|
| **Agent System (Section 4)** | Agent dispatch (Agent/Task tools) is part of the tool system |
| **Hook System (Section 7)** | Hooks fire on tool invocations; the tool system is the surface they intercept |
| **Logging/Audit (Section 9)** | The audit log captures tool invocations; file-first execution is enforced at the tool layer |
| **Context Management (Section 8)** | The context-reporter hook fires on every tool call via PreToolUse; ToolSearch manages context budget by deferring rarely-used schemas |
