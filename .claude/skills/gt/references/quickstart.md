# gt Quickstart

Basic table creation with gt(), adding structural elements (headers, footers,
source notes, footnotes), simple formatting, and column labeling. gt 1.3.0.

---

## Creating a gt Table

```r
library(gt)

# From a data frame
tbl <- df |> gt()

# With row names as a column
tbl <- mtcars |>
  tibble::rownames_to_column("car") |>
  head(10) |>
  gt()
```

gt takes a data frame and returns a `gt_tbl` object. All subsequent operations
chain with `|>`.

## Table Header and Footer

```r
tbl <- df |>
  gt() |>
  tab_header(
    title = "Enrollment by State",
    subtitle = "Public K-12 schools, 2022-23"
  ) |>
  tab_source_note("Source: NCES Common Core of Data (CCD).") |>
  tab_source_note("Note: Enrollment counts exclude pre-K.")
```

- `tab_header()`: Title and optional subtitle at the top
- `tab_source_note()`: Source/note lines at the bottom (call multiple times for
  multiple notes)
- Multiple source notes appear in the order they are added

## Footnotes

```r
tbl <- df |>
  gt() |>
  tab_footnote(
    footnote = "Includes charter schools.",
    locations = cells_column_labels(columns = enrollment)
  ) |>
  tab_footnote(
    footnote = "Poverty rate estimated from SAIPE.",
    locations = cells_body(columns = poverty_rate, rows = 1)
  )
```

`locations` specifies where the footnote mark appears:
- `cells_column_labels(columns)` -- on a column header
- `cells_body(columns, rows)` -- on a specific cell
- `cells_title(groups = "title")` -- on the title
- `cells_stub(rows)` -- on row labels

## Column Labels

By default, gt uses column names as labels. Rename them for readability:

```r
tbl <- df |>
  gt() |>
  cols_label(
    state_name = "State",
    total_enrollment = "Total Enrollment",
    pct_frpl = "% FRPL",
    n_schools = "Schools"
  )
```

Use `md()` or `html()` for formatted labels:

```r
cols_label(
  pct_frpl = md("% **FRPL**"),
  n_schools = html("Schools<br><small>(count)</small>")
)
```

## Simple Number Formatting

```r
tbl <- df |>
  gt() |>
  fmt_number(
    columns = total_enrollment,
    decimals = 0,
    use_seps = TRUE           # thousands separator (default TRUE)
  ) |>
  fmt_percent(
    columns = pct_frpl,
    decimals = 1
  ) |>
  fmt_currency(
    columns = revenue_per_pupil,
    currency = "USD",
    decimals = 0
  )
```

Common `fmt_*()` functions:

| Function | Formats | Example Output |
|----------|---------|----------------|
| `fmt_number()` | General numeric | 1,234.56 |
| `fmt_integer()` | Integers | 1,235 |
| `fmt_percent()` | Percentages (input 0-1 scale) | 45.2% |
| `fmt_currency()` | Currency | $1,235 |
| `fmt_date()` | Dates | Jan 15, 2023 |
| `fmt_missing()` | NA values | -- |

For `fmt_percent()`, the input values should be on the 0-1 scale (e.g., 0.452
displays as 45.2%). If your data is already on the 0-100 scale, use
`fmt_number(columns, decimals = 1, pattern = "{x}%")` instead.

## Hiding Columns

```r
tbl <- df |>
  gt() |>
  cols_hide(columns = c(state_fips, internal_id))
```

Hides columns from display while keeping them available for calculations
(e.g., summary rows can still reference hidden columns).

## Column Alignment

```r
tbl <- df |>
  gt() |>
  cols_align(align = "center", columns = everything()) |>
  cols_align(align = "left", columns = state_name) |>
  cols_align(align = "right", columns = where(is.numeric))
```

## Column Reordering

```r
tbl <- df |>
  gt() |>
  cols_move_to_start(columns = state_name) |>
  cols_move(columns = pct_frpl, after = total_enrollment)
```

## Complete Example

```r
library(gt)

# --- Example: State enrollment summary ---
summary_df <- data.frame(
  state = c("California", "Texas", "New York"),
  enrollment = c(5903155, 5493940, 2599436),
  pct_frpl = c(0.592, 0.609, 0.541),
  schools = c(10627, 9138, 4796)
)

tbl <- summary_df |>
  gt() |>
  tab_header(
    title = "K-12 Public School Enrollment",
    subtitle = "Top 3 states by enrollment, 2022-23"
  ) |>
  cols_label(
    state = "State",
    enrollment = "Total Enrollment",
    pct_frpl = "% FRPL",
    schools = "Schools"
  ) |>
  fmt_number(columns = enrollment, decimals = 0) |>
  fmt_percent(columns = pct_frpl, decimals = 1) |>
  fmt_integer(columns = schools) |>
  tab_source_note("Source: NCES Common Core of Data (CCD).") |>
  tab_footnote(
    footnote = "Free or Reduced-Price Lunch eligibility.",
    locations = cells_column_labels(columns = pct_frpl)
  )

# Save to HTML
gtsave(tbl, "enrollment_summary.html")
```

## gt vs kableExtra vs modelsummary: When to Use What

| Scenario | Recommended |
|----------|-------------|
| Rich data table with formatting, colors, spanners | gt |
| Simple table in a Quarto .qmd document | kableExtra `kbl()` |
| Regression coefficients, multiple models | modelsummary |
| Quick console preview | `knitr::kable()` or `print()` |
| Table needs LaTeX output for journal | gt `gtsave()` or modelsummary `output = "latex"` |
