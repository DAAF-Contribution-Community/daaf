# Tuning

Hyperparameter tuning via tune_grid(), the tune() placeholder, dials parameter
ranges, collecting results, and finalizing workflows with the best parameters.

## The Tuning Workflow

1. Mark parameters with `tune()` in the model spec or recipe
2. Create resamples (see `resampling.md`)
3. Run `tune_grid()` to evaluate parameter combinations
4. Inspect results with `collect_metrics()` and `show_best()`
5. Select best parameters with `select_best()`
6. Finalize the workflow with `finalize_workflow()`
7. Fit the finalized workflow on the full training set

## Step 1: Mark Parameters with tune()

Replace fixed values with `tune()` to indicate "search over this":

```r
library(tidymodels)

# --- Model with tunable parameters ---
spec <- rand_forest(
  trees = 500,
  mtry = tune(),        # Search over mtry
  min_n = tune()        # Search over min_n
) |>
  set_engine("ranger") |>
  set_mode("classification")

# --- Recipe with tunable parameters ---
rec <- recipe(outcome ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors()) |>
  step_pca(all_numeric_predictors(), num_comp = tune())  # Search over components

# --- Bundle ---
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)
```

## Step 2: Create Resamples

```r
set.seed(42)
folds <- vfold_cv(train_data, v = 10, strata = outcome)
```

See `resampling.md` for details on resampling strategies.

## Step 3: Run tune_grid()

```r
# --- Automatic grid (space-filling design) ---
set.seed(42)
tune_results <- tune_grid(
  wf,
  resamples = folds,
  grid = 20           # 20 parameter combinations
)

# --- Manual grid ---
param_grid <- grid_regular(
  mtry(range = c(2, 8)),
  min_n(range = c(5, 30)),
  levels = 5           # 5 levels per parameter = 25 combinations
)

set.seed(42)
tune_results <- tune_grid(
  wf,
  resamples = folds,
  grid = param_grid
)
```

### Grid Types

| Function | Strategy | When to Use |
|----------|----------|-------------|
| `grid_regular()` | All combinations of evenly-spaced values | Few parameters (2-3), small grids |
| `grid_random()` | Random sampling from parameter ranges | Many parameters, exploration phase |
| `grid_space_filling()` | Space-filling design (Latin hypercube and variants) | Many parameters, better coverage than random |
| Integer (e.g., `grid = 20`) | Auto space-filling design with N points | Quick exploration |

`grid_latin_hypercube()` was deprecated in dials 1.3.0 (verified: calling it warns
"Please use `grid_space_filling()` instead") — use `grid_space_filling()`.

## Step 4: Inspect Results

```r
# --- Summary metrics across all parameter combos ---
collect_metrics(tune_results)
# Returns tibble with: mtry, min_n, .metric, .estimator, mean, std_err, n

# --- Top 5 by a specific metric ---
show_best(tune_results, metric = "accuracy", n = 5)
show_best(tune_results, metric = "roc_auc", n = 5)

# --- Plot performance ---
autoplot(tune_results)
```

## Step 5: Select Best Parameters

```r
# --- Select the single best parameter combination ---
best_params <- select_best(tune_results, metric = "accuracy")
best_params
# Returns a tibble with one row: the best mtry and min_n values

# --- Select within one SE of the best (simpler model preference) ---
best_params <- select_by_one_std_err(
  tune_results,
  metric = "accuracy",
  mtry, min_n   # Parameters to simplify (prefer smaller values)
)
```

## Step 6: Finalize the Workflow

```r
# Replace tune() placeholders with the selected values
final_wf <- finalize_workflow(wf, best_params)

# Verify: print to confirm tune() values are replaced
final_wf
```

## Step 7: Fit on Full Training Data

```r
# Fit the finalized workflow on ALL training data (not just CV folds)
final_fit <- final_wf |> fit(data = train_data)

# Evaluate on held-out test set
results <- final_fit |> augment(new_data = test_data)
accuracy(results, truth = outcome, estimate = .pred_class)
```

