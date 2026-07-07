---
name: gt
description: >-
  R table formatting with gt, kableExtra, modelsummary. Publication-quality
  tables: gt() grammar-of-tables, fmt_*() formatting, tab_*() structure,
  gtsave() export. Use when execution language is R. No dedicated Python skill
  yet; for Python, the installed great-tables package covers similar needs.
autoload: never
metadata:
  audience: research-coders
  domain: r-library
  library-version: "gt 1.3.0"
  skill-last-updated: "2026-05-13"
  tags: ["r", "tables", "gt", "kableExtra", "modelsummary", "formatting"]
---

# gt Skill

R table formatting ecosystem for publication-quality tables. Covers gt 1.3.0 for
grammar-of-tables construction (gt(), fmt_*() number formatting, tab_*() structure,
cols_*() column operations, gtsave() export), kableExtra 1.4.0 for knitr/kable
HTML and LaTeX table styling in Quarto documents, and modelsummary 2.6.0 for
formatting regression output from lm/glm/fixest/plm models into publication tables.
Use when execution language is R and the task involves creating formatted data
tables, summary tables, or regression tables for reports or papers. No dedicated
Python-side skill exists yet, but the `great-tables` Python package (same author,
same grammar of tables) is installed in DAAF and usable directly. For
visualization (charts/plots), use ggplot2 instead. For document structure and
rendering, use quarto instead.

## What is gt?

gt implements a **grammar of tables** for R, analogous to ggplot2's grammar of
graphics but for tabular output:

- **Declarative**: Build tables by layering formatting, structure, and style
- **Pipeline-friendly**: Chain operations with `|>` (data frame in, gt table out)
- **Rich formatting**: Number formatting (fmt_number, fmt_percent, fmt_currency),
  conditional styling, color scales, icons, images in cells
- **Structured**: Table header, column spanners, row groups, summary rows,
  footnotes, source notes
- **Export**: HTML, PNG, LaTeX, Word, RTF via gtsave()

**kableExtra** extends knitr's `kable()` for HTML and LaTeX table styling:
- Lightweight alternative when gt is overkill (simple summary tables in Quarto)
- Row/column styling, striped rows, scroll boxes, grouped rows
- Tight integration with Quarto's knitr engine

**modelsummary** formats regression output into publication-ready tables:
- Supports 100+ model classes (lm, glm, fixest, plm, survey, etc.)
- Side-by-side model comparison with custom coefficient labels
- Output to gt, kableExtra, HTML, LaTeX, Word, markdown, PNG
- Robust/clustered SEs via `vcov` argument (no re-fitting needed)
- Already covered in depth by the r-stats skill (`reporting.md`) and referenced
  by fixest -- this skill provides the table-formatting perspective

## Version Notes

- **gt 1.3.0**: Stable release. Full grammar-of-tables API. `fmt_*()` family for
  number formatting, `tab_*()` for structural elements, `cols_*()` for column
  operations, `opt_*()` for table options.
- **kableExtra 1.4.0**: Stable release. `kbl()` replaces `knitr::kable()` as the
  recommended entry point. Full HTML and LaTeX styling support.
- **modelsummary 2.6.0**: Supports gt and kableExtra as output backends. The
  default output backend in modelsummary 2.x is **tinytable** — request a gt
  object explicitly with `output = "gt"`. See r-stats skill `reporting.md` for
  comprehensive modelsummary coverage.
- **knitr 1.51**: Provides the underlying `kable()` function that kableExtra
  extends.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Basic gt() table, headers/footers/source notes, simple formatting | Starting out or need a quick table |
| `formatting.md` | fmt_*() family, conditional styling, spanners, row groups, summary rows | Detailed formatting and structure |
| `modelsummary-tables.md` | Regression tables via modelsummary(), customization, multi-model comparison | Formatting regression output |
| `export.md` | gtsave(), kableExtra in Quarto, inline tables in .qmd, output formats | Saving or embedding tables |

### Reading Order

