# Interactive Maps with leaflet

Creating interactive web maps using the leaflet package -- tile layers, choropleth polygons, markers, popups, legends, and saving to HTML. leaflet is the R counterpart to Python's folium.

---

## Basic Leaflet Map

```r
library(leaflet)
library(sf)

# Minimal map centered on data
m <- leaflet(counties) |>
  addTiles() |>          # OpenStreetMap base tiles
  addPolygons()          # Add sf polygons
m  # Display (in viewer) or save (see below)
```

---

## Tile Providers

```r
# OpenStreetMap (default)
addTiles()

# CartoDB Positron (light, clean -- best for choropleth overlays)
addProviderTiles(providers$CartoDB.Positron)

# CartoDB DarkMatter (dark background)
addProviderTiles(providers$CartoDB.DarkMatter)

# Esri World Imagery (satellite)
addProviderTiles(providers$Esri.WorldImagery)

# Stamen Terrain
addProviderTiles(providers$Stadia.StamenTerrain)

# Stamen Toner Lite (grayscale)
addProviderTiles(providers$Stadia.StamenTonerLite)

# Multiple tile layers with layer control
leaflet() |>
  addProviderTiles(providers$CartoDB.Positron, group = "Light") |>
  addProviderTiles(providers$Esri.WorldImagery, group = "Satellite") |>
  addLayersControl(baseGroups = c("Light", "Satellite"))
```

---

## Choropleth Polygons

```r
library(leaflet)
library(sf)

# Color palette function
pal <- colorBin(
  palette = "YlOrRd",
  domain = counties$poverty_rate,
  bins = 5
)

# Build choropleth
m <- leaflet(counties) |>
  addProviderTiles(providers$CartoDB.Positron) |>
  addPolygons(
    fillColor = ~pal(poverty_rate),
    fillOpacity = 0.7,
    color = "white",      # Border color
    weight = 1,           # Border width
    opacity = 1,          # Border opacity
    highlight = highlightOptions(
      weight = 3,
      color = "#666",
      fillOpacity = 0.8,
      bringToFront = TRUE
    ),
    popup = ~paste0(
      "<b>", name, "</b><br/>",
      "Poverty Rate: ", round(poverty_rate, 1), "%<br/>",
      "Population: ", format(population, big.mark = ",")
    ),
    label = ~name
  ) |>
  addLegend(
    pal = pal,
    values = ~poverty_rate,
    title = "Poverty Rate (%)",
    position = "bottomright"
  )
```

---

## Color Palette Functions

leaflet provides three palette constructors:

| Function | Use For | Example |
|----------|---------|---------|
| `colorBin()` | Binned continuous (equal-interval or custom breaks) | `colorBin("YlOrRd", domain, bins = 5)` |
| `colorQuantile()` | Quantile-based bins (equal count per bin) | `colorQuantile("YlOrRd", domain, n = 5)` |
| `colorNumeric()` | Continuous gradient (no binning) | `colorNumeric("viridis", domain)` |
| `colorFactor()` | Categorical / factor variables | `colorFactor("Set2", domain)` |

### Custom Breaks with classInt

```r
library(classInt)
brks <- classIntervals(counties$poverty_rate, n = 5, style = "fisher")

pal <- colorBin(
  palette = "YlOrRd",
  domain = counties$poverty_rate,
  bins = brks$brks
)
```

---

## Points and Markers

### Circle Markers

```r
leaflet(schools) |>
  addProviderTiles(providers$CartoDB.Positron) |>
  addCircleMarkers(
    radius = ~sqrt(enrollment) / 5,     # Size by enrollment
    color = "steelblue",
    fillColor = "steelblue",
    fillOpacity = 0.6,
    stroke = TRUE,
    weight = 1,
    popup = ~paste0("<b>", school_name, "</b><br/>Enrollment: ", enrollment),
    label = ~school_name
  )
```

### Default Markers (Pin Icons)

