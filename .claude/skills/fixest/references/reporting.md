# Reporting: Tables and Plots

## Contents

- [etable: Regression Tables](#etable-regression-tables)
- [coefplot: Coefficient Plots](#coefplot-coefficient-plots)
- [iplot: Event Study / Interaction Plots](#iplot-event-study--interaction-plots)
- [fixef: Extracting Fixed Effects](#fixef-extracting-fixed-effects)
- [Saving Outputs](#saving-outputs)

## etable: Regression Tables

`etable()` produces formatted regression tables comparing multiple models side by
side. It is one of fixest's most mature features and is more full-featured than
pyfixest's equivalent.

### Basic Usage

```r
library(fixest)
data(trade, package = "fixest")

fit1 <- feols(log(Euros) ~ log(dist_km), data = trade)
fit2 <- feols(log(Euros) ~ log(dist_km) | Origin, data = trade)
fit3 <- feols(log(Euros) ~ log(dist_km) | Origin + Destination, data = trade)

# Console display
etable(fit1, fit2, fit3)
```

### Output Formats

```r
# Console table (default)
etable(fit1, fit2)

# LaTeX output
etable(fit1, fit2, tex = TRUE)

# Save LaTeX to file
etable(fit1, fit2, tex = TRUE, file = "tables/regression_table.tex")

# Get as data.frame for further processing
et_df <- etable(fit1, fit2)
# Returns class "etable_df" (inherits from data.frame)
```

Note: fixest does not have a `type = "markdown"` argument for etable. The
`markdown = TRUE` argument only works inside RMarkdown/Quarto knitr chunks.
For plain markdown output, extract the data.frame and format manually, or use
the `modelsummary` R package.

### Customization

```r
etable(fit1, fit2, fit3,
       # Variable selection
       keep = "log",                    # Regex: keep variables matching "log"
       drop = "Intercept",             # Drop intercept row
       order = c("dist", "Intercept"), # Reorder rows

       # Formatting
       digits = 3,                     # Decimal places
       digits.stats = 3,              # Decimal places for statistics
       signif.code = c("***" = 0.001, "**" = 0.01, "*" = 0.05),

       # Labels
       dict = c(log_dist_km = "Log Distance",
                Origin = "Origin FE",
                Destination = "Dest FE"),

       # SE display
       se.below = TRUE,               # SE in parentheses below coef (default)
       coefstat = "se",               # "se", "tstat", "confint"

       # Headers and caption
       headers = c("(1)", "(2)", "(3)"),
       caption = "Gravity Model Estimates")
```

### Key Customization Arguments

| Argument | Purpose | Example |
|----------|---------|---------|
| `keep` | Keep variables (regex) | `keep = "^X"` |
| `drop` | Drop variables (regex) | `drop = "Intercept"` |
| `order` | Reorder variables | `order = c("X1", "X2")` |
| `dict` | Rename variables/FEs | `dict = c(X1 = "Education")` |
| `se.below` | SE below coefficients | `TRUE` (default) |
| `coefstat` | What to show with coef | `"se"`, `"tstat"`, `"confint"` |
| `digits` | Decimal places | `3` (default) |
| `signif.code` | Significance stars | Named vector of thresholds |
| `headers` | Column headers | Character vector |
| `caption` | Table caption | String |
| `tex` | LaTeX output | `TRUE` for LaTeX |
| `file` | Save to file | File path |
| `fitstat` | Fit statistics to show | `~r2 + n + f` |
| `fixef.group` | Group FE indicators | Named list |

### Fixed Effects Indicator Rows

`etable()` automatically adds rows showing which fixed effects are included
(with checkmarks). Use `dict` to rename them:

```r
etable(fit1, fit2, fit3,
       dict = c(Origin = "Origin FE", Destination = "Destination FE"))
```

### Grouping Fixed Effects

```r
# Group multiple FE under a single label
etable(fit1, fit2, fit3,
       fixef.group = list("Geographic FE" = "Origin|Destination",
                          "Time FE" = "Year"))
```

### Fit Statistics

```r
# Control which statistics appear at the bottom
etable(fit1, fit2,
       fitstat = ~r2 + r2.within + n)

# Available fit statistics include:
# r2, r2.within, r2.adj, n (observations), f (F-stat), rmse, aic, bic
```

### LaTeX Customization

```r
etable(fit1, fit2, tex = TRUE,
       style.tex = style.tex(
         depvar.title = "Dep. Var.:",
         fixef.title = "Fixed Effects:",
         fixef.suffix = " FE",
         yesNo = c("Yes", "No"),       # FE indicator text
         notes.tpt.intro = "\\footnotesize"
       ),
       notes = "Standard errors in parentheses.",
       label = "tab:gravity",
       float = TRUE,
       placement = "htbp")
```

### Working with Multi-Estimation

When using `sw()`/`csw()`, `feols()` returns a `fixest_multi` object. Pass it
directly to `etable()`:

```r
fits <- feols(log(Euros) ~ csw(log(dist_km), Destination) | Origin, data = trade)
etable(fits)           # Correct
# etable(list(fits))   # Wrong
```

## coefplot: Coefficient Plots

`coefplot()` visualizes estimated coefficients with confidence intervals.

### Basic Usage

```r
# Single model
coefplot(fit1)

# Compare across models
coefplot(list(fit1, fit2))
```

### Customization

```r
coefplot(fit1,
         keep = "log",                  # Variables to include (regex)
         drop = "Intercept",           # Variables to exclude
         main = "Coefficient Estimates",
         xlab = "Estimate",
         horiz = TRUE,                 # Horizontal layout (default)
         ci.width = 0.05,             # 95% CI
         col = "steelblue",
         pch = 20)
```

### Comparing Models

```r
coefplot(list(fit1, fit2, fit3),
         keep = "log",
         main = "Model Comparison",
         legendtext = c("No FE", "Origin FE", "Two-Way FE"))
```

## iplot: Event Study / Interaction Plots

`iplot()` is specifically designed for models with `i()` interaction terms,
particularly event studies. See `did.md` for full event study usage.

### Basic Usage

```r
fit <- feols(y ~ i(rel_year, ref = -1) | entity + year, data = df)
iplot(fit)
```

### Customization

```r
iplot(fit,
      main = "Event Study",
      xlab = "Periods Relative to Treatment",
      ylab = "Estimated Effect",
      ref.line = -1,                  # Vertical reference line
      zero.line = TRUE,               # Horizontal line at y=0
      ci.width = 0.05,               # 95% CI
      ci.fill = TRUE,                # Filled confidence bands
      col = "steelblue")
```

### Comparing Models

```r
iplot(list(fit_twfe, fit_sa),
      main = "TWFE vs Sun-Abraham",
      legendtext = c("TWFE", "Sun-Abraham"))
```

## fixef: Extracting Fixed Effects

The `fixef()` function recovers absorbed FE estimates. See `fixed-effects.md`
for technical details.

### Basic Extraction

```r
fit <- feols(y ~ x1 | entity + year, data = df)
fe <- fixef(fit)

# Access individual FE dimensions
entity_effects <- fe$entity     # Named numeric vector
year_effects <- fe$year         # Named numeric vector

# Summary of FE estimates
summary(fe)

# Quick plot
plot(fe)
```

### Converting to Data Frame

```r
# For merging or further analysis
entity_df <- data.frame(
  entity = names(fe$entity),
  fe_entity = as.numeric(fe$entity)
)

year_df <- data.frame(
  year = as.integer(names(fe$year)),
  fe_year = as.numeric(fe$year)
)
```

### Combining FE with Predicted Values

```r
# Predicted values including FE
yhat <- predict(fit)              # Includes FE contributions (fixef = FALSE
                                  # is the default and returns full predictions)

# NOTE: predict(fit, fixef = TRUE) does NOT return Xb-without-FE. It returns
# a data.frame of the per-observation fixed-effect coefficients instead.
fe_contrib <- predict(fit, fixef = TRUE)  # per-obs FE coefficient(s)

# To get the linear predictor WITHOUT the FE contribution (just Xb), subtract
# the summed FE contributions from the full prediction:
xb <- yhat - rowSums(fe_contrib)
```

## Saving Outputs

### Tables

```r
# LaTeX to file
etable(fit1, fit2, tex = TRUE, file = "output/tables/regression.tex")

# Data frame for programmatic use
et_df <- etable(fit1, fit2)
```

### Plots

```r
# PNG for reports
png("output/figures/coef_plot.png", width = 10, height = 6,
    units = "in", res = 300)
coefplot(fit1)
dev.off()

# PDF for LaTeX
pdf("output/figures/event_study.pdf", width = 10, height = 6)
iplot(fit)
dev.off()
```

### DAAF Pipeline Convention

In research pipelines, save all figures to `output/figures/` using the DAAF
naming convention:

```r
# YYYY-MM-DD[suffix]_description.png
png("output/figures/2026-01-24a_event_study.png",
    width = 10, height = 6, units = "in", res = 300)
iplot(fit, main = "Event Study: Policy Effect")
dev.off()

cat("Figure saved: output/figures/2026-01-24a_event_study.png\n")
stopifnot(file.exists("output/figures/2026-01-24a_event_study.png"))
```

## References

- Berge, L., Butts, K., and McDermott, G. (2026). "Fast and User-Friendly
  Econometrics Estimations: The R Package fixest." arXiv:2601.21749.
- fixest documentation — Tables and Plots:
  https://lrberge.github.io/fixest/articles/etable_new_features.html
