---
name: ggplot2
description: |
  R visualization with ggplot2 grammar of graphics. Geoms, aesthetics, scales,
  facets, coords, themes. Extensions: patchwork, ggrepel, ggridges, ggdist.
  Use when execution language is R. Python equivalent: plotnine.
autoload: never
metadata:
  audience: research-coders
  domain: r-library
  library-version: "ggplot2 4.0.2"
  skill-last-updated: "2026-05-08"
  tags: ["r", "visualization", "ggplot2", "grammar-of-graphics"]
---

# ggplot2 Skill

R visualization with the grammar of graphics via ggplot2 4.0.x. Covers geoms
(point, line, bar, histogram, boxplot, violin, ribbon, tile, text), aesthetics,
scales, coordinates, facets, and themes. Extension packages: patchwork (multi-panel
composition), ggrepel (non-overlapping text labels), ggridges (ridgeline density
plots), ggdist (distribution visualization). Use when execution language is R and
static publication-quality figures are needed. Python equivalent: plotnine (which
ports ggplot2's grammar to Python). For interactive R charts, use plotly-r instead.

## What is ggplot2?

ggplot2 is **the** grammar of graphics implementation for R:
- **Declarative**: Describe what you want, not how to draw it
- **Layered**: Build plots by adding components with `+`
- **The original**: plotnine (Python) is a port of ggplot2, not the reverse
- **Publication-ready**: Extensive themes and customization for polished output
- **Extensible**: Hundreds of extension packages (patchwork, ggrepel, ggridges, ggdist)

## Version Notes: ggplot2 4.0.x (Breaking Changes from 3.x)

ggplot2 4.0.0 is a major release with significant breaking changes. Code written
for 3.x may need updates.

### Critical: `linewidth` vs `size` for Lines

The `size` aesthetic for line-based geoms was deprecated in 3.4.0. In 4.0.x:
- `geom_line(size = 1)` still works but throws a deprecation warning
- `geom_bar(size = 1)` / `geom_col(size = 1)` **silently ignores** `size` (fallback removed)
- **Always use `linewidth`** for lines, borders, and outlines
- `size` remains correct for points only (`geom_point(size = 3)`)

```r
# WRONG (deprecated / ignored in 4.0)
geom_line(size = 1)
geom_bar(size = 0.5)

# CORRECT (4.0+)
geom_line(linewidth = 1)
geom_bar(linewidth = 0.5)
```

### Other 4.0.x Breaking Changes

| Change | 3.x Behavior | 4.0.x Behavior |
|--------|-------------|----------------|
| S7 internals | S3 classes | S7 classes (affects extension authors, not users) |
| `coord_trans()` | Primary name | Renamed to `coord_transform()`; `coord_trans()` still works |
| `theme_set()` etc. | Primary names | Renamed: `set_theme()`, `get_theme()`, `update_theme()`, `replace_theme()`; old names still work |
| `geom_errorbarh()` | Primary | Deprecated; use `geom_errorbar(orientation = "y")` |
| `geom_violin(draw_quantiles)` | Geom parameter | Deprecated; use `geom_violin(quantiles = c(...), quantile.linetype = 1)` — quantiles are hidden by default in 4.0, so `quantile.linetype` (a non-`0` value) is required to display them |
| `fatten` argument | In boxplot/crossbar/pointrange | Deprecated |
| `borders()` | Active | Deprecated; use `annotation_borders()` |
| Pre-3.0 deprecations | Warnings | Now errors |
| Theme geom defaults | Via `update_geom_defaults()` | New `theme(geom = element_geom(...))` for global defaults |
| Binning defaults | Old boundary selection | Better adherence to `nbin` argument; may change existing plots |
| `mgcv`, `tibble` | Imported | Moved to Suggests (install separately if needed) |

### New 4.0.x Features

- `theme(geom = element_geom(...))` for global geom aesthetic defaults
- `from_theme()` inside `aes()` to reference theme defaults
- `stat_connect()` and `stat_manual()` new stats
- `theme(panel.widths, panel.heights)` for panel sizing
- `labs(dictionary = ...)` for label mapping by variable name
- `ggsave()` can write multi-page PDFs from a list of plots
- `theme_*(ink, paper, accent)` arguments for foreground/background/highlight colors

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Basic ggplot pattern, ggsave, essential setup | Starting out or quick reminder |
| `geoms.md` | All major geoms with examples | Choosing chart types |
| `scales.md` | Scales, axes, color palettes, labels, the scales package | Axis/color/label formatting |
| `facets.md` | facet_wrap, facet_grid, labellers, spacing | Multi-panel layouts |
| `themes.md` | Built-in themes, custom theme(), publication-ready styling | Styling and polish |
| `extensions.md` | patchwork, ggrepel, ggridges, ggdist | Multi-panel, labels, distributions |
| `gotchas.md` | 4.0 migration, common mistakes, factor ordering, save tips | Debugging or reviewing |

### Reading Order

1. **Quick plot?** Start with `quickstart.md`
2. **Which geom?** Check `geoms.md`
3. **Customize scales/axes?** Read `scales.md`
4. **Multi-panel?** Read `facets.md`
5. **Publication polish?** Read `themes.md`
6. **Extensions?** Read `extensions.md`
7. **Trouble?** Check `gotchas.md`

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `plotnine` | Python equivalent (plotnine ports ggplot2 to Python) |
| `tidyverse` | Data preparation -- tidy data feeds into ggplot2 pipelines |
| `plotly-r` | Interactive R charts (use when interactivity needed) |
| `gt` | Publication-quality tables (use for tabular output, not charts) |
| `r-python-translation` | Cross-language visualization translation |
| `data-scientist` | Method selection and visualization design guidance |

## Quick Decision Trees

### "What chart type do I need?"

```
What are you visualizing?
├─ Relationship (x vs y)
│   ├─ Continuous x, continuous y → geom_point() + geom_smooth()
│   ├─ Time series → geom_line()
│   └─ With error/uncertainty → geom_pointrange() or geom_ribbon()
├─ Distribution
│   ├─ One variable → geom_histogram() or geom_density()
│   ├─ By group (few groups) → geom_boxplot() or geom_violin()
│   ├─ By group (many groups) → ggridges::geom_density_ridges()
│   └─ Full distribution detail → ggdist::stat_halfeye()
├─ Comparison
│   ├─ Counts → geom_bar()
│   ├─ Values → geom_col()
│   └─ Grouped → geom_col(position = "dodge")
├─ Composition
│   ├─ Parts of whole → geom_col(position = "fill")
│   └─ Over time → geom_area(position = "stack")
├─ Heatmap / tile → geom_tile() or geom_raster()
└─ Multiple plots → patchwork (p1 + p2) / p3
```

### "How do I save this plot?"

```
Saving a plot?
├─ To PNG (default for DAAF) → ggsave("file.png", p, width = 10, height = 8, dpi = 300)
├─ To PDF → ggsave("file.pdf", p, width = 10, height = 8)
├─ To SVG → ggsave("file.svg", p, width = 10, height = 8)
├─ Multiple plots to one PDF → ggsave("file.pdf", list(p1, p2, p3))
└─ Temp file (smoke tests) → ggsave(tempfile(fileext = ".png"), p)
```

## File-First Execution in Research Workflows

In DAAF research pipelines, all visualizations are generated through **script
files** in `scripts/stage8_analysis/`, not interactively. This ensures auditability
and reproducibility.

**The pattern:**
1. Write plot code to `scripts/stage8_analysis/{step}_{plot-name}.R`
2. Execute via `bash {BASE_DIR}/scripts/run_with_capture.sh {script_path}`
3. Output gets appended to the script as comments
4. Use `ggsave()` to save plots to the project output directory

See `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first
execution protocol.

## Quick Reference

### Essential Setup

```r
library(ggplot2)
library(scales)       # label_comma(), label_percent(), etc.
library(patchwork)    # plot composition: p1 + p2, p1 / p2
library(ggrepel)      # geom_text_repel(), geom_label_repel()
library(ggridges)     # geom_density_ridges()
library(ggdist)       # stat_halfeye(), stat_dots()
```

### Basic Plot Pattern

```r
p <- ggplot(df, aes(x = col_x, y = col_y)) +
  geom_point() +
  labs(title = "Title", x = "X Label", y = "Y Label") +
  theme_minimal()

ggsave("output.png", p, width = 10, height = 8, dpi = 300)
```

### Common Geoms

| Geom | Use Case |
|------|----------|
| `geom_point()` | Scatter plots |
| `geom_line()` | Line plots / time series |
| `geom_bar()` | Count bars (stat = "count") |
| `geom_col()` | Value bars (stat = "identity") |
| `geom_histogram()` | Distributions |
| `geom_density()` | Density curves |
| `geom_boxplot()` | Box-and-whisker |
| `geom_violin()` | Violin plots |
| `geom_smooth()` | Trend lines |
| `geom_tile()` | Heatmaps |

### Common Aesthetics

| Aesthetic | Controls | Use `size` or `linewidth`? |
|-----------|----------|---------------------------|
| `x`, `y` | Position | N/A |
| `color` | Point/line color | N/A |
| `fill` | Area fill color | N/A |
| `size` | **Point** size only (4.0+) | `size` for points |
| `linewidth` | **Line** width (4.0+) | `linewidth` for lines |
| `shape` | Point shape | N/A |
| `alpha` | Transparency | N/A |
| `linetype` | Line pattern | N/A |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Basic plot pattern | `./references/quickstart.md` |
| ggsave() parameters | `./references/quickstart.md` |
| Data requirements | `./references/quickstart.md` |
| Scatter, line, bar, area | `./references/geoms.md` |
| Histogram, density, boxplot | `./references/geoms.md` |
| Smoothing, error bars | `./references/geoms.md` |
| Heatmaps, tiles, text | `./references/geoms.md` |
| Position adjustments | `./references/geoms.md` |
| Continuous/discrete scales | `./references/scales.md` |
| Color palettes (Brewer, viridis) | `./references/scales.md` |
| Axis labels and formatting | `./references/scales.md` |
| scales package helpers | `./references/scales.md` |
| facet_wrap, facet_grid | `./references/facets.md` |
| Free scales, labellers | `./references/facets.md` |
| Built-in themes | `./references/themes.md` |
| Custom theme() elements | `./references/themes.md` |
| Publication-ready themes | `./references/themes.md` |
| patchwork composition | `./references/extensions.md` |
| ggrepel labels | `./references/extensions.md` |
| ggridges ridgeline plots | `./references/extensions.md` |
| ggdist distribution viz | `./references/extensions.md` |
| linewidth vs size migration | `./references/gotchas.md` |
| 4.0 breaking changes | `./references/gotchas.md` |
| Factor ordering | `./references/gotchas.md` |
| Save resolution/dimensions | `./references/gotchas.md` |
| Common errors | `./references/gotchas.md` |

## Citation

When ggplot2 is used as a primary visualization tool, include in the report's
Software & Tools references:

> Wickham, H. (2016). *ggplot2: Elegant Graphics for Data Analysis* (2nd ed.). Springer-Verlag New York. https://ggplot2.tidyverse.org

**Cite when:** ggplot2 produces figures included in the report.
**Do not cite when:** Only used for quick exploratory plots not included in deliverables.
