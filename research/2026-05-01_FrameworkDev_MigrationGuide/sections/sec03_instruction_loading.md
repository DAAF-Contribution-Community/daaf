## 3. Instruction Loading and Project Configuration
**Criticality:** CRITICAL | **Interdependencies:** 7 (all other features depend on this)

### Design Intent

An LLM research orchestration framework must solve a fundamental tension: every agent in the system needs shared rules (safety, documentation standards, coding style), but no single agent should carry the full weight of every instruction the framework has ever written. Load everything at once and the context window fills before work begins. Load nothing and agents operate without guardrails. The wrong instructions reaching the wrong agent at the wrong time produces either wasted context or inconsistent behavior.

DAAF's response is a **10-layer instruction hierarchy** with a **progressive disclosure cascade** that determines *when* each layer loads, *who* sees it, and *how much context it costs*. The hierarchy separates content by three dimensions: universality (does every agent need this?), temporality (does this apply for the whole session or only during a specific phase?), and audience (is this for the orchestrator, a specific subagent type, or all agents?). This separation is DAAF's core architectural contribution in this area -- Claude Code provides the loading primitives, but the decisions about *what goes where* and *when it loads* are entirely DAAF's design.

The hierarchy exists to serve a single operational guarantee: **every agent in the system -- orchestrator and subagent alike -- operates under a consistent set of universal rules, while carrying only the additional context it needs for its specific task.**

### What It Does

The instruction loading system accomplishes five things:

1. **Universal rule propagation** -- A single source of truth for framework-wide rules (safety boundaries, coding style, documentation standards, context monitoring thresholds) that automatically reaches every agent without explicit forwarding.
2. **Runtime configuration** -- Model selection, permission patterns, environment variables, and feature toggles that shape the harness's behavior before any agent code runs.
3. **Progressive knowledge injection** -- Mode-specific protocols, workflow phase instructions, and domain skills load only when relevant, keeping context lean through early phases.
4. **Subagent context composition** -- When a subagent spawns, a deterministic set of layers assembles its initial context: system prompt, universal rules, agent-specific protocol, preloaded skills, and the orchestrator's task prompt.
5. **Persistent cross-session configuration** -- User preferences survive session boundaries via a version-controlled, human-editable configuration store.

### Current Realization on Claude Code

The 10 instruction layers load in sequence from earliest/most persistent to latest/most ephemeral. Each layer is classified as Native Primitive, DAAF-Built, or Hybrid.

#### Layer 1: Claude Code System Prompt -- Native Primitive

Injected by the Claude Code runtime. Not visible in the DAAF repository and not configurable by DAAF. Contains Claude's base identity, tool definitions and usage instructions (Read, Write, Edit, Bash, Glob, Grep, Agent, Skill, WebSearch, WebFetch, and others), Anthropic safety guidelines, and conventions for git commits and PR creation.

**Migration implication:** Completely invisible and uncontrollable. Any target harness must provide its own equivalent system prompt defining tool capabilities, identity, and safety baselines.

#### Layer 2: CLAUDE.md -- Hybrid (Native Loading, DAAF Content)

**File:** `/daaf/CLAUDE.md` (377 lines)

**Loading mechanism (Native Primitive):** Claude Code automatically discovers CLAUDE.md files at session start by walking up from the current working directory to the git worktree root. The content is injected as a `<system-reminder>` block tagged `# claudeMd`. This injection happens for the orchestrator *and* for every subagent -- subagents receive CLAUDE.md in their context automatically without the orchestrator forwarding it.

**Content scope (DAAF-Built):** DAAF authored all 377 lines to serve as the framework's universal rulebook. The content is organized into nine sections:

