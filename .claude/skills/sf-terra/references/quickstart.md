# sf Quickstart

## sf Objects

An sf object is a data.frame (or tibble) with a special `geometry` list-column containing sfc (Simple Feature Column) geometries. Every row is a spatial feature; every column is an attribute or the geometry.

```r
library(sf)

# An sf object has:
# - Regular columns (name, population, etc.)
# - A geometry column (sfc class: points, lines, or polygons)
# - A CRS (Coordinate Reference System) attached to the sfc column
```

### Inspecting sf Objects

```r
class(x)            # "sf" "data.frame"
st_geometry_type(x) # Geometry types (POINT, POLYGON, etc.)
st_crs(x)           # CRS information
st_bbox(x)          # Bounding box: xmin, ymin, xmax, ymax
nrow(x)             # Number of features
ncol(x)             # Number of columns (including geometry)
names(x)            # Column names
head(x)             # First rows (geometry prints as WKT)
```

---

## Creating sf Objects

### From a Data Frame with Coordinates

The most common case -- a data frame with latitude/longitude columns:

```r
library(sf)

df <- data.frame(
  name = c("School A", "School B", "School C"),
  lon = c(-77.036, -77.009, -76.995),
  lat = c(38.901, 38.889, 38.910),
  enrollment = c(500, 800, 650)
)

pts <- st_as_sf(df, coords = c("lon", "lat"), crs = 4326)
```

`coords = c("lon", "lat")` specifies column names in (x, y) order: longitude is x, latitude is y. This matches mathematical convention but trips up users who think "lat, lon". See `gotchas.md` for coordinate order pitfalls.

### From WKT or WKB

```r
# From Well-Known Text
wkt <- "POLYGON ((-77.05 38.90, -77.04 38.90, -77.04 38.91, -77.05 38.91, -77.05 38.90))"
geom <- st_as_sfc(wkt, crs = 4326)
poly <- st_sf(name = "Park", geometry = geom)
```

### Empty sf with Schema

```r
empty_sf <- st_sf(
  name = character(0),
  value = numeric(0),
  geometry = st_sfc(crs = 4326)
)
```

---

## Reading Spatial Data

### Read Any Supported Vector Format

sf uses GDAL under the hood, supporting 80+ vector formats:

```r
# GeoPackage (recommended modern format)
counties <- st_read("counties.gpkg")

# Shapefile (legacy -- see note below)
counties <- st_read("counties.shp")

# GeoJSON
counties <- st_read("counties.geojson")

# Specific layer from multi-layer file
counties <- st_read("multi_layer.gpkg", layer = "counties")
```

### Read with Filters (Efficient for Large Files)

```r
# Read only features within a bounding box
counties <- st_read("large_file.gpkg",
                     wkt_filter = "POLYGON ((-78 38, -76 38, -76 40, -78 40, -78 38))")

# Read only specific columns (via SQL)
counties <- st_read("large_file.gpkg",
                     query = "SELECT NAME, POP, geom FROM counties WHERE POP > 10000")

# Read limited rows
counties <- st_read("large_file.gpkg", query = "SELECT * FROM counties LIMIT 100")
```

### Read GeoParquet

GeoParquet is the fastest format for analytical workflows. sf does not natively
read GeoParquet, and the sfarrow package is **not installed** in this
environment. Read with arrow and convert the WKB geometry column (this pattern
is verified against the installed sf 1.1-0 + arrow):

```r
library(arrow)
library(sf)

df <- read_parquet("counties.parquet")
# geometry arrives as a list of raw vectors (WKB); convert to sfc, then sf.
# Check the source's CRS metadata — geopandas GeoParquet defaults to EPSG:4326.
df$geometry <- st_as_sfc(structure(as.list(df$geometry), class = "WKB"), crs = 4326)
counties <- st_as_sf(df)
```

Note: `st_as_sf()` has a `wkt =` argument for well-known-text columns but **no
`wkb =` argument** (verified against `formals()`) — WKB must go through
`st_as_sfc()` as above.

### Shapefile Limitations

Shapefiles have legacy constraints that modern formats avoid:
- Column names truncated to 10 characters
- No NULL value support
- 2 GB file size limit
- Character encoding ambiguity
- No multi-layer support

Prefer GeoPackage (.gpkg) or GeoParquet (.parquet) for new work.

---

## Writing Spatial Data

