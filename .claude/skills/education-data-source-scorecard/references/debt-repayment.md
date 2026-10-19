# Debt and Repayment Data

College Scorecard provides comprehensive data on federal student debt and loan repayment outcomes from the National Student Loan Data System (NSLDS).

> **Portal datasets:**
> - Default rates: `scorecard/colleges_scorecard_repayment_fsa` (177,882 rows x 9 cols, years 1996-2020)
> - Repayment rates: `scorecard/colleges_scorecard_repayment_nslds` (167,976 rows x 31 cols, years 2007-2016)
>
> **Portal uses lowercase LONG format.** Original Scorecard names like `CDR3` become `default_rate` filtered by `years_since_entering_repay`. Repayment rates like `RPY_3YR_RT` become `repay_rate` filtered by `years_since_entering_repay == 3`.
>
> **Note:** Debt variables (`DEBT_MDN`, `GRAD_DEBT_MDN`, etc.) from the original Scorecard bulk downloads are **not available as separate Portal datasets**. Debt information is embedded in other Portal datasets or must be obtained from the Scorecard bulk downloads at `collegescorecard.ed.gov`.

## Data Source: NSLDS

| Aspect | Detail |
|--------|--------|
| Source | National Student Loan Data System |
| Manager | U.S. Department of Education |
| Coverage | All federal student loans |
| Tracking | From disbursement through closure |

NSLDS is the central database for Title IV loans, tracking:
- Loan origination and disbursement
- Outstanding balances
- Repayment status
- Default and delinquency
- Deferment and forbearance

## What Debt Data Includes

### Federal Loans Tracked

| Loan Type | Included |
|-----------|----------|
| Direct Subsidized | Yes |
| Direct Unsubsidized | Yes |
| Direct PLUS (Parent) | No — excluded from cumulative debt metrics; reported separately (`PLUS_DEBT_INST_MD`, `PLUS_DEBT_ALL_MD`) |
| Direct PLUS (Graduate) | Yes |
| Perkins Loans | No — excluded from cumulative debt since the merged 2017-18 file and from repayment-rate metrics |
| FFEL Loans | Yes (federally held) |

### Federal Loans Reported

- Cumulative debt at completion/withdrawal
- Debt by completion status (completers vs non-completers)
- Debt by dependency status
- Debt by family income level

## What Debt Data Excludes

| Excluded | Impact |
|----------|--------|
| **Private student loans** | Not in NSLDS-based debt metrics; the share of borrowing missed varies by school (no published range cited here) |
| **Institutional loans** | School-issued loans not tracked |
| **State loans** | State-specific programs missing |
| **Credit card debt** | Used for education expenses |
| **Family loans** | Informal borrowing |
| **Home equity loans** | Used to pay for college |

**Critical:** Scorecard debt is almost certainly an **underestimate** of total student borrowing, especially at:
- High-cost private institutions
- Institutions where students exhaust federal limits
- Graduate programs with high costs

## Debt Metrics

### Cumulative Debt Variables

| Variable | Description |
|----------|-------------|
| `DEBT_MDN` | Median cumulative federal debt |
| `DEBT_MEAN` | Mean cumulative federal debt |
| `DEBT_N` | Count of students with debt |

### Debt by Completion Status

| Variable | Description |
|----------|-------------|
| `GRAD_DEBT_MDN` | Median debt for completers |
| `WDRAW_DEBT_MDN` | Median debt for withdrawals |
| `GRAD_DEBT_MDN10YR_SUPP` | Median completer debt as 10-year monthly payment, suppressed for n < 30 (a value, not a flag) |

### Debt by Income Level

| Variable | Description |
|----------|-------------|
| `LO_INC_DEBT_MDN` | Median debt, family income $0-30,000 |
| `MD_INC_DEBT_MDN` | Median debt, family income $30,001-75,000 |
| `HI_INC_DEBT_MDN` | Median debt, family income $75,001+ |

### Debt by Dependency Status

| Variable | Description |
|----------|-------------|
| `DEP_DEBT_MDN` | Median debt, dependent students |
| `IND_DEBT_MDN` | Median debt, independent students |

