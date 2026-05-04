# DAAF Skill System: Complete Architecture Reference

## 1. Overview

The DAAF skill system is built on Claude Code's native skill infrastructure. Skills provide **domain knowledge** (answering "What do I need to know?") as opposed to agents, which define **behavioral protocols** (answering "How should I behave?"). The system implements a three-level progressive disclosure architecture that optimizes context window usage by loading information only when needed.

**Scale:** 36 skills across 36 directories, with 251 reference files and 5 bundled scripts. Total SKILL.md content is 12,259 lines across all skills (ranging from 171 to 827 lines per skill).

---

## 2. Skill Directory Structure

### 2.1 Top-Level Organization

All skills live under `.claude/skills/` in the project root. Each skill occupies its own directory named identically to the skill's `name` frontmatter field:

```
.claude/skills/
├── agent-authoring/
├── daaf-orchestrator/
├── data-scientist/
├── education-data-context/
├── education-data-explorer/
├── education-data-query/
├── education-data-source-campus-safety/
├── education-data-source-ccd/
├── education-data-source-crdc/
├── education-data-source-eada/
├── education-data-source-edfacts/
├── education-data-source-fsa/
├── education-data-source-ipeds/
├── education-data-source-meps/
├── education-data-source-nacubo/
├── education-data-source-nccs/
├── education-data-source-nhgis/
├── education-data-source-pseo/
├── education-data-source-saipe/
├── education-data-source-scorecard/
├── election-data-source-countypres/
├── geopandas/
├── linearmodels/
├── marimo/
├── plotly/
├── plotnine/
├── polars/
├── pyfixest/
├── r-python-translation/
├── science-communication/
├── scikit-learn/
├── shell-scripting/
├── skill-authoring/
├── stata-python-translation/
├── statsmodels/
└── svy/
```

### 2.2 Internal Directory Structure (Per Skill)

Every skill has the same canonical structure:

```
.claude/skills/<name>/
├── SKILL.md              # REQUIRED — entry point with YAML frontmatter + body
├── references/           # OPTIONAL — on-demand documentation files
├── scripts/              # OPTIONAL — executable code bundled with the skill
└── assets/               # OPTIONAL — templates, images, config files
```

**Observed patterns in DAAF:**
- All 36 skills have `SKILL.md` (required)
- All 36 skills have a `references/` subdirectory (100% adoption in DAAF)
- Only 1 skill (`election-data-source-countypres`) has a `scripts/` subdirectory, containing 5 Python profiling scripts
- No skills use an `assets/` subdirectory (0% adoption in DAAF)

### 2.3 References Directory Pattern

The `references/` subdirectory is flat (one level deep, no nesting). Files are named descriptively with hyphens:

```
# Example: polars skill
references/
├── aggregations-grouping.md
├── dataframes-series.md
├── expressions.md
├── gotchas.md
├── interop.md
├── io-data.md
├── joins-concat.md
├── performance.md
├── quickstart.md
└── strings-datetime-categorical.md
```

Common reference file naming conventions across skills:
- `quickstart.md` — getting started guides (tool skills)
- `gotchas.md` — common errors and anti-patterns (tool skills)
- `variable-definitions.md` — coded values and variable meanings (data source skills)
- `data-quality.md` — quality issues and limitations (data source skills)
- `historical-changes.md` — definition changes over time (data source skills)

### 2.4 Skill Categories

DAAF classifies skills using the `domain` metadata field into these categories:

| Category | `domain` Value | Count | Examples |
|----------|---------------|-------|----------|
| Data Source | `data-source` | 16 | `education-data-source-ccd`, `election-data-source-countypres` |
| Python Library / Tool | `python-library` | 11 | `polars`, `pyfixest`, `plotnine`, `statsmodels` |
| Data Access | `data-access` | 2 | `education-data-query`, `education-data-explorer` |
| Data Documentation | `data-documentation` | 1 | `education-data-context` |
| Research Methodology | `research-methodology` | 1 | `data-scientist` |
| Research Orchestration | `research-orchestration` | 1 | `daaf-orchestrator` |
| Research Communication | `research-communication` | 1 | `science-communication` |
| Skill Development (meta) | `skill-development` | 3 | `skill-authoring`, `agent-authoring` |

---

## 3. SKILL.md Frontmatter Specification

### 3.1 Complete Field Reference

The frontmatter is a YAML block delimited by `---` that must start on line 1 of SKILL.md.

