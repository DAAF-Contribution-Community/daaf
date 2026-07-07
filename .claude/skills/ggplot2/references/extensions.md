# Extensions: patchwork, ggrepel, ggridges, ggdist

Extension packages that enhance ggplot2 for common research visualization needs.
All operate on standard ggplot objects and compose with `+`.

## patchwork: Plot Composition

Combine multiple ggplot2 plots into a single figure using arithmetic operators.

```r
library(patchwork)
```

### Basic Operators

| Operator | Layout | Example |
|----------|--------|---------|
| `+` | Auto-layout (wraps) | `p1 + p2 + p3` |
| `\|` | Side by side | `p1 \| p2` |
| `/` | Stacked vertically | `p1 / p2` |

```r
# Side by side
p1 | p2

# Stacked
p1 / p2

# Complex layout: two on top, one on bottom
(p1 | p2) / p3

# Three across, one below
(p1 | p2 | p3) / p4
```

### Layout Control

```r
# Custom grid
p1 + p2 + p3 + plot_layout(ncol = 2)

# Unequal widths
p1 + p2 + plot_layout(widths = c(2, 1))

# Unequal heights
p1 / p2 + plot_layout(heights = c(3, 1))

# Collect guides (merge identical legends)
p1 + p2 + plot_layout(guides = "collect")

# Collect axes (remove duplicate axes)
p1 + p2 + plot_layout(axes = "collect")

# Collect axis titles
p1 + p2 + plot_layout(axis_titles = "collect")
```

### Annotations

```r
p1 + p2 + p3 +
  plot_annotation(
    title = "Combined Figure",
    subtitle = "Three-panel analysis",
    caption = "Source: CCD 2021-22",
    tag_levels = "A"    # Auto-tag: A, B, C
  )
```

Tag level options: `"A"` (uppercase), `"a"` (lowercase), `"1"` (numeric),
`"i"` (roman), `"I"` (Roman).

### Nested Layouts

```r
# Nest a patchwork explicitly
layout <- (p1 | p2) / nest(p3 | p4 | p5)
```

### free() for Unaligned Panels

When a plot should not align with the rest:

```r
# Free the panel alignment
p1 | free(p2)

# Free specific sides (1.3.0+)
p1 | free(p2, type = "panel", side = "l")
```

### Empty Panels (Spacers)

```r
# Insert empty space
p1 + plot_spacer() + p2 + plot_layout(ncol = 3)
```

### Non-ggplot Objects

```r
# Tables (gt objects, 1.3.0+)
library(gt)
tbl <- gt(summary_df)
p1 | wrap_table(tbl)

# Arbitrary grobs
p1 + wrap_elements(grid::textGrob("Custom text"))
```

### Complete patchwork Example

```r
library(ggplot2)
library(patchwork)

p1 <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() + geom_smooth(method = "lm") +
  labs(title = "Weight vs MPG") + theme_minimal()

p2 <- ggplot(mtcars, aes(x = factor(cyl), y = mpg)) +
  geom_boxplot() +
  labs(title = "MPG by Cylinders") + theme_minimal()

p3 <- ggplot(mtcars, aes(x = mpg)) +
  geom_histogram(bins = 15) +
  labs(title = "MPG Distribution") + theme_minimal()

combined <- (p1 | p2) / p3 +
  plot_annotation(
    title = "Motor Trend Car Analysis",
    tag_levels = "A"
  ) +
  plot_layout(heights = c(2, 1))

ggsave("combined_figure.png", combined, width = 12, height = 10, dpi = 300)
```

### Comparison: patchwork vs plotnine Composition

| patchwork (R) | plotnine (Python 0.15+) |
|---------------|------------------------|
| `p1 \| p2` | `p1 \| p2` |
| `p1 / p2` | `p1 / p2` |
| `(p1 \| p2) / p3` | `(p1 \| p2) / p3` |
| `plot_layout(guides = "collect")` | Not available |
| `plot_annotation(tag_levels = "A")` | Not available |
| `free(p2)` | Not available |

