---
name: education-data-source-crdc
description: >-
  CRDC — OCR civil rights collection for U.S. public schools; Portal families have topic-specific coverage from 2011 through 2022. Discipline, course access, harassment, restraint/seclusion by race/sex/disability/EL. Use for civil rights and equity analysis. Official evidence identifies 2013-14 as a universe collection; 2020-21 is COVID-impacted.
metadata:
  audience: any-agent
  domain: data-source
  skill-authored: "2026-02-09"
  skill-last-updated: "2026-08-06"
---

# CRDC Data Source Reference

Civil Rights Data Collection (CRDC) — mandatory OCR collection measuring educational opportunity and civil rights compliance in U.S. public schools. Portal dataset families have topic-specific coverage from 2011 through 2022; use them for school discipline disparities, course access equity, harassment, restraint/seclusion, or chronic absenteeism by race, sex, disability, and English learner status. The 2013-14 collection was officially a universe collection covering 16,758 districts and 95,507 schools; this skill does not make an unverified coverage claim for 2011-12. The 2020-21 collection is COVID-impacted and not directly comparable to ordinary years.

The Civil Rights Data Collection is a mandatory biennial survey of all U.S. public schools measuring educational opportunity and civil rights compliance. It is the only national source for school-level discipline disparities, course access equity, harassment, and restraint/seclusion data disaggregated by race, sex, disability, and English learner status.

> **CRITICAL: Value Encoding**
>
> The Education Data Portal uses **integer codes**, not the string codes shown in OCR documentation. Always filter using integers.
>
> | Variable | String Code (Raw) | Portal Integer |
> |----------|-------------------|----------------|
> | Race: White | `WH` | `1` |
> | Race: Black | `BL` | `2` |
> | Race: Hispanic | `HI` | `3` |
> | Sex: Male | `M` | `1` |
> | Sex: Female | `F` | `2` |
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is CRDC?

The Civil Rights Data Collection is a **mandatory OCR collection** of public schools and districts that measures educational opportunity and civil rights compliance:

- **Collector**: U.S. Department of Education, Office for Civil Rights (OCR)
- **Purpose**: Enforce civil rights laws, identify discrimination, monitor equity
- **Coverage**: Collection-specific; official evidence establishes 2013-14 as a universe collection. Verify 2011-12 against its own authoritative documentation rather than applying a blanket early-year label.
- **Cadence**: Usually organized by school-year collection cycles, historically often biennial, but not governed by an odd/even parity rule; 2020-21 and 2021-22 are consecutive collections
- **Disaggregation**: Race/ethnicity, sex, disability status, English learner status
- **History**: Collected since 1968 (as Elementary and Secondary School Civil Rights Survey)
- **Portal coverage (v2 mirror, build validated 2026-08-06)**: Topic-specific families spanning **2011 through 2022** (content-based year range confirmed in the v2 build); year availability differs by topic
- **Available through**: Education Data Portal mirrors

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `civil-rights-context.md` | Legal framework (Title VI, IX, Section 504, IDEA) | Understanding why data is collected |
| `data-elements.md` | All data categories and what's collected | Planning analysis, identifying variables |
| `collection-methodology.md` | Sampling, universe, timeline, reporting | Understanding coverage limitations |
| `variable-definitions.md` | Key variables, codes, disaggregation categories | Coding data, interpreting values |
| `data-quality.md` | Known issues, suppression, state variations | Addressing limitations in analysis |
| `historical-changes.md` | Evolution across collection years | Time series analysis, year comparison |

## Decision Trees

### What CRDC data do I need?

