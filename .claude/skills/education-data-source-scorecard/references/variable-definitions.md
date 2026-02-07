# Variable Definitions

College Scorecard uses consistent naming conventions and special values. Understanding these is essential for building queries and interpreting results.

## Variable Naming Conventions

### General Pattern

```
[METRIC]_[POPULATION]_[TIMEFRAME]_[DISAGGREGATION]_[FLAGS]
```

### Common Prefixes

| Prefix | Meaning | Example |
|--------|---------|---------|
| `MD_` | Median | `MD_EARN_WNE_P6` |
| `MN_` | Mean | `MN_EARN_WNE_P6` |
| `PCT_` | Percent/Proportion | `PCT_PELL` |
| `NUM_` | Count | `NUM4_PUB` |
| `C_` | Completion | `C150_4` |
| `RPY_` | Repayment | `RPY_3YR_RT` |
| `DEBT_` | Debt | `DEBT_MDN` |

### Population Suffixes

| Suffix | Population |
|--------|------------|
| `_WNE` | Working and Not Enrolled |
| `_NWNE` | Not Working and Not Enrolled |
| `_PELL` | Pell Grant recipients |
| `_NOPELL` | Non-Pell students |
| `_DEP` | Dependent students |
| `_IND` | Independent students |
| `_MALE` | Male students |
| `_FEMALE` | Female students |

### Time Frame Suffixes

| Suffix | Time Frame |
|--------|------------|
| `_P6` | 6 years after entry |
| `_P8` | 8 years after entry |
| `_P10` | 10 years after entry |
| `_1YR` | 1 year |
| `_3YR` | 3 years |
| `_5YR` | 5 years |

### Income Disaggregation

| Suffix | Income Level | FAFSA Family Income |
|--------|--------------|---------------------|
| `_INC1` | Low income | $0-$30,000 |
| `_INC2` | Middle income | $30,001-$75,000 |
| `_INC3` | High income | $75,001+ |
| `_LO_INC` | Low income (alternate) | Bottom third |
| `_MD_INC` | Middle income (alternate) | Middle third |
| `_HI_INC` | High income (alternate) | Top third |

### Race/Ethnicity Suffixes

| Suffix | Group |
|--------|-------|
| `_WHITE` | White |
| `_BLACK` | Black or African American |
| `_HISP` | Hispanic |
| `_ASIAN` | Asian |
| `_AIAN` | American Indian/Alaska Native |
| `_NHPI` | Native Hawaiian/Pacific Islander |
| `_2MOR` | Two or more races |
| `_NRA` | Non-resident alien |
| `_UNKN` | Unknown |

### Flag Suffixes

| Suffix | Meaning |
|--------|---------|
| `_SUPP` | Suppression flag |
| `_N` | Count/denominator |
| `_POOLED` | Pooled cohort |

## Key Variable Categories

### Institutional Identifiers

| Variable | Description | Format |
|----------|-------------|--------|
| `UNITID` | IPEDS institution ID | 6-digit integer |
| `OPEID` | OPE ID (Title IV) | 8-digit string |
| `OPEID6` | 6-digit OPE ID | 6-digit string |
| `INSTNM` | Institution name | String |
| `CITY` | City | String |
| `STABBR` | State abbreviation | 2-letter code |
| `ZIP` | ZIP code | String |

### Institution Characteristics

| Variable | Description | Values |
|----------|-------------|--------|
| `CONTROL` | Control type | 1=Public, 2=Private NP, 3=Private FP |
| `PREDDEG` | Predominant degree | 0-4 (see below) |
| `HIGHDEG` | Highest degree | 0-4 |
| `LOCALE` | Urban/rural locale | 11-43 (see codes) |
| `HBCU` | HBCU indicator | 0, 1 |
| `MENONLY` | Men only | 0, 1 |
| `WOMENONLY` | Women only | 0, 1 |
| `RELAFFIL` | Religious affiliation | Various codes |

### Predominant Degree Codes

