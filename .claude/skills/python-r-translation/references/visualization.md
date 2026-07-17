# Visualization: R Explained for Python Users

This reference covers R visualization code explained for Python users. The core
mapping is **ggplot2 (R) for plotnine (Python) users** and **plotly R for plotly
Python users**. ggplot2 and plotnine share the same grammar of graphics -- the
translation is syntactic, not conceptual.

> **Versions referenced:**
> R: ggplot2 4.0.2, plotly 4.12.0
> Python: plotnine 0.15.3, plotly 6.5.2
> See SKILL.md § Library Versions for the complete version table.

---

## Section 1: ggplot2 for plotnine Users

plotnine is a near-1:1 port of ggplot2. The grammar is identical: `ggplot()`,
`aes()`, `geom_*()`, `scale_*()`, `facet_*()`, `theme_*()`, composed with `+`.

### Key Syntax Differences

| ggplot2 (R) | plotnine (Python) |
|-------------|-------------------|
| Bare names: `aes(x = year, y = value)` | Strings: `aes(x="year", y="value")` |
| Formula in facets: `facet_wrap(~ var)` | String: `facet_wrap("var")` |
| `library(ggplot2)` | `from plotnine import *` |
| `ggsave("file.png", p, width=10, height=8)` | `p.save("file.png", width=10, height=8, dpi=300)` |
| `face = "bold"` in theme | `weight = "bold"` |
| Dots in theme names: `panel.grid.major` | Underscores: `panel_grid_major` |

### Complete Parallel Example

```r
# R (ggplot2) -- you know this from plotnine
p <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  geom_smooth(method = "lm", se = FALSE) +
  scale_color_brewer(palette = "Set1") +
  labs(title = "Fuel Efficiency vs Weight", x = "Weight", y = "MPG") +
  theme_minimal() +
  theme(plot.title = element_text(size = 16, face = "bold"))

ggsave("plot.png", p, width = 10, height = 8)
```

```python
# Python (plotnine) -- what you know
p = (
    ggplot(mtcars, aes(x="wt", y="mpg", color="factor(cyl)"))
    + geom_point(size=3)
    + geom_smooth(method="lm", se=False)
    + scale_color_brewer(palette="Set1")
    + labs(title="Fuel Efficiency vs Weight", x="Weight", y="MPG")
    + theme_minimal()
    + theme(plot_title=element_text(size=16, weight="bold"))
)
p.save("plot.png", width=10, height=8, dpi=300)
```

Three differences: (1) bare names vs strings in `aes()`, (2) `face="bold"` vs
`weight="bold"`, (3) dots vs underscores in theme element names.

---

## Section 2: Geoms, Scales, and Faceting

Most geoms, scales, and faceting functions are **identical** between ggplot2 and
plotnine. All `geom_point()`, `geom_line()`, `geom_bar()`, `geom_histogram()`,
`geom_boxplot()`, `geom_smooth()`, `geom_tile()`, etc. work the same way.

**R-only geoms:** `geom_sf()` (spatial) exists in ggplot2 but not plotnine.
Use `geom_map()` with a GeoDataFrame in plotnine instead.

### Scales

| ggplot2 (R) | plotnine (Python) |
|-------------|-------------------|
| `scale_color_viridis_c()` | `scale_color_cmap(cmap_name="viridis")` |
| `scale_fill_viridis_c()` | `scale_fill_cmap(cmap_name="viridis")` |
| `scale_y_continuous(labels = scales::dollar)` | `scale_y_continuous(labels=lambda x: [f"${v:,.0f}" for v in x])` |

R's `scales` package helpers (`dollar`, `percent`, `comma`) have no direct plotnine
equivalents. Use lambda functions.

### Faceting

```r
# R
facet_wrap(~ state, ncol = 3, scales = "free_y")
facet_grid(sector ~ year)
```

```python
# Python
facet_wrap("state", ncol=3, scales="free_y")
facet_grid("sector ~ year")
```

Formula (`~`) becomes string in plotnine.

---

## Section 3: plotly R for plotly Python Users

| plotly R | plotly Python |
|----------|---------------|
| `plot_ly(df, x = ~year, y = ~value)` | `px.scatter(df, x="year", y="value")` |
| `~column_name` (tilde formula) | `"column_name"` (string) |
| `list(title = "X")` | `dict(title="X")` |
| `TRUE` / `FALSE` | `True` / `False` |
| `%>% layout(...)` | `.update_layout(...)` |
| `htmlwidgets::saveWidget(p, "f.html")` | `fig.write_html("f.html")` |

R uses tilde formula for variable references (`~column_name`), Python uses strings.
R's `list()` maps to Python's `dict()`.

---

## Section 4: Coefficient and Effect Plots

| R (fixest) | Python (pyfixest) |
|-----------|-------------------|
| `coefplot(fit)` | `pf.coefplot(fit)` |
| `coefplot(list(fit1, fit2))` | `pf.coefplot([fit1, fit2])` |
| `iplot(fit)` | `fit.iplot()` |
| `iplot(fit, joint = TRUE)` | `fit.iplot(joint="both")` |

pyfixest's plot functions are functionally equivalent to fixest's.

---

## Section 5: Patchwork (Multi-Panel Layouts)

```r
# R (patchwork)
library(patchwork)
(p1 | p2 | p3) / p4
```

```python
# Python (plotnine v0.15+) -- same operators
(p1 | p2 | p3) / p4
```

plotnine now supports patchwork-style composition with identical operators.

---

## Quick Reference

| Need | R Tool | Python Tool |
|------|--------|-------------|
| Static grammar-of-graphics | ggplot2 | plotnine |
| Interactive chart | plotly R | plotly Python |
| Coefficient plot | fixest::coefplot | pf.coefplot() |
| Event study plot | fixest::iplot | fit.iplot() |
| Regression table | etable / modelsummary | pf.etable() |
| Combining plots | patchwork | plotnine `|` and `/` |
| Spatial / map | ggplot2 + geom_sf | geopandas .plot() |

> **Sources:** Wickham, *ggplot2: Elegant Graphics for Data Analysis*, 3rd ed. (2024);
> plotnine documentation (plotnine.org, accessed 2026-03-28)
