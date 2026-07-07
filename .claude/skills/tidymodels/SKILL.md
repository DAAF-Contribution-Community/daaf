---
name: tidymodels
description: |
  R machine learning with tidymodels: recipes (preprocessing), parsnip
  (model specs), workflows (fit pipelines), tune (hyperparameters), rsample
  (resampling). Engines: ranger (RF), glmnet (lasso/ridge), xgboost. UMAP
  via uwot. Use when execution language is R. Python equivalent: scikit-learn.
  For econometric regression use fixest or r-stats.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "tidymodels 1.4.1"
  skill-last-updated: "2026-05-08"
  tags: ["r", "machine-learning", "tidymodels", "classification", "prediction"]
---

# tidymodels Skill

R machine learning with the tidymodels ecosystem. Covers recipes for preprocessing
(normalization, dummy encoding, imputation, interactions), parsnip for model
specifications (linear_reg, logistic_reg, rand_forest, boost_tree,
nearest_neighbor), workflows for combining recipe + model into a single fit/predict
pipeline, tune for hyperparameter optimization via grid search and cross-validation,
rsample for resampling (v-fold CV, bootstrap, LOO), and yardstick for evaluation
metrics (rmse, accuracy, roc_auc, confusion matrix). Engines: ranger (random
forest), glmnet (lasso/ridge/elasticnet), xgboost (gradient boosting), kknn
(k-nearest neighbors). UMAP via uwot (not part of tidymodels). Use when execution
language is R and the task involves classification, prediction, clustering via
recipes, or preprocessing for ML. Python equivalent: scikit-learn. For econometric
regression (OLS, FE, IV, DiD) use fixest or r-stats.

Comprehensive skill for machine learning in R with tidymodels. Covers supervised
methods (classification, regression), preprocessing (recipes), hyperparameter
tuning, resampling, evaluation, and unsupervised dimension reduction. Use decision
trees below to find the right guidance, then load detailed references.

## What is tidymodels?

tidymodels (Kuhn & Wickham) is R's unified machine learning framework, designed
as the successor to caret:

- **Recipe/workflow paradigm**: Preprocessing (recipe) and model (parsnip spec)
  are separate objects combined into a workflow -- different from scikit-learn's
  Pipeline where steps are positional
- **Engine abstraction**: `set_engine()` decouples model type from implementation
  (e.g., `rand_forest() |> set_engine("ranger")` vs `set_engine("randomForest")`)
- **Tidy evaluation**: Results come back as tibbles, not custom S3/S4 objects
- **Consistent interface**: Every model uses `fit()`, `predict()`, `augment()` --
  same verbs regardless of engine
- **Resampling first**: Cross-validation and bootstrap are built into the tuning
  workflow, not bolted on

## Version Notes

This skill targets **tidymodels 1.4.1** (R 4.5.3). Key package versions:

| Package | Version | Role |
|---------|---------|------|
| recipes | 1.3.2 | Preprocessing step definitions |
| parsnip | 1.5.0 | Model specifications + engine bindings |
| workflows | 1.3.0 | Recipe + model bundling |
| tune | 2.0.1 | Hyperparameter tuning infrastructure |
| rsample | 1.3.2 | Resampling (CV, bootstrap, etc.) |
| yardstick | 1.4.0 | Evaluation metrics |
| dials | 1.4.3 | Parameter ranges for tuning |
| ranger | 0.18.0 | Random forest engine |
| glmnet | 4.1.10 | Regularized regression engine |
| xgboost | 3.2.1.1 | Gradient boosting engine |
| uwot | 0.2.4 | UMAP (not tidymodels, standalone) |

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Full tidymodels workflow: recipe, model spec, workflow, fit, predict | First use of tidymodels |
| `recipes.md` | step_normalize, step_dummy, step_impute_*, step_interact, roles | Preprocessing tasks |
| `models.md` | parsnip model specs: linear_reg, logistic_reg, rand_forest, boost_tree, nearest_neighbor | Choosing and configuring models |
| `workflows.md` | workflow() + add_recipe + add_model, fit(), predict(), augment() | Building ML pipelines |
| `tuning.md` | tune(), tune_grid(), collect_metrics(), select_best(), finalize_workflow | Hyperparameter optimization |
| `resampling.md` | vfold_cv, bootstraps, loo_cv, group_vfold_cv, strata, assessment/analysis | Creating resamples |
| `engines.md` | ranger, glmnet, xgboost, kknn: engine-specific args, installation, tuning params | Engine configuration |
| `unsupervised.md` | PCA via recipes::step_pca, UMAP via uwot::umap(), k-means via stats::kmeans | Dimension reduction, clustering |
| `evaluation.md` | yardstick metrics: rmse, accuracy, roc_auc, conf_mat, metric_set() | Evaluating model performance |
| `gotchas.md` | Recipe baking order, data leakage, parsnip mode, engine args, tidymodels vs caret | Debugging common mistakes |

