# Instrumental Variables

## Contents

- [IV Formula Syntax](#iv-formula-syntax)
- [First-Stage Diagnostics](#first-stage-diagnostics)
- [Weak Instrument Tests](#weak-instrument-tests)
- [Common IV Designs](#common-iv-designs)

## IV Formula Syntax

fixest uses a three-part formula for IV estimation. The third part (after the
second `|`) specifies `endogenous ~ instruments`:

### Basic IV (No Fixed Effects)

```r
library(fixest)

# y ~ exogenous | 0 (no FE) | endogenous ~ instruments
fit <- feols(y ~ x_exog | 0 | x_endog ~ z_instrument, data = df)
summary(fit)
```

Use `0` for the FE slot when you have no fixed effects but need IV.

### IV with Fixed Effects

```r
# y ~ exogenous | FE | endogenous ~ instruments
fit <- feols(y ~ x_exog | entity + year | x_endog ~ z_instrument, data = df)
```

### Multiple Instruments (Over-Identification)

```r
# Two instruments for one endogenous variable
fit <- feols(y ~ 1 | fe | x_endog ~ z1 + z2, data = df)
```

Over-identification allows for Sargan/Hansen tests of instrument validity.

### No Exogenous Regressors

When the only non-FE regressor is the endogenous variable, use `1` for the
exogenous part:

```r
# Only endogenous variable (plus FE)
fit <- feols(y ~ 1 | entity + year | x_endog ~ z1, data = df)
```

### IV with Clustered Standard Errors

```r
fit <- feols(y ~ x_exog | entity + year | x_endog ~ z1, data = df,
             vcov = ~entity)
```

Or switch post-estimation:

```r
fit <- feols(y ~ x_exog | entity + year | x_endog ~ z1, data = df)
summary(fit, vcov = ~entity)
```

### Multiple Endogenous Variables

```r
# Two endogenous variables, each with their own instrument
fit <- feols(y ~ x_exog | fe | x_endog1 + x_endog2 ~ z1 + z2, data = df)
```

The number of instruments must be at least as large as the number of endogenous
variables (order condition for identification).

## First-Stage Diagnostics

The first-stage regression estimates the relationship between the instrument(s)
and the endogenous variable. A strong first stage is essential for reliable IV
estimates.

### Accessing First-Stage Results

```r
fit <- feols(y ~ 1 | fe | x_endog ~ z1 + z2, data = df, vcov = ~entity)

# View first-stage results
summary(fit, stage = 1)

# First-stage F-statistic
fitstat(fit, type = "ivf")

# Wald statistic on excluded instruments (uses the model's vcov, so it is
# robust/cluster-aware when the model was estimated that way)
fitstat(fit, type = "ivwald")

# All IV diagnostics at once
fitstat(fit, type = ~ivf + ivwald + kpr + cd + sargan + wh)
```

### fitstat() Types for IV

There are no `"ivf.kp"` / `"ivwald.kp"` types — the `.` in a fitstat type
denotes a component (e.g., `ivf.stat`, `ivf.p`), so those names error. The
Kleibergen-Paap and Cragg-Donald statistics have their own type names:

| Type | Description | When to Use |
|------|-------------|-------------|
| `"ivf"` | First-stage F-statistic | Always check (rule of thumb: F > 10) |
| `"ivwald"` | Wald statistic on excluded instruments, computed with the model's vcov | Preferred with robust/clustered errors |
| `"kpr"` | Kleibergen-Paap rank test | Underidentification test. Only computed for IID vcov or exactly identified models (returns NA otherwise, with a warning) |
| `"cd"` | Cragg-Donald F | Weak-instrument statistic under IID errors; compare to Stock-Yogo critical values |
| `"sargan"` | Sargan test of overidentification | When # instruments > # endogenous |
| `"wh"` | Wu-Hausman endogeneity test | Whether IV is needed (H0: exogenous) |

Run `fitstat(show_types = TRUE)` for the full list of valid type names.

### Interpreting First Stage

```r
# View the first-stage regression
s1 <- summary(fit, stage = 1)
cat("First-stage coefficients:\n")
print(coef(s1))
cat("First-stage F:", fitstat(fit, type = "ivf")$ivf$stat, "\n")
```

The first-stage estimates: `x_endog = pi_0 + pi_1*z1 + pi_2*z2 + FE + error`

Key checks:
- **Sign and significance of pi**: Instruments should predict the endogenous
  variable in the expected direction
- **F-statistic > 10**: Staiger & Stock (1997) rule of thumb for single
  endogenous variable
- **`ivwald` with robust/clustered vcov**: Preferred first-stage strength
  check with non-IID errors

## Weak Instrument Tests

Weak instruments produce unreliable IV estimates: biased toward OLS, with
severely distorted inference (size distortion of Wald tests).

### Stock-Yogo Critical Values

For the traditional Cragg-Donald F (under IID errors), with **1 endogenous
regressor** (Stock & Yogo 2005; as tabulated in Stata's ivregress
postestimation documentation):

| Maximal Size of 5% Wald Test | 1 Instrument | 2 Instruments | 3 Instruments |
|------------------------------|-------------|---------------|---------------|
| 10% | 16.38 | 19.93 | 22.30 |
| 15% | 8.96 | 11.59 | 12.83 |
| 20% | 6.66 | 8.75 | 9.54 |
| 25% | 5.53 | 7.25 | 7.80 |

These are the *maximal size* critical values: a Cragg-Donald F above the
threshold bounds the true size of a nominal 5% Wald test at the stated level.
Stock-Yogo *relative-bias* critical values are a different table and exist
only for 3 or more instruments.

### Comprehensive Diagnostics

```r
fit <- feols(y ~ 1 | fe | x_endog ~ z1 + z2, data = df, vcov = ~entity)

# All IV stats
fitstat(fit, type = ~ivf + ivwald + cd + sargan + wh)
```

### Recommendations by Situation

| Situation | Recommended Test | Threshold |
|-----------|-----------------|-----------|
| Single endogenous, IID | First-stage F (`ivf`) or Cragg-Donald (`cd`) | > 10 (Staiger-Stock) / Stock-Yogo tables |
| Single endogenous, clustered | First-stage Wald with model vcov (`ivwald`) | > 10 (approximate) |
| Multiple endogenous | Cragg-Donald (`cd`) | Stock-Yogo tables |
| Over-identified | Sargan test (`sargan`) | p > 0.05 (instruments valid) |
| Suspected exogeneity | Wu-Hausman (`wh`) | p < 0.05 (endogenous) |

## Common IV Designs

Brief descriptions of common instrument strategies. For methodology guidance on
identification assumptions, load the `data-scientist` skill's causal inference
references.

### Lottery / Randomization Instruments

```r
# Charter school lottery: lottery_win instruments for charter_attendance
fit <- feols(test_score ~ demographics | district | charter_attend ~ lottery_win,
             data = df, vcov = ~school)
```

**Identification:** Random assignment ensures the instrument is independent of
potential outcomes. Estimates a Local Average Treatment Effect (LATE) for compliers.

### Geographic / Distance Instruments

```r
# Distance to college instruments for years of education
fit <- feols(log_wage ~ experience | 0 | education ~ college_proximity,
             data = df, vcov = "hetero")
```

**Key assumption:** Distance affects the outcome only through the endogenous
variable (exclusion restriction).

### Policy / Regulatory Instruments

```r
# Compulsory schooling laws instrument for education
fit <- feols(log_wage ~ 1 | birth_cohort + state | education ~ compulsory_years,
             data = df, vcov = ~state)
```

### Shift-Share / Bartik Instruments

```r
# Bartik instrument: local exposure to national industry shocks
# Construct: sum(local_share_j * national_growth_j)
fit <- feols(y ~ controls | region + year | employment_change ~ bartik,
             data = df, vcov = ~region)
```

## References

- Staiger, D. and Stock, J.H. (1997). "Instrumental Variables Regression with
  Weak Instruments." *Econometrica*, 65(3), 557-586.
- Stock, J.H. and Yogo, M. (2005). "Testing for Weak Instruments in Linear IV
  Regression." In Andrews, D.W.K. and Stock, J.H. (eds.), *Identification and
  Inference for Econometric Models*, Cambridge University Press.
- Kleibergen, F. and Paap, R. (2006). "Generalized reduced rank tests using
  the singular value decomposition." *Journal of Econometrics*, 133(1), 97-126.
- fixest documentation — IV:
  https://lrberge.github.io/fixest/articles/fixest_walkthrough.html#iv
