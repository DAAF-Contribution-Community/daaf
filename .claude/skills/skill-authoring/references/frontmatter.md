# Frontmatter Specification

The YAML frontmatter is the metadata block at the start of every SKILL.md file. It controls skill discovery and triggering.

## Frontmatter Structure

```yaml
---
name: skill-name
description: What this skill does and when to use it.
metadata:
  key1: value1
  key2: value2
---
```

The frontmatter must:
- Start on line 1 with `---`
- Contain valid YAML
- End with `---`
- Produce a dictionary when parsed

## Required Fields

### `name`

The skill identifier. Must match the containing directory name.

**Constraints:**

| Rule | Example Valid | Example Invalid |
|------|---------------|-----------------|
| Lowercase only | `my-skill` | `My-Skill` |
| Alphanumeric + hyphens | `pdf-v2` | `pdf_v2` |
| No leading hyphen | `skill-name` | `-skill-name` |
| No trailing hyphen | `skill-name` | `skill-name-` |
| No consecutive hyphens | `my-skill` | `my--skill` |
| 1-64 characters | `a` to 64 chars | empty or 65+ chars |

**Validation Regex:**

```
^[a-z0-9]+(-[a-z0-9]+)*$
```

**Normalization:**

If you provide a non-conforming name, it gets normalized:

| Input | Normalized |
|-------|------------|
| `My Skill` | `my-skill` |
| `PDF_Processor` | `pdf-processor` |
| `--test--` | `test` |
| `foo  bar` | `foo-bar` |

### `description`

The primary triggering mechanism. This is what agents see when deciding whether to load a skill.

**Constraints:**

| Rule | Limit |
|------|-------|
| Length | 1-1024 characters |
| No angle brackets | Cannot contain `<` or `>` |
| Non-empty | Must have content after trimming whitespace |

**Must Include:**

1. **What the skill does** - Functionality overview
2. **When to use it** - Specific triggering conditions
3. **Third-person voice** - Write as "Processes files" not "I help you process files" or "You can use this to process files"

**Good Examples:**

```yaml
# Good: Clear what + when
description: Generate SQL queries for analytics. Use when asked to query databases, create reports, or analyze data with SQL.

# Good: Specific triggers
description: Fix failing GitHub Actions CI. Use when PR checks fail, CI is red, or asked to debug GitHub Actions workflows.

# Good: File-type trigger
description: Process and manipulate PDF files. Use when working with .pdf files, rotating pages, merging documents, or extracting text from PDFs.
```

**Bad Examples:**

```yaml
# Bad: No "when to use"
description: A helpful skill for various tasks.

# Bad: Too vague
description: Does things with files.

# Bad: Contains angle brackets
description: Use <this> when needed.

# Bad: "When to use" in wrong place (will be in body, loaded too late)
description: Helps with testing.
# Then in body: "## When to Use This Skill" <-- WRONG
```

### Combating Undertriggering

Claude tends to undertrigger skills — not using them when they'd be useful. Make descriptions slightly "pushy" by including contexts where the skill should activate even if the user doesn't explicitly name it.

```yaml
# Standard (may undertrigger)
description: Build dashboards to display data.

# Pushy (better triggering)
description: Build dashboards to display data. Use this skill whenever the user mentions dashboards, data visualization, internal metrics, or wants to display any kind of data, even if they don't explicitly ask for a "dashboard."
```

### Combating Overtriggering

If a skill loads for unrelated queries, add negative triggers to narrow scope:

```yaml
description: Advanced statistical analysis for CSV datasets. Use for regression modeling, clustering, and hypothesis testing. Do NOT use for simple data exploration or basic charting (use data-viz skill instead).
```

### Naming Conventions

Consider using **gerund form** (verb + -ing) for skill names, as this clearly describes the activity the skill provides:

- `processing-pdfs` — clearly an activity
- `analyzing-spreadsheets` — clearly an activity
- `managing-databases` — clearly an activity

Acceptable alternatives include noun phrases (`pdf-processing`) or action-oriented names (`process-pdfs`). Avoid vague names like `helper`, `utils`, or `tools`.

## Optional Fields

### `metadata`

Additional key-value pairs for categorization. Values must be strings.

```yaml
metadata:
  audience: research-coders
  domain: python-library
  library-version: "1.x"
```

### Controlled Vocabulary

DAAF uses a controlled vocabulary for `audience` and `domain` to enable consistent skill routing. Use the exact values below — do not invent new values without updating this spec.

#### `audience` — Which agent role benefits from this skill?

| Value | Targets | Example Skills |
|-------|---------|----------------|
| `any-agent` | Broadly useful across roles | data sources, data-scientist, skill-authoring |
| `research-orchestrator` | Orchestrator agent only | daaf-orchestrator |
| `research-planner` | Planning/discovery agents | education-data-explorer |
| `research-coders` | Anyone writing or reviewing code | Python libraries, education-data-query |
| `research-writers` | Anyone writing or reviewing narrative | science-communication |

