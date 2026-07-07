# Models (parsnip)

Parsnip model specifications: defining algorithm, engine, and mode. Covers the
five most common model types, their available engines, and tunable parameters.

## The Parsnip Model Specification Pattern

Every model in tidymodels follows the same three-step pattern:

```r
spec <- model_type(param1 = value, param2 = value) |>
  set_engine("engine_name") |>
  set_mode("classification")  # or "regression"
```

| Step | Purpose | Example |
|------|---------|---------|
| `model_type()` | Algorithm family | `rand_forest()`, `linear_reg()` |
| `set_engine()` | Implementation backend | `"ranger"`, `"glmnet"`, `"xgboost"` |
| `set_mode()` | Task type | `"classification"` or `"regression"` |

The mode must always be set explicitly. Some models (like `logistic_reg`) default
to one mode, but always be explicit.

## linear_reg (Linear Regression)

Encompasses OLS, ridge, lasso, and elastic net depending on engine and parameters.

```r
# --- Plain OLS ---
spec <- linear_reg() |>
  set_engine("lm") |>
  set_mode("regression")

# --- Ridge (L2 penalty, mixture = 0) ---
spec <- linear_reg(penalty = 0.01, mixture = 0) |>
  set_engine("glmnet") |>
  set_mode("regression")

# --- Lasso (L1 penalty, mixture = 1) ---
spec <- linear_reg(penalty = 0.01, mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")

# --- Elastic net (0 < mixture < 1) ---
spec <- linear_reg(penalty = 0.01, mixture = 0.5) |>
  set_engine("glmnet") |>
  set_mode("regression")
```

| Parameter | Meaning | Range |
|-----------|---------|-------|
| `penalty` | Regularization strength (lambda) | [0, Inf) |
| `mixture` | L1/L2 blend (alpha): 0 = ridge, 1 = lasso | [0, 1] |

| Engine | Backend Package | Notes |
|--------|----------------|-------|
| `"lm"` | base R `lm()` | OLS only, no regularization |
| `"glmnet"` | glmnet | Ridge/lasso/elasticnet; requires penalty + mixture |

## logistic_reg (Logistic Regression)

