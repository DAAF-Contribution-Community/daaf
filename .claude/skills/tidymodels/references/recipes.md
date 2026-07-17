# Recipes

Preprocessing specification via the recipes package. Covers step functions for
normalization, encoding, imputation, interactions, and transformations. Also
covers role assignment, selector functions, and the prep/bake API.

## Recipe Basics

A recipe is a preprocessing specification. It describes *what* transformations to
apply, but does not execute them until `prep()` (fit) and `bake()` (transform).
When used inside a workflow, prep/bake happen automatically during `fit()`.

```r
library(tidymodels)

# Define a recipe
rec <- recipe(outcome ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())

# Manual prep + bake (rarely needed -- workflows handle this)
prepped <- prep(rec, training = train_data)
baked_train <- bake(prepped, new_data = NULL)      # NULL = training data
baked_test <- bake(prepped, new_data = test_data)   # Apply to test
```

## Selector Functions

Selectors choose which columns a step applies to. Use these instead of
hard-coding column names:

| Selector | Selects |
|----------|---------|
| `all_predictors()` | All predictor columns |
| `all_outcomes()` | Outcome column(s) |
| `all_numeric_predictors()` | Numeric predictors only |
| `all_nominal_predictors()` | Factor/character predictors only |
| `all_numeric()` | All numeric columns (including outcome) |
| `all_nominal()` | All factor/character columns |
| `starts_with("x")` | Columns starting with "x" |
| `contains("score")` | Columns containing "score" |
| `matches("^x\\d+$")` | Regex match |
| `has_role("id")` | Columns with a specific role |

```r
# Combine selectors
rec <- recipe(y ~ ., data = df) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors()) |>
  step_log(starts_with("income"))
```

## Normalization and Scaling

### step_normalize (Z-score)

Centers to mean=0, scales to sd=1. The default choice for most ML methods.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors())
```

### step_range (Min-Max Scaling)

Scales to [0, 1] range.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_range(all_numeric_predictors(), min = 0, max = 1)
```

### step_center / step_scale (Separate)

Center only or scale only:

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_center(all_numeric_predictors()) |>  # Subtract mean
  step_scale(all_numeric_predictors())      # Divide by sd
```

## Encoding Categorical Variables

### step_dummy (One-Hot Encoding)

Creates indicator variables for factor/character columns.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_dummy(all_nominal_predictors(), one_hot = FALSE)
# one_hot = FALSE (default): drops reference level (n-1 dummies)
# one_hot = TRUE: creates n dummies (no reference level dropped)
```

### step_integer (Ordinal Encoding)

Maps factor levels to integers.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_integer(ordered_var)
```

### step_other (Lump Rare Categories)

Collapses infrequent factor levels into "other".

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_other(category_col, threshold = 0.05)  # Levels < 5% become "other"
```

## Imputation

### step_impute_mean / step_impute_median

Replace NA with mean or median (numeric columns only).

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_impute_mean(all_numeric_predictors())   # Mean imputation
  # or
  step_impute_median(all_numeric_predictors())  # Median (more robust)
```

### step_impute_knn

K-nearest-neighbor imputation.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_impute_knn(all_predictors(), neighbors = 5)
```

### step_impute_mode

Replace NA with mode (for factor columns).

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_impute_mode(all_nominal_predictors())
```

## Interactions and Transformations

### step_interact

Create interaction terms.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_interact(terms = ~ x1:x2)           # Single interaction
  # or
  step_interact(terms = ~ starts_with("x"):starts_with("z"))  # Multiple
```

### step_mutate

Create new features with arbitrary R expressions.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_mutate(ratio = feature1 / feature2,
              log_income = log(income + 1))
```

### step_log / step_sqrt

Common transformations.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_log(income, base = 10) |>
  step_sqrt(count_var)
```

### step_poly

Polynomial expansion.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_poly(x1, degree = 3)
```

## Feature Filtering

### step_zv / step_nzv

Remove zero-variance or near-zero-variance predictors.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_zv(all_predictors()) |>       # Remove constant columns
  step_nzv(all_predictors())         # Remove near-constant columns
```

### step_corr

Remove highly correlated predictors.

```r
rec <- recipe(y ~ ., data = train_data) |>
  step_corr(all_numeric_predictors(), threshold = 0.9)
```

## Role Assignment

By default, the formula determines roles (outcome vs predictors). Use
`update_role()` to assign custom roles for ID or grouping variables that should
not be used as predictors:

```r
rec <- recipe(y ~ ., data = train_data) |>
  update_role(student_id, new_role = "id") |>
  update_role(school_name, new_role = "group") |>
  step_normalize(all_numeric_predictors())
# student_id and school_name are kept in the data but not used as predictors
```

## Step Ordering

The order of steps in a recipe matters. Follow this recommended sequence:

1. **Imputation** -- fill NA before other transformations
2. **Feature engineering** -- interactions, polynomials, transformations
3. **Encoding** -- dummy variables (after imputation)
4. **Normalization** -- scale after encoding (dummy columns are already 0/1)
5. **Filtering** -- remove zero-variance or correlated after all other steps

```r
rec <- recipe(y ~ ., data = train_data) |>
  # 1. Imputation
  step_impute_median(all_numeric_predictors()) |>
  step_impute_mode(all_nominal_predictors()) |>
  # 2. Feature engineering
  step_interact(terms = ~ x1:x2) |>
  step_log(income) |>
  # 3. Encoding
  step_dummy(all_nominal_predictors()) |>
  # 4. Normalization
  step_normalize(all_numeric_predictors()) |>
  # 5. Filtering
  step_zv(all_predictors())
```

## Quick Reference

| Task | Step Function |
|------|---------------|
| Z-score normalize | `step_normalize(all_numeric_predictors())` |
| Min-max scale | `step_range(all_numeric_predictors())` |
| One-hot encode | `step_dummy(all_nominal_predictors())` |
| Lump rare levels | `step_other(col, threshold = 0.05)` |
| Mean impute | `step_impute_mean(all_numeric_predictors())` |
| Median impute | `step_impute_median(all_numeric_predictors())` |
| KNN impute | `step_impute_knn(all_predictors(), neighbors = 5)` |
| Mode impute | `step_impute_mode(all_nominal_predictors())` |
| Interaction | `step_interact(terms = ~ x1:x2)` |
| New feature | `step_mutate(new_col = expr)` |
| Log transform | `step_log(col)` |
| Polynomial | `step_poly(col, degree = 3)` |
| Remove constant | `step_zv(all_predictors())` |
| Remove correlated | `step_corr(all_numeric_predictors(), threshold = 0.9)` |
| Assign role | `update_role(col, new_role = "id")` |
| PCA | `step_pca(all_numeric_predictors(), num_comp = 5)` |
