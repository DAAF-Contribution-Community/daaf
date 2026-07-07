# Common Gotchas and Troubleshooting

Frequent issues when working with sf, terra, and the R spatial stack -- symptoms, causes, and fixes.

---

## s2 Geometry Engine (Spherical Geometry)

### The Issue

Since sf 1.0, the s2 spherical geometry engine is enabled by default for geographic CRS (EPSG:4326). This means spatial operations use geodesic (great-circle) geometry on the sphere rather than planar (Euclidean) geometry. This is mathematically correct but changes behavior from earlier sf versions and can cause unexpected errors or results.

### Common s2 Errors

```
Error in s2_geography_from_wkb(): Edges must have at most 180 degrees.
```

This happens when polygons have edges longer than 180 degrees of longitude (often from anti-meridian crossing or large-extent polygons).

```
Error in s2_intersects(): Loop is not valid...
```

This happens when polygon rings have self-intersections or incorrect winding order under s2 rules.

### Fix: Disable s2 When Needed

```r
# Temporarily disable s2 for problematic operations
sf_use_s2(FALSE)
result <- st_intersection(x, y)  # Uses planar GEOS instead
sf_use_s2(TRUE)                  # Re-enable

# Or wrap in a function
with_s2_off <- function(expr) {
  old <- sf_use_s2(FALSE)
  on.exit(sf_use_s2(old))
  eval(expr)
}
```

### When s2 Matters

| Scenario | s2 ON (default) | s2 OFF |
|----------|----------------|--------|
| Area of polygons in EPSG:4326 | Correct (geodesic m^2) | Wrong (square degrees) |
| Distance between points in 4326 | Correct (meters) | Wrong (degrees) |
| Buffer in geographic CRS | May error | Works but wrong shape |
| Intersection of complex polygons | May error on invalid rings | More permissive |

**Best practice:** Work in a projected CRS (e.g., EPSG:5070) for geometric operations. This avoids s2 issues entirely because s2 only activates for geographic CRS.

---

## CRS Mismatch Errors

### Symptom

```
Error: st_crs(x) != st_crs(y)
```

### Cause

Spatial operations (join, intersection, distance) require all inputs in the same CRS. This error fires when CRS differs between objects.

### Fix

```r
# Check CRS of both inputs
st_crs(x)
st_crs(y)

# Reproject one to match the other
y <- st_transform(y, crs = st_crs(x))

# Now the spatial operation works
result <- st_join(x, y)
```

### Prevention

Reproject all inputs to a common CRS at the start of the script:

```r
TARGET_CRS <- 5070
x <- st_transform(x, TARGET_CRS)
y <- st_transform(y, TARGET_CRS)
```

---

## Geometry Column Persistence

### Symptom

After a dplyr operation, the geometry column disappears or the result is a plain data.frame instead of sf.

### Cause

Most dplyr verbs preserve the sf class and geometry column automatically. However, some operations can drop it:

- `select()` that excludes the geometry column
- `as.data.frame()` or `as_tibble()` conversions
- `pull()` extracts a vector, not an sf object
- Operations on columns without touching geometry

### Fix

```r
# select() automatically includes geometry even if not listed
# But if you explicitly exclude it:
result <- x |> select(-geometry)  # Now a plain data.frame

# To explicitly keep geometry:
result <- x |> select(name, population)  # geometry is auto-included

# If geometry was lost, re-attach it:
result_sf <- st_as_sf(result, sf_column_name = "geometry")

# Or use st_drop_geometry() intentionally when you want a plain data.frame:
df <- st_drop_geometry(x)
```

### group_by + summarize Preserves Geometry

```r
# This works correctly -- geometries are unioned per group
states <- counties |>
  group_by(state_fips) |>
  summarize(total_pop = sum(population))
# Result is sf with unioned geometries per state
```

---

## Invalid Geometries

### Symptom

- Overlay or spatial join returns empty or unexpected results
- Error: `TopologyException` or `ParseException`
- Unexpected geometry fragments after intersection

### Detection

```r
# Check which geometries are invalid
invalid_mask <- !st_is_valid(x)
cat("Invalid geometries:", sum(invalid_mask), "/", nrow(x), "\n")

# Get reasons for invalidity
if (any(invalid_mask)) {
  reasons <- st_is_valid(x, reason = TRUE)
  print(table(reasons[invalid_mask]))
}
```

### Fix

```r
# st_make_valid() -- preferred fix (built into sf 1.x)
x <- st_make_valid(x)
stopifnot(all(st_is_valid(x)))

# Buffer by zero -- classic approach (less predictable)
x$geometry <- st_buffer(x$geometry, 0)
```

### When to Validate

