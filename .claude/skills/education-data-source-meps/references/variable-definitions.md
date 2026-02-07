# MEPS Variable Definitions

Comprehensive definitions of all variables in the MEPS dataset, including identifiers, estimates, and metadata.

## Core MEPS Variables

### School Identifier

| Variable | Type | Description |
|----------|------|-------------|
| `ncessch` | String (12 char) | NCES school identification number. Unique identifier for each school. Format: {2-digit state FIPS}{5-digit district}{5-digit school} |

**Example**: `060000100001`
- `06` = California (state FIPS)
- `00001` = District code
- `00001` = School code

### Geographic Identifiers

| Variable | Type | Description |
|----------|------|-------------|
| `fips` | Integer | Federal Information Processing Standard state code (1-56) |
| `leaid` | String (7 char) | Local Education Agency (district) ID |
| `year` | Integer | School year (fall semester). Example: 2018 = 2018-19 school year |

### MEPS Estimates

| Variable | Type | Range | Description |
|----------|------|-------|-------------|
| `meps` | Float | 0.0-1.0 | Estimated share of students from households at or below 100% FPL |
| `meps_mod` | Float | 0.0-1.0 | Modified MEPS estimate (adjusted for high-poverty districts) |
| `meps_se` | Float | 0.0+ | Standard error of the MEPS estimate |

## Understanding MEPS Values

### The `meps` Variable

The primary poverty estimate. Interpretation:
- `meps = 0.25` means 25% of students estimated to be in poverty (≤100% FPL)
- Values range from 0 (no students in poverty) to 1 (all students in poverty)
- National average is approximately 0.15-0.20

### The `meps_mod` Variable

Modified estimate for schools in high-poverty districts:
- Adjusts for systematic underestimation in the original model
- Generally higher than `meps` for high-poverty schools
- Use when focusing on high-poverty populations

### The `meps_se` Variable

Standard error quantifying estimation uncertainty:
- Smaller values = more precise estimates
- Larger values = less certainty about the point estimate
- Use for confidence intervals and statistical comparisons

**Calculating confidence intervals:**
```
95% CI = meps ± (1.96 × meps_se)
```

## Poverty Threshold: 100% FPL

### Federal Poverty Level (FPL)

MEPS uses 100% of the Federal Poverty Level as its threshold:

| Family Size | 100% FPL (2024) | 130% FPL | 185% FPL |
|-------------|-----------------|----------|----------|
| 1 | $15,060 | $19,578 | $27,861 |
| 2 | $20,440 | $26,572 | $37,814 |
| 3 | $25,820 | $33,566 | $47,767 |
| 4 | $31,200 | $40,560 | $57,720 |
| 5 | $36,580 | $47,554 | $67,673 |
| 6 | $41,960 | $54,548 | $77,626 |

**Note**: FPL is updated annually by the Department of Health and Human Services.

### Comparison to Other Thresholds

| Measure | Threshold | Meaning |
|---------|-----------|---------|
| MEPS | 100% FPL | Official poverty line |
| FRPL Free | 130% FPL | Free lunch eligibility |
| FRPL Reduced | 185% FPL | Reduced-price lunch eligibility |
| Near poverty | 200% FPL | Common research threshold |

**Key implication**: MEPS captures **deeper poverty** than FRPL. Schools may have low MEPS but higher FRPL if many families are 100-185% FPL.

## Supplementary Variables

Depending on the data version, MEPS may include:

### School Characteristics (from CCD)

| Variable | Type | Description |
|----------|------|-------------|
| `enrollment` | Integer | Total enrollment count |
| `school_name` | String | School name |
| `charter` | Integer | 1 = Charter school, 0 = Traditional public |
| `magnet` | Integer | 1 = Magnet school, 0 = Not magnet |
| `urban_centric_locale` | Integer | Locale code (see below) |
| `school_level` | Integer | 1=Primary, 2=Middle, 3=High, 4=Other |

### Urban-Centric Locale Codes

| Code | Description |
|------|-------------|
| 11 | City, Large |
| 12 | City, Midsize |
| 13 | City, Small |
| 21 | Suburb, Large |
| 22 | Suburb, Midsize |
| 23 | Suburb, Small |
| 31 | Town, Fringe |
| 32 | Town, Distant |
| 33 | Town, Remote |
| 41 | Rural, Fringe |
| 42 | Rural, Distant |
| 43 | Rural, Remote |

