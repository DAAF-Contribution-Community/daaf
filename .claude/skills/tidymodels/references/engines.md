# Engines

Engine-specific configuration for ranger (random forest), glmnet (regularized
regression), xgboost (gradient boosting), and kknn (k-nearest neighbors).
Covers engine args passed through `set_engine()`, installation, and tunable
parameters specific to each backend.

## Engine Architecture

In tidymodels, `set_engine()` selects the backend implementation. The parsnip
model type defines the interface; the engine provides the computation:

```
rand_forest(trees = 500) |>     # parsnip: what kind of model
  set_engine("ranger") |>       # engine: which implementation
  set_mode("classification")    # task type
```

Engine-specific arguments are passed via `set_engine()`:

```r
# Engine args go inside set_engine(), not the model function
spec <- rand_forest(trees = 500) |>
  set_engine("ranger", importance = "impurity") |>
  set_mode("classification")
```

## ranger (Random Forest)

Fast C++ random forest implementation. The preferred engine for `rand_forest()`.

### Installation

```r
install.packages("ranger")
```

### Parsnip-to-ranger Parameter Mapping

| parsnip Parameter | ranger Argument | Notes |
|-------------------|----------------|-------|
| `trees` | `num.trees` | Number of trees |
| `mtry` | `mtry` | Features sampled per split |
| `min_n` | `min.node.size` | Minimum node size |

### Engine-Specific Arguments

```r
spec <- rand_forest(trees = 500, mtry = 4, min_n = 5) |>
  set_engine("ranger",
    importance = "impurity",     # Variable importance: "impurity" or "permutation"
    num.threads = 4,             # Parallel threads
    seed = 42,                   # Reproducibility (ranger has its own seed)
    respect.unordered.factors = "order"  # Better handling of factors
  ) |>
  set_mode("classification")
```

### Variable Importance

Importance must be requested at fit time via `set_engine("ranger", importance =
"impurity")` (or `"permutation"`) — with ranger's default `importance = "none"`,
both `$variable.importance` and vip fail with "No variable importance found"
(verified).

```r
fit <- wf |> fit(data = train_data)  # spec must include importance = "impurity"

# Extract ranger object for importance
engine_fit <- extract_fit_engine(fit)
importance_vals <- engine_fit$variable.importance

# Or use vip package
library(vip)
fit |> extract_fit_parsnip() |> vip()
```

For model-agnostic alternatives (permutation importance via DALEX/iml, SHAP),
see `interpretation.md`.

### Probability Calibration

ranger's probability predictions may be uncalibrated for small forests. Use
`trees >= 500` for reliable probability estimates.

## glmnet (Regularized Regression)

Lasso, ridge, and elastic net via coordinate descent. Used with `linear_reg()`
and `logistic_reg()`.

### Installation

```r
install.packages("glmnet")
```

### Parsnip-to-glmnet Parameter Mapping

| parsnip Parameter | glmnet Argument | Notes |
|-------------------|----------------|-------|
| `penalty` | `lambda` | Regularization strength |
| `mixture` | `alpha` | L1/L2 blend: 0 = ridge, 1 = lasso |

### How penalty and mixture Work

| mixture | Regularization Type | Effect |
|---------|-------------------|--------|
| 0 | Ridge (L2) | Shrinks coefficients toward zero, keeps all features |
| 1 | Lasso (L1) | Shrinks some coefficients to exactly zero (feature selection) |
| 0.5 | Elastic net | Mix of L1 and L2 |

### Engine-Specific Arguments

```r
spec <- linear_reg(penalty = tune(), mixture = tune()) |>
  set_engine("glmnet",
    nlambda = 100,              # Number of lambda values in path
    standardize = TRUE,         # Standardize internally (default)
    family = "gaussian"         # Explicitly set family
  ) |>
  set_mode("regression")
```

### Important: glmnet and penalty

glmnet internally fits a full regularization path (many lambda values). The
`penalty` parameter in parsnip selects which point on that path to use for
predictions. If `penalty` is not set, glmnet uses its own default (often the
smallest lambda), which may not be what you want.

Always either:
1. Set `penalty` explicitly, or
2. Use `tune()` and let tuning find the best value

```r
# --- Explicit penalty ---
spec <- linear_reg(penalty = 0.01, mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")

# --- Tunable penalty (recommended) ---
spec <- linear_reg(penalty = tune(), mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")
```

### Extracting Coefficients

```r
fit <- wf |> fit(data = train_data)
engine_fit <- extract_fit_engine(fit)

# Coefficients at the selected penalty
coefs <- coef(engine_fit, s = 0.01)
# coefs is a sparse matrix; convert for readability
coef_df <- as.data.frame(as.matrix(coefs))
```

