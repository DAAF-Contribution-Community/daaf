# Common Gotchas and Troubleshooting

## Contents

- [Default SE Changed (v0.13+)](#default-se-changed-v013)
- [Singleton Fixed Effects](#singleton-fixed-effects)
- [Collinearity with Fixed Effects](#collinearity-with-fixed-effects)
- [Poisson Convergence and Separation](#poisson-convergence-and-separation)
- [Formula Parsing Pitfalls](#formula-parsing-pitfalls)
- [Panel ID Requirements](#panel-id-requirements)
- [etable Formatting Issues](#etable-formatting-issues)
- [pyfixest vs fixest Differences](#pyfixest-vs-fixest-differences)
- [Matching Stata Results](#matching-stata-results)
- [Quick Diagnostic Table](#quick-diagnostic-table)

## Default SE Changed (v0.13+)

### The Breaking Change

**Before v0.13:** Default SE was cluster-robust by the first fixed effect variable.
**v0.13+ (including v0.14.0):** Default SE is `"iid"`.

```r
# Old behavior: SEs were auto-clustered by first FE
# New behavior (v0.14): SEs are IID
fit <- feols(y ~ x1 | entity, data = df)
summary(fit)  # Shows "Standard-errors: IID"

# If you want clustering (the old default):
summary(fit, vcov = ~entity)
```

**Impact:** Code from pre-v0.13 that relied on the old default will produce
different standard errors, t-statistics, p-values, and significance stars without
any error or warning.

**Best practice:** Always specify `vcov` explicitly in research scripts:

```r
# Explicit is always better
fit <- feols(y ~ x1 | entity + year, data = df, vcov = ~entity)
```

### Setting a Global Default

```r
# Restore old behavior for the session.
# setFixest_vcov() takes named arguments keyed by FE structure
# (no_FE, one_FE, two_FE, panel, all, reset) — there is no `vcov = ` argument.
# The `all` key only accepts "iid" or "hetero"; clustering must be set via
# the per-structure keys:
setFixest_vcov(one_FE = "cluster", two_FE = "cluster", panel = "cluster")
# Or
setFixest_vcov(all = "hetero")    # Always use robust
```

## Singleton Fixed Effects

### What Happens

Since v0.13, fixest drops singleton FE groups (observations where a FE level
appears only once) by default. The `fixef.rm` default is `"perfect_fit"`, which
removes both singletons and observations perfectly fit by the FE:

```r
# You will see:
# "NOTE: XX singleton observations removed"
fit <- feols(y ~ x1 | entity + year, data = df)
```

### When Many Singletons Are Removed

If a large fraction of observations are singletons, investigate:
- Is the panel very unbalanced (many entities appear only once)?
- Is the FE specification too fine-grained (e.g., interacted FE with rare
  combinations)?
- Did data cleaning inadvertently create many single-observation groups?

```r
# Check how many observations per FE group
table(table(df$entity))    # Distribution of observations per entity
table(table(df$year))      # Distribution of observations per year
```

### Keeping Singletons

```r
# Not recommended, but possible
fit <- feols(y ~ x1 | entity, data = df, fixef.rm = "none")
```

## Collinearity with Fixed Effects

### The Problem

If a regressor has no within-group variation after FE demeaning, it is perfectly
collinear with the FE and fixest drops it:

```r
# x_static is constant within entity -> collinear with entity FE
fit <- feols(y ~ x_static + x_varying | entity, data = df)
# Warning: variable 'x_static' is collinear with the fixed effects
# x_static is dropped from the model
```

### Common Causes

| Cause | Example | Fix |
|-------|---------|-----|
| Time-invariant variable + entity FE | Gender, race with person FE | Remove FE or variable |
| Entity-invariant variable + time FE | National policy with year FE | Remove FE or variable |
| Interaction creates collinearity | `i(state, x) + state FE` when x is binary | Reconsider specification |

### Diagnosing

```r
fit <- feols(y ~ x1 + x2 + x3 | entity, data = df)
# Check which variables were dropped
cat("Dropped variables:", setdiff(c("x1", "x2", "x3"), names(coef(fit))), "\n")
```

## Poisson Convergence and Separation

### Convergence Failures

```r
# Warning: Maximum number of iterations reached
fit <- fepois(count_y ~ x1 | entity + year, data = df)
```

**Fixes:**

```r
# Increase iterations
fit <- fepois(count_y ~ x1 | entity + year, data = df,
              glm.iter = 100)    # Default is 25

# Relax convergence tolerance
fit <- fepois(count_y ~ x1 | entity + year, data = df,
              glm.tol = 1e-06)   # Default is 1e-08
```

### Separation

Separation occurs when a FE level perfectly predicts zero (or infinity). All
observations in that group have Y = 0, so the FE intercept goes to negative
infinity.

```r
# Check for zero-count FE groups
group_sums <- tapply(df$count_y, df$entity, sum)
cat("Zero-count entities:", sum(group_sums == 0), "\n")
```

fixest can detect and handle separation, but severe cases may require:
- Removing zero-count groups manually
- Simplifying the FE specification
- Using a different estimator

### Poisson with Many Zeros

If your data has many zeros:
- Zero-inflated Poisson/NB: Not in fixest; use `pscl::zeroinfl()` (no FE). `pscl`
  is not pre-installed in DAAF, and runtime installs are blocked (see CLAUDE.md
  § Runtime Package Installation) — escalate to the user to add `pscl` to the
  Dockerfile (user additions block) and rebuild before use.
- Hurdle model: Not in fixest; use `pscl::hurdle()` (no FE). Same `pscl`
  availability note as above.
- PPML with FE: `fepois()` handles excess zeros reasonably well for
  gravity-type models

## Formula Parsing Pitfalls

### Variable Names

```r
# Column names with spaces or special characters cause errors
# Fix: rename columns before estimation
names(df) <- gsub(" ", "_", names(df))
names(df) <- gsub("[^a-zA-Z0-9_.]", "", names(df))
```

### Transformations in Formulas

```r
# These work in fixest formulas:
y ~ log(x1)             # Log transform
y ~ I(x1^2)             # Polynomial (I() protects ^)
y ~ x1 * x2             # Full interaction
y ~ poly(x1, 2, raw = TRUE)  # Polynomial terms

# Common mistake: ^ without I() is interpreted as interaction
y ~ x1^2               # This means x1:x1, NOT x1-squared
y ~ I(x1^2)            # This is x1-squared
```

### Factor Variables

```r
# fixest handles factors automatically
fit <- feols(y ~ factor(group) + x1, data = df)

# For explicit reference level, use i()
fit <- feols(y ~ i(group, ref = "control") + x1, data = df)

# DO NOT use i() for the FE part (after |)
# i() is for the regressor part only
fit <- feols(y ~ i(group, ref = "A") | entity, data = df)  # Correct
# feols(y ~ x1 | i(entity, ref = 1), data = df)           # Wrong
```

### The `|` Separator

```r
# | separates regressors from FE
y ~ x1 + x2 | fe1 + fe2

# Second | separates FE from IV specification
y ~ x1 | fe1 | x_endo ~ z_inst

# 0 means "no FE" (needed for IV without FE)
y ~ x1 | 0 | x_endo ~ z_inst

# DO NOT use | inside interaction terms
# y ~ x1 | x2  means  y ~ x1 | FE=x2  (not y ~ x1 or x2)
```

## Panel ID Requirements

Some fixest features (Newey-West, Driscoll-Kraay) require explicit panel
structure:

```r
# Method 1: panel.id argument
fit <- feols(y ~ x1 | entity, data = df,
             panel.id = ~entity + year, vcov = "NW")

# Method 2: panel() function
pdat <- panel(df, ~entity + year)
fit <- feols(y ~ x1 | entity, data = pdat, vcov = "NW")

# Method 3: setFixest_estimation() global setting
setFixest_estimation(panel.id = ~entity + year)
fit <- feols(y ~ x1 | entity, data = df, vcov = "NW")
```

Without panel.id, you will get an error like:
```
Error: To compute the Newey-West VCOV, we need a variable for the time.
```

## etable Formatting Issues

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Markdown output doesn't work | `markdown = TRUE` only in knitr | Use `tex = FALSE` for data.frame |
| FE labels missing | Variables not in `dict` | Add to `dict = c(fe_name = "Label")` |
| Too many decimal places | Default formatting | Set `digits = 3` |
| Wrong significance stars | Different convention | Set `signif.code` explicitly |

### etable with fixest_multi

```r
fits <- feols(y ~ csw(x1, x2) | entity, data = df)
etable(fits)            # Correct: pass directly
# etable(list(fits))    # Wrong: don't wrap in list
```

### Mixing Model Types in etable

```r
# feols, fepois, feglm can all be combined
fit_ols <- feols(y ~ x1 | entity, data = df)
fit_pois <- fepois(count_y ~ x1 | entity, data = df)
fit_logit <- feglm(binary_y ~ x1 | entity, data = df, family = binomial)

etable(fit_ols, fit_pois, fit_logit,
       headers = c("OLS", "Poisson", "Logit"))
```

## pyfixest vs fixest Differences

| Feature | R fixest 0.14 | pyfixest 0.60 |
|---------|--------------|---------------|
| feglm with FE | Fully supported | Supported (since 0.50) |
| sunab() | Formula function | `event_study(estimator="saturated")` |
| did2s | Not built-in (use `did2s` package) | `pf.did2s()` built-in |
| lpdid | Not built-in | `pf.lpdid()` built-in |
| panelview | Not built-in | `pf.panelview()` built-in |
| etable maturity | Very mature (LaTeX, styling) | Evolving (uses maketables) |
| Conley spatial | `conley()` | Not supported |
| Wild bootstrap | `fwildclusterboot` package | `wildboottest` package |
| Multiple LHS | `c(y1, y2) ~ x` | `"y1 + y2 ~ x"` |
| Cluster SE syntax | `vcov = ~group` | `vcov={"CRV1": "group"}` |
| CRV3 jackknife | Not built-in | `vcov={"CRV3": "group"}` |
| Default SE (v0.13+/v0.40+) | IID | IID |
| Formula quoting | Unquoted | String (quoted) |

### Features in pyfixest Not in R fixest

- `did2s()` built-in (R needs separate package)
- `lpdid()` local projections DiD
- `panelview()` treatment visualization
- CRV3 cluster jackknife SEs
- `event_study()` unified interface

### Features in R fixest Not in pyfixest

- `feglm()` with absorbed FE (logit, probit with high-dimensional FE)
- `conley()` spatial SEs
- More mature `etable()` with LaTeX customization
- `sunab()` as formula function (more natural syntax)
- `fenegbin()` negative binomial with FE
- `feNmlm()` general nonlinear models

## Matching Stata Results

### Clustered Standard Errors

```r
# Match Stata's vce(cluster state)
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state,
             ssc = ssc(K.adj = TRUE, K.fixef = "none", G.adj = TRUE))
```

### Two-Way Clustering

```r
# Match Stata's conventional two-way clustering
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state + year,
             ssc = ssc(G.df = "conv"))
```

### Fixed Effects OLS

With IID standard errors, fixest and Stata match to very high precision.
Differences are typically due to small-sample correction choices:

```r
# Check ssc settings with print(ssc()) / getFixest_ssc()
# Stata (vce(cluster)): FE not counted in K -- equivalent to K.fixef = "none"
# fixest default: K.fixef = "nonnested" -- NOT the same; set
# ssc(K.fixef = "none") explicitly when matching Stata clustered SEs
```

## Quick Diagnostic Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Different SEs from old code | v0.13+ default SE change | Specify `vcov` explicitly |
| "Singleton observations removed" | Default `fixef.rm = "perfect_fit"` | Expected; or set `fixef.rm = "none"` (valid tokens: `"perfect_fit"`, `"singletons"`, `"infinite_coef"`, `"none"`) |
| Variable dropped (collinear with FE) | No within-group variation | Reconsider FE specification |
| Poisson won't converge | Separation or sparse data | Increase `glm.iter`, check for separation |
| "need panel.id" error | NW/DK requires panel structure | Add `panel.id = ~entity + year` |
| etable markdown doesn't work | Only in knitr context | Use `tex = FALSE` for data.frame output |
| `sunab` not found as function | sunab is a formula function | Use inside `feols()`: `feols(y ~ sunab(...))` |
| ^ in formula gives wrong result | `x^2` means `x:x` in formulas | Use `I(x^2)` for squaring |
| CRV3 not available | Not in fixest | Use `fwildclusterboot` or pyfixest for CRV3 |

## References

- fixest changelog: https://lrberge.github.io/fixest/news/index.html
- fixest FAQ: https://lrberge.github.io/fixest/articles/fixest_faq.html
- Berge, L., Butts, K., and McDermott, G. (2026). "Fast and User-Friendly
  Econometrics Estimations: The R Package fixest." arXiv:2601.21749.
- Cameron, A.C. and Miller, D.L. (2015). "A Practitioner's Guide to
  Cluster-Robust Inference." *Journal of Human Resources*, 50(2), 317-372.
