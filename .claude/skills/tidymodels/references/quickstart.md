# Quickstart

The complete tidymodels workflow: recipe, model specification, workflow, fit,
predict. Covers the fundamental paradigm difference from scikit-learn and shows
end-to-end examples for both classification and regression.

## Installation

No installation needed in DAAF: `tidymodels`, all four engine packages
(`ranger`, `glmnet`, `xgboost`, `kknn`), and `uwot` (UMAP) are pre-installed
in the container. Runtime installs are blocked in DAAF (`install.packages()`
is refused both at the command line and inside executed scripts — see
CLAUDE.md § Runtime Package Installation). If a package beyond these is
needed, escalate to the user to add it to the Dockerfile (user additions
block near the end) and rebuild.

### Verify Installation

```r
library(tidymodels)
cat("tidymodels version:", as.character(packageVersion("tidymodels")), "\n")
cat("recipes version:", as.character(packageVersion("recipes")), "\n")
cat("parsnip version:", as.character(packageVersion("parsnip")), "\n")
```

## Core Concept: The Recipe/Workflow Paradigm

tidymodels separates ML into three distinct objects:

| Object | Purpose | scikit-learn Equivalent |
|--------|---------|------------------------|
| **Recipe** | Preprocessing specification | `ColumnTransformer` + scalers/encoders |
| **Model spec** (parsnip) | Algorithm + engine + mode | `RandomForestClassifier(...)` |
| **Workflow** | Bundles recipe + model | `Pipeline([...])` |

Key difference from scikit-learn: in scikit-learn, preprocessing steps are
positional inside a Pipeline. In tidymodels, the recipe is a self-contained
specification that knows which columns to transform based on roles and selectors,
not position.

## Train/Test Split

```r
library(tidymodels)

# --- Basic split ---
set.seed(42)
split <- initial_split(data, prop = 0.8)
train_data <- training(split)
test_data <- testing(split)

# --- Stratified split (preserves outcome distribution) ---
set.seed(42)
split <- initial_split(data, prop = 0.8, strata = outcome)
train_data <- training(split)
test_data <- testing(split)
```

## Supervised Example: Classification (End-to-End)

```r
library(tidymodels)

# --- Data ---
set.seed(42)
split <- initial_split(iris, prop = 0.8, strata = Species)
train_data <- training(split)
test_data <- testing(split)

# --- 1. Recipe ---
rec <- recipe(Species ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors())

# --- 2. Model spec ---
spec <- rand_forest(trees = 500) |>
  set_engine("ranger") |>
  set_mode("classification")

# --- 3. Workflow ---
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)

# --- 4. Fit ---
fit <- wf |> fit(data = train_data)

# --- 5. Predict + evaluate ---
preds <- fit |> augment(new_data = test_data)
# augment() returns the test data with .pred_class and .pred_{level} columns

accuracy(preds, truth = Species, estimate = .pred_class)
```

## Supervised Example: Regression (End-to-End)

```r
library(tidymodels)

# --- Data ---
set.seed(42)
split <- initial_split(mtcars, prop = 0.8, strata = mpg)
train_data <- training(split)
test_data <- testing(split)

# --- 1. Recipe ---
rec <- recipe(mpg ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors())

# --- 2. Model spec ---
spec <- linear_reg(penalty = 0.01, mixture = 1) |>
  set_engine("glmnet") |>
  set_mode("regression")

# --- 3. Workflow ---
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)

# --- 4. Fit ---
fit <- wf |> fit(data = train_data)

# --- 5. Predict + evaluate ---
preds <- fit |> augment(new_data = test_data)
rmse(preds, truth = mpg, estimate = .pred)
rsq(preds, truth = mpg, estimate = .pred)
```

## The augment() Pattern

`augment()` is the preferred way to get predictions in tidymodels. It returns
the original data with prediction columns appended:

| Column | When | Content |
|--------|------|---------|
| `.pred` | regression | Numeric prediction |
| `.pred_class` | classification | Predicted class factor |
| `.pred_{level}` | classification | Probability for each class level |

```r
# augment returns a tibble with predictions joined to the data
results <- fit |> augment(new_data = test_data)

# For classification, you get both class predictions and probabilities
# results$.pred_class   -- predicted class
# results$.pred_setosa  -- probability of setosa
# results$.pred_versicolor -- etc.
```

## Reproducibility with set.seed()

R uses `set.seed()` for reproducibility. Set it before any random operation:

```r
set.seed(42)
split <- initial_split(data, prop = 0.8)

set.seed(42)
folds <- vfold_cv(train_data, v = 10)
```

Unlike scikit-learn where `random_state` is per-estimator, R's `set.seed()` is
global. Set it once before each random operation for reproducibility.

## Data Format: tibbles and data frames

tidymodels works with R data frames and tibbles. Unlike scikit-learn (which
often requires numeric matrices), tidymodels handles factors and characters
natively -- the recipe does the encoding.

```r
# Factors are fine -- recipe handles encoding
df <- tibble(
  outcome = factor(c("yes", "no", "yes", "no")),
  feature1 = c(1.0, 2.0, 3.0, 4.0),
  category = factor(c("a", "b", "a", "b"))
)

# Recipe will encode 'category' via step_dummy()
rec <- recipe(outcome ~ ., data = df) |>
  step_dummy(all_nominal_predictors())
```

## Next Steps

- Need preprocessing steps? See `recipes.md`
- Need to choose a model? See `models.md`
- Need cross-validation? See `resampling.md`
- Need hyperparameter tuning? See `tuning.md`
- Coming from scikit-learn or caret? See `gotchas.md`
