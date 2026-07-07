# Robust and Clustered Standard Errors

Reference for robust inference with plm models and the estimatr package.
Covers plm's vcov functions (vcovHC, vcovNW, vcovSCC), estimatr's lm_robust
and iv_robust, and integration with lmtest::coeftest().

## Contents

- [plm vcov Functions](#plm-vcov-functions)
- [Using coeftest() with plm](#using-coeftest-with-plm)
- [estimatr: lm_robust and iv_robust](#estimatr-lm_robust-and-iv_robust)
- [SE Type Decision Guide](#se-type-decision-guide)
- [Comparison with fixest and linearmodels](#comparison-with-fixest-and-linearmodels)
- [References](#references)

---

## plm vcov Functions

plm provides its own variance-covariance estimators that are aware of panel
structure. These are used with `lmtest::coeftest()` for robust inference.

### vcovHC -- Heteroskedasticity-Consistent

```r
library(plm)
library(lmtest)

data("Grunfeld", package = "plm")
pdf <- pdata.frame(Grunfeld, index = c("firm", "year"))
fit <- plm(inv ~ value + capital, data = pdf, model = "within")

# HC0 (White)
coeftest(fit, vcov = vcovHC(fit, type = "HC0"))

# HC1 (with df correction -- most common)
coeftest(fit, vcov = vcovHC(fit, type = "HC1"))

# HC2
coeftest(fit, vcov = vcovHC(fit, type = "HC2"))

# HC3 (jackknife-like)
coeftest(fit, vcov = vcovHC(fit, type = "HC3"))

# HC4 (leverage-adjusted)
coeftest(fit, vcov = vcovHC(fit, type = "HC4"))
```

### vcovHC with Clustering

plm's `vcovHC()` supports clustering via the `cluster=` argument:

```r
# Cluster by entity groups (default for panel data)
coeftest(fit, vcov = vcovHC(fit, type = "HC1", cluster = "group"))

# Cluster by time periods
coeftest(fit, vcov = vcovHC(fit, type = "HC1", cluster = "time"))
```

| cluster= | What It Does |
|----------|-------------|
| `"group"` | Entity-clustered (accounts for within-entity serial correlation) |
| `"time"` | Time-clustered (accounts for cross-sectional correlation) |

### vcovNW -- Newey-West (HAC)

Panel HAC estimator. Robust to heteroskedasticity and serial correlation
within entities.

```r
# Newey-West with automatic bandwidth
coeftest(fit, vcov = vcovNW(fit))

# Specify maximum lag
coeftest(fit, vcov = vcovNW(fit, maxlag = 3))
```

### vcovSCC -- Driscoll-Kraay

Robust to heteroskedasticity, serial correlation, AND cross-sectional
dependence. The most robust option for panel data, appropriate when
`pcdtest()` rejects cross-sectional independence.

```r
# Driscoll-Kraay SEs
coeftest(fit, vcov = vcovSCC(fit))

# With specific maximum lag
coeftest(fit, vcov = vcovSCC(fit, maxlag = 4))
```

### vcovBK -- Beck-Katz (Panel-Corrected)

Panel-corrected standard errors (Beck & Katz 1995). Accounts for
panel heteroskedasticity and contemporaneous correlation. Requires
balanced panels.

```r
# Panel-corrected SEs
coeftest(fit, vcov = vcovBK(fit))
```

---

## Using coeftest() with plm

The standard pattern for robust inference with plm models is
`coeftest(fit, vcov = vcov_function(fit))` from the `lmtest` package.

```r
library(lmtest)

# Store the vcov for reuse
vc <- vcovHC(fit, type = "HC1", cluster = "group")

# Coefficient test
coeftest(fit, vcov = vc)

# Confidence intervals
confint(coeftest(fit, vcov = vc))

# Wald test for joint significance
waldtest(fit, vcov = vc)
```

### Summary with Robust SEs via modelsummary

```r
library(modelsummary)

# modelsummary accepts a vcov argument directly
modelsummary(
  list("FE" = fit_fe, "RE" = fit_re),
  vcov = list(
    "FE" = vcovHC(fit_fe, cluster = "group"),
    "RE" = vcovHC(fit_re, cluster = "group")
  )
)
```

---

## estimatr: lm_robust and iv_robust

The `estimatr` package provides one-step robust estimation for cross-sectional
models. It is faster than the sandwich+lmtest approach and produces the same
results.

### lm_robust -- OLS with Built-in Robust SEs

```r
library(estimatr)

# HC2 robust SEs (default)
fit_robust <- lm_robust(y ~ x1 + x2, data = df)
summary(fit_robust)

# HC1 (matches Stata robust)
fit_hc1 <- lm_robust(y ~ x1 + x2, data = df, se_type = "HC1")

# Clustered SEs
fit_cl <- lm_robust(y ~ x1 + x2, data = df,
                    clusters = group_var, se_type = "CR2")

# Fixed effects via estimatr (absorbs, does not estimate)
fit_fe <- lm_robust(y ~ x1 + x2, data = df,
                    fixed_effects = ~ entity_id,
                    clusters = entity_id, se_type = "CR2")
```

### SE Types in estimatr

| se_type | Description | R Equivalent |
|---------|-------------|-------------|
| `"HC0"` | White (no df correction) | `sandwich::vcovHC(type = "HC0")` |
| `"HC1"` | With (n/(n-k)) correction | `sandwich::vcovHC(type = "HC1")` |
| `"HC2"` | Leverage-adjusted (default) | `sandwich::vcovHC(type = "HC2")` |
| `"HC3"` | Jackknife-like | `sandwich::vcovHC(type = "HC3")` |
| `"stata"` | Alias for HC1 | Stata `robust` |
| `"CR0"` | Cluster-robust (no correction) | Basic cluster-robust |
| `"CR2"` | Cluster with Bell-McCaffrey (default) | Improved small-sample |
| `"classical"` | Homoskedastic (no correction) | Standard OLS |

### iv_robust -- IV with Robust SEs

```r
library(estimatr)

# 2SLS with robust SEs
fit_iv <- iv_robust(
  y ~ x1 + x_endog | x1 + z1 + z2,
  data = df,
  se_type = "HC1"
)
summary(fit_iv)

# With clustering
fit_iv_cl <- iv_robust(
  y ~ x1 + x_endog | x1 + z1 + z2,
  data = df,
  clusters = group_var,
  se_type = "CR2"
)
```

### iv_robust Formula Syntax

The `iv_robust()` formula uses the same plm-style convention: regressors on
the left of `|`, all exogenous variables + instruments on the right.

```r
# y ~ endogenous + exogenous | exogenous + instruments
iv_robust(y ~ x_endog + x1 + x2 | z1 + z2 + x1 + x2, data = df)
```

### When to Use estimatr vs sandwich+lmtest

| Scenario | Preferred |
|----------|-----------|
| Cross-sectional OLS with robust SEs | estimatr (simpler, one step) |
| Cross-sectional IV with robust SEs | estimatr iv_robust |
| Panel model (plm) with robust SEs | plm vcov functions + coeftest |
| Need Bell-McCaffrey CR2 correction | estimatr (built in) |
| Need Driscoll-Kraay or Newey-West | plm vcov functions (not in estimatr) |

---

## SE Type Decision Guide

| Situation | Recommended | Code |
|-----------|------------|------|
| Panel, within-entity correlation | Entity-clustered | `vcovHC(fit, cluster = "group")` |
| Panel, cross-sectional dependence | Driscoll-Kraay | `vcovSCC(fit)` |
| Panel, serial correlation (HAC) | Newey-West | `vcovNW(fit)` |
| Panel, balanced, contemp. correlation | Beck-Katz | `vcovBK(fit)` |
| Cross-section, heteroskedasticity | HC1 or HC2 | `lm_robust(se_type = "HC1")` |
| Cross-section, group structure | Clustered | `lm_robust(clusters = g, se_type = "CR2")` |
| Any, small clusters (< 50) | CR2 or bootstrap | `lm_robust(se_type = "CR2")` |

Default for panel data: **entity-clustered SEs** (`vcovHC(cluster = "group")`).

---

## Comparison with fixest and linearmodels

| SE Type | plm | fixest | linearmodels |
|---------|-----|--------|-------------|
| HC robust | `vcovHC(type = "HC1")` | `vcov = "hetero"` | `cov_type="robust"` |
| Entity-clustered | `vcovHC(cluster = "group")` | `vcov = ~entity` | `cluster_entity=True` |
| Time-clustered | `vcovHC(cluster = "time")` | `vcov = ~time` | `cluster_time=True` |
| Two-way cluster | `vcovDC()` (double clustering) | `vcov = ~e + t` | `cluster_entity + cluster_time` |
| Newey-West | `vcovNW()` | `vcov = "NW"` | `cov_type="kernel"` |
| Driscoll-Kraay | `vcovSCC()` | `vcov = "DK"` | `cov_type="kernel"` |
| Post-estimation switch | Yes (coeftest) | Yes (summary vcov=) | No (must re-fit) |
| CRV3 / wild bootstrap | No | No | No |

### Key Difference: Post-Estimation SE Switching

Both plm (via coeftest) and fixest (via summary vcov=) support post-estimation
SE switching. linearmodels (Python) requires re-fitting.

```r
# plm: switch SEs without re-estimating
coeftest(fit, vcov = vcovHC(fit, cluster = "group"))
coeftest(fit, vcov = vcovSCC(fit))
coeftest(fit, vcov = vcovNW(fit))
```

---

## References

- White, H. (1980). "A Heteroskedasticity-Consistent Covariance Matrix
  Estimator and a Direct Test for Heteroskedasticity." Econometrica, 48(4),
  817-838.
- Driscoll, J.C. & Kraay, A.C. (1998). "Consistent Covariance Matrix
  Estimation with Spatially Dependent Panel Data." Review of Economics and
  Statistics, 80(4), 549-560.
- Cameron, A.C. & Miller, D.L. (2015). "A Practitioner's Guide to
  Cluster-Robust Inference." Journal of Human Resources, 50(2), 317-372.
- Beck, N. & Katz, J.N. (1995). "What to Do (and Not to Do) with
  Time-Series Cross-Section Data." American Political Science Review, 89(3),
  634-647.
- Blair, G., Cooper, J., Coppock, A., Humphreys, M., & Sonnet, L. (2022).
  estimatr: Fast Estimators for Design-Based Inference. R package.
