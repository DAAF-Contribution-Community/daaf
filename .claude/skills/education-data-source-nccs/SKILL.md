---
name: education-data-source-nccs
description: National Center for Charitable Statistics (NCCS) nonprofit organization data from the Urban Institute. Use when researching private nonprofit colleges and universities, understanding Form 990 financial data, analyzing nonprofit higher education institutions, or supplementing IPEDS data with detailed financial and governance information from IRS filings.
metadata:
  audience: data-analysts
  domain: education-data
---

# NCCS: National Center for Charitable Statistics

The National Center for Charitable Statistics (NCCS) is a research center and open data platform operated by the Urban Institute's Center on Nonprofits and Philanthropy. It serves as the principal U.S. repository for empirical data on the nonprofit and charitable sector, derived primarily from IRS tax filings.

## Why NCCS Matters for Education Research

Private nonprofit colleges and universities are 501(c)(3) tax-exempt organizations that file IRS Form 990. NCCS data provides:

- **Financial depth**: Detailed revenue, expenses, assets, liabilities, and endowment data beyond what IPEDS collects
- **Governance information**: Board composition, executive compensation, and organizational structure
- **Historical coverage**: Data spanning 30+ years for trend analysis
- **Complementary perspective**: Different financial reporting framework than IPEDS

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `nonprofit-data.md` | NCCS datasets and what they contain | Understanding available data sources |
| `form-990.md` | IRS Form 990 structure and data elements | Understanding what information is collected |
| `education-relevance.md` | How NCCS relates to higher education | Connecting nonprofit data to education research |
| `ntee-codes.md` | Nonprofit classification system | Finding and filtering educational institutions |
| `variable-definitions.md` | Key financial and organizational variables | Building queries and analysis |

## Decision Trees

### What data am I looking for?

```
Research need?
├─ Financial data for private colleges → ./references/form-990.md
│   ├─ Revenue breakdown → Part VIII (Statement of Revenue)
│   ├─ Expenses by function → Part IX (Statement of Functional Expenses)
│   ├─ Assets and liabilities → Part X (Balance Sheet)
│   └─ Endowment details → Schedule D
├─ Governance/leadership → ./references/form-990.md
│   ├─ Board members → Part VII (Compensation)
│   ├─ Executive compensation → Part VII, Schedule J
│   └─ Policies and procedures → Part VI (Governance)
├─ Organizational characteristics → ./references/nonprofit-data.md
│   ├─ Basic info (name, address, EIN) → BMF
│   ├─ Tax-exempt type → BMF (SUBSECCD)
│   └─ NTEE classification → BMF (NTEECC)
└─ Identify institutions → ./references/ntee-codes.md
    ├─ All higher education → NTEE B40-B50
    ├─ Universities → B40, B41, B42, B43
    └─ Community colleges → B44
```

### Which NCCS dataset should I use?

```
Dataset selection?
├─ Need universe of all nonprofits?
│   └─ Business Master File (BMF) → ./references/nonprofit-data.md
├─ Need detailed financial variables?
│   ├─ Large organizations (full 990 filers) → Core PC files
│   ├─ All organizations (990 + 990EZ) → Core PZ files
│   └─ Maximum detail (2000+ fields) → Efile database
├─ Need private foundations?
│   └─ Core PF or 990-PF Efile data
└─ Need small grassroots orgs?
    └─ 990-N ePostcard database
```

### How do I connect NCCS to other education data?

```
Linking NCCS to education data?
├─ Need to match to IPEDS?
│   └─ See ./references/education-relevance.md (EIN-UNITID crosswalk)
├─ Need geographic analysis?
│   └─ Use BMF geocoded addresses + Census crosswalks
├─ Want institutional comparisons?
│   └─ Filter by NTEE codes B40-B50 for higher ed
└─ Analyzing trends over time?
    └─ Use Core data panel (1989-present)
```

## Quick Reference: NCCS Datasets

| Dataset | Description | Coverage | Key Use |
|---------|-------------|----------|---------|
| Business Master File (BMF) | All active tax-exempt organizations | ~3.8M orgs | Sampling frame, basic info |
| NCCS Core Series | 990/990EZ filer financials | 1989-2022 | Historical financial analysis |
| IRS 990 Efile | Full electronic filings (2000+ fields) | 2012-present | Detailed governance, programs |
| Form 990-N ePostcard | Small nonprofits (<$50K revenue) | 2007-present | Grassroots organizations |
| Pub78 | Organizations eligible for tax-deductible donations | Current | Verify charitable status |

## Quick Reference: Key Identifiers

| Identifier | Format | Description |
|------------|--------|-------------|
| EIN | 9-digit number | Employer Identification Number (unique to each nonprofit) |
| NTEECC | Letter + 2 digits | NTEE classification code (e.g., B42 = 4-year college) |
| SUBSECCD | 2-digit code | IRS subsection (03 = 501(c)(3) charity) |
| FIPS | 5-digit code | State + county geographic identifier |

## Quick Reference: Education NTEE Codes

| Code | Description |
|------|-------------|
| B20-B29 | Elementary & Secondary Schools |
| B40 | Higher Education Institutions (General) |
| B41 | Two-Year Colleges |
| B42 | Undergraduate Colleges (4-year) |
| B43 | Universities |
| B50 | Graduate/Professional Schools |
| B60 | Adult/Continuing Education |
| B70 | Libraries |
| B80 | Student Services/Organizations |
| B90 | Educational Services/Schools N.E.C. |

