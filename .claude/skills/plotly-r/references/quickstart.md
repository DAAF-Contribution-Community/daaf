# Quickstart

## Essential Setup

```r
library(plotly)
library(htmlwidgets)  # For saveWidget()
```

## The Formula Interface

plotly R uses the **formula interface** to reference data columns. Prefix column
names with `~` (tilde):

```r
# R plotly -- formula interface
plot_ly(df, x = ~column_x, y = ~column_y)

# NOT bare names (ggplot2 style)
# plot_ly(df, x = column_x, y = column_y)  # Error

# NOT strings (Python plotly style)
# plot_ly(df, x = "column_x", y = "column_y")  # Creates literal text, not data mapping
```

The tilde tells plotly to evaluate the expression in the context of the data
frame. This also supports inline transformations:

```r
plot_ly(df, x = ~log(value), y = ~rate * 100)
plot_ly(df, x = ~factor(year), y = ~enrollment)
```

## Basic plot_ly() Pattern

Every plot_ly() call follows this structure:

```r
p <- plot_ly(
  data = df,           # Data frame
  x = ~col_x,          # X variable (formula)
  y = ~col_y,          # Y variable (formula)
  type = "scatter",    # Trace type
  mode = "markers"     # Mode (for scatter: "markers", "lines", "lines+markers")
)
```

### Minimal Example

```r
p <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers")
p  # Display
```

### With Color and Size

```r
p <- plot_ly(
  mtcars,
  x = ~wt,
  y = ~mpg,
  color = ~factor(cyl),     # Color by category
  size = ~hp,               # Size by value
  type = "scatter",
  mode = "markers"
)
```

### Color Semantics

| Argument | Purpose | Example |
|----------|---------|---------|
| `color = ~col` | Map to data column (automatic palette) | `color = ~factor(cyl)` |
| `colors = "Set1"` | Choose palette for mapped color | `colors = viridisLite::viridis(256)` |
| `marker = list(color = "red")` | Fixed color for all points | Single color |

```r
# Mapped color (discrete)
plot_ly(df, x = ~x, y = ~y, color = ~group, type = "scatter", mode = "markers")

# Mapped color (continuous) -- colors takes RColorBrewer names, color vectors,
# or interpolation functions. "Viridis" is NOT a brewer name and errors here;
# use a viridisLite color vector instead.
plot_ly(df, x = ~x, y = ~y, color = ~value, colors = viridisLite::viridis(256),
        type = "scatter", mode = "markers")

# Fixed color
plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers",
        marker = list(color = "steelblue", size = 8))
```

## add_trace()

Add additional traces (series) to an existing plot:

```r
p <- plot_ly(df, x = ~date) |>
  add_trace(y = ~series_a, name = "Series A", type = "scatter", mode = "lines") |>
  add_trace(y = ~series_b, name = "Series B", type = "scatter", mode = "lines")
```

### Convenience Wrappers

plotly provides shorthand functions that set type and mode automatically:

| Function | Equivalent |
|----------|------------|
| `add_markers()` | `add_trace(type = "scatter", mode = "markers")` |
| `add_lines()` | `add_trace(type = "scatter", mode = "lines")` |
| `add_bars()` | `add_trace(type = "bar")` |
| `add_histogram()` | `add_trace(type = "histogram")` |
| `add_boxplot()` | `add_trace(type = "box")` |
| `add_heatmap()` | `add_trace(type = "heatmap")` |
| `add_surface()` | `add_trace(type = "surface")` |

```r
p <- plot_ly(df, x = ~date) |>
  add_lines(y = ~value, name = "Trend") |>
  add_markers(y = ~value, name = "Points")
```

## Piping with |>

All plotly functions return the plot object, so R's native pipe works naturally:

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  layout(
    title = "My Plot",
    xaxis = list(title = "X Axis"),
    yaxis = list(title = "Y Axis")
  ) |>
  config(displayModeBar = FALSE)
```

Chaining order is flexible -- layout(), add_trace(), and config() can appear in
any order.

## Saving with htmlwidgets

```r
library(htmlwidgets)

# HTML export (loads plotly.js from CDN -- default for DAAF)
saveWidget(p, "plot.html", selfcontained = FALSE)

# Self-contained HTML (embeds plotly.js, ~3MB -- requires pandoc)
# saveWidget(p, "plot.html", selfcontained = TRUE)  # NOT available in DAAF
```

> **DAAF note:** `selfcontained = TRUE` requires pandoc, which is not installed
> in the DAAF container. Always use `selfcontained = FALSE`. The output HTML
> loads plotly.js from a CDN, so an internet connection is needed to view it.

### DAAF Research Workflow Pattern

```r
# --- Config ---
library(plotly)
library(htmlwidgets)
PROJECT_DIR <- "/daaf/research/YYYY-MM-DD_Project_Name"
OUTPUT_DIR <- file.path(PROJECT_DIR, "output")

# --- Transform / Analyze ---
p <- plot_ly(df, x = ~year, y = ~enrollment, type = "scatter", mode = "lines") |>
  layout(title = "Enrollment Trends", xaxis = list(title = "Year"))

# --- Save ---
saveWidget(
  p,
  file.path(OUTPUT_DIR, "YYYY-MM-DD_enrollment_trends.html"),
  selfcontained = FALSE
)
cat("Plot saved successfully\n")
```

### Saving to Temp Files (Tests)

```r
tmp <- tempfile(fileext = ".html")
saveWidget(p, tmp, selfcontained = FALSE)
stopifnot(file.exists(tmp))
file.remove(tmp)
```

## Built-in Data

plotly does not bundle its own datasets like Python's Plotly Express. Use R's
built-in datasets:

```r
mtcars      # Motor Trend car data
iris        # Fisher's iris data
airquality  # NY air quality
economics   # US economic time series (from ggplot2)
```

## Data Requirements

plot_ly() works with:
- **data.frame** (base R)
- **tibble** (tidyverse)
- **data.table** (automatically handled)

Arrow tables should be converted to data.frame first via `as.data.frame()`.

## Quick Comparison: R plotly vs Python plotly

| Feature | R (plotly) | Python (plotly) |
|---------|-----------|-----------------|
| Column reference | Formula: `~col` | String: `"col"` |
| High-level API | `plot_ly()` | `px.scatter()` etc. |
| Low-level API | `plot_ly(type=...)` | `go.Figure(go.Scatter(...))` |
| Add traces | `add_trace()` / `add_lines()` | `fig.add_trace()` |
| Layout | `layout(title = ...)` | `fig.update_layout(title=...)` |
| Chaining | Native pipe `\|>` | Method chaining `.update_*()` |
| Export HTML | `saveWidget()` | `fig.write_html()` |
| Static export | `orca()` / `kaleido()` | `fig.write_image()` |
