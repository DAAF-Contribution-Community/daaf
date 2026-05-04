## 6. Skill System: Progressive Knowledge Disclosure

**Classification: HYBRID** -- Claude Code provides the Skill tool, the SKILL.md file format, automatic filesystem discovery, and frontmatter-based preloading. DAAF designed the three-level progressive disclosure architecture, the "skills loaded by subagents, not orchestrator" governance model, the trust framework distinguishing curated knowledge from LLM inference, the metadata controlled vocabulary, the hook-enforced orchestrator loading chain, and all 36 domain-specific skills.

**Criticality:** HIGH | **Interdependencies:** 5 (instruction loading, agent system, hook system, context management, tool system)

---

### Design Intent

LLM agents need domain knowledge to perform specialized tasks -- an agent fetching education data needs to know which API endpoint to call, which variables to request, and which coded values mean what. But domain knowledge is expensive: each skill body consumes 2,000-5,000 words of context window, and a research framework may accumulate dozens of skills across multiple domains.

The fundamental tension is between **availability** (every agent should be able to find and access any skill it needs) and **context efficiency** (no agent should pay the token cost for knowledge it does not use). DAAF resolves this through progressive disclosure: a three-level architecture where all 36 skills are always discoverable at minimal cost (~3,600 words total for the metadata layer), but the full content of any given skill loads only when an agent determines it is relevant.

A secondary design problem is **trust calibration**. Skills contain curated, point-in-time knowledge that can go stale as APIs change, endpoints deprecate, and datasets update. More critically, when an agent acts on a skill's guidance and fills in details beyond what the skill explicitly states, that additional detail is LLM-generated inference, not curated knowledge. The framework must make this distinction visible so agents and human reviewers can calibrate their verification effort accordingly.

---

### What It Does

The skill system provides on-demand domain knowledge injection for agents. It maintains an inventory of 36 skills spanning data sources, Python libraries, research methodology, orchestration protocols, and meta-development guidance. Each skill consists of a structured entry point (SKILL.md) and optional reference files. The system allows any agent to discover all available skills at low cost, load the full instructions for a specific skill when needed, and drill into detailed reference material during execution -- all without consuming context budget in agents that never need a particular skill.

Beyond knowledge injection, the system enforces a governance model: skills are loaded by subagents in their own context windows, not by the orchestrator, protecting the orchestrator's limited context budget for coordination work. Three documented exceptions exist where the orchestrator loads skills directly.

---

### Current Realization on Claude Code

#### Skill Discovery and the Skill Tool (Native Primitives)

Claude Code discovers skills by scanning `.claude/skills/*/SKILL.md` at project level (and `~/.claude/skills/*/SKILL.md` at user-global level), walking up from the current working directory to the git worktree root. No manual registration is required -- placing a properly formatted SKILL.md in the correct directory makes it immediately available.

At session start (and at each subagent spawn), Claude Code extracts the `name` and `description` fields from every discovered skill's YAML frontmatter and injects them into the model's context as a `<system-reminder>` block listing available skills. This injection is the Level 1 metadata layer -- the always-on discovery mechanism.

The `Skill` tool is a first-class Claude Code tool that takes a single parameter -- the skill name -- and injects the full SKILL.md body into the calling agent's context. After loading, the agent can use the `Read` tool to access files in the skill's `references/` subdirectory.

#### SKILL.md Format (Native Format, DAAF-Designed Content)

Each SKILL.md begins with a YAML frontmatter block containing three recognized fields:

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `name` | Yes | String (max 64 chars) | Lowercase alphanumeric + hyphens; must match directory name |
| `description` | Yes | String (max 250 chars effective) | Truncated at ~250 chars in the system prompt; no angle brackets |
| `metadata` | No | Dict of strings | Key-value pairs using controlled vocabulary; ~100 words total |

The body below the frontmatter closing `---` is the skill's primary instruction set: decision trees, quick references, code patterns, and navigation pointers to reference files. DAAF targets under 500 lines and under 5,000 words per body.

Example frontmatter for a data source skill:

```yaml
---
name: education-data-source-ccd
description: >-
  CCD -- federal universe of all U.S. public K-12 schools (~100K) and
  districts (~18K). Enrollment, staffing, finance, directory data
  (1986-present). Use for public school analysis by grade/race/sex.
  Public only; excludes private and postsecondary.
metadata:
  audience: any-agent
  domain: data-source
  skill-authored: "2026-02-09"
  skill-last-updated: "2026-02-09"
---
```

