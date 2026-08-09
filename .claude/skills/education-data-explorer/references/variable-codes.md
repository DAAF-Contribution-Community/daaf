# Variable Codes Reference

> **Vintage & verification banner.** Coded values here are keyed to **mirror vintage 0.26.1 (pinned HuggingFace revision `0ad00ce0e232c96b0642459e4e7326607a8d26aa`)**. Facts were verified against Portal v0.26.1 variable metadata and live probes on 2026-08-07/08 (route + variable audits under `research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/`). The `urban_csv` fallback mirror is unpinned/current-Portal, so these guarantees are exact only for the pinned mirror. For the complete, mechanically generated per-variable coded-value strings (all 2,235 per-source variables, deduplicated from 2,994 endpoint-variable rows), see the `variable-dictionary-{source}.md` files in this directory — those carry the Portal's verbatim `values` metadata; this file curates the analytically load-bearing schemes with cross-source populated-subset notes that the mechanical dictionaries cannot express.

Reference for coded values used across Education Data Portal mirror datasets.

## Contents

- [State FIPS Codes](#state-fips-codes)
- [Grade Codes](#grade-codes)
- [Race/Ethnicity Codes](#raceethnicity-codes)
- [Sex Codes](#sex-codes)
- [School Level Codes](#school-level-codes)
- [School Type Codes](#school-type-codes)
- [Urban-Centric Locale Codes](#urban-centric-locale-codes)
- [Institution Control Codes](#institution-control-codes-colleges)
- [Institution Level Codes](#institution-level-codes-colleges)
- [Sector Codes](#sector-codes-colleges)
- [Award Level Codes](#award-level-codes)
- [Special Population Codes](#special-population-codes)
- [Missing Value Codes](#missing-value-codes)
- [Legacy / Federal Name Aliases](#legacy--federal-name-aliases)

---

## State FIPS Codes

Two-digit numeric codes for U.S. states and territories.

| FIPS | State | FIPS | State |
|------|-------|------|-------|
| 1 | Alabama | 30 | Montana |
| 2 | Alaska | 31 | Nebraska |
| 4 | Arizona | 32 | Nevada |
| 5 | Arkansas | 33 | New Hampshire |
| 6 | California | 34 | New Jersey |
| 8 | Colorado | 35 | New Mexico |
| 9 | Connecticut | 36 | New York |
| 10 | Delaware | 37 | North Carolina |
| 11 | District of Columbia | 38 | North Dakota |
| 12 | Florida | 39 | Ohio |
| 13 | Georgia | 40 | Oklahoma |
| 15 | Hawaii | 41 | Oregon |
| 16 | Idaho | 42 | Pennsylvania |
| 17 | Illinois | 44 | Rhode Island |
| 18 | Indiana | 45 | South Carolina |
| 19 | Iowa | 46 | South Dakota |
| 20 | Kansas | 47 | Tennessee |
| 21 | Kentucky | 48 | Texas |
| 22 | Louisiana | 49 | Utah |
| 23 | Maine | 50 | Vermont |
| 24 | Maryland | 51 | Virginia |
| 25 | Massachusetts | 53 | Washington |
| 26 | Michigan | 54 | West Virginia |
| 27 | Minnesota | 55 | Wisconsin |
| 28 | Mississippi | 56 | Wyoming |
| 29 | Missouri | | |

### Territories and Other

| FIPS | Territory |
|------|-----------|
| 60 | American Samoa |
| 64 | Federated States of Micronesia |
| 66 | Guam |
| 68 | Marshall Islands |
| 69 | Northern Mariana Islands |
| 70 | Palau |
| 72 | Puerto Rico |
| 74 | U.S. Minor Outlying Islands |
| 78 | U.S. Virgin Islands |
| 59 | Outlying Areas (aggregate) |

### Bureau of Indian Education

| FIPS | Description |
|------|-------------|
| 58 | Bureau of Indian Education (DoDEA) |

---

## Grade Codes

### Numeric Grade Codes

Used in response data:

| Code | Description |
|------|-------------|
| -1 | Pre-Kindergarten |
| 0 | Kindergarten |
| 1 | Grade 1 |
| 2 | Grade 2 |
| 3 | Grade 3 |
| 4 | Grade 4 |
| 5 | Grade 5 |
| 6 | Grade 6 |
| 7 | Grade 7 |
| 8 | Grade 8 |
| 9 | Grade 9 |
| 10 | Grade 10 |
| 11 | Grade 11 |
| 12 | Grade 12 |
| 13 | Adult Education |
| 14 | Ungraded |
| 99 | Total (all grades) |

### Grade Values (Portal route form)

Portal route form (citation/maintenance reference). In the mirror these are the `grade`
column value on `ccd/schools_ccd_enrollment_{year}` — filter locally rather than
constructing a route:

| Portal route form | Grade |
|-------------------|-------|
| `grade-pk` | Pre-Kindergarten |
| `grade-k` | Kindergarten |
| `grade-1` | Grade 1 |
| `grade-2` | Grade 2 |
| `grade-3` | Grade 3 |
| `grade-4` | Grade 4 |
| `grade-5` | Grade 5 |
| `grade-6` | Grade 6 |
| `grade-7` | Grade 7 |
| `grade-8` | Grade 8 |
| `grade-9` | Grade 9 |
| `grade-10` | Grade 10 |
| `grade-11` | Grade 11 |
| `grade-12` | Grade 12 |
| `grade-13` | Adult Education |
| `grade-14` | Ungraded |
| `grade-99` | Total (all grades) |

**Example**: for 5th grade enrollment, filter `pl.col("grade") == 5` on `ccd/schools_ccd_enrollment_2022` (Portal route form: `/schools/ccd/enrollment/2022/grade-5/`).

---

## Race/Ethnicity Codes

| Code | Description |
|------|-------------|
| 1 | White |
| 2 | Black or African American |
| 3 | Hispanic or Latino |
| 4 | Asian |
| 5 | American Indian or Alaska Native |
| 6 | Native Hawaiian or Other Pacific Islander |
| 7 | Two or More Races |
| 8 | Nonresident Alien (colleges only) |
| 9 | Unknown |
| 20 | Other / Not Specified (legacy; not observed in any probed Portal source as of 2026-08-07) |
| 99 | Total (all races) |

### Race Codes in Different Data Sources

| Source | Codes Available |
|--------|-----------------|
| CCD | 1-7, 9, 99 (live-verified) |
| CRDC | 1-7, 99 (live-verified) |
| IPEDS | 1-9, 99 (live-verified; code 8 IPEDS-only) |
| EDFacts | 1-9, 20, 99 + sentinels (**metadata-declared, not live-confirmed**) |

> **EDFacts race — metadata-declared only.** The EDFacts `race` set `{1-9, 20, 99}` plus missing sentinels is taken from Portal metadata, not a live probe: 2026-08-08 live probes of EDFacts assessments were blocked by an Urban API outage (HTTP 500 on EDFacts assessments), so the populated subset could not be confirmed. Treat the EDFacts race set as provisional until re-probed. A 2026-08-09 re-probe (`scripts/mirror_maintenance/56_race-edfacts-reprobe.py`) again returned HTTP 500 on all three attempted slices, so the outage persists across two sessions and these codes stay provisional; the next re-probe is recommended on a longer cadence. Valid `grade_edfacts` codes are `{3-8, 9="Grades 9-12", 99}`.

### Historical Note

Prior to 2008, race categories differed. The current categories align with OMB standards for collecting race/ethnicity data.

---

## Sex Codes

| Code | Description |
|------|-------------|
| 1 | Male |
| 2 | Female |
| 3 | Another gender (IPEDS 2022+ only) |
| 4 | Unknown gender (IPEDS 2022+ only) |
| 9 | Unknown / Not Reported |
| 99 | Total (all sexes) |

> **Note:** Codes 3 and 4 were added to IPEDS starting with the 2022-23 collection. Among K-12 sources, live CCD data **does** carry `sex=9` (Unknown) — verified live at `schools/ccd/enrollment/2020/grade-9/race/sex/?fips=11`, distinct sex = `[1, 2, 9, 99]`. CRDC in the same probe set showed only `{1, 2, 99}`. Do not assume K-12 sources are limited to `{1, 2, 99}`; inspect the actual distinct values per source and year.

---

## School Level Codes

CCD school level classification:

| Code | Description |
|------|-------------|
| 0 | Not applicable / Not reported |
| 1 | Primary (elementary: generally PK-5 or PK-6) |
| 2 | Middle (generally 6-8 or 7-8) |
| 3 | High (generally 9-12) |
| 4 | Other (ungraded, combined, or special) |

### Typical Grade Ranges by Level

| Level | Common Grade Ranges |
|-------|---------------------|
| Primary | PK-5, PK-6, K-5, K-6 |
| Middle | 5-8, 6-8, 7-8 |
| High | 9-12, 10-12 |
| Other | Varies (K-12, K-8, etc.) |

---

## School Type Codes

CCD school type classification:

| Code | Description |
|------|-------------|
| 1 | Regular School |
| 2 | Special Education School |
| 3 | Vocational/Technical School |
| 4 | Alternative/Other School |

### School Type Details

| Type | Typical Characteristics |
|------|------------------------|
| Regular | Standard K-12 curriculum |
| Special Ed | Primarily serves students with disabilities |
| Vocational | Career and technical education focus |
| Alternative | Nontraditional settings, dropout recovery |

---

## Urban-Centric Locale Codes

NCES urban-centric locale classification (12 categories):

### City

| Code | Description |
|------|-------------|
| 11 | City, Large (population ≥250,000) |
| 12 | City, Midsize (population 100,000-249,999) |
| 13 | City, Small (population <100,000) |

### Suburb

| Code | Description |
|------|-------------|
| 21 | Suburb, Large (outside large city) |
| 22 | Suburb, Midsize (outside midsize city) |
| 23 | Suburb, Small (outside small city) |

### Town

| Code | Description |
|------|-------------|
| 31 | Town, Fringe (≤10 miles from urbanized area) |
| 32 | Town, Distant (10-35 miles from urbanized area) |
| 33 | Town, Remote (>35 miles from urbanized area) |

### Rural

| Code | Description |
|------|-------------|
| 41 | Rural, Fringe (≤5 miles from urbanized area) |
| 42 | Rural, Distant (5-25 miles from urbanized area) |
| 43 | Rural, Remote (>25 miles from urbanized area) |

### Simplified Groupings

For analysis, often grouped as:

| Group | Codes |
|-------|-------|
| Urban | 11, 12, 13, 21, 22, 23 |
| Town | 31, 32, 33 |
| Rural | 41, 42, 43 |

---

## Institution Control Codes (Colleges)

| Code | Description |
|------|-------------|
| 1 | Public |
| 2 | Private nonprofit |
| 3 | Private for-profit |

---

## Institution Level Codes (Colleges)

| Code | Description |
|------|-------------|
| 1 | Less-than-2-year |
| 2 | 2-year |
| 4 | 4-year or above |

Code `3` is **unpopulated** in probed data. (Live-verified 2026-08-07: `ipeds/directory/2022` `unitid=110635`, UC Berkeley → `institution_level=4`; existence probes `?institution_level=3` returned count 0 for 1990, 2004, and 2022, and a CA directory slice showed only `{1, 2, 4}`.)

> **Footnote (metadata vs. data):** Portal v0.26.1 metadata *does* define code `3` ("Less than four years") alongside `1`, `2`, `4`. It is simply unpopulated in the years probed (1990/2004/2022 + a CA slice). Filter on observed values, but do not treat code `3` as impossible — it is reserved in the Portal scheme.

---

## Sector Codes (Colleges)

Combined control and level:

| Code | Description |
|------|-------------|
| 0 | Administrative unit |
| 1 | Public, 4-year or above |
| 2 | Private nonprofit, 4-year or above |
| 3 | Private for-profit, 4-year or above |
| 4 | Public, 2-year |
| 5 | Private nonprofit, 2-year |
| 6 | Private for-profit, 2-year |
| 7 | Public, less-than-2-year |
| 8 | Private nonprofit, less-than-2-year |
| 9 | Private for-profit, less-than-2-year |

---

## Award Level Codes

IPEDS `award_level` classification (Portal scheme, used on the two `completions` families). This replaces a prior mis-mapped table — the earlier scheme (`3=Associate's, 5=Bachelor's, 7=Master's, 9=Doctor's`, plus codes 10-12) was **contradicted** by Portal metadata (variable audit §43-C3, 2026-08-07). Shared codes carried different meanings and codes 10-12 do not exist in the Portal scheme.

| Code | Description |
|------|-------------|
| 4 | Associate's degree |
| 5 | Award of at least one but less than four academic years |
| 7 | Bachelor's degree |
| 9 | Master's degree |
| 20 | Doctor's degree (until 2008) |
| 22 | Doctor's degree — research/scholarship (starting 2007) |
| 23 | Doctor's degree — professional practice |
| 30 | Postsecondary certificate (various; see codebook) |
| 31 | Postsecondary certificate (various; see codebook) |
| 32 | Postsecondary certificate (various; see codebook) |
| 33 | Postsecondary certificate (various; see codebook) |
| 99 | Total |

> Codes 30-33 are certificate categories; consult the `completions` codebook (`ipeds/codebook_colleges_ipeds_completions-2digcip` / `-6digcip`) for the exact certificate label per code. The `20` vs `22`/`23` split reflects the 2007-08 doctoral reclassification.

---

## Special Population Codes

Used in EDFacts and CRDC for student subgroups:

### Disability Status

Full Portal scheme (the prior binary `0/1/99` table undercounted — Section 504 code `2` was observed live but missing; variable audit §43-C2):

| Code | Description | Confirmation |
|------|-------------|--------------|
| 0 | Students without disabilities | live |
| 1 | Students served under IDEA | live |
| 2 | Students served under Section 504 only | live-observed (CRDC) |
| 3 | Students not served under IDEA | metadata-defined |
| 4 | (Portal metadata category) | metadata-defined |
| 99 | Total (all students) | live |

> Code `2` (Section 504 only) is a distinct, analytically meaningful category — verified live at `schools/crdc/discipline/2017/disability/race/sex/?fips=11`, distinct disability = `[0, 1, 2, 99]`. Do not collapse disability to a `0/1` binary.

### Economic Status

| Code | Description |
|------|-------------|
| 0 | Not economically disadvantaged |
| 1 | Economically disadvantaged |
| 99 | Total |

### English Proficiency

| Code | Description |
|------|-------------|
| 0 | Not limited English proficient |
| 1 | Limited English proficient (LEP) / English learner (EL) |
| 99 | Total |

### Other Populations

| Variable | Values |
|----------|--------|
| `homeless` | 0=No, 1=Yes, 99=Total |
| `migrant` | 0=No, 1=Yes, 99=Total |
| `foster_care` | 0=No, 1=Yes, 99=Total |

---

## Missing Value Codes

Standard codes for missing or suppressed data. A scan of the **entire** Portal `values` corpus (all 2,994 variables, 2026-08-07) found the negative sentinels `-1, -2, -3, -99` only — codes `-4` (previously documented as "Derived/Imputed") and `-9` ("Not available") appear **nowhere** in the corpus and have been removed. `-99` is present in Portal metadata and is newly documented here.

| Code | Meaning |
|------|---------|
| -1 | Missing / Not reported |
| -2 | Not applicable |
| -3 | Suppressed (privacy protection) |
| -99 | Missing / Not reported (alternate sentinel present in Portal metadata) |

### Interpretation Guidelines

| Code | When Used | How to Handle |
|------|-----------|---------------|
| -1 | Data not collected or reported | Exclude from analysis |
| -2 | Question doesn't apply (e.g., no AP offered) | Exclude from analysis |
| -3 | Small cell size suppressed | May estimate or exclude |
| -99 | Alternate missing sentinel (Portal metadata) | Exclude from analysis |

### Suppression Rules

Data suppression for privacy varies by source:
- **CCD**: Cells with <3 students may be suppressed
- **CRDC**: Cells with <10 students may be suppressed
- **EDFacts**: Range reporting for small cells
- **IPEDS**: Varies by variable

---

## College Student Level Codes

### Enrollment Level (URL Path)

| URL Value | Description |
|-----------|-------------|
| `undergraduate` | Undergraduate students |
| `graduate` | Graduate students |
| `first-professional` | First professional (historical) |

### Attendance Status

| Code | Description |
|------|-------------|
| 1 | Full-time |
| 2 | Part-time |
| 99 | Total |

---

## Calendar System Codes (Colleges)

| Code | Description |
|------|-------------|
| 1 | Semester |
| 2 | Quarter |
| 3 | Trimester |
| 4 | Four-one-four plan |
| 5 | Other academic year |
| 6 | Differs by program |
| 7 | Continuous |

---

## Carnegie Basic Classification Codes (2021)

The `ccbasic` variable uses the 2021 Carnegie Classification. The 2025 Carnegie update **is** now reflected in Portal data: as of Portal v0.25.0 (released 2026-03-30), ipeds/directory responses now carry new Carnegie 2025 variables — observed 2026-08-07 are `cc_basic_2025`, `cc_undergrad_2025`, `cc_research_act_desig_2025`, `cc_stud_access_earn_2025`, `cc_instit_size_2025`, and `cc_award_level_focus_2025` (the Portal release history records seven Carnegie 2025 variables added in v0.25.0). These are null for years predating the 2025 classification. The `ccbasic` codes below remain the 2021 scheme; use the `cc_*_2025` variables for the 2025 classification.

| Code | Description |
|------|-------------|
| -2 | Not applicable |
| 1 | Associate's: High Transfer-High Traditional |
| 2 | Associate's: High Transfer-Mixed Trad/Nontrad |
| 3 | Associate's: High Transfer-High Nontraditional |
| 4 | Associate's: Mixed Transfer/Career & Tech-High Traditional |
| 5 | Associate's: Mixed Transfer/Career & Tech-Mixed Trad/Nontrad |
| 6 | Associate's: Mixed Transfer/Career & Tech-High Nontraditional |
| 7 | Associate's: High Career & Tech-High Traditional |
| 8 | Associate's: High Career & Tech-Mixed Trad/Nontrad |
| 9 | Associate's: High Career & Tech-High Nontraditional |
| 10 | Special Focus Two-Year: Health Professions |
| 11 | Special Focus Two-Year: Technical Professions |
| 12 | Special Focus Two-Year: Arts & Design |
| 13 | Special Focus Two-Year: Other Fields |
| 14 | Baccalaureate/Associate's: Associate's Dominant |
| 15 | Doctoral Universities: Very High Research Activity (R1) |
| 16 | Doctoral Universities: High Research Activity (R2) |
| 17 | Doctoral/Professional Universities |
| 18 | Master's Colleges & Universities: Larger Programs |
| 19 | Master's Colleges & Universities: Medium Programs |
| 20 | Master's Colleges & Universities: Small Programs |
| 21 | Baccalaureate Colleges: Arts & Sciences Focus |
| 22 | Baccalaureate Colleges: Diverse Fields |
| 23 | Baccalaureate/Associate's: Mixed |
| 24 | Special Focus Four-Year: Faith-Related Institutions |
| 25 | Special Focus Four-Year: Medical Schools & Centers |
| 26 | Special Focus Four-Year: Other Health Professions |
| 27 | Special Focus Four-Year: Engineering Schools |
| 28 | Special Focus Four-Year: Other Technology-Related |
| 29 | Special Focus Four-Year: Business & Management |
| 30 | Special Focus Four-Year: Arts, Music & Design |
| 31 | Special Focus Four-Year: Law Schools |
| 32 | Special Focus Four-Year: Other Special Focus |
| 33 | Tribal Colleges |

---

## Legacy / Federal Name Aliases

The Portal renames many federal/documented variables. If you arrive with one of these
stale or federal-documentation names, the current mirror variable is on the right. Each
target below was verified present in the matching `variable-dictionary-{source}.md` file.

| Legacy / federal name | Current mirror variable | Source (dictionary) |
|-----------------------|-------------------------|---------------------|
| `inst_level` | `institution_level` | IPEDS (`variable-dictionary-ipeds.md`) |
| `applicants_total` | `number_applied` | IPEDS (`variable-dictionary-ipeds.md`) |
| `admissions_total` | `number_admitted` | IPEDS (`variable-dictionary-ipeds.md`) |
| `grad_rate_150pct` | `completion_rate_150pct` | IPEDS (`variable-dictionary-ipeds.md`) |
| `school_poverty` | `meps_poverty_pct` | MEPS (`variable-dictionary-meps.md`) |
| `population_5_17_poverty` | `est_population_5_17_poverty` | SAIPE (`variable-dictionary-saipe.md`) |

> This is a reverse-lookup convenience only. For the full per-variable catalog with coded
> values, see the `variable-dictionary-{source}.md` files. Always verify the actual column
> names against the downloaded file schema before filtering.

---

## Quick Code Lookup

### Common Filter Values

Applied as LOCAL filter expressions on the downloaded mirror file (Polars). The code
values are the same values stored in the mirror columns — only the filter syntax is local.

| Filter | Local Polars expression |
|--------|-------------------------|
| California schools | `pl.col("fips") == 6` |
| Texas schools | `pl.col("fips") == 48` |
| New York schools | `pl.col("fips") == 36` |
| Charter schools | `pl.col("charter") == 1` |
| High schools | `pl.col("school_level") == 3` |
| Total enrollment | `pl.col("grade") == 99` |
| All races | `pl.col("race") == 99` (or omit the filter) |
| Public colleges | `pl.col("inst_control") == 1` |
| 4-year colleges | `pl.col("institution_level") == 4` (after verifying the file schema) |
| HBCUs | `pl.col("hbcu") == 1` |

### Combining Filters

Combine local expressions with `&`:

```
(pl.col("fips") == 6) & (pl.col("charter") == 1) & (pl.col("school_level") == 3)
```

Selects California charter high schools.
