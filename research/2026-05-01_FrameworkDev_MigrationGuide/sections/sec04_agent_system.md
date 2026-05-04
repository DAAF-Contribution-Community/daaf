## 4. Agent System: Definition, Dispatch, and Isolation

**Classification: HYBRID** | **Criticality: CRITICAL** | **Interdependencies: 7**

The agent system is DAAF's architectural backbone. Claude Code provides the runtime primitives: agent definition files with YAML frontmatter, the Agent/Task dispatch tools, per-agent tool restrictions, permission modes, and context isolation. DAAF designed everything layered on top: the 14 specialized agents, the 12-section protocol template, structured output contracts, skill-preloading strategy, wave-based parallelism patterns, tool-access tiers, and the hooks that block unsuitable agent types.

---

## 4.1 Design Intent

Multi-stage research pipelines require fundamentally different capabilities at different stages: data fetching demands web access and code execution; QA review demands read access and analytical judgment; plan verification demands read-only inspection. A single general-purpose agent cannot optimally serve all of these roles, and giving every agent full capabilities violates the principle of least privilege.

DAAF's agent system solves three problems simultaneously:

1. **Specialization without complexity.** Each agent carries exactly the tools, permissions, domain knowledge, and behavioral protocol it needs for its role -- nothing more. A `plan-checker` cannot accidentally write files; a `research-executor` cannot accidentally browse the web (unless it is the `debugger`, which has a legitimate need for web access during error diagnosis).

2. **Context isolation as a resource strategy.** Each subagent receives a fresh context window (~200K tokens), independent of the orchestrator's context. This means skill loading, code execution, and verbose data exploration happen in disposable context that does not consume the orchestrator's limited budget. Dispatch is explicitly used as a context preservation mechanism.

3. **Auditable delegation.** Every agent dispatch is visible to the researcher (named agents require permission confirmation), every agent's behavioral protocol is inspectable on disk, and every return follows a structured format. The researcher can audit not just what the AI did, but which specialist did it and under what constraints.

---

## 4.2 What It Does

The agent system provides six capabilities:

- **Definition**: Agent behavior, tool access, permissions, and knowledge are declared in markdown files with YAML frontmatter, stored in `.claude/agents/`.
- **Routing**: When the orchestrator dispatches a named agent, the runtime matches the `subagent_type` parameter to an agent file's `name` field and loads its full configuration.
- **Isolation**: Each dispatched agent receives a fresh context window with no access to the parent's conversation history.
- **Restriction**: Per-agent tool allowlists and permission modes enforce least-privilege access at the runtime level.
- **Parallelism**: Up to 5 agents can be dispatched concurrently in a single response, enabling wave-based parallel execution.
- **Gating**: PreToolUse hooks intercept every dispatch call and block unsuitable agent types before they spawn.

---

## 4.3 Current Realization on Claude Code

### 4.3.1 Agent Definition File Format (Native Primitive)

Agent definition files reside in `.claude/agents/` with the naming convention `lowercase-hyphenated.md`. The filename (minus `.md`) must match the `name` field in the YAML frontmatter. Claude Code discovers agents by scanning this directory automatically -- no registration step is required.

Each file has two parts: YAML frontmatter (fenced by `---` delimiters) defining configuration, and a markdown body defining behavioral protocol.

### 4.3.2 Complete Frontmatter Schema (Native Primitive)

The frontmatter supports 8 fields. Claude Code parses these and applies them when the agent spawns.

| Field | Type | Required | Default | Purpose |
|-------|------|----------|---------|---------|
| `name` | string (lowercase-hyphenated) | YES | -- | Unique identifier; must match filename. Used for routing when `subagent_type` matches this value. |
| `description` | string (multi-line via `>`) | YES | -- | Third-person description of what the agent does and when to use it. Used by Claude Code for discovery and the orchestrator for dispatch decisions. |
| `tools` | array of strings | NO | all tools | Explicit allowlist of tools the agent can use. When specified, the agent can ONLY use listed tools. |
| `permissionMode` | string enum: `"default"` or `"plan"` | NO | `"default"` | `default` = read/write filesystem access. `plan` = read-only (cannot write, edit, or create files). |
| `model` | string enum: `"sonnet"`, `"opus"`, `"haiku"`, `"inherit"`, or model ID | NO | inherits parent model | Which model runs the agent. Omitting is equivalent to `"inherit"`. |
| `skills` | string or array of strings | NO | none | Preloads skill content into agent context at startup. The agent does NOT need to call the Skill tool for preloaded skills. |
| `hooks` | object (nested YAML) | NO | none | Agent-scoped hook registrations. Identical structure to `settings.json` hooks but fires only for this agent. |
| `maxTurns` | integer | NO | Claude Code default | Maximum tool-use turns before forced return. Prevents runaway agents. |

