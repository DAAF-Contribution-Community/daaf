# IPEDS Survey Components

Complete reference for all IPEDS survey components, their collection periods, data content, and key variables.

## Contents

- [Collection Schedule](#collection-schedule)
- [Fall Collection](#fall-collection)
- [Winter Collection](#winter-collection)
- [Spring Collection](#spring-collection)
- [Data Release Schedule](#data-release-schedule)

## Collection Schedule

IPEDS collects data in three periods annually. Each collection opens ~2 months before the due date.

| Collection | Opens | Closes | Data Release |
|------------|-------|--------|--------------|
| Fall | August | October | Following September |
| Winter | December | February | Following December |
| Spring | December | April | Following January |

## Fall Collection

### Institutional Characteristics (IC)

The foundational survey that must be completed first. Establishes institution identity.

**Collection Period**: August-October

**Data Collected**:
- Institution name, address, website
- Control (public/private nonprofit/private for-profit)
- Highest degree offered
- Carnegie classification
- Calendar system (semester/quarter/trimester)
- Student services offered
- Special institutional characteristics (HBCU, tribal, women's, religious)
- Open admission policy
- Tuition and fees
- Room and board charges

**Key Variables**:

| Variable | Description | Values |
|----------|-------------|--------|
| `unitid` | Unique institution ID | 6-digit integer |
| `instnm` | Institution name | Text |
| `addr` | Street address | Text |
| `city` | City | Text |
| `stabbr` | State abbreviation | 2-letter |
| `fips` | State FIPS code | Integer |
| `zip` | ZIP code | Text |
| `control` | Institutional control | 1=Public, 2=Private NP, 3=Private FP |
| `iclevel` | Level of institution | 1=4-yr, 2=2-yr, 3=<2-yr |
| `hloffer` | Highest level of offering | 1-9 scale |
| `ugoffer` | Undergraduate offering | 1=Yes, 0=No |
| `groffer` | Graduate offering | 1=Yes, 0=No |
| `hdegofr1` | Highest degree offered | 0-24 scale |
| `deggrant` | Degree-granting status | 1=Yes, 0=No |
| `hbcu` | HBCU indicator | 1=Yes, 2=No |
| `hospital` | Has hospital | 1=Yes, 2=No |
| `medical` | Grants medical degree | 1=Yes, 2=No |
| `tribal` | Tribal college | 1=Yes, 2=No |
| `locale` | Urban-centric locale code | 11-43 |
| `openpubl` | Open to general public | 1=Yes, 2=No |
| `obereg` | Bureau of Economic Analysis region | 0-8 |
| `ccbasic` | Carnegie basic classification | Integer codes |
| `tuition1_in` | In-state tuition | Dollar amount |
| `tuition2_in` | In-state required fees | Dollar amount |
| `tuition3_in` | In-state per credit hour | Dollar amount |
| `tuition1_out` | Out-of-state tuition | Dollar amount |
| `roomcap` | Room capacity | Integer |
| `roomamt` | Room charges | Dollar amount |
| `boardamt` | Board charges | Dollar amount |
| `applfeeu` | Application fee (undergrad) | Dollar amount |
| `applfeeg` | Application fee (graduate) | Dollar amount |

### 12-Month Enrollment (E12)

Provides unduplicated headcount for the full academic year.

**Collection Period**: August-October (for prior academic year)

**Data Collected**:
- Unduplicated headcount by level, race/ethnicity, gender
- Instructional activity (credit/contact hours)
- Full-time equivalent (FTE) enrollment

**Key Variables**:

| Variable | Description |
|----------|-------------|
| `efytotlt` | Total 12-month enrollment |
| `efytotlm` | Male 12-month enrollment |
| `efytotlw` | Female 12-month enrollment |
| `efyug` | Undergraduate 12-month enrollment |
| `efygr` | Graduate 12-month enrollment |
| `fteug` | Undergraduate FTE |
| `ftegr` | Graduate FTE |
| `fte` | Total FTE |
| `efyaiant` | American Indian/Alaska Native |
| `efyasiat` | Asian |
| `efybkaat` | Black or African American |
| `efyhispt` | Hispanic/Latino |
| `efynhpit` | Native Hawaiian/Pacific Islander |
| `efywhitt` | White |
| `efy2mort` | Two or more races |
| `efyunknt` | Race/ethnicity unknown |
| `efynralt` | Nonresident alien |

**FTE Calculation Methods**:

Credit hour institutions:
- Undergrad FTE = (FT undergrad) + (PT undergrad credit hours / 30)
- Graduate FTE = (FT grad) + (PT grad credit hours / 24)

Clock hour institutions:
- FTE = Total contact hours / 900

### Completions (C)

Degrees and certificates awarded during the academic year.

**Collection Period**: August-October

**Data Collected**:
- Completions by CIP code, award level, race/ethnicity, gender
- Completers (unduplicated count of individuals)
- Distance education program indicator

**Award Levels**:

| Code | Award Level |
|------|-------------|
| 1 | Postsecondary certificate (<1 year) |
| 2 | Postsecondary certificate (1-2 years) |
| 3 | Associate's degree |
| 4 | Postsecondary certificate (2-4 years) |
| 5 | Bachelor's degree |
| 6 | Postbaccalaureate certificate |
| 7 | Master's degree |
| 8 | Post-master's certificate |
| 17 | Doctor's degree - research/scholarship |
| 18 | Doctor's degree - professional practice |
| 19 | Doctor's degree - other |

**CIP Code Structure**:
- 2-digit: General field (e.g., 52 = Business)
- 4-digit: More specific (e.g., 52.02 = Business Administration)
- 6-digit: Most specific (e.g., 52.0201 = Business Administration and Management)

### Cost (CST)

New component (2024-25) - Cost of attendance and net price data.

**Collection Period**: Fall and Winter

**Data Collected**:
- Published cost of attendance
- Net price by income level
- Books and supplies estimates
- Other expenses

## Winter Collection

### Admissions (ADM)

Application and admissions data for degree-granting institutions.

**Collection Period**: December-February

**Data Collected**:
- Applications received (men/women)
- Applicants admitted (men/women)
- Admitted students who enrolled (men/women)
- SAT/ACT score ranges (25th-75th percentile)
- Admission considerations (test scores, GPA, etc.)

**Key Variables**:

| Variable | Description |
|----------|-------------|
| `applcn` | Total applicants |
| `applcnm` | Male applicants |
| `applcnw` | Female applicants |
| `admssn` | Total admitted |
| `enrlt` | Total enrolled |
| `enrlft` | Enrolled full-time |
| `enrlpt` | Enrolled part-time |
| `satpct` | Percent submitting SAT |
| `actpct` | Percent submitting ACT |
| `satvr25` | SAT Verbal 25th percentile |
| `satvr75` | SAT Verbal 75th percentile |
| `satmt25` | SAT Math 25th percentile |
| `satmt75` | SAT Math 75th percentile |
| `actcm25` | ACT Composite 25th percentile |
| `actcm75` | ACT Composite 75th percentile |
| `admcon1`-`admcon9` | Admission considerations |

**Admission Rate Calculation**:
```
Admission rate = admssn / applcn
Yield rate = enrlt / admssn
```

### Student Financial Aid (SFA)

Financial aid awarded to students.

**Collection Period**: December-February

**Data Collected**:
- Number receiving aid by type
- Total amount awarded by type
- Military education benefits recipients

**Key Populations**:

| Population | Description |
|------------|-------------|
| All undergraduates | All enrolled undergrads |
| Full-time first-time | FTFT degree-seeking |
| All degree/certificate-seeking | Excludes non-degree |

**Aid Categories**:

| Category | Description |
|----------|-------------|
| Any aid | Any type of financial aid |
| Grant/scholarship | Gift aid (no repayment) |
| Federal grants | Pell, SEOG, other federal |
| State/local grants | State need-based, merit |
| Institutional grants | Institution-funded |
| Federal loans | Direct subsidized, unsubsidized, PLUS |

### Graduation Rates (GR)

See `graduation-rates.md` for complete details.

**Collection Period**: December-February

**Key Data**:
- 150% time completion rates
- Cohort counts by race/ethnicity, gender
- Pell/Stafford loan recipient rates
- Transfer-out counts

### Graduation Rates 200% (GR200)

Extended completion tracking.

**Collection Period**: December-February

**Data Collected**:
- 200% time completion rates
- Additional completers beyond 150% window

**Time Windows**:

| Institution Type | 150% Time | 200% Time |
|-----------------|-----------|-----------|
| 4-year | 6 years | 8 years |
| 2-year | 3 years | 4 years |
| Less-than-2-year | Varies | Varies |

### Outcome Measures (OM)

Expanded success metrics including part-time and transfer students.

**Collection Period**: December-February

**Cohort Groups** (unlike GR, includes more students):
1. First-time, full-time entering
2. First-time, part-time entering
3. Non-first-time, full-time entering (transfers)
4. Non-first-time, part-time entering

**Outcomes Tracked at 8 years**:
- Award at reporting institution
- Award at another institution
- Still enrolled at reporting institution
- Still enrolled elsewhere
- No longer enrolled anywhere

**Key Advantage**: Tracks students IPEDS graduation rates miss.

## Spring Collection

### Fall Enrollment (EF)

Point-in-time enrollment snapshot.

**Collection Period**: December-April (for previous fall)

**Data Collected**:
- Enrollment by level, attendance status, race/ethnicity, gender
- First-time student residence (even years)
- Enrollment by age (odd years)
- Retention rates
- Student-to-faculty ratio
- Distance education enrollment

**Key Variables**:

| Variable | Description |
|----------|-------------|
| `effall` | Total fall enrollment |
| `efft` | Full-time enrollment |
| `efpt` | Part-time enrollment |
| `efug` | Undergraduate enrollment |
| `efgr` | Graduate enrollment |
| `ret_pcf` | Full-time retention rate |
| `ret_pcp` | Part-time retention rate |
| `stufacr` | Student-to-faculty ratio |
| `efdeexc` | Distance ed exclusively |
| `efdesom` | Distance ed some but not all |
| `efdenom` | Not enrolled in distance ed |

**Enrollment Categories**:

| Category | Definition |
|----------|------------|
| First-time | Never attended college before |
| Transfer | Previously attended another institution |
| Continuing | Enrolled previous year at same institution |
| Graduate | Master's, doctoral, professional |
| Non-degree | Not in a degree program |

### Finance (F)

Institutional finances - see `finance-data.md` for GASB/FASB details.

**Collection Period**: December-April

**Data Collected**:
- Revenues by source
- Expenses by function and natural classification
- Assets and liabilities
- Scholarships and fellowships
- Endowment and investments

### Human Resources (HR)

Employees and compensation.

**Collection Period**: December-April

**Data Collected**:
- Employees by occupational category
- Full-time and part-time counts
- Faculty counts by rank and tenure status
- Salaries for full-time instructional staff
- New hires
- Employees by race/ethnicity and gender

**Occupational Categories**:
- Instruction (faculty)
- Research
- Public service
- Librarians
- Student and academic affairs
- Management
- Business and financial operations
- Computer, engineering, and science
- Community service, legal, arts, and media
- Healthcare practitioners
- Service occupations
- Sales and office
- Natural resources, construction, and maintenance
- Production, transportation, and material moving

### Academic Libraries (AL)

Library resources and services. **Collected biennially**.

**Collection Period**: December-April (odd years)

**Data Collected**:
- Library expenditures
- Collections (physical and digital)
- Circulation
- Interlibrary loans

## Data Release Schedule

Data releases occur in three types:

| Release Type | Timing | Use Case |
|--------------|--------|----------|
| Provisional | Shortly after collection closes | Initial analysis |
| Final | ~6 months after provisional | Most analysis |
| Revised | As needed | Corrections |

**Typical Release Calendar**:

| Collection | Provisional | Final |
|------------|-------------|-------|
| Fall 2024 | September 2025 | March 2026 |
| Winter 2024-25 | December 2025 | June 2026 |
| Spring 2025 | January 2026 | July 2026 |

## Title IV Requirement

All institutions participating in Title IV federal student financial aid programs are required to report IPEDS data. This includes:

- Pell Grant program
- Federal Direct Loans
- Federal Work-Study
- Federal Supplemental Educational Opportunity Grant (SEOG)
- Federal Perkins Loan (discontinued)
- TEACH Grant

**Non-Title IV institutions** are not in IPEDS (e.g., some religious institutions, purely non-credit vocational schools).

## Survey Response Rates

IPEDS achieves ~99% response rate because:
1. Reporting is mandatory for Title IV participation
2. Non-response can result in fine and loss of Title IV eligibility
3. Extensive follow-up by NCES

Imputation is used for remaining missing data.
