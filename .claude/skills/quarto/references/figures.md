# Figures

## Basic Figure Output

Any R code that produces a plot creates a figure in the output:

````markdown
```{r}
plot(mtcars$wt, mtcars$mpg)
```
````

This works for base R, ggplot2, lattice, and any graphics system.

## ggplot2 Figures

ggplot2 is the primary plotting library in DAAF R pipelines:

````markdown
```{r}
#| label: fig-scatter
#| fig-cap: "Relationship between weight and fuel efficiency"

library(ggplot2)

ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point() +
  theme_minimal() +
  labs(x = "Weight (1000 lbs)", y = "Miles per Gallon")
```
````

The last expression in the chunk is the ggplot object -- it renders automatically.

## Figure Options

### Captions

````markdown
```{r}
#| label: fig-trend
#| fig-cap: "Enrollment trend 2010-2024"

ggplot(df, aes(x = year, y = enrollment)) +
  geom_line()
```
````

The caption appears below the figure. Combined with a `fig-` label prefix, it
enables cross-referencing.

### Sizing

````markdown
```{r}
#| fig-width: 10
#| fig-height: 6

ggplot(df, aes(x = x, y = y)) + geom_point()
```
````

| Option | Default | Unit | Purpose |
|--------|---------|------|---------|
| `fig-width` | 7 | inches | Width of the generated plot |
| `fig-height` | 5 | inches | Height of the generated plot |
| `out-width` | (auto) | CSS | Display width in document (e.g., `"80%"`) |
| `out-height` | (auto) | CSS | Display height in document |
| `fig-dpi` | 72 | dpi | Resolution (higher = larger file) |

`fig-width`/`fig-height` control the **R graphics device** size (affects text/element proportions).
`out-width`/`out-height` control the **display size** in the rendered document.

For print-quality figures, use higher DPI:

````markdown
```{r}
#| fig-width: 8
#| fig-height: 5
#| fig-dpi: 300
```
````

### Format

````markdown
```{r}
#| fig-format: svg
```
````

| Format | Best For | Notes |
|--------|----------|-------|
| `png` | Default, raster | Good for most uses |
| `svg` | Vector, scalable | Clean for HTML, larger file |
| `pdf` | Print, PDF output | Vector, PDF-only |

### Alignment

````markdown
```{r}
#| fig-align: center
```
````

Options: `left`, `center`, `right`, `default`

### Alt Text

For accessibility:

````markdown
```{r}
#| fig-alt: "Scatter plot showing negative correlation between car weight and fuel efficiency"
```
````

## Cross-Referencing Figures

To create a cross-referenceable figure:
1. Use a `fig-` prefixed label
2. Add a `fig-cap`
3. Reference with `@fig-label`

````markdown
```{r}
#| label: fig-distribution
#| fig-cap: "Distribution of school enrollment"

ggplot(df, aes(x = enrollment)) +
  geom_histogram(bins = 50) +
  theme_minimal()
```

As shown in @fig-distribution, enrollment is right-skewed.
````

The `@fig-distribution` reference renders as a clickable link like "Figure 1".

Requirements for cross-references to work:
- Label MUST start with `fig-`
- Caption (`fig-cap`) MUST be present
- Reference uses `@` prefix

## Multiple Figures

### Side-by-Side Figures

Use `layout-ncol`:

````markdown
```{r}
#| label: fig-comparison
#| fig-cap: "Enrollment comparison"
#| fig-subcap:
#|   - "By grade level"
#|   - "By school type"
#| layout-ncol: 2

# First plot
ggplot(df, aes(x = grade, y = enrollment)) +
  geom_col()

# Second plot
ggplot(df, aes(x = type, y = enrollment)) +
  geom_col()
```
````

Each plot in the chunk becomes a sub-figure with its own subcaption.

Reference sub-figures:
- `@fig-comparison` -- the whole figure
- `@fig-comparison-1` -- first sub-figure
- `@fig-comparison-2` -- second sub-figure

### Custom Layout

````markdown
```{r}
#| label: fig-grid
#| fig-cap: "Analysis dashboard"
#| layout: [[1,1], [1]]

# Row 1, Col 1
plot1

# Row 1, Col 2
plot2

# Row 2, full width
plot3
```
````

The `layout` list specifies relative widths. `[[1,1], [1]]` means:
- Row 1: two equal-width plots
- Row 2: one full-width plot

### Separate Chunks for Each Figure

For maximum control, use separate chunks:

````markdown
```{r}
#| label: fig-trend-a
#| fig-cap: "Public school enrollment"

ggplot(public_df, aes(x = year, y = enrollment)) + geom_line()
```

```{r}
#| label: fig-trend-b
#| fig-cap: "Private school enrollment"

ggplot(private_df, aes(x = year, y = enrollment)) + geom_line()
```

@fig-trend-a shows public trends while @fig-trend-b shows private trends.
````

## Global Figure Defaults

Set in YAML frontmatter:

```yaml
---
execute:
  fig-width: 8
  fig-height: 5
  fig-dpi: 150
  fig-format: png
  fig-align: center
---
```

Or under the format key for format-specific defaults:

```yaml
---
format:
  html:
    fig-width: 8
    fig-height: 5
  pdf:
    fig-width: 6
    fig-height: 4
---
```

## Saving Figures Separately

To save a figure to a file in addition to including it in the document:

````markdown
```{r}
#| label: fig-main-result

p <- ggplot(df, aes(x = x, y = y)) + geom_point()

# Save to file
ggsave("output/figures/main_result.png", p, width = 8, height = 5, dpi = 300)

# Display in document
p
```
````

In DAAF pipelines, figures saved during Stage 8 analysis scripts are the
authoritative versions. Stage 9 notebooks display the script code that
produced them, not the figures themselves.

## Base R Plots

Base R plots work identically -- the chunk options are the same:

````markdown
```{r}
#| label: fig-base-example
#| fig-cap: "Base R scatter plot"
#| fig-width: 7
#| fig-height: 5

plot(mtcars$wt, mtcars$mpg,
     xlab = "Weight", ylab = "MPG",
     main = "Weight vs. MPG",
     pch = 19, col = "steelblue")
```
````

## Figure Paths

When `quarto render` runs, figures are saved to a `_files/` directory next to the
output:

```
analysis.qmd
analysis.html
analysis_files/
  figure-html/
    fig-scatter-1.png
    fig-trend-1.png
```

With `embed-resources: true`, figures are embedded in the HTML -- no separate files.

For PDF output, figures are embedded directly in the PDF.

## Tips

1. **Use consistent sizing** across related figures for visual coherence
2. **Set global defaults** in YAML to avoid repeating options per chunk
3. **Use `fig-` prefix on labels** -- cross-references only work with this prefix
4. **Always include `fig-cap`** for any figure you want to cross-reference
5. **Use `fig-alt`** for accessibility in HTML documents
6. **Prefer SVG** for HTML documents with simple graphics (lines, bars)
7. **Prefer PNG** for complex plots or when file size matters
8. **Use `embed-resources`** for self-contained HTML delivery
