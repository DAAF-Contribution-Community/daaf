# Heckman Selection Models: Implementation Reference

Implementation reference for Heckman selection correction models using only installed
packages (statsmodels, scipy, numpy, polars). No dedicated Heckman package exists in
the Python ecosystem, and **statsmodels does not include a Heckman module** -- every
online tutorial showing `sm.heckman.Heckman()` is wrong. Everything must be built
manually from Probit, OLS, and scipy's normal distribution functions.

For the methodology behind selection bias correction -- when Heckman models are
appropriate vs. alternative approaches (matching, IV, bounds) -- see
`causal-inference.md` > "Method Selection Guide." This file focuses on **how to
implement** once you have determined that sample selection bias is the relevant threat.

## Contents

- [When to Use Heckman Selection Models](#when-to-use-heckman-selection-models)
- [Model Setup](#model-setup)
- [Manual Two-Step Estimation (Heckit)](#manual-two-step-estimation-heckit)
- [Bootstrap Inference](#bootstrap-inference)
- [Full Information Maximum Likelihood (FIML)](#full-information-maximum-likelihood-fiml)
- [Diagnostics](#diagnostics)
- [Complete Heckman Analysis Template](#complete-heckman-analysis-template)
- [Gotchas](#gotchas)
- [References](#references)

## When to Use Heckman Selection Models

Heckman selection models address **sample selection bias**: the outcome variable is
observed only for a non-random subset of the population. The classic example is
estimating a wage equation when wages are observed only for people who choose to work
-- the working population is not a random draw from all adults.

**Use Heckman when all three conditions hold:**
1. The outcome is observed only for a selected (non-random) subset
2. The selection process is correlated with unobservables that also affect the outcome
3. You have at least one variable (an "exclusion restriction") that predicts selection
   but does not directly affect the outcome

**Do NOT use Heckman when:**
- The outcome is observed for everyone (no selection) -- use standard regression
- Selection is on observables only -- matching/IPW is simpler and avoids the
  bivariate normality assumption (see `causal-matching.md`)
- You lack an exclusion restriction -- identification is fragile without one (see
  Gotcha #1)
- You are interested in treatment effects, not correcting for sample selection --
  use IV, DiD, or RD instead

**Common applications:**
- Wage equations (selection into employment)
- Earnings of migrants (selection into migration)
- Technology adoption and performance (selection into adoption)
- Insurance claims and amounts (selection into claiming)
- Academic performance conditional on enrollment

## Model Setup

### The Two-Equation System

**Selection equation** (estimated on the full sample):
```
D_i* = Z_i * gamma + u_i
D_i  = 1  if D_i* > 0
D_i  = 0  otherwise
```

**Outcome equation** (observed only when D_i = 1):
```
y_i = X_i * beta + epsilon_i
```

Where:
- D_i is the binary selection indicator (1 = observed, 0 = not observed)
- Z_i is the vector of selection equation covariates (must include X_i plus at
  least one excluded instrument)
- X_i is the vector of outcome equation covariates
- (u_i, epsilon_i) are jointly bivariate normal with correlation rho

The key insight (Heckman 1979): for the selected sample,

```
E[y_i | X_i, D_i = 1] = X_i * beta + rho * sigma * lambda(Z_i * gamma)
```

where lambda() is the inverse Mills ratio (IMR): lambda(a) = phi(a) / Phi(a),
with phi and Phi being the standard normal PDF and CDF respectively.

### Variable Requirements

| Variable set | Contents | Role |
|-------------|----------|------|
| Z_i (selection) | All predictors of selection, including X_i | Selection equation regressors |
| X_i (outcome) | Predictors of the outcome | Outcome equation regressors |
| Exclusion restriction | Variables in Z but NOT in X (at least one) | Identifies the model beyond functional form |

The exclusion restriction is the variable that predicts whether an observation is
selected but does not directly affect the outcome. For example, in a wage equation:
number of young children affects labor force participation but (arguably) not wage
rates conditional on working.

### Data Preparation

```python
import numpy as np
import polars as pl
import statsmodels.api as sm
from scipy.stats import norm

# --- Config ---
DATA_DIR = f"{PROJECT_DIR}/data"
OUTPUT_DIR = f"{PROJECT_DIR}/output"

# --- Load ---
df = pl.read_parquet(f"{DATA_DIR}/analysis_data.parquet")

# INTENT: Separate selection and outcome variables
# Selection equation: predict whether outcome is observed
# Outcome equation: model the outcome for observed cases

# Z columns: all predictors in the selection equation
# X columns: predictors in the outcome equation (subset of Z)
# Exclusion restriction: columns in Z but NOT in X

z_cols = ["age", "education", "married", "num_children", "region"]
x_cols = ["age", "education", "married", "region"]
excl_cols = ["num_children"]  # In Z but not X -- the exclusion restriction

# ASSUMES: num_children predicts labor force participation (selection)
# but does not directly affect wages (outcome) conditional on working

outcome_col = "log_wage"
selection_col = "employed"  # 1 = observed wage, 0 = not observed

# --- Prepare arrays ---
Z = sm.add_constant(df.select(z_cols).to_pandas())
X = sm.add_constant(df.select(x_cols).to_pandas())
D = df[selection_col].to_numpy()
y = df.filter(pl.col(selection_col) == 1)[outcome_col].to_numpy()

print(f"Full sample: {len(D)} observations")
print(f"Selected (D=1): {D.sum()} ({D.mean()*100:.1f}%)")
print(f"Not selected (D=0): {(1-D).sum()} ({(1-D).mean()*100:.1f}%)")
```

## Manual Two-Step Estimation (Heckit)

The Heckit procedure (Heckman 1979) estimates the model in two steps:

1. Estimate a Probit model on the full sample to get gamma-hat
2. Compute the inverse Mills ratio (IMR) for the selected subsample
3. Include the IMR as an additional regressor in the OLS outcome equation

### Step 1: Probit Selection Model

```python
# --- Step 1: Probit on full sample ---
# INTENT: Estimate selection equation via Probit on all observations
probit_model = sm.Probit(D, Z)
probit_result = probit_model.fit(disp=0)  # disp=0 suppresses optimizer output
print(probit_result.summary())

# Diagnostics: check that the exclusion restriction is significant
for col in excl_cols:
    coef = probit_result.params[col]
    pval = probit_result.pvalues[col]
    print(f"Exclusion restriction '{col}': coef={coef:.4f}, p={pval:.4f}")
    assert pval < 0.10, (
        f"Exclusion restriction '{col}' is not significant (p={pval:.4f}). "
        "Weak exclusion restriction makes Heckman correction unreliable."
    )
```

### Step 2: Compute the Inverse Mills Ratio

```python
# --- Step 2: Compute inverse Mills ratio ---
# INTENT: Get the linear predictor (Z * gamma-hat) and compute IMR
# REASONING: The which="linear" argument returns Z*gamma instead of Phi(Z*gamma)

probit_xb = probit_result.predict(Z, which="linear")  # Z * gamma-hat (linear index)

# Inverse Mills ratio: lambda(a) = phi(a) / Phi(a)
# ASSUMES: Selection follows a Probit model (normality of u_i)
imr = norm.pdf(probit_xb) / norm.cdf(probit_xb)

# Extract IMR for the selected subsample only
selected_mask = D == 1
imr_selected = imr[selected_mask]

print(f"IMR range (selected): [{imr_selected.min():.4f}, {imr_selected.max():.4f}]")
print(f"IMR mean (selected):  {imr_selected.mean():.4f}")
print(f"IMR std (selected):   {imr_selected.std():.4f}")
```

### Step 3: OLS with IMR

```python
# --- Step 3: OLS outcome regression with IMR ---
# INTENT: Estimate outcome equation on selected sample, including IMR
# REASONING: If rho != 0 (selection bias exists), IMR coefficient will be
# significant and the beta estimates will be corrected for selection

X_selected = X.loc[selected_mask].copy()
X_selected["imr"] = imr_selected

ols_model = sm.OLS(y, X_selected)
ols_result = ols_model.fit()
print(ols_result.summary())

# --- Extract key results ---
beta_hat = ols_result.params.drop("imr")
imr_coef = ols_result.params["imr"]  # This is rho * sigma
imr_pval = ols_result.pvalues["imr"]

print(f"\n=== Heckman Two-Step Results ===")
print(f"IMR coefficient (rho*sigma): {imr_coef:.4f}")
print(f"IMR p-value: {imr_pval:.4f}")
if imr_pval < 0.05:
    print("Selection bias IS significant -- Heckman correction is warranted")
else:
    print("Selection bias NOT significant -- OLS without correction may suffice")
    print("(Heckman correction can increase MSE when selection is weak; see Puhani 2000)")
```

### Step 4: Compare with Naive OLS

```python
# --- Compare: naive OLS (no selection correction) ---
# INTENT: Show the bias from ignoring selection
ols_naive = sm.OLS(y, X.loc[selected_mask]).fit()

print(f"\n=== Coefficient Comparison ===")
print(f"{'Variable':20s}  {'Naive OLS':>12s}  {'Heckman':>12s}  {'Difference':>12s}")
for col in x_cols + ["const"]:
    naive = ols_naive.params[col]
    heck = beta_hat[col]
    diff = heck - naive
    print(f"{col:20s}  {naive:12.4f}  {heck:12.4f}  {diff:12.4f}")
# REASONING: Large differences between naive OLS and Heckman indicate
# substantial selection bias. Small differences suggest selection may not
# be a serious concern in this application.
```

## Bootstrap Inference

**The two-step Heckman standard errors from OLS are inconsistent.** They understate
uncertainty because they ignore that the IMR is a generated regressor (its sampling
variability is not accounted for in the second-stage OLS standard errors). Murphy
and Topel (1985) provide an analytical correction, but bootstrap is simpler and
more widely applicable.

Bootstrap over **both stages** -- re-estimate the Probit, recompute the IMR, and
re-estimate the OLS on each bootstrap resample.

```python
# --- Bootstrap inference for two-step Heckman ---
# INTENT: Obtain valid standard errors by bootstrapping the entire procedure
# REASONING: OLS SEs from step 3 are too small because they treat the IMR
# as fixed, ignoring estimation error from the Probit step

n = len(D)
n_boot = 1000
boot_betas = []

np.random.seed(42)

for b in range(n_boot):
    # Resample the FULL dataset (both selected and non-selected)
    idx = np.random.choice(n, size=n, replace=True)
    D_b = D[idx]
    Z_b = Z.iloc[idx]
    X_b = X.iloc[idx]

    # Skip resamples with no variation in selection
    if D_b.sum() < 10 or (1 - D_b).sum() < 10:
        continue

    # Step 1b: Probit on bootstrap sample
    try:
        probit_b = sm.Probit(D_b, Z_b).fit(disp=0, maxiter=100)
    except Exception:
        continue  # Skip failed convergence

    # Step 2b: IMR on bootstrap sample
    xb_b = probit_b.predict(Z_b, which="linear")
    imr_b = norm.pdf(xb_b) / norm.cdf(xb_b)

    # Step 3b: OLS with IMR on selected subsample
    sel_b = D_b == 1
    y_b = y[np.where(selected_mask)[0][np.isin(np.where(selected_mask)[0], idx[sel_b])]]

    # Simpler: rebuild from the bootstrap indices
    # Get outcome values for selected observations in bootstrap sample
    full_y = df[outcome_col].to_numpy()
    y_b = full_y[idx[sel_b]]
    X_b_sel = X_b.iloc[sel_b].copy()
    X_b_sel["imr"] = imr_b[sel_b]

    if len(y_b) < X_b_sel.shape[1] + 5:
        continue  # Too few observations

    try:
        ols_b = sm.OLS(y_b, X_b_sel).fit()
        boot_betas.append(ols_b.params.drop("imr").values)
    except Exception:
        continue

boot_betas = np.array(boot_betas)
print(f"Successful bootstrap iterations: {len(boot_betas)} / {n_boot}")

# Bootstrap standard errors and confidence intervals
boot_se = boot_betas.std(axis=0)
boot_ci_lower = np.percentile(boot_betas, 2.5, axis=0)
boot_ci_upper = np.percentile(boot_betas, 97.5, axis=0)

col_names = [c for c in X.columns if c != "imr"]
print(f"\n=== Bootstrap Inference ===")
print(f"{'Variable':20s}  {'Estimate':>10s}  {'Boot SE':>10s}  {'CI Lower':>10s}  {'CI Upper':>10s}")
for i, col in enumerate(col_names):
    est = beta_hat.iloc[i]
    print(f"{col:20s}  {est:10.4f}  {boot_se[i]:10.4f}  "
          f"{boot_ci_lower[i]:10.4f}  {boot_ci_upper[i]:10.4f}")
```

## Full Information Maximum Likelihood (FIML)

FIML estimates all parameters jointly by maximizing the full log-likelihood of the
bivariate selection model. It is more efficient than two-step when the normality
assumption holds, but harder to implement and more sensitive to misspecification.

### Log-Likelihood

The log-likelihood has two components:

For selected observations (D_i = 1):
```
log L_i = log phi((y_i - X_i*beta) / sigma)  - log(sigma)
        + log Phi((Z_i*gamma + rho*(y_i - X_i*beta)/sigma) / sqrt(1 - rho^2))
```

For non-selected observations (D_i = 0):
```
log L_i = log Phi(-Z_i*gamma)
```

### Implementation with scipy.optimize

```python
from scipy.optimize import minimize
from scipy.stats import norm

# --- FIML Heckman ---
# INTENT: Joint estimation of selection and outcome equations
# REASONING: More efficient than two-step but requires stronger assumptions

# Prepare data
Z_arr = Z.values.astype(float)
X_sel_arr = X.loc[selected_mask].values.astype(float)
y_arr = y.astype(float)
D_arr = D.astype(float)

# Dimensions
k_z = Z_arr.shape[1]  # Number of selection equation params
k_x = X_sel_arr.shape[1]  # Number of outcome equation params

def heckman_loglik(params):
    """Negative log-likelihood for Heckman selection model."""
    gamma = params[:k_z]
    beta = params[k_z:k_z + k_x]
    log_sigma = params[k_z + k_x]  # Log-transform for positivity
    atanh_rho = params[k_z + k_x + 1]  # Arctanh-transform for (-1, 1)

    sigma = np.exp(log_sigma)
    rho = np.tanh(atanh_rho)

    # Selection index for all observations
    Zg = Z_arr @ gamma

    # Log-likelihood for non-selected (D=0)
    ll_0 = norm.logcdf(-Zg[D_arr == 0]).sum()

    # Log-likelihood for selected (D=1)
    resid = (y_arr - X_sel_arr @ beta) / sigma
    adj = (Zg[D_arr == 1] + rho * resid) / np.sqrt(1 - rho**2)

    ll_1 = (
        norm.logpdf(resid).sum()
        - len(y_arr) * log_sigma
        + norm.logcdf(adj).sum()
    )

    return -(ll_0 + ll_1)  # Negative because we minimize

# --- Starting values from two-step ---
# INTENT: Initialize FIML with two-step estimates for faster convergence
gamma_init = probit_result.params.values
beta_init = ols_result.params.drop("imr").values
sigma_init = np.log(ols_result.resid.std())
rho_init = np.arctanh(np.clip(imr_coef / np.exp(sigma_init), -0.95, 0.95))

x0 = np.concatenate([gamma_init, beta_init, [sigma_init], [rho_init]])

# Optimize
fiml_result = minimize(
    heckman_loglik,
    x0,
    method="L-BFGS-B",
    options={"maxiter": 5000, "ftol": 1e-12},
)

if not fiml_result.success:
    print(f"WARNING: FIML optimization did not converge: {fiml_result.message}")
else:
    print("FIML converged successfully")

# --- Extract FIML estimates ---
gamma_fiml = fiml_result.x[:k_z]
beta_fiml = fiml_result.x[k_z:k_z + k_x]
sigma_fiml = np.exp(fiml_result.x[k_z + k_x])
rho_fiml = np.tanh(fiml_result.x[k_z + k_x + 1])

print(f"\n=== FIML Estimates ===")
print(f"sigma: {sigma_fiml:.4f}")
print(f"rho:   {rho_fiml:.4f}")

col_names = list(X.columns)
print(f"\n{'Variable':20s}  {'Two-Step':>10s}  {'FIML':>10s}")
for i, col in enumerate(col_names):
    print(f"{col:20s}  {beta_hat.iloc[i]:10.4f}  {beta_fiml[i]:10.4f}")
```

### FIML Standard Errors

FIML standard errors come from the inverse of the observed information matrix
(Hessian). scipy's `minimize` can approximate this numerically:

```python
from scipy.optimize import approx_fprime

# --- Numerical Hessian for FIML SEs ---
# INTENT: Compute standard errors from inverse Hessian at FIML optimum
n_params = len(fiml_result.x)
eps = 1e-5
hessian = np.zeros((n_params, n_params))

for i in range(n_params):
    def grad_i(params):
        return approx_fprime(params, heckman_loglik, eps)[i]
    hessian[i, :] = approx_fprime(fiml_result.x, grad_i, eps)

# Variance-covariance matrix = inverse of Hessian (for negative log-likelihood)
try:
    vcov = np.linalg.inv(hessian)
    fiml_se = np.sqrt(np.diag(vcov))

    print(f"\n=== FIML Standard Errors ===")
    param_names = list(Z.columns) + list(X.columns) + ["log_sigma", "atanh_rho"]
    for i, name in enumerate(param_names):
        est = fiml_result.x[i]
        se = fiml_se[i]
        z_stat = est / se
        pval = 2 * (1 - norm.cdf(abs(z_stat)))
        print(f"{name:20s}  {est:10.4f}  ({se:8.4f})  z={z_stat:7.3f}  p={pval:.4f}")
except np.linalg.LinAlgError:
    print("WARNING: Hessian is singular -- FIML SEs cannot be computed")
    print("This often indicates identification problems or near-boundary rho")
```

### FIML Likelihood Ratio Test for Selection Bias

```python
# --- LR test: rho = 0 ---
# INTENT: Test whether selection bias exists (rho = 0 vs rho != 0)
# REASONING: More powerful than the two-step t-test on the IMR coefficient

# Restricted model: rho = 0 (equivalent to separate Probit + OLS)
x0_restricted = x0.copy()
x0_restricted[-1] = 0.0  # Fix atanh(rho) = 0 => rho = 0

# Minimize with rho fixed at zero
from scipy.optimize import minimize

def heckman_loglik_rho0(params_short):
    """Log-likelihood with rho constrained to zero."""
    params_full = np.concatenate([params_short, [0.0]])
    return heckman_loglik(params_full)

fiml_restricted = minimize(
    heckman_loglik_rho0,
    x0_restricted[:-1],
    method="L-BFGS-B",
    options={"maxiter": 5000, "ftol": 1e-12},
)

lr_stat = 2 * (fiml_restricted.fun - fiml_result.fun)
lr_pval = 1 - norm.cdf(np.sqrt(abs(lr_stat)))  # chi2(1) approximation
# More precisely: from scipy.stats import chi2; lr_pval = 1 - chi2.cdf(lr_stat, df=1)
from scipy.stats import chi2
lr_pval = 1 - chi2.cdf(lr_stat, df=1)

print(f"\n=== LR Test for Selection Bias (H0: rho = 0) ===")
print(f"LR statistic: {lr_stat:.4f}")
print(f"p-value (chi2, df=1): {lr_pval:.4f}")
if lr_pval < 0.05:
    print("Reject H0: significant selection bias detected")
else:
    print("Fail to reject H0: no evidence of selection bias")
```

## Diagnostics

### 1. Test for Selection Bias

The most important diagnostic: is the selection correction actually needed?

| Approach | How | Interpretation |
|----------|-----|----------------|
| Two-step: IMR t-test | Test significance of IMR coefficient in step 3 | p < 0.05 suggests selection bias |
| FIML: LR test | Compare unrestricted (rho free) vs restricted (rho=0) | LR stat ~ chi2(1) |
| FIML: Wald test on rho | Test atanh(rho) = 0 using FIML SE | z-test on transformed rho |
| Compare OLS vs Heckman | Large coefficient differences suggest bias | Informal but informative |

If the test fails to reject H0 (no selection bias), **prefer naive OLS**. Heckman
correction adds noise when selection bias is absent (Puhani 2000).

### 2. Check Exclusion Restriction Strength

```python
# --- Exclusion restriction diagnostics ---
# INTENT: Verify the exclusion restriction is predictive in the selection equation
# REASONING: A weak exclusion restriction makes the IMR collinear with X

# Partial F-test: does the exclusion restriction add predictive power?
# Compare full Probit (with exclusion vars) vs restricted (without)
z_cols_restricted = [c for c in z_cols if c not in excl_cols]
Z_restricted = sm.add_constant(df.select(z_cols_restricted).to_pandas())
probit_restricted = sm.Probit(D, Z_restricted).fit(disp=0)

lr_excl = 2 * (probit_restricted.llf - probit_result.llf)
# Note: signs -- llf is log-likelihood (negative); more negative = worse fit
lr_excl = -2 * (probit_restricted.llf - probit_result.llf)
excl_pval = 1 - chi2.cdf(lr_excl, df=len(excl_cols))

print(f"LR test for exclusion restriction: {lr_excl:.4f} (p={excl_pval:.4f})")
if excl_pval > 0.10:
    print("WARNING: Exclusion restriction is weak -- Heckman identification is fragile")
```

### 3. Check IMR Collinearity

```python
# --- VIF check for IMR collinearity ---
# INTENT: Verify the IMR is not collinear with outcome covariates
# REASONING: High collinearity makes the Heckman correction unreliable
# even with a valid exclusion restriction

from statsmodels.stats.outliers_influence import variance_inflation_factor

X_with_imr = X_selected.copy()  # From step 3
vif_data = []
for i, col in enumerate(X_with_imr.columns):
    vif = variance_inflation_factor(X_with_imr.values, i)
    vif_data.append({"variable": col, "VIF": round(vif, 2)})

vif_df = pl.DataFrame(vif_data)
print(vif_df)

imr_vif = [v for v in vif_data if v["variable"] == "imr"][0]["VIF"]
if imr_vif > 10:
    print(f"WARNING: IMR VIF = {imr_vif:.1f} -- severe collinearity")
    print("Heckman correction is unreliable. Consider:")
    print("  1. Strengthening the exclusion restriction")
    print("  2. Using FIML instead of two-step")
    print("  3. Reconsidering whether Heckman is appropriate")
elif imr_vif > 5:
    print(f"CAUTION: IMR VIF = {imr_vif:.1f} -- moderate collinearity")
```

### 4. Sensitivity to Exclusion Restriction

```python
# --- Sensitivity: compare estimates with different exclusion restrictions ---
# INTENT: Check that results are robust to the choice of exclusion restriction
# REASONING: If results change substantially, identification is fragile

alt_excl_vars = [["num_children"], ["num_children", "spouse_income"]]

sensitivity_results = []
for excl_set in alt_excl_vars:
    z_set = x_cols + excl_set
    Z_alt = sm.add_constant(df.select(z_set).to_pandas())

    probit_alt = sm.Probit(D, Z_alt).fit(disp=0)
    xb_alt = probit_alt.predict(Z_alt, which="linear")
    imr_alt = norm.pdf(xb_alt) / norm.cdf(xb_alt)

    X_sel_alt = X.loc[selected_mask].copy()
    X_sel_alt["imr"] = imr_alt[selected_mask]
    ols_alt = sm.OLS(y, X_sel_alt).fit()

    sensitivity_results.append({
        "exclusion_vars": ", ".join(excl_set),
        "imr_coef": round(ols_alt.params["imr"], 4),
        "imr_pval": round(ols_alt.pvalues["imr"], 4),
    })

sens_df = pl.DataFrame(sensitivity_results)
print(sens_df)
# REASONING: Estimates that are stable across different valid exclusion
# restrictions provide stronger evidence that the correction is reliable.
```

## Complete Heckman Analysis Template

This template provides the full estimation and diagnostic sequence, suitable for
adaptation into a DAAF pipeline script.

```python
# --- Config ---
import numpy as np
import polars as pl
import statsmodels.api as sm
from scipy.stats import norm, chi2

OUTCOME_COL = "log_wage"
SELECTION_COL = "employed"
Z_COLS = ["age", "education", "married", "num_children", "region"]
X_COLS = ["age", "education", "married", "region"]
EXCL_COLS = ["num_children"]
N_BOOT = 1000

# --- Load ---
df = pl.read_parquet(f"{DATA_DIR}/analysis_data.parquet")

# --- Prepare ---
Z = sm.add_constant(df.select(Z_COLS).to_pandas())
X = sm.add_constant(df.select(X_COLS).to_pandas())
D = df[SELECTION_COL].to_numpy()
full_y = df[OUTCOME_COL].to_numpy()
selected_mask = D == 1
y = full_y[selected_mask]

print(f"Total N: {len(D)}")
print(f"Selected: {D.sum()} ({D.mean()*100:.1f}%)")
print(f"Not selected: {(1-D).sum()}")

# --- Step 1: Probit ---
probit = sm.Probit(D, Z).fit(disp=0)
print(probit.summary())

# --- Step 2: IMR ---
probit_xb = probit.predict(Z, which="linear")
imr = norm.pdf(probit_xb) / norm.cdf(probit_xb)

# --- Step 3: Heckman two-step ---
X_sel = X.loc[selected_mask].copy()
X_sel["imr"] = imr[selected_mask]
heckman = sm.OLS(y, X_sel).fit()
print(heckman.summary())

imr_coef = heckman.params["imr"]
imr_pval = heckman.pvalues["imr"]
print(f"\nIMR coef: {imr_coef:.4f}, p-value: {imr_pval:.4f}")

# --- Step 4: Naive OLS comparison ---
naive = sm.OLS(y, X.loc[selected_mask]).fit()
print(f"\n{'Variable':20s}  {'Naive OLS':>10s}  {'Heckman':>10s}")
for col in list(X.columns):
    print(f"{col:20s}  {naive.params[col]:10.4f}  {heckman.params[col]:10.4f}")

# --- Step 5: Bootstrap ---
n = len(D)
boot_betas = []
np.random.seed(42)
for b in range(N_BOOT):
    idx = np.random.choice(n, size=n, replace=True)
    D_b, Z_b, X_b = D[idx], Z.iloc[idx], X.iloc[idx]
    if D_b.sum() < 10 or (1-D_b).sum() < 10:
        continue
    try:
        prob_b = sm.Probit(D_b, Z_b).fit(disp=0, maxiter=100)
        xb_b = prob_b.predict(Z_b, which="linear")
        imr_b = norm.pdf(xb_b) / norm.cdf(xb_b)
        sel_b = D_b == 1
        y_b = full_y[idx[sel_b]]
        Xb_sel = X_b.iloc[sel_b].copy()
        Xb_sel["imr"] = imr_b[sel_b]
        ols_b = sm.OLS(y_b, Xb_sel).fit()
        boot_betas.append(ols_b.params.drop("imr").values)
    except Exception:
        continue

boot_betas = np.array(boot_betas)
boot_se = boot_betas.std(axis=0)
print(f"\nBootstrap SE ({len(boot_betas)} replications):")
for i, col in enumerate(X.columns):
    print(f"  {col:20s}  SE={boot_se[i]:.4f}")

# --- Step 6: Diagnostics ---
# VIF
from statsmodels.stats.outliers_influence import variance_inflation_factor
for i, col in enumerate(X_sel.columns):
    vif = variance_inflation_factor(X_sel.values, i)
    print(f"  VIF {col}: {vif:.2f}")

# --- Validate ---
print(f"\n=== Validation ===")
print(f"Total N: {len(D)}")
print(f"Selected N: {D.sum()}")
print(f"Selection rate: {D.mean()*100:.1f}%")
assert D.sum() > 50, f"Too few selected observations: {D.sum()}"
assert (1-D).sum() > 50, f"Too few non-selected observations: {(1-D).sum()}"
```

## Gotchas

### 1. The Exclusion Restriction Is Not Optional

Without at least one variable that appears in the selection equation but not the
outcome equation, the Heckman model is identified solely through the nonlinearity
of the inverse Mills ratio. This is a dangerous form of identification because:

- The IMR is nearly linear over the range (-1, 2), which covers most of the data
  for typical selection probabilities
- Near-linearity makes the IMR collinear with X, inflating standard errors and
  making the correction unstable
- Small specification changes (adding a covariate, changing functional form) can
  dramatically alter results

**Always use an exclusion restriction.** If you cannot find a credible one, the
Heckman model is likely not the right approach. Consider bounds analysis (Manski
1990) or sensitivity analysis instead.

### 2. Two-Step Standard Errors Are Wrong

The OLS standard errors from Step 3 of the Heckit procedure are **inconsistent**.
They treat the inverse Mills ratio as a known regressor rather than an estimated
quantity, ignoring the sampling variability from the first-stage Probit. This
underestimates uncertainty, sometimes substantially.

**Use bootstrap** (re-estimating both stages on each resample) as the default
inference approach. The Murphy-Topel (1985) analytical correction is an alternative
but harder to implement and less commonly used.

### 3. The Collinearity Trap

Even with a valid exclusion restriction, if the excluded variable has weak predictive
power in the selection equation, the IMR will be nearly collinear with the outcome
covariates X. Symptoms:

- Very large VIF for the IMR (> 10)
- Heckman standard errors much larger than OLS standard errors
- Estimates change dramatically with minor specification changes

Check VIF after estimation. If IMR VIF > 10, the correction is unreliable
regardless of whether the IMR coefficient is "significant."

### 4. Heckman Correction Can Increase MSE When Selection Is Weak

Puhani (2000) reviews the literature and finds that when selection bias is small
(rho close to zero), the Heckman correction can **increase** mean squared error
relative to naive OLS. The correction introduces additional noise through the
estimated IMR, and when the bias being corrected is small, this noise outweighs
the bias reduction.

**Decision rule:** If the IMR coefficient is not significant (or rho is close to
zero in FIML), report the naive OLS results as the primary specification and note
that the Heckman correction did not find evidence of selection bias.

### 5. `sm.heckman.Heckman()` Does Not Exist

Multiple online tutorials, blog posts, and even some textbooks show code like:

```python
# THIS DOES NOT WORK -- the API does not exist
import statsmodels as sm
result = sm.heckman.Heckman(y, X, Z).fit()  # ImportError
```

This API **does not exist** in statsmodels (as of v0.14.x). GitHub issue #1921
requesting this feature was opened in 2014 and remains open and unmerged as of
2026. There is no `statsmodels.heckman` module, no `Heckman` class, and no
`heckman` subpackage. Any code using this import will raise `ImportError` or
`AttributeError`.

You **must** implement the two-step procedure manually (Probit + OLS with IMR)
or write the FIML log-likelihood by hand, as shown in this reference.

### 6. The Bivariate Normality Assumption Is Strong and Untestable

The Heckman model assumes that the error terms (u_i, epsilon_i) are jointly
bivariate normal. This assumption is:

- **Strong:** It imposes a specific parametric form on the joint distribution of
  unobservables, ruling out heavy tails, skewness, or nonlinear dependence
- **Untestable:** Because epsilon_i is only observed for selected units and u_i
  is never observed directly, the joint distribution cannot be assessed from data
- **Consequential:** If violated, both two-step and FIML estimates are
  inconsistent -- the correction itself introduces bias

Robustness checks: (1) Compare two-step and FIML results -- large discrepancies
suggest sensitivity to distributional assumptions. (2) Compare with semiparametric
alternatives if available (e.g., Robinson 1988). (3) Try different functional forms
for the selection and outcome equations.

## References

### Core Papers

Heckman, J.J. (1979). "Sample Selection Bias as a Specification Error."
*Econometrica*, 47(1), 153-162. https://doi.org/10.2307/1912352

Robinson, P.M. (1988). "Root-N-Consistent Semiparametric Regression."
*Econometrica*, 56(4), 931-954. https://doi.org/10.2307/1912705

Heckman, J.J. (1976). "The Common Structure of Statistical Models of Truncation,
Sample Selection and Limited Dependent Variables and a Simple Estimator for Such
Models." *Annals of Economic and Social Measurement*, 5(4), 475-492.

### Inference

Murphy, K.M. and Topel, R.H. (1985). "Estimation and Inference in Two-Step
Econometric Models." *Journal of Business & Economic Statistics*, 3(4), 370-379.
https://doi.org/10.1080/07350015.1985.10509471

### Reviews and Critiques

Puhani, P.A. (2000). "The Heckman Correction for Sample Selection and Its Critique."
*Journal of Economic Surveys*, 14(1), 53-68.
https://doi.org/10.1111/1467-6419.00104

Toomet, O. and Henningsen, A. (2008). "Sample Selection Models in R: Package
sampleSelection." *Journal of Statistical Software*, 27(7), 1-23.
https://doi.org/10.18637/jss.v027.i07

### Textbooks

Wooldridge, J.M. (2010). *Econometric Analysis of Cross Section and Panel Data*,
2nd ed., Chapter 19. MIT Press. ISBN: 978-0-262-23258-6.

Cameron, A.C. and Trivedi, P.K. (2005). *Microeconometrics: Methods and
Applications*, Chapters 16 and 24. Cambridge University Press.

### Methodology (Additional)

Heckman, J.J. (1990). "Varieties of Selection Bias." *American Economic Review*,
80(2), 313-318.

Manski, C.F. (1990). "Nonparametric Bounds on Treatment Effects." *American
Economic Review*, 80(2), 319-323.