### Monthly Payment Estimates

| Variable | Description |
|----------|-------------|
| `GRAD_DEBT_MDN10YR` | Estimated monthly payment (10-year standard) |

## Repayment Rates

### What Repayment Rate Means

Repayment rate = share of borrowers making progress on reducing principal

**Definition has evolved over time.** Current metrics focus on:
- Has the borrower defaulted?
- Is the principal balance declining?

### Repayment Rate Variables (Portal: `repayment_nslds` dataset)

> **Portal column names are lowercase.** Filter by `years_since_entering_repay` (values: 1, 3, 5, 7) to select time horizon.

| Portal Column | Description | Original Scorecard |
|---------------|-------------|-------------------|
| `repay_rate` | Overall repayment rate | `RPY_*YR_RT` |
| `repay_count` | Count of borrowers | — |
| `repay_rate_pell` | Repayment rate, Pell recipients | — |
| `repay_rate_nopell` | Repayment rate, non-Pell | — |
| `repay_rate_lowincome` | Repayment rate, low income | — |
| `repay_rate_midincome` | Repayment rate, mid income | — |
| `repay_rate_highincome` | Repayment rate, high income | — |
| `repay_rate_firstgen` | Repayment rate, first-gen | — |
| `repay_rate_notfirstgen` | Repayment rate, not first-gen | — |
| `repay_rate_dependent` | Repayment rate, dependent | — |
| `repay_rate_independent` | Repayment rate, independent | — |
| `repay_rate_female` | Repayment rate, female | — |
| `repay_rate_male` | Repayment rate, male | — |
| `years_since_entering_repay` | 1, 3, 5, or 7 years | Was in variable name |

### Original Scorecard Repayment Variables (Historical Reference)

The original Scorecard bulk downloads include additional disaggregations not available in the Portal:

| Variable | Description |
|----------|-------------|
| `COMPL_RPY_1YR_RT` | 1-year rate, completers |
| `COMPL_RPY_3YR_RT` | 3-year rate, completers |
| `NONCOM_RPY_1YR_RT` | 1-year rate, non-completers |

### Dollar-Based Repayment Rates (DBRR)

> **Note:** DBRR variables are from the original Scorecard bulk downloads. They may not be available in the Portal mirror datasets.

| Variable | Description |
|----------|-------------|
| `DBRR1_FED_UG_RT` | Dollar-based rate, 1 year into repayment |
| `DBRR4_FED_UG_RT` | Dollar-based rate, 4 years into repayment |
| `DBRR5_FED_UG_RT` | Dollar-based rate, 5 years into repayment |
| `DBRR10_FED_UG_RT` | Dollar-based rate, 10 years into repayment |
| `DBRR20_FED_UG_RT` | Dollar-based rate, 20 years into repayment |

## Default Rates

### Cohort Default Rate (Portal: `repayment_fsa` dataset)

The official federal accountability metric:

| Portal Column | Description | Original Scorecard |
|---------------|-------------|-------------------|
| `default_rate` | Default rate (Float64) | `CDR2`, `CDR3` |
| `default_rate_denom` | Borrowers in cohort | `CDR3_DENOM` |
| `years_since_entering_repay` | 2 or 3 years | Was in variable name |
| `year` | Year of measurement (end of the default window), not the repayment-entry cohort (e.g., FY2013 entry cohort, cohort 2012, has its 3-year rate at `year` 2015) | — |

**CDR3 definition:** share of borrowers who entered repayment during a federal fiscal year (Oct 1–Sep 30) and defaulted before the end of the second following fiscal year (e.g., FY2016 cohort: entered repayment Oct 1, 2015–Sep 30, 2016; defaulted before Sep 30, 2018).

### What Counts as Default

- Scorecard repayment-rate categories classify a loan as in default after more than 360 days of nonpayment (31–360 days = delinquent)
- CDR default (34 CFR 668.202(c)(1)): Direct Loans after 360 days of delinquency (270 days if delinquency began before Oct 7, 1998); FFEL loans once a default claim is paid by a guaranty agency or ED (FFEL statutory default: 270 days for loans repayable monthly, 20 U.S.C. §1085(l))

