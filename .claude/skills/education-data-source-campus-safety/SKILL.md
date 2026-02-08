---
name: education-data-source-campus-safety
description: Campus Safety and Security (CSS) data from the Clery Act reporting system. Covers campus crime statistics, fire safety, VAWA offenses, hate crimes, and geographic reporting categories. Use when analyzing college/university crime data, understanding Clery Act requirements, or interpreting campus safety statistics and their limitations.
metadata:
  audience: data-analysts
  domain: education-data
---

# Campus Safety and Security (CSS) Data Source

Guide to understanding and using campus crime and fire safety data collected under the Clery Act.

## What is Campus Safety and Security Data?

The Campus Safety and Security (CSS) data comes from the annual survey required by the Jeanne Clery Disclosure of Campus Security Policy and Campus Crime Statistics Act:

- **Federal mandate**: All Title IV institutions must report crime and fire statistics annually
- **Consumer protection**: Designed to inform students, parents, and employees about campus safety
- **Primary source**: U.S. Department of Education Office of Postsecondary Education
- **Coverage**: All postsecondary institutions receiving federal financial aid
- **Reporting period**: Calendar year (January 1 - December 31)
- **Official portal**: https://ope.ed.gov/campussafety/

> **CRITICAL: Limited Data in Portal Mirrors**
>
> The Education Data Portal mirrors contain **only hate crimes data**. For other campus safety data (primary offenses, VAWA offenses, arrests/referrals, fire safety), access the Department of Education directly at https://ope.ed.gov/campussafety/

> **CRITICAL: Portal Integer Encoding**
>
> The Education Data Portal and HuggingFace mirror use **integer codes** for categorical variables, not string labels:
>
> | Variable | Example Code | Meaning |
> |----------|--------------|---------|
> | `bias` | `1` | Race-based bias |
> | `crime_type` | `14` | Intimidation |
> | `fips` | `6` | California |
>
> See `./references/variable-definitions.md` for complete code mappings.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `clery-act.md` | Legal framework, history, reporting requirements | Understanding compliance context |
| `crime-categories.md` | Criminal offenses, definitions, classification rules | Interpreting crime statistics |
| `vawa-offenses.md` | Dating violence, domestic violence, stalking | Analyzing gender-based violence data |
| `hate-crimes.md` | Bias categories, additional offenses, classification | Working with hate crime statistics |
| `campus-geography.md` | On-campus, residence halls, public property, noncampus | Understanding location categories |
| `fire-safety.md` | Fire statistics, safety systems, HEOA requirements | Analyzing residential fire data |
| `arrests-referrals.md` | Drug, alcohol, weapons violations | Working with disciplinary data |
| `variable-definitions.md` | Key variables, data structure, identifiers | Building queries |
| `limitations.md` | Underreporting, comparability issues, interpretation | Critical data analysis |

## Decision Trees

### What type of crime data do I need?

```
Crime data type?
├─ Violent crimes (murder, assault, robbery, sex offenses)
│   └─ See ./references/crime-categories.md
├─ Property crimes (burglary, motor vehicle theft, arson)
│   └─ See ./references/crime-categories.md
├─ Sex offenses (rape, fondling, incest, statutory rape)
│   └─ See ./references/crime-categories.md
├─ Dating/domestic violence, stalking
│   └─ See ./references/vawa-offenses.md
├─ Hate crimes (bias-motivated)
│   └─ See ./references/hate-crimes.md
├─ Drug/alcohol/weapons violations
│   └─ See ./references/arrests-referrals.md
└─ Fire incidents in residence halls
    └─ See ./references/fire-safety.md
```

### Where did the crime occur?

```
Understanding crime location?
├─ On-campus (main campus buildings/grounds)
│   └─ See ./references/campus-geography.md
├─ On-campus student housing (subset of on-campus)
│   └─ See ./references/campus-geography.md
├─ Public property (streets, sidewalks adjacent to campus)
│   └─ See ./references/campus-geography.md
├─ Noncampus (off-site but institution-controlled)
│   └─ See ./references/campus-geography.md
└─ Not sure which category
    └─ See ./references/campus-geography.md (definitions section)
```

### Can I compare schools?

```
Planning institutional comparisons?
├─ Want to rank schools by safety
│   └─ See ./references/limitations.md (CRITICAL: comparability issues)
├─ Comparing similar institution types
│   └─ See ./references/limitations.md (controlling for factors)
├─ Analyzing trends over time
│   └─ See ./references/limitations.md (reporting changes)
└─ Understanding what statistics mean
    └─ See ./references/limitations.md (interpretation guidance)
```

## Quick Reference: Crime Categories

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
| `16` | Domestic Violence | VAWA (2014+) |
| `17` | Dating Violence | VAWA (2014+) |
| `18` | Stalking | VAWA (2014+) |
| `99` | Total | All types combined |

### Bias Category Codes (Portal Integer Encoding)

| Code | Bias Category | Notes |
|------|---------------|-------|
| `1` | Race | Most common category |
| `2` | Religion | Anti-Jewish, Anti-Islamic, etc. |
| `3` | Sexual Orientation | Anti-Gay, Anti-Lesbian, etc. |
| `4` | Gender | Based on perceived gender |
| `5` | Gender Identity | Added 2014 |
| `6` | Ethnicity | Separated from National Origin in 2014 |
| `7` | National Origin | Based on country of birth |
| `8` | Disability | Physical or mental |
| `9` | Unknown/Other | |
| `99` | Total | All bias categories combined |

