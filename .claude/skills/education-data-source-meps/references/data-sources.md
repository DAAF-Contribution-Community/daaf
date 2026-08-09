# MEPS Data Sources

Input data used to construct Model Estimates of Poverty in Schools, including CCD, SAIPE, and ISP data.

## Overview

MEPS combines multiple federal data sources to estimate school-level poverty:

```
MEPS = f(CCD school data, SAIPE district poverty, ISP direct certification)
```

Each source contributes different information to the model.

## Common Core of Data (CCD)

### What is CCD?

The Common Core of Data is the primary federal database on public elementary and secondary schools and districts in the United States.

- **Source**: National Center for Education Statistics (NCES)
- **Coverage**: All public schools and districts
- **Frequency**: Annual
- **Years**: 1986-present

### CCD Components Used in MEPS

| CCD Dataset | MEPS Usage |
|-------------|------------|
| School Directory | School identifiers, location, type |
| School Enrollment | Total enrollment, demographics |
| School Characteristics | Grade span, charter status, locale |
| District Directory | District identifiers, boundaries |
| FRPL Counts | Where reliable, as model input |

### Key CCD Variables for MEPS

| Variable | Description | Role in MEPS |
|----------|-------------|--------------|
| `ncessch` | 12-character school ID | Primary identifier |
| `leaid` | 7-character district ID | Aggregation unit |
| `enrollment` | Total student count | Weighting |
| `free_or_reduced_price_lunch` | FRPL eligible count | Model input (where reliable) |
| `fips` | State FIPS code | Geographic identifier |
| `urban_centric_locale` | Urban/suburban/rural | Model covariate |
| `charter` | Charter school indicator | Model covariate |
| `school_type` | Regular, special ed, vocational | Sample selection |

### CCD Data Quality Notes

- **FRPL in CEP schools**: Often reported as 100%, unreliable as poverty measure
- **Missing data**: Some schools have missing enrollment or FRPL counts
- **Definitional changes**: School IDs can change with restructuring
- **Input vintage**: Record the exact CCD vintage used by the selected MEPS release; do not infer a fixed MEPS publication lag from CCD timing

## Small Area Income and Poverty Estimates (SAIPE)

### What is SAIPE?

SAIPE provides annual estimates of income and poverty for states, counties, and school districts produced by the U.S. Census Bureau.

- **Source**: U.S. Census Bureau
- **Coverage**: All states, counties, and school districts
- **Frequency**: Annual
- **Years**: 1995-present

### SAIPE Methodology

SAIPE combines multiple data sources:
1. American Community Survey (ACS) - primary survey data
2. Individual income tax returns (IRS)
3. Supplemental Nutrition Assistance Program (SNAP) data
4. Decennial Census data (for benchmarking)

Uses a regression-based model to produce estimates for small areas where direct survey estimates would be unreliable.

### Key SAIPE Variables for MEPS

| Variable | Description | Role in MEPS |
|----------|-------------|--------------|
| `population_5_17_poverty` | Children 5-17 in poverty (count) | District calibration |
| `population_5_17_poverty_pct` | Percent of 5-17 in poverty | Model target alignment |
| `population_5_17` | Total children 5-17 | Denominator |
| `median_household_income` | District median income | Model covariate |

### SAIPE in MEPS

SAIPE serves as the **calibration anchor** for MEPS:
1. MEPS model generates school-level estimates
2. School estimates are adjusted so district totals match SAIPE
3. This ensures MEPS aligns with Census poverty data at the district level

### SAIPE Data Quality Notes

- **Model-based**: SAIPE itself is modeled, not direct counts
- **Margin of error**: Estimates have uncertainty, especially for small districts
- **School-age specific**: Uses 5-17 population, not total population
- **Geographic boundaries**: Based on school district boundaries which can change

## Identified Student Percentage (ISP) Data

### What is ISP?

The Identified Student Percentage is the share of students directly certified for free meals through categorical eligibility programs.

- **Source**: State education agencies (via USDA/FNS)
- **Used in**: MEPS 2.0 (December 2025)
- **Coverage**: Schools participating in National School Lunch Program

### ISP Components

Students are identified through participation in:

