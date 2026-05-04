# DAAF Instruction Loading, System Prompt Architecture, and CLAUDE.md — Complete Migration Reference

> **Generated:** 2026-05-01
> **Purpose:** Comprehensive documentation of how DAAF structures and loads instructions across all agents, sufficient to reconstruct the entire instruction architecture in another AI coding harness.

---

## 1. The Complete Instruction Hierarchy

Listed in order of loading, from earliest/most persistent to latest/most ephemeral.

### Layer 1: Claude Code System Prompt (Anthropic-provided)

**Source:** Injected by the Claude Code runtime itself. Not visible in the DAAF repository. Not configurable by DAAF.

**What it contains:**
- Claude's base identity and capabilities
- Tool definitions and usage instructions (Read, Write, Edit, Bash, Glob, Grep, Agent, Skill, WebSearch, WebFetch)
- Safety guidelines from Anthropic
- Git commit conventions and PR creation guidance
- Instructions about using tools, avoiding emojis, sharing file paths

**Migration implication:** This layer is completely invisible and uncontrollable from DAAF's perspective. Any migrated harness must provide its own equivalent system prompt defining tool capabilities, identity, and safety baselines.

### Layer 2: CLAUDE.md — Project-Level Instructions

**Source:** `/daaf/CLAUDE.md` (377 lines)

**Loading mechanism:** Claude Code automatically discovers and loads CLAUDE.md files at session start. It walks up from the current working directory to the git worktree root, loading any CLAUDE.md files it finds. The content appears in the model's context as a `<system-reminder>` block tagged with `# claudeMd` and subtitled `Contents of /daaf/CLAUDE.md (project instructions, checked into the codebase)`.

**What it contains (section by section):**

| Section | Lines (approx) | Content |
|---------|----------------|---------|
| Identity | 1-28 | Framework philosophy, five core requirements (Transparent, Rigorous, Reproducible, Responsible, Scalable) |
| Execution Philosophy | 30-70 | Universal rules for all code-writing agents: iterative validation, file-first execution, IAT documentation, parquet-only, immutable versioning, skill awareness |
| Code Style | 72-100 | Sequential inline Python: no functions, no classes, flat scripts |
| Context-Efficient Reading | 102-132 | Progressive disclosure reading rules, practical defaults |
| Context & Session Health | 134-200 | Utilization thresholds (40%/60%/75% or 150k/200k/250k tokens), subagent monitoring, degradation symptoms |
| Boundaries & Safety | 204-248 | Credential protection, destructive command prevention, repository safety, defense-in-depth table |
| Project Conventions | 250-329 | Bash one-command rule, shell permissions, version control, file/script naming |
| Reference Files | 331-360 | Index of all reference documents |
| User Preferences | 362-377 | Primary language background, cross-language annotations setting |

**Key design principles:**
- CLAUDE.md defines UNIVERSAL rules that apply to ALL agents (orchestrator and subagents)
- It does NOT contain mode-specific or stage-specific instructions — those are in the orchestrator skill and workflow phase files
- It is the ONLY instruction layer guaranteed to be visible to every agent in the system
- It is checked into version control and human-editable

**Who sees it:** Both the orchestrator AND all subagents. Confirmed by observation: subagents can see CLAUDE.md content in their system-reminder block.

### Layer 3: settings.json — Configuration and Permissions

**Source:** `/daaf/.claude/settings.json` (228 lines)

**What it configures:**

