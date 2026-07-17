---
name: quarto
description: |
  Quarto document system for R: .qmd format with knitr engine, YAML frontmatter,
  code chunks with execution options, rendering to HTML/PDF. DAAF's R notebook
  format — Stage 9 literally archives executed R scripts in globally and
  per-chunk non-evaluating chunks paired with real execution logs. Optional
  display-only content may preview existing Parquet data or show already-created
  figures, but may not analyze data or generate figures. Use when execution
  language is R. Python equivalent: marimo.
autoload: never
metadata:
  audience: research-coders
  domain: r-library
  library-version: "Quarto 1.7.29"
  skill-last-updated: "2026-05-08"
  tags: ["r", "notebook", "quarto", "knitr", "reproducibility"]
---

# Quarto

Quarto open-source publishing system for R-based reproducible documents. Covers .qmd document format with knitr engine, YAML frontmatter configuration, R code chunks with `#|` execution options, inline R expressions, rendering to HTML/PDF/Word via `quarto render`, figure and table output from ggplot2/gt/kable, and cross-referencing. In DAAF Stage 9, its role narrows to literal non-evaluating script-and-log archival, with only bounded existing-data or existing-figure display allowed; broader report-authoring capabilities apply outside Stage 9. Use when the execution language is R and you need to assemble research notebooks, render analysis reports, or produce reproducible documents. Python equivalent: marimo skill.

## What is Quarto?

Quarto is an open-source **scientific and technical publishing system** built on Pandoc:
- **Language-agnostic**: Supports R (via knitr), Python, Julia, Observable JS
- **Multiple formats**: Render to HTML, PDF, Word, slides, websites, books
- **.qmd format**: Plain-text Markdown with YAML frontmatter and executable code chunks
- **Git-friendly**: .qmd files are plain text -- no binary notebook formats
- **CLI-driven**: `quarto render` produces output from the command line

In DAAF, Quarto serves the same role as marimo in Python pipelines: the Stage 9 notebook format that compiles executed scripts into a reviewable document artifact.

## Version Notes

This skill targets **Quarto 1.7.29** with **knitr 1.51** and **rmarkdown 2.31**.

Key features in Quarto 1.7.x:
- `#|` (hash-pipe) chunk option syntax is the standard (replaces legacy `{r, ...}` header syntax)
- Native cross-referencing with `@fig-`, `@tbl-`, `@sec-` prefixes
- YAML frontmatter for all format configuration
- `quarto render` CLI replaces `rmarkdown::render()` as the standard rendering path
- Typst output format available (alternative to LaTeX for PDF)

The `quarto` R package is NOT required. Quarto CLI invokes knitr directly -- the R package is a thin convenience wrapper that adds no functionality beyond what the CLI provides.

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Basic .qmd structure, YAML, R chunks, rendering | Starting a new .qmd document |
| `chunks.md` | Code chunk options (`#|` syntax), all execution options | Configuring chunk behavior |
| `format.md` | YAML frontmatter for HTML, PDF, Word, themes, TOC | Choosing and configuring output format |
| `figures.md` | Figure output from ggplot2, captions, sizing, cross-refs | Adding figures to documents |
| `tables.md` | Table output from gt, kable, kableExtra, cross-refs | Adding tables to documents |
| `daaf-notebook.md` | DAAF Stage 9 notebook assembly pattern for .qmd | **Required for Stage 9 notebook assembly** |
| `rendering.md` | `quarto render` CLI, format selection, parameters, batch | Rendering documents from command line |
| `gotchas.md` | Common pitfalls: chunk syntax, YAML, figure paths, cache | Debugging rendering issues |

### Reading Order

1. **New to Quarto?** Start with `quickstart.md` then `chunks.md`
2. **Configuring output?** Read `format.md` then `rendering.md`
3. **Adding figures/tables?** Read `figures.md` or `tables.md`
4. **DAAF Stage 9 notebook?** Read `daaf-notebook.md` (required)
5. **Having issues?** Check `gotchas.md` first

## Related Skills

**Always Load Together (when execution language is R):**
- `ggplot2` -- Visualization library used for figure chunks in .qmd documents
- `data-scientist` -- Methodology and validation principles that inform notebook structure

**Load for Specific Features:**
- `gt` -- Publication-quality tables in .qmd documents
- `fixest` -- Fixed effects regression output in .qmd documents

**Python Equivalent:**
- `marimo` -- DAAF's Python notebook format (same Stage 9 compilation role)

## CRITICAL: Stage 9 is Script COMPILATION, Not Report Authoring

