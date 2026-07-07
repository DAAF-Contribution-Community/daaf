# R Stats Diagnostics Reference

Regression diagnostics using `car`, `lmtest`, and base R: VIF, heteroskedasticity
tests, normality tests, specification tests, serial correlation, joint hypothesis
tests, and influence analysis. car 3.1-5, lmtest 0.9-40.

---

## Contents

- [VIF (Multicollinearity)](#vif-multicollinearity)
- [Heteroskedasticity Tests](#heteroskedasticity-tests)
- [Normality Tests](#normality-tests)
- [Specification Tests](#specification-tests)
- [Serial Correlation Tests](#serial-correlation-tests)
- [Joint Hypothesis Tests](#joint-hypothesis-tests)
- [Influence and Outlier Analysis](#influence-and-outlier-analysis)
- [Residual Analysis](#residual-analysis)
- [Diagnostic Checklist](#diagnostic-checklist)
- [Comparison to Python](#comparison-to-python)

---

## VIF (Multicollinearity)

### car::vif()

```r
library(car)

fit <- lm(y ~ x1 + x2 + x3, data = df)

# VIF for each predictor
vif(fit)
# Returns named vector: x1, x2, x3

# For models with interactions or categorical variables (GVIF)
fit_cat <- lm(y ~ x1 + x2 * factor(group), data = df)
vif(fit_cat)
# Returns matrix with GVIF, Df, GVIF^(1/(2*Df))
```

### Interpretation

| VIF Value | Interpretation |
|-----------|----------------|
| 1 | No collinearity |
| 1-5 | Moderate (usually acceptable) |
| 5-10 | Concerning |
| > 10 | Serious multicollinearity |

For GVIF (Generalized VIF, used when a factor has multiple dummies), compare
`GVIF^(1/(2*Df))` to the thresholds above.

### Condition Number

```r
# From the model matrix
X <- model.matrix(fit)
kappa(X)          # condition number
# > 30 suggests multicollinearity

# Alternative: via eigen decomposition
eigen_vals <- eigen(crossprod(X))$values
sqrt(max(eigen_vals) / min(eigen_vals))
```

---

## Heteroskedasticity Tests

### Breusch-Pagan Test (lmtest)

```r
library(lmtest)

fit <- lm(y ~ x1 + x2, data = df)

# Standard Breusch-Pagan
bptest(fit)

# Studentized Breusch-Pagan (default, more robust)
bptest(fit, studentize = TRUE)

# Against specific variables
bptest(fit, ~ x1 + I(x1^2), data = df)
```

- H0: homoskedasticity (constant variance)
- Reject if p-value < 0.05 -- heteroskedasticity detected
- `studentize = TRUE` (default) is the Koenker variant, more robust to
  non-normality

### NCV Test (car)

```r
library(car)

# Non-Constant Variance test
ncvTest(fit)

# Against specific variable
ncvTest(fit, ~ x1)
```

- Equivalent to a score test for heteroskedasticity
- H0: constant variance

### What to Do If Heteroskedasticity Detected

1. Use robust SEs: `coeftest(fit, vcov = vcovHC(fit, type = "HC1"))`
2. Use WLS if variance structure is known: `lm(y ~ x, weights = 1/var_x)`
3. Transform the DV: `lm(log(y) ~ x)` if variance is proportional to the mean
4. Use a GLM with appropriate variance function (e.g., Gamma for positive data)

---

## Normality Tests

### Shapiro-Wilk Test

```r
# Test residuals for normality
shapiro.test(residuals(fit))

# H0: residuals are normally distributed
# Recommended for n < 5000
```

### Jarque-Bera Test

```r
library(tseries)
jarque.bera.test(residuals(fit))

# Tests skewness and kurtosis jointly
# H0: residuals are normally distributed
```

### Kolmogorov-Smirnov Test

```r
# Against a normal distribution
ks.test(residuals(fit), "pnorm",
        mean = mean(residuals(fit)),
        sd = sd(residuals(fit)))
```

### QQ Plot (Visual)

```r
# Base R QQ plot
qqnorm(residuals(fit))
qqline(residuals(fit), col = "red")

# car::qqPlot (with confidence envelope)
library(car)
qqPlot(fit)
# Adds 95% confidence bands -- points outside bands are potential outliers
```

### Practical Note

In large samples (n > 1000), normality tests almost always reject because
any tiny departure becomes statistically detectable. Focus on the degree of
non-normality (examine QQ plots, skewness, kurtosis numerically) rather than
relying solely on p-values. OLS inference is robust to moderate non-normality
when n is large (central limit theorem).

---

## Specification Tests

### RESET Test (lmtest)

Ramsey's Regression Equation Specification Error Test:

```r
library(lmtest)

# Default: adds y-hat^2 and y-hat^3
resettest(fit)

# Custom power
resettest(fit, power = 2:4)

# Type: "fitted" (default) or "regressor" or "princomp"
resettest(fit, type = "fitted")
```

- H0: model is correctly specified
- Rejection suggests omitted variables, wrong functional form, or missing
  interactions

### Harvey-Collier Test (lmtest)

```r
harvtest(fit)
# Tests linearity using recursive residuals
# H0: relationship is linear
```

### Rainbow Test (lmtest)

```r
raintest(fit)
# Tests for non-linearity by fitting the model to a subset of data
# H0: model is linear
```

---

## Serial Correlation Tests

### Durbin-Watson Test (lmtest)

```r
library(lmtest)

dwtest(fit)
# H0: no first-order autocorrelation
# DW ~= 2: no autocorrelation
# DW < 2: positive autocorrelation
# DW > 2: negative autocorrelation

# Alternative: test for negative autocorrelation
dwtest(fit, alternative = "less")
```

Cannot be used when the model contains a lagged dependent variable.

### Breusch-Godfrey Test (lmtest)

More general than Durbin-Watson; works with lagged dependent variables:

```r
bgtest(fit, order = 4)
# Tests for autocorrelation up to order 4
# H0: no serial correlation

# Higher order for monthly data
bgtest(fit, order = 12)
```

### Ljung-Box Test (base R)

```r
Box.test(residuals(fit), lag = 10, type = "Ljung-Box")
# H0: residuals are independently distributed
# Primarily for time series residuals
```

---

## Joint Hypothesis Tests

### car::linearHypothesis()

Test linear restrictions on model coefficients:

```r
library(car)

fit <- lm(y ~ x1 + x2 + x3, data = df)

# Test: x1 = 0 (same as t-test from summary)
linearHypothesis(fit, "x1 = 0")

# Joint test: x1 = 0 AND x2 = 0
linearHypothesis(fit, c("x1 = 0", "x2 = 0"))

# Test equality: x1 = x2
linearHypothesis(fit, "x1 = x2")

# Test: x1 + x2 = 1
linearHypothesis(fit, "x1 + x2 = 1")

# Multiple restrictions
linearHypothesis(fit, c("x1 = x2", "x2 = x3"))
```

### With Robust Covariance

```r
library(sandwich)

# Joint test with HC1 robust SEs
linearHypothesis(fit, c("x1 = 0", "x2 = 0"),
                 vcov. = vcovHC(fit, type = "HC1"))

# With clustered SEs
linearHypothesis(fit, c("x1 = 0", "x2 = 0"),
                 vcov. = vcovCL(fit, cluster = df$state))
```

### Wald Test (lmtest)

```r
library(lmtest)

fit_full <- lm(y ~ x1 + x2 + x3, data = df)
fit_reduced <- lm(y ~ x1, data = df)

# Compare nested models
waldtest(fit_full, fit_reduced)

# With robust vcov
waldtest(fit_full, fit_reduced, vcov = vcovHC(fit_full, type = "HC1"))
```

### Type II and Type III Anova (car)

```r
library(car)

# Type II SS: tests each term controlling for all others at same level
Anova(fit, type = "II")

# Type III SS: tests each term controlling for all other terms
# Recommended for models with interactions
Anova(fit, type = "III")

# With robust SEs (white.adjust)
Anova(fit, type = "III", white.adjust = "hc3")
```

---

## Influence and Outlier Analysis

### Base R Influence Measures

```r
fit <- lm(y ~ x1 + x2, data = df)

# Cook's distance
cooks.distance(fit)
# Rule of thumb: > 4/n is influential

# Leverage (hat values)
hatvalues(fit)
# Rule of thumb: > 2*(k+1)/n is high leverage

# DFBETAS (influence on each coefficient)
dfbetas(fit)
# Rule of thumb: |DFBETAS| > 2/sqrt(n)

# DFFITS
dffits(fit)
# Rule of thumb: |DFFITS| > 2*sqrt((k+1)/n)

# Studentized residuals
rstudent(fit)
# |rstudent| > 2 is potential outlier

# Comprehensive influence measures
influence.measures(fit)
# Returns: dfbetas, dffits, cov.r, cook.d, hat
# Flags influential observations with asterisks
```

### car Influence Diagnostics

```r
library(car)

# Influence plot (bubble chart: hat vs studentized residual, size = Cook's D)
influencePlot(fit)

# Influence index plot (Cook's D by observation number)
influenceIndexPlot(fit)

# Added-variable plots (partial regression plots)
avPlots(fit)

# Component-plus-residual plots (check linearity)
crPlots(fit)
```

### Outlier Test

```r
library(car)

# Bonferroni-corrected test for the largest studentized residual
outlierTest(fit)
# If p < 0.05, the most extreme observation is a significant outlier
```

---

## Residual Analysis

### Residual Types

```r
# Raw residuals
residuals(fit)                    # or: resid(fit)

# Standardized residuals (divided by sigma * sqrt(1 - h_ii))
rstandard(fit)

# Studentized (externally) residuals (leave-one-out)
rstudent(fit)

# For GLMs: Pearson and deviance residuals
residuals(fit_glm, type = "pearson")
residuals(fit_glm, type = "deviance")
residuals(fit_glm, type = "response")    # raw residuals
residuals(fit_glm, type = "working")     # working residuals
```

### Diagnostic Plots (Base R)

```r
# Four standard diagnostic plots
par(mfrow = c(2, 2))
plot(fit)
par(mfrow = c(1, 1))

# Plot 1: Residuals vs Fitted -- check linearity + homoskedasticity
# Plot 2: Normal QQ -- check normality
# Plot 3: Scale-Location (sqrt |standardized residuals| vs fitted) -- check homoskedasticity
# Plot 4: Residuals vs Leverage -- identify influential points
```

### Using broom::augment()

```r
library(broom)

aug <- augment(fit)
# Columns: .fitted, .resid, .hat, .sigma, .cooksd, .std.resid
# Plus all original data columns

# Observations with high Cook's D
aug[aug$.cooksd > 4 / nobs(fit), ]

# Observations with high leverage
aug[aug$.hat > 2 * (length(coef(fit))) / nobs(fit), ]
```

---

## Diagnostic Checklist

| Assumption | Test | R Code | H0 |
|------------|------|--------|-----|
| Homoskedasticity | Breusch-Pagan | `lmtest::bptest(fit)` | Constant variance |
| Homoskedasticity | NCV | `car::ncvTest(fit)` | Constant variance |
| Normality | Shapiro-Wilk | `shapiro.test(resid(fit))` | Normal residuals |
| Normality | Jarque-Bera | `tseries::jarque.bera.test(resid(fit))` | Normal residuals |
| Correct specification | RESET | `lmtest::resettest(fit)` | Correct specification |
| Linearity | Harvey-Collier | `lmtest::harvtest(fit)` | Linear relationship |
| No multicollinearity | VIF | `car::vif(fit)` | VIF < 10 |
| No serial correlation | Durbin-Watson | `lmtest::dwtest(fit)` | No autocorrelation |
| No serial correlation | Breusch-Godfrey | `lmtest::bgtest(fit)` | No autocorrelation |
| No influential points | Cook's D | `cooks.distance(fit)` | D < 4/n |
| No outliers | Bonferroni outlier | `car::outlierTest(fit)` | No outliers |
| Joint significance | F-test | `car::linearHypothesis(fit, ...)` | Coefficients = 0 |

---

## Comparison to Python

| Diagnostic | R | Python (statsmodels) |
|-----------|---|---------------------|
| VIF | `car::vif(fit)` (one call) | `variance_inflation_factor()` (loop over columns) |
| Breusch-Pagan | `lmtest::bptest(fit)` | `het_breuschpagan(resid, exog)` |
| White test | `skedastic::white_lm(fit)` | `het_white(resid, exog)` |
| RESET test | `lmtest::resettest(fit)` | `linear_reset(fit)` |
| Durbin-Watson | `lmtest::dwtest(fit)` | `durbin_watson(resid)` |
| Breusch-Godfrey | `lmtest::bgtest(fit)` | `acorr_breusch_godfrey(fit)` |
| Cook's D | `cooks.distance(fit)` | `OLSInfluence(fit).cooks_distance` |
| Linear hypothesis | `car::linearHypothesis(fit, ...)` | `fit.f_test(r_matrix)` |
| QQ plot | `qqPlot(fit)` (car, with CI) | `qqplot(resid, line='45')` |
| Influence plot | `influencePlot(fit)` | Manual construction |
| Shapiro-Wilk | `shapiro.test(resid(fit))` | `scipy.stats.shapiro(resid)` |

Key difference: R provides single-function calls for most diagnostics (`vif(fit)`,
`bptest(fit)`). Python typically requires extracting model components first and
passing them individually.

---

## References

- Fox, J. & Weisberg, S. (2019). *An R Companion to Applied Regression*, 3rd ed.
  Sage, Thousand Oaks CA.
- Zeileis, A. & Hothorn, T. (2002). "Diagnostic Checking in Regression
  Relationships." *R News*, 2(3), 7-10.
- Belsley, D.A., Kuh, E., & Welsch, R.E. (1980). *Regression Diagnostics*.
  Wiley.
- Cook, R.D. & Weisberg, S. (1982). *Residuals and Influence in Regression*.
  Chapman and Hall.