### CDR Limitations

| Issue | Impact |
|-------|--------|
| 3-year window only | Long-term struggles not captured |
| Strategic timing | Schools may encourage forbearance to delay default |
| Income-driven plans | Prevent default but may not build equity |
| Excludes consolidation | Some defaults "hidden" via consolidation |

## Repayment Complexities

### Income-Driven Repayment (IDR)

Many borrowers enroll in IDR plans:
- Payments based on income, not loan balance
- $0 payments possible for low earners
- 20-25 year forgiveness
- Balance may grow while in IDR

**Impact on metrics:** IDR participants may be "in repayment" but not reducing principal.

### Deferment and Forbearance

Borrowers can pause payments:
- Economic hardship
- Unemployment
- Returning to school
- Military service

**Impact on metrics:** Not in default, but not progressing.

### Loan Forgiveness Programs

- Public Service Loan Forgiveness (PSLF)
- Teacher Loan Forgiveness
- Income-driven plan forgiveness

Forgiveness may affect long-term repayment rates.

## Interpreting Debt Data

### Debt ≠ Cost

| Metric | What It Shows |
|--------|--------------|
| Sticker price | Published tuition + fees |
| Net price | After grants/scholarships |
| Debt | Actually borrowed (subset of cost) |

Students may pay with:
- Family contributions (not debt)
- Work earnings (not debt)
- Scholarships/grants (not debt)
- Private loans (not in Scorecard)

### Debt by Completion Status

Non-completers typically have:
- Lower absolute debt (left early)
- BUT worse outcomes (no credential)
- Higher default rates

Completers typically have:
- Higher absolute debt (more time in school)
- BUT better outcomes (credential earned)
- Lower default rates

### Low Debt May Not Mean "Affordable"

Low debt might indicate:
- Generous financial aid (good)
- Students couldn't afford to borrow more (bad)
- Students worked excessive hours (bad)
- Students chose not to complete (bad)
- High dropout rate (bad)

## Debt-to-Earnings Metrics

### Gainful Employment Metrics

| Variable | Description |
|----------|-------------|
| `DEBT_EARN_*` | Various debt-to-earnings ratios |

Used for program-level accountability.

### Interpreting Debt-to-Earnings

(Illustrative; thresholds echo past Gainful Employment rules — not verified here.)

| Ratio | Interpretation |
|-------|---------------|
| < 8% | Generally manageable |
| 8-12% | Potentially burdensome |
| > 12% | High debt burden relative to earnings |

## Repayment Rate Trends

### Why Repayment Rates Change

- Economy and unemployment
- Policy changes (IDR expansion, forgiveness)
- Institutional enrollment changes
- Student body composition

### Pandemic Effects

2020-2023 repayment data affected by:
- Payment pause (March 2020 - September 2023)
- $0 payments counted as "on track"
- Forbearance protected from default

## Recommended Practices

### For Debt Analysis

1. **Note federal loans only** - Private debt excluded
2. **Compare within similar institution types** - Cost structures vary
3. **Consider completion status** - Completers vs non-completers differ
4. **Check for suppression** - Small programs may lack data

### For Repayment Analysis

1. **Understand metric definitions** - Have changed over time
2. **Consider IDR effects** - "In repayment" ≠ "reducing principal"
3. **Note pandemic effects** - 2020-2023 data atypical
4. **Use completion-specific rates** when possible

### Reporting Recommendations

```
Good: "Median federal loan debt for graduates was $27,000"
Better: "Median federal loan debt for graduates was $27,000; 
        private loans not included"
Best: "Median federal loan debt for graduates was $27,000 
      (federal loans only; private loans excluded). 
      35% of graduates borrowed no federal loans."
```

## Common Pitfalls

| Pitfall | Why It's Wrong |
|---------|---------------|
| "Average debt is $X" | May mean nothing - some students borrow $0 |
| "School is affordable because debt is low" | Low debt may mean high dropout |
| "High repayment rate means good outcomes" | IDR can mask struggles |
| "Comparing debt across school types" | Cost structures fundamentally differ |
| "Debt = cost of attendance" | Debt is only what was borrowed |
