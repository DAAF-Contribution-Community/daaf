---
name: education-data-source-ipeds
description: Deep reference for IPEDS (Integrated Postsecondary Education Data System) - the primary federal data source on U.S. colleges and universities. Use when analyzing postsecondary data, understanding graduation rate limitations, comparing institution finances, interpreting enrollment metrics, or working with UNITID/OPEID identifiers.
metadata:
  audience: data-analysts
  domain: education-data
---

# IPEDS Data Source Reference

Comprehensive guide to understanding and using IPEDS data correctly. IPEDS is the most widely used source for postsecondary education data but has significant complexities and limitations that users must understand.

> **CRITICAL: Portal vs NCES Raw File Encoding**
>
> This document describes **Education Data Portal** integer encodings, which differ from NCES raw file string codes. The Portal converts categorical variables to integers for consistency across sources.
>
> | Context | Race White | Race Black | Sex Male | Sector Public 4-yr |
> |---------|------------|------------|----------|-------------------|
> | **Portal (integers)** | `1` | `2` | `1` | `1` |
> | NCES raw files | `EFFY_WHITE` | `EFFY_BKAA` | `M` | varies |
>
> **Always verify codes against Portal codebooks** (available at each endpoint in the HuggingFace mirror).

## What is IPEDS?

IPEDS (Integrated Postsecondary Education Data System) is a system of 12+ interrelated survey components:

- **Administered by**: National Center for Education Statistics (NCES)
- **Coverage**: ~6,500 Title IV-participating postsecondary institutions
- **Frequency**: Annual collection in three periods (Fall, Winter, Spring)
- **Mandate**: Required for Title IV federal student aid participation
- **Available years**: 1980-present (varies by component)

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `survey-components.md` | All 12+ IPEDS surveys with collection periods | Understanding data structure |
| `graduation-rates.md` | **CRITICAL** GRS limitations and who is tracked | Any graduation rate analysis |
| `enrollment-data.md` | Fall vs 12-month, FTE calculations | Enrollment comparisons |
| `finance-data.md` | GASB vs FASB accounting standards | Cross-sector finance analysis |
| `financial-aid.md` | Net price, aid types, populations | Aid and cost analysis |
| `institution-identifiers.md` | UNITID, OPEID, mergers, closures | Data linking and longitudinal work |
| `completions-data.md` | Degrees awarded, CIP codes | Completions and outcomes |
| `data-quality.md` | Known issues, sector comparisons | Quality assurance |

## Decision Trees

### What data am I working with?

```
Working with IPEDS data?
├─ Graduation rates → ./references/graduation-rates.md (READ FIRST!)
├─ Enrollment counts → ./references/enrollment-data.md
├─ Finance/revenue/expenses → ./references/finance-data.md
├─ Financial aid/net price → ./references/financial-aid.md
├─ Degrees/completions → ./references/completions-data.md
├─ Institutional info → ./references/survey-components.md (IC section)
├─ Human resources/salaries → ./references/survey-components.md (HR section)
└─ Linking to other data → ./references/institution-identifiers.md
```

### Is my analysis valid?

```
Cross-sector comparison?
├─ Comparing grad rates across sectors
│   └─ CAUTION: Different populations → ./references/graduation-rates.md
├─ Comparing finances across sectors
│   └─ CAUTION: GASB vs FASB → ./references/finance-data.md
├─ Comparing net price across sectors
│   └─ CAUTION: Aid populations differ → ./references/financial-aid.md
└─ Time series analysis
    └─ Check for institutional changes → ./references/institution-identifiers.md
```

### Finding specific variables?

```
Need variable definitions?
├─ Survey component overview → ./references/survey-components.md
├─ Graduation cohort definitions → ./references/graduation-rates.md
├─ Enrollment level/status → ./references/enrollment-data.md
├─ Revenue/expense categories → ./references/finance-data.md
├─ Aid types and populations → ./references/financial-aid.md
└─ CIP codes for programs → ./references/completions-data.md
```

## Quick Reference: Survey Components

