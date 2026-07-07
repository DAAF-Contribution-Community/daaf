# Panel IV and Dynamic GMM

Reference for instrumental variable estimation and dynamic panel models in plm.
Covers panel IV via plm() with instruments, Sargan/Hansen tests, and dynamic
GMM (Arellano-Bond, Blundell-Bond) via pgmm().

## Contents

- [Panel IV via plm()](#panel-iv-via-plm)
- [IV Formula Syntax](#iv-formula-syntax)
- [IV Diagnostics](#iv-diagnostics)
- [Dynamic GMM (pgmm)](#dynamic-gmm-pgmm)
- [Arellano-Bond vs Blundell-Bond](#arellano-bond-vs-blundell-bond)
- [GMM Diagnostics](#gmm-diagnostics)
- [Comparison with fixest and linearmodels](#comparison-with-fixest-and-linearmodels)
- [References](#references)

---

## Panel IV via plm()

plm supports instrumental variables within the panel framework. The
instruments are specified after `|` in the formula. The estimation combines
panel transformations (within, between, etc.) with 2SLS.

```r
library(plm)
data("Wages", package = "plm")
pdf <- pdata.frame(Wages, index = c("nr", "year"))

# Panel IV: educ is endogenous, instrumented by father's education
# All exogenous variables must appear on BOTH sides of |
fit_iv <- plm(lwage ~ exp + wks + educ | exp + wks + father_educ,
              data = pdf, model = "within")
summary(fit_iv)
```

### How plm IV Works

The formula `y ~ x1 + x_endog | x1 + z1 + z2` means:
- **Left of |**: regressors in the structural equation (including endogenous)
- **Right of |**: ALL exogenous variables + excluded instruments

All exogenous regressors from the left side must also appear on the right
side. The excluded instruments are those that appear on the right but not
the left.

---

## IV Formula Syntax

```r
# Basic IV: x_endog is endogenous, z is the excluded instrument
# x1 is exogenous and appears on both sides
y ~ x1 + x_endog | x1 + z

# Multiple excluded instruments
y ~ x1 + x_endog | x1 + z1 + z2

# Multiple endogenous variables
y ~ x1 + x_endog1 + x_endog2 | x1 + z1 + z2 + z3

# Combined with model argument for different panel transformations
plm(y ~ x1 + x_endog | x1 + z, data = pdf, model = "within")   # FE-IV
plm(y ~ x1 + x_endog | x1 + z, data = pdf, model = "random")   # RE-IV
plm(y ~ x1 + x_endog | x1 + z, data = pdf, model = "fd")       # FD-IV
```

### Common Mistakes

```r
# WRONG: exogenous variable missing from right side
y ~ x1 + x_endog | z
# This treats x1 as endogenous too

# CORRECT: x1 must appear on both sides
y ~ x1 + x_endog | x1 + z
```

### Comparison with Other IV Syntax

| Package | IV Syntax |
|---------|-----------|
| plm | `y ~ x1 + x_endog \| x1 + z` (exogenous on both sides) |
| fixest | `y ~ x1 \| fe \| x_endog ~ z` (three-part formula) |
| linearmodels | `"y ~ 1 + x1 + [x_endog ~ z]"` (bracket notation) |
| Stata `ivregress` | `ivregress 2sls y x1 (x_endog = z)` |

---

## IV Diagnostics

### Sargan Test (Overidentification)

When you have more instruments than endogenous variables, the Sargan test
checks whether the overidentifying restrictions are valid.

```r
# Sargan test for overidentifying restrictions
# H0: instruments are valid (exogenous)
# Rejection suggests at least one instrument may be endogenous
fit_iv <- plm(y ~ x1 + x_endog | x1 + z1 + z2,
              data = pdf, model = "within")

# The Sargan test is printed in summary for overidentified models
summary(fit_iv)
```

### Weak Instrument Checks

plm does not provide a built-in first-stage F-statistic. Check instrument
strength manually:

```r
# Manual first-stage regression
first_stage <- plm(x_endog ~ x1 + z1 + z2, data = pdf, model = "within")
summary(first_stage)
# Check: partial F on excluded instruments (z1, z2) should be > 10
```

---

## Dynamic GMM (pgmm)

`pgmm()` implements generalized method of moments for dynamic panel models.
Handles the endogeneity of lagged dependent variables in short-T panels
where within-estimation is inconsistent (Nickell bias).

### Arellano-Bond (Difference GMM)

```r
library(plm)
data("EmplUK", package = "plm")
pdf <- pdata.frame(EmplUK, index = c("firm", "year"))

# Arellano-Bond difference GMM
# lag(emp, 1:2) are endogenous, instrumented by deeper lags
fit_ab <- pgmm(
  log(emp) ~ lag(log(emp), 1:2) + lag(log(wage), 0:1) + log(capital) |
    lag(log(emp), 2:99),
  data = pdf,
  effect = "twoways",
  model = "twosteps"
)
summary(fit_ab)
```

### pgmm Formula Syntax

The formula for `pgmm()` has a specific structure:

```
y ~ lag(y, 1:k) + x_vars | GMM_instruments
```

- **Left of |**: the structural equation (dependent var, lagged DV, regressors)
- **Right of |**: GMM-style instruments (typically `lag(y, 2:99)` for all
  available lags beyond the endogenous lag range)

### Blundell-Bond (System GMM)

```r
# System GMM adds level equations alongside differenced equations
# More efficient when the process is highly persistent
fit_bb <- pgmm(
  log(emp) ~ lag(log(emp), 1:2) + lag(log(wage), 0:1) + log(capital) |
    lag(log(emp), 2:99),
  data = pdf,
  effect = "twoways",
  model = "twosteps",
  transformation = "ld"   # "ld" = level and difference (system GMM)
)
summary(fit_bb)
```

---

## Arellano-Bond vs Blundell-Bond

| Feature | Arellano-Bond (Diff GMM) | Blundell-Bond (Sys GMM) |
|---------|--------------------------|------------------------|
| Transformation | `transformation = "d"` (default) | `transformation = "ld"` |
| Equations | Differenced only | Differenced + levels |
| Instruments | Lagged levels for diff eq | + lagged diffs for level eq |
| Efficiency | Lower | Higher (esp. persistent series) |
| Assumption | Standard | Additional: mean stationarity |
| Finite sample | Better with moderate persistence | Better with high persistence |
| pgmm code | `model = "twosteps"` | `model = "twosteps", transformation = "ld"` |

### When to Prefer Each

- **Arellano-Bond**: When the dependent variable is not highly persistent
  (rho < 0.8) and you want to avoid the additional mean-stationarity
  assumption
- **Blundell-Bond**: When the dependent variable is highly persistent
  (rho > 0.8), which weakens AB instruments (levels are poor instruments
  for differences when the process is close to a unit root)

### Steps Options

| model= | Description |
|--------|-------------|
| `"onestep"` | One-step GMM with homoskedastic weight matrix |
| `"twosteps"` | Two-step GMM with optimal weight matrix (standard) |

Two-step is generally preferred for efficiency, but one-step is more robust
to misspecification of the weight matrix. Two-step standard errors should use
the Windmeijer (2005) correction.

---

## GMM Diagnostics

### Sargan/Hansen Test

```r
# Automatically reported in summary(fit_ab)
summary(fit_ab)
# Look for: Sargan test
# H0: overidentifying restrictions are valid
# Rejection: instrument set may be invalid
```

### Arellano-Bond AR Tests

```r
# AR(1) and AR(2) test for serial correlation in first-differenced residuals
# AR(1): expected to reject (differencing induces correlation)
# AR(2): should NOT reject (no second-order serial correlation in levels)
summary(fit_ab)
# Look for: Autocorrelation test of degree 1 and degree 2
```

The key diagnostic is AR(2):
- **AR(1) rejection**: Expected and unproblematic
- **AR(2) rejection**: Problematic -- suggests instruments (lag 2+) are invalid
  due to serial correlation in levels

### Instrument Proliferation

A common concern with GMM is too many instruments relative to cross-sections,
which can weaken the Sargan/Hansen test and cause finite-sample bias.

```r
# Limit instrument count by restricting lag depth
fit_ab <- pgmm(
  log(emp) ~ lag(log(emp), 1) + log(wage) + log(capital) |
    lag(log(emp), 2:4),   # Only lags 2-4 instead of 2:99
  data = pdf,
  effect = "twoways",
  model = "twosteps"
)
```

Rule of thumb: number of instruments should not exceed the number of
cross-sections (entities).

---

## Comparison with fixest and linearmodels

| Feature | plm | fixest | linearmodels |
|---------|-----|--------|-------------|
| Panel IV (FE + IV) | Yes (plm formula) | Yes (three-part formula) | No |
| Dynamic GMM | Yes (pgmm) | No | No |
| Arellano-Bond | Yes | No | No |
| Blundell-Bond | Yes | No | No |
| Cross-sectional IV | Via plm with model="pooling" | feols 3-part formula | IV2SLS, IVLIML, IVGMM |
| LIML / k-class | No | No | IVLIML |
| GMM-IV (non-panel) | No | No | IVGMM, IVGMMCUE |
| System estimation | No | No | SUR, IV3SLS |

**Key routing:**
- Panel IV (FE + endogenous): plm or fixest
- Dynamic panels (lagged DV): plm pgmm() (unique capability)
- Cross-sectional IV with LIML/GMM: linearmodels (Python)
- IV with high-dimensional FE: fixest

---

## References

- Arellano, M. & Bond, S. (1991). "Some Tests of Specification for Panel
  Data: Monte Carlo Evidence and an Application to Employment Equations."
  Review of Economic Studies, 58(2), 277-297.
- Blundell, R. & Bond, S. (1998). "Initial Conditions and Moment Restrictions
  in Dynamic Panel Data Models." Journal of Econometrics, 87(1), 115-143.
- Windmeijer, F. (2005). "A Finite Sample Correction for the Variance of
  Linear Efficient Two-step GMM Estimators." Journal of Econometrics,
  126(1), 25-51.
- Roodman, D. (2009). "How to Do xtabond2: An Introduction to Difference
  and System GMM in Stata." Stata Journal, 9(1), 86-136.
