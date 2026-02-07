# EADA Variable Definitions

Detailed definitions for key EADA variables available through the Education Data Portal.

> **CRITICAL: Portal Integer Encoding**
>
> This document describes **Education Data Portal** integer encodings. The Portal converts categorical variables to integers for consistency across sources.
>
> | Variable | Code | Meaning |
> |----------|------|---------|
> | `ath_classification_code` | `1` | NCAA Division I FBS |
> | `ath_classification_code` | `2` | NCAA Division I FCS |
> | `ath_classification_code` | `8` | Other (see `ath_classification_other` for detail) |
> | `fips` | `6` | California |
> | Any variable | `-1` | Missing/not reported |
> | Any variable | `-2` | Not applicable |
> | Any variable | `-3` | Suppressed data |
>
> See the Athletic Classification Codes section below for complete mappings.

## Institution Identification

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier (6 digits) |
| `year` | Integer | Reporting year (fiscal year ending) |
| `institution_name` | String | Name of institution |
| `fips` | Integer | State FIPS code (see FIPS codes below) |
| `sector` | Integer | Institutional sector (see codes below) |

### Sector Codes

| Code | Description |
|------|-------------|
| 1 | Public, 4-year or above |
| 2 | Private nonprofit, 4-year or above |
| 3 | Private for-profit, 4-year or above |

### State FIPS Codes (Portal Integer Encoding)

| Code | State | Code | State | Code | State |
|------|-------|------|-------|------|-------|
| 1 | Alabama | 18 | Indiana | 35 | New Mexico |
| 2 | Alaska | 19 | Iowa | 36 | New York |
| 4 | Arizona | 20 | Kansas | 37 | North Carolina |
| 5 | Arkansas | 21 | Kentucky | 38 | North Dakota |
| 6 | California | 22 | Louisiana | 39 | Ohio |
| 8 | Colorado | 23 | Maine | 40 | Oklahoma |
| 9 | Connecticut | 24 | Maryland | 41 | Oregon |
| 10 | Delaware | 25 | Massachusetts | 42 | Pennsylvania |
| 11 | District of Columbia | 26 | Michigan | 44 | Rhode Island |
| 12 | Florida | 27 | Minnesota | 45 | South Carolina |
| 13 | Georgia | 28 | Mississippi | 46 | South Dakota |
| 15 | Hawaii | 29 | Missouri | 47 | Tennessee |
| 16 | Idaho | 30 | Montana | 48 | Texas |
| 17 | Illinois | 31 | Nebraska | 49 | Utah |
| | | 32 | Nevada | 50 | Vermont |
| | | 33 | New Hampshire | 51 | Virginia |
| | | 34 | New Jersey | 53 | Washington |
| | | | | 54 | West Virginia |
| | | | | 55 | Wisconsin |
| | | | | 56 | Wyoming |

**Territories and Special Codes:**
| Code | Jurisdiction |
|------|--------------|
| 60 | American Samoa |
| 66 | Guam |
| 69 | Northern Mariana Islands |
| 72 | Puerto Rico |
| 78 | Virgin Islands |

### Athletic Classification Codes (Portal Integer Encoding)

| Code | Athletic Division |
|------|-------------------|
| 1 | NCAA Division I FBS |
| 2 | NCAA Division I FCS |
| 3 | NCAA Division I (without football) |
| 4 | NCAA Division II (with football) |
| 5 | NCAA Division II (without football) |
| 6 | NCAA Division III (with football) |
| 7 | NCAA Division III (without football) |
| 8 | Other (see `ath_classification_other` field) |
| 9 | NAIA Division I |
| 10 | NAIA Division II |
| 12 | NJCAA Division I |
| 13 | NJCAA Division II |
| 14 | NJCAA Division III |
| 15 | NCCAA Division I |
| 16 | NCCAA Division II |
| 17 | CCCAA (California Community Colleges) |
| 18 | Independent |
| 19 | NWAC (Northwest Athletic Conference) |
| 20 | USCAA (United States Collegiate Athletic Association) |
| -1 | Missing/not reported |
| -2 | Not applicable |
| -3 | Suppressed |

> **Note:** Code `8` (Other) is used for institutions that don't fit the standard classifications. Check the `ath_classification_other` string field for additional detail.

## Participation Variables

