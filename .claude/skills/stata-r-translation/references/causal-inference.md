# Causal Inference: Stata to R Translation

R has the strongest causal inference ecosystem of the three languages (Stata, R,
Python). Most methods papers now ship R packages first or simultaneously with
Stata. This means Stata users moving to R gain capabilities rather than losing
them.

> **Versions referenced:** R: fixest 0.14.0, rdrobust 3.0.0, did 2.1.2,
> augsynth (latest), MatchIt (latest), binsreg (latest)
> Stata: Stata 18

> **Availability:** `fixest`, `rdrobust` (3.0.0), and `marginaleffects` are
> pre-installed in DAAF. The specialized causal packages used below — `did2s`,
> `did`, `DIDmultiplegt`, `rddensity`, `MatchIt`, `augsynth`, `Synth`,
> `binsreg`, `AIPW`, `lmtp` — are NOT pre-installed, and runtime installs are
> blocked (see CLAUDE.md § Runtime Package Installation) — escalate to the user
> to add the needed package to the Dockerfile (user additions block) and rebuild
> before use.

---

## 1. Difference-in-Differences

### Traditional TWFE DiD

```stata
reghdfe y treated_post, absorb(unit year) cluster(unit)
```

```r
fit <- feols(y ~ treated_post | unit + year, data = df, vcov = ~unit)
```

### Sun-Abraham (via fixest sunab)

```stata
eventstudyinteract y ..., absorb(unit year) cohort(first_treat) control_cohort(never)
```

```r
fit <- feols(y ~ sunab(first_treat, year) | unit + year, data = df, vcov = ~unit)
summary(fit, agg = "ATT")     # Overall ATT
iplot(fit)                      # Event study plot
```

### Callaway-Sant'Anna

```stata
csdid y, ivar(unit) time(year) gvar(first_treat) method(dripw)
```

```r
library(did)
out <- att_gt(
  yname = "y", tname = "year", idname = "unit", gname = "first_treat",
  data = df, control_group = "nevertreated", est_method = "dr"
)
aggte(out, type = "simple")    # Overall ATT
aggte(out, type = "dynamic")   # Dynamic event study
ggdid(out)                      # Plot
```

### DiD Estimator Summary

| Stata | R | Notes |
|-------|---|-------|
| `reghdfe y treated, absorb(unit year)` | `feols(y ~ treated \| unit + year)` | TWFE |
| `did2s` | `did2s::did2s()` | Imputation |
| `csdid` | `did::att_gt()` | Group-time ATTs |
| `eventstudyinteract` / `sunab` | `feols(y ~ sunab(...) \| ...)` | Sun-Abraham (built into fixest) |
| `did_multiplegt` | `DIDmultiplegt::did_multiplegt()` | R package exists |

**Key R advantage:** `sunab()` is built directly into fixest's formula interface.
No separate package needed.

---

## 2. Event Studies

```stata
gen rel_year = year - treatment_year
reghdfe y ib(-1).rel_year, absorb(unit year) cluster(unit)
coefplot, keep(*.rel_year) vertical
```

```r
df$rel_year <- df$year - df$treatment_year
fit <- feols(y ~ i(rel_year, ref = -1) | unit + year, data = df, vcov = ~unit)
iplot(fit)                                # Event study plot
iplot(fit, ci_level = c(0.9, 0.95))      # Multiple CI bands
coefplot(fit)                              # Coefficient plot
```

---

## 3. Regression Discontinuity

Same authors maintain Stata, R, and Python versions. Translation is mechanical.

```stata
rdrobust Y X, c(cutoff)
rdplot Y X, c(cutoff)
rdrobust Y X, c(cutoff) fuzzy(T)
```

```r
library(rdrobust)
rd <- rdrobust(Y, X, c = cutoff)
summary(rd)
rdplot(Y, X, c = cutoff)
rd_fuzzy <- rdrobust(Y, X, c = cutoff, fuzzy = T)
```

| Stata | R | Notes |
|-------|---|-------|
| `rdrobust Y X, c(0)` | `rdrobust(Y, X, c = 0)` | Identical |
| `rdplot Y X, c(0)` | `rdplot(Y, X, c = 0)` | Identical |
| `rdbwselect Y X` | `rdbwselect(Y, X)` | Identical |
| `rddensity X` | `rddensity::rddensity(X)` | Identical |

---

## 4. Matching and Propensity Scores

R has much stronger matching support than Python via MatchIt.

```stata
teffects psmatch (y) (treat x1 x2 x3)
psmatch2 treat x1 x2, outcome(y) neighbor(3)
cem x1 x2 x3, treatment(treat)
```

```r
library(MatchIt)

# Nearest-neighbor PS matching
m <- matchit(treat ~ x1 + x2 + x3, data = df, method = "nearest")
summary(m)                              # Balance diagnostics
plot(m, type = "jitter")                # Visual balance check
matched_df <- match.data(m)             # Extract matched data
fit <- lm(y ~ treat, data = matched_df, weights = weights)

# CEM
m <- matchit(treat ~ x1 + x2 + x3, data = df, method = "cem")

# Full matching
m <- matchit(treat ~ x1 + x2 + x3, data = df, method = "full")
```

**Key R advantage:** MatchIt provides comprehensive balance diagnostics and
correct standard errors that account for the matching step. This is a major
gap in the Python ecosystem.

---

## 5. Synthetic Control

```stata
synth depvar predictor1 predictor2, trunit(id) trperiod(year)
```

```r
# augsynth (recommended -- Ben-Michael, Feller, Rothstein)
library(augsynth)
syn <- augsynth(y ~ treat, unit = unit, time = year, data = df)
summary(syn)
plot(syn)

# Synth (classic ADH)
library(Synth)
# Requires specific data preparation; see Synth documentation
```

---

## 6. Binscatter

Same authors across all three languages.

```stata
binsreg y x, nbins(20)
binsreg y x, controls(x2 x3)
```

```r
library(binsreg)
binsreg(y, x, data = df, nbins = 20)
binsreg(y, x, w = ~ x2 + x3, data = df, nbins = 20)
```

---

## 7. Ecosystem Mapping

| Method | Stata | R | Fidelity |
|--------|-------|---|----------|
| TWFE DiD | `reghdfe` | `feols()` | Very High |
| Sun-Abraham | `eventstudyinteract` | `feols(sunab())` | Very High |
| Callaway-Sant'Anna | `csdid` | `did::att_gt()` | Very High |
| de Chaisemartin-D'H | `did_multiplegt` | `DIDmultiplegt` | High |
| RD | `rdrobust` | `rdrobust` | Very High |
| PS matching | `teffects psmatch` | `MatchIt` | Very High |
| CEM | `cem` | `MatchIt(method="cem")` | Very High |
| AIPW | `teffects aipw` | `AIPW` / `lmtp` | High |
| Synthetic control | `synth` | `augsynth` / `Synth` | Very High |
| Binscatter | `binsreg` | `binsreg` | Very High |
| IV + FE | `ivreghdfe` | `feols()` | Very High |