#### Frontmatter Preloading (Native Primitive, DAAF-Configured)

Agent definition files can declare skills in their YAML frontmatter via the `skills:` field. Declared skills are injected into the agent's context at startup, without requiring the agent to call the Skill tool. This is used heavily: 12 of 14 DAAF agents preload at least one skill.

| Skill | Preloaded By |
|-------|-------------|
| `data-scientist` | 12 agents (all except `search-agent` and `framework-engineer`) |
| `marimo` | `notebook-assembler` |
| `skill-authoring` | `framework-engineer` |
| `agent-authoring` | `framework-engineer` |

#### The Hook-Enforced Orchestrator Loading Chain (DAAF-Built)

The `daaf-orchestrator` skill must load into the orchestrator's context at the start of every session. Because this is critical to DAAF's operation and cannot depend on the model reliably remembering to do it, DAAF uses three cooperating hooks to create a deterministic loading chain:

1. **`remind-orchestrator.sh`** (UserPromptSubmit hook, universal matcher): When the user sends their first message, this hook checks for a session-scoped flag file at `/tmp/claude-daaf-orchestrator-{session_id}`. If the flag does not exist, it emits a directive: "You MUST IMMEDIATELY invoke the daaf-orchestrator skill BEFORE doing any other work."

2. **The orchestrator calls `Skill(skill: "daaf-orchestrator")`**, loading the 592-line SKILL.md into its context.

3. **`flag-orchestrator-loaded.sh`** (PostToolUse hook, `Skill` matcher): After any Skill tool call, this hook checks whether the loaded skill was `daaf-orchestrator`. If so, it creates the flag file at `/tmp/claude-daaf-orchestrator-{session_id}`.

On subsequent user messages, `remind-orchestrator.sh` finds the flag and emits no reminder. The three hooks cooperate via a shared `/tmp` flag file to ensure the skill is loaded exactly once per session, regardless of model behavior.

---

### Design Choices and Rationale

**Skills load in subagents, not the orchestrator.** Each skill body consumes 2,000-5,000 words of context, and reference files can add substantially more. The orchestrator's context is a scarce, shared resource that must remain available for coordination across an entire multi-stage research session. Loading even a few skills directly into orchestrator context would consume 10,000-20,000 tokens -- context that cannot be reclaimed. Subagents, by contrast, each get a fresh context window; a skill loaded into a subagent's context is discarded when that subagent returns. This makes subagent context the appropriate place for domain knowledge, and orchestrator context the appropriate place for coordination state.

**Three exceptions exist for orchestrator skill loading.** In Ad Hoc Collaboration mode, the orchestrator loads `data-scientist` because the user is having a direct conversation about methodology and dispatching a subagent for every question would be disruptive. In Framework Development mode, the orchestrator loads `skill-authoring` and `agent-authoring` because it needs to advise on framework structure and coordinate integration checklists. These exceptions are documented in the orchestrator skill's loading decision tree, and the orchestrator limits itself to 2-3 directly loaded skills even in exception modes to avoid context pressure.

**The description is truncated to 250 characters.** Claude Code injects only the first ~250 characters of each skill's description into the system prompt. This is the ONLY text agents see when deciding whether to load a skill. The truncation is a forcing function: it compels skill authors to front-load the most important information -- what the skill covers, when to use it, and how to distinguish it from similar skills -- into a compact, high-signal summary. A description that buries key information after the 250-character mark effectively hides it from the triggering mechanism. The full description is preserved as a paragraph at the top of the SKILL.md body, available once the skill is loaded, but irrelevant for triggering decisions.

**Metadata uses a controlled vocabulary.** The `audience` and `domain` metadata fields draw from defined value sets (5 audience values, 8 domain values). This enables systematic inventory management and human auditing -- a maintainer can filter all data-source skills or all skills targeting research-coders. Importantly, these metadata fields are NOT used for programmatic agent routing at runtime; skill selection is driven by description text matching and explicit skill name references in orchestrator dispatch tables. The controlled vocabulary serves governance, not automation.

**The loading chain uses three cooperating hooks instead of a simpler mechanism.** A simpler approach would be to include the orchestrator skill's content in CLAUDE.md or inject it via a single hook. The three-hook chain exists because each alternative has a specific failure mode. Embedding in CLAUDE.md would add 592 lines to every agent's context, violating the "skills load in subagents" principle and wasting tokens in all 14 subagent types. A single hook that injects the full skill content would bypass the Skill tool's loading mechanism, losing the standard injection path and preventing the agent from reading the skill's reference files through the normal skill interface. The three-hook approach uses standard Claude Code primitives (a reminder on user message, the Skill tool, a post-tool flag) composed to achieve deterministic behavior: the reminder ensures the model calls the tool, the tool provides proper loading, and the flag ensures the reminder stops. Each hook is simple and independently testable.

