# R Stats Quickstart Reference

Technical reference for base R statistical modeling with `lm()`, `summary()`,
`confint()`, `predict()`, and the formula interface. Covers OLS, WLS, model
matrix construction, and key output interpretation. R 4.5.3.

---

## Contents

- [Your First Model](#your-first-model)
- [Reading the summary() Output](#reading-the-summary-output)
- [Key Results Extraction](#key-results-extraction)
- [Confidence Intervals](#confidence-intervals)
- [Prediction](#prediction)
- [Formula Syntax](#formula-syntax)
- [Weighted Least Squares](#weighted-least-squares)
- [Model Matrix](#model-matrix)
- [anova() vs summary()](#anova-vs-summary)
- [MASS Extras: rlm() and stepAIC()](#mass-extras)
- [Quick Comparison: R stats vs statsmodels](#quick-comparison-r-stats-vs-statsmodels)

---

## Your First Model

```r
# --- Config ---
library(broom)

# --- Load ---
df <- data.frame(
  y  = c(1, 2, 3, 4, 5),
  x1 = c(2, 4, 5, 7, 8),
  x2 = c(1, 3, 2, 5, 4)
)

# --- Transform ---
# INTENT: Fit basic OLS regression of y on x1 and x2
fit <- lm(y ~ x1 + x2, data = df)

# --- Validate ---
cat("Coefficients:\n")
print(coef(fit))

cat("\nFull summary:\n")
print(summary(fit))

cat("\nTidy output:\n")
print(tidy(fit, conf.int = TRUE))
```

`lm()` returns a fitted model object immediately -- no separate `.fit()` call
is needed (unlike Python's statsmodels). The object contains the model
specification, fitted values, residuals, and all information needed for
post-estimation.

---

## Reading the summary() Output

```r
fit <- lm(y ~ x1 + x2, data = df)
s <- summary(fit)
print(s)
```

The output has four sections:

### Call
Shows the formula used. Confirms the model specification.

### Residuals
Five-number summary (Min, 1Q, Median, 3Q, Max) of residuals. Symmetric
distribution around zero suggests good specification.

### Coefficients Table

| Column | Meaning |
|--------|---------|
| `Estimate` | Point estimate of the coefficient |
| `Std. Error` | Standard error of the estimate |
| `t value` | t-statistic = Estimate / Std. Error |
| `Pr(>\|t\|)` | Two-sided p-value for H0: coefficient = 0 |

Significance codes: `***` < 0.001, `**` < 0.01, `*` < 0.05, `.` < 0.1

### Bottom Statistics

| Field | Meaning |
|-------|---------|
| `Residual standard error` | sqrt(RSS / df_resid) = estimate of sigma |
| `Multiple R-squared` | Proportion of variance explained |
| `Adjusted R-squared` | R-squared penalized for number of predictors |
| `F-statistic` | Joint test that all slope coefficients are zero |
| `p-value` | p-value for the F-test |

---

## Key Results Extraction

```r
fit <- lm(y ~ x1 + x2, data = df)
s <- summary(fit)

# Coefficients
coef(fit)               # Named vector of estimates
s$coefficients          # Full coefficient table (matrix)

# Standard errors
s$coefficients[, "Std. Error"]

# p-values
s$coefficients[, "Pr(>|t|)"]

# R-squared
s$r.squared
s$adj.r.squared

# F-statistic
s$fstatistic            # Named vector: value, numdf, dendf

# Residual standard error (sigma)
s$sigma

# Residuals
residuals(fit)          # or: resid(fit)

# Fitted values
fitted(fit)             # or: fitted.values(fit)

# Number of observations
nobs(fit)

# Degrees of freedom
fit$df.residual         # Residual df

# AIC and BIC
AIC(fit)
BIC(fit)

# Log-likelihood
logLik(fit)

# Variance-covariance matrix of coefficients
vcov(fit)
```

### Using broom for Tidy Extraction

```r
library(broom)

# Tidy coefficient table (one row per term)
tidy(fit)
# Columns: term, estimate, std.error, statistic, p.value

# With confidence intervals
tidy(fit, conf.int = TRUE, conf.level = 0.95)
# Adds: conf.low, conf.high

# Model-level statistics (one row)
glance(fit)
# Columns: r.squared, adj.r.squared, sigma, statistic, p.value, df,
#          logLik, AIC, BIC, deviance, df.residual, nobs

# Observation-level data (one row per observation)
augment(fit)
# Columns: .fitted, .resid, .hat, .sigma, .cooksd, .std.resid
```

---

## Confidence Intervals

```r
# Default 95% CI
confint(fit)

# 99% CI
confint(fit, level = 0.99)

# CI for specific coefficient
confint(fit, parm = "x1")

# Using broom
tidy(fit, conf.int = TRUE, conf.level = 0.95)
```

---

## Prediction

### Point Predictions

```r
new_df <- data.frame(x1 = c(3, 6, 9), x2 = c(2, 4, 6))

# Point predictions
predict(fit, newdata = new_df)
```

### Confidence Intervals for the Mean (E[y|x])

```r
# Interval for the conditional mean
predict(fit, newdata = new_df, interval = "confidence", level = 0.95)
# Returns matrix: fit, lwr, upr
```

### Prediction Intervals for Individual Observations

```r
# Interval for a new individual observation (wider than confidence)
predict(fit, newdata = new_df, interval = "prediction", level = 0.95)
# Returns matrix: fit, lwr, upr
```

The prediction interval is always wider because it includes residual variance
(irreducible uncertainty). The confidence interval only captures uncertainty
about the mean.

### Standard Errors of Predictions

```r
pred <- predict(fit, newdata = new_df, se.fit = TRUE)
pred$fit        # Point predictions
pred$se.fit     # Standard errors
pred$df         # Residual degrees of freedom
pred$residual.scale  # Residual standard error (sigma)
```

### In-sample Predictions

```r
# Fitted values (same as predict without newdata)
fitted(fit)
predict(fit)   # equivalent
```

---

## Formula Syntax

R's formula interface is the original system that Python's patsy and formulaic
later adopted.

### Core Operators

| Formula | Meaning |
|---------|---------|
| `y ~ x1 + x2` | Additive model with intercept |
| `y ~ x1 * x2` | Main effects + interaction: `x1 + x2 + x1:x2` |
| `y ~ x1 : x2` | Interaction term only (no main effects) |
| `y ~ factor(region)` | Treat region as categorical |
| `y ~ x1 + I(x1^2)` | Polynomial; `I()` protects `^` from formula interpretation |
| `y ~ x1 - 1` | No intercept (through origin) |
| `y ~ 0 + x1` | Same as above: no intercept |
| `y ~ log(income)` | Log transformation applied inline |
| `y ~ (x1 + x2 + x3)^2` | All main effects and two-way interactions |
| `y ~ .` | All other columns in the data frame as predictors |

### Categorical Variables (Factors)

```r
# Automatic: character columns are treated as factors
fit <- lm(y ~ region, data = df)

# Explicit factor conversion
fit <- lm(y ~ factor(region), data = df)

# Set reference level
df$region <- relevel(factor(df$region), ref = "West")
fit <- lm(y ~ region, data = df)

# Or use C() in formula (less common in R than in Python)
# R uses relevel() or contrasts() instead
```

### Contrast Coding

R uses treatment (dummy) coding by default. The first level of a factor
(alphabetically, or as set by `levels()`) is the reference.

```r
# View current contrasts
contrasts(factor(df$region))

# Set sum (deviation) coding
contrasts(df$region) <- contr.sum(nlevels(df$region))
fit <- lm(y ~ region, data = df)

# Set Helmert coding
contrasts(df$region) <- contr.helmert(nlevels(df$region))

# Set custom reference level
df$region <- relevel(factor(df$region), ref = "West")
```

### Protecting Operators with I()

In formulas, `^` means interaction level, `+` means additive terms, `*` means
interaction. To use them as arithmetic, wrap in `I()`:

```r
# WRONG: ^ means interaction power, not exponent
y ~ x1^2        # same as y ~ x1 (x1 interacted with itself = x1)

# CORRECT: I() protects the arithmetic
y ~ x1 + I(x1^2)           # x1 and x1-squared
y ~ I(x1 + x2)             # sum of x1 and x2 as single predictor
y ~ I(log(x1) * x2)        # product of log(x1) and x2
```

### Updating Formulas

```r
# Start with a base model
fit1 <- lm(y ~ x1, data = df)

# Add a variable
fit2 <- update(fit1, . ~ . + x2)      # y ~ x1 + x2

# Remove a variable
fit3 <- update(fit2, . ~ . - x2)      # back to y ~ x1

# Change the response
fit4 <- update(fit1, log(y) ~ .)      # log(y) ~ x1
```

---

## Weighted Least Squares

```r
# Weights inversely proportional to variance
fit_wls <- lm(y ~ x1 + x2, data = df, weights = w)

# Common: weight by group size
fit_wls <- lm(y ~ x1, data = df, weights = n_obs)

# Common: weight by inverse variance
fit_wls <- lm(y ~ x1, data = df, weights = 1 / variance)
```

`weights` in `lm()` are proportional to the inverse of the error variance.
Larger weight = more precise observation = more influence.

WLS is NOT survey-weighted regression. For complex survey designs with
stratification, clustering, and finite population corrections, use the
`survey-r` skill instead.

---

## Model Matrix

The model matrix (design matrix) is the matrix X that R constructs from the
formula:

```r
# Extract the model matrix from a fitted model
model.matrix(fit)

# Construct model matrix from a formula + data without fitting
X <- model.matrix(~ x1 + x2, data = df)

# Check column names (useful for understanding coding)
colnames(model.matrix(fit))
```

The model matrix shows exactly how R encodes variables -- factor levels become
dummy columns, interactions become product columns.

---

## anova() vs summary()

Both analyze the model, but they answer different questions:

### summary(fit): Coefficient-Level Tests

- Tests each coefficient individually: is this coefficient different from zero?
- t-tests with associated p-values
- Reports R-squared, adjusted R-squared, overall F-test

### anova(fit): Sequential (Type I) Tests

```r
# Type I SS: tests each term in the order it appears in the formula
anova(fit)
# Tests: x1 first (given intercept), then x2 (given intercept + x1)
```

Order matters for Type I sums of squares. The first variable gets credit for
shared variance.

### anova(fit1, fit2): Model Comparison

```r
fit1 <- lm(y ~ x1, data = df)
fit2 <- lm(y ~ x1 + x2, data = df)

# F-test comparing nested models
anova(fit1, fit2)
# Tests: is the additional variable x2 significant?
```

### car::Anova(): Type II/III Tests

```r
library(car)

# Type II SS: tests each term controlling for all others at the same level
Anova(fit, type = "II")

# Type III SS: tests each term controlling for all other terms
Anova(fit, type = "III")
```

- Type II: recommended for models without interactions
- Type III: recommended for models with interactions (tests main effects
  controlling for the interaction)
- Type III requires sum-coded contrasts for sensible interpretation of main
  effects in the presence of interactions

---

## MASS Extras

### Robust Regression (rlm)

M-estimation for regression that is resistant to outliers:

```r
library(MASS)

# Default: Huber's M-estimator
fit_rlm <- rlm(y ~ x1 + x2, data = df)

# Bisquare (Tukey) M-estimator (more resistant to outliers)
fit_rlm <- rlm(y ~ x1 + x2, data = df, method = "MM")

summary(fit_rlm)
```

Note: `rlm()` does not produce p-values in its summary by default. Use
`sfsmisc::f.robftest()` or the `robustbase` package for inference.

### stepAIC for Model Selection

```r
library(MASS)

full_model <- lm(y ~ x1 + x2 + x3 + x4, data = df)

# Forward selection
fit_step <- stepAIC(lm(y ~ 1, data = df),
                    scope = list(upper = full_model),
                    direction = "forward",
                    trace = FALSE)

# Backward elimination
fit_step <- stepAIC(full_model, direction = "backward", trace = FALSE)

# Both directions
fit_step <- stepAIC(full_model, direction = "both", trace = FALSE)

cat("Selected model:\n")
print(formula(fit_step))
```

---

## Quick Comparison: R stats vs statsmodels

| Task | R (base stats) | Python (statsmodels) |
|------|---------------|---------------------|
| OLS | `lm(y ~ x, data = df)` | `smf.ols("y ~ x", data=df).fit()` |
| Requires .fit() | No | **Yes** |
| Formula quoting | Unquoted | String |
| Coefficients | `coef(fit)` | `fit.params` |
| Standard errors | `summary(fit)$coefficients[,2]` | `fit.bse` |
| Confidence intervals | `confint(fit)` | `fit.conf_int()` |
| Predictions | `predict(fit, newdata)` | `fit.predict(newdata)` |
| Prediction intervals | `predict(fit, newdata, interval = "prediction")` | `fit.get_prediction(newdata).summary_frame()` |
| Residuals | `residuals(fit)` | `fit.resid` |
| R-squared | `summary(fit)$r.squared` | `fit.rsquared` |
| AIC | `AIC(fit)` | `fit.aic` |
| Model comparison | `anova(fit1, fit2)` | `fit.compare_f_test(fit_restricted)` |
| Tidy output | `broom::tidy(fit)` | `fit.summary2().tables[1]` |
| Intercept handling | Auto-included | Auto-included (formula) / manual (array) |

Key differences:
- R's `lm()` returns a fitted model directly; statsmodels requires a separate
  `.fit()` call
- R's `predict()` supports `interval = "prediction"` natively; statsmodels
  requires `get_prediction()`
- R's formula is unquoted (`y ~ x`); statsmodels uses strings (`"y ~ x"`)
- R's `anova()` for model comparison is simpler than statsmodels' approach
- broom provides much cleaner tidy output than statsmodels' summary parsing

---

## References

- R Core Team (2025). R: A Language and Environment for Statistical Computing.
  R Foundation for Statistical Computing, Vienna, Austria.
- Chambers, J.M. & Hastie, T.J. (1992). *Statistical Models in S*. Chapman & Hall.
- Venables, W.N. & Ripley, B.D. (2002). *Modern Applied Statistics with S*,
  4th ed. Springer. (MASS package reference)
- Fox, J. & Weisberg, S. (2019). *An R Companion to Applied Regression*, 3rd ed.
  Sage. (car package reference)
