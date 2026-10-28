# FSA Data Quality and Limitations

Reference for understanding data quality issues, coverage limitations, and timing considerations when working with FSA data in the Urban Institute Education Data Portal.

## Contents

- [Overview](#overview)
- [Year Coverage by Dataset](#year-coverage-by-dataset)
- [Institutional Coverage](#institutional-coverage)
- [Data Timing and Lag](#data-timing-and-lag)
- [Known Data Issues](#known-data-issues)
- [Missing Data Patterns](#missing-data-patterns)
- [Methodological Considerations](#methodological-considerations)
- [Data Source Comparison](#data-source-comparison)

## Overview

FSA data provides valuable information on federal student aid programs but has important limitations that analysts should understand before conducting research.

### Key Considerations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Data lag | 1-3 years behind current year | Note data vintage in analysis |
| Coverage gaps | Not all institutions in all datasets | Check institutional availability |
| Methodology changes | Calculation rules change over time | Document methods by year |
| Self-reported data | Subject to reporting errors | Cross-validate with other sources |

## Year Coverage by Dataset

### Available Years (Portal Mirror)

| Dataset Path | Earliest Year | Latest Year | Total Years |
|-------------|---------------|-------------|-------------|
| `fsa/colleges_fsa_grants` | 1999 | 2021 | 23 |
| `fsa/colleges_fsa_loans` | 1999 | 2021 | 23 |
| `fsa/colleges_fsa_campus_based_volume` | 2001 | 2021 | 21 |
| `fsa/colleges_fsa_composite_scores` | 2006 | 2016 | 11 |
| `fsa/colleges_fsa_90_10_revenue_percentages` | 2014 | 2021 | 8 |

> **Loans: rows from 1999, volume from 2003.** The year range above is row presence. In the pinned mirror vintage (Portal v0.26.1, probed 2026-10-27), `fsa/colleges_fsa_loans` has rows for 1999-2002, but `value_loan_disbursements_unitid` sums to 0 in each of those years for both Direct Loan (codes 3+6+9) and FFEL (codes 10+11+14); the first non-zero year is 2003 (FFEL $36.1B, Direct $11.9B). Within FFEL PLUS, the combined code 14 carries volume from 2003, but its split is empty earlier: Parent PLUS (12) is null in every row before 2006, and Grad PLUS (13) first has positive values in 2005 (337 rows, $69M). Grad PLUS loans began with disbursements on or after 1 July 2006, so the 2005 values need a year-convention check before use (inference, not probed); use code 14 for FFEL PLUS totals before 2006. Only the unitid-level disbursement column was checked. Maintainer-only run log, not shipped: `research/2026-09-18_AdHoc_Typesafe_Classifier_Experiments/probes/2026-10-27_mF_fsa_probe.py`.

### Timeline Visualization

```
         1999  2001  2006  2010  2014  2016  2021
Grants   |-----------------------------------------------|
Loans    |-----------------------------------------------|
Campus   |     |---------------------------------------------|
Fin Resp |          |---------------------|
90/10    |                    |-----------------------------|
```

### Data Currency

**Note**: Data is accessed via the Education Data Portal mirrors (see `mirrors.yaml` for mirror configuration, `datasets-reference.md` for canonical paths, `fetch-patterns.md` for fetch code).

## Institutional Coverage

### Title IV Participation Universe

FSA data covers institutions that:
- Are certified to participate in Title IV programs
- Have a valid Program Participation Agreement (PPA)
- Actually disbursed Title IV funds during the year

### Coverage by Sector

| Sector | Grants/Loans Coverage | Financial Responsibility | 90/10 |
|--------|----------------------|-------------------------|-------|
| Public 4-year | High | Limited* | N/A |
| Public 2-year | High | Limited* | N/A |
| Private nonprofit | High | Good | N/A |
| Private for-profit | High | Good | Complete |

*Public institutions often exempt from composite score requirements

### Institutions NOT in FSA Data

- Non-Title IV participating schools
- Schools that lost eligibility
- Schools that never disbursed aid in a given year
- Foreign institutions (even if Title IV eligible)
- Schools closed before data collection

### Institutional Count by Dataset (Approximate)

| Dataset | Records per Year | Unique Institutions |
|----------|------------------|---------------------|
| Grants | ~5,500-6,500 | Varies by year |
| Loans | ~5,500-6,500 | Varies by year |
| Campus-Based | ~4,500-5,500 | Varies by year |
| Financial Responsibility | ~2,500-3,500 | Private/for-profit only |
| 90/10 | ~1,700-2,000 | For-profit only |

## Data Timing and Lag

### Award Year vs. Fiscal Year

| Data Type | Reporting Period | Definition |
|-----------|------------------|------------|
| Grants/Loans | Award year | July 1 - June 30 (e.g., 2017-18) |
| Campus-Based | Award year | July 1 - June 30 |
| Financial Responsibility | Fiscal years ending in the award year | `year` = fall start year of that award year (2015 = FYE 7/1/2015-6/30/2016) |
| 90/10 | Fiscal years ending in the award year | `year` = fall start year of that award year (2015 = FYE 7/1/2015-6/30/2016) |

### Data Publication Lag

| Dataset | Typical Lag | Reason |
|----------|-------------|--------|
| Grants/Loans | 1-2 years | Reconciliation period after award year |
| Campus-Based | 1-2 years | FISAP reporting cycle |
| Financial Responsibility | 2-3 years | Audit completion + analysis |
| 90/10 | 2-3 years | Fiscal year audits required |

### Example: What Data is Available When?

If current date is January 2026 (illustrative; verify against the FSA Data Center):
- Grants/Loans: Likely through 2023-24 or 2024-25 award year
- Financial Responsibility: Likely through 2022 or 2023 fiscal year
- 90/10: Likely through 2022 or 2023 fiscal year

## Known Data Issues

### Grant Data Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| Pell timing | Disbursements vs. obligations | May not match other sources |
| Year-round Pell | Multiple grants per student | Recipient counts may double-count |
| FSEOG variability (campus-based dataset, `award_type` 1; not a grants-dataset code) | Campus-based allocation varies | Not comparable across institutions |

### Loan Data Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| Origination vs. disbursement | Data may use different definitions | Verify metric definition |
| PLUS loan attribution | Parent vs. student counts | Clarify what "recipient" means |
| Consolidation loans | May not be in institutional data | Aggregate data may differ |
| Default recoveries | Affect net disbursement figures | Historical comparisons impacted |

### Financial Responsibility Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| Public institution gaps | Many publics exempt from reporting | Sector comparisons limited |
| Accounting standard changes | FASB/GASB changes affect ratios | Time series comparisons difficult |
| Related-party adjustments | Vary by interpretation | Scores may not be fully comparable |
| Restatements | Prior years may be restated | Check for data updates |

### 90/10 Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| Limited years | 2014-2021 available | 8-year time series |
| Proportion format | `rev_pct_90_10` is a proportion (0-1), not percentage (0-100) | Compare to 0.90 threshold, not 90 |
| ARPA (P.L. 117-2) definition not in Portal | All Portal years (2014-2021) use the pre-ARPA Title IV-only numerator; VA/DoD and other federal education funds count as federal only for fiscal years beginning on or after 2023-01-01 | Portal data are not comparable to post-2023 ED 90/10 reports |
| Revenue recognition | Timing differences | Annual figures may be volatile |
| Audit adjustments | May differ from published data | Verify with official sources |

## Missing Data Patterns

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| -1 | Not reported | Institution did not report value |
| -2 | Not applicable | Variable doesn't apply to institution |
| -3 | Suppressed | Small cell size protection |
| null/NA | No data | Record or field not present |

### Common Missing Data Scenarios

**Grants Dataset:**
- No students received Pell → Pell values = 0 or -1
- Data not yet available → null

**Campus-Based Dataset:**
- Institution doesn't participate in FSEOG (`award_type` 1) → FSEOG values = -2

**Loans Dataset:**
- Undergraduate-only school → Grad PLUS = -2
- No students took loans → values = 0

**Financial Responsibility:**
- Public institution → entire record may be missing
- Score calculation error → composite_score = null

**90/10:**
- Nonprofit/public institution → no record
- New proprietary school → may not have full year data

### Handling Missing Data

```python
import polars as pl

# Approach 1: Filter to non-null records
df = df.filter(pl.col("grant_recipients_unitid").is_not_null())

# Approach 2: Filter out missing data codes
df = df.filter(~pl.col("fips").is_in([-1, -2, -3]))

# Approach 3: Replace missing codes with null
df = df.with_columns(
    pl.when(pl.col("fips").is_in([-1, -2, -3]))
    .then(None)
    .otherwise(pl.col("fips"))
    .alias("fips_clean")
)
```

```r
library(dplyr)

# Approach 1: Filter to non-null records
df <- df |> filter(!is.na(grant_recipients_unitid))

# Approach 2: Filter out missing data codes
df <- df |> filter(!(fips %in% c(-1, -2, -3)))

# Approach 3: Replace missing codes with NA
df <- df |> mutate(
  fips_clean = if_else(fips %in% c(-1, -2, -3), NA, fips)
)
```

## Methodological Considerations

### Changes Over Time

| Year | Change | Impact |
|------|--------|--------|
| 2010 (= 2010-11) | First Portal year with no new FFEL loans (HCERA, P.L. 111-152) | In the pinned mirror vintage (Portal v0.26.1; `fsa/colleges_fsa_loans`, probed 2026-10-27), FFEL codes 10-14 keep their rows every year through 2021 (the same row count as every other loan_type in a year, e.g. 5,266 in 2010), but from `year` 2010 every `value_loan_disbursements_unitid` value is null (0 of 300,570 rows above zero). Direct Loan disbursements (codes 3+6+9) rise from $42.6B (2009) to $91.1B (2010). FFEL subsequent disbursements still made in 2010-11 under GEN-10-05 do not appear in the file. Treat FFEL rows from 2010 as structurally empty, not as zero lending; earlier years mix FFEL and Direct Loan |
| 2012 | Grad subsidized eliminated | Grad loan composition changes |
| 2017 | Perkins discontinued | No new Perkins loans after September 30, 2017; final disbursements permitted through June 30, 2018, so Portal campus-based `year`=2017 (2017-18) can still contain Perkins disbursements |
| 2023 (FYs beginning on/after Jan 1) | ARPA 90/10 definition | VA/DoD funds count as federal; outside Portal coverage |
| 2024 | SAI replaces EFC | May affect Pell eligibility patterns |

### Comparability Issues

| Comparison | Concern | Recommendation |
|------------|---------|----------------|
| Year-over-year | Enrollment changes | Calculate per-student metrics |
| Cross-sector | Different program participation | Control for sector |
| Pre/post-2010 | FFEL to Direct Loan (`year` 2010 = 2010-11 is the first year with no new FFEL loans) | Combine loan types or note break |
| State-level | Different state aid programs | Account for state context |

### Inflation Adjustment

Dollar amounts are nominal (not inflation-adjusted):

```python
import polars as pl

# Example: Adjust to 2021 dollars using CPI multipliers
cpi_multipliers = {2018: 1.08, 2019: 1.06, 2020: 1.04, 2021: 1.00}

df = df.with_columns(
    (pl.col("value_grants_disbursed_unitid") *
     pl.col("year").replace(cpi_multipliers)).alias("grants_real_2021")
)
```

```r
library(dplyr)

# Example: Adjust to 2021 dollars using CPI multipliers
df <- df |> mutate(
  cpi_multiplier = recode_values(year,  # recode_values supersedes case_match (soft-deprecated dplyr 1.2.0)
    2018 ~ 1.08,
    2019 ~ 1.06,
    2020 ~ 1.04,
    2021 ~ 1.00
  ),
  grants_real_2021 = value_grants_disbursed_unitid * cpi_multiplier
)
```

## Data Source Comparison

### FSA vs. IPEDS Financial Aid

| Aspect | FSA Data | IPEDS SFA |
|--------|----------|-----------|
| Source | FSA administrative data | Institutional survey |
| Timing | Award year, with lag | Fall cohort, annual |
| Coverage | All Title IV institutions | Title IV institutions |
| Detail | Program-specific | Aggregated categories |
| Accuracy | Administrative records | Self-reported |

### When to Use Each

| Use Case | Preferred Source | Reason |
|----------|------------------|--------|
| Total Pell disbursements | FSA | Direct administrative data |
| Net price by income | IPEDS | Includes institutional aid |
| Loan composition | FSA | Detailed by program |
| Aid by enrollment status | IPEDS | Includes part-time |

### FSA vs. College Scorecard

| Aspect | FSA Data | College Scorecard |
|--------|----------|------------------|
| Aid data | Direct from FSA | Derived/processed |
| Outcomes | Limited | Earnings, debt, repayment |
| Program-level | Institutional | Some program-level |
| Update frequency | Periodic | Annual |

## Best Practices

### Before Analysis

1. **Check year coverage**: Verify dataset has data for your period
2. **Check institutional coverage**: Confirm institutions of interest are present
3. **Review missing data**: Understand patterns of missingness
4. **Note methodology**: Document which rules apply to your years

### During Analysis

1. **Use appropriate filters**: Filter out missing/not-applicable values
2. **Control for enrollment**: Calculate per-student metrics when comparing
3. **Acknowledge limitations**: Note coverage gaps in findings
4. **Cross-validate**: Check key findings against other sources

### Reporting Results

1. **State data vintage**: Note the year(s) of data used
2. **Document exclusions**: Explain any records dropped
3. **Acknowledge gaps**: Note sectors or years not covered
4. **Cite appropriately**: Credit Education Data Portal and original FSA data

## Data Quality Checks

### Reasonableness Checks

| Check | Variable | Flag If |
|-------|----------|---------|
| Composite score | `financial_resp_score` | Outside -1 to 3 range |
| 90/10 proportion | `rev_pct_90_10` | > 1.01 or < 0 (stored as proportion 0-1, not percentage) |
| Grant values | `value_grants_disbursed_*` | Negative values |
| Recipient count | `grant_recipients_*` | Negative values |

### Cross-Validation

```python
import polars as pl

# Check: 90/10 calculation matches components
# NOTE: rev_pct_90_10 is a proportion (0-1), not percentage (0-100)
df = df.with_columns(
    (pl.col("numerator_90_10") / pl.col("denominator_90_10"))
    .alias("calculated_pct")
)

# Flag discrepancies > 0.01 (1 percentage point)
df_discrepancy = df.filter(
    (pl.col("rev_pct_90_10") - pl.col("calculated_pct")).abs() > 0.01
)
```

```r
library(dplyr)

# Check: 90/10 calculation matches components
# NOTE: rev_pct_90_10 is a proportion (0-1), not percentage (0-100)
df <- df |> mutate(
  calculated_pct = numerator_90_10 / denominator_90_10
)

# Flag discrepancies > 0.01 (1 percentage point)
df_discrepancy <- df |> filter(
  abs(rev_pct_90_10 - calculated_pct) > 0.01
)
```

### Outlier Detection

```python
import polars as pl

# Identify extreme values
q01 = df["financial_resp_score"].quantile(0.01)
q99 = df["financial_resp_score"].quantile(0.99)

outliers = df.filter(
    (pl.col("financial_resp_score") < q01) |
    (pl.col("financial_resp_score") > q99)
)
```

```r
library(dplyr)

# Identify extreme values
q01 <- quantile(df$financial_resp_score, 0.01, na.rm = TRUE)
q99 <- quantile(df$financial_resp_score, 0.99, na.rm = TRUE)

outliers <- df |> filter(
    (financial_resp_score < q01) |
    (financial_resp_score > q99)
)
```
