# Finding 02: Agent System — Frontmatter, Dispatch, and Model Selection

> **Scope:** How DAAF defines, dispatches, configures, and constrains specialized subagents within Claude Code's agent framework.
>
> **Source files examined:** All 15 agent `.md` files in `.claude/agents/`, `agent_reference/AGENT_TEMPLATE.md`, `.claude/skills/agent-authoring/SKILL.md`, `.claude/settings.json`, `.claude/hooks/enforce-explore-model.sh`, `.claude/hooks/enforce-foreground-agents.sh`, `.claude/hooks/deny-claude-code-guide.sh`, `.claude/hooks/enforce-file-first.sh`, `.claude/skills/daaf-orchestrator/SKILL.md`, `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md`, `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md`, `agent_reference/WORKFLOW_PHASE3_ACQUISITION.md`.

---

## 1. Agent Definition File Format

### 1.1 File Location and Naming

Agent definition files live in `.claude/agents/` with the naming convention `lowercase-hyphenated.md`. The filename (minus extension) must match the `name` field in YAML frontmatter. Claude Code discovers agents by scanning this directory.

**Current inventory (15 agents):**

| File | Name | Permission Mode | Has Hooks |
|------|------|----------------|-----------|
| `code-reviewer.md` | `code-reviewer` | `default` | Yes |
| `data-ingest.md` | `data-ingest` | `default` | Yes |
| `data-planner.md` | `data-planner` | `default` | No |
| `data-verifier.md` | `data-verifier` | `plan` | No |
| `debugger.md` | `debugger` | `default` | Yes |
| `framework-engineer.md` | `framework-engineer` | `default` | No |
| `integration-checker.md` | `integration-checker` | `plan` | No |
| `notebook-assembler.md` | `notebook-assembler` | `default` | No |
| `plan-checker.md` | `plan-checker` | `plan` | No |
| `report-writer.md` | `report-writer` | `default` | No |
| `research-executor.md` | `research-executor` | `default` | Yes |
| `research-synthesizer.md` | `research-synthesizer` | `default` | No |
| `search-agent.md` | `search-agent` | `plan` | No |
| `source-researcher.md` | `source-researcher` | `plan` | No |

A companion `README.md` file in the same directory serves as the canonical agent index/catalog but is not an agent definition itself.

---

### 1.2 Complete YAML Frontmatter Schema

The frontmatter is fenced by `---` delimiters at the top of the file, following standard YAML front matter conventions. Here is the complete schema based on every field observed across all 15 agents plus the `AGENT_TEMPLATE.md` specification:

```yaml
---
# ── REQUIRED FIELDS ────���───────────────────────���─────────────────────────

name: agent-name-here
# Type: string (lowercase-hyphenated)
# Purpose: Unique identifier. Must match filename (minus .md extension).
# Used by: Claude Code's agent routing — when `subagent_type` in an Agent
#          tool call matches this value, Claude Code loads this file.
# Required: YES — every agent file must have this.

description: >
  Third-person description of what the agent does AND when to use it.
# Type: string (multi-line folded scalar via `>`)
# Purpose: Claude Code uses this for agent discovery and routing decisions.
#          The orchestrator also reads it for dispatch decisions.
# Convention: Must be third person ("Reviews scripts..." not "Review scripts").
#             Must include WHAT the agent does AND WHEN to use it.
# Required: YES

tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
# Type: array of strings
# Purpose: Explicit allowlist of tools the agent can use. When specified,
#          the agent can ONLY use the listed tools. Omitting this field
#          grants access to all tools.
# Known tool names: Read, Write, Edit, Bash, Glob, Grep, Skill,
#                   WebSearch, WebFetch
# Required: NO (but DAAF always specifies it for explicitness)

permissionMode: default
# Type: string enum
# Values:
#   "default" — agent can read AND write files, execute code
#   "plan"    — agent is READ-ONLY; cannot write/edit/create files
# Purpose: Controls the agent's filesystem permissions.
# Required: NO (defaults to "default" if omitted, per Claude Code behavior)


# ── OPTIONAL FIELDS ───────────��──────────────────────────────────────────

model: inherit
# Type: string enum
# Values: "sonnet", "opus", "haiku", "inherit", or specific model IDs
# Purpose: Specifies which model runs the agent. "inherit" means use the
#          parent's model (the invoking orchestrator's model).
# Default when omitted: The agent runs on the SAME model as the parent
#          (effectively "inherit"). In DAAF's case, the orchestrator runs
#          on claude-opus-4-6[1m] (set via ANTHROPIC_MODEL env var in
#          settings.json), so all agents without explicit model fields
#          also run on Opus.
# Current usage: ONLY `search-agent` explicitly sets `model: inherit`.
#          All other agents omit this field (and thus also inherit).
# Required: NO

maxTurns: 50
# Type: integer
# Purpose: Limits the number of tool-use turns the agent can take before
#          it must return. Prevents runaway agents.
# Default: Claude Code's default (not explicitly set in any DAAF agent)
# Current usage: NO DAAF agent currently sets this field.
# Required: NO

skills: skill-name
# Type: string (single skill) or array of strings (multiple skills)
# Purpose: Preloads skill content into the agent's context at startup.
#          The full skill SKILL.md content is injected BEFORE the agent
#          begins executing. The agent does NOT need to call the Skill
#          tool for preloaded skills — doing so would load the content
#          a second time and waste context tokens.
# Syntax variants:
#   Single:   skills: data-scientist
#   Multiple: skills:
#               - skill-authoring
#               - agent-authoring
# Current usage: See Section 1.3 below.
# Required: NO

memory: project
# Type: string enum
# Values: "user", "project", "local"
# Purpose: Controls the agent's access to Claude Code's memory system.
# Current usage: NO DAAF agent currently sets this field.
#          (DAAF disables auto-memory entirely via
#          CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 in settings.json)
# Required: NO

hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/hook-name.sh"
          timeout: 5
# Type: object (nested YAML structure mirroring settings.json hook format)
# Purpose: Registers hooks that fire ONLY when this specific agent is
#          active. Distinct from project-wide hooks in settings.json.
# Structure: Identical to settings.json hook registration but scoped to
#            the agent. Uses hook lifecycle events (PreToolUse, PostToolUse,
#            etc.) with matchers and command hooks.
# Current usage: See Section 1.4 below.
# Required: NO
---
```

