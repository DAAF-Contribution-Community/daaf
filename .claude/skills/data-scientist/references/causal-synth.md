# Synthetic Control Methods

Implementation reference for synthetic control methods (SCM) and synthetic
difference-in-differences (SDID) in Python. Covers manual implementation with
scipy (always available), plus four installable packages for production use.

For methodology fundamentals (when to use SC, comparison with other designs,
threats to validity), see `./causal-inference.md` > "Synthetic Control: Core
Principles" and the Method Selection Guide.

## Contents

- [When to Use Synthetic Control](#when-to-use-synthetic-control)
- [Package Landscape](#package-landscape)
- [Manual Implementation (scipy)](#manual-implementation-scipy)
- [pysyncon (Recommended Primary)](#pysyncon-recommended-primary)
- [synthdid (Synthetic Difference-in-Differences)](#synthdid-synthetic-difference-in-differences)
- [scpi-pkg (Formal Prediction Intervals)](#scpi-pkg-formal-prediction-intervals)
- [CausalPy (Bayesian Approach)](#causalpy-bayesian-approach)
- [Inference for Synthetic Controls](#inference-for-synthetic-controls)
- [How SDID Differs from Classic SCM](#how-sdid-differs-from-classic-scm)
- [Gotchas and Pitfalls](#gotchas-and-pitfalls)
- [Decision Tree: Which Approach?](#decision-tree-which-approach)
- [References](#references)

## When to Use Synthetic Control

Synthetic control is designed for a specific research setting:

| Condition | Requirement |
|-----------|-------------|
| Number of treated units | Small (often 1, sometimes 2-5) |
| Pre-treatment periods | Many (long pre-treatment panel) |
| Donor pool | Sufficient untreated units to construct a credible match |
| Treatment effect size | Large enough to distinguish from noise in placebo distribution |
| Outcome data | Aggregate-level (state, region, country) panel data |

Classic examples: effect of a policy change in one state, impact of an event on
one country, consequence of a merger for one firm.

**When NOT to use SC:**
- Many treated units with short pre-periods -- use DiD instead (see
  `pyfixest` skill's `difference-in-differences.md`)
- Micro-level individual data with standard treatment/control -- use matching,
  regression, or DiD
- No credible donor pool (treated unit is too unique to approximate)

## Package Landscape

**No synthetic control package is currently installed in the DAAF environment.**
The manual scipy implementation below works with installed dependencies. All
package-based approaches require user installation.

| Package | Install | Strengths | Best For |
|---------|---------|-----------|----------|
| **pysyncon** | `pip install pysyncon` | Closest to Abadie et al.; placebo tests; conformal CI | General SCM work |
| **synthdid** | `pip install synthdid` | Arkhangelsky et al. SDID; staggered designs | SDID estimation |
| **scpi-pkg** | `pip install scpi` | Rigorous prediction intervals (Cattaneo et al.) | Formal inference |
| **CausalPy** | `pip install CausalPy` | Bayesian uncertainty via PyMC | Bayesian SC |
| *scipy (manual)* | *Already installed* | No install needed; full control | Fallback; learning |

## Manual Implementation (scipy)

This implementation uses only `scipy.optimize` and `numpy`, both of which are
installed. It implements the classic Abadie, Diamond, and Hainmueller (2010)
nested optimization.

### Data Setup

SC requires panel data in a specific structure: outcomes and predictors for one
treated unit and J donor (control) units across T time periods, with T0
pre-treatment periods.

```python
import numpy as np
import polars as pl
from scipy.optimize import minimize

# --- Config ---
TREATED_UNIT = "California"
TREATMENT_YEAR = 2000
OUTCOME_COL = "outcome"
UNIT_COL = "state"
TIME_COL = "year"

# --- Load ---
df = pl.read_parquet("path/to/panel_data.parquet")

# Separate pre-treatment and post-treatment periods
pre_periods = [y for y in df[TIME_COL].unique().sort().to_list() if y < TREATMENT_YEAR]
post_periods = [y for y in df[TIME_COL].unique().sort().to_list() if y >= TREATMENT_YEAR]

# Identify donor units (all units except treated)
all_units = df[UNIT_COL].unique().sort().to_list()
donor_units = [u for u in all_units if u != TREATED_UNIT]
J = len(donor_units)

# Build outcome matrices: rows = time periods, columns = units
# X1 = treated unit pre-treatment outcomes (T0 x 1)
# X0 = donor units pre-treatment outcomes (T0 x J)
pre_df = df.filter(pl.col(TIME_COL).is_in(pre_periods))

X1 = (pre_df.filter(pl.col(UNIT_COL) == TREATED_UNIT)
      .sort(TIME_COL)[OUTCOME_COL].to_numpy().reshape(-1, 1))

X0 = np.column_stack([
    pre_df.filter(pl.col(UNIT_COL) == donor)
    .sort(TIME_COL)[OUTCOME_COL].to_numpy()
    for donor in donor_units
])

# Post-treatment outcomes for gap calculation
post_df = df.filter(pl.col(TIME_COL).is_in(post_periods))

Y1 = (post_df.filter(pl.col(UNIT_COL) == TREATED_UNIT)
      .sort(TIME_COL)[OUTCOME_COL].to_numpy())

Y0 = np.column_stack([
    post_df.filter(pl.col(UNIT_COL) == donor)
    .sort(TIME_COL)[OUTCOME_COL].to_numpy()
    for donor in donor_units
])

print(f"Treated unit: {TREATED_UNIT}")
print(f"Donor pool: {J} units")
print(f"Pre-treatment periods: {len(pre_periods)}")
print(f"Post-treatment periods: {len(post_periods)}")
```

### The Nested Optimization

Classic SCM solves a nested optimization problem:

- **Outer problem:** Find diagonal weight matrix V (predictor importance weights)
  that minimizes the post-treatment prediction error on a hold-out portion of the
  pre-treatment period, or more commonly minimizes the pre-treatment RMSPE
- **Inner problem:** Given V, find unit weights W that minimize the V-weighted
  distance between treated and synthetic control pre-treatment predictors,
  subject to W >= 0 and sum(W) = 1

The simplified version below optimizes W directly on pre-treatment outcomes
(equivalent to setting V = I when predictors are the outcome time series). This
is the most common approach when the primary matching variable is the outcome
trajectory itself.

```python
# --- Inner optimization: find W given V ---
# Simplified: match on pre-treatment outcome trajectory directly
# Objective: minimize ||X1 - X0 @ w||^2

def sc_objective(w, X0, X1):
    """Squared prediction error for synthetic control weights."""
    synth = X0 @ w.reshape(-1, 1)
    return float(np.sum((X1 - synth) ** 2))

# Constraints: weights sum to 1, each weight >= 0
constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
bounds = [(0.0, 1.0)] * J

# Initial weights: equal across all donors
w0 = np.ones(J) / J

# Solve
result = minimize(
    sc_objective,
    w0,
    args=(X0, X1),
    method="SLSQP",
    bounds=bounds,
    constraints=constraints,
    options={"maxiter": 1000, "ftol": 1e-12},
)

w_star = result.x
print(f"Optimization success: {result.success}")
print(f"Pre-treatment RMSPE: {np.sqrt(result.fun / len(pre_periods)):.4f}")

# Display non-trivial weights
for i, donor in enumerate(donor_units):
    if w_star[i] > 0.001:
        print(f"  {donor}: {w_star[i]:.4f}")
```

### Full Nested Optimization with V Weights

When matching on multiple predictors (not just the outcome trajectory), the full
nested optimization is needed. V weights determine the relative importance of
each predictor in constructing the synthetic control.

```python
# --- Full nested optimization with predictor importance (V) weights ---
# Predictors: pre-treatment outcome averages over different sub-periods,
# plus covariates like GDP, population, etc.

# Build predictor matrices (K predictors x 1 for treated, K x J for donors)
# Example: use outcome means over sub-periods as predictors
period_splits = [pre_periods[:len(pre_periods)//2], pre_periods[len(pre_periods)//2:]]

def build_predictor_matrices(df, unit_col, time_col, outcome_col,
                             treated, donors, period_splits):
    """Build K x 1 (treated) and K x J (donors) predictor matrices."""
    Z1_list = []
    Z0_list = []
    for periods in period_splits:
        sub = df.filter(pl.col(time_col).is_in(periods))
        treated_mean = (sub.filter(pl.col(unit_col) == treated)
                        [outcome_col].mean())
        Z1_list.append(treated_mean)
        donor_means = [
            sub.filter(pl.col(unit_col) == d)[outcome_col].mean()
            for d in donors
        ]
        Z0_list.append(donor_means)
    Z1 = np.array(Z1_list).reshape(-1, 1)
    Z0 = np.array(Z0_list)
    return Z1, Z0

Z1, Z0 = build_predictor_matrices(
    pre_df, UNIT_COL, TIME_COL, OUTCOME_COL,
    TREATED_UNIT, donor_units, period_splits,
)
K = Z1.shape[0]

def inner_w(V_diag, Z0, Z1):
    """Solve for W given V (predictor importance weights)."""
    V = np.diag(V_diag)

    def obj_w(w):
        diff = Z1 - Z0 @ w.reshape(-1, 1)
        return float(np.squeeze(diff.T @ V @ diff))

    res = minimize(obj_w, np.ones(J) / J, method="SLSQP",
                   bounds=[(0, 1)] * J,
                   constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1})
    return res.x

def outer_v(V_diag, X0, X1, Z0, Z1):
    """Outer objective: pre-treatment outcome fit given optimal W(V)."""
    w = inner_w(V_diag, Z0, Z1)
    synth = X0 @ w.reshape(-1, 1)
    return float(np.sum((X1 - synth) ** 2))

# Optimize V (normalize to sum to 1 for identifiability)
v0 = np.ones(K) / K
res_v = minimize(
    outer_v, v0, args=(X0, X1, Z0, Z1),
    method="SLSQP",
    bounds=[(0, 1)] * K,
    constraints={"type": "eq", "fun": lambda v: np.sum(v) - 1},
    options={"maxiter": 500},
)

V_star = res_v.x
W_star = inner_w(V_star, Z0, Z1)
print(f"V weights (predictor importance): {V_star}")
print(f"Outer optimization success: {res_v.success}")
```

### Computing Treatment Effects and Gaps

```python
# --- Treatment effect: gap between treated and synthetic control ---
synth_pre = X0 @ w_star
synth_post = Y0 @ w_star

gap_pre = X1.flatten() - synth_pre
gap_post = Y1 - synth_post

pre_rmspe = np.sqrt(np.mean(gap_pre ** 2))
post_rmspe = np.sqrt(np.mean(gap_post ** 2))

print(f"Pre-treatment RMSPE: {pre_rmspe:.4f}")
print(f"Post-treatment RMSPE: {post_rmspe:.4f}")
print(f"RMSPE ratio (post/pre): {post_rmspe / pre_rmspe:.2f}")
print(f"Average post-treatment gap (ATT): {np.mean(gap_post):.4f}")

# Year-by-year gaps
for i, year in enumerate(post_periods):
    print(f"  {year}: gap = {gap_post[i]:.4f}")
```

### Plotting (manual)

```python
import plotnine as p9

# Combine treated and synthetic series for plotting
all_periods = pre_periods + post_periods
treated_series = np.concatenate([X1.flatten(), Y1])
synth_series = np.concatenate([synth_pre, synth_post])

plot_df = pl.DataFrame({
    "year": all_periods * 2,
    "value": np.concatenate([treated_series, synth_series]).tolist(),
    "series": ["Treated"] * len(all_periods) + ["Synthetic"] * len(all_periods),
})

# Path plot: treated vs synthetic
path_plot = (
    p9.ggplot(plot_df, p9.aes(x="year", y="value", color="series"))
    + p9.geom_line(size=1)
    + p9.geom_vline(xintercept=TREATMENT_YEAR, linetype="dashed", alpha=0.5)
    + p9.labs(x="Year", y=OUTCOME_COL, color="",
              title=f"Synthetic Control: {TREATED_UNIT}")
    + p9.theme_minimal()
)

# Gap plot: treatment effect over time
gap_df = pl.DataFrame({
    "year": all_periods,
    "gap": np.concatenate([gap_pre, gap_post]).tolist(),
})

gap_plot = (
    p9.ggplot(gap_df, p9.aes(x="year", y="gap"))
    + p9.geom_line(size=1)
    + p9.geom_hline(yintercept=0, linetype="dashed", alpha=0.5)
    + p9.geom_vline(xintercept=TREATMENT_YEAR, linetype="dashed", alpha=0.5)
    + p9.labs(x="Year", y="Gap (Treated - Synthetic)",
              title=f"Treatment Effect: {TREATED_UNIT}")
    + p9.theme_minimal()
)
```

## pysyncon (Recommended Primary)

**Install:** `pip install pysyncon`

pysyncon is the closest Python implementation to the original Abadie, Diamond,
and Hainmueller Synth package. It provides a structured API for data preparation,
estimation, placebo testing, and conformal inference.

### Data Preparation

```python
from pysyncon import Dataprep, Synth

# Dataprep configures the SC problem
dataprep = Dataprep(
    foo=df,                                    # DataFrame (pandas or polars)
    predictors=["gdp", "population", "trade"], # Covariates to match on
    predictors_op="mean",                      # Aggregation for predictors
    time_predictors_prior=[1980, 1990],        # Period range for predictor matching
    special_predictors=[                        # Outcome at specific periods
        ("outcome", [1985], "mean"),
        ("outcome", [1990], "mean"),
        ("outcome", [1995], "mean"),
    ],
    dependent="outcome",                       # Outcome variable
    unit_variable="unit_name",                 # Unit identifier column
    time_variable="year",                      # Time column
    treatment_identifier="California",         # Treated unit value
    controls_identifier=["Nevada", "Oregon", "Washington", ...],  # Donors
    time_optimize_ssr=[1980, 1999],           # Pre-treatment period for fitting
)
```

**Parameter notes:**
- `predictors_op` aggregates covariates over `time_predictors_prior` (usually "mean")
- `special_predictors` allows matching the outcome at specific time points --
  this is often more important than covariate matching for pre-treatment fit
- `time_optimize_ssr` defines the period over which the pre-treatment fit is
  optimized -- typically the full pre-treatment period

### Estimation

```python
synth = Synth()
synth.fit(
    dataprep=dataprep,
    optim_method="Nelder-Mead",   # Optimization method (default)
    optim_initial="equal",        # Starting weights (default: equal)
)

# Key results
print(synth.weights())           # Donor unit weights (W)
print(synth.summary())           # Predictor balance table
print(synth.mspe())              # Pre-treatment mean squared prediction error
print(synth.att())               # Average treatment effect on treated

# Detailed gap by period
gaps = synth.att(time_period="all")
```

### Visualization

```python
# Path plot: treated vs synthetic
synth.path_plot(
    time_period=[1980, 2010],     # Full time range
    treatment_time=2000,          # Vertical line at treatment
)

# Gap plot: treatment effect over time
synth.gaps_plot(
    time_period=[1980, 2010],
    treatment_time=2000,
)
```

### Placebo Tests (In-Space)

In-space placebos iteratively apply the SC method to each control unit as if it
were treated. The treated unit's gap is then compared to the distribution of
placebo gaps.

```python
from pysyncon import PlaceboTest

placebo = PlaceboTest()
placebo.fit(dataprep=dataprep, synth=synth)

# Gap plot with placebos (gray lines = placebos, black = treated)
placebo.gaps_plot(
    time_period=[1980, 2010],
    treatment_time=2000,
    mspe_threshold=5,             # Exclude placebos with pre-RMSPE > 5x treated
)

# p-value from placebo distribution
print(f"Placebo p-value: {placebo.pvalue():.4f}")
```

The `mspe_threshold` parameter filters out placebos with poor pre-treatment fit
(pre-RMSPE more than N times the treated unit's). This prevents units that
cannot be well-matched from inflating the placebo distribution. Common values:
2-5 (Abadie et al. 2010 used 2; 5 is more conservative/inclusive).

### Conformal Inference

Chernozhukov, Wuthrich, and Zhu (2021) conformal inference provides
finite-sample valid confidence intervals without distributional assumptions.

```python
# Conformal confidence intervals
ci = synth.confidence_interval(
    alpha=0.05,                    # 95% CI
    time_periods=[2000, 2001, 2002, 2003, 2004, 2005],
)
print(ci)
```

## synthdid (Synthetic Difference-in-Differences)

**Install:** `pip install synthdid`

synthdid implements the Arkhangelsky, Athey, Hirshberg, Imbens, and Wager (2021)
estimator, which combines synthetic control unit weights with DiD-style time
weights and additive unit fixed effects.

### Basic SDID Estimation

```python
from synthdid.synthdid import Synthdid as sdid

# Input: long-format panel DataFrame
# Required columns: unit identifier, time period, treatment indicator, outcome
result = sdid(
    df,
    unit="state",           # Unit identifier column
    time="year",            # Time period column
    treatment="treated",    # Binary treatment indicator (0/1)
    outcome="outcome",      # Outcome variable
)

# Fit the model, then compute variance
result.fit(cov_method="optimized")
result.vcov(method="placebo", n_reps=50)

# Access results via summary table
summary = result.summary().summary2
print(summary)  # Columns: ATT, Std. Err., t, P>|t|, [0.025, 0.975]
```

Note: The `Synthdid` class uses method chaining — `.fit()` and `.vcov()` return
the object itself. Results are accessed through `.summary().summary2`, not through
individual attributes.

### Inference

SDID supports multiple variance estimation methods via `.vcov()`:

```python
# Placebo-based variance (recommended for few treated units)
result.vcov(method="placebo", n_reps=50)
print(result.summary().summary2)

# Bootstrap variance
result.vcov(method="bootstrap", n_reps=200)
print(result.summary().summary2)

# Jackknife variance
result.vcov(method="jackknife")
print(result.summary().summary2)
```

### Staggered and Block Designs

synthdid supports designs where multiple units receive treatment at different times:

```python
# Staggered adoption: treatment indicator already encodes timing
# (treated[i,t] = 1 for unit i in periods after their adoption date)
result_stag = sdid(
    df_staggered,
    unit="state",
    time="year",
    treatment="treated",
    outcome="outcome",
).fit(cov_method="optimized").vcov(method="placebo")
```

### SDID Visualization

```python
# The result object provides outcome trajectory and weight plots
result.plot_outcomes()          # Treated vs synthetic outcome paths
result.plot_weights()           # Unit and time weight distributions
```

## scpi-pkg (Formal Prediction Intervals)

**Install:** `pip install scpi`

scpi-pkg (Cattaneo, Feng, Palomba, and Titiunik 2025) is the only package that
provides rigorous prediction intervals that account for both in-sample
uncertainty (estimation of weights) and out-of-sample uncertainty (prediction of
future outcomes).

### Core API

```python
from scpi_pkg.scdata import scdata
from scpi_pkg.scest import scest
from scpi_pkg.scpi import scpi
from scpi_pkg.scplot import scplot

# Step 1: Prepare data
data = scdata(
    df=df,
    id_var="unit",
    time_var="year",
    outcome_var="outcome",
    period_pre=[1980, 1999],     # Pre-treatment periods
    period_post=[2000, 2010],    # Post-treatment periods
    unit_tr="California",        # Treated unit
    unit_co=donor_list,          # Control units
    features={"outcome": range(1980, 2000)},  # Features for matching
)

# Step 2: Point estimation with weight constraints
est = scest(
    data,
    w_constr={                    # Weight constraints
        "name": "simplex",       # simplex (default), lasso, ridge, ols
    },
)
print(est.effect)

# Step 3: Prediction intervals
pi_result = scpi(
    data,
    sims=200,                    # Bootstrap replications
    w_constr={"name": "simplex"},
    u_alpha=0.05,                # Significance for PI
)

# Step 4: Visualization
scplot(pi_result)
```

### Weight Constraint Options

| Constraint | Meaning | When to Use |
|------------|---------|-------------|
| `simplex` | W >= 0, sum(W) = 1 | Classic SCM (default, most common) |
| `lasso` | L1 penalty | Sparse solutions with many donors |
| `ridge` | L2 penalty | Regularized when donors are collinear |
| `ols` | Unconstrained | When extrapolation is acceptable |

### Multiple Treated Units

scpi-pkg natively supports multiple treated units and staggered adoption, unlike
most other SC packages:

```python
data_multi = scdata(
    df=df,
    id_var="unit",
    time_var="year",
    outcome_var="outcome",
    period_pre=[1980, 1999],
    period_post=[2000, 2010],
    unit_tr=["California", "New York"],  # Multiple treated units
    unit_co=donor_list,
)
```

## CausalPy (Bayesian Approach)

**Install:** `pip install CausalPy`

CausalPy provides Bayesian synthetic control via PyMC, yielding posterior
distributions, highest density intervals (HDI), and ROPE (region of practical
equivalence) analysis for the treatment effect. The dependency chain is heavy
(PyMC, PyTensor, ArviZ) -- consider whether Bayesian uncertainty quantification
is needed before installing.

### API Overview

CausalPy expects **wide-format** data: columns represent units, index represents
time periods.

```python
import causalpy as cp

# Prepare wide-format data: index=time, columns=unit names
# Treated unit and control units as separate columns
result = cp.SyntheticControl(
    df_wide,                                   # Wide-format DataFrame
    treatment_time=2000,                       # Treatment onset
    control_units=["Nevada", "Oregon", "Washington", "Colorado"],
    treated_units=["California"],
    model=cp.pymc_models.WeightedSumFitter(
        sample_kwargs={
            "target_accept": 0.95,
            "random_seed": 42,
            "chains": 4,
            "draws": 1000,
        },
    ),
)

# Results
result.summary()                # Summary statistics
result.plot()                   # Path plot with HDI bands

# Access posterior
posterior_att = result.post_treatment_effect   # Posterior samples of ATT
print(f"Mean ATT: {posterior_att.mean():.4f}")
print(f"95% HDI: [{np.percentile(posterior_att, 2.5):.4f}, "
      f"{np.percentile(posterior_att, 97.5):.4f}]")
```

**Key differences from frequentist SC:**
- Produces full posterior distribution of weights and treatment effects
- Natural uncertainty quantification through HDI (no need for placebo heuristics)
- MCMC sampling is slower than optimization-based methods
- Results depend on prior specification (WeightedSumFitter uses a Dirichlet prior
  on weights by default, enforcing the simplex constraint probabilistically)

## Inference for Synthetic Controls

Inference is where SC most differs from standard regression methods. Standard
errors, t-tests, and p-values from asymptotic theory do not apply -- the treated
sample size is 1 (or very small), and the donor weights are estimated. This
section covers the five main inference approaches.

### 1. In-Space Placebo Tests (Abadie, Diamond, and Hainmueller 2010)

The foundational inference approach for SC. Apply the SC method to each control
unit as if it were treated (using the remaining controls as donors). The treated
unit's post-treatment gap is compared to this distribution of placebo gaps.

**Procedure:**
1. Estimate SC for the treated unit -> compute gap_treated(t) for each post period
2. For each donor j = 1, ..., J:
   a. Apply SC using the remaining J-1 donors (excluding j) as the donor pool
   b. Compute gap_j(t) for each post period
3. Compare treated gap to placebo distribution

**Filtering placebos:** Exclude units with poor pre-treatment fit. If a
placebo unit has pre-RMSPE much larger than the treated unit's, its large
post-treatment gap is an artifact of poor matching, not a treatment effect.

```python
# Manual in-space placebo (using scipy implementation from above)
placebo_gaps = {}

for j, placebo_unit in enumerate(donor_units):
    # Remaining donors (exclude placebo unit)
    remaining = [d for d in donor_units if d != placebo_unit]

    # Build matrices for this placebo run
    X1_p = (pre_df.filter(pl.col(UNIT_COL) == placebo_unit)
            .sort(TIME_COL)[OUTCOME_COL].to_numpy().reshape(-1, 1))
    X0_p = np.column_stack([
        pre_df.filter(pl.col(UNIT_COL) == d)
        .sort(TIME_COL)[OUTCOME_COL].to_numpy()
        for d in remaining
    ])
    Y1_p = (post_df.filter(pl.col(UNIT_COL) == placebo_unit)
            .sort(TIME_COL)[OUTCOME_COL].to_numpy())
    Y0_p = np.column_stack([
        post_df.filter(pl.col(UNIT_COL) == d)
        .sort(TIME_COL)[OUTCOME_COL].to_numpy()
        for d in remaining
    ])

    J_p = len(remaining)
    res_p = minimize(
        sc_objective, np.ones(J_p) / J_p, args=(X0_p, X1_p),
        method="SLSQP",
        bounds=[(0, 1)] * J_p,
        constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1},
    )
    synth_pre_p = X0_p @ res_p.x
    synth_post_p = Y0_p @ res_p.x
    pre_rmspe_p = np.sqrt(np.mean((X1_p.flatten() - synth_pre_p) ** 2))
    post_gap_p = Y1_p - synth_post_p

    placebo_gaps[placebo_unit] = {
        "pre_rmspe": pre_rmspe_p,
        "post_gaps": post_gap_p,
        "post_rmspe": np.sqrt(np.mean(post_gap_p ** 2)),
    }

print(f"Treated pre-RMSPE: {pre_rmspe:.4f}")
```

### 2. RMSPE Ratio Test

The RMSPE ratio -- post-treatment RMSPE divided by pre-treatment RMSPE -- is the
standard test statistic for SC inference. A unit with a large post/pre ratio has
a gap that is large relative to its pre-treatment fit quality.

```python
# RMSPE ratio for treated unit
treated_ratio = post_rmspe / pre_rmspe

# RMSPE ratios for all placebos
ratios = {}
for unit, vals in placebo_gaps.items():
    if vals["pre_rmspe"] > 0:
        ratios[unit] = vals["post_rmspe"] / vals["pre_rmspe"]

# Include treated unit
ratios[TREATED_UNIT] = treated_ratio

# Rank-based p-value
all_ratios = sorted(ratios.values(), reverse=True)
rank = all_ratios.index(treated_ratio) + 1
p_value = rank / len(all_ratios)

print(f"Treated RMSPE ratio: {treated_ratio:.2f}")
print(f"Rank: {rank} of {len(all_ratios)}")
print(f"p-value: {p_value:.4f}")
```

**Interpretation:** The p-value is rank(treated_ratio) / (J + 1). With J = 19
donors (20 total units including treated), the minimum achievable p-value is
1/20 = 0.05. For p < 0.05, you need J >= 19 control units.

### 3. Pre-RMSPE Filtering

Not all placebos deserve equal standing. Units with poor pre-treatment fit
generate noisy post-treatment gaps that dilute the placebo distribution.

```python
# Filter: exclude placebos with pre-RMSPE > threshold * treated pre-RMSPE
MSPE_THRESHOLD = 5  # Abadie et al. (2010) used 2; 5 is more inclusive

filtered_ratios = {
    unit: r for unit, r in ratios.items()
    if unit == TREATED_UNIT
    or placebo_gaps.get(unit, {}).get("pre_rmspe", float("inf")) <= MSPE_THRESHOLD * pre_rmspe
}

n_excluded = len(ratios) - len(filtered_ratios)
print(f"Excluded {n_excluded} placebos with pre-RMSPE > {MSPE_THRESHOLD}x treated")

# Recalculate p-value with filtered set
filtered_sorted = sorted(filtered_ratios.values(), reverse=True)
filtered_rank = filtered_sorted.index(treated_ratio) + 1
filtered_p = filtered_rank / len(filtered_sorted)
print(f"Filtered p-value: {filtered_p:.4f} ({len(filtered_sorted)} units)")
```

### 4. In-Time Placebo Tests

Reassign treatment to a pre-treatment date. If the SC method detects a "gap"
before the actual treatment, the method may be detecting pre-existing divergence
rather than a treatment effect.

```python
# In-time placebo: pretend treatment happened at a pre-treatment date
PLACEBO_TREATMENT_YEAR = 1990  # Well before actual treatment

placebo_pre = [y for y in pre_periods if y < PLACEBO_TREATMENT_YEAR]
placebo_post = [y for y in pre_periods if y >= PLACEBO_TREATMENT_YEAR]

# Re-estimate SC using only pre-placebo period for fitting
# Then check if a "gap" appears in the placebo-post period
# A large gap here is a red flag: the SC is not tracking the treated unit
# even before real treatment, suggesting the counterfactual is unreliable
```

### 5. Conformal Inference (Chernozhukov, Wuthrich, and Zhu 2021)

Conformal inference provides finite-sample valid p-values and confidence
intervals without distributional assumptions. It permutes the treatment
assignment across time periods to construct a reference distribution.

Available in pysyncon via `synth.confidence_interval()` (see pysyncon section
above). Also available in scpi-pkg via `scpi()`.

**Advantages over placebo tests:**
- Finite-sample exact coverage (not approximate)
- Does not require a large donor pool for valid inference
- Provides confidence intervals, not just p-values

### 6. Prediction Intervals (Cattaneo, Feng, and Titiunik 2021)

Available only via scpi-pkg. These intervals account for two sources of
uncertainty that other methods ignore:

1. **In-sample uncertainty:** estimation error in the synthetic control weights
2. **Out-of-sample uncertainty:** prediction error for future outcomes given
   estimated weights

Standard SC treats the weights as known and only considers the prediction gap,
understating total uncertainty. Prediction intervals are wider but more honest.

### Inference Method Comparison

| Method | Source of Validity | Requires | Produces | Package |
|--------|-------------------|----------|----------|---------|
| In-space placebos | Permutation analogy | J >= 19 for p < 0.05 | Rank-based p-value | pysyncon, manual |
| RMSPE ratio | Permutation | Same as above | p-value | pysyncon, manual |
| In-time placebos | Falsification check | Sufficient pre-periods | Visual diagnostic | Any / manual |
| Conformal inference | Finite-sample exactness | Exchangeability across time | CI + p-value | pysyncon, scpi-pkg |
| Prediction intervals | In- and out-of-sample uncertainty | Regularity conditions | Prediction interval | scpi-pkg only |
| Bayesian HDI | Posterior distribution | Prior specification | HDI + posterior | CausalPy |

**Recommendation:** Use in-space placebos as the baseline (most widely accepted),
supplement with conformal inference for formal CI, and report in-time placebos as
a falsification check. If rigorous prediction intervals are needed, use scpi-pkg.

## How SDID Differs from Classic SCM

Synthetic difference-in-differences (Arkhangelsky et al. 2021) is a distinct
estimator that combines elements of SCM and DiD.

### Conceptual Comparison

| Dimension | Classic SCM | DiD (TWFE) | SDID |
|-----------|-------------|------------|------|
| Unit weights | Optimized to match pre-treatment trajectory | Equal (all controls) | Optimized (like SCM) |
| Time weights | None (all pre-periods equal) | None (all periods equal within pre/post) | Optimized to balance pre-treatment trends |
| Unit fixed effects | None (absorbed into weighting) | Additive (two-way FE) | Additive (like DiD) |
| Identification | Pre-treatment trajectory match | Parallel trends | Parallel trends (relaxed by weighting) |

### Why SDID Can Be Preferred

1. **Robust to permanent level differences:** The additive unit FE in SDID absorbs
   permanent differences between treated and control units, which classic SCM
   must match exactly via weights. If the treated unit is at a systematically
   different level, SCM may struggle to achieve good pre-treatment fit, while
   SDID handles this naturally.

2. **Valid large-panel inference:** Classic SCM inference relies on permutation
   with J + 1 units -- with few donors, minimum p-values are large (1/(J+1)).
   SDID has standard asymptotic properties as both N and T grow, enabling
   conventional inference even with moderate panel sizes.

3. **Time weights improve robustness:** By down-weighting pre-treatment periods
   that are less relevant to the treatment-period comparison, SDID is less
   sensitive to early pre-treatment dynamics that may not predict post-treatment
   counterfactuals.

### When to Use Each

| Setting | Preferred Method | Reason |
|---------|-----------------|--------|
| 1 treated unit, long pre-period, good fit | Classic SCM | Well-established, transparent weights |
| 1 treated unit, permanent level differences | SDID | FE absorbs level shifts |
| Few treated units, many controls | SDID | Better inference properties |
| Many treated units, staggered adoption | DiD estimators (pyfixest) | Designed for this; see `difference-in-differences.md` |
| Need formal prediction intervals | scpi-pkg (SCM) | Only package with rigorous PI |
| Need Bayesian uncertainty | CausalPy | Full posterior distribution |

### Reporting Both

In practice, running both SCM and SDID as robustness checks is common when both
are feasible. Agreement between the two strengthens the findings; disagreement
prompts investigation into which assumptions are more credible in the specific
application.

## Gotchas and Pitfalls

These are the most common mistakes and subtle issues in applied SC work.

### 1. Overfitting Pre-Treatment

**Problem:** Using too many predictors (especially outcome lags at many specific
time points) relative to the number of pre-treatment periods causes the SC to
match noise rather than signal.

**Diagnostic:** The danger zone is T0/J <= 0.8 (pre-treatment periods divided by
number of donors). If you have 10 pre-periods and 15 donors, be cautious about
matching on more than a few predictors.

**Solution:** Use outcome means over sub-periods rather than individual years.
Cross-validate by holding out some pre-treatment periods and checking
out-of-sample fit.

### 2. Interpolation Bias

**Problem:** If the relationship between the outcome and predictors is nonlinear,
a weighted average of donor units (which is a linear operation) may poorly
approximate the treated unit even with perfect predictor balance.

**Example:** Averaging a very rich and a very poor country to approximate a
middle-income country fails when growth dynamics are nonlinear in income level.

**Solution:** Restrict the donor pool to units that are individually similar to the
treated unit. Do not rely on averaging dissimilar units to "meet in the middle."

### 3. Extrapolation Bias

**Problem:** If the treated unit lies outside the convex hull of the donor pool
(i.e., it is more extreme than any weighted average of donors can produce), the
SC is forced to extrapolate.

**Diagnostic:** Check whether the treated unit's predictor values fall within the
range spanned by the donor units. If the treated unit has the highest GDP, the
lowest poverty rate, etc., no convex combination of donors can match it.

**Solution:** Accept that SC may not be appropriate for this treated unit, or relax
the simplex constraint (allow negative weights via scpi-pkg's `ols` constraint),
understanding that this sacrifices interpretability.

### 4. Small Donor Pools and Inference Limitations

**Problem:** The minimum achievable p-value from in-space placebos is 1/(J+1). With
only 10 control units, the best p-value is 1/11 = 0.09 -- you cannot achieve
conventional significance regardless of effect size.

**Rule of thumb:** For p < 0.05, need J >= 19 control units. For p < 0.01, need
J >= 99.

**Solution:** Use conformal inference (which does not depend on donor pool size for
validity) or prediction intervals (scpi-pkg) as alternatives when the donor pool
is small.

### 5. SUTVA Violations

**Problem:** Spillover effects from the treated unit to control units (or
anticipatory effects from expected treatment) contaminate the donor pool. If
California's policy affects Nevada's outcome, Nevada is no longer a valid control.

**Diagnostic:** Consider whether the treatment could plausibly affect donor units
through trade, migration, competition, or policy imitation.

**Solution:** Exclude geographically or economically proximate units from the donor
pool if spillovers are plausible. This trades donor pool size for donor pool
validity.

### 6. Multiple Treated Units

**Problem:** Classic SCM is designed for a single treated unit. Running separate
SCMs and averaging the effects is common but ignores correlation across treated
units and does not provide valid joint inference.

**Solution:** Use scpi-pkg, which natively supports multiple treated units with
appropriate inference. For staggered adoption with many treated units, consider
switching to DiD estimators (pyfixest) instead.

### 7. Outcome Scale Sensitivity

**Problem:** Results can change meaningfully depending on whether the outcome is
measured in levels, logs, growth rates, or per-capita terms. The "best"
synthetic control in levels may be different from the best in logs.

**Diagnostic:** Report results under multiple transformations. If the qualitative
conclusion changes, discuss which scale is most appropriate for the research
question.

### 8. No Formal Standard Errors

**Problem:** Bootstrap standard errors are **invalid** for SCM because the
estimator is not smooth (it involves a constrained optimization with binding
inequality constraints). Researchers sometimes report bootstrap SEs out of habit
-- these have no theoretical justification for SC.

**Solution:** Use placebo-based inference, conformal inference, or prediction
intervals. Never report bootstrap standard errors for SC weights or treatment
effects as if they were valid.

### 9. Pre-Treatment Fit Quality

**Problem:** There is no universal threshold for "acceptable" pre-treatment RMSPE.
A pre-RMSPE of 5.0 is excellent for an outcome measured in hundreds but terrible
for one measured in single digits.

**Diagnostic:** Compare the treated unit's pre-RMSPE to the scale of the outcome
and to the distribution of placebo pre-RMSPEs. A treated unit whose fit is worse
than most placebos has a questionable synthetic control.

**Solution:** Report pre-RMSPE alongside outcome summary statistics. Show the
path plot so readers can visually assess fit quality. If fit is poor, be
transparent that the counterfactual is weakly identified.

### 10. Non-Uniqueness of V Weights

**Problem:** The outer optimization over V (predictor importance weights) is
non-convex and may have multiple local optima. Different starting values or
optimization algorithms can produce different V weights and therefore different
W weights and treatment effect estimates. Klosner and Kaul (2018) documented
this sensitivity systematically.

**Solution:** Run the optimization from multiple starting points and check
sensitivity. Report the range of estimates across starting points. If results
vary substantially, this is a signal that the SC is not robustly identified for
this application.

## Decision Tree: Which Approach?

```
Do you have a synthetic control package installed?
│
├─ NO
│   └─ Use manual scipy implementation (above)
│       └─ Is the analysis exploratory or will it be published?
│           ├─ Exploratory → manual implementation is sufficient
│           └─ Publication → install pysyncon for placebo tests + conformal CI
│
├─ YES → What do you need?
│   │
│   ├─ Classic SCM (single treated unit, trajectory matching)
│   │   └─ pysyncon
│   │       └─ Need formal prediction intervals?
│   │           ├─ YES → supplement with scpi-pkg
│   │           └─ NO → pysyncon placebo tests + conformal CI
│   │
│   ├─ SDID (unit weights + time weights + unit FE)
│   │   └─ synthdid
│   │       └─ Staggered adoption with many units?
│   │           ├─ YES → synthdid supports staggered
│   │           └─ Consider DiD estimators (pyfixest) if J is large
│   │
│   ├─ Multiple treated units with formal inference
│   │   └─ scpi-pkg (native support)
│   │
│   ├─ Bayesian uncertainty quantification
│   │   └─ CausalPy
│   │
│   └─ Robustness: run SCM + SDID and compare
```

## References

### Foundational SCM Papers

Abadie, A. and Gardeazabal, J. (2003). "The Economic Costs of Conflict: A Case
Study of the Basque Country." *American Economic Review*, 93(1), 113-132.
https://doi.org/10.1257/000282803321455188

Abadie, A., Diamond, A., and Hainmueller, J. (2010). "Synthetic Control Methods
for Comparative Case Studies: Estimating the Effect of California's Tobacco
Control Program." *Journal of the American Statistical Association*,
105(490), 493-505. https://doi.org/10.1198/jasa.2009.ap08746

Abadie, A., Diamond, A., and Hainmueller, J. (2015). "Comparative Politics and
the Synthetic Control Method." *American Journal of Political Science*,
59(2), 495-510. https://doi.org/10.1111/ajps.12116

Abadie, A. (2021). "Using Synthetic Controls: Feasibility, Data Requirements,
and Methodological Aspects." *Journal of Economic Literature*, 59(2),
391-425. https://doi.org/10.1257/jel.20191450

### Synthetic Difference-in-Differences

Arkhangelsky, D., Athey, S., Hirshberg, D.A., Imbens, G.W., and Wager, S.
(2021). "Synthetic Difference-in-Differences." *American Economic Review*,
111(12), 4088-4118. https://doi.org/10.1257/aer.20190159

### Inference Methods

Cattaneo, M.D., Feng, Y., and Titiunik, R. (2021). "Prediction Intervals for
Synthetic Control Methods." *Journal of the American Statistical
Association*, 116(536), 1865-1880.
https://doi.org/10.1080/01621459.2021.1979561

Chernozhukov, V., Wuthrich, K., and Zhu, Y. (2021). "An Exact and Robust
Conformal Inference Method for Counterfactual and Synthetic Controls."
*Journal of the American Statistical Association*, 116(536), 1849-1864.
https://doi.org/10.1080/01621459.2021.1920957

### Extensions

Ben-Michael, E., Feller, A., and Rothstein, J. (2021). "The Augmented Synthetic
Control Method." *Journal of the American Statistical Association*,
116(536), 1789-1803. https://doi.org/10.1080/01621459.2021.1929245

Doudchenko, N. and Imbens, G.W. (2016). "Balancing, Regression,
Difference-in-Differences and Synthetic Control Methods: A Synthesis." NBER
Working Paper No. 22791.

### Software

Cattaneo, M.D., Feng, Y., Palomba, F., and Titiunik, R. (2025). "scpi:
Uncertainty Quantification for Synthetic Control Methods." *Journal of
Statistical Software*, 113(1), 1-38.

### Textbooks

Cunningham, S. (2021). *Causal Inference: The Mixtape*. Yale University Press.
Ch. 10: Synthetic Control. https://mixtape.scunning.com/

### Methodological Caveats

Kaul, A., Klößner, S., Pfeifer, G., and Schieler, M. (2015). "Synthetic Control Methods: Never Use All
Pre-Intervention Outcomes Together with Covariates." Working Paper.
