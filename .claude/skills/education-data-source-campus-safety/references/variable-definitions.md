# Variable Definitions and Data Structure

## Data Sources and Access

### Primary Source: Department of Education

The Campus Safety and Security (CSS) data is collected through an annual survey administered by the U.S. Department of Education, Office of Postsecondary Education.

**Official Data Portal**: https://ope.ed.gov/campussafety/

**Access Options**:
1. **Web tool**: Search individual institutions or compare up to 4 schools
2. **Custom download**: Select variables and institutions for bulk download
3. **Trend data**: View trends over time for specific questions

### Urban Institute Education Data Portal

The Education Data Portal includes CSS data integrated with other college-level data sources.

**Base Endpoint**: `/api/v1/college-university/css/`

**Years Available**: Varies by variable; generally 2001-present

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
- Crime type
- Bias category
- Geographic location

### Bias Category Codes

| Code | Bias Category |
|------|---------------|
| `race` | Race |
| `religion` | Religion |
| `sexual_orientation` | Sexual orientation |
| `gender` | Gender |
| `gender_identity` | Gender identity |
| `ethnicity` | Ethnicity |
| `national_origin` | National origin |
| `disability` | Disability |

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

## Missing Data Codes

| Code | Meaning |
|------|---------|
| `-1` | Not applicable |
| `-2` | Data not available |
| `-3` | Suppressed for privacy |
| `null` / blank | Missing data |

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

### For API Queries

| Filter | Description | Example |
|--------|-------------|---------|
| `year` | Calendar year | `year=2022` |
| `unitid` | Institution ID | `unitid=110635` |
| `state` | State code | `state=CA` |
| `sector` | Institution sector | `sector=1` (public 4-year) |

### Sector Codes

| Code | Description |
|------|-------------|
| 1 | Public, 4-year or above |
| 2 | Private nonprofit, 4-year or above |
| 3 | Private for-profit, 4-year or above |
| 4 | Public, 2-year |
| 5 | Private nonprofit, 2-year |
| 6 | Private for-profit, 2-year |
| 7 | Public, less-than 2-year |
| 8 | Private nonprofit, less-than 2-year |
| 9 | Private for-profit, less-than 2-year |

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