## Missing Data Codes

MEPS uses standard missing data codes:

| Code | Meaning |
|------|---------|
| `-1` | Missing/not reported |
| `-2` | Not applicable |
| `-3` | Suppressed for privacy |
| `null` | Data not available |

**Handling missing data:**
```python
# Filter out missing values
valid_data = df[df['meps'] >= 0]

# Or explicitly handle each code
df['meps_clean'] = df['meps'].apply(
    lambda x: x if x >= 0 else None
)
```

## Derived Variables

### Creating Categorical Poverty Measures

MEPS is continuous; create categories as needed:

```python
# Quartiles
df['poverty_quartile'] = pd.qcut(df['meps'], 4, labels=['Low', 'Med-Low', 'Med-High', 'High'])

# Policy-relevant thresholds
df['high_poverty'] = df['meps'] >= 0.30  # 30%+ in poverty
df['low_poverty'] = df['meps'] < 0.10    # <10% in poverty

# Title I style categories
def poverty_category(meps):
    if meps >= 0.40:
        return 'Very High'
    elif meps >= 0.25:
        return 'High'
    elif meps >= 0.10:
        return 'Moderate'
    else:
        return 'Low'

df['poverty_level'] = df['meps'].apply(poverty_category)
```

### School-Level Poverty Count

Estimate the number of students in poverty:

```python
df['poverty_count'] = (df['meps'] * df['enrollment']).round()
```

### District Aggregation

Aggregate school MEPS to district level:

```python
# Enrollment-weighted district average
district_meps = df.groupby('leaid').apply(
    lambda x: (x['meps'] * x['enrollment']).sum() / x['enrollment'].sum()
)
```

## Variable Relationships

### MEPS vs FRPL Conceptual Mapping

| FRPL Concept | MEPS Equivalent | Notes |
|--------------|-----------------|-------|
| % FRPL eligible | `meps` | Different threshold (185% vs 100% FPL) |
| Free lunch % | No direct equivalent | MEPS doesn't distinguish free vs reduced |
| Reduced lunch % | No direct equivalent | Not separately estimated |
| FRPL count | `meps × enrollment` | Approximate only |

### MEPS and Other Poverty Measures

| Other Measure | Relationship to MEPS | Correlation |
|---------------|---------------------|-------------|
| SAIPE (district) | MEPS calibrated to match | ~0.90 |
| Census tract poverty | Similar but geographic | ~0.70 |
| Title I status | Based on different criteria | ~0.65 |
| FRPL (non-CEP schools) | Related but different threshold | ~0.75 |
| FRPL (CEP schools) | Not comparable | Low/meaningless |

## Data Type Specifications

### For Database/DataFrame Setup

```python
# Python/Pandas dtypes
meps_dtypes = {
    'ncessch': 'string',
    'year': 'int64',
    'fips': 'int64',
    'leaid': 'string',
    'meps': 'float64',
    'meps_mod': 'float64',
    'meps_se': 'float64',
    'enrollment': 'int64',
}
```

```sql
-- SQL table definition
CREATE TABLE meps (
    ncessch VARCHAR(12) NOT NULL,
    year INTEGER NOT NULL,
    fips INTEGER,
    leaid VARCHAR(7),
    meps DECIMAL(4,3),
    meps_mod DECIMAL(4,3),
    meps_se DECIMAL(5,4),
    enrollment INTEGER,
    PRIMARY KEY (ncessch, year)
);
```

## Quick Reference Card

| Variable | What it tells you |
|----------|-------------------|
| `meps` | Share of students in poverty (100% FPL) |
| `meps_mod` | Adjusted estimate for high-poverty districts |
| `meps_se` | How confident you can be in the estimate |
| `ncessch` | Unique school identifier for joins |
| `leaid` | District ID for aggregation |
| `year` | Which school year |
| `fips` | Which state |

**Most common usage:**
```python
# "What's the poverty rate at this school?"
poverty_rate = df.loc[df['ncessch'] == '060000100001', 'meps'].values[0]
# Returns: 0.25 (meaning 25% estimated in poverty)
```
