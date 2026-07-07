# Survey, Spatial, and Machine Learning: Stata to R

For full R-side API details, load the dedicated skill: `survey-r`, `sf-terra`, or
`tidymodels`.

---

## Part A: Complex Surveys (Stata `svy:` to R `survey`)

R's `survey` package by Thomas Lumley is the gold standard for design-based
inference -- more mature and comprehensive than both Stata's `svy:` and Python's
`svy` package.

### Design Specification

```stata
svyset psu_id [pw=finalwgt], strata(stratum_var)
svy: mean income
svy: regress y x1 x2
```

```r
library(survey)

design <- svydesign(id = ~psu_id, strata = ~stratum_var,
                    weights = ~finalwgt, data = df)
svymean(~income, design)
svyglm(y ~ x1 + x2, design = design)
```

### Estimation Mapping

| Stata | R (survey) |
|-------|------------|
| `svy: mean income` | `svymean(~income, design)` |
| `svy: total population` | `svytotal(~population, design)` |
| `svy: proportion employed` | `svymean(~employed, design)` |
| `svy: regress y x1 x2` | `svyglm(y ~ x1 + x2, design)` |
| `svy: logit y x1 x2` | `svyglm(y ~ x1 + x2, design, family = quasibinomial)` |
| `svy, over(gender): mean income` | `svyby(~income, ~gender, design, svymean)` |
| `svy, subpop(female): mean income` | `svymean(~income, subset(design, female == 1))` |

### Key R Advantages Over Stata

- Broader model family (ordinal, multinomial, Cox survival via svycoxph)
- Post-stratification, raking, and GREG calibration via `calibrate()`
- Replicate weight support (BRR, jackknife, bootstrap) via `svrepdesign()`

---

## Part B: Spatial Analysis (sf/terra)

R's spatial ecosystem (sf + terra + spdep) is substantially more capable than
Stata's limited spatial tools.

| Stata | R |
|-------|---|
| `shp2dta using shapefile` | `st_read("shapefile.shp")` |
| `spmap var using coords.dta` | `ggplot() + geom_sf(aes(fill = var))` |
| `spmatrix create contiguity W` | `spdep::poly2nb(gdf)` |
| `spregress y x, gs2sls dvarlag(W)` | `spatialreg::lagsarlm(y ~ x, data, W)` |
| No equivalent | `st_join()`, `st_buffer()`, `st_intersection()` |
| No equivalent | Interactive maps via `leaflet` |

---

## Part C: Machine Learning (tidymodels)

R's tidymodels framework is dramatically more capable than Stata's limited ML.
That said, Python's scikit-learn ecosystem is deeper still — especially for model
interpretation, fairness auditing, and clustering diagnostics — so for ML-heavy
work it is reasonable to execute in Python (scikit-learn) even when the rest of
the pipeline is in R; the R-side interpretation/fairness tooling (iml,
fairmodels, vip) is covered in the `tidymodels` skill.

| Stata | R (tidymodels) |
|-------|----------------|
| `lasso linear y x1-x20` | `linear_reg(penalty, mixture = 1) \|> set_engine("glmnet")` |
| `rf y x1-x20` (via H2O) | `rand_forest() \|> set_engine("ranger")` |
| No equivalent | `recipe() \|> step_normalize() \|> step_dummy()` |
| No equivalent | `tune_grid()` for hyperparameter search |
| `pca x1 x2 x3` | `prcomp(X, scale. = TRUE)` or tidymodels recipe step |
| `cluster kmeans` | `kmeans(X, centers = k)` |

```r
library(tidymodels)

# Preprocessing + model pipeline
rec <- recipe(y ~ ., data = train) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())

spec <- rand_forest(trees = 500) |>
  set_engine("ranger") |>
  set_mode("regression")

wf <- workflow() |> add_recipe(rec) |> add_model(spec)
fit <- wf |> fit(data = train)
```