### 1.3 Skills Preloading — Current Assignments

| Agent | Preloaded Skills |
|-------|-----------------|
| `code-reviewer` | `data-scientist` |
| `data-ingest` | `data-scientist` |
| `data-planner` | `data-scientist` |
| `data-verifier` | `data-scientist` |
| `debugger` | `data-scientist` |
| `framework-engineer` | `skill-authoring`, `agent-authoring` |
| `integration-checker` | `data-scientist` |
| `notebook-assembler` | `data-scientist`, `marimo` |
| `plan-checker` | `data-scientist` |
| `report-writer` | `data-scientist` |
| `research-executor` | `data-scientist` |
| `research-synthesizer` | `data-scientist` |
| `search-agent` | *(none)* |
| `source-researcher` | `data-scientist` |

Key observations:
- `data-scientist` is preloaded by 13 of 15 agents (all except `search-agent` and `framework-engineer`).
- `framework-engineer` preloads two domain-specific skills (`skill-authoring` and `agent-authoring`) instead.
- `notebook-assembler` preloads two skills (`data-scientist` + `marimo`).
- `search-agent` preloads no skills — it loads them on-demand based on the search task.

### 1.4 Per-Agent Hooks — Current Assignments

Only 4 agents register per-agent hooks, all for the same hook (`enforce-file-first.sh`):

| Agent | Hook | Matcher | Purpose |
|-------|------|---------|---------|
| `code-reviewer` | `enforce-file-first.sh` | `Bash` | Blocks direct `python`/`python3` execution |
| `data-ingest` | `enforce-file-first.sh` | `Bash` | Blocks direct `python`/`python3` execution |
| `debugger` | `enforce-file-first.sh` | `Bash` | Blocks direct `python`/`python3` execution |
| `research-executor` | `enforce-file-first.sh` | `Bash` | Blocks direct `python`/`python3` execution |