| Section | Approx. Lines | Content |
|---------|---------------|---------|
| Identity | 1-28 | Framework philosophy, five core requirements (Transparent, Rigorous, Reproducible, Responsible, Scalable) |
| Execution Philosophy | 30-70 | File-first execution mandate, iterative validation, IAT documentation, parquet-only, immutable versioning, skill information awareness |
| Code Style | 72-100 | Sequential inline Python: no functions, no classes, flat scripts |
| Context-Efficient Reading | 102-132 | Progressive disclosure reading rules, practical defaults for file reads |
| Context & Session Health | 134-200 | Dual-threshold utilization system (40%/60%/75% or 150k/200k/250k tokens), subagent monitoring, degradation symptoms, quality primacy rule |
| Boundaries & Safety | 204-248 | Credential protection, destructive command prevention, repository safety, defense-in-depth architecture table |
| Project Conventions | 250-329 | One-command-per-Bash-call rule, shell permissions, version control protocol, file naming conventions, folder structure, script naming |
| Reference Files | 331-360 | Index of all reference documents in `agent_reference/` |
| User Preferences | 362-377 | Primary analysis language background, cross-language annotation toggle |

**Key design principle:** CLAUDE.md contains *only* universal rules that apply to every agent. It does not contain mode-specific instructions (those live in the orchestrator skill), agent-specific protocols (those live in agent definition files), or domain knowledge (that lives in skills). This separation is deliberate -- CLAUDE.md is the one instruction layer guaranteed visible to all agents, so it must be limited to content that genuinely applies universally.

#### Layer 3: settings.json -- Hybrid (Native Parsing, DAAF Configuration)

**File:** `/daaf/.claude/settings.json` (228 lines)

Claude Code parses this file at session start to configure the runtime. DAAF authored all configuration values. The file contains six top-level keys:

| Key | Type | DAAF Configuration |
|-----|------|--------------------|
| `statusLine` | object | Runs `context-bar.sh` to display model, branch, and real-time context utilization in the terminal status bar |
| `permissions` | object | `allow` (38 patterns) and `deny` (35 patterns) controlling tool auto-approval and hard-blocking |
| `env` | object | 7 environment variables (see below) |
| `outputStyle` | string | `"Explanatory"` -- detailed, structured responses |
| `showThinkingSummaries` | boolean | `true` -- shows abbreviated thinking summaries |
| `hooks` | object | 15 hook registrations across 5 lifecycle event types |

**Environment variables configured via `env`:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `ANTHROPIC_MODEL` | `claude-opus-4-6[1m]` | Model selection with 1M context window |
| `CLAUDE_CODE_EFFORT_LEVEL` | `high` | Extended thinking effort level |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | `1` | Prevents auto-creating memory entries |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | `1` | No background task execution |
| `DISABLE_AUTOUPDATER` | `1` | Prevents auto-updates |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | No telemetry |
| `ENABLE_PROMPT_CACHING_1H` | `1` | 1-hour prompt caching |

The permission patterns and hook registrations are covered in detail in Section 5 (Permission and Security System) and Section 7 (Hook System), respectively.

#### Layer 4: Agent Frontmatter -- Hybrid (Native Parsing, DAAF Configuration)

**Files:** `/daaf/.claude/agents/*.md` (14 agent definition files)

When the orchestrator invokes the Agent tool with a specific `subagent_type`, Claude Code locates the matching `.claude/agents/{name}.md` file, parses the YAML frontmatter, applies tool restrictions, permission mode, and hook registrations, then injects the markdown body as the agent's behavioral protocol. DAAF authored all 14 agent definitions.

Covered in full in Section 4 (Agent System).

#### Layer 5: Hooks -- Hybrid (Native Infrastructure, DAAF Scripts)

**Files:** `/daaf/.claude/hooks/*.sh` (12 hook scripts)

Claude Code provides the hook lifecycle (5 event types, JSON stdin, exit code semantics). DAAF designed and implemented all 12 hook scripts. Hooks inject instructions into agent context via two mechanisms: `additionalContext` JSON output (injected as `<system-reminder>` blocks) and stderr messages on exit code 2 (shown to the model as error context). The context-reporter hook, for example, injects utilization data as a system reminder on every tool call for both the orchestrator and subagents.

