# Code Chunk Options

## The #| Syntax

Quarto uses `#|` (hash-pipe) for chunk options. This is the standard and only
recommended syntax. Place options at the top of the chunk, one per line:

````markdown
```{r}
#| label: my-chunk
#| echo: false
#| warning: false
#| fig-width: 8

plot(x, y)
```
````

Each `#|` line is a YAML key-value pair. Values follow standard YAML rules:
- Booleans: `true`, `false` (lowercase)
- Numbers: `8`, `6.5`
- Strings: `"My caption"` or unquoted if no special characters

## Complete Option Reference

### Display Options

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `echo` | `true` | `true`, `false`, `fenced` | Show source code |
| `eval` | `true` | `true`, `false` | Execute the code |
| `output` | `true` | `true`, `false`, `asis` | Show code output |
| `warning` | `true` | `true`, `false` | Show warnings |
| `message` | `true` | `true`, `false` | Show messages |
| `include` | `true` | `true`, `false` | Include chunk entirely (overrides all) |
| `error` | `false` | `true`, `false` | Continue on error (show error in output) |

**`echo` details:**
- `true` -- show the code
- `false` -- hide the code, show only output
- `fenced` -- show the code including the chunk fence markers (useful for teaching)

**`output` details:**
- `true` -- show output normally
- `false` -- suppress all output
- `asis` -- treat output as raw Markdown (useful when generating Markdown from R)

**`include: false`** is a shortcut that suppresses everything -- the chunk runs silently. Commonly used for setup chunks:

````markdown
```{r}
#| label: setup
#| include: false

library(dplyr)
library(ggplot2)
```
````

### Labeling

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `label` | (auto) | string | Chunk identifier |

Labels serve three purposes:
1. Cross-referencing (`@fig-label`, `@tbl-label`)
2. Cache key identification
3. Debugging (error messages reference the label)

Label conventions:
- Use lowercase with hyphens: `load-data`, `fig-scatter`, `tbl-summary`
- Prefix with `fig-` for figure chunks (enables `@fig-` cross-refs)
- Prefix with `tbl-` for table chunks (enables `@tbl-` cross-refs)
- Must be unique within a document

### Figure Options

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `fig-cap` | (none) | string | Figure caption |
| `fig-subcap` | (none) | list | Subcaptions for multi-figure chunks |
| `fig-width` | `7` | number (inches) | Figure width |
| `fig-height` | `5` | number (inches) | Figure height |
| `fig-dpi` | `72` | number | Resolution in dots per inch |
| `fig-format` | (auto) | `png`, `svg`, `pdf` | Image format |
| `fig-align` | `default` | `left`, `center`, `right` | Alignment |
| `fig-alt` | (none) | string | Alt text for accessibility |
| `out-width` | (none) | CSS size | Display width (e.g., `"80%"`) |
| `out-height` | (none) | CSS size | Display height |

Example with figure options:

````markdown
```{r}
#| label: fig-enrollment
#| fig-cap: "Enrollment by state"
#| fig-width: 10
#| fig-height: 6
#| fig-dpi: 150
#| fig-alt: "Bar chart showing enrollment counts by state"

ggplot(df, aes(x = state, y = enrollment)) +
  geom_col() +
  theme_minimal()
```
````

### Table Options

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `tbl-cap` | (none) | string | Table caption |
| `tbl-subcap` | (none) | list | Subcaptions for multi-table chunks |
| `tbl-colwidths` | (auto) | list or `false` | Column width proportions |

Example:

````markdown
```{r}
#| label: tbl-stats
#| tbl-cap: "Summary statistics by group"

df |>
  group_by(category) |>
  summarize(mean = mean(value), sd = sd(value)) |>
  knitr::kable()
```
````

### Caching

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `cache` | `false` | `true`, `false` | Cache chunk results |
| `cache-vars` | (auto) | list | Variables to cache |
| `dependson` | (none) | list | Chunks this depends on |

Caching stores results so unchanged chunks skip re-execution:

