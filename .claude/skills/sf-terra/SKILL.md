---
name: sf-terra
description: >-
  R spatial data: sf vectors, terra rasters, spdep/spatialreg spatial stats,
  leaflet interactive maps, ggplot2+geom_sf() choropleths. CRS, spatial joins,
  geometry ops. Use when execution language is R. Python equivalent: geopandas.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "sf 1.1-0"
  skill-last-updated: "2026-05-08"
  tags: ["r", "geospatial", "sf", "terra", "mapping"]
---

# sf-terra Skill

R geospatial analysis with sf (Simple Features for R), terra (modern raster
operations), spdep/spatialreg (spatial statistics and spatial econometrics),
leaflet (interactive web maps), and classInt (classification breaks for
choropleth maps). Covers sf objects, CRS management, spatial joins, geometric
operations, raster creation and manipulation, choropleth maps via
ggplot2 + geom_sf(), interactive maps via leaflet, and spatial autocorrelation
and regression. Use when the execution language is R and the task involves
spatial data, map-making, or spatial statistics. Python equivalent: the
geopandas skill.

## What is sf?

sf (Simple Features) is the modern R package for vector geospatial data:

- **sf objects**: An sf object is a data.frame (or tibble) with a special `geometry` list-column containing sfc geometries -- tabular data meets spatial operations
- **Tidyverse integration**: sf objects work with dplyr verbs (`filter()`, `mutate()`, `group_by()`, `summarize()`), and the geometry column is preserved automatically
- **ggplot2 integration**: `geom_sf()` plots sf objects with automatic CRS-aware axis labels
- **GDAL/GEOS/PROJ backend**: Full access to industry-standard spatial libraries
- **Successor to sp/rgdal/rgeos**: Those packages are retired; sf is the standard

## What is terra?

terra is the modern R package for raster data (replaces the retired `raster` package):

- **SpatRaster objects**: Multi-band, multi-layer raster data with CRS and extent metadata
- **Raster arithmetic**: Element-wise operations, aggregation, focal operations
- **Raster-vector interaction**: `extract()`, `crop()`, `mask()` using sf geometries
- **Memory-efficient**: Processes large rasters on disk without loading everything into memory

## Version Notes

Versions installed in the DAAF container (R 4.5.3):

| Package | Version | Role |
|---------|---------|------|
| sf | 1.1-0 | Vector spatial data (Simple Features) |
| terra | 1.9-11 | Raster spatial data |
| stars | 0.7.2 | Spatiotemporal arrays (raster time series) |
| spdep | 1.4.2 | Spatial weights and spatial autocorrelation |
| spatialreg | 1.4.3 | Spatial regression models (SAR, SEM, SDM) |
| leaflet | 2.2.3 | Interactive web maps |
| classInt | 0.4.11 | Classification intervals for choropleth breaks |

**sf 1.x changes to be aware of:**
- s2 geometry engine enabled by default for geographic CRS (spherical geometry) -- this changes area/distance/intersection behavior from earlier versions
- Use `sf_use_s2(FALSE)` to temporarily revert to planar GEOS operations when s2 produces unexpected results (see `gotchas.md`)
- `st_make_valid()` is now built into sf (no longer needs lwgeom)

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | sf objects, st_read/st_write, basic plotting, CRS inspection | Starting with sf or quick reminder |
| `crs.md` | st_transform(), EPSG codes, CRS management, projection pitfalls | CRS errors or projection decisions |
| `spatial-ops.md` | st_join(), st_buffer(), st_intersection(), st_union(), geometric operations | Combining or transforming spatial data |
| `raster.md` | terra::rast(), raster arithmetic, extract(), crop/mask, raster-vector interaction | Working with raster data |
| `mapping.md` | ggplot2 + geom_sf(), choropleth with scale_fill, classInt for breaks, annotation | Making static maps |
| `interactive.md` | leaflet: addPolygons, addCircleMarkers, colorBin, popups, tile layers | Making interactive web maps |
| `spatial-stats.md` | spdep::poly2nb(), nb2listw(), moran.test(), spatialreg::lagsarlm() | Spatial autocorrelation and regression |
| `gotchas.md` | s2 geometry, CRS mismatch, geometry column persistence, large data performance | Debugging spatial issues |