| Value | Description |
|-------|-------------|
| 0 | Not classified |
| 1 | Predominantly certificate |
| 2 | Predominantly associate's |
| 3 | Predominantly bachelor's |
| 4 | Entirely graduate |

### Admissions

| Variable | Description |
|----------|-------------|
| `ADM_RATE` | Admission rate |
| `ADM_RATE_ALL` | Admission rate, all campuses |
| `SATVR25` | SAT verbal 25th percentile |
| `SATVR75` | SAT verbal 75th percentile |
| `SATMT25` | SAT math 25th percentile |
| `SATMT75` | SAT math 75th percentile |
| `ACTCM25` | ACT composite 25th percentile |
| `ACTCM75` | ACT composite 75th percentile |

### Enrollment

| Variable | Description |
|----------|-------------|
| `UGDS` | Undergraduate enrollment |
| `UG` | Undergraduate Title IV enrollment |
| `UGDS_WHITE` | White enrollment share |
| `UGDS_BLACK` | Black enrollment share |
| `UGDS_HISP` | Hispanic enrollment share |
| `UGDS_ASIAN` | Asian enrollment share |
| `PPTUG_EF` | Part-time share |
| `PFTFTUG1_EF` | Full-time, first-time share |

### Cost Variables

| Variable | Description |
|----------|-------------|
| `COSTT4_A` | Average cost (academic year) |
| `COSTT4_P` | Average cost (program year) |
| `TUITIONFEE_IN` | In-state tuition and fees |
| `TUITIONFEE_OUT` | Out-of-state tuition and fees |
| `TUITIONFEE_PROG` | Program-year tuition |
| `NPT4_PUB` | Net price, public |
| `NPT4_PRIV` | Net price, private |
| `NPT4_PROG` | Net price, program |

### Aid Variables

| Variable | Description |
|----------|-------------|
| `PCTPELL` | Percent receiving Pell grants |
| `PCTFLOAN` | Percent receiving federal loans |
| `PELL_EVER` | Ever received Pell |
| `LOAN_EVER` | Ever received loan |
| `FTFTPCTPELL` | First-time full-time Pell share |
| `FTFTPCTFLOAN` | First-time full-time loan share |

### Earnings Variables

| Variable | Description |
|----------|-------------|
| `MD_EARN_WNE_P6` | Median earnings at 6 years |
| `MD_EARN_WNE_P8` | Median earnings at 8 years |
| `MD_EARN_WNE_P10` | Median earnings at 10 years |
| `PCT10_EARN_WNE_P6` | 10th percentile earnings |
| `PCT25_EARN_WNE_P6` | 25th percentile earnings |
| `PCT75_EARN_WNE_P6` | 75th percentile earnings |
| `PCT90_EARN_WNE_P6` | 90th percentile earnings |
| `COUNT_WNE_P6` | Count working and not enrolled |

### Debt Variables

| Variable | Description |
|----------|-------------|
| `DEBT_MDN` | Median debt |
| `DEBT_MEAN` | Mean debt |
| `GRAD_DEBT_MDN` | Median debt, completers |
| `WDRAW_DEBT_MDN` | Median debt, withdrawals |
| `LO_INC_DEBT_MDN` | Median debt, low income |
| `MD_INC_DEBT_MDN` | Median debt, middle income |
| `HI_INC_DEBT_MDN` | Median debt, high income |

### Repayment Variables

| Variable | Description |
|----------|-------------|
| `RPY_1YR_RT` | 1-year repayment rate |
| `RPY_3YR_RT` | 3-year repayment rate |
| `RPY_5YR_RT` | 5-year repayment rate |
| `RPY_7YR_RT` | 7-year repayment rate |
| `CDR3` | 3-year cohort default rate |
| `DBRR1_FED_UG_RT` | Dollar-based repayment rate, 1 year |
| `DBRR4_FED_UG_RT` | Dollar-based repayment rate, 4 years |

### Completion Variables

