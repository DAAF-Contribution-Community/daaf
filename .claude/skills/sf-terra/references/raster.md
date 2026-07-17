# Raster Data with terra

Working with raster data using terra (SpatRaster objects) and stars (spatiotemporal arrays). Covers reading, writing, raster arithmetic, raster-vector interaction, and conversion.

---

## terra Basics

terra is the modern R raster package, replacing the retired `raster` package. It uses SpatRaster objects backed by C++ for performance and memory efficiency.

### Reading a Raster

```r
library(terra)

r <- rast("elevation.tif")

# Inspect
print(r)              # Summary: dimensions, resolution, extent, CRS
crs(r)                # CRS
ext(r)                # Extent (xmin, xmax, ymin, ymax)
res(r)                # Resolution (pixel width, height)
dim(r)                # Dimensions (nrow, ncol, nlyr)
nlyr(r)               # Number of layers/bands
names(r)              # Layer names
minmax(r)             # Min/max values
ncell(r)              # Total number of cells
hasValues(r)          # Does the raster have values loaded?
```

### Reading a Subset

```r
# Read only a geographic extent
e <- ext(-78, -76, 38, 40)  # xmin, xmax, ymin, ymax
r_sub <- crop(rast("large_raster.tif"), e)

# Read specific bands
r_b1 <- rast("multi_band.tif", lyrs = 1)
```

### Creating Rasters from Scratch

```r
# Empty raster with defined extent and resolution
r <- rast(nrows = 100, ncols = 100,
          xmin = -78, xmax = -76, ymin = 38, ymax = 40,
          crs = "EPSG:4326")

# Fill with values
values(r) <- runif(ncell(r))

# From a matrix
m <- matrix(1:100, nrow = 10, ncol = 10)
r <- rast(m, ext = ext(-78, -76, 38, 40), crs = "EPSG:4326")

# Multi-layer raster
r_multi <- c(r1, r2, r3)  # Stack layers
```

### Writing Rasters

```r
# GeoTIFF (default and recommended)
writeRaster(r, "output.tif", overwrite = TRUE)

# With compression and internal tiling (the GTiff option is TILED=YES;
# "TILEDB" is a different GDAL driver — GDAL warns "driver GTiff does not
# support creation option TILEDB" and ignores it, verified)
writeRaster(r, "output.tif", overwrite = TRUE,
            gdal = c("COMPRESS=LZW", "TILED=YES"))

# NetCDF
writeRaster(r, "output.nc", overwrite = TRUE)
```

---

## Raster Arithmetic

terra supports element-wise operations directly on SpatRaster objects:

```r
# Basic arithmetic
r2 <- r * 2
r3 <- r1 + r2
r4 <- r1 / r2
r5 <- sqrt(r)
r6 <- log(r + 1)

# Logical operations
mask <- r > 100
r_masked <- ifel(r > 100, r, NA)  # Conditional: if-else

# Summary statistics
global(r, fun = "mean", na.rm = TRUE)     # Global mean
global(r, fun = "sum", na.rm = TRUE)      # Global sum
global(r, fun = c("min", "max", "mean", "sd"), na.rm = TRUE)

# Cell-level statistics across layers
r_mean <- app(r_multi, fun = "mean")      # Mean across layers
r_sum <- app(r_multi, fun = "sum")        # Sum across layers
r_custom <- app(r_multi, fun = function(x) x[1] - x[2])  # Custom function
```

### Focal (Neighborhood) Operations

```r
# Moving window operations
r_smooth <- focal(r, w = 3, fun = "mean")     # 3x3 mean filter
r_sum3 <- focal(r, w = 3, fun = "sum")        # 3x3 sum
r_sd <- focal(r, w = 5, fun = "sd")           # 5x5 std dev

# Custom window shape (e.g., circular)
w <- focalMat(r, d = 1000, type = "circle")   # 1000m radius circle
r_focal <- focal(r, w = w, fun = "mean")
```

### Reclassify

```r
# Reclassify raster values
# Matrix format: from, to, new_value
rcl <- matrix(c(
  0,   50,  1,   # 0-50 -> 1
  50,  100, 2,   # 50-100 -> 2
  100, 200, 3    # 100-200 -> 3
), ncol = 3, byrow = TRUE)

r_class <- classify(r, rcl)
```

### Aggregate and Disaggregate

