# College Scorecard Context

The College Scorecard provides federal data on student outcomes, focusing on earnings and debt for students who received federal financial aid. In this system, Scorecard data is accessed through the Urban Institute Education Data Portal, which restructures variable names to lowercase and applies integer encoding to categorical variables.

## Source Overview

| Attribute | Value |
|-----------|-------|
| Publisher | U.S. Department of Education |
| Data Sources | NSLDS (loans), IRS (earnings), IPEDS (institutional) |
| Coverage | Students receiving Title IV federal financial aid |
| Focus | Student outcomes, costs, debt |
| Primary Use | Earnings, debt, repayment, completion |

## Critical Coverage Limitation

**The single most important caveat for College Scorecard:**

### Title IV Recipients Only

Scorecard data covers ONLY students who received federal financial aid (Title IV). This includes:
- Pell Grants
- Federal student loans
- Federal work-study

### Who Is Excluded

| Excluded Group | Why It Matters |
|----------------|----------------|
| Students paying full price | Often higher-income; different outcomes |
| Students with only institutional/state aid | Missing from federal records |
| International students | Not eligible for federal aid |
| Students at non-Title IV schools | Not in system |
| Some graduate students | If no federal aid |

### Size of the Gap

Coverage varies widely by sector and selectivity; no published national ranges are cited here. Compute coverage for your sample (e.g., Scorecard `PCTPELL`/`PCTFLOAN` or IPEDS SFA shares).

**(DAAF inference) The data likely overrepresents lower-income students**, who are more likely to receive federal aid (follows from Title IV-only coverage; no published magnitude cited).

## Earnings Data

### What Earnings Data Shows

Scorecard reports earnings from Treasury/IRS tax records (W-2 wages and deferred compensation plus positive Schedule SE self-employment earnings):
- Median earnings
- Earnings by percentile (25th, 75th)
- Earnings thresholds (above $25K, $28K, etc.)

### Earnings Caveats

| Issue | Impact |
|-------|--------|
| Title IV only | Lower-income students likely overrepresented (DAAF inference) |
| Tax-record earnings only | Unreported (cash) and non-labor income excluded |
| Working students only | Non-employed excluded from earnings |
| Suppression | `PS` when privacy standards not met; DP noise; `*_SUPP` versions use a <30-student rule |
| Time lag | 6-10 years after enrollment |

### What Earnings Excludes

- Unreported (cash-economy) income
- Self-employment or gig income not reported on Schedule SE (inference)
- Graduate school students (not working)
- Stay-at-home parents
- Deceased individuals
- Those who left the country

### Earnings Timing

| Metric | Timing |
|--------|--------|
| Completer earnings (exit cohorts) | 1 and 5 years after completion (`MD_EARN_WNE_1YR`/`_5YR`; the Portal earnings rows probed carry only 6/8/10 years after entry) |
| 6-year earnings | 6 years after entry |
| 8-year earnings | 8 years after entry |
| 10-year earnings | 10 years after entry |

**"After entry" means after first enrollment**, not after graduation.

### Interpreting Earnings

```python
# Earnings analysis caveats
def interpret_earnings(earnings_6yr, earnings_10yr, pct_employed):
    """
    Context for earnings interpretation:
    - These are Title IV recipients only
    - Only employed individuals included
    - Self-employment counted only via Schedule SE
    """
    notes = []
    
    if pct_employed and pct_employed < 0.7:
        notes.append("WARNING: <70% employed; earnings may not be representative")
    
    if earnings_10yr and earnings_10yr < 30000:
        notes.append("NOTE: Low earnings may reflect part-time work or career fields")
    
    return notes
```

```r
# Earnings analysis caveats
# Context for earnings interpretation:
# - These are Title IV recipients only
# - Only employed individuals included
# - Self-employment counted only via Schedule SE

if (!is.null(pct_employed) && pct_employed < 0.7) {
  cat("WARNING: <70% employed; earnings may not be representative\n")
}

if (!is.null(earnings_10yr) && earnings_10yr < 30000) {
  cat("NOTE: Low earnings may reflect part-time work or career fields\n")
}
```

