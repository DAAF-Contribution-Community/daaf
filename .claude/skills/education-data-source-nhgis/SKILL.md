---
name: education-data-source-nhgis
description: IPUMS NHGIS (National Historical Geographic Information System) census data source for education research. Use when working with census geography, demographic data for school communities, time series analysis, geographic crosswalks, or linking schools to census tracts/block groups.
metadata:
  audience: data-analysts
  domain: education-data
---

# NHGIS: National Historical Geographic Information System

Census geography and demographic data source for education research. NHGIS provides the foundation for linking schools to community characteristics.

> **CRITICAL: Portal Integer Encodings**
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
> See `references/variable-catalog.md` for complete encoding tables.

## What is NHGIS?

NHGIS (from IPUMS, University of Minnesota) provides free access to:

- **Summary tables**: Census data from 1790-present (decennial census + ACS)
- **GIS boundary files**: States, counties, tracts, blocks, school districts
- **Time series tables**: Harmonized data across census years
- **Geographic crosswalks**: Allocate data between different census geographies

**Key for education research**: Links school locations to community demographics via census tracts, block groups, and school district boundaries.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `geographic-units.md` | Census geography hierarchy (tracts, blocks, districts) | Understanding census geography |
| `school-geography-links.md` | Linking schools to census areas | Connecting school data to demographics |
| `time-series.md` | Historical data, harmonization methods | Longitudinal analysis |
| `variable-catalog.md` | Key demographic variables for education | Selecting census variables |
| `boundary-changes.md` | How boundaries change between censuses | Handling geographic inconsistencies |
| `data-access.md` | API, Python/R packages, data extraction | Downloading NHGIS data |

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

## Quick Reference: Geographic Levels

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

## Quick Reference: Key Education Variables

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

## Quick Reference: Data Sources

| Source | Years | Geographic Detail | Content |
|--------|-------|-------------------|---------|
| Decennial Census | 1790-2020 | Block (1990+) | 100% count: age, sex, race, housing |
| ACS 5-Year | 2005-2023 | Block group | Sample: income, education, language |
| ACS 1-Year | 2010-2023 | Areas 65K+ pop | Sample: same as 5-year |
| Time Series | 1790-2020 | Varies | Harmonized across years |
| Geographic Crosswalks | 1990-2020 | Block+ | Interpolation weights |

## NHGIS in Education Data Portal

The Urban Institute Education Data Portal includes NHGIS-derived data linking schools to census geography.

> **Schema Difference:** Schools NHGIS files (47 columns) have a different schema than colleges NHGIS files (26 columns). Schools data includes more detailed geographic identifiers (block-level precision), while colleges data is primarily tract-level. Do not assume identical column structures when working with both.

### Available via HuggingFace Mirror

| Mirror Path | Census Year | Content |
|-------------|-------------|---------|
| `schools/nhgis/census-1990/` | 1990 | School-to-tract links |
| `schools/nhgis/census-2000/` | 2000 | School-to-tract links |
| `schools/nhgis/census-2010/` | 2010 | School-to-tract links |
| `schools/nhgis/census-2020/` | 2020 | School-to-tract links |

### Key Variables in Portal NHGIS Data

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

### Accessing Data

```python
import polars as pl

# Load school-to-census links for 2020
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/nhgis/census-2020/schools_nhgis_geog_2020.parquet"
df = pl.read_parquet(url)

# Filter to specific school
school_census = df.filter(pl.col("ncessch") == 60000100001)
```

**Note**: The Portal provides pre-processed crosswalks; for custom geographic analysis, use NHGIS directly (requires free IPUMS registration).

## Data Access Methods

| Method | Best For | Registration |
|--------|----------|--------------|
| [Data Finder](https://data2.nhgis.org/main) | Interactive selection | Required (free) |
| [IPUMS API](https://developer.ipums.org/) | Programmatic access | Required (free) |
| [ipumsr (R)](https://tech.popdata.org/ipumsr/) | R workflows | Uses API key |
| [ipumspy (Python)](https://ipumspy.readthedocs.io/) | Python workflows | Uses API key |

## Common Pitfalls

| Issue | Problem | Solution |
|-------|---------|----------|
| Boundary changes | Tracts split/merged between censuses | Use crosswalks or standardized tables |
| ACS margins of error | Small-area estimates have high uncertainty | Check MOE; aggregate areas if needed |
| Block data limitations | Only 100% count variables (no income) | Use block groups for sample data |
| GISJOIN vs GEOID | Different ID formats | Use GISJOIN for NHGIS joins |
| 2020 Census issues | Differential privacy added noise | Check for negative values; use ACS |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Census tract definition | `geographic-units.md` |
| Block group definition | `geographic-units.md` |
| School district boundaries | `geographic-units.md` |
| School-to-tract linking | `school-geography-links.md` |
| SABINS attendance areas | `school-geography-links.md` |
| NCES EDGE files | `school-geography-links.md` |
| Time series tables | `time-series.md` |
| Geographic standardization | `time-series.md` |
| Geographic crosswalks | `time-series.md` |
| Population variables | `variable-catalog.md` |
| Income/poverty variables | `variable-catalog.md` |
| Education variables | `variable-catalog.md` |
| Tract boundary changes | `boundary-changes.md` |
| 2022 Connecticut changes | `boundary-changes.md` |
| TIGER/Line versions | `boundary-changes.md` |
| API access | `data-access.md` |
| ipumspy Python package | `data-access.md` |
| Data Finder workflow | `data-access.md` |