```r
# Reduce resolution (aggregate cells)
r_coarse <- aggregate(r, fact = 4, fun = "mean")  # 4x reduction

# Increase resolution (disaggregate cells)
r_fine <- disagg(r, fact = 2)  # 2x increase (interpolation options available)

# Resample to match another raster's grid
r_resampled <- resample(r, template_raster, method = "bilinear")
```

---

## Raster-Vector Interaction

### Extract Values at Points/Polygons

```r
library(sf)
library(terra)

# Convert sf to terra's SpatVector format
pts_vect <- vect(pts_sf)

# Extract raster values at point locations
vals <- extract(r, pts_vect)
# Returns: data.frame with ID column + raster values

# Attach back to sf object
pts_sf$elevation <- vals[, 2]  # Column 2 is the raster value

# Extract and summarize within polygons
poly_vals <- extract(r, vect(polygons_sf), fun = "mean", na.rm = TRUE)
polygons_sf$mean_elev <- poly_vals[, 2]
```

### Crop and Mask

```r
# Crop: trim raster to extent of vector features
r_cropped <- crop(r, vect(study_area_sf))

# Mask: set cells outside polygons to NA
r_masked <- mask(r, vect(study_area_sf))

# Crop + mask together (most common pattern)
r_clipped <- crop(r, vect(study_area_sf)) |>
  mask(vect(study_area_sf))
```

### Rasterize (Vector to Raster)

```r
# Burn polygon values into a raster grid
r_template <- rast(ext(polygons_sf), res = 100, crs = st_crs(polygons_sf)$wkt)
r_burned <- rasterize(vect(polygons_sf), r_template, field = "population")
```

### Vectorize (Raster to Vector)

```r
# Convert raster cells to polygons
polys <- as.polygons(r_class)
polys_sf <- st_as_sf(polys)

# Convert raster cells to points
pts <- as.points(r)
pts_sf <- st_as_sf(pts)
```

---

## CRS Operations with terra

```r
# Check CRS
crs(r)
crs(r, describe = TRUE)  # Structured CRS info

# Reproject raster
r_proj <- project(r, "EPSG:5070", method = "bilinear")

# Set CRS (declare, not transform)
crs(r) <- "EPSG:4326"

# Match CRS between raster and sf
if (st_crs(sf_obj)$wkt != crs(r)) {
  sf_obj <- st_transform(sf_obj, crs = crs(r))
}
```

---

## stars: Spatiotemporal Arrays

stars extends raster data to named dimensions (time, band, depth). Use when working with time series rasters, NetCDF, or multi-dimensional data.

```r
library(stars)

# Read a GeoTIFF
s <- read_stars("temperature.tif")

# Read NetCDF with time dimension
s <- read_stars("climate.nc")

# Inspect
print(s)
st_dimensions(s)   # Dimension information
st_crs(s)          # CRS

# Subset by dimension
s_jan <- s[, , , 1]              # First time step
s_sub <- filter(s, time >= "2020-01-01" & time <= "2020-12-31")

# Convert between stars and terra
r <- as(s, "SpatRaster")        # stars -> terra
s <- st_as_stars(r)             # terra -> stars

# Convert to sf (for vector operations)
sf_obj <- st_as_sf(s, as_points = TRUE)  # Raster cells as points
```

### stars + sf Integration

```r
# Crop stars object by sf polygon
s_cropped <- s[study_area_sf]

# Aggregate by polygons (zonal statistics equivalent)
agg <- aggregate(s, by = polygons_sf, FUN = mean)
```

---

## Performance Tips

| Scenario | Approach |
|----------|----------|
| Large raster, only need subset | `crop()` before processing |
| Many extract operations | Convert sf to SpatVector once, reuse |
| Raster + large polygon set | Process in chunks with `lapply()` |
| Multi-band operations | Use `app()` instead of R loops |
| Repeated read of same raster | Keep SpatRaster object in memory |

---

## References and Further Reading

Hijmans, R.J. (2024). *terra: Spatial Data Analysis*. https://rspatial.org/

Pebesma, E. (2021). "stars: Spatiotemporal Arrays, Raster and Vector Data Cubes." https://r-spatial.github.io/stars/

Lovelace, R., Nowosad, J., and Muenchow, J. (2024). *Geocomputation with R* (2nd ed.), Chs. 6-7: "Raster data" and "Raster-vector interactions." https://r.geocompx.org/
