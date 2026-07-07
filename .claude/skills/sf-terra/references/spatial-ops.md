# Spatial Operations

Vector spatial operations in sf -- joins, overlays, dissolve, clip, buffer, distance, and geometry manipulation. For methodology guidance (when/why to use each operation), see the `data-scientist` skill's `geospatial-operations.md`.

---

## Spatial Joins

Spatial joins connect records from two sf objects based on geographic relationships rather than shared key columns.

### Basic Spatial Join

```r
# Which county contains each school? (point-in-polygon)
result <- st_join(schools, counties, join = st_within)

# Which features overlap? (most permissive -- default)
result <- st_join(x, y, join = st_intersects)

# Left join (keep all features from x, even unmatched)
result <- st_join(x, y, join = st_within, left = TRUE)

# Inner join (only matched features)
result <- st_join(x, y, join = st_within, left = FALSE)
```

### Spatial Predicates

| Predicate | Meaning | Common Use |
|-----------|---------|------------|
| `st_intersects` | Geometries share any space (default) | Broadest match |
| `st_within` | Left is entirely inside right | Points within polygons |
| `st_contains` | Left entirely encloses right | Polygons containing points |
| `st_touches` | Shared boundary, no interior overlap | Adjacency detection |
| `st_crosses` | Partial interior overlap | Lines crossing polygons |
| `st_covers` | Like contains but includes boundary | Inclusive containment |
| `st_covered_by` | Like within but includes boundary | Inclusive membership |

### Nearest-Neighbor Join

```r
# Find nearest school to each census tract centroid
result <- st_join(tracts, schools, join = st_nearest_feature)

# Note: st_nearest_feature joins do not take a distance limit.
# To limit distance, compute the nearest-feature distances via row indices
# (verified pattern -- indexing by an id column is only correct when ids
# happen to equal row positions):
nearest_idx <- st_nearest_feature(tracts, schools)
result$dist <- st_distance(tracts, schools[nearest_idx, ], by_element = TRUE)
result <- result[as.numeric(result$dist) <= 10000, ]  # 10 km max
```

`st_nearest_feature` requires both sf objects in a projected CRS for meaningful distances.

### Post-Join Validation

Spatial joins can produce unexpected row counts due to many-to-many relationships. Always validate:

```r
cat("Input rows:", nrow(schools), "\n")
cat("Result rows:", nrow(result), "\n")
cat("Duplicated indices:", sum(duplicated(result$school_id)), "\n")
cat("Null join columns:", sum(is.na(result$county_name)), "\n")

# If duplicates exist, decide how to handle:
# Option 1: Keep first match
result_dedup <- result[!duplicated(result$school_id), ]

# Option 2: Aggregate
result_agg <- result |>
  group_by(school_id) |>
  summarize(county_name = first(county_name), total_pop = sum(pop))
```

---

## Attribute Joins (Non-Spatial)

Standard dplyr joins for joining by shared columns:

```r
library(dplyr)

# Join census data to county geometries by FIPS code
counties_data <- counties |>
  left_join(census_df, by = c("GEOID" = "fips"))

# Note: left_join preserves the sf class when the left input is sf
```

---

## Overlay Operations

Overlays combine two polygon layers to produce new geometries. Unlike spatial joins (which transfer attributes), overlays create new geometries from intersections.

### Intersection

```r
# Find areas where flood zones and school districts overlap
flood_school <- st_intersection(school_districts, flood_zones)

# Compute area of overlap
flood_school$overlap_area_km2 <- as.numeric(st_area(flood_school)) / 1e6
```

### Union

```r
# Combine two polygon layers into all unique sub-areas
combined <- st_union(x, y)  # Per-feature union (returns geometry pairs)

# Union all geometries into one
merged <- st_union(x)  # Returns a single geometry
```

### Difference

```r
# Areas in x but NOT in y
diff <- st_difference(x, y)
```

### Symmetric Difference

```r
# Areas in either but NOT both
sym_diff <- st_sym_difference(x, y)
```

---

## Dissolve (Aggregate Geometries)

Dissolve merges geometries by a grouping column. In sf, this is done via dplyr's `group_by()` + `summarize()` -- the geometry column is automatically unioned within each group.

```r
library(dplyr)

# Merge counties into states (sum population, merge geometries)
states <- counties |>
  group_by(state_fips) |>
  summarize(
    total_pop = sum(population, na.rm = TRUE),
    n_counties = n()
  )

# Dissolve all features into one (no grouping)
us_boundary <- st_union(counties)
```

---

## Clipping

