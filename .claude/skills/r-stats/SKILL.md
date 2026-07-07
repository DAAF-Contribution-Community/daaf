---
name: r-stats
description: >-
  R statistical modeling with base stats, sandwich, lmtest, car, broom. OLS/WLS/
  GLS via lm(), GLMs via glm() (logit, probit, Poisson, negative binomial),
  robust/clustered SEs via sandwich+lmtest, diagnostics via car, tidy output via
  broom. Use when execution language is R. Python equivalent: statsmodels. For FE
  regressions use fixest; for panel RE/between use plm; for complex surveys use
  survey-r.
autoload: never
metadata:
  audience: research-coders
  domain: r-library
  library-version: "R 4.5.3 stats"
  skill-last-updated: "2026-05-08"
  tags: ["r", "statistics", "regression", "glm", "diagnostics"]
---

# R Stats Skill

R's statistical modeling ecosystem centered on base `stats` with key extension
packages: `sandwich` for robust/clustered variance estimators, `lmtest` for
coefficient testing with custom covariance matrices, `car` for regression
diagnostics and hypothesis tests, `broom` for tidy model output, and
`MASS` for negative binomial regression. Covers OLS/WLS/GLS via `lm()`, GLMs
via `glm()` (logit, probit, Poisson, negative binomial, Gamma), robust and
clustered standard errors via sandwich+lmtest, diagnostics (VIF,
heteroskedasticity tests, normality tests), tidy output via broom, and classical
hypothesis tests (t, chi-squared, Wilcoxon, Fisher). Use when execution language
is R and the model does not require absorbed fixed effects or panel structure.
Python equivalent: `statsmodels`. For fixed effects regressions use `fixest`;
for panel RE/between/Fama-MacBeth use `plm`; for complex survey designs use
`survey-r`.

## What is R Stats?

R is the original statistical computing environment. The `stats` package ships
with every R installation and provides the core modeling functions that the
entire R ecosystem builds upon:

- **Formula interface**: `y ~ x1 + x2` — the original formula syntax that Python
  libraries (patsy, formulaic) later adopted
- **Linear models**: `lm()` for OLS, WLS, GLS; `summary()`, `confint()`,
  `predict()`, `anova()` for post-estimation
- **Generalized linear models**: `glm()` with family/link specifications
  (binomial/logit, Poisson/log, Gamma/inverse, etc.)
- **Classical tests**: `t.test()`, `chisq.test()`, `wilcox.test()`,
  `fisher.test()`, `prop.test()`, `ks.test()`, `cor.test()`
- **Time series**: `ts()`, `arima()`, `acf()`, `pacf()`, `stl()`

The extension packages covered by this skill complete the modeling toolkit:

| Package | Version | Role |
|---------|---------|------|
| `sandwich` | 3.1-1 | Robust (HC0-HC4) and clustered variance-covariance estimators |
| `lmtest` | 0.9-40 | `coeftest()` with custom vcov; `bptest()`, `dwtest()`, `bgtest()` |
| `car` | 3.1-5 | `vif()`, `linearHypothesis()`, `ncvTest()`, Anova (type II/III) |
| `broom` | 1.0.12 | `tidy()`, `glance()`, `augment()` for tidy model output |
| `MASS` | 7.3-65 | `glm.nb()` for negative binomial; `stepAIC()` |
| `modelsummary` | 2.6.0 | Publication-quality regression tables (multiple models) |
| `marginaleffects` | 0.32.0 | Average marginal effects, contrasts, predictions |

## Version Notes

- **R 4.5.3**: Base R stats included. The `|>` native pipe (R 4.1+) is the
  preferred pipe style in DAAF scripts (not magrittr `%>%`).
- **sandwich 3.1-1**: vcovHC types HC0-HC4, vcovCL for clustering, vcovHAC for
  time series, vcovBS for bootstrap.
- **lmtest 0.9-40**: coeftest(), waldtest(), bptest(), dwtest(), bgtest(),
  resettest(), grangertest().
- **car 3.1-5**: vif(), linearHypothesis(), Anova() type II/III, ncvTest(),
  influencePlot().
- **broom 1.0.12**: Tidiers for 100+ model classes including lm, glm, nls,
  t.test, and many extension package models.
- **MASS 7.3-65**: Ships with R. glm.nb() for negative binomial, polr() for
  ordered logit/probit, rlm() for robust regression.
- **modelsummary 2.6.0**: Supports lm, glm, fixest, plm, and many other model
  classes. Output formats: markdown, LaTeX, HTML, Word, PNG.
- **marginaleffects 0.32.0**: avg_slopes(), avg_comparisons(),
  avg_predictions(), hypotheses() for delta-method inference.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | lm() basics, summary(), confint(), predict(), formula syntax | Starting with R stats or need formula reference |