| Field | Required | Type | Max Length | Constraints |
|-------|----------|------|------------|-------------|
| `name` | **Yes** | String | 64 chars | Lowercase alphanumeric + hyphens; must match directory name; regex: `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `description` | **Yes** | String | **250 chars effective** (1024 YAML max) | No angle brackets (`<` `>`); truncated at 250 chars in system prompt |
| `metadata` | No | Dict of strings | ~100 words total | Key-value pairs, all values must be strings |

**Only these three fields are recognized.** Unknown fields are silently ignored.

### 3.2 Frontmatter Examples from Actual DAAF Skills

**Data source skill (with provenance metadata):**
```yaml
---
name: education-data-source-ccd
description: >-
  CCD — federal universe of all U.S. public K-12 schools (~100K) and
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

**Python library skill (with version tracking):**
```yaml
---
name: polars
description: >-
  Polars DataFrame library for high-performance data manipulation.
  Lazy/eager execution, expressions, I/O (CSV, Parquet, JSON),
  aggregations, joins, string/datetime ops, pandas interop. Use for
  Polars DataFrames or reading/writing Parquet files.
metadata:
  audience: research-coders
  domain: python-library
  library-version: "1.x"
  skill-last-updated: "2026-03-26"
---
```

**Operational skill (orchestrator-only):**
```yaml
---
name: daaf-orchestrator
description: >-
  Operational framework for the DAAF orchestrator. Defines engagement
  modes, confirmation protocol, subagent dispatch, context budget, and
  reference-loading. Loaded exclusively by the orchestrator — not for
  subagents or user questions.
metadata:
  audience: research-orchestrator
  domain: research-orchestration
---
```

**Meta/development skill (minimal metadata):**
```yaml
---
name: skill-authoring
description: >-
  Guide for creating and auditing DAAF skills (SKILL.md). Covers
  frontmatter, metadata vocabulary, progressive disclosure, decision
  trees, reference files. Use when creating, reviewing, or debugging
  skill loading. For agent files, use agent-authoring.
metadata:
  audience: any-agent
  domain: skill-development
---
```

### 3.3 Metadata Controlled Vocabulary

DAAF defines a controlled vocabulary for the two primary metadata keys:

**`audience` — which agent role benefits from this skill:**

| Value | Targets | Example Skills |
|-------|---------|----------------|
| `any-agent` | Broadly useful across roles | data sources, data-scientist, skill-authoring |
| `research-orchestrator` | Orchestrator agent only | daaf-orchestrator |
| `research-planner` | Planning/discovery agents | education-data-explorer |
| `research-coders` | Anyone writing or reviewing code | Python libraries, education-data-query |
| `research-writers` | Anyone writing or reviewing narrative | science-communication |

**`domain` — functional category:**

| Value | Covers | Example Skills |
|-------|--------|----------------|
| `data-source` | Reference guides for specific datasets | education-data-source-ccd |
| `data-access` | Fetching/discovering data | education-data-query |
| `data-documentation` | Provenance, caveats, interpretation | education-data-context |
| `python-library` | Library syntax/API reference | polars, plotly, statsmodels |
| `research-methodology` | Analytical approach, rigor, mindset | data-scientist |
| `research-orchestration` | Workflow/pipeline management | daaf-orchestrator |
| `research-communication` | Translating findings for audiences | science-communication |
| `skill-development` | Meta-skills for building skills/agents | skill-authoring |

**Additional standard metadata keys:**

| Key | Purpose | Example | When Required |
|-----|---------|---------|---------------|
| `library-version` | Library version tracked | `"1.x"`, `"0.40.0"` | Python library skills only |
| `skill-authored` | ISO-8601 creation date | `"2026-02-09"` | Data source skills (required) |
| `skill-last-updated` | ISO-8601 last-verified date | `"2026-02-09"` | Data source skills (required); library skills (recommended) |

**Important:** These metadata fields are used for inventory management and human auditing, NOT for programmatic agent routing. Skill selection at runtime is driven by description text matching and explicit skill name references in dispatch tables.

### 3.4 The Description Field: Critical Design

The `description` field is the **primary triggering mechanism** for Claude Code's skill matching. It has specific design requirements:

1. **250-character hard limit** — Claude Code truncates descriptions at ~250 chars in the system prompt. Text beyond this is silently dropped. This is the ONLY text agents see when deciding whether to load a skill.

2. **Must include (within 250 chars):**
   - What the skill does (identity + scope)
   - When to use it (key triggering conditions)
   - Disambiguation from similar skills (e.g., "For FE use pyfixest; for GLM use statsmodels")

3. **Writing conventions:**
   - Third-person voice ("Processes files" not "I help you process files")
   - Slightly "pushy" to combat undertriggering
   - Front-load important words (may be truncated in UI)
   - Include negative triggers to prevent overtriggering

