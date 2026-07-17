# Causal Inference: R Explained for Python Users

R has been the primary language for causal inference in quantitative social
science. Most influential causal methods papers ship R implementations first.
This reference explains R causal inference code in terms Python users know.

DAAF's R stack provides strong coverage:
- **fixest:** TWFE DiD, Sun-Abraham (`sunab()`), event studies (`i()`, `iplot`)
- **did2s:** Two-stage DiD (Gardner, 2022)
- **rdrobust:** Regression discontinuity (same authors as Python version)
- **marginaleffects:** Post-estimation interpretation (same author as Python)
- **MatchIt/WeightIt:** Matching and weighting (R has much stronger coverage)

> **Versions referenced:**
> R: fixest 0.14.0, marginaleffects 0.32.0, rdrobust 3.0.0
> Python: pyfixest 0.40.0, marginaleffects 0.5.0, rdrobust 1.3.0
> See SKILL.md § Library Versions for the complete version table.

> **Availability:** Of the R packages below, `fixest`, `marginaleffects`,
> `rdrobust` (3.0.0), and `survival` (ships with the R distribution) are
> pre-installed in DAAF. The specialized causal packages referenced here —
> `did2s`, `did`, `MatchIt`, `WeightIt`, `cobalt`, `grf`, `Synth`,
> `augsynth`, `gsynth` — are NOT pre-installed, and runtime installs are blocked
> (see CLAUDE.md § Runtime Package Installation) — escalate to the user to add the
> needed package to the Dockerfile (user additions block) and rebuild before use.

---

## 1. Difference-in-Differences

### Traditional TWFE DiD

```r
# R (fixest) -- you know this as pf.feols("y ~ treated | unit + time", ...)
fit <- feols(y ~ treated | unit + time, data = df, vcov = ~unit)
```

Formula is identical. Only SE syntax differs (`~unit` vs `{"CRV1": "unit"}`).

### Two-Stage DiD (did2s)

```r
# R -- you know this as pf.did2s(...)
library(did2s)
fit <- did2s(
  data = df, yname = "y",
  first_stage = ~ 0 | unit + time,
  second_stage = ~ i(rel_time, ref = -1),
  treatment = "treated", cluster_var = "unit"
)
iplot(fit)
```

Key difference: R uses `cluster_var`; Python uses `cluster`.

### Sun-Abraham Saturated Estimator

```r
# R -- sunab() is a formula function inside feols
fit <- feols(y ~ sunab(cohort, period) | unit + period, data = df, vcov = ~unit)
summary(fit, agg = "ATT")
iplot(fit)
```

```python
# Python -- uses a separate function
fit = pf.event_study(data=df, yname="y", idname="unit", tname="period",
                     gname="cohort", estimator="saturated", att=False)
```

R uses `sunab()` inline in the formula. Python uses `pf.event_study()` with
`estimator="saturated"`.

---

## 2. Event Studies

```r
# R -- you know this as pf.feols("y ~ i(rel_year, ref=-1) | unit + year", ...)
df$rel_year <- df$year - df$treatment_year
fit <- feols(y ~ i(rel_year, ref = -1) | unit + year, data = df, vcov = ~unit)
iplot(fit)
iplot(fit, joint = TRUE)   # Bonferroni bands
```

| R | Python |
|---|--------|
| `iplot(fit)` (standalone) | `fit.iplot()` (method) |
| `iplot(fit, joint = TRUE)` | `fit.iplot(joint="both")` |

---

## 3. Regression Discontinuity

Both R and Python rdrobust are maintained by the same authors. The API is
virtually identical.

```r
# R -- you know this as rdrobust.rdrobust(Y, X, c=cutoff)
library(rdrobust)
rd <- rdrobust(Y, X, c = cutoff)
summary(rd)
rdplot(Y, X, c = cutoff)
```

| R | Python |
|---|--------|
| `rdrobust(Y, X, c = cutoff)` | `rdrobust(Y, X, c=cutoff)` |
| `rdplot(Y, X, c = cutoff)` | `rdplot(Y, X, c=cutoff)` |
| `h = c(left, right)` | `h=[left, right]` |
| `covs = cbind(c1, c2)` | `covs=covs_array` |

The API is nearly identical. Main differences: R's `c()` vs Python's `[]`,
R's `cbind()` vs numpy arrays.

---

## 4. Matching and Weighting

This is where **R significantly exceeds Python coverage.** R has mature, validated
packages; Python alternatives are fragmented.

```r
# R (MatchIt) -- no strong Python equivalent
library(MatchIt)
m.out <- matchit(treat ~ x1 + x2 + x3, data = df, method = "nearest")
summary(m.out)
matched_df <- match.data(m.out)

# R (WeightIt) -- no Python equivalent
library(WeightIt)
w.out <- weightit(treat ~ x1 + x2 + x3, data = df, method = "ps")
```

| R Package | Python Equivalent | Fidelity |
|-----------|------------------|----------|
| `MatchIt` | Manual with scikit-learn | Low |
| `WeightIt` | No equivalent | N/A |
| `cobalt` (balance) | No equivalent | N/A |

---

## 5. Marginal Effects

Both implementations are by Vincent Arel-Bundock. The API is intentionally
parallel.

```r
# R -- you know this as marginaleffects.avg_slopes(fit, variables="x1")
library(marginaleffects)
avg_slopes(fit, variables = "x1")
predictions(fit, newdata = datagrid(x1 = c(0, 1), x2 = mean))
hypotheses(fit, "x1 = x2")
```

The R version supports 100+ model classes. The Python version supports
statsmodels, pyfixest, and scikit-learn.

---

## 6. Ecosystem Comparison

| Method | R | Python | Fidelity |
|--------|---|--------|----------|
| TWFE DiD | `fixest::feols()` | `pf.feols()` | Very High |
| did2s | `did2s::did2s()` | `pf.did2s()` | Very High |
| Callaway-Sant'Anna | `did::att_gt()` (not pre-installed) | `csdid` (`pip install csdid`) | Medium |
| Sun-Abraham | `fixest::sunab()` | `pf.event_study(est="saturated")` | High |
| LP-DiD | Manual | `pf.lpdid()` | Python has better wrapper |
| RD | `rdrobust` | `rdrobust` (Python) | Very High (same authors) |
| IV + FE | `fixest::feols()` | `pf.feols()` | Very High |
| **Matching** | `MatchIt` | Manual | **Significant gap** |
| **Weighting** | `WeightIt` | No equivalent | **Significant gap** |
| Synthetic control | `Synth`, `augsynth`, `gsynth` | `CausalPy` (Bayesian) | Low |
| Causal forests | `grf` | `econml` | Medium |
| **GLM + FE** | `fixest::feglm()` | **Not supported** | **Major gap** |
| Survival/Cox | `survival::coxph()` | `lifelines` | High |

> **Sources:** Cunningham, *Causal Inference: The Mixtape* (2021);
> Huntington-Klein, *The Effect* (2021);
> Cattaneo, Idrobo, & Titiunik, *rdrobust* (rdpackages.github.io)