**For DAAF research workflows**, the Stage 9 Quarto notebook has ONE job: **compile executed script contents into .qmd code chunks verbatim.**

### What Stage 9 IS

- **A script viewer** -- Paste script code into code chunks
- **An audit tool** -- Include execution logs to prove what ran
- **A file compiler** -- Read script files, copy contents, format as .qmd

### What Stage 9 is NOT

- NOT a place for new analysis code
- NOT a place for new data transformations
- NOT a place for interactive widgets or Shiny elements
- NOT a report authoring environment (the Report is a separate Stage 11 deliverable)

### Stage 9 Notebook Assembly

Stage 9 is handled by the **notebook-assembler agent** (see `.claude/agents/notebook-assembler.md`), which:
1. READS `.R` scripts from `scripts/stage{5,6,7,8}_*/`
2. EMITS the canonical rich YAML with global `execute: eval: false`, then one literal R archive chunk per script with exactly one `#| code-fold: false`, exactly one `#| eval: false`, and the exact `# --- VERBATIM COPY of scripts/<stage>/<filename>.R ---` marker as the first nonblank non-option line
3. COPIES the script code beneath that marker literally and un-commented
4. REQUIRES and COPIES each real, non-empty, non-placeholder execution log VERBATIM into exactly one immediately adjacent `::: {.callout-note collapse="true" title="Execution Log"}` block with one plain fenced body; a missing or ambiguous log blocks assembly
5. OPTIONALLY ADDS, only after the complete archive/log pair, either a bounded Parquet preview or display of an already-created figure; neither path performs analysis or creates/modifies a figure, and display content is not decompiled

The assembler emits only this canonical form. Bounded legacy containers accepted by `scripts/decompile_notebook.R` exist solely for intake compatibility and are not valid templates for new Stage 9 output. Structural recognition intentionally centers on the exact `VERBATIM COPY` marker; the Python/Marimo Plan-template path instead centers on literal `mo.md()` headers.

### ABSOLUTE PROHIBITIONS for Stage 9

| Prohibited Element | Why |
|-------------------|-----|
| New `library()` calls beyond arrow | No new analysis -- copy script code only |
| New `dplyr::filter()` | No filtering -- just load and display |
| New `dplyr::mutate()` | No transforms -- just load and display |
| New `dplyr::summarize()` | No new aggregations -- copy script code only |
| New `ggplot()` calls | No new plots -- copy script code only |
| Shiny runtime elements | Not an interactive app |
| `params:` YAML for dynamic reports | Not a parameterized report |

### The ONLY New Display Content Allowed

Stage 9 permits exactly two bounded display forms:

1. Preview existing Parquet data without transforming it:
```r
df <- arrow::read_parquet("path/to/file.parquet")
dplyr::glimpse(df)
head(df, 20)
```
2. Display an already-created Stage 8 figure. Prefer non-executing Markdown:
```markdown
![Figure description](output/figures/existing-figure.png)
```
When a chunk is needed, it must contain only `knitr::include_graphics("output/figures/existing-figure.png")` with `#| eval: true` and `#| echo: false`.

No filtering, mutation, selection, aggregation, plotting, or figure generation. The preview is bounded to the first 20 rows. (`dplyr::glimpse()` is namespace-qualified because inspection chunks attach no libraries — a bare `glimpse()` fails at render time.)

**See:**
- `.claude/agents/notebook-assembler.md` for the complete behavioral protocol
- `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` Stage 9 for template
- `./references/daaf-notebook.md` for the .qmd-specific assembly pattern

---

## Quick Decision Trees

### "I need to create a .qmd document"

```
Creating a .qmd?
|- Basic document structure -> ./references/quickstart.md
|- YAML frontmatter options -> ./references/format.md
|- R code chunks -> ./references/chunks.md
|- Rendering to output -> ./references/rendering.md
\- DAAF Stage 9 notebook -> ./references/daaf-notebook.md
```

### "I need to configure output format"

```
Choosing output format?
|- HTML (default, recommended) -> ./references/format.md
|- PDF (requires LaTeX or Typst) -> ./references/format.md
|- Word (.docx) -> ./references/format.md
|- Multiple formats -> ./references/rendering.md
\- Self-contained HTML -> ./references/format.md
```

### "I need to add figures or tables"

```
Adding visual elements?
|- ggplot2 figure -> ./references/figures.md
|- Base R plot -> ./references/figures.md
|- Figure sizing/captions -> ./references/figures.md
|- gt table -> ./references/tables.md
|- kable/kableExtra table -> ./references/tables.md
\- Cross-referencing -> ./references/figures.md or ./references/tables.md
```

