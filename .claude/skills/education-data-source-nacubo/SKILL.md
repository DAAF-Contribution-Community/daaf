---
name: education-data-source-nacubo
description: NACUBO endowment study data source for college/university endowments. Use when researching higher education endowment market values, investment returns, asset allocations, spending rates, or governance practices from the NACUBO-Commonfund Study of Endowments.
metadata:
  audience: data-analysts
  domain: education-data
---

# NACUBO Endowment Data Source

Reference for understanding college and university endowment data from the NACUBO-Commonfund Study of Endowments (NCSE), available through the Urban Institute Education Data Portal.

## What is NACUBO?

The National Association of College and University Business Officers (NACUBO) is a nonprofit professional organization representing chief administrative and financial officers at higher education institutions. Since 1974, NACUBO has conducted the most comprehensive annual study of U.S. college and university endowments.

Key characteristics:

- **Voluntary survey** of ~1,500 colleges, universities, and affiliated foundations
- **658 participants** in FY2024 (most recent), representing $873.7 billion in assets
- **Annual data collection** September-December, results published February
- **Coverage**: Investment returns, asset allocations, spending rates, governance
- **50+ years** of historical data (study founded 1974)

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `endowment-study.md` | NCSE methodology, participation, history | Understanding data source context |
| `endowment-metrics.md` | Market values, returns, spending rates | Interpreting performance data |
| `variable-definitions.md` | Key variables, size categories, institution types | Building queries, filtering data |
| `data-quality.md` | Coverage limitations, data caveats | Assessing data reliability |
| `asset-allocation.md` | Investment categories, alternative strategies | Analyzing portfolio composition |

## Decision Trees

### What endowment data do I need?

```
Endowment research topic?
├─ Market values / fund size
│   ├─ Individual institution values → NCSE public tables
│   ├─ Size distribution → ./references/variable-definitions.md
│   └─ Historical trends → ./references/endowment-metrics.md
├─ Investment returns
│   ├─ One-year returns → ./references/endowment-metrics.md
│   ├─ Multi-year returns (3/5/10/25-year) → ./references/endowment-metrics.md
│   └─ Returns by size/type → ./references/variable-definitions.md
├─ Asset allocation
│   ├─ Traditional vs alternative → ./references/asset-allocation.md
│   ├─ Private equity/VC allocation → ./references/asset-allocation.md
│   └─ ESG/responsible investing → ./references/asset-allocation.md
├─ Spending and distributions
│   ├─ Spending rates → ./references/endowment-metrics.md
│   ├─ Spending purposes (aid, faculty, etc.) → ./references/endowment-metrics.md
│   └─ Budget contribution → ./references/endowment-metrics.md
└─ Data quality concerns
    ├─ Coverage/participation → ./references/data-quality.md
    ├─ Self-reported data issues → ./references/data-quality.md
    └─ Comparability across years → ./references/data-quality.md
```

### Which data source should I use?

```
Comparing NACUBO vs IPEDS for endowment data?
├─ Need ALL institutions → Use IPEDS (mandatory reporting)
├─ Need investment returns → Use NACUBO (IPEDS doesn't have)
├─ Need asset allocations → Use NACUBO (IPEDS doesn't have)
├─ Need spending rates → Use NACUBO (IPEDS doesn't have)
├─ Need just market values → Either works
│   ├─ More institutions → IPEDS
│   └─ More detail → NACUBO
└─ Need governance/policies → Use NACUBO (IPEDS doesn't have)
```

### Understanding study name changes

```
Which study by year?
├─ FY2023-present → NACUBO-Commonfund Study of Endowments (NCSE)
├─ FY2018-FY2022 → NACUBO-TIAA Study of Endowments (NTSE)
├─ FY2009-FY2017 → NACUBO-Commonfund Study of Endowments (NCSE)
└─ Before FY2009 → NACUBO Endowment Study (NES)
```

## Quick Reference: NACUBO Data

### Key Metrics Available

| Metric | Description | Granularity |
|--------|-------------|-------------|
| Market Value | Total endowment assets (FMV) | Institution, size category, type |
| Investment Return | Time-weighted return, net of fees | 1, 3, 5, 10, 25-year periods |
| Effective Spending Rate | Annual withdrawal as % of market value | Institution type, size |
| Asset Allocation | Portfolio composition by asset class | Size category, type |
| New Gifts | Donations added to endowment | Aggregate by size/type |
| Budget Support | Endowment % of operating budget | Size category, type |

### Endowment Size Categories