- Before any overlay or intersection operation
- Before spatial joins with `st_within` or `st_contains`
- After reading Shapefiles (the format is prone to validity issues)
- After simplification (`st_simplify`)
- After reprojection of complex geometries

---

## Coordinate Order Confusion (lon/lat vs lat/lon)

### The Problem

- **GIS/math convention:** x = longitude, y = latitude --> `c(lon, lat)` = `c(-77.036, 38.901)`
- **Everyday convention:** "latitude and longitude" --> people say `c(38.901, -77.036)`
- **Google Maps URLs:** `@38.901,-77.036` (lat, lon)

### Symptoms of Getting It Wrong

- Points plot in the ocean or wrong hemisphere
- Spatial joins return zero matches
- Data appears reflected across the equator or prime meridian

### How sf Expects Coordinates

```r
# coords = c("x_column", "y_column") = c("longitude", "latitude")
pts <- st_as_sf(df, coords = c("lon", "lat"), crs = 4326)

# st_point takes c(x, y) = c(lon, lat)
pt <- st_point(c(-77.009, 38.890))
```

### Quick Diagnostic

```r
# Check bounding box
st_bbox(x)
# Expected for US data: xmin ~ -125, ymin ~ 24, xmax ~ -66, ymax ~ 50
# If you see xmin ~ 24, the coordinates are swapped

# Fix: swap x and y
x$geometry <- st_sfc(
  lapply(st_geometry(x), function(g) {
    coords <- st_coordinates(g)
    st_point(c(coords[2], coords[1]))
  }),
  crs = st_crs(x)
)
```

---

## Memory Issues with Large Spatial Data

### Symptoms

- R session crashes or runs out of memory
- Operations are extremely slow

### Fixes

```r
# 1. Read only needed columns (via SQL query)
x <- st_read("large.gpkg",
             query = "SELECT name, geom FROM layer WHERE state = 'MD'")

# 2. Read only a geographic subset
x <- st_read("large.gpkg",
             wkt_filter = "POLYGON ((-78 38, -76 38, -76 40, -78 40, -78 38))")

# 3. Simplify geometries to reduce memory
x <- st_simplify(x, preserveTopology = TRUE, dTolerance = 100)

# 4. Use terra for large rasters (processes on disk, not in memory)
r <- rast("huge_raster.tif")  # Does NOT load all data into memory

# 5. Process in chunks
chunks <- split(seq_len(nrow(large_sf)), ceiling(seq_len(nrow(large_sf)) / 1000))
results <- lapply(chunks, function(idx) {
  st_intersection(large_sf[idx, ], clip_boundary)
})
result <- do.call(rbind, results)
```

---

## sp/rgdal/rgeos Migration

### The Situation

The `sp`, `rgdal`, and `rgeos` packages were retired in October 2023. All code using them should migrate to `sf` (vector) and `terra` (raster).

### Common Migrations

| Old (sp/rgdal/rgeos) | New (sf/terra) |
|---------------------|----------------|
| `readOGR()` | `st_read()` |
| `writeOGR()` | `st_write()` |
| `spTransform()` | `st_transform()` |
| `gBuffer()` | `st_buffer()` |
| `gIntersection()` | `st_intersection()` |
| `gUnion()` / `gUnaryUnion()` | `st_union()` |
| `over()` | `st_join()` or `st_intersection()` |
| `SpatialPointsDataFrame()` | `st_as_sf(df, coords = ...)` |
| `raster::raster()` | `terra::rast()` |
| `raster::extract()` | `terra::extract()` |
| `raster::crop()` | `terra::crop()` |
| `raster::mask()` | `terra::mask()` |
| `raster::stack()` | `c(r1, r2, r3)` with terra |

### Converting Between sp and sf

```r
# sp -> sf
sf_obj <- st_as_sf(sp_obj)

# sf -> sp (only if needed for legacy package compatibility)
sp_obj <- as(sf_obj, "Spatial")
```

---

## terra and sf Interoperability

terra uses its own `SpatVector` class rather than sf objects. Converting between them:

```r
library(terra)
library(sf)

# sf -> SpatVector (for terra functions)
v <- vect(sf_obj)

# SpatVector -> sf (for sf/dplyr/ggplot2 functions)
sf_obj <- st_as_sf(v)

# Common pattern: convert just for terra::extract(), then use sf for everything else
vals <- extract(raster, vect(points_sf))
points_sf$raster_value <- vals[, 2]
```

---

## References and Further Reading

sf migration guide. https://r-spatial.org/r/2023/05/15/evolution4.html

Pebesma, E. and Bivand, R. (2023). *Spatial Data Science*. https://r-spatial.org/book/

sf FAQ. https://r-spatial.github.io/sf/articles/sf7.html
