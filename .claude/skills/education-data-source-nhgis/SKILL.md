---
name: education-data-source-nhgis
description: >-
  NHGIS — census geography crosswalks via Portal: links schools (ncessch) and colleges (unitid) to census tracts, block groups, CBSAs, and regions (census-geography vintages 1990-2020; mirror file-year/linkage coverage 1980, 1984-2023). Portal provides geography linkage tables ONLY; browse census demographics in the public NHGIS Data Finder, then sign in with a free IPUMS NHGIS account to submit, manage, or download extracts. API extract requests also need an API key. Use for linking education or institutional data to census geography.
metadata:
  audience: any-agent
  domain: data-source
  skill-authored: "2026-02-09"
  skill-last-updated: "2026-10-27"
---

# NHGIS Data Source Reference

IPUMS NHGIS — census geography crosswalks and demographic data for education research. Via the Education Data Portal: geographic crosswalk tables linking K-12 schools (ncessch) and colleges (unitid) to census tracts, block groups, CBSAs, and regions. The `1990-2020` here denotes the **census-geography vintages** the crosswalks resolve to; the mirror files themselves span **1980, 1984-2023** file-years (the education/institution linkage years). See `datasets-reference.md` for per-file year ranges. Census demographic variables (income, poverty, race, educational attainment) are NOT in the Portal. Browse those variables publicly in the NHGIS Data Finder; sign in with a free IPUMS NHGIS account to submit, manage, or download extracts, and use an API key for API extract requests. Use when linking school or institutional data to census geography for contextual analysis.

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
> | `geocode_accuracy` | `-2`, or a score up to `100` (not a code) | Esri geocoder match score (100 = perfect match; observed minimum 61 in colleges, 4 in schools). Every row is `-2` in college years 2018-2023 and school years 2017-2023. The codebook's 1-4 labels do not describe the data (pinned mirror, probed 2026-10-27) |
>
> See `./references/variable-catalog.md` for complete encoding tables.

> **CRITICAL: Portal Data Scope**
>
> The Education Data Portal provides ONLY **geographic crosswalk tables** that link schools and colleges to census geography (tracts, block groups, regions, CBSAs). These contain geographic identifiers and assignment columns — approximately 35-47 columns per file.
>
> The Portal does **NOT** provide census demographic data (population, income, poverty, race, education attainment, housing, language, etc.). For demographic variables, browse the public NHGIS Data Finder, then use a free IPUMS NHGIS account to submit, manage, or download an extract. API extract requests additionally require an API key. See `./references/data-access.md` for direct access methods.
>
> This skill documents both contexts: Portal crosswalk data (with integer encodings above) and direct NHGIS census variables (in `./references/variable-catalog.md`). Direct NHGIS products remain subject to separate IPUMS terms, citation requirements, and redistribution restrictions; the Portal's ODC-By terms do not automatically apply to them.

## What is NHGIS?

NHGIS (from IPUMS, University of Minnesota) provides free access to census geography and demographic data.

