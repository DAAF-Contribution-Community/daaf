# Regression Tables with modelsummary

Using modelsummary() to format regression output from lm, glm, fixest, plm, and
other model classes into publication-quality tables. Customizing coefficients,
statistics, output formats, and integrating with gt/kableExtra backends.
modelsummary 2.6.0.

> **Note:** The r-stats skill (`reporting.md`) provides comprehensive modelsummary
> coverage from the statistical modeling perspective. This reference focuses on
> the table formatting and presentation aspects -- how to make regression tables
> look right for publication.

---

## Basic Regression Table

```r
library(modelsummary)

fit1 <- lm(mpg ~ wt, data = mtcars)
fit2 <- lm(mpg ~ wt + hp, data = mtcars)
fit3 <- lm(mpg ~ wt + hp + factor(cyl), data = mtcars)

# Default table (side-by-side models)
modelsummary(list(fit1, fit2, fit3))
```

### Named Models

```r
modelsummary(list(
  "Bivariate" = fit1,
  "Controls" = fit2,
  "Full" = fit3
))
```

## Output Formats

```r
# gt object (default -- richest formatting)
modelsummary(models, output = "gt")

# kableExtra (good for Quarto)
modelsummary(models, output = "kableExtra")

# Markdown (good for DAAF reports)
modelsummary(models, output = "markdown")

# LaTeX (for journal submissions)
modelsummary(models, output = "latex")

# Save directly to file
modelsummary(models, output = "results_table.html")
modelsummary(models, output = "results_table.tex")
modelsummary(models, output = "results_table.png")
modelsummary(models, output = "results_table.docx")

# Data frame (for further processing)
modelsummary(models, output = "data.frame")
```

When `output = "gt"` (default), the return value is a gt table object that can
be further customized with gt functions:

```r
modelsummary(models, output = "gt") |>
  tab_header(title = "Regression Results") |>
  tab_source_note("Source: mtcars dataset.") |>
  opt_row_striping()
```

## Coefficient Customization

### Renaming Coefficients

```r
modelsummary(
  models,
  coef_rename = c(
    "wt" = "Weight (1000 lbs)",
    "hp" = "Horsepower",
    "factor(cyl)6" = "6 Cylinders",
    "factor(cyl)8" = "8 Cylinders",
    "(Intercept)" = "Constant"
  )
)
```

### Omitting Coefficients

```r
# Omit the intercept
modelsummary(models, coef_omit = "(Intercept)")

# Omit by regex pattern
modelsummary(models, coef_omit = "factor\\(cyl\\)")

# Keep only specific coefficients
modelsummary(models, coef_omit = "^(?!wt|hp)")
```

### Reordering Coefficients

```r
modelsummary(
  models,
  coef_map = c(
    "wt" = "Weight",
    "hp" = "Horsepower",
    "(Intercept)" = "Constant"
  )
)
```

`coef_map` both renames and reorders. Only listed coefficients appear in the
output (implicitly omits unlisted ones).

## Statistics and Formatting

### Statistic Below Each Coefficient

```r
# Standard errors in parentheses (default)
modelsummary(models, statistic = "({std.error})")

# Confidence intervals in brackets
modelsummary(models, statistic = "[{conf.low}, {conf.high}]")

# t-statistics
modelsummary(models, statistic = "t = {statistic}")

# p-values
modelsummary(models, statistic = "p = {p.value}")

# Multiple statistics per coefficient
modelsummary(
  models,
  statistic = c("({std.error})", "[{conf.low}, {conf.high}]")
)

# No statistic row (coefficients only)
modelsummary(models, statistic = NULL)
```

### Significance Stars

```r
modelsummary(
  models,
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001)
)

# With a note about star meaning
modelsummary(
  models,
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001),
  notes = "* p < 0.05, ** p < 0.01, *** p < 0.001"
)
```

### Number Formatting

```r
modelsummary(
  models,
  fmt = 3,          # 3 decimal places for all numbers
  fmt = fmt_decimal(digits = 3, pdigits = 4)  # 3 decimals, 4 for p-values
)
```

## Goodness-of-Fit Statistics

### Selecting Statistics