4. **Full description in body:** Since 250 chars is insufficient for complete context, the full description is preserved as a plain paragraph immediately after the `# Title` heading in the SKILL.md body. This provides complete context once the skill is loaded but does NOT influence triggering decisions.

---

## 4. SKILL.md Body Content Patterns

### 4.1 Body Structure

The SKILL.md body (everything after the frontmatter closing `---`) is the skill's primary instruction set. It follows these constraints:

| Constraint | Guideline |
|------------|-----------|
| Line count | <500 lines recommended |
| Word count | <5000 words |
| Writing style | Imperative/infinitive form |
| Content focus | Examples over explanations |

**Actual DAAF sizes (lines per SKILL.md):**
- Smallest: `plotnine` at 171 lines
- Median: ~310 lines
- Largest: `data-scientist` at 827 lines (the one skill exceeding the 500-line guideline)
- Average: ~340 lines

### 4.2 Standard Section Layout

Most DAAF skills follow this section pattern:

1. **`# Title`** — Skill name as heading
2. **Full description paragraph** — Expanded description that couldn't fit in frontmatter
3. **"What is X?" section** — Brief intro with bullet points
4. **Version Notes** (library skills only) — Tracked version and breaking changes
5. **"Reference File Structure" table** — Maps reference files to purposes and loading triggers
6. **Decision Trees** — ASCII tree diagrams routing to reference files based on user need
7. **Quick Reference** — Essential tables, code patterns, core concepts
8. **Common Pitfalls** — Table of known issues with solutions
9. **Related Skills/Data Sources** — Cross-references to other skills
10. **Topic Index** — Final section mapping all topics to reference file locations
11. **Citation** (library skills) — How to cite the tool in reports

### 4.3 Decision Tree Pattern

Decision trees are DAAF's primary navigation mechanism within skills. They use ASCII box-drawing characters and point to reference files:

```
What kind of regression?
├─ OLS with fixed effects → ./references/quickstart.md
├─ OLS without fixed effects → ./references/quickstart.md
├─ IV / 2SLS → ./references/instrumental-variables.md
├─ Poisson (count data) → ./references/integration.md
└─ Multiple models at once → ./references/integration.md
```

Conventions:
- Use `├─`, `└─`, `│` for box-drawing
- Keep to 2-3 levels of nesting
- Use `→` for pointing to targets
- Each leaf points to a specific reference file or section

### 4.4 Four Body Patterns

The skill-authoring skill defines four structural patterns for SKILL.md bodies:

| Pattern | Best For | Structure |
|---------|----------|-----------|
| **Workflow-Based** | Sequential processes, decision flows | Overview → Decision Tree → Steps |
| **Task-Based** | Collections of related tools/operations | Quick Start → Task sections → Quick Reference |
| **Reference-Based** | Standards, specifications, guidelines | Overview → Guidelines → Specs → Examples |
| **Capabilities-Based** | Platform integrations, feature-rich tools | Core Capabilities → Feature sections |

Most DAAF skills mix the Workflow-Based and Reference-Based patterns.

---

## 5. Progressive Disclosure: The Three-Level Loading System

This is the core architectural insight of the skill system. Content loads in stages to optimize context window usage.

### 5.1 Three Loading Levels

| Level | Content | When Loaded | Token Cost | Purpose |
|-------|---------|-------------|------------|---------|
| **1: Metadata** | `name` + `description` (from frontmatter) | At agent startup, for ALL installed skills | ~100 words/skill | Discovery and matching — agents decide which skills to load |
| **2: Body** | SKILL.md body (everything after frontmatter) | When the skill triggers / is explicitly loaded | <5000 words | Detailed instructions, decision trees, quick references |
| **3: Resources** | `references/`, `scripts/`, `assets/` | During execution, on demand | Variable | Implementation details, deep reference material |

### 5.2 Level 1: Always in Context

At the start of every conversation (and every subagent context), Claude Code injects the **name and description** of ALL installed skills into the system prompt. This is visible in the conversation as a `<system-reminder>` block listing available skills.

**Example from actual system prompt injection:**
```
The following skills are available for use with the Skill tool:
- polars: Polars DataFrame library for high-performance data manipulation...
- education-data-source-ccd: CCD — federal universe of all U.S. public K-12 schools...
[...all 36 skills listed...]
```

With 36 skills at ~100 words each, the Level 1 metadata consumes roughly 3,600 words of every agent's context window. This is the fixed cost of the skill system.

### 5.3 Level 2: On Skill Trigger

When an agent calls the `Skill` tool (e.g., `Skill({ skill: "polars" })`), the FULL body of SKILL.md is injected into the agent's conversation context. This gives the agent the decision trees, quick references, and navigation to Level 3 resources.

### 5.4 Level 3: On Demand During Execution

