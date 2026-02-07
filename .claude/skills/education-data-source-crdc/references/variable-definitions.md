# CRDC Variable Definitions

Detailed definitions for key CRDC variables, including codes, disaggregation categories, and special values.

## Contents

- [Race/Ethnicity Categories](#raceethnicity-categories)
- [Sex Categories](#sex-categories)
- [Disability Categories](#disability-categories)
- [English Learner Definition](#english-learner-definition)
- [Discipline Definitions](#discipline-definitions)
- [Restraint and Seclusion Definitions](#restraint-and-seclusion-definitions)
- [Harassment Categories](#harassment-categories)
- [Chronic Absenteeism Definition](#chronic-absenteeism-definition)
- [Special Codes and Missing Values](#special-codes-and-missing-values)
- [School Type Codes](#school-type-codes)

---

## Race/Ethnicity Categories

### Seven Categories (Post-2007 Standards)

CRDC uses OMB's 2007 standards for race/ethnicity reporting:

| Code | Category | Definition |
|------|----------|------------|
| `HI` | Hispanic/Latino | Person of Cuban, Mexican, Puerto Rican, South/Central American, or other Spanish culture or origin, regardless of race |
| `AM` | American Indian/Alaska Native | Person having origins in any of the original peoples of North and South America (including Central America), and who maintains tribal affiliation or community attachment |
| `AS` | Asian | Person having origins in any of the original peoples of the Far East, Southeast Asia, or the Indian subcontinent |
| `BL` | Black or African American | Person having origins in any of the Black racial groups of Africa |
| `HP` | Native Hawaiian/Pacific Islander | Person having origins in any of the original peoples of Hawaii, Guam, Samoa, or other Pacific Islands |
| `WH` | White | Person having origins in any of the original peoples of Europe, the Middle East, or North Africa |
| `TR` | Two or more races | Person who identifies with two or more racial categories (non-Hispanic only) |

### Important Notes

1. **Hispanic/Latino is ethnicity, not race** - Persons of Hispanic origin are counted in Hispanic category regardless of race
2. **Non-overlapping categories** - Each student counted in exactly one category
3. **Two or more races** - Only for non-Hispanic students identifying as multiracial

### Variable Naming Pattern

```
{variable}_{race_code}

Examples:
enrollment_bl = Black enrollment
oss_hi = Hispanic students with OSS
ap_enrollment_as = Asian students in AP
```

---

## Sex Categories

### Binary Categories

| Code | Category |
|------|----------|
| `M` | Male |
| `F` | Female |

### Important Notes

- CRDC collects binary sex only (not gender identity)
- Some guidance has addressed LGBTQ+ students under Title IX, but data collection remains binary
- Variable names typically use `male` / `female` suffixes

### Variable Naming Pattern

```
{variable}_male
{variable}_female

Examples:
enrollment_male = Male enrollment
oss_female = Female students with OSS
```

---

## Disability Categories

### Primary Distinction

| Category | Definition |
|----------|------------|
| **Students with disabilities (IDEA)** | Students receiving special education services under IDEA with an IEP |
| **Students with Section 504 plans only** | Students with disabilities served under Section 504 but not IDEA |
| **Students without disabilities** | All other students |

### IDEA Disability Categories (13 categories)

| Code | Category | Definition |
|------|----------|------------|
| `AUT` | Autism | Developmental disability affecting communication and social interaction |
| `DB` | Deaf-blindness | Concomitant hearing and visual impairments |
| `DD` | Developmental delay | Delay in physical, cognitive, communication, social-emotional, or adaptive development (ages 3-9) |
| `ED` | Emotional disturbance | Condition exhibiting characteristics over time affecting educational performance |
| `HI` | Hearing impairment | Hearing loss not covered under deaf-blindness |
| `ID` | Intellectual disability | Significantly subaverage general intellectual functioning with deficits in adaptive behavior |
| `MD` | Multiple disabilities | Concomitant impairments (not deaf-blindness) |
| `OI` | Orthopedic impairment | Severe orthopedic impairment affecting educational performance |
| `OHI` | Other health impairment | Limited strength, vitality, or alertness due to chronic or acute health problems |
| `SLD` | Specific learning disability | Disorder in psychological processes affecting reading, math, writing |
| `SLI` | Speech or language impairment | Communication disorder |
| `TBI` | Traumatic brain injury | Acquired injury to brain causing functional disability |
| `VI` | Visual impairment | Visual impairment affecting educational performance |

### Variable Naming Pattern

```
{variable}_idea = Students with disabilities (IDEA)
{variable}_504 = Students with 504 plans only
{variable}_wodis = Students without disabilities

Examples:
enrollment_idea = IDEA students enrolled
oss_idea = IDEA students with OSS
restrained_idea = IDEA students restrained
```

---

## English Learner Definition

### Definition

**English Learner (EL)** / **Limited English Proficient (LEP)**: A student who:
1. Has a primary or home language other than English, AND
2. Has difficulty speaking, reading, writing, or understanding English

### Important Notes

| Note | Details |
|------|---------|
| **State variation** | EL identification criteria vary by state |
| **Exit criteria vary** | When students are reclassified as proficient varies |
| **Title III definition** | Based on ESEA/ESSA definition |
| **Not same as immigrant** | EL status is about English proficiency, not immigration status |

### Variable Naming Pattern

```
{variable}_lep

Examples:
enrollment_lep = English learner enrollment
oss_lep = English learners with OSS
chronic_absent_lep = Chronically absent EL students
```

---

## Discipline Definitions

### In-School Suspension (ISS)

**Definition**: Instances in which a child is temporarily removed from his or her regular classroom(s) for disciplinary purposes but remains under the direct supervision of school personnel. Direct supervision means school personnel are physically in the same location as students under their supervision.

| Element | Specification |
|---------|---------------|
| Location | Remains at school |
| Duration | Any length |
| Supervision | Direct supervision required |

### Out-of-School Suspension (OSS)

**Definition**: Instances in which a child is temporarily removed from his or her regular school for disciplinary purposes to another setting (e.g., home, behavior center). This includes both removals where no IEP services are provided and removals where the child continues to receive IEP services.

| Element | Specification |
|---------|---------------|
| Location | Removed from school |
| Duration | Temporary (returns to school) |
| Variants | One suspension / More than one suspension |

### Expulsion

**Definition**: An action taken by the LEA removing a child from his/her regular school for disciplinary purposes for the remainder of the school year or longer (consistent with LEA policy).

| Variant | Definition |
|---------|------------|
| **With educational services** | Expelled but receives educational services elsewhere |
| **Without educational services** | Expelled with no educational services provided |

### Referral to Law Enforcement

**Definition**: An action by which a student is reported to any law enforcement agency or official, including a school police unit, for an incident that occurs on school grounds, during school-related events, or while taking school transportation.

### School-Related Arrest

**Definition**: An arrest of a student for any activity conducted on school grounds, during off-campus school activities (including while taking school transportation), or due to a referral by any school official.

---

## Restraint and Seclusion Definitions

### Mechanical Restraint

**Definition**: The use of any device or equipment to restrict a student's freedom of movement. This term does not include devices implemented by trained school personnel, or utilized by a student that have been prescribed by an appropriate medical or related services professional and are used for the specific and approved purposes for which such devices were designed.

**Exclusions**:
- Medically prescribed devices (e.g., wheelchair restraints)
- Therapeutic devices used as designed

### Physical Restraint

**Definition**: A personal restriction that immobilizes or reduces the ability of a student to move his or her torso, arms, legs, or head freely. The term does not include a physical escort.

**Physical escort (excluded)**: A temporary touching or holding of the hand, wrist, arm, shoulder, or back for the purpose of inducing a student who is acting out to walk to a safe location.

### Seclusion

**Definition**: The involuntary confinement of a student alone in a room or area from which the student is physically prevented from leaving. It does not include a timeout, which is a behavior management technique that involves the monitored separation of the student in a non-locked setting.

**Timeout (excluded)**: Monitored separation in non-locked setting that student can leave.

---

## Harassment Categories

### Harassment or Bullying Based on Race, Color, or National Origin

**Definition**: Harassment or bullying directed at a student because of their race, color, or national origin that is:
- Sufficiently severe, persistent, or pervasive to interfere with education, OR
- Creates a hostile or abusive educational environment

### Harassment or Bullying Based on Sex

**Definition**: Sexual harassment or bullying based on sex that includes:
- Unwelcome conduct of a sexual nature
- Gender-based harassment

### Harassment or Bullying Based on Disability

**Definition**: Harassment or bullying directed at a student because of their disability status.

### Variables Collected

| Variable Type | Description |
|---------------|-------------|
| Students **alleging** | Count of students who alleged harassment |
| Students **disciplined** | Count of students disciplined for harassing |

---

## Chronic Absenteeism Definition

### Official Definition

**Chronically absent**: A student who is absent 15 or more school days during the school year.

| Element | Specification |
|---------|---------------|
| Threshold | 15 or more days |
| Types of absence | All absences (excused and unexcused) |
| Reference period | Full school year |

### Important Notes

1. **Any absence counts** - Excused, unexcused, suspensions all count
2. **15-day threshold is CRDC standard** - Some states use 10% of enrolled days
3. **Added in 2015-16** - Not available in earlier collections
4. **COVID impact** - 2020-21 definition complicated by remote learning

### State Variation

Some states define chronic absenteeism as:
- Missing 10% or more of enrolled days
- Different day thresholds
- Different treatment of excused absences

CRDC uses consistent 15-day definition across all states.

---

## Special Codes and Missing Values

### Education Data Portal Codes

When accessing CRDC via Urban Institute Education Data Portal:

| Code | Meaning |
|------|---------|
| `-1` | Missing/not reported |
| `-2` | Not applicable |
| `-3` | Suppressed (small cell) |
| `-9` | Data withheld (multiple reasons) |

### Handling Special Codes

```python
import polars as pl

def clean_crdc_values(df, value_columns):
    """
    Handle CRDC special codes appropriately.
    
    Args:
        df: DataFrame with CRDC data
        value_columns: List of columns to clean
    
    Returns:
        DataFrame with nulls for special codes
    """
    for col in value_columns:
        df = df.with_columns(
            pl.when(pl.col(col) < 0)
            .then(None)
            .otherwise(pl.col(col))
            .alias(col)
        )
    return df

def flag_suppressed(df, column):
    """
    Flag suppressed values separately.
    """
    return df.with_columns(
        (pl.col(column) == -3).alias(f"{column}_suppressed")
    )
```

### Suppression Rules

Small cells are suppressed to protect student privacy:
- Typically counts of 1-5 students
- Applied at subgroup level
- More suppression in small schools
- Complementary suppression to prevent back-calculation

---

## School Type Codes

### Level Codes

| Code | Level |
|------|-------|
| `1` | Primary (elementary) |
| `2` | Middle |
| `3` | High |
| `4` | Other |

### School Type Indicators

| Variable | Values |
|----------|--------|
| `charter` | 1 = Charter, 0 = Not charter |
| `magnet` | 1 = Magnet, 0 = Not magnet |
| `alternative` | 1 = Alternative, 0 = Regular |
| `virtual` | 1 = Virtual, 0 = Not virtual |
| `special_ed` | 1 = Special education school, 0 = Regular |
| `vocational` | 1 = Vocational, 0 = Not vocational |

### Title I Status

| Code | Status |
|------|--------|
| `1` | Title I schoolwide program |
| `2` | Title I targeted assistance |
| `0` | Not a Title I school |

---

## Cross-Tabulation Variables

### Available Cross-Tabulations

CRDC provides some variables cross-tabulated:

| Cross-Tab | Available For |
|-----------|---------------|
| Race × Sex | Most discipline variables |
| Race × Disability | Some discipline variables |
| Sex × Disability | Some discipline variables |
| Race × Sex × Disability | Limited variables |

### Example Variable Names

```
# Race × Sex patterns
oss_bl_male = Black male students with OSS
oss_hi_female = Hispanic female students with OSS

# Race × Disability patterns
oss_bl_idea = Black students with disabilities with OSS
oss_wh_wodis = White students without disabilities with OSS
```

---

## Grade Level Codes

### Grade Codes

| Code | Grade |
|------|-------|
| `PS` | Preschool |
| `PK` | Pre-Kindergarten |
| `KG` | Kindergarten |
| `01`-`12` | Grades 1-12 |
| `UG` | Ungraded |

### School Grade Span

| Pattern | Description |
|---------|-------------|
| `grades_offered_lowest` | Lowest grade offered |
| `grades_offered_highest` | Highest grade offered |
| `elementary_school` | Indicator for elementary |
| `middle_school` | Indicator for middle school |
| `high_school` | Indicator for high school |

---

## Staffing Variables

### FTE (Full-Time Equivalent)

Staff counts reported as FTE:
- 1.0 FTE = Full-time position
- 0.5 FTE = Half-time position
- Allows comparison across schools with different staffing models

### Teacher Categories

| Variable | Definition |
|----------|------------|
| `teachers_fte` | Total teacher FTE |
| `teachers_first_year` | Teachers in first year of teaching |
| `teachers_second_year` | Teachers in second year |
| `teachers_certified` | Teachers with full certification |
| `teachers_not_certified` | Teachers without full certification |
| `teachers_emergency_certified` | Teachers with emergency/provisional certification |

### Support Staff

| Variable | Definition |
|----------|------------|
| `counselors_fte` | School counselor FTE |
| `psychologists_fte` | School psychologist FTE |
| `social_workers_fte` | School social worker FTE |
| `nurses_fte` | School nurse FTE |
| `sro_fte` | School resource officer FTE |
| `security_fte` | Security guard FTE |

---

## Course Offering Indicators

### Binary Indicators

Many course variables are binary (school offers or doesn't):

| Variable | Values |
|----------|--------|
| `offers_algebra1` | 1 = Offers, 0 = Doesn't offer |
| `offers_calculus` | 1 = Offers, 0 = Doesn't offer |
| `offers_physics` | 1 = Offers, 0 = Doesn't offer |
| `offers_ap` | 1 = Offers any AP, 0 = No AP |
| `offers_cs` | 1 = Offers computer science, 0 = No CS |

### Enrollment Counts

When courses are offered, enrollment counts available:

| Variable | Description |
|----------|-------------|
| `ap_enrollment` | Total AP enrollment |
| `ap_enrollment_{race}` | AP enrollment by race |
| `ap_enrollment_male` | Male AP enrollment |
| `ap_enrollment_female` | Female AP enrollment |