| Setting | Value | Purpose |
|---------|-------|---------|
| `statusLine` | `context-bar.sh` command | Custom terminal status bar showing model, branch, context % |
| `permissions.allow` | 38 entries | Auto-allowed tool patterns (no user confirmation needed) |
| `permissions.deny` | 35 entries | Explicitly blocked tool patterns (always blocked) |
| `env.ANTHROPIC_MODEL` | `claude-opus-4-6[1m]` | Model selection with 1M context window |
| `env.CLAUDE_CODE_EFFORT_LEVEL` | `high` | Extended thinking effort |
| `env.CLAUDE_CODE_DISABLE_AUTO_MEMORY` | `1` | Prevents auto-creating memory entries |
| `env.CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | `1` | No background task execution |
| `env.DISABLE_AUTOUPDATER` | `1` | Prevents auto-updates |
| `env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | No telemetry |
| `env.ENABLE_PROMPT_CACHING_1H` | `1` | 1-hour prompt caching |
| `outputStyle` | `"Explanatory"` | Controls response style |
| `showThinkingSummaries` | `true` | Shows thinking process summaries |
| `hooks` | 6 event types, 13 registrations | Runtime behavior injection |

### Layer 4: Agent Frontmatter — Per-Agent Configuration

**Source:** `.claude/agents/*.md` files (15 agent files)

**Loading mechanism:** When the orchestrator invokes `Agent(subagent_type: "agent-name")`, Claude Code finds the matching `.claude/agents/agent-name.md`, parses YAML frontmatter, applies configuration, and injects the markdown body.

**Frontmatter fields used by DAAF:**

| Field | Example | Purpose |
|-------|---------|---------|
| `name` | `research-executor` | Agent identifier; must match filename and subagent_type |
| `description` | Multi-line string | Third-person role description |
| `tools` | `[Read, Write, Edit, Bash, Glob, Grep, Skill]` | Explicit tool allowlist |
| `permissionMode` | `default` or `plan` | `plan` = read-only; `default` = full access |
| `skills` | `data-scientist` or list | Skills auto-loaded at spawn |
| `model` | `inherit` (search-agent only) | Model inheritance |
| `hooks.PreToolUse` | Hook registration | Agent-scoped hooks |

**Skills preloading via frontmatter — complete inventory:**

| Agent | Preloaded Skills |
|-------|-----------------|
| research-executor | `data-scientist` |
| code-reviewer | `data-scientist` |
| data-planner | `data-scientist` |
| plan-checker | `data-scientist` |
| source-researcher | `data-scientist` |
| research-synthesizer | `data-scientist` |
| debugger | `data-scientist` |
| notebook-assembler | `data-scientist`, `marimo` |
| integration-checker | `data-scientist` |
| report-writer | `data-scientist` |
| data-verifier | `data-scientist` |
| data-ingest | `data-scientist` |
| framework-engineer | `skill-authoring`, `agent-authoring` |
| search-agent | *(none)* |

### Layer 5: Hooks — Runtime Behavior Injection

**Source:** `/daaf/.claude/hooks/*.sh` (13 files)

**Hook event types and injection mechanisms:**

| Event | Trigger | Output Mechanism | Injection Format |
|-------|---------|-----------------|------------------|
| `SessionStart` | Session begins | stdout to log | Not injected into model context |
| `SessionEnd` | Session ends | stdout to log | Not injected into model context |
| `UserPromptSubmit` | User sends message | stdout → visible as hook result | Visible to model as user message context |
| `PreToolUse` (additionalContext) | Before tool executes | JSON → `<system-reminder>` | System-level context before tool result |
| `PreToolUse` (permissionDecision) | Before tool executes | JSON → blocks tool | Blocks execution with reason |
| `PreToolUse` (exit code 2) | Before tool executes | stderr → shown to model | Blocks execution with error |
| `PostToolUse` | After tool executes | stdout → injected | Visible to model after tool result |

### Layer 6: The daaf-orchestrator Skill — "Mega System Prompt"

**Source:** `/daaf/.claude/skills/daaf-orchestrator/SKILL.md` (592 lines) + 12 reference files