**Provenance metadata enables staleness detection.** Data source skills carry `skill-authored` and `skill-last-updated` ISO-8601 date fields. These allow agents to assess whether a skill's factual claims (API endpoints, coded values, variable names) may have drifted since the skill was last verified. An agent working with a skill whose `skill-last-updated` date is several months old treats its claims with appropriate caution and flags uncertainty in its output. This is not automated enforcement -- it is a calibration signal for agents and human reviewers.

---

### The Three-Level Progressive Disclosure Architecture

This is the core architectural contribution of the skill system.

| Level | Content | When Loaded | Token Cost | Purpose |
|-------|---------|-------------|------------|---------|
| **1: Metadata** | `name` + truncated `description` for all 36 skills | At every agent startup | ~3,600 words (fixed) | Discovery -- agents decide which skills to load |
| **2: Body** | Full SKILL.md content (decision trees, quick references, navigation) | When a skill is triggered or preloaded | <5,000 words per skill | Detailed instructions and reference file navigation |
| **3: Resources** | Files in `references/`, `scripts/`, `assets/` directories | During execution, on demand via Read tool | Variable (no limit) | Deep reference material, API details, variable definitions |

**Level 1 is the fixed cost of the system.** With 36 skills at approximately 100 words each, every agent pays ~3,600 words for the ability to discover and load any skill. This is the price of availability. The 250-character truncation keeps this cost bounded as the skill inventory grows.

**Level 2 is the per-task cost.** A typical agent loads 1-2 skills during execution, adding 2,000-10,000 words. The SKILL.md body is deliberately concise ("Concise is Key" is the authoring principle), containing decision trees and quick references that point to Level 3 resources rather than inlining all detail.

**Level 3 is the on-demand cost.** Reference files are loaded individually via the Read tool. They follow the inverse principle ("Thorough is Key") -- because their token cost is only incurred when specifically needed, they encode all discovered knowledge comprehensively. The `references/` directory is flat (one level, no nesting), with descriptively named files (e.g., `variable-definitions.md`, `quickstart.md`, `gotchas.md`).

---

### Skill Loading Paths

Agents receive skills through four distinct paths:

| Path | Mechanism | When Used |
|------|-----------|-----------|
| **Frontmatter preloading** | `skills:` field in agent YAML frontmatter | Agent needs the skill for every invocation (e.g., all coding agents preload `data-scientist`) |
| **Explicit Skill tool call** | Agent calls `Skill(skill: "name")` during execution | Agent determines during task execution that it needs a specific skill |
| **Orchestrator prompt instruction** | Orchestrator includes "Call the skill tool with name X" in the Agent dispatch prompt | Orchestrator knows which skill the subagent will need based on the task |
| **Slash command** | User types `/skillname` in conversation | User directly triggers a skill for immediate context injection |

Frontmatter preloading and explicit loading are complementary. Preloaded skills are available at startup without a tool call; calling the Skill tool for an already-preloaded skill would load it a second time, wasting context tokens. Agent protocols are designed to be aware of their preloaded skills and call the Skill tool only for additional skills needed for a specific task.

---

### Skill Categories and Trust Model

#### Eight Domain Categories (36 Skills)

| Domain | Count | Description |
|--------|-------|-------------|
| `data-source` | 16 | Reference guides for specific datasets (CCD, IPEDS, CRDC, etc.) |
| `python-library` | 11 | Library API reference and patterns (polars, pyfixest, plotnine, etc.) |
| `data-access` | 2 | Data fetching and discovery mechanisms |
| `data-documentation` | 1 | Cross-source interpretation guidance |
| `research-methodology` | 1 | Analytical approach and method selection |
| `research-orchestration` | 1 | Orchestrator operational protocol |
| `research-communication` | 1 | Translating findings for audiences |
| `skill-development` | 3 | Meta-skills for building framework components |

#### Trust Model: Curated Knowledge vs. LLM Inference

Skills contain **curated domain knowledge** -- point-in-time snapshots that represent a human-verified (or at least deliberately authored) understanding of a data source, library, or methodology. This curated knowledge can drift as the external world changes, but it represents a known baseline with a known verification date.

