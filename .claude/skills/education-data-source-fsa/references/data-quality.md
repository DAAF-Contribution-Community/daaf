# FSA Data Quality and Limitations

Reference for understanding data quality issues, coverage limitations, and timing considerations when working with FSA data in the Urban Institute Education Data Portal.

## Contents

- [Overview](#overview)
- [Year Coverage by Endpoint](#year-coverage-by-endpoint)
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
| Coverage gaps | Not all institutions in all endpoints | Check institutional availability |
| Methodology changes | Calculation rules change over time | Document methods by year |
| Self-reported data | Subject to reporting errors | Cross-validate with other sources |

## Year Coverage by Endpoint

### Available Years

| Endpoint | Earliest Year | Latest Year | Total Years |
|----------|---------------|-------------|-------------|
| `/fsa/grants/` | 1999 | 2018 | 20 |
| `/fsa/loans/` | 1999 | 2018 | 20 |
| `/fsa/campus-based-volume/` | 2001 | 2017 | 17 |
| `/fsa/financial-responsibility/` | 2006 | 2016 | 11 |
| `/fsa/90-10-revenue-percentages/` | 2014 | 2017 | 4 |

### Timeline Visualization

```
         1999  2001  2006  2010  2014  2016  2017  2018
Grants   |----------------------------------------------|
Loans    |----------------------------------------------|
Campus   |     |-------------------------------------|   |
Fin Resp |          |---------------------|              |
90/10    |                    |---------|               |
```

### Data Currency

**Note**: The Education Data Portal updates periodically. Check the [Updates Timeline](https://educationdata.urban.org/documentation/#data_update) for the most recent data additions.

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

### Institutional Count by Endpoint (Approximate)

| Endpoint | Records per Year | Unique Institutions |
|----------|------------------|---------------------|
| Grants | ~5,500-6,500 | Varies by year |
| Loans | ~5,500-6,500 | Varies by year |
| Campus-Based | ~4,500-5,500 | Varies by year |
| Financial Responsibility | ~2,500-3,500 | Private/for-profit only |
| 90/10 | ~2,000-3,000 | For-profit only |

## Data Timing and Lag

### Award Year vs. Fiscal Year

| Data Type | Reporting Period | Definition |
|-----------|------------------|------------|
| Grants/Loans | Award year | July 1 - June 30 (e.g., 2017-18) |
| Campus-Based | Award year | July 1 - June 30 |
| Financial Responsibility | Fiscal year | Institution's fiscal year end |
| 90/10 | Fiscal year | Institution's fiscal year end |

### Data Publication Lag

| Endpoint | Typical Lag | Reason |
|----------|-------------|--------|
| Grants/Loans | 1-2 years | Reconciliation period after award year |
| Campus-Based | 1-2 years | FISAP reporting cycle |
| Financial Responsibility | 2-3 years | Audit completion + analysis |
| 90/10 | 2-3 years | Fiscal year audits required |

### Example: What Data is Available When?

If current date is January 2026:
- Grants/Loans: Likely through 2023-24 or 2024-25 award year
- Financial Responsibility: Likely through 2022 or 2023 fiscal year
- 90/10: Likely through 2022 or 2023 fiscal year

## Known Data Issues

### Grant Data Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| Pell timing | Disbursements vs. obligations | May not match other sources |
| Year-round Pell | Multiple grants per student | Recipient counts may double-count |
| FSEOG variability | Campus-based allocation varies | Not comparable across institutions |

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
| Limited years | Only 2014-2017 available | Short time series |
| Pre-2021 methodology | VA/DoD not counted as federal | Not comparable to current rule |
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

**Grants Endpoint:**
- Institution doesn't participate in FSEOG → FSEOG values = -2
- No students received Pell → Pell values = 0 or -1
- Data not yet available → null

**Loans Endpoint:**
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
# Approach 1: Filter to complete records
df = df.dropna(subset=['pell_recipients', 'pell_disbursements'])

# Approach 2: Replace missing codes with NaN
import numpy as np
df = df.replace([-1, -2, -3], np.nan)

# Approach 3: Keep and document
df['pell_reported'] = df['pell_recipients'] >= 0
```

## Methodological Considerations

### Changes Over Time

| Year | Change | Impact |
|------|--------|--------|
| 2010 | Direct Loan transition | FFEL phased out; Direct Loan data increases |
| 2012 | Grad subsidized eliminated | Grad loan composition changes |
| 2017 | Perkins discontinued | No new Perkins loans after this |
| 2021 | 90/10 methodology change | VA/DoD now counted as federal |
| 2024 | SAI replaces EFC | May affect Pell eligibility patterns |

### Comparability Issues

| Comparison | Concern | Recommendation |
|------------|---------|----------------|
| Year-over-year | Enrollment changes | Calculate per-student metrics |
| Cross-sector | Different program participation | Control for sector |
| Pre/post-2010 | FFEL to Direct Loan | Combine loan types or note break |
| State-level | Different state aid programs | Account for state context |

### Inflation Adjustment

Dollar amounts are nominal (not inflation-adjusted):

```python
# Example: Adjust to 2018 dollars using CPI
# Get CPI multipliers for each year
df['pell_real_2018'] = df['pell_disbursements'] * df['cpi_multiplier']
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

1. **Check year coverage**: Verify endpoint has data for your period
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

| Check | Method | Flag If |
|-------|--------|---------|
| Pell average | pell_avg_amount | > $7,500 or < $500 |
| Recipient count | pell_recipients | > total_enrollment |
| Composite score | composite_score | Outside -1 to 3 range |
| 90/10 percentage | title_iv_percentage | > 100% or < 0% |

### Cross-Validation

```python
# Check: Pell disbursements should equal recipients × average
calculated = df['pell_recipients'] * df['pell_avg_amount']
discrepancy = abs(df['pell_disbursements'] - calculated) / df['pell_disbursements']
# Flag if discrepancy > 5%
```

### Outlier Detection

```python
# Identify extreme values
import numpy as np
q1, q99 = df['composite_score'].quantile([0.01, 0.99])
outliers = df[(df['composite_score'] < q1) | (df['composite_score'] > q99)]
```
