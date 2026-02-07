# Debt and Repayment Data

College Scorecard provides comprehensive data on federal student debt and loan repayment outcomes from the National Student Loan Data System (NSLDS).

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
| Direct PLUS (Parent) | Conditional |
| Direct PLUS (Graduate) | Yes |
| Perkins Loans | Yes (while active) |
| FFEL Loans | Yes (federally held) |

### Federal Loans Reported

- Cumulative debt at completion/withdrawal
- Debt by completion status (completers vs non-completers)
- Debt by dependency status
- Debt by family income level

## What Debt Data Excludes

| Excluded | Impact |
|----------|--------|
| **Private student loans** | 10-20% of total borrowing at some schools missing |
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
| `GRAD_DEBT_MDN10YR_SUPP` | Suppression flag |

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

### Repayment Rate Variables

| Variable | Description |
|----------|-------------|
| `RPY_1YR_RT` | 1-year repayment rate |
| `RPY_3YR_RT` | 3-year repayment rate |
| `RPY_5YR_RT` | 5-year repayment rate |
| `RPY_7YR_RT` | 7-year repayment rate |

### Repayment by Completion Status

| Variable | Description |
|----------|-------------|
| `COMPL_RPY_1YR_RT` | 1-year rate, completers |
| `COMPL_RPY_3YR_RT` | 3-year rate, completers |
| `NONCOM_RPY_1YR_RT` | 1-year rate, non-completers |

### Repayment by Income Level

| Suffix | Family Income Level |
|--------|-------------------|
| `_LO_INC_` | Lowest third |
| `_MD_INC_` | Middle third |
| `_HI_INC_` | Highest third |

### Dollar-Based Repayment Rates (DBRR)

Newer metric measuring share of loan dollars being repaid:

| Variable | Description |
|----------|-------------|
| `DBRR1_FED_UG_RT` | Dollar-based rate, 1 year into repayment |
| `DBRR4_FED_UG_RT` | Dollar-based rate, 4 years into repayment |
| `DBRR5_FED_UG_RT` | Dollar-based rate, 5 years into repayment |
| `DBRR10_FED_UG_RT` | Dollar-based rate, 10 years into repayment |
| `DBRR20_FED_UG_RT` | Dollar-based rate, 20 years into repayment |

## Default Rates

### Cohort Default Rate (CDR)

The official federal accountability metric:

| Variable | Description |
|----------|-------------|
| `CDR3` | 3-year cohort default rate |
| `CDR3_DENOM` | Borrowers in CDR3 cohort |

**CDR Definition:** Share of borrowers who enter repayment and default within 3 years.

### What Counts as Default

- 270+ days delinquent on payments
- Formal default status in NSLDS

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