Covered in full in Section 7 (Hook System).

#### Layer 6: The daaf-orchestrator Skill -- DAAF-Built

**File:** `/daaf/.claude/skills/daaf-orchestrator/SKILL.md` (592 lines) + 12 reference files

The orchestrator's "mega system prompt" -- loaded via a deterministic three-hook chain on the first user message. Contains mode classification (9 engagement modes), confirmation protocol, subagent coordination patterns, context budget rules, and progressive reference loading decision trees. This is the largest single instruction payload in the system.

**Loading mechanism (DAAF-Built, using native hook primitives):**
1. User sends first message; `UserPromptSubmit` fires
2. `remind-orchestrator.sh` checks for a session flag file; flag absent, so it emits "Load daaf-orchestrator skill NOW" into context
3. Orchestrator calls `Skill(skill: "daaf-orchestrator")`; SKILL.md body injected
4. `PostToolUse` fires on the Skill matcher; `flag-orchestrator-loaded.sh` creates the flag file
5. On subsequent messages, the flag exists, and the reminder is suppressed

**Who sees it:** Only the orchestrator. The skill description explicitly states: "Loaded exclusively by the orchestrator -- not for subagents or user questions."

**Relationship to CLAUDE.md:** Complementary, not overlapping. CLAUDE.md carries universal rules for all agents. The orchestrator skill carries orchestrator-specific behavioral protocol (modes, dispatch patterns, communication standards). This separation ensures subagents operate under universal rules without receiving orchestrator-only instructions that would consume their context budget and potentially create conflicting directives.

#### Layer 7: Agent Protocol Body -- DAAF-Built (Portable Markdown)

The markdown body below each agent's YAML frontmatter. DAAF designed a 12-section template (Identity, Core Distinction, Upstream Inputs, Core Behaviors, Protocol, Output Format, Downstream Consumers, Boundaries, Anti-Patterns, Quality Standards, Invocation, References). These are pure text -- the most portable instruction layer in the system.

#### Layer 8: Skills -- Hybrid (Native Skill Tool, DAAF Content and Architecture)

**Files:** `/daaf/.claude/skills/*/SKILL.md` (36 skills)

Domain knowledge loaded on demand into subagent contexts. Claude Code provides the Skill tool and automatic filesystem discovery. DAAF designed the three-level progressive disclosure architecture (metadata always loaded, body on trigger, reference files on demand) and authored all 36 skills.

Covered in full in Section 6 (Skill System).

#### Layer 9: System Reminders -- Native Primitive

Claude Code injects several `<system-reminder>` blocks into every agent's context:

| Reminder | Content |
|----------|---------|
| `# claudeMd` | Full CLAUDE.md content (see Layer 2) |
| `# currentDate` | Today's date in YYYY-MM-DD format |
| `# userEmail` | User's configured email address |
| `gitStatus` | Current branch, working tree status, recent commit history |
| Available skills | Complete list of all 36 skill names with truncated descriptions |
| Environment | Platform, shell, OS version |
| Model identity | "You are powered by the model named..." |
| Output style | "Explanatory output style is active" |

These reminders fire for both the orchestrator and subagents. The skills list alone consumes approximately 3,600 words of context (36 skills at ~100 words each) -- a fixed cost of the skill system's always-available discovery mechanism.

#### Layer 10: Orchestrator Prompt to Subagent -- DAAF-Built

When the orchestrator dispatches a subagent via the Agent tool, the `prompt` parameter becomes part of the subagent's initial context. DAAF mandates that every orchestrator prompt includes `**BASE_DIR:**` with the project's absolute path and provides all file paths as absolute paths. This is the orchestrator's mechanism for passing task-specific context, file references, and instructions that are too narrow for CLAUDE.md but essential for the subagent's task.

### Design Choices and Rationale

