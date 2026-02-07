# SKILL.md Body Structure

The Markdown body follows the frontmatter and contains instructions for the agent. This document covers organization patterns, formatting conventions, and section templates.

## Body Constraints

| Constraint | Guideline |
|------------|-----------|
| Line count | <500 lines (recommended) |
| Word count | <5000 words |
| Writing style | Imperative/infinitive form |
| Content focus | Examples over explanations |

## Four Body Patterns

Choose based on your skill's primary purpose. Patterns can be mixed.

### Pattern 1: Workflow-Based

For skills with sequential processes or decision flows.

**Best for:** CI/CD pipelines, deployment processes, multi-step procedures

**Structure:**

```markdown
# Skill Name

Brief intro.

## Overview

What this workflow accomplishes.

## Decision Tree

```
Starting point?
├─ Condition A → Step 1
├─ Condition B → Step 2
└─ Condition C → Step 3
```

## Step 1: First Action

Instructions for step 1.

## Step 2: Second Action

Instructions for step 2.

## Step 3: Third Action

Instructions for step 3.
```

### Pattern 2: Task-Based

For skills that are collections of related tools or operations.

**Best for:** File processors, API clients, utility collections

**Structure:**

```markdown
# Skill Name

Brief intro.

## Quick Start

Minimal example to get started.

## Task 1: Do Something

How to accomplish task 1.

## Task 2: Do Another Thing

How to accomplish task 2.

## Task 3: Advanced Operation

How to accomplish task 3.

## Quick Reference

| Task | Command/Method |
|------|----------------|
| Task 1 | `command1` |
| Task 2 | `command2` |
```

### Pattern 3: Reference-Based

For skills that encode standards, specifications, or guidelines.

**Best for:** Style guides, API specs, coding standards

**Structure:**

```markdown
# Skill Name

Brief intro.

## Overview

What this reference covers.

## Guidelines

### Guideline 1

Explanation and examples.

### Guideline 2

Explanation and examples.

## Specifications

| Item | Specification |
|------|---------------|
| Spec 1 | Details |
| Spec 2 | Details |

## Examples

### Good Example

```code
good code here
```

### Bad Example

```code
bad code here
```
```

### Pattern 4: Capabilities-Based

For skills that expose integrated system features.

**Best for:** Platform integrations, feature-rich tools, SDK wrappers

**Structure:**

```markdown
# Skill Name

Brief intro.

## Core Capabilities

- Capability 1
- Capability 2
- Capability 3

## Feature 1

### Usage

How to use feature 1.

### Examples

```code
example code
```

## Feature 2

### Usage

How to use feature 2.

### Examples

```code
example code
```
```

## Standard Sections

These sections appear in most well-structured skills.

### "What is X?" Section

Brief introduction with bullet points.

```markdown
## What is X?

X is a tool for doing Y:

- **Feature 1**: Brief description
- **Feature 2**: Brief description
- **Feature 3**: Brief description
```

### Reference File Structure Table

Links topics to reference files for progressive disclosure.

```markdown
## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Getting started | New to this tool |
| `advanced.md` | Deep features | Need more control |
| `gotchas.md` | Common issues | Debugging |
```

### Decision Trees

Navigate users to the right information.

```markdown
## Decision Tree

```
What do you need?
├─ Getting started → ./references/quickstart.md
├─ Advanced feature → ./references/advanced.md
│   ├─ Sub-feature A → Section in advanced.md
│   └─ Sub-feature B → Section in advanced.md
└─ Troubleshooting → ./references/gotchas.md
```
```

**Decision tree conventions:**

- Use ASCII box-drawing: `├─`, `└─`, `│`
- Keep to 2-3 levels of nesting
- Point to files or sections
- Use `→` for pointing

### Quick Reference Section

Essential commands/APIs in table format.

```markdown
## Quick Reference

| Command | Purpose |
|---------|---------|
| `cmd1` | Does X |
| `cmd2` | Does Y |
| `cmd3` | Does Z |
```

### Topic Index

Final section mapping all topics to locations.

```markdown
## Topic Index

| Topic | Reference File |
|-------|---------------|
| Installation | `./references/quickstart.md` |
| Configuration | `./references/config.md` |
| API Reference | `./references/api.md` |
| Troubleshooting | `./references/gotchas.md` |
```

## Formatting Conventions

### Tables

Use tables for:
- Quick lookups (commands, APIs)
- Comparisons
- Reference data

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data | Data | Data |
```

### Code Blocks

Always specify language for syntax highlighting:

````markdown
```python
def example():
    pass
```

```bash
echo "hello"
```

```yaml
key: value
```
````

### Bullet Points

Use for:
- Feature lists
- Guidelines
- Non-sequential items

```markdown
- Item 1
- Item 2
- Item 3
```

### Numbered Lists

Use for:
- Sequential steps
- Prioritized items
- Ordered procedures

```markdown
1. First step
2. Second step
3. Third step
```

## Writing Style

### Use Imperative Form

```markdown
# Good
Run the command.
Create a new file.
Configure the settings.

# Bad
The command should be run.
A new file is created.
You should configure the settings.
```

### Prefer Examples Over Prose

```markdown
# Good
```python
df.filter(pl.col("x") > 10)
```

# Less Good
To filter a DataFrame, use the filter method with a column expression
that specifies the condition you want to match against the data.
```

### Be Concise

Every line should justify its token cost.

```markdown
# Good
Use `ruff check --fix` to auto-fix linting issues.

# Bad
When you're running the linter and you want it to automatically
apply fixes for any issues it finds rather than just reporting
them, you can use the --fix flag with the ruff check command
to enable auto-fixing.
```

## Length Guidelines

| Section | Recommended Length |
|---------|-------------------|
| Intro | 1-2 sentences |
| "What is X?" | 3-5 bullet points |
| Decision tree | 5-15 lines per tree |
| Quick reference | 5-20 rows |
| Topic index | Match number of topics |

## When to Split Content

If SKILL.md exceeds 300-400 lines, consider splitting:

1. Move detailed reference content to `references/` files
2. Keep SKILL.md as a navigation hub
3. Use decision trees to point to reference files

See `progressive-disclosure.md` for splitting patterns.
