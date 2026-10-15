# Causal Inference: Stata to Python Translation

Stata is the dominant platform for applied causal inference in economics and
quantitative social science. Most influential methods papers ship Stata packages
first — `reghdfe`, `did_multiplegt`, `rdrobust`, `synth` — and Python ports
follow months to years later. Some never arrive. This creates a real translation
challenge: Stata users working with DAAF's Python stack will encounter methods
where the Python coverage ranges from "nearly identical API from the same
package project" to "no equivalent exists."

DAAF's Python stack covers the most common causal designs:
- **Difference-in-differences:** pyfixest (TWFE, did2s, lpdid, Sun-Abraham event_study)
- **Event studies:** pyfixest (i() operator, iplot, panelview)
- **Regression discontinuity:** rdrobust (same rdpackages project as the Stata version)
- **Instrumental variables:** pyfixest (with FE) and linearmodels (LIML, GMM)
- **Marginal effects / interpretation:** marginaleffects (same author as R version)
- **Synthetic control:** scpi (one package implemented in Python, R, and Stata; not the authors of Stata `synth`), CausalPy (Bayesian)
- **Binscatter:** binsreg (same nppackages project as the Stata `binsreg`; not the author of Stata `binscatter`)

This reference documents both what translates cleanly and where real gaps remain.

> **Versions referenced:**
> Python: pyfixest 0.60.0, rdrobust 1.3.0, marginaleffects 0.5.0 (all
> pre-installed).
> Stata: Stata 18 (SE/MP)
> See SKILL.md for the complete version table.

> **Package availability:** The `pip install X` lines throughout this reference are
> package-identity references, not instructions to run. Apart from the three
> pre-installed packages above (pyfixest, rdrobust, marginaleffects), the packages
> named here — including scpi, binsreg, csdid, rddensity, rdmulti, rdpower,
> pymatchit-causal, psmpy, pysmatch, SyntheticControlMethods, synthdid, and
> CausalPy — are **not** pre-installed in the DAAF container, and runtime installs
> are blocked (`pip install`/`uv add` are refused both at the command line and
> inside executed scripts — see CLAUDE.md § Runtime Package Installation). Before
> planning an analysis around any of them, verify availability with
> `pip show <pkg>` and, if it is absent, escalate to the user to add it to the
> Dockerfile (user additions block near the end) and rebuild before use.

> **Sources:** Cunningham, *Causal Inference: The Mixtape* (Yale, 2021);
> Huntington-Klein, *The Effect* (Chapman & Hall/CRC, 2022);
> Fischer et al., *pyfixest* (pyfixest.org, v0.60.0, accessed 2026-07-24);
> Cattaneo, Idrobo, & Titiunik, *A Practical Introduction to Regression
> Discontinuity Designs: Foundations* (Cambridge, 2020);
> Arel-Bundock, Greifer, & Heiss, "How to Interpret Statistical Models Using
> marginaleffects for R and Python" (*J. Statistical Software*, 2024;
> https://doi.org/10.18637/jss.v111.i09);
> Goodman-Bacon, "Difference-in-Differences with Variation in Treatment Timing"
> (*J. Econometrics*, 2021);
> de Chaisemartin & D'Haultfoeuille, "Two-Way Fixed Effects Estimators with
> Heterogeneous Treatment Effects" (*AER*, 2020)

---

## 1. Difference-in-Differences

### Traditional TWFE DiD

The simplest DiD design: all treated units adopt simultaneously. In this setting
TWFE is reasonable. Roth et al. (2023, Table 1) note that when everyone is
treated at the same time and the panel is balanced, TWFE specifications "yield
easily interpretable estimates"; with staggered timing, they advise considering
a heterogeneity-robust estimator and to "Use TWFE only if you’re confident in
treatment effect homogeneity." Modern estimators target the same parameter, though their
estimates need not be numerically identical (DAAF inference).

**Stata:**
```stata
* Method 1: Interaction operator
reg y treated##post, cluster(unit)

* Method 2: Explicit indicator + FE
reghdfe y treated_post, absorb(unit year) cluster(unit)

* Method 3: Community diff command
diff y, t(treated) p(post)
```

**Python (pyfixest):**
```python
import pyfixest as pf

# Method 1: Interaction
fit = pf.feols("y ~ treat:post | unit + time", data=df, vcov={"CRV1": "unit"})

# Method 2: Explicit indicator + FE (equivalent)
fit = pf.feols("y ~ treated_post | unit + year", data=df, vcov={"CRV1": "unit"})

fit.summary()
```

The formula syntax is nearly identical. The only difference is the clustering
syntax: Stata's `cluster(unit)` becomes pyfixest's `vcov={"CRV1": "unit"}`.