````markdown
```{r}
#| label: expensive-model
#| cache: true

model <- lm(y ~ x1 + x2 + x3, data = large_df)
```
````

Cache pitfalls -- see `./gotchas.md` for details on when cache invalidation fails.

### Code Display

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `code-fold` | `false` | `true`, `false`, `show` | Foldable code (HTML only) |
| `code-summary` | `"Code"` | string | Label for fold toggle |
| `code-overflow` | `scroll` | `scroll`, `wrap` | Handle long lines |
| `code-line-numbers` | `false` | `true`, `false` | Show line numbers |

These can also be set globally in YAML frontmatter:

```yaml
---
format:
  html:
    code-fold: true
    code-summary: "Show code"
---
```

### Layout Options

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `layout-ncol` | (none) | number | Number of columns for output |
| `layout-nrow` | (none) | number | Number of rows for output |
| `layout` | (none) | list | Custom layout grid |
| `column` | `body` | `body`, `page`, `margin`, etc. | Output column placement |

Column placement example (HTML with page margins):

````markdown
```{r}
#| column: margin
#| fig-cap: "Marginal note figure"

plot(x, y)
```
````

## Global Chunk Options

Set default options for all chunks in YAML frontmatter:

```yaml
---
title: "My Document"
execute:
  echo: false
  warning: false
  message: false
---
```

All `execute:` options apply to every chunk. Individual chunks can override:

````markdown
```{r}
#| echo: true

# This chunk WILL show code despite the global echo: false
important_code()
```
````

### Common Global Configurations

**Analysis report (hide code, show results):**

```yaml
execute:
  echo: false
  warning: false
  message: false
```

**Teaching document (show everything):**

```yaml
execute:
  echo: true
  warning: true
```

**DAAF Stage 9 notebook (show code as audit trail):**

```yaml
execute:
  echo: true
  eval: false
```

Stage 9 notebooks set `eval: false` globally because they display already-executed
scripts -- the code is shown for review, not for re-execution.

## Non-R Code Chunks

Quarto supports other languages in the same document:

````markdown
```{python}
#| label: python-chunk
import pandas as pd
print("Hello from Python")
```

```{bash}
#| label: shell-chunk
echo "Hello from Bash"
```
````

In DAAF R pipelines, stick to R chunks exclusively.

## Chunk Execution Order

Chunks execute top-to-bottom in document order. Unlike marimo (reactive), Quarto
is sequential -- chunk order matters.

If chunk B depends on objects created in chunk A, chunk A must appear first:

````markdown
```{r}
#| label: define-data
df <- data.frame(x = 1:10, y = rnorm(10))
```

```{r}
#| label: use-data
# This works because define-data runs first
plot(df$x, df$y)
```
````

## Raw Output with `output: asis`

Generate Markdown from R code:

````markdown
```{r}
#| output: asis

for (group in unique(df$category)) {
  cat("###", group, "\n\n")
  sub <- df[df$category == group, ]
  cat("Count:", nrow(sub), "\n\n")
}
```
````

This produces actual Markdown headings and text in the output.

## Conditional Chunk Execution

Use `eval` with an R expression:

````markdown
```{r}
#| eval: !expr nrow(df) > 0

# Only runs if df has rows
summary(df)
```
````

The `!expr` prefix tells Quarto to evaluate the R expression to determine the boolean value.

## Summary: Most-Used Options

For quick reference, these are the options used in the majority of chunks:

| Scenario | Options |
|----------|---------|
| Setup chunk (hidden) | `#| include: false` |
| Code + output | (defaults, no options needed) |
| Output only | `#| echo: false` |
| Silent execution | `#| include: false` |
| Figure with caption | `#| label: fig-name` + `#| fig-cap: "..."` |
| Table with caption | `#| label: tbl-name` + `#| tbl-cap: "..."` |
| Suppress warnings | `#| warning: false` + `#| message: false` |
| Skip execution | `#| eval: false` |