**Loading mechanism — deterministic chain:**
1. User sends first message
2. `UserPromptSubmit` fires
3. `remind-orchestrator.sh` checks flag → not found → emits "Load daaf-orchestrator skill NOW"
4. Orchestrator calls `Skill(skill: "daaf-orchestrator")`
5. SKILL.md loaded into orchestrator context
6. `PostToolUse` fires → `flag-orchestrator-loaded.sh` creates flag
7. Subsequent messages: flag found → no reminder

**What it contains:**

| Section | Content |
|---------|---------|
| Identity & Mission | Orchestrator role |
| Tone & Voice | Communication standards |
| Welcome Preamble | Greeting, orientation, language detection |
| Mode Classification | Nine modes, decision tree, confirmation protocol, escalation |
| Communication Standards | Plain-language rule, context-sensitive help |
| What to Load Next | Progressive reference loading decision tree |
| Subagent Coordination | Dispatch patterns, skill loading, context budget, return processing |

**Relationship to CLAUDE.md:** Complementary, not overlapping:
- CLAUDE.md = universal rules for ALL agents
- Orchestrator skill = orchestrator-specific behavioral protocol (modes, dispatch, communication)

**Who sees it:** ONLY the orchestrator. Explicitly documented: "Loaded exclusively by the orchestrator — not for subagents."

### Layer 7: Agent Protocol Body (Markdown)

**Source:** `.claude/agents/*.md` body (below frontmatter)

Agent bodies follow a 12-section template: Identity, Core Distinction, Upstream Inputs, Core Behaviors, Protocol, Output Format, Downstream Consumers, Boundaries, Anti-Patterns, Quality Standards, Invocation, References.

**Migration implication:** Agent bodies are pure markdown text — highly portable.

### Layer 8: Skills — On-Demand Domain Knowledge

**Source:** `.claude/skills/*/SKILL.md` files (36 skills)

**Loading paths:**
1. **Frontmatter preloading:** Auto-loaded at subagent spawn
2. **Explicit loading:** Agent calls `Skill(skill: "name")` during execution

Skills are loaded INTO THE SUBAGENT'S CONTEXT. Exceptions: orchestrator loads skills directly in Framework Development mode (skill-authoring, agent-authoring) and Ad Hoc mode (data-scientist).

**Skill discovery paths:**
1. Project: `.claude/skills/<name>/SKILL.md` (searched first)
2. Global: `~/.claude/skills/<name>/SKILL.md` (searched second)

### Layer 9: System Reminders — Runtime Context Injection

**Known `<system-reminder>` injection points in DAAF:**

| Source | Tag/Label | Content |
|--------|-----------|---------|
| CLAUDE.md | `# claudeMd` | Full CLAUDE.md content |
| Current date | `# currentDate` | "Today's date is YYYY-MM-DD." |
| User email | `# userEmail` | "The user's email address is X" |
| Git status | `gitStatus` | Branch, status, recent commits |
| Available skills | (within system-reminder) | Full skill list with descriptions/triggers |
| Environment | (plain text) | Platform, shell, OS version |
| Model identity | (plain text) | "You are powered by the model named..." |
| Context reporter | `additionalContext` | "Context utilization [SEVERITY]: Nk / Mk tokens" |
| Output style | (within system-reminder) | "Explanatory output style is active" |

### Layer 10: Orchestrator Prompt to Subagent

The orchestrator's Agent tool call prompt becomes part of the subagent's initial context. Every prompt MUST include `**BASE_DIR:**` and all file paths must be absolute.

---

## 2. What Subagents See vs. Don't See

### What a subagent DOES see at spawn time:

| Content | Source |
|---------|--------|
| CLAUDE.md content | Automatic Claude Code loading |
| Agent body (markdown protocol) | From `.claude/agents/agent-name.md` |
| Preloaded skills | From `skills` field in frontmatter |
| Orchestrator's prompt | The `prompt` parameter of Agent tool call |
| Available skills list | System-provided |
| Current date, user email, git status, environment | System-provided system-reminders |
| Model identity | System-provided |
| Context utilization | Hook injection (context-reporter fires for subagents) |
| Project-level hooks | Hooks with `""` matcher fire for all agents |

