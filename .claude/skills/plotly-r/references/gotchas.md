# Gotchas and Best Practices

## plot_ly() vs ggplotly() Tradeoffs

### When to Use Each

| Situation | Recommendation | Why |
|-----------|---------------|-----|
| Building from scratch | plot_ly() | Direct control, cleaner code |
| Already have ggplot2 code | ggplotly() | Minimal effort conversion |
| Fine-grained trace control | plot_ly() | add_trace() is more explicit |
| Quick interactive preview | ggplotly() | One function call |
| Complex multi-trace | plot_ly() | Mixing trace types is clearer |
| Need both static and interactive | ggplot2 + ggplotly() | Same base plot, two outputs |
| Large datasets (>50k rows) | plot_ly() | Avoids ggplot2 rendering overhead |
| Faceted panels | ggplotly() | Facets convert well |
| Publication static figures | ggplot2 (not plotly) | ggsave() for PNG/PDF |

### Key Insight

ggplotly() is a convenience wrapper, not a full port. It converts the ggplot2
object to plotly's JSON structure, which means some features are lost or
approximated. For production interactive charts, plot_ly() gives more predictable
results.

---

## Formula Interface (~x) Gotchas

### The Tilde is Required

```r
# CORRECT: formula interface
plot_ly(df, x = ~column_name, y = ~other_column)

# WRONG: bare name (causes error)
# plot_ly(df, x = column_name)  # Error: object 'column_name' not found

# WRONG: string (creates literal text axis, not data mapping)
# plot_ly(df, x = "column_name")  # Plots the literal string
```

### Inline Transformations

The formula interface supports R expressions:

```r
plot_ly(df, x = ~log(value), y = ~rate * 100)
plot_ly(df, x = ~factor(year), y = ~enrollment / 1000)
plot_ly(df, x = ~paste(first, last), y = ~score)
```

### Environment Scoping

The tilde evaluates in the data frame's context first, then the calling
environment. If a column name matches a variable name, the column takes
precedence:

```r
x <- 42
plot_ly(df, x = ~x)  # Uses df$x, not the variable x = 42
```

---

## Common Errors

### "Error: object not found"

Column referenced without tilde:

```r
# WRONG
plot_ly(df, x = my_column)

# CORRECT
plot_ly(df, x = ~my_column)
```

### Literal String on Axis

Passing a string instead of a formula creates a categorical axis with one value:

```r
# WRONG -- shows "value" as a literal category
plot_ly(df, x = "value", y = ~count, type = "bar")

# CORRECT
plot_ly(df, x = ~value, y = ~count, type = "bar")
```

### Type/Mode Mismatch

Some type/mode combinations are invalid:

```r
# WRONG: "bar" type does not use "mode"
plot_ly(df, x = ~x, y = ~y, type = "bar", mode = "markers")

# CORRECT: bar has no mode
plot_ly(df, x = ~x, y = ~y, type = "bar")

# Scatter requires mode
plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers")
```

### Implicit Type Inference

If you omit `type`, plotly guesses based on data types. This can produce
unexpected results:

```r
# Ambiguous -- plotly infers type
plot_ly(df, x = ~x, y = ~y)

# Explicit -- always predictable
plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers")
```

Always specify `type` (and `mode` for scatter) explicitly.

### Color Argument Confusion

```r
# Map color to data (automatic palette)
plot_ly(df, x = ~x, y = ~y, color = ~group, type = "scatter", mode = "markers")

# Fixed color (use marker argument, NOT color)
plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers",
        marker = list(color = "red"))

# WRONG: color = "red" tries to find a column named "red"
# plot_ly(df, x = ~x, y = ~y, color = "red")  # Error or unexpected behavior
```

### saveWidget Path Issues

saveWidget() requires an absolute path or a path relative to the working
directory. Relative paths with `../` can fail:

```r
# SAFE: absolute path
saveWidget(p, "/daaf/research/project/output/plot.html", selfcontained = FALSE)

# SAFE: file.path() construction
saveWidget(p, file.path(OUTPUT_DIR, "plot.html"), selfcontained = FALSE)

# RISKY: relative path with parent traversal
# saveWidget(p, "../output/plot.html")  # May fail depending on temp dir behavior
```

