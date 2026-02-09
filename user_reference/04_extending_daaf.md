# Extending DAAF

> **Prerequisites:** [README](../README.md) and [Understanding DAAF](02_understanding_daaf.md) (architecture section) — you should understand how agents, skills, and the query pipeline fit together before extending the system.

This guide focuses on the primary extension path: bringing new datasets and data domains into DAAF. If you want to modify the framework itself (agents, protocols, validation logic), see [Contributing](05_contributing.md) for framework-level changes.

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

## Next Steps

- **[Contributing](05_contributing.md)** — For framework-level modifications and the pull request process
- **[Understanding DAAF](02_understanding_daaf.md)** — Review the architecture if you need a refresher on how pieces fit together
