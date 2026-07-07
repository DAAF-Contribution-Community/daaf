# Regression Modeling: Stata to R Translation

Stata's estimation interface is unified: `command depvar indepvars, options`.
R fragments this across packages, but fixest provides the closest Stata-like
experience for the most common models.

- **fixest** (primary): Closest to Stata `regress`/`reghdfe`/`ivreghdfe`; handles OLS, Poisson, IV, FE, DiD
- **stats** (base R): `lm()`, `glm()` for basic OLS and GLM
- **plm** (panel): Random effects, between, Fama-MacBeth
- **marginaleffects** (post-estimation): Direct R equivalent of Stata `margins`; same author
- **modelsummary** / fixest `etable()`: Publication tables replacing `esttab`

> **Versions referenced:** R: fixest 0.14.0, stats (base), plm 2.6-7, marginaleffects 0.32.0
> Stata: Stata 18

---

## 1. OLS Regression

### Basic OLS

```stata
regress y x1 x2
regress y x1 x2, robust
regress y x1 x2, vce(cluster state)
```

```r
library(fixest)

fit <- feols(y ~ x1 + x2, data = df)                          # IID SEs
fit <- feols(y ~ x1 + x2, data = df, vcov = "hetero")         # HC1 (Stata robust)
fit <- feols(y ~ x1 + x2, data = df, vcov = ~state)           # Clustered
fit <- feols(y ~ x1 + x2, data = df, vcov = ~state + year)    # Two-way cluster
```

### Accessing Results

| Stata | fixest | base R `lm()` |
|-------|--------|---------------|
| `_b[x1]` | `coef(fit)["x1"]` | `coef(fit)["x1"]` |
| `_se[x1]` | `se(fit)["x1"]` | `summary(fit)$coefficients["x1","Std. Error"]` |
| `e(N)` | `nobs(fit)` | `nobs(fit)` |
| `e(r2)` | `r2(fit)` | `summary(fit)$r.squared` |
| `predict yhat, xb` | `predict(fit)` or `fitted(fit)` | `fitted(fit)` |
| `predict resid, residuals` | `resid(fit)` | `resid(fit)` |
| `confint` | `confint(fit)` | `confint(fit)` |

---

## 2. Fixed Effects Regression

### One-Way and Multi-Way FE

```stata
areg y x1 x2, absorb(state)
reghdfe y x1 x2, absorb(state year)
reghdfe y x1 x2, absorb(state#year)
reghdfe y x1 x2, absorb(state year) cluster(state)
```

```r
fit <- feols(y ~ x1 + x2 | state, data = df)                           # One-way
fit <- feols(y ~ x1 + x2 | state + year, data = df)                    # Two-way
fit <- feols(y ~ x1 + x2 | state^year, data = df)                      # Interacted
fit <- feols(y ~ x1 + x2 | state + year, data = df, vcov = ~state)     # Clustered
```

### FE Syntax Mapping

| Stata | fixest | Notes |
|-------|--------|-------|
| `areg y x, absorb(fe)` | `feols(y ~ x \| fe)` | Single FE |
| `reghdfe y x, absorb(fe1 fe2)` | `feols(y ~ x \| fe1 + fe2)` | Multi-way |
| `reghdfe y x, absorb(fe1#fe2)` | `feols(y ~ x \| fe1^fe2)` | Interacted |
| `reghdfe ..., cluster(cl)` | `vcov = ~cl` | Cluster SE |
| `reghdfe ..., cluster(cl1 cl2)` | `vcov = ~cl1 + cl2` | Two-way |

---

## 3. Random Effects

```stata
xtset entity year
xtreg y x1 x2, re
```

```r
library(plm)
fit <- plm(y ~ x1 + x2, data = df, index = c("entity", "year"), model = "random")
summary(fit)
```

### Hausman Test

```stata
xtreg y x1 x2, fe
estimates store fe
xtreg y x1 x2, re
hausman fe
```

```r
fe_fit <- plm(y ~ x1 + x2, data = df, index = c("entity", "year"), model = "within")
re_fit <- plm(y ~ x1 + x2, data = df, index = c("entity", "year"), model = "random")
phtest(fe_fit, re_fit)
```

---

## 4. Instrumental Variables

```stata
ivregress 2sls y x_exog (x_endog = z1 z2)
ivreghdfe y x_exog (x_endog = z1), absorb(state year) cluster(state)
```

```r
# fixest: three-part formula (same as pyfixest)
fit <- feols(y ~ x_exog | 0 | x_endog ~ z1 + z2, data = df)
fit <- feols(y ~ x_exog | state + year | x_endog ~ z1, data = df, vcov = ~state)

# First-stage diagnostics
fitstat(fit, "ivf")     # First-stage F
summary(fit, stage = 1) # First-stage results
```

---

## 5. GLM: Logit, Probit, Poisson