```r
# Show only specific GOF statistics
modelsummary(
  models,
  gof_map = c("nobs", "r.squared", "adj.r.squared")
)

# Custom GOF display
modelsummary(
  models,
  gof_map = list(
    list(raw = "nobs", clean = "N", fmt = 0),
    list(raw = "r.squared", clean = "R-squared", fmt = 3),
    list(raw = "adj.r.squared", clean = "Adj. R-squared", fmt = 3),
    list(raw = "aic", clean = "AIC", fmt = 1)
  )
)
```

### Adding Custom Rows

```r
# Add fixed effects indicators
rows <- data.frame(
  term = c("State FE", "Year FE"),
  "(1)" = c("No", "No"),
  "(2)" = c("Yes", "No"),
  "(3)" = c("Yes", "Yes"),
  check.names = FALSE
)

modelsummary(models, add_rows = rows)
```

## Robust and Clustered Standard Errors

modelsummary can compute robust/clustered SEs without re-fitting:

```r
# HC1 robust SEs
modelsummary(models, vcov = "HC1")

# Clustered by state
modelsummary(models, vcov = ~state)

# Two-way clustering
modelsummary(models, vcov = ~state + year)

# Different SE types per model
modelsummary(
  list("IID" = fit, "Robust" = fit, "Clustered" = fit),
  vcov = list("iid", "HC1", ~state)
)
```

## fixest Models in modelsummary

fixest models work seamlessly with modelsummary:

```r
library(fixest)
library(modelsummary)

fe1 <- feols(mpg ~ wt | cyl, data = mtcars)
fe2 <- feols(mpg ~ wt + hp | cyl + am, data = mtcars)

modelsummary(
  list("FE1" = fe1, "FE2" = fe2),
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001),
  gof_map = c("nobs", "r.squared", "adj.r.squared",
              "FE: cyl", "FE: am")
)
```

**fixest etable() vs modelsummary():**

| Feature | etable() | modelsummary() |
|---------|----------|----------------|
| fixest-only models | Best choice | Works fine |
| Mixed model classes (lm + fixest + plm) | Cannot mix | Handles all |
| LaTeX output | Excellent | Excellent |
| gt/kableExtra backend | No | Yes |
| Coefficient rename | dict() syntax | Named vector |
| FE indicators | Automatic | Via gof_map or add_rows |

Use `etable()` when all models are fixest and you want quick output. Use
`modelsummary()` when mixing model classes, when you want gt formatting, or
when you need finer control over presentation.

## GLM Models: Exponentiated Coefficients

```r
fit_logit <- glm(am ~ wt + hp, data = mtcars, family = binomial)
fit_pois <- glm(carb ~ wt + hp, data = mtcars, family = poisson)

# Odds ratios and incidence rate ratios
modelsummary(
  list("Logit (OR)" = fit_logit, "Poisson (IRR)" = fit_pois),
  exponentiate = TRUE,
  statistic = "({std.error})"
)
```

## Descriptive Statistics Tables

modelsummary also creates summary statistics tables (not just regressions):

```r
# datasummary for descriptive statistics
datasummary_skim(mtcars)

# Custom summary table
datasummary(
  mpg + hp + wt ~ Mean + SD + Min + Max + N,
  data = mtcars
)

# Balance table (treatment vs control)
datasummary_balance(~ am, data = mtcars)

# Correlation matrix
datasummary_correlation(mtcars[, c("mpg", "hp", "wt")])
```

## Complete Example: Publication Table

```r
library(modelsummary)
library(gt)

fit1 <- lm(mpg ~ wt, data = mtcars)
fit2 <- lm(mpg ~ wt + hp, data = mtcars)
fit3 <- lm(mpg ~ wt + hp + factor(cyl), data = mtcars)

tbl <- modelsummary(
  list("(1)" = fit1, "(2)" = fit2, "(3)" = fit3),
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001),
  coef_map = c(
    "wt" = "Weight (1000 lbs)",
    "hp" = "Horsepower",
    "factor(cyl)6" = "6 Cylinders",
    "factor(cyl)8" = "8 Cylinders",
    "(Intercept)" = "Constant"
  ),
  gof_map = c("nobs", "r.squared", "adj.r.squared"),
  output = "gt"
) |>
  tab_header(
    title = "Determinants of Fuel Economy",
    subtitle = "OLS regression, mtcars data"
  ) |>
  tab_source_note("Standard errors in parentheses.") |>
  tab_source_note("* p < 0.05, ** p < 0.01, *** p < 0.001")

# Save
gtsave(tbl, "regression_table.html")
gtsave(tbl, "regression_table.png")
```