### What a subagent DOES NOT see:

| Content | Reason |
|---------|--------|
| Orchestrator's conversation history | Subagents are isolated contexts |
| Other subagents' results | Unless passed in orchestrator prompt |
| Orchestrator skill content | Only loaded in orchestrator context |
| Mode-specific reference files | Only loaded in orchestrator context |
| STATE.md content (unless in prompt) | Orchestrator reads it; subagents only see what's passed |
| UserPromptSubmit hook output | Only fires on user messages, not subagent spawns |

### Subagent context composition:

```
[Claude Code System Prompt]
  + [CLAUDE.md (project instructions)]
  + [System reminders: date, email, git status, environment, skills list]
  + [Agent frontmatter config (tools, permissions, hooks)]
  + [Agent body (behavioral protocol)]
  + [Preloaded skills (from frontmatter)]
  + [Orchestrator's prompt (task specification)]
```

**Key insight:** CLAUDE.md is the ONLY "shared knowledge" between orchestrator and subagents that isn't explicitly passed in prompts. This is why CLAUDE.md contains universal rules while mode-specific instructions live elsewhere.

---

## 3. The Output Style System

**Configuration:** `"outputStyle": "Explanatory"` in settings.json

The output style is a Claude Code setting that affects response formatting and verbosity. "Explanatory" produces detailed, structured responses — aligned with DAAF's educational philosophy. This is complemented by the orchestrator skill's "Tone & Voice" section for orchestrator-specific communication standards.

**Migration implication:** Output style is a single config key. Behavioral effect must be replicated through system prompt instructions.

---

## 4. User Preferences in CLAUDE.md

**Location:** `/daaf/CLAUDE.md` lines 362-377

**Propagation flow:**
```
CLAUDE.md (stored preference: "Primary analysis language background: Python")
  → Orchestrator (reads at session start)
    → Agent prompts (directive injected into code-producing agent dispatches)
      → Subagent (loads translation skill, adds inline comments)
```

**Mechanism:** Orchestrator detects language background signals, proposes updating CLAUDE.md with user confirmation, then EDITS CLAUDE.md directly. On subsequent sessions, reads the preference and silently propagates translation directives.

**Key design insight:** CLAUDE.md serves as a persistent configuration store across sessions. Being git-tracked, preference changes are auditable.

---

## 5. Progressive Disclosure Architecture

### Loading cascade:

```
ALWAYS LOADED (every agent, every session):
  CLAUDE.md, settings.json, system reminders

ORCHESTRATOR ONLY (first user message):
  daaf-orchestrator/SKILL.md
  first-run-transparency.txt (first session only)

AFTER MODE CONFIRMATION:
  Mode-specific reference file (e.g., full-pipeline-mode.md)
  Mode-specific workflow files (loaded per phase)

WHEN SUBAGENT SPAWNED:
  Agent body, preloaded skills, orchestrator prompt

DURING EXECUTION (on demand):
  Additional skills, reference files, data files
```

### Full Pipeline progressive loading (most complex):

1. CLAUDE.md (always)
2. daaf-orchestrator/SKILL.md (first user message)
3. full-pipeline-mode.md (after mode confirmation)
4. Pre-flight checklist presented (STOP for confirmation)
5. WORKFLOW_PHASE1_DISCOVERY.md (entering Phase 1)
6. WORKFLOW_PHASE2_PLANNING.md (entering Phase 2)
7. WORKFLOW_PHASE3_ACQUISITION.md (entering Phase 3)
8. WORKFLOW_PHASE4_ANALYSIS.md (entering Phase 4)
9. WORKFLOW_PHASE5_SYNTHESIS.md (entering Phase 5)
10. VALIDATION_CHECKPOINTS.md (when code execution begins)
11. ERROR_RECOVERY.md (when errors occur)

