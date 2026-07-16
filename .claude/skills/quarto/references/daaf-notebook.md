# DAAF Stage 9 Notebook Assembly (.qmd)

## Purpose

This file is the **canonical DAAF Stage 9 R/Quarto assembly contract**. In DAAF
R pipelines, the Stage 9 notebook is a `.qmd` document that **compiles executed
scripts into a single reviewable artifact**. It serves the same role as the
marimo notebook in Python pipelines: a structured audit trail, not a new
analysis environment.

The notebook-assembler agent (`.claude/agents/notebook-assembler.md`) handles
assembly. Other live framework files may summarize this contract, but they
must preserve the YAML, archive-chunk, execution-log, and optional-inspection
patterns defined here.

### Consumer Scope

This contract governs **DAAF archive-shaped Quarto notebooks**: Stage 9 `.qmd`
files whose R chunks archive executed Stage 5-8 scripts under the exact
`# --- VERBATIM COPY of scripts/<path> ---` marker and place each script's log
in the immediately following collapsed Execution Log callout. Reproducibility
Verification consumers use those DAAF structural anchors; they do not attempt
to infer or decompile arbitrary Quarto documents, general knitr semantics, or
unmarked R chunks.

## Core Principle

**Copy, don't create.** Every *archive* chunk contains literal R code that was
already written and executed during Stages 5-8, paired with its real execution
log. The notebook adds brief Plan-derived narrative structure but introduces no
new analysis logic. The only non-archive code allowed is a bounded display-only
chunk that either reads/heads existing Parquet data without filtering,
transforming, selecting, or aggregating, or displays an already-created figure
without generating or modifying it. Display content is not decompiled.

The notebook-assembler emits only the canonical structures in this document.
Bounded legacy forms accepted by `scripts/decompile_notebook.R` are intake
compatibility for older archives, not alternatives for newly emitted Stage 9
notebooks. Structural recognition intentionally centers on the exact `VERBATIM
COPY` marker; in the Python/Marimo Plan-template path, recognition instead
centers on literal `mo.md()` script headers.

## .qmd Notebook Template

The concrete code and log values below illustrate the canonical structure only.
For a project notebook, replace each sample bundle with the selected script's
literal code and real log; never emit these examples as project evidence.

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
#| eval: false

# --- VERBATIM COPY of scripts/stage5_fetch/01_fetch-source.R ---
# --- Config ---
output_path <- "data/raw/YYYY-MM-DD_source_data.parquet"
cat(sprintf("Saved existing output to %s\n", output_path))
```

::: {.callout-note collapse="true" title="Execution Log"}
```
Executed: 2026-01-24 14:32:05
Exit code: 0
CP1 STATUS: PASSED
```
:::

#### Data Inspection

```{r}
#| label: inspect-raw-data
#| eval: true
#| echo: false

df <- arrow::read_parquet("data/raw/YYYY-MM-DD_source_data.parquet")
dplyr::glimpse(df)
head(df, 20)
```

---

## Stage 6: Data Cleaning

### 6.1 [First clean script description]

Source: `scripts/stage6_clean/01_clean-source.R`

```{r}
#| label: stage6-01-clean
#| code-fold: false
#| eval: false

# --- VERBATIM COPY of scripts/stage6_clean/01_clean-source.R ---
# --- Load ---
cleaned_path <- "data/processed/YYYY-MM-DD_cleaned.parquet"
cat(sprintf("Validated existing output at %s\n", cleaned_path))
```

::: {.callout-note collapse="true" title="Execution Log"}
```
Executed: 2026-01-24 14:38:10
Exit code: 0
CP2 STATUS: PASSED
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

**Execution-flag contract (belt-and-suspenders):** the notebook sets
`eval: false` globally in the YAML `execute:` block AND every script-archive
chunk carries its own `#| eval: false`; optional data-preview and dedicated
figure-display chunks are the ONLY chunks that opt back in with `#| eval:
true`. Standard Markdown image syntax does not execute R and therefore needs
no chunk. The redundancy is deliberate: the global flag protects chunks that
lose their per-chunk option in editing, and the per-chunk flag keeps each
archive chunk safe even if the frontmatter is changed. This contract is
stated identically in `.claude/agents/notebook-assembler.md`.

## Chunk Patterns

### Script Code Chunk (most common)

````markdown
```{r}
#| label: stage5-01-fetch
#| code-fold: false
#| eval: false

# --- VERBATIM COPY of scripts/stage5_fetch/01_fetch-source.R ---
# --- Config ---
output_path <- "data/raw/YYYY-MM-DD_source_data.parquet"
cat(sprintf("Saved existing output to %s\n", output_path))
```
````

Rules:
- Label follows pattern: `stage{N}-{step}-{description}`
- `code-fold: false` -- code must be visible (overrides any global setting)
- `#| eval: false` -- per-chunk half of the belt-and-suspenders contract
  (in addition to the global `execute: eval: false`)
- The `# --- VERBATIM COPY of scripts/<path> ---` marker line is MANDATORY,
  appears as the first nonblank line after zero or more `#|` option lines, and
  occurs exactly once in the chunk. `<path>` is exactly one canonical stage
  directory (`stage5_fetch`, `stage6_clean`, `stage7_transform`, or
  `stage8_analysis`) plus one safe filename ending in uppercase `.R`. The marker
  is the anchor `scripts/decompile_notebook.R` uses to identify script chunks
  and recover source paths
