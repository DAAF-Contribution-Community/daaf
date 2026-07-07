# Survey, Spatial, and ML: R Explained for Python Users

Three specialized domains where R has strong, mature packages. This reference
explains R code in terms of the Python equivalents you know: survey (`survey`
package for `svy` users), spatial (`sf` for `geopandas` users), and ML
(`tidymodels`/`caret` for `scikit-learn` users).

For full R-side API details, load the dedicated skill: `survey-r`, `sf-terra`, or
`tidymodels`.

> **Versions referenced:**
> R: survey 4.5, sf 1.1-0, terra 1.9-11, tidymodels 1.4.1
> Python: svy 0.13.0, geopandas 1.1.3, scikit-learn 1.8.0
> See SKILL.md § Library Versions for the complete version table.

---

## Part A: Complex Surveys (R `survey` for `svy` Users)

### Design Specification

```r
# R -- you know this as svy.Design(stratum="stratum", psu="psu", wgt="weight")
library(survey)
des <- svydesign(
  ids     = ~psu,
  strata  = ~stratum,
  weights = ~weight,
  data    = df,
  nest    = TRUE
)
```

| R (`survey`) | Python (`svy`) |
|-------------|----------------|
| Formula: `~varname` | String: `"varname"` |
| Single `svydesign()` call | Two-step: `Design()` then `Sample()` |
| `fpc = ~pop_size` | `fpc="pop_size"` |
| R data.frame | Polars DataFrame |

### Estimation

| R (`survey`) | Python (`svy`) |
|-------------|----------------|
| `svymean(~x, design)` | `sample.estimation.mean("x")` |
| `svytotal(~x, design)` | `sample.estimation.total("x")` |
| `svyby(~x, ~group, design, svymean)` | `sample.estimation.mean("x", by="group")` |
| `svyratio(~num, ~denom, design)` | `sample.estimation.ratio(y="num", x="denom")` |

### Regression

| R (`survey`) | Python (`svy`) |
|-------------|----------------|
| `svyglm(y ~ x1 + x2, design, family=gaussian())` | `sample.glm.fit(y="y", x=["x1", "x2"], family="gaussian")` |
| `svyglm(y ~ x1, design, family=binomial())` | `sample.glm.fit(y="y", x=["x1"], family="binomial")` |
| `svyglm(y ~ factor(x), design)` | `sample.glm.fit(y="y", x=[svy.Cat("x")])` |
| `svyolr(y ~ x, design)` | **NOT AVAILABLE** (use rpy2 bridge) |
| `svycoxph(Surv(t,d) ~ x, design)` | **NOT AVAILABLE** (use rpy2 bridge) |

R's `survey` covers substantially more model families than Python's `svy`.

### Replicate Weights

| R | Python |
|---|--------|
| `svrepdesign(data=df, weights=~wt, repweights="brr[0-9]+", type="BRR")` | `svy.Design(wgt="wt", rep_weights="brr1-brr64", rep_type="brr")` |
| `as.svrepdesign(des, type="bootstrap", replicates=500)` | Specify `rep_type` in Design |

---

## Part B: Spatial Data (R `sf` for `geopandas` Users)

R's `sf` uses standalone `st_*()` functions. Python's `geopandas` uses methods
and properties on GeoDataFrame objects.

### Reading and Writing

| R (`sf`) | Python (`geopandas`) |
|---------|---------------------|
| `st_read("file.shp")` | `gpd.read_file("file.shp")` |
| `st_read("file.gpkg")` | `gpd.read_file("file.gpkg")` |
| `st_write(df, "file.gpkg")` | `gdf.to_file("file.gpkg")` |
| `sfarrow::st_read_parquet("f.parquet")` (sfarrow not pre-installed) | `gpd.read_parquet("f.parquet")` |

### Core Operations

| R (`sf`) | Python (`geopandas`) |
|---------|---------------------|
| `st_transform(df, crs)` | `gdf.to_crs(crs)` |
| `st_join(a, b)` | `gpd.sjoin(a, b)` |
| `st_buffer(geom, dist)` | `gdf.buffer(dist)` |
| `st_area(geom)` | `gdf.area` (property) |
| `st_centroid(geom)` | `gdf.centroid` (property) |
| `st_union(geom)` | `gdf.union_all()` |
| `st_intersection(a, b)` | `gpd.overlay(a, b, how="intersection")` |
| `st_crs(df)` | `gdf.crs` |
| `st_dissolve() / group_by() |> summarise()` | `gdf.dissolve(by="col")` |