Clip features to a boundary -- everything outside the mask is removed.

```r
# Clip schools to a state boundary (modifies geometries)
schools_in_state <- st_intersection(schools, state_boundary)

# Crop to a bounding box (faster, axis-aligned clip)
bbox <- st_bbox(c(xmin = -78, ymin = 38, xmax = -76, ymax = 40), crs = 4326)
clipped <- st_crop(x, bbox)
```

### st_crop vs st_intersection

- **`st_crop`**: Fast axis-aligned bounding box clip; does not cut geometries precisely to irregular shapes
- **`st_intersection`**: Precise clip to any polygon boundary; slower but exact

---

## Buffering

Create a zone around features at a specified distance.

```r
# Buffer points by 1 km (CRS must be in meters)
schools_proj <- st_transform(schools, crs = 5070)
schools_buf <- st_buffer(schools_proj, dist = 1000)  # 1000 meters

# Variable-distance buffer (different distance per feature)
schools_buf <- st_buffer(schools_proj, dist = schools_proj$radius_m)

# Negative buffer (shrink polygons)
shrunk <- st_buffer(polygons_proj, dist = -100)

# Buffer parameters
st_buffer(x,
  dist = 1000,       # Distance in CRS units
  nQuadSegs = 30     # Number of segments per quarter circle (smoothness)
)
```

Buffering in a geographic CRS (degrees) triggers an s2 operation that may produce unexpected results -- always project first.

---

## Distance

```r
# Distance matrix between all features in two sf objects
dist_matrix <- st_distance(x, y)
# Returns: units matrix (nrow(x) x nrow(y))

# Element-wise distance (same number of features in both)
dists <- st_distance(x, y, by_element = TRUE)

# Distance from every feature to a single point
capitol <- st_sfc(st_point(c(-77.009, 38.890)), crs = 4326)
capitol_proj <- st_transform(capitol, 5070)
x_proj <- st_transform(x, 5070)
x$dist_to_capitol <- as.numeric(st_distance(x_proj, capitol_proj))
```

Always compute distances in a projected CRS for results in meters.

---

## Centroid and Representative Point

```r
# Centroid of each geometry
centroids <- st_centroid(x)

# Representative point (guaranteed to be inside the polygon)
# Centroid might fall outside for concave polygons
rep_pts <- st_point_on_surface(x)
```

Use `st_point_on_surface()` for irregular or concave polygons where the centroid might fall outside the geometry.

---

## Area and Length

```r
# Area (returns units object -- meters^2 for projected, or m^2 via s2 for geographic)
areas <- st_area(x)
x$area_km2 <- as.numeric(areas) / 1e6

# Ensure projected CRS for non-s2 workflows
x_proj <- st_transform(x, 5070)
x$area_km2 <- as.numeric(st_area(x_proj)) / 1e6

# Length (for LINESTRING geometries)
lengths <- st_length(x)
x$length_km <- as.numeric(lengths) / 1e3
```

---

## Geometry Manipulation

### Simplify

Reduce geometry complexity (fewer vertices):

```r
# Simplify with tolerance (in CRS units)
x_simple <- st_simplify(x, dTolerance = 100)  # 100 meters if projected

# Preserve topology (prevents gaps between adjacent polygons)
x_simple <- st_simplify(x, preserveTopology = TRUE, dTolerance = 100)
```

### Convex Hull

```r
hulls <- st_convex_hull(x)
```

### Explode (Multi to Single)

Split MULTIPOLYGON/MULTILINESTRING into individual geometries:

```r
x_single <- st_cast(x, "POLYGON")  # MULTIPOLYGON -> POLYGON
```

### Bounds

```r
# Bounding box of entire sf object
st_bbox(x)  # xmin, ymin, xmax, ymax

# Bounding box polygon for each feature
boxes <- st_as_sfc(lapply(seq_len(nrow(x)), function(i) {
  st_as_sfc(st_bbox(x[i, ]))[[1]]
}), crs = st_crs(x))
```

### Make Valid

Fix invalid geometries:

```r
x_valid <- st_make_valid(x)
stopifnot(all(st_is_valid(x_valid)))
```

---

## References and Further Reading

Lovelace, R., Nowosad, J., and Muenchow, J. (2024). *Geocomputation with R* (2nd ed.), Chs. 4-5: "Spatial data operations" and "Geometry operations." https://r.geocompx.org/

Pebesma, E. and Bivand, R. (2023). *Spatial Data Science*, Ch. 4: "Spatial data operations." https://r-spatial.org/book/

sf package documentation. https://r-spatial.github.io/sf/
