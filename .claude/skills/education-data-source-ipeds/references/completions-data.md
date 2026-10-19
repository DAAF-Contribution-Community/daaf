# IPEDS Completions Data

Understanding degrees and certificates awarded, CIP codes, and completions analysis.

## Contents

- [Completions Survey Overview](#completions-survey-overview)
- [Completions vs Completers](#completions-vs-completers)
- [Award Levels](#award-levels)
- [CIP Codes](#cip-codes)
- [Data Disaggregation](#data-disaggregation)
- [Distance Education](#distance-education)
- [Common Analysis Uses](#common-analysis-uses)
- [Data Quality Issues](#data-quality-issues)
- [Variable Reference](#variable-reference)

## Completions Survey Overview

The Completions (C) survey collects data on postsecondary awards conferred during an academic year.

### Collection Period

Fall collection (August-October) for the prior academic year (July 1 - June 30).

### What's Collected

1. **Completions**: Count of awards by CIP code, award level, race/ethnicity, gender
2. **Completers**: Unduplicated count of individuals receiving awards
3. **Distance education indicator**: Whether program is offered via DE

### Key Distinction: Academic Year

Completions are for the academic year, not calendar year:
- 2022-23 completions = Awards conferred July 1, 2022 - June 30, 2023 (Portal `year` = 2023 under the inferred end-year convention in SKILL.md § Year Field Meanings; confirm against the codebook)
- Collected in the Fall 2023 (2023-24) collection; provisional ~9 months after collection closes, final released September 23, 2025 (NCES Data Release Schedule)

## Completions vs Completers

### Completions

**Count of awards conferred** - a student receiving two degrees counts as two completions.

```python
# If student earns BS in Biology and BA in Chemistry
completions = 2  # Two awards

# If student earns dual degree (single program)
completions = 1  # One award
```

```r
# If student earns BS in Biology and BA in Chemistry
completions <- 2  # Two awards

# If student earns dual degree (single program)
completions <- 1  # One award
```

### Completers

**Unduplicated count of individuals** - each person counted once regardless of awards.

```python
# Same student with two degrees
completers = 1  # One person

# Why different totals?
# completions >= completers (always)
# completions = completers + double majors + multiple awards
```

```r
# Same student with two degrees
completers <- 1  # One person

# Why different totals?
# completions >= completers (always)
# completions = completers + double majors + multiple awards
```

### When to Use Each

| Use Case | Measure | Why |
|----------|---------|-----|
| Degrees by field | Completions | Shows all awards in each field |
| Graduation outcomes | Completers | Counts individuals |
| Program productivity | Completions | Shows program output |
| Degree inflation analysis | Ratio | completions/completers trend |
| Labor market supply | Completions by CIP | Degrees in workforce fields |

### Double Counting Warning

Using completions can overcount individuals:

```python
# Example: Counting STEM graduates
stem_completions = bio_completions + chem_completions + physics_completions
# May count same person multiple times if double major

# Solution: Use completers for people count, completions for field analysis
```

```r
# Example: Counting STEM graduates
stem_completions <- bio_completions + chem_completions + physics_completions
# May count same person multiple times if double major

# Solution: Use completers for people count, completions for field analysis
```

## Award Levels

### Portal Award Level Codes

> **CRITICAL:** The Portal uses DIFFERENT award level codes than NCES raw documentation. Labels below are the Portal codebook labels for `award_level` in `completions-2digcip` and `completions-6digcip` (as transcribed in `education-data-explorer/references/variable-dictionary-ipeds.md`). Spot-checked 2026-10-19: UC Berkeley (unitid 110635) Portal `year`=2023, `award_level`=7, `cipcode_6digit`=99, first major, all races and sexes = 9,207 awards, close to College Navigator's 9,216 bachelor's degrees. Always verify against the codebook.

| Code | Level (codebook label) |
|------|------------------------|
| 1 | Award of less than one academic year |
| 2 | Award of less than two academic years |
| 3 | Award of at least one but less than two academic years |
| 4 | Associate's degree |
| 5 | Award of at least one but less than four academic years |
| 6 | Award of at least two but less than four academic years |
| 7 | Bachelor's degree |
| 8 | Postbaccalaureate or post-master's certificate |
| 9 | Master's degree |
| 20 | Doctor's degree (until 2008) |
| 21 | First-professional degree (until 2008) |
| 22 | Doctor's degree, research/scholarship (starting 2007) |
| 23 | Doctor's degree, professional practice (starting 2007) |
| 24 | Doctor's degree, other (starting 2007) |
| 30 | Certificate of less than 12 weeks |
| 31 | Certificates of at least 12 weeks but less than 1 year |
| 32 | Certificate of at least 1 year but less than 2 years |
| 33 | Certificate of at least 2 years but less than 4 years |
| 99 | Total |
| -1 / -2 / -3 | Missing/not reported / Not applicable / Suppressed data |

> **Overlapping certificate codes.** The codebook labels overlap: codes 2 and 5 span the ranges of other codes, and codes 1/3/6 and 30-33 describe overlapping certificate lengths. The codebook does not say which codes occur in which years, or whether 2 and 5 are subtotals (inference: they may be). Tabulate `award_level` by `year` in your extract before summing certificate codes, and never add code 99 to its components.

> Verify these codes against the live codebook. Use `get_codebook_url()` from `fetch-patterns.md`:
> ```python
> url = get_codebook_url("ipeds/codebook_colleges_ipeds_completions-2digcip")
> ```
> ```r
> # get_codebook_url() is a Python helper; in R, build the URL from the mirror root.
> # Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
> mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]
> url <- paste0(mirror$root_url, "/", "ipeds/codebook_colleges_ipeds_completions-2digcip", ".xls")
> ```

#### NCES Raw File Award Level Codes (for reference only)

NCES documentation and raw IPEDS data files use a different numbering system (`AWLEVEL`). The Portal column below matches each NCES level to the Portal code with the same codebook label — a label match (inference), not a published crosswalk. Certificate rows have two candidate Portal code families; check which one your extract uses.

| NCES `AWLEVEL` Code | Portal Code (label match) | Level |
|-----------|-------------|-------|
| 1 | 1 (or 30/31) | Certificate (<1 year) |
| 2 | 3 (or 32) | Certificate (1-<2 years) |
| 3 | 4 | Associate's |
| 4 | 6 (or 33) | Certificate (2-<4 years) |
| 5 | 7 | Bachelor's |
| 6 | 8 (shared with post-master's) | Postbaccalaureate certificate |
| 7 | 9 | Master's |
| 8 | 8 (shared with postbaccalaureate) | Post-master's certificate |
| 17 | 22 | Doctor's - research/scholarship |
| 18 | 23 | Doctor's - professional practice |
| 19 | 24 | Doctor's - other |

### Award Level Groupings (Portal Codes)

```python
# Common groupings using PORTAL codes (not NCES codes); labels per the Portal codebook.
# Drop 99 (Total) and negative codes before summing.
# Sub-baccalaureate certificate codes overlap (2 and 5 span other ranges; 1/3/6 vs 30-33):
# tabulate award_level by year in your extract and use ONE non-overlapping set.
subbacc_certs_ay = [1, 3, 6]          # by academic-year length
subbacc_certs_wk = [30, 31, 32, 33]   # by weeks/years length
associate = [4]
bachelor = [7]
grad_certificates = [8]               # postbaccalaureate or post-master's certificate
master = [9]
doctoral = [22, 23, 24]               # from 2007; codes 20/21 cover years until 2008
doctoral_pre2008 = [20, 21]           # until 2008 (21 = first-professional); 2007-2008 may also carry 22-24 — tabulate by year, never sum both families for one year

# Undergraduate vs graduate (pick the certificate set your extract actually uses)
undergraduate = subbacc_certs_ay + associate + bachelor
graduate = grad_certificates + master + doctoral  # add doctoral_pre2008 for years before 2007
```

```r
# Common groupings using PORTAL codes (not NCES codes); labels per the Portal codebook.
# Drop 99 (Total) and negative codes before summing.
# Sub-baccalaureate certificate codes overlap (2 and 5 span other ranges; 1/3/6 vs 30-33):
# tabulate award_level by year in your extract and use ONE non-overlapping set.
subbacc_certs_ay <- c(1, 3, 6)          # by academic-year length
subbacc_certs_wk <- c(30, 31, 32, 33)   # by weeks/years length
associate <- c(4)
bachelor <- c(7)
grad_certificates <- c(8)               # postbaccalaureate or post-master's certificate
master <- c(9)
doctoral <- c(22, 23, 24)               # from 2007; codes 20/21 cover years until 2008
doctoral_pre2008 <- c(20, 21)           # until 2008 (21 = first-professional); 2007-2008 may also carry 22-24 — tabulate by year, never sum both families for one year

# Undergraduate vs graduate (pick the certificate set your extract actually uses)
undergraduate <- c(subbacc_certs_ay, associate, bachelor)
graduate <- c(grad_certificates, master, doctoral)  # add doctoral_pre2008 for years before 2007
```

## CIP Codes

### Classification of Instructional Programs

CIP (Classification of Instructional Programs) is a taxonomy of instructional programs.

### CIP Code Structure

| Level | Digits | Example | Meaning |
|-------|--------|---------|---------|
| 2-digit | XX | 52 | Business |
| 4-digit | XX.XX | 52.02 | Business Administration |
| 6-digit | XX.XXXX | 52.0201 | Business Admin & Management |

### Major CIP Families (2-digit)

| CIP | Field |
|-----|-------|
| 01 | Agriculture |
| 03 | Natural Resources |
| 04 | Architecture |
| 05 | Area/Ethnic/Cultural Studies |
| 09 | Communication |
| 10 | Communications Technologies |
| 11 | Computer Science |
| 13 | Education |
| 14 | Engineering |
| 15 | Engineering Technologies |
| 16 | Foreign Languages |
| 22 | Legal Professions |
| 23 | English |
| 24 | Liberal Arts |
| 26 | Biological Sciences |
| 27 | Mathematics |
| 30 | Interdisciplinary Studies |
| 31 | Parks and Recreation |
| 38 | Philosophy |
| 40 | Physical Sciences |
| 42 | Psychology |
| 43 | Security and Protective Services |
| 44 | Public Administration |
| 45 | Social Sciences |
| 50 | Visual and Performing Arts |
| 51 | Health Professions |
| 52 | Business |
| 54 | History |

### CIP Version Changes

CIP codes are updated periodically:
- CIP 2000
- CIP 2010
- CIP 2020

**Impact**: Programs may be reclassified; crosswalks available from NCES.

### STEM CIP Codes

DHS designates STEM fields for OPT purposes. Common STEM 2-digit CIPs:

```python
# 2-digit values; Portal `cipcode` may hold 6-digit-style values (110000) — tabulate before filtering (unverified)
stem_cips = [
    1,   # Agriculture (some)
    3,   # Natural Resources
    11,  # Computer Science
    14,  # Engineering
    15,  # Engineering Tech
    26,  # Biology
    27,  # Math
    40,  # Physical Sciences
    41,  # Science Tech
]
```

```r
# 2-digit values; Portal `cipcode` may hold 6-digit-style values (110000) — tabulate before filtering (unverified)
stem_cips <- c(
    1,   # Agriculture (some)
    3,   # Natural Resources
    11,  # Computer Science
    14,  # Engineering
    15,  # Engineering Tech
    26,  # Biology
    27,  # Math
    40,  # Physical Sciences
    41   # Science Tech
)
```

## Data Disaggregation

### By Demographics

Completions are reported by:
- Race/ethnicity (9 categories)
- Gender (men, women)

```python
# Demographic breakdown
completions_by_race = df.group_by(["cipcode", "race"]).agg(pl.col("awards").sum())
completions_by_gender = df.group_by(["cipcode", "sex"]).agg(pl.col("awards").sum())
```

```r
library(dplyr)

# Demographic breakdown
completions_by_race <- df |> group_by(cipcode, race) |> summarise(awards = sum(awards), .groups = "drop")
completions_by_gender <- df |> group_by(cipcode, sex) |> summarise(awards = sum(awards), .groups = "drop")
```

### Race/Ethnicity Categories (Portal Integer Encoding)

| Code | Category |
|------|----------|
| 1 | White |
| 2 | Black or African American |
| 3 | Hispanic/Latino |
| 4 | Asian |
| 5 | American Indian/Alaska Native |
| 6 | Native Hawaiian/Pacific Islander |
| 7 | Two or more races |
| 8 | Nonresident alien |
| 9 | Race/ethnicity unknown |
| 20 | Other |
| 99 | Total |
| -1 | Missing/not reported |
| -3 | Suppressed |

> **Note:** The ordering differs from some NCES documentation. Always use the Portal codebook values.

### By Age (Completers Only)

Completers are also reported by age category:
- Under 18
- 18-24
- 25-39
- 40 and over

## Distance Education

### What's Collected

For each CIP code and award level:
- Is the program offered entirely via distance education?
- If not, is it offered partially via distance education?

### Distance Education Flag

| Value | Meaning |
|-------|---------|
| 1 | Program offered entirely via DE |
| 2 | Program offered partially via DE |
| 3 | Program not offered via DE |

### Analysis Considerations

```python
# Illustrative: no `distance_ed` column exists in Portal completions files (explorer dictionary); the 1/2/3 flag table is unverified
# Filter to programs with DE option
de_programs = completions.filter(
    pl.col("distance_ed").is_in([1, 2])
)

# Count completions in fully online programs
online_only = completions.filter(
    pl.col("distance_ed") == 1
).select(pl.col("awards").sum())
```

```r
library(dplyr)

# Illustrative: no `distance_ed` column exists in Portal completions files (explorer dictionary); the 1/2/3 flag table is unverified
# Filter to programs with DE option
de_programs <- completions |> filter(distance_ed %in% c(1, 2))

# Count completions in fully online programs
online_only <- completions |> filter(distance_ed == 1) |> summarise(total = sum(awards))
```

## Common Analysis Uses

### Labor Market Supply

Estimate graduates entering workforce:

```python
# 2-digit CIP column is `cipcode`; codebook labels use 6-digit-style values (110000 = Computer and information sciences) — tabulate `cipcode` before filtering (11 vs 110000 unverified)
# CS graduates available
cs_grads = completions.filter(
    pl.col("cipcode") == 11
).select(pl.col("awards").sum())

# By degree level
cs_by_level = completions.filter(
    pl.col("cipcode") == 11
).group_by("award_level").agg(pl.col("awards").sum())
```

```r
# 2-digit CIP column is `cipcode`; codebook labels use 6-digit-style values (110000 = Computer and information sciences) — tabulate `cipcode` before filtering (11 vs 110000 unverified)
# CS graduates available
cs_grads <- completions |> filter(cipcode == 11) |> summarise(total = sum(awards))

# By degree level
cs_by_level <- completions |> filter(cipcode == 11) |> group_by(award_level) |> summarise(total = sum(awards))
```

### Program Growth Analysis

Track field trends over time:

```python
# Year-over-year change
field_trend = completions.group_by(["year", "cipcode"]).agg(
    pl.col("awards").sum().alias("total")
).sort(["cipcode", "year"])

# Calculate growth rate
field_trend = field_trend.with_columns(
    (pl.col("total") / pl.col("total").shift(1) - 1).over("cipcode").alias("growth")
)
```

```r
library(dplyr)

# Year-over-year change
field_trend <- completions |>
  group_by(year, cipcode) |>
  summarise(total = sum(awards), .groups = "drop") |>
  arrange(cipcode, year)

# Calculate growth rate
field_trend <- field_trend |>
  group_by(cipcode) |>
  mutate(growth = total / lag(total) - 1) |>
  ungroup()
```

### Diversity in Fields

Analyze representation:

```python
import polars as pl

# Percent women in engineering (sex=2 is Female in Portal integer encoding)
# `cipcode` value coding (14 vs 140000) unverified — tabulate `cipcode` before filtering
eng_by_gender = completions.filter(
    (pl.col("cipcode") == 14) &
    (pl.col("race") == 99)  # Total across races
).group_by("sex").agg(pl.col("awards").sum())

female_awards = eng_by_gender.filter(pl.col("sex") == 2)["awards"][0]
total_awards = eng_by_gender.filter(pl.col("sex") == 99)["awards"][0]
pct_women = female_awards / total_awards * 100
```

```r
library(dplyr)

# Percent women in engineering (sex=2 is Female in Portal integer encoding)
# `cipcode` value coding (14 vs 140000) unverified — tabulate `cipcode` before filtering
eng_by_gender <- completions |>
  filter(cipcode == 14, race == 99) |>
  group_by(sex) |>
  summarise(awards = sum(awards), .groups = "drop")

female_awards <- eng_by_gender |> filter(sex == 2) |> pull(awards)
total_awards <- eng_by_gender |> filter(sex == 99) |> pull(awards)
pct_women <- female_awards / total_awards * 100
```

### Institution Program Mix

Understand institutional focus:

```python
# Programs by field at institution
inst_mix = completions.filter(
    pl.col("unitid") == 110635
).group_by("cipcode").agg(
    pl.col("awards").sum().alias("completions")
).sort("completions", descending=True)
```

```r
# Programs by field at institution
inst_mix <- completions |>
  filter(unitid == 110635) |>
  group_by(cipcode) |>
  summarise(completions = sum(awards), .groups = "drop") |>
  arrange(desc(completions))
```

## Data Quality Issues

### Issue 1: Program Reporting vs Award Reporting

Some institutions may:
- Report programs not actually conferring awards
- Not report all programs

**Mitigation**: Focus on institutions with completions > 0.

### Issue 2: CIP Code Accuracy

Program classification may vary:
- Similar programs coded differently
- CIP updates change classifications
- Interdisciplinary programs difficult to classify

**Mitigation**: 
- Use 2-digit CIP for robustness
- Note CIP version in analysis

### Issue 3: Branch Campus Reporting

For multi-campus systems:
- Some report completions at campus level
- Some consolidate at system level

**Mitigation**: Check reporting patterns; aggregate to OPEID6 if needed.

### Issue 4: Double Majors

Double majors appear in completions for both fields.

```python
# Example
bio_chem_double_major_student = 1  # person
bio_completions += 1  # appears here
chem_completions += 1  # and here
total_completions += 2  # counts twice
total_completers += 1  # counts once
```

```r
# Example
bio_chem_double_major_student <- 1  # person
bio_completions <- bio_completions + 1  # appears here
chem_completions <- chem_completions + 1  # and here
total_completions <- total_completions + 2  # counts twice
total_completers <- total_completers + 1  # counts once
```

**Mitigation**: Use completers for people counts; note when using completions.

### Issue 5: Certificate Program Variability

Certificate programs vary widely:
- Some are a few weeks
- Some are nearly 2 years
- Industry certifications vs academic certificates

**Mitigation**: 
- Separate analysis by award level
- Focus on degree-level awards for comparability

## Variable Reference

> Verify these variable names against the live codebook. Use `get_codebook_url()` from `fetch-patterns.md`. Portal variable names differ from NCES documentation.

### Portal Completions Variables (2-digit CIP dataset)

The `completions-2digcip` (yearly) dataset contains disaggregated rows by race, sex, and award level:

| Portal Variable | Description |
|-----------------|-------------|
| `unitid` | Institution identifier |
| `year` | Data year (inferred: academic year ending in `year`; see SKILL.md § Year Field Meanings) |
| `cipcode` | CIP code (2-digit family, integer; values may be 6-digit-style, e.g. 110000 — unverified, tabulate before filtering) |
| `award_level` | Award level code (Portal codes 1-9, 20-24, 30-33, 99; see Award Levels) |
| `majornum` | Major number (1=first major, 2=second major) |
| `awards` | Count of awards conferred |
| `race` | Race/ethnicity (integer codes: 1-9, 99=Total) |
| `sex` | Sex (1=Male, 2=Female, 99=Total) |
| `fips` | State FIPS code |

The `completions-6digcip` (yearly) dataset has the same structure but with 6-digit CIP codes for more granular field analysis.

#### NCES Raw File Names (for reference only)

The following variable names appear in NCES documentation and raw IPEDS data files but are NOT used in the Portal:

| NCES Name | Portal Equivalent | Notes |
|-----------|-------------------|-------|
| `AWLEVEL` | `award_level` | Different code sets — see Award Levels above (e.g., bachelor's = NCES 5, Portal 7) |
| `CTOTALT` | `awards` (filtered to totals) | Portal uses disaggregated rows |
| `CIPCODE` | `cipcode` | Same name, but 2-digit vs 6-digit depends on dataset |
| `MAJORNUM` | `majornum` | Same concept |

### Completers Dataset

The `completers` dataset counts unduplicated individuals. Consult the codebook for variables:

```python
url = get_codebook_url("ipeds/codebook_colleges_ipeds_completers")
```

```r
# get_codebook_url() is a Python helper; in R, build the URL from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]
url <- paste0(mirror$root_url, "/", "ipeds/codebook_colleges_ipeds_completers", ".xls")
```

### CIP-Related Resources

| Resource | Description |
|----------|-------------|
| CIP code lookup | nces.ed.gov/ipeds/cipcode |
| CIP crosswalk | NCES provides version crosswalks |
| STEM designation | DHS STEM Designated Degree Program List |
