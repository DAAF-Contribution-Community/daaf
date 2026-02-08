# MEPS API Usage (Legacy Reference)

> **LEGACY REFERENCE:** This file documents the deprecated REST API approach for accessing MEPS data. Data is now fetched via configured mirrors (see `education-data-query` skill and `mirrors.yaml`). This file is retained for reference on API structure and variable documentation only.

How to query Model Estimates of Poverty in Schools via the Urban Institute Education Data Portal API.

> **CRITICAL: Portal Data Encoding**
>
> Portal returns MEPS data with integer-encoded IDs and native nulls:
> - `ncessch`, `leaid`, `fips` are **Int64** (not strings)
> - Missing values are **null** (not -1, -2, -3)
> - Years available: **2009-2022** (actual data range)
>
> See `variable-definitions.md` for complete type mappings.

## API Endpoint

### Base URL

```
https://educationdata.urban.org/api/v1/schools/meps/{year}/
```

### URL Pattern

```
/api/v1/schools/meps/{year}/[?optional_filters]
```

| Component | Description | Example |
|-----------|-------------|---------|
| `{year}` | School year (required) | `2018` |
| `?filters` | Query parameters | `?fips=6` |

## Available Years

MEPS data is available for:
- **Actual Portal range**: 2009-2022 (as of last verification)
- **MEPS 1.0 documentation**: 2006-2019
- **MEPS 2.0**: Extended range (December 2025 release)

To check available years:
```
GET /api/v1/schools/meps/
```

> **Note:** Documentation may cite 2006-2019, but actual Portal data starts at 2009.

## Query Parameters

### Filtering

| Parameter | Description | Example |
|-----------|-------------|---------|
| `fips` | State FIPS code | `?fips=6` (California) |
| `leaid` | District ID | `?leaid=0600001` |
| `ncessch` | School ID | `?ncessch=060000100001` |

### Pagination

| Parameter | Description | Default |
|-----------|-------------|---------|
| `page` | Page number | 1 |
| `per_page` | Results per page | 100 (max 10000) |

### Multiple Filters

Combine filters with `&`:
```
?fips=6&per_page=1000
```

## Example API Calls

### All Schools in a State

**California (FIPS=6), 2018:**
```
GET https://educationdata.urban.org/api/v1/schools/meps/2018/?fips=6
```

### Specific District

**Los Angeles Unified (LEAID=0622710), 2018:**
```
GET https://educationdata.urban.org/api/v1/schools/meps/2018/?leaid=0622710
```

### Specific School

**School ID 060000100001, 2018:**
```
GET https://educationdata.urban.org/api/v1/schools/meps/2018/?ncessch=060000100001
```

### Large Result Set

**All schools nationwide, 2018:**
```
GET https://educationdata.urban.org/api/v1/schools/meps/2018/?per_page=10000
```

Note: May require pagination for full dataset.

## Response Format

### JSON Structure

```json
{
    "count": 1234,
    "next": "https://educationdata.urban.org/api/v1/schools/meps/2018/?page=2",
    "previous": null,
    "results": [
        {
            "ncessch": "060000100001",
            "year": 2018,
            "fips": 6,
            "leaid": "0600001",
            "meps": 0.245,
            "meps_mod": 0.251,
            "meps_se": 0.032
        },
        ...
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `count` | Integer | Total matching records |
| `next` | String/null | URL for next page |
| `previous` | String/null | URL for previous page |
| `results` | Array | Data records |

### Record Fields (Portal Encoding)

| Field | Type | Notes |
|-------|------|-------|
| `ncessch` | Integer | 12-digit school ID as integer |
| `year` | Integer | Academic year |
| `fips` | Integer | State FIPS (1-56) |
| `leaid` | Integer | 7-digit district ID as integer |
| `gleaid` | Integer | Geographic LEA ID |
| `meps_poverty_pct` | Float | Poverty percentage (0-100 scale) |
| `meps_mod_poverty_pct` | Float | Modified estimate |
| `meps_poverty_se` | Float | Standard error |
| `meps_poverty_ptl` | Integer | Poverty percentile (1-100) |
| `meps_mod_poverty_ptl` | Integer | Modified percentile |

## Using Python

### Basic Request

```python
import requests

url = "https://educationdata.urban.org/api/v1/schools/meps/2018/"
params = {"fips": 6, "per_page": 1000}

response = requests.get(url, params=params)
data = response.json()

print(f"Total records: {data['count']}")
for school in data['results'][:5]:
    print(f"{school['ncessch']}: {school['meps']:.1%}")
```

### Paginated Retrieval

```python
import requests
import pandas as pd

def get_all_meps(year, **filters):
    """Retrieve all MEPS records with pagination."""
    base_url = f"https://educationdata.urban.org/api/v1/schools/meps/{year}/"
    all_records = []
    
    params = {"per_page": 10000, **filters}
    url = base_url
    
    while url:
        response = requests.get(url, params=params if url == base_url else None)
        data = response.json()
        all_records.extend(data['results'])
        url = data.get('next')
        print(f"Retrieved {len(all_records)} of {data['count']} records...")
    
    return pd.DataFrame(all_records)