| `glm.md` | glm() families, MASS::glm.nb(), link functions, deviance, overdispersion | Non-linear models, binary/count outcomes |
| `robust-se.md` | sandwich vcovHC/vcovCL/vcovHAC, lmtest coeftest() | Robust or clustered standard errors |
| `diagnostics.md` | car::vif(), linearHypothesis(), residual analysis, heteroskedasticity tests | Checking model assumptions |
| `reporting.md` | broom tidy/glance/augment, modelsummary, marginaleffects | Tidy output, publication tables, marginal effects |
| `tests.md` | t.test(), chisq.test(), wilcox.test(), fisher.test(), correlation tests | Classical hypothesis tests |
| `time-series.md` | ts objects, arima(), acf/pacf, Durbin-Watson, ADF test | Time series analysis |
| `gotchas.md` | Formula pitfalls, factor contrasts, na.action, predict() type arg | Debugging common issues |

### Reading Order

1. **New to R stats?** Start with `quickstart.md` then `robust-se.md`
2. **Need GLM or logit/probit?** Read `quickstart.md` then `glm.md`
3. **Need robust or clustered SEs?** Read `robust-se.md`
4. **Checking model assumptions?** Read `diagnostics.md`
5. **Building publication tables?** Read `reporting.md`
6. **Coming from Python?** Read `quickstart.md` (R is the original formula syntax)

**The reference-file routing in this skill applies to advisory and brainstorming
turns as much as implementation.** Recommending a model, reviewing an analysis
plan, or answering a question that touches a routed topic calls for reading the
routed reference file just as much as writing code does — the reference files
carry curated caveats and environment-specific constraints (e.g., which
packages are pre-installed, sandwich function signatures) that this overview
and general knowledge lack.

## Related Skills

- **statsmodels**: Python equivalent for OLS/GLM/time series. If execution
  language is Python, use statsmodels instead of r-stats. API patterns differ
  (statsmodels requires `.fit()` call; R returns fitted object from `lm()`
  directly)
- **fixest**: Use instead of base R stats when model needs absorbed fixed
  effects, IV with FE, or DiD. fixest is faster for FE models; base R stats is
  broader for GLMs and classical tests
- **plm**: Use for panel data models (FE within, RE, between, first difference,
  Fama-MacBeth). plm extends the lm/formula interface for panel structure
- **survey-r**: Use for survey-weighted regression with complex designs. Base R
  `lm()` with weights is NOT equivalent to survey-weighted regression — it does
  not account for stratification, clustering, or finite population corrections
