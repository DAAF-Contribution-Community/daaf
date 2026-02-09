---
name: education-data-source-nacubo
description: >-
  NACUBO-Commonfund Study of Endowments (NCSE) data for college/university
  endowment market values, investment returns, asset allocations, spending
  rates, and governance practices. Use when researching higher education
  endowment performance, portfolio composition, or spending policies.
  Portal mirror contains only 7 market-value columns; full study requires
  separate NACUBO access.
metadata:
  audience: data-analysts
  domain: education-data
---

# NACUBO Data Source Reference

The NACUBO-Commonfund Study of Endowments (NCSE) is the most comprehensive annual survey of U.S. college and university endowments, covering ~650 institutions representing over $870 billion in assets. The Education Data Portal mirrors a limited subset (7 market-value columns); full investment, allocation, spending, and governance data requires direct NACUBO access.

> **CRITICAL: Value Encoding**
>
> The Education Data Portal uses **integer codes** for categorical variables and
> **null values** for missing data (NOT coded -1/-2/-3 like CCD, CRDC, etc.).
> Always verify codes against codebooks whenever possible.
>
> | Variable | Portal Format | Notes |
> |----------|---------------|-------|
> | `fips` | Integer (`6` = California) | Not string abbreviations ("CA") |
> | `year` | Integer (`2022`) | Fiscal year ending year |
> | Missing data | `null` | NOT -1, -2, -3 |
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is NACUBO?

The National Association of College and University Business Officers (NACUBO) is a nonprofit professional organization representing chief administrative and financial officers at higher education institutions.

- **Collector**: NACUBO with Commonfund Institute (currently); TIAA partnership FY2018-2022
- **Coverage**: ~650 participating colleges, universities, and affiliated foundations (voluntary)
- **Scope**: Investment returns, asset allocations, spending rates, governance practices, market values
- **Frequency**: Annual survey (September-December collection, February publication)
- **Available years**: 1974-present (50+ years); Portal mirror covers 2012-2022
- **Primary identifier**: `unitid` (IPEDS 6-digit institution ID)
- **FY2024 total**: 658 participants representing $873.7 billion in assets

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

> **Portal Coverage Note:** The Education Data Portal mirrors contain only **7 columns** focused on endowment market values (e.g., `endowment_total_end_fy`, fiscal year market values). Full investment data (returns, asset allocations, spending rates, governance) requires access to the complete NACUBO study. See "Full Report Access" section below.

### Key Metrics Available

| Metric | Description | Granularity |
|--------|-------------|-------------|
| Market Value | Total endowment assets (FMV) | Institution, size category, type |
| Investment Return | Time-weighted return, net of fees | 1, 3, 5, 10, 25-year periods |
| Effective Spending Rate | Annual withdrawal as % of market value | Institution type, size |
| Asset Allocation | Portfolio composition by asset class | Size category, type |
| New Gifts | Donations added to endowment | Aggregate by size/type |
| Budget Support | Endowment % of operating budget | Size category, type |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `unitid` | Integer (6-digit) | Institution | `166027` | IPEDS institution ID; primary join key |
| `inst_name_nacubo` | String | Institution | `Harvard University` | NACUBO version of name |
| `fips` | Integer (1-56) | State | `25` (Massachusetts) | State FIPS code |

### Endowment Size Categories

| Category Code | Range | FY24 Count | % of Participants |
|---------------|-------|------------|-------------------|
| 1 | Over $5 Billion | ~25 | ~4% |
| 2 | $1 Billion to $5 Billion | ~107 | ~16% |
| 3 | $501 Million to $1 Billion | ~77 | ~12% |
| 4 | $251 Million to $500 Million | ~97 | ~15% |
| 5 | $101 Million to $250 Million | ~161 | ~24% |
| 6 | $51 Million to $100 Million | ~111 | ~17% |
| 7 | Under $50 Million | ~80 | ~12% |

### Institution Types

| Type Code | Type Name | Description |
|-----------|-----------|-------------|
| 1 | Private | Private colleges and universities |
| 2 | Public | Public colleges and universities |
| 3 | IRF | Institutionally Related Foundations |
| 4 | Combined | Combined endowment/foundation |