### VAWA Offenses (Added 2013)

| Code | Offense | Definition |
|------|---------|------------|
| `16` | Domestic Violence | Violence by current/former spouse, cohabitant, or similar |
| `17` | Dating Violence | Violence by person in romantic/intimate relationship |
| `18` | Stalking | Course of conduct causing fear for safety |

### Hate Crime-Only Offenses

Codes 12-15 are only reported as hate crimes. They are not standalone Clery crimes unless bias-motivated.

### Arrests and Disciplinary Referrals

| Category | What's Counted |
|----------|----------------|
| Liquor Law Violations | Arrests + Disciplinary referrals |
| Drug Law Violations | Arrests + Disciplinary referrals |
| Weapons Violations | Arrests + Disciplinary referrals |

## Quick Reference: Geographic Categories

| Location | Definition | Reported Separately? |
|----------|------------|---------------------|
| On-Campus | Buildings/property owned/controlled by institution, reasonably contiguous | Yes |
| On-Campus Student Housing | Residence halls (subset of on-campus) | Yes (as subset) |
| Noncampus | Institution-owned/controlled property not contiguous; student org properties | Yes |
| Public Property | Streets, sidewalks, parking within or immediately adjacent to campus | Yes |

## Quick Reference: Fire Safety Data

Fire data is reported only for **on-campus student housing facilities**:

| Data Element | Description |
|--------------|-------------|
| Number of fires | Total fires per building per year |
| Cause of fire | Intentional, unintentional, undetermined |
| Injuries | Fire-related injuries requiring treatment |
| Deaths | Fire-related fatalities |
| Property damage | Estimated dollar value |
| Fire safety systems | Sprinklers, alarms, smoke detectors, etc. |

## Data Access

### HuggingFace Mirror (Recommended)

Campus safety data is available via the Education Data Portal HuggingFace mirror:

```python
import polars as pl

# Download hate crimes data
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/campus-crime/hate-crimes/colleges_csafety_hate_crimes.parquet"
df = pl.read_parquet(url)

# Filter by bias category (1 = Race)
race_crimes = df.filter(pl.col("bias") == 1)

# Filter by crime type (14 = Intimidation)
intimidation = df.filter(pl.col("crime_type") == 14)
```

**Available Files**:
- `college-university/campus-crime/hate-crimes/colleges_csafety_hate_crimes.parquet`

**Years Available**: 2005-2021

### Direct from Department of Education

- **Web tool**: https://ope.ed.gov/campussafety/
- **Bulk download**: Available through Campus Safety website
- **Custom reports**: Generate by institution, state, or sector

## Key Identifiers

| Variable | Description | Format |
|----------|-------------|--------|
| `unitid` | IPEDS institution ID | 6-digit integer |
| `opeid` | OPE institution ID | 8-character |
| `instnm` | Institution name | String |
| `branch` | Campus/branch identifier | String |

## Important Caveats

**Before analyzing CSS data, read `./references/limitations.md`**

Key issues:
1. **Underreporting**: Many crimes go unreported; CSS captures only reported incidents
2. **Definition changes**: Crime definitions have changed over time (especially sex offenses in 2014)
3. **Institutional variation**: Reporting practices vary across institutions
4. **Geography complexity**: Multi-campus institutions have complex reporting
5. **Not comparable to FBI data**: Different definitions and scope
6. **Higher numbers may indicate better reporting**: More crimes reported can mean more trust in reporting systems

## Reporting Timeline

| Date | Action |
|------|--------|
| Calendar year | Data collection period |
| October 1 | Annual Security Report (ASR) due |
| October 15 | CSS survey submission deadline |
| Following spring | Data available publicly |

## Cross-Reference to Related Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `education-data-explorer` | Find available endpoints | Identifying what data exists |
| `education-data-query` | Construct API queries | After identifying variables |
| `education-data-source-ipeds` | Link to institutional characteristics | Joining with IPEDS directory |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Clery Act history and requirements | `./references/clery-act.md` |
| Criminal offense definitions | `./references/crime-categories.md` |
| Sex offense classification | `./references/crime-categories.md` |
| VAWA amendments | `./references/vawa-offenses.md` |
| Dating violence definition | `./references/vawa-offenses.md` |
| Domestic violence definition | `./references/vawa-offenses.md` |
| Stalking definition | `./references/vawa-offenses.md` |
| Hate crime bias categories | `./references/hate-crimes.md` |
| Hate crime offenses | `./references/hate-crimes.md` |
| On-campus definition | `./references/campus-geography.md` |
| Residence hall reporting | `./references/campus-geography.md` |
| Public property definition | `./references/campus-geography.md` |
| Noncampus property | `./references/campus-geography.md` |
| Fire statistics | `./references/fire-safety.md` |
| Fire safety systems | `./references/fire-safety.md` |
| Arrests vs referrals | `./references/arrests-referrals.md` |
| Drug/alcohol violations | `./references/arrests-referrals.md` |
| Weapons violations | `./references/arrests-referrals.md` |
| Variable names and codes | `./references/variable-definitions.md` |
| Underreporting issues | `./references/limitations.md` |
| Institutional comparisons | `./references/limitations.md` |
| Trend analysis caveats | `./references/limitations.md` |
| Data interpretation | `./references/limitations.md` |
