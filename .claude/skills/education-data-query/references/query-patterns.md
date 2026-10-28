# Query Patterns Reference

> **LEGACY REFERENCE:** This file documents the deprecated REST API query approach using direct HTTP requests. For current mirror-based data fetching, see `fetch-patterns.md` in this skill directory. This file is retained for reference only. On 2026-10-28 its example routes were checked against the current Portal endpoint catalog (130 endpoints): 26 route forms were not in it (among them `ipeds/completions`, `ipeds/completions-cip`, `ipeds/hr`, `ipeds/sfa`, `ipeds/net-price`, `ipeds/student-services`, `ipeds/athletics`, `fsa/program-volume`, `ccd/membership` and `crdc/gifted-and-talented`); each was replaced with its catalog route where a direct equivalent exists and deleted otherwise. Do not cite the removed forms. For current routes use each family's "Portal endpoint(s)" line in `education-data-explorer`.

Comprehensive URL construction examples for the Education Data Portal API.

## URL Structure

```
https://educationdata.urban.org/api/v1/{level}/{source}/{topic}/{year}/[disaggregators]/[?filters]
```

## Schools (CCD)

### Directory

Basic school information (name, address, type, status).

```
# All schools (paginated)
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/"

# Schools in California
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=6"

# Charter schools nationwide
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?charter=1"

# Magnet schools in New York
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=36&magnet=1"

# High schools (school_level=3)
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?school_level=3"

# Elementary schools in Texas
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=48&school_level=1"

# Charter high schools in California
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=6&charter=1&school_level=3"

# Virtual schools
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?virtual=1"

# Title I eligible schools in Florida
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=12&title_i_eligible=1"

# Urban schools (urban_centric_locale 11-13)
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?urban_centric_locale=11,12,13"

# Rural schools (urban_centric_locale 41-43)
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?urban_centric_locale=41,42,43"

# Multiple states
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=6,36,48"

# Specific school by NCES ID
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?ncessch=060000000001"

# Schools in a specific district
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?leaid=0600001"

# Multiple years: one request per year (the catalog route takes {year} as a path segment)
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2018/?fips=6"
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2019/?fips=6"
```

### Enrollment

School enrollment data. **Requires grade disaggregator in path.**

```
# Total enrollment (grade-99 = all grades)
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-99/"

# Total enrollment in California
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-99/?fips=6"

# Grade 3 enrollment
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-3/"

# Kindergarten enrollment in Texas
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-pk/?fips=48"

# Grade 12 enrollment in charter schools
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-12/?charter=1"

# Enrollment by race (MUST include grade first - grade-99 for totals)
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-99/race/"

# Enrollment by race in California
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-99/race/?fips=6"

# Enrollment by sex (MUST include grade first)
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-99/sex/"

# Enrollment by race and sex (order: grade → race → sex)
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-99/race/sex/"
```

**Grade values (URL path → data column):**

| URL Path | Data Column | Description |
|----------|-------------|-------------|
| `grade-pk` | `grade = -1` | Pre-kindergarten (**SEMANTIC TRAP!**) |
| `grade-k` | `grade = 0` | Kindergarten |
| `grade-1` to `grade-12` | `grade = 1` to `12` | Grades 1-12 |
| `grade-13` | `grade = 13` | Grade 13 |
| `grade-14` | `grade = 14` | Adult education (route form inferred, not tested) |
| `grade-15` | `grade = 15` | Ungraded (route form inferred, not tested) |
| `grade-99` | `grade = 99` | Total (all grades combined) |
| (not documented) | `grade = 999` | Not specified |

**CRITICAL:** In downloaded data, `grade = -1` means Pre-K, NOT missing data!

**CRITICAL: Disaggregator Ordering Rules**

For CCD enrollment endpoints, disaggregators must follow this order:
1. `grade` (REQUIRED for race/sex disaggregation)
2. `race` (optional)
3. `sex` (optional)

Patterns that **FAIL** (return HTTP 500):
- `/enrollment/2020/race/` - Missing grade
- `/enrollment/2020/sex/` - Missing grade
- `/enrollment/2020/race/grade-99/` - Wrong order

## Schools (CRDC)

Civil Rights Data Collection - discipline, courses, staffing.

### Enrollment

```
# By disability status (and sex)
"https://educationdata.urban.org/api/v1/schools/crdc/enrollment/2017/disability/sex/"

# By race and sex
"https://educationdata.urban.org/api/v1/schools/crdc/enrollment/2017/race/sex/"

# LEP students (and sex)
"https://educationdata.urban.org/api/v1/schools/crdc/enrollment/2017/lep/sex/"
```

### Discipline

**CRITICAL: CRDC discipline endpoints require disaggregation levels in the URL path.**

