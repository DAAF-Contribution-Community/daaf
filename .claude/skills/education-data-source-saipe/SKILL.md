---
name: education-data-source-saipe
description: Census Bureau Small Area Income and Poverty Estimates (SAIPE) for school districts. Use when working with district-level poverty data, understanding poverty estimation methodology, interpreting Title I allocation data, or analyzing school-age children in poverty estimates.
metadata:
  audience: data-analysts
  domain: education-data
---

# SAIPE: Small Area Income and Poverty Estimates

Reference for understanding Census Bureau poverty estimates for school districts, counties, and states.

> **CRITICAL: Portal vs Census Raw File Encoding**
>
> This document describes **Education Data Portal** integer encodings, which differ from Census Bureau raw file formats. The Portal uses integers for FIPS codes and standard missing data conventions.
>
> | Context | FIPS Alabama | FIPS California | Missing | Suppressed |
> |---------|--------------|-----------------|---------|------------|
> | **Portal (integers)** | `1` | `6` | `-1` | `-3` |
> | Census raw files | `01` (string) | `06` (string) | varies | varies |
>
> **Key difference:** Portal FIPS codes are integers (no leading zeros), while Census files use 2-character strings.

## What is SAIPE?

SAIPE is the Census Bureau's program for producing **model-based** estimates of income and poverty:

- **Primary purpose**: Provide annual poverty estimates for Title I education funding allocations
- **Coverage**: All 50 states, 3,100+ counties, 13,000+ school districts
- **Key measure**: Related children ages 5-17 in families in poverty
- **Update frequency**: Annual (released each December, ~18-month lag)
- **Available years**: 1995-2023 (school districts from 1999)

### Critical Understanding

SAIPE estimates are **model-based**, not direct survey counts:

1. They combine ACS survey data with administrative records (IRS tax returns, SNAP data)
2. They use regression models with "shrinkage" techniques
3. School district estimates are allocated from county totals using within-county shares
4. All estimates contain uncertainty - confidence intervals are essential

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `estimation-methodology.md` | How state/county models work | Understanding model inputs and outputs |
| `school-district-estimates.md` | How district estimates are derived | Working with school district data |
| `variable-definitions.md` | Variables, codes, population universes | Interpreting specific data fields |
| `data-quality.md` | Uncertainty, CV, limitations | Assessing estimate reliability |
| `historical-changes.md` | Methodology changes over time | Comparing across years |
| `comparison-other-sources.md` | SAIPE vs ACS, FRPL, CPS | Choosing between data sources |

## Decision Trees

### What do I need to understand?

```
Understanding SAIPE?
├─ How are estimates created?
│   ├─ State/county models → ./references/estimation-methodology.md
│   └─ School district shares → ./references/school-district-estimates.md
├─ What variables are available?
│   └─ Variable definitions → ./references/variable-definitions.md
├─ How reliable are estimates?
│   ├─ Confidence intervals → ./references/data-quality.md
│   └─ Small district uncertainty → ./references/data-quality.md
├─ Comparing data sources?
│   ├─ SAIPE vs FRPL → ./references/comparison-other-sources.md
│   ├─ SAIPE vs ACS → ./references/comparison-other-sources.md
│   └─ Why estimates differ → ./references/comparison-other-sources.md
└─ Year-to-year changes?
    ├─ Methodology breaks → ./references/historical-changes.md
    └─ Safe comparisons → ./references/historical-changes.md
```

### Common research questions

```
Research question?
├─ District poverty rate for Title I
│   ├─ Use SAIPE (official source for Title I)
│   └─ Note: rates use different numerator/denominator universes
├─ Compare district poverty over time
│   ├─ Check methodology breaks → ./references/historical-changes.md
│   └─ Cannot compare school districts pre/post 2010
├─ Why doesn't SAIPE match FRPL?
│   └─ Different income thresholds → ./references/comparison-other-sources.md
├─ Poverty by race/ethnicity in districts
│   └─ SAIPE does NOT provide race breakdowns for districts
│       Use ACS 5-year estimates instead
└─ Very small district reliability
    └─ Check CV by population size → ./references/data-quality.md
```

## Quick Reference: Key Variables

> **API Implementation:** For URL construction patterns, pagination, and error handling, see the `education-data-query` skill. For comprehensive API learnings, see `agent_reference/EDUCATION_DATA_API_LEARNINGS.md`.

### CRITICAL: Field Name Prefix

All SAIPE fields in the Education Data Portal API have the `est_` prefix:

| Documented Name | Actual API Field |
|-----------------|------------------|
| `population_total` | `est_population_total` |
| `population_5_17` | `est_population_5_17` |
| `population_5_17_poverty` | `est_population_5_17_poverty` |
| `population_5_17_poverty_pct` | `est_population_5_17_poverty_pct` |

### School District Estimates

