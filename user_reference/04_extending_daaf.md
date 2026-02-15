# 04. Extending DAAF

**UNDER CONSTRUCTION, EVERYTHING HERE SUBJECT TO CHANGE BY LAUNCH** This guide focuses on the primary extension path: bringing new datasets, data domain expertise, and methodological tooling into DAAF. If you want to modify the framework itself (agents, protocols, validation logic), see [**05. Contributing to DAAF**](CONTRIBUTING.md) for framework-level changes.

[**Back to main**](../.)

---

- **Expanded data ingestion:** Ask DAAF to invoke the `data-ingest` agent, point it to a dataset (public data sources preferred, or ensure that you're being extremely careful to abide by your organization's AI policy and data protection standards for any proprietary data!!!), and provide any codebook or documentation available. DAAF will carefully build an intensive set of data documentation via manual data diagnostics and exploration, allowing it to use that data robustly and carefully in any future research request. This gets packaged into a new `data-source-skill` that can be shared with anyone else using DAAF at any time.
- **Methodological skill extensions:** Ask DAAF to use the `skill-authoring` skill and conduct deep research online for documentation or literature on a given methodological toolset for Python (e.g., pyfixest, predictive analytics, cluster analysis, etc.) to generate a new methodological toolset it can reference for future analyses. This gets packaged into a new `methodology-skill` that can be shared with anyone else using DAAF at any time.
- **Content area knowledge skill extensions:** Similarly, ask DAAF to use the `skill-authoring` skill and conduct deep research online for literature on a given area of domain expertise to help it navigate future analyses with more appropriate intuition, data concerns, and limitations. This gets packaged into a new `context-skill` that can be shared with anyone else using DAAF at any time.
- **Learnings integration:** Every time DAAF runs a completed project, it compiles learnings about the research process and data idiosyncrasies along the way. The LEARNINGS.md project file is written to be immediately actionable with revisions to make to documentation, skills, and more -- share these back with the community by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) so DAAF can self-iterate and grow from its runs across users!
- **Better, more robust, and more efficient workflows:** DAAF is *extremely* usage-hungry and likely far moreso than it needs to be, even for the level of care desired here. If you find a bug or have a suggestion, please [open an issue!](https://github.com/DAAF-Contribution-Community/daaf/issues)
- **Coding language agnosticism:** Today, DAAF works primarily in the Python ecosystem as its default analytic language. That being said, it is entirely possible to replace Python with any analytic toolset that can be installed open-source and run from the command line (e.g., R). I use the Polars library (which follows extremely similar syntax to tidyverse) to try and split the difference, but future collaborators can help us incorporate other languages more freely to suit more analytic workflows and organizational contexts.
- **Coding agent agnosticism:** DAAF is currently built on Claude Code, but the vast majority of the tooling present here (Skills, Agents, agent_reference, and so on) can be immediately ported to any similar coding harness/agent program (Gemini CLI, Codex, OpenCode, etc.). There will be important work to do related to the Hooks processes and similar guardrails.

---

## Table of Contents

- [**The Extension Model: Skills + Agents + Data-Ingest**](#the-extension-model-skills--agents--data-ingest)
- [**When to Extend vs. When to Contribute**](#when-to-extend-vs-when-to-contribute)
- [**Anatomy of an Existing Skill: A Guided Tour**](#anatomy-of-an-existing-skill-a-guided-tour)
- [**How Skills, Mirrors, and the Query Pipeline Connect**](#how-skills-mirrors-and-the-query-pipeline-connect)
- [**Step-by-Step: Profiling a New Dataset with Data-Ingest**](#step-by-step-profiling-a-new-dataset-with-data-ingest)
- [**Step-by-Step: Authoring a New Skill**](#step-by-step-authoring-a-new-skill)
- [**Adding a New Agent**](#adding-a-new-agent)
- [**Testing Your New Extension End-to-End**](#testing-your-new-extension-end-to-end)
- [**Submitting Your Extension for Inclusion**](#submitting-your-extension-for-inclusion)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## The Extension Model: Skills + Agents + Data-Ingest

Here's the fundamental insight behind DAAF's extensibility: **the framework separates what it *knows* from how it *behaves*.** This is a really important distinction that makes the whole extension model work, so let me explain it clearly.

DAAF has two types of building blocks:

- **Skills** are structured knowledge documents. They tell DAAF's agents *what they need to know* about a specific topic -- a data source, a Python library, a visualization framework, a domain of expertise. Think of skills as extremely thorough, well-organized reference guides that an agent loads into its context when it needs specialized knowledge to do its job.

- **Agents** are behavioral protocols. They tell a subagent *how to behave* -- what steps to follow, what to validate, when to stop, how to format output. Think of agents as detailed job descriptions that define a specific role in the pipeline (the code reviewer, the data planner, the report writer, etc.).

This separation is what makes DAAF extensible without being fragile. When you want DAAF to work with a new dataset, you don't need to touch the workflow, the validation logic, or the agent protocols at all. You just add a new skill that teaches the existing agents about the new data. The agents already know *how* to fetch, clean, transform, and analyze data -- they just need to be told the specifics of *your* data.

### The Three Extension Paths

| Extension Type | What You're Adding | Tool to Use | Result |
|----------------|-------------------|-------------|--------|
| **Data source** | Knowledge about a specific dataset | `data-ingest` agent | A new `data-source-skill` |
| **Methodology** | Knowledge about a statistical or analytical method | `skill-authoring` skill | A new `methodology-skill` |
| **Domain expertise** | Knowledge about a content area or field | `skill-authoring` skill | A new `context-skill` |

The most common extension path by far -- and the one I'll spend the most time on in this guide -- is adding new data sources. DAAF ships with a dedicated agent specifically for this purpose: the `data-ingest` agent, which does the heavy lifting of profiling a dataset and generating the skill documentation for you. You still need to review its output (this is *always* true with DAAF), but it dramatically reduces the manual effort involved.

For methodology and domain expertise skills, the process is lighter-weight -- you ask DAAF to use the `skill-authoring` skill, point it at documentation or literature to research, and it drafts a skill for you to review and refine. I'll cover that process too, but it's more straightforward than data ingestion.

### What Happens Under the Hood

When you ask DAAF to work with a data source (say, CCD enrollment data), here's the flow:

1. The **orchestrator** dispatches a subagent to explore available data (Stage 2)
2. The subagent **loads the relevant skill** (e.g., `education-data-source-ccd`) into its context
3. The skill tells the subagent everything it needs: what variables exist, what the coded values mean, what the known pitfalls are, how to access the data
4. The subagent uses that knowledge to do its job and returns findings to the orchestrator

The key thing to understand: **skills are loaded by subagents, not by the orchestrator.** This keeps the orchestrator's context lean and means skill knowledge only gets loaded when it's actually needed. It also means you can add as many skills as you want without bloating the base system -- they're loaded on demand.

---

## When to Extend vs. When to Contribute

This is a genuinely important distinction, and it maps directly to the [open-source licensing model](../#why-open-source-what-does-it-mean-for-daaf) described in the README. **Extending** DAAF means adding new knowledge on top of the existing framework. **Contributing** means modifying the framework itself. Both are valuable, but they're different activities with different guides.

| If You Want To... | Type | Guide |
|-------------------|------|-------|
| Add a new data source for DAAF to analyze | Extension | This document (04) |
| Teach DAAF a new statistical method or Python library | Extension | This document (04) |
| Give DAAF domain expertise in a new field | Extension | This document (04) |
| Add a new specialized agent to the pipeline | Extension | This document (04) -- [Adding a New Agent](#adding-a-new-agent) |
| Modify an existing agent's behavior | Contribution | [**05. Contributing to DAAF**](CONTRIBUTING.md) |
| Change validation protocols or workflow stages | Contribution | [**05. Contributing to DAAF**](CONTRIBUTING.md) |
| Fix a bug in the framework | Contribution | [**05. Contributing to DAAF**](CONTRIBUTING.md) |
| Improve documentation or tutorials | Contribution | [**05. Contributing to DAAF**](CONTRIBUTING.md) |

**A helpful rule of thumb:** If you're adding a new `.md` file to `.claude/skills/` or `agents/`, you're extending. If you're editing existing files in `agent_reference/`, `agents/`, or the root `CLAUDE.md`, you're contributing. The licensing implications matter here too -- extensions you build on top of DAAF are yours to keep proprietary or open-source as you choose, while modifications to the core framework must be shared back if you distribute them (see the [README](../#why-open-source-what-does-it-mean-for-daaf) for the full details on LGPL-3.0).

---

## Anatomy of an Existing Skill: A Guided Tour

Before you create a new skill, it really helps to understand what a well-structured one looks like. Let me walk you through the CCD (Common Core of Data) skill -- `education-data-source-ccd` -- since it's one of the most comprehensive data source skills in the system and a good model for what you'll be building.

Every data source skill lives at `.claude/skills/[skill-name]/SKILL.md` and follows a **canonical 12-section structure**. Here's what each section does and why it matters.

### 1. Frontmatter (YAML Header)

```yaml
---
name: education-data-source-ccd
description: >-
  Deep reference for the Common Core of Data (CCD), the US Department of
  Education's primary database on public K-12 education. Use when working with
  CCD data to understand survey components, variable definitions, data quality
  issues, historical changes, and state-level variations.
metadata:
  audience: data-analysts
  domain: education-data
---
```

This is the metadata that Claude Code reads *at startup* for every skill -- before any skill body is loaded. The `name` must exactly match the directory name. The `description` tells agents *when* to load this skill (this is crucial -- a vague description means agents won't know when to reach for it). Think of it as the label on the filing cabinet that tells you whether to pull this drawer open or not.

### 2-3. Title and Summary Paragraph

```markdown
# CCD Data Source Reference

The CCD is the Department of Education's comprehensive, annual, national
database of all public elementary and secondary schools and school districts
in the United States.
```

Short, clear, and immediately oriented. An agent that loads this skill knows within two sentences exactly what data universe it's dealing with.

### 4. Value Encodings Warning

This is a blockquote that appears right after the summary, and it's probably the single most important section for preventing data errors. The Education Data Portal re-encodes categorical variables as integers, which differ from the original NCES string codes. The CCD skill includes a comparison table showing both encodings side by side:

```markdown
> **CRITICAL: Value Encoding**
> | Context | `school_type` | `charter` |
> |---------|---------------|-----------|
> | **Portal (integers)** | `1` (Regular) | `0` (No) / `1` (Yes) |
> | NCES original | `1-Regular school` | `Yes` / `No` |
```

This warns agents immediately, before they even get into the details. Without this, an agent might assume `charter = 1` means "not a charter school" based on some documentation convention where `1 = Yes, 2 = No`, when actually it means `1 = Yes, 0 = No`. These kinds of encoding mistakes are exactly the sort of silent data corruption that DAAF's entire design philosophy is built to prevent.

### 5. "What is [Source]?"

A concise factsheet about the data source: what it covers, who collects it, how often, how many records, how far back it goes. This gives agents enough context to make informed decisions about whether the data is appropriate for a given research question.

### 6. Reference File Structure

A table pointing to the `references/` subdirectory -- the more detailed documentation that agents load on-demand when they need deeper information:

```markdown
| File | Purpose | When to Read |
|------|---------|--------------|
| `survey-components.md` | Detailed coverage of each CCD survey component | Understanding what data is collected |
| `variable-definitions.md` | Key variables, coding schemes, special values | Interpreting specific data elements |
| `data-quality.md` | Missing data patterns, suppression, state variations | Assessing data reliability |
```

This is the **progressive disclosure** pattern in action -- the main SKILL.md stays under 500 lines by keeping the essential quick-reference material in the body and pushing the deep dives into separate files. Agents load these reference files only when they need them, preserving precious context window space.

### 7. Decision Trees

These are genuinely one of the most clever parts of the skill structure. Decision trees guide agents through common questions using a branching format:

```
What information do you need?
+-- Student enrollment counts -> Membership
|   +-- By grade -> Membership (grade disaggregation)
|   +-- By race/ethnicity -> Membership (race disaggregation)
+-- Staff/teacher counts -> Staffing
+-- Revenue and expenditure -> Finance
```

An agent working on a research question about school staffing trends can follow the tree straight to the right component without reading the entire skill. These trees are concise, scannable, and extremely effective at helping agents navigate complex data landscapes quickly.

### 8. Quick Reference

The meat of the skill -- tables of key variables, identifiers, coded values, and component mappings. This is what agents reference most frequently during actual analysis work. For CCD, this includes things like school type codes (1 = Regular, 2 = Special Education, etc.), missing data codes (-1 = Missing/not reported, -2 = Not applicable, -3 = Suppressed), and key identifiers like `ncessch` (12-character school ID) and `leaid` (7-character district ID).

### 9. Data Access

How to actually get the data -- dataset paths, codebook locations, and the truth hierarchy for resolving conflicts between documentation and observed data:

> **Truth Hierarchy:** When interpreting variable values:
> 1. **Actual data file** (what you observe in the parquet/CSV) -- this IS the truth
> 2. **Live codebook** (.xls in mirror) -- authoritative documentation, may lag
> 3. **This skill documentation** -- convenient summary, may drift from codebook

This hierarchy is a core principle across the entire framework. Documentation describes intent; data reveals reality. When they conflict, you trust the data.

### 10. Common Pitfalls

A 3-column table (Pitfall | Impact | Mitigation) documenting the known gotchas that trip up analysts. For CCD, this includes things like: "Grade -1 means Pre-K, not missing data -- do NOT filter `grade >= 0`" and "Free/reduced lunch counts are unreliable after ~2014 due to Community Eligibility Provision (CEP)." These pitfalls are *exactly* the kind of hard-won domain knowledge that makes the difference between a credible analysis and one with silent errors.

### 11. Related Data Sources

Cross-references to other skills that complement or overlap with this one. For CCD, that includes EDFacts (state assessment data), MEPS and SAIPE (poverty estimates), and CRDC (civil rights data). This helps agents understand the broader data ecosystem and know when to pull in additional sources.

### 12. Topic Index

A flat lookup table at the very end that maps topics to reference files. This serves as a quick "Ctrl+F alternative" for agents that know what they're looking for but aren't sure which reference file contains it.

### The References Directory

Alongside SKILL.md, each skill can have a `references/` directory for detailed documentation that would bloat the main file. For the CCD skill:

```
.claude/skills/education-data-source-ccd/
+-- SKILL.md                            # Main skill (< 500 lines)
+-- references/
    +-- survey-components.md            # Deep dive: what data is in each component
    +-- variable-definitions.md         # Full variable catalogs and encoding tables
    +-- data-quality.md                 # Missingness, suppression, state quirks
    +-- data-collection.md              # How data flows from schools to NCES
    +-- historical-changes.md           # What changed across years
```

This structure keeps the main SKILL.md focused and scannable while ensuring that the detailed reference material is available when agents need to go deep. It's a good model to follow for your own skills.

---

## How Skills, Mirrors, and the Query Pipeline Connect

This section explains the end-to-end data flow from "I need some data" to "I have a validated parquet file on disk." Understanding this pipeline will help you see where your new skill fits into the bigger picture.

### The Mirror System

DAAF doesn't query APIs directly. Instead, it downloads pre-built data files from **mirrors** -- hosted copies of education datasets in formats optimized for bulk download (primarily parquet files). Mirrors are configured in a YAML file (`.claude/skills/education-data-query/references/mirrors.yaml`) that specifies:

- **URL templates** for building download URLs
- **Read strategies** defining how Polars should load the files (eager parquet, lazy CSV, etc.)
- **Discovery endpoints** for checking what files are available
- **Priority ordering** so DAAF tries the fastest/most reliable mirror first

Why mirrors instead of direct API calls? Three reasons: (1) bulk downloads are much faster than paginated API requests for large datasets, (2) parquet format preserves types and is dramatically more efficient than CSV, and (3) mirrors can be configured for offline or air-gapped environments where API access isn't available. The Education Data Portal happens to provide excellent mirror endpoints, but the system is designed so that *any* data source with downloadable files can be integrated.

### The Query Pipeline

Here's the flow when DAAF needs to fetch data during a research project:

```
Research question requires CCD enrollment data
    |
    v
Orchestrator dispatches Stage 5 (fetch) task
    |
    v
research-executor agent loads education-data-query skill
    |
    v
Agent looks up dataset path in datasets-reference.md
    (e.g., "ccd/schools_ccd_enrollment_2022")
    |
    v
Agent reads mirrors.yaml for mirror URLs and priority
    |
    v
Agent writes a fetch script using patterns from fetch-patterns.md
    |
    v
Script tries each mirror in priority order:
    Mirror 1: Build URL from template + dataset path -> download -> success? done
    Mirror 2: Build URL from template + dataset path -> download -> success? done
    All failed? -> STOP, escalate to user
    |
    v
Downloaded data saved to data/raw/*.parquet
    |
    v
CP1 validation runs (shape, types, missingness checks)
```

The **data source skill** (like `education-data-source-ccd`) doesn't directly participate in fetching. Instead, it provides the knowledge that the fetch scripts need -- the dataset paths, the expected column names, the known data quality issues. The **query skill** (`education-data-query`) provides the mechanical patterns for building URLs and downloading files. They work together but stay cleanly separated.

### Local Data Storage

All fetched data lands in `data/raw/` as parquet files, following the naming convention `YYYY-MM-DD_[source]_[description].parquet`. After cleaning and context application (Stage 6), processed data goes to `data/processed/`. This separation between raw and processed data is intentional -- it means you can always go back to the original downloaded files if something goes wrong during cleaning.

### Where Your New Skill Fits

When you create a new data source skill, you're primarily adding knowledge to the system at two points:

1. **Exploration (Stage 2-3):** Your skill tells agents what data is available, what variables exist, and what caveats to watch for
2. **Context application (Stage 6):** Your skill tells agents how to handle coded values, missing data patterns, and source-specific quirks during cleaning

The fetch mechanics (Stage 5) are mostly handled by the query skill and mirror configuration. If your data source is available through the existing mirrors, you may not need to change anything there. If your data comes from a different source entirely, you'll need to either add a new mirror configuration or provide the data files directly.

---

## Step-by-Step: Profiling a New Dataset with Data-Ingest

The `data-ingest` agent is DAAF's built-in tool for turning a raw dataset into a comprehensive data source skill. It automates the tedious but critical work of profiling every column, detecting coded values, checking data quality, and reconciling what the documentation says against what the data actually contains. Here's how to use it.

### Before You Start

You'll need:

1. **A data file** in a supported format (parquet, CSV, Excel, or TSV). Public data sources are strongly preferred. If you're working with proprietary or sensitive data, please be *extremely* careful to abide by your organization's AI policy and data protection standards -- Claude will be examining the actual contents of the data.
2. **Any available documentation** -- codebooks, data dictionaries, README files, or documentation website URLs. These aren't strictly required, but they dramatically improve the quality of the resulting skill because the agent can cross-reference what the documentation *says* against what the data *actually shows*.
3. **A sense of how the data will be used** -- what research questions it might inform, what domain it belongs to, and which columns are most important for your purposes.

### Preparing Your Data

Place your data file somewhere accessible within the Docker volume (the easiest spot is the `research/` directory or a subfolder of it). If you have documentation files, put those nearby too. Note the absolute file paths -- you'll need them.

A few practical considerations:

- **File size:** The agent can handle files up to about 1GB without special handling. For larger files, it'll ask you about a sampling strategy before proceeding.
- **File format:** Parquet is ideal (fast, preserves types). CSV works fine but may have type inference quirks. Excel files work but require the `openpyxl` library.
- **Multiple files:** If your data source spans multiple files (e.g., one file per year), start with a single representative file. The skill can document the multi-file structure, but profiling works best on one file at a time.

### Running the Data-Ingest Agent

You don't need to invoke the agent directly -- just ask DAAF conversationally. Something like:

```
I have a new dataset I'd like to profile and integrate into DAAF.
The data file is at: /daaf/research/my-data/state_spending_2023.parquet
I also have a codebook at: /daaf/research/my-data/codebook.xlsx
The documentation website is: https://example.gov/data-documentation

This is state-level education spending data. I'd like to use it
for analyzing per-pupil expenditure trends across states. The most
important columns are probably the ones related to total spending,
enrollment counts, and state identifiers.
```

DAAF will classify this as a data-ingest task and dispatch the `data-ingest` agent, which will then execute a systematic profiling protocol:

**Phase 1 -- Structural Profile:** Basic shape of the data (rows, columns, memory footprint, column types). This gives the agent a bird's-eye view of what it's working with.

**Phase 2 -- Column-Level Profile:** Detailed statistics for every column -- null rates, unique value counts, distributions, min/max ranges. For numeric columns, it checks for potential coded values (those suspicious negative numbers like -1, -2, -9 that often mean "missing" or "suppressed" rather than being real values). For categorical columns, it enumerates all unique values.

**Phase 3 -- Relationship Profiling:** Identifying potential key columns (high uniqueness suggests an identifier), foreign keys (naming patterns like `_id` suffixes), and hierarchical relationships between columns.

**Phase 4 -- Quality Profile:** Systematic data quality checks -- completeness rates, coded missing value detection, anomalous patterns, potential duplicates.

**Phase 5 -- Semantic Interpretation:** This is where it gets interesting. The agent uses column names, value patterns, and domain conventions to make educated guesses about what each column *means*. Every interpretation is explicitly marked as `[PRELIMINARY]` -- the agent knows it's hypothesizing, not asserting. Column named `fips`? Probably a FIPS geographic code. Column with values 0 and 1? Probably a binary indicator, but is 1 "Yes" or "Male" or "Urban"? The agent will flag the ambiguity.

If you provided documentation, the agent also runs **Documentation Reconciliation (Mode 2)**: it parses your codebook or data dictionary, extracts every claim it can find (column definitions, expected types, coded value meanings), and then *verifies each claim against the actual data.* Documentation says there are 50 columns? The agent checks. Codebook says `state_code` should be a string? The agent confirms or flags the mismatch. This reconciliation is one of the most valuable things the data-ingest agent does -- it catches the disturbingly common case where documentation is outdated or describes a different version of the data than what you actually have.

### Reviewing the Profile Output

The agent will return a structured report with:

- **Structural summary:** Row/column counts, memory size, format
- **Column summary:** Type, null rate, unique count, and notes for every column
- **Coded values detected:** Which columns have potential coded values, and whether documentation confirms their meaning
- **Quality assessment:** Scores for completeness, documentation accuracy, and coded value coverage
- **Preliminary interpretations:** The agent's best guesses for what columns mean, each flagged with a confidence level and basis for the interpretation
- **Discrepancies found:** Every case where documentation contradicted observed data, with evidence for both sides
- **User review requested:** Explicit questions for you to answer -- which interpretations are correct, how to handle undocumented values, whether missing columns are expected

**This review step is not optional.** The whole point of marking interpretations as `[PRELIMINARY]` is that *you* need to confirm or correct them. The agent has done the mechanical work of profiling, but the semantic understanding -- what these columns actually *mean* in context -- requires your domain expertise. Take the time to go through the review questions carefully. Your answers will directly determine the quality of the resulting skill.

Once you've provided your feedback, the agent uses your corrections to finalize the skill and writes it to `.claude/skills/[skill-name]/`.

---

## Step-by-Step: Authoring a New Skill

### Data Source Skills (via Data-Ingest)

If you're adding a new data source, the `data-ingest` agent (described above) handles most of the skill authoring for you. It follows a **canonical 12-section template** (defined in `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md`) that ensures every data source skill has the same predictable structure. The sections are:

1. Frontmatter (YAML)
2. Title
3. Summary paragraph
4. Value Encodings Warning (blockquote)
5. "What is [Source]?"
6. Reference File Structure
7. Decision Trees
8. Quick Reference (variables, identifiers, coded values)
9. Data Access
10. Common Pitfalls
11. Related Data Sources
12. Topic Index

The agent creates the skill directory, writes the SKILL.md, and populates the `references/` subdirectory with detailed backup documentation. After your review and corrections, the skill is ready to use.

### Methodology Skills (via Skill-Authoring)

For adding knowledge about a statistical method, Python library, or analytical technique, you'll use the `skill-authoring` skill directly. This is more free-form than data ingestion -- there's no fixed 12-section template (that's specific to data sources), and the content depends heavily on what you're documenting.

Ask DAAF something like:

```
I'd like to create a new methodology skill for pyfixest
(fixed-effects regression in Python). Please use the
skill-authoring skill to guide the process, and research
the pyfixest documentation online to build a comprehensive
reference.
```

DAAF will use the `skill-authoring` skill to guide the process. The skill-authoring skill provides detailed guidance on:

- **Frontmatter requirements:** The YAML header that every skill needs, including naming conventions (lowercase-hyphenated, 1-64 chars) and description best practices
- **Body structure patterns:** Different organizing patterns depending on whether the skill is workflow-based (sequential steps), task-based (tool collection), reference-based (standards/specs), or capabilities-based (features)
- **Progressive disclosure:** How to keep the main SKILL.md under 500 lines by splitting detailed content into `references/` files
- **Decision trees:** How to write effective navigation trees that help agents find what they need quickly
- **Content limits:** SKILL.md body should stay under 500 lines and 5,000 words -- be concise and justify every token

The resulting skill gets placed at `.claude/skills/[skill-name]/SKILL.md` with optional `references/`, `scripts/`, and `assets/` subdirectories.

### Domain Expertise Skills (via Skill-Authoring)

Same process as methodology skills, but the content focuses on domain knowledge rather than tooling. For example, you might create a skill that documents the nuances of interpreting graduation rate data, or the policy context around school funding formulas, or the methodological considerations for analyzing panel data in education research.

```
I'd like to create a context skill for understanding Community
Eligibility Provision (CEP) and its impact on free/reduced-price
lunch data. This is critical context for anyone analyzing school
poverty measures after 2014. Please use the skill-authoring skill
and research this topic.
```

### Registering Your New Skill

Here's the part that people sometimes miss: **creating the skill file is not enough.** DAAF uses a manual, documentation-based discovery system -- there's no auto-discovery of skills. After creating a new skill, it needs to be registered in several places so the orchestrator and agents can find it.

For data source skills, the `data-ingest` agent will provide you with a specific registration checklist at the end of its report. It looks something like this:

| Priority | File | Section to Update | What to Add |
|----------|------|-------------------|-------------|
| 1 (Required) | `CLAUDE.md` | Data Need Source Skill Lookup table | New row mapping data need to skill name |
| 2 (Required) | `agent_reference/03_SKILL_INVOCATIONS.md` | Available source skills list | New bullet with skill name and description |
| 3 (Required) | `agents/source-researcher.md` | Step 1 examples | Add skill to example list |
| 4 (Recommended) | `README.md` | Data Source Quick Lookup | New row for user reference |

The agent will typically offer to make these updates for you -- just confirm and it'll handle the file edits. Note that these registration edits touch core framework files, which means they fall under the "contribution" category if you plan to share them (see [When to Extend vs. When to Contribute](#when-to-extend-vs-when-to-contribute)).

For methodology and domain expertise skills, registration is simpler -- you primarily need to update `CLAUDE.md` so the orchestrator knows the skill exists and when to recommend loading it.

---

## Adding a New Agent

Adding data sources is the most common extension path, but sometimes you need something different: a new **behavioral role** in the pipeline. Maybe you need a specialized validator for a particular type of analysis, or a new synthesis pattern for cross-domain work, or a domain-specific planner that understands the constraints of your field. That's when you add a new agent.

This is a less common operation and a more involved one. Agents are deeply wired into the DAAF ecosystem -- they have producer/consumer relationships with other agents, they reference shared protocols, and they need to be discoverable by the orchestrator. The `agent-authoring` skill exists specifically to guide you through this process and make sure nothing gets missed.

### When You Actually Need a New Agent

Before creating a new agent, ask yourself honestly:

| Situation | What You Actually Need |
|-----------|----------------------|
| New data source to analyze | A data source skill (see sections above) |
| New Python library or tool to use | A methodology skill (see sections above) |
| New **behavioral role** that no existing agent covers | A new agent (this section) |

DAAF currently has 12 specialized agents covering execution, code review, planning, plan validation, verification, source research, synthesis, debugging, notebook assembly, integration checking, data ingestion, and report writing. That's a pretty comprehensive set. Make sure your new role genuinely doesn't fit any of these before creating a new agent -- it's much better to extend an existing agent's protocol than to create a new one that overlaps and confuses the orchestrator.

### The Agent-Authoring Workflow

Ask DAAF to use the `agent-authoring` skill:

```
I need to create a new agent for [describe the behavioral role].
Please use the agent-authoring skill to guide me through the process.
```

The workflow has five phases:

**Phase 1: Design (before writing).** This is where you get crystal clear on the fundamentals. The agent-authoring skill will make sure you can answer five critical questions:

1. What does this agent do and why does it exist? (one sentence)
2. Which pipeline stage(s) does it operate in?
3. Which existing agents are most similar, and how does yours differ?
4. Does it need file-write access (`general-purpose`) or is it read-only (`Plan`)?
5. Will it need to invoke any skills?

If any of these answers are vague, the agent-authoring skill will push you to sharpen them. This upfront clarity is genuinely important -- a poorly defined role leads to a poorly functioning agent.

**Phase 2: Author.** Write the agent definition file following the canonical 12-section template (defined in `agent_reference/AGENT_TEMPLATE.md`). The required sections include: Identity, Inputs, Core Behaviors, Protocol, Output Format, Boundaries, STOP Conditions, Anti-Patterns, Quality Standards, Invocation, References, and Consumers. The agent-authoring skill provides section-by-section guidance and a self-validation checklist covering everything from minimum anti-pattern counts to expected file length (400-700 lines).

**Phase 3: Integrate.** This is the step where the most things can go wrong if you're not careful. A new agent needs to be registered across multiple files in the DAAF ecosystem. The agent-authoring skill provides a complete integration checklist organized into tiers:

- **Tier 1 (Mandatory, 6 files):** Every new agent must be registered in `agents/README.md`, `CLAUDE.md`, `README.md`, and several other core files
- **Tier 2 (Conditional):** Additional updates if the agent maps to a specific pipeline stage
- **Tier 3 (Conditional):** Additional updates if the agent affects specific workflow areas

**Phase 4: Validate.** Verification checks to confirm cross-agent consistency and completeness. The skill provides specific grep commands to run.

**Phase 5: Human review.** This is non-negotiable. You *must* review the agent file yourself for accuracy, intention, completeness, and value before it's considered done.

### Key Resources

| Resource | Purpose |
|----------|---------|
| `agent-authoring` skill | Full workflow with integration checklist |
| `agent_reference/AGENT_TEMPLATE.md` | Canonical 12-section template |
| `agents/README.md` | Current agent landscape, commonly confused pairs, coordination matrix |

For changes to *existing* agents (modifying behavior rather than adding new ones), see [**05. Contributing to DAAF**](CONTRIBUTING.md).

---

## Testing Your New Extension End-to-End

You've created a new skill (or agent). How do you know it actually works? Here's a practical testing sequence, ordered from lightest to heaviest.

### Discovery Test

The simplest test: can DAAF find your new skill and understand what it's for?

```
What data sources does DAAF know about? Can you tell me about
[your new data source]?
```

If the skill is properly registered, DAAF should be able to describe the data source, list key variables, and mention important caveats. If it can't find the skill or gives a generic response, check your registration entries in `CLAUDE.md` and the other files listed in the registration checklist.

### Fetch Test

If your data source is accessible through the mirror system (or available as a local file), test that DAAF can actually retrieve and load the data:

```
Can you fetch [your data source] for [year] and show me the first
few rows and basic summary statistics?
```

This tests the data access pathway -- the dataset paths in your skill, the mirror configuration, and the basic loading mechanics. The fetch should complete with a CP1 validation (shape, types, missingness checks). If CP1 fails, it usually means the dataset path in your skill doesn't match what's actually available on the mirror, or the expected column structure differs from reality.

### Context Test

This tests whether your skill's coded value mappings, missing data codes, and caveats are being correctly applied during data cleaning:

```
Can you fetch and clean [your data source] for [year], making sure
to handle any coded missing values and apply the source-specific
caveats documented in the skill?
```

Watch the cleaning script that DAAF produces. It should reference the specific coded values, suppression patterns, and pitfalls documented in your skill. If it's treating -9 as a real numeric value instead of a missing data code, the coded value documentation in your skill may not be clear enough.

### Full Pipeline Test

The gold standard: run a simple research question that exercises your new skill through the entire pipeline.

```
Using [your new data source], can you analyze [simple, well-defined
research question]? Keep the scope narrow -- I just want to verify
the data flows through correctly.
```

Pick a question that's deliberately simple -- something like "What is the average [measure] by [grouping variable] for [year]?" You're not testing analytical sophistication here, you're testing integration. Does the data flow through fetch, clean, transform, and analysis without errors? Do the coded values get handled correctly? Does the report reference the right caveats?

### Methodology/Domain Skill Test

For non-data-source skills, the testing is more straightforward:

```
I'd like to run a [method from your new skill] analysis on
[some existing DAAF data]. Can you walk me through the approach?
```

Check that DAAF references your skill's guidance -- the correct function calls, the appropriate assumptions to validate, the known limitations to document.

---

## Submitting Your Extension for Inclusion

If you've created a useful skill or agent and want to share it with the broader DAAF community -- please do! The whole point of this being open-source is that the framework gets better as more people contribute their domain expertise. A skill you create for, say, health survey data or labor market statistics could save someone else weeks of profiling work.

### Before You Submit

A few things to check:

- **Quality:** Did you thoroughly review the data-ingest output and correct any preliminary interpretations? Skills with `[PRELIMINARY]` markers still in place aren't ready for sharing.
- **Completeness:** Does the skill follow the canonical 12-section template (for data sources)? Does it have at least 2 decision trees? Is the Common Pitfalls section substantive?
- **Privacy:** Does the skill reference only publicly accessible data? If it was built from proprietary data, make sure the skill documentation doesn't leak any confidential information or values.
- **Testing:** Have you run at least a Discovery Test and a Fetch Test to confirm the skill works end-to-end?

### How to Submit

See [**05. Contributing to DAAF**](CONTRIBUTING.md) for the full contribution workflow. The short version: fork the repository, add your skill files, update the registration entries, and submit a pull request. The contribution guide covers pull request formatting, quality standards, and the review process in detail.

If you're not comfortable with the pull request process, you can also [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) describing your new skill and sharing the files -- the community can help get it integrated.

### LEARNINGS.md: The Other Way to Contribute

Even if you're not creating new skills, there's a contribution path that requires almost zero effort: **sharing your LEARNINGS.md files.** Every time DAAF completes a Full Pipeline project, it produces a LEARNINGS.md file documenting everything it learned about data quirks, process issues, and methodology edge cases along the way. These learnings are written to be immediately actionable -- they often contain specific suggestions for updating skills, improving documentation, or adding new pitfall entries.

If you [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) with your LEARNINGS.md content, the community can fold those insights back into the framework. This is genuinely one of the most impactful things you can do -- every project run generates practical knowledge that benefits every future project.

---

## Recommended Next Steps

- [**05. Contributing to DAAF**](CONTRIBUTING.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