When an agent fills in details *beyond* what a skill explicitly states -- inferring an API parameter, guessing a coded value, or extrapolating from similar data sources -- that is **LLM-generated inference**, not curated knowledge. The trust model requires different verification protocols for each:

- **Curated knowledge:** Agents with web access (`WebSearch`, `WebFetch`) should verify skill-sourced details when results are unexpected or when the `skill-last-updated` date suggests potential staleness. Agents without web access flag uncertainty in their return output.
- **LLM inference:** Any detail an agent adds beyond what the skill explicitly provides should be treated with greater skepticism. CLAUDE.md encodes this distinction: "information that an agent supplies *beyond* what is explicitly encoded in a skill is LLM-generated inference -- not curated knowledge -- and should be verified with even greater diligence."

This trust distinction is enforced by convention and instruction, not by runtime mechanism. It depends on agents understanding the boundary between what a skill says and what they are inferring.

---

### Complete Skill Inventory

| # | Skill Name | Domain | Preloaded By | Audience |
|---|-----------|--------|--------------|----------|
| 1 | `agent-authoring` | skill-development | framework-engineer | any-agent |
| 2 | `daaf-orchestrator` | research-orchestration | *(hook-loaded by orchestrator)* | research-orchestrator |
| 3 | `data-scientist` | research-methodology | 13 agents (all except search-agent, framework-engineer) | any-agent |
| 4 | `education-data-context` | data-documentation | *(on demand)* | any-agent |
| 5 | `education-data-explorer` | data-access | *(on demand)* | research-planner |
| 6 | `education-data-query` | data-access | *(on demand)* | research-coders |
| 7 | `education-data-source-campus-safety` | data-source | *(on demand)* | any-agent |
| 8 | `education-data-source-ccd` | data-source | *(on demand)* | any-agent |
| 9 | `education-data-source-crdc` | data-source | *(on demand)* | any-agent |
| 10 | `education-data-source-eada` | data-source | *(on demand)* | any-agent |
| 11 | `education-data-source-edfacts` | data-source | *(on demand)* | any-agent |
| 12 | `education-data-source-fsa` | data-source | *(on demand)* | any-agent |
| 13 | `education-data-source-ipeds` | data-source | *(on demand)* | any-agent |
| 14 | `education-data-source-meps` | data-source | *(on demand)* | any-agent |
| 15 | `education-data-source-nacubo` | data-source | *(on demand)* | any-agent |
| 16 | `education-data-source-nccs` | data-source | *(on demand)* | any-agent |
| 17 | `education-data-source-nhgis` | data-source | *(on demand)* | any-agent |
| 18 | `education-data-source-pseo` | data-source | *(on demand)* | any-agent |
| 19 | `education-data-source-saipe` | data-source | *(on demand)* | any-agent |
| 20 | `education-data-source-scorecard` | data-source | *(on demand)* | any-agent |
| 21 | `election-data-source-countypres` | data-source | *(on demand)* | any-agent |
| 22 | `geopandas` | python-library | *(on demand)* | research-coders |
| 23 | `linearmodels` | python-library | *(on demand)* | research-coders |
| 24 | `marimo` | python-library | notebook-assembler | research-coders |
| 25 | `plotly` | python-library | *(on demand)* | research-coders |
| 26 | `plotnine` | python-library | *(on demand)* | research-coders |
| 27 | `polars` | python-library | *(on demand)* | research-coders |
| 28 | `pyfixest` | python-library | *(on demand)* | research-coders |
| 29 | `r-python-translation` | python-library | *(on demand)* | research-coders |
| 30 | `science-communication` | research-communication | *(on demand)* | research-writers |
| 31 | `scikit-learn` | python-library | *(on demand)* | research-coders |
| 32 | `shell-scripting` | skill-development | *(on demand)* | research-coders |
| 33 | `skill-authoring` | skill-development | framework-engineer | any-agent |
| 34 | `stata-python-translation` | python-library | *(on demand)* | research-coders |
| 35 | `statsmodels` | python-library | *(on demand)* | research-coders |
| 36 | `svy` | python-library | *(on demand)* | research-coders |

---

### Replication Specification

**Required capabilities in the target harness:**