**Binary** classification via logistic regression. `logistic_reg()` has no
multiclass argument (its parameters are only `penalty` and `mixture` — there is
no `multi_class` argument; that is scikit-learn's API). For outcomes with 3+
classes, use `multinom_reg()` below.

```r
# --- Standard logistic ---
spec <- logistic_reg() |>
  set_engine("glm") |>
  set_mode("classification")

# --- Regularized logistic ---
spec <- logistic_reg(penalty = 0.01, mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("classification")
```

| Parameter | Meaning | Range |
|-----------|---------|-------|
| `penalty` | Regularization strength | [0, Inf) |
| `mixture` | L1/L2 blend | [0, 1] |

| Engine | Notes |
|--------|-------|
| `"glm"` | Base R `glm(family = binomial)`. No regularization. |
| `"glmnet"` | Regularized. Binary outcomes only — for 3+ classes use `multinom_reg()`. |

## multinom_reg (Multinomial Regression)

Multiclass (3+ level) classification via multinomial logistic regression.

```r
# --- Regularized multinomial (glmnet) ---
spec <- multinom_reg(penalty = 0.01) |>
  set_engine("glmnet") |>
  set_mode("classification")

# --- Unregularized multinomial (nnet) ---
spec <- multinom_reg() |>
  set_engine("nnet") |>
  set_mode("classification")
```

| Engine | Notes |
|--------|-------|
| `"nnet"` | Base multinomial via `nnet::multinom()`. No regularization. |
| `"glmnet"` | Regularized; requires `penalty`. |

Both engines are installed and verified in this environment. Tree models
(`rand_forest`, `boost_tree`) also handle multiclass outcomes natively.

## rand_forest (Random Forest)

Ensemble of decision trees with bagging and random feature selection.

```r
# --- Classification ---
spec <- rand_forest(
  trees = 500,
  mtry = 3,
  min_n = 5
) |>
  set_engine("ranger") |>
  set_mode("classification")

# --- Regression ---
spec <- rand_forest(trees = 500) |>
  set_engine("ranger") |>
  set_mode("regression")
```

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `trees` | Number of trees | 500 |
| `mtry` | Predictors sampled per split | floor(sqrt(p)) for classification, floor(p/3) for regression |
| `min_n` | Minimum node size to split | 10 (classification), 5 (regression) — parsnip fits ranger *probability* forests for classification, whose ranger default `min.node.size` is 10 (verified on a fitted model), not the 1 used by plain classification forests |

| Engine | Notes |
|--------|-------|
| `"ranger"` | Fast C++ implementation. Preferred engine. |
| `"randomForest"` | Classic R implementation. Slower. |

## boost_tree (Gradient Boosting)

Boosted ensemble of decision trees.

```r
# --- XGBoost ---
spec <- boost_tree(
  trees = 500,
  tree_depth = 6,
  learn_rate = 0.1,
  min_n = 10,
  loss_reduction = 0,
  sample_size = 0.8
) |>
  set_engine("xgboost") |>
  set_mode("classification")

# --- Regression ---
spec <- boost_tree(trees = 500, learn_rate = 0.1) |>
  set_engine("xgboost") |>
  set_mode("regression")
```

| Parameter | Meaning | Typical Range |
|-----------|---------|---------------|
| `trees` | Number of boosting iterations | 100-2000 |
| `tree_depth` | Max tree depth | 1-15 |
| `learn_rate` | Step size (eta) | 0.001-0.3 |
| `min_n` | Minimum observations in node | 1-40 |
| `loss_reduction` | Minimum loss reduction to split (gamma) | 0-10 |
| `sample_size` | Row subsampling fraction | 0.5-1.0 |
| `mtry` | Column subsampling (as count) | 1-p |

| Engine | Notes |
|--------|-------|
| `"xgboost"` | Fast, feature-rich. Preferred engine. |

## nearest_neighbor (K-Nearest Neighbors)

Instance-based learning; classify/predict based on nearest training examples.

```r
spec <- nearest_neighbor(
  neighbors = 5,
  weight_func = "rectangular",
  dist_power = 2
) |>
  set_engine("kknn") |>
  set_mode("classification")
```

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `neighbors` | Number of neighbors (k) | 5 |
| `weight_func` | Weighting function | "rectangular" (uniform) |
| `dist_power` | Minkowski distance power | 2 (Euclidean) |

| Engine | Notes |
|--------|-------|
| `"kknn"` | Weighted KNN. The primary engine. |

## Model Comparison Table

| Model | Regression | Classification | Key Engines | Tunable Params |
|-------|-----------|----------------|-------------|----------------|
| `linear_reg` | Yes | No | lm, glmnet | penalty, mixture |
| `logistic_reg` | No | Yes (binary) | glm, glmnet | penalty, mixture |
| `multinom_reg` | No | Yes (multiclass) | nnet, glmnet | penalty, mixture |
| `rand_forest` | Yes | Yes | ranger | trees, mtry, min_n |
| `boost_tree` | Yes | Yes | xgboost | trees, tree_depth, learn_rate, min_n |
| `nearest_neighbor` | Yes | Yes | kknn | neighbors, weight_func, dist_power |

## Extracting Results from Fitted Models

After fitting a workflow, extract the underlying parsnip fit:

```r
fit <- wf |> fit(data = train_data)

# Extract parsnip fit
parsnip_fit <- extract_fit_parsnip(fit)

# Extract the raw engine object (e.g., ranger object)
engine_fit <- extract_fit_engine(fit)

# For ranger: variable importance — ONLY works if importance was requested at
# fit time via set_engine("ranger", importance = "impurity"); otherwise vip
# errors with "No variable importance found" (verified)
library(vip)
vip(parsnip_fit)

# For glmnet: coefficient path
coef(engine_fit, s = 0.01)
```

For the full interpretation toolkit (permutation importance, PDP/ICE, SHAP via
DALEX / iml / kernelshap), see `interpretation.md`.

## Quick Reference

| Task | Code |
|------|------|
| OLS | `linear_reg() \|> set_engine("lm")` |
| Ridge | `linear_reg(penalty = 0.01, mixture = 0) \|> set_engine("glmnet")` |
| Lasso | `linear_reg(penalty = 0.01, mixture = 1) \|> set_engine("glmnet")` |
| Logistic (binary) | `logistic_reg() \|> set_engine("glm")` |
| Multinomial (3+ classes) | `multinom_reg() \|> set_engine("nnet")` |
| Random forest | `rand_forest(trees = 500) \|> set_engine("ranger")` |
| XGBoost | `boost_tree(trees = 500) \|> set_engine("xgboost")` |
| KNN | `nearest_neighbor(neighbors = 5) \|> set_engine("kknn")` |
