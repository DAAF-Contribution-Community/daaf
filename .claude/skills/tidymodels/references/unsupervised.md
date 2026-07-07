# Unsupervised Methods

PCA via recipes, UMAP via uwot, and k-means clustering via base R. tidymodels
is primarily a supervised learning framework; unsupervised methods are either
integrated into recipes (PCA) or use standalone R packages (uwot, stats::kmeans).

## PCA via recipes::step_pca

PCA can be added as a recipe step for dimension reduction as part of a supervised
pipeline, or used standalone for exploratory analysis.

### PCA in a Supervised Pipeline

```r
library(tidymodels)

rec <- recipe(outcome ~ ., data = train_data) |>
  step_normalize(all_numeric_predictors()) |>  # Always scale before PCA
  step_pca(all_numeric_predictors(), num_comp = 5)

# In a workflow, PCA is applied as preprocessing before the model
wf <- workflow() |>
  add_recipe(rec) |>
  add_model(spec)
```

### PCA for Exploration (Standalone)

```r
library(tidymodels)

# Define recipe with PCA
rec <- recipe(~ ., data = df) |>  # No outcome -- unsupervised

  step_normalize(all_numeric()) |>
  step_pca(all_numeric(), num_comp = 5)

# Prep and bake
prepped <- prep(rec, training = df)
pca_results <- bake(prepped, new_data = NULL)

# Inspect variance explained
tidy(prepped, number = 2, type = "variance")
# Returns: terms, value, component columns
# terms "variance" = eigenvalue
# terms "cumulative percent variance" = cumulative explained variance
```

### PCA Parameters

| Parameter | Purpose | Default |
|-----------|---------|---------|
| `num_comp` | Number of components to retain | 5 |
| `threshold` | Retain components until cumulative variance >= threshold | (not used by default) |
| `prefix` | Column name prefix for components | "PC" |

```r
# Keep enough components for 95% variance
rec <- recipe(~ ., data = df) |>
  step_normalize(all_numeric()) |>
  step_pca(all_numeric(), threshold = 0.95)
```

### PCA Loadings

```r
prepped <- prep(rec, training = df)

# Get loadings (component weights)
loadings <- tidy(prepped, number = 2)  # number = PCA step index
# Returns tibble: terms (variable), value (loading), component (PC1, PC2, ...)
```

## UMAP via uwot

UMAP (Uniform Manifold Approximation and Projection) is not part of tidymodels.
Use the `uwot` package directly. UMAP is for **visualization only** -- do not
use UMAP distances for quantitative analysis.

### Basic UMAP

```r
library(uwot)

# Input: numeric matrix or data frame (scaled)
X_scaled <- scale(df[, numeric_cols])

set.seed(42)
umap_result <- umap(X_scaled, n_components = 2, n_neighbors = 15, min_dist = 0.1)

# umap_result is a matrix with n_components columns
umap_df <- data.frame(
  UMAP1 = umap_result[, 1],
  UMAP2 = umap_result[, 2]
)
```

### UMAP Parameters

| Parameter | Purpose | Default | Guidance |
|-----------|---------|---------|----------|
| `n_components` | Output dimensions | 2 | Use 2 for visualization |
| `n_neighbors` | Local neighborhood size | 15 | Smaller = more local structure |
| `min_dist` | Minimum distance in embedding | 0.01 | Smaller = tighter clusters |
| `metric` | Distance metric | "euclidean" | "cosine" for text/sparse |
| `n_epochs` | Training iterations | NULL (auto) | More = better quality |
| `scale` | Scale input | FALSE | Pre-scale with `scale()` instead |

### UMAP Visualization

```r
library(ggplot2)

umap_df$label <- df$group_variable

ggplot(umap_df, aes(x = UMAP1, y = UMAP2, color = label)) +
  geom_point(alpha = 0.6, size = 1.5) +
  theme_minimal() +
  labs(title = "UMAP Embedding")
```

### UMAP Caveats

- **Visualization only**: UMAP distorts distances to preserve local neighborhoods.
  Cluster sizes and between-cluster gaps in the plot are not meaningful.
- **Parameter sensitivity**: Results change with `n_neighbors` and `min_dist`.
  Run multiple parameter values and report sensitivity.
- **Reproducibility**: Always set `set.seed()` before calling `umap()`.
- **Scaling**: Always scale numeric features before UMAP (use `scale()`).

## K-Means Clustering via stats::kmeans

Base R's `kmeans()` is the standard k-means implementation. tidymodels does not
provide its own clustering API.

### Basic K-Means

```r
# Scale features first
X_scaled <- scale(df[, numeric_cols])

set.seed(42)
km <- kmeans(X_scaled, centers = 4, nstart = 25)

# Results
km$cluster          # Cluster assignment for each row
km$centers          # Cluster centroids (in scaled space)
km$tot.withinss     # Total within-cluster sum of squares
km$withinss         # Within-SS per cluster
km$size             # Number of observations per cluster
```

### Choosing k (Elbow Method)

```r
wss <- sapply(2:15, function(k) {
  set.seed(42)
  kmeans(X_scaled, centers = k, nstart = 25)$tot.withinss
})

plot(2:15, wss, type = "b", xlab = "k", ylab = "Total within-SS",
     main = "Elbow Plot")
```

### Silhouette Score

```r
library(cluster)

km <- kmeans(X_scaled, centers = 4, nstart = 25)
sil <- silhouette(km$cluster, dist(X_scaled))
mean(sil[, "sil_width"])  # Average silhouette width
```

### K-Means Parameters

| Parameter | Purpose | Recommended |
|-----------|---------|-------------|
| `centers` | Number of clusters (k) | Determine via elbow/silhouette |
| `nstart` | Number of random initializations | 25+ |
| `iter.max` | Maximum iterations | 300 (increase if convergence warning) |
| `algorithm` | Algorithm variant | "Hartigan-Wong" (default) |

## When to Use Each Method

| Method | Purpose | Within tidymodels? |
|--------|---------|-------------------|
| PCA (step_pca) | Dimension reduction as preprocessing | Yes (recipe step) |
| PCA (standalone) | Exploratory variance analysis | Yes (prep + bake) |
| UMAP (uwot) | Nonlinear visualization of high-dim data | No (standalone) |
| K-means (stats) | Partition data into k groups | No (standalone) |

For methodology guidance on when to use clustering, PCA, or UMAP, consult
the `data-scientist` skill's `exploratory-unsupervised.md` reference.

## Quick Reference

| Task | Code |
|------|------|
| PCA in recipe | `step_pca(all_numeric_predictors(), num_comp = 5)` |
| PCA threshold | `step_pca(all_numeric(), threshold = 0.95)` |
| PCA loadings | `tidy(prepped_rec, number = pca_step_index)` |
| PCA variance | `tidy(prepped_rec, number = pca_step_index, type = "variance")` |
| UMAP | `uwot::umap(X_scaled, n_components = 2)` |
| K-means | `kmeans(X_scaled, centers = k, nstart = 25)` |
| Silhouette | `cluster::silhouette(km$cluster, dist(X))` |
