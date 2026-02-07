# Reference Tables

Quick lookup tables for common values used in education data analysis.

---

## State FIPS Codes

| State | FIPS | State | FIPS | State | FIPS |
|-------|------|-------|------|-------|------|
| Alabama | 01 | Louisiana | 22 | Ohio | 39 |
| Alaska | 02 | Maine | 23 | Oklahoma | 40 |
| Arizona | 04 | Maryland | 24 | Oregon | 41 |
| Arkansas | 05 | Massachusetts | 25 | Pennsylvania | 42 |
| California | 06 | Michigan | 26 | Rhode Island | 44 |
| Colorado | 08 | Minnesota | 27 | South Carolina | 45 |
| Connecticut | 09 | Mississippi | 28 | South Dakota | 46 |
| Delaware | 10 | Missouri | 29 | Tennessee | 47 |
| District of Columbia | 11 | Montana | 30 | Texas | 48 |
| Florida | 12 | Nebraska | 31 | Utah | 49 |
| Georgia | 13 | Nevada | 32 | Vermont | 50 |
| Hawaii | 15 | New Hampshire | 33 | Virginia | 51 |
| Idaho | 16 | New Jersey | 34 | Washington | 53 |
| Illinois | 17 | New Mexico | 35 | West Virginia | 54 |
| Indiana | 18 | New York | 36 | Wisconsin | 55 |
| Iowa | 19 | North Carolina | 37 | Wyoming | 56 |
| Kansas | 20 | North Dakota | 38 | |
| Kentucky | 21 | | | |

### Territories

| Territory | FIPS |
|-----------|------|
| American Samoa | 60 |
| Guam | 66 |
| Northern Mariana Islands | 69 |
| Puerto Rico | 72 |
| U.S. Virgin Islands | 78 |

---

## Coded Missing Values

Standard codes used across Education Data Portal sources:

| Code | Meaning | Standard Action |
|------|---------|-----------------|
| `-1` | Missing/not reported | Filter before calculations |
| `-2` | Not applicable | Exclude from analysis |
| `-3` | Suppressed for privacy | Cannot recover; document suppression rate |
| `null` | Genuinely missing | Handle per analysis needs |

### By Source

| Source | Uses -1 | Uses -2 | Uses -3 | Notes |
|--------|---------|---------|---------|-------|
| CCD | Yes | Yes | Yes | Primary K-12 source |
| IPEDS | Yes | Yes | Yes | College data |
| CRDC | Yes | Yes | Yes | Civil rights data |
| EDFacts | Yes | Yes | Yes | Assessment data |
| Scorecard | Yes | Yes | No | College outcomes |

---

## Analysis Type Validity Matrix

This matrix defines which types of cross-entity comparisons are valid for each data source.

| Source | Within-State Trends | Cross-State Counts | Cross-State Rates | Cross-State Assessments |
|--------|---------------------|--------------------|--------------------|-------------------------|
| CCD | ✅ | ✅ | ✅ | N/A |
| CRDC | ✅ | ✅ | ⚠️ Conditional | N/A |
| EDFacts | ✅ | ❌ | ⚠️ Grad rates only | ❌ **NEVER** |
| IPEDS | ✅ | ✅ | ✅ | N/A |
| Scorecard | ✅ | ✅ | ✅ | N/A |
| SAIPE | ✅ | ✅ | ✅ | N/A |
| MEPS | ✅ | ✅ | ✅ | N/A |

**Legend:**
- ✅ **Valid** - Comparison is methodologically sound
- ⚠️ **Conditional** - Valid only under specific conditions (see source skill for details)
- ❌ **Invalid** - Never valid; comparisons are misleading
- **NEVER** - Explicitly blocked; agent must STOP if attempted

### Key Restrictions

**CRDC Cross-State Rates:** 
- Conditional on consistent reporting requirements
- Load `education-data-source-crdc` skill for state-specific variations