### Typical Return Ranges (Historical)

| Period | Average Range | Notes |
|--------|---------------|-------|
| 1-year | -8% to +31% | High volatility |
| 3-year | 3% to 15% | Less volatile |
| 5-year | 5% to 12% | More stable |
| 10-year | 6% to 9% | Most commonly cited |
| 25-year | 6% to 9% | Long-term benchmark |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `null` | Not reported / missing | Standard for all NACUBO variables |

> **Note:** Unlike other Education Data Portal sources (CCD, CRDC, etc.), NACUBO data uses **null values** for missing data rather than coded values like -1, -2, -3. NACUBO is a voluntary survey with simpler missing data patterns; the Portal preserves null rather than applying coded values.

```python
# Correct: Check for null
df.filter(pl.col("endow_per_fte").is_null())

# Incorrect: Checking for -1/-2/-3 (these don't exist in NACUBO)
# df.filter(pl.col("endow_per_fte") == -1)  # Won't find anything
```

## Data Access

### Dataset Paths

| Topic | Type | Huggingface Path |
|-------|------|------------------|
| Endowments | Single | `college-university/nacubo/endowments/colleges_nacubo_endow` |

> **Urban CSV mirror path:** `nacubo/colleges_nacubo_endow`

### Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| Endowments | `college-university/nacubo/endowments/codebook_colleges_nacubo_endowments` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for the
> full catalog and `fetch-patterns.md` for `get_codebook_url()`. For human
> reference -- not parsed programmatically.

### Example Fetch

```python
import polars as pl

url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/nacubo/endowments/colleges_nacubo_endow.parquet"
df = pl.read_parquet(url)

# Filter locally
df = df.filter(
    (pl.col("fips") == 6) &  # California
    (pl.col("year") == 2022)
)
```

### Filtering

```python
# Filter by state
df_ca = df.filter(pl.col("fips") == 6)  # California

# Filter by year range
df_recent = df.filter(pl.col("year").is_between(2018, 2022))

# Drop nulls in key column
df_valid = df.filter(pl.col("endowment_total_end_fy").is_not_null())
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

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Using NCES-style codes | Portal uses integer FIPS, not string state abbreviations | Use integer fips codes (1-56) |
| Expecting coded missing values | NACUBO in Portal uses nulls, not -1/-2/-3 | Check for null, not negative codes |
| Comparing to IPEDS values | NACUBO is voluntary (~650), IPEDS is mandatory (~6,000+) | Note sample differences in analysis |
| Year interpretation | FY2024 = July 2023 - June 2024 | Align fiscal year definitions carefully |
| Assuming comprehensive coverage | Only ~650 of ~4,000+ institutions participate | Use IPEDS for population-level analysis |
| Ignoring partner changes | TIAA (2018-22) vs Commonfund (other years) may change methodology | Check methodology for specific years |

## Key Caveats

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Voluntary participation | ~650 of ~4,000+ institutions | Use IPEDS for comprehensive coverage |
| Self-reported data | Unverified accuracy | Cross-reference with IPEDS where possible |
| Selection bias | Larger, well-resourced institutions overrepresented | Analyze by size category |
| Partner changes | TIAA (2018-22), Commonfund (other years) | Check methodology changes |
| Fiscal year timing | July 1 - June 30 | Match to other data sources carefully |
| Portal subset | Only 7 columns mirrored | Full study required for returns, allocations, governance |

## Common Use Cases

| Research Question | Primary Variables | Reference File |
|-------------------|-------------------|----------------|
| How do endowment returns vary by size? | Return rates, size category | `endowment-metrics.md` |
| What drives endowment spending decisions? | Spending rate, spending policy | `endowment-metrics.md` |
| How are endowments invested? | Asset allocation percentages | `asset-allocation.md` |
| Which schools have the largest endowments? | Market value, institution name | Public tables |
| How has endowment performance changed? | Historical return series | `endowment-metrics.md` |
| What portion of budgets come from endowments? | Budget support percentage | `endowment-metrics.md` |

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ipeds` | Complementary; mandatory reporting covers all institutions | Need all institutions or just market values |
| `education-data-source-scorecard` | Complementary; student outcomes | Linking endowment size to student outcomes |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |

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