After loading a skill (Level 2), agents use the decision trees and reference file tables to identify which specific reference files they need. They then use the `Read` tool to load only the relevant reference files into context.

**Key design principle for Level 3:**
- **SKILL.md (Level 2) should be CONCISE** — "Concise is Key." Justify every token because this content shares context with conversation history.
- **Reference files (Level 3) should be THOROUGH** — "Thorough is Key." Their token cost is only incurred when specifically needed, so they should encode all discovered knowledge comprehensively rather than summarizing.

### 5.5 Token Budget Guidelines

| Component | Budget | Notes |
|-----------|--------|-------|
| All skill metadata (Level 1) | ~100 words x N skills | Always loaded; fixed cost |
| Active skill body (Level 2) | <5000 words | One skill at a time typically |
| Loaded references (Level 3) | No hard limit | Load only what's needed |
| Scripts | ~0 tokens | Executed via Bash, not read into context |
| Assets | 0 tokens | Used directly in output, not read |

### 5.6 When to Split Content into References

Content should move from SKILL.md body to `references/` when:
1. SKILL.md approaches 300-400 lines
2. Content is domain-specific and not always needed
3. Framework/variant alternatives exist (only one used at a time)
4. Detailed API docs support but don't drive the workflow

**Keep in SKILL.md body:**
- Core workflow/process
- Decision trees for navigation
- Quick reference tables
- Topic index pointing to references

---

## 6. Skill Loading Mechanics

### 6.1 How Claude Code Discovers Skills

Claude Code discovers skills via filesystem scanning at these locations (searched in order):

| Location | Scope | Path |
|----------|-------|------|
| Project config | Project-local | `.claude/skills/<name>/SKILL.md` |
| Global config | User-global | `~/.claude/skills/<name>/SKILL.md` |

For project-local paths, Claude Code walks up from the current directory to the git worktree root. **No manual registration is needed** — placing a properly formatted SKILL.md in the correct directory makes it immediately available.

### 6.2 The Skill Tool

The `Skill` tool is a first-class Claude Code tool available to any agent that has it in their `tools` list. It takes a single parameter:

```
Skill({ skill: "skill-name" })
```

When invoked:
1. Claude Code looks up the skill by name
2. The FULL content of `SKILL.md` is injected into the current conversation context
3. The agent can then read reference files from the skill's `references/` directory using the `Read` tool
4. The agent can execute scripts from the skill's `scripts/` directory using the `Bash` tool

### 6.3 The `/skillname` Slash Command

Users can trigger skills via slash commands (e.g., `/polars`). Claude Code matches the text after `/` to skill names in the available skills list. When matched, it invokes the Skill tool with that name, injecting the SKILL.md content into context.

### 6.4 Skill Loading via Agent Frontmatter (`skills:` field)

Agents can preload skills by declaring them in their YAML frontmatter. This causes the skill content to be injected into the agent's context at startup, without requiring the agent to explicitly call the Skill tool.

**Single skill preload:**
```yaml
skills: data-scientist
```

**Multiple skills preload:**
```yaml
skills:
  - data-scientist
  - marimo
```

**When preloaded:**
- The full SKILL.md body is injected at agent startup
- The agent does NOT need to call the Skill tool for preloaded skills
- Calling the Skill tool for an already-preloaded skill would load it a second time, wasting context tokens

**Current DAAF preload assignments:**

| Skill | Assigned to (via frontmatter) |
|-------|-------------------------------|
| `data-scientist` | research-executor, code-reviewer, debugger, data-ingest, data-planner, plan-checker, data-verifier, source-researcher, research-synthesizer, integration-checker, report-writer, notebook-assembler (12 agents) |
| `marimo` | notebook-assembler |
| `skill-authoring` | framework-engineer |
| `agent-authoring` | framework-engineer |

### 6.5 The Settings.json Role

In `/daaf/.claude/settings.json`, the `Skill` tool appears in the allow list (line 36), meaning agents can call it without permission prompts. There is also a `PostToolUse` hook on the `Skill` matcher:

```json
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
```

This hook (`flag-orchestrator-loaded.sh`) sets a session-scoped flag file when the `daaf-orchestrator` skill is loaded, which is used by a reminder hook to stop issuing "load the orchestrator skill" reminders once it has been loaded.

---

## 7. DAAF's Skill Loading Patterns

### 7.1 The Core Principle: Skills Loaded by Subagents, Not Orchestrator

The orchestrator's SKILL.md explicitly states:

> "Skills are loaded **by subagents**, not by the orchestrator."

