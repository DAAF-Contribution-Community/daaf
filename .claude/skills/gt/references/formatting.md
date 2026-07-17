# gt Formatting and Structure

Detailed formatting with fmt_*() functions, conditional styling with tab_style(),
column spanners, row groups, summary rows, color scales, and cell merging.
gt 1.3.0.

---

## Number Formatting (fmt_*() Family)

### fmt_number — General Numeric

```r
tbl |>
  fmt_number(
    columns = c(value1, value2),
    decimals = 2,
    use_seps = TRUE,          # thousands separator
    sep_mark = ",",           # separator character
    dec_mark = "."            # decimal character
  )
```

### fmt_percent — Percentages

```r
# Input on 0-1 scale (0.452 -> 45.2%)
tbl |> fmt_percent(columns = rate, decimals = 1)

# Input on 0-100 scale -- use scale_values
tbl |> fmt_percent(columns = rate_100, decimals = 1, scale_values = FALSE)
```

### fmt_currency — Money Values

```r
tbl |> fmt_currency(columns = revenue, currency = "USD", decimals = 0)
tbl |> fmt_currency(columns = cost, currency = "EUR", decimals = 2)
```

### fmt_integer — Whole Numbers

```r
tbl |> fmt_integer(columns = count)
# Equivalent to fmt_number(decimals = 0)
```

### fmt_date — Dates

```r
tbl |> fmt_date(columns = date_col, date_style = "yMMMd")
# Common styles: "yMMMd" (Jan 15, 2023), "yMd" (1/15/2023),
#                "iso" (2023-01-15), "wd_MMMd" (Sun, Jan 15)
```

### sub_missing — NA Display

```r
tbl |> sub_missing(columns = everything(), missing_text = "---")
tbl |> sub_missing(columns = c(col1, col2), missing_text = "N/A")
```