### "I need to control code chunk behavior"

```
Chunk execution options?
|- Show/hide code (echo) -> ./references/chunks.md
|- Run/skip code (eval) -> ./references/chunks.md
|- Suppress warnings/messages -> ./references/chunks.md
|- Figure dimensions -> ./references/chunks.md
|- Cache expensive chunks -> ./references/chunks.md
\- Label chunks for cross-ref -> ./references/chunks.md
```

### "Something isn't working"

```
Having issues?
|- Chunk options not working -> ./references/gotchas.md (#| syntax)
|- YAML parse error -> ./references/gotchas.md (indentation)
|- Figures not showing -> ./references/gotchas.md (figure paths)
|- PDF won't render -> ./references/gotchas.md (LaTeX/Typst)
|- Cache problems -> ./references/gotchas.md (knitr cache)
\- quarto render fails -> ./references/rendering.md + ./references/gotchas.md
```

## File-First Execution and .qmd

Quarto .qmd documents fit DAAF's file-first execution model naturally:

1. **WRITE** the .qmd file to the appropriate location
2. **EXECUTE** via CLI: `quarto render document.qmd --to html`
3. **CAPTURE** -- output files are written alongside the .qmd (or to `--output-dir`)

The .qmd source file is the permanent record. The rendered output (HTML/PDF) is the deliverable. Both are stored in the project directory.

For Stage 9 notebooks specifically, the .qmd is assembled from existing executed scripts -- no new code execution occurs during assembly.

## Quick Reference

### Minimal .qmd Document

```markdown
---
title: "Analysis Title"
author: "Researcher Name"
date: today
format: html
---

## Section Heading

Narrative text with **bold** and *italic*.

```{r}
#| label: load-data
#| message: false

library(arrow)
df <- read_parquet("data/analysis_data.parquet")
head(df)
```

Results show `r nrow(df)` observations.
```

### Essential Chunk Options

| Option | Values | Purpose |
|--------|--------|---------|
| `echo` | `true`/`false` | Show/hide source code |
| `eval` | `true`/`false` | Execute/skip the chunk |
| `warning` | `true`/`false` | Show/suppress warnings |
| `message` | `true`/`false` | Show/suppress messages |
| `include` | `true`/`false` | Include chunk in output at all |
| `label` | string | Name the chunk (for cross-refs) |
| `fig-cap` | string | Figure caption |
| `fig-width` | number | Figure width in inches |
| `fig-height` | number | Figure height in inches |
| `tbl-cap` | string | Table caption |

### Essential CLI Commands

| Command | Purpose |
|---------|---------|
| `quarto render doc.qmd` | Render to default format |
| `quarto render doc.qmd --to html` | Render to HTML |
| `quarto render doc.qmd --to pdf` | Render to PDF |
| `quarto render doc.qmd --to docx` | Render to Word |
| `quarto preview doc.qmd` | Live preview with auto-reload |
| `quarto check knitr` | Verify R/knitr installation |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Document structure | `./references/quickstart.md` |
| YAML frontmatter | `./references/quickstart.md`, `./references/format.md` |
| R code chunks | `./references/quickstart.md`, `./references/chunks.md` |
| Chunk options (`#|` syntax) | `./references/chunks.md` |
| HTML format | `./references/format.md` |
| PDF format | `./references/format.md` |
| Word format | `./references/format.md` |
| Themes and styling | `./references/format.md` |
| Figure output | `./references/figures.md` |
| Figure cross-references | `./references/figures.md` |
| Table output | `./references/tables.md` |
| Table cross-references | `./references/tables.md` |
| DAAF Stage 9 notebook | `./references/daaf-notebook.md` |
| Script compilation pattern | `./references/daaf-notebook.md` |
| `quarto render` CLI | `./references/rendering.md` |
| Batch rendering | `./references/rendering.md` |
| Parameterized rendering | `./references/rendering.md` |
| Chunk syntax pitfalls | `./references/gotchas.md` |
| YAML indentation errors | `./references/gotchas.md` |
| Figure path issues | `./references/gotchas.md` |
| knitr cache problems | `./references/gotchas.md` |
| PDF rendering issues | `./references/gotchas.md` |

## Citation

When Quarto is used as the document format, include in the report's
Software & Tools references:

> Allaire, J.J., Teague, C., Scheidegger, C., Xie, Y., & Dervieux, C. (2024). Quarto (Version 1.7) [Computer software]. https://quarto.org

**Cite when:** The analysis notebook or report is delivered as a Quarto document (typically always true in DAAF R pipelines).
**Do not cite when:** Quarto is not used for document delivery.