- **gt**: Publication-quality tables with gt and modelsummary. Load for
  formatted regression output beyond what broom provides -- modelsummary
  (covered in this skill's `reporting.md`) uses gt as its default backend
- **data-scientist**: Provides methodology guidance (when to use which model,
  assumption checking protocol). Load alongside r-stats for the "why"; r-stats
  provides the "how"
- **r-python-translation**: Cross-language reference mapping R stats functions to
  Python equivalents. Load when annotating R code for Python-background users

## Quick Decision Trees

### "I need to fit a regression model"

```
What kind of regression?
+-- Linear (continuous outcome)
|   +-- Basic OLS --> ./references/quickstart.md
|   +-- Weighted least squares --> ./references/quickstart.md (WLS section)
|   |   (WLS != survey-weighted regression -- for complex surveys, use survey-r)
|   +-- Robust to outliers (M-estimator) --> MASS::rlm() in ./references/quickstart.md
|   +-- Quantile regression --> quantreg::rq() (external package)
|   +-- Need fixed effects?
|       +-- Use fixest instead (faster FE absorption)
+-- Binary outcome (0/1)
|   +-- Logit --> ./references/glm.md
|   +-- Probit --> ./references/glm.md
+-- Count outcome (0, 1, 2, ...)
|   +-- Poisson --> ./references/glm.md
|   +-- Negative binomial --> ./references/glm.md (MASS::glm.nb)
|   +-- Zero-inflated --> pscl package (external)
+-- Ordinal (ordered categories)
|   +-- MASS::polr() --> ./references/glm.md
+-- GLM (custom family/link)
|   +-- glm() framework --> ./references/glm.md
+-- Need robust/clustered SEs?
    +-- sandwich + lmtest --> ./references/robust-se.md
```

### "I need to check model assumptions"

```
What assumption to check?
+-- Heteroskedasticity --> ./references/diagnostics.md
|   +-- Breusch-Pagan (lmtest::bptest)
|   +-- NCV test (car::ncvTest)
+-- Normality of residuals --> ./references/diagnostics.md
|   +-- Shapiro-Wilk (shapiro.test)
|   +-- Jarque-Bera (tseries::jarque.bera.test)
+-- Multicollinearity --> ./references/diagnostics.md
|   +-- VIF (car::vif)
+-- Specification / functional form --> ./references/diagnostics.md
|   +-- RESET test (lmtest::resettest)
+-- Serial correlation --> ./references/diagnostics.md
|   +-- Durbin-Watson (lmtest::dwtest)
|   +-- Breusch-Godfrey (lmtest::bgtest)
+-- Joint hypothesis test --> ./references/diagnostics.md
|   +-- car::linearHypothesis
+-- Influential observations --> ./references/diagnostics.md
    +-- Cook's distance, leverage, DFBETAS
```

### "I need classical hypothesis tests"

```
What test?
+-- Compare two means --> ./references/tests.md
|   +-- t.test() (parametric)
|   +-- wilcox.test() (non-parametric)
+-- Compare proportions --> ./references/tests.md
|   +-- prop.test()
+-- Test independence --> ./references/tests.md
|   +-- chisq.test() (large sample)
|   +-- fisher.test() (exact, small sample)
+-- Test correlation --> ./references/tests.md
|   +-- cor.test() (Pearson, Spearman, Kendall)
+-- Goodness of fit --> ./references/tests.md
|   +-- chisq.test() with expected frequencies
|   +-- ks.test() (Kolmogorov-Smirnov)
```

### "Something isn't working"

```
Common issues?
+-- Formula I() for arithmetic --> ./references/gotchas.md
+-- Factor contrasts (treatment vs sum) --> ./references/gotchas.md
+-- predict() type argument --> ./references/gotchas.md
+-- na.action behavior --> ./references/gotchas.md
+-- summary() vs anova() --> ./references/gotchas.md
+-- Convergence warnings (GLM) --> ./references/gotchas.md
+-- r-stats vs fixest boundary --> ./references/gotchas.md
```

## File-First Execution in Research Workflows

**Important:** In data research pipelines (see `CLAUDE.md`), R analyses are
executed through **script files**, not interactively. This ensures auditability
and reproducibility.

**The pattern:**
1. Write model code to `scripts/stage8_analysis/{step}_{model-name}.R`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory
file-first execution protocol covering complete code file writing, output
capture, and file versioning rules.

**See:**
- `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` -- Script execution protocol
  and format with validation

The examples below show R syntax. In research workflows, wrap them in scripts
following the file-first pattern.

---

## Quick Reference

### Essential Library Loading

```r
# --- Config ---
library(sandwich)         # Robust variance estimators
library(lmtest)           # Coefficient testing with custom vcov
library(car)              # Diagnostics: VIF, linearHypothesis
library(broom)            # Tidy model output
library(MASS)             # glm.nb(), polr(), rlm()
library(modelsummary)     # Publication tables
library(marginaleffects)  # Marginal effects
```

### Core Operations

| Operation | Code |
|-----------|------|
| OLS | `lm(y ~ x1 + x2, data = df)` |
| WLS | `lm(y ~ x1 + x2, data = df, weights = w)` |
| Logit | `glm(y ~ x1 + x2, data = df, family = binomial)` |
| Probit | `glm(y ~ x1 + x2, data = df, family = binomial(link = "probit"))` |
| Poisson | `glm(count ~ x1 + x2, data = df, family = poisson)` |
| Neg. binomial | `MASS::glm.nb(count ~ x1 + x2, data = df)` |
| Gamma | `glm(y ~ x1 + x2, data = df, family = Gamma(link = "log"))` |
| Robust SE (HC1) | `coeftest(fit, vcov = vcovHC(fit, type = "HC1"))` |
| Clustered SE | `coeftest(fit, vcov = vcovCL(fit, cluster = df$group))` |
| Summary | `summary(fit)` |
| Tidy output | `broom::tidy(fit, conf.int = TRUE)` |
| Model stats | `broom::glance(fit)` |
| Predict | `predict(fit, newdata = new_df)` |
| Confidence intervals | `confint(fit)` |
| VIF | `car::vif(fit)` |
| Joint hypothesis | `car::linearHypothesis(fit, c("x1 = 0", "x2 = 0"))` |
| Marginal effects | `marginaleffects::avg_slopes(fit)` |
| Pub table | `modelsummary::modelsummary(list(fit1, fit2))` |

### Formula Syntax

```r
# Additive terms
y ~ x1 + x2 + x3

# Interaction (with main effects)
y ~ x1 * x2           # equivalent to x1 + x2 + x1:x2

# Interaction only (no main effects)
y ~ x1 : x2

# Factor variable (explicit)
y ~ factor(region)

# Suppress intercept
y ~ x1 + x2 - 1       # or: y ~ 0 + x1 + x2

# Polynomial: I() protects arithmetic operators
y ~ x1 + I(x1^2)

# Log transformation
y ~ log(income) + age

# All pairwise interactions
y ~ (x1 + x2 + x3)^2
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| lm() basics | `./references/quickstart.md` |
| Formula syntax | `./references/quickstart.md` |
| summary() output | `./references/quickstart.md` |
| confint() | `./references/quickstart.md` |
| predict() | `./references/quickstart.md` |
| WLS / weighted regression | `./references/quickstart.md` |
| Model matrix / design matrix | `./references/quickstart.md` |
| anova() vs summary() | `./references/quickstart.md` |
| Comparison to statsmodels | `./references/quickstart.md` |
| glm() framework | `./references/glm.md` |
| Logit / probit | `./references/glm.md` |
| Poisson regression | `./references/glm.md` |
| Negative binomial (MASS) | `./references/glm.md` |
| Ordered logit/probit (MASS) | `./references/glm.md` |
| GLM families and links | `./references/glm.md` |
| Deviance and overdispersion | `./references/glm.md` |
| Odds ratios and IRR | `./references/glm.md` |
| Marginal effects | `./references/reporting.md` |
| Robust SEs (HC0-HC4) | `./references/robust-se.md` |
| Clustered SEs | `./references/robust-se.md` |
| HAC / Newey-West SEs | `./references/robust-se.md` |
| Bootstrap SEs | `./references/robust-se.md` |
| coeftest() | `./references/robust-se.md` |
| waldtest() | `./references/robust-se.md` |
| VIF / multicollinearity | `./references/diagnostics.md` |
| Breusch-Pagan test | `./references/diagnostics.md` |
| NCV test | `./references/diagnostics.md` |
| Shapiro-Wilk test | `./references/diagnostics.md` |
| RESET test | `./references/diagnostics.md` |
| Durbin-Watson test | `./references/diagnostics.md` |
| Breusch-Godfrey test | `./references/diagnostics.md` |
| linearHypothesis() | `./references/diagnostics.md` |
| Cook's distance | `./references/diagnostics.md` |
| Influence plots | `./references/diagnostics.md` |
| Residual analysis | `./references/diagnostics.md` |
| broom::tidy() | `./references/reporting.md` |
| broom::glance() | `./references/reporting.md` |
| broom::augment() | `./references/reporting.md` |
| modelsummary tables | `./references/reporting.md` |
| marginaleffects | `./references/reporting.md` |
| t.test() | `./references/tests.md` |
| chisq.test() | `./references/tests.md` |
| wilcox.test() | `./references/tests.md` |
| fisher.test() | `./references/tests.md` |
| prop.test() | `./references/tests.md` |
| ks.test() | `./references/tests.md` |
| cor.test() | `./references/tests.md` |
| ts objects | `./references/time-series.md` |
| arima() | `./references/time-series.md` |
| acf / pacf | `./references/time-series.md` |
| Durbin-Watson (time series) | `./references/time-series.md` |
| ADF test | `./references/time-series.md` |
| Formula pitfalls (I()) | `./references/gotchas.md` |
| Factor contrasts | `./references/gotchas.md` |
| na.action behavior | `./references/gotchas.md` |
| predict() type argument | `./references/gotchas.md` |
| Convergence warnings | `./references/gotchas.md` |
| r-stats vs fixest boundary | `./references/gotchas.md` |

## Citation

When base R stats functions are used as a primary analytical tool, include in
the report's Software & Tools references:

> R Core Team (2026). R: A Language and Environment for Statistical Computing.
> R Foundation for Statistical Computing, Vienna, Austria.
> https://www.R-project.org/

For extension packages, cite when they contribute substantially to the analysis:

> Zeileis, A. (2004). "Econometric Computing with HC and HAC Covariance Matrix
> Estimators." Journal of Statistical Software, 11(10), 1-17.
> (sandwich package)

> Zeileis, A. & Hothorn, T. (2002). "Diagnostic Checking in Regression
> Relationships." R News, 2(3), 7-10.
> (lmtest package)

> Fox, J. & Weisberg, S. (2019). An R Companion to Applied Regression, Third
> Edition. Sage, Thousand Oaks CA.
> (car package)

> Robinson, D., Hayes, A., & Couch, S. (2023). broom: Convert Statistical
> Objects into Tidy Tibbles. R package.
> (broom package)

> Arel-Bundock, V. (2022). "modelsummary: Data and Model Summaries in R."
> Journal of Statistical Software, 103(1), 1-23.
> (modelsummary package)

> Arel-Bundock, V., Greifer, N., & Heiss, A. (2024). "How to Interpret
> Statistical Models Using marginaleffects for R and Python." Journal of
> Statistical Software, 111(9), 1-32.
> (marginaleffects package)

**Cite when:** The package's functions are central to the analytical approach
(e.g., sandwich for robust inference, car for diagnostics).
**Do not cite when:** Only used incidentally for output formatting.
