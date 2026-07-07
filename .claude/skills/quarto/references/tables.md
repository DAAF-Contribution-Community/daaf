# Tables

## Table Output Methods

Three approaches for tables in Quarto documents, from simplest to most powerful:

| Method | Package | Best For |
|--------|---------|----------|
| `knitr::kable()` | knitr (built-in) | Simple tables, quick output |
| `kableExtra` | kableExtra | Styled tables with formatting |
| `gt::gt()` | gt | Publication-quality tables |

## knitr::kable()

The simplest table output. No additional packages needed:

````markdown
```{r}
#| label: tbl-basic
#| tbl-cap: "Summary of enrollment data"

df |>
  head(10) |>
  knitr::kable()
```
````

### kable Options

```r
knitr::kable(
  df,
  digits = 2,           # Decimal places
  col.names = c("Year", "Count", "Mean"),  # Column headers
  align = c("l", "r", "r"),               # l=left, c=center, r=right
  format.args = list(big.mark = ",")       # Thousands separator
)
```

| Argument | Purpose | Example |
|----------|---------|---------|
| `digits` | Decimal places | `2` |
| `col.names` | Custom column names | `c("A", "B")` |
| `align` | Column alignment | `c("l", "r")` |
| `caption` | Table caption (prefer `tbl-cap` chunk option) | `"My table"` |
| `format.args` | Formatting options | `list(big.mark = ",")` |

### kable with Pipe

```r
df |>
  group_by(year) |>
  summarize(
    n = n(),
    mean_value = mean(value, na.rm = TRUE)
  ) |>
  knitr::kable(digits = 1, col.names = c("Year", "N", "Mean"))
```

## kableExtra

Enhanced styling on top of kable. Load the package:

```r
library(kableExtra)
```

### Basic Styled Table

```r
df |>
  knitr::kable() |>
  kable_styling(
    bootstrap_options = c("striped", "hover", "condensed"),
    full_width = FALSE,
    position = "center"
  )
```

### Bootstrap Options (HTML)

| Option | Effect |
|--------|--------|
| `"striped"` | Alternating row colors |
| `"hover"` | Highlight on mouse hover |
| `"condensed"` | Reduced padding |
| `"bordered"` | Cell borders |
| `"responsive"` | Horizontal scroll on overflow |

### Column Formatting

```r
df |>
  knitr::kable() |>
  kable_styling() |>
  column_spec(1, bold = TRUE) |>
  column_spec(3, color = "red", width = "3cm")
```

### Row Formatting

```r
df |>
  knitr::kable() |>
  kable_styling() |>
  row_spec(0, bold = TRUE, color = "white", background = "#4472C4") |>
  row_spec(c(3, 5), background = "#FFFFCC")
```

Row 0 is the header row.

### Grouped Rows

```r
df |>
  knitr::kable() |>
  kable_styling() |>
  pack_rows("Group A", 1, 3) |>
  pack_rows("Group B", 4, 6)
```

### Footnotes

```r
df |>
  knitr::kable() |>
  kable_styling() |>
  footnote(
    general = "Source: CCD 2022",
    number = c("Enrollment in thousands", "Missing data excluded")
  )
```

## gt Tables

The gt package produces publication-quality tables with a grammar-of-tables
approach. Most powerful but most verbose:

```r
library(gt)
```

### Basic gt Table

````markdown
```{r}
#| label: tbl-gt-basic
#| tbl-cap: "Enrollment by state"

df |>
  group_by(state) |>
  summarize(
    schools = n(),
    total_enrollment = sum(enrollment)
  ) |>
  gt()
```
````

### Formatted gt Table

```r
df |>
  gt() |>
  tab_header(
    title = "School Enrollment Summary",
    subtitle = "Academic Year 2023-24"
  ) |>
  fmt_number(
    columns = enrollment,
    decimals = 0,
    use_seps = TRUE
  ) |>
  fmt_percent(
    columns = pct_change,
    decimals = 1
  ) |>
  cols_label(
    state = "State",
    enrollment = "Total Enrollment",
    pct_change = "% Change"
  )
```

### gt Formatting Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `fmt_number()` | Number formatting | Thousands separators, decimals |
| `fmt_percent()` | Percentage formatting | 0.15 -> 15.0% |
| `fmt_currency()` | Currency formatting | 1234 -> $1,234 |
| `fmt_date()` | Date formatting | ISO to readable |
| `fmt_missing()` | Missing value display | NA -> "---" |

### gt Styling

```r
df |>
  gt() |>
  tab_style(
    style = cell_fill(color = "#F0F0F0"),
    locations = cells_body(rows = seq(1, nrow(df), 2))
  ) |>
  tab_style(
    style = cell_text(weight = "bold"),
    locations = cells_column_labels()
  )
```

### gt Source Notes

```r
df |>
  gt() |>
  tab_source_note("Source: Common Core of Data, 2022") |>
  tab_source_note("Note: Enrollment figures rounded to nearest hundred")
```

### gt Spanners (Column Groups)

```r
df |>
  gt() |>
  tab_spanner(
    label = "Demographics",
    columns = c(white, black, hispanic)
  ) |>
  tab_spanner(
    label = "Outcomes",
    columns = c(grad_rate, dropout_rate)
  )
```

## Cross-Referencing Tables

To create a cross-referenceable table:
1. Use a `tbl-` prefixed label
2. Add a `tbl-cap`
3. Reference with `@tbl-label`

````markdown
```{r}
#| label: tbl-demographics
#| tbl-cap: "School demographics by district type"

df |>
  group_by(district_type) |>
  summarize(across(white:hispanic, mean)) |>
  knitr::kable(digits = 1)
```

As shown in @tbl-demographics, urban districts have higher diversity.
````

Requirements:
- Label MUST start with `tbl-`
- Caption (`tbl-cap`) MUST be present
- Reference uses `@` prefix

The reference renders as "Table 1" (or appropriate number).

## Multiple Tables

### Side-by-Side Tables

````markdown
```{r}
#| label: tbl-comparison
#| tbl-cap: "Comparison tables"
#| tbl-subcap:
#|   - "Public schools"
#|   - "Private schools"
#| layout-ncol: 2

public_df |> head(5) |> knitr::kable()
private_df |> head(5) |> knitr::kable()
```
````

### Panel Tables (gt)

gt supports grouped/panel layouts natively:

```r
df |>
  gt(groupname_col = "category") |>
  tab_header(title = "Results by Category")
```

## Choosing a Table Method

| Need | Use |
|------|-----|
| Quick data display | `knitr::kable()` |
| Styled HTML tables | `kableExtra` |
| Publication-quality | `gt` |
| PDF output | `knitr::kable()` or `gt` (kableExtra has PDF limitations) |
| Cross-referenced | Any method + `tbl-` label + `tbl-cap` |

For DAAF Stage 9 notebooks, `knitr::kable()` is sufficient -- the notebook
displays data for inspection, not for publication formatting.

## Tips

1. **Always use `tbl-cap`** for any table you want to cross-reference
2. **Use `tbl-` prefix on labels** -- cross-references require it
3. **Keep tables simple** in Stage 9 notebooks -- `head(df) |> kable()` is enough
4. **Use gt for reports** -- its formatting capabilities justify the verbosity
5. **Test PDF output** if targeting PDF -- some kableExtra features are HTML-only
6. **Format numbers consistently** -- use `digits` in kable or `fmt_number` in gt
