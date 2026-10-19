# Variable Definitions and Data Structure

> **CRITICAL: Portal vs Raw File Encoding**
>
> This document describes **Education Data Portal** integer encodings, which differ from Department of Education raw file string codes. The Portal converts categorical variables to integers for consistency across sources.
>
> | Context | Example: Bias Category | Crime Type |
> |---------|------------------------|------------|
> | **Portal (integers)** | `1` = Race, `2` = Religion | `1` = Murder, `13` = Intimidation |
> | Raw files (strings) | Text descriptions | Text descriptions |
>
> **Always use integer codes** when working with mirror data.

> **Codebook Authority:** The variable definitions in this document are summaries for convenience.
> The authoritative source for variable names, codes, and definitions is the codebook `.xls` file
> available in the data mirrors. Use `get_codebook_url("csafety/codebook_colleges_csafety_hate_crimes")` from `fetch-patterns.md`
> to download the codebook. If this document contradicts the codebook, trust the codebook and
> flag the discrepancy.

## Data Sources and Access

### Primary Source: Department of Education

The Campus Safety and Security (CSS) data is collected through an annual survey administered by the U.S. Department of Education, Office of Postsecondary Education.

**Official Data Portal**: https://ope.ed.gov/campussafety/

For data NOT available in the mirror system (primary offenses, VAWA, arrests/referrals, fire safety), access the Department of Education directly.

### Education Data Portal (Urban Institute) -- Mirror System

The Education Data Portal includes CSS hate crimes data integrated with other college-level data sources. Data is available via mirror downloads. See `datasets-reference.md` for canonical paths, `mirrors.yaml` for mirror configuration, and `fetch-patterns.md` for fetch code patterns.

**Available Dataset:**

| Dataset | Path | Codebook | Years |
|---------|------|----------|-------|
| Hate Crimes | `csafety/colleges_csafety_hate_crimes` | `csafety/codebook_colleges_csafety_hate_crimes` | 2005-2021 |

> **Note:** Only 1 campus safety dataset is available in the Portal mirrors. Consult `datasets-reference.md` for the authoritative list.

## Key Identifiers

### Identifiers in Portal Mirror Data (Hate Crimes Dataset)

The following columns are **empirically confirmed** in the `csafety/colleges_csafety_hate_crimes` dataset:

| Variable | Description | Type | Notes |
|----------|-------------|------|-------|
| `unitid` | IPEDS institution ID | Int64 | Primary identifier for joining with IPEDS data |
| `opeid` | OPE institution ID | String | 8-character; 126 null values in dataset |
| `inst_name` | Institution name | String | Official institution name |
| `fips` | State FIPS code | Int64 | 59 unique values (50 states + DC + territories) |

> **Note:** The Portal hate crimes data uses `inst_name` (not `instnm`). Columns such as `branch`, `address`, `city`, `zip`, `state`, `campus_id`, `main_campus`, `sector`, `control`, `enrollment`, `fte_enrollment`, `housing`, and `housing_capacity` are NOT present in the mirror dataset. Join with IPEDS directory data on `unitid` to obtain institutional characteristics.

### Identifiers in Full CSS Data (Department of Education Direct Access)

