# ggplotly() -- Converting ggplot2 Objects

## Basic Conversion

ggplotly() takes a ggplot2 object and converts it to an interactive plotly widget:

```r
library(ggplot2)
library(plotly)

g <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  labs(title = "MPG vs Weight", color = "Cylinders") +
  theme_minimal()

p <- ggplotly(g)
p
```

Hover, zoom, pan, and select are automatically enabled.

## What Converts Well

| ggplot2 Feature | ggplotly Support |
|-----------------|------------------|
| geom_point | Full |
| geom_line | Full |
| geom_bar / geom_col | Full |
| geom_histogram | Full |
| geom_boxplot | Full |
| geom_smooth | Full (trend line + CI ribbon) |
| geom_tile | Full |
| geom_area | Full |
| geom_ribbon | Full |
| facet_wrap / facet_grid | Full (creates subplot panels) |
| scale_color_* / scale_fill_* | Full |
| labs() | Full |
| theme_minimal() etc. | Partial (some theme elements mapped) |
| coord_flip() | Full |

## Tooltip Customization

### Default Tooltip

By default, ggplotly shows all mapped aesthetics in the tooltip:

```r
g <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point()

# Default tooltip shows x, y, and color
p <- ggplotly(g)
```

### Selecting Tooltip Variables

Use the `tooltip` argument to control which aesthetics appear:

```r
p <- ggplotly(g, tooltip = c("x", "y"))  # Only x and y
p <- ggplotly(g, tooltip = "text")       # Only custom text
p <- ggplotly(g, tooltip = "all")        # Everything (default)
```

### Custom Tooltip with text Aesthetic

Map a `text` aesthetic in ggplot2 to provide custom hover content:

```r
g <- ggplot(mtcars, aes(
  x = wt, y = mpg,
  color = factor(cyl),
  text = paste(
    "Car:", rownames(mtcars),
    "\nWeight:", wt,
    "\nMPG:", mpg,
    "\nCylinders:", cyl
  )
)) +
  geom_point(size = 3)

p <- ggplotly(g, tooltip = "text")
```

### Modifying Tooltip After Conversion

```r
p <- ggplotly(g)

# Modify hover template for all traces
p <- p |> style(
  hovertemplate = paste(
    "<b>Weight:</b> %{x:.1f}<br>",
    "<b>MPG:</b> %{y:.1f}",
    "<extra></extra>"
  )
)
```

## Layout Modifications After Conversion

ggplotly returns a plotly object, so you can chain layout() and other functions:

```r
p <- ggplotly(g) |>
  layout(
    title = list(text = "Updated Title", x = 0.5),
    legend = list(orientation = "h", y = -0.2)
  ) |>
  config(displayModeBar = FALSE)
```

## Faceted Plots

ggplotly preserves facet structure:

```r
g <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  geom_smooth(method = "lm") +
  facet_wrap(~ cyl, scales = "free") +
  theme_minimal()

p <- ggplotly(g)
```

Each facet becomes a separate subplot panel with independent hover behavior.

## Sizing

### Dynamic Sizing

```r
# Fill container (default)
p <- ggplotly(g, dynamicTicks = TRUE)
```

### Fixed Sizing

```r
p <- ggplotly(g, width = 800, height = 600)
```

## Animations with frame

ggplotly supports animation via the `frame` aesthetic:

```r
g <- ggplot(gapminder::gapminder, aes(
  x = gdpPercap, y = lifeExp,
  size = pop, color = continent,
  frame = year,       # Animation frame
  ids = country       # Smooth transitions between frames
)) +
  geom_point(alpha = 0.7) +
  scale_x_log10()

p <- ggplotly(g) |>
  animation_opts(frame = 1000, transition = 500)
```

Note: the gapminder package must be installed for this example.

## Limitations and Gotchas

### Features That Do Not Convert Well

| Feature | Issue |
|---------|-------|
| `geom_text()` / `geom_label()` | Labels may overlap; no repulsion (unlike ggrepel) |
| Complex custom themes | Many theme() elements are ignored or approximated |
| `annotation_custom()` | Not supported |
| `geom_sf()` | Spatial geometries not supported; use plotly's geo traces |
| `coord_polar()` | Not supported |
| `geom_raster()` | Use geom_tile() instead for conversion |
| Patchwork compositions | Each plot must be converted separately; use subplot() |
| `geom_ribbon()` fillcolor | May need manual adjustment after conversion |
| Subtle line type patterns | Some dash patterns approximate differently |

### Patchwork Does Not Convert

patchwork compositions cannot be passed to ggplotly() directly. Convert each
plot individually and use plotly's subplot():

```r
# WRONG
# ggplotly(p1 + p2)  # Error

# CORRECT
p1_ly <- ggplotly(g1)
p2_ly <- ggplotly(g2)
subplot(p1_ly, p2_ly, nrows = 1)
```

### Legend Duplication

When multiple geoms map the same aesthetic, ggplotly may create duplicate legend
entries. Fix with showlegend:

```r
p <- ggplotly(g)
# Hide legend for specific traces
p$x$data[[2]]$showlegend <- FALSE
```

Or more robustly:

```r
p <- ggplotly(g) |>
  style(showlegend = FALSE, traces = 3:4)
```

### Theme Elements Lost

ggplotly maps ggplot2 themes to plotly layout as best it can, but many
element_text(), element_line(), and element_rect() customizations are dropped.
For precise styling, apply layout() after conversion:

```r
p <- ggplotly(g) |>
  layout(
    font = list(family = "Arial", size = 12),
    paper_bgcolor = "white",
    plot_bgcolor = "white"
  )
```

## When to Use ggplotly() vs plot_ly()

| Situation | Recommendation |
|-----------|----------------|
| Already have ggplot2 code | ggplotly() |
| Want quick interactive version | ggplotly() |
| Need precise trace control | plot_ly() |
| Multiple trace types (bar + line) | plot_ly() + add_trace() |
| Performance with large data | plot_ly() (avoids ggplot2 overhead) |
| Complex tooltip formatting | plot_ly() (hovertemplate is easier) |
| Publication static + interactive | ggplot2 for static, ggplotly() for interactive |
| Patchwork multi-panel | ggplotly() each panel + subplot() |