**The hook registration syntax** (identical across all four):
```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

**Selection criteria:** Any agent that writes and executes Python scripts via `run_with_capture.sh` must register this hook. Read-only agents (`permissionMode: plan`), agents that don't execute Python (`report-writer`, `notebook-assembler`), and the orchestrator itself do not need it.

### 1.5 Tools Allowlist — Patterns Across Agents

Three distinct capability tiers emerge from the `tools` field:

| Tier | Tools | Agents | Count |
|------|-------|--------|-------|
| **Full read/write** | `[Read, Write, Edit, Bash, Glob, Grep, Skill]` | code-reviewer, data-planner, framework-engineer, notebook-assembler, report-writer, research-executor, research-synthesizer | 7 |
| **Read-only** | `[Read, Bash, Glob, Grep, Skill]` | data-verifier, integration-checker, plan-checker, source-researcher | 4 |
| **Read-only + web** | `[Read, Bash, Glob, Grep, Skill, WebSearch, WebFetch]` | search-agent | 1 |
| **Full read/write + web** | `[Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill]` | data-ingest, debugger | 2 |

Note that `Write` and `Edit` are never granted to `plan`-mode agents. The `Bash` tool IS granted to `plan`-mode agents (they can run read-only bash commands), but `plan` mode prevents file creation/modification at the permission layer regardless of tool access.

`WebSearch` and `WebFetch` are restricted to 3 agents: `search-agent`, `data-ingest`, and `debugger`.

---

## 2. Agent Body Content

### 2.1 What Goes Below the Frontmatter

The markdown body below the YAML frontmatter is the **agent protocol definition** — Claude Code injects this as system-level instructions for the subagent when it is spawned. The body defines the agent's identity, behavioral rules, execution protocol, output format, boundaries, and quality standards.

### 2.2 How Claude Code Uses the Body

When `subagent_type` in an Agent tool call matches an agent's `name` field, Claude Code:
1. Loads the agent's `.md` file
2. Applies the frontmatter settings (tools, permissionMode, model, skills, hooks)
3. Injects the markdown body as the agent's system prompt / behavioral instructions
4. Injects any preloaded skill content (from the `skills` field)
5. Then delivers the orchestrator's `prompt` text as the user message / task

The agent body is therefore **the behavioral contract** — it defines what the agent does, how it operates, what it can and cannot do, and what format its output must take.

### 2.3 Mandatory Body Sections (AGENT_TEMPLATE.md)

DAAF mandates 12 sections in every agent body, per `agent_reference/AGENT_TEMPLATE.md`:

| # | Section | Required | Tag Wrapper | Purpose |
|---|---------|----------|-------------|---------|
| 1 | Title and Purpose | REQUIRED | — | H1 title + one-sentence purpose + invocation type |
| 2 | Identity and Philosophy | REQUIRED | — | Role definition, philosophy maxim, Core Distinction table |
| 3 | Upstream Inputs | REQUIRED | `<upstream_input>` | Input table + orchestrator checklist |
| 4 | Core Behaviors | REQUIRED | — | 3-7 numbered behavioral principles |
| 5 | Execution Protocol | REQUIRED | �� | Sequential steps + decision points |
| 6 | Output Format | REQUIRED | — | Status, Confidence, Learning Signal, Recommendations |
| 7 | Downstream Consumers | REQUIRED | `<downstream_consumer>` | Consumer table + severity-to-action mapping |
| 8 | Boundaries and Error Handling | REQUIRED | — | Always/Ask/Never tiers + STOP Conditions |
| 9 | Anti-Patterns | REQUIRED | `<anti_patterns>` | 4-column table (min 5 rows) |
| 10 | Quality and Completion | REQUIRED | — | COMPLETE/INCOMPLETE criteria + Self-Check |
| 11 | Invocation Pattern | REQUIRED | — | `subagent_type` reference + link to WORKFLOW files |
| 12 | References | CONDITIONAL | — | On-demand reference files (only when agent references external files) |

### 2.4 Practical Size Limits

- **Target length:** 400-700 lines per agent file
- **Hard limit:** Never exceed 1000 lines
- Current agents range from ~560 lines (`source-researcher.md` at 22,488 bytes) to ~1,340 lines (`code-reviewer.md` at 53,457 bytes — the largest agent)
- The body is injected into the agent's context window, consuming tokens. Excessively long bodies reduce the agent's available context for actual work.
- The agent's context window is described as "fresh 200K-token context" per subagent launch.

### 2.5 Token Efficiency Rules for Bodies

From AGENT_TEMPLATE.md:
1. Be deliberate about every token
2. Minimize large inline code blocks — extract to `agent_reference/` if shared across agents
3. No duplicate content — reference `agent_reference/` files, don't copy
4. One example per pattern; link additional examples
5. Core Behaviors should be principles (2-5 sentences each), not essays

---

## 3. Agent Dispatch Mechanics

### 3.1 The Agent Tool Call Structure

Agents are invoked via the `Agent` tool (or equivalently `Task` tool — both appear in settings.json permission lists). The tool call structure uses these parameters:

```python
Agent({
    description: "[3-5 word summary]",
    prompt: """[The full prompt/instructions for the subagent]""",
    subagent_type: "[agent-name]"
})
```

**Parameters observed in DAAF usage:**

| Parameter | Type | Required | Purpose |
|-----------|------|----------|---------|
| `description` | string | Yes | Short summary shown in UI/logs (3-5 words) |
| `prompt` | string | Yes | The full text prompt sent to the subagent as its task |
| `subagent_type` | string | Yes | Routes to a named agent file OR a generic type |
| `model` | string | No | Override the model for this invocation (not used by DAAF) |
| `run_in_background` | boolean | No | Run agent in background (BLOCKED by DAAF hooks — see Section 3.6) |

**Note on `isolation`:** This parameter is referenced in the system prompt's Agent tool description but is not used by DAAF. All DAAF agents run in their own fresh context.

### 3.2 How the Orchestrator's Prompt Combines with the Agent's Body

The combination works in layers:

1. **Agent body** (from `.md` file) → injected as system-level behavioral instructions
2. **Preloaded skills** (from `skills` frontmatter) → injected into agent context at startup
3. **CLAUDE.md** (project instructions) → also injected into the agent's context (all agents in a project inherit the project's `CLAUDE.md`)
4. **Orchestrator's `prompt`** → delivered as the task/user message

The orchestrator's prompt typically contains:
- `**BASE_DIR:**` declaration (mandatory in every DAAF subagent prompt)
- Skill loading instructions (for skills NOT preloaded via frontmatter)
- Context from Plan.md (methodology, research question)
- Task specification (often in XML `<task>` blocks)
- Output format directives
- Stage-specific emphasis

### 3.3 Context Inheritance

**What a subagent inherits from the parent:**

| Aspect | Inherited? | Details |
|--------|-----------|---------|
| CLAUDE.md | YES | Project instructions are injected into all agent contexts |
| Conversation history | NO | Each agent gets a fresh context window |
| Parent's context/memory | NO | Agents start fresh — "Each subagent gets fresh 200K-token context (no degradation)" |
| settings.json hooks | YES | Project-wide hooks (e.g., `bash-safety.sh`, `context-reporter.sh`) fire for all agents |
| settings.json permissions | YES | The project's allow/deny lists apply to all agents |
| Agent-specific hooks | SCOPED | Only fire for the agent that declares them in frontmatter |
| Environment variables | YES | `settings.json` env vars (ANTHROPIC_MODEL, etc.) are inherited |

**Critical implication:** Because subagents do NOT inherit conversation history, the orchestrator must provide ALL necessary context in the `prompt` parameter. This is why DAAF's invocation templates are so detailed — they inline Plan.md excerpts, task specifications, prior findings, and file paths.

### 3.4 How Subagents Return Results

Subagents return results by simply producing their final text output. The orchestrator receives this as the return value of the Agent tool call. There is no special return mechanism — the agent's last response IS the return value.

DAAF imposes discipline on returns:
- **Hard cap: 2,000 words maximum** for most agents (3,500 for `data-ingest`)
- Script files on disk are the archive; the agent return is the signal
- Returns must follow the agent's Output Format (Status, Confidence, Learning Signal, etc.)
- The orchestrator processes returns via a 5-step protocol: verify format → write to disk (for discovery agents) → extract key findings → discard verbose content → store summary + file path

### 3.5 Sub-Subagent Spawning

**Can subagents spawn sub-subagents?** Yes — Claude Code's Agent tool is available to any agent that has it in their `tools` list. However:

- DAAF does not explicitly use nested sub-subagents in its documented patterns
- The `Agent` and `Task` tool types appear in the project-wide `settings.json` allow list, meaning any agent with general tool access could theoretically dispatch sub-subagents
- The practical limit is context: each nested agent gets its own 200K context, but the parent must wait for the child to complete and the child's return consumes parent context
- DAAF enforces a **maximum of 5 concurrent subagents** at the orchestrator level (sub-batch into groups of ≤5)
- Background agents are blocked by the `enforce-foreground-agents.sh` hook

### 3.6 Hooks that Gate Agent Dispatch

Three hooks in `settings.json` fire on every `Agent` and `Task` tool call (via `PreToolUse` matcher):

| Hook | Matcher | What It Does |
|------|---------|-------------|
| `enforce-explore-model.sh` | `Agent`, `Task` | **BLOCKS** any agent with `subagent_type: "Explore"`. Explore agents run on Haiku (insufficient reasoning depth). Recommends `search-agent` instead. |
| `enforce-foreground-agents.sh` | `Agent`, `Task` | **BLOCKS** any agent with `run_in_background: true`. Background agents cannot prompt for permissions, causing silent failures. |
| `deny-claude-code-guide.sh` | `Agent`, `Task` | **BLOCKS** the built-in `claude-code-guide` agent. It runs on Haiku with an opaque system prompt incompatible with DAAF's transparency requirements. Recommends `search-agent` + WebFetch instead. |

**Hook mechanism:** Each hook reads the tool call JSON from stdin, inspects `tool_input.subagent_type` or `tool_input.run_in_background`, and outputs a JSON `permissionDecision: "deny"` with a descriptive reason if the condition matches. If no condition matches, they exit 0 (allow).

### 3.7 Permission System Interaction with Agent Dispatch

The `settings.json` allow list explicitly permits certain agent types without user confirmation:

```json
"Task(general-purpose)",
"Task(Plan)",
"Task(Explore)",
"Task(search-agent)",
"Agent(general-purpose)",
"Agent(Plan)",
"Agent(Explore)",
"Agent(search-agent)"
```

**Important:** Only `general-purpose`, `Plan`, `Explore`, and `search-agent` are in the allow list. All other named agents (e.g., `research-executor`, `code-reviewer`, `data-planner`) are NOT in the allow list, meaning they will prompt the user for permission on first use in a session. This is by design — it gives the user visibility into agent spawning while allowing frequently-used generic types to auto-execute.

Note: `Explore` is in the allow list but immediately blocked by the `enforce-explore-model.sh` hook — this means the hook catches it cleanly rather than having it fail at the permission prompt stage.

---

## 4. Model Selection and Inheritance

### 4.1 How Model Selection Works

Model selection follows a precedence chain:

1. **Agent tool call `model` parameter** — if specified in the dispatch call, this takes effect (DAAF never uses this)
2. **Agent frontmatter `model` field** — if specified in the agent's `.md` file
3. **Parent model inheritance** — if neither is specified, the agent inherits the parent's model
4. **Environment default** — the orchestrator's model is set via `ANTHROPIC_MODEL` env var in `settings.json`

### 4.2 Current Model Configuration

**Orchestrator model:** `claude-opus-4-6[1m]` (set via `settings.json` env var `ANTHROPIC_MODEL`)

**Agent model specifications:**

| Agent | Frontmatter `model` | Effective Model |
|-------|---------------------|-----------------|
| `search-agent` | `inherit` | `claude-opus-4-6[1m]` (explicitly inherits from parent) |
| All other 14 agents | *(not specified)* | `claude-opus-4-6[1m]` (implicit inheritance) |

**Key finding:** Only ONE agent (`search-agent`) explicitly declares `model: inherit`. All other agents omit the field entirely. The practical effect is identical — all agents run on the same model as the orchestrator (Opus). The explicit `inherit` on `search-agent` appears to be documentation intent: making it clear that this agent (which replaced the now-blocked Explore type that ran on Haiku) inherits the main Opus model.

### 4.3 The Explore/Haiku Problem (Why Model Matters)

DAAF's model selection design was shaped by a specific failure mode with Claude Code's built-in `Explore` subagent type:

- `Explore` agents automatically run on the **Haiku** model (Claude's smallest/fastest model)
- Haiku lacks sufficient reasoning depth for DAAF's complex codebase analysis tasks
- DAAF blocks `Explore` via hook (`enforce-explore-model.sh`) and redirects to `search-agent` which inherits Opus
- Similarly, the built-in `claude-code-guide` agent runs on Haiku and is blocked (`deny-claude-code-guide.sh`)

**Implication for migration:** The target harness must support model selection per agent. If the harness defaults all subagents to a weaker model, DAAF's quality assumptions break. Named agents must be able to specify or inherit the orchestrator's model.

### 4.4 Model Override at Dispatch Time

The Agent tool accepts a `model` parameter that could override the agent's frontmatter. DAAF never uses this feature — all model selection is static (via frontmatter or inheritance). However, the capability exists in Claude Code for dynamic model routing if needed.

### 4.5 Available Model Values

From AGENT_TEMPLATE.md, the documented options are:
- `sonnet` — Claude Sonnet (mid-tier)
- `opus` — Claude Opus (highest tier)
- `haiku` — Claude Haiku (fastest/smallest)
- `inherit` — use the parent's model
- Specific model ID strings are also possible (e.g., `claude-opus-4-6[1m]`)

---

## 5. Permission Modes

### 5.1 Available Modes

| Mode | Filesystem Access | Who Uses It |
|------|------------------|-------------|
| `default` | Full read/write — can create, edit, and delete files | research-executor, code-reviewer, data-planner, debugger, data-ingest, framework-engineer, notebook-assembler, report-writer, research-synthesizer (9 agents) |
| `plan` | Read-only — can read files and run read-only bash commands; CANNOT write, edit, or create files | data-verifier, integration-checker, plan-checker, search-agent, source-researcher (5 agents) |

### 5.2 How Permission Modes Interact with Tools and settings.json

Permission modes create a **layered permission system**:

1. **`permissionMode`** — coarse-grained: `default` (read/write) vs `plan` (read-only)
2. **`tools` allowlist** — medium-grained: which tools the agent can use at all
3. **`settings.json` allow/deny lists** — fine-grained: which specific tool invocations are auto-allowed, denied, or require user confirmation

**The interaction:**
- `plan` mode prevents file writes even if `Write` and `Edit` appear in the tools list (they don't — DAAF correctly omits them from `plan`-mode agents)
- `settings.json` deny rules apply to ALL agents regardless of permission mode (e.g., `rm -rf`, credential file reads are denied for everyone)
- `settings.json` allow rules auto-approve matching tool calls for all agents (e.g., `Bash(ls *)`, `Grep`, `Glob`)
- Per-agent hooks (frontmatter `hooks`) add agent-specific constraints on top of project-wide settings

**Example interaction chain for `research-executor` running a bash command:**
1. Agent has `Bash` in `tools` → allowed to attempt Bash calls
2. Agent has `permissionMode: default` → can write files
3. `settings.json` `Bash(bash *)` is in allow list → auto-approved
4. Agent's frontmatter hook `enforce-file-first.sh` fires (PreToolUse on Bash) → blocks direct `python` execution
5. Project-wide hook `bash-safety.sh` fires (PreToolUse on Bash) → blocks destructive commands
6. If the command passes all checks → executes

### 5.3 The DAAF Permission Architecture

```
+-------------------------------------------------------------+
|                    settings.json                             |
|  +--------------+  +--------------+  +------------------+   |
|  |  allow list   |  |  deny list   |  |  project hooks   |  |
|  | (auto-approve |  | (hard block) |  | (all agents)     |  |
|  |  matching)    |  |              |  |  - bash-safety    |  |
|  +--------------+  +--------------+  |  - context-reporter| |
|                                       |  - audit-log      |  |
|                                       |  - output-scanner |  |
|                                       |  - enforce-explore |  |
|                                       |  - enforce-fg     |  |
|                                       |  - deny-guide     |  |
|                                       +------------------+   |
+-------------------------------------------------------------+
                          | applies to all agents