#### `domain` — What functional category does this skill belong to?

| Value | Covers | Example Skills |
|-------|--------|----------------|
| `data-source` | Reference guides for specific datasets | education-data-source-ccd, election-data-source-countypres |
| `data-access` | Fetching/discovering data | education-data-query, education-data-explorer |
| `data-documentation` | Provenance, caveats, interpretation | education-data-context |
| `python-library` | Library syntax/API reference | polars, plotly, statsmodels |
| `research-methodology` | Analytical approach, rigor, mindset | data-scientist |
| `research-orchestration` | Workflow/pipeline management | daaf-orchestrator |
| `research-communication` | Translating findings for audiences | science-communication |
| `skill-development` | Meta-skills for building skills/agents | skill-authoring, agent-authoring |

#### Other Standard Metadata Keys

| Key | Purpose | Example Values | When to Include |
|-----|---------|----------------|-----------------|
| `library-version` | Library version tracked by the skill | `"1.x"`, `"0.40.0"` | Python library skills only |
| `skill-authored` | ISO-8601 creation date | `"2026-02-09"` | Data source skills (required) |
| `skill-last-updated` | ISO-8601 last-verified date | `"2026-02-09"` | Data source skills (required); Python library skills (recommended) |

> **Provenance in metadata:** Data source skills MUST include `skill-authored` and `skill-last-updated` as metadata keys. These track when the skill was created and when it was last verified against actual data. On updates, change only `skill-last-updated`; `skill-authored` remains fixed. If `skill-last-updated` is more than a few months old, treat skill claims with caution — re-run data onboarding to re-verify.

> **Library skill staleness:** Python library skills SHOULD include `skill-last-updated` to signal when the `library-version` claim was last verified. Library APIs evolve — if the tracked version is outdated, the skill's syntax examples and API patterns may have drifted.

> **Metadata routing semantics:** The `audience` and `domain` fields are used for skill inventory management, human auditing, and maintenance — not for programmatic agent routing. Agent skill selection is driven by description text matching and explicit skill name references in orchestrator dispatch tables and agent frontmatter. These fields help maintainers answer questions like "show me all skills relevant to code-writing agents" or "list all data source skills" without affecting runtime behavior.

## Field Reference Table

| Field | Required | Type | Max Length | Notes |
|-------|----------|------|------------|-------|
| `name` | Yes | String | 64 chars | Lowercase hyphen-case |
| `description` | Yes | String | 1024 chars | No `<` or `>` |
| `metadata` | No | Dict | - | String values only |

## Unknown Fields

Unknown frontmatter fields are ignored but may cause validation errors in stricter systems. Stick to the documented fields.

**Allowed fields only:**
- `name`
- `description`
- `metadata`

## Complete Example

```yaml
---
name: polars
description: >-
  Polars DataFrame library for high-performance data manipulation in Python.
  Covers lazy/eager execution, expressions, I/O, aggregations, joins,
  string/datetime operations, pandas/NumPy interop, and performance
  optimization. Use when working with Polars DataFrames, migrating from
  pandas, reading Parquet files, or optimizing data pipeline performance.
metadata:
  audience: research-coders
  domain: python-library
  library-version: "1.x"
---
```

## Description Writing Tips

### Be Specific About Triggers

```yaml
# Vague (bad)
description: Helps with data tasks.

# Specific (good)
description: Transform and analyze data with Polars. Use when working with DataFrames, CSV/Parquet files, or performing data aggregations.
```

### Include File Types When Relevant

```yaml
description: Edit and process images. Use when working with .png, .jpg, .gif files or asked to resize, crop, or convert images.
```

### Include Command/Tool Names

```yaml
description: Fast DataFrame library for Python data science. Use for any Polars data manipulation, lazy/eager execution, or performance optimization task.
```

### Front-Load Important Words

The description may be truncated in UI. Put key information first.

```yaml
# Key info first (good)
description: PostgreSQL database operations. Use when writing SQL queries, managing schemas, or optimizing database performance.

# Key info buried (less good)
description: A comprehensive skill for various operations related to PostgreSQL database management and optimization.
```

### Avoid Offering Too Many Options

Provide a default approach with an escape hatch, rather than listing multiple equivalent alternatives:

```yaml
# Bad: Too many choices
description: Process PDFs using pypdf, pdfplumber, PyMuPDF, or pdf2image.

# Good: Default with escape hatch
description: Process PDFs using pdfplumber for text extraction. For scanned PDFs requiring OCR, uses pdf2image with pytesseract instead.
```