**Why it matters:** Each phase file is 200-500 lines. Loading all upfront would consume 2000-4000 lines before work begins. Progressive loading keeps orchestrator context lean.

---

## 6. Hook-Based Behavioral Enforcement

DAAF's hooks serve three distinct purposes:

### Safety (prevent harmful actions):
- `bash-safety.sh` — blocks destructive Bash commands
- `enforce-file-first.sh` — blocks direct Python execution (agent-scoped)
- `output-scanner.sh` — detects leaked secrets

### Behavioral enforcement (shape agent behavior):
- `remind-orchestrator.sh` — forces skill loading
- `enforce-explore-model.sh` — blocks low-capability subagent types
- `deny-claude-code-guide.sh` — blocks opaque built-in agent
- `enforce-foreground-agents.sh` — blocks background execution

### Observability (audit and monitoring):
- `context-reporter.sh` — continuous utilization monitoring
- `audit-log.sh` — complete tool invocation audit trail
- `archive-session.sh` — session transcript preservation
- `recover-session-logs.sh` — crash recovery

---

## 7. User-Level CLAUDE.md

**Does DAAF use `~/.claude/CLAUDE.md`?** No. DAAF relies entirely on project-level `/daaf/CLAUDE.md`.

---

## 8. The .claudeignore File

**Source:** `/daaf/.claudeignore` (13 lines) — prevents Claude Code from indexing sensitive files (`.env`, `*.pem`, `*.key`, `credentials*`, `secrets/`, `environment_settings*.txt`). Separate from `deny` permissions in settings.json — `.claudeignore` prevents discovery, deny rules prevent access.

---

## 9. Complete Information Flow

```
SESSION START
  Claude Code loads: System Prompt + CLAUDE.md + settings.json + system-reminders
  SessionStart hook: recover-session-logs.sh

USER SENDS FIRST MESSAGE
  UserPromptSubmit hooks:
    context-reporter.sh → utilization data
    remind-orchestrator.sh → "Load daaf-orchestrator NOW"
  Orchestrator loads skill → flag-orchestrator-loaded.sh sets flag
  Orchestrator: welcome → mode classification → confirmation (STOP)

USER CONFIRMS MODE
  Orchestrator loads mode reference file
  Progressive phase-by-phase execution begins
  Subagents dispatched as needed:
    Each subagent gets: System Prompt + CLAUDE.md + agent body + skills + prompt
    Project hooks fire on every tool call
    Subagent returns structured output to orchestrator

SESSION END
  archive-session.sh preserves transcripts
```

---

## 10. Key Migration Considerations

### Claude Code-Specific Primitives (must be reimplemented)

| Primitive | Migration Complexity | Notes |
|-----------|---------------------|-------|
| CLAUDE.md auto-loading | HIGH | Must inject project instructions into ALL agent contexts automatically |
| Agent tool + frontmatter | HIGH | Agent spawning with per-agent config, tools, permissions |
| Skill tool | MEDIUM | On-demand reference document injection into agent context |
| Hook system (5 event types) | HIGH | Runtime interception for safety and monitoring |
| Permission allow/deny | HIGH | Tool access control with three-tier matching |
| `<system-reminder>` injection | MEDIUM | System-level context injection mechanism |
| Output style setting | LOW | Response formatting control |
| `.claudeignore` | LOW | Sensitive file exclusion |

### Portable Content (text-based, harness-independent)

| Content | Scope | Notes |
|---------|-------|-------|
| CLAUDE.md | 1 file, 377 lines | Must inject into all agent contexts |
| Orchestrator skill | 1 + 12 reference files | Orchestrator-only instructions |
| Agent protocols | 15 files, 400-700 lines each | Per-agent behavioral specs |
| Domain skills | 36 skills | Reference material |
| Workflow phases | 5 files | Stage execution templates |
| Other references | ~20 files | Templates, checklists, standards |
