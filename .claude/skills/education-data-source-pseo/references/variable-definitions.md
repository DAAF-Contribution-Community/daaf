# Variable Definitions

Complete reference for PSEO variables, codes, and status flags.

## Contents

- [Identifier Variables](#identifier-variables)
- [Earnings Variables](#earnings-variables)
- [Flow Variables](#flow-variables)
- [Status Flags](#status-flags)
- [Degree Level Codes](#degree-level-codes)
- [CIP Codes](#cip-codes)
- [Institution Codes](#institution-codes)
- [Geography Codes](#geography-codes)
- [Aggregation Levels](#aggregation-levels)

## Identifier Variables

### Institution Identifiers

| Variable | Description | Format |
|----------|-------------|--------|
| `INSTITUTION` | Office of Postsecondary Education ID (OPEID) | 8-digit string |
| `INST_STATE` | State FIPS code of institution | 2-digit string |
| `INST_LEVEL` | Institution vs state aggregate | `I` or `S` |
| `LABEL_INSTITUTION` | Institution name | Text |
| `LABEL_INST_STATE` | State name | Text |

**INST_LEVEL values:**

| Code | Meaning |
|------|---------|
| `I` | Individual institution |
| `S` | State-level aggregate (all institutions in state) |

### Program Identifiers

| Variable | Description | Format |
|----------|-------------|--------|
| `DEGREE_LEVEL` | Type of credential | 2-char code |
| `CIPCODE` | Classification of Instructional Programs | 2 or 4 digit |
| `CIP_LEVEL` | Granularity of CIP code | `2` or `4` |
| `LABEL_DEGREE_LEVEL` | Degree level name | Text |
| `LABEL_CIPCODE` | Program name | Text |

### Cohort Identifiers

| Variable | Description | Format |
|----------|-------------|--------|
| `GRAD_COHORT` | First year of graduation cohort | 4-digit year or `0000` |
| `GRAD_COHORT_YEARS` | Number of years in cohort | `3` or `5` |

## Earnings Variables

### Percentile Earnings

| Variable | Description | Unit |
|----------|-------------|------|
| `Y1_P25_EARNINGS` | 25th percentile earnings, Year 1 | 2022 dollars |
| `Y1_P50_EARNINGS` | Median earnings, Year 1 | 2022 dollars |
| `Y1_P75_EARNINGS` | 75th percentile earnings, Year 1 | 2022 dollars |
| `Y5_P25_EARNINGS` | 25th percentile earnings, Year 5 | 2022 dollars |
| `Y5_P50_EARNINGS` | Median earnings, Year 5 | 2022 dollars |
| `Y5_P75_EARNINGS` | 75th percentile earnings, Year 5 | 2022 dollars |
| `Y10_P25_EARNINGS` | 25th percentile earnings, Year 10 | 2022 dollars |
| `Y10_P50_EARNINGS` | Median earnings, Year 10 | 2022 dollars |
| `Y10_P75_EARNINGS` | 75th percentile earnings, Year 10 | 2022 dollars |

### Graduate Counts (Earnings)

| Variable | Description |
|----------|-------------|
| `Y1_GRADS` | Graduates with valid earnings, Year 1 |
| `Y5_GRADS` | Graduates with valid earnings, Year 5 |
| `Y10_GRADS` | Graduates with valid earnings, Year 10 |

## Flow Variables

### Employment Counts

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP` | Employed graduates, Year 1 |
| `Y5_GRADS_EMP` | Employed graduates, Year 5 |
| `Y10_GRADS_EMP` | Employed graduates, Year 10 |

### In-State Employment

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP_INSTATE` | Employed in institution's state, Year 1 |
| `Y5_GRADS_EMP_INSTATE` | Employed in institution's state, Year 5 |
| `Y10_GRADS_EMP_INSTATE` | Employed in institution's state, Year 10 |

### Non-Employed/Marginal

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_NME` | Non-employed or marginally employed, Year 1 |
| `Y5_GRADS_NME` | Non-employed or marginally employed, Year 5 |
| `Y10_GRADS_NME` | Non-employed or marginally employed, Year 10 |

### Industry Classification

| Variable | Description |
|----------|-------------|
| `NAICS` | 2-digit NAICS industry sector |
| `LABEL_NAICS` | Industry sector name |

### Geography of Employment

| Variable | Description |
|----------|-------------|
| `division` | Census Division code (1-9) |
| `LABEL_DIVISION` | Division name |

## Status Flags

### Earnings Status Flags

| Variable | Applies To |
|----------|------------|
| `STATUS_Y1_EARNINGS` | Y1_P25, Y1_P50, Y1_P75_EARNINGS |
| `STATUS_Y5_EARNINGS` | Y5_P25, Y5_P50, Y5_P75_EARNINGS |
| `STATUS_Y10_EARNINGS` | Y10_P25, Y10_P50, Y10_P75_EARNINGS |

### Flow Status Flags

| Variable | Applies To |
|----------|------------|
| `STATUS_Y1_GRADS_EMP` | Y1_GRADS_EMP |
| `STATUS_Y5_GRADS_EMP` | Y5_GRADS_EMP |
| `STATUS_Y10_GRADS_EMP` | Y10_GRADS_EMP |

### Status Flag Values

| Code | Meaning | Action |
|------|---------|--------|
| `1` | Valid data | Use normally |
| `5` | Suppressed (count < 30) | Data quality insufficient |

## Degree Level Codes

| Code | Degree Level | CIP Level | Cohort Years |
|------|--------------|-----------|--------------|
| `1C` | Certificate (< 1 year) | 4-digit | 5 |
| `1A` | Certificate (1-2 years) | 4-digit | 5 |
| `2A` | Certificate (2-4 years) | 4-digit | 5 |
| `03` | Associate's | 4-digit | 5 |
| `05` | Bachelor's | 4-digit | 3 |
| `07` | Master's | 2-digit only | 5 |
| `17` | Doctoral-Professional Practice | 4-digit | 5 |
| `18` | Doctoral-Research/Scholarship | 2-digit only | 5 |

**Notes:**
- Bachelor's (05) is the default if not specified
- Master's and Doctoral-Research only have 2-digit CIP codes
- Cohort years affects GRAD_COHORT valid values

## CIP Codes

### CIP Level

| Level | Description | Example |
|-------|-------------|---------|
| 2-digit | Broad field | `11` = Computer and Information Sciences |
| 4-digit | Specific program | `11.01` = Computer and Information Sciences, General |

### Common 2-Digit CIP Codes

| Code | Field |
|------|-------|
| `01` | Agriculture |
| `03` | Natural Resources and Conservation |
| `04` | Architecture |
| `05` | Area, Ethnic, Cultural, Gender Studies |
| `09` | Communication, Journalism |
| `10` | Communications Technologies |
| `11` | Computer and Information Sciences |
| `13` | Education |
| `14` | Engineering |
| `15` | Engineering Technologies |
| `16` | Foreign Languages, Literatures, Linguistics |
| `19` | Family and Consumer Sciences |
| `22` | Legal Professions and Studies |
| `23` | English Language and Literature |
| `24` | Liberal Arts and Sciences |
| `25` | Library Science |
| `26` | Biological and Biomedical Sciences |
| `27` | Mathematics and Statistics |
| `30` | Multi/Interdisciplinary Studies |
| `31` | Parks, Recreation, Leisure, Fitness |
| `38` | Philosophy and Religious Studies |
| `40` | Physical Sciences |
| `42` | Psychology |
| `43` | Homeland Security, Law Enforcement |
| `44` | Public Administration and Social Service |
| `45` | Social Sciences |
| `50` | Visual and Performing Arts |
| `51` | Health Professions |
| `52` | Business, Management, Marketing |
| `54` | History |

Full reference: [CIPCODE Labels (CSV)](https://lehd.ces.census.gov/data/schema/latest/label_cipcode.csv)

## Institution Codes

### OPEID Format

8-digit code: `XXXXXXYY`
- First 6 digits: Institution identifier
- Last 2 digits: Sub-institution/branch code (often `00`)

**Examples:**

| OPEID | Institution |
|-------|-------------|
| `00365800` | University of Texas at Austin |
| `00216200` | Georgia Institute of Technology |
| `00154500` | University of Michigan - Ann Arbor |
| `00126614` | University of California - Berkeley |

### Finding Institution Codes

1. [All PSEO Institution Codes (CSV)](https://lehd.ces.census.gov/data/pseo/latest_release/all/pseo_all_institutions.csv)
2. [Complete Institution Labels (CSV)](https://lehd.ces.census.gov/data/schema/latest/label_institution.csv)

## Geography Codes

### State FIPS Codes (INST_STATE)

| Code | State | Code | State |
|------|-------|------|-------|
| `01` | Alabama | `27` | Minnesota |
| `04` | Arizona | `29` | Missouri |
| `08` | Colorado | `30` | Montana |
| `09` | Connecticut | `36` | New York |
| `11` | District of Columbia | `39` | Ohio |
| `13` | Georgia | `40` | Oklahoma |
| `15` | Hawaii | `41` | Oregon |
| `17` | Illinois | `42` | Pennsylvania |
| `18` | Indiana | `44` | Rhode Island |
| `19` | Iowa | `45` | South Carolina |
| `22` | Louisiana | `46` | South Dakota |
| `23` | Maine | `48` | Texas |
| `25` | Massachusetts | `49` | Utah |
| `26` | Michigan | `51` | Virginia |
| `00` | Online-only institutions | `54` | West Virginia |
| | | `55` | Wisconsin |
| | | `56` | Wyoming |

Full reference: [State FIPS Labels (CSV)](https://lehd.ces.census.gov/data/schema/latest/label_fipsnum.csv)

### Census Division Codes

| Code | Division |
|------|----------|
| `1` | New England |
| `2` | Middle Atlantic |
| `3` | East North Central |
| `4` | West North Central |
| `5` | South Atlantic |
| `6` | East South Central |
| `7` | West South Central |
| `8` | Mountain |
| `9` | Pacific |

Full reference: [Division Labels (CSV)](https://lehd.ces.census.gov/data/schema/latest/label_geography_division.csv)

## Aggregation Levels

### AGG_LEVEL_PSEO

The `AGG_LEVEL_PSEO` variable indicates the combination of dimensions in a tabulation:

| Code | Dimensions Included |
|------|---------------------|
| `38` | Institution + Degree + CIP + Cohort |
| Other codes | Various combinations |

Use to filter for specific aggregation patterns in bulk data.

### Default Values

When parameters are not specified:

| Parameter | Default Value |
|-----------|---------------|
| `DEGREE_LEVEL` | `05` (Bachelor's) |
| `CIP_LEVEL` | `2` |
| `GRAD_COHORT_YEARS` | `3` (if Bachelor's) or `5` |
| `INST_LEVEL` | `I` (Individual institution) |

## Schema Reference Files

| File | URL |
|------|-----|
| Complete schema | `lehd.ces.census.gov/data/schema/latest/lehd_public_use_schema.html` |
| Earnings variables | `lehd.ces.census.gov/data/schema/latest/variables_pseoe.csv` |
| Flows variables | `lehd.ces.census.gov/data/schema/latest/variables_pseof.csv` |
| All labels | `lehd.ces.census.gov/data/schema/latest/` (browse directory) |
