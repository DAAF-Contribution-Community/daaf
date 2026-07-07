# Workflows

The workflows package bundles a recipe (preprocessing) and a model spec (parsnip)
into a single object that handles fit, predict, and augment seamlessly. This is
the central organizational unit in tidymodels.

## Why Workflows?

Without workflows, you must manually prep/bake recipes and fit models separately.
Workflows automate this and ensure preprocessing is applied correctly during
cross-validation and tuning (preventing data leakage).

| Without Workflow | With Workflow |
|-----------------|---------------|
| `prep()` recipe on training data | `fit()` does everything |
| `bake()` to transform training data | Preprocessing automatic |
| `fit()` model on baked data | Single object to manage |
| `bake()` test data separately | `predict()` handles preprocessing |
| Manual coordination for CV | CV/tuning works automatically |

## Building a Workflow

```r
library(tidymodels)

# --- 1. Define recipe ---
rec <- recipe(outcome ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())

# --- 2. Define model spec ---
spec <- rand_forest(trees = 500) |>
  set_engine("ranger") |>
  set_mode("classification")

# --- 3. Bundle into workflow ---
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)
```

## Fitting a Workflow

```r
# fit() preps the recipe and fits the model in one step
fit <- wf |> fit(data = train_data)

# The recipe is prepped on train_data only -- no leakage
```

## Predicting with a Workflow

### predict()

Returns a tibble with prediction columns only:

```r
# Classification: returns .pred_class
preds <- fit |> predict(new_data = test_data)

# Regression: returns .pred
preds <- fit |> predict(new_data = test_data)

# Probabilities: returns .pred_{level} columns
probs <- fit |> predict(new_data = test_data, type = "prob")
```

### augment() (Preferred)

Returns the original data with prediction columns appended:

```r
results <- fit |> augment(new_data = test_data)

# Classification results include:
# - .pred_class (predicted class)
# - .pred_{level} (probability for each level)
# - All original columns from test_data

# Regression results include:
# - .pred (predicted value)
# - All original columns from test_data
```

`augment()` is preferred because it keeps the truth column alongside predictions,
making it easy to compute metrics directly:

```r
results <- fit |> augment(new_data = test_data)
accuracy(results, truth = outcome, estimate = .pred_class)
rmse(results, truth = outcome, estimate = .pred)
```

## Extracting Components

After fitting, extract internal components for inspection:

```r
# Extract the fitted parsnip model
parsnip_fit <- extract_fit_parsnip(fit)

# Extract the raw engine object (e.g., ranger, glmnet)
engine_fit <- extract_fit_engine(fit)

# Extract the prepped recipe
prepped_rec <- extract_recipe(fit)

# Extract the preprocessor (recipe before prepping)
preprocessor <- extract_preprocessor(fit)
```

### Common Extractions

```r
# Variable importance from ranger
library(vip)
fit |> extract_fit_parsnip() |> vip()

# Coefficients from glmnet
fit |> extract_fit_engine() |> coef(s = 0.01)

# See what the recipe did to the data
fit |> extract_recipe() |> tidy()
```

## Updating Workflows

Swap components without rebuilding from scratch:

```r
# Change the model
wf_new <- wf |>
  remove_model() |>
  add_model(
    boost_tree(trees = 500) |>
      set_engine("xgboost") |>
      set_mode("classification")
  )

# Change the recipe
wf_new <- wf |>
  remove_recipe() |>
  add_recipe(new_recipe)
```

## Workflow Without a Recipe

For models that need no preprocessing, use `add_formula()` instead of
`add_recipe()`:

```r
wf <- workflow() |>
  add_formula(outcome ~ feature1 + feature2) |>
  add_model(spec)
```

This is simpler but does not support step functions. Use it only when raw data
is already suitable for the model.

## Workflow with add_variables()

For even more control, specify predictor and outcome roles directly:

```r
wf <- workflow() |>
  add_variables(outcomes = outcome, predictors = c(x1, x2, x3)) |>
  add_model(spec)
```

## Workflows in Cross-Validation

Workflows integrate seamlessly with `tune_grid()` and `fit_resamples()`:

```r
folds <- vfold_cv(train_data, v = 10)

# fit_resamples: evaluate a fixed workflow across resamples
results <- fit_resamples(wf, resamples = folds)
collect_metrics(results)

# tune_grid: tune a workflow with tune() placeholders
# (see tuning.md for details)
```

## Quick Reference

| Task | Code |
|------|------|
| Create workflow | `workflow()` |
| Add recipe | `wf \|> add_recipe(rec)` |
| Add model | `wf \|> add_model(spec)` |
| Add formula (no recipe) | `wf \|> add_formula(y ~ x)` |
| Fit | `wf \|> fit(data = train_data)` |
| Predict (class) | `fit \|> predict(new_data = test)` |
| Predict (prob) | `fit \|> predict(new_data = test, type = "prob")` |
| Augment | `fit \|> augment(new_data = test)` |
| Extract parsnip fit | `extract_fit_parsnip(fit)` |
| Extract engine fit | `extract_fit_engine(fit)` |
| Extract recipe | `extract_recipe(fit)` |
| Swap model | `wf \|> remove_model() \|> add_model(new_spec)` |
| Swap recipe | `wf \|> remove_recipe() \|> add_recipe(new_rec)` |
