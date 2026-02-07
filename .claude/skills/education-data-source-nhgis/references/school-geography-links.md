# Linking Schools to Census Geography

Connecting schools to census demographics requires establishing geographic relationships between school locations and census units.

## Linking Methods Overview

| Method | Input Required | Output | Best For |
|--------|----------------|--------|----------|
| Point-in-polygon | School coordinates | Tract/BG assignment | Custom analysis |
| NCES EDGE files | NCES school ID | District-to-tract relationships | District-level work |
| Education Data Portal | NCES school ID | Pre-linked tract data | Quick lookups |
| SABINS | SABINS boundary ID | Attendance area demographics | 2009-2012 only |
| Geocoding | School address | Coordinates or tract | When coordinates missing |

## Method 1: Point-in-Polygon Spatial Join

Most direct method when you have school coordinates.

### Process

1. Obtain school coordinates (latitude/longitude)
   - Source: CCD directory via Education Data Portal
   - Fields: `latitude`, `longitude`

2. Obtain census boundary files
   - Source: NHGIS Data Finder
   - Select: Census Tract or Block Group shapefiles
   - Match year to your analysis period

3. Perform spatial join
   - Tool: GIS software or Python/R spatial libraries
   - Operation: Point-in-polygon
   - Result: Each school gets census unit ID

### Python Example

```python
import geopandas as gpd
import pandas as pd

# Load school points (from CCD)
schools = pd.read_csv("schools.csv")
schools_gdf = gpd.GeoDataFrame(
    schools,
    geometry=gpd.points_from_xy(schools.longitude, schools.latitude),
    crs="EPSG:4326"
)

# Load tract boundaries (from NHGIS)
tracts = gpd.read_file("nhgis_tracts_2020.shp")

# Spatial join
schools_with_tracts = gpd.sjoin(
    schools_gdf, 
    tracts[["GISJOIN", "geometry"]], 
    how="left", 
    predicate="within"
)
```

### Considerations

- **Coordinate quality**: CCD coordinates are generally accurate but verify edge cases
- **Boundary vintage**: Match boundary year to data year
- **Projection**: NHGIS uses Albers Equal Area; transform if needed
- **Edge cases**: Schools exactly on boundaries may need manual review

## Method 2: NCES EDGE Geographic Relationship Files

NCES provides pre-computed relationships between school districts and census units.

### Available Files

| File | Content | Source |
|------|---------|--------|
| School District-Tract | District to tract relationships | NCES EDGE |
| School District-County | District to county relationships | NCES EDGE |
| School-Block | Individual schools to blocks | NCES EDGE |

### District-to-Tract Relationship

The EDGE School District Geographic Relationship Files show how census tracts relate to school districts.

**Key fields**:
- `LEAID`: NCES district ID (7 characters)
- `GEOID`: Census tract ID (11 characters)
- `LANDAREA`: Land area in square meters
- `AESSION`: Allocation session

**Types of relationships**:
1. **Tract fully in district**: Tract entirely within district boundaries
2. **Tract partially in district**: Tract split across districts
3. **Multiple tracts in district**: Most districts contain many tracts

### Using EDGE Files

```python
import pandas as pd

# Load EDGE relationship file
edge = pd.read_csv("EDGE_GEOCODE_PUBLICSCH_2223.csv")

# Filter to specific district
district_tracts = edge[edge["LEAID"] == "0622710"]

# Get unique tracts in district
tracts_in_district = district_tracts["TRACT"].unique()
```

### Limitations

- Relationships based on boundaries, not student residence
- Doesn't account for open enrollment or choice programs
- Updated annually; verify vintage matches your data

## Method 3: Education Data Portal NHGIS Data

The Urban Institute provides pre-linked school-to-tract data via the HuggingFace mirror.

### Mirror Paths

```
schools/nhgis/census-{year}/schools_nhgis_geog_{year}.parquet
```

### Available Years

Based on decennial census years:
- 1990
- 2000
- 2010
- 2020

### Key Variables

| Variable | Description | Type |
|----------|-------------|------|
| `ncessch` | NCES school ID | Int64 |
| `tract` | Census tract number | Int64 |
| `block_group` | Block group number | Int64 |
| `geoid_block` | Full block identifier | Int64 |
| `census_region` | Census region (1-4, 9 for territories) | Int64 |
| `census_division` | Census division (1-9) | Int64 |
| `cbsa` | CBSA code | Int64 |
| `cbsa_type` | 1=Metropolitan, 2=Micropolitan | Int64 |

### Querying via Mirror

```python
import polars as pl

# Load from HuggingFace mirror
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/nhgis/census-2020/schools_nhgis_geog_2020.parquet"
df = pl.read_parquet(url)

# Filter to specific school
school_data = df.filter(pl.col("ncessch") == 60000100001)
print(school_data.select(["ncessch", "tract", "block_group", "census_region"]))
```

### Note on Integer Encodings

Portal data uses integer encodings for categorical variables:

