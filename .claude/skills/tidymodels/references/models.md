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

Binary and multiclass classification via logistic regression.

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
| `"glmnet"` | Regularized. Handles multiclass via multinomial. |

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
| `min_n` | Minimum node size to split | 1 (classification), 5 (regression) |

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
| `logistic_reg` | No | Yes | glm, glmnet | penalty, mixture |
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

# For ranger: variable importance
library(vip)
vip(parsnip_fit)

# For glmnet: coefficient path
coef(engine_fit, s = 0.01)
```

## Quick Reference

| Task | Code |
|------|------|
| OLS | `linear_reg() \|> set_engine("lm")` |
| Ridge | `linear_reg(penalty = 0.01, mixture = 0) \|> set_engine("glmnet")` |
| Lasso | `linear_reg(penalty = 0.01, mixture = 1) \|> set_engine("glmnet")` |
| Logistic | `logistic_reg() \|> set_engine("glm")` |
| Random forest | `rand_forest(trees = 500) \|> set_engine("ranger")` |
| XGBoost | `boost_tree(trees = 500) \|> set_engine("xgboost")` |
| KNN | `nearest_neighbor(neighbors = 5) \|> set_engine("kknn")` |
