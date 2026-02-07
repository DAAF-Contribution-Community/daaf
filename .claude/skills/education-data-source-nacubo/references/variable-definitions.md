# Variable Definitions

Reference for NACUBO endowment study variables, size categories, institution types, and data classifications.

## Primary Identifiers

### Institution Identifier

| Variable | Format | Description |
|----------|--------|-------------|
| `unitid` | 6-digit integer | IPEDS institution identifier |
| Institution Name | String | Official institution name |
| State | 2-letter code | State location |

**Joining with Other Data**: Use `unitid` to link NACUBO data with IPEDS, College Scorecard, and other Education Data Portal sources.

## Endowment Size Categories

### Standard Size Cohorts

NACUBO segments institutions into seven size categories based on fiscal year-end market value:

| Category Code | Size Range | Description |
|---------------|------------|-------------|
| 1 | Over $5 Billion | Mega-endowments |
| 2 | $1 Billion to $5 Billion | Large endowments |
| 3 | $501 Million to $1 Billion | Upper-mid endowments |
| 4 | $251 Million to $500 Million | Mid-size endowments |
| 5 | $101 Million to $250 Million | Lower-mid endowments |
| 6 | $51 Million to $100 Million | Small endowments |
| 7 | Under $50 Million | Very small endowments |

**Note**: Some historical data uses slightly different breakpoints. Always verify category definitions for specific study years.

### Alternative Size Groupings

Simplified three-category grouping sometimes used:

| Group | Size Range | Typical Count |
|-------|------------|---------------|
| Large | Over $1 Billion | ~130-140 |
| Medium | $101 Million to $1 Billion | ~350 |
| Small | Under $100 Million | ~180-200 |

### Distribution by Size (FY24)

| Size Category | Count | % of Participants | % of Total Assets |
|---------------|-------|-------------------|-------------------|
| Over $5B | ~25 | ~4% | ~35% |
| $1B to $5B | ~107 | ~16% | ~49% |
| $501M to $1B | ~77 | ~12% | ~7% |
| $251M to $500M | ~97 | ~15% | ~4% |
| $101M to $250M | ~161 | ~24% | ~3% |
| $51M to $100M | ~111 | ~17% | ~1% |
| Under $50M | ~80 | ~12% | <1% |

**Key Insight**: ~20% of participants (>$1B) control ~84% of total endowment assets.

## Institution Types

### Primary Type Classification

| Type Code | Type Name | Description |
|-----------|-----------|-------------|
| 1 | Private | Private colleges and universities |
| 2 | Public | Public colleges and universities |
| 3 | IRF | Institutionally Related Foundations |
| 4 | Combined | Combined endowment/foundation |

### Type Definitions

**Private**: Independent colleges and universities with institutional endowment funds.

**Public**: State colleges and universities with institutional endowment funds directly managed by the institution.

**Institutionally Related Foundation (IRF)**: Separate 501(c)(3) organization that holds and manages endowment assets on behalf of a (typically public) institution. Common structure for public universities.

**Combined**: Institutions reporting combined endowment and foundation data together (may include both institutional funds and IRF).

### Type Distribution (FY24)

| Type | Count | % of Participants |
|------|-------|-------------------|
| Private | ~400 | ~60% |
| Public | ~100 | ~15% |
| IRF | ~130 | ~20% |
| Combined | ~30 | ~5% |

## Financial Variables

### Market Value Variables

| Variable | Description | Unit |
|----------|-------------|------|
| `market_value` | Total endowment market value at fiscal year end | USD |
| `market_value_prior` | Market value at prior fiscal year end | USD |
| `market_value_change` | Absolute change in market value | USD |
| `market_value_change_pct` | Percentage change in market value | % |
| `market_value_per_fte` | Market value per FTE student | USD |

### Investment Return Variables

| Variable | Description | Unit |
|----------|-------------|------|
| `return_1yr` | One-year investment return (net of fees) | % |
| `return_3yr` | Three-year annualized return | % |
| `return_5yr` | Five-year annualized return | % |
| `return_10yr` | Ten-year annualized return | % |
| `return_25yr` | Twenty-five-year annualized return | % |

### Spending Variables

| Variable | Description | Unit |
|----------|-------------|------|
| `effective_spending_rate` | Actual spending as % of market value | % |
| `target_spending_rate` | Policy target spending rate | % |
| `total_spending` | Total endowment distributions | USD |
| `spending_financial_aid` | Spending on student financial aid | USD or % |
| `spending_academic` | Spending on academic programs | USD or % |
| `spending_faculty` | Spending on endowed positions | USD or % |
| `spending_operations` | Spending on operations/maintenance | USD or % |
| `spending_other` | Other spending | USD or % |

