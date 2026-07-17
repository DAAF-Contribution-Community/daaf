# Static Maps with ggplot2 + geom_sf()

Making static maps using ggplot2's `geom_sf()` layer. Covers choropleths, classification schemes with classInt, layered maps, annotation, and multi-panel layouts. For ggplot2 fundamentals (themes, scales, facets), see the `ggplot2` skill.

---

## Basic Choropleth

```r
library(sf)
library(ggplot2)

ggplot(counties) +
  geom_sf(aes(fill = poverty_rate), color = "white", linewidth = 0.2) +
  scale_fill_distiller(palette = "YlOrRd", direction = 1) +
  labs(
    title = "Poverty Rate by County",
    fill = "Poverty Rate"
  ) +
  theme_void()
```

Note: "YlOrRd" is a ColorBrewer palette (use `scale_fill_distiller()` /
`scale_fill_brewer()`), not a viridis option. Passing it to
`scale_fill_viridis_c(option = ...)` does not error — it warns "Option 'YlOrRd'
does not exist" and silently falls back to the default viridis palette
(verified), so the map renders with the wrong colors. Valid viridis options are
"viridis", "magma", "plasma", "inferno", "cividis", "rocket", "mako", "turbo".

### geom_sf() Key Parameters

| Parameter | Effect |
|-----------|--------|
| `aes(fill = col)` | Color polygons by column (choropleth) |
| `aes(color = col)` | Color points/lines by column |
| `aes(size = col)` | Size points by column |
| `color` / `colour` | Border color (outside aes) |
| `fill` | Fill color (outside aes) |
| `linewidth` | Border width |
| `alpha` | Transparency (0-1) |
| `show.legend` | Show in legend (TRUE/FALSE) |

---

## Classification Schemes with classInt

classInt provides statistical classification methods for choropleth maps. Without classification, continuous color ramps can obscure patterns.

### Computing Breaks

```r
library(classInt)

# Fisher-Jenks natural breaks (default recommendation)
brks <- classIntervals(counties$poverty_rate, n = 5, style = "fisher")

# Quantiles (equal number of observations per class)
brks <- classIntervals(counties$poverty_rate, n = 5, style = "quantile")

# Equal intervals
brks <- classIntervals(counties$poverty_rate, n = 5, style = "equal")

# Fixed/custom breaks
brks <- classIntervals(counties$poverty_rate, style = "fixed",
                       fixedBreaks = c(0, 5, 10, 15, 20, 30))

# Inspect
print(brks)
brks$brks         # Break points
table(findCols(brks))  # Observations per class
```

### Available Styles

| Style | How It Works | Best For |
|-------|-------------|----------|
| `"fisher"` | Minimizes within-class variance (Fisher-Jenks) | General purpose (default) |
| `"jenks"` | Similar to Fisher | General purpose |
| `"quantile"` | Equal number of observations per class | Skewed distributions |
| `"equal"` | Equal range per class | Uniformly distributed data |
| `"sd"` | Classes based on standard deviations from mean | Deviation from average |
| `"pretty"` | Round "nice" break values | Presentation-ready labels |
| `"fixed"` | Custom breakpoints | Domain-specific thresholds |
| `"headtails"` | For heavy-tailed distributions | Power-law data |

### Applying Breaks to ggplot2

```r
library(classInt)
library(ggplot2)

# Compute breaks
brks <- classIntervals(counties$poverty_rate, n = 5, style = "fisher")

# Create classified column
counties$pov_class <- cut(counties$poverty_rate,
                          breaks = brks$brks,
                          include.lowest = TRUE,
                          dig.lab = 4)

# Plot with discrete fill scale
ggplot(counties) +
  geom_sf(aes(fill = pov_class), color = "white", linewidth = 0.2) +
  scale_fill_brewer(palette = "YlOrRd", name = "Poverty Rate (%)") +
  labs(title = "Poverty Rate by County (Fisher-Jenks)") +
  theme_void()
```

### Alternative: scale_fill_fermenter() for Binned Continuous

```r
# ggplot2's built-in binning (simpler but less control than classInt)
ggplot(counties) +
  geom_sf(aes(fill = poverty_rate), color = "white", linewidth = 0.2) +
  scale_fill_fermenter(palette = "YlOrRd", n.breaks = 5, direction = 1,
                       name = "Poverty Rate") +
  theme_void()
```

---

## Color Scales for Maps

### Continuous

```r
# Viridis family (perceptually uniform, colorblind-safe)
scale_fill_viridis_c(option = "viridis")    # Default
scale_fill_viridis_c(option = "magma")       # Dark-to-light
scale_fill_viridis_c(option = "plasma")
scale_fill_viridis_c(option = "inferno")
scale_fill_viridis_c(option = "turbo")       # Rainbow-like

# Gradient
scale_fill_gradient(low = "white", high = "darkred")

# Diverging (centered on midpoint)
scale_fill_gradient2(low = "blue", mid = "white", high = "red",
                     midpoint = median(counties$change))

# Distiller (ColorBrewer continuous)
scale_fill_distiller(palette = "YlOrRd", direction = 1)
```

