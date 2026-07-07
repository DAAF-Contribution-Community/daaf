# Difference-in-Differences

## Contents

- [TWFE DiD](#twfe-did)
- [Event Study Specification](#event-study-specification)
- [Sun-Abraham Saturated Estimator (sunab)](#sun-abraham-saturated-estimator-sunab)
- [Event Study Plotting with iplot](#event-study-plotting-with-iplot)
- [Parallel Trends Assessment](#parallel-trends-assessment)
- [Comparison with pyfixest DiD](#comparison-with-pyfixest-did)

## TWFE DiD

### Basic TWFE DiD

```r
library(fixest)
data(base_did, package = "fixest")

# Classic 2x2 DiD with entity + time FE
fit <- feols(y ~ treat:post | id + period, data = base_did, vcov = ~id)
summary(fit)

# Or with a pre-computed treatment indicator
fit <- feols(y ~ treated | id + period, data = base_did, vcov = ~id)
```

### When TWFE Works

TWFE DiD produces unbiased estimates when:
- **Single treatment date**: All treated units adopt treatment simultaneously
- **Homogeneous effects**: Treatment effect is the same across all units and
  time periods
- **No anticipation**: Units do not change behavior before treatment

### When TWFE Fails

With **staggered treatment timing** and **heterogeneous treatment effects**, TWFE
can produce severely biased estimates including sign reversals. This occurs
because TWFE implicitly uses already-treated units as controls for newly-treated
units, creating "forbidden comparisons" with negative weights (Goodman-Bacon,
2021; de Chaisemartin & D'Haultfoeuille, 2020).

**When you have staggered treatment:** Use `sunab()` for the Sun-Abraham
saturated estimator. See the section below.

## Event Study Specification

### Manual Event Study with `i()`

```r
# Create relative-time variable: periods since treatment
df$rel_year <- df$year - df$treatment_year

# Event study: i() creates dummies for each relative year, omitting -1
fit <- feols(y ~ i(rel_year, ref = -1) | entity + year, data = df,
             vcov = ~entity)

# Plot the event study
iplot(fit)
```

The `ref = -1` normalizes to the period immediately before treatment, which is
the standard convention.

### i() Operator Details

```r
# Basic categorical with reference level
y ~ i(year, ref = 2000) | entity

# Numeric interaction with categorical
y ~ i(group, x1, ref = "control")

# Binning distant periods (to reduce noise at extremes)
y ~ i(rel_year, ref = -1, bin = c(-Inf, -5, 5, Inf))
# This bins: all periods < -5 together, all periods > 5 together

# Keeping specific range
y ~ i(rel_year, ref = -1, keep = -5:10)
# Drops coefficients outside [-5, 10] window
```

### The `keep` and `bin` Arguments

| Argument | Purpose | Example |
|----------|---------|---------|
| `ref` | Omitted reference level | `ref = -1` |
| `keep` | Show only these levels | `keep = -5:10` |
| `bin` | Combine extreme levels | `bin = c(-Inf, -5, 5, Inf)` |

These are particularly useful for event studies where very early or very late
periods have few observations and noisy estimates.

## Sun-Abraham Saturated Estimator (sunab)

### What is sunab?

`sunab()` implements the Sun & Abraham (2021) interaction-weighted estimator for
staggered DiD. It fully saturates the model with cohort-by-relative-time
indicators, then aggregates using appropriate weights. This avoids the negative
weighting problem of TWFE.

### Basic Usage

```r
data(base_stagg, package = "fixest")

# sunab(cohort_var, time_var)
# cohort_var = year unit first treated (0 or Inf for never-treated)
# time_var = calendar time period
fit <- feols(y ~ x1 + sunab(year_treated, year) | id + year,
             data = base_stagg, vcov = ~id)
summary(fit)
iplot(fit)
```

`sunab()` is a **formula function** — it goes inside the `feols()` formula, not
as a separate function call. It is not exported as a standalone function; it only
works within fixest estimation formulas.

### sunab Arguments

| Argument | Purpose | Example |
|----------|---------|---------|
| 1st positional | Cohort variable (year of treatment) | `year_treated` |
| 2nd positional | Time variable (calendar period) | `year` |
| `ref.p` | Reference period(s) | `ref.p = -1` (default) |
| `ref.c` | Reference cohort | `ref.c = min(cohort)` |
| `bin` | Bin extreme periods | `bin = c(-20, 10)` |
| `att` | Report ATT only | `att = TRUE` |

### Aggregation

```r
# Dynamic event study (default)
fit <- feols(y ~ sunab(year_treated, year) | id + year,
             data = base_stagg, vcov = ~id)
summary(fit)

# Aggregate to overall ATT
summary(fit, agg = "ATT")

# Aggregate by cohort
summary(fit, agg = "cohort")

# Aggregate by period
summary(fit, agg = "period")
```

The `agg` argument in `summary()` provides different levels of aggregation:

| `agg` Value | What It Reports |
|-------------|-----------------|
| (none) | All cohort-by-period estimates |
| `"ATT"` | Single overall treatment effect |
| `"cohort"` | Treatment effect by cohort (treatment-year group) |
| `"period"` | Treatment effect by relative time period |

### Data Requirements for sunab

1. **Cohort variable**: Must indicate the year (or period) the unit first
   received treatment. Never-treated units should have a value that is never
   observed as a treatment time (e.g., 0 or Inf or 10000).
2. **Time variable**: Calendar time period.
3. **Unit identifier**: In the FE specification (e.g., `| id + year`).
4. **Never-treated units**: Strongly recommended. Without a never-treated
   control group, the estimator uses the last-treated cohort as the reference,
   which may be problematic.

### Complete sunab Example

```r
library(fixest)
data(base_stagg, package = "fixest")

# Examine the data structure
cat("Cohort values:", sort(unique(base_stagg$year_treated)), "\n")
# year_treated: 0 (never-treated), 5, 6, 7 (treatment cohorts)

# Estimate Sun-Abraham
fit_sa <- feols(y ~ x1 + sunab(year_treated, year) | id + year,
                data = base_stagg, vcov = ~id)

# Event study plot
iplot(fit_sa, main = "Sun-Abraham Event Study")

# Overall ATT
summary(fit_sa, agg = "ATT")

# Compare with naive TWFE
base_stagg$treated <- as.numeric(base_stagg$year >= base_stagg$year_treated &
                                   base_stagg$year_treated > 0)
fit_twfe <- feols(y ~ treated + x1 | id + year,
                  data = base_stagg, vcov = ~id)

# Side-by-side comparison
etable(fit_twfe, fit_sa, headers = c("TWFE", "Sun-Abraham"))
```

## Event Study Plotting with iplot

### Basic Usage

```r
# For models with i() terms
fit <- feols(y ~ i(rel_year, ref = -1) | entity + year, data = df)
iplot(fit)

# For sunab() models
fit_sa <- feols(y ~ sunab(cohort, period) | id + period, data = df)
iplot(fit_sa)
```

### Customization

```r
iplot(fit,
      main = "Event Study: Treatment Effect Over Time",
      xlab = "Periods Relative to Treatment",
      ylab = "Estimated Effect",
      ref.line = -1,           # Vertical reference line
      zero.line = TRUE,        # Horizontal line at y=0
      ci.width = 0.05,         # 95% CI (alpha)
      ci.fill = TRUE,          # Filled confidence bands
      pt.pch = 20,             # Point shape
      col = "steelblue")       # Color
```

### Comparing Multiple Models

```r
# Compare TWFE vs Sun-Abraham
fit1 <- feols(y ~ i(rel_year, ref = -1) | id + year, data = df)
fit2 <- feols(y ~ sunab(cohort, year) | id + year, data = df)

iplot(list(fit1, fit2),
      main = "TWFE vs Sun-Abraham",
      legendtext = c("TWFE", "Sun-Abraham"))
```

### Saving Plots

```r
# Save to file for research pipeline
png("output/figures/event_study.png", width = 10, height = 6,
    units = "in", res = 300)
iplot(fit, main = "Event Study")
dev.off()

# Or with pdf for LaTeX
pdf("output/figures/event_study.pdf", width = 10, height = 6)
iplot(fit)
dev.off()
```

## Parallel Trends Assessment

The parallel trends assumption — that treated and control groups would have
followed the same trajectory absent treatment — is fundamentally untestable.
Pre-treatment event study coefficients provide suggestive evidence but cannot
confirm the assumption.

### Visual Assessment

```r
# Pre-treatment coefficients close to zero suggest parallel trends
fit <- feols(y ~ i(rel_year, ref = -1) | entity + year, data = df,
             vcov = ~entity)
iplot(fit)
# Look for: pre-treatment coefficients near zero, no trend
```

### Joint F-Test for Pre-Trends

```r
# Formal test that all pre-treatment coefficients are jointly zero
# Use wald() to test the pre-period coefficients
fit <- feols(y ~ i(rel_year, ref = -1) | entity + year, data = df)

# Identify pre-treatment coefficients
pre_coefs <- grep("rel_year::-[0-9]", names(coef(fit)), value = TRUE)
wald(fit, keep = pre_coefs)
```

### Important Caveat

Failing to reject the null of no pre-trends does NOT confirm parallel trends.
It may simply reflect low statistical power. Roth (2022) shows that pre-tests
have low power against violations that would meaningfully bias treatment effect
estimates.

When parallel trends are critical to your identification:
- Present pre-treatment coefficients transparently
- Discuss the plausibility of the assumption based on institutional knowledge
- Consider the Rambachan & Roth (2023) sensitivity analysis (HonestDiD R
  package) for formal robustness to violations

## Comparison with pyfixest DiD

| Feature | R fixest | pyfixest |
|---------|----------|----------|
| TWFE | `feols(y ~ treat \| fe)` | `pf.feols("y ~ treat \| fe")` |
| Sun-Abraham | `sunab()` in formula | `pf.event_study(estimator="saturated")` |
| did2s | Not built-in (use `did2s` R package) | `pf.did2s()` built-in |
| LP-DiD | Not built-in | `pf.lpdid()` built-in |
| Event study | `i(rel_year, ref=-1)` in formula | `"i(rel_year, ref=-1)"` in formula |
| iplot | `iplot(fit)` (standalone function) | `fit.iplot()` (method) |
| ATT aggregation | `summary(fit, agg="ATT")` | `fit.aggregate(weighting="shares")` |
| panelview | Not built-in | `pf.panelview()` built-in |

Key difference: R fixest uses `sunab()` as a formula function inside `feols()`,
while pyfixest uses a separate `event_study()` function. The underlying estimator
is identical. R fixest does not include `did2s` or `lpdid` natively — those
require separate R packages (`did2s`, or manual implementation).

## Clustering in DiD Designs

Following Cameron & Miller (2015): **cluster at the level of treatment
assignment.**

```r
# State-level policy -> cluster at state
fit <- feols(y ~ treat | entity + year, data = df, vcov = ~state)

# sunab with state-level clustering
fit <- feols(y ~ sunab(cohort, year) | id + year, data = df, vcov = ~state)
```

See `standard-errors.md` for full guidance on choosing cluster levels.

## References

- Sun, L. and Abraham, S. (2021). "Estimating Dynamic Treatment Effects in
  Event Studies with Heterogeneous Treatment Effects." *Journal of Econometrics*,
  225(2), 175-199.
- Goodman-Bacon, A. (2021). "Difference-in-Differences with Variation in
  Treatment Timing." *Journal of Econometrics*, 225(2), 254-277.
- de Chaisemartin, C. and D'Haultfoeuille, X. (2020). "Two-Way Fixed Effects
  Estimators with Heterogeneous Treatment Effects." *American Economic Review*,
  110(9), 2964-2996.
- Roth, J. (2022). "Pretest with Caution: Event-Study Estimates after Testing
  for Parallel Trends." *American Economic Review: Insights*, 4(3), 305-322.
- Rambachan, A. and Roth, J. (2023). "A More Credible Approach to Parallel
  Trends." *Review of Economic Studies*, 90(5), 2555-2591.
- fixest documentation — DiD and sunab:
  https://lrberge.github.io/fixest/articles/fixest_walkthrough.html