### Institution-Level Participation

| Variable | Type | Description |
|----------|------|-------------|
| `partic_men` | Integer | Unduplicated count of male participants across all sports |
| `partic_women` | Integer | Unduplicated count of female participants across all sports |
| `partic_coed_men` | Integer | Male participants on coed teams |
| `partic_coed_women` | Integer | Female participants on coed teams |

### Definition: "Participant"

A participant is a student who:
- Is listed on the varsity team roster
- As of the first day of the first scheduled contest
- During the reporting year

**Includes**:
- Scholarship athletes
- Walk-ons
- Redshirts (if on roster)

**Excludes**:
- Practice players not on varsity roster
- Club sport participants
- Junior varsity (unless no varsity)

### Unduplicated vs. Duplicated

- **Unduplicated**: Multi-sport athletes counted once for institution total
- **Duplicated**: Summing sport-level data will double-count multi-sport athletes

## Coaching Variables

### Head Coach Counts

| Variable | Type | Description |
|----------|------|-------------|
| `hdcoach_men_male_ft` | Integer | Full-time male head coaches of men's teams |
| `hdcoach_men_male_pt` | Integer | Part-time male head coaches of men's teams |
| `hdcoach_men_female_ft` | Integer | Full-time female head coaches of men's teams |
| `hdcoach_men_female_pt` | Integer | Part-time female head coaches of men's teams |
| `hdcoach_women_male_ft` | Integer | Full-time male head coaches of women's teams |
| `hdcoach_women_male_pt` | Integer | Part-time male head coaches of women's teams |
| `hdcoach_women_female_ft` | Integer | Full-time female head coaches of women's teams |
| `hdcoach_women_female_pt` | Integer | Part-time female head coaches of women's teams |
| `hdcoach_coed_male_ft` | Integer | Full-time male head coaches of coed teams |
| `hdcoach_coed_male_pt` | Integer | Part-time male head coaches of coed teams |
| `hdcoach_coed_female_ft` | Integer | Full-time female head coaches of coed teams |
| `hdcoach_coed_female_pt` | Integer | Part-time female head coaches of coed teams |

### Assistant Coach Counts

Same structure as head coaches with `asstcoach_` prefix.

### Definition: Full-Time vs. Part-Time

| Status | Definition |
|--------|------------|
| **Full-time** | Employed by institution on a full-time basis (regardless of coaching assignment) |
| **Part-time** | Not full-time employees; may include graduate assistants |

**Note**: A full-time employee who coaches part-time is counted as full-time.

## Salary Variables

### Coach Salary Averages

| Variable | Type | Description |
|----------|------|-------------|
| `salary_men_coach` | Decimal | Average annual salary of head coaches of men's teams |
| `salary_women_coach` | Decimal | Average annual salary of head coaches of women's teams |
| `salary_coed_coach` | Decimal | Average annual salary of head coaches of coed teams |
| `asstcoach_salary_men` | Decimal | Average annual salary of assistant coaches of men's teams |
| `asstcoach_salary_women` | Decimal | Average annual salary of assistant coaches of women's teams |
| `asstcoach_salary_coed` | Decimal | Average annual salary of assistant coaches of coed teams |

### Definition: Salary

**Includes**:
- Base salary
- Bonuses from the institution
- Any supplemental pay from institutional funds

**Excludes**:
- Income from camps/clinics (unless institutional compensation)
- Media/broadcast contracts
- Apparel/equipment deals
- Outside speaking fees
- Deferred compensation
- Benefits (health insurance, retirement)

### Calculation Method

```
Average Salary = Total Salaries Paid / Number of Paid Coaching Positions
```

**Note**: Volunteer coaches (0 salary) may or may not be excluded from denominator depending on reporting practice.

## Expense Variables

### Operating (Game-Day) Expenses

| Variable | Type | Description |
|----------|------|-------------|
| `exp_men` | Decimal | Operating expenses attributable to men's teams |
| `exp_women` | Decimal | Operating expenses attributable to women's teams |
| `exp_coed` | Decimal | Operating expenses attributable to coed teams |

### Definition: Operating Expenses

**Includes**:
- Team travel (transportation, lodging, meals)
- Equipment and uniforms
- Game officials
- Game-day support personnel

