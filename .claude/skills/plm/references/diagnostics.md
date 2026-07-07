# Panel Diagnostics

Reference for panel-specific diagnostic tests in plm. Covers the Hausman test
(FE vs RE), poolability tests, serial correlation tests, cross-sectional
dependence tests, and panel unit root tests.

## Contents

- [Hausman Test (FE vs RE)](#hausman-test-fe-vs-re)
- [Poolability Test (F-Test for FE)](#poolability-test-f-test-for-fe)
- [Serial Correlation Tests](#serial-correlation-tests)
- [Cross-Sectional Dependence Tests](#cross-sectional-dependence-tests)
- [Panel Unit Root Tests](#panel-unit-root-tests)
- [Diagnostic Workflow](#diagnostic-workflow)
- [References](#references)

---

## Hausman Test (FE vs RE)

The Hausman test compares FE and RE estimators. Under H0 (RE assumptions
hold), both are consistent but RE is efficient. Under H1, only FE is
consistent.

```r
library(plm)
data("Grunfeld", package = "plm")
pdf <- pdata.frame(Grunfeld, index = c("firm", "year"))

fit_fe <- plm(invest ~ value + capital, data = pdf, model = "within")
fit_re <- plm(invest ~ value + capital, data = pdf, model = "random")

# Hausman test
ht <- phtest(fit_fe, fit_re)
print(ht)
# Low p-value: reject RE, use FE
# High p-value: RE is consistent, prefer RE for efficiency
```

### Interpreting the Result

| p-value | Decision | Reasoning |
|---------|----------|-----------|
| < 0.05 | Use FE | RE assumption (effects uncorrelated with regressors) rejected |
| >= 0.05 | RE is acceptable | Cannot reject that effects are uncorrelated |

### Common Issues with phtest()

**Negative chi-squared statistic**: Can occur when the variance of the
difference (V_FE - V_RE) is not positive semi-definite. This is a
finite-sample problem.

```r
# If phtest() gives a warning about non-positive definite matrix,
# use the auxiliary regression version:
phtest(invest ~ value + capital, data = pdf, method = "aux")
```

**Two-way effects**: When using `effect = "twoways"`, both models must use
the same effect specification:

```r
fit_fe_2w <- plm(y ~ x, data = pdf, model = "within", effect = "twoways")
fit_re_2w <- plm(y ~ x, data = pdf, model = "random", effect = "twoways")
phtest(fit_fe_2w, fit_re_2w)
```

### Comparison with linearmodels

linearmodels (Python) does NOT have a built-in Hausman test. The plm
`phtest()` is one of plm's key advantages over linearmodels for model
selection.

---

## Poolability Test (F-Test for FE)

Tests whether entity fixed effects are jointly significant. H0: all entity
effects are zero (pooled OLS is appropriate). Rejection supports FE.

```r
fit_fe <- plm(invest ~ value + capital, data = pdf, model = "within")
fit_pool <- plm(invest ~ value + capital, data = pdf, model = "pooling")

# F-test for individual effects
pFtest(fit_fe, fit_pool)
# Low p-value: entity effects matter, reject pooled OLS
```

### Honda LM Test (Alternative)

```r
# Breusch-Pagan LM test for individual effects
plmtest(fit_pool, type = "bp")

# Honda test (one-sided, more powerful)
plmtest(fit_pool, type = "honda")

# Ghosh-Kim-Sun-Weidner test (for unbalanced panels)
plmtest(fit_pool, type = "ghm")
```

| Test | H0 | When to Use |
|------|-----|-------------|
| `pFtest()` | All entity effects = 0 | Standard F-test (requires within model) |
| `plmtest(type = "bp")` | Var(entity effects) = 0 | Breusch-Pagan LM (uses pooling model) |
| `plmtest(type = "honda")` | Var(entity effects) = 0 | One-sided, more powerful than BP |

---

## Serial Correlation Tests

### Breusch-Godfrey / Wooldridge Test

Tests for serial correlation in panel model residuals.

```r
# Breusch-Godfrey test for serial correlation
pbgtest(fit_fe)
# Low p-value: serial correlation is present

# Specify lag order
pbgtest(fit_fe, order = 2)
```

### Wooldridge First-Difference Test

```r
# Wooldridge test for AR(1) serial correlation in FE models
pwartest(fit_fe)
```

### Breusch-Pagan LM Test for Serial Correlation

```r
# LM test variant
plmtest(fit_pool, type = "bp", effect = "time")
```

### Durbin-Watson for Panel

```r
# Panel Durbin-Watson
pdwtest(fit_fe)
# Statistic near 2: no serial correlation
# Near 0 or 4: positive or negative serial correlation
```

---

## Cross-Sectional Dependence Tests

Tests whether residuals are correlated across entities within the same time
period. Important because cross-sectional dependence invalidates standard
clustered SEs.

### Pesaran CD Test

```r
# Pesaran CD test (works well with large N, any T)
pcdtest(fit_fe, test = "cd")
# Low p-value: cross-sectional dependence detected
# -> Consider Driscoll-Kraay SEs (vcovSCC)
```

### Friedman Test

```r
# Friedman rank test for cross-sectional dependence
pcdtest(fit_fe, test = "sclm")
```

### Breusch-Pagan LM Test

```r
# LM test (requires T > N; not suitable for large panels)
pcdtest(fit_fe, test = "lm")
```

| Test | Requirements | Best For |
|------|-------------|----------|
| Pesaran CD | Any N, T | Large panels (default choice) |
| Friedman | Any N, T | Non-parametric alternative |
| LM (Breusch-Pagan) | T > N | Small panels only |

### When Cross-Sectional Dependence Is Detected

If `pcdtest()` rejects independence, use Driscoll-Kraay SEs:

```r
library(lmtest)
coeftest(fit_fe, vcov = vcovSCC(fit_fe))
```

---

## Panel Unit Root Tests

Tests whether panel variables are stationary. Important for avoiding
spurious regressions in panel data with long T.

### purtest() -- Multiple Panel Unit Root Tests

```r
# Im-Pesaran-Shin (IPS) test
purtest(pdf$invest, test = "ips", exo = "intercept", lags = "AIC")

# Levin-Lin-Chu (LLC) test
purtest(pdf$invest, test = "levinlin", exo = "intercept")

# Maddala-Wu (Fisher-type) test
purtest(pdf$invest, test = "madwu", exo = "intercept")

# Hadri test (H0: stationarity, opposite null)
purtest(pdf$invest, test = "hadri", exo = "intercept")
```

| Test | H0 | H1 | Best When |
|------|-----|-----|-----------|
| `"ips"` | All panels have unit root | Some panels are stationary | Heterogeneous panels |
| `"levinlin"` | Common unit root | All panels are stationary | Homogeneous panels |
| `"madwu"` | All panels have unit root | Some panels are stationary | Unbalanced panels |
| `"hadri"` | All panels are stationary | Some panels have unit root | Reverse null |

### cipstest() -- Pesaran CIPS Test

```r
# Cross-sectionally augmented IPS (CIPS) -- robust to cross-sect dependence
cipstest(pdf$invest, type = "drift")
```

The CIPS test is preferable when cross-sectional dependence is present
(which is common in macro and financial panels).

---

## Diagnostic Workflow

A recommended sequence of diagnostic tests for panel analysis:

```r
library(plm)
library(lmtest)

# 1. Set up panel
pdf <- pdata.frame(df, index = c("entity_id", "year"))

# 2. Estimate models
fit_pool <- plm(y ~ x1 + x2, data = pdf, model = "pooling")
fit_fe   <- plm(y ~ x1 + x2, data = pdf, model = "within")
fit_re   <- plm(y ~ x1 + x2, data = pdf, model = "random")

# 3. Poolability: are entity effects significant?
pFtest(fit_fe, fit_pool)
# If reject: entity effects matter, proceed to FE vs RE

# 4. Hausman: FE or RE?
phtest(fit_fe, fit_re)
# If reject: use FE
# If fail to reject: RE is acceptable

# 5. Serial correlation
pbgtest(fit_fe)
# If reject: serial correlation present
# -> Use clustered or Newey-West SEs

# 6. Cross-sectional dependence
pcdtest(fit_fe, test = "cd")
# If reject: cross-sectional dependence present
# -> Use Driscoll-Kraay SEs (vcovSCC)

# 7. Unit roots (if T is large)
purtest(pdf$y, test = "ips", exo = "intercept", lags = "AIC")
# If fail to reject: non-stationarity, consider first-differencing

# 8. Final model with appropriate SEs
# (based on diagnostic results)
coeftest(fit_fe, vcov = vcovHC(fit_fe, cluster = "group"))
```

---

## References

- Hausman, J.A. (1978). "Specification Tests in Econometrics." Econometrica,
  46(6), 1251-1271.
- Pesaran, M.H. (2004). "General Diagnostic Tests for Cross Section
  Dependence in Panels." Cambridge Working Papers in Economics, 0435.
- Im, K.S., Pesaran, M.H., & Shin, Y. (2003). "Testing for Unit Roots in
  Heterogeneous Panels." Journal of Econometrics, 115(1), 53-74.
- Breusch, T.S. & Pagan, A.R. (1980). "The Lagrange Multiplier Test and Its
  Applications to Model Specification in Econometrics." Review of Economic
  Studies, 47(1), 239-253.
- Wooldridge, J.M. (2010). Econometric Analysis of Cross Section and Panel
  Data. 2nd ed. MIT Press.
