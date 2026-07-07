# Resampling

Resampling strategies via rsample: v-fold cross-validation, bootstrap, leave-one-out,
grouped CV, stratification, and the analysis/assessment split API.

## Train/Test Split

Before resampling, create a held-out test set:

```r
library(tidymodels)

set.seed(42)
split <- initial_split(data, prop = 0.8, strata = outcome)
train_data <- training(split)
test_data <- testing(split)
```

| Argument | Purpose | Default |
|----------|---------|---------|
| `prop` | Fraction for training | 0.75 |
| `strata` | Stratify by this variable | NULL (no stratification) |

Stratification preserves the outcome distribution across train/test. Use it
for classification or skewed numeric outcomes.

## V-Fold Cross-Validation

The most common resampling strategy. Splits training data into v folds; each
fold serves as assessment (validation) once.

```r
set.seed(42)
folds <- vfold_cv(train_data, v = 10, strata = outcome)

# folds is an rset object with v rows
folds
# Each row contains a split object with analysis (train) and assessment (test)
```

| Argument | Purpose | Default |
|----------|---------|---------|
| `v` | Number of folds | 10 |
| `repeats` | Repeat the entire v-fold process | 1 |
| `strata` | Stratify folds by this variable | NULL |

### Repeated V-Fold CV

More stable estimates at the cost of computation:

```r
set.seed(42)
folds <- vfold_cv(train_data, v = 10, repeats = 5, strata = outcome)
# 50 total resamples (10 folds x 5 repeats)
```

## Bootstrap

Sample with replacement. Each resample is the same size as the original data;
out-of-bag observations form the assessment set.

```r
set.seed(42)
boots <- bootstraps(train_data, times = 25, strata = outcome)
```

| Argument | Purpose | Default |
|----------|---------|---------|
| `times` | Number of bootstrap samples | 25 |
| `strata` | Stratify by this variable | NULL |

Bootstrap tends to produce optimistic performance estimates compared to v-fold CV.

## Leave-One-Out Cross-Validation

Each observation is the assessment set once. Only practical for small datasets.

```r
loo <- loo_cv(train_data)
# n resamples, one observation per assessment set
```

## Group V-Fold Cross-Validation

When observations are nested within groups (e.g., students within schools) and
you want to ensure entire groups stay together in the same fold:

```r
set.seed(42)
group_folds <- group_vfold_cv(train_data, group = school_id, v = 10)
# All observations from a school are in the same fold
```

This prevents data leakage when observations within a group are correlated.

## Accessing Splits

Each resample contains an analysis set (training fold) and an assessment set
(validation fold):

```r
# Access the first split
first_split <- folds$splits[[1]]

# Get the data
analysis_data <- analysis(first_split)    # Training fold
assessment_data <- assessment(first_split) # Validation fold

cat("Analysis rows:", nrow(analysis_data), "\n")
cat("Assessment rows:", nrow(assessment_data), "\n")
```

## Using Resamples with Workflows

Resamples integrate with `fit_resamples()` (fixed parameters) and `tune_grid()`
(hyperparameter search):

```r
# --- Evaluate a fixed workflow ---
results <- fit_resamples(wf, resamples = folds)
collect_metrics(results)

# --- Tune hyperparameters ---
tune_results <- tune_grid(wf, resamples = folds, grid = 20)
collect_metrics(tune_results)
```

## Stratification

Stratification ensures each fold/resample reflects the overall distribution of a
variable. Use it when:

- **Classification**: Prevents a fold from having no examples of a rare class
- **Regression**: Prevents extreme values from clustering in one fold
- **Imbalanced data**: Maintains class proportions in every fold

```r
# Stratify by outcome (classification)
folds <- vfold_cv(train_data, v = 10, strata = outcome)

# Stratify by a continuous variable (uses quartile binning internally)
folds <- vfold_cv(train_data, v = 10, strata = income)
```

## Validation Set (Single Split)

For large datasets where v-fold CV is too expensive:

```r
set.seed(42)
val_split <- validation_split(train_data, prop = 0.8, strata = outcome)
# Single split: 80% analysis, 20% assessment
# Compatible with fit_resamples() and tune_grid()
```

## Quick Reference

| Strategy | Function | When to Use |
|----------|----------|-------------|
| Train/test split | `initial_split(data, prop, strata)` | Hold out test set |
| V-fold CV | `vfold_cv(data, v, strata)` | Standard evaluation |
| Repeated V-fold | `vfold_cv(data, v, repeats, strata)` | More stable estimates |
| Bootstrap | `bootstraps(data, times, strata)` | Confidence intervals |
| LOO CV | `loo_cv(data)` | Small datasets only |
| Group V-fold | `group_vfold_cv(data, group, v)` | Clustered/nested data |
| Validation set | `validation_split(data, prop, strata)` | Large datasets |
| Get training fold | `analysis(split)` | Manual access |
| Get validation fold | `assessment(split)` | Manual access |
