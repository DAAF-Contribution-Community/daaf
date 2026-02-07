---
name: education-data-source-scorecard
description: College Scorecard data source for post-college outcomes. Covers earnings from IRS/Treasury, student debt and repayment from NSLDS, and completion metrics. Use when analyzing post-graduation earnings, loan repayment, debt levels, or when understanding Scorecard's Title IV recipient limitation is critical.
metadata:
  audience: data-analysts
  domain: education-data
---

# College Scorecard Data Source

Federal data on post-college outcomes including earnings, debt, and repayment for students who received Title IV financial aid.

## What is College Scorecard?

- **Publisher**: U.S. Department of Education
- **Primary value**: Post-college labor market outcomes (earnings) and debt/repayment metrics
- **Data sources**: NSLDS (loans/aid), IRS/Treasury (earnings), IPEDS (institutional characteristics)
- **Coverage**: **Title IV federal aid recipients only** - not all students
- **Unique feature**: Links education to IRS tax records for actual earnings data
- **Access**: Free via API, bulk downloads at collegescorecard.ed.gov

## Critical Limitation: Title IV Recipients Only

**The single most important caveat for all Scorecard analysis:**

Scorecard tracks ONLY students who received federal financial aid (Title IV):
- Pell Grants
- Federal student loans (Direct, Perkins, PLUS)
- Federal work-study

| Excluded Group | Impact |
|----------------|--------|
| Full-pay students | Often higher-income; different outcomes |
| Students with only state/institutional aid | Missing from data |
| International students | Not eligible for federal aid |
| Some graduate students | If they received no federal aid |

**Coverage varies dramatically by institution type:**

| Institution Type | Typical Title IV Coverage |
|-----------------|---------------------------|
| For-profit colleges | 80-90%+ |
| Community colleges | 60-80% |
| Public flagships | 50-70% |
| Selective private colleges | 30-50% |

**Data systematically overrepresents lower-income students** who are more likely to need federal aid.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `earnings-data.md` | Post-college earnings methodology, cohorts, time horizons | Analyzing earnings outcomes |
| `debt-repayment.md` | Student debt, repayment rates, default rates | Analyzing debt or loan outcomes |
| `completion-rates.md` | Completion metrics vs IPEDS | Comparing graduation rates |
| `population-coverage.md` | Title IV limitation details, who is included/excluded | Understanding data representativeness |
| `variable-definitions.md` | Key variables, naming conventions, special values | Building queries or interpreting results |
| `data-quality.md` | Suppression rules, selection bias, known limitations | Assessing data reliability |
| `field-of-study.md` | Program-level earnings and debt data | Analyzing outcomes by major/CIP code |

## Decision Trees

### What outcome am I researching?

```
Outcome type?
├─ Post-college earnings
│   ├─ Institution-level → ./references/earnings-data.md
│   └─ By field of study → ./references/field-of-study.md
├─ Student debt levels
│   ├─ Cumulative borrowing → ./references/debt-repayment.md
│   └─ Debt by field → ./references/field-of-study.md
├─ Loan repayment/default
│   └─ Repayment rates → ./references/debt-repayment.md
├─ Completion rates
│   └─ Scorecard completion → ./references/completion-rates.md
└─ Understanding limitations
    ├─ Who is included → ./references/population-coverage.md
    └─ Data quality issues → ./references/data-quality.md
```

### How do I interpret this data?

```
Interpretation question?
├─ Why are earnings suppressed?
│   └─ Privacy thresholds → ./references/data-quality.md
├─ What does "6-year earnings" mean?
│   └─ Cohort timing → ./references/earnings-data.md
├─ Why don't Scorecard rates match IPEDS?
│   └─ Different cohorts → ./references/completion-rates.md
├─ What loans are included in debt?
│   └─ Federal only → ./references/debt-repayment.md
└─ How representative is this data?
    └─ Title IV coverage → ./references/population-coverage.md
```

### Building a query?

```
Query construction?
├─ Variable names and codes → ./references/variable-definitions.md
├─ Suppression flags to handle → ./references/data-quality.md
├─ Understanding cohort years → ./references/earnings-data.md
└─ Field-level queries → ./references/field-of-study.md
```

## Quick Reference: Key Variables

### Earnings Variables

| Variable Pattern | Description | Source |
|-----------------|-------------|--------|
| `MD_EARN_WNE_P6` | Median earnings 6 years after entry | IRS W-2 |
| `MD_EARN_WNE_P8` | Median earnings 8 years after entry | IRS W-2 |
| `MD_EARN_WNE_P10` | Median earnings 10 years after entry | IRS W-2 |
| `PCT_EARN_WNE_P*` | Share working and not enrolled | IRS |
| `*_INC1_*`, `*_INC2_*`, `*_INC3_*` | By FAFSA family income tercile | IRS |

### Debt Variables

| Variable Pattern | Description | Source |
|-----------------|-------------|--------|
| `DEBT_MDN` | Median cumulative debt at graduation | NSLDS |
| `GRAD_DEBT_MDN` | Median debt for completers | NSLDS |
| `WDRAW_DEBT_MDN` | Median debt for withdrawals | NSLDS |
| `LO_INC_DEBT_MDN` | Median debt, low-income students | NSLDS |