**Separating universal rules (CLAUDE.md) from orchestrator protocol (skill) from agent protocol (body).** CLAUDE.md is the only layer guaranteed visible to every agent. If orchestrator-specific instructions (mode classification, dispatch patterns) were in CLAUDE.md, every subagent would pay the context cost for content it cannot act on. Conversely, if universal rules (safety boundaries, coding style) were only in the orchestrator skill, subagents would operate without guardrails. The three-way separation ensures each agent receives exactly the instructions relevant to its role.

**CLAUDE.md as persistent cross-session configuration store.** User preferences (primary analysis language, annotation toggles) are stored in CLAUDE.md rather than in a separate configuration file. This exploits CLAUDE.md's auto-loading property: preferences are automatically available to every agent in every session without explicit loading logic. Because CLAUDE.md is git-tracked, preference changes are auditable and reversible. The orchestrator edits CLAUDE.md directly (with user confirmation) when a user indicates a preference change.

**Progressive disclosure cascade.** DAAF's instruction content totals tens of thousands of lines across CLAUDE.md, the orchestrator skill, 14 agent protocols, 5 workflow phase files, and 36 skills. Loading everything at session start would consume the context window before any work begins. The cascade structures loading into four tiers:

| Tier | When Loaded | Content | Approx. Size |
|------|-------------|---------|--------------|
| Always loaded | Every agent, every session | CLAUDE.md, settings.json config, system reminders | ~6,000 words |
| Orchestrator-only | First user message | daaf-orchestrator/SKILL.md | ~5,000 words |
| Mode-confirmed | After user confirms engagement mode | Mode-specific reference file, workflow phase files (loaded per phase) | 200-500 lines per file |
| On-demand | During execution | Additional skills, reference files, data files | Variable |

**The `.claudeignore` discovery prevention pattern.** `/daaf/.claudeignore` contains 12 patterns preventing Claude Code from indexing sensitive files (`.env`, `.env.*`, `.env.local`, `.env.production`, `environment_settings.txt`, `environment_settings*.txt`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `**/credentials*`, `**/secrets/`). This is distinct from the `deny` rules in settings.json: `.claudeignore` prevents *discovery* (the files never appear in search results or file listings), while deny rules prevent *access* (attempts to read/write/edit matched files are hard-blocked). DAAF uses both layers as defense-in-depth for credential protection.

**Settings.json environment variables for runtime control.** Rather than hardcoding model selection and feature toggles, DAAF uses settings.json's `env` key to inject environment variables that Claude Code reads at startup. This makes the configuration declarative, version-controlled, and modifiable without editing CLAUDE.md. The `ANTHROPIC_MODEL` variable with the `[1m]` suffix is particularly significant -- it activates the 1M-token context window that DAAF's context monitoring system is calibrated for.

**No user-level CLAUDE.md.** DAAF relies entirely on the project-level `/daaf/CLAUDE.md`. A user-level `~/.claude/CLAUDE.md` could introduce inconsistencies between users sharing the same project. By keeping all instructions project-scoped and version-controlled, DAAF ensures uniform behavior across all users.

### Replication Specification

A target harness must provide the following capabilities to achieve instruction loading parity:

**R3.1 — Project instruction auto-injection.** The harness must automatically discover and inject project-level instructions (equivalent to CLAUDE.md) into every agent's context at startup -- including subagents. This injection must happen without explicit loading calls; it must be automatic and universal.

*Acceptance criterion:* A newly spawned subagent can reference a rule defined in the project instruction file without the orchestrator forwarding that rule in its prompt.

**R3.2 — Project configuration file.** The harness must support a declarative configuration file (equivalent to settings.json) that controls: permission patterns (allow/deny), environment variables, hook registrations, and UI preferences. The file must be version-controllable and project-scoped.

*Acceptance criterion:* A permission pattern added to the configuration file takes effect on the next session start without code changes.

**R3.3 — Sensitive file exclusion.** The harness must support a file-level exclusion mechanism (equivalent to .claudeignore) that prevents specified patterns from appearing in search results, file listings, and indexing. This is a discovery-prevention layer, complementary to access-prevention (deny rules).

