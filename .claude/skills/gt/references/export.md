# Table Export and Quarto Integration

Saving gt tables with gtsave(), kableExtra integration with Quarto documents,
inline tables in .qmd files, and output format comparison.

---

## gtsave() — Exporting gt Tables

### HTML Output (Default)

```r
tbl <- df |> gt() |> tab_header(title = "My Table")

# Save to HTML
gtsave(tbl, "output/tables/my_table.html")
```

HTML is the default and richest format. All gt features (colors, fonts, borders,
interactive hover) are preserved.

### PNG Output

```r
# Save to PNG (requires chromote or webshot2 package)
gtsave(tbl, "output/tables/my_table.png")

# With explicit dimensions
gtsave(tbl, "output/tables/my_table.png", vwidth = 800, vheight = 600)
```

PNG output renders the HTML table to an image. Useful for embedding in
presentations or documents that do not support HTML.

**Dependency:** PNG export requires a headless-browser backend — either
`chromote` or `webshot2` (both drive headless Chrome). Neither is pre-installed
in DAAF, and runtime installs are blocked (see CLAUDE.md § Runtime Package
Installation), so PNG export is unavailable out of the box. Prefer HTML or LaTeX
output; if PNG is genuinely required, escalate to the user to add `chromote` (or
`webshot2`) to the Dockerfile (user additions block) and rebuild before use.

### LaTeX Output

```r
# Save to .tex file
gtsave(tbl, "output/tables/my_table.tex")

# Or capture as string
latex_str <- as_latex(tbl)
```

In gt 1.3.0, LaTeX output produces a floating `\begin{table}` environment
containing a `tabular*`. A `longtable` environment (for tables that span pages)
is opt-in via `tab_options(latex.use_longtable = TRUE)`. Some gt features
(color gradients, complex borders) may not translate perfectly to LaTeX.

### Word/RTF Output

```r
gtsave(tbl, "output/tables/my_table.rtf")
gtsave(tbl, "output/tables/my_table.docx")
```

### Format Comparison

| Format | Rich Formatting | Colors | Spanners | Summary Rows | Best For |
|--------|----------------|--------|----------|-------------|----------|
| HTML | Full | Full | Yes | Yes | Web, reports, Quarto HTML |
| PNG | Full (rendered) | Full | Yes | Yes | Presentations, email |
| LaTeX | Partial | Partial | Yes | Yes | Journal submissions |
| RTF | Partial | Partial | Yes | Yes | Word documents |
| DOCX | Partial | Partial | Yes | Yes | Word documents |

## gt Tables in Quarto Documents

### Inline gt Output

In a Quarto `.qmd` document, gt tables render directly in code chunks:

````
```{r}
#| label: tbl-enrollment
#| tbl-cap: "Enrollment by State"

library(gt)

df |>
  gt() |>
  tab_header(title = "Enrollment Summary") |>
  fmt_integer(columns = enrollment) |>
  fmt_percent(columns = pct_frpl, decimals = 1)
```
````

The gt table renders as HTML in HTML output and as a table in both PDF paths,
LaTeX (`format: pdf`) and Typst (`format: typst`), with its title, formatted
values, "Table 1:" caption and resolved `@tbl-` cross-reference in each.

### Cross-Referencing gt Tables

```
See @tbl-enrollment for the enrollment summary.
```

The `#| label: tbl-` prefix enables Quarto cross-referencing. The `#| tbl-cap:`
option sets the caption visible in the rendered document.

## kableExtra in Quarto Documents

kableExtra is often preferred for simple tables in Quarto because of its lighter
weight and tight integration with knitr's rendering pipeline.

**Output format.** The `format = "html"` examples below are for HTML output
only, and `bootstrap_options`, `scroll_box()` and pixel widths are HTML
features. In a Quarto chunk, leave `format =` out of `kbl()` so knitr picks the
format of the output being rendered: a hard-coded `format = "html"` stops a
LaTeX PDF render (no PDF is written) with "Error: Functions that produce HTML
output found in document targeting pdf output." kableExtra does not work in a
Typst PDF (`format: typst`); use gt or `knitr::kable()` with no `format =`
there (the quarto skill's `references/tables.md` § Choosing a Table Method has
the details). For
the chunk label and caption form that numbers a
kableExtra table correctly in a LaTeX PDF, see the quarto skill's
`references/tables.md` § kableExtra in LaTeX PDF.