**When TWFE fails:** With staggered treatment timing and heterogeneous effects,
TWFE can produce severely biased estimates including sign reversals (Goodman-Bacon,
2021; de Chaisemartin & D'Haultfoeuille, 2020). Use one of the modern estimators
below for staggered designs.

### Two-Stage DiD (Gardner, 2022)

did2s imputes the counterfactual using only untreated observations, then estimates
treatment effects in a second stage. This avoids the negative weighting problem
of TWFE under treatment effect heterogeneity.

**Stata (`did2s`):**
```stata
did2s y, first_stage(i.unit i.time) second_stage(i.rel_time) treatment(treated) cluster(unit)
```

**Python (pyfixest):**
```python
fit = pf.did2s(
    data=df,
    yname="y",
    first_stage="~ 0 | unit + time",         # FE from untreated obs
    second_stage="~ i(rel_time, ref=-1)",     # Treatment effect spec
    treatment="treated",
    cluster="unit",
)
fit.summary()
fit.iplot()                                   # Event study plot
```

**Pooled ATT** (single treatment effect instead of event study):

**Stata:**
```stata
did2s y, first_stage(i.unit i.time) second_stage(treated) treatment(treated) cluster(unit)
```

**Python:**
```python
fit = pf.did2s(df, "y", "~ 0 | unit + time", "~ treated", "treated", "unit")
```

**Key differences:**
- Stata uses `first_stage()` and `second_stage()` options; Python uses string formula arguments
- Stata uses `cluster()` option; Python uses `cluster=` keyword
- Both return objects compatible with etable/iplot

### Callaway-Sant'Anna (2021)

Group-time ATTs that properly handle staggered adoption with doubly-robust
estimation.

**Stata (`csdid`):**
```stata
csdid y, ivar(unit_id) time(year) gvar(first_treat) method(dripw)
estat simple              * Overall ATT
estat event               * Dynamic event study
estat group               * Group-specific ATT
csdid_plot                * Event study visualization
```

**Python (`csdid` package):**
```python
# pip install csdid
from csdid import att_gt

out = att_gt(
    yname="y",
    tname="year",
    idname="unit_id",
    gname="first_treat",
    data=df,
    control_group="nevertreated",
    est_method="dr",                # Doubly robust
)
# API mirrors Stata csdid package; check csdid docs
# for current aggregation and plotting methods
```

**Coverage note:** The Python `csdid` package is a community port (d2cml-ai), not
an official release by Callaway & Sant'Anna. It aims to replicate the Stata API
but may lag behind on features and bug fixes. Verify results against Stata when
using for published research.

### Sun-Abraham Saturated Estimator

Fully saturates the model with cohort-by-period indicators, then aggregates.
This avoids the cross-lag "contamination" of dynamic TWFE coefficients when
treatment effects differ across adoption cohorts (Sun and Abraham 2021, as
summarized by Roth et al. 2023).

**Stata:**
```stata
* Using fixest-style sunab() in Stata:
* eventstudyinteract y lead_lag_vars, absorb(unit year) cohort(first_treat) control_cohort(never_treat)

* Or manual saturation:
reghdfe y ib(-1).rel_time, absorb(unit year) cluster(unit)
```

**Python (pyfixest):**
```python
fit = pf.event_study(
    data=df,
    yname="y",
    idname="unit",
    tname="period",
    gname="cohort",           # Year of treatment adoption
    estimator="saturated",    # Sun-Abraham
    att=False,                # False = dynamic event study
    cluster="unit",
)
fit.summary()
fit.iplot()

# Aggregate to overall ATT
agg = fit.aggregate(weighting="shares")
```

**Key difference:** Stata uses `sunab()` as a formula function or a separate
command. Python uses `pf.event_study()` with `estimator="saturated"`.
The underlying estimator is identical.

### Local Projections DiD (Dube et al., 2023)

Local projections estimated separately at each horizon (Jordà, 2005), combined with a "clean control" condition; can accommodate non-absorbing treatment (Dube et al., 2023).

**Stata:** `lpdid` (Busch and Girardi 2023, SSC; `ssc install lpdid`) implements
LP-DiD; local projections follow Jordà (2005).

**Python (pyfixest):**
```python
result = pf.lpdid(
    data=df,
    yname="y",
    idname="unit",
    tname="year",
    gname="treatment_year",
    att=True,                 # True = pooled ATT, False = period-specific
    pre_window=5,
    post_window=10,
    never_treated=0,          # Value of gname for never-treated units
)
# Important: lpdid() returns a DataFrame, NOT a Feols object
# result.summary() and result.iplot() will NOT work
```

**Important:** `lpdid()` returns a pandas DataFrame with columns for period,
estimate, std_error, ci_lower, ci_upper, etc. It cannot be passed to
`pf.etable()` or use `.iplot()`. Plot results manually with plotnine or
matplotlib.

### DiD Estimator Summary

| Stata | pyfixest | When to Use |
|-------|----------|-------------|
| `reghdfe y treated, absorb(unit year)` | `pf.feols("y ~ treated \| unit + year")` | Simultaneous adoption, balanced panel |
| `did2s` | `pf.did2s(...)` | Staggered; imputation-based |
| `csdid` | `csdid.att_gt(...)` | Staggered; group-time ATTs |
| `eventstudyinteract` / `sunab` | `pf.event_study(estimator="saturated")` | Staggered; fully saturated |
| `lpdid` (SSC) | `pf.lpdid(...)` | Flexible dynamics |
| `did_multiplegt` | **No Python equivalent** | de Chaisemartin-D'Haultfoeuille |

---

## 2. Event Studies

### Manual Event Study with i()

**Stata:**
```stata
* Create relative-time variable
gen rel_year = year - treatment_year

* Event study regression — omit t=-1 as reference
reghdfe y ib(-1).rel_year, absorb(unit year) cluster(unit)

* Plot (community-contributed)
coefplot, keep(*.rel_year) vertical
event_plot
```

**Python (pyfixest):**
```python
# Create relative-time variable
df["rel_year"] = df["year"] - df["treatment_year"]

# Event study with i() — omit t=-1 as reference
fit = pf.feols("y ~ i(rel_year, ref=-1) | unit + year", data=df,
               vcov={"CRV1": "unit"})

# Plot
fit.iplot()

# With joint confidence bands (Bonferroni + Scheffe)
fit.iplot(joint="both")
```

### Event Study Syntax Comparison

| Feature | Stata | pyfixest |
|---------|-------|----------|
| Reference level | `ib(-1).rel_year` | `i(rel_year, ref=-1)` |
| Plot | `coefplot` / `event_plot` | `fit.iplot()` |
| Joint bands | Varies by package | `fit.iplot(joint="both")` |
| Band types | Bonferroni | `"bonferroni"`, `"scheffe"`, or `"both"` |

### Unified Event Study Interface

pyfixest provides a single function that can run TWFE, did2s, or Sun-Abraham
event studies:

```python
# TWFE event study
fit_twfe = pf.event_study(
    data=df, yname="y", idname="unit", tname="year",
    gname="treatment_year", estimator="twfe", att=False, cluster="unit"
)

# did2s event study
fit_d2s = pf.event_study(
    data=df, yname="y", idname="unit", tname="year",
    gname="treatment_year", estimator="did2s", att=False, cluster="unit"
)

# Sun-Abraham event study
fit_sa = pf.event_study(
    data=df, yname="y", idname="unit", tname="year",
    gname="treatment_year", estimator="saturated", att=False, cluster="unit"
)

# Compare visually
pf.coefplot([fit_twfe, fit_d2s, fit_sa])
```

Stata does not have a single unified function for this — you must choose between
different commands (`reghdfe` + `i()`, `did2s`, `eventstudyinteract`).

### Treatment Pattern Visualization

**Stata:**
```stata
* panelview (if installed)
panelview y, i(unit) t(year) d(treated) type(treat)
```

**Python (pyfixest):**
```python
pf.panelview(data=df, unit="unit", time="year", treat="treated")
```

`panelview()` produces a heatmap showing treatment assignment across units and
time periods. This is built into pyfixest with no additional package needed.

---

## 3. Regression Discontinuity

All three implementations (Stata, R, Python) of rdrobust come from the
rdpackages project. The Stata software paper and CRAN package are by Calonico,
Cattaneo, Farrell, and Titiunik (Calonico et al. 2017); the pinned Python
package's metadata (rdrobust 1.3.0) lists Ricardo Masini as author, and the
current PyPI release (2.1.1) lists Calonico, Cattaneo, Farrell, Masini, and
Titiunik. The translation is nearly mechanical.

### Sharp RD

**Stata:**
```stata
rdrobust Y X, c(cutoff)
rdplot Y X, c(cutoff)
rdbwselect Y X, c(cutoff)
```

**Python:**
```python
# rdrobust is pre-installed in DAAF (pinned 1.3.0)
from rdrobust import rdrobust, rdplot, rdbwselect

# Point estimate with robust bias-corrected CI
rd = rdrobust(Y, X, c=cutoff)
print(rd)

# Data-driven RD plot
rdplot(Y, X, c=cutoff)

# Bandwidth selection
bw = rdbwselect(Y, X, c=cutoff)
print(bw)
```

### Fuzzy RD

**Stata:**
```stata
rdrobust Y X, c(cutoff) fuzzy(T)
```

**Python:**
```python
rd = rdrobust(Y, X, c=cutoff, fuzzy=T)
```

### Key Parameter Mapping

| Parameter | Stata | Python | Notes |
|-----------|-------|--------|-------|
| Outcome | `Y` (1st positional) | `Y` (1st positional) | Numpy array or Series |
| Running variable | `X` (2nd positional) | `X` (2nd positional) | Numpy array or Series |
| Cutoff | `c(0)` | `c=0` | Default is 0 |
| Kernel | `kernel(tri)` | `kernel="tri"` | `"tri"`, `"uni"`, `"epa"` |
| Bandwidth | `h(h_left h_right)` | `h=[h_left, h_right]` | Stata space-separated; Python list |
| Polynomial order | `p(1)` | `p=1` | Local linear is default |
| Fuzzy | `fuzzy(T)` | `fuzzy=T` | Treatment indicator |
| Covariates | `covs(c1 c2)` | `covs=covs_array` | Stata varlist; Python numpy array |
| Clustering | `cluster(cl)` | `cluster=cl` | Cluster variable |

The API is virtually identical. The main syntactic differences are Stata's
space-separated paired values vs Python's lists, and Stata's varlist vs numpy
arrays for covariates.

### Additional RD Packages (rdpackages Suite, Same API Across Languages)

| Tool | Stata Command | Python Package | Install |
|------|---------------|----------------|---------|
| Local polynomial RD | `rdrobust` | `rdrobust` | Pre-installed (1.3.0) |
| RD plots | `rdplot` | `rdrobust.rdplot()` | Included |
| Bandwidth selection | `rdbwselect` | `rdrobust.rdbwselect()` | Included |
| Manipulation testing | `rddensity` | `rddensity` | `pip install rddensity` |
| Multi-cutoff/score | `rdmulti` | `rdmulti` | `pip install rdmulti` |
| Power calculations | `rdpower` | `rdpower` | `pip install rdpower` |

The `rdpackages` suite (https://rdpackages.github.io/) collects these packages;
author lists differ by package, so check each package's own author list and
software paper. Translation is mechanical.

### Data Preparation Difference

The one meaningful difference is data handling. Stata reads from the in-memory
dataset; Python passes arrays explicitly:

**Stata:**
```stata
use "election_data.dta", clear
rdrobust vote_share margin, c(0)
```

**Python:**
```python
import polars as pl
df = pl.read_parquet("election_data.parquet")
Y = df["vote_share"].to_numpy()
X = df["margin"].to_numpy()
rd = rdrobust(Y, X, c=0)
```

---

## 4. Instrumental Variables (Causal Inference Context)

See also Section 4 of the companion `regression-modeling.md` for formula syntax
details. This section focuses on the causal inference aspects of IV.

### IV with Fixed Effects

**Stata:**
```stata
* Classic IV: education instrumented by college proximity
ivreghdfe log_wage experience (education = college_prox), absorb(state year) cluster(state)
```

**Python (pyfixest):**
```python
fit = pf.feols(
    "log_wage ~ experience | state + year | education ~ college_prox",
    data=df, vcov={"CRV1": "state"}
)
fit.IV_Diag()                        # First-stage F and effective F
fit._model_1st_stage.summary()       # First-stage results
```

### LIML and GMM

**Stata:**
```stata
ivregress liml y x_exog (x_endog = z1 z2)
ivregress gmm y x_exog (x_endog = z1 z2)
```

**Python (linearmodels):**
```python
from linearmodels.iv import IVLIML, IVGMM

fit_liml = IVLIML.from_formula("y ~ 1 + x_exog + [x_endog ~ z1 + z2]", data=df).fit()
fit_gmm = IVGMM.from_formula("y ~ 1 + x_exog + [x_endog ~ z1 + z2]", data=df).fit()
```

linearmodels has broader IV estimator coverage than the standard Stata `ivregress`
suite (LIML, GMM, CUE all in one package).

### Weak Instrument Testing

**Stata:**
```stata
ivregress 2sls y (x_endog = z1 z2), first
estat firststage
```

**Python (pyfixest):**
```python
fit = pf.feols("y ~ 1 | 0 | x_endog ~ z1 + z2", data=df)
fit.IV_Diag()    # First-stage F and effective F (Montiel Olea-Pflueger 2013)
```

pyfixest reports the Montiel Olea-Pflueger (2013) effective F-statistic, a
weak-instrument test for a linear IV model with one endogenous regressor that is
robust to heteroscedasticity, autocorrelation, and clustering; the Staiger-Stock
(1997) and Stock-Yogo (2005) pretests assume conditionally homoscedastic,
serially uncorrelated errors. Montiel Olea and Pflueger give a conservative TSLS rule of
thumb: reject the null of weak instruments when the effective F exceeds 23.1
(Nagar bias above 10% of a "worst-case" benchmark, 5% size).

---

## 5. Matching and Propensity Scores

This is a **significant gap** in the Python ecosystem relative to Stata's
built-in `teffects` suite.

### Stata's `teffects` Suite

```stata
* Propensity score matching
teffects psmatch (y) (treat x1 x2 x3)

* Inverse probability weighting
teffects ipw (y) (treat x1 x2 x3)

* Regression adjustment
teffects ra (y x1 x2 x3) (treat)

* Doubly-robust AIPW
teffects aipw (y x1 x2 x3) (treat x1 x2 x3)

* Community-contributed matching
psmatch2 treat x1 x2, outcome(y) neighbor(3)

* Coarsened exact matching
cem x1 x2 x3, treatment(treat)
```

### Python Alternatives (Fragmented)

| Stata | Python Equivalent | Fidelity | Notes |
|-------|------------------|----------|-------|
| `teffects psmatch` | `pymatchit-causal` or manual sklearn | Low-Medium | SEs do not account for estimated PS |
| `teffects ipw` | Manual: sklearn LogisticRegression + weighting | Low | Must implement manually |
| `teffects ra` | Manual: separate regressions + averaging | Low | |
| `teffects aipw` / `teffects ipwra` | `econml.dr.DRLearner` | Medium | Different implementation |
| `psmatch2` | `pymatchit-causal` or `psmpy` | Low-Medium | Community packages |
| `cem` | `pymatchit-causal` (CEM method) | Low-Medium | |

### Manual PSM in Python (Sketch)

```python
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
import numpy as np

# Estimate propensity scores
X = df[["x1", "x2", "x3"]].to_numpy()
treatment = df["treat"].to_numpy()
ps_model = LogisticRegression().fit(X, treatment)
ps = ps_model.predict_proba(X)[:, 1]

# Nearest-neighbor matching on propensity score
treated_ps = ps[treatment == 1].reshape(-1, 1)
control_ps = ps[treatment == 0].reshape(-1, 1)
nn = NearestNeighbors(n_neighbors=1)
nn.fit(control_ps)
distances, indices = nn.kneighbors(treated_ps)
```

This sketch lacks MatchIt/teffects' balance diagnostics, caliper options, exact
matching constraints, variance ratio checks, and (critically) correct standard
errors.

### The Standard Error Problem

Stata's `teffects psmatch` computes Abadie-Imbens standard errors that account
for the fact that propensity scores are estimated (Abadie & Imbens, 2016;
Stata's manual cites the 2012 NBER working-paper version). Python matching
packages generally do not offer this adjustment (DAAF assessment, not checked
package by package). Ignoring the adjustment does not uniformly make SEs too
small: for the ATE the adjustment reduces the asymptotic variance, so unadjusted
SEs tend to be too large; for the ATT the adjustment need not reduce it (Abadie &
Imbens, 2016; checked against the 2009 NBER working-paper version). For
published research using propensity score matching, consider estimating with
Stata's `teffects psmatch`.

### Available Python Matching Packages

| Package | Install | Methods | Quality |
|---------|---------|---------|---------|
| `pymatchit-causal` | `pip install pymatchit-causal` | Nearest neighbor, optimal, exact, CEM | Medium (port of R MatchIt) |
| `psmpy` | `pip install psmpy` | PS matching via k-NN | Medium (academic) |
| `pysmatch` | `pip install pysmatch` | Gradient-based propensity matching | Fair |
| Manual sklearn | Pre-installed | LogisticRegression + NearestNeighbors | Requires manual implementation |

---

## 6. Synthetic Control

### Classic Synthetic Control (Abadie-Diamond-Hainmueller)

**Stata:**
```stata
synth depvar predictor1 predictor2, trunit(treated_id) trperiod(treatment_year)
```

**Python (scpi — recommended):**
```python
# pip install scpi
import scpi

# scpi (by Cattaneo, Feng, Palomba, Titiunik) provides prediction intervals
# and uncertainty quantification; scpi is also implemented in R and Stata
```

**Python (SyntheticControlMethods — community):**
```python
# pip install SyntheticControlMethods
from SyntheticControlMethods import Synth

sc = Synth(df, "outcome", "unit_id", "time", treatment_id, treatment_time)
sc.fit()
sc.path_plot()
```

**Python (CausalPy — Bayesian alternative):**
```python
# pip install CausalPy
import causalpy as cp

result = cp.SyntheticControl(
    df,
    treatment_time=treatment_time,
    formula="y ~ 0 + x1 + x2",
    model=cp.pymc_models.WeightedSumFitter(),
)
result.plot()
```

### Synthetic Control Package Comparison

| Stata | Python Equivalent | Install | Fidelity | Notes |
|-------|------------------|---------|----------|-------|
| `synth` | `scpi` | `pip install scpi` | High | Different authors from Stata `synth` (scpi: Cattaneo, Feng, Palomba, Titiunik); includes prediction intervals |
| `synth` | `SyntheticControlMethods` | `pip install SyntheticControlMethods` | Medium | Community; classic ADH estimator |
| `synth_runner` | No direct equivalent | N/A | **Gap** | Automated inference for synth |
| N/A | `CausalPy` | `pip install CausalPy` | Different methodology | Bayesian SC (PyMC) |
| N/A | `synthdid` | `pip install synthdid` | Medium | Synthetic DiD (Arkhangelsky et al.) |

The `scpi` package provides prediction intervals and uncertainty quantification;
its JSS paper describes it as "the first package to offer uncertainty
quantification using prediction intervals with random potential outcomes"
(Cattaneo, Feng, Palomba, and Titiunik 2025).

---

## 7. Binscatter

### binsreg (Same Project Across Languages)

**Stata:**
```stata
* Community-contributed
binsreg y x, nbins(20)
binsreg y x, nbins(20) controls(x2 x3)
binscatter y x, controls(x2 x3)
```

**Python:**
```python
# pip install binsreg
import binsreg

# Basic binscatter
binsreg.binsreg(y=df["y"].to_numpy(), x=df["x"].to_numpy(), nbins=20)

# With controls
binsreg.binsreg(
    y=df["y"].to_numpy(),
    x=df["x"].to_numpy(),
    w=df[["x2", "x3"]].to_numpy(),
    nbins=20,
)
```

The `binsreg` package comes from one nppackages project across Stata, R, and
Python (CRAN lists Cattaneo, Crump, Farrell, and Feng; PyPI also lists Ricardo
Masini). The Python API closely mirrors the Stata syntax. The main
difference is that Stata reads from the in-memory dataset while Python requires
explicit numpy arrays.

---

## 8. Other Causal Tools

### Survival Analysis / Duration Models

**Stata:**
```stata
stset time, failure(event)
stcox x1 x2, strata(group)
sts graph
```

**Python:**
```python
# pip install lifelines
# DAAF note: lifelines is NOT installable here — its latest release (0.30.3)
# requires pandas<3.0, incompatible with the pinned pandas 3.0.0 (see Dockerfile).
# Use R's pre-installed survival::coxph() for survival analysis instead.
from lifelines import CoxPHFitter

cph = CoxPHFitter()
cph.fit(df_pd, duration_col="time", event_col="event",
        formula="x1 + x2 + strata(group)")
cph.print_summary()
cph.plot()
```

`lifelines` is mature and well-maintained. It covers Cox PH, Kaplan-Meier,
Nelson-Aalen, and parametric survival models. However, in DAAF it cannot be
installed: its latest release (0.30.3) requires `pandas<3.0`, which conflicts
with the pinned pandas 3.0.0. The working route for survival analysis is R's
pre-installed `survival` package.

### Bayesian Causal Impact (Time Series Intervention)

**Stata:** No direct equivalent. Some users implement manually or use R's
`CausalImpact` via `rcall`.

**Python:**
```python
# pip install CausalPy
import causalpy as cp

result = cp.InterruptedTimeSeries(
    df,
    treatment_time=treatment_time,
    formula="y ~ 1 + t",
    model=cp.pymc_models.LinearRegression(),
)
result.plot()
```

### Dynamic Panel GMM

**Stata:**
```stata
xtabond y L.y x1 x2, lags(2) vce(robust)
xtdpd y L(1/2).y x1 x2, dgmmiv(y) lgmmiv(y) vce(robust)
xtabond2 y L.y x1 x2, gmm(L.y) iv(x1 x2)
```

**Python:** **Limited support.** linearmodels does not implement Arellano-Bond or
Blundell-Bond GMM estimators. This is a significant gap for researchers working
with dynamic panel models.

Partial workaround: implement the first-differenced IV approach manually using
`pyfixest` or `linearmodels.IV2SLS` with lagged instruments, but this does not
replicate `xtabond2`'s full functionality (sequential moment conditions, Windmeijer
correction, Sargan/Hansen tests for over-identification).

---

## 9. Coverage Gaps: Honest Assessment

### What Stata Has That Python Lacks

| Stata Command | Gap Description | Severity | Best Workaround |
|---------------|-----------------|----------|-----------------|
| `did_multiplegt` | de Chaisemartin & D'Haultfoeuille estimators | **High** | No Python port; use Stata or R |
| `teffects` suite | Unified treatment effects framework with correct SEs | **High** | Manual implementation; verify SEs carefully |
| `teffects psmatch` SE correction | SEs accounting for estimated propensity scores | **High** | Run matching in Stata/R; import matched data |
| `teffects ipwra` / `teffects aipw` | Doubly-robust AIPW with correct SEs | **High** | `econml.dr.DRLearner` (different implementation) |
| `xtabond` / `xtabond2` / `xtdpd` | Dynamic panel GMM (Arellano-Bond, Blundell-Bond) | **High** | No adequate Python equivalent |
| `feglm` / GLM + high-dim FE | pyfixest `feglm()` covers logit/probit/gaussian FE-GLMs since 0.50; Gamma and negative-binomial FE-GLMs still unported | **Low** | Direct `pf.feglm()` for logit/probit/gaussian; R fixest for Gamma/negbin |
| `synth_runner` | Automated SC inference and placebo tests | **Medium** | Manual iteration; `scpi` for prediction intervals |
| `psmatch2` balance diagnostics | Balance tables, variance ratios | **Medium** | Manual computation |
| `cem` (coarsened exact matching) | Limited Python coverage | **Medium** | `pymatchit-causal` partial support |

### What Python Does Better

| Capability | Python Advantage | Notes |
|-----------|-----------------|-------|
| `pf.event_study()` | Unified interface for TWFE/did2s/Sun-Abraham | Stata requires different commands for each |
| `pf.panelview()` | Built-in treatment pattern visualization | Stata requires separate install |
| LIML/GMM estimators | `linearmodels` has LIML, GMM, CUE in one package | Stata `ivregress` has 2SLS/LIML/GMM but less unified |
| Multiple model objects | Models coexist as variables | Stata has one active `e()` result |
| Reproducible pipelines | DAAF's file-first execution model | Stata do-files have no immutable audit trail |

---

## 10. Ecosystem Mapping Table

| Method | Stata | Python | Fidelity | Notes |
|--------|-------|--------|----------|-------|
| **TWFE DiD** | `reghdfe` | `pf.feols()` | Very High | Cluster SE syntax only |
| **did2s** | `did2s` | `pf.did2s()` | Very High | Arg names differ |
| **Sun-Abraham** | `eventstudyinteract` | `pf.event_study(est="saturated")` | High | Different API, same estimator |
| **Callaway-Sant'Anna** | `csdid` | `csdid.att_gt()` | Medium | Community port |
| **LP-DiD** | `lpdid` (SSC) | `pf.lpdid()` | Medium | Both languages have packages |
| **de Chaisemartin-D'Haultfoeuille** | `did_multiplegt` | **No equivalent** | N/A | **Gap** |
| **Event study (iplot)** | `coefplot` / `event_plot` | `fit.iplot()` | Very High | Method vs command |
| **RD (sharp/fuzzy)** | `rdrobust` | `rdrobust` | Very High | Same rdpackages project |
| **RD plots** | `rdplot` | `rdrobust.rdplot()` | Very High | Same rdpackages project |
| **RD density test** | `rddensity` | `rddensity` | Very High | Same rdpackages project |
| **IV + FE** | `ivreghdfe` | `pf.feols()` | Very High | Three-part formula |
| **IV (2SLS, no FE)** | `ivregress 2sls` | `linearmodels.IV2SLS()` | High | Formula syntax differs |
| **LIML** | `ivregress liml` | `linearmodels.IVLIML()` | High | |
| **GMM-IV** | `ivregress gmm` | `linearmodels.IVGMM()` | High | |
| **PS matching** | `teffects psmatch` | `pymatchit-causal` / manual | Low | **SE gap** |
| **IPW** | `teffects ipw` | Manual sklearn + weighting | Low | **SE gap** |
| **AIPW** | `teffects aipw` | `econml.dr.DRLearner` | Medium | Different implementation |
| **Synthetic control** | `synth` | `scpi` | High | Different authors from Stata `synth` |
| **Binscatter** | `binsreg` / `binscatter` | `binsreg` | Very High | Same nppackages project as Stata `binsreg` (`binscatter` is a different author's command) |
| **Survival/Cox** | `stcox` | `lifelines.CoxPHFitter()` | High | Not installable in DAAF (needs pandas<3.0); use R `survival` |
| **Dynamic panel GMM** | `xtabond2` | **No equivalent** | N/A | **Gap** |
| **Marginal effects** | `margins` | `marginaleffects` | High | Same author (R version); Python port announced as "alpha" in July 2023 (pinned 0.5.0) |

### Fidelity Legend

- **Very High:** Same or near-identical API (for rdrobust/binsreg, the same rdpackages/nppackages project across languages), or results match to high precision
- **High:** Reliable implementation with minor syntax differences; results match
- **Medium:** Community port or different implementation; verify results for published work
- **Low:** Partial coverage; significant feature gaps or SE issues
- **N/A:** No equivalent available

> **Sources:** Cunningham, *Causal Inference: The Mixtape* (Yale, 2021), ch. 5-10
> (1st edition);
> Huntington-Klein, *The Effect* (Chapman & Hall/CRC, 2022; online 2nd ed.,
> Chs. 14, 16-21);
> Gardner, "Two-Stage Differences in Differences" (arXiv:2207.05943, 2022);
> Callaway & Sant'Anna, "Difference-in-Differences with Multiple Time Periods"
> (*J. Econometrics*, 2021);
> Sun & Abraham, "Estimating Dynamic Treatment Effects in Event Studies with
> Heterogeneous Treatment Effects" (*J. Econometrics*, 2021);
> Roth, J., Sant'Anna, P.H.C., Bilinski, A., and Poe, J. (2023). "What's Trending in Difference-in-Differences?" *Journal of Econometrics*, 235(2), 2218-2244. https://doi.org/10.1016/j.jeconom.2023.03.008;
> Dube, Girardi, Jordà, & Taylor, "A Local Projections Approach to
> Difference-in-Differences" (NBER WP 31184, 2023);
> Jordà, Ò. (2005). "Estimation and Inference of Impulse Responses by Local
> Projections." *American Economic Review*.
> https://doi.org/10.1257/0002828053828518;
> Busch & Girardi, "LPDID: Stata module implementing Local Projections
> Difference-in-Differences (LP-DiD) estimator" (Statistical Software
> Components S459273, Boston College Department of Economics, 2023);
> Cattaneo, Idrobo, & Titiunik, *A Practical Introduction to Regression
> Discontinuity Designs: Foundations* (Cambridge, 2020);
> Calonico, Cattaneo, Farrell, & Titiunik, "rdrobust: Software for
> Regression-discontinuity Designs" (*Stata Journal*, 2017);
> Cattaneo, M.D., Feng, Y., Palomba, F., and Titiunik, R. (2025). "scpi:
> Uncertainty Quantification for Synthetic Control Methods." *Journal of
> Statistical Software*, 113(1), 1-38. https://doi.org/10.18637/jss.v113.i01;
> Abadie, Diamond, & Hainmueller, "Synthetic Control Methods for Comparative
> Case Studies: Estimating the Effect of California's Tobacco Control Program"
> (*JASA*, 2010);
> Arkhangelsky, D., Athey, S., Hirshberg, D.A., Imbens, G.W., and Wager, S.
> (2021). "Synthetic Difference-in-Differences." *American Economic Review*,
> 111(12), 4088-4118. https://doi.org/10.1257/aer.20190159;
> Abadie & Imbens, "Matching on the Estimated Propensity Score" (*Econometrica*,
> 2016);
> Montiel Olea, J.L., & Pflueger, C. (2013). "A Robust Test for Weak
> Instruments." *Journal of Business & Economic Statistics*, 31(3), 358-369.
> https://doi.org/10.1080/00401706.2013.806694;
> Staiger, D. and Stock, J.H. (1997). "Instrumental Variables Regression with
> Weak Instruments." *Econometrica*, 65(3), 557-586;
> Stock, J.H. and Yogo, M. (2005). "Testing for Weak Instruments in Linear IV
> Regression." In Andrews, D.W.K. and Stock, J.H. (Eds.), *Identification and
> Inference for Econometric Models*, 80-108. Cambridge University Press;
> de Chaisemartin & D'Haultfoeuille, "Two-Way Fixed Effects Estimators with
> Heterogeneous Treatment Effects" (*AER*, 2020);
> Goodman-Bacon, "Difference-in-Differences with Variation in Treatment Timing"
> (*J. Econometrics*, 2021);
> Arel-Bundock, "marginaleffects" (marginaleffects.com, accessed 2026-03-28);
> Fischer et al., *pyfixest* (pyfixest.org, v0.60.0, accessed 2026-07-24);
> Naqvi, "DiD estimator comparison" (asjadnaqvi.github.io/DiD);
> Stata `teffects` manual (stata.com/manuals/causal.pdf)
