# CRDC Collection Methodology

Understanding how CRDC data is collected, who reports it, and what universe it covers is essential for proper analysis and interpretation.

## Contents

- [Collection Overview](#collection-overview)
- [Sampling vs. Universe](#sampling-vs-universe)
- [Collection Timeline](#collection-timeline)
- [Reporting Requirements](#reporting-requirements)
- [Data Submission Process](#data-submission-process)
- [Who Reports](#who-reports)
- [Validation and Quality Control](#validation-and-quality-control)
- [Coverage Limitations](#coverage-limitations)

---

## Collection Overview

### Basic Facts

| Attribute | Value |
|-----------|-------|
| **Collector** | U.S. Department of Education, Office for Civil Rights |
| **Frequency** | Generally biennial; 2020-21 and 2021-22 were consecutive |
| **Unit of collection** | School and LEA (Local Educational Agency) |
| **Reference period** | Full school year |
| **Respondents** | All public schools and LEAs receiving federal financial assistance |
| **Data type** | Administrative data reported by schools |

### What Makes CRDC Unique

1. **Mandatory collection** - Schools are legally required to respond
2. **Civil rights focus** - Designed for equity monitoring and enforcement
3. **Subgroup disaggregation** - Extensive breakdown by protected classes
4. **Self-reported** - Schools report their own data
5. **Universe coverage** - OCR documents every modern collection (2011-12, 2013-14, 2015-16, 2017-18, 2020-21, 2021-22, 2023-24) as a universe collection; collections from 1968 to 2010 were samples, except 1976 and 2000

---

## Sampling vs. Universe

### Evolution of Collection Approach

| Year | Approach | Coverage | Notes |
|------|----------|----------|-------|
| **1968-2008** | Sample (universe in 1976 and 2000) | Varied | Per OCR, collections from 1968 to 2010 were samples, except 1976 and 2000 |
| **2009-10** | Sample | ~7,000 LEAs | Modern CRDC redesign |
| **2011-12** | **Universe** | All public schools and districts (response: 98.4% of districts, 99.2% of schools, 99.6% of students) | First modern universe collection (OCR 2011-12 Data Snapshot) |
| **2013-14** | **Universe** | 16,758 districts; 95,507 schools | Official First Look explicitly identifies a universe collection; chronic absenteeism first collected |
| **2015-16** | Universe | 96,440 schools (final target) | Chronic absenteeism collected again |
| **2017-18** | Universe | ~97,600 schools (17,637 LEAs final target) | Expanded variables; Puerto Rico added; chronic absenteeism now taken from EDFacts |
| **2020-21** | Universe | ~97,500 schools | COVID-impacted year |
| **2021-22** | Universe | ~98,000 schools | Consecutive collection after 2020-21 |
| **2023-24** | Universe | 17,591 LEAs; 97,094 schools | Public-use file released August 31, 2026 |

### Implications for Analysis

```python
def check_coverage_appropriateness(year, analysis_type):
    """
    Determine if CRDC year is appropriate for analysis type.
    """
    # Portal year = fall of the school year (2020 = 2020-21, 2021 = 2021-22).
    # Every modern collection is a universe collection per OCR; 2023 is
    # exposed for some topics only, so check the family's years first.
    universe_years = [2011, 2013, 2015, 2017, 2020, 2021, 2023]
    covid_years = [2020]  # 2020-21; 2021-22 is not the COVID year
    
    if year not in universe_years:
        return {
            'appropriate': False,
            'reason': f'{year} is not a CRDC collection year label',
            'recommendation': 'Use a collection year label (fall year of the school year)'
        }
    
    if analysis_type == 'time_series' and year in covid_years:
        return {
            'appropriate': False,
            'reason': '2020-21 is COVID-impacted and not comparable for trends',
            'recommendation': 'Exclude or flag Portal year 2020; harmonize definitions across cycles'
        }
    
    return {'appropriate': True}
```

```r
# Determine if a CRDC year is appropriate for the analysis type.
# Portal year = fall of the school year (2020 = 2020-21, 2021 = 2021-22).
# Every modern collection is a universe collection per OCR; 2023 is
# exposed for some topics only, so check the family's years first.
universe_years <- c(2011, 2013, 2015, 2017, 2020, 2021, 2023)
covid_years <- c(2020)  # 2020-21; 2021-22 is not the COVID year

year <- 2013
analysis_type <- "national_totals"  # or "school_level", "time_series"

if (!(year %in% universe_years)) {
  result <- list(
    appropriate = FALSE,
    reason = sprintf("%d is not a CRDC collection year label", year),
    recommendation = "Use a collection year label (fall year of the school year)"
  )
} else if (analysis_type == "time_series" && year %in% covid_years) {
  result <- list(
    appropriate = FALSE,
    reason = "2020-21 is COVID-impacted and not comparable for trends",
    recommendation = "Exclude or flag Portal year 2020; harmonize definitions across cycles"
  )
} else {
  result <- list(appropriate = TRUE)
}
```

### Early Collection Coverage

OCR's 2011-12 Data Snapshot (School Discipline, March 2014) states that the 2011-12 CRDC "included all public schools and public school districts in the nation that serve students for at least 50% of the school day", with a response rate of 98.4% of school districts and 99.2% of schools, representing 99.6% of students. The 2020-21 user's manual adds that collections from 1968 to 2010 were samples, except the 1976 and 2000 collections, which covered a universe of school districts. The 2025-26 overview lists 2011-12 first among the universe collections.

### Universe Collection Strengths (2011-12 onward)

- **Comprehensive enumeration** - Official 2013-14 evidence reports 16,758 districts and 95,507 schools
- **National aggregation possible** - Subject to response, suppression, and data-quality checks
- **Longitudinal analysis still requires care** - Definitions, family availability, and COVID context vary
- **Small area analysis possible** - State, district, and school-level analysis, with suppression checks

---

## Collection Timeline

### Typical Schedule

```
School Year (e.g., 2021-22)
├── September-June: School year in progress
│   └── Schools accumulate data throughout year
│
├── Following Fall: Collection opens
│   └── Schools receive notification to report
│
├── Collection Period: ~6 months
│   ├── Schools enter data into CRDC system
│   ├── Validation checks run
│   └── Corrections requested
│
├── Data Processing: ~6-12 months
│   ├── OCR reviews submissions
│   ├── Data quality checks
│   └── Final data preparation
│
└── Public Release: ~2 years after school year
    └── Data files and reports released
```

### Historical Release Timeline

| School Year | Data Released | Lag Time |
|-------------|---------------|----------|
| 2011-12 | 2014 | ~2 years |
| 2013-14 | 2016 | ~2 years |
| 2015-16 | 2018 | ~2 years |
| 2017-18 | 2020 | ~2 years |
| 2020-21 | 2023 | ~2 years |
| 2021-22 | 2025 (Jan 17) | ~2-3 years |
| 2023-24 | 2026 (Aug 31) | ~2 years after the school year; ~1.4 years after the collection closed (April 7, 2025) |

Submission windows from the user's manuals: December 13, 2021 to April 8, 2022 (2020-21); December 11, 2023 to February 26, 2024 (2021-22); December 9, 2024 to April 7, 2025 (2023-24).

### Reference Period

| Data Type | Reference Period |
|-----------|------------------|
| Enrollment | Typically October 1 snapshot |
| Discipline | Full school year cumulative |
| Restraint/seclusion | Full school year cumulative |
| Course enrollment | Full school year |
| Chronic absenteeism | Full school year |
| Staffing | Point-in-time |

---

## Reporting Requirements

### Who Must Report

All public schools and LEAs that receive **federal financial assistance** from the Department of Education, including:

| Entity Type | Required |
|-------------|----------|
| Traditional public schools | Yes |
| Charter schools | Yes |
| Magnet schools | Yes |
| Alternative schools | Yes |
| Justice facility schools | Yes |
| Virtual schools | Yes |

### Who Is Exempt

| Entity Type | Required | Notes |
|-------------|----------|-------|
| Bureau of Indian Education schools | No | Tribal schools excluded |
| DoD schools | No | Department of Defense operated |
| U.S. territory schools (except PR) | No | Guam, Virgin Islands, etc. |
| Puerto Rico | Yes | Added beginning with the 2017-18 CRDC |
| Private schools | No | Not receiving ED financial assistance |

### Legal Authority

OCR's authority to collect CRDC data comes from:

1. **Department of Education Organization Act** - 20 U.S.C. § 3413(c)(1)
2. **Title VI regulations** - 34 CFR § 100.6(b)
3. **Section 504 regulations** - 34 CFR § 104.61
4. **Title IX regulations** - 34 CFR § 106.81

### Failure to Report

Schools that fail to submit CRDC data may face:
- OCR compliance review
- Technical assistance requirements
- Potential impact on federal funding eligibility

---

## Data Submission Process

### Collection System

CRDC uses a web-based data collection system:

1. **Pre-populated directory** - School information from CCD pre-loaded
2. **Data entry forms** - Online forms for each data category
3. **Validation rules** - System checks for logical errors
4. **Edit reports** - Flagged issues for correction
5. **Certification** - Official sign-off by LEA

### Data Entry Methods

| Method | Description |
|--------|-------------|
| **Manual entry** | Direct entry into web forms |
| **File upload** | Batch upload of formatted data files |
| **State submission** | Some states submit on behalf of LEAs |

### Validation Checks

The collection system runs automatic checks:

| Check Type | Example |
|------------|---------|
| **Range checks** | Enrollment > 0 |
| **Cross-field validation** | Discipline ≤ enrollment |
| **Year-over-year comparison** | Flagging large changes |
| **Logical consistency** | AP enrollment only at schools offering AP |
| **Completeness** | Required fields populated |

---

## Who Reports

### Reporting Chain

```
School → LEA/District → OCR
     └── Individual schools prepare data
           └── LEA coordinates and certifies
                 └── Submitted to OCR system
```

### Certification

- **LEA-level certification** - Superintendent or designee certifies
- **Legal attestation** - Certifies data is "complete and accurate"
- **Deadline** - Specified by OCR for each collection

### Common Reporting Challenges

| Challenge | Impact |
|-----------|--------|
| **Staff capacity** | Small districts struggle with burden |
| **Data systems** | Not all systems track CRDC variables |
| **Definition interpretation** | Inconsistent understanding |
| **Documentation** | Records may be incomplete |
| **Turnover** | New staff unfamiliar with requirements |

---

## Validation and Quality Control

### OCR Quality Control

After submission, OCR performs:

1. **Automated edits** - Additional validation checks
2. **Outlier review** - Flagging extreme values
3. **Follow-up** - Contact LEAs about concerns
4. **Data corrections** - Process amendments

### Known Quality Issues

| Issue | Description |
|-------|-------------|
| **Underreporting** | Some incidents not captured |
| **Definition variance** | Different interpretations |
| **System limitations** | Local data systems may not track all variables |
| **Respondent burden** | May affect accuracy |

### No Independent Verification

Important: CRDC data is **self-reported** and **not independently verified**:
- OCR may conduct spot-checks
- Investigations may reveal discrepancies
- But routine verification is not performed

---

## Coverage Limitations

### Populations Not Covered

| Population | Covered | Notes |
|------------|---------|-------|
| Public school students | Yes | Primary focus |
| Private school students | No | Not receiving ED funds |
| Home-schooled students | No | Not in public system |
| BIE school students | No | Different federal oversight |
| DoD school students | No | Different federal system |

### Geographic Limitations

| Area | Covered | Since |
|------|---------|-------|
| 50 states | Yes | 1968 |
| District of Columbia | Yes | 1968 |
| Puerto Rico | Yes | 2017-18 |
| U.S. Virgin Islands | No | — |
| Guam | No | — |
| American Samoa | No | — |
| Northern Mariana Islands | No | — |

### Missing Data Scenarios

Schools may have missing data due to:

| Scenario | Result |
|----------|--------|
| School didn't respond | Missing for that school |
| Variable not applicable | Set to 0 or null |
| Small cell suppression | Suppressed for privacy |
| Data not collected that year | Variable doesn't exist |

---

## Linking CRDC to Other Data

### Common Core of Data (CCD) Link

CRDC uses **ncessch** (NCES school ID) as primary identifier for linking to CCD:

```python
import polars as pl

# Linking CRDC to CCD
def link_crdc_ccd(crdc_df: pl.DataFrame, ccd_df: pl.DataFrame) -> pl.DataFrame:
    """
    Link CRDC data to CCD school characteristics.

    Args:
        crdc_df: CRDC data (must have ncessch as String)
        ccd_df: CCD directory data (must have ncessch as String)

    Returns:
        Joined DataFrame with CCD characteristics
    """
    ccd_cols = ccd_df.select([
        "ncessch", "school_name", "leaid",
        "urban_centric_locale", "charter",
        "free_or_reduced_price_lunch",
    ])

    merged = crdc_df.join(ccd_cols, on="ncessch", how="left")

    # Check join success
    unmatched = merged.filter(pl.col("school_name").is_null()).height
    if unmatched > 0:
        print(f"Warning: {unmatched} CRDC schools not matched to CCD")

    return merged
```

```r
library(dplyr)

# Linking CRDC to CCD school characteristics.
# ASSUMES: ncessch is a character (string) column in both data frames.
ccd_cols <- ccd_df |> select(
  ncessch, school_name, leaid,
  urban_centric_locale, charter,
  free_or_reduced_price_lunch
)

merged <- crdc_df |> left_join(ccd_cols, by = "ncessch")

# Check join success
unmatched <- merged |> filter(is.na(school_name)) |> nrow()
if (unmatched > 0) {
  cat(sprintf("Warning: %d CRDC schools not matched to CCD\n", unmatched))
}
```

> **Note:** Some CRDC rows have `ncessch` as null. Use `crdc_id` or `leaid` for alternative linkage when `ncessch` is unavailable.

### Key Identifiers

| Identifier | Format | Description |
|------------|--------|-------------|
| `crdc_id` | 12-character string | Primary CRDC identifier; always present |
| `ncessch` | 12-character string | NCES school ID; may be null for some entries |
| `leaid` | 7-character string | NCES district ID; always present |
| `fips` | 2-digit integer | State FIPS code |

### Year Alignment

When linking:
- CRDC Portal `year` is the fall of the school year (2020-21 = year 2020)
- CCD Portal `year` uses the same fall convention (see `education-data-context`)
- Ensure same school year for accurate linking

---

## Data Documentation Resources

### Official Documentation

| Resource | URL |
|----------|-----|
| CRDC website | https://civilrightsdata.ed.gov/ |
| CRDC Resource Center | https://crdc.communities.ed.gov/ |
| Data elements list | Available on ED.gov |
| Collection forms | Available on CRDC Resource Center |

### Technical Documentation

- **Data file user's manual** - Detailed file layouts
- **Data element definitions** - Official variable definitions
- **Collection instruments** - Actual survey forms
- **Codebooks** - Code values and meanings

### Education Data Portal

Urban Institute provides processed CRDC data via the Education Data Portal:
- https://educationdata.urban.org/
- Data available through mirror-based downloads (parquet primary, CSV fallback)
- See `mirrors.yaml` for mirror configuration and `datasets-reference.md` for canonical dataset paths
- See `fetch-patterns.md` for `fetch_from_mirrors()` and `fetch_yearly_from_mirrors()` code patterns

---

## Best Practices for Using CRDC

### Before Analysis

1. **Check year coverage** - Sample vs. universe
2. **Verify variables exist** - Not all variables all years
3. **Read documentation** - Official definitions may differ from assumptions
4. **Understand suppression** - Small cells suppressed

### During Analysis

1. **Use rates, not counts** - Normalize by enrollment
2. **Document definitions** - Note which CRDC year's definitions used
3. **Check for outliers** - Flag extreme values for review
4. **Note limitations** - Self-reported, potential underreporting

### Reporting Results

1. **Cite data source** - CRDC year, access date
2. **Note coverage** - What population is included
3. **Acknowledge limitations** - Self-reported, definition variation
4. **Provide context** - Civil rights purpose of data
