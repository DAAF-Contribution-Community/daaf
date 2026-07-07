# Common Gotchas and Troubleshooting

A reference for known sharp edges, silent failures, and package-specific
behaviors in plm, estimatr, and lme4. Each section describes a problem, why
it happens, and how to fix it.

## Contents

1. [pdata.frame Requirements](#1-pdataframe-requirements)
2. [Unbalanced Panel Handling](#2-unbalanced-panel-handling)
3. [FE vs RE: When to Use Which](#3-fe-vs-re-when-to-use-which)
4. [fixest vs plm: Package Selection](#4-fixest-vs-plm-package-selection)
5. [Hausman Test Pitfalls](#5-hausman-test-pitfalls)
6. [IV Formula Confusion](#6-iv-formula-confusion)
7. [Default SEs Are Classical (Not Robust)](#7-default-ses-are-classical-not-robust)
8. [plm vs linearmodels (Python) Differences](#8-plm-vs-linearmodels-python-differences)
9. [lme4 Convergence Warnings](#9-lme4-convergence-warnings)
10. [Nickell Bias with Lagged DV](#10-nickell-bias-with-lagged-dv)

---

## 1. pdata.frame Requirements

**Problem:** plm silently auto-detects the panel index if you pass a plain
data.frame without explicit `pdata.frame()` declaration. This can produce
wrong entity/time assignments.

**Why:** plm's auto-detection heuristic guesses based on column names and
data patterns. If columns are named non-obviously, it may guess wrong.

**Fix:** Always create an explicit `pdata.frame()`:

```r
# WRONG: relying on auto-detection
fit <- plm(y ~ x, data = df, model = "within")

# CORRECT: explicit panel declaration
pdf <- pdata.frame(df, index = c("entity_id", "year"))
fit <- plm(y ~ x, data = pdf, model = "within")
```

**Verify with:**

```r
pdim(pdf)
# Check that n, T, and N match your expectations
```

---

## 2. Unbalanced Panel Handling

**Problem:** Some plm functions work differently or fail with unbalanced
panels (entities with different numbers of time periods).

**Key behaviors:**

| Function | Unbalanced Support |
|----------|-------------------|
| `plm()` (all models) | Yes -- handles automatically |
| `phtest()` | Yes -- but results may be less reliable |
| `vcovBK()` | No -- requires balanced panel |
| `purtest()` | Depends on test (madwu works, levinlin may not) |
| `pgmm()` | Yes -- handles gaps |

**Check balance:**

```r
is.pbalanced(pdf)
pdim(pdf)  # Shows min/max obs per entity

# Force balance by filling gaps with NA
pdf_bal <- make.pbalanced(pdf, balance.type = "fill")
```

---

## 3. FE vs RE: When to Use Which

**Problem:** Users default to FE without considering whether RE is
appropriate, or use RE without testing.

**Decision framework:**

```
Start: Do entity effects correlate with regressors?
|
+-- "Probably yes" (most social science applications)
|   --> FE is safer (consistent regardless of correlation)
|
+-- "Probably no" or "uncertain"
|   --> Run both, then Hausman test:
|       phtest(fit_fe, fit_re)
|       +-- p < 0.05: reject RE, use FE
|       +-- p >= 0.05: RE is acceptable, use RE for efficiency
|
+-- "Need time-invariant variables in the model"
    --> RE is the only option (FE absorbs time-invariant vars)
    --> Or use Mundlak approach (include entity means in RE)
```

**Common misconceptions:**
- "FE is always better" -- Wrong. RE is more efficient when its assumption
  holds, and it preserves time-invariant regressors.
- "RE assumes effects are zero" -- Wrong. RE assumes effects are
  uncorrelated with regressors, not that they are zero.
- "Small Hausman p-value means FE is better" -- More precisely: it means
  RE is inconsistent, making FE the only consistent option.

---

## 4. fixest vs plm: Package Selection

**Problem:** Both fixest and plm estimate panel models in R. Using the wrong
one wastes time or limits capabilities.

| Need | Use | Why |
|------|-----|-----|
| Entity FE (fast, large data) | fixest | C++ backend, much faster |
| Random effects | plm | fixest has no RE |
| Between estimator | plm | fixest has no between |
| Hausman test | plm | fixest has no phtest() |
| Panel diagnostics (serial corr, CD) | plm | Full diagnostic suite |
| First difference | plm | fixest has no FD |
| Fama-MacBeth | plm (pmg) | fixest has no FM |
| Dynamic GMM (Arellano-Bond) | plm (pgmm) | Unique to plm |
| 3+ way FE | fixest | plm max 2-way |
| FE + IV combined | fixest or plm | Both support it |
| DiD / event study | fixest | plm has no DiD |
| Publication tables (etable) | fixest | plm uses modelsummary |
| Poisson/GLM with FE | fixest | plm is linear only |

**Typical workflow:** Use plm for model selection (RE, Hausman test, diagnostics),
then fixest for final FE estimation with publication output.

---

## 5. Hausman Test Pitfalls

**Problem:** `phtest()` gives warnings or nonsensical results.

**Issue 1: Non-positive-definite variance matrix**

```
Warning: the covariance matrix of the difference is not positive definite
```

This is a finite-sample problem. The difference V(b_FE) - V(b_RE) should
be positive semi-definite in large samples, but may not be in practice.

```r
# Solution: use the auxiliary regression version
phtest(invest ~ value + capital, data = pdf, method = "aux")
```

**Issue 2: Different regressors in FE and RE**

Both models must have the same regressors. Time-invariant variables
included in RE but absorbed by FE will cause issues.

```r
# WRONG: different specifications
fit_fe <- plm(y ~ x1, data = pdf, model = "within")
fit_re <- plm(y ~ x1 + time_invariant, data = pdf, model = "random")
phtest(fit_fe, fit_re)  # May error or give misleading results

# CORRECT: same regressors (time_invariant excluded from both)
fit_fe <- plm(y ~ x1, data = pdf, model = "within")
fit_re <- plm(y ~ x1, data = pdf, model = "random")
phtest(fit_fe, fit_re)
```

**Issue 3: Two-way effects**

Both models must use the same `effect=` argument.

---

## 6. IV Formula Confusion

**Problem:** plm's IV formula syntax differs from fixest and Stata, causing
confusion.

```r
# plm IV syntax: regressors | ALL exogenous + instruments
y ~ x1 + x_endog | x1 + z1 + z2
#   ^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^
#   structural eq   exogenous set (must include x1!)

# fixest IV syntax: three-part formula
# y ~ x1 | fe | x_endog ~ z1 + z2

# Stata syntax: ivregress 2sls y x1 (x_endog = z1 z2)
```

**Key rule for plm:** Every exogenous regressor from the left side of `|`
must also appear on the right side. Forgetting this treats the variable as
endogenous.

```r
# WRONG: x1 missing from right side -> x1 treated as endogenous
plm(y ~ x1 + x_endog | z1 + z2, data = pdf, model = "within")

# CORRECT: x1 on both sides
plm(y ~ x1 + x_endog | x1 + z1 + z2, data = pdf, model = "within")
```

---

## 7. Default SEs Are Classical (Not Robust)

**Problem:** `summary(plm_fit)` reports classical (homoskedastic) SEs by
default. In panel data, these are almost always wrong.

**Fix:** Always use `coeftest()` with an appropriate vcov function:

```r
library(lmtest)

# Default summary -- WRONG for most applications
summary(fit)

# Correct: entity-clustered SEs
coeftest(fit, vcov = vcovHC(fit, cluster = "group"))
```

**Comparison with fixest:** fixest also defaults to IID SEs since v0.13, but
switching SEs is easier (`summary(fit, vcov = ~entity)`). Both packages
require the user to explicitly request robust/clustered SEs.

---

## 8. plm vs linearmodels (Python) Differences

**Problem:** Users switching between R (plm) and Python (linearmodels) get
confused by API differences.

| Feature | plm | linearmodels |
|---------|-----|-------------|
| Panel setup | `pdata.frame(index = c("e","t"))` | `df.set_index(["e","t"])` MultiIndex |
| FE keyword | `model = "within"` | `EntityEffects` in formula |
| RE keyword | `model = "random"` | `RandomEffects` class |
| Hausman test | `phtest(fe, re)` | Not available |
| Panel IV | `y ~ x1 + x_endog \| x1 + z` | Not available (use pyfixest) |
| Dynamic GMM | `pgmm()` | Not available |
| Driscoll-Kraay | `vcovSCC()` | `cov_type="kernel"` |
| FE extraction | `fixef(fit)` | `res.estimated_effects` |
| Constant in RE | Included automatically | Must include `1` in formula |
| Default vcov | Classical | Classical |
| Post-estimation SE switch | Yes (coeftest) | No (must re-fit) |

**Key advantage of plm over linearmodels:**
- Hausman test (phtest)
- Dynamic GMM (pgmm for Arellano-Bond / Blundell-Bond)
- Panel IV within a single formula
- Full diagnostic test suite (serial correlation, CD, unit root)

**Key advantage of linearmodels over plm:**
- LIML, k-class, continuously updating GMM (IVGMMCUE)
- System estimation (SUR, 3SLS, system GMM)
- Asset pricing factor models
- Fama-MacBeth with built-in HAC SEs

---

## 9. lme4 Convergence Warnings

**Problem:** lmer/glmer models fail with convergence warnings or singular
fit messages.

**"boundary (singular) fit"** means a variance component was estimated at
zero. The random effect structure is too complex for the data.

```r
# Solution: simplify the random effects
# Step 1: start with intercept only
fit1 <- lmer(y ~ x + (1 | group), data = df)

# Step 2: add random slopes one at a time
fit2 <- lmer(y ~ x + (1 + x | group), data = df)

# Step 3: if fit2 is singular, try uncorrelated
fit3 <- lmer(y ~ x + (1 | group) + (0 + x | group), data = df)
```

**"Model failed to converge"** means the optimizer didn't find a solution.

```r
# Solution: try different optimizer
fit <- lmer(y ~ x + (1 + x | group), data = df,
            control = lmerControl(optimizer = "bobyqa",
                                  optCtrl = list(maxfun = 200000)))
```

---

## 10. Nickell Bias with Lagged DV

**Problem:** Including a lagged dependent variable in a fixed effects model
creates inconsistency when T is small (Nickell 1981).

```r
# WRONG for short panels (small T):
fit <- plm(y ~ lag(y, 1) + x1, data = pdf, model = "within")
# The within transformation creates correlation between the
# demeaned lagged DV and the demeaned error

# CORRECT for short panels: use dynamic GMM
fit <- pgmm(
  y ~ lag(y, 1) + x1 | lag(y, 2:99),
  data = pdf, model = "twosteps"
)
```

**When Nickell bias matters:**
- T < 20: Substantial bias (magnitude approximately -1/(T-1))
- T > 30: Bias becomes small enough to be ignorable in practice
- N large, T small: Maximum bias (most panel datasets)
- N small, T large: FE is fine

---

## Quick Diagnostic Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Wrong entity/time assignment | Missing explicit pdata.frame | `pdata.frame(df, index = c("e", "t"))` |
| `vcovBK()` error | Unbalanced panel | Use `vcovHC(cluster = "group")` or balance the panel |
| Hausman test non-PD warning | Small sample | `phtest(..., method = "aux")` |
| Results differ from fixest FE | Different SE defaults | Both default to IID; specify same robust vcov |
| IV results strange | Exogenous var missing from RHS of \| | Include all exogenous on both sides |
| lmer singular fit | Too-complex random structure | Simplify random effects |
| Dynamic panel bias | Lagged DV in FE with short T | Use pgmm() |
| plm slower than fixest for FE | plm is pure R, fixest is C++ | Use fixest for speed; plm for RE/diagnostics |

---

## References

- Nickell, S. (1981). "Biases in Dynamic Models with Fixed Effects."
  Econometrica, 49(6), 1417-1426.
- Croissant, Y. & Millo, G. (2008). "Panel Data Econometrics in R: The plm
  Package." Journal of Statistical Software, 27(2), 1-43.
- Wooldridge, J.M. (2010). Econometric Analysis of Cross Section and Panel
  Data. 2nd ed. MIT Press.