The full CSS survey data (available at https://ope.ed.gov/campussafety/) includes additional identifiers not present in the Portal mirror, such as `branch`, `address`, `city`, `state`, `zip`, `campus_id`, and `main_campus`. These are relevant when accessing data directly from the Department of Education rather than through the Portal mirrors.

## Institutional Characteristics

> **Not in Portal mirror data:** The variables below are available in the full CSS survey from the Department of Education but are NOT present in the Portal mirror hate crimes dataset. To obtain institutional characteristics, join the hate crimes data with the IPEDS directory dataset (`ipeds/colleges_ipeds_directory`) on `unitid`.

### Basic Characteristics (Full CSS / IPEDS Join)

| Variable | Description | Values |
|----------|-------------|--------|
| `sector` | Institution sector | Integer codes 1-9 (see sector codes below) |
| `level` | Institution level | 4-year, 2-year, Less than 2-year |
| `control` | Institution control | Public, Private nonprofit, Private for-profit |
| `enrollment` | Total enrollment | Integer |
| `fte_enrollment` | Full-time equivalent enrollment | Integer |

### Housing Information (Full CSS Only)

| Variable | Description | Values |
|----------|-------------|--------|
| `housing` | Has on-campus housing | Yes/No |
| `housing_capacity` | Housing bed capacity | Integer |

## Crime Statistics Variables

> **Not in Portal mirror data:** The individual crime count variables below (e.g., `murder`, `rape`, `robbery`) are available in the full CSS survey from the Department of Education but are NOT present in the Portal mirror hate crimes dataset. The mirror data contains only aggregate hate crime counts by location (see "Hate Crime Variables" section below).

### Criminal Offenses

| Variable | Description |
|----------|-------------|
| `murder` | Murder and non-negligent manslaughter |
| `negligent_manslaughter` | Manslaughter by negligence |
| `rape` | Rape |
| `fondling` | Fondling |
| `incest` | Incest |
| `statutory_rape` | Statutory rape |
| `robbery` | Robbery |
| `aggravated_assault` | Aggravated assault |
| `burglary` | Burglary |
| `motor_vehicle_theft` | Motor vehicle theft |
| `arson` | Arson |

### VAWA Offenses

| Variable | Description |
|----------|-------------|
| `domestic_violence` | Domestic violence |
| `dating_violence` | Dating violence |
| `stalking` | Stalking |

### Arrests and Referrals

| Variable | Description |
|----------|-------------|
| `weapons_arrests` | Weapons law violation arrests |
| `weapons_referrals` | Weapons law violation disciplinary referrals |
| `drug_arrests` | Drug law violation arrests |
| `drug_referrals` | Drug law violation disciplinary referrals |
| `liquor_arrests` | Liquor law violation arrests |
| `liquor_referrals` | Liquor law violation disciplinary referrals |

## Geographic Location Suffixes

> **Not in Portal mirror data:** The suffixed crime variables below (e.g., `robbery_oncampus`) are part of the full CSS survey, not the Portal mirror. In the Portal mirror hate crimes dataset, geographic breakdowns are provided as separate count columns: `on_campus_hate_crimes`, `residence_hall_hate_crimes`, `non_campus_hate_crimes`, `public_property_hate_crimes`, `other_hate_crimes`, and `total_hate_crimes`.

Crime variables in the full CSS data typically have suffixes indicating location:

| Suffix | Description |
|--------|-------------|
| `_oncampus` | On-campus (total) |
| `_oncampus_housing` or `_studenthousing` | On-campus student housing (subset of on-campus) |
| `_noncampus` | Noncampus property |
| `_publicproperty` | Public property |

### Example Variable Names

```
robbery_oncampus
robbery_oncampus_housing
robbery_noncampus
robbery_publicproperty
```

## Hate Crime Variables

> **This is the data available in Portal mirrors.** The hate crimes dataset is the only campus safety data in the mirror system.

### Structure

Hate crimes are reported by:
- Crime type (integer code)
- Bias category (integer code)
- Geographic location (as separate count columns)

### Bias Category Codes (Portal Integer Encoding)

Labels are the Portal variable-metadata labels for endpoint 130 (Education Data Portal API variable list, fetched 2026-10-19). Parenthesized meanings come from matching Portal 2017 rows to UC Berkeley's CY2017 Annual Security Report (ASR) hate-crime table. Code order 1-8 matches the column order of ED's CSS hate-crime form (Race, Religion, Sexual orientation, Gender, Gender Identity, Disability, Ethnicity, National Origin; 2019 CSS form), and code 2 = Religion also matched UC Riverside CY2015 and CY2016 ASR rows. Row-level Portal/ASR disagreements occur (UC Berkeley CY2016: two bias codes; LSU CY2017: one on-campus intimidation hate crime absent from the Portal); treat these as institution submission or revision differences, not a code change. The era column records which codes were **observed in the UC Berkeley (unitid 110635) 2010/2016 Portal probes**; it is an observation, not a documented rule.

| Code | Portal label | Meaning / notes | Observed in UC Berkeley 2010/2016 Portal probes |
|------|--------------|-----------------|-------------------------------------------------|
| `1` | Race | Anti-Black, Anti-White, Anti-Asian, etc. | 2010 and 2016 |
| `2` | Religion | Anti-Jewish, Anti-Islamic, Anti-Catholic, etc. | 2010 and 2016 |
| `3` | Sex | Sexual orientation (ASR match): Anti-Gay, Anti-Lesbian, Anti-Bisexual, etc. | 2010 and 2016 |
| `4` | Gender | Bias based on actual or perceived gender | 2010 and 2016 |
| `5` | Gender Identity | Anti-Transgender, Anti-Gender Non-Conforming | 2016 only |
| `6` | Disability | Anti-Physical Disability, Anti-Mental Disability | 2010 and 2016 |
| `7` | Ethnicity | Ethnicity (ASR match): Anti-Hispanic/Latino, etc. | 2016 only |
| `8` | Nationality | National origin (ASR match): based on country of birth | 2016 only |
| `9` | Ethnicity (Pre 2014) | Pre-2014 ethnicity category | 2010 only |
| `99` | Total | All bias categories combined | 2010 and 2016 |
| `null` | Missing | Data not reported | — |

> **Historical Note:** VAWA 2013 (Pub. L. 113-4) added national origin and gender identity to the statutory bias categories (ethnicity was already listed). The Portal carries pre-2014 ethnicity as code 9 and post-2014 ethnicity/national origin as codes 7/8 — do not splice 9 with 7 without documenting the break.

### Crime Type Codes (Portal Integer Encoding)

Labels are the Portal variable-metadata labels for endpoint 130; era column as above.

| Code | Portal label | Category | Observed in UC Berkeley 2010/2016 Portal probes |
|------|--------------|----------|-------------------------------------------------|
| `1` | Murder | Criminal offense | 2010 and 2016 |
| `2` | Rape | Sex offense (2014+ category) | 2016 only |
| `3` | Fondling | Sex offense (2014+ category) | 2016 only |
| `4` | Aggravated Assault | Criminal offense | 2010 and 2016 |
| `5` | Incest | Sex offense (2014+ category) | 2016 only |
| `6` | Statutory Rape | Sex offense (2014+ category) | 2016 only |
| `7` | Robbery | Criminal offense | 2010 and 2016 |
| `8` | Burglary | Criminal offense | 2010 and 2016 |
| `9` | Motor Vehicle Theft | Criminal offense | 2010 and 2016 |
| `10` | Arson | Criminal offense | 2010 and 2016 |
| `11` | Simple Assault | Hate crime only | 2010 and 2016 |
| `12` | Larceny | Hate crime only | 2010 and 2016 |
| `13` | Intimidation | Hate crime only | 2010 and 2016 |
| `14` | Destruction, Damage, or Vandalism | Hate crime only | 2010 and 2016 |
| `15` | Forcible Sex Offense | Sex offense (pre-2014 category) | 2010 only |
| `16` | Neglient Manslaughter [sic] (negligent manslaughter) | Criminal offense | 2010 only |
| `17` | Nonforcible Sex Offense | Sex offense (pre-2014 category) | 2010 only |
| `18` | Body Injury | Undocumented | Not observed |

> **Note:** Codes 11-14 (Simple Assault, Larceny, Intimidation, Vandalism) are hate-crime-only offenses. They are not standalone Clery crimes unless bias-motivated. VAWA offenses (domestic violence, dating violence, stalking) are **not** in the hate-crimes file and have no `crime_type` code. `crime_type == 16` is negligent manslaughter; it appeared in the 2010 probe but not the 2016 probe (the 2019 CSS hate-crime form has no negligent-manslaughter item, so code 16 likely appears only in pre-2014 data — inference from one form year).

> **Empirically verified:** The Portal mirror data contains crime_type values 1-18 only. Code `99` (Total) does NOT appear in the actual data, despite being documented in some references. Verify codes against the live codebook. Use `get_codebook_url()` from `fetch-patterns.md`.

### Hate Crime-Only Offenses

> Earlier versions of this file listed `larceny_theft_hate`, `simple_assault_hate`, `intimidation_hate`, `vandalism_hate`; these are not Portal/mirror columns. The hate-crimes file encodes these offenses as crime_type 11 (Simple Assault), 12 (Larceny), 13 (Intimidation), 14 (Destruction, Damage, or Vandalism); location counts are on_campus_/residence_hall_/non_campus_/public_property_/other_/total_hate_crimes.

## Fire Safety Variables

> **Not in Portal mirror data:** Fire safety variables are NOT available in the Portal mirrors. Access the Department of Education CSS portal directly for fire data.

### Fire Statistics

| Variable | Description |
|----------|-------------|
| `fires_total` | Total number of fires |
| `fire_injuries` | Number of fire-related injuries |
| `fire_deaths` | Number of fire-related deaths |
| `fire_damage_value` | Property damage from fires |

### Fire Cause Categories

| Code | Description |
|------|-------------|
| `unintentional` | Accidental fire |
| `intentional` | Deliberately set |
| `undetermined` | Cause unknown |

### Fire Safety Systems

| Variable | Description | Values |
|----------|-------------|--------|
| `fire_alarm` | Fire alarm system present | Yes/No |
| `sprinklers` | Sprinkler system | Full/Partial/None |
| `smoke_detectors` | Smoke detection | Yes/No |
| `fire_extinguishers` | Fire extinguishers present | Yes/No |
| `evacuation_plans` | Evacuation plans posted | Yes/No |
| `fire_drills` | Number of fire drills | Integer |

## Time Variables

| Variable | Description | Format | In Mirror Data? |
|----------|-------------|--------|-----------------|
| `year` | Calendar year in which the crime was reported (34 CFR 668.46(c)(3)); Portal metadata's generic label "Academic year (fall semester)" does not apply | YYYY (Int64) | Yes |
| `survey_year` | Year survey was submitted | YYYY | No (full CSS only) |

**Note**: Crime statistics are recorded for the calendar year (Jan 1 - Dec 31) in which the crime was reported (34 CFR 668.46(c)(3)). The survey submitted in fall of year X contains data for year X-1. The Portal mirror data contains `year` (2005-2021) but not `survey_year`.

## Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `null` | Missing/not reported | Data not submitted or not applicable |
| `0` | Zero incidents | Explicitly reported as zero (distinct from missing) |

> **Empirically verified:** The Portal mirror hate crimes dataset does NOT use `-1`, `-2`, or `-3` coded values for missing data. All missing data appears as `null` (e.g., 352,310 null values in the `bias` column). This differs from some other Portal datasets (e.g., CCD enrollment) that use negative integer codes. Always verify against the actual data.

## Data Quality Flags

> **Not in Portal mirror data:** The data quality flag columns (`imputed`, `revised`, `estimated`) are NOT present in the Portal mirror hate crimes dataset. These may be available in full CSS survey data from the Department of Education.

## Historical Variable Changes

### VAWA 2013 Changes (CY2013–2014 transitional; final definitions from CY2015)

VAWA 2013 (Pub. L. 113-4) required good-faith reporting of these offenses starting with calendar-year 2013 statistics in the October 1, 2014 ASR; the final regulations (79 FR 62752, Oct. 20, 2014) took effect July 1, 2015, and statistics for 2013–2014 did not have to be revised to the final definitions.

**Added Variables**:
- `dating_violence`
- `domestic_violence`
- `stalking`
- Hate crime bias: gender identity and national origin added to the statutory list (ethnicity was already listed). In the Portal, pre-2014 ethnicity is `bias` code 9; 2014+ ethnicity and national origin are codes 7 and 8

**Changed Variables**:
- Sex offense definitions changed
- `rape` definition expanded
- Previous categories (forcible/non-forcible) replaced by rape, fondling, incest, statutory rape (79 FR 62752). In the Portal hate-crimes file, codes 15/17 (forcible/nonforcible) were observed in the UC Berkeley 2010 probe and codes 2/3/5/6 in the 2016 probe

### 2008 Changes (HEOA)

**Added Variables**:
- All fire safety variables
- Enhanced emergency notification data

### Pre-2014 Sex Offense Variables

Before the VAWA final regulations (79 FR 62752; final definitions apply from CY2015, with CY2013–2014 transitional), sex offenses were categorized as:

**Forcible Sex Offenses**:
- Forcible rape
- Forcible sodomy
- Sexual assault with an object
- Forcible fondling

**Non-Forcible Sex Offenses**:
- Incest
- Statutory rape

**Note**: These categories are not directly comparable to the final-rule categories (rape, fondling, incest, statutory rape; CY2015+, CY2013–2014 transitional).

## Common Filters (Portal Mirror Data)

| Filter | Description | Example |
|--------|-------------|---------|
| `year` | Calendar year | `pl.col("year") == 2021` |
| `unitid` | Institution ID (IPEDS) | `pl.col("unitid") == 110635` |
| `fips` | State FIPS code | `pl.col("fips") == 6` (California) |
| `crime_type` | Crime type code (1-18) | `pl.col("crime_type") == 13` (Intimidation) |
| `bias` | Bias category code (1-9, 99) | `pl.col("bias") == 1` (Race) |

### Sector Codes (Portal Integer Encoding)

| Code | Description |
|------|-------------|
| `1` | Public, 4-year or above |
| `2` | Private nonprofit, 4-year or above |
| `3` | Private for-profit, 4-year or above |
| `4` | Public, 2-year |
| `5` | Private nonprofit, 2-year |
| `6` | Private for-profit, 2-year |
| `7` | Public, less-than 2-year |
| `8` | Private nonprofit, less-than 2-year |
| `9` | Private for-profit, less-than 2-year |

## Joining with Other Data

### Linking to IPEDS

Use `unitid` to join CSS data with IPEDS data:
- Directory information
- Enrollment data
- Financial data
- Graduation rates

### Linking to College Scorecard

Use `unitid` to join with College Scorecard data:
- Earnings outcomes
- Student debt
- Default rates

### Example Join Logic

```
CSS data (campus safety statistics)
  ↓ join on unitid
IPEDS directory (institutional characteristics)
  ↓ join on unitid
College Scorecard (outcomes data)
```

## Data Availability by Year

| Data Category | First Year Available |
|---------------|---------------------|
| Criminal offenses | 2001 |
| Arrests/referrals | 2001 |
| Hate crimes | 2001 (expanded 2008) |
| VAWA offenses | 2013 (good-faith reporting; final-rule definitions from 2015) |
| Fire safety | 2009 |

**Note**: Data coverage and quality may vary in earlier years.
