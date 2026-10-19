# Civil Rights Data Collection (CRDC) Context

The CRDC collects data on equity indicators and civil rights compliance from public schools and districts. In this system, CRDC data is accessed through the Urban Institute Education Data Portal, which standardizes variable names to lowercase and applies integer encoding to categorical variables.

## Source Overview

| Attribute | Value |
|-----------|-------|
| Collector | U.S. Department of Education, Office for Civil Rights |
| Respondents | Public schools and districts |
| Focus | Educational equity and civil rights |
| Frequency | Generally biennial (2020-21 and 2021-22 were consecutive) |
| Available Years | Portal: 2011, 2013, 2015, 2017, 2020, 2021 for most topics; chronic absenteeism also 2022 (EDFacts-sourced); some topics (e.g., offerings) also 2023 |
| Primary Use | Discipline, course access, resource equity |

### Historical Context

- First collected 1968 as part of civil rights enforcement
- Collections from 1968 to 2010 were samples (except 1976 and 2000); every collection from 2011-12 on is a universe collection
- Scope and variables have expanded over time
- Focus on identifying discrimination and inequity

## Collection Schedule

### Available Years

| School Year (Portal `year`) | Data Released | Notes |
|-------------|--------------|-------|
| 2011-12 (2011) | 2014 (Data Snapshot, March 21, 2014) | Universe collection (all public schools and districts) |
| 2013-14 (2013) | 2016 (First Look, June 7, 2016) | Universe |
| 2015-16 (2015) | 2018 (OCR brief, April 2018) | Universe |
| 2017-18 (2017) | 2020 (user's manual dated June 2020) | Universe; chronic absenteeism taken from EDFacts |
| 2020-21 (2020) | 2023 (user's manual dated September 19, 2023) | Universe; COVID-19 impacted year |
| 2021-22 (2021) | 2025 (January 17, 2025) | Universe; consecutive with 2020-21 |
| 2023-24 (2023) | 2026 (August 31, 2026) | Universe; Portal exposes 2023 for some topics only (e.g., offerings) |

### NOT Annual Data

**Critical**: CRDC is generally collected every other school year (2020-21 and 2021-22 were consecutive).
- Cannot interpolate between collection years
- No collections for school years 2012-13, 2014-15, 2016-17, 2018-19, 2019-20, 2022-23 (chronic-absenteeism files nonetheless reach Portal 2022 via EDFacts)

### Timing Within Year

Data reflects the full school year (not point-in-time):
- Discipline counts: full year
- Enrollment: varies by variable
- Course enrollment: full year

## Sampling and Coverage

### Sample vs. Universe

| Collection | Approach |
|------------|----------|
| 2011-12 | Universe (all public schools and districts; 98.4% of districts, 99.2% of schools responded) |
| 2013-14 | Universe (16,758 districts; 95,507 schools) |
| 2015-16 | Universe (96,440 schools, final target) |
| 2017-18 | Universe (~97,600 schools; 17,637 LEAs final target) |
| 2020-21 | Universe (~97,500 schools) |
| 2021-22 | Universe (~98,000 schools) |
| 2023-24 | Universe (17,591 LEAs; 97,094 schools) |

### Coverage Implications

- Every collection from 2011-12 on is a universe collection (OCR); 1968-2010 collections were samples, except 1976 and 2000
- Nonresponse and suppression still apply — check coverage against CCD
- Cross-year comparisons still need attention to openings/closures and definition changes

### Verifying Coverage

```python
# Check school coverage
def crdc_coverage_check(crdc_df, ccd_df, year):
    crdc_schools = set(crdc_df["ncessch"].unique())
    ccd_schools = set(ccd_df["ncessch"].unique())
    
    coverage = len(crdc_schools & ccd_schools) / len(ccd_schools) * 100
    print(f"CRDC covers {coverage:.1f}% of CCD schools for {year}")
    
    return coverage
```

```r
# Check school coverage
crdc_schools <- unique(crdc_df$ncessch)
ccd_schools <- unique(ccd_df$ncessch)

coverage <- length(intersect(crdc_schools, ccd_schools)) / length(ccd_schools) * 100
cat(sprintf("CRDC covers %.1f%% of CCD schools for %s\n", coverage, year))
```

## Self-Reported Data

### Quality Implications

CRDC is self-reported by districts:

| Issue | Impact |
|-------|--------|
| Definition interpretation | Districts may define categories differently |
| Data system quality | Varies by district size and resources |
| Verification | OCR spot-checks but cannot verify all |
| Incentives | Under-reporting discipline may occur |

### Known Quality Concerns

1. **Small districts**: May have less sophisticated data systems
2. **New districts**: First-time reporters have learning curve
3. **Sensitive categories**: Discipline data may be underreported
4. **Complex categories**: Restraint/seclusion definitions vary

## Discipline Data

### Categories Collected

| Category | Definition Notes |
|----------|------------------|
| In-school suspension | Student removed from class but remains in school |
| Out-of-school suspension | Student removed from school premises |
| Expulsion | Removal for extended period or permanent |
| Referral to law enforcement | Any contact with police |
| School-related arrest | Arrest on school property or for school incident |
| Corporal punishment | Physical discipline (where legal) |
| Restraint | Physical restraint of student |
| Seclusion | Involuntary confinement |

### Discipline Data Caveats

**Definition Variation:**
- "Suspension" length thresholds vary by district
- "Referral to law enforcement" interpretation varies
- State laws affect what must be reported

**Zero-Tolerance Policies:**
- Districts with mandatory discipline policies show higher counts
- Policy changes affect time series
- Not necessarily indicator of student behavior

**Underreporting Concerns:**
- Discipline carries stigma
- Districts may use unreported informal discipline
- Electronic records may be incomplete

### Analyzing Discipline Data

```python
# Discipline rates per 100 students
def calculate_discipline_rate(df, discipline_col, enrollment_col):
    return (df[discipline_col] / df[enrollment_col] * 100)

# Compare across subgroups
def discipline_disparity(df, discipline_col, group1, group2):
    rate1 = df.filter(pl.col("subgroup") == group1)[discipline_col].mean()
    rate2 = df.filter(pl.col("subgroup") == group2)[discipline_col].mean()
    return rate1 / rate2  # Disparity ratio
```

```r
# Discipline rates per 100 students
df <- df |> mutate(discipline_rate = .data[[discipline_col]] / .data[[enrollment_col]] * 100)

# Compare across subgroups
rate1 <- df |> filter(subgroup == group1) |> pull(!!sym(discipline_col)) |> mean()
rate2 <- df |> filter(subgroup == group2) |> pull(!!sym(discipline_col)) |> mean()
disparity_ratio <- rate1 / rate2
```

## Variable Consistency

### Variables Added Over Time

| Variable Category | First Collected |
|-------------------|-----------------|
| Basic discipline | 2011 |
| Restraint/seclusion | 2011 |
| Chronic absenteeism | 2013 (CRDC form 2013-14 and 2015-16; taken from EDFacts from 2017-18) |
| Preschool suspension | 2011 (first collected 2011-12); Portal exposes preschool suspension instances from 2015 (discipline-instances) |
| Harassment or bullying (incl. on the basis of sex) | 2011 (Portal student counts; allegation counts from 2013) |
| Advanced coursework access | 2011 (expanded later) |

### Definition Changes

Always compare codebooks across collection years:
- Variable names may change
- Categories may be combined or split
- Response options may differ

### Missing Variables

Check that variables exist for your year:
```python
# Verify variable availability
def check_variable_availability(variable, year):
    availability = {
        "chronic_absent": [2013, 2015, 2017, 2020, 2021, 2022],  # Portal years; 2017+ sourced from EDFacts
        "preschool_suspend": [2015, 2017, 2020, 2021],  # Portal discipline-instances years
        # Add more as needed
    }
    if year not in availability.get(variable, []):
        print(f"WARNING: {variable} not available for {year}")
```

```r
# Verify variable availability
availability <- list(
  chronic_absent = c(2013, 2015, 2017, 2020, 2021, 2022),  # Portal years; 2017+ sourced from EDFacts
  preschool_suspend = c(2015, 2017, 2020, 2021)
)
if (!(year %in% availability[[variable]])) {
  cat(sprintf("WARNING: %s not available for %s\n", variable, year))
}
```

## COVID-19 Impact (2020-21 collection, Portal `year` 2020)

The 2020-21 collection reflects pandemic conditions:

### Comparability Issues

| Domain | Impact |
|--------|--------|
| Discipline | Reduced due to remote learning |
| Chronic absenteeism | Taken from EDFacts (state-reported) since 2017-18; reflects pandemic attendance disruption — compare with caution (no OCR redefinition documented) |
| Course enrollment | AP/IB offerings may have changed |
| School staffing | Significant changes |

### What's Different

1. **Reduced in-person time**: Discipline naturally lower
2. **Attendance disruption**: 2020-21 absenteeism reflects remote/hybrid schooling; a uniform 15-day definition across states after 2016 was not verified
3. **Course access**: Some courses not offered
4. **New indicators**: COVID-specific variables added

### Recommendation

Do NOT directly compare 2020-21 to prior years without explicitly noting COVID context.

## Course Access Data

### What's Collected

| Category | Examples |
|----------|----------|
| Math | Algebra I, Algebra II, Calculus |
| Science | Physics, Chemistry, Biology |
| AP courses | By subject area |
| Computer science | Any CS course |
| Career/technical | By pathway |

### Access vs. Enrollment

CRDC distinguishes:
- **Course offered**: School offers the course
- **Student enrolled**: Students taking the course

### Equity Analysis

```python
# Course access disparity
def course_access_disparity(df):
    # Schools with no access vs. students by subgroup
    return df.group_by(["school_has_ap", "student_race"]).agg(
        pl.col("enrollment").sum()
    )
```

```r
# Course access disparity
df |>
  group_by(school_has_ap, student_race) |>
  summarise(enrollment = sum(enrollment), .groups = "drop")
```

## Linking CRDC to Other Data

### To CCD

CRDC uses NCESSCH identifiers, same as CCD:

```python
# Join CRDC to CCD
crdc = fetch("schools/crdc/discipline/2017")
ccd = fetch("schools/ccd/directory/2017")

merged = crdc.join(ccd, on="ncessch", how="left")
```

```r
# Join CRDC to CCD
crdc <- arrow::read_parquet("data/raw/schools_crdc_discipline_2017.parquet")
ccd <- arrow::read_parquet("data/raw/schools_ccd_directory.parquet") |> filter(year == 2017)

merged <- crdc |> left_join(ccd, by = "ncessch")
```

### Year Alignment

CRDC is generally biennial; align with correct CCD year:

| CRDC Collection | CCD Year to Use |
|-----------------|-----------------|
| 2017-18 CRDC | 2017-18 CCD |
| 2015-16 CRDC | 2015-16 CCD |

### Coverage Differences

Not all CCD schools are in CRDC (nonresponse and differing school universes, even in universe years):
- Check for nulls after merge
- Document schools dropped due to non-match

## Suppression

### Suppression Rules

Small cell sizes are suppressed for privacy:
- No fixed OCR cutoff: 2011-12 counts were rounded in groups of three; 2015-16 suppressed small cells and rounded other counts; 2020-21 onward uses small random perturbation plus data-quality suppression. Portal -3 marks suppressed values (check the codebook for the OCR-code mapping)
- Affects subgroup breakdowns
- More suppression in smaller schools

### Suppression Impact

```python
# Check suppression rate before analysis
def suppression_rate(df, variable):
    suppressed = df.filter(pl.col(variable) == -3).height
    total = df.height
    rate = suppressed / total * 100
    
    if rate > 10:
        print(f"WARNING: {rate:.1f}% of {variable} is suppressed")
        print("Subgroup analysis may be unreliable")
    
    return rate
```

```r
# Check suppression rate before analysis
suppressed <- df |> filter(.data[[variable]] == -3) |> nrow()
total <- nrow(df)
rate <- suppressed / total * 100

if (rate > 10) {
  cat(sprintf("WARNING: %.1f%% of %s is suppressed\n", rate, variable))
  cat("Subgroup analysis may be unreliable\n")
}
```

## Recommended Practices

### Before Analysis

1. **Check collection year and topic coverage** - universe since 2011-12, but topics vary by year
2. **Verify variable exists** - Not all variables all years
3. **Compare definitions** - Review codebook for your year
4. **Check suppression** - Especially for subgroup analysis
5. **Note COVID impact** - If using 2020-21 data

### For Discipline Analysis

1. **Calculate rates per enrollment** - Not raw counts
2. **Compare within similar school types** - Elementary vs. high school differ
3. **Consider policy context** - Zero-tolerance affects counts
4. **Document definition interpretation**

### For Time Series

1. **Use years in which your topic is collected** - all collections from 2011-12 on are universe
2. **Same schools across years** - Restrict to consistent sample
3. **Note definition changes**
4. **Exclude or flag 2020-21**

### For Equity Analysis

1. **Check suppression by subgroup** - Small groups often suppressed
2. **Use disparity ratios** - Compare to majority group
3. **Control for school characteristics**
4. **Document data limitations**

## Related Data Sources

| Source | Use When |
|--------|----------|
| CCD | Need school/district characteristics |
| EDFacts | Need assessment/graduation data |
| State administrative data | Need more detailed discipline records |
| OCR complaints | Need enforcement context |

## Quick Reference Card

| Task | Guidance |
|------|----------|
| Checking availability | CRDC is generally biennial (Portal 2011, 2013, 2015, 2017, 2020, 2021; some topics also 2022 or 2023) |
| Using early years | 2011-12 onward are universe collections; check topic availability |
| Discipline analysis | Rates, not counts; within-type comparisons |
| Subgroup analysis | Check suppression first |
| Time series | Check topic availability by year; flag COVID year (Portal 2020 = 2020-21) |
| Linking to CCD | Use NCESSCH; check coverage |
| COVID year | Do not compare directly to prior years |
| Course access | Distinguish offered vs. enrolled |
