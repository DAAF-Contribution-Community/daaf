# Themes

Themes control the non-data appearance of plots: backgrounds, gridlines, fonts,
margins, and overall styling.

## Built-in Themes

| Theme | Description |
|-------|-------------|
| `theme_gray()` | Default gray background |
| `theme_bw()` | Black and white |
| `theme_minimal()` | Minimal, no background |
| `theme_classic()` | Classic, axes only (4.0: black ticks, square line ends) |
| `theme_light()` | Light gray lines |
| `theme_dark()` | Dark background |
| `theme_void()` | Nothing (good for maps, diagrams) |
| `theme_linedraw()` | All black lines |

```r
ggplot(df, aes(x, y)) +
  geom_point() +
  theme_minimal()
```

### Theme Base Parameters

```r
theme_minimal(base_size = 14, base_family = "Arial")
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `base_size` | Base font size (pts) | 11 |
| `base_family` | Font family | "" (default) |
| `base_line_size` | Base line width | `base_size / 22` |
| `base_rect_size` | Base rect outline width | `base_size / 22` |

### 4.0 Feature: ink/paper/accent Arguments

All built-in themes accept `ink`, `paper`, and `accent` arguments in 4.0 for
quick color scheme changes:

```r
# Dark mode
theme_minimal(ink = "white", paper = "#1a1a1a", accent = "#4488ff")

# Warm tones
theme_bw(ink = "#333333", paper = "#fff8f0", accent = "#cc6600")
```

| Argument | Controls |
|----------|----------|
| `ink` | Foreground color (text, lines, ticks) |
| `paper` | Background color (panel, plot, strip) |
| `accent` | Highlight color |

### 4.0 Feature: header_family

```r
# Different font for headers/titles
theme_minimal(base_family = "Arial", header_family = "Georgia")
```

## Custom theme() Elements

The `theme()` function modifies individual theme elements:

```r
theme(
  axis.text = element_text(size = 12),
  axis.title = element_text(size = 14, face = "bold"),
  legend.position = "bottom",
  panel.grid.major = element_line(color = "grey90", linewidth = 0.5),
  panel.background = element_rect(fill = "white")
)
```

### Element Functions

| Function | For | Key Parameters |
|----------|-----|----------------|
| `element_text()` | Text styling | size, color, family, face, angle, hjust, vjust |
| `element_line()` | Lines and borders | color, linewidth, linetype |
| `element_rect()` | Rectangles (backgrounds) | fill, color, linewidth |
| `element_blank()` | Remove element | (no parameters) |

### element_text()

```r
element_text(
  size = 12,
  color = "black",
  family = "Arial",
  face = "bold",        # "plain", "bold", "italic", "bold.italic"
  angle = 45,
  hjust = 0.5,          # horizontal alignment (0 = left, 1 = right)
  vjust = 0.5,          # vertical alignment (0 = bottom, 1 = top)
  lineheight = 1.2,
  margin = margin(t = 5, r = 0, b = 0, l = 0)
)
```

### Syntax Comparison: ggplot2 vs plotnine

| ggplot2 (R) | plotnine (Python) |
|-------------|-------------------|
| `element_text(face = "bold")` | `element_text(weight = "bold")` |
| `element_text(hjust = 0.5)` | `element_text(ha = "center")` |
| `plot.title` (dots) | `plot_title` (underscores) |
| `panel.grid.major` | `panel_grid_major` |
| `axis.text.x` | `axis_text_x` |
| `legend.position` | `legend_position` |

R uses **dots** in theme element names; plotnine uses **underscores**.

### element_line()

```r
element_line(
  color = "grey80",
  linewidth = 0.5,      # 4.0: use linewidth, not size
  linetype = "dashed",
  lineend = "round"     # "round", "butt", "square"
)
```

### element_rect()

```r
element_rect(
  fill = "white",
  color = "black",
  linewidth = 0.5       # 4.0: use linewidth, not size
)
```

### element_blank()

Remove an element entirely:

```r
theme(panel.grid.minor = element_blank())
```

## Themeable Elements Reference

### Axis Elements

| Element | Description | Type |
|---------|-------------|------|
| `axis.title` | Both axis titles | text |
| `axis.title.x` | X axis title | text |
| `axis.title.y` | Y axis title | text |
| `axis.text` | Both tick labels | text |
| `axis.text.x` | X tick labels | text |
| `axis.text.y` | Y tick labels | text |
| `axis.ticks` | Tick marks | line |
| `axis.ticks.length` | Tick length | unit |
| `axis.line` | Axis lines | line |

### Panel Elements

| Element | Description | Type |
|---------|-------------|------|
| `panel.background` | Panel background | rect |
| `panel.border` | Panel border (fill forced transparent in 4.0) | rect |
| `panel.grid.major` | Major grid lines | line |
| `panel.grid.minor` | Minor grid lines | line |
| `panel.grid.major.x` | Major x grid lines | line |
| `panel.grid.major.y` | Major y grid lines | line |
| `panel.spacing` | Space between panels | unit |
| `panel.spacing.x` | Horizontal panel spacing | unit |
| `panel.spacing.y` | Vertical panel spacing | unit |
| `panel.widths` | Panel widths (4.0) | unit vector |
| `panel.heights` | Panel heights (4.0) | unit vector |

### Legend Elements

| Element | Description | Type |
|---------|-------------|------|
| `legend.position` | Position: "top", "bottom", "left", "right", "none", or c(x, y) | character/numeric |
| `legend.justification` | Anchor point for positioned legends | numeric |
| `legend.title` | Legend title | text |
| `legend.text` | Legend labels | text |
| `legend.background` | Background | rect |
| `legend.key` | Key background | rect |
| `legend.key.size` | Key size | unit |
| `legend.key.justification` | Key alignment (4.0) | numeric |
| `legend.spacing` | Between legends | unit |

### Plot Elements

| Element | Description | Type |
|---------|-------------|------|
| `plot.title` | Main title | text |
| `plot.subtitle` | Subtitle | text |
| `plot.caption` | Caption | text |
| `plot.tag` | Tag (e.g., "A", "B") | text |
| `plot.background` | Overall background | rect |
| `plot.margin` | Margins | margin |

### Strip Elements (Facet Labels)

| Element | Description | Type |
|---------|-------------|------|
| `strip.text` | Facet label text | text |
| `strip.text.x` | Top strip text | text |
| `strip.text.y` | Right strip text | text |
| `strip.background` | Strip background | rect |
| `strip.placement` | "inside" or "outside" axis | character |
| `strip.clip` | Clipping ("on" by default in 4.0) | character |

## Common Theme Modifications

### Legend Position

```r
theme(legend.position = "bottom")       # bottom, top, left, right
theme(legend.position = "none")         # remove legend
theme(legend.position = c(0.8, 0.2))   # coordinates (0-1)
theme(legend.position = "inside")       # 4.0: explicitly inside
```

### Remove Grid Lines

```r
theme(
  panel.grid.major = element_blank(),
  panel.grid.minor = element_blank()
)
```

### Rotate Axis Labels

```r
theme(axis.text.x = element_text(angle = 45, hjust = 1))
```

### Transparent Background (for overlay on slides)

```r
theme(
  panel.background = element_rect(fill = "transparent"),
  plot.background = element_rect(fill = "transparent", color = NA),
  legend.background = element_rect(fill = "transparent")
)
```

## 4.0 Feature: Geom Defaults via Theme

Set default aesthetics for all geoms globally:

```r
# Set all geoms to use a specific color/fill
theme(geom = element_geom(
  ink = "navy",          # foreground color for all geoms
  paper = "white",       # background/fill default
  accent = "steelblue",  # highlight color
  linewidth = 0.5,       # default linewidth
  pointsize = 2,         # default point size
  borderwidth = 0.5      # default border width
))
```

### from_theme() in aes()

Access theme defaults inside aesthetics:

```r
# Use theme's ink color
geom_point(aes(color = from_theme(ink)))
```

## 4.0 Feature: theme_sub_*() Helpers

Set related theme elements in groups:

```r
# Instead of:
theme(
  axis.line = element_line(color = "black"),
  axis.text = element_text(size = 10),
  axis.ticks = element_line(color = "black"),
  axis.ticks.length = unit(3, "mm")
)

