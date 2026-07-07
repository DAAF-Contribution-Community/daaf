# Spatial Statistics with spdep and spatialreg

Spatial weights, autocorrelation tests, LISA local indicators, and spatial regression models using spdep and spatialreg. These are the R counterparts to Python's PySAL ecosystem (libpysal, esda, spreg). For methodology and interpretation guidance, see the `data-scientist` skill's `geospatial-analysis.md`.

---

## Spatial Weights

Spatial weights formalize the concept of "neighbor" -- they define which observations are connected and how strongly. Every spatial statistic depends on this choice.

### Contiguity Weights (Polygons)

```r
library(spdep)

# Queen contiguity: neighbors share an edge or vertex
nb_queen <- poly2nb(counties, queen = TRUE)

# Rook contiguity: neighbors share an edge only (stricter)
nb_rook <- poly2nb(counties, queen = FALSE)

# Inspect
summary(nb_queen)
card(nb_queen)                   # Number of neighbors per observation
nb_queen[[1]]                    # Neighbors of first observation
```

### Distance-Based Weights (Points or Polygons)

```r
# First get centroid coordinates
coords <- st_coordinates(st_centroid(counties))

# K-Nearest Neighbors
nb_knn <- knearneigh(coords, k = 6) |> knn2nb()

# Distance band (all neighbors within threshold)
nb_dist <- dnearneigh(coords, d1 = 0, d2 = 50000)  # 0-50 km (projected CRS!)

# Critical: distance-based weights require a projected CRS (meters).
# Geographic CRS (degrees) produces meaningless distances.
```

### Converting nb to listw (Weights List)

Most spdep/spatialreg functions require a `listw` object, not raw `nb`:

```r
# Row-standardized weights (W-style): each row sums to 1
# This is the most common choice -- spatial lag becomes a weighted average
listw_W <- nb2listw(nb_queen, style = "W")

# Binary weights (B-style): neighbors = 1, non-neighbors = 0
listw_B <- nb2listw(nb_queen, style = "B")

# Handling islands (observations with zero neighbors):
# zero.policy = TRUE allows them (coded as 0 in spatial lag)
listw_W <- nb2listw(nb_queen, style = "W", zero.policy = TRUE)
```

### Weight Styles

| Style | Meaning | Row Sum | Common Use |
|-------|---------|---------|------------|
| `"W"` | Row-standardized | 1 | Most analyses (default) |
| `"B"` | Binary | Variable | Raw neighbor counts |
| `"C"` | Globally standardized | Variable | Comparable across datasets |
| `"S"` | Variance-stabilizing | Variable | Heterogeneous neighbor counts |

---

## Global Spatial Autocorrelation

### Moran's I

Tests whether a variable is spatially clustered (positive I), dispersed (negative I), or random (I ~ 0).

```r
# Moran's I test (permutation-based)
moran_result <- moran.test(counties$poverty_rate, listw_W)
print(moran_result)

# Key outputs:
# - Moran I statistic: the I value
# - p-value: significance of spatial autocorrelation
# - Expectation: expected I under no spatial autocorrelation

# Monte Carlo permutation test (more robust than analytical)
moran_mc <- moran.mc(counties$poverty_rate, listw_W, nsim = 999)
print(moran_mc)
cat("Moran's I:", moran_mc$statistic, "\n")
cat("p-value:", moran_mc$p.value, "\n")
```

### Moran Scatter Plot

```r
# Moran scatter plot: variable vs spatial lag
mp <- moran.plot(counties$poverty_rate, listw_W,
                 labels = counties$name,
                 xlab = "Poverty Rate",
                 ylab = "Spatial Lag of Poverty Rate",
                 main = "Moran Scatter Plot")
```

### Geary's C

Complementary to Moran's I -- more sensitive to local differences:

```r
geary_result <- geary.test(counties$poverty_rate, listw_W)
print(geary_result)
# C < 1: positive autocorrelation
# C > 1: negative autocorrelation
# C = 1: no autocorrelation
```

---

## Local Spatial Autocorrelation (LISA)

### Local Moran's I

Identifies local clusters and outliers -- where spatial autocorrelation is strongest.

```r
# Compute local Moran's I
lisa <- localmoran(counties$poverty_rate, listw_W)

# lisa is a matrix with columns:
# Ii      = local Moran's I
# E.Ii    = expected value
# Var.Ii  = variance
# Z.Ii    = z-score
# Pr(z != E(Ii)) = p-value (two-sided)

# Attach results to sf object
counties$lisa_I <- lisa[, "Ii"]
counties$lisa_z <- lisa[, "Z.Ii"]
counties$lisa_p <- lisa[, "Pr(z != E(Ii))"]
```

### LISA Quadrant Classification

