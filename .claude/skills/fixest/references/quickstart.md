# fixest Quickstart

## Contents

- [Setup](#setup)
- [Your First Regression](#your-first-regression)
- [Formula Syntax Overview](#formula-syntax-overview)
- [Multi-Estimation: sw, csw, csw0, sw0](#multi-estimation-sw-csw-csw0-sw0)
- [Multiple Outcomes](#multiple-outcomes)
- [Data Requirements](#data-requirements)
- [Quick Comparison: R fixest vs pyfixest](#quick-comparison-r-fixest-vs-pyfixest)

## Setup

### Loading fixest

```r
library(fixest)
```

fixest is already installed in the DAAF container (v0.14.0, R 4.5.3). No
additional installation is needed.

### Built-in Datasets

fixest ships with useful built-in datasets for examples:

| Dataset | Description | Key Columns |
|---------|-------------|-------------|
| `trade` | Bilateral trade (gravity model) | `Euros`, `dist_km`, `Origin`, `Destination`, `Year` |
| `base_did` | Staggered DiD example (simulated) | `y`, `x1`, `id`, `period`, `post`, `treat` |
| `base_stagg` | Staggered treatment timing | `y`, `x1`, `id`, `year`, `year_treated`, `time_to_treatment` |

```r
data(trade, package = "fixest")
data(base_did, package = "fixest")
data(base_stagg, package = "fixest")
```

## Your First Regression

### Basic OLS (No Fixed Effects)

```r
library(fixest)
data(trade, package = "fixest")

# Simple OLS
fit <- feols(log(Euros) ~ log(dist_km), data = trade)
summary(fit)
```

### OLS with Fixed Effects

```r
# One-way FE: absorb origin country intercepts
fit <- feols(log(Euros) ~ log(dist_km) | Origin, data = trade)
summary(fit)

# Two-way FE: origin + destination fixed effects
fit <- feols(log(Euros) ~ log(dist_km) | Origin + Destination, data = trade)
summary(fit)
```

### Reading the Summary Output

The `summary()` output displays:
- **Estimation method**: OLS, Poisson, etc.
- **Dep. Var.**: The outcome variable
- **Observations**: Sample size (after dropping singletons if applicable)
- **Fixed-effects**: Names and number of FE levels absorbed
- **Standard-errors**: SE type used (IID, Hetero, Clustered, etc.)
- **Coefficient table**: Estimate, Std. Error, t value, Pr(>|t|)
- **R2 / Within R2 / Adj. R2**: Model fit statistics
- **RMSE**: Root mean squared error

### Switching Standard Errors After Estimation

A key workflow pattern: estimate once, try different SE assumptions without
re-estimating.

```r
fit <- feols(log(Euros) ~ log(dist_km) | Origin + Destination, data = trade)

# IID (default in v0.14)
summary(fit)

# Heteroskedasticity-robust
summary(fit, vcov = "hetero")

# Clustered by Origin
summary(fit, vcov = ~Origin)

# Two-way clustered
summary(fit, vcov = ~Origin + Destination)
```

This works because SE computation is independent of point estimation under
OLS --- changing the variance estimator only affects standard errors, not
coefficients.

The `cluster` argument is available as an alias for `vcov` in most fixest
functions. Both `vcov = ~state` and `cluster = ~state` produce the same result.

## Formula Syntax Overview

fixest uses a three-part formula separated by `|`:

```
depvar ~ exogenous_vars | fixed_effects | endogenous ~ instruments
```

### Part 1: Dependent Variable and Exogenous Regressors

```r
# Basic regressors
y ~ x1 + x2

# Interaction with main effects
y ~ x1 * x2            # equivalent to x1 + x2 + x1:x2

# Interaction only (no main effects)
y ~ x1:x2

# Categorical variable with reference level
y ~ i(state, ref = "CA")

# Transformations (R-standard)
y ~ log(x1) + I(x2^2)
```

### Part 2: Fixed Effects (After First `|`)

```r
# One-way FE
y ~ x1 | entity

# Two-way FE
y ~ x1 | entity + year

# Three-way FE
y ~ x1 | entity + year + industry

# Interacted FE (entity-by-year)
y ~ x1 | entity^year
```

### Part 3: Instrumental Variables (After Second `|`)

```r
# IV: endogenous ~ instrument
y ~ x_exog | fe | x_endog ~ z_instrument

# IV with no FE (use 0 for empty FE)
y ~ x_exog | 0 | x_endog ~ z1 + z2

# Multiple instruments
y ~ 1 | fe | x_endog ~ z1 + z2
```

### The `i()` Operator for Interactions and Categoricals

```r
# Categorical with reference level
y ~ i(year, ref = 2000) | entity

# Numeric interaction with categorical
y ~ i(group, x1, ref = "control")

# i() is essential for event study specifications
# See did.md for full event study syntax with i()
```

### Operator Quick Reference

| Operator | In Formula | Meaning |
|----------|-----------|---------|
| `+` | After `~` | Add regressor |
| `*` | After `~` | Full interaction (main + cross) |
| `:` | After `~` | Interaction only |
| `\|` | Formula separator | Separate parts (regressors \| FE \| IV) |
| `+` | After `\|` | Add FE dimension |
| `^` | After `\|` | Interact FE dimensions |
| `[var]` | After FE name | Varying slopes |
| `i()` | In regressors | Categorical/interaction with ref level |
| `sunab()` | In regressors | Sun-Abraham DiD specification |
| `sw()` | In regressors | Stepwise model variations |
| `csw()` | In regressors | Cumulative stepwise |
| `csw0()` | In regressors | Cumulative stepwise from intercept-only |
| `sw0()` | In regressors | Stepwise from intercept-only |
| `c()` | On LHS | Multiple dependent variables |

## Multi-Estimation: sw, csw, csw0, sw0

fixest can estimate multiple models in a single call using stepwise operators.
This is more efficient than separate calls because the data is processed once.

### `csw()` — Cumulative Stepwise

Each model includes all previous variables plus the next one:

```r
# Model 1: y ~ x1 | fe
# Model 2: y ~ x1 + x2 | fe
# Model 3: y ~ x1 + x2 + x3 | fe
fits <- feols(y ~ csw(x1, x2, x3) | id, data = base_did)
etable(fits)
```

### `csw0()` — Cumulative Stepwise from Intercept-Only

Starts with an intercept-only model (no regressors):

```r
# Model 1: y ~ 1 | fe     (intercept only)
# Model 2: y ~ x1 | fe
# Model 3: y ~ x1 + x2 | fe
fits <- feols(y ~ csw0(x1, x2) | id, data = base_did)
etable(fits)
```

### `sw()` — Stepwise Alternatives

Each model includes exactly one variable (alternatives, not cumulative):

```r
# Model 1: y ~ x1 | fe
# Model 2: y ~ x2 | fe
fits <- feols(y ~ sw(x1, x2) | id, data = base_did)
etable(fits)
```

### `sw0()` — Stepwise from Intercept-Only

```r
# Model 1: y ~ 1 | fe     (intercept only)
# Model 2: y ~ x1 | fe
# Model 3: y ~ x2 | fe
fits <- feols(y ~ sw0(x1, x2) | id, data = base_did)
```

### Multi-Estimation Returns `fixest_multi`

When using `sw`/`csw` operators, the result is a `fixest_multi` object (a list
of `fixest` models). Pass it directly to `etable()`:

```r
fits <- feols(y ~ csw(x1, x2) | id, data = base_did)
etable(fits)           # Correct: pass fixest_multi directly
# etable(list(fits))   # Wrong: don't wrap in list()
```

To access individual models:

```r
fits[[1]]              # First model
summary(fits[[2]])     # Summary of second model
```

## Multiple Outcomes

Use `c()` on the left-hand side to estimate the same specification for multiple
dependent variables:

```r
# Same specification, different outcomes
fits <- feols(c(y, x1) ~ treat | id + period, data = base_did)
etable(fits)
```

This estimates both `y ~ treat | id + period` and `x1 ~ treat | id + period`
in a single call. Combined with `sw()`/`csw()`, this can produce large model
grids efficiently.

## Data Requirements

### Input Data

fixest accepts a standard R `data.frame` or `tibble`. Column names used in
formulas should be syntactically valid R names (no spaces, no special characters
other than `.` and `_`).

### DAAF Parquet Workflow

DAAF pipelines store data in parquet format. To use with fixest:

```r
library(arrow)
library(fixest)

# Load parquet data
df <- read_parquet("data/processed/analysis_data.parquet")

# fixest works directly with data.frames from arrow
fit <- feols(y ~ x1 + x2 | entity + year, data = df)
```

The `arrow` package's `read_parquet()` returns a standard R data.frame that
fixest accepts directly. No conversion step is needed (unlike pyfixest, which
requires Polars-to-pandas conversion).

### Panel Data

fixest does not require explicit panel declaration (unlike `plm::pdata.frame()`).
Instead, panel structure is specified through the formula:

```r
# Entity and time identifiers go in the FE slot
fit <- feols(y ~ x1 | entity + year, data = df)
```

For panel-specific features like Newey-West or Driscoll-Kraay SEs, use the
`panel.id` argument or `panel()` function:

```r
# Set panel identifiers for HAC SEs
fit <- feols(y ~ x1 | entity + year, data = df,
             panel.id = ~entity + year, vcov = "NW")
```

## Quick Comparison: R fixest vs pyfixest

| Task | R fixest | pyfixest |
|------|----------|----------|
| OLS | `feols(y ~ x, data)` | `pf.feols("y ~ x", data)` |
| OLS + FE | `feols(y ~ x \| fe, data)` | `pf.feols("y ~ x \| fe", data)` |
| Clustered SE | `vcov = ~g` | `vcov={"CRV1": "g"}` |
| Two-way cluster | `vcov = ~g1 + g2` | `vcov={"CRV1": "g1+g2"}` |
| Poisson + FE | `fepois(y ~ x \| fe, data)` | `pf.fepois("y ~ x \| fe", data)` |
| GLM + FE | `feglm(y ~ x \| fe, data, family)` | **Not supported** |
| IV + FE | `feols(y ~ 1 \| fe \| x ~ z, data)` | `pf.feols("y ~ 1 \| fe \| x ~ z", data)` |
| Sun-Abraham | `feols(y ~ sunab(g,t) \| ...)` | `pf.event_study(estimator="saturated")` |
| Regression table | `etable(fit1, fit2)` | `pf.etable([fit1, fit2])` |
| Multiple LHS | `c(y1, y2) ~ x` | `"y1 + y2 ~ x"` |
| Stepwise | `csw(x1, x2)` | `"csw(x1, x2)"` |
| Switch SE post-est | `summary(fit, vcov = ...)` | `fit.vcov(...)` |

The most notable syntax differences:
1. **Clustering**: R uses one-sided formula (`~state`); Python uses dict (`{"CRV1": "state"}`)
2. **Multiple outcomes**: R uses `c()`; Python uses `+`
3. **Formulas are unquoted in R**, quoted strings in Python
4. **feglm with FE**: Works in R, not in pyfixest (major gap)
5. **Sun-Abraham**: R uses `sunab()` in formula; Python uses separate `event_study()` function

## Next Steps

- Learn about fixed effects specification → `fixed-effects.md`
- Choose standard errors → `standard-errors.md`
- Set up instrumental variables → `iv.md`
- Run difference-in-differences designs → `did.md`
- Create publication tables and plots → `reporting.md`
- Explore non-OLS models (Poisson, GLM, negbin) → `models.md`

## References

- Berge, L., Butts, K., and McDermott, G. (2026). "Fast and User-Friendly
  Econometrics Estimations: The R Package fixest." arXiv:2601.21749.
  https://arxiv.org/abs/2601.21749
- fixest documentation: https://lrberge.github.io/fixest/
- fixest CRAN: https://CRAN.R-project.org/package=fixest
- pyfixest documentation: https://pyfixest.org