1. **Quick data table?** Start with `quickstart.md`
2. **Complex formatting?** Read `formatting.md`
3. **Regression table?** Read `modelsummary-tables.md`
4. **Saving or embedding?** Read `export.md`
5. **Simple Quarto table?** Read `export.md` (kableExtra section)

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `ggplot2` | Visualization (charts/plots) -- use ggplot2 for figures, gt for tables |
| `quarto` | Document rendering -- gt/kableExtra tables render in .qmd documents |
| `fixest` | Regression output -- fixest models feed into modelsummary/gt tables. fixest's own `etable()` is an alternative to modelsummary for fixest-only output |
| `r-stats` | Regression output -- lm/glm models feed into modelsummary/gt tables. r-stats `reporting.md` has comprehensive modelsummary coverage |
| `plm` | Panel model output -- plm models feed into modelsummary/gt tables |
| `data-scientist` | Methodology guidance for what to present in tables |

**Python counterpart:** There is no dedicated Python table-formatting skill in
DAAF yet, but the `great-tables` Python package (version 0.21.0, by the same
author as gt, implementing the same grammar of tables) **is installed** and can
be used directly in Python pipelines. For regression tables in Python,
modelsummary-equivalent functionality is partially covered by pyfixest's
`etable()` and statsmodels' `summary()`.

## Quick Decision Trees

### "I need to make a table"

```
What kind of table?
+-- Data summary table (descriptive stats, crosstabs)
|   +-- Simple (few rows/columns, minimal formatting)
|   |   +-- In a Quarto doc? --> kableExtra kbl() in ./references/export.md
|   |   +-- Standalone? --> gt() in ./references/quickstart.md
|   +-- Complex (conditional formatting, row groups, summary rows)
|       +-- gt() in ./references/formatting.md
+-- Regression table (model coefficients)
|   +-- Single model --> ./references/modelsummary-tables.md
|   +-- Multiple models side-by-side --> ./references/modelsummary-tables.md
|   +-- fixest models only --> Consider fixest etable() (see fixest skill)
|       OR modelsummary() for more customization
+-- Frequency / cross-tabulation table
|   +-- gt() with row groups --> ./references/formatting.md
+-- Table with color scales or conditional formatting
    +-- gt tab_style() or data_color() --> ./references/formatting.md
```

### "Which package should I use?"

```
Choosing a table package?
+-- Publication-quality data table with rich formatting
|   +-- gt() (most flexible, best output quality)
+-- Regression table (multiple models, SEs, goodness-of-fit)
|   +-- modelsummary() (purpose-built for this)
+-- Simple table in a Quarto document
|   +-- kableExtra kbl() (lightweight, integrates with knitr)
+-- Quick console output (not for publication)
|   +-- print() or knitr::kable() (no extra packages needed)
+-- LaTeX table for a journal submission
    +-- gt() with gtsave("file.tex") OR modelsummary(output = "latex")
```

## File-First Execution in Research Workflows

In DAAF research pipelines, tables are generated through **script files** in
`scripts/stage8_analysis/`, not interactively. This ensures auditability and
reproducibility.

**The pattern:**
1. Write table code to `scripts/stage8_analysis/{step}_{table-name}.R`
2. Execute via `bash {BASE_DIR}/scripts/run_with_capture.sh {script_path}`
3. Output gets appended to the script as comments
4. Use `gtsave()` to save tables to the project output directory

See `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first
execution protocol.

## Quick Reference

### Essential Setup

```r
library(gt)
library(kableExtra)
library(modelsummary)
```

### Basic gt Table

```r
tbl <- df |>
  gt() |>
  tab_header(
    title = "Table Title",
    subtitle = "Subtitle or description"
  ) |>
  tab_source_note("Source: Dataset name, year.") |>
  fmt_number(columns = where(is.numeric), decimals = 2)