```r
leaflet(schools) |>
  addTiles() |>
  addMarkers(
    popup = ~school_name,
    label = ~school_name,
    clusterOptions = markerClusterOptions()  # Cluster nearby markers
  )
```

---

## Popups and Labels

### Popup (Click to Show)

```r
addPolygons(
  popup = ~paste0(
    "<b>", name, "</b><br/>",
    "<table>",
    "<tr><td>Population:</td><td>", format(pop, big.mark = ","), "</td></tr>",
    "<tr><td>Poverty:</td><td>", round(pov_rate, 1), "%</td></tr>",
    "</table>"
  )
)
```

### Label (Hover to Show)

```r
addPolygons(
  label = ~paste0(name, ": ", round(poverty_rate, 1), "%"),
  labelOptions = labelOptions(
    style = list("font-size" = "12px"),
    direction = "auto"
  )
)
```

---

## Legends

```r
# Continuous legend
addLegend(
  pal = pal,
  values = ~poverty_rate,
  title = "Poverty Rate (%)",
  position = "bottomright",      # "topright", "bottomright", "bottomleft", "topleft"
  opacity = 1
)

# Custom labels
addLegend(
  pal = pal,
  values = ~poverty_rate,
  title = "Poverty Rate",
  labFormat = labelFormat(suffix = "%", digits = 1),
  position = "bottomright"
)
```

---

## Layered Maps

```r
m <- leaflet() |>
  addProviderTiles(providers$CartoDB.Positron) |>
  # Layer 1: Counties
  addPolygons(
    data = counties,
    fillColor = ~pal(poverty_rate),
    fillOpacity = 0.5,
    color = "gray",
    weight = 0.5,
    group = "Counties"
  ) |>
  # Layer 2: Schools
  addCircleMarkers(
    data = schools,
    radius = 3,
    color = "red",
    fillOpacity = 0.8,
    group = "Schools",
    popup = ~school_name
  ) |>
  # Layer control (toggle layers)
  addLayersControl(
    overlayGroups = c("Counties", "Schools"),
    options = layersControlOptions(collapsed = FALSE)
  )
```

---

## Setting View and Bounds

```r
# Set initial view
leaflet() |>
  setView(lng = -96, lat = 37.5, zoom = 4) |>   # Center of US
  addTiles()

# Fit to data bounds
leaflet(counties) |>
  addTiles() |>
  addPolygons() |>
  fitBounds(
    lng1 = st_bbox(counties)["xmin"],
    lat1 = st_bbox(counties)["ymin"],
    lng2 = st_bbox(counties)["xmax"],
    lat2 = st_bbox(counties)["ymax"]
  )
```

---

## Saving Leaflet Maps

```r
library(htmlwidgets)

# Save to HTML file
saveWidget(m, file = "interactive_map.html", selfcontained = TRUE)

# selfcontained = TRUE bundles all resources into one file (larger but portable)
# selfcontained = FALSE creates a folder of dependencies (smaller HTML)
```

In DAAF research pipelines, interactive maps are saved to the project output directory for inspection but are not the primary deliverable (static maps from ggplot2 are preferred for reports).

---

## CRS Considerations

leaflet expects data in **WGS84 (EPSG:4326)** -- longitude/latitude coordinates. sf objects in other CRS will be automatically transformed by the leaflet package. However, it is good practice to be explicit:

```r
# Ensure WGS84 for leaflet
counties_wgs <- st_transform(counties, 4326)
leaflet(counties_wgs) |> addTiles() |> addPolygons()
```

---

## References and Further Reading

Cheng, J. et al. (2024). *leaflet: Create Interactive Web Maps with the JavaScript 'Leaflet' Library*. https://rstudio.github.io/leaflet/

Lovelace, R., Nowosad, J., and Muenchow, J. (2024). *Geocomputation with R* (2nd ed.), Ch. 9: "Making maps with R." https://r.geocompx.org/
