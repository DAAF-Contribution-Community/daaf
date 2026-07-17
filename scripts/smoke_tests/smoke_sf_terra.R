# smoke_sf_terra.R -- Smoke test for sf, terra, spdep, spatialreg, leaflet, classInt
# Validates: sf vector ops, terra raster ops, CRS handling, spatial joins,
#            geometry ops, ggplot2+geom_sf(), spdep spatial stats, leaflet, classInt
# All tests use synthetic data (no external files needed).

# --- Config ---
library(sf)
library(terra)
library(spdep)
library(spatialreg)
library(leaflet)
library(classInt)
library(ggplot2)

cat("=== sf-terra Smoke Test ===\n\n")

# --- Test 1: Version checks ---
cat("Test 1: Version checks\n")
sf_ver <- as.character(packageVersion("sf"))
terra_ver <- as.character(packageVersion("terra"))
spdep_ver <- as.character(packageVersion("spdep"))
spatialreg_ver <- as.character(packageVersion("spatialreg"))
leaflet_ver <- as.character(packageVersion("leaflet"))
classint_ver <- as.character(packageVersion("classInt"))

cat("  sf:", sf_ver, "\n")
cat("  terra:", terra_ver, "\n")
cat("  spdep:", spdep_ver, "\n")
cat("  spatialreg:", spatialreg_ver, "\n")
cat("  leaflet:", leaflet_ver, "\n")
cat("  classInt:", classint_ver, "\n")

stopifnot(numeric_version(sf_ver) >= "1.0.0")
stopifnot(numeric_version(terra_ver) >= "1.7.0")
stopifnot(numeric_version(spdep_ver) >= "1.3.0")
cat("  PASS: All versions meet minimum requirements\n\n")

# --- Test 2: st_read() / st_write() vector I/O ---
cat("Test 2: st_read() / st_write() vector I/O\n")
# Create synthetic polygon data (4 squares forming a 2x2 grid)
polys <- st_sf(
  id = 1:4,
  name = c("NW", "NE", "SW", "SE"),
  value = c(10, 20, 30, 40),
  geometry = st_sfc(
    st_polygon(list(matrix(c(0,0, 1,0, 1,1, 0,1, 0,0), ncol = 2, byrow = TRUE))),
    st_polygon(list(matrix(c(1,0, 2,0, 2,1, 1,1, 1,0), ncol = 2, byrow = TRUE))),
    st_polygon(list(matrix(c(0,1, 1,1, 1,2, 0,2, 0,1), ncol = 2, byrow = TRUE))),
    st_polygon(list(matrix(c(1,1, 2,1, 2,2, 1,2, 1,1), ncol = 2, byrow = TRUE)))
  ),
  crs = 4326
)

tmp_gpkg <- tempfile(fileext = ".gpkg")
st_write(polys, tmp_gpkg, quiet = TRUE)
polys_read <- st_read(tmp_gpkg, quiet = TRUE)
stopifnot(nrow(polys_read) == 4)
stopifnot(inherits(polys_read, "sf"))
stopifnot(!is.na(st_crs(polys_read)$epsg))
file.remove(tmp_gpkg)
cat("  PASS\n\n")

# --- Test 3: st_transform() CRS reprojection ---
cat("Test 3: st_transform() CRS reprojection\n")
polys_proj <- st_transform(polys, crs = 5070)
stopifnot(st_crs(polys_proj)$epsg == 5070)
stopifnot(!st_is_longlat(polys_proj))
# Verify coordinates changed
bbox_orig <- st_bbox(polys)
bbox_proj <- st_bbox(polys_proj)
stopifnot(bbox_proj["xmin"] != bbox_orig["xmin"])
cat("  Original CRS: EPSG:", st_crs(polys)$epsg, "\n")
cat("  Projected CRS: EPSG:", st_crs(polys_proj)$epsg, "\n")
cat("  PASS\n\n")

# --- Test 4: st_join() spatial join ---
cat("Test 4: st_join() spatial join\n")
# Create points inside the polygons
pts <- st_sf(
  pt_id = 1:4,
  geometry = st_sfc(
    st_point(c(0.5, 0.5)),   # Inside NW
    st_point(c(1.5, 0.5)),   # Inside NE
    st_point(c(0.5, 1.5)),   # Inside SW (note: our grid has SW at top)
    st_point(c(1.5, 1.5))    # Inside SE
  ),
  crs = 4326
)

