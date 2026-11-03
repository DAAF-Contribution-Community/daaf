# Title IX Context for Athletics

Understanding the legal framework behind gender equity in college athletics.

## What is Title IX?

Title IX of the Education Amendments of 1972 prohibits sex discrimination in educational programs receiving federal financial assistance:

> "No person in the United States shall, on the basis of sex, be excluded from participation in, be denied the benefits of, or be subjected to discrimination under any education program or activity receiving Federal financial assistance."

**Key Points**:
- Applies to ALL educational programs, not just athletics
- Athletics is one of the most visible and litigated areas
- Enforced by the Department of Education's Office for Civil Rights (OCR)
- Affects ~2,000+ coeducational colleges and high schools

## Title IX in Athletics: Three Compliance Areas

### 1. Participation Opportunities (Athletic Participation)

Institutions must provide equitable opportunities for participation. OCR uses a **three-prong test** (satisfy ANY one):

| Prong | Description | How to Demonstrate |
|-------|-------------|-------------------|
| **Prong 1: Proportionality** | Athletic participation substantially proportionate to enrollment | Female athletes % ≈ Female full-time undergraduate % |
| **Prong 2: History & Continuing Practice** | History of expanding opportunities for underrepresented sex | Adding women's teams over time |
| **Prong 3: Full Accommodation** | Fully accommodating interests and abilities | Surveys, demonstrated interest met |

**EADA Connection**: EADA reports participation counts, but EADA counting differs from Title IX counting methods.

### 2. Athletic Financial Assistance (Scholarships)

Scholarship dollars must be substantially proportionate to participation ratios:

```
If women = 45% of athletes
Then women should receive ≈ 45% of athletic scholarship dollars
```

**EADA Connection**: EADA reports `ath_stuaid_men` and `ath_stuaid_women` totals.

### 3. Treatment and Benefits (The "Laundry List")

Equal treatment across the nine treatment factors in 34 CFR 106.41(c)(2)–(10) plus recruitment and support services (1979 Policy Interpretation):

| Component | Examples |
|-----------|----------|
| Equipment & supplies | Quality, quantity, maintenance |
| Scheduling | Practice times, game times, season length |
| Travel & per diem | Mode of transportation, lodging quality |
| Coaching | Number, qualifications, compensation |
| Tutoring | Academic support services |
| Locker rooms & facilities | Quality, exclusivity, maintenance |
| Medical & training | Trainers, facilities, insurance |
| Housing & dining | Quality, location |
| Publicity | Media guides, promotion |
| Recruiting | Budget, staff time |
| Support services | Administrative support |

**EADA Connection**: EADA captures only limited financial data (expenses, revenues, salaries). It does NOT capture most "laundry list" items.

## The Proportionality Standard

The most commonly used compliance test is **substantial proportionality** (Prong 1):

### Calculation

```python
female_enrollment_pct = female_fulltime_undergrads / total_fulltime_undergrads
female_participation_pct = female_athletes / total_athletes
participation_gap = female_enrollment_pct - female_participation_pct
```

```r
female_enrollment_pct <- female_fulltime_undergrads / total_fulltime_undergrads
female_participation_pct <- female_athletes / total_athletes
participation_gap <- female_enrollment_pct - female_participation_pct
```

### What is "Substantial"?

No fixed percentage: OCR (1996 Clarification) asks whether the number of additional opportunities needed for proportionality would be enough to sustain a viable team, considering natural enrollment fluctuations.

## Historical Context

| Year | Event |
|------|-------|
| 1972 | Title IX enacted |
| 1975 | Title IX athletics regulations issued (HEW) |
| 1979 | Policy Interpretation issued (three-prong test) |
| 1994 | EADA enacted |
| 1996 | Clarification of the three-part test (Jan 16, 1996) |
| 2003 | Further clarification of compliance standards |
| 2005 | Additional Clarification on Part Three (Mar 17, 2005) |
| 2010 | 2005 Additional Clarification withdrawn (Apr 20, 2010) |

## EADA's Role in Title IX

### Congressional Intent

EADA was passed to:
1. Provide transparency about athletic programs
2. Help prospective students make informed decisions
3. Create public accountability for gender equity
4. Enable researchers and advocates to monitor trends

### What EADA Does NOT Do

- Does NOT determine Title IX compliance
- Does NOT use Title IX counting methods
- Does NOT capture all equity factors
- Does NOT trigger enforcement actions
- Does NOT include "laundry list" treatment data

## Key Differences: EADA vs. Title IX

| Aspect | EADA Reporting | Title IX Compliance |
|--------|----------------|---------------------|
| **Purpose** | Public disclosure | Legal compliance |
| **Counting** | As of each team's first scheduled contest | Generally, athletes on the squad list as of the team's first competitive event (1996 Clarification) |
| **Duplicates** | Per-team (duplicated) plus an unduplicated head count | Multi-sport athletes counted in each sport |
| **Walk-ons** | Included | Included |
| **Verification** | Self-reported | OCR investigation |
| **Scope** | Limited data points | Comprehensive review |
| **Enforcement** | Consumer information | Civil rights law |

## Participation Counting Differences

### EADA Counting Rules

- Count as of the day of each varsity team's first scheduled contest of the reporting year (34 CFR 668.47(c)(2)(i))
- Each student counted once (unduplicated for total)
- Multi-sport athletes: counted for each sport, once for institution total

### Title IX Counting Rules

- Generally, athletes on the squad or eligibility list as of the team's first competitive event (1996 Clarification)
- Multi-sport athletes counted as a participant in each sport (1996 Clarification)
- Different guidance for roster management
- Focus on "opportunities" not just participants

**Result**: The count date is similar; EADA counts may still differ from Title IX participation analysis because the participant definitions and the scope of review differ.

## Using EADA Data for Equity Analysis

### Can Do

- Calculate participation ratios
- Track trends over time
- Compare financial investment
- Analyze coaching demographics
- Identify potential disparities

### Cannot Do

- Determine Title IX compliance
- Assess quality of treatment
- Evaluate interest and abilities
- Review all equity factors
- Make legal compliance judgments

## Additional Resources

### Official Guidance

- OCR Policy Interpretation (1979)
- OCR Policy Clarification (1996)
- Athletic Investigators Manual

### Research Organizations

- Women's Sports Foundation
- National Women's Law Center
- National Coalition for Women and Girls in Education
- The Drake Group

### Data Sources

- EADA (this data)
- NCAA Demographics Database
- Knight Commission reports
