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

**Dependency:** PNG export requires the `chromote` package (headless Chrome).
If not available, install with `install.packages("chromote")`.

### LaTeX Output

```r
# Save to .tex file
gtsave(tbl, "output/tables/my_table.tex")

# Or capture as string
latex_str <- as_latex(tbl)
```

LaTeX output produces a `\begin{longtable}` environment. Some gt features
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

The gt table renders as HTML in HTML output and as LaTeX in PDF output.

### Cross-Referencing gt Tables

```
See @tbl-enrollment for the enrollment summary.
```

The `#| label: tbl-` prefix enables Quarto cross-referencing. The `#| tbl-cap:`
option sets the caption visible in the rendered document.

## kableExtra in Quarto Documents

kableExtra is often preferred for simple tables in Quarto because of its lighter
weight and tight integration with knitr's rendering pipeline.

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

````
```{r}
#| label: tbl-summary
#| tbl-cap: "Descriptive Statistics"

library(kableExtra)

summary_df |>
  kbl(format = "html", digits = 2) |>
  kable_styling(bootstrap_options = c("striped", "condensed"))
```
````

## kableExtra vs gt: When to Choose

| Scenario | Recommended | Rationale |
|----------|-------------|-----------|
| Simple summary table in Quarto | kableExtra | Lighter, faster rendering |
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
