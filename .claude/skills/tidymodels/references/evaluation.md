# Evaluation

Yardstick metrics for evaluating model performance: regression metrics (RMSE, MAE,
R-squared), classification metrics (accuracy, ROC-AUC, precision, recall, F1,
confusion matrix), metric sets, and integration with tuning results.

## Evaluation Pattern

In tidymodels, evaluation uses `augment()` to get predictions joined to truth,
then yardstick metric functions:

```r
library(tidymodels)

# Get predictions with truth
results <- fit |> augment(new_data = test_data)

# Compute metrics
rmse(results, truth = outcome, estimate = .pred)
accuracy(results, truth = outcome, estimate = .pred_class)
```

## Regression Metrics

```r
# --- RMSE (root mean squared error) ---
rmse(results, truth = y, estimate = .pred)

# --- MAE (mean absolute error) ---
mae(results, truth = y, estimate = .pred)

# --- R-squared ---
rsq(results, truth = y, estimate = .pred)

# --- MAPE (mean absolute percentage error) ---
mape(results, truth = y, estimate = .pred)

# --- Huber loss (robust to outliers) ---
huber_loss(results, truth = y, estimate = .pred)
```

| Metric | Range | Interpretation |
|--------|-------|---------------|
| `rmse` | [0, Inf) | Same units as target. Lower = better. |
| `mae` | [0, Inf) | Same units as target. Robust to outliers. Lower = better. |
| `rsq` | [0, 1] | Fraction of variance explained. Higher = better. |
| `mape` | [0, Inf) | Percentage error. Lower = better. |

## Classification Metrics

### Accuracy

```r
accuracy(results, truth = outcome, estimate = .pred_class)
```

Only meaningful when classes are balanced. For imbalanced data, use precision/
recall/F1 or ROC-AUC.

### ROC AUC

Requires probability predictions (`.pred_{level}` columns from `augment()`):

```r
# Binary classification
roc_auc(results, truth = outcome, .pred_positive_class)

# Multi-class
roc_auc(results, truth = outcome, .pred_class1, .pred_class2, .pred_class3)
# Or use the tidyselect helper:
roc_auc(results, truth = outcome, starts_with(".pred_"), -c(.pred_class))
```

### ROC Curve

```r
# Get ROC curve data for plotting
roc_data <- roc_curve(results, truth = outcome, .pred_positive_class)

# Plot
autoplot(roc_data)
```

### Precision, Recall, F1

```r
# Precision (positive predictive value)
precision(results, truth = outcome, estimate = .pred_class)

# Recall (sensitivity)
recall(results, truth = outcome, estimate = .pred_class)

# F1 (harmonic mean of precision and recall)
f_meas(results, truth = outcome, estimate = .pred_class)
```

For multi-class, specify the estimator:

```r
# Macro average (unweighted mean across classes)
f_meas(results, truth = outcome, estimate = .pred_class, estimator = "macro")

# Weighted average (weighted by class support)
f_meas(results, truth = outcome, estimate = .pred_class, estimator = "macro_weighted")
```

### Confusion Matrix

```r
# Confusion matrix
cm <- conf_mat(results, truth = outcome, estimate = .pred_class)
cm

# Visual display
autoplot(cm, type = "heatmap")

# Summary statistics from confusion matrix
summary(cm)
# Returns: accuracy, kappa, sensitivity, specificity, ppv, npv, etc.
```

### Sensitivity and Specificity

```r
sensitivity(results, truth = outcome, estimate = .pred_class)
specificity(results, truth = outcome, estimate = .pred_class)
```

## metric_set(): Multiple Metrics at Once

Bundle multiple metrics into a single function call:

```r
# --- Regression metric set ---
reg_metrics <- metric_set(rmse, mae, rsq)
reg_metrics(results, truth = y, estimate = .pred)
# Returns a tibble with .metric, .estimator, .estimate columns

# --- Classification metric set ---
class_metrics <- metric_set(accuracy, f_meas, precision, recall)
class_metrics(results, truth = outcome, estimate = .pred_class)
```

## Metrics with Tuning Results

When using `tune_grid()` or `fit_resamples()`, metrics are collected
automatically:

```r
# Default metrics
tune_results <- tune_grid(wf, resamples = folds, grid = 20)
collect_metrics(tune_results)

# Custom metrics
my_metrics <- metric_set(accuracy, roc_auc, f_meas)
tune_results <- tune_grid(wf, resamples = folds, grid = 20, metrics = my_metrics)
collect_metrics(tune_results)
```

Default metrics by mode:

| Mode | Default Metrics |
|------|----------------|
| regression | rmse, rsq |
| classification | accuracy, roc_auc (if probabilities available) |

## Comparing Models

To compare multiple models, collect predictions from each and compute metrics:

```r
# Fit multiple workflows
fit_rf <- wf_rf |> fit(data = train_data)
fit_glm <- wf_glm |> fit(data = train_data)
fit_xgb <- wf_xgb |> fit(data = train_data)

# Augment test data with each
results_rf <- fit_rf |> augment(new_data = test_data) |> mutate(model = "RF")
results_glm <- fit_glm |> augment(new_data = test_data) |> mutate(model = "GLM")
results_xgb <- fit_xgb |> augment(new_data = test_data) |> mutate(model = "XGBoost")

# Combine and compute metrics by model
all_results <- bind_rows(results_rf, results_glm, results_xgb)
all_results |>
  group_by(model) |>
  accuracy(truth = outcome, estimate = .pred_class)
```

## Event Level

For binary classification, yardstick needs to know which class is the "event"
(positive class). By default, yardstick treats the **first level** of the factor
as the event.

```r
# Check factor levels
levels(results$outcome)
# [1] "no"  "yes"  -- "no" is the event by default

# Specify event level explicitly
sensitivity(results, truth = outcome, estimate = .pred_class, event_level = "second")
roc_auc(results, truth = outcome, .pred_yes, event_level = "second")
```

## Quick Reference

| Task | Code |
|------|------|
| RMSE | `rmse(results, truth = y, estimate = .pred)` |
| MAE | `mae(results, truth = y, estimate = .pred)` |
| R-squared | `rsq(results, truth = y, estimate = .pred)` |
| Accuracy | `accuracy(results, truth = y, estimate = .pred_class)` |
| ROC AUC | `roc_auc(results, truth = y, .pred_positive)` |
| Precision | `precision(results, truth = y, estimate = .pred_class)` |
| Recall | `recall(results, truth = y, estimate = .pred_class)` |
| F1 | `f_meas(results, truth = y, estimate = .pred_class)` |
| Confusion matrix | `conf_mat(results, truth = y, estimate = .pred_class)` |
| Metric set | `metric_set(rmse, mae, rsq)` |
| ROC curve | `roc_curve(results, truth = y, .pred_positive) \|> autoplot()` |
| Event level | `metric(..., event_level = "second")` |