# Get all California schools
df = get_all_meps(2018, fips=6)
print(f"Retrieved {len(df)} schools")
```

### Using the `educationdata` Package

```python
# Install: pip install educationdata
from educationdata import get_education_data

# Get MEPS data
df = get_education_data(
    level='schools',
    source='meps',
    filters={'year': 2018, 'fips': 6}
)

print(df.head())
```

## Using R

### Using `educationdata` Package

```r
# Install: install.packages("educationdata")
library(educationdata)

# Get MEPS data for California 2018
df <- get_education_data(
    level = "schools",
    source = "meps",
    filters = list(year = 2018, fips = 6)
)

head(df)
summary(df$meps)
```

### Basic HTTP Request

```r
library(httr)
library(jsonlite)

url <- "https://educationdata.urban.org/api/v1/schools/meps/2018/"

response <- GET(url, query = list(fips = 6, per_page = 1000))
data <- fromJSON(content(response, "text"))

print(paste("Total records:", data$count))
head(data$results)
```

## Using Stata

### Using `educationdata` Package

```stata
* Install: ssc install educationdata

* Get MEPS data
educationdata, level(schools) source(meps) filters(year==2018 fips==6) clear

* Summarize
summarize meps
```

## Bulk Downloads

For large analyses, consider bulk CSV downloads:

1. Visit: https://educationdata.urban.org/data-explorer/
2. Select "Schools" → "MEPS"
3. Choose years and filters
4. Download CSV

Benefits:
- Faster than API for full datasets
- No pagination needed
- Can be scheduled

## Joining MEPS with Other Data

### Join with CCD Directory

```python
# Get MEPS
meps_df = get_education_data(
    level='schools', source='meps',
    filters={'year': 2018, 'fips': 6}
)

# Get CCD directory
ccd_df = get_education_data(
    level='schools', source='ccd', topic='directory',
    filters={'year': 2018, 'fips': 6}
)

# Join on school ID and year
merged = meps_df.merge(
    ccd_df, 
    on=['ncessch', 'year'],
    how='left'
)
```

### Join with EDFacts Assessments

```python
# Get MEPS
meps_df = get_education_data(
    level='schools', source='meps',
    filters={'year': 2018}
)

# Get assessment data
assess_df = get_education_data(
    level='schools', source='edfacts', topic='assessments',
    subtopic=['grade-8'],
    filters={'year': 2018}
)

# Join
merged = meps_df.merge(
    assess_df,
    on=['ncessch', 'year'],
    how='inner'
)
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 404 Not Found | Invalid year or endpoint | Check available years |
| 400 Bad Request | Invalid parameter | Verify filter values |
| Empty results | No matching data | Broaden filters |
| Timeout | Large request | Add filters or paginate |

### Python Error Handling

```python
import requests

def safe_meps_request(year, **filters):
    """Make MEPS API request with error handling."""
    url = f"https://educationdata.urban.org/api/v1/schools/meps/{year}/"
    
    try:
        response = requests.get(url, params=filters, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code}")
        return None
    except requests.exceptions.Timeout:
        print("Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
```

## Rate Limiting and Best Practices

### Best Practices

1. **Use pagination** for large requests
2. **Cache results** to avoid redundant calls
3. **Request specific years** rather than all years
4. **Use filters** to reduce response size
5. **Consider bulk downloads** for full datasets

### Example: Efficient Multi-Year Query

```python
import time

def get_multi_year_meps(years, **filters):
    """Efficiently retrieve MEPS for multiple years."""
    all_data = []
    
    for year in years:
        print(f"Fetching {year}...")
        df = get_all_meps(year, **filters)
        all_data.append(df)
        time.sleep(0.5)  # Brief pause between years
    
    return pd.concat(all_data, ignore_index=True)

# Get 2015-2018 for California
df = get_multi_year_meps([2015, 2016, 2017, 2018], fips=6)
```

## Quick Reference

### Common Queries

| Query | URL |
|-------|-----|
| All 2018 | `/api/v1/schools/meps/2018/` |
| California 2018 | `/api/v1/schools/meps/2018/?fips=6` |
| Texas 2017 | `/api/v1/schools/meps/2017/?fips=48` |
| Specific school | `/api/v1/schools/meps/2018/?ncessch=060000100001` |

### State FIPS Codes (Common)

| State | FIPS |
|-------|------|
| California | 6 |
| Texas | 48 |
| New York | 36 |
| Florida | 12 |
| Illinois | 17 |
| Pennsylvania | 42 |
| Ohio | 39 |
| Michigan | 26 |
| Georgia | 13 |
| North Carolina | 37 |

Full list: See `education-data-explorer` skill → `variable-codes.md`