| Program | Typical Income Threshold | Coverage |
|---------|-------------------------|----------|
| SNAP | 130% FPL | Nationwide |
| TANF | Varies by state | Nationwide |
| Medicaid | Varies by state | Select states |
| Foster Care | N/A (categorical) | Nationwide |
| Homeless | N/A (categorical) | Nationwide |
| Migrant | N/A (categorical) | Nationwide |
| Runaway | N/A (categorical) | Nationwide |
| Head Start | 100% FPL | Where applicable |

### ISP Advantages Over FRPL

| Characteristic | FRPL | ISP |
|----------------|------|-----|
| Requires family application | Often yes | No |
| Affected by form non-response | Yes | No |
| Directly tied to program data | No | Yes |
| Available in CEP schools | Distorted | Yes |

### ISP in MEPS 2.0

MEPS 2.0 incorporates ISP as a key predictor:
- Provides poverty signal even in CEP schools
- More directly measures program participation
- Less affected by form collection policies

### ISP Data Quality Notes

- **State variation**: Which programs are linked varies by state
- **Matching quality**: Student-level matching to programs varies
- **Timing**: ISP measured at a point in time, may not reflect full year
- **Not a poverty rate**: ISP is program participation, not income verification

## Data Linkage

### How Data Sources Connect

```
CCD Schools ─────┬──── ncessch (school ID)
                 │
                 ├──── leaid (district ID) ──── SAIPE Districts
                 │
                 └──── School characteristics ──── Model covariates
                 
ISP Data ────────┴──── Matched to schools via state/school identifiers
```

### Join Keys

| Join | Key Variable(s) | Notes |
|------|----------------|-------|
| CCD School ↔ MEPS | `ncessch`, `year` | Direct match |
| CCD School ↔ CCD District | `leaid` | Many-to-one |
| CCD District ↔ SAIPE | `leaid`, `year` | Direct match |
| CCD School ↔ ISP | State-specific matching | Complex matching |

## Data Availability

### Coverage by Year

| Data Source | Relevant Coverage / Status | Update Note |
|-------------|----------------------------|-------------|
| CCD | Verify the exact input years documented for the selected MEPS release | Federal source updates separately from MEPS |
| SAIPE | Verify the exact input years documented for the selected MEPS release | Federal source updates separately from MEPS |
| ISP | Used in MEPS 2.0 | State availability and linkage vary |
| MEPS 1.0 | 2006-2019 | Original release |
| MEPS 2.0 | School years 2009-10 through 2022-23 | Released 2025-12-11; Urban states updates will occur annually |

> **Portal status re-probed 2026-08-06:** Portal year 2022 returned rows (count 94,941); Portal year 2023 returned an empty result (count 0). This is a publication-vintage observation, not evidence of a fixed methodological lag or a causal delay attributable to CCD or SAIPE.

### Known Data Gaps

1. **Private schools**: Not included in CCD or MEPS
2. **New schools**: May be missing first year of operation
3. **Closed schools**: May have incomplete final year data
4. **Restructured districts**: ID changes can complicate longitudinal analysis

## Accessing Source Data

### CCD Data

Available via the mirror system. See `datasets-reference.md` for canonical paths and `fetch-patterns.md` for fetch code patterns.

Key CCD datasets:
- School Directory: `ccd/schools_ccd_directory`
- School Enrollment: `ccd/schools_ccd_enrollment_{year}` (yearly)
- District Directory: `ccd/school-districts_lea_directory`

### SAIPE Data

Available via the mirror system:
- District Poverty: `saipe/districts_saipe`

Also available directly from the Census Bureau:
- https://www.census.gov/programs-surveys/saipe.html

### ISP Data

- Not directly available via the Education Data Portal mirrors
- Incorporated into MEPS 2.0 estimates
- Raw data available through USDA Food and Nutrition Service

## Data Quality Assessment

### Reliability Hierarchy

| Data Element | Reliability | Notes |
|--------------|-------------|-------|
| Enrollment counts | High | Well-collected in CCD |
| School identifiers | High | NCES standards |
| SAIPE district poverty | Moderate-High | Model-based but Census quality |
| FRPL counts (non-CEP) | Moderate | Varies by state |
| FRPL counts (CEP schools) | Low | Often 100%, meaningless |
| ISP | Moderate | Varies by state matching |

### Recommendations

1. **Trust MEPS over raw FRPL** - MEPS accounts for known data quality issues
2. **Use enrollment for weighting** - Most reliable CCD variable
3. **Check for ID changes** - When doing longitudinal analysis
4. **Note CEP status** - Helps interpret FRPL data quality