The loading lifecycle:
1. **Orchestrator creates Agent call** with agent protocol and skill name in the prompt
2. **Subagent receives prompt** and reads its agent protocol file
3. **Subagent calls Skill tool** to load specialized knowledge into its own context
4. **Subagent follows agent protocol** using the skill's guidance
5. **Subagent returns findings** to orchestrator (concise, focusing on key findings)

**What the orchestrator does NOT do:**
- Call the Skill tool directly in orchestrator context (with exceptions below)
- Pre-load all skills at conversation start
- Copy skill content into prompts to subagents

### 7.2 Orchestrator Skill Loading Exceptions

There are exactly **three documented exceptions** where the orchestrator loads skills directly:

| Exception | Mode | Skill(s) Loaded | Rationale |
|-----------|------|-----------------|-----------|
| 1 | Ad Hoc Collaboration | `data-scientist` | Orchestrator responds directly to user with methodology advice; needs the skill without dispatching a subagent for every question |
| 2 | Framework Development | `skill-authoring` | Orchestrator advises on framework structure, template requirements |
| 3 | Framework Development | `agent-authoring` | Orchestrator coordinates integration checklists, answers agent structure questions |

These are marked in the orchestrator's loading decision tree with the annotation: `(orchestrator loads directly — exception to standard pattern)`.

### 7.3 How Subagents Know Which Skills to Load

Skills are communicated to subagents through multiple channels:

1. **Agent frontmatter `skills:` field** — Skills preloaded at agent startup (see Section 6.4). The agent doesn't need to do anything; the content is already available.

2. **Orchestrator prompt instructions** — The orchestrator includes skill names in the Agent tool prompt. Example from the research-executor's documentation:
   ```
   Call the skill tool only for additional stage-specific skills:
   - Stage 5: Load the domain-specific query skill (name provided in Agent prompt)
   - Stage 8: Load library skills as needed (pyfixest, statsmodels, etc.)
   ```

3. **Agent protocol decision trees** — Agent definition files contain decision trees that tell the agent when to load which skills. For example, the `data-scientist` skill's body contains an extensive decision tree mapping task types to library skills.

4. **Skill cross-references** — Skills themselves reference other skills. For example, the `education-data-context` skill says: "For comprehensive understanding beyond the quick context files above, load the dedicated data source skill."

### 7.4 Context Budget Implications

The orchestrator's context budget rules explicitly account for skill loading costs:

**What Gets Delegated to Subagents (because of context cost):**
- Skill invocations (skills add 5K-20K tokens)
- Data exploration (iterative searching fills context)
- Source deep-dives (reference docs are large)

**What Never Goes in Orchestrator Context:**
- Full skill content (let subagents load)
- Raw data samples (only shapes and summaries)
- Complete code files (only references)

The orchestrator limits itself to 2-3 directly loaded skills even in exception modes, with the ad-hoc mode documentation explicitly noting: "If the orchestrator has loaded more than 2-3 skills directly, prefer dispatching to subagents for subsequent tasks to avoid context pressure."

---

## 8. Skill Content Patterns by Category

### 8.1 Data Source Skills

The largest category (16 skills). These encode domain knowledge about specific datasets.

**Distinctive features:**
- Required `skill-authored` and `skill-last-updated` metadata for provenance tracking
- "CRITICAL: Value Encoding" callout box near the top
- "Truth Hierarchy" section (data file > codebook > skill documentation)
- "Data Access" section with mirror paths and codebook references
- "Common Pitfalls" table (issue/solution format)
- "Related Data Sources" cross-reference table
- Reference files typically include: `variable-definitions.md`, `data-quality.md`, `historical-changes.md`

**Size range:** 282-472 lines (SKILL.md body); reference files collectively target 3x+ the SKILL.md line count

### 8.2 Python Library / Tool Skills

11 skills covering data manipulation, visualization, statistical modeling, etc.

**Distinctive features:**
- `library-version` metadata field
- "Version Notes" section documenting breaking changes
- "File-First Execution in Research Workflows" section (DAAF-specific integration)
- Code examples throughout (both in SKILL.md and references)
- "Citation" section at the bottom for report attribution
- Reference files typically include: `quickstart.md`, `gotchas.md`, domain-specific topic files

**Size range:** 171-335 lines

### 8.3 Methodology/Orchestration Skills

Small category (2 skills: `data-scientist`, `daaf-orchestrator`).

**Distinctive features:**
- Much larger than other categories (`data-scientist` at 827 lines, `daaf-orchestrator` at 592 lines)
- Extensive decision trees routing to library skills or reference files
- "Related Skills — When to Load" section with dependency trees
- `daaf-orchestrator` contains the mode classification framework and loading decision tree

### 8.4 Meta/Development Skills

3 skills (`skill-authoring`, `agent-authoring`, `shell-scripting`).

