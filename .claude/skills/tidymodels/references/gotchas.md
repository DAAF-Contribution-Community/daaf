# Gotchas and Common Mistakes

Common pitfalls with tidymodels, organized as Problem / Why / Fix.

## Contents

- [Forgetting to Set Mode](#forgetting-to-set-mode)
- [Recipe Step Order Matters](#recipe-step-order-matters)
- [Data Leakage via Manual prep/bake](#data-leakage-via-manual-prepbake)
- [Prediction Column Names](#prediction-column-names)
- [glmnet Without Setting penalty](#glmnet-without-setting-penalty)
- [Engine-Specific Args in Wrong Place](#engine-specific-args-in-wrong-place)
- [Factor Level Ordering and event_level](#factor-level-ordering-and-event_level)
- [Forgetting set.seed Before Resampling](#forgetting-setseed-before-resampling)
- [Using tidymodels for Causal Inference](#using-tidymodels-for-causal-inference)
- [tidymodels vs caret Migration](#tidymodels-vs-caret-migration)

## Forgetting to Set Mode

**Problem:** Error message like "Please set the mode for the model" or the model
fits for the wrong task (regression when you wanted classification).

**Why:** parsnip model types can support both regression and classification. The
mode must be set explicitly. Some models (like `logistic_reg`) default to
classification, but others (like `rand_forest`) do not default.

**Fix:** Always call `set_mode()` explicitly.

```r
# --- Wrong (mode not set) ---
spec <- rand_forest(trees = 500) |>
  set_engine("ranger")
# Error: parsnip model object but it isn't any mode

# --- Right ---
spec <- rand_forest(trees = 500) |>
  set_engine("ranger") |>
  set_mode("classification")
```

## Recipe Step Order Matters

**Problem:** Unexpected preprocessing results or errors from steps applied in
the wrong order.

**Why:** Recipe steps execute in the order they are added. Some steps depend on
the output of previous steps. Encoding before imputation fails because NAs in
factors cause issues; normalizing before encoding means dummy columns (0/1) get
normalized alongside continuous features.

**Fix:** Follow the recommended ordering:

1. Imputation (fill NA first)
2. Feature engineering (interactions, transforms)
3. Encoding (step_dummy)
4. Normalization (step_normalize)
5. Filtering (step_zv, step_corr)

```r
# --- Wrong (normalize before dummy) ---
rec <- recipe(y ~ ., data = df) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())
# Problem: dummy columns are 0/1, don't need normalizing.
# But they also won't match because they didn't exist when normalize was defined.

# --- Right ---
rec <- recipe(y ~ ., data = df) |>
  step_impute_median(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors()) |>
  step_normalize(all_numeric_predictors())
```

## Data Leakage via Manual prep/bake

**Problem:** Metrics on test data are suspiciously good; model performs worse on
new data than on test set.

**Why:** If you prep a recipe on the full dataset before splitting (or prep on
test data), the preprocessing learns statistics (means, PCA loadings, etc.) from
data the model should not have seen.

**Fix:** Use workflows. Workflows handle prep/bake automatically, ensuring the
recipe is fit on training data only. If you must use prep/bake manually, prep
only on training data:

```r
# --- Wrong (leakage) ---
prepped <- prep(rec, training = full_data)  # Leaks test data statistics
baked <- bake(prepped, new_data = NULL)
# Then split...

# --- Right (workflow handles this) ---
wf <- workflow() |> add_recipe(rec) |> add_model(spec)
fit <- wf |> fit(data = train_data)  # Recipe prepped on train_data only

# --- Right (manual, if needed) ---
prepped <- prep(rec, training = train_data)
train_baked <- bake(prepped, new_data = NULL)
test_baked <- bake(prepped, new_data = test_data)  # Uses train stats
```

## Prediction Column Names

**Problem:** `Error in metric(results, truth = y, estimate = .pred)` or wrong
column referenced.

**Why:** tidymodels uses different prediction column names depending on the mode:

| Mode | `predict()` Column | `augment()` Columns |
|------|-------------------|-------------------|
| regression | `.pred` | `.pred` |
| classification | `.pred_class` | `.pred_class`, `.pred_{level1}`, `.pred_{level2}`, ... |

**Fix:** Use the correct column name for the task:

```r
# Regression
rmse(results, truth = y, estimate = .pred)

# Classification (hard predictions)
accuracy(results, truth = y, estimate = .pred_class)

# Classification (probabilities)
roc_auc(results, truth = y, .pred_positive_class)
```

## glmnet Without Setting penalty

**Problem:** Unexpected results from glmnet models; predictions use a different
penalty than expected.

**Why:** glmnet fits a full regularization path internally. If you do not set
`penalty`, parsnip may select a default lambda value that does not match your
intent. The default behavior can change between versions.

**Fix:** Always set `penalty` explicitly or use `tune()`:

```r
# --- Wrong (ambiguous penalty) ---
spec <- linear_reg(mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")

# --- Right (explicit) ---
spec <- linear_reg(penalty = 0.01, mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")

# --- Right (tune) ---
spec <- linear_reg(penalty = tune(), mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")
```

## Engine-Specific Args in Wrong Place

**Problem:** Engine-specific arguments silently ignored or cause errors.

**Why:** parsnip model functions (like `rand_forest()`) accept only a defined set
of standardized parameters. Engine-specific arguments go inside `set_engine()`,
not in the model function.

**Fix:** Put engine-specific args in `set_engine()`:

```r
# --- Wrong (importance is not a parsnip arg) ---
spec <- rand_forest(trees = 500, importance = "impurity") |>
  set_engine("ranger") |>
  set_mode("classification")

# --- Right (engine arg in set_engine) ---
spec <- rand_forest(trees = 500) |>
  set_engine("ranger", importance = "impurity") |>
  set_mode("classification")
```

## Factor Level Ordering and event_level

**Problem:** Binary classification metrics (sensitivity, specificity, ROC-AUC)
give unexpectedly low values.

**Why:** yardstick treats the **first level** of the factor outcome as the
"event" (positive class). If your factor has levels `c("no", "yes")`, then "no"
is the event -- the opposite of what most analyses intend.

**Fix:** Either relevel the factor or use `event_level = "second"`:

```r
# --- Option 1: Relevel the factor ---
data$outcome <- relevel(data$outcome, ref = "no")
# Now levels are c("no", "yes") but "no" is still first
# Better: make the positive class first
data$outcome <- factor(data$outcome, levels = c("yes", "no"))

# --- Option 2: Specify event_level ---
sensitivity(results, truth = outcome, estimate = .pred_class, event_level = "second")
roc_auc(results, truth = outcome, .pred_yes, event_level = "second")
```

## Forgetting set.seed Before Resampling

**Problem:** Different results each time you run the same code.

**Why:** `initial_split()`, `vfold_cv()`, `bootstraps()`, and `tune_grid()` all
use random number generation. Without `set.seed()`, results vary between runs.

**Fix:** Set the seed before each random operation:

```r
set.seed(42)
split <- initial_split(data, prop = 0.8)

set.seed(42)
folds <- vfold_cv(train_data, v = 10)

set.seed(42)
tune_results <- tune_grid(wf, resamples = folds, grid = 20)
```

## Using tidymodels for Causal Inference

**Problem:** Using tidymodels to estimate treatment effects, then interpreting
coefficients causally.

**Why:** tidymodels is designed for **prediction** (minimize expected loss on
future data), not **inference** (estimate causal parameters with valid standard
errors). tidymodels models:
- Do not report standard errors or p-values
- Use regularization that biases coefficients
- Optimize for predictive accuracy, not unbiased estimation

**Fix:** For causal inference, use fixest (FE, IV, DiD) or r-stats (OLS/GLM with
robust SEs). Use tidymodels only when the goal is prediction or classification.

## tidymodels vs caret Migration

For users coming from the caret package:

| caret | tidymodels Equivalent |
|-------|----------------------|
| `train()` | `workflow() \|> fit()` |
| `trainControl()` | `vfold_cv()` + `tune_grid()` |
| `preProcess` | `recipe()` with step functions |
| `method = "rf"` | `rand_forest() \|> set_engine("ranger")` |
| `tuneGrid` | `grid_regular()` or `grid_space_filling()` |
| `confusionMatrix()` | `conf_mat()` + `summary()` |
| `predict(model, newdata)` | `predict(fit, new_data)` or `augment(fit, new_data)` |
| `varImp()` | `vip::vip()` on extracted parsnip fit (ranger: requires `importance =` in `set_engine()`) |

Key differences:
- caret uses `newdata`; tidymodels uses `new_data` (with underscore)
- caret combines preprocessing and tuning in `train()`; tidymodels separates
  recipe, model spec, and workflow
- caret returns caret-specific objects; tidymodels returns tibbles
- tidymodels is actively developed; caret is in maintenance mode

## Quick Fix Table

| Problem | Quick Fix |
|---------|-----------|
| "set the mode" error | Add `set_mode("classification")` or `set_mode("regression")` |
| Unexpected preprocessing | Check step ordering: impute, engineer, encode, normalize, filter |
| Data leakage | Use workflows (automatic) or prep on training data only |
| Wrong prediction column | Regression: `.pred`. Classification: `.pred_class` |
| glmnet behaves oddly | Set `penalty` explicitly or use `tune()` |
| Engine arg ignored | Put engine args in `set_engine()`, not model function |
| Metrics seem inverted | Check `event_level`; first factor level is the default event |
| Different results each run | Add `set.seed()` before random operations |
| Need p-values/SEs | Use fixest or r-stats instead -- tidymodels is for prediction |
| Migrating from caret | `new_data` (not `newdata`); separate recipe from model |
