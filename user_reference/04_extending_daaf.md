# 04. Extending DAAF

This guide focuses on the primary extension path: bringing new datasets and data domains into DAAF. If you want to modify the framework itself (agents, protocols, validation logic), see [Contributing](05_contributing.md) for framework-level changes.

---

## Documentation Table of Contents

- [**00. README**](../.) — **\[Prerequisite\]** Vision and purpose, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — **\[Prerequisite\]** Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**02. Understanding DAAF**](02_understanding_daaf.md) — **\[Prerequisite\]** Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**03. Best Practices**](03_best_practices.md) — **\[Prerequisite\]** Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- **04. Extending DAAF** — **\[This document\]** How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05. Contributing**](05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)

---

## The Extension Model: Skills + Data-Ingest Agent

<!-- NEW: Overview of how DAAF's extensibility works — skills provide knowledge, data-ingest profiles new sources -->

How DAAF separates domain knowledge (skills) from behavioral protocols (agents), and why this makes it straightforward to add new data domains without changing the core framework.

### What a Skill Is

A skill is a structured knowledge document that tells DAAF's agents how to work with a specific data source: what endpoints exist, what variables mean, what caveats to watch for, and how to query the data.

### What the Data-Ingest Agent Does

The data-ingest agent profiles a new dataset and produces the documentation artifacts needed to create a skill — it automates much of the tedious work of cataloging variables, types, and distributions.

---

## When to Extend vs. When to Contribute

<!-- NEW: Clear boundary between adding a skill (this doc) vs. modifying the framework (05_contributing.md) -->

The distinction between extension (adding domain knowledge) and contribution (modifying framework behavior), and which guide to follow for each.

| If You Want To... | Guide |
|-------------------|-------|
| Add a new data source | This document (04) |
| Add a new data domain | This document (04) |
| Add a new agent | This document (04) — "Adding a New Agent" section |
| Modify an agent's behavior | [Contributing](05_contributing.md) |
| Change validation protocols | [Contributing](05_contributing.md) |
| Fix a bug in the framework | [Contributing](05_contributing.md) |

---

## Step-by-Step: Profiling a New Dataset with Data-Ingest

<!-- NEW: Walkthrough of using the data-ingest agent to profile a dataset -->

How to use the data-ingest agent to analyze a new dataset and generate the documentation artifacts that will become a skill.

### Preparing Your Data

What format your data should be in, where to place it, and what metadata to have ready.

### Running the Data-Ingest Agent

How to invoke data-ingest and what it produces (variable catalog, distribution profiles, quality assessment).

### Reviewing the Profile Output

What to check in the generated profile before proceeding to skill creation.

---

## Step-by-Step: Authoring a New Data Source Skill

<!-- NEW: Walkthrough of creating a skill from the profile output, referencing the skill-authoring skill -->

How to turn a data-ingest profile into a complete skill that DAAF's agents can use.

### Using the Skill-Authoring Skill

How the `skill-authoring` skill guides you through creating a properly structured SKILL.md file.

### Required Skill Sections

What every data source skill must contain: frontmatter, variable definitions, query patterns, caveats, and coded value mappings.

### Registering the Skill

Where to place the skill files and how DAAF discovers them.

---

## Adding a New Agent

<!-- NEW: Guidance for adding new specialized agents to DAAF -->

While adding data sources is the most common extension path, you may also need to add a new **specialized agent** — a behavioral protocol that defines how a subagent should operate during a specific part of the workflow.

### When You Need a New Agent

| Situation | Extension Type |
|-----------|---------------|
| New data source to analyze | Data source skill (see sections above) |
| New tool/library to use | Tool skill (e.g., plotnine, polars) |
| New **behavioral role** in the pipeline | New agent (this section) |

A new agent is warranted when you need a distinct behavioral protocol that doesn't fit any existing agent's role — for example, a specialized validator for a new data domain, or a new synthesis pattern for cross-domain analysis.

### Using the Agent-Authoring Skill

The `agent-authoring` skill provides comprehensive guidance for creating new agents:

1. **Design phase:** Identify the role, pipeline stage, and similar agents to differentiate from
2. **Author phase:** Write the agent file following the canonical 12-section template (`agent_reference/AGENT_TEMPLATE.md`)
3. **Integrate phase:** Update all registry files across the documentation ecosystem (the skill provides a complete checklist)
4. **Validate phase:** Verify cross-agent consistency and registry completeness

### Key Resources

| Resource | Purpose |
|----------|---------|
| `agent-authoring` skill | Full workflow with integration checklist |
| `agent_reference/AGENT_TEMPLATE.md` | Canonical 12-section template |
| `agents/README.md` | Current agent landscape and coordination matrix |

For framework-level changes to existing agents (modifying behavior, not adding new ones), see [Contributing](05_contributing.md).

---

## Anatomy of an Existing Skill

<!-- NEW: Walk through a real skill (e.g., education-data-source-ccd) as a template -->

A guided tour of an existing data source skill, explaining each section and how it's used by DAAF's agents during analysis.

### Frontmatter and Metadata

What the YAML frontmatter tells DAAF about when and how to load the skill.

### Variable Definitions and Coded Values

How variables, types, and coded value mappings are documented.

### Query Patterns and Mirror Configuration

How the skill connects to data access mirrors and specifies download patterns.

### Caveats and Limitations

How source-specific warnings are documented and surfaced during analysis.

---

## How Skills, Mirrors, and the Query Pipeline Connect

<!-- NEW: Explain the data flow from skill → query → mirror → local parquet -->

The end-to-end path from a skill's query specification to downloaded parquet files on disk.

### The Mirror System

What mirrors are, where they're configured (`mirrors.yaml`), and how they provide data access.

### The Query Pipeline

How the `education-data-query` skill uses mirror configuration and source skill metadata to fetch data.

### Local Data Storage

Where fetched data lands (`data/raw/`), the naming convention, and the parquet format requirement.

---

## Testing Your New Skill End-to-End

<!-- NEW: How to verify a new skill works correctly through the full pipeline -->

How to validate that your new skill integrates correctly with DAAF's agents and produces reliable results.

### Discovery Test

Verify that the explorer skill finds your new data source and its variables.

### Fetch Test

Verify that data can be downloaded and passes CP1 validation.

### Context Test

Verify that caveats and coded values are correctly applied during cleaning.

### Full Pipeline Test

Run a simple analysis using your new skill to verify end-to-end integration.

---

## Submitting Your Skill for Inclusion

<!-- NEW: Bridge to contributing guide for the submission process -->

How to share your skill with the DAAF community — preparation, quality standards, and the pull request process.

See [Contributing](05_contributing.md) for the full contribution workflow, including how to submit a pull request.

---

## Recommended Next Steps

- [**05. Contributing**](05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)
