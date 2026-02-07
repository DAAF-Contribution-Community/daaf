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

### Race/Ethnicity (7 categories)
- Hispanic/Latino of any race
- American Indian or Alaska Native
- Asian
- Black or African American
- Native Hawaiian or Other Pacific Islander
- White
- Two or more races

### Sex
- Male
- Female

### Disability Status
- Students with disabilities (served under IDEA)
- Students without disabilities

### English Learner Status
- English learner (EL/LEP)
- Non-English learner

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
# Calculate discipline disparity
def discipline_disparity(df, discipline_var, group_a, group_b):
    """
    Calculate risk ratio between two groups.
    Value > 1 indicates group_a has higher rate.
    """
    rate_a = df[df['race'] == group_a][discipline_var].sum() / \
             df[df['race'] == group_a]['enrollment'].sum()
    rate_b = df[df['race'] == group_b][discipline_var].sum() / \
             df[df['race'] == group_b]['enrollment'].sum()
    return rate_a / rate_b
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
| **Raw counts** | Different enrollment sizes | Use rates per 100/1000 students |
| **Missing years** | Assuming annual data | Remember biennial schedule |
| **COVID year** | 2020-21 not comparable | Flag or exclude from trends |
| **Suppression** | Small cell suppression | Check suppression rates first |
| **Sample years** | Early years sampled | Use 2015+ for national estimates |
| **Definition drift** | Variables change over time | Check codebooks for each year |

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
