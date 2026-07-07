# R Stats Gotchas and Common Pitfalls

Known sharp edges, silent failures, and library-specific behaviors in R's
statistical modeling ecosystem. Each section describes a problem, why it
happens, and how to fix it.

---

## Contents

1. [Formula I() for Arithmetic](#1-formula-i-for-arithmetic)
2. [Factor Contrasts and Reference Levels](#2-factor-contrasts-and-reference-levels)
3. [na.action Behavior](#3-naaction-behavior)
4. [predict() type Argument](#4-predict-type-argument)
5. [summary() vs anova()](#5-summary-vs-anova)
6. [Convergence Warnings in GLMs](#6-convergence-warnings-in-glms)
7. [r-stats vs fixest Boundary](#7-r-stats-vs-fixest-boundary)
8. [poly() vs I(x^2) in Formulas](#8-poly-vs-ix2-in-formulas)
9. [scope() and Environments in lm()](#9-scope-and-environments-in-lm)
10. [GLM Dispersion and Standard Errors](#10-glm-dispersion-and-standard-errors)

---

## 1. Formula I() for Arithmetic

**This is the most common R formula mistake.** In R formulas, `+`, `*`, `^`,
and `-` have special meanings (additive terms, interactions, interaction order,
term removal). To use them as arithmetic, wrap in `I()`.

```r
# WRONG: ^ means interaction power in formulas
lm(y ~ x1^2, data = df)
# This is the same as lm(y ~ x1) -- x1 "crossed" with itself is just x1

# CORRECT: I() protects arithmetic
lm(y ~ x1 + I(x1^2), data = df)
# Now x1^2 is truly x1-squared

# WRONG: * means interaction in formulas
lm(y ~ x1 * x2, data = df)
# This fits x1 + x2 + x1:x2 (main effects plus interaction)

# CORRECT: if you want the arithmetic product as one predictor
lm(y ~ I(x1 * x2), data = df)
# Now x1*x2 is a single product variable

# WRONG: + means "add this term" in formulas
lm(y ~ x1 + x2, data = df)
# This fits two separate predictors

# CORRECT: if you want the sum as one predictor
lm(y ~ I(x1 + x2), data = df)
# Now (x1 + x2) is a single combined predictor
```

### When I() is NOT Needed

Functions like `log()`, `sqrt()`, `abs()`, `exp()` work directly in formulas
because they are not formula operators:

```r
# These all work without I()
lm(y ~ log(x1), data = df)
lm(y ~ sqrt(x1), data = df)
lm(y ~ x1 + log(x2), data = df)
```

---

## 2. Factor Contrasts and Reference Levels

### Default Behavior

R uses treatment (dummy) coding by default. The first level alphabetically (or
as set by `levels()`) is the reference category and is dropped from the model.

```r
# If region has levels c("East", "North", "South", "West")
# "East" is the reference by default (alphabetical first)
fit <- lm(y ~ factor(region), data = df)
coef(fit)
# (Intercept)           -- mean for East
# factor(region)North   -- difference from East
# factor(region)South   -- difference from East
# factor(region)West    -- difference from East
```

### Changing the Reference Level

```r
# Method 1: relevel (most common)
df$region <- relevel(factor(df$region), ref = "West")
fit <- lm(y ~ region, data = df)

# Method 2: reorder factor levels
df$region <- factor(df$region, levels = c("West", "East", "North", "South"))

# Method 3: contrasts function
contrasts(df$region) <- contr.treatment(4, base = 4)
# base = 4 makes the 4th level the reference
```

### Sum (Deviation) Coding

Each level is compared to the grand mean instead of a reference category:

```r
contrasts(df$region) <- contr.sum(nlevels(df$region))
fit <- lm(y ~ region, data = df)
# Now coefficients are deviations from the grand mean
# The last level's coefficient is -(sum of other coefficients)
```

Sum coding is needed when interpreting main effects in models with interactions
(Type III SS).

### Gotcha: Character vs Factor

R's `lm()` automatically converts character columns to factors. But the factor
ordering may not be what you expect:

```r
# Character column: levels are alphabetical
df$group <- c("control", "treatment", "control", "treatment")
lm(y ~ group, data = df)
# "control" is reference (alphabetical first)

# Explicit factor with custom order
df$group <- factor(df$group, levels = c("control", "treatment"))
# Now "control" is explicitly first
```

---

## 3. na.action Behavior

### Default: na.omit

R's default `na.action` is `na.omit` -- rows with any NA in the variables used
by the formula are silently dropped.

```r
fit <- lm(y ~ x1 + x2, data = df)
# If df has 100 rows but 5 have NA in x1 or x2:
nobs(fit)  # 95 (5 rows silently dropped)
```

### Gotcha: Mismatched Observations

When comparing models or computing diagnostics, NA handling can cause
observation count mismatches:

```r
fit1 <- lm(y ~ x1, data = df)       # drops rows where x1 is NA
fit2 <- lm(y ~ x1 + x2, data = df)  # drops rows where x1 OR x2 is NA

# If x2 has additional NAs, fit1 and fit2 use different samples
nobs(fit1)   # may be 98
nobs(fit2)   # may be 95

# This makes anova() comparison invalid
anova(fit1, fit2)   # WARNING: models not on same sample

# Fix: use complete cases for both
cc <- complete.cases(df[, c("y", "x1", "x2")])
df_cc <- df[cc, ]
fit1 <- lm(y ~ x1, data = df_cc)
fit2 <- lm(y ~ x1 + x2, data = df_cc)
```

### Changing na.action

```r
# Fail if any NA present
fit <- lm(y ~ x1, data = df, na.action = na.fail)

# Exclude NAs (default)
fit <- lm(y ~ x1, data = df, na.action = na.omit)

# Keep NAs in residuals/fitted (useful for time series alignment)
fit <- lm(y ~ x1, data = df, na.action = na.exclude)
# residuals(fit) will have NA in positions of dropped rows
```

### Best Practice

Always check observation counts after fitting:

```r
cat("Input rows:", nrow(df), "\n")
cat("Observations used:", nobs(fit), "\n")
cat("Rows dropped:", nrow(df) - nobs(fit), "\n")
```

---

## 4. predict() type Argument

### For lm(): No type Needed

```r
fit <- lm(y ~ x1, data = df)
predict(fit, newdata = new_df)            # predicted y values
predict(fit, newdata = new_df, type = "response")  # same thing
```

### For glm(): type is Critical

```r
fit <- glm(y ~ x1, data = df, family = binomial)

# type = "link": returns log-odds (linear predictor eta)
predict(fit, newdata = new_df, type = "link")
# Range: (-Inf, +Inf)

# type = "response": returns probabilities (response scale)
predict(fit, newdata = new_df, type = "response")
# Range: (0, 1) for binomial

# DEFAULT is "link" -- this catches many people off guard
predict(fit, newdata = new_df)  # returns log-odds, NOT probabilities
```

**The default for `glm()` is `type = "link"`, NOT `type = "response"`.** This
is the single most common GLM prediction error. Always specify `type`
explicitly.

### For MASS::polr(): type Options

```r
fit <- MASS::polr(rating ~ x1, data = df)

predict(fit, type = "class")   # predicted category (default)
predict(fit, type = "probs")   # matrix of category probabilities
```

---

## 5. summary() vs anova()

### summary() Tests Each Coefficient Individually

```r
fit <- lm(y ~ x1 + x2 + x3, data = df)
summary(fit)
# Each coefficient gets its own t-test: is this coefficient != 0,
# controlling for all other variables?
```

### anova() Tests Sequentially (Type I SS)

```r
anova(fit)
# Tests x1 first (given intercept)
# Then x2 (given intercept + x1)
# Then x3 (given intercept + x1 + x2)
# ORDER MATTERS: reordering variables changes p-values
```

### Gotcha: anova() Order Dependence

```r
fit_a <- lm(y ~ x1 + x2, data = df)
fit_b <- lm(y ~ x2 + x1, data = df)

# Coefficients are identical
all.equal(coef(fit_a), coef(fit_b)[names(coef(fit_a))])  # TRUE

# But anova() p-values may differ!
anova(fit_a)  # tests x1 first
anova(fit_b)  # tests x2 first
```

### Fix: Use Type II or III SS

```r
library(car)

# Type II: order-independent (no interactions)
Anova(fit, type = "II")

# Type III: order-independent (with interactions)
# Requires sum contrasts for interpretable main effects
options(contrasts = c("contr.sum", "contr.poly"))
Anova(fit, type = "III")
```

---

## 6. Convergence Warnings in GLMs

### Symptoms

```
Warning: glm.fit: algorithm did not converge
Warning: glm.fit: fitted probabilities numerically 0 or 1 occurred
```

### Common Causes

**Perfect separation** (logit/probit): a predictor perfectly separates y = 0
from y = 1. The MLE diverges to +/- infinity.

```r
# Diagnose: check for zero cells in cross-tabulation
for (var in c("x1_binary", "x2_binary")) {
  tab <- table(df$y, df[[var]])
  if (any(tab == 0)) {
    cat("Potential separation:", var, "\n")
    print(tab)
  }
}

# Large coefficients or SEs indicate separation
coef_table <- summary(fit)$coefficients
cat("Large coefficients:\n")
print(coef_table[abs(coef_table[, "Estimate"]) > 10, ])
```

**Fixes:**
1. Remove the separating variable
2. Combine sparse categories
3. Use Firth's penalized logistic regression: `logistf::logistf(y ~ x, data = df)`
4. Use `brglm2` package for bias-reduced GLM fitting

**Scale issues**: predictors on vastly different scales slow convergence.

```r
# Standardize predictors
df$x1_std <- scale(df$x1)
df$x2_std <- scale(df$x2)
fit <- glm(y ~ x1_std + x2_std, data = df, family = binomial)
```

**Optimizer settings:**

```r
# Increase iterations
glm(y ~ x, data = df, family = binomial,
    control = glm.control(maxit = 100))

# Change epsilon (convergence tolerance)
glm(y ~ x, data = df, family = binomial,
    control = glm.control(epsilon = 1e-10))
```

---

## 7. r-stats vs fixest Boundary

### When to Stay in base R stats

- GLMs: `glm()` supports all families/links; fixest `feglm()` is limited
- Classical tests: `t.test()`, `chisq.test()`, etc. -- no fixest equivalent
- Time series: `arima()`, `acf()`, `stl()` -- not in fixest
- Model diagnostics: `car::vif()`, `lmtest::bptest()`, influence measures
- Marginal effects: `marginaleffects::avg_slopes()` works with `glm()` results
- Ordered/multinomial models: `MASS::polr()`, `nnet::multinom()`

### When to Switch to fixest

- Multi-way fixed effects: `feols(y ~ x | fe1 + fe2, data = df)` -- much faster
  than dummy variables in `lm()`
- Clustered SEs as primary inference: fixest integrates `vcov` into the
  estimation call; base R requires post-hoc `sandwich + lmtest`
- DiD / event studies: fixest provides `sunab()` and related estimators
- Poisson with FE: `fepois()` -- base R has no equivalent
- Multiple estimations: fixest `feols(y ~ csw(x1, x2) | fe, ...)` runs many
  specifications in one call
- Publication tables: fixest `etable()` is purpose-built for regression tables

### Gotcha: Mixing ecosystems

Base R `lm()` objects and fixest `fixest` objects have different class structures.
Functions designed for one may not work with the other:

```r
# car::vif() works with lm() but NOT fixest
fit_lm <- lm(y ~ x1 + x2, data = df)
car::vif(fit_lm)      # works

fit_fe <- fixest::feols(y ~ x1 + x2, data = df)
# car::vif(fit_fe)    # may error or give unexpected results

# broom::tidy() works with both
broom::tidy(fit_lm)
broom::tidy(fit_fe)

# modelsummary works with both
modelsummary::modelsummary(list("lm" = fit_lm, "fixest" = fit_fe))
```

---

## 8. poly() vs I(x^2) in Formulas

```r
# poly(x, 2): ORTHOGONAL polynomials (default)
lm(y ~ poly(x, 2), data = df)
# Coefficients represent orthogonal polynomial components
# NOT directly interpretable as "effect of x" and "effect of x-squared"

# poly(x, 2, raw = TRUE): RAW polynomials
lm(y ~ poly(x, 2, raw = TRUE), data = df)
# Coefficients are for x and x^2 directly -- same as I(x^2)

# I(x^2): always raw
lm(y ~ x + I(x^2), data = df)
# Same as poly(x, 2, raw = TRUE) but more explicit
```

`poly()` with default orthogonal polynomials avoids multicollinearity between
x and x^2, but the coefficients are harder to interpret. For research reporting,
`x + I(x^2)` or `poly(x, 2, raw = TRUE)` is preferred because coefficients
correspond directly to the linear and quadratic terms.

---

## 9. scope() and Environments in lm()

### Gotcha: Variables Not Found

```r
# This fails if x1 is not in df
fit <- lm(y ~ x1, data = df)
# Error: object 'x1' not found

# This works but is fragile (uses global environment)
x1 <- c(1, 2, 3, 4, 5)
y <- c(2, 4, 5, 4, 5)
fit <- lm(y ~ x1)  # no data argument -- searches global env
```

Best practice: always pass `data = df` and ensure all variables are columns.

### Gotcha: predict() with New Data

```r
# This works
fit <- lm(y ~ x1 + x2, data = df)
predict(fit, newdata = data.frame(x1 = 5, x2 = 3))

# This fails: variable names must match exactly
predict(fit, newdata = data.frame(X1 = 5, X2 = 3))
# Error: variables not found

# This fails: factor levels must match
df$group <- factor(df$group, levels = c("A", "B", "C"))
fit <- lm(y ~ group, data = df)
predict(fit, newdata = data.frame(group = "D"))
# Error: factor has new levels
```

---

## 10. GLM Dispersion and Standard Errors

### Poisson and Binomial: Dispersion Fixed at 1

For `family = poisson` and `family = binomial`, R assumes the dispersion
parameter phi = 1. This means standard errors do NOT account for
overdispersion.

```r
fit_pois <- glm(count ~ x1, data = df, family = poisson)
summary(fit_pois)
# "Dispersion parameter for poisson family taken to be 1"
```

### Quasi Families: Dispersion Estimated

```r
fit_qpois <- glm(count ~ x1, data = df, family = quasipoisson)
summary(fit_qpois)
# Reports estimated dispersion; SEs are inflated accordingly
```

### Gotcha: summary() for GLM uses Dispersion = 1

`summary(glm_fit)` always reports z-tests (not t-tests) for Poisson and
binomial models because it uses the known dispersion phi = 1. The z-tests
use normal critical values, not t-distribution.

For quasi-families, `summary()` reports t-tests with estimated dispersion and
uses t-distribution critical values.

### Gotcha: confint() for GLMs

```r
# Profile likelihood CI (default for GLMs -- more accurate)
confint(fit_glm)

# Wald CI (faster, less accurate for small samples)
confint.default(fit_glm)
```

`confint()` on a `glm` object computes profile likelihood confidence intervals,
which can be slow but are more accurate than Wald intervals. Use
`confint.default()` for the Wald version if speed matters and n is large.

---

## References

- Venables, W.N. & Ripley, B.D. (2002). *Modern Applied Statistics with S*,
  4th ed. Springer.
- Fox, J. & Weisberg, S. (2019). *An R Companion to Applied Regression*, 3rd ed.
  Sage.
- R Core Team (2025). R: A Language and Environment for Statistical Computing.