**Distinctive features:**
- Teach how to create other framework components
- Extensive template examples and validation checklists
- Cross-reference authoritative template files in `agent_reference/`

---

## 9. Skill Registration and Discovery

### 9.1 Automatic Discovery

Skills are automatically discovered by Claude Code via their YAML frontmatter. No manual registration in any configuration file is needed for the skill to appear in the available skills list. Placing a properly formatted SKILL.md in `.claude/skills/<name>/` makes it immediately available.

### 9.2 Framework Integration Beyond Discovery

While discovery is automatic, DAAF has additional integration points that require manual wiring:

1. **Agent frontmatter `skills:` field** — If the skill should be preloaded by specific agents
2. **Pipeline stage mappings** — If the skill should be referenced in workflow phase documents
3. **Orchestrator dispatch tables** — If the orchestrator should name the skill in agent prompts
4. **Documentation cross-references** — README.md, CLAUDE.md references
5. **System-prompt skill list** — The skill description appears automatically, but the text shown there influences whether other agents decide to load it

The complete integration checklist is documented in `agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` (items S8-S10 for skills specifically).

---

## 10. Skill Authoring Conventions

### 10.1 Authoring Workflow

1. **Before creating:** Read 1-2 existing skills of the same type as structural exemplars
2. **Write frontmatter:** Follow the spec in Section 3
3. **Write body:** Follow the structural patterns in Section 4
4. **Create references:** Split detailed content per the guidelines in Section 5
5. **Register:** Run the framework integration checklist
6. **Test:** Use realistic prompts to verify triggering accuracy

### 10.2 Key Authoring Principles

| Principle | Meaning |
|-----------|---------|
| **Concise is Key (SKILL.md)** | Body shares context with conversation; justify every token |
| **Thorough is Key (references)** | Reference files load on-demand; encode all discovered knowledge |
| **Progressive Disclosure** | Load only what's needed, when needed |
| **Appropriate Freedom** | Match specificity to task fragility |
| **Explain the Why** | Use reasoning over rigid ALWAYS/NEVER directives |
| **Examples over Prose** | Show input/output pairs rather than describing behavior |
| **Test and Iterate** | Create test prompts, observe behavior, refine |

### 10.3 Content Limits

| Component | Limit | Notes |
|-----------|-------|-------|
| Name | 64 chars | Lowercase hyphen-case, must match directory |
| Description (frontmatter) | **250 chars** | Hard truncation in system prompt |
| Description (body) | ~500 chars | Full description after `# Title` heading |
| SKILL.md body | <500 lines | Guideline, not enforced |
| SKILL.md body | <5000 words | Keep concise |
| Metadata per skill | ~100 words | Always in context |
| Reference files | No limit | Comprehensive is preferred; only loaded on demand |

### 10.4 Data Source Skills: Special Requirements

- **Required metadata:** `skill-authored` and `skill-last-updated` (ISO-8601 dates)
- **Codebook references:** Include codebook path table if codebooks exist
- **Truth Hierarchy:** Document the priority: observed data > codebook > skill documentation
- **Reference file density:** Target 3x+ the SKILL.md line count collectively
- **Staleness awareness:** `skill-last-updated` enables agents to assess if the skill's factual claims may have drifted

---

## 11. Skill Information Trustworthiness Model

DAAF has a sophisticated trust model for skill-sourced information:

### 11.1 Curated vs. Inferred Knowledge

Skills contain **curated domain knowledge** — point-in-time snapshots that can drift as APIs evolve, endpoints change, and documentation updates. More critically, when an agent fills in details *beyond* what a skill explicitly states, that is **LLM-generated inference** — not curated knowledge — and is substantially more likely to be inaccurate.

### 11.2 Verification Protocol

- Agents with web access (`WebSearch`, `WebFetch`) should verify skill-sourced details that produce unexpected results
- Agents without web access should flag uncertainty in their return output for the orchestrator to resolve
- The orchestrator surfaces verification opportunities to users proactively

### 11.3 Staleness Detection

The `skill-last-updated` metadata field enables staleness assessment:
- If more than a few months old, treat the skill's claims with caution
- Consider re-running data onboarding to re-verify
- Agents note staleness caveats in script header comments when working with potentially stale skill data

---

## 12. Skill System in the Broader DAAF Architecture

### 12.1 Relationship to Agents

| Aspect | Skill | Agent |
|--------|-------|-------|
| **Purpose** | Provide domain knowledge | Define behavioral protocol |
| **Content** | Reference material, decision trees | Execution patterns, validation rules |
| **Loading** | Subagent calls Skill tool | Orchestrator includes agent definition in Agent prompt |
| **Example** | `education-data-source-ccd` (CCD knowledge) | `research-executor` (execution protocol) |