```r
# Classify into HH, LL, HL, LH quadrants
x <- scale(counties$poverty_rate)[, 1]         # Standardized variable
lag_x <- lag.listw(listw_W, counties$poverty_rate)  # Spatial lag
lag_x_std <- scale(lag_x)[, 1]                 # Standardized lag

counties$lisa_quad <- NA_character_
counties$lisa_quad[x > 0 & lag_x_std > 0] <- "HH"  # Hot spot
counties$lisa_quad[x < 0 & lag_x_std < 0] <- "LL"  # Cold spot
counties$lisa_quad[x > 0 & lag_x_std < 0] <- "HL"  # High-Low outlier
counties$lisa_quad[x < 0 & lag_x_std > 0] <- "LH"  # Low-High outlier

# Only show significant clusters
counties$lisa_cluster <- ifelse(
  counties$lisa_p < 0.05,
  counties$lisa_quad,
  "Not Significant"
)
```

### LISA Quadrants

| Quadrant | Code | Meaning | Interpretation |
|----------|------|---------|----------------|
| HH | High-High | Hot spot | High value surrounded by high values |
| LH | Low-High | Spatial outlier | Low value surrounded by high values |
| LL | Low-Low | Cold spot | Low value surrounded by low values |
| HL | High-Low | Spatial outlier | High value surrounded by low values |

### LISA Cluster Map

```r
library(ggplot2)

lisa_colors <- c(
  "HH" = "#d7191c",
  "LL" = "#2c7bb6",
  "HL" = "#fdae61",
  "LH" = "#abd9e9",
  "Not Significant" = "#f0f0f0"
)

ggplot(counties) +
  geom_sf(aes(fill = lisa_cluster), color = "white", linewidth = 0.2) +
  scale_fill_manual(values = lisa_colors, name = "LISA Cluster") +
  labs(title = "LISA Cluster Map: Poverty Rate") +
  theme_void()
```

---

## Spatial Regression

spatialreg provides spatial regression models. Start with OLS + LM diagnostics to determine which spatial model (if any) is needed.

### OLS with Spatial Diagnostics

```r
library(spatialreg)

# OLS regression
ols <- lm(poverty_rate ~ median_income + pct_rural, data = counties)

# Rao's score (formerly "Lagrange Multiplier") tests for spatial dependence.
# spdep >= 1.3-2 renamed lm.LMtests() to lm.RStests() and the test tokens
# from LM*/RLM* to RS*/adjRS* (installed spdep is 1.4.2).
rs_tests <- lm.RStests(ols, listw_W,
                       test = c("RSerr", "RSlag", "adjRSerr", "adjRSlag", "SARMA"))
print(rs_tests)

# Decision rule:
# RSlag significant, RSerr not -> Spatial Lag Model (SAR)
# RSerr significant, RSlag not -> Spatial Error Model (SEM)
# Both significant -> Check adjusted (robust) versions (adjRSlag, adjRSerr)
# Neither significant -> OLS is fine
```

### Spatial Lag Model (SAR / SLM)

The outcome is influenced by neighbors' outcomes (Wy):

```r
# Maximum Likelihood
sar <- lagsarlm(poverty_rate ~ median_income + pct_rural,
                data = counties, listw = listw_W)
summary(sar)
# Key output: rho (spatial autoregressive coefficient), coefficients, log-likelihood

# Impact decomposition (direct, indirect, total effects)
impacts(sar, listw = listw_W)
```

### Spatial Error Model (SEM)

Spatial dependence is in the error term:

```r
sem <- errorsarlm(poverty_rate ~ median_income + pct_rural,
                  data = counties, listw = listw_W)
summary(sem)
# Key output: lambda (spatial error coefficient), coefficients
```

### Spatial Durbin Model (SDM)

Includes both spatial lag of Y and spatial lags of X (most flexible):

```r
sdm <- lagsarlm(poverty_rate ~ median_income + pct_rural,
                data = counties, listw = listw_W, type = "mixed")
summary(sdm)

# Impact decomposition is especially important for SDM
impacts(sdm, listw = listw_W)
```

### Model Comparison

```r
# Compare models via AIC / log-likelihood
AIC(ols)
AIC(sar)
AIC(sem)
AIC(sdm)

# LR test for nested models
LR.Sarlm(sar, ols)   # SAR vs OLS
LR.Sarlm(sem, ols)   # SEM vs OLS
```

### Residual Diagnostics

After fitting a spatial model, verify that residuals no longer exhibit spatial autocorrelation:

```r
moran.test(residuals(sar), listw_W)
# p > 0.05 indicates spatial dependence has been adequately modeled
```

---

## References and Further Reading

Bivand, R.S., Pebesma, E., and Gomez-Rubio, V. (2013). *Applied Spatial Data Analysis with R* (2nd ed.). Springer.

Bivand, R.S. and Wong, D.W.S. (2018). "Comparing Implementations of Global and Local Indicators of Spatial Association." *TEST*, 27(3), 716-748.

Anselin, L. (1995). "Local Indicators of Spatial Association -- LISA." *Geographical Analysis*, 27(2), 93-115.

spdep documentation. https://r-spatial.github.io/spdep/

spatialreg documentation. https://r-spatial.github.io/spatialreg/
