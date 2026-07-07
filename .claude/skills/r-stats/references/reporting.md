# R Stats Reporting Reference

Tidy model output with `broom`, publication-quality tables with `modelsummary`,
and marginal effects with `marginaleffects`. broom 1.0.12, modelsummary 2.6.0,
marginaleffects 0.32.0.

---

## Contents

- [broom: Tidy Model Output](#broom-tidy-model-output)
- [modelsummary: Publication Tables](#modelsummary-publication-tables)
- [marginaleffects: Marginal Effects and Comparisons](#marginaleffects-marginal-effects-and-comparisons)
- [Comparison to Python](#comparison-to-python)

---

## broom: Tidy Model Output

broom provides three functions that convert model objects to tidy data frames:

### tidy(): Coefficient-Level Statistics

```r
library(broom)

fit <- lm(y ~ x1 + x2, data = df)

# Basic tidy output
tidy(fit)
# Returns: term, estimate, std.error, statistic, p.value

# With confidence intervals
tidy(fit, conf.int = TRUE, conf.level = 0.95)
# Adds: conf.low, conf.high

# For GLMs: exponentiate for odds ratios / IRRs
fit_logit <- glm(y ~ x1 + x2, data = df, family = binomial)
tidy(fit_logit, conf.int = TRUE, exponentiate = TRUE)
# estimate, conf.low, conf.high are now odds ratios
```

### glance(): Model-Level Statistics

```r
glance(fit)
# Returns one-row data frame:
# r.squared, adj.r.squared, sigma, statistic, p.value, df,
# logLik, AIC, BIC, deviance, df.residual, nobs

# For GLMs
glance(fit_logit)
# Returns: null.deviance, df.null, logLik, AIC, BIC, deviance,
#          df.residual, nobs
```

### augment(): Observation-Level Data

```r
augment(fit)
# Returns one row per observation:
# All original data columns plus:
# .fitted   -- fitted values
# .resid    -- residuals
# .hat      -- leverage (diagonal of hat matrix)
# .sigma    -- leave-one-out estimate of sigma
# .cooksd   -- Cook's distance
# .std.resid -- standardized residuals

# Augment with new data
augment(fit, newdata = new_df)
# Returns: .fitted (predictions) plus newdata columns
```

### broom with Other Model Types

broom supports 100+ model classes:

```r
# t-test
tt <- t.test(x, y)
tidy(tt)
# Returns: estimate, estimate1, estimate2, statistic, p.value,
#          parameter, conf.low, conf.high, method, alternative

# Chi-squared test
ct <- chisq.test(table(x, y))
tidy(ct)

# Wilcoxon test
wt <- wilcox.test(x, y)
tidy(wt)

# Correlation test
cor_t <- cor.test(x, y)
tidy(cor_t)

# MASS::glm.nb
library(MASS)
fit_nb <- glm.nb(count ~ x1 + x2, data = df)
tidy(fit_nb, conf.int = TRUE, exponentiate = TRUE)
# IRRs with confidence intervals
```

### broom with Robust SEs

broom does not natively accept custom vcov. Use `lmtest::coeftest()` first:

```r
library(lmtest)
library(sandwich)

robust_ct <- coeftest(fit, vcov = vcovHC(fit, type = "HC1"))
tidy(robust_ct, conf.int = TRUE)
# Returns tidy output with robust SEs
```

---

## modelsummary: Publication Tables

### Basic Usage

```r
library(modelsummary)

fit1 <- lm(y ~ x1, data = df)
fit2 <- lm(y ~ x1 + x2, data = df)
fit3 <- lm(y ~ x1 + x2 + x3, data = df)

# Default table (multiple models side by side)
modelsummary(list(fit1, fit2, fit3))
```

### Output Formats

```r
# Markdown (good for DAAF reports)
modelsummary(list(fit1, fit2, fit3), output = "markdown")

# LaTeX
modelsummary(list(fit1, fit2, fit3), output = "latex")

# Save to file
modelsummary(list(fit1, fit2, fit3), output = "results_table.md")
modelsummary(list(fit1, fit2, fit3), output = "results_table.tex")
modelsummary(list(fit1, fit2, fit3), output = "results_table.png")
modelsummary(list(fit1, fit2, fit3), output = "results_table.docx")

# Data frame (for further processing)
modelsummary(list(fit1, fit2, fit3), output = "data.frame")
```

### Customization

```r
# Named models
modelsummary(list("Base" = fit1, "Extended" = fit2, "Full" = fit3))

# Custom coefficient labels
modelsummary(
  list(fit1, fit2, fit3),
  coef_rename = c("x1" = "Education", "x2" = "Experience", "x3" = "Age")
)

# Keep only specific coefficients
modelsummary(list(fit1, fit2, fit3), coef_omit = "(Intercept)")

# Custom statistics
modelsummary(
  list(fit1, fit2, fit3),
  statistic = "({std.error})",    # parenthetical SEs (default)
  # Or: statistic = "[{conf.low}, {conf.high}]"  # CIs
  # Or: statistic = "p = {p.value}"               # p-values
)

# Multiple statistics per coefficient
modelsummary(
  list(fit1, fit2, fit3),
  statistic = c("({std.error})", "[{conf.low}, {conf.high}]")
)

# Custom goodness-of-fit rows
modelsummary(
  list(fit1, fit2, fit3),
  gof_map = c("nobs", "r.squared", "adj.r.squared", "aic")
)

# Stars
modelsummary(
  list(fit1, fit2, fit3),
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001)
)
```

### Robust Standard Errors in modelsummary

```r
# HC1 robust SEs
modelsummary(list(fit1, fit2), vcov = "HC1")

# Clustered SEs
modelsummary(list(fit1, fit2), vcov = ~ state)

# Two-way clustered
modelsummary(list(fit1, fit2), vcov = ~ state + year)

# Different SE types per model
modelsummary(
  list("IID" = fit1, "Robust" = fit1, "Clustered" = fit1),
  vcov = list("iid", "HC1", ~ state)
)
```

### Adding Rows

```r
# Add fixed effects indicators
modelsummary(
  list(fit1, fit2, fit3),
  add_rows = data.frame(
    term = c("State FE", "Year FE"),
    `(1)` = c("No", "No"),
    `(2)` = c("Yes", "No"),
    `(3)` = c("Yes", "Yes")
  )
)
```

### modelsummary with GLMs

```r
fit_logit <- glm(y ~ x1 + x2, data = df, family = binomial)
fit_pois <- glm(count ~ x1 + x2, data = df, family = poisson)

# Exponentiate for odds ratios / IRRs
modelsummary(
  list("Logit (OR)" = fit_logit, "Poisson (IRR)" = fit_pois),
  exponentiate = TRUE
)
```

### Descriptive Statistics Table

```r
# Summary statistics for data
datasummary_skim(df)

# Custom summary table
datasummary(
  x1 + x2 + x3 ~ Mean + SD + Min + Max + N,
  data = df
)

# Balance table (by group)
datasummary_balance(~ treatment, data = df)

# Correlation matrix
datasummary_correlation(df)
```

---

## marginaleffects: Marginal Effects and Comparisons

### Average Marginal Effects (AME)

> **Reserved variable names.** marginaleffects (0.32.0+) forbids models whose data
> contain variables named `group`, `term`, `contrast`, `estimate`, `std.error`,
> `statistic`, `p.value`, `conf.low`, or `conf.high` — these collide with its
> internal output columns and error with "These variable names are forbidden…".
> Rename such columns before fitting (the examples below use `region`, not `group`).

```r
library(marginaleffects)

fit <- glm(y ~ x1 + x2 + factor(region), data = df, family = binomial)

# Average marginal effects for all variables
avg_slopes(fit)
# Returns: term, estimate (dydx), std.error, statistic, p.value,
#          s.value, conf.low, conf.high

# AME for specific variables
avg_slopes(fit, variables = "x1")

# AME at specific values
slopes(fit, newdata = datagrid(x1 = c(0, 1, 2)))
```

### Average Comparisons (for Categorical Variables)

```r
# Compare levels of a factor
avg_comparisons(fit, variables = "region")
# Returns: pairwise differences in predicted probability

# Specific comparison
avg_comparisons(fit, variables = list(region = c("A", "B")))
```

### Average Predictions

```r
# Predicted probabilities at specific covariate values
avg_predictions(fit, by = "region")

# Predictions over a grid
predictions(fit, newdata = datagrid(x1 = seq(0, 10, by = 1)))
```

### Hypothesis Tests on Effects

```r
# Test: is the AME of x1 = 0?
# (Default -- reported in avg_slopes output)

# Equality test -- is AME of x1 = AME of x2?
# Use POSITIONAL indices (b1, b2, ...) into the avg_slopes() output rather than
# variable names. On models with a factor, the string form "x1 = x2" errors with
# a non-unique `term` column, because each factor level adds a term row.
fit2 <- glm(y ~ x1 + x2, data = df, family = binomial)
avg_slopes(fit2)                       # inspect row order first
hypotheses(avg_slopes(fit2), "b1 = b2")

# Joint (Wald) test: AME of x1 = 0 AND AME of x2 = 0.
# Pass `joint` to the FITTED MODEL, not to avg_slopes(): the joint form on an
# avg_slopes() object fails ("Lapack routine dgesv: system is exactly singular")
# because the effects object carries no usable joint vcov.
hypotheses(fit, joint = c("x1", "x2"))
```

> **Caveats (marginaleffects 0.32.0).** Two forms that look natural but fail:
> `hypotheses(avg_slopes(fit), "x1 = x2")` errors when a factor with 3+ levels
> is in the model (two or more rows then share a `term` label, making the
> column non-unique — use positional `b1`/`b2` indices instead), and
> `hypotheses(avg_slopes(fit), joint = ...)` errors as singular (run the joint
> test on the fitted model object as shown above). Because positional indices
> depend on row order, inspect `avg_slopes()` output first and assert the order
> (e.g. `stopifnot(s$term[1] == "x1")`) before relying on `b1`/`b2`.

### marginaleffects with Different Models

```r
# Works with lm, glm, MASS::glm.nb, MASS::polr, fixest, and many more

# Poisson: AME in terms of expected count change
fit_pois <- glm(count ~ x1 + x2, data = df, family = poisson)
avg_slopes(fit_pois)

# Ordered logit: AME for each outcome category
library(MASS)
fit_ord <- polr(rating ~ x1 + x2, data = df, method = "logistic")
avg_slopes(fit_ord)
```

### Plotting Marginal Effects

```r
library(ggplot2)

fit <- glm(y ~ x1 + x2, data = df, family = binomial)

# Plot marginal effect of x1 across its range
p <- plot_slopes(fit, variables = "x1", condition = "x1")
ggsave("marginal_effect_x1.png", p, width = 8, height = 6, dpi = 300)

# Predictions plot
p2 <- plot_predictions(fit, condition = "x1")
ggsave("predictions_x1.png", p2, width = 8, height = 6, dpi = 300)
```

---

## Comparison to Python

| Task | R | Python |
|------|---|--------|
| Tidy coefficients | `broom::tidy(fit)` | Parse `fit.summary2().tables[1]` |
| Model statistics | `broom::glance(fit)` | Manual attribute extraction |
| Augmented data | `broom::augment(fit)` | Manual construction |
| Multi-model table | `modelsummary(list(fit1, fit2))` | `pf.etable([fit1, fit2])` (pyfixest) |
| Robust SE table | `modelsummary(fit, vcov = "HC1")` | `pf.etable()` with `.vcov("hetero")` |
| Average marginal effects | `marginaleffects::avg_slopes(fit)` | `fit.get_margeff()` (statsmodels) |
| Comparisons | `marginaleffects::avg_comparisons(fit)` | `marginaleffects.avg_comparisons(fit)` |
| Predictions at values | `marginaleffects::predictions(fit, ...)` | `marginaleffects.predictions(fit, ...)` |

Key differences:
- R's `broom` provides a universal tidy interface -- one call for any model type.
  Python has no equivalent (each library has its own output format).
- `modelsummary` handles robust SEs via a simple `vcov` argument. Python requires
  re-fitting or calling `.vcov()` before table generation.
- `marginaleffects` works identically in R and Python (same author, same API).

---

## References

- Robinson, D., Hayes, A., & Couch, S. (2023). broom: Convert Statistical
  Objects into Tidy Tibbles. R package version 1.0.12.
- Arel-Bundock, V. (2022). "modelsummary: Data and Model Summaries in R."
  *Journal of Statistical Software*, 103(1), 1-23.
- Arel-Bundock, V., Greifer, N., & Heiss, A. (2024). "How to Interpret
  Statistical Models Using marginaleffects for R and Python." *Journal of
  Statistical Software*, 111(9), 1-32.