## xgboost (Gradient Boosting)

Extreme gradient boosting. Used with `boost_tree()`.

### Installation

```r
install.packages("xgboost")
```

### Parsnip-to-xgboost Parameter Mapping

| parsnip Parameter | xgboost Argument | Notes |
|-------------------|-----------------|-------|
| `trees` | `nrounds` | Number of boosting rounds |
| `tree_depth` | `max_depth` | Maximum tree depth |
| `learn_rate` | `eta` | Learning rate |
| `min_n` | `min_child_weight` | Minimum sum of instance weight in a child |
| `loss_reduction` | `gamma` | Minimum loss reduction for a split |
| `sample_size` | `subsample` | Row subsampling fraction |
| `mtry` | `colsample_bynode` | Column subsampling per split. Passed as a **count** by default (verified via `translate()`: `mtry = 2` becomes `colsample_bynode = 2`). To pass a proportion, add `set_engine("xgboost", counts = FALSE)` and give `mtry` a value in (0, 1]. |

### Engine-Specific Arguments

```r
spec <- boost_tree(
  trees = 500,
  tree_depth = 6,
  learn_rate = 0.1,
  min_n = 10,
  loss_reduction = 0,
  sample_size = 0.8
) |>
  set_engine("xgboost",
    nthread = 4,                 # Parallel threads
    objective = "binary:logistic",  # Objective function
    eval_metric = "auc",         # Evaluation metric
    early_stop = 20,             # Early stopping rounds (via parsnip arg)
    verbose = 0                  # Suppress training output
  ) |>
  set_mode("classification")
```

### xgboost Data Requirements

- xgboost only accepts numeric data. Factor/character columns must be encoded
  first (recipes `step_dummy()` handles this automatically in a workflow)
- Missing values are handled natively by xgboost (it learns optimal split
  directions for NA)

### Feature Importance

```r
fit <- wf |> fit(data = train_data)
engine_fit <- extract_fit_engine(fit)

# Built-in importance
xgboost::xgb.importance(model = engine_fit)

# Or via vip
library(vip)
fit |> extract_fit_parsnip() |> vip()
```

## kknn (K-Nearest Neighbors)

Weighted k-nearest neighbors. Used with `nearest_neighbor()`.

### Installation

```r
install.packages("kknn")
```

### Parsnip-to-kknn Parameter Mapping

| parsnip Parameter | kknn Argument | Notes |
|-------------------|--------------|-------|
| `neighbors` | `k` | Number of neighbors |
| `weight_func` | `kernel` | Weighting function |
| `dist_power` | `distance` | Minkowski distance power |

### Weight Functions

| `weight_func` | Behavior |
|---------------|----------|
| `"rectangular"` | Uniform (all neighbors equally weighted) |
| `"triangular"` | Linear decay |
| `"epanechnikov"` | Quadratic decay |
| `"gaussian"` | Gaussian decay |
| `"optimal"` | Optimized kernel |

### KNN Data Requirements

- **Scaling is critical**: KNN uses distance metrics. Features with larger ranges
  dominate. Always include `step_normalize()` in the recipe.
- KNN stores the entire training set -- memory-intensive for large datasets.

```r
rec <- recipe(outcome ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())

spec <- nearest_neighbor(neighbors = tune()) |>
  set_engine("kknn") |>
  set_mode("classification")
```

## Engine Comparison

| Engine | Model Type | Speed | Handles NAs | Needs Scaling | Feature Selection |
|--------|-----------|-------|-------------|---------------|-------------------|
| ranger | rand_forest | Fast | No (impute first) | No | Built-in importance |
| glmnet | linear_reg, logistic_reg | Very fast | No (impute first) | Auto-standardizes | Lasso zeros out features |
| xgboost | boost_tree | Fast | Yes (native) | No | Built-in importance |
| kknn | nearest_neighbor | Slow (large data) | No (impute first) | Yes (critical) | No |

## Quick Reference

| Task | Code |
|------|------|
| ranger with importance | `set_engine("ranger", importance = "impurity")` |
| glmnet lasso | `linear_reg(penalty = tune(), mixture = 1) \|> set_engine("glmnet")` |
| glmnet ridge | `linear_reg(penalty = tune(), mixture = 0) \|> set_engine("glmnet")` |
| xgboost with threads | `set_engine("xgboost", nthread = 4)` |
| kknn optimal kernel | `set_engine("kknn") with weight_func = "optimal"` |
| Extract engine fit | `extract_fit_engine(fitted_wf)` |
| Variable importance | `library(vip); vip(extract_fit_parsnip(fit))` (ranger: requires `importance =` in `set_engine()`) |