```
Research topic?
├─ School discipline
│   ├─ Suspensions (ISS/OSS) → ./references/data-elements.md#discipline
│   ├─ Expulsions → ./references/data-elements.md#discipline
│   ├─ Referrals to law enforcement → ./references/data-elements.md#discipline
│   ├─ School-related arrests → ./references/data-elements.md#discipline
│   └─ Preschool suspensions → ./references/data-elements.md#discipline
├─ Restraint and seclusion
│   └─ Physical restraint, mechanical, seclusion → ./references/data-elements.md#restraint-seclusion
├─ Harassment and bullying
│   ├─ Allegations by type → ./references/data-elements.md#harassment
│   └─ Disciplined for harassment → ./references/data-elements.md#harassment
├─ Course access and enrollment
│   ├─ AP/IB courses → ./references/data-elements.md#advanced-courses
│   ├─ Gifted/talented → ./references/data-elements.md#gifted-talented
│   ├─ Math/science courses → ./references/data-elements.md#course-access
│   └─ Computer science → ./references/data-elements.md#course-access
├─ Chronic absenteeism
│   └─ Students missing 15+ days → ./references/data-elements.md#chronic-absenteeism
├─ Special populations
│   ├─ Students with disabilities (IDEA) → ./references/data-elements.md#students-with-disabilities
│   ├─ English learners → ./references/data-elements.md#english-learners
│   └─ Preschool enrollment → ./references/data-elements.md#preschool
├─ School staffing
│   ├─ Teacher experience/certification → ./references/data-elements.md#staffing
│   └─ Counselors, nurses, etc. → ./references/data-elements.md#staffing
└─ School safety
    └─ Offenses, violence, weapons → ./references/data-elements.md#school-offenses
```

### Understanding the legal context?

```
Civil rights law question?
├─ Race/ethnicity discrimination → ./references/civil-rights-context.md#title-vi
├─ Sex/gender discrimination → ./references/civil-rights-context.md#title-ix
├─ Disability discrimination → ./references/civil-rights-context.md#section-504
├─ Special education services → ./references/civil-rights-context.md#idea
├─ Age discrimination → ./references/civil-rights-context.md#age-discrimination-act
└─ OCR enforcement process → ./references/civil-rights-context.md#ocr-enforcement
```

### Data quality concerns?

```
Data quality issue?
├─ Missing or suppressed data → ./references/data-quality.md#suppression
├─ Definition inconsistencies → ./references/data-quality.md#definition-variation
├─ Year-to-year comparability → ./references/historical-changes.md
├─ COVID-19 impact (2020-21) → ./references/data-quality.md#covid-impact
├─ Underreporting concerns → ./references/data-quality.md#underreporting
└─ State-level variations → ./references/data-quality.md#state-variations
```

## Quick Reference: CRDC Data Categories

### Collection Years

| School Year | Coverage status | Scale / Portal note | Key Notes |
|-------------|-----------------|---------------------|-----------|
| 2011-12 | Not re-verified in this correction cycle | Portal families include 2011 for some topics | Consult collection-specific authoritative documentation before generalizing |
| 2013-14 | **Universe** | 16,758 districts; 95,507 schools (First Look figure; the revised target population was 95,958 schools) | Official first-look evidence explicitly calls this a universe collection |
| 2015-16 | Universe collection | ~96,000 schools | Chronic absenteeism added |
| 2017-18 | Universe collection | ~96,000 schools | Expanded variables |
| 2020-21 | Universe collection | ~97,500 schools | COVID-impacted year |
| 2021-22 | Universe collection | ~98,000 schools; selected Portal topics reach 2022 | Consecutive collection after 2020-21 |
| 2023-24 | No Portal data established | No Portal CRDC 2024 data as of the probes: original 2026-08-06 probe errored (HTTP 500; exact endpoint not recorded), and a 2026-08-07 re-probe of `https://educationdata.urban.org/api/v1/schools/crdc/enrollment/2024/` returned HTTP 404 — either way zero rows | Do not infer 2024 data from the count of dataset families |

**Cadence:** CRDC is organized by school-year collection cycles and is often described as biennial, but there is no valid odd/even-year rule. Portal year labels represent the terminal year of the school year; 2020 and 2021 are consecutive available collection labels. Re-probed 2026-08-06: `chronic-absenteeism/2022/race/sex/` returned rows (HTTP 200), while a direct 2024 CRDC enrollment probe returned no rows (the original 2026-08-06 probe errored HTTP 500 with the exact endpoint not recorded; a 2026-08-07 re-probe of `https://educationdata.urban.org/api/v1/schools/crdc/enrollment/2024/` returned HTTP 404).

