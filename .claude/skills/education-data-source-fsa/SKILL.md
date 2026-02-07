---
name: education-data-source-fsa
description: Federal Student Aid (FSA) data source for the Urban Institute Education Data Portal. Covers Title IV programs including Pell Grants, Direct Loans, PLUS loans, campus-based aid, financial responsibility composite scores, and 90/10 rule metrics. Use when working with federal student aid data, analyzing institutional aid distributions, or understanding Title IV program participation.
metadata:
  audience: data-analysts
  domain: education-data
---

# Federal Student Aid (FSA) Data Source

Reference guide for FSA data available through the Urban Institute Education Data Portal. FSA data provides institutional-level information on Title IV federal student aid programs administered by the U.S. Department of Education.

## What is FSA Data?

Federal Student Aid (FSA) is the office within the U.S. Department of Education that administers Title IV aid programs:

- **Title IV Programs**: Federal financial aid authorized under Title IV of the Higher Education Act (HEA)
- **Institutional Coverage**: All Title IV-eligible postsecondary institutions (approximately 5,500+ schools)
- **Data Types**: Aid disbursements, recipient counts, loan/grant volumes, financial responsibility metrics
- **Primary Identifier**: `unitid` (6-digit IPEDS institution ID)
- **Years Available**: 1999-2021 depending on endpoint

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `title-iv-programs.md` | Pell Grants, Direct Loans, PLUS, campus-based aid | Understanding aid program types |
| `financial-responsibility.md` | Composite scores, institutional oversight | Analyzing institutional financial health |
| `90-10-rule.md` | For-profit revenue requirements | Working with proprietary institutions |
| `variable-definitions.md` | Key variables, aid types, amounts | Building queries, interpreting results |
| `data-quality.md` | Known issues, coverage, timing | Understanding data limitations |

## Decision Trees

### What FSA topic am I researching?

```
FSA research topic?
├─ Grant programs
│   ├─ Federal Pell Grants → ./references/title-iv-programs.md
│   ├─ FSEOG (campus-based) → ./references/title-iv-programs.md
│   └─ Grant amounts/recipients → ./references/variable-definitions.md
├─ Loan programs
│   ├─ Direct Subsidized/Unsubsidized → ./references/title-iv-programs.md
│   ├─ Parent PLUS loans → ./references/title-iv-programs.md
│   ├─ Graduate PLUS loans → ./references/title-iv-programs.md
│   ├─ Perkins Loans (legacy) → ./references/title-iv-programs.md
│   └─ Loan volumes/disbursements → ./references/variable-definitions.md
├─ Campus-based programs
│   ├─ Federal Work-Study → ./references/title-iv-programs.md
│   ├─ FSEOG → ./references/title-iv-programs.md
│   └─ Program allocations → ./references/variable-definitions.md
├─ Institutional oversight
│   ├─ Financial responsibility scores → ./references/financial-responsibility.md
│   ├─ 90/10 rule compliance → ./references/90-10-rule.md
│   └─ Eligibility/participation → ./references/data-quality.md
└─ Data quality concerns
    └─ Coverage, timing, limitations → ./references/data-quality.md
```

### Which FSA endpoint do I need?

```
FSA endpoint selection?
├─ Need grant data (Pell, FSEOG)
│   └─ /college-university/fsa/grants/{year}/
├─ Need loan data (Direct, PLUS)
│   └─ /college-university/fsa/loans/{year}/
├─ Need campus-based program data
│   └─ /college-university/fsa/campus-based-volume/{year}/
├─ Need institutional financial health
│   └─ /college-university/fsa/financial-responsibility/{year}/
└─ Need 90/10 compliance (for-profits)
    └─ /college-university/fsa/90-10-revenue-percentages/{year}/
```

## Quick Reference: FSA Endpoints

| Endpoint | Description | Years | Key Variables |
|----------|-------------|-------|---------------|
| `/fsa/grants/` | Pell Grant recipients and amounts | 1999-2018 | `recipients`, `disbursements` |
| `/fsa/loans/` | Direct Loan recipients and volumes | 1999-2018 | `recipients`, `disbursements` |
| `/fsa/campus-based-volume/` | FWS, FSEOG, Perkins allocations | 2001-2017 | `fws_*`, `fseog_*`, `perkins_*` |
| `/fsa/financial-responsibility/` | Composite scores by institution | 2006-2016 | `composite_score` |
| `/fsa/90-10-revenue-percentages/` | For-profit Title IV revenue ratios | 2014-2017 | `title_iv_percentage` |

## Quick Reference: Title IV Programs

