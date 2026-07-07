# Panel Data Models

Reference for all panel estimators available via plm. For methodology guidance
on when to use FE vs RE, assumption checking, and model selection, see the
data-scientist skill.

## Contents

- [Within (Fixed Effects)](#within-fixed-effects)
- [Random Effects](#random-effects)
- [Between Estimator](#between-estimator)
- [First Difference](#first-difference)
- [Pooled OLS](#pooled-ols)
- [Fama-MacBeth](#fama-macbeth)
- [Two-Way Effects](#two-way-effects)
- [Weighted Estimation](#weighted-estimation)
- [Model Comparison](#model-comparison)
- [Common Patterns](#common-patterns)
- [References](#references)

---

## Within (Fixed Effects)

The within estimator demeans each variable by its entity mean, absorbing
time-invariant unobserved heterogeneity. This is the workhorse panel model
for controlling confounders that differ across entities but are constant over
time.

```r
library(plm)
data("Grunfeld", package = "plm")
pdf <- pdata.frame(Grunfeld, index = c("firm", "year"))

# Entity fixed effects (default)
fit_fe <- plm(invest ~ value + capital, data = pdf, model = "within")
summary(fit_fe)

# Extract entity fixed effects
fixef(fit_fe)

# Overall intercept
within_intercept(fit_fe)
```

### Interpreting FE Results

- **Coefficients** measure within-entity changes: a one-unit increase in x
  within the same entity is associated with a beta-unit change in y
- **R-squared** is the within R-squared (variation explained after demeaning)
- **Fixed effects** (`fixef()`) are entity-specific intercepts. They are not
  printed in summary() but can be extracted
- **F-test for individual effects** tests whether all entity effects are
  jointly zero. Rejection supports FE over pooled OLS

```r
# F-test for FE significance
pFtest(fit_fe, plm(invest ~ value + capital, data = pdf, model = "pooling"))
```

### Time-Invariant Variables

Variables that do not vary within an entity are dropped automatically by the
within estimator (they are perfectly collinear with entity effects). If you
need to include time-invariant regressors, use RE or the Mundlak approach:

```r
# Mundlak approach: include entity means of time-varying vars in RE model
# to approximate FE while retaining time-invariant vars
pdf$value_mean <- ave(pdf$value, pdf$firm, FUN = mean)
fit_mundlak <- plm(invest ~ value + capital + value_mean,
                   data = pdf, model = "random")
```

---

## Random Effects

GLS estimator with quasi-demeaning. More efficient than FE when the
assumption that entity effects are uncorrelated with regressors holds.
Includes an explicit intercept and preserves time-invariant regressors.

```r
# Random effects (default: Swamy-Arora variance component estimation)
fit_re <- plm(invest ~ value + capital, data = pdf, model = "random")
summary(fit_re)
```

### Variance Component Estimation Methods

The `random.method=` argument controls how variance components are estimated:

| Method | Code | Description |
|--------|------|-------------|
| Swamy-Arora | `random.method = "swar"` (default) | Uses within and between residuals |
| Amemiya | `random.method = "amemiya"` | Based on within residuals |
| Wallace-Hussain | `random.method = "walhus"` | Based on pooled OLS residuals |
| Nerlove | `random.method = "nerlove"` | Based on FE residuals |

```r
# Compare variance component methods
fit_re_swar <- plm(invest ~ value + capital, data = pdf,
                   model = "random", random.method = "swar")
fit_re_amem <- plm(invest ~ value + capital, data = pdf,
                   model = "random", random.method = "amemiya")
```

### Variance Decomposition

```r
# Summary shows the variance components
summary(fit_re)
# Look for:
#   var.comp: individual (sigma_alpha^2) and idiosyncratic (sigma_epsilon^2)
#   theta: quasi-demeaning parameter

# The theta value indicates how much quasi-demeaning is applied
# theta = 0: pooled OLS (no entity effect)
# theta = 1: within estimator (full demeaning)
# 0 < theta < 1: partial demeaning (RE)

# Extract variance components
ercomp(fit_re)
```

---

## Between Estimator

Regresses entity time-averages on entity-averaged regressors. Uses only
between-entity variation. Useful for understanding cross-sectional
relationships and as a diagnostic tool.

```r
fit_be <- plm(invest ~ value + capital, data = pdf, model = "between")
summary(fit_be)

# Effective N = number of entities (not total observations)
```

### When to Use Between

- As part of a panel decomposition analysis (pooled = weighted average of
  within and between)
- To check whether cross-sectional and within-entity patterns agree
- When the research question is inherently cross-sectional (e.g., "do
  larger firms invest more?")

---

## First Difference

Eliminates entity effects by first-differencing consecutive observations:
delta_y_it = y_it - y_{i,t-1}. Alternative to within estimation with
different properties under serial correlation.

```r
fit_fd <- plm(invest ~ value + capital, data = pdf, model = "fd")
summary(fit_fd)
```

### FD vs Within (FE)

| Aspect | First Difference | Within (FE) |
|--------|-----------------|-------------|
| Transformation | Adjacent-period differencing | Entity mean demeaning |
| Observations lost | 1 per entity | 0 |
| Under AR(1) errors | More efficient when rho~1 | More efficient when rho~0 |
| Under MA errors | FD can be more efficient | Within is more efficient |
| With T=2 | FD = Within (identical) | FD = Within (identical) |
| Time-invariant vars | Differenced out | Demeaned out |

```r
# With T=2, FD and Within produce identical estimates
# (a useful sanity check with two-period panels)
```

---

## Pooled OLS

Standard OLS ignoring panel structure. Useful as a baseline model, but
assumes no entity-specific effects (or that they are uncorrelated with
regressors and have constant variance).

```r
fit_pool <- plm(invest ~ value + capital, data = pdf, model = "pooling")
summary(fit_pool)

# Compare with FE to test for entity effects
pFtest(fit_fe, fit_pool)
# Rejection: entity effects matter, use FE/RE
```

### Panel-Aware SEs for Pooled OLS

Pooled OLS coefficients are consistent when effects are uncorrelated with
regressors, but standard errors are wrong if within-entity correlation exists.
Use clustered SEs:

```r
library(lmtest)

# Pooled OLS with entity-clustered SEs
coeftest(fit_pool, vcov = vcovHC(fit_pool, cluster = "group"))
```

---

## Fama-MacBeth

Two-step procedure: (1) estimate a cross-sectional regression for each time
period, (2) average coefficients across periods. Standard in empirical asset
pricing.

plm provides Fama-MacBeth via `pmg()` (panel mean group estimator):

```r
# Fama-MacBeth: mean group estimator
fit_fm <- pmg(invest ~ value + capital, data = pdf, model = "mg")
summary(fit_fm)
```

### pmg Model Types

| model= | Description |
|--------|-------------|
| `"mg"` | Mean group -- period-by-period OLS, average coefficients |
| `"dmg"` | Demeaned mean group -- entity-demeaned before cross-sectional OLS |
| `"cmg"` | Correlated common effects (Pesaran 2006) -- includes cross-sectional averages |

```r
# Correlated common effects mean group (CCE-MG)
fit_ccemg <- pmg(invest ~ value + capital, data = pdf, model = "cmg")
summary(fit_ccemg)
```

### Comparison with linearmodels FamaMacBeth

| Feature | plm pmg() | linearmodels FamaMacBeth |
|---------|-----------|------------------------|
| Basic FM | `model = "mg"` | `FamaMacBeth.from_formula()` |
| HAC SEs | Not built in (use Newey-West manually) | `cov_type="kernel"` |
| CCE extension | `model = "cmg"` | Not available |

---

## Two-Way Effects

Model both entity and time effects simultaneously. Available for within
(FE) and random effects.

### Two-Way Fixed Effects

```r
# Entity + time fixed effects
fit_twfe <- plm(invest ~ value + capital, data = pdf,
                model = "within", effect = "twoways")
summary(fit_twfe)

# Extract entity and time effects separately
fixef(fit_twfe, effect = "individual")
fixef(fit_twfe, effect = "time")
```

### Two-Way Random Effects

```r
# Entity + time random effects
fit_twre <- plm(invest ~ value + capital, data = pdf,
                model = "random", effect = "twoways")
summary(fit_twre)
```

### Time Effects Only

```r
# Time effects only (unusual but available)
fit_time_fe <- plm(invest ~ value + capital, data = pdf,
                   model = "within", effect = "time")
summary(fit_time_fe)
```

---

## Weighted Estimation

plm supports weighted estimation via the `weights=` argument. Weights are
observation-level and must have the same length as the data.

```r
# WLS panel estimation
fit_wls <- plm(invest ~ value + capital, data = pdf,
               model = "within", weights = pdf$some_weight)
summary(fit_wls)
```

Common weight sources:
- **Population weights**: weight by group size for representative estimates
- **Precision weights**: inverse of known variance for heteroskedastic data
- **Frequency weights**: when data is pre-aggregated with counts

---

## Model Comparison

### Side-by-Side with modelsummary

```r
library(modelsummary)

modelsummary(
  list(
    "Pooled" = fit_pool,
    "FE" = fit_fe,
    "RE" = fit_re,
    "Between" = fit_be,
    "FD" = fit_fd
  ),
  stars = TRUE
)
```

### Systematic Comparison Workflow

```r
# Typical panel analysis workflow
# 1. Pooled OLS as baseline
fit_pool <- plm(y ~ x1 + x2, data = pdf, model = "pooling")

# 2. FE -- test for entity effects
fit_fe <- plm(y ~ x1 + x2, data = pdf, model = "within")
pFtest(fit_fe, fit_pool)  # Reject? Entity effects matter.

# 3. RE -- compare with FE
fit_re <- plm(y ~ x1 + x2, data = pdf, model = "random")
phtest(fit_fe, fit_re)    # Reject? RE inconsistent, use FE.

# 4. Report preferred model with clustered SEs
library(lmtest)
coeftest(fit_fe, vcov = vcovHC(fit_fe, cluster = "group"))
```

---

## Common Patterns

### Adding Time Trends

```r
# Linear time trend as a regressor
pdf$trend <- as.numeric(pdf$year) - min(as.numeric(pdf$year))
fit <- plm(y ~ x1 + x2 + trend, data = pdf, model = "within")
```

### Lagged Variables

plm provides `lag()` and `diff()` that are panel-aware (they respect entity
boundaries):

```r
# Lagged dependent variable (requires careful interpretation in FE)
fit <- plm(y ~ lag(y, 1) + x1, data = pdf, model = "pooling")
# For dynamic panels with lagged DV under FE, use pgmm() instead
# (Nickell bias is severe when T is small)

# First differences
pdf$dy <- diff(pdf$y)
```

### Lead Variables

```r
# Lead (forward) values
pdf$y_lead <- lead(pdf$y, 1)
```

---

## References

- Croissant, Y. & Millo, G. (2008). "Panel Data Econometrics in R: The plm
  Package." Journal of Statistical Software, 27(2), 1-43.
- Wooldridge, J.M. (2010). Econometric Analysis of Cross Section and Panel
  Data. 2nd ed. MIT Press.
- Baltagi, B.H. (2021). Econometric Analysis of Panel Data. 6th ed. Springer.
- Mundlak, Y. (1978). "On the Pooling of Time Series and Cross Section Data."
  Econometrica, 46(1), 69-85.
- Pesaran, M.H. (2006). "Estimation and Inference in Large Heterogeneous
  Panels with a Multifactor Error Structure." Econometrica, 74(4), 967-1012.
