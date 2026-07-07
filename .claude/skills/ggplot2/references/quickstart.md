# Quickstart

## Essential Setup

```r
library(ggplot2)
library(scales)  # label_comma(), label_percent(), etc.
```

## Basic Plot Anatomy

Every ggplot2 plot follows this pattern:

```r
ggplot(data, aes(x = column_x, y = column_y)) +  # Data + aesthetics
  geom_point()                                     # Geometry layer
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `ggplot()` | Initialize plot with data |
| `aes()` | Map columns to visual properties |
| `geom_*()` | Define how to represent data |
| `+` | Add layers/components |

## Minimal Example

```r
library(ggplot2)

ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point()
```

## Column References: Bare Names

R uses **bare column names** (unquoted) in `aes()`, not strings:

```r
# R (ggplot2) -- bare names
aes(x = wt, y = mpg, color = factor(cyl))

# Python (plotnine) -- strings (do NOT use in R)
# aes(x = "wt", y = "mpg", color = "factor(cyl)")
```

This is the primary syntax difference from plotnine. Strings are never needed
for column references in ggplot2 `aes()`.

## Adding Layers

Layers are added with `+`. In R, `+` at end of line works (unlike Python/plotnine
which requires wrapping in parentheses):

```r
ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  geom_smooth(method = "lm") +
  theme_minimal()
```

## Assigning to Variables

```r
p <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  theme_minimal()

# Print to display
print(p)
```

## Saving Plots with ggsave()

```r
p <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point()

# Basic save
ggsave("plot.png", p)

# With dimensions and resolution
ggsave("plot.png", p, width = 10, height = 8, dpi = 300)

# Different formats
ggsave("plot.pdf", p, width = 10, height = 8)
ggsave("plot.svg", p, width = 10, height = 8)
```

### ggsave() Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `filename` | Output path (format from extension) | Required |
| `plot` | Plot object | Last plot |
| `width` | Width in inches (or `units`) | 7 |
| `height` | Height in inches (or `units`) | 7 |
| `dpi` | Resolution | 300 |
| `units` | "in", "cm", "mm", "px" | "in" |
| `bg` | Background color | "white" |
| `scale` | Scaling factor | 1 |

### DAAF Research Workflow Pattern

In DAAF pipelines, save to the project output directory:

```r
# --- Config ---
library(ggplot2)
PROJECT_DIR <- "/daaf/research/YYYY-MM-DD_Project_Name"
OUTPUT_DIR <- file.path(PROJECT_DIR, "output")

# --- Transform / Analyze ---
p <- ggplot(df, aes(x = year, y = enrollment)) +
  geom_line() +
  theme_minimal()

# --- Save ---
ggsave(
  file.path(OUTPUT_DIR, "YYYY-MM-DD_enrollment_trends.png"),
  p, width = 10, height = 8, dpi = 300
)
cat("Plot saved successfully\n")
```

### Saving to Temp Files (Tests)

```r
tmp <- tempfile(fileext = ".png")
ggsave(tmp, p, width = 10, height = 8, dpi = 300)
stopifnot(file.exists(tmp))
file.remove(tmp)
```

### Multi-Page PDFs (4.0+ feature)

```r
plots <- list(p1, p2, p3)
ggsave("multi_page.pdf", plots, width = 10, height = 8)
```

## Built-in Datasets

```r
# Available without loading extra packages
mtcars      # Motor Trend car data
iris        # Fisher's iris data
diamonds    # From ggplot2 package
mpg         # Fuel economy data (ggplot2)
economics   # US economic time series (ggplot2)
```

## Data Requirements

ggplot2 works with:
- **data.frame** (base R)
- **tibble** (tidyverse)
- **data.table** (automatically converted)

Arrow tables and other formats should be converted to data.frame first.

## Quick Examples

### Scatter with Color

```r
ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  labs(color = "Cylinders")
```

### Line Plot

```r
ggplot(economics, aes(x = date, y = unemploy)) +
  geom_line()
```

### Bar Chart

```r
ggplot(mtcars, aes(x = factor(cyl))) +
  geom_bar()
```

### Histogram

```r
ggplot(diamonds, aes(x = price)) +
  geom_histogram(bins = 30)
```

### Scatter with Trend Line

```r
ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  geom_smooth(method = "lm", se = TRUE)
```

### Complete Publication Example

```r
p <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  geom_smooth(method = "lm", se = FALSE) +
  scale_color_brewer(palette = "Set1") +
  labs(
    title = "Fuel Efficiency vs Weight",
    x = "Weight (1000 lbs)",
    y = "Miles per Gallon",
    color = "Cylinders"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 16, face = "bold"),
    legend.position = "bottom"
  )

ggsave("mpg_vs_wt.png", p, width = 10, height = 8, dpi = 300)
```

## Next Steps

- [Geoms](./geoms.md) -- chart types
- [Scales](./scales.md) -- axis and color control
- [Facets](./facets.md) -- multi-panel layouts
- [Themes](./themes.md) -- styling and polish
- [Extensions](./extensions.md) -- patchwork, ggrepel, ggridges, ggdist
