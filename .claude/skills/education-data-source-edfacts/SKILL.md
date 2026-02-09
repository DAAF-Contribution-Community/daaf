---
name: education-data-source-edfacts
description: >-
  EDFacts state accountability data for K-12 assessments, graduation rates, and
  federal reporting. Use when working with state proficiency data, ACGR graduation
  rates, or ESSA accountability indicators. CRITICAL - state assessment scores
  CANNOT be compared across states.
metadata:
  audience: data-analysts
  domain: education-data
---

# EDFacts Data Source Reference

EDFacts is the U.S. Department of Education's centralized data collection system for pre-K through grade 12 education data from State Education Agencies (SEAs). It provides state assessment proficiency rates, graduation rates, and accountability indicators — the authoritative federal source for state-level K-12 outcome data.

> **CRITICAL: Value Encoding**
>
> The Urban Institute Education Data Portal converts NCES string codes (e.g., `ALL`, `CWD`, `LEP`) to **integer codes**. Always verify actual data values before filtering — do not rely on documentation labels alone.
>
> | Context | Subgroup "All" | English Learner | Sex "Male" |
> |---------|----------------|-----------------|------------|
> | **Portal integer** | `99` | `1` | `1` |
> | NCES string | `ALL` | `LEP` | `M` |
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is EDFacts?

- **Collector**: U.S. Department of Education, via State Education Agencies (SEAs)
- **Coverage**: All public schools and districts in 50 states + DC
- **Content**: State assessment proficiency rates, ACGR graduation rates, participation rates, accountability indicators
- **Frequency**: Annual collection
- **Available years**: Assessments 2009-10 to present; Graduation rates 2010-11 to present
- **Primary identifiers**: `ncessch` (12-char school ID), `leaid` (7-char district ID), `fips` (2-digit state code)
- **Key limitation**: State assessment scores CANNOT be compared across states (different tests, different cut scores)

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `accountability-context.md` | ESSA, NCLB history, accountability systems | Understanding policy context |
| `assessment-data.md` | Proficiency levels, test scores, limitations | Working with assessment data |
| `graduation-rates.md` | ACGR methodology, cohort definitions | Analyzing graduation data |
| `variable-definitions.md` | Key variables, suppression codes, special values | Interpreting specific variables |
| `data-quality.md` | Known issues, state variations, COVID impacts | Data cleaning, limitations |
| `subgroup-reporting.md` | Special populations, disaggregation | Analyzing by student groups |

## Decision Trees

### What type of analysis?

```
What EDFacts data do you need?
├─ Assessment/proficiency data
│   ├─ Within-state trends → Valid analysis
│   ├─ Cross-state comparison → INVALID - use NAEP instead
│   └─ Subgroup gaps → See ./references/subgroup-reporting.md
├─ Graduation rates (ACGR)
│   ├─ Understand methodology → See ./references/graduation-rates.md
│   ├─ Extended rates (5-year, 6-year) → See ./references/graduation-rates.md
│   └─ Subgroup rates → See ./references/subgroup-reporting.md
├─ Understanding variables
│   ├─ Missing/suppressed values → See ./references/variable-definitions.md
│   ├─ Range vs. exact values → See ./references/variable-definitions.md
│   └─ Subgroup codes → See ./references/subgroup-reporting.md
└─ Data quality concerns
    ├─ COVID-19 impacts (2019-20) → See ./references/data-quality.md
    ├─ State reporting changes → See ./references/data-quality.md
    └─ Suppression rates → See ./references/data-quality.md
```

### Is my comparison valid?

```
What are you comparing?
├─ Same state, different years
│   ├─ Same assessment system? → Valid
│   └─ Different tests? → Break in time series
├─ Schools within same state → Valid
├─ Districts within same state → Valid
├─ Subgroups within same school → Valid (check suppression)
├─ Different states
│   ├─ Proficiency rates → INVALID
│   ├─ Graduation rates (ACGR) → More comparable
│   └─ Use NAEP instead → Valid
└─ National ranking by proficiency → INVALID
```

## Quick Reference: EDFacts Data Elements

### Assessment Data

| Data Element | Description | Available Years |
|--------------|-------------|-----------------|
| Proficiency rates | % meeting state standards in reading/math | 2009-10 to present |
| Participation rates | % of students assessed | 2012-13 to present |
| Achievement levels | Below Basic, Basic, Proficient, Advanced | Varies by state |
| Grade levels | Grades 3-8, high school (varies) | 2009-10 to present |

### Graduation Data

| Data Element | Description | Available Years |
|--------------|-------------|-----------------|
| 4-year ACGR | Adjusted Cohort Graduation Rate | 2010-11 to present |
| 5-year ACGR | Extended graduation rate | 2011-12 to present |
| 6-year ACGR | Further extended rate | 2012-13 to present |
| Diploma types | Regular diploma only in ACGR | All years |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `ncessch` | 12-char | School | `060000000001` | NCES school ID |
| `leaid` | 7-char | District/LEA | `0600001` | NCES district ID |
| `fips` | 2-digit | State | `06` (California) | Federal state code |

