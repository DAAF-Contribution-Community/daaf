# CRS and Projections

Coordinate Reference System handling in sf -- checking, setting, transforming, and choosing projections. Getting the CRS right is a prerequisite for correct spatial operations; getting it wrong produces silently wrong results.

---

## CRS Fundamentals

### Geographic vs Projected CRS

| Property | Geographic CRS | Projected CRS |
|----------|---------------|---------------|
| Coordinates | Longitude/latitude (degrees) | Easting/northing (meters or feet) |
| Earth model | 3D ellipsoid | 2D flat plane |
| Standard example | WGS84 (EPSG:4326) | NAD83 Conus Albers (EPSG:5070) |
| Distance units | Decimal degrees (not constant) | Meters (constant within valid region) |
| Area calculation | Wrong -- 1 degree varies by latitude | Correct (within projection's valid region) |

**The critical rule:** Buffer, area, distance, and centroid operations on a geographic CRS (longitude/latitude) produce wrong or misleading results because one degree of longitude varies from ~111 km at the equator to ~0 km at the poles. Always reproject to an appropriate projected CRS before computing.

**sf and the s2 engine:** Since sf 1.0, geographic CRS operations use the s2 spherical geometry engine by default. This means `st_area()` and `st_distance()` on EPSG:4326 data return correct results in square meters / meters (using geodesic calculations), unlike older versions which computed in degrees. However, some operations (intersection, buffer) may behave unexpectedly with s2. See `gotchas.md` for details.

---

## Checking CRS

```r
# Check the current CRS
st_crs(x)
# Returns: Coordinate Reference System with EPSG code, proj4string, WKT

# Extract EPSG code
st_crs(x)$epsg
# Returns: 4326 (or NA if not an EPSG CRS)

# Extract the input string used to set CRS
st_crs(x)$input
# Returns: "EPSG:4326" or a proj4 string

# Check if geographic (lon/lat) or projected
st_is_longlat(x)
# Returns: TRUE for geographic, FALSE for projected

# Detailed WKT2 representation
cat(st_crs(x)$wkt)

# Check axis units
st_crs(x)$units_gdal
# Returns: "degree" for geographic, "metre" for projected
```

---

## Setting CRS (Declaring, Not Transforming)

**Setting** a CRS tells sf what system the coordinates are already in. No coordinate values change. Use this when data arrives without CRS metadata (common with CSV files containing lat/lon columns).

```r
# Set CRS on creation
pts <- st_as_sf(df, coords = c("lon", "lat"), crs = 4326)

# Set CRS on existing sf object (no CRS currently set)
st_crs(x) <- 4326

# Or using a pipe-friendly function
x <- st_set_crs(x, 4326)
```

**When to use `st_set_crs()`:** Only when the sf object has no CRS (`st_crs(x)` returns NA) or when you know the existing CRS label is incorrect. If the data already has a CRS and you want to change the projection, use `st_transform()` instead.

---

## Reprojecting (Transforming Coordinates)

**Reprojecting** recomputes all coordinate values from one CRS to another. Use this when you need a different projection for analysis or visualization.

```r
# Reproject to NAD83 Conus Albers (equal-area, good for US maps)
x_albers <- st_transform(x, crs = 5070)

# Reproject using full EPSG string
x_utm <- st_transform(x, crs = "EPSG:32617")

# Reproject using PROJ string
x_custom <- st_transform(x, crs = "+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=37.5 +lon_0=-96")

# Reproject to match another sf object's CRS
x_matched <- st_transform(x, crs = st_crs(other_sf))
```

### Setting vs Transforming: The Difference

```r
# WRONG: Setting CRS to "reproject" -- coordinates don't change, CRS label changes
# This makes the data plot in the wrong location
st_crs(x) <- 5070  # DON'T DO THIS if x is in EPSG:4326

# RIGHT: Transform to reproject -- coordinates are recomputed
x_proj <- st_transform(x, crs = 5070)  # Coordinates change, CRS changes
```

---

## Choosing a Projection

### Decision Guide

```
What does your analysis need?
+-- Area calculations or thematic maps
|   +-- Equal-area projection
|       +-- Continental US -> EPSG:5070 (NAD83 Conus Albers)
|       +-- Single state -> State Plane (equal-area variant)
|       +-- Global -> Mollweide or Equal Earth
|       +-- Custom study area -> LAEA centered on study centroid
+-- Distance or local-scale analysis (<500 km)
|   +-- UTM zone for study area
+-- Web map display
|   +-- Web Mercator (EPSG:3857) -- display only, never for analysis
+-- Data storage or exchange
|   +-- WGS84 (EPSG:4326)
+-- Unsure
    +-- Start with EPSG:5070 for US, UTM for local
```

### Common US Projections

| EPSG | Name | Best For | Units |
|------|------|----------|-------|
| 4326 | WGS84 | Storage, exchange (not analysis) | Degrees |
| 5070 | NAD83 Conus Albers | Continental US thematic maps, area calculations | Meters |
| 3857 | Web Mercator | Web tile display only | Meters (distorted) |
| 32617 | UTM Zone 17N | US East Coast local analysis | Meters |
| 32610 | UTM Zone 10N | US West Coast local analysis | Meters |

### Finding the Right UTM Zone

```r
# From a point
lon <- -77.0
# UTM zone = floor((lon + 180) / 6) + 1
utm_zone <- floor((lon + 180) / 6) + 1
epsg <- 32600 + utm_zone  # Northern hemisphere
cat("UTM Zone:", utm_zone, "-> EPSG:", epsg, "\n")
```

### Custom LAEA (Lambert Azimuthal Equal-Area)

For study areas not well-served by standard projections:

```r
# Center the projection on your study area
centroid <- st_coordinates(st_centroid(st_union(x)))
custom_crs <- paste0("+proj=laea +lat_0=", centroid[2],
                      " +lon_0=", centroid[1],
                      " +datum=WGS84 +units=m")
x_custom <- st_transform(x, crs = custom_crs)
```

---

## CRS Matching Before Spatial Operations

All spatial operations (join, overlay, distance) require both inputs to be in the same CRS. sf raises an error if they differ.

```r
# Check if two sf objects share the same CRS
if (st_crs(x) == st_crs(y)) {
  result <- st_join(x, y)
} else {
  # Reproject one to match the other
  y_reproj <- st_transform(y, crs = st_crs(x))
  result <- st_join(x, y_reproj)
}
```

### Best Practice: Reproject Early

```r
# Standard workflow: reproject all inputs to a common CRS at the start
TARGET_CRS <- 5070

counties <- st_read("counties.gpkg") |> st_transform(TARGET_CRS)
schools <- st_read("schools.gpkg") |> st_transform(TARGET_CRS)
tracts <- st_read("tracts.gpkg") |> st_transform(TARGET_CRS)

# Now all spatial operations work without CRS concerns
```

---

## Common CRS Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Area computed in geographic CRS (pre-s2) | Areas in square degrees | Reproject to equal-area CRS first |
| Buffer in geographic CRS | s2 error or unexpected shape | Reproject to projected CRS, then buffer |
| Distance in degrees (pre-s2) | Values like 0.01 instead of 1000 m | Use st_distance() with s2 or reproject |
| `st_crs<-` used instead of `st_transform` | Data plots in wrong location | Use `st_transform()` to reproject |
| Web Mercator for analysis | Areas wildly wrong at high latitudes | Use equal-area projection |
| CRS lost after non-sf operation | `st_crs(x)` returns NA | Re-set CRS or use sf-aware functions |
| Mixed CRS in spatial operation | Error: CRS mismatch | Reproject to common CRS |

---

## References and Further Reading

Lovelace, R., Nowosad, J., and Muenchow, J. (2024). *Geocomputation with R* (2nd ed.), Ch. 7: "Reprojecting geographic data." https://r.geocompx.org/

Pebesma, E. and Bivand, R. (2023). *Spatial Data Science*, Ch. 2: "Coordinates." https://r-spatial.org/book/

PROJ documentation. https://proj.org/
