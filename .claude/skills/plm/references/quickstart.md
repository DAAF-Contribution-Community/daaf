# plm Quickstart

A technical reference for using plm 2.6-7 in R. Covers pdata.frame setup,
plm() basics, model= argument, summary output, coeftest with robust vcov,
and syntax comparison with linearmodels (Python). No methodology content --
syntax and library guidance only.

## Contents

- [Setup](#setup)
- [The pdata.frame Requirement](#the-pdataframe-requirement)
- [Your First Panel Model](#your-first-panel-model)
- [The model= Argument](#the-model-argument)
- [Reading the Summary Output](#reading-the-summary-output)
- [Post-Estimation Essentials](#post-estimation-essentials)
- [Panel Dimensions and Balance](#panel-dimensions-and-balance)
- [Quick Syntax Comparison: plm vs linearmodels vs fixest](#quick-syntax-comparison-plm-vs-linearmodels-vs-fixest)
- [References](#references)

---

## Setup

### Loading plm

```r
library(plm)
library(lmtest)   # coeftest() for robust inference
library(arrow)    # parquet I/O (DAAF convention)
```

plm is already installed in the DAAF container (v2.6-7, R 4.5.3). No
additional installation is needed.

### Built-in Datasets

plm ships with classic panel datasets:

| Dataset | Description | Key Columns |
|---------|-------------|-------------|
| `Grunfeld` | Investment data (10 firms, 20 years) | `inv`, `value`, `capital`, `firm`, `year` |
| `Produc` | US state production (48 states, 17 years) | `gsp`, `pcap`, `pc`, `emp`, `unemp`, `state`, `year` |
| `Wages` | Individual wage panel (595 persons, 7 years) | `lwage`, `exp`, `wks`, `ed`, `married`, `union` -- no index columns; declare with `pdata.frame(Wages, index = 595)` |
| `EmplUK` | UK employment (140 firms, 7-9 years) | `emp`, `wage`, `capital`, `output`, `firm`, `year` |

```r
data("Grunfeld", package = "plm")
data("Produc", package = "plm")
```

---

## The pdata.frame Requirement

plm requires panel structure to be declared via `pdata.frame()`. This converts
a regular data.frame into a panel-aware object by identifying the entity and
time columns.

### Creating a pdata.frame

```r
library(plm)

# From a data.frame with entity and time columns
data("Grunfeld", package = "plm")
pdf <- pdata.frame(Grunfeld, index = c("firm", "year"))

# Verify structure
pdim(pdf)
# Balanced Panel: n = 10, T = 20, N = 200
```

### From Parquet (DAAF Workflow)

```r
library(arrow)
library(plm)

df <- read_parquet("data/processed/panel_data.parquet")
pdf <- pdata.frame(df, index = c("entity_id", "year"))
```

### What the index= Argument Does

The `index` argument takes a character vector of length 1, 2, or 3:
- `index = c("entity", "time")` -- standard two-way panel
- `index = c("entity", "time", "group")` -- nested panel (group > entity)
- `index = "entity"` -- entity only; time index is inferred from row order

```r
# Two-way (most common)
pdf <- pdata.frame(df, index = c("firm", "year"))

# If time is implicit in row ordering
pdf <- pdata.frame(df, index = "firm")
```

### What Happens Without pdata.frame

If you pass a plain data.frame to `plm()`, plm will try to auto-detect the
index. This can silently produce wrong results if it guesses wrong. Always
declare the panel structure explicitly.

```r
# Risky: plm guesses which columns are entity/time
fit <- plm(y ~ x, data = df, model = "within")

# Safe: explicit panel declaration
pdf <- pdata.frame(df, index = c("entity_id", "year"))
fit <- plm(y ~ x, data = pdf, model = "within")
```

### Comparison with linearmodels (Python)

| Concept | plm (R) | linearmodels (Python) |
|---------|---------|----------------------|
| Panel declaration | `pdata.frame(df, index = c("entity", "time"))` | `df.set_index(["entity", "time"])` (pandas MultiIndex) |
| Panel verification | `pdim(pdf)` | `print(df.index.names)` |
| Balance check | `is.pbalanced(pdf)` | Manual via `.groupby(level=0).size()` |
| Entity/time access | `pdf$firm` returns pseries | `df.index.get_level_values(0)` |

---

## Your First Panel Model

### Fixed Effects (Within Estimator)

```r
library(plm)
data("Grunfeld", package = "plm")
pdf <- pdata.frame(Grunfeld, index = c("firm", "year"))

# Entity fixed effects
fit_fe <- plm(inv ~ value + capital, data = pdf, model = "within")
summary(fit_fe)
```

### Random Effects

```r
# Random effects (GLS quasi-demeaning)
fit_re <- plm(inv ~ value + capital, data = pdf, model = "random")
summary(fit_re)
```

### Hausman Test (FE vs RE)

```r
# Test whether RE assumptions hold
phtest(fit_fe, fit_re)
# Low p-value: reject RE, use FE
# High p-value: RE is consistent, prefer RE for efficiency
```

---

## The model= Argument

The `model=` argument is the primary way to select the estimator:

| model= | Estimator | What It Does |
|--------|-----------|-------------|
| `"within"` | Fixed effects | Entity demeaning (within transformation) |
| `"random"` | Random effects | GLS quasi-demeaning |
| `"between"` | Between | Regresses entity means on averaged regressors |
| `"fd"` | First difference | Eliminates entity effects by differencing |
| `"pooling"` | Pooled OLS | Ignores panel structure (baseline) |

```r
# Switch estimator by changing model= only
fit_fe <- plm(y ~ x1 + x2, data = pdf, model = "within")
fit_re <- plm(y ~ x1 + x2, data = pdf, model = "random")
fit_be <- plm(y ~ x1 + x2, data = pdf, model = "between")
fit_fd <- plm(y ~ x1 + x2, data = pdf, model = "fd")
fit_pool <- plm(y ~ x1 + x2, data = pdf, model = "pooling")
```

### The effect= Argument

Controls which dimension(s) of effects are modeled:

| effect= | Meaning | Used With |
|---------|---------|-----------|
| `"individual"` (default) | Entity effects only | within, random, between |
| `"time"` | Time effects only | within, random |
| `"twoways"` | Entity + time effects | within, random |

```r
# Two-way fixed effects
fit_twfe <- plm(y ~ x1 + x2, data = pdf, model = "within", effect = "twoways")

# Time random effects
fit_re_time <- plm(y ~ x1 + x2, data = pdf, model = "random", effect = "time")
```

---

## Reading the Summary Output

### Fixed Effects Summary

```r
fit <- plm(inv ~ value + capital, data = pdf, model = "within")
summary(fit)
```

Key output sections:

| Section | What It Shows |
|---------|---------------|
| **Oneway (individual) effect Within Model** | Model type and effect specification |
| **Balanced Panel** | n (entities), T (periods), N (total obs) |
| **Residuals** | Min, 1Q, Median, 3Q, Max of residuals |
| **Coefficients** | Estimate, Std. Error, t-value, Pr(>t) |
| **Total Sum of Squares** | Total variation |
| **Residual Sum of Squares** | Unexplained variation |
| **R-Squared** | Within R-squared (adj and unadj) |
| **F-statistic** | Joint significance of regressors |

### Random Effects Summary

Random effects summary additionally shows:

| Section | What It Shows |
|---------|---------------|
| **Effects** | Variance decomposition: `var.comp` for individual and idiosyncratic |
| **theta** | Quasi-demeaning parameter (0 = pooled, 1 = within) |

```r
fit_re <- plm(inv ~ value + capital, data = pdf, model = "random")
summary(fit_re)

# The theta value indicates how much quasi-demeaning is applied
# theta closer to 1 means RE approaches FE
```

---

## Post-Estimation Essentials

```r
fit <- plm(inv ~ value + capital, data = pdf, model = "within")

# Coefficients
coef(fit)

# Variance-covariance matrix
vcov(fit)

# Fixed effects estimates (entity intercepts)
fixef(fit)

# Overall intercept for within model
within_intercept(fit)

# Fitted values and residuals
fitted(fit)
residuals(fit)

# Tidy output via broom
broom::tidy(fit, conf.int = TRUE)
broom::glance(fit)

# Model comparison table via modelsummary
library(modelsummary)
modelsummary(list("FE" = fit_fe, "RE" = fit_re))
```

### Robust Inference

plm's default summary uses classical (homoskedastic) SEs. For robust or
clustered inference, use `coeftest()` from lmtest with plm's vcov functions:

```r
library(lmtest)

# Heteroskedasticity-robust (White)
coeftest(fit, vcov = vcovHC(fit, type = "HC1"))

# Entity-clustered SEs
coeftest(fit, vcov = vcovHC(fit, cluster = "group"))

# Newey-West (HAC for panel)
coeftest(fit, vcov = vcovNW(fit))

# Driscoll-Kraay (cross-sectional dependence robust)
coeftest(fit, vcov = vcovSCC(fit))
```

See `./robust.md` for the full SE reference.

---

## Panel Dimensions and Balance

### pdim() -- Panel Dimensions

```r
pdf <- pdata.frame(Grunfeld, index = c("firm", "year"))
pdim(pdf)
# Balanced Panel: n = 10, T = 20, N = 200

# Access components
pd <- pdim(pdf)
pd$nT$n        # Number of entities
pd$nT$T        # Number of time periods
pd$nT$N        # Total observations
pd$balanced     # TRUE/FALSE
```

### is.pbalanced() -- Balance Check

```r
is.pbalanced(pdf)   # TRUE if balanced
```

### punbalancedness() -- Imbalance Measure

```r
# Quantify the degree of imbalance
punbalancedness(pdf)
```

### make.pbalanced() -- Balance the Panel

```r
# Fill missing entity-time combinations with NA
pdf_bal <- make.pbalanced(pdf, balance.type = "fill")
```

---

## Quick Syntax Comparison: plm vs linearmodels vs fixest

| Task | plm (R) | linearmodels (Python) | fixest (R) |
|------|---------|----------------------|------------|
| Panel setup | `pdata.frame(df, index=c("e","t"))` | `df.set_index(["e","t"])` | Not required |
| Entity FE | `plm(y~x, data, model="within")` | `PanelOLS.from_formula("y~x+EntityEffects", data)` | `feols(y~x\|e, data)` |
| Two-way FE | `plm(y~x, data, model="within", effect="twoways")` | `PanelOLS.from_formula("y~x+EntityEffects+TimeEffects", data)` | `feols(y~x\|e+t, data)` |
| Random effects | `plm(y~x, data, model="random")` | `RandomEffects.from_formula("y~1+x", data)` | N/A |
| Between | `plm(y~x, data, model="between")` | `BetweenOLS.from_formula("y~1+x", data)` | N/A |
| First difference | `plm(y~x, data, model="fd")` | `FirstDifferenceOLS.from_formula("y~x", data)` | N/A |
| Hausman test | `phtest(fe, re)` | Manual comparison | N/A |
| Clustered SEs | `coeftest(fit, vcovHC(fit, cluster="group"))` | `.fit(cov_type="clustered", cluster_entity=True)` | `vcov=~e` |
| Driscoll-Kraay | `coeftest(fit, vcovSCC(fit))` | `.fit(cov_type="kernel", kernel="bartlett")` | `vcov="DK"` |
| Panel IV | `plm(y~x\|z, model="within")` | Not available (use pyfixest) | `feols(y~1\|e\|x~z)` |
| Dynamic GMM | `pgmm()` | Not available | Not available |
| Model comparison | `modelsummary(list(fe, re))` | `compare({"FE": fe, "RE": re})` | `etable(fe1, fe2)` |

### When to Use Which in R

**Use plm when:**
- You need random effects, between estimation, or first difference
- Running the Hausman test (FE vs RE)
- Fama-MacBeth cross-sectional regressions (via `pmg(model = "mg")` with a
  reversed, time-first index -- see `./models.md`)
- Panel diagnostic tests (serial correlation, cross-sectional dependence, unit root)
- Dynamic GMM (Arellano-Bond, Blundell-Bond)
- Panel IV within entity-demeaned data

**Use fixest when:**
- High-dimensional fixed effects (3+ way FE)
- IV combined with fixed effects (three-part formula)
- Difference-in-differences or event study designs (sunab)
- Poisson/GLM with fixed effects (fepois, feglm)
- Publication-quality tables (etable) and coefficient plots
- Speed matters (C++ backend is much faster for large FE)

**Use r-stats when:**
- Cross-sectional regression without panel structure
- GLMs (logit, probit, Poisson) without fixed effects
- Classical hypothesis tests (t-test, chi-squared)
- Time series models (ARIMA, VAR)

---

## References

- Croissant, Y. & Millo, G. (2008). "Panel Data Econometrics in R: The plm
  Package." Journal of Statistical Software, 27(2), 1-43.
- Croissant, Y. & Millo, G. (2019). "Panel Data Econometrics with R." Wiley.
- plm CRAN: https://CRAN.R-project.org/package=plm
- plm vignettes: https://cran.r-project.org/web/packages/plm/vignettes/