1. **Skill discovery via filesystem scanning.** The harness must automatically discover skill definition files (or equivalent) by scanning a designated directory. Discovery must be automatic -- adding a new skill file makes it available without modifying any registration file.
2. **Metadata injection into all agent contexts.** At session start and at each subagent spawn, the harness must inject a compact summary (name + short description) of all available skills into the agent's context. This is the Level 1 layer. The summary must be concise enough that the full inventory fits within a few thousand tokens.
3. **On-demand content loading.** The harness must provide a mechanism (tool, function, or equivalent) for agents to load the full body of a specific skill into their context mid-conversation. This is the Level 2 layer.
4. **Reference file access.** After loading a skill, agents must be able to read additional files from the skill's directory structure. This is the Level 3 layer. Any file-reading mechanism suffices.
5. **Agent-level skill preloading.** The harness must support declaring skills in agent configuration so that skill content is injected at agent startup without requiring an explicit loading call.
6. **Independent subagent context windows.** Skills loaded by subagents must not consume the orchestrator's context. This requires subagents to have their own context windows -- shared-context architectures would defeat the "skills in subagents" governance model.

**Behavioral contract:**

- Level 1 metadata is always present in every agent context. An agent that has never loaded a skill can still see the names and descriptions of all available skills.
- Level 2 loading is idempotent but additive. Loading the same skill twice injects the content twice, consuming double the context tokens. The framework relies on agents being aware of their preloaded skills to avoid duplicate loading.
- Level 3 access uses standard file-reading mechanisms. No special skill-aware file access is needed.
- The description truncation length (250 characters in Claude Code) must be documented for the target harness so skill authors can optimize their descriptions accordingly.

**Acceptance criteria:**

- Feature parity is achieved when: (a) new skills are discoverable without modifying configuration files, (b) all agents see a compact skill inventory in their context at startup, (c) agents can load specific skills on demand during execution, (d) agents can read reference files from loaded skills, (e) agent configuration can declare skills for automatic preloading, (f) skill loading in subagents does not consume orchestrator context, and (g) a deterministic mechanism ensures the orchestrator's operational skill loads at session start regardless of model behavior.

**Degraded-mode options:**

- Without automatic discovery: a manifest file listing skills is acceptable but adds a manual registration step that discovery eliminates.
- Without metadata injection: agents can be given a static skills inventory document, but this loses automatic synchronization when skills are added or removed.
- Without a dedicated skill-loading tool: embedding skill content directly in agent prompts (orchestrator copies relevant skill text into dispatch prompts) is functional but shifts the context cost to the orchestrator and couples skill content to dispatch logic.
- Without independent subagent contexts: all skill loading consumes the shared context. The governance model of "skills in subagents" collapses, requiring aggressive skill selection to avoid exhausting the context window.

---

### Harness Landscape

- **Codex (OpenAI):** Supports `AGENTS.md` and the emerging `agentskills.io` open standard. Skill discovery and loading mechanisms are converging toward SKILL.md-compatible patterns. Closest parity for the skill system overall.
- **Cursor:** Custom instructions and rules files; agent skills support emerging. Partial parity for metadata injection; skill-loading tool would need to be built or adapted.
- **OpenCode:** Supports custom instructions and tool definitions. Skill-equivalent loading would require plugin development.
- **Windsurf / Aider:** Limited custom instruction support. The three-level progressive disclosure architecture would need to be implemented as a middleware layer.

---

### Dependencies

| Depends On | Relationship |
|------------|-------------|
| **Instruction Loading (Section 3)** | Skills are Layer 8 of the 10-layer instruction hierarchy; CLAUDE.md carries the trust model and skill awareness instructions that all agents inherit |
| **Agent System (Section 4)** | The `skills:` frontmatter field in agent definitions is the mechanism for preloading; skill loading governance depends on the orchestrator/subagent dispatch model |
| **Hook System (Section 7)** | The deterministic orchestrator loading chain uses three hooks (remind-orchestrator, the Skill tool call, flag-orchestrator-loaded) cooperating via a `/tmp` flag file |
| **Context Management (Section 8)** | Progressive disclosure exists to manage context budget; the "skills in subagents" principle is a context-efficiency strategy |

| Depended On By | Relationship |
|----------------|-------------|
| **Agent System (Section 4)** | 12 of 14 agents preload skills; agent behavioral quality depends on domain knowledge availability |
| **Logging/Audit (Section 9)** | The file-first execution protocol is documented in skills (data-scientist, library skills); agents learn it from both CLAUDE.md and skill content |
| **Tool System (Section 10)** | Per-agent tool restrictions interact with skill loading -- agents without the Skill tool cannot load skills on demand |
