---
name: plotly
description: Interactive visualization library for Python. Covers Plotly Express and Graph Objects for scatter, line, bar, histogram, box plots, subplots, styling, and export. Use when creating interactive plots with Plotly, building web-based visualizations, or needing hover/zoom functionality.
metadata:
  audience: python-developers
  domain: data-visualization
  plotly-version: "6.x"
---

# Plotly Skill

Quick reference for creating interactive data visualizations with Plotly, featuring both the high-level Plotly Express API and low-level Graph Objects.

## What is Plotly?

Plotly is an interactive visualization library for Python:
- **Interactive**: Hover, zoom, pan, and select built-in
- **Two APIs**: Plotly Express (simple) and Graph Objects (flexible)
- **Web-based**: Renders as HTML/JavaScript, works in notebooks and browsers
- **Wide chart support**: 40+ chart types including statistical, scientific, financial, and geographic

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Installation, imports, px vs go | Starting out |
| `charts.md` | Scatter, line, bar, histogram, box | Creating visualizations |
| `subplots-facets.md` | Multi-panel layouts, faceting | Multiple charts together |
| `styling.md` | Templates, colors, layout | Customizing appearance |
| `export.md` | HTML, images, JSON | Saving and sharing |
| `gotchas.md` | Common errors, best practices | Debugging |

## Quick Decision Trees

### "I need to create a chart"

```
What kind of chart?
├─ Scatter plot → ./references/charts.md
├─ Line chart → ./references/charts.md
├─ Bar chart → ./references/charts.md
├─ Histogram → ./references/charts.md
├─ Box/Violin plot → ./references/charts.md
├─ Heatmap → ./references/charts.md
├─ 3D/Maps/Financial → ./references/charts.md (Other Chart Types)
└─ Not sure → ./references/quickstart.md
```

### "I need multiple charts"

```
Multiple panels?
├─ Same chart, split by category → ./references/subplots-facets.md (faceting)
├─ Different charts in grid → ./references/subplots-facets.md (make_subplots)
├─ Shared axes → ./references/subplots-facets.md
└─ Secondary y-axis → ./references/subplots-facets.md
```

### "I need to customize appearance"

```
What to customize?
├─ Overall theme → ./references/styling.md (templates)
├─ Colors → ./references/styling.md
├─ Titles/labels → ./references/styling.md
├─ Axes → ./references/styling.md
├─ Legend → ./references/styling.md
└─ Hover info → ./references/styling.md
```

### "I need to save/export"

```
Export format?
├─ Interactive HTML → ./references/export.md
├─ Static image (PNG/SVG/PDF) → ./references/export.md
├─ JSON for API → ./references/export.md
└─ Embed in webpage → ./references/export.md
```

### "Something isn't working"

```
Common issues?
├─ Figure not showing → ./references/gotchas.md
├─ Image export fails → ./references/gotchas.md
├─ Performance issues → ./references/gotchas.md
├─ px vs go confusion → ./references/gotchas.md
└─ Column/data errors → ./references/gotchas.md
```

## File-First Execution in Research Workflows

**Important:** In data research pipelines (see `CLAUDE.md`), all visualizations are generated through **script files** in `scripts/stage8_viz/`, not interactively. This ensures auditability and reproducibility.

**The pattern:**
1. Write plot code FIRST to `scripts/stage8_viz/{step}_{plot-name}.py`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

**See:**
- `agent_reference/02_WORKFLOW_STAGES.md` — Stage 8 (Visualization)

The examples below show Plotly syntax. In research workflows, wrap them in scripts following the file-first pattern.

---

## Quick Reference

### Essential Imports

```python
import plotly.express as px          # High-level API
import plotly.graph_objects as go    # Low-level API
from plotly.subplots import make_subplots  # For subplots
import plotly.io as pio              # For export/config
```

### Plotly Express Pattern

```python
import plotly.express as px

fig = px.scatter(df, x="col_x", y="col_y", color="category")
fig.show()
```

### Graph Objects Pattern

```python
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(x=x_data, y=y_data, mode="markers"))
fig.update_layout(title="My Plot")
fig.show()
```

### Common px Functions

| Function | Chart Type |
|----------|------------|
| `px.scatter()` | Scatter plot |
| `px.line()` | Line chart |
| `px.bar()` | Bar chart |
| `px.histogram()` | Histogram |
| `px.box()` | Box plot |
| `px.violin()` | Violin plot |
| `px.imshow()` | Heatmap/Image |
| `px.pie()` | Pie chart |

### Common go Trace Types

| Trace | Use Case |
|-------|----------|
| `go.Scatter` | Points, lines, or both |
| `go.Bar` | Bar charts |
| `go.Histogram` | Histograms |
| `go.Box` | Box plots |
| `go.Heatmap` | Heatmaps |
| `go.Pie` | Pie charts |

### Saving Plots

```python
# Interactive HTML
fig.write_html("plot.html")

# Static image (requires kaleido)
fig.write_image("plot.png")
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Installation | `./references/quickstart.md` |
| px vs go | `./references/quickstart.md` |
| Built-in datasets | `./references/quickstart.md` |
| Scatter plots | `./references/charts.md` |
| Line charts | `./references/charts.md` |
| Bar charts | `./references/charts.md` |
| Histograms | `./references/charts.md` |
| Box plots | `./references/charts.md` |
| Other chart types | `./references/charts.md` |
| Faceting | `./references/subplots-facets.md` |
| make_subplots | `./references/subplots-facets.md` |
| Templates/Themes | `./references/styling.md` |
| Colors | `./references/styling.md` |
| Layout customization | `./references/styling.md` |
| Hover customization | `./references/styling.md` |
| HTML export | `./references/export.md` |
| Image export | `./references/export.md` |
| JSON export | `./references/export.md` |
| Common errors | `./references/gotchas.md` |
| Performance | `./references/gotchas.md` |
| Best practices | `./references/gotchas.md` |
