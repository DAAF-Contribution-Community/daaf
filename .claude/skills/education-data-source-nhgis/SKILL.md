---
name: education-data-source-nhgis
description: >-
  IPUMS NHGIS (National Historical Geographic Information System) census
  geography and demographic data for education research. Use when working with
  census geography, demographic data for school communities, time series
  analysis, geographic crosswalks, or linking schools to census tracts/block
  groups. Portal data is pre-processed crosswalks; direct NHGIS requires
  IPUMS registration.
metadata:
  audience: data-analysts
  domain: education-data
---

# NHGIS Data Source Reference

Census geography and demographic data source for education research. NHGIS provides the foundation for linking schools to community characteristics via census tracts, block groups, and school district boundaries.

> **CRITICAL: Value Encoding**
>
> When accessing NHGIS data through the Education Data Portal (not NHGIS directly), categorical variables use **integer encodings**, not string labels. Always verify the exact codes in the mirror codebook.
>
> | Variable | Integer Code | Meaning |
> |----------|--------------|---------|
> | `census_region` | `1` | Northeast |
> | `census_region` | `2` | Midwest |
> | `census_region` | `3` | South |
> | `census_region` | `4` | West |
> | `cbsa_type` | `1` | Metropolitan |
> | `cbsa_type` | `2` | Micropolitan |
> | `geocode_accuracy` | `-2` | Not geocoded |
>
> See `./references/variable-catalog.md` for complete encoding tables.

## What is NHGIS?

NHGIS (from IPUMS, University of Minnesota) provides free access to census geography and demographic data.

- **Collector**: IPUMS, University of Minnesota
- **Coverage**: US census data from 1790-present (decennial census + ACS)
- **Content**: Summary tables, GIS boundary files, time series tables, geographic crosswalks
- **Frequency**: Decennial census (every 10 years) + ACS (annual, 5-year rolling)
- **Available years**: 1790-2020 (decennial), 2005-2023 (ACS 5-year)
- **Primary identifiers**: GISJOIN (NHGIS internal), GEOID (Census Bureau standard)
- **Education relevance**: Links school locations to community demographics via census tracts, block groups, and school district boundaries

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `geographic-units.md` | Census geography hierarchy (tracts, blocks, districts) | Understanding census geography |
| `school-geography-links.md` | Linking schools to census areas | Connecting school data to demographics |
| `time-series.md` | Historical data, harmonization methods | Longitudinal analysis |
| `variable-catalog.md` | Key demographic variables, codes, special values | Selecting census variables or interpreting encodings |
| `boundary-changes.md` | How boundaries change between censuses | Handling geographic inconsistencies |
| `data-access.md` | API, Python/R packages, data extraction | Downloading NHGIS data directly |

## Decision Trees

### What geographic level should I use?

```
Research question about...
├─ Individual schools
│   ├─ School's immediate neighborhood → Census tract or block group
│   ├─ School attendance zone → SABINS (limited years) or block-to-school crosswalk
│   └─ School district overall → School district boundaries
├─ School districts
│   ├─ District-level demographics → School district geographic level
│   ├─ Within-district variation → Census tracts within district
│   └─ District poverty estimates → SAIPE (via Education Data Portal)
├─ Regional patterns
│   ├─ County-level → County boundaries
│   ├─ Metro area → CBSA (Core Based Statistical Area)
│   └─ State-level → State boundaries
└─ Historical analysis
    ├─ Consistent boundaries needed → Geographically standardized tables
    └─ Original boundaries OK → Nominally integrated tables
```

### How do I link schools to census data?

```
Linking schools to census demographics?
├─ Have school coordinates (lat/lon)
│   ├─ Point-in-polygon → Spatial join to tract/block group boundaries
│   └─ Need tract ID only → Geocoding service or FCC API
├─ Have school NCES ID only
│   ├─ Use NCES EDGE files → School District Geographic Relationship Files
│   └─ Use Education Data Portal → NHGIS source provides tract links
├─ Need school attendance zones
│   ├─ 2009-2012 data → SABINS school areas
│   └─ Current data → Contact school district (no national source)
└─ See ./references/school-geography-links.md for details
```

### What time period data do I need?

```
Time period?
├─ Single recent year
│   ├─ Tract/block group level → ACS 5-year (most recent)
│   ├─ Larger areas (65K+ pop) → ACS 1-year
│   └─ Full census count → 2020 Decennial Census
├─ Historical comparison
│   ├─ Same boundaries across time → Geographically standardized tables (to 2010)
│   ├─ Original boundaries → Nominally integrated time series
│   └─ Custom standardization → Use geographic crosswalks
├─ Long time series (1970+)
│   └─ See ./references/time-series.md
└─ Pre-1970
    └─ Limited tract coverage; county/state more complete
```