### Earnings Suppression

Earnings are suppressed when:
- Cell sizes do not meet privacy standards (shown as `PS`; base-element threshold not stated in the October 2026 technical documentation)
- Separate `*_SUPP` versions of consumer-site elements suppress institutions with fewer than 30 students in the denominator
- Counts and medians also carry differential-privacy noise

This particularly affects:
- Small programs
- Fields with many graduate school attendees
- Newer programs without enough cohorts

## Debt and Repayment

### Federal Loans Only

Scorecard debt data includes ONLY federal loans:
- Direct Subsidized Loans
- Direct Unsubsidized Loans
- Grad PLUS (in graduate-student [LOAN]=FED metrics only)
- Not Perkins: excluded from cumulative debt since the merged 2017-18 file (and from repayment-rate metrics)
- Not Parent PLUS: excluded from cumulative debt metrics (reported separately)

### What Debt Excludes

| Excluded | Why It Matters |
|----------|----------------|
| Private student loans | Not tracked (share of borrowing varies; no figure cited) |
| Institutional loans | Not tracked federally |
| Credit card debt | Used for education expenses |
| Family loans | Informal borrowing |

### Debt Metrics

| Metric | Definition |
|--------|------------|
| Median debt | Median cumulative federal borrowing |
| Monthly payment | Estimated 10-year repayment |
| Debt-to-earnings | Debt relative to earnings |

### Repayment Rates

**Repayment rate definitions have changed over time.**

Current definition: Share of borrowers who have not defaulted and are making progress on principal.

Complexities:
- Income-driven repayment plans affect rates
- Deferment and forbearance affect timing
- Definition of "progress" has changed

### Default Rates

| Metric | Definition |
|--------|------------|
| CDR (Cohort Default Rate) | Federal 3-year default measure |
| Scorecard default | May use different windows |

Default rate limitations:
- CDR counts a Direct Loan borrower as defaulted after 360 days of delinquency (270 days if delinquency began before Oct 7, 1998) and an FFEL borrower once a default claim is paid (FFEL statutory default: 270 days for monthly-installment loans, 20 U.S.C. §1085(l)) — 34 CFR 668.202(c)(1); Scorecard repayment-rate categories treat >360 days of nonpayment as default
- Income-driven plans prevent default but may not build equity
- Strategic behavior affects timing

## Cohort Definitions

### Scorecard vs. IPEDS

| Aspect | Scorecard NSLDS/Treasury-based measures | IPEDS |
|--------|-----------|-------|
| Who's tracked | Title IV recipients | First-time full-time |
| Includes part-time | Yes | No |
| Includes transfers | Entering transfers | No (at origin) |
| Entry point | Any entry | Fall entry |

Scorecard `C150_*`/`C200_*` completion rates are the IPEDS full-time, first-time rates, not Title IV-recipient cohorts.

### Cohort Year Meaning

For `year=2014` earnings data (Portal `year` = calendar year earnings are measured = `cohort_year` + `years_after_entry`):
- 6-year earnings: students who entered in 2008
- 8-year earnings: entered in 2006
- 10-year earnings: entered in 2004

Cohort definitions can be complex; check documentation.

## Data Freshness

### Significant Lag

Scorecard data has inherent lag:

| Data Point | Typical Lag |
|------------|-------------|
| Enrollment cohort | 6-10 years ago |
| Earnings measurement | (Illustrative/unsourced — verify) 1-2 years for processing |
| Data release | (Illustrative/unsourced — verify) 1 year after measurement |

**Earnings for "newest" data may reflect students who entered 7+ years ago.**

### Implications

- Labor market conditions when measured may differ from now
- Fields with rapid change (tech) may be outdated
- Institutional changes not reflected in old cohorts

## Comparability Issues

### Do Not Compare Scorecard Earnings To:

| Source | Why Not Comparable |
|--------|-------------------|
| BLS occupation wages | Different populations, timing |
| Census income data | Different definitions, population |
| Alumni surveys | Different methodology, response bias |
| General population | Scorecard is not representative |

### Valid Comparisons

- Same institution over time (with caveats)
- Similar institutions with similar aid populations
- Same field across similar institution types

