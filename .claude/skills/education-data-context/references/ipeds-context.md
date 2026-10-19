# Integrated Postsecondary Education Data System (IPEDS) Context

IPEDS is the primary source for data on colleges, universities, and other postsecondary institutions in the United States. In this system, IPEDS data is accessed through the Urban Institute Education Data Portal, which standardizes variable names to lowercase, applies integer encoding to categorical variables, and provides a curated subset of the full IPEDS survey universe.

## Source Overview

| Attribute | Value |
|-----------|-------|
| Collector | National Center for Education Statistics (NCES) |
| Respondents | All Title IV participating institutions |
| Coverage | ~5,800 Title IV institutions and administrative offices (5,829 in the 2024-25 collection), plus voluntary non-Title IV reporters |
| Frequency | Annual (multiple survey components) |
| Available Years | 1979-present in the mirror (varies by component; IPEDS replaced HEGIS in 1986, so pre-1986 years are HEGIS-era) |
| Mandate | Required for Title IV participation |

### Survey Components

| Component | Collection Period | Content |
|-----------|------------------|---------|
| Institutional Characteristics | Fall | Basic institution info; tuition and fees through 2023-24 (moved to the Cost (CST) component from 2024-25) |
| Fall Enrollment | Spring | Student counts by level, demographics |
| 12-Month Enrollment | Fall | Full academic year enrollment |
| Completions | Fall | Degrees/certificates awarded |
| Graduation Rates | Winter | Cohort completion outcomes |
| Student Financial Aid | Winter | Aid types, amounts, recipients |
| Finance | Spring | Revenues, expenditures, assets |
| Human Resources | Spring | Employees, salaries |
| Academic Libraries | Spring | Library resources (annual from the 2014-15 collection, biennial before; not in the current NCES component list) |

## Coverage

### What IPEDS Includes

- All institutions participating in Title IV federal student aid programs
- Public, private nonprofit, and for-profit institutions
- 2-year, 4-year, and less-than-2-year institutions
- Main campuses and branch campuses (separate UNITIDs)

### What IPEDS Excludes

| Excluded | Alternative |
|----------|-------------|
| Non-Title IV institutions | Report only voluntarily; coverage is partial |
| Some religious institutions | May self-exclude from aid programs |
| Non-degree vocational schools | Some included if Title IV |
| International students' home country institutions | N/A |

### Institutional Changes

Institutions can:
- **Change sector**: For-profit to nonprofit (common in recent years)
- **Merge**: Creates new UNITID for combined entity
- **Close**: Check institution status variables
- **Add/drop branches**: Each branch may have separate UNITID

## Graduation Rate Caveats

**CRITICAL**: IPEDS graduation rates have significant limitations that are often misunderstood.

### Who Is Tracked

IPEDS graduation rates track ONLY:
- **First-time students**: Never attended college before
- **Full-time students**: Enrolled full-time in their first term
- **Degree/certificate seeking**: Enrolled in a program
- **Started in fall term**: No spring, summer, or mid-year starts

### Who Is NOT Tracked

| Excluded Group | Size of Gap |
|----------------|-------------|
| Transfer students | Share varies (unsourced; compute from IPEDS transfer-in counts) |
| Part-time students | Share varies (compute from IPEDS Fall Enrollment) |
| Spring/summer starts | Varies by institution type |
| Returning adults | Large at community colleges |
| Students who transfer OUT | Not counted as completers |

### What This Means

For many institutions, especially community colleges:
- IPEDS graduation rates may cover a minority of students (illustrative; compute the FTFT share for your sample)
- Students who transfer to complete elsewhere count as non-completers
- Part-time students (majority at many schools) are invisible

### Transfer-Out Rates

IPEDS reports transfer-out rates separately:
- Students known to have transferred to another institution
- Does NOT track whether they completed at new institution
- Transfer-out ≠ failure to complete higher education

### Time to Completion

| Institution Type | "On Time" | 150% Time | 200% Time |
|-----------------|-----------|-----------|-----------|
| 4-year | 4 years | 6 years | 8 years |
| 2-year | 2 years | 3 years | 4 years |
| Less-than-2-year | <2 years | Varies | Varies |

Most reported rates use 150% time (6 years for 4-year schools).

### Calculating a More Complete Picture

```python
# IPEDS grad rate alone is incomplete
ipeds_grad_rate = completers_150pct / first_time_full_time_cohort

# Consider also examining:
# - Transfer-out rate
# - 200% graduation rate
# - Pell recipient graduation rate (for equity)
# - Part-time student outcomes (from Scorecard if available)
```

```r
# IPEDS grad rate alone is incomplete
ipeds_grad_rate <- completers_150pct / first_time_full_time_cohort

# Consider also examining:
# - Transfer-out rate
# - 200% graduation rate
# - Pell recipient graduation rate (for equity)
# - Part-time student outcomes (from Scorecard if available)
```

