# LEHD Methodology

How the Longitudinal Employer-Household Dynamics (LEHD) program produces PSEO tabulations.

## Contents

- [LEHD Program Overview](#lehd-program-overview)
- [Data Sources](#data-sources)
- [Data Matching Process](#data-matching-process)
- [Employment Coverage](#employment-coverage)
- [Differential Privacy Protection](#differential-privacy-protection)
- [Historical Context](#historical-context)

## LEHD Program Overview

The Longitudinal Employer-Household Dynamics (LEHD) program is part of the U.S. Census Bureau's Center for Economic Studies. LEHD creates public-use information by combining multiple administrative data sources:

- **Local Employment Dynamics (LED) partnership**: State unemployment insurance wage records
- **Federal employment data**: Office of Personnel Management records
- **Census Bureau surveys**: Demographic and business data
- **Partner institution data**: University transcript records

PSEO is one of several LEHD data products:

| Product | Description |
|---------|-------------|
| QWI (Quarterly Workforce Indicators) | Employment, earnings, job creation by industry/geography |
| LODES (Origin-Destination Employment Statistics) | Home-work commuting patterns |
| J2J (Job-to-Job Flows) | Worker transitions between employers |
| PSEO | Graduate employment outcomes |

## Data Sources

### Transcript Data (Education Input)

Institutions and state agencies submit graduation files containing:

| Field | Description |
|-------|-------------|
| Social Security Number | Primary identifier for matching |
| Date of birth | Secondary identifier |
| Graduation year | When credential was awarded |
| Degree/credential type | Certificate, Associate's, Bachelor's, Master's, Doctoral |
| Major/discipline | CIP code (Classification of Instructional Programs) |
| Institution | OPEID (Office of Postsecondary Education ID) |

### Employment Data (LEHD Input)

State unemployment insurance (UI) wage records include:

| Field | Description |
|-------|-------------|
| Worker identifier | SSN or state equivalent |
| Employer identifier | State Employer ID (SEIN) |
| Wages | Quarterly earnings |
| Industry | NAICS code from employer |
| Location | State and county of establishment |

## Data Matching Process

```
┌─────────────────────┐     ┌─────────────────────┐
│  Transcript Data    │     │    LEHD Jobs Data   │
│  (from partners)    │     │  (UI wage records)  │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           └───────────┬───────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Person Record  │
              │    Linkage      │
              │  (SSN/DOB)      │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Employment     │
              │  Histories      │
              │  by Graduate    │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Tabulation &   │
              │  Aggregation    │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Differential   │
              │  Privacy Noise  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Published      │
              │  Statistics     │
              └─────────────────┘
```

### Key Matching Steps

1. **Standardize identifiers**: Clean and format SSNs, dates of birth
2. **Link to Person Universe Infrastructure (PUI)**: Census's master person file
3. **Attach employment histories**: All jobs in LEHD system for matched graduates
4. **Calculate post-graduation outcomes**: Earnings and employment 1, 5, 10 years out
5. **Apply labor force attachment filters**: Remove marginal workers
6. **Aggregate to tabulation cells**: By institution, degree, CIP, cohort
7. **Apply privacy protection**: Differential privacy noise injection

## Employment Coverage

### What's Covered

LEHD covers **over 96%** of U.S. employment (PSEO Technical Documentation):

**Private sector** (covered by state UI):
- All wage and salary workers
- Most corporate officials and executives
- Part-time workers
- Workers on paid leave

**State and local government**:
- Most employees (varies by state)
- Elected officials often excluded

**Federal government** (from OPM data):
- Most civilian federal workers
- Coverage: 2000-2020 per the PSEO Technical Documentation (updated June 12, 2023); later releases may extend this

### What's NOT Covered

| Category | Reason |
|----------|--------|
| Self-employed (unincorporated) | Not covered by UI |
| Independent contractors | Not covered by UI |
| Railroad workers | Separate railroad UI system |
| Military | Not in OPM data |
| U.S. Postal Service | Not in OPM data |
| Some family employees | State-specific exemptions |
| Certain farm workers | State-specific exemptions |
| Some non-profit workers | State-specific exemptions |
| National security agencies | Security exclusions |

### UI Coverage by State

States have discretion in UI coverage rules. LEHD has varying historical coverage:

- **Early 1990s**: ~10 states
- **Late 1990s**: ~40 states
- **2010**: All 50 states + D.C. (Massachusetts was last)

## Differential Privacy Protection

PSEO uses **differential privacy** to protect individual confidentiality, a state-of-the-art method from computer science.

### Why Differential Privacy?

Traditional suppression (hiding small cells) has limitations:
- Differencing attacks can reveal suppressed values
- External data can be combined to re-identify individuals
- Universities have access to their own transcript data

Differential privacy provides **mathematically provable** privacy guarantees regardless of external information.

### How It Works

**For earnings tabulations:**
1. Categorize individual earnings into predefined histogram bins
2. Add noise (geometric mechanism) to each bin count
3. Construct empirical cumulative distribution function (CDF)
4. Calculate percentiles from the protected CDF
5. Sum bin counts for protected cell counts

**For flows tabulations:**
- Apply geometric noise mechanism directly to counts

### Suppression Rules

Earnings cells with protected count < 30 are suppressed due to low quality (flows counts are instead noise-infused and post-processed):
- Status flag = 5 indicates suppression
- Suppression is for data quality, not privacy (differential privacy already protects)

### Privacy-Accuracy Tradeoff

- More noise = more privacy, less accuracy
- Small cells have higher relative noise
- Aggregating across institutions/cohorts improves accuracy

## Historical Context

### Timeline

| Year | Milestone |
|------|-----------|
| 2018 | First PSEO data released (March) |
| R2022Q4 | Partners in 24 states (Census pseo_all_partners.txt for that release) |
| V4.13.0 (2025Q4) | 952 institutions; partners in 32 states plus D.C. |
| V4.14.1 (2026Q2) | 1,117 institution rows; partners in 37 states plus D.C. |

PSEO coverage changes by release. The V4.14.1 count was verified on 2026-10-19 from the Census latest-release institution, partner, and version files (V4.13.0, now the prior release, was first counted on 2026-07-21); those files should be rechecked before reporting current coverage. No national graduate-coverage percentage is asserted here.

### PSEO Coalition

The **PSEO Coalition** facilitates partnerships between institutions and Census Bureau:
- Coordinates data sharing agreements
- Develops best practices
- Advocates for program expansion
- Provides member support

Members include state higher education agencies, university systems, and individual institutions.

## Technical References

- [PSEO Technical Documentation (PDF)](https://lehd.ces.census.gov/doc/PSEOTechnicalDocumentation.pdf)
- [PSEO Protection System Appendix (PDF)](https://lehd.ces.census.gov/doc/pseo_appendix_tech_doc.pdf)
- [LEHD Public Use Schema](https://lehd.ces.census.gov/data/schema/latest/lehd_public_use_schema.html)
- Abowd, J. M., Stephens, B. E., Vilhuber, L., Andersson, F., McKinney, K. L., Roemer, M., & Woodcock, S. (2009). The LEHD Infrastructure Files and the Creation of the Quarterly Workforce Indicators. In *Producer Dynamics: New Evidence from Micro Data* (NBER Chapters, pp. 149–230). National Bureau of Economic Research.
