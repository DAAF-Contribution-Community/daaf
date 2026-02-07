# FSA Variable Definitions

Comprehensive reference for variables available in FSA endpoints through the Urban Institute Education Data Portal.

## Contents

- [Overview](#overview)
- [Grants Endpoint Variables](#grants-endpoint-variables)
- [Loans Endpoint Variables](#loans-endpoint-variables)
- [Campus-Based Volume Variables](#campus-based-volume-variables)
- [Financial Responsibility Variables](#financial-responsibility-variables)
- [90/10 Revenue Variables](#9010-revenue-variables)
- [Common Identifiers](#common-identifiers)
- [Missing Data Codes](#missing-data-codes)

## Overview

FSA data in the Education Data Portal is organized into five endpoints, each with specific variables related to Title IV aid programs.

### Endpoint Summary

| Endpoint | URL Pattern | Years | Record Count |
|----------|-------------|-------|--------------|
| Grants | `/fsa/grants/{year}/` | 1999-2018 | ~6,000/year |
| Loans | `/fsa/loans/{year}/` | 1999-2018 | ~6,000/year |
| Campus-Based Volume | `/fsa/campus-based-volume/{year}/` | 2001-2017 | ~5,000/year |
| Financial Responsibility | `/fsa/financial-responsibility/{year}/` | 2006-2016 | ~3,000/year |
| 90/10 Revenue Percentages | `/fsa/90-10-revenue-percentages/{year}/` | 2014-2017 | ~2,500/year |

## Grants Endpoint Variables

Endpoint: `/api/v1/college-university/fsa/grants/{year}/`

### Identification Variables

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier (6-digit) |
| `year` | Integer | Academic award year (fall start year) |
| `fips` | Integer | State FIPS code |

### Pell Grant Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `pell_recipients` | Integer | Number of Pell Grant recipients | Count |
| `pell_disbursements` | Float | Total Pell Grant disbursements | Dollars |
| `pell_avg_amount` | Float | Average Pell Grant per recipient | Dollars |

**Calculated field:**
```
pell_avg_amount = pell_disbursements / pell_recipients
```

### Other Grant Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `fseog_recipients` | Integer | FSEOG recipients | Count |
| `fseog_disbursements` | Float | Total FSEOG disbursements | Dollars |

### Example Query

```
# Get all Pell Grant data for California institutions in 2018
/api/v1/college-university/fsa/grants/2018/?fips=6
```

## Loans Endpoint Variables

Endpoint: `/api/v1/college-university/fsa/loans/{year}/`

### Identification Variables

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier |
| `year` | Integer | Academic award year |
| `fips` | Integer | State FIPS code |

### Direct Subsidized Loan Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `dl_sub_recipients` | Integer | Direct Subsidized Loan recipients | Count |
| `dl_sub_disbursements` | Float | Direct Subsidized Loan disbursements | Dollars |
| `dl_sub_avg_amount` | Float | Average Direct Subsidized Loan | Dollars |

### Direct Unsubsidized Loan Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `dl_unsub_recipients` | Integer | Direct Unsubsidized Loan recipients | Count |
| `dl_unsub_disbursements` | Float | Direct Unsubsidized Loan disbursements | Dollars |
| `dl_unsub_avg_amount` | Float | Average Direct Unsubsidized Loan | Dollars |

### Parent PLUS Loan Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `dl_parent_plus_recipients` | Integer | Parent PLUS Loan recipients | Count |
| `dl_parent_plus_disbursements` | Float | Parent PLUS Loan disbursements | Dollars |
| `dl_parent_plus_avg_amount` | Float | Average Parent PLUS Loan | Dollars |

### Graduate PLUS Loan Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `dl_grad_plus_recipients` | Integer | Graduate PLUS Loan recipients | Count |
| `dl_grad_plus_disbursements` | Float | Graduate PLUS Loan disbursements | Dollars |
| `dl_grad_plus_avg_amount` | Float | Average Graduate PLUS Loan | Dollars |

### Aggregate Loan Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `dl_total_recipients` | Integer | Total Direct Loan recipients | Count |
| `dl_total_disbursements` | Float | Total Direct Loan disbursements | Dollars |

### Example Query

```
# Get all loan data for a specific institution
/api/v1/college-university/fsa/loans/2018/?unitid=110635
```

## Campus-Based Volume Variables

Endpoint: `/api/v1/college-university/fsa/campus-based-volume/{year}/`

### Identification Variables

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier |
| `year` | Integer | Academic award year |
| `fips` | Integer | State FIPS code |

### Federal Work-Study Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `fws_allocation` | Float | Federal allocation for FWS | Dollars |
| `fws_recipients` | Integer | FWS recipients | Count |
| `fws_disbursements` | Float | Total FWS earnings paid | Dollars |
| `fws_avg_amount` | Float | Average FWS per recipient | Dollars |

### FSEOG Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `fseog_allocation` | Float | Federal allocation for FSEOG | Dollars |
| `fseog_recipients` | Integer | FSEOG recipients | Count |
| `fseog_disbursements` | Float | Total FSEOG disbursements | Dollars |
| `fseog_avg_amount` | Float | Average FSEOG per recipient | Dollars |

### Perkins Loan Variables (Historical)

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `perkins_allocation` | Float | Federal allocation for Perkins | Dollars |
| `perkins_recipients` | Integer | Perkins Loan recipients | Count |
| `perkins_disbursements` | Float | Total Perkins disbursements | Dollars |
| `perkins_avg_amount` | Float | Average Perkins Loan | Dollars |

**Note**: Perkins Loan program discontinued; no new loans after September 30, 2017.

### Example Query

```
# Get campus-based data for 2015
/api/v1/college-university/fsa/campus-based-volume/2015/
```

## Financial Responsibility Variables

Endpoint: `/api/v1/college-university/fsa/financial-responsibility/{year}/`

### Identification Variables

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier |
| `year` | Integer | Fiscal year |
| `fips` | Integer | State FIPS code |

### Composite Score Variables

| Variable | Type | Description | Range |
|----------|------|-------------|-------|
| `composite_score` | Float | Overall financial responsibility score | -1.0 to 3.0 |

### Component Ratio Variables

| Variable | Type | Description | Typical Range |
|----------|------|-------------|---------------|
| `primary_reserve_ratio` | Float | Expendable resources / Total expenses | -0.5 to 1.0+ |
| `equity_ratio` | Float | Modified equity / Modified assets | -0.5 to 0.5+ |
| `net_income_ratio` | Float | Net income / Total revenue | -0.2 to 0.2+ |

### Score Interpretation

| Composite Score | Classification |
|-----------------|----------------|
| ≥ 1.5 | Financially Responsible |
| 1.0 - 1.49 | In the Zone |
| < 1.0 | Not Financially Responsible |

### Example Query

```
# Get financial responsibility scores for 2016
/api/v1/college-university/fsa/financial-responsibility/2016/

# Filter for institutions with scores below 1.5
/api/v1/college-university/fsa/financial-responsibility/2016/?composite_score__lt=1.5
```

## 90/10 Revenue Variables

Endpoint: `/api/v1/college-university/fsa/90-10-revenue-percentages/{year}/`

### Identification Variables

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier |
| `year` | Integer | Fiscal year |
| `fips` | Integer | State FIPS code |

### Revenue Variables

| Variable | Type | Description | Units |
|----------|------|-------------|-------|
| `title_iv_percentage` | Float | Percentage of revenue from Title IV | Percent (0-100) |
| `title_iv_revenue` | Float | Total Title IV revenue | Dollars |
| `total_revenue` | Float | Total revenue from eligible programs | Dollars |
| `non_title_iv_revenue` | Float | Revenue from non-Title IV sources | Dollars |

### Calculated Relationship

```
title_iv_percentage = (title_iv_revenue / total_revenue) × 100
non_title_iv_revenue = total_revenue - title_iv_revenue
```

### Compliance Interpretation

| Title IV Percentage | Status |
|--------------------|--------|
| ≤ 90% | Compliant |
| > 90% (1 year) | Provisional |
| > 90% (2 consecutive years) | Ineligible |

### Example Query

```
# Get 90/10 data for 2017
/api/v1/college-university/fsa/90-10-revenue-percentages/2017/

# Filter for institutions above 85%
/api/v1/college-university/fsa/90-10-revenue-percentages/2017/?title_iv_percentage__gte=85
```

## Common Identifiers

### Primary Keys

| Identifier | Format | Description | Example |
|------------|--------|-------------|---------|
| `unitid` | 6-digit integer | IPEDS institution ID | 110635 |
| `year` | 4-digit integer | Academic/fiscal year | 2018 |

### Geographic Identifiers

| Identifier | Format | Description | Example |
|------------|--------|-------------|---------|
| `fips` | 1-2 digit integer | State FIPS code | 6 (California) |

### Common FIPS Codes

| FIPS | State | FIPS | State |
|------|-------|------|-------|
| 1 | Alabama | 36 | New York |
| 6 | California | 39 | Ohio |
| 12 | Florida | 44 | Rhode Island |
| 17 | Illinois | 48 | Texas |
| 25 | Massachusetts | 53 | Washington |

## Missing Data Codes

FSA data uses standard Education Data Portal missing data codes:

| Code | Meaning |
|------|---------|
| -1 | Not reported |
| -2 | Not applicable |
| -3 | Suppressed due to small cell size |
| `null` | No data available |

### Handling Missing Data

When analyzing FSA data:

```python
# Filter out missing values
df = df[df['pell_recipients'] > 0]

# Or explicitly handle codes
df = df[~df['pell_recipients'].isin([-1, -2, -3])]
```

## Variable Naming Conventions

FSA variables follow consistent naming patterns:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `*_recipients` | Count of aid recipients | `pell_recipients` |
| `*_disbursements` | Total dollars disbursed | `pell_disbursements` |
| `*_avg_amount` | Average per recipient | `pell_avg_amount` |
| `*_allocation` | Federal allocation amount | `fws_allocation` |
| `dl_*` | Direct Loan program | `dl_sub_recipients` |
| `*_ratio` | Financial ratio | `equity_ratio` |

## Data Type Considerations

### Integer Variables

- Recipient counts
- Year values
- FIPS codes
- Unit IDs

### Float Variables

- Dollar amounts (disbursements, allocations)
- Percentages
- Ratios
- Composite scores

### String Variables

- Institution names (from joined IPEDS data)
- State names (when labels applied)

## Common Calculations

### Per-Student Metrics (join with IPEDS enrollment)

```
Pell per undergraduate = pell_disbursements / undergraduate_enrollment
Loan per student = dl_total_disbursements / total_enrollment
```

### Year-over-Year Changes

```
pell_growth = (pell_recipients_2018 - pell_recipients_2017) / pell_recipients_2017
disbursement_change = pell_disbursements_2018 - pell_disbursements_2017
```

### Sector Aggregations (join with IPEDS)

```
Group by inst_control:
- Total Pell recipients by sector
- Average loan amount by institution type
- Distribution of composite scores
```

## API Query Patterns

### Basic Filters

```
# Single filter
?fips=6

# Multiple filters
?fips=6&year=2018

# Comparison operators
?composite_score__lt=1.5
?title_iv_percentage__gte=85
```

### Pagination

```
# Default page size
?page=1

# Custom page size (max 10000)
?per_page=1000&page=2
```