### Reading Order

1. **New to tidymodels?** Start with `quickstart.md` then `workflows.md`
2. **Need preprocessing?** Read `recipes.md`
3. **Choosing a model?** Read `models.md` then `engines.md`
4. **Need tuning?** Read `tuning.md` then `resampling.md`
5. **Evaluating results?** Read `evaluation.md`
6. **Unsupervised task?** Read `unsupervised.md`
7. **Coming from scikit-learn?** Read `quickstart.md` then `gotchas.md`
8. **Having issues?** Check `gotchas.md` first

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `scikit-learn` | Python equivalent -- Pipeline/estimator pattern vs tidymodels recipe/workflow pattern. Load when execution language is Python. |
| `data-scientist` | Methodology guidance -- load for "when and why" behind methods |
| `r-python-translation` | Cross-language mappings for R tidymodels vs Python scikit-learn |
| `fixest` | Econometric regression with FE/IV/DiD in R. Use instead of tidymodels for causal inference. |
| `r-stats` | Base R stats for OLS/GLM without FE. Use instead of tidymodels for simple regression without regularization or tuning. |
| `ggplot2` | Visualization of model results. tidymodels objects are tidy -- pipe directly to ggplot2. |

**Routing guidance:**
- For econometric regression (hypothesis testing, standard errors, coefficient
  interpretation), use `fixest` or `r-stats` -- not tidymodels
- For unsupervised methodology (when to cluster, how to validate), read
  `exploratory-unsupervised.md` in the `data-scientist` skill
- For simple OLS/GLM without tuning or regularization, use `r-stats`
- For data manipulation, use `tidyverse`

## Quick Decision Trees

### "I need to build a predictive model"

```
What kind of prediction?
+-- Continuous outcome (regression)
|   +-- Simple linear --> linear_reg() (./references/models.md)
|   +-- Regularized (lasso/ridge) --> linear_reg(penalty, mixture) with glmnet
|   |   (./references/models.md + ./references/engines.md)
|   +-- Tree-based --> rand_forest() or boost_tree()
|   |   (./references/models.md)
|   +-- Need to tune hyperparameters --> ./references/tuning.md
|   +-- NOTE: For econometric regression (causal inference, SEs),
|       use fixest or r-stats instead
+-- Categorical outcome (classification)
|   +-- Binary --> logistic_reg() (./references/models.md)
|   +-- Multi-class --> logistic_reg(multi_class) or rand_forest()
|   |   (./references/models.md)
|   +-- Best performance --> boost_tree() with xgboost
|   |   (./references/models.md + ./references/engines.md)
|   +-- Need tuning --> ./references/tuning.md
```

### "I need to preprocess data"

```
What preprocessing?
+-- Normalize numeric features --> step_normalize() (./references/recipes.md)
+-- Create dummy variables --> step_dummy() (./references/recipes.md)
+-- Handle missing values --> step_impute_mean/median/knn (./references/recipes.md)
+-- Create interactions --> step_interact() (./references/recipes.md)
+-- PCA / dimension reduction --> step_pca() (./references/unsupervised.md)
+-- Mixed types (numeric + categorical) --> recipe with multiple steps
|   (./references/recipes.md)
+-- Feature engineering --> step_mutate(), step_log() (./references/recipes.md)
```

### "I need to evaluate a model"

```
What evaluation?
+-- Regression metrics
|   +-- RMSE, MAE, R-squared --> ./references/evaluation.md
+-- Classification metrics
|   +-- Accuracy, ROC-AUC, confusion matrix --> ./references/evaluation.md
|   +-- Precision, recall, F1 --> ./references/evaluation.md
+-- Cross-validated performance
|   +-- collect_metrics() from tune_grid --> ./references/tuning.md
+-- Compare multiple models
|   +-- collect_metrics() + bind_rows --> ./references/evaluation.md
```

### "I need to tune hyperparameters"

