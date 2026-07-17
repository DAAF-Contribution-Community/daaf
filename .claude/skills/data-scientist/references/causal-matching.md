# Matching, IPW, and Doubly Robust Estimation

Implementation reference for selection-on-observables causal inference methods using
installed packages only (scikit-learn, statsmodels, scipy, polars, numpy). No dedicated
matching package is installed in the DAAF environment -- everything is built from these
components.

For methodology, assumptions, and when to use these methods vs. alternatives (IV, DiD,
RD), see `causal-inference.md` > "Matching and Inverse Probability Weighting" and the
Method Selection Guide. This file focuses on **how to implement** once you have decided
matching/IPW is the right design.

**Recommended default:** Doubly robust / AIPW estimation (see [Doubly Robust / AIPW
Estimation](#doubly-robust--aipw-estimation)) is the state-of-the-art approach for
selection-on-observables designs. It is consistent if *either* the propensity score
model or the outcome model is correctly specified, and cross-fitted AIPW provides
valid asymptotic inference without bootstrap. Start here unless you have a specific
reason to prefer pure matching or pure IPW.

## Contents

- [Propensity Score Estimation](#propensity-score-estimation)
- [Common Support and Trimming](#common-support-and-trimming)
- [Matching Methods](#matching-methods)
- [Inverse Probability Weighting (IPW)](#inverse-probability-weighting-ipw)
- [Doubly Robust / AIPW Estimation](#doubly-robust--aipw-estimation)
- [Balance Diagnostics](#balance-diagnostics)
- [Inference After Matching](#inference-after-matching)
- [Gotchas and Common Mistakes](#gotchas-and-common-mistakes)
- [Decision Guide: Which Method to Use](#decision-guide-which-method-to-use)
- [References and Further Reading](#references-and-further-reading)

## Propensity Score Estimation

The propensity score e(X) = P(T=1|X) is the probability of receiving treatment
conditional on observed covariates. It reduces a high-dimensional covariate space
to a single scalar for balancing (Rosenbaum and Rubin 1983).

### Estimation with Logistic Regression

```python
import numpy as np
from sklearn.linear_model import LogisticRegression

# X_mat: numpy array of covariates (N x p)
# T: numpy array of treatment indicator (N,), values 0/1

# C=1e6 effectively removes regularization -- goal is BALANCE, not prediction
ps_model = LogisticRegression(C=1e6, max_iter=1000, solver="lbfgs")
ps_model.fit(X_mat, T)
e_hat = ps_model.predict_proba(X_mat)[:, 1]

print(f"Propensity score range: [{e_hat.min():.4f}, {e_hat.max():.4f}]")
print(f"Mean PS (treated):  {e_hat[T == 1].mean():.4f}")
print(f"Mean PS (control):  {e_hat[T == 0].mean():.4f}")
```

### Variable Selection for the Propensity Score

Variable selection for propensity scores follows different rules than predictive
modeling. The goal is **balance** on confounders, not prediction accuracy.

**Include:**
- Confounders (variables that cause both treatment and outcome)
- Outcome predictors (variables that predict Y but not T) -- these improve
  precision without introducing bias (Brookhart et al. 2006)

**Exclude:**
- **Instruments** (variables that predict T but not Y directly) -- including
  instruments in the propensity score amplifies bias and increases variance
  (Brookhart et al. 2006; Myers et al. 2011)
- **Colliders** (variables caused by both T and Y) -- conditioning on a collider
  opens a non-causal path between treatment and outcome
- **Post-treatment variables** (variables affected by treatment) -- conditioning
  on these blocks part of the causal effect ("bad controls")

**Do NOT optimize for AUC or classification accuracy.** A propensity score model
with high AUC may indicate that treated and control groups are very different --
which is a problem for causal inference, not a success. The metric that matters
is **covariate balance after matching or weighting**, not predictive performance.

### Logit Transformation

Working on the logit scale is standard practice for caliper matching and
diagnostics because propensity scores are bounded [0,1] and often concentrated
near 0 or 1:

```python
logit_ps = np.log(e_hat / (1 - e_hat))
```

## Common Support and Trimming

The conditional independence assumption requires **common support** (overlap):
for every covariate value, there must be a positive probability of being in both
treatment and control. Propensity scores near 0 or 1 violate this.

### Trimming to Common Support

```python
# Crump et al. (2009) recommend trimming to [0.1, 0.9]
alpha_trim = 0.1
support_mask = (e_hat >= alpha_trim) & (e_hat <= (1 - alpha_trim))

n_before = len(e_hat)
n_after = support_mask.sum()
n_dropped = n_before - n_after
print(f"Common support trimming: {n_dropped} obs dropped "
      f"({n_dropped / n_before * 100:.1f}%)")
print(f"  Treated dropped: {(~support_mask & (T == 1)).sum()}")
print(f"  Control dropped: {(~support_mask & (T == 0)).sum()}")

# Apply trim
X_trim = X_mat[support_mask]
T_trim = T[support_mask]
Y_trim = Y[support_mask]
e_trim = e_hat[support_mask]
```

Trimming changes the estimand -- you are now estimating the treatment effect for
the subpopulation with overlap, not the full population. Report how many
observations were dropped and from which group.

### Visual Overlap Assessment

```python
import plotnine as p9
import polars as pl

ps_df = pl.DataFrame({
    "ps": e_hat,
    "group": ["Treated" if t == 1 else "Control" for t in T]
})

plot = (
    p9.ggplot(ps_df.to_pandas(), p9.aes(x="ps", fill="group"))
    + p9.geom_histogram(bins=50, alpha=0.5, position="identity")
    + p9.labs(x="Propensity Score", y="Count",
              title="Propensity Score Distribution by Treatment Group")
    + p9.theme_minimal()
)
```

Regions where one group has density and the other does not indicate common support
violations. These observations cannot be reliably matched or weighted.

## Matching Methods

### Nearest-Neighbor Propensity Score Matching (1:1, With Replacement)

```python
from sklearn.neighbors import NearestNeighbors

# Reshape propensity scores for sklearn
ps_treated = e_hat[T == 1].reshape(-1, 1)
ps_control = e_hat[T == 0].reshape(-1, 1)

# Fit on control group, query with treated
nn = NearestNeighbors(n_neighbors=1, metric="euclidean")
nn.fit(ps_control)
distances, indices = nn.kneighbors(ps_treated)

# indices maps each treated unit to its matched control (index into control array)
# With replacement: a control unit can be matched to multiple treated units
matched_control_idx = np.where(T == 0)[0][indices.flatten()]
treated_idx = np.where(T == 1)[0]

# Treatment effect estimate (ATT)
att = Y[treated_idx].mean() - Y[matched_control_idx].mean()
print(f"ATT (NN 1:1 with replacement): {att:.4f}")
print(f"Mean match distance: {distances.mean():.4f}")
print(f"Max match distance:  {distances.max():.4f}")
```

### Nearest-Neighbor Matching Without Replacement

Matching without replacement prevents a control unit from being reused, which
reduces bias from repeatedly using a poor match but increases bias from later
matches being worse. This is a bias-variance tradeoff.

```python
# Greedy matching without replacement
ps_treated = e_hat[T == 1]
ps_control = e_hat[T == 0]
treated_idx = np.where(T == 1)[0]
control_idx = np.where(T == 0)[0]

# Sort treated by PS to match in order (random order also acceptable)
sort_order = np.argsort(ps_treated)
matched_pairs = []
available = set(range(len(control_idx)))

for i in sort_order:
    if not available:
        break
    avail_list = np.array(sorted(available))
    dists = np.abs(ps_treated[i] - ps_control[avail_list])
    best_j = avail_list[np.argmin(dists)]
    matched_pairs.append((treated_idx[i], control_idx[best_j]))
    available.remove(best_j)

matched_pairs = np.array(matched_pairs)
att = Y[matched_pairs[:, 0]].mean() - Y[matched_pairs[:, 1]].mean()
print(f"ATT (NN 1:1 without replacement): {att:.4f}")
print(f"Matched pairs: {len(matched_pairs)}")
```

### Caliper Matching

A caliper imposes a maximum distance for acceptable matches. Unmatched treated
units are dropped. Austin (2011) recommends a caliper of 0.2 * SD(logit(PS)):

```python
logit_ps = np.log(e_hat / (1 - e_hat))
caliper = 0.2 * logit_ps.std()
print(f"Caliper (0.2 * SD of logit PS): {caliper:.4f}")

logit_treated = logit_ps[T == 1].reshape(-1, 1)
logit_control = logit_ps[T == 0].reshape(-1, 1)

nn = NearestNeighbors(n_neighbors=1, metric="euclidean")
nn.fit(logit_control)
distances, indices = nn.kneighbors(logit_treated)

# Apply caliper: keep only matches within the caliper distance
within_caliper = distances.flatten() <= caliper
n_matched = within_caliper.sum()
n_unmatched = (~within_caliper).sum()
print(f"Matched: {n_matched}, Unmatched (dropped): {n_unmatched}")

matched_treated = np.where(T == 1)[0][within_caliper]
matched_control = np.where(T == 0)[0][indices.flatten()[within_caliper]]

att = Y[matched_treated].mean() - Y[matched_control].mean()
print(f"ATT (caliper matching): {att:.4f}")
```

Alternatively, use `radius_neighbors` for radius-based matching that finds ALL
controls within the caliper for each treated unit (variable-ratio matching):

```python
nn_radius = NearestNeighbors(radius=caliper, metric="euclidean")
nn_radius.fit(logit_control)
radius_distances, radius_indices = nn_radius.radius_neighbors(logit_treated)
```

### Mahalanobis Distance Matching

Mahalanobis matching uses the covariance structure of the covariates to define
distance, giving less weight to highly correlated variables:

```python
from scipy.spatial.distance import cdist

# Compute inverse covariance matrix from pooled sample
cov_mat = np.cov(X_mat, rowvar=False)
cov_inv = np.linalg.inv(cov_mat)

X_treated = X_mat[T == 1]
X_control = X_mat[T == 0]

# Pairwise Mahalanobis distances (n_treated x n_control)
dist_matrix = cdist(X_treated, X_control, metric="mahalanobis", VI=cov_inv)

# 1:1 nearest neighbor on Mahalanobis distance (with replacement)
best_match_idx = dist_matrix.argmin(axis=1)
control_pool_idx = np.where(T == 0)[0]
matched_control = control_pool_idx[best_match_idx]
treated_idx = np.where(T == 1)[0]

att = Y[treated_idx].mean() - Y[matched_control].mean()
print(f"ATT (Mahalanobis matching): {att:.4f}")
```

Note: Mahalanobis matching suffers from the curse of dimensionality -- with many
covariates, distances become less meaningful. Consider combining with propensity
score matching or using it for a smaller set of key covariates.

### Exact Matching

Exact matching on categorical covariates uses polars joins. Treatment effect is
computed within strata and then aggregated:

```python
import polars as pl

# df: polars DataFrame with treatment column "T", outcome "Y",
# and categorical matching variables
exact_vars = ["region", "gender", "education_level"]

matched = (
    df.filter(pl.col("T") == 1)
    .join(
        df.filter(pl.col("T") == 0),
        on=exact_vars,
        how="inner",
        suffix="_ctrl"
    )
)
print(f"Exact matches found: {matched.height}")
# Many-to-many: each treated matched to all controls in same stratum
```

For ATT estimation with exact matching, compute stratum-level effects and weight
by treated counts:

```python
strata_effects = (
    df.group_by(exact_vars)
    .agg([
        pl.col("Y").filter(pl.col("T") == 1).mean().alias("Y_treated"),
        pl.col("Y").filter(pl.col("T") == 0).mean().alias("Y_control"),
        pl.col("T").sum().alias("n_treated"),
        (1 - pl.col("T")).sum().alias("n_control"),
    ])
    .filter(
        (pl.col("n_treated") > 0) & (pl.col("n_control") > 0)
    )
    .with_columns(
        (pl.col("Y_treated") - pl.col("Y_control")).alias("effect")
    )
)

# ATT: weight by number of treated in each stratum
total_treated = strata_effects["n_treated"].sum()
att = (strata_effects["effect"] * strata_effects["n_treated"]).sum() / total_treated
print(f"ATT (exact matching): {att:.4f}")
print(f"Strata with both groups: {strata_effects.height}")
```

### Coarsened Exact Matching (CEM)

CEM (Iacus, King, and Porro 2012) coarsens continuous covariates into bins, then
performs exact matching on the coarsened values. It guarantees a maximum imbalance
on the matched covariates (the "equal percent bias reducing" property).

```python
import polars as pl

# Step 1: Coarsen continuous variables into bins
df_cem = df.with_columns([
    # Quantile-based binning for continuous vars
    pl.col("income").qcut(5, labels=[str(i) for i in range(5)]).alias("income_bin"),
    pl.col("age").qcut(4, labels=[str(i) for i in range(4)]).alias("age_bin"),
    # Categorical vars stay as-is
    pl.col("region").alias("region_bin"),
    pl.col("education_level").alias("educ_bin"),
])

cem_vars = ["income_bin", "age_bin", "region_bin", "educ_bin"]

# Step 2: Create strata and identify those with both treated and control
strata = (
    df_cem.group_by(cem_vars)
    .agg([
        pl.col("T").sum().alias("n_treated"),
        (1 - pl.col("T")).sum().alias("n_control"),
        pl.len().alias("n_total"),
    ])
    .filter(
        (pl.col("n_treated") > 0) & (pl.col("n_control") > 0)
    )
)

print(f"Total strata: {df_cem.group_by(cem_vars).len().height}")
print(f"Matched strata (both T and C): {strata.height}")

# Step 3: Compute CEM weights
# Treated weight = 1 (targeting ATT)
# Control weight = (n_treated_s / n_control_s) * (N_control / N_treated)
# This creates balance within each stratum
df_weighted = (
    df_cem.join(strata.select(cem_vars + ["n_treated", "n_control"]),
                on=cem_vars, how="inner")
    .with_columns(
        pl.when(pl.col("T") == 1)
        .then(1.0)
        .otherwise(
            pl.col("n_treated") / pl.col("n_control")
        )
        .alias("cem_weight")
    )
)

n_matched = df_weighted.height
n_dropped = df.height - n_matched
print(f"Observations in matched strata: {n_matched}")
print(f"Dropped (unmatched strata): {n_dropped} ({n_dropped / df.height * 100:.1f}%)")
```

CEM weights can then be used in a weighted regression for outcome estimation.

## Inverse Probability Weighting (IPW)

IPW uses propensity scores to reweight the sample so that the covariate
distribution is balanced between treatment groups. Unlike matching, IPW uses all
observations (within the common support region).

### ATE Weights

```python
# ATE: weight both groups to represent the full population
# Treated: w = 1/e(x), Control: w = 1/(1-e(x))
w_ate = np.where(T == 1, 1.0 / e_hat, 1.0 / (1.0 - e_hat))

# Horvitz-Thompson estimator
ate_ht = (T * Y / e_hat).mean() - ((1 - T) * Y / (1 - e_hat)).mean()
print(f"ATE (Horvitz-Thompson): {ate_ht:.4f}")

# Compact Hajek-style (normalized weights)
w_treated = T / e_hat
w_control = (1 - T) / (1 - e_hat)
ate_hajek = (w_treated * Y).sum() / w_treated.sum() - \
            (w_control * Y).sum() / w_control.sum()
print(f"ATE (Hajek / normalized): {ate_hajek:.4f}")
```

The compact formula for ATE-IPW (useful for derivations and doubly robust
estimation):

```python
# Compact ATE-IPW: E[(T - e) / (e * (1-e)) * Y]
ate_compact = ((T - e_hat) / (e_hat * (1 - e_hat)) * Y).mean()
print(f"ATE (compact formula): {ate_compact:.4f}")
```

### ATT Weights

```python
# ATT: treated get weight 1, controls get weight e(x)/(1-e(x))
w_att = np.where(T == 1, 1.0, e_hat / (1.0 - e_hat))

# ATT estimate
y1_att = (T * Y).sum() / T.sum()
y0_att = ((1 - T) * w_att * Y).sum() / ((1 - T) * w_att).sum()
att = y1_att - y0_att
print(f"ATT (IPW): {att:.4f}")
```

### Stabilized Weights

Standard IPW weights can be highly variable, especially when propensity scores
are near 0 or 1. Stabilized weights replace the numerator 1 with the marginal
treatment probability, reducing variance without introducing bias:

```python
# Marginal treatment probability
p_treat = T.mean()

# Stabilized ATE weights
sw_ate = np.where(T == 1,
                  p_treat / e_hat,
                  (1 - p_treat) / (1 - e_hat))

# Stabilized ATT weights
sw_att = np.where(T == 1,
                  1.0,
                  (p_treat / (1 - p_treat)) * (e_hat / (1 - e_hat)))

print(f"Unstabilized ATE weights -- mean: {w_ate.mean():.2f}, "
      f"max: {w_ate.max():.2f}, CV: {w_ate.std() / w_ate.mean():.2f}")
print(f"Stabilized ATE weights   -- mean: {sw_ate.mean():.2f}, "
      f"max: {sw_ate.max():.2f}, CV: {sw_ate.std() / sw_ate.mean():.2f}")
```

### Weight Diagnostics

Always inspect weight distributions before proceeding to outcome estimation.
Extreme weights signal common support problems and inflate variance.

```python
# Effective sample size (Kish 1965)
# ESS = (sum(w))^2 / sum(w^2) -- the "number of independent observations"
# equivalent to the weighted sample
ess = w_ate.sum()**2 / (w_ate**2).sum()
print(f"Effective sample size: {ess:.0f} (actual N: {len(w_ate)})")

# Weight distribution summary
for label, mask in [("Treated", T == 1), ("Control", T == 0)]:
    w_group = w_ate[mask]
    print(f"\n{label} weights:")
    print(f"  Mean:   {w_group.mean():.3f}")
    print(f"  Median: {np.median(w_group):.3f}")
    print(f"  SD:     {w_group.std():.3f}")
    print(f"  Min:    {w_group.min():.3f}")
    print(f"  Max:    {w_group.max():.3f}")
    print(f"  P99:    {np.percentile(w_group, 99):.3f}")

# Truncation at 99th percentile (when extreme weights are present)
p99 = np.percentile(w_ate, 99)
w_truncated = np.clip(w_ate, a_min=None, a_max=p99)
n_truncated = (w_ate > p99).sum()
print(f"\nTruncation: {n_truncated} weights clipped at {p99:.3f}")
```

### Overlap Weights

Li, Morgan, and Zaslavsky (2018) propose overlap weights as an alternative that
automatically down-weights units in regions of poor overlap. The target estimand
is the ATO (average treatment effect for the overlap population):

```python
# Overlap weights: w = 1-e(x) for treated, e(x) for control
# These are naturally bounded and self-normalizing
w_overlap = np.where(T == 1, 1 - e_hat, e_hat)

y1_ov = (T * w_overlap * Y).sum() / (T * w_overlap).sum()
y0_ov = ((1 - T) * w_overlap * Y).sum() / ((1 - T) * w_overlap).sum()
ato = y1_ov - y0_ov
print(f"ATO (overlap weights): {ato:.4f}")
```

Overlap weights are an attractive option when common support is marginal: they
estimate a well-defined parameter (the ATO) for a population where both treatment
conditions are plausible, without arbitrary trimming thresholds.

### Weighted Outcome Regression

IPW weights can be passed to statsmodels WLS for regression adjustment:

```python
import statsmodels.api as sm

# Weighted least squares with IPW weights
X_reg = sm.add_constant(T)  # or include additional covariates
wls_model = sm.WLS(Y, X_reg, weights=w_ate).fit()
print(wls_model.summary())
ate_wls = wls_model.params[1]
print(f"ATE (WLS with IPW weights): {ate_wls:.4f}")
```

Note: WLS standard errors from statsmodels do **not** account for the fact that
propensity scores were estimated in a prior step. These SEs are typically too
small. Use bootstrap (for IPW -- see Inference section) or the doubly robust
influence-function SE (see AIPW section) for correct inference.

## Doubly Robust / AIPW Estimation

**This is the recommended default for selection-on-observables designs.**

The augmented inverse probability weighted (AIPW) estimator combines a propensity
score model with an outcome model. It is **doubly robust**: consistent if *either*
the propensity score model or the outcome model is correctly specified (Robins,
Rotnitzky, and Zhao 1994; Bang and Robins 2005). Even when both models are
slightly misspecified, the doubly robust estimator typically has smaller bias than
either pure matching or pure IPW.

### Basic AIPW Estimator

The AIPW estimator for E[Y(1)] and E[Y(0)]:

```
E[Y(1)] = (1/N) * sum( T*Y/e + (1-T/e)*mu1(X) )
         = (1/N) * sum( T*(Y-mu1)/e + mu1 )

E[Y(0)] = (1/N) * sum( (1-T)*Y/(1-e) + (1-(1-T)/(1-e))*mu0(X) )
         = (1/N) * sum( (1-T)*(Y-mu0)/(1-e) + mu0 )

ATE = E[Y(1)] - E[Y(0)]
```

Where mu1(X) = E[Y|X, T=1] and mu0(X) = E[Y|X, T=0] are outcome regression models.

```python
import numpy as np
from sklearn.linear_model import LogisticRegression, LinearRegression

# Step 1: Estimate propensity scores
ps_model = LogisticRegression(C=1e6, max_iter=1000)
ps_model.fit(X_mat, T)
e_hat = ps_model.predict_proba(X_mat)[:, 1]

# Step 2: Estimate outcome models (separate for treated and control)
mu1_model = LinearRegression()
mu1_model.fit(X_mat[T == 1], Y[T == 1])
mu1_hat = mu1_model.predict(X_mat)  # predict for ALL observations

mu0_model = LinearRegression()
mu0_model.fit(X_mat[T == 0], Y[T == 0])
mu0_hat = mu0_model.predict(X_mat)  # predict for ALL observations

# Step 3: AIPW scores
score_1 = T * (Y - mu1_hat) / e_hat + mu1_hat
score_0 = (1 - T) * (Y - mu0_hat) / (1 - e_hat) + mu0_hat

# Step 4: ATE and influence-function SE
ate_aipw = score_1.mean() - score_0.mean()
scores = score_1 - score_0
se_aipw = scores.std() / np.sqrt(len(scores))

print(f"ATE (AIPW): {ate_aipw:.4f}")
print(f"SE:         {se_aipw:.4f}")
print(f"95% CI:     [{ate_aipw - 1.96*se_aipw:.4f}, {ate_aipw + 1.96*se_aipw:.4f}]")
```

### Cross-Fitted AIPW (Recommended)

Cross-fitting (Chernozhukov et al. 2018) estimates nuisance parameters (propensity
scores and outcome models) on different folds than where they are evaluated. This
eliminates the overfitting bias that arises when the same data is used for both
estimation and evaluation, and produces valid asymptotic inference.

```python
import numpy as np
from sklearn.model_selection import KFold
from sklearn.linear_model import LogisticRegression, LinearRegression

n = len(Y)
K = 5  # number of folds
kf = KFold(n_splits=K, shuffle=True, random_state=42)

# Storage for cross-fitted predictions
e_cf = np.zeros(n)
mu1_cf = np.zeros(n)
mu0_cf = np.zeros(n)

for train_idx, eval_idx in kf.split(X_mat):
    X_train, X_eval = X_mat[train_idx], X_mat[eval_idx]
    T_train, Y_train = T[train_idx], Y[train_idx]

    # Propensity score on training fold
    ps_k = LogisticRegression(C=1e6, max_iter=1000)
    ps_k.fit(X_train, T_train)
    e_cf[eval_idx] = ps_k.predict_proba(X_eval)[:, 1]

    # Outcome models on training fold
    mu1_k = LinearRegression()
    mu1_k.fit(X_train[T_train == 1], Y_train[T_train == 1])
    mu1_cf[eval_idx] = mu1_k.predict(X_eval)

    mu0_k = LinearRegression()
    mu0_k.fit(X_train[T_train == 0], Y_train[T_train == 0])
    mu0_cf[eval_idx] = mu0_k.predict(X_eval)

# Clip propensity scores to avoid division by near-zero
e_cf = np.clip(e_cf, 0.01, 0.99)

# AIPW with cross-fitted nuisance parameters
score_1 = T * (Y - mu1_cf) / e_cf + mu1_cf
score_0 = (1 - T) * (Y - mu0_cf) / (1 - e_cf) + mu0_cf

ate_cf = score_1.mean() - score_0.mean()
scores_cf = score_1 - score_0
se_cf = scores_cf.std() / np.sqrt(n)

print(f"ATE (Cross-fitted AIPW): {ate_cf:.4f}")
print(f"SE (influence function): {se_cf:.4f}")
print(f"95% CI: [{ate_cf - 1.96*se_cf:.4f}, {ate_cf + 1.96*se_cf:.4f}]")
```

The influence-function SE (`std(scores) / sqrt(N)`) is asymptotically valid with
cross-fitting. This is the primary advantage of cross-fitted AIPW: valid inference
without bootstrap.

### ATT via AIPW

For the ATT (effect on the treated), modify the estimator to weight by treatment
probability:

```python
# ATT-AIPW
p_treat = T.mean()
score_att = (T * (Y - mu0_cf) - (1 - T) * e_cf / (1 - e_cf) * (Y - mu0_cf)) / p_treat

att_aipw = score_att.mean()
se_att = score_att.std() / np.sqrt(n)
print(f"ATT (Cross-fitted AIPW): {att_aipw:.4f} (SE: {se_att:.4f})")
```

## Balance Diagnostics

**Balance diagnostics are mandatory.** They are what distinguish careful causal
inference from sloppy regression. After matching or weighting, you must verify
that the covariate distributions are balanced between treatment groups. If balance
is not achieved, the causal estimate is unreliable regardless of how sophisticated
the estimation method is.

### Standardized Mean Difference (SMD)

The SMD is the primary balance metric. The threshold for acceptable balance is
|SMD| < 0.1 (Austin 2011; Stuart 2010). Some authors recommend |SMD| < 0.05
for high-stakes analyses.

```python
import numpy as np

# Unweighted SMD (for matching)
# For continuous variables:
# SMD = (mean_treated - mean_control) / pooled_SD
# pooled_SD = sqrt((var_treated + var_control) / 2)

# For binary variables:
# SMD = (p_treated - p_control) / sqrt((p_t*(1-p_t) + p_c*(1-p_c)) / 2)

covariate_names = ["age", "income", "education", "female"]  # example

smd_results = []
for j, name in enumerate(covariate_names):
    x_t = X_mat[T == 1, j]
    x_c = X_mat[T == 0, j]

    mean_t = x_t.mean()
    mean_c = x_c.mean()

    # Check if binary (0/1) for appropriate variance formula
    unique_vals = np.unique(X_mat[:, j])
    if len(unique_vals) == 2 and set(unique_vals).issubset({0, 1}):
        # Binary: Bernoulli variance
        pooled_sd = np.sqrt((mean_t * (1 - mean_t) + mean_c * (1 - mean_c)) / 2)
    else:
        # Continuous: pooled SD
        pooled_sd = np.sqrt((x_t.var() + x_c.var()) / 2)

    smd = (mean_t - mean_c) / pooled_sd if pooled_sd > 0 else 0.0
    smd_results.append({"variable": name, "smd_raw": smd})

for r in smd_results:
    flag = " ***" if abs(r["smd_raw"]) >= 0.1 else ""
    print(f"  {r['variable']:20s}  SMD = {r['smd_raw']:+.4f}{flag}")
```

### Weighted SMD (for IPW)

For IPW estimates, compute weighted means but use **unweighted** pooled SD as the
denominator. Using weighted SD in the denominator obscures remaining imbalance
because reweighting itself changes the variance.

```python
# Weighted SMD for IPW
smd_weighted = []
for j, name in enumerate(covariate_names):
    x = X_mat[:, j]

    # Weighted means
    w_t = w_ate[T == 1]
    w_c = w_ate[T == 0]
    wmean_t = np.average(x[T == 1], weights=w_t)
    wmean_c = np.average(x[T == 0], weights=w_c)

    # UNWEIGHTED pooled SD as denominator
    pooled_sd = np.sqrt((x[T == 1].var() + x[T == 0].var()) / 2)

    smd_w = (wmean_t - wmean_c) / pooled_sd if pooled_sd > 0 else 0.0
    smd_weighted.append({"variable": name, "smd_before": smd_results[j]["smd_raw"],
                         "smd_after": smd_w})

print("\nBalance table (IPW):")
print(f"  {'Variable':20s}  {'Before':>10s}  {'After':>10s}")
for r in smd_weighted:
    flag = " ***" if abs(r["smd_after"]) >= 0.1 else ""
    print(f"  {r['variable']:20s}  {r['smd_before']:+10.4f}  {r['smd_after']:+10.4f}{flag}")
```

### Variance Ratios

Variance ratios assess balance in dispersion, not just location. Acceptable range:
[0.5, 2.0] (Rubin 2001). Values outside this range suggest the matching or
weighting failed to equalize the covariate distributions.

```python
print("\nVariance ratios:")
for j, name in enumerate(covariate_names):
    var_t = X_mat[T == 1, j].var()
    var_c = X_mat[T == 0, j].var()
    vr = var_t / var_c if var_c > 0 else np.inf
    flag = " ***" if vr < 0.5 or vr > 2.0 else ""
    print(f"  {name:20s}  VR = {vr:.3f}{flag}")
```

### Love Plot

A Love plot shows |SMD| before and after matching/weighting for all covariates,
with a threshold line at 0.1. This is the standard visual summary of balance:

```python
import plotnine as p9
import polars as pl

balance_df = pl.DataFrame({
    "variable": [r["variable"] for r in smd_weighted] * 2,
    "abs_smd": ([abs(r["smd_before"]) for r in smd_weighted] +
                [abs(r["smd_after"]) for r in smd_weighted]),
    "stage": (["Before"] * len(smd_weighted) +
              ["After"] * len(smd_weighted)),
})

plot = (
    p9.ggplot(balance_df.to_pandas(),
              p9.aes(x="abs_smd", y="variable", color="stage", shape="stage"))
    + p9.geom_point(size=3)
    + p9.geom_vline(xintercept=0.1, linetype="dashed", color="red")
    + p9.labs(x="|Standardized Mean Difference|", y="",
              title="Covariate Balance: Before vs. After Matching/Weighting")
    + p9.theme_minimal()
    + p9.scale_color_manual(values={"Before": "gray", "After": "steelblue"})
)
```

### KS Tests for Distributional Balance

SMD checks balance in means; the Kolmogorov-Smirnov test checks balance across
the entire distribution. This catches cases where means are balanced but
distributions differ in shape (e.g., different variances or skewness):

```python
from scipy.stats import ks_2samp

print("\nKS tests for distributional balance:")
for j, name in enumerate(covariate_names):
    x_t = X_mat[T == 1, j]
    x_c = X_mat[T == 0, j]
    ks_stat, ks_pval = ks_2samp(x_t, x_c)
    flag = " ***" if ks_pval < 0.05 else ""
    print(f"  {name:20s}  KS = {ks_stat:.4f}, p = {ks_pval:.4f}{flag}")
```

### Balance Diagnostic Decision Rule

| Diagnostic | Threshold | Action if Failed |
|------------|-----------|------------------|
| SMD | \|SMD\| < 0.1 for all covariates | Revise PS model, add interactions/polynomials, or switch method |
| Variance ratio | [0.5, 2.0] for all covariates | Consider CEM or Mahalanobis matching on offending variable |
| KS test | p > 0.05 for key covariates | Investigate distributional differences; consider flexible PS model |
| Effective sample size | ESS > 50% of N (rule of thumb) | Common support problem; consider overlap weights or trimming |

**If balance diagnostics fail, do not proceed to outcome estimation.** Revise the
propensity score specification (add interactions, squared terms, or use a more
flexible estimator), try a different matching method, or reconsider whether the
selection-on-observables design is viable for this data.

## Inference After Matching

Standard errors for matching and weighting estimators require care because the
matched/weighted sample is not a simple random sample.

### Bootstrap (Valid for IPW and AIPW)

Bootstrap is the recommended default for IPW. The full estimation pipeline
(propensity score estimation + weighting + outcome estimation) must be repeated
on each bootstrap resample:

```python
import numpy as np

n = len(Y)
n_boot = 1000
boot_ates = np.zeros(n_boot)

for b in range(n_boot):
    idx = np.random.choice(n, size=n, replace=True)
    X_b, T_b, Y_b = X_mat[idx], T[idx], Y[idx]

    # Re-estimate propensity scores on bootstrap sample
    ps_b = LogisticRegression(C=1e6, max_iter=1000)
    ps_b.fit(X_b, T_b)
    e_b = ps_b.predict_proba(X_b)[:, 1]
    e_b = np.clip(e_b, 0.01, 0.99)

    # IPW estimate on bootstrap sample
    boot_ates[b] = ((T_b - e_b) / (e_b * (1 - e_b)) * Y_b).mean()

se_boot = boot_ates.std()
ci_lower = np.percentile(boot_ates, 2.5)
ci_upper = np.percentile(boot_ates, 97.5)
print(f"Bootstrap SE: {se_boot:.4f}")
print(f"Bootstrap 95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
```

### Bootstrap is INVALID for Nearest-Neighbor Matching

Abadie and Imbens (2008) proved that the standard bootstrap is inconsistent for
nearest-neighbor matching estimators. The bootstrap does not correctly replicate
the matching structure -- the distribution of match quality changes across
resamples in ways that invalidate the bootstrap approximation.

**For NN matching, use one of these alternatives:**
1. **Abadie-Imbens variance estimator** (Abadie and Imbens 2006): uses the match
   discrepancy to estimate the conditional variance. This is the theoretically
   correct approach but requires custom implementation.
2. **Block bootstrap** (or subsampling): valid under weaker conditions than the
   standard bootstrap but requires choosing a block/subsample size.
3. **Cross-fitted AIPW** (recommended): switch from pure matching to doubly
   robust estimation, which has straightforward inference via the influence
   function SE.

### Influence-Function SE (for Cross-Fitted AIPW)

When using cross-fitted AIPW, the influence-function standard error is
asymptotically valid (Chernozhukov et al. 2018). This is the simplest
path to correct inference:

```python
# From the cross-fitted AIPW section:
scores_cf = score_1 - score_0
se_if = scores_cf.std() / np.sqrt(n)
# This is a valid asymptotic SE -- no bootstrap needed
```

### Naive OLS SEs on Matched Data Are Wrong

Abadie and Spiess (2022) show that running OLS on matched data and using standard
OLS standard errors produces incorrect inference. The matching step introduces
dependence between observations (matched pairs are not independent), and OLS SEs
ignore this dependence. This applies to all forms of matching (NN, caliper,
Mahalanobis).

**Never** report OLS standard errors from a regression on matched data as if
they were valid. Use bootstrap (for non-NN methods), Abadie-Imbens SEs (for NN),
or switch to AIPW with influence-function SEs.

### Inference Summary

| Method | Valid SE Approach | Invalid |
|--------|-------------------|---------|
| IPW / Weighted regression | Bootstrap (re-estimate PS each iteration) | Naive WLS SE (ignores PS estimation step) |
| NN matching (with/without replacement) | Abadie-Imbens variance; block bootstrap | Standard bootstrap; OLS on matched data |
| Caliper / radius matching | Bootstrap; Abadie-Imbens | OLS on matched data |
| AIPW (non-cross-fitted) | Bootstrap | Influence-function SE (requires cross-fitting) |
| Cross-fitted AIPW | Influence-function SE: std(scores)/sqrt(N) | None (this is the gold standard) |
| CEM + weighted regression | Bootstrap | Unweighted OLS SE |

## Gotchas and Common Mistakes

### 1. The Propensity Score Paradox

King and Nielsen (2019) argue that propensity score matching (nearest-neighbor on
the PS) can increase imbalance and model dependence as more observations are pruned.
The core issue is that collapsing a multidimensional covariate space to a scalar
(the PS) discards information about which specific covariates are balanced.

**Scope of the critique:** This critique is specific to **PSM matching** -- it does
not apply to IPW or doubly robust estimators that use propensity scores for
weighting rather than matching. When the propensity score is used for weighting,
the dimensional reduction is less harmful because all observations contribute to
the estimate.

**Practical response:** If using PSM, verify covariate-level balance (not just PS
balance) and compare results to Mahalanobis matching or CEM. If using IPW or AIPW,
the King-Nielsen critique is less relevant.

### 2. Bootstrap is Invalid for NN Matching

Abadie and Imbens (2008) proved the standard bootstrap is inconsistent for
nearest-neighbor matching. See the Inference section for alternatives. This is
not a minor technical point -- the coverage of bootstrap confidence intervals
for NN matching can be substantially wrong.

### 3. Variable Selection: Instruments Amplify Bias

Including a variable that predicts treatment but not the outcome (an instrument)
in the propensity score model amplifies bias and increases variance (Brookhart
et al. 2006). This is the opposite of the intuition from predictive modeling,
where "more variables is better." In the propensity score context, the right
variables to include are confounders and outcome predictors.

### 4. Common Support Violations and Extreme Weights

Propensity scores near 0 or 1 produce extreme IPW weights (approaching infinity).
These observations have near-deterministic treatment assignment -- they are
fundamentally different from the population where treatment is uncertain.

**Diagnostics:** Check weight distributions, ESS, max weights. **Remedies:**
trim to [0.1, 0.9] (Crump et al. 2009), use stabilized weights, truncate at
a percentile (99th), or use overlap weights (Li, Morgan, and Zaslavsky 2018).

### 5. Matching With vs. Without Replacement

With replacement: lower bias (each treated unit gets its best possible match)
but higher variance (some controls used repeatedly, reducing effective sample
size). Without replacement: higher bias (later matches may be poor) but lower
variance. Report which approach was used and the distribution of match counts.

### 6. Curse of Dimensionality in Covariate Matching

Mahalanobis and exact matching degrade rapidly as the number of covariates
increases. In high dimensions, all observations are approximately equidistant.
This is why the propensity score (a dimension reduction device) was introduced
in the first place. For high-dimensional covariate spaces, prefer PSM or CEM
over direct Mahalanobis matching.

### 7. Extreme IPW Weights: Stabilization and Truncation

Even after common support trimming, some weights may be very large. Three
remedies, in order of preference:
1. **Overlap weights** (Li et al. 2018): change the estimand to the overlap
   population -- weights are naturally bounded
2. **Stabilized weights**: replace numerator 1 with marginal treatment probability
3. **Weight truncation**: clip at a percentile (e.g., 99th) -- this introduces
   bias but reduces variance

Always report the effective sample size and maximum weight alongside the estimate.

### 8. Naive Post-Matching Standard Errors

Abadie and Spiess (2022) demonstrate that OLS standard errors computed on matched
data are incorrect. The matching process creates dependence between observations
that OLS SEs do not account for. This affects all matching methods, not just
nearest-neighbor. See the Inference section for correct alternatives.

## Decision Guide: Which Method to Use

```
Selection-on-observables design confirmed?
│
├─ Yes → How many covariates?
│   │
│   ├─ Few (< 5), mostly categorical
│   │   └─ Exact matching or CEM
│   │       (guaranteed balance on matched vars)
│   │
│   ├─ Moderate (5-20)
│   │   └─ Cross-fitted AIPW (recommended default)
│   │       ├─ Valid if either PS or outcome model correct
│   │       ├─ Influence-function SE (no bootstrap needed)
│   │       └─ Report balance diagnostics on PS-weighted sample
│   │
│   └─ Many (20+) or high-dimensional
│       └─ Cross-fitted AIPW with flexible ML for nuisance
│           (e.g., Ridge/Lasso for outcome model, regularized logistic for PS)
│           └─ Consider DML (Chernozhukov et al. 2018) framework
│
├─ Need ATT specifically?
│   └─ Matching (NN or CEM) gives ATT naturally
│       IPW-ATT and AIPW-ATT also available
│       └─ If NN matching: use Abadie-Imbens SE, NOT bootstrap
│
├─ Severe overlap problems?
│   └─ Overlap weights (Li et al. 2018)
│       ├─ Estimates ATO (overlap population)
│       ├─ Naturally bounded weights
│       └─ No arbitrary trimming threshold
│
└─ No → Selection-on-observables is not credible
    └─ Consider IV, DiD, or RD instead
        (see causal-inference.md Method Selection Guide)
```

## References and Further Reading

### Foundations

Rosenbaum, P.R. and Rubin, D.B. (1983). "The Central Role of the Propensity Score in Observational Studies for Causal Effects." *Biometrika*, 70(1), 41-55. https://doi.org/10.1093/biomet/70.1.41

Stuart, E.A. (2010). "Matching Methods for Causal Inference: A Review and a Look Forward." *Statistical Science*, 25(1), 1-21. https://doi.org/10.1214/09-STS313

Ho, D.E., Imai, K., King, G., and Stuart, E.A. (2007). "Matching as Nonparametric Preprocessing for Reducing Model Dependence in Parametric Causal Inference." *Political Analysis*, 15(3), 199-236.

### Matching Methods

Austin, P.C. (2011). "An Introduction to Propensity Score Methods for Reducing the Effects of Confounding in Observational Studies." *Multivariate Behavioral Research*, 46(3), 399-424.

Iacus, S.M., King, G., and Porro, G. (2012). "Causal Inference without Balance Checking: Coarsened Exact Matching." *Political Analysis*, 20(1), 1-24. https://doi.org/10.1093/pan/mpr013

King, G. and Nielsen, R. (2019). "Why Propensity Scores Should Not Be Used for Matching." *Political Analysis*, 27(4), 435-454.

Caliendo, M. and Kopeinig, S. (2008). "Some Practical Guidance for the Implementation of Propensity Score Matching." *Journal of Economic Surveys*, 22(1), 31-72.

### Inverse Probability Weighting

Li, F., Morgan, K.L., and Zaslavsky, A.M. (2018). "Balancing Covariates via Propensity Score Weighting." *Journal of the American Statistical Association*, 113(521), 390-400.

Crump, R.K., Hotz, V.J., Imbens, G.W., and Mitnik, O.A. (2009). "Dealing with Limited Overlap in Estimation of Average Treatment Effects." *Biometrika*, 96(1), 187-199.

### Doubly Robust Estimation

Robins, J.M., Rotnitzky, A., and Zhao, L.P. (1994). "Estimation of Regression Coefficients When Some Regressors Are Not Always Observed." *Journal of the American Statistical Association*, 89(427), 846-866.

Bang, H. and Robins, J.M. (2005). "Doubly Robust Estimation in Missing Data and Causal Inference Models." *Biometrics*, 61(4), 962-973.

Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey, W., and Robins, J. (2018). "Double/Debiased Machine Learning for Treatment and Structural Parameters." *Econometrics Journal*, 21(1), C1-C68.

### Inference

Abadie, A. and Imbens, G.W. (2006). "Large Sample Properties of Matching Estimators for Average Treatment Effects." *Econometrica*, 74(1), 235-267.

Abadie, A. and Imbens, G.W. (2008). "On the Failure of the Bootstrap for Matching Estimators." *Econometrica*, 76(6), 1537-1557. https://doi.org/10.3982/ECTA6474

Kish, L. (1965). *Survey Sampling*. John Wiley & Sons.

Myers, J.A. et al. (2011). "Effects of Adjusting for Instrumental Variables on Bias and Precision of Effect Estimates." *American Journal of Epidemiology*, 174(11), 1213-1222. https://doi.org/10.1093/aje/kwr364

Rubin, D.B. (2001). "Using Propensity Scores to Help Design Observational Studies: Application to the Tobacco Litigation." *Health Services and Outcomes Research Methodology*, 2, 169-188.

Abadie, A. and Spiess, J. (2022). "Robust Post-Matching Inference." *Journal of the American Statistical Association*, 117(538), 983-995.

### Variable Selection

Brookhart, M.A., Schneeweiss, S., Rothman, K.J., Glynn, R.J., Avorn, J., and Sturmer, T. (2006). "Variable Selection for Propensity Score Models." *American Journal of Epidemiology*, 163(12), 1149-1156.

### Textbooks and Accessible Resources

Cunningham, S. (2021). *Causal Inference: The Mixtape*. Yale University Press. https://mixtape.scunning.com/ (Matching chapter)

Huntington-Klein, N. (2022). *The Effect: An Introduction to Research Design and Causality*. Chapman & Hall/CRC. https://theeffectbook.net/ (Ch. 14)

Facure, M. (2022). *Causal Inference for the Brave and True*. https://matheusfacure.github.io/python-causality-handbook/ (Chs. 11-12)
