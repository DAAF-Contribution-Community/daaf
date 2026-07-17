# Model Interpretation

Permutation importance, partial dependence (PDP), individual conditional expectation (ICE), SHAP values, and native engine importance for tidymodels fits. For methodology guidance (when interpretation is appropriate, causation caveats, reporting standards), see `supervised-ml.md` in the `data-scientist` skill. Python equivalent: `interpretation.md` in the `scikit-learn` skill.

## The R Interpretation Stack (Installed Packages)

R has no single equivalent of Python's `shap` package. Interpretation is spread across several packages, all model-agnostic and connectable to tidymodels workflows:

| Package | Version | Role |
|---------|---------|------|
| DALEX | 2.5.3 | Explainer framework: permutation importance, PDP/ICE, break-down, SHAP |
| iml | 0.11.4 | Alternative framework: FeatureImp, FeatureEffect, Shapley |
| kernelshap | 0.9.1 | Efficient Kernel SHAP for many observations |
| vip | 0.4.5 | Quick variable-importance plots from engine-native importance |

**NOT installed:** `DALEXtra` (the tidymodels-specific DALEX adapter) and `shapviz` (SHAP plotting). Both are worked around below: DALEX connects to workflows directly via `predict_function`, and kernelshap/DALEX results plot with their own `plot()` methods or ggplot2.

**Key difference from Python:** there is no installed equivalent of `shap.TreeExplainer` (fast exact tree SHAP). `kernelshap` is a sampling approximation — accurate but slower. For SHAP on large data, subset the rows you explain.

## Connecting Explainers to a Workflow Fit

All three frameworks need a function that maps `(model, newdata)` to a numeric vector. For tidymodels workflows:

```r
# Regression: predict() returns a tibble with .pred
pred_fun <- function(m, newdata) predict(m, new_data = newdata)$.pred

# Classification: use the probability of the event class
pred_fun <- function(m, newdata) predict(m, new_data = newdata, type = "prob")$.pred_yes
```

Pass the **raw predictor data** (recipe-untransformed) to the explainer — the workflow applies its recipe inside `predict()`, so explanations are expressed in the original feature space.

## DALEX

### Building an Explainer

```r
library(tidymodels)
library(DALEX)   # masks dplyr::explain — call DALEX::explain() explicitly

# fit is a fitted workflow(); test_data holds raw predictors + outcome y
explainer <- DALEX::explain(
  model = fit,
  data = dplyr::select(test_data, -y),   # predictors only
  y = test_data$y,
  predict_function = function(m, newdata) predict(m, new_data = newdata)$.pred,
  label = "rf_workflow",
  verbose = FALSE
)
```

For classification, additionally set `type = "classification"` and pass `y` as numeric 0/1 — DALEX cannot infer the task type from a workflow object and defaults to regression (this matters downstream: `fairmodels::fairness_check()` rejects regression-typed explainers).

### Permutation Importance: model_parts()

```r
# INTENT: model-agnostic importance — how much does loss increase when a feature is shuffled?
vi <- model_parts(explainer, loss_function = loss_root_mean_square, B = 5)
print(head(as.data.frame(vi)))
# columns: variable, permutation, dropout_loss, label
# rows _full_model_ and _baseline_ bracket the feature rows

p <- plot(vi)   # ggplot object
ggsave(file.path(FIGURES_DIR, "permutation_importance.png"), p, width = 8, height = 5, dpi = 150)
```

### PDP and ICE: model_profile()

```r
# PDP: average prediction as one feature varies
pdp <- model_profile(explainer, variables = "x1", N = 100)
# aggregated profiles: pdp$agr_profiles; per-observation (ICE) curves: pdp$cp_profiles

p <- plot(pdp)
ggsave(file.path(FIGURES_DIR, "pdp_x1.png"), p, width = 8, height = 5, dpi = 150)
```

`N` controls how many observations the profiles are computed from — the ICE curves in `$cp_profiles` are one per sampled observation per grid point.

### Single-Prediction Explanations: predict_parts()

```r
# Break-down: sequential attribution for one observation
bd <- predict_parts(explainer, new_observation = test_data[1, ], type = "break_down")

# SHAP (sampling-based Shapley values)
shap_one <- predict_parts(explainer, new_observation = test_data[1, ], type = "shap", B = 5)
```

## iml

iml wraps the model in a `Predictor` R6 object; interpretation methods are R6 classes.

```r
library(iml)

predictor <- Predictor$new(
  model = fit,
  data = as.data.frame(dplyr::select(test_data, -y)),   # iml expects a data.frame
  y = test_data$y,
  predict.function = function(model, newdata) predict(model, new_data = newdata)$.pred
)

# --- Permutation importance (with quantiles across repetitions) ---
imp <- FeatureImp$new(predictor, loss = "rmse", n.repetitions = 5)
print(imp$results)   # feature, importance.05, importance, importance.95
# importance is a RATIO: loss after shuffling / original loss (1 = no importance)

# --- PDP + ICE in one plot ---
eff <- FeatureEffect$new(predictor, feature = "x1", method = "pdp+ice")
print(head(eff$results))

# --- Shapley values for a single observation ---
shap_iml <- Shapley$new(predictor,
  x.interest = as.data.frame(test_data[1, setdiff(names(test_data), "y")]))
print(shap_iml$results)   # feature, phi, phi.var, feature.value
```

