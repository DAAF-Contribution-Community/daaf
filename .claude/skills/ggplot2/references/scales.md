# Scales, Axes, and Labels

Scales control how data values map to visual properties. The `scales` package
(loaded separately) provides label formatting helpers.

## Scale Naming Convention

```
scale_<aesthetic>_<type>()
```

Examples: `scale_x_continuous()`, `scale_color_brewer()`, `scale_fill_manual()`

## Position Scales

### Continuous

| Scale | Description |
|-------|-------------|
| `scale_x_continuous()` | Continuous x-axis |
| `scale_y_continuous()` | Continuous y-axis |
| `scale_x_log10()` | Log10 x-axis |
| `scale_y_log10()` | Log10 y-axis |
| `scale_x_sqrt()` | Square root x |
| `scale_x_reverse()` | Reverse direction |

```r
# Custom breaks and labels
scale_x_continuous(breaks = c(0, 5, 10), labels = c("Low", "Mid", "High"))

# Limit range (removes data outside range)
scale_x_continuous(limits = c(0, 100))

# Formatting with scales package
library(scales)
scale_y_continuous(labels = label_comma())
scale_y_continuous(labels = label_dollar())
scale_y_continuous(labels = label_percent())
```

### Discrete

| Scale | Description |
|-------|-------------|
| `scale_x_discrete()` | Categorical x-axis |
| `scale_y_discrete()` | Categorical y-axis |

```r
# Reorder categories
scale_x_discrete(limits = c("C", "B", "A"))

# Custom labels
scale_x_discrete(labels = c("a" = "Group A", "b" = "Group B"))
```

### Date and Time

| Scale | Description |
|-------|-------------|
| `scale_x_date()` | Date x-axis |
| `scale_x_datetime()` | Date-time x-axis |

```r
scale_x_date(date_labels = "%b %Y", date_breaks = "3 months")
scale_x_date(date_labels = "%Y", date_breaks = "1 year")
```

### Common date_labels Format Codes

| Code | Meaning | Example |
|------|---------|---------|
| `%Y` | 4-digit year | 2024 |
| `%y` | 2-digit year | 24 |
| `%m` | Month (01-12) | 03 |
| `%b` | Abbreviated month | Mar |
| `%B` | Full month | March |
| `%d` | Day (01-31) | 15 |

## Color and Fill Scales

### Discrete Colors

| Scale | Description |
|-------|-------------|
| `scale_color_brewer()` | ColorBrewer palettes |
| `scale_fill_brewer()` | ColorBrewer fills |
| `scale_color_manual()` | Custom colors |
| `scale_fill_manual()` | Custom fills |
| `scale_color_viridis_d()` | Viridis discrete |
| `scale_fill_viridis_d()` | Viridis discrete fills |

```r
# ColorBrewer palette
scale_color_brewer(palette = "Set1")
scale_fill_brewer(palette = "Blues")

# Manual colors
scale_color_manual(values = c("red", "blue", "green"))
scale_fill_manual(values = c("A" = "#FF0000", "B" = "#00FF00"))

# Viridis discrete
scale_color_viridis_d()
scale_fill_viridis_d(option = "plasma")
```

### ColorBrewer Palette Reference

| Type | Palettes |
|------|----------|
| Sequential | Blues, Greens, Oranges, Reds, Purples, Greys, YlOrRd, YlGnBu |
| Diverging | RdBu, RdYlBu, BrBG, PiYG, PRGn, RdYlGn, Spectral |
| Qualitative | Set1, Set2, Set3, Pastel1, Pastel2, Dark2, Paired, Accent |

### Continuous Colors

| Scale | Description |
|-------|-------------|
| `scale_color_gradient()` | Two-color gradient |
| `scale_color_gradient2()` | Diverging gradient |
| `scale_color_gradientn()` | Multi-color gradient |
| `scale_color_viridis_c()` | Viridis continuous |
| `scale_fill_viridis_c()` | Viridis continuous fill |
| `scale_color_distiller()` | ColorBrewer continuous |

```r
# Two-color gradient
scale_color_gradient(low = "white", high = "red")

# Diverging with midpoint
scale_color_gradient2(low = "blue", mid = "white", high = "red", midpoint = 0)

# Viridis continuous
scale_fill_viridis_c()
scale_fill_viridis_c(option = "magma")

# Named viridis options: "viridis" (default), "magma", "plasma", "inferno",
# "cividis", "rocket", "mako", "turbo"
```

### Grey Scale

```r
scale_color_grey()
scale_fill_grey(start = 0.2, end = 0.8)
```

## Other Aesthetic Scales

### Size

```r
scale_size(range = c(1, 10))
scale_size_area(max_size = 10)  # Area proportional to value
```

### Shape

```r
scale_shape_manual(values = c(16, 17, 18))
```

R shape codes: 0-14 (hollow), 15-20 (solid), 21-25 (filled with separate
color/fill).

### Alpha

```r
scale_alpha(range = c(0.2, 1))
```

### Linetype

