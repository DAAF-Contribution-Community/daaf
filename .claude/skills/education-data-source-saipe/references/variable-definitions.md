# SAIPE Variable Definitions

Detailed definitions of SAIPE variables, population universes, and coding conventions.

> **CRITICAL: Portal vs Census Raw File Encoding**
>
> This document describes **Education Data Portal** integer encodings, which differ from Census Bureau raw file formats. The Portal converts categorical variables to integers for consistency across sources.
>
> | Context | FIPS Alabama | FIPS California | Missing | Suppressed |
> |---------|--------------|-----------------|---------|------------|
> | **Portal (integers)** | `1` | `6` | `-1` | `-3` |
> | Census raw files | `01` (string) | `06` (string) | varies | varies |
>
> **Key difference:** Portal FIPS codes are integers (no leading zeros). When filtering by state, use integers: `fips == 6` not `fips == "06"` or `fips == "6"`.

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

### State FIPS Codes (Portal Integer Encoding)

The Portal stores FIPS codes as integers (no leading zeros). Use integers when filtering:

```python
# Correct - use integer
df.filter(pl.col("fips") == 6)  # California

# WRONG - these will not match
df.filter(pl.col("fips") == "06")  # String won't match integer
df.filter(pl.col("fips") == "6")   # Still a string
```

| Code | State | Code | State |
|------|-------|------|-------|
| 1 | Alabama | 27 | Minnesota |
| 2 | Alaska | 28 | Mississippi |
| 4 | Arizona | 29 | Missouri |
| 5 | Arkansas | 30 | Montana |
| 6 | California | 31 | Nebraska |
| 8 | Colorado | 32 | Nevada |
| 9 | Connecticut | 33 | New Hampshire |
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

**Territories (in Portal data):**
| Code | Territory |
|------|-----------|
| 60 | American Samoa |
| 66 | Guam |
| 69 | Northern Mariana Islands |
| 72 | Puerto Rico |
| 78 | Virgin Islands |

### School District ID (LEAID)

In the Portal, `leaid` is stored as an **integer** (not a 7-character string):

- Conceptually 7 digits: first 2 = state FIPS, remaining 5 = district within state
- Example: `622710` (integer) = California district 22710
- Note: Leading zeros are not stored (state FIPS 06 → 6, so 0622710 → 622710)

```python
# Filtering by leaid - use integers
df.filter(pl.col("leaid") == 622710)  # California district 22710

# If you need the 7-character format for joining with other sources
df.with_columns(
    pl.col("leaid").cast(str).str.zfill(7).alias("leaid_str")
)
```

### County FIPS Codes

- 5-character string
- First 2 = state FIPS
- Last 3 = county within state
- Example: `06037` = Los Angeles County, CA

## Missing Data Codes

### Portal Integer Encoding

The Education Data Portal uses standard negative integer codes across all SAIPE variables:

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing/not reported | State did not report; value unknown |
| `-2` | Not applicable | Item doesn't apply to this district |
| `-3` | Suppressed | Data suppressed for privacy protection |
| `null` | No data | No value present in source |

> **Note:** Unlike some other sources (e.g., CCD enrollment where `-1` = Pre-K), SAIPE uses `-1` consistently for missing data across all variables.

### Handling Missing Data

```python
import polars as pl

# Identify problematic values
missing_codes = [-1, -2, -3]

# Filter to valid data only
df_valid = df.filter(~pl.col("est_population_5_17_poverty").is_in(missing_codes))

# Or convert to null for calculations
df_clean = df.with_columns(
    pl.when(pl.col("est_population_5_17_poverty").is_in(missing_codes))
    .then(None)
    .otherwise(pl.col("est_population_5_17_poverty"))
    .alias("est_population_5_17_poverty")
)
```

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

When accessing SAIPE via the Urban Institute API, variable names include the `est_` prefix:

| Census Variable | Portal Variable | Data Type |
|-----------------|-----------------|-----------|
| Total population | `est_population_total` | Integer |
| Population 5-17 | `est_population_5_17` | Integer |
| Children 5-17 in poverty | `est_population_5_17_poverty` | Integer |
| Percent 5-17 in poverty | `est_population_5_17_poverty_pct` | Float |
| Percent population 5-17 | `est_population_5_17_pct` | Float |
| District ID | `leaid` | Integer |
| State FIPS | `fips` | Integer |
| Year | `year` | Integer |
| Census district ID | `district_id` | Integer |
| Census district name | `district_name` | String |

> **Note:** All Portal variables are lowercase. The `est_` prefix indicates these are estimates, not direct counts.
