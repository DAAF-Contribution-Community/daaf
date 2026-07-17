# --- Config ---
# INTENT: Smoke test for tidymodels skill — verify installed versions and
#         core API patterns documented in skill reference files

library(tidymodels)
library(ranger)
library(glmnet)
library(xgboost)
library(uwot)

test_count <- 0
pass_count <- 0

# --- Version Check ---
cat("=== VERSION CHECK ===\n")

# Test 1: Package version alignment with SKILL.md metadata
expected_versions <- list(
  tidymodels = "1.4.1",
  recipes = "1.3.2",
  parsnip = "1.5.0",
  workflows = "1.3.0",
  tune = "2.0.1",
  rsample = "1.3.2",
  ranger = "0.18.0",
  glmnet = "4.1.10",
  xgboost = "3.2.1.1",
  uwot = "0.2.4"
)

for (pkg_name in names(expected_versions)) {
  installed <- as.character(packageVersion(pkg_name))
  expected <- expected_versions[[pkg_name]]
  cat(pkg_name, ": installed =", installed, ", expected =", expected, "\n")
  stopifnot(installed == expected)
}

cat("R version:", R.version$major, ".", R.version$minor, "\n", sep = "")
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: Versions aligned\n\n")

# --- Core API Tests ---
cat("=== CORE API TESTS ===\n")

# Test 2: recipe() + step_normalize() — preprocessing
# Source: recipes.md
cat("Test 2: recipe() + step_normalize()\n")
rec <- recipe(Species ~ ., data = iris) |>
  step_normalize(all_numeric_predictors())
prepped <- prep(rec, training = iris)
baked <- bake(prepped, new_data = NULL)

stopifnot(is.data.frame(baked))
stopifnot(ncol(baked) == 5)
# Verify normalization: means should be near 0
col_means <- colMeans(baked[, 1:4])
stopifnot(all(abs(col_means) < 0.01))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: recipe + step_normalize works correctly\n\n")

# Test 3: rand_forest() |> set_engine("ranger") — model specification
# Source: models.md, engines.md
cat("Test 3: rand_forest() |> set_engine('ranger')\n")
spec <- rand_forest(trees = 100) |>
  set_engine("ranger") |>
  set_mode("classification")

stopifnot(inherits(spec, "model_spec"))
stopifnot(spec$engine == "ranger")
cat("PASS: rand_forest model spec with ranger engine\n\n")

# Test 4: workflow() + fit() — workflow fitting
# Source: workflows.md
cat("Test 4: workflow() + fit()\n")
set.seed(42)
split <- initial_split(iris, prop = 0.8, strata = Species)
train_data <- training(split)
test_data <- testing(split)

wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)

fit_result <- wf |> fit(data = train_data)

stopifnot(inherits(fit_result, "workflow"))
# Verify the workflow has a fitted model
engine_fit <- extract_fit_engine(fit_result)
stopifnot(inherits(engine_fit, "ranger"))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: workflow + fit works correctly\n\n")

# Test 5: vfold_cv() + tune_grid() — cross-validation and tuning
# Source: tuning.md, resampling.md
cat("Test 5: vfold_cv() + tune_grid()\n")
set.seed(42)
folds <- vfold_cv(train_data, v = 3, strata = Species)

tune_spec <- rand_forest(trees = 50, mtry = tune()) |>
  set_engine("ranger") |>
  set_mode("classification")

tune_wf <- workflow() |>
  add_recipe(rec) |>
  add_model(tune_spec)

set.seed(42)
tune_results <- tune_grid(
  tune_wf,
  resamples = folds,
  grid = 3
)

stopifnot(inherits(tune_results, "tune_results"))
stopifnot(nrow(tune_results) == 3)  # 3 folds
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: vfold_cv + tune_grid works correctly\n\n")

# Test 6: collect_metrics() — results extraction
# Source: tuning.md, evaluation.md
cat("Test 6: collect_metrics()\n")
metrics <- collect_metrics(tune_results)

stopifnot(is.data.frame(metrics))
stopifnot("accuracy" %in% metrics$.metric)
stopifnot("roc_auc" %in% metrics$.metric)
stopifnot("mean" %in% names(metrics))
cat("Metrics collected:", unique(metrics$.metric), "\n")
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: collect_metrics returns expected metrics\n\n")

# Test 7: glmnet lasso via parsnip — regularization
# Source: models.md, engines.md
cat("Test 7: glmnet lasso via parsnip\n")
lasso_rec <- recipe(mpg ~ ., data = mtcars) |>
  step_normalize(all_numeric_predictors())