+-------------------------------------------------------------+
|                Agent Definition (.md)                         |
|  +--------------+  +--------------+  +------------------+   |
|  | permissionMode|  | tools list   |  | per-agent hooks  |  |
|  | default|plan  |  | [Read,Bash..]|  | enforce-file-    |  |
|  |               |  |              |  | first.sh         |  |
|  +--------------+  +--------------+  +------------------+   |
+-------------------------------------------------------------+
```

---

## 6. Subagent Type System

### 6.1 Named Agents vs. Generic Types

Claude Code supports two categories of subagent types:

**Named agents** — defined by `.md` files in `.claude/agents/`. When `subagent_type` matches an agent's `name` field, Claude Code loads that agent's full definition (frontmatter settings + body protocol).

**Generic/built-in types** — predefined by Claude Code itself:

| Generic Type | Capabilities | DAAF Usage |
|-------------|-------------|------------|
| `general-purpose` | Full tool access, file writes, code execution | Used for ad-hoc tasks without a dedicated agent (e.g., Stage DI-7 skill authoring) |
| `Plan` | Read-only; can read files and make data access calls but CANNOT write | Fallback for read-only tasks when `search-agent` is not suitable |
| `Explore` | Read-only, runs on Haiku model | **BLOCKED by DAAF** — insufficient reasoning depth |
| `claude-code-guide` | Built-in documentation agent, runs on Haiku | **BLOCKED by DAAF** — opaque system prompt, wrong model |

### 6.2 The Name-to-File Mapping

The `subagent_type` parameter in Agent tool calls maps to agent files as follows:

```
subagent_type: "research-executor"
    -> Claude Code scans .claude/agents/
    -> Finds research-executor.md (name: research-executor)
    -> Loads frontmatter (tools, permissionMode, skills, hooks)
    -> Injects body as system instructions
    -> Delivers orchestrator's prompt as task
