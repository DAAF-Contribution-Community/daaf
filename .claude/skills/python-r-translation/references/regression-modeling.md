# Regression Modeling: R Explained for Python Users

Regression modeling is where R shines with unified interfaces. R provides a
single formula system (`y ~ x1 + x2`) that works identically across base R and
extension packages. Python fragments this across pyfixest, statsmodels, and
linearmodels with different APIs and formula engines.

This reference shows R regression code and explains it in terms Python users know.

DAAF's R modeling stack:
- **fixest** (primary): OLS, Poisson, IV, FE regression -- closest to pyfixest
- **base R stats** (general): lm/glm for simple models -- closest to statsmodels
- **plm** (panel): Within/RE/between estimators -- closest to linearmodels
- **lme4** (mixed effects): `lmer()`/`glmer()` -- closest to statsmodels MixedLM

> **Versions referenced:**
> R: fixest 0.14.0, lmtest 0.9-40, sandwich 3.1-1, plm 2.6-7, lme4 2.0-1
> Python: pyfixest 0.40.0, statsmodels 0.14.6, linearmodels 7.0
> See SKILL.md § Library Versions for the complete version table.

---

## 1. OLS Regression

### Basic OLS

```r
# R (base) -- you know this as smf.ols("y ~ x1 + x2", data=df).fit()
fit <- lm(y ~ x1 + x2, data = df)
summary(fit)
coef(fit)                # Python: fit.params
summary(fit)$r.squared   # Python: fit.rsquared
```

```r
# R (fixest) -- you know this as pf.feols("y ~ x1 + x2", data=df)
library(fixest)
fit <- feols(y ~ x1 + x2, data = df)
summary(fit)
coef(fit)
r2(fit, type = "r2")
```

### Key Differences

| R | Python (pyfixest) | Python (statsmodels) |
|---|-------------------|---------------------|
| `lm(y ~ x, data)` or `feols(y ~ x, data)` | `pf.feols("y ~ x", data)` | `smf.ols("y ~ x", data).fit()` |
| No `.fit()` needed | No `.fit()` needed | **`.fit()` required** |
| Unquoted formula | String formula | String formula |
| `coef(fit)` | `fit.coef()` | `fit.params` |
| `confint(fit)` | `fit.confint()` | `fit.conf_int()` |
| `predict(fit, newdata)` | `fit.predict(newdata)` | `fit.predict(newdata)` |
| `residuals(fit)` | `fit.resid()` | `fit.resid` |

---

## 2. Fixed Effects Regression

```r
# R (fixest) -- you know this as pf.feols("y ~ x | entity + year", data=df)
fit <- feols(y ~ x1 + x2 | entity + year, data = df)

# Interacted FE -- you know this as pf.feols("y ~ x | entity ^ year", data=df)
fit <- feols(y ~ x1 | entity^year, data = df)
```

The formula syntax is nearly identical between fixest and pyfixest. Both use `|`
to separate regressors from absorbed fixed effects.

### Clustered Standard Errors

| R (fixest) | Python (pyfixest) |
|-----------|-------------------|
| `feols(..., vcov = ~entity)` | `pf.feols(..., vcov={"CRV1": "entity"})` |
| `feols(..., vcov = ~entity + year)` | `pf.feols(..., vcov={"CRV1": "entity+year"})` |
| `feols(..., vcov = "hetero")` | `pf.feols(..., vcov="hetero")` |
| `summary(fit, vcov = ~state)` | `fit.vcov({"CRV1": "state"})` |

The main syntax difference: R uses a one-sided formula (`~entity`), Python
uses a dictionary (`{"CRV1": "entity"}`).

---

## 3. Instrumental Variables / 2SLS

### fixest Three-Part Formula (Identical in Both)

```r
# R -- Y ~ exogenous | FE | endogenous ~ instruments
fit <- feols(y ~ x_exog | entity + year | x_endog ~ z_inst, data = df)
```

```python
# Python -- identical formula structure
fit = pf.feols("y ~ x_exog | entity + year | x_endog ~ z_inst", data=df)
```

The three-part formula is identical in both languages.

---

## 4. Panel Data Models

```r
# R (plm) -- you know this as linearmodels.PanelOLS
library(plm)
pdata <- pdata.frame(df, index = c("entity", "year"))
fit <- plm(y ~ x1 + x2, data = pdata, model = "within")  # FE
fit <- plm(y ~ x1 + x2, data = pdata, model = "random")  # RE
```

```python
# Python -- requires pandas MultiIndex
df_panel = df.set_index(["entity", "year"])
fit = PanelOLS.from_formula("y ~ x1 + x2 + EntityEffects", data=df_panel).fit()
```

| R (plm) | Python (linearmodels) |
|---------|----------------------|
| `plm(..., model="within")` | `PanelOLS(..., "y ~ x + EntityEffects")` |
| `plm(..., model="random")` | `RandomEffects(..., "y ~ 1 + x")` |
| `plm(..., model="between")` | `BetweenOLS(..., "y ~ 1 + x")` |
| `plm(..., model="fd")` | `FirstDifferenceOLS(...)` |
| `plm(..., effect="twoways")` | `PanelOLS(..., "y ~ x + EntityEffects + TimeEffects")` |

R uses `pdata.frame()` with an `index` argument. Python requires manually setting
a pandas MultiIndex.

### Mixed Effects Models (lme4 for MixedLM users)

The Python route for mixed/multilevel models is `statsmodels` MixedLM
(`smf.mixedlm`), NOT linearmodels — linearmodels has no mixed-effects estimator.
lme4 is available in the DAAF R environment (installed as a dependency).