| Variable | Code | Meaning |
|----------|------|---------|
| `census_region` | 1 | Northeast |
| `census_region` | 2 | Midwest |
| `census_region` | 3 | South |
| `census_region` | 4 | West |
| `census_region` | 9 | Territories |
| `cbsa_type` | 1 | Metropolitan |
| `cbsa_type` | 2 | Micropolitan |

## Method 4: SABINS School Attendance Areas

SABINS provides actual school attendance boundaries (catchment areas) for select areas and years.

### Coverage

| School Year | Status |
|-------------|--------|
| 2009-10 | Available |
| 2010-11 | Available |
| 2011-12 | Available |
| After 2012 | Not available (funding ended) |

### Geographic Coverage

- Not nationwide
- Varies by grade level
- Coverage maps: https://www.nhgis.org/sabins-data-availability

### Data Components

1. **Boundary files**: GIS shapefiles of attendance zones
2. **Census data**: 2010 Census data tabulated for attendance areas
3. **Crosswalk tables**: Link boundaries to CCD schools

### Using SABINS

```
1. Access via NHGIS Data Finder
2. Select "SABINS" in Geographic Levels filter
3. Choose grade level (K-12)
4. Download boundary files and/or tabular data
```

### SABINS-CCD Crosswalk

Attendance boundaries don't always match 1:1 with schools:
- Some schools share attendance areas
- Some attendance areas feed multiple schools

Crosswalk tables available for each grade:
- `sabins_ccd_crosswalk_grade{N}_{year}.csv`

### Limitations

- **Historical only**: No data after 2011-12 school year
- **Incomplete coverage**: Many districts not included
- **Grade-specific**: Boundaries vary by grade level
- **No current equivalent**: No national source for current attendance boundaries

## Method 5: Geocoding Addresses

When coordinates are unavailable, geocode school addresses to census units.

### Services

| Service | Output | Cost |
|---------|--------|------|
| Census Geocoder | Coordinates + tract | Free |
| FCC Area API | Tract from coordinates | Free |
| Google Geocoding | Coordinates | Paid |
| ArcGIS Geocoding | Coordinates + tract | Varies |

### Census Geocoder

```python
import requests

address = "1600 Pennsylvania Avenue NW, Washington, DC 20500"
url = f"https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
params = {
    "address": address,
    "benchmark": "Public_AR_Current",
    "vintage": "Census2020_Current",
    "format": "json"
}
response = requests.get(url, params=params)
result = response.json()

# Extract tract
tract = result["result"]["addressMatches"][0]["geographies"]["Census Tracts"][0]["GEOID"]
```

### Batch Geocoding

For many addresses, use Census Batch Geocoder:
- Upload CSV with addresses
- Returns coordinates and census geography
- Limit: 10,000 addresses per batch

## Aggregating Census Data to School Districts

When NHGIS doesn't provide school-district-level data for your variables:

### Method A: Tract-Weighted Aggregation

1. Get all tracts in district (via EDGE files)
2. Get tract-level data from NHGIS
3. Sum counts or compute weighted averages

```python
# Example: Total population in district
district_population = tracts_in_district["total_pop"].sum()

# Example: Weighted average median income
weighted_income = (
    (tracts_in_district["median_income"] * tracts_in_district["households"]).sum() 
    / tracts_in_district["households"].sum()
)
```

### Method B: Block-Level Aggregation

More precise but more complex:

1. Get block-to-school-district crosswalk
2. Get block-level data
3. Aggregate blocks to districts

### Handling Partial Tracts

When tracts cross district boundaries:

**Option 1**: Area-based apportionment
- Pro: Simple
- Con: Assumes uniform distribution

**Option 2**: Use block data
- Pro: Exact for 100% count variables
- Con: No sample data at block level

**Option 3**: Population-weighted
- Use NHGIS crosswalk weights (if available)
- Pro: More accurate allocation
- Con: Requires crosswalk data

## Best Practices

### Matching Vintages

| School Data Year | Census Boundary Year | Census Data Year |
|------------------|----------------------|------------------|
| 2022-23 | 2020 | ACS 2018-2022 or 2020 Census |
| 2019-20 | 2010 or 2019 | ACS 2015-2019 |
| 2014-15 | 2010 | ACS 2011-2015 or 2010 Census |
| 2009-10 | 2010 | 2010 Census or SABINS |

### Quality Checks

1. **Missing matches**: Flag schools not matching any tract
2. **Edge cases**: Verify schools near boundaries
3. **Zero population**: Some tracts are non-residential
4. **Coordinate errors**: Check for obvious outliers

### Documentation

Record your linking methodology:
- Boundary vintage used
- Join method (point-in-polygon, crosswalk, etc.)
- Handling of edge cases
- Match rate achieved

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| School not in any tract | Coordinates error or offshore | Verify coordinates; manual fix |
| Multiple tracts per school | Point exactly on boundary | Pick one or nearest centroid |
| Tract spans districts | Census/district mismatch | Use blocks or apportion |
| Historical mismatch | Boundary changes | Use standardized time series |
| Missing demographics | Low population tract | Aggregate to larger area |