`sub_missing()` replaced `fmt_missing()`, which is deprecated since gt 0.6.0
("Since gt v0.6.0 `fmt_missing()` is deprecated and will soon be removed. Use
`sub_missing()` instead."). Do not use `fmt_missing()` in new code.

### Applying to Specific Rows

All `fmt_*()` functions accept a `rows` argument:

```r
tbl |>
  fmt_percent(columns = rate, decimals = 1, rows = rate > 0) |>
  sub_missing(columns = rate, rows = is.na(rate))
```

### Custom Patterns

```r
# Suffix or prefix via pattern
tbl |> fmt_number(columns = change, decimals = 1, pattern = "+{x}")
tbl |> fmt_number(columns = value, decimals = 0, pattern = "{x} students")
```

## Conditional Formatting with tab_style()

### Basic Conditional Style

```r
tbl |>
  tab_style(
    style = cell_text(weight = "bold"),
    locations = cells_body(
      columns = state,
      rows = enrollment > 1000000
    )
  )
```

### Multiple Style Properties

```r
tbl |>
  tab_style(
    style = list(
      cell_text(color = "red", weight = "bold"),
      cell_fill(color = "#FFF3F3")
    ),
    locations = cells_body(
      columns = pct_change,
      rows = pct_change < 0
    )
  )
```

### Style Functions

| Function | Controls |
|----------|----------|
| `cell_text(color, size, weight, style, align, font)` | Text formatting |
| `cell_fill(color, alpha)` | Background color |
| `cell_borders(sides, color, weight, style)` | Cell borders |

### Location Functions for tab_style

| Function | Targets |
|----------|---------|
| `cells_body(columns, rows)` | Data cells |
| `cells_column_labels(columns)` | Column headers |
| `cells_title(groups)` | Title/subtitle |
| `cells_stub(rows)` | Row labels |
| `cells_row_groups(groups)` | Row group labels |
| `cells_summary(groups, columns, rows)` | Summary row cells |
| `cells_grand_summary(columns, rows)` | Grand summary cells |
| `cells_column_spanners(spanners)` | Spanner labels |

### Color Scales with data_color()

```r
# Continuous color scale on a column
tbl |>
  data_color(
    columns = enrollment,
    palette = "Blues"           # Any RColorBrewer or viridis palette
  )

# Custom color range
tbl |>
  data_color(
    columns = pct_change,
    palette = c("red", "white", "green"),
    domain = c(-0.1, 0, 0.1)   # Map colors to this range
  )

# Discrete color mapping
tbl |>
  data_color(
    columns = rating,
    palette = c("A" = "#2ECC71", "B" = "#F39C12", "C" = "#E74C3C")
  )
```

## Column Spanners

Column spanners group multiple columns under a shared header:

```r
tbl |>
  tab_spanner(
    label = "Enrollment",
    columns = c(enroll_male, enroll_female, enroll_total)
  ) |>
  tab_spanner(
    label = "Demographics",
    columns = c(pct_white, pct_black, pct_hispanic)
  )
```

### Nested Spanners

```r
tbl |>
  tab_spanner(
    label = "2022",
    columns = c(enroll_2022, pct_frpl_2022)
  ) |>
  tab_spanner(
    label = "2023",
    columns = c(enroll_2023, pct_frpl_2023)
  ) |>
  tab_spanner(
    label = "By Year",
    columns = c(enroll_2022, pct_frpl_2022, enroll_2023, pct_frpl_2023)
  )
```

## Row Groups

### From a Column

```r
# Group rows by a column value
tbl <- df |>
  gt(groupname_col = "region") |>
  tab_header(title = "Schools by Region")
```

### Manual Row Groups

```r
tbl <- df |>
  gt() |>
  tab_row_group(label = "High Enrollment", rows = enrollment > 500) |>
  tab_row_group(label = "Low Enrollment", rows = enrollment <= 500)
```

Row groups display in reverse order of creation (last created appears first).
Use `row_group_order()` to set explicit order:

```r
tbl |> row_group_order(groups = c("High Enrollment", "Low Enrollment"))
```

## Summary Rows

### Per-Group Summaries

```r
tbl |>
  summary_rows(
    groups = everything(),     # All groups (or specify group names)
    columns = c(enrollment, revenue),
    fns = list(
      Total = ~ sum(., na.rm = TRUE),
      Average = ~ mean(., na.rm = TRUE)
    ),
    fmt = ~ fmt_number(., decimals = 0)
  )
```

### Grand Summary (Bottom of Table)

```r
tbl |>
  grand_summary_rows(
    columns = c(enrollment, revenue),
    fns = list(
      "Grand Total" = ~ sum(., na.rm = TRUE),
      "Overall Mean" = ~ mean(., na.rm = TRUE)
    ),
    fmt = ~ fmt_number(., decimals = 0)
  )
```

## Column Width

```r
tbl |>
  cols_width(
    state_name ~ px(200),
    enrollment ~ px(120),
    starts_with("pct_") ~ px(100),
    everything() ~ px(80)
  )
```

## Merging Cells

### Merge Duplicate Values

```r
# Merge identical adjacent values in a column (useful for grouped displays)
tbl |> cols_merge_range(col_begin = lower, col_end = upper, sep = " -- ")
```

### Merge Columns

```r
# Combine first + last name into one column
tbl |>
  cols_merge(
    columns = c(first_name, last_name),
    pattern = "{1} {2}"
  )
```

## Table Options

```r
tbl |>
  opt_row_striping() |>                     # Zebra stripes
  opt_table_outline(color = "grey80") |>    # Table border
  opt_horizontal_padding(scale = 2) |>      # Wider cells
  opt_vertical_padding(scale = 0.5)         # Tighter rows
```

## Complete Example: Formatted Summary Table

```r
library(gt)

summary_df <- data.frame(
  region = c("Northeast", "Northeast", "South", "South", "West", "West"),
  state = c("NY", "MA", "TX", "FL", "CA", "WA"),
  enrollment = c(2599436, 965382, 5493940, 2892064, 5903155, 1139840),
  pct_frpl = c(0.541, 0.378, 0.609, 0.567, 0.592, 0.425),
  change = c(-0.023, 0.011, 0.034, 0.019, -0.008, 0.042)
)

tbl <- summary_df |>
  gt(groupname_col = "region") |>
  tab_header(
    title = "K-12 Enrollment by State",
    subtitle = "Selected states, 2022-23"
  ) |>
  cols_label(
    state = "State",
    enrollment = "Enrollment",
    pct_frpl = "% FRPL",
    change = "YoY Change"
  ) |>
  fmt_integer(columns = enrollment) |>
  fmt_percent(columns = pct_frpl, decimals = 1) |>
  fmt_percent(columns = change, decimals = 1, force_sign = TRUE) |>
  tab_style(
    style = cell_text(color = "red"),
    locations = cells_body(columns = change, rows = change < 0)
  ) |>
  tab_style(
    style = cell_text(color = "green"),
    locations = cells_body(columns = change, rows = change > 0)
  ) |>
  summary_rows(
    groups = everything(),
    columns = enrollment,
    fns = list(Subtotal = ~ sum(.)),
    fmt = ~ fmt_integer(.)
  ) |>
  grand_summary_rows(
    columns = enrollment,
    fns = list(Total = ~ sum(.)),
    fmt = ~ fmt_integer(.)
  ) |>
  tab_source_note("Source: NCES CCD.") |>
  opt_row_striping()
```