```r
# R (lme4) -- you know this as smf.mixedlm("y ~ x", df, groups=df["group"]).fit()
library(lme4)
fit <- lmer(y ~ x + (1 | group), data = df)            # Random intercept
fit <- lmer(y ~ x + (1 + x | group), data = df)        # Random slope + intercept
```

```python
# Python (statsmodels MixedLM)
fit = smf.mixedlm("y ~ x", data=df, groups=df["group"]).fit()                      # Random intercept
fit = smf.mixedlm("y ~ x", data=df, groups=df["group"], re_formula="~x").fit()     # Random slope + intercept
```

| R (lme4) | Python (statsmodels) |
|----------|----------------------|
| `lmer(y ~ x + (1 \| g))` | `smf.mixedlm("y ~ x", df, groups=df["g"]).fit()` |
| `lmer(y ~ x + (1 + x \| g))` | `smf.mixedlm("y ~ x", df, groups=df["g"], re_formula="~x").fit()` |
| `glmer(..., family = binomial)` | `BinomialBayesMixedGLM` (approximate; no exact equivalent) |

Key difference: R encodes random effects inside the formula (`(1 | group)`);
Python passes them as separate `groups=` / `re_formula=` arguments. lme4's
generalized mixed models (`glmer`) have no exact statsmodels equivalent.

---

## 5. GLM / Logit / Probit

```r
# R -- you know logit as smf.logit("y ~ x", data=df).fit()
fit <- glm(y ~ x1 + x2, data = df, family = binomial(link = "logit"))

# R (fixest with FE) -- GLM + FE works natively!
fit <- feglm(y ~ x1 | entity + year, data = df, family = binomial)
```

R fixest's `feglm()` supports logit/probit with high-dimensional FE. This is a
**major gap in pyfixest** -- `pf.feglm()` does NOT support fixed effects.

| R | Python |
|---|--------|
| `glm(y ~ x, family = binomial)` | `smf.logit("y ~ x", data=df).fit()` |
| `glm(y ~ x, family = poisson)` | `smf.poisson("y ~ x", data=df).fit()` |
| `feglm(y ~ x | fe, family = binomial)` | **Not supported** in pyfixest |
| `fepois(y ~ x | fe)` | `pf.fepois("y ~ x | fe", data=df)` |

---

## 6. Robust and Clustered Standard Errors

R integrates SEs more cleanly than Python. fixest provides them as a first-class
feature; base R uses the sandwich + lmtest ecosystem.

| SE Type | R (fixest) | R (sandwich) | Python (pyfixest) | Python (statsmodels) |
|---------|-----------|-------------|-------------------|---------------------|
| IID | Default | Default | `"iid"` | Default |
| HC1 | `vcov = "hetero"` | `vcovHC(type="HC1")` | `"hetero"` | `cov_type="HC1"` |
| 1-way cluster | `vcov = ~g` | `vcovCL(cluster=...)` | `{"CRV1": "g"}` | `cov_type="cluster"` |
| 2-way cluster | `vcov = ~g1 + g2` | `vcovCL(cluster=cbind(...))` | `{"CRV1": "g1+g2"}` | Not built-in |
| Newey-West | `vcov = "NW"` | `vcovHAC(fit)` | `"NW"` | `cov_type="HAC"` |

---

## 7. Model Comparison Tables

```r
# R (fixest) -- you know this as pf.etable([fit1, fit2, fit3])
library(fixest)
etable(fit1, fit2, fit3)
etable(fit1, fit2, tex = TRUE)       # LaTeX output

# R (modelsummary) -- broader model support
library(modelsummary)
modelsummary(list(fit1, fit2, fit3))
```

pyfixest's `etable()` mirrors R fixest's `etable()` closely.

---

## 8. Formula Syntax Reference

R has ONE universal formula system. Python has three incompatible dialects.

| Feature | R formula | patsy (statsmodels) | formulaic (pyfixest) |
|---------|-----------|--------------------|--------------------|
| Intercept | Included by default | Included by default | Included by default |
| No intercept | `y ~ x - 1` | `"y ~ x - 1"` | `"y ~ x - 1"` |
| Interaction | `y ~ x1:x2` | `"y ~ x1:x2"` | `"y ~ x1:x2"` |
| Full cross | `y ~ x1*x2` | `"y ~ x1*x2"` | `"y ~ x1*x2"` |
| Fixed effects | `y ~ x | fe` (fixest) | N/A (use dummies) | `"y ~ x | fe"` |
| Categorical | `factor(x)` | `C(x)` | `C(x)` |
| Set reference | `relevel(factor(x), ref="a")` | `C(x, Treatment('a'))` | `i(x, ref='a')` |

**Key insight for Python users:** In R, `y ~ x1 + x2` works everywhere: `lm()`,
`glm()`, `feols()`, `svyglm()`, `plm()`. You learn one formula syntax and use
it with every modeling function. This is R's greatest ergonomic advantage for
statistical modeling.

---

## 9. Model Diagnostics

| R | Python |
|---|--------|
| `summary(fit)` | `fit.summary()` |
| `car::vif(fit)` | `variance_inflation_factor()` (loop required) |
| `lmtest::bptest(fit)` | `sm.stats.diagnostic.het_breuschpagan(...)` |
| `lmtest::dwtest(fit)` | `sm.stats.stattools.durbin_watson(fit.resid)` |
| `plot(fit)` | `sm.graphics.plot_regress_exog(fit)` |

R's diagnostic functions are typically single-call convenience wrappers.
Python often requires assembling the inputs manually.

> **Sources:** Berge, Butts, & McDermott, *fixest* (CRAN);
> Fischer et al., *pyfixest* (pyfixest.org, accessed 2026-03-28);
> Seabold & Perktold, *statsmodels* (v0.14.6);
> Croissant & Millo, *plm* (CRAN)
