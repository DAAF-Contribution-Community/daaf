# Industry Flows

What industries graduates enter: employment by NAICS sector.

> **Portal Integer Encoding:** The `industry` column contains 2-digit NAICS integers (11-92, 99). Null values indicate no industry data for that row.

## Contents

- [Overview](#overview)
- [NAICS Sector Codes](#naics-sector-codes)
- [Industry Flow Variables](#industry-flow-variables)
- [Analysis Patterns](#analysis-patterns)
- [Matching Programs to Industries](#matching-programs-to-industries)
- [Limitations](#limitations)

## Overview

The Employment Flows tabulations include industry data showing which sectors employ graduates:

- **NAICS Sector**: 2-digit North American Industry Classification System
- **20 sectors** covering all economic activity
- Available at 1, 5, and 10 years post-graduation

Industry flows help answer:
- What industries employ graduates from a specific program?
- Are graduates working in fields related to their training?
- How do career patterns differ by major?

## NAICS Sector Codes (Portal Integer Encoding)

| Code | Sector |
|------|--------|
| `11` | Agriculture, Forestry, Fishing and Hunting |
| `21` | Mining, Quarrying, and Oil and Gas Extraction |
| `22` | Utilities |
| `23` | Construction |
| `31`-`33` | Manufacturing |
| `42` | Wholesale Trade |
| `44`-`45` | Retail Trade |
| `48`-`49` | Transportation and Warehousing |
| `51` | Information |
| `52` | Finance and Insurance |
| `53` | Real Estate and Rental and Leasing |
| `54` | Professional, Scientific, and Technical Services |
| `55` | Management of Companies and Enterprises |
| `56` | Administrative and Support and Waste Management |
| `61` | Educational Services |
| `62` | Health Care and Social Assistance |
| `71` | Arts, Entertainment, and Recreation |
| `72` | Accommodation and Food Services |
| `81` | Other Services (except Public Administration) |
| `92` | Public Administration |
| `99` | Unclassified/Federal (PSEO-specific) |

> **Data Note:** In Portal parquet files, the `industry` column is `Int64` with `null` values (not -1) for rows without industry data.

### Key Sectors by Common Graduate Fields

| Graduate Field | Primary Industries |
|----------------|-------------------|
| Engineering | 31-33 (Manufacturing), 54 (Prof Services), 23 (Construction) |
| Computer Science | 51 (Information), 54 (Prof Services), 52 (Finance) |
| Business | 52 (Finance), 54 (Prof Services), 44-45 (Retail) |
| Education | 61 (Educational Services), 92 (Public Admin) |
| Health/Nursing | 62 (Health Care) |
| Biology/Chemistry | 54 (Prof Services), 62 (Health Care), 31-33 (Manufacturing) |
| Arts/Humanities | 51 (Information), 61 (Education), 71 (Arts/Entertainment) |

## Industry Flow Variables

### Employment by Industry

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP` | Employed graduates (when filtered by NAICS) |
| `Y5_GRADS_EMP` | Employed graduates, 5 years out |
| `Y10_GRADS_EMP` | Employed graduates, 10 years out |

### Querying by Industry

Use the `NAICS` parameter in the Flows endpoint:

```
# Employment in Information sector (51), 1 year post-graduation
GET api.census.gov/data/timeseries/pseo/flows
  ?get=Y1_GRADS_EMP
  &for=us:1
  &NAICS=54
  &INSTITUTION=00365800
  &DEGREE_LEVEL=05
  &CIPCODE=11
```

### Multiple Industries

Query multiple NAICS codes:
```
&NAICS=51&NAICS=54&NAICS=52
```

Or add NAICS to get statement for all industries:
```
?get=Y1_GRADS_EMP,NAICS
```

## Analysis Patterns

### Industry Distribution for a Program

Show where graduates from a specific program work:

```
Computer Science (CIP=11) Bachelor's from UT Austin, Y1 Employment:

┌─────────────────────────────────────────────┬──────────┬─────────┐
│ Industry (NAICS)                            │ Employed │ Share   │
├─────────────────────────────────────────────┼──────────┼─────────┤
│ 54 - Professional, Scientific, Technical   │ 280      │ 35%     │
│ 51 - Information                            │ 200      │ 25%     │
│ 52 - Finance and Insurance                  │ 120      │ 15%     │
│ 31-33 - Manufacturing                       │ 80       │ 10%     │
│ 61 - Educational Services                   │ 40       │ 5%      │
│ Other sectors                               │ 80       │ 10%     │
├─────────────────────────────────────────────┼──────────┼─────────┤
│ Total Employed                              │ 800      │ 100%    │
└─────────────────────────────────────────────┴──────────┴─────────┘
```

### Career Trajectory Analysis

Compare Y1 vs Y5 vs Y10 industry distribution:

```python
# Pseudo-code: How industry distribution changes over time
for year in [1, 5, 10]:
    industry_dist = get_employment_by_naics(institution, cip, year)
    print(f"Year {year}: {industry_dist}")
```

**Example finding**: Engineering graduates may start in manufacturing (31-33) but shift toward management (55) or professional services (54) by Year 10.

### Cross-Program Comparison

Compare industry destinations for different programs at same institution:

| Program (CIP) | Top Industry | % in Top Industry |
|---------------|--------------|-------------------|
| Computer Science (11) | 54 (Prof Services) | 35% |
| Nursing (51.38) | 62 (Health Care) | 92% |
| Business (52) | 52 (Finance) | 28% |
| Education (13) | 61 (Educational Services) | 75% |

## Matching Programs to Industries

### Expected vs. Actual Industry Match

Some programs have clear industry matches; others are more diffuse:

| Match Type | Example Programs | Characteristics |
|------------|------------------|-----------------|
| **Tight match** | Nursing, Education | 70%+ in single industry |
| **Moderate match** | Engineering, Accounting | 40-70% in 2-3 industries |
| **Diffuse** | Business, Communications | Spread across many industries |

### Field-Specific Expectations

**Health Sciences (CIP 51)**
- Expected: 62 (Health Care and Social Assistance)
- Typical match rate: 80-95%

**Engineering (CIP 14)**
- Expected: 31-33 (Manufacturing), 54 (Prof Services), 23 (Construction)
- Typical combined rate: 60-80%

**Business/Management (CIP 52)**
- Expected: 52 (Finance), 54 (Prof Services), 55 (Management)
- Distribution typically more varied

**Computer Science (CIP 11)**
- Expected: 51 (Information), 54 (Prof Services)
- Tech workers also common in 52 (Finance), 31-33 (Manufacturing)

## Limitations

### Granularity Constraints

| Limitation | Impact |
|------------|--------|
| 2-digit NAICS only | Cannot distinguish sub-industries |
| No occupation data | NAICS ≠ job function |
| Sector boundaries | Some industries span multiple codes |

### Interpretation Challenges

| Issue | Consideration |
|-------|---------------|
| Headquarters vs. work site | Large companies classified by HQ industry |
| Multi-industry firms | Conglomerates may be classified inconsistently |
| Federal employment | May appear in NAICS 99 (unclassified) |
| Contractor classification | IT workers at banks → Finance (52) not Information (51) |

### Missing Data

Industry data suppressed when:
- Fewer than 30 graduates in industry-program cell
- Program or institution has insufficient coverage

### Example: Complete Industry Profile

For Business Administration Bachelor's graduates (hypothetical):

```
Institution: State University
CIP: 52 (Business, Management, Marketing)
Degree Level: 05 (Bachelor's)
Cohort: 2016

Industry Distribution Evolution:

Year 1:
┌─────────────────────────────────────┬────────┐
│ Industry                            │ Share  │
├─────────────────────────────────────┼────────┤
│ 52 - Finance and Insurance          │ 22%    │
│ 54 - Professional, Scientific       │ 18%    │
│ 44-45 - Retail Trade                │ 15%    │
│ 56 - Administrative Support         │ 12%    │
│ 72 - Accommodation and Food         │ 10%    │
│ Other                               │ 23%    │
└─────────────────────────────────────┴────────┘

Year 5:
┌─────────────────────────────────────┬────────┐
│ Industry                            │ Share  │
├─────────────────────────────────────┼────────┤
│ 52 - Finance and Insurance          │ 28%    │
│ 54 - Professional, Scientific       │ 22%    │
│ 55 - Management of Companies        │ 10%    │
│ 44-45 - Retail Trade                │ 8%     │
│ 56 - Administrative Support         │ 8%     │
│ Other                               │ 24%    │
└─────────────────────────────────────┴────────┘

Insight: Graduates shift from retail/food service toward 
finance, professional services, and management over time.
```

## Industry Code Reference

For complete NAICS definitions, see:
- [NAICS Code Labels (CSV)](https://lehd.ces.census.gov/data/schema/latest/label_industry.csv)
- [Census Bureau NAICS Reference](https://www.census.gov/naics/)