# Use:
theme_sub_axis(
  line = element_line(color = "black"),
  text = element_text(size = 10),
  ticks = element_line(color = "black"),
  ticks.length = unit(3, "mm")
)
```

## 4.0 Feature: Margin Helpers

```r
# Change just one margin side (others inherit)
theme(plot.title = element_text(margin = margin_part(b = 10)))

# CSS-style margin recycling
margin_auto(10)       # all sides 10
margin_auto(10, 20)   # top/bottom 10, left/right 20
```

## Setting and Getting Themes

### 4.0 Renamed Functions

| 4.0 Name (preferred) | Old Name (still works) |
|----------------------|----------------------|
| `set_theme()` | `theme_set()` |
| `get_theme()` | `theme_get()` |
| `update_theme()` | `theme_update()` |
| `replace_theme()` | `theme_replace()` |

```r
# Set global default theme
set_theme(theme_minimal(base_size = 14))

# Get current theme
current <- get_theme()

# Update specific elements globally
update_theme(legend.position = "bottom")
```

## Combining Themes

Apply a base theme then override specific elements:

```r
ggplot(df, aes(x, y)) +
  geom_point() +
  theme_minimal(base_size = 14) +
  theme(
    plot.title = element_text(face = "bold"),
    legend.position = "bottom"
  )
```

## Reusable Custom Theme

```r
my_theme <- theme_minimal(base_size = 14) +
  theme(
    plot.title = element_text(size = 18, face = "bold"),
    plot.subtitle = element_text(size = 14, color = "grey40"),
    axis.text = element_text(size = 11),
    legend.position = "bottom",
    panel.grid.minor = element_blank()
  )

# Apply to any plot
p + my_theme
```

## Publication-Ready Theme Template

```r
theme_publication <- function(base_size = 12) {
  theme_minimal(base_size = base_size) +
    theme(
      # Title styling
      plot.title = element_text(face = "bold", size = base_size * 1.4),
      plot.subtitle = element_text(color = "grey40", size = base_size * 1.1),
      plot.caption = element_text(color = "grey50", size = base_size * 0.8),

      # Axis styling
      axis.title = element_text(face = "bold"),
      axis.text = element_text(size = base_size * 0.9),

      # Grid: only major y-lines
      panel.grid.major.x = element_blank(),
      panel.grid.minor = element_blank(),

      # Legend
      legend.position = "bottom",
      legend.title = element_text(face = "bold"),

      # Margins
      plot.margin = margin(15, 15, 15, 15)
    )
}

# Usage
p + theme_publication(base_size = 14)
```

Note: This theme definition uses a function, which is the one idiomatic case
for function definitions in R visualization code (theme factories). In DAAF
pipeline scripts, define the theme inline or as a stored `theme()` object
rather than a function, unless multiple plots in the same script need it.
