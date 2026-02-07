---
name: education-data-source-ccd
description: Deep reference for the Common Core of Data (CCD), the US Department of Education's primary database on public K-12 education. Use when working with CCD data to understand survey components, variable definitions, data quality issues, historical changes, and state-level variations. Essential for interpreting enrollment, staffing, finance, and directory data from public schools and districts.
metadata:
  audience: data-analysts
  domain: education-data
---

# Common Core of Data (CCD) Source Reference

The CCD is the Department of Education's comprehensive, annual, national database of all public elementary and secondary schools and school districts in the United States. This skill provides deep context for working with CCD data.

## What is CCD?

- **Primary K-12 database**: DOE's authoritative source for public elementary/secondary education statistics
- **Universe survey**: Covers ALL public schools and districts, not a sample
- **Annual collection**: Data submitted by State Education Agencies (SEAs) each year
- **Six major components**: Directory, Membership, Staffing, Finance (state and district), Dropout/Completers
- **Coverage**: ~100,000 public schools and ~18,000 school districts nationwide
- **Historical depth**: Data available from 1986 to present (varies by component)
- **Collector**: National Center for Education Statistics (NCES) via EDFacts

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `survey-components.md` | Detailed coverage of each CCD survey component | Understanding what data is collected |
| `data-collection.md` | How data flows from schools to NCES, timelines, respondent universe | Understanding data provenance and timing |
| `variable-definitions.md` | Key variables, coding schemes, special values | Interpreting specific data elements |
| `data-quality.md` | Missing data patterns, suppression, state variations | Assessing data reliability |
| `historical-changes.md` | Definition changes, code revisions over time | Longitudinal analysis |

## Decision Trees

### What CCD component do I need?

```
What information do you need?
├─ School/district names, addresses, contacts → Directory
│   └─ See ./references/survey-components.md#directory
├─ Student enrollment counts → Membership
│   ├─ By grade → Membership (grade disaggregation)
│   ├─ By race/ethnicity → Membership (race disaggregation)
│   ├─ By sex → Membership (sex disaggregation)
│   └─ See ./references/survey-components.md#membership
├─ Staff/teacher counts → Staffing
│   └─ See ./references/survey-components.md#staffing
├─ Revenue and expenditure → Finance
│   ├─ State-level totals → National Public Education Financial Survey
│   ├─ District-level detail → School District Finance Survey (F-33)
│   └─ See ./references/survey-components.md#finance
├─ Graduation/dropout rates → Dropout and Completers
│   └─ See ./references/survey-components.md#dropout-completers
└─ School type, charter status, locale → Directory
    └─ See ./references/survey-components.md#directory
```

### Is this a data quality issue?

```
Unexpected data values?
├─ Negative numbers (-1, -2, -3, -9) → Missing data codes
│   └─ See ./references/variable-definitions.md#missing-data-codes
├─ Very different from prior year → Check for definition changes
│   └─ See ./references/historical-changes.md
├─ State appears as outlier → Check state-specific reporting
│   └─ See ./references/data-quality.md#state-variations
├─ Large number of zeros → Check suppression rules
│   └─ See ./references/data-quality.md#suppression
└─ Locale codes don't match → Pre/post 2006 locale system change
    └─ See ./references/historical-changes.md#locale-codes
```

### Can I compare across time?

```
Building a time series?
├─ Race/ethnicity categories → Major change in 2010
│   └─ See ./references/historical-changes.md#race-ethnicity
├─ Locale codes → Completely revised in 2006
│   └─ See ./references/historical-changes.md#locale-codes
├─ School/district IDs → Check for ID changes
│   └─ See ./references/variable-definitions.md#identifiers
├─ Free/reduced lunch → CEP and direct certification changes
│   └─ See ./references/data-quality.md#frpl
└─ Finance data → Definition changes and inflation
    └─ See ./references/historical-changes.md#finance
```

## Quick Reference: CCD Components

| Component | Level | Key Variables | Years | Update Cycle |
|-----------|-------|---------------|-------|--------------|
| Directory | School, LEA, State | Name, address, type, status, locale, charter | 1986+ | Annual |
| Membership | School, LEA, State | Enrollment by grade, race, sex | 1986+ | Annual |
| Staffing | School, LEA, State | FTE teachers, staff by category | 1987+ | Annual |
| Finance (State) | State | Revenue, expenditure by source/function | 1989+ | Annual (1-2 yr lag) |
| Finance (District) | LEA | Revenue, expenditure, per-pupil | 1989+ | Annual (2 yr lag) |
| Dropout/Completers | LEA, State | Dropout counts, diploma recipients | 1991+ | Annual |

## Quick Reference: Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `NCESSCH` | 12 characters | School | `010000100100` | State FIPS (2) + LEA suffix (5) + School (5) |
| `LEAID` | 7 characters | District | `0100001` | State FIPS (2) + State-assigned (5) |
| `FIPS` | 2 digits | State | `01` | Federal Information Processing Standard |

## Quick Reference: Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing | Data not reported by state |
| `-2` | Not applicable | Item doesn't apply to this entity |
| `-3` | Suppressed | Data suppressed for privacy |
| `-9` | Not reported | State did not report this item |

## Quick Reference: School Types

| Code | Type | Description |
|------|------|-------------|
| 1 | Regular | Standard public school |
| 2 | Special Education | Focuses on students with disabilities |
| 3 | Vocational | Career/technical education focus |
| 4 | Alternative | Non-traditional programs |
| 5 | Reportable Program | Program within another school (2007-08+) |

