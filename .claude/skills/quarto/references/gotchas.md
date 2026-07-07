# Gotchas & Common Pitfalls

## Chunk Option Syntax

### The #1 Mistake: Wrong Chunk Option Syntax

Quarto uses `#|` (hash-pipe) syntax. The legacy R Markdown `{r, ...}` header
syntax still works but should not be used in Quarto documents.

````markdown
# WRONG -- legacy R Markdown syntax
```{r, echo=FALSE, fig.width=8}
plot(x, y)
```

# CORRECT -- Quarto hash-pipe syntax
```{r}
#| echo: false
#| fig-width: 8

plot(x, y)
```
````

Key differences:

| Legacy (R Markdown) | Quarto (#|) | Notes |
|---------------------|-------------|-------|
| `echo=FALSE` | `echo: false` | YAML boolean, not R boolean |
| `fig.width=8` | `fig-width: 8` | Hyphens, not dots |
| `fig.cap="text"` | `fig-cap: "text"` | Hyphens, not dots |
| `message=FALSE` | `message: false` | Lowercase `false`, not `FALSE` |
| `results='asis'` | `output: asis` | Different key name |
| `cache=TRUE` | `cache: true` | Lowercase `true`, not `TRUE` |

### Dots vs Hyphens

All chunk options use **hyphens** in Quarto, not dots:

| Wrong | Correct |
|-------|---------|
| `fig.width` | `fig-width` |
| `fig.height` | `fig-height` |
| `fig.cap` | `fig-cap` |
| `fig.align` | `fig-align` |
| `tbl.cap` | `tbl-cap` |
| `out.width` | `out-width` |

### Boolean Values

Use YAML booleans (`true`/`false`), not R booleans (`TRUE`/`FALSE`):

```yaml
#| echo: false      # Correct
#| echo: FALSE      # Wrong (treated as string "FALSE")
#| eval: true       # Correct
#| eval: TRUE       # Wrong
```

### Spacing After #|

A space after `#|` is required:

```yaml
#| echo: false      # Correct
#|echo: false       # Wrong -- no space after pipe
```

## YAML Frontmatter Errors

### Indentation

YAML is indentation-sensitive. Use spaces (not tabs), consistently:

```yaml
# CORRECT
format:
  html:
    toc: true
    theme: cosmo

# WRONG -- inconsistent indentation
format:
  html:
    toc: true
   theme: cosmo     # Only 3 spaces instead of 4

# WRONG -- tabs instead of spaces
format:
	html:             # Tab character
		toc: true       # Tab character
```

### Colons in Values

Values containing colons need quoting:

```yaml
# WRONG
title: Analysis: A Study

# CORRECT
title: "Analysis: A Study"
```

### Multi-line Strings

```yaml
# Folded (newlines become spaces)
description: >
  This is a long description
  that wraps across lines.

# Literal (newlines preserved)
abstract: |
  Line one.
  Line two.
  Line three.
```

### Missing Document Separator

The YAML block MUST start and end with `---`:

```yaml
---
title: "My Doc"
format: html
---
```

If the closing `---` is missing, the entire document is treated as YAML.

## Figure Path Issues

### Relative vs Absolute Paths

R code in .qmd executes in the directory containing the .qmd file. Paths
must be relative to that location:

```r
# If .qmd is in project root:
df <- arrow::read_parquet("data/raw/schools.parquet")  # Correct

# If .qmd is in a subdirectory:
df <- arrow::read_parquet("../data/raw/schools.parquet")  # Relative to .qmd
```

### The _files Directory

Rendered figures go to `document_files/figure-html/`:

```
analysis.qmd
analysis.html
analysis_files/
  figure-html/
    fig-scatter-1.png
```

This directory is auto-managed by Quarto. Do not manually add files to it.

With `embed-resources: true`, no `_files` directory is created.

### ggsave and Chunk Figures

If you use `ggsave()` AND display the plot, you get two copies:

```r
# Creates BOTH a saved file AND a chunk figure
p <- ggplot(df, aes(x, y)) + geom_point()
ggsave("output/plot.png", p)
p  # This also creates a figure in _files/
```

In Stage 9 notebooks this is not an issue because `eval: false` prevents
execution.

## knitr Cache Pitfalls

### When Cache Breaks

The knitr cache invalidates when the chunk code changes. But it does NOT
detect:

| Change | Cache Detects? | Risk |
|--------|---------------|------|
| Code in the chunk | Yes | None |
| External data file changes | No | Stale results |
| Changes in sourced files | No | Stale results |
| Package updates | No | Stale results |
| Changes in other chunks | Partially | May miss indirect deps |

### Fixing Stale Cache

```bash
# Delete cache directory
rm -r document_cache/

# Or force refresh on render
quarto render doc.qmd --cache-refresh
```

### Safe Cache Usage

```yaml
#| cache: true
#| dependson: "load-data"  # Invalidate when load-data chunk changes
```

Use `dependson` to explicitly declare inter-chunk dependencies.

For DAAF Stage 9 notebooks, caching is irrelevant because `eval: false`.

## PDF Rendering Issues

### No LaTeX Installed

```
Error: LaTeX failed to compile document.pdf
```

Fix:

```bash
quarto install tinytex
```

Or use Typst instead (bundled with Quarto, no installation needed):

```yaml
format: typst
```

### Missing LaTeX Packages

TinyTeX auto-installs missing packages on first render. If this fails:

```bash
# Manual install
quarto install tinytex --update-path
```

### Unicode Characters in PDF

LaTeX may fail on Unicode characters. Fix with XeLaTeX:

```yaml
format:
  pdf:
    pdf-engine: xelatex
```

### Long Tables Overflowing

Tables wider than the page in PDF:

```r
knitr::kable(df) |>
  kableExtra::kable_styling(latex_options = "scale_down")
```

## Cross-Reference Issues

### Cross-References Not Rendering

Common causes:

1. **Label missing `fig-` or `tbl-` prefix:**
```yaml
#| label: scatter          # Won't cross-reference
#| label: fig-scatter      # Will cross-reference
```

2. **Caption missing:**
```yaml
#| label: fig-scatter
# No fig-cap -- cross-reference won't work
```

3. **Wrong reference syntax:**
```markdown
See Figure @fig-scatter    # Wrong -- "Figure" is redundant
See @fig-scatter           # Correct -- Quarto adds "Figure"
```

Quarto automatically adds "Figure" or "Table" prefix to cross-references.
Writing `Figure @fig-scatter` produces "Figure Figure 1".

### Duplicate Labels

Each label must be unique within a document:

````markdown
```{r}
#| label: fig-plot
# First occurrence -- OK
```

```{r}
#| label: fig-plot
# ERROR -- duplicate label
```
````

## Inline R Expression Issues

### Expression Too Complex

Inline expressions must be single expressions:

```markdown
The count is `r nrow(df)`.                    # OK
The count is `r x <- nrow(df); x`.            # WRONG -- multiple expressions
The count is `r format(nrow(df), big.mark=",")`  # OK -- single nested call
```

### Missing Backtick

Inline code needs proper backtick delimiters:

```markdown
The count is `r nrow(df)`.    # Correct
The count is `r nrow(df).     # Wrong -- missing closing backtick
```

### NULL Output

If the expression returns NULL, nothing is printed:

```markdown
The result is `r invisible(42)`.  # Prints nothing!
The result is `r 42`.             # Prints "42"
```

## Common Quarto vs R Markdown Differences

If you have R Markdown experience, watch for these:

| R Markdown | Quarto | Notes |
|-----------|--------|-------|
| `output: html_document` | `format: html` | Different key names |
| `rmarkdown::render()` | `quarto render` CLI | Different rendering path |
| `setup` chunk with `knitr::opts_chunk$set()` | `execute:` in YAML | Global options location |
| `{r chunk-name, ...}` | `{r}` + `#| label: name` | Option location |
| `.Rmd` extension | `.qmd` extension | File format |
| `fig.width` | `fig-width` | Dots to hyphens |
| `results = 'asis'` | `output: asis` | Different option name |

## Rendering Fails Silently

If `quarto render` exits without error but output looks wrong:

1. **Check `--log`:** `quarto render doc.qmd --log render.log`
2. **Check warnings:** Render with `warning: true` on all chunks
3. **Check eval:** Verify `eval` is set correctly (true for execution, false for display)
4. **Check format:** Ensure YAML format matches `--to` flag

## Environment Issues

### Library Not Found

```
Error in library(ggplot2) : there is no package called 'ggplot2'
```

Quarto uses the R installation found by `quarto check knitr`. Ensure
packages are installed in the correct library path:

```bash
quarto check knitr
# Shows: LibPaths and installed packages
```

### Wrong R Version

```bash
quarto check knitr
# Shows: Version and Path
```

If Quarto uses the wrong R, set `QUARTO_R` environment variable:

```bash
export QUARTO_R=/opt/R/4.5.3/bin/R
quarto render doc.qmd
```

## Summary Checklist

| Issue | Fix |
|-------|-----|
| Chunk options not working | Use `#|` syntax with hyphens, not dots |
| YAML parse error | Check indentation (spaces, not tabs) |
| Cross-ref not linking | Add `fig-`/`tbl-` prefix AND caption |
| PDF won't render | `quarto install tinytex` or use `format: typst` |
| Cache stale | Delete `_cache/` or `--cache-refresh` |
| Wrong R version | Check `quarto check knitr` |
| Figures missing | Check paths relative to .qmd location |
| "Figure Figure 1" | Remove manual prefix -- `@fig-x` adds it |