### Discrete / Categorical

```r
# ColorBrewer palettes
scale_fill_brewer(palette = "Set2")        # Qualitative
scale_fill_brewer(palette = "YlOrRd")      # Sequential
scale_fill_brewer(palette = "RdBu")        # Diverging

# Manual colors
scale_fill_manual(values = c("Rural" = "#2c7bb6", "Urban" = "#d7191c"))
```

### Common Map Colormaps

| Category | Palettes | Use For |
|----------|----------|---------|
| Sequential | `YlOrRd`, `Blues`, `Greens`, `Purples`, `viridis` | Single-direction data (counts, rates) |
| Diverging | `RdBu`, `RdYlGn`, `BrBG` | Data with meaningful center |
| Categorical | `Set1`, `Set2`, `Dark2`, `Paired` | Distinct categories |

---

## Layered Maps

```r
ggplot() +
  # Base layer: counties
  geom_sf(data = counties, fill = "lightyellow", color = "gray80",
          linewidth = 0.3) +
  # Overlay: schools colored by enrollment
  geom_sf(data = schools, aes(color = enrollment), size = 1) +
  scale_color_viridis_c(name = "Enrollment") +
  # Overlay: district boundaries (no fill)
  geom_sf(data = districts, fill = NA, color = "red", linewidth = 1) +
  labs(title = "Schools by Enrollment") +
  theme_void()
```

---

## Map Annotation

```r
library(ggplot2)

ggplot(counties) +
  geom_sf(aes(fill = poverty_rate), color = "white", linewidth = 0.2) +
  scale_fill_viridis_c(name = "Poverty\nRate (%)") +
  # Add text labels
  geom_sf_text(aes(label = name), size = 2, color = "gray30") +
  # Or repelled labels (avoids overlap)
  geom_sf_label(data = top_counties, aes(label = name),
                size = 2, fill = "white", alpha = 0.7) +
  # North arrow and scale bar via ggspatial
  # library(ggspatial)
  # annotation_north_arrow(location = "tl", style = north_arrow_minimal()) +
  # annotation_scale(location = "bl") +
  labs(
    title = "Poverty Rate by County",
    subtitle = "Source: ACS 5-Year Estimates",
    caption = "Projection: NAD83 Conus Albers (EPSG:5070)"
  ) +
  theme_void() +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    legend.position = c(0.85, 0.3)
  )
```

---

## Multi-Panel Maps

```r
library(patchwork)

p1 <- ggplot(counties) +
  geom_sf(aes(fill = poverty_rate), color = "white", linewidth = 0.1) +
  scale_fill_viridis_c() +
  labs(title = "Poverty Rate") +
  theme_void()

p2 <- ggplot(counties) +
  geom_sf(aes(fill = median_income), color = "white", linewidth = 0.1) +
  scale_fill_viridis_c(option = "plasma") +
  labs(title = "Median Income") +
  theme_void()

combined <- p1 + p2 +
  plot_annotation(title = "Economic Indicators by County")
ggsave("panel_maps.png", combined, width = 16, height = 6, dpi = 300)
```

### Faceted Maps

```r
# Long-format data with year column
ggplot(counties_long) +
  geom_sf(aes(fill = poverty_rate), color = "white", linewidth = 0.1) +
  scale_fill_viridis_c() +
  facet_wrap(~ year, ncol = 3) +
  labs(title = "Poverty Rate Over Time") +
  theme_void()
```

---

## Saving Maps

```r
# PNG (default for DAAF)
ggsave("map.png", p, width = 10, height = 8, dpi = 300)

# SVG (scalable, for publications)
ggsave("map.svg", p, width = 10, height = 8)

# PDF (for print)
ggsave("map.pdf", p, width = 10, height = 8)
```

---

## Missing Data Handling

```r
# Explicitly show areas with no data
ggplot(counties) +
  geom_sf(aes(fill = poverty_rate), color = "white", linewidth = 0.2) +
  scale_fill_viridis_c(na.value = "gray90", name = "Poverty Rate") +
  theme_void()
```

---

## References and Further Reading

Lovelace, R., Nowosad, J., and Muenchow, J. (2024). *Geocomputation with R* (2nd ed.), Ch. 9: "Making maps with R." https://r.geocompx.org/

Pebesma, E. and Bivand, R. (2023). *Spatial Data Science*, Ch. 14: "Plotting spatial data." https://r-spatial.org/book/

classInt documentation. https://r-spatial.github.io/classInt/
