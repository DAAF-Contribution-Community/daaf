# Geoms (Geometric Objects)

Geoms determine how data is visually represented. Each geom has required and
optional aesthetics. In ggplot2 4.0+, use `linewidth` (not `size`) for all
line-based geoms.

## Geoms by Use Case

### Points and Scatter

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_point()` | Scatter plot | x, y |
| `geom_jitter()` | Jittered points | x, y |
| `geom_count()` | Count overlapping points | x, y |

```r
# Basic scatter
ggplot(df, aes(x = x, y = y)) +
  geom_point()

# With jitter for overplotting
ggplot(df, aes(x = x, y = y)) +
  geom_jitter(width = 0.2)

# Size by count
ggplot(df, aes(x = x, y = y)) +
  geom_count()
```

### Lines and Paths

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_line()` | Connect points (ordered by x) | x, y |
| `geom_path()` | Connect points (data order) | x, y |
| `geom_step()` | Step line | x, y |
| `geom_segment()` | Line segment | x, y, xend, yend |

```r
# Line plot
ggplot(df, aes(x = date, y = value)) +
  geom_line()

# Grouped lines
ggplot(df, aes(x = date, y = value, color = group)) +
  geom_line(linewidth = 0.8)

# Step function
ggplot(df, aes(x = date, y = value)) +
  geom_step(linewidth = 0.7)
```

### Bars

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_bar()` | Bar heights from counts | x |
| `geom_col()` | Bar heights from values | x, y |

```r
# Count occurrences
ggplot(df, aes(x = category)) +
  geom_bar()

# Use existing values
ggplot(df, aes(x = category, y = value)) +
  geom_col()

# Stacked bars
ggplot(df, aes(x = category, fill = group)) +
  geom_bar()

# Dodged (side-by-side)
ggplot(df, aes(x = category, fill = group)) +
  geom_bar(position = "dodge")

# Horizontal bars (modern approach, no coord_flip needed)
ggplot(df, aes(y = category, x = value)) +
  geom_col()
```

### Distributions

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_histogram()` | Histogram | x |
| `geom_density()` | Density curve | x |
| `geom_freqpoly()` | Frequency polygon | x |
| `geom_dotplot()` | Dot plot | x |

```r
# Histogram
ggplot(df, aes(x = value)) +
  geom_histogram(bins = 30)

# Density
ggplot(df, aes(x = value)) +
  geom_density()

# Overlaid densities
ggplot(df, aes(x = value, fill = group)) +
  geom_density(alpha = 0.5)

# Histogram with density overlay
ggplot(df, aes(x = value)) +
  geom_histogram(aes(y = after_stat(density)), bins = 30) +
  geom_density(color = "red", linewidth = 1)
```

### Box and Violin

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_boxplot()` | Box-and-whisker | x, y |
| `geom_violin()` | Violin plot | x, y |

```r
# Boxplot by group
ggplot(df, aes(x = category, y = value)) +
  geom_boxplot()

# Violin plot
ggplot(df, aes(x = category, y = value)) +
  geom_violin()

# Violin with embedded boxplot
ggplot(df, aes(x = category, y = value)) +
  geom_violin() +
  geom_boxplot(width = 0.1)

# Horizontal boxplot (no coord_flip needed)
ggplot(df, aes(y = category, x = value)) +
  geom_boxplot()
```

Note: In 4.0, `geom_violin(draw_quantiles = ...)` is deprecated. Use
`stat_ydensity(quantiles = ...)` instead.

### Area and Ribbon

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_area()` | Area under line | x, y |
| `geom_ribbon()` | Ribbon with ymin/ymax | x, ymin, ymax |

```r
# Stacked area
ggplot(df, aes(x = date, y = value, fill = group)) +
  geom_area()

# Confidence band
ggplot(df, aes(x = x, ymin = lower, ymax = upper)) +
  geom_ribbon(alpha = 0.3)

# Line with confidence band
ggplot(df, aes(x = x, y = estimate)) +
  geom_ribbon(aes(ymin = lower, ymax = upper), alpha = 0.2) +
  geom_line(linewidth = 1)
```

### Smoothing and Trends

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_smooth()` | Smoothed conditional mean | x, y |

```r
# Default: loess for n<1000, gam otherwise
ggplot(df, aes(x = x, y = y)) +
  geom_point() +
  geom_smooth()

# Linear regression
ggplot(df, aes(x = x, y = y)) +
  geom_point() +
  geom_smooth(method = "lm")

# Without confidence interval
ggplot(df, aes(x = x, y = y)) +
  geom_smooth(se = FALSE)

# By group
ggplot(df, aes(x = x, y = y, color = group)) +
  geom_point() +
  geom_smooth(method = "lm")
