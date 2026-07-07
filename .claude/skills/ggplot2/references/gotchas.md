# Gotchas and Common Mistakes

## ggplot2 4.0.x Migration Guide

### linewidth vs size (Critical)

The `size` aesthetic for line-based geoms was deprecated in 3.4.0. In 4.0:

**For geom_line, geom_path, geom_step, geom_segment, geom_hline, geom_vline,
geom_abline, geom_smooth, geom_ribbon (outline):**
- `size` throws a deprecation warning
- Use `linewidth` instead

**For geom_bar, geom_col, geom_boxplot, geom_crossbar (border):**
- `size` is silently **ignored** (fallback removed in 4.0)
- Use `linewidth` for border width

**For geom_point, geom_jitter, geom_count:**
- `size` remains correct for point size
- Do NOT use `linewidth` for points

**For element_line() and element_rect() in themes:**
- Use `linewidth`, not `size`

```r
# WRONG (4.0)
geom_line(size = 1)                    # Warning
geom_bar(size = 0.5)                   # Silently ignored
element_line(size = 0.5)               # Deprecated

# CORRECT (4.0)
geom_line(linewidth = 1)
geom_bar(linewidth = 0.5)
element_line(linewidth = 0.5)
geom_point(size = 3)                   # size is correct for points
```

### Renamed Functions

| 4.0 Name (preferred) | Old Name (still works) | Type |
|----------------------|----------------------|------|
| `coord_transform()` | `coord_trans()` | Coord |
| `set_theme()` | `theme_set()` | Theme |
| `get_theme()` | `theme_get()` | Theme |
| `update_theme()` | `theme_update()` | Theme |
| `replace_theme()` | `theme_replace()` | Theme |
| `get_last_plot()` | `last_plot()` | Utility |
| `get_layer_data()` | `layer_data()` | Utility |
| `annotation_borders()` | `borders()` | Annotation |

### Deprecated Features

| Deprecated | Replacement |
|-----------|-------------|
| `geom_errorbarh()` | `geom_errorbar(orientation = "y")` |
| `geom_violin(draw_quantiles = ...)` | `geom_violin(quantiles = c(...), quantile.linetype = 1)` — in 4.0 quantiles are hidden unless `quantile.linetype` is set to a non-`0` value |
| `fatten` in boxplot/crossbar/pointrange | Use specific styling arguments |
| `facet_wrap(as.table = ...)` | `facet_wrap(dir = ...)` |
| Pre-3.0 deprecated functions | Now throw errors (not just warnings) |

### New Dependencies

In 4.0, `mgcv` and `tibble` moved from Imports to Suggests. If your code uses
`geom_smooth(method = "gam")`, install mgcv separately:

```r
install.packages("mgcv")
```

## Common Errors

### Literal vs Mapped Color

```r
# WRONG: looks for a column named "blue"
aes(color = "blue")

# CORRECT: fixed color (outside aes)
geom_point(color = "blue")

# CORRECT: map to data column
aes(color = species)
```

### color vs fill

- **Points and lines**: use `color`
- **Bars, areas, polygons**: use `fill` (and optionally `color` for border)

```r
# Points -- color
geom_point(aes(color = group))

# Bars -- fill
geom_bar(aes(fill = group))

# Bars with both fill and border
geom_bar(aes(fill = group), color = "black", linewidth = 0.3)
```

### Missing Required Aesthetic

```
Error: geom_point requires the following missing aesthetics: x, y
```

Fix: ensure `aes()` provides all required aesthetics for the geom.

### Unexpected Grouping in geom_line

If `geom_line()` draws separate segments instead of a connected line:

```r
# Problem: implicit grouping from other aesthetics
ggplot(df, aes(x = date, y = value, color = "Series A")) +
  geom_line()  # Draws disconnected points

# Fix: explicit group
ggplot(df, aes(x = date, y = value, group = 1)) +
  geom_line(color = "steelblue")
```

When a categorical aesthetic is present (even as a fixed string in `aes()`),
ggplot2 groups by it. Use `group = 1` to force a single group.

### stat_count vs stat_identity

```r
# geom_bar() uses stat = "count" by default -- counts rows
ggplot(df, aes(x = category)) +
  geom_bar()

# geom_col() uses stat = "identity" -- uses y values directly
ggplot(df, aes(x = category, y = value)) +
  geom_col()

# Common error: providing y to geom_bar without stat = "identity"
# Fix: use geom_col() instead
```

### Factor Ordering for Categorical Axes

By default, categories appear in alphabetical order. Control order with:

