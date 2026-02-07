# Earnings Data

College Scorecard's earnings data represents actual post-college earnings from IRS W-2 records, making it uniquely valuable for understanding labor market outcomes.

## Data Source: IRS/Treasury

Earnings come from IRS W-2 wage records matched to students via Social Security numbers:

| Aspect | Detail |
|--------|--------|
| Source | IRS W-2 forms (employer-reported wages) |
| Matching | Treasury matches NSLDS records to tax filings |
| Reporting | Aggregated to protect individual privacy |
| Coverage | Employed individuals with W-2 income only |

### What W-2 Earnings Include

- Wages, salaries, tips
- Employer-reported compensation
- Most full-time and part-time employment

### What W-2 Earnings Exclude

| Excluded Income | Impact on Analysis |
|-----------------|-------------------|
| Self-employment (1099) | Entrepreneurs, gig workers missing |
| Business income | Small business owners missing |
| Investment income | Passive income not counted |
| Non-reported income | Cash economy excluded |
| Foreign earnings | Those working abroad missing |

## Cohort Definitions

### Entry Cohort vs Completion Cohort

Scorecard primarily uses **entry cohorts** - students grouped by when they first enrolled:

```
Entry Cohort Example:
- Students who entered in Fall 2008
- 6-year earnings measured in 2014
- 10-year earnings measured in 2018
```

**Important:** Earnings are measured from entry, NOT graduation. This means:
- A student who took 4 years to graduate has earnings measured 2 years post-graduation at the "6-year" mark
- A student who took 6 years to graduate has earnings measured AT graduation at the "6-year" mark

### Entry Cohort Construction

Students included in entry cohorts:
- First-time undergraduates who received Title IV aid
- Includes full-time AND part-time students
- Includes students who transferred in (at receiving institution)
- Includes students who did not complete

### Pooled Cohorts

Many metrics use "pooled" cohorts combining multiple years:
- Increases sample size
- Reduces suppression
- Typical pooling: 2-4 entry years combined

Variable naming convention: `*_POOLED` or `*_POOLED_SUPP`

## Time Horizons

### Available Measurement Points

| Metric | Years After Entry | What It Captures |
|--------|------------------|------------------|
| 6-year earnings | 6 years | Early career, ~2 years post-graduation for 4-year completers |
| 8-year earnings | 8 years | Early-mid career |
| 10-year earnings | 10 years | Mid-career, ~6 years post-graduation for 4-year completers |

### Interpreting Time Horizons

**6-Year Earnings:**
- Most commonly reported metric
- Captures early career earnings
- For 4-year completers: ~2 years post-graduation
- For 2-year completers: ~4 years post-graduation
- For non-completers: earnings regardless of completion status

**10-Year Earnings:**
- Better reflection of career trajectory
- More stable earnings picture
- Fewer students still in graduate school
- But: cohorts are even older (11+ years old when data released)

### Data Vintage and Lag

Earnings data has significant lag:

```
Example for 2024 data release:
├─ 10-year earnings
│   ├─ Entry cohort: ~2014
│   ├─ Measured in: ~2024
│   ├─ Reflects: Students who entered 10+ years ago
│   └─ Labor market: 2024 conditions applied to old cohort
└─ 6-year earnings
    ├─ Entry cohort: ~2018
    ├─ Measured in: ~2024
    └─ Reflects: Students who entered 6+ years ago
```

**Implication:** Earnings data reflects students and programs from years ago. Rapid changes in:
- Program quality
- Curriculum
- Labor market conditions
- Industry demand

...may not be reflected in current data.

## Earnings Metrics

### Median Earnings (Primary Metric)

| Variable | Description |
|----------|-------------|
| `MD_EARN_WNE_P6` | Median earnings, 6 years after entry |
| `MD_EARN_WNE_P8` | Median earnings, 8 years after entry |
| `MD_EARN_WNE_P10` | Median earnings, 10 years after entry |

"WNE" = Working and Not Enrolled

### Percentile Earnings

| Variable | Description |
|----------|-------------|
| `PCT10_EARN_WNE_P*` | 10th percentile earnings |
| `PCT25_EARN_WNE_P*` | 25th percentile earnings |
| `PCT75_EARN_WNE_P*` | 75th percentile earnings |
| `PCT90_EARN_WNE_P*` | 90th percentile earnings |

### Earnings by Family Income

Disaggregated by FAFSA-reported family income tercile:

