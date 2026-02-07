# IPEDS Graduation Rates: Critical Limitations

**This is the most misunderstood aspect of IPEDS data.** Understanding these limitations is essential for any graduation rate analysis.

## Contents

- [The Core Problem](#the-core-problem)
- [Who Is Tracked](#who-is-tracked)
- [Who Is NOT Tracked](#who-is-not-tracked)
- [Impact by Institution Type](#impact-by-institution-type)
- [Time Windows](#time-windows)
- [Transfer-Out Rates](#transfer-out-rates)
- [Pell and Loan Cohorts](#pell-and-loan-cohorts)
- [Outcome Measures Alternative](#outcome-measures-alternative)
- [Calculating Rates](#calculating-rates)
- [Valid and Invalid Comparisons](#valid-and-invalid-comparisons)

## The Core Problem

IPEDS graduation rates track a **narrow subset of students** that does not represent the full undergraduate population at most institutions.

**Key Fact**: At many institutions, IPEDS graduation rates represent **less than 25% of their students**.

This is not a data quality issue—it's by design. The Student Right-to-Know Act (1990) established this cohort definition, and while it made sense for traditional 4-year residential colleges, it fails to capture the reality of modern higher education.

## Who Is Tracked

The IPEDS Graduation Rates (GR) cohort includes ONLY students who are:

| Criterion | Definition | Exclusion Impact |
|-----------|------------|------------------|
| **First-time** | Never previously enrolled at ANY postsecondary institution | Excludes transfers |
| **Full-time** | Enrolled full-time in their FIRST term | Excludes part-time starts |
| **Degree/certificate-seeking** | Enrolled in a program leading to an award | Excludes non-degree |
| **Fall entering** | Started in the fall term | Excludes spring/summer starts |
| **At this institution** | Tracked at entry institution | Transfers OUT are non-completers |

**ALL criteria must be met for a student to be in the cohort.**

## Who Is NOT Tracked

### Transfer Students (~40% of undergraduates nationally)

- Students who transfer IN from another institution are excluded
- Students who transfer OUT count as **non-completers**, even if they graduate elsewhere
- Community college transfers to 4-year schools: NOT in 4-year school's cohort
- "Swirling" students who attend multiple institutions: poorly captured

### Part-Time Students (~40% of undergraduates nationally)

- Students who begin part-time are excluded entirely
- Even if they later switch to full-time
- Disproportionately excludes:
  - Working adults
  - Parents
  - Students at community colleges
  - Students at for-profit institutions

### Spring/Summer Starts

- Students entering in spring or summer terms are excluded
- This is especially significant for:
  - Community colleges (many have year-round enrollment)
  - For-profit institutions (often have rolling starts)
  - Some public 4-year institutions with mid-year programs

### Non-Degree Students

- Students not enrolled in a degree/certificate program excluded
- Includes many adult learners taking courses for job skills

## Impact by Institution Type

### Community Colleges

**IPEDS graduation rates are most misleading for community colleges.**

| Factor | Impact |
|--------|--------|
| Transfer mission | Students who transfer to 4-year school before graduating = non-completers |
| Part-time majority | ~65% of CC students attend part-time; excluded from cohort |
| Non-fall starts | Many CCs enroll year-round |
| Swirling students | Students attending multiple schools |

**Real-world example**: A community college might have a 15% IPEDS graduation rate, but:
- 30% of students transfer before completing (counted as failures)
- 65% started part-time (not in cohort at all)
- Actual success rate when including transfers could be 50%+

### For-Profit Institutions

| Factor | Impact |
|--------|--------|
| Program-based enrollment | Often rolling starts, not fall-based |
| Short-term programs | Certificate programs may have different dynamics |
| Part-time students | Significant population at some institutions |

### Highly Selective 4-Year Institutions

**IPEDS graduation rates are most appropriate for these institutions** because:
- Most students are first-time, full-time
- Most enter in fall
- Transfer rates are relatively low
- Cohort represents most of the student body

### Open-Access 4-Year Institutions

Less appropriate than selective institutions because:
- More transfer students
- More part-time students
- More non-traditional students

## Time Windows

### 150% Time (Standard Reported Rate)

| Institution Type | Program Length | 150% Window |
|-----------------|----------------|-------------|
| 4-year | 4 years | 6 years |
| 2-year | 2 years | 3 years |
| Less-than-2-year | Varies | 1.5x program length |

**150% time is the most commonly reported and used rate.**

### 100% Time ("On-Time" Graduation)

| Institution Type | 100% Window |
|-----------------|-------------|
| 4-year | 4 years |
| 2-year | 2 years |

Increasingly reported but penalizes students who:
- Take reduced course loads
- Work while enrolled
- Change majors
- Take leave of absence

### 200% Time (GR200 Survey)

| Institution Type | 200% Window |
|-----------------|-------------|
| 4-year | 8 years |
| 2-year | 4 years |

Captures additional completers but:
- Long lag time makes data less current
- Still excludes same populations

**How Many Additional Completers?**

Typically 2-5 percentage points more than 150% rate for 4-year institutions.

## Transfer-Out Rates

IPEDS collects transfer-out rates separately, but with major limitations:

### What Is Reported

- Students who transferred to another institution (if known)
- Counted separately from completers and non-completers

### Critical Limitations

| Limitation | Implication |
|------------|-------------|
| Only "known" transfers | Institutions may not know student transferred |
| No outcome tracking | Transfer doesn't mean student graduated elsewhere |
| Not subtracted from non-completers | Transfer + graduation could exceed 100% |

### How to Use

```python
# Basic transfer-adjusted rate (imperfect but better)
adjusted_success = graduation_rate + transfer_out_rate

# But this is NOT a true completion rate because:
# 1. Not all transfers complete elsewhere
# 2. Not all transfers are captured
# 3. Some students may be double-counted
```

### Transfer-Out Rate Patterns

| Institution Type | Typical Transfer-Out Rate |
|-----------------|---------------------------|
| Community colleges | 20-40% |
| Non-selective 4-year | 10-20% |
| Selective 4-year | 5-10% |
| Highly selective 4-year | 2-5% |

## Pell and Loan Cohorts

Since 2017, IPEDS reports graduation rates disaggregated by:

### Pell Grant Recipients

Students who received a Pell Grant at any point during cohort tracking.

**Why It Matters**:
- Pell = low-income proxy (family income typically <$60K)
- Pell recipient graduation rates often 5-15 percentage points lower
- Shows equity gaps

### Subsidized Stafford Loan Recipients

Students who received subsidized Direct Loans.

**Why It Matters**:
- Indicates financial need (not Pell level, but need-based)
- Broader income range than Pell

### Neither Pell nor Loan

Students who received neither Pell grants nor subsidized loans.

- Generally higher-income students
- Often have highest graduation rates
- Helps identify equity gaps

**Calculating Equity Gaps**:
```python
equity_gap = grad_rate_neither_pell_loan - grad_rate_pell
# Positive value = higher-income students graduate at higher rates
```

## Outcome Measures Alternative

The **Outcome Measures (OM)** survey addresses GR limitations by tracking:

### Four Cohorts

1. **First-time, full-time** (same as GR)
2. **First-time, part-time** (NEW)
3. **Non-first-time, full-time** (transfers - NEW)
4. **Non-first-time, part-time** (transfers, part-time - NEW)

### Eight-Year Outcomes

At 8 years from entry, reports:
- Received award at this institution
- Received award at another institution
- Still enrolled at this institution
- Still enrolled at another institution
- Not enrolled anywhere (known)

### Key Advantages

| GR Limitation | OM Solution |
|---------------|-------------|
| Excludes part-time | Includes PT cohort |
| Excludes transfers | Includes transfer cohort |
| Transfers-out = failure | Tracks awards elsewhere |
| 6-year max (4-year schools) | 8-year window |

### Key Limitation

- First collected in 2015-16 (for 2007-08 cohort)
- Less historical data than GR
- More complex to analyze
- Less widely used in rankings/accountability

## Calculating Rates

### Basic Graduation Rate

```python
grad_rate_150 = (
    completers_within_150_pct_time / 
    adjusted_cohort
) * 100

# Where adjusted_cohort = initial_cohort - exclusions
# Exclusions: died, disabled, military service, foreign service
```

### By Demographic Group

```python
# By race/ethnicity
grad_rate_black = completers_black / cohort_black * 100

# By gender
grad_rate_female = completers_female / cohort_female * 100

# By Pell status
grad_rate_pell = completers_pell / cohort_pell * 100
```

### Transfer-Adjusted (Informal)

```python
# NOT an official rate, but provides context
transfer_adjusted = grad_rate_150 + transfer_out_rate

# Better interpretation: "percentage who either graduated or transferred"
# This is NOT equal to "percentage who succeeded"
```

## Valid and Invalid Comparisons

### Valid Comparisons

| Comparison | Why Valid |
|------------|-----------|
| Same institution over time | Same population definition |
| Similar institutions (same sector, selectivity, Carnegie) | Similar student bodies |
| Within racial/ethnic groups | Controls for composition |
| Pell vs non-Pell within institution | Same institution, different income |

### Invalid or Problematic Comparisons

| Comparison | Why Problematic |
|------------|-----------------|
| Community college vs 4-year | CC grad rate excludes transfer successes |
| Open-access vs selective | Different student populations |
| Public vs for-profit | Different enrollment patterns |
| Cross-sector rankings | Comparing apples to oranges |

### Best Practices

1. **Always note the cohort definition** in any graduation rate analysis
2. **Compare within peer groups** (same Carnegie class, sector, selectivity)
3. **Report transfer-out rates** alongside graduation rates
4. **Use Outcome Measures** when available for complete picture
5. **Avoid using as sole quality metric** - it reflects student population as much as institutional quality

## Cohort Year vs Data Year

**Critical for understanding data timing:**

| Term | Meaning | Example |
|------|---------|---------|
| Cohort year | Year students entered | 2018 |
| Outcome year | Year outcomes measured | 2024 (for 6-yr) |
| Data release year | Year data published | 2025 |

**GR data labeled "2024" refers to the 2018 entering cohort** (6 years earlier for 4-year schools).

## Variable Reference

### Key GR Variables

| Variable | Description |
|----------|-------------|
| `cohort` | Adjusted cohort count |
| `grtype` | Grad rate type (by level) |
| `chrtstat` | Cohort status (completers, transfers, etc.) |
| `grtotlt` | Total graduates |
| `grrace*` | Graduates by race |
| `grgenderc` | Graduates by gender |
| `grrttot` | Total graduation rate |
| `grrt*` | Graduation rates by subgroup |
| `trtotlt` | Total transfers out |
| `grpell*` | Pell recipient outcomes |
| `grssl*` | Subsidized loan recipient outcomes |

### Outcome Measures Variables

| Variable | Description |
|----------|-------------|
| `omachrt` | Award at this institution |
| `omawdoth` | Award at other institution |
| `omstleng` | Still enrolled at this institution |
| `omengoth` | Still enrolled elsewhere |
| `omnoleng` | Not enrolled anywhere |