| Program | Type | Eligibility | Max Amount (2025-26) |
|---------|------|-------------|----------------------|
| Federal Pell Grant | Need-based grant | Undergrad with financial need | $7,395 |
| Direct Subsidized Loan | Need-based loan | Undergrad with financial need | $3,500-$5,500/yr |
| Direct Unsubsidized Loan | Non-need loan | Undergrad/Grad students | $5,500-$20,500/yr |
| Parent PLUS Loan | Credit-based loan | Parents of dependent undergrads | Cost of attendance |
| Graduate PLUS Loan | Credit-based loan | Graduate/professional students | Cost of attendance |
| FSEOG | Need-based grant | Undergrad with exceptional need | $100-$4,000/yr |
| Federal Work-Study | Employment program | Students with financial need | Varies by school |
| Perkins Loan | Need-based loan | Discontinued (no new loans after 2017) | N/A |

## Quick Reference: Financial Responsibility Scores

| Score Range | Classification | Meaning |
|-------------|----------------|---------|
| 1.5 to 3.0 | Financially Responsible | Meets all standards |
| 1.0 to 1.49 | In the Zone | Provisionally certified, monitoring required |
| Below 1.0 | Not Financially Responsible | Must post letter of credit or face sanctions |
| -1.0 | Minimum score | Lowest possible composite score |

## API URL Patterns

FSA endpoints follow the Education Data Portal pattern:

```
https://educationdata.urban.org/api/v1/college-university/fsa/{endpoint}/{year}/
```

**Examples:**

```
# Pell Grant data for 2018
/api/v1/college-university/fsa/grants/2018/

# Direct Loan data for 2017, California institutions
/api/v1/college-university/fsa/loans/2017/?fips=6

# Financial responsibility scores for 2016
/api/v1/college-university/fsa/financial-responsibility/2016/

# 90/10 data for for-profit institutions
/api/v1/college-university/fsa/90-10-revenue-percentages/2017/
```

## Common Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `unitid` | IPEDS institution ID | `?unitid=110635` |
| `fips` | State FIPS code | `?fips=6` (California) |
| `year` | Academic year | Specified in URL path |

## Joining FSA Data with Other Sources

| Source 1 | Source 2 | Join Key | Use Case |
|----------|----------|----------|----------|
| FSA Grants | IPEDS Directory | `unitid` | Aid by institution type |
| FSA Loans | IPEDS Enrollment | `unitid` | Loan volume per student |
| FSA Financial Responsibility | IPEDS Finance | `unitid` | Financial health analysis |
| FSA 90/10 | IPEDS Directory | `unitid` | For-profit compliance |
| FSA | College Scorecard | `unitid` | Aid and student outcomes |

## Common Research Applications

| Research Question | FSA Endpoints | Complementary Data |
|-------------------|---------------|-------------------|
| Pell Grant distribution by institution type | `/fsa/grants/` | IPEDS Directory |
| Student loan burden by sector | `/fsa/loans/` | IPEDS Enrollment |
| Financial stability of for-profit schools | `/fsa/financial-responsibility/`, `/fsa/90-10-revenue-percentages/` | IPEDS Directory |
| Campus-based aid allocation patterns | `/fsa/campus-based-volume/` | IPEDS Directory |
| Title IV participation trends | `/fsa/grants/`, `/fsa/loans/` | Multiple years |

## Data Update Schedule

- FSA data typically lags 1-2 years behind the current award year
- Financial responsibility scores published annually
- 90/10 percentages updated after institutional fiscal year audits
- Campus-based data tied to FISAP reporting cycle

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Pell Grant program | `./references/title-iv-programs.md` |
| Direct Loan program | `./references/title-iv-programs.md` |
| PLUS loans | `./references/title-iv-programs.md` |
| Federal Work-Study | `./references/title-iv-programs.md` |
| FSEOG grants | `./references/title-iv-programs.md` |
| Perkins Loans | `./references/title-iv-programs.md` |
| Composite score calculation | `./references/financial-responsibility.md` |
| Primary reserve ratio | `./references/financial-responsibility.md` |
| Equity ratio | `./references/financial-responsibility.md` |
| Net income ratio | `./references/financial-responsibility.md` |
| 90/10 rule requirements | `./references/90-10-rule.md` |
| For-profit revenue sources | `./references/90-10-rule.md` |
| Grant variables | `./references/variable-definitions.md` |
| Loan variables | `./references/variable-definitions.md` |
| Campus-based variables | `./references/variable-definitions.md` |
| Data coverage | `./references/data-quality.md` |
| Missing data handling | `./references/data-quality.md` |
| Year coverage by endpoint | `./references/data-quality.md` |
