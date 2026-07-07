# DAAF Stage 9 Notebook Assembly (.qmd)

## Purpose

In DAAF R pipelines, the Stage 9 notebook is a .qmd document that **compiles
executed scripts into a single reviewable artifact**. It serves the same role
as the marimo notebook in Python pipelines: a structured audit trail, not a
new analysis environment.

The notebook-assembler agent (`.claude/agents/notebook-assembler.md`) handles
assembly. This reference documents the .qmd-specific patterns.

## Core Principle

**Copy, don't create.** Every code chunk in a Stage 9 notebook contains
script code that was already written and executed during Stages 5-8. The
notebook adds narrative structure around this code but introduces no new
analysis logic.

## .qmd Notebook Template

````markdown
---
title: "Research Notebook: [Project Title]"
subtitle: "[Date Prefix] [Short Description]"
author: "[Researcher Name]"
date: today
format:
  html:
    toc: true
    toc-depth: 2
    code-fold: show
    embed-resources: true
    theme: cosmo
execute:
  echo: true
  eval: false
  warning: false
---

## Project Overview

[Brief description of the research question and approach. 2-3 sentences.]

**Date prefix:** [YYYY-MM-DD]
**Execution language:** R
**Data sources:** [List primary data sources]

---

## Stage 5: Data Acquisition

### 5.1 [First fetch script description]

Source: `scripts/stage5_fetch/01_fetch-source.R`

```{r}
#| label: stage5-01-fetch
#| code-fold: false

# --- VERBATIM COPY of scripts/stage5_fetch/01_fetch-source.R ---
[Exact script contents pasted here]
```

::: {.callout-note collapse="true" title="Execution Log"}
```
[Exact execution log output pasted here]
```
:::

#### Data Inspection

```{r}
#| label: inspect-raw-data
#| eval: true
#| echo: false

df <- arrow::read_parquet("data/raw/YYYY-MM-DD_source_data.parquet")
glimpse(df)
head(df, 20)
```

---

## Stage 6: Data Cleaning

### 6.1 [First clean script description]

Source: `scripts/stage6_clean/01_clean-source.R`

```{r}
#| label: stage6-01-clean
#| code-fold: false

# --- VERBATIM COPY of scripts/stage6_clean/01_clean-source.R ---
[Exact script contents pasted here]
```

::: {.callout-note collapse="true" title="Execution Log"}
```
[Exact execution log output pasted here]
```
:::

---

## Stage 7: Transformation

[Same pattern as above for each transform script]

---

## Stage 8: Analysis & Visualization

[Same pattern as above for each analysis script]

---

## Metadata

**Scripts compiled:** [count]
**Assembly date:** [date]
**Notebook format:** Quarto .qmd with knitr engine
````

## Key YAML Settings

```yaml
execute:
  echo: true    # Show all code (it IS the audit trail)
  eval: false   # Do NOT re-execute scripts
```

- `echo: true` -- The entire point is showing the code
- `eval: false` -- Scripts were already executed; re-running would fail
  (dependencies, data paths, etc. may not resolve in notebook context)

The ONLY chunks with `eval: true` are data inspection chunks that load
parquet files for display.

## Chunk Patterns

### Script Code Chunk (most common)

````markdown
```{r}
#| label: stage5-01-fetch
#| code-fold: false

# --- VERBATIM COPY of scripts/stage5_fetch/01_fetch-source.R ---
# [Full script contents, including all comments, IAT annotations, etc.]
```
````

Rules:
- Label follows pattern: `stage{N}-{step}-{description}`
- `code-fold: false` -- code must be visible (overrides any global setting)
- Script code is pasted EXACTLY as written, including:
  - All `# INTENT:`, `# REASONING:`, `# ASSUMES:` IAT annotations
  - All inline validation code
  - All section separators (`# --- Config ---`, etc.)
  - All comments

### Execution Log Block

