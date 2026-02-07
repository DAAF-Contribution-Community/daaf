# API Access

Programmatic access to PSEO data via Census Bureau API and bulk downloads.

## Contents

- [API Overview](#api-overview)
- [Earnings Endpoint](#earnings-endpoint)
- [Flows Endpoint](#flows-endpoint)
- [Query Construction](#query-construction)
- [Advanced Queries](#advanced-queries)
- [Bulk Data Downloads](#bulk-data-downloads)
- [Code Examples](#code-examples)
- [PSEO Explorer](#pseo-explorer)

## API Overview

### Base URLs

| Endpoint | URL |
|----------|-----|
| Earnings | `https://api.census.gov/data/timeseries/pseo/earnings` |
| Flows | `https://api.census.gov/data/timeseries/pseo/flows` |

### API Key

- **Optional but recommended** for higher rate limits
- Request at: https://api.census.gov/data/key_signup.html
- Append to queries: `&key=YOUR_KEY`

### Response Format

API returns JSON arrays:
```json
[
  ["Y1_P50_EARNINGS", "INSTITUTION", "us"],
  ["65000", "00365800", "1"]
]
```

First row contains headers; subsequent rows contain data.

## Earnings Endpoint

### Documentation Links

- Variables: https://api.census.gov/data/timeseries/pseo/earnings/variables.html
- Examples: https://api.census.gov/data/timeseries/pseo/earnings.html

### Basic Query Structure

```
GET https://api.census.gov/data/timeseries/pseo/earnings
  ?get={variables}
  &for=us:1
  &{filters}
  &key={api_key}
```

### Example: Median Earnings by Institution

```
https://api.census.gov/data/timeseries/pseo/earnings
  ?get=Y1_P50_EARNINGS,Y5_P50_EARNINGS,LABEL_INSTITUTION
  &for=us:1
  &INSTITUTION=00365800
  &DEGREE_LEVEL=05
  &GRAD_COHORT=2016
```

### Available Variables

| Variable | Description |
|----------|-------------|
| `Y1_P25_EARNINGS` | 25th percentile, Year 1 |
| `Y1_P50_EARNINGS` | Median, Year 1 |
| `Y1_P75_EARNINGS` | 75th percentile, Year 1 |
| `Y5_P*_EARNINGS` | Year 5 percentiles |
| `Y10_P*_EARNINGS` | Year 10 percentiles |
| `Y1_GRADS`, `Y5_GRADS`, `Y10_GRADS` | Graduate counts |
| `STATUS_Y*_EARNINGS` | Status flags |

## Flows Endpoint

### Documentation Links

- Variables: https://api.census.gov/data/timeseries/pseo/flows/variables.html
- Examples: https://api.census.gov/data/timeseries/pseo/flows.html

### Basic Query Structure

```
GET https://api.census.gov/data/timeseries/pseo/flows
  ?get={variables}
  &for=division:{code}
  &{filters}
  &key={api_key}
```

### Example: Employment by Industry

```
https://api.census.gov/data/timeseries/pseo/flows
  ?get=Y1_GRADS_EMP,LABEL_NAICS
  &for=us:1
  &INSTITUTION=00365800
  &DEGREE_LEVEL=05
  &CIPCODE=11
  &NAICS=54
  &GRAD_COHORT=2016
```

### Available Variables

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP` | Employed, Year 1 |
| `Y5_GRADS_EMP` | Employed, Year 5 |
| `Y10_GRADS_EMP` | Employed, Year 10 |
| `Y*_GRADS_EMP_INSTATE` | In-state employment |
| `Y*_GRADS_NME` | Non-employed/marginal |
| `NAICS` | Industry sector |
| `division` | Census Division |

### Geography Options

| Geography | Usage | Notes |
|-----------|-------|-------|
| `&for=us:1` | National total | Earnings and Flows |
| `&for=division:9` | Single division | Flows only |
| `&for=division:*` | All divisions | Flows only |
| `&for=division:1,2,3` | Multiple divisions | Flows only |

## Query Construction

### Required Components

Every query needs:
1. **Endpoint URL** (earnings or flows)
2. **Get statement**: `?get=Y1_P50_EARNINGS`
3. **Geography**: `&for=us:1`

### Optional Filters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `INSTITUTION` | 8-digit OPEID | `&INSTITUTION=00365800` |
| `INST_STATE` | State FIPS code | `&INST_STATE=48` |
| `INST_LEVEL` | Institution/state level | `&INST_LEVEL=I` |
| `DEGREE_LEVEL` | Credential type | `&DEGREE_LEVEL=05` |
| `CIPCODE` | Field of study | `&CIPCODE=11` |
| `CIP_LEVEL` | CIP granularity | `&CIP_LEVEL=2` |
| `NAICS` | Industry (flows only) | `&NAICS=54` |
| `GRAD_COHORT` | Cohort start year | `&GRAD_COHORT=2016` |
| `GRAD_COHORT_YEARS` | Cohort span | `&GRAD_COHORT_YEARS=3` |

### Defaults When Not Specified

| Parameter | Default |
|-----------|---------|
| `DEGREE_LEVEL` | `05` (Bachelor's) |
| `CIP_LEVEL` | `2` (2-digit CIP) |
| `INST_LEVEL` | `I` (Individual institution) |

**Important**: If `INSTITUTION` is not specified, ALL institutions are returned.

## Advanced Queries

### Get All Values for a Variable

Add variable name to get statement:
```
?get=Y1_P50_EARNINGS,INSTITUTION,CIPCODE
&for=us:1
&DEGREE_LEVEL=05
```

Returns all combinations of institutions and CIP codes.

### Multiple Indicators

```
?get=Y1_P25_EARNINGS,Y1_P50_EARNINGS,Y1_P75_EARNINGS,Y1_GRADS
&for=us:1
&INSTITUTION=00365800
```

### Multiple Values for Filter

Use repeated parameters:
```
&NAICS=51&NAICS=54&NAICS=52
```

Or use commas for divisions:
```
&for=division:1,2,3,9
```

### Including Labels

Add `LABEL_` prefix to get human-readable names:
```
?get=Y1_P50_EARNINGS,LABEL_INSTITUTION,LABEL_CIPCODE
```

### Status Flags

Add `STATUS_` prefix for data quality indicators:
```
?get=Y1_P50_EARNINGS,STATUS_Y1_EARNINGS
```

### Aggregation Level

Use `AGG_LEVEL_PSEO` to filter by specific variable crossings:
```
&AGG_LEVEL_PSEO=38
```

## Bulk Data Downloads

### Download Location

https://lehd.ces.census.gov/data/pseo/

### File Structure

```
/data/pseo/
├── latest_release/
│   ├── all/
│   │   ├── pseo_all_earnings.csv.gz
│   │   ├── pseo_all_flows.csv.gz
│   │   └── pseo_all_institutions.csv
│   └── {state_fips}/
│       ├── pseo_{state}_earnings.csv.gz
│       └── pseo_{state}_flows.csv.gz
```

### File Formats

| Format | Description |
|--------|-------------|
| `.csv.gz` | Compressed CSV (recommended) |
| `.xlsx` | Excel (limited rows due to size) |

### Comprehensive vs. State Files

| File Type | Contents | Size |
|-----------|----------|------|
| `all/` | All institutions nationwide | Large |
| `{state}/` | Institutions in specific state | Smaller |

## Code Examples

### Python with requests

```python
import requests
import pandas as pd

# API endpoint
base_url = "https://api.census.gov/data/timeseries/pseo/earnings"

# Query parameters
params = {
    "get": "Y1_P50_EARNINGS,Y5_P50_EARNINGS,LABEL_INSTITUTION,LABEL_CIPCODE",
    "for": "us:1",
    "INSTITUTION": "00365800",
    "DEGREE_LEVEL": "05",
    # "key": "YOUR_API_KEY"  # optional
}

# Make request
response = requests.get(base_url, params=params)
data = response.json()

# Convert to DataFrame
df = pd.DataFrame(data[1:], columns=data[0])
print(df)
```

### Python with HuggingFace Mirror (Recommended)

```python
# Using the HuggingFace mirror (recommended for data analysis)
import polars as pl

# Download PSEO data from mirror
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/pseo/earnings-and-flows/colleges_pseo_2020.parquet"
df = pl.read_parquet(url)

# Filter to specific institution using integer unitid
ut_austin = df.filter(pl.col("unitid") == 228778)

# Filter by degree level (5 = Bachelor's)
bachelors = df.filter(pl.col("degree_level") == 5)
```

> **Note:** The Portal uses integer encodings. See `variable-definitions.md` for code mappings.

### Python with Urban Institute API (Legacy)

```python
# Direct API access (note: uses Census API string codes, not Portal integers)
import requests

base_url = "https://educationdata.urban.org/api/v1"
endpoint = "/college-university/pseo/earnings-and-flows/"
url = f"{base_url}{endpoint}?unitid=228778&year=2020"

response = requests.get(url)
data = response.json()
```

### R with httr

```r
library(httr)
library(jsonlite)

# Build query
url <- "https://api.census.gov/data/timeseries/pseo/earnings"
query <- list(
  get = "Y1_P50_EARNINGS,LABEL_INSTITUTION",
  `for` = "us:1",
  INSTITUTION = "00365800",
  DEGREE_LEVEL = "05"
)

# Make request
response <- GET(url, query = query)
data <- fromJSON(content(response, "text"))

# Convert to data frame
df <- as.data.frame(data[-1, ], stringsAsFactors = FALSE)
names(df) <- data[1, ]
```

### Bulk Download with Python

```python
import pandas as pd

# Direct bulk download
url = "https://lehd.ces.census.gov/data/pseo/latest_release/all/pseo_all_earnings.csv.gz"
df = pd.read_csv(url, compression='gzip')

# Filter to specific institution
ut_austin = df[df['institution'] == '00365800']
```

## PSEO Explorer

### Interactive Tool

URL: https://lehd.ces.census.gov/data/pseo_explorer.html

### Features

| Feature | Description |
|---------|-------------|
| Earnings comparison | Bar charts comparing programs/institutions |
| Employment flows | Sankey diagrams showing industry/geography flows |
| Filter controls | Select state, institution, degree, major |
| Export | Download filtered data |

### Direct Linking

Pre-populate Explorer with specific selections:

```
https://lehd.ces.census.gov/applications/pseo/
  ?type=earnings
  &compare=postgrad
  &specificity=2
  &state=48
  &institution=00365800
  &degreelevel=05
  &gradcohort=0000-3
  &filter=50
  &program=11
```

### URL Parameters

| Parameter | Description | Values |
|-----------|-------------|--------|
| `type` | Data type | `earnings`, `flows` |
| `state` | State FIPS | 2-digit code |
| `institution` | OPEID | 8-digit code |
| `degreelevel` | Degree | Code (e.g., `05`) |
| `program` | CIP code | 2-digit |
| `gradcohort` | Cohort | `YYYY-N` format |

## Additional Resources

| Resource | URL |
|----------|-----|
| API documentation | https://www.census.gov/data/developers/data-sets/pseo.html |
| Data schema | https://lehd.ces.census.gov/data/schema/latest/lehd_public_use_schema.html |
| Code samples | https://lehd.ces.census.gov/data/lehd-code-samples/sections/pseo.html |
| Technical docs | https://lehd.ces.census.gov/doc/PSEOTechnicalDocumentation.pdf |
| PSEO Explorer | https://lehd.ces.census.gov/data/pseo_explorer.html |