> **Source verification (accessed 2026-07-21):** [Official 2013-14 first look](https://www.ed.gov/about/offices/list/ocr/docs/crdc-2013-14.html), [Portal endpoint catalog](https://educationdata.urban.org/api/v1/api-endpoints/), and [Portal bulk manifest](https://educationdata.urban.org/api/v1/api-downloads/).

### Data Categories

| Category | Description | Disaggregation |
|----------|-------------|----------------|
| **Enrollment** | Student counts by grade level | Race, sex, disability, LEP |
| **Discipline** | Suspensions, expulsions, arrests | Race, sex, disability, LEP |
| **Restraint/Seclusion** | Physical/mechanical restraint, seclusion | Race, sex, disability |
| **Harassment** | Allegations and discipline by type | Race, sex, disability |
| **Course Access** | AP, IB, math, science, CS offerings | School-level, enrollment by race/sex |
| **Chronic Absenteeism** | 15+ days missed | Race, sex, disability, LEP |
| **Staffing** | Teachers, counselors, nurses, etc. | FTE counts, qualifications |
| **Offenses** | Violence, weapons, drugs at school | Type of offense |
| **Retention** | Students retained in grade | Race, sex, disability |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `crdc_id` | 12-digit string | School | `010000201705` | Primary CRDC identifier; always present |
| `ncessch` | 12-digit string | School | `010000201705` | NCES school ID, joins to CCD; may be null for some entries |
| `leaid` | 7-digit string | District | `0100002` | NCES district ID, joins to CCD; always present |

> **Note:** The OCR-internal `combokey` (e.g., `AL-0010-00002`) does NOT appear as a column in Portal data. Use `crdc_id` or `ncessch` for school-level identification.

> **WARNING: String Type Override Required.** When reading CRDC data from CSV, `ncessch`, `leaid`, and `crdc_id` must be read as String (`pl.Utf8`) via `schema_overrides`. Polars infers these as Int64, silently destroying leading zeros for ~19% of rows (FIPS 01-09 states: AL, AK, AZ, AR, CA, CO, CT). In R, `readr::read_csv()` has the identical failure mode — apply the same guard with `col_types = cols(ncessch = col_character(), leaid = col_character(), crdc_id = col_character())`. Parquet files preserve whatever dtype the file was written with — and that dtype is **not** uniformly String across CRDC files. A 2026-08-07 per-file audit found id typing is heterogeneous even within the 2020 vintage (e.g. `school_characteristics` all String, but `enrollment_k12_2020` `crdc_id` and `harass_bully_students_2020` all three ids are Int64). Do not assume a parquet read yields String ids — inspect the schema and normalize/cast on read. See `references/data-quality.md` § Identifier Typing for the per-file evidence.

### Race/Ethnicity (Portal Integer Codes)

| Code | Category |
|------|----------|
| `1` | White |
| `2` | Black or African American |
| `3` | Hispanic/Latino of any race |
| `4` | Asian |
| `5` | American Indian or Alaska Native |
| `6` | Native Hawaiian or Other Pacific Islander |
| `7` | Two or more races |
| `99` | Total |

> **Empirically observed values:** Codes `1`-`7` and `99` appear in CRDC data. Additional codes (`8` Nonresident alien, `9` Unknown, `20` Other) are defined in the codebook but are not observed in practice for K-12 CRDC datasets. See `variable-definitions.md` for the full codebook listing.

### Sex (Portal Integer Codes)

| Code | Category |
|------|----------|
| `1` | Male |
| `2` | Female |
| `3` | Non-binary/other (newer collections; rows exist but mostly contain -1 or -2 values) |
| `99` | Total |

### Disability Status (Portal Integer Codes)

| Code | Category |
|------|----------|
| `0` | Students without disabilities |
| `1` | Students with disabilities (served under IDEA) |
| `2` | Students with Section 504 only |
| `3` | Students not served under IDEA (includes 504-only and non-disabled) |
| `4` | Students with disabilities (combined: IDEA + Section 504) |
| `99` | Total |

> **Note:** Not all disability codes appear in every dataset. Enrollment data typically has `[1, 2, 99]`; discipline data has `[0, 1, 2, 4, 99]`. Verify codes against the live codebook for your specific dataset.

### English Learner Status (Portal Integer Codes)

| Code | Category |
|------|----------|
| `1` | English learner (EL/LEP) |
| `99` | All students |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing | Data not reported by school/district |
| `-2` | Not applicable | Item doesn't apply to this entity |
| `-3` | Suppressed | Data suppressed for privacy (small cell sizes) |
| `-9` | Skip pattern | Question not asked in this collection year (rare; check codebook) |
| `null` | Not available | Value absent from dataset (e.g., `ncessch` is null for some schools) |

> Verify these codes against the live codebook for your specific dataset. Use `get_codebook_url()` from `fetch-patterns.md`.

## Data Access

Datasets for CRDC are available via the Education Data Portal mirror system. See `datasets-reference.md` for canonical paths, `mirrors.yaml` for mirror configuration, and `fetch-patterns.md` for fetch code patterns including `fetch_from_mirrors()` and `fetch_yearly_from_mirrors()`.

**Portal bulk family inventory observed 2026-07-21 (24 families: 10 year-sharded, 14 multi-year/single-file):**

| Dataset family | Path | Type | Codebook |
|---------|------|------|----------|
| Discipline | `crdc/schools_crdc_discipline_k12_{year}` | Yearly | `crdc/codebook_schools_crdc_discipline` |
| AP/IB Enrollment | `crdc/schools_crdc_apib_enroll` | Single | `crdc/codebook_schools_crdc_ap-ib-enrollment` |
| Enrollment | `crdc/schools_crdc_enrollment_k12_{year}` | Yearly | `crdc/codebook_schools_crdc_enrollment` |
| Chronic Absenteeism | `crdc/schools_crdc_chronic_absenteeism_{year}` | Yearly | `crdc/codebook_schools_crdc_chronic-absenteeism` |
| Harassment/Bullying | `crdc/schools_crdc_harass_bully_students_{year}` | Yearly | `crdc/codebook_schools_crdc_harrassment-bullying-students` |
| Restraint/Seclusion | `crdc/schools_crdc_restraint_seclusion_students_{year}` | Yearly | `crdc/codebook_schools_crdc_restraint-seclusion-students` |
| Algebra | `crdc/schools_crdc_algebra_{year}` | Yearly | `crdc/codebook_schools_crdc_algebra-1` |
| AP Exams | `crdc/schools_crdc_ap_exams_{year}` | Yearly | `crdc/codebook_schools_crdc_ap-exams` |
| Retention | `crdc/schools_crdc_retention_{year}` | Yearly | `crdc/codebook_schools_crdc_retention` |
| SAT/ACT Participation | `crdc/schools_crdc_sat_and_act_participation_{year}` | Yearly | `crdc/codebook_schools_crdc_sat-act-participation` |
| COVID Indicators | `crdc/schools_crdc_covid_indicators` | Single | `crdc/codebook_schools_crdc_covid_indicators` |
| Credit Recovery | `crdc/schools_crdc_credit_recovery` | Single | `crdc/codebook_schools_crdc_credit-recovery` |
| Directory/Characteristics | `crdc/schools_crdc_school_characteristics` | Single | `crdc/codebook_schools_crdc_directory` |
| Discipline Instances | `crdc/schools_crdc_disciplineinstances` | Single | `crdc/codebook_schools_crdc_discipline_instances` |
| Dual Enrollment | `crdc/schools_crdc_dual_enrollment` | Single | `crdc/codebook_schools_crdc_dual_enrollment` |
| Harassment/Bullying Allegations | `crdc/schools_crdc_harass_bully_allegations` | Single | `crdc/codebook_schools_crdc_harrassment-bullying-allegations` |
| Internet Access | `crdc/schools_crdc_internet_access` | Single | `crdc/codebook_schools_crdc_internet_access` |
| Math and Science | `crdc/schools_crdc_mathandscience` | Single | `crdc/codebook_schools_crdc_math-and-science` |
| Offenses | `crdc/schools_crdc_offenses` | Single | `crdc/codebook_schools_crdc_offenses` |
| Offerings | `crdc/schools_crdc_offerings` | Single | `crdc/codebook_schools_crdc_offerings` |
| Restraint/Seclusion Instances | `crdc/schools_crdc_restraint_seclusion_instances` | Single | `crdc/codebook_schools_crdc_restraint-seclusion-instances` |
| School Finance | `crdc/schools_crdc_finance` | Single | `crdc/codebook_schools_crdc_finance` |
| Suspensions (Days) | `crdc/schools_crdc_suspensions` | Single | `crdc/codebook_schools_crdc_suspensions_days` |
| Teachers/Staff | `crdc/schools_crdc_teacher` | Single | `crdc/codebook_schools_crdc_teachers_staff` |

The **24** count is the deduplicated Urban bulk family inventory, not a year, row count, or API endpoint count. The live Portal catalog separately exposed **50 CRDC endpoint templates** because topic/disaggregation routes split more finely than bulk files. Family-specific year coverage varies; neither number implies CRDC 2024 data.

> **CRDC naming note:** Some data file paths use concatenated names (e.g., `disciplineinstances`, `mathandscience`) while their codebook counterparts use underscored names (e.g., `discipline_instances`, `math_and_science`). Always use the exact paths from `datasets-reference.md`.

Codebooks are `.xls` files co-located with data in all mirrors. Use `get_codebook_url()` from `fetch-patterns.md` to construct download URLs:

```python
from fetch_patterns import get_codebook_url
url = get_codebook_url("crdc/codebook_schools_crdc_discipline")
```

```r
# get_codebook_url() is a Python helper; in R, construct the codebook URL from the
# mirror root in mirrors.yaml (codebooks are .xls files co-located with the data).
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern).
config <- yaml::read_yaml("mirrors.yaml")
mirror <- config$mirrors[[1]]
url <- paste0(mirror$root_url, "/", "crdc/codebook_schools_crdc_discipline", ".xls")
```

> **Truth Hierarchy:** When interpreting variable values, apply this priority:
> 1. **Actual data file** (what you observe in the parquet/CSV) -- this IS the truth
> 2. **Live codebook** (.xls in mirror) -- authoritative documentation, may lag
> 3. **This skill documentation** -- convenient summary, may drift from codebook
>
> If this documentation contradicts the codebook, trust the codebook. If the codebook contradicts observed data, trust the data and investigate.

### Filtering

```python
import polars as pl

# Filter to a single state (California) and disaggregated race groups
df = df.filter(
    (pl.col("fips") == 6) &       # California
    (pl.col("race") < 99)          # Exclude totals row
)

# Filter to specific demographic intersection
df = df.filter(
    (pl.col("race") == 2) &        # Black students
    (pl.col("sex") == 99) &         # Both sexes (total)
    (pl.col("disability") == 99)    # All disability statuses
)
```

```r
library(dplyr)

# Filter to a single state (California) and disaggregated race groups
df <- df |> filter(
    (fips == 6) &       # California
    (race < 99)          # Exclude totals row
)

# Filter to specific demographic intersection
df <- df |> filter(
    (race == 2) &        # Black students
    (sex == 99) &         # Both sexes (total)
    (disability == 99)    # All disability statuses
)
```

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| **Using string codes** | Portal uses integers, not strings | `race == 2` not `race == "BL"` |
| **Raw counts** | Different enrollment sizes | Use rates per 100/1000 students |
| **Collection cadence** | Assuming annual data or applying an odd/even parity rule | Check topic-specific collection labels; 2020 and 2021 are consecutive |
| **COVID year** | 2020-21 not comparable | Flag or exclude from trends |
| **Suppression** | Small cell suppression | Check suppression rates first |
| **Coverage history** | Applying one sampling label to both early collections | 2013-14 is an official universe collection; verify 2011-12 separately |
| **Definition drift** | Variables change over time | Check codebooks for each year |
| **Forgetting code 99** | Including totals in calculations | Filter `race < 99` for disaggregated analysis |
| **CSV type inference** | Polars and readr infer `ncessch`/`leaid`/`crdc_id` as integer, destroying leading zeros | Python: `schema_overrides={"ncessch": pl.Utf8, "leaid": pl.Utf8, "crdc_id": pl.Utf8}`; R: `readr::read_csv(..., col_types = cols(ncessch = col_character(), leaid = col_character(), crdc_id = col_character()))` |

## Equity Analysis Framework

CRDC data is designed for civil rights analysis. Key analytical approaches:

### Disparity Ratios

```python
import polars as pl

# Calculate discipline disparity using Portal integer codes
def discipline_disparity(df, discipline_var, group_a, group_b):
    """
    Calculate risk ratio between two groups.
    Value > 1 indicates group_a has higher rate.

    Args:
        df: DataFrame with CRDC data
        discipline_var: Column with discipline counts
        group_a: Integer race code (e.g., 2 for Black)
        group_b: Integer race code (e.g., 1 for White)

    Example:
        # Black vs White OSS disparity
        disparity = discipline_disparity(df, 'students_susp_out_sch_single', 2, 1)
    """
    # Filter to each group (using integer codes)
    df_a = df.filter(pl.col('race') == group_a)
    df_b = df.filter(pl.col('race') == group_b)

    # Calculate rates
    rate_a = df_a.select(pl.col(discipline_var).sum()).item() / \
             df_a.select(pl.col('enrollment_crdc').sum()).item()
    rate_b = df_b.select(pl.col(discipline_var).sum()).item() / \
             df_b.select(pl.col('enrollment_crdc').sum()).item()

    return rate_a / rate_b

# Example: Black (race=2) vs White (race=1) disparity
# disparity = discipline_disparity(df, 'students_susp_out_sch_single', 2, 1)
```

```r
library(dplyr)

# Calculate discipline disparity using Portal integer codes.
# Risk ratio between two groups; value > 1 indicates group_a has a higher rate.
# Example: Black (race=2) vs White (race=1) OSS disparity
discipline_var <- "students_susp_out_sch_single"
group_a <- 2  # Black
group_b <- 1  # White

# Filter to each group (using integer codes)
df_a <- df |> filter(race == group_a)
df_b <- df |> filter(race == group_b)

# Calculate rates
rate_a <- sum(df_a[[discipline_var]], na.rm = TRUE) /
  sum(df_a$enrollment_crdc, na.rm = TRUE)
rate_b <- sum(df_b[[discipline_var]], na.rm = TRUE) /
  sum(df_b$enrollment_crdc, na.rm = TRUE)

disparity <- rate_a / rate_b
```

### Composition vs. Representation

- **Composition**: What share of suspended students are Black?
- **Representation**: Are Black students suspended at higher rates than enrollment share?

### Risk Ratios

- Compare discipline/outcome rates across groups
- Adjust for school-level factors when appropriate

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ccd` | School/district characteristics | Linking CRDC to school demographics, locale, Title I status (join on `ncessch` or `leaid`) |
| `education-data-source-edfacts` | Assessment outcomes | Comparing discipline patterns to academic outcomes |
| `education-data-explorer` | Parent discovery skill | Routing questions to mirror CRDC dataset files and variables |
| `education-data-query` | Data fetching | Downloading CRDC parquet/CSV files from mirrors |
| `education-data-context` | General interpretation | Education data interpretation and citation generation |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Title VI (race) | `./references/civil-rights-context.md` |
| Title IX (sex) | `./references/civil-rights-context.md` |
| Section 504 (disability) | `./references/civil-rights-context.md` |
| IDEA | `./references/civil-rights-context.md` |
| OCR enforcement | `./references/civil-rights-context.md` |
| Discipline data | `./references/data-elements.md` |
| Restraint/seclusion | `./references/data-elements.md` |
| Harassment | `./references/data-elements.md` |
| Course access | `./references/data-elements.md` |
| AP/IB/Gifted | `./references/data-elements.md` |
| Chronic absenteeism | `./references/data-elements.md` |
| Staffing | `./references/data-elements.md` |
| Preschool | `./references/data-elements.md` |
| Sampling approach | `./references/collection-methodology.md` |
| Collection timeline | `./references/collection-methodology.md` |
| Variable codes | `./references/variable-definitions.md` |
| Suppression rules | `./references/data-quality.md` |
| COVID impact | `./references/data-quality.md` |
| Year changes | `./references/historical-changes.md` |