```r
scale_linetype_manual(values = c("solid", "dashed", "dotted"))
```

## The scales Package

The `scales` package provides `label_*()` functions for formatting axis labels.
These are the R equivalents of Python lambda formatters.

### Label Formatters

| Function | Output Example | Use Case |
|----------|---------------|----------|
| `label_comma()` | 1,234,567 | Large numbers |
| `label_dollar()` | $1,234 | Currency |
| `label_percent()` | 45% | Percentages (input: 0.45) |
| `label_percent(scale = 1)` | 45% | Percentages (input: 45) |
| `label_number(suffix = "K", scale = 1e-3)` | 1.2K | Abbreviated |
| `label_number(suffix = "M", scale = 1e-6)` | 1.2M | Millions |
| `label_scientific()` | 1.2e+06 | Scientific notation |
| `label_ordinal()` | 1st, 2nd | Ordinals |
| `label_date(format = "%b %Y")` | Jan 2024 | Date formatting |
| `label_wrap(width = 15)` | (wrapped text) | Long labels |
| `label_log()` | 10^3 | Log scales |

```r
library(scales)

# Currency axis
scale_y_continuous(labels = label_dollar())

# Percentage axis (data in 0-1 range)
scale_y_continuous(labels = label_percent())

# Percentage axis (data in 0-100 range)
scale_y_continuous(labels = label_percent(scale = 1))

# Comma-separated thousands
scale_y_continuous(labels = label_comma())

# Abbreviated large numbers
scale_y_continuous(labels = label_number(suffix = "K", scale = 1e-3))
```

### Custom Label Functions

For anything `label_*()` does not cover, pass a function:

```r
# Custom formatter
scale_y_continuous(labels = function(x) paste0(x, "%"))

# Multiple formatting steps
scale_x_continuous(labels = function(x) format(x, big.mark = ",", scientific = FALSE))
```

### Comparison: R scales vs Python Formatting

| R (scales) | Python (plotnine) |
|-----------|-------------------|
| `label_dollar()` | `lambda x: [f"${v:,.0f}" for v in x]` |
| `label_percent()` | `lambda x: [f"{v:.0%}" for v in x]` |
| `label_comma()` | `lambda x: [f"{v:,.0f}" for v in x]` |

The scales package provides concise, named formatters where plotnine requires
lambda functions.

## Axis Limits

### Quick Methods

```r
xlim(0, 100)
ylim(-10, 10)
```

### Via Scales (removes data outside range)

```r
scale_x_continuous(limits = c(0, 100))
```

### Coordinate Limits (zoom without removing data)

```r
coord_cartesian(xlim = c(0, 100), ylim = c(0, 50))
```

The distinction matters for statistics: `limits` in scales drops data before
stat computation (affects trend lines, boxplot whiskers, etc.);
`coord_cartesian` zooms after computation.

## Labels and Titles

### labs()

Set multiple labels at once:

```r
labs(
  title = "Main Title",
  subtitle = "Subtitle text",
  caption = "Data source: ...",
  x = "X Axis Label",
  y = "Y Axis Label",
  color = "Legend Title",
  fill = "Fill Legend"
)
```

### 4.0 Feature: labs(dictionary)

Map labels by variable name rather than aesthetic:

```r
labs(dictionary = c(wt = "Weight (1000 lbs)", mpg = "Miles per Gallon"))
```

### Individual Functions

```r
ggtitle("Title")
xlab("X Label")
ylab("Y Label")
```

## Guides (Legends)

### Modify Legend

```r
# Legend title via scale
scale_color_brewer(name = "Category", palette = "Set1")

# Remove all legends
theme(legend.position = "none")

# Remove legend for specific aesthetic
guides(color = "none")

# Customize legend layout
guides(color = guide_legend(title = "My Title", nrow = 2))
```

### guide_legend()

```r
guide_legend(
  title = "Title",
  nrow = 2,
  ncol = 1,
  reverse = TRUE,
  override.aes = list(size = 5)
)
```

### guide_colorbar()

For continuous color scales:

```r
guide_colorbar(
  title = "Value",
  barwidth = unit(10, "mm"),
  barheight = unit(80, "mm")
)
```

## Coordinates

| Coord | Description |
|-------|-------------|
| `coord_cartesian()` | Default; zoom without data removal |
| `coord_fixed()` | Fixed aspect ratio (wrapper for coord_cartesian in 4.0) |
| `coord_flip()` | Swap x and y (often unnecessary -- use `aes(y = ..., x = ...)` instead) |
| `coord_transform()` | Transform coordinates (renamed from `coord_trans()` in 4.0) |
| `coord_polar()` | Polar coordinates |
| `coord_sf()` | For spatial data (sf objects) |

```r
# Zoom without dropping data
coord_cartesian(xlim = c(0, 10), ylim = c(0, 100))

# Fixed aspect ratio
coord_fixed(ratio = 1)
coord_cartesian(ratio = 1)  # 4.0 alternative

# Reverse an axis via coord (4.0 feature)
coord_cartesian(reverse = "x")
```