**Excludes**:
- Coaching salaries (separate)
- Athletic scholarships (separate)
- Facilities (capital)
- Administrative overhead

### Recruiting Expenses

| Variable | Type | Description |
|----------|------|-------------|
| `recruiting_exp_men` | Decimal | Recruiting expenses for men's teams |
| `recruiting_exp_women` | Decimal | Recruiting expenses for women's teams |
| `recruiting_exp_coed` | Decimal | Recruiting expenses for coed teams |

### Definition: Recruiting Expenses

**Includes**:
- Travel for coaching staff on recruiting trips
- Lodging and meals during recruiting
- Prospect visit expenses (on-campus)
- Communication costs
- Recruiting services/subscriptions

## Revenue Variables

### Team Revenues

| Variable | Type | Description |
|----------|------|-------------|
| `rev_men` | Decimal | Revenues attributable to men's teams |
| `rev_women` | Decimal | Revenues attributable to women's teams |
| `rev_coed` | Decimal | Revenues attributable to coed teams |

### Definition: Revenue

**Includes**:
- Ticket sales
- Game guarantees received
- Broadcast rights (attributed portion)
- NCAA/conference distributions (attributed)
- Program sales
- Concessions (if tracked by sport)
- Donations restricted to specific sports

**Excludes**:
- Student fees (typically)
- General institutional support
- Unrestricted donations

### Revenue Attribution Challenges

Many revenue sources are shared (conference distributions, multimedia rights) and attribution varies by institution.

## Athletic Aid Variables

### Financial Assistance

| Variable | Type | Description |
|----------|------|-------------|
| `aid_men` | Decimal | Total athletic aid to male students |
| `aid_women` | Decimal | Total athletic aid to female students |
| `aid_num_men` | Integer | Number of male students receiving athletic aid |
| `aid_num_women` | Integer | Number of female students receiving athletic aid |

### Definition: Athletic Aid

Athletic student aid includes:
- Scholarships specifically for athletics
- Grants-in-aid designated for athletes
- Tuition waivers awarded for athletic participation
- Room, board, and required fees if athletically related

**Excludes**:
- Need-based aid that happens to go to athletes
- Academic merit aid to athletes
- Non-athletic institutional aid

### Equivalency Calculation

For Division I:
```
Full Scholarship Equivalency = Total Aid Dollars / Cost of Full Scholarship
```

**Note**: EADA reports total dollars, not equivalencies.

## Calculated Fields

### Common Calculations

```python
# Total participation
total_partic = partic_men + partic_women

# Female participation share
female_share = partic_women / total_partic

# Total expenses
total_exp = exp_men + exp_women + exp_coed

# Per-athlete expense
exp_per_male = exp_men / partic_men
exp_per_female = exp_women / partic_women

# Aid proportionality
aid_share_female = aid_women / (aid_men + aid_women)
```

## Missing Value Interpretation (Portal Integer Encoding)

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing/not reported | State/institution did not report; value unknown |
| `-2` | Not applicable | Item doesn't apply to this institution |
| `-3` | Suppressed | Data suppressed for privacy protection |
| `NULL` | Null value | Genuinely not present in source data |
| `0` | Zero | Reported as zero (institution has no activity) |

### Handling Missing Data

```python
import polars as pl

# Identify coded missing values
missing_codes = [-1, -2, -3]

# Filter to valid data only
df_valid = df.filter(~pl.col("variable").is_in(missing_codes))

# Or convert coded values to null for calculations
df_clean = df.with_columns(
    pl.when(pl.col("variable").is_in(missing_codes))
    .then(None)
    .otherwise(pl.col("variable"))
    .alias("variable")
)
```

## Data Type Notes

- **Integers**: Count variables (participants, coaches)
- **Decimals**: Financial variables (may have cents)
- **Strings**: Names, identifiers
- **Years**: Fiscal year ending (e.g., 2022 = FY2021-22)

## Joining with Other Data

### IPEDS Join Key

Use `unitid` to join with IPEDS data for:
- Enrollment figures
- Institutional characteristics
- Carnegie classification
- Geographic details

```python
# Example join
eada_df.merge(ipeds_df, on=['unitid', 'year'])
```

### Year Alignment

EADA reporting year may not align perfectly with IPEDS year. Check documentation for specific alignment requirements.
