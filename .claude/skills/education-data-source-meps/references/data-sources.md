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

- **FRPL in CEP schools**: CEP schools may report all students as free-lunch eligible (NCES); since SY 2016-17 states may report direct certification instead. Unreliable as a poverty measure
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
| `population_5_17_poverty` | Children 5-17 in poverty (count) | Model outcome after Urban's adjustment |
| `population_5_17_poverty_pct` | Percent of 5-17 in poverty | Model target alignment |
| `population_5_17` | Total children 5-17 | Denominator |
| `median_household_income` | District median income | Model covariate |

### SAIPE in MEPS

SAIPE is the **model outcome** for MEPS (Gutierrez & Blagg 2025):
1. Urban adjusts SAIPE's count of students in poverty for geographic districts enrolling 10,000 or more students, subtracting ACS-based estimates of non-public school students in poverty
2. The district-level model predicts adjusted SAIPE poverty from district-aggregated free-lunch or direct-certification shares; its parameters are then applied to schools
3. Only Modified MEPS is adjusted so district aggregates match adjusted SAIPE. Original MEPS is a model prediction

### SAIPE Data Quality Notes

- **Model-based**: SAIPE itself is modeled, not direct counts
- **Margin of error**: Estimates have uncertainty, especially for small districts
- **School-age specific**: Uses 5-17 population, not total population
- **Geographic boundaries**: Based on school district boundaries which can change

## Identified Student Percentage (ISP) Data

### What is ISP?

The Identified Student Percentage is identified students ÷ enrollment as of April 1 of the prior school year. Identified students are those certified for free meals without an application (directly certified via SNAP, TANF, FDPIR or, where USDA-approved, Medicaid, plus homeless, migrant, runaway, Head Start and non-application foster children). ISP is not identical to CCD's direct-certification count.

- **Source**: ISP: from FRAC's CEP database (state-posted ISPs, 2013-14 onward), used to fill missing direct-certification data. MEPS 1.0 used some; 2.0 uses all available.
- **Coverage**: States must post school-level ISPs for schools with ISPs of at least 15 percent as of SY 2024-25 (30 percent for prior years), so lower-ISP schools are generally absent (Gutierrez & Blagg 2025, appendix A)
- **Timing**: Posted ISP files report the previous school year's ISP (e.g., the 2022-23 file refers to spring 2022 data)

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

MEPS 2.0 uses ISP as a **proxy for missing direct-certification data**, not as a separate predictor. MEPS 1.0 used some ISP data; MEPS 2.0 uses all available ISPs for 2013-14 through 2022-23. ISP files are matched to CCD schools numerically (identifiers exist only from 2019-20) or by fuzzy name matching at a 90 percent threshold (Gutierrez & Blagg 2025, appendix A).

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
| ISP | MEPS 1.0 used some; MEPS 2.0 uses all available for 2013-14 through 2022-23 | State availability and linkage vary |
| MEPS 1.0 | 2013-14 to 2018-19 (superseded) | Original release |
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
- Incorporated into MEPS 2.0 estimates (as a proxy for missing direct certification)
- Source: FRAC's national CEP database, compiled from state-posted ISPs. The public database shows only the most recent year; Urban obtained earlier years (from 2013) on request from FRAC (Gutierrez & Blagg 2025, appendix A)

## Data Quality Assessment

### Reliability Hierarchy

| Data Element | Reliability | Notes |
|--------------|-------------|-------|
| Enrollment counts | High | Well-collected in CCD |
| School identifiers | High | NCES standards |
| SAIPE district poverty | Moderate-High | Model-based but Census quality |
| FRPL counts (non-CEP) | Moderate | Varies by state |
| FRPL counts (CEP schools) | Low | May report all students as eligible; not a poverty signal |
| ISP | Moderate | Varies by state matching |

### Recommendations

1. **Trust MEPS over raw FRPL** - MEPS accounts for known data quality issues
2. **Use enrollment for weighting** - Most reliable CCD variable
3. **Check for ID changes** - When doing longitudinal analysis
4. **Note CEP status** - Helps interpret FRPL data quality