| Variable | Description | Notes |
|----------|-------------|-------|
| `est_population_total` | Total population in district | Not enrollment - residential population |
| `est_population_5_17` | Children ages 5-17 | School-age population, all enrollment types |
| `est_population_5_17_poverty` | Related children 5-17 in families in poverty | Numerator for poverty calculations |
| `est_population_5_17_poverty_pct` | Percent of children 5-17 in poverty | **Not a true rate** - see notes |

### State/County Estimates (additional)

| Variable | Description |
|----------|-------------|
| `population_0_4_poverty` | Children under 5 in poverty (states only) |
| `population_0_17_poverty` | All children under 18 in poverty |
| `population_poverty` | All ages in poverty |
| `median_household_income` | Median household income |

## Quick Reference: Key Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **Model-based estimates** | Not direct counts; contain model uncertainty | Use confidence intervals |
| **~18 month lag** | 2023 estimates released Dec 2024 | Accept lag for federal allocations |
| **No race/ethnicity** | School district estimates not disaggregated | Use ACS 5-year for demographics |
| **Not enrollment** | Population-based, not enrolled students | Different from FRPL counts |
| **Boundary timing** | May not reflect very recent district changes | Check SDRP update cycle |
| **County allocation** | Districts inherit county model uncertainty | Larger CV for small districts |

## Quick Reference: When to Use SAIPE vs Alternatives

| Use Case | Best Source | Reason |
|----------|-------------|--------|
| Title I allocations | **SAIPE** | Legally mandated source |
| Annual district poverty | **SAIPE** | Only annual source for all districts |
| District poverty by race | ACS 5-year | SAIPE has no race breakdown |
| School-level poverty | ACS 5-year or FRPL | SAIPE is district-level only |
| Most current data | ACS 1-year | Lower lag (but fewer districts) |
| 5-year trends | Use caution | Methodology breaks exist |

## Quick Reference: Confidence Intervals

State and county estimates include 90% confidence intervals. Interpretation:

```
Estimate: 5,000 children in poverty
90% CI: 4,200 - 5,800

Interpretation: We are 90% confident the true value falls
between 4,200 and 5,800.
```

**School district estimates do NOT have published confidence intervals** - use CV guidance:

| District Population | Median CV | Approximate 90% CI Width |
|---------------------|-----------|--------------------------|
| 0-2,500 | 0.67 | +/- 110% |
| 2,500-5,000 | 0.42 | +/- 69% |
| 5,000-10,000 | 0.35 | +/- 58% |
| 10,000-20,000 | 0.28 | +/- 46% |
| 20,000-65,000 | 0.23 | +/- 38% |
| 65,000+ | 0.15 | +/- 25% |

## Data Access via Mirrors

SAIPE data is fetched from mirrors, not via REST API. See `education-data-query` skill.

| Mirror | Path |
|--------|------|
| huggingface | `school-districts/saipe/districts_saipe.parquet` |
| urban_csv | `saipe/school-districts_saipe.csv` |

**Years Available:** 1999-2023

**Example Fetch**:
```python
import polars as pl

url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/school-districts/saipe/districts_saipe.parquet"
df = pl.read_parquet(url)

# Filter locally
df = df.filter(
    (pl.col("fips") == 6) &  # California
    (pl.col("year") == 2022)
)
```

## Poverty Definition

SAIPE uses the **official Census Bureau poverty definition**:

- Poverty threshold based on family size and composition
- Cash income only (excludes non-cash benefits like SNAP)
- Pre-tax income
- 2023 threshold example: $30,900 for family of 4 with 2 children

**"Related children"** = persons ages 5-17 related to householder by birth, marriage, or adoption who live in families (excludes foster children, group quarters residents).

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Model-based estimation | `./references/estimation-methodology.md` |
| Shrinkage estimators | `./references/estimation-methodology.md` |
| ACS integration | `./references/estimation-methodology.md` |
| Administrative records | `./references/estimation-methodology.md` |
| School district methodology | `./references/school-district-estimates.md` |
| Within-county shares | `./references/school-district-estimates.md` |
| Grade relevance | `./references/school-district-estimates.md` |
| Overlapping districts | `./references/school-district-estimates.md` |
| Variable definitions | `./references/variable-definitions.md` |
| Population universes | `./references/variable-definitions.md` |
| Poverty thresholds | `./references/variable-definitions.md` |
| Confidence intervals | `./references/data-quality.md` |
| Coefficient of variation | `./references/data-quality.md` |
| Small area uncertainty | `./references/data-quality.md` |
| Geocoding limitations | `./references/data-quality.md` |
| 2005 ACS switch | `./references/historical-changes.md` |
| 2010 decennial update | `./references/historical-changes.md` |
| Methodology breaks | `./references/historical-changes.md` |
| SAIPE vs FRPL | `./references/comparison-other-sources.md` |
| SAIPE vs ACS | `./references/comparison-other-sources.md` |
| Title I requirements | `./references/comparison-other-sources.md` |
