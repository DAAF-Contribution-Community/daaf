---
name: education-data-source-scorecard
description: >-
  College Scorecard data source for post-college outcomes including earnings
  from IRS/Treasury, student debt and repayment from NSLDS, and completion
  metrics. Use when analyzing post-graduation earnings, loan repayment, debt
  levels, or when understanding Scorecard's Title IV recipient limitation is
  critical. Covers only Title IV federal aid recipients, not all students.
metadata:
  audience: data-analysts
  domain: education-data
---

# Scorecard Data Source Reference

Federal data on post-college outcomes including earnings, debt, and repayment for students who received Title IV financial aid. Links education records to IRS tax data for actual earnings, making it the primary source for post-college labor market outcomes.

> **CRITICAL: Value Encoding**
>
> The Education Data Portal uses **integer encodings** for all categorical variables.
> In HuggingFace mirror parquet files, **`null` is the primary indicator for
> missing/suppressed data** — not the string `"PrivacySuppressed"` from original
> Scorecard documentation. Always verify codes against codebooks.
>
> | Context | `pred_degree_awarded_ipeds` | HBCU / tribal flags | `religious_affiliation` |
> |---------|----------------------------|---------------------|-------------------------|
> | **Portal (integer)** | `0`-`4` | `0` / `1` | Integer codes 22-200 |
> | Original Scorecard | String labels | String labels | String labels |
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is College Scorecard?

- **Publisher**: U.S. Department of Education
- **Primary value**: Post-college labor market outcomes (earnings) and debt/repayment metrics
- **Data sources**: NSLDS (loans/aid), IRS/Treasury (earnings), IPEDS (institutional characteristics)
- **Coverage**: **Title IV federal aid recipients only** — not all students
- **Unique feature**: Links education to IRS tax records for actual earnings data
- **Access**: Education Data Portal mirrors (parquet/CSV) or bulk downloads at collegescorecard.ed.gov
- **Primary identifier**: `unitid` (IPEDS institution ID)

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

## Quick Reference: Scorecard Variables

### Portal Data Structure (CRITICAL)

The Portal uses **LONG format** with time horizon as a column, NOT the WIDE format from original Scorecard files.

| Scorecard (WIDE) | Portal (LONG) | How to Get |
|------------------|---------------|------------|
| `MD_EARN_WNE_P6` | `earnings_med` | Filter: `years_after_entry == 6` |
| `MD_EARN_WNE_P10` | `earnings_med` | Filter: `years_after_entry == 10` |
| `COUNT_WNE_P6` | `count_working` | Filter: `years_after_entry == 6` |
| `CONTROL`, `INSTNM` | NOT IN FILE | Join to IPEDS directory |

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

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `unitid` | 6-digit integer | Institution | `110635` | Same as IPEDS unitid; primary join key |

### Data Timing

| Metric | "Years After" Meaning | Typical Lag |
|--------|----------------------|-------------|
| 6-year earnings | 6 years after first enrollment | Data from 7+ years ago |
| 10-year earnings | 10 years after first enrollment | Data from 11+ years ago |
| Repayment rates | Years since entering repayment | Varies by metric |
| Completion rates | 150%/200% of normal time | 6-8 years for 4-year schools |

**"After entry" means after first enrollment**, not after graduation.

### Categorical Value Encodings

| Variable | Values |
|----------|--------|
| `pred_degree_awarded_ipeds` | 0=Not classified, 1=Certificate, 2=Associate's, 3=Bachelor's, 4=Graduate |
| Yes/No flags (HBCU, tribal, etc.) | 0=No, 1=Yes, null=Missing |
| `religious_affiliation` | Integer codes 22-200 (see variable-definitions.md), null=None/Missing |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `null` | Missing/suppressed/not applicable | Primary missing indicator in parquet files |
| `-3` | Suppressed | Privacy suppression (appears in some numeric fields) |
| Valid integer (e.g., 0-4) | Actual value | Categorical codes |
| Positive numeric | Actual value | Earnings, debt, counts |

```python
# Filter for valid earnings (handle both null and -3)
valid = df.filter(
    (pl.col("earnings_med").is_not_null()) &
    (pl.col("earnings_med") != -3)
)
```

## Data Access

Datasets for Scorecard are available via the mirror system. See `datasets-reference.md` for canonical paths and `fetch-patterns.md` for fetch code patterns.

**Key datasets:**

| Dataset | Path | Type |
|---------|------|------|
| Earnings | `scorecard/colleges_scorecard_earnings` | Single |

6 Scorecard datasets exist in the mirror. See `datasets-reference.md` for the complete list with codebook paths.

### Filtering

```python
# Filter by time horizon (LONG format — filter, don't use wide column names)
six_yr = df.filter(pl.col("years_after_entry") == 6)

# Filter for valid earnings (exclude null and suppressed)
valid = df.filter(
    (pl.col("earnings_med").is_not_null()) &
    (pl.col("earnings_med") != -3)
)

# Join to IPEDS for institution names/control (not in Scorecard data)
# ipeds_dir = pl.read_parquet("...ipeds/directory/...")
# df = df.join(ipeds_dir.select("unitid", "inst_name", "control"), on="unitid")
```

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| "All graduates" claims | Scorecard covers Title IV recipients only, not all students | Note Title IV limitation prominently in any analysis |
| Wage comparison | Comparing to BLS wages or Census income uses different populations | Use for relative comparisons, not absolute claims; document population differences |
| Ignoring suppression | Many programs have no data due to privacy thresholds | Check suppression rates before analyzing; document coverage |
| Time lag ignored | Earnings reflect old cohorts (6-year = data from 7+ years ago) | Document data vintage and cohort years explicitly |
| Total borrowing assumption | Scorecard debt includes only federal loans, not private | State "federal loans only" when reporting debt figures |
| String codes from docs | Original Scorecard uses string labels; Portal uses integers | Verify actual data types in Portal parquet files; use integer codes |
| Wide-format variable names | Using `MD_EARN_WNE_P10` column name on Portal data | Portal uses LONG format — filter `years_after_entry` instead |

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

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ipeds` | Institutional characteristics, enrollment, finance | Join on `unitid` for institution names, control type, enrollment context |
| `education-data-source-pseo` | Alternative post-college earnings (Census LEHD) | When broader population coverage needed (not limited to Title IV) |
| `education-data-source-fsa` | Federal student aid details | Deeper analysis of aid types and disbursements |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |

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
