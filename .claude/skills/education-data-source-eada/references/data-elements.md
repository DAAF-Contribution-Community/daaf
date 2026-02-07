# EADA Data Elements

Comprehensive guide to data collected through the Equity in Athletics Disclosure Act.

## Data Categories Overview

| Category | Description | Key Variables |
|----------|-------------|---------------|
| Participation | Athletes by gender and sport | `partic_*` |
| Coaching | Staff counts and demographics | `hdcoach_*`, `asstcoach_*` |
| Salaries | Coach compensation | `salary_*` |
| Expenses | Operating, recruiting, total | `exp_*` |
| Revenues | Income by team | `rev_*` |
| Athletic Aid | Scholarships/grants | `aid_*` |
| Recruiting | Recruiting expenses | `recruiting_*` |

## Participation Data

### Institution-Level Counts

| Variable | Description |
|----------|-------------|
| `partic_men` | Total male participants (unduplicated) |
| `partic_women` | Total female participants (unduplicated) |
| `partic_coed_men` | Male participants on coed teams |
| `partic_coed_women` | Female participants on coed teams |

### Counting Rules

**Unduplicated Count**: A student who plays multiple sports is counted once for the institution total, but counted for each sport in sport-level data.

**Timing**: Count taken as of the first day of the first scheduled contest of the sport's season.

**Who Counts**:
- Varsity athletes only
- Walk-ons included
- Redshirts if on roster
- Practice squad if varsity designated

### Example Calculation

```python
# Total athletes
total_athletes = partic_men + partic_women

# Female participation rate
female_pct = partic_women / total_athletes

# Compare to enrollment
enrollment_gap = female_enrollment_pct - female_pct
```

## Coaching Data

### Head Coaches

| Variable | Description |
|----------|-------------|
| `hdcoach_salary_men` | Head coach salaries for men's teams |
| `hdcoach_salary_women` | Head coach salaries for women's teams |
| `hdcoach_salary_coed` | Head coach salaries for coed teams |
| `hdcoach_men_male_ft` | Full-time male head coaches of men's teams |
| `hdcoach_men_male_pt` | Part-time male head coaches of men's teams |
| `hdcoach_men_female_ft` | Full-time female head coaches of men's teams |
| `hdcoach_men_female_pt` | Part-time female head coaches of men's teams |
| `hdcoach_women_male_ft` | Full-time male head coaches of women's teams |
| `hdcoach_women_male_pt` | Part-time male head coaches of women's teams |
| `hdcoach_women_female_ft` | Full-time female head coaches of women's teams |
| `hdcoach_women_female_pt` | Part-time female head coaches of women's teams |

### Assistant Coaches

Similar structure to head coaches with `asstcoach_*` prefix:

| Variable Pattern | Description |
|------------------|-------------|
| `asstcoach_[team]_[gender]_[status]` | Assistant coaches by team gender, coach gender, employment status |

Employment Status:
- `ft` = Full-time
- `pt` = Part-time

### Coaching Demographics Analysis

```python
# Female head coaches of women's teams
female_coaches_womens = (
    hdcoach_women_female_ft + hdcoach_women_female_pt
)

# Total head coaches of women's teams
total_coaches_womens = (
    hdcoach_women_male_ft + hdcoach_women_male_pt +
    hdcoach_women_female_ft + hdcoach_women_female_pt
)

# Percentage female
pct_female = female_coaches_womens / total_coaches_womens
```

## Salary Data

### Salary Reporting Rules

Institutions report:
- **Institutional compensation only**: W-2 wages and bonuses from the institution
- **Excludes**: Media income, camps, endorsements, outside income
- **Calculated as average**: Total salaries / Number of paid positions

| Variable | Description |
|----------|-------------|
| `salary_men_coach` | Average salary for head coaches of men's teams |
| `salary_women_coach` | Average salary for head coaches of women's teams |
| `salary_coed_coach` | Average salary for head coaches of coed teams |
| `asstcoach_salary_men` | Average salary for assistant coaches of men's teams |
| `asstcoach_salary_women` | Average salary for assistant coaches of women's teams |
| `asstcoach_salary_coed` | Average salary for assistant coaches of coed teams |

### Salary Analysis Cautions