joined <- st_join(pts, polys, join = st_within)
stopifnot(nrow(joined) == 4)
stopifnot(all(!is.na(joined$name)))
cat("  Joined", nrow(joined), "points to polygons\n")
cat("  PASS\n\n")

# --- Test 5: st_buffer() + st_intersection() geometry ops ---
cat("Test 5: st_buffer() + st_intersection() geometry ops\n")
# Buffer a point by a small amount
pt_center <- st_sf(
  geometry = st_sfc(st_point(c(1, 1)), crs = 4326)
)
pt_proj <- st_transform(pt_center, 5070)
buf <- st_buffer(pt_proj, dist = 50000)  # 50 km buffer
stopifnot(inherits(buf, "sf"))
stopifnot(st_geometry_type(buf) == "POLYGON")

# Intersection of buffer with projected polygons
polys_proj2 <- st_transform(polys, 5070)
isect <- st_intersection(polys_proj2, buf)
stopifnot(nrow(isect) > 0)
cat("  Buffer created:", round(as.numeric(st_area(buf)) / 1e6, 0), "km2\n")
cat("  Intersection produced:", nrow(isect), "features\n")
cat("  PASS\n\n")

# --- Test 6: terra::rast() + basic operations ---
cat("Test 6: terra::rast() + basic operations\n")
r <- rast(nrows = 10, ncols = 10,
          xmin = 0, xmax = 2, ymin = 0, ymax = 2,
          crs = "EPSG:4326")
values(r) <- runif(ncell(r), 0, 100)
stopifnot(inherits(r, "SpatRaster"))
stopifnot(ncell(r) == 100)

# Raster arithmetic
r2 <- r * 2 + 10
stopifnot(all(values(r2) >= 10))

# Extract at points
pts_vect <- vect(pts)
vals <- extract(r, pts_vect)
stopifnot(nrow(vals) == 4)
stopifnot(ncol(vals) == 2)  # ID + value

cat("  Raster:", nrow(r), "x", ncol(r), "cells\n")
cat("  Global mean:", round(global(r, "mean", na.rm = TRUE)[[1]], 1), "\n")
cat("  PASS\n\n")

# --- Test 7: ggplot() + geom_sf() static map ---
cat("Test 7: ggplot() + geom_sf() static map\n")
tmp_map <- tempfile(fileext = ".png")
p <- ggplot(polys) +
  geom_sf(aes(fill = value), color = "white", linewidth = 0.5) +
  geom_sf(data = pts, color = "red", size = 3) +
  scale_fill_viridis_c() +
  labs(title = "sf-terra Smoke Test Map") +
  theme_void()
ggsave(tmp_map, p, width = 6, height = 6, dpi = 100)
stopifnot(file.exists(tmp_map))
stopifnot(file.info(tmp_map)$size > 0)
file.remove(tmp_map)
cat("  PASS\n\n")

# --- Test 8: spdep::poly2nb() + moran.test() spatial autocorrelation ---
cat("Test 8: spdep::poly2nb() + moran.test()\n")
nb <- poly2nb(polys, queen = TRUE)
stopifnot(inherits(nb, "nb"))
stopifnot(length(nb) == 4)

listw <- nb2listw(nb, style = "W")
# Use a spatially correlated variable for a meaningful test
polys$spatial_var <- c(10, 12, 11, 13)  # Slightly correlated neighbors
mt <- moran.test(polys$spatial_var, listw)
stopifnot(inherits(mt, "htest"))
cat("  Neighbors created:", length(nb), "features\n")
cat("  Moran's I:", round(mt$estimate["Moran I statistic"], 4), "\n")
cat("  p-value:", round(mt$p.value, 4), "\n")
cat("  PASS\n\n")

# --- Test 9: leaflet() + addPolygons() interactive map ---
cat("Test 9: leaflet() + addPolygons() interactive map\n")
m <- leaflet(polys) |>
  addTiles() |>
  addPolygons(
    fillColor = "steelblue",
    fillOpacity = 0.5,
    color = "white",
    weight = 1,
    popup = ~paste0("ID: ", id, "<br>Value: ", value)
  ) |>
  addCircleMarkers(
    data = pts,
    radius = 5,
    color = "red",
    fillOpacity = 0.8
  )
stopifnot(inherits(m, "leaflet"))