**Key API difference:** R's `st_*` functions are standalone (pipe-friendly).
Python's equivalents are methods on the GeoDataFrame, properties (no parentheses),
or module-level `gpd` functions.

### Mapping

| R | Python |
|---|--------|
| `ggplot2::geom_sf()` | No plotnine equivalent; use `gdf.plot()` |
| `leaflet::leaflet(gdf)` (pre-installed) | `gdf.explore()` (folium-based) |
| `ggplot(gdf) + geom_sf(aes(fill = var))` | `gdf.plot(column="var")` |

`mapview` and `tmap` are common in the wild but NOT pre-installed in DAAF; the
pre-installed routes are `leaflet` (interactive) and `ggplot2::geom_sf()`
(static choropleths).

---

## Part C: Machine Learning (R `tidymodels` for `scikit-learn` Users)

### Paradigm Comparison

| R (`tidymodels`) | Python (`scikit-learn`) |
|-----------------|----------------------|
| Declarative: specify *what* | Imperative: call methods in sequence |
| `recipe()` with `step_*()` | `Pipeline` with transformer objects |
| `parsnip` model spec + engine | Direct estimator instantiation |
| `tune_grid()` over workflow | `GridSearchCV` wrapping estimator |
| `rsample::vfold_cv()` creates folds | `StratifiedKFold` or `cross_val_score` |

### Model Training

| R | Python |
|---|--------|
| `rand_forest() |> set_engine("ranger")` | `RandomForestClassifier()` |
| `logistic_reg()` | `LogisticRegression()` |
| `linear_reg()` | `Ridge()` / `Lasso()` / `ElasticNet()` |
| `boost_tree() |> set_engine("xgboost")` | `GradientBoostingClassifier()` |

### Preprocessing

| R (`recipes`) | Python (`sklearn.preprocessing`) |
|--------------|--------------------------------|
| `step_normalize(all_numeric_predictors())` | `StandardScaler()` |
| `step_dummy(all_nominal_predictors())` | `OneHotEncoder(drop="first")` |
| `step_impute_median(...)` | `SimpleImputer(strategy="median")` |
| `step_pca(..., num_comp=5)` | `PCA(n_components=5)` |

### Unsupervised Learning

| R | Python |
|---|--------|
| `kmeans(x, centers = k)` | `KMeans(n_clusters=k).fit(X)` |
| `prcomp(x, scale. = TRUE)` | `PCA().fit_transform(StandardScaler().fit_transform(X))` |
| `Rtsne::Rtsne(x)` (not pre-installed) | `TSNE().fit_transform(X)` |
| `uwot::umap(x)` (pre-installed) | `umap.UMAP().fit_transform(X)` |

### Model Evaluation

| R | Python |
|---|--------|
| `yardstick::accuracy(data, truth, estimate)` | `accuracy_score(y_true, y_pred)` |
| `yardstick::roc_auc(...)` | `roc_auc_score(y_true, y_prob)` |
| `rsample::vfold_cv(data, v = 10)` | `StratifiedKFold(n_splits=10)` |
| `tune::tune_grid(wf, resamples, grid)` | `GridSearchCV(pipe, param_grid, cv=5)` |

---

## Coverage Gaps Summary

| Domain | R Advantage | Python Gap |
|--------|-------------|-----------|
| Survey | Ordinal logistic, Cox survival, neg. binomial | Use rpy2 bridge |
| Survey | Full formula interface | Pre-compute interactions manually |
| Spatial | `geom_sf()` in ggplot2 | Use `gdf.plot()` (matplotlib) |
| Spatial | `terra` raster unified | `rasterio` + `rioxarray` + `rasterstats` |
| ML | `NbClust` all-in-one cluster count (not pre-installed in DAAF) | Manual silhouette/elbow/gap |
| ML | `recipes` tidy selectors | `ColumnTransformer` + `make_column_selector()` |

The gaps above run R-ward, but the reverse holds for ML depth overall: Python's
scikit-learn ecosystem is deeper than tidymodels for model interpretation,
fairness auditing, and clustering diagnostics, so for ML-heavy work it is
reasonable to stay in Python (scikit-learn) even when the rest of the pipeline
is in R; the R-side interpretation/fairness tooling (iml, fairmodels, vip) is
covered in the `tidymodels` skill.

> **Sources:** Lumley, *Complex Surveys* (2010);
> Pebesma, *sf* (r-spatial.github.io/sf/, accessed 2026-03-28);
> Kuhn & Silge, *Tidy Modeling with R* (2022);
> scikit-learn documentation (scikit-learn.org, accessed 2026-03-28)
