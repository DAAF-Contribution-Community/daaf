---
name: education-data-source-pseo
description: Postsecondary Employment Outcomes (PSEO) data source from the Census Bureau LEHD program. Experimental tabulations linking college graduates to employment outcomes. Use when researching graduate earnings, employment by industry, geographic flows of graduates, or comparing outcomes across institutions and degree programs.
metadata:
  audience: data-analysts
  domain: education-data
---

# Education Data Source: PSEO

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
├─ Certificate (<1 year) → DEGREE_LEVEL=1C
├─ Certificate (1-2 years) → DEGREE_LEVEL=1A
├─ Certificate (2-4 years) → DEGREE_LEVEL=2A
├─ Associate's → DEGREE_LEVEL=03
├─ Bachelor's → DEGREE_LEVEL=05 (default, 3-year cohorts)
├─ Master's → DEGREE_LEVEL=07 (2-digit CIP only)
├─ Doctoral-Professional Practice → DEGREE_LEVEL=17
└─ Doctoral-Research → DEGREE_LEVEL=18 (2-digit CIP only)
```

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

## Quick Reference: Data Endpoints

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Earnings | `api.census.gov/data/timeseries/pseo/earnings` | Graduate earnings percentiles |
| Flows | `api.census.gov/data/timeseries/pseo/flows` | Industry and geographic employment |

## Quick Reference: Key Variables

### Earnings Endpoint

| Variable | Description |
|----------|-------------|
| `Y1_P25_EARNINGS` | 25th percentile earnings, 1 year post-graduation |
| `Y1_P50_EARNINGS` | Median earnings, 1 year post-graduation |
| `Y1_P75_EARNINGS` | 75th percentile earnings, 1 year post-graduation |
| `Y5_P*_EARNINGS` | Same percentiles, 5 years post-graduation |
| `Y10_P*_EARNINGS` | Same percentiles, 10 years post-graduation |
| `Y1_GRADS` | Graduate count, 1 year post-graduation |

### Flows Endpoint

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP` | Employed graduates, 1 year post-graduation |
| `Y1_GRADS_EMP_INSTATE` | Employed in-state, 1 year post-graduation |
| `Y1_GRADS_NME` | Non-employed or marginally employed |
| `NAICS` | Industry sector (2-digit NAICS) |
| `division` | Census Division of employment |

## Quick Reference: Key Filters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `INSTITUTION` | 8-digit OPEID code | `00365800` (UT Austin) |
| `INST_STATE` | State FIPS of institution | `48` (Texas) |
| `DEGREE_LEVEL` | Degree type code | `05` (Bachelor's) |
| `CIPCODE` | Field of study (CIP code) | `11` (Computer Science) |
| `CIP_LEVEL` | CIP code precision | `2` or `4` |
| `GRAD_COHORT` | First year of cohort | `2019` |
| `GRAD_COHORT_YEARS` | Cohort span | `3` (Bachelor's) or `5` |

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