## Program-Level Data

### Field of Study Data

Scorecard provides some earnings by field (CIP code):
- 2-digit CIP level
- 4-digit CIP level (more specific)

### Field-Level Caveats

| Issue | Impact |
|-------|--------|
| Small programs suppressed | Many fields unavailable |
| Double majors | Counted in one field |
| Field changes | Student may have changed majors |
| Graduate school | Students in grad school not working |

### Using Field Data

```python
# Field-level analysis
def analyze_field_earnings(df, cip_level="2digit"):
    # Check suppression
    suppressed_pct = df.filter(pl.col("earnings_median").is_null()).height / df.height
    
    if suppressed_pct > 0.3:
        print(f"WARNING: {suppressed_pct:.0%} of fields suppressed")
        print("Results may not be representative")
    
    return df.filter(pl.col("earnings_median").is_not_null())
```

```r
# Field-level analysis - check suppression
suppressed_pct <- sum(is.na(df$earnings_median)) / nrow(df)

if (suppressed_pct > 0.3) {
  cat(sprintf("WARNING: %.0f%% of fields suppressed\n", suppressed_pct * 100))
  cat("Results may not be representative\n")
}

df <- df |> filter(!is.na(earnings_median))
```

## Institutional Identifiers

### UNITID

Scorecard uses UNITID, same as IPEDS:

```python
# Link Scorecard to IPEDS
scorecard = fetch("college-university/scorecard/earnings/2014")
ipeds = fetch("college-university/ipeds/directory/2020")

merged = scorecard.join(ipeds, on="unitid", how="left")
```

```r
# Link Scorecard to IPEDS
scorecard <- arrow::read_parquet("data/raw/colleges_scorecard_earnings.parquet") |> filter(year == 2014)
ipeds <- arrow::read_parquet("data/raw/colleges_ipeds_directory.parquet") |> filter(year == 2020)

merged <- scorecard |> left_join(ipeds, by = "unitid")
```

### OPEID

Some Scorecard data may use OPEID:
- Links to financial aid system
- Main campus vs. branches may differ from IPEDS

## Common Analysis Mistakes

### Do Not:

1. **Claim Scorecard shows what "all graduates" earn**
   - Title IV recipients only

2. **Compare to general labor market data**
   - Different populations

3. **Use for small programs without checking suppression**
   - Many programs have no data

4. **Ignore the time lag**
   - Earnings reflect old cohorts

5. **Assume debt reflects total borrowing**
   - Federal only; private excluded

### Do:

1. **Note Title IV limitation prominently**
2. **Check suppression before analyzing**
3. **Use for relative comparisons**, not absolute claims
4. **Supplement with other data sources** for context
5. **Document data vintage clearly**

## Recommended Practices

### Before Analysis

1. Check coverage (how many institutions have data?)
2. Check suppression rates by variable
3. Understand cohort timing
4. Note data limitations prominently

### For Earnings Analysis

1. State population clearly (Title IV recipients)
2. Note employed students only
3. Provide context for time lag
4. Don't over-interpret small differences

### For Debt Analysis

1. Note federal loans only
2. Provide repayment context
3. Consider income-driven plan effects
4. Don't compare across very different institutions

### For Comparisons

1. Compare within similar institution types
2. Use relative rankings rather than absolute values
3. Document all limitations
4. Consider supplementing with IPEDS, institutional data

## Related Data Sources

| Source | Use When |
|--------|----------|
| IPEDS | Need enrollment, institutional characteristics |
| NSLDS | Need loan-level detail (restricted access) |
| Census | Need general population context |
| BLS | Need occupational wage context |
| Alumni surveys | Need richer outcome data |

## Quick Reference Card

| Task | Guidance |
|------|----------|
| Understanding coverage | Title IV recipients only |
| Interpreting earnings | Note population, suppression, lag |
| Using debt data | Federal loans only |
| Comparing institutions | Within similar types only |
| Field-level analysis | Check suppression first |
| Linking to IPEDS | Use UNITID |
| Time context | Earnings reflect cohorts from 6-10 years ago |
| General claims | Always note limitations |
