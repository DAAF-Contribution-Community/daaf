# SAIPE Variable Definitions

Detailed definitions of SAIPE variables, population universes, and coding conventions.

## School District Variables

### Core Estimates

| Variable | Definition | Universe |
|----------|------------|----------|
| `population_total` | Total population residing within school district boundaries | All persons in households and group quarters |
| `population_5_17` | Population ages 5-17 residing within district | All children 5-17, regardless of enrollment status |
| `population_5_17_poverty` | Related children ages 5-17 in families in poverty | Related children in families with income below poverty threshold |

### Derived Measures

| Variable | Calculation | Notes |
|----------|-------------|-------|
| `population_5_17_poverty_pct` | `population_5_17_poverty / population_5_17 * 100` | Not a true poverty "rate" - numerator excludes some in denominator |

## State and County Variables

### Income Estimates

| Variable | Definition | Unit |
|----------|------------|------|
| `median_household_income` | Median income of all households | Dollars |
| `median_household_income_moe` | 90% margin of error for median income | Dollars |

### Poverty Estimates (Counts)

| Variable | Definition | Ages |
|----------|------------|------|
| `population_0_4_poverty` | Children under age 5 in poverty | 0-4 (states only) |
| `population_5_17_poverty` | Related children 5-17 in families in poverty | 5-17 |
| `population_0_17_poverty` | All children under 18 in poverty | 0-17 |
| `population_poverty` | All persons in poverty | All ages |

### Poverty Estimates (Rates/Percentages)

| Variable | Definition |
|----------|------------|
| `population_0_4_poverty_pct` | Percent of children 0-4 in poverty |
| `population_5_17_poverty_pct` | Percent of children 5-17 in poverty |
| `population_0_17_poverty_pct` | Percent of children 0-17 in poverty |
| `population_poverty_pct` | Percent of all persons in poverty |

### Confidence Intervals (States and Counties)

| Variable | Definition |
|----------|------------|
| `*_lb` | Lower bound of 90% confidence interval |
| `*_ub` | Upper bound of 90% confidence interval |

Example: `population_5_17_poverty_lb`, `population_5_17_poverty_ub`

## Population Universes

### Understanding "Related Children"

**Related children ages 5-17 in families** includes:
- Persons ages 5 through 17
- Related to the householder by birth, marriage, or adoption
- Living in family households

**Excludes**:
- Foster children
- Other unrelated individuals in household
- Children in group quarters (institutions, college dorms, military barracks)
- Children who are householders or spouses of householders

### "In Families" vs "In Households"

| Term | Definition |
|------|------------|
| **Family** | Householder plus one or more related persons |
| **Household** | All persons in a housing unit (may include unrelated) |
| **In families** | Only persons in family households, related to householder |

SAIPE school district estimates use "related children in families" - a more restrictive universe than "all children in households."

### Poverty Universe

The poverty universe excludes:
- Persons in military barracks
- Persons in institutional group quarters
- Unrelated individuals under age 15
- Foster children

This means the denominator for poverty rates differs from total population.

## Poverty Threshold Definition

### Official Census Bureau Poverty Thresholds

Poverty status determined by comparing family income to threshold based on:
- Number of family members
- Number of related children under 18
- Age of householder (under 65 or 65+)

### 2023 Poverty Thresholds (Selected)

| Family Size | Children Under 18 | Threshold |
|-------------|-------------------|-----------|
| 2 persons | None | $19,515 |
| 2 persons | 1 child | $20,088 |
| 3 persons | 1 child | $24,580 |
| 3 persons | 2 children | $24,677 |
| 4 persons | 2 children | $30,900 |
| 5 persons | 3 children | $36,591 |

### What Counts as Income

**Included** in poverty determination:
- Wages and salaries
- Self-employment income
- Interest, dividends, rental income
- Social Security and retirement income
- Cash public assistance (TANF, SSI)
- Unemployment compensation
- Child support received

**Excluded** from poverty determination:
- SNAP (food stamps)
- Medicaid/Medicare
- Housing subsidies
- School lunch programs
- Non-cash benefits

### How Poverty Differs from FRPL Eligibility

| Aspect | Official Poverty | Free Lunch | Reduced Lunch |
|--------|------------------|------------|---------------|
| Income threshold | 100% of threshold | 130% of guidelines | 185% of guidelines |
| Threshold source | Census Bureau | HHS Guidelines | HHS Guidelines |
| 2024 example (family of 4) | ~$31,000 | ~$40,560 | ~$57,720 |
| Non-cash benefits | Not counted | Not counted | Not counted |

