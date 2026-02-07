---
name: education-data-source-crdc
description: Deep reference for Civil Rights Data Collection (CRDC) - biennial OCR survey of public schools. Use when analyzing school discipline disparities, course access equity, harassment data, restraint/seclusion, chronic absenteeism, or any civil rights education indicators. Covers legal framework, data elements, quality issues, and historical changes.
metadata:
  audience: data-analysts
  domain: education-civil-rights
---

# Civil Rights Data Collection (CRDC) Source Guide

Comprehensive reference for understanding, analyzing, and interpreting CRDC data from the U.S. Department of Education's Office for Civil Rights.

## What is CRDC?

The Civil Rights Data Collection is a **mandatory biennial survey** of all public schools and districts that measures educational opportunity and civil rights compliance:

- **Collector**: U.S. Department of Education, Office for Civil Rights (OCR)
- **Purpose**: Enforce civil rights laws, identify discrimination, monitor equity
- **Coverage**: All public LEAs and schools receiving federal financial assistance
- **Frequency**: Biennial (every 2 school years)
- **Disaggregation**: Race/ethnicity, sex, disability status, English learner status
- **History**: Collected since 1968 (as Elementary and Secondary School Civil Rights Survey)

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `civil-rights-context.md` | Legal framework (Title VI, IX, Section 504, IDEA) | Understanding why data is collected |
| `data-elements.md` | All data categories and what's collected | Planning analysis, identifying variables |
| `collection-methodology.md` | Sampling, universe, timeline, reporting | Understanding coverage limitations |
| `variable-definitions.md` | Key variables, codes, disaggregation categories | Coding data, interpreting values |
| `data-quality.md` | Known issues, suppression, state variations | Addressing limitations in analysis |
| `historical-changes.md` | Evolution across collection years | Time series analysis, year comparison |

## Decision Trees

### What CRDC data do I need?

```
Research topic?
├─ School discipline
│   ├─ Suspensions (ISS/OSS) → ./references/data-elements.md#discipline
│   ├─ Expulsions → ./references/data-elements.md#discipline
│   ├─ Referrals to law enforcement → ./references/data-elements.md#discipline
│   ├─ School-related arrests → ./references/data-elements.md#discipline
│   └─ Preschool suspensions → ./references/data-elements.md#discipline
├─ Restraint and seclusion
│   └─ Physical restraint, mechanical, seclusion → ./references/data-elements.md#restraint-seclusion
├─ Harassment and bullying
│   ├─ Allegations by type → ./references/data-elements.md#harassment
│   └─ Disciplined for harassment → ./references/data-elements.md#harassment
├─ Course access and enrollment
│   ├─ AP/IB courses → ./references/data-elements.md#advanced-courses
│   ├─ Gifted/talented → ./references/data-elements.md#gifted-talented
│   ├─ Math/science courses → ./references/data-elements.md#course-access
│   └─ Computer science → ./references/data-elements.md#course-access
├─ Chronic absenteeism
│   └─ Students missing 15+ days → ./references/data-elements.md#chronic-absenteeism
├─ Special populations
│   ├─ Students with disabilities (IDEA) → ./references/data-elements.md#students-with-disabilities
│   ├─ English learners → ./references/data-elements.md#english-learners
│   └─ Preschool enrollment → ./references/data-elements.md#preschool
├─ School staffing
│   ├─ Teacher experience/certification → ./references/data-elements.md#staffing
│   └─ Counselors, nurses, etc. → ./references/data-elements.md#staffing
└─ School safety
    └─ Offenses, violence, weapons → ./references/data-elements.md#school-offenses
```

### Understanding the legal context?

```
Civil rights law question?
├─ Race/ethnicity discrimination → ./references/civil-rights-context.md#title-vi
├─ Sex/gender discrimination → ./references/civil-rights-context.md#title-ix
├─ Disability discrimination → ./references/civil-rights-context.md#section-504
├─ Special education services → ./references/civil-rights-context.md#idea
├─ Age discrimination → ./references/civil-rights-context.md#age-discrimination-act
└─ OCR enforcement process → ./references/civil-rights-context.md#ocr-enforcement
```

### Data quality concerns?

```
Data quality issue?
├─ Missing or suppressed data → ./references/data-quality.md#suppression
├─ Definition inconsistencies → ./references/data-quality.md#definition-variation
├─ Year-to-year comparability → ./references/historical-changes.md
├─ COVID-19 impact (2020-21) → ./references/data-quality.md#covid-impact
├─ Underreporting concerns → ./references/data-quality.md#underreporting
└─ State-level variations → ./references/data-quality.md#state-variations
```