## Quick Reference: Geographic Levels and Variables

### Geographic Levels

| Level | Typical Size | Education Use | NHGIS Coverage |
|-------|--------------|---------------|----------------|
| Block | ~40 people | Point locations | 1990-2020 |
| Block Group | ~1,500 people | School neighborhoods | 1990-2020 |
| Census Tract | ~4,000 people | Community context | 1910-2020 |
| County Subdivision | Varies | Rural areas | 1980-2020 |
| Place | City/town | Urban context | 1980-2020 |
| School District | Varies | District analysis | 2000-2020 |
| County | ~100,000 people | Regional patterns | 1790-2020 |
| State | Varies | Policy analysis | 1790-2020 |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `ncessch` | 12-digit integer | School | `60000100001` | NCES school ID (in Portal data) |
| `GISJOIN` | String with prefix | Any | `G0600010` | NHGIS internal ID; use for NHGIS joins |
| `GEOID` | Numeric string | Any | `06001402100` | Census Bureau standard; use for non-NHGIS joins |
| `tract` | Integer | Tract | `402100` | Census tract number (in Portal data) |
| `block_group` | Integer | Block Group | `1` | Block group within tract (in Portal data) |
| `geoid_block` | String | Block | `060014021001001` | Full block FIPS code (in Portal data) |
| `cbsa` | Integer | Metro area | `41860` | Core Based Statistical Area code |

### Key Education Variables

| Topic | Example Variables | Source |
|-------|-------------------|--------|
| Child population | Under 18, 5-17 school-age | Decennial, ACS |
| Race/ethnicity | Hispanic, White, Black, Asian, etc. | Decennial, ACS |
| Poverty | Persons below poverty, SNAP receipt | ACS (sample) |
| Education attainment | HS diploma, BA+ (adults) | ACS (sample) |
| Language | English proficiency, language at home | ACS (sample) |
| Housing | Owner/renter, median value, crowding | Decennial, ACS |
| Family structure | Single-parent, grandparent households | ACS (sample) |
| Immigration | Foreign-born, recent immigrants | ACS (sample) |

### Data Sources by Type

| Source | Years | Geographic Detail | Content |
|--------|-------|-------------------|---------|
| Decennial Census | 1790-2020 | Block (1990+) | 100% count: age, sex, race, housing |
| ACS 5-Year | 2005-2023 | Block group | Sample: income, education, language |
| ACS 1-Year | 2010-2023 | Areas 65K+ pop | Sample: same as 5-year |
| Time Series | 1790-2020 | Varies | Harmonized across years |
| Geographic Crosswalks | 1990-2020 | Block+ | Interpolation weights |

### Portal Variables (Schools NHGIS)

| Variable | Description |
|----------|-------------|
| `ncessch` | NCES school ID |
| `tract` | Census tract (integer) |
| `block_group` | Block group number |
| `geoid_block` | Full block identifier |
| `census_region` | Census Bureau region (1-4, 9) |
| `census_division` | Census Bureau division (1-9) |
| `cbsa` | CBSA code (if applicable) |
| `cbsa_type` | Metropolitan (1) or Micropolitan (2) |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-2` | Not geocoded | `geocode_accuracy` field in Portal data |
| `-1` | Missing/not reported | General missing data indicator in Portal data |
| `9` | Unknown region | `census_region` when area not classified |
| `null` | Not available | Variable not applicable to this record |

> **Schema Difference:** Schools NHGIS files (47 columns) have a different schema than colleges NHGIS files (26 columns). Schools data includes more detailed geographic identifiers (block-level precision), while colleges data is primarily tract-level. Do not assume identical column structures when working with both.

## Data Access

### Dataset Paths

| Topic | Type | Huggingface Path |
|-------|------|------------------|
| Schools Census 1990 | Single | `schools/nhgis/census-1990/schools_nhgis_geog_1990` |
| Schools Census 2000 | Single | `schools/nhgis/census-2000/schools_nhgis_geog_2000` |
| Schools Census 2010 | Single | `schools/nhgis/census-2010/schools_nhgis_geog_2010` |
| Schools Census 2020 | Single | `schools/nhgis/census-2020/schools_nhgis_geog_2020` |
| Colleges Census 1990 | Single | `college-university/nhgis/census-1990/colleges_nhgis_geog_1990` |
| Colleges Census 2000 | Single | `college-university/nhgis/census-2000/colleges_nhgis_geog_2000` |
| Colleges Census 2010 | Single | `college-university/nhgis/census-2010/colleges_nhgis_geog_2010` |
| Colleges Census 2020 | Single | `college-university/nhgis/census-2020/colleges_nhgis_geog_2020` |

### Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| Schools Census 1990 | `schools/nhgis/census-1990/codebook_schools_nhgis_census1990` |
| Schools Census 2000 | `schools/nhgis/census-2000/codebook_schools_nhgis_census2000` |
| Schools Census 2010 | `schools/nhgis/census-2010/codebook_schools_nhgis_census2010` |
| Schools Census 2020 | `schools/nhgis/census-2020/codebook_schools_nhgis_census2020` |
| Colleges Census 1990 | `college-university/nhgis/census-1990/codebook_colleges_nhgis_census1990` |
| Colleges Census 2000 | `college-university/nhgis/census-2000/codebook_colleges_nhgis_census2000` |
| Colleges Census 2010 | `college-university/nhgis/census-2010/codebook_colleges_nhgis_census2010` |
| Colleges Census 2020 | `college-university/nhgis/census-2020/codebook_colleges_nhgis_census2020` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for the full catalog and `fetch-patterns.md` for `get_codebook_url()`. For human reference — not parsed programmatically.

### Example Fetch

```python
import polars as pl

