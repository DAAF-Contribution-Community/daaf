# Layout Customization

## layout() Basics

layout() controls everything outside the traces: titles, axes, legends,
margins, annotations, and background. It takes named list arguments:

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  layout(
    title = "My Plot",
    xaxis = list(title = "X Axis"),
    yaxis = list(title = "Y Axis")
  )
```

---

## Title

### Simple Title

```r
layout(title = "My Chart Title")
```

### Styled Title

```r
layout(
  title = list(
    text = "My Chart Title",
    x = 0.5,                        # Center (0 = left, 1 = right)
    font = list(size = 20, family = "Arial", color = "black")
  )
)
```

### Subtitle Pattern

plotly does not have a native subtitle. Use annotations:

```r
layout(
  title = list(text = "Main Title", x = 0.5, y = 0.95),
  annotations = list(
    list(
      text = "Subtitle text here",
      x = 0.5, y = 1.05, xref = "paper", yref = "paper",
      showarrow = FALSE,
      font = list(size = 14, color = "grey50")
    )
  )
)
```

---

## Axes

### Axis Titles

```r
layout(
  xaxis = list(title = "X Label"),
  yaxis = list(title = "Y Label")
)

# Styled axis title
layout(
  xaxis = list(title = list(
    text = "X Label",
    font = list(size = 14, color = "black")
  ))
)
```

### Axis Range

```r
layout(
  xaxis = list(range = c(0, 100)),
  yaxis = list(range = c(-10, 10))
)

# Start at zero
layout(yaxis = list(rangemode = "tozero"))
```

### Tick Formatting

```r
layout(
  xaxis = list(
    tickformat = ".2f",          # Number format
    tickprefix = "$",            # Prefix
    ticksuffix = "%",            # Suffix
    tickangle = 45,              # Rotate labels
    dtick = 10                   # Tick interval
  )
)

# Date format
layout(xaxis = list(tickformat = "%Y-%m-%d"))

# Comma-separated thousands
layout(yaxis = list(tickformat = ","))
```

### Log Scale

```r
layout(yaxis = list(type = "log"))
```

### Reversed Axis

```r
layout(yaxis = list(autorange = "reversed"))
```

### Grid Lines

```r
layout(
  xaxis = list(
    showgrid = TRUE,
    gridwidth = 1,
    gridcolor = "lightgray"
  )
)

# Hide grid
layout(
  xaxis = list(showgrid = FALSE),
  yaxis = list(showgrid = FALSE)
)
```

### Axis Lines

```r
layout(
  xaxis = list(
    showline = TRUE,
    linewidth = 2,
    linecolor = "black",
    mirror = TRUE    # Show on opposite side too
  )
)
```

### Zero Line

```r
layout(
  xaxis = list(zeroline = TRUE, zerolinewidth = 1, zerolinecolor = "grey"),
  yaxis = list(zeroline = TRUE)
)
```

---

## Legend

### Position

```r
# Right side (default)
layout(legend = list(x = 1, y = 1, xanchor = "left"))

# Bottom horizontal
layout(legend = list(
  orientation = "h",
  x = 0.5, y = -0.15,
  xanchor = "center"
))

# Inside plot area
layout(legend = list(x = 0.02, y = 0.98))
```

### Legend Title

```r
layout(legend = list(title = list(text = "Categories")))
```

### Legend Appearance

```r
layout(legend = list(
  bgcolor = "white",
  bordercolor = "black",
  borderwidth = 1,
  font = list(size = 12)
))
```

### Hide Legend

```r
layout(showlegend = FALSE)
```

---

## Margins

```r
layout(margin = list(l = 60, r = 20, t = 80, b = 60))