plotnine 0.15+ adopted patchwork's operators but does not yet support the full
annotation and layout control API.

---

## ggrepel: Non-Overlapping Labels

Automatically position text labels to avoid overlaps. Drop-in replacement for
`geom_text()` and `geom_label()`.

```r
library(ggrepel)
```

### geom_text_repel()

```r
ggplot(df, aes(x = x, y = y, label = name)) +
  geom_point() +
  geom_text_repel()
```

### geom_label_repel()

```r
ggplot(df, aes(x = x, y = y, label = name)) +
  geom_point() +
  geom_label_repel()
```

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max.overlaps` | Max overlapping labels before giving up | 10 |
| `force` | Repulsion force | 1 |
| `force_pull` | Attraction to data point | 1 |
| `nudge_x`, `nudge_y` | Initial offset | 0 |
| `box.padding` | Padding around label | 0.25 |
| `point.padding` | Padding around data point | 0 |
| `min.segment.length` | Min length of connector line | 0.5 |
| `segment.color` | Connector line color | "grey50" |
| `segment.size` | Connector line width | 0.5 |
| `seed` | Random seed (reproducible placement) | NA |
| `direction` | Repel direction: "both", "x", "y" | "both" |

```r
# Label only some points (e.g., top 5)
top5 <- head(df[order(-df$value), ], 5)

ggplot(df, aes(x = x, y = y)) +
  geom_point(color = "grey60") +
  geom_point(data = top5, color = "red", size = 3) +
  geom_text_repel(
    data = top5,
    aes(label = name),
    max.overlaps = 20,
    seed = 42
  )
```

### Tips

- Set `seed` for reproducible label placement across runs
- Use `max.overlaps = Inf` to always show all labels (may be messy)
- Filter to important points rather than labeling everything
- Use `direction = "y"` for horizontal comparisons
- Combine with `nudge_x`/`nudge_y` for consistent offset direction

### Comparison: ggrepel vs plotnine

plotnine does not have `geom_text_repel()`. Workarounds in Python:
- Use `geom_text()` with `position_nudge()` (manual offset, no collision avoidance)
- Use the `adjustText` Python package to post-process matplotlib text objects

ggrepel is a major advantage of the R ggplot2 ecosystem for label-heavy figures.

---

## ggridges: Ridgeline Plots

Density ridgeline (joy) plots for comparing distributions across groups.

```r
library(ggridges)
```

### geom_density_ridges()

```r
ggplot(df, aes(x = value, y = category, fill = category)) +
  geom_density_ridges(alpha = 0.7)
```

### Key Variants

| Geom | Description |
|------|-------------|
| `geom_density_ridges()` | Density ridgelines |
| `geom_density_ridges2()` | Closed polygons (filled to baseline) |
| `geom_ridgeline()` | Pre-computed height values |
| `geom_density_ridges_gradient()` | Color gradient fill along x |

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `scale` | Overlap scaling (> 1 = more overlap) | 1 |
| `rel_min_height` | Minimum height to draw (trim tails) | 0 |
| `bandwidth` | Density bandwidth | auto |
| `quantile_lines` | Show quantile lines | FALSE |
| `quantiles` | Which quantiles to show | 2 (median) |
| `jittered_points` | Show data points | FALSE |

```r
# Overlapping ridgelines with quantile lines
ggplot(df, aes(x = value, y = category, fill = category)) +
  geom_density_ridges(
    scale = 1.5,
    rel_min_height = 0.01,
    quantile_lines = TRUE,
    quantiles = 2
  ) +
  theme_ridges() +
  theme(legend.position = "none")
```

### With Data Points

```r
ggplot(df, aes(x = value, y = category)) +
  geom_density_ridges(
    jittered_points = TRUE,
    position = position_points_jitter(width = 0.05, height = 0),
    point_shape = "|",
    point_size = 2,
    alpha = 0.7
  )