```
Tuning approach?
+-- Grid search (exhaustive) --> tune_grid() (./references/tuning.md)
+-- Which parameters to tune --> tune() placeholder + dials ranges
|   (./references/tuning.md)
+-- Select best model --> select_best() + finalize_workflow()
|   (./references/tuning.md)
+-- Resampling for tuning --> vfold_cv() (./references/resampling.md)
```

### "I need unsupervised analysis"

```
What unsupervised method?
+-- PCA (within a recipe) --> step_pca() (./references/unsupervised.md)
+-- UMAP --> uwot::umap() (./references/unsupervised.md)
+-- K-means clustering --> stats::kmeans() (./references/unsupervised.md)
+-- NOTE: tidymodels focuses on supervised learning. For advanced
    clustering, see data-scientist skill methodology guidance.
```

### "Something isn't working"

```
Common issues?
+-- "recipe must be prepped" --> ./references/gotchas.md
+-- "set mode" error --> ./references/gotchas.md
+-- Engine-specific args not working --> ./references/gotchas.md
+-- Predictions wrong type --> ./references/gotchas.md
+-- Data leakage concerns --> ./references/gotchas.md
+-- tidymodels vs caret migration --> ./references/gotchas.md
```

## File-First Execution in Research Workflows

**Important:** In DAAF research pipelines, tidymodels analyses are executed through
**script files**, not interactively. This ensures auditability and reproducibility.

**The pattern:**
1. Write ML code to `scripts/stage8_analysis/{step}_{task-name}.R`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory
file-first execution protocol covering complete code file writing, output capture,
and file versioning rules. All ML scripts must follow the Inline Audit Trail (IAT)
standard -- see `agent_reference/INLINE_AUDIT_TRAIL.md`. For ML code, document
model selection rationale (why this algorithm, why these hyperparameters, what
assumptions) with `# INTENT:`, `# REASONING:`, and `# ASSUMES:` comments.

**See:**
- `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` -- Stage 8 (Analysis & Visualization)
- `agent_reference/INLINE_AUDIT_TRAIL.md` -- IAT documentation standard

The examples below show tidymodels syntax. In research workflows, wrap them in
scripts following the file-first pattern.

---

## Quick Reference

### Essential Setup

```r
library(tidymodels)       # Loads recipes, parsnip, workflows, tune, rsample, yardstick, dials
library(arrow)            # For parquet I/O (DAAF convention)
```

### The tidymodels Workflow (5 Steps)

```r
# 1. Define recipe (preprocessing)
rec <- recipe(outcome ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())

# 2. Define model specification
spec <- rand_forest(trees = 500) |>
  set_engine("ranger") |>
  set_mode("classification")

# 3. Bundle into workflow
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)

# 4. Fit
fit <- wf |> fit(data = train_data)

# 5. Predict
preds <- fit |> predict(new_data = test_data)
```

### Common Operations