**Current usage across all 14 agents:**

- `name` and `description`: Set by all 14 agents.
- `tools`: Set by all 14 agents (DAAF always specifies explicitly for clarity, even though omission would grant all tools).
- `permissionMode`: Set by all 14. Nine use `default`; five use `plan`.
- `model`: Set by only 1 agent (`search-agent` sets `model: inherit` as documentation intent). All others omit it, inheriting the parent model implicitly.
- `skills`: Set by 13 of 14 agents. Only `search-agent` omits it (loads skills on demand per task).
- `hooks`: Set by 4 agents (all register `enforce-file-first.sh`).
- `maxTurns`: Not set by any DAAF agent.

### 4.3.3 The 12-Section Agent Body Template (DAAF-Built)

The markdown body below the frontmatter is injected as the agent's system-level instructions. DAAF mandates a 12-section structure defined in `agent_reference/AGENT_TEMPLATE.md`:

| # | Section | Purpose |
|---|---------|---------|
| 1 | Title and Purpose | H1 title, one-sentence purpose, invocation type |
| 2 | Identity and Philosophy | Role definition, philosophy maxim, Core Distinction table |
| 3 | Upstream Inputs | Input table with orchestrator checklist (wrapped in `<upstream_input>` tags) |
| 4 | Core Behaviors | 3-7 numbered behavioral principles |
| 5 | Execution Protocol | Sequential steps and decision points |
| 6 | Output Format | Status, Confidence, Learning Signal, Recommendations |
| 7 | Downstream Consumers | Consumer table with severity-to-action mapping (wrapped in `<downstream_consumer>` tags) |
| 8 | Boundaries and Error Handling | Always/Ask/Never tiers plus STOP Conditions |
| 9 | Anti-Patterns | 4-column table (minimum 5 rows, wrapped in `<anti_patterns>` tags) |
| 10 | Quality and Completion | COMPLETE/INCOMPLETE criteria plus Self-Check |
| 11 | Invocation Pattern | `subagent_type` reference and link to WORKFLOW files |
| 12 | References | On-demand reference files (conditional: only when external files are referenced) |

**Size constraints**: Target 400-700 lines per agent file. Hard limit of 1000 lines. Current agents range from ~560 lines (`source-researcher.md`) to ~1,340 lines (`code-reviewer.md`). The body is injected into the agent's context window, so excessively long bodies reduce available context for actual work.

**Token efficiency rules**: Be deliberate about every token. Minimize inline code blocks (extract to `agent_reference/` if shared). No duplicated content. One example per pattern. Core Behaviors should be principles, not essays.

### 4.3.4 Dispatch Mechanics (Hybrid)

**The Agent/Task tool call** (Native Primitive): Agents are dispatched via the `Agent` tool (or equivalently `Task`). The tool accepts these parameters:

| Parameter | Type | Required | Purpose |
|-----------|------|----------|---------|
| `description` | string | Yes | Short summary shown in UI/logs (3-5 words) |
| `prompt` | string | Yes | Full text prompt sent to the subagent as its task |
| `subagent_type` | string | Yes | Routes to a named agent file or a generic type |
| `model` | string | No | Override model for this invocation (not used by DAAF) |
| `run_in_background` | boolean | No | Run in background (BLOCKED by DAAF hook) |

**Name-to-file routing** (Native Primitive): When `subagent_type` matches an agent's `name` field, Claude Code loads the full definition:

```
subagent_type: "research-executor"
  -> scans .claude/agents/
  -> finds research-executor.md (name: research-executor)
  -> applies frontmatter (tools, permissionMode, skills, hooks)
  -> injects body as system instructions
  -> delivers orchestrator's prompt as task
```

