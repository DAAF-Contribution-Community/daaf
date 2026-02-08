---
name: education-data-source-fsa
description: Federal Student Aid (FSA) data source for the Urban Institute Education Data Portal. Covers Title IV programs including Pell Grants, Direct Loans, PLUS loans, campus-based aid, financial responsibility composite scores, and 90/10 rule metrics. Use when working with federal student aid data, analyzing institutional aid distributions, or understanding Title IV program participation.
metadata:
  audience: data-analysts
  domain: education-data
---

# Federal Student Aid (FSA) Data Source

Reference guide for FSA data available through the Urban Institute Education Data Portal. FSA data provides institutional-level information on Title IV federal student aid programs administered by the U.S. Department of Education.

> **CRITICAL: Portal Integer Encoding**
>
> The Education Data Portal converts categorical variables to **integers**. This differs from original FSA documentation which may use string codes. All categorical columns in the Portal parquet files are integer-typed.
>
> | Variable | Example Value | Meaning |
> |----------|---------------|---------|
> | `grant_type` | `1` | Federal Pell Grant |
> | `loan_type` | `1` | Subsidized Direct Loan - Undergraduate |
> | `award_type` | `1` | Federal Supplemental Educational Opportunity Grants |
> | `fips` | `6` | California |
> | `allocation_flag` | `1` | Yes |
>
> **Missing data codes** (`-1`, `-2`, `-3`) apply to `numeric` format variables, not categorical codes.

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
| `fsa/grants/` | Grant recipients and amounts by type | 1999-2021 | `grant_type`, `grant_recipients_*`, `value_grants_disbursed_*` |
| `fsa/loans/` | Loan recipients and volumes by type | 1999-2021 | `loan_type`, `loan_recipients_*`, `value_loan_disbursements_*` |
| `fsa/campus-based-volume/` | FWS, FSEOG, Perkins by award type | 2001-2021 | `award_type`, `campus_award_recipients_*`, `value_campus_disbursed_*` |
| `fsa/financial-responsibility/` | Composite scores by institution | 2006-2016 | `financial_resp_score` |
| `fsa/90-10-revenue-percentages/` | For-profit Title IV revenue ratios | 2014-2021 | `rev_pct_90_10` |

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

## Data Access Patterns

> **Recommended:** Use the HuggingFace mirror for bulk data access. See `education-data-query` skill for download patterns.

### HuggingFace Mirror Paths

FSA data is available as parquet files:

```
college-university/fsa/grants/colleges_fsa_grants.parquet
college-university/fsa/loans/colleges_fsa_loans.parquet
college-university/fsa/campus-based-volume/colleges_fsa_campus_based_volume.parquet
college-university/fsa/financial-responsibility/colleges_fsa_composite_scores.parquet
college-university/fsa/90-10-revenue-percentages/colleges_fsa_90_10_revenue_percentages.parquet
```

### FSA Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| Grants | `college-university/fsa/grants/codebook_colleges_fsa_grants` |
| Loans | `college-university/fsa/loans/codebook_colleges_fsa_loans` |
| Campus-Based Volume | `college-university/fsa/campus-based-volume/codebook_colleges_fsa_campus_based_volume` |
| Financial Responsibility | `college-university/fsa/financial-responsibility/codebook_colleges_fsa_financial_responsibility` |
| 90/10 Revenue | `college-university/fsa/90-10-revenue-percentages/codebook_colleges_fsa_90-10_revenue_percentages` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for full catalog and `fetch-patterns.md` for `get_codebook_url()`. For human reference — not parsed programmatically.

**Download Example:**
```bash
curl -sL "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/fsa/grants/colleges_fsa_grants.parquet" -o fsa_grants.parquet
```

### Filtering After Download

```python
import polars as pl

# Load data
df = pl.read_parquet("fsa_grants.parquet")

# Filter by year and state
df_ca_2020 = df.filter(
    (pl.col("year") == 2020) &
    (pl.col("fips") == 6)
)

# Filter by grant type (1 = Federal Pell Grant)
df_pell = df.filter(pl.col("grant_type") == 1)
```

## Quick Reference: Categorical Code Tables

### Grant Type Codes (grants endpoint)

| Code | Grant Type |
|------|------------|
| `1` | Federal Pell Grant |
| `2` | Federal Supplemental Educational Opportunity Grant (FSEOG) |
| `3` | TEACH Grant |
| `4` | Iraq and Afghanistan Service Grant |
| `5` | Children of Fallen Heroes Grant |

### Loan Type Codes (loans endpoint)

| Code | Loan Type |
|------|-----------|
| `1` | Subsidized Direct Loan - Undergraduate |
| `2` | Subsidized Direct Loan - Graduate |
| `3` | Subsidized Direct Loan - Total |
| `4` | Unsubsidized Direct Loan - Undergraduate |
| `5` | Unsubsidized Direct Loan - Graduate |
| `6` | Unsubsidized Direct Loan - Total |
| `7` | Direct Loan, Parent PLUS |
| `8` | Direct Loan, Grad PLUS |
| `9` | Direct Loan PLUS (sum of Parent PLUS and Grad PLUS) |
| `10` | Subsidized Federal Family Education Loans |
| `11` | Unsubsidized Federal Family Education Loans |
| `12` | Parent PLUS Federal Family Education Loans |
| `13` | Grad PLUS Federal Family Education Loans |
| `14` | PLUS Federal Family Education Loans |

### Award Type Codes (campus-based-volume endpoint)

| Code | Award Type |
|------|------------|
| `1` | Federal Supplemental Educational Opportunity Grants |
| `2` | Federal Work-Study |
| `3` | Perkins Loans |

### Yes/No Codes (allocation_flag, combined_flag)

| Code | Meaning |
|------|---------|
| `0` | No |
| `1` | Yes |
| `null` | Not reported |

### Missing Data Codes

| Code | Meaning |
|------|---------|
| `-1` | Missing/not reported |
| `-2` | Not applicable |
| `-3` | Suppressed data |

## Common Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `unitid` | IPEDS institution ID | Filter df by `unitid == 110635` |
| `fips` | State FIPS code (integer) | Filter df by `fips == 6` (California) |
| `year` | Academic year | Filter df by `year == 2020` |

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