**EDFacts Assessments:**
- Within-state trends: ✅ Valid (same test over time)
- Cross-state comparisons: ❌ **NEVER valid** (different state tests, cut scores, standards)
- Agent MUST BLOCK any cross-state assessment comparison

**EDFacts Graduation Rates:**
- ACGR (4-year adjusted cohort) is comparable across states
- Other graduation rate measures vary by state

### When to Reference This Matrix

- During Stage 3 (Source Deep-Dive): Document validity for planned analysis
- During Stage 6 (Context Application): Check validity before allowing analysis to proceed
- When user requests cross-state comparisons: Verify validity before executing

---

## School Level Codes (CCD)

| Code | Level | Description |
|------|-------|-------------|
| 1 | Primary | Elementary schools (typically grades K-5/6) |
| 2 | Middle | Middle schools (typically grades 6-8) |
| 3 | High | High schools (typically grades 9-12) |
| 4 | Other | Other configurations |

---

## School Type Codes (CCD)

| Code | Type | Description |
|------|------|-------------|
| 1 | Regular | Regular public school |
| 2 | Special Education | Focus on students with disabilities |
| 3 | Vocational | Career/technical education focus |
| 4 | Alternative | Alternative education programs |

---

## Charter Status (CCD)

| Code | Status |
|------|--------|
| 1 | Charter school |
| 2 | Not a charter school |

---

## Locale Codes (CCD)

| Code | Category | Description |
|------|----------|-------------|
| 11 | City-Large | Population ≥250,000 |
| 12 | City-Midsize | Population 100,000-249,999 |
| 13 | City-Small | Population <100,000 |
| 21 | Suburb-Large | In urbanized area, large city |
| 22 | Suburb-Midsize | In urbanized area, midsize city |
| 23 | Suburb-Small | In urbanized area, small city |
| 31 | Town-Fringe | In urban cluster, ≤10 miles from urbanized area |
| 32 | Town-Distant | In urban cluster, 10-35 miles from urbanized area |
| 33 | Town-Remote | In urban cluster, >35 miles from urbanized area |
| 41 | Rural-Fringe | Rural, ≤5 miles from urbanized area |
| 42 | Rural-Distant | Rural, 5-25 miles from urbanized area |
| 43 | Rural-Remote | Rural, >25 miles from urbanized area |

### Simplified Categories

| Category | Codes |
|----------|-------|
| Urban | 11, 12, 13 |
| Suburban | 21, 22, 23 |
| Town | 31, 32, 33 |
| Rural | 41, 42, 43 |

---

## Portal Integer Encodings

The Education Data Portal uses integer codes for categorical variables. These codes are consistent across most sources but require careful handling.

### Race Codes (Universal)

These codes are consistent across CCD, CRDC, IPEDS, and EDFacts:

| Code | Category |
|------|----------|
| 1 | White |
| 2 | Black |
| 3 | Hispanic |
| 4 | Asian |
| 5 | American Indian/Alaska Native |
| 6 | Native Hawaiian/Pacific Islander |
| 7 | Two or More Races |
| 8 | Nonresident alien (postsecondary only) |
| 9 | Unknown |
| 99 | Total |

**Usage:** Filter to `race=99` for institution-level totals when data is disaggregated by race.

### Sex Codes (Universal)

| Code | Category |
|------|----------|
| 1 | Male |
| 2 | Female |
| 3 | Another gender / Nonbinary |
| 9 | Unknown |
| 99 | Total |

**Usage:** Filter to `sex=99` for institution-level totals when data is disaggregated by sex.

### Grade Codes (CCD Enrollment)

| Code | Grade | Notes |
|------|-------|-------|
| **-1** | **Pre-K** | **WARNING: NOT a missing value!** |
| 0 | Kindergarten | |
| 1-12 | Grades 1-12 | |
| 15 | Ungraded | |
| 99 | Total | Use for totals across all grades |
| 999 | Not specified | |