*Acceptance criterion:* A file matching an exclusion pattern does not appear in search or listing results, even though it exists on the filesystem.

**R3.4 — System-level context injection.** The harness must be able to inject contextual information (date, user identity, git status, environment, available skills/tools) into every agent's context as system-level metadata distinct from user messages or tool output.

*Acceptance criterion:* An agent can access the current date and user email without making a tool call.

**R3.5 — Progressive content loading.** The harness must support loading instruction content at different points in the session lifecycle: at session start, on first user message, after a mode/phase transition, and on demand during execution. Content loaded later must not require pre-registration at session start.

*Acceptance criterion:* A workflow phase file loaded in Phase 3 is not present in the agent's context during Phases 1-2, and its loading does not require any Phase 1 configuration.

**R3.6 — Deterministic subagent context composition.** When a subagent spawns, its initial context must be deterministically composed from: system prompt + project instructions + system reminders + agent-specific configuration + agent-specific protocol + preloaded skills + orchestrator prompt. Conversation history from the orchestrator must NOT be inherited.

*Acceptance criterion:* Two subagents of the same type, spawned at different points in the orchestrator's conversation, receive identical base contexts (differing only in the orchestrator's task prompt and time-varying system reminders).

**Degraded-mode options:**
- If auto-injection of project instructions into subagents is unavailable, the orchestrator can explicitly include critical rules in every subagent prompt. This increases orchestrator context cost and risks inconsistency, but preserves the behavioral contract.
- If progressive loading is unavailable, the full instruction set can be loaded at session start. This reduces the effective context budget for work but maintains correctness.
- If declarative configuration is unavailable, settings can be encoded as additional project instructions, with enforcement shifted to hooks or behavioral directives rather than runtime configuration.

### Harness Landscape

Most surveyed harnesses support some form of project instruction file: Codex uses `AGENTS.md`, Cursor uses `.cursor/rules/`, Windsurf uses `.windsurfrules`, and Aider uses `.aider.conf.yml` plus conventions files. All support environment variable configuration. Progressive disclosure and automatic subagent injection have fewer direct equivalents -- Codex's `AGENTS.md` is injected into all agent contexts (closest parallel to CLAUDE.md), while Cursor and Windsurf load rules files that may not propagate to subagents.

The `agentskills.io` open standard (adopted by Codex and Cursor) provides skill discovery and loading semantics comparable to Claude Code's Skill tool, making Layer 8 increasingly portable.

See Section 14 (Harness Comparison Matrix) for detailed cross-reference.

### Dependencies

**What depends on this feature:**
- **Section 4 (Agent System):** Agents inherit CLAUDE.md automatically; agent frontmatter is parsed by the instruction loading system (Layer 4)
- **Section 5 (Permission System):** Permission patterns are defined in settings.json (Layer 3)
- **Section 6 (Skill System):** Skills are loaded as instruction content (Layer 8); skill metadata is injected via system reminders (Layer 9)
- **Section 7 (Hook System):** Hook registrations are defined in settings.json (Layer 3); hooks inject instructions via Layers 5 and 9
- **Section 8 (Context Management):** Context thresholds are defined in CLAUDE.md (Layer 2); the context-reporter hook injects utilization via Layer 5
- **Section 9 (Logging and Audit Trail):** File-first execution rules are defined in CLAUDE.md (Layer 2); `run_with_capture.sh` and IAT conventions are enforced through instruction loading
- **Section 10 (Tool System):** The one-command-per-Bash-call rule is defined in CLAUDE.md (Layer 2); per-agent tool restrictions are applied via Layer 4

**What this feature depends on:**
- The Claude Code runtime (Layer 1) must exist before any other layer can load
- The filesystem must be accessible for CLAUDE.md discovery, settings.json parsing, and agent file lookup
- Git repository structure is assumed for CLAUDE.md directory-walking behavior