For generic types (`general-purpose`, `Plan`, `Explore`), Claude Code uses built-in definitions rather than `.md` files.

**DAAF's standardized prompt structure** (DAAF-Built): Every subagent invocation follows a template defined in the WORKFLOW_PHASE reference files:

1. `**BASE_DIR:**` declaration (mandatory in every DAAF subagent prompt)
2. Skill loading instructions (for skills NOT preloaded via frontmatter)
3. Context from Plan.md (methodology, research question)
4. Task specification (often in XML `<task>` blocks with `depends_on`, `skill`, `agent`, `files`, `action`, `verify`, `done` elements)
5. File-first execution instructions (Stages 5-8)
6. Output format directives with hard word cap

### 4.3.5 Context Composition at Spawn (Native Primitive + DAAF Protocol)

When a subagent spawns, it receives a layered context:

| Layer | Source | Content |
|-------|--------|---------|
| 1 | Claude Code auto-injection | `CLAUDE.md` project instructions (all agents inherit these) |
| 2 | Agent definition file | Frontmatter settings applied + markdown body as system instructions |
| 3 | Frontmatter `skills` field | Preloaded skill content injected before execution begins |
| 4 | Orchestrator's `prompt` parameter | Task specification, context from Plan.md, file paths, output format |

**What a subagent does NOT inherit:**

- Parent conversation history (each agent gets a fresh ~200K-token context)
- Orchestrator's loaded skills (skills add 5K-20K tokens each; having subagents load them keeps the cost in the subagent's disposable context)
- Other subagents' results (the orchestrator must explicitly include any cross-agent context in the prompt)
- Parent's context utilization or state (the subagent starts fresh)

**Critical implication**: Because subagents do NOT inherit conversation history, the orchestrator must provide ALL necessary context in the `prompt` parameter. This is why DAAF's invocation templates are detailed -- they inline Plan.md excerpts, task specifications, prior findings, and file paths.

### 4.3.6 Subagent Return Mechanics (Hybrid)

**Native behavior**: Subagents return results by producing their final text output. The orchestrator receives this as the return value of the Agent tool call.

**DAAF-imposed discipline**:

- Hard cap: 2,000 words maximum for most agents (3,500 for `data-ingest`)
- Returns must follow the structured Output Format (Status, Confidence, Learning Signal, Recommendations)
- Script files on disk are the archive; the agent return is the signal
- The orchestrator processes returns via a 5-step protocol: verify format, write to disk (for discovery agents as preliminary notes), extract key findings, discard verbose content, store summary + file path

### 4.3.7 Permission Modes (Native Primitive, DAAF-Configured)

Two modes enforce filesystem access at the runtime level:

| Mode | Filesystem Access | Agent Count | Agents |
|------|------------------|-------------|--------|
| `default` | Full read/write: can create, edit, delete files | 9 | research-executor, code-reviewer, data-planner, debugger, data-ingest, framework-engineer, notebook-assembler, report-writer, research-synthesizer |
| `plan` | Read-only: can read files and run read-only bash commands; CANNOT write, edit, or create files | 5 | data-verifier, integration-checker, plan-checker, search-agent, source-researcher |

The `plan` mode enforces read-only access at the runtime level -- it is not merely an instruction. Even if a `plan`-mode agent attempted to use `Write` or `Edit`, the runtime would block it. DAAF correctly omits `Write` and `Edit` from the `tools` list of all `plan`-mode agents as a belt-and-suspenders measure. Note that `Bash` IS granted to `plan`-mode agents (for read-only shell commands), but `plan` mode prevents file creation/modification via Bash at the permission layer.

### 4.3.8 Tool-Access Tiers (Hybrid)

Four distinct capability tiers emerge from the `tools` frontmatter field:

| Tier | Tools | Agents | Count |
|------|-------|--------|-------|
| **Full read/write** | Read, Write, Edit, Bash, Glob, Grep, Skill | code-reviewer, data-planner, framework-engineer, notebook-assembler, report-writer, research-executor, research-synthesizer | 7 |
| **Read-only** | Read, Bash, Glob, Grep, Skill | data-verifier, integration-checker, plan-checker, source-researcher | 4 |
| **Read-only + web** | Read, Bash, Glob, Grep, Skill, WebSearch, WebFetch | search-agent | 1 |
| **Full read/write + web** | Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill | data-ingest, debugger | 2 |