```

For generic types (`general-purpose`, `Plan`, `Explore`), Claude Code uses its own built-in definitions rather than looking for `.md` files.

### 6.3 Complete Subagent Type Table

From the orchestrator's SKILL.md:

| Agent Name (subagent_type) | Permission Mode | Primary Use |
|---------------------------|----------------|-------------|
| `research-executor` | `default` (read/write) | Data acquisition, cleaning, transformation, visualization |
| `code-reviewer` | `default` (read/write) | QA review of executed scripts |
| `data-planner` | `default` (read/write) | Research plan creation |
| `plan-checker` | `plan` (read-only) | Plan verification |
| `source-researcher` | `plan` (read-only) | Source deep-dive |
| `research-synthesizer` | `default` (read/write) | Multi-source synthesis |
| `debugger` | `default` (read/write) | Error diagnosis |
| `notebook-assembler` | `default` (read/write) | Notebook compilation |
| `integration-checker` | `plan` (read-only) | Wiring verification |
| `report-writer` | `default` (read/write) | Stakeholder report |
| `data-verifier` | `plan` (read-only) | Final verification |
| `data-ingest` | `default` (read/write) | Dataset profiling |
| `framework-engineer` | `default` (read/write) | Framework artifact authoring |
| `search-agent` | `plan` (read-only) | Broad-purpose read-only exploration |

---

## 7. Agent Invocation Templates

### 7.1 Standard Agent Prompt Structure

Every DAAF subagent invocation must follow a standardized template (from `full-pipeline-mode.md`):

```python
Agent({
    description: "[3-5 word summary]",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
[Only include skill tool calls for skills NOT preloaded via agent frontmatter.
Named agents already have `data-scientist` injected at startup — do not re-load it.
Call the skill tool only for additional skills.]

## CONTEXT FROM PLAN
[Paste relevant Plan.md methodology sections and Plan_Tasks.md task blocks]

Original Request: [verbatim user request]
Research Question: [from Plan.md]
Data Source: [from Plan.md]
Current Stage: [N]
Wave: [N] (if applicable)

## TASK SPECIFICATION
<task name="[task-name]" type="[auto|checkpoint:human-verify|checkpoint:decision]" wave="[N]">
  <depends_on>[task-ids or "none"]</depends_on>
  <skill>[skill-name]</skill>
  <agent>[agent-name]</agent>
  <files>
    <input>[input file path]</input>
    <output>[output file path]</output>
  </files>
  <action>
    1. [Specific step 1]
    2. [Specific step 2]
  </action>
  <verify>
    - [Verification criterion 1]
  </verify>
  <done>[Measurable completion condition]</done>
</task>

## FILE-FIRST RULE (Stages 5-8)
[File-first execution instructions]

## OUTPUT FORMAT
**Hard cap: 2000 words maximum.**
[Output format specification]
""",
    subagent_type: "[agent-name]"
})
```

### 7.2 Real Invocation Examples

**Stage 2 — Data Exploration (search-agent):**
```python
Agent({
    description: "Stage 2: Data Exploration",
    prompt: """**BASE_DIR:** {BASE_DIR}
...
Then, call the skill tool with name '{domain_explorer_skill}'.
**ORIGINAL REQUEST (for context):** > {original_user_request_verbatim}
**RESEARCH QUESTION:** {research_question}
**CONSTRAINTS:** [years, geography, population]
**THOROUGHNESS DIRECTIVE:** [search directives]
**OUTPUT FORMAT:** [structured output template]
...""",
    subagent_type: "search-agent"
})
```

**Stage 5 — Data Fetch (research-executor):**
```python
Agent({
    description: "Stage 5: Fetch {source} data",
    prompt: """**BASE_DIR:** {BASE_DIR}
## SKILL LOADING
Call the skill tool with name '{domain_query_skill}'.
## CONTEXT FROM PLAN
[Plan.md methodology, Plan_Tasks.md task block]
## TASK SPECIFICATION
<task name="fetch-{source}" type="auto" wave="1">
  [full task XML]
</task>
## FILE-FIRST RULE
[execution instructions]
## OUTPUT FORMAT
[structured return format]""",
    subagent_type: "research-executor"
})
```

**QA Review (code-reviewer):**
```python
Agent({
    description: "QA Review: Stage {N} Step {step} - {task_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
**SCRIPT TO REVIEW:** [path]
**PLAN LOCATIONS:** [Plan.md, Plan_Tasks.md paths]
**OUTPUT FILES:** [list]
**CONTEXT:** [Stage, Step, Wave, Task, Research Question]
## PLAN EXPECTATIONS FOR THIS TASK
[inline table with expected rows, columns, tolerances]
## RISK REGISTER ITEMS FOR THIS STAGE
[risk/mitigation/symptom table]
## QA TOLERANCE FOR THIS ANALYSIS
[tolerance thresholds]
**TASK:** [review instructions]
**OUTPUT FORMAT:** [code reviewer format]""",
    subagent_type: "code-reviewer"
})
```

### 7.3 Parallel Dispatch

Multiple agents can be dispatched simultaneously by making multiple Agent tool calls in a single response message:

- **Maximum 5 concurrent subagents** (sub-batch into groups of <=5)
- All parallel agents must run in **foreground** (background blocked by hook)
- Same-wave tasks dispatch simultaneously
- Later waves wait for ALL prior waves to complete

Example: Stage 3 dispatches multiple `source-researcher` agents in parallel (one per data source).

---

## 8. Context and Session Mechanics

### 8.1 Fresh Context Per Agent

Each subagent launch gets a **fresh context window** — documented as approximately 200K tokens. This is independent of the parent's context utilization. The agent does not see the parent's conversation history, only:
- Its own `.md` body (system instructions)
- Preloaded skill content
- CLAUDE.md project instructions
- The orchestrator's prompt

### 8.2 Context Monitoring for Agents

The `context-reporter.sh` hook fires for both the orchestrator and all subagents (registered on `PreToolUse` with an empty matcher, meaning it fires for every tool call). It injects utilization data as `<system-reminder>` messages. Subagents must act on these signals per the thresholds in CLAUDE.md (NOMINAL < 40%, ELEVATED >= 40%, HIGH >= 60%, CRITICAL >= 75%).

### 8.3 What Happens When a Subagent Hits Context Limits

DAAF defines an **early return protocol** for context-pressured subagents:
1. Complete only the current atomic unit of work
2. Format return output with: completed work + incomplete items list + file paths + decisions made
3. Return to orchestrator, which can redelegate remaining work to a fresh subagent
4. An incomplete but well-documented return is far more valuable than a degraded-context completion

---

## 9. Migration-Critical Summary

### 9.1 What the Target Harness Must Support

| Capability | Claude Code Feature | Migration Priority |
|-----------|-------------------|-------------------|
| **Agent definition files** | `.claude/agents/*.md` with YAML frontmatter + markdown body | CRITICAL — core architecture |
| **Named subagent routing** | `subagent_type` maps to agent files by `name` field | CRITICAL — all dispatch depends on this |
| **Tool allowlisting** | `tools` field restricts available tools per agent | HIGH — security model |
| **Permission modes** | `permissionMode: plan` for read-only agents | HIGH — prevents accidental writes |
| **Skill preloading** | `skills` frontmatter injects skill content at startup | HIGH — 13/15 agents use this |
| **Per-agent hooks** | `hooks` in frontmatter for agent-scoped enforcement | MEDIUM — 4 agents use this |
| **Model selection** | `model` field + inheritance from parent | HIGH — prevents quality degradation |
| **Fresh context per agent** | Each agent gets independent context window | CRITICAL — design assumption |
| **Parallel agent dispatch** | Multiple Agent calls in single response | HIGH — wave-based parallelism |
| **Project-wide hooks on dispatch** | PreToolUse hooks fire on Agent/Task tool calls | MEDIUM — safety enforcement |
| **Context monitoring injection** | Hook-based utilization reporting to agents | MEDIUM — prevents context exhaustion |

### 9.2 What DAAF Builds on Top of Claude Code

| DAAF Layer | What It Adds |
|-----------|-------------|
| **12-section template** | Standardized body structure (AGENT_TEMPLATE.md) — not a Claude Code requirement |
| **Output format contracts** | Standardized Status/Confidence/Learning Signal — DAAF convention, not Claude Code |
| **2,000-word return cap** | DAAF-imposed discipline; Claude Code has no built-in return size limit |
| **Hook-based agent blocking** | enforce-explore, enforce-foreground, deny-guide — DAAF custom hooks |
| **Skill-in-frontmatter assignment table** | DAAF tracks which skills go to which agents — the mechanism is Claude Code's |
| **Invocation templates** | Standardized prompt structure in WORKFLOW_PHASE*.md files — DAAF convention |
| **Preliminary notes persistence** | Orchestrator writes agent returns to disk — DAAF workflow pattern |

### 9.3 Potential Migration Pitfalls

1. **Implicit model inheritance:** If the target harness defaults subagents to a weaker model, all DAAF agents will degrade. The current system assumes every agent runs on the orchestrator's model (Opus) unless explicitly overridden.

2. **CLAUDE.md injection:** Claude Code automatically injects CLAUDE.md into all agents. A migration target must provide an equivalent mechanism for project-wide instructions.

3. **Permission mode semantics:** "plan" mode in Claude Code means read-only at the filesystem level. The target must enforce this equivalently — it's not just about removing Write/Edit from the tool list (Bash could still write files).

4. **Hook event model:** DAAF relies on PreToolUse hooks to gate agent dispatch (blocking Explore, background, claude-code-guide). The target needs equivalent pre-execution interception points.

5. **Parallel dispatch:** DAAF dispatches up to 5 agents simultaneously in a single message. The target must support concurrent subagent execution with foreground permission prompting.

6. **Context isolation:** Each agent getting a fresh ~200K context is a design assumption. If the target shares context between agents or gives agents less context, the invocation templates and agent bodies may not fit.

---

## 10. Appendix: Complete Frontmatter for Every Agent

For reference, here is the exact frontmatter from each of the 15 agent files:

### code-reviewer.md
```yaml
name: code-reviewer
description: >
  Performs iterative QA review of executed scripts. Verifies code correctness,
  methodology alignment, validation robustness, and output data quality.
  Creates parallel QA inspection scripts. Invoked by orchestrator after each
  Stage 5-8 script execution. Also performs QA review of profiling scripts
  during Data Onboarding mode (QAP1-QAP4).
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: default
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

### data-ingest.md
```yaml
name: data-ingest
description: >
  Systematically profiles tabular datasets across four structured parts (Structural,
  Statistical, Relational, Interpretation), producing detailed findings that feed into
  skill authoring. Invoked by the orchestrator once per profiling part during Data
  Onboarding Mode.
tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill]
skills: data-scientist
permissionMode: default
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

### data-planner.md
```yaml
name: data-planner
description: >
  Creates comprehensive research plans (Plan.md) and executable task sequences
  (Plan_Tasks.md) with wave-based parallelization. Invoked by orchestrator at
  Stage 4 after discovery phases complete. Also handles plan revisions when
  plan-checker or user identifies issues.
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: default
```

### data-verifier.md
```yaml
name: data-verifier
description: >
  Performs adversarial goal-backward verification of completed analyses.
  Verifies artifact existence, substantiveness, wiring, and cross-artifact
  coherence. Invoked by orchestrator at Stage 12 (Final Review) before delivery.
tools: [Read, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: plan
```

### debugger.md
```yaml
name: debugger
description: >
  Diagnoses data quality issues and analysis failures using scientific
  hypothesis-testing methodology. Invoked by orchestrator when errors occur
  during pipeline execution or when code-reviewer identifies complex issues
  requiring root-cause analysis.
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill, WebFetch, WebSearch]
skills: data-scientist
permissionMode: default
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

### framework-engineer.md
```yaml
name: framework-engineer
description: >
  Modifies DAAF framework artifacts (skills, agents, modes, reference files,
  hooks) with template compliance, cross-file consistency, and integration
  checklist execution. Invoked during Framework Development mode for authoring,
  editing, and wiring framework components.
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
permissionMode: default
skills:
  - skill-authoring
  - agent-authoring
```

### integration-checker.md
```yaml
name: integration-checker
description: >
  Validates that analysis components are properly connected by tracing data flows,
  verifying file references resolve, and detecting orphaned components. Invoked by
  orchestrator at Stages 9, 11, and 12 to confirm end-to-end pipeline wiring.
tools: [Read, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: plan
```

### notebook-assembler.md
```yaml
name: notebook-assembler
description: >
  Compiles executed scripts into a Marimo notebook by literally copying script
  file contents into cells. Does not generate new analysis code, dashboards,
  or interactive widgets. Invoked at Stage 9 after all Stage 5-8 scripts and
  QA substages are complete.
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
skills:
  - data-scientist
  - marimo
permissionMode: default
```

### plan-checker.md
```yaml
name: plan-checker
description: >
  Verifies research plans will achieve analysis goals before execution begins.
  Performs goal-backward analysis across six dimensions (completeness, consistency,
  feasibility, testability, clarity, scope). Invoked by orchestrator at Stage 4.5
  after data-planner creates Plan.md and Plan_Tasks.md.
tools: [Read, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: plan
```

### report-writer.md
```yaml
name: report-writer
description: >
  Synthesizes all pipeline artifacts into a stakeholder-appropriate report
  following REPORT_TEMPLATE.md. Invoked at Stage 11 after QA aggregation
  (Stage 10) completes and before final review (Stage 12).
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: default
```

### research-executor.md
```yaml
name: research-executor
description: >
  Executes data acquisition, cleaning, transformation, and visualization tasks
  with atomic precision. Spawned by orchestrator for Stages 5-8 operations.
  Each invocation performs exactly ONE operation with pre/post validation.
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: default
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

### research-synthesizer.md
```yaml
name: research-synthesizer
description: >
  Consolidates findings from parallel Stage 2-3 exploration tasks into
  actionable guidance for planning. Resolves conflicts between data sources,
  documents uncertainty, and produces structured recommendations. Invoked at
  Stage 3.5 when multiple sources have been explored and findings need
  integration before Plan creation.
tools: [Read, Write, Edit, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: default
```

### search-agent.md
```yaml
name: search-agent
description: >
  Performs read-only exploration of codebases, documentation, datasets, and web
  sources to locate specific information. Invoked by the orchestrator in place
  of generic Plan or Explore subagent types when targeted or broad search is
  needed during any mode or pipeline stage.
tools: [Read, Bash, Glob, Grep, Skill, WebSearch, WebFetch]
permissionMode: plan
model: inherit
```

### source-researcher.md
```yaml
name: source-researcher
description: >
  Performs deep-dive investigation of a single data source's structure,
  caveats, coded values, and pitfalls. Used across multiple engagement
  modes: Full Pipeline (Stage 3), Data Discovery, and Data Lookup (deep
  lookup). Each invocation focuses on exactly one data source.
tools: [Read, Bash, Glob, Grep, Skill]
skills: data-scientist
permissionMode: plan
```
