# Causal Machine Learning Methods

Implementation reference for causal machine learning methods in Python: Double/
Debiased Machine Learning (DML), meta-learners for heterogeneous treatment
effects (CATE), and causal forests. Covers manual implementation with installed
packages (scikit-learn, statsmodels, pyfixest) plus API patterns for specialized
packages that require installation (EconML, DoubleML).

For methodology fundamentals (when to use causal ML, comparison with traditional
methods, the role of ML in the causal toolkit), see `./causal-inference.md` >
"Machine Learning for Causal Inference" and the Method Selection Guide.

## Contents

- [When to Use Causal ML](#when-to-use-causal-ml)
- [Key Concepts](#key-concepts)
- [Package Landscape](#package-landscape)
- [Manual DML: Partially Linear Model](#manual-dml-partially-linear-model)
- [Manual DML: Interactive Model (ATE)](#manual-dml-interactive-model-ate)
- [Meta-Learners: S-Learner (Manual)](#meta-learners-s-learner-manual)
- [Meta-Learners: T-Learner (Manual)](#meta-learners-t-learner-manual)
- [EconML Patterns](#econml-patterns)
- [DoubleML Patterns](#doubleml-patterns)
- [Causal Forests](#causal-forests)
- [Diagnostics and Validation](#diagnostics-and-validation)
- [Gotchas and Pitfalls](#gotchas-and-pitfalls)
- [Decision Tree: Which Approach?](#decision-tree-which-approach)
- [References](#references)

## When to Use Causal ML

Causal ML methods are designed for two distinct goals within a valid causal design:

| Goal | Methods | When to Use |
|------|---------|-------------|
| **ATE/ATT with flexible nuisance** | DML (partially linear model) | Many potential confounders; want to avoid functional form assumptions in nuisance estimation while preserving root-n inference for the causal parameter |
| **Treatment effect heterogeneity** | Meta-learners, causal forests, DML (interactive model) | After establishing a credible causal effect, explore how the effect varies across subpopulations (CATE estimation) |

**When NOT to use causal ML:**
- As a substitute for a valid research design -- ML handles nuisance estimation
  and heterogeneity exploration, not identification
- When the covariate space is moderate and well-understood -- traditional
  regression with hand-selected controls may be more transparent and sufficient
- For discovery of causal relationships from observational data -- causal ML
  estimates conditional effects, it does not discover causal structure
- When sample size is small -- cross-fitting and ML nuisance models need
  sufficient data in each fold

## Key Concepts

### CATE: Conditional Average Treatment Effect

CATE is the treatment effect conditional on observed characteristics:

```
CATE(x) = E[Y(1) - Y(0) | X = x]
```

This captures how the treatment effect varies across subpopulations defined by
covariates X. The ATE is the unconditional expectation of CATE: ATE = E[CATE(X)].

CATE is the target quantity for treatment effect heterogeneity analysis -- it
answers "who benefits most from treatment?" rather than "what is the average
effect?"

### Double/Debiased Machine Learning (DML)

Chernozhukov et al. (2018) developed DML to solve a fundamental tension: ML
models are good at prediction but produce biased estimates of causal parameters
because regularization bias does not vanish at root-n rates. DML resolves this
through two key ideas:

**1. Neyman orthogonality:** Construct a moment condition for the causal
parameter that is insensitive (to first order) to errors in nuisance function
estimation. This "orthogonalization" ensures that the regularization bias from ML
nuisance estimates does not contaminate inference on the causal parameter.

**2. Cross-fitting:** Split the sample into K folds. For each fold, estimate
nuisance functions on the other K-1 folds and compute residuals on the held-out
fold. This avoids overfitting bias that arises when the same data is used for
both nuisance estimation and causal parameter estimation.

**The partially linear model** is the most common DML specification:

```
Y = theta * D + g(X) + epsilon     (outcome equation)
D = m(X) + U                       (treatment equation)
```

where theta is the causal parameter of interest, g(X) is the outcome nuisance
function, and m(X) is the treatment nuisance function (propensity score for
binary treatment). The algorithm:

1. Split data into K folds (typically K=5)
2. For each fold k:
   a. Fit ML models for g(X) = E[Y|X] and m(X) = E[D|X] on all folds except k
   b. Predict on fold k to get residuals: V_hat = Y - g_hat(X), U_hat = D - m_hat(X)
3. Estimate theta from the pooled residuals: theta = sum(U_hat * V_hat) / sum(U_hat^2)
4. Compute standard errors accounting for the cross-fitting structure

### Meta-Learners

Meta-learners estimate CATE by combining predictions from standard ML models
(the "base learners") in specific ways. The prefix indicates the estimation
strategy:

| Learner | Strategy | Bias-Variance | Best When |
|---------|----------|---------------|-----------|
| **S-learner** | Single model on (X, D), CATE = mu(x,1) - mu(x,0) | High bias, low variance | Large samples; weak heterogeneity |
| **T-learner** | Separate models per treatment arm | Low bias, high variance | Balanced treatment arms; strong heterogeneity |
| **X-learner** | Impute individual treatment effects, then cross-estimate | Adaptive | Imbalanced groups (many controls, few treated) |
| **R-learner** | Neyman-orthogonal loss minimization | Low bias | Valid causal design; moderate sample |
| **DR-learner** | Doubly robust pseudo-outcomes | Low bias | Valid causal design; robustness desired |

S-learner and T-learner can be implemented manually with installed packages.
X-learner, R-learner, and DR-learner with valid inference require EconML or
CausalML.

### Causal Forests

Wager and Athey (2018) adapted random forests to estimate CATE with valid
pointwise confidence intervals. Key design differences from standard random
forests:

- **Honesty:** Each tree uses separate subsamples for splitting (finding the
  partition) and estimation (computing treatment effects within leaves). This
  prevents the adaptive bias that occurs when the same data determines both
  the partition and the estimates.
- **Subsampling (not bootstrap):** Trees are grown on subsamples drawn without
  replacement. This is necessary for the asymptotic normality result that
  enables valid confidence intervals.
- **Treatment effect splitting:** Splits are chosen to maximize heterogeneity in
  treatment effects across child nodes, not to minimize prediction error.

Causal forests require either EconML (`CausalForestDML`) or the R `grf` package
(gold standard, no Python port). Neither is installed by default.

## Package Landscape

**No causal ML package is currently installed in the DAAF environment.** The
manual implementations below use only installed dependencies (scikit-learn,
statsmodels, pyfixest). All package-based approaches require user installation.

| Package | Install | Strengths | Best For |
|---------|---------|-----------|----------|
| **EconML** | `pip install econml` | DML, CausalForestDML, meta-learners (S/T/X/DR), CATE inference, policy learning | General causal ML; CATE with CIs |
| **DoubleML** | `pip install doubleml` | Dedicated DML; clean API; sensitivity analysis; strong docs | Focused DML estimation |
| **CausalML** | `pip install causalml` | Meta-learners, uplift modeling, CATE visualization | Marketing/uplift; meta-learner variety |
| **DoWhy** | `pip install dowhy` | Causal graph framework; refutation tests; sensitivity | Causal reasoning pipeline |
| *scikit-learn (manual)* | *Already installed* | KFold, regressors, classifiers for nuisance | Manual DML; S/T-learner |
| *statsmodels (manual)* | *Already installed* | OLS for final stage; SE computation | Manual DML final stage |
| *pyfixest (manual)* | *Already installed* | Clustered SEs; FE in final stage | Manual DML with clustered data |

## Manual DML: Partially Linear Model

This implementation estimates the ATE (theta) in the partially linear model
Y = theta * D + g(X) + epsilon using only installed packages. It follows the
Chernozhukov et al. (2018) algorithm exactly.

### Step 1: Data Setup

```python
import numpy as np
import polars as pl
from sklearn.model_selection import KFold
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier

# --- Config ---
N_FOLDS = 5
RANDOM_STATE = 42
OUTCOME_COL = "outcome"
TREATMENT_COL = "treatment"  # Binary (0/1) or continuous
COVARIATE_COLS = ["x1", "x2", "x3", "x4", "x5"]

# --- Load ---
df = pl.read_parquet("path/to/analysis_data.parquet")

# Extract numpy arrays
Y = df[OUTCOME_COL].to_numpy().astype(float)
D = df[TREATMENT_COL].to_numpy().astype(float)
X = df[COVARIATE_COLS].to_numpy().astype(float)

n = len(Y)
print(f"Sample size: {n}")
print(f"Treatment prevalence: {D.mean():.3f}")
print(f"Covariates: {len(COVARIATE_COLS)}")
```

### Step 2: Cross-Fitted Residualization

```python
# --- Cross-fitting: residualize Y and D on X ---
# INTENT: Estimate nuisance functions g(X)=E[Y|X] and m(X)=E[D|X] using
#   cross-fitting to avoid overfitting bias
# REASONING: Each observation's residuals are computed from models trained on
#   OTHER observations, preventing the regularization bias that would arise
#   from using the full sample

V_hat = np.full(n, np.nan)  # Y residuals: Y - g_hat(X)
U_hat = np.full(n, np.nan)  # D residuals: D - m_hat(X)

kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

for fold_idx, (train_idx, test_idx) in enumerate(kf.split(X)):
    # --- Outcome model: g(X) = E[Y|X] ---
    # REASONING: HistGradientBoosting handles missing values, high dimensions,
    #   and nonlinear relationships without manual tuning
    model_y = HistGradientBoostingRegressor(
        max_iter=200, max_depth=5, learning_rate=0.1,
        random_state=RANDOM_STATE,
    )
    model_y.fit(X[train_idx], Y[train_idx])
    g_hat = model_y.predict(X[test_idx])
    V_hat[test_idx] = Y[test_idx] - g_hat

    # --- Treatment model: m(X) = E[D|X] ---
    # ASSUMES: Binary treatment uses classifier; continuous uses regressor
    if np.array_equal(np.unique(D), [0, 1]):
        model_d = HistGradientBoostingClassifier(
            max_iter=200, max_depth=5, learning_rate=0.1,
            random_state=RANDOM_STATE,
        )
        model_d.fit(X[train_idx], D[train_idx])
        m_hat = model_d.predict_proba(X[test_idx])[:, 1]
    else:
        model_d = HistGradientBoostingRegressor(
            max_iter=200, max_depth=5, learning_rate=0.1,
            random_state=RANDOM_STATE,
        )
        model_d.fit(X[train_idx], D[train_idx])
        m_hat = model_d.predict(X[test_idx])

    U_hat[test_idx] = D[test_idx] - m_hat

    print(f"Fold {fold_idx + 1}: "
          f"Y model R2={model_y.score(X[test_idx], Y[test_idx]):.3f}, "
          f"D resid mean={U_hat[test_idx].mean():.4f}")

# Validate: no NaN residuals
assert not np.any(np.isnan(V_hat)), "NaN in Y residuals"
assert not np.any(np.isnan(U_hat)), "NaN in D residuals"
print(f"\nResiduals computed for all {n} observations")
```

### Step 3: Estimate Theta and Standard Errors

```python
# --- DML estimator: theta = sum(U_hat * V_hat) / sum(U_hat^2) ---
# INTENT: Estimate the causal parameter from the orthogonalized residuals
# REASONING: This is the Frisch-Waugh-Lovell theorem applied to the
#   cross-fitted residuals — regressing Y-residuals on D-residuals

theta_hat = np.sum(U_hat * V_hat) / np.sum(U_hat ** 2)

# --- Standard error: accounts for estimation uncertainty ---
# REASONING: The influence function psi_i = U_hat_i * (V_hat_i - theta * U_hat_i)
#   provides the basis for the sandwich-style variance estimator
psi = U_hat * (V_hat - theta_hat * U_hat)
var_theta = np.mean(psi ** 2) / (np.mean(U_hat ** 2) ** 2) / n
se_theta = np.sqrt(var_theta)

# Inference
z_stat = theta_hat / se_theta
from scipy.stats import norm
p_value = 2 * (1 - norm.cdf(np.abs(z_stat)))
ci_lower = theta_hat - 1.96 * se_theta
ci_upper = theta_hat + 1.96 * se_theta

print(f"\n=== DML Estimate (Partially Linear Model) ===")
print(f"theta_hat:  {theta_hat:.4f}")
print(f"SE:         {se_theta:.4f}")
print(f"z-stat:     {z_stat:.2f}")
print(f"p-value:    {p_value:.4f}")
print(f"95% CI:     [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"N:          {n}")
print(f"Folds:      {N_FOLDS}")
```

### Step 4: Verification with OLS on Residuals

```python
# --- Cross-check: OLS regression of V_hat on U_hat should match ---
# INTENT: Verify the closed-form DML estimate matches a regression approach
# REASONING: Both should produce the same point estimate; OLS provides
#   an alternative SE calculation for comparison
import statsmodels.api as sm

ols_result = sm.OLS(V_hat, U_hat).fit(cov_type="HC1")
print(f"\nOLS cross-check:")
print(f"  Coefficient: {ols_result.params[0]:.4f} (DML: {theta_hat:.4f})")
print(f"  HC1 SE:      {ols_result.bse[0]:.4f} (DML: {se_theta:.4f})")
print(f"  p-value:     {ols_result.pvalues[0]:.4f}")
```

### Alternative Final Stage: pyfixest (Clustered SEs)

```python
# --- Final stage with pyfixest for clustered standard errors ---
# INTENT: When data has clustering structure (e.g., students within schools),
#   standard DML SEs are too small — use clustered SEs
# ASSUMES: cluster_var identifies the clustering unit

import pyfixest as pf

resid_df = pl.DataFrame({
    "V_hat": V_hat,
    "U_hat": U_hat,
    "cluster_id": df["school_id"].to_numpy(),
})

fit = pf.feols("V_hat ~ U_hat - 1", data=resid_df, vcov={"CRV1": "cluster_id"})
print(fit.summary())
# REASONING: The point estimate is identical; only the SEs differ.
# Clustered SEs account for within-cluster correlation of the DML
# influence function.
```

> **Note:** pyfixest always includes an intercept regardless of `- 1` syntax in
> the formula (unlike R's `fixest`). This does not affect the point estimate on
> `U_hat` (because DML residuals have mean near zero), but be aware that
> `fit.coef()` includes both `Intercept` and `U_hat`. Extract the treatment
> coefficient by name: `fit.coef()["U_hat"]`.

### Sensitivity to ML Model Choice

```python
# --- Robustness: compare nuisance model specifications ---
# INTENT: DML estimates should be stable across reasonable nuisance model choices
# REASONING: If theta changes substantially with different ML models, either
#   the models fit poorly (check R2) or the partially linear specification
#   is misspecified

from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LassoCV, LogisticRegressionCV

nuisance_specs = {
    "HistGBR": (HistGradientBoostingRegressor(random_state=42),
                HistGradientBoostingClassifier(random_state=42)),
    "RandomForest": (RandomForestRegressor(n_estimators=200, random_state=42),
                     RandomForestClassifier(n_estimators=200, random_state=42)),
    "Lasso/Logistic": (LassoCV(cv=5, random_state=42),
                       LogisticRegressionCV(cv=5, random_state=42)),
}

results = []
for name, (y_model, d_model) in nuisance_specs.items():
    V_r = np.full(n, np.nan)
    U_r = np.full(n, np.nan)
    kf_r = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    for train_idx, test_idx in kf_r.split(X):
        y_m = y_model.__class__(**y_model.get_params())
        y_m.fit(X[train_idx], Y[train_idx])
        V_r[test_idx] = Y[test_idx] - y_m.predict(X[test_idx])

        d_m = d_model.__class__(**d_model.get_params())
        d_m.fit(X[train_idx], D[train_idx])
        if hasattr(d_m, "predict_proba"):
            U_r[test_idx] = D[test_idx] - d_m.predict_proba(X[test_idx])[:, 1]
        else:
            U_r[test_idx] = D[test_idx] - d_m.predict(X[test_idx])

    theta_r = np.sum(U_r * V_r) / np.sum(U_r ** 2)
    psi_r = U_r * (V_r - theta_r * U_r)
    se_r = np.sqrt(np.mean(psi_r ** 2) / (np.mean(U_r ** 2) ** 2) / n)
    results.append({"model": name, "theta": round(theta_r, 4), "se": round(se_r, 4)})
    print(f"  {name}: theta={theta_r:.4f} (SE={se_r:.4f})")

# REASONING: Stability across specifications strengthens the result.
# Large variation suggests model-dependence — investigate which nuisance
# function is poorly estimated.
```

## Manual DML: Interactive Model (ATE)

The interactive model relaxes the partially linear restriction by allowing
treatment effect heterogeneity in the nuisance functions:

```
Y = g(D, X) + epsilon
```

where g(1, X) - g(0, X) = CATE(X). The ATE is estimated using the augmented
inverse propensity weighting (AIPW) score, which is the efficient influence
function for the ATE.

```python
# --- DML Interactive Model (AIPW-based ATE) ---
# INTENT: Estimate ATE without assuming a partially linear model
# REASONING: The AIPW score is doubly robust — consistent if either the
#   outcome model or the propensity score is correctly specified
# ASSUMES: Binary treatment (D in {0, 1})

mu1_hat = np.full(n, np.nan)  # E[Y|D=1, X]
mu0_hat = np.full(n, np.nan)  # E[Y|D=0, X]
e_hat = np.full(n, np.nan)    # P(D=1|X) -- propensity score

kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

for train_idx, test_idx in kf.split(X):
    # Outcome models: separate by treatment arm
    treated_mask = D[train_idx] == 1
    control_mask = D[train_idx] == 0

    model_y1 = HistGradientBoostingRegressor(
        max_iter=200, max_depth=5, random_state=RANDOM_STATE,
    )
    model_y1.fit(X[train_idx][treated_mask], Y[train_idx][treated_mask])
    mu1_hat[test_idx] = model_y1.predict(X[test_idx])

    model_y0 = HistGradientBoostingRegressor(
        max_iter=200, max_depth=5, random_state=RANDOM_STATE,
    )
    model_y0.fit(X[train_idx][control_mask], Y[train_idx][control_mask])
    mu0_hat[test_idx] = model_y0.predict(X[test_idx])

    # Propensity score model
    model_e = HistGradientBoostingClassifier(
        max_iter=200, max_depth=5, random_state=RANDOM_STATE,
    )
    model_e.fit(X[train_idx], D[train_idx])
    e_hat[test_idx] = model_e.predict_proba(X[test_idx])[:, 1]

# Clip propensity scores to avoid extreme weights
# REASONING: Propensity scores near 0 or 1 produce extreme IPW weights
#   that inflate variance. Trimming at 0.01/0.99 is standard practice.
e_hat_clipped = np.clip(e_hat, 0.01, 0.99)

# AIPW score for each observation
# REASONING: This is the efficient influence function for the ATE —
#   combines outcome modeling with IPW reweighting
aipw_score = (
    (mu1_hat - mu0_hat)
    + D * (Y - mu1_hat) / e_hat_clipped
    - (1 - D) * (Y - mu0_hat) / (1 - e_hat_clipped)
)

ate_hat = np.mean(aipw_score)
se_ate = np.std(aipw_score, ddof=1) / np.sqrt(n)

ci_lower = ate_hat - 1.96 * se_ate
ci_upper = ate_hat + 1.96 * se_ate

print(f"\n=== DML Interactive Model (AIPW ATE) ===")
print(f"ATE:    {ate_hat:.4f}")
print(f"SE:     {se_ate:.4f}")
print(f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"N:      {n}")
```

## Meta-Learners: S-Learner (Manual)

The S-learner (Single-model learner) fits one model with treatment as a feature.
CATE is estimated as the difference in predictions under D=1 and D=0.

```python
# --- S-Learner ---
# INTENT: Estimate CATE using a single model that includes treatment as a feature
# REASONING: Simple and stable, but biased toward zero when treatment effects
#   are small relative to the main effects — the model may ignore D entirely
#   if X dominates the predictions

# Construct feature matrix with treatment as a column
XD = np.column_stack([X, D])

model_s = HistGradientBoostingRegressor(
    max_iter=300, max_depth=5, learning_rate=0.1, random_state=RANDOM_STATE,
)
model_s.fit(XD, Y)

# CATE(x) = mu(x, 1) - mu(x, 0)
XD_1 = np.column_stack([X, np.ones(n)])   # Set D=1 for all
XD_0 = np.column_stack([X, np.zeros(n)])  # Set D=0 for all

cate_s = model_s.predict(XD_1) - model_s.predict(XD_0)

print(f"S-Learner CATE summary:")
print(f"  Mean (ATE):    {cate_s.mean():.4f}")
print(f"  Std:           {cate_s.std():.4f}")
print(f"  Min:           {cate_s.min():.4f}")
print(f"  Max:           {cate_s.max():.4f}")
print(f"  Median:        {np.median(cate_s):.4f}")

# REASONING: Check whether the model actually uses D — if CATE has near-zero
# variance, the model is effectively ignoring treatment status, which is the
# S-learner's known bias toward homogeneous effects.
```

## Meta-Learners: T-Learner (Manual)

The T-learner (Two-model learner) fits separate outcome models for treated and
control groups. CATE is the difference between the two predictions.

```python
# --- T-Learner ---
# INTENT: Estimate CATE using separate models for each treatment arm
# REASONING: Avoids the S-learner's bias toward zero, but introduces variance
#   from estimating two independent models — particularly when one group is small
# ASSUMES: Binary treatment

treated_mask = D == 1
control_mask = D == 0

print(f"T-Learner groups: treated={treated_mask.sum()}, control={control_mask.sum()}")

model_t1 = HistGradientBoostingRegressor(
    max_iter=300, max_depth=5, learning_rate=0.1, random_state=RANDOM_STATE,
)
model_t1.fit(X[treated_mask], Y[treated_mask])

model_t0 = HistGradientBoostingRegressor(
    max_iter=300, max_depth=5, learning_rate=0.1, random_state=RANDOM_STATE,
)
model_t0.fit(X[control_mask], Y[control_mask])

# CATE(x) = mu_1(x) - mu_0(x)
cate_t = model_t1.predict(X) - model_t0.predict(X)

print(f"\nT-Learner CATE summary:")
print(f"  Mean (ATE):    {cate_t.mean():.4f}")
print(f"  Std:           {cate_t.std():.4f}")
print(f"  Min:           {cate_t.min():.4f}")
print(f"  Max:           {cate_t.max():.4f}")
print(f"  Median:        {np.median(cate_t):.4f}")

# Cross-check: out-of-sample performance
from sklearn.model_selection import cross_val_score

r2_t1 = cross_val_score(model_t1, X[treated_mask], Y[treated_mask], cv=5).mean()
r2_t0 = cross_val_score(model_t0, X[control_mask], Y[control_mask], cv=5).mean()
print(f"\nNuisance model quality:")
print(f"  mu_1 CV R2: {r2_t1:.3f}")
print(f"  mu_0 CV R2: {r2_t0:.3f}")
# REASONING: Poor nuisance model fit makes CATE estimates unreliable.
# If R2 is low, the CATE reflects noise more than signal.
```

### Comparing S-Learner and T-Learner

```python
# --- Compare S and T learner CATE distributions ---
# REASONING: Agreement between the two methods strengthens confidence
#   in the heterogeneity pattern; disagreement signals sensitivity to
#   the estimation strategy

print(f"\nS vs T Learner comparison:")
print(f"  Correlation:  {np.corrcoef(cate_s, cate_t)[0, 1]:.3f}")
print(f"  Mean diff:    {(cate_s - cate_t).mean():.4f}")
print(f"  Max abs diff: {np.abs(cate_s - cate_t).max():.4f}")
# REASONING: High correlation with similar means suggests robust heterogeneity
# patterns. Low correlation suggests the estimated heterogeneity is fragile.
```

## EconML Patterns

**Install:** `pip install econml`

EconML (Microsoft/PyWhy) provides the most comprehensive causal ML toolkit in
Python. It implements DML, causal forests, meta-learners, and policy learning
with a unified API.

### DML (LinearDML)

```python
from econml.dml import LinearDML

# LinearDML: partially linear model with linear final stage
est = LinearDML(
    model_y=HistGradientBoostingRegressor(max_iter=200, random_state=42),
    model_t=HistGradientBoostingClassifier(max_iter=200, random_state=42),
    cv=5,                    # Cross-fitting folds
    random_state=42,
)
est.fit(Y, D, X=X)          # Y=outcome, T=treatment, X=effect modifiers

# ATE with confidence interval
ate = est.ate(X)
ate_ci = est.ate_interval(X, alpha=0.05)
print(f"ATE: {ate:.4f}, 95% CI: [{ate_ci[0]:.4f}, {ate_ci[1]:.4f}]")

# CATE for each observation
cate = est.effect(X)
cate_ci = est.effect_interval(X, alpha=0.05)

# Coefficient on X for linear CATE model: CATE(x) = x @ coef + intercept
print(f"CATE coefficients: {est.coef_}")
print(f"CATE intercept: {est.intercept_}")
```

### CausalForestDML

```python
from econml.dml import CausalForestDML

est = CausalForestDML(
    model_y=HistGradientBoostingRegressor(max_iter=200, random_state=42),
    model_t=HistGradientBoostingClassifier(max_iter=200, random_state=42),
    n_estimators=1000,       # Number of trees
    min_samples_leaf=10,     # Minimum leaf size (controls smoothing)
    cv=5,
    random_state=42,
)
est.fit(Y, D, X=X)

# Pointwise CATE with confidence intervals
cate = est.effect(X)
cate_lower, cate_upper = est.effect_interval(X, alpha=0.05)

# Feature importance for heterogeneity
importances = est.feature_importances_
for i, col in enumerate(COVARIATE_COLS):
    print(f"  {col}: {importances[i]:.3f}")

# ATE and inference
ate_result = est.ate_inference(X)
print(f"ATE: {ate_result.mean_point:.4f} "
      f"({ate_result.conf_int_mean()[0]:.4f}, {ate_result.conf_int_mean()[1]:.4f})")
```

### Meta-Learners (EconML)

```python
from econml.metalearners import SLearner, TLearner, XLearner, DomainAdaptationLearner

# X-Learner: handles imbalanced treatment groups well
x_learner = XLearner(
    models=HistGradientBoostingRegressor(max_iter=200, random_state=42),
    propensity_model=HistGradientBoostingClassifier(max_iter=200, random_state=42),
    cate_models=HistGradientBoostingRegressor(max_iter=200, random_state=42),
)
x_learner.fit(Y, D, X=X)

cate_x = x_learner.effect(X)
print(f"X-Learner ATE: {cate_x.mean():.4f}")
```

### DR-Learner (EconML)

```python
from econml.dr import DRLearner

# DR-Learner: doubly robust CATE estimation
dr_learner = DRLearner(
    model_propensity=HistGradientBoostingClassifier(max_iter=200, random_state=42),
    model_regression=HistGradientBoostingRegressor(max_iter=200, random_state=42),
    model_final=HistGradientBoostingRegressor(max_iter=200, random_state=42),
    cv=5,
    random_state=42,
)
dr_learner.fit(Y, D, X=X)

cate_dr = dr_learner.effect(X)
cate_dr_lower, cate_dr_upper = dr_learner.effect_interval(X, alpha=0.05)

print(f"DR-Learner ATE: {cate_dr.mean():.4f}")
print(f"DR-Learner CATE range: [{cate_dr.min():.4f}, {cate_dr.max():.4f}]")
```

## DoubleML Patterns

**Install:** `pip install doubleml`

DoubleML provides a focused, well-documented implementation of the DML framework
with strong support for sensitivity analysis and model diagnostics.

### Partially Linear Regression

```python
import doubleml as dml
from doubleml import DoubleMLPLR, DoubleMLData

# DoubleML requires a DoubleMLData object
dml_data = DoubleMLData.from_arrays(
    x=X,           # Covariates
    y=Y,           # Outcome
    d=D,           # Treatment
)

# Partially linear regression (PLR)
plr = DoubleMLPLR(
    dml_data,
    ml_l=HistGradientBoostingRegressor(max_iter=200, random_state=42),  # E[Y|X]
    ml_m=HistGradientBoostingClassifier(max_iter=200, random_state=42), # E[D|X]
    n_folds=5,
    score="partialling out",   # Standard DML score
)
plr.fit()

print(plr.summary)
# Columns: coef, std err, t, P>|t|, 2.5%, 97.5%
```

### Interactive Regression Model (IRM)

```python
from doubleml import DoubleMLIRM

# IRM: AIPW-based ATE (more flexible than PLR)
irm = DoubleMLIRM(
    dml_data,
    ml_g=HistGradientBoostingRegressor(max_iter=200, random_state=42),  # E[Y|D,X]
    ml_m=HistGradientBoostingClassifier(max_iter=200, random_state=42), # E[D|X]
    n_folds=5,
    score="ATE",    # Or "ATTE" for ATT
)
irm.fit()
print(irm.summary)
```

### Sensitivity Analysis

```python
# DoubleML provides built-in sensitivity analysis (Chernozhukov et al. 2022)
plr.sensitivity_analysis()

# Sensitivity parameters:
# - cf_y: confounding strength for outcome (R^2-like)
# - cf_d: confounding strength for treatment (R^2-like)
# These bound how much an omitted confounder could change the estimate

print(f"Sensitivity results:")
print(f"  Robustness value (rho): {plr.sensitivity_params['rv']:.3f}")
print(f"  Robustness value (rho, alpha=0.05): {plr.sensitivity_params['rva']:.3f}")
# REASONING: rho is the minimum confounding strength that would change the
# conclusion. Larger rho = more robust. rva accounts for statistical uncertainty.
```

## Causal Forests

Causal forests are the primary tool for nonparametric CATE estimation with valid
inference. Two implementations exist:

### EconML CausalForestDML

See the EconML section above. `CausalForestDML` combines DML-style cross-fitting
for nuisance estimation with an honest causal forest for CATE estimation. This is
the recommended Python implementation.

### R grf Package (Gold Standard)

The R `grf` package (Athey, Tibshirani, and Wager 2019) is the reference
implementation for generalized random forests. It is not available in Python
but can be accessed via `rpy2` if R is installed.

```python
# --- R grf via rpy2 (requires R and grf installed) ---
# pip install rpy2
# R: install.packages("grf")

import rpy2.robjects as ro
from rpy2.robjects import numpy2ri
numpy2ri.activate()

ro.r('library(grf)')

# Pass data to R
ro.r.assign('X_r', X)
ro.r.assign('Y_r', Y)
ro.r.assign('W_r', D)  # grf uses W for treatment

# Fit causal forest
ro.r('''
cf <- causal_forest(X_r, Y_r, W_r,
                    num.trees = 2000,
                    honesty = TRUE,
                    seed = 42)
''')

# Extract CATE predictions and CIs
ro.r('''
pred <- predict(cf, estimate.variance = TRUE)
cate_grf <- pred$predictions
cate_var <- pred$variance.estimates
''')

cate_grf = np.array(ro.r('cate_grf')).flatten()
cate_se = np.sqrt(np.array(ro.r('cate_var')).flatten())

# ATE
ro.r('ate_result <- average_treatment_effect(cf)')
ate_grf = np.array(ro.r('ate_result'))
print(f"grf ATE: {ate_grf[0]:.4f} (SE: {ate_grf[1]:.4f})")

# Variable importance for heterogeneity
ro.r('vi <- variable_importance(cf)')
vi = np.array(ro.r('vi')).flatten()
for i, col in enumerate(COVARIATE_COLS):
    print(f"  {col}: {vi[i]:.3f}")
```

**Key grf features not available in EconML:**
- `best_linear_projection()`: tests whether CATE varies with specific covariates
  (formal heterogeneity test)
- `rank_average_treatment_effect()`: evaluates targeting quality (RATE metric)
- Calibration diagnostics via `test_calibration()`
- Honest forests with tuning via `tune_forest()`

## Diagnostics and Validation

### Overlap (Common Support) Check

```python
# --- Propensity score overlap ---
# INTENT: Verify that treated and control groups overlap in covariate space
# REASONING: All CATE methods assume common support — P(D=1|X) bounded away
#   from 0 and 1. Violations produce extreme weights and unreliable estimates.

from sklearn.ensemble import HistGradientBoostingClassifier

ps_model = HistGradientBoostingClassifier(max_iter=200, random_state=42)
ps_model.fit(X, D)
e_scores = ps_model.predict_proba(X)[:, 1]

print(f"Propensity score summary:")
print(f"  Range:  [{e_scores.min():.3f}, {e_scores.max():.3f}]")
print(f"  Mean:   {e_scores.mean():.3f}")
print(f"  < 0.05: {(e_scores < 0.05).sum()} obs ({(e_scores < 0.05).mean():.1%})")
print(f"  > 0.95: {(e_scores > 0.95).sum()} obs ({(e_scores > 0.95).mean():.1%})")

# Overlap histogram
import plotnine as p9
ps_df = pl.DataFrame({
    "propensity_score": e_scores,
    "group": ["Treated" if d == 1 else "Control" for d in D],
}).to_pandas()

overlap_plot = (
    p9.ggplot(ps_df, p9.aes(x="propensity_score", fill="group"))
    + p9.geom_histogram(bins=50, alpha=0.6, position="identity")
    + p9.labs(x="Propensity Score", y="Count", title="Overlap Check")
    + p9.theme_minimal()
)
# REASONING: Good overlap shows substantial distributional overlap between
# treated and control propensity scores. Lack of overlap in certain regions
# means CATE is extrapolated, not estimated, in those regions.
```

### CATE Validation: Sorted Group Average Treatment Effects (GATES)

```python
# --- GATES: test whether estimated CATE predicts actual heterogeneity ---
# INTENT: Divide sample into quantile groups by estimated CATE and check
#   whether the actual treatment effect varies across these groups
# REASONING: If CATE estimates are informative, groups with higher predicted
#   CATE should show larger actual treatment effects (Chernozhukov et al. 2018)
# ASSUMES: Binary treatment with a valid causal design

# Sort observations by estimated CATE into quintiles
cate_estimates = cate_t  # or cate_s, or any estimator
quintile_labels = np.digitize(
    cate_estimates,
    bins=np.quantile(cate_estimates, [0.2, 0.4, 0.6, 0.8]),
)

gates_results = []
for q in range(5):
    mask = quintile_labels == q
    n_q = mask.sum()
    # Simple difference in means within each quintile
    y_treated = Y[mask & (D == 1)]
    y_control = Y[mask & (D == 0)]
    if len(y_treated) > 0 and len(y_control) > 0:
        gate = y_treated.mean() - y_control.mean()
        se_gate = np.sqrt(y_treated.var() / len(y_treated)
                          + y_control.var() / len(y_control))
        gates_results.append({
            "quintile": q + 1,
            "predicted_cate": cate_estimates[mask].mean(),
            "actual_gate": round(gate, 4),
            "se": round(se_gate, 4),
            "n": n_q,
        })

gates_df = pl.DataFrame(gates_results)
print(gates_df)
# REASONING: An increasing pattern in actual_gate across quintiles sorted
# by predicted_cate indicates the CATE estimates capture real heterogeneity.
# A flat pattern suggests the estimated heterogeneity is noise.
```

### BLP: Best Linear Predictor Test

```python
# --- BLP test (Chernozhukov et al. 2018) ---
# INTENT: Formal test of whether estimated CATE predicts actual heterogeneity
# REASONING: Regress Y on (D, D*CATE_hat) controlling for CATE_hat.
#   The coefficient on D*CATE_hat tests whether the estimated heterogeneity
#   is predictive. A significant positive coefficient validates the CATE model.

# Center CATE estimates for interpretability
cate_centered = cate_estimates - cate_estimates.mean()

blp_df = pl.DataFrame({
    "Y": Y,
    "D": D,
    "D_cate": D * cate_centered,
    "cate_hat": cate_centered,
}).to_pandas()

import statsmodels.formula.api as smf
blp_fit = smf.ols("Y ~ D + D_cate + cate_hat", data=blp_df).fit(cov_type="HC1")
print(f"\nBLP Test:")
print(f"  D coefficient (ATE):       {blp_fit.params['D']:.4f} "
      f"(p={blp_fit.pvalues['D']:.4f})")
print(f"  D*CATE coefficient (het.): {blp_fit.params['D_cate']:.4f} "
      f"(p={blp_fit.pvalues['D_cate']:.4f})")
# REASONING: If D_cate coefficient is significantly positive, the CATE
# model captures real treatment effect heterogeneity. A coefficient near 1
# suggests well-calibrated CATE estimates.
```

## Gotchas and Pitfalls

### 1. DML Requires a Valid Causal Design

DML handles nuisance estimation flexibly, but it does NOT solve the
identification problem. If the partially linear model's assumption
(conditional exogeneity: E[epsilon|D,X] = 0) is violated, DML produces a
biased estimate -- just with correctly computed standard errors around a wrong
number. Always establish identification first (RCT, quasi-experiment, or
defended conditional independence), then use DML for estimation.

### 2. Cross-Fitting Is Not Optional

The cross-fitting step in DML is not a convenience -- it is mathematically
necessary. Without cross-fitting, the regularization bias from ML nuisance
models contaminates the causal parameter estimate, and standard errors are
invalid. Naive plug-in (fitting nuisance models on the full sample, then
computing residuals on the same sample) produces overfitting bias that does
not vanish at root-n rates. Always use K-fold cross-fitting with K >= 2
(K=5 is standard).

### 3. CATE Estimates Are Noisy for Small Subgroups

Estimating CATE(x) for a specific covariate profile x requires sufficient
data in the neighborhood of x. In thin regions of the covariate space,
CATE estimates are driven by noise rather than signal. Confidence intervals
(from EconML or causal forests) will correctly reflect this uncertainty by
being wide -- but point estimates alone can be misleading. Always report
confidence intervals for CATE, and be suspicious of extreme estimated CATE
values that occur in sparse regions.

### 4. Overlap Is Critical for All CATE Methods

All CATE methods require common support (overlap): for every covariate
profile x, there must be positive probability of both treatment and control.
When P(D=1|X=x) is near 0 or 1, the method must extrapolate, and the
resulting CATE estimates are unreliable. Always check the propensity score
distribution and trim or report overlap violations. This is the same
requirement as for matching/IPW methods (see `./causal-matching.md`).

### 5. Meta-Learner Bias-Variance Tradeoffs

S-learner is biased toward zero (the model may ignore a small treatment
effect), while T-learner has high variance (two independent models with no
information sharing). Neither dominates -- the right choice depends on sample
balance and signal strength. When in doubt, estimate both and compare. If
they disagree substantially, the heterogeneity pattern may not be robust.

### 6. Variable Importance in Causal Forests Is Not Causal Discovery

Feature importance from causal forests measures which covariates are useful
for predicting treatment effect heterogeneity -- not which covariates cause
the heterogeneity. A variable can rank high because it is correlated with
a true effect modifier, not because it is one. Interpret importance scores as
"predictive of heterogeneity," not "causing heterogeneity."

### 7. DML Standard Errors May Need HC Adjustment

The standard DML variance formula assumes homoskedastic errors in the
influence function. With heteroskedastic data, use HC-robust standard errors
(HC1 or HC3) in the final-stage regression of V_hat on U_hat. The manual
implementation above uses the sandwich-style estimator, which is
heteroskedasticity-consistent. When data has clustering structure, use
pyfixest with clustered SEs in the final stage (see the pyfixest final-stage
example above).

### 8. pyfixest Can Serve as the DML Final Stage

After DML residualization, the final-stage regression of Y-residuals on
D-residuals can be run through pyfixest instead of manual computation. This
is particularly useful when you need clustered standard errors, fixed effects
in the final stage, or want to use pyfixest's reporting tools (`etable`,
`coefplot`). The point estimate is identical; only the SE computation differs.

## Decision Tree: Which Approach?

```
What is your goal?
|
+-- Estimate ATE with many confounders
|   |
|   +-- Installed packages only?
|   |   +-- YES --> Manual DML (partially linear model, above)
|   |   +-- NO  --> DoubleML PLR or EconML LinearDML
|   |
|   +-- Need sensitivity analysis?
|       +-- YES --> DoubleML (built-in sensitivity)
|       +-- NO  --> Either package
|
+-- Estimate CATE (treatment effect heterogeneity)
|   |
|   +-- Just exploring heterogeneity patterns?
|   |   +-- YES --> Manual S/T-learner (above)
|   |   |          Then validate with GATES/BLP
|   |   +-- NO (need valid CIs on CATE)
|   |       +-- EconML CausalForestDML or DR-Learner
|   |       +-- Or R grf (gold standard) via rpy2
|   |
|   +-- Imbalanced treatment groups?
|   |   +-- YES --> X-Learner (EconML) or DR-Learner
|   |   +-- NO  --> T-Learner or CausalForestDML
|   |
|   +-- Want doubly robust estimation?
|       +-- YES --> DR-Learner (EconML) or AIPW (manual, above)
|       +-- NO  --> T-Learner or CausalForestDML
|
+-- Policy learning (who to treat?)
|   +-- EconML PolicyTree or PolicyForest
|
+-- Not sure where to start?
    +-- Start with manual DML for ATE
    +-- Then manual S/T-learner for heterogeneity
    +-- Install EconML when you need valid CATE CIs
```

## References

### Foundational Papers

Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey,
W., and Robins, J. (2018). "Double/Debiased Machine Learning for Treatment
and Structural Parameters." *Econometrics Journal*, 21(1), C1-C68.
https://doi.org/10.1111/ectj.12097

Wager, S. and Athey, S. (2018). "Estimation and Inference of Heterogeneous
Treatment Effects Using Random Forests." *Journal of the American Statistical
Association*, 113(523), 1228-1242.
https://doi.org/10.1080/01621459.2017.1319839

Athey, S., Tibshirani, J., and Wager, S. (2019). "Generalized Random Forests."
*Annals of Statistics*, 47(2), 1148-1178.
https://doi.org/10.1214/18-AOS1709

### Meta-Learners

Kunzel, S.R., Sekhon, J.S., Bickel, P.J., and Yu, B. (2019). "Metalearners
for Estimating Heterogeneous Treatment Effects Using Machine Learning."
*Proceedings of the National Academy of Sciences*, 116(10), 4156-4165.
https://doi.org/10.1073/pnas.1804597116

Nie, X. and Wager, S. (2021). "Quasi-Oracle Estimation of Heterogeneous
Treatment Effects." *Biometrika*, 108(2), 299-319.
https://doi.org/10.1093/biomet/asaa076

Kennedy, E.H. (2023). "Towards Optimal Doubly Robust Estimation of
Heterogeneous Causal Effects." *Electronic Journal of Statistics*, 17(2),
3008-3049.
https://doi.org/10.1214/23-EJS2157

### Software

Battocchi, K., Dillon, E., Hei, M., Lewis, G., Oka, P., Oprescu, M., and
Syrgkanis, V. (2019). "EconML: A Python Package for ML-Based Heterogeneous
Treatment Effects Estimation." Microsoft Research.
https://github.com/py-why/EconML

Sharma, A. and Kiciman, E. (2020). "DoWhy: An End-to-End Library for
Causal Inference." arXiv:2011.04216.
https://arxiv.org/abs/2011.04216

Bach, P., Chernozhukov, V., Kurz, M.S., and Spindler, M. (2022). "DoubleML:
An Object-Oriented Implementation of Double Machine Learning in Python."
*Journal of Machine Learning Research*, 23(53), 1-6.
https://jmlr.org/papers/v23/21-0862.html

### Textbooks

Cunningham, S. (2021). *Causal Inference: The Mixtape*. Yale University Press.
https://mixtape.scunning.com/

Huntington-Klein, N. (2022). *The Effect: An Introduction to Research Design
and Causality*. Chapman & Hall/CRC.
https://theeffectbook.net/