| Component | Abbrev | Collection | Key Content |
|-----------|--------|------------|-------------|
| Institutional Characteristics | IC | Fall | Directory, tuition, mission |
| 12-Month Enrollment | E12 | Fall | Unduplicated headcount, FTE |
| Completions | C | Fall | Degrees by CIP, demographics |
| Cost | CST | Fall/Winter | Cost of attendance, net price |
| Admissions | ADM | Winter | Applications, admits, enrollees |
| Student Financial Aid | SFA | Winter | Aid counts and amounts |
| Graduation Rates | GR | Winter | 150% completion rates |
| Graduation Rates 200% | GR200 | Winter | 200% completion rates |
| Outcome Measures | OM | Winter | Part-time and transfer outcomes |
| Fall Enrollment | EF | Spring | Point-in-time enrollment |
| Finance | F | Spring | Revenue, expenses, assets |
| Human Resources | HR | Spring | Employees, salaries |
| Academic Libraries | AL | Spring | Library resources (biennial) |

## Quick Reference: Institution Types

### Portal Integer Encoding

| Variable | Values | Meaning |
|----------|--------|---------|
| `inst_control` | 1 | Public |
| | 2 | Private nonprofit |
| | 3 | Private for-profit |
| | -1 | Missing/not reported |
| `institution_level` | 1 | Less than 2-year |
| | 2 | 2-year (at least 2 but less than 4) |
| | **4** | 4-year or above |
| | -1 | Missing/not reported |
| `sector` | 0 | Administrative unit |
| | 1 | Public, 4-year or above |
| | 2 | Private not-for-profit, 4-year or above |
| | 3 | Private for-profit, 4-year or above |
| | 4 | Public, 2-year |
| | 5 | Private not-for-profit, 2-year |
| | 6 | Private for-profit, 2-year |
| | 7 | Public, less-than 2-year |
| | 8 | Private not-for-profit, less-than 2-year |
| | 9 | Private for-profit, less-than 2-year |
| | -1 | Sector unknown (not active) |
| `hbcu` | 1 | Historically Black College/University |
| | 0 | Not HBCU |
| `tribal_college` | 1 | Tribal College |
| | 0 | Not Tribal College |
| `degree_granting` | 1 | Degree-granting |
| | 0 | Non-degree-granting |

**Note:** There is **no code 3** for `institution_level`. This is a common source of confusion. The API uses codes 1, 2, 4 (not 1, 2, 3).

## Quick Reference: Demographic Codes

### Race/Ethnicity (Portal Integer Encoding)

| Code | Category | Notes |
|------|----------|-------|
| `1` | White | Single race, non-Hispanic |
| `2` | Black | Single race, non-Hispanic |
| `3` | Hispanic | Any race |
| `4` | Asian | Single race, non-Hispanic |
| `5` | American Indian/Alaska Native | Single race, non-Hispanic |
| `6` | Native Hawaiian/Pacific Islander | Single race, non-Hispanic |
| `7` | Two or more races | Multiple races selected, non-Hispanic |
| `8` | Nonresident alien | International students |
| `9` | Unknown | Race/ethnicity unknown |
| `20` | Other | Other race/ethnicity |
| `99` | Total | All races combined |
| `-1` | Missing/not reported | |
| `-2` | Not applicable | |
| `-3` | Suppressed | Privacy protection |

> **Historical note:** Prior to 2010, Asian included Pacific Islanders (code 6 did not exist), and "Two or more races" (code 7) was not collected.

### Sex (Portal Integer Encoding)

| Code | Category |
|------|----------|
| `1` | Male |
| `2` | Female |
| `3` | Nonbinary/Another gender |
| `4` | Unknown/Prefer not to say |
| `9` | Unknown |
| `99` | Total |
| `-1` | Missing/not reported |
| `-2` | Not applicable |
| `-3` | Suppressed |

> **Note:** Codes 3 and 4 are recent additions for non-binary gender reporting. Historical data may only have codes 1, 2, and 99. The exact meaning of codes 3 vs 4 may vary by endpoint - check the specific codebook.

## Critical Limitations Summary

### Graduation Rates (GRS)

**CRITICAL**: IPEDS graduation rates track ONLY first-time, full-time, fall-entering students.

| Excluded Population | Approximate % of Undergrads |
|---------------------|----------------------------|
| Transfer students | ~40% |
| Part-time students | ~40% |
| Spring/summer starts | Varies |
| Students who transfer OUT | Counted as non-completers |

**At community colleges, IPEDS grad rates may represent <25% of students.**

See `./references/graduation-rates.md` for complete details.

### Finance Data

**CRITICAL**: Public and private institutions use different accounting standards.