# Load school-to-census links for 2020
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/nhgis/census-2020/schools_nhgis_geog_2020.parquet"
df = pl.read_parquet(url)

# Filter to California schools
df = df.filter(pl.col("fips") == 6)
```

### Filtering

```python
# Filter to a specific school
school_census = df.filter(pl.col("ncessch") == 60000100001)

# Filter to metropolitan areas only
metro = df.filter(pl.col("cbsa_type") == 1)

# Filter to a specific census region (South)
south = df.filter(pl.col("census_region") == 3)
```

### Direct NHGIS Access Methods

| Method | Best For | Registration |
|--------|----------|--------------|
| [Data Finder](https://data2.nhgis.org/main) | Interactive selection | Required (free) |
| [IPUMS API](https://developer.ipums.org/) | Programmatic access | Required (free) |
| [ipumsr (R)](https://tech.popdata.org/ipumsr/) | R workflows | Uses API key |
| [ipumspy (Python)](https://ipumspy.readthedocs.io/) | Python workflows | Uses API key |

> **Note**: The Portal provides pre-processed crosswalks; for custom geographic analysis, use NHGIS directly (requires free IPUMS registration).

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Boundary changes | Tracts split/merged between censuses break longitudinal analysis | Use crosswalks or geographically standardized tables |
| ACS margins of error | Small-area estimates have high uncertainty | Check MOE; aggregate areas if needed |
| Block data limitations | Only 100% count variables available (no income/poverty) | Use block groups for sample data (ACS) |
| GISJOIN vs GEOID | Different ID formats cause join failures | Use GISJOIN for NHGIS joins, GEOID for Census Bureau joins |
| 2020 Census noise | Differential privacy added noise to small-area counts | Check for negative values; prefer ACS for detailed characteristics |
| Schools vs colleges schema | Different column counts (47 vs 26) and geographic precision | Check schema before joining; do not assume identical structures |
| Using string codes | Portal data uses integer encodings, not string labels | Always verify codes against codebook (see encoding warning above) |

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ccd` | School identifiers for linking | Join school data to census geography via `ncessch` |
| `education-data-source-saipe` | District-level poverty | Use SAIPE for district poverty; NHGIS for tract/block group poverty |
| `education-data-source-meps` | School-level poverty | MEPS provides school-level poverty estimates; NHGIS provides community context |
| `education-data-source-ipeds` | College identifiers for linking | Join college data to census geography via `unitid` |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Census tract definition | `./references/geographic-units.md` |
| Block group definition | `./references/geographic-units.md` |
| School district boundaries | `./references/geographic-units.md` |
| School-to-tract linking | `./references/school-geography-links.md` |
| SABINS attendance areas | `./references/school-geography-links.md` |
| NCES EDGE files | `./references/school-geography-links.md` |
| Time series tables | `./references/time-series.md` |
| Geographic standardization | `./references/time-series.md` |
| Geographic crosswalks | `./references/time-series.md` |
| Population variables | `./references/variable-catalog.md` |
| Income/poverty variables | `./references/variable-catalog.md` |
| Education variables | `./references/variable-catalog.md` |
| Tract boundary changes | `./references/boundary-changes.md` |
| 2022 Connecticut changes | `./references/boundary-changes.md` |
| TIGER/Line versions | `./references/boundary-changes.md` |
| API access | `./references/data-access.md` |
| ipumspy Python package | `./references/data-access.md` |
| Data Finder workflow | `./references/data-access.md` |
