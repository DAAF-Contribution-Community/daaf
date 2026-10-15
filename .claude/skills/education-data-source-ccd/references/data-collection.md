# CCD Data Collection

This reference covers how CCD data is collected, processed, and released.

## Data Collection System

### EDFacts

CCD nonfiscal data has been collected via EDEN (the Education Data Exchange Network) from 2005-06; reporting it through **EDFacts** became mandatory from 2007-08, when EDFacts superseded EDEN. EDFacts centralizes data collection across multiple Department of Education programs.

**EDFacts Features**:
- Centralized data submission portal
- Standardized file specifications
- Automated validation checks
- Single submission for multiple federal requirements

**Submission Portal**: Since the SY 2022-23 collection cycle, states submit through EDPass, 'a centralized data submission system used by ED to standardize data submissions across ED offices', which runs data-quality checks at upload.

### Pre-EDFacts Collection (Before 2007-08)

Through the 2005-06 collection, CCD data were voluntarily obtained from administrative records collected and edited by SEAs during their regular state reporting cycle (NCES Handbook of Survey Methods). Collection tools evolved:
- Survey instruments distributed to states (early years)
- Downloadable PC software from the 2001-02 collection
- A web-based data collection application from 2004-05

The transition to EDFacts improved standardization but created some discontinuities in historical data.

## Respondent Universe

### Who Reports CCD Data?

**Primary Respondents**: State Education Agencies (SEAs)

States are responsible for:
1. Collecting data from Local Education Agencies (LEAs)
2. Validating and compiling state-level files
3. Submitting to NCES via EDFacts
4. Responding to quality review inquiries

**Data Flow**:
```
Individual Schools
      ↓
Local Education Agencies (LEAs/Districts)
      ↓
State Education Agencies (SEAs)
      ↓
EDFacts/NCES
      ↓
Public CCD Data Files
```

### Universe Definition

CCD is a **universe survey**, not a sample. It aims to include:

**Schools**:
- All public elementary schools
- All public secondary schools
- All public combined schools
- Charter schools (public)
- Magnet schools
- Alternative schools
- Virtual schools
- Special education schools (public)
- Vocational/career-technical schools (public)

**Local Education Agencies**:
- Regular school districts
- Supervisory unions
- Regional education service agencies
- State-operated agencies (schools for deaf, blind, incarcerated)
- Federally-operated agencies (BIE, DoDEA)
- Charter school agencies

**Jurisdictions**:
- 50 states
- District of Columbia
- Puerto Rico (nonfiscal data)
- Bureau of Indian Education (BIE) schools
- Department of Defense Education Activity (DoDEA) schools
- Other territories (American Samoa, Guam, Northern Mariana Islands, Virgin Islands)

### Exclusions

CCD does **not** include:
- Private schools (covered by Private School Universe Survey)
- Home-schooled students
- Postsecondary institutions (covered by IPEDS)
- Preschool programs not operated by public schools
- Adult education programs (unless part of K-12 system)

## Data Collection Timeline

### Nonfiscal Data (Directory, Membership, Staffing)

| Activity | Timing | Notes |
|----------|--------|-------|
| Reference Date | October 1 | Snapshot date for counts |
| State Submission | Due about July after the school year | Since SY 2022-23 via EDPass, which runs data-quality checks at upload |
| Public Release | Within about 4 months of the due date | SY 2023-24 example (NCES) |

Since SY 2022-23 (EDPass), states submit by about July after the school year and NCES releases within about 4 months (SY 2023-24 example). EDPass replaced the earlier post-submission data-quality review, which made release lags longer in prior years.

**Example**: For school year 2023-24 (October 1, 2023 snapshot):
- Submission due: July 2024
- Public release: less than 4 months later

### Fiscal Data (Finance)

Finance data has a longer lag due to fiscal year-end reporting requirements.

| Activity | Timing | Notes |
|----------|--------|-------|
| Fiscal Year End | June 30 | Most states |
| State Submission | Following fall/winter | After audits |
| Data Release | 18-24 months after FY end | |

**Example**: For fiscal year 2022 (July 2021 - June 2022):
- States submit: Late 2022 - Early 2023
- Data release: Late 2023 - 2024

## Data Submission Specifications

### EDFacts File Specifications

Each data element has detailed submission specifications including:
- **Data Group**: Category of data (e.g., membership, staff FTE)
- **File Number**: Unique identifier (e.g., FS052 for membership)
- **Permitted Values**: Valid codes and ranges
- **Business Rules**: Validation logic

**Key File Specifications** (EDFacts files that provide CCD data; NCES CCD SY 2015-16 documentation, Exhibit 3):

| File | Description | Level |
|------|-------------|-------|
| FS029 | Directory | SEA, LEA, School |
| FS039 | Grades offered | LEA, School |
| FS129 | School | School |
| FS052 | Membership | SEA, LEA, School |
| FS033 | Free & reduced-price lunch | School |
| FS059 | Staff | SEA, LEA, School |