- **Football/basketball skew**: High-revenue sport coaches inflate men's averages
- **Part-time inclusion**: May lower averages
- **Non-institutional income**: Not captured (can be substantial)
- **Benefits**: Not typically included

### Meaningful Comparisons

Better approach: Compare coaches of similar sports
```python
# Example: Compare basketball coaches
# Rather than all men's vs all women's coaches
basketball_men_salary vs basketball_women_salary
```

## Expense Data

### Operating Expenses (Game-Day)

| Variable | Description |
|----------|-------------|
| `exp_men` | Total expenses for men's teams |
| `exp_women` | Total expenses for women's teams |
| `exp_coed` | Total expenses for coed teams |

Operating expenses include:
- Lodging, meals, transportation
- Uniforms and equipment
- Officials
- Game-day personnel

### Not Operating Expenses

- Salaries (reported separately)
- Athletic scholarships
- Facilities construction/maintenance
- Debt service

### Recruiting Expenses

| Variable | Description |
|----------|-------------|
| `recruiting_exp_men` | Recruiting expenses for men's teams |
| `recruiting_exp_women` | Recruiting expenses for women's teams |
| `recruiting_exp_coed` | Recruiting expenses for coed teams |

Recruiting includes:
- Transportation for prospects and staff
- Lodging for recruiting trips
- Entertainment of prospects
- Communication costs

### Total Expenses

Some datasets report total athletic expenditures:
- Operating + Salaries + Recruiting + Other
- Useful for overall investment comparison

## Revenue Data

### Revenue Sources

| Variable | Description |
|----------|-------------|
| `rev_men` | Total revenues from men's teams |
| `rev_women` | Total revenues from women's teams |
| `rev_coed` | Total revenues from coed teams |

Revenue includes:
- Ticket sales
- Broadcast rights
- NCAA/conference distributions
- Guarantees
- Program sales
- Concessions (if attributed)

### Revenue Interpretation

**Important**: Most women's sports programs don't generate significant independent revenue. This does NOT mean they're less worthy of investment—most men's non-revenue sports also don't generate income.

```
Common pattern:
- Football: Positive revenue (large programs)
- Men's basketball: Positive or break-even
- All other sports: Typically subsidized
```

## Athletic Aid Data

### Variables

| Variable | Description |
|----------|-------------|
| `aid_men` | Total athletic aid to male students |
| `aid_women` | Total athletic aid to female students |
| `aid_coed` | Athletic aid for coed teams (if applicable) |
| `aid_men_num` | Number of male aid recipients |
| `aid_women_num` | Number of female aid recipients |

### What Counts as Athletic Aid

- Scholarships
- Grants-in-aid
- Tuition waivers for athletics
- Room, board, books if athletically related

### Title IX Standard

Athletic aid should be proportional to participation:

```python
# If participation is 45% women, 55% men
# Aid should be approximately:
aid_women / (aid_men + aid_women) ≈ 0.45
```

Small deviations (1-2%) acceptable; larger gaps raise concerns.

## Derived Metrics

### Participation Equity

```python
# Female participation share
female_share = partic_women / (partic_men + partic_women)

# Compare to enrollment (need IPEDS data)
enrollment_gap = female_enrollment_share - female_share
```

### Financial Investment Per Athlete

```python
# Expenses per athlete
exp_per_male = exp_men / partic_men
exp_per_female = exp_women / partic_women

# Investment ratio
investment_ratio = exp_per_female / exp_per_male
```

### Coaching Investment

```python
# Average salary comparison
salary_ratio = salary_women_coach / salary_men_coach

# Coaches per athlete
coaches_per_male = total_coaches_men / partic_men
coaches_per_female = total_coaches_women / partic_women
```

### Aid Proportionality

```python
# Aid share vs participation share
aid_share_women = aid_women / (aid_men + aid_women)
partic_share_women = partic_women / (partic_men + partic_women)

# Proportionality gap
aid_gap = partic_share_women - aid_share_women
```

## Data Quality Considerations

### Missing Values

- Some institutions don't have certain sports
- Zero values may mean "not applicable" or "zero dollars"
- NULL vs 0 distinction important

### Self-Reporting

- No independent verification
- Interpretation differences across institutions
- Potential for errors or strategic reporting

### Year-to-Year Changes

May reflect:
- Actual changes in program
- Reporting methodology changes
- Roster fluctuations
- One-time events (coach buyouts, etc.)
