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
> **Always use integer codes** when querying the Portal API or working with mirror data.

## Data Sources and Access

### Primary Source: Department of Education

The Campus Safety and Security (CSS) data is collected through an annual survey administered by the U.S. Department of Education, Office of Postsecondary Education.

**Official Data Portal**: https://ope.ed.gov/campussafety/

**Access Options**:
1. **Web tool**: Search individual institutions or compare up to 4 schools
2. **Custom download**: Select variables and institutions for bulk download
3. **Trend data**: View trends over time for specific questions

### Education Data Portal (Urban Institute) / HuggingFace Mirror

The Education Data Portal includes CSS data integrated with other college-level data sources. Data is available via mirror downloads.

**Mirror Location**: `college-university/campus-crime/` in the HuggingFace mirror

**Available Endpoints**:
- `hate-crimes/colleges_csafety_hate_crimes.parquet` - Hate crime statistics by institution, year, crime type, and bias category

**Years Available**: 2005-2021 (varies by variable)

## Key Identifiers

### Institution Identifiers

| Variable | Description | Format | Notes |
|----------|-------------|--------|-------|
| `unitid` | IPEDS institution ID | 6-digit integer | Primary identifier for joining with IPEDS data |
| `opeid` | OPE institution ID | 8-character | Used in federal student aid system |
| `instnm` | Institution name | String | Official institution name |
| `branch` | Campus/branch identifier | String | For institutions with multiple campuses |
| `address` | Street address | String | Institution address |
| `city` | City | String | Location city |
| `state` | State | 2-character | State abbreviation |
| `zip` | ZIP code | String | 5 or 9 digit |

### Campus Identification

Multi-campus institutions report separately for each campus. Key variables:

| Variable | Description |
|----------|-------------|
| `campus_id` | Unique campus identifier |
| `main_campus` | Indicator for main campus |
| `branch_name` | Name of branch campus |

## Institutional Characteristics

### Basic Characteristics

| Variable | Description | Values |
|----------|-------------|--------|
| `sector` | Institution sector | Public 4-year, Private nonprofit 4-year, Private for-profit 4-year, Public 2-year, etc. |
| `level` | Institution level | 4-year, 2-year, Less than 2-year |
| `control` | Institution control | Public, Private nonprofit, Private for-profit |
| `enrollment` | Total enrollment | Integer |
| `fte_enrollment` | Full-time equivalent enrollment | Integer |

### Housing Information

| Variable | Description | Values |
|----------|-------------|--------|
| `housing` | Has on-campus housing | Yes/No |
| `housing_capacity` | Housing bed capacity | Integer |

## Crime Statistics Variables

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

Crime variables typically have suffixes indicating location:

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

### Structure

Hate crimes are reported by:
- Crime type (integer code)
- Bias category (integer code)
- Geographic location

### Bias Category Codes (Portal Integer Encoding)

| Code | Bias Category | Notes |
|------|---------------|-------|
| `1` | Race | Anti-Black, Anti-White, Anti-Asian, etc. |
| `2` | Religion | Anti-Jewish, Anti-Islamic, Anti-Catholic, etc. |
| `3` | Sexual Orientation | Anti-Gay, Anti-Lesbian, Anti-Bisexual, etc. |
| `4` | Gender | Bias based on actual or perceived gender |
| `5` | Gender Identity | Anti-Transgender, Anti-Gender Non-Conforming (2014+) |
| `6` | Ethnicity | Anti-Hispanic/Latino, etc. (separated from National Origin in 2014) |
| `7` | National Origin | Based on country of birth (separated from Ethnicity in 2014) |
| `8` | Disability | Anti-Physical Disability, Anti-Mental Disability |
| `9` | Unknown/Other | Bias category not specified |
| `99` | Total | All bias categories combined |
| `null` | Missing | Data not reported |

> **Historical Note:** Prior to 2014, National Origin (7) and Ethnicity (6) were combined. Gender Identity (5) was added in 2014.

### Crime Type Codes (Portal Integer Encoding)