## Enrollment Data

### Fall Enrollment vs. 12-Month Enrollment

| Metric | Fall Enrollment | 12-Month Enrollment |
|--------|-----------------|---------------------|
| Timing | Point-in-time (fall census) | Full academic year |
| Use case | Comparing institution size | Unduplicated headcount |
| FTE calculation | Fall only | Full year |

### Full-Time Equivalent (FTE)

FTE = 12-month instructional activity ÷ a standard full-time load (semester calendars: undergraduate credit hours ÷ 30, graduate ÷ 24; divisors differ for quarter/clock-hour reporting). Institutions may report their own FTE (`rep_fte`) instead of the derived value (`est_fte`).

**Do not directly compare FTE across institutions without checking calendar system and reported (`rep_fte`) vs. derived (`est_fte`) values.**

### Enrollment Categories

| Category | Definition |
|----------|------------|
| First-time | Never attended any college |
| Transfer-in | Previously attended another institution |
| Continuing | Enrolled in prior year at same institution |
| Returning | Previously enrolled, skipped time |
| Graduate | Enrolled in master's, doctoral, professional |

## Finance Data

### GASB vs. FASB Accounting

**CRITICAL**: Public and private institutions use different accounting standards.

| Standard | Institution Type | Key Differences |
|----------|-----------------|-----------------|
| GASB | Public | Government accounting rules |
| FASB | Private nonprofit | Business accounting rules |
| FASB | Private for-profit | Business accounting rules |

**Implications:**
- Revenue and expense categories differ
- Direct comparisons across sectors are problematic
- Within-sector comparisons are valid

### Finance Categories

| Category | Public (GASB) | Private (FASB) |
|----------|---------------|----------------|
| Tuition revenue | Tuition and fees | Tuition and fees |
| State appropriations | Operating or non-operating | Reported when received (usually small or zero; Cornell, unitid 190415, reports $370M in Portal `year` 2017) |
| Federal grants | By source | By purpose |
| Endowment | Complex treatment | Net assets |

### Finance Data Lag

NCES releases provisional Finance data about 1.5 years after the fiscal year ends (final data about a year later), and the pinned mirror lags further (Finance ends at Portal `year` 2017 in mirror 0.26.1; the live Portal lists through 2023) (see `education-data-source-ipeds` § Data Availability & Lag Times). Contributing factors:
- Institutions report after fiscal year close
- Audited figures may be delayed
- Most recent year often incomplete

## Student Financial Aid

### Key Distinctions

| Population | Definition | Use |
|------------|------------|-----|
| First-time full-time | New students, full load | Comparable across institutions |
| All undergraduates | Everyone | Larger but heterogeneous |
| Full-time undergrads | Full load only | Middle ground |

### Net Price

Net price = Cost of attendance - Grant aid received

Reported by income bracket:
- $0-$30,000
- $30,001-$48,000
- $48,001-$75,000
- $75,001-$110,000
- $110,001+

**Caveats:**
- Average net price: full-time, first-time degree/certificate-seeking undergraduates awarded grant or scholarship aid (public institutions: in-state/in-district only)
- Net price by income: the subset of those students awarded Title IV aid
- Students with no grant aid (or, for by-income figures, no Title IV aid) are excluded
- Institutional aid varies significantly

### Aid Types

| Type | What It Includes |
|------|------------------|
| Federal grants | Pell, SEOG, other federal |
| State/local grants | State need-based, merit, etc. |
| Institutional grants | School-funded scholarships |
| Federal loans | Subsidized, unsubsidized, PLUS |

## Institutional Identifiers

### UNITID

- **Unique identifier** for each IPEDS reporting unit
- Assigned by NCES
- Generally one per campus
- Changes when: institution merges, closes/reopens, significant restructuring

### OPEID

- **Office of Postsecondary Education ID**
- Used for Title IV administration
- One OPEID may cover multiple UNITIDs (main + branches)

### OPEID6

- First 6 digits of OPEID
- Identifies institution family (main campus)
- 8-digit OPEID adds branch suffix

### Linking IPEDS to Other Data

```python
# IPEDS to Scorecard: both use UNITID
ipeds_data = fetch("college-university/ipeds/directory/2020")
scorecard_data = fetch("college-university/scorecard/earnings/2014")
merged = ipeds_data.join(scorecard_data, on="unitid", how="left")

# Note: Not all institutions in both sources
# Check for nulls after merge
```

```r
# IPEDS to Scorecard: both use UNITID
ipeds_data <- arrow::read_parquet("data/raw/colleges_ipeds_directory.parquet") |> filter(year == 2020)
scorecard_data <- arrow::read_parquet("data/raw/colleges_scorecard_earnings.parquet") |> filter(year == 2014)
merged <- ipeds_data |> left_join(scorecard_data, by = "unitid")

# Note: Not all institutions in both sources
# Check for NAs after merge
```

