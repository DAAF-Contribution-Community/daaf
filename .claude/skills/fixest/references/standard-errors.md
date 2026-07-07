# Standard Errors

## Contents

- [SE Type Reference Table](#se-type-reference-table)
- [Clustered Standard Errors](#clustered-standard-errors)
- [Heteroskedasticity-Robust SEs](#heteroskedasticity-robust-ses)
- [Newey-West (HAC)](#newey-west-hac)
- [Driscoll-Kraay](#driscoll-kraay)
- [Conley Spatial](#conley-spatial)
- [Two-Way Clustering](#two-way-clustering)
- [Small Sample Corrections (ssc)](#small-sample-corrections-ssc)
- [Default SE Behavior](#default-se-behavior)

## SE Type Reference Table

| `vcov` Value | Type | When to Use | Panel Required |
|---|---|---|---|
| `"iid"` | Classical (spherical) | Homoskedastic, independent errors | No |
| `"hetero"` | HC1 robust | Default for cross-sectional data | No |
| `~group` | One-way cluster-robust | Correlated errors within groups | No |
| `~g1 + g2` | Two-way cluster-robust | Errors correlated along two dimensions | No |
| `"NW"` | Newey-West HAC | Time series, serial correlation | Yes |
| `"DK"` | Driscoll-Kraay | Panel, cross-sectional dependence | Yes |
| `conley(...)` | Conley spatial | Spatially correlated errors | Needs lat/lon |

## Clustered Standard Errors

### One-Way Clustering

```r
library(fixest)
data(trade, package = "fixest")

# At estimation time
fit <- feols(log(Euros) ~ log(dist_km) | Origin + Destination,
             data = trade, vcov = ~Origin)

# Or switch post-estimation
fit <- feols(log(Euros) ~ log(dist_km) | Origin + Destination, data = trade)
summary(fit, vcov = ~Origin)
```

The `~` prefix on the clustering variable is a one-sided formula. The `cluster`
argument is available as a convenience alias:

```r
# These are equivalent
fit <- feols(y ~ x | fe, data = df, vcov = ~state)
fit <- feols(y ~ x | fe, data = df, cluster = ~state)
```

### Choosing the Cluster Level

Following Cameron & Miller (2015): **cluster at the level of treatment assignment.**

| Treatment Varies At | Cluster At | Example |
|---------------------|-----------|---------|
| State level | `~state` | State policy evaluation |
| School level | `~school` | School intervention |
| Individual level (in clustered sample) | `~classroom` or `~school` | Student outcomes in clustered data |

When uncertain, clustering at a coarser level is generally conservative (wider
confidence intervals). Clustering at a finer level than treatment assignment can
be anti-conservative.

## Heteroskedasticity-Robust SEs

```r
# HC1 (Stata-equivalent "robust")
summary(fit, vcov = "hetero")

# "hetero" is HC1 in fixest terminology
# For HC0, HC2, HC3 — fixest does not provide these natively
# Use sandwich::vcovHC() with lmtest::coeftest() for base lm() models
# For fixest models, "hetero" (HC1) is the standard choice
```

fixest's `"hetero"` applies the HC1 correction (N/(N-k) scaling). This matches
Stata's `robust` option and is the most commonly used heteroskedasticity-robust
estimator in applied work.

## Newey-West (HAC)

For time series or panel data with serial correlation:

```r
# Requires panel.id to be set
fit <- feols(y ~ x1 | entity, data = df,
             panel.id = ~entity + year, vcov = "NW")

# Or with the panel() function
pdat <- panel(df, ~entity + year)
fit <- feols(y ~ x1 | entity, data = pdat, vcov = "NW")
```

Newey-West SEs are robust to both heteroskedasticity and autocorrelation up to
a specified lag. The bandwidth (number of lags) is chosen automatically by
default.

### Custom Bandwidth

```r
# Explicit bandwidth (number of lags): pass the lag to the NW() helper
summary(fit, vcov = NW(5))   # 5-lag Newey-West
# NOTE: `vcov = NW ~ 5` is NOT valid syntax and errors — the formula RHS of
# vcov helpers is reserved for panel/cluster variables, not the lag count.
# A formula is used when overriding the panel variables, e.g. NW ~ id + period.
```

## Driscoll-Kraay

For panels with cross-sectional dependence (shocks correlated across units):

```r
fit <- feols(y ~ x1 | entity, data = df,
             panel.id = ~entity + year, vcov = "DK")
```

Driscoll-Kraay SEs are robust to serial correlation, heteroskedasticity, AND
cross-sectional dependence. They are appropriate for macro panels where shocks
are correlated across units (e.g., states responding to national-level policy).

### When DK vs NW

| SE Type | Handles Serial Correlation | Handles Cross-Sectional Dependence |
|---------|---------------------------|-----------------------------------|
| NW | Yes | No |
| DK | Yes | Yes |
| Clustered | Depends on cluster level | Depends on cluster level |

## Conley Spatial

For spatially correlated errors (units that are geographically close may have
correlated errors):

```r
# Requires latitude and longitude columns (auto-detected from common names)
fit <- feols(y ~ x1, data = df, vcov = conley(cutoff = 100))

# conley() has NO lat/lon arguments — its only arguments are
# cutoff, pixel, and distance. To name the coordinate columns explicitly,
# use vcov_conley() post-estimation:
fit <- feols(y ~ x1, data = df)
vcov_conley(fit, lat = "latitude", lon = "longitude", cutoff = 100)

# Cutoff is in km; use an "mi" suffix string for miles
fit <- feols(y ~ x1, data = df, vcov = conley(cutoff = "50mi"))
```

The `cutoff` parameter specifies the distance (in km, or `"Xmi"` for miles)
beyond which spatial correlation is assumed to be zero. Units farther apart
than `cutoff` contribute zero to the spatial covariance kernel. If `cutoff` is
omitted, fixest deduces one via a rule of thumb — convenient, but a deliberate
cutoff is preferable in research scripts.

### Conley Parameters (conley() / vcov_conley())

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `cutoff` | Rule-of-thumb if missing | Distance cutoff in km (`"100mi"` string for miles) |
| `pixel` | `NULL` | Aggregate points into pixel-km squares (speed vs precision) |
| `distance` | `"triangular"` | Distance computation: `"triangular"` or `"spherical"` (great circle) |
| `lat`, `lon` | Auto-detected | Coordinate column names — `vcov_conley()` only |

fixest auto-detects latitude and longitude columns from common column names
(e.g., "lat", "latitude", "lon", "longitude"). If detection fails, specify them
explicitly via `vcov_conley()` — the in-formula `conley()` helper cannot take
column names.

## Two-Way Clustering

```r
# Cluster by state AND year
fit <- feols(y ~ x1 | entity, data = df, vcov = ~state + year)

# Post-estimation
summary(fit, vcov = ~state + year)
```

Two-way clustering accounts for correlation within states (across years) AND
within years (across states). The variance is computed using the
Cameron-Gelbach-Miller (2011) formula:

V_twoway = V_state + V_year - V_state_x_year

### When to Use Two-Way Clustering

- Panel data where errors may be correlated along both the cross-sectional
  and time dimensions
- Settings where one-way clustering may be insufficient (e.g., state-year
  panels where both state-level and year-level shocks exist)
- DiD with state-level treatment when year-specific shocks may also matter

## Small Sample Corrections (ssc)

The `ssc()` function controls degrees-of-freedom adjustments:

```r
# View default SSC settings (getFixest_ssc() reads; setFixest_ssc() SETS)
print(fixest::ssc())        # Shows the package defaults
fixest::getFixest_ssc()     # Shows any session-level override

# Customize (canonical 0.14 argument names)
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state,
             ssc = ssc(K.adj = TRUE, K.fixef = "none",
                       G.adj = TRUE, G.df = "min"))
```

### `ssc()` Parameters

Canonical names in 0.14 are `K.*` (parameter counting) and `G.*` (cluster
adjustment); the pre-0.13 names (`adj`, `fixef.K`, `cluster.adj`,
`cluster.df`) still work as deprecated aliases.

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `K.adj` | `TRUE` | Apply (N-1)/(N-K) small-sample adjustment |
| `K.fixef` | `"nonnested"` | Count FE in K: `"none"`, `"full"`, or `"nonnested"` (FEs nested in clusters excluded) |
| `K.exact` | `FALSE` | Compute the exact number of FE parameters (collinearity-aware) |
| `G.adj` | `TRUE` | Apply G/(G-1) cluster adjustment |
| `G.df` | `"min"` | Two-way cluster DOF: `"min"` (conservative) or `"conv"` (conventional) |
| `t.df` | `"min"` | DOF for the t distribution of test statistics |

### Matching Stata Results

```r
# Match Stata's one-way clustering (vce(cluster state)).
# NOTE: fixest's default K.fixef is "nonnested", so set "none" explicitly.
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state,
             ssc = ssc(K.adj = TRUE, K.fixef = "none", G.adj = TRUE))

# Match Stata's two-way clustering
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state + year,
             ssc = ssc(G.df = "conv"))
```

### Setting Defaults Globally

```r
# Set SSC defaults for the entire session
setFixest_ssc(ssc(K.adj = TRUE, K.fixef = "none", G.adj = TRUE))
```

## Default SE Behavior

### v0.14.0 Defaults

Since fixest 0.13 (carried forward in 0.14.0), the default standard errors are
**IID** (classical). This is a breaking change from pre-0.13 versions, which
defaulted to clustering by the first FE variable.

```r
# v0.14: default is IID
fit <- feols(y ~ x1 | entity, data = df)
summary(fit)  # Standard-errors: IID

# To get the old behavior, specify clustering explicitly
summary(fit, vcov = ~entity)
```

### Setting Defaults Globally

```r
# Set default SE type for all subsequent estimations.
# setFixest_vcov() takes NAMED arguments keyed by FE structure, not a
# `vcov = ` argument. The recognized keys are: no_FE, one_FE, two_FE,
# panel, all, and reset.
# CAVEAT: the `all` key only accepts "iid" or "hetero" (clustering is
# structure-dependent, so "cluster" must go through the per-structure keys).
setFixest_vcov(all = "hetero")          # Default to robust everywhere
setFixest_vcov(one_FE = "cluster",      # Default to clustering whenever
               two_FE = "cluster",      # the model has FE / panel structure
               panel = "cluster")
setFixest_vcov(reset = TRUE)            # Reset to package defaults (IID)

# Structure-conditional defaults: apply different SEs by FE count
setFixest_vcov(no_FE = "iid", one_FE = "cluster")
```

### Recommendation

Always specify `vcov` explicitly in research scripts to avoid ambiguity. This
makes the script's inference assumptions clear to reviewers and robust to
changes in package defaults:

```r
# Explicit is always better than implicit
fit <- feols(y ~ x1 | entity + year, data = df, vcov = ~entity)
```

## Comparing fixest and pyfixest SE Syntax

| Operation | R fixest | pyfixest |
|-----------|----------|----------|
| One-way cluster | `vcov = ~entity` | `vcov={"CRV1": "entity"}` |
| Two-way cluster | `vcov = ~entity + year` | `vcov={"CRV1": "entity+year"}` |
| Heteroskedastic | `vcov = "hetero"` | `vcov="hetero"` |
| IID | `vcov = "iid"` | `vcov="iid"` |
| Newey-West | `vcov = "NW"` | `vcov="NW"` |
| Driscoll-Kraay | `vcov = "DK"` | `vcov="DK"` |
| Conley spatial | `vcov = conley(...)` | Not supported |
| CRV3 jackknife | Not built-in | `vcov={"CRV3": "g"}` |

The most notable difference is the clustering syntax: R uses a one-sided formula
(`~entity`), while pyfixest uses a dictionary (`{"CRV1": "entity"}`).

## References

- Cameron, A.C. and Miller, D.L. (2015). "A Practitioner's Guide to
  Cluster-Robust Inference." *Journal of Human Resources*, 50(2), 317-372.
- Cameron, A.C., Gelbach, J.B., and Miller, D.L. (2011). "Robust Inference
  with Multiway Clustering." *Journal of Business & Economic Statistics*,
  29(2), 238-249.
- Conley, T.G. (1999). "GMM estimation with cross-sectional dependence."
  *Journal of Econometrics*, 92(1), 1-45.
- Newey, W.K. and West, K.D. (1987). "A Simple, Positive Semi-definite,
  Heteroskedasticity and Autocorrelation Consistent Covariance Matrix."
  *Econometrica*, 55(3), 703-708.
- Driscoll, J.C. and Kraay, A.C. (1998). "Consistent Covariance Matrix
  Estimation with Spatially Dependent Panel Data." *Review of Economics and
  Statistics*, 80(4), 549-560.
- fixest documentation — Standard Errors:
  https://lrberge.github.io/fixest/articles/standard_errors.html
