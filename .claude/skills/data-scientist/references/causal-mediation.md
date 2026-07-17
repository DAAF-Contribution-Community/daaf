# Causal Mediation Analysis

Implementation reference for causal mediation analysis in Python using statsmodels
and manual bootstrap methods. Covers the full workflow: when mediation is appropriate,
the causal framework (NDE/NIE), statsmodels `Mediation` class, manual product-of-coefficients
bootstrap, sensitivity analysis, and reporting. For methodology context -- where mediation
fits in the causal inference toolkit and how it relates to other designs -- see
`causal-inference.md` > "Method Selection Guide." This file focuses on **how to implement**
once you have decided mediation is the right design.

**Recommended default:** The statsmodels `Mediation` class (see [statsmodels Mediation
Class](#statsmodels-mediation-class)) implements the Imai, Keele, and Tingley (2010)
framework with simulation-based inference. Start here for standard mediation analyses
with OLS or GLM outcome models. For full control over the bootstrap or nonstandard
model combinations, use the manual bootstrap approach.

## Contents

- [When to Use Causal Mediation](#when-to-use-causal-mediation)
- [Causal Framework](#causal-framework)
- [Sequential Ignorability](#sequential-ignorability)
- [statsmodels Mediation Class](#statsmodels-mediation-class)
- [Manual Bootstrap: Product of Coefficients](#manual-bootstrap-product-of-coefficients)
- [Sobel Test (Legacy)](#sobel-test-legacy)
- [Moderated Mediation](#moderated-mediation)
- [Multiple Mediators](#multiple-mediators)
- [Sensitivity Analysis](#sensitivity-analysis)
- [Complete Mediation Analysis Template](#complete-mediation-analysis-template)
- [Gotchas](#gotchas)
- [References](#references)

## When to Use Causal Mediation

Mediation analysis asks: **through what mechanism** does a treatment affect an outcome?
It decomposes the total effect of treatment T on outcome Y into an indirect effect
(T -> M -> Y, operating through the mediator) and a direct effect (T -> Y, through
all other channels).

**Appropriate when:**
- There is a clear theoretical causal chain: T -> M -> Y
- Treatment is randomized or conditionally ignorable given covariates
- The mediator is measured after treatment but before the outcome
- The research question is about *mechanisms*, not just total effects
- No post-treatment confounders exist between M and Y

**Not appropriate when:**
- The mediator is measured with substantial error (biases indirect effect toward zero)
- Post-treatment confounders exist between M and Y (invalidates NDE/NIE decomposition)
- There is no theoretical basis for the causal ordering T -> M -> Y
- The mediator is a collider (conditioning on it opens non-causal paths)
- The goal is simply to test whether a total effect exists (use standard methods instead)
- Treatment and mediator interact in ways that cannot be modeled

**Relationship to other causal methods:** Mediation is not an identification strategy
in the same sense as IV, RD, or DiD. Those methods answer "does T cause Y?" Mediation
answers "through what channel does T cause Y?" -- it requires a credible total effect
as a starting point. Mediation decomposes an already-identified causal effect into
pathways; it does not establish causality on its own.

## Causal Framework

The modern causal mediation framework follows Imai, Keele, and Tingley (2010) and
Pearl (2001, 2014), replacing the older Baron-Kenny (1986) "causal steps" approach.

### Effect Definitions

Using potential outcomes notation where M(t) is the mediator value under treatment t,
and Y(t, m) is the outcome under treatment t and mediator value m:

| Effect | Definition | Interpretation |
|--------|-----------|----------------|
| **Total Effect (TE)** | E[Y(1, M(1)) - Y(0, M(0))] | Full effect of treatment on outcome |
| **Natural Indirect Effect (NIE)** | E[Y(t, M(1)) - Y(t, M(0))] | Effect of treatment operating *through* the mediator (also called ACME) |
| **Natural Direct Effect (NDE)** | E[Y(1, M(t)) - Y(0, M(t))] | Effect of treatment operating through *all other channels* (also called ADE) |
| **Controlled Direct Effect (CDE)** | E[Y(1, m) - Y(0, m)] | Effect of treatment when mediator is held fixed at value m |

**Exact decomposition:** Total Effect = NDE + NIE. This holds by definition under
the potential outcomes framework, regardless of functional form.

**Proportion mediated:** NIE / TE gives the fraction of the total effect that operates
through the mediator. This is interpretable only when the total effect and indirect
effect have the same sign. When they have opposite signs (inconsistent mediation or
suppression), the proportion can exceed 1 or be negative, which is a signal of
complex causal dynamics, not an error.

### Baron-Kenny vs. Modern Framework

The Baron-Kenny (1986) "causal steps" approach -- (1) show T affects Y, (2) show T
affects M, (3) show M affects Y controlling for T, (4) check if T's effect on Y
diminishes when M is included -- has no formal causal foundation. It conflates
statistical associations with causal effects and can indicate mediation where none
exists (and miss mediation where it does exist).

The modern framework (Imai et al. 2010; Pearl 2014) provides:
- Clearly defined causal estimands (NDE, NIE) grounded in potential outcomes
- Explicit identification assumptions (sequential ignorability)
- Valid inference via simulation or bootstrap
- Proper handling of nonlinear models (where the product-of-coefficients
  decomposition breaks down)

Use the modern framework. Baron-Kenny is included in this reference only because
it appears frequently in existing literature and reviewers may ask about it.

## Sequential Ignorability

The key identification assumption for causal mediation is **sequential ignorability**
(Imai, Keele, and Yamamoto 2010). It has two parts:

**SI-1 (Treatment ignorability):** Conditional on observed pre-treatment covariates X,
treatment assignment is independent of potential outcomes and potential mediator values:

```
{Y(t', m), M(t)} independent of T | X = x
```

This is satisfied by randomization of treatment or by the standard conditional
independence assumption (selection on observables) used in matching/regression.

**SI-2 (Mediator ignorability):** Conditional on observed pre-treatment covariates X
and treatment status T, the mediator is independent of potential outcomes:

```
Y(t', m) independent of M | T = t, X = x
```

This is the **critical and problematic** assumption. It requires that there are no
unobserved confounders of the M -> Y relationship, even after conditioning on treatment
and covariates. Unlike SI-1, **SI-2 cannot be guaranteed by randomizing treatment.**
Even in an RCT, post-treatment confounders between M and Y can violate SI-2.

**Why SI-2 is so demanding:**
- Treatment randomization does not randomize the mediator
- Conditioning on post-treatment variables (including M) can introduce collider bias
- Any unmeasured common cause of M and Y invalidates the decomposition
- This assumption is **fundamentally untestable** from the data alone

**Practical implication:** Because SI-2 cannot be tested or guaranteed, sensitivity
analysis is not optional -- it is an essential component of any mediation analysis.
Report how sensitive your conclusions are to violations of SI-2. See the Sensitivity
Analysis section below.

## statsmodels Mediation Class

The DAAF environment includes statsmodels 0.14.6, which provides
`statsmodels.stats.mediation.Mediation` implementing the Imai, Keele, and Tingley
(2010) simulation-based approach.

### Basic Usage

```python
import numpy as np
import polars as pl
import statsmodels.api as sm
from statsmodels.stats.mediation import Mediation

# --- Load ---
df = pl.read_parquet(f"{DATA_DIR}/analysis_data.parquet")
df_pd = df.to_pandas()

# --- Mediator model: M ~ T + X ---
# INTENT: Model the mediator as a function of treatment and covariates
mediator_formula = "mediator ~ treatment + covariate1 + covariate2"
mediator_model = sm.OLS.from_formula(mediator_formula, data=df_pd)

# --- Outcome model: Y ~ M + T + X ---
# INTENT: Model the outcome as a function of mediator, treatment, and covariates
# ASSUMES: No post-treatment confounders between mediator and outcome (SI-2)
outcome_formula = "outcome ~ mediator + treatment + covariate1 + covariate2"
outcome_model = sm.OLS.from_formula(outcome_formula, data=df_pd)

# --- Mediation analysis ---
med = Mediation(outcome_model, mediator_model, "treatment", "mediator")
result = med.fit(method="parametric", n_rep=1000)
print(result.summary())
```

### Reading the Output

The `summary()` method returns a pandas DataFrame and prints a table. The DataFrame
has a multi-level index with rows for control, treated, and average variants of each
effect:

| Row Index | What It Is |
|-----------|------------|
| `ACME (control)` | NIE evaluated at control treatment level |
| `ACME (treated)` | NIE evaluated at treated treatment level |
| `ADE (control)` | NDE evaluated at control treatment level |
| `ADE (treated)` | NDE evaluated at treated treatment level |
| `Total effect` | NDE + NIE = total causal effect |
| `Prop. mediated (control)` | ACME / Total at control level |
| `Prop. mediated (treated)` | ACME / Total at treated level |
| `ACME (average)` | Average NIE across treatment levels |
| `ADE (average)` | Average NDE across treatment levels |
| `Prop. mediated (average)` | Average proportion mediated |

Each row has four columns: `Estimate`, `Lower CI bound`, `Upper CI bound`, `P-value`.

**Important:** The result object attributes like `result.ACME_avg`, `result.ADE_avg`,
`result.total_effect`, and `result.prop_med_avg` exist but contain numpy arrays of
all `n_rep` simulation draws (shape `(n_rep,)`), NOT scalar point estimates. There
are no `_CI` attributes (e.g., `result.ACME_avg_CI` does not exist). To get point
estimates and confidence intervals, use `result.summary()` as shown below.

### Extracting Results Programmatically

```python
result = med.fit(method="parametric", n_rep=1000)

# --- Extract key results ---
# INTENT: Extract point estimates and CIs from the summary DataFrame
# REASONING: Raw attributes (result.ACME_avg, etc.) are numpy arrays of n_rep
# simulation draws, NOT scalars. Use summary() for point estimates and CIs.
summary = result.summary()

acme = summary.loc["ACME (average)", "Estimate"]
acme_ci = (summary.loc["ACME (average)", "Lower CI bound"],
           summary.loc["ACME (average)", "Upper CI bound"])
acme_pval = summary.loc["ACME (average)", "P-value"]

ade = summary.loc["ADE (average)", "Estimate"]
ade_ci = (summary.loc["ADE (average)", "Lower CI bound"],
          summary.loc["ADE (average)", "Upper CI bound"])

total = summary.loc["Total effect", "Estimate"]
total_ci = (summary.loc["Total effect", "Lower CI bound"],
            summary.loc["Total effect", "Upper CI bound"])

prop_med = summary.loc["Prop. mediated (average)", "Estimate"]
prop_med_ci = (summary.loc["Prop. mediated (average)", "Lower CI bound"],
               summary.loc["Prop. mediated (average)", "Upper CI bound"])

print(f"ACME (indirect): {acme:.4f} [{acme_ci[0]:.4f}, {acme_ci[1]:.4f}]")
print(f"ADE (direct):    {ade:.4f} [{ade_ci[0]:.4f}, {ade_ci[1]:.4f}]")
print(f"Total effect:    {total:.4f} [{total_ci[0]:.4f}, {total_ci[1]:.4f}]")
print(f"Prop. mediated:  {prop_med:.4f} [{prop_med_ci[0]:.4f}, {prop_med_ci[1]:.4f}]")
```

### Constructor Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `outcome_model` | statsmodels model (unfitted) | Model for Y ~ M + T + X. Accepts OLS, GLM, Logit, etc. |
| `mediator_model` | statsmodels model (unfitted) | Model for M ~ T + X. Accepts OLS, GLM, Logit, etc. |
| `exposure` | str | Name of the treatment variable |
| `mediator` | str | Name of the mediator variable |
| `moderators` | dict, optional | Variables that moderate the mediation (see Moderated Mediation) |

### Fit Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `method` | `"parametric"` | `"parametric"` draws from fitted model distributions; `"bootstrap"` resamples data |
| `n_rep` | 1000 | Number of simulation/bootstrap replications. Use 5000 for final results |

### Using GLM Models

For binary mediators or outcomes, use GLM instead of OLS:

```python
# Binary mediator (logistic)
mediator_model = sm.GLM.from_formula(
    "binary_mediator ~ treatment + covariate1 + covariate2",
    data=df_pd,
    family=sm.families.Binomial()
)

# Binary outcome (logistic)
outcome_model = sm.GLM.from_formula(
    "binary_outcome ~ binary_mediator + treatment + covariate1 + covariate2",
    data=df_pd,
    family=sm.families.Binomial()
)

med = Mediation(outcome_model, mediator_model, "treatment", "binary_mediator")
result = med.fit(method="parametric", n_rep=1000)
print(result.summary())
# REASONING: The simulation-based approach in statsmodels handles nonlinear
# models correctly, unlike the product-of-coefficients method which assumes
# linearity for the TE = NDE + NIE decomposition.
```

## Manual Bootstrap: Product of Coefficients

When you need full control over the estimation procedure or want to use models
not supported by statsmodels `Mediation`, implement the bootstrap manually.

The product-of-coefficients approach estimates the indirect effect as `a * b`, where:
- `a` = effect of treatment on mediator (from M ~ T + X)
- `b` = effect of mediator on outcome controlling for treatment (from Y ~ M + T + X)

This decomposition is exact for linear models but approximate for nonlinear models.
For nonlinear models, prefer the statsmodels `Mediation` simulation approach.

```python
import numpy as np
import statsmodels.api as sm

# --- Config ---
N_BOOT = 5000
SEED = 42
rng = np.random.default_rng(SEED)

# --- Prepare data ---
# INTENT: Set up numpy arrays for bootstrapping
T = df["treatment"].to_numpy()
M = df["mediator"].to_numpy()
Y = df["outcome"].to_numpy()
X = df[["covariate1", "covariate2"]].to_numpy()
n = len(Y)

# --- Point estimates ---
# Stage 1: M ~ T + X
X_med = np.column_stack([np.ones(n), T, X])
med_model = sm.OLS(M, X_med).fit()
a_hat = med_model.params[1]  # Coefficient on T

# Stage 2: Y ~ M + T + X
X_out = np.column_stack([np.ones(n), M, T, X])
out_model = sm.OLS(Y, X_out).fit()
b_hat = out_model.params[1]  # Coefficient on M
c_prime = out_model.params[2]  # Direct effect (coefficient on T)

indirect = a_hat * b_hat
direct = c_prime
total = indirect + direct

print(f"Indirect effect (a*b): {indirect:.4f}")
print(f"Direct effect (c'):    {direct:.4f}")
print(f"Total effect:          {total:.4f}")
print(f"Proportion mediated:   {indirect / total:.4f}")

# --- Bootstrap ---
# INTENT: Bootstrap both stages jointly for valid CIs
# REASONING: Must resample and re-estimate both models on each replicate
# to account for estimation uncertainty in both a and b
boot_indirect = np.zeros(N_BOOT)
boot_direct = np.zeros(N_BOOT)

for i in range(N_BOOT):
    idx = rng.choice(n, size=n, replace=True)
    T_b, M_b, Y_b, X_b = T[idx], M[idx], Y[idx], X[idx]

    # Stage 1
    X_med_b = np.column_stack([np.ones(n), T_b, X_b])
    a_b = sm.OLS(M_b, X_med_b).fit().params[1]

    # Stage 2
    X_out_b = np.column_stack([np.ones(n), M_b, T_b, X_b])
    params_b = sm.OLS(Y_b, X_out_b).fit().params
    b_b = params_b[1]
    c_b = params_b[2]

    boot_indirect[i] = a_b * b_b
    boot_direct[i] = c_b

# --- CIs (percentile method) ---
ci_indirect = np.percentile(boot_indirect, [2.5, 97.5])
ci_direct = np.percentile(boot_direct, [2.5, 97.5])
se_indirect = boot_indirect.std()
se_direct = boot_direct.std()

print(f"\nBootstrap results ({N_BOOT} replications):")
print(f"Indirect: {indirect:.4f} (SE: {se_indirect:.4f}) "
      f"95% CI: [{ci_indirect[0]:.4f}, {ci_indirect[1]:.4f}]")
print(f"Direct:   {direct:.4f} (SE: {se_direct:.4f}) "
      f"95% CI: [{ci_direct[0]:.4f}, {ci_direct[1]:.4f}]")
```

### Bias-Corrected and Accelerated (BCa) Bootstrap

The percentile bootstrap can have poor coverage in small samples. The BCa correction
improves coverage but is more computationally intensive:

```python
from scipy.stats import norm

# BCa correction for indirect effect
# Step 1: Bias correction
z0 = norm.ppf((boot_indirect < indirect).mean())

# Step 2: Acceleration (jackknife estimate)
jack_indirect = np.zeros(n)
for j in range(n):
    idx_j = np.concatenate([np.arange(j), np.arange(j + 1, n)])
    T_j, M_j, Y_j, X_j = T[idx_j], M[idx_j], Y[idx_j], X[idx_j]
    n_j = len(Y_j)
    a_j = sm.OLS(M_j, np.column_stack([np.ones(n_j), T_j, X_j])).fit().params[1]
    b_j = sm.OLS(Y_j, np.column_stack([np.ones(n_j), M_j, T_j, X_j])).fit().params[1]
    jack_indirect[j] = a_j * b_j

jack_mean = jack_indirect.mean()
acc = ((jack_mean - jack_indirect) ** 3).sum() / (
    6 * ((jack_mean - jack_indirect) ** 2).sum() ** 1.5
)

# Step 3: Adjusted percentiles
alpha = 0.05
z_lo = norm.ppf(alpha / 2)
z_hi = norm.ppf(1 - alpha / 2)
p_lo = norm.cdf(z0 + (z0 + z_lo) / (1 - acc * (z0 + z_lo)))
p_hi = norm.cdf(z0 + (z0 + z_hi) / (1 - acc * (z0 + z_hi)))

ci_bca = np.percentile(boot_indirect, [p_lo * 100, p_hi * 100])
print(f"BCa 95% CI: [{ci_bca[0]:.4f}, {ci_bca[1]:.4f}]")
```

## Sobel Test (Legacy)

The Sobel test is a legacy approach that tests H0: a*b = 0 using a first-order
approximation to the standard error of the product. It assumes the sampling
distribution of a*b is normal, which is often violated (the product of two normal
variables is not normal, especially in small samples).

**Prefer bootstrap CIs over the Sobel test.** The Sobel test is included here because
it appears in older literature and some reviewers may request it. For new analyses,
use the bootstrap or statsmodels `Mediation`.

```python
from scipy.stats import norm

# a, b from the two regression stages
# se_a, se_b from model standard errors
a = med_model.params[1]
se_a = med_model.bse[1]
b = out_model.params[1]
se_b = out_model.bse[1]

# Sobel test statistic
sobel_se = np.sqrt(a**2 * se_b**2 + b**2 * se_a**2)
sobel_z = (a * b) / sobel_se
sobel_p = 2 * (1 - norm.cdf(abs(sobel_z)))

print(f"Sobel test: z = {sobel_z:.4f}, p = {sobel_p:.4f}")
# REASONING: The Sobel test assumes normality of the a*b distribution.
# Bootstrap CIs are preferred because a*b is often skewed, especially
# when sample sizes are small or effects are weak.
```

## Moderated Mediation

Moderated mediation (also called conditional indirect effects) occurs when the
strength of the mediation pathway varies across levels of a moderator variable.
For example, the indirect effect of a training program through skill acquisition
may be stronger for younger workers.

### Using statsmodels Mediation

The `moderators` parameter in the `Mediation` constructor allows specifying
variables that moderate the mediation process:

```python
# INTENT: Test whether the indirect effect varies by moderator value
# ASSUMES: Moderator is pre-treatment (not affected by treatment)

# Include interaction terms in both models
mediator_formula = "mediator ~ treatment * moderator + covariate1"
mediator_model = sm.OLS.from_formula(mediator_formula, data=df_pd)

outcome_formula = "outcome ~ mediator * moderator + treatment * moderator + covariate1"
outcome_model = sm.OLS.from_formula(outcome_formula, data=df_pd)

# Fit at different moderator values
med = Mediation(
    outcome_model, mediator_model,
    "treatment", "mediator",
    moderators={"moderator": 0}  # Evaluate at moderator = 0
)
result_low = med.fit(method="parametric", n_rep=1000)

med_high = Mediation(
    outcome_model, mediator_model,
    "treatment", "mediator",
    moderators={"moderator": 1}  # Evaluate at moderator = 1
)
result_high = med_high.fit(method="parametric", n_rep=1000)

print("=== Moderator = 0 ===")
print(result_low.summary())
print("\n=== Moderator = 1 ===")
print(result_high.summary())
```

### Manual Moderated Mediation

For more flexibility, compute conditional indirect effects manually:

```python
# Include interactions in both stages
# Stage 1: M ~ T + W + T*W + X
# Stage 2: Y ~ M + T + W + M*W + T*W + X
# Indirect effect at moderator W = w: a(w) * b(w)

# Where a(w) = a1 + a3*w  (a1 = T coef, a3 = T*W interaction coef)
# And   b(w) = b1 + b4*w  (b1 = M coef, b4 = M*W interaction coef)

# Index of moderated mediation = difference in indirect effects across W levels
# IMM = a(1)*b(1) - a(0)*b(0)
# Bootstrap the IMM for inference
```

## Multiple Mediators

When multiple mediators operate in parallel (T -> M1 -> Y and T -> M2 -> Y
simultaneously), each pathway can be estimated separately.

### Parallel Mediators

```python
# INTENT: Estimate indirect effects through multiple parallel mediators
# ASSUMES: Mediators do not cause each other (parallel, not sequential)

mediators = ["mediator1", "mediator2", "mediator3"]
results = {}

for m_var in mediators:
    # Mediator model: M_k ~ T + X
    med_formula = f"{m_var} ~ treatment + covariate1 + covariate2"
    med_model = sm.OLS.from_formula(med_formula, data=df_pd)

    # Outcome model: Y ~ M_k + T + X (include all mediators for correct decomposition)
    out_formula = (
        f"outcome ~ {' + '.join(mediators)} + treatment + covariate1 + covariate2"
    )
    out_model = sm.OLS.from_formula(out_formula, data=df_pd)

    med_obj = Mediation(out_model, med_model, "treatment", m_var)
    results[m_var] = med_obj.fit(method="parametric", n_rep=1000)
    print(f"\n=== Mediator: {m_var} ===")
    print(results[m_var].summary())

# REASONING: Including all mediators in the outcome model partials out
# the effects of other mediators, giving the specific indirect effect
# through each pathway. The sum of specific indirect effects plus the
# direct effect equals the total effect.
```

### Sequential Mediators

When mediators are causally ordered (T -> M1 -> M2 -> Y), the analysis is more
complex and requires careful specification of the causal ordering. Typically,
each link in the chain is estimated separately, and the full indirect pathway
is the product of all coefficients along the chain.

```python
# Sequential: T -> M1 -> M2 -> Y
# Three-path indirect effect: a1 * d * b2
# Where: a1 = T->M1, d = M1->M2, b2 = M2->Y (controlling for T and M1)
# Bootstrap all three stages jointly for valid inference
```

## Sensitivity Analysis

Because sequential ignorability (SI-2) is untestable, sensitivity analysis is a
mandatory component of any causal mediation analysis. Two approaches are available
in the DAAF environment.

### E-value for Mediation

The E-value (VanderWeele and Ding 2017) computes the minimum strength of association
that an unmeasured confounder would need to have with both the mediator and the outcome
(on the risk ratio scale) to fully explain away the observed indirect effect. Higher
E-values indicate greater robustness to unmeasured confounding.

```python
import numpy as np

# INTENT: Compute E-value for the indirect effect
# REASONING: E-value requires converting to risk ratio scale.
# For a continuous outcome, use the approximation from VanderWeele and Ding (2017):
# RR approx exp(0.91 * beta / SD(Y)) for a 1-SD change in the exposure

# From the mediation results:
indirect_effect = acme  # Scalar from result.summary() (see "Extracting Results")
se_indirect = se_indirect  # From bootstrap

# Approximate risk ratio (continuous outcome)
sd_y = df["outcome"].std()
rr = np.exp(0.91 * abs(indirect_effect) / sd_y)

# E-value
e_value = rr + np.sqrt(rr * (rr - 1))

# E-value for CI bound (use the bound closest to null)
ci_bound = min(abs(ci_indirect[0]), abs(ci_indirect[1]))
if ci_indirect[0] > 0 or ci_indirect[1] < 0:
    # CI excludes zero -- compute E-value for the bound
    rr_ci = np.exp(0.91 * ci_bound / sd_y)
    e_ci = rr_ci + np.sqrt(rr_ci * (rr_ci - 1))
else:
    e_ci = 1.0  # CI includes zero; no confounding needed to nullify

print(f"E-value for indirect effect: {e_value:.2f}")
print(f"E-value for CI bound: {e_ci:.2f}")
# REASONING: An E-value of 2.5 means an unmeasured confounder would need
# to be associated with both M and Y by a factor of at least 2.5 (each)
# to explain away the observed indirect effect. Compare this to the
# strength of known confounders in your data to assess plausibility.
```

### Informal Sensitivity Checks

When formal sensitivity analysis tools are unavailable (the R `mediation` package's
`medsens()` function, which implements the Imai et al. rho-based sensitivity analysis,
has no Python equivalent), these informal checks provide evidence about robustness:

```python
# --- Check 1: Coefficient stability ---
# INTENT: See if indirect effect changes when adding more covariates
# REASONING: If adding controls substantially changes the indirect effect,
# unobserved confounders may also shift it

covariate_sets = [
    ["covariate1"],
    ["covariate1", "covariate2"],
    ["covariate1", "covariate2", "covariate3", "covariate4"],
]

for covs in covariate_sets:
    cov_str = " + ".join(covs)
    med_m = sm.OLS.from_formula(f"mediator ~ treatment + {cov_str}", data=df_pd)
    out_m = sm.OLS.from_formula(
        f"outcome ~ mediator + treatment + {cov_str}", data=df_pd
    )
    med_obj = Mediation(out_m, med_m, "treatment", "mediator")
    res = med_obj.fit(method="parametric", n_rep=500)
    res_summary = res.summary()
    print(f"Covariates: {covs}")
    print(f"  ACME = {res_summary.loc['ACME (average)', 'Estimate']:.4f}, "
          f"ADE = {res_summary.loc['ADE (average)', 'Estimate']:.4f}")
```

```python
# --- Check 2: Placebo mediator test ---
# INTENT: A variable that should NOT mediate the effect should show
# a near-zero indirect effect
# REASONING: If a placebo mediator shows a large indirect effect,
# the model may be capturing spurious associations

placebo_med = sm.OLS.from_formula(
    "placebo_variable ~ treatment + covariate1 + covariate2", data=df_pd
)
placebo_out = sm.OLS.from_formula(
    "outcome ~ placebo_variable + treatment + covariate1 + covariate2", data=df_pd
)
placebo_analysis = Mediation(placebo_out, placebo_med, "treatment", "placebo_variable")
placebo_result = placebo_analysis.fit(method="parametric", n_rep=500)
print("Placebo mediator test:")
print(placebo_result.summary())
# ASSUMES: placebo_variable is theoretically unrelated to the T->Y pathway
```

### Imai et al. rho-based Sensitivity (R Only)

The canonical sensitivity analysis for causal mediation (Imai, Keele, and Yamamoto
2010) parametrizes the degree of violation of sequential ignorability by rho, the
correlation between the error terms of the mediator and outcome models. At rho = 0,
sequential ignorability holds exactly. The analysis reports how the ACME changes as
rho moves away from zero.

**This method has no Python implementation.** The R `mediation` package provides
`medsens()` for this analysis. If rho-based sensitivity is essential for the
project, consider using rpy2 to call R, or report E-values and informal checks
as the sensitivity analysis, noting the limitation.

## Complete Mediation Analysis Template

This template provides the full workflow for a mediation analysis, suitable for
adaptation into a DAAF pipeline script.

```python
# --- Config ---
import numpy as np
import polars as pl
import statsmodels.api as sm
from statsmodels.stats.mediation import Mediation

TREATMENT = "treatment"
MEDIATOR = "mediator"
OUTCOME = "outcome"
COVARIATES = ["covariate1", "covariate2"]
N_REP = 5000
SEED = 42

# --- Load ---
df = pl.read_parquet(f"{DATA_DIR}/analysis_data.parquet")
df_pd = df.to_pandas()
n = len(df_pd)

# --- Step 1: Verify total effect exists ---
# INTENT: Confirm treatment affects outcome before decomposing
cov_str = " + ".join(COVARIATES)
total_model = sm.OLS.from_formula(
    f"{OUTCOME} ~ {TREATMENT} + {cov_str}", data=df_pd
).fit()
total_effect = total_model.params[TREATMENT]
total_pval = total_model.pvalues[TREATMENT]
print(f"Total effect of {TREATMENT} on {OUTCOME}: {total_effect:.4f} (p={total_pval:.4f})")
# REASONING: A non-significant total effect does not preclude mediation
# (suppression effects are possible), but the decomposition is most
# interpretable when a total effect exists.

# --- Step 2: Verify treatment affects mediator (a-path) ---
a_model = sm.OLS.from_formula(
    f"{MEDIATOR} ~ {TREATMENT} + {cov_str}", data=df_pd
).fit()
a_path = a_model.params[TREATMENT]
a_pval = a_model.pvalues[TREATMENT]
print(f"a-path ({TREATMENT} -> {MEDIATOR}): {a_path:.4f} (p={a_pval:.4f})")
assert a_pval < 0.10, f"WARNING: Treatment does not significantly affect mediator (p={a_pval:.4f})"

# --- Step 3: Mediation analysis ---
mediator_model = sm.OLS.from_formula(
    f"{MEDIATOR} ~ {TREATMENT} + {cov_str}", data=df_pd
)
outcome_model = sm.OLS.from_formula(
    f"{OUTCOME} ~ {MEDIATOR} + {TREATMENT} + {cov_str}", data=df_pd
)

med = Mediation(outcome_model, mediator_model, TREATMENT, MEDIATOR)
result = med.fit(method="parametric", n_rep=N_REP)
print("\n=== Mediation Results ===")
print(result.summary())

# --- Step 4: Extract results ---
# INTENT: Extract point estimates and CIs from the summary DataFrame
# REASONING: Raw attributes (result.ACME_avg, etc.) are numpy arrays of n_rep
# simulation draws, NOT scalars. Use summary() for point estimates and CIs.
summary = result.summary()

acme = summary.loc["ACME (average)", "Estimate"]
acme_ci = (summary.loc["ACME (average)", "Lower CI bound"],
           summary.loc["ACME (average)", "Upper CI bound"])
ade = summary.loc["ADE (average)", "Estimate"]
ade_ci = (summary.loc["ADE (average)", "Lower CI bound"],
          summary.loc["ADE (average)", "Upper CI bound"])
te = summary.loc["Total effect", "Estimate"]
te_ci = (summary.loc["Total effect", "Lower CI bound"],
         summary.loc["Total effect", "Upper CI bound"])
prop = summary.loc["Prop. mediated (average)", "Estimate"]
prop_ci = (summary.loc["Prop. mediated (average)", "Lower CI bound"],
           summary.loc["Prop. mediated (average)", "Upper CI bound"])

print(f"\n=== Summary ===")
print(f"ACME (indirect): {acme:.4f} [{acme_ci[0]:.4f}, {acme_ci[1]:.4f}]")
print(f"ADE (direct):    {ade:.4f} [{ade_ci[0]:.4f}, {ade_ci[1]:.4f}]")
print(f"Total:           {te:.4f} [{te_ci[0]:.4f}, {te_ci[1]:.4f}]")
print(f"Prop. mediated:  {prop:.4f} [{prop_ci[0]:.4f}, {prop_ci[1]:.4f}]")

# --- Step 5: Sensitivity analysis (E-value) ---
sd_y = df_pd[OUTCOME].std()
rr = np.exp(0.91 * abs(acme) / sd_y)
e_val = rr + np.sqrt(rr * (rr - 1))
print(f"\nE-value for ACME: {e_val:.2f}")

# --- Step 6: Coefficient stability check ---
print("\n=== Coefficient Stability ===")
for extra_cov in [[], ["covariate3"], ["covariate3", "covariate4"]]:
    all_covs = COVARIATES + extra_cov
    cs = " + ".join(all_covs)
    m_m = sm.OLS.from_formula(f"{MEDIATOR} ~ {TREATMENT} + {cs}", data=df_pd)
    o_m = sm.OLS.from_formula(
        f"{OUTCOME} ~ {MEDIATOR} + {TREATMENT} + {cs}", data=df_pd
    )
    r = Mediation(o_m, m_m, TREATMENT, MEDIATOR).fit(method="parametric", n_rep=500)
    r_summary = r.summary()
    print(f"  Covariates: {all_covs} -> "
          f"ACME = {r_summary.loc['ACME (average)', 'Estimate']:.4f}")

# --- Validate ---
print(f"\n=== Validation ===")
print(f"N: {n}")
print(f"Total effect (regression): {total_effect:.4f}")
print(f"Total effect (ACME + ADE): {acme + ade:.4f}")
print(f"Decomposition check: |diff| = {abs(total_effect - (acme + ade)):.6f}")
assert abs(acme + ade - te) < 0.01, "Decomposition check failed: ACME + ADE != Total"
```

## Gotchas

### 1. Post-Treatment Confounding Invalidates NDE/NIE

If any variable confounds the M -> Y relationship and is itself affected by treatment,
the natural direct and indirect effects are not identified. No statistical adjustment
can fix this -- the problem is structural. Before running mediation, draw the DAG and
verify that no post-treatment variable confounds the mediator-outcome path.

### 2. Sequential Ignorability is Untestable

SI-2 (mediator ignorability) cannot be verified from observed data. Even in a
randomized experiment, treatment randomization does not randomize the mediator.
Sensitivity analysis is not optional -- report how the conclusions change under
plausible violations of SI-2.

### 3. Baron-Kenny Has No Causal Foundation

The Baron-Kenny (1986) "causal steps" approach can indicate mediation where none
exists and miss mediation where it does exist. It conflates statistical significance
of regression coefficients with causal mediation. Use the Imai et al. (2010) framework
(statsmodels `Mediation` or manual bootstrap) instead. If a reviewer requests
Baron-Kenny results, provide them alongside modern results with a note explaining
the distinction.

### 4. Measurement Error in Mediator Biases Indirect Effect Toward Zero

Classical measurement error in the mediator variable attenuates the b-path coefficient
(effect of M on Y) toward zero, which in turn attenuates the estimated indirect effect
(a * b) toward zero. This means mediation analyses using noisy mediator measures are
biased against finding mediation. If the mediator is measured with known unreliability,
consider corrections (e.g., disattenuation formulas) or discuss the likely direction
of bias.

### 5. Collider Bias from Conditioning on the Mediator

In the outcome model (Y ~ M + T + X), conditioning on M can introduce collider bias
if M is a common effect of T and some unmeasured cause of Y. This is a specific
manifestation of the SI-2 problem. Drawing the full DAG before analysis helps identify
potential collider structures.

### 6. Product-of-Coefficients Decomposition Fails for Nonlinear Models

For logistic regression and other nonlinear models, the decomposition TE = NDE + NIE
does not hold when computed as the product of regression coefficients from separate
models. This is because the scaling of coefficients differs across models with different
sets of covariates (the "non-collapsibility" issue). The statsmodels `Mediation` class
handles this correctly using simulation -- it generates predictions from the fitted
models rather than multiplying coefficients. For nonlinear models, always use the
simulation-based approach, not manual coefficient products.

### 7. Multiple Testing with Multiple Mediators

Testing several potential mediators inflates the family-wise false positive rate.
With k mediators tested independently at alpha = 0.05, the probability of at least
one false positive is 1 - (1 - 0.05)^k. For example, with 5 mediators, the probability
of at least one spurious finding is 23%. Apply Bonferroni or Benjamini-Hochberg
corrections when testing multiple mediators, and pre-specify which mediators are
primary versus exploratory.

## References

### Core Methodological Framework

Imai, K., Keele, L., and Tingley, D. (2010). "A General Approach to Causal Mediation
Analysis." *Psychological Methods*, 15(4), 309-334.
https://doi.org/10.1037/a0020761

Imai, K., Keele, L., and Yamamoto, T. (2010). "Identification, Inference and
Sensitivity Analysis for Causal Mediation Effects." *Statistical Science*, 25(1),
51-71. https://doi.org/10.1214/10-STS321

Pearl, J. (2001). "Direct and Indirect Effects." *Proceedings of the Seventeenth
Conference on Uncertainty in Artificial Intelligence (UAI)*, 411-420.

Pearl, J. (2014). "Interpretation and Identification of Causal Mediation."
*Psychological Methods*, 19(4), 459-481. https://doi.org/10.1037/a0036434

### Software

Tingley, D., Yamamoto, T., Hirose, K., Keele, L., and Imai, K. (2014). "mediation:
R Package for Causal Mediation Analysis." *Journal of Statistical Software*, 59(5),
1-38. https://doi.org/10.18637/jss.v059.i05

### Legacy and Historical

Baron, R.M. and Kenny, D.A. (1986). "The Moderator-Mediator Variable Distinction in
Social Psychological Research: Conceptual, Strategic, and Statistical Considerations."
*Journal of Personality and Social Psychology*, 51(6), 1173-1182.
https://doi.org/10.1037/0022-3514.51.6.1173

Preacher, K.J. and Hayes, A.F. (2008). "Asymptotic and Resampling Strategies for
Assessing and Comparing Indirect Effects in Multiple Mediator Models." *Behavior
Research Methods*, 40(3), 879-891. https://doi.org/10.3758/BRM.40.3.879

### Classification and Interpretation

Zhao, X., Lynch, J.G., Jr., and Chen, Q. (2010). "Reconsidering Baron and Kenny:
Myths and Truths about Mediation Analysis." *Journal of Consumer Research*, 37(2),
197-206. https://doi.org/10.1086/651257

### Sensitivity Analysis

VanderWeele, T.J. and Ding, P. (2017). "Sensitivity Analysis in Observational
Research: Introducing the E-Value." *Annals of Internal Medicine*, 167(4), 268-274.
https://doi.org/10.7326/M16-2607

### Textbooks

VanderWeele, T.J. (2015). *Explanation in Causal Inference: Methods for Mediation
and Interaction*. Oxford University Press. ISBN: 978-0-19-932587-0.

MacKinnon, D.P. (2008). *Introduction to Statistical Mediation Analysis*. Routledge.
ISBN: 978-0-8058-6429-8.