### last_fit() Shortcut

`last_fit()` fits on training and evaluates on test in one step:

```r
# Uses the original split object
final_fit <- last_fit(final_wf, split = data_split)

# Collect test metrics
collect_metrics(final_fit)

# Get test predictions
collect_predictions(final_fit)
```

## Complete Tuning Example

```r
library(tidymodels)

# --- Data ---
set.seed(42)
split <- initial_split(iris, prop = 0.8, strata = Species)
train_data <- training(split)
test_data <- testing(split)

# --- Recipe ---
rec <- recipe(Species ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors())

# --- Tunable model ---
spec <- rand_forest(
  trees = 500,
  mtry = tune(),
  min_n = tune()
) |>
  set_engine("ranger") |>
  set_mode("classification")

# --- Workflow ---
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)

# --- Resamples ---
set.seed(42)
folds <- vfold_cv(train_data, v = 5, strata = Species)

# --- Tune ---
set.seed(42)
tune_results <- tune_grid(wf, resamples = folds, grid = 10)

# --- Select best ---
best <- select_best(tune_results, metric = "accuracy")

# --- Finalize and fit ---
final_wf <- finalize_workflow(wf, best)
final_fit <- final_wf |> fit(data = train_data)

# --- Evaluate ---
results <- final_fit |> augment(new_data = test_data)
accuracy(results, truth = Species, estimate = .pred_class)
```

## Controlling Metrics During Tuning

By default, tune_grid collects a standard set of metrics. Specify custom metrics:

```r
# --- Custom metric set ---
my_metrics <- metric_set(accuracy, roc_auc, f_meas)

tune_results <- tune_grid(
  wf,
  resamples = folds,
  grid = 20,
  metrics = my_metrics
)
```

## Parallel Processing

tune 2.0 changed its parallel backend: foreach/doParallel is **no longer supported**
(tune 2.0.1 NEWS: "The `foreach` package is no longer supported. Instead, use the
future or mirai packages."). In this environment, use future — doParallel and mirai
are not installed.

```r
library(future)
plan(multisession, workers = 2)   # size to available cores

# tune_grid dispatches resamples to the future workers automatically
tune_results <- tune_grid(wf, resamples = folds, grid = 50)

plan(sequential)   # release the workers when done
```

See `?tune::parallelism` for details. Old `registerDoParallel()` code silently
runs sequentially under tune 2.0 — migrate it to `plan(multisession)`.

## dials: Parameter Ranges

The dials package defines parameter objects with sensible defaults:

```r
# --- Inspect parameter ranges ---
mtry()          # Default range depends on data
min_n()         # Default: 2 to 40
trees()         # Default: 1 to 2000
tree_depth()    # Default: 1 to 15
learn_rate()    # Default: -10 to -1 (log10 scale)
penalty()       # Default: -10 to 0 (log10 scale)

# --- Custom ranges ---
mtry(range = c(2, 10))
min_n(range = c(5, 50))
penalty(range = c(-5, -1))
```

## Quick Reference

| Task | Code |
|------|------|
| Mark for tuning | `param = tune()` |
| Auto grid | `tune_grid(wf, resamples, grid = 20)` |
| Regular grid | `grid_regular(mtry(), min_n(), levels = 5)` |
| Random grid | `grid_random(mtry(), min_n(), size = 20)` |
| Space-filling grid | `grid_space_filling(mtry(), min_n(), size = 20)` |
| See all results | `collect_metrics(tune_results)` |
| Top N results | `show_best(tune_results, metric = "accuracy")` |
| Best params | `select_best(tune_results, metric = "accuracy")` |
| Simpler model | `select_by_one_std_err(tune_results, metric, ...)` |
| Finalize | `finalize_workflow(wf, best_params)` |
| Last fit | `last_fit(final_wf, split)` |
| Custom metrics | `tune_grid(..., metrics = metric_set(accuracy, roc_auc))` |
| Parallel tuning | `library(future); plan(multisession)` before `tune_grid()` |
