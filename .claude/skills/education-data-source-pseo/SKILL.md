---
name: education-data-source-pseo
description: Postsecondary Employment Outcomes (PSEO) data source from the Census Bureau LEHD program. Experimental tabulations linking college graduates to employment outcomes. Use when researching graduate earnings, employment by industry, geographic flows of graduates, or comparing outcomes across institutions and degree programs.
metadata:
  audience: data-analysts
  domain: education-data
---

# Education Data Source: PSEO

> **CRITICAL: Portal vs Census API Encoding**
>
> This document describes **Education Data Portal** integer encodings, which differ from Census API string codes. The Portal converts categorical variables to integers for consistency.
>
> | Context | Baccalaureate | Associates | Masters | Census Division Pacific |
> |---------|---------------|------------|---------|-------------------------|
> | **Portal (integers)** | `5` | `3` | `7` | `9` |
> | Census API (strings) | `05` | `03` | `07` | `9` |
>
> **Key differences:** Degree level uses simple integers (1-10), not string codes like "1C", "05". CIP codes are 2-digit integers (11 for Computer Science), not strings like "11.01".

Postsecondary Employment Outcomes (PSEO) is an experimental data product from the U.S. Census Bureau that links college graduate records to national employment data, providing earnings and employment outcomes by institution, degree level, and field of study.

## What is PSEO?

- **Experimental data product** from Census Bureau's LEHD program (Longitudinal Employer-Household Dynamics)
- **Links education to employment**: Matches university transcript data with national UI wage records
- **Tracks graduates nationally**: Unlike state-based systems, follows students across state lines
- **Two data types**: Graduate Earnings (percentile earnings) and Employment Flows (industry/geography)
- **Coverage**: ~29% of all U.S. college graduates from 31 states + D.C. + Western Governors University
- **Privacy protected**: Uses differential privacy mechanisms to protect individual data

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `lehd-methodology.md` | How LEHD produces tabulations, data matching process | Understanding data creation |
| `earnings-data.md` | Percentile earnings, cohort definitions, labor attachment | Analyzing graduate earnings |
| `geographic-flows.md` | Where graduates work by Census Division | Studying migration patterns |
| `industry-flows.md` | What industries graduates enter by NAICS sector | Career pathway analysis |
| `variable-definitions.md` | All variables, codes, and status flags | Building queries |
| `state-coverage.md` | Participating states, coverage rates, data partners | Understanding limitations |
| `api-access.md` | Census API endpoints, query construction | Programmatic data access |

## Decision Trees

### What type of outcome am I researching?

```
Graduate outcomes research?
├─ Earnings by program/institution
│   ├─ Median earnings → Earnings endpoint, Y*_P50_EARNINGS
│   ├─ Earnings distribution → 25th/50th/75th percentiles
│   └─ See ./references/earnings-data.md
├─ Where graduates work (geography)
│   ├─ Census Division of employment → Flows endpoint
│   ├─ In-state vs out-of-state → Y*_GRADS_EMP_INSTATE
│   └─ See ./references/geographic-flows.md
├─ What industries graduates enter
│   ├─ NAICS sector employment → Flows endpoint
│   └─ See ./references/industry-flows.md
└─ How many graduates are employed
    ├─ Employment counts → Y*_GRADS_EMP
    ├─ Non-employed/marginal → Y*_GRADS_NME
    └─ See ./references/variable-definitions.md
```

### What degree level am I researching?

```
Degree level?
├─ Certificate (<1 year) → degree_level=1
├─ Certificate (1-2 years) → degree_level=2
├─ Certificate (2-4 years) → degree_level=4
├─ Associate's → degree_level=3
├─ Bachelor's → degree_level=5 (default, 3-year cohorts)
├─ Post-Bacc Certificate → degree_level=6
├─ Master's → degree_level=7 (2-digit CIP only)
├─ Post-Masters Certificate → degree_level=8
├─ Doctoral-Research → degree_level=9 (2-digit CIP only)
└─ Doctoral-Professional Practice → degree_level=10
```

> **Note:** Portal uses integers 1-10. Census API uses string codes like "05", "1C".

### Is my institution/state covered?

```
Checking data availability?
├─ Which states participate → ./references/state-coverage.md
├─ Which institutions have data → Check PSEO Explorer or API
├─ Coverage rate for state → ./references/state-coverage.md
└─ Why data might be missing
    ├─ Institution not partnered
    ├─ Cell suppressed (count < 30)
    └─ Insufficient labor force attachment
```

## Quick Reference: Data Access

### HuggingFace Mirror (Recommended)

| Data | URL Pattern |
|------|-------------|
| PSEO Data | `huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/pseo/earnings-and-flows/colleges_pseo_{year}.parquet` |
| Codebook | `huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/pseo/earnings-and-flows/codebook_colleges_pseo.xls` |

### Urban Institute API

| Endpoint | URL |
|----------|-----|
| PSEO | `educationdata.urban.org/api/v1/college-university/pseo/earnings-and-flows/` |

### Census API (Original Source)

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Earnings | `api.census.gov/data/timeseries/pseo/earnings` | Graduate earnings percentiles |
| Flows | `api.census.gov/data/timeseries/pseo/flows` | Industry and geographic employment |