```

### Error Bars

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_errorbar()` | Error bars (vertical or horizontal) | x, ymin, ymax |
| `geom_pointrange()` | Point with range | x, y, ymin, ymax |
| `geom_linerange()` | Vertical line | x, ymin, ymax |
| `geom_crossbar()` | Crossbar | x, y, ymin, ymax |

```r
# Error bars
ggplot(df, aes(x = category, y = mean, ymin = lower, ymax = upper)) +
  geom_errorbar(width = 0.2)

# Point with range
ggplot(df, aes(x = category, y = mean, ymin = lower, ymax = upper)) +
  geom_pointrange()

# Horizontal error bars (4.0: use orientation, not geom_errorbarh)
ggplot(df, aes(y = category, x = mean, xmin = lower, xmax = upper)) +
  geom_errorbar(orientation = "y", width = 0.2)
```

Note: `geom_errorbarh()` is deprecated in 4.0. Use
`geom_errorbar(orientation = "y")` instead.

### Text and Labels

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_text()` | Text labels | x, y, label |
| `geom_label()` | Text with background box | x, y, label |

```r
# Add labels
ggplot(df, aes(x = x, y = y, label = name)) +
  geom_point() +
  geom_text()

# Adjust position
ggplot(df, aes(x = x, y = y, label = name)) +
  geom_point() +
  geom_text(nudge_y = 0.5, size = 3)

# With background box
ggplot(df, aes(x = x, y = y, label = name)) +
  geom_point() +
  geom_label(size = 3)
```

For non-overlapping labels, use `ggrepel::geom_text_repel()` -- see
`extensions.md`.

### Reference Lines

| Geom | Description | Key parameter |
|------|-------------|---------------|
| `geom_hline()` | Horizontal line | yintercept |
| `geom_vline()` | Vertical line | xintercept |
| `geom_abline()` | Line by slope/intercept | slope, intercept |

```r
ggplot(df, aes(x = x, y = y)) +
  geom_point() +
  geom_hline(yintercept = 0, linetype = "dashed") +
  geom_vline(xintercept = 5, color = "red", linewidth = 0.5)
```

### Tiles and Heatmaps

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_tile()` | Rectangle by center | x, y |
| `geom_raster()` | Fast tiles (equal size) | x, y |
| `geom_rect()` | Rectangle by corners | xmin, xmax, ymin, ymax |

```r
# Heatmap
ggplot(df, aes(x = x, y = y, fill = value)) +
  geom_tile() +
  scale_fill_viridis_c()

# Correlation heatmap
ggplot(corr_long, aes(x = var1, y = var2, fill = correlation)) +
  geom_tile(color = "white") +
  geom_text(aes(label = round(correlation, 2)), size = 3) +
  scale_fill_gradient2(low = "blue", mid = "white", high = "red", midpoint = 0)
```

### 2D Density

| Geom | Description | Required aes |
|------|-------------|--------------|
| `geom_bin_2d()` | 2D histogram | x, y |
| `geom_density_2d()` | 2D density contours | x, y |
| `geom_density_2d_filled()` | Filled 2D density | x, y |

```r
# 2D bins (heatmap)
ggplot(df, aes(x = x, y = y)) +
  geom_bin_2d()

# Density contours over scatter
ggplot(df, aes(x = x, y = y)) +
  geom_point(alpha = 0.3) +
  geom_density_2d()
```

## Common Geom Parameters (4.0+)

| Parameter | Description | Applies to | Example |
|-----------|-------------|------------|---------|
| `color` | Outline/line color | All | `color = "blue"` |
| `fill` | Fill color | Bars, areas, polygons | `fill = "red"` |
| `alpha` | Transparency (0-1) | All | `alpha = 0.5` |
| `size` | **Point** size only | Points | `size = 3` |
| `linewidth` | **Line** width | Lines, borders | `linewidth = 1` |
| `linetype` | Line style | Lines | `linetype = "dashed"` |
| `shape` | Point shape | Points | `shape = 17` |
| `position` | Position adjustment | All | `position = "dodge"` |

## Position Adjustments

| Position | Description |
|----------|-------------|
| `"identity"` | No adjustment (default for most geoms) |
| `"dodge"` | Side by side |
| `"dodge2"` | Side by side preserving width |
| `"stack"` | Stack on top (default for area/bar) |
| `"fill"` | Stack and normalize to 100% |
| `"jitter"` | Random noise |

```r
# Dodged bars with custom width
geom_bar(position = position_dodge(width = 0.8))

# Stacked area
geom_area(position = "stack")

# Jitter with control
geom_point(position = position_jitter(width = 0.2, height = 0))

# Nudge labels away from points
geom_text(position = position_nudge(y = 0.5))
```