## Quick Reference: LEA Types

| Code | Type | Description |
|------|------|-------------|
| 1 | Regular | Locally governed school district |
| 2 | Component | District sharing superintendent with others |
| 3 | Supervisory Union | Admin services for multiple districts |
| 4 | Regional Agency | Education service agency |
| 5 | State-operated | State-run schools (deaf, blind, correctional) |
| 6 | Federal-operated | Federal schools (BIE, DoDEA) |
| 7 | Charter Agency | All schools are charters (2007-08+) |
| 8 | Other | Doesn't fit other categories (2007-08+) |

## Data Collection Flow

```
Schools → Local Education Agencies (LEAs)
                ↓
    State Education Agencies (SEAs)
                ↓
        EDFacts Submission System
                ↓
    NCES Quality Review & Editing
                ↓
        CCD Public Data Files
```

**Timeline**: Data for school year 20XX-YY typically submitted spring 20YY, released fall 20YY (preliminary) to spring 20YY+1 (provisional/final).

## Coverage Notes

### What CCD Includes

- All public schools (traditional, charter, magnet, alternative)
- All public school districts and LEAs
- Bureau of Indian Education (BIE) schools
- Department of Defense Education Activity (DoDEA) schools
- State-operated schools (deaf, blind, correctional)

### What CCD Excludes

- Private schools (use Private School Universe Survey - PSS)
- Homeschool students
- Postsecondary institutions (use IPEDS)
- Detailed student-level data (CCD is aggregate only)

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Summing grades | Misses ungraded students | Use grade=-99 (total) instead |
| Cross-state comparison | Different state definitions | Check state methodology first |
| Using FRPL as poverty measure | CEP schools show 100% | Supplement with SAIPE data |
| Locale time series | 2006 code system change | Analyze pre/post-2006 separately |
| Charter school counts | Early years incomplete | Verify against state records pre-2010 |
| Dropout rate comparison | State definitions vary | Within-state comparisons only |

## Related Data Sources

| Source | Relationship to CCD | Use When |
|--------|---------------------|----------|
| EDFacts | CCD nonfiscal data flows through EDFacts | Same underlying data |
| CRDC | Biennial; uses CCD school IDs | Need discipline, course access, equity data |
| SAIPE | Uses CCD district IDs | Need poverty estimates (better than FRPL) |
| IPEDS | Separate system for postsecondary | Need college/university data |
| PSS | Private school equivalent | Need private school data |
| NHGIS | Census geography crosswalks | Need school-Census links |

## Education Data Portal Mapping

In the Urban Institute Education Data Portal:

| Portal Endpoint | CCD Component |
|-----------------|---------------|
| `/schools/ccd/directory/` | School Directory |
| `/schools/ccd/enrollment/` | School Membership |
| `/school-districts/ccd/directory/` | LEA Directory |
| `/school-districts/ccd/enrollment/` | LEA Membership |
| `/school-districts/ccd/finance/` | F-33 District Finance |

## Education Data Portal API Patterns

> **API Implementation:** For URL construction patterns, pagination, and error handling, see the `education-data-query` skill. For comprehensive API learnings, see `agent_reference/EDUCATION_DATA_API_LEARNINGS.md`.

### CRITICAL: Enrollment Disaggregator Rules

For CCD enrollment endpoints, the `grade` disaggregator is **REQUIRED** and must come **FIRST** in the URL path.

| Pattern | Status |
|---------|--------|
| `/enrollment/{year}/grade-99/` | ✅ Works (totals) |
| `/enrollment/{year}/grade-99/race/` | ✅ Works |
| `/enrollment/{year}/grade-99/race/sex/` | ✅ Works |
| `/enrollment/{year}/race/` | ❌ HTTP 500 (missing grade) |
| `/enrollment/{year}/race/grade-99/` | ❌ HTTP 500 (wrong order) |

Use `grade-99` to get totals across all grades.

**Example correct URL:**
```
/api/v1/schools/ccd/enrollment/2022/grade-99/?fips=6
```

### Finance Field Names

API field names include `_total` suffix (not documented):

| Documented | Actual API Field |
|------------|------------------|
| `exp_current_instruction` | `exp_current_instruction_total` |

**Finance data lag:** As of January 2026, latest available year is **2020** (not 2021).

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Directory survey | `./references/survey-components.md` |
| Membership survey | `./references/survey-components.md` |
| Staffing survey | `./references/survey-components.md` |
| Finance surveys | `./references/survey-components.md` |
| Dropout/completers | `./references/survey-components.md` |
| Data collection process | `./references/data-collection.md` |
| EDFacts submission | `./references/data-collection.md` |
| Respondent universe | `./references/data-collection.md` |
| NCES identifiers | `./references/variable-definitions.md` |
| Missing data codes | `./references/variable-definitions.md` |
| Grade codes | `./references/variable-definitions.md` |
| Race/ethnicity codes | `./references/variable-definitions.md` |
| Locale codes | `./references/variable-definitions.md` |
| State-level variations | `./references/data-quality.md` |
| Missing data patterns | `./references/data-quality.md` |
| FRPL limitations | `./references/data-quality.md` |
| Data suppression | `./references/data-quality.md` |
| Locale code changes (2006) | `./references/historical-changes.md` |
| Race/ethnicity changes (2010) | `./references/historical-changes.md` |
| LEA type changes (2007) | `./references/historical-changes.md` |
| ID changes over time | `./references/historical-changes.md` |