### Data Levels

| Level | Identifier | EDFacts Endpoints |
|-------|------------|-------------------|
| School | `ncessch` (12-char) | `/schools/edfacts/` |
| District/LEA | `leaid` (7-char) | `/school-districts/edfacts/` |
| State | `fips` (2-digit) | Aggregate from lower levels |

### Subgroups Reported

| Subgroup | String Code | Portal Integer | Notes |
|----------|-------------|----------------|-------|
| All students | `ALL` | `99` | Total row (filter dimension) |
| Economically disadvantaged | `ECODIS` | `1` | In econ_disadvantaged column |
| Students with disabilities | `CWD` | See disability codes | IDEA-eligible students |
| English learners | `LEP` | `1` | In lep column |
| Homeless | `HOM` | `1` | In homeless column |
| Foster care | `FCS` | `1` | In foster_care column |
| Migrant | `MIG` | `1` | In migrant column |
| Military connected | `MIL` | `1` | In military_connected column |
| Race/ethnicity | Multiple | See race codes | Integer codes 1-99 |

**EDFacts Filter Column Pattern:**
- Special population columns (lep, disability, homeless, migrant, etc.) use `1` = subgroup, `99` = total
- Race column uses integer codes (1=White, 2=Black, etc.)
- Sex column uses `1` = Male, `2` = Female, `99` = Total

### Grade Codes (grade_edfacts)

| Code | Grade Level |
|------|-------------|
| `3`-`8` | Grades 3-8 (individual) |
| `9` | Grades 9-12 combined |
| `99` | Total (all grades) |

### Race Codes

| Code | Category |
|------|----------|
| `1` | White |
| `2` | Black |
| `3` | Hispanic |
| `4` | Asian |
| `5` | American Indian/Alaska Native |
| `6` | Native Hawaiian/Pacific Islander |
| `7` | Two or More Races |
| `8` | Nonresident alien |
| `9` | Unknown |
| `20` | Other |
| `99` | Total |
| `-1` | Missing/not reported |
| `-2` | Not applicable |
| `-3` | Suppressed |

### Sex Codes

| Code | Category |
|------|----------|
| `1` | Male |
| `2` | Female |
| `9` | Unknown |
| `99` | Total |

### Disability Codes

| Code | Category |
|------|----------|
| `0` | Students without disabilities |
| `1` | Students with disabilities served under IDEA |
| `2` | Students with disabilities served under Section 504 only |
| `3` | Students not served under IDEA |
| `4` | Students with disabilities (Section 504 and IDEA) |
| `99` | Total |

### LEP Codes

| Code | Category |
|------|----------|
| `1` | Students who are limited English proficient |
| `99` | All students (total) |

### Special Population Columns

For `homeless`, `migrant`, `econ_disadvantaged`, `foster_care`, `military_connected`:

| Code | Category |
|------|----------|
| `1` | Yes (in subgroup) |
| `99` | Total (all students) |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing/not applicable | Data not reported |
| `-2` | Not reported | Item doesn't apply to this entity |
| `-3` | Suppressed for privacy | Data suppressed for small N-size |
| `-9` | Rounds to zero | Value rounds to zero |
| Range values | Exact value suppressed | Range provided instead of exact value |
| `_midpt` suffix | Calculated midpoint of suppressed range | Use for analysis when exact values are suppressed |

**Always use `_midpt` variables for analysis when exact values are suppressed.**

## Data Access

### Dataset Paths

| Topic | Type | Huggingface Path |
|-------|------|------------------|
| School Assessments | Yearly (2009-2018, 2020) | `schools/edfacts/assessments/schools_edfacts_assessments_{year}` |
| School Grad Rates | Yearly (2010-2019) | `schools/edfacts/grad-rates/schools_edfacts_grad_rates_{year}` |
| District Assessments | Yearly (2009-2020) | `school-districts/edfacts/assessments/districts_edfacts_assessments_{year}` |
| District Grad Rates | Yearly (2010-2019) | `school-districts/edfacts/grad-rates/districts_edfacts_grad_rates_{year}` |

### Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| School Assessments | `schools/edfacts/assessments/codebook_schools_edfacts_assessments` |
| School Grad Rates | `schools/edfacts/grad-rates/codebook_schools_edfacts_grad_rates` |
| District Assessments | `school-districts/edfacts/assessments/codebook_districts_edfacts_assessments` |
| District Grad Rates | `school-districts/edfacts/grad-rates/codebook_districts_edfacts_grad_rates` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for full catalog and `fetch-patterns.md` for `get_codebook_url()`. For human reference — not parsed programmatically.

> **Note:** 2019 assessment data is NOT available due to COVID testing waivers.

### Example Fetch

```python
import polars as pl

# Assessment data (yearly file)
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/edfacts/assessments/schools_edfacts_assessments_2018.parquet"
df = pl.read_parquet(url)

# Filter by state and grade locally
df = df.filter(
    (pl.col("fips") == 6) &  # California
    (pl.col("grade_edfacts") == 4)  # Grade 4
)
```