# Tight margins
layout(margin = list(l = 0, r = 0, t = 30, b = 0))
```

---

## Size

```r
layout(
  width = 800,
  height = 600,
  autosize = FALSE
)
```

---

## Background

```r
layout(
  paper_bgcolor = "white",    # Area outside plot
  plot_bgcolor = "#f8f8f8"    # Plot area
)
```

---

## Font

```r
layout(font = list(
  family = "Arial, sans-serif",
  size = 14,
  color = "black"
))
```

---

## Annotations

### Text Annotation

```r
layout(annotations = list(
  list(
    x = 2, y = 25,
    text = "Important point",
    showarrow = TRUE,
    arrowhead = 2,
    ax = 40, ay = -30   # Arrow offset in pixels
  )
))
```

### Styled Annotation

```r
layout(annotations = list(
  list(
    x = 3, y = 20,
    text = "Label",
    font = list(size = 14, color = "red"),
    bgcolor = "white",
    bordercolor = "black",
    borderwidth = 1,
    showarrow = FALSE
  )
))
```

### Multiple Annotations

```r
layout(annotations = list(
  list(x = 1, y = 2, text = "Point A", showarrow = TRUE),
  list(x = 3, y = 4, text = "Point B", showarrow = TRUE)
))
```

---

## Reference Lines and Shapes

### Horizontal / Vertical Lines

plotly R does not have add_hline()/add_vline() convenience functions like Python.
Use shapes:

```r
layout(shapes = list(
  # Horizontal line
  list(
    type = "line",
    x0 = 0, x1 = 1, xref = "paper",   # Full width
    y0 = 50, y1 = 50, yref = "y",
    line = list(color = "red", dash = "dash", width = 1)
  ),
  # Vertical line
  list(
    type = "line",
    x0 = 3, x1 = 3, xref = "x",
    y0 = 0, y1 = 1, yref = "paper",   # Full height
    line = list(color = "blue", dash = "dot", width = 1)
  )
))
```

### Rectangles (Shaded Regions)

```r
layout(shapes = list(
  list(
    type = "rect",
    x0 = 2, x1 = 4, xref = "x",
    y0 = 0, y1 = 1, yref = "paper",
    fillcolor = "green", opacity = 0.2,
    line = list(width = 0)
  )
))
```

---

## Color Scales

### Continuous Color

```r
plot_ly(df, x = ~x, y = ~y, color = ~value,
        colors = viridisLite::viridis(256),
        type = "scatter", mode = "markers") |>
  layout(coloraxis = list(colorbar = list(title = "Value")))
```

### Reversed Color Scale

```r
plot_ly(df, x = ~x, y = ~y, color = ~value,
        colors = rev(viridisLite::viridis(256)),
        type = "scatter", mode = "markers")
```

### Discrete Color

```r
plot_ly(df, x = ~x, y = ~y, color = ~group,
        colors = c("A" = "red", "B" = "blue", "C" = "green"),
        type = "scatter", mode = "markers")
```

### Built-in Color Palettes

Works with RColorBrewer palette names:

```r
plot_ly(df, x = ~x, y = ~y, color = ~group,
        colors = "Set1",
        type = "scatter", mode = "markers")
```

Common palettes: `"Set1"`, `"Set2"`, `"Dark2"`, `"Paired"`, `"Pastel1"`,
`"Blues"`, `"Reds"`.

Note: `"Viridis"` is NOT an RColorBrewer palette -- `colors = "Viridis"` errors
(`invalid color name 'Viridis'`). Use `colors = viridisLite::viridis(256)` for
the viridis palette. (`"Viridis"` is valid only as a trace-level plotly.js
`colorscale`, e.g. `marker = list(colorscale = "Viridis")`.)

---

## Hover Mode

```r
# Show all traces at same x position
layout(hovermode = "x unified")

# Options: "x", "y", "closest", "x unified", "y unified", FALSE
```

---

## config()

config() controls the toolbar and interaction behavior:

```r
p |> config(
  displayModeBar = FALSE,        # Hide toolbar
  scrollZoom = FALSE,            # Disable scroll zoom
  staticPlot = FALSE,            # If TRUE, disables all interaction
  displaylogo = FALSE,           # Hide Plotly logo
  modeBarButtonsToRemove = c("zoom2d", "pan2d", "select2d", "lasso2d")
)
```

---

## Publication-Ready Recipe

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers",
             marker = list(size = 8, color = "steelblue")) |>
  layout(
    title = list(text = "Title", font = list(size = 16), x = 0.5),
    xaxis = list(
      title = "X Label",
      showline = TRUE, linewidth = 1, linecolor = "black",
      showgrid = FALSE
    ),
    yaxis = list(
      title = "Y Label",
      showline = TRUE, linewidth = 1, linecolor = "black",
      showgrid = TRUE, gridcolor = "#eeeeee"
    ),
    paper_bgcolor = "white",
    plot_bgcolor = "white",
    font = list(family = "Arial", size = 12),
    margin = list(l = 60, r = 20, t = 50, b = 50)
  ) |>
  config(displaylogo = FALSE)
```