| Category | Range | FY24 Count | % of Participants |
|----------|-------|------------|-------------------|
| Over $5 Billion | >$5B | ~25 | ~4% |
| $1 Billion to $5 Billion | $1B-$5B | ~107 | ~16% |
| $501 Million to $1 Billion | $501M-$1B | ~77 | ~12% |
| $251 Million to $500 Million | $251M-$500M | ~97 | ~15% |
| $101 Million to $250 Million | $101M-$250M | ~161 | ~24% |
| $51 Million to $100 Million | $51M-$100M | ~111 | ~17% |
| Under $50 Million | <$50M | ~80 | ~12% |

### Institution Types

| Type | Description |
|------|-------------|
| Private | Private colleges and universities |
| Public | Public colleges and universities |
| IRF | Institutionally Related Foundations |
| Combined | Combined endowment/foundation |

### Typical Return Ranges (Historical)

| Period | Average Range | Notes |
|--------|---------------|-------|
| 1-year | -8% to +31% | High volatility |
| 3-year | 3% to 15% | Less volatile |
| 5-year | 5% to 12% | More stable |
| 10-year | 6% to 9% | Most commonly cited |
| 25-year | 6% to 9% | Long-term benchmark |

## Data Access

### Urban Institute Education Data Portal

NACUBO data available through the Education Data Portal at college-university level:

```
Base URL: https://educationdata.urban.org/api/v1/college-university/
```

**Note**: The Education Data Portal integrates select NACUBO variables with IPEDS data. For comprehensive NCSE data (asset allocations, detailed returns, governance), access the full NACUBO report.

### Public NACUBO Tables

Free tables available at: https://www.nacubo.org/Research/2024/Public-NCSE-Tables

Includes:
- Participating institutions by market value
- Average/median returns by size and type
- Asset allocation summaries
- Spending rate summaries

### Full Report Access

- **Participants**: Free access
- **NACUBO Members**: $250
- **Non-members**: $1,500
- **Academic researchers**: Contact Commonfund Institute

## Key Caveats

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Voluntary participation | ~650 of ~4,000+ institutions | Use IPEDS for comprehensive coverage |
| Self-reported data | Unverified accuracy | Cross-reference with IPEDS where possible |
| Selection bias | Larger, well-resourced institutions overrepresented | Analyze by size category |
| Partner changes | TIAA (2018-22), Commonfund (other years) | Check methodology changes |
| Fiscal year timing | July 1 - June 30 | Match to other data sources carefully |

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Using NCES-style codes | Portal uses integer FIPS, not string state abbreviations | Use integer fips codes (1-56) |
| Expecting coded missing values | NACUBO in Portal uses nulls, not -1/-2/-3 | Check for null, not negative codes |
| Comparing to IPEDS values | NACUBO is voluntary, IPEDS is mandatory | Note sample differences in analysis |
| Year interpretation | FY2024 = July 2023 - June 2024 | Align fiscal year definitions carefully |

## Common Use Cases

| Research Question | Primary Variables | Reference File |
|-------------------|-------------------|----------------|
| How do endowment returns vary by size? | Return rates, size category | `endowment-metrics.md` |
| What drives endowment spending decisions? | Spending rate, spending policy | `endowment-metrics.md` |
| How are endowments invested? | Asset allocation percentages | `asset-allocation.md` |
| Which schools have the largest endowments? | Market value, institution name | Public tables |
| How has endowment performance changed? | Historical return series | `endowment-metrics.md` |
| What portion of budgets come from endowments? | Budget support percentage | `endowment-metrics.md` |

## Related Skills and Data Sources

| Resource | Relationship | When to Use |
|----------|--------------|-------------|
| `education-data-explorer` | Parent skill for all education data | General exploration |
| IPEDS Finance | Complementary source | Need all institutions |
| College Scorecard | Complementary source | Student outcomes |
| IPEDS Directory | Join key (`unitid`) | Institution characteristics |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Study methodology | `./references/endowment-study.md` |
| Partnership history | `./references/endowment-study.md` |
| Participation criteria | `./references/endowment-study.md` |
| Investment returns | `./references/endowment-metrics.md` |
| Spending rates | `./references/endowment-metrics.md` |
| Market values | `./references/endowment-metrics.md` |
| Size categories | `./references/variable-definitions.md` |
| Institution types | `./references/variable-definitions.md` |
| Variable list | `./references/variable-definitions.md` |
| Asset classes | `./references/asset-allocation.md` |
| Alternative investments | `./references/asset-allocation.md` |
| ESG investing | `./references/asset-allocation.md` |
| Selection bias | `./references/data-quality.md` |
| Coverage gaps | `./references/data-quality.md` |
| Comparability issues | `./references/data-quality.md` |
