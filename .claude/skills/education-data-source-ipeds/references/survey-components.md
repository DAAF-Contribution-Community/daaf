# IPEDS Survey Components

Complete reference for all IPEDS survey components, their collection periods, data content, and key variables.

> **IMPORTANT: NCES vs Portal Variable Names.** Many variable names in this file are from NCES survey documentation (e.g., `instnm`, `stabbr`, `applcn`, `eftotlt`). The Portal uses different, descriptive lowercase names (e.g., `inst_name`, `state_abbr`, `number_applied`, `enrollment_fall`). Always verify actual column names by inspecting the downloaded data or consulting the codebook. See `SKILL.md` for common NCES-to-Portal mappings, and use `get_codebook_url()` from `fetch-patterns.md` to download codebooks.

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
| Fall | August–early September (2024-25: Sept 4) | Mid-October | Following summer (2025-26 Fall: July 28, 2026) |
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
- Tuition and fees (through 2023-24; moved to the Cost (CST) component from 2024-25)
- Room and board charges (through 2023-24; moved to the Cost (CST) component from 2024-25)

**Key Variables** (NCES names shown; Portal uses different names — see note at top):

| NCES Variable | Portal Variable | Description | Values |
|---------------|-----------------|-------------|--------|
| `unitid` | `unitid` | Unique institution ID | 6-digit integer |
| `instnm` | `inst_name` | Institution name | Text |
| `addr` | `address` | Street address | Text |
| `city` | `city` | City | Text |
| `stabbr` | `state_abbr` | State abbreviation | 2-letter |
| `fips` | `fips` | State FIPS code | Integer |
| `zip` | `zip` | ZIP code | Text |
| `control` | `inst_control` | Institutional control | 1=Public, 2=Private NP, 3=Private FP |
| `iclevel` | `institution_level` | Level of institution | 1=<2-yr, 2=2-yr, 4=4-yr+ |
| `hloffer` | `offering_highest_level` | Highest level of offering | Integer |
| `ugoffer` | `offering_undergrad` | Undergraduate offering | 1=Yes, 0=No |
| `groffer` | `offering_grad` | Graduate offering | 1=Yes, 0=No |
| `hdegofr1` | `offering_highest_degree` | Highest degree offered | Integer |
| `deggrant` | `degree_granting` | Degree-granting status | 1=Yes, 0=No |
| `hbcu` | `hbcu` | HBCU indicator | 1=Yes, 0=No |
| `hospital` | `hospital` | Has hospital | 1=Yes |
| `medical` | `medical_degree` | Grants medical degree | 1=Yes |
| `tribal` | `tribal_college` | Tribal college | 1=Yes, 0=No |
| `locale` | `urban_centric_locale` | Urban-centric locale code | 11-43 |
| `openpubl` | `open_public` | Open to general public | Integer |
| `obereg` | `region` | Bureau of Economic Analysis region | 0-8 |
| `ccbasic` | `cc_basic_2021` | Carnegie basic classification (2021) | See codebook |

> **Note on `institution_level`:** The Portal uses codes 1, 2, 4 (NOT 1, 2, 3). There is no code 3. This differs from the `iclevel` NCES values where 1=4-yr, 2=2-yr, 3=<2-yr.

> **Note on `hbcu` and `tribal_college`:** The Portal uses 0=No, 1=Yes (not 2=No as in some NCES documentation). Both also have -1=Missing.

### 12-Month Enrollment (E12)

Provides unduplicated headcount for the full academic year.

**Collection Period**: August-October (for prior academic year)

**Data Collected**:
- Unduplicated headcount by level, race/ethnicity, gender
- Instructional activity (credit/contact hours)
- Full-time equivalent (FTE) enrollment

**Portal Dataset**: `enrollment-fte` (path: `ipeds/colleges_ipeds_enrollment-fte`)

> **Structural Note:** The Portal transforms E12 data from the NCES wide format (one column per demographic group, e.g., `efytotlt`, `efyug`) into a **long/tidy format** with dimension columns + measure columns. There are no separate columns for race/ethnicity breakdowns; instead, those are available in the `headcount` dataset which uses `race` and `sex` dimension columns.