### 12.2 Relationship to Hooks

Hooks interact with the skill system in two ways:
1. **PostToolUse hook on Skill matcher** — `flag-orchestrator-loaded.sh` fires after any Skill tool call, setting a flag when `daaf-orchestrator` is loaded
2. **Context reporter** — Monitors utilization across all agents, influencing how many skills an agent can afford to load before returning

### 12.3 Relationship to Orchestrator Reference Files

The orchestrator skill (`daaf-orchestrator`) uses its own `references/` directory to store mode-specific operational documents:

```
.claude/skills/daaf-orchestrator/references/
├── WORKFLOW_PHASE_DO_AUTHORING.md    # Data Onboarding: skill authoring phase
├── WORKFLOW_PHASE_DO_PROFILING.md    # Data Onboarding: profiling phase
├── ad-hoc-collaboration-mode.md      # Ad Hoc Collaboration mode protocol
├── data-discovery-mode.md            # Data Discovery mode protocol
├── data-lookup-mode.md               # Data Lookup mode protocol
├── data-onboarding-mode.md           # Data Onboarding mode protocol
├── framework-development-mode.md     # Framework Development mode protocol
├── full-pipeline-mode.md             # Full Pipeline mode protocol
├── reproducibility-verification-mode.md  # Reproducibility mode protocol
├── revision-and-extension-mode.md    # Revision & Extension mode protocol
├── session-recovery.md               # Session recovery protocol
└── user-support-mode.md              # User Support mode protocol
```

These are loaded progressively by the orchestrator based on which mode the user confirms — a perfect example of the Level 3 progressive disclosure pattern applied to operational protocols rather than domain knowledge.

---

## 13. Migration Considerations

### 13.1 What a Target Platform Must Support

To reconstruct this skill system, a target AI coding harness needs:

1. **Skill discovery** — Automatic scanning of a skill directory for SKILL.md files with YAML frontmatter
2. **System prompt injection** — Ability to inject skill metadata (name + description) into every conversation's system prompt at startup
3. **On-demand loading** — A tool or mechanism for agents to load skill body content into their context mid-conversation
4. **Reference file reading** — Ability for agents to read additional files from the skill's directory structure
5. **Agent-level skill preloading** — Mechanism to inject skill content at agent startup via configuration
6. **Subagent contexts** — Independent context windows for subagents so skill loading doesn't consume the orchestrator's budget

### 13.2 What Is Claude Code-Specific vs. Portable

| Aspect | Claude Code-Specific | Portable |
|--------|---------------------|----------|
| `SKILL.md` file format | The file name convention | YAML frontmatter + Markdown body is standard |
| Skill tool invocation syntax | `Skill({ skill: "name" })` | Concept of loading a skill by name |
| System prompt injection | Claude Code's automatic injection | Any system with skill metadata injection |
| Agent frontmatter `skills:` | Claude Code agent format | Concept of preloading skills for agents |
| 250-char description truncation | Claude Code's specific limit | Need to determine target platform's limit |
| `references/` directory | Read tool access | Any file reading mechanism |
| PostToolUse hooks on Skill | Claude Code hook system | Would need equivalent event system |
| Progressive disclosure levels | Design pattern, not code | Fully portable as an architecture |

### 13.3 Key Design Decisions to Preserve

1. **Separate metadata from content** — The 250-char description as a matching/triggering summary, separate from the full content
2. **Three-level progressive disclosure** — Metadata always loaded, body on trigger, references on demand
3. **Skills loaded by subagents, not orchestrator** — Critical for context budget management
4. **Thorough references, concise body** — Different optimization targets for Level 2 vs. Level 3
5. **Flat reference structure** — One level deep, no nesting
6. **Provenance metadata** — `skill-authored` and `skill-last-updated` for staleness detection
7. **Trust model** — Curated skill knowledge vs. LLM inference, with verification protocols

---

## Appendix A: Complete Skill Inventory

