# Geographic Flows

Where graduates work after completion: employment by Census Division and in-state retention.

## Contents

- [Overview](#overview)
- [Census Divisions](#census-divisions)
- [Geographic Flow Variables](#geographic-flow-variables)
- [In-State Employment](#in-state-employment)
- [Analysis Patterns](#analysis-patterns)
- [Limitations](#limitations)

## Overview

The Employment Flows tabulations include geographic employment data showing where graduates work:

- **Census Division**: 9 regions covering the U.S.
- **In-state**: Whether graduate works in the same state as their institution

Geographic flows help answer:
- Are graduates staying in-state or leaving?
- Which regions attract graduates from specific programs?
- How do migration patterns vary by field of study?

## Census Divisions

PSEO reports employment by the 9 Census Divisions:

| Code | Division | States |
|------|----------|--------|
| 1 | New England | CT, ME, MA, NH, RI, VT |
| 2 | Middle Atlantic | NJ, NY, PA |
| 3 | East North Central | IL, IN, MI, OH, WI |
| 4 | West North Central | IA, KS, MN, MO, NE, ND, SD |
| 5 | South Atlantic | DE, DC, FL, GA, MD, NC, SC, VA, WV |
| 6 | East South Central | AL, KY, MS, TN |
| 7 | West South Central | AR, LA, OK, TX |
| 8 | Mountain | AZ, CO, ID, MT, NV, NM, UT, WY |
| 9 | Pacific | AK, CA, HI, OR, WA |

### Division Map Reference

```
┌─────────────────────────────────────────────────────────────┐
│     9              4                1                       │
│  Pacific    West North       New England                    │
│             Central                                         │
│     8              3           2                            │
│  Mountain   East North    Middle                            │
│             Central       Atlantic                          │
│     7              6           5                            │
│  West South  East South   South                             │
│  Central     Central      Atlantic                          │
└─────────────────────────────────────────────────────────────┘
```

## Geographic Flow Variables

### Employment by Division

Available for Years 1, 5, and 10 post-graduation:

| Variable Pattern | Description |
|------------------|-------------|
| `Y1_GRADS_EMP` | Employed graduates (when filtered by division) |
| `Y5_GRADS_EMP` | Employed graduates, 5 years out |
| `Y10_GRADS_EMP` | Employed graduates, 10 years out |

### Total Employment Variables

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP` | Total employed (sum across divisions) |
| `Y1_GRADS_NME` | Non-employed or marginally employed |

### Querying by Division

Use the `division` parameter in the Flows endpoint:

```
# Employment in Pacific Division (9), 1 year post-graduation
GET api.census.gov/data/timeseries/pseo/flows
  ?get=Y1_GRADS_EMP
  &for=division:9
  &INSTITUTION=00365800
  &DEGREE_LEVEL=05
```

To get all divisions:
```
&for=division:*
```

## In-State Employment

### In-State Variables

| Variable | Description |
|----------|-------------|
| `Y1_GRADS_EMP_INSTATE` | Employed in same state as institution, Year 1 |
| `Y5_GRADS_EMP_INSTATE` | Employed in same state as institution, Year 5 |
| `Y10_GRADS_EMP_INSTATE` | Employed in same state as institution, Year 10 |

### Calculating Retention Rate

```
In-State Retention Rate = Y1_GRADS_EMP_INSTATE / Y1_GRADS_EMP × 100
```

**Example**:
- Y1_GRADS_EMP = 1,000
- Y1_GRADS_EMP_INSTATE = 650
- In-state retention = 65%

### Interpreting In-State Data

| Retention Rate | Interpretation |
|----------------|----------------|
| > 80% | High retention (likely strong local job market) |
| 60-80% | Moderate retention |
| < 60% | Low retention (graduates leaving for opportunities elsewhere) |

## Analysis Patterns

### Brain Drain Analysis

Compare in-state employment rates across institutions or programs:

```python
# Pseudo-code for brain drain analysis
retention_by_program = {}
for cip_code in programs:
    total_emp = get_y1_grads_emp(institution, cip_code)
    instate_emp = get_y1_grads_emp_instate(institution, cip_code)
    retention_by_program[cip_code] = instate_emp / total_emp
```

### Migration Flow Analysis

Show where graduates from an institution/state work:

| From Institution State | To Division | Y1_GRADS_EMP |
|------------------------|-------------|--------------|
| Texas (48) | West South Central (7) | 8,500 |
| Texas (48) | Pacific (9) | 1,200 |
| Texas (48) | Mountain (8) | 800 |
| Texas (48) | South Atlantic (5) | 600 |

### Comparative Regional Analysis

Compare the same program across institutions in different regions:

```
Computer Science (CIP=11) Bachelor's, Y1 Employment by Division:
- UT Austin: 70% in West South Central
- UC Berkeley: 85% in Pacific
- Georgia Tech: 45% in South Atlantic
```

## Limitations

### Geographic Granularity

| Limitation | Impact |
|------------|--------|
| Division level only | Cannot distinguish California from Oregon |
| No state-level flows | Cannot track state-to-state migration precisely |
| No metro-area data | Cannot identify specific job markets |

### Interpretation Challenges

| Issue | Consideration |
|-------|---------------|
| Remote work | Employment location may not equal residence |
| Multi-state employers | Assignment to division may be headquarters vs. work site |
| Federal employment | OPM data may have different geographic coding |

### Missing Data

Flows data can be missing when:
- Fewer than 30 graduates in a cell (suppressed)
- Institution recently joined PSEO
- Program has insufficient completers

### Example: Complete Geographic Profile

For Texas Engineering Bachelor's graduates (hypothetical data):

```
Institution: Texas Higher Education Coordinating Board (State aggregate)
CIP: 14 (Engineering)
Degree Level: 05 (Bachelor's)
Cohort: 2016

Geographic Distribution (Y1):
┌────────────────────────┬────────────┬─────────┐
│ Division               │ Y1_EMP     │ Share   │
├────────────────────────┼────────────┼─────────┤
│ West South Central (7) │ 12,500     │ 62%     │
│ Pacific (9)            │ 2,800      │ 14%     │
│ Mountain (8)           │ 1,600      │ 8%      │
│ East North Central (3) │ 1,000      │ 5%      │
│ South Atlantic (5)     │ 900        │ 4%      │
│ Other divisions        │ 1,200      │ 6%      │
├────────────────────────┼────────────┼─────────┤
│ Total Employed         │ 20,000     │ 100%    │
│ In-State (Texas)       │ 11,500     │ 57.5%   │
│ Non-Employed/Marginal  │ 3,000      │ --      │
└────────────────────────┴────────────┴─────────┘
```

**Insights**:
- 62% stay in West South Central (includes Texas)
- 57.5% specifically stay in Texas
- Pacific region (14%) is second-largest destination (likely California tech)
- Mountain region (8%) attracts some (Colorado, Arizona tech hubs)
