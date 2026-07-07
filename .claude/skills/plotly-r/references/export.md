# Export and Saving

## Interactive HTML (Primary DAAF Export)

### htmlwidgets::saveWidget()

The primary export mechanism for plotly R charts in DAAF:

```r
library(htmlwidgets)

# HTML export (loads plotly.js from CDN -- default for DAAF)
saveWidget(p, "plot.html", selfcontained = FALSE)

# Self-contained HTML (embeds plotly.js, ~3MB -- requires pandoc)
# saveWidget(p, "plot.html", selfcontained = TRUE)  # NOT available in DAAF
```

### selfcontained: TRUE vs FALSE

| Option | File Size | Offline Viewing | Requires | Best For |
|--------|-----------|-----------------|----------|----------|
| `FALSE` | ~3-50KB | No (needs CDN) | Nothing | **DAAF default** |
| `TRUE` | ~3MB+ | Yes | pandoc | Sharing, archival (not in DAAF) |

> **DAAF note:** `selfcontained = TRUE` requires pandoc, which is not installed
> in the DAAF container. Always use `selfcontained = FALSE`. The output HTML
> loads plotly.js from a CDN, so an internet connection is needed to view it.

### Title in HTML

```r
saveWidget(p, "plot.html", selfcontained = FALSE,
           title = "My Interactive Chart")
```

### DAAF Research Workflow Pattern

```r
# --- Config ---
library(plotly)
library(htmlwidgets)
PROJECT_DIR <- "/daaf/research/YYYY-MM-DD_Project_Name"
OUTPUT_DIR <- file.path(PROJECT_DIR, "output")

# --- Save ---
saveWidget(
  p,
  file.path(OUTPUT_DIR, "YYYY-MM-DD_enrollment_interactive.html"),
  selfcontained = FALSE,
  title = "Enrollment Trends (Interactive)"
)
cat("Plot saved to:", file.path(OUTPUT_DIR, "YYYY-MM-DD_enrollment_interactive.html"), "\n")
```

### Saving to Temp Files (Tests)

```r
tmp <- tempfile(fileext = ".html")
saveWidget(p, tmp, selfcontained = FALSE)
stopifnot(file.exists(tmp))
fsize <- file.info(tmp)$size
cat("File size:", fsize, "bytes\n")
stopifnot(fsize > 100)
file.remove(tmp)
```

---

## Static Image Export

> **DAAF note:** Static image export via `orca()` or `kaleido()` is NOT available
> in the DAAF container. orca requires a separate system binary; kaleido requires
> Python's kaleido package via reticulate. For static PNG/SVG/PDF figures, use
> **ggplot2** with `ggsave()`. Reserve plotly for interactive HTML output.
>
> The reference below is retained for completeness if these tools are available in
> a custom environment.

### orca (legacy)

```r
# Requires orca system binary: https://github.com/plotly/orca
orca(p, "plot.png", width = 1200, height = 800)
orca(p, "plot.svg")
orca(p, "plot.pdf")
```

### kaleido (via reticulate)

```r
# Requires: reticulate + Python kaleido package
# pip install kaleido (in Python environment)
kaleido(p, "plot.png", width = 1200, height = 800)
```

### Supported Static Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PNG | `.png` | Raster, best for web |
| SVG | `.svg` | Vector, scalable |
| PDF | `.pdf` | Vector, print quality |
| JPEG | `.jpg` | Raster, lossy |
| WebP | `.webp` | Modern, efficient |

---

## Quarto Embedding

plotly widgets integrate naturally with Quarto documents when using the knitr
engine:

### Basic Embedding

````markdown
```{r}
library(plotly)

p <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers")
p
```
````

The widget renders as interactive HTML in the Quarto output. Simply printing the
plotly object in a code chunk is sufficient -- no explicit save step needed for
Quarto rendering.

### With Figure Options

````markdown
```{r}
#| fig-cap: "Interactive scatter plot of MPG vs Weight"
#| fig-width: 8
#| fig-height: 6

p <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers") |>
  layout(title = "MPG vs Weight")
p
```
````

Note: `fig-width` and `fig-height` in Quarto primarily affect static output
formats. For HTML output, plotly widgets are responsive by default.

### Multiple Plots

Each plotly object in a code chunk renders as a separate interactive widget:

````markdown
```{r}
p1 <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers")
p2 <- plot_ly(mtcars, x = ~factor(cyl), type = "bar")

p1
p2
```
````

---

## JSON Export

### Save to JSON

```r
plotly_json(p, jsonedit = FALSE)           # Print JSON to console
# Note: plotly_json() has no file argument (signature: p, jsonedit, pretty, ...).
# To write JSON to a file, use the string-conversion pattern below.
```

### Alternative: Convert to JSON String

```r
json_str <- plotly_build(p) |> plotly:::to_JSON()
writeLines(json_str, "plot.json")
```

---

## Quick Reference

| Task | Method |
|------|--------|
| Interactive HTML (DAAF default) | `saveWidget(p, "plot.html", selfcontained = FALSE)` |
| Interactive HTML (self-contained) | `saveWidget(p, "plot.html", selfcontained = TRUE)` (requires pandoc) |
| Quarto embedding | Just print `p` in a code chunk |
| Static PNG (not in DAAF) | `orca(p, "plot.png")` or `kaleido(p, "plot.png")` |
| Static SVG (not in DAAF) | `orca(p, "plot.svg")` |
| Static PDF (not in DAAF) | `orca(p, "plot.pdf")` |
| JSON | `plotly_json(p)` |
| For static figures in DAAF | Use ggplot2 + ggsave() instead |
