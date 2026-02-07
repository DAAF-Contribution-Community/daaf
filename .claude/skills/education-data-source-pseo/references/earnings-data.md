# Earnings Data

Graduate earnings tabulations from PSEO: percentile earnings, cohort definitions, and labor force attachment requirements.

## Contents

- [Earnings Overview](#earnings-overview)
- [Percentile Earnings Variables](#percentile-earnings-variables)
- [Labor Force Attachment](#labor-force-attachment)
- [Cohort Definitions](#cohort-definitions)
- [Earnings Adjustments](#earnings-adjustments)
- [Interpretation Guidelines](#interpretation-guidelines)

## Earnings Overview

The Graduate Earnings tabulations provide earnings percentiles for graduates at three time points post-graduation:

| Time Point | Definition |
|------------|------------|
| Year 1 | First full calendar year after graduation year |
| Year 5 | Fifth full calendar year after graduation year |
| Year 10 | Tenth full calendar year after graduation year |

**Example**: A student graduating in May 2015:
- Year 1 = Calendar year 2016 (Jan-Dec)
- Year 5 = Calendar year 2020
- Year 10 = Calendar year 2025

## Percentile Earnings Variables

### Variable Names

| Variable | Description |
|----------|-------------|
| `Y1_P25_EARNINGS` | 25th percentile earnings, 1 year post-graduation |
| `Y1_P50_EARNINGS` | Median (50th percentile) earnings, 1 year post-graduation |
| `Y1_P75_EARNINGS` | 75th percentile earnings, 1 year post-graduation |
| `Y5_P25_EARNINGS` | 25th percentile earnings, 5 years post-graduation |
| `Y5_P50_EARNINGS` | Median earnings, 5 years post-graduation |
| `Y5_P75_EARNINGS` | 75th percentile earnings, 5 years post-graduation |
| `Y10_P25_EARNINGS` | 25th percentile earnings, 10 years post-graduation |
| `Y10_P50_EARNINGS` | Median earnings, 10 years post-graduation |
| `Y10_P75_EARNINGS` | 75th percentile earnings, 10 years post-graduation |

### Graduate Counts

| Variable | Description |
|----------|-------------|
| `Y1_GRADS` | Total graduates with observable earnings, Year 1 |
| `Y5_GRADS` | Total graduates with observable earnings, Year 5 |
| `Y10_GRADS` | Total graduates with observable earnings, Year 10 |

### Status Flags

| Variable | Description |
|----------|-------------|
| `STATUS_Y1_EARNINGS` | Status flag for all Y1 earnings variables |
| `STATUS_Y5_EARNINGS` | Status flag for all Y5 earnings variables |
| `STATUS_Y10_EARNINGS` | Status flag for all Y10 earnings variables |

**Status flag values:**

| Code | Meaning |
|------|---------|
| 1 | Valid data |
| 5 | Suppressed (cell count < 30) |

## Labor Force Attachment

Not all graduates are included in earnings statistics. PSEO applies labor force attachment restrictions to focus on workers who are meaningfully employed.

### Inclusion Criteria

A graduate is included if they meet BOTH requirements:

1. **Minimum earnings threshold**: Annual earnings ≥ full-time federal minimum wage equivalent
   - Calculated as: Federal minimum wage × 40 hours × 52 weeks
   - Example: At $7.25/hour = $15,080/year minimum

2. **Employment continuity**: Earnings in at least 3 of 4 quarters in the reference year

### Exclusions

Graduates excluded from earnings tabulations:

| Reason | Impact |
|--------|--------|
| Earnings below threshold | Low earners/part-time workers excluded |
| Fewer than 3 quarters with earnings | Seasonal/intermittent workers excluded |
| No match in LEHD | Self-employed, uncovered employment |
| Zero earnings all year | Graduate students, not in labor force |

### Non-Employed/Marginal Employment

Graduates who don't meet attachment criteria are counted in residual variables:

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_NME` | Non-employed or marginally employed, Year 1 |
| `Y5_GRADS_NME` | Non-employed or marginally employed, Year 5 |
| `Y10_GRADS_NME` | Non-employed or marginally employed, Year 10 |

## Cohort Definitions

Graduates are grouped into cohorts based on graduation year. Cohort length varies by degree level:

### Bachelor's Degree Cohorts (3-year)

| GRAD_COHORT | Years Included |
|-------------|----------------|
| 2001 | 2001, 2002, 2003 |
| 2004 | 2004, 2005, 2006 |
| 2007 | 2007, 2008, 2009 |
| 2010 | 2010, 2011, 2012 |
| 2013 | 2013, 2014, 2015 |
| 2016 | 2016, 2017, 2018 |
| 2019 | 2019, 2020, 2021 |

### All Other Degree Levels (5-year)

Includes: Certificates, Associate's, Master's, Doctoral

| GRAD_COHORT | Years Included |
|-------------|----------------|
| 2001 | 2001, 2002, 2003, 2004, 2005 |
| 2006 | 2006, 2007, 2008, 2009, 2010 |
| 2011 | 2011, 2012, 2013, 2014, 2015 |
| 2016 | 2016, 2017, 2018, 2019, 2020 |

### Why Different Cohort Lengths?

- **Bachelor's (3-year)**: Higher graduate counts allow smaller cohorts while maintaining sufficient sample sizes
- **Other degrees (5-year)**: Smaller programs require larger cohorts to avoid suppression

### All-Cohort Aggregations

When `GRAD_COHORT=0000`, data spans all available cohorts. `GRAD_COHORT_YEARS` indicates the cohort span:
- `3` for Bachelor's
- `5` for all other degree levels

## Earnings Adjustments

### Inflation Adjustment

All earnings are converted to **2022 dollars** using the Consumer Price Index for All Urban Consumers (CPI-U).

Example conversion:
```
Real_2022 = Nominal_Year × (CPI-U_2022 / CPI-U_Year)
```

### Multiple Jobs

Earnings include total annual earnings from **all jobs**:
- If a graduate works multiple jobs, all covered earnings are summed
- Part-time job + full-time job = combined earnings

### Earnings Sources

Included:
- Wages and salaries from UI-covered employment
- Federal civilian employment (from OPM)

Excluded:
- Self-employment income
- Investment/capital income
- Uncovered employment

## Interpretation Guidelines

### Comparing Programs

When comparing earnings across programs:

1. **Same degree level**: Only compare Bachelor's to Bachelor's, etc.
2. **Same time point**: Compare Y1 to Y1, Y5 to Y5
3. **Check sample sizes**: Large differences may reflect small cells
4. **Consider field**: Some fields have delayed earnings (e.g., grad school track)

### Understanding Percentiles

| Percentile | Meaning |
|------------|---------|
| 25th (P25) | 25% of graduates earn less than this |
| 50th (P50) | Half earn more, half earn less (median) |
| 75th (P75) | 25% of graduates earn more than this |

**Interquartile range (IQR)** = P75 - P25: Indicates earnings dispersion

### Limitations

| Issue | Impact |
|-------|--------|
| Selection into labor force | Higher earners more likely to meet attachment criteria |
| Graduate school | Enrolled grad students may be excluded (low/no earnings) |
| Geographic cost of living | Raw earnings don't account for regional differences |
| Field-specific patterns | Some fields have non-linear career trajectories |
| Cohort effects | Economic conditions vary by graduation year |

### Example Analysis

**Question**: What do Computer Science Bachelor's graduates from UT Austin earn?

```
Institution: 00365800 (UT Austin)
Degree Level: 05 (Bachelor's)
CIP Code: 11 (Computer and Information Sciences)
Cohort: 2016 (graduates 2016-2018)

Y1_P50_EARNINGS: $62,500 (median 1 year out)
Y5_P50_EARNINGS: $95,000 (median 5 years out)
Y1_GRADS: 450 (sample size)
```

**Interpretation**: Median CS graduate from UT Austin earned $62,500 one year after graduation (in 2022 dollars), growing to $95,000 five years out. With 450 graduates in the cell, this estimate is relatively precise.