**Portal Variables** (`enrollment-fte` dataset, 9 columns):

| Portal Variable | Type | Description | Values |
|-----------------|------|-------------|--------|
| `unitid` | Int64 | Unique institution ID | 6-digit integer |
| `year` | Int64 | Academic year | 1997-2021 |
| `fips` | Int64 | State FIPS code | Integer |
| `level_of_study` | Int64 | Level of study | 1=Undergraduate, 2=Graduate, 3=First Professional |
| `acttype` | Int64 | Instructional activity type | 1=Credit hours, 2=Contact hours, 3=Both; -2=Not applicable |
| `credit_hours` | Int64 | Total credit hours | Integer |
| `contact_hours` | Int64 | Total contact hours | Integer |
| `est_fte` | Int64 | Estimated FTE enrollment | Integer |
| `rep_fte` | Int64 | Reported FTE enrollment | Integer |

> **NCES-to-Portal mapping:** The NCES variables `efytotlt`, `efyug`, `efygr`, `fteug`, `ftegr`, `fte` (wide-format totals/subtotals) do not exist as separate columns. To get undergraduate FTE, filter `level_of_study == 1` and read `est_fte` or `rep_fte`. For 12-month enrollment headcounts by race/ethnicity and sex, use the separate `headcount` dataset (`ipeds/colleges_ipeds_headcount`), which has `headcount`, `level_of_study`, `race`, and `sex` dimension columns.

**FTE Calculation Methods**:

**12-month FTE (E12)**: total 12-month instructional activity ÷ a standard full-time load. For semester-calendar institutions, undergraduate credit hours ÷ 30 and graduate credit hours ÷ 24 (Portal enrollment-full-time-equivalent documentation). Divisors differ for quarter-calendar and clock-hour reporting; check the E12 instructions for the reporting year. Institutions may report their own FTE instead (`rep_fte` vs derived `est_fte`).

### Completions (C)

Degrees and certificates awarded during the academic year.

**Collection Period**: August-October

**Data Collected**:
- Completions by CIP code, award level, race/ethnicity, gender
- Completers (unduplicated count of individuals)
- Distance education program indicator

**Award Levels** (NCES `AWLEVEL` codes used in NCES raw files — NOT the Portal `award_level` codes; for Portal codes see `completions-data.md` § Award Levels):

| NCES `AWLEVEL` Code | Award Level |
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

**Key Variables** (Portal `admissions-enrollment` dataset):

| Portal Variable | NCES Name | Description |
|-----------------|-----------|-------------|
| `number_applied` | `APPLCN` | Total applicants |
| `number_admitted` | `ADMSSN` | Total admitted |
| `number_enrolled_total` | `ENRLT` | Total enrolled |
| `number_enrolled_ft` | `ENRLFT` | Enrolled full-time |
| `number_enrolled_pt` | `ENRLPT` | Enrolled part-time |
| `sex` | — | Sex (1=Male, 2=Female, 3=Nonbinary, 9=Unknown, 99=Total) |

> **Note:** The Portal `admissions-enrollment` dataset has only 9 columns: `unitid`, `year`, `fips`, `sex`, `number_applied`, `number_admitted`, `number_enrolled_ft`, `number_enrolled_pt`, `number_enrolled_total`. SAT/ACT scores are in the separate `admissions-requirements` dataset.

**Admission Rate Calculation**:
```python
# Filter to totals first (sex == 99)
admit_rate = number_admitted / number_applied
yield_rate = number_enrolled_total / number_admitted
```