| Suffix | Family Income Level |
|--------|-------------------|
| `_INC1_` | Lowest third (0-$30,000) |
| `_INC2_` | Middle third ($30,001-$75,000) |
| `_INC3_` | Highest third ($75,001+) |

Example: `MD_EARN_WNE_INC1_P6` = Median earnings at 6 years for lowest-income students

### Working and Enrollment Status

| Variable | Description |
|----------|-------------|
| `COUNT_WNE_P*` | Number working and not enrolled |
| `COUNT_NWNE_P*` | Number not working and not enrolled |
| `PCT_EARN_WNE_P*` | Share working and not enrolled |

## Working Population Filter

**Critical:** Earnings are only calculated for students who are:
1. Working (have positive W-2 earnings)
2. Not enrolled in postsecondary education

### Who Is Excluded from Earnings Calculations

| Excluded Group | Reason | Impact |
|----------------|--------|--------|
| Graduate school students | Enrolled, not working | Fields with high grad school rates (e.g., biology, pre-law) show higher earnings than they would if grads included |
| Non-employed | No W-2 income | Unemployed, stay-at-home parents, disabled excluded |
| Self-employed only | No W-2 | Entrepreneurs missing |
| Deceased | No W-2 | Small effect |
| Living abroad | No W-2 | May affect certain fields |

### Implications for Analysis

- Fields with high graduate school attendance may appear to have HIGHER earnings (low earners are still in school)
- Institutions/programs with higher unemployment rates are NOT penalized in earnings metrics
- Self-employment heavy fields (arts, consulting) may show lower median earnings

## Earnings Suppression

Earnings are suppressed when privacy thresholds are not met:

### Suppression Rules

| Threshold | Action |
|-----------|--------|
| < 30 students with positive earnings | Earnings suppressed |
| Small cells in disaggregations | Additional suppression |

### Variables Indicating Suppression

> **Portal Encoding:** In the HuggingFace mirror parquet files, **`null` is the primary indicator** for suppressed/missing data.

| Data Pattern | Meaning | Notes |
|--------------|---------|-------|
| `null` | Suppressed or missing | Primary indicator in parquet |
| Positive value | Valid earnings | Actual data |
| `EARN_*_SUPP` = 1 | Suppression flag | Flag variables use 0/1 |

### High Suppression Rates Affect

- Small institutions
- Small programs (by CIP code)
- Disaggregations (by income, race, gender)
- Newer programs without enough cohorts

## Cohort Year Mapping

Understanding which cohort corresponds to which measurement year:

### Institution-Level Earnings

For annual data files (e.g., `merged_2022_23`):

| Variable | Entry Cohort Years (Approx) | Measurement Year |
|----------|---------------------------|------------------|
| 6-year earnings | 2015-16, 2016-17 | 2021, 2022 |
| 8-year earnings | 2013-14, 2014-15 | 2021, 2022 |
| 10-year earnings | 2011-12, 2012-13 | 2021, 2022 |

**Note:** Specific cohort years vary by data release. Always check documentation.

### Data Errata

**Known Issue (2022-2023):** Entry-cohort earnings calculations in some files were calculated with misaligned cohorts. Check the College Scorecard errata document for affected variables.

## Recommended Practices

### Before Earnings Analysis

1. **Identify cohort timing** - Know which entry years are reflected
2. **Check suppression rates** - How many institutions/programs have data?
3. **Note WNE filter** - Earnings exclude non-workers and enrolled students
4. **Understand coverage** - Title IV recipients only

### Reporting Earnings

1. **State population clearly**: "Title IV aid recipients who were working and not enrolled"
2. **Note time context**: "Earnings measured 6 years after enrollment"
3. **Acknowledge lag**: "Reflects students who entered in [year]"
4. **Report suppression**: "X% of programs had suppressed earnings data"

### Comparing Earnings

**Valid comparisons:**
- Same institution type, similar aid populations
- Same field across similar institution types
- Same institution over time (with cohort caveats)

**Invalid comparisons:**
- Scorecard earnings vs BLS occupational wages
- Scorecard earnings vs Census income
- Scorecard vs alumni survey earnings
- Institutions with very different Title IV coverage rates

## Example: Interpreting 6-Year Earnings

```
Institution A: Median 6-year earnings = $45,000

What this means:
- Half of Title IV aid recipients earned more, half less
- Measured 6 years after first enrollment
- Only includes those working and not enrolled
- Excludes students in graduate school
- Excludes unemployed, self-employed, those abroad
- Reflects cohort that entered ~6 years ago
- May not reflect current program quality or labor market
```