### Repayment Variables

| Variable Pattern | Description | Source |
|-----------------|-------------|--------|
| `RPY_*YR_RT` | Repayment rate at N years | NSLDS |
| `COMPL_RPY_*YR_RT` | Repayment rate, completers only | NSLDS |
| `CDR3` | 3-year cohort default rate | FSA |
| `DBRR*` | Dollar-based repayment rate | NSLDS |

### Completion Variables

| Variable Pattern | Description | Source |
|-----------------|-------------|--------|
| `C150_4` | 150% completion rate, 4-year | Scorecard |
| `C150_L4` | 150% completion rate, <4-year | Scorecard |
| `C150_4_POOLED` | Pooled completion rate | Scorecard |
| `COMP_ORIG_YR*_RT` | Completion rate by year | Scorecard |

## Quick Reference: Data Timing

| Metric | "Years After" Meaning | Typical Lag |
|--------|----------------------|-------------|
| 6-year earnings | 6 years after first enrollment | Data from 7+ years ago |
| 10-year earnings | 10 years after first enrollment | Data from 11+ years ago |
| Repayment rates | Years since entering repayment | Varies by metric |
| Completion rates | 150%/200% of normal time | 6-8 years for 4-year schools |

**"After entry" means after first enrollment**, not after graduation.

## Quick Reference: Missing Data Codes

> **Portal Encoding Warning:** The Education Data Portal uses **integer encodings** for all categorical values. In the HuggingFace mirror parquet files, **`null` is the primary indicator for missing/suppressed data** (not the `-1, -2, -3` codes documented in codebooks). String values like `"PrivacySuppressed"` in original Scorecard documentation are represented as `null`. Always verify actual data patterns.

| Data Pattern | Meaning | Notes |
|--------------|---------|-------|
| `null` | Missing/suppressed/not applicable | Primary missing indicator in parquet |
| Valid integer (e.g., 0-4) | Actual value | Categorical codes |
| Positive numeric | Actual value | For earnings, debt, counts |

### Categorical Value Encodings

| Variable | Values |
|----------|--------|
| `pred_degree_awarded_ipeds` | 0=Not classified, 1=Certificate, 2=Associate's, 3=Bachelor's, 4=Graduate |
| Yes/No flags (HBCU, tribal, etc.) | 0=No, 1=Yes, null=Missing |
| `religious_affiliation` | Integer codes 22-200 (see variable-definitions.md), null=None/Missing |

## What Scorecard Data Does NOT Include

| Excluded | Why It Matters |
|----------|----------------|
| Non-Title IV students | Often higher-income; different outcomes |
| Self-employment income | 1099 income excluded from earnings |
| Students still in school | Not working = not in earnings data |
| Private student loans | Only federal loans tracked |
| Students who left the country | Lost to follow-up |

## Comparison: Scorecard vs IPEDS

| Aspect | College Scorecard | IPEDS |
|--------|------------------|-------|
| **Who's tracked** | Title IV aid recipients | First-time, full-time students |
| **Includes part-time** | Yes | No (for grad rates) |
| **Includes transfers-in** | Yes | No (tracked at origin) |
| **Outcome focus** | Earnings, debt, repayment | Completion, retention |
| **Data source** | NSLDS + IRS | Institution-reported |

## Common Analysis Mistakes

**Do Not:**
1. Claim Scorecard shows "all graduates" - it's Title IV recipients only
2. Compare to BLS wages or Census income - different populations
3. Ignore suppression - many programs have no data
4. Forget the time lag - earnings reflect old cohorts
5. Assume debt is total borrowing - private loans excluded
6. Use string codes from original documentation - Portal uses integers

**Do:**
1. Note Title IV limitation prominently in any analysis
2. Check suppression rates before analyzing
3. Use for relative comparisons, not absolute claims
4. Supplement with other data sources
5. Document data vintage (cohort years)
6. Verify actual data types in Portal data (all categorical values are integers)

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Earnings methodology | `./references/earnings-data.md` |
| Cohort definitions | `./references/earnings-data.md` |
| IRS data matching | `./references/earnings-data.md` |
| Earnings suppression | `./references/data-quality.md` |
| Debt metrics | `./references/debt-repayment.md` |
| Repayment rates | `./references/debt-repayment.md` |
| Default rates | `./references/debt-repayment.md` |
| NSLDS data | `./references/debt-repayment.md` |
| Completion methodology | `./references/completion-rates.md` |
| IPEDS comparison | `./references/completion-rates.md` |
| Title IV coverage | `./references/population-coverage.md` |
| Who is excluded | `./references/population-coverage.md` |
| Selection bias | `./references/population-coverage.md` |
| Variable names | `./references/variable-definitions.md` |
| Special values | `./references/variable-definitions.md` |
| Privacy suppression | `./references/data-quality.md` |
| Data limitations | `./references/data-quality.md` |
| Program-level data | `./references/field-of-study.md` |
| CIP codes | `./references/field-of-study.md` |
