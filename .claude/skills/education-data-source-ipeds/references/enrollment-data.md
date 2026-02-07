# IPEDS Enrollment Data

Understanding the different enrollment measures in IPEDS and when to use each.

## Contents

- [Two Enrollment Surveys](#two-enrollment-surveys)
- [Fall Enrollment (EF)](#fall-enrollment-ef)
- [12-Month Enrollment (E12)](#12-month-enrollment-e12)
- [Full-Time Equivalent (FTE)](#full-time-equivalent-fte)
- [Enrollment Categories](#enrollment-categories)
- [Distance Education](#distance-education)
- [Retention Rates](#retention-rates)
- [Common Analysis Issues](#common-analysis-issues)

## Two Enrollment Surveys

IPEDS collects enrollment data through two separate surveys:

| Survey | Timing | Purpose | Best For |
|--------|--------|---------|----------|
| Fall Enrollment (EF) | Point-in-time (fall census) | Traditional headcount | Institution size comparison |
| 12-Month Enrollment (E12) | Full academic year | Unduplicated total | True scope of students served |

**Key Difference**: A student enrolled in both fall and spring is counted ONCE in E12 but appears in fall EF only.

## Fall Enrollment (EF)

### When Collected

Spring collection period (December-April) for the previous fall semester.

### Census Date

- **Academic year reporters**: Institution's official fall reporting date
- **Program reporters**: Students enrolled between August 1 and October 31

### What Is Counted

Total students enrolled in credit-bearing courses as of the census date.

### Key Breakdowns

| Dimension | Categories |
|-----------|------------|
| Attendance status | Full-time, Part-time |
| Level | Undergraduate, Graduate, First-professional |
| Undergraduate type | First-time, Transfer, Continuing, Non-degree |
| Race/ethnicity | 9 categories |
| Gender | Men, Women |
| Residence (even years) | State of residence for first-time students |
| Age (odd years) | Age distribution |
| Distance education | Exclusively DE, Some DE, No DE |

### Limitations

- Point-in-time snapshot
- May not capture students in short-term programs
- Doesn't show full year enrollment patterns
- Different institutions have different census dates

## 12-Month Enrollment (E12)

### When Collected

Fall collection period (August-October) for the prior academic year (July 1 - June 30).

### What Is Counted

**Unduplicated headcount**: Each student counted only once regardless of number of terms enrolled.

### Key Components

1. **Unduplicated headcount** by level, race/ethnicity, gender
2. **Instructional activity** (credit hours attempted)
3. **Full-time equivalent (FTE)** enrollment

### Advantages Over Fall Enrollment

| Fall EF | 12-Month E12 |
|---------|--------------|
| Misses spring-only enrollees | Captures all enrollees |
| Misses summer enrollees | Captures summer |
| May undercount at non-traditional schools | Better for year-round schools |
| Snapshot can be misleading | Full picture |

### When to Use Each

| Use Case | Recommended Survey |
|----------|-------------------|
| Comparing institution sizes | Fall EF |
| Calculating per-student metrics | E12 or FTE |
| Traditional 4-year institutions | Either (similar) |
| Community colleges | E12 (captures more students) |
| For-profit institutions | E12 (rolling enrollment) |
| Year-round programs | E12 |

## Full-Time Equivalent (FTE)

FTE standardizes enrollment across institutions with different full-time/part-time mixes.

### FTE Calculation Methods

**Credit Hour Institutions (most common)**:

```
Undergraduate FTE = Full-time UG + (Part-time UG credit hours / 30)
Graduate FTE = Full-time Grad + (Part-time Grad credit hours / 24)
```

**Clock Hour Institutions**:

```
FTE = Total contact hours / 900
```

### FTE vs Headcount

| Measure | When to Use |
|---------|-------------|
| Headcount | Counting individuals |
| FTE | Comparing across institutions |
| FTE | Per-student calculations |
| FTE | Resource allocation analysis |

### FTE Data Quality Issues

1. **Different calculation methods**: Credit vs clock hour
2. **Part-time estimation**: Not always precise
3. **Cross-sector comparison**: Different student intensity patterns
4. **Program mix**: Short programs vs degree programs

### FTE in Per-Student Metrics

Common calculations using FTE:

```python
# Expenditure per FTE
exp_per_fte = total_expenditures / total_fte

# Revenue per FTE  
rev_per_fte = total_revenue / total_fte

# Faculty to student ratio (uses fall enrollment)
ratio = fall_enrollment / instructional_faculty
```

## Enrollment Categories

### By Attendance Status

| Status | Definition |
|--------|------------|
| Full-time | Enrolled for 12+ semester hours or equivalent |
| Part-time | Enrolled for fewer than 12 semester hours |

Note: Definition varies by institution and term type (semester vs quarter).

### By Student Level

| Level | Definition |
|-------|------------|
| Undergraduate | Enrolled in bachelor's or lower program |
| Graduate | Enrolled in master's or doctoral program |
| First-professional | Enrolled in professional degree (JD, MD, etc.) |
| Unclassified | Not classified by level |

### By Enrollment Status (Undergraduates)

| Status | Definition |
|--------|------------|
| First-time | Never previously enrolled at ANY postsecondary institution |
| Transfer | Previously enrolled at another institution |
| Continuing | Enrolled previous year at same institution |
| Returning | Previously enrolled at same institution but not last year |

### Degree-Seeking Status

| Status | Definition |
|--------|------------|
| Degree-seeking | Enrolled in program leading to award |
| Non-degree-seeking | Taking courses but not in a program |

## Distance Education

### Definitions (since 2012-13)

| Category | Definition |
|----------|------------|
| Exclusively distance education | All courses are distance education |
| Some but not all distance education | Mix of DE and in-person |
| Not enrolled in any distance education | All in-person |

### Distance Education Definition

A course where instruction is delivered:
- Using one or more technologies to deliver instruction to students separated from instructor
- Supports regular and substantive interaction between students and instructor
- Synchronous or asynchronous

### Data Availability

- Fall enrollment by DE status: 2012-13+
- Completions by DE status: 2012-13+
- COVID impact: 2020-21 data shows dramatic shifts

### Common Uses

```python
# Percent of students in distance education
pct_de_any = (exclusively_de + some_de) / total_enrollment * 100

# Percent exclusively online
pct_exclusively_online = exclusively_de / total_enrollment * 100
```

## Retention Rates

### Definition

Percentage of first-time students who return to the same institution the following fall.

### Calculation

```
Retention rate = (First-time students returning in fall Y+1) / 
                 (First-time students in fall Y) * 100
```

### Full-Time vs Part-Time

IPEDS reports separate retention rates:
- Full-time first-time student retention
- Part-time first-time student retention

### Limitations

- Only tracks first-time students (not transfers)
- Only at same institution (transfer = not retained)
- Full-time/part-time status based on initial enrollment

### Using Retention Data

| Use | Caution |
|-----|---------|
| Institutional effectiveness | Reflects student selection too |
| Early warning indicator | Better than 6-year lag of grad rates |
| Peer comparison | Compare within peer groups |

## Common Analysis Issues

### Issue 1: Comparing Enrollment Across Institution Types

**Problem**: Different institutions serve different populations.

| Institution Type | Typical Pattern |
|-----------------|-----------------|
| Research university | FT undergrad, FT grad heavy |
| Community college | PT heavy, year-round enrollment |
| For-profit | Rolling enrollment, PT common |

**Solution**: Compare within peer groups; note composition differences.

### Issue 2: Year-Over-Year Changes

**Problem**: Single-year changes may reflect data issues, not trends.

**Solution**: 
- Look at multi-year trends
- Check for institutional changes
- Verify with other sources

### Issue 3: First-Time Student Definition

**Problem**: "First-time" means never attended ANY college, including:
- Dual enrollment in high school
- Summer programs

**Impact**: Some students counted as "transfers" were actually first-time college students.

### Issue 4: FTE vs Headcount for Per-Student Metrics

**Problem**: Using headcount when FTE is more appropriate (or vice versa).

| Metric | Recommended Denominator |
|--------|------------------------|
| Instruction spending per student | FTE |
| Student services per student | Headcount or FTE |
| Graduation rate | Cohort count |
| Room & board revenue per student | Residential headcount |

### Issue 5: COVID-19 Impact

**2020 and 2021 data** show significant disruptions:
- Enrollment declines
- Shift to distance education
- Changed retention patterns

**Recommendation**: Note pandemic years when analyzing trends.

## Variable Reference

### Fall Enrollment Key Variables

| Variable | Description |
|----------|-------------|
| `eftotlt` | Total fall enrollment |
| `eftotlm` | Male fall enrollment |
| `eftotlw` | Female fall enrollment |
| `efft` | Full-time enrollment |
| `efpt` | Part-time enrollment |
| `efug` | Undergraduate enrollment |
| `efgr` | Graduate enrollment |
| `ef1st` | First-time students |
| `eftran` | Transfer students |
| `efcont` | Continuing students |
| `efdeexc` | Exclusively distance education |
| `efdesom` | Some distance education |

### 12-Month Enrollment Key Variables

| Variable | Description |
|----------|-------------|
| `efytotlt` | Total 12-month unduplicated headcount |
| `efyug` | Undergraduate 12-month |
| `efygr` | Graduate 12-month |
| `fteug` | Undergraduate FTE |
| `ftegr` | Graduate FTE |
| `ftetot` | Total FTE |

### Retention Variables

| Variable | Description |
|----------|-------------|
| `ret_pcf` | Full-time retention rate |
| `ret_pcp` | Part-time retention rate |
| `ret_nmf` | Full-time students in retention cohort |
| `ret_nmp` | Part-time students in retention cohort |