## Quick Reference: Collection Years

| School Year | Collection | Coverage | Key Notes |
|-------------|------------|----------|-----------|
| 2011-12 | Sample | ~7,000 districts | First modern CRDC; sampled |
| 2013-14 | Expanded | ~16,000 districts | Larger sample |
| 2015-16 | Near-universe | ~96,000 schools | First near-complete |
| 2017-18 | Universe | ~96,000 schools | Full universe collection |
| 2020-21 | Universe | ~97,500 schools | COVID-impacted year |
| 2021-22 | Universe | ~98,000 schools | Post-pandemic baseline |
| 2023-24 | Universe | In progress | Current collection |

**Critical**: CRDC is biennial - no data for odd years (2012, 2014, 2016, 2018, 2019).

## Quick Reference: Data Categories

| Category | Description | Disaggregation |
|----------|-------------|----------------|
| **Enrollment** | Student counts by grade level | Race, sex, disability, LEP |
| **Discipline** | Suspensions, expulsions, arrests | Race, sex, disability, LEP |
| **Restraint/Seclusion** | Physical/mechanical restraint, seclusion | Race, sex, disability |
| **Harassment** | Allegations and discipline by type | Race, sex, disability |
| **Course Access** | AP, IB, math, science, CS offerings | School-level, enrollment by race/sex |
| **Chronic Absenteeism** | 15+ days missed | Race, sex, disability, LEP |
| **Staffing** | Teachers, counselors, nurses, etc. | FTE counts, qualifications |
| **Offenses** | Violence, weapons, drugs at school | Type of offense |
| **Retention** | Students retained in grade | Race, sex, disability |

## Quick Reference: Disaggregation Categories

> **CRITICAL: Portal Integer Encoding**
>
> The Education Data Portal uses **integer codes**, not the string codes shown in OCR documentation. Always filter using integers.
>
> | Variable | String Code (Raw) | Portal Integer |
> |----------|-------------------|----------------|
> | Race: White | `WH` | `1` |
> | Race: Black | `BL` | `2` |
> | Race: Hispanic | `HI` | `3` |
> | Sex: Male | `M` | `1` |
> | Sex: Female | `F` | `2` |
>
> See `./references/variable-definitions.md` for complete encoding tables.

### Race/Ethnicity (Portal Integer Codes)

| Code | Category |
|------|----------|
| `1` | White |
| `2` | Black or African American |
| `3` | Hispanic/Latino of any race |
| `4` | Asian |
| `5` | American Indian or Alaska Native |
| `6` | Native Hawaiian or Other Pacific Islander |
| `7` | Two or more races |
| `99` | Total |

### Sex (Portal Integer Codes)

| Code | Category |
|------|----------|
| `1` | Male |
| `2` | Female |
| `99` | Total |

### Disability Status (Portal Integer Codes)

| Code | Category |
|------|----------|
| `0` | Students without disabilities |
| `1` | Students with disabilities (served under IDEA) |
| `2` | Students with Section 504 only |
| `99` | Total |

### English Learner Status (Portal Integer Codes)

| Code | Category |
|------|----------|
| `1` | English learner (EL/LEP) |
| `99` | All students |

## API Access via Education Data Portal

> **API Implementation:** For URL construction patterns, pagination, and error handling, see the `education-data-query` skill. For comprehensive API learnings, see `agent_reference/EDUCATION_DATA_API_LEARNINGS.md`.

CRDC data is available through Urban Institute's Education Data Portal.

### CRITICAL: Disaggregation Required in URL Path

Most CRDC endpoints **require** disaggregation levels in the URL path (not optional):

| Documented | Actual Working Endpoint |
|------------|------------------------|
| `/schools/crdc/suspensions/{year}/` | ❌ Returns 404 |
| `/schools/crdc/discipline/{year}/disability/sex/` | ✅ Works |
| `/schools/crdc/ap-enrollment/{year}/` | ❌ Returns 404 |
| `/schools/crdc/ap-ib-enrollment/{year}/race/sex/` | ✅ Works |

**Race disaggregation cannot be used standalone** - must combine with other dimensions like `disability` or `sex`.

### Endpoints That Work WITHOUT Disaggregation

| Endpoint | Description |
|----------|-------------|
| `/schools/crdc/offerings/{year}/` | Course offerings data |
| `/schools/crdc/directory/{year}/` | School directory |

### Endpoints That REQUIRE Disaggregation

