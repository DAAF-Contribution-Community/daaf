# Facets

Create multiple panels (small multiples) from data subsets.

## facet_wrap()

Wrap panels into rows/columns from a single variable:

```r
# Single variable
facet_wrap(~ variable)

# Control layout
facet_wrap(~ variable, ncol = 3)
facet_wrap(~ variable, nrow = 2)

# Free scales
facet_wrap(~ variable, scales = "free")
facet_wrap(~ variable, scales = "free_x")
facet_wrap(~ variable, scales = "free_y")
```

### Multiple Variables in facet_wrap

```r
# Two variables
facet_wrap(~ var1 + var2)

# Using vars() syntax (preferred for complex expressions)
facet_wrap(vars(var1, var2))
```

### Panel Direction (4.0 update)

The `as.table` argument is deprecated in 4.0. Use `dir` instead:

```r
# Left-to-right, top-to-bottom (default)
facet_wrap(~ variable, dir = "lt")

# 4.0 dir options: "lt" (left-top, default), "rt", "lb", "rb",
# plus "h" and "v" (deprecated in 4.0)
```

### Free Space (1-row or 1-column layouts)

New in 4.0: `facet_wrap()` supports `space = "free_x"` for single-row layouts
and `space = "free_y"` for single-column layouts:

```r
# Panels sized proportional to data range
facet_wrap(~ variable, nrow = 1, space = "free_x", scales = "free_x")
```

## facet_grid()

Grid layout with row and column variables:

```r
# Rows by one variable, columns by another
facet_grid(row_var ~ col_var)

# Only rows
facet_grid(row_var ~ .)

# Only columns
facet_grid(. ~ col_var)

# Free scales
facet_grid(row_var ~ col_var, scales = "free")

# Free space (panels sized by data range)
facet_grid(row_var ~ col_var, space = "free")
```

### vars() Syntax

```r
# Alternative to formula (more explicit)
facet_grid(rows = vars(row_var), cols = vars(col_var))
```

### Syntax Comparison: ggplot2 vs plotnine

| ggplot2 (R) | plotnine (Python) |
|-------------|-------------------|
| `facet_wrap(~ var)` | `facet_wrap("var")` |
| `facet_grid(row ~ col)` | `facet_grid("row ~ col")` |
| `facet_grid(row ~ .)` | `facet_grid("row ~ .")` |
| `facet_wrap(~ var1 + var2)` | `facet_wrap("var1 + var2")` |

R uses formula notation (`~`); plotnine uses strings. The variable names and
other parameters are otherwise identical.

## Facet Labels

### Built-in Labellers

| Function | Result |
|----------|--------|
| `label_value` | Value only (default) |
| `label_both` | Variable: Value |
| `label_context` | Smart context |
| `label_parsed` | Parse as expression |
| `label_wrap_gen(width)` | Wrap long labels |

```r
# Show variable name and value
facet_wrap(~ var, labeller = label_both)

# Custom labels via named vector
facet_wrap(~ var, labeller = labeller(var = c("A" = "Group A", "B" = "Group B")))

# Wrap long labels
facet_wrap(~ long_var, labeller = label_wrap_gen(width = 20))
```

### Custom Labeller Functions

```r
# Custom labeller for a single variable
my_labeller <- as_labeller(c(
  "1" = "Category One",
  "2" = "Category Two",
  "3" = "Category Three"
))

facet_wrap(~ category, labeller = my_labeller)

# Multiple variables with different labellers
facet_grid(
  row_var ~ col_var,
  labeller = labeller(
    row_var = c("a" = "Group A", "b" = "Group B"),
    col_var = label_both
  )
)
```

### Syntax Comparison: Labellers

| ggplot2 (R) | plotnine (Python) |
|-------------|-------------------|
| `c("A" = "Group A")` (named vector) | `{"A": "Group A"}` (dict) |
| `labeller(var = c(...))` | `labeller(var = {...})` |
| `label_both` | `label_both` |
| `label_wrap_gen(20)` | Not available |

## Panel Sizing (4.0 Feature)

New in 4.0: Control panel dimensions via theme:

```r
# Set absolute panel widths (all panels)
theme(panel.widths = unit(c(3, 5), "cm"))

# Set absolute panel heights
theme(panel.heights = unit(c(4, 6), "cm"))
```

## Margins in facet_grid

Include marginal panels:

```r
facet_grid(row_var ~ col_var, margins = TRUE)
facet_grid(row_var ~ col_var, margins = "row_var")
```

## Complete Faceting Example

```r
ggplot(mpg, aes(x = displ, y = hwy)) +
  geom_point(aes(color = class), size = 2) +
  geom_smooth(method = "lm", se = FALSE, linewidth = 0.8) +
  facet_wrap(~ year, ncol = 2, scales = "free_y") +
  scale_color_brewer(palette = "Set2") +
  labs(
    title = "Engine Displacement vs Highway MPG",
    subtitle = "By model year",
    x = "Displacement (L)",
    y = "Highway MPG"
  ) +
  theme_minimal() +
  theme(
    strip.text = element_text(face = "bold", size = 12),
    strip.background = element_rect(fill = "lightblue", color = NA),
    legend.position = "bottom"
  )
```

## Strip Customization

```r
theme(
  # Strip text
  strip.text = element_text(size = 12, face = "bold"),
  strip.text.x = element_text(size = 12),      # Top strips only
  strip.text.y = element_text(angle = 0),       # Right strips

  # Strip background
  strip.background = element_rect(fill = "grey90", color = "grey50"),

  # Strip placement (outside axis labels)
  strip.placement = "outside",

  # Strip clipping (4.0: defaults to "on")
  strip.clip = "on"
)
```