**CRITICAL WARNING:** In CCD enrollment data, `grade=-1` means **Pre-Kindergarten**, NOT missing data. Do NOT filter out grade=-1 when you need Pre-K enrollment. This is a common semantic trap.

```python
# WRONG - Loses Pre-K data!
df_clean = df.filter(pl.col("grade") >= 0)

# CORRECT - Explicitly handle Pre-K
df_prek = df.filter(pl.col("grade") == -1)  # Pre-K only
df_k12 = df.filter(pl.col("grade").is_between(0, 12))  # K-12
df_totals = df.filter(pl.col("grade") == 99)  # Totals
```

### Missing Data Patterns by Source

Different sources use different patterns for missing/suppressed data:

| Source | Uses `-1/-2/-3` Coded Values | Uses Native `null` | Notes |
|--------|------------------------------|-------------------|-------|
| CCD | Yes | Rare | Standard coded values |
| CRDC | Yes | Rare | Standard coded values |
| EDFacts | Yes | Rare | Standard coded values |
| EADA | Yes | Rare | Standard coded values |
| NHGIS | Yes | Rare | Standard coded values |
| IPEDS | Yes | Yes | Both patterns present |
| FSA | Yes | Yes | Both patterns present |
| Scorecard | No | Yes | Native nulls only |
| MEPS | No | Yes | Native nulls only |
| NACUBO | No | Yes | Native nulls only |

**Implication:** For sources with native nulls only, the standard `-1/-2/-3` filter will not catch missing data. Check for both:

```python
# For sources like Scorecard, MEPS, NACUBO
df_clean = df.filter(
    pl.col("value").is_not_null() &
    ~pl.col("value").is_in([-1, -2, -3])  # May not have these, but safe to check
)

# For sources like CCD, CRDC, EDFacts
df_clean = df.filter(
    ~pl.col("value").is_in([-1, -2, -3])
)
```

---

## Race/Ethnicity Categories (Variable Naming)

### CCD/CRDC Variable Suffixes

| Category | Variable Suffix |
|----------|-----------------|
| American Indian/Alaska Native | `_aian` |
| Asian | `_asian` |
| Black | `_black` |
| Hispanic | `_hisp` |
| Native Hawaiian/Pacific Islander | `_nhpi` |
| White | `_white` |
| Two or More Races | `_tr` |

### IPEDS Variable Prefixes

| Prefix | Category |
|--------|----------|
| APTS | American Indian/Alaska Native |
| ASPT | Asian |
| BKPT | Black or African American |
| HISN | Hispanic/Latino |
| NHPT | Native Hawaiian/Pacific Islander |
| WHPT | White |
| 2MPT | Two or more races |
| UNKN | Race/ethnicity unknown |
| NRA | Nonresident alien |

---

## Grade Levels (String Codes)

Some endpoints use string codes instead of integers:

| Code | Grade |
|------|-------|
| PK | Pre-Kindergarten |
| KG | Kindergarten |
| 01-12 | Grades 1-12 |
| UG | Ungraded |

---

## Gender Codes (String)

Some endpoints use string codes:

| Code | Gender |
|------|--------|
| M | Male |
| F | Female |

---

## Title I Status

| Code | Status |
|------|--------|
| 1 | Title I school |
| 2 | Not a Title I school |

---

## IPEDS Sector Codes

| Code | Sector |
|------|--------|
| 1 | Public, 4-year or above |
| 2 | Private not-for-profit, 4-year or above |
| 3 | Private for-profit, 4-year or above |
| 4 | Public, 2-year |
| 5 | Private not-for-profit, 2-year |
| 6 | Private for-profit, 2-year |
| 7 | Public, less-than-2-year |
| 8 | Private not-for-profit, less-than-2-year |
| 9 | Private for-profit, less-than-2-year |

---

## Carnegie Classification (Basic)