```r
# Reorder by another variable (e.g., by mean value)
df$category <- reorder(df$category, df$value, FUN = mean)

# Or use forcats
library(forcats)
df$category <- fct_reorder(df$category, df$value)

# Manual order
df$category <- factor(df$category, levels = c("Low", "Medium", "High"))

# Reverse
df$category <- fct_rev(df$category)

# Reorder inside aes (quick)
aes(x = reorder(category, -value), y = value)
```

### coord_flip vs Orientation

Historically, horizontal bar charts required `coord_flip()`. In modern ggplot2,
use orientation directly:

```r
# Old approach (still works)
ggplot(df, aes(x = category, y = value)) +
  geom_col() +
  coord_flip()

# Modern approach (preferred in 4.0)
ggplot(df, aes(y = category, x = value)) +
  geom_col()
```

Mapping the categorical variable to `y` instead of `x` produces a horizontal
chart without `coord_flip()`.

### Overlapping Axis Labels

```r
# Rotate labels
theme(axis.text.x = element_text(angle = 45, hjust = 1))

# Or wrap with scales package
scale_x_discrete(labels = scales::label_wrap(15))

# Or use coord_flip / horizontal orientation for many categories
```

### Warning: Removed N rows containing non-finite values

This means your data contains `NA`, `Inf`, or `-Inf` in the plotted columns:

```r
# Check
sum(!is.finite(df$value))

# Filter before plotting
df_clean <- df[is.finite(df$value), ]

# Or suppress the warning if NAs are expected
ggplot(df, aes(x, y)) +
  geom_point(na.rm = TRUE)
```

### Warning: Ignoring unknown aesthetics

You passed an aesthetic the geom does not understand:

```r
# WRONG: geom_bar doesn't have a y aesthetic with stat = "count"
geom_bar(aes(y = value))

# RIGHT: use geom_col for pre-computed values
geom_col(aes(y = value))
```

## Saving Tips

### Resolution and Dimensions

```r
# Screen display (presentations)
ggsave("plot.png", p, width = 10, height = 8, dpi = 150)

# Print quality (papers, reports)
ggsave("plot.png", p, width = 10, height = 8, dpi = 300)

# High-res (posters, large prints)
ggsave("plot.png", p, width = 10, height = 8, dpi = 600)

# Vector (scales perfectly, larger file)
ggsave("plot.pdf", p, width = 10, height = 8)
```

### Text Sizing

When using `ggsave()`, text size appears relative to the output dimensions.
A `base_size = 12` looks different at `width = 5` vs `width = 15`:

- For wide plots (10+ inches): use `base_size = 14` or higher
- For narrow plots (< 6 inches): use `base_size = 10-12`
- For multi-panel (patchwork): use `base_size = 10-12` since panels are smaller

### Background Color

```r
# White background (default for PNG)
ggsave("plot.png", p, bg = "white")

# Transparent background
ggsave("plot.png", p, bg = "transparent")
```

### Multi-Page PDF (4.0 Feature)

```r
# Save multiple plots as pages
ggsave("all_plots.pdf", list(p1, p2, p3), width = 10, height = 8)
```

## Performance Tips

### Large Datasets

1. **Sample for exploration:**
   ```r
   ggplot(df[sample(nrow(df), 5000), ], aes(x, y)) + geom_point()
   ```

2. **Use `geom_bin_2d()` or `geom_hex()`** instead of `geom_point()` for
   millions of points.

3. **Use `geom_raster()`** instead of `geom_tile()` for regular grids (faster).

### Memory

For very large plots or many plots in a script:

```r
p <- ggplot(...) + geom_point()
ggsave("plot.png", p)
rm(p)
gc()  # Garbage collect if memory is tight
```

## ggplot2 vs plotnine Quick Syntax Reference

| Feature | ggplot2 (R) | plotnine (Python) |
|---------|-------------|-------------------|
| Column in aes | Bare names: `aes(x = wt)` | Strings: `aes(x="wt")` |
| Facet formula | `facet_wrap(~ var)` | `facet_wrap("var")` |
| Multi-line `+` | `+` at end of line works | Must wrap in `()` |
| Theme elements | Dots: `plot.title` | Underscores: `plot_title` |
| Bold text | `face = "bold"` | `weight = "bold"` |
| Saving | `ggsave("f.png", p)` | `p.save("f.png")` |
| factor in aes | `factor(cyl)` | `"factor(cyl)"` (string) |
| Named vectors | `c("A" = "red")` | `{"A": "red"}` (dict) |
| Boolean | `TRUE` / `FALSE` | `True` / `False` |
| Display | `print(p)` | `p.draw()` |
| NA handling | `na.rm = TRUE` | `na_rm = True` |
| Line width | `linewidth = 1` (4.0) | `size = 1` (plotnine 0.15) |

Note the last row: ggplot2 4.0 uses `linewidth` for lines while plotnine 0.15
still uses `size`. This is a key divergence that matters for R-to-Python
translation.