## Quick Reference: Key Variables (Portal Schema)

### Earnings Variables

| Portal Variable | Description |
|-----------------|-------------|
| `p25_earnings` | 25th percentile earnings (2022 dollars) |
| `p50_earnings` | Median earnings (2022 dollars) |
| `p75_earnings` | 75th percentile earnings (2022 dollars) |
| `years_after_grad` | Years post-graduation: `1`, `5`, or `10` |
| `employed_grads_count_e` | Graduate count with earnings data |
| `total_grads_count` | Total IPEDS-reported graduates |

### Flows Variables

| Portal Variable | Description |
|-----------------|-------------|
| `employed_grads_count_f` | Employed graduates count |
| `employed_instate_grads_count` | Employed in institution's state |
| `jobless_m_emp_grads_count` | Non-employed or marginally employed |
| `industry` | 2-digit NAICS sector (integer) |
| `census_division` | Census Division of employment (1-9, 99) |

> **Note:** Portal uses restructured schema with `years_after_grad` column instead of Census API's `Y1_*/Y5_*/Y10_*` naming.

## Quick Reference: Key Filters (Portal Integer Encoding)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `unitid` | IPEDS Unit ID | `100751` (University of Alabama) |
| `opeid` | OPEID as integer | `105100` (not string "00105100") |
| `fips` | State FIPS of institution | `48` (Texas) |
| `degree_level` | Degree type integer | `5` (Bachelor's) |
| `cipcode` | Field of study (2-digit integer) | `11` (Computer Science) |
| `pseo_cohort` | Graduation cohort | `"2016-18"` (string format) |
| `years_after_grad` | Years post-graduation | `1`, `5`, or `10` |

> **Note:** Variable names are lowercase in Portal data. `opeid` is an integer (not 8-digit string).

## Cohort Definitions

| Degree Level | Cohort Years | Example Cohorts |
|--------------|--------------|-----------------|
| Bachelor's | 3-year | 2001-03, 2004-06, 2007-09, 2010-12, 2013-15, 2016-18, 2019-21 |
| All others | 5-year | 2001-05, 2006-10, 2011-15, 2016-20 |

## PSEO vs Other Data Sources

| Feature | PSEO | College Scorecard | State Systems |
|---------|------|-------------------|---------------|
| Coverage | Graduates only | All enrollees | Graduates only |
| Geographic scope | National (cross-state) | National | In-state only |
| Sample | All graduates from partners | Federal aid recipients | All graduates |
| Earnings detail | 25th/50th/75th percentile | Median only | Varies |
| Industry data | Yes (NAICS sector) | No | Varies |
| Geographic flows | Yes (Census Division) | No | No |
| Privacy method | Differential privacy | Traditional suppression | Varies |

## Important Limitations

1. **Experimental status**: Not official Census statistics; methodology may change
2. **Partial coverage**: Only ~29% of graduates from participating institutions
3. **Selection bias**: Participating states/institutions may differ systematically
4. **Employment coverage**: Excludes self-employed, independent contractors, military, some federal
5. **Labor attachment requirement**: Workers must have 3+ quarters of earnings above minimum wage threshold
6. **Suppression**: Cells with fewer than 30 graduates are suppressed
7. **Earnings inflation-adjusted**: All earnings in 2022 dollars (CPI-U)

## Common Use Cases

| Use Case | Data Needed | Key Considerations |
|----------|-------------|-------------------|
| Compare programs within institution | Earnings by CIPCODE | Check cell counts for suppression |
| Compare institutions for same program | Earnings by INSTITUTION | Ensure same degree level and CIP |
| Analyze brain drain/retention | Flows by division + in-state | Only 9 Census Divisions |
| Career pathway analysis | Flows by NAICS sector | 2-digit NAICS only |
| ROI by degree level | Earnings across DEGREE_LEVEL | Different cohort spans |

## Access Methods

1. **PSEO Explorer**: Interactive visualization tool at `lehd.ces.census.gov/data/pseo_explorer.html`
2. **Census API**: Programmatic access via `api.census.gov/data/timeseries/pseo/`
3. **Bulk download**: CSV/XLS files at `lehd.ces.census.gov/data/pseo/`
4. **Urban Institute Education Data Portal**: Integrated access with other education data

## Topic Index

| Topic | Reference File |
|-------|---------------|
| LEHD program overview | `./references/lehd-methodology.md` |
| Data matching process | `./references/lehd-methodology.md` |
| Differential privacy | `./references/lehd-methodology.md` |
| Percentile earnings | `./references/earnings-data.md` |
| Labor force attachment | `./references/earnings-data.md` |
| Cohort definitions | `./references/earnings-data.md` |
| Census Division employment | `./references/geographic-flows.md` |
| In-state employment | `./references/geographic-flows.md` |
| NAICS sector employment | `./references/industry-flows.md` |
| Industry code reference | `./references/industry-flows.md` |
| Variable names and codes | `./references/variable-definitions.md` |
| Status flags | `./references/variable-definitions.md` |
| State participation | `./references/state-coverage.md` |
| Coverage rates | `./references/state-coverage.md` |
| Data partners | `./references/state-coverage.md` |
| API query construction | `./references/api-access.md` |
| Bulk data download | `./references/api-access.md` |