| # | Skill Name | Category | Lines | Refs | Audience |
|---|-----------|----------|-------|------|----------|
| 1 | `agent-authoring` | skill-development | 225 | 3 | any-agent |
| 2 | `daaf-orchestrator` | research-orchestration | 592 | 12 | research-orchestrator |
| 3 | `data-scientist` | research-methodology | 827 | 15 | any-agent |
| 4 | `education-data-context` | data-documentation | 482 | 6 | any-agent |
| 5 | `education-data-explorer` | data-access | 576 | 5 | research-planner |
| 6 | `education-data-query` | data-access | 270 | 5 | research-coders |
| 7 | `education-data-source-campus-safety` | data-source | 329 | 9 | any-agent |
| 8 | `education-data-source-ccd` | data-source | 352 | 5 | any-agent |
| 9 | `education-data-source-crdc` | data-source | 362 | 6 | any-agent |
| 10 | `education-data-source-eada` | data-source | 309 | 6 | any-agent |
| 11 | `education-data-source-edfacts` | data-source | 398 | 6 | any-agent |
| 12 | `education-data-source-fsa` | data-source | 337 | 5 | any-agent |
| 13 | `education-data-source-ipeds` | data-source | 472 | 8 | any-agent |
| 14 | `education-data-source-meps` | data-source | 282 | 5 | any-agent |
| 15 | `education-data-source-nacubo` | data-source | 316 | 5 | any-agent |
| 16 | `education-data-source-nccs` | data-source | 334 | 5 | any-agent |
| 17 | `education-data-source-nhgis` | data-source | 321 | 6 | any-agent |
| 18 | `education-data-source-pseo` | data-source | 297 | 6 | any-agent |
| 19 | `education-data-source-saipe` | data-source | 282 | 6 | any-agent |
| 20 | `education-data-source-scorecard` | data-source | 346 | 7 | any-agent |
| 21 | `election-data-source-countypres` | data-source | 349 | 6 | any-agent |
| 22 | `geopandas` | python-library | 282 | 8 | research-coders |
| 23 | `linearmodels` | python-library | 263 | 7 | research-coders |
| 24 | `marimo` | python-library | 289 | 8 | research-coders |
| 25 | `plotly` | python-library | 218 | 6 | research-coders |
| 26 | `plotnine` | python-library | 171 | 6 | research-coders |
| 27 | `polars` | python-library | 328 | 10 | research-coders |
| 28 | `pyfixest` | python-library | 275 | 8 | research-coders |
| 29 | `r-python-translation` | python-library | 374 | 10 | research-coders |
| 30 | `science-communication` | research-communication | 219 | 6 | research-writers |
| 31 | `scikit-learn` | python-library | 335 | 14 | research-coders |
| 32 | `shell-scripting` | skill-development | 205 | 5 | research-coders |
| 33 | `skill-authoring` | skill-development | 275 | 7 | any-agent |
| 34 | `stata-python-translation` | python-library | 406 | 10 | research-coders |
| 35 | `statsmodels` | python-library | 289 | 7 | research-coders |
| 36 | `svy` | python-library | 272 | 3 | research-coders |

## Appendix B: Frontmatter Field Summary (All Observed Combinations)

```yaml
# === REQUIRED FIELDS ===
name: <string>          # 1-64 chars, lowercase hyphen-case, must match directory
description: <string>   # 1-250 chars effective (truncated in system prompt)

# === OPTIONAL: metadata block ===
metadata:
  # Controlled vocabulary fields (standard)
  audience: <any-agent | research-orchestrator | research-planner | research-coders | research-writers>
  domain: <data-source | data-access | data-documentation | python-library | research-methodology | research-orchestration | research-communication | skill-development>
  
  # Provenance fields (data source skills: required; library skills: recommended)
  skill-authored: "YYYY-MM-DD"
  skill-last-updated: "YYYY-MM-DD"
  
  # Version tracking (library skills only)
  library-version: "X.Y.Z"
```

## Appendix C: Loading Lifecycle Diagram

```
SESSION START
    |
    v
[Claude Code scans .claude/skills/*/SKILL.md]
    |
    v
[Extract name + description from YAML frontmatter]
    |
    v
[Inject ALL skill metadata into system prompt]          <-- Level 1 (always)
    |
    v
[Agent sees list of available skills in <system-reminder>]
    |
    v
===================================================
    |
[User request arrives / Agent begins task]
    |
    +--- Agent determines skill needed (from description matching)
    |    |
    |    v
    |    Skill({ skill: "polars" })                      <-- Level 2 (on trigger)
    |    |
    |    v
    |    [SKILL.md body injected into agent context]
    |    |
    |    v
    |    [Agent reads decision trees, identifies needed refs]
    |    |
    |    v
    |    Read("./references/quickstart.md")               <-- Level 3 (on demand)
    |    |
    |    v
    |    [Reference content loaded into context]
    |
    +--- Agent has preloaded skill (via frontmatter)
    |    |
    |    v
    |    [SKILL.md body already in context at startup]    <-- Level 2 (at startup)
    |    |
    |    v
    |    [Agent reads references as needed]               <-- Level 3 (on demand)
    |
    +--- Orchestrator exception (Ad Hoc / Framework Dev)
         |
         v
         Skill({ skill: "data-scientist" })               <-- Level 2 (exception)
         |
         v
         [Orchestrator uses skill knowledge directly]
```