### Filtering

```python
# Grade filtering: grade_edfacts uses integer codes
df = df.filter(pl.col("grade_edfacts") == 4)  # Grade 4
df = df.filter(pl.col("grade_edfacts") == 99)  # All grades combined

# Subgroup filtering: special population columns use 1/99 pattern
df_total = df.filter(pl.col("sex") == 99)  # All students (total)
df_econ = df.filter(pl.col("econ_disadvantaged") == 1)  # Economically disadvantaged only

# Race filtering: integer codes
df_black = df.filter(pl.col("race") == 2)  # Black students
```

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Ranking states by proficiency | Different tests, different cut scores make comparisons meaningless | Use NAEP for cross-state comparisons |
| Comparing 2019-20 to other years | COVID testing waivers created data gaps | Note data gap, exclude year |
| Ignoring suppression | Results biased toward larger schools/subgroups | Document suppression rates, use `_midpt` variables |
| Assuming proficiency = same thing | State definitions of "proficient" vary widely | Clarify each state's definition |
| Pre/post ESSA comparison | Different accountability systems (NCLB vs ESSA) | Note policy change at 2015 boundary |
| Using string codes for filtering | Portal uses integer encoding, not NCES strings | Always check actual data values; see encoding tables above |

## Key Policy Context

| Law | Years | Key Features |
|-----|-------|--------------|
| NCLB | 2002-2015 | AYP, 100% proficiency goal, HQT |
| ESSA | 2015-present | State flexibility, multiple indicators |

- **AYP (Adequate Yearly Progress)**: NCLB requirement eliminated by ESSA
- **ESSA Accountability**: States design own systems with federal guardrails
- **N-size**: Minimum students required for reporting (varies by state, typically 10-30)

## CRITICAL WARNING: Cross-State Comparisons

**State assessment proficiency rates CANNOT be compared across states.**

| Factor | Why It Varies |
|--------|---------------|
| Assessment content | Each state creates its own tests |
| Proficiency cut scores | Each state sets own thresholds |
| Standards alignment | State academic standards differ |
| Test difficulty | Not calibrated nationally |

A student "proficient" in one state may score "below basic" in another state taking a harder test with higher cut scores. **Rankings of states by proficiency rates are meaningless.**

Use NAEP (National Assessment of Educational Progress) for valid cross-state comparisons.

### Valid vs. Invalid Analysis Examples

**Valid Analysis:**

```python
# Within-state trend analysis
state_df = df.filter(pl.col("fips") == 6)  # California only
trend = state_df.group_by("year").agg(
    pl.col("read_test_pct_prof_midpt").mean()
)
# Valid: Same state, same test system
```

**INVALID Analysis:**

```python
# DO NOT DO THIS - Cross-state comparison
# This comparison is MEANINGLESS
state_comparison = df.group_by("fips").agg(
    pl.col("read_test_pct_prof_midpt").mean()
).sort("read_test_pct_prof_midpt", descending=True)
# INVALID: Different tests, different standards
```

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ccd` | CCD provides school/district demographics | Combining outcome data with school characteristics |
| `education-data-source-crdc` | CRDC has discipline, AP, school climate data | Analyzing school equity alongside achievement |
| `education-data-source-saipe` | SAIPE provides district poverty estimates | Linking poverty to achievement |
| `education-data-source-meps` | MEPS provides school poverty estimates | School-level poverty and assessment analysis |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| NCLB to ESSA transition | `./references/accountability-context.md` |
| State accountability systems | `./references/accountability-context.md` |
| Federal reporting requirements | `./references/accountability-context.md` |
| Proficiency levels | `./references/assessment-data.md` |
| Why states can't be compared | `./references/assessment-data.md` |
| NAEP comparison | `./references/assessment-data.md` |
| Assessment system changes | `./references/assessment-data.md` |
| ACGR calculation | `./references/graduation-rates.md` |
| Cohort adjustments | `./references/graduation-rates.md` |
| Extended graduation rates | `./references/graduation-rates.md` |
| Diploma types | `./references/graduation-rates.md` |
| Suppression codes | `./references/variable-definitions.md` |
| Missing data values | `./references/variable-definitions.md` |
| Range/midpoint variables | `./references/variable-definitions.md` |
| Participation rates | `./references/variable-definitions.md` |
| COVID-19 data gaps | `./references/data-quality.md` |
| State reporting variations | `./references/data-quality.md` |
| Known data issues | `./references/data-quality.md` |
| Time series breaks | `./references/data-quality.md` |
| Students with disabilities | `./references/subgroup-reporting.md` |
| English learners | `./references/subgroup-reporting.md` |
| Economically disadvantaged | `./references/subgroup-reporting.md` |
| Race/ethnicity reporting | `./references/subgroup-reporting.md` |
| Homeless/foster/migrant | `./references/subgroup-reporting.md` |
| N-size requirements | `./references/subgroup-reporting.md` |