```r
# GeoPackage (preferred)
st_write(x, "output.gpkg", driver = "GPKG")

# Overwrite existing file
st_write(x, "output.gpkg", delete_dsn = TRUE)

# GeoJSON
st_write(x, "output.geojson", driver = "GeoJSON")

# Shapefile (legacy -- avoid if possible)
st_write(x, "output.shp")

# Parquet with WKB geometry (sfarrow is NOT installed; use arrow directly).
# unclass() strips the WKB class so arrow stores a plain binary column (verified):
library(arrow)
out <- st_drop_geometry(x)
out$geometry <- unclass(st_as_binary(st_geometry(x)))
write_parquet(out, "output.parquet")
# Note: this is plain parquet + WKB, not full GeoParquet (no CRS metadata) --
# record the CRS alongside (e.g., in the data dictionary). For a self-describing
# spatial format, prefer st_write() to GeoPackage.
```

---

## Basic Inspection

```r
# Structure
print(x)                    # Full print with geometry
str(x)                      # Structure (compact)

# Geometry info
st_geometry_type(x)         # Per-feature geometry types
st_geometry_type(x, by_geometry = FALSE)  # Overall type
st_crs(x)                  # CRS
st_bbox(x)                 # Bounding box [xmin, ymin, xmax, ymax]
st_is_valid(x)             # Validity check for each geometry

# Dimensions
nrow(x)
ncol(x)

# Drop geometry to get a plain data.frame
st_drop_geometry(x)
```

---

## Basic Plotting

### Base R plot()

```r
# Default plot -- all attribute columns as facets
plot(x)

# Plot single column
plot(x["population"])

# Just geometries
plot(st_geometry(x))

# Layered plot
plot(st_geometry(counties), col = "lightgray", border = "white")
plot(st_geometry(schools), col = "red", pch = 20, cex = 0.5, add = TRUE)
```

### ggplot2 + geom_sf()

```r
library(ggplot2)

# Basic choropleth
ggplot(counties) +
  geom_sf(aes(fill = population)) +
  scale_fill_viridis_c() +
  theme_minimal()

# Layered map
ggplot() +
  geom_sf(data = counties, fill = "lightgray", color = "white") +
  geom_sf(data = schools, color = "red", size = 0.5) +
  labs(title = "Schools by County") +
  theme_void()
```

For advanced maps, see `mapping.md`.

---

## Tidyverse Integration

sf objects work seamlessly with dplyr verbs. The geometry column is preserved automatically:

```r
library(dplyr)

result <- counties |>
  filter(state == "MD") |>
  mutate(pop_density = population / as.numeric(st_area(geometry)) * 1e6) |>
  select(name, population, pop_density) |>
  arrange(desc(pop_density))

# Spatial aggregation via group_by + summarize (equivalent to dissolve)
states <- counties |>
  group_by(state_fips) |>
  summarize(
    total_pop = sum(population, na.rm = TRUE),
    n_counties = n()
  )
# Geometries are automatically unioned within each group
```

---

## Essential Spatial Operations Preview

```r
# Reproject
counties_proj <- st_transform(counties, crs = 5070)

# Spatial join (which polygon contains each point?)
result <- st_join(schools, counties, join = st_within)

# Buffer (1 km around points -- CRS must be in meters)
schools_buf <- st_buffer(st_transform(schools, 5070), dist = 1000)

# Dissolve (merge counties into states)
states <- counties |> group_by(state_fips) |> summarize()

# Intersection of two polygon layers
overlap <- st_intersection(layer1, layer2)
```

For complete spatial operations reference, see `spatial-ops.md`.

---

## Next Steps

- Learn about [CRS and projections](./crs.md) -- essential before geometric computation
- Master [spatial operations](./spatial-ops.md) -- joins, overlays, dissolve
- Explore [static maps](./mapping.md) -- ggplot2 + geom_sf()
- Build [interactive maps](./interactive.md) -- leaflet

## References and Further Reading

Pebesma, E. (2018). "Simple Features for R: Standardized Support for Spatial Vector Data." *The R Journal*, 10(1), 439-446. https://doi.org/10.32614/RJ-2018-009

Lovelace, R., Nowosad, J., and Muenchow, J. (2024). *Geocomputation with R* (2nd ed.). CRC Press. https://r.geocompx.org/

Pebesma, E. and Bivand, R. (2023). *Spatial Data Science: With Applications in R*. CRC Press. https://r-spatial.org/book/