### Reading Order

1. **New to sf?** Start with `quickstart.md` then `spatial-ops.md`
2. **Making maps?** Read `mapping.md` (relies on `crs.md` for projection choices)
3. **Interactive maps?** Read `interactive.md`
4. **Raster data?** Read `raster.md`
5. **Spatial statistics?** Read `spatial-stats.md` (for methodology context, also load `data-scientist` skill's `geospatial-analysis.md`)
6. **Having issues?** Check `gotchas.md` first

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `geopandas` | Python equivalent -- covers the same spatial domain for Python pipelines |
| `data-scientist` (`geospatial-analysis.md`, `geospatial-operations.md`) | Spatial methodology -- when/why to use spatial methods, interpretation guidance |
| `ggplot2` | Visualization -- `geom_sf()` is built on ggplot2; load ggplot2 skill for themes and styling |
| `tidyverse` | Data preparation -- sf objects work with dplyr verbs; tidyverse prepares data for spatial analysis |
| `r-stats` | Statistical modeling -- non-spatial regression and diagnostics |
| `fixest` | Fixed effects regression -- when combining spatial data with panel econometrics |
| `r-python-translation` | Cross-language spatial translation |

## Quick Decision Trees

### "I need to read or write spatial data"

```
Loading/saving spatial data?
+-- Read vector file (Shapefile, GeoPackage, GeoJSON) -> ./references/quickstart.md
+-- Read GeoParquet -> ./references/quickstart.md
+-- Create sf from lat/lon columns -> ./references/quickstart.md
+-- Write to file -> ./references/quickstart.md
+-- Read raster data (GeoTIFF) -> ./references/raster.md
+-- Raster time series (NetCDF) -> ./references/raster.md
```

### "I need to combine or transform spatial data"

```
Spatial operations?
+-- Join by location (point-in-polygon) -> ./references/spatial-ops.md
+-- Nearest-neighbor join -> ./references/spatial-ops.md
+-- Overlay (intersection, union, difference) -> ./references/spatial-ops.md
+-- Dissolve/aggregate polygons -> ./references/spatial-ops.md
+-- Buffer features -> ./references/spatial-ops.md
+-- Clip to boundary -> ./references/spatial-ops.md
+-- Compute distances -> ./references/spatial-ops.md
+-- Compute centroids or areas -> ./references/spatial-ops.md
```

### "I need to fix CRS or projection issues"

```
CRS/projection issues?
+-- Check current CRS -> ./references/crs.md
+-- Reproject to different CRS -> ./references/crs.md
+-- Choose a projection for analysis -> ./references/crs.md
+-- Data has no CRS (set it) -> ./references/crs.md
+-- CRS mismatch error -> ./references/gotchas.md
+-- Area/distance calculations wrong -> ./references/crs.md
```

### "I need to make a map"

```
Making maps?
+-- Quick static choropleth (ggplot2) -> ./references/mapping.md
+-- Classification schemes (quantiles, Jenks) -> ./references/mapping.md
+-- Layered map with multiple sf layers -> ./references/mapping.md
+-- Multi-panel maps -> ./references/mapping.md
+-- Interactive map (pan/zoom/hover) -> ./references/interactive.md
+-- Export to PNG/SVG/HTML -> ./references/mapping.md or ./references/interactive.md
```

### "I need spatial statistics"

```
Spatial statistics?
+-- Build spatial weights (contiguity, distance) -> ./references/spatial-stats.md
+-- Test for spatial autocorrelation (Moran's I) -> ./references/spatial-stats.md
+-- Local clusters / hot spots (LISA) -> ./references/spatial-stats.md
+-- Spatial regression (lag, error, Durbin) -> ./references/spatial-stats.md
+-- Methodology guidance (interpretation, MAUP) -> data-scientist skill: geospatial-analysis.md
```

### "I need to work with rasters"

```
Raster operations?
+-- Read GeoTIFF -> ./references/raster.md
+-- Raster arithmetic -> ./references/raster.md
+-- Extract raster values at points/polygons -> ./references/raster.md
+-- Crop/mask raster by polygon -> ./references/raster.md
+-- Raster-vector conversion -> ./references/raster.md
+-- Raster time series (stars) -> ./references/raster.md
```

### "Something isn't working"

```
Having issues?
+-- s2 geometry errors -> ./references/gotchas.md
+-- CRS mismatch errors -> ./references/gotchas.md
+-- Geometry column lost after dplyr -> ./references/gotchas.md
+-- Invalid geometry errors -> ./references/gotchas.md
+-- Memory issues with large files -> ./references/gotchas.md
+-- General troubleshooting -> ./references/gotchas.md
```

## File-First Execution in Research Workflows

In DAAF research pipelines, R spatial operations follow the **file-first execution
protocol** -- code is written to `.R` script files and executed via the
`run_with_capture.sh` wrapper, never run interactively.

**The pattern:**
1. Write spatial analysis code to `scripts/stage{N}_{type}/{step}_{task-name}.R`
2. Execute via Bash: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script_name}.R`
3. `run_with_capture.sh` detects the `.R` extension and uses `Rscript` automatically
4. stdout/stderr are appended to the script file as comments
5. If a script fails, create a versioned copy (`_a.R`, `_b.R`, etc.) for fixes

Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

**R spatial script structure follows DAAF conventions:**

```r
# --- Config ---
library(sf)
library(dplyr)
library(ggplot2)