```

### theme_ridges()

A theme optimized for ridgeline plots:

```r
theme_ridges(font_size = 14, grid = FALSE)
```

### Comparison: ggridges vs plotnine

plotnine does not include ridgeline geoms. Python workarounds:
- `geom_violin()` with `coord_flip()` (rough approximation)
- `ridgeplot` Python package
- Manual offset `geom_density()` layers

ggridges is another significant advantage of the R ecosystem.

---

## ggdist: Distribution Visualization

Visualize distributions, uncertainty, and frequencies with a unified API.

```r
library(ggdist)
```

### Key Stats and Geoms

| Function | Description |
|----------|-------------|
| `stat_halfeye()` | Half-violin + interval (default) |
| `stat_eye()` | Full violin + interval |
| `stat_dots()` | Quantile dot plots |
| `stat_dotsinterval()` | Dots + interval |
| `stat_slab()` | Density slab only |
| `stat_interval()` | Interval only |
| `stat_pointinterval()` | Point + interval |
| `stat_gradientinterval()` | Gradient-filled interval |

### stat_halfeye() -- The Default

```r
ggplot(df, aes(x = category, y = value)) +
  stat_halfeye()
```

This draws a half-density (slab) with a point-interval summary underneath --
the "rain cloud" pattern in one call.

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `.width` | Interval width(s) | c(0.66, 0.95) |
| `point_interval` | Summary function | median_qi |
| `slab_type` | "pdf", "cdf", "ccdf", "histogram" | "pdf" |
| `normalize` | Normalization: "all", "panels", "xy", "groups", "none" | "all" |
| `fill_type` | Fill behavior: "segments", "gradient" | "segments" |
| `side` | Slab side: "topright", "bottomleft", "both" | "topright" |

```r
# Rain cloud plot
ggplot(df, aes(x = category, y = value)) +
  stat_halfeye(
    .width = c(0.66, 0.95),
    point_interval = median_qi,
    slab_type = "pdf"
  )

# With data points below
ggplot(df, aes(x = category, y = value)) +
  stat_halfeye(side = "right", adjust = 0.5) +
  stat_dots(side = "left", dotsize = 0.5)
```

### stat_dots() -- Quantile Dot Plots

```r
ggplot(df, aes(x = category, y = value)) +
  stat_dots(
    quantiles = 50,     # Number of dots
    side = "both"
  )
```

### Interval Specifications

| Summary | Meaning |
|---------|---------|
| `median_qi` | Median + quantile interval |
| `mean_qi` | Mean + quantile interval |
| `mode_qi` | Mode + quantile interval |
| `median_hdi` | Median + highest-density interval |
| `mean_hdi` | Mean + highest-density interval |

```r
# 80% and 95% highest-density intervals
stat_halfeye(.width = c(0.80, 0.95), point_interval = median_hdi)
```

### Posterior / Uncertainty Visualization

ggdist is designed for Bayesian posterior distributions but works well for any
group comparison:

```r
ggplot(df, aes(x = group, y = value, fill = group)) +
  stat_halfeye(
    .width = c(0.66, 0.95),
    point_interval = median_qi,
    slab_alpha = 0.6
  ) +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "Distribution Comparison") +
  theme_minimal() +
  theme(legend.position = "none")
```

### Complete ggdist Example

```r
library(ggplot2)
library(ggdist)

ggplot(iris, aes(x = Species, y = Sepal.Length, fill = Species)) +
  stat_halfeye(
    adjust = 0.5,
    width = 0.6,
    .width = c(0.5, 0.89),
    point_interval = median_qi
  ) +
  scale_fill_brewer(palette = "Pastel1") +
  labs(
    title = "Sepal Length by Species",
    y = "Sepal Length (cm)"
  ) +
  theme_minimal() +
  theme(legend.position = "none")
```

### Comparison: ggdist vs Python

Python does not have a direct ggdist equivalent. Workarounds:
- `seaborn.violinplot()` for basic violin + box
- Manual construction with plotnine `geom_violin()` + `geom_pointrange()`
- `arviz` for Bayesian posterior visualization

ggdist provides the most polished distribution visualization in either ecosystem.
