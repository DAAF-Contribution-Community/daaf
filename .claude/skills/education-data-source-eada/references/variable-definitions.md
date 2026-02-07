# EADA Variable Definitions

Detailed definitions for key EADA variables available through the Education Data Portal.

## Institution Identification

| Variable | Type | Description |
|----------|------|-------------|
| `unitid` | Integer | IPEDS institution identifier (6 digits) |
| `year` | Integer | Reporting year (fiscal year ending) |
| `institution_name` | String | Name of institution |
| `fips` | Integer | State FIPS code |
| `sector` | Integer | Institutional sector (see codes below) |

### Sector Codes

| Code | Description |
|------|-------------|
| 1 | Public, 4-year or above |
| 2 | Private nonprofit, 4-year or above |
| 3 | Private for-profit, 4-year or above |

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

## Missing Value Interpretation

| Value | Meaning |
|-------|---------|
| NULL/NA | Data not reported or not applicable |
| 0 | Reported as zero (institution has no activity) |
| -1, -2 | Suppressed or not calculated (check source) |

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