**DALEX or iml?** They overlap heavily. DALEX has the more consistent output/plot system and connects to `fairmodels`; iml reports uncertainty bands on importance (`importance.05`/`.95`). Pick one per project for consistency — DALEX is the DAAF default.

## kernelshap: SHAP for Many Observations

`Shapley$new()` (iml) and `predict_parts(type = "shap")` (DALEX) explain one observation at a time. For a SHAP matrix over many rows, use kernelshap:

```r
library(kernelshap)

# INTENT: SHAP matrix for 20 test rows against a background sample
# REASONING: background (bg_X) anchors the "average prediction"; 50-200 rows is typical
X_explain <- as.data.frame(test_data[1:20, setdiff(names(test_data), "y")])
bg <- as.data.frame(train_data[1:60, setdiff(names(train_data), "y")])

ks <- kernelshap(
  object = fit,
  X = X_explain,
  bg_X = bg,
  pred_fun = function(object, X, ...) predict(object, new_data = X)$.pred,
  verbose = FALSE
)

# ks$S is the SHAP matrix (n_rows x n_features); global importance:
sort(colMeans(abs(ks$S)), decreasing = TRUE)
```

Note the kernelshap `pred_fun` signature is `function(object, X, ...)` — different argument names than DALEX/iml. `shapviz` (the companion plotting package) is not installed; plot from `ks$S` directly with ggplot2 if needed.

## Native Engine Importance

Fastest option when a tree engine is already fitted — but ranger requires opting in at fit time:

```r
# ranger: importance must be requested in set_engine(), or none is computed
spec <- rand_forest(trees = 500) |>
  set_engine("ranger", importance = "impurity") |>   # or "permutation"
  set_mode("classification")
fit <- workflow() |> add_recipe(rec) |> add_model(spec) |> fit(data = train_data)

extract_fit_engine(fit)$variable.importance   # named numeric vector

# xgboost: importance is always available from the booster
xgboost::xgb.importance(model = extract_fit_engine(bt_fit))  # Gain, Cover, Frequency
```

### vip: Quick Importance Plots

```r
library(vip)
vi(extract_fit_parsnip(fit))    # tibble: Variable, Importance
p <- vip(extract_fit_parsnip(fit))  # ggplot bar chart
ggsave(file.path(FIGURES_DIR, "vip.png"), p, width = 6, height = 4, dpi = 150)
```

**Gotcha (verified):** for ranger fits, `vip::vi()` errors with "No variable importance found. Please use 'importance' option when growing the forest." unless `importance =` was set in `set_engine()`. Always set it when you plan to inspect importance.

## Interpreting Results: Mandatory Caveats

These apply to ALL methods above (full treatment: `supervised-ml.md` in `data-scientist`):

1. **Explanations describe the MODEL, not reality.** A model trained on biased data produces explanations that reflect the bias.
2. **Feature importance is NOT causal importance.** Predictive weight does not mean intervening on the feature changes outcomes. For causal questions use `fixest` / `r-stats`.
3. **Correlated features split importance unstably** — SHAP and permutation importance distribute credit among correlated features in sample-dependent ways.
4. **Rankings are model-dependent.** Report the model alongside importance claims.
5. **PDP assumes feature independence.** With correlated features, PDP averages over unrealistic combinations; ICE curves partially reveal this.
6. **iml importance is a ratio, DALEX importance is a loss level.** Do not compare numbers across frameworks — compare rankings.

## Quick Reference

| Task | Code |
|------|------|
| DALEX explainer (regression) | `DALEX::explain(fit, data = X, y = y, predict_function = \(m, d) predict(m, new_data = d)$.pred)` |
| DALEX explainer (classification) | add `type = "classification"`, prob predict_function, numeric 0/1 y |
| Permutation importance | `model_parts(explainer, B = 5)` |
| PDP / ICE | `model_profile(explainer, variables = "x1", N = 100)` |
| Break-down (one obs) | `predict_parts(explainer, new_observation = row, type = "break_down")` |
| SHAP (one obs) | `predict_parts(explainer, new_observation = row, type = "shap", B = 5)` |
| SHAP (many obs) | `kernelshap(fit, X = X_explain, bg_X = bg, pred_fun = ...)` |
| iml importance | `FeatureImp$new(predictor, loss = "rmse", n.repetitions = 5)` |
| iml PDP+ICE | `FeatureEffect$new(predictor, feature = "x1", method = "pdp+ice")` |
| ranger native importance | `set_engine("ranger", importance = "impurity")` then `extract_fit_engine(fit)$variable.importance` |
| xgboost native importance | `xgboost::xgb.importance(model = extract_fit_engine(fit))` |
| Quick importance plot | `vip::vip(extract_fit_parsnip(fit))` |