```

### Core gt Operations

| Operation | Code |
|-----------|------|
| Create table | `gt(df)` or `df |> gt()` |
| Title/subtitle | `tab_header(title, subtitle)` |
| Source note | `tab_source_note("Source: ...")` |
| Footnote | `tab_footnote(footnote, locations)` |
| Format numbers | `fmt_number(columns, decimals)` |
| Format percent | `fmt_percent(columns, decimals)` |
| Format currency | `fmt_currency(columns, currency)` |
| Format date | `fmt_date(columns, date_style)` |
| Column spanner | `tab_spanner(label, columns)` |
| Row group | `gt(groupname_col = "group_var")` |
| Summary row | `summary_rows(groups, fns, columns)` |
| Conditional style | `tab_style(style, locations)` |
| Column labels | `cols_label(col1 = "Label 1")` |
| Hide columns | `cols_hide(columns)` |
| Column width | `cols_width(col1 ~ px(150))` |
| Save | `gtsave(tbl, "file.html")` |

### kableExtra Quick Pattern

```r
df |>
  kbl(format = "html", digits = 2, caption = "Table Title") |>
  kable_styling(bootstrap_options = c("striped", "hover", "condensed")) |>
  add_header_above(c(" " = 1, "Group A" = 2, "Group B" = 2))
```

### modelsummary Quick Pattern

```r
modelsummary(
  list("Model 1" = fit1, "Model 2" = fit2),
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001),
  coef_rename = c("x1" = "Education", "x2" = "Experience"),
  gof_map = c("nobs", "r.squared", "adj.r.squared"),
  output = "gt"
)
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Basic gt table creation | `./references/quickstart.md` |
| tab_header, tab_source_note | `./references/quickstart.md` |
| tab_footnote | `./references/quickstart.md` |
| Simple number formatting | `./references/quickstart.md` |
| cols_label column renaming | `./references/quickstart.md` |
| fmt_number, fmt_percent, fmt_currency | `./references/formatting.md` |
| fmt_date, fmt_integer | `./references/formatting.md` |
| Conditional formatting (tab_style) | `./references/formatting.md` |
| Color scales (data_color) | `./references/formatting.md` |
| Column spanners (tab_spanner) | `./references/formatting.md` |
| Row groups | `./references/formatting.md` |
| Summary rows | `./references/formatting.md` |
| Grand summary | `./references/formatting.md` |
| Column width and alignment | `./references/formatting.md` |
| Merge cells | `./references/formatting.md` |
| modelsummary basic usage | `./references/modelsummary-tables.md` |
| Multi-model comparison | `./references/modelsummary-tables.md` |
| Coefficient renaming and omission | `./references/modelsummary-tables.md` |
| Custom statistics rows | `./references/modelsummary-tables.md` |
| Robust/clustered SEs in tables | `./references/modelsummary-tables.md` |
| fixest models in modelsummary | `./references/modelsummary-tables.md` |
| Stars and significance formatting | `./references/modelsummary-tables.md` |
| gtsave to HTML/PNG/LaTeX | `./references/export.md` |
| kableExtra in Quarto | `./references/export.md` |
| Inline tables in .qmd | `./references/export.md` |
| Output format comparison | `./references/export.md` |

## Citation

When gt is used as a primary table-formatting tool, include in the report's
Software & Tools references:

> Iannone, R., Cheng, J., Schloerke, B., Hughes, E., Lauer, A., & Seo, J.
> (2024). gt: Easily Create Presentation-Ready Display Tables. R package
> version 1.3.0. https://gt.rstudio.com/

**Cite when:** gt produces tables included in the report or deliverables.
**Do not cite when:** Only used for quick exploratory tables not included in
deliverables.

For modelsummary citation (when used for regression tables):

> Arel-Bundock, V. (2022). "modelsummary: Data and Model Summaries in R."
> Journal of Statistical Software, 103(1), 1-23.

For kableExtra citation (when used for Quarto table styling):

> Zhu, H. (2024). kableExtra: Construct Complex Table with kable and Pipe
> Syntax. R package version 1.4.0.