# Save to HTML to verify it works end-to-end
tmp_html <- tempfile(fileext = ".html")
htmlwidgets::saveWidget(m, file = tmp_html, selfcontained = FALSE)
stopifnot(file.exists(tmp_html))
stopifnot(file.info(tmp_html)$size > 0)
unlink(tmp_html)
unlink(sub("\\.html$", "_files", tmp_html), recursive = TRUE)
cat("  Leaflet map created and saved successfully\n")
cat("  PASS\n\n")

# --- Test 10: classInt::classIntervals() classification ---
cat("Test 10: classInt::classIntervals() classification\n")
set.seed(42)
test_data <- c(rnorm(50, mean = 20, sd = 5), rnorm(50, mean = 50, sd = 10))

# Fisher-Jenks
brks_fisher <- classIntervals(test_data, n = 5, style = "fisher")
stopifnot(inherits(brks_fisher, "classIntervals"))
stopifnot(length(brks_fisher$brks) == 6)  # 5 classes -> 6 break points

# Quantile
brks_quant <- classIntervals(test_data, n = 5, style = "quantile")
stopifnot(length(brks_quant$brks) == 6)

cat("  Fisher-Jenks breaks:", paste(round(brks_fisher$brks, 1), collapse = ", "), "\n")
cat("  Quantile breaks:", paste(round(brks_quant$brks, 1), collapse = ", "), "\n")
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 10 tests PASSED ===\n")
cat("Tested: sf", sf_ver, "/ terra", terra_ver, "/ spdep", spdep_ver, "\n")
cat("        spatialreg", spatialreg_ver, "/ leaflet", leaflet_ver,
    "/ classInt", classint_ver, "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-10 15:57:49
# Command: Rscript /daaf/scripts/smoke_tests/smoke_sf_terra.R
# Duration: 3s
# Exit code: 0
#
# --- STDOUT ---
# Linking to GEOS 3.11.1, GDAL 3.6.2, PROJ 9.1.1; sf_use_s2() is TRUE
# terra 1.9.11
# Loading required package: spData
# To access larger datasets in this package, install the spDataLarge
# package with: `install.packages('spDataLarge',
# repos='https://nowosad.github.io/drat/', type='source')`
# Loading required package: Matrix
# 
# Attaching package: ‘spatialreg’
# 
# The following objects are masked from ‘package:spdep’:
# 
#     get.ClusterOption, get.coresOption, get.mcOption,
#     get.VerboseOption, get.ZeroPolicyOption, set.ClusterOption,
#     set.coresOption, set.mcOption, set.VerboseOption,
#     set.ZeroPolicyOption
# 
# === sf-terra Smoke Test ===
# 
# Test 1: Version checks
#   sf: 1.1.0 
#   terra: 1.9.11 
#   spdep: 1.4.2 
#   spatialreg: 1.4.3 
#   leaflet: 2.2.3 
#   classInt: 0.4.11 
#   PASS: All versions meet minimum requirements
# 
# Test 2: st_read() / st_write() vector I/O
# [1] TRUE
#   PASS
# 
# Test 3: st_transform() CRS reprojection
#   Original CRS: EPSG: 4326 
#   Projected CRS: EPSG: 5070 
#   PASS
# 
# Test 4: st_join() spatial join
#   Joined 4 points to polygons
#   PASS
# 
# Test 5: st_buffer() + st_intersection() geometry ops
# Warning message:
# attribute variables are assumed to be spatially constant throughout all geometries 
#   Buffer created: 7850 km2
#   Intersection produced: 4 features
#   PASS
# 
# Test 6: terra::rast() + basic operations
#   Raster: 10 x 10 cells
#   Global mean: 53 
#   PASS
# 
# Test 7: ggplot() + geom_sf() static map
# [1] TRUE
#   PASS
# 
# Test 8: spdep::poly2nb() + moran.test()
#   Neighbors created: 4 features
#   Moran's I: -0.3333 
#   p-value: 0.5 
#   PASS
# 
# Test 9: leaflet() + addPolygons() interactive map
#   Leaflet map created and saved successfully
#   PASS
# 
# Test 10: classInt::classIntervals() classification
#   Fisher-Jenks breaks: 6.7, 20.6, 33.4, 45.8, 55.2, 65.8 
#   Quantile breaks: 6.7, 18.6, 23.7, 41.7, 54.9, 65.8 
#   PASS
# 
# === All 10 tests PASSED ===
# Tested: sf 1.1.0 / terra 1.9.11 / spdep 1.4.2 
#         spatialreg 1.4.3 / leaflet 2.2.3 / classInt 0.4.11 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