`WebSearch` and `WebFetch` are restricted to only 3 agents. This is a deliberate design choice: DAAF prioritizes curated skills over ad-hoc web searches and limits web access to agents with a legitimate need (search tasks, data ingestion from web APIs, error diagnosis requiring documentation lookups).

### 4.3.9 Parallel Dispatch (Native Primitive, DAAF-Governed)

Multiple Agent tool calls in a single response trigger concurrent execution:

- Maximum 5 concurrent subagents (DAAF-imposed convention, enforced by orchestrator workflow instructions)
- All parallel agents must run in foreground (background dispatch is blocked by hook)
- Same-wave tasks dispatch simultaneously; later waves wait for all prior waves to complete
- Example: Stage 3 dispatches multiple `source-researcher` agents in parallel, one per data source

### 4.3.10 Model Selection (Native Primitive, DAAF-Configured)

Model selection follows a precedence chain:

1. Agent tool call `model` parameter (if specified at dispatch time -- DAAF never uses this)
2. Agent frontmatter `model` field (if specified in the `.md` file)
3. Parent model inheritance (if neither is specified, the agent inherits the parent's model)
4. Environment default (the orchestrator's model is set via `ANTHROPIC_MODEL` in `settings.json`)

**Current state**: The orchestrator runs on `claude-opus-4-6[1m]` (set via `settings.json` env var). Only `search-agent` explicitly declares `model: inherit`; all other agents omit the field and inherit implicitly. The practical effect: all 14 agents run on Opus.

### 4.3.11 Generic and Built-In Agent Types (Native Primitive, DAAF-Gated)

Claude Code provides four built-in agent types alongside named agents:

| Generic Type | Capabilities | DAAF Status |
|-------------|-------------|-------------|
| `general-purpose` | Full tool access, file writes, code execution | Used for ad-hoc tasks without a dedicated agent |
| `Plan` | Read-only; can read files but cannot write | Fallback for read-only tasks |
| `Explore` | Read-only, runs on Haiku model | **BLOCKED by DAAF** |
| `claude-code-guide` | Built-in documentation agent, runs on Haiku | **BLOCKED by DAAF** |

### 4.3.12 Hooks That Gate Agent Dispatch (DAAF-Built)

Three PreToolUse hooks registered in `settings.json` fire on every `Agent` and `Task` tool call:

| Hook | What It Blocks | Why |
|------|---------------|-----|
| `enforce-explore-model.sh` | `subagent_type: "Explore"` | Explore agents run on Haiku, which lacks sufficient reasoning depth for DAAF's tasks. Recommends `search-agent` instead. |
| `enforce-foreground-agents.sh` | `run_in_background: true` | Background agents cannot prompt for permissions, causing silent failures. All DAAF agents must run in foreground. |
| `deny-claude-code-guide.sh` | `claude-code-guide` agent | Runs on Haiku with an opaque system prompt incompatible with DAAF's transparency requirements. Recommends `search-agent` + WebFetch instead. |

Each hook reads the tool call JSON from stdin, inspects the relevant field, and outputs a `permissionDecision: "deny"` with a descriptive reason if the condition matches. If no condition matches, they exit 0 (allow).

### 4.3.13 Permission System Interaction (Hybrid)

The `settings.json` allow list explicitly permits certain agent types without user confirmation:

```
Task(general-purpose), Task(Plan), Task(Explore), Task(search-agent)
Agent(general-purpose), Agent(Plan), Agent(Explore), Agent(search-agent)
```

All other named agents (e.g., `research-executor`, `code-reviewer`, `data-planner`) are NOT in the allow list. They prompt the user for permission on first use in a session. This is by design: it gives the researcher visibility into agent spawning while allowing frequently-used generic types to auto-execute.

Note: `Explore` is in the allow list but immediately blocked by the `enforce-explore-model.sh` hook. This means the hook catches it cleanly rather than having it fail at the permission prompt stage.

---

## 4.4 Design Choices and Rationale

### Why Certain Agents Are Read-Only (DAAF Decision)

Five agents operate in `plan` (read-only) mode: `data-verifier`, `integration-checker`, `plan-checker`, `search-agent`, and `source-researcher`. The rationale varies by role:

- **Verification agents** (`data-verifier`, `integration-checker`, `plan-checker`): These agents assess artifacts produced by others. Granting write access would create a conflict of interest -- a verifier that can "fix" what it finds is no longer an independent reviewer. Read-only mode enforces separation of concerns.
- **Research agents** (`source-researcher`, `search-agent`): These agents explore codebases, documentation, and data sources to gather information. They have no legitimate need to modify files, and accidental writes during exploration could corrupt project state.

### Why Explore and claude-code-guide Are Blocked (DAAF Decision)

Claude Code's built-in `Explore` agent type defaults to the Haiku model (Claude's smallest). Haiku lacks the reasoning depth required for DAAF's complex codebase analysis, data interpretation, and methodology decisions. Rather than risk degraded quality from an undersized model, DAAF blocks `Explore` entirely and redirects to `search-agent`, which inherits the orchestrator's Opus model.

The `claude-code-guide` agent is blocked for two reasons: it also runs on Haiku, and its system prompt is opaque (not inspectable by the researcher), violating DAAF's transparency principle.

### Why All Agents Use Opus (DAAF Decision)

DAAF runs every agent on the same model as the orchestrator (currently Opus with 1M context). This ensures uniform reasoning quality across all pipeline stages. The cost is higher per-agent token usage, but the benefit is that no pipeline stage degrades due to model capability mismatch. If an agent produced lower-quality output on a cheaper model, the resulting errors could cascade through downstream stages and cost more to diagnose than the model savings.

### Why Named Agents Are Not Auto-Allowed (DAAF Decision)

Despite being DAAF's own agents, named agents like `research-executor` and `code-reviewer` are NOT in the `settings.json` auto-allow list. Each dispatch prompts the user for confirmation. This maintains the transparency principle: the researcher is always aware when a new specialist is being activated and can inspect the prompt being sent. The researcher's awareness of delegation is a feature, not friction.

### The Structured Output Contract Pattern (DAAF-Built)

Every agent's Output Format section defines a structured return contract (Status, Confidence, Learning Signal, Recommendations). This is not a Claude Code requirement -- it is a DAAF convention that:

- Enables the orchestrator to process returns programmatically (verify format, extract key findings, discard verbose content)
- Provides the researcher with consistent metadata across all agent types
- Supports the learning signal accumulation pipeline (subagent signals buffer in STATE.md, flush to LEARNINGS.md at phase boundaries)

### Why the 2,000-Word Return Cap Exists (DAAF Decision)

Each subagent return consumes orchestrator context. A single verbose return (~4,000 words, ~8,000 tokens) over 10 round-trips in a stage would consume ~80,000 tokens -- a meaningful share of the orchestrator's capacity. The 2,000-word cap forces agents to put detailed findings on disk (as script output, preliminary notes, or data files) and return only the signal the orchestrator needs for coordination. Script files on disk are the archive; the agent return is the signal.

---

## 4.5 Replication Specification

### Required Capabilities in the Target Harness

| Capability | Priority | Specification |
|-----------|----------|---------------|
| Agent definition files | CRITICAL | The harness must support defining named agent types with configurable behavior, tool access, and permissions via files (or equivalent registry). |
| Named agent routing | CRITICAL | A dispatch call specifying an agent name must load and apply that agent's configuration and behavioral protocol. |
| Per-agent tool restriction | HIGH | Each agent must be constrainable to a specific set of tools. An agent without `Write` in its allowlist must be physically unable to write files. |
| Permission modes | HIGH | At least two modes: full read/write and read-only. Read-only must be enforced at the runtime level (not just instructional). |
| Fresh context per agent | CRITICAL | Each dispatched agent must receive an independent context window. Sharing context between agents or between agent and orchestrator breaks DAAF's context budget model. |
| Project-wide instruction inheritance | CRITICAL | An equivalent of CLAUDE.md must be automatically injected into every agent's context. Universal rules (context monitoring, code style, safety) must apply to all agents equally. |
| Skill preloading | HIGH | Agent configuration must support specifying domain knowledge to inject at startup, before the agent begins executing. 13 of 14 DAAF agents use this. |
| Per-agent hook registration | MEDIUM | Agent configuration must support scoped lifecycle hooks that fire only for that agent. 4 DAAF agents use this for file-first execution enforcement. |
| Parallel dispatch | HIGH | The orchestrator must be able to dispatch multiple agents concurrently (at least 5) and receive their results. |
| Pre-dispatch interception | MEDIUM | The harness must support hooks or equivalent that can inspect and block agent dispatch calls before they execute. |
| Model selection per agent | HIGH | Each agent must be able to specify or inherit a model. If the harness defaults all subagents to a weaker model, DAAF's quality assumptions break. |

### Behavioral Contract

**Dispatch**: The orchestrator provides a prompt string and an agent identifier. The harness spawns a new agent context, applies the agent's configuration, injects the agent's protocol and project-wide instructions, and delivers the prompt as the task.

**Return**: The agent produces text output, which the orchestrator receives as the dispatch call's return value. No special return mechanism exists -- the agent's final response IS the return value.

**Isolation**: The agent cannot read the orchestrator's conversation history. The orchestrator cannot read the agent's intermediate tool calls (only the final return). The agent's context is destroyed after it returns.

**Failure modes**: If an agent exceeds its context window, it should return whatever output it has produced rather than failing silently. If an agent is blocked by a pre-dispatch hook, the orchestrator receives an error message explaining why.

### Acceptance Criteria

Feature parity is achieved when:

1. Fifteen named agents can be defined with distinct tool access, permission modes, skill preloading, and behavioral protocols.
2. Dispatching `subagent_type: "research-executor"` loads the `research-executor` agent's full configuration and protocol.
3. A `plan`-mode agent physically cannot write files, even via Bash commands.
4. Each dispatched agent receives a fresh context window with no access to parent conversation history.
5. CLAUDE.md-equivalent project instructions are injected into every agent context.
6. Up to 5 agents can be dispatched concurrently with their results collected by the orchestrator.
7. Pre-dispatch hooks can block specific agent types (e.g., `Explore`, background agents) before they spawn.
8. All agents run on the orchestrator's model unless explicitly overridden.

### Degraded-Mode Options

If full parity is not achievable:

- **No per-agent tool restriction**: Enforce via instructions in the agent protocol rather than runtime restriction. Reduced safety but functional. Combine with post-execution auditing.
- **No permission modes**: Use instructions to prohibit writes. Less reliable -- a "read-only" agent could still accidentally write files. Mitigate with post-execution file-change detection.
- **No parallel dispatch**: Execute agents sequentially. Wave-based parallelism degrades to serial execution; pipeline throughput drops but correctness is unaffected.
- **No fresh context per agent**: This is the most damaging gap. Without context isolation, skill loading and code execution consume the orchestrator's context directly, severely limiting pipeline length. Mitigate by aggressively truncating agent returns and minimizing skill content.

---

## 4.6 Harness Landscape

**Codex (OpenAI)**: Supports custom agents via `agents.md` convention and AGENTS.md. Task isolation with separate containers. No direct equivalent of YAML frontmatter for per-agent tool restriction; would require wrapper logic.

**Cursor**: Supports custom agents/modes with instruction files. Agent context isolation present. Tool restrictions are less granular than Claude Code's per-agent frontmatter. MCP integration available for extending tool access.

**OpenCode**: Supports agents with configurable system prompts and tool access. Context isolation via separate sessions. Hook system present but less mature than Claude Code's.

**Aider/Windsurf**: Limited or no native subagent support. Would require significant wrapper or middleware to implement DAAF's multi-agent architecture.

---

## 4.7 Dependencies

**Depends on:**
- Section 3 (Instruction Loading): CLAUDE.md auto-injection into all agent contexts
- Section 5 (Permission System): `settings.json` allow/deny lists apply to all agents; named agent permission prompts
- Section 6 (Skill System): Frontmatter `skills` field triggers skill preloading; agents invoke Skill tool at runtime
- Section 7 (Hook System): Per-agent `hooks` in frontmatter; project-wide hooks fire for all agents; dispatch-gating hooks

**Feeds into:**
- Section 8 (Context Management): Agent context isolation is the foundation of DAAF's context budget strategy; `context-reporter` fires for all agents
- Section 9 (Logging and Audit Trail): `enforce-file-first.sh` is registered as a per-agent hook on 4 coding agents; `audit-log.sh` records all agent tool calls
- Section 10 (Tool System): Per-agent tool restrictions define the tool matrix; one-command-per-Bash-call rule applies within agents

---

## 4.8 Complete Agent Inventory

The following table provides the full frontmatter specification for all 14 DAAF agents.

| Agent | Permission Mode | Tools | Skills Preloaded | Has Hooks | Description (summarized) |
|-------|----------------|-------|-----------------|-----------|-------------------------|
| `code-reviewer` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | data-scientist | Yes (enforce-file-first) | QA review of executed scripts; methodology alignment; output quality |
| `data-ingest` | `default` | Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill | data-scientist | Yes (enforce-file-first) | Systematic dataset profiling across four structured parts |
| `data-planner` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | data-scientist | No | Research plan and executable task sequence creation |
| `data-verifier` | `plan` | Read, Bash, Glob, Grep, Skill | data-scientist | No | Adversarial goal-backward verification of completed analyses |
| `debugger` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill, WebFetch, WebSearch | data-scientist | Yes (enforce-file-first) | Data quality and analysis failure diagnosis |
| `framework-engineer` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | skill-authoring, agent-authoring | No | Framework artifact authoring with template compliance |
| `integration-checker` | `plan` | Read, Bash, Glob, Grep, Skill | data-scientist | No | Data flow tracing and reference validation |
| `notebook-assembler` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | data-scientist, marimo | No | Script compilation into Marimo notebooks |
| `plan-checker` | `plan` | Read, Bash, Glob, Grep, Skill | data-scientist | No | Research plan verification across six dimensions |
| `report-writer` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | data-scientist | No | Stakeholder report synthesis from pipeline artifacts |
| `research-executor` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | data-scientist | Yes (enforce-file-first) | Data acquisition, cleaning, transformation, visualization |
| `research-synthesizer` | `default` | Read, Write, Edit, Bash, Glob, Grep, Skill | data-scientist | No | Multi-source finding consolidation and conflict resolution |
| `search-agent` | `plan` | Read, Bash, Glob, Grep, Skill, WebSearch, WebFetch | *(none)* | No | Read-only exploration of codebases, docs, datasets, web |
| `source-researcher` | `plan` | Read, Bash, Glob, Grep, Skill | data-scientist | No | Deep-dive investigation of single data sources |

**Key patterns visible in the inventory:**

- `data-scientist` is preloaded by 12 of 14 agents. It provides baseline data science methodology that nearly every role requires.
- `framework-engineer` is the only agent with non-data-scientist skills (`skill-authoring` + `agent-authoring`), reflecting its unique meta-development role.
- `notebook-assembler` preloads two skills (`data-scientist` + `marimo`), combining domain methodology with the notebook framework.
- `search-agent` preloads no skills. It loads them on demand based on the search task, keeping its base context lean for maximum flexibility.
- Only 4 agents register per-agent hooks, all for the same hook (`enforce-file-first.sh`). These are the four agents that write and execute Python scripts via `run_with_capture.sh`: `code-reviewer`, `data-ingest`, `debugger`, and `research-executor`.
- `model: inherit` is explicitly set only by `search-agent` -- as documentation intent, making clear that this agent (which replaced the blocked Explore type) inherits Opus rather than defaulting to a cheaper model.

### Layered Permission Architecture

The agent system creates a multi-layered permission evaluation chain. For a `research-executor` running a Bash command, the evaluation proceeds:

1. `tools` field: Agent has `Bash` in its allowlist -- tool call is permitted
2. `permissionMode`: Agent is `default` -- file writes are permitted
3. `settings.json` allow list: `Bash(bash *)` matches -- auto-approved without user prompt
4. Agent frontmatter hook: `enforce-file-first.sh` fires on `Bash` matcher -- blocks direct `python` execution
5. Project-wide hook: `bash-safety.sh` fires on `Bash` matcher -- blocks destructive commands
6. If all checks pass: command executes

This layered architecture means that no single failure point can bypass all protections. Even if an instruction is ignored, the hooks enforce the rules programmatically. Even if a hook fails, the permission mode constrains the blast radius.
