---
name: education-data-source-pseo
description: >-
  Postsecondary Employment Outcomes (PSEO) data source from the Census Bureau
  LEHD program. Experimental tabulations linking college graduates to employment
  outcomes. Use when researching graduate earnings, employment by industry,
  geographic flows of graduates, or comparing outcomes across institutions and
  degree programs. Coverage limited to ~29% of graduates from participating
  states.
metadata:
  audience: data-analysts
  domain: education-data
---

# PSEO Data Source Reference

Postsecondary Employment Outcomes (PSEO) is an experimental data product from the U.S. Census Bureau that links college graduate records to national employment data, providing earnings and employment outcomes by institution, degree level, and field of study.

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
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is PSEO?

- **Producer**: U.S. Census Bureau, LEHD program (Longitudinal Employer-Household Dynamics)
- **Coverage**: ~29% of all U.S. college graduates from 31 states + D.C. + Western Governors University
- **Content**: Links university transcript data with national UI wage records to track graduate employment outcomes
- **Two data types**: Graduate Earnings (percentile earnings) and Employment Flows (industry/geography)
- **Frequency**: Updated periodically; cohorts span 3-year (Bachelor's) or 5-year (all others) windows
- **Primary identifiers**: `unitid` (IPEDS Unit ID), `opeid` (8-character string)
- **Privacy method**: Differential privacy mechanisms protect individual data

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `lehd-methodology.md` | How LEHD produces tabulations, data matching process | Understanding data creation |
| `earnings-data.md` | Percentile earnings, cohort definitions, labor attachment | Analyzing graduate earnings |
| `geographic-flows.md` | Where graduates work by Census Division | Studying migration patterns |
| `industry-flows.md` | What industries graduates enter by NAICS sector | Career pathway analysis |
| `variable-definitions.md` | All variables, codes, and status flags | Building queries or interpreting values |
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

## Quick Reference: PSEO Variables

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

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `unitid` | Integer | Institution | `100751` | IPEDS Unit ID (University of Alabama) |
| `opeid` | 8-char string | Institution | `"00105100"` | Not an integer; zero-padded |
| `fips` | Integer | State | `48` | State of institution (Texas) |
| `cipcode` | 2-digit integer | Field of study | `11` | Computer Science; Portal uses integers, not "11.01" |

### Key Filters (Portal Integer Encoding)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `degree_level` | Degree type integer | `5` (Bachelor's) |
| `pseo_cohort` | Graduation cohort | `"2016-18"` (string format) |
| `years_after_grad` | Years post-graduation | `1`, `5`, or `10` |

### Cohort Definitions

| Degree Level | Cohort Years | Example Cohorts |
|--------------|--------------|-----------------|
| Bachelor's | 3-year | 2001-03, 2004-06, 2007-09, 2010-12, 2013-15, 2016-18, 2019-21 |
| All others | 5-year | 2001-05, 2006-10, 2011-15, 2016-20 |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `null` | Not available | Earnings data not available for cell |
| Suppressed cell | Count < 30 graduates | Differential privacy suppression threshold |
| `-1` | Missing | Data not reported (Portal convention) |
| `-2` | Not applicable | Item doesn't apply to this entity (Portal convention) |

> **Note:** PSEO uses differential privacy rather than traditional suppression. Cells with fewer than 30 graduates are suppressed entirely. Earnings values may also be absent when labor force attachment requirements are not met.

## Data Access

### Dataset Paths

| Topic | Type | Huggingface Path |
|-------|------|------------------|
| Earnings and Flows | Yearly | `college-university/pseo/earnings-and-flows/colleges_pseo_{year}` |

### Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| PSEO Earnings and Flows | `college-university/pseo/earnings-and-flows/codebook_colleges_pseo` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for the
> full catalog and `fetch-patterns.md` for `get_codebook_url()`. For human
> reference -- not parsed programmatically.

### Example Fetch

```python
import polars as pl

url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/pseo/earnings-and-flows/colleges_pseo_2021.parquet"
df = pl.read_parquet(url)

# Filter for Texas Bachelor's degree earnings, 5 years post-graduation
df = df.filter(
    (pl.col("fips") == 48) &
    (pl.col("degree_level") == 5) &
    (pl.col("years_after_grad") == 5)
)
```

### Filtering

```python
# Filter by institution
df.filter(pl.col("unitid") == 100751)  # University of Alabama

# Filter by field of study
df.filter(pl.col("cipcode") == 11)  # Computer Science

# Filter by cohort
df.filter(pl.col("pseo_cohort") == "2016-18")

# Earnings endpoint only (non-null median earnings)
df.filter(pl.col("p50_earnings").is_not_null())
```

### Census API (Original Source)

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Earnings | `api.census.gov/data/timeseries/pseo/earnings` | Graduate earnings percentiles |
| Flows | `api.census.gov/data/timeseries/pseo/flows` | Industry and geographic employment |

### Additional Access Methods

1. **PSEO Explorer**: Interactive visualization tool at `lehd.ces.census.gov/data/pseo_explorer.html`
2. **Bulk download**: CSV/XLS files at `lehd.ces.census.gov/data/pseo/`

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Using Census string codes | Portal uses integers (e.g., `5` for Bachelor's), not Census strings (`"05"`) | Always check encoding; see variable-definitions.md |
| Ignoring suppression | Cells with <30 graduates are suppressed; missing data looks like no program exists | Check `total_grads_count` to confirm cell exists; null earnings may mean suppression |
| Cross-institution comparison without controlling degree/CIP | Institutions offer different program mixes; aggregate comparison is misleading | Always filter to same `degree_level` and `cipcode` when comparing institutions |
| Treating PSEO as comprehensive | Only ~29% of graduates covered; participating states differ systematically | Acknowledge selection bias; do not generalize to all U.S. graduates |
| Ignoring labor attachment | Workers need 3+ quarters above minimum wage threshold to appear in earnings data | Some graduates are employed but excluded; note this limitation |
| Using opeid as integer | `opeid` is an 8-character zero-padded string, not a numeric field | Keep as string: `"00105100"`, not `105100` |
| Mixing cohort spans | Bachelor's uses 3-year cohorts; all others use 5-year | Filter by `degree_level` first, then verify cohort format matches |
| Assuming inflation comparability | All earnings are in 2022 CPI-U dollars | No manual inflation adjustment needed; values are already real dollars |

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

## Common Use Cases

| Use Case | Data Needed | Key Considerations |
|----------|-------------|-------------------|
| Compare programs within institution | Earnings by CIPCODE | Check cell counts for suppression |
| Compare institutions for same program | Earnings by INSTITUTION | Ensure same degree level and CIP |
| Analyze brain drain/retention | Flows by division + in-state | Only 9 Census Divisions |
| Career pathway analysis | Flows by NAICS sector | 2-digit NAICS only |
| ROI by degree level | Earnings across DEGREE_LEVEL | Different cohort spans |

## Important Limitations

1. **Experimental status**: Not official Census statistics; methodology may change
2. **Partial coverage**: Only ~29% of graduates from participating institutions
3. **Selection bias**: Participating states/institutions may differ systematically
4. **Employment coverage**: Excludes self-employed, independent contractors, military, some federal
5. **Labor attachment requirement**: Workers must have 3+ quarters of earnings above minimum wage threshold
6. **Suppression**: Cells with fewer than 30 graduates are suppressed
7. **Earnings inflation-adjusted**: All earnings in 2022 dollars (CPI-U)

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-scorecard` | Alternative earnings source (median only, all enrollees) | When PSEO coverage is insufficient or need non-graduate outcomes |
| `education-data-source-ipeds` | Institution characteristics, enrollment, graduation rates | Contextualizing PSEO institutions; join on `unitid` |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |

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
