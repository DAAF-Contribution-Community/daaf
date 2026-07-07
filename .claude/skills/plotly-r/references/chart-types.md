# Chart Types

## Scatter Plots

### Basic Scatter

```r
p <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers")
```

### With Color and Size

```r
p <- plot_ly(
  mtcars,
  x = ~wt,
  y = ~mpg,
  color = ~factor(cyl),
  size = ~hp,
  type = "scatter",
  mode = "markers",
  text = ~paste("Car:", rownames(mtcars))  # Custom hover text
)
```

### Marker Customization

```r
p <- plot_ly(
  df, x = ~x, y = ~y, type = "scatter", mode = "markers",
  marker = list(
    size = 10,
    color = "steelblue",
    line = list(color = "black", width = 1),  # Marker border
    opacity = 0.7
  )
)
```

### Common Scatter Options

| Argument | Purpose |
|----------|---------|
| `color = ~col` | Color by data column |
| `colors = "Set1"` | Color palette name |
| `size = ~col` | Size by data column |
| `sizes = c(5, 30)` | Min/max bubble size |
| `symbol = ~col` | Shape by data column |
| `text = ~col` | Hover text |
| `hoverinfo = "text"` | Show only custom text |

---

## Line Charts

### Basic Line

```r
p <- plot_ly(economics, x = ~date, y = ~unemploy,
             type = "scatter", mode = "lines")
```

### Multiple Lines

```r
p <- plot_ly(df, x = ~date) |>
  add_lines(y = ~series_a, name = "Series A") |>
  add_lines(y = ~series_b, name = "Series B")
```

### Line Styles

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "lines",
             line = list(
               color = "red",
               width = 2,
               dash = "dash"  # "solid", "dot", "dash", "longdash", "dashdot"
             ))
```

### Lines with Markers

```r
p <- plot_ly(df, x = ~date, y = ~value,
             type = "scatter", mode = "lines+markers",
             marker = list(size = 6))
```

---

## Bar Charts

### Vertical Bars

```r
p <- plot_ly(df, x = ~category, y = ~value, type = "bar")
```

### Horizontal Bars

```r
p <- plot_ly(df, x = ~value, y = ~category, type = "bar",
             orientation = "h")
```

### Grouped Bars

```r
p <- plot_ly(df, x = ~category, y = ~value_a, type = "bar", name = "Group A") |>
  add_bars(y = ~value_b, name = "Group B") |>
  layout(barmode = "group")
```

### Stacked Bars

```r
p <- plot_ly(df, x = ~category, y = ~value_a, type = "bar", name = "A") |>
  add_bars(y = ~value_b, name = "B") |>
  layout(barmode = "stack")
```

### Bar Options

| Layout Argument | Values |
|-----------------|--------|
| `barmode` | `"group"`, `"stack"`, `"relative"`, `"overlay"` |
| `bargap` | Gap between bars (0-1) |
| `bargroupgap` | Gap between bar groups (0-1) |

---

## Histograms

### Basic Histogram

```r
p <- plot_ly(mtcars, x = ~mpg, type = "histogram")
```

### With Bin Control

```r
p <- plot_ly(mtcars, x = ~mpg, type = "histogram",
             nbinsx = 20)
```

### Colored by Category

```r
p <- plot_ly(mtcars, x = ~mpg, color = ~factor(cyl), type = "histogram") |>
  layout(barmode = "overlay")
```

### Histogram Options

| Argument | Purpose |
|----------|---------|
| `nbinsx` | Number of x bins |
| `nbinsy` | Number of y bins |
| `histnorm` | `"percent"`, `"probability"`, `"density"` |
| `cumulative = list(enabled = TRUE)` | Cumulative histogram |

---

## Box Plots

### Basic Box Plot

```r
p <- plot_ly(mtcars, y = ~mpg, type = "box")
```

### Grouped Box Plot

```r
p <- plot_ly(mtcars, x = ~factor(cyl), y = ~mpg, type = "box")
```

### With All Points

```r
p <- plot_ly(mtcars, x = ~factor(cyl), y = ~mpg, type = "box",
             boxpoints = "all",   # "all", "outliers", "suspectedoutliers", FALSE
             jitter = 0.3,
             pointpos = -1.8)
```

### Colored Box Plot

```r
p <- plot_ly(mtcars, x = ~factor(cyl), y = ~mpg,
             color = ~factor(am), type = "box") |>
  layout(boxmode = "group")
```

---

## Violin Plots

### Basic Violin

```r
p <- plot_ly(mtcars, y = ~mpg, type = "violin",
             box = list(visible = TRUE),
             meanline = list(visible = TRUE))
```

### Grouped Violin

```r
p <- plot_ly(mtcars, x = ~factor(cyl), y = ~mpg, type = "violin",
             box = list(visible = TRUE)) |>
  layout(violinmode = "group")
```

---

## Heatmaps

### Basic Heatmap

```r
# From a matrix
z <- matrix(rnorm(100), nrow = 10)
p <- plot_ly(z = ~z, type = "heatmap")
```

### With Labels

```r
p <- plot_ly(
  x = col_names,
  y = row_names,
  z = ~z_matrix,
  type = "heatmap",
  colorscale = "Viridis"
)
```

### Correlation Heatmap

```r
cor_mat <- cor(mtcars)
p <- plot_ly(
  x = colnames(cor_mat),
  y = rownames(cor_mat),
  z = ~cor_mat,
  type = "heatmap",
  colorscale = "RdBu",
  zmin = -1, zmax = 1
) |>
  layout(title = "Correlation Matrix")
```

### Color Scales

Common colorscale values: `"Viridis"`, `"Hot"`, `"Greys"`, `"YlGnBu"`,
`"RdBu"`, `"Blues"`, `"Greens"`, `"Reds"`, `"Picnic"`, `"Portland"`.

---

## 3D Charts

### 3D Scatter

```r
p <- plot_ly(
  mtcars,
  x = ~wt, y = ~hp, z = ~mpg,
  color = ~factor(cyl),
  type = "scatter3d",
  mode = "markers"
)
```

### 3D Surface

```r
z <- matrix(rnorm(400), nrow = 20)
p <- plot_ly(z = ~z, type = "surface")
```

### 3D Surface with Axes

```r
p <- plot_ly(z = ~z, type = "surface") |>
  layout(scene = list(
    xaxis = list(title = "X"),
    yaxis = list(title = "Y"),
    zaxis = list(title = "Z")
  ))
```

---

## Pie Charts

```r
p <- plot_ly(
  labels = c("A", "B", "C", "D"),
  values = c(30, 25, 20, 25),
  type = "pie"
)
```

### Donut Chart

```r
p <- plot_ly(
  labels = c("A", "B", "C"),
  values = c(40, 35, 25),
  type = "pie",
  hole = 0.4
)
```

---

## Chart Selection Guide

| Data Type | Recommended |
|-----------|-------------|
| Two continuous variables | `type = "scatter", mode = "markers"` |
| Time series | `type = "scatter", mode = "lines"` |
| Categories vs values | `type = "bar"` |
| Distribution (one var) | `type = "histogram"` |
| Distribution comparison | `type = "box"` or `type = "violin"` |
| Matrix / correlation | `type = "heatmap"` |
| Part of whole | `type = "pie"` |
| 3D relationships | `type = "scatter3d"` |
| 3D surface | `type = "surface"` |