## Cohort Timing

Understanding when data refers to:

| Data Type | Year Field Meaning |
|-----------|-------------------|
| Institutional characteristics | As of fall of indicated year |
| Fall enrollment | As of fall census date |
| Completions | Academic year ENDING in the indicated year (`year`=2022 = 2021-22 awards; inferred, medium confidence — see education-data-source-ipeds) |
| Graduation rates | NOT the entry year: status is measured at the end of the `year` academic year (Aug 31 of `year`+1). Use `cohort_year` (4-year 150%: `year` − 5; less-than-4-year: `year` − 2; GR200/OM 4-year: `year` − 7) |
| Student financial aid | For indicated academic year |
| Finance | Fiscal year BEGINNING in the indicated year (`year`=2017 = FY2018, ending June 30, 2018 for June fiscal-year institutions) |

### Graduation Rate Timing Example

For `year=2015` graduation rate data (150% rates):
- 4-year institutions: cohort entered in fall 2010 (`cohort_year` = 2010)
- Less-than-4-year institutions: cohort entered in fall 2013 (`cohort_year` = 2013)
- 150% status measured as of August 31, 2016 for both (inference from the offsets)
- Always filter or label by the `cohort_year` column

## Common Analysis Mistakes

### Do Not:

1. **Use IPEDS grad rates as institutional quality measure**
   - Affected by student population, not just institution

2. **Compare grad rates across institution types**
   - Community colleges have different student populations

3. **Compare finance data across sectors**
   - GASB vs. FASB not directly comparable

4. **Assume net price is what students pay**
   - Based on aid recipients only; full-pay students excluded

5. **Use IPEDS to track transfer student outcomes**
   - Transfers counted as non-completers at origin

### Do:

1. **Compare within sector** (4-year public to 4-year public)
2. **Use cohort-appropriate benchmarks**
3. **Supplement with Scorecard** for outcomes of non-traditional students
4. **Note IPEDS limitations** in any analysis
5. **Check institutional status** before including (closed, merged, etc.)

## Data Quality Checks

```python
def ipeds_quality_check(df, institution_type="4-year"):
    checks = []
    
    # Check for plausible graduation rates (Portal rates are 0-1 proportions; -1/-2/-3 are missing codes)
    if "completion_rate_150pct" in df.columns:
        implausible = df.filter(
            (pl.col("completion_rate_150pct") > 1)
            | ((pl.col("completion_rate_150pct") < 0)
               & ~pl.col("completion_rate_150pct").is_in([-1.0, -2.0, -3.0]))
        )
        if implausible.height > 0:
            checks.append(f"Implausible grad rates: {implausible.height}")
    
    # Check enrollment consistency
    if all(c in df.columns for c in ["enrollment_ft", "enrollment_pt", "enrollment_total"]):
        inconsistent = df.filter(
            pl.col("enrollment_ft") + pl.col("enrollment_pt") != pl.col("enrollment_total")
        )
        if inconsistent.height > 0:
            checks.append(f"Enrollment inconsistencies: {inconsistent.height}")
    
    return checks
```

```r
# Check for plausible graduation rates (Portal rates are 0-1 proportions; -1/-2/-3 are missing codes)
if ("completion_rate_150pct" %in% names(df)) {
  implausible <- df |> filter(completion_rate_150pct > 1 |
    (completion_rate_150pct < 0 & !completion_rate_150pct %in% c(-1, -2, -3)))
  if (nrow(implausible) > 0) {
    cat(sprintf("Implausible grad rates: %d\n", nrow(implausible)))
  }
}

# Check enrollment consistency
if (all(c("enrollment_ft", "enrollment_pt", "enrollment_total") %in% names(df))) {
  inconsistent <- df |> filter(enrollment_ft + enrollment_pt != enrollment_total)
  if (nrow(inconsistent) > 0) {
    cat(sprintf("Enrollment inconsistencies: %d\n", nrow(inconsistent)))
  }
}
```

## Related Data Sources

| Source | Use When |
|--------|----------|
| College Scorecard | Need outcomes for non-traditional students |
| NSLDS | Need federal loan-level data |
| Census | Need local area demographics |
| BLS | Need labor market outcomes by field |
| State systems | Need state-specific details |

## Quick Reference Card

| Task | Guidance |
|------|----------|
| Comparing graduation rates | Within-sector only; note population limits |
| Analyzing finance | Keep GASB/FASB separate |
| Using net price | Note income bracket; aid recipients only |
| Linking institutions | Use UNITID; check OPEID for branches |
| Time series | Check for institutional changes, mergers |
| Understanding enrollment | Note FT vs. PT, fall vs. 12-month |
| Cohort graduation data | `year` ≠ entry year; use `cohort_year` (4-year: `year` − 5) |
| Transfer analysis | IPEDS doesn't track transfer outcomes |