PROJECT_DIR <- "/daaf/research/YYYY-MM-DD_Project"
TARGET_CRS <- 5070  # NAD83 Conus Albers

# --- Load ---
# INTENT: Load school point data and county boundaries
schools <- st_read(file.path(PROJECT_DIR, "data", "schools.gpkg")) |>
  st_transform(TARGET_CRS)
counties <- st_read(file.path(PROJECT_DIR, "data", "counties.gpkg")) |>
  st_transform(TARGET_CRS)
cat("Schools:", nrow(schools), "rows\n")
cat("Counties:", nrow(counties), "rows\n")

# --- Transform ---
# INTENT: Assign each school to its county via spatial join
# ASSUMES: All schools fall within a county boundary
joined <- st_join(schools, counties["county_name"], join = st_within)

# --- Validate ---
stopifnot(nrow(joined) == nrow(schools))
stopifnot(sum(is.na(joined$county_name)) == 0)
cat("Join complete:", nrow(joined), "schools matched\n")

# --- Save ---
st_write(joined, file.path(PROJECT_DIR, "data", "schools_with_county.gpkg"),
         delete_dsn = TRUE)
cat("Saved: schools_with_county.gpkg\n")
```

## Quick Reference

### Essential Setup

```r
library(sf)          # vector spatial data
library(terra)       # raster spatial data
library(dplyr)       # data manipulation (works with sf)
library(ggplot2)     # static maps via geom_sf()
library(spdep)       # spatial weights, Moran's I
library(spatialreg)  # spatial regression models
library(leaflet)     # interactive web maps
library(classInt)    # classification intervals
```

### Core Operations

| Operation | Code | Package |
|-----------|------|---------|
| Read vector | `st_read("data.gpkg")` | sf |
| Read parquet | `sfarrow::st_read_parquet("data.parquet")` | sfarrow |
| From lat/lon | `st_as_sf(df, coords = c("lon", "lat"), crs = 4326)` | sf |
| Check CRS | `st_crs(x)` | sf |
| Reproject | `st_transform(x, crs = 5070)` | sf |
| Spatial join | `st_join(points, polygons, join = st_within)` | sf |
| Intersection | `st_intersection(x, y)` | sf |
| Buffer | `st_buffer(x, dist = 1000)` (CRS units) | sf |
| Centroid | `st_centroid(x)` | sf |
| Area | `st_area(x)` (returns units) | sf |
| Distance | `st_distance(x, y)` | sf |
| Union/dissolve | `x |> group_by(col) |> summarize()` | sf + dplyr |
| Plot (static) | `ggplot(x) + geom_sf(aes(fill = col))` | ggplot2 |
| Plot (interactive) | `leaflet(x) |> addTiles() |> addPolygons()` | leaflet |
| Write vector | `st_write(x, "out.gpkg")` | sf |
| Read raster | `rast("elev.tif")` | terra |
| Raster extract | `extract(r, vect(sf_obj))` | terra |
| Crop raster | `crop(r, vect(sf_obj))` | terra |

### Common CRS Codes

| EPSG | Name | Use For |
|------|------|---------|
| 4326 | WGS84 | Storage, exchange, web (not analysis) |
| 5070 | NAD83 Conus Albers | US thematic maps (equal-area) |
| 3857 | Web Mercator | Web tiles display only |
| 32617 | UTM Zone 17N | US East Coast local analysis |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| sf objects and structure | `./references/quickstart.md` |
| st_read / st_write | `./references/quickstart.md` |
| Creating sf from coordinates | `./references/quickstart.md` |
| Basic plotting with plot() | `./references/quickstart.md` |
| GeoParquet I/O | `./references/quickstart.md` |
| CRS fundamentals | `./references/crs.md` |
| st_transform / reprojection | `./references/crs.md` |
| Choosing projections | `./references/crs.md` |
| Common US projections | `./references/crs.md` |
| set_crs vs st_transform | `./references/crs.md` |
| Spatial joins (st_join) | `./references/spatial-ops.md` |
| Nearest-neighbor joins | `./references/spatial-ops.md` |
| Overlay (st_intersection, st_union) | `./references/spatial-ops.md` |
| Dissolve and aggregation | `./references/spatial-ops.md` |
| Buffering (st_buffer) | `./references/spatial-ops.md` |
| Clipping (st_crop, st_intersection) | `./references/spatial-ops.md` |
| Area, distance, centroid | `./references/spatial-ops.md` |
| terra::rast() basics | `./references/raster.md` |
| Raster arithmetic | `./references/raster.md` |
| extract(), crop(), mask() | `./references/raster.md` |
| stars spatiotemporal arrays | `./references/raster.md` |
| Raster-vector conversion | `./references/raster.md` |
| ggplot2 + geom_sf() maps | `./references/mapping.md` |
| Choropleth maps | `./references/mapping.md` |
| classInt classification schemes | `./references/mapping.md` |
| Map annotation and styling | `./references/mapping.md` |
| Multi-panel maps | `./references/mapping.md` |
| leaflet interactive maps | `./references/interactive.md` |
| addPolygons, addCircleMarkers | `./references/interactive.md` |
| Color palettes and legends | `./references/interactive.md` |
| Popups and labels | `./references/interactive.md` |
| Tile providers | `./references/interactive.md` |
| Spatial weights (nb, listw) | `./references/spatial-stats.md` |
| Moran's I test | `./references/spatial-stats.md` |
| LISA local indicators | `./references/spatial-stats.md` |
| Spatial regression (SAR, SEM) | `./references/spatial-stats.md` |
| s2 geometry engine | `./references/gotchas.md` |
| CRS mismatch errors | `./references/gotchas.md` |
| Invalid geometries | `./references/gotchas.md` |
| Geometry column persistence | `./references/gotchas.md` |
| Memory and performance | `./references/gotchas.md` |
| sp/rgdal/rgeos migration | `./references/gotchas.md` |

## Citation

When sf is used as a primary analytical tool, include in the report's
Software & Tools references:

> Pebesma, E. (2018). "Simple Features for R: Standardized Support for Spatial Vector Data." *The R Journal*, 10(1), 439-446. https://doi.org/10.32614/RJ-2018-009

**Cite when:** sf is used for spatial operations, spatial joins, or map
production central to the analysis.
**Do not cite when:** Only used to read a shapefile for a simple reference lookup.

If terra raster operations are also used, additionally cite:

> Hijmans, R.J. (2024). *terra: Spatial Data Analysis*. R package. https://rspatial.org/

If spdep/spatialreg spatial analysis is also used, additionally cite:

> Bivand, R.S., Pebesma, E., and Gomez-Rubio, V. (2013). *Applied Spatial Data Analysis with R* (2nd ed.). Springer. https://doi.org/10.1007/978-1-4614-7618-4