---

## Performance with Large Data

### Row Count Guidelines

| Rows | Performance | Recommendation |
|------|------------|----------------|
| < 5,000 | Fast | Standard plot_ly() |
| 5,000 - 50,000 | Moderate | Use WebGL: `toWebGL()` |
| 50,000 - 500,000 | Slow | Aggregate or sample |
| > 500,000 | Very slow / browser freeze | Must aggregate |

### WebGL Rendering

For scatter plots with many points, convert to WebGL:

```r
p <- plot_ly(large_df, x = ~x, y = ~y, type = "scattergl", mode = "markers")

# Or convert after creation
p <- plot_ly(large_df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  toWebGL()
```

### Data Aggregation

```r
# Sample for exploration
sampled <- df[sample(nrow(df), 5000), ]
plot_ly(sampled, x = ~x, y = ~y, type = "scatter", mode = "markers")

# Aggregate for bar charts
library(dplyr)
agg <- df |>
  group_by(category) |>
  summarize(mean_value = mean(value), .groups = "drop")
plot_ly(agg, x = ~category, y = ~mean_value, type = "bar")
```

### File Size Concerns

Self-contained HTML files can be large because they embed plotly.js (~3MB):

- A basic chart: ~3-4MB
- Chart with many points: can grow significantly
- Multiple saveWidget() calls: each file embeds plotly.js independently

For many charts, consider `selfcontained = FALSE` to share the plotly.js library.

---

## ggplotly-Specific Gotchas

### Patchwork Does Not Convert

```r
# WRONG -- errors
# ggplotly(p1 + p2)

# CORRECT -- convert individually, then subplot()
subplot(ggplotly(g1), ggplotly(g2), nrows = 1)
```

### Legend Duplication

Multiple geom layers with the same aesthetic can create duplicate legend entries:

```r
g <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point() +
  geom_smooth(method = "lm")

p <- ggplotly(g)
# May show duplicate legend entries for point and line traces
```

Fix by hiding extra legend entries:

```r
p <- ggplotly(g) |>
  style(showlegend = FALSE, traces = 4:6)
```

### Theme Elements Lost

Many ggplot2 theme() settings do not transfer. Apply styling after conversion:

```r
p <- ggplotly(g) |>
  layout(
    font = list(family = "Arial"),
    paper_bgcolor = "white",
    plot_bgcolor = "white"
  )
```

---

## Syntax Differences: R plotly vs Python plotly

| Aspect | R | Python |
|--------|---|--------|
| Column reference | `~col` (formula) | `"col"` (string) |
| Layout args | `list(title = "X")` | `dict(title="X")` |
| Chaining | `\|>` pipe | `.update_layout()` method |
| Add trace | `add_trace()` / `add_lines()` | `fig.add_trace()` |
| Subplot | `subplot(p1, p2)` | `make_subplots()` + `add_trace()` |
| Save HTML | `saveWidget()` | `fig.write_html()` |
| Static export | `orca()` / `kaleido()` | `fig.write_image()` |
| Config | `config()` | `fig.update_layout()` or `fig.show(config=)` |
| Boolean | `TRUE` / `FALSE` | `True` / `False` |
| NULL | `NULL` | `None` |

---

## Best Practices

### 1. Always Specify type and mode

```r
# Explicit -- always predictable
plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers")
```

### 2. Use |> Pipe for Readability

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  layout(title = "Title") |>
  config(displaylogo = FALSE)
```

### 3. HTML Export for DAAF (selfcontained = FALSE)

```r
# selfcontained = TRUE requires pandoc (not installed in DAAF)
saveWidget(p, file.path(OUTPUT_DIR, "plot.html"), selfcontained = FALSE)
```

### 4. Static Figures via ggplot2

For PNG/SVG/PDF output in DAAF, use ggplot2 + ggsave(). plotly is for interactive
HTML only (no kaleido/orca in the container).

### 5. Check Data Before Plotting

```r
cat("Rows:", nrow(df), "\n")
cat("Columns:", paste(names(df), collapse = ", "), "\n")
cat("NAs:\n")
print(colSums(is.na(df)))
```

### 6. Use toWebGL() for Large Scatter

```r
p <- plot_ly(large_df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  toWebGL()
```
