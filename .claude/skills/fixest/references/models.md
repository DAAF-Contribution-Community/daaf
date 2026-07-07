# Model Families

## Contents

- [fepois: Poisson Regression](#fepois-poisson-regression)
- [feglm: Generalized Linear Models with FE](#feglm-generalized-linear-models-with-fe)
- [fenegbin: Negative Binomial](#fenegbin-negative-binomial)
- [feNmlm: Nonlinear Models](#fenlml-nonlinear-models)
- [Model Selection Guide](#model-selection-guide)

## fepois: Poisson Regression

Poisson regression with absorbed high-dimensional fixed effects. Uses iteratively
reweighted least squares (IRLS/IWLS) for estimation.

### Basic Usage

```r
library(fixest)

# Poisson with FE
fit <- fepois(count_y ~ x1 + x2 | entity + year, data = df)
summary(fit)

# Poisson without FE
fit <- fepois(count_y ~ x1 + x2, data = df)
```

### When to Use fepois

- **Count data**: Outcomes that are non-negative integers (counts)
- **Log-linear models**: Poisson pseudo-maximum likelihood (PPML) is the
  standard estimator for gravity-type models (trade, migration) even when the
  dependent variable is continuous
- **Multiplicative models**: When the conditional expectation is multiplicative
  rather than additive

### Gravity Model Example

```r
data(trade, package = "fixest")

# Santos Silva & Tenreyro (2006) PPML gravity estimator
fit_ppml <- fepois(Euros ~ log(dist_km) | Origin + Destination + Year,
                   data = trade, vcov = ~Origin + Destination)
summary(fit_ppml)

# Compare with log-linear OLS
fit_ols <- feols(log(Euros) ~ log(dist_km) | Origin + Destination + Year,
                 data = trade, vcov = ~Origin + Destination)

etable(fit_ols, fit_ppml, headers = c("Log-OLS", "PPML"))
```

### Convergence Parameters

```r
fit <- fepois(count_y ~ x1 | entity + year, data = df,
              glm.iter = 25,         # Max IRLS iterations (default 25)
              glm.tol = 1e-08)       # Convergence tolerance
```

If convergence fails, see `gotchas.md` for troubleshooting separation and
convergence issues.

### Interpreting Poisson Coefficients

Poisson coefficients are semi-elasticities (in the log-linear model):
- A coefficient of 0.05 on x1 means a one-unit increase in x1 is associated
  with approximately a 5% increase in E[Y|X]
- For exact interpretation: `exp(beta) - 1` gives the proportional change

## feglm: Generalized Linear Models with FE

`feglm()` supports GLM families with absorbed high-dimensional fixed effects.
This is a major advantage over pyfixest, where `feglm()` does NOT support FE.

### Supported Families

| Family | Link | Use Case |
|--------|------|----------|
| `binomial` (logit) | logit | Binary outcomes |
| `binomial(link = "probit")` | probit | Binary outcomes (normal CDF) |
| `Gamma` | inverse | Positive continuous, heteroskedastic |
| `gaussian` | identity | Linear model (same as feols) |

### Logit with Fixed Effects

```r
# Logit with entity FE
fit <- feglm(binary_y ~ x1 + x2 | entity, data = df, family = binomial)
summary(fit)

# Logit with two-way FE
fit <- feglm(binary_y ~ x1 + x2 | entity + year, data = df, family = binomial)
```

This is one of the strongest features of R fixest over pyfixest. In Python,
logit/probit with high-dimensional FE requires manual dummies (which is infeasible
with many FE levels) or using a linear probability model instead.

### Probit with Fixed Effects

```r
fit <- feglm(binary_y ~ x1 + x2 | entity, data = df,
             family = binomial(link = "probit"))
summary(fit)
```

### Key Differences from feols

| Aspect | feols (OLS) | feglm (GLM) |
|--------|-------------|-------------|
| Estimation | Closed-form (demeaning + OLS) | Iterative (IRLS) |
| Speed | Very fast | Slower (iterative) |
| Coefficients | Linear effects | Log-odds (logit), z-scores (probit) |
| Marginal effects | Coefficients ARE marginal effects | Need `marginaleffects` package |
| SE switching | Free (post-estimation) | Free (post-estimation) |

### Marginal Effects for feglm

feglm coefficients are not directly interpretable as marginal effects. Use the
`marginaleffects` R package:

```r
library(marginaleffects)

fit <- feglm(binary_y ~ x1 + x2 | entity, data = df, family = binomial)

# Average marginal effects
avg_slopes(fit, variables = "x1")

# Marginal effects at representative values
slopes(fit, variables = "x1",
       newdata = datagrid(x2 = c(0, 1)))
```

### Incidental Parameters Problem

With short panels (few time periods per entity), logit/probit with entity FE
suffer from the incidental parameters problem: FE estimates are inconsistent
with fixed T, biasing coefficient estimates. This bias is O(1/T):

| T | Approximate Bias |
|---|-----------------|
| 2 | ~100% |
| 5 | ~20% |
| 10 | ~10% |
| 20 | ~5% |
| 50+ | Negligible |

**Mitigations:**
- Conditional logit (not available in fixest; use `survival::clogit()`)
- Linear probability model (`feols()` with robust/clustered SEs)
- Bias correction (Fernandez-Val & Weidner, 2016)
- Use feglm when T is reasonably large (say, T > 10-20)

## fenegbin: Negative Binomial

Negative binomial regression with FE, for overdispersed count data.

### Basic Usage

```r
# Negative binomial with FE
fit <- fenegbin(count_y ~ x1 + x2 | entity + year, data = df)
summary(fit)
```

### When to Use fenegbin vs fepois

| Criterion | fepois (Poisson) | fenegbin (Neg. Binomial) |
|-----------|-----------------|------------------------|
| Variance = Mean | Yes (equidispersion) | No (overdispersion) |
| Overdispersed counts | Robust but may be inefficient | More efficient |
| Zero-inflated data | Not ideal | Better fit |
| Robust to misspecification | Yes (PPML is consistent) | Less robust |

In practice, Poisson pseudo-ML (fepois) is often preferred because:
- It is consistent for the conditional mean even if the variance is misspecified
- With clustered SEs, inference is valid regardless of overdispersion
- Santos Silva & Tenreyro (2006) show PPML outperforms alternatives for
  gravity-type models

Use fenegbin when modeling the dispersion parameter itself is of interest, or
when the Poisson model shows severe convergence issues due to overdispersion.

## feNmlm: Nonlinear Models

`feNmlm()` is the most general estimation function in fixest, supporting custom
nonlinear specifications with FE.

### Basic Syntax

```r
# Custom nonlinear model
fit <- feNmlm(y ~ x1 + x2, data = df,
              NL.fml = ~ a * exp(b * x3),  # Nonlinear component
              NL.start = list(a = 1, b = 0.5))
```

### Available Families

| Family | Description | Example |
|--------|-------------|---------|
| `"poisson"` | Same as fepois | Count data |
| `"negbin"` | Same as fenegbin | Overdispersed counts |
| `"logit"` | Same as feglm(binomial) | Binary outcomes |
| `"gaussian"` | Same as feols | Linear model |
| Custom | User-specified likelihood | Research-specific models |

### When to Use feNmlm

- Nonlinear specifications that don't fit into feols/fepois/feglm/fenegbin
- Custom likelihood functions
- Models combining linear and nonlinear components

For standard models, prefer the specialized functions (feols, fepois, feglm,
fenegbin) — they are faster and have better diagnostics.

## Model Selection Guide

```
What outcome type?
│
├─ Continuous → feols (OLS)
│   ├─ With fixed effects → feols(y ~ x | fe)
│   └─ Without FE → feols(y ~ x) or lm(y ~ x)
│
├─ Count / Non-negative → Consider Poisson first
│   ├─ fepois(count ~ x | fe)
│   ├─ Overdispersed? → fenegbin(count ~ x | fe)
│   └─ Gravity model → fepois (PPML, Santos Silva & Tenreyro 2006)
│
├─ Binary (0/1) → Consider options:
│   ├─ LPM: feols(binary ~ x | fe, vcov = "hetero")
│   │   Pro: Fast, easy interpretation, handles many FE
│   │   Con: Can predict outside [0,1], heteroskedastic by construction
│   ├─ Logit: feglm(binary ~ x | fe, family = binomial)
│   │   Pro: Proper binary model, bounded predictions
│   │   Con: Incidental parameters problem with short panels
│   └─ Probit: feglm(binary ~ x | fe, family = binomial("probit"))
│       Pro: Normal CDF link
│       Con: Same incidental parameters concern as logit
│
├─ Ordinal / Multinomial → Not in fixest
│   └─ Use nnet::multinom() or MASS::polr() (no FE absorption)
│
└─ Custom nonlinear → feNmlm()
```

### Quick Function Reference

| Function | Model | FE Support | IV Support |
|----------|-------|-----------|-----------|
| `feols()` | OLS / linear | Yes | Yes |
| `fepois()` | Poisson | Yes | No |
| `feglm()` | GLM (logit, probit, Gamma, ...) | Yes | No |
| `fenegbin()` | Negative binomial | Yes | No |
| `feNmlm()` | General nonlinear | Yes | No |

## References

- Santos Silva, J.M.C. and Tenreyro, S. (2006). "The Log of Gravity."
  *Review of Economics and Statistics*, 88(4), 641-658.
- Fernandez-Val, I. and Weidner, M. (2016). "Individual and time effects in
  nonlinear panel models with large N, T." *Journal of Econometrics*, 192(1),
  291-312.
- fixest documentation — GLM and nonlinear models:
  https://lrberge.github.io/fixest/reference/feglm.html