lasso_spec <- linear_reg(penalty = 0.1, mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")

lasso_wf <- workflow() |>
  add_recipe(lasso_rec) |>
  add_model(lasso_spec)

lasso_fit <- lasso_wf |> fit(data = mtcars)

stopifnot(inherits(lasso_fit, "workflow"))
engine_obj <- extract_fit_engine(lasso_fit)
stopifnot(inherits(engine_obj, "glmnet"))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: glmnet lasso via parsnip works correctly\n\n")

# Test 8: predict() on new data — prediction
# Source: workflows.md
cat("Test 8: predict() on new data\n")
preds <- fit_result |> augment(new_data = test_data)

stopifnot(is.data.frame(preds))
stopifnot(".pred_class" %in% names(preds))
stopifnot(nrow(preds) == nrow(test_data))

acc <- accuracy(preds, truth = Species, estimate = .pred_class)
cat("Test accuracy:", acc$.estimate, "\n")
stopifnot(acc$.estimate > 0.5)  # Should be well above chance
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: predict on new data works correctly\n\n")

# Test 9: uwot::umap() — UMAP embedding
# Source: unsupervised.md
cat("Test 9: uwot::umap()\n")
X_scaled <- scale(iris[, 1:4])

set.seed(42)
umap_result <- uwot::umap(X_scaled, n_components = 2, n_neighbors = 15)

stopifnot(is.matrix(umap_result))
stopifnot(ncol(umap_result) == 2)
stopifnot(nrow(umap_result) == 150)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: uwot::umap() produces 2D embedding\n\n")

# --- Summary ---
cat("=== SMOKE TEST SUMMARY ===\n")
cat("Tests run:", test_count, "\n")
cat("Tests passed:", pass_count, "\n")
cat("Tests failed:", test_count - pass_count, "\n")
stopifnot(pass_count == test_count)
cat("ALL SMOKE TESTS PASSED\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-10 15:53:34
# Command: Rscript /daaf/scripts/smoke_tests/smoke_tidymodels.R
# Duration: 3s
# Exit code: 0
#
# --- STDOUT ---
# ── Attaching packages ────────────────────────────────────── tidymodels 1.4.1 ──
# ✔ broom        1.0.12     ✔ recipes      1.3.2 
# ✔ dials        1.4.3      ✔ rsample      1.3.2 
# ✔ dplyr        1.2.1      ✔ tailor       0.1.0 
# ✔ ggplot2      4.0.2      ✔ tidyr        1.3.2 
# ✔ infer        1.1.0      ✔ tune         2.0.1 
# ✔ modeldata    1.5.1      ✔ workflows    1.3.0 
# ✔ parsnip      1.5.0      ✔ workflowsets 1.1.1 
# ✔ purrr        1.2.2      ✔ yardstick    1.4.0 
# ── Conflicts ───────────────────────────────────────── tidymodels_conflicts() ──
# ✖ purrr::discard() masks scales::discard()
# ✖ dplyr::filter()  masks stats::filter()
# ✖ dplyr::lag()     masks stats::lag()
# ✖ recipes::step()  masks stats::step()
# Loading required package: Matrix
# 
# Attaching package: ‘Matrix’
# 
# The following objects are masked from ‘package:tidyr’:
# 
#     expand, pack, unpack
# 
# Loaded glmnet 4.1-10
# === VERSION CHECK ===
# tidymodels : installed = 1.4.1 , expected = 1.4.1 
# recipes : installed = 1.3.2 , expected = 1.3.2 
# parsnip : installed = 1.5.0 , expected = 1.5.0 
# workflows : installed = 1.3.0 , expected = 1.3.0 
# tune : installed = 2.0.1 , expected = 2.0.1 
# rsample : installed = 1.3.2 , expected = 1.3.2 
# ranger : installed = 0.18.0 , expected = 0.18.0 
# glmnet : installed = 4.1.10 , expected = 4.1.10 
# xgboost : installed = 3.2.1.1 , expected = 3.2.1.1 
# uwot : installed = 0.2.4 , expected = 0.2.4 
# R version:4.5.3
# PASS: Versions aligned
# 
# === CORE API TESTS ===
# Test 2: recipe() + step_normalize()
# PASS: recipe + step_normalize works correctly
# 
# Test 3: rand_forest() |> set_engine('ranger')
# PASS: rand_forest model spec with ranger engine
# 
# Test 4: workflow() + fit()
# PASS: workflow + fit works correctly
# 
# Test 5: vfold_cv() + tune_grid()
# i Creating pre-processing data to finalize 1 unknown parameter: "mtry"
# PASS: vfold_cv + tune_grid works correctly
# 
# Test 6: collect_metrics()
# Metrics collected: accuracy brier_class roc_auc 
# PASS: collect_metrics returns expected metrics
# 
# Test 7: glmnet lasso via parsnip
# PASS: glmnet lasso via parsnip works correctly
# 
# Test 8: predict() on new data
# Test accuracy: 0.9333333 
# PASS: predict on new data works correctly
# 
# Test 9: uwot::umap()
# PASS: uwot::umap() produces 2D embedding
# 
# === SMOKE TEST SUMMARY ===
# Tests run: 8 
# Tests passed: 8 
# Tests failed: 0 
# ALL SMOKE TESTS PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