- Exactly one `#| eval: false` and exactly one `#| code-fold: false` precede the marker
- Script code is pasted EXACTLY as written and remains literal and un-commented;
  do not prefix R code lines with `#` (existing source comments remain comments), including:
  - All `# INTENT:`, `# REASONING:`, `# ASSUMES:` IAT annotations
  - All inline validation code
  - All section separators (`# --- Config ---`, etc.)
  - All comments

### Execution Log Block

````markdown
::: {.callout-note collapse="true" title="Execution Log"}
```
Executed: 2026-01-24 14:32:05
Exit code: 0
CP1 STATUS: PASSED
```
:::
````

The assembler emits exactly one callout with the literal opener
`::: {.callout-note collapse="true" title="Execution Log"}` and exactly one
plain fenced body. It must appear immediately after the archive chunk whose log
it contains, with blank lines only between the chunk and callout, so Stage 9 and
RV consumers can associate the pair structurally. The fenced body must contain
the real, non-empty execution log from `run_with_capture.sh`; placeholders such
as `No execution log found` (or instructions to paste/copy a log later) are not
evidence and must not appear in a canonical Stage 9 archive. A missing, empty,
ambiguous, or placeholder log blocks canonical assembly until the source script
is corrected. Do not emit an empty callout or a legacy `<details>` container as
a fallback. Logs are important for the audit trail but would clutter the
document if always expanded.

### Data Inspection Chunk

````markdown
```{r}
#| label: inspect-cleaned-data
#| eval: true
#| echo: false

df <- arrow::read_parquet("data/processed/YYYY-MM-DD_cleaned.parquet")
dplyr::glimpse(df)
head(df, 20)
```
````

This is one of two permitted Stage 9 display types. A data-preview chunk:
- Loads a parquet file with `arrow::read_parquet()`
- Previews structure with `dplyr::glimpse(df)` and the first 20 rows with
  `head(df, 20)` — `glimpse` must be namespace-qualified because inspection
  chunks attach no libraries and a bare `glimpse()` fails at render time
- Contains nothing else — no filtering, transforming, summarizing, or table
  formatting

### Existing Figure Display

Existing saved Stage 8 figures may be displayed, but Stage 9 must not create a
new visualization. The preferred form is standard Markdown image syntax, which
references the existing file without executing R:

```markdown
![Figure description](output/figures/YYYY-MM-DD_existing-figure.png)
```

A dedicated display chunk is the allowed alternative when Quarto chunk handling
is needed. It contains only `knitr::include_graphics()` and explicitly opts in
to execution:

````markdown
```{r}
#| label: display-existing-figure
#| eval: true
#| echo: false

knitr::include_graphics("output/figures/YYYY-MM-DD_existing-figure.png")
```
````

This is the second permitted Stage 9 display type alongside the non-transforming
Parquet preview. Do not add plotting code, transformations, summaries, table
formatting, or any other R statements to the display chunk.

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
   c. Require the real, non-placeholder execution log and add it in exactly one immediately adjacent `::: {.callout-note collapse="true" title="Execution Log"}` block with one plain fenced body; stop for correction if the source boundary or log is missing, empty, ambiguous, or placeholder-only
   d. Only after the archive/log pair, optionally add either a non-transforming data-preview chunk or an existing-figure display (Markdown image preferred; a dedicated `knitr::include_graphics()` display chunk is allowed)
5. **Add** metadata section at the end

## What the Notebook Does NOT Contain

| Prohibited | Why | What to Do Instead |
|-----------|-----|-------------------|
| New R code beyond the permitted display types | Stage 9 compiles, not creates | Use only the canonical Parquet preview, standard Markdown image syntax, or a dedicated `knitr::include_graphics()` display chunk for an existing figure |
| `knitr::include_graphics()` mixed with plotting or other new R statements | The bounded figure-display exception must not become a new analysis chunk | Use a dedicated chunk containing only `knitr::include_graphics("existing/path.png")`, with `#| eval: true` and `#| echo: false`, or prefer standard Markdown image syntax |
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
| Archive non-execution | Global + per-chunk `eval: false`; literal R remains visible | Every Python source line is comment-prefixed and the archive cell ends with one canonical `pass` |
| Data display | `dplyr::glimpse(df)` + `head(df, 20)` | `mo.ui.table(df.head(100))` |
| Collapsible logs | `::: {.callout-note collapse="true"}` block | `mo.accordion()` |
| Output format | Rendered HTML via `quarto render` | marimo app or exported HTML |
| Git format | Plain text .qmd | Plain text .py |

Both formats serve the identical purpose: structured audit trail of executed scripts.

## Rendering the Stage 9 Notebook

After assembly:

```bash
quarto render YYYY-MM-DD_Project_Notebook.qmd --to html
```

The rendered HTML is the deliverable notebook artifact. The `.qmd` source is
the archival record.

`quarto render` validates the document's YAML, Markdown, chunk syntax, resource
references, and any optional preview or dedicated figure-display chunks that
explicitly opt into `#| eval: true`. Because `eval: false` is set globally and
repeated on every script-archive chunk, rendering does **not** re-run the
archived Stage 5-8 analysis scripts and is not a full analysis reproduction
test. Those scripts' prior executions and captured logs remain the audit
evidence; reproduction is a separate workflow.

If present, enabled data-preview chunks require their referenced parquet files
and packages to be accessible at render time. Enabled dedicated figure-display
chunks require their existing image files to resolve; Markdown image references
require no R execution. A notebook with no enabled preview or figure-display
chunks renders without executing R archive code.
