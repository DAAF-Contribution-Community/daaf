# Subplots

## subplot() Basics

plotly R uses `subplot()` to combine multiple plotly objects into a single figure:

```r
p1 <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers")
p2 <- plot_ly(mtcars, x = ~factor(cyl), type = "bar")

combined <- subplot(p1, p2)
combined
```

---

## Layout Options

### Side by Side (Default)

```r
subplot(p1, p2, nrows = 1)  # 1 row, 2 columns (default)
```

### Stacked Vertically

```r
subplot(p1, p2, nrows = 2)
```

### Grid Layout

```r
subplot(p1, p2, p3, p4, nrows = 2)  # 2x2 grid
```

### Custom Widths

```r
subplot(p1, p2, widths = c(0.7, 0.3))  # 70%-30% split
```

### Custom Heights

```r
subplot(p1, p2, nrows = 2, heights = c(0.6, 0.4))  # 60%-40% split
```

### Spacing

```r
subplot(p1, p2, margin = 0.05)  # 5% margin between subplots
```

---

## Shared Axes

### Share X Axis

```r
subplot(p1, p2, nrows = 2, shareX = TRUE)
```

### Share Y Axis

```r
subplot(p1, p2, shareY = TRUE)
```

### Share Both

```r
subplot(p1, p2, nrows = 2, shareX = TRUE, shareY = TRUE)
```

Shared axes are linked -- zooming one panel zooms all panels on that axis.

---

## Subplot Titles

plotly R does not have a direct `subplot_titles` argument. Use annotations:

```r
combined <- subplot(p1, p2, nrows = 1, margin = 0.05) |>
  layout(annotations = list(
    list(
      text = "Plot A",
      x = 0.2, y = 1.05, xref = "paper", yref = "paper",
      showarrow = FALSE, font = list(size = 14)
    ),
    list(
      text = "Plot B",
      x = 0.8, y = 1.05, xref = "paper", yref = "paper",
      showarrow = FALSE, font = list(size = 14)
    )
  ))
```

---

## Mixed Chart Types

subplot() handles different trace types naturally:

```r
p_scatter <- plot_ly(mtcars, x = ~wt, y = ~mpg,
                     type = "scatter", mode = "markers", name = "Scatter")
p_bar <- plot_ly(mtcars, x = ~factor(cyl), type = "bar", name = "Bar")
p_hist <- plot_ly(mtcars, x = ~mpg, type = "histogram", name = "Histogram")

combined <- subplot(p_scatter, p_bar, p_hist, nrows = 1, margin = 0.05)
```

---

## Combining ggplotly Objects

Convert ggplot2 plots individually, then combine with subplot():

```r
library(ggplot2)
library(plotly)

g1 <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() + theme_minimal()
g2 <- ggplot(mtcars, aes(x = factor(cyl))) +
  geom_bar(fill = "steelblue") + theme_minimal()

p1 <- ggplotly(g1)
p2 <- ggplotly(g2)

combined <- subplot(p1, p2, nrows = 1, margin = 0.05)
```

Note: patchwork compositions (p1 + p2) cannot be converted via ggplotly().
Each plot must be converted separately, then combined with subplot().

---

## Adding an Overall Title

```r
combined <- subplot(p1, p2, nrows = 1) |>
  layout(title = list(text = "Dashboard Title", x = 0.5))
```

---

## Common Patterns

### Dashboard Layout (Overview + Details)

```r
p_main <- plot_ly(df, x = ~date, y = ~total, type = "scatter", mode = "lines",
                  name = "Total")
p_detail1 <- plot_ly(df, x = ~category, y = ~count, type = "bar",
                     name = "By Category")
p_detail2 <- plot_ly(df, x = ~value, type = "histogram", name = "Distribution")

dashboard <- subplot(
  p_main,
  subplot(p_detail1, p_detail2, nrows = 1, margin = 0.05),
  nrows = 2,
  heights = c(0.6, 0.4),
  margin = 0.08
) |>
  layout(title = list(text = "Dashboard", x = 0.5))
```

### Comparison Grid

```r
plots <- lapply(split(df, df$group), function(sub) {
  plot_ly(sub, x = ~x, y = ~y, type = "scatter", mode = "markers",
          name = unique(sub$group))
})

combined <- subplot(plots, nrows = 2, shareX = TRUE, shareY = TRUE)
```

### Before/After Comparison

```r
p_before <- plot_ly(df_before, x = ~x, y = ~y, type = "scatter",
                    mode = "markers", name = "Before")
p_after <- plot_ly(df_after, x = ~x, y = ~y, type = "scatter",
                   mode = "markers", name = "After")

subplot(p_before, p_after, shareY = TRUE, margin = 0.05) |>
  layout(title = "Before vs After")
```

---

## Limitations

| Limitation | Workaround |
|-----------|------------|
| No built-in subplot titles | Use annotations positioned above each panel |
| No colspan/rowspan spanning | Create nested subplot() calls |
| Secondary y-axis | Use `add_trace()` with `yaxis = "y2"` + layout `yaxis2` |
| No `specs` argument (unlike Python) | Use nesting for complex layouts |

### Secondary Y-Axis (Without subplot)

For dual y-axis on a single panel, use add_trace with yaxis specification:

```r
p <- plot_ly(df, x = ~date) |>
  add_lines(y = ~metric_a, name = "Metric A", yaxis = "y") |>
  add_bars(y = ~metric_b, name = "Metric B", yaxis = "y2") |>
  layout(
    yaxis = list(title = "Metric A"),
    yaxis2 = list(
      title = "Metric B",
      overlaying = "y",
      side = "right"
    )
  )
```