| Code | Classification |
|------|----------------|
| 15 | Doctoral Universities: Very High Research Activity |
| 16 | Doctoral Universities: High Research Activity |
| 17 | Doctoral Universities: Moderate Research Activity |
| 18 | Master's Colleges & Universities: Larger Programs |
| 19 | Master's Colleges & Universities: Medium Programs |
| 20 | Master's Colleges & Universities: Small Programs |
| 21 | Baccalaureate Colleges: Arts & Sciences Focus |
| 22 | Baccalaureate Colleges: Diverse Fields |
| 23 | Baccalaureate/Associate's Colleges |

---

## Year Formats

| Source | Format | Example | Notes |
|--------|--------|---------|-------|
| CCD | Fall year | 2022 | Represents 2022-23 school year |
| IPEDS | Fall year | 2022 | Represents 2022-23 academic year |
| CRDC | Survey year | 2020 | Collected every 2 years |
| Scorecard | Cohort year | 2018 | Year students entered |

---

## Data Availability Quick Reference

### CCD (K-12 Schools & Districts)

| Data Type | Years Available | Update Frequency |
|-----------|-----------------|------------------|
| Directory | 1986-present | Annual |
| Enrollment | 1986-present | Annual |
| Finance (districts) | 1990-present | Annual |

### IPEDS (Colleges & Universities)

| Data Type | Years Available | Update Frequency |
|-----------|-----------------|------------------|
| Directory | 1980-present | Annual |
| Enrollment | 1980-present | Annual |
| Graduation Rates | 1996-present | Annual |
| Finance | 1984-present | Annual |

### CRDC (Civil Rights)

| Data Type | Years Available | Update Frequency |
|-----------|-----------------|------------------|
| All CRDC | 2011-present | Biennial |

### EDFacts (State Accountability)

| Data Type | Years Available | Update Frequency |
|-----------|-----------------|------------------|
| Assessment | 2010-present | Annual |
| Graduation | 2011-present | Annual |

---

## Identifier Cross-Reference

| Source | School ID | District ID | College ID |
|--------|-----------|-------------|------------|
| CCD | `ncessch` (12 digits) | `leaid` (7 digits) | — |
| CRDC | `ncessch` | `leaid` | — |
| IPEDS | — | — | `unitid` (6 digits) |
| Scorecard | — | — | `unitid` |

### ID Format Examples

| ID Type | Example | Structure |
|---------|---------|-----------|
| NCES School ID | 010000100001 | State(2) + District(5) + School(5) |
| NCES District ID | 0100001 | State(2) + District(5) |
| IPEDS UNITID | 100654 | Sequential assignment |

---

## Suppression Thresholds

| Source | Typical Threshold | Notes |
|--------|-------------------|-------|
| CCD | 3 students | Below 3 is suppressed |
| CRDC | 3 students | Below 3 is suppressed |
| EDFacts | Varies by state | State-determined |
| IPEDS | Institution-level | Rarely suppressed |

---

## Common Filters

### Schools Analysis

```python
# Standard school-level filters
filters = {
    "school_type": 1,      # Regular schools only
    "charter": [1, 2],     # Include both charter and non-charter
    "school_status": 1,    # Open schools only
}
```

### Districts Analysis

```python
# Standard district-level filters
filters = {
    "agency_type": [1, 2], # Regular local and local supervisory union
}
```

### Colleges Analysis

```python
# Standard college-level filters
filters = {
    "sector": [1, 2],      # Public and private non-profit 4-year
    "main": 1,             # Main campus only
}
```

---

## Quick Command Reference

| Task | Command |
|------|---------|
| Lint Python | `ruff check . --fix` |
| Format Python | `ruff format .` |
| Run marimo | `marimo run notebook.py` |
| Edit marimo | `marimo edit notebook.py` |
| Export marimo to HTML | `marimo export html notebook.py -o output.html` |

> **Docker:** When running in a container, add `--host 0.0.0.0 --port 2718 --headless`