## Geographic Identifiers

### State FIPS Codes

| Code | State | Code | State |
|------|-------|------|-------|
| 01 | Alabama | 27 | Minnesota |
| 02 | Alaska | 28 | Mississippi |
| 04 | Arizona | 29 | Missouri |
| 05 | Arkansas | 30 | Montana |
| 06 | California | 31 | Nebraska |
| 08 | Colorado | 32 | Nevada |
| 09 | Connecticut | 33 | New Hampshire |
| 10 | Delaware | 34 | New Jersey |
| 11 | District of Columbia | 35 | New Mexico |
| 12 | Florida | 36 | New York |
| 13 | Georgia | 37 | North Carolina |
| 15 | Hawaii | 38 | North Dakota |
| 16 | Idaho | 39 | Ohio |
| 17 | Illinois | 40 | Oklahoma |
| 18 | Indiana | 41 | Oregon |
| 19 | Iowa | 42 | Pennsylvania |
| 20 | Kansas | 44 | Rhode Island |
| 21 | Kentucky | 45 | South Carolina |
| 22 | Louisiana | 46 | South Dakota |
| 23 | Maine | 47 | Tennessee |
| 24 | Maryland | 48 | Texas |
| 25 | Massachusetts | 49 | Utah |
| 26 | Michigan | 50 | Vermont |
| | | 51 | Virginia |
| | | 53 | Washington |
| | | 54 | West Virginia |
| | | 55 | Wisconsin |
| | | 56 | Wyoming |

### School District ID (LEAID)

- 7-character string
- First 2 characters = state FIPS code
- Remaining 5 = unique district within state
- Example: `0622710` = California district 22710

### County FIPS Codes

- 5-character string
- First 2 = state FIPS
- Last 3 = county within state
- Example: `06037` = Los Angeles County, CA

## Missing Data Codes

### Education Data Portal Conventions

| Code | Meaning |
|------|---------|
| `-1` | Missing/not available |
| `-2` | Not applicable |
| `-3` | Suppressed for confidentiality |
| `null` | No data |

### Suppression Rules

SAIPE applies disclosure avoidance:
- Estimates may be suppressed if based on very small populations
- Complementary suppression to prevent inference
- School district pieces with zero population not published

## Age Assignment for Grade Relevance

For school district estimation, children are assigned grades based on age:

| Age | Assigned Grade |
|-----|----------------|
| 5 | Kindergarten |
| 6 | Grade 1 |
| 7 | Grade 2 |
| 8 | Grade 3 |
| 9 | Grade 4 |
| 10 | Grade 5 |
| 11 | Grade 6 |
| 12 | Grade 7 |
| 13 | Grade 8 |
| 14 | Grade 9 |
| 15 | Grade 10 |
| 16 | Grade 11 |
| 17 | Grade 12 |

This one-to-one mapping is used for allocating children to overlapping elementary/secondary districts.

## Time Reference

### Estimate Year vs Data Year

| Term | Meaning |
|------|---------|
| **Estimate year** | Calendar year the estimate represents (e.g., 2023) |
| **Release year** | Year estimates are published (typically estimate year + 1) |
| **Tax year** | IRS data year (typically estimate year - 1) |
| **ACS year** | ACS data year (same as estimate year) |

Example for 2023 SAIPE (released December 2024):
- Estimate year: 2023
- ACS data: 2023 ACS
- IRS tax data: Tax year 2022 (filed in 2023)
- SNAP data: 2023

### School Year vs Calendar Year

SAIPE estimates are for **calendar year** income, not school year:
- 2023 SAIPE = calendar year 2023 income
- School district boundaries from School Year 2022-2023

## Education Data Portal Variable Names

When accessing SAIPE via the Urban Institute API, variable names may differ slightly:

| Census Variable | Education Data Portal |
|-----------------|----------------------|
| Total population | `population_total` |
| Population 5-17 | `population_5_17` |
| Children 5-17 in poverty | `population_5_17_poverty` |
| Percent 5-17 in poverty | `population_5_17_poverty_pct` |
| Median household income | `median_household_income` |

Check the Education Data Portal documentation for current variable names.
