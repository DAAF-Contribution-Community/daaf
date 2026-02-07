# EADA API Endpoints

Guide to accessing EADA data through the Urban Institute Education Data Portal.

## Overview

EADA data is available through the Urban Institute's Education Data Portal as part of the college-university data level.

**Base URL**: `https://educationdata.urban.org/api/v1/`

> **CRITICAL: Portal Integer Encoding**
>
> The Portal returns **integer codes** for categorical variables. When filtering:
>
> ```python
> # Filter by state using integer FIPS code
> eada_ca = get_eada_data(2022, fips=6)  # California = 6, NOT "CA"
>
> # Filter by athletic classification
> ncaa_d1_fbs = df.filter(pl.col("ath_classification_code") == 1)  # NCAA D1 FBS
> ```
>
> Missing data codes: `-1` (missing), `-2` (not applicable), `-3` (suppressed)

## Endpoint Structure

### Institution-Level EADA Data

```
/college-university/eada/{year}/
```

**Example**:
```
https://educationdata.urban.org/api/v1/college-university/eada/2022/
```

### Years Available

| Earliest | Latest | Notes |
|----------|--------|-------|
| 2003 | 2022 | Annual updates |

Check the Education Data Portal documentation for the most current year available.

## Query Parameters

### Filtering

| Parameter | Description | Example |
|-----------|-------------|---------|
| `unitid` | IPEDS institution ID | `?unitid=110635` |
| `fips` | State FIPS code | `?fips=6` (California) |
| `sector` | Institutional sector | `?sector=1` (Public) |

### Pagination

| Parameter | Description | Default |
|-----------|-------------|---------|
| `page` | Page number | 1 |
| `per_page` | Results per page | 1000 (max 10000) |

### Example with Filters

```
/college-university/eada/2022/?fips=6&sector=1&per_page=5000
```

## Response Format

### JSON Structure

```json
{
  "count": 2500,
  "next": "https://educationdata.urban.org/api/v1/.../&page=2",
  "previous": null,
  "results": [
    {
      "unitid": 110635,
      "year": 2022,
      "partic_men": 250,
      "partic_women": 200,
      ...
    }
  ]
}
```

## Using R Package

### Installation

```r
install.packages('educationdata')
```

### Basic Query

```r
library(educationdata)

# Get EADA data for a specific year
eada_data <- get_education_data(
  level = 'college-university',
  source = 'eada',
  topic = '',
  filters = list(year = 2022)
)
```

### With Filters

```r
# California public institutions
eada_ca_public <- get_education_data(
  level = 'college-university',
  source = 'eada',
  topic = '',
  filters = list(
    year = 2022,
    fips = 6,
    sector = 1
  )
)
```

### Multiple Years

```r
# Get multiple years
eada_trend <- get_education_data(
  level = 'college-university',
  source = 'eada',
  topic = '',
  filters = list(year = 2018:2022)
)
```

## Using Stata Package

### Installation

```stata
ssc install libjson
ssc install educationdata, replace
```

### Basic Query

```stata
educationdata using "college-university eada", sub(year=2022) clear
```

### With Filters

```stata
educationdata using "college-university eada", ///
  sub(year=2022 fips=6) clear
```

## Using Python

### Direct API Access

```python
import requests
import pandas as pd

def get_eada_data(year, **filters):
    """Fetch EADA data from Urban Institute API."""
    base_url = "https://educationdata.urban.org/api/v1"
    endpoint = f"/college-university/eada/{year}/"
    
    params = {k: v for k, v in filters.items()}
    params['per_page'] = 10000
    
    all_results = []
    page = 1
    
    while True:
        params['page'] = page
        response = requests.get(base_url + endpoint, params=params)
        data = response.json()
        all_results.extend(data['results'])
        
        if data['next'] is None:
            break
        page += 1
    
    return pd.DataFrame(all_results)

# Example usage
eada_2022 = get_eada_data(2022, fips=6)
```

### Using educationdata Package (if available)

```python
# Check Urban Institute GitHub for Python package updates
```

## Common Query Patterns

### Single Institution Time Series

