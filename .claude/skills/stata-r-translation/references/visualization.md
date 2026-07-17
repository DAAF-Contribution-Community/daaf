# Visualization: Stata to R (ggplot2)

Stata's graph system is command-based: pick a plot type and configure with
options. R's ggplot2 uses the grammar of graphics: compose layers. The mental
model shift is from "run a graph command with options" to "build a plot by
adding components."

> **Versions referenced:** R: ggplot2 4.0.2, plotly (R) 4.12.0, fixest 0.14.0

---

## Core Mapping

| Stata | ggplot2 |
|-------|---------|
| `twoway scatter y x` | `ggplot(df, aes(x, y)) + geom_point()` |
| `twoway line y x` | `ggplot(df, aes(x, y)) + geom_line()` |
| `twoway connected y x` | `geom_line() + geom_point()` |
| `graph bar (mean) y, over(g)` | Pre-aggregate + `geom_col()` or `stat_summary()` |
| `graph bar (count), over(g)` | `geom_bar()` |
| `graph hbar` | `geom_col() + coord_flip()` |
| `graph box y, over(g)` | `geom_boxplot()` |
| `histogram y` | `geom_histogram()` |
| `histogram y, kdensity` | `geom_histogram(aes(y = after_stat(density))) + geom_density()` |
| `kdensity y` | `geom_density()` |
| `twoway (scatter y x) (lfit y x)` | `geom_point() + geom_smooth(method = "lm")` |

---

## Scatter Plots

```stata
graph twoway scatter mpg weight, mcolor(navy) title("Fuel Efficiency")
graph twoway scatter mpg weight, by(cyl)
```

```r
ggplot(df, aes(x = weight, y = mpg)) +
  geom_point(color = "navy") +
  labs(title = "Fuel Efficiency")

# By group -- color
ggplot(df, aes(x = weight, y = mpg, color = factor(cyl))) +
  geom_point()

# By group -- facets
ggplot(df, aes(x = weight, y = mpg)) +
  geom_point() +
  facet_wrap(~cyl)
```

---

## Coefficient and Event Study Plots

```stata
reghdfe y i.rel_time, absorb(unit year) cluster(unit)
coefplot, keep(*.rel_time) vertical
```

```r
fit <- feols(y ~ i(rel_time, ref = -1) | unit + year, data = df, vcov = ~unit)
iplot(fit)                                      # Event study
coefplot(fit)                                    # Coefficient plot
coefplot(list(m1, m2, m3))                      # Multiple models
```

---

## Customization

| Stata | ggplot2 |
|-------|---------|
| `title("text")` | `labs(title = "text")` |
| `xtitle("X")` | `labs(x = "X")` |
| `note("Source: CCD")` | `labs(caption = "Source: CCD")` |
| `scheme(s2mono)` | `theme_bw()` |
| `scheme(s1color)` | `theme_minimal()` |
| `by(var)` | `facet_wrap(~var)` |
| `by(var1 var2)` | `facet_grid(var1 ~ var2)` |
| `graph export "f.png"` | `ggsave("f.png", dpi = 300)` |
| `xsize(10) ysize(6)` | `theme(aspect.ratio = 6/10)` or `ggsave(width = 10, height = 6)` |

---

## Multi-Panel Layouts

```stata
graph combine g1 g2, cols(2)
```

```r
library(patchwork)
p1 <- ggplot(df, aes(x, y1)) + geom_point()
p2 <- ggplot(df, aes(x, y2)) + geom_point()
p1 | p2                    # Side by side
p1 / p2                    # Stacked
(p1 | p2) / p3             # Complex layout
```

---

## Interactive Plots (plotly)

Stata has no built-in interactive visualization. R's plotly provides hover,
zoom, and pan:

```r
library(plotly)

# Convert any ggplot to interactive
p <- ggplot(df, aes(x = income, y = score, color = sector)) + geom_point()
ggplotly(p)

# Direct plotly
plot_ly(df, x = ~income, y = ~score, color = ~sector, type = "scatter", mode = "markers")
```

---

## Common Gotchas

1. **Factor ordering in plots:** ggplot2 plots factor levels in order. Use
   `fct_reorder()` or `fct_infreq()` to control order.
2. **Multiple series:** Stata plots multiple y-variables from wide data.
   ggplot2 requires long format with a group variable mapped to color/linetype.
3. **Bar chart means:** `geom_bar()` counts by default. For means, use
   `geom_col()` with pre-aggregated data or `stat_summary(fun = mean, geom = "bar")`.