| Working Pattern | Description |
|-----------------|-------------|
| `/schools/crdc/discipline/{year}/disability/sex/` | Discipline incidents |
| `/schools/crdc/discipline/{year}/disability/race/sex/` | Discipline with full disaggregation |
| `/schools/crdc/ap-ib-enrollment/{year}/race/sex/` | AP/IB enrollment |
| `/schools/crdc/harassment-or-bullying/{year}/` | Harassment allegations |
| `/schools/crdc/restraint-and-seclusion/{year}/` | Restraint/seclusion |
| `/schools/crdc/chronic-absenteeism/{year}/` | Chronic absence |
| `/schools/crdc/retention/{year}/` | Grade retention |

### Available Years via API
- 2011, 2013, 2015, 2017, 2020, 2021 (as of 2024)
- **CRDC is biennial** - no data for even-numbered school years

## Equity Analysis Framework

CRDC data is designed for civil rights analysis. Key analytical approaches:

### Disparity Ratios
```python
import polars as pl

# Calculate discipline disparity using Portal integer codes
def discipline_disparity(df, discipline_var, group_a, group_b):
    """
    Calculate risk ratio between two groups.
    Value > 1 indicates group_a has higher rate.

    Args:
        df: DataFrame with CRDC data
        discipline_var: Column with discipline counts
        group_a: Integer race code (e.g., 2 for Black)
        group_b: Integer race code (e.g., 1 for White)

    Example:
        # Black vs White OSS disparity
        disparity = discipline_disparity(df, 'students_susp_out_sch_single', 2, 1)
    """
    # Filter to each group (using integer codes)
    df_a = df.filter(pl.col('race') == group_a)
    df_b = df.filter(pl.col('race') == group_b)

    # Calculate rates
    rate_a = df_a.select(pl.col(discipline_var).sum()).item() / \
             df_a.select(pl.col('enrollment_crdc').sum()).item()
    rate_b = df_b.select(pl.col(discipline_var).sum()).item() / \
             df_b.select(pl.col('enrollment_crdc').sum()).item()

    return rate_a / rate_b

# Example: Black (race=2) vs White (race=1) disparity
# disparity = discipline_disparity(df, 'students_susp_out_sch_single', 2, 1)
```

### Composition vs. Representation
- **Composition**: What share of suspended students are Black?
- **Representation**: Are Black students suspended at higher rates than enrollment share?

### Risk Ratios
- Compare discipline/outcome rates across groups
- Adjust for school-level factors when appropriate

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| **Using string codes** | Portal uses integers, not strings | `race == 2` not `race == "BL"` |
| **Raw counts** | Different enrollment sizes | Use rates per 100/1000 students |
| **Missing years** | Assuming annual data | Remember biennial schedule |
| **COVID year** | 2020-21 not comparable | Flag or exclude from trends |
| **Suppression** | Small cell suppression | Check suppression rates first |
| **Sample years** | Early years sampled | Use 2015+ for national estimates |
| **Definition drift** | Variables change over time | Check codebooks for each year |
| **Forgetting code 99** | Including totals in calculations | Filter `race < 99` for disaggregated analysis |

## Related Skills and Tools

| Resource | Use When |
|----------|----------|
| `education-data-explorer` | Finding CRDC endpoints and variables |
| `education-data-query` | Constructing API queries |
| `education-data-context` | General education data interpretation |
| CCD data | Linking to school characteristics |
| EDFacts data | Comparing to assessment outcomes |

## Topic Index

| Topic | Reference File | Section |
|-------|---------------|---------|
| Title VI (race) | `civil-rights-context.md` | Title VI |
| Title IX (sex) | `civil-rights-context.md` | Title IX |
| Section 504 (disability) | `civil-rights-context.md` | Section 504 |
| IDEA | `civil-rights-context.md` | IDEA |
| OCR enforcement | `civil-rights-context.md` | OCR Enforcement |
| Discipline data | `data-elements.md` | Discipline |
| Restraint/seclusion | `data-elements.md` | Restraint and Seclusion |
| Harassment | `data-elements.md` | Harassment |
| Course access | `data-elements.md` | Course Access |
| AP/IB/Gifted | `data-elements.md` | Advanced Courses |
| Chronic absenteeism | `data-elements.md` | Chronic Absenteeism |
| Staffing | `data-elements.md` | Staffing |
| Preschool | `data-elements.md` | Preschool |
| Sampling approach | `collection-methodology.md` | Sampling |
| Collection timeline | `collection-methodology.md` | Timeline |
| Variable codes | `variable-definitions.md` | All |
| Suppression rules | `data-quality.md` | Suppression |
| COVID impact | `data-quality.md` | COVID Impact |
| Year changes | `historical-changes.md` | All |
