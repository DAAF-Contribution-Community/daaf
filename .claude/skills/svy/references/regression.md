# svy Regression Reference

svy v0.19.0 — syntax and library guidance only. Signatures and the coefficient schema below
were verified against the installed library (`/daaf/scripts/smoke_tests/smoke_svy_a.py`).
**GLM inference is now cross-validated against R** (2026-07-15): coefficients, SEs, p-values,
and residual df agree with R `survey::svyglm(family=quasibinomial()/quasipoisson())` to <1e-6
relative on a matched stratified-clustered design (see "Cross-Validating Inference"). One
caveat remains on `margins()` — its continuous-predictor AME matches R to ~0.1% (point) /
~0.9% (SE), but it emits **only** continuous-predictor slopes and omits categorical-level
contrasts (see "Marginal Effects").

---

## Contents

1. [Overview: Survey-Weighted GLM](#overview-survey-weighted-glm)
2. [The `glm.fit()` Signature and Return Object](#the-glmfit-signature-and-return-object)
3. [Survey-Weighted Linear Regression (Gaussian)](#survey-weighted-linear-regression-gaussian)
4. [Survey-Weighted Logistic Regression (Binomial)](#survey-weighted-logistic-regression-binomial)
5. [Survey-Weighted Poisson Regression](#survey-weighted-poisson-regression)
6. [Survey-Weighted Gamma Regression](#survey-weighted-gamma-regression)
7. [Link Functions](#link-functions)
8. [Specifying Predictors](#specifying-predictors)
9. [Extracting Results](#extracting-results)
10. [Marginal Effects](#marginal-effects)
11. [Cross-Validating Inference (p-values / margins vs. R)](#cross-validating-inference-p-values--margins-vs-r)
12. [Survey Regression vs. WLS vs. Cluster-Robust SEs](#survey-regression-vs-wls-vs-cluster-robust-ses)
13. [Diagnostics and Model Fit](#diagnostics-and-model-fit)
14. [Domain-Restricted Regression](#domain-restricted-regression)
15. [The rpy2 Bridge for Unsupported Models](#the-rpy2-bridge-for-unsupported-models)
16. [Complete Regression Workflow Example](#complete-regression-workflow-example)

---

## Overview: Survey-Weighted GLM

svy fits generalized linear models (GLMs) that account for the complex survey design in both point estimation and variance estimation. The interface is `sample.glm.fit()`:

```python
model = sample.glm.fit(
    y="outcome_variable",
    x=["predictor1", "predictor2", svy.Cat("categorical_var")],   # svy.Cat REQUIRED for strings
    family="gaussian",   # "gaussian" | "binomial" | "poisson" | "gamma"
)
```

**Supported families (all four confirmed to fit at 0.19.0):**

| Family | Use Case | Default Link |
|--------|----------|--------------|
| `"gaussian"` | Continuous outcome (linear regression) | Identity |
| `"binomial"` | Binary outcome (logistic regression) | Logit |
| `"poisson"` | Count outcome (Poisson regression) | Log |
| `"gamma"` | Positive, right-skewed continuous outcome (e.g., costs, expenditures) | Inverse (canonical) — assumed default, not introspected; pass `link=` explicitly |

**Not supported in svy** (use the rpy2 bridge + R survey package):
- Negative binomial
- Ordinal logistic (`svyolr` in R)
- Cox proportional hazards (`svycoxph` in R)
- Multinomial logistic
- Quasi-families

The design-based SEs produced by `sample.glm.fit()` are model-robust "sandwich" estimators that account for stratification, clustering, and unequal probability of selection — analogous to R's `survey::svyglm()`. (Coefficients, SEs, p-values, and residual df are verified equal to R `svyglm` with quasi-families to <1e-6 relative — see the cross-validation section.)

---

## The `glm.fit()` Signature and Return Object

Observed signature (note `x` and `family` are keyword-only):

```python
sample.glm.fit(
    y,                 # str: outcome column (positional)
    *,
    x=None,            # Sequence[Feature]: predictors (strings + svy.Cat(...))
    intercept=True,    # include an intercept
    family="gaussian", # "gaussian" | "binomial" | "poisson" | "gamma"
    link=None,         # None -> canonical link; else see "Link Functions"
    where=None,        # polars expression to restrict the fit (see "Domain-Restricted Regression")
    drop_nulls=True,   # drop rows with nulls in model columns
    tol=1e-08,         # convergence tolerance
    max_iter=100,      # max IRLS iterations
    alpha=0.05,        # 1 - confidence level for coefficient CIs
) -> GLM
```

**`fit()` returns a `GLM` object directly.** Call `.to_polars()` on it for the coefficient table — there is no separate `.fitted` accessor to reach through (that was a 0.13.0-era pattern). The coefficient-table schema is:

```
['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']
```

Observed term naming: the intercept row is `_intercept_`; a continuous predictor keeps its name (`age`); a `svy.Cat("gender")` predictor expands to one row per non-reference level named `{var}_{level}` (e.g., `gender_Male`).

```python
model = sample.glm.fit(y="employed", x=["age", svy.Cat("gender")], family="binomial")
coef = model.to_polars()
#   term          estimate   std_err   conf_low   conf_high  statistic  p_value   df
#   _intercept_   -0.5520    0.2484    -1.0737    -0.0302    -2.2225    0.0393    18
#   age            0.0107    0.0040     0.0024     0.0190     2.7006    0.0146    18
#   gender_Male    0.6325    0.2112     0.1888     1.0762     2.9951    0.0078    18
```

---

## Survey-Weighted Linear Regression (Gaussian)

```python
import svy
import polars as pl

data = pl.read_parquet("data/raw/nhanes.parquet")
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)

# INTENT: Estimate association between age and BMI, controlling for gender
# REASONING: Linear model appropriate for continuous outcome (BMI)
# ASSUMES: Linear relationship between age and BMI within the modeled range
model = sample.glm.fit(
    y="bmxbmi",
    x=["ridageyr", svy.Cat("riagendr")],
    family="gaussian",
)
print(model.to_polars())
```

Gaussian-family coefficients are interpreted identically to OLS: each is the expected change in Y per one-unit change in X, holding others constant. SEs, statistics, and p-values reflect the complex survey design, not SRS assumptions.

---

## Survey-Weighted Logistic Regression (Binomial)

```python
# INTENT: Model probability of obesity as a function of demographics
# REASONING: Binary outcome (obese yes/no) requires logistic regression
# ASSUMES: The outcome variable is coded 0/1
model = sample.glm.fit(
    y="obese_flag",
    x=["ridageyr", "indfmpir", svy.Cat("riagendr"), svy.Cat("ridreth1")],
    family="binomial",
)
coef = model.to_polars()
```

### Interpreting Logistic Output (odds ratios)

Coefficients are on the **log-odds** scale. Exponentiate for odds ratios and their CI bounds:

```python
import numpy as np

coef = model.to_polars()   # term, estimate, std_err, conf_low, conf_high, statistic, p_value, df
coef = coef.with_columns(
    np.exp(pl.col("estimate")).alias("odds_ratio"),
    np.exp(pl.col("conf_low")).alias("or_ci_low"),
    np.exp(pl.col("conf_high")).alias("or_ci_high"),
)
```

### Quasi-Binomial in R vs. svy

In R's `survey::svyglm()`, `family=quasibinomial()` is preferred over `family=binomial()` to avoid warnings about non-integer successes from weighted data. svy handles this internally — use `family="binomial"` directly.

---

## Survey-Weighted Poisson Regression

```python
# INTENT: Model count of doctor visits as a function of health indicators
# REASONING: Count outcome with no upper bound suits Poisson regression
# ASSUMES: Conditional mean equals conditional variance (Poisson assumption)
model = sample.glm.fit(
    y="doctor_visits",
    x=["ridageyr", svy.Cat("health_status")],
    family="poisson",
)
```

Coefficients are on the **log scale**; exponentiate for incidence rate ratios (IRRs). A coefficient of 0.3 means `exp(0.3) = 1.35`, a 35% higher rate per unit increase.

### Overdispersion Caveat

Poisson assumes conditional variance equals conditional mean. Survey data often exhibits overdispersion. The design-based sandwich SEs partially accommodate this, but severe overdispersion may still mislead. For negative binomial (overdispersed Poisson), use the rpy2 bridge + R's `survey::svyglm(family=quasipoisson())`.

---

## Survey-Weighted Gamma Regression

**New family at 0.19.0.** Gamma regression suits positive, right-skewed continuous outcomes — health costs, expenditures, length-of-stay — where a linear model on the raw scale is inappropriate. The smoke test confirmed a gamma GLM fits and returns the same 8-column coefficient schema.

```python
# INTENT: Model medical expenditure (positive, right-skewed) on demographics
# REASONING: Gamma family handles the skew and the positive-only support
# ASSUMES: Outcome is strictly positive; a log link keeps predictions positive
model = sample.glm.fit(
    y="total_expenditure",
    x=["age", svy.Cat("insurance_status")],
    family="gamma",
    link="log",          # log link is the common choice for gamma cost models
)
```

Gamma's canonical (inverse) link is assumed to be the default — this was not directly introspected, so pass `link=` explicitly rather than relying on the default. For cost models a `link="log"` is usually preferred so coefficients are interpretable as multiplicative rate effects.

---

## Link Functions

Pass `link=` to override the canonical link. Observed options:

```
"identity" | "logit" | "log" | "inverse" | "inverse_squared"
```

```python
# Log-binomial model (risk ratios instead of odds ratios)
model = sample.glm.fit(y="disease", x=["exposure"], family="binomial", link="log")
```

Non-canonical links (e.g., log-binomial for risk ratios) may have convergence difficulties; if the fit does not converge, raise `max_iter` or loosen `tol`, and consider whether the canonical link is more appropriate. Link/family combinations beyond the canonical pairings were not individually smoke-tested — verify convergence and sanity-check estimates.

---

## Specifying Predictors

### Continuous Predictors

Pass variable names as strings in the `x` list:

```python
x=["age", "income", "bmi"]
```

### Categorical Predictors with svy.Cat (REQUIRED for strings)

**svy does not auto-detect categorical predictors.** A raw string/categorical column passed as a predictor raises `ValueError: Failed to prepare data: conversion from str to f64 failed` (svy strict-casts predictors to float). Wrap every string/categorical predictor in `svy.Cat()`:

```python
x=["age", svy.Cat("education"), svy.Cat("region")]
```

Observed signature: `svy.Cat(name, ref=None)`. `svy.Cat()` creates indicator (dummy) variables for each level with one level omitted as reference; pass `ref=` to choose the reference level explicitly (otherwise the first level is used). Numeric predictors that are actually categorical (e.g., an integer-coded region) should also be wrapped in `svy.Cat()` so they are dummy-coded rather than treated as continuous.

### Mixing Continuous and Categorical

```python
model = sample.glm.fit(
    y="income",
    x=[
        "age",                          # continuous
        "years_education",              # continuous
        svy.Cat("gender"),              # categorical (2 levels)
        svy.Cat("race_ethnicity"),      # categorical (5 levels)
    ],
    family="gaussian",
)
```

### Interactions

svy has no formula interface; pre-compute interaction columns in Polars before building the `Sample`:

```python
import polars as pl
data = data.with_columns(
    (pl.col("age") * pl.col("income")).alias("age_x_income")
)
sample = svy.Sample(data, design=design)
model = sample.glm.fit(y="bmi", x=["age", "income", "age_x_income"], family="gaussian")
```

---

## Extracting Results

### Coefficient Table (the verified path)

```python
model = sample.glm.fit(y="bmxbmi", x=["ridageyr", svy.Cat("riagendr")], family="gaussian")

# Print the model
print(model)

# Coefficient table as a Polars DataFrame (confirmed schema)
coef = model.to_polars()
# ['term','estimate','std_err','conf_low','conf_high','statistic','p_value','df']
```

**Important:** `sample.glm` returns a fresh `GLM` accessor each time it is accessed (it is a property). Hold a reference to the return value of `.fit()` — that `GLM` object is what carries the results and `.margins()`.

### Model Statistics, Prediction, Residuals

> **[unverified at 0.19.0]** The 0.13.0 skill documented `model.fitted`, `fit.coefs` (list of `GLMCoef`), `fit.stats` (`GLMStats` with `.n`, `.r_squared`, `.aic`, `.bic`, `.deviance`), and `model.predict(new_data=, y_col=)` returning fitted values / residuals. These were **not** confirmed against the 0.19.0 build (only `.to_polars()` and `.margins()` were exercised). Before using them, introspect the returned object: `[a for a in dir(model) if not a.startswith("_")]` and `inspect.signature(model.predict)`. Do not report model-fit statistics or residual diagnostics whose accessor you have not confirmed on the installed library.

### Reporting Results

When reporting survey regression results:
1. State the survey design (strata, PSU, weight variable)
2. Report the variance estimation method (Taylor linearization or replicate type)
3. Report design-based degrees of freedom (the `df` column, not sample size minus parameters)
4. Report coefficients with design-based SEs and CIs
5. Note the effective sample size if substantially smaller than n
6. p-values, SEs, and residual df are verified equal to R `svyglm` (quasi-families) to <1e-6 relative — no provisional flagging needed for standard designs; spot-check only extraordinary ones (see the next section)

---

## Marginal Effects

`model.margins()` computes average marginal effects (AME). Observed signature and return:

```python
model.margins(at=None, variables=None, alpha=0.05) -> GLMMargins | list[GLMMargins]
```

- The **default call returns a `list[GLMMargins]`** containing **only continuous predictors** (one element per continuous term; categorical-level contrasts are omitted — see the coverage note below). Iterate it.
- Each element's `.to_polars()` has schema `['term', 'margin', 'se', 'lci', 'uci']`.
- `at=` (a `dict[str, list]`) computes marginal effects at representative values; `variables=` restricts to specific predictors.

```python
margins = model.margins()                    # list[GLMMargins]
for m in margins:
    print(m.to_polars())                     # ['term','margin','se','lci','uci']
```

> **Quantified caveat + coverage gap (cross-validated 2026-07-15).** The continuous-predictor AME agrees with R `marginaleffects::avg_slopes()` to ~0.1% on the point estimate and ~0.9% on the SE — a small numerical-method difference (finite-difference / delta-method conventions), not a design error, so the continuous AME is safe to report. **The more important limitation is coverage:** `margins()` emits **only** continuous-predictor slopes. Categorical-level contrasts (e.g., a gender effect) are **absent** from its output — the returned `list[GLMMargins]` contains only the continuous term(s). Compute categorical-level contrasts from the coefficient table (`model.to_polars()`) or in R (`avg_slopes()` reports them). Evidence: `/daaf/scripts/scratch/xval_svy_r_05_compare.py`.

---

## Cross-Validating Inference (p-values / margins vs. R)

GLM inference has been cross-validated against R (2026-07-15; evidence `/daaf/scripts/scratch/xval_svy_r_05_compare.py`):

1. **Coefficients, SEs, p-values, and residual df** — verified equal to R `survey::svyglm(family=quasibinomial()/quasipoisson())` to **<1e-6 relative** on a matched stratified-clustered design (24 PSUs, Taylor variance, logistic + Poisson). The df convention is identical: `df = degf(design) − n_predictors`, and both use a **t-statistic on that df** (no t-vs-z discrepancy). The historical upstream issue-#5 report of "slightly different p-values" did **not** reproduce at 0.19.0; it plausibly originated from comparing svy against R `family=binomial()` (normal / z-based) rather than `quasibinomial()` — *labeled inference, not tested (only `quasibinomial()` was compared here).*
2. **`margins()`** — continuous-predictor AME matches R `marginaleffects::avg_slopes()` to ~0.1% (point) / ~0.9% (SE); see "Marginal Effects" for the caveat and the categorical-contrast coverage gap.

The verification used one synthetic design (24 PSUs, one 2-level categorical, quasi-families only), so the recipe below is now a **spot-check** rather than a mandatory pre-publication gate: for extraordinary designs (many strata, extreme weights, multi-level categorical predictors) still spot-check inference-critical results against R. The rpy2 bridge below is the in-process way to do this; a parallel standalone R script using `survey::svyglm()` on the same design is equally valid (and often cleaner for the audit trail).

```python
# Cross-validation sketch: fit the same model in R via rpy2 and compare p_value / margins
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects.packages import importr

pandas2ri.activate()
survey_r = importr("survey")
r_design = survey_r.svydesign(
    ids=ro.Formula("~sdmvpsu"), strata=ro.Formula("~sdmvstra"),
    weights=ro.Formula("~wtmec2yr"), data=data.to_pandas(), nest=True,
)
r_model = survey_r.svyglm(ro.Formula("obese_flag ~ ridageyr + riagendr"),
                          design=r_design, family=ro.r("quasibinomial()"))
print(ro.r.summary(r_model))   # compare coefficient p-values against model.to_polars()
```

Document the cross-validation in an `# ASSUMES:`/`# REASONING:` comment noting whether svy and R agreed.

---

## Survey Regression vs. WLS vs. Cluster-Robust SEs

This distinction is critical. Three approaches look superficially similar but are fundamentally different:

### 1. Survey-Weighted Regression (svy)

```python
design = svy.Design(stratum="strata", psu="psu", wgt="weight")
sample = svy.Sample(data, design=design)
model = sample.glm.fit(y="y", x=["x1", "x2"], family="gaussian")
```

Uses weights in point estimation, uses the full design (strata + PSU + weights) for variance, produces design-based degrees of freedom (# PSUs − # strata), and accounts for stratification (reduces variance), clustering (increases variance), and unequal selection.

### 2. Weighted Least Squares (statsmodels WLS)

```python
import statsmodels.formula.api as smf
results = smf.wls("y ~ x1 + x2", data=df, weights=df["weight"]).fit()
```

Uses weights in point estimation only; does NOT account for stratification or clustering. **Produces incorrect SEs for survey data — typically too small.**

### 3. Cluster-Robust Standard Errors (statsmodels / pyfixest)

```python
results = smf.ols("y ~ x1 + x2", data=df).fit(cov_type="cluster", cov_kwds={"groups": df["psu"]})
```

Accounts for within-cluster correlation only; does NOT use survey weights (unless combined with WLS) and does NOT account for stratification or unequal selection.

### Summary Comparison

| Aspect | svy Survey Regression | statsmodels WLS | Cluster-Robust SEs |
|--------|----------------------|-----------------|-------------------|
| Weights in point estimates | Yes | Yes | No (unless combined) |
| Stratification in SE | Yes | No | No |
| Clustering in SE | Yes | No | Yes |
| Unequal selection in SE | Yes | No | No |
| Degrees of freedom | Design-based | Model-based | Large-sample |
| Correct for complex surveys | **Yes** | **No** | **No** |

**Rule of thumb:** If you have data from a complex survey with known design variables, use svy. If you have non-survey data with clustered observations, cluster-robust SEs are appropriate.

---

## Diagnostics and Model Fit

### R-Squared in Survey Context

Traditional R-squared is not well-defined for survey-weighted regression because the weights change the effective sample. Some implementations report a pseudo-R-squared. Interpret with caution.

### Residual Analysis

> **[unverified at 0.19.0]** Prediction/residual accessors (`model.predict(new_data=, y_col=)` returning `.yhat`/`.residuals`, and a `pred.to_polars()`) were documented for 0.13.0 but not confirmed on the installed build. Introspect `inspect.signature(model.predict)` before use. Methodologically: residual plots for survey regressions should use weighted residuals — unweighted residual plots can mislead because they treat all observations equally regardless of their population representation.

### Specification Concerns

Standard diagnostic tests (Breusch-Pagan, RESET, VIF) from statsmodels assume simple random samples. For survey data:
- **Multicollinearity**: VIF on the unweighted design matrix still detects collinearity, though not its impact on survey SEs
- **Functional form**: Plot weighted residuals against predictors; formal tests need survey-adjusted versions
- **Influential observations**: Observations with large weights are inherently influential by design — they represent more of the population. Do not remove them without substantive justification

### Model Comparison

For comparing nested survey regression models, use Wald tests based on the design-based covariance matrix rather than likelihood ratio tests (which assume independent observations). If you need AIC/BIC, first confirm the model-statistics accessor on the installed build (see "Model Statistics" above).

---

## Domain-Restricted Regression

To fit a regression within a subpopulation, do **not** pre-filter the data (that discards PSUs/strata and corrupts the design). At 0.19.0 `glm.fit()` accepts a **`where=`** parameter (a polars expression) that restricts the fit while keeping the design:

```python
import polars as pl

# Fit the model on women only, preserving the full design structure
model = sample.glm.fit(
    y="income",
    x=["age", svy.Cat("education")],
    family="gaussian",
    where=pl.col("gender") == "Female",
)
```

> This resolves the 0.13.0 limitation (where `fit()` had no `by=`/`subset=`/`where=`). The `where=` parameter is **signature-confirmed** and takes a polars expression (a string raises `TypeError`), consistent with the estimation `where=`. Its **numerical correctness for domain variance was not cross-checked** against R at 0.19.0 — for inference-critical domain models, validate the SEs against `svyglm(..., design=subset(design, ...))` in R (see cross-validation above). Do not pre-filter into a new `Sample` — that is the methodologically wrong path `where=` exists to replace.

---

## The rpy2 Bridge for Unsupported Models

When svy does not support the needed model (ordinal logistic, Cox survival, negative binomial, etc.), use R's survey package via rpy2. (The same bridge doubles as the cross-validation path for p-values/margins — see above.)

### Setup

```python
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects.packages import importr

pandas2ri.activate()
survey_r = importr("survey")

df_pandas = data.to_pandas()   # rpy2 uses the pandas bridge

r_design = survey_r.svydesign(
    ids=ro.Formula("~psu_id"),
    strata=ro.Formula("~stratum"),
    weights=ro.Formula("~weight"),
    data=df_pandas,
    nest=True,
)
```

### Ordinal Logistic

```python
r_model = survey_r.svyolr(ro.Formula("ordered_outcome ~ age + education"), design=r_design)
print(ro.r.summary(r_model))
```

### Cox Proportional Hazards

```python
r_model = survey_r.svycoxph(ro.Formula("Surv(time, event) ~ age + treatment"), design=r_design)
print(ro.r.summary(r_model))
```

### Negative Binomial (via Quasi-Poisson)

```python
r_model = survey_r.svyglm(ro.Formula("count ~ age + region"), design=r_design,
                          family=ro.r("quasipoisson()"))
print(ro.r.summary(r_model))
```

**Decision rule:** If `family` is not `"gaussian"`, `"binomial"`, `"poisson"`, or `"gamma"`, use the rpy2 bridge. Document bridge usage with `# REASONING:` comments explaining why svy was insufficient.

---

## Complete Regression Workflow Example

```python
import svy
import polars as pl
import numpy as np

# --- Config ---
DATA_PATH = "data/raw/2026-07-15_nhanes_demo_exam.parquet"

# --- Load ---
data = pl.read_parquet(DATA_PATH)
print(f"Loaded {data.shape[0]} rows, {data.shape[1]} columns")

# --- Design ---
# INTENT: NHANES 2017-2020 uses a complex multi-stage probability design
# REASONING: sdmvstra/sdmvpsu are masked design variables; wtmec2yr is the
#   2-year MEC exam weight appropriate for variables collected during the exam
# ASSUMES: Analysis restricted to MEC-examined participants aged 20+
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)

# --- Transform (do prep in Polars, then build the Sample) ---
# INTENT: Age-squared term for a nonlinear age effect on BMI
data = data.with_columns((pl.col("ridageyr") ** 2).alias("age_sq"))
sample = svy.Sample(data, design=design)

# --- Analysis ---
# INTENT: Estimate association between demographics and BMI
# REASONING: Gaussian family for continuous outcome; design-based SEs
# ASSUMES: Linear in parameters; additive effects; no unmeasured confounders
model = sample.glm.fit(
    y="bmxbmi",
    x=["ridageyr", "age_sq", "indfmpir", svy.Cat("riagendr"), svy.Cat("ridreth1")],
    family="gaussian",
)

# --- Validate ---
coef = model.to_polars()   # ['term','estimate','std_err','conf_low','conf_high','statistic','p_value','df']
print(coef)
assert coef.height >= 1, "no coefficients returned"
assert (coef.get_column("std_err") > 0).all(), "non-positive SE(s)"
# NOTE: coefficients/SEs/p-values/df are verified equal to R svyglm (quasi-families)
#   to <1e-6 relative at 0.19.0 (see "Cross-Validating Inference"). Spot-check only
#   extraordinary designs (many strata, extreme weights, multi-level categoricals).
```