```r
# Filter to totals first (sex == 99)
admit_rate <- number_admitted / number_applied
yield_rate <- number_enrolled_total / number_admitted
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

Beginning with the 2017-18 collection, each cohort is further split by Pell Grant recipient status (eight cohorts; Portal `year` ≥ 2016).

**Outcomes Tracked at 8 years**:
- Received award
- Did not receive award, still enrolled at reporting institution
- Did not receive award, subsequently enrolled at another institution
- Did not receive award, subsequent enrollment status unknown

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

> **Structural Note:** The Portal splits the NCES Fall Enrollment survey into **six separate datasets**, each in long/tidy format with dimension columns + a single measure column. The NCES wide-format variables (e.g., `effall`, `efft`, `efug`) do not exist as separate columns. Instead, filter on dimension columns (`ftpt`, `level_of_study`, `sex`, `race`, etc.) to get the desired subpopulation counts.

**Portal Datasets** (all Spring Collection, reported for previous fall):

| Portal Dataset | Path | Rows | Cols | Key Measure | Dimensions |
|----------------|------|------|------|-------------|------------|
| Fall Enrollment (Race) | `ipeds/colleges_ipeds_fall-enrollment-race_{year}` | ~3.5M/yr | 10 | `enrollment_fall` | `sex`, `race`, `ftpt`, `level_of_study`, `degree_seeking`, `class_level` |
| Fall Enrollment (Age) | `ipeds/colleges_ipeds_fall-enrollment-age_{year}` | ~1.2M/yr | 9 | `enrollment_fall` | `sex`, `age`, `ftpt`, `level_of_study`, `degree_seeking` |
| Fall Enrollment (Residence) | `ipeds/colleges_ipeds_fall-res` | 3.1M total | 6 | `enrollment_fall` | `state_of_residence`, `type_of_freshman` |
| Enrollment Headcount | `ipeds/colleges_ipeds_headcount` | 9.6M total | 7 | `headcount` | `level_of_study`, `race`, `sex` |
| Fall Retention | `ipeds/colleges_ipeds_fall-retention` | 325K total | 9 | `retention_rate` | `ftpt` |
| Student-Faculty Ratio | `ipeds/colleges_ipeds_student-faculty-ratio` | 80K total | 4 | `student_faculty_ratio` | (none — one row per institution-year) |

**Fall Enrollment (Race) Variables** (yearly dataset, 10 columns):

| Portal Variable | Type | Description | Values |
|-----------------|------|-------------|--------|
| `unitid` | Int64 | Unique institution ID | 6-digit integer |
| `year` | Int64 | Fall term year | 1986-2022 |
| `fips` | Int64 | State FIPS code | Integer |
| `sex` | Int64 | Sex | 1=Male, 2=Female, 99=Total |
| `race` | Int64 | Race/ethnicity | 1-9=Individual groups, 99=Total |
| `ftpt` | Int64 | Full-time/part-time | 1=Full-time, 2=Part-time, 99=Total |
| `level_of_study` | Int64 | Level of study | 1=Undergraduate, 2=Graduate, 99=Total |
| `degree_seeking` | Int64 | Degree-seeking status | 0=Non-degree, 1=Degree-seeking, 99=Total |
| `class_level` | Int64 | Class level | 1=First-year, 2=Second-year, 3=Third-year, 4=Fourth-year+, 99=Total |
| `enrollment_fall` | Int64 | Fall enrollment count | Integer |

**Fall Retention Variables** (single-file, 10 columns):

| Portal Variable | Type | Description | Values |
|-----------------|------|-------------|--------|
| `unitid` | Int64 | Unique institution ID | 6-digit integer |
| `year` | Int64 | Year | 2003-2020 |
| `fips` | Int64 | State FIPS code | Integer |
| `ftpt` | Int64 | Full-time/part-time | 1=Full-time, 2=Part-time, 99=Total |
| `retention_rate` | Float64 | Retention rate | Percentage |
| `returning_students` | String | Number returning | String (may contain suppression markers) |
| `prev_cohort` | String | Previous year cohort size | String |
| `prev_inclusions` | String | Additions to cohort | String (live-verified 2026-08-07; undocumented in prior Portal codebook — consult the sfa/retention codebook for exact meaning) |
| `prev_exclusions` | String | Exclusions from cohort | String |
| `prev_cohort_adj` | String | Adjusted cohort | String |

**NCES-to-Portal Mapping:**

| NCES Variable | Portal Equivalent | How to Derive |
|---------------|-------------------|---------------|
| `effall` (total fall enrollment) | `enrollment_fall` | Filter `fall-enrollment-race`: `sex==99`, `race==99`, `ftpt==99`, `level_of_study==99` |
| `efft` (full-time enrollment) | `enrollment_fall` | Filter: `ftpt==1`, `sex==99`, `race==99`, `level_of_study==99` |
| `efpt` (part-time enrollment) | `enrollment_fall` | Filter: `ftpt==2`, `sex==99`, `race==99`, `level_of_study==99` |
| `efug` (undergrad enrollment) | `enrollment_fall` | Filter: `level_of_study==1`, `sex==99`, `race==99`, `ftpt==99` |
| `efgr` (graduate enrollment) | `enrollment_fall` | Filter: `level_of_study==2`, `sex==99`, `race==99`, `ftpt==99` |
| `ret_pcf` (FT retention rate) | `retention_rate` | Filter `fall-retention`: `ftpt==1` |
| `ret_pcp` (PT retention rate) | `retention_rate` | Filter `fall-retention`: `ftpt==2` |
| `stufacr` (student-faculty ratio) | `student_faculty_ratio` | Direct column in `student-faculty-ratio` dataset |
| `efdeexc` (distance ed exclusively) | — | Not available as a separate Portal dataset column |
| `efdesom` (distance ed some) | — | Not available as a separate Portal dataset column |
| `efdenom` (not distance ed) | — | Not available as a separate Portal dataset column |

> **Note:** Distance education enrollment variables (`efdeexc`, `efdesom`, `efdenom`) are not in the Portal mirror datasets. These are available in the NCES IPEDS Data Center directly.

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

**Portal Dataset**: `finance` (path: `ipeds/colleges_ipeds_finance`)

> **Structural Note:** Unlike E12 and EF, the Portal finance dataset keeps a **wide format** with 141 descriptive column names. The Portal replaces NCES form-field codes (e.g., `f1a01`, `f2a01`) with readable names (e.g., `rev_tuition_fees_gross`, `exp_instruc_total`). All finance forms (GASB F1, FASB F2, for-profit F3) are merged into a single dataset with `form_type` and `reporting_form` columns to distinguish them.

**Key Portal Variables** (selected from 141 columns; see `finance-data.md` for complete GASB/FASB treatment):

*Identification & Classification:*

| Portal Variable | Type | Description | Values |
|-----------------|------|-------------|--------|
| `unitid` | Int64 | Unique institution ID | 6-digit integer |
| `year` | Int64 | Fiscal year that BEGINS in `year` (e.g., 2017 = FY2018; see SKILL.md § Year Field Meanings) | 1979, 1983-2017 in the pinned mirror (live Portal: 1979, 1983-2023) |
| `fips` | Int64 | State FIPS code | Integer |
| `form_type` | Int64 | Finance reporting form | 1-5 (see below) |
| `reporting_form` | Int64 | Detailed reporting form | -2=Not applicable, -1=Missing, 1-6 |
| `gasb_alternative_accounting` | Int64 | GASB alternative model | -2=N/A, -1=Missing, 1-4 |
| `parent_child_flag` | Int64 | Parent/child institution | -2=N/A, -1=Missing, 1-6 |
| `parent_unitid` | Int64 | Parent institution unitid | Integer |

*Revenue Variables (selected):*

| Portal Variable | Type | Description |
|-----------------|------|-------------|
| `rev_tuition_fees_gross` | Float64 | Gross tuition and fees |
| `rev_tuition_fees_net` | Float64 | Net tuition and fees (after allowances) |
| `rev_appropriations_state` | Float64 | State appropriations |
| `rev_appropriations_local` | Float64 | Local appropriations |
| `rev_appropriations_fed` | Float64 | Federal appropriations |
| `rev_grants_contracts_federal` | Float64 | Federal grants and contracts |
| `rev_grants_contracts_state` | Float64 | State grants and contracts |
| `rev_grants_contracts_local` | Float64 | Local grants and contracts |
| `rev_auxiliary_enterprises_gross` | Float64 | Auxiliary enterprises (gross) |
| `rev_hospital` | Float64 | Hospital revenue |
| `rev_investment_return` | Float64 | Investment return |
| `rev_endowment_income` | Float64 | Endowment income |
| `rev_total_current` | Float64 | Total current revenues |

*Expense Variables (selected):*

| Portal Variable | Type | Description |
|-----------------|------|-------------|
| `exp_instruc_total` | Float64 | Instruction total expenses |
| `exp_instruc_salaries` | Float64 | Instruction salaries |
| `exp_research_total` | Float64 | Research total expenses |
| `exp_pub_serv_total` | Float64 | Public service total |
| `exp_acad_supp_total` | Float64 | Academic support total |
| `exp_student_serv_total` | Float64 | Student services total |
| `exp_inst_supp_total` | Float64 | Institutional support total |
| `exp_aux_ent_total` | Float64 | Auxiliary enterprises total |
| `exp_hospital_total` | Float64 | Hospital expenses total |
| `exp_total_current` | Float64 | Total current expenses |
| `exp_total_salaries` | Float64 | Total salary outlays |
| `exp_total_benefits` | Float64 | Total benefit expenses |

*Scholarship & Aid Variables:*

| Portal Variable | Type | Description |
|-----------------|------|-------------|
| `sch_pell_grant` | Float64 | Pell Grant expenditures |
| `sch_grants_state` | Float64 | State grant aid |
| `sch_grants_institutional` | Float64 | Institutional grant aid |
| `sch_total_student_aid` | Float64 | Total student aid |

*Balance Sheet Variables (selected):*

| Portal Variable | Type | Description |
|-----------------|------|-------------|
| `assets` | Float64 | Total assets |
| `liabilities` | Float64 | Total liabilities |
| `endowment_beg` | Float64 | Endowment beginning of year |
| `endowment_end` | Float64 | Endowment end of year |
| `equity_total` | Float64 | Total equity |
| `est_fte` | Int64 | Estimated FTE (for per-FTE calculations) |
| `rep_fte` | Int64 | Reported FTE |
| `calc_fte` | Float64 | Calculated FTE |

*Cost Adjustment Indices:*

| Portal Variable | Type | Description |
|-----------------|------|-------------|
| `cpi` | Float64 | Consumer Price Index |
| `heca` | Float64 | Higher Education Cost Adjustment |
| `hepi` | Float64 | Higher Education Price Index |

> **`form_type` values (Portal codebook labels):** 1=Common form, 2=Form 1, 3=Form 1A, 4=Form 2, 5=Form 3. Code 4 is not limited to public FASB reporters: Harvard (unitid 166027) and Cornell (unitid 190415), both private nonprofits, carry `form_type` 4 (with `reporting_form` 5) in Portal `year` 2017 (probed 2026-10-19). For the accounting standard itself, use `reporting_form` (codebook: 4 = FASB reporting standards, 5 = FASB reporting standards (aligned), 6 = Modified FASB (private for-profit institutions); 1-3 = GASB variants). Not all columns are populated for all form types; see `finance-data.md` for which revenue/expense categories apply to which form.

> **NCES form-field codes** (e.g., `f1a01`=GASB total current assets, `f2a01`=FASB total current assets) do not appear in the Portal. The Portal uses the descriptive names listed above. See the codebook (`ipeds/codebook_colleges_ipeds_finance`) for complete column documentation.

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

**Portal Datasets**: The Portal splits HR into two separate datasets, both in **long/tidy format** with dimension columns:

| Portal Dataset | Path | Rows | Cols | Years |
|----------------|------|------|------|-------|
| Instructional Staff Salaries | `ipeds/colleges_ipeds_salaries_is` | 7.2M | 11 | 1980-2022 |
| Noninstructional Staff Salaries | `ipeds/colleges_ipeds_salaries_nis` | 680K | 6 | 2012-2022 |

**Instructional Staff Salaries Variables** (11 columns):

| Portal Variable | Type | Description | Values |
|-----------------|------|-------------|--------|
| `unitid` | Int64 | Unique institution ID | 6-digit integer |
| `year` | Int64 | Year | 1980-2022 |
| `fips` | Int64 | State FIPS code | Integer |
| `academic_rank` | Int64 | Faculty rank | 1=Professor, 2=Associate Professor, 3=Assistant Professor, 4=Instructor, 5=Lecturer, 6=No Academic Rank, 99=Total |
| `contract_length` | Int64 | Contract length (months) | 5-13=Month count, 99=Total |
| `sex` | Int64 | Sex | 1=Male, 2=Female, 99=Total |
| `instruc_staff_count` | Float64 | Number of instructional staff | Float (may have fractional FTE) |
| `salary_outlays` | Float64 | Total salary outlays ($) | Float |
| `average_salary` | Float64 | Average salary ($) | Float; -1=Not applicable |
| `total_months` | Float64 | Total months of contract | Float |
| `avg_wgtd_mon_salary` | Float64 | Average weighted monthly salary ($) | Float |

**Noninstructional Staff Salaries Variables** (6 columns):

| Portal Variable | Type | Description | Values |
|-----------------|------|-------------|--------|
| `unitid` | Int64 | Unique institution ID | 6-digit integer |
| `year` | Int64 | Year | 2012-2022 |
| `fips` | Int64 | State FIPS code | Integer |
| `staff_category` | Int64 | Occupational category | 2-14, 99=Total (see below) |
| `noninstruc_staff_count` | Float64 | Number of noninstructional staff | Float |
| `salary_outlays` | Float64 | Total salary outlays ($) | Float |

**`staff_category` Values** (noninstructional staff):

| Code | Occupational Category |
|------|-----------------------|
| 2 | Research |
| 3 | Public service |
| 4 | Librarians, curators, archivists |
| 5 | Student and academic affairs |
| 6 | Management |
| 7 | Business and financial operations |
| 8 | Computer, engineering, and science |
| 9 | Community service, legal, arts, and media |
| 10 | Healthcare practitioners |
| 11 | Service occupations |
| 12 | Sales and office |
| 13 | Natural resources, construction, and maintenance |
| 14 | Production, transportation, and material moving |
| 99 | Total |

> **Structural Note:** NCES HR data uses wide-format variables for each occupation/rank/gender combination. The Portal transforms this into long format: one row per institution-year-dimension combination. To get total instructional staff salary, filter `salaries_is` with `academic_rank==99`, `contract_length==99`, `sex==99`. For occupational breakdowns, filter `salaries_nis` by `staff_category`.

**Occupational Categories** (NCES reference):
- Instruction (faculty) -- in `salaries_is` dataset
- Research through Production/transportation -- in `salaries_nis` dataset (codes 2-14)

### Academic Libraries (AL)

Library resources and services. **Collected annually in the spring from the 2014-15 collection** (the predecessor Academic Libraries Survey was biennial, odd-numbered years). Current NCES component lists (fetched 2026-10-19) no longer include AL; confirm whether collection continues.

**Collection Period**: Spring collection (December-April)

**Data Collected**:
- Library expenditures
- Collections (physical and digital)
- Circulation
- Interlibrary loans

## Data Release Schedule

Data releases occur in two types (provisional and revised/final, released together but for different collection years):

| Release Type | Timing | Use Case |
|--------------|--------|----------|
| Provisional | ~9 months after the collection period closes | Initial analysis |
| Revised/Final | ~9 months after the next year's Prior Year Revision (PYR) system closes, usually alongside the following year's provisional release | Most analysis |

**Recent releases (NCES Data Release Schedule, fetched 2026-10-19):** 2024-25 Winter provisional Dec 9, 2025; 2024-25 Spring provisional Jan 6, 2026; 2025-26 Fall provisional Jul 28, 2026; 2024-25 Fall final Sep 8, 2026.

## Title IV Requirement

All institutions participating in Title IV federal student financial aid programs are required to report IPEDS data. This includes:

- Pell Grant program
- Federal Direct Loans
- Federal Work-Study
- Federal Supplemental Educational Opportunity Grant (SEOG)
- Federal Perkins Loan (discontinued)
- TEACH Grant

**Non-Title IV institutions** are not required to report; they may report voluntarily, so IPEDS coverage of non-Title IV providers is partial (NCES Handbook of Survey Methods, IPEDS chapter).

## Survey Response Rates

IPEDS unit response rates are very high (greater than 99 percent for each component in the Spring 2018 collection; about 89 to over 99 percent for Title IV institutions since web collection began; NCES Handbook of Survey Methods) because reporting is mandatory for Title IV participants and NCES follows up extensively. Nonrespondents are imputed.