### Budget Variables

| Variable | Description | Unit |
|----------|-------------|------|
| `budget_support_pct` | Endowment as % of operating budget | % |
| `operating_budget` | Total institutional operating budget | USD |

### Gift Variables

| Variable | Description | Unit |
|----------|-------------|------|
| `new_gifts` | New contributions to endowment | USD |
| `gifts_restricted` | Donor-restricted new gifts | USD |
| `gifts_unrestricted` | Unrestricted new gifts | USD |

## Asset Allocation Variables

### Major Asset Classes

| Variable | Description | Typical Range |
|----------|-------------|---------------|
| `alloc_us_equity` | U.S. public equities | 10-25% |
| `alloc_non_us_equity` | Non-U.S. developed market equities | 5-15% |
| `alloc_emerging_equity` | Emerging market equities | 3-10% |
| `alloc_global_equity` | Global equity strategies | 0-10% |
| `alloc_fixed_income` | Bonds and fixed income | 8-15% |

### Alternative Investment Classes

| Variable | Description | Typical Range |
|----------|-------------|---------------|
| `alloc_private_equity` | Private equity (buyout, growth) | 10-25% |
| `alloc_venture_capital` | Venture capital | 5-15% |
| `alloc_marketable_alts` | Hedge funds, liquid alternatives | 10-20% |
| `alloc_real_assets` | Real estate, natural resources | 8-15% |
| `alloc_private_credit` | Private debt strategies | 0-5% |

### Aggregated Categories

| Variable | Components | Typical Range |
|----------|------------|---------------|
| `alloc_public_equity` | US + Non-US + EM + Global | 25-45% |
| `alloc_alternatives` | PE + VC + Alts + Real + Credit | 40-60% |
| `alloc_traditional` | Public equity + Fixed income | 35-55% |

## Governance Variables

### Investment Committee

| Variable | Description |
|----------|-------------|
| `committee_size` | Number of investment committee members |
| `committee_meetings` | Annual meeting frequency |
| `has_student_managed` | Whether students manage portion of endowment |
| `student_managed_value` | Market value of student-managed funds |

### Management Structure

| Variable | Description |
|----------|-------------|
| `num_external_managers` | Number of external investment managers |
| `has_ocio` | Uses outsourced CIO |
| `internal_management_pct` | Percentage managed internally |

### Policy Variables

| Variable | Description |
|----------|-------------|
| `spending_policy_type` | Type of spending policy (moving avg, etc.) |
| `smoothing_period` | Years/quarters in smoothing formula |
| `rebalancing_frequency` | How often portfolio rebalanced |

## ESG/Responsible Investing Variables

| Variable | Description |
|----------|-------------|
| `has_esg_policy` | Implements ESG considerations |
| `has_negative_screening` | Uses negative/exclusionary screening |
| `has_impact_investing` | Allocates to impact investments |
| `esg_policy_type` | Type of ESG integration |

## Time Variables

| Variable | Description | Format |
|----------|-------------|--------|
| `fiscal_year` | Fiscal year of data | YYYY (ending year) |
| `fye_date` | Fiscal year end date | June 30 |
| `survey_year` | Year survey was conducted | YYYY |

**Note**: FY2024 data refers to July 1, 2023 - June 30, 2024.

## Missing Data Codes

| Code | Meaning |
|------|---------|
| Blank/Null | Not reported |
| -1 | Not applicable |
| -2 | Data suppressed |
| -3 | Not collected |

## Data Types

| Variable Type | Examples | Notes |
|---------------|----------|-------|
| Currency | Market value, spending | Reported in USD, often in thousands |
| Percentage | Returns, allocations, rates | Usually 0-100 scale |
| Count | Committee size, managers | Integer |
| Category | Size category, type | Coded values |
| Boolean | Has OCIO, Has ESG policy | Yes/No or 1/0 |

## Derived Variables

Common calculations:

```
market_value_change_pct = (market_value - market_value_prior) / market_value_prior * 100

effective_spending_rate = total_spending / market_value_prior * 100

budget_support_pct = total_spending / operating_budget * 100

market_value_per_fte = market_value / fte_enrollment
```

## Historical Variable Changes

Some variables have changed over study history:

| Period | Change |
|--------|--------|
| Pre-2018 | Fewer alternative investment categories |
| 2018-2022 | TIAA added governance questions |
| 2023+ | Commonfund expanded ESG questions |

Always check documentation for specific years when analyzing historical trends.