```
# Discipline (requires disaggregation - use disability/sex or disability/race/sex)
"https://educationdata.urban.org/api/v1/schools/crdc/discipline/2020/disability/sex/"

# Discipline by race (must include other disaggregations)
"https://educationdata.urban.org/api/v1/schools/crdc/discipline/2020/disability/race/sex/"

# Suspensions-days endpoint
"https://educationdata.urban.org/api/v1/schools/crdc/suspensions-days/2020/race/sex/"

# Restraint and seclusion (students, by disability and sex)
"https://educationdata.urban.org/api/v1/schools/crdc/restraint-and-seclusion/2017/disability/sex/"
```

**Note:** Endpoints like `/crdc/suspensions/` and `/crdc/expulsions/` may return 404. Use `/crdc/discipline/` with disaggregation instead.

### Advanced Coursework

**CRITICAL: AP enrollment requires disaggregation in URL path.**

```
# AP/IB enrollment (requires race/sex disaggregation)
"https://educationdata.urban.org/api/v1/schools/crdc/ap-ib-enrollment/2020/race/sex/"

# Note: /crdc/ap-enrollment/ may return 404; use /crdc/ap-ib-enrollment/ instead

# AP exams
"https://educationdata.urban.org/api/v1/schools/crdc/ap-exams/2017/race/sex/"

# Algebra enrollment
"https://educationdata.urban.org/api/v1/schools/crdc/algebra1/2017/race/sex"
```

## Schools (EDFacts)

Assessment and achievement data.

```
# Assessment proficiency (2009-2018, 2020; no 2019)
"https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2018/grade-3/"

# By race
"https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2018/grade-3/race/"

# Math and reading proficiency are columns of the assessments endpoint above
# (math_test_pct_prof_*, read_test_pct_prof_*); there is no separate proficiency endpoint

# Graduation rates (EDFacts)
"https://educationdata.urban.org/api/v1/schools/edfacts/grad-rates/2019/"
```

## School Districts (CCD)

### Directory

```
# All districts
"https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2020/"

# Districts in California
"https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2020/?fips=6"

# Specific district by LEAID
"https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2020/?leaid=0600001"

```

`agency_type` is not an API filter (declared filter flag `no` in `education-data-explorer/references/variable-dictionary-ccd.md`): fetch the directory and filter locally.

### Enrollment

```
# Total district enrollment
"https://educationdata.urban.org/api/v1/school-districts/ccd/enrollment/2020/grade-99/"

# District enrollment in Texas
"https://educationdata.urban.org/api/v1/school-districts/ccd/enrollment/2020/grade-99/?fips=48"

# By grade
"https://educationdata.urban.org/api/v1/school-districts/ccd/enrollment/2020/grade-3/"

# By race (grade segment required, as for schools)
"https://educationdata.urban.org/api/v1/school-districts/ccd/enrollment/2020/grade-99/race/"

# By sex
"https://educationdata.urban.org/api/v1/school-districts/ccd/enrollment/2020/grade-99/sex/"
```

### Finance

District financial data (revenues, expenditures).

```
# All district finance data
"https://educationdata.urban.org/api/v1/school-districts/ccd/finance/2019/"

# Finance data for California districts
"https://educationdata.urban.org/api/v1/school-districts/ccd/finance/2019/?fips=6"

# Specific district finance
"https://educationdata.urban.org/api/v1/school-districts/ccd/finance/2019/?leaid=0600001"
```

## School Districts (SAIPE)

Small Area Income and Poverty Estimates.

```
# Poverty estimates for all districts
"https://educationdata.urban.org/api/v1/school-districts/saipe/2020/"

# Poverty estimates for California districts
"https://educationdata.urban.org/api/v1/school-districts/saipe/2020/?fips=6"

# Multiple years: one request per year
"https://educationdata.urban.org/api/v1/school-districts/saipe/2019/?fips=6"
```

## School Districts (EDFacts)

```
# District assessments (2009-2018, 2020; no 2019; grade segment required)
"https://educationdata.urban.org/api/v1/school-districts/edfacts/assessments/2018/grade-8/"

# District graduation rates
"https://educationdata.urban.org/api/v1/school-districts/edfacts/grad-rates/2019/"
```

## Colleges (IPEDS)

Integrated Postsecondary Education Data System.

### Directory

```
# All institutions
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/"

# Institutions in Massachusetts
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?fips=25"

# Public 4-year (sector=1)
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?sector=1"

# Private nonprofit 4-year (sector=2)
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?sector=2"

# Private for-profit 4-year (sector=3)
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?sector=3"

# Public 2-year (sector=4)
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?sector=4"

# HBCUs
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?hbcu=1"

# Tribal colleges
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?tribal_college=1"

# Degree-granting institutions
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?degree_granting=1"

# Specific institution by UNITID
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?unitid=166027"

# By control (1=public, 2=private nonprofit, 3=private for-profit)
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?inst_control=1"
```

