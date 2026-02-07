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

## Optional Fields

### `metadata`

Additional key-value pairs for categorization. Values must be strings.

```yaml
metadata:
  audience: python-developers
  domain: data-science
  version: "1.0"
```

Common metadata keys:

| Key | Purpose | Example Values |
|-----|---------|----------------|
| `audience` | Target users | `developers`, `data-scientists`, `devops` |
| `domain` | Subject area | `testing`, `visualization`, `deployment` |
| `version` | Skill version | `1.0`, `2.3.1` |

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
name: polars-helper
description: Assists with Polars DataFrame operations. Covers lazy/eager execution, expressions, I/O, aggregations, joins, and performance optimization. Use for any Polars data manipulation task.
metadata:
  audience: python-developers
  domain: data-science
  polars-version: "1.x"
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
description: Lint and format Python code with Ruff. Use when running ruff check, ruff format, or configuring pyproject.toml linting rules.
```

### Front-Load Important Words

The description may be truncated in UI. Put key information first.

```yaml
# Key info first (good)
description: PostgreSQL database operations. Use when writing SQL queries, managing schemas, or optimizing database performance.

# Key info buried (less good)
description: A comprehensive skill for various operations related to PostgreSQL database management and optimization.
```