### Basic kableExtra Table

```r
library(kableExtra)

df |>
  kbl(
    format = "html",
    digits = 2,
    caption = "Summary Statistics",
    col.names = c("Variable", "Mean", "SD", "Min", "Max")
  ) |>
  kable_styling(
    bootstrap_options = c("striped", "hover", "condensed"),
    full_width = FALSE,
    position = "center"
  )
```

### kableExtra Styling Options

```r
df |>
  kbl(format = "html") |>
  kable_styling(
    bootstrap_options = c("striped", "hover", "condensed", "responsive"),
    full_width = FALSE
  ) |>
  row_spec(0, bold = TRUE, background = "#f0f0f0") |>   # Header row
  row_spec(which(df$value > 100), bold = TRUE) |>         # Conditional rows
  column_spec(1, width = "200px") |>                      # Column width
  column_spec(3, color = "red")                           # Column color
```

### Grouped Headers (Column Spanners)

```r
df |>
  kbl(format = "html") |>
  kable_styling() |>
  add_header_above(c(" " = 1, "Group A" = 2, "Group B" = 2))
```

### Grouped Rows

```r
df |>
  kbl(format = "html") |>
  kable_styling() |>
  pack_rows("Northeast", 1, 3) |>
  pack_rows("South", 4, 6)
```

### Scroll Box for Large Tables

```r
df |>
  kbl(format = "html") |>
  kable_styling() |>
  scroll_box(width = "100%", height = "400px")
```

### kableExtra in Quarto Chunks

No `format =` and no `caption =` in `kbl()`: the chunk options carry the label
and caption, and knitr picks HTML or LaTeX to match the output.

````
```{r}
#| label: tbl-summary
#| tbl-cap: "Descriptive Statistics"

library(kableExtra)

summary_df |>
  kbl(digits = 2, booktabs = TRUE) |>
  kable_styling()
```
````

Format-specific options can still go in `kable_styling()`:
`bootstrap_options` apply to HTML output, `latex_options` (for example
`c("striped", "hold_position")`) to a LaTeX PDF.

## kableExtra vs gt: When to Choose

| Scenario | Recommended | Rationale |
|----------|-------------|-----------|
| Simple summary table in Quarto | kableExtra (HTML or LaTeX PDF; for Typst PDF use gt or `knitr::kable()`) | Lighter, faster rendering |
| Complex formatting (color scales, conditional styling) | gt | More formatting power |
| Regression table | modelsummary (either backend) | Purpose-built |
| Journal-ready table | gt | Better LaTeX control |
| Quick exploratory table | kableExtra or `knitr::kable()` | Minimal setup |
| Table needs PNG export | gt | gtsave() handles it |

## modelsummary Export

modelsummary tables can also be saved directly:

```r
# Save via output argument
modelsummary(models, output = "results.html")
modelsummary(models, output = "results.tex")
modelsummary(models, output = "results.png")
modelsummary(models, output = "results.docx")

# Or get a gt object and use gtsave
tbl <- modelsummary(models, output = "gt")
gtsave(tbl, "results.html")
```

## DAAF Pipeline Convention

In DAAF research pipelines, table scripts follow the same file-first pattern as
all other scripts:

```r
# --- Config ---
library(gt)

PROJECT_DIR <- "/path/to/project"

# --- Load ---
df <- arrow::read_parquet(file.path(PROJECT_DIR, "data/processed/analysis_data.parquet"))

# --- Create Table ---
tbl <- df |>
  gt() |>
  tab_header(title = "Results Table") |>
  fmt_number(columns = where(is.numeric), decimals = 2)

# --- Save ---
gtsave(tbl, file.path(PROJECT_DIR, "output/tables/results_table.html"))
cat("Table saved to output/tables/results_table.html\n")

# --- Validate ---
stopifnot(file.exists(file.path(PROJECT_DIR, "output/tables/results_table.html")))
cat("PASS: Table file exists and is non-empty\n")
```
