# R Stats Robust Standard Errors Reference

Robust, clustered, and HAC standard errors using `sandwich` and `lmtest`.
Covers `vcovHC()` (HC0-HC4), `vcovCL()` (clustered), `vcovHAC()` (Newey-West),
`vcovBS()` (bootstrap), and `coeftest()` for inference with custom covariance
matrices. sandwich 3.1-1, lmtest 0.9-40.

---

## Contents

- [The sandwich + lmtest Pattern](#the-sandwich--lmtest-pattern)
- [Heteroskedasticity-Consistent (HC) SEs](#heteroskedasticity-consistent-hc-ses)
- [Clustered Standard Errors](#clustered-standard-errors)
- [HAC Standard Errors (Newey-West)](#hac-standard-errors-newey-west)
- [Bootstrap Standard Errors](#bootstrap-standard-errors)
- [Using Robust SEs with Other Functions](#using-robust-ses-with-other-functions)
- [Comparison to Python](#comparison-to-python)

---

## The sandwich + lmtest Pattern

R's standard approach for robust SEs uses two packages together:

1. **sandwich**: Computes the robust variance-covariance matrix (`vcovHC`,
   `vcovCL`, `vcovHAC`, etc.)
2. **lmtest**: Provides `coeftest()` to display coefficients with any
   user-supplied vcov matrix

```r
library(sandwich)
library(lmtest)

# Step 1: Fit the model with standard (non-robust) SEs
fit <- lm(y ~ x1 + x2, data = df)

# Step 2: Compute robust vcov matrix
V <- vcovHC(fit, type = "HC1")

# Step 3: Display coefficients with robust SEs
coeftest(fit, vcov = V)
```

This pattern works with `lm()`, `glm()`, and many other model classes. The
point estimates (coefficients) do not change -- only the standard errors,
t-statistics, and p-values change.

---

## Heteroskedasticity-Consistent (HC) SEs

### vcovHC() Types

```r
library(sandwich)

fit <- lm(y ~ x1 + x2, data = df)

# HC0: White (1980) -- no degrees-of-freedom correction
V0 <- vcovHC(fit, type = "HC0")

# HC1: White with small-sample correction (n/(n-k) scaling)
# Equivalent to Stata's "robust" option
V1 <- vcovHC(fit, type = "HC1")

# HC2: Uses leverage weights (1 - h_ii)
V2 <- vcovHC(fit, type = "HC2")

# HC3: Jackknife-like correction -- most conservative
# Recommended for small samples
V3 <- vcovHC(fit, type = "HC3")

# HC4: Further refinement of HC3
V4 <- vcovHC(fit, type = "HC4")

# HC4m and HC5: additional variants
V4m <- vcovHC(fit, type = "HC4m")
V5  <- vcovHC(fit, type = "HC5")
```

### Which HC Type to Use

| Type | Formula | When to Use |
|------|---------|-------------|
| HC0 | White (1980) | Large samples; matches asymptotic theory |
| HC1 | HC0 * n/(n-k) | **Default recommendation** -- matches Stata's `robust` |
| HC2 | Leverage-adjusted | Medium samples; accounts for high-leverage points |
| HC3 | Jackknife-approximation | **Small samples** (n < 50); most conservative |
| HC4 | Further HC3 refinement | Small samples with high-leverage outliers |

HC1 is the most commonly used in empirical work. HC3 is preferred for small
samples.

### Displaying Results

```r
library(lmtest)

# Full coefficient table with HC1 robust SEs
coeftest(fit, vcov = vcovHC(fit, type = "HC1"))

# Compare standard vs robust SEs side by side
cat("Standard SEs:\n")
print(coeftest(fit))
cat("\nRobust SEs (HC1):\n")
print(coeftest(fit, vcov = vcovHC(fit, type = "HC1")))
```

---

## Clustered Standard Errors

### One-Way Clustering

```r
library(sandwich)
library(lmtest)

fit <- lm(y ~ x1 + x2, data = df)

# Cluster by state (variable in the data)
V_cl <- vcovCL(fit, cluster = df$state)
coeftest(fit, vcov = V_cl)

# Using a formula interface
V_cl <- vcovCL(fit, cluster = ~ state)
coeftest(fit, vcov = V_cl)
```

### Two-Way Clustering

```r
# Cluster by both state and year (multiway)
V_2way <- vcovCL(fit, cluster = ~ state + year)
coeftest(fit, vcov = V_2way)

# Using a data frame with multiple cluster variables
V_2way <- vcovCL(fit, cluster = df[, c("state", "year")])
coeftest(fit, vcov = V_2way)
```

### vcovCL Options

```r
# type: "HC0" through "HC3" for the within-cluster adjustment
V_cl <- vcovCL(fit, cluster = ~ state, type = "HC1")

# cadjust: apply small-cluster correction (G/(G-1) where G = number of clusters)
# Default is TRUE
V_cl <- vcovCL(fit, cluster = ~ state, cadjust = TRUE)

# fix: if TRUE, ensure positive semi-definiteness via eigenvalue adjustment
V_cl <- vcovCL(fit, cluster = ~ state, fix = TRUE)
```

### Clustering for GLMs

The same pattern works for `glm()` objects:

```r
fit_logit <- glm(y ~ x1 + x2, data = df, family = binomial)

# Clustered SEs for logistic regression
coeftest(fit_logit, vcov = vcovCL(fit_logit, cluster = df$state))
```

---

## HAC Standard Errors (Newey-West)

For time series data with heteroskedasticity AND autocorrelation:

### Basic Newey-West

```r
library(sandwich)
library(lmtest)

fit <- lm(y ~ x1 + x2, data = df)

# Newey-West with automatic bandwidth selection
V_hac <- vcovHAC(fit)
coeftest(fit, vcov = V_hac)

# Newey-West with manual bandwidth (maxlag)
V_nw <- NeweyWest(fit, lag = 4, prewhite = FALSE)
coeftest(fit, vcov = V_nw)
```

### vcovHAC Options

```r
# Bartlett kernel (default, same as Newey-West)
V_hac <- vcovHAC(fit, kernel = "Bartlett")

# Quadratic Spectral kernel
V_hac <- vcovHAC(fit, kernel = "Quadratic Spectral")

# Parzen kernel
V_hac <- vcovHAC(fit, kernel = "Parzen")

# Custom bandwidth
V_hac <- vcovHAC(fit, bw = 5)
```

### Rule of Thumb for Bandwidth

A common starting point: `floor(0.75 * T^(1/3))` where T is the number of
observations. But automatic bandwidth selection (the default in `vcovHAC()`)
is generally preferred.

---

## Bootstrap Standard Errors

### vcovBS (sandwich 3.1+)

```r
library(sandwich)
library(lmtest)

fit <- lm(y ~ x1 + x2, data = df)

# Pairs bootstrap (resample observations)
V_bs <- vcovBS(fit, R = 999, type = "xy")
coeftest(fit, vcov = V_bs)

# Residual bootstrap (resample residuals)
V_bs_resid <- vcovBS(fit, R = 999, type = "residual")
coeftest(fit, vcov = V_bs_resid)

# Wild bootstrap
V_bs_wild <- vcovBS(fit, R = 999, type = "wild")
coeftest(fit, vcov = V_bs_wild)

# Cluster bootstrap
V_bs_cl <- vcovBS(fit, R = 999, cluster = df$state, type = "xy")
coeftest(fit, vcov = V_bs_cl)
```

### Bootstrap Types

| Type | Description | When to Use |
|------|-------------|-------------|
| `"xy"` | Pairs bootstrap (resample rows) | General heteroskedasticity |
| `"residual"` | Resample residuals | Homoskedastic errors assumed |
| `"wild"` | Wild bootstrap (Rademacher weights) | Heteroskedasticity + small samples |
| `"jackknife"` | Leave-one-out jackknife | Conservative small-sample inference |

---

## Using Robust SEs with Other Functions

### waldtest() with Robust Covariance

```r
library(lmtest)

fit_full <- lm(y ~ x1 + x2 + x3, data = df)
fit_reduced <- lm(y ~ x1, data = df)

# Wald test with robust vcov
waldtest(fit_full, fit_reduced, vcov = vcovHC(fit_full, type = "HC1"))
```

### car::linearHypothesis() with Robust Covariance

```r
library(car)
library(sandwich)

fit <- lm(y ~ x1 + x2 + x3, data = df)

# Joint test: x2 = 0 AND x3 = 0, using robust SEs
linearHypothesis(fit, c("x2 = 0", "x3 = 0"),
                 vcov. = vcovHC(fit, type = "HC1"))

# Test: x1 = x2, using clustered SEs
linearHypothesis(fit, "x1 = x2",
                 vcov. = vcovCL(fit, cluster = df$state))
```

### confint() with Robust Covariance

```r
library(lmtest)

# Robust confidence intervals
coefci(fit, vcov. = vcovHC(fit, type = "HC1"))

# Clustered CI
coefci(fit, vcov. = vcovCL(fit, cluster = df$state))
```

### broom::tidy() with Robust SEs

broom does not natively accept a custom vcov. Use `lmtest::coeftest()` first:

```r
library(broom)
library(lmtest)
library(sandwich)

robust_test <- coeftest(fit, vcov = vcovHC(fit, type = "HC1"))
tidy(robust_test, conf.int = TRUE)
```

### modelsummary with Robust SEs

```r
library(modelsummary)

# Specify vcov in modelsummary (preferred approach)
modelsummary(fit, vcov = "HC1")
modelsummary(fit, vcov = ~state)   # clustered
modelsummary(fit, vcov = ~state + year)  # two-way clustered

# Multiple models with different SEs
modelsummary(
  list("OLS" = fit, "Robust" = fit, "Clustered" = fit),
  vcov = list("iid", "HC1", ~state)
)
```

---

## Comparison to Python

| Task | R (sandwich + lmtest) | Python (statsmodels) |
|------|----------------------|---------------------|
| HC1 robust SEs | `coeftest(fit, vcov = vcovHC(fit, "HC1"))` | `smf.ols(...).fit(cov_type="HC1")` |
| HC3 robust SEs | `coeftest(fit, vcov = vcovHC(fit, "HC3"))` | `smf.ols(...).fit(cov_type="HC3")` |
| One-way clustered | `coeftest(fit, vcov = vcovCL(fit, ~state))` | `.fit(cov_type="cluster", cov_kwds={"groups": df["state"]})` |
| Two-way clustered | `coeftest(fit, vcov = vcovCL(fit, ~state + year))` | Not built-in (use pyfixest) |
| Newey-West | `coeftest(fit, vcov = NeweyWest(fit))` | `.fit(cov_type="HAC", cov_kwds={"maxlags": 4})` |
| Bootstrap | `vcovBS(fit, R = 999)` | Not built-in |

Key difference: R separates estimation (`lm/glm`) from inference (`coeftest` +
custom vcov). Python bakes inference into the `.fit()` call. The R approach is
more flexible -- any vcov matrix can be plugged into any post-estimation function.

---

## References

- Zeileis, A. (2004). "Econometric Computing with HC and HAC Covariance Matrix
  Estimators." *Journal of Statistical Software*, 11(10), 1-17.
- Zeileis, A. (2006). "Object-Oriented Computation of Sandwich Estimators."
  *Journal of Statistical Software*, 16(9), 1-16.
- Zeileis, A., Koell, S., & Graham, N. (2020). "Various Versatile Variances:
  An Object-Oriented Implementation of Clustered Covariances in R." *Journal of
  Statistical Software*, 95(1), 1-36.
- White, H. (1980). "A Heteroskedasticity-Consistent Covariance Matrix Estimator
  and a Direct Test for Heteroskedasticity." *Econometrica*, 48(4), 817-838.
- Newey, W. & West, K. (1987). "A Simple, Positive Semi-Definite,
  Heteroskedasticity and Autocorrelation Consistent Covariance Matrix."
  *Econometrica*, 55(3), 703-708.
