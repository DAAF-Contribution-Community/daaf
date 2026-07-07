---
name: plotly-r
description: |
  Interactive R visualization with plotly: plot_ly() for scatter, line, bar,
  heatmap, 3D charts; ggplotly() to convert ggplot2 objects; layout() for
  customization; htmlwidgets::saveWidget() for export. Use when execution
  language is R and interactivity needed. Python equivalent: plotly. For
  static figures use ggplot2.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "plotly 4.12.0"
  skill-last-updated: "2026-05-08"
  tags: ["r", "visualization", "interactive", "plotly"]
---

# plotly-r Skill

Interactive R visualization with the plotly package (4.12.0). Covers plot_ly()
for direct trace-based charts (scatter, line, bar, histogram, box, heatmap, 3D
scatter, 3D surface); ggplotly() for converting ggplot2 objects to interactive
equivalents; layout() for axis, title, legend, and annotation customization;
subplot() for multi-panel composition; and htmlwidgets::saveWidget() for
self-contained HTML export. Use when execution language is R and interactive
hover/zoom/pan behavior is needed. Python equivalent: plotly (Plotly Express +
Graph Objects). For static publication-quality R figures, use ggplot2 instead.

## What is plotly for R?

plotly is an R interface to the Plotly.js JavaScript library:
- **Interactive**: Hover, zoom, pan, and select built-in
- **Two approaches**: plot_ly() (direct) and ggplotly() (convert from ggplot2)
- **Web-based**: Renders as HTML/JavaScript via htmlwidgets
- **Wide chart support**: scatter, line, bar, histogram, box, heatmap, 3D, maps
- **Piping**: Works with R's native pipe `|>` for chained layout/trace updates

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | plot_ly() basics, add_trace(), piping, saveWidget | Starting out |
| `chart-types.md` | scatter, line, bar, histogram, box, heatmap, 3D | Choosing chart types |
| `ggplotly.md` | Converting ggplot2 objects, tooltip customization | ggplot2 bridge |
| `layouts.md` | layout() for axes, titles, legends, annotations | Customizing appearance |
| `export.md` | saveWidget(), orca/kaleido for static, Quarto embedding | Saving and sharing |
| `subplots.md` | subplot() composition, shared axes, mixed types | Multi-panel layouts |
| `gotchas.md` | plot_ly vs ggplotly tradeoffs, formula interface, performance | Debugging |

### Reading Order

1. **Quick plot?** Start with `quickstart.md`
2. **Which chart?** Check `chart-types.md`
3. **Have ggplot2 code?** Read `ggplotly.md`
4. **Customize layout?** Read `layouts.md`
5. **Save/export?** Read `export.md`
6. **Multiple panels?** Read `subplots.md`
7. **Trouble?** Check `gotchas.md`

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `plotly` | Python equivalent (Plotly Express + Graph Objects) |
| `ggplot2` | Static R figures; ggplotly() converts ggplot2 objects to interactive |
| `quarto` | Quarto embedding for plotly htmlwidgets |
| `tidyverse` | Data preparation -- tidy data feeds into plot_ly() pipelines |
| `r-python-translation` | Cross-language visualization translation |
| `data-scientist` | Method selection and visualization design guidance |

## Quick Decision Trees

### "What chart type do I need?"

```
What are you visualizing?
|-- Relationship (x vs y)
|   |-- Continuous x, continuous y -> plot_ly(type = "scatter", mode = "markers")
|   |-- Time series -> plot_ly(type = "scatter", mode = "lines")
|   +-- With error/uncertainty -> add error bars via error_y
|-- Distribution
|   |-- One variable -> plot_ly(type = "histogram")
|   |-- By group -> plot_ly(type = "box") or plot_ly(type = "violin")
|   +-- Heatmap/density -> plot_ly(type = "heatmap")
|-- Comparison
|   |-- Counts/values -> plot_ly(type = "bar")
|   +-- Grouped -> barmode = "group" in layout()
|-- 3D
|   |-- Scatter -> plot_ly(type = "scatter3d")
|   +-- Surface -> plot_ly(type = "surface")
+-- Already have ggplot2 code -> ggplotly(p)
```

### "How do I save this plot?"

```
Saving a plot?
|-- Interactive HTML (primary DAAF export) -> htmlwidgets::saveWidget()
|-- Static PNG (requires orca/kaleido) -> orca() or kaleido()
|-- Embed in Quarto -> just print the widget in a code chunk
+-- Temp file (smoke tests) -> saveWidget(p, tempfile(fileext = ".html"))
```

### "plot_ly() or ggplotly()?"

```
Which approach?
|-- Building from scratch -> plot_ly()
|-- Already have ggplot2 code -> ggplotly()
|-- Need fine-grained trace control -> plot_ly()
|-- Quick interactive version of static plot -> ggplotly()
|-- Complex multi-trace with mixed types -> plot_ly() + add_trace()
+-- Want ggplot2 facets interactive -> ggplotly() (preserves faceting)
```