| Operation | Code |
|-----------|------|
| Create recipe | `recipe(y ~ ., data = df)` |
| Normalize numeric | `step_normalize(all_numeric_predictors())` |
| Dummy encode | `step_dummy(all_nominal_predictors())` |
| Impute missing | `step_impute_median(all_numeric_predictors())` |
| Random forest | `rand_forest(trees = 500) \|> set_engine("ranger")` |
| Logistic regression | `logistic_reg() \|> set_engine("glm")` |
| Lasso | `linear_reg(penalty = 0.01, mixture = 1) \|> set_engine("glmnet")` |
| Ridge | `linear_reg(penalty = 0.01, mixture = 0) \|> set_engine("glmnet")` |
| XGBoost | `boost_tree(trees = 500) \|> set_engine("xgboost")` |
| Build workflow | `workflow() \|> add_recipe(rec) \|> add_model(spec)` |
| Fit workflow | `wf \|> fit(data = train_data)` |
| Predict | `fit \|> predict(new_data = test_data)` |
| Augment | `fit \|> augment(new_data = test_data)` |
| V-fold CV | `vfold_cv(train_data, v = 10, strata = outcome)` |
| Tune grid | `tune_grid(wf, resamples = folds, grid = 20)` |
| Best params | `select_best(tune_results, metric = "rmse")` |
| Finalize | `finalize_workflow(wf, best_params)` |
| RMSE | `rmse(results, truth = y, estimate = .pred)` |
| Accuracy | `accuracy(results, truth = y, estimate = .pred_class)` |
| ROC AUC | `roc_auc(results, truth = y, .pred_class1)` |
| Confusion matrix | `conf_mat(results, truth = y, estimate = .pred_class)` |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| First tidymodels workflow | `./references/quickstart.md` |
| recipe + spec + workflow pattern | `./references/quickstart.md` |
| fit() and predict() | `./references/quickstart.md` |
| train/test split | `./references/quickstart.md` |
| step_normalize | `./references/recipes.md` |
| step_dummy | `./references/recipes.md` |
| step_impute_mean / median / knn | `./references/recipes.md` |
| step_interact | `./references/recipes.md` |
| step_mutate / step_log | `./references/recipes.md` |
| Role assignment (update_role) | `./references/recipes.md` |
| prep() and bake() | `./references/recipes.md` |
| Selector functions | `./references/recipes.md` |
| linear_reg | `./references/models.md` |
| logistic_reg | `./references/models.md` |
| rand_forest | `./references/models.md` |
| boost_tree | `./references/models.md` |
| nearest_neighbor | `./references/models.md` |
| set_engine() | `./references/models.md` |
| set_mode() | `./references/models.md` |
| workflow() construction | `./references/workflows.md` |
| add_recipe / add_model | `./references/workflows.md` |
| fit() on workflow | `./references/workflows.md` |
| predict() on workflow | `./references/workflows.md` |
| augment() | `./references/workflows.md` |
| extract_fit_parsnip | `./references/workflows.md` |
| tune() placeholder | `./references/tuning.md` |
| tune_grid() | `./references/tuning.md` |
| collect_metrics() | `./references/tuning.md` |
| select_best() | `./references/tuning.md` |
| finalize_workflow() | `./references/tuning.md` |
| show_best() | `./references/tuning.md` |
| dials parameter ranges | `./references/tuning.md` |
| vfold_cv | `./references/resampling.md` |
| bootstraps | `./references/resampling.md` |
| loo_cv | `./references/resampling.md` |
| group_vfold_cv | `./references/resampling.md` |
| strata argument | `./references/resampling.md` |
| analysis() / assessment() | `./references/resampling.md` |
| initial_split / training / testing | `./references/resampling.md` |
| ranger (random forest) | `./references/engines.md` |
| glmnet (lasso / ridge / elasticnet) | `./references/engines.md` |
| xgboost (gradient boosting) | `./references/engines.md` |
| kknn (k-nearest neighbors) | `./references/engines.md` |
| Engine-specific arguments | `./references/engines.md` |
| PCA via step_pca | `./references/unsupervised.md` |
| UMAP via uwot | `./references/unsupervised.md` |
| K-means via stats::kmeans | `./references/unsupervised.md` |
| rmse, mae, rsq | `./references/evaluation.md` |
| accuracy, precision, recall, f_meas | `./references/evaluation.md` |
| roc_auc, roc_curve | `./references/evaluation.md` |
| conf_mat | `./references/evaluation.md` |
| metric_set() | `./references/evaluation.md` |
| Recipe baking order | `./references/gotchas.md` |
| Data leakage in recipes | `./references/gotchas.md` |
| parsnip mode requirement | `./references/gotchas.md` |
| Engine-specific args (set_engine) | `./references/gotchas.md` |
| tidymodels vs caret | `./references/gotchas.md` |
| Prediction type (.pred vs .pred_class) | `./references/gotchas.md` |
| set_output for scikit-learn comparison | `./references/gotchas.md` |

## Citation

When this framework is used as a primary analytical tool, include in the report's
Software & Tools references:

> Kuhn, M. & Wickham, H. (2020). Tidymodels: a collection of packages for
> modeling and machine learning using tidyverse principles.
> https://www.tidymodels.org

**Cite when:** tidymodels is used for model fitting, preprocessing, tuning, or
evaluation central to the analysis.
**Do not cite when:** Only loaded but no modeling performed.

For engine-specific citations:

> Wright, M.N. & Ziegler, A. (2017). "ranger: A Fast Implementation of Random
> Forests for High Dimensional Data in C++ and R." Journal of Statistical
> Software, 77(1), 1-17. (ranger engine)

> Friedman, J., Hastie, T., & Tibshirani, R. (2010). "Regularization Paths for
> Generalized Linear Models via Coordinate Descent." Journal of Statistical
> Software, 33(1), 1-22. (glmnet engine)

> Chen, T. & Guestrin, C. (2016). "XGBoost: A Scalable Tree Boosting System."
> Proceedings of the 22nd ACM SIGKDD, 785-794. (xgboost engine)

For method-specific citations, consult the reference files in this skill and
`agent_reference/CITATION_REFERENCE.md`.