```stata
logit y x1 x2
logit y x1 x2, or
probit y x1 x2
poisson y x1 x2
ppmlhdfe y x1 x2, absorb(state year)
nbreg y x1 x2
```

```r
# Logit / Probit (base R)
fit <- glm(y ~ x1 + x2, data = df, family = binomial(link = "logit"))
exp(coef(fit))  # Odds ratios
fit <- glm(y ~ x1 + x2, data = df, family = binomial(link = "probit"))

# Poisson with FE (fixest)
fit <- fepois(y ~ x1 + x2 | state + year, data = df)

# Negative binomial (MASS)
fit <- MASS::glm.nb(y ~ x1 + x2, data = df)

# GLM with FE (fixest -- unlike pyfixest, R fixest DOES support feglm with FE)
fit <- feglm(y ~ x1 + x2 | state, data = df, family = binomial)
fit <- fenegbin(y ~ x1 + x2 | state, data = df)
```

**Key advantage over Python:** R's fixest `feglm()` and `fenegbin()` support
FE absorption for GLM models. This is a major gap in pyfixest that does not
exist in R fixest.

---

## 6. Post-Estimation

### Hypothesis Testing

```stata
test x1 x2                        * Joint F-test
test x1 = x2                      * Equality test
lincom x1 + x2
```

```r
# car package
library(car)
linearHypothesis(fit, c("x1 = 0", "x2 = 0"))   # Joint
linearHypothesis(fit, "x1 = x2")                 # Equality

# marginaleffects
library(marginaleffects)
hypotheses(fit, "x1 + x2 = 0")
hypotheses(fit, "x1 = x2")
```

### Marginal Effects

```stata
logit y x1 x2 x3
margins, dydx(*)
margins, dydx(x1)
margins, at(x1=(0 1))
margins group, dydx(x1)
```

```r
fit <- glm(y ~ x1 + x2 + x3, data = df, family = binomial)

avg_slopes(fit)                                              # AME all
avg_slopes(fit, variables = "x1")                            # AME for x1
predictions(fit, newdata = datagrid(x1 = c(0, 1)))           # Predictive margins
avg_slopes(fit, variables = "x1", by = "group")              # Group-specific
```

R's `marginaleffects` is the **original** package (Python version is a port).
The R version is more mature and has broader model support.

---

## 7. Estimation Tables

```stata
eststo m1: regress y x1
eststo m2: regress y x1 x2
esttab m1 m2, se star(* 0.10 ** 0.05 *** 0.01) r2
```

```r
m1 <- feols(y ~ x1, data = df)
m2 <- feols(y ~ x1 + x2, data = df)

# fixest etable
etable(m1, m2)
etable(m1, m2, tex = TRUE)                     # LaTeX
etable(m1, m2, dict = c(x1 = "Education"))     # Labels

# modelsummary (alternative)
library(modelsummary)
modelsummary(list(m1, m2), stars = c("*" = 0.1, "**" = 0.05, "***" = 0.01))
```

---

## 8. Standard Errors

| Stata | fixest | Notes |
|-------|--------|-------|
| (default) | `vcov = "iid"` | Classical |
| `, robust` | `vcov = "hetero"` | HC1 |
| `, vce(hc2)` | `vcov = "HC2"` | |
| `, vce(hc3)` | `vcov = "HC3"` | |
| `, vce(cluster cl)` | `vcov = ~cl` | One-way |
| `, vce(cluster cl1 cl2)` | `vcov = ~cl1 + cl2` | Two-way |
| (Newey-West) | `vcov = NW ~ unit + year` | HAC |
| (Driscoll-Kraay) | `vcov = DK ~ unit + year` | Panel |

### Switching SEs Post-Estimation

```r
fit <- feols(y ~ x1 + x2, data = df)
summary(fit, vcov = "hetero")              # HC1
summary(fit, vcov = ~state)                # Clustered
etable(fit, vcov = list("iid", "hetero"))  # Compare SEs side-by-side
```

---

## 9. Formula Syntax Quick Reference

| Feature | Stata | fixest | base R |
|---------|-------|--------|--------|
| Intercept | Default | Default | Default |
| No intercept | `nocons` | `y ~ x - 1` | `y ~ x - 1` |
| Interaction | `c.x1#c.x2` | `x1:x2` | `x1:x2` |
| Full cross | `c.x1##c.x2` | `x1*x2` | `x1*x2` |
| Factor variable | `i.group` | `factor(group)` or `i(group)` | `factor(group)` |
| Reference level | `ib3.group` | `i(group, ref = 3)` | `relevel(factor(group), ref = "3")` |
| Fixed effects | `absorb(fe)` | `\| fe` | Not supported (use dummies) |
| Polynomial | `c.x#c.x` | `I(x^2)` | `I(x^2)` |
| Multiple depvars | Not in base | `c(y1, y2) ~ x` | Not supported |
| Stepwise | Not native | `sw(x1, x2)` | Not supported |