```python
# Track one institution over time
years = range(2018, 2023)
institution_data = []

for year in years:
    data = get_eada_data(year, unitid=110635)
    institution_data.append(data)

trend_df = pd.concat(institution_data)
```

### State-Level Analysis

```python
# All institutions in a state
state_data = get_eada_data(2022, fips=6)  # California
```

### Sector Comparison

```python
# Compare public vs private
public = get_eada_data(2022, sector=1)
private_nonprofit = get_eada_data(2022, sector=2)
```

## Joining with IPEDS Data

### Why Join?

EADA data lacks:
- Enrollment counts (needed for proportionality)
- Institution characteristics
- Carnegie classification
- Geographic details

### Join Key

Use `unitid` and `year` to join:

```python
# Get IPEDS directory data
ipeds_dir = get_education_data(
    level='college-university',
    source='ipeds',
    topic='directory',
    filters={'year': 2022}
)

# Join
merged = eada_data.merge(
    ipeds_dir[['unitid', 'year', 'inst_name', 'stabbr', 
               'enrollment_fte', 'enrollment_women']],
    on=['unitid', 'year'],
    how='left'
)
```

### Key IPEDS Variables to Join

| Variable | Source | Purpose |
|----------|--------|---------|
| `enrollment` | Directory | Total enrollment for ratios |
| `enrollment_women` | Directory | Female enrollment |
| `inst_control` | Directory | Public/private indicator |
| `carnegie_class` | Characteristics | Institution type |
| `hbcu`, `tribal` | Directory | Special designation |

## Calculating Key Metrics

### Participation Proportionality

```python
# After joining with IPEDS enrollment
df['female_partic_pct'] = df['partic_women'] / (df['partic_men'] + df['partic_women'])
df['female_enroll_pct'] = df['enrollment_women'] / df['enrollment']
df['participation_gap'] = df['female_enroll_pct'] - df['female_partic_pct']
```

### Aid Proportionality

```python
df['aid_total'] = df['aid_men'] + df['aid_women']
df['aid_women_pct'] = df['aid_women'] / df['aid_total']
df['aid_gap'] = df['female_partic_pct'] - df['aid_women_pct']
```

### Investment Per Athlete

```python
df['exp_per_male'] = df['exp_men'] / df['partic_men']
df['exp_per_female'] = df['exp_women'] / df['partic_women']
df['investment_ratio'] = df['exp_per_female'] / df['exp_per_male']
```

## Handling Large Datasets

### Pagination

The API limits to 10,000 results per page. Always paginate:

```python
def get_all_pages(endpoint, params):
    all_data = []
    params['page'] = 1
    params['per_page'] = 10000
    
    while True:
        response = requests.get(endpoint, params=params)
        data = response.json()
        all_data.extend(data['results'])
        
        if not data['next']:
            break
        params['page'] += 1
    
    return all_data
```

### Batch by Year

For multi-year analysis, query each year separately:

```python
all_years = []
for year in range(2018, 2023):
    year_data = get_eada_data(year)
    all_years.append(year_data)

full_data = pd.concat(all_years, ignore_index=True)
```

## Summary Endpoints

The Education Data Portal offers summary endpoints for aggregation:

```
/api/v1/college-university/eada/summaries/
```

Parameters:
- `var`: Variable to summarize
- `stat`: Statistic (sum, avg, count)
- `by`: Grouping variable

### Example Summary

```
GET /college-university/eada/summaries/?var=partic_women&stat=sum&by=fips&year=2022
```

Returns sum of female participants by state.

## Error Handling

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| 404 | Invalid endpoint | Check URL structure |
| Empty results | No matching data | Verify filter values |
| Timeout | Large request | Add pagination, reduce scope |

### Validation

Always validate:
- Row counts match expectations
- Key fields are populated
- Joins didn't drop records unexpectedly

## Data Export

### CSV Download

The Education Data Portal also offers bulk CSV downloads:
- Navigate to Data Explorer
- Select EADA data
- Choose filters
- Export as CSV

### When to Use CSV vs API

| Use Case | Recommended |
|----------|-------------|
| One-time analysis | CSV download |
| Repeated queries | API |
| Integration with pipeline | API |
| Exploratory analysis | Data Explorer + CSV |