- **Collector**: IPUMS, University of Minnesota
- **Coverage**: US census data from 1790-present (decennial census + ACS)
- **Content**: Summary tables, GIS boundary files, time series tables, geographic crosswalks
- **Frequency**: Decennial census (every 10 years) + ACS (annual, 5-year rolling)
- **Available years**: 1790-2020 (decennial), 2005-2009 through 2020-2024 (ACS 5-year; 2020-2024 added February 2026)
- **Primary identifiers**: GISJOIN (NHGIS internal), GEOID (Census Bureau standard)
- **Education relevance**: Links school locations to community demographics via census tracts, block groups, and school district boundaries
- **Available through Education Data Portal**: Geographic crosswalk tables only (school-to-census and college-to-census links for census 1990, 2000, 2010, 2020). Census demographic data requires direct NHGIS access.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `geographic-units.md` | Census geography hierarchy (tracts, blocks, districts) | Understanding census geography |
| `school-geography-links.md` | Linking schools to census areas | Connecting school data to demographics |
| `time-series.md` | Historical data, harmonization methods | Longitudinal analysis |
| `variable-catalog.md` | Key demographic variables, codes, special values | Selecting census variables or interpreting encodings |
| `boundary-changes.md` | How boundaries change between censuses | Handling geographic inconsistencies |
| `data-access.md` | Direct NHGIS access methods (registration, Data Finder, ipumspy) | Custom census analysis beyond Portal |

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
│   ├─ 2009-10 or 2010-11 data (2011-12: Minnesota only) → SABINS school areas
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
| `ncessch` | Int64 | School | `10000201704` | NCES school ID (schools Portal data) |
| `unitid` | Int64 | College | `100654` | IPEDS institution ID (colleges Portal data) |
| `GISJOIN` | String with prefix | Any | `G0600010` | NHGIS internal ID; use for direct NHGIS joins (not in Portal data) |
| `GEOID` | Numeric string | Any | `06001402100` | Census Bureau standard; use for non-NHGIS joins (not in Portal data) |
| `tract` | Int64 | Tract | `402100` | Census tract number (in Portal data) |
| `block_group` | Int64 | Block Group | `1` | Block group within tract (1-9; 0=unassigned) |
| `geoid_block` | Int64 | Varies by census vintage | `10730118025` (2010 file) | Despite the name and "Block identifier" label, never a 15-digit block GEOID; its form depends on the census-vintage file (observed on Portal v0.26.1 / HF revision `0ad00ce0`, probed 2026-10-27: rebuilt from the file's own columns in the four college files and the 1990/2010 school files; the 2000/2020 school files checked by leading digits only). **2010/2020 files:** the 12-digit block-group GEOID (state+county+tract+block group). **1990 files:** the 11-digit tract GEOID (state+county+tract). **2000 files:** encoding not identified; it matches neither form rebuilt from the file's own columns, so do not treat it as a block or block-group GEOID. Stored as Int64 in every file, so the leading zero drops for states with FIPS < 10; zero-pad (12 or 11 digits) before joining |
| `cbsa` | Int64 | Metro area | `41860` | Core Based Statistical Area code (2000+ census files only) |

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
| ACS 5-Year | 2005-2009 through 2020-2024 | Block group | Sample: income, education, language |
| ACS 1-Year | through 2024 (no 2020 1-year data in NHGIS) | Areas 65K+ pop | Sample: same as 5-year |
| Time Series | 1790-2020 | Varies | Harmonized across years |
| Geographic Crosswalks | 1990-2020 | Block+ | Interpolation weights |

### Portal Variables (Schools NHGIS)

Key geographic and identifying columns in the schools NHGIS datasets. Census 2020 files have 47 columns; earlier census years have fewer (e.g., 1990 has 35 columns — no CBSA or legislative district fields).

| Variable | Description | Type |
|----------|-------------|------|
| `ncessch` | NCES school ID | Int64 |
| `leaid` | NCES district ID | Int64 |
| `tract` | Census tract number | Int64 |
| `block_group` | Block group number (1-9; 0 = unassigned) | Int64 |
| `geoid_block` | 12-digit block-group GEOID in the 2010/2020 files; 11-digit tract GEOID in the 1990 file; unidentified encoding in the 2000 file. Never a 15-digit block ID; zero-pad before use (see Key Identifiers) | Int64 |
| `census_region` | Census Bureau region (1-4, 9) | Int64 |
| `census_division` | Census Bureau division (1-9) | Int64 |
| `cbsa` | CBSA code (2000+ census files only) | Int64 |
| `cbsa_type` | Metropolitan (1) or Micropolitan (2) | Int64 |
| `cbsa_city` | Principal city indicator (0=No, 1=Yes; 2000+ only). See note below. | Int64 |
| `geocode_accuracy` | Geocode match score up to 100 (100 = perfect match; Esri geocoder score). The Portal codebook lists 1=High/2=Medium/3=Low/4=Did not geocode/-2=Not applicable, but the pinned mirror (probed 2026-10-27) holds scores of 4-100 in the school files (only 2 rows at or below 4; 805 nulls) and `-2` for every row in school years 2017-2023. Filter on the score, not on the 1-4 codes, and treat 2017 onward as unscored | Float64 |
| `geocode_accuracy_detailed` | Geocode match type (1-12) | Int64 |
| `class_code` | FIPS place class code | Int64 |
| `lower_chamber_type` | State legislative district lower chamber type (1-8; census 2010 and census 2020 files). See `variable-catalog.md` for code mapping. | Int64 |
| `geo_latitude` / `geo_longitude` | Geocoded coordinates | Float64 |
| `latitude` / `longitude` | CCD-reported coordinates (many nulls in early years) | Float64 |
| `fips` | State FIPS code | Int64 |
| `puma` | Public Use Microdata Area (2000+ census files only) | Int64 |

### Portal Variables (Colleges NHGIS)

Colleges NHGIS datasets have 38 columns (2020 census). Different identifier set from schools.

| Variable | Description | Type |
|----------|-------------|------|
| `unitid` | IPEDS institution ID | Int64 |
| `opeid` | Office of Postsecondary Education ID | String |
| `tract` | Census tract number | Int64 |
| `block_group` | Block group number (1-9) | Int64 |
| `geoid_block` | 12-digit block-group GEOID in the 2010/2020 files; 11-digit tract GEOID in the 1990 file; unidentified encoding in the 2000 file. Never a 15-digit block ID; zero-pad before use (see Key Identifiers) | Int64 |
| `census_region` | Census Bureau region (1-4, 9) | Int64 |
| `census_division` | Census Bureau division (1-9) | Int64 |
| `cbsa` | CBSA code | Int64 |
| `cbsa_type` | Metropolitan (1) or Micropolitan (2) | Int64 |
| `cbsa_city` | Principal city indicator (0=No, 1=Yes; 2000+ only) | Int64 |
| `geocode_accuracy` | Geocode match score (Int64 in colleges, Float64 in schools); observed 61-100 in the college files, and `-2` for every row in college years 2018-2023 (pinned mirror, probed 2026-10-27) | Int64 |
| `county_fips` | County FIPS code | Int64 |
| `county_name` | County name | String |
| `state_abbr` | State abbreviation | String |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-2` | Not applicable (codebook label) | `geocode_accuracy` in Portal data: every row in college years 2018-2023 and school years 2017-2023, none earlier (pinned mirror, probed 2026-10-27) |
| `-1` | Missing/not reported | General missing data indicator (e.g., `latitude`, `county_code`) |
| `0` | Unassigned | `block_group` (rare, ~4 rows in schools) |
| `null` | Not available | Variable not applicable to this record; many columns heavily null in early years |

> **Schema Difference:** Schools NHGIS 2020 files (47 columns) have a different schema than colleges NHGIS 2020 files (38 columns). Schools data includes school-specific identifiers (`ncessch`, `leaid`, `school_name`, mailing/location address fields) while colleges data includes institution-specific identifiers (`unitid`, `opeid`, `inst_name`, `county_name`). Both entity types have block-level geographic precision. Earlier census years have fewer columns (e.g., Schools 1990 has 35 columns — no CBSA or legislative district fields). Do not assume identical column structures when working across entities or census years.

## Data Access

Datasets for NHGIS are available via the mirror system. See `datasets-reference.md` for canonical paths, `mirrors.yaml` for mirror configuration, and `fetch-patterns.md` for fetch code patterns.

| Dataset | Type | Years | Path | Codebook |
|---------|------|-------|------|----------|
| Schools Census 1990 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_1990` | `nhgis/codebook_schools_nhgis_census1990` |
| Schools Census 2000 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_2000` | `nhgis/codebook_schools_nhgis_census2000` |
| Schools Census 2010 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_2010` | `nhgis/codebook_schools_nhgis_census2010` |
| Schools Census 2020 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_2020` | `nhgis/codebook_schools_nhgis_census2020` |
| Colleges Census 1990 | Single | 1980, 1984-2023 | `nhgis/colleges_nhgis_geog_1990` | `nhgis/codebook_colleges_nhgis_census1990` |
| Colleges Census 2000 | Single | 1980, 1984-2023 | `nhgis/colleges_nhgis_geog_2000` | `nhgis/codebook_colleges_nhgis_census2000` |
| Colleges Census 2010 | Single | 1980, 1984-2023 | `nhgis/colleges_nhgis_geog_2010` | `nhgis/codebook_colleges_nhgis_census2010` |
| Colleges Census 2020 | Single | 1980, 1984-2023 | `nhgis/colleges_nhgis_geog_2020` | `nhgis/codebook_colleges_nhgis_census2020` |

Codebooks are `.xls` files co-located with data in all mirrors. Use `get_codebook_url()` from `fetch-patterns.md` to construct download URLs.

> **Truth Hierarchy:** When interpreting variable values, apply this priority:
> 1. **Actual data file** (what you observe in the parquet/CSV) — this IS the truth
> 2. **Live codebook** (.xls in mirror) — authoritative documentation, may lag
> 3. **This skill documentation** — convenient summary, may drift from codebook
>
> If this documentation contradicts the codebook, trust the codebook. If the codebook contradicts observed data, trust the data and investigate.

### Filtering

```python
import polars as pl

# Filter to a specific school
school_census = df.filter(pl.col("ncessch") == 10000201704)

# Filter to metropolitan areas only (cbsa_type only in 2000+ census files)
metro = df.filter(pl.col("cbsa_type") == 1)

# Filter to a specific census region (South)
south = df.filter(pl.col("census_region") == 3)

# Filter to a specific year
recent = df.filter(pl.col("year") == 2023)
```

```r
library(dplyr)

# Filter to a specific school
school_census <- df |> filter(ncessch == 10000201704)

# Filter to metropolitan areas only (cbsa_type only in 2000+ census files)
metro <- df |> filter(cbsa_type == 1)

# Filter to a specific census region (South)
south <- df |> filter(census_region == 3)

# Filter to a specific year
recent <- df |> filter(year == 2023)
```

> **Direct-access note:** The Portal provides pre-processed school/college-to-census-geography links. For custom census analysis (tract-level demographics, time series, boundary files), browse the NHGIS Data Finder without signing in; a free IPUMS NHGIS account and login are required to submit, manage, or download extracts, and API requests additionally need an API key. See `./references/data-access.md`. Direct NHGIS data is governed by separate IPUMS terms and citation requirements.

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Boundary changes | Tracts split/merged between censuses break longitudinal analysis | Use crosswalks or geographically standardized tables |
| ACS margins of error | Small-area estimates have high uncertainty | Check MOE; aggregate areas if needed |
| Block data limitations | Only 100% count variables available (no income/poverty) | Use block groups for sample data (ACS) |
| GISJOIN vs GEOID | Different ID formats cause join failures | Use GISJOIN for NHGIS joins, GEOID for Census Bureau joins |
| 2020 Census noise | Differential privacy added noise to small-area counts; post-processing forces published counts to be nonnegative integers, biasing small counts up and large counts down | Treat block and block-group 2020 counts as noisy; aggregate or prefer ACS for detailed characteristics |
| Schools vs colleges schema | Different column counts (47 vs 38 for 2020) and identifier sets | Check schema before joining; do not assume identical structures |
| Census year schema drift | Earlier census files have fewer columns (e.g., 1990 lacks CBSA/legislative fields) | Check available columns per census year before relying on them |
| geocode_accuracy type | Float64 in schools, Int64 in colleges | Cast to consistent type before cross-entity comparison |
| Treating `geoid_block` as one ID type | Its form changes by census-vintage file: block-group GEOID (2010/2020), tract GEOID (1990), unidentified (2000); Int64, so leading zeros are lost | Zero-pad, and check the file's vintage before joining; do not join the 2000 file's `geoid_block` to block or block-group data |
| Trusting 1990/2000 geo FIPS columns | Observed on the pinned mirror (Portal v0.26.1 / HF revision `0ad00ce0`, probed 2026-10-27 over all rows with positive codes in all 8 files): in the 1990 files `state_fips_geo` is the state FIPS × 10 (Ohio = 390, Alabama = 10; 331,043 of 331,049 college rows and 3,627,315 of 3,627,352 school rows, against the same record's 2010-file value), while `county_fips_geo` is a correct 5-digit state+county code. In the 2000 files `state_fips_geo` is correct but `county_fips_geo` is not a county FIPS code (values 10-990, never 5-digit; about 70% equal 10 × the 3-digit county code, e.g. Ohio county 057 → 570). The 2010/2020 files are consistent | For state, use `fips` (or the leading digits of the 1990 `county_fips_geo`). For county in the 2000 files, use the 2010/2020 file of the same record, or `county_fips` (colleges) / `county_code` (schools), which mostly carry state+county codes (school `county_code` values start at 7, so check the width) but are not always populated (every checked row of the 2000 college file, about 61% of school rows; about a third of college rows in the other vintages) |
| Using string codes | Portal data uses integer encodings, not string labels | Always verify codes against codebook (see encoding warning above) |

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ccd` | School identifiers for linking | Join school data to census geography via `ncessch` |
| `education-data-source-saipe` | District-level poverty | Use SAIPE for district poverty; NHGIS for tract/block group poverty |
| `education-data-source-meps` | School-level poverty | MEPS provides school-level poverty estimates; NHGIS provides community context |
| `education-data-source-ipeds` | College identifiers for linking | Join college data to census geography via `unitid` |
| `education-data-explorer` | Parent discovery skill | Routing questions to mirror dataset files |
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
| Direct NHGIS access | `./references/data-access.md` |
| ipumspy Python package | `./references/data-access.md` |
| Data Finder workflow | `./references/data-access.md` |