## Exploration Workflow

1. **Identify target organizations**
   - Filter BMF by NTEE codes (B40-B50 for higher ed)
   - Verify 501(c)(3) status (SUBSECCD = 03)
   - Note EINs for organizations of interest

2. **Select appropriate dataset**
   - Core PZ for broad coverage
   - Core PC for detailed financials (larger orgs)
   - Efile for maximum detail (governance, compensation)

3. **Extract and clean data**
   - Download relevant years
   - Merge with BMF for organizational attributes
   - Handle missing data codes (-1, -2, -3)

4. **Link to education data (if needed)**
   - Use EIN-UNITID crosswalk for IPEDS matching
   - Apply Census crosswalks for geographic analysis

5. **Analyze**
   - See variable definitions for meaning and limitations
   - Apply appropriate error checking procedures

## Key Differences: NCCS vs. IPEDS

| Aspect | NCCS (Form 990) | IPEDS |
|--------|-----------------|-------|
| **Coverage** | All 501(c)(3) nonprofits | Title IV institutions only |
| **Reporting Basis** | IRS fiscal year | IPEDS survey cycles |
| **Financial Framework** | Nonprofit accounting (GAAP) | Education-specific categories |
| **Governance** | Detailed board/compensation data | Limited HR data |
| **Programs** | Mission statements, activities | Degree programs, enrollment |
| **Identifier** | EIN | UNITID |
| **Update Frequency** | Annual (with lag) | Annual |

## Common Pitfalls

- **Filing threshold**: Organizations under $200K revenue may file 990-EZ (fewer variables)
- **Fiscal year variation**: Nonprofits have different fiscal year ends
- **Missing data**: Not all fields required; some intentionally redacted (donor names)
- **Classification accuracy**: ~25% of NTEE codes estimated to be imprecise
- **Consolidation**: Some university systems file consolidated 990s
- **Form version changes**: 990 was redesigned in 2008; variable definitions changed
- **Using Portal integer codes**: The Education Data Portal uses integer encodings (see below)

## Education Data Portal Encoding Warning

> **CRITICAL:** The Education Data Portal encodes ALL categorical variables as **integers**, not strings.

### Integer Encoding Examples

| Variable | Portal Value | Meaning |
|----------|-------------|---------|
| `fips` | `6` | California (not "CA" or "California") |
| `fips` | `-1` | Missing/not reported |
| `fips` | `-2` | Not applicable |
| `fips` | `-3` | Suppressed data |
| `mult_ein_flag` | `0` | No (single EIN) |
| `mult_ein_flag` | `1` | Yes (multiple EINs) |

### Variable Names

All variable names are **lowercase** in Portal data:
- `unitid` (not `UNITID`)
- `fips` (not `FIPS` or `fips_code`)
- `contributions_total` (not `CONT`)
- `revenue_total` (not `TOTREV`)

### Data Access Pattern

```python
import polars as pl

# Download from HuggingFace mirror (recommended)
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/nccs/990-forms/colleges_nccs_all.parquet"
df = pl.read_parquet(url)

# Filter by state using integer FIPS
california = df.filter(pl.col("fips") == 6)  # California
texas = df.filter(pl.col("fips") == 48)       # Texas

# Handle missing data codes
df_clean = df.filter(pl.col("fips") >= 1)  # Exclude -1, -2, -3
```

### Mapping Portal Variables to Original NCCS Names

The Portal uses descriptive lowercase names mapped from original 990 variables:

| Portal Name | Original NCCS/990 | Description |
|-------------|-------------------|-------------|
| `contributions_total` | `CONT` | Total contributions |
| `prog_serv_rev` | `PROGREV` | Program service revenue |
| `revenue_total` | `TOTREV` | Total revenue |
| `expenses_total` | `EXPS` | Total expenses |
| `total_assets_eoy` | `TOTASS` | Total assets (end of year) |
| `net_assets_eoy` | `NETASS` | Net assets (end of year) |
| `compensation_officers` | `COMPENS` | Officer compensation |
| `salaries_other` | `OTHSAL` | Other salaries |

## Cross-Reference to Related Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `education-data-explorer` | Discover Urban Institute education datasets | Finding what data exists |
| `education-data-query` | Download data from HuggingFace mirror | After identifying endpoints |

> **Note:** The `education-data-query` skill now uses mirror-based downloads from HuggingFace rather than direct API calls. See that skill for current download patterns.

## Topic Index

| Topic | Reference File |
|-------|---------------|
| BMF overview | `./references/nonprofit-data.md` |
| Core data series | `./references/nonprofit-data.md` |
| Efile database | `./references/nonprofit-data.md` |
| Form 990 structure | `./references/form-990.md` |
| Revenue variables | `./references/form-990.md` |
| Expense variables | `./references/form-990.md` |
| Balance sheet | `./references/form-990.md` |
| Governance data | `./references/form-990.md` |
| Schedule details | `./references/form-990.md` |
| Linking to IPEDS | `./references/education-relevance.md` |
| Private college identification | `./references/education-relevance.md` |
| Supplementing education research | `./references/education-relevance.md` |
| NTEE code structure | `./references/ntee-codes.md` |
| Education NTEE codes | `./references/ntee-codes.md` |
| NTEEV2 format | `./references/ntee-codes.md` |
| Financial variables | `./references/variable-definitions.md` |
| Variable naming conventions | `./references/variable-definitions.md` |
| Data quality issues | `./references/variable-definitions.md` |
