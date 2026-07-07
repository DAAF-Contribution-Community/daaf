# Quickstart

## What You Need

Quarto requires:
- **Quarto CLI** (1.7.29 in DAAF container) -- the rendering engine
- **R** (4.5.3) -- the computation language
- **knitr** (1.51) -- the R execution engine Quarto invokes
- **rmarkdown** (2.31) -- provides knitr infrastructure

The `quarto` R package is NOT required. The CLI calls knitr directly.

### Verify Installation

```bash
quarto --version
# 1.7.29

quarto check knitr
# Checks R, knitr, rmarkdown, and renders a test document
```

## Basic .qmd Document

### Minimal Example

Create a file named `analysis.qmd`:

````markdown
---
title: "My Analysis"
format: html
---

## Introduction

This is a Quarto document with R code.

```{r}
1 + 1
```
````

### Render It

```bash
quarto render analysis.qmd
```

This produces `analysis.html` in the same directory.

## .qmd File Structure

Every .qmd document has three parts:

```
---
YAML frontmatter (document metadata and format options)
---

Markdown content (narrative text, headings, lists, etc.)

Code chunks (executable R code blocks)
```

### 1. YAML Frontmatter

The YAML block at the top configures the document:

```yaml
---
title: "Analysis Title"
author: "Author Name"
date: today
format: html
---
```

Common frontmatter fields:

| Field | Purpose | Example |
|-------|---------|---------|
| `title` | Document title | `"School Poverty Analysis"` |
| `author` | Author name(s) | `"Research Team"` |
| `date` | Document date | `today`, `"2026-05-08"`, `last-modified` |
| `format` | Output format | `html`, `pdf`, `docx` |
| `execute` | Global chunk options | `echo: false` |

### 2. Markdown Content

Standard Markdown between code chunks:

```markdown
## Section Heading

Regular paragraph text with **bold**, *italic*, and `code`.

- Bullet list item
- Another item

1. Numbered item
2. Another item

> Blockquote text

[Link text](https://example.com)
```

### 3. R Code Chunks

Executable code blocks with `{r}` language identifier:

````markdown
```{r}
#| label: load-data

library(arrow)
df <- read_parquet("data/analysis.parquet")
nrow(df)
```
````

Key elements:
- Opening fence: `` ```{r} ``
- Chunk options: Lines starting with `#|` (hash-pipe)
- R code: Standard R code
- Closing fence: `` ``` ``

## Chunk Options with #| Syntax

Quarto uses the `#|` (hash-pipe) syntax for chunk options. Place them at the top of the chunk, one per line:

````markdown
```{r}
#| label: summary-stats
#| echo: false
#| warning: false

summary(df)
```
````

The most commonly used options:

| Option | Default | Purpose |
|--------|---------|---------|
| `label` | (none) | Name the chunk (used for cross-refs) |
| `echo` | `true` | Show source code in output |
| `eval` | `true` | Actually run the code |
| `warning` | `true` | Show warning messages |
| `message` | `true` | Show R messages |
| `include` | `true` | Include chunk and output at all |

See `./chunks.md` for the complete options reference.

## Inline R Code

Embed R expressions in narrative text:

```markdown
The dataset contains `r nrow(df)` observations across `r ncol(df)` variables.
```

This renders as: "The dataset contains 5000 observations across 12 variables."

Inline expressions:
- Delimited by single backticks with `r` prefix
- Must be a single R expression (no assignments)
- Result is coerced to character and inserted into text

## Output Formats

### HTML (default, recommended)

```yaml
---
format: html
---
```

### PDF (requires LaTeX)

```yaml
---
format: pdf
---
```

Requires TinyTeX or a full LaTeX distribution. Install TinyTeX:

```bash
quarto install tinytex
```

### Word

```yaml
---
format: docx
---
```

### Multiple Formats

```yaml
---
format:
  html: default
  pdf: default
  docx: default
---
```

Render a specific format:

```bash
quarto render doc.qmd --to pdf
```

## Rendering from the Command Line

### Basic Rendering

```bash
# Render to default format specified in YAML
quarto render analysis.qmd

# Override format
quarto render analysis.qmd --to html
quarto render analysis.qmd --to pdf
quarto render analysis.qmd --to docx
```

### Specify Output File

```bash
quarto render analysis.qmd --output report.html
quarto render analysis.qmd --output-dir output/
```

### Preview with Auto-Reload

```bash
quarto preview analysis.qmd
```

Opens a browser with live preview. Changes to the .qmd trigger re-render.

## A Complete Example

````markdown
---
title: "School Enrollment Analysis"
author: "Research Team"
date: today
format:
  html:
    toc: true
    code-fold: true
---

## Overview

This analysis examines enrollment trends across public schools.

```{r}
#| label: setup
#| message: false

library(arrow)
library(dplyr)
library(ggplot2)
```

```{r}
#| label: load-data

df <- read_parquet("data/enrollment.parquet")
cat("Loaded", nrow(df), "records\n")
```

## Summary Statistics

```{r}
#| label: tbl-summary
#| tbl-cap: "Enrollment summary by year"

df |>
  group_by(year) |>
  summarize(
    n_schools = n(),
    mean_enrollment = mean(enrollment, na.rm = TRUE)
  ) |>
  knitr::kable()
```

## Enrollment Distribution

```{r}
#| label: fig-distribution
#| fig-cap: "Distribution of school enrollment"
#| fig-width: 8
#| fig-height: 5

ggplot(df, aes(x = enrollment)) +
  geom_histogram(bins = 50) +
  theme_minimal() +
  labs(x = "Enrollment", y = "Count")
```

As shown in @fig-distribution, enrollment follows a right-skewed distribution.
See @tbl-summary for yearly trends.

## Conclusion

The analysis covers `r nrow(df)` school records.
````

## Git-Friendly Format

.qmd files are plain text, making them ideal for version control:

- No binary blobs (unlike .ipynb)
- Clean diffs on content changes
- Merge-friendly structure
- YAML frontmatter is human-readable

The output files (.html, .pdf) are typically gitignored -- only the .qmd source is tracked.

## Next Steps

- Configure chunk behavior: `./chunks.md`
- Customize output format: `./format.md`
- Add figures: `./figures.md`
- Add tables: `./tables.md`
- DAAF notebook assembly: `./daaf-notebook.md`