### Submission Modes

**Level 1 (Aggregate)**: State provides aggregate counts
**Level 2 (Detail)**: State provides school/district-level data

Most states submit Level 2 data for CCD.

## Quality Review Process

### NCES Data Review

After submission, NCES performs:

1. **Automated Validation**
   - Range checks
   - Internal consistency (e.g., grade enrollment sums)
   - Year-to-year comparisons
   - Cross-file consistency

2. **Manual Review**
   - Outlier investigation
   - Trend analysis
   - State-specific notes review

3. **State Follow-up**
   - Questions sent to state coordinators
   - Resolution of discrepancies
   - Resubmission if needed

### Common Quality Checks

| Check Type | Example | Action |
|------------|---------|--------|
| Range | Enrollment > 0 for operational schools | Flag for review |
| Consistency | Membership by grade ≈ Total | Investigate difference |
| Year-to-Year | Large change from prior years (e.g., >20%: an illustrative example, not an NCES threshold) | Contact state |
| Cross-file | School counts match directory | Verify |

> NCES's actual year-to-year check (since SY 2009-10) is a multi-year edit: it compares the current value with the prior 4 years, tests a related ratio (e.g., pupil/teacher ratio), and flags large variances for state review. Values that cannot be explained are suppressed.

### Imputation

NCES imputes only state-level (State Nonfiscal) items. School and LEA values are edited or suppressed, not imputed.

State-level files carry imputation flags (the letter `I` followed by the variable name) indicating which values were adjusted or imputed.

## State Coordinators

Each state has designated **CCD Coordinators**:
- **Nonfiscal Coordinator**: Handles directory, membership, staffing
- **Fiscal Coordinator**: Handles finance data

Coordinators are responsible for:
- Compiling state data
- Validating before submission
- Responding to NCES inquiries
- Communicating data limitations

## Data Release Process

### Preliminary vs. Provisional

| Release Type | Description | Use Case |
|--------------|-------------|----------|
| Preliminary (0x) | First release, limited quality review | Timely access, subject to revision |
| Provisional (1x) | Quality-reviewed, considered final | Research, official statistics |

**Version Letters**: Multiple releases within a type (0a, 0b, 1a, 1b) indicate updates/corrections.

### Publication Formats

CCD data is available through:

1. **Data Files**: CSV/SAS files for download from NCES
2. **ELSI (Elementary/Secondary Information System)**: NCES online query tool
3. **School/District Locators**: Individual entity lookup on NCES site
4. **Publications**: NCES reports and tables
5. **Education Data Portal mirrors**: Processed CCD data available via HuggingFace (parquet) and Urban Institute (CSV) mirrors. See `datasets-reference.md` for canonical paths and `mirrors.yaml` for mirror configuration.

### Documentation

Each release includes:
- Record layouts
- Variable definitions
- State notes
- Change logs
- Imputation information

## Special Reporting Situations

### Bureau of Indian Education (BIE) Schools

BIE schools are reported both by:
- BIE directly to NCES
- States where schools are located (in some cases)

**Double-counting issue**: Some BIE schools appear in both BIE and state files. NCES provides crosswalk documentation to identify duplicates.

### Department of Defense Schools (DoDEA)

DoDEA operates schools on military installations:
- Department of Defense, Domestic
- Department of Defense, Overseas (Department of Defense Dependent Schools)

Since 2010-11, DoDEA (domestic and overseas) reports as a single unit.

### Virtual Schools

Starting in SY 2013-14, all schools in the CCD have a VIRTUAL flag indicating whether the school is a virtual school (NCES SY 2015-16 documentation). The categorical status below comes from later collections; the year it started was not verified:
- Full-time virtual
- Supplemental virtual
- Not virtual

Virtual school enrollment counting varies significantly by state.

### Charter Schools

Charter school reporting has improved over time:
- Early years (pre-2000): Many charters missing or miscoded
- 2000-2010: Improving but inconsistent
- 2010+: Generally complete coverage

**Charter Agency Type**: Starting 2007-08, LEA type code 7 specifically identifies charter school agencies.

## State-Specific Notes

Each CCD release includes state notes documenting:
- Known data quality issues
- Reporting methodology differences
- Missing data explanations
- Definition variations

**Examples**:
- State X reports all students in grade 13 as ungraded
- State Y unable to provide race/ethnicity for certain schools
- State Z includes prekindergarten differently than other states

Always check state notes before interpreting outliers or unexpected values.

## Contact Information

**EDFacts Partner Support Center (PSC)**: EDFacts@ed.gov (NCES's listed contact for nonfiscal CCD questions)

**State Coordinators**: Contact information available on NCES CCD website.