| Variable | Description |
|----------|-------------|
| `C150_4` | 150% completion rate, 4-year |
| `C150_L4` | 150% completion rate, <4-year |
| `C200_4` | 200% completion rate, 4-year |
| `C200_L4` | 200% completion rate, <4-year |
| `C150_4_POOLED` | Pooled 150% rate |
| `RET_FT4` | Retention rate, 4-year full-time |
| `RET_PT4` | Retention rate, 4-year part-time |

## Special Values

### Missing Data Codes

| Value | Meaning | When Used |
|-------|---------|-----------|
| `NULL` | Not available | Data not collected or not applicable |
| `PrivacySuppressed` | Privacy suppressed | Below threshold (typically 30) |
| `-999` | Not reported | Institution didn't report |
| `-2` | Not applicable | Doesn't apply to institution type |

### Handling Special Values

```python
import polars as pl

# Filter out suppressed values
df = df.filter(
    ~pl.col("MD_EARN_WNE_P6").is_in(["PrivacySuppressed", "NULL"])
)

# Convert to numeric (strings become null)
df = df.with_columns(
    pl.col("MD_EARN_WNE_P6").cast(pl.Float64, strict=False)
)

# Exclude invalid numeric codes
df = df.filter(
    (pl.col("DEBT_MDN") > 0) | pl.col("DEBT_MDN").is_null()
)
```

## Variable Data Types

### Numeric Variables

Most outcome variables should be numeric:
- Earnings: float
- Rates: float (0-1 or percentage)
- Counts: integer
- Debt: float

### Categorical Variables

| Variable | Type | Values |
|----------|------|--------|
| `CONTROL` | categorical | 1, 2, 3 |
| `PREDDEG` | categorical | 0-4 |
| `LOCALE` | categorical | 11-43 |
| `STABBR` | string | State codes |

### String Variables

| Variable | Type |
|----------|------|
| `INSTNM` | string |
| `CITY` | string |
| `ZIP` | string |
| `OPEID` | string (leading zeros) |

## API Variable Names vs Download Names

The API uses different naming in some cases:

| Download Name | API Name |
|---------------|----------|
| `MD_EARN_WNE_P6` | `latest.earnings.6_yrs_after_entry.median` |
| `C150_4` | `latest.completion.completion_rate_4yr_150nt` |
| `DEBT_MDN` | `latest.aid.median_debt.completers.overall` |

**Recommendation:** Use download files for bulk analysis; API for specific queries.

## Commonly Used Variable Sets

### Earnings Analysis

```
MD_EARN_WNE_P6, MD_EARN_WNE_P10,
PCT25_EARN_WNE_P6, PCT75_EARN_WNE_P6,
COUNT_WNE_P6, UNITID, INSTNM, CONTROL
```

### Debt Analysis

```
DEBT_MDN, GRAD_DEBT_MDN, WDRAW_DEBT_MDN,
PCTFLOAN, RPY_3YR_RT, CDR3,
UNITID, INSTNM, CONTROL
```

### Completion Analysis

```
C150_4, C150_4_POOLED, C150_4_PELL,
RET_FT4, TRANS_4_POOLED,
UNITID, INSTNM, CONTROL, ADM_RATE
```

### Institutional Context

```
UNITID, INSTNM, CITY, STABBR, CONTROL,
PREDDEG, HIGHDEG, LOCALE, HBCU,
UGDS, ADM_RATE, PCTPELL
```

## Field-Level Variable Patterns

Field of study data uses CIP codes:

| Variable | Description |
|----------|-------------|
| `CIPCODE` | CIP code (4 or 6 digit) |
| `CIPDESC` | CIP description |
| `CREDLEV` | Credential level |
| `CREDDESC` | Credential description |
| `EARN_MDN_HI_1YR` | Median earnings, 1 year post-completion |
| `EARN_MDN_HI_2YR` | Median earnings, 2 years post-completion |
| `DEBT_ALL_STGP_ANY_MDN` | Median debt by program |

## Data Dictionary Reference

The official data dictionary (Excel file) contains:
- All variable names
- Descriptions
- Data sources
- Cohort timing
- Suppression rules

Download from: `collegescorecard.ed.gov/assets/CollegeScorecardDataDictionary.xlsx`