| Standard | Institution Type | Comparison |
|----------|-----------------|------------|
| GASB | Public | Compare within sector only |
| FASB | Private nonprofit | Different from GASB |
| FASB | Private for-profit | Different revenue treatment |

See `./references/finance-data.md` for crosswalk guidance.

### Net Price

Net price is calculated ONLY for:
- First-time, full-time students
- Who received Title IV aid
- Excludes full-pay students

See `./references/financial-aid.md` for details.

## Quick Reference: Year Field Meanings

| Data Type | Year Field Meaning |
|-----------|--------------------|
| Institutional characteristics | As of fall of indicated year |
| Fall enrollment | As of fall census date |
| 12-month enrollment | July 1 to June 30 academic year |
| Completions | Awarded during academic year |
| Graduation rates | **Cohort entered** in indicated year |
| Finance | Fiscal year ending in indicated year |
| Student financial aid | For indicated academic year |

## Common Analysis Mistakes

### Do NOT:

1. Use IPEDS grad rates as sole quality measure
2. Compare grad rates across institution types without adjusting for population
3. Compare finance data across GASB/FASB sectors directly
4. Assume net price represents all students
5. Use IPEDS to track transfer student outcomes
6. Ignore institutional mergers/closures in time series

### DO:

1. Compare within sector and Carnegie class
2. Use Outcome Measures (OM) for part-time/transfer data
3. Note all limitations in analysis
4. Check institutional status before including
5. Use appropriate cohort definitions
6. Supplement with College Scorecard for non-traditional students

## Data Quality Checklist

```python
def ipeds_quality_check(df):
    """Basic IPEDS data quality checks."""
    issues = []
    
    # Check graduation rates are 0-100
    if "grad_rate_150" in df.columns:
        bad = df.filter(
            (pl.col("grad_rate_150") > 100) | 
            (pl.col("grad_rate_150") < 0)
        )
        if bad.height > 0:
            issues.append(f"Invalid grad rates: {bad.height} rows")
    
    # Check for closed institutions
    if "inst_status" in df.columns:
        closed = df.filter(pl.col("inst_status") != 1)
        if closed.height > 0:
            issues.append(f"Non-active institutions: {closed.height}")
    
    # Check sector consistency
    if "inst_control" in df.columns:
        invalid = df.filter(~pl.col("inst_control").is_in([1, 2, 3]))
        if invalid.height > 0:
            issues.append(f"Invalid control codes: {invalid.height}")
    
    return issues
```

## Related Data Sources

| Source | Use When | Link Key |
|--------|----------|----------|
| College Scorecard | Non-traditional student outcomes | UNITID |
| FSA (Federal Student Aid) | Detailed loan/grant data | OPEID |
| BPS (Beginning Postsecondary Students) | Student-level trajectories | N/A (sample) |
| NSLDS | Individual loan records | N/A (restricted) |
| State longitudinal systems | State-specific outcomes | Varies |

## Education Data Portal API Gotchas

> **Data Retrieval:** For mirror-based data fetching patterns and filtering, see the `education-data-query` skill.

### IPEDS Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| Directory | `college-university/ipeds/directory/codebook_colleges_ipeds_directory` |
| Admissions Enrollment | `college-university/ipeds/admissions-enrollment/codebook_colleges_ipeds_admissions-enrollment` |
| Enrollment FTE | `college-university/ipeds/enrollment-full-time-equivalent/codebook_colleges_ipeds_enrollment-fte` |
| Graduation Rates | `college-university/ipeds/grad-rates/codebook_colleges_ipeds_grad-rates` |
| Finance | `college-university/ipeds/finance/codebook_colleges_ipeds_finance` |

> 32 IPEDS codebooks exist total (one per survey component). See `datasets-reference.md` for the complete list. Codebooks are `.xls` files on both mirrors. For human reference — not parsed programmatically.

### Data Availability & Lag Times

IPEDS data becomes available with significant lag. Always verify year availability before committing to a year range.

| Survey Component | Typical Lag | Latest Available (as of Jan 2026) |
|------------------|-------------|-----------------------------------|
| **Directory** | ~1 year | 2023 |
| **Admissions-Enrollment** | ~2 years | 2022 |
| **Fall Enrollment** | ~2-3 years | 2021 |
| **Completions** | ~2 years | Varies |
| **Finance** | ~4+ years | **2017** (see warning below) |
| **Graduation Rates** | ~2-3 years | 2021 |

