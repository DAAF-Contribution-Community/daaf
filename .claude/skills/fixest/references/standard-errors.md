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
# Explicit bandwidth (number of lags)
summary(fit, vcov = NW ~ 5)  # 5-lag Newey-West
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
# Requires latitude and longitude columns
fit <- feols(y ~ x1, data = df,
             vcov = conley(cutoff = 100, lat = "latitude", lon = "longitude"))

# With distance in miles (default is km)
fit <- feols(y ~ x1, data = df,
             vcov = conley(cutoff = 50, lat = "lat", lon = "lon", distance = "miles"))
```

The `cutoff` parameter specifies the distance beyond which spatial correlation
is assumed to be zero. Units farther apart than `cutoff` contribute zero to the
spatial covariance kernel.

### Conley Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `cutoff` | Required | Distance cutoff (km or miles) |
| `lat` | Auto-detected | Latitude column name |
| `lon` | Auto-detected | Longitude column name |
| `distance` | `"km"` | Distance units: `"km"` or `"miles"` |

fixest will attempt to auto-detect latitude and longitude columns from common
column names (e.g., "lat", "latitude", "lon", "longitude"). If detection fails,
specify them explicitly.

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
# View default SSC settings
fixest::setFixest_ssc()

# Customize
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state,
             ssc = ssc(adj = TRUE, fixef.K = "none",
                       cluster.adj = TRUE, cluster.df = "min"))
```

### `ssc()` Parameters

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `adj` | `TRUE` | Apply (N-1)/(N-k) small-sample adjustment |
| `fixef.K` | `"none"` | Count FE in k: `"none"`, `"full"`, or `"nested"` |
| `cluster.adj` | `TRUE` | Apply G/(G-1) cluster adjustment |
| `cluster.df` | `"min"` | Two-way cluster DOF: `"min"` (conservative) or `"conventional"` |

### Matching Stata Results

```r
# Match Stata's one-way clustering (vce(cluster state))
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state,
             ssc = ssc(adj = TRUE, fixef.K = "none",
                       cluster.adj = TRUE))

# Match Stata's two-way clustering
fit <- feols(y ~ x1 | fe, data = df,
             vcov = ~state + year,
             ssc = ssc(cluster.df = "conventional"))
```

### Setting Defaults Globally

```r
# Set SSC defaults for the entire session
setFixest_ssc(ssc(adj = TRUE, fixef.K = "none", cluster.adj = TRUE))
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
setFixest_vcov(all = "cluster")         # Default to clustering everywhere
setFixest_vcov(all = "hetero")          # Default to robust everywhere
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