**Sector values:**
- 0 = Administrative unit
- 1 = Public 4-year
- 2 = Private nonprofit 4-year
- 3 = Private for-profit 4-year
- 4 = Public 2-year
- 5 = Private nonprofit 2-year
- 6 = Private for-profit 2-year
- 7 = Public less-than-2-year
- 8 = Private nonprofit less-than-2-year
- 9 = Private for-profit less-than-2-year

### Enrollment

**Requires level_of_study in path.**

```
# Undergraduate FTE enrollment
"https://educationdata.urban.org/api/v1/college-university/ipeds/enrollment-full-time-equivalent/2020/undergraduate/"

# Graduate FTE enrollment
"https://educationdata.urban.org/api/v1/college-university/ipeds/enrollment-full-time-equivalent/2020/graduate/"

# Fall enrollment by race and sex
"https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/2020/undergraduate/race/sex/"

# Headcount enrollment
"https://educationdata.urban.org/api/v1/college-university/ipeds/enrollment-headcount/2020/undergraduate/"
```

### Graduation Rates

```
# Overall graduation rates (race and sex are columns; the catalog has no race route)
"https://educationdata.urban.org/api/v1/college-university/ipeds/grad-rates/2020/"

# 200% time graduation rates
"https://educationdata.urban.org/api/v1/college-university/ipeds/grad-rates-200pct/2020/"

# Pell recipient graduation rates
"https://educationdata.urban.org/api/v1/college-university/ipeds/grad-rates-pell/2020/"
```

### Admissions

```
# Admissions and test scores
"https://educationdata.urban.org/api/v1/college-university/ipeds/admissions-enrollment/2020/"

# Admissions requirements
"https://educationdata.urban.org/api/v1/college-university/ipeds/admissions-requirements/2020/"
```

### Costs and Financial Aid

```
# Academic year tuition and fees
"https://educationdata.urban.org/api/v1/college-university/ipeds/academic-year-tuition/2020/"

# Room, board, and other expenses
"https://educationdata.urban.org/api/v1/college-university/ipeds/academic-year-room-board-other/2020/"

# Student financial aid, all undergraduates (the catalog also has sfa-ftft,
# sfa-by-living-arrangement and sfa-by-tuition-type)
"https://educationdata.urban.org/api/v1/college-university/ipeds/sfa-all-undergraduates/2020/"

# Grants and net price by income
"https://educationdata.urban.org/api/v1/college-university/ipeds/sfa-grants-and-net-price/2020/"
```

### Institutional Characteristics

```
# Institutional characteristics
"https://educationdata.urban.org/api/v1/college-university/ipeds/institutional-characteristics/2020/"

# Completions (degrees awarded) by 2-digit CIP code
"https://educationdata.urban.org/api/v1/college-university/ipeds/completions-cip-2/2020/"

# Program completions by 6-digit CIP code
"https://educationdata.urban.org/api/v1/college-university/ipeds/completions-cip-6/2020/"
```

### Finance

```
# Institutional finance
"https://educationdata.urban.org/api/v1/college-university/ipeds/finance/2020/"
```

## Colleges (Scorecard)

College Scorecard data.

```
# Scorecard data
"https://educationdata.urban.org/api/v1/college-university/scorecard/earnings/2020/"

# Student loan repayment
"https://educationdata.urban.org/api/v1/college-university/scorecard/repayment/2020/"

# Default rates
"https://educationdata.urban.org/api/v1/college-university/scorecard/default/2020/"
```

## Colleges (FSA)

Federal Student Aid data.

```
# Title IV grant volume
"https://educationdata.urban.org/api/v1/college-university/fsa/grants/2020/"

# Title IV loan volume
"https://educationdata.urban.org/api/v1/college-university/fsa/loans/2020/"
```

## Combined Filters Examples

### Complex School Queries

```
# Large urban charter high schools in California
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?fips=6&charter=1&school_level=3&urban_centric_locale=11,12"

# Title I magnet elementary schools
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?title_i_eligible=1&magnet=1&school_level=1"

# Schools in specific districts (multiple LEAIDs)
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2020/?leaid=0600001,0600002,0600003"
```

### Complex College Queries

```
# HBCUs with high graduation rates (need to filter after fetch)
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?hbcu=1"

# Public research universities in multiple states
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?sector=1&fips=6,36,48"

# Community colleges in California
"https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2020/?fips=6&sector=4"
```

### Time Series Queries

```
# California schools across multiple years: one request per year, 2015 through 2020
"https://educationdata.urban.org/api/v1/schools/ccd/directory/2015/?fips=6"

# Enrollment trends: one request per year, 2015 through 2020
"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2015/grade-99/?fips=6"
```

## Note on Data Fetching

URL patterns in this file document the endpoint path structure of the Education Data Portal.
For actual data fetching, use the mirror-based patterns in `./fetch-patterns.md` — no direct
API calls are used. These URL patterns remain useful for understanding dataset naming conventions.