````markdown
::: {.callout-note collapse="true" title="Execution Log"}
```
[Paste the stdout/stderr output that run_with_capture.sh appended to the script]
```
:::
````

The Quarto callout block with `collapse="true"` creates a collapsible section
(analogous to marimo's `mo.accordion()`). Logs are important for the audit trail
but would clutter the document if always expanded.

### Data Inspection Chunk

````markdown
```{r}
#| label: inspect-cleaned-data
#| eval: true
#| echo: false

df <- arrow::read_parquet("data/processed/YYYY-MM-DD_cleaned.parquet")
glimpse(df)
head(df, 20)
```
````

These are the ONLY chunks with `eval: true`. They:
- Load a parquet file with `arrow::read_parquet()`
- Preview structure with `glimpse(df)` and the first 20 rows with `head(df, 20)`
- Nothing else -- no filtering, no transforming, no summarizing

### Narrative Cell (Markdown)

````markdown
## Stage 6: Data Cleaning

This stage applies validation rules and standardizes variable formats.
[Brief description of what the cleaning accomplished, drawn from the
plan document.]
````

Narrative cells provide context between script chunks. They should be brief
and factual, drawn from the research plan -- not new interpretation.

## Assembly Procedure

The notebook-assembler agent follows this sequence:

1. **Read** the research plan and plan tasks to understand the script sequence
2. **Read** each script file in stage order (5 -> 6 -> 7 -> 8)
3. **Create** the .qmd YAML frontmatter with project metadata
4. **For each script:**
   a. Add a Markdown narrative cell with the script's purpose
   b. Add a code chunk with the FULL script contents (verbatim)
   c. Add the execution log in a `::: {.callout-note collapse="true"}` block
   d. Optionally add a data inspection chunk for key outputs
5. **Add** metadata section at the end

## What the Notebook Does NOT Contain

| Prohibited | Why | What to Do Instead |
|-----------|-----|-------------------|
| New R code beyond `arrow::read_parquet()` + `glimpse()`/`head()` | Stage 9 compiles, not creates | Put new analysis in Stage 8 scripts |
| `library()` calls beyond `arrow` | No new dependencies | Libraries are in the copied scripts |
| Parameterized rendering (`params:`) | Not a dynamic report | The notebook is a static artifact |
| Shiny runtime | Not an interactive app | Use standalone Shiny for interactivity |
| New visualizations | Plots belong in Stage 8 scripts | Copy the plotting scripts verbatim |
| Summary tables from new aggregations | Summaries belong in Stage 8 | Copy the summary scripts verbatim |

## Differences from marimo (Python) Stage 9

| Aspect | Quarto .qmd (R) | marimo .py (Python) |
|--------|------------------|---------------------|
| File format | .qmd (Markdown + YAML) | .py (Python) |
| Code blocks | ```` ```{r} ```` fenced chunks | `@app.cell` decorated functions |
| Execution model | Sequential, top-to-bottom | Reactive (DAG-based) |
| Non-execution flag | `eval: false` in YAML | Code is display-only in cell wrappers |
| Data display | `glimpse(df)` + `head(df, 20)` | `mo.ui.table(df.head(100))` |
| Collapsible logs | `::: {.callout-note collapse="true"}` block | `mo.accordion()` |
| Output format | Rendered HTML via `quarto render` | marimo app or exported HTML |
| Git format | Plain text .qmd | Plain text .py |

Both formats serve the identical purpose: structured audit trail of executed scripts.

## Rendering the Stage 9 Notebook

After assembly:

```bash
quarto render YYYY-MM-DD_Project_Notebook.qmd --to html
```

The rendered HTML is the deliverable notebook artifact. The .qmd source is
the archival record.

Since `eval: false` is set globally, rendering is fast -- Quarto just formats
the Markdown and code blocks without executing R.

The data inspection chunks (`eval: true`) will execute and require that the
parquet files are accessible at the specified paths.