| Code | Crime Type | Category |
|------|------------|----------|
| `1` | Murder/Non-negligent Manslaughter | Primary Offense |
| `2` | Manslaughter by Negligence | Primary Offense |
| `3` | Rape | Sex Offense |
| `4` | Fondling | Sex Offense |
| `5` | Incest | Sex Offense |
| `6` | Statutory Rape | Sex Offense |
| `7` | Robbery | Primary Offense |
| `8` | Aggravated Assault | Primary Offense |
| `9` | Burglary | Property Crime |
| `10` | Motor Vehicle Theft | Property Crime |
| `11` | Arson | Property Crime |
| `12` | Larceny-Theft | Hate Crime Only |
| `13` | Simple Assault | Hate Crime Only |
| `14` | Intimidation | Hate Crime Only |
| `15` | Destruction/Damage/Vandalism | Hate Crime Only |
| `16` | Domestic Violence | VAWA Offense (2014+) |
| `17` | Dating Violence | VAWA Offense (2014+) |
| `18` | Stalking | VAWA Offense (2014+) |
| `99` | Total | All crime types combined |

> **Note:** Crime types 12-15 (Larceny-Theft, Simple Assault, Intimidation, Vandalism) are only reported as hate crimes. They are not standalone Clery crimes unless bias-motivated.

### Hate Crime-Only Offenses

| Variable | Description |
|----------|-------------|
| `larceny_theft_hate` | Larceny-theft (hate crime only) |
| `simple_assault_hate` | Simple assault (hate crime only) |
| `intimidation_hate` | Intimidation (hate crime only) |
| `vandalism_hate` | Destruction/damage/vandalism of property (hate crime only) |

## Fire Safety Variables

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

| Variable | Description | Format |
|----------|-------------|--------|
| `year` | Calendar year of data | YYYY |
| `survey_year` | Year survey was submitted | YYYY |

**Note**: Crime statistics are for calendar years (Jan 1 - Dec 31). The survey submitted in fall of year X contains data for year X-1.

## Missing Data Codes (Portal Integer Encoding)

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing/Not reported | State/institution did not report |
| `-2` | Not applicable | Item doesn't apply to this institution |
| `-3` | Suppressed | Data suppressed for privacy protection |
| `null` | Genuinely missing | No data available |

> **Note:** Unlike some other Portal datasets (e.g., CCD enrollment where `-1` means Pre-K), campus safety data uses standard missing codes where negative values always indicate missing/suppressed data.

## Data Quality Flags

Some datasets include flags indicating data quality:

| Flag | Meaning |
|------|---------|
| `imputed` | Value was imputed |
| `revised` | Value was corrected after initial submission |
| `estimated` | Value is an estimate |

## Historical Variable Changes

### 2014 Changes (VAWA)

**Added Variables**:
- `dating_violence`
- `domestic_violence`
- `stalking`
- Hate crime bias: `gender_identity`
- Separate `national_origin` and `ethnicity`

**Changed Variables**:
- Sex offense definitions changed
- `rape` definition expanded
- Previous categories (forcible/non-forcible) restructured

### 2008 Changes (HEOA)

**Added Variables**:
- All fire safety variables
- Enhanced emergency notification data

### Pre-2014 Sex Offense Variables

Prior to 2014, sex offenses were categorized as:

**Forcible Sex Offenses**:
- Forcible rape
- Forcible sodomy
- Sexual assault with an object
- Forcible fondling

**Non-Forcible Sex Offenses**:
- Incest
- Statutory rape

**Note**: These categories are not directly comparable to post-2014 categories.

## Common Filters

### For Parquet Downloads

| Filter | Description | Example |
|--------|-------------|---------|
| `year` | Calendar year | `pl.col("year") == 2021` |
| `unitid` | Institution ID (IPEDS) | `pl.col("unitid") == 110635` |
| `fips` | State FIPS code | `pl.col("fips") == 6` (California) |
| `crime_type` | Crime type code | `pl.col("crime_type") == 14` (Intimidation) |
| `bias` | Bias category code | `pl.col("bias") == 1` (Race) |

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
| VAWA offenses | 2014 |
| Fire safety | 2009 |

**Note**: Data coverage and quality may vary in earlier years.