## File-First Execution in Research Workflows

In DAAF research pipelines, all visualizations are generated through **script
files** in `scripts/stage8_analysis/`, not interactively. This ensures auditability
and reproducibility.

**The pattern:**
1. Write plot code to `scripts/stage8_analysis/{step}_{plot-name}.R`
2. Execute via `bash {BASE_DIR}/scripts/run_with_capture.sh {script_path}`
3. Output gets appended to the script as comments
4. Use `htmlwidgets::saveWidget()` to save interactive HTML to the project output directory

See `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first
execution protocol.

## Quick Reference

### Essential Setup

```r
library(plotly)
library(htmlwidgets)  # saveWidget() for HTML export
```

### Basic plot_ly() Pattern

```r
p <- plot_ly(df, x = ~col_x, y = ~col_y, type = "scatter", mode = "markers")
p
```

Note the **formula interface**: columns are referenced with `~col_name` (tilde
prefix), not bare names or strings.

### ggplotly() Bridge

```r
library(ggplot2)
library(plotly)

g <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point()

p <- ggplotly(g)
p
```

### Common plot_ly() Trace Types

| Type | Mode | Use Case |
|------|------|----------|
| `"scatter"` | `"markers"` | Scatter plot |
| `"scatter"` | `"lines"` | Line chart |
| `"scatter"` | `"lines+markers"` | Line with points |
| `"bar"` | — | Bar chart |
| `"histogram"` | — | Histogram |
| `"box"` | — | Box plot |
| `"heatmap"` | — | Heatmap |
| `"scatter3d"` | `"markers"` | 3D scatter |
| `"surface"` | — | 3D surface |

### Layout Customization

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  layout(
    title = "My Plot",
    xaxis = list(title = "X Label"),
    yaxis = list(title = "Y Label")
  )
```

### Saving Plots

```r
library(htmlwidgets)

# HTML export (uses CDN for plotly.js -- default for DAAF)
saveWidget(p, "plot.html", selfcontained = FALSE)

# Self-contained HTML (embeds plotly.js, ~3MB -- requires pandoc)
# saveWidget(p, "plot.html", selfcontained = TRUE)  # NOT available in DAAF (no pandoc)
```

> **DAAF note:** `selfcontained = TRUE` requires pandoc, which is not installed
> in the DAAF container. Use `selfcontained = FALSE` (loads plotly.js from CDN).
> Static image export via `orca()` or `kaleido()` is also not available. Use
> **ggplot2** with `ggsave()` for static PNG/SVG figures.

### Piping with |>

plotly R functions return the plot object, enabling piping:

```r
p <- plot_ly(df, x = ~x, y = ~y, type = "scatter", mode = "markers") |>
  add_trace(y = ~y2, name = "Series 2", mode = "lines") |>
  layout(title = "Two Series", xaxis = list(title = "X")) |>
  config(displayModeBar = FALSE)
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| plot_ly() basics | `./references/quickstart.md` |
| add_trace() | `./references/quickstart.md` |
| Formula interface (~x) | `./references/quickstart.md` |
| Piping with \|> | `./references/quickstart.md` |
| saveWidget() | `./references/quickstart.md` |
| Scatter plots | `./references/chart-types.md` |
| Line charts | `./references/chart-types.md` |
| Bar charts | `./references/chart-types.md` |
| Histograms | `./references/chart-types.md` |
| Box plots | `./references/chart-types.md` |
| Heatmaps | `./references/chart-types.md` |
| 3D scatter and surface | `./references/chart-types.md` |
| ggplotly() conversion | `./references/ggplotly.md` |
| Tooltip customization | `./references/ggplotly.md` |
| ggplotly limitations | `./references/ggplotly.md` |
| Axis titles and formatting | `./references/layouts.md` |
| Legends | `./references/layouts.md` |
| Annotations | `./references/layouts.md` |
| Multiple axes | `./references/layouts.md` |
| Color scales | `./references/layouts.md` |
| HTML export | `./references/export.md` |
| Static image export | `./references/export.md` |
| Quarto embedding | `./references/export.md` |
| subplot() composition | `./references/subplots.md` |
| Shared axes in subplots | `./references/subplots.md` |
| Mixed chart types | `./references/subplots.md` |
| plot_ly vs ggplotly | `./references/gotchas.md` |
| Formula interface gotchas | `./references/gotchas.md` |
| Performance with large data | `./references/gotchas.md` |
| Common errors | `./references/gotchas.md` |

## Citation

When plotly is used as a primary visualization tool, include in the report's
Software & Tools references:

> Sievert, C. (2020). *Interactive Web-Based Data Visualization with R, plotly, and shiny*. Chapman and Hall/CRC. https://plotly-r.com

**Cite when:** plotly produces interactive figures included in the report or notebook.
**Do not cite when:** Only used for quick exploratory plots not included in deliverables.