> **CRITICAL: IPEDS Finance Data Cutoff.** As of January 2026, IPEDS Finance data is only available through **2017**. This affects endowment values (`endowment_end`), revenue/expense data, and any financial ratios. Options: (1) limit analysis to available years, (2) use NCCS 990 data for private institutions as an alternative, or (3) forward-fill with a documented caveat and indicator column.

### Admissions Data: Sex Disaggregation

**CRITICAL:** Admissions data is disaggregated by sex. You must filter to `sex=99` for institution totals:

```python
# WRONG - includes duplicates (~26K rows with multiple sex values per institution)
df = pl.read_parquet("admissions.parquet")

# CORRECT - one row per institution-year (~8K rows)
df_totals = df.filter(pl.col("sex") == 99)
```

| Sex Value | Meaning |
|-----------|---------|
| 1 | Male |
| 2 | Female |
| 3 | Nonbinary/Another gender |
| 9 | Unknown |
| **99** | **Total (use this for institution totals)** |

> **Note:** Code 3 (Nonbinary) was added recently. In older data or some endpoints, you may only see codes 1, 2, and 99.

### Variable Name Mappings

The API uses different names than documentation:

| Documented Name | Actual API Name |
|-----------------|-----------------|
| `inst_level` | `institution_level` |
| `applicants_total` | `number_applied` |
| `admissions_total` | `number_admitted` |
| `grad_rate_150pct` | `completion_rate_150pct` |

### Admission Rate Must Be Calculated

The API does **NOT** provide `admit_rate`. Calculate manually:

```python
df = df.with_columns(
    (pl.col("number_admitted") / pl.col("number_applied") * 100).alias("admit_rate")
)
```

### Fall Enrollment: FTE Only

The fall-enrollment endpoint provides **FTE (Full-Time Equivalent)**, NOT headcount:
- `est_fte` - Estimated FTE enrollment
- `rep_fte` - Reported FTE enrollment

**Data lag:** Fall enrollment typically has a **2-3 year lag**.

### Path Segments That Fail

| Fails (HTTP 500) | Works |
|------------------|-------|
| `/fall-enrollment/2021/undergrad/` | `/fall-enrollment/2021/?level_of_study=1` |

### Enrollment Endpoint Confusion

The API has two enrollment endpoints that BOTH return FTE data:
- `/ipeds/fall-enrollment/` - Returns `est_fte`, `rep_fte`
- `/ipeds/enrollment-headcount/` - Despite the name, also returns FTE-style data

Neither provides traditional headcount enrollment.

### `inst_size` is Categorical

The `inst_size` variable is a **category code (1-5)**, not an actual enrollment count:

| Code | Meaning |
|------|---------|
| 1 | Under 1,000 |
| 2 | 1,000 - 4,999 |
| 3 | 5,000 - 9,999 |
| 4 | 10,000 - 19,999 |
| 5 | 20,000 and above |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Survey components overview | `./references/survey-components.md` |
| Graduation rate cohort definition | `./references/graduation-rates.md` |
| First-time full-time limitation | `./references/graduation-rates.md` |
| Transfer-out rates | `./references/graduation-rates.md` |
| Outcome Measures survey | `./references/graduation-rates.md` |
| 150% vs 200% time | `./references/graduation-rates.md` |
| Fall enrollment | `./references/enrollment-data.md` |
| 12-month enrollment | `./references/enrollment-data.md` |
| FTE calculations | `./references/enrollment-data.md` |
| Enrollment by level | `./references/enrollment-data.md` |
| GASB accounting | `./references/finance-data.md` |
| FASB accounting | `./references/finance-data.md` |
| Revenue categories | `./references/finance-data.md` |
| Expense categories | `./references/finance-data.md` |
| Net price definition | `./references/financial-aid.md` |
| Pell grant data | `./references/financial-aid.md` |
| Aid by income level | `./references/financial-aid.md` |
| UNITID | `./references/institution-identifiers.md` |
| OPEID | `./references/institution-identifiers.md` |
| Institutional mergers | `./references/institution-identifiers.md` |
| Sector changes | `./references/institution-identifiers.md` |
| CIP codes | `./references/completions-data.md` |
| Award levels | `./references/completions-data.md` |
| Completers vs completions | `./references/completions-data.md` |
| Data quality issues | `./references/data-quality.md` |
| Missing data codes | `./references/data-quality.md` |
| Sector comparisons | `./references/data-quality.md` |
